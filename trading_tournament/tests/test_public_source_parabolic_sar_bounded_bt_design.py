from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "research_recovery" / "public_source_parabolic_sar_bounded_bt_design" / "latest"


def load_manifest() -> dict:
    return json.loads(
        (EVIDENCE / "public_source_parabolic_sar_bounded_bt_design_manifest.json").read_text(encoding="utf-8")
    )


def load_consistency() -> dict:
    return json.loads(
        (EVIDENCE / "public_source_parabolic_sar_bounded_bt_design_consistency_check.json").read_text(
            encoding="utf-8"
        )
    )


def read_rows(filename: str) -> list[dict[str, str]]:
    with (EVIDENCE / filename).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_manifest_design_only_run_ready_and_correct_source() -> None:
    manifest = load_manifest()
    consistency = load_consistency()

    assert manifest["public_source_parabolic_sar_bounded_bt_design_only"] is True
    assert manifest["source_id"] == "parabolic_sar_spy_bil_long_only_reversal"
    assert manifest["source_intake_eligibility_decision"] == "eligible_for_bounded_bt_design"
    assert manifest["batch_intake_eligibility_decision"] == "eligible_for_bounded_bt_design"
    assert manifest["lane_id"] == "public_source_parabolic_sar_bounded_bt_lane_v1"
    assert manifest["family_id"] == "equity_index_parabolic_sar_trend_reversal"
    assert manifest["run_readiness_decision"] == "public_source_parabolic_sar_bounded_bt_design_run_ready"
    assert manifest["run_readiness_blocker"] == "none"
    assert manifest["next_action"] == "run_public_source_parabolic_sar_bounded_bt_lane"
    assert consistency["consistency_passed"] is True


def test_formula_contract_initialization_reversal_and_warmup_are_documented() -> None:
    manifest = load_manifest()
    formula = (EVIDENCE / "parabolic_sar_formula_signal_definition.md").read_text(encoding="utf-8")
    initialization = (EVIDENCE / "initialization_convention_report.md").read_text(encoding="utf-8")
    reversal = (EVIDENCE / "reversal_state_transition_report.md").read_text(encoding="utf-8")
    warmup = (EVIDENCE / "warmup_tradability_report.md").read_text(encoding="utf-8")
    contract = (EVIDENCE / "formula_contract_report.md").read_text(encoding="utf-8")
    utility = (EVIDENCE / "existing_utility_discovery_report.md").read_text(encoding="utf-8")

    assert manifest["formula_contract_id"] == "parabolic_sar_wilder_stockcharts_contract_v1"
    assert manifest["formula_contract_complete"] is True
    assert manifest["repository_standard_psar_utility_found"] is False
    assert manifest["uses_completed_daily_adjusted_ohlc"] is True
    assert manifest["initialization_convention_documented"] is True
    assert manifest["initialization_convention_is_implementation_convention"] is True
    assert manifest["reversal_state_transition_documented"] is True
    assert manifest["warmup_tradability_documented"] is True
    assert manifest["first_valid_sar_date_reporting_required"] is True
    assert manifest["first_reversal_date_reporting_required"] is True
    assert manifest["first_tradable_signal_date_reporting_required"] is True
    assert "SAR_t = SAR_{t-1}" in contract
    assert "implementation convention, not optimization" in initialization
    assert "reset AF to 0.02" in reversal
    assert "Pre-tradable rows must hold BIL/cash" in warmup
    assert "Bullish state" in formula
    assert "no repository-standard PSAR utility" in utility


def test_source_backed_parameters_are_frozen_and_not_tuned() -> None:
    manifest = load_manifest()
    rows = read_rows("source_backed_parameter_report.csv")
    params = {row["parameter"]: row for row in rows}
    report = (EVIDENCE / "source_backed_parameter_report.md").read_text(encoding="utf-8")

    assert manifest["source_backed_parameters"] is True
    assert manifest["parameters_tuned"] is False
    assert manifest["af_start"] == 0.02
    assert manifest["af_increment"] == 0.02
    assert manifest["af_maximum"] == 0.2
    assert manifest["alternative_af_parameters_added"] is False
    assert manifest["threshold_sweep_created"] is False
    assert manifest["adx_filter_added"] is False
    assert manifest["moving_average_filters_added"] is False
    assert manifest["rsi_macd_cci_bollinger_volume_filters_added"] is False
    assert manifest["filters_added"] is False
    assert manifest["stop_loss_or_profit_target_added"] is False
    assert manifest["alternate_exits_added"] is False
    assert params["parabolic_sar_acceleration_factor_start"]["value"] == "0.02"
    assert params["parabolic_sar_acceleration_factor_increment"]["value"] == "0.02"
    assert params["parabolic_sar_acceleration_factor_maximum"]["value"] == "0.2"
    assert "No alternate AF settings" in report


