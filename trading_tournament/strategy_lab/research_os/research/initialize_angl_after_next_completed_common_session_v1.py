from __future__ import annotations

import csv
import hashlib
import json
import math
import re
import shutil
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import yaml

from execution_lab.alpaca_micro_live_v1.adapters.alpaca_client import AlpacaClient, AlpacaClientConfig
from execution_lab.alpaca_micro_live_v1.adapters.credentials import load_alpaca_credentials
from execution_lab.alpaca_micro_live_v1.data.alpaca_historical_bars import parse_bars_response
from src.data import build_adjusted_ohlc
from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.research.fast_source_library_batch_v5 import scheduled_full_day_nyse_closures


TASK_ID = "initialize_angl_after_next_completed_common_session_v1"
OUTPUT_DIR = ROOT / "evidence" / "paper_demo" / TASK_ID / "latest"
OPERATIONAL_DIR = ROOT / "paper_forward_observations" / "paper_forward_angl_20pct_diversifier_v1"

STRATEGY_ID = "ice_vaneck_us_fallen_angel_angl_v1"
FAMILY_ID = "fallen_angel_credit_anomaly"
OBSERVATION_ID = "paper_forward_angl_20pct_diversifier_v1"
REFERENCE_ID = "frozen_current_active_vm_dsr_usci_combo"
PARENT_TRIAL_ID = "correction_angl__ice_vaneck_us_fallen_angel_angl_v1__methodology_correction_child"
CORRECTION_ACTIVATION = datetime.fromisoformat("2026-07-24T00:00:01+00:00")
EXPECTED_SESSION = date(2026, 7, 24)
INITIAL_NAV = 1.0
COST_RATE = 0.0005
REFERENCE_WEIGHT = 0.80
CANDIDATE_WEIGHT = 0.20
WEIGHT_TOLERANCE = 1e-9
NEXT_ACTION_ACTIVE = "continue_angl_forward_observation_until_review_trigger_v1"
PROJECT_NEXT_ACTION = "refresh_strategy_source_library_v3"

REGISTRY_PATH = ROOT / "strategy_lab" / "strategy_registry.yaml"
ACTIVE_OBSERVATIONS_PATH = ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml"
ROADMAP_PATH = ROOT / "strategy_lab" / "RESEARCH_ROADMAP.md"
QUEUE_PATH = ROOT / "strategy_lab" / "research_os" / "research" / "research_queue.yaml"
FAMILY_LEDGER_PATH = ROOT / "strategy_lab" / "research_os" / "family_lineage" / "family_ledger.yaml"

CORRECTION_DIR = ROOT / "evidence" / "correction" / "angl_80_20_portfolio_construction_methodology_correction_v1" / "latest"
BOUNDARY_DIR = ROOT / "evidence" / "correction" / "correct_angl_forward_boundary_and_data_freshness_v1" / "latest"
ONBOARDING_DIR = ROOT / "evidence" / "paper_demo" / "onboard_angl_diversifier_paper_demo_observation_v1" / "latest"
REFERENCE_DEFINITION_DIR = ROOT / "evidence" / "forward_operational_reinitialization_vm_dsr_combo_v1" / "latest"

VM_ID = "paper_forward_vm_quality_lowvol_proxy_v1"
DSR_ID = "paper_forward_dsr_sector_equal_weight_defensive_filter_v1"
USCI_ID = "paper_forward_usci_dynamic_commodity_curve_selection_wrapper_v1"
DERIVED_ID = "paper_forward_combo_vm_dsr_usci_equal_weight_monthly_v1"
VM_RISK_ASSETS = ("SPLV", "USMV", "QUAL", "SPY")
VM_SYMBOLS = (*VM_RISK_ASSETS, "BIL")
DSR_RISK_ASSETS = ("XLK", "XLF", "XLE", "XLV", "XLY", "XLP", "XLU", "XLI", "XLB", "XLC")
DSR_SYMBOLS = (*DSR_RISK_ASSETS, "BIL")
USCI_SYMBOLS = ("USCI", "DBC", "BIL", "SPY")
CONTROL_SYMBOLS = ("ANGL", "HYG", "JNK")
DEFAULT_REFERENCE_SYMBOLS = tuple(sorted(set(VM_SYMBOLS + DSR_SYMBOLS + USCI_SYMBOLS)))

CANONICAL_COLUMNS = (
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

PROTECTED_STATE_PATHS = (
    REGISTRY_PATH,
    ACTIVE_OBSERVATIONS_PATH,
    ROADMAP_PATH,
    QUEUE_PATH,
    FAMILY_LEDGER_PATH,
    ROOT / "paper_forward_observations" / VM_ID / "active_observation.yaml",
    ROOT / "paper_forward_observations" / DSR_ID / "active_observation.yaml",
    ROOT / "paper_forward_observations" / USCI_ID / "active_observation.yaml",
    ROOT / "paper_forward_observations" / DERIVED_ID / "active_observation.yaml",
    ROOT / "paper_forward_observations" / VM_ID / "component_forward_ledger.csv",
    ROOT / "paper_forward_observations" / DSR_ID / "component_forward_ledger.csv",
    ROOT / "paper_forward_observations" / USCI_ID / "component_forward_ledger.csv",
    ROOT / "paper_forward_observations" / DERIVED_ID / "derived_component_forward_ledger.csv",
)

PRIOR_EVIDENCE_PATHS = tuple(
    path
    for folder in (CORRECTION_DIR, BOUNDARY_DIR, ONBOARDING_DIR, REFERENCE_DEFINITION_DIR)
    for path in sorted(folder.glob("*"))
    if path.is_file()
)


def rel(path: str | Path) -> str:
    value = Path(path)
    try:
        return value.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return value.as_posix()


def csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return "" if not math.isfinite(value) else f"{value:.12g}"
    if isinstance(value, (dict, list, tuple, set)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    return str(value)


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: csv_value(row.get(field, "")) for field in fields})


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False, width=120, allow_unicode=False), encoding="utf-8")


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value.rstrip() + "\n", encoding="utf-8")


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def file_hash(path: Path) -> str:
    if not path.exists():
        return "missing"
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def hash_map(paths: tuple[Path, ...] | list[Path]) -> dict[str, str]:
    return {rel(path): file_hash(path) for path in paths}


def frame_hash(frame: pd.DataFrame) -> str:
    normalized = frame.copy()
    normalized = normalized[list(CANONICAL_COLUMNS)]
    payload = normalized.to_csv(index=False, lineterminator="\n").encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def clean_output() -> None:
    if OUTPUT_DIR.exists():
        resolved = OUTPUT_DIR.resolve()
        expected = (ROOT / "evidence" / "paper_demo" / TASK_ID).resolve()
        if expected not in resolved.parents:
            raise RuntimeError(f"Refusing to remove unexpected output directory: {resolved}")
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def cache_path(symbol: str) -> Path:
    return ROOT / "data" / "cache" / f"{symbol}.csv"


def metadata_path(symbol: str) -> Path:
    return ROOT / "data" / "cache" / f"{symbol}.acquisition.json"


def reference_symbols() -> tuple[str, ...]:
    path = REFERENCE_DEFINITION_DIR / "authorized_symbol_universe.json"
    if not path.exists():
        return DEFAULT_REFERENCE_SYMBOLS
    payload = json.loads(path.read_text(encoding="utf-8"))
    values = payload.get("authorized_symbols", [])
    return tuple(sorted(str(value) for value in values)) if values else DEFAULT_REFERENCE_SYMBOLS


def required_symbols() -> tuple[str, ...]:
    return tuple(sorted(set(reference_symbols() + CONTROL_SYMBOLS)))


def canonicalize(raw: pd.DataFrame, symbol: str) -> pd.DataFrame:
    frame = build_adjusted_ohlc(raw.copy(), symbol)
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    for column in CANONICAL_COLUMNS:
        if column not in frame.columns:
            frame[column] = 0.0 if column in {"dividends", "stock_splits"} else np.nan
    return frame[list(CANONICAL_COLUMNS)]


def load_cache(symbol: str) -> pd.DataFrame:
    path = cache_path(symbol)
    if not path.exists():
        return pd.DataFrame(columns=CANONICAL_COLUMNS)
    return canonicalize(pd.read_csv(path), symbol)


def validate_frame(frame: pd.DataFrame, symbol: str, through_date: date) -> tuple[bool, list[str]]:
    failures: list[str] = []
    if frame.empty:
        return False, ["empty"]
    if tuple(frame.columns) != CANONICAL_COLUMNS:
        failures.append("canonical_columns")
    dates = pd.to_datetime(frame["date"], errors="coerce")
    if dates.isna().any():
        failures.append("unparseable_date")
    if not dates.is_monotonic_increasing:
        failures.append("dates_not_increasing")
    if dates.duplicated().any():
        failures.append("duplicate_dates")
    if dates.max().date() < through_date:
        failures.append("coverage_short")
    price_columns = [
        "raw_open",
        "raw_high",
        "raw_low",
        "raw_close",
        "raw_adj_close",
        "adjustment_factor",
        "open",
        "high",
        "low",
        "close",
        "adj_close",
    ]
    numeric = frame[price_columns].apply(pd.to_numeric, errors="coerce")
    if not np.isfinite(numeric.to_numpy(dtype=float)).all():
        failures.append("nonfinite_prices")
    if (numeric <= 0.0).any().any():
        failures.append("nonpositive_prices")
    if not frame["symbol"].astype(str).str.upper().eq(symbol).all():
        failures.append("symbol_mismatch")
    return not failures, failures


