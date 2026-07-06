from __future__ import annotations

import csv
import json
from pathlib import Path

import pandas as pd

from strategy_lab.research_os.research.public_source_coppock_curve_bounded_bt_run import (
    EXPECTED_VARIANTS,
    LANE_ID,
    coppock_events,
    target_map_from_events,
)


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "research_recovery" / "public_source_coppock_curve_bounded_bt_run" / "latest"


def load_manifest() -> dict:
    return json.loads(
        (EVIDENCE / "public_source_coppock_curve_bounded_bt_run_manifest.json").read_text(encoding="utf-8")
    )


def load_consistency() -> dict:
    return json.loads(
        (EVIDENCE / "public_source_coppock_curve_bounded_bt_run_consistency_check.json").read_text(encoding="utf-8")
    )


def load_rows() -> list[dict[str, str]]:
    with (EVIDENCE / "row_level_results.csv").open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def bool_text(value: str) -> bool:
    return value == "True"


def test_manifest_exact_coppock_bounded_lane_run_contract() -> None:
    manifest = load_manifest()
    consistency = load_consistency()

    assert manifest["public_source_coppock_curve_bounded_bt_lane_run"] is True
    assert manifest["source_id"] == "coppock_curve_monthly_equity_signal"
    assert manifest["family_id"] == "long_term_equity_index_momentum_zero_cross"
    assert manifest["lane_id"] == LANE_ID
    assert manifest["source_design_run_ready"] is True
    assert manifest["source_design_next_action_correct"] is True
    assert manifest["formula_implemented"] is True
    assert manifest["formula_status"] == "coppock_roc14_plus_roc11_wma10_completed_monthly_adjusted_close"
    assert manifest["source_backed_parameters"] is True
    assert manifest["roc_periods"] == [14, 11]
    assert manifest["wma_smoothing_period"] == 10
    assert manifest["signal_threshold"] == 0.0
    assert manifest["parameters_tuned"] is False
    assert manifest["variant_count_planned"] == 5
    assert manifest["variant_count_evaluated"] == 5
    assert manifest["approved_variant_ids"] == list(EXPECTED_VARIANTS)
    assert set(manifest["evaluated_variant_ids"]) == set(EXPECTED_VARIANTS)
    assert manifest["primary_source_row_count"] == 1
    assert manifest["timing_sanity_row_count"] == 1
    assert manifest["control_row_count"] == 3
    assert consistency["consistency_passed"] is True


def test_guardrails_and_non_promotable_outputs() -> None:
    manifest = load_manifest()
    rows = load_rows()

    assert manifest["uses_local_cache_only"] is True
    assert manifest["provider_download"] is False
    assert manifest["intraday_data_used"] is False
    assert manifest["public_source_scraped"] is False
    assert manifest["public_strategy_list_ingested"] is False
    assert manifest["bounded_bt_design_changed"] is False
    assert manifest["new_instruments_added"] is False
    assert manifest["daily_coppock_variants_added"] is False
    assert manifest["weekly_coppock_variants_added"] is False
    assert manifest["alternate_roc_periods_added"] is False
    assert manifest["alternate_smoothing_periods_added"] is False
    assert manifest["signal_lines_added"] is False
    assert manifest["moving_average_filters_added"] is False
    assert manifest["volatility_filters_added"] is False
    assert manifest["stop_loss_or_profit_target_added"] is False
    assert manifest["holding_period_exit_added"] is False
    assert manifest["divergence_rules_added"] is False
    assert manifest["additional_exits_added"] is False
    assert manifest["parameter_sweep_created"] is False
    assert manifest["optimization_run"] is False
    assert manifest["larry_connors_continued"] is False
    assert manifest["percent_b_continued"] is False
    assert manifest["turn_of_month_continued"] is False
    assert manifest["faber_taa_retested"] is False
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
    assert all(bool_text(row["promotion_eligibility"]) is False for row in rows)
    assert all(bool_text(row["paper_forward_eligibility"]) is False for row in rows)
    assert all(bool_text(row["candidate_exhaustive_eligibility"]) is False for row in rows)


def test_row_results_have_expected_roles_labels_and_event_fields() -> None:
    manifest = load_manifest()
    rows = load_rows()

    assert manifest["data_blocked_row_count"] == 0
    assert {row["variant_id"] for row in rows} == set(EXPECTED_VARIANTS)
    assert {row["variant_role"] for row in rows} == {"source_primary", "timing_sanity", "control"}
    assert {row["research_label"] for row in rows} <= {
        "public_source_coppock_curve_primary",
        "public_source_coppock_curve_timing_sanity",
        "public_source_coppock_curve_control_only",
        "public_source_coppock_curve_sparse_context_only",
    }
    assert {row["symbols_used"] for row in rows} <= {"SPY", "BIL", "SPY|BIL"}
    assert manifest["results_interpretable"] is True
    assert manifest["usable_diagnostic_evidence"] is True
    assert isinstance(manifest["primary_row_numeric_criteria_pass"], bool)
    assert manifest["positive_zero_cross_entry_count"] >= 0
    assert manifest["negative_zero_cross_exit_count"] >= 0
    assert manifest["completed_round_trip_event_count"] >= 0
    primary = next(row for row in rows if row["variant_role"] == "source_primary")
    assert primary["formula_status"] == "coppock_roc14_plus_roc11_wma10_completed_monthly_adjusted_close"
    assert primary["roc_periods"] == "14|11"
    assert primary["wma_smoothing_period"] == "10"
    assert primary["signal_threshold"] == "0.0"
    assert int(primary["positive_zero_cross_entry_count"]) == manifest["positive_zero_cross_entry_count"]
    assert int(primary["completed_round_trip_event_count"]) == manifest["completed_round_trip_event_count"]


