from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
import pytest
import yaml

from strategy_lab.research_os.research import (
    v7_candidate_diversifier_incremental_value_followup_v1 as followup,
)


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = (
    ROOT
    / "evidence"
    / "research_recovery"
    / followup.TASK_ID
    / "latest"
)

REQUIRED_ARTIFACTS = {
    "followup_manifest.yaml",
    "strategy_cards.csv",
    "trial_ledger.csv",
    "benchmark_reference_log.csv",
    "process_task_log.csv",
    "reproduction_check.csv",
    "full_period_portfolio_results.csv",
    "chronological_half_portfolio_results.csv",
    "portfolio_control_definitions.csv",
    "incremental_value_comparison.csv",
    "turnover_cost_reconciliation.csv",
    "invariant_results.csv",
    "exploratory_followup_candidates.csv",
    "failure_reasons.csv",
    "next_actions.csv",
    "outcome_summary.csv",
    "cohort_funnel_counts.json",
    "consistency_check.json",
    "followup_report.md",
}


@pytest.fixture(scope="module", autouse=True)
def evidence_ready() -> None:
    assert (EVIDENCE / "consistency_check.json").exists(), (
        "Run the dedicated diversifier follow-up runner before focused tests."
    )


def rows(name: str) -> list[dict[str, str]]:
    with (EVIDENCE / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def json_payload(name: str) -> dict:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def yaml_payload(name: str) -> dict:
    return yaml.safe_load((EVIDENCE / name).read_text(encoding="utf-8"))


def test_exact_scope_manifest_and_required_artifacts() -> None:
    assert REQUIRED_ARTIFACTS.issubset({path.name for path in EVIDENCE.iterdir()})
    manifest = yaml_payload("followup_manifest.yaml")
    assert manifest["task_id"] == followup.TASK_ID
    assert manifest["mode"] == "fast-progress"
    assert manifest["stage"] == "exploration"
    assert tuple(manifest["strategy_ids"]) == followup.EXPECTED_STRATEGY_IDS
    assert manifest["existing_strategy_identity_count"] == 2
    assert manifest["new_child_experiment_trial_count"] == 2
    assert manifest["evaluation_route"] == "diversifier_only"
    assert manifest["portfolio_start"] == "2010-08-10"
    assert manifest["portfolio_end"] == "2026-06-18"
    assert manifest["cost_assumptions_bps"] == [0.0, 5.0, 10.0]
    assert manifest["prior_standalone_outcomes_changed"] is False
    assert manifest["validation_claimed"] is False
    assert manifest["authoritative_lifecycle_changed"] is False


def test_strategy_identities_and_child_trial_lineage_are_exact() -> None:
    strategies = rows("strategy_cards.csv")
    trials = rows("trial_ledger.csv")
    assert len(strategies) == len(trials) == 2
    assert tuple(row["strategy_id"] for row in strategies) == (
        followup.EXPECTED_STRATEGY_IDS
    )
    assert {row["entity_type"] for row in strategies} == {
        "strategy_configuration"
    }
    assert {row["entity_type"] for row in trials} == {"experiment_trial"}
    assert {row["stage"] for row in strategies + trials} == {"exploration"}
    assert {row["evaluation_route"] for row in strategies + trials} == {
        "diversifier_only"
    }
    assert {row["adaptation_label"] for row in trials} == {"exploratory_variant"}
    assert {
        row["changed_fields_from_parent"] for row in trials
    } == {"evaluation_route_and_predeclared_portfolio_controls_only"}
    expected_parents = {card.strategy_id: card.parent_trial_id for card in followup.CARDS}
    assert {
        row["strategy_id"]: row["parent_trial_id"] for row in trials
    } == expected_parents
    frozen_false = {
        "strategy_rule_changed",
        "parameters_changed",
        "instruments_changed",
        "execution_changed",
        "cost_model_changed",
        "source_rule_changed",
        "result_driven_parameter_change",
    }
    assert all(row[field] == "false" for row in trials for field in frozen_false)
    assert {row["portfolio_route_changed"] for row in trials} == {"true"}
    assert {row["counted_as_new_strategy"] for row in trials} == {"false"}
    assert {row["counted_as_new_trial"] for row in trials} == {"true"}


def test_prior_standalone_closures_are_preserved() -> None:
    strategies = {row["strategy_id"]: row for row in rows("strategy_cards.csv")}
    assert strategies[followup.EXPECTED_STRATEGY_IDS[0]][
        "prior_standalone_failure_reason"
    ] == "weak_vs_primary_control"
    assert strategies[followup.EXPECTED_STRATEGY_IDS[1]][
        "prior_standalone_failure_reason"
    ] == "period_instability"
    assert {row["prior_standalone_outcome"] for row in strategies.values()} == {
        "closed_exploration"
    }
    assert {
        row["prior_standalone_outcome_changed"] for row in strategies.values()
    } == {"false"}
    assert {
        row["authoritative_lifecycle_changed"] for row in strategies.values()
    } == {"false"}


def test_v7_full_and_half_portfolio_reproduction_passes() -> None:
    reproduction = rows("reproduction_check.csv")
    assert reproduction
    assert {row["reproduction_pass"] for row in reproduction} == {"true"}
    metric_rows = [row for row in reproduction if row["difference"]]
    assert max(abs(float(row["difference"])) for row in metric_rows) <= 1e-10
    assert {
        row["period_label"]
        for row in reproduction
        if row["metric"] != "aggregate_approximate_expectation"
    } == {
        "full_period",
        "first_chronological_half",
        "second_chronological_half",
    }
    approximate = [
        row
        for row in reproduction
        if row["metric"] == "aggregate_approximate_expectation"
    ]
    assert len(approximate) == 2


def test_predeclared_controls_and_exposure_weights_are_frozen() -> None:
    definitions = rows("portfolio_control_definitions.csv")
    by_strategy = {
        strategy_id: {
            row["portfolio_id"]
            for row in definitions
            if row["strategy_id"] == strategy_id
        }
        for strategy_id in followup.EXPECTED_STRATEGY_IDS
    }
    absorption = followup.CARDS[0]
    high_volume = followup.CARDS[1]
    assert by_strategy[absorption.strategy_id] == {
        "frozen_reference_100pct",
        absorption.candidate_portfolio_id,
        *{followup.portfolio_id(value, absorption) for value in absorption.controls},
    }
    assert by_strategy[high_volume.strategy_id] == {
        "frozen_reference_100pct",
        high_volume.candidate_portfolio_id,
        *{
            followup.portfolio_id(value, high_volume)
            for value in high_volume.controls
        },
    }
    exposure = {
        row["strategy_id"]: float(row["exposure_matched_SPY_weight"])
        for row in definitions
        if row["exposure_matched_SPY_weight"]
    }
    assert np.isclose(
        exposure[absorption.strategy_id], 0.641084462982, atol=1e-12
    )
    assert np.isclose(
        exposure[high_volume.strategy_id],
        0.15849843587069865,
        atol=1e-12,
    )
    assert {row["optimized"] for row in definitions} == {"false"}


def test_portfolio_results_use_exact_periods_costs_and_natural_drift() -> None:
    full = rows("full_period_portfolio_results.csv")
    halves = rows("chronological_half_portfolio_results.csv")
    assert {row["cost_assumption_bps"] for row in full + halves} == {
        "0",
        "5",
        "10",
    }
    assert {row["evaluation_start"] for row in full} == {"2010-08-10"}
    assert {row["evaluation_end"] for row in full} == {"2026-06-18"}
    assert {
        (row["evaluation_start"], row["evaluation_end"]) for row in halves
    } == {
        ("2010-08-10", "2018-07-11"),
        ("2018-07-12", "2026-06-18"),
    }
    assert all("not_clean" in row["period_role"] for row in halves)
    definitions = rows("portfolio_control_definitions.csv")
    assert {
        row["construction"] for row in definitions
    } == {
        "100pct_frozen_reference",
        "monthly_rebalanced_80pct_reference_plus_20pct_frozen_sleeve",
    }
    assert {row["natural_drift"] for row in definitions} == {"true"}
    assert {
        row["execution"] for row in definitions
    } == {"following_session_close"}


def test_turnover_cost_and_portfolio_invariants_pass() -> None:
    turnover = rows("turnover_cost_reconciliation.csv")
    invariants = rows("invariant_results.csv")
    assert turnover and invariants
    assert {
        row["turnover_formula"] for row in turnover
    } == {"0.5*sum(abs(target_weight-pretrade_weight))"}
    assert {row["natural_drift_between_rebalances"] for row in turnover} == {
        "true"
    }
    assert {row["fixed_weight_daily_return_blend_used"] for row in turnover} == {
        "false"
    }
    assert {row["invariant_pass"] for row in invariants} == {"true"}
    assert {row["explicit_zero_weights"] for row in invariants} == {"true"}
    assert {row["stale_weight_forward_fill_used"] for row in invariants} == {
        "false"
    }
    assert {row["negative_weights_present"] for row in invariants} == {"false"}
    assert {row["leverage_or_shorting_used"] for row in invariants} == {"false"}
    assert all(
        float(row["maximum_gross_exposure"]) <= 1.0 + 1e-9
        and float(row["maximum_daily_weight_sum"]) <= 1.0 + 1e-9
        for row in invariants
    )


def test_incremental_value_outcomes_and_unfavorable_comparisons_remain_visible() -> None:
    outcomes = {row["strategy_id"]: row for row in rows("outcome_summary.csv")}
    absorption = outcomes[followup.EXPECTED_STRATEGY_IDS[0]]
    high_volume = outcomes[followup.EXPECTED_STRATEGY_IDS[1]]
    assert absorption["outcome"] == "closed_exploration"
    assert absorption["failure_reason"] == "period_instability"
    assert "first_chronological_half" in absorption["decision_reason"]
    assert high_volume["outcome"] == "closed_exploration"
    assert high_volume["failure_reason"] == "benchmark_like_behavior"
    assert "exposure-matched control" in high_volume["decision_reason"]
    comparisons = rows("incremental_value_comparison.csv")
    assert comparisons
    assert any(
        row["strategy_id"] == absorption["strategy_id"]
        and row["period_label"] == "first_chronological_half"
        and row["comparison_role"] == "critical_exposure_matched"
        and row["candidate_worse_on_sharpe_and_drawdown"] == "true"
        for row in comparisons
    )
    assert any(
        row["strategy_id"] == high_volume["strategy_id"]
        and row["period_label"] == "full_period"
        and row["comparison_role"] == "critical_exposure_matched"
        and row["candidate_material_advantage"] == "false"
        for row in comparisons
    )


def test_entity_funnel_next_action_and_no_followups_reconcile() -> None:
    funnel = json_payload("cohort_funnel_counts.json")
    assert funnel["existing_strategy_identities"] == 2
    assert funnel["prior_standalone_trials_carried_as_parent_references"] == 2
    assert funnel["new_child_experiment_trials"] == 2
    assert funnel["benchmark_references"] == 11
    assert funnel["process_tasks"] == 1
    assert funnel["exploratory_followup_candidate_diversifier"] == 0
    assert funnel["closed_exploration"] == 2
    assert funnel["blocked_feasibility"] == 0
    assert funnel["outcome_count_reconciles"] is True
    assert funnel["exact_next_action"] == followup.NEXT_ALL_CLOSED
    assert len(rows("process_task_log.csv")) == 1


def test_protected_state_cache_v7_and_prior_evidence_are_unchanged() -> None:
    check = json_payload("consistency_check.json")
    assert check["consistency_passed"] is True
    assert check["protected_state_unchanged"] is True
    assert check["cache_unchanged"] is True
    assert check["V7_evidence_unchanged"] is True
    assert check["prior_evidence_unchanged"] is True
    assert check["all_portfolio_invariants_passed"] is True
    assert check["monthly_rebalanced_80_20_with_natural_drift"] is True
    assert check["fixed_weight_daily_return_blend_used"] is False
    assert check["authoritative_lifecycle_changed"] is False
    assert not any(check["forbidden_actions"].values())


def test_frozen_core_hash_is_deterministic() -> None:
    assert followup.deterministic_core_hash() == followup.deterministic_core_hash()
    assert followup.deterministic_core_hash().startswith("sha256:")