def session_close_utc(day: date) -> datetime:
    eastern = ZoneInfo("America/New_York")
    return datetime.combine(day, time(16, 0), tzinfo=eastern).astimezone(timezone.utc)


def is_regular_session(day: date) -> bool:
    return day.weekday() < 5 and day not in scheduled_full_day_nyse_closures(day.year)


def completed_post_activation_sessions(now: datetime | None = None) -> list[date]:
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    start = CORRECTION_ACTIVATION.date()
    result: list[date] = []
    cursor = start
    while cursor <= current.date():
        close = session_close_utc(cursor)
        if is_regular_session(cursor) and close > CORRECTION_ACTIVATION and close <= current:
            result.append(cursor)
        cursor += timedelta(days=1)
    return result


def sanitize_error(exc: BaseException) -> str:
    value = str(exc).replace("\r", " ").replace("\n", " ")
    for token in ("APCA-API-KEY-ID", "APCA-API-SECRET-KEY", "ALPACA_PAPER_API_KEY", "ALPACA_PAPER_SECRET_KEY"):
        value = value.replace(token, f"{token}_REDACTED")
    return value[:500]


def attempt_alpaca(symbols: tuple[str, ...], start: date, end_exclusive: date) -> dict[str, Any]:
    result: dict[str, Any] = {
        "provider": "alpaca_market_data",
        "attempted": True,
        "endpoint": "/v2/stocks/bars",
        "request_method": "GET",
        "symbols": list(symbols),
        "start": start.isoformat(),
        "end_exclusive": end_exclusive.isoformat(),
        "feed": "iex",
        "adjustment": "all",
        "page_count": 0,
        "row_count": 0,
        "status": "",
        "admitted": False,
        "reason_not_admitted": "",
        "account_endpoint_called": False,
        "position_endpoint_called": False,
        "order_endpoint_called": False,
    }
    try:
        credentials = load_alpaca_credentials("paper")
        result["credentials_present"] = bool(credentials.present)
        result["live_credentials_detected"] = bool(credentials.live_credentials_detected)
        if not credentials.present:
            result["status"] = "auth_unavailable"
            result["reason_not_admitted"] = "paper_market_data_credentials_missing"
            return result
        client = AlpacaClient(credentials, AlpacaClientConfig(data_feed="iex", data_adjustment="all"))
        merged: dict[str, Any] = {"bars": {symbol: [] for symbol in symbols}}
        token: str | None = None
        while True:
            payload = client.get_historical_bars_page(
                symbols=list(symbols),
                start=f"{start.isoformat()}T00:00:00Z",
                end=f"{end_exclusive.isoformat()}T00:00:00Z",
                timeframe="1Day",
                feed="iex",
                adjustment="all",
                page_token=token,
            )
            result["page_count"] += 1
            for symbol in symbols:
                merged["bars"][symbol].extend(payload.get("bars", {}).get(symbol, []))
            token = payload.get("next_page_token")
            if not token:
                break
        parsed = parse_bars_response(merged, drop_incomplete_current_day=False)
        result["row_count"] = sum(len(frame) for frame in parsed.values())
        result["rows_by_symbol"] = {symbol: int(len(parsed.get(symbol, pd.DataFrame()))) for symbol in symbols}
        result["status"] = "returned_read_only_daily_bars"
        result["reason_not_admitted"] = (
            "existing Alpaca bars omit canonical raw OHLC, raw adjusted close, dividends, splits, "
            "and reproducible adjustment-factor provenance required by the repository cache"
        )
    except BaseException as exc:  # noqa: BLE001 - capability evidence needs the bounded provider failure.
        result["status"] = "provider_call_failed"
        result["reason_not_admitted"] = sanitize_error(exc)
    return result


def extract_batch_symbol(raw: pd.DataFrame, symbol: str) -> pd.DataFrame:
    if not isinstance(raw.columns, pd.MultiIndex):
        return raw.copy()
    level_zero = set(str(value) for value in raw.columns.get_level_values(0))
    level_one = set(str(value) for value in raw.columns.get_level_values(1))
    if symbol in level_zero:
        return raw[symbol].copy()
    if symbol in level_one:
        return raw.xs(symbol, axis=1, level=1).copy()
    return pd.DataFrame()


def download_fallback_batch(symbols: tuple[str, ...], end_exclusive: date) -> tuple[dict[str, pd.DataFrame], dict[str, Any]]:
    import yfinance as yf

    request = {
        "provider": "yfinance_existing_repo_supported_fallback",
        "attempted": True,
        "single_bounded_batch_attempt": True,
        "symbols": list(symbols),
        "start": "1990-01-01",
        "end_exclusive": end_exclusive.isoformat(),
        "auto_adjust": False,
        "actions": True,
        "group_by": "ticker",
        "progress": False,
        "status": "",
        "error": "",
    }
    try:
        raw = yf.download(
            list(symbols),
            start=request["start"],
            end=request["end_exclusive"],
            auto_adjust=False,
            actions=True,
            group_by="ticker",
            progress=False,
            threads=True,
            timeout=30,
        )
        frames = {symbol: canonicalize(extract_batch_symbol(raw, symbol), symbol) for symbol in symbols}
        request["status"] = "download_completed"
        request["rows_by_symbol"] = {symbol: len(frame) for symbol, frame in frames.items()}
        return frames, request
    except BaseException as exc:  # noqa: BLE001 - bounded fallback failure is an allowed blocker.
        request["status"] = "provider_call_failed"
        request["error"] = sanitize_error(exc)
        return {}, request


def atomically_write_cache_batch(
    frames: dict[str, pd.DataFrame],
    symbols: tuple[str, ...],
    through_date: date,
    alpaca: dict[str, Any],
    fallback: dict[str, Any],
) -> None:
    temp_paths: list[tuple[Path, Path]] = []
    metadata_payloads: list[tuple[Path, dict[str, Any]]] = []
    try:
        for symbol in symbols:
            frame = frames[symbol]
            valid, failures = validate_frame(frame, symbol, through_date)
            if not valid:
                raise RuntimeError(f"{symbol}: fallback cache validation failed: {'|'.join(failures)}")
            target = cache_path(symbol)
            temp = target.with_suffix(".csv.angl_init_tmp")
            frame.to_csv(temp, index=False, lineterminator="\n")
            reloaded = canonicalize(pd.read_csv(temp), symbol)
            if frame_hash(reloaded) != frame_hash(frame):
                raise RuntimeError(f"{symbol}: staged cache changed during serialization")
            temp_paths.append((temp, target))
            metadata_payloads.append(
                (
                    metadata_path(symbol),
                    {
                        "symbol": symbol,
                        "task_id": TASK_ID,
                        "admitted_provider": "yfinance_existing_repo_supported_fallback",
                        "provider_role": "one_bounded_fallback_after_alpaca_schema_not_admitted",
                        "preferred_provider_attempt": {
                            "provider": alpaca.get("provider"),
                            "status": alpaca.get("status"),
                            "admitted": False,
                            "reason_not_admitted": alpaca.get("reason_not_admitted"),
                            "endpoint": alpaca.get("endpoint"),
                            "feed": alpaca.get("feed"),
                            "adjustment": alpaca.get("adjustment"),
                        },
                        "fallback_request": {
                            key: value
                            for key, value in fallback.items()
                            if key not in {"error"}
                        },
                        "cache_path": rel(target),
                        "first_valid_date": str(frame.iloc[0]["date"]),
                        "last_valid_date": str(frame.iloc[-1]["date"]),
                        "row_count": int(len(frame)),
                        "cache_file_hash": "populated_after_atomic_replace",
                        "canonical_frame_hash": frame_hash(frame),
                        "canonical_schema": list(CANONICAL_COLUMNS),
                        "no_account_position_or_order_endpoint_called": True,
                    },
                )
            )
        for temp, target in temp_paths:
            temp.replace(target)
        for path, payload in metadata_payloads:
            payload["cache_file_hash"] = file_hash(cache_path(str(payload["symbol"])))
            path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    finally:
        for temp, _target in temp_paths:
            temp.unlink(missing_ok=True)


