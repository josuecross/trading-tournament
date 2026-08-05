from __future__ import annotations

import csv
import json
from datetime import datetime, timezone

import pytest
import yaml

from strategy_lab.research_os.research import (
    correct_faa_stage_and_onboard_paper_demo_observation_v1 as task,
)


def rows(name: str) -> list[dict[str, str]]:
    with (task.OUTPUT_DIR / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def require_output() -> None:
    if not (task.OUTPUT_DIR / "consistency_check.json").exists():
        pytest.skip("artifact assertions run after the serial onboarding runner")


def test_standard_framework_compatibility_and_virtual_accounting_fixture() -> None:
    compatibility, passed = task.standard_framework_compatibility()
    fixture = task.virtual_accounting_fixture()
    assert passed is True
    assert {row["status"] for row in compatibility} == {"pass"}
    assert {row["custom_faa_framework_required"] for row in compatibility} == {False}
    assert fixture["weight_sum_pass"] is True
    assert fixture["equity_reconciliation_pass"] is True
    assert fixture["broker_calls"] == 0
    assert fixture["orders_created"] == 0


def test_initial_target_reconciles_before_august_3_close() -> None:
    now = datetime(2026, 8, 3, 1, 0, tzinfo=timezone.utc)
    formation, reconciliation, passed = task.reconcile_formation(now)
    assert passed is True
    assert formation["selection"] == ["SPY", "VNQ", "SHY"]
    assert {row["status"] for row in reconciliation} == {"pass"}


def test_frozen_strategy_fingerprint_is_deterministic() -> None:
    assert task.strategy_fingerprint() == task.strategy_fingerprint()
    assert task.INITIAL_TARGET["SPY"] == 1.0 / 3.0
    assert task.INITIAL_TARGET["SHY"] == 1.0 / 3.0
    assert task.INITIAL_TARGET["VNQ"] == 1.0 / 3.0
    assert sum(task.INITIAL_TARGET.values()) == 1.0


def test_output_records_exact_entity_separation() -> None:
    require_output()
    manifest = yaml.safe_load(
        (task.OUTPUT_DIR / "onboarding_manifest.yaml").read_text(encoding="utf-8")
    )
    assert manifest["existing_strategy_configurations_used"] == 1
    assert manifest["new_strategy_configurations"] == 0
    assert manifest["strategy_lifecycle_records_updated"] == 1
    assert manifest["direction_correction_records"] == 1
    assert manifest["prior_validation_workflows_superseded"] == 1
    assert manifest["paper_demo_observations_created"] == 1
    assert manifest["new_experiment_trials"] == 0
    assert manifest["new_robustness_trials"] == 0
    assert manifest["validation_observations_created"] == 0
    assert manifest["broker_or_paper_orders"] == 0


def test_registry_and_active_observation_have_exact_faa_records() -> None:
    require_output()
    registry = task.registry_entries(task.REGISTRY_PATH.read_text(encoding="utf-8"))
    active = task.active_entries(task.ACTIVE_OBSERVATIONS_PATH.read_text(encoding="utf-8"))
    lifecycle = [row for row in registry if row.get("id") == task.STRATEGY_ID]
    observations = [row for row in active if row.get("observation_id") == task.OBSERVATION_ID]
    assert len(lifecycle) == 1
    assert lifecycle[0]["entity_type"] == "strategy_lifecycle_record"
    assert lifecycle[0]["stage"] == "paper-demo-eligibility"
    assert lifecycle[0]["eligibility"] == "paper_demo_eligible"
    assert lifecycle[0]["eligible_route"] == "standalone_only"
    assert lifecycle[0]["real_money_authorized"] is False
    assert len(observations) == 1
    assert observations[0]["state"] == "active_accepted_frozen_observation"
    assert observations[0]["paper_forward_active"] is True


def test_prior_custom_validation_is_preserved_but_superseded() -> None:
    require_output()
    trial = task.read_yaml(task.ACTIVE_VALIDATION_DIR / "trial_state.yaml")
    counters = task.read_yaml(task.ACTIVE_VALIDATION_DIR / "observation_counters.yaml")
    transition = task.read_yaml(task.TRANSITION_PATH)
    assert trial["trial_id"] == task.PRIOR_TRIAL_ID
    assert trial["status"] == "superseded_nonblocking_workflow"
    assert trial["validation_outcome"] == ""
    assert trial["completed_validation_claim"] is False
    assert trial["paper_demo_blocker"] is False
    assert trial["continue_custom_recorder"] is False
    assert counters["validation_observation_id"] == task.PRIOR_OBSERVATION_ID
    assert counters["validation_decision"] == ""
    assert counters["performance_rows_transferred"] == 0
    assert transition["replacement_observation"] == task.OBSERVATION_ID


def test_standard_observation_is_active_pending_execution_with_empty_ledger() -> None:
    require_output()
    observation = task.read_yaml(task.OBSERVATION_YAML)
    ledger_rows = task.read_csv(task.COMPONENT_LEDGER)
    with task.COMPONENT_LEDGER.open(newline="", encoding="utf-8") as handle:
        fields = tuple(next(csv.reader(handle)))
    assert observation["status"] == "active_paper_demo_observation"
    assert observation["initialization_status"] == "scheduled_for_first_prospective_execution"
    assert observation["scheduled_first_execution_date"] == "2026-08-03"
    assert observation["first_eligible_performance_date"] == "2026-08-04"
    assert observation["historical_backfill"] is False
    assert observation["historical_performance_rows_imported"] == 0
    assert observation["broker_integration"] is False
    assert ledger_rows == []
    assert fields == task.STANDARD_LEDGER_FIELDS


def test_evidence_packet_and_consistency_pass() -> None:
    require_output()
    check = json.loads(
        (task.OUTPUT_DIR / "consistency_check.json").read_text(encoding="utf-8")
    )
    assert {path.name for path in task.OUTPUT_DIR.iterdir() if path.is_file()} == task.REQUIRED_OUTPUTS
    assert check["overall_pass"] is True
    assert check["protected_state_cache_and_prior_evidence_unchanged"] is True
    assert check["historical_performance_rows_imported"] == 0
    assert check["standard_component_ledger_rows"] == 0
    assert check["custom_recorder_continues"] is False
    assert check["validation_outcome_claimed"] is False
    assert check["broker_calls"] == 0
    assert check["real_money_authorization"] is False


def test_exact_outcome_and_next_action() -> None:
    require_output()
    outcome = rows("outcome_summary.csv")
    assert len(outcome) == 1
    assert outcome[0]["outcome"] == task.OUTCOME_ONBOARDED
    assert outcome[0]["next_action"] == task.NEXT_ONBOARDED
    assert outcome[0]["performance_rows_created"] == "0"
    assert rows("failure_reasons.csv") == []
