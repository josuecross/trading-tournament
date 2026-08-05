from __future__ import annotations

import csv
import json
import math
from datetime import date, datetime, timezone

import pytest
import yaml

from strategy_lab.research_os.research import (
    record_faa_prospective_validation_monthly_v1 as task,
)


def latest_run_dir():
    if not task.CHECKPOINT_ROOT.exists():
        pytest.skip("recording packet assertions run after the serial runner")
    candidates = sorted(
        path
        for path in task.CHECKPOINT_ROOT.iterdir()
        if path.is_dir() and not path.name.startswith(".")
    )
    if not candidates:
        pytest.skip("recording packet assertions run after the serial runner")
    return candidates[-1]


def rows(path):
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_offline_gate_reconciles_active_state_without_network() -> None:
    result = task.offline_gate()
    assert result["passed"] is True
    assert {row["status"] for row in result["rows"]} == {"pass"}
    assert {row["network_calls_at_check"] for row in result["rows"]} == {0}
    assert result["protected_before"] == result["protected_after"]
    assert result["active_before"] == result["active_after"]


def test_time_gate_precedes_scheduled_execution() -> None:
    now = datetime(2026, 8, 2, 22, 30, tzinfo=timezone.utc)
    latest = task.activation.latest_completed_session(now)
    assert latest == date(2026, 7, 31)
    assert task.time_gate(latest, None) == task.PENDING
    assert task.time_gate(date(2026, 8, 3), None) == task.INITIAL_EXECUTION_RECORDED
    assert task.time_gate(date(2026, 8, 4), None) == task.UPDATED
    assert task.time_gate(date(2026, 8, 4), date(2026, 8, 4)) == task.NO_NEW_SESSION


def test_initial_execution_cost_is_separate_from_market_return() -> None:
    shy = {symbol: (1.0 if symbol == "SHY" else 0.0) for symbol in task.SYMBOLS}
    target = task.read_json(task.ACTIVE_DIR / "current_target_vectors.json")[
        task.STRATEGY_ID
    ]
    result = task.execute_at_close(shy, target, 1.0, 5.0)
    assert math.isclose(result["one_way_turnover"], 2.0 / 3.0, abs_tol=1e-12)
    assert math.isclose(
        result["closing_nav_after_cost"],
        1.0 - (2.0 / 3.0) * 5.0 / 10000.0,
        abs_tol=1e-12,
    )
    assert "gross_portfolio_return" not in result


def test_daily_accounting_uses_drifted_holdings_and_costs_once() -> None:
    target = task.read_json(task.ACTIVE_DIR / "current_target_vectors.json")[
        task.STRATEGY_ID
    ]
    previous = {symbol: 100.0 for symbol in task.SYMBOLS}
    current = {symbol: 101.0 + index for index, symbol in enumerate(task.SYMBOLS)}
    result = task.account_close_to_close_session(
        target, 1.0, previous, current, 5.0
    )
    assert result["turnover"] == 0.0
    assert result["cost"] == 0.0
    assert result["invariant_result"] is True
    assert math.isclose(sum(result["post_trade_holdings"].values()), 1.0)


def test_append_unique_rows_is_idempotent_and_rejects_conflicts() -> None:
    key = ("market_date", "portfolio_id", "cost_bps")
    row = {
        "market_date": "2026-08-04",
        "portfolio_id": task.STRATEGY_ID,
        "cost_bps": 5,
        "closing_nav": 1.01,
    }
    assert task.append_unique_rows([row], [row], key) == [row]
    with pytest.raises(ValueError, match="immutable row conflict"):
        task.append_unique_rows([row], [{**row, "closing_nav": 1.02}], key)


def test_snapshot_hashes_and_reconciliation_alert_pass() -> None:
    inventory, latest = task.admitted_snapshot_inventory()
    assert len(inventory) == 7
    assert {row["status"] for row in inventory} == {"pass"}
    assert set(latest.values()) == {date(2026, 7, 31)}


def test_fixture_flow_covers_lookahead_and_idempotency() -> None:
    checks = task.fixture_flow_checks()
    assert checks
    assert all(checks.values())


def test_serial_packet_is_immutable_pending_state() -> None:
    run_dir = latest_run_dir()
    manifest = yaml.safe_load(
        (run_dir / "recording_manifest.yaml").read_text(encoding="utf-8")
    )
    consistency = json.loads(
        (run_dir / "consistency_check.json").read_text(encoding="utf-8")
    )
    assert {path.name for path in run_dir.iterdir() if path.is_file()} == task.REQUIRED_OUTPUTS
    assert manifest["outcome"] == task.PENDING
    assert manifest["network_calls"] == 0
    assert manifest["new_execution_events"] == 0
    assert manifest["new_daily_performance_rows"] == 0
    assert manifest["validation_decision"] == ""
    assert consistency["overall_pass"] is True
    assert consistency["protected_state_and_prior_evidence_unchanged"] is True
    assert consistency["active_state_changed"] is False
    assert rows(run_dir / "execution_event_ledger.csv") == []
    assert rows(run_dir / "new_daily_candidate_performance.csv") == []
    assert rows(run_dir / "new_daily_comparator_performance.csv") == []


def test_entity_counts_and_next_action_remain_operational() -> None:
    run_dir = latest_run_dir()
    manifest = yaml.safe_load(
        (run_dir / "recording_manifest.yaml").read_text(encoding="utf-8")
    )
    assert manifest["new_strategy_configurations"] == 0
    assert manifest["new_experiment_trials"] == 0
    assert manifest["new_validation_observations"] == 0
    assert manifest["paper_demo_observations"] == 0
    assert manifest["process_tasks"] == 1
    assert manifest["data_capability_tasks"] == 0
    assert manifest["broker_or_paper_orders"] == 0
    assert manifest["next_action"] == task.NEXT_RECORD