def test_exposure_and_cash_bil_invariants_in_outputs() -> None:
    manifest = load_manifest()
    weights = pd.read_csv(EVIDENCE / "daily_target_weights.csv")
    rows = load_rows()

    assert manifest["invariant_failure_count"] == 0
    assert manifest["exposure_invariant_passed"] is True
    assert manifest["max_daily_exposure"] <= 1.000001
    assert manifest["max_daily_weight_sum"] <= 1.000001
    assert weights["weight_sum"].max() <= 1.000001
    assert weights["risky_exposure"].max() <= 1.000001
    assert weights[["SPY", "BIL"]].min().min() >= -1e-9
    assert not weights[["SPY", "BIL", "weight_sum"]].isna().any().any()
    assert all(bool_text(row["exposure_invariant_pass"]) is True for row in rows)
    assert all(int(float(row["weight_sum_violation_count"])) == 0 for row in rows)
    assert all(int(float(row["negative_weight_violation_count"])) == 0 for row in rows)
    assert all(int(float(row["nan_weight_count"])) == 0 for row in rows)
    assert all(int(float(row["impossible_cash_and_risky_exposure_days"])) == 0 for row in rows)


def test_similarity_sparse_and_exit_caveat_reports_are_carried_forward() -> None:
    manifest = load_manifest()
    sparse = (EVIDENCE / "sparse_signal_adequacy_report.md").read_text(encoding="utf-8")
    similarity = (EVIDENCE / "similarity_risk_report.md").read_text(encoding="utf-8")
    caveat = (EVIDENCE / "sell_exit_caveat_carry_forward_report.md").read_text(encoding="utf-8")

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
    assert manifest["specific_duplicate_or_do_not_retest_match_discovered"] is False
    assert manifest["sell_exit_caveat_preserved"] is True
    assert "Completed round-trip events" in sparse
    assert "spy200d_trend_control" in similarity
    assert "original use was mainly buy-signal focused" in caveat


def test_monthly_zero_cross_event_translation_is_no_lookahead() -> None:
    dates = pd.bdate_range("2020-01-01", "2020-05-15")
    monthly = pd.DataFrame(
        {
            "signal_month": ["2020-01", "2020-02", "2020-03", "2020-04"],
            "previous_coppock": [-1.0, 1.0, 0.5, -0.5],
            "coppock": [1.0, 0.5, -0.5, 0.75],
            "positive_zero_cross": [True, False, False, True],
            "negative_zero_cross": [False, False, True, False],
        },
        index=pd.to_datetime(["2020-01-31", "2020-02-28", "2020-03-31", "2020-04-30"]),
    )

    events = coppock_events(dates, monthly)
    primary_targets = target_map_from_events(events, pd.Timestamp(dates[0]), delayed=False)
    delayed_targets = target_map_from_events(events, pd.Timestamp(dates[0]), delayed=True)

    assert events[0]["signal_type"] == "positive_zero_cross_entry"
    assert events[0]["signal_close_date"] == "2020-01-31"
    assert events[0]["primary_effective_date"] == "2020-02-03"
    assert events[0]["timing_sanity_effective_date"] == "2020-03-02"
    assert events[1]["signal_type"] == "negative_zero_cross_exit"
    assert events[1]["primary_effective_date"] == "2020-04-01"
    assert primary_targets[pd.Timestamp("2020-01-01")] == {"SPY": 0.0, "BIL": 1.0}
    assert primary_targets[pd.Timestamp("2020-02-03")] == {"SPY": 1.0, "BIL": 0.0}
    assert primary_targets[pd.Timestamp("2020-04-01")] == {"SPY": 0.0, "BIL": 1.0}
    assert delayed_targets[pd.Timestamp("2020-03-02")] == {"SPY": 1.0, "BIL": 0.0}


def test_required_evidence_files_and_next_action() -> None:
    manifest = load_manifest()
    consistency = load_consistency()
    required = consistency["required_files"]

    assert manifest["next_action"] == "audit_public_source_coppock_curve_bounded_bt_results"
    assert all(required.values())
    for filename in required:
        assert (EVIDENCE / filename).exists(), filename
