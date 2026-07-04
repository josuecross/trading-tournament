from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "research_recovery" / "public_source_percent_b_money_flow_bounded_bt_design" / "latest"


def load_manifest() -> dict:
    return json.loads(
        (EVIDENCE / "public_source_percent_b_money_flow_bounded_bt_design_manifest.json").read_text(encoding="utf-8")
    )


def load_consistency() -> dict:
    return json.loads(
        (EVIDENCE / "public_source_percent_b_money_flow_bounded_bt_design_consistency_check.json").read_text(
            encoding="utf-8"
        )
    )


def read_rows(filename: str) -> list[dict[str, str]]:
    with (EVIDENCE / filename).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_manifest_design_only_and_run_ready_with_source_backed_parameters() -> None:
    manifest = load_manifest()
    consistency = load_consistency()

    assert manifest["public_source_percent_b_money_flow_bounded_bt_design_only"] is True
    assert manifest["source_id"] == "percent_b_money_flow"
    assert manifest["source_intake_eligibility_decision"] == "eligible_for_bounded_bt_design"
    assert manifest["lane_id"] == "public_source_percent_b_money_flow_bounded_bt_lane_v1"
    assert manifest["family_id"] == "price_band_money_flow_confirmation"
    assert manifest["indicator_definitions_complete"] is True
    assert manifest["missing_indicator_parameters"] == []
    assert manifest["source_backed_indicator_parameters"] is True
    assert manifest["indicator_parameters_tuned"] is False
    assert manifest["bollinger_band_period"] == 20
    assert manifest["bollinger_band_standard_deviation"] == 2
    assert manifest["money_flow_index_period"] == 10
    assert manifest["percent_b_upper_threshold"] == 0.8
    assert manifest["percent_b_lower_threshold"] == 0.2
    assert manifest["mfi_upper_threshold"] == 80
    assert manifest["mfi_lower_threshold"] == 20
    assert manifest["run_readiness_decision"] == "public_source_percent_b_money_flow_bounded_bt_design_run_ready"
    assert manifest["run_readiness_blocker"] == "none"
    assert manifest["next_action"] == "run_public_source_percent_b_money_flow_bounded_bt_lane"
    assert consistency["consistency_passed"] is True


def test_executable_rows_are_small_bounded_and_non_promotable() -> None:
    manifest = load_manifest()
    rows = read_rows("planned_row_table.csv")
    indicator_rows = read_rows("indicator_definition_completeness.csv")
    source_params = (EVIDENCE / "source_backed_parameter_report.md").read_text(encoding="utf-8")

    assert manifest["planned_rows_frozen"] is True
    assert manifest["planned_row_count"] == 5
    assert manifest["planned_row_count_lte_6"] is True
    assert manifest["primary_source_row_count"] == 1
    assert manifest["timing_sanity_row_count"] == 1
    assert manifest["control_row_count"] == 3
    assert {row["status"] for row in indicator_rows} == {"present"}
    assert {row["variant_id"] for row in rows} == {
        "percent_b_mfi_spy_bil_primary_v1",
        "percent_b_mfi_spy_bil_one_bar_delayed_timing_sanity_v1",
        "percent_b_mfi_spy_buy_hold_control_v1",
        "percent_b_mfi_bil_cash_control_v1",
        "percent_b_mfi_spy200d_frozen_control_v1",
    }
    assert all(row["promotion_eligibility"] == "False" for row in rows)
    assert all(row["paper_forward_eligibility"] == "False" for row in rows)
    assert all(row["candidate_exhaustive_eligibility"] == "False" for row in rows)
    primary = next(row for row in rows if row["variant_role"] == "source_primary")
    assert "bollinger_band_period=20" in primary["indicator_parameters"]
    assert "money_flow_index_period=10" in primary["indicator_parameters"]
    assert "percent_b_upper_threshold=0.8" in primary["indicator_parameters"]
    assert "mfi_upper_threshold=80" in primary["indicator_parameters"]
    assert "Parameter status: `source_backed_parameters`" in source_params
    assert "Tuned parameters: `False`" in source_params


def test_cache_bt_adapter_and_timing_requirements_are_documented() -> None:
    manifest = load_manifest()
    cache_rows = read_rows("local_cache_availability.csv")
    timing = (EVIDENCE / "signal_timing_convention.md").read_text(encoding="utf-8")
    criteria = (EVIDENCE / "numeric_success_failure_criteria.md").read_text(encoding="utf-8")

    assert manifest["uses_only_spy_and_bil"] is True
    assert manifest["spy_cache_ready"] is True
    assert manifest["bil_cache_ready"] is True
    assert manifest["local_cache_complete"] is True
    assert {row["symbol"]: row["cache_status"] for row in cache_rows} == {"SPY": "cache_ready", "BIL": "cache_ready"}
    assert {row["symbol"]: row["data_requirement_status"] for row in cache_rows} == {
        "SPY": "adjusted_ohlcv_ready",
        "BIL": "cash_proxy_adjusted_close_ready",
    }
    assert manifest["bt_adapter_control_poc_passed"] is True
    assert manifest["bt_adapter_multasset_poc_passed"] is True
    assert manifest["bt_adapter_ready_for_design"] is True
    assert manifest["signal_timing_convention_documented"] is True
    assert manifest["no_lookahead_timing_documented"] is True
    assert "%B > 0.80" in timing
    assert "MFI(10) > 80" in timing
    assert "shifted-weight convention" in timing
    assert "Max drawdown reduction versus SPY buy-and-hold is `>= 0.2000`" in criteria
    assert "Duplicate/reference correlation" in criteria


def test_guardrails_no_run_backtest_expansion_or_execution_paths() -> None:
    manifest = load_manifest()

    assert manifest["bounded_bt_design_packet_created"] is True
    assert manifest["executable_bounded_bt_design_created"] is True
    assert manifest["bounded_bt_lane_run"] is False
    assert manifest["strategy_backtest_run"] is False
    assert manifest["strategy_implemented"] is False
    assert manifest["public_source_scraped"] is False
    assert manifest["public_strategy_list_ingested"] is False
    assert manifest["additional_public_sources_ingested"] is False
    assert manifest["percent_b_thresholds_tuned"] is False
    assert manifest["mfi_thresholds_tuned"] is False
    assert manifest["bollinger_or_mfi_periods_tuned"] is False
    assert manifest["threshold_sweep_created"] is False
    assert manifest["other_indicators_added"] is False
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
        "public_source_percent_b_money_flow_bounded_bt_design_summary.md",
        "source_intake_review.md",
        "local_cache_availability.csv",
        "local_cache_availability.md",
        "indicator_definition_completeness.csv",
        "indicator_definition_completeness.md",
        "source_backed_parameter_report.md",
        "planned_row_table.csv",
        "planned_row_table.md",
        "signal_timing_convention.md",
        "baseline_control_policy.md",
        "numeric_success_failure_criteria.md",
        "bt_adapter_readiness.md",
        "guardrail_checklist.json",
        "exposure_invariant_requirements.md",
        "run_readiness_decision.md",
        "public_source_percent_b_money_flow_bounded_bt_design_next_action.md",
    ]
    for filename in required:
        assert (EVIDENCE / filename).exists(), filename
