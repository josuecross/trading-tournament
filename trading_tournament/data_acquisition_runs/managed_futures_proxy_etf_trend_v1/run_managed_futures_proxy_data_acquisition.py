from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import platform
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path
from typing import Any, Callable
from zipfile import ZIP_DEFLATED, ZipFile

import pandas as pd
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.data import DataQualityError, _standardize_raw_columns, build_adjusted_ohlc


SUBJECT_ID = "managed_futures_proxy_etf_trend_v1"
APPROVED_SYMBOLS = ("DBMF", "KMLM")
EXCLUDED_SYMBOLS = ("CTA", "FMF", "WTMF")
EXCLUDED_REFRESH_SYMBOLS = ("SPY", "BIL")
CONFIG_PATH = Path(__file__).resolve().with_name("acquisition_config.yaml")
EVIDENCE_ROOT = REPO_ROOT / "evidence" / "data_acquisition_runs" / SUBJECT_ID
LATEST_DIR = EVIDENCE_ROOT / "latest"
LATEST_ZIP = EVIDENCE_ROOT / "latest_data_acquisition_packet.zip"


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
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def validate_requested_symbols(config: dict[str, Any], requested_symbols: list[str] | None = None) -> list[str]:
    allowed = [str(symbol).upper() for symbol in config.get("allowed_symbols", [])]
    excluded = {str(symbol).upper() for symbol in config.get("excluded_symbols", [])}
    excluded_refresh = {str(symbol).upper() for symbol in config.get("excluded_default_refresh_symbols", [])}
    allow_refresh = bool(config.get("allow_symbol_refresh", False))
    symbols = [str(symbol).upper() for symbol in (requested_symbols if requested_symbols is not None else allowed)]

    if allowed != list(APPROVED_SYMBOLS):
        raise ValueError(f"acquisition config allowed_symbols must be exactly {', '.join(APPROVED_SYMBOLS)}")
    if sorted(symbols) != sorted(allowed):
        raise ValueError(f"requested symbols must exactly match approved symbols: {', '.join(allowed)}")
    unapproved = sorted(set(symbols) - set(allowed))
    if unapproved:
        raise ValueError(f"unapproved symbols requested: {', '.join(unapproved)}")
    blocked = sorted(set(symbols) & excluded)
    if blocked:
        raise ValueError(f"excluded managed-futures symbols requested: {', '.join(blocked)}")
    refresh = sorted(set(symbols) & excluded_refresh)
    if refresh and not allow_refresh:
        raise ValueError(f"excluded refresh symbols requested without approval: {', '.join(refresh)}")
    return symbols


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
        "start": request_settings.get("start", "2007-01-01"),
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
        kwargs["timeout"] = float(request_settings.get("timeout", 20))
    try:
        return yf.download(symbol, **kwargs)
    except TypeError as exc:
        if "multi_level_index" not in str(exc):
            raise
        kwargs.pop("multi_level_index", None)
        return yf.download(symbol, **kwargs)


def normalized_date_series(frame: pd.DataFrame) -> pd.Series:
    return pd.to_datetime(frame["date"], errors="coerce").dt.tz_localize(None)


def cached_date_set(cache_root: Path, symbol: str) -> set[pd.Timestamp]:
    path = cache_root / f"{symbol}.csv"
    if not path.exists():
        return set()
    frame = pd.read_csv(path, usecols=["date"])
    return set(pd.to_datetime(frame["date"], errors="coerce").dropna().dt.tz_localize(None))


