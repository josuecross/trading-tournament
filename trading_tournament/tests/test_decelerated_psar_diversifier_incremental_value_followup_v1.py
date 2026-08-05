from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest
import yaml

from strategy_lab.research_os.research import (
    decelerated_psar_diversifier_incremental_value_followup_v1 as followup,
)


OUTPUT = followup.OUTPUT_DIR


def rows(name: str) -> list[dict[str, str]]:
    with (OUTPUT / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def payload(name: str) -> dict:
    return json.loads((OUTPUT / name).read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture(scope="module", autouse=True)
def generated() -> None:
    result = followup.run()
    assert result["overall_pass"] is True


def test_required_artifacts_and_single_route_scope() -> None:
    required = {
        "followup_manifest.yaml",
        "strategy_cards.csv",
        "trial_ledger.csv",
        "benchmark_reference_log.csv",
        "process_task_log.csv",
        "reproduction_check.csv",
        "portfolio_control_definitions.csv",
        "full_period_portfolio_results.csv",
        "chronological_half_portfolio_results.csv",
        "rolling_36_month_portfolio_results.csv",
        "rolling_60_month_portfolio_results.csv",
        "rolling_window_summary.csv",
        "reference_negative_month_results.csv",
        "candidate_mechanism_diagnostics.csv",
        "turnover_cost_reconciliation.csv",
        "invariant_results.csv",
        "exploratory_followup_candidates.csv",
        "outcome_summary.csv",
        "failure_reasons.csv",
        "next_actions.csv",
        "cohort_funnel_counts.json",
        "consistency_check.json",
        "followup_report.md",
    }
    assert required == {path.name for path in OUTPUT.iterdir() if path.is_file()}
    manifest = yaml.safe_load((OUTPUT / "followup_manifest.yaml").read_text(encoding="utf-8"))
    assert manifest["strategy_id"] == followup.STRATEGY_ID
    assert manifest["route"] == "diversifier_only"
    assert manifest["new_strategy_configuration_count"] == 0
    assert manifest["new_experiment_trial_count"] == 1


def test_child_trial_lineage_and_parent_closure_are_preserved() -> None:
    strategies = rows("strategy_cards.csv")
    trials = rows("trial_ledger.csv")
    assert len(strategies) == len(trials) == 1
    trial = trials[0]
    assert trial["trial_id"] == followup.TRIAL_ID
    assert trial["parent_trial_id"] == followup.PARENT_TRIAL_ID
    assert trial["adaptation_label"] == "exploratory_variant"
    assert trial["changed_fields_from_parent"] == (
        "evaluation_route_and_portfolio_controls_only"
    )
    assert trial["route_changed_to_diversifier_only"].lower() == "true"
    assert trial["result_driven_route_review"].lower() == "true"
    assert trial["PSAR_formula_changed"].lower() == "false"
    assert trial["AF_parameters_changed"].lower() == "false"
    assert trial["standalone_outcome_changed"].lower() == "false"


def test_parent_reproduction_passes_exact_tolerance() -> None:
    reproduction = rows("reproduction_check.csv")
    assert len(reproduction) == 4 * 3 * len(followup.REPRODUCTION_METRICS)
    assert all(row["reproduction_pass"].lower() == "true" for row in reproduction)
    assert max(float(row["absolute_difference"]) for row in reproduction) <= 1e-9
    consistency = payload("consistency_check.json")
    assert consistency["parent_reproduction_pass"] is True
    assert consistency["evaluation_period_exact"] is True


def test_archived_and_route_frozen_exposure_weights_are_not_conflated() -> None:
    definitions = {
        row["control_id"]: row for row in rows("portfolio_control_definitions.csv")
    }
    exposure = definitions[
        "decelerated_psar_exposure_matched_spy_bil_control"
    ]
    assert float(exposure["route_frozen_weight"]) == 0.753493
    assert float(exposure["SPY_weight"]) == 0.753493
    assert float(exposure["BIL_weight"]) == 0.246507
    assert float(exposure["parent_archived_weight"]) != 0.753493
    assert exposure["weight_recalculated"].lower() == "false"


def test_exact_seven_portfolios_costs_period_and_controls() -> None:
    full = rows("full_period_portfolio_results.csv")
    assert len(full) == 7 * 3
    assert {row["portfolio_id"] for row in full} == set(followup.PORTFOLIO_IDS)
    assert {float(row["cost_assumption_bps"]) for row in full} == {
        0.0,
        5.0,
        10.0,
    }
    assert {row["evaluation_start"] for row in full} == {"2010-08-10"}
    assert {row["evaluation_end"] for row in full} == {"2026-06-18"}
    benchmarks = rows("benchmark_reference_log.csv")
    assert len(benchmarks) == 6
    assert {row["benchmark_or_control_id"] for row in benchmarks} == set(
        followup.CONTROL_IDS
    )


def test_inner_outer_turnover_and_costs_are_separate() -> None:
    turnover = rows("turnover_cost_reconciliation.csv")
    assert len(turnover) == 7 * 3
    candidate = next(
        row
        for row in turnover
        if row["portfolio_id"]
        == "80pct_reference_20pct_decelerated_psar_candidate"
        and float(row["cost_assumption_bps"]) == 5.0
    )
    assert float(candidate["inner_turnover"]) > 0.0
    assert float(candidate["outer_turnover"]) > 0.0
    assert float(candidate["inner_transaction_cost_drag"]) > 0.0
    assert float(candidate["outer_transaction_cost_drag"]) > 0.0
    assert candidate["costs_charged_once"].lower() == "true"


def test_halves_and_rolling_windows_remain_complete_and_unfavorable_visible() -> None:
    halves = rows("chronological_half_portfolio_results.csv")
    assert len(halves) == 7 * 2
    assert {row["period_label"] for row in halves} == {
        "first_chronological_half",
        "second_chronological_half",
    }
    assert all("not_validation" in row["period_role"] for row in halves)
    rolling36 = rows("rolling_36_month_portfolio_results.csv")
    rolling60 = rows("rolling_60_month_portfolio_results.csv")
    assert rolling36 and rolling60
    assert len({row["window_sequence"] for row in rolling36}) == 155
    assert len({row["window_sequence"] for row in rolling60}) == 131
    assert {row["comparison_portfolio_id"] for row in rolling36} == {
        "100pct_frozen_reference",
        "80pct_reference_20pct_original_psar_control",
        "80pct_reference_20pct_decelerated_psar_exposure_matched_control",
    }
    assert all(row["validation_claimed"].lower() == "false" for row in rolling36 + rolling60)
    assert any(
        row["control_dominates_candidate"].lower() == "true"
        or float(row["sharpe_difference"]) < 0.0
        for row in rolling36 + rolling60
    )


def test_downside_and_mechanism_diagnostics_are_present() -> None:
    downside = rows("reference_negative_month_results.csv")
    mechanism = rows("candidate_mechanism_diagnostics.csv")
    assert len(downside) == 7
    assert all(int(row["reference_negative_month_count"]) > 0 for row in downside)
    assert mechanism
    assert all(row["PSAR_formula_changed"].lower() == "false" for row in mechanism)
    assert all(row["AF_parameters_changed"].lower() == "false" for row in mechanism)


def test_outcome_gate_next_action_and_entity_counts_reconcile() -> None:
    outcome = rows("outcome_summary.csv")[0]
    assert outcome["outcome"] in followup.ALLOWED_OUTCOMES
    assert outcome["failure_reason"] in followup.ALLOWED_FAILURE_REASONS
    expected = followup.next_action_for_outcome(outcome["outcome"])
    assert outcome["next_action"] == expected
    funnel = payload("cohort_funnel_counts.json")
    assert funnel["outcome_count_reconciles"] is True
    assert funnel["existing_strategy_configuration_carried_forward_count"] == 1
    assert funnel["new_strategy_configuration_count"] == 0
    assert funnel["new_experiment_trial_count"] == 1
    assert funnel["benchmark_reference_count"] == 6


def test_protected_state_caches_parent_evidence_and_reruns_are_deterministic() -> None:
    protected_before = {
        path: sha256(path)
        for path in followup.PROTECTED_STATE_PATHS
        if path.exists()
    }
    cache_before = {
        path: sha256(path) for path in followup.cache_inventory_files()
    }
    parent_before = {
        path: sha256(path) for path in followup.parent_evidence_paths()
    }
    first = followup.run()
    names = {path.name for path in OUTPUT.iterdir() if path.is_file()}
    first_bytes = {name: (OUTPUT / name).read_bytes() for name in names}
    second = followup.run()
    second_bytes = {name: (OUTPUT / name).read_bytes() for name in names}
    protected_after = {
        path: sha256(path)
        for path in followup.PROTECTED_STATE_PATHS
        if path.exists()
    }
    cache_after = {
        path: sha256(path) for path in followup.cache_inventory_files()
    }
    parent_after = {
        path: sha256(path) for path in followup.parent_evidence_paths()
    }
    assert first["overall_pass"] is True
    assert second["overall_pass"] is True
    assert first_bytes == second_bytes
    assert protected_before == protected_after
    assert cache_before == cache_after
    assert parent_before == parent_after
