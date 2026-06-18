from __future__ import annotations

from math import sqrt


FORBIDDEN_MECHANICS = {
    "leverage": False,
    "margin": False,
    "shorting": False,
    "options": False,
    "futures": False,
    "forex": False,
    "crypto": False,
    "intraday": False,
    "broker_integration": False,
    "live_orders": False,
    "order_placement": False,
    "real_money_recommendation": False,
}


def vm_quality_lowvol_proxy_allocation(
    closes: dict[str, float],
    sma_200: dict[str, float],
    returns_126d: dict[str, float],
    realized_vol_60d: dict[str, float],
) -> dict[str, float]:
    """Fixed recovered rule for vm_quality_lowvol_proxy_v1."""
    risk_assets = ["SPLV", "USMV", "QUAL", "SPY"]
    eligible = [
        symbol
        for symbol in risk_assets
        if closes.get(symbol, 0.0) > sma_200.get(symbol, float("inf"))
        and realized_vol_60d.get(symbol, 0.0) > 0
    ]
    ranked = sorted(
        eligible,
        key=lambda symbol: returns_126d.get(symbol, 0.0) / realized_vol_60d[symbol],
        reverse=True,
    )
    if not ranked:
        return {"BIL": 1.0}
    top = ranked[:2]
    weight = 1.0 / len(top)
    return {symbol: weight for symbol in top}


def dsr_sector_equal_weight_defensive_filter_allocation(
    closes: dict[str, float],
    sma_200: dict[str, float],
) -> dict[str, float]:
    """Fixed recovered rule for dsr_sector_equal_weight_defensive_filter_v1."""
    sectors = ["XLK", "XLF", "XLE", "XLV", "XLY", "XLP", "XLU", "XLI", "XLB", "XLC"]
    qualifying = [symbol for symbol in sectors if closes.get(symbol, 0.0) > sma_200.get(symbol, float("inf"))]
    if not qualifying:
        return {"BIL": 1.0}
    if len(qualifying) <= 2:
        allocation = {symbol: 1.0 / 3.0 for symbol in qualifying}
        allocation["BIL"] = 1.0 - sum(allocation.values())
        return allocation
    weight = 1.0 / len(qualifying)
    return {symbol: weight for symbol in qualifying}


def gror_balanced_momentum_60_40_allocation(
    closes: dict[str, float],
    sma_200: dict[str, float],
    returns_63d: dict[str, float],
) -> dict[str, float]:
    """Recovered minimum rule for queued GROR balanced momentum row."""
    risk_on = ["SPY", "QQQ", "IWM", "EFA", "EEM", "GLD"]
    defensive = ["IEF", "TLT", "BIL"]
    eligible_risk = [
        symbol
        for symbol in risk_on
        if closes.get(symbol, 0.0) > sma_200.get(symbol, float("inf"))
    ]
    top_risk = sorted(eligible_risk, key=lambda symbol: returns_63d.get(symbol, 0.0), reverse=True)[:2]
    top_defensive = sorted(defensive, key=lambda symbol: returns_63d.get(symbol, 0.0), reverse=True)[:1]
    allocation: dict[str, float] = {}
    if top_risk:
        for symbol in top_risk:
            allocation[symbol] = 0.60 / len(top_risk)
    else:
        allocation["BIL"] = allocation.get("BIL", 0.0) + 0.60
    defensive_symbol = top_defensive[0] if top_defensive else "BIL"
    allocation[defensive_symbol] = allocation.get(defensive_symbol, 0.0) + 0.40
    return allocation


def realized_volatility(returns: list[float]) -> float:
    if len(returns) < 2:
        return 0.0
    mean = sum(returns) / len(returns)
    variance = sum((value - mean) ** 2 for value in returns) / (len(returns) - 1)
    return sqrt(variance * 252)


def max_drawdown(equity_curve: list[float]) -> float:
    peak = None
    worst = 0.0
    for value in equity_curve:
        peak = value if peak is None else max(peak, value)
        worst = min(worst, value - peak)
    return worst


def stop_hit(equity_curve: list[float], starting_equity: float = 3000.0, stop_dollars: float = -600.0) -> bool:
    return any(value - starting_equity <= stop_dollars for value in equity_curve)
