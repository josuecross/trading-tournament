from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = (
    ROOT
    / "evidence"
    / "research_recovery"
    / "public_source_percent_b_money_flow_state_reconciliation"
    / "latest"
)


def load_manifest() -> dict:
    return json.loads((EVIDENCE / "percent_b_state_reconciliation_manifest.json").read_text(encoding="utf-8"))


def load_consistency() -> dict:
    return json.loads(
        (EVIDENCE / "percent_b_state_reconciliation_consistency_check.json").read_text(encoding="utf-8")
    )


def read_rows(filename: str) -> list[dict[str, str]]:
    with (EVIDENCE / filename).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_reconciliation_records_completed_run_as_current_source_of_truth() -> None:
    manifest = load_manifest()
    consistency = load_consistency()

    assert manifest["percent_b_money_flow_state_reconciliation_only"] is True
    assert manifest["source_id"] == "percent_b_money_flow"
    assert manifest["lane_id"] == "public_source_percent_b_money_flow_bounded_bt_lane_v1"
    assert manifest["family_id"] == "price_band_money_flow_confirmation"
    assert manifest["design_evidence_exists"] is True
    assert manifest["run_evidence_exists"] is True
    assert manifest["chronology_decision"] == "design_packet_stale_relative_to_completed_run"
    assert manifest["run_logically_downstream_of_design"] is True
    assert manifest["design_run_variant_set_match"] is True
    assert manifest["current_percent_b_status"] == "completed_diagnostic_failed_pre_registered_criteria_no_rerun_authorized"
    assert consistency["consistency_passed"] is True


def test_run_result_and_failure_reason_are_preserved() -> None:
    manifest = load_manifest()

    assert manifest["variant_count_planned"] == 5
    assert manifest["variant_count_evaluated"] == 5
    assert manifest["data_blocked_row_count"] == 0
    assert manifest["primary_row_numeric_criteria_pass"] is False
    assert manifest["primary_failure_reason"] == "average_spy_exposure_above_pre_registered_sparse_signal_bound"
    assert manifest["primary_spy_exposure_bounds_pass"] is False
    assert manifest["primary_average_spy_exposure_share"] > manifest["pre_registered_spy_exposure_upper_bound"]
    assert round(manifest["primary_average_spy_exposure_share"], 4) == 0.6684
    assert round(manifest["primary_total_return"], 4) == 1.6373
    assert round(manifest["primary_max_drawdown"], 4) == -0.2618
    assert round(manifest["primary_drawdown_reduction_versus_spy_buy_hold"], 4) == 0.5257


def test_invariants_and_non_promotable_status_are_preserved() -> None:
    manifest = load_manifest()

    assert manifest["exposure_invariant_passed"] is True
    assert manifest["max_daily_exposure"] == 1.0
    assert manifest["max_daily_weight_sum"] == 1.0
    assert manifest["invariant_failure_count"] == 0
    assert manifest["run_consistency_passed"] is True
    assert manifest["results_interpretable"] is True
    assert manifest["usable_diagnostic_evidence"] is True
    assert manifest["outputs_diagnostic_only"] is True
    assert manifest["outputs_non_promotable"] is True
    assert manifest["candidate_exhaustive_ready"] is False
    assert manifest["paper_demo_eligible"] is False


def test_no_queue_mutation_and_move_on_next_action_recorded() -> None:
    manifest = load_manifest()
    rows = read_rows("status_file_scan.csv")
    queue_review = (EVIDENCE / "queue_status_review.md").read_text(encoding="utf-8")

    assert manifest["queue_status_file_updated"] is False
    assert manifest["queue_status_update_reason"] == "no_current_queue_pointer_to_percent_b_run_next_action_found"
    assert manifest["stale_status_pointer_count"] == 0
    assert rows == []
    assert manifest["current_authorized_next_action"] == "select_next_public_source_candidate_or_review_batch_candidates"
    assert manifest["next_action"] == "select_next_public_source_candidate_or_review_batch_candidates"
    assert "No stale Percent B run next-action pointer" in queue_review


def test_guardrails_prevent_rerun_or_execution_paths() -> None:
    manifest = load_manifest()
    guardrails = json.loads((EVIDENCE / "guardrail_checklist.json").read_text(encoding="utf-8"))

    expected_false = [
        "percent_b_lane_rerun",
        "backtest_run",
        "bounded_run_implementation_created",
        "design_regenerated",
        "robustness_report_created",
        "results_audit_created",
        "criteria_relaxed",
        "thresholds_tuned",
        "public_source_scraped",
        "additional_public_sources_ingested",
        "provider_download",
        "intraday_data_used",
        "new_packages_installed",
        "strategy_discovery_run",
        "candidate_exhaustive_run",
        "promotion_candidates_created",
        "paper_demo_observation_activated",
        "broker_api_called",
        "broker_orders_submitted",
        "broker_orders_cancelled",
        "broker_orders_reconciled",
        "live_orders",
        "real_money_recommendation",
        "public_source_or_high_return_treated_as_profitability_proof",
    ]
    for key in expected_false:
        assert manifest[key] is False
        assert guardrails[key] is False


def test_required_reconciliation_files_exist() -> None:
    required = [
        "percent_b_state_reconciliation_manifest.json",
        "percent_b_state_reconciliation_summary.md",
        "evidence_paths_inspected.md",
        "chronology_decision.md",
        "percent_b_current_status.md",
        "queue_status_review.md",
        "guardrail_checklist.json",
        "status_file_scan.csv",
        "percent_b_state_reconciliation_next_action.md",
        "percent_b_state_reconciliation_consistency_check.json",
    ]
    for filename in required:
        assert (EVIDENCE / filename).exists(), filename
