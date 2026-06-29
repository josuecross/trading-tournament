from __future__ import annotations

import numpy as np
import pandas as pd


def _frame_from_close(close: list[float] | np.ndarray, volume: list[float] | np.ndarray | float = 1000.0) -> pd.DataFrame:
    values = np.asarray(close, dtype=float)
    if isinstance(volume, (int, float)):
        volume_values = np.full(len(values), float(volume))
    else:
        volume_values = np.asarray(volume, dtype=float)
    return pd.DataFrame(
        {
            "date": pd.date_range("2020-01-01", periods=len(values), freq="D"),
            "open": values,
            "high": values + 0.5,
            "low": values - 0.5,
            "close": values,
            "volume": volume_values,
        }
    )


def flat_price_fixture(rows: int = 260, price: float = 100.0, volume: float = 1000.0) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.date_range("2020-01-01", periods=rows, freq="D"),
            "open": np.full(rows, price),
            "high": np.full(rows, price),
            "low": np.full(rows, price),
            "close": np.full(rows, price),
            "volume": np.full(rows, volume),
        }
    )


def monotonic_up_fixture(rows: int = 260, start: float = 20.0, step: float = 1.0) -> pd.DataFrame:
    close = start + np.arange(rows, dtype=float) * step
    volume = 1000.0 + np.arange(rows, dtype=float)
    return _frame_from_close(close, volume)


def monotonic_down_fixture(rows: int = 260, start: float = 300.0, step: float = 1.0) -> pd.DataFrame:
    close = start - np.arange(rows, dtype=float) * step
    volume = 1000.0 + np.arange(rows, dtype=float)
    return _frame_from_close(close, volume)


def gap_fixture() -> pd.DataFrame:
    close = np.array([10.0, 10.5, 20.0, 19.0, 21.0, 30.0, 29.0, 31.0])
    high = np.array([10.2, 10.7, 21.0, 19.5, 21.4, 31.0, 29.5, 31.5])
    low = np.array([9.8, 10.2, 19.5, 18.5, 20.5, 29.0, 28.5, 30.5])
    return pd.DataFrame(
        {
            "date": pd.date_range("2020-01-01", periods=len(close), freq="D"),
            "open": close,
            "high": high,
            "low": low,
            "close": close,
            "volume": np.full(len(close), 1000.0),
        }
    )


def missing_values_fixture(rows: int = 40) -> pd.DataFrame:
    frame = monotonic_up_fixture(rows)
    frame.loc[5, "close"] = np.nan
    frame.loc[6, "high"] = np.nan
    frame.loc[7, "low"] = np.nan
    frame.loc[8, "volume"] = np.nan
    return frame


def short_history_fixture(rows: int = 4) -> pd.DataFrame:
    return monotonic_up_fixture(rows)


def known_manual_calculation_fixture() -> pd.DataFrame:
    close = np.array([10.0, 12.0, 11.0, 15.0, 14.0, 18.0])
    high = np.array([10.5, 12.5, 11.5, 15.5, 14.5, 18.5])
    low = np.array([9.5, 11.5, 10.5, 14.5, 13.5, 17.5])
    return pd.DataFrame(
        {
            "date": pd.date_range("2020-01-01", periods=len(close), freq="D"),
            "open": close,
            "high": high,
            "low": low,
            "close": close,
            "volume": np.array([1000.0, 1100.0, 900.0, 1200.0, 800.0, 1300.0]),
        }
    )
