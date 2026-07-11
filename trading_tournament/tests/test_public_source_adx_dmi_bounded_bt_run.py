from __future__ import annotations

import csv
import json
from pathlib import Path

import pandas as pd

from strategy_lab.research_os.research.public_source_adx_dmi_bounded_bt_run import (
    EXPECTED_VARIANTS,
    FORMULA_CONTRACT_VERSION,
    LANE_ID,
    adx_dmi_frame,
    one_extra_bar_delayed_targets,
    primary_adx_targets,
)


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "research_recovery" / "public_source_adx_dmi_bounded_bt_run" / "latest"


def load_manifest() -> dict:
    return json.loads((EVIDENCE / "public_source_adx_dmi_bounded_bt_run_manifest.json").read_text(encoding="utf-8"))


def load_consistency() -> dict:
    return json.loads(
        (EVIDENCE / "public_source_adx_dmi_bounded_bt_run_consistency_check.json").read_text(encoding="utf-8")
    )


def load_rows() -> list[dict[str, str]]:
    with (EVIDENCE / "row_level_results.csv").open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def bool_text(value: str) -> bool:
    return value == "True"


def test_manifest_exact_bounded_lane_run_contract() -> None:
    manifest = load_manifest()
    consistency = load_consistency()

    assert manifest["public_source_adx_dmi_bounded_bt_lane_run"] is True
    assert manifest["source_id"] == "adx_dmi_trend_strength_crossover"
    assert manifest["family_id"] == "equity_index_adx_dmi_trend_strength"
    assert manifest["lane_id"] == LANE_ID
    assert manifest["source_design_run_ready"] is True
    assert manifest["source_design_next_action_correct"] is True
    assert manifest["formula_contract_complete"] is True
    assert manifest["formula_contract_version"] == FORMULA_CONTRACT_VERSION
    assert manifest["formula_contract_used_exactly"] is True
    assert manifest["indicator_formula_implemented"] is True
    assert manifest["indicator_parameters_source_backed"] is True
    assert manifest["dmi_adx_period"] == 14
    assert manifest["adx_threshold"] == 25.0
    assert manifest["parameters_tuned"] is False
    assert manifest["variant_count_planned"] == 5
    assert manifest["variant_count_evaluated"] == 5
    assert manifest["approved_variant_ids"] == list(EXPECTED_VARIANTS)
    assert set(manifest["evaluated_variant_ids"]) == set(EXPECTED_VARIANTS)
    assert manifest["primary_source_row_count"] == 1
    assert manifest["timing_sanity_row_count"] == 1
    assert manifest["control_row_count"] == 3
    assert manifest["methodology_patch_applied"] is True
    assert manifest["methodology_patch_id"] == "adx_dmi_true_crossover_event_patch_v1"
    assert manifest["previous_adx_dmi_run_superseded"] is True
    assert manifest["cross_fields_are_true_transition_events"] is True
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
    assert manifest["threshold_sweep_created"] is False
    assert manifest["optimization_run"] is False
    assert manifest["other_indicators_added"] is False
    assert manifest["spy200d_added_as_source_filter"] is False
    assert manifest["moving_average_filters_added"] is False
    assert manifest["volatility_filters_added"] is False
    assert manifest["stop_loss_or_profit_target_added"] is False
    assert manifest["alternate_exits_added"] is False
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


def test_row_results_have_expected_roles_labels_formula_and_events() -> None:
    manifest = load_manifest()
    rows = load_rows()

    assert manifest["data_blocked_row_count"] == 0
    assert {row["variant_id"] for row in rows} == set(EXPECTED_VARIANTS)
    assert {row["variant_role"] for row in rows} == {"source_primary", "timing_sanity", "control"}
    assert {row["research_label"] for row in rows} == {
        "public_source_adx_dmi_primary",
        "public_source_adx_dmi_timing_sanity",
        "public_source_adx_dmi_control_only",
    }
    assert {row["symbols_used"] for row in rows} <= {"SPY", "BIL", "SPY|BIL"}
    assert manifest["results_interpretable"] is True
    assert manifest["usable_diagnostic_evidence"] is True
    assert isinstance(manifest["primary_row_numeric_criteria_pass"], bool)
    assert manifest["similarity_hit_preserved"] is True
    assert manifest["similarity_hit_count"] == 12
    assert manifest["specific_duplicate_or_do_not_retest_match_discovered"] is False
    assert manifest["long_only_adaptation_caveat_carried_forward"] is True
    primary = next(row for row in rows if row["variant_role"] == "source_primary")
    assert primary["formula_contract_version"] == FORMULA_CONTRACT_VERSION
    assert primary["formula_status"] == "frozen_wilder_adx_dmi_contract_v1_exact"
    assert primary["dmi_adx_period"] == "14"
    assert primary["adx_threshold"] == "25.0"
    assert int(float(primary["di_crossover_count"])) >= int(float(primary["adx_confirmed_entry_count"]))
    assert manifest["true_bullish_crossover_event_count"] < manifest["raw_bullish_directional_state_day_count"]
    assert manifest["true_bearish_crossover_event_count"] < manifest["raw_bearish_directional_state_day_count"]
    assert int(float(primary["adx_confirmed_entry_count"])) != manifest["raw_bullish_directional_state_day_count"]
    assert bool_text(primary["entry_exit_counts_reported"]) is True
    assert manifest["adx_alone_creates_exposure"] is False
    assert manifest["invalid_indicator_rows_signal_active"] is False


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


