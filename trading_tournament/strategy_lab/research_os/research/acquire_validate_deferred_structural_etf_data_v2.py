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
from src.data import build_adjusted_ohlc, load_symbol_data
from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT


TASK_ID = "acquire_validate_deferred_structural_etf_data_v2"
OUTPUT_DIR = ROOT / "evidence" / "data_capability" / TASK_ID / "latest"
SOURCE_LIBRARY_ID = "strategy_source_library_refresh_v2"
FROZEN_TIMESTAMP = "2026-07-24T00:00:00+00:00"
REQUIRED_THROUGH_DATE = pd.Timestamp("2026-06-18")
DOWNLOAD_END_EXCLUSIVE = "2026-06-19"
DOWNLOAD_START = "2000-01-01"
TARGET_SYMBOLS = ("CSD", "IWR", "PKW")
DATA_CACHE_DIR = ROOT / "data" / "cache"
SOURCE_RECORDS_PATH = (
    ROOT
    / "evidence"
    / "research_recovery"
    / "strategy_source_library_refresh_v2"
    / "latest"
    / "selected_source_library_records.yaml"
)
FROZEN_SPECS_PATH = (
    ROOT
    / "evidence"
    / "research_recovery"
    / "strategy_source_library_refresh_v2"
    / "latest"
    / "frozen_candidate_specs.yaml"
)
SOURCE_REPORT_PATH = (
    ROOT
    / "evidence"
    / "research_recovery"
    / "strategy_source_library_refresh_v2"
    / "latest"
    / "strategy_source_library_refresh_v2.md"
)
KST_CONSISTENCY_PATH = (
    ROOT
    / "evidence"
    / "lifecycle"
    / "reconcile_and_close_kst_after_validation_v1"
    / "latest"
    / "consistency_check.json"
)
SOURCE_RECORD_IDS = (
    "src_cusatis_spinoff_csd_wrapper_v1",
    "src_peyer_vermaelen_buyback_pkw_wrapper_v1",
)
STRATEGY_REQUIREMENTS = {
    "invesco_sp_us_spinoff_csd_v1": {
        "source_record_id": "src_cusatis_spinoff_csd_wrapper_v1",
        "family_id": "corporate_spinoff_equity_anomaly",
        "required_symbols": ("CSD", "IWR", "SPY"),
        "controls": ("IWR_buy_and_hold", "SPY_buy_and_hold"),
    },
    "nasdaq_buyback_achievers_pkw_v1": {
        "source_record_id": "src_peyer_vermaelen_buyback_pkw_wrapper_v1",
        "family_id": "net_share_reduction_buyback_anomaly",
        "required_symbols": ("PKW", "SPY", "DGRO"),
        "controls": ("SPY_buy_and_hold", "DGRO_buy_and_hold"),
    },
}
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
INPUT_EVIDENCE_FILES = [SOURCE_RECORDS_PATH, FROZEN_SPECS_PATH, SOURCE_REPORT_PATH, KST_CONSISTENCY_PATH]
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
    "new_provider_integration": False,
    "strategy_configuration_created": False,
    "experiment_trial_created": False,
    "paper_demo_observation_created": False,
    "new_research_candidate_created": False,
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
    return [path for path in INPUT_EVIDENCE_FILES if path.exists()]


def prior_evidence_hashes() -> dict[str, str]:
    return {rel(path): file_hash(path) for path in prior_evidence_files()}


