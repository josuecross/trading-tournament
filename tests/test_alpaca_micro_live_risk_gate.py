from __future__ import annotations

import pytest

from trading_tournament.execution_lab.alpaca_micro_live_v1.adapters.credentials import AlpacaCredentials
from trading_tournament.execution_lab.alpaca_micro_live_v1.execution.models import ProposedOrder
from trading_tournament.execution_lab.alpaca_micro_live_v1.execution.risk_gate import evaluate_risk_gate


pytestmark = pytest.mark.alpaca_micro_live


REGISTRY = {
    "strategies": {
        "vm_quality_lowvol_proxy_v1": {
            "enabled": True,
            "runtime_ready": True,
            "live_trading_allowed": False,
            "allowed_symbols": ["QUAL", "SPY", "BIL"],
        }
    }
}


def base_limits():
    return {
        "paper_trading_allowed": True,
        "live_trading_allowed": False,
        "require_market_open": True,
        "max_order_notional": 5,
        "min_order_notional": 1,
        "max_total_notional_per_run": 25,
        "cash_buffer_pct": 0.05,
        "allow_shorts": False,
        "allow_margin": False,
        "allow_options": False,
        "allow_crypto": False,
        "allow_futures": False,
    }


def creds():
    return AlpacaCredentials("paper", "key", "secret", "test")


def test_risk_gate_blocks_live():
    result = evaluate_risk_gate(
        mode="live",
        submit_requested=True,
        credentials=creds(),
        strategy_id="vm_quality_lowvol_proxy_v1",
        strategy_registry=REGISTRY,
        risk_limits=base_limits(),
        market_clock={"is_open": True},
        account={"cash": 100, "equity": 100},
        open_orders=[],
        proposed_orders=[ProposedOrder("QUAL", "buy", 5, "test")],
    )
    assert not result.allowed
    assert "live_execution_not_supported" in result.errors


def test_risk_gate_blocks_market_closed_submit():
    result = evaluate_risk_gate(
        mode="paper",
        submit_requested=True,
        credentials=creds(),
        strategy_id="vm_quality_lowvol_proxy_v1",
        strategy_registry=REGISTRY,
        risk_limits=base_limits(),
        market_clock={"is_open": False},
        account={"cash": 100, "equity": 100},
        open_orders=[],
        proposed_orders=[ProposedOrder("QUAL", "buy", 5, "test")],
    )
    assert not result.allowed
    assert "market_not_open" in result.errors
