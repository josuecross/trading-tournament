from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest
import yaml

from run_strategy_lab import validate_registry_data
from strategy_lab.research_os.research import defer_angl_observation_data_lane_v1 as task


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "lifecycle" / task.TASK_ID / "latest"


@pytest.fixture(scope="module", autouse=True)
def evidence_ready() -> None:
    assert (EVIDENCE / "consistency_check.json").exists(), (
        "Run the dedicated lifecycle runner before focused tests."
    )


def rows(name: str) -> list[dict[str, str]]:
    with (EVIDENCE / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def payload(name: str) -> dict[str, object]:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def yaml_payload(path: Path) -> dict[str, object]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def strategy_record() -> dict[str, object]:
    registry = yaml_payload(ROOT / "strategy_lab" / "strategy_registry.yaml")
    matches = [
        row
        for row in registry["strategies"]
        if row.get("id") == task.STRATEGY_ID
    ]
    assert len(matches) == 1
    return matches[0]


def observation_record() -> dict[str, object]:
    active = yaml_payload(
        ROOT
        / "strategy_lab"
        / "research_os"
        / "operations"
        / "active_observations.yaml"
    )
    matches = [
        row
        for row in active["active_observations"]
        if row.get("observation_id") == task.OBSERVATION_ID
    ]
    assert len(matches) == 1
    return matches[0]


def test_required_packet_and_exact_counts() -> None:
    required = {
        "deferral_manifest.yaml",
        "strategy_cards.csv",
        "trial_ledger.csv",
        "paper_demo_observations.csv",
        "data_capability_task_log.csv",
        "process_task_log.csv",
        "deferral_decision.csv",
        "reopen_conditions.csv",
        "state_change_manifest.csv",
        "outcome_summary.csv",
        "failure_reasons.csv",
        "next_actions.csv",
        "consistency_check.json",
        "deferral_report.md",
    }
    assert required.issubset({path.name for path in EVIDENCE.iterdir()})
    manifest = yaml_payload(EVIDENCE / "deferral_manifest.yaml")
    assert manifest["task_id"] == task.TASK_ID
    assert manifest["mode"] == "active-direction-execution"
    assert manifest["stage"] == "correction"
    assert manifest["process_outcome"] == "observation_data_lane_deferred"
    assert manifest["failure_reason"] == "data_or_comparability_failure"
    assert manifest["strategy_configurations_created"] == 0
    assert manifest["strategy_configurations_updated"] == 1
    assert manifest["experiment_trials_created"] == 0
    assert manifest["existing_trials_carried_forward"] == 3
    assert manifest["observations_created"] == 0
    assert manifest["observations_updated"] == 1
    assert manifest["observations_activated"] == 0
    assert manifest["forward_records_created"] == 0
    assert manifest["new_data_capability_tasks"] == 0
    assert manifest["process_tasks"] == 1


def test_strategy_eligibility_and_frozen_construction_are_preserved() -> None:
    strategy = strategy_record()
    assert strategy["entity_type"] == "strategy_configuration"
    assert strategy["family_id"] == "fallen_angel_credit_anomaly"
    assert strategy["stage"] == "paper_demo_eligible"
    assert strategy["outcome"] == "paper_demo_eligible"
    assert strategy["route"] == "diversifier_only"
    assert (
        strategy["validated_portfolio_use"]
        == "80pct_frozen_reference_20pct_ANGL_monthly_rebalanced"
    )
    assert strategy["parameters"]["assigned_portfolio_sleeve_weight"] == 0.2
    assert strategy["parameters"]["portfolio_rebalance_frequency"] == "monthly"
    assert strategy["standalone_100pct_angl_observation_approved"] is False
    assert strategy["real_money_authorized"] is False
    assert strategy["paper_demo_active"] is False
    assert strategy["next_action"] == task.OBSERVATION_NEXT_ACTION
    assert strategy["allowed_next_action"] == "no_action"
    assert strategy["observation_stage"] == "deferred"
    assert strategy["observation_failure_reason"] == "data_or_comparability_failure"


def test_observation_is_deferred_in_place_without_forward_evidence() -> None:
    observation = observation_record()
    assert observation["entity_type"] == "paper_demo_observation"
    assert observation["stage"] == "deferred"
    assert observation["semantic_stage"] == "deferred"
    assert observation["outcome"] == "observation_invalid_or_incomplete"
    assert observation["failure_reason"] == "data_or_comparability_failure"
    assert observation["adaptation_label"] == "paper_demo_observation_fix"
    assert observation["observation_route"] == "diversifier_only"
    assert observation["target_weights"] == {"frozen_reference": 0.8, "ANGL": 0.2}
    assert observation["rebalance_frequency"] == "monthly"
    assert observation["cost_assumption"] == "5_bps_per_one_way_turnover"
    assert observation["paper_forward_active"] is False
    assert observation["paper_demo_active"] is False
    assert observation["first_forward_observation_date"] == ""
    assert observation["forward_records_created"] == 0
    assert observation["valid_forward_record_count"] == 0
    assert observation["deferred_reason"] == task.DEFERRED_REASON
    assert observation["automatic_remediation_attempts_exhausted"] is True
    assert observation["last_attempted_session"] == "2026-07-24"
    assert observation["last_data_outcome"] == task.FINAL_DATA_OUTCOME
    assert observation["next_action"] == task.OBSERVATION_NEXT_ACTION
    assert observation["june_18_record_classification"] == "historical_reconciliation_only"


def test_reopen_conditions_require_material_change() -> None:
    reopen = {row["condition_id"]: row for row in rows("reopen_conditions.csv")}
    assert set(reopen) == {
        "authorized_provider_deterministic_full_cohort",
        "canonical_pipeline_materially_corrected_and_verified",
        "separately_approved_observation_methodology_change",
        "elapsed_time_alone",
    }
    assert reopen["elapsed_time_alone"]["material_change_required"] == "false"
    assert {
        row["approved_or_implemented_in_this_task"] for row in reopen.values()
    } == {"false"}
    observation = observation_record()
    assert observation["elapsed_time_alone_reopen_condition"] is False


def test_existing_trials_and_data_tasks_are_read_only() -> None:
    trials = rows("trial_ledger.csv")
    data_tasks = rows("data_capability_task_log.csv")
    assert len(trials) == 3
    assert {row["entity_type"] for row in trials} == {"experiment_trial"}
    assert {row["read_only"] for row in trials} == {"true"}
    assert {row["new_trial_created"] for row in trials} == {"false"}
    assert len(data_tasks) == 20
    assert {row["entity_type"] for row in data_tasks} == {"data_capability_task"}
    assert {row["read_only"] for row in data_tasks} == {"true"}
    assert {row["new_data_capability_task_created"] for row in data_tasks} == {
        "false"
    }
    assert {row["counted_as_strategy"] for row in data_tasks} == {"false"}
    assert {row["counted_as_trial"] for row in data_tasks} == {"false"}


def test_process_outcome_and_next_actions_are_exact() -> None:
    process = rows("process_task_log.csv")
    assert process == [
        {
            "task_id": task.TASK_ID,
            "entity_type": "process_task",
            "stage": "correction",
            "outcome": "observation_data_lane_deferred",
            "failure_reason": "data_or_comparability_failure",
            "next_action": "refresh_strategy_source_library_v3",
            "counted_as_strategy": "false",
            "counted_as_trial": "false",
            "provider_called": "false",
            "cache_modified": "false",
        }
    ]
    actions = {row["action_scope"]: row for row in rows("next_actions.csv")}
    assert actions["ANGL_observation"]["exact_next_action"] == task.OBSERVATION_NEXT_ACTION
    assert actions["project"]["exact_next_action"] == "refresh_strategy_source_library_v3"
    assert {row["execute_in_this_task"] for row in actions.values()} == {"false"}


def test_only_two_authorized_source_of_truth_files_changed() -> None:
    state = rows("state_change_manifest.csv")
    changed = {row["path"] for row in state if row["changed"] == "true"}
    assert changed == {
        "strategy_lab/strategy_registry.yaml",
        "strategy_lab/research_os/operations/active_observations.yaml",
    }
    assert {
        row["change_permitted"]
        for row in state
        if row["changed"] == "true"
    } == {"true"}
    assert {
        row["changed"]
        for row in state
        if row["path_type"]
        in {
            "protected_prior_evidence",
            "protected_operational_forward_file",
            "protected_market_data_cache_or_metadata",
        }
    } <= {"false"}


def test_registry_active_state_and_guardrails_validate() -> None:
    registry = yaml_payload(ROOT / "strategy_lab" / "strategy_registry.yaml")
    active = yaml_payload(
        ROOT
        / "strategy_lab"
        / "research_os"
        / "operations"
        / "active_observations.yaml"
    )
    assert validate_registry_data(registry)["passed"] is True
    assert task.validate_active_observation_document(active)["passed"] is True
    check = payload("consistency_check.json")
    assert check["consistency_passed"] is True
    assert check["literal_deferred_stage_accepted"] is True
    assert check["prior_evidence_unchanged"] is True
    assert check["market_data_cache_and_metadata_unchanged"] is True
    assert check["operational_forward_files_unchanged"] is True
    assert check["provider_called"] is False
    assert check["cache_modified"] is False
    assert check["backtest_or_validation_run"] is False
    assert check["broker_account_position_order_endpoint_called"] is False
    assert check["paper_or_live_order_submitted"] is False
    assert check["real_money_action"] is False


def test_runner_has_no_provider_backtest_or_broker_dependency() -> None:
    source = Path(task.__file__).read_text(encoding="utf-8")
    forbidden = {
        "from src.data import",
        "_download_yfinance(",
        "load_symbol_data(",
        "yfinance.",
        "alpaca.",
        "run_backtest(",
        "submit_order(",
    }
    assert not {token for token in forbidden if token in source.lower()}


def test_proposals_are_deterministic_without_state_mutation() -> None:
    registry = yaml_payload(ROOT / "strategy_lab" / "strategy_registry.yaml")
    active = yaml_payload(
        ROOT
        / "strategy_lab"
        / "research_os"
        / "operations"
        / "active_observations.yaml"
    )
    strategy = task.strategy_records(registry)[0]
    observation = task.observation_records(active)[0]
    assert task.proposed_strategy_record(strategy) == task.proposed_strategy_record(
        strategy
    )
    assert task.proposed_observation_record(
        observation
    ) == task.proposed_observation_record(observation)
