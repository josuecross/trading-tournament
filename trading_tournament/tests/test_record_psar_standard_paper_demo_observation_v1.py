from __future__ import annotations

import csv
import json
from datetime import datetime, timezone

import pytest
import yaml

from strategy_lab.research_os.research import (
    record_psar_standard_paper_demo_observation_v1 as task,
)


FIXED_NOW = datetime(2026, 8, 3, 17, 0, tzinfo=timezone.utc)


def test_required_symbol_scope_is_frozen_and_complete() -> None:
    assert task.REQUIRED_SYMBOLS == (
        "BIL",
        "QUAL",
        "SPY",
        "SPLV",
        "USCI",
        "USMV",
        "XLB",
        "XLC",
        "XLE",
        "XLF",
        "XLI",
        "XLK",
        "XLP",
        "XLU",
        "XLV",
        "XLY",
    )


def test_offline_gate_and_fixture_pass_without_network() -> None:
    rows, passed, fixture = task.offline_gate()
    repeated_rows, repeated_pass, repeated_fixture = task.offline_gate()
    assert passed is False
    assert repeated_pass is False
    assert repeated_rows == rows
    assert repeated_fixture == fixture
    assert len(rows) == 15
    assert all(row["provider_access_required"] is False for row in rows)
    status = {row["check_id"]: row["status"] for row in rows}
    assert status["admitted_initialization_status"] == "fail"
    assert status["no_completed_virtual_execution"] == "fail"
    assert status["standard_ledger_empty"] == "fail"
    assert fixture["weight_sum_pass"] is True
    assert fixture["equity_pass"] is True
    assert fixture["cost_charged_once"] is True
    assert fixture["performance_rows"] == 0
    assert fixture["orders_created"] == 0


def test_frozen_target_rerun_waits_without_another_provider_cycle() -> None:
    observation = yaml.safe_load(task.OBSERVATION_YAML.read_text(encoding="utf-8"))
    assert task.frozen_target_waiting_for_execution(
        observation, task.date(2026, 7, 31)
    ) is False
    assert task.frozen_target_waiting_for_execution(
        observation, task.date(2026, 8, 3)
    ) is False
    assert observation["initialization_status"] == "initialized_active_recording"
    assert observation["initialization_execution_date"] == "2026-08-03"
    active = task.active_payload()
    matching = [
        row
        for row in active["active_observations"]
        if row.get("observation_id") == task.OBSERVATION_ID
    ]
    assert len(matching) == 1


def test_timing_uses_latest_completed_session_and_future_close() -> None:
    assert task.latest_fully_completed_session(FIXED_NOW).isoformat() == "2026-07-31"
    assert task.next_initialization_close(FIXED_NOW, task.date(2026, 7, 31)).isoformat() == "2026-08-03"


def test_target_calculations_are_deterministic_on_fixture() -> None:
    target = task.aggregate_target(
        {"SPY": 0.5, "BIL": 0.5},
        {"SPY": 1.0, "BIL": 0.0},
    )
    assert target == {"BIL": pytest.approx(0.4), "SPY": pytest.approx(0.6)}
    assert sum(target.values()) == pytest.approx(1.0)


def _latest() -> task.Path:
    if task.RUN_ROOT.exists():
        for value in sorted(
            (path for path in task.RUN_ROOT.iterdir() if path.is_dir()),
            reverse=True,
        ):
            if (value / "target_freeze_record.csv").exists():
                return value
    pytest.skip("target-freeze recorder has not generated an immutable run packet")


def test_run_packet_contains_all_required_outputs() -> None:
    output = _latest()
    assert {path.name for path in output.iterdir() if path.is_file()} == task.REQUIRED_TOP_LEVEL_OUTPUTS
    assert (output / "raw").is_dir()
    assert (output / "normalized").is_dir()


def test_target_freeze_does_not_initialize_or_create_performance() -> None:
    output = _latest()
    outcome = next(csv.DictReader((output / "outcome_summary.csv").open(newline="", encoding="utf-8")))
    observation = yaml.safe_load(task.OBSERVATION_YAML.read_text(encoding="utf-8"))
    assert outcome["outcome"] == task.OUTCOME_TARGET_FROZEN
    assert outcome["performance_rows_created"] == "0"
    assert task.read_csv(output / "virtual_initialization_record.csv") == []
    assert task.read_csv(output / "new_performance_rows.csv") == []
    assert observation["initialization_status"] == "initialized_active_recording"
    assert observation["performance_rows"] == 0
    assert observation["scheduled_target_allocation"]
    assert observation["historical_backfill"] is False
    assert len(task.read_csv(task.COMPONENT_LEDGER)) == 1


def test_provider_scope_and_no_order_calls() -> None:
    output = _latest()
    attempt = next(csv.DictReader((output / "provider_attempt_log.csv").open(newline="", encoding="utf-8")))
    manifest = yaml.safe_load((output / "recording_manifest.yaml").read_text(encoding="utf-8"))
    assert attempt["bounded_cycles"] == "1"
    assert attempt["account_endpoint_called"] == "false"
    assert attempt["position_endpoint_called"] == "false"
    assert attempt["order_endpoint_called"] == "false"
    assert manifest["broker_or_paper_orders"] == 0
    assert manifest["new_strategy_configurations"] == 0
    assert manifest["new_experiment_trials"] == 0
    assert manifest["new_paper_demo_observations"] == 0


def test_accounting_and_target_reconcile() -> None:
    output = _latest()
    rows = list(csv.DictReader((output / "combined_target_reconciliation.csv").open(newline="", encoding="utf-8")))
    weights = [float(row["combined_target_weight"]) for row in rows]
    assert sum(weights) == pytest.approx(1.0)
    assert all(weight >= 0 for weight in weights)
    assert sum(abs(weight) for weight in weights) <= 1.0 + 1e-12
    assert task.read_csv(output / "virtual_initialization_record.csv") == []
    assert task.read_csv(output / "new_performance_rows.csv") == []


def test_protected_state_and_consistency_pass() -> None:
    output = _latest()
    consistency = json.loads((output / "consistency_check.json").read_text(encoding="utf-8"))
    assert consistency["protected_state_and_prior_evidence_unchanged"] is True
    assert consistency["unrelated_active_observations_unchanged"] is True
    assert consistency["unrelated_registry_records_unchanged"] is True
    assert consistency["overall_pass"] is True
