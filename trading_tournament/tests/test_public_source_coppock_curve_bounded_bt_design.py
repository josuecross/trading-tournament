from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "research_recovery" / "public_source_coppock_curve_bounded_bt_design" / "latest"


def load_manifest() -> dict:
    return json.loads(
        (EVIDENCE / "public_source_coppock_curve_bounded_bt_design_manifest.json").read_text(encoding="utf-8")
    )


def load_consistency() -> dict:
    return json.loads(
        (EVIDENCE / "public_source_coppock_curve_bounded_bt_design_consistency_check.json").read_text(
            encoding="utf-8"
        )
    )


def read_rows(filename: str) -> list[dict[str, str]]:
    with (EVIDENCE / filename).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_manifest_design_only_run_ready_and_source_backed() -> None:
    manifest = load_manifest()
    consistency = load_consistency()

    assert manifest["public_source_coppock_curve_bounded_bt_design_only"] is True
    assert manifest["source_id"] == "coppock_curve_monthly_equity_signal"
    assert manifest["source_intake_eligibility_decision"] == "eligible_for_bounded_bt_design"
    assert manifest["batch_intake_eligibility_decision"] == "eligible_for_bounded_bt_design"
    assert manifest["lane_id"] == "public_source_coppock_curve_bounded_bt_lane_v1"
    assert manifest["family_id"] == "long_term_equity_index_momentum_zero_cross"
    assert manifest["candidate_specific_evidence_valid"] is True
    assert manifest["coppock_yaml_valid"] is True
    assert manifest["verification_decision"] == "coppock_intake_evidence_consistent_ready_for_design"
    assert manifest["generic_bridge_blank_intake_not_used_as_eligibility_source"] is True
    assert manifest["source_backed_parameters"] is True
    assert manifest["parameter_status"] == "source_backed_parameters"
    assert manifest["roc_periods"] == [14, 11]
    assert manifest["wma_smoothing_period"] == 10
    assert manifest["signal_threshold"] == 0
    assert manifest["signal_frequency"] == "completed_monthly_close_only"
    assert manifest["parameters_tuned"] is False
    assert manifest["run_readiness_decision"] == "public_source_coppock_curve_bounded_bt_design_run_ready"
    assert manifest["run_readiness_blocker"] == "none"
    assert manifest["next_action"] == "run_public_source_coppock_curve_bounded_bt_lane"
    assert consistency["consistency_passed"] is True


def test_planned_rows_are_bounded_contextual_and_non_promotable() -> None:
    manifest = load_manifest()
    rows = read_rows("planned_row_table.csv")

    assert manifest["planned_row_count"] == 5
    assert manifest["planned_row_count_target_4_to_5"] is True
    assert manifest["planned_row_count_lte_5"] is True
    assert manifest["primary_source_row_count"] == 1
    assert manifest["timing_sanity_row_count"] == 1
    assert manifest["control_row_count"] == 3
    assert {row["variant_id"] for row in rows} == {
        "coppock_spy_bil_monthly_zero_cross_primary_v1",
        "coppock_spy_bil_one_month_delayed_timing_sanity_v1",
        "coppock_spy_buy_hold_control_v1",
        "coppock_bil_cash_control_v1",
        "coppock_spy200d_frozen_control_v1",
    }
    assert all(row["promotion_eligibility"] == "False" for row in rows)
    assert all(row["paper_forward_eligibility"] == "False" for row in rows)
    assert all(row["candidate_exhaustive_eligibility"] == "False" for row in rows)
    primary = next(row for row in rows if row["variant_role"] == "source_primary")
    assert "ROC14 + ROC11" in primary["formula"]
    assert primary["roc_periods"] == "14|11"
    assert primary["wma_smoothing_period"] == "10"
    assert primary["threshold"] == "0"
    assert "completed_month_end_close_signal" in primary["signal_timing"]
    assert "roc_period_1=14" in primary["source_backed_parameters"]
    assert "wma_smoothing_period=10" in primary["source_backed_parameters"]


def test_similarity_caveat_and_sparse_signal_risks_are_recorded() -> None:
    manifest = load_manifest()
    similarity = (EVIDENCE / "similarity_risk_report.md").read_text(encoding="utf-8")
    caveat = (EVIDENCE / "source_caveat_sell_exit_rule.md").read_text(encoding="utf-8")
    sparse = (EVIDENCE / "sparse_signal_risk_report.md").read_text(encoding="utf-8")
    criteria = (EVIDENCE / "numeric_success_failure_criteria.md").read_text(encoding="utf-8")

    assert manifest["similarity_contexts_preserved"] == [
        "spy200d_trend_control",
        "global_multi_asset",
        "macro_gld_duration_risk_off",
        "high_return_tactical_equity",
        "volatility_throttle_volatility_managed_equity",
        "turn_of_month_calendar_effect",
        "mean_reversion_rejected_or_existing_candidate",
        "price_band_money_flow_confirmation",
    ]
    assert manifest["similarity_not_current_duplicate_blocker"] is True
    assert manifest["source_caveat_report_created"] is True
    assert manifest["sell_exit_caveat_preserved"] is True
    assert manifest["sparse_signal_risk_recorded"] is True
    assert manifest["future_run_must_report_event_count"] is True
    assert manifest["future_run_must_report_sample_adequacy"] is True
    assert "spy200d_trend_control" in similarity
    assert "negative zero-cross exit" in caveat
    assert "event count" in sparse
    assert "Average SPY exposure share is `>= 0.0500` and `<= 0.9500`" in criteria
    assert "Duplicate/reference correlation" in criteria


