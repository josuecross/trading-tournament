from __future__ import annotations

import csv
import json

import pytest
import yaml

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.research import (
    kaufman_breakout_diversifier_incremental_value_followup_v1 as task,
)


OUTPUT = ROOT / "evidence" / "research_recovery" / task.TASK_ID / "latest"


@pytest.fixture(scope="module", autouse=True)
def evidence_ready() -> None:
    assert (OUTPUT / "consistency_check.json").exists()


def rows(name: str) -> list[dict[str, str]]:
    with (OUTPUT / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def json_payload(name: str) -> dict:
    return json.loads((OUTPUT / name).read_text(encoding="utf-8"))


def test_exact_outputs_and_entity_separation() -> None:
    assert {path.name for path in OUTPUT.iterdir()} == task.REQUIRED_OUTPUTS
    manifest = yaml.safe_load((OUTPUT / "followup_manifest.yaml").read_text())
    funnel = json_payload("cohort_funnel_counts.json")
    assert manifest["strategy_id"] == task.STRATEGY_ID
    assert manifest["child_trial_id"] == task.TRIAL_ID
    assert funnel["existing_strategy_configurations_carried_forward"] == 1
    assert funnel["new_strategy_configurations"] == 0
    assert funnel["existing_parent_trials_carried_forward"] == 1
    assert funnel["new_experiment_trials"] == 1
    assert funnel["benchmark_references"] == 6
    assert funnel["portfolio_diagnostics"] == 7
    assert funnel["process_tasks"] == 1
    assert funnel["paper_demo_observations"] == 0


def test_child_trial_changes_only_route_and_controls() -> None:
    strategy = rows("strategy_cards.csv")
    trial = rows("trial_ledger.csv")
    assert len(strategy) == len(trial) == 1
    assert strategy[0]["authoritative_parent_route"] == "standalone"
    assert strategy[0]["authoritative_parent_outcome"] == "closed_exploration"
    assert strategy[0]["evaluation_route"] == "diversifier_only"
    assert strategy[0]["new_strategy_configuration_created"] == "false"
    assert trial[0]["trial_id"] == task.TRIAL_ID
    assert trial[0]["parent_trial_id"] == task.PARENT_TRIAL_ID
    assert trial[0]["adaptation_label"] == "exploratory_variant"
    assert (
        trial[0]["changed_fields_from_parent"]
        == "evaluation_route_and_predeclared_portfolio_controls_only"
    )
    for field in (
        "strategy_rule_changed",
        "channel_formula_changed",
        "period_changed",
        "instruments_changed",
        "execution_changed",
        "cost_model_changed",
        "source_rule_changed",
        "standalone_outcome_changed",
        "optimization_performed",
        "post_result_parameter_change_allowed",
    ):
        assert trial[0][field] == "false"
    assert trial[0]["portfolio_route_changed"] == "true"
    assert trial[0]["result_driven_adaptation"] == "true"


def test_parent_portfolio_reproduction_passes_with_exact_period() -> None:
    reproduction = rows("reproduction_check.csv")
    assert reproduction
    assert all(row["pass"] == "true" for row in reproduction)
    numeric = [row for row in reproduction if row["difference"]]
    assert max(abs(float(row["difference"])) for row in numeric) <= 1e-9
    periods = [
        row for row in reproduction if row["metric"] == "evaluation_period"
    ]
    assert periods
    assert {
        row["reproduced_value"] for row in periods
    } == {"2010-08-10|2026-06-18"}


def test_exposure_control_uses_parent_frozen_weight() -> None:
    benchmarks = rows("benchmark_reference_log.csv")
    exposure = next(
        row
        for row in benchmarks
        if row["benchmark_reference_id"] == task.CONTROL_IDS[1]
    )
    assert float(exposure["exposure_SPY_weight"]) == pytest.approx(
        task.FROZEN_EXPOSURE_SPY
    )
    assert float(exposure["exposure_BIL_weight"]) == pytest.approx(
        task.FROZEN_EXPOSURE_BIL
    )
    assert exposure["recalculated_from_followup_period"] == "false"


def test_required_portfolios_costs_and_explicit_holdings_are_complete() -> None:
    results = rows("full_period_portfolio_results.csv")
    assert len(results) == 21
    assert {row["portfolio_id"] for row in results} == set(
        task.PORTFOLIO_IDS.values()
    )
    assert {float(row["cost_bps"]) for row in results} == {0.0, 5.0, 10.0}
    assert {row["evaluation_start"] for row in results} == {"2010-08-10"}
    assert {row["evaluation_end"] for row in results} == {"2026-06-18"}
    assert {row["daily_fixed_weight_return_blend_used"] for row in results} == {
        "false"
    }
    assert all(
        float(row["maximum_gross_exposure"]) <= 1.0 + 1e-9
        for row in results
    )
    assert all(
        float(row["maximum_daily_weight_sum"]) <= 1.0 + 1e-9
        for row in results
    )


def test_inner_outer_turnover_and_costs_are_separate_and_reconciled() -> None:
    turnover = rows("turnover_cost_reconciliation.csv")
    assert len(turnover) == 21
    assert {row["inner_and_outer_costs_charged_once"] for row in turnover} == {
        "true"
    }
    assert {row["daily_fixed_weight_return_blend_used"] for row in turnover} == {
        "false"
    }
    for row in turnover:
        assert float(row["combined_turnover_diagnostic"]) == pytest.approx(
            float(row["inner_sleeve_turnover"])
            + float(row["outer_turnover"])
        )
        assert float(row["combined_transaction_cost_drag"]) == pytest.approx(
            float(row["inner_transaction_cost_drag"])
            + float(row["outer_transaction_cost_drag"])
        )


def test_halves_and_all_rolling_windows_remain_visible() -> None:
    halves = rows("chronological_half_portfolio_results.csv")
    rolling36 = rows("rolling_36_month_portfolio_results.csv")
    rolling60 = rows("rolling_60_month_portfolio_results.csv")
    assert len(halves) == 14
    assert {row["period_role"] for row in halves} == {
        "chronological_half_not_validation"
    }
    assert rolling36 and rolling60
    assert {row["sealed_untouched_or_validation"] for row in rolling36} == {
        "false"
    }
    assert {row["sealed_untouched_or_validation"] for row in rolling60} == {
        "false"
    }
    assert all(row["donchian_sharpe_difference"] for row in rolling36)
    assert all(row["exposure_matched_sharpe_difference"] for row in rolling60)


def test_candidate_mechanism_is_carried_without_rule_change() -> None:
    diagnostics = rows("candidate_mechanism_diagnostics.csv")
    assert diagnostics
    record_types = {row["record_type"] for row in diagnostics}
    assert {"summary", "daily_target_history", "signal_change", "trade"} <= record_types
    assert {row["rule_changed"] for row in diagnostics} == {"false"}
    assert {row["used_for_parameter_change"] for row in diagnostics} == {"false"}
    summary = next(row for row in diagnostics if row["record_type"] == "summary")
    assert int(summary["completed_trade_count"]) > 0
    assert float(summary["average_candidate_SPY_exposure"]) >= 0.0


def test_all_invariants_and_reproduction_gate_pass() -> None:
    invariants = rows("invariant_results.csv")
    check = json_payload("consistency_check.json")
    assert len(invariants) == 21
    assert {row["invariant_pass"] for row in invariants} == {"true"}
    assert {row["signal_rule_changed"] for row in invariants} == {"false"}
    assert {row["channel_formula_changed"] for row in invariants} == {"false"}
    assert {row["inner_execution_next_open"] for row in invariants} == {"true"}
    assert {
        row["outer_execution_following_session_close"] for row in invariants
    } == {"true"}
    assert check["reproduction_passed"] is True
    assert check["serial_rerun_deterministic"] is True


def test_outcome_is_exploration_only_and_exactly_gated() -> None:
    outcome = rows("outcome_summary.csv")[0]
    candidates = rows("exploratory_followup_candidates.csv")
    assert outcome["outcome"] in {
        "exploratory_followup_candidate_diversifier",
        "closed_exploration",
        "blocked_feasibility",
    }
    assert outcome["validation_evidence_claimed"] == "false"
    assert outcome["paper_demo_eligibility_supported"] == "false"
    if outcome["outcome"] == "exploratory_followup_candidate_diversifier":
        assert len(candidates) == 1
        assert outcome["failure_reason"] == ""
        assert outcome["exact_next_action"] == task.NEXT_ADVANCE
    else:
        assert candidates == []
        assert outcome["failure_reason"]


def test_parent_protected_state_caches_and_prior_evidence_are_unchanged() -> None:
    check = json_payload("consistency_check.json")
    assert check["overall_pass"] is True
    assert check["required_outputs_exact"] is True
    assert check["parent_evidence_unchanged"] is True
    assert check["protected_state_unchanged"] is True
    assert check["market_data_caches_unchanged"] is True
    assert check["prior_evidence_unchanged"] is True
    assert check["provider_access"] is False
    assert check["network_access"] is False
    assert check["lifecycle_state_changed"] is False
    assert check["paper_demo_observations_created"] == 0
    assert check["parameter_search_performed"] is False
    assert check["broker_orders"] == 0
    assert check["real_money_actions"] == 0
