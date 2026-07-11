from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "research_recovery" / "public_source_adx_dmi_bounded_bt_design" / "latest"


def load_manifest() -> dict:
    return json.loads((EVIDENCE / "public_source_adx_dmi_bounded_bt_design_manifest.json").read_text(encoding="utf-8"))


def load_consistency() -> dict:
    return json.loads(
        (EVIDENCE / "public_source_adx_dmi_bounded_bt_design_consistency_check.json").read_text(encoding="utf-8")
    )


def read_rows(filename: str) -> list[dict[str, str]]:
    with (EVIDENCE / filename).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_manifest_design_only_run_ready_and_correct_source() -> None:
    manifest = load_manifest()
    consistency = load_consistency()

    assert manifest["public_source_adx_dmi_bounded_bt_design_only"] is True
    assert manifest["source_id"] == "adx_dmi_trend_strength_crossover"
    assert manifest["source_intake_eligibility_decision"] == "eligible_for_bounded_bt_design"
    assert manifest["batch_intake_eligibility_decision"] == "eligible_for_bounded_bt_design"
    assert manifest["lane_id"] == "public_source_adx_dmi_bounded_bt_lane_v1"
    assert manifest["family_id"] == "equity_index_adx_dmi_trend_strength"
    assert manifest["run_readiness_decision"] == "public_source_adx_dmi_bounded_bt_design_run_ready"
    assert manifest["run_readiness_blocker"] == "none"
    assert manifest["next_action"] == "run_public_source_adx_dmi_bounded_bt_lane"
    assert consistency["consistency_passed"] is True


def test_source_backed_adx_dmi_parameters_are_frozen_and_not_tuned() -> None:
    manifest = load_manifest()
    param_rows = read_rows("source_backed_parameter_report.csv")
    params = {row["parameter"]: row for row in param_rows}
    formula = (EVIDENCE / "adx_dmi_formula_signal_definition.md").read_text(encoding="utf-8")
    parameter_report = (EVIDENCE / "source_backed_parameter_report.md").read_text(encoding="utf-8")

    assert manifest["source_backed_parameters"] is True
    assert manifest["parameter_status"] == "source_backed_parameters"
    assert manifest["dmi_adx_period"] == 14
    assert manifest["adx_trend_strength_threshold"] == 25
    assert manifest["bullish_direction_state"] == "+DI above -DI"
    assert manifest["bearish_or_cash_direction_state"] == "-DI above +DI"
    assert manifest["parameters_tuned"] is False
    assert manifest["alternative_adx_thresholds_added"] is False
    assert manifest["alternative_dmi_periods_added"] is False
    assert manifest["threshold_sweep_created"] is False
    assert manifest["spy200d_added_as_source_filter"] is False
    assert manifest["moving_average_filters_added"] is False
    assert manifest["rsi_macd_cci_bollinger_volume_filters_added"] is False
    assert manifest["volatility_filters_added"] is False
    assert manifest["stop_loss_or_profit_target_added"] is False
    assert manifest["alternate_exits_added"] is False
    assert params["dmi_adx_period"]["value"] == "14"
    assert params["adx_trend_strength_threshold"]["value"] == "25"
    assert params["tuned_parameters"]["value"] == "False"
    assert "ADX measures trend strength, not direction" in formula
    assert "+DI(14)" in formula
    assert "No ADX threshold sweep" in parameter_report