def test_cache_bt_adapter_and_timing_requirements_are_documented() -> None:
    manifest = load_manifest()
    cache_rows = read_rows("local_cache_availability.csv")
    timing = (EVIDENCE / "signal_timing_convention.md").read_text(encoding="utf-8")
    formula = (EVIDENCE / "formula_monthly_signal_definition.md").read_text(encoding="utf-8")

    assert manifest["uses_only_spy_and_bil"] is True
    assert manifest["spy_cache_ready"] is True
    assert manifest["bil_cache_ready"] is True
    assert manifest["local_cache_complete"] is True
    assert {row["symbol"]: row["cache_status"] for row in cache_rows} == {"SPY": "cache_ready", "BIL": "cache_ready"}
    assert manifest["bt_adapter_control_poc_passed"] is True
    assert manifest["bt_adapter_multasset_poc_passed"] is True
    assert manifest["bt_adapter_ready_for_design"] is True
    assert manifest["formula_monthly_signal_definition_documented"] is True
    assert manifest["signal_timing_convention_documented"] is True
    assert manifest["no_lookahead_timing_documented"] is True
    assert "completed monthly closes" in formula
    assert "ROC(14), ROC(11), and WMA(10)" in timing
    assert "shifted-weight convention" in timing


def test_guardrails_no_run_backtest_expansion_or_execution_paths() -> None:
    manifest = load_manifest()

    assert manifest["bounded_bt_design_packet_created"] is True
    assert manifest["executable_bounded_bt_design_created"] is True
    assert manifest["bounded_run_implementation_created"] is False
    assert manifest["bounded_bt_lane_run"] is False
    assert manifest["strategy_backtest_run"] is False
    assert manifest["strategy_implemented"] is False
    assert manifest["public_source_scraped"] is False
    assert manifest["public_strategy_list_ingested"] is False
    assert manifest["additional_public_sources_ingested"] is False
    assert manifest["larry_connors_continued"] is False
    assert manifest["percent_b_continued"] is False
    assert manifest["turn_of_month_continued"] is False
    assert manifest["faber_taa_retested"] is False
    assert manifest["daily_coppock_variants_added"] is False
    assert manifest["weekly_coppock_variants_added"] is False
    assert manifest["alternate_roc_periods_added"] is False
    assert manifest["alternate_smoothing_periods_added"] is False
    assert manifest["signal_lines_added"] is False
    assert manifest["moving_average_filters_added"] is False
    assert manifest["volatility_filters_added"] is False
    assert manifest["stop_loss_or_profit_target_added"] is False
    assert manifest["divergence_rules_added"] is False
    assert manifest["additional_exits_added"] is False
    assert manifest["parameter_sweep_created"] is False
    assert manifest["optimization_run"] is False
    assert manifest["provider_download"] is False
    assert manifest["intraday_data_used"] is False
    assert manifest["new_packages_installed"] is False
    assert manifest["current_backtester_replaced"] is False
    assert manifest["strategy_discovery_run"] is False
    assert manifest["candidate_exhaustive_run"] is False
    assert manifest["promotion_candidates_created"] is False
    assert manifest["paper_forward_activation"] is False
    assert manifest["broker_api_called"] is False
    assert manifest["live_orders"] is False
    assert manifest["real_money_recommendation"] is False
    assert manifest["public_source_presence_is_profitability_proof"] is False
    assert manifest["outputs_non_promotable"] is True


def test_required_design_evidence_files_exist() -> None:
    required = [
        "public_source_coppock_curve_bounded_bt_design_summary.md",
        "source_intake_review.md",
        "local_cache_availability.csv",
        "local_cache_availability.md",
        "source_backed_parameter_report.csv",
        "source_backed_parameter_report.md",
        "formula_monthly_signal_definition.md",
        "source_caveat_sell_exit_rule.md",
        "similarity_risk_report.md",
        "sparse_signal_risk_report.md",
        "planned_row_table.csv",
        "planned_row_table.md",
        "signal_timing_convention.md",
        "baseline_control_policy.md",
        "numeric_success_failure_criteria.md",
        "bt_adapter_readiness.md",
        "guardrail_checklist.json",
        "exposure_invariant_requirements.md",
        "run_readiness_decision.md",
        "public_source_coppock_curve_bounded_bt_design_next_action.md",
    ]
    for filename in required:
        assert (EVIDENCE / filename).exists(), filename
