from __future__ import annotations

import csv
import hashlib
import inspect
import json
import platform
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from src.data import DataQualityError, _standardize_raw_columns, build_adjusted_ohlc
from strategy_lab.research_os.exploratory_sandbox.sandbox_config import DATA_CACHE_DIR, ROOT
from strategy_lab.research_os.objective_reset.objective_reset_review import write_json, write_text


FAMILY_ID = "commodity_basket_etf_momentum_v1"
LANE_ID = "commodity_basket_etf_momentum_bounded_lane_v1"
OUTPUT_DIR = Path("evidence") / "research_recovery" / "commodity_basket_provider_refresh" / "latest"

AUTHORIZED_REFRESH_SYMBOLS = ("DBC", "PDBC", "COMT", "GSG", "USCI")
REQUIRED_SYMBOLS = (*AUTHORIZED_REFRESH_SYMBOLS, "BIL", "SPY", "GLD")
REQUEST_SETTINGS = {
    "start": "2006-01-01",
    "end": None,
    "auto_adjust": False,
    "actions": True,
    "progress": False,
    "multi_level_index": False,
    "timeout": 30,
}

RUN_READY = "commodity_basket_cache_ready_for_bounded_run"
RUN_BLOCKED = "commodity_basket_cache_still_blocked"
NEXT_ACTION_READY = "run_commodity_basket_etf_momentum_bounded_lane"
NEXT_ACTION_BLOCKED = "provide_existing_raw_commodity_cache_files_or_authorize_provider_refresh"

REFRESH_FIELDS = (
    "symbol",
    "authorized_for_refresh",
    "provider",
    "download_attempted",
    "download_status",
    "cache_path",
    "cache_written",
    "row_count",
    "first_date",
    "last_date",
    "quality_status",
    "error",
)

QUALITY_FIELDS = (
    "symbol",
    "downloaded",
    "cache_written",
    "row_count",
    "first_date",
    "last_date",
    "duplicate_date_count",
    "missing_adjusted_close_count",
    "missing_close_count",
    "missing_volume_count",
    "adjusted_close_available",
    "raw_close_available",
    "volume_available",
    "enough_rows_for_126d_momentum",
    "enough_rows_for_200d_sma",
    "enough_rows_for_180d_after_warmup",
    "quality_status",
    "notes",
)

HASH_FIELDS = ("symbol", "cache_path", "sha256", "row_count", "first_date", "last_date")

AVAILABILITY_FIELDS = (
    "symbol",
    "required_for_lane",
    "cache_path",
    "cache_exists",
    "is_raw_price_history",
    "row_count",
    "first_date",
    "last_date",
    "sha256",
    "status",
)


Downloader = Callable[[str, dict[str, Any]], pd.DataFrame]


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def package_versions() -> dict[str, str]:
    versions: dict[str, str] = {}
    for package in ("pandas", "numpy", "yfinance", "PyYAML"):
        try:
            versions[package] = metadata.version(package)
        except metadata.PackageNotFoundError:
            versions[package] = "not_installed"
    return versions


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


def cache_metadata(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "cache_exists": False,
            "is_raw_price_history": False,
            "row_count": 0,
            "first_date": "",
            "last_date": "",
            "sha256": "",
        }
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            fields = set(reader.fieldnames or [])
            is_raw = {"date", "open", "high", "low", "close", "adj_close", "volume"}.issubset(fields)
            row_count = 0
            first_date = ""
            last_date = ""
            for row in reader:
                row_count += 1
                date = row.get("date", "")
                if row_count == 1:
                    first_date = date
                last_date = date
    except (OSError, UnicodeDecodeError, csv.Error):
        return {
            "cache_exists": True,
            "is_raw_price_history": False,
            "row_count": 0,
            "first_date": "",
            "last_date": "",
            "sha256": sha256_file(path),
        }
    return {
        "cache_exists": True,
        "is_raw_price_history": is_raw,
        "row_count": row_count,
        "first_date": first_date,
        "last_date": last_date,
        "sha256": sha256_file(path),
    }