def cache_guard_hashes() -> dict[str, str]:
    guarded: dict[str, str] = {}
    if not DATA_CACHE_DIR.exists():
        return guarded
    permitted_names = {
        name
        for symbol in TARGET_SYMBOLS
        for name in (f"{symbol}.csv", f"{symbol}.acquisition.json")
    }
    for path in sorted(DATA_CACHE_DIR.glob("*")):
        if path.name in permitted_names:
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
    valid_timestamp_range = bool(
        dates.notna().all()
        and (dates >= pd.Timestamp("1900-01-01")).all()
        and (dates <= REQUIRED_THROUGH_DATE).all()
        and (dates.dt.weekday < 5).all()
    )
    add(
        "no_impossible_or_future_timestamps",
        valid_timestamp_range,
        f"minimum={dates.min().date().isoformat()};maximum={dates.max().date().isoformat()};frozen_endpoint={REQUIRED_THROUGH_DATE.date().isoformat()}",
        int(((dates > REQUIRED_THROUGH_DATE) | (dates.dt.weekday >= 5)).sum()),
    )
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
    add("canonical_adjustment_compatibility", factor_ok and factor_math_ok and close_match_ok, "raw and adjusted fields remain separate", "")
    symbol_ok = bool(frame["symbol"].astype(str).str.upper().eq(symbol).all())
    add("symbol_identity_matches_requested_symbol", symbol_ok, "", int((~frame["symbol"].astype(str).str.upper().eq(symbol)).sum()))
    last_date = dates.max()
    add(
        "coverage_through_required_date",
        bool(pd.notna(last_date) and last_date >= REQUIRED_THROUGH_DATE),
        f"last_date={last_date.date().isoformat() if pd.notna(last_date) else ''}; required={REQUIRED_THROUGH_DATE.date().isoformat()}",
        "",
    )
    spy_path = cache_path("SPY")
    if spy_path.exists():
        spy_dates = pd.to_datetime(pd.read_csv(spy_path, usecols=["date"])["date"], errors="coerce").dropna()
        overlap_start = max(dates.min(), spy_dates.min())
        overlap_end = min(dates.max(), spy_dates.max(), REQUIRED_THROUGH_DATE)
        expected = set(spy_dates[(spy_dates >= overlap_start) & (spy_dates <= overlap_end)].dt.strftime("%Y-%m-%d"))
        observed = set(dates[(dates >= overlap_start) & (dates <= overlap_end)].dt.strftime("%Y-%m-%d"))
        missing = sorted(expected - observed)
        add(
            "missing_session_and_coverage_gap_report_generated",
            True,
            (
                f"reference=SPY_cache;overlap_start={overlap_start.date().isoformat()};"
                f"overlap_end={overlap_end.date().isoformat()};missing_sessions={'|'.join(missing)}"
            ),
            len(missing),
        )
    else:
        add("missing_session_and_coverage_gap_report_generated", False, "SPY reference cache missing", "")
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
        merged: dict[str, Any] = {"bars": {symbol: []}}
        page_token: str | None = None
        page_count = 0
        while True:
            payload = client.get_historical_bars_page(
                symbols=[symbol],
                start=f"{DOWNLOAD_START}T00:00:00Z",
                end=f"{DOWNLOAD_END_EXCLUSIVE}T00:00:00Z",
                timeframe="1Day",
                feed="iex",
                adjustment="all",
                page_token=page_token,
            )
            page_count += 1
            merged["bars"][symbol].extend(payload.get("bars", {}).get(symbol, []))
            page_token = payload.get("next_page_token")
            if not page_token:
                break
        parsed = parse_bars_response(merged, drop_incomplete_current_day=False).get(symbol, pd.DataFrame())
        row["alpaca_rows_returned"] = int(len(parsed))
        row["alpaca_page_count"] = page_count
        row["alpaca_pagination_complete"] = True
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
                "alpaca_page_count": prior_manifest.get("alpaca_page_count", preferred_meta.get("alpaca_page_count", "")),
                "alpaca_pagination_complete": prior_manifest.get(
                    "alpaca_pagination_complete", preferred_meta.get("alpaca_pagination_complete", "")
                ),
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


