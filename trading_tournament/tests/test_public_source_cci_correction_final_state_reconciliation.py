from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = (
    ROOT
    / "evidence"
    / "research_recovery"
    / "public_source_cci_correction_final_state_reconciliation"
    / "latest"
)


def load_manifest() -> dict:
    return json.loads(
        (EVIDENCE / "public_source_cci_correction_final_state_reconciliation_manifest.json").read_text(
            encoding="utf-8"
        )
    )


def load_consistency() -> dict:
    return json.loads(
        (EVIDENCE / "public_source_cci_correction_final_state_reconciliation_consistency_check.json").read_text(
            encoding="utf-8"
        )
    )


def read_rows(filename: str) -> list[dict[str, str]]:
    with (EVIDENCE / filename).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_reconciliation_records_complete_cci_evidence_chain() -> None:
    manifest = load_manifest()
    consistency = load_consistency()
    chain = read_rows("evidence_chain_status.csv")

    assert manifest["public_source_cci_correction_final_state_reconciliation_only"] is True
    assert manifest["source_id"] == "cci_correction"
    assert manifest["family_id"] == "equity_index_cci_pullback_trend_bias"
    assert manifest["lane_id"] == "public_source_cci_correction_bounded_bt_lane_v1"
    assert manifest["intake_eligible"] is True
    assert manifest["batch_intake_decision"] == "eligible_for_bounded_bt_design"
    assert manifest["design_run_ready"] is True
    assert manifest["bounded_run_completed"] is True
    assert manifest["bounded_run_exact_5_rows"] is True
    assert manifest["run_interpretable"] is True
    assert manifest["run_usable_diagnostic_evidence"] is True
    assert manifest["run_primary_base_criteria_pass"] is True
    assert manifest["results_audit_mechanics_passed"] is True
    assert {row["stage"] for row in chain} == {
        "intake",
        "batch_intake",
        "bounded_design",
        "bounded_run",
        "results_audit",
        "final_closeout",
    }
    assert all(row["passed"] == "True" for row in chain)
    assert consistency["consistency_passed"] is True


def test_final_status_locks_control_weak_context_only_decision() -> None:
    manifest = load_manifest()

    assert manifest["final_status_locked"] is True
    assert (
        manifest["final_cci_correction_status"]
        == "completed_diagnostic_control_weak_context_only_no_continuation_authorized"
    )
    assert manifest["results_audit_decision"] == "public_source_cci_correction_results_passed_but_control_weak"
    assert manifest["serious_interpretation_weakness"] is True
    assert manifest["primary_numeric_criteria_pass"] is True
    assert round(float(manifest["primary_total_return"]), 4) == 1.9032
    assert round(float(manifest["spy_buy_hold_total_return"]), 4) == 5.9116
    assert round(float(manifest["spy200d_total_return"]), 4) == 4.0224
    assert round(float(manifest["primary_max_drawdown"]), 4) == -0.2925
    assert round(float(manifest["spy200d_max_drawdown"]), 4) == -0.2646
    assert round(float(manifest["primary_return_drawdown_proxy"]), 4) == 0.1967
    assert round(float(manifest["spy200d_return_drawdown_proxy"]), 4) == 0.3340
    assert manifest["spy200d_dominates_primary_metric_count"] == 3
    assert manifest["timing_sanity_context_only"] is True
    assert manifest["long_only_adaptation_verified"] is True
    assert manifest["similarity_contexts_preserved"] is True
    assert manifest["specific_duplicate_or_do_not_retest_match_discovered"] is False


def test_outputs_are_not_actionable_and_no_continuation_is_authorized() -> None:
    manifest = load_manifest()

    assert manifest["not_promotable"] is True
    assert manifest["not_candidate_exhaustive_ready"] is True
    assert manifest["not_paper_demo_eligible"] is True
    assert manifest["not_broker_live_eligible"] is True
    assert manifest["not_real_money_relevant"] is True
    assert manifest["continuation_authorized"] is False
    assert manifest["robustness_run_authorized"] is False
    assert manifest["results_reaudit_authorized"] is False
    assert manifest["rerun_authorized"] is False
    assert manifest["parameter_tuning_authorized"] is False
    assert manifest["daily_weekly_variant_expansion_authorized"] is False
    assert manifest["alternate_exits_filters_stops_authorized"] is False
    assert manifest["short_inverse_exposure_authorized"] is False
    assert manifest["candidate_exhaustive_authorized"] is False
    assert manifest["promotion_authorized"] is False
    assert manifest["paper_demo_activation_authorized"] is False
    assert manifest["broker_live_action_authorized"] is False
    assert manifest["outputs_diagnostic_only"] is True
    assert manifest["outputs_non_promotable"] is True


def test_queue_status_review_and_next_action_are_recorded_without_mutation() -> None:
    manifest = load_manifest()
    rows = read_rows("status_file_scan.csv")
    queue_review = (EVIDENCE / "queue_status_review.md").read_text(encoding="utf-8")

    assert manifest["queue_status_file_updated"] is False
    assert manifest["queue_status_update_reason"] == "no_safe_automatic_queue_status_update_convention_used"
    assert manifest["stale_status_pointer_count"] == len(rows)
    assert manifest["next_action"] == "direction_owner_select_next_public_source_candidate"
    assert manifest["final_authorized_next_action"] == "direction_owner_select_next_public_source_candidate"
    assert "Final authorized next action" in queue_review


def test_guardrails_prevent_robustness_rerun_tuning_and_execution_paths() -> None:
    manifest = load_manifest()
    guardrails = json.loads((EVIDENCE / "guardrail_checklist.json").read_text(encoding="utf-8"))
    expected_false = [
        "cci_robustness_run",
        "cci_backtest_rerun",
        "cci_results_reaudit",
        "cci_periods_tuned",
        "cci_thresholds_tuned",
        "cci_timing_tuned",
        "cci_exit_logic_tuned",
        "daily_only_variants_added",
        "weekly_only_variants_added",
        "alternate_cci_periods_added",
        "alternate_thresholds_added",
        "alternate_exits_added",
        "filters_added",
        "stop_loss_or_profit_target_added",
        "short_or_inverse_exposure_added",
        "new_variants_created",
        "next_public_source_selected_by_codex",
        "public_source_scraped",
        "public_strategy_list_ingested",
        "coppock_continued",
        "larry_connors_continued",
        "percent_b_continued",
        "turn_of_month_continued",
        "faber_taa_continued",
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
        "public_source_cci_correction_final_state_reconciliation_manifest.json",
        "public_source_cci_correction_final_state_reconciliation_summary.md",
        "evidence_paths_inspected.md",
        "evidence_chain_status.csv",
        "evidence_chain_status.md",
        "cci_correction_current_status.md",
        "no_continuation_reasons.md",
        "queue_status_review.md",
        "guardrail_checklist.json",
        "status_file_scan.csv",
        "public_source_cci_correction_final_state_reconciliation_next_action.md",
        "public_source_cci_correction_final_state_reconciliation_consistency_check.json",
    ]
    for filename in required:
        assert (EVIDENCE / filename).exists(), filename
