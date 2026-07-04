from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from strategy_lab.research_os.research.public_source_turn_of_month_bounded_bt_results_audit import (
    AUDIT_DECISION_PASSED,
    LANE_ID,
    OUTPUT_DIR,
    VALID_NEXT_ACTIONS,
)


ROOT = Path(__file__).resolve().parents[1]


def output_dir() -> Path:
    return ROOT / OUTPUT_DIR


def load_manifest() -> dict:
    return json.loads(
        (output_dir() / "public_source_turn_of_month_bounded_bt_results_audit_manifest.json").read_text(
            encoding="utf-8"
        )
    )


def load_consistency() -> dict:
    return json.loads(
        (
            output_dir()
            / "public_source_turn_of_month_bounded_bt_results_audit_consistency_check.json"
        ).read_text(encoding="utf-8")
    )


def test_audit_manifest_guardrails_and_decision() -> None:
    manifest = load_manifest()
    consistency = load_consistency()

    assert manifest["public_source_turn_of_month_results_audit_only"] is True
    assert manifest["source_id_audited"] == "turn_of_month_equity_indexes"
    assert manifest["family_id_audited"] == "calendar_effect_turn_of_month_equity_index"
    assert manifest["lane_id_audited"] == LANE_ID
    assert manifest["source_run_evidence_reviewed"] is True
    assert manifest["source_design_evidence_reviewed"] is True
    assert manifest["local_cache_reconstructed_for_audit"] is True
    assert manifest["approved_rows_recomputed_for_audit_only"] is True
    assert manifest["row_count_reviewed"] == 5
    assert manifest["exact_approved_rows_reviewed"] is True
    assert manifest["final_audit_decision"] == AUDIT_DECISION_PASSED
    assert manifest["next_action"] in VALID_NEXT_ACTIONS
    assert consistency["consistency_passed"] is True


def test_audit_no_discrepancies_or_criteria_mismatches() -> None:
    manifest = load_manifest()
    discrepancies = pd.read_csv(output_dir() / "row_level_discrepancy_report.csv")
    criteria = pd.read_csv(output_dir() / "criteria_recomputation_report.csv")

    assert manifest["row_level_discrepancy_count"] == 0
    assert manifest["criteria_mismatch_count"] == 0
    assert discrepancies.empty
    assert len(criteria) == 5
    assert criteria["reported_numeric_criteria_pass"].eq(criteria["recomputed_numeric_criteria_pass"]).all()
    assert criteria["reported_research_label"].eq(criteria["recomputed_research_label"]).all()


def test_calendar_timing_and_no_lookahead_verified() -> None:
    manifest = load_manifest()
    timing_report = (output_dir() / "calendar_timing_audit_report.md").read_text(encoding="utf-8")
    no_lookahead_report = (output_dir() / "shifted_weight_no_lookahead_audit_report.md").read_text(
        encoding="utf-8"
    )

    assert manifest["calendar_timing_recomputed"] is True
    assert manifest["shifted_weight_no_lookahead_verified"] is True
    assert manifest["max_abs_shifted_return_delta"] <= 1e-12
    assert manifest["spy_exposure_through_third_trading_day_close_verified"] is True
    assert manifest["bil_exposure_after_exit_verified"] is True
    assert "one common trading day before month-end" in timing_report
    assert "third common trading day" in timing_report
    assert "shifted one bar" in no_lookahead_report


def test_timing_sanity_is_context_only_not_optimized() -> None:
    manifest = load_manifest()
    report = (output_dir() / "timing_sanity_interpretation_report.md").read_text(encoding="utf-8")

    assert manifest["timing_sanity_total_return_higher_than_primary"] is True
    assert manifest["timing_sanity_max_drawdown_worse_than_primary"] is True
    assert manifest["timing_sanity_return_drawdown_proxy_worse_than_primary"] is True
    assert manifest["timing_sanity_context_only"] is True
    assert manifest["timing_sanity_not_selected_as_best_strategy"] is True
    assert manifest["calendar_optimization_recommended"] is False
    assert "Timing-sanity selected as best strategy: `false`" in report


def test_controls_exposure_and_guardrails() -> None:
    manifest = load_manifest()

    assert manifest["control_row_count"] == 3
    assert manifest["control_rows_context_only"] is True
    assert manifest["exposure_invariant_passed"] is True
    assert manifest["invariant_failure_count"] == 0
    assert manifest["max_daily_exposure"] <= 1.000001
    assert manifest["max_daily_weight_sum"] <= 1.000001
    assert manifest["guardrails_passed"] is True
    assert manifest["provider_download"] is False
    assert manifest["intraday_data_used"] is False
    assert manifest["public_source_scraped"] is False
    assert manifest["public_strategy_list_ingested"] is False
    assert manifest["faber_taa_designed_or_retested"] is False
    assert manifest["candidate_exhaustive_run"] is False
    assert manifest["promotion_candidates_created"] is False
    assert manifest["best_single_variant_promoted"] is False
    assert manifest["paper_forward_activation"] is False
    assert manifest["new_paper_forward_candidate_created"] is False
    assert manifest["broker_api_called"] is False
    assert manifest["broker_orders_submitted"] is False
    assert manifest["broker_orders_cancelled"] is False
    assert manifest["broker_orders_reconciled"] is False
    assert manifest["live_orders"] is False
    assert manifest["real_money_recommendation"] is False
    assert manifest["outputs_remain_diagnostic_non_promotable"] is True


def test_required_audit_files_exist() -> None:
    consistency = load_consistency()
    required = consistency["required_files"]

    assert all(required.values())
    for filename in required:
        assert (output_dir() / filename).exists(), filename
