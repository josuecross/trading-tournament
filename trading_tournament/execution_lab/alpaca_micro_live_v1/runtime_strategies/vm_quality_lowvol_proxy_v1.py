from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from execution_lab.alpaca_micro_live_v1 import MODULE_ROOT
from execution_lab.alpaca_micro_live_v1.execution.models import RuntimeSignal
from execution_lab.alpaca_micro_live_v1.execution.logging_utils import utc_timestamp


SPEC_PATH = MODULE_ROOT / "runtime_strategies" / "vm_quality_lowvol_proxy_v1.yaml"


def load_strategy_spec(path: Path | None = None) -> dict[str, Any]:
    return yaml.safe_load((path or SPEC_PATH).read_text(encoding="utf-8"))


def _metrics_for_symbol(frame: pd.DataFrame, sma_window: int, return_window: int, volatility_window: int) -> dict[str, Any]:
    ordered = frame.copy()
    ordered["date"] = ordered["date"].astype(str)
    ordered = ordered.sort_values("date")
    close = ordered["close"].astype(float)
    if len(ordered) <= max(sma_window, return_window, volatility_window):
        return {"missing": True, "rows": len(ordered)}
    latest_close = float(close.iloc[-1])
    sma_200 = float(close.rolling(sma_window).mean().iloc[-1])
    return_126d = float((latest_close / close.iloc[-return_window - 1]) - 1.0)
    realized_vol_60d = float(close.pct_change().rolling(volatility_window).std().iloc[-1])
    eligible = bool(latest_close > sma_200)
    score = return_126d / realized_vol_60d if realized_vol_60d and not np.isnan(realized_vol_60d) else np.nan
    return {
        "missing": False,
        "rows": len(ordered),
        "latest_date": ordered["date"].iloc[-1],
        "close": latest_close,
        "sma_200": sma_200,
        "return_126d": return_126d,
        "realized_vol_60d": realized_vol_60d,
        "eligible": eligible,
        "score": float(score) if not np.isnan(score) else None,
    }


def generate_signal_from_bars(
    bars_by_symbol: dict[str, pd.DataFrame],
    *,
    spec: dict[str, Any] | None = None,
    feed: str = "iex",
    adjustment: str = "all",
) -> RuntimeSignal:
    spec = spec or load_strategy_spec()
    strategy_id = spec["strategy_id"]
    risk_assets = spec["universe"]["risk_assets"]
    fallback = spec["portfolio"]["fallback"]
    sma_window = int(spec["eligibility"]["sma_window"])
    return_window = int(spec["ranking"]["return_window"])
    volatility_window = int(spec["ranking"]["volatility_window"])
    hold_top_n = int(spec["portfolio"]["hold_top_n"])

    eligibility_table: list[dict[str, Any]] = []
    ranking_table: list[dict[str, Any]] = []
    missing_data: list[str] = []
    latest_dates: list[str] = []

    for symbol in risk_assets:
        frame = bars_by_symbol.get(symbol)
        if frame is None or frame.empty:
            missing_data.append(symbol)
            eligibility_table.append({"symbol": symbol, "eligible": False, "reason": "missing_data"})
            continue
        metrics = _metrics_for_symbol(frame, sma_window, return_window, volatility_window)
        if metrics.get("missing"):
            missing_data.append(symbol)
            eligibility_table.append({"symbol": symbol, "eligible": False, "reason": "insufficient_history", "rows": metrics["rows"]})
            continue
        latest_dates.append(str(metrics["latest_date"]))
        eligibility_table.append(
            {
                "symbol": symbol,
                "eligible": metrics["eligible"],
                "close": round(metrics["close"], 6),
                "sma_200": round(metrics["sma_200"], 6),
            }
        )
        ranking_table.append(
            {
                "symbol": symbol,
                "eligible": metrics["eligible"],
                "return_126d": round(metrics["return_126d"], 8),
                "realized_vol_60d": round(metrics["realized_vol_60d"], 8),
                "score": None if metrics["score"] is None else round(metrics["score"], 8),
            }
        )

    ranked = [
        row for row in ranking_table if row["eligible"] and row["score"] is not None
    ]
    ranked.sort(key=lambda row: row["score"], reverse=True)
    selected = [row["symbol"] for row in ranked[:hold_top_n]]
    fallback_triggered = not selected
    if fallback_triggered:
        target_weights = {fallback: 1.0}
        cash_weight = 0.0
    else:
        weight = 1.0 / len(selected)
        target_weights = {symbol: weight for symbol in selected}
        cash_weight = 0.0

    as_of = min(latest_dates) if latest_dates else ""
    return RuntimeSignal(
        strategy_id=strategy_id,
        as_of=as_of,
        target_weights=target_weights,
        cash_weight=cash_weight,
        metadata={
            "generated_at": utc_timestamp(),
            "data_source": "alpaca_historical_bars",
            "adjustment": adjustment,
            "feed": feed,
            "strategy_logic_modified": False,
        },
        eligibility_table=eligibility_table,
        ranking_table=ranked + [row for row in ranking_table if row not in ranked],
        selected_holdings=selected if selected else [fallback],
        fallback_triggered=fallback_triggered,
        missing_data=missing_data,
        approximations=[],
    )


def generate_target_from_bars(bars_by_symbol: dict[str, pd.DataFrame], spec: dict[str, Any]) -> dict[str, Any]:
    signal = generate_signal_from_bars(bars_by_symbol, spec=spec)
    return {
        "strategy_id": signal.strategy_id,
        "as_of": signal.as_of,
        "target_source": "alpaca_runtime",
        "target_weights": signal.target_weights,
        "cash_weight": signal.cash_weight,
        "metadata": {
            "strategy_logic_modified": False,
            "selected_holdings": signal.selected_holdings,
            "eligibility": signal.eligibility_table,
            "ranking": signal.ranking_table,
            "fallback_triggered": signal.fallback_triggered,
        },
    }