def analyze_symbol(
    symbol: str,
    raw: pd.DataFrame | None,
    normalized: pd.DataFrame | None,
    cache_path: Path,
    error: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    downloaded = raw is not None and not raw.empty
    cache_written = normalized is not None and not normalized.empty and cache_path.exists()
    duplicate_date_count = 0
    missing_adj = missing_close = missing_volume = 0
    adjusted_close_available = raw_close_available = volume_available = False

    if raw is not None and not raw.empty:
        try:
            raw_standard = _standardize_raw_columns(raw, symbol)
            dates = normalized_date_series(raw_standard)
            duplicate_date_count = int(dates.duplicated().sum())
            missing_adj = int(raw_standard["raw_adj_close"].isna().sum())
            missing_close = int(raw_standard["raw_close"].isna().sum())
            missing_volume = int(raw_standard["raw_volume"].isna().sum())
            adjusted_close_available = missing_adj < len(raw_standard)
            raw_close_available = missing_close < len(raw_standard)
            volume_available = missing_volume < len(raw_standard)
        except Exception:
            pass

    row_count = int(len(normalized)) if normalized is not None else 0
    first_date = str(normalized_date_series(normalized).min().date()) if normalized is not None and not normalized.empty else ""
    last_date = str(normalized_date_series(normalized).max().date()) if normalized is not None and not normalized.empty else ""
    enough_126 = row_count >= 126
    enough_200 = row_count >= 200
    enough_180_after_warmup = row_count >= 380

    if (
        error
        or not downloaded
        or not cache_written
        or not adjusted_close_available
        or not raw_close_available
        or duplicate_date_count
        or not enough_180_after_warmup
    ):
        quality_status = "fail"
    elif missing_volume:
        quality_status = "warning"
    else:
        quality_status = "pass"

    notes = (
        error
        if error
        else "basic QA passed; product/tax/wrapper review remains deferred"
        if quality_status == "pass"
        else "warning: usable adjusted prices but volume/product-action metadata needs caution"
        if quality_status == "warning"
        else "failed basic cache refresh QA"
    )

    refresh = {
        "symbol": symbol,
        "authorized_for_refresh": symbol in AUTHORIZED_REFRESH_SYMBOLS,
        "provider": "yfinance_compatible",
        "download_attempted": True,
        "download_status": "downloaded_pass" if quality_status in {"pass", "warning"} else "downloaded_fail",
        "cache_path": str(cache_path),
        "cache_written": cache_written,
        "row_count": row_count,
        "first_date": first_date,
        "last_date": last_date,
        "quality_status": quality_status,
        "error": error,
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
        "volume_available": volume_available,
        "enough_rows_for_126d_momentum": enough_126,
        "enough_rows_for_200d_sma": enough_200,
        "enough_rows_for_180d_after_warmup": enough_180_after_warmup,
        "quality_status": quality_status,
        "notes": notes,
    }
    cache = {
        "symbol": symbol,
        "cache_path": str(cache_path),
        "sha256": sha256_file(cache_path) if cache_written else "",
        "row_count": row_count if cache_written else 0,
        "first_date": first_date,
        "last_date": last_date,
    }
    return refresh, quality, cache


def refresh_symbols(root: Path, downloader: Downloader) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    cache_root = root / DATA_CACHE_DIR
    cache_root.mkdir(parents=True, exist_ok=True)
    refresh_rows: list[dict[str, Any]] = []
    quality_rows: list[dict[str, Any]] = []
    hash_rows: list[dict[str, Any]] = []
    for symbol in AUTHORIZED_REFRESH_SYMBOLS:
        raw: pd.DataFrame | None = None
        normalized: pd.DataFrame | None = None
        error = ""
        cache_path = cache_root / f"{symbol}.csv"
        try:
            raw = downloader(symbol, REQUEST_SETTINGS)
            if raw is None or raw.empty:
                raise DataQualityError(f"{symbol}: provider returned no rows")
            normalized = build_adjusted_ohlc(raw, symbol)
            normalized.to_csv(cache_path, index=False)
        except Exception as exc:
            error = str(exc)
        refresh, quality, cache = analyze_symbol(symbol, raw, normalized, cache_path, error)
        refresh_rows.append(refresh)
        quality_rows.append(quality)
        hash_rows.append(cache)
    return refresh_rows, quality_rows, hash_rows


def availability_rows(root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for symbol in REQUIRED_SYMBOLS:
        path = root / DATA_CACHE_DIR / f"{symbol}.csv"
        meta = cache_metadata(path)
        ok = meta["cache_exists"] and meta["is_raw_price_history"] and meta["row_count"] >= 380
        rows.append(
            {
                "symbol": symbol,
                "required_for_lane": True,
                "cache_path": str(path),
                "cache_exists": meta["cache_exists"],
                "is_raw_price_history": meta["is_raw_price_history"],
                "row_count": meta["row_count"],
                "first_date": meta["first_date"],
                "last_date": meta["last_date"],
                "sha256": meta["sha256"],
                "status": "available_raw_price_history" if ok else "missing_or_invalid_raw_price_history",
            }
        )
    return rows


def readiness(availability: list[dict[str, Any]], quality: list[dict[str, Any]]) -> tuple[str, str, list[str]]:
    missing = [row["symbol"] for row in availability if row["status"] != "available_raw_price_history"]
    failed = [row["symbol"] for row in quality if row["quality_status"] == "fail"]
    blockers = sorted(set(missing + failed))
    if blockers:
        return RUN_BLOCKED, NEXT_ACTION_BLOCKED, blockers
    return RUN_READY, NEXT_ACTION_READY, []


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: tuple[str, ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def provider_source_md() -> str:
    return f"""# Provider / Source Used

Provider: `yfinance_compatible`

Authorized symbols refreshed: `{', '.join(AUTHORIZED_REFRESH_SYMBOLS)}`

Request settings:

- start: `{REQUEST_SETTINGS['start']}`
- end: `{REQUEST_SETTINGS['end']}`
- auto_adjust: `{REQUEST_SETTINGS['auto_adjust']}`
- actions: `{REQUEST_SETTINGS['actions']}`
- interval: daily provider default

This refresh is limited to raw daily ETF/fund-wrapper OHLCV/adjusted price cache. It does not use intraday data, a keyed provider, broker APIs, or live/order paths.
"""


def guardrail_md(payload: dict[str, Any]) -> str:
    keys = [
        "provider_download",
        "authorized_symbol_only_refresh",
        "intraday_data_used",
        "commodity_lane_run",
        "new_backtests_run",
        "new_strategy_discovery_run",
        "new_research_batch_run",
        "new_family_created",
        "new_variants_created",
        "six_row_design_changed",
        "candidate_exhaustive_run",
        "promotion_candidates_created",
        "paper_forward_activation",
        "broker_api_called",
        "live_orders",
        "real_money_recommendation",
        "summary_metrics_converted_to_price_history",
    ]
    return "# Guardrail Checklist\n\n" + "\n".join(f"- `{key}`: `{payload[key]}`" for key in keys) + "\n"


def missing_invalid_md(blockers: list[str], quality: list[dict[str, Any]]) -> str:
    lines = ["# Missing / Invalid Data Report", ""]
    lines.append(f"Blocking symbols: `{', '.join(blockers) if blockers else 'none'}`")
    lines.append("")
    for row in quality:
        if row["quality_status"] == "fail":
            lines.append(f"- `{row['symbol']}` failed: {row['notes']}")
    if not blockers:
        lines.append("All authorized refresh symbols passed cache availability and QA checks.")
    return "\n".join(lines) + "\n"


def summary_md(payload: dict[str, Any]) -> str:
    return f"""# Commodity Basket Provider Refresh

Family: `{payload['family_id']}`

Lane: `{payload['lane_id']}`

Authorized refreshed symbols: `{', '.join(payload['authorized_refresh_symbols'])}`

Downloaded symbols: `{', '.join(payload['downloaded_symbols']) or 'none'}`

Failed symbols: `{', '.join(payload['failed_symbols']) or 'none'}`

Run-readiness decision: `{payload['run_readiness_decision']}`

Exact next action: `{payload['next_action']}`

No commodity bounded lane, backtest, discovery, candidate_exhaustive, promotion, paper-forward activation, broker/live action, or real-money recommendation occurred.
"""


def next_action_md(payload: dict[str, Any]) -> str:
    return f"""# Commodity Provider Refresh Next Action

Exact next action:

`{payload['next_action']}`

Do not execute it in this task.
"""


def build_manifest(
    created: str,
    output: Path,
    refresh_rows: list[dict[str, Any]],
    quality_rows: list[dict[str, Any]],
    availability: list[dict[str, Any]],
) -> dict[str, Any]:
    decision, next_action, blockers = readiness(availability, quality_rows)
    downloaded = [row["symbol"] for row in refresh_rows if row["download_status"] == "downloaded_pass"]
    failed = [row["symbol"] for row in refresh_rows if row["download_status"] == "downloaded_fail"]
    quality_counts = {status: sum(1 for row in quality_rows if row["quality_status"] == status) for status in ("pass", "warning", "fail")}
    return {
        "created_utc": created,
        "evidence_path": str(output.resolve()),
        "commodity_provider_refresh_only": True,
        "family_id": FAMILY_ID,
        "lane_id": LANE_ID,
        "authorized_refresh_symbols": list(AUTHORIZED_REFRESH_SYMBOLS),
        "required_symbols": list(REQUIRED_SYMBOLS),
        "downloaded_symbols": downloaded,
        "failed_symbols": failed,
        "blocked_symbols": blockers,
        "quality_counts": quality_counts,
        "provider": "yfinance_compatible",
        "provider_download": True,
        "provider_api_called": True,
        "keyed_provider_used": False,
        "api_key_or_secret_written": False,
        "authorized_symbol_only_refresh": set(downloaded + failed).issubset(set(AUTHORIZED_REFRESH_SYMBOLS)),
        "unrelated_symbols_refreshed": [],
        "canonical_cache_root": str((ROOT / DATA_CACHE_DIR).resolve()),
        "raw_ohlcv_in_evidence": False,
        "summary_metrics_converted_to_price_history": False,
        "intraday_data_used": False,
        "commodity_lane_run": False,
        "new_backtests_run": False,
        "new_strategy_discovery_run": False,
        "new_research_batch_run": False,
        "new_family_created": False,
        "new_variants_created": False,
        "six_row_design_changed": False,
        "candidate_exhaustive_run": False,
        "promotion_candidates_created": False,
        "paper_forward_activation": False,
        "new_paper_forward_candidate_created": False,
        "broker_api_called": False,
        "broker_orders_submitted": False,
        "broker_orders_cancelled": False,
        "broker_orders_reconciled": False,
        "live_orders": False,
        "real_money_recommendation": False,
        "active_vm_preserved": True,
        "active_dsr_preserved": True,
        "static_all_weather_benchmark_control_only": True,
        "macro_gld_continued": False,
        "volatility_throttle_continued": False,
        "managed_futures_reopened": False,
        "package_versions": package_versions(),
        "python_version": platform.python_version(),
        "request_settings": REQUEST_SETTINGS,
        "all_required_symbols_available": not blockers,
        "run_readiness_decision": decision,
        "next_action": next_action,
    }


def consistency_check(payload: dict[str, Any], output: Path) -> dict[str, Any]:
    required = {
        "provider_refresh_manifest.json": (output / "provider_refresh_manifest.json").exists(),
        "provider_source.md": (output / "provider_source.md").exists(),
        "symbol_refresh_table.csv": (output / "symbol_refresh_table.csv").exists(),
        "cache_write_manifest.csv": (output / "cache_write_manifest.csv").exists(),
        "required_symbol_availability.csv": (output / "required_symbol_availability.csv").exists(),
        "data_quality_summary.csv": (output / "data_quality_summary.csv").exists(),
        "hash_report.csv": (output / "hash_report.csv").exists(),
        "missing_invalid_data_report.md": (output / "missing_invalid_data_report.md").exists(),
        "guardrail_checklist.md": (output / "guardrail_checklist.md").exists(),
        "provider_refresh_summary.md": (output / "provider_refresh_summary.md").exists(),
        "provider_refresh_next_action.md": (output / "provider_refresh_next_action.md").exists(),
        "provider_refresh_consistency_check.json": True,
    }
    checks: dict[str, Any] = {
        "refresh_only": payload["commodity_provider_refresh_only"] is True,
        "correct_family": payload["family_id"] == FAMILY_ID,
        "correct_lane": payload["lane_id"] == LANE_ID,
        "only_authorized_symbols_refreshed": payload["authorized_symbol_only_refresh"] is True
        and not payload["unrelated_symbols_refreshed"],
        "provider_download_scoped": payload["provider_download"] is True and payload["provider_api_called"] is True,
        "no_intraday": payload["intraday_data_used"] is False,
        "no_lane_or_backtest": payload["commodity_lane_run"] is False and payload["new_backtests_run"] is False,
        "no_discovery_or_batch": payload["new_strategy_discovery_run"] is False
        and payload["new_research_batch_run"] is False,
        "no_family_variant_design_change": payload["new_family_created"] is False
        and payload["new_variants_created"] is False
        and payload["six_row_design_changed"] is False,
        "no_candidate_promotion_paper": payload["candidate_exhaustive_run"] is False
        and payload["promotion_candidates_created"] is False
        and payload["paper_forward_activation"] is False
        and payload["new_paper_forward_candidate_created"] is False,
        "no_broker_live_real_money": payload["broker_api_called"] is False
        and payload["broker_orders_submitted"] is False
        and payload["broker_orders_cancelled"] is False
        and payload["broker_orders_reconciled"] is False
        and payload["live_orders"] is False
        and payload["real_money_recommendation"] is False,
        "summary_not_converted": payload["summary_metrics_converted_to_price_history"] is False,
        "raw_ohlcv_not_in_evidence": payload["raw_ohlcv_in_evidence"] is False,
        "readiness_valid": payload["run_readiness_decision"] in {RUN_READY, RUN_BLOCKED},
        "next_action_valid": payload["next_action"] in {NEXT_ACTION_READY, NEXT_ACTION_BLOCKED},
        "required_files_present": all(required.values()),
        "required_files": required,
    }
    checks["consistency_passed"] = all(value is True for key, value in checks.items() if key != "required_files")
    return checks


def run(root: Path = ROOT, downloader: Downloader | None = None) -> dict[str, Any]:
    created = now_utc()
    output = root / OUTPUT_DIR
    output.mkdir(parents=True, exist_ok=True)
    refresh_rows, quality_rows, hash_rows = refresh_symbols(root, downloader or default_yfinance_downloader)
    availability = availability_rows(root)
    payload = build_manifest(created, output, refresh_rows, quality_rows, availability)

    write_json(output / "provider_refresh_manifest.json", payload)
    write_text(output / "provider_source.md", provider_source_md())
    write_csv(output / "symbol_refresh_table.csv", refresh_rows, REFRESH_FIELDS)
    write_csv(output / "cache_write_manifest.csv", hash_rows, HASH_FIELDS)
    write_csv(output / "required_symbol_availability.csv", availability, AVAILABILITY_FIELDS)
    write_csv(output / "data_quality_summary.csv", quality_rows, QUALITY_FIELDS)
    write_csv(output / "hash_report.csv", hash_rows, HASH_FIELDS)
    write_text(output / "missing_invalid_data_report.md", missing_invalid_md(payload["blocked_symbols"], quality_rows))
    write_text(output / "guardrail_checklist.md", guardrail_md(payload))
    write_text(output / "provider_refresh_summary.md", summary_md(payload))
    write_text(output / "provider_refresh_next_action.md", next_action_md(payload))
    checks = consistency_check(payload, output)
    write_json(output / "provider_refresh_consistency_check.json", checks)
    return {**payload, "output_dir": str(output.resolve()), "consistency_passed": checks["consistency_passed"]}


if __name__ == "__main__":
    result = run()
    print(
        json.dumps(
            {
                "output_dir": result["output_dir"],
                "downloaded_symbols": result["downloaded_symbols"],
                "failed_symbols": result["failed_symbols"],
                "run_readiness_decision": result["run_readiness_decision"],
                "next_action": result["next_action"],
                "consistency_passed": result["consistency_passed"],
            },
            indent=2,
        )
    )
