from __future__ import annotations

import csv
import json

import pytest
import yaml

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.research import (
    kaufman_breakout_diversifier_robustness_v1 as task,
)


OUTPUT = ROOT / "evidence" / "robustness" / task.TASK_ID / "latest"


@pytest.fixture(scope="module", autouse=True)
def evidence_ready() -> None:
    assert (OUTPUT / "consistency_check.json").exists()


def rows(name: str) -> list[dict[str, str]]:
    with (OUTPUT / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def json_payload(name: str) -> dict:
    return json.loads((OUTPUT / name).read_text(encoding="utf-8"))


def test_exact_outputs_and_entity_counts() -> None:
    assert {path.name for path in OUTPUT.iterdir()} == task.REQUIRED_OUTPUTS
    manifest = yaml.safe_load((OUTPUT / "robustness_manifest.yaml").read_text())
    assert manifest["strategy_id"] == task.STRATEGY_ID
    assert manifest["trial_id"] == task.TRIAL_ID
    assert manifest["existing_strategy_configurations"] == 1
    assert manifest["new_strategy_configurations"] == 0
    assert manifest["existing_exploration_trials_carried_forward"] == 2
    assert manifest["new_robustness_trials"] == 1
    assert manifest["benchmark_references"] == 6
    assert manifest["process_tasks"] == 1
    assert manifest["data_capability_tasks"] == 0
    assert manifest["paper_demo_observations"] == 0


def test_one_robustness_child_and_no_configuration_change() -> None:
    strategy = rows("strategy_cards.csv")
    trial = rows("trial_ledger.csv")
    assert len(strategy) == len(trial) == 1
    assert strategy[0]["approved_route"] == "20pct_diversifier_only"
    assert strategy[0]["authoritative_standalone_outcome"] == "closed_exploration"
    assert (
        strategy[0]["exploratory_diversifier_outcome"]
        == "exploratory_followup_candidate_diversifier"
    )
    assert trial[0]["trial_id"] == task.TRIAL_ID
    assert trial[0]["parent_trial_id"] == task.PARENT_TRIAL_ID
    assert trial[0]["adaptation_label"] == "robustness_variant"
    assert trial[0]["changed_fields_from_parent"] == "robustness_diagnostics_only"
    for field in (
        "strategy_rule_changed",
        "channel_formula_changed",
        "period_changed",
        "instruments_changed",
        "execution_changed",
        "candidate_sleeve_weight_changed",
        "frozen_reference_changed",
        "controls_changed",
        "optimization_performed",
        "result_driven_parameter_change",
        "independent_validation_claimed",
    ):
        assert trial[0][field] == "false"


def test_complete_parent_reproduction_passes() -> None:
    reproduction = rows("reproduction_check.csv")
    assert reproduction
    assert {row["pass"] for row in reproduction} == {"true"}
    numeric = [abs(float(row["difference"])) for row in reproduction if row["difference"]]
    assert max(numeric) <= task.REPRODUCTION_TOLERANCE
    scopes = {row["scope"] for row in reproduction}
    assert {
        "full_period",
        "chronological_halves",
        "rolling_36_month",
        "rolling_60_month",
        "turnover_and_cost",
        "invariants",
    } <= scopes


def test_cost_stress_is_complete_and_not_new_trials() -> None:
    costs = rows("cost_stress_results.csv")
    assert len(costs) == 35
    assert {float(row["cost_bps"]) for row in costs} == {
        0.0,
        5.0,
        10.0,
        15.0,
        20.0,
    }
    assert {row["portfolio_id"] for row in costs} == set(
        task.PORTFOLIO_IDS.values()
    )
    assert {row["entity_type"] for row in costs} == {
        "portfolio_robustness_diagnostic"
    }
    assert {row["period_independence"] for row in costs} == {
        "same_viewed_period_not_independent_validation"
    }


def test_partitions_years_and_start_dates_are_predeclared() -> None:
    quarters = rows("chronological_quarter_results.csv")
    years = rows("calendar_year_results.csv")
    starts = rows("start_date_sensitivity.csv")
    assert len(quarters) == 28
    assert {
        row["period"] for row in quarters
    } == {
        "chronological_quarter_1",
        "chronological_quarter_2",
        "chronological_quarter_3",
        "chronological_quarter_4",
    }
    assert years
    assert {int(row["calendar_year"]) for row in years} == set(range(2011, 2026))
    assert len(starts) == 42
    assert {int(row["requested_start_year"]) for row in starts} == set(
        task.START_YEARS
    )
    assert {row["fixed_end_date"] for row in starts} == {"2026-06-18"}
    assert {row["start_selected_from_performance"] for row in starts} == {"false"}


def test_every_rolling_window_is_retained() -> None:
    rolling36 = rows("rolling_36_month_results.csv")
    rolling60 = rows("rolling_60_month_results.csv")
    assert len(rolling36) == 156
    assert len(rolling60) == 132
    assert {row["sealed_untouched_or_validation"] for row in rolling36} == {
        "false"
    }
    assert {row["sealed_untouched_or_validation"] for row in rolling60} == {
        "false"
    }


def test_concentration_diagnostics_do_not_modify_canonical_returns() -> None:
    concentration = rows("excess_return_concentration.csv")
    assert len(concentration) == 3
    assert {row["comparator_portfolio_id"] for row in concentration} == {
        task.REFERENCE_PORTFOLIO_ID,
        task.DONCHIAN_PORTFOLIO_ID,
        task.EXPOSURE_PORTFOLIO_ID,
    }
    assert {row["canonical_return_series_modified"] for row in concentration} == {
        "false"
    }
    assert {row["used_for_strategy_change"] for row in concentration} == {
        "false"
    }


def test_paired_bootstrap_is_frozen_and_deterministic() -> None:
    bootstrap = rows("bootstrap_results.csv")
    assert len(bootstrap) == 3
    assert {int(row["moving_block_length_months"]) for row in bootstrap} == {12}
    assert {int(row["resamples"]) for row in bootstrap} == {5000}
    assert {int(row["deterministic_seed"]) for row in bootstrap} == {20260727}
    assert {
        row["paired_cross_portfolio_dependence_preserved"] for row in bootstrap
    } == {"true"}
    for row in bootstrap:
        for field in (
            "probability_candidate_higher_sharpe",
            "probability_candidate_less_severe_maximum_drawdown",
            "probability_positive_candidate_CAGR_difference",
        ):
            assert 0.0 <= float(row[field]) <= 1.0


def test_turnover_costs_and_all_invariants_pass() -> None:
    turnover = rows("turnover_cost_reconciliation.csv")
    invariants = rows("invariant_results.csv")
    assert len(turnover) == len(invariants) == 35
    assert {row["inner_and_outer_costs_charged_once"] for row in turnover} == {
        "true"
    }
    assert {row["daily_fixed_weight_return_blend_used"] for row in turnover} == {
        "false"
    }
    assert {row["invariant_pass"] for row in invariants} == {"true"}
    assert {row["stale_weight_forward_fill_used"] for row in invariants} == {
        "false"
    }
    assert all(
        float(row["maximum_gross_exposure"]) <= 1.0 + 1e-9
        and float(row["maximum_daily_weight_sum"]) <= 1.0 + 1e-9
        for row in invariants
    )


def test_outcome_is_robustness_only_and_exactly_routed() -> None:
    outcome = rows("outcome_summary.csv")[0]
    assert outcome["outcome"] in {
        "robustness_positive",
        "robustness_mixed",
        "robustness_failed",
        "robustness_blocked",
    }
    assert outcome["independent_validation_claimed"] == "false"
    assert outcome["paper_demo_eligibility_supported"] == "false"
    expected_actions = {
        "robustness_positive": task.NEXT_POSITIVE,
        "robustness_mixed": task.NEXT_MIXED,
        "robustness_failed": task.NEXT_FAILED,
        "robustness_blocked": task.NEXT_BLOCKED,
    }
    assert outcome["exact_next_action"] == expected_actions[outcome["outcome"]]
    if outcome["outcome"] == "robustness_positive":
        assert outcome["outcome_interpretation"] == (
            "ready_for_prospective_validation_design"
        )
        assert outcome["failure_reason"] == ""
    else:
        assert outcome["failure_reason"]


def test_prior_evidence_protected_state_and_cache_are_unchanged() -> None:
    check = json_payload("consistency_check.json")
    assert check["overall_pass"] is True
    assert check["required_outputs_exact"] is True
    assert check["standalone_evidence_unchanged"] is True
    assert check["exploration_evidence_unchanged"] is True
    assert check["protected_state_unchanged"] is True
    assert check["market_data_caches_unchanged"] is True
    assert check["prior_evidence_unchanged"] is True
    assert check["preregistration_written_before_robustness_calculation"] is True
    assert check["serial_rerun_deterministic"] is True
    assert check["provider_access"] is False
    assert check["network_access"] is False
    assert check["lifecycle_state_changed"] is False
    assert check["paper_demo_observations_created"] == 0
    assert check["parameter_search_performed"] is False
    assert check["broker_orders"] == 0
    assert check["real_money_actions"] == 0