def backtester_interface_row(symbol: str, frame: pd.DataFrame) -> dict[str, Any]:
    if frame.empty:
        return {
            "symbol": symbol,
            "normal_backtester_interface": "src.data.load_symbol_data",
            "load_source": "not_called_missing_validated_cache",
            "load_status": "blocked",
            "loaded_row_count": 0,
            "expected_row_count": 0,
            "loaded_frame_hash": "",
            "expected_frame_hash": "",
            "normal_backtester_load_pass": False,
        }
    config = {
        "data": {
            "cache_dir": "data/cache",
            "raw_dir": "data/raw",
            "use_cache": True,
            "refresh_cache": False,
            "start_date": DOWNLOAD_START,
            "end_date": DOWNLOAD_END_EXCLUSIVE,
            "yfinance": {},
        }
    }
    loaded, coverage, source = load_symbol_data(symbol, config, ROOT)
    loaded_hash = dataframe_hash(loaded) if loaded is not None and not loaded.empty else ""
    expected_hash = dataframe_hash(frame) if not frame.empty else ""
    return {
        "symbol": symbol,
        "normal_backtester_interface": "src.data.load_symbol_data",
        "load_source": source,
        "load_status": coverage.get("status", ""),
        "loaded_row_count": int(len(loaded)) if loaded is not None else 0,
        "expected_row_count": int(len(frame)),
        "loaded_frame_hash": loaded_hash,
        "expected_frame_hash": expected_hash,
        "normal_backtester_load_pass": bool(
            loaded is not None
            and not loaded.empty
            and len(loaded) == len(frame)
            and loaded_hash == expected_hash
            and coverage.get("status") == "valid"
        ),
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


def load_frozen_source_records() -> list[dict[str, Any]]:
    payload = yaml.safe_load(SOURCE_RECORDS_PATH.read_text(encoding="utf-8")) or {}
    records = [
        record
        for record in payload.get("records", [])
        if record.get("source_record_id") in SOURCE_RECORD_IDS
    ]
    if [record.get("source_record_id") for record in records] != list(SOURCE_RECORD_IDS):
        by_id = {record.get("source_record_id"): record for record in records}
        records = [by_id[source_id] for source_id in SOURCE_RECORD_IDS if source_id in by_id]
    if len(records) != 2:
        raise RuntimeError("The frozen source packet must contain exactly the two authorized structural records.")
    if any(record.get("entity_type") != "source_library_record" or record.get("stage") != "source_extracted" for record in records):
        raise RuntimeError("Frozen source entity type or stage changed.")
    return records


def validate_frozen_specs() -> None:
    payload = yaml.safe_load(FROZEN_SPECS_PATH.read_text(encoding="utf-8")) or {}
    by_id = {row.get("strategy_id"): row for row in payload.get("strategies", [])}
    for strategy_id, requirement in STRATEGY_REQUIREMENTS.items():
        spec = by_id.get(strategy_id)
        if not spec:
            raise RuntimeError(f"Frozen candidate specification missing: {strategy_id}")
        controls = spec.get("controls", {})
        if tuple(spec.get("universe", [])) != requirement["required_symbols"]:
            raise RuntimeError(f"Frozen universe changed for {strategy_id}")
        if tuple(controls.values()) != requirement["controls"]:
            raise RuntimeError(f"Frozen controls changed for {strategy_id}")
        if spec.get("family_id") != requirement["family_id"]:
            raise RuntimeError(f"Frozen family changed for {strategy_id}")


def source_library_rows(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for record in records:
        strategy_id = record["proposed_strategy_id"]
        spec = STRATEGY_REQUIREMENTS[strategy_id]
        rows.append(
            {
                "source_record_id": record["source_record_id"],
                "entity_type": "source_library_record",
                "stage": "source_extracted",
                "proposed_strategy_id": strategy_id,
                "family_id": record["family_id"],
                "display_name": record["display_name"],
                "strategy_architecture": record["strategy_architecture"],
                "required_instruments": spec["required_symbols"],
                "benchmark_or_control": spec["controls"],
                "source_record_carried_forward": True,
                "counted_as_strategy_configuration": False,
                "counted_as_experiment_trial": False,
                "rules_or_mapping_changed": False,
            }
        )
    return rows


def symbol_failure_reason(source_row: dict[str, Any]) -> str:
    if source_row.get("final_cache_status") == "validated":
        return ""
    fallback_status = str(source_row.get("fallback_status", ""))
    preferred_status = str(source_row.get("preferred_provider_status", ""))
    if fallback_status == "downloaded_but_failed_validation":
        return "data_or_comparability_failure"
    if fallback_status == "provider_call_failed" or preferred_status in {"auth_unavailable", "provider_call_failed"}:
        return "data_unavailable"
    if preferred_status == "auth_unavailable" and not source_row.get("fallback_attempted"):
        return "capability_missing"
    return "methodology_failure"


def data_capability_rows(symbol_results: dict[str, dict[str, Any]], next_action: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for symbol in TARGET_SYMBOLS:
        source = symbol_results[symbol]["source_row"]
        feasible = source.get("final_cache_status") == "validated"
        rows.append(
            {
                "task_id": f"{TASK_ID}__{symbol.lower()}",
                "parent_task_id": TASK_ID,
                "symbol": symbol,
                "entity_type": "data_capability_task",
                "stage": "feasible" if feasible else "blocked",
                "adaptation_label": "data_feasibility_adjustment",
                "provider_attempted": source.get("preferred_provider", "alpaca_market_data"),
                "fallback_attempted": source.get("fallback_attempted", False),
                "acquisition_outcome": source.get("acquisition_result", ""),
                "validation_outcome": "canonical_data_validated" if feasible else "canonical_data_not_validated",
                "failure_reason": symbol_failure_reason(source),
                "next_action": next_action,
                "cache_path": source.get("cache_path", ""),
                "counted_as_strategy_configuration": False,
                "counted_as_experiment_trial": False,
                "counted_as_paper_demo_observation": False,
            }
        )
    return rows


def provider_attempt_rows(symbol_results: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for symbol in TARGET_SYMBOLS:
        source = symbol_results[symbol]["source_row"]
        rows.append(
            {
                "symbol": symbol,
                "attempt_order": 1,
                "provider_id": "alpaca_market_data",
                "provider_role": "preferred_read_only_market_data",
                "attempted": source.get("preferred_provider_attempted", False),
                "endpoint_or_library": source.get("alpaca_endpoint", "/v2/stocks/bars"),
                "feed": source.get("alpaca_feed", "iex"),
                "adjustment": source.get("alpaca_adjustment", "all"),
                "outcome": source.get("preferred_provider_status", ""),
                "rows_returned": source.get("alpaca_rows_returned", ""),
                "pagination_complete": source.get("alpaca_pagination_complete", ""),
                "reason_not_admitted": source.get("preferred_provider_reason_not_admitted", ""),
                "credentials_persisted": False,
                "account_order_or_position_endpoint_called": False,
            }
        )
        rows.append(
            {
                "symbol": symbol,
                "attempt_order": 2,
                "provider_id": "yfinance",
                "provider_role": "single_existing_repo_supported_fallback",
                "attempted": source.get("fallback_attempted", False),
                "endpoint_or_library": "src.data/yfinance_existing_supported_path",
                "feed": "adjusted_daily_etf_history",
                "adjustment": "auto_adjust_false_actions_true_then_build_adjusted_ohlc",
                "outcome": source.get("fallback_status", ""),
                "rows_returned": len(symbol_results[symbol]["frame"]),
                "pagination_complete": "not_applicable",
                "reason_not_admitted": source.get("fallback_failure_reason", ""),
                "credentials_persisted": False,
                "account_order_or_position_endpoint_called": False,
            }
        )
    return rows


def data_source_rows(symbol_results: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for symbol in TARGET_SYMBOLS:
        source = symbol_results[symbol]["source_row"]
        metadata = read_symbol_metadata(symbol)
        frame = symbol_results[symbol]["frame"]
        dates = pd.to_datetime(frame["date"], errors="coerce") if not frame.empty else pd.Series(dtype="datetime64[ns]")
        rows.append(
            {
                "symbol": symbol,
                "provider_identifier": source.get("admitted_provider", ""),
                "provider_role": metadata.get("provider_role", ""),
                "acquisition_timestamp": metadata.get("admission_timestamp", source.get("first_retrieval_timestamp", "")),
                "requested_start": DOWNLOAD_START,
                "requested_end_exclusive": DOWNLOAD_END_EXCLUSIVE,
                "first_valid_date": dates.min().date().isoformat() if not dates.empty else "",
                "last_valid_date": dates.max().date().isoformat() if not dates.empty else "",
                "row_count": int(len(frame)),
                "canonical_cache_path": source.get("cache_path", rel(cache_path(symbol))),
                "canonical_cache_hash": source.get("cache_file_hash", file_hash(cache_path(symbol))),
                "canonical_frame_hash": source.get("canonical_frame_hash", ""),
                "metadata_path": rel(metadata_path(symbol)),
                "metadata_hash": file_hash(metadata_path(symbol)),
                "canonical_field_mapping": {
                    "trading_date": "date",
                    "adjusted_open": "open",
                    "adjusted_high": "high",
                    "adjusted_low": "low",
                    "adjusted_close": "adj_close",
                    "adjusted_volume": "volume",
                    "provider_identifier": "separate_acquisition_metadata",
                    "acquisition_timestamp": "separate_acquisition_metadata",
                    "adjustment_provenance": "raw_*_plus_adjustment_factor_and_separate_acquisition_metadata",
                },
                "adjustment_metadata": "raw OHLC and adjusted close retained; adjusted OHLC derived with raw_adj_close/raw_close factor",
                "provenance_metadata": "provider attempt and canonical admission details stored in symbol acquisition JSON",
                "admitted_to_canonical_cache": source.get("final_cache_status") == "validated",
            }
        )
    return rows


def missing_session_summary(symbol: str, integrity_rows: list[dict[str, Any]]) -> tuple[int | str, str]:
    row = next(
        (item for item in integrity_rows if item.get("check_name") == "missing_session_and_coverage_gap_report_generated"),
        {},
    )
    return row.get("violation_count", ""), row.get("details", "")


def coverage_rows_v2(symbol_results: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for symbol in TARGET_SYMBOLS:
        base = coverage_row(symbol, symbol_results[symbol]["frame"], symbol_results[symbol]["source_row"])
        gap_count, gap_details = missing_session_summary(symbol, symbol_results[symbol]["integrity_rows"])
        base["missing_reference_sessions"] = gap_count
        base["coverage_gap_report"] = gap_details
        rows.append(base)
    return rows


def validated_cache_available(symbol: str) -> tuple[bool, pd.DataFrame]:
    frame = load_canonical_cache(symbol)
    if frame.empty:
        return False, frame
    dates = pd.to_datetime(frame["date"], errors="coerce")
    prices = frame[["open", "high", "low", "close", "adj_close"]].apply(pd.to_numeric, errors="coerce")
    valid = bool(
        dates.notna().all()
        and dates.is_monotonic_increasing
        and not dates.duplicated().any()
        and np.isfinite(prices.to_numpy(dtype=float)).all()
        and (prices > 0).all().all()
        and dates.max() >= REQUIRED_THROUGH_DATE
    )
    return valid, frame


def strategy_sufficiency_rows_v2() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for strategy_id, spec in STRATEGY_REQUIREMENTS.items():
        frames: dict[str, pd.DataFrame] = {}
        missing: list[str] = []
        for symbol in spec["required_symbols"]:
            available, frame = validated_cache_available(symbol)
            if not available:
                missing.append(symbol)
            else:
                frames[symbol] = frame
        common_dates: set[str] | None = None
        for frame in frames.values():
            dates = set(pd.to_datetime(frame["date"]).dt.strftime("%Y-%m-%d"))
            common_dates = dates if common_dates is None else common_dates & dates
        ordered_common = sorted(common_dates or [])
        sufficient = not missing and bool(ordered_common)
        rows.append(
            {
                "source_record_id": spec["source_record_id"],
                "proposed_strategy_id": strategy_id,
                "family_id": spec["family_id"],
                "entity_type": "source_library_record",
                "stage": "source_extracted",
                "required_symbols": spec["required_symbols"],
                "missing_or_invalid_symbols": missing,
                "common_evaluation_start": ordered_common[0] if ordered_common else "",
                "common_evaluation_end": ordered_common[-1] if ordered_common else "",
                "common_session_count": len(ordered_common),
                "data_sufficiency_outcome": "data_feasible" if sufficient else "blocked",
                "data_sufficiency_failure_reason": "" if sufficient else "data_unavailable",
                "evaluation_dates_selected_from_returns": False,
                "strategy_result_calculated": False,
            }
        )
    return rows


def select_next_action(sufficiency: list[dict[str, Any]]) -> str:
    ready = {row["proposed_strategy_id"]: row["data_sufficiency_outcome"] == "data_feasible" for row in sufficiency}
    spin_ready = ready["invesco_sp_us_spinoff_csd_v1"]
    buyback_ready = ready["nasdaq_buyback_achievers_pkw_v1"]
    if spin_ready and buyback_ready:
        return "run_deferred_structural_source_batch_v2"
    if spin_ready:
        return "run_spinoff_structural_source_exploration_v2"
    if buyback_ready:
        return "run_buyback_structural_source_exploration_v2"
    return "refresh_strategy_source_library_v3"


def benchmark_rows_v2() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for strategy_id, spec in STRATEGY_REQUIREMENTS.items():
        for control_id in spec["controls"]:
            rows.append(
                {
                    "source_record_id": spec["source_record_id"],
                    "proposed_strategy_id": strategy_id,
                    "family_id": spec["family_id"],
                    "benchmark_or_control_id": control_id,
                    "entity_type": "benchmark_reference",
                    "stage": "benchmark_reference_only",
                    "calculated_in_this_task": False,
                    "counted_as_strategy_configuration": False,
                    "counted_as_experiment_trial": False,
                }
            )
    return rows


def process_row(next_action: str, feasible_count: int) -> dict[str, Any]:
    return {
        "task_id": TASK_ID,
        "entity_type": "process_task",
        "stage": "feasibility",
        "outcome": "data_capability_complete",
        "validated_symbol_count": feasible_count,
        "exact_next_action": next_action,
        "strategy_configurations_created": 0,
        "experiment_trials_created": 0,
        "paper_demo_observations_created": 0,
    }


def all_cache_hashes() -> dict[str, str]:
    paths = {path for path in DATA_CACHE_DIR.glob("*") if path.is_file()}
    for symbol in TARGET_SYMBOLS:
        paths.add(cache_path(symbol))
        paths.add(metadata_path(symbol))
    return {rel(path): file_hash(path) for path in sorted(paths)}


def state_change_rows(
    protected_before: dict[str, str],
    protected_after: dict[str, str],
    cache_before: dict[str, str],
    cache_after: dict[str, str],
    validated_symbols: set[str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    permitted = {
        rel(path)
        for symbol in validated_symbols
        for path in (cache_path(symbol), metadata_path(symbol))
    }
    combined_before = {**protected_before, **cache_before}
    combined_after = {**protected_after, **cache_after}
    for path in sorted(set(combined_before) | set(combined_after)):
        before = combined_before.get(path, "missing")
        after = combined_after.get(path, "missing")
        file_name = Path(path).name
        symbol = file_name.split(".", 1)[0]
        metadata = read_symbol_metadata(symbol) if symbol in validated_symbols else {}
        created_by_this_task = (
            path in permitted
            and metadata.get("task_id") == TASK_ID
            and metadata.get("admitted_to_canonical_cache") is True
        )
        changed = before != after or created_by_this_task
        if created_by_this_task and before == after:
            before = "missing_before_initial_task_attempt"
        rows.append(
            {
                "path": path,
                "hash_before": before,
                "hash_after": after,
                "changed": changed,
                "change_permitted": (not changed) or path in permitted,
                "change_description": "validated_target_cache_or_metadata_admitted"
                if changed and path in permitted
                else "unchanged"
                if not changed
                else "unexpected_change",
            }
        )
    return rows


def failure_rows_v2(
    data_tasks: list[dict[str, Any]],
    sufficiency: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for task in data_tasks:
        if task["stage"] == "blocked":
            rows.append(
                {
                    "entity_id": task["symbol"],
                    "entity_type": "data_capability_task",
                    "failure_reason": task["failure_reason"],
                    "details": task["validation_outcome"],
                    "blocking": True,
                    "instrument_substitution": False,
                }
            )
    for row in sufficiency:
        if row["data_sufficiency_outcome"] == "blocked":
            rows.append(
                {
                    "entity_id": row["source_record_id"],
                    "entity_type": "source_library_record",
                    "failure_reason": row["data_sufficiency_failure_reason"],
                    "details": f"missing_or_invalid_symbols={csv_value(row['missing_or_invalid_symbols'])}",
                    "blocking": True,
                    "instrument_substitution": False,
                }
            )
    return rows


def report_text_v2(
    data_tasks: list[dict[str, Any]],
    sufficiency: list[dict[str, Any]],
    next_action: str,
) -> str:
    symbol_lines = [
        f"- `{row['symbol']}`: `{row['stage']}`; acquisition `{row['acquisition_outcome']}`; validation `{row['validation_outcome']}`."
        for row in data_tasks
    ]
    source_lines = [
        f"- `{row['proposed_strategy_id']}`: `{row['data_sufficiency_outcome']}`; common period `{row['common_evaluation_start']}` to `{row['common_evaluation_end']}`."
        for row in sufficiency
    ]
    return f"""# Deferred Structural ETF Data V2

This data-capability task investigated exactly `CSD`, `IWR`, and `PKW`. Alpaca was attempted first through the
existing read-only stock-bars endpoint. Alpaca bars were not admitted when the existing adapter lacked the raw
adjustment fields required by the canonical cache. Each symbol then received at most one bounded attempt through
the existing yfinance adjusted-daily fallback.

## Symbol Outcomes

{chr(10).join(symbol_lines)}

## Source Record Data Sufficiency

{chr(10).join(source_lines)}

Provider and acquisition metadata are stored separately from canonical OHLCV files. Raw OHLCV is not copied into
this evidence packet.

Exact next action: `{next_action}`.

No strategy configuration, experiment trial, backtest, performance metric, promotion, paper/demo observation,
broker call, order, or real-money action was created or executed.
"""


def write_artifacts_v2(
    records: list[dict[str, Any]],
    symbol_results: dict[str, dict[str, Any]],
    protected_before: dict[str, str],
    evidence_before: dict[str, str],
    cache_before: dict[str, str],
) -> dict[str, Any]:
    sufficiency = strategy_sufficiency_rows_v2()
    next_action = select_next_action(sufficiency)
    data_tasks = data_capability_rows(symbol_results, next_action)
    source_rows = source_library_rows(records)
    provider_rows = provider_attempt_rows(symbol_results)
    source_manifest = data_source_rows(symbol_results)
    coverage = coverage_rows_v2(symbol_results)
    integrity = [row for symbol in TARGET_SYMBOLS for row in symbol_results[symbol]["integrity_rows"]]
    reload_rows = []
    for symbol in TARGET_SYMBOLS:
        reload_row = reload_reconciliation_row(symbol, symbol_results[symbol]["frame"])
        interface = backtester_interface_row(symbol, symbol_results[symbol]["frame"])
        reload_rows.append({**reload_row, **interface})
        integrity.append(
            {
                "symbol": symbol,
                "check_name": "normal_backtester_data_interface_load",
                "status": "pass" if interface["normal_backtester_load_pass"] else "fail",
                "violation_count": 0 if interface["normal_backtester_load_pass"] else 1,
                "details": f"interface={interface['normal_backtester_interface']};source={interface['load_source']}",
            }
        )
    validated_symbols = {row["symbol"] for row in data_tasks if row["stage"] == "feasible"}
    protected_after = protected_hashes()
    evidence_after = prior_evidence_hashes()
    cache_after = all_cache_hashes()
    state_rows = state_change_rows(protected_before, protected_after, cache_before, cache_after, validated_symbols)
    unexpected_changes = [row["path"] for row in state_rows if row["changed"] and not row["change_permitted"]]
    failures = failure_rows_v2(data_tasks, sufficiency)
    feasible_symbol_count = len(validated_symbols)
    feasible_source_count = sum(row["data_sufficiency_outcome"] == "data_feasible" for row in sufficiency)
    benchmark_rows = benchmark_rows_v2()
    process = process_row(next_action, feasible_symbol_count)
    fallback_counts = {
        symbol: sum(
            bool(row["attempted"])
            for row in provider_rows
            if row["symbol"] == symbol and row["attempt_order"] == 2
        )
        for symbol in TARGET_SYMBOLS
    }
    consistency = {
        "task_id": TASK_ID,
        "exact_symbols_investigated": list(TARGET_SYMBOLS),
        "exactly_three_target_symbols_investigated": tuple(TARGET_SYMBOLS) == ("CSD", "IWR", "PKW"),
        "source_library_records_carried_forward": len(source_rows),
        "data_capability_tasks": len(data_tasks),
        "process_tasks": 1,
        "benchmark_references": len(benchmark_rows),
        "strategy_configurations_created": 0,
        "experiment_trials_created": 0,
        "paper_demo_observations_created": 0,
        "new_research_candidates_created": 0,
        "validated_symbol_count": feasible_symbol_count,
        "data_feasible_source_record_count": feasible_source_count,
        "fallback_attempt_count_by_symbol": fallback_counts,
        "at_most_one_fallback_attempt_per_symbol": all(count <= 1 for count in fallback_counts.values()),
        "alpaca_attempted_first_for_each_missing_symbol": all(
            any(row["attempt_order"] == 1 and bool(row["attempted"]) for row in provider_rows if row["symbol"] == symbol)
            or symbol_results[symbol]["source_row"].get("existing_cache_status_before_provider_attempt") == "current_cache_validated"
            for symbol in TARGET_SYMBOLS
        ),
        "cache_reload_all_identical": all(row["reload_identical"] for row in reload_rows if row["original_row_count"]),
        "normal_backtester_load_all_pass": all(row["normal_backtester_load_pass"] for row in reload_rows if row["expected_row_count"]),
        "all_mandatory_integrity_checks_pass_for_validated_symbols": all(
            row["status"] == "pass"
            for row in integrity
            if row["symbol"] in validated_symbols
        ),
        "protected_state_hashes_before": protected_before,
        "protected_state_hashes_after": protected_after,
        "protected_state_hashes_unchanged": protected_before == protected_after,
        "input_evidence_hashes_before": evidence_before,
        "input_evidence_hashes_after": evidence_after,
        "input_evidence_hashes_unchanged": evidence_before == evidence_after,
        "all_cache_hashes_before": cache_before,
        "all_cache_hashes_after": cache_after,
        "unexpected_state_or_cache_changes": unexpected_changes,
        "cache_changes_limited_to_validated_target_files": not unexpected_changes,
        "exact_next_action": next_action,
        **FORBIDDEN_FLAGS,
    }
    consistency["consistency_passed"] = bool(
        consistency["exactly_three_target_symbols_investigated"]
        and consistency["source_library_records_carried_forward"] == 2
        and consistency["data_capability_tasks"] == 3
        and consistency["process_tasks"] == 1
        and consistency["strategy_configurations_created"] == 0
        and consistency["experiment_trials_created"] == 0
        and consistency["paper_demo_observations_created"] == 0
        and consistency["new_research_candidates_created"] == 0
        and consistency["at_most_one_fallback_attempt_per_symbol"]
        and consistency["alpaca_attempted_first_for_each_missing_symbol"]
        and consistency["cache_reload_all_identical"]
        and consistency["normal_backtester_load_all_pass"]
        and consistency["all_mandatory_integrity_checks_pass_for_validated_symbols"]
        and consistency["protected_state_hashes_unchanged"]
        and consistency["input_evidence_hashes_unchanged"]
        and consistency["cache_changes_limited_to_validated_target_files"]
        and not any(consistency[key] for key in FORBIDDEN_FLAGS)
    )
    manifest = {
        "task_id": TASK_ID,
        "mode": "data-capability",
        "stage": "feasibility",
        "adaptation_label": "data_feasibility_adjustment",
        "target_symbols": list(TARGET_SYMBOLS),
        "required_through_date": REQUIRED_THROUGH_DATE.date().isoformat(),
        "source_library_id": SOURCE_LIBRARY_ID,
        "source_library_records_carried_forward": 2,
        "data_capability_tasks": 3,
        "process_tasks": 1,
        "benchmark_references": len(benchmark_rows),
        "strategy_configurations_created": 0,
        "experiment_trials_created": 0,
        "paper_demo_observations_created": 0,
        "new_research_candidates_created": 0,
        "exact_next_action": next_action,
    }
    outcome = {
        "task_id": TASK_ID,
        "process_outcome": "data_capability_completed",
        "symbols_investigated": len(TARGET_SYMBOLS),
        "symbols_feasible": feasible_symbol_count,
        "symbols_blocked": len(TARGET_SYMBOLS) - feasible_symbol_count,
        "source_records_carried_forward": 2,
        "source_records_data_feasible": feasible_source_count,
        "source_records_blocked": 2 - feasible_source_count,
        "strategy_configurations_created": 0,
        "experiment_trials_created": 0,
        "paper_demo_observations_created": 0,
        "new_research_candidates_created": 0,
        "exact_next_action": next_action,
    }
    action_rows = [
        {
            "scope": "project",
            "entity_id": TASK_ID,
            "exact_next_action": next_action,
            "execute_now": False,
        }
    ] + [
        {
            "scope": "source_library_record",
            "entity_id": row["source_record_id"],
            "exact_next_action": next_action,
            "execute_now": False,
        }
        for row in sufficiency
    ]

    write_yaml(OUTPUT_DIR / "task_manifest.yaml", manifest)
    write_csv(
        OUTPUT_DIR / "source_library_records.csv",
        source_rows,
        [
            "source_record_id",
            "entity_type",
            "stage",
            "proposed_strategy_id",
            "family_id",
            "display_name",
            "strategy_architecture",
            "required_instruments",
            "benchmark_or_control",
            "source_record_carried_forward",
            "counted_as_strategy_configuration",
            "counted_as_experiment_trial",
            "rules_or_mapping_changed",
        ],
    )
    write_csv(
        OUTPUT_DIR / "data_capability_task_log.csv",
        data_tasks,
        [
            "task_id",
            "parent_task_id",
            "symbol",
            "entity_type",
            "stage",
            "adaptation_label",
            "provider_attempted",
            "fallback_attempted",
            "acquisition_outcome",
            "validation_outcome",
            "failure_reason",
            "next_action",
            "cache_path",
            "counted_as_strategy_configuration",
            "counted_as_experiment_trial",
            "counted_as_paper_demo_observation",
        ],
    )
    write_csv(
        OUTPUT_DIR / "process_task_log.csv",
        [process],
        [
            "task_id",
            "entity_type",
            "stage",
            "outcome",
            "validated_symbol_count",
            "exact_next_action",
            "strategy_configurations_created",
            "experiment_trials_created",
            "paper_demo_observations_created",
        ],
    )
    write_csv(
        OUTPUT_DIR / "benchmark_reference_log.csv",
        benchmark_rows,
        [
            "source_record_id",
            "proposed_strategy_id",
            "family_id",
            "benchmark_or_control_id",
            "entity_type",
            "stage",
            "calculated_in_this_task",
            "counted_as_strategy_configuration",
            "counted_as_experiment_trial",
        ],
    )
    write_csv(
        OUTPUT_DIR / "provider_attempts.csv",
        provider_rows,
        [
            "symbol",
            "attempt_order",
            "provider_id",
            "provider_role",
            "attempted",
            "endpoint_or_library",
            "feed",
            "adjustment",
            "outcome",
            "rows_returned",
            "pagination_complete",
            "reason_not_admitted",
            "credentials_persisted",
            "account_order_or_position_endpoint_called",
        ],
    )
    write_csv(
        OUTPUT_DIR / "data_source_manifest.csv",
        source_manifest,
        [
            "symbol",
            "provider_identifier",
            "provider_role",
            "acquisition_timestamp",
            "requested_start",
            "requested_end_exclusive",
            "first_valid_date",
            "last_valid_date",
            "row_count",
            "canonical_cache_path",
            "canonical_cache_hash",
            "canonical_frame_hash",
            "metadata_path",
            "metadata_hash",
            "canonical_field_mapping",
            "adjustment_metadata",
            "provenance_metadata",
            "admitted_to_canonical_cache",
        ],
    )
    write_csv(
        OUTPUT_DIR / "data_coverage.csv",
        coverage,
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
            "missing_reference_sessions",
            "coverage_gap_report",
        ],
    )
    write_csv(
        OUTPUT_DIR / "data_integrity_checks.csv",
        integrity,
        ["symbol", "check_name", "status", "violation_count", "details"],
    )
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
            "normal_backtester_interface",
            "load_source",
            "load_status",
            "loaded_row_count",
            "expected_row_count",
            "loaded_frame_hash",
            "expected_frame_hash",
            "normal_backtester_load_pass",
        ],
    )
    write_csv(
        OUTPUT_DIR / "strategy_data_sufficiency.csv",
        sufficiency,
        [
            "source_record_id",
            "proposed_strategy_id",
            "family_id",
            "entity_type",
            "stage",
            "required_symbols",
            "missing_or_invalid_symbols",
            "common_evaluation_start",
            "common_evaluation_end",
            "common_session_count",
            "data_sufficiency_outcome",
            "data_sufficiency_failure_reason",
            "evaluation_dates_selected_from_returns",
            "strategy_result_calculated",
        ],
    )
    write_csv(
        OUTPUT_DIR / "state_change_manifest.csv",
        state_rows,
        ["path", "hash_before", "hash_after", "changed", "change_permitted", "change_description"],
    )
    write_csv(
        OUTPUT_DIR / "outcome_summary.csv",
        [outcome],
        [
            "task_id",
            "process_outcome",
            "symbols_investigated",
            "symbols_feasible",
            "symbols_blocked",
            "source_records_carried_forward",
            "source_records_data_feasible",
            "source_records_blocked",
            "strategy_configurations_created",
            "experiment_trials_created",
            "paper_demo_observations_created",
            "new_research_candidates_created",
            "exact_next_action",
        ],
    )
    write_csv(
        OUTPUT_DIR / "failure_reasons.csv",
        failures,
        ["entity_id", "entity_type", "failure_reason", "details", "blocking", "instrument_substitution"],
    )
    write_csv(
        OUTPUT_DIR / "next_actions.csv",
        action_rows,
        ["scope", "entity_id", "exact_next_action", "execute_now"],
    )
    write_json(OUTPUT_DIR / "consistency_check.json", consistency)
    write_text(OUTPUT_DIR / "data_feasibility_report.md", report_text_v2(data_tasks, sufficiency, next_action))
    return consistency


def run() -> dict[str, Any]:
    previous_manifest = read_previous_task_source_manifest()
    records = load_frozen_source_records()
    validate_frozen_specs()
    kst_consistency = json.loads(KST_CONSISTENCY_PATH.read_text(encoding="utf-8"))
    if kst_consistency.get("consistency_passed") is not True:
        raise RuntimeError("The authoritative KST lifecycle consistency input did not pass.")
    protected_before = protected_hashes()
    evidence_before = prior_evidence_hashes()
    cache_before = all_cache_hashes()
    clean_output_dir()
    symbol_results = {symbol: acquire_or_validate_symbol(symbol, previous_manifest) for symbol in TARGET_SYMBOLS}
    consistency = write_artifacts_v2(records, symbol_results, protected_before, evidence_before, cache_before)
    return {
        "task_id": TASK_ID,
        "evidence_path": rel(OUTPUT_DIR),
        "validated_symbol_count": consistency["validated_symbol_count"],
        "data_feasible_source_record_count": consistency["data_feasible_source_record_count"],
        "exact_next_action": consistency["exact_next_action"],
        "consistency_passed": consistency["consistency_passed"],
        "protected_state_hashes_unchanged": consistency["protected_state_hashes_unchanged"],
        "input_evidence_hashes_unchanged": consistency["input_evidence_hashes_unchanged"],
        "cache_changes_limited_to_validated_target_files": consistency["cache_changes_limited_to_validated_target_files"],
        "task_outcome": "deferred_structural_etf_data_capability_complete",
    }
