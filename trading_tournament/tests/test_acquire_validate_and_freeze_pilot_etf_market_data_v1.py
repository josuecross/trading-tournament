from __future__ import annotations

import csv
import hashlib
import json
from datetime import date
from pathlib import Path

import yaml

from strategy_lab.research_os.universe_expansion import acquire_validate_and_freeze_pilot_etf_market_data_v1 as freeze


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "strategy_lab" / "research_os" / "universe_expansion" / "pilot_etf_market_data_freeze_v1"
EVIDENCE_DIR = ROOT / "evidence" / "pilot_etf_market_data_freeze_v1" / "latest"
SNAPSHOT_DIR = ROOT / "data" / "universe_expansion" / "pilot_etf_market_data_v1"
STEP1_DESIGN = ROOT / "strategy_lab" / "research_os" / "universe_expansion" / "pilot_etf_universe_design_v1"
REGISTRY = ROOT / "strategy_lab" / "strategy_registry.yaml"
ACTIVE_OBSERVATIONS = ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(name: str) -> list[dict[str, str]]:
    with (OUTPUT_DIR / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_json(name: str):
    return json.loads((OUTPUT_DIR / name).read_text(encoding="utf-8"))


def read_yaml(name: str):
    return yaml.safe_load((OUTPUT_DIR / name).read_text(encoding="utf-8"))


def test_required_outputs_exist_in_design_and_evidence() -> None:
    for name in freeze.OUTPUT_FILES:
        assert (OUTPUT_DIR / name).exists(), name
        assert (EVIDENCE_DIR / name).exists(), name


def test_step1_remains_byte_identical() -> None:
    payload = read_json("step1_packet_hash_verification.json")
    assert payload["byte_identical_after_step2"] is True
    assert payload["before"] == payload["after"]


def test_only_frozen_60_symbols_can_enter_acquisition() -> None:
    provider = read_csv("provider_request_manifest.csv")
    snapshots = read_csv("immutable_snapshot_manifest.csv")
    assert {row["symbol"] for row in provider} == set(freeze.FROZEN_SYMBOLS)
    assert {row["symbol"] for row in snapshots} == set(freeze.FROZEN_SYMBOLS)
    assert all(row["in_frozen_60"] == "True" for row in provider)


def test_no_off_list_replacement_can_enter() -> None:
    final = read_csv("final_primary_universe.csv")
    reserves = read_csv("final_reserve_universe.csv")
    assert {row["symbol"] for row in final} <= set(freeze.FROZEN_SYMBOLS)
    assert {row["symbol"] for row in reserves} <= set(freeze.FROZEN_SYMBOLS)
    assert read_json("consistency_check.json")["off_list_replacement_added"] is False


def test_existing_valid_data_are_reused_and_research_caches_not_overwritten() -> None:
    provider = read_csv("provider_request_manifest.csv")
    assert any(row["existing_valid_data_reused"] == "True" for row in provider)
    assert read_json("consistency_check.json")["general_research_caches_overwritten"] is False


def test_single_frozen_endpoint_recorded_before_eligibility() -> None:
    endpoint = read_json("frozen_data_endpoint.json")
    assert endpoint["endpoint_recorded_before_eligibility"] is True
    assert endpoint["final_frozen_endpoint"] == "2026-07-16"
    assert endpoint["execution_date_assumed_complete_session"] is False


def test_data_before_inception_and_exchange_holidays_not_treated_as_missing() -> None:
    history = read_csv("history_and_integrity_metrics.csv")
    assert all(row["data_before_inception_treated_as_missing"] == "False" for row in history)
    assert all(row["exchange_holidays_treated_as_missing"] == "False" for row in history)
    sessions = freeze.expected_sessions(date(2026, 4, 2), date(2026, 4, 6))
    assert date(2026, 4, 3) not in sessions  # Good Friday
    assert date(2026, 4, 2) in sessions
    assert date(2026, 4, 6) in sessions


def test_missing_prices_or_volume_are_not_forward_filled() -> None:
    history = read_csv("history_and_integrity_metrics.csv")
    assert all(row["prices_or_volume_forward_filled"] == "False" for row in history)


def test_adjusted_close_and_volume_are_mandatory() -> None:
    assert "adj_close" in freeze.REQUIRED_MARKET_DATA_FIELDS
    assert "volume" in freeze.REQUIRED_MARKET_DATA_FIELDS
    check = read_json("consistency_check.json")
    assert check["adjusted_close_and_volume_mandatory"] is True


def test_core_thresholds_are_applied_exactly_and_not_lowered() -> None:
    assert freeze.PRIMARY_ELIGIBILITY["min_valid_daily_adjusted_price_observations"] == 2000
    assert freeze.PRIMARY_ELIGIBILITY["latest_adjusted_price_minimum"] == 5.0
    assert freeze.PRIMARY_ELIGIBILITY["latest_60_session_median_dollar_volume_minimum"] == 10_000_000.0
    assert freeze.PRIMARY_ELIGIBILITY["missing_session_rate_maximum"] == 0.01
    eligibility = read_csv("eligibility_results.csv")
    assert all(row["thresholds_lowered_to_fill_quota"] == "False" for row in eligibility)


def test_actively_managed_funds_are_deferred_not_silently_discarded() -> None:
    identity = [
        {
            "symbol": "ACTIVE",
            "current_official_name": "Example Active ETF",
            "index_tracking_or_active_status": "active_or_actively_managed",
            "product_structure": "conventional_unleveraged_etf",
            "leveraged_or_inverse_status": "not_flagged",
            "single_stock_status": "not_flagged",
            "options_income_covered_call_buffer_defined_outcome_status": "not_flagged",
            "crypto_or_digital_asset_status": "not_flagged",
            "etn_status": "not_flagged",
        }
    ]
    assert freeze.active_fund_rows(identity)[0]["deferred_status"] == "future_active_etf_specialized_lane"
    assert freeze.product_structure_rows(identity)[0]["active_fund_deferred"] is True


def test_commodity_pools_and_physical_metal_trusts_remain_eligible_when_valid() -> None:
    product = {row["symbol"]: row for row in read_csv("product_structure_verification.csv")}
    for symbol in ("DBC", "DBA", "DBE", "GLD", "SLV"):
        assert product[symbol]["allowed_product_structure"] == "True"


def test_forbidden_product_types_cannot_enter() -> None:
    identity = [
        {
            "symbol": "BAD",
            "current_official_name": "Bad ETN",
            "index_tracking_or_active_status": "index_or_passive_wrapper_not_flagged_active_by_official_name",
            "product_structure": "other_exchange_traded_structure",
            "leveraged_or_inverse_status": "not_flagged",
            "single_stock_status": "not_flagged",
            "options_income_covered_call_buffer_defined_outcome_status": "not_flagged",
            "crypto_or_digital_asset_status": "not_flagged",
            "etn_status": "flagged",
        }
    ]
    assert freeze.product_structure_rows(identity)[0]["v1_product_eligible"] is False
    assert read_json("consistency_check.json")["forbidden_product_types_can_enter"] is False


def test_bid_ask_spread_is_diagnostic_only() -> None:
    spreads = read_csv("bid_ask_spread_diagnostics.csv")
    assert all(row["spread_status"] == "spread_unavailable" for row in spreads)
    assert all(row["eligibility_effect"] == "diagnostic_only_no_pass_fail_threshold_in_v1" for row in spreads)


def test_duplicate_representatives_do_not_use_performance() -> None:
    duplicates = read_csv("duplicate_representative_review.csv")
    assert duplicates
    assert all(row["performance_used"] == "False" for row in duplicates)
    selections = {row["potential_duplicate_group"]: row["selected_representative"] for row in duplicates}
    assert selections["us_large_cap_sp500"] == "SPY"
    assert selections["physical_gold"] == "GLD"
    assert selections["broad_commodity_pool"] == "DBC"
    assert selections["us_low_volatility_factor"] == "USMV"
    notes = {row["potential_duplicate_group"]: row["notes"] for row in duplicates}
    assert notes["us_low_volatility_factor"] == "related_not_automatic_duplicate_primary_preserved"


def test_no_return_volatility_drawdown_correlation_or_backtest_is_calculated() -> None:
    check = read_json("consistency_check.json")
    assert check["returns_volatility_drawdown_correlation_or_backtest_calculated"] is False
    assert check["strategy_backtest_run"] is False
    forbidden = ("cagr", "sharpe", "drawdown", "correlation", "momentum", "trend")
    for csv_name in ("history_and_integrity_metrics.csv", "liquidity_metrics.csv", "eligibility_results.csv"):
        header = (OUTPUT_DIR / csv_name).read_text(encoding="utf-8").splitlines()[0].lower()
        assert not any(term in header for term in forbidden)


def test_exactly_48_instruments_are_required_for_passed_outcome() -> None:
    check = read_json("consistency_check.json")
    assert check["outcome"] == "pilot_etf_market_data_freeze_incomplete"
    assert check["final_primary_count"] == 47
    assert check["passed_outcome_requires_48"] is True


def test_incomplete_groups_produce_gap_report_not_invented_replacement() -> None:
    blocked = read_csv("excluded_and_blocked_candidates.csv")
    assert len(blocked) == 1
    assert blocked[0]["proposed_primary_symbol"] == "DBE"
    assert blocked[0]["blocked_reason"] == "latest60_median_dollar_volume_below_10000000"
    assert blocked[0]["off_list_replacement_added"] == "False"


def test_every_snapshot_is_hashed_and_immutable() -> None:
    snapshots = read_csv("immutable_snapshot_manifest.csv")
    assert len(snapshots) == 60
    for row in snapshots:
        path = ROOT / row["snapshot_path"]
        assert path.exists()
        assert row["snapshot_hash"] == sha256(path)
        assert len(row["snapshot_hash"]) == 64


def test_strategy_registry_and_active_observations_remain_byte_identical() -> None:
    before = {REGISTRY: sha256(REGISTRY), ACTIVE_OBSERVATIONS: sha256(ACTIVE_OBSERVATIONS)}
    result = freeze.run()
    after = {REGISTRY: sha256(REGISTRY), ACTIVE_OBSERVATIONS: sha256(ACTIVE_OBSERVATIONS)}
    assert result["outcome"] == "pilot_etf_market_data_freeze_incomplete"
    assert before == after


def test_quantpedia_is_not_accessed_and_no_pair_generation_occurs() -> None:
    check = read_json("consistency_check.json")
    assert check["quantpedia_accessed"] is False
    assert check["pair_generation"] is False


def test_output_is_deterministic_after_snapshots_are_frozen() -> None:
    files = sorted(path for path in OUTPUT_DIR.iterdir() if path.is_file())
    before = {path.name: sha256(path) for path in files}
    freeze.run()
    after = {path.name: sha256(path) for path in files}
    assert before == after
