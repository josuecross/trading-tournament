from __future__ import annotations

import csv
import json
from datetime import datetime, timezone

import pytest
import yaml

from strategy_lab.research_os.research import (
    correct_psar_stage_and_onboard_paper_demo_observation_v1 as task,
)


FIXED_NOW = datetime(2026, 8, 3, 4, 0, tzinfo=timezone.utc)


def test_frozen_identity_route_and_fingerprint_are_deterministic() -> None:
    assert task.STRATEGY_ID == "barbara_decelerated_psar_spy_bil_v1"
    assert task.ROUTE == "20pct_diversifier_only"
    assert task.REFERENCE_WEIGHT == 0.80
    assert task.PSAR_WEIGHT == 0.20
    assert task.strategy_fingerprint() == task.strategy_fingerprint()


def test_reference_and_psar_reconcile_but_require_pending_boundary() -> None:
    reference = task.reference_state_reconciliation(FIXED_NOW)
    psar = task.psar_state_reconciliation(FIXED_NOW)
    combined = task.combined_target(reference, psar)
    assert reference["status"] == "active_paper_demo_observation"
    assert reference["data_freshness"] == "stale_or_incomplete"
    assert psar["state_reconciled"] is True
    assert psar["latest_completed_signal_date"] == "2026-06-18"
    assert psar["sleeve_target"] == {"SPY": 1.0, "BIL": 0.0}
    assert combined["safe_for_execution"] is False
    assert combined["initialization_status"] == "pending_first_valid_signal_or_execution"
    assert combined["weight_sum"] == pytest.approx(1.0)


def test_standard_composite_fixture_charges_cost_once() -> None:
    rows, passed = task.standard_framework_compatibility()
    fixture = task.virtual_accounting_fixture()
    assert passed is True
    assert len(rows) == 9
    assert fixture["weight_sum_pass"] is True
    assert fixture["equity_reconciliation_pass"] is True
    assert fixture["transaction_cost_charged_once"] is True
    assert fixture["orders_created"] == 0
    assert fixture["broker_calls"] == 0


def test_preflight_preserves_standalone_closure_and_positive_route() -> None:
    if task.OBSERVATION_DIR.exists():
        pytest.skip("post-run preflight intentionally rejects duplicate onboarding")
    result = task.preflight(FIXED_NOW)
    assert result["passed"] is True
    assert result["checks"]["standalone_closure_exact"] is True
    assert result["checks"]["robustness_positive_exact"] is True
    assert result["checks"]["prior_workflow_zero_performance"] is True
    assert result["checks"]["faa_observation_present_for_preservation"] is True


def _require_artifacts() -> None:
    if not task.OUTPUT_DIR.exists():
        pytest.skip("onboarding artifacts have not been generated")


def test_required_packet_and_outcome() -> None:
    _require_artifacts()
    assert {path.name for path in task.OUTPUT_DIR.iterdir() if path.is_file()} == task.REQUIRED_OUTPUTS
    with (task.OUTPUT_DIR / "outcome_summary.csv").open(newline="", encoding="utf-8") as handle:
        row = next(csv.DictReader(handle))
    assert row["outcome"] == task.OUTCOME_ONBOARDED
    assert row["initialization_status"] == "pending_first_valid_signal_or_execution"
    assert row["performance_rows_created"] == "0"
    assert row["next_action"] == task.NEXT_ONBOARDED


def test_registry_and_active_inventory_have_exactly_one_psar_record() -> None:
    _require_artifacts()
    registry = yaml.safe_load(task.REGISTRY_PATH.read_text(encoding="utf-8"))
    active = yaml.safe_load(task.ACTIVE_OBSERVATIONS_PATH.read_text(encoding="utf-8"))
    registry_rows = [
        row for row in registry["strategies"]
        if row.get("id") == task.STRATEGY_ID or row.get("strategy_id") == task.STRATEGY_ID
    ]
    active_rows = [
        row for row in active["active_observations"]
        if row.get("observation_id") == task.OBSERVATION_ID
    ]
    assert len(registry_rows) == 1
    assert registry_rows[0]["eligibility"] == "paper_demo_eligible"
    assert registry_rows[0]["eligible_route"] == task.ROUTE
    assert registry_rows[0]["historical_standalone_outcome"] == "closed_exploration"
    assert registry_rows[0]["historical_standalone_failure_reason"] == "benchmark_like_behavior"
    assert len(active_rows) == 1
    assert active_rows[0]["status"] == "active_paper_demo_observation"
    assert active_rows[0]["initialization_status"] == "pending_first_valid_signal_or_execution"


def test_standard_observation_is_pending_and_ledger_is_header_only() -> None:
    _require_artifacts()
    observation = yaml.safe_load(task.OBSERVATION_YAML.read_text(encoding="utf-8"))
    with task.COMPONENT_LEDGER.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fields = tuple(reader.fieldnames or ())
    assert observation["current_target_allocation"] == {}
    assert observation["scheduled_first_execution_date"] == ""
    assert observation["historical_backfill"] is False
    assert observation["historical_performance_rows_imported"] == 0
    assert rows == []
    assert fields == task.COMPOSITE_LEDGER_FIELDS
    assert set(task.STANDARD_CORE_LEDGER_FIELDS).issubset(fields)


def test_faa_and_protected_state_are_unchanged() -> None:
    _require_artifacts()
    with (task.OUTPUT_DIR / "faa_observation_preservation_check.csv").open(
        newline="", encoding="utf-8"
    ) as handle:
        rows = list(csv.DictReader(handle))
    consistency = json.loads(
        (task.OUTPUT_DIR / "consistency_check.json").read_text(encoding="utf-8")
    )
    assert all(row["unchanged"] == "true" for row in rows)
    assert consistency["faa_active_record_unchanged"] is True
    assert consistency["protected_state_cache_and_prior_evidence_unchanged"] is True
    assert consistency["overall_pass"] is True


def test_entity_counts_and_no_orders() -> None:
    _require_artifacts()
    manifest = yaml.safe_load(
        (task.OUTPUT_DIR / "onboarding_manifest.yaml").read_text(encoding="utf-8")
    )
    assert manifest["existing_strategy_configurations_used"] == 1
    assert manifest["new_strategy_configurations"] == 0
    assert manifest["paper_demo_observations_created"] == 1
    assert manifest["benchmark_references_carried_forward"] == 6
    assert manifest["new_experiment_trials"] == 0
    assert manifest["validation_observations_created"] == 0
    assert manifest["broker_or_paper_orders"] == 0
