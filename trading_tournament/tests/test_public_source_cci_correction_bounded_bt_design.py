from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "research_recovery" / "public_source_cci_correction_bounded_bt_design" / "latest"


def load_manifest() -> dict:
    return json.loads(
        (EVIDENCE / "public_source_cci_correction_bounded_bt_design_manifest.json").read_text(encoding="utf-8")
    )


def load_consistency() -> dict:
    return json.loads(
        (EVIDENCE / "public_source_cci_correction_bounded_bt_design_consistency_check.json").read_text(
            encoding="utf-8"
        )
    )


def read_rows(filename: str) -> list[dict[str, str]]:
    with (EVIDENCE / filename).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_manifest_design_only_run_ready_and_correct_source() -> None:
    manifest = load_manifest()
    consistency = load_consistency()

    assert manifest["public_source_cci_correction_bounded_bt_design_only"] is True
    assert manifest["source_id"] == "cci_correction"
    assert manifest["source_intake_eligibility_decision"] == "eligible_for_bounded_bt_design"
    assert manifest["batch_intake_eligibility_decision"] == "eligible_for_bounded_bt_design"
    assert manifest["lane_id"] == "public_source_cci_correction_bounded_bt_lane_v1"
    assert manifest["family_id"] == "equity_index_cci_pullback_trend_bias"
    assert manifest["run_readiness_decision"] == "public_source_cci_correction_bounded_bt_design_run_ready"
    assert manifest["run_readiness_blocker"] == "none"
    assert manifest["next_action"] == "run_public_source_cci_correction_bounded_bt_lane"
    assert consistency["consistency_passed"] is True


def test_source_backed_cci_parameters_are_frozen_and_not_tuned() -> None:
    manifest = load_manifest()
    param_rows = read_rows("source_backed_parameter_report.csv")
    params = {row["parameter"]: row for row in param_rows}
    parameter_report = (EVIDENCE / "source_backed_parameter_report.md").read_text(encoding="utf-8")
    cci_definition = (EVIDENCE / "weekly_daily_cci_signal_definition.md").read_text(encoding="utf-8")

    assert manifest["source_backed_parameters"] is True
    assert manifest["parameter_status"] == "source_backed_parameters"
    assert manifest["weekly_cci_period"] == 26
    assert manifest["daily_cci_period"] == 26
    assert manifest["weekly_bullish_bias_threshold"] == 100
    assert manifest["weekly_bearish_bias_threshold"] == -100
    assert manifest["daily_pullback_threshold"] == -100
    assert manifest["daily_reversal_threshold"] == 0
    assert manifest["parameters_tuned"] is False
    assert manifest["daily_only_variants_added"] is False
    assert manifest["weekly_only_variants_added"] is False
    assert manifest["alternate_cci_periods_added"] is False
    assert manifest["alternate_thresholds_added"] is False
    assert manifest["cci_parameters_tuned"] is False
    assert manifest["threshold_sweep_created"] is False
    assert params["weekly_cci_period"]["value"] == "26"
    assert params["daily_cci_period"]["value"] == "26"
    assert params["weekly_bullish_bias_threshold"]["value"] == "100"
    assert params["weekly_bearish_bias_threshold"]["value"] == "-100"
    assert "No alternate CCI period" in parameter_report
    assert "CCI(n)" in cci_definition
    assert "Weekly CCI(26)" in cci_definition
    assert "Daily CCI(26)" in cci_definition


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
        "cci_correction_spy_bil_primary_v1",
        "cci_correction_spy_bil_one_bar_delayed_timing_sanity_v1",
        "cci_correction_spy_buy_hold_control_v1",
        "cci_correction_bil_cash_control_v1",
        "cci_correction_spy200d_frozen_control_v1",
    }
    assert all(row["promotion_eligibility"] == "False" for row in rows)
    assert all(row["paper_forward_eligibility"] == "False" for row in rows)
    assert all(row["candidate_exhaustive_eligibility"] == "False" for row in rows)
    primary = next(row for row in rows if row["variant_role"] == "source_primary")
    assert "weekly_cci_period=26" in primary["source_backed_parameters"]
    assert "daily_cci_period=26" in primary["source_backed_parameters"]
    assert "daily_reversal_threshold=0" in primary["source_backed_parameters"]


def test_similarity_long_only_cache_adapter_and_timing_requirements_are_documented() -> None:
    manifest = load_manifest()
    cache_rows = read_rows("local_cache_availability.csv")
    similarity = (EVIDENCE / "similarity_risk_report.md").read_text(encoding="utf-8")
    long_only = (EVIDENCE / "long_only_adaptation_caveat.md").read_text(encoding="utf-8")
    timing = (EVIDENCE / "signal_timing_convention.md").read_text(encoding="utf-8")
    criteria = (EVIDENCE / "numeric_success_failure_criteria.md").read_text(encoding="utf-8")

    assert manifest["similarity_hit_count"] == 10
    assert manifest["duplicate_or_do_not_retest_blocker"] is False
    assert "larry_connors_rsi2_mean_reversion" in similarity
    assert "price_band_money_flow_confirmation" in similarity
    assert "coppock_curve_monthly_equity_signal" in similarity
    assert "Duplicate/do-not-retest blocker in current intake result: `false`" in similarity
    assert manifest["long_only_adaptation_caveat_documented"] is True
    assert manifest["bearish_mode_maps_to_bil_cash"] is True
    assert "Bearish mode maps to BIL/cash only" in long_only
    assert manifest["uses_only_spy_and_bil"] is True
    assert {row["symbol"]: row["cache_status"] for row in cache_rows} == {"SPY": "cache_ready", "BIL": "cache_ready"}
    assert {row["symbol"]: row["data_requirement_status"] for row in cache_rows} == {
        "SPY": "adjusted_ohlcv_ready",
        "BIL": "cash_proxy_adjusted_close_ready",
    }
    assert manifest["bt_adapter_control_poc_passed"] is True
    assert manifest["bt_adapter_multasset_poc_passed"] is True
    assert manifest["bt_adapter_ready_for_design"] is True
    assert manifest["weekly_daily_cci_definition_documented"] is True
    assert manifest["signal_timing_convention_documented"] is True
    assert manifest["no_lookahead_timing_documented"] is True
    assert "completed weekly OHLC bars" in timing
    assert "shifted-weight convention" in timing
    assert "Average SPY exposure share is `>= 0.0500` and `<= 0.8000`" in criteria


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
    assert manifest["shorting_inverse_leverage_options_futures_intraday_added"] is False
    assert manifest["public_source_presence_is_profitability_proof"] is False
    assert manifest["outputs_non_promotable"] is True


def test_required_design_evidence_files_exist() -> None:
    required = [
        "public_source_cci_correction_bounded_bt_design_summary.md",
        "source_intake_review.md",
        "local_cache_availability.csv",
        "local_cache_availability.md",
        "source_backed_parameter_report.csv",
        "source_backed_parameter_report.md",
        "weekly_daily_cci_signal_definition.md",
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
        "public_source_cci_correction_bounded_bt_design_next_action.md",
    ]
    for filename in required:
        assert (EVIDENCE / filename).exists(), filename
