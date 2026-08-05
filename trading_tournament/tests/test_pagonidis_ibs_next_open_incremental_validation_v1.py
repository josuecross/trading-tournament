from __future__ import annotations

import csv
import json
from pathlib import Path

import pandas as pd
import pytest
import yaml

from strategy_lab.research_os.research import (
    pagonidis_ibs_next_open_incremental_validation_v1 as validation,
)


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = (
    ROOT
    / "evidence"
    / "validation"
    / validation.TASK_ID
    / "latest"
)


@pytest.fixture(scope="module", autouse=True)
def evidence_ready() -> None:
    assert (EVIDENCE / "consistency_check.json").exists(), (
        "Run the dedicated validation runner before focused tests."
    )


def rows(name: str) -> list[dict[str, str]]:
    with (EVIDENCE / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def json_payload(name: str) -> dict:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def yaml_payload(name: str) -> dict:
    return yaml.safe_load((EVIDENCE / name).read_text(encoding="utf-8"))


def test_exact_scope_artifacts_and_manifest() -> None:
    assert {path.name for path in EVIDENCE.iterdir()} == validation.REQUIRED_OUTPUTS
    manifest = yaml_payload("validation_manifest.yaml")
    assert manifest["task_id"] == validation.TASK_ID
    assert manifest["mode"] == manifest["stage"] == "validation"
    assert manifest["strategy_id"] == validation.STRATEGY_ID
    assert manifest["strategy_configuration_count"] == 1
    assert manifest["validation_trial_count"] == 1
    assert manifest["benchmark_reference_count"] == 4
    assert manifest["process_task_count"] == 1
    assert manifest["parent_trial_id"] == validation.PARENT_TRIAL_ID
    assert manifest["validation_trial_id"] == validation.VALIDATION_TRIAL_ID
    assert manifest["adaptation_label"] == "validation_variant"
    assert manifest["exact_source_replication_claimed"] is False
    assert manifest["promotion_lifecycle_or_paper_demo_authorized"] is False


def test_lineage_and_frozen_strategy_fields() -> None:
    strategies = rows("strategy_cards.csv")
    trials = rows("trial_ledger.csv")
    process = rows("process_task_log.csv")
    benchmarks = rows("benchmark_reference_log.csv")
    assert len(strategies) == len(trials) == len(process) == 1
    assert len(benchmarks) == 4
    assert strategies[0]["entity_type"] == "strategy_configuration"
    assert strategies[0]["stage"] == "validation"
    assert trials[0]["entity_type"] == "experiment_trial"
    assert trials[0]["trial_id"] == validation.VALIDATION_TRIAL_ID
    assert trials[0]["parent_trial_id"] == validation.PARENT_TRIAL_ID
    assert trials[0]["adaptation_label"] == "validation_variant"
    assert trials[0]["changed_fields_from_parent"] == (
        "validation_period_cost_and_stability_diagnostics_only"
    )
    for field in (
        "signal_changed",
        "threshold_changed",
        "instruments_changed",
        "execution_changed",
        "optimization_performed",
        "result_driven_change",
    ):
        assert trials[0][field] == "false"
    assert trials[0]["cost_diagnostics_expanded"] == "true"
    assert {row["entity_type"] for row in benchmarks} == {
        "benchmark_reference"
    }
    assert {row["stage"] for row in benchmarks} == {
        "benchmark_reference_only"
    }
    assert {row["benchmark_id"] for row in benchmarks} == set(
        validation.CONTROL_IDS
    )


def test_parent_reproduction_passes_at_one_e_minus_nine() -> None:
    reproduction = rows("reproduction_check.csv")
    assert reproduction
    assert {row["reproduction_status"] for row in reproduction} == {"pass"}
    strict = [
        row
        for row in reproduction
        if row["tolerance"] == "1e-09" and row["absolute_difference"]
    ]
    assert strict
    assert max(float(row["absolute_difference"]) for row in strict) <= 1e-9
    assert any(
        row["scope"] == "frozen_count_or_turnover"
        and row["metric"] == "active_session_count"
        and float(row["actual_value"]) == 876.0
        for row in reproduction
    )
    assert any(
        row["scope"] == "frozen_count_or_turnover"
        and row["metric"] == "total_one_way_turnover"
        and float(row["actual_value"]) == 1752.0
        for row in reproduction
    )


def test_cost_grid_and_exposure_control_are_frozen() -> None:
    costs = rows("cost_sensitivity_results.csv")
    assert len(costs) == 25
    assert {float(row["cost_assumption_bps"]) for row in costs} == set(
        validation.COST_BPS
    )
    assert {row["row_id"] for row in costs} == {
        validation.STRATEGY_ID,
        *validation.CONTROL_IDS,
    }
    exposure = [
        row
        for row in costs
        if row["row_id"] == "exposure_matched_fractional_spy_intraday_v1"
    ]
    assert all(
        float(row["average_spy_intraday_exposure"])
        == pytest.approx(876 / 4794)
        for row in exposure
    )
    full = rows("full_period_results.csv")
    assert len(full) == 5
    assert {row["cost_assumption_bps"] for row in full} == {"5"}


def test_break_even_costs_are_deterministic_roots() -> None:
    roots = rows("break_even_cost_results.csv")
    assert {row["period_label"] for row in roots} == {
        "full_period",
        "first_chronological_half",
        "second_chronological_half",
    }
    assert {
        row["root_finding_method"] for row in roots
    } == {"deterministic_bisection_on_frozen_trade_ledger"}
    assert {
        row["threshold_or_strategy_optimized_from_root"] for row in roots
    } == {"false"}
    for row in roots:
        assert abs(float(row["root_residual_total_return"])) <= 1e-10
    full = next(row for row in roots if row["period_label"] == "full_period")
    assert float(full["break_even_one_way_cost_bps"]) < 10.0


def test_halves_include_every_cost_and_are_not_claimed_as_holdouts() -> None:
    halves = rows("chronological_half_results.csv")
    assert len(halves) == 50
    assert {row["period_label"] for row in halves} == {
        "first_chronological_half",
        "second_chronological_half",
    }
    assert {row["period_role"] for row in halves} == {
        "chronological_half_not_clean_or_sealed_holdout"
    }
    assert {float(row["cost_assumption_bps"]) for row in halves} == set(
        validation.COST_BPS
    )
    second = next(
        row
        for row in halves
        if row["row_id"] == validation.STRATEGY_ID
        and row["period_label"] == "second_chronological_half"
        and row["cost_assumption_bps"] == "5"
    )
    assert float(second["total_return"]) <= 0.0
    assert float(second["sharpe_ratio"]) <= 0.0


def test_all_eligible_monthly_rolling_windows_remain_visible() -> None:
    summaries = rows("rolling_window_summary.csv")
    assert {int(row["window_months"]) for row in summaries} == {24, 36, 60}
    for months in validation.ROLLING_MONTHS:
        rolling = rows(f"rolling_{months}_month_results.csv")
        summary = next(
            row for row in summaries if int(row["window_months"]) == months
        )
        assert len(rolling) == int(summary["eligible_window_count"])
        assert int(summary["possible_monthly_stepped_windows"]) == (
            len(rolling) + int(summary["excluded_below_25_active_signals"])
        )
        assert all(int(row["active_signals"]) >= 25 for row in rolling)
        dates = [pd.Timestamp(row["window_end"]) for row in rolling]
        assert dates == sorted(dates)
        assert len(dates) == len(set(dates))
        assert summary["all_unfavorable_eligible_windows_retained"] == "true"


def test_rolling_control_dominance_fields_recompute() -> None:
    rolling = rows("rolling_36_month_results.csv")
    assert rolling
    for row in rolling[:25]:
        candidate = {
            "cagr": float(row["candidate_cagr"]),
            "sharpe_ratio": float(row["candidate_sharpe_ratio"]),
            "maximum_drawdown": float(row["candidate_maximum_drawdown"]),
        }
        prior = {
            "cagr": float(row["prior_negative_cagr"]),
            "sharpe_ratio": float(row["prior_negative_sharpe_ratio"]),
            "maximum_drawdown": float(
                row["prior_negative_maximum_drawdown"]
            ),
        }
        exposure = {
            "cagr": float(row["exposure_matched_cagr"]),
            "sharpe_ratio": float(row["exposure_matched_sharpe_ratio"]),
            "maximum_drawdown": float(
                row["exposure_matched_maximum_drawdown"]
            ),
        }
        assert (
            row["prior_negative_dominates_candidate"] == "true"
        ) == validation.dominates(prior, candidate)
        assert (
            row["exposure_matched_dominates_candidate"] == "true"
        ) == validation.dominates(exposure, candidate)


def test_calendar_and_signal_stability_diagnostics_are_complete() -> None:
    calendar = rows("calendar_year_results.csv")
    stability = rows("signal_stability_diagnostics.csv")
    assert calendar
    assert sum(int(row["active_signals"]) for row in calendar) == 876
    assert {row["threshold_changed_from_diagnostic"] for row in calendar} == {
        "false"
    }
    assert {row["period_label"] for row in stability} == {
        "full_period",
        "first_chronological_half",
        "second_chronological_half",
    }
    assert {
        row["threshold_changed_from_diagnostic"] for row in stability
    } == {"false"}
    assert all(row["net_returns_by_cost_json"] for row in stability)


def test_turnover_costs_and_invariants_preserve_open_close_accounting() -> None:
    turnover = rows("turnover_cost_reconciliation.csv")
    invariants = rows("invariant_results.csv")
    assert len(turnover) == len(invariants) == 25
    candidate = [
        row for row in turnover if row["row_id"] == validation.STRATEGY_ID
    ]
    assert {float(row["total_open_one_way_turnover"]) for row in candidate} == {
        876.0
    }
    assert {float(row["total_close_one_way_turnover"]) for row in candidate} == {
        876.0
    }
    assert {float(row["total_one_way_turnover"]) for row in candidate} == {
        1752.0
    }
    assert {row["open_and_close_costs_netted_away"] for row in candidate} == {
        "false"
    }
    assert {row["invariant_pass"] for row in invariants} == {"true"}
    candidate_invariants = [
        row for row in invariants if row["row_id"] == validation.STRATEGY_ID
    ]
    assert {
        row["SPY_overnight_return_in_candidate"]
        for row in candidate_invariants
    } == {"false"}
    assert all(
        float(row["maximum_gross_exposure"]) <= 1.0 + 1e-12
        for row in invariants
    )


def test_outcome_failure_reason_and_next_action_follow_frozen_gate() -> None:
    summary = rows("outcome_summary.csv")
    assert len(summary) == 1
    row = summary[0]
    assert row["outcome"] == "validation_failed"
    assert row["primary_failure_reason"] == "cost_drag"
    assert row["exact_next_action"] == (
        "direction_owner_review_close_ibs_after_validation_v1"
    )
    assert row["exact_source_replication_claimed"] == "false"
    checks = json.loads(row["validation_checks"])
    assert checks["reproduction_pass"] is True
    assert checks["all_invariants_pass"] is True
    assert checks["full_period_10bps_return_nonnegative"] is False
    assert checks["full_period_break_even_at_least_10bps"] is False
    assert (
        checks["second_half_5bps_total_return_and_sharpe_positive"] is False
    )
    actions = rows("next_actions.csv")
    assert {
        action["exact_next_action"] for action in actions
    } == {"direction_owner_review_close_ibs_after_validation_v1"}
    assert {action["execute_in_this_task"] for action in actions} == {"false"}


def test_protected_inputs_and_prior_evidence_are_unchanged() -> None:
    consistency = json_payload("consistency_check.json")
    assert consistency["status"] == "pass"
    assert consistency["consistency_passed"] is True
    assert consistency["parent_exploration_evidence_unchanged"] is True
    assert consistency["V5_evidence_unchanged"] is True
    assert consistency["market_data_caches_unchanged"] is True
    assert consistency["protected_state_unchanged"] is True
    assert consistency["prior_evidence_unchanged"] is True
    assert consistency["reproduction_pass"] is True
    assert consistency["all_invariants_pass"] is True
    assert consistency["deterministic_frozen_core_hash"] == (
        validation.deterministic_core_hash()
    )
    assert not any(consistency["forbidden_actions"].values())
