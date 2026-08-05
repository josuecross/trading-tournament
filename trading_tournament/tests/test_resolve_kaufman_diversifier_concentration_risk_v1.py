from __future__ import annotations

import csv
import json

import pytest
import yaml

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.research import (
    resolve_kaufman_diversifier_concentration_risk_v1 as task,
)


OUTPUT = ROOT / "evidence" / "robustness" / task.TASK_ID / "latest"


@pytest.fixture(scope="module", autouse=True)
def evidence_ready() -> None:
    assert (OUTPUT / "consistency_check.json").exists()


def rows(name: str) -> list[dict[str, str]]:
    with (OUTPUT / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def check() -> dict:
    return json.loads((OUTPUT / "consistency_check.json").read_text())


def test_exact_outputs_and_entity_counts() -> None:
    assert {path.name for path in OUTPUT.iterdir()} == task.REQUIRED_OUTPUTS
    manifest = yaml.safe_load((OUTPUT / "resolution_manifest.yaml").read_text())
    assert manifest["existing_strategy_configurations"] == 1
    assert manifest["new_strategy_configurations"] == 0
    assert manifest["existing_exploration_robustness_trials_carried_forward"] == 3
    assert manifest["new_robustness_trials"] == 1
    assert manifest["benchmark_references"] == 6
    assert manifest["process_tasks"] == 1
    assert manifest["data_capability_tasks"] == 0
    assert manifest["paper_demo_observations"] == 0


def test_exactly_one_result_driven_robustness_child() -> None:
    strategy = rows("strategy_cards.csv")
    trial = rows("trial_ledger.csv")
    assert len(strategy) == len(trial) == 1
    assert strategy[0]["approved_route"] == "20pct_diversifier_only"
    assert trial[0]["trial_id"] == task.TRIAL_ID
    assert trial[0]["parent_trial_id"] == task.PARENT_TRIAL_ID
    assert (
        trial[0]["adaptation_label"]
        == "result_driven_robustness_diagnostic"
    )
    assert trial[0]["changed_fields_from_parent"] == (
        "diversifier_route_concentration_diagnostics_and_decision_gate_only"
    )
    assert trial[0]["result_driven_diagnostic"] == "true"
    for field in (
        "strategy_rule_changed",
        "channel_formula_changed",
        "period_changed",
        "instruments_changed",
        "execution_changed",
        "sleeve_weight_changed",
        "reference_changed",
        "controls_changed",
        "costs_changed",
        "optimization_performed",
        "independent_validation_claimed",
    ):
        assert trial[0][field] == "false"


def test_every_parent_robustness_table_reproduces() -> None:
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
        "cost_stress",
        "chronological_quarters",
        "calendar_years",
        "rolling_36_month",
        "rolling_60_month",
        "start_date_sensitivity",
        "concentration",
        "bootstrap",
        "turnover_and_cost",
        "invariants",
    } == {row["scope"] for row in reproduction}


def test_favorable_dates_are_frozen_once_from_reference_comparison() -> None:
    frozen = rows("frozen_concentration_observations.csv")
    months = [
        row for row in frozen if row["observation_type"] == "positive_excess_month"
    ]
    year = [
        row
        for row in frozen
        if row["observation_type"]
        == "strongest_additive_excess_calendar_year"
    ]
    assert len(months) == 3
    assert months[0]["observation"] == "2020-04"
    assert len(year) == 1
    assert year[0]["observation"] == "2023"
    assert {row["identified_once_for_all_comparisons"] for row in frozen} == {
        "true"
    }
    assert {row["canonical_return_series_modified"] for row in frozen} == {
        "false"
    }


def test_month_and_year_neutralization_preserve_timelines() -> None:
    month = rows("month_neutralization_results.csv")
    year = rows("strongest_year_neutralization_results.csv")
    assert len(month) == 6
    assert len(year) == 3
    assert {row["scenario"] for row in month} == {
        "strongest_positive_month",
        "three_strongest_months",
    }
    for row in [*month, *year]:
        assert (
            row["timeline_observation_count_before"]
            == row["timeline_observation_count_after"]
        )
        assert row["temporary_counterfactual_copy"] == "true"
        assert row["canonical_return_series_modified"] == "false"
        assert row["observation_deleted"] == "false"