def test_formula_contract_smoothing_warmup_and_edge_cases_are_frozen() -> None:
    manifest = load_manifest()
    formula = (EVIDENCE / "adx_dmi_formula_signal_definition.md").read_text(encoding="utf-8")
    patch_report = (EVIDENCE / "formula_contract_patch_report.md").read_text(encoding="utf-8")
    utility = (EVIDENCE / "existing_utility_discovery_report.md").read_text(encoding="utf-8")
    warmup = (EVIDENCE / "warmup_effective_start_requirements.md").read_text(encoding="utf-8")

    assert manifest["formula_contract_complete"] is True
    assert manifest["formula_contract_version"] == "adx_dmi_wilder_contract_v1"
    assert manifest["canonical_adx_dmi_utility_found"] is False
    assert manifest["wilder_formula_contract_frozen"] is True
    assert manifest["uses_completed_daily_adjusted_ohlc"] is True
    assert manifest["previous_close_is_prior_completed_adjusted_close"] is True
    assert manifest["true_range_definition_documented"] is True
    assert manifest["positive_dm_definition_documented"] is True
    assert manifest["negative_dm_definition_documented"] is True
    assert manifest["wilder_smoothing_seed_documented"] is True
    assert manifest["wilder_smoothing_update_documented"] is True
    assert manifest["di_definition_documented"] is True
    assert manifest["dx_definition_documented"] is True
    assert manifest["adx_seed_documented"] is True
    assert manifest["adx_update_documented"] is True
    assert manifest["divide_by_zero_behavior_documented"] is True
    assert manifest["invalid_indicator_rows_signal_blocked"] is True
    assert manifest["warmup_effective_start_documented"] is True
    assert manifest["first_valid_di_date"]
    assert manifest["first_valid_adx_date"]
    assert manifest["effective_start_date_after_alignment_and_warmup"]
    assert "TR = max(high - low, abs(high - previous_close), abs(low - previous_close))" in formula
    assert "+DM = up_move if up_move > down_move and up_move > 0 else 0" in formula
    assert "-DM = down_move if down_move > up_move and down_move > 0 else 0" in formula
    assert "initial smoothed TR, +DM, and -DM use rolling sum" in formula
    assert "next_smoothed = prior_smoothed - (prior_smoothed / 14) + current_raw_component" in formula
    assert "+DI = 100 * smoothed(+DM) / smoothed(TR)" in formula
    assert "DX = 100 * abs(+DI - -DI) / (+DI + -DI)" in formula
    assert "initial ADX is the arithmetic mean of the first 14 valid DX values" in formula
    assert "ADX_t = ((ADX_{t-1} * 13) + DX_t) / 14" in formula
    assert "zero denominators produce NaN, not inf" in formula
    assert "Rows before valid +DI, -DI, and ADX must hold BIL/cash" in warmup
    assert "no strategy performance or backtest was computed" in patch_report
    assert "no ADX/DMI formula implementation found" in utility


def test_planned_rows_are_small_bounded_controls_non_promotable() -> None:
    manifest = load_manifest()
    rows = read_rows("planned_row_table.csv")

    assert manifest["planned_row_count"] == 5
    assert manifest["planned_row_count_target_4_to_5"] is True
    assert manifest["planned_row_count_lte_5"] is True
    assert manifest["primary_source_row_count"] == 1
    assert manifest["timing_sanity_row_count"] == 1
    assert manifest["control_row_count"] == 3
    assert {row["variant_id"] for row in rows} == {
        "adx_dmi_spy_bil_primary_v1",
        "adx_dmi_spy_bil_one_bar_delayed_timing_sanity_v1",
        "adx_dmi_spy_buy_hold_control_v1",
        "adx_dmi_bil_cash_control_v1",
        "adx_dmi_spy200d_frozen_control_v1",
    }
    assert all(row["promotion_eligibility"] == "False" for row in rows)
    assert all(row["paper_forward_eligibility"] == "False" for row in rows)
    assert all(row["candidate_exhaustive_eligibility"] == "False" for row in rows)
    primary = next(row for row in rows if row["variant_role"] == "source_primary")
    assert "dmi_adx_period=14" in primary["source_backed_parameters"]
    assert "adx_trend_strength_threshold=25" in primary["source_backed_parameters"]
    assert "+DI" in primary["entry_rule"]
    assert "-DI" in primary["exit_rule"]


