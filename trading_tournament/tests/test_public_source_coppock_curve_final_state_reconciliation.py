from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = (
    ROOT
    / "evidence"
    / "research_recovery"
    / "public_source_coppock_curve_final_state_reconciliation"
    / "latest"
)


def load_manifest() -> dict:
    return json.loads(
        (EVIDENCE / "public_source_coppock_curve_final_state_reconciliation_manifest.json").read_text(
            encoding="utf-8"
        )
    )


def load_consistency() -> dict:
    return json.loads(
        (EVIDENCE / "public_source_coppock_curve_final_state_reconciliation_consistency_check.json").read_text(
            encoding="utf-8"
        )
    )


def read_rows(filename: str) -> list[dict[str, str]]:
    with (EVIDENCE / filename).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_reconciliation_records_completed_coppock_evidence_chain() -> None:
    manifest = load_manifest()
    consistency = load_consistency()
    chain = read_rows("evidence_chain_status.csv")

    assert manifest["public_source_coppock_curve_final_state_reconciliation_only"] is True
    assert manifest["source_id"] == "coppock_curve_monthly_equity_signal"
    assert manifest["family_id"] == "long_term_equity_index_momentum_zero_cross"
    assert manifest["lane_id"] == "public_source_coppock_curve_bounded_bt_lane_v1"
    assert manifest["intake_eligible"] is True
    assert manifest["batch_intake_decision"] == "eligible_for_bounded_bt_design"
    assert manifest["intake_consistency_verified"] is True
    assert manifest["candidate_specific_evidence_valid"] is True
    assert manifest["design_run_ready"] is True
    assert manifest["bounded_run_completed"] is True
    assert manifest["bounded_run_exact_5_rows"] is True
    assert manifest["run_results_interpretable"] is True
    assert manifest["run_usable_diagnostic_evidence"] is True
    assert {row["stage"] for row in chain} == {
        "intake",
        "batch_intake",
        "intake_consistency",
        "bounded_design",
        "bounded_run",
        "final_closeout",
    }
    assert all(row["passed"] == "True" for row in chain)
    assert consistency["consistency_passed"] is True


def test_final_status_locks_sparse_failed_context_only_decision() -> None:
    manifest = load_manifest()

    assert manifest["final_status_locked"] is True
    assert (
        manifest["final_coppock_curve_status"]
        == "completed_diagnostic_sparse_context_only_failed_criteria_no_continuation_authorized"
    )
    assert manifest["primary_label"] == "public_source_coppock_curve_sparse_context_only"
    assert manifest["primary_numeric_criteria_pass"] is False
    assert manifest["only_one_completed_round_trip"] is True
    assert manifest["primary_numeric_criteria_failed"] is True
    assert manifest["primary_label_sparse_context_only"] is True
    assert manifest["drawdown_reduction_effectively_zero"] is True
    assert manifest["return_drawdown_proxy_did_not_beat_spy"] is True
    assert manifest["spy_buy_hold_control_outperformed_primary"] is True
    assert manifest["average_spy_exposure_very_high"] is True
    assert manifest["completed_round_trip_event_count"] == 1
    assert manifest["positive_zero_cross_entry_count"] == 2
    assert manifest["negative_zero_cross_exit_count"] == 1
    assert manifest["monthly_observation_count"] == 206
    assert round(manifest["primary_total_return"], 4) == 6.5172
    assert round(manifest["spy_buy_hold_total_return"], 4) == 10.5356
    assert round(manifest["primary_average_spy_exposure"], 4) == 0.9081
    assert round(manifest["primary_duplicate_reference_correlation"], 4) == 0.9476


