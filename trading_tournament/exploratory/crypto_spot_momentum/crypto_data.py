from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd


NORMALIZED_COLUMNS = [
    "date",
    "open",
    "high",
    "low",
    "close",
    "adj_close",
    "volume",
    "symbol",
    "source",
]


DATA_LIMITATION_NOTES = [
    "yfinance crypto data is Tier 1 exploratory only.",
    "Exchange-specific crypto prices may differ.",
    "Crypto trades 24/7 and daily bar timestamps can differ by source.",
    "No bid/ask spread, order book depth, exchange outage, delisting, custody, or stablecoin risk is modeled.",
]


class CryptoDataError(RuntimeError):
    """Raised when exploratory crypto data cannot be loaded."""


@dataclass(frozen=True)
class DataLoadResult:
    data: pd.DataFrame
    coverage: pd.DataFrame
    source: str
    network_download_occurred: bool
    warnings: list[str]


def normalize_ohlcv(raw: pd.DataFrame, symbol: str, source: str) -> pd.DataFrame:
    """Normalize vendor OHLCV into the exploratory lane convention."""
    if raw is None or raw.empty:
        return pd.DataFrame(columns=NORMALIZED_COLUMNS)

    df = raw.copy()
    if isinstance(df.columns, pd.MultiIndex):
        if symbol in df.columns.get_level_values(-1):
            df = df.xs(symbol, axis=1, level=-1)
        elif symbol in df.columns.get_level_values(0):
            df = df.xs(symbol, axis=1, level=0)
        else:
            df.columns = [str(col[-1] if isinstance(col, tuple) else col) for col in df.columns]

    rename = {
        "Date": "date",
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Adj Close": "adj_close",
        "Adj_Close": "adj_close",
        "Volume": "volume",
        "open": "open",
        "high": "high",
        "low": "low",
        "close": "close",
        "adj_close": "adj_close",
        "volume": "volume",
    }
    df = df.rename(columns=rename)
    if "date" not in df.columns:
        df = df.reset_index().rename(columns=rename)

    required = ["date", "open", "high", "low", "close", "volume"]
    for col in required:
        if col not in df.columns:
            df[col] = pd.NA
    if "adj_close" not in df.columns:
        df["adj_close"] = df["close"]
    df["adj_close"] = df["adj_close"].fillna(df["close"])

    out = df[["date", "open", "high", "low", "close", "adj_close", "volume"]].copy()
    out["date"] = pd.to_datetime(out["date"], utc=True, errors="coerce").dt.tz_convert(None).dt.normalize()
    for col in ["open", "high", "low", "close", "adj_close", "volume"]:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    out["symbol"] = symbol
    out["source"] = source
    out = out.dropna(subset=["date"]).sort_values("date")
    out = out.drop_duplicates(subset=["date", "symbol"], keep="last")
    return out[NORMALIZED_COLUMNS].reset_index(drop=True)


def build_data_coverage(
    symbol: str,
    source: str,
    data: pd.DataFrame,
    excluded_reason: str = "",
) -> dict[str, Any]:
    if data.empty:
        return {
            "symbol": symbol,
            "source": source,
            "first_date": "",
            "last_date": "",
            "row_count": 0,
            "missing_ohlc_count": 0,
            "missing_volume_count": 0,
            "excluded_reason": excluded_reason or "no_data",
        }
    ohlc_cols = ["open", "high", "low", "close", "adj_close"]
    missing_ohlc = int(data[ohlc_cols].isna().any(axis=1).sum())
    nonpositive = int((data[ohlc_cols] <= 0).any(axis=1).sum())
    reason = excluded_reason
    if missing_ohlc:
        reason = "missing_ohlc"
    elif nonpositive:
        reason = "nonpositive_ohlc"
    return {
        "symbol": symbol,
        "source": source,
        "first_date": data["date"].min().date().isoformat(),
        "last_date": data["date"].max().date().isoformat(),
        "row_count": int(len(data)),
        "missing_ohlc_count": missing_ohlc,
        "missing_volume_count": int(data["volume"].isna().sum()),
        "excluded_reason": reason,
    }


def cache_file(cache_dir: Path, symbol: str, source: str) -> Path:
    safe_symbol = symbol.replace("/", "-")
    return cache_dir / f"{source}_{safe_symbol}.csv"


def load_cached_symbol(cache_dir: Path, symbol: str, source: str) -> pd.DataFrame:
    path = cache_file(cache_dir, symbol, source)
    if not path.exists():
        return pd.DataFrame(columns=NORMALIZED_COLUMNS)
    cached = pd.read_csv(path)
    return normalize_ohlcv(cached, symbol=symbol, source=source)


def download_yfinance_symbol(symbol: str, start_date: str, end_date: str | None) -> pd.DataFrame:
    try:
        import yfinance as yf
    except ImportError as exc:
        raise CryptoDataError("yfinance is required for the default crypto exploratory data source.") from exc

    kwargs: dict[str, Any] = {
        "auto_adjust": False,
        "progress": False,
        "actions": False,
    }
    if end_date and end_date != "latest":
        kwargs["end"] = end_date
    raw = yf.download(symbol, start=start_date, **kwargs)
    return normalize_ohlcv(raw, symbol=symbol, source="yfinance")


