from __future__ import annotations

import pytest

from execution_lab.alpaca_micro_live_v1.execution.order_sizing import build_delta_orders

pytestmark = pytest.mark.alpaca_micro_live


def test_order_sizing_buys_when_below_target() -> None:
    orders, skipped = build_delta_orders(
        target_weights={"SPY": 1.0},
        account={"cash": "100"},
        positions=[],
        latest_prices={"SPY": 100.0},
        risk_limits={"capital_sleeve_notional": 25, "max_order_notional": 5, "min_order_notional": 1},
    )
    assert skipped == []
    assert len(orders) == 1
    assert orders[0].symbol == "SPY"
    assert orders[0].side == "buy"
    assert orders[0].notional == 5


def test_order_sizing_skips_within_tolerance() -> None:
    orders, skipped = build_delta_orders(
        target_weights={"SPY": 1.0},
        account={"cash": "100"},
        positions=[{"symbol": "SPY", "market_value": "24.50"}],
        latest_prices={"SPY": 100.0},
        risk_limits={"capital_sleeve_notional": 25, "rebalance_tolerance_notional": 1},
    )
    assert orders == []
    assert skipped[0]["reason"] == "within_tolerance"


def test_reduce_only_sell_cannot_sell_more_than_current_position() -> None:
    orders, skipped = build_delta_orders(
        target_weights={"SPY": 0.0},
        account={"cash": "100"},
        positions=[{"symbol": "SPY", "market_value": "3.00", "current_price": "100"}],
        latest_prices={"SPY": 100.0},
        risk_limits={
            "capital_sleeve_notional": 25,
            "max_order_notional": 5,
            "min_order_notional": 1,
            "allow_paper_reduce_only_sells": True,
        },
    )
    assert skipped == []
    assert orders[0].side == "sell"
    assert orders[0].notional == 3.0
    assert orders[0].qty == 0.03