def test_outputs_are_not_actionable_and_no_continuation_is_authorized() -> None:
    manifest = load_manifest()

    assert manifest["not_promotable"] is True
    assert manifest["not_candidate_exhaustive_ready"] is True
    assert manifest["not_paper_demo_eligible"] is True
    assert manifest["not_broker_live_eligible"] is True
    assert manifest["not_real_money_relevant"] is True
    assert manifest["continuation_authorized"] is False
    assert manifest["results_audit_authorized"] is False
    assert manifest["robustness_run_authorized"] is False
    assert manifest["rerun_authorized"] is False
    assert manifest["parameter_tuning_authorized"] is False
    assert manifest["daily_weekly_variant_authorized"] is False
    assert manifest["alternate_roc_wma_authorized"] is False
    assert manifest["signal_line_filter_divergence_stop_profit_target_authorized"] is False
    assert manifest["candidate_exhaustive_authorized"] is False
    assert manifest["promotion_authorized"] is False
    assert manifest["paper_demo_activation_authorized"] is False
    assert manifest["broker_live_action_authorized"] is False
    assert manifest["exposure_invariant_passed"] is True
    assert manifest["max_daily_exposure"] == 1.0
    assert manifest["max_daily_weight_sum"] == 1.0


def test_queue_status_scan_and_next_action_are_recorded_without_mutation() -> None:
    manifest = load_manifest()
    rows = read_rows("status_file_scan.csv")
    queue_review = (EVIDENCE / "queue_status_review.md").read_text(encoding="utf-8")

    assert manifest["queue_status_file_updated"] is False
    assert manifest["queue_status_update_reason"] == "no_safe_automatic_queue_status_update_convention_used"
    assert manifest["stale_status_pointer_count"] == len(rows)
    assert manifest["next_action"] == "direction_owner_select_next_public_source_candidate"
    assert manifest["final_authorized_next_action"] == "direction_owner_select_next_public_source_candidate"
    assert "Final authorized next action" in queue_review


def test_guardrails_prevent_audit_rerun_robustness_tuning_and_execution_paths() -> None:
    manifest = load_manifest()
    guardrails = json.loads((EVIDENCE / "guardrail_checklist.json").read_text(encoding="utf-8"))

    expected_false = [
        "results_audit_run",
        "coppock_backtest_rerun",
        "coppock_robustness_run",
        "roc_periods_tuned",
        "wma_period_tuned",
        "threshold_tuned",
        "signal_timing_tuned",
        "exit_rule_tuned",
        "daily_coppock_variants_added",
        "weekly_coppock_variants_added",
        "alternate_roc_periods_added",
        "alternate_wma_periods_added",
        "signal_lines_added",
        "filters_added",
        "divergence_rules_added",
        "stop_losses_added",
        "profit_targets_added",
        "alternate_exits_added",
        "new_variants_created",
        "next_public_source_selected_by_codex",
        "public_source_scraped",
        "public_strategy_list_ingested",
        "larry_connors_continued",
        "percent_b_continued",
        "turn_of_month_continued",
        "faber_taa_designed_or_retested",
        "provider_download",
        "intraday_data_used",
        "new_packages_installed",
        "strategy_discovery_run",
        "candidate_exhaustive_run",
        "promotion_candidates_created",
        "best_single_variant_promoted",
        "paper_demo_observation_activated",
        "broker_api_called",
        "broker_orders_submitted",
        "broker_orders_cancelled",
        "broker_orders_reconciled",
        "live_orders",
        "real_money_recommendation",
    ]
    for key in expected_false:
        assert manifest[key] is False
        assert guardrails[key] is False


def test_required_closeout_files_exist() -> None:
    required = [
        "public_source_coppock_curve_final_state_reconciliation_manifest.json",
        "public_source_coppock_curve_final_state_reconciliation_summary.md",
        "evidence_paths_inspected.md",
        "evidence_chain_status.csv",
        "evidence_chain_status.md",
        "coppock_curve_current_status.md",
        "no_continuation_reasons.md",
        "queue_status_review.md",
        "guardrail_checklist.json",
        "status_file_scan.csv",
        "public_source_coppock_curve_final_state_reconciliation_next_action.md",
        "public_source_coppock_curve_final_state_reconciliation_consistency_check.json",
    ]
    for filename in required:
        assert (EVIDENCE / filename).exists(), filename
