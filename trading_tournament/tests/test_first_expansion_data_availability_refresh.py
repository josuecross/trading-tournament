from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import yaml

import run_first_expansion_data_availability_refresh as refresh
import run_first_expansion_discovery_preregistration as prereg


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / refresh.OUTPUT_DIR
PREREG_OUTPUT_DIR = ROOT / prereg.OUTPUT_DIR
MANIFEST_PATH = OUTPUT_DIR / "first_expansion_data_refresh_manifest.json"
CONSISTENCY_PATH = OUTPUT_DIR / "first_expansion_data_refresh_consistency_check.json"
COVERAGE_PATH = OUTPUT_DIR / "first_expansion_symbol_coverage.csv"
PREREG_BATCH_PATH = PREREG_OUTPUT_DIR / "first_expansion_discovery_batch.yaml"
PREREG_MANIFEST_PATH = PREREG_OUTPUT_DIR / "first_expansion_discovery_manifest.json"


def load_json(path: Path) -> dict[str, Any]:
    assert path.exists(), f"missing json artifact: {path}"
    return json.loads(path.read_text(encoding="utf-8"))


def load_manifest() -> dict[str, Any]:
    return load_json(MANIFEST_PATH)


def load_consistency() -> dict[str, Any]:
    return load_json(CONSISTENCY_PATH)


def load_batch() -> dict[str, Any]:
    assert PREREG_BATCH_PATH.exists(), f"missing prereg batch: {PREREG_BATCH_PATH}"
    return yaml.safe_load(PREREG_BATCH_PATH.read_text(encoding="utf-8"))


def load_coverage() -> list[dict[str, str]]:
    assert COVERAGE_PATH.exists(), f"missing coverage csv: {COVERAGE_PATH}"
    with COVERAGE_PATH.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def candidate_ids() -> list[str]:
    return [candidate["candidate_id"] for candidate in load_batch()["candidates"]]


def test_only_dia_and_xlre_are_authorized_for_refresh() -> None:
    manifest = load_manifest()
    assert manifest["authorized_symbols"] == refresh.AUTHORIZED_SYMBOLS
    assert manifest["requested_symbols"] == refresh.AUTHORIZED_SYMBOLS


def test_no_intraday_event_or_unrelated_data_refresh_is_allowed() -> None:
    manifest = load_manifest()
    assert manifest["daily_adjusted_ohlcv_only"] is True
    assert manifest["intraday_data_downloaded"] is False
    assert manifest["event_data_downloaded"] is False
    assert manifest["unrelated_symbols_downloaded"] is False
    assert set(manifest["downloaded_symbols"]) <= set(refresh.AUTHORIZED_SYMBOLS)


def test_manifest_confirms_data_refresh_only_mode() -> None:
    assert load_manifest()["data_refresh_only"] is True


def test_manifest_confirms_no_backtest_or_discovery() -> None:
    manifest = load_manifest()
    assert manifest["backtests_run"] is False
    assert manifest["discovery_run"] is False


def test_manifest_confirms_no_performance_metrics() -> None:
    assert load_manifest()["performance_metrics_computed"] is False


def test_manifest_confirms_no_candidate_exhaustive_or_paper_forward_action() -> None:
    manifest = load_manifest()
    assert manifest["candidate_exhaustive_run"] is False
    assert manifest["paper_forward_review"] is False
    assert manifest["paper_forward_activation"] is False


def test_manifest_confirms_no_broker_or_live_path() -> None:
    manifest = load_manifest()
    assert manifest["broker_path_touched"] is False
    assert manifest["live_orders"] is False


def test_frozen_candidate_rules_remain_unchanged() -> None:
    consistency = load_consistency()
    assert consistency["frozen_rules_changed"] is False
    assert consistency["candidate_universe_changed"] is False
    assert consistency["benchmarks_changed"] is False
    assert consistency["consistency_passed"] is True


def test_included_candidates_remain_exactly_the_same_five() -> None:
    assert candidate_ids() == prereg.AUTHORIZED_CANDIDATE_IDS


def test_excluded_candidates_remain_excluded() -> None:
    assert set(candidate_ids()).isdisjoint(prereg.EXCLUDED_CANDIDATE_IDS)


def test_data_availability_is_rechecked_after_refresh() -> None:
    prereg_manifest = load_json(PREREG_MANIFEST_PATH)
    refresh_manifest = load_manifest()
    assert refresh_manifest["pre_registration_data_availability_status"] == prereg_manifest["data_availability_status"]
    assert refresh_manifest["data_availability_status_after_refresh"] in {
        "sufficient_for_discovery",
        "still_missing_required_data",
        "unknown_requires_manual_review",
    }


def test_next_action_runs_discovery_only_if_all_required_data_is_sufficient() -> None:
    manifest = load_manifest()
    if manifest["data_availability_status_after_refresh"] == "sufficient_for_discovery":
        assert manifest["next_action"] == "run_first_expansion_discovery_batch"


def test_next_action_does_not_run_discovery_if_missing_or_unknown() -> None:
    manifest = load_manifest()
    if manifest["data_availability_status_after_refresh"] in {"still_missing_required_data", "unknown_requires_manual_review"}:
        assert manifest["next_action"] != "run_first_expansion_discovery_batch"


def test_no_symbols_were_removed_or_substituted() -> None:
    required = {"SPY", "QQQ", "IWM", "DIA", "XLK", "XLF", "XLV", "XLE", "XLI", "XLY", "XLP", "XLU", "XLB", "XLRE", "BIL"}
    coverage_symbols = {row["symbol"] for row in load_coverage()}
    assert required <= coverage_symbols
    assert {"DIA", "XLRE"} <= coverage_symbols


def test_dia_and_xlre_are_schema_valid_after_refresh_or_prior_cache() -> None:
    rows = {row["symbol"]: row for row in load_coverage()}
    for symbol in refresh.AUTHORIZED_SYMBOLS:
        assert rows[symbol]["qa_status"] == "passed"
        assert rows[symbol]["adjusted_close_available"] == "True"
        assert rows[symbol]["schema_matches_existing_daily_etf_data"] == "True"
