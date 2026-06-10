from __future__ import annotations

import inspect
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .utils import ensure_dir, sha256_file


RAW_COLUMNS = [
    "raw_open",
    "raw_high",
    "raw_low",
    "raw_close",
    "raw_adj_close",
    "raw_volume",
    "dividends",
    "stock_splits",
]

NORMALIZED_COLUMNS = [
    "date",
    *RAW_COLUMNS,
    "adjustment_factor",
    "open",
    "high",
    "low",
    "close",
    "adj_close",
    "volume",
    "symbol",
]


class DataQualityError(RuntimeError):
    """Raised when a symbol cannot be used without violating data assumptions."""


@dataclass
class DataLoadResult:
    data: dict[str, pd.DataFrame]
    coverage: pd.DataFrame
    data_source: str
    yfinance_params: dict[str, Any]


def _flatten_yfinance_columns(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    if not isinstance(df.columns, pd.MultiIndex):
        return df.copy()

    # yfinance can return either (field, ticker) or (ticker, field).
    for level in range(df.columns.nlevels):
        if symbol in df.columns.get_level_values(level):
            try:
                return df.xs(symbol, axis=1, level=level, drop_level=True).copy()
            except KeyError:
                pass

    flattened = df.copy()
    flattened.columns = [
        "_".join(str(part) for part in col if str(part) and str(part) != symbol)
        for col in flattened.columns
    ]
    return flattened


def _normal_name(name: Any) -> str:
    return str(name).strip().lower().replace(" ", "_").replace("-", "_")


def _standardize_raw_columns(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    frame = _flatten_yfinance_columns(df, symbol).copy()
    if "date" not in {_normal_name(c) for c in frame.columns}:
        frame = frame.reset_index()

    renamed = {_normal_name(col): col for col in frame.columns}
    aliases = {
        "date": ["date", "datetime"],
        "raw_open": ["raw_open", "open"],
        "raw_high": ["raw_high", "high"],
        "raw_low": ["raw_low", "low"],
        "raw_close": ["raw_close", "close"],
        "raw_adj_close": ["raw_adj_close", "adj_close", "adjusted_close"],
        "raw_volume": ["raw_volume", "volume"],
        "dividends": ["dividends", "dividend"],
        "stock_splits": ["stock_splits", "stock_splits_", "splits", "stock_split"],
    }

    out = pd.DataFrame()
    for target, candidates in aliases.items():
        source = next((renamed[c] for c in candidates if c in renamed), None)
        if source is None:
            if target in {"dividends", "stock_splits"}:
                out[target] = 0.0
                continue
            raise DataQualityError(f"{symbol}: missing required column {target}")
        out[target] = frame[source]

    out["date"] = pd.to_datetime(out["date"], utc=False).dt.tz_localize(None)
    out = out.sort_values("date").drop_duplicates("date", keep="last")
    return out


def build_adjusted_ohlc(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    raw = _standardize_raw_columns(df, symbol)

    numeric_cols = [c for c in RAW_COLUMNS if c != "stock_splits"]
    for col in numeric_cols + ["stock_splits"]:
        raw[col] = pd.to_numeric(raw[col], errors="coerce")

    missing_adj = raw["raw_adj_close"].isna().sum()
    missing_close = raw["raw_close"].isna().sum()
    missing_ohlc = raw[["raw_open", "raw_high", "raw_low", "raw_close"]].isna().any(axis=1).sum()
    non_positive = (
        (raw[["raw_open", "raw_high", "raw_low", "raw_close", "raw_adj_close"]] <= 0)
        .any(axis=1)
        .sum()
    )
    if missing_adj or missing_close:
        raise DataQualityError(
            f"{symbol}: missing adjusted close or close values "
            f"(adj={missing_adj}, close={missing_close})"
        )
    if missing_ohlc or non_positive:
        raise DataQualityError(
            f"{symbol}: missing/non-positive OHLC data "
            f"(missing_ohlc={missing_ohlc}, non_positive={non_positive})"
        )

    raw["raw_volume"] = raw["raw_volume"].fillna(0)
    raw["dividends"] = raw["dividends"].fillna(0)
    raw["stock_splits"] = raw["stock_splits"].fillna(0)
    raw["adjustment_factor"] = raw["raw_adj_close"] / raw["raw_close"]
    invalid_factor = (
        raw["adjustment_factor"].isna()
        | ~np.isfinite(raw["adjustment_factor"])
        | (raw["adjustment_factor"] <= 0)
    )
    if invalid_factor.any():
        raise DataQualityError(f"{symbol}: invalid adjustment factor")

    raw["open"] = raw["raw_open"] * raw["adjustment_factor"]
    raw["high"] = raw["raw_high"] * raw["adjustment_factor"]
    raw["low"] = raw["raw_low"] * raw["adjustment_factor"]
    raw["close"] = raw["raw_adj_close"]
    raw["adj_close"] = raw["raw_adj_close"]
    raw["volume"] = raw["raw_volume"]
    raw["symbol"] = symbol

    normalized = raw[NORMALIZED_COLUMNS].copy()
    if normalized[["open", "high", "low", "close"]].isna().any().any():
        raise DataQualityError(f"{symbol}: adjusted OHLC contains missing values")
    if (normalized[["open", "high", "low", "close"]] <= 0).any().any():
        raise DataQualityError(f"{symbol}: adjusted OHLC contains non-positive prices")
    return normalized


def _coverage_row(
    symbol: str,
    status: str,
    df: pd.DataFrame | None,
    excluded_reason: str,
    cache_file: Path,
) -> dict[str, Any]:
    cache_hash = sha256_file(cache_file) if cache_file.exists() else ""
    if df is None or df.empty:
        return {
            "symbol": symbol,
            "status": status,
            "first_date": "",
            "last_date": "",
            "row_count": 0,
            "missing_ohlc_count": "",
            "missing_adj_close_count": "",
            "excluded_reason": excluded_reason,
            "cache_file": str(cache_file),
            "cache_file_hash": cache_hash,
        }
    return {
        "symbol": symbol,
        "status": status,
        "first_date": str(pd.to_datetime(df["date"]).min().date()),
        "last_date": str(pd.to_datetime(df["date"]).max().date()),
        "row_count": int(len(df)),
        "missing_ohlc_count": int(df[["open", "high", "low", "close"]].isna().any(axis=1).sum()),
        "missing_adj_close_count": int(df["adj_close"].isna().sum()),
        "excluded_reason": excluded_reason,
        "cache_file": str(cache_file),
        "cache_file_hash": cache_hash,
    }


def _read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path)


def _download_yfinance(symbol: str, start: str, end: str | None, params: dict[str, Any]) -> pd.DataFrame:
    import yfinance as yf

    kwargs = {
        "start": start,
        "end": end,
        "auto_adjust": bool(params.get("auto_adjust", False)),
        "actions": bool(params.get("actions", True)),
        "progress": bool(params.get("progress", False)),
    }
    if "multi_level_index" in inspect.signature(yf.download).parameters:
        kwargs["multi_level_index"] = bool(params.get("multi_level_index", False))
    if "timeout" in inspect.signature(yf.download).parameters and params.get("timeout") is not None:
        kwargs["timeout"] = float(params.get("timeout", 10))

    try:
        return yf.download(symbol, **kwargs)
    except TypeError as exc:
        if "multi_level_index" not in str(exc):
            raise
        kwargs.pop("multi_level_index", None)
        return yf.download(symbol, **kwargs)


def load_symbol_data(
    symbol: str,
    config: dict[str, Any],
    root: Path,
) -> tuple[pd.DataFrame | None, dict[str, Any], str]:
    data_cfg = config["data"]
    cache_dir = ensure_dir(root / data_cfg["cache_dir"])
    raw_dir = ensure_dir(root / data_cfg["raw_dir"])
    cache_file = cache_dir / f"{symbol}.csv"
    raw_file = raw_dir / f"{symbol}.csv"
    use_cache = bool(data_cfg.get("use_cache", True))
    refresh_cache = bool(data_cfg.get("refresh_cache", False))

    try:
        if use_cache and cache_file.exists() and not refresh_cache:
            cached = _read_csv(cache_file)
            normalized = build_adjusted_ohlc(cached, symbol)
            return normalized, _coverage_row(symbol, "valid", normalized, "", cache_file), "cache"

        source = "yfinance"
        try:
            raw = _download_yfinance(
                symbol,
                str(data_cfg["start_date"]),
                data_cfg.get("end_date"),
                data_cfg.get("yfinance", {}),
            )
            if raw.empty:
                raise DataQualityError(f"{symbol}: yfinance returned no rows")
        except Exception as exc:
            if not raw_file.exists():
                raise DataQualityError(
                    f"{symbol}: yfinance failed and no CSV fallback found at {raw_file}: {exc}"
                ) from exc
            raw = _read_csv(raw_file)
            source = "raw_csv_fallback"

        normalized = build_adjusted_ohlc(raw, symbol)
        normalized.to_csv(cache_file, index=False)
        return normalized, _coverage_row(symbol, "valid", normalized, "", cache_file), source
    except DataQualityError as exc:
        return None, _coverage_row(symbol, "excluded", None, str(exc), cache_file), "excluded"


def load_market_data(config: dict[str, Any], root: Path) -> DataLoadResult:
    symbols = list(dict.fromkeys(config["universe"]["symbols"]))
    data: dict[str, pd.DataFrame] = {}
    rows: list[dict[str, Any]] = []
    sources: list[str] = []
    for symbol in symbols:
        df, coverage, source = load_symbol_data(symbol, config, root)
        rows.append(coverage)
        sources.append(source)
        if df is not None and not df.empty:
            data[symbol] = df

    coverage_df = pd.DataFrame(rows)
    if not data:
        raise RuntimeError(
            "No valid market data loaded. Check network access to Yahoo Finance "
            "or provide CSV fallbacks under data/raw/*.csv."
        )
    source_summary = ",".join(f"{src}:{sources.count(src)}" for src in sorted(set(sources)))
    return DataLoadResult(
        data=data,
        coverage=coverage_df,
        data_source=source_summary,
        yfinance_params=config["data"].get("yfinance", {}),
    )
