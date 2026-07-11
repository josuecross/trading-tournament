from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = (
    ROOT
    / "evidence"
    / "research_recovery"
    / "public_source_adx_dmi_final_state_reconciliation"
    / "latest"
)


def load_manifest() -> dict:
    return json.loads(
        (EVIDENCE / "public_source_adx_dmi_final_state_reconciliation_manifest.json").read_text(
            encoding="utf-8"
        )
    )


def load_consistency() -> dict:
    return json.loads(
        (EVIDENCE / "public_source_adx_dmi_final_state_reconciliation_consistency_check.json").read_text(
            encoding="utf-8"
        )
    )


def read_rows(filename: str) -> list[dict[str, str]]:
    with (EVIDENCE / filename).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_reconciliation_records_complete_adx_dmi_evidence_chain() -> None:
    manifest = load_manifest()
    consistency = load_consistency()
    chain = read_rows("evidence_chain_status.csv")

    assert manifest["public_source_adx_dmi_final_state_reconciliation_only"] is True
    assert manifest["source_id"] == "adx_dmi_trend_strength_crossover"
    assert manifest["family_id"] == "equity_index_adx_dmi_trend_strength"
    assert manifest["lane_id"] == "public_source_adx_dmi_bounded_bt_lane_v1"
    assert manifest["formula_contract_version"] == "adx_dmi_wilder_contract_v1"
    assert manifest["methodology_patch_id"] == "adx_dmi_true_crossover_event_patch_v1"
    assert manifest["intake_eligible"] is True
    assert manifest["batch_intake_decision"] == "eligible_for_bounded_bt_design"
    assert manifest["design_run_ready"] is True
    assert manifest["initial_results_audit_found_methodology_issue"] is True
    assert manifest["true_crossover_methodology_patch_completed"] is True
    assert manifest["corrected_run_completed"] is True
    assert manifest["corrected_event_counts_verified"] is True
    assert manifest["corrected_results_audit_mechanically_passed"] is True
    assert manifest["evidence_chain_complete"] is True
    assert {row["stage"] for row in chain} == {
        "intake_validation",
        "batch_intake_validation",
        "bounded_design",
        "initial_results_audit_methodology_issue",
        "true_crossover_methodology_patch",
        "corrected_bounded_run",
        "corrected_event_count_semantics",
        "corrected_results_audit",
        "final_closeout",
    }
    assert all(row["passed"] == "True" for row in chain)
    assert consistency["consistency_passed"] is True


def test_final_status_locks_control_weak_low_exposure_context_only_state() -> None:
    manifest = load_manifest()

    assert manifest["final_status_locked"] is True
    assert (
        manifest["final_adx_dmi_state"]
        == "completed_diagnostic_control_weak_low_exposure_context_only_no_continuation_authorized"
    )
    assert manifest["corrected_results_audit_decision"] == (
        "public_source_adx_dmi_corrected_results_passed_but_control_weak"
    )
    assert manifest["control_weakness_detected"] is True
    assert manifest["primary_behaves_like_low_exposure_defensive_timing"] is True
    assert manifest["primary_underperforms_spy_buy_hold_total_return"] is True
    assert manifest["primary_underperforms_spy200d_total_return"] is True
    assert round(float(manifest["primary_total_return"]), 4) == 0.7329
    assert round(float(manifest["spy_buy_hold_total_return"]), 4) == 5.9116
    assert round(float(manifest["spy200d_total_return"]), 4) == 4.0224
    assert round(float(manifest["primary_average_spy_exposure_share"]), 4) == 0.0959
    assert manifest["timing_sanity_context_only"] is True


