from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import platform
import shutil
import sys
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path
from typing import Any, Callable

import pandas as pd
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.data import DataQualityError, build_adjusted_ohlc


SUBJECT_ID = "global_multi_asset_fast_exploratory"
APPROVED_SYMBOLS = (
    "SPY",
    "QQQ",
    "GLD",
    "IEF",
    "BIL",
    "DBC",
    "PDBC",
    "COMT",
    "GSG",
    "USCI",
    "IWM",
    "EFA",
    "EEM",
    "TLT",
)
STRATEGY_UNIVERSE_SYMBOLS = ("SPY", "QQQ", "IWM", "EFA", "EEM", "IEF", "TLT", "GLD", "PDBC", "COMT", "BIL")
CONFIG_PATH = Path(__file__).resolve().with_name("acquisition_config.yaml")
EVIDENCE_ROOT = REPO_ROOT / "evidence" / "data_acquisition_runs" / SUBJECT_ID
LATEST_DIR = EVIDENCE_ROOT / "latest"
LATEST_ZIP = EVIDENCE_ROOT / "latest_global_multi_asset_acquisition_packet.zip"
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

Downloader = Callable[[str, dict[str, Any]], pd.DataFrame]


@dataclass
class AcquisitionOutputs:
    run_id: str
    run_dir: Path
    latest_dir: Path
    zip_path: Path
    coverage: pd.DataFrame
    quality: pd.DataFrame
    cache_manifest: pd.DataFrame
    manifest: dict[str, Any]


def utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def load_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def validate_requested_symbols(config: dict[str, Any]) -> list[str]:
    approved = [str(symbol).upper() for symbol in config.get("approved_symbols", [])]
    if approved != list(APPROVED_SYMBOLS):
        raise ValueError(f"approved_symbols must be exactly {', '.join(APPROVED_SYMBOLS)}")
    strategy_symbols = [str(symbol).upper() for symbol in config.get("strategy_universe_symbols", [])]
    if strategy_symbols != list(STRATEGY_UNIVERSE_SYMBOLS):
        raise ValueError(f"strategy_universe_symbols must be exactly {', '.join(STRATEGY_UNIVERSE_SYMBOLS)}")
    return approved


def package_versions() -> dict[str, str]:
    versions: dict[str, str] = {}
    for package in ["pandas", "numpy", "yfinance", "PyYAML"]:
        try:
            versions[package] = metadata.version(package)
        except metadata.PackageNotFoundError:
            versions[package] = "not_installed"
    return versions


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def default_yfinance_downloader(symbol: str, request_settings: dict[str, Any]) -> pd.DataFrame:
    import yfinance as yf

    kwargs: dict[str, Any] = {
        "start": request_settings.get("start", "2006-01-01"),
        "end": request_settings.get("end"),
        "auto_adjust": bool(request_settings.get("auto_adjust", False)),
        "actions": bool(request_settings.get("actions", True)),
        "progress": bool(request_settings.get("progress", False)),
    }
    if kwargs["end"] is None:
        kwargs.pop("end")
    signature = inspect.signature(yf.download)
    if "multi_level_index" in signature.parameters:
        kwargs["multi_level_index"] = bool(request_settings.get("multi_level_index", False))
    if "timeout" in signature.parameters and request_settings.get("timeout") is not None:
        kwargs["timeout"] = float(request_settings.get("timeout", 30))
    try:
        return yf.download(symbol, **kwargs)
    except TypeError as exc:
        if "multi_level_index" not in str(exc):
            raise
        kwargs.pop("multi_level_index", None)
        return yf.download(symbol, **kwargs)


def normalized_date_series(frame: pd.DataFrame) -> pd.Series:
    return pd.to_datetime(frame["date"], errors="coerce").dt.tz_localize(None)


def read_existing_cache(cache_path: Path, symbol: str) -> pd.DataFrame:
    cached = pd.read_csv(cache_path)
    return build_adjusted_ohlc(cached, symbol)


def normalize_download(raw: pd.DataFrame, symbol: str) -> pd.DataFrame:
    if raw is None or raw.empty:
        raise DataQualityError(f"{symbol}: provider returned no rows")
    return build_adjusted_ohlc(raw, symbol)


