from __future__ import annotations

import csv
import json
from datetime import datetime, timezone

import pytest

from strategy_lab.research_os.research import (
    record_psar_standard_paper_demo_virtual_execution_v1 as task,
)


def _latest_execution_packet() -> task.Path:
    for path in sorted(
        (value for value in task.freeze.RUN_ROOT.iterdir() if value.is_dir()),
        reverse=True,
    ):
        if (path / "prior_target_freeze_reconciliation.csv").exists():
            return path
    pytest.skip("execution-stage recorder has not generated an immutable packet")


def test_prior_frozen_target_reconciles_exactly() -> None:
    target, row = task.load_frozen_target()
    assert task.freeze.canonical_hash(target) == task.TARGET_HASH
    assert row["target_hash"] == task.TARGET_HASH
    assert sum(target.values()) == pytest.approx(1.0)
    assert target["USCI"] == pytest.approx(0.26666666666666666)
    assert target["BIL"] == pytest.approx(0.2)


def test_august_3_close_boundary_is_explicit() -> None:
    assert task.close_completed(datetime(2026, 8, 3, 19, 59, 59, tzinfo=timezone.utc)) is False
    assert task.close_completed(datetime(2026, 8, 3, 20, 0, 0, tzinfo=timezone.utc)) is True


def test_virtual_initialization_cost_and_holdings_reconcile() -> None:
    target, _ = task.load_frozen_target()
    prices = {symbol: float(index + 50) for index, symbol in enumerate(target)}
    result = task.calculate_virtual_initialization(target, prices, 3000.0)
    assert result["initialization_turnover"] == pytest.approx(1.0)
    assert result["transaction_cost"] == pytest.approx(1.5)
    assert result["post_cost_equity"] == pytest.approx(2998.5)
    assert result["residual_cash"] == pytest.approx(0.0, abs=1e-9)
    assert sum(result["holdings"].values()) == pytest.approx(2998.5)
    for symbol, weight in target.items():
        assert result["holdings"][symbol] / result["post_cost_equity"] == pytest.approx(weight)


def test_latest_execution_packet_matches_the_current_execution_phase() -> None:
    output = _latest_execution_packet()
    outcome = next(csv.DictReader((output / "outcome_summary.csv").open(newline="", encoding="utf-8")))
    provider = next(csv.DictReader((output / "provider_attempt_log.csv").open(newline="", encoding="utf-8")))
    assert outcome["outcome"] in {task.OUTCOME_PENDING, task.OUTCOME_INITIALIZED}
    assert outcome["performance_rows"] == "0"
    assert provider["account_endpoint_called"] == "false"
    assert provider["position_endpoint_called"] == "false"
    assert provider["order_endpoint_called"] == "false"
    assert task.freeze.read_csv(output / "new_performance_rows.csv") == []
    if outcome["outcome"] == task.OUTCOME_PENDING:
        assert outcome["failure_reason"] == "scheduled_close_not_completed"
        assert outcome["virtual_execution_events"] == "0"
        assert provider["attempted"] == "false"
        assert task.freeze.read_csv(output / "virtual_initialization_record.csv") == []
        assert task.freeze.read_csv(output / "virtual_holdings_after.csv") == []
    else:
        assert outcome["failure_reason"] == ""
        assert outcome["virtual_execution_events"] == "1"
        assert provider["attempted"] == "true"
        assert len(task.freeze.read_csv(output / "virtual_initialization_record.csv")) == 1
        assert len(task.freeze.read_csv(task.freeze.COMPONENT_LEDGER)) == 1


def test_execution_packet_and_consistency_are_exact() -> None:
    output = _latest_execution_packet()
    assert {path.name for path in output.iterdir() if path.is_file()} == task.REQUIRED_OUTPUTS
    consistency = json.loads((output / "consistency_check.json").read_text(encoding="utf-8"))
    assert consistency["prior_freeze_packet_unchanged"] is True
    assert consistency["target_never_recalculated"] is True
    assert consistency["provider_called_only_after_close"] is True
    assert consistency["no_august_3_performance"] is True
    assert consistency["unrelated_active_observations_unchanged"] is True
    assert consistency["unrelated_registry_records_unchanged"] is True
    assert consistency["overall_pass"] is True