def test_event_counts_and_patch_state_are_preserved() -> None:
    manifest = load_manifest()

    assert manifest["patch_evidence_consistency_passed"] is True
    assert manifest["formula_recomputation_passed"] is True
    assert manifest["corrected_event_semantics_passed"] is True
    assert manifest["saved_run_recomputation_passed"] is True
    assert manifest["criteria_recomputation_passed"] is True
    assert manifest["exposure_invariants_passed"] is True
    assert manifest["raw_bullish_directional_state_days"] == 2760
    assert manifest["raw_bearish_directional_state_days"] == 2035
    assert manifest["true_bullish_crossover_events"] == 212
    assert manifest["true_bearish_crossover_events"] == 213
    assert manifest["adx_confirmed_bullish_crossover_events"] == 31
    assert manifest["entries"] == 31
    assert manifest["exits"] == 31
    assert manifest["round_trips"] == 31


def test_outputs_are_not_actionable_and_no_continuation_is_authorized() -> None:
    manifest = load_manifest()

    assert manifest["not_promotable"] is True
    assert manifest["not_candidate_exhaustive_ready"] is True
    assert manifest["not_paper_demo_eligible"] is True
    assert manifest["not_broker_live_eligible"] is True
    assert manifest["not_real_money_relevant"] is True
    assert manifest["robustness_run_authorized"] is False
    assert manifest["results_reaudit_authorized"] is False
    assert manifest["rerun_authorized"] is False
    assert manifest["parameter_tuning_authorized"] is False
    assert manifest["alternate_adx_thresholds_authorized"] is False
    assert manifest["alternate_dmi_periods_authorized"] is False
    assert manifest["alternate_exits_authorized"] is False
    assert manifest["filters_authorized"] is False
    assert manifest["stop_loss_authorized"] is False
    assert manifest["profit_target_authorized"] is False
    assert manifest["spy200d_source_filter_authorized"] is False
    assert manifest["short_inverse_authorized"] is False
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
    assert manifest["roadmap_updated"] is False
    assert manifest["registry_updated"] is False
    assert manifest["state_files_changed"] is False
    assert manifest["queue_status_update_reason"] == "no_safe_automatic_queue_status_update_convention_used"
    assert manifest["stale_status_pointer_count"] == len(rows)
    assert manifest["next_action"] == "direction_owner_select_next_public_source_candidate"
    assert manifest["final_authorized_next_action"] == "direction_owner_select_next_public_source_candidate"
    assert "Final authorized next action" in queue_review


def test_guardrails_prevent_robustness_rerun_tuning_and_execution_paths() -> None:
    manifest = load_manifest()
    guardrails = json.loads((EVIDENCE / "guardrail_checklist.json").read_text(encoding="utf-8"))
    expected_false = [
        "adx_dmi_robustness_run",
        "adx_dmi_rerun",
        "adx_dmi_results_reaudit",
        "adx_dmi_period_tuned",
        "adx_threshold_tuned",
        "signal_timing_tuned",
        "exit_logic_tuned",
        "alternate_adx_thresholds_added",
        "alternate_dmi_periods_added",
        "alternate_exits_added",
        "filters_added",
        "stop_loss_or_profit_target_added",
        "spy200d_source_filter_added",
        "short_or_inverse_exposure_added",
        "new_variants_created",
        "next_public_source_selected_by_codex",
        "public_source_scraped",
        "additional_public_sources_ingested",
        "bollinger_continued",
        "macd_stochastic_continued",
        "cci_continued",
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
        "public_source_adx_dmi_final_state_reconciliation_manifest.json",
        "public_source_adx_dmi_final_state_reconciliation_summary.md",
        "evidence_paths_inspected.md",
        "evidence_chain_status.csv",
        "evidence_chain_status.md",
        "adx_dmi_final_current_status.md",
        "no_continuation_reasons.md",
        "not_authorized_actions.md",
        "queue_status_review.md",
        "guardrail_checklist.json",
        "status_file_scan.csv",
        "public_source_adx_dmi_final_state_reconciliation_next_action.md",
        "public_source_adx_dmi_final_state_reconciliation_consistency_check.json",
    ]
    for filename in required:
        assert (EVIDENCE / filename).exists(), filename