def analyze_symbol(
    symbol: str,
    normalized: pd.DataFrame | None,
    cache_path: Path,
    source_status: str,
    error: str = "",
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    cached_or_downloaded = normalized is not None and not normalized.empty
    cache_written = cached_or_downloaded and cache_path.exists()
    duplicate_date_count = 0
    missing_adj = missing_close = missing_volume = 0
    adjusted_close_available = raw_close_available = volume_available = False

    if normalized is not None and not normalized.empty:
        dates = normalized_date_series(normalized)
        duplicate_date_count = int(dates.duplicated().sum())
        missing_adj = int(normalized["adj_close"].isna().sum()) if "adj_close" in normalized else len(normalized)
        missing_close = int(normalized["close"].isna().sum()) if "close" in normalized else len(normalized)
        missing_volume = int(normalized["volume"].isna().sum()) if "volume" in normalized else len(normalized)
        adjusted_close_available = "adj_close" in normalized and missing_adj < len(normalized)
        raw_close_available = "close" in normalized and missing_close < len(normalized)
        volume_available = "volume" in normalized and missing_volume < len(normalized)

    row_count = int(len(normalized)) if normalized is not None else 0
    first_date = str(normalized_date_series(normalized).min().date()) if normalized is not None and not normalized.empty else ""
    last_date = str(normalized_date_series(normalized).max().date()) if normalized is not None and not normalized.empty else ""
    enough_126 = row_count >= 126
    enough_200 = row_count >= 200
    enough_180_after_warmup = row_count >= 380

    if error or not cached_or_downloaded or not cache_written or not adjusted_close_available or not raw_close_available or duplicate_date_count or not enough_180_after_warmup:
        quality_status = "fail"
    elif missing_volume:
        quality_status = "warning"
    else:
        quality_status = "pass"

    if error:
        notes = error
    elif quality_status == "pass" and source_status == "cache_confirmed":
        notes = "existing local cache confirmed; exploratory ETF/fund wrapper QA passed"
    elif quality_status == "pass":
        notes = "missing approved symbol downloaded and cached; exploratory ETF/fund wrapper QA passed"
    elif quality_status == "warning":
        notes = "warning: usable adjusted prices but volume/actions/product metadata need caution"
    else:
        notes = "failed basic fast exploratory QA"

    coverage = {
        "symbol": symbol,
        "cached_or_downloaded": cached_or_downloaded,
        "cache_written": cache_written,
        "source_status": source_status,
        "row_count": row_count,
        "first_date": first_date,
        "last_date": last_date,
        "coverage_status": quality_status,
        "notes": notes,
    }
    quality = {
        "symbol": symbol,
        "cached_or_downloaded": cached_or_downloaded,
        "cache_written": cache_written,
        "row_count": row_count,
        "first_date": first_date,
        "last_date": last_date,
        "duplicate_date_count": duplicate_date_count,
        "missing_adjusted_close_count": missing_adj,
        "missing_close_count": missing_close,
        "missing_volume_count": missing_volume,
        "adjusted_close_available": adjusted_close_available,
        "raw_close_available": raw_close_available,
        "volume_available": volume_available,
        "enough_rows_for_126d_momentum": enough_126,
        "enough_rows_for_200d_sma": enough_200,
        "enough_rows_for_180d_after_warmup": enough_180_after_warmup,
        "quality_status": quality_status,
        "notes": notes,
    }
    cache = {
        "symbol": symbol,
        "cache_path": str(cache_path.relative_to(REPO_ROOT)),
        "source_status": source_status,
        "cache_written": cache_written,
        "rows_available": row_count if cache_written else 0,
        "sha256": sha256_file(cache_path) if cache_written else "",
        "write_status": source_status if cache_written else "failed",
    }
    return coverage, quality, cache


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sync_latest_and_zip(run_dir: Path, latest_dir: Path, zip_path: Path) -> None:
    if latest_dir.exists():
        shutil.rmtree(latest_dir)
    latest_dir.mkdir(parents=True, exist_ok=True)
    for path in sorted(run_dir.iterdir()):
        if path.is_file():
            shutil.copy2(path, latest_dir / path.name)
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(latest_dir.iterdir()):
            if path.is_file():
                archive.write(path, path.name)


def write_report_files(
    run_dir: Path,
    run_id: str,
    config: dict[str, Any],
    metadata: dict[str, Any],
    coverage: pd.DataFrame,
    quality: pd.DataFrame,
    cache_manifest: pd.DataFrame,
    manifest: dict[str, Any],
) -> None:
    cache_confirmed = manifest["cache_confirmed_symbols"]
    downloaded = manifest["downloaded_symbols"]
    failed = manifest["failed_symbols"]
    quality_counts = manifest["quality_counts"]
    readme = f"""# README For Advisor

This is a compact Global Multi-Asset ETF Fast Exploration Batch 1 acquisition packet for `{SUBJECT_ID}`.

It used existing cache first and a yfinance-compatible public-data path only for missing approved ETF/fund wrapper symbols. No unapproved symbols, keyed API provider, API key, secret, broker integration, live order, or order placement is included.

Raw OHLCV is excluded from this compact evidence packet and from advisor upload packets. Raw cache files, if written, remain under `data/cache/`.

This acquisition does not implement a strategy, run a backtest, run Profit Exploration, run candidate_exhaustive, activate paper-forward, add leverage, margin, shorting, futures contracts, options, forex, intraday logic, or make a real-money recommendation.
"""
    summary = f"""# Acquisition Summary

run_id: `{run_id}`

provider: `{config.get('provider')}`

approved_symbols: {', '.join(APPROVED_SYMBOLS)}

strategy_universe_symbols: {', '.join(STRATEGY_UNIVERSE_SYMBOLS)}

cache_confirmed_symbols: {', '.join(cache_confirmed) or 'none'}

symbols_downloaded: {', '.join(downloaded) or 'none'}

symbols_failed: {', '.join(failed) or 'none'}

quality_counts: pass={quality_counts['pass']}, warning={quality_counts['warning']}, fail={quality_counts['fail']}

This is early-stage exploratory ETF/fund wrapper data. International ETF, emerging-market ETF, duration, gold, commodity wrapper, product identity, tax, roll-yield, issuer methodology, and wrapper economics remain non-final.

No raw OHLCV is included in this packet. No real-money recommendation is made.
"""
    warnings = """# Warnings And Limitations

- yfinance-compatible data can have revisions, missing actions, adjustment differences, provider outages, and ticker mapping errors.
- This is exploratory public-data ETF/fund wrapper evidence only.
- International and emerging-market ETFs add currency, country, liquidity, and tracking risks.
- Duration ETFs add interest-rate and duration-regime risks.
- Commodity wrapper returns may reflect futures-linked indexes, collateral, fees, product methodology, and roll yield.
- Wrapper adjusted-price modeling is not direct futures strategy evidence.
- No futures contracts, futures roll logic, leverage, margin, shorting, options, forex, or intraday logic are added.
- Candidate_exhaustive and paper-forward approval remain blocked.
- Raw OHLCV is excluded from compact/advisor evidence.
- No broker integration, live orders, order placement, or real-money recommendation is included.
"""
    (run_dir / "README_FOR_ADVISOR.md").write_text(readme, encoding="utf-8")
    (run_dir / "acquisition_summary.md").write_text(summary, encoding="utf-8")
    write_json(run_dir / "acquisition_metadata.json", metadata)
    coverage.to_csv(run_dir / "symbol_coverage_summary.csv", index=False)
    quality.to_csv(run_dir / "data_quality_summary.csv", index=False)
    cache_manifest.to_csv(run_dir / "cache_write_manifest.csv", index=False)
    (run_dir / "warnings_and_limitations.md").write_text(warnings, encoding="utf-8")
    write_json(run_dir / "acquisition_manifest.json", manifest)


def run_acquisition(
    repo_root: Path = REPO_ROOT,
    config_path: Path = CONFIG_PATH,
    downloader: Downloader | None = None,
    run_id: str | None = None,
) -> AcquisitionOutputs:
    config = load_config(config_path)
    symbols = validate_requested_symbols(config)
    request_settings = dict(config.get("request_settings", {}))
    cache_root = repo_root / str(config.get("cache", {}).get("target_root", "data/cache"))
    cache_root.mkdir(parents=True, exist_ok=True)
    run_id = run_id or utc_run_id()
    run_dir = EVIDENCE_ROOT / "runs" / run_id
    if run_dir.exists():
        shutil.rmtree(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    downloader = downloader or default_yfinance_downloader

    coverage_rows: list[dict[str, Any]] = []
    quality_rows: list[dict[str, Any]] = []
    cache_rows: list[dict[str, Any]] = []
    downloaded_symbols: list[str] = []
    cache_confirmed_symbols: list[str] = []
    provider_api_called = False

    for symbol in symbols:
        normalized: pd.DataFrame | None = None
        error = ""
        source_status = "cache_missing"
        cache_path = cache_root / f"{symbol}.csv"
        try:
            if cache_path.exists():
                normalized = read_existing_cache(cache_path, symbol)
                source_status = "cache_confirmed"
                cache_confirmed_symbols.append(symbol)
            else:
                provider_api_called = True
                raw = downloader(symbol, request_settings)
                normalized = normalize_download(raw, symbol)
                normalized.to_csv(cache_path, index=False)
                source_status = "downloaded_yfinance_compatible"
                downloaded_symbols.append(symbol)
        except Exception as exc:
            error = str(exc)
            normalized = None
            source_status = "failed"
        coverage, quality, cache = analyze_symbol(symbol, normalized, cache_path, source_status, error)
        coverage_rows.append(coverage)
        quality_rows.append(quality)
        cache_rows.append(cache)

    coverage_df = pd.DataFrame(coverage_rows)
    quality_df = pd.DataFrame(quality_rows)
    cache_df = pd.DataFrame(cache_rows)
    quality_counts = {status: int(quality_df["quality_status"].eq(status).sum()) for status in ["pass", "warning", "fail"]}
    timestamp = datetime.now(timezone.utc).isoformat()
    versions = package_versions()
    failed = quality_df[quality_df["quality_status"].astype(str).eq("fail")]["symbol"].astype(str).tolist()
    metadata = {
        "run_id": run_id,
        "timestamp": timestamp,
        "provider": config.get("provider"),
        "provider_id": "yfinance_compatible",
        "approved_symbols": symbols,
        "strategy_universe_symbols": list(STRATEGY_UNIVERSE_SYMBOLS),
        "request_settings": request_settings,
        "package_versions": versions,
        "python_version": platform.python_version(),
        "cache_target_root": str(cache_root.relative_to(repo_root)),
        "existing_cache_first": True,
        "raw_ohlcv_in_evidence": False,
        "broker_integration": False,
        "live_orders": False,
        "order_placement": False,
        "real_money_recommendation": False,
    }
    manifest = {
        "run_id": run_id,
        "timestamp": timestamp,
        "approved_symbols": list(APPROVED_SYMBOLS),
        "strategy_universe_symbols": list(STRATEGY_UNIVERSE_SYMBOLS),
        "cache_confirmed_symbols": cache_confirmed_symbols,
        "downloaded_symbols": downloaded_symbols,
        "failed_symbols": failed,
        "data_downloaded": bool(downloaded_symbols),
        "controlled_fast_exploratory_download": bool(downloaded_symbols),
        "yfinance_compatible_provider_call": provider_api_called,
        "provider_api_called": provider_api_called,
        "keyed_provider_used": False,
        "api_key_or_secret_written": False,
        "raw_ohlcv_included": False,
        "strategy_implemented": False,
        "backtest_run": False,
        "profit_exploration_run": False,
        "candidate_exhaustive_run": False,
        "paper_forward_rule_changed": False,
        "active_combo_rule_changed": False,
        "spy200d_replaced": False,
        "futures_contract_logic_added": False,
        "uses_leverage": False,
        "uses_margin": False,
        "uses_shorting": False,
        "uses_options": False,
        "uses_forex": False,
        "uses_intraday": False,
        "broker_integration": False,
        "live_orders": False,
        "order_placement": False,
        "real_money_recommendation": False,
        "quality_counts": quality_counts,
        "latest_folder_file_count": len(REQUIRED_FILES),
    }
    write_report_files(run_dir, run_id, config, metadata, coverage_df, quality_df, cache_df, manifest)
    files = sorted(path.name for path in run_dir.iterdir() if path.is_file())
    if sorted(files) != sorted(REQUIRED_FILES) or len(files) > 10:
        raise RuntimeError(f"Fast global multi-asset acquisition evidence contract failed: {files}")
    sync_latest_and_zip(run_dir, LATEST_DIR, LATEST_ZIP)
    return AcquisitionOutputs(run_id, run_dir, LATEST_DIR, LATEST_ZIP, coverage_df, quality_df, cache_df, manifest)


def main() -> int:
    parser = argparse.ArgumentParser(description="Acquire approved global multi-asset ETF/fund symbols for fast exploratory screening.")
    parser.add_argument("--config", type=Path, default=CONFIG_PATH)
    args = parser.parse_args()
    outputs = run_acquisition(config_path=args.config)
    print(f"run_id={outputs.run_id}")
    print(f"cache_confirmed_symbols={','.join(outputs.manifest['cache_confirmed_symbols'])}")
    print(f"downloaded_symbols={','.join(outputs.manifest['downloaded_symbols'])}")
    print(f"failed_symbols={','.join(outputs.manifest['failed_symbols'])}")
    print(f"latest_dir={outputs.latest_dir}")
    print(f"latest_file_count={outputs.manifest['latest_folder_file_count']}")
    print(f"zip_path={outputs.zip_path}")
    print(f"quality_counts={outputs.manifest['quality_counts']}")
    print("raw_ohlcv_in_evidence=false")
    print("strategy_implemented=false")
    print("backtest_run=false")
    print("profit_exploration_run=false")
    print("candidate_exhaustive_run=false")
    return 0 if not outputs.manifest["failed_symbols"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
