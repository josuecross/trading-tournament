from __future__ import annotations

import csv
import json
from pathlib import Path

import pandas as pd

from strategy_lab.research_os.research.public_source_parabolic_sar_bounded_bt_run import (
    AF_INCREMENT,
    AF_MAXIMUM,
    AF_START,
    parabolic_sar_state,
    primary_targets,
)


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "research_recovery" / "public_source_parabolic_sar_bounded_bt_run" / "latest"


def load_manifest() -> dict:
    return json.loads((EVIDENCE / "public_source_parabolic_sar_bounded_bt_run_manifest.json").read_text(encoding="utf-8"))


def load_consistency() -> dict:
    return json.loads(
        (EVIDENCE / "public_source_parabolic_sar_bounded_bt_run_consistency_check.json").read_text(encoding="utf-8")
    )


def read_rows(filename: str) -> list[dict[str, str]]:
    with (EVIDENCE / filename).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_manifest_exact_lane_formula_rows_and_next_action() -> None:
    manifest = load_manifest()
    consistency = load_consistency()

    assert manifest["public_source_parabolic_sar_bounded_bt_run"] is True
    assert manifest["source_id"] == "parabolic_sar_spy_bil_long_only_reversal"
    assert manifest["lane_id"] == "public_source_parabolic_sar_bounded_bt_lane_v1"
    assert manifest["family_id"] == "equity_index_parabolic_sar_trend_reversal"
    assert manifest["source_design_run_ready"] is True
    assert manifest["source_design_next_action_correct"] is True
    assert manifest["variant_count_planned"] == 5
    assert manifest["variant_count_evaluated"] == 5
    assert manifest["formula_contract_version"] == "parabolic_sar_wilder_stockcharts_contract_v1"
    assert manifest["formula_contract_used_exactly"] is True
    assert manifest["formula_contract_complete"] is True
    assert manifest["next_action"] == "audit_public_source_parabolic_sar_bounded_bt_results"
    assert consistency["consistency_passed"] is True


def test_frozen_source_backed_parameters_and_no_expansion() -> None:
    manifest = load_manifest()

    assert manifest["indicator_parameters_source_backed"] is True
    assert manifest["af_start"] == AF_START == 0.02
    assert manifest["af_increment"] == AF_INCREMENT == 0.02
    assert manifest["af_maximum"] == AF_MAXIMUM == 0.20
    assert manifest["parameters_tuned"] is False
    assert manifest["alternative_af_parameters_added"] is False
    assert manifest["threshold_sweep_created"] is False
    assert manifest["optimization_run"] is False
    assert manifest["adx_filter_added"] is False
    assert manifest["moving_average_filters_added"] is False
    assert manifest["rsi_macd_cci_bollinger_volume_filters_added"] is False
    assert manifest["volatility_filters_added"] is False
    assert manifest["stop_loss_or_profit_target_added"] is False
    assert manifest["alternate_exits_added"] is False
    assert manifest["spy200d_added_as_source_filter"] is False
    assert manifest["new_instruments_added"] is False
    assert manifest["new_variants_added"] is False


def test_row_results_exact_variants_roles_and_non_promotable() -> None:
    rows = read_rows("row_level_results.csv")
    manifest = load_manifest()

    assert {row["variant_id"] for row in rows} == set(manifest["approved_variant_ids"])
    assert {row["variant_role"] for row in rows} == {"source_primary", "timing_sanity_context", "control"}
    assert sum(row["variant_role"] == "source_primary" for row in rows) == 1
    assert sum(row["variant_role"] == "timing_sanity_context" for row in rows) == 1
    assert sum(row["variant_role"] == "control" for row in rows) == 3
    assert all(row["promotion_eligibility"] == "False" for row in rows)
    assert all(row["paper_forward_eligibility"] == "False" for row in rows)
    assert all(row["candidate_exhaustive_eligibility"] == "False" for row in rows)
    primary = next(row for row in rows if row["variant_id"] == "parabolic_sar_spy_bil_primary_v1")
    timing = next(row for row in rows if row["variant_id"] == "parabolic_sar_spy_bil_one_bar_delayed_timing_sanity_v1")
    assert primary["research_only_label"] in {
        "parabolic_sar_primary_diagnostic_passed",
        "parabolic_sar_primary_diagnostic_failed",
    }
    assert timing["research_only_label"] == "parabolic_sar_timing_sanity_context_only"
    assert timing["timing_sanity_context_only"] == "True"