def analyze_symbol(
    symbol: str,
    raw: pd.DataFrame | None,
    normalized: pd.DataFrame | None,
    cache_path: Path,
    cache_root: Path,
    error: str = "",
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    downloaded = raw is not None and not raw.empty
    cache_written = cache_path.exists() and normalized is not None and not normalized.empty
    duplicate_date_count = 0
    missing_adj = missing_close = missing_volume = 0
    adjusted_close_available = raw_close_available = dividends_available = splits_available = False
    adjusted_constructible = normalized is not None and not normalized.empty and not error

    if raw is not None and not raw.empty:
        try:
            raw_standard = _standardize_raw_columns(raw, symbol)
            dates = normalized_date_series(raw_standard)
            duplicate_date_count = int(dates.duplicated().sum())
            missing_adj = int(raw_standard["raw_adj_close"].isna().sum())
            missing_close = int(raw_standard["raw_close"].isna().sum())
            missing_volume = int(raw_standard["raw_volume"].isna().sum())
            adjusted_close_available = "raw_adj_close" in raw_standard and missing_adj < len(raw_standard)
            raw_close_available = "raw_close" in raw_standard and missing_close < len(raw_standard)
            dividends_available = "dividends" in raw_standard
            splits_available = "stock_splits" in raw_standard
        except Exception:
            pass

    row_count = int(len(normalized)) if normalized is not None else 0
    first_date = str(normalized_date_series(normalized).min().date()) if normalized is not None and not normalized.empty else ""
    last_date = str(normalized_date_series(normalized).max().date()) if normalized is not None and not normalized.empty else ""
    enough_200 = row_count >= 200
    enough_126 = row_count >= 126
    enough_180 = row_count >= 380

    symbol_dates = set(normalized_date_series(normalized).dropna()) if normalized is not None and not normalized.empty else set()
    common = symbol_dates & cached_date_set(cache_root, "SPY") & cached_date_set(cache_root, "BIL")
    common_overlap = ""
    common_count = 0
    if common:
        common_overlap = f"{min(common).date()} to {max(common).date()}"
        common_count = len(common)

    if error or not downloaded or not cache_written or not adjusted_constructible or not enough_180 or missing_adj or missing_close or duplicate_date_count:
        quality_status = "fail"
    elif missing_volume:
        quality_status = "warning"
    else:
        quality_status = "pass"
    notes = error or ("pass; issuer/fund methodology review still required" if quality_status == "pass" else "warning: missing volume values; methodology review still required")

    coverage = {
        "symbol": symbol,
        "downloaded": downloaded,
        "cache_written": cache_written,
        "row_count": row_count,
        "first_date": first_date,
        "last_date": last_date,
        "common_overlap_with_cached_SPY_BIL": common_overlap,
        "common_overlap_row_count": common_count,
        "coverage_notes": notes,
    }
    quality = {
        "symbol": symbol,
        "downloaded": downloaded,
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
        "dividends_available": dividends_available,
        "splits_available": splits_available,
        "adjusted_ohlc_constructible": adjusted_constructible,
        "enough_rows_for_200d_sma": enough_200,
        "enough_rows_for_126d_momentum": enough_126,
        "enough_rows_for_180d_rolling_after_warmup": enough_180,
        "common_overlap_with_cached_SPY_BIL": common_overlap,
        "quality_status": quality_status,
        "quality_notes": notes,
    }
    if normalized is not None and not normalized.empty:
        dates = sorted(symbol_dates)
        gaps = [
            (dates[idx] - dates[idx - 1]).days
            for idx in range(1, len(dates))
            if (dates[idx] - dates[idx - 1]).days > 4
        ]
        max_gap = max(gaps) if gaps else 0
    else:
        max_gap = 0
    gap = {
        "symbol": symbol,
        "duplicate_date_count": duplicate_date_count,
        "missing_adjusted_close_count": missing_adj,
        "missing_close_count": missing_close,
        "missing_volume_count": missing_volume,
        "max_calendar_gap_days_gt_4": max_gap,
        "gap_notes": "calendar gaps over weekends/holidays are expected; max only flags long gaps",
    }
    adjustment = {
        "symbol": symbol,
        "adjusted_close_available": adjusted_close_available,
        "raw_close_available": raw_close_available,
        "dividends_available": dividends_available,
        "splits_available": splits_available,
        "adjusted_ohlc_constructible": adjusted_constructible,
        "adjustment_notes": "adjusted OHLC constructed from raw OHLC and adjusted close" if adjusted_constructible else notes,
    }
    cache = {
        "symbol": symbol,
        "cache_path": str(cache_path.relative_to(REPO_ROOT)) if cache_path.is_relative_to(REPO_ROOT) else str(cache_path),
        "rows_written": row_count if cache_written else 0,
        "sha256": sha256_file(cache_path) if cache_written else "",
        "write_status": "written" if cache_written else "failed",
    }
    return coverage, quality, gap, adjustment, cache


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def common_overlap_window(coverage: pd.DataFrame) -> tuple[str, str]:
    if coverage.empty or not coverage["first_date"].astype(str).ne("").all() or not coverage["last_date"].astype(str).ne("").all():
        return "", ""
    return str(pd.to_datetime(coverage["first_date"]).max().date()), str(pd.to_datetime(coverage["last_date"]).min().date())


def write_report_files(
    run_dir: Path,
    run_id: str,
    config: dict[str, Any],
    metadata: dict[str, Any],
    coverage: pd.DataFrame,
    quality: pd.DataFrame,
    gap: pd.DataFrame,
    adjustment: pd.DataFrame,
    cache_manifest: pd.DataFrame,
    manifest: dict[str, Any],
) -> None:
    pass_count = int(quality["quality_status"].eq("pass").sum()) if not quality.empty else 0
    warning_count = int(quality["quality_status"].eq("warning").sum()) if not quality.empty else 0
    fail_count = int(quality["quality_status"].eq("fail").sum()) if not quality.empty else 0
    downloaded = coverage[coverage["downloaded"].astype(bool)]["symbol"].astype(str).tolist() if not coverage.empty else []
    failed = quality[quality["quality_status"].astype(str).eq("fail")]["symbol"].astype(str).tolist() if not quality.empty else []
    common_start, common_end = common_overlap_window(coverage)

    readme = f"""# Managed-Futures Proxy Data Acquisition Packet

This is a data acquisition and quality packet only for `{SUBJECT_ID}`.

The yfinance-compatible provider call was allowed only for `DBMF` and `KMLM`. No keyed API provider was used. No API key or secret was written.

No strategy was implemented. No backtest was run. No Profit Exploration run was triggered. No futures contract logic was added. No paper-forward rule was changed. No broker integration, live orders, or real-money recommendation were added.

Raw OHLCV/cache data is excluded from this compact evidence packet and from advisor upload packets.
"""
    summary = f"""# Acquisition Summary

Run id: `{run_id}`

Provider used: `{config.get('provider')}`

Requested symbols: {', '.join(APPROVED_SYMBOLS)}

Symbols downloaded: {', '.join(downloaded) or 'none'}

Symbols failed: {', '.join(failed) or 'none'}

Quality counts: pass={pass_count}, warning={warning_count}, fail={fail_count}

Common overlap window across acquired symbols: {common_start or 'unavailable'} to {common_end or 'unavailable'}

Issuer/fund methodology review is still required. This acquisition does not prove the funds are good managed-futures proxies. Wrapper-level ETF/fund price modeling is not the same as direct futures strategy modeling.

Future strategy implementation may be reviewed only after data quality and methodology review are accepted. This packet does not implement or validate a strategy.

Future work must review fund name, issuer, inception date, expense ratio, methodology, internal futures exposure, risk target, collateral exposure, and whether evidence is fund-specific.

No real-money recommendation.
"""
    warnings = """# Warnings And Limitations

- yfinance/Yahoo data can have revisions, gaps, licensing/personal-use limits, ticker mapping issues, and adjustment differences.
- This data acquisition does not validate a strategy.
- Managed-futures proxy wrappers are not direct futures strategy tests.
- Issuer/fund methodology review remains required.
- Provider data quality must pass before implementation.
- Raw OHLCV/cache data is excluded from compact evidence and advisor upload packets.
- No strategy implementation, backtest, Profit Exploration run, futures contract logic, broker integration, live orders, or real-money recommendation is included.
"""
    (run_dir / "README_FOR_ADVISOR.md").write_text(readme, encoding="utf-8")
    (run_dir / "acquisition_summary.md").write_text(summary, encoding="utf-8")
    write_json(run_dir / "acquisition_metadata.json", metadata)
    coverage.to_csv(run_dir / "symbol_coverage_summary.csv", index=False)
    quality.to_csv(run_dir / "data_quality_summary.csv", index=False)
    gap.to_csv(run_dir / "data_gap_report.csv", index=False)
    adjustment.to_csv(run_dir / "adjustment_field_report.csv", index=False)
    cache_manifest.to_csv(run_dir / "cache_write_manifest.csv", index=False)
    (run_dir / "warnings_and_limitations.md").write_text(warnings, encoding="utf-8")
    write_json(run_dir / "acquisition_manifest.json", manifest)


def update_registry_status(repo_root: Path, status: str, next_action: str, summary: str) -> None:
    registry_path = repo_root / "strategy_lab" / "strategy_registry.yaml"
    data = yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
    for row in data.get("strategies", []):
        if row.get("id") == SUBJECT_ID:
            row["status"] = status
            row["implementation_status"] = "not_implemented"
            row["evidence_source"] = "managed_futures_proxy_data_acquisition"
            row["latest_evidence_path"] = "evidence/data_acquisition_runs/managed_futures_proxy_etf_trend_v1/latest/"
            row["latest_known_result_summary"] = summary
            row["allowed_next_action"] = next_action
            forbidden = list(row.get("forbidden_next_actions", []))
            for action in [
                "implement_strategy_without_methodology_review",
                "run_backtest_before_strategy_prompt",
                "observe_as_paper_forward",
                "promote_to_real_money",
                "add_broker_integration",
                "add_futures_contract_logic_without_review",
                "skip_data_gate",
            ]:
                if action not in forbidden:
                    forbidden.append(action)
            row["forbidden_next_actions"] = forbidden
            row["paper_forward_active"] = False
            row["paper_forward_allowed_by_risk_framework"] = False
            row["real_money_recommendation"] = False
            row["promotion_blockers"] = "strategy_not_implemented;methodology_review_required;not_paper_forward_allowed"
            row["promotion_requirements"] = "Issuer/fund methodology review, updated implementation review, fixed rule prompt, research_sample evidence, and separate promotion review."
            break
    registry_path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=False), encoding="utf-8")


