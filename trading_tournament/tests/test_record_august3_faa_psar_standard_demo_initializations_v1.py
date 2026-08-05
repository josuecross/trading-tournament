from __future__ import annotations

import csv
import json
from datetime import datetime, timezone

import pytest

from strategy_lab.research_os.research import (
    record_august3_faa_psar_standard_demo_initializations_v1 as task,
)


def test_session_gate_uses_completed_august_3_close() -> None:
    assert task.psar.close_completed(datetime(2026, 8, 3, 19, 59, 59, tzinfo=timezone.utc)) is False
    assert task.psar.close_completed(datetime(2026, 8, 3, 20, 0, 0, tzinfo=timezone.utc)) is True


def test_faa_frozen_target_and_hash_reconcile() -> None:
    target = task.faa.load_frozen_target()
    assert target == task.faa.EXPECTED_TARGET
    assert task.common.canonical_hash(target) == task.faa.TARGET_HASH
    assert sum(target.values()) == pytest.approx(1.0)


def test_psar_frozen_target_and_hash_reconcile() -> None:
    target, row = task.psar.load_frozen_target()
    assert task.common.canonical_hash(target) == task.psar.TARGET_HASH
    assert row["target_hash"] == task.psar.TARGET_HASH
    assert sum(target.values()) == pytest.approx(1.0)


def test_faa_initialization_accounting_is_exact() -> None:
    target = task.faa.EXPECTED_TARGET
    prices = {symbol: float(index + 50) for index, symbol in enumerate(target)}
    result = task.faa.calculate_virtual_initialization(target, prices, 3000.0)
    assert result["initialization_turnover"] == pytest.approx(1.0)
    assert result["transaction_cost"] == pytest.approx(1.5)
    assert result["post_cost_equity"] == pytest.approx(2998.5)
    assert result["residual_cash"] == pytest.approx(0.0, abs=1e-9)
    assert sum(result["holdings"].values()) == pytest.approx(2998.5)


@pytest.mark.parametrize(
    ("close_complete", "faa_initialized", "psar_initialized", "blocked", "expected"),
    [
        (False, False, False, False, task.OUTCOME_PENDING),
        (True, True, True, False, task.OUTCOME_RECORDED),
        (True, True, False, False, task.OUTCOME_PARTIAL),
        (True, False, True, False, task.OUTCOME_PARTIAL),
        (True, False, False, True, task.OUTCOME_BLOCKED),
    ],
)
def test_combined_outcome_selection_is_deterministic(
    close_complete: bool,
    faa_initialized: bool,
    psar_initialized: bool,
    blocked: bool,
    expected: str,
) -> None:
    outcome, _ = task.classify_outcome(close_complete, faa_initialized, psar_initialized, blocked)
    assert outcome == expected


def test_completed_initializations_are_idempotently_detected() -> None:
    if not task.OUTPUT_DIR.exists():
        pytest.skip("combined execution packet has not been generated")
    assert task.faa.already_initialized() is True
    assert task.psar_already_initialized() is True
    assert task.faa.latest_initialized_packet() is not None
    assert task.latest_psar_initialized_packet() is not None


def test_component_ledgers_have_one_execution_and_no_performance_row() -> None:
    if not task.OUTPUT_DIR.exists():
        pytest.skip("combined execution packet has not been generated")
    for ledger in (task.faa.COMPONENT_LEDGER, task.common.COMPONENT_LEDGER):
        rows = list(csv.DictReader(ledger.open(newline="", encoding="utf-8")))
        assert len(rows) == 1
        assert rows[0]["row_type"] == "virtual_initialization"
        assert rows[0]["date"] == "2026-08-03"
    for recorder_result in ("faa_recorder_result.csv", "psar_recorder_result.csv"):
        result = next(csv.DictReader((task.OUTPUT_DIR / recorder_result).open(newline="", encoding="utf-8")))
        packet = task.ROOT / result["immutable_packet"]
        assert task.common.read_csv(packet / "new_performance_rows.csv") == []


def test_execution_costs_and_first_performance_date_reconcile() -> None:
    if not task.OUTPUT_DIR.exists():
        pytest.skip("combined execution packet has not been generated")
    rows = task.common.read_csv(task.OUTPUT_DIR / "execution_and_cost_reconciliation.csv")
    assert len(rows) == 2
    for row in rows:
        assert float(row["one_way_initialization_turnover"]) == pytest.approx(1.0)
        assert float(row["actual_initialization_cost"]) == pytest.approx(1.5)
        assert float(row["post_cost_starting_equity"]) == pytest.approx(2998.5)
        assert row["cost_charged_once"] == "true"
        assert row["no_august3_performance"] == "true"


def test_combined_packet_is_complete_and_consistent() -> None:
    if not task.OUTPUT_DIR.exists():
        pytest.skip("combined execution packet has not been generated")
    assert {path.name for path in task.OUTPUT_DIR.iterdir() if path.is_file()} == task.REQUIRED_OUTPUTS
    consistency = json.loads((task.OUTPUT_DIR / "consistency_check.json").read_text(encoding="utf-8"))
    assert consistency["outcome"] == task.OUTCOME_RECORDED
    assert consistency["no_august_3_performance_rows"] is True
    assert consistency["duplicate_execution_prevented"] is True
    assert consistency["vortex_and_real_momentum_closures_preserved"] is True
    assert consistency["overall_pass"] is True
