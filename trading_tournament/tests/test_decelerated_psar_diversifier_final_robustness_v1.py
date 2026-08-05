from __future__ import annotations

import csv
import json

import yaml

from strategy_lab.research_os.research import (
    decelerated_psar_diversifier_final_robustness_v1 as task,
)


OUTPUT = task.OUTPUT_DIR


def rows(name: str) -> list[dict[str, str]]:
    with (OUTPUT / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def payload(name: str) -> dict:
    return json.loads((OUTPUT / name).read_text(encoding="utf-8"))


def test_required_outputs_and_entity_counts() -> None:
    assert {path.name for path in OUTPUT.iterdir() if path.is_file()} == (
        task.REQUIRED_OUTPUTS
    )
    manifest = yaml.safe_load(
        (OUTPUT / "robustness_manifest.yaml").read_text(encoding="utf-8")
    )
    assert manifest["existing_strategy_configurations"] == 1
    assert manifest["new_strategy_configurations"] == 0
    assert manifest["existing_exploration_trials_carried_forward"] == 2
    assert manifest["new_robustness_trials"] == 1
    assert manifest["benchmark_references"] == 6
    assert manifest["process_tasks"] == 1
    assert manifest["data_capability_tasks"] == 0
    assert manifest["paper_demo_observations"] == 0


def test_single_robustness_child_preserves_strategy_and_parent_outcomes() -> None:
    strategy = rows("strategy_cards.csv")
    trial = rows("trial_ledger.csv")
    assert len(strategy) == len(trial) == 1
    assert strategy[0]["strategy_id"] == task.STRATEGY_ID
    assert strategy[0]["new_strategy_configuration_created"] == "false"
    assert strategy[0]["standalone_outcome"] == "closed_exploration"
    assert strategy[0]["standalone_failure_reason"] == "benchmark_like_behavior"
    assert (
        strategy[0]["diversifier_exploration_outcome"]
        == "exploratory_followup_candidate_diversifier"
    )
    assert trial[0]["trial_id"] == task.TRIAL_ID
    assert trial[0]["parent_trial_id"] == task.PARENT_TRIAL_ID
    assert trial[0]["adaptation_label"] == "robustness_variant"
    assert trial[0]["changed_fields_from_parent"] == (
        "exact_exposure_control_weight_correction_and_robustness_diagnostics_only"
    )
    for field in (
        "PSAR_formula_changed",
        "AF_parameters_changed",
        "instruments_changed",
        "signal_timing_changed",
        "execution_changed",
        "candidate_sleeve_changed",
        "reference_portfolio_changed",
        "candidate_cost_model_changed",
        "optimization_performed",
        "independent_validation_claimed",
        "result_driven_strategy_change",
    ):
        assert trial[0][field] == "false"
    assert trial[0]["critical_control_weight_corrected"] == "true"


def test_complete_exploratory_child_reproduction_passes() -> None:
    reproduction = rows("reproduction_check.csv")
    assert reproduction
    assert {row["pass"] for row in reproduction} == {"true"}
    numeric = [
        abs(float(row["difference"]))
        for row in reproduction
        if row["difference"]
    ]
    assert max(numeric) <= task.REPRODUCTION_TOLERANCE
    assert {
        "full_period",
        "chronological_halves",
        "rolling_36_and_60_month_summaries",
        "reference_negative_months",
        "turnover_and_cost",
        "parent_invariants",
        "evaluation_period",
    } <= {row["scope"] for row in reproduction}


def test_exact_exposure_methodology_correction_is_frozen() -> None:
    correction = rows("exposure_control_weight_correction.csv")
    corrected = rows("corrected_control_results.csv")
    assert len(correction) == len(corrected) == 5
    assert {float(row["cost_bps"]) for row in correction} == set(task.COST_BPS)
    assert {
        row["methodology_correction"] for row in correction
    } == {"methodology_correction_to_exact_parent_exposure"}
    assert {
        float(row["approximate_SPY_weight"]) for row in correction
    } == {task.APPROXIMATE_EXPOSURE_SPY}
    assert {float(row["exact_SPY_weight"]) for row in correction} == {
        task.EXACT_EXPOSURE_SPY
    }
    assert all(
        abs(
            float(row["SPY_weight_difference"])
            - (task.EXACT_EXPOSURE_SPY - task.APPROXIMATE_EXPOSURE_SPY)
        )
        <= 1e-12
        for row in correction
    )
    assert {row["exact_control_used_for_decision"] for row in correction} == {
        "true"
    }
    assert {row["weight_selected_from_performance"] for row in correction} == {
        "false"
    }
    assert {row["portfolio_id"] for row in corrected} == {
        task.EXACT_EXPOSURE_ID
    }


def test_cost_partitions_years_and_starts_are_complete() -> None:
    cost = rows("cost_stress_results.csv")
    quarters = rows("chronological_quarter_results.csv")
    years = rows("calendar_year_results.csv")
    starts = rows("start_date_sensitivity.csv")
    assert len(cost) == len(task.PORTFOLIO_IDS) * len(task.COST_BPS)
    assert {float(row["cost_bps"]) for row in cost} == set(task.COST_BPS)
    assert len(quarters) == len(task.PORTFOLIO_IDS) * 4
    assert {row["period"] for row in quarters} == {
        "chronological_quarter_1",
        "chronological_quarter_2",
        "chronological_quarter_3",
        "chronological_quarter_4",
    }
    assert len(years) == len(task.PORTFOLIO_IDS) * 15
    assert {int(row["calendar_year"]) for row in years} == set(
        range(2011, 2026)
    )
    assert len(starts) == len(task.PORTFOLIO_IDS) * len(task.START_YEARS)
    assert {int(row["requested_start_year"]) for row in starts} == set(
        task.START_YEARS
    )
    assert {row["fixed_end_date"] for row in starts} == {"2026-06-18"}
    assert {row["start_selected_from_performance"] for row in starts} == {
        "false"
    }


def test_rolling_windows_and_unfavorable_evidence_are_retained() -> None:
    rolling36 = rows("rolling_36_month_results.csv")
    rolling60 = rows("rolling_60_month_results.csv")
    summary = rows("rolling_window_summary.csv")
    assert len(rolling36) == 155 * 3
    assert len(rolling60) == 131 * 3
    assert len(summary) == 6
    assert {row["unfavorable_window_retained"] for row in rolling36} == {
        "true"
    }
    assert {row["unfavorable_window_retained"] for row in rolling60} == {
        "true"
    }
    assert any(
        row["comparison_dominates_candidate"] == "true"
        for row in rolling36 + rolling60
    )


def test_month_and_year_neutralization_replaces_without_deleting() -> None:
    concentration = rows("monthly_excess_concentration.csv")
    neutralization = rows("month_and_year_neutralization_results.csv")
    assert len(concentration) == 191
    assert sum(row["strongest_positive_month"] == "true" for row in concentration) == 1
    assert sum(
        row["among_three_strongest_positive_months"] == "true"
        for row in concentration
    ) == 3
    assert {row["canonical_observation_deleted"] for row in concentration} == {
        "false"
    }
    assert {row["scenario"] for row in neutralization} == {
        "neutralize_strongest_positive_month",
        "neutralize_three_strongest_positive_months",
        "neutralize_strongest_additive_excess_calendar_year",
    }
    assert {row["observations_deleted"] for row in neutralization} == {"false"}
    assert {
        row["canonical_return_series_modified"] for row in neutralization
    } == {"false"}


def test_all_defensive_episodes_are_individually_rebuilt() -> None:
    inventory = rows("defensive_episode_inventory.csv")
    leave_one = rows("leave_one_defensive_episode_out_results.csv")
    summary = rows("leave_one_defensive_episode_out_summary.csv")
    assert inventory
    assert len(inventory) == len(leave_one) == int(
        summary[0]["completed_episode_count"]
    )
    assert {row["completed_episode"] for row in inventory} == {"true"}
    assert {row["all_other_states_preserved"] for row in leave_one} == {"true"}
    assert {row["outer_portfolio_rebuilt"] for row in leave_one} == {"true"}
    assert {row["cost_model_preserved"] for row in leave_one} == {"true"}
    assert {row["used_for_strategy_change"] for row in leave_one} == {"false"}


def test_paired_moving_block_bootstrap_is_frozen_and_deterministic() -> None:
    bootstrap = rows("bootstrap_results.csv")
    assert len(bootstrap) == 3
    assert {int(row["moving_block_length_months"]) for row in bootstrap} == {
        task.BLOCK_LENGTH_MONTHS
    }
    assert {int(row["resamples"]) for row in bootstrap} == {
        task.BOOTSTRAP_RESAMPLES
    }
    assert {int(row["deterministic_seed"]) for row in bootstrap} == {
        task.BOOTSTRAP_SEED
    }
    assert {
        row["paired_cross_portfolio_dependence_preserved"] for row in bootstrap
    } == {"true"}
    for row in bootstrap:
        for field in (
            "probability_candidate_higher_sharpe",
            "probability_candidate_less_severe_maximum_drawdown",
            "probability_candidate_higher_sharpe_or_less_severe_drawdown",
        ):
            assert 0.0 <= float(row[field]) <= 1.0


def test_outcome_routing_invariants_and_protected_state() -> None:
    outcome = rows("outcome_summary.csv")[0]
    check = payload("consistency_check.json")
    expected_actions = {
        "robustness_positive": task.NEXT_POSITIVE,
        "robustness_mixed": task.NEXT_MIXED,
        "robustness_failed": task.NEXT_FAILED,
        "robustness_blocked": task.NEXT_BLOCKED,
    }
    assert outcome["outcome"] in task.ALLOWED_OUTCOMES
    assert outcome["failure_reason"] in task.ALLOWED_FAILURE_REASONS
    assert outcome["exact_next_action"] == expected_actions[outcome["outcome"]]
    assert outcome["independent_validation_claimed"] == "false"
    assert outcome["paper_demo_eligibility_supported"] == "false"
    assert check["overall_pass"] is True
    assert check["required_outputs_exact"] is True
    assert check["reproduction_passed"] is True
    assert check["exposure_control_correction_passed"] is True
    assert check["all_invariants_passed"] is True
    assert check["protected_state_unchanged"] is True
    assert check["market_data_caches_unchanged"] is True
    assert check["prior_evidence_unchanged"] is True
    assert check["serial_rerun_deterministic"] is True
    assert check["network_access"] is False
    assert check["provider_access"] is False
    assert check["lifecycle_state_changed"] is False
    assert check["paper_demo_observations_created"] == 0
    assert check["broker_orders"] == 0
    assert check["real_money_actions"] == 0
    assert check["no_further_same_period_PSAR_diagnostic_authorized"] is True
