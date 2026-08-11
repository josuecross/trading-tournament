from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from strategy_lab.research_os.research import (
    accepted_47_source_backed_exploration_batch_v2 as exploration,
)
from strategy_lab.research_os.research import (
    accepted_47_source_backed_v2_two_candidate_final_robustness_v1 as robustness,
)


def read_csv(name: str) -> pd.DataFrame:
    return pd.read_csv(robustness.OUTPUT_DIR / name, keep_default_na=False)


def test_parent_reproduction_gate_is_exact_for_both_candidates() -> None:
    rows = read_csv("parent_reproduction_check.csv")
    assert rows["pass"].astype(str).str.lower().eq("true").all()
    assert (pd.to_numeric(rows["mismatch_count"]) == 0).all()
    assert (pd.to_numeric(rows["maximum_numeric_difference"]) <= 1e-9).all()
    scopes = set(rows["scope"])
    assert f"candidate_reproduction_gate:{robustness.MCA_ID}" in scopes
    assert f"candidate_reproduction_gate:{robustness.HYG_ID}" in scopes


def test_parent_5bps_metrics_reproduce_requested_values() -> None:
    parent = pd.read_csv(exploration.OUTPUT_DIR / "all_trial_results.csv")
    rows = parent[parent["cost_bps_one_way"].eq(5.0)].set_index("strategy_id")
    assert rows.loc[robustness.MCA_ID, "cagr"] == pytest.approx(0.08154376388908902)
    assert rows.loc[robustness.MCA_ID, "sharpe_ratio"] == pytest.approx(0.8568586551210704)
    assert rows.loc[robustness.HYG_ID, "cagr"] == pytest.approx(0.12052943438830122)
    assert rows.loc[robustness.HYG_ID, "turnover"] == pytest.approx(169.0)


def test_mca_formula_fixture_and_zero_dispersion_guard() -> None:
    assert exploration.formula_fixture_result()["pass"]
    correlation = np.full((3, 3), 0.2)
    np.fill_diagonal(correlation, 1.0)
    with pytest.raises(ValueError, match="dispersion"):
        exploration.minimum_correlation_from_matrix(
            correlation, np.asarray([0.1, 0.2, 0.3])
        )


def test_hyg_ema_seed_and_recurrence_remain_frozen() -> None:
    index = pd.bdate_range("2024-01-01", periods=101)
    values = pd.Series(np.arange(1.0, 102.0), index=index)
    ema = exploration.sma_seeded_ema(values, 100)
    seed = float(values.iloc[:100].mean())
    assert ema.first_valid_index() == index[99]
    assert ema.iloc[99] == seed
    assert ema.iloc[100] == pytest.approx((2.0 / 101.0) * 101.0 + (99.0 / 101.0) * seed)


def test_chronological_quarters_are_complete_and_deterministic() -> None:
    rows = read_csv("chronological_quarter_results.csv")
    for strategy_id in (robustness.MCA_ID, robustness.HYG_ID):
        subset = rows[rows["strategy_id"].eq(strategy_id)]
        assert set(subset["period"]) == {
            "chronological_quarter_1",
            "chronological_quarter_2",
            "chronological_quarter_3",
            "chronological_quarter_4",
        }
        assert subset["unfavorable_result_retained"].astype(str).str.lower().eq("true").all()


def test_rolling_windows_and_summaries_retain_all_comparisons() -> None:
    rows36 = read_csv("rolling_36_month_results.csv")
    rows60 = read_csv("rolling_60_month_results.csv")
    summary = read_csv("rolling_window_summary.csv")
    assert len(rows36) > len(summary)
    assert len(rows60) > len(summary)
    assert set(summary["window_months"]) == {36, 60}
    assert summary["unfavorable_windows_retained"].astype(str).str.lower().eq("true").all()


def test_concentration_and_neutralization_are_frozen_without_deletion() -> None:
    concentration = read_csv("monthly_excess_concentration.csv")
    neutral = read_csv("neutralization_results.csv")
    assert concentration["observation_deleted"].astype(str).str.lower().eq("false").all()
    assert set(neutral["scenario"]) == {
        "neutralize_strongest_positive_month",
        "neutralize_three_strongest_positive_months",
        "neutralize_strongest_positive_calendar_year",
    }
    assert neutral["observations_deleted"].astype(str).str.lower().eq("false").all()
    assert neutral["canonical_returns_modified"].astype(str).str.lower().eq("false").all()