def update_data_acquisition_review(repo_root: Path, run_id: str, status: str, quality_counts: dict[str, int]) -> None:
    review_path = repo_root / "data_acquisition_reviews" / SUBJECT_ID / "data_acquisition_manifest.json"
    if not review_path.exists():
        return
    manifest = json.loads(review_path.read_text(encoding="utf-8"))
    manifest["latest_acquisition_run_id"] = run_id
    manifest["latest_acquisition_status"] = status
    manifest["latest_quality_counts"] = quality_counts
    manifest["data_downloaded"] = True
    manifest["api_called"] = True
    manifest["yfinance_compatible_provider_call"] = True
    manifest["keyed_provider_used"] = False
    manifest["raw_ohlcv_included"] = False
    review_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    latest_manifest = repo_root / "evidence" / "data_acquisition_reviews" / SUBJECT_ID / "latest" / "data_acquisition_manifest.json"
    if latest_manifest.exists():
        latest_manifest.write_text(review_path.read_text(encoding="utf-8"), encoding="utf-8")


def update_implementation_decision(repo_root: Path, run_id: str, status: str) -> None:
    decision_path = repo_root / "implementation_reviews" / SUBJECT_ID / "IMPLEMENTATION_DECISION.md"
    if not decision_path.exists():
        return
    text = decision_path.read_text(encoding="utf-8")
    note = (
        f"\n\n## Data Acquisition Update\n\n"
        f"Controlled DBMF/KMLM data acquisition run `{run_id}` completed with status `{status}`. "
        "This update does not approve implementation. Issuer/fund methodology review remains required before any research_sample strategy prompt.\n"
    )
    if "## Data Acquisition Update" not in text:
        decision_path.write_text(text.rstrip() + note, encoding="utf-8")


