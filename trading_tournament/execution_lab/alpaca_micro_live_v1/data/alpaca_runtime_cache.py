from __future__ import annotations

from pathlib import Path

import pandas as pd

from trading_tournament.execution_lab.alpaca_micro_live_v1 import MODULE_ROOT


DEFAULT_CACHE_DIR = MODULE_ROOT / "evidence" / "alpaca_runtime_data" / "cache"


def cache_path(symbol: str, cache_dir: Path | None = None) -> Path:
    root = cache_dir or DEFAULT_CACHE_DIR
    return root / f"{symbol.upper()}_1Day.csv"


def write_symbol_bars(symbol: str, bars: pd.DataFrame, cache_dir: Path | None = None) -> Path:
    path = cache_path(symbol, cache_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    bars.to_csv(path, index=False)
    return path


def read_symbol_bars(symbol: str, cache_dir: Path | None = None) -> pd.DataFrame | None:
    path = cache_path(symbol, cache_dir)
    if not path.exists():
        return None
    frame = pd.read_csv(path)
    if "date" in frame.columns:
        frame["date"] = pd.to_datetime(frame["date"]).dt.date.astype(str)
    return frame
