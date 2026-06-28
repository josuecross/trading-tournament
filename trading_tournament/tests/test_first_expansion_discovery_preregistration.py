from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

import run_first_expansion_discovery_preregistration as prereg


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / prereg.OUTPUT_DIR
BATCH_PATH = OUTPUT_DIR / "first_expansion_discovery_batch.yaml"
MANIFEST_PATH = OUTPUT_DIR / "first_expansion_discovery_manifest.json"
DATA_MANIFEST_PATH = OUTPUT_DIR / "first_expansion_data_availability_manifest.json"
CONSISTENCY_PATH = OUTPUT_DIR / "first_expansion_consistency_check.json"
DATA_REPORT_PATH = OUTPUT_DIR / "first_expansion_data_availability_report.md"
MISSING_REPORT_PATH = OUTPUT_DIR / "first_expansion_missing_data_report.md"
SPECS_PATH = OUTPUT_DIR / "first_expansion_candidate_specs.md"


def load_batch() -> dict[str, Any]:
    assert BATCH_PATH.exists(), f"missing batch packet: {BATCH_PATH}"
    return yaml.safe_load(BATCH_PATH.read_text(encoding="utf-8"))


def load_manifest() -> dict[str, Any]:
    assert MANIFEST_PATH.exists(), f"missing manifest: {MANIFEST_PATH}"
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def load_data_manifest() -> dict[str, Any]:
    assert DATA_MANIFEST_PATH.exists(), f"missing data manifest: {DATA_MANIFEST_PATH}"
    return json.loads(DATA_MANIFEST_PATH.read_text(encoding="utf-8"))


def candidates() -> list[dict[str, Any]]:
    return load_batch()["candidates"]


def candidate_ids() -> list[str]:
    return [candidate["candidate_id"] for candidate in candidates()]


def walk_scalars(value: Any) -> list[str]:
    if isinstance(value, dict):
        return [item for child in value.values() for item in walk_scalars(child)]
    if isinstance(value, list):
        return [item for child in value for item in walk_scalars(child)]
    return [str(value)]


def test_exactly_five_candidates_are_included() -> None:
    assert len(candidates()) == 5
    assert load_manifest()["candidates_included_count"] == 5


def test_included_candidate_ids_match_authorized_list() -> None:
    assert candidate_ids() == prereg.AUTHORIZED_CANDIDATE_IDS


def test_no_intraday_candidates_are_included() -> None:
    assert all(candidate["timeframe"] != "intraday" for candidate in candidates())
    assert load_manifest()["intraday_candidates_included"] is False


def test_no_event_data_candidates_are_included() -> None:
    ids = set(candidate_ids())
    assert "post_earnings_drift_large_cap_later_v1" not in ids
    assert load_manifest()["event_data_candidates_included"] is False


def test_excluded_candidates_are_absent() -> None:
    assert set(candidate_ids()).isdisjoint(prereg.EXCLUDED_CANDIDATE_IDS)


def test_no_forbidden_status_values_appear() -> None:
    scalars = {item.lower() for item in walk_scalars(load_batch())}
    assert scalars.isdisjoint(prereg.FORBIDDEN_STATUS_VALUES)


def test_manifest_confirms_pre_registration_only() -> None:
    manifest = load_manifest()
    assert manifest["pre_registration_only"] is True


def test_manifest_confirms_data_availability_audit_only() -> None:
    manifest = load_manifest()
    assert manifest["data_availability_audit_only"] is True


def test_manifest_confirms_no_backtest_or_discovery() -> None:
    manifest = load_manifest()
    assert manifest["backtests_run"] is False
    assert manifest["discovery_run"] is False


def test_manifest_confirms_no_performance_metrics_computed() -> None:
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


def test_manifest_confirms_no_provider_download() -> None:
    manifest = load_manifest()
    assert manifest["provider_download"] is False
    assert manifest["provider_api_called"] is False


def test_etf_wrapper_track_is_not_reopened() -> None:
    assert load_manifest()["etf_wrapper_track_reopened"] is False


def test_active_strategy_state_is_not_changed() -> None:
    manifest = load_manifest()
    consistency = json.loads(CONSISTENCY_PATH.read_text(encoding="utf-8"))
    assert manifest["active_strategy_state_changed"] is False
    assert consistency["active_strategy_state_changed"] is False
    assert consistency["consistency_passed"] is True


def test_each_candidate_has_fixed_rules_and_gates() -> None:
    required = [
        "entry_rule",
        "exit_rule",
        "sizing_rule",
        "benchmark_controls",
        "risk_controls",
        "acceptance_criteria",
        "rejection_criteria",
    ]
    for candidate in candidates():
        for field in required:
            assert candidate[field], f"{candidate['candidate_id']} missing {field}"


def test_candidate_specs_do_not_contain_vague_optimization_phrases() -> None:
    text = (SPECS_PATH.read_text(encoding="utf-8") + "\n" + BATCH_PATH.read_text(encoding="utf-8")).lower()
    hits = [phrase for phrase in prereg.VAGUE_OPTIMIZATION_PHRASES if phrase in text]
    assert hits == []


def test_each_candidate_has_duplication_check_against_active_references() -> None:
    active_terms = ["active vm", "active dsr", "active combo", "spy_200d"]
    for candidate in candidates():
        text = " ".join(candidate["duplication_checks"] + candidate["benchmark_controls"]).lower()
        assert any(term in text for term in active_terms), candidate["candidate_id"]


def test_future_discovery_outcomes_are_limited() -> None:
    manifest = load_manifest()
    batch = load_batch()
    assert manifest["future_discovery_outcomes_allowed"] == prereg.ALLOWED_FUTURE_DISCOVERY_OUTCOMES
    assert batch["metadata"]["future_discovery_outcomes_allowed"] == prereg.ALLOWED_FUTURE_DISCOVERY_OUTCOMES


def test_data_availability_report_exists() -> None:
    assert DATA_REPORT_PATH.exists()
    assert "Data availability status" in DATA_REPORT_PATH.read_text(encoding="utf-8")


def test_missing_data_report_exists() -> None:
    assert MISSING_REPORT_PATH.exists()
    assert "Missing Data Report" in MISSING_REPORT_PATH.read_text(encoding="utf-8")


def test_missing_or_unknown_data_blocks_discovery_next_action() -> None:
    manifest = load_manifest()
    if manifest["data_availability_status"] in {"missing_required_data", "unknown_requires_manual_review"}:
        assert manifest["next_action"] == "authorize_data_availability_or_cache_refresh_for_first_expansion_batch"


def test_sufficient_data_allows_discovery_next_action() -> None:
    manifest = load_manifest()
    if manifest["data_availability_status"] == "sufficient_for_discovery":
        assert manifest["next_action"] == "run_first_expansion_discovery_batch"


def test_data_manifest_matches_manifest_next_action() -> None:
    manifest = load_manifest()
    data_manifest = load_data_manifest()
    assert data_manifest["data_availability_status"] == manifest["data_availability_status"]
    assert data_manifest["next_action"] == manifest["next_action"]
