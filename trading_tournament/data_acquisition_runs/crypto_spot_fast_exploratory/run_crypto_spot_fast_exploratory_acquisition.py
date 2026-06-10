from __future__ import annotations

import csv
import json
import shutil
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
CACHE_DIR = REPO_ROOT / "data" / "exploratory" / "crypto_spot_momentum" / "cache"
OUTPUT_ROOT = REPO_ROOT / "evidence" / "data_acquisition_runs" / "crypto_spot_fast_exploratory"
LATEST_DIR = OUTPUT_ROOT / "latest"
ZIP_PATH = OUTPUT_ROOT / "latest_crypto_spot_fast_acquisition_packet.zip"
ALLOWED_SYMBOLS = ["BTC-USD", "ETH-USD"]
REQUIRED_FILES = [
    "README_FOR_ADVISOR.md",
    "acquisition_summary.md",
    "acquisition_metadata.json",
    "symbol_coverage_summary.csv",
    "data_quality_summary.csv",
    "cache_write_manifest.csv",
    "warnings_and_limitations.md",
    "acquisition_manifest.json",
]


def load_symbol(symbol: str) -> pd.DataFrame:
    path = CACHE_DIR / f"yfinance_{symbol}.csv"
    if not path.exists():
        return pd.DataFrame()
    frame = pd.read_csv(path)
    if "date" not in frame.columns:
        return pd.DataFrame()
    frame = frame.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    return frame.dropna(subset=["date"]).sort_values("date")


def quality_row(symbol: str, frame: pd.DataFrame) -> dict[str, Any]:
    if frame.empty:
        return {
            "symbol": symbol,
            "cached_or_downloaded": False,
            "cache_written": False,
            "row_count": 0,
            "first_date": "",
            "last_date": "",
            "duplicate_date_count": 0,
            "missing_adjusted_close_or_close_count": "",
            "missing_close_count": "",
            "missing_volume_count": "",
            "adjusted_close_available": False,
            "close_available": False,
            "volume_available": False,
            "enough_rows_for_126d_momentum": False,
            "enough_rows_for_200d_sma": False,
            "enough_rows_for_180d_after_warmup": False,
            "quality_status": "fail",
            "notes": "cache_missing; no download attempted in cache-confirmation mode",
        }
    row_count = int(len(frame))
    has_adj = "adj_close" in frame.columns
    has_close = "close" in frame.columns
    has_volume = "volume" in frame.columns
    usable_price = pd.Series(dtype=float)
    if has_adj:
        usable_price = pd.to_numeric(frame["adj_close"], errors="coerce")
    elif has_close:
        usable_price = pd.to_numeric(frame["close"], errors="coerce")
    dup_count = int(frame["date"].duplicated().sum())
    missing_price = int(usable_price.isna().sum()) if not usable_price.empty else row_count
    missing_close = int(pd.to_numeric(frame["close"], errors="coerce").isna().sum()) if has_close else row_count
    missing_volume = int(pd.to_numeric(frame["volume"], errors="coerce").isna().sum()) if has_volume else row_count
    fail = bool(row_count < 380 or missing_price > 0 or not has_close or dup_count > 0)
    notes: list[str] = []
    if not has_adj and has_close:
        notes.append("missing adjusted close but usable close exists")
    notes.append("crypto trades 24/7; later research aligns to ETF/BIL trading days")
    notes.append("source limitations remain exploratory")
    return {
        "symbol": symbol,
        "cached_or_downloaded": True,
        "cache_written": False,
        "row_count": row_count,
        "first_date": frame["date"].min().date().isoformat(),
        "last_date": frame["date"].max().date().isoformat(),
        "duplicate_date_count": dup_count,
        "missing_adjusted_close_or_close_count": missing_price,
        "missing_close_count": missing_close,
        "missing_volume_count": missing_volume,
        "adjusted_close_available": has_adj,
        "close_available": has_close,
        "volume_available": has_volume,
        "enough_rows_for_126d_momentum": row_count >= 126,
        "enough_rows_for_200d_sma": row_count >= 200,
        "enough_rows_for_180d_after_warmup": row_count >= 380,
        "quality_status": "fail" if fail else "pass",
        "notes": "; ".join(notes),
    }


def csv_text(rows: list[dict[str, Any]], columns: list[str]) -> str:
    from io import StringIO

    handle = StringIO()
    writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return handle.getvalue()