def sync_latest_and_zip(run_dir: Path, latest_dir: Path, zip_path: Path) -> None:
    latest_dir.mkdir(parents=True, exist_ok=True)
    for existing in latest_dir.iterdir():
        if existing.is_file():
            existing.unlink()
    for path in sorted(run_dir.iterdir()):
        if path.is_file():
            shutil.copy2(path, latest_dir / path.name)
    if zip_path.exists():
        zip_path.unlink()
    with ZipFile(zip_path, "w", compression=ZIP_DEFLATED) as archive:
        for path in sorted(latest_dir.iterdir()):
            if path.is_file():
                archive.write(path, path.name)


def run_acquisition(
    repo_root: Path = REPO_ROOT,
    config_path: Path = CONFIG_PATH,
    downloader: Downloader | None = None,
    run_id: str | None = None,
    update_registry: bool = True,
) -> AcquisitionOutputs:
    config = load_config(config_path)
    symbols = validate_requested_symbols(config)
    request_settings = dict(config.get("request_settings", {}))
    cache_root = repo_root / str(config.get("cache", {}).get("target_root", "data/cache"))
    cache_root.mkdir(parents=True, exist_ok=True)
    run_id = run_id or utc_run_id()
    evidence_root = repo_root / "evidence" / "data_acquisition_runs" / SUBJECT_ID
    run_dir = evidence_root / "runs" / run_id
    latest_dir = evidence_root / "latest"
    zip_path = evidence_root / "latest_data_acquisition_packet.zip"
    run_dir.mkdir(parents=True, exist_ok=True)
    downloader = downloader or default_yfinance_downloader

    coverage_rows: list[dict[str, Any]] = []
    quality_rows: list[dict[str, Any]] = []
    gap_rows: list[dict[str, Any]] = []
    adjustment_rows: list[dict[str, Any]] = []
    cache_rows: list[dict[str, Any]] = []
    for symbol in symbols:
        raw: pd.DataFrame | None = None
        normalized: pd.DataFrame | None = None
        error = ""
        cache_path = cache_root / f"{symbol}.csv"
        try:
            raw = downloader(symbol, request_settings)
            if raw is None or raw.empty:
                raise DataQualityError(f"{symbol}: provider returned no rows")
            normalized = build_adjusted_ohlc(raw, symbol)
            normalized.to_csv(cache_path, index=False)
        except Exception as exc:
            error = str(exc)
        coverage, quality, gap, adjustment, cache = analyze_symbol(symbol, raw, normalized, cache_path, cache_root, error)
        coverage_rows.append(coverage)
        quality_rows.append(quality)
        gap_rows.append(gap)
        adjustment_rows.append(adjustment)
        cache_rows.append(cache)

    coverage_df = pd.DataFrame(coverage_rows)
    quality_df = pd.DataFrame(quality_rows)
    gap_df = pd.DataFrame(gap_rows)
    adjustment_df = pd.DataFrame(adjustment_rows)
    cache_df = pd.DataFrame(cache_rows)
    quality_counts = {status: int(quality_df["quality_status"].eq(status).sum()) for status in ["pass", "warning", "fail"]}

    if quality_counts["fail"] == 0 and quality_counts["warning"] == 0:
        strategy_status = "data_quality_review_passed_methodology_review_required"
        next_action = "issuer_methodology_review"
    elif quality_counts["fail"] == 0:
        strategy_status = "data_acquired_pending_methodology_review"
        next_action = "issuer_methodology_review"
    elif bool(quality_df["quality_status"].eq("pass").any()):
        strategy_status = "partial_data_acquired_quality_review_required"
        next_action = "data_quality_followup"
    else:
        strategy_status = "data_acquisition_failed"
        next_action = "provider_fallback_review"

    timestamp = datetime.now(timezone.utc).isoformat()
    versions = package_versions()
    metadata = {
        "run_id": run_id,
        "timestamp": timestamp,
        "provider": config.get("provider"),
        "provider_id": "yfinance_compatible",
        "request_settings": request_settings,
        "package_versions": versions,
        "yfinance_version": versions.get("yfinance", "not_installed"),
        "python_version": platform.python_version(),
        "symbols": symbols,
        "cache_target_root": str(cache_root.relative_to(repo_root) if cache_root.is_relative_to(repo_root) else cache_root),
        "broker_integration": False,
        "live_orders": False,
        "futures_contract_logic_added": False,
        "real_money_recommendation": False,
    }
    manifest = {
        "run_id": run_id,
        "timestamp": timestamp,
        "data_downloaded": bool(coverage_df["downloaded"].any()),
        "yfinance_compatible_provider_call": True,
        "keyed_provider_used": False,
        "api_key_or_secret_written": False,
        "raw_ohlcv_included": False,
        "strategy_implemented": False,
        "backtest_run": False,
        "profit_exploration_run": False,
        "futures_contract_logic_added": False,
        "paper_forward_rule_changed": False,
        "broker_integration": False,
        "live_orders": False,
        "real_money_recommendation": False,
        "latest_folder_file_count": 10,
        "strategy_lab_status": strategy_status,
        "quality_counts": quality_counts,
    }
    write_report_files(run_dir, run_id, config, metadata, coverage_df, quality_df, gap_df, adjustment_df, cache_df, manifest)
    sync_latest_and_zip(run_dir, latest_dir, zip_path)
    if update_registry:
        summary = (
            f"Managed-futures proxy DBMF/KMLM data acquisition run {run_id}; quality counts "
            f"pass={quality_counts['pass']}, warning={quality_counts['warning']}, fail={quality_counts['fail']}; "
            "issuer/fund methodology review remains required and strategy remains not implemented."
        )
        update_registry_status(repo_root, strategy_status, next_action, summary)
        update_data_acquisition_review(repo_root, run_id, strategy_status, quality_counts)
        update_implementation_decision(repo_root, run_id, strategy_status)
    return AcquisitionOutputs(run_id, run_dir, latest_dir, zip_path, coverage_df, quality_df, cache_df, manifest)