def download_ccxt_symbol(symbol: str, exchange_name: str, start_date: str, timeframe: str) -> pd.DataFrame:
    try:
        import ccxt  # type: ignore
    except ImportError as exc:
        raise CryptoDataError("ccxt is optional and is not installed. Use --source yfinance or install ccxt separately.") from exc

    exchange_cls = getattr(ccxt, exchange_name)
    exchange = exchange_cls({"enableRateLimit": True})
    since = int(pd.Timestamp(start_date, tz="UTC").timestamp() * 1000)
    rows = exchange.fetch_ohlcv(symbol, timeframe=timeframe, since=since)
    raw = pd.DataFrame(rows, columns=["date", "open", "high", "low", "close", "volume"])
    raw["date"] = pd.to_datetime(raw["date"], unit="ms", utc=True)
    return normalize_ohlcv(raw, symbol=symbol.replace("/", "-"), source=f"ccxt_{exchange_name}")


def load_crypto_data(
    config: dict[str, Any],
    source: str = "yfinance",
    no_network: bool = False,
    reuse_cache: bool = True,
    force_download: bool = False,
) -> DataLoadResult:
    data_cfg = config["data"]
    cache_dir = Path(data_cfg["cache_dir"])
    cache_dir.mkdir(parents=True, exist_ok=True)

    if source == "yfinance":
        symbols = data_cfg["yfinance_symbols"]
        source_name = "yfinance"
    elif source == "ccxt":
        symbols = data_cfg["ccxt_symbols"]
        source_name = f"ccxt_{data_cfg.get('ccxt_exchange', 'coinbase')}"
    else:
        raise CryptoDataError(f"Unsupported crypto data source: {source}")

    frames: list[pd.DataFrame] = []
    coverage_rows: list[dict[str, Any]] = []
    network_download_occurred = False
    errors: list[str] = []

    for symbol in symbols:
        cached = pd.DataFrame(columns=NORMALIZED_COLUMNS)
        if reuse_cache and not force_download:
            cached = load_cached_symbol(cache_dir, symbol if source == "yfinance" else symbol.replace("/", "-"), source_name)
        if not cached.empty and not force_download:
            frames.append(cached)
            coverage_rows.append(build_data_coverage(cached["symbol"].iloc[0], source_name, cached))
            continue

        if no_network or not data_cfg.get("allow_network_download", True):
            symbol_for_coverage = symbol if source == "yfinance" else symbol.replace("/", "-")
            coverage_rows.append(build_data_coverage(symbol_for_coverage, source_name, cached, "no_cache_network_disabled"))
            errors.append(f"No cached data for {symbol_for_coverage} and network download is disabled.")
            continue

        try:
            if source == "yfinance":
                downloaded = download_yfinance_symbol(symbol, data_cfg["start_date"], data_cfg.get("end_date"))
                cache_symbol = symbol
            else:
                downloaded = download_ccxt_symbol(
                    symbol,
                    exchange_name=data_cfg.get("ccxt_exchange", "coinbase"),
                    start_date=data_cfg["start_date"],
                    timeframe=data_cfg.get("timeframe", "1d"),
                )
                cache_symbol = symbol.replace("/", "-")
            network_download_occurred = True
            if downloaded.empty:
                coverage_rows.append(build_data_coverage(cache_symbol, source_name, downloaded, "download_returned_empty"))
                errors.append(f"Download returned no rows for {cache_symbol}.")
                continue
            downloaded.to_csv(cache_file(cache_dir, cache_symbol, source_name), index=False)
            frames.append(downloaded)
            coverage_rows.append(build_data_coverage(downloaded["symbol"].iloc[0], source_name, downloaded))
        except Exception as exc:  # noqa: BLE001 - must produce a clear exploratory data failure.
            fallback_symbol = symbol if source == "yfinance" else symbol.replace("/", "-")
            fallback = load_cached_symbol(cache_dir, fallback_symbol, source_name)
            if not fallback.empty:
                frames.append(fallback)
                coverage_rows.append(build_data_coverage(fallback["symbol"].iloc[0], source_name, fallback))
                errors.append(f"Download failed for {fallback_symbol}; used cached data. Error: {exc}")
            else:
                coverage_rows.append(build_data_coverage(fallback_symbol, source_name, fallback, "download_failed_no_cache"))
                errors.append(f"Download failed for {fallback_symbol} and no cache was available. Error: {exc}")

    coverage = pd.DataFrame(coverage_rows)
    if not frames:
        raise CryptoDataError("No crypto data available. " + " ".join(errors))

    data = pd.concat(frames, ignore_index=True).sort_values(["symbol", "date"])
    bad = data[["open", "high", "low", "close", "adj_close"]].isna().any(axis=1) | (
        data[["open", "high", "low", "close", "adj_close"]] <= 0
    ).any(axis=1)
    data = data.loc[~bad].reset_index(drop=True)
    if data.empty:
        raise CryptoDataError("Crypto data was loaded, but all rows had invalid OHLC values.")

    warnings = DATA_LIMITATION_NOTES + errors
    return DataLoadResult(
        data=data,
        coverage=coverage,
        source=source_name,
        network_download_occurred=network_download_occurred,
        warnings=warnings,
    )
