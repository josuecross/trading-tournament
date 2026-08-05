from __future__ import annotations

import csv
import json
from datetime import date

import pytest
import yaml

from strategy_lab.research_os.research import (
    ivts_unfiltered_diversifier_incremental_value_followup_v1 as task,
)


@pytest.fixture(scope="module")
def result() -> dict[str, object]:
    return task.run()


def rows(name: str) -> list[dict[str, str]]:
    with (task.OUTPUT_DIR / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_required_artifacts_and_consistency(result: dict[str, object]) -> None:
    assert result["consistency_passed"] is True
    assert all((task.OUTPUT_DIR / name).exists() for name in task.REQUIRED_ARTIFACTS)


def test_exactly_one_result_driven_strategy_and_trial(result: dict[str, object]) -> None:
    strategy = rows("strategy_cards.csv")
    trial = rows("trial_ledger.csv")
    assert len(strategy) == 1
    assert len(trial) == 1
    assert strategy[0]["strategy_id"] == task.STRATEGY_ID
    assert strategy[0]["route"] == "diversifier_only"
    assert strategy[0]["adaptation_selected_after_viewing_V4_results"] == "true"
    assert strategy[0]["source_rule_changed"] == "true"
    assert trial[0]["parent_trial_id"] == task.PARENT_TRIAL_ID
    assert trial[0]["adaptation_label"] == "result_driven_exploratory_variant"
    assert trial[0]["prior_benchmark_reference_represented_as_existing_trial"] == "false"


def test_median5_remains_closed_and_unchanged(result: dict[str, object]) -> None:
    check = json.loads(
        (task.OUTPUT_DIR / "consistency_check.json").read_text(encoding="utf-8")
    )
    assert check["V4_median5_outcome_preserved"] == "closed_exploration"
    assert check["V4_median5_failure_reason_preserved"] == "weak_vs_primary_control"
    assert check["prior_evidence_unchanged"] is True


def test_v4_reproduction_gate_passes(result: dict[str, object]) -> None:
    reproduction = rows("v4_reproduction_check.csv")
    assert reproduction
    assert all(row["pass"] == "true" for row in reproduction)
    assert max(abs(float(row["difference"])) for row in reproduction) <= 1e-9
    assert result["V4_reproduction_passed"] is True


def test_no_median_is_calculated_or_used(result: dict[str, object]) -> None:
    diagnostics = rows("state_signal_diagnostics.csv")
    assert diagnostics
    assert all(row["rolling_median_calculated_or_used"] == "false" for row in diagnostics)
    manifest = yaml.safe_load(
        (task.OUTPUT_DIR / "followup_manifest.yaml").read_text(encoding="utf-8")
    )
    assert manifest["median_filter_removed"] is True
    assert manifest["thresholds_changed"] is False


def test_frozen_controls_and_cost_grid(result: dict[str, object]) -> None:
    benchmark = rows("benchmark_reference_log.csv")
    standalone = rows("standalone_results.csv")
    assert len(benchmark) == 5
    assert {row["benchmark_reference_id"] for row in benchmark} == set(task.CONTROLS)
    assert len(standalone) == 18
    assert {float(row["cost_bps"]) for row in standalone} == {0.0, 5.0, 10.0}
    exposure = next(
        row for row in benchmark if row["benchmark_reference_id"] == task.EXPOSURE_CONTROL
    )
    assert "candidate-average" in exposure["control_definition"]


def test_following_session_timing_is_enforced(result: dict[str, object]) -> None:
    signals = [
        row
        for row in rows("state_signal_diagnostics.csv")
        if row["record_type"] == "signal_observation"
        and row["following_execution_session"]
    ]
    assert signals
    assert all(
        date.fromisoformat(row["following_execution_session"])
        > date.fromisoformat(row["signal_date"])
        for row in signals
    )
    assert all(row["same_day_return_allowed"] == "false" for row in signals)


def test_portfolio_construction_uses_explicit_holdings(result: dict[str, object]) -> None:
    portfolio = rows("portfolio_contribution_results.csv")
    assert len(portfolio) == 18
    assert {row["portfolio_id"] for row in portfolio} == set(task.PORTFOLIO_IDS.values())
    assert all(row["daily_fixed_weight_return_blend_used"] == "false" for row in portfolio)
    assert all(
        float(row["maximum_gross_exposure"]) <= 1.0 + 1e-9
        for row in portfolio
    )


def test_chronological_and_rolling_windows_remain_visible(
    result: dict[str, object],
) -> None:
    standalone_half = rows("standalone_chronological_half_results.csv")
    portfolio_half = rows("portfolio_chronological_half_results.csv")
    rolling36 = rows("rolling_36_month_portfolio_results.csv")
    rolling60 = rows("rolling_60_month_portfolio_results.csv")
    assert len(standalone_half) == 12
    assert len(portfolio_half) == 12
    assert rolling36 and rolling60
    assert all(row["sealed_holdout_or_validation"] == "false" for row in rolling36)
    assert all(row["sealed_holdout_or_validation"] == "false" for row in rolling60)


def test_turnover_cost_and_all_invariants_reconcile(result: dict[str, object]) -> None:
    turnover = rows("turnover_cost_reconciliation.csv")
    invariants = rows("invariant_results.csv")
    assert len(turnover) == 36
    assert len(invariants) == 36
    assert all(row["turnover_reconciles"] == "true" for row in turnover)
    assert all(row["cost_reconciles"] == "true" for row in turnover)
    assert all(row["invariant_pass"] == "true" for row in invariants)
    assert all(row["signal_date_return_used"] == "false" for row in invariants)


def test_outcome_is_exploration_only(result: dict[str, object]) -> None:
    outcome = rows("outcome_summary.csv")[0]
    assert outcome["outcome"] in {
        "exploratory_followup_candidate_diversifier",
        "closed_exploration",
        "inconclusive_data_issue",
        "blocked_feasibility",
    }
    assert outcome["validation_evidence_claimed"] == "false"
    assert outcome["paper_demo_eligibility_supported"] == "false"


def test_protected_state_and_cache_are_unchanged(result: dict[str, object]) -> None:
    check = json.loads(
        (task.OUTPUT_DIR / "consistency_check.json").read_text(encoding="utf-8")
    )
    assert check["protected_state_unchanged"] is True
    assert check["prior_evidence_unchanged"] is True
    assert check["cache_unchanged"] is True
    assert not any(check["forbidden_actions"].values())


def test_generation_is_deterministic(result: dict[str, object]) -> None:
    first = json.loads(
        (task.OUTPUT_DIR / "consistency_check.json").read_text(encoding="utf-8")
    )
    rerun = task.run()
    second = json.loads(
        (task.OUTPUT_DIR / "consistency_check.json").read_text(encoding="utf-8")
    )
    assert rerun["consistency_passed"] is True
    assert first["deterministic_core_hash"] == second["deterministic_core_hash"]