def test_adx_dmi_formula_and_signal_helpers_are_deterministic() -> None:
    index = pd.date_range("2024-01-01", periods=40, freq="D")
    high_values = list(range(101, 141))
    low_values = list(range(99, 139))
    close_values = list(range(100, 140))
    ohlc = pd.DataFrame(
        {
            "high": high_values,
            "low": low_values,
            "close": close_values,
            "adj_close": close_values,
        },
        index=index,
    )
    state = adx_dmi_frame(ohlc)

    assert state["positive_di"].dropna().index.min() == index[14]
    assert state["adx"].dropna().index.min() == index[27]
    assert state["positive_dm"].dropna().iloc[0] == 1.0
    assert state["negative_dm"].dropna().iloc[0] == 0.0
    assert state["adx"].dropna().iloc[-1] == 100.0
    assert state["adx"].replace([float("inf"), float("-inf")], pd.NA).dropna().shape[0] == state["adx"].dropna().shape[0]

    custom = pd.DataFrame(index=index)
    custom["positive_di"] = [pd.NA] * 5 + [10, 20, 30, 35, 40, 38, 25, 15, 10, 35, 40, 20, 15, 10, 5] + [5] * 20
    custom["negative_di"] = [pd.NA] * 5 + [20, 15, 10, 8, 7, 10, 20, 30, 35, 10, 8, 25, 30, 35, 40] + [40] * 20
    custom["adx"] = [pd.NA] * 5 + [30] * 35
    custom["valid_signal_row"] = custom[["positive_di", "negative_di", "adx"]].notna().all(axis=1)
    custom["di_bullish_state"] = (custom["positive_di"] > custom["negative_di"]) & custom["valid_signal_row"]
    custom["di_bearish_state"] = (custom["negative_di"] > custom["positive_di"]) & custom["valid_signal_row"]
    custom["bullish_cross"] = (
        custom["valid_signal_row"]
        & custom["positive_di"].shift(1).notna()
        & custom["negative_di"].shift(1).notna()
        & (custom["positive_di"] > custom["negative_di"])
        & (custom["positive_di"].shift(1) <= custom["negative_di"].shift(1))
    )
    custom["bearish_cross"] = (
        custom["valid_signal_row"]
        & custom["positive_di"].shift(1).notna()
        & custom["negative_di"].shift(1).notna()
        & (custom["negative_di"] > custom["positive_di"])
        & (custom["negative_di"].shift(1) <= custom["positive_di"].shift(1))
    )
    custom["adx_confirmed_bullish_cross"] = custom["bullish_cross"] & (custom["adx"] > 25.0) & custom["valid_signal_row"]

    primary, _events = primary_adx_targets(custom)
    delayed = one_extra_bar_delayed_targets(primary)

    assert primary.loc[index[0]].to_dict() == {"SPY": 0.0, "BIL": 1.0}
    assert primary.loc[index[6]].to_dict() == {"SPY": 1.0, "BIL": 0.0}
    assert primary.loc[index[12]].to_dict() == {"SPY": 0.0, "BIL": 1.0}
    assert primary.loc[index[14]].to_dict() == {"SPY": 1.0, "BIL": 0.0}
    assert primary.loc[index[16]].to_dict() == {"SPY": 0.0, "BIL": 1.0}
    assert delayed.loc[index[6]].to_dict() == {"SPY": 0.0, "BIL": 1.0}
    assert delayed.loc[index[7]].to_dict() == {"SPY": 1.0, "BIL": 0.0}


def test_corrected_state_table_crosses_are_true_transition_events() -> None:
    state = pd.read_csv(EVIDENCE / "adx_dmi_state_table.csv")
    valid = state[["positive_di", "negative_di", "adx"]].notna().all(axis=1)
    prior_di_valid = state["positive_di"].shift(1).notna() & state["negative_di"].shift(1).notna()
    expected_bull = (
        valid
        & prior_di_valid
        & (state["positive_di"] > state["negative_di"])
        & (state["positive_di"].shift(1) <= state["negative_di"].shift(1))
    )
    expected_bear = (
        valid
        & prior_di_valid
        & (state["negative_di"] > state["positive_di"])
        & (state["negative_di"].shift(1) <= state["positive_di"].shift(1))
    )
    actual_bull = state["bullish_cross"].astype(str).str.lower().eq("true")
    actual_bear = state["bearish_cross"].astype(str).str.lower().eq("true")
    actual_confirmed = state["adx_confirmed_bullish_cross"].astype(str).str.lower().eq("true")

    assert actual_bull.equals(expected_bull)
    assert actual_bear.equals(expected_bear)
    assert actual_confirmed.equals(expected_bull & (state["adx"] > 25.0))
    assert int(actual_bull.sum()) < int(state["di_bullish_state"].astype(str).str.lower().eq("true").sum())
    assert int(actual_bear.sum()) < int(state["di_bearish_state"].astype(str).str.lower().eq("true").sum())


def test_required_evidence_files_and_next_action() -> None:
    manifest = load_manifest()
    consistency = load_consistency()
    required = consistency["required_files"]

    assert manifest["next_action"] == "audit_public_source_adx_dmi_bounded_bt_results"
    assert all(required.values())
    for filename in required:
        assert (EVIDENCE / filename).exists(), filename
