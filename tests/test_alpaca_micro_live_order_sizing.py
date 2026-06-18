from __future__ import annotations

import pytest

from trading_tournament.execution_lab.alpaca_micro_live_v1.execution.order_sizing import build_delta_orders


pytestmark = pytest.mark.alpaca_micro_live


def limits(**overrides):
    base = {
        "capital_sleeve_notional": 25.0,
        "max_order_notional": 5.0,
        "min_order_notional": 1.0,
        "rebalance_tolerance_notional": 1.0,
        "allow_paper_reduce_only_sells": False,
    }
    base.update(overrides)
    return base


def test_order_sizing_buys_below_target():
    orders, skipped = build_delta_orders(
        target_weights={"QUAL": 0.5},
        account={"equity": 1000, "cash": 1000},
        positions=[],
        latest_prices={"QUAL": 100},
        risk_limits=limits(),
    )
    assert orders[0].symbol == "QUAL"
    assert orders[0].side == "buy"
    assert orders[0].notional == 5.0
    assert skipped == []


def test_order_sizing_skips_within_tolerance():
    orders, skipped = build_delta_orders(
        target_weights={"QUAL": 0.5},
        account={"equity": 1000, "cash": 1000},
        positions=[{"symbol": "QUAL", "market_value": "12.0"}],
        latest_prices={"QUAL": 100},
        risk_limits=limits(),
    )
    assert orders == []
    assert skipped[0]["reason"] == "within_tolerance"


def test_reduce_only_sell_cannot_sell_more_than_current_position():
    orders, _ = build_delta_orders(
        target_weights={"QUAL": 0.0},
        account={"equity": 1000, "cash": 1000},
        positions=[{"symbol": "QUAL", "market_value": "3.00", "current_price": "10"}],
        latest_prices={"QUAL": 10},
        risk_limits=limits(allow_paper_reduce_only_sells=True, max_order_notional=10.0),
    )
    assert orders[0].side == "sell"
    assert orders[0].notional == 3.0
    assert orders[0].qty == pytest.approx(0.3)
