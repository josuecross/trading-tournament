from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = (
    ROOT
    / "evidence"
    / "research_recovery"
    / "public_source_larry_connors_rsi2_final_state_reconciliation"
    / "latest"
)


def load_manifest() -> dict:
    return json.loads(
        (EVIDENCE / "larry_connors_rsi2_final_state_reconciliation_manifest.json").read_text(encoding="utf-8")
    )


def load_consistency() -> dict:
    return json.loads(
        (EVIDENCE / "larry_connors_rsi2_final_state_reconciliation_consistency_check.json").read_text(
            encoding="utf-8"
        )
    )


def read_rows(filename: str) -> list[dict[str, str]]:
    with (EVIDENCE / filename).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_reconciliation_records_completed_evidence_chain() -> None:
    manifest = load_manifest()
    consistency = load_consistency()
    chain = read_rows("evidence_chain_status.csv")

    assert manifest["larry_connors_rsi2_final_state_reconciliation_only"] is True
    assert manifest["source_id"] == "larry_connors_rsi2_mean_reversion"
    assert manifest["family_id"] == "short_term_equity_mean_reversion"
    assert manifest["lane_id"] == "public_source_larry_connors_rsi2_bounded_bt_lane_v1"
    assert manifest["intake_eligible"] is True
    assert manifest["batch_intake_decision"] == "eligible_for_bounded_bt_design"
    assert manifest["design_run_ready"] is True
    assert manifest["bounded_run_completed"] is True
    assert manifest["bounded_run_exact_5_rows"] is True
    assert manifest["run_primary_base_criteria_pass"] is True
    assert manifest["results_audit_passed"] is True
    assert manifest["robustness_completed"] is True
    assert manifest["robustness_evidence_usable"] is True
    assert {row["stage"] for row in chain} == {
        "intake",
        "batch_intake",
        "bounded_design",
        "bounded_run",
        "results_audit",
        "sample_adequacy",
        "robustness",
    }
    assert all(row["passed"] == "True" for row in chain)
    assert consistency["consistency_passed"] is True


def test_final_status_locks_cost_sensitive_rolling_weak_context_only_decision() -> None:
    manifest = load_manifest()

    assert manifest["final_status_locked"] is True
    assert (
        manifest["final_larry_connors_rsi2_status"]
        == "completed_diagnostic_context_only_cost_sensitive_rolling_weak_no_continuation_authorized"
    )
    assert manifest["primary_robustness_label"] == "connors_rsi2_robustness_cost_sensitive"
    assert manifest["primary_base_pass"] is True
    assert manifest["primary_10bps_stress_pass"] is False
    assert manifest["primary_25bps_stress_pass"] is False
    assert manifest["primary_subperiod_failure_count"] == 0
    assert manifest["primary_rolling_window_weakness"] is True
    assert manifest["primary_event_trade_count"] == 368
    assert round(manifest["primary_average_holding_days"], 2) == 2.99
    assert manifest["primary_median_holding_days"] == 2.0
    assert round(manifest["primary_worst_event_return"], 4) == -0.12
    assert manifest["primary_event_unstable"] is False
    assert manifest["sample_adequacy_primary_classification"] == "adequate_diagnostic_sample"
    assert float(manifest["sample_adequacy_calendar_years"]) >= 19.0
    assert int(manifest["sample_adequacy_trading_days"]) >= 4700
    assert int(manifest["sample_adequacy_event_count"]) >= 700


def test_outputs_are_not_actionable_and_no_continuation_is_authorized() -> None:
    manifest = load_manifest()

    assert manifest["not_promotable"] is True
    assert manifest["not_candidate_exhaustive_ready"] is True
    assert manifest["not_paper_demo_eligible"] is True
    assert manifest["not_broker_live_eligible"] is True
    assert manifest["not_real_money_relevant"] is True
    assert manifest["continuation_authorized"] is False
    assert manifest["robustness_audit_authorized"] is False
    assert manifest["parameter_tuning_authorized"] is False
    assert manifest["timing_delay_optimization_authorized"] is False
    assert manifest["threshold_sweeps_authorized"] is False
    assert manifest["new_variants_authorized"] is False
    assert manifest["new_exits_stops_filters_authorized"] is False
    assert manifest["rerun_authorized"] is False
    assert manifest["candidate_exhaustive_authorized"] is False
    assert manifest["promotion_authorized"] is False
    assert manifest["paper_demo_activation_authorized"] is False
    assert manifest["broker_live_action_authorized"] is False
    assert manifest["timing_sanity_context_only"] is True
    assert manifest["timing_delay_optimization_recommended"] is False
    assert manifest["controls_control_only"] is True
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


def test_guardrails_prevent_rerun_audit_tuning_and_execution_paths() -> None:
    manifest = load_manifest()
    guardrails = json.loads((EVIDENCE / "guardrail_checklist.json").read_text(encoding="utf-8"))

    expected_false = [
        "robustness_audit_run",
        "larry_connors_backtest_rerun",
        "larry_connors_robustness_rerun",
        "rsi_period_tuned",
        "rsi_threshold_tuned",
        "sma_periods_tuned",
        "timing_delay_optimized",
        "threshold_sweep_created",
        "new_variants_created",
        "new_exits_stops_filters_added",
        "new_indicators_added",
        "next_public_source_selected_by_codex",
        "public_source_scraped",
        "public_strategy_list_ingested",
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
        "larry_connors_rsi2_final_state_reconciliation_manifest.json",
        "larry_connors_rsi2_final_state_reconciliation_summary.md",
        "evidence_paths_inspected.md",
        "evidence_chain_status.csv",
        "evidence_chain_status.md",
        "larry_connors_rsi2_current_status.md",
        "queue_status_review.md",
        "guardrail_checklist.json",
        "status_file_scan.csv",
        "larry_connors_rsi2_final_state_reconciliation_next_action.md",
        "larry_connors_rsi2_final_state_reconciliation_consistency_check.json",
    ]
    for filename in required:
        assert (EVIDENCE / filename).exists(), filename