def test_planned_rows_are_exact_small_bounded_controls_non_promotable() -> None:
    manifest = load_manifest()
    rows = read_rows("planned_row_table.csv")

    assert manifest["planned_row_count"] == 5
    assert manifest["planned_row_count_target_4_to_5"] is True
    assert manifest["planned_row_count_lte_5"] is True
    assert manifest["primary_source_row_count"] == 1
    assert manifest["timing_sanity_row_count"] == 1
    assert manifest["control_row_count"] == 3
    assert {row["variant_id"] for row in rows} == {
        "parabolic_sar_spy_bil_primary_v1",
        "parabolic_sar_spy_bil_one_bar_delayed_timing_sanity_v1",
        "parabolic_sar_spy_buy_hold_control_v1",
        "parabolic_sar_bil_cash_control_v1",
        "parabolic_sar_spy200d_frozen_control_v1",
    }
    assert all(row["promotion_eligibility"] == "False" for row in rows)
    assert all(row["paper_forward_eligibility"] == "False" for row in rows)
    assert all(row["candidate_exhaustive_eligibility"] == "False" for row in rows)
    assert all(row["spy200d_source_filter"] == "False" for row in rows)
    primary = next(row for row in rows if row["variant_role"] == "source_primary")
    assert "AF_start=0.02" in primary["source_backed_parameters"]
    assert "SAR flips from above price to below price" in primary["entry_rule"]
    assert "SAR flips from below price to above price" in primary["exit_rule"]


def test_similarity_cache_adapter_timing_and_risk_caveats_are_documented() -> None:
    manifest = load_manifest()
    cache_rows = read_rows("local_cache_availability.csv")
    similarity = (EVIDENCE / "similarity_risk_report.md").read_text(encoding="utf-8")
    caveat = (EVIDENCE / "long_only_adaptation_caveat.md").read_text(encoding="utf-8")
    whipsaw = (EVIDENCE / "whipsaw_ranging_market_risk.md").read_text(encoding="utf-8")
    timing = (EVIDENCE / "signal_timing_convention.md").read_text(encoding="utf-8")
    criteria = (EVIDENCE / "numeric_success_failure_criteria.md").read_text(encoding="utf-8")

    assert manifest["similarity_hit_preserved"] is True
    assert manifest["similarity_hit_count"] == 13
    assert manifest["duplicate_or_do_not_retest_blocker"] is False
    assert "Duplicate/do-not-retest blocker in current intake result: `false`" in similarity
    assert "long-only SPY/BIL adaptation" in caveat
    assert manifest["whipsaw_ranging_market_risk_documented"] is True
    assert "whipsaw risk" in whipsaw
    assert manifest["uses_only_spy_and_bil"] is True
    assert manifest["spy_cache_ready"] is True
    assert manifest["bil_cache_ready"] is True
    assert manifest["spy_ohlc_cache_ready"] is True
    assert manifest["local_cache_complete"] is True
    assert {row["symbol"]: row["cache_status"] for row in cache_rows} == {"SPY": "cache_ready", "BIL": "cache_ready"}
    assert {row["symbol"]: row["data_requirement_status"] for row in cache_rows} == {
        "SPY": "daily_adjusted_ohlc_ready_for_parabolic_sar",
        "BIL": "cash_proxy_adjusted_close_ready",
    }
    assert manifest["bt_adapter_control_poc_passed"] is True
    assert manifest["bt_adapter_multasset_poc_passed"] is True
    assert manifest["bt_adapter_ready_for_design"] is True
    assert manifest["signal_timing_convention_documented"] is True
    assert manifest["no_lookahead_timing_documented"] is True
    assert "completed daily adjusted SPY OHLC" in timing
    assert "shifted-weight convention" in timing
    assert "Average SPY exposure share is `>= 0.0500` and `<= 0.8500`" in criteria
    assert "Entry count, exit count, completed round trips, and turnover are reported" in criteria


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
        "public_source_parabolic_sar_bounded_bt_design_summary.md",
        "source_intake_review.md",
        "local_cache_availability.csv",
        "local_cache_availability.md",
        "source_backed_parameter_report.csv",
        "source_backed_parameter_report.md",
        "formula_contract_report.md",
        "existing_utility_discovery_report.md",
        "parabolic_sar_formula_signal_definition.md",
        "initialization_convention_report.md",
        "reversal_state_transition_report.md",
        "warmup_tradability_report.md",
        "long_only_adaptation_caveat.md",
        "whipsaw_ranging_market_risk.md",
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
        "do_not_run_or_promote.md",
        "public_source_parabolic_sar_bounded_bt_design_next_action.md",
    ]
    for filename in required:
        assert (EVIDENCE / filename).exists(), filename
