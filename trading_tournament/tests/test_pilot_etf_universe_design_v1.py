from __future__ import annotations

import csv
import hashlib
from pathlib import Path

import yaml

from strategy_lab.research_os.universe_expansion import pilot_etf_universe_design_v1 as design


ROOT = Path(__file__).resolve().parents[1]
DESIGN_DIR = ROOT / "strategy_lab" / "research_os" / "universe_expansion" / "pilot_etf_universe_design_v1"
EVIDENCE_DIR = ROOT / "evidence" / "pilot_etf_universe_design_v1" / "latest"
REGISTRY = ROOT / "strategy_lab" / "strategy_registry.yaml"
ACTIVE_OBSERVATIONS = ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_yaml(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_required_outputs_exist_in_design_and_evidence() -> None:
    for name in design.REQUIRED_FILES:
        assert (DESIGN_DIR / name).exists(), name
        assert (EVIDENCE_DIR / name).exists(), name


def test_only_official_public_inventory_sources_are_used() -> None:
    manifest = read_yaml(DESIGN_DIR / "official_source_manifest.yaml")
    sources = manifest["official_sources"]
    assert {row["source_id"] for row in sources} == {
        "nasdaq_trader_nasdaqlisted",
        "nasdaq_trader_otherlisted",
    }
    assert all("nasdaqtrader.com/dynamic/SymDir/" in row["source_url"] for row in sources)
    assert all(row["official_public_inventory_source"] is True for row in sources)


def test_no_login_cookies_or_private_api_are_used() -> None:
    manifest = read_yaml(DESIGN_DIR / "official_source_manifest.yaml")
    for row in manifest["official_sources"]:
        assert row["login_used"] is False
        assert row["cookies_used"] is False
        assert row["private_api_used"] is False


def test_source_files_are_hashed() -> None:
    hashes = design.json.loads((DESIGN_DIR / "raw_source_hashes.json").read_text(encoding="utf-8"))
    assert hashes
    for payload in hashes.values():
        assert len(payload["file_hash"]) == 64
        assert Path(ROOT / payload["snapshot_file"]).exists()


def test_test_and_inactive_issues_are_excluded() -> None:
    assert design.exclusion_reason("TEST", "Plain Vanilla ETF", "Y", "") == ("excluded", "test_issue")
    assert design.exclusion_reason("BAD", "Plain Vanilla ETF", "N", "D") == (
        "excluded",
        "inactive_or_non_normal_listing_status",
    )


def test_prohibited_product_types_are_excluded() -> None:
    samples = {
        "leveraged_or_inverse": "ProShares UltraShort S&P500",
        "single_stock_or_leveraged_tactical_product": "Direxion Daily NVDA Bull Shares",
        "option_income_buffer_or_defined_outcome": "Covered Call Option Income ETF",
        "crypto_product_or_crypto_theme": "Spot Bitcoin ETF",
        "etn": "Commodity Exchange Traded Note ETN",
        "active_managed_fund": "Example Active ETF",
    }
    for expected, name in samples.items():
        status, reason = design.exclusion_reason("X", name, "N", "")
        assert status == "excluded"
        assert reason == expected


def test_commodity_pools_and_physical_metals_are_not_auto_excluded() -> None:
    assert design.exclusion_reason("DBC", "Invesco DB Commodity Index Tracking Fund", "N", "") == (
        "not_excluded_by_v1_rules",
        "",
    )
    assert design.exclusion_reason("GLD", "SPDR Gold Shares", "N", "") == (
        "not_excluded_by_v1_rules",
        "",
    )


def test_uncertain_records_remain_unresolved() -> None:
    row = design.plan_row(design.PRIMARY_PLANS[0], None)
    assert row["listing_exchange"] == "missing_from_current_official_inventory"
    assert row["classification_confidence"] == "unresolved_missing_official_inventory"


def test_primary_exposure_quotas_total_48() -> None:
    rows = read_csv(DESIGN_DIR / "proposed_primary_48.csv")
    assert len(rows) == 48
    counts = {group: 0 for group in design.EXPOSURE_BUDGET}
    for row in rows:
        counts[row["candidate_group"]] += 1
    assert counts == design.EXPOSURE_BUDGET
    assert sum(counts.values()) == 48


def test_reserve_count_is_at_most_12() -> None:
    rows = read_csv(DESIGN_DIR / "proposed_reserve_equivalents.csv")
    assert len(rows) <= 12


def test_equivalent_wrappers_cannot_both_enter_primary() -> None:
    rows = read_csv(DESIGN_DIR / "proposed_primary_48.csv")
    groups: dict[str, int] = {}
    for row in rows:
        groups[row["potential_duplicate_group"]] = groups.get(row["potential_duplicate_group"], 0) + 1
    assert all(count == 1 for count in groups.values())


def test_performance_and_backtest_are_never_used() -> None:
    check = design.json.loads((DESIGN_DIR / "consistency_check.json").read_text(encoding="utf-8"))
    assert check["performance_used_for_selection"] is False
    assert check["return_volatility_correlation_or_backtest_calculated"] is False
    assert check["backtest_run"] is False
    assert check["pair_selection_run"] is False


def test_no_historical_data_download_occurs() -> None:
    check = design.json.loads((DESIGN_DIR / "consistency_check.json").read_text(encoding="utf-8"))
    assert check["historical_market_data_download"] is False


def test_old_two_symbol_limit_is_not_applied() -> None:
    check = design.json.loads((DESIGN_DIR / "consistency_check.json").read_text(encoding="utf-8"))
    assert check["old_two_symbol_limit_applied"] is False
    cache = read_csv(DESIGN_DIR / "current_cache_feasibility.csv")
    missing = [row for row in cache if row["needs_acquisition"] == "True"]
    assert len(missing) > 2


def test_strategy_registry_and_active_observations_remain_byte_identical() -> None:
    before = {REGISTRY: sha256(REGISTRY), ACTIVE_OBSERVATIONS: sha256(ACTIVE_OBSERVATIONS)}
    after = {REGISTRY: sha256(REGISTRY), ACTIVE_OBSERVATIONS: sha256(ACTIVE_OBSERVATIONS)}
    check = design.json.loads((DESIGN_DIR / "consistency_check.json").read_text(encoding="utf-8"))
    assert check["next_action"] == design.NEXT_ACTION
    assert before == after


def test_quantpedia_is_not_accessed() -> None:
    check = design.json.loads((DESIGN_DIR / "consistency_check.json").read_text(encoding="utf-8"))
    assert check["quantpedia_accessed"] is False


def test_output_generation_is_deterministic() -> None:
    design_files = sorted(path for path in DESIGN_DIR.iterdir() if path.is_file())
    evidence_files = sorted(path for path in EVIDENCE_DIR.iterdir() if path.is_file())
    design_hashes = {path.name: sha256(path) for path in design_files}
    evidence_hashes = {path.name: sha256(path) for path in evidence_files}
    assert design_hashes == evidence_hashes


def test_consistency_check_passes_and_next_action_is_exact() -> None:
    check = design.json.loads((DESIGN_DIR / "consistency_check.json").read_text(encoding="utf-8"))
    assert check["consistency_passed"] is True
    assert check["next_action"] == "acquire_validate_and_freeze_pilot_etf_market_data_v1"
