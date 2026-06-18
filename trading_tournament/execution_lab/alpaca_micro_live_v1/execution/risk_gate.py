from __future__ import annotations

from typing import Any

from trading_tournament.execution_lab.alpaca_micro_live_v1.adapters.credentials import AlpacaCredentials
from trading_tournament.execution_lab.alpaca_micro_live_v1.execution.models import ProposedOrder, RiskGateResult


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def evaluate_risk_gate(
    *,
    mode: str,
    submit_requested: bool,
    credentials: AlpacaCredentials,
    strategy_id: str,
    strategy_registry: dict[str, Any],
    risk_limits: dict[str, Any],
    market_clock: dict[str, Any] | None,
    account: dict[str, Any],
    open_orders: list[dict[str, Any]],
    proposed_orders: list[ProposedOrder],
    assets: dict[str, dict[str, Any]] | None = None,
    unresolved_broker_ambiguity: bool = False,
    target_version_already_handled: bool = False,
    emergency_stop: bool = False,
) -> RiskGateResult:
    errors: list[str] = []
    warnings: list[str] = []

    if emergency_stop:
        errors.append("emergency_stop_active")
    if mode != "paper":
        errors.append("live_execution_not_supported")
    if risk_limits.get("live_trading_allowed") is True:
        errors.append("live_trading_allowed_must_be_false")
    if submit_requested and not risk_limits.get("paper_trading_allowed", False):
        errors.append("paper_trading_not_allowed")
    if submit_requested and not credentials.present:
        errors.append("paper_credentials_missing")

    row = strategy_registry.get("strategies", {}).get(strategy_id)
    if not row:
        errors.append("strategy_not_registered")
        allowed_symbols: set[str] = set()
    else:
        if not row.get("enabled") or not row.get("runtime_ready"):
            errors.append("strategy_not_enabled_runtime_ready")
        if row.get("live_trading_allowed") is True:
            errors.append("strategy_live_trading_allowed_must_be_false")
        allowed_symbols = set(row.get("allowed_symbols", []))

    if risk_limits.get("allow_shorts") or risk_limits.get("allow_margin") or risk_limits.get("allow_options") or risk_limits.get("allow_crypto") or risk_limits.get("allow_futures"):
        errors.append("disallowed_instrument_or_leverage_flag_enabled")

    if target_version_already_handled:
        errors.append("target_version_already_handled")
    if unresolved_broker_ambiguity:
        errors.append("unresolved_broker_ambiguity")

    if submit_requested and risk_limits.get("require_market_open", True):
        if not market_clock or not bool(market_clock.get("is_open")):
            errors.append("market_not_open")

    open_order_symbols = {order.get("symbol") for order in open_orders}
    if open_order_symbols:
        proposed_symbols = {order.symbol for order in proposed_orders}
        conflicts = sorted(proposed_symbols & open_order_symbols)
        if conflicts:
            errors.append(f"open_order_conflicts:{','.join(conflicts)}")

    max_order = _float(risk_limits.get("max_order_notional"), 5.0)
    min_order = _float(risk_limits.get("min_order_notional"), 1.0)
    max_total = _float(risk_limits.get("max_total_notional_per_run"), 25.0)
    total = 0.0
    for order in proposed_orders:
        total += order.notional
        if order.symbol not in allowed_symbols:
            errors.append(f"symbol_not_approved:{order.symbol}")
        if order.notional > max_order:
            errors.append(f"order_exceeds_max_notional:{order.symbol}")
        if order.notional < min_order:
            errors.append(f"order_below_min_notional:{order.symbol}")
        if order.side == "sell" and not risk_limits.get("allow_paper_reduce_only_sells", False):
            errors.append(f"sells_disabled:{order.symbol}")
        if assets and order.symbol in assets:
            asset = assets[order.symbol]
            if asset.get("tradable") is False:
                errors.append(f"asset_not_tradable:{order.symbol}")
            if order.side == "buy" and asset.get("fractionable") is False:
                warnings.append(f"asset_not_fractionable:{order.symbol}")
    if total > max_total:
        errors.append("run_exceeds_max_total_notional")

    cash = _float(account.get("cash"))
    equity = _float(account.get("equity"))
    buffer_cash = equity * _float(risk_limits.get("cash_buffer_pct"), 0.05)
    buy_total = sum(order.notional for order in proposed_orders if order.side == "buy")
    if submit_requested and buy_total > max(0.0, cash - buffer_cash):
        errors.append("insufficient_cash_after_buffer")

    return RiskGateResult(allowed=not errors, errors=errors, warnings=warnings)
