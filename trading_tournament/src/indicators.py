from __future__ import annotations

import numpy as np
import pandas as pd


TRADING_DAYS = 252


def sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window=window, min_periods=window).mean()


def ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False, min_periods=span).mean()


def atr(df: pd.DataFrame, window: int = 20) -> pd.Series:
    prev_close = df["close"].shift(1)
    true_range = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - prev_close).abs(),
            (df["low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return true_range.rolling(window=window, min_periods=window).mean()


def rsi(series: pd.Series, window: int = 2) -> pd.Series:
    delta = series.diff()
    gains = delta.clip(lower=0)
    losses = -delta.clip(upper=0)
    avg_gain = gains.rolling(window=window, min_periods=window).mean()
    avg_loss = losses.rolling(window=window, min_periods=window).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    out = 100 - (100 / (1 + rs))
    out = out.where(avg_loss != 0, 100.0)
    out = out.where(avg_gain != 0, 0.0)
    return out


def bollinger_bands(series: pd.Series, window: int = 20, stds: float = 2.0) -> pd.DataFrame:
    mid = sma(series, window)
    sigma = series.rolling(window=window, min_periods=window).std(ddof=0)
    return pd.DataFrame(
        {
            "bb_mid": mid,
            "bb_upper": mid + stds * sigma,
            "bb_lower": mid - stds * sigma,
        }
    )


def realized_volatility(series: pd.Series, window: int = 20) -> pd.Series:
    return series.pct_change().rolling(window=window, min_periods=window).std() * np.sqrt(TRADING_DAYS)


def rolling_return(series: pd.Series, window: int) -> pd.Series:
    return series / series.shift(window) - 1.0


def rolling_high(series: pd.Series, window: int, shift: int = 1) -> pd.Series:
    return series.rolling(window=window, min_periods=window).max().shift(shift)


def consolidation_range(df: pd.DataFrame, window: int = 10) -> pd.Series:
    high = df["high"].rolling(window=window, min_periods=window).max()
    low = df["low"].rolling(window=window, min_periods=window).min()
    range_pct = (high - low) / df["close"]
    threshold = range_pct.rolling(window=TRADING_DAYS, min_periods=window).quantile(0.35)
    return range_pct <= threshold


def rolling_percentile_rank(series: pd.Series, window: int = 252, min_periods: int = 50) -> pd.Series:
    rolling = series.rolling(window=window, min_periods=min_periods)
    if hasattr(rolling, "rank"):
        return rolling.rank(pct=True)

    def pct_rank(values: np.ndarray) -> float:
        last = values[-1]
        if not np.isfinite(last):
            return np.nan
        finite = values[np.isfinite(values)]
        if len(finite) == 0:
            return np.nan
        return float((finite <= last).sum() / len(finite))

    return series.rolling(window=window, min_periods=min_periods).apply(pct_rank, raw=True)


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    out = df.sort_values("date").copy()
    out["sma_5"] = sma(out["close"], 5)
    out["ema_10"] = ema(out["close"], 10)
    out["sma_20"] = sma(out["close"], 20)
    out["sma_50"] = sma(out["close"], 50)
    out["sma_100"] = sma(out["close"], 100)
    out["sma_200"] = sma(out["close"], 200)
    out["atr_20"] = atr(out, 20)
    out["atr_10"] = atr(out, 10)
    out["rsi_2"] = rsi(out["close"], 2)
    bands = bollinger_bands(out["close"], 20, 2.0)
    out = pd.concat([out, bands], axis=1)
    out["rv_20"] = realized_volatility(out["close"], 20)
    out["rv_60"] = realized_volatility(out["close"], 60)
    out["ret_63"] = rolling_return(out["close"], 63)
    out["ret_126"] = rolling_return(out["close"], 126)
    out["ret_252"] = rolling_return(out["close"], 252)
    out["high_20"] = rolling_high(out["close"], 20, shift=1)
    out["avg_volume_20"] = out["volume"].rolling(window=20, min_periods=20).mean()
    out["is_consolidating_10"] = consolidation_range(out, 10)
    out["atr_10_percentile"] = rolling_percentile_rank(out["atr_10"], 252, 50)
    return out


def _spy_regime(spy: pd.DataFrame) -> pd.DataFrame:
    out = spy[["date", "close", "sma_200", "rv_20"]].copy()
    q75 = out["rv_20"].rolling(window=252, min_periods=63).quantile(0.75)
    q25 = out["rv_20"].rolling(window=252, min_periods=63).quantile(0.25)
    out["spy_rv_20_q75"] = q75.shift(1)

    regime = []
    for close, sma200, rv, hi, lo in zip(out["close"], out["sma_200"], out["rv_20"], q75, q25, strict=False):
        if not np.isfinite(close) or not np.isfinite(sma200):
            trend = "unknown"
        elif abs(close / sma200 - 1.0) <= 0.05:
            trend = "sideways"
        elif close > sma200:
            trend = "bull"
        else:
            trend = "bear"

        if not np.isfinite(rv) or not np.isfinite(hi) or not np.isfinite(lo):
            vol = "vol_unknown"
        elif rv > hi:
            vol = "high_volatility"
        elif rv < lo:
            vol = "low_volatility"
        else:
            vol = "normal_volatility"
        regime.append(f"{trend}_{vol}")

    out["market_regime"] = regime
    return out[["date", "market_regime", "spy_rv_20_q75"]]


def prepare_indicators(data: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    prepared = {symbol: add_indicators(df) for symbol, df in data.items()}
    if "SPY" in prepared:
        spy_regime = _spy_regime(prepared["SPY"])
        for symbol, df in prepared.items():
            prepared[symbol] = df.merge(spy_regime, on="date", how="left")
            prepared[symbol]["market_regime"] = prepared[symbol]["market_regime"].fillna("unknown")
    else:
        for symbol, df in prepared.items():
            prepared[symbol]["market_regime"] = "unknown"
    return prepared


def indicators_ready(row: pd.Series, columns: list[str]) -> bool:
    return all(pd.notna(row.get(col)) and np.isfinite(row.get(col)) for col in columns)