def test_similarity_cache_adapter_timing_and_long_only_caveat_are_documented() -> None:
    manifest = load_manifest()
    cache_rows = read_rows("local_cache_availability.csv")
    similarity = (EVIDENCE / "similarity_risk_report.md").read_text(encoding="utf-8")
    caveat = (EVIDENCE / "long_only_adaptation_caveat.md").read_text(encoding="utf-8")
    timing = (EVIDENCE / "signal_timing_convention.md").read_text(encoding="utf-8")
    criteria = (EVIDENCE / "numeric_success_failure_criteria.md").read_text(encoding="utf-8")

    assert manifest["similarity_hit_preserved"] is True
    assert manifest["similarity_hit_count"] == 12
    assert manifest["duplicate_or_do_not_retest_blocker"] is False
    assert "Duplicate/do-not-retest blocker in current intake result: `false`" in similarity
    assert "long-only SPY/BIL adaptation only" in caveat
    assert manifest["uses_only_spy_and_bil"] is True
    assert manifest["spy_cache_ready"] is True
    assert manifest["bil_cache_ready"] is True
    assert manifest["spy_ohlc_cache_ready"] is True
    assert manifest["local_cache_complete"] is True
    assert {row["symbol"]: row["cache_status"] for row in cache_rows} == {"SPY": "cache_ready", "BIL": "cache_ready"}
    assert {row["symbol"]: row["data_requirement_status"] for row in cache_rows} == {
        "SPY": "daily_adjusted_ohlc_ready_for_adx_dmi",
        "BIL": "cash_proxy_adjusted_close_ready",
    }
    assert manifest["bt_adapter_control_poc_passed"] is True
    assert manifest["bt_adapter_multasset_poc_passed"] is True
    assert manifest["bt_adapter_ready_for_design"] is True
    assert manifest["signal_timing_convention_documented"] is True
    assert manifest["no_lookahead_timing_documented"] is True
    assert "completed daily close" in timing
    assert "shifted-weight convention" in timing
    assert "Average SPY exposure share is `>= 0.0500` and `<= 0.8500`" in criteria
    assert "Entry count, exit count, and completed round trips are reported" in criteria


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
    assert manifest["provider_download"] is False
    assert manifest["intraday_data_used"] is False
    assert manifest["new_packages_installed"] is False
    assert manifest["current_backtester_replaced"] is False
    assert manifest["strategy_discovery_run"] is False
    assert manifest["candidate_exhaustive_run"] is False
    assert manifest["promotion_candidates_created"] is False
    assert manifest["paper_forward_activation"] is False
    assert manifest["broker_api_called"] is False
    assert manifest["broker_orders_submitted"] is False
    assert manifest["broker_orders_cancelled"] is False
    assert manifest["broker_orders_reconciled"] is False
    assert manifest["live_orders"] is False
    assert manifest["real_money_recommendation"] is False
    assert manifest["public_source_presence_is_profitability_proof"] is False
    assert manifest["outputs_non_promotable"] is True


def test_required_design_evidence_files_exist() -> None:
    required = [
        "public_source_adx_dmi_bounded_bt_design_summary.md",
        "source_intake_review.md",
        "local_cache_availability.csv",
        "local_cache_availability.md",
        "source_backed_parameter_report.csv",
        "source_backed_parameter_report.md",
        "formula_contract_patch_report.md",
        "existing_utility_discovery_report.md",
        "adx_dmi_formula_signal_definition.md",
        "warmup_effective_start_requirements.md",
        "long_only_adaptation_caveat.md",
        "similarity_risk_report.md",
        "planned_row_table.csv",
        "planned_row_table.md",
        "signal_timing_convention.md",
        "baseline_control_policy.md",
        "numeric_success_failure_criteria.md",
        "bt_adapter_readiness.md",
        "guardrail_checklist.json",
        "exposure_invariant_requirements.md",
        "run_readiness_decision.md",
        "public_source_adx_dmi_bounded_bt_design_next_action.md",
    ]
    for filename in required:
        assert (EVIDENCE / filename).exists(), filename