def main() -> int:
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    rows = [quality_row(symbol, load_symbol(symbol)) for symbol in ALLOWED_SYMBOLS]
    cache_confirmed = [row["symbol"] for row in rows if row["quality_status"] in {"pass", "warning"}]
    failed = [row["symbol"] for row in rows if row["quality_status"] == "fail"]
    data_downloaded = False
    downloaded_symbols: list[str] = []

    if LATEST_DIR.exists():
        shutil.rmtree(LATEST_DIR)
    LATEST_DIR.mkdir(parents=True, exist_ok=True)
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()

    coverage_columns = ["symbol", "cached_or_downloaded", "cache_written", "row_count", "first_date", "last_date", "quality_status", "notes"]
    quality_columns = list(rows[0].keys()) if rows else []
    cache_rows = [
        {
            "symbol": row["symbol"],
            "cache_path": str(CACHE_DIR / f"yfinance_{row['symbol']}.csv"),
            "cache_written_this_run": False,
            "raw_ohlcv_in_evidence": False,
            "status": "cache_confirmed" if row["symbol"] in cache_confirmed else "cache_missing_or_failed",
        }
        for row in rows
    ]
    cache_columns = ["symbol", "cache_path", "cache_written_this_run", "raw_ohlcv_in_evidence", "status"]
    metadata = {
        "run_id": run_id,
        "provider": "existing_cache_first",
        "allowed_symbols": ALLOWED_SYMBOLS,
        "fallback_or_cash_benchmark": "BIL",
        "data_downloaded": data_downloaded,
        "downloaded_symbols": downloaded_symbols,
        "cache_confirmed_symbols": cache_confirmed,
        "failed_symbols": failed,
        "raw_ohlcv_in_evidence": False,
        "broker_integration": False,
        "exchange_execution": False,
        "live_orders": False,
        "order_placement": False,
        "real_money_recommendation": False,
    }
    manifest = {
        **metadata,
        "latest_folder_file_count": len(REQUIRED_FILES),
        "uses_leverage": False,
        "uses_margin": False,
        "uses_shorting": False,
        "uses_futures_contracts": False,
        "uses_perpetuals": False,
        "uses_options": False,
    }

    files = {
        "README_FOR_ADVISOR.md": "# README For Advisor\n\nThis is a crypto spot fast exploratory cache-status packet. It contains no raw OHLCV, no API keys, no broker integration, no exchange execution, no live orders, and no real-money recommendation.\n",
        "acquisition_summary.md": (
            "# Crypto Spot Fast Exploratory Acquisition Summary\n\n"
            f"run_id: `{run_id}`\n\n"
            "mode: `cache_status_no_download`\n\n"
            f"symbols_requested: `{','.join(ALLOWED_SYMBOLS)}`\n\n"
            f"cache_confirmed_symbols: `{','.join(cache_confirmed) or 'none'}`\n\n"
            f"downloaded_symbols: `{','.join(downloaded_symbols) or 'none'}`\n\n"
            f"failed_symbols: `{','.join(failed) or 'none'}`\n\n"
            "Raw OHLCV is excluded from this evidence packet.\n"
        ),
        "acquisition_metadata.json": json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        "symbol_coverage_summary.csv": csv_text(rows, coverage_columns),
        "data_quality_summary.csv": csv_text(rows, quality_columns),
        "cache_write_manifest.csv": csv_text(cache_rows, cache_columns),
        "warnings_and_limitations.md": "# Warnings And Limitations\n\n- Crypto spot data is exploratory and non-final.\n- BTC/ETH only for this batch.\n- Crypto trades 24/7 and is later aligned to ETF/BIL trading days for the research_sample engine.\n- No raw OHLCV in advisor packets.\n- No leverage, margin, shorting, futures, perpetuals, options, broker integration, exchange execution, live orders, or real-money recommendation.\n",
        "acquisition_manifest.json": json.dumps(manifest, indent=2, sort_keys=True) + "\n",
    }
    for name in REQUIRED_FILES:
        (LATEST_DIR / name).write_text(files[name], encoding="utf-8")
    observed = sorted(path.name for path in LATEST_DIR.iterdir() if path.is_file())
    if sorted(observed) != sorted(REQUIRED_FILES) or len(observed) > 10:
        raise RuntimeError(f"Crypto acquisition evidence contract failed: {observed}")
    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(LATEST_DIR.iterdir()):
            if path.is_file():
                zf.write(path, path.name)
    print(f"crypto_spot_fast_acquisition_latest_dir={LATEST_DIR}")
    print(f"crypto_spot_fast_acquisition_latest_zip={ZIP_PATH}")
    print(f"symbols_requested={','.join(ALLOWED_SYMBOLS)}")
    print(f"cache_confirmed_symbols={','.join(cache_confirmed) or 'none'}")
    print(f"downloaded_symbols={','.join(downloaded_symbols) or 'none'}")
    print(f"failed_symbols={','.join(failed) or 'none'}")
    print("data_downloaded=false")
    print("raw_ohlcv_in_evidence=false")
    print("real_money_recommendation=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
