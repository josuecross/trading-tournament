from __future__ import annotations

import csv
import json
from datetime import date

import pytest
import yaml

from strategy_lab.research_os.research import (
    correct_ivts_trial_lineage_and_run_exploration_v4 as task,
)


@pytest.fixture(scope="module")
def result() -> dict[str, object]:
    return task.run()


def rows(name: str) -> list[dict[str, str]]:
    with (task.OUTPUT_DIR / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_required_artifacts_exist(result: dict[str, object]) -> None:
    assert result["consistency_passed"] is True
    assert all((task.OUTPUT_DIR / name).exists() for name in task.REQUIRED_ARTIFACTS)


def test_v1_is_only_trial_parent(result: dict[str, object]) -> None:
    ledger = rows("trial_ledger.csv")
    child = [row for row in ledger if row["created_in_v4"] == "true"]
    assert len(child) == 1
    assert child[0]["trial_id"] == task.TRIAL_ID
    assert child[0]["parent_trial_id"] == task.PARENT_TRIAL_ID
    assert child[0]["record_role"] == "new_V4_child_exploration_trial"


def test_v2_and_v3_are_not_fabricated_trials(result: dict[str, object]) -> None:
    check = json.loads((task.OUTPUT_DIR / "consistency_check.json").read_text(encoding="utf-8"))
    assert check["V2_experiment_trial_count"] == 0
    assert check["V3_experiment_trials_created"] == 0
    lineage = rows("data_and_process_lineage.csv")
    assert {row["entity_type"] for row in lineage} == {
        "data_capability_lineage",
        "process_methodology_lineage",
    }
    assert all(row["used_as_parent_trial"] == "false" for row in lineage)


def test_official_history_hashes_reproduce_without_download(result: dict[str, object]) -> None:
    reconciliation = rows("official_history_hash_reconciliation.csv")
    assert len(reconciliation) == 4
    assert {row["series"] for row in reconciliation} == {"VIX", "VIX3M"}
    assert all(row["status"] == "pass" for row in reconciliation)
    assert all(row["network_request_performed"] == "false" for row in reconciliation)


def test_frozen_strategy_and_timing_are_preserved(result: dict[str, object]) -> None:
    ledger = next(row for row in rows("trial_ledger.csv") if row["created_in_v4"] == "true")
    for field in (
        "strategy_rule_changed",
        "ratio_changed",
        "median_length_changed",
        "thresholds_changed",
        "instruments_changed",
        "target_allocations_changed",
        "following_session_execution_changed",
        "optimization_performed",
        "post_result_adaptation_allowed",
    ):
        assert ledger[field] == "false"
    manifest = yaml.safe_load((task.OUTPUT_DIR / "correction_manifest.yaml").read_text(encoding="utf-8"))
    assert manifest["timing_policy"] == task.TIMING_POLICY
    assert manifest["vintage_status"] == "current_history_non_vintage"


def test_candidate_and_all_controls_run_at_frozen_costs(result: dict[str, object]) -> None:
    all_results = rows("all_trial_results.csv")
    controls = rows("control_results.csv")
    assert len(all_results) == 21
    assert len(controls) == 18
    assert {float(row["cost_bps"]) for row in all_results} == {0.0, 5.0, 10.0}
    assert {row["entity_id"] for row in controls} == set(task.BENCHMARKS)
    benchmark_rows = {
        row["benchmark_reference_id"]: row
        for row in rows("benchmark_reference_log.csv")
    }
    assert benchmark_rows["SPY_200_day_trend_control"]["instrument_universe"] == "SPY|BIL"


def test_following_session_timing_and_invariants_pass(result: dict[str, object]) -> None:
    invariants = rows("invariant_results.csv")
    assert len(invariants) == 21
    assert all(row["signal_date_return_used"] == "false" for row in invariants)
    assert all(row["following_open_execution_used"] == "false" for row in invariants)
    assert all(row["stale_weight_forward_fill_used"] == "false" for row in invariants)
    assert all(row["invariant_pass"] == "true" for row in invariants)
    signal_rows = [
        row
        for row in rows("state_signal_diagnostics.csv")
        if row["record_type"] == "signal_observation"
        and row["following_execution_session"]
    ]
    assert all(
        date.fromisoformat(row["following_execution_session"])
        > date.fromisoformat(row["signal_date"])
        for row in signal_rows
    )


def test_state_diagnostics_disclose_non_vintage_status(result: dict[str, object]) -> None:
    diagnostics = rows("state_signal_diagnostics.csv")
    signal_rows = [row for row in diagnostics if row["record_type"] == "signal_observation"]
    assert signal_rows
    assert all(row["vintage_status"] == "current_history_non_vintage" for row in signal_rows)
    assert all(row["same_day_return_allowed"] == "false" for row in signal_rows)
    assert any(row["record_type"] == "state_summary" for row in diagnostics)
    assert any(row["record_type"] == "missing_common_observation_summary" for row in diagnostics)


def test_chronological_halves_are_descriptive_only(result: dict[str, object]) -> None:
    half = rows("chronological_half_results.csv")
    assert len(half) == 14
    assert {row["period"] for row in half} == {
        "first_chronological_half",
        "second_chronological_half",
    }


def test_portfolio_diagnostics_use_explicit_monthly_holdings(result: dict[str, object]) -> None:
    portfolios = rows("portfolio_contribution_results.csv")
    assert len(portfolios) == 15
    non_reference = [
        row
        for row in portfolios
        if row["portfolio_id"] != "frozen_current_active_vm_dsr_usci_combo"
    ]
    assert all(row["daily_fixed_weight_return_blend_used"] == "false" for row in non_reference)
    assert all(row["explicit_holdings_used"] == "true" for row in non_reference)
    assert all(row["natural_drift_used"] == "true" for row in non_reference)


def test_outcome_and_next_action_are_controlled(result: dict[str, object]) -> None:
    outcome = rows("outcome_summary.csv")[0]
    assert outcome["outcome"] in {
        "exploratory_followup_candidate_standalone",
        "closed_exploration",
        "inconclusive_data_issue",
        "blocked_feasibility",
    }
    assert outcome["next_action"] in {
        task.ADVANCE_NEXT_ACTION,
        task.CLOSE_NEXT_ACTION,
        task.BLOCK_NEXT_ACTION,
    }
    assert outcome["validation_or_point_in_time_proof"] == "false"
    assert outcome["paper_demo_eligibility_supported"] == "false"


def test_protected_state_prior_evidence_and_cache_are_unchanged(
    result: dict[str, object],
) -> None:
    check = json.loads((task.OUTPUT_DIR / "consistency_check.json").read_text(encoding="utf-8"))
    assert check["protected_state_unchanged"] is True
    assert check["prior_evidence_unchanged"] is True
    assert check["cache_unchanged"] is True
    assert not any(check["forbidden_actions"].values())


def test_generation_is_deterministic(result: dict[str, object]) -> None:
    first = json.loads((task.OUTPUT_DIR / "consistency_check.json").read_text(encoding="utf-8"))
    rerun = task.run()
    second = json.loads((task.OUTPUT_DIR / "consistency_check.json").read_text(encoding="utf-8"))
    assert rerun["consistency_passed"] is True
    assert first["deterministic_core_hash"] == second["deterministic_core_hash"]