def test_bootstrap_is_deterministic_and_uses_frozen_parameters() -> None:
    rows = read_csv("paired_block_bootstrap_results.csv")
    assert len(rows) == 4
    assert (rows["moving_block_length_months"] == 12).all()
    assert (rows["resamples"] == 5000).all()
    assert (rows["deterministic_seed"] == 20260806).all()
    index = pd.period_range("2010-01", periods=48, freq="M")
    synthetic = pd.DataFrame(
        {
            robustness.MCA_ID: np.linspace(-0.02, 0.03, 48),
            exploration.MCA_NAMED: np.linspace(-0.025, 0.025, 48),
            exploration.MCA_STATIC: np.linspace(-0.018, 0.022, 48),
        },
        index=index,
    )
    first = robustness.paired_moving_block_bootstrap(
        robustness.MCA_ID, synthetic, resamples=50, seed=20260806
    )
    second = robustness.paired_moving_block_bootstrap(
        robustness.MCA_ID, synthetic, resamples=50, seed=20260806
    )
    assert first == second


def test_mca_asset_concentration_is_cap_free_and_below_specific_thresholds() -> None:
    rows = read_csv("mca_asset_and_weight_concentration.csv")
    details = rows[rows["record_type"].eq("asset_detail")]
    summary = rows[rows["record_type"].eq("concentration_summary")].iloc[0]
    assert set(details["asset"]) == set(exploration.MCA_RISK)
    assert float(summary["strongest_asset_share_of_positive_excess"]) <= 0.60
    assert float(summary["strongest_calendar_year_share_of_positive_excess"]) <= 0.60
    assert float(summary["cap_free_maximum_single_asset_target"]) > 0.0


def test_hyg_episode_inventory_and_leave_one_out_are_complete() -> None:
    inventory = read_csv("hyg_defensive_episode_inventory.csv")
    episodes = inventory[inventory["episode_id"].ne("")]
    leave = read_csv("hyg_leave_one_episode_out_results.csv")
    summary = read_csv("hyg_leave_one_episode_out_summary.csv").iloc[0]
    assert len(episodes) == len(leave) == int(summary["episode_count"])
    assert (
        pd.to_datetime(episodes["SPY_reentry_execution_date"])
        > pd.to_datetime(episodes["BIL_entry_execution_date"])
    ).all()
    assert leave["combinations_of_episodes_removed"].astype(str).str.lower().eq("false").all()
    assert float(summary["fraction_still_materially_better_than_SPY_EMA100"]) >= 0.75


def test_turnover_cost_and_entity_counts_reconcile() -> None:
    turnover = read_csv("turnover_cost_reconciliation.csv")
    assert turnover["cost_charged_once"].astype(str).str.lower().eq("true").all()
    funnel = json.loads((robustness.OUTPUT_DIR / "cohort_funnel_counts.json").read_text())
    trials = read_csv("trial_ledger.csv")
    benchmarks = read_csv("benchmark_reference_log.csv")
    assert len(trials) == funnel["new_robustness_trials"] == 2
    assert len(benchmarks) == funnel["benchmark_references_carried_forward"] == 10
    assert funnel["new_strategy_configurations"] == 0
    assert funnel["paper_demo_observations"] == 0


def test_outcomes_next_action_and_protected_state_are_exact() -> None:
    outcomes = read_csv("outcome_summary.csv")
    actions = read_csv("next_actions.csv")
    consistency = json.loads((robustness.OUTPUT_DIR / "consistency_check.json").read_text())
    assert set(outcomes["outcome"]) == {"robustness_mixed"}
    assert set(outcomes["failure_reason"]) == {"concentration_risk"}
    assert actions.iloc[0]["exact_next_action"] == (
        "direction_owner_review_source_backed_v2_robustness_yield_and_discovery_model_v1"
    )
    assert consistency["overall_pass"]
    assert consistency["protected_state_cache_source_parent_and_observations_unchanged"]