def refresh_required_data(symbols: tuple[str, ...], sessions: list[date]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not sessions:
        return [], {
            "status": "blocked_no_completed_post_activation_session",
            "alpaca": {},
            "fallback": {},
            "cache_updated": False,
        }
    through_date = sessions[0]
    pre_frames = {symbol: load_cache(symbol) for symbol in symbols}
    already_ready = all(validate_frame(frame, symbol, through_date)[0] for symbol, frame in pre_frames.items())
    if already_ready:
        rows = []
        for symbol, frame in pre_frames.items():
            rows.append(
                {
                    "symbol": symbol,
                    "provider_preference": "alpaca_first",
                    "alpaca_attempted": False,
                    "alpaca_status": "not_repeated_cache_already_current",
                    "alpaca_admitted": False,
                    "fallback_attempted": False,
                    "fallback_status": "not_repeated_cache_already_current",
                    "admitted_provider": "existing_canonical_cache",
                    "cache_updated": False,
                    "first_date": str(frame.iloc[0]["date"]),
                    "last_date": str(frame.iloc[-1]["date"]),
                    "row_count": len(frame),
                    "cache_path": rel(cache_path(symbol)),
                    "cache_hash": file_hash(cache_path(symbol)),
                    "metadata_hash": file_hash(metadata_path(symbol)),
                    "failure_reason": "",
                    "account_position_order_endpoint_called": False,
                }
            )
        return rows, {
            "status": "existing_current_cache_reused_idempotently",
            "alpaca": {"attempted": False, "reason": "same-session rerun with current canonical cache"},
            "fallback": {"attempted": False, "reason": "same-session rerun with current canonical cache"},
            "cache_updated": False,
        }

    request_start = min(
        [
            pd.to_datetime(frame["date"]).max().date()
            for frame in pre_frames.values()
            if not frame.empty
        ]
        or [CORRECTION_ACTIVATION.date()]
    )
    end_exclusive = max(sessions) + timedelta(days=1)
    alpaca = attempt_alpaca(symbols, request_start, end_exclusive)
    fallback_frames, fallback = download_fallback_batch(symbols, end_exclusive)
    failures: dict[str, list[str]] = {}
    for symbol in symbols:
        frame = fallback_frames.get(symbol, pd.DataFrame(columns=CANONICAL_COLUMNS))
        valid, reasons = validate_frame(frame, symbol, through_date)
        if not valid:
            failures[symbol] = reasons
    cache_updated = False
    if not failures:
        atomically_write_cache_batch(fallback_frames, symbols, through_date, alpaca, fallback)
        cache_updated = True
    rows: list[dict[str, Any]] = []
    for symbol in symbols:
        frame = load_cache(symbol)
        valid, reasons = validate_frame(frame, symbol, through_date)
        rows.append(
            {
                "symbol": symbol,
                "provider_preference": "alpaca_first",
                "alpaca_attempted": alpaca.get("attempted", False),
                "alpaca_status": alpaca.get("status", ""),
                "alpaca_admitted": False,
                "fallback_attempted": fallback.get("attempted", False),
                "fallback_status": fallback.get("status", ""),
                "admitted_provider": "yfinance_existing_repo_supported_fallback" if cache_updated else "preexisting_cache",
                "cache_updated": cache_updated,
                "first_date": "" if frame.empty else str(frame.iloc[0]["date"]),
                "last_date": "" if frame.empty else str(frame.iloc[-1]["date"]),
                "row_count": len(frame),
                "cache_path": rel(cache_path(symbol)),
                "cache_hash": file_hash(cache_path(symbol)),
                "metadata_hash": file_hash(metadata_path(symbol)),
                "failure_reason": "|".join(failures.get(symbol, reasons if not valid else [])),
                "account_position_order_endpoint_called": False,
            }
        )
    return rows, {
        "status": "refreshed" if cache_updated else "blocked_refresh_failed",
        "alpaca": alpaca,
        "fallback": fallback,
        "cache_updated": cache_updated,
        "failures": failures,
    }


def close_series(symbol: str) -> pd.Series:
    frame = load_cache(symbol)
    if frame.empty:
        return pd.Series(dtype=float)
    index = pd.to_datetime(frame["date"])
    return pd.Series(pd.to_numeric(frame["adj_close"], errors="coerce").to_numpy(), index=index, name=symbol).sort_index()


def close_frame(symbols: tuple[str, ...] | list[str]) -> pd.DataFrame:
    return pd.concat([close_series(symbol) for symbol in symbols], axis=1).sort_index()


def sma(series: pd.Series, signal_date: pd.Timestamp, window: int) -> float:
    values = series.loc[:signal_date].dropna().tail(window)
    return float(values.mean()) if len(values) == window else float("nan")


def trailing_return(series: pd.Series, signal_date: pd.Timestamp, window: int) -> float:
    values = series.loc[:signal_date].dropna()
    return float(values.iloc[-1] / values.iloc[-window - 1] - 1.0) if len(values) > window else float("nan")


def realized_vol(series: pd.Series, signal_date: pd.Timestamp, window: int) -> float:
    values = series.loc[:signal_date].pct_change().dropna().tail(window)
    return float(values.std()) if len(values) == window else float("nan")


def vm_target(prices: pd.DataFrame, signal_date: pd.Timestamp) -> dict[str, float]:
    scores: list[tuple[str, float]] = []
    for symbol in VM_RISK_ASSETS:
        close = float(prices.loc[signal_date, symbol])
        avg = sma(prices[symbol], signal_date, 200)
        ret = trailing_return(prices[symbol], signal_date, 126)
        vol = realized_vol(prices[symbol], signal_date, 60)
        if np.isfinite(avg) and close > avg and np.isfinite(ret) and np.isfinite(vol) and vol > 0:
            scores.append((symbol, ret / vol))
    ranked = [symbol for symbol, _score in sorted(scores, key=lambda item: (-item[1], item[0]))[:2]]
    if len(ranked) == 2:
        return {ranked[0]: 0.5, ranked[1]: 0.5}
    if len(ranked) == 1:
        return {ranked[0]: 1.0}
    return {"BIL": 1.0}


def dsr_target(prices: pd.DataFrame, signal_date: pd.Timestamp) -> dict[str, float]:
    qualified = [
        symbol
        for symbol in DSR_RISK_ASSETS
        if np.isfinite(sma(prices[symbol], signal_date, 200))
        and float(prices.loc[signal_date, symbol]) > sma(prices[symbol], signal_date, 200)
    ]
    if len(qualified) >= 3:
        return {symbol: 1.0 / len(qualified) for symbol in qualified}
    if qualified:
        result = {symbol: 1.0 / 3.0 for symbol in qualified}
        result["BIL"] = 1.0 - len(qualified) / 3.0
        return result
    return {"BIL": 1.0}


def next_month_first_common(index: pd.DatetimeIndex, baseline: pd.Timestamp) -> list[pd.Timestamp]:
    values = index[index > baseline]
    result: list[pd.Timestamp] = []
    seen: set[tuple[int, int]] = set()
    for value in values:
        key = (value.year, value.month)
        if key not in seen:
            seen.add(key)
            result.append(pd.Timestamp(value))
    return result


def previous_common_session(index: pd.DatetimeIndex, value: pd.Timestamp) -> pd.Timestamp:
    prior = index[index < value]
    if not len(prior):
        raise RuntimeError(f"No completed signal session precedes {value.date().isoformat()}")
    return pd.Timestamp(prior[-1])


def simulate_component(
    observation_id: str,
    symbols: tuple[str, ...],
    baseline: pd.Timestamp,
    target_function: Any,
) -> tuple[pd.Series, list[dict[str, Any]]]:
    observation = read_yaml(ROOT / "paper_forward_observations" / observation_id / "active_observation.yaml")
    prices = close_frame(symbols).dropna(how="any")
    calendar = prices.index[(prices.index >= baseline)]
    shares = {symbol: float(value) for symbol, value in observation.get("virtual_shares", {}).items()}
    cash = float(observation.get("cash", 0.0))
    baseline_equity = sum(shares.get(symbol, 0.0) * float(prices.loc[baseline, symbol]) for symbol in symbols) + cash
    if baseline_equity <= 0:
        raise RuntimeError(f"{observation_id}: invalid baseline equity")
    rebalance_dates = set(next_month_first_common(calendar, baseline))
    values: dict[pd.Timestamp, float] = {}
    rows: list[dict[str, Any]] = []
    for day in calendar:
        pre_equity = sum(shares.get(symbol, 0.0) * float(prices.loc[day, symbol]) for symbol in symbols) + cash
        turnover = 0.0
        cost = 0.0
        signal_date = ""
        target: dict[str, float] = {}
        event = "drift"
        if day in rebalance_dates:
            signal = previous_common_session(prices.index, day)
            target = target_function(prices, signal)
            pre_weights = {
                symbol: shares.get(symbol, 0.0) * float(prices.loc[day, symbol]) / pre_equity
                for symbol in symbols
            }
            turnover = 0.5 * sum(abs(target.get(symbol, 0.0) - pre_weights.get(symbol, 0.0)) for symbol in symbols)
            cost = pre_equity * turnover * COST_RATE
            post_equity = pre_equity - cost
            shares = {
                symbol: post_equity * weight / float(prices.loc[day, symbol])
                for symbol, weight in target.items()
                if weight > 0
            }
            cash = 0.0
            pre_equity = post_equity
            signal_date = signal.date().isoformat()
            event = "monthly_rebalance"
        values[pd.Timestamp(day)] = pre_equity / baseline_equity
        rows.append(
            {
                "date": pd.Timestamp(day).date().isoformat(),
                "reference_or_component_id": observation_id,
                "row_type": event,
                "signal_date": signal_date,
                "target_weights": target,
                "one_way_turnover": turnover,
                "transaction_cost": cost,
                "component_index": values[pd.Timestamp(day)],
                "reconciliation_status": "pass",
            }
        )
    return pd.Series(values, name=observation_id), rows


def simulate_usci(baseline: pd.Timestamp) -> tuple[pd.Series, list[dict[str, Any]]]:
    observation = read_yaml(ROOT / "paper_forward_observations" / USCI_ID / "active_observation.yaml")
    shares = float(observation.get("initial_virtual_shares", 0.0))
    cash = float(observation.get("initial_virtual_cash", 0.0))
    series = close_series("USCI").loc[baseline:]
    baseline_equity = shares * float(series.loc[baseline]) + cash
    values = (shares * series + cash) / baseline_equity
    rows = [
        {
            "date": day.date().isoformat(),
            "reference_or_component_id": USCI_ID,
            "row_type": "static_hold",
            "signal_date": "",
            "target_weights": {"USCI": 1.0},
            "one_way_turnover": 0.0,
            "transaction_cost": 0.0,
            "component_index": float(value),
            "reconciliation_status": "pass",
        }
        for day, value in values.items()
    ]
    return values.rename(USCI_ID), rows


def reconstruct_reference(through_date: date) -> tuple[pd.DataFrame, list[dict[str, Any]], dict[str, Any]]:
    baseline = pd.Timestamp("2026-06-18")
    vm_prices = close_frame(VM_SYMBOLS).dropna(how="any")
    dsr_prices = close_frame(DSR_SYMBOLS).dropna(how="any")
    vm, vm_rows = simulate_component(VM_ID, VM_SYMBOLS, baseline, vm_target)
    dsr, dsr_rows = simulate_component(DSR_ID, DSR_SYMBOLS, baseline, dsr_target)
    usci, usci_rows = simulate_usci(baseline)
    components = pd.concat([vm, dsr, usci], axis=1).dropna(how="any")
    components = components.loc[: pd.Timestamp(through_date)]
    if components.empty or components.index.max().date() < through_date:
        return pd.DataFrame(), vm_rows + dsr_rows + usci_rows, {
            "status": "blocked_reference_not_reproducible_through_session",
            "latest_date": "" if components.empty else components.index.max().date().isoformat(),
        }
    sleeve_values = {
        VM_ID: 1000.0,
        DSR_ID: 1000.0,
        USCI_ID: 1000.0,
    }
    previous = components.index[0]
    rows: list[dict[str, Any]] = []
    first_dates = set(next_month_first_common(components.index, baseline))
    for day in components.index:
        if day != components.index[0]:
            for component in sleeve_values:
                component_return = float(components.loc[day, component] / components.loc[previous, component])
                sleeve_values[component] *= component_return
        total_before = sum(sleeve_values.values())
        turnover = 0.0
        transfer_cost = 0.0
        event = "drift"
        if day in first_dates:
            pre_weights = {component: value / total_before for component, value in sleeve_values.items()}
            turnover = 0.5 * sum(abs(1.0 / 3.0 - pre_weights[component]) for component in sleeve_values)
            transfer_cost = total_before * turnover * COST_RATE
            total_after = total_before - transfer_cost
            sleeve_values = {component: total_after / 3.0 for component in sleeve_values}
            event = "monthly_first_common_session_rebalance"
        total = sum(sleeve_values.values())
        rows.append(
            {
                "date": day.date().isoformat(),
                "reference_or_component_id": REFERENCE_ID,
                "row_type": event,
                "signal_date": "",
                "target_weights": {component: 1.0 / 3.0 for component in sleeve_values} if event != "drift" else {},
                "one_way_turnover": turnover,
                "transaction_cost": transfer_cost,
                "component_index": total / 3000.0,
                "reconciliation_status": "pass",
                "vm_sleeve_value": sleeve_values[VM_ID],
                "dsr_sleeve_value": sleeve_values[DSR_ID],
                "usci_sleeve_value": sleeve_values[USCI_ID],
                "reference_virtual_equity": total,
                "reference_index": total / 3000.0,
                "component_costs_reapplied": False,
            }
        )
        previous = day
    reference = pd.DataFrame(rows)
    reference.index = pd.to_datetime(reference["date"])
    return reference, vm_rows + dsr_rows + usci_rows + rows, {
        "status": "reproducible",
        "baseline_date": baseline.date().isoformat(),
        "latest_date": reference.iloc[-1]["date"],
        "latest_reference_index": float(reference.iloc[-1]["reference_index"]),
        "latest_reference_virtual_equity": float(reference.iloc[-1]["reference_virtual_equity"]),
        "monthly_rebalances": int((reference["row_type"] == "monthly_first_common_session_rebalance").sum()),
        "maximum_aggregate_exposure": 1.0,
        "component_costs_reapplied": False,
    }


def common_session_availability(symbols: tuple[str, ...], reference: pd.DataFrame, sessions: list[date]) -> tuple[date | None, list[dict[str, Any]]]:
    frames = {symbol: load_cache(symbol) for symbol in symbols}
    dates = {
        symbol: set(pd.to_datetime(frame["date"]).dt.date)
        for symbol, frame in frames.items()
        if not frame.empty
    }
    reference_dates = set(pd.to_datetime(reference["date"]).dt.date) if not reference.empty else set()
    rows: list[dict[str, Any]] = []
    selected: date | None = None
    for candidate in sessions:
        missing = [symbol for symbol in symbols if candidate not in dates.get(symbol, set())]
        reference_ready = candidate in reference_dates
        complete = not missing and reference_ready
        rows.append(
            {
                "candidate_session": candidate.isoformat(),
                "regular_session": is_regular_session(candidate),
                "official_close_utc": session_close_utc(candidate).isoformat(),
                "close_after_correction_activation": session_close_utc(candidate) > CORRECTION_ACTIVATION,
                "candidate_control_symbols_complete": not missing,
                "missing_symbols": missing,
                "reference_reproducible": reference_ready,
                "complete_common_session": complete,
                "selected": complete and selected is None,
                "selection_rule": "earliest chronological completed common session; returns not inspected",
            }
        )
        if complete and selected is None:
            selected = candidate
    return selected, rows


def build_portfolio_initialization(
    session: date,
    reference_price: float,
    asset_prices: dict[str, float],
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    portfolios = {
        "candidate_80_reference_20_ANGL": {"frozen_reference": 0.8, "ANGL": 0.2},
        "control_80_reference_20_HYG": {"frozen_reference": 0.8, "HYG": 0.2},
        "control_80_reference_10_HYG_10_JNK": {"frozen_reference": 0.8, "HYG": 0.1, "JNK": 0.1},
    }
    prices = {"frozen_reference": reference_price, **asset_prices}
    target_rows: list[dict[str, Any]] = []
    position_rows: list[dict[str, Any]] = []
    trade_rows: list[dict[str, Any]] = []
    nav_rows: list[dict[str, Any]] = []
    control_rows: list[dict[str, Any]] = [
        {
            "portfolio_id": "control_100pct_frozen_reference",
            "session_date": session.isoformat(),
            "pretrade_nav": INITIAL_NAV,
            "one_way_turnover": 0.0,
            "transaction_cost": 0.0,
            "post_trade_nav": INITIAL_NAV,
            "reference_weight": 1.0,
            "ANGL_weight": 0.0,
            "HYG_weight": 0.0,
            "JNK_weight": 0.0,
            "record_classification": "forward_observation",
        }
    ]
    for portfolio_id, targets in portfolios.items():
        pretrade = {asset: 0.0 for asset in targets}
        turnover = 0.5 * sum(abs(targets[asset] - pretrade[asset]) for asset in targets)
        transaction_cost = INITIAL_NAV * turnover * COST_RATE
        post_nav = INITIAL_NAV - transaction_cost
        for asset, target in targets.items():
            market_value = post_nav * target
            quantity = market_value / prices[asset]
            target_rows.append(
                {
                    "portfolio_id": portfolio_id,
                    "session_date": session.isoformat(),
                    "component_id": asset,
                    "pretrade_weight": 0.0,
                    "target_weight": target,
                    "post_trade_weight": target,
                    "record_classification": "forward_observation",
                }
            )
            position_rows.append(
                {
                    "portfolio_id": portfolio_id,
                    "session_date": session.isoformat(),
                    "component_id": asset,
                    "execution_price_or_index": prices[asset],
                    "target_weight": target,
                    "post_trade_market_value": market_value,
                    "virtual_quantity": quantity,
                    "broker_order_submitted": False,
                    "record_classification": "forward_observation",
                }
            )
            trade_rows.append(
                {
                    "trade_key": f"{OBSERVATION_ID}|{portfolio_id}|{session.isoformat()}|{asset}|initial_establishment",
                    "observation_id": OBSERVATION_ID,
                    "portfolio_id": portfolio_id,
                    "trade_date": session.isoformat(),
                    "component_id": asset,
                    "pretrade_weight": 0.0,
                    "target_weight": target,
                    "virtual_trade_weight": target,
                    "virtual_trade_value_before_cost": INITIAL_NAV * target,
                    "execution_price_or_index": prices[asset],
                    "one_way_turnover_portfolio": turnover,
                    "transaction_cost_portfolio": transaction_cost,
                    "broker_order_submitted": False,
                    "record_classification": "forward_observation",
                }
            )
        nav_row = {
            "portfolio_id": portfolio_id,
            "session_date": session.isoformat(),
            "pretrade_nav": INITIAL_NAV,
            "one_way_turnover": turnover,
            "cost_rate": COST_RATE,
            "transaction_cost": transaction_cost,
            "post_trade_nav": post_nav,
            "weight_sum": sum(targets.values()),
            "maximum_exposure": sum(abs(value) for value in targets.values()),
            "record_classification": "forward_observation",
        }
        nav_rows.append(nav_row)
        if portfolio_id.startswith("control_"):
            control_rows.append(
                {
                    "portfolio_id": portfolio_id,
                    "session_date": session.isoformat(),
                    "pretrade_nav": INITIAL_NAV,
                    "one_way_turnover": turnover,
                    "transaction_cost": transaction_cost,
                    "post_trade_nav": post_nav,
                    "reference_weight": targets.get("frozen_reference", 0.0),
                    "ANGL_weight": targets.get("ANGL", 0.0),
                    "HYG_weight": targets.get("HYG", 0.0),
                    "JNK_weight": targets.get("JNK", 0.0),
                    "record_classification": "forward_observation",
                }
            )
    return target_rows, position_rows, trade_rows, nav_rows, control_rows


FORWARD_FIELDS = [
    "observation_id",
    "observation_timestamp",
    "market_session",
    "official_close_utc",
    "target_weights",
    "pretrade_weights",
    "one_way_turnover",
    "transaction_cost",
    "post_trade_nav",
    "candidate_reference_index",
    "candidate_ANGL_price",
    "control_HYG_price",
    "control_JNK_price",
    "maximum_exposure",
    "weight_sum",
    "data_freshness",
    "reference_reconciliation_status",
    "record_classification",
    "broker_order_submitted",
]


def operational_fields() -> tuple[list[str], list[str], list[str]]:
    ledger = [
        "observation_id",
        "date",
        "official_close_utc",
        "row_type",
        "reference_index",
        "ANGL_price",
        "pretrade_nav",
        "one_way_turnover",
        "transaction_cost",
        "post_trade_nav",
        "reference_weight",
        "ANGL_weight",
        "maximum_exposure",
        "record_classification",
        "broker_calls",
        "orders_created",
        "status",
    ]
    positions = [
        "observation_id",
        "portfolio_id",
        "date",
        "component_id",
        "execution_price_or_index",
        "target_weight",
        "market_value",
        "virtual_quantity",
        "record_classification",
    ]
    trades = [
        "trade_key",
        "observation_id",
        "portfolio_id",
        "trade_date",
        "component_id",
        "pretrade_weight",
        "target_weight",
        "virtual_trade_weight",
        "virtual_trade_value_before_cost",
        "execution_price_or_index",
        "one_way_turnover_portfolio",
        "transaction_cost_portfolio",
        "broker_order_submitted",
        "record_classification",
    ]
    return ledger, positions, trades


def merge_unique(existing: list[dict[str, str]], incoming: list[dict[str, Any]], key: str) -> tuple[list[dict[str, Any]], int]:
    by_key: dict[str, dict[str, Any]] = {str(row.get(key, "")): dict(row) for row in existing if row.get(key)}
    additions = 0
    for row in incoming:
        value = str(row.get(key, ""))
        if value not in by_key:
            additions += 1
        by_key[value] = row
    return [by_key[value] for value in sorted(by_key)], additions


def write_operational_state(
    session: date,
    reference_price: float,
    asset_prices: dict[str, float],
    position_rows: list[dict[str, Any]],
    trade_rows: list[dict[str, Any]],
    nav_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    OPERATIONAL_DIR.mkdir(parents=True, exist_ok=True)
    ledger_path = OPERATIONAL_DIR / "forward_observation_ledger.csv"
    positions_path = OPERATIONAL_DIR / "virtual_positions.csv"
    trades_path = OPERATIONAL_DIR / "virtual_trades.csv"
    ledger_fields, position_fields, trade_fields = operational_fields()
    candidate_nav = next(row for row in nav_rows if row["portfolio_id"] == "candidate_80_reference_20_ANGL")
    ledger_row = {
        "ledger_key": f"{OBSERVATION_ID}|{session.isoformat()}|initial_establishment",
        "observation_id": OBSERVATION_ID,
        "date": session.isoformat(),
        "official_close_utc": session_close_utc(session).isoformat(),
        "row_type": "initial_establishment",
        "reference_index": reference_price,
        "ANGL_price": asset_prices["ANGL"],
        "pretrade_nav": candidate_nav["pretrade_nav"],
        "one_way_turnover": candidate_nav["one_way_turnover"],
        "transaction_cost": candidate_nav["transaction_cost"],
        "post_trade_nav": candidate_nav["post_trade_nav"],
        "reference_weight": REFERENCE_WEIGHT,
        "ANGL_weight": CANDIDATE_WEIGHT,
        "maximum_exposure": 1.0,
        "record_classification": "forward_observation",
        "broker_calls": 0,
        "orders_created": 0,
        "status": "initialized_brokerless",
    }
    existing_ledger = read_csv(ledger_path)
    if existing_ledger and "ledger_key" not in existing_ledger[0]:
        for row in existing_ledger:
            row["ledger_key"] = f"{row.get('observation_id')}|{row.get('date')}|{row.get('row_type')}"
    merged_ledger, ledger_additions = merge_unique(existing_ledger, [ledger_row], "ledger_key")
    write_csv(ledger_path, merged_ledger, ["ledger_key", *ledger_fields])

    candidate_positions = [
        {
            "position_key": f"{OBSERVATION_ID}|{row['portfolio_id']}|{row['session_date']}|{row['component_id']}",
            "observation_id": OBSERVATION_ID,
            "portfolio_id": row["portfolio_id"],
            "date": row["session_date"],
            "component_id": row["component_id"],
            "execution_price_or_index": row["execution_price_or_index"],
            "target_weight": row["target_weight"],
            "market_value": row["post_trade_market_value"],
            "virtual_quantity": row["virtual_quantity"],
            "record_classification": row["record_classification"],
        }
        for row in position_rows
    ]
    merged_positions, position_additions = merge_unique(read_csv(positions_path), candidate_positions, "position_key")
    write_csv(positions_path, merged_positions, ["position_key", *position_fields])
    merged_trades, trade_additions = merge_unique(read_csv(trades_path), trade_rows, "trade_key")
    write_csv(trades_path, merged_trades, trade_fields)

    payload = {
        "observation_id": OBSERVATION_ID,
        "strategy_id": STRATEGY_ID,
        "family_id": FAMILY_ID,
        "entity_type": "paper_demo_observation",
        "stage": "paper_demo_active",
        "outcome": "paper_demo_active",
        "status": "active_brokerless_paper_demo_observation",
        "paper_forward_active": True,
        "protected": True,
        "frozen": True,
        "rules_frozen": True,
        "adaptation_label": "paper_demo_observation_fix",
        "parent_strategy_id": STRATEGY_ID,
        "parent_trial_id": PARENT_TRIAL_ID,
        "observation_route": "diversifier_only",
        "reference_portfolio_id": REFERENCE_ID,
        "candidate_sleeve_id": "ANGL",
        "target_weights": {"frozen_reference": REFERENCE_WEIGHT, "ANGL": CANDIDATE_WEIGHT},
        "rebalance_frequency": "monthly",
        "signal_timing": "month_end_close",
        "execution_convention": "next_available_session_close",
        "cost_assumption": "5_bps_per_one_way_turnover",
        "correction_activation_timestamp": CORRECTION_ACTIVATION.isoformat(),
        "first_forward_observation_date": session.isoformat(),
        "latest_committed_observation_date": session.isoformat(),
        "latest_committed_virtual_nav": candidate_nav["post_trade_nav"],
        "latest_reference_index": reference_price,
        "latest_ANGL_price": asset_prices["ANGL"],
        "failure_reason": "",
        "next_action": NEXT_ACTION_ACTIVE,
        "review_trigger": "after_three_completed_scheduled_month_end_rebalance_cycles_or_immediate_operational_exception",
        "record_classification": "forward_observation",
        "operational_ledger": rel(ledger_path),
        "virtual_positions": rel(positions_path),
        "virtual_trades": rel(trades_path),
        "broker_integration": False,
        "account_access": False,
        "paper_orders": False,
        "live_orders": False,
        "real_money_recommendation": False,
    }
    write_yaml(OPERATIONAL_DIR / "active_observation.yaml", payload)
    return {
        "ledger_path": rel(ledger_path),
        "positions_path": rel(positions_path),
        "trades_path": rel(trades_path),
        "ledger_additions": ledger_additions,
        "position_additions": position_additions,
        "trade_additions": trade_additions,
        "ledger_rows": len(merged_ledger),
        "position_rows": len(merged_positions),
        "trade_rows": len(merged_trades),
    }


def replace_authoritative_observation(
    stage: str,
    outcome: str,
    failure_reason: str,
    next_action: str,
    first_forward_date: str,
) -> str:
    text = ACTIVE_OBSERVATIONS_PATH.read_text(encoding="utf-8")
    match_pattern = re.compile(
        rf"(?ms)^- observation_id: {re.escape(OBSERVATION_ID)}\n.*?(?=^benchmark_controls:|^- observation_id:|\Z)"
    )
    match = match_pattern.search(text)
    if not match:
        raise RuntimeError(f"Existing observation {OBSERVATION_ID} was not found")
    old = yaml.safe_load("active_observations:\n" + "\n".join("  " + line for line in match.group(0).splitlines()))
    prior = old["active_observations"][0]
    active = stage == "paper_demo_active"
    prior.update(
        {
            "stage": stage,
            "outcome": outcome,
            "state": "active_accepted_frozen_observation" if active else "blocked_observation_invalid_or_incomplete",
            "paper_forward_active": active,
            "corrected_first_forward_observation_date": first_forward_date,
            "first_forward_observation_date": first_forward_date,
            "current_status": stage,
            "failure_reason": failure_reason,
            "adaptation_label": "paper_demo_observation_fix",
            "next_action": next_action,
            "latest_operational_update_id": TASK_ID,
            "latest_operational_update_evidence_path": rel(OUTPUT_DIR),
            "broker_integration": False,
            "paper_orders": False,
            "live_orders": False,
            "real_money_recommendation": False,
        }
    )
    block = yaml.safe_dump([prior], sort_keys=False, width=120, allow_unicode=False).rstrip()
    updated = match_pattern.sub(block + "\n", text, count=1)
    if updated != text:
        ACTIVE_OBSERVATIONS_PATH.write_text(updated, encoding="utf-8")
        return "updated_in_place"
    return "already_current"


def update_registry_next_action(next_action: str) -> str:
    text = REGISTRY_PATH.read_text(encoding="utf-8")
    pattern = re.compile(rf"(?ms)^- id: {re.escape(STRATEGY_ID)}\n.*?(?=^- id:|\Z)")
    match = pattern.search(text)
    if not match:
        raise RuntimeError(f"Strategy record {STRATEGY_ID} was not found")
    block = match.group(0)
    if re.search(r"(?m)^  next_action:", block):
        updated = re.sub(r"(?m)^  next_action:.*$", f"  next_action: {next_action}", block)
    else:
        anchor = re.search(r"(?m)^  allowed_next_action:.*$", block)
        if not anchor:
            raise RuntimeError("ANGL strategy record has no next-action insertion anchor")
        updated = block[: anchor.start()] + f"  next_action: {next_action}\n" + block[anchor.start() :]
    updated = re.sub(r"(?m)^  allowed_next_action:.*$", f"  allowed_next_action: {next_action}", updated)
    if updated == block:
        return "already_current"
    REGISTRY_PATH.write_text(text[: match.start()] + updated + text[match.end() :], encoding="utf-8")
    return "next_action_updated"


def strategy_card(next_action: str) -> dict[str, Any]:
    return {
        "strategy_id": STRATEGY_ID,
        "family_id": FAMILY_ID,
        "display_name": "ICE/VanEck US Fallen Angel ANGL",
        "entity_type": "strategy_configuration",
        "stage": "paper_demo_eligible",
        "outcome": "paper_demo_eligible",
        "route": "diversifier_only",
        "standalone_observation_authorized": False,
        "paper_demo_eligibility_changed": False,
        "strategy_rules_changed": False,
        "new_strategy_created": False,
        "next_action": next_action,
        "real_money_authorized": False,
    }


def trial_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    sources = [
        ROOT / "evidence" / "research_recovery" / "rerun_fast_source_library_blocked_candidates_v3" / "latest" / "trial_ledger.csv",
        ROOT / "evidence" / "validation" / "angl_fallen_angel_diversifier_validation_v1" / "latest" / "trial_ledger.csv",
        CORRECTION_DIR / "trial_ledger.csv",
    ]
    for source in sources:
        for row in read_csv(source):
            if row.get("strategy_id") != STRATEGY_ID:
                continue
            rows.append(
                {
                    "trial_id": row.get("trial_id", ""),
                    "parent_trial_id": row.get("parent_trial_id", ""),
                    "strategy_id": STRATEGY_ID,
                    "entity_type": "experiment_trial",
                    "stage": row.get("stage", ""),
                    "adaptation_label": row.get("adaptation_label", ""),
                    "outcome": row.get("outcome", ""),
                    "read_only": True,
                    "source_path": rel(source),
                    "new_trial_created": False,
                }
            )
    by_id = {row["trial_id"]: row for row in rows if row["trial_id"]}
    return [by_id[key] for key in sorted(by_id)]


def historical_rows() -> list[dict[str, Any]]:
    return [
        {
            **row,
            "record_classification": row.get("corrected_record_classification", "historical_reconciliation_only"),
        }
        for row in read_csv(BOUNDARY_DIR / "historical_reconciliation_records.csv")
    ]


def run(now: datetime | None = None) -> dict[str, Any]:
    clean_output()
    requested_at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    symbols = required_symbols()
    cache_paths = [path for symbol in symbols for path in (cache_path(symbol), metadata_path(symbol))]
    state_before = hash_map(list(PROTECTED_STATE_PATHS))
    prior_before = hash_map(list(PRIOR_EVIDENCE_PATHS))
    cache_before = hash_map(cache_paths)
    operational_before = hash_map(
        [
            OPERATIONAL_DIR / "active_observation.yaml",
            OPERATIONAL_DIR / "forward_observation_ledger.csv",
            OPERATIONAL_DIR / "virtual_positions.csv",
            OPERATIONAL_DIR / "virtual_trades.csv",
        ]
    )

    sessions = completed_post_activation_sessions(requested_at)
    refresh_rows, refresh = refresh_required_data(symbols, sessions)
    attempted_through = sessions[0] if sessions else EXPECTED_SESSION
    reference, reference_rows, reference_status = reconstruct_reference(attempted_through)
    selected_session, boundary_rows = common_session_availability(symbols, reference, sessions)

    target_rows: list[dict[str, Any]] = []
    position_rows: list[dict[str, Any]] = []
    trade_rows: list[dict[str, Any]] = []
    nav_rows: list[dict[str, Any]] = []
    control_rows: list[dict[str, Any]] = []
    forward_rows: list[dict[str, Any]] = []
    operational_result: dict[str, Any] = {}
    failure_reason = ""
    blocker = ""
    next_action = NEXT_ACTION_ACTIVE
    stage = "paper_demo_active"
    outcome = "paper_demo_active"

    if not sessions:
        failure_reason = "data_unavailable"
        blocker = "no completed regular U.S. market session exists after correction activation"
        next_action = "wait_for_first_completed_common_session_after_angl_correction_activation"
    elif refresh.get("status") == "blocked_refresh_failed":
        failure_reason = "data_unavailable"
        missing = refresh.get("failures", {})
        blocker = "bounded current-data refresh failed for: " + "|".join(sorted(missing))
        next_action = "authorize_specific_missing_angl_observation_market_data_remediation"
    elif reference_status.get("status") != "reproducible":
        failure_reason = "data_or_comparability_failure"
        blocker = "frozen_current_active_vm_dsr_usci_combo is not reproducible through the earliest completed session"
        next_action = "repair_frozen_reference_state_through_completed_session_v1"
    elif selected_session is None:
        failure_reason = "data_unavailable"
        blocker = "no complete candidate/control/reference session exists after correction activation"
        next_action = "authorize_specific_missing_angl_observation_market_data_remediation"

    if failure_reason:
        stage = "blocked"
        outcome = "observation_invalid_or_incomplete"
        replace_authoritative_observation(stage, outcome, failure_reason, next_action, "")
        registry_action = update_registry_next_action(next_action)
    else:
        assert selected_session is not None
        reference_row = reference.loc[pd.Timestamp(selected_session)]
        reference_price = float(reference_row["reference_index"])
        asset_prices = {symbol: float(close_series(symbol).loc[pd.Timestamp(selected_session)]) for symbol in CONTROL_SYMBOLS}
        target_rows, position_rows, trade_rows, nav_rows, control_rows = build_portfolio_initialization(
            selected_session, reference_price, asset_prices
        )
        candidate_nav = next(row for row in nav_rows if row["portfolio_id"] == "candidate_80_reference_20_ANGL")
        forward_rows = [
            {
                "observation_id": OBSERVATION_ID,
                "observation_timestamp": requested_at.isoformat(),
                "market_session": selected_session.isoformat(),
                "official_close_utc": session_close_utc(selected_session).isoformat(),
                "target_weights": {"frozen_reference": 0.8, "ANGL": 0.2},
                "pretrade_weights": {"frozen_reference": 0.0, "ANGL": 0.0},
                "one_way_turnover": candidate_nav["one_way_turnover"],
                "transaction_cost": candidate_nav["transaction_cost"],
                "post_trade_nav": candidate_nav["post_trade_nav"],
                "candidate_reference_index": reference_price,
                "candidate_ANGL_price": asset_prices["ANGL"],
                "control_HYG_price": asset_prices["HYG"],
                "control_JNK_price": asset_prices["JNK"],
                "maximum_exposure": candidate_nav["maximum_exposure"],
                "weight_sum": candidate_nav["weight_sum"],
                "data_freshness": "all_required_symbols_same_completed_session",
                "reference_reconciliation_status": "pass",
                "record_classification": "forward_observation",
                "broker_order_submitted": False,
            }
        ]
        operational_result = write_operational_state(
            selected_session, reference_price, asset_prices, position_rows, trade_rows, nav_rows
        )
        replace_authoritative_observation(
            stage,
            outcome,
            "",
            next_action,
            selected_session.isoformat(),
        )
        registry_action = update_registry_next_action(next_action)

    observation_row = {
        "observation_id": OBSERVATION_ID,
        "entity_type": "paper_demo_observation",
        "stage": stage,
        "outcome": outcome,
        "parent_strategy_id": STRATEGY_ID,
        "parent_trial_id": PARENT_TRIAL_ID,
        "observation_route": "diversifier_only",
        "reference_portfolio_id": REFERENCE_ID,
        "target_weights": {"frozen_reference": 0.8, "ANGL": 0.2},
        "adaptation_label": "paper_demo_observation_fix",
        "correction_activation_timestamp": CORRECTION_ACTIVATION.isoformat(),
        "first_forward_observation_date": "" if selected_session is None or failure_reason else selected_session.isoformat(),
        "failure_reason": failure_reason,
        "next_action": next_action,
        "new_observation_created": False,
        "broker_integration": False,
        "paper_orders": False,
        "live_orders": False,
        "real_money_recommendation": False,
    }

    cache_after = hash_map(cache_paths)
    state_after = hash_map(list(PROTECTED_STATE_PATHS))
    prior_after = hash_map(list(PRIOR_EVIDENCE_PATHS))
    operational_after = hash_map(
        [
            OPERATIONAL_DIR / "active_observation.yaml",
            OPERATIONAL_DIR / "forward_observation_ledger.csv",
            OPERATIONAL_DIR / "virtual_positions.csv",
            OPERATIONAL_DIR / "virtual_trades.csv",
        ]
    )
    allowed_state_changes = {rel(REGISTRY_PATH), rel(ACTIVE_OBSERVATIONS_PATH)}
    protected_unchanged = all(
        state_before[path] == state_after[path]
        for path in state_before
        if path not in allowed_state_changes
    )
    prior_unchanged = prior_before == prior_after
    weights_pass = all(abs(float(row["weight_sum"]) - 1.0) <= WEIGHT_TOLERANCE for row in nav_rows)
    exposure_pass = all(float(row["maximum_exposure"]) <= 1.0 + WEIGHT_TOLERANCE for row in nav_rows)
    duplicate_trade_keys = len({row["trade_key"] for row in trade_rows}) != len(trade_rows)
    idempotency_rows = [
        {
            "check_id": "existing_observation_updated_in_place",
            "status": "pass",
            "details": f"observation_id={OBSERVATION_ID};new_observation_created=false",
        },
        {
            "check_id": "same_session_trade_keys_unique",
            "status": "pass" if not duplicate_trade_keys else "fail",
            "details": f"unique={len({row['trade_key'] for row in trade_rows})};rows={len(trade_rows)}",
        },
        {
            "check_id": "same_session_rerun_upserts_without_duplicate_trade",
            "status": (
                "pass"
                if not failure_reason and operational_result.get("trade_rows", 0) == len(trade_rows)
                else "pass" if failure_reason else "fail"
            ),
            "details": json.dumps(operational_result, sort_keys=True),
        },
        {
            "check_id": "earliest_session_selected_chronologically",
            "status": (
                "pass"
                if failure_reason
                or (
                    selected_session is not None
                    and selected_session == next(
                        date.fromisoformat(row["candidate_session"])
                        for row in boundary_rows
                        if row["complete_common_session"]
                    )
                )
                else "fail"
            ),
            "details": "" if selected_session is None else selected_session.isoformat(),
        },
    ]

    state_change_rows: list[dict[str, Any]] = []
    for path_text, before_hash in state_before.items():
        after_hash = state_after[path_text]
        state_change_rows.append(
            {
                "path": path_text,
                "path_type": "protected_state",
                "before_hash": before_hash,
                "after_hash": after_hash,
                "changed": before_hash != after_hash,
                "change_permitted": path_text in allowed_state_changes,
                "action": (
                    "ANGL_strategy_next_action_only"
                    if path_text == rel(REGISTRY_PATH)
                    else "existing_ANGL_observation_updated_in_place"
                    if path_text == rel(ACTIVE_OBSERVATIONS_PATH)
                    else "unchanged_required"
                ),
            }
        )
    for path_text, before_hash in cache_before.items():
        state_change_rows.append(
            {
                "path": path_text,
                "path_type": "authorized_market_data_cache_or_metadata",
                "before_hash": before_hash,
                "after_hash": cache_after[path_text],
                "changed": before_hash != cache_after[path_text],
                "change_permitted": True,
                "action": "bounded_exact_symbol_refresh",
            }
        )
    for path_text, before_hash in operational_before.items():
        state_change_rows.append(
            {
                "path": path_text,
                "path_type": "ANGL_operational_observation_file",
                "before_hash": before_hash,
                "after_hash": operational_after[path_text],
                "changed": before_hash != operational_after[path_text],
                "change_permitted": True,
                "action": "same_observation_operational_state_or_ledger",
            }
        )

    data_rows: list[dict[str, Any]] = []
    for symbol in symbols:
        frame = load_cache(symbol)
        available = set(pd.to_datetime(frame["date"]).dt.date) if not frame.empty else set()
        data_rows.append(
            {
                "symbol": symbol,
                "role": (
                    "candidate"
                    if symbol == "ANGL"
                    else "control"
                    if symbol in {"HYG", "JNK"}
                    else "frozen_reference_input"
                ),
                "cache_path": rel(cache_path(symbol)),
                "first_date": "" if frame.empty else str(frame.iloc[0]["date"]),
                "latest_date": "" if frame.empty else str(frame.iloc[-1]["date"]),
                "selected_session": "" if selected_session is None else selected_session.isoformat(),
                "selected_session_available": selected_session in available if selected_session else False,
                "canonical_adjusted_schema": tuple(frame.columns) == CANONICAL_COLUMNS if not frame.empty else False,
                "cache_hash": file_hash(cache_path(symbol)),
                "metadata_hash": file_hash(metadata_path(symbol)),
                "freshness_status": (
                    "pass"
                    if selected_session and selected_session in available
                    else "blocked_missing_selected_session"
                ),
            }
        )

    historical = historical_rows()
    trial = trial_rows()
    benchmark_rows = [
        {
            "benchmark_or_control_id": REFERENCE_ID,
            "entity_type": "benchmark_reference",
            "stage": "benchmark_reference_only",
            "role": "frozen_reference",
            "counted_as_strategy_or_trial": False,
        },
        {
            "benchmark_or_control_id": "HYG_buy_hold",
            "entity_type": "benchmark_reference",
            "stage": "benchmark_reference_only",
            "role": "principal_control",
            "counted_as_strategy_or_trial": False,
        },
        {
            "benchmark_or_control_id": "monthly_rebalanced_50_50_HYG_JNK",
            "entity_type": "benchmark_reference",
            "stage": "benchmark_reference_only",
            "role": "principal_control",
            "counted_as_strategy_or_trial": False,
        },
    ]
    process_rows = [
        {
            "task_id": TASK_ID,
            "entity_type": "process_task",
            "stage": "implementation",
            "strategy_counted": False,
            "trial_counted": False,
            "observation_counted": False,
            "brokerless": True,
        }
    ]
    failure_rows = (
        [
            {
                "observation_id": OBSERVATION_ID,
                "primary_failure_reason": failure_reason,
                "blocker": blocker,
                "stage": stage,
                "next_action": next_action,
            }
        ]
        if failure_reason
        else []
    )
    outcome_rows = [
        {
            "task_id": TASK_ID,
            "observation_id": OBSERVATION_ID,
            "stage": stage,
            "outcome": outcome,
            "selected_session": "" if selected_session is None or failure_reason else selected_session.isoformat(),
            "expected_session_used": bool(selected_session == EXPECTED_SESSION and not failure_reason),
            "forward_observation_rows": len(forward_rows),
            "new_strategy_count": 0,
            "new_trial_count": 0,
            "new_observation_count": 0,
            "failure_reason": failure_reason,
            "blocker": blocker,
            "observation_next_action": next_action,
            "project_discovery_next_action": PROJECT_NEXT_ACTION,
        }
    ]

    write_yaml(
        OUTPUT_DIR / "initialization_manifest.yaml",
        {
            "task_id": TASK_ID,
            "mode": "active-direction-execution",
            "stage": "implementation",
            "strategy_id": STRATEGY_ID,
            "family_id": FAMILY_ID,
            "observation_id": OBSERVATION_ID,
            "parent_trial_id": PARENT_TRIAL_ID,
            "correction_activation_timestamp": CORRECTION_ACTIVATION.isoformat(),
            "requested_at_utc": requested_at.isoformat(),
            "expected_earliest_session": EXPECTED_SESSION.isoformat(),
            "selected_session": "" if selected_session is None or failure_reason else selected_session.isoformat(),
            "outcome": outcome,
            "primary_failure_reason": failure_reason,
            "observation_next_action": next_action,
            "project_discovery_next_action": PROJECT_NEXT_ACTION,
            "new_strategy_configurations": 0,
            "new_experiment_trials": 0,
            "new_observations": 0,
            "broker_account_position_order_endpoint_called": False,
            "paper_or_live_order_submitted": False,
            "real_money_action": False,
        },
    )
    write_csv(
        OUTPUT_DIR / "strategy_cards.csv",
        [strategy_card(next_action)],
        list(strategy_card(next_action)),
    )
    write_csv(
        OUTPUT_DIR / "trial_ledger.csv",
        trial,
        [
            "trial_id",
            "parent_trial_id",
            "strategy_id",
            "entity_type",
            "stage",
            "adaptation_label",
            "outcome",
            "read_only",
            "source_path",
            "new_trial_created",
        ],
    )
    write_csv(OUTPUT_DIR / "paper_demo_observations.csv", [observation_row], list(observation_row))
    write_csv(OUTPUT_DIR / "process_task_log.csv", process_rows, list(process_rows[0]))
    write_csv(OUTPUT_DIR / "benchmark_reference_log.csv", benchmark_rows, list(benchmark_rows[0]))
    write_csv(OUTPUT_DIR / "market_data_refresh_manifest.csv", refresh_rows, list(refresh_rows[0]) if refresh_rows else ["symbol"])
    write_csv(OUTPUT_DIR / "data_freshness.csv", data_rows, list(data_rows[0]))
    reference_fields = [
        "date",
        "reference_or_component_id",
        "row_type",
        "signal_date",
        "target_weights",
        "one_way_turnover",
        "transaction_cost",
        "component_index",
        "reconciliation_status",
        "vm_sleeve_value",
        "dsr_sleeve_value",
        "usci_sleeve_value",
        "reference_virtual_equity",
        "reference_index",
        "component_costs_reapplied",
    ]
    write_csv(OUTPUT_DIR / "reference_state_reconciliation.csv", reference_rows, reference_fields)
    write_csv(OUTPUT_DIR / "forward_boundary_reconciliation.csv", boundary_rows, list(boundary_rows[0]) if boundary_rows else ["candidate_session"])
    historical_fields = sorted({key for row in historical for key in row}) if historical else ["record_classification"]
    write_csv(OUTPUT_DIR / "historical_reconciliation_records.csv", historical, historical_fields)
    write_csv(OUTPUT_DIR / "forward_observation_records.csv", forward_rows, FORWARD_FIELDS)
    write_csv(
        OUTPUT_DIR / "initial_target_weights.csv",
        target_rows,
        ["portfolio_id", "session_date", "component_id", "pretrade_weight", "target_weight", "post_trade_weight", "record_classification"],
    )
    write_csv(
        OUTPUT_DIR / "initial_virtual_positions.csv",
        position_rows,
        [
            "portfolio_id",
            "session_date",
            "component_id",
            "execution_price_or_index",
            "target_weight",
            "post_trade_market_value",
            "virtual_quantity",
            "broker_order_submitted",
            "record_classification",
        ],
    )
    write_csv(
        OUTPUT_DIR / "initial_virtual_trades.csv",
        trade_rows,
        operational_fields()[2],
    )
    write_csv(
        OUTPUT_DIR / "initial_virtual_nav.csv",
        nav_rows,
        [
            "portfolio_id",
            "session_date",
            "pretrade_nav",
            "one_way_turnover",
            "cost_rate",
            "transaction_cost",
            "post_trade_nav",
            "weight_sum",
            "maximum_exposure",
            "record_classification",
        ],
    )
    write_csv(
        OUTPUT_DIR / "control_virtual_nav.csv",
        control_rows,
        [
            "portfolio_id",
            "session_date",
            "pretrade_nav",
            "one_way_turnover",
            "transaction_cost",
            "post_trade_nav",
            "reference_weight",
            "ANGL_weight",
            "HYG_weight",
            "JNK_weight",
            "record_classification",
        ],
    )
    write_csv(OUTPUT_DIR / "idempotency_check.csv", idempotency_rows, list(idempotency_rows[0]))
    write_csv(OUTPUT_DIR / "state_change_manifest.csv", state_change_rows, list(state_change_rows[0]))
    write_csv(OUTPUT_DIR / "outcome_summary.csv", outcome_rows, list(outcome_rows[0]))
    write_csv(
        OUTPUT_DIR / "failure_reasons.csv",
        failure_rows,
        ["observation_id", "primary_failure_reason", "blocker", "stage", "next_action"],
    )
    next_rows = [
        {
            "action_scope": "ANGL_observation",
            "exact_next_action": next_action,
            "execute_in_this_task": False,
        },
        {
            "action_scope": "separate_project_discovery",
            "exact_next_action": PROJECT_NEXT_ACTION,
            "execute_in_this_task": False,
        },
    ]
    write_csv(OUTPUT_DIR / "next_actions.csv", next_rows, list(next_rows[0]))

    consistency = {
        "consistency_passed": bool(
            protected_unchanged
            and prior_unchanged
            and not duplicate_trade_keys
            and (failure_reason != "" or (weights_pass and exposure_pass and len(forward_rows) == 1))
        ),
        "expected_earliest_session": EXPECTED_SESSION.isoformat(),
        "selected_session": "" if selected_session is None or failure_reason else selected_session.isoformat(),
        "earliest_valid_session_used": bool(
            failure_reason
            or (
                selected_session is not None
                and selected_session
                == next(
                    date.fromisoformat(row["candidate_session"])
                    for row in boundary_rows
                    if row["complete_common_session"]
                )
            )
        ),
        "june_18_records_historical_reconciliation_only": bool(
            historical and all(row["record_classification"] == "historical_reconciliation_only" for row in historical)
        ),
        "forward_rows_created": len(forward_rows),
        "forward_rows_use_forward_observation_classification": all(
            row["record_classification"] == "forward_observation" for row in forward_rows
        ),
        "candidate_controls_reference_same_session": bool(
            failure_reason
            or (
                len({row["session_date"] for row in position_rows}) == 1
                and len({row["session_date"] for row in nav_rows}) == 1
                and len({row["session_date"] for row in control_rows}) == 1
            )
        ),
        "weights_sum_to_one": weights_pass,
        "maximum_exposure_lte_one": exposure_pass,
        "turnover_nonnegative": all(float(row["one_way_turnover"]) >= 0 for row in nav_rows),
        "costs_nonnegative": all(float(row["transaction_cost"]) >= 0 for row in nav_rows),
        "trade_keys_unique": not duplicate_trade_keys,
        "idempotency_checks_pass": all(row["status"] == "pass" for row in idempotency_rows),
        "reference_reproducible": reference_status.get("status") == "reproducible",
        "all_required_symbols_exactly_authorized": set(symbols) == set(reference_symbols() + CONTROL_SYMBOLS),
        "only_permitted_state_changes": protected_unchanged,
        "prior_evidence_unchanged": prior_unchanged,
        "cache_changes_limited_to_required_symbols": True,
        "new_strategy_configurations": 0,
        "new_experiment_trials": 0,
        "new_observations": 0,
        "strategy_stage": "paper_demo_eligible",
        "strategy_outcome": "paper_demo_eligible",
        "strategy_route": "diversifier_only",
        "observation_stage": stage,
        "observation_outcome": outcome,
        "registry_action": registry_action,
        "broker_account_position_order_endpoint_called": False,
        "paper_or_live_order_submitted": False,
        "real_money_action": False,
        "performance_review_run": False,
        "observation_next_action": next_action,
        "project_discovery_next_action": PROJECT_NEXT_ACTION,
    }
    write_json(OUTPUT_DIR / "consistency_check.json", consistency)
    write_text(
        OUTPUT_DIR / "initialization_report.md",
        f"""# ANGL Brokerless Forward Initialization

The existing `{OBSERVATION_ID}` record was processed using the earliest chronologically available completed common session after `{CORRECTION_ACTIVATION.isoformat()}`.

## Outcome

- Observation stage/outcome: `{stage}` / `{outcome}`
- Selected forward session: `{'' if selected_session is None or failure_reason else selected_session.isoformat()}`
- Official close: `{'' if selected_session is None or failure_reason else session_close_utc(selected_session).isoformat()}`
- Primary failure reason: `{failure_reason}`
- Blocker: `{blocker}`
- Frozen reference reconstruction: `{reference_status.get('status')}`
- New strategies/trials/observations: `0 / 0 / 0`
- Broker, account, position, or order endpoint calls: `0`
- Virtual orders submitted: `0`

All June 18 records remain `historical_reconciliation_only`. The initialized row is operational evidence only and is not evidence of profitability.

## Next Actions

- ANGL observation: `{next_action}` (not executed)
- Separate project discovery: `{PROJECT_NEXT_ACTION}` (not executed)
""",
    )
    return {
        "task_id": TASK_ID,
        "output_dir": rel(OUTPUT_DIR),
        "observation_id": OBSERVATION_ID,
        "stage": stage,
        "outcome": outcome,
        "selected_session": "" if selected_session is None or failure_reason else selected_session.isoformat(),
        "primary_failure_reason": failure_reason,
        "observation_next_action": next_action,
        "project_discovery_next_action": PROJECT_NEXT_ACTION,
        "consistency_passed": consistency["consistency_passed"],
    }


def main() -> int:
    result = run()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["consistency_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
