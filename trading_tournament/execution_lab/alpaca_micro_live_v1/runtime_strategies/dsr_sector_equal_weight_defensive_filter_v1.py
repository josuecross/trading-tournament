from __future__ import annotations

from typing import Any

import pandas as pd


def _metrics(frame: pd.DataFrame, sma_window: int) -> dict[str, Any]:
    ordered = frame.copy()
    ordered["date"] = ordered["date"].astype(str)
    ordered = ordered.sort_values("date")
    close = ordered["close"].astype(float)
    if len(ordered) < sma_window:
        return {"eligible": False, "reason": "insufficient_history", "rows": len(ordered)}
    latest_close = float(close.iloc[-1])
    sma = float(close.rolling(sma_window).mean().iloc[-1])
    return {
        "eligible": latest_close > sma,
        "latest_date": ordered["date"].iloc[-1],
        "close": latest_close,
        "sma_200": sma,
    }


def generate_target_from_bars(bars_by_symbol: dict, spec: dict) -> dict:
    sector_assets = spec["universe"]["sector_assets"]
    fallback = spec["portfolio"]["fallback"]
    sma_window = int(spec["eligibility"]["sma_window"])
    eligibility = []
    qualifying = []
    latest_dates = []
    for symbol in sector_assets:
        frame = bars_by_symbol.get(symbol)
        if frame is None or frame.empty:
            eligibility.append({"symbol": symbol, "eligible": False, "reason": "missing_data"})
            continue
        metrics = _metrics(frame, sma_window)
        row = {"symbol": symbol, **metrics}
        eligibility.append(row)
        if metrics.get("latest_date"):
            latest_dates.append(str(metrics["latest_date"]))
        if metrics.get("eligible"):
            qualifying.append(symbol)
    if not qualifying:
        target_weights = {fallback: 1.0}
        fallback_triggered = True
    elif len(qualifying) <= 2:
        target_weights = {symbol: 1.0 / 3.0 for symbol in qualifying}
        target_weights[fallback] = 1.0 - sum(target_weights.values())
        fallback_triggered = False
    else:
        weight = 1.0 / len(qualifying)
        target_weights = {symbol: weight for symbol in qualifying}
        fallback_triggered = False
    return {
        "strategy_id": spec["strategy_id"],
        "as_of": min(latest_dates) if latest_dates else "",
        "target_source": "alpaca_runtime",
        "target_weights": target_weights,
        "cash_weight": 0.0,
        "metadata": {
            "strategy_logic_modified": False,
            "selected_holdings": list(target_weights),
            "eligibility": eligibility,
            "ranking": [],
            "fallback_triggered": fallback_triggered,
        },
    }