def test_exposure_invariants_and_shifted_weight_guardrails() -> None:
    manifest = load_manifest()
    weights = read_rows("daily_target_weights.csv")

    assert manifest["exposure_invariant_passed"] is True
    assert manifest["invariant_failure_count"] == 0
    assert manifest["max_daily_exposure"] <= 1.000001
    assert manifest["max_daily_weight_sum"] <= 1.000001
    assert manifest["bil_cash_replacement_remainder_only"] is True
    assert manifest["zero_target_weights_stale_forward_filled"] is False
    assert manifest["signal_timing_no_lookahead"] is True
    assert manifest["invalid_pretradable_rows_signal_active"] is False
    assert manifest["one_extra_bar_delayed_timing_sanity_only"] is True
    assert max(float(row["weight_sum"]) for row in weights) <= 1.000001
    assert max(float(row["risky_exposure"]) for row in weights) <= 1.000001
    assert min(float(row["SPY"]) for row in weights) >= -1e-9
    assert min(float(row["BIL"]) for row in weights) >= -1e-9


def test_sar_tables_events_and_trade_counts_exist_and_are_consistent() -> None:
    manifest = load_manifest()
    state_rows = read_rows("sar_state_table.csv")
    event_rows = read_rows("daily_signal_event_table.csv")
    turnover_rows = read_rows("rebalance_turnover_report.csv")

    assert manifest["first_valid_sar_date"]
    assert manifest["first_reversal_date"]
    assert manifest["first_tradable_signal_date"]
    assert manifest["bullish_flip_count"] > 0
    assert manifest["bearish_flip_count"] > 0
    assert manifest["primary_entry_count"] > 0
    assert manifest["primary_exit_count"] > 0
    assert manifest["primary_completed_round_trip_count"] > 0
    assert len(state_rows) == manifest["full_spy_ohlc_rows"]
    assert len(event_rows) == manifest["full_spy_ohlc_rows"]
    assert {row["variant_id"] for row in turnover_rows} == set(manifest["approved_variant_ids"])


def test_deterministic_sar_reversal_state_machine_uses_true_flip_events() -> None:
    dates = pd.date_range("2020-01-01", periods=6, freq="D")
    ohlc = pd.DataFrame(
        {
            "high": [10.0, 11.0, 12.0, 13.0, 12.0, 14.0],
            "low": [9.0, 10.0, 11.0, 12.0, 8.0, 9.0],
            "close": [10.0, 11.0, 11.5, 12.5, 9.0, 13.0],
        },
        index=dates,
    )
    state = parabolic_sar_state(ohlc)
    weights, events = primary_targets(state)

    assert bool(state.loc[dates[0], "valid_sar"]) is False
    assert bool(state.loc[dates[1], "valid_sar"]) is True
    assert bool(state.loc[dates[4], "bearish_flip"]) is True
    assert bool(state.loc[dates[5], "bullish_flip"]) is True
    assert bool(weights.loc[dates[4], "BIL"] == 1.0)
    assert bool(weights.loc[dates[5], "SPY"] == 1.0)
    assert int(events["entry_signal"].sum()) == 1
    assert int(events["exit_signal"].sum()) == 1


def test_guardrails_no_download_scrape_promotion_paper_or_broker_paths() -> None:
    manifest = load_manifest()

    assert manifest["uses_local_cache_only"] is True
    assert manifest["provider_download"] is False
    assert manifest["intraday_data_used"] is False
    assert manifest["public_source_scraped"] is False
    assert manifest["public_strategy_list_ingested"] is False
    assert manifest["additional_public_sources_ingested"] is False
    assert manifest["strategy_discovery_run"] is False
    assert manifest["new_research_batch_run"] is False
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
    assert manifest["outputs_diagnostic_only"] is True
    assert manifest["outputs_non_promotable"] is True
    assert manifest["candidate_exhaustive_ready"] is False
    assert manifest["paper_demo_eligible"] is False
    assert manifest["public_source_presence_is_profitability_proof"] is False


def test_required_run_evidence_files_exist() -> None:
    required = [
        "public_source_parabolic_sar_bounded_bt_run_manifest.json",
        "public_source_parabolic_sar_bounded_bt_run_consistency_check.json",
        "row_level_results.csv",
        "numeric_criteria_results.csv",
        "parabolic_sar_formula_calculation_report.md",
        "initialization_warmup_tradability_report.md",
        "reversal_state_transition_report.md",
        "signal_timing_no_lookahead_report.md",
        "sar_state_table.csv",
        "daily_signal_event_table.csv",
        "daily_target_weights.csv",
        "equity_curve_returns.csv",
        "rebalance_turnover_report.csv",
        "rebalance_turnover_report.md",
        "event_trade_count_report.md",
        "baseline_control_comparison_report.csv",
        "baseline_control_comparison_report.md",
        "whipsaw_turnover_risk_note.md",
        "exposure_invariant_report.md",
        "similarity_risk_report.md",
        "long_only_adaptation_caveat_report.md",
        "role_label_summary.md",
        "public_source_parabolic_sar_bounded_bt_run_summary.md",
        "public_source_parabolic_sar_bounded_bt_run_next_action.md",
    ]
    for filename in required:
        assert (EVIDENCE / filename).exists(), filename
