from __future__ import annotations

import csv
import json

import numpy as np
import pandas as pd

from strategy_lab.research_os.research import (
    native_etf_two_candidate_final_robustness_v1 as robustness,
)


def rows(name: str) -> list[dict[str, str]]:
    with (robustness.OUTPUT_DIR / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_exactly_two_robustness_children_with_frozen_lineage() -> None:
    trials = rows("trial_ledger.csv")
    assert len(trials) == 2
    by_strategy = {row["strategy_id"]: row for row in trials}
    assert by_strategy[robustness.VIX_ID]["trial_id"] == robustness.VIX_TRIAL
    assert by_strategy[robustness.VIX_ID]["parent_trial_id"] == robustness.VIX_PARENT_TRIAL
    assert by_strategy[robustness.FAA_ID]["trial_id"] == robustness.FAA_TRIAL
    assert by_strategy[robustness.FAA_ID]["parent_trial_id"] == robustness.FAA_PARENT_TRIAL
    assert all(row["stage"] == "robustness" for row in trials)
    assert all(row["adaptation_label"] == "robustness_variant" for row in trials)
    assert all(row["changed_fields_from_parent"] == "robustness_diagnostics_only" for row in trials)
    assert all(row["route"] == "standalone_only" for row in trials)
    assert all(row["strategy_rule_changed"] == "false" for row in trials)
    assert all(row["parameters_changed"] == "false" for row in trials)
    assert all(row["controls_changed"] == "false" for row in trials)
    assert all(row["independent_validation_claimed"] == "false" for row in trials)


def test_parent_packet_reproduces_all_scopes_within_tolerance() -> None:
    reproduction = rows("parent_reproduction_check.csv")
    assert len(reproduction) >= 10
    assert all(row["pass"] == "true" for row in reproduction)
    assert max(float(row["maximum_numeric_difference"]) for row in reproduction) <= 1e-9
    scopes = {row["scope"] for row in reproduction}
    assert "vix_fix_diagnostics.csv" in scopes
    assert "faa_diagnostics.csv" in scopes
    assert "portfolio_contribution_results.csv" in scopes
    assert "parent_trial_lineage_and_outcomes" in scopes


def test_archived_control_weights_are_used_without_recalculation() -> None:
    reconciliation = rows("archived_control_parameter_reconciliation.csv")
    assert len(reconciliation) == 9
    assert all(row["recalculated_for_robustness"] == "false" for row in reconciliation)
    assert all(row["used_for_all_robustness_results"] == "true" for row in reconciliation)
    assert all(float(row["absolute_difference"]) <= 1e-9 for row in reconciliation)
    vix_spy = next(
        row
        for row in reconciliation
        if row["strategy_id"] == robustness.VIX_ID and row["asset"] == "SPY"
    )
    assert np.isclose(float(vix_spy["archived_target_weight"]), 0.5409801876955161)


def test_cost_stress_has_only_predeclared_costs_and_all_controls() -> None:
    cost = pd.read_csv(robustness.OUTPUT_DIR / "cost_stress_results.csv")
    vix = cost.loc[cost["strategy_id"].eq(robustness.VIX_ID)]
    faa = cost.loc[cost["strategy_id"].eq(robustness.FAA_ID)]
    assert set(vix["cost_bps_one_way"]) == set(robustness.VIX_COSTS)
    assert set(faa["cost_bps_one_way"]) == set(robustness.FAA_COSTS)
    assert set(vix["series_id"]) == {robustness.VIX_ID, *robustness.exploration.VIX_CONTROLS}
    assert set(faa["series_id"]) == {robustness.FAA_ID, *robustness.exploration.FAA_CONTROLS}
    assert vix["invariant_pass"].all()
    assert faa["invariant_pass"].all()


def test_all_rolling_windows_and_bootstrap_comparisons_are_retained() -> None:
    rolling36 = pd.read_csv(robustness.OUTPUT_DIR / "rolling_36_month_results.csv")
    rolling60 = pd.read_csv(robustness.OUTPUT_DIR / "rolling_60_month_results.csv")
    assert len(rolling36) > 700
    assert len(rolling60) > 600
    assert rolling36["unfavorable_window_retained"].all()
    assert rolling60["unfavorable_window_retained"].all()
    bootstrap = pd.read_csv(robustness.OUTPUT_DIR / "paired_block_bootstrap_results.csv")
    assert len(bootstrap) == 5
    assert set(bootstrap["resamples"]) == {5000}
    assert set(bootstrap["block_length_months"]) == {12}
    assert set(bootstrap["deterministic_seed"]) == {20260730}
    assert bootstrap["paired_cross_series_dependence_preserved"].all()


def test_neutralizations_replace_returns_without_deleting_observations() -> None:
    neutral = pd.read_csv(
        robustness.OUTPUT_DIR / "month_and_year_neutralization_results.csv"
    )
    assert len(neutral) == 6
    assert set(neutral.groupby("strategy_id").size()) == {3}
    assert not neutral["observations_deleted"].any()
    assert not neutral["canonical_series_modified"].any()
    assert not neutral["used_for_strategy_change"].any()
    assert neutral["material_advantage_vs_named_control"].all()
    assert not neutral["static_control_dominates"].any()


def test_vix_episode_leave_one_out_is_single_episode_only() -> None:
    inventory = pd.read_csv(
        robustness.OUTPUT_DIR / "vix_fix_defensive_episode_inventory.csv"
    )
    leave_one = pd.read_csv(
        robustness.OUTPUT_DIR / "vix_fix_leave_one_episode_out_results.csv"
    )
    summary = pd.read_csv(
        robustness.OUTPUT_DIR / "vix_fix_leave_one_episode_out_summary.csv"
    ).iloc[0]
    assert len(inventory) == len(leave_one) == int(summary["completed_defensive_episode_count"])
    assert len(inventory) > 100
    assert not inventory["combinations_removed"].any()
    assert leave_one["all_other_signals_and_execution_preserved"].all()
    assert leave_one["cost_model_preserved"].all()
    assert float(summary["fraction_materially_better_than_close_only"]) >= 0.75


def test_faa_attribution_and_concentration_cover_frozen_universe() -> None:
    assets = pd.read_csv(
        robustness.OUTPUT_DIR / "faa_asset_selection_and_contribution.csv"
    )
    asset_rows = assets.loc[assets["row_type"].eq("asset")]
    summary = assets.loc[assets["row_type"].eq("summary")].iloc[0]
    assert set(asset_rows["asset"]) == set(robustness.exploration.FAA_UNIVERSE)
    assert np.isclose(asset_rows["selection_frequency"].sum(), 3.0)
    assert float(
        summary[
            "largest_positive_asset_contribution_fraction_of_positive_candidate_minus_return_only"
        ]
    ) <= 0.50
    components = pd.read_csv(robustness.OUTPUT_DIR / "faa_component_attribution.csv")
    assert set(components["comparison_id"]) == {
        robustness.FAA_NAMED,
        robustness.FAA_ATTRIBUTION,
        robustness.FAA_STATIC,
    }
    assert {
        "full_period",
        "chronological_quarter",
        "calendar_year",
        "rolling_36_month",
        "rolling_60_month",
    }.issubset(set(components["period_type"]))


def test_outcomes_match_frozen_robustness_gates() -> None:
    outcome = {row["strategy_id"]: row for row in rows("outcome_summary.csv")}
    assert outcome[robustness.VIX_ID]["outcome"] == "robustness_mixed"
    assert outcome[robustness.VIX_ID]["failure_reason"] == "period_instability"
    assert outcome[robustness.FAA_ID]["outcome"] == "robustness_positive"
    assert outcome[robustness.FAA_ID]["failure_reason"] == ""
    assert all(row["independent_validation_claimed"] == "false" for row in outcome.values())
    assert all(row["diversifier_route_reopened"] == "false" for row in outcome.values())
    assert all(
        row["final_historical_task_for_exact_configuration"] == "true"
        for row in outcome.values()
    )


def test_entity_counts_and_protected_state_reconcile() -> None:
    funnel = json.loads(
        (robustness.OUTPUT_DIR / "cohort_funnel_counts.json").read_text()
    )
    assert funnel["existing_strategy_configurations_carried_forward"] == 2
    assert funnel["new_strategy_configurations"] == 0
    assert funnel["existing_exploration_trials_carried_forward"] == 2
    assert funnel["new_robustness_trials"] == 2
    assert funnel["validation_observations"] == 0
    assert funnel["paper_demo_observations"] == 0
    consistency = json.loads(
        (robustness.OUTPUT_DIR / "consistency_check.json").read_text()
    )
    assert consistency["overall_pass"] is True
    assert consistency["protected_state_cache_and_parent_evidence_unchanged"] is True
    assert consistency["diversifier_routes_remain_closed"] is True


def test_all_required_outputs_exist() -> None:
    assert all((robustness.OUTPUT_DIR / name).is_file() for name in robustness.REQUIRED_FILES)
