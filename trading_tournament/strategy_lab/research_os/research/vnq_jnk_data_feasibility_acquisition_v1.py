from __future__ import annotations

import csv
import hashlib
import json
import math
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import yaml
import numpy as np

from execution_lab.alpaca_micro_live_v1.adapters.alpaca_client import AlpacaClient, AlpacaClientConfig
from execution_lab.alpaca_micro_live_v1.adapters.credentials import load_alpaca_credentials
from execution_lab.alpaca_micro_live_v1.data.alpaca_historical_bars import parse_bars_response
from src.data import build_adjusted_ohlc
from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.research import fast_price_volume_discovery_batch_v2 as prior
from strategy_lab.research_os.research import fast_source_library_batch_v3 as source_batch


TASK_ID = "vnq_jnk_data_feasibility_acquisition_v1"
OUTPUT_DIR = ROOT / "evidence" / "data_capability" / TASK_ID / "latest"
SOURCE_LIBRARY_ID = "strategy_source_library_refresh_v1"
FROZEN_TIMESTAMP = "2026-07-23T00:00:00+00:00"
REQUIRED_THROUGH_DATE = pd.Timestamp("2026-06-18")
DOWNLOAD_END_EXCLUSIVE = "2026-06-19"
DOWNLOAD_START = "2003-01-01"
TARGET_SYMBOLS = ("VNQ", "JNK")
DATA_CACHE_DIR = ROOT / "data" / "cache"
REQUIRED_CACHE_COLUMNS = (
    "date",
    "raw_open",
    "raw_high",
    "raw_low",
    "raw_close",
    "raw_adj_close",
    "raw_volume",
    "dividends",
    "stock_splits",
    "adjustment_factor",
    "open",
    "high",
    "low",
    "close",
    "adj_close",
    "volume",
    "symbol",
)
ADJUSTED_OHLCV_COLUMNS = ("open", "high", "low", "close", "adj_close", "volume")
PROTECTED_STATE_PATHS = [
    ROOT / "strategy_lab" / "strategy_registry.yaml",
    ROOT / "strategy_lab" / "RESEARCH_ROADMAP.md",
    ROOT / "strategy_lab" / "research_os" / "research" / "research_queue.yaml",
    ROOT / "strategy_lab" / "research_os" / "family_lineage" / "family_ledger.yaml",
    ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml",
]
INPUT_EVIDENCE_DIRS = [
    ROOT / "evidence" / "tournament_status" / "tournament_strategy_readiness_inventory_v1" / "latest",
    ROOT / "evidence" / "research_recovery" / "fast_price_volume_discovery_batch_v2" / "latest",
    ROOT / "evidence" / "research_recovery" / "fast_price_volume_candidate_incremental_value_followup_v1" / "latest",
    ROOT / "evidence" / "research_recovery" / "fast_source_library_batch_v3" / "latest",
]
PROVIDER_ATTEMPT_LABEL = "alpaca_market_data_then_existing_yfinance_adjusted_daily_fallback"
FORBIDDEN_FLAGS = {
    "strategy_backtest_run": False,
    "strategy_performance_metrics_calculated": False,
    "benchmark_metrics_calculated": False,
    "control_calculation_run": False,
    "strategy_rules_changed": False,
    "strategy_registry_modified": False,
    "roadmap_modified": False,
    "research_queue_modified": False,
    "family_ledger_modified": False,
    "active_observations_modified": False,
    "broker_account_endpoint_called": False,
    "broker_order_endpoint_called": False,
    "broker_order_submitted": False,
    "paper_demo_activation": False,
    "promotion_review": False,
    "parameter_search": False,
    "instrument_substitution": False,
    "new_data_infrastructure": False,
}


def rel(path: str | Path) -> str:
    p = Path(path)
    if not p.is_absolute():
        return p.as_posix()
    try:
        return p.relative_to(ROOT).as_posix()
    except ValueError:
        return p.as_posix()


def csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        if not math.isfinite(value):
            return ""
        return f"{value:.12g}"
    if isinstance(value, (list, tuple, set)):
        return "|".join(str(v) for v in value)
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    return str(value)


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: csv_value(row.get(field, "")) for field in fieldnames})


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False, width=120, allow_unicode=False), encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def file_hash(path: Path) -> str:
    if not path.exists():
        return "missing"
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def dataframe_hash(frame: pd.DataFrame) -> str:
    normalized = frame.copy()
    if "date" in normalized.columns:
        normalized["date"] = pd.to_datetime(normalized["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    normalized = normalized.sort_values("date") if "date" in normalized.columns else normalized
    payload = normalized.to_csv(index=False, lineterminator="\n")
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def protected_hashes() -> dict[str, str]:
    return {rel(path): file_hash(path) for path in PROTECTED_STATE_PATHS if path.exists()}


def prior_evidence_files() -> list[Path]:
    files: list[Path] = []
    for folder in INPUT_EVIDENCE_DIRS:
        if folder.exists():
            files.extend(path for path in sorted(folder.glob("*")) if path.is_file())
    return files


def prior_evidence_hashes() -> dict[str, str]:
    return {rel(path): file_hash(path) for path in prior_evidence_files()}


def cache_guard_hashes() -> dict[str, str]:
    guarded: dict[str, str] = {}
    if not DATA_CACHE_DIR.exists():
        return guarded
    for path in sorted(DATA_CACHE_DIR.glob("*")):
        if path.name.upper().startswith(("VNQ", "JNK")):
            continue
        if path.is_file():
            guarded[rel(path)] = file_hash(path)
    return guarded


def read_previous_task_source_manifest() -> dict[str, dict[str, str]]:
    path = OUTPUT_DIR / "data_source_manifest.csv"
    if not path.exists():
        return {}
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    return {row.get("symbol", ""): row for row in rows if row.get("symbol")}


def clean_output_dir() -> None:
    if OUTPUT_DIR.exists():
        resolved = OUTPUT_DIR.resolve()
        expected = (ROOT / "evidence" / "data_capability" / TASK_ID).resolve()
        if expected not in resolved.parents:
            raise RuntimeError(f"Refusing to remove unexpected output path: {resolved}")
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def cache_path(symbol: str) -> Path:
    return DATA_CACHE_DIR / f"{symbol}.csv"


def metadata_path(symbol: str) -> Path:
    return DATA_CACHE_DIR / f"{symbol}.acquisition.json"


def read_symbol_metadata(symbol: str) -> dict[str, Any]:
    path = metadata_path(symbol)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def sanitize_error(exc: BaseException) -> str:
    text = str(exc).replace("\n", " ").replace("\r", " ")
    for key in ("ALPACA_PAPER_API_KEY", "ALPACA_PAPER_SECRET_KEY", "APCA-API-KEY-ID", "APCA-API-SECRET-KEY"):
        text = text.replace(key, f"{key}_REDACTED")
    return text[:500]


def canonicalize_cache_frame(raw: pd.DataFrame, symbol: str) -> pd.DataFrame:
    frame = build_adjusted_ohlc(raw, symbol)
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    return frame[list(REQUIRED_CACHE_COLUMNS)]


def load_canonical_cache(symbol: str) -> pd.DataFrame:
    path = cache_path(symbol)
    if not path.exists():
        return pd.DataFrame()
    raw = pd.read_csv(path)
    return canonicalize_cache_frame(raw, symbol)


def integrity_rows_for_frame(symbol: str, frame: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    def add(check: str, passed: bool, details: str = "", count: int | str = "") -> None:
        rows.append(
            {
                "symbol": symbol,
                "check_name": check,
                "status": "pass" if passed else "fail",
                "violation_count": count,
                "details": details,
            }
        )

    if frame.empty:
        add("non_empty_frame", False, "no rows available", 0)
        return rows
    add("required_canonical_columns_present", set(REQUIRED_CACHE_COLUMNS).issubset(frame.columns), "", "")
    dates = pd.to_datetime(frame["date"], errors="coerce")
    add("dates_parse", bool(dates.notna().all()), "", int(dates.isna().sum()))
    add("dates_strictly_increasing", bool(dates.is_monotonic_increasing), "", "")
    add("dates_unique", bool(not dates.duplicated().any()), "", int(dates.duplicated().sum()))
    finite_price = frame[["open", "high", "low", "close", "adj_close", "raw_open", "raw_high", "raw_low", "raw_close", "raw_adj_close"]].apply(
        pd.to_numeric, errors="coerce"
    )
    finite_price_ok = bool(np.isfinite(finite_price.to_numpy(dtype=float)).all())
    positive_price_ok = bool((finite_price > 0.0).all().all())
    add("prices_finite", finite_price_ok, "", int((~np.isfinite(finite_price.to_numpy(dtype=float))).sum()))
    add("prices_positive", positive_price_ok, "", int((finite_price <= 0.0).sum().sum()))
    raw_volume = pd.to_numeric(frame["raw_volume"], errors="coerce")
    volume = pd.to_numeric(frame["volume"], errors="coerce")
    volume_ok = bool(raw_volume.notna().all() and volume.notna().all() and (raw_volume >= 0.0).all() and (volume >= 0.0).all())
    add("volume_finite_nonnegative", volume_ok, "", int(raw_volume.isna().sum() + volume.isna().sum()))
    adjusted_high_ok = bool((finite_price["high"] + 1e-9 >= finite_price[["open", "low", "close"]].max(axis=1)).all())
    adjusted_low_ok = bool((finite_price["low"] <= finite_price[["open", "high", "close"]].min(axis=1) + 1e-9).all())
    raw_high_ok = bool((finite_price["raw_high"] + 1e-9 >= finite_price[["raw_open", "raw_low", "raw_close"]].max(axis=1)).all())
    raw_low_ok = bool((finite_price["raw_low"] <= finite_price[["raw_open", "raw_high", "raw_close"]].min(axis=1) + 1e-9).all())
    add("adjusted_ohlc_relationships", adjusted_high_ok and adjusted_low_ok, "", "")
    add("raw_ohlc_relationships", raw_high_ok and raw_low_ok, "", "")
    factor = pd.to_numeric(frame["adjustment_factor"], errors="coerce")
    factor_ok = bool(factor.notna().all() and (factor > 0.0).all() and factor.apply(math.isfinite).all())
    add("adjustment_factor_positive_finite", factor_ok, "", int((factor <= 0.0).sum() + factor.isna().sum()))
    expected_adj_close = finite_price["raw_close"] * factor
    factor_math_ok = bool((expected_adj_close - finite_price["raw_adj_close"]).abs().max() <= 1e-6)
    add("adjustment_factor_matches_raw_adj_close", factor_math_ok, "", "")
    close_match_ok = bool((finite_price["close"] - finite_price["adj_close"]).abs().max() <= 1e-10)
    add("close_equals_adj_close_in_canonical_cache", close_match_ok, "", "")
    symbol_ok = bool(frame["symbol"].astype(str).str.upper().eq(symbol).all())
    add("symbol_identity_matches_requested_symbol", symbol_ok, "", int((~frame["symbol"].astype(str).str.upper().eq(symbol)).sum()))
    last_date = dates.max()
    add(
        "coverage_through_required_date",
        bool(pd.notna(last_date) and last_date >= REQUIRED_THROUGH_DATE),
        f"last_date={last_date.date().isoformat() if pd.notna(last_date) else ''}; required={REQUIRED_THROUGH_DATE.date().isoformat()}",
        "",
    )
    return rows


def frame_valid(symbol: str, frame: pd.DataFrame) -> tuple[bool, str, list[dict[str, Any]]]:
    rows = integrity_rows_for_frame(symbol, frame)
    failing = [row for row in rows if row["status"] != "pass"]
    if failing:
        return False, "|".join(row["check_name"] for row in failing), rows
    return True, "", rows


def try_existing_cache(symbol: str) -> tuple[pd.DataFrame | None, str, list[dict[str, Any]]]:
    frame = load_canonical_cache(symbol)
    if frame.empty:
        return None, "missing_current_cache", integrity_rows_for_frame(symbol, frame)
    valid, reason, rows = frame_valid(symbol, frame)
    if not valid:
        return None, f"current_cache_failed_validation:{reason}", rows
    return frame, "current_cache_validated", rows


def try_alpaca(symbol: str) -> dict[str, Any]:
    row: dict[str, Any] = {
        "symbol": symbol,
        "alpaca_attempted": True,
        "alpaca_endpoint": "/v2/stocks/bars",
        "alpaca_feed": "iex",
        "alpaca_adjustment": "all",
        "alpaca_schema_fields": "date|timestamp|open|high|low|close|volume",
        "alpaca_status": "",
        "alpaca_rows_returned": 0,
        "alpaca_reason_not_admitted": "",
    }
    try:
        credentials = load_alpaca_credentials("paper")
        row["alpaca_credentials_present"] = bool(credentials.present)
        row["alpaca_credentials_source"] = credentials.source if credentials.present else "none"
        row["alpaca_live_credentials_detected"] = bool(credentials.live_credentials_detected)
        if not credentials.present:
            row["alpaca_status"] = "auth_unavailable"
            row["alpaca_reason_not_admitted"] = "alpaca_paper_market_data_credentials_missing"
            return row
        client = AlpacaClient(credentials, AlpacaClientConfig(data_feed="iex", data_adjustment="all"))
        payload = client.get_historical_bars_page(
            symbols=[symbol],
            start=f"{DOWNLOAD_START}T00:00:00Z",
            end=f"{DOWNLOAD_END_EXCLUSIVE}T00:00:00Z",
            timeframe="1Day",
            feed="iex",
            adjustment="all",
        )
        parsed = parse_bars_response(payload, drop_incomplete_current_day=False).get(symbol, pd.DataFrame())
        row["alpaca_rows_returned"] = int(len(parsed))
        row["alpaca_status"] = "returned_bars"
        missing = sorted(set(REQUIRED_CACHE_COLUMNS) - set(parsed.columns))
        row["alpaca_reason_not_admitted"] = (
            "existing_alpaca_integration_returns_adjusted_stock_bars_without_canonical_raw_adjustment_metadata:"
            + "|".join(missing)
        )
    except BaseException as exc:  # noqa: BLE001 - evidence packet should capture provider capability failures.
        row["alpaca_status"] = "provider_call_failed"
        row["alpaca_reason_not_admitted"] = sanitize_error(exc)
    return row


def yfinance_download(symbol: str) -> pd.DataFrame:
    import yfinance as yf

    raw = yf.download(
        symbol,
        start=DOWNLOAD_START,
        end=DOWNLOAD_END_EXCLUSIVE,
        auto_adjust=False,
        actions=True,
        progress=False,
        multi_level_index=False,
        timeout=30,
    )
    if raw.empty:
        raise RuntimeError(f"{symbol}: yfinance returned no rows")
    return canonicalize_cache_frame(raw, symbol)


def write_validated_cache(symbol: str, frame: pd.DataFrame, provenance: dict[str, Any]) -> None:
    DATA_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = cache_path(symbol)
    temp_path = path.with_suffix(".csv.tmp")
    frame.to_csv(temp_path, index=False, lineterminator="\n")
    reloaded = pd.read_csv(temp_path)
    normalized = canonicalize_cache_frame(reloaded, symbol)
    valid, reason, _ = frame_valid(symbol, normalized)
    if not valid:
        temp_path.unlink(missing_ok=True)
        raise RuntimeError(f"{symbol}: refusing to admit cache after validation failure: {reason}")
    temp_path.replace(path)
    meta = {
        **provenance,
        "symbol": symbol,
        "task_id": TASK_ID,
        "cache_path": rel(path),
        "cache_file_hash": file_hash(path),
        "canonical_frame_hash": dataframe_hash(normalized),
        "admitted_to_canonical_cache": True,
        "admission_timestamp": FROZEN_TIMESTAMP,
        "no_strategy_backtest_run": True,
        "no_broker_account_or_order_endpoint_called": True,
    }
    metadata_path(symbol).write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def acquire_or_validate_symbol(symbol: str, previous_manifest: dict[str, dict[str, str]]) -> dict[str, Any]:
    previous = previous_manifest.get(symbol, {})
    existing_frame, existing_status, existing_integrity = try_existing_cache(symbol)
    if existing_frame is not None:
        metadata = read_symbol_metadata(symbol)
        preferred_meta = metadata.get("preferred_provider_attempt", {}) if isinstance(metadata.get("preferred_provider_attempt"), dict) else {}
        previous_is_reuse_only = (
            bool(preferred_meta)
            and previous.get("preferred_provider_status") == "not_called_current_cache_valid"
            and previous.get("fallback_status") == "not_called_current_cache_valid"
        )
        prior_manifest = {} if previous_is_reuse_only else previous
        cache_status = "validated_current_cache"
        acquisition_result = "cache_already_present"
        if previous.get("final_cache_status") == "validated":
            acquisition_result = "previously_acquired_by_task_cache_reused"
        elif metadata.get("admitted_to_canonical_cache") is True:
            acquisition_result = "previously_acquired_by_task_cache_reused"
        preferred_attempted = prior_manifest.get("preferred_provider_attempted", preferred_meta.get("alpaca_attempted", False))
        fallback_attempted = prior_manifest.get(
            "fallback_attempted",
            bool(metadata.get("admitted_provider") == "yfinance_existing_repo_supported_fallback"),
        )
        return {
            "symbol": symbol,
            "frame": existing_frame,
            "integrity_rows": existing_integrity,
            "source_row": {
                "symbol": symbol,
                "preferred_provider": "alpaca_market_data",
                "preferred_provider_attempted": preferred_attempted,
                "preferred_provider_status": prior_manifest.get(
                    "preferred_provider_status", preferred_meta.get("alpaca_status", "not_called_current_cache_valid")
                ),
                "preferred_provider_reason_not_admitted": prior_manifest.get(
                    "preferred_provider_reason_not_admitted", preferred_meta.get("alpaca_reason_not_admitted", "")
                ),
                "fallback_provider": prior_manifest.get("admitted_provider", metadata.get("admitted_provider", "existing_cache")),
                "fallback_attempted": fallback_attempted,
                "fallback_status": prior_manifest.get(
                    "fallback_status",
                    "downloaded_validated_and_admitted" if fallback_attempted else "not_called_current_cache_valid",
                ),
                "fallback_failure_reason": prior_manifest.get("fallback_failure_reason", ""),
                "admitted_provider": prior_manifest.get("admitted_provider", metadata.get("admitted_provider", "existing_cache")),
                "acquisition_result": acquisition_result,
                "final_cache_status": "validated",
                "cache_path": rel(cache_path(symbol)),
                "cache_file_hash": file_hash(cache_path(symbol)),
                "canonical_frame_hash": dataframe_hash(existing_frame),
                "first_retrieval_timestamp": prior_manifest.get("first_retrieval_timestamp", metadata.get("admission_timestamp", FROZEN_TIMESTAMP)),
                "provider_download_performed": prior_manifest.get("provider_download_performed", bool(fallback_attempted)),
                "existing_integration_reused": True,
                "existing_cache_status_before_provider_attempt": existing_status,
                "alpaca_attempted": prior_manifest.get("alpaca_attempted", preferred_attempted),
                "alpaca_endpoint": prior_manifest.get("alpaca_endpoint", preferred_meta.get("alpaca_endpoint", "/v2/stocks/bars")),
                "alpaca_feed": prior_manifest.get("alpaca_feed", preferred_meta.get("alpaca_feed", "iex")),
                "alpaca_adjustment": prior_manifest.get("alpaca_adjustment", preferred_meta.get("alpaca_adjustment", "all")),
                "alpaca_schema_fields": prior_manifest.get(
                    "alpaca_schema_fields",
                    preferred_meta.get("alpaca_schema_fields", "date|timestamp|open|high|low|close|volume"),
                ),
                "alpaca_status": prior_manifest.get("alpaca_status", preferred_meta.get("alpaca_status", "")),
                "alpaca_rows_returned": prior_manifest.get("alpaca_rows_returned", preferred_meta.get("alpaca_rows_returned", "")),
                "alpaca_reason_not_admitted": prior_manifest.get(
                    "alpaca_reason_not_admitted", preferred_meta.get("alpaca_reason_not_admitted", "")
                ),
                "alpaca_credentials_present": prior_manifest.get("alpaca_credentials_present", preferred_meta.get("alpaca_credentials_present", "")),
                "alpaca_credentials_source": prior_manifest.get("alpaca_credentials_source", preferred_meta.get("alpaca_credentials_source", "")),
                "alpaca_live_credentials_detected": prior_manifest.get(
                    "alpaca_live_credentials_detected", preferred_meta.get("alpaca_live_credentials_detected", "")
                ),
            },
        }

    alpaca_row = try_alpaca(symbol)
    fallback_status = ""
    fallback_reason = ""
    frame: pd.DataFrame | None = None
    try:
        frame = yfinance_download(symbol)
        valid, reason, integrity = frame_valid(symbol, frame)
        if not valid:
            fallback_status = "downloaded_but_failed_validation"
            fallback_reason = reason
            frame = None
        else:
            fallback_status = "downloaded_validated_and_admitted"
            provenance = {
                "admitted_provider": "yfinance_existing_repo_supported_fallback",
                "provider_role": "single_bounded_fallback_after_alpaca_inadequate_or_unavailable",
                "preferred_provider_attempt": alpaca_row,
                "download_start": DOWNLOAD_START,
                "download_end_exclusive": DOWNLOAD_END_EXCLUSIVE,
                "canonical_schema": list(REQUIRED_CACHE_COLUMNS),
            }
            write_validated_cache(symbol, frame, provenance)
            frame = load_canonical_cache(symbol)
            integrity = frame_valid(symbol, frame)[2]
    except BaseException as exc:  # noqa: BLE001
        fallback_status = "provider_call_failed"
        fallback_reason = sanitize_error(exc)
        frame = None
        integrity = integrity_rows_for_frame(symbol, pd.DataFrame())

    if frame is None:
        return {
            "symbol": symbol,
            "frame": pd.DataFrame(),
            "integrity_rows": integrity,
            "source_row": {
                "symbol": symbol,
                "preferred_provider": "alpaca_market_data",
                "preferred_provider_attempted": True,
                "preferred_provider_status": alpaca_row.get("alpaca_status", ""),
                "preferred_provider_reason_not_admitted": alpaca_row.get("alpaca_reason_not_admitted", ""),
                "fallback_provider": "yfinance_existing_repo_supported_fallback",
                "fallback_attempted": True,
                "fallback_status": fallback_status,
                "fallback_failure_reason": fallback_reason,
                "admitted_provider": "",
                "acquisition_result": "failed",
                "final_cache_status": "missing_or_invalid",
                "cache_path": rel(cache_path(symbol)),
                "cache_file_hash": file_hash(cache_path(symbol)),
                "canonical_frame_hash": "",
                "first_retrieval_timestamp": "",
                "provider_download_performed": False,
                "existing_integration_reused": True,
                "existing_cache_status_before_provider_attempt": existing_status,
                **{k: v for k, v in alpaca_row.items() if k.startswith("alpaca_")},
            },
        }
    return {
        "symbol": symbol,
        "frame": frame,
        "integrity_rows": integrity,
        "source_row": {
            "symbol": symbol,
            "preferred_provider": "alpaca_market_data",
            "preferred_provider_attempted": True,
            "preferred_provider_status": alpaca_row.get("alpaca_status", ""),
            "preferred_provider_reason_not_admitted": alpaca_row.get("alpaca_reason_not_admitted", ""),
            "fallback_provider": "yfinance_existing_repo_supported_fallback",
            "fallback_attempted": True,
            "fallback_status": fallback_status,
            "fallback_failure_reason": fallback_reason,
            "admitted_provider": "yfinance_existing_repo_supported_fallback",
            "acquisition_result": "downloaded_validated_and_admitted",
            "final_cache_status": "validated",
            "cache_path": rel(cache_path(symbol)),
            "cache_file_hash": file_hash(cache_path(symbol)),
            "canonical_frame_hash": dataframe_hash(frame),
            "first_retrieval_timestamp": FROZEN_TIMESTAMP,
            "provider_download_performed": True,
            "existing_integration_reused": True,
            "existing_cache_status_before_provider_attempt": existing_status,
            **{k: v for k, v in alpaca_row.items() if k.startswith("alpaca_")},
        },
    }


def coverage_row(symbol: str, frame: pd.DataFrame, source_row: dict[str, Any]) -> dict[str, Any]:
    if frame.empty:
        return {
            "symbol": symbol,
            "status": "missing_or_invalid",
            "first_date": "",
            "last_date": "",
            "row_count": 0,
            "required_through_date": REQUIRED_THROUGH_DATE.date().isoformat(),
            "covers_required_through_date": False,
            "observation_frequency": "daily_adjusted_ohlcv_required",
            "adjusted_open_high_low_close_volume_available": False,
            "provider": source_row.get("admitted_provider", ""),
            "cache_path": rel(cache_path(symbol)),
            "cache_file_hash": file_hash(cache_path(symbol)),
        }
    dates = pd.to_datetime(frame["date"])
    return {
        "symbol": symbol,
        "status": "validated",
        "first_date": dates.min().date().isoformat(),
        "last_date": dates.max().date().isoformat(),
        "row_count": int(len(frame)),
        "required_through_date": REQUIRED_THROUGH_DATE.date().isoformat(),
        "covers_required_through_date": bool(dates.max() >= REQUIRED_THROUGH_DATE),
        "observation_frequency": "adjusted_daily",
        "adjusted_open_high_low_close_volume_available": True,
        "provider": source_row.get("admitted_provider", ""),
        "canonical_schema": "|".join(REQUIRED_CACHE_COLUMNS),
        "cache_path": rel(cache_path(symbol)),
        "cache_file_hash": file_hash(cache_path(symbol)),
    }


def reload_reconciliation_row(symbol: str, frame: pd.DataFrame) -> dict[str, Any]:
    reloaded = load_canonical_cache(symbol)
    return {
        "symbol": symbol,
        "cache_path": rel(cache_path(symbol)),
        "original_row_count": int(len(frame)),
        "reloaded_row_count": int(len(reloaded)),
        "original_frame_hash": dataframe_hash(frame) if not frame.empty else "",
        "reloaded_frame_hash": dataframe_hash(reloaded) if not reloaded.empty else "",
        "cache_file_hash": file_hash(cache_path(symbol)),
        "reload_identical": bool(not frame.empty and len(frame) == len(reloaded) and dataframe_hash(frame) == dataframe_hash(reloaded)),
    }


def target_cards() -> list[Any]:
    return [
        card
        for card in source_batch.CARDS
        if card.strategy_id
        in {
            "daryanani_opportunistic_rebalance_20band_10day_v1",
            "clare_inverse_volatility_five_asset_risk_parity_v1",
            "ice_vaneck_us_fallen_angel_angl_v1",
        }
    ]


def nvi_card() -> Any:
    return next(card for card in source_batch.CARDS if card.strategy_id == "fosback_nvi_255ema_spy_bil_v1")


def cache_available(symbol: str) -> bool:
    frame = prior.load_adjusted_ohlcv(symbol)
    if frame.empty:
        return False
    return bool(frame.index.max() >= REQUIRED_THROUGH_DATE)


def common_price_frame(symbols: tuple[str, ...]) -> pd.DataFrame:
    frame = prior.load_price_frame(symbols)
    if frame.empty:
        return frame
    return frame.loc[:REQUIRED_THROUGH_DATE].dropna().sort_index()


def month_end_return_count(prices: pd.DataFrame) -> int:
    if prices.empty:
        return 0
    periods = pd.Series(prices.index.to_period("M"), index=prices.index)
    month_ends = prices.index[periods.ne(periods.shift(-1)).fillna(True)]
    returns = prices.loc[month_ends].pct_change(fill_method=None).dropna()
    return int(len(returns.dropna()))


def strategy_sufficiency_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for card in target_cards():
        required = tuple(card.required_data_symbols)
        missing = [symbol for symbol in required if not cache_available(symbol)]
        prices = common_price_frame(required) if not missing else pd.DataFrame()
        monthly_returns = month_end_return_count(prices)
        has_common = not prices.empty and prices.index.max() >= REQUIRED_THROUGH_DATE
        warmup_ok = True
        if card.strategy_id == "clare_inverse_volatility_five_asset_risk_parity_v1":
            warmup_ok = monthly_returns >= 12
        ready = bool(not missing and has_common and warmup_ok)
        rows.append(
            {
                "strategy_id": card.strategy_id,
                "family_id": card.family_id,
                "trial_id": card.trial_id,
                "route": card.route,
                "required_symbols": required,
                "previous_blocked_symbol": "VNQ" if "VNQ" in required else "JNK",
                "missing_symbols_after_task": missing,
                "common_start": prices.index.min().date().isoformat() if not prices.empty else "",
                "common_end": prices.index.max().date().isoformat() if not prices.empty else "",
                "common_trading_days": int(len(prices)),
                "completed_monthly_return_count": monthly_returns,
                "risk_parity_12_month_warmup_satisfied": warmup_ok if card.strategy_id == "clare_inverse_volatility_five_asset_risk_parity_v1" else "",
                "data_sufficiency_outcome": "ready_for_rerun_after_cache_validation" if ready else "inconclusive_data_issue",
                "backtest_run": False,
                "controls_or_benchmarks_calculated": False,
            }
        )
    return rows


def strategy_card_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    prior_issues = read_csv_rows(source_batch.OUTPUT_DIR / "rejection_and_data_issue_log.csv")
    issue_by_strategy = {row["strategy_id"]: row for row in prior_issues}
    suff_by_strategy = {row["strategy_id"]: row for row in strategy_sufficiency_rows()}
    for card in target_cards():
        issue = issue_by_strategy.get(card.strategy_id, {})
        suff = suff_by_strategy.get(card.strategy_id, {})
        rows.append(
            {
                "strategy_id": card.strategy_id,
                "family_id": card.family_id,
                "trial_id": card.trial_id,
                "entity_type": "strategy_configuration",
                "stage": "data_feasibility",
                "source_library_id": SOURCE_LIBRARY_ID,
                "route": card.route,
                "complete_frozen_rule": card.complete_frozen_rule,
                "instruments": card.instruments,
                "required_symbols": card.required_data_symbols,
                "blocked_symbol_from_prior_batch": issue.get("missing_symbols", ""),
                "prior_classification": issue.get("classification", "inconclusive_data_issue"),
                "current_data_sufficiency": suff.get("data_sufficiency_outcome", ""),
                "candidate_rules_changed": False,
                "new_strategy_trial_created": False,
                "strategy_backtest_run": False,
            }
        )
    return rows


def trial_ledger_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    suff_by_strategy = {row["strategy_id"]: row for row in strategy_sufficiency_rows()}
    for card in target_cards():
        rows.append(
            {
                "trial_id": card.trial_id,
                "parent_trial_id": card.parent_trial_id,
                "strategy_id": card.strategy_id,
                "family_id": card.family_id,
                "entity_type": "strategy_configuration",
                "stage": "data_feasibility_carry_forward",
                "source_library_id": SOURCE_LIBRARY_ID,
                "carried_forward_existing_trial": True,
                "changed_fields_from_parent": "none_data_capability_task_only",
                "prior_outcome": "inconclusive_data_issue",
                "current_data_outcome": suff_by_strategy[card.strategy_id]["data_sufficiency_outcome"],
                "new_strategy_trial_created": False,
                "preexisting_trial_id_preserved": True,
            }
        )
    return rows


def benchmark_reference_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for card in target_cards():
        for control_id in card.principal_control_ids:
            rows.append(
                {
                    "strategy_id": card.strategy_id,
                    "family_id": card.family_id,
                    "trial_id": card.trial_id,
                    "benchmark_or_control_id": control_id,
                    "entity_type": "benchmark_reference",
                    "stage": "benchmark_reference_only",
                    "calculated_in_this_task": False,
                    "source": "fast_source_library_batch_v3_frozen_controls",
                }
            )
    return rows


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def process_task_rows(symbol_results: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for symbol in TARGET_SYMBOLS:
        source_row = symbol_results[symbol]["source_row"]
        rows.append(
            {
                "task_id": f"{symbol.lower()}_data_feasibility_acquisition_v1",
                "parent_task_id": TASK_ID,
                "symbol": symbol,
                "entity_type": "data_capability_task",
                "stage": "feasibility",
                "adaptation_label": "data_feasibility_adjustment",
                "provider_attempt_path": PROVIDER_ATTEMPT_LABEL,
                "final_cache_status": source_row.get("final_cache_status", ""),
                "acquisition_result": source_row.get("acquisition_result", ""),
                "cache_path": source_row.get("cache_path", ""),
                "strategy_backtest_run": False,
                "broker_or_order_path_touched": False,
            }
        )
    return rows


def global_next_action(symbol_results: dict[str, dict[str, Any]]) -> str:
    ready = {symbol: symbol_results[symbol]["source_row"].get("final_cache_status") == "validated" for symbol in TARGET_SYMBOLS}
    if ready["VNQ"] and ready["JNK"]:
        return "rerun_fast_source_library_blocked_candidates_v3"
    if ready["VNQ"] and not ready["JNK"]:
        return "rerun_vnq_unblocked_source_candidates_v3"
    if ready["JNK"] and not ready["VNQ"]:
        return "rerun_jnk_unblocked_source_candidate_v3"
    return "evaluate_remaining_source_library_candidates_v1"


def failure_rows(symbol_results: dict[str, dict[str, Any]], sufficiency: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for symbol in TARGET_SYMBOLS:
        source_row = symbol_results[symbol]["source_row"]
        if source_row.get("final_cache_status") != "validated":
            rows.append(
                {
                    "entity_id": symbol,
                    "entity_type": "data_symbol",
                    "failure_reason": source_row.get("fallback_failure_reason")
                    or source_row.get("preferred_provider_reason_not_admitted")
                    or "missing_validated_cache",
                    "blocking": True,
                    "no_substitution_made": True,
                }
            )
    for row in sufficiency:
        if row["data_sufficiency_outcome"] != "ready_for_rerun_after_cache_validation":
            rows.append(
                {
                    "entity_id": row["strategy_id"],
                    "entity_type": "strategy_configuration",
                    "failure_reason": "missing_data_after_vnq_jnk_data_task",
                    "missing_symbols": row["missing_symbols_after_task"],
                    "blocking": True,
                    "no_substitution_made": True,
                }
            )
    return rows


def outcome_rows(symbol_results: dict[str, dict[str, Any]], sufficiency: list[dict[str, Any]], next_action: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for symbol in TARGET_SYMBOLS:
        source_row = symbol_results[symbol]["source_row"]
        rows.append(
            {
                "entity_id": symbol,
                "entity_type": "data_symbol",
                "stage": "data_feasibility",
                "outcome": "validated_cache_ready" if source_row.get("final_cache_status") == "validated" else "data_capability_blocked",
                "next_action": next_action,
                "counted_in_data_acquisition_symbol_cohort": True,
            }
        )
    for row in sufficiency:
        rows.append(
            {
                "entity_id": row["strategy_id"],
                "entity_type": "strategy_configuration",
                "stage": "data_sufficiency_assessment",
                "outcome": row["data_sufficiency_outcome"],
                "next_action": next_action,
                "counted_in_data_acquisition_symbol_cohort": False,
            }
        )
    nvi = nvi_card()
    rows.append(
        {
            "entity_id": nvi.strategy_id,
            "entity_type": "strategy_configuration",
            "stage": "exploratory_followup_standalone",
            "outcome": "exploratory_followup_candidate_standalone",
            "next_action": "targeted_nvi_incremental_signal_followup_v1",
            "counted_in_data_acquisition_symbol_cohort": False,
        }
    )
    return rows


def next_action_rows(symbol_results: dict[str, dict[str, Any]], sufficiency: list[dict[str, Any]], next_action: str) -> list[dict[str, Any]]:
    rows = [
        {
            "scope": "global",
            "entity_id": TASK_ID,
            "exact_next_action": next_action,
            "execute_now": False,
            "reason": "next action selected only from VNQ/JNK validation outcome",
        }
    ]
    for row in sufficiency:
        rows.append(
            {
                "scope": "strategy_configuration",
                "entity_id": row["strategy_id"],
                "exact_next_action": next_action if row["data_sufficiency_outcome"] == "ready_for_rerun_after_cache_validation" else "resolve_remaining_data_blocker",
                "execute_now": False,
                "reason": row["data_sufficiency_outcome"],
            }
        )
    return rows


def build_report(symbol_results: dict[str, dict[str, Any]], sufficiency: list[dict[str, Any]], next_action: str) -> str:
    symbol_lines = []
    for symbol in TARGET_SYMBOLS:
        source_row = symbol_results[symbol]["source_row"]
        symbol_lines.append(
            f"- `{symbol}`: `{source_row.get('final_cache_status')}` via `{source_row.get('admitted_provider')}`; "
            f"cache `{source_row.get('cache_path')}`."
        )
    suff_lines = []
    for row in sufficiency:
        suff_lines.append(
            f"- `{row['strategy_id']}`: `{row['data_sufficiency_outcome']}`; common window "
            f"`{row['common_start']}` to `{row['common_end']}`."
        )
    return f"""
# VNQ/JNK Data Feasibility Acquisition V1

This packet investigated exactly `VNQ` and `JNK` as a data-capability task. It did not run strategy backtests,
controls, benchmark metrics, promotion review, paper/demo activation, broker account calls, broker order calls,
or real-money actions.

## Provider Path

Alpaca market data was the preferred source. The existing Alpaca stock-bars integration was inspected and used only
as a read-only market-data path. When Alpaca was unavailable or did not expose the canonical raw/adjustment fields
required by the repository cache, the task used one bounded fallback through the repository-supported yfinance
adjusted daily OHLC builder.

## Symbol Outcomes

{chr(10).join(symbol_lines)}

## Strategy Data Sufficiency

{chr(10).join(suff_lines)}

`fosback_nvi_255ema_spy_bil_v1` was not rerun, modified, promoted, validated, or closed. Its status is carried
forward only as a non-cohort strategy-configuration record with next action `targeted_nvi_incremental_signal_followup_v1`.

Exact next action: `{next_action}`.
"""


def write_artifacts(symbol_results: dict[str, dict[str, Any]], before_hashes: dict[str, str], prior_hashes_before: dict[str, str], cache_hashes_before: dict[str, str]) -> dict[str, Any]:
    sufficiency = strategy_sufficiency_rows()
    next_action = global_next_action(symbol_results)
    source_rows = [symbol_results[symbol]["source_row"] for symbol in TARGET_SYMBOLS]
    coverage_rows = [coverage_row(symbol, symbol_results[symbol]["frame"], symbol_results[symbol]["source_row"]) for symbol in TARGET_SYMBOLS]
    integrity_rows = [row for symbol in TARGET_SYMBOLS for row in symbol_results[symbol]["integrity_rows"]]
    reload_rows = [reload_reconciliation_row(symbol, symbol_results[symbol]["frame"]) for symbol in TARGET_SYMBOLS]
    failures = failure_rows(symbol_results, sufficiency)
    outcomes = outcome_rows(symbol_results, sufficiency, next_action)
    actions = next_action_rows(symbol_results, sufficiency, next_action)
    after_hashes = protected_hashes()
    prior_hashes_after = prior_evidence_hashes()
    cache_hashes_after = cache_guard_hashes()
    symbol_ready_count = sum(1 for symbol in TARGET_SYMBOLS if symbol_results[symbol]["source_row"].get("final_cache_status") == "validated")
    strategy_ready_count = sum(1 for row in sufficiency if row["data_sufficiency_outcome"] == "ready_for_rerun_after_cache_validation")
    consistency = {
        "task_id": TASK_ID,
        "exact_symbols_investigated": list(TARGET_SYMBOLS),
        "exactly_vnq_jnk_investigated": tuple(TARGET_SYMBOLS) == ("VNQ", "JNK"),
        "alpaca_preferred": True,
        "single_existing_provider_fallback_only": True,
        "canonical_cache_admitted_symbols": [
            symbol for symbol in TARGET_SYMBOLS if symbol_results[symbol]["source_row"].get("final_cache_status") == "validated"
        ],
        "validated_symbol_count": symbol_ready_count,
        "strategy_data_sufficiency_ready_count": strategy_ready_count,
        "nvi_status_carried_forward_non_cohort_only": True,
        "benchmark_references_only_no_calculation": True,
        "protected_state_hashes_before": before_hashes,
        "protected_state_hashes_after": after_hashes,
        "protected_state_hashes_unchanged": before_hashes == after_hashes,
        "prior_evidence_hashes_before": prior_hashes_before,
        "prior_evidence_hashes_after": prior_hashes_after,
        "prior_evidence_hashes_unchanged": prior_hashes_before == prior_hashes_after,
        "preexisting_cache_hashes_before": cache_hashes_before,
        "preexisting_cache_hashes_after": cache_hashes_after,
        "preexisting_cached_symbols_unchanged": cache_hashes_before == cache_hashes_after,
        "cache_reload_all_identical": all(row["reload_identical"] for row in reload_rows if row["original_row_count"]),
        "all_integrity_checks_pass_for_validated_symbols": all(
            row["status"] == "pass"
            for row in integrity_rows
            if symbol_results[row["symbol"]]["source_row"].get("final_cache_status") == "validated"
        ),
        "exact_next_action": next_action,
        **FORBIDDEN_FLAGS,
    }

    manifest = {
        "task_id": TASK_ID,
        "task_type": "data-acquisition-or-capability",
        "stage": "feasibility",
        "primary_adaptation_label": "data_feasibility_adjustment",
        "frozen_timestamp": FROZEN_TIMESTAMP,
        "target_symbols": list(TARGET_SYMBOLS),
        "required_through_date": REQUIRED_THROUGH_DATE.date().isoformat(),
        "source_batch": "fast_source_library_batch_v3",
        "source_library_id": SOURCE_LIBRARY_ID,
        "protected_state_paths": [rel(path) for path in PROTECTED_STATE_PATHS],
        "input_evidence_dirs": [rel(path) for path in INPUT_EVIDENCE_DIRS],
        "forbidden_actions": FORBIDDEN_FLAGS,
        "exact_next_action": next_action,
    }

    write_yaml(OUTPUT_DIR / "task_manifest.yaml", manifest)
    write_csv(
        OUTPUT_DIR / "strategy_cards.csv",
        strategy_card_rows(),
        [
            "strategy_id",
            "family_id",
            "trial_id",
            "entity_type",
            "stage",
            "source_library_id",
            "route",
            "complete_frozen_rule",
            "instruments",
            "required_symbols",
            "blocked_symbol_from_prior_batch",
            "prior_classification",
            "current_data_sufficiency",
            "candidate_rules_changed",
            "new_strategy_trial_created",
            "strategy_backtest_run",
        ],
    )
    write_csv(
        OUTPUT_DIR / "trial_ledger.csv",
        trial_ledger_rows(),
        [
            "trial_id",
            "parent_trial_id",
            "strategy_id",
            "family_id",
            "entity_type",
            "stage",
            "source_library_id",
            "carried_forward_existing_trial",
            "changed_fields_from_parent",
            "prior_outcome",
            "current_data_outcome",
            "new_strategy_trial_created",
            "preexisting_trial_id_preserved",
        ],
    )
    write_csv(
        OUTPUT_DIR / "process_task_log.csv",
        process_task_rows(symbol_results),
        [
            "task_id",
            "parent_task_id",
            "symbol",
            "entity_type",
            "stage",
            "adaptation_label",
            "provider_attempt_path",
            "final_cache_status",
            "acquisition_result",
            "cache_path",
            "strategy_backtest_run",
            "broker_or_order_path_touched",
        ],
    )
    write_csv(
        OUTPUT_DIR / "data_source_manifest.csv",
        source_rows,
        [
            "symbol",
            "preferred_provider",
            "preferred_provider_attempted",
            "preferred_provider_status",
            "preferred_provider_reason_not_admitted",
            "fallback_provider",
            "fallback_attempted",
            "fallback_status",
            "fallback_failure_reason",
            "admitted_provider",
            "acquisition_result",
            "final_cache_status",
            "cache_path",
            "cache_file_hash",
            "canonical_frame_hash",
            "first_retrieval_timestamp",
            "provider_download_performed",
            "existing_integration_reused",
            "existing_cache_status_before_provider_attempt",
            "alpaca_attempted",
            "alpaca_endpoint",
            "alpaca_feed",
            "alpaca_adjustment",
            "alpaca_schema_fields",
            "alpaca_status",
            "alpaca_rows_returned",
            "alpaca_reason_not_admitted",
            "alpaca_credentials_present",
            "alpaca_credentials_source",
            "alpaca_live_credentials_detected",
        ],
    )
    write_csv(
        OUTPUT_DIR / "data_coverage.csv",
        coverage_rows,
        [
            "symbol",
            "status",
            "first_date",
            "last_date",
            "row_count",
            "required_through_date",
            "covers_required_through_date",
            "observation_frequency",
            "adjusted_open_high_low_close_volume_available",
            "provider",
            "canonical_schema",
            "cache_path",
            "cache_file_hash",
        ],
    )
    write_csv(OUTPUT_DIR / "data_integrity_checks.csv", integrity_rows, ["symbol", "check_name", "status", "violation_count", "details"])
    write_csv(
        OUTPUT_DIR / "cache_reload_reconciliation.csv",
        reload_rows,
        [
            "symbol",
            "cache_path",
            "original_row_count",
            "reloaded_row_count",
            "original_frame_hash",
            "reloaded_frame_hash",
            "cache_file_hash",
            "reload_identical",
        ],
    )
    write_csv(
        OUTPUT_DIR / "strategy_data_sufficiency.csv",
        sufficiency,
        [
            "strategy_id",
            "family_id",
            "trial_id",
            "route",
            "required_symbols",
            "previous_blocked_symbol",
            "missing_symbols_after_task",
            "common_start",
            "common_end",
            "common_trading_days",
            "completed_monthly_return_count",
            "risk_parity_12_month_warmup_satisfied",
            "data_sufficiency_outcome",
            "backtest_run",
            "controls_or_benchmarks_calculated",
        ],
    )
    write_csv(
        OUTPUT_DIR / "benchmark_reference_log.csv",
        benchmark_reference_rows(),
        [
            "strategy_id",
            "family_id",
            "trial_id",
            "benchmark_or_control_id",
            "entity_type",
            "stage",
            "calculated_in_this_task",
            "source",
        ],
    )
    write_csv(
        OUTPUT_DIR / "outcome_summary.csv",
        outcomes,
        ["entity_id", "entity_type", "stage", "outcome", "next_action", "counted_in_data_acquisition_symbol_cohort"],
    )
    write_csv(
        OUTPUT_DIR / "failure_reasons.csv",
        failures,
        ["entity_id", "entity_type", "failure_reason", "missing_symbols", "blocking", "no_substitution_made"],
    )
    write_csv(OUTPUT_DIR / "next_actions.csv", actions, ["scope", "entity_id", "exact_next_action", "execute_now", "reason"])
    write_json(OUTPUT_DIR / "consistency_check.json", consistency)
    write_text(OUTPUT_DIR / "data_feasibility_report.md", build_report(symbol_results, sufficiency, next_action))
    return consistency


def run() -> dict[str, Any]:
    previous_manifest = read_previous_task_source_manifest()
    before_hashes = protected_hashes()
    prior_hashes_before = prior_evidence_hashes()
    cache_hashes_before = cache_guard_hashes()
    clean_output_dir()

    symbol_results = {symbol: acquire_or_validate_symbol(symbol, previous_manifest) for symbol in TARGET_SYMBOLS}
    consistency = write_artifacts(symbol_results, before_hashes, prior_hashes_before, cache_hashes_before)
    return {
        "task_id": TASK_ID,
        "evidence_path": rel(OUTPUT_DIR),
        "validated_symbol_count": consistency["validated_symbol_count"],
        "strategy_data_sufficiency_ready_count": consistency["strategy_data_sufficiency_ready_count"],
        "exact_next_action": consistency["exact_next_action"],
        "protected_state_hashes_unchanged": consistency["protected_state_hashes_unchanged"],
        "prior_evidence_hashes_unchanged": consistency["prior_evidence_hashes_unchanged"],
        "preexisting_cached_symbols_unchanged": consistency["preexisting_cached_symbols_unchanged"],
        "task_outcome": "vnq_jnk_data_feasibility_acquisition_complete",
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
