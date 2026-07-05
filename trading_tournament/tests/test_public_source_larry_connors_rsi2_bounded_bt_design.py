from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = (
    ROOT
    / "evidence"
    / "research_recovery"
    / "public_source_larry_connors_rsi2_bounded_bt_design"
    / "latest"
)


def load_manifest() -> dict:
    return json.loads(
        (EVIDENCE / "public_source_larry_connors_rsi2_bounded_bt_design_manifest.json").read_text(encoding="utf-8")
    )


def load_consistency() -> dict:
    return json.loads(
        (EVIDENCE / "public_source_larry_connors_rsi2_bounded_bt_design_consistency_check.json").read_text(
            encoding="utf-8"
        )
    )


def read_rows(filename: str) -> list[dict[str, str]]:
    with (EVIDENCE / filename).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_manifest_design_only_run_ready_and_correct_source() -> None:
    manifest = load_manifest()
    consistency = load_consistency()

    assert manifest["public_source_larry_connors_rsi2_bounded_bt_design_only"] is True
    assert manifest["source_id"] == "larry_connors_rsi2_mean_reversion"
    assert manifest["source_intake_eligibility_decision"] == "eligible_for_bounded_bt_design"
    assert manifest["batch_intake_eligibility_decision"] == "eligible_for_bounded_bt_design"
    assert manifest["lane_id"] == "public_source_larry_connors_rsi2_bounded_bt_lane_v1"
    assert manifest["family_id"] == "short_term_equity_mean_reversion"
    assert manifest["run_readiness_decision"] == "public_source_larry_connors_rsi2_bounded_bt_design_run_ready"
    assert manifest["run_readiness_blocker"] == "none"
    assert manifest["next_action"] == "run_public_source_larry_connors_rsi2_bounded_bt_lane"
    assert consistency["consistency_passed"] is True


def test_source_backed_parameters_are_frozen_and_not_tuned() -> None:
    manifest = load_manifest()
    param_rows = read_rows("source_backed_parameter_report.csv")
    params = {row["parameter"]: row for row in param_rows}
    parameter_report = (EVIDENCE / "source_backed_parameter_report.md").read_text(encoding="utf-8")

    assert manifest["source_backed_parameters"] is True
    assert manifest["parameter_status"] == "source_backed_parameters"
    assert manifest["rsi_period"] == 2
    assert manifest["rsi_entry_threshold"] == 5
    assert manifest["rsi_entry_operator"] == "less_than"
    assert manifest["trend_sma_period"] == 200
    assert manifest["exit_sma_period"] == 5
    assert manifest["parameters_tuned"] is False
    assert manifest["rsi_threshold_variants_added"] is False
    assert manifest["rsi_or_sma_parameters_tuned"] is False
    assert manifest["threshold_sweep_created"] is False
    assert manifest["other_indicators_added"] is False
    assert manifest["stop_loss_or_profit_target_added"] is False
    assert manifest["holding_period_exit_added"] is False
    assert params["rsi_period"]["value"] == "2"
    assert params["rsi_entry_threshold"]["value"] == "5"
    assert params["trend_sma_period"]["value"] == "200"
    assert params["exit_sma_period"]["value"] == "5"
    assert "No threshold sweep" in parameter_report


def test_planned_rows_are_small_bounded_controls_non_promotable() -> None:
    manifest = load_manifest()
    rows = read_rows("planned_row_table.csv")

    assert manifest["planned_row_count"] == 5
    assert manifest["planned_row_count_target_3_to_5"] is True
    assert manifest["planned_row_count_lte_5"] is True
    assert manifest["primary_source_row_count"] == 1
    assert manifest["timing_sanity_row_count"] == 1
    assert manifest["control_row_count"] == 3
    assert {row["variant_id"] for row in rows} == {
        "connors_rsi2_spy_bil_primary_v1",
        "connors_rsi2_spy_bil_one_bar_delayed_timing_sanity_v1",
        "connors_rsi2_spy_buy_hold_control_v1",
        "connors_rsi2_bil_cash_control_v1",
        "connors_rsi2_spy200d_frozen_control_v1",
    }
    assert all(row["promotion_eligibility"] == "False" for row in rows)
    assert all(row["paper_forward_eligibility"] == "False" for row in rows)
    assert all(row["candidate_exhaustive_eligibility"] == "False" for row in rows)
    primary = next(row for row in rows if row["variant_role"] == "source_primary")
    assert "rsi_period=2" in primary["source_backed_parameters"]
    assert "rsi_entry_threshold=5" in primary["source_backed_parameters"]
    assert "trend_sma_period=200" in primary["source_backed_parameters"]
    assert "exit_sma_period=5" in primary["source_backed_parameters"]


def test_similarity_cache_adapter_and_timing_requirements_are_documented() -> None:
    manifest = load_manifest()
    cache_rows = read_rows("local_cache_availability.csv")
    similarity = (EVIDENCE / "similarity_risk_report.md").read_text(encoding="utf-8")
    timing = (EVIDENCE / "signal_timing_convention.md").read_text(encoding="utf-8")
    criteria = (EVIDENCE / "numeric_success_failure_criteria.md").read_text(encoding="utf-8")

    assert manifest["similarity_hit_preserved"] is True
    assert manifest["mean_reversion_similarity_hit"] == "mean_reversion_rejected_or_existing_candidate"
    assert manifest["duplicate_or_do_not_retest_blocker"] is False
    assert "mean_reversion_rejected_or_existing_candidate" in similarity
    assert "Duplicate/do-not-retest blocker in current intake result: `false`" in similarity
    assert manifest["uses_only_spy_and_bil"] is True
    assert manifest["spy_cache_ready"] is True
    assert manifest["bil_cache_ready"] is True
    assert manifest["local_cache_complete"] is True
    assert {row["symbol"]: row["cache_status"] for row in cache_rows} == {"SPY": "cache_ready", "BIL": "cache_ready"}
    assert manifest["bt_adapter_control_poc_passed"] is True
    assert manifest["bt_adapter_multasset_poc_passed"] is True
    assert manifest["bt_adapter_ready_for_design"] is True
    assert manifest["signal_timing_convention_documented"] is True
    assert manifest["no_lookahead_timing_documented"] is True
    assert "RSI(2) < 5" in timing
    assert "SPY close > SMA(200)" in timing
    assert "shifted-weight convention" in timing
    assert "Average SPY exposure share is `>= 0.0100` and `<= 0.4500`" in criteria


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
        "public_source_larry_connors_rsi2_bounded_bt_design_summary.md",
        "source_intake_review.md",
        "local_cache_availability.csv",
        "local_cache_availability.md",
        "source_backed_parameter_report.csv",
        "source_backed_parameter_report.md",
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
        "public_source_larry_connors_rsi2_bounded_bt_design_next_action.md",
    ]
    for filename in required:
        assert (EVIDENCE / filename).exists(), filename