def main() -> int:
    parser = argparse.ArgumentParser(description="Acquire approved managed-futures proxy ETF/fund data only.")
    parser.add_argument("--config", type=Path, default=CONFIG_PATH)
    args = parser.parse_args()
    outputs = run_acquisition(config_path=args.config)
    downloaded = outputs.coverage[outputs.coverage["downloaded"].astype(bool)]["symbol"].astype(str).tolist()
    failed = outputs.quality[outputs.quality["quality_status"].astype(str).eq("fail")]["symbol"].astype(str).tolist()
    print(f"run_id={outputs.run_id}")
    print(f"downloaded_symbols={','.join(downloaded)}")
    print(f"failed_symbols={','.join(failed)}")
    print(f"latest_dir={outputs.latest_dir}")
    print(f"latest_file_count={outputs.manifest['latest_folder_file_count']}")
    print(f"zip_path={outputs.zip_path}")
    print(f"strategy_lab_status={outputs.manifest['strategy_lab_status']}")
    print(f"quality_counts={outputs.manifest['quality_counts']}")
    print("strategy_implemented=false")
    print("backtest_run=false")
    print("profit_exploration_run=false")
    print("futures_contract_logic_added=false")
    return 0 if not failed else 2


if __name__ == "__main__":
    raise SystemExit(main())

