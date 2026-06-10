from __future__ import annotations

import numpy as np
import pandas as pd

from src.data import build_adjusted_ohlc
from src.indicators import atr, ema, rsi, sma


def test_adjusted_ohlc_construction_preserves_raw_and_adjusts_prices():
    raw = pd.DataFrame(
        {
            "Date": pd.date_range("2020-01-01", periods=2),
            "Open": [100.0, 110.0],
            "High": [120.0, 130.0],
            "Low": [90.0, 100.0],
            "Close": [100.0, 120.0],
            "Adj Close": [50.0, 60.0],
            "Volume": [1000, 2000],
            "Dividends": [0.0, 0.1],
            "Stock Splits": [0.0, 0.0],
        }
    )
    adjusted = build_adjusted_ohlc(raw, "TST")

    assert adjusted.loc[0, "raw_open"] == 100.0
    assert adjusted.loc[0, "adjustment_factor"] == 0.5
    assert adjusted.loc[0, "open"] == 50.0
    assert adjusted.loc[0, "high"] == 60.0
    assert adjusted.loc[0, "low"] == 45.0
    assert adjusted.loc[0, "close"] == 50.0
    assert adjusted.loc[0, "volume"] == 1000


def test_sma_ema_warmup_behavior():
    values = pd.Series([1, 2, 3, 4, 5], dtype=float)

    simple = sma(values, 3)
    exponential = ema(values, 3)

    assert simple.iloc[:2].isna().all()
    assert simple.iloc[2] == 2.0
    assert exponential.iloc[:2].isna().all()
    assert np.isfinite(exponential.iloc[2])


def test_atr_and_rsi_calculations_have_expected_warmup():
    df = pd.DataFrame(
        {
            "high": [11, 12, 13, 14, 15],
            "low": [9, 10, 11, 12, 13],
            "close": [10, 11, 12, 13, 14],
        },
        dtype=float,
    )
    out_atr = atr(df, 3)
    out_rsi = rsi(df["close"], 2)

    assert out_atr.iloc[:2].isna().all()
    assert out_atr.iloc[2] == 2.0
    assert out_rsi.iloc[:2].isna().all()
    assert out_rsi.iloc[-1] == 100.0
