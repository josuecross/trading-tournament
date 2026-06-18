from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from execution_lab.alpaca_micro_live_v1.adapters.alpaca_client import AlpacaClient
from execution_lab.alpaca_micro_live_v1.data.alpaca_runtime_cache import write_symbol_bars


ALLOWED_SYMBOLS = {"SPLV", "USMV", "QUAL", "SPY", "BIL"}
MIN_HISTORY_DAYS = 201


def _bar_to_record(bar: dict[str, Any]) -> dict[str, Any]:
    ts = pd.to_datetime(bar.get("t"), utc=True)
    return {
        "date": ts.date().isoformat(),
        "timestamp": ts.isoformat(),
        "open": float(bar.get("o")),
        "high": float(bar.get("h")),
        "low": float(bar.get("l")),
        "close": float(bar.get("c")),
        "volume": float(bar.get("v", 0.0)),
    }


def parse_bars_response(payload: dict[str, Any], *, drop_incomplete_current_day: bool = True) -> dict[str, pd.DataFrame]:
    today = datetime.now(timezone.utc).date().isoformat()
    parsed: dict[str, pd.DataFrame] = {}
    for symbol, bars in payload.get("bars", {}).items():
        records = [_bar_to_record(bar) for bar in bars]
        frame = pd.DataFrame(records)
        if frame.empty:
            parsed[symbol] = frame
            continue
        frame = frame.sort_values("date").drop_duplicates("date", keep="last")
        if drop_incomplete_current_day:
            frame = frame[frame["date"] < today]
        parsed[symbol] = frame.reset_index(drop=True)
    return parsed


def fetch_daily_bars(
    client: AlpacaClient,
    *,
    symbols: list[str],
    start: str,
    end: str | None = None,
    feed: str = "iex",
    adjustment: str = "all",
    drop_incomplete_current_day: bool = True,
    cache_dir: Path | None = None,
    min_history_days: int = MIN_HISTORY_DAYS,
) -> dict[str, pd.DataFrame]:
    unknown = sorted(set(symbols) - ALLOWED_SYMBOLS)
    if unknown:
        raise ValueError(f"Symbols are not approved for this runtime: {unknown}")

    merged_payload: dict[str, Any] = {"bars": {symbol: [] for symbol in symbols}}
    page_token: str | None = None
    while True:
        payload = client.get_historical_bars_page(
            symbols=symbols,
            start=start,
            end=end,
            timeframe="1Day",
            page_token=page_token,
            feed=feed,
            adjustment=adjustment,
        )
        for symbol, bars in payload.get("bars", {}).items():
            merged_payload["bars"].setdefault(symbol, []).extend(bars)
        page_token = payload.get("next_page_token")
        if not page_token:
            break

    parsed = parse_bars_response(
        merged_payload,
        drop_incomplete_current_day=drop_incomplete_current_day,
    )
    for symbol in symbols:
        frame = parsed.get(symbol, pd.DataFrame())
        if len(frame) < min_history_days:
            raise ValueError(f"{symbol} has insufficient Alpaca history: {len(frame)} rows")
        write_symbol_bars(symbol, frame, cache_dir)
    return parsed

