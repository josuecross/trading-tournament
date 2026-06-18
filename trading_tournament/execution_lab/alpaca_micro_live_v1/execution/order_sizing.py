from __future__ import annotations

from typing import Any

from trading_tournament.execution_lab.alpaca_micro_live_v1.execution.models import ProposedOrder


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def positions_by_symbol(positions: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(position.get("symbol")): position for position in positions}


def build_delta_orders(
    *,
    target_weights: dict[str, float],
    account: dict[str, Any],
    positions: list[dict[str, Any]],
    latest_prices: dict[str, float] | None,
    risk_limits: dict[str, Any],
) -> tuple[list[ProposedOrder], list[dict[str, Any]]]:
    sleeve = _float(risk_limits.get("capital_sleeve_notional"), 25.0)
    max_order = _float(risk_limits.get("max_order_notional"), 5.0)
    min_order = _float(risk_limits.get("min_order_notional"), 1.0)
    tolerance = _float(risk_limits.get("rebalance_tolerance_notional"), 1.0)
    allow_sells = bool(risk_limits.get("allow_paper_reduce_only_sells", False))

    current = positions_by_symbol(positions)
    proposed: list[ProposedOrder] = []
    skipped: list[dict[str, Any]] = []

    for symbol, weight in target_weights.items():
        target_notional = sleeve * float(weight)
        position = current.get(symbol, {})
        current_notional = _float(position.get("market_value"))
        delta = target_notional - current_notional
        if abs(delta) <= tolerance:
            skipped.append({"symbol": symbol, "reason": "within_tolerance", "delta": round(delta, 2)})
            continue
        if delta > 0:
            notional = min(delta, max_order)
            if notional < min_order:
                skipped.append({"symbol": symbol, "reason": "below_min_order_notional", "notional": round(notional, 2)})
                continue
            proposed.append(ProposedOrder(symbol=symbol, side="buy", notional=round(notional, 2), reason="below_target"))
            continue
        if not allow_sells:
            skipped.append({"symbol": symbol, "reason": "reduce_only_sells_disabled", "delta": round(delta, 2)})
            continue
        reduce_notional = min(abs(delta), current_notional, max_order)
        if reduce_notional < min_order:
            skipped.append({"symbol": symbol, "reason": "sell_below_min_order_notional", "notional": round(reduce_notional, 2)})
            continue
        price = (latest_prices or {}).get(symbol) or _float(position.get("current_price"))
        qty = reduce_notional / price if price else None
        proposed.append(
            ProposedOrder(
                symbol=symbol,
                side="sell",
                notional=round(reduce_notional, 2),
                qty=None if qty is None else round(qty, 8),
                reason="above_target_reduce_only",
            )
        )
    return proposed, skipped
