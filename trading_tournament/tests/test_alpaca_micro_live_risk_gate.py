from __future__ import annotations

import pytest

from execution_lab.alpaca_micro_live_v1.execution.models import ProposedOrder
from execution_lab.alpaca_micro_live_v1.execution.risk_gate import evaluate_risk_gate
from tests.alpaca_micro_live_fakes import fake_credentials

pytestmark = pytest.mark.alpaca_micro_live


def _registry() -> dict:
    return {
        "strategies": {
            "vm_quality_lowvol_proxy_v1": {
                "enabled": True,
                "runtime_ready": True,
                "live_trading_allowed": False,
                "allowed_symbols": ["SPY", "BIL"],
            }
        }
    }


def _risk_limits() -> dict:
    return {
        "paper_trading_allowed": True,
        "live_trading_allowed": False,
        "max_order_notional": 5,
        "min_order_notional": 1,
        "max_total_notional_per_run": 25,
        "cash_buffer_pct": 0,
    }


def test_risk_gate_blocks_live_mode() -> None:
    result = evaluate_risk_gate(
        mode="live",
        submit_requested=True,
        credentials=fake_credentials(),
        strategy_id="vm_quality_lowvol_proxy_v1",
        strategy_registry=_registry(),
        risk_limits=_risk_limits(),
        market_clock={"is_open": True},
        account={"cash": "100", "equity": "100"},
        open_orders=[],
        proposed_orders=[ProposedOrder("SPY", "buy", 5, "test")],
    )
    assert result.allowed is False
    assert "live_execution_not_supported" in result.errors


def test_risk_gate_blocks_market_closed_paper_submit() -> None:
    result = evaluate_risk_gate(
        mode="paper",
        submit_requested=True,
        credentials=fake_credentials(),
        strategy_id="vm_quality_lowvol_proxy_v1",
        strategy_registry=_registry(),
        risk_limits={**_risk_limits(), "require_market_open": True},
        market_clock={"is_open": False},
        account={"cash": "100", "equity": "100"},
        open_orders=[],
        proposed_orders=[ProposedOrder("SPY", "buy", 5, "test")],
    )
    assert result.allowed is False
    assert "market_not_open" in result.errors


def test_stop_emergency_state_prevents_submit() -> None:
    result = evaluate_risk_gate(
        mode="paper",
        submit_requested=True,
        credentials=fake_credentials(),
        strategy_id="vm_quality_lowvol_proxy_v1",
        strategy_registry=_registry(),
        risk_limits=_risk_limits(),
        market_clock={"is_open": True},
        account={"cash": "100", "equity": "100"},
        open_orders=[],
        proposed_orders=[ProposedOrder("SPY", "buy", 5, "test")],
        emergency_stop=True,
    )
    assert result.allowed is False
    assert "emergency_stop_active" in result.errors