def test_leave_one_trade_out_is_independent_and_complete() -> None:
    result = rows("leave_one_trade_out_results.csv")
    summary = rows("leave_one_trade_out_summary.csv")[0]
    assert len(result) == int(summary["completed_trade_count"]) == 20
    assert {row["replacement_sleeve"] for row in result} == {"BIL"}
    assert {row["trade_combination_removed"] for row in result} == {"false"}
    assert {row["canonical_return_series_modified"] for row in result} == {
        "false"
    }
    assert {row["invariant_pass"] for row in result} == {"true"}
    assert summary["combinations_of_removed_trades_constructed"] == "false"
    assert summary["counterfactual_rerun_deterministic"] == "true"


def test_trade_concentration_is_complete_without_combination_search() -> None:
    contribution = rows("trade_contribution_concentration.csv")
    individual = [
        row
        for row in contribution
        if row["record_type"] == "individual_completed_trade"
    ]
    summary = [
        row
        for row in contribution
        if row["record_type"] == "concentration_summary"
    ]
    assert len(individual) == 20
    assert len(summary) == 1
    assert {int(row["rank"]) for row in individual} == set(range(1, 21))
    assert {row["combinations_of_removed_trades_constructed"] for row in contribution} == {
        "false"
    }
    assert {row["canonical_return_series_modified"] for row in contribution} == {
        "false"
    }


def test_downside_months_and_reference_selected_episodes_are_complete() -> None:
    downside = rows("reference_negative_month_results.csv")
    episodes = rows("reference_drawdown_episode_results.csv")
    assert {row["portfolio_id"] for row in downside} == set(
        task.PORTFOLIO_IDS.values()
    )
    assert len({row["reference_negative_month_count"] for row in downside}) == 1
    assert episodes
    assert {row["episode_selected_from_reference_only"] for row in episodes} == {
        "true"
    }


def test_cost_accounting_and_invariants_remain_frozen() -> None:
    turnover = rows("turnover_cost_reconciliation.csv")
    invariants = rows("invariant_results.csv")
    assert len(turnover) == len(invariants) == 21
    assert {float(row["cost_bps"]) for row in turnover} == {0.0, 5.0, 10.0}
    assert {row["inner_and_outer_costs_charged_once"] for row in turnover} == {
        "true"
    }
    assert {row["invariant_pass"] for row in invariants} == {"true"}
    assert all(
        float(row["maximum_gross_exposure"]) <= 1.0 + 1e-9
        and float(row["maximum_daily_weight_sum"]) <= 1.0 + 1e-9
        for row in invariants
    )


def test_outcome_is_final_same_period_direction_decision() -> None:
    outcome = rows("outcome_summary.csv")[0]
    assert outcome["outcome"] in {
        "robustness_positive_for_prospective_validation_design",
        "robustness_mixed_defer",
        "robustness_failed",
        "robustness_blocked",
    }
    expected_actions = {
        "robustness_positive_for_prospective_validation_design": (
            task.NEXT_POSITIVE
        ),
        "robustness_mixed_defer": task.NEXT_MIXED,
        "robustness_failed": task.NEXT_FAILED,
        "robustness_blocked": task.NEXT_BLOCKED,
    }
    assert outcome["exact_next_action"] == expected_actions[outcome["outcome"]]
    assert outcome["final_same_period_kaufman_diagnostic"] == "true"
    assert outcome["further_same_period_kaufman_diagnostic_authorized"] == "false"
    assert outcome["independent_validation_claimed"] == "false"
    assert outcome["paper_demo_eligibility_supported"] == "false"


def test_parent_evidence_state_cache_and_canonical_returns_are_unchanged() -> None:
    payload = check()
    assert payload["overall_pass"] is True
    assert payload["required_outputs_exact"] is True
    assert payload["parent_evidence_unchanged"] is True
    assert payload["protected_state_unchanged"] is True
    assert payload["market_data_caches_unchanged"] is True
    assert payload["prior_evidence_unchanged"] is True
    assert payload["canonical_return_series_unchanged"] is True
    assert payload["counterfactual_rerun_deterministic"] is True
    assert (
        payload["preregistration_written_before_diagnostic_calculation"] is True
    )
    assert payload["provider_access"] is False
    assert payload["network_access"] is False
    assert payload["lifecycle_state_changed"] is False
    assert payload["paper_demo_observations_created"] == 0
    assert payload["parameter_search_performed"] is False
    assert payload["broker_orders"] == 0
    assert payload["real_money_actions"] == 0
