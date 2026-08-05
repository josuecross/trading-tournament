from __future__ import annotations

import csv
import json

import pandas as pd

from strategy_lab.research_os.research import (
    native_etf_v3_two_candidate_final_robustness_v1 as robustness,
)


def rows(name: str) -> list[dict[str, str]]:
    with (robustness.OUTPUT_DIR / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_exactly_two_frozen_robustness_children() -> None:
    trials = rows("trial_ledger.csv")
    assert len(trials) == 2
    by_strategy = {row["strategy_id"]: row for row in trials}
    assert by_strategy[robustness.PERCENTILE_ID]["trial_id"] == robustness.PERCENTILE_TRIAL
    assert by_strategy[robustness.PERCENTILE_ID]["parent_trial_id"] == robustness.PERCENTILE_PARENT_TRIAL
    assert by_strategy[robustness.GROWTH_ID]["trial_id"] == robustness.GROWTH_TRIAL
    assert by_strategy[robustness.GROWTH_ID]["parent_trial_id"] == robustness.GROWTH_PARENT_TRIAL
    assert all(row["stage"] == "robustness" for row in trials)
    assert all(row["adaptation_label"] == "robustness_variant" for row in trials)
    assert all(row["changed_fields_from_parent"] == "robustness_diagnostics_only" for row in trials)
    assert all(row["route"] == "standalone_only" for row in trials)
    assert all(row["source_rule_changed"] == "false" for row in trials)
    assert all(row["parameters_changed"] == "false" for row in trials)
    assert all(row["controls_added"] == "false" for row in trials)
    assert all(row["diversifier_route_reopened"] == "false" for row in trials)


def test_parent_packet_reproduces_before_robustness() -> None:
    reproduction = rows("parent_reproduction_check.csv")
    assert len(reproduction) >= 20
    assert all(row["pass"] == "true" for row in reproduction)
    assert max(float(row["maximum_numeric_difference"]) for row in reproduction) <= 1e-9
    scopes = {row["scope"] for row in reproduction}
    assert "percentile_channel_signal_ledger.csv" in scopes
    assert "growth_inflation_daily_regime_ledger.csv" in scopes
    assert "parent_trial_lineage_and_outcomes" in scopes


def test_cost_stress_grid_and_controls_are_frozen() -> None:
    cost = pd.read_csv(robustness.OUTPUT_DIR / "cost_stress_results.csv")
    percentile = cost.loc[cost["strategy_id"].eq(robustness.PERCENTILE_ID)]
    growth = cost.loc[cost["strategy_id"].eq(robustness.GROWTH_ID)]
    assert set(percentile["cost_bps_one_way"]) == set(robustness.PERCENTILE_COSTS)
    assert set(growth["cost_bps_one_way"]) == set(robustness.GROWTH_COSTS)
    assert set(percentile["series_id"]) == {robustness.PERCENTILE_ID, *robustness.exploration.PERCENTILE_CONTROLS}
    assert set(growth["series_id"]) == {robustness.GROWTH_ID, *robustness.exploration.GROWTH_CONTROLS}
    assert percentile["invariant_pass"].all()
    assert growth["invariant_pass"].all()


def test_rolling_windows_and_bootstrap_retain_all_comparisons() -> None:
    rolling36 = pd.read_csv(robustness.OUTPUT_DIR / "rolling_36_month_results.csv")
    rolling60 = pd.read_csv(robustness.OUTPUT_DIR / "rolling_60_month_results.csv")
    assert len(rolling36) > 500
    assert len(rolling60) > 400
    assert rolling36["unfavorable_window_retained"].all()
    assert rolling60["unfavorable_window_retained"].all()
    bootstrap = pd.read_csv(robustness.OUTPUT_DIR / "paired_block_bootstrap_results.csv")
    assert len(bootstrap) == len(robustness.PERCENTILE_DECISIVE) + len(robustness.GROWTH_DECISIVE)
    assert set(bootstrap["resamples"]) == {5000}
    assert set(bootstrap["block_length_months"]) == {12}
    assert set(bootstrap["deterministic_seed"]) == {20260804}
    assert bootstrap["paired_cross_series_dependence_preserved"].all()


def test_month_and_year_neutralization_replaces_without_deletion() -> None:
    neutral = pd.read_csv(robustness.OUTPUT_DIR / "month_and_year_neutralization_results.csv")
    assert len(neutral) == 6
    assert set(neutral.groupby("strategy_id").size()) == {3}
    assert not neutral["observations_deleted"].any()
    assert not neutral["canonical_series_modified"].any()
    assert not neutral["used_for_strategy_change"].any()


def test_percentile_component_attribution_is_complete() -> None:
    assets = pd.read_csv(robustness.OUTPUT_DIR / "percentile_channel_asset_contribution.csv")
    assert set(assets["asset"]) == set(robustness.exploration.PERCENTILE_UNIVERSE)
    assert assets["selection_frequency"].between(0.0, 1.0).all()
    horizons = pd.read_csv(robustness.OUTPUT_DIR / "percentile_channel_horizon_diagnostics.csv")
    assert set(horizons["asset"]) == set(robustness.exploration.PERCENTILE_RISKY)
    assert set(horizons["horizon_sessions"]) == {60, 120, 180, 252}
    assert len(horizons) == 16
    assert not horizons["horizon_removed_or_changed"].any()


def test_growth_regimes_episodes_and_counterfactuals_are_complete() -> None:
    regimes = pd.read_csv(robustness.OUTPUT_DIR / "growth_inflation_regime_attribution.csv")
    regime_rows = regimes.loc[regimes["row_type"].eq("regime")]
    assert set(regime_rows["regime"]) == set(robustness.REGIME_BY_ASSET.values())
    episodes = pd.read_csv(robustness.OUTPUT_DIR / "growth_inflation_episode_inventory.csv")
    assert len(episodes) > 100
    assert not episodes["episode_removed"].any()
    neutral = pd.read_csv(robustness.OUTPUT_DIR / "growth_inflation_episode_neutralization.csv")
    assert set(neutral["neutralized_episode_count"]) == {1, 3}
    assert not neutral["observations_deleted"].any()
    assert not neutral["strategy_changed"].any()


def test_outcomes_use_only_allowed_final_robustness_states() -> None:
    outcome = rows("outcome_summary.csv")
    assert len(outcome) == 2
    assert {row["outcome"] for row in outcome} <= {
        "robustness_positive", "robustness_mixed", "robustness_failed", "robustness_blocked"
    }
    assert all(row["independent_validation_claimed"] == "false" for row in outcome)
    assert all(row["diversifier_route_reopened"] == "false" for row in outcome)
    assert all(row["paper_demo_eligibility_granted_inside_task"] == "false" for row in outcome)
    assert all(row["final_historical_task_for_exact_configuration"] == "true" for row in outcome)


def test_entity_counts_and_protected_state_reconcile() -> None:
    funnel = json.loads((robustness.OUTPUT_DIR / "cohort_funnel_counts.json").read_text())
    assert funnel["existing_strategy_configurations_carried_forward"] == 2
    assert funnel["new_strategy_configurations"] == 0
    assert funnel["existing_exploration_trials_carried_forward"] == 2
    assert funnel["new_robustness_trials"] == 2
    assert funnel["validation_observations"] == 0
    assert funnel["paper_demo_observations"] == 0
    consistency = json.loads((robustness.OUTPUT_DIR / "consistency_check.json").read_text())
    assert consistency["overall_pass"] is True
    assert consistency["protected_state_cache_parent_evidence_and_observations_unchanged"] is True
    assert consistency["diversifier_routes_remain_closed"] is True


def test_all_required_outputs_exist() -> None:
    assert all((robustness.OUTPUT_DIR / name).is_file() for name in robustness.REQUIRED_FILES)
