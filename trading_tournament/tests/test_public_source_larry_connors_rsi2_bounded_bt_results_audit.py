from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = (
    ROOT
    / "evidence"
    / "research_recovery"
    / "public_source_larry_connors_rsi2_bounded_bt_results_audit"
    / "latest"
)


def load_manifest() -> dict:
    return json.loads(
        (EVIDENCE / "public_source_larry_connors_rsi2_bounded_bt_results_audit_manifest.json").read_text(
            encoding="utf-8"
        )
    )


def load_consistency() -> dict:
    return json.loads(
        (EVIDENCE / "public_source_larry_connors_rsi2_bounded_bt_results_audit_consistency_check.json").read_text(
            encoding="utf-8"
        )
    )


def read_rows(filename: str) -> list[dict[str, str]]:
    with (EVIDENCE / filename).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_audit_manifest_passes_for_exact_larry_connors_lane() -> None:
    manifest = load_manifest()
    consistency = load_consistency()

    assert manifest["public_source_larry_connors_rsi2_results_audit_only"] is True
    assert manifest["source_id_audited"] == "larry_connors_rsi2_mean_reversion"
    assert manifest["family_id_audited"] == "short_term_equity_mean_reversion"
    assert manifest["lane_id_audited"] == "public_source_larry_connors_rsi2_bounded_bt_lane_v1"
    assert manifest["source_run_evidence_reviewed"] is True
    assert manifest["source_design_evidence_reviewed"] is True
    assert manifest["sample_adequacy_evidence_reviewed"] is True
    assert manifest["row_count_reviewed"] == 5
    assert manifest["expected_row_count"] == 5
    assert manifest["exact_approved_rows_reviewed"] is True
    assert manifest["final_audit_decision"] == "public_source_larry_connors_rsi2_results_audit_passed"
    assert consistency["consistency_passed"] is True


def test_formula_signal_shifted_weight_and_criteria_recompute_cleanly() -> None:
    manifest = load_manifest()
    discrepancies = read_rows("row_level_discrepancy_report.csv")
    criteria = read_rows("criteria_recomputation_report.csv")

    assert manifest["rsi_sma_formula_recomputed"] is True
    assert manifest["rsi_period_verified"] == 2
    assert manifest["rsi_threshold_verified"] == 5.0
    assert manifest["trend_sma_period_verified"] == 200
    assert manifest["exit_sma_period_verified"] == 5
    assert manifest["source_backed_parameters_only"] is True
    assert manifest["signal_logic_verified"] is True
    assert manifest["hidden_rule_detected"] is False
    assert manifest["shifted_weight_no_lookahead_verified"] is True
    assert manifest["target_weights_are_output_contract"] is True
    assert manifest["max_abs_shifted_return_delta"] <= 1e-12
    assert manifest["row_level_discrepancy_count"] == 0
    assert manifest["criteria_mismatch_count"] == 0
    assert discrepancies == []
    assert len(criteria) == 5
    primary = next(row for row in criteria if row["variant_role"] == "source_primary")
    assert primary["reported_numeric_criteria_pass"] == "True"
    assert primary["recomputed_numeric_criteria_pass"] == "True"


def test_timing_sanity_is_better_but_context_only() -> None:
    manifest = load_manifest()
    timing_report = (EVIDENCE / "timing_sanity_interpretation_report.md").read_text(encoding="utf-8")

    assert manifest["timing_sanity_total_return_higher_than_primary"] is True
    assert manifest["timing_sanity_max_drawdown_better_than_primary"] is True
    assert manifest["timing_sanity_return_drawdown_proxy_higher_than_primary"] is True
    assert manifest["timing_sanity_context_only"] is True
    assert manifest["timing_sanity_not_selected_as_best_strategy"] is True
    assert manifest["timing_delay_optimization_recommended"] is False
    assert "Execution-delay optimization recommended: `false`" in timing_report


def test_sample_adequacy_controls_and_exposure_are_documented() -> None:
    manifest = load_manifest()
    sample_note = (EVIDENCE / "sample_adequacy_note.md").read_text(encoding="utf-8")

    assert manifest["sample_adequacy_primary_classification"] == "adequate_diagnostic_sample"
    assert manifest["sample_adequacy_used_as_promotion_evidence"] is False
    assert "Primary trade/signal/event count" in sample_note
    assert manifest["control_row_count"] == 3
    assert manifest["control_rows_context_only"] is True
    assert manifest["exposure_invariant_passed"] is True
    assert manifest["invariant_failure_count"] == 0
    assert manifest["max_daily_exposure"] == 1.0
    assert manifest["max_daily_weight_sum"] == 1.0


def test_guardrails_forbidden_actions_and_next_action() -> None:
    manifest = load_manifest()

    assert manifest["guardrails_passed"] is True
    assert manifest["new_variants_created"] is False
    assert manifest["new_exits_or_filters_added"] is False
    assert manifest["rsi_sma_or_exit_parameters_tuned"] is False
    assert manifest["optimization_run"] is False
    assert manifest["robustness_run"] is False
    assert manifest["new_strategy_discovery_run"] is False
    assert manifest["new_research_batch_run"] is False
    assert manifest["percent_b_rerun"] is False
    assert manifest["turn_of_month_rerun"] is False
    assert manifest["faber_taa_retest"] is False
    assert manifest["provider_download"] is False
    assert manifest["intraday_data_used"] is False
    assert manifest["public_source_scraped"] is False
    assert manifest["public_strategy_list_ingested"] is False
    assert manifest["candidate_exhaustive_run"] is False
    assert manifest["promotion_candidates_created"] is False
    assert manifest["paper_forward_activation"] is False
    assert manifest["broker_api_called"] is False
    assert manifest["live_orders"] is False
    assert manifest["real_money_recommendation"] is False
    assert manifest["public_source_presence_is_profitability_proof"] is False
    assert manifest["outputs_remain_diagnostic_non_promotable"] is True
    assert manifest["next_action"] == "design_public_source_larry_connors_rsi2_robustness_check"


def test_required_audit_files_exist() -> None:
    consistency = load_consistency()
    required = consistency["required_files"]

    assert all(required.values())
    for filename in required:
        assert (EVIDENCE / filename).exists(), filename
