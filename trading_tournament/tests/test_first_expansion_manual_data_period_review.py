from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import yaml

import run_first_expansion_manual_data_period_review as review
import run_first_expansion_discovery_preregistration as prereg


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / review.OUTPUT_DIR
MANIFEST_PATH = OUTPUT_DIR / "first_expansion_manual_period_review_manifest.json"
CONSISTENCY_PATH = OUTPUT_DIR / "first_expansion_manual_period_consistency_check.json"
COMPATIBILITY_PATH = OUTPUT_DIR / "first_expansion_candidate_period_compatibility.csv"
PREREG_BATCH_PATH = ROOT / prereg.OUTPUT_DIR / "first_expansion_discovery_batch.yaml"


def load_json(path: Path) -> dict[str, Any]:
    assert path.exists(), f"missing artifact: {path}"
    return json.loads(path.read_text(encoding="utf-8"))


def load_manifest() -> dict[str, Any]:
    return load_json(MANIFEST_PATH)


def load_consistency() -> dict[str, Any]:
    return load_json(CONSISTENCY_PATH)


def load_rows() -> list[dict[str, str]]:
    assert COMPATIBILITY_PATH.exists(), f"missing compatibility table: {COMPATIBILITY_PATH}"
    with COMPATIBILITY_PATH.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def load_batch() -> dict[str, Any]:
    assert PREREG_BATCH_PATH.exists(), f"missing prereg batch: {PREREG_BATCH_PATH}"
    return yaml.safe_load(PREREG_BATCH_PATH.read_text(encoding="utf-8"))


def row_by_id() -> dict[str, dict[str, str]]:
    return {row["candidate_id"]: row for row in load_rows()}


def test_manual_period_review_is_governance_only() -> None:
    assert load_manifest()["manual_period_review_only"] is True


def test_no_backtest_or_discovery_was_run() -> None:
    manifest = load_manifest()
    assert manifest["backtests_run"] is False
    assert manifest["discovery_run"] is False


def test_no_performance_metrics_were_computed() -> None:
    assert load_manifest()["performance_metrics_computed"] is False


def test_no_provider_download_occurred() -> None:
    assert load_manifest()["provider_download"] is False


def test_no_candidate_exhaustive_or_paper_forward_action() -> None:
    manifest = load_manifest()
    assert manifest["candidate_exhaustive_run"] is False
    assert manifest["paper_forward_review"] is False
    assert manifest["paper_forward_activation"] is False


def test_no_broker_or_live_path_was_touched() -> None:
    manifest = load_manifest()
    assert manifest["broker_path_touched"] is False
    assert manifest["live_orders"] is False


def test_frozen_rules_remain_unchanged() -> None:
    consistency = load_consistency()
    assert consistency["frozen_rules_changed"] is False
    assert consistency["consistency_passed"] is True


def test_candidate_universes_remain_unchanged() -> None:
    consistency = load_consistency()
    assert consistency["candidate_universe_changed"] is False
    candidate_ids = [candidate["candidate_id"] for candidate in load_batch()["candidates"]]
    assert candidate_ids == prereg.AUTHORIZED_CANDIDATE_IDS


def test_benchmarks_remain_unchanged() -> None:
    assert load_consistency()["benchmarks_changed"] is False


def test_xlre_period_blocker_is_detected() -> None:
    manifest = load_manifest()
    rows = row_by_id()
    assert manifest["xlre_period_blocker_detected"] is True
    assert rows["sector_rs_weekly_cash_filter_v1"]["blocked_by_xlre"] == "True"


def test_dia_is_not_incorrectly_marked_missing() -> None:
    assert load_manifest()["dia_cache_present"] is True
    assert load_consistency()["dia_not_marked_missing"] is True


def test_xlre_is_not_incorrectly_marked_missing() -> None:
    assert load_manifest()["xlre_cache_present"] is True
    assert load_consistency()["xlre_not_marked_missing"] is True


def test_issue_is_period_inception_limitation_not_missing_cache() -> None:
    manifest = load_manifest()
    assert manifest["issue_classification"] == "period_inception_limitation_not_missing_cache"
    assert load_consistency()["issue_is_period_not_missing_cache"] is True


def test_selected_resolution_is_allowed() -> None:
    manifest = load_manifest()
    assert manifest["selected_resolution"] in review.ALLOWED_RESOLUTIONS
    assert manifest["selected_resolution"] == review.SELECTED_RESOLUTION


def test_next_action_is_not_blind_data_refresh() -> None:
    manifest = load_manifest()
    assert manifest["next_action"] != "authorize_data_availability_or_cache_refresh_for_first_expansion_batch"
    assert load_consistency()["next_action_not_blind_refresh"] is True


def test_no_symbols_are_removed_or_substituted() -> None:
    rows = row_by_id()
    assert "XLRE" in rows["sector_rs_weekly_cash_filter_v1"]["required_symbols"].split(";")
    assert "DIA" in rows["dmr_liquid_etf_oversold_rebound_v1"]["required_symbols"].split(";")
    assert load_consistency()["no_symbols_removed_or_substituted"] is True


def test_if_all_five_proceed_mixed_inception_diagnostics_required() -> None:
    manifest = load_manifest()
    if manifest["selected_resolution"] not in {"run_first_expansion_discovery_batch_without_sector_rs", "pre_register_sector_rs_limited_history_batch"}:
        assert manifest["mixed_inception_diagnostics_required_for_future_discovery"] is True


def test_deferred_limited_history_candidates_require_separate_preregistration() -> None:
    manifest = load_manifest()
    assert manifest["deferred_limited_history_candidate_ids"] == ["sector_rs_weekly_cash_filter_v1"]
    assert manifest["separate_limited_history_next_action"] == "pre_register_sector_rs_limited_history_batch"
    assert load_consistency()["limited_history_preregistration_required_for_deferred_candidates"] is True


def test_expected_candidate_period_classification() -> None:
    rows = row_by_id()
    assert rows["vm_spy_qqq_daily_vol_target_v1"]["recommended_handling"] == "allow_in_first_batch"
    assert rows["rs_pair_rotation_spy_qqq_xlk_xlu_v1"]["recommended_handling"] == "allow_in_first_batch"
    assert rows["sector_rs_weekly_cash_filter_v1"]["recommended_handling"] == "defer_to_limited_history_preregistration"
    assert rows["dmr_liquid_etf_oversold_rebound_v1"]["recommended_handling"] == "allow_in_first_batch_with_mixed_inception_diagnostics"
    assert rows["vol_compression_breakout_etf_v1"]["recommended_handling"] == "allow_in_first_batch_with_mixed_inception_diagnostics"
