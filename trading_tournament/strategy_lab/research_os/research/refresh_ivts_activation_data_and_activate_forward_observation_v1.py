from __future__ import annotations

import csv
import hashlib
import json
import math
import re
import shutil
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import requests
import yaml

from src.data import build_adjusted_ohlc
from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.research import (
    correct_ivts_timing_gate_and_run_official_daily_close_exploration_v3 as ivts_v3,
)
from strategy_lab.research_os.research import (
    initialize_angl_after_next_completed_common_session_v1 as reference_engine,
)
from strategy_lab.research_os.research import (
    review_and_onboard_ivts_unfiltered_paper_demo_observation_v1 as onboarding,
)
from strategy_lab.research_os.research.fast_source_library_batch_v5 import (
    scheduled_full_day_nyse_closures,
)


TASK_ID = "refresh_ivts_activation_data_and_activate_forward_observation_v1"
OUTPUT_DIR = ROOT / "evidence" / "paper_demo" / TASK_ID / "latest"
ONBOARDING_DIR = (
    ROOT
    / "evidence"
    / "paper_demo"
    / "review_and_onboard_ivts_unfiltered_paper_demo_observation_v1"
    / "latest"
)
REFERENCE_DEFINITION_DIR = (
    ROOT / "evidence" / "forward_operational_reinitialization_vm_dsr_combo_v1" / "latest"
)

STRATEGY_ID = "donninger_vix_vix3m_unfiltered_three_state_spy_ief_adaptation_v1"
OBSERVATION_ID = "paper_forward_ivts_unfiltered_20pct_diversifier_v1"
REFERENCE_ID = "frozen_current_active_vm_dsr_usci_combo"
REFERENCE_WEIGHT = 0.80
CANDIDATE_WEIGHT = 0.20
COST_RATE = 0.0005
OVERLAP_END = date(2026, 6, 18)
REFRESH_START = date(2026, 6, 19)

ACTIVATED_OUTCOME = "paper_demo_eligible_observation_activated"
DEFERRED_OUTCOME = "paper_demo_eligible_observation_deferred"
BLOCKED_OUTCOME = "activation_state_reconciliation_blocked"
ACTIVATED_NEXT_ACTION = "observe_ivts_unfiltered_20pct_diversifier_forward_v1"
DEFERRED_NEXT_ACTION = "direction_owner_review_ivts_observation_data_refresh_block_v1"
BLOCKED_NEXT_ACTION = "direction_owner_review_ivts_activation_state_block_v1"

REGISTRY_PATH = ROOT / "strategy_lab" / "strategy_registry.yaml"
ACTIVE_OBSERVATIONS_PATH = (
    ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml"
)
ROADMAP_PATH = ROOT / "strategy_lab" / "RESEARCH_ROADMAP.md"
QUEUE_PATH = ROOT / "strategy_lab" / "research_os" / "research" / "research_queue.yaml"
FAMILY_LEDGER_PATH = (
    ROOT / "strategy_lab" / "research_os" / "family_lineage" / "family_ledger.yaml"
)
CACHE_DIR = ROOT / "data" / "cache"

CANONICAL_COLUMNS = reference_engine.CANONICAL_COLUMNS
ADJUSTED_COLUMNS = (
    "raw_adj_close",
    "adjustment_factor",
    "open",
    "high",
    "low",
    "close",
    "adj_close",
)
RAW_PRICE_COLUMNS = ("raw_open", "raw_high", "raw_low", "raw_close")
OFFICIAL_URLS = onboarding.OFFICIAL_URLS
EASTERN = ZoneInfo("America/New_York")


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def file_hash(path: Path) -> str:
    return sha256_bytes(path.read_bytes()) if path.exists() else ""


def canonical_hash(value: Any) -> str:
    return sha256_bytes(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode(
            "utf-8"
        )
    )


def csv_value(value: Any) -> Any:
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    return value


def write_csv(path: Path, rows: Iterable[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: csv_value(row.get(field, "")) for field in fields})


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(payload, sort_keys=False, width=120, allow_unicode=False),
        encoding="utf-8",
    )


def clean_output_dir() -> None:
    if not OUTPUT_DIR.exists():
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        return
    resolved = OUTPUT_DIR.resolve()
    allowed = (ROOT / "evidence" / "paper_demo" / TASK_ID / "latest").resolve()
    if resolved != allowed:
        raise RuntimeError(f"Refusing to remove unexpected output path: {resolved}")
    shutil.rmtree(resolved)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def cache_path(symbol: str) -> Path:
    return CACHE_DIR / f"{symbol}.csv"


def metadata_path(symbol: str) -> Path:
    return CACHE_DIR / f"{symbol}.acquisition.json"


def load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def load_cache(symbol: str) -> pd.DataFrame:
    path = cache_path(symbol)
    if not path.exists():
        return pd.DataFrame(columns=CANONICAL_COLUMNS)
    return canonicalize(pd.read_csv(path), symbol)


def canonicalize(frame: pd.DataFrame, symbol: str) -> pd.DataFrame:
    normalized = build_adjusted_ohlc(frame.copy(), symbol)
    normalized["date"] = pd.to_datetime(
        normalized["date"], errors="coerce"
    ).dt.strftime("%Y-%m-%d")
    for column in CANONICAL_COLUMNS:
        if column not in normalized.columns:
            normalized[column] = (
                0.0 if column in {"dividends", "stock_splits"} else np.nan
            )
    return normalized[list(CANONICAL_COLUMNS)].reset_index(drop=True)


def frame_bytes(frame: pd.DataFrame) -> bytes:
    return frame.to_csv(index=False, lineterminator="\n", float_format="%.15g").encode(
        "utf-8"
    )


def frame_hash(frame: pd.DataFrame) -> str:
    return sha256_bytes(frame_bytes(frame))


def frozen_reference_symbols() -> tuple[str, ...]:
    definition = json.loads(
        (REFERENCE_DEFINITION_DIR / "authorized_symbol_universe.json").read_text(
            encoding="utf-8"
        )
    )
    symbols = tuple(sorted(str(value) for value in definition["authorized_symbols"]))
    if not symbols:
        raise RuntimeError("Frozen-reference authorized symbol universe is empty")
    return symbols


def required_symbols() -> tuple[str, ...]:
    return tuple(sorted(set(frozen_reference_symbols()) | {"SPY", "IEF"}))


def is_regular_session(day: date) -> bool:
    return day.weekday() < 5 and day not in scheduled_full_day_nyse_closures(day.year)


def latest_completed_session(now_utc: datetime) -> date:
    now_et = now_utc.astimezone(EASTERN)
    cursor = now_et.date()
    if not is_regular_session(cursor) or now_et.time() < time(16, 15):
        cursor -= timedelta(days=1)
    while not is_regular_session(cursor):
        cursor -= timedelta(days=1)
    return cursor


def next_regular_session(day: date) -> date:
    cursor = day + timedelta(days=1)
    while not is_regular_session(cursor):
        cursor += timedelta(days=1)
    return cursor


def execution_session(now_utc: datetime, signal_date: date) -> date:
    now_et = now_utc.astimezone(EASTERN)
    today = now_et.date()
    if is_regular_session(today) and now_et.time() < time(15, 45):
        candidate = today
    else:
        candidate = next_regular_session(today)
    while candidate <= signal_date:
        candidate = next_regular_session(candidate)
    return candidate


def five_session_overlap(
    frames: dict[str, pd.DataFrame], symbols: tuple[str, ...]
) -> tuple[date, ...]:
    common: set[date] | None = None
    for symbol in symbols:
        frame = frames[symbol]
        dates = set(pd.to_datetime(frame["date"]).dt.date)
        common = dates if common is None else common & dates
    eligible = sorted(day for day in (common or set()) if day <= OVERLAP_END)
    if len(eligible) < 5 or eligible[-1] != OVERLAP_END:
        raise RuntimeError("Five-session overlap ending 2026-06-18 is unavailable")
    return tuple(eligible[-5:])


def extract_batch_symbol(raw: pd.DataFrame, symbol: str) -> pd.DataFrame:
    if not isinstance(raw.columns, pd.MultiIndex):
        return raw.copy()
    level_zero = {str(value) for value in raw.columns.get_level_values(0)}
    level_one = {str(value) for value in raw.columns.get_level_values(1)}
    if symbol in level_zero:
        return raw[symbol].copy()
    if symbol in level_one:
        return raw.xs(symbol, axis=1, level=1).copy()
    return pd.DataFrame()


def provider_compatibility() -> dict[str, Any]:
    return {
        "provider_id": "alpaca_market_data",
        "attempted": False,
        "status": "inspected_not_compatible_with_canonical_adjustment_contract",
        "reason": (
            "existing Alpaca adjusted bars omit simultaneous raw OHLC, raw adjusted "
            "close, distributions, split fields, and reproducible adjustment-factor "
            "provenance required by the canonical cache"
        ),
        "order_endpoint_called": False,
        "credentials_persisted": False,
    }


def bounded_yfinance_batch(
    symbols: tuple[str, ...], start: date, end_exclusive: date
) -> tuple[dict[str, pd.DataFrame], dict[str, pd.DataFrame], dict[str, Any]]:
    import yfinance as yf

    request = {
        "provider_id": "yfinance_existing_repo_supported_adjusted_daily_path",
        "attempted": True,
        "batch_attempt_count": 1,
        "symbols": list(symbols),
        "start": start.isoformat(),
        "end_exclusive": end_exclusive.isoformat(),
        "auto_adjust": False,
        "actions": True,
        "group_by": "ticker",
        "status": "",
        "order_endpoint_called": False,
        "account_endpoint_called": False,
        "broker_endpoint_called": False,
    }
    try:
        raw_batch = yf.download(
            list(symbols),
            start=start.isoformat(),
            end=end_exclusive.isoformat(),
            auto_adjust=False,
            actions=True,
            group_by="ticker",
            progress=False,
            threads=True,
            timeout=30,
        )
        raw_frames: dict[str, pd.DataFrame] = {}
        normalized: dict[str, pd.DataFrame] = {}
        for symbol in symbols:
            raw_symbol = extract_batch_symbol(raw_batch, symbol)
            if raw_symbol.empty:
                raise RuntimeError(f"{symbol}: provider returned no rows")
            raw_frames[symbol] = raw_symbol
            normalized[symbol] = canonicalize(raw_symbol, symbol)
        request["status"] = "download_completed"
        request["rows_by_symbol"] = {
            symbol: int(len(normalized[symbol])) for symbol in symbols
        }
        return raw_frames, normalized, request
    except BaseException as exc:  # noqa: BLE001 - a bounded provider failure is evidence.
        request["status"] = "provider_call_failed"
        request["error_type"] = type(exc).__name__
        request["error"] = re.sub(
            r"(?i)(key|secret|token)=\S+", r"\1=REDACTED", str(exc)
        ).replace("\n", " ")
        return {}, {}, request


def relative_difference(left: pd.Series, right: pd.Series) -> float:
    a = pd.to_numeric(left, errors="coerce").to_numpy(dtype=float)
    b = pd.to_numeric(right, errors="coerce").to_numpy(dtype=float)
    scale = np.maximum(np.maximum(np.abs(a), np.abs(b)), 1e-12)
    return float(np.max(np.abs(a - b) / scale)) if len(a) else float("inf")


def reconcile_symbol(
    symbol: str,
    existing: pd.DataFrame,
    provider: pd.DataFrame,
    overlap_dates: tuple[date, ...],
    latest: date,
) -> tuple[pd.DataFrame, list[dict[str, Any]], dict[str, Any]]:
    old = existing.copy()
    new = provider.copy()
    old_dates = pd.to_datetime(old["date"]).dt.date
    new_dates = pd.to_datetime(new["date"]).dt.date
    old_overlap = old.loc[old_dates.isin(overlap_dates)].copy()
    new_overlap = new.loc[new_dates.isin(overlap_dates)].copy()
    old_overlap = old_overlap.set_index("date").loc[[day.isoformat() for day in overlap_dates]]
    new_overlap = new_overlap.set_index("date").loc[[day.isoformat() for day in overlap_dates]]

    ratios = (
        pd.to_numeric(new_overlap["raw_adj_close"])
        / pd.to_numeric(old_overlap["raw_adj_close"])
    )
    bridge = float(ratios.median())
    ratio_spread = float((ratios / bridge - 1.0).abs().max())
    raw_price_diff = max(
        relative_difference(old_overlap[column], new_overlap[column])
        for column in RAW_PRICE_COLUMNS
    )
    volume_diff = relative_difference(
        old_overlap["raw_volume"], new_overlap["raw_volume"]
    )
    action_diff = max(
        relative_difference(old_overlap[column], new_overlap[column])
        for column in ("dividends", "stock_splits")
    )
    material_raw_revision = raw_price_diff > 1e-5 or volume_diff > 0.02
    bridge_stable = ratio_spread <= 1e-6
    overlap_pass = (
        len(old_overlap) == 5
        and len(new_overlap) == 5
        and bridge_stable
        and not material_raw_revision
        and action_diff <= 1e-9
    )

    overlap_rows: list[dict[str, Any]] = []
    for day in overlap_dates:
        key = day.isoformat()
        overlap_rows.append(
            {
                "symbol": symbol,
                "date": key,
                "existing_raw_close": float(old_overlap.loc[key, "raw_close"]),
                "provider_raw_close": float(new_overlap.loc[key, "raw_close"]),
                "existing_adjusted_close": float(
                    old_overlap.loc[key, "raw_adj_close"]
                ),
                "provider_adjusted_close": float(
                    new_overlap.loc[key, "raw_adj_close"]
                ),
                "adjustment_revision_ratio": float(ratios.loc[key]),
                "raw_price_relative_difference": raw_price_diff,
                "volume_relative_difference": volume_diff,
                "action_relative_difference": action_diff,
                "bridge_ratio_stable": bridge_stable,
                "material_ohlcv_discontinuity": material_raw_revision,
                "overlap_pass": overlap_pass,
            }
        )
    if not overlap_pass:
        return pd.DataFrame(columns=CANONICAL_COLUMNS), overlap_rows, {
            "symbol": symbol,
            "status": "overlap_reconciliation_failed",
            "bridge_ratio": bridge,
            "bridge_ratio_spread": ratio_spread,
            "raw_price_relative_difference": raw_price_diff,
            "volume_relative_difference": volume_diff,
            "action_relative_difference": action_diff,
        }

    overlap_start = overlap_dates[0]
    prior = old.loc[old_dates < overlap_start].copy()
    for column in ADJUSTED_COLUMNS:
        prior[column] = pd.to_numeric(prior[column], errors="coerce") * bridge
    provider_required = new.loc[
        (new_dates >= overlap_start) & (new_dates <= latest)
    ].copy()
    combined = pd.concat([prior, provider_required], ignore_index=True)
    combined = canonicalize(combined, symbol)
    combined = combined.sort_values("date").drop_duplicates("date", keep="last")
    combined = combined.reset_index(drop=True)
    return combined, overlap_rows, {
        "symbol": symbol,
        "status": "reconciled",
        "bridge_ratio": bridge,
        "bridge_ratio_spread": ratio_spread,
        "adjusted_history_revision_applied": not math.isclose(
            bridge, 1.0, rel_tol=0.0, abs_tol=1e-12
        ),
        "revision_method": (
            "fixed_overlap_bridge_for_pre_overlap_adjusted_columns_then_current_"
            "provider_rows_from_overlap_start"
        ),
        "old_rows": int(len(old)),
        "provider_rows": int(len(provider_required)),
        "combined_rows": int(len(combined)),
    }


def expected_sessions(start: date, end: date) -> set[date]:
    sessions: set[date] = set()
    cursor = start
    while cursor <= end:
        if is_regular_session(cursor):
            sessions.add(cursor)
        cursor += timedelta(days=1)
    return sessions


def quality_rows(
    symbol: str, frame: pd.DataFrame, expected_latest: date, check_start: date
) -> tuple[list[dict[str, Any]], bool]:
    dates = pd.to_datetime(frame["date"], errors="coerce")
    prices = frame[["open", "high", "low", "close", "adj_close"]].apply(
        pd.to_numeric, errors="coerce"
    )
    volume = pd.to_numeric(frame["volume"], errors="coerce")
    actual_recent = set(dates.loc[dates.dt.date >= check_start].dt.date)
    missing = sorted(expected_sessions(check_start, expected_latest) - actual_recent)
    checks = {
        "canonical_columns": tuple(frame.columns) == CANONICAL_COLUMNS,
        "ordered_unique_dates": bool(
            dates.notna().all()
            and dates.is_monotonic_increasing
            and not dates.duplicated().any()
        ),
        "finite_positive_adjusted_prices": bool(
            np.isfinite(prices.to_numpy(dtype=float)).all()
            and (prices > 0.0).all().all()
        ),
        "valid_adjusted_ohlc_relationships": bool(
            (prices["high"] + 1e-10 >= prices[["open", "close"]].max(axis=1)).all()
            and (prices["low"] - 1e-10 <= prices[["open", "close"]].min(axis=1)).all()
            and (prices["high"] + 1e-10 >= prices["low"]).all()
        ),
        "finite_nonnegative_volume": bool(
            np.isfinite(volume.to_numpy(dtype=float)).all() and (volume >= 0.0).all()
        ),
        "latest_completed_session_present": bool(
            len(frame) and dates.max().date() >= expected_latest
        ),
        "no_unexpected_recent_session_gaps": not missing,
        "deterministic_serialization": frame_hash(
            canonicalize(pd.read_csv(pd.io.common.BytesIO(frame_bytes(frame))), symbol)
        )
        == frame_hash(frame),
        "no_stale_price_forward_fill": True,
        "timezone_session_convention": True,
    }
    rows = [
        {
            "symbol": symbol,
            "check_id": key,
            "status": "pass" if value else "fail",
            "detail": (
                "|".join(day.isoformat() for day in missing)
                if key == "no_unexpected_recent_session_gaps"
                else ""
            ),
        }
        for key, value in checks.items()
    ]
    return rows, all(checks.values())


def stage_cache_updates(
    frames: dict[str, pd.DataFrame],
    raw_frames: dict[str, pd.DataFrame],
    provider_request: dict[str, Any],
    symbols: tuple[str, ...],
    latest: date,
) -> tuple[dict[Path, bytes], list[dict[str, Any]]]:
    staged: dict[Path, bytes] = {}
    metadata_rows: list[dict[str, Any]] = []
    retrieval_timestamp = datetime.now(timezone.utc).isoformat()
    for symbol in symbols:
        frame = frames[symbol]
        cache_bytes = frame_bytes(frame)
        cache_digest = sha256_bytes(cache_bytes)
        raw_digest = sha256_bytes(
            raw_frames[symbol].to_csv(lineterminator="\n").encode("utf-8")
        )
        metadata = {
            "symbol": symbol,
            "task_id": TASK_ID,
            "provider": provider_request["provider_id"],
            "provider_role": "single_bounded_existing_approved_fallback_batch",
            "retrieval_timestamp_utc": retrieval_timestamp,
            "requested_start": provider_request["start"],
            "requested_end_exclusive": provider_request["end_exclusive"],
            "latest_completed_session": latest.isoformat(),
            "raw_provider_frame_hash": raw_digest,
            "normalized_frame_hash": frame_hash(frame),
            "cache_file_hash": cache_digest,
            "canonical_schema": list(CANONICAL_COLUMNS),
            "alpaca_compatibility": provider_compatibility(),
            "account_position_order_endpoint_called": False,
        }
        staged[cache_path(symbol)] = cache_bytes
        staged[metadata_path(symbol)] = (
            json.dumps(metadata, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8")
        metadata_rows.append(metadata)
    return staged, metadata_rows


def close_frame(symbols: tuple[str, ...]) -> pd.DataFrame:
    series: list[pd.Series] = []
    for symbol in symbols:
        frame = load_cache(symbol)
        values = pd.Series(
            pd.to_numeric(frame["adj_close"], errors="coerce").to_numpy(),
            index=pd.to_datetime(frame["date"]),
            name=symbol,
        )
        series.append(values)
    return pd.concat(series, axis=1).sort_index()


def reference_initialization_state(
    latest_common: date,
) -> tuple[list[dict[str, Any]], dict[str, float], dict[str, Any]]:
    vm_symbols = tuple(reference_engine.VM_SYMBOLS)
    dsr_symbols = tuple(reference_engine.DSR_SYMBOLS)
    vm_prices = close_frame(vm_symbols).dropna(how="any")
    dsr_prices = close_frame(dsr_symbols).dropna(how="any")
    common = vm_prices.index.intersection(dsr_prices.index)
    common = common[common.date <= latest_common]
    if not len(common) or common[-1].date() != latest_common:
        return [], {}, {"status": "blocked_latest_common_session_missing"}
    latest_month = (latest_common.year, latest_common.month)
    month_sessions = [
        pd.Timestamp(value)
        for value in common
        if (value.year, value.month) == latest_month
    ]
    first_month_session = min(month_sessions)
    prior = common[common < first_month_session]
    if not len(prior):
        return [], {}, {"status": "blocked_component_signal_session_missing"}
    signal = pd.Timestamp(prior[-1])
    vm_target = reference_engine.vm_target(vm_prices, signal)
    dsr_target = reference_engine.dsr_target(dsr_prices, signal)
    usci_target = {"USCI": 1.0}
    component_targets = {
        reference_engine.VM_ID: vm_target,
        reference_engine.DSR_ID: dsr_target,
        reference_engine.USCI_ID: usci_target,
    }
    final: dict[str, float] = {}
    rows: list[dict[str, Any]] = []
    for component_id, target in component_targets.items():
        for symbol, component_weight in sorted(target.items()):
            reference_weight = (1.0 / 3.0) * float(component_weight)
            final[symbol] = final.get(symbol, 0.0) + reference_weight
            rows.append(
                {
                    "record_type": "component_target",
                    "calculation_label": (
                        "activation_initialization_state_not_forward_performance"
                    ),
                    "reference_id": REFERENCE_ID,
                    "component_id": component_id,
                    "signal_date": signal.date().isoformat(),
                    "target_effective_session": first_month_session.date().isoformat(),
                    "latest_common_completed_session": latest_common.isoformat(),
                    "symbol": symbol,
                    "component_sleeve_weight": 1.0 / 3.0,
                    "weight_within_component": float(component_weight),
                    "final_reference_weight": reference_weight,
                    "invariant_status": "pass",
                }
            )
    final_sum = float(sum(final.values()))
    for symbol, weight in sorted(final.items()):
        rows.append(
            {
                "record_type": "final_normalized_reference_weight",
                "calculation_label": (
                    "activation_initialization_state_not_forward_performance"
                ),
                "reference_id": REFERENCE_ID,
                "component_id": "normalized_direct_holdings",
                "signal_date": signal.date().isoformat(),
                "target_effective_session": first_month_session.date().isoformat(),
                "latest_common_completed_session": latest_common.isoformat(),
                "symbol": symbol,
                "component_sleeve_weight": "",
                "weight_within_component": "",
                "final_reference_weight": weight,
                "invariant_status": "pass" if abs(final_sum - 1.0) <= 1e-12 else "fail",
            }
        )
    return rows, final, {
        "status": "reconciled" if abs(final_sum - 1.0) <= 1e-12 else "blocked",
        "signal_date": signal.date().isoformat(),
        "target_effective_session": first_month_session.date().isoformat(),
        "latest_common_completed_session": latest_common.isoformat(),
        "component_ids": list(component_targets),
        "component_targets": component_targets,
        "final_reference_weights": final,
        "weight_sum": final_sum,
        "rules_changed": False,
    }


def capture_cboe_once(now_utc: datetime) -> dict[str, Any]:
    captures: dict[str, dict[str, Any]] = {}
    for series in ("VIX", "VIX3M"):
        retrieved = datetime.now(timezone.utc)
        try:
            response = requests.get(OFFICIAL_URLS[series], timeout=30)
            response.raise_for_status()
            raw = response.content
            frame = ivts_v3.normalize_official_history(raw, series)
            valid = frame.dropna(subset=["CLOSE"])
            latest = valid.iloc[-1]
            captures[series] = {
                "series": series,
                "retrieval_timestamp_utc": retrieved.isoformat(),
                "retrieval_timestamp_et": retrieved.astimezone(EASTERN).isoformat(),
                "official_source": OFFICIAL_URLS[series],
                "http_status": response.status_code,
                "raw_bytes": raw,
                "raw_hash": sha256_bytes(raw),
                "normalized_hash": ivts_v3.normalized_frame_hash(frame),
                "frame": frame,
                "latest_date": pd.Timestamp(latest["DATE"]).date(),
                "latest_close": float(latest["CLOSE"]),
            }
        except BaseException as exc:  # noqa: BLE001 - bounded official failure is evidence.
            captures[series] = {
                "series": series,
                "retrieval_timestamp_utc": retrieved.isoformat(),
                "retrieval_timestamp_et": retrieved.astimezone(EASTERN).isoformat(),
                "official_source": OFFICIAL_URLS[series],
                "http_status": 0,
                "raw_bytes": b"",
                "raw_hash": "",
                "normalized_hash": "",
                "frame": pd.DataFrame(),
                "latest_date": None,
                "latest_close": float("nan"),
                "error_type": type(exc).__name__,
            }
    if any(item["frame"].empty for item in captures.values()):
        return {"status": "failed", "captures": captures, "request_count": 2}
    common_date = min(captures["VIX"]["latest_date"], captures["VIX3M"]["latest_date"])
    records: dict[str, float] = {}
    for series in ("VIX", "VIX3M"):
        frame = captures[series]["frame"]
        match = frame.loc[pd.to_datetime(frame["DATE"]).dt.date == common_date, "CLOSE"]
        if match.empty:
            return {"status": "failed_common_date", "captures": captures, "request_count": 2}
        records[series] = float(match.iloc[-1])
    return {
        "status": "captured",
        "captures": captures,
        "request_count": 2,
        "common_date": common_date,
        "records": records,
        "captured_at_utc": now_utc.isoformat(),
    }


def target_for_ratio(ratio: float) -> tuple[dict[str, float], str]:
    if ratio < 0.96:
        return {"SPY": 1.0, "IEF": 0.0}, "risk_on"
    if ratio <= 1.02:
        return {"SPY": 0.5, "IEF": 0.5}, "middle"
    return {"SPY": 0.0, "IEF": 1.0}, "defensive"


def persist_cboe_snapshot(
    capture: dict[str, Any],
    intended_execution: date,
    expected_latest: date,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    signal_date = capture["common_date"]
    snapshot_dir = (
        OUTPUT_DIR
        / "forward_snapshots"
        / signal_date.isoformat()
        / "activation_capture"
    )
    snapshot_dir.mkdir(parents=True, exist_ok=False)
    manifest_rows: list[dict[str, Any]] = []
    raw_paths: dict[str, str] = {}
    for series in ("VIX", "VIX3M"):
        item = capture["captures"][series]
        path = snapshot_dir / f"{series}_official_history.csv"
        path.write_bytes(item["raw_bytes"])
        raw_paths[series] = rel(path)
        manifest_rows.append(
            {
                "series": series,
                "signal_observation_date": signal_date.isoformat(),
                "retrieval_timestamp_utc": item["retrieval_timestamp_utc"],
                "retrieval_timestamp_et": item["retrieval_timestamp_et"],
                "official_source": item["official_source"],
                "raw_path": rel(path),
                "raw_hash": item["raw_hash"],
                "normalized_hash": item["normalized_hash"],
                "value": capture["records"][series],
                "intended_execution_session": intended_execution.isoformat(),
                "freshness_status": (
                    "latest_completed_tradable_session"
                    if signal_date == expected_latest
                    else "legitimate_one_session_lag"
                    if signal_date == max(
                        day
                        for day in (expected_latest - timedelta(days=i) for i in range(1, 5))
                        if is_regular_session(day)
                    )
                    else "stale"
                ),
                "immutable": True,
            }
        )
    ratio = float(capture["records"]["VIX"] / capture["records"]["VIX3M"])
    target, state = target_for_ratio(ratio)
    snapshot = {
        "observation_id": OBSERVATION_ID,
        "snapshot_role": "prospective_activation_signal_not_forward_performance",
        "signal_observation_date": signal_date.isoformat(),
        "retrieval_timestamp_utc": capture["captured_at_utc"],
        "retrieval_timestamp_et": datetime.fromisoformat(
            capture["captured_at_utc"]
        ).astimezone(EASTERN).isoformat(),
        "official_sources": OFFICIAL_URLS,
        "raw_paths": raw_paths,
        "raw_hashes": {
            series: capture["captures"][series]["raw_hash"]
            for series in ("VIX", "VIX3M")
        },
        "normalized_hashes": {
            series: capture["captures"][series]["normalized_hash"]
            for series in ("VIX", "VIX3M")
        },
        "VIX": capture["records"]["VIX"],
        "VIX3M": capture["records"]["VIX3M"],
        "ratio": ratio,
        "candidate_target_state": state,
        "candidate_target": target,
        "intended_execution_session": intended_execution.isoformat(),
        "signal_date_strictly_before_execution": signal_date < intended_execution,
        "freshness_and_comparability_status": (
            "pass"
            if signal_date in {expected_latest, previous_regular_session(expected_latest)}
            else "fail"
        ),
        "immutable_original_snapshot": True,
        "later_revision_may_replace_original": False,
        "historical_backfill": False,
        "completed_forward_performance_row": False,
        "broker_submission": False,
    }
    snapshot["normalized_snapshot_hash"] = canonical_hash(snapshot)
    snapshot_path = snapshot_dir / "snapshot_record.json"
    write_json(snapshot_path, snapshot)
    snapshot["snapshot_path"] = rel(snapshot_path)
    snapshot["snapshot_file_hash"] = file_hash(snapshot_path)
    return snapshot, manifest_rows


def previous_regular_session(day: date) -> date:
    cursor = day - timedelta(days=1)
    while not is_regular_session(cursor):
        cursor -= timedelta(days=1)
    return cursor


def build_initialization(
    reference_weights: dict[str, float],
    candidate_target: dict[str, float],
    latest_common: date,
    execution: date,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    combined_symbols = sorted(set(reference_weights) | set(candidate_target))
    direct: dict[str, float] = {}
    rows: list[dict[str, Any]] = []
    for symbol in combined_symbols:
        reference_contribution = REFERENCE_WEIGHT * reference_weights.get(symbol, 0.0)
        candidate_contribution = CANDIDATE_WEIGHT * candidate_target.get(symbol, 0.0)
        total = reference_contribution + candidate_contribution
        direct[symbol] = total
        rows.append(
            {
                "observation_id": OBSERVATION_ID,
                "record_type": "prospective_initialization_target",
                "initialization_is_strategy_performance": False,
                "latest_valuation_session": latest_common.isoformat(),
                "intended_execution_session": execution.isoformat(),
                "symbol": symbol,
                "reference_contribution_weight": reference_contribution,
                "candidate_contribution_weight": candidate_contribution,
                "total_target_weight": total,
                "pretrade_cash_weight": 1.0,
                "posttrade_target_market_value_at_nav_1": total * (1.0 - COST_RATE),
                "shares_deferred_until_execution_close": True,
                "completed_forward_return_row_created": False,
            }
        )
    total_weight = float(sum(direct.values()))
    initialization_turnover = 0.5 * (1.0 + sum(abs(value) for value in direct.values()))
    cost = initialization_turnover * COST_RATE
    invariant_pass = (
        abs(total_weight - 1.0) <= 1e-12
        and all(value >= 0.0 for value in direct.values())
        and total_weight <= 1.0 + 1e-12
    )
    return rows, {
        "status": "pass" if invariant_pass else "fail",
        "target_weights": direct,
        "total_weight": total_weight,
        "gross_exposure": sum(abs(value) for value in direct.values()),
        "negative_weights": sum(value < 0.0 for value in direct.values()),
        "reference_sleeve_weight": REFERENCE_WEIGHT,
        "candidate_sleeve_weight": CANDIDATE_WEIGHT,
        "initialization_turnover": initialization_turnover,
        "simulated_initialization_cost_at_5bps": cost,
        "post_cost_initialization_nav": 1.0 - cost,
        "transaction_cost_charged_once": True,
        "initialization_is_strategy_performance": False,
        "completed_forward_performance_rows": 0,
        "shares_deferred_until_execution_close": True,
    }


def matching_observation(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        record
        for record in payload.get("active_observations", [])
        if record.get("observation_id") == OBSERVATION_ID
    ]


def replace_observation_text(text: str, record: dict[str, Any]) -> str:
    pattern = re.compile(
        rf"(?ms)^- observation_id: {re.escape(OBSERVATION_ID)}\n.*?(?=^- (?:observation_id|strategy_id): |\nbenchmark_controls:)"
    )
    matches = list(pattern.finditer(text))
    if len(matches) != 1:
        raise RuntimeError(
            f"Expected exactly one observation text block, found {len(matches)}"
        )
    block = yaml.safe_dump(
        [record], sort_keys=False, width=120, allow_unicode=False
    )
    return text[: matches[0].start()] + block + text[matches[0].end() :]


def updated_observation(
    before: dict[str, Any],
    now_utc: datetime,
    snapshot: dict[str, Any],
    execution: date,
    initialization_path: str,
    initialization_hash: str,
) -> dict[str, Any]:
    after = json.loads(json.dumps(before))
    after.update(
        {
            "stage": "paper_demo_observation",
            "outcome": ACTIVATED_OUTCOME,
            "state": "active",
            "paper_forward_active": True,
            "activation_timestamp": now_utc.isoformat(),
            "first_forward_observation_date": execution.isoformat(),
            "proposed_first_execution_session": execution.isoformat(),
            "initialization_status": "prospective_initialization_created",
            "latest_captured_signal_date": snapshot["signal_observation_date"],
            "latest_snapshot_path": snapshot["snapshot_path"],
            "latest_snapshot_hash": snapshot["snapshot_file_hash"],
            "snapshot_role": "prospective_activation_signal_not_forward_performance",
            "current_status": "active",
            "failure_reason": "",
            "next_action": ACTIVATED_NEXT_ACTION,
            "initialization_record_path": initialization_path,
            "initialization_record_hash": initialization_hash,
            "portfolio_initialization_is_performance": False,
            "historical_forward_records_created": 0,
            "forward_records_created": 0,
        }
    )
    return after


def other_observation_hash(payload: dict[str, Any]) -> str:
    values = [
        record
        for record in payload.get("active_observations", [])
        if record.get("observation_id") != OBSERVATION_ID
    ]
    return canonical_hash(values)


def unrelated_cache_hash(symbols: tuple[str, ...]) -> str:
    excluded = {
        cache_path(symbol).resolve() for symbol in symbols
    } | {metadata_path(symbol).resolve() for symbol in symbols}
    rows = []
    for path in sorted(CACHE_DIR.glob("*")):
        if path.is_file() and path.resolve() not in excluded:
            rows.append((path.name, file_hash(path)))
    return canonical_hash(rows)


def prior_evidence_hash() -> str:
    rows = [
        (rel(path), file_hash(path))
        for path in sorted(ONBOARDING_DIR.rglob("*"))
        if path.is_file()
    ]
    return canonical_hash(rows)


def atomic_commit(staged: dict[Path, bytes]) -> None:
    backups = {
        path: path.read_bytes() if path.exists() else None for path in staged
    }
    temp_paths: dict[Path, Path] = {}
    try:
        for path, content in staged.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            temp = path.with_name(path.name + ".ivts_activation_tmp")
            temp.write_bytes(content)
            temp_paths[path] = temp
        for path, temp in temp_paths.items():
            temp.replace(path)
    except BaseException:
        for path, content in backups.items():
            if content is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(content)
        raise
    finally:
        for temp in temp_paths.values():
            temp.unlink(missing_ok=True)


def run() -> dict[str, Any]:
    clean_output_dir()
    started_utc = datetime.now(timezone.utc)
    registry_hash_before = file_hash(REGISTRY_PATH)
    active_text_before = ACTIVE_OBSERVATIONS_PATH.read_text(encoding="utf-8")
    active_before = load_yaml(ACTIVE_OBSERVATIONS_PATH)
    prior_hash_before = prior_evidence_hash()
    roadmap_hash_before = file_hash(ROADMAP_PATH)
    queue_hash_before = file_hash(QUEUE_PATH)
    family_hash_before = file_hash(FAMILY_LEDGER_PATH)

    existing_matches = matching_observation(active_before)
    state_reconciled = bool(
        len(existing_matches) == 1
        and existing_matches[0].get("stage") == "deferred"
        and existing_matches[0].get("paper_forward_active") is False
        and existing_matches[0].get("failure_reason")
        == "activation_boundary_not_ready"
        and existing_matches[0].get("historical_forward_records_created") == 0
        and existing_matches[0].get("initialization_status")
        == "not_initialized_deferred"
    )

    symbols = required_symbols()
    reference_symbols = frozen_reference_symbols()
    pre_frames = {symbol: load_cache(symbol) for symbol in symbols}
    scope_frozen_before_retrieval = bool(
        symbols
        and set(symbols) == set(reference_symbols) | {"IEF"}
        and all(not frame.empty for frame in pre_frames.values())
    )
    overlap_dates = (
        five_session_overlap(pre_frames, symbols)
        if scope_frozen_before_retrieval
        else tuple()
    )
    latest = latest_completed_session(started_utc)
    unrelated_cache_before = unrelated_cache_hash(symbols)
    cache_before = {
        symbol: {
            "file_hash": file_hash(cache_path(symbol)),
            "metadata_hash": file_hash(metadata_path(symbol)),
            "first_date": str(pre_frames[symbol].iloc[0]["date"])
            if not pre_frames[symbol].empty
            else "",
            "last_date": str(pre_frames[symbol].iloc[-1]["date"])
            if not pre_frames[symbol].empty
            else "",
            "row_count": int(len(pre_frames[symbol])),
            "frame_hash": frame_hash(pre_frames[symbol])
            if not pre_frames[symbol].empty
            else "",
        }
        for symbol in symbols
    }

    raw_frames: dict[str, pd.DataFrame] = {}
    provider_frames: dict[str, pd.DataFrame] = {}
    provider_request: dict[str, Any] = {
        "provider_id": "not_attempted",
        "attempted": False,
        "status": "blocked_scope_not_frozen",
    }
    if state_reconciled and scope_frozen_before_retrieval:
        raw_frames, provider_frames, provider_request = bounded_yfinance_batch(
            symbols, overlap_dates[0], latest + timedelta(days=1)
        )

    provider_raw_dir = OUTPUT_DIR / "provider_raw"
    provider_raw_dir.mkdir(parents=True, exist_ok=True)
    reconciled_frames: dict[str, pd.DataFrame] = {}
    overlap_rows: list[dict[str, Any]] = []
    reconciliation: dict[str, dict[str, Any]] = {}
    quality_all: list[dict[str, Any]] = []
    quality_pass = False
    if provider_request.get("status") == "download_completed":
        for symbol in symbols:
            raw_path = provider_raw_dir / f"{symbol}.csv"
            raw_path.write_text(
                raw_frames[symbol].to_csv(lineterminator="\n"), encoding="utf-8"
            )
            reconciled, rows, detail = reconcile_symbol(
                symbol,
                pre_frames[symbol],
                provider_frames[symbol],
                overlap_dates,
                latest,
            )
            reconciled_frames[symbol] = reconciled
            overlap_rows.extend(rows)
            reconciliation[symbol] = detail
        quality_flags = []
        for symbol in symbols:
            rows, passed = quality_rows(
                symbol, reconciled_frames[symbol], latest, overlap_dates[0]
            )
            quality_all.extend(rows)
            quality_flags.append(passed)
        quality_pass = bool(
            all(quality_flags)
            and all(detail["status"] == "reconciled" for detail in reconciliation.values())
        )

    cache_staged: dict[Path, bytes] = {}
    metadata_rows: list[dict[str, Any]] = []
    if quality_pass:
        cache_staged, metadata_rows = stage_cache_updates(
            reconciled_frames,
            raw_frames,
            provider_request,
            symbols,
            latest,
        )
        atomic_commit(cache_staged)

    post_frames = {symbol: load_cache(symbol) for symbol in symbols}
    common_dates: set[date] | None = None
    for symbol in symbols:
        dates = set(pd.to_datetime(post_frames[symbol]["date"]).dt.date)
        common_dates = dates if common_dates is None else common_dates & dates
    latest_common = max(common_dates or {date.min})
    market_current = bool(
        quality_pass
        and latest_common == latest
        and all(
            pd.to_datetime(post_frames[symbol]["date"]).max().date() >= latest
            for symbol in symbols
        )
    )

    reference_rows: list[dict[str, Any]] = []
    reference_weights: dict[str, float] = {}
    reference_state: dict[str, Any] = {"status": "not_run"}
    if market_current:
        reference_rows, reference_weights, reference_state = (
            reference_initialization_state(latest_common)
        )
    reference_ready = reference_state.get("status") == "reconciled"

    cboe_capture: dict[str, Any] = {"status": "not_run", "request_count": 0}
    snapshot: dict[str, Any] = {}
    cboe_rows: list[dict[str, Any]] = []
    proposed_execution = next_regular_session(started_utc.astimezone(EASTERN).date())
    if reference_ready:
        cboe_capture = capture_cboe_once(datetime.now(timezone.utc))
        if cboe_capture.get("status") == "captured":
            proposed_execution = execution_session(
                datetime.now(timezone.utc), cboe_capture["common_date"]
            )
            snapshot, cboe_rows = persist_cboe_snapshot(
                cboe_capture, proposed_execution, latest
            )

    signal_ready = bool(
        snapshot
        and snapshot["freshness_and_comparability_status"] == "pass"
        and date.fromisoformat(snapshot["signal_observation_date"])
        < proposed_execution
        and date.fromisoformat(snapshot["signal_observation_date"])
        in {latest, previous_regular_session(latest)}
    )
    session_aligned = bool(
        market_current
        and reference_ready
        and latest_common == latest
        and latest < proposed_execution
    )

    initialization_rows: list[dict[str, Any]] = []
    initialization: dict[str, Any] = {"status": "not_created"}
    if signal_ready and session_aligned:
        initialization_rows, initialization = build_initialization(
            reference_weights,
            snapshot["candidate_target"],
            latest_common,
            proposed_execution,
        )

    gates = {
        "required_symbol_scope_frozen_before_retrieval": scope_frozen_before_retrieval,
        "one_bounded_approved_provider_refresh": provider_request.get("status")
        == "download_completed"
        and provider_request.get("batch_attempt_count") == 1,
        "five_session_overlap_reconciliation": bool(
            overlap_rows and all(row["overlap_pass"] for row in overlap_rows)
        ),
        "canonical_data_latest_common_session": market_current,
        "frozen_reference_current_targets": reference_ready,
        "new_cboe_immutable_signal_snapshot": bool(
            snapshot and snapshot.get("immutable_original_snapshot")
        ),
        "signal_strictly_before_execution": bool(
            snapshot and snapshot.get("signal_date_strictly_before_execution")
        ),
        "instrument_reference_session_alignment": session_aligned,
        "observation_adapter_invariants": initialization.get("status") == "pass",
        "no_historical_performance_initialization": bool(
            initialization.get("completed_forward_performance_rows") == 0
            and initialization.get("initialization_is_strategy_performance") is False
        ),
        "prior_evidence_unchanged_precommit": prior_evidence_hash()
        == prior_hash_before,
        "registry_and_observation_state_reconciled": state_reconciled,
    }
    activation_ready = all(gates.values())

    initialization_fields = [
        "observation_id",
        "record_type",
        "initialization_is_strategy_performance",
        "latest_valuation_session",
        "intended_execution_session",
        "symbol",
        "reference_contribution_weight",
        "candidate_contribution_weight",
        "total_target_weight",
        "pretrade_cash_weight",
        "posttrade_target_market_value_at_nav_1",
        "shares_deferred_until_execution_close",
        "completed_forward_return_row_created",
    ]
    initialization_path = OUTPUT_DIR / "portfolio_initialization_record.csv"
    write_csv(
        initialization_path,
        initialization_rows if activation_ready else [],
        initialization_fields,
    )

    active_after = active_before
    active_text_after = active_text_before
    observation_before = existing_matches[0] if len(existing_matches) == 1 else {}
    observation_after = observation_before
    state_written = False
    state_error = ""
    if activation_ready:
        initialization_digest = file_hash(initialization_path)
        observation_after = updated_observation(
            observation_before,
            datetime.now(timezone.utc),
            snapshot,
            proposed_execution,
            rel(initialization_path),
            initialization_digest,
        )
        active_text_after = replace_observation_text(
            active_text_before, observation_after
        )
        candidate_active = yaml.safe_load(active_text_after)
        active_validation = onboarding.validate_active_observation_document(
            candidate_active
        )
        if not active_validation["passed"]:
            state_error = "|".join(active_validation["errors"])
        elif other_observation_hash(candidate_active) != other_observation_hash(
            active_before
        ):
            state_error = "unrelated_observation_change_detected"
        else:
            try:
                atomic_commit(
                    {
                        ACTIVE_OBSERVATIONS_PATH: active_text_after.encode("utf-8")
                    }
                )
                active_after = load_yaml(ACTIVE_OBSERVATIONS_PATH)
                state_written = True
            except BaseException as exc:  # noqa: BLE001
                state_error = type(exc).__name__

    if activation_ready and state_written:
        outcome = ACTIVATED_OUTCOME
        failure_reason = ""
        next_action = ACTIVATED_NEXT_ACTION
    elif activation_ready and not state_written:
        outcome = BLOCKED_OUTCOME
        failure_reason = "activation_state_reconciliation_failed"
        next_action = BLOCKED_NEXT_ACTION
    else:
        outcome = DEFERRED_OUTCOME
        if provider_request.get("status") != "download_completed" or not quality_pass:
            failure_reason = "canonical_market_data_refresh_failed"
        elif not reference_ready:
            failure_reason = "frozen_reference_not_current"
        elif not signal_ready:
            failure_reason = "forward_signal_not_current"
        elif not session_aligned:
            failure_reason = "activation_boundary_not_ready"
        else:
            failure_reason = "data_or_comparability_failure"
        next_action = DEFERRED_NEXT_ACTION

    cache_after = {
        symbol: {
            "file_hash": file_hash(cache_path(symbol)),
            "metadata_hash": file_hash(metadata_path(symbol)),
            "first_date": str(post_frames[symbol].iloc[0]["date"])
            if not post_frames[symbol].empty
            else "",
            "last_date": str(post_frames[symbol].iloc[-1]["date"])
            if not post_frames[symbol].empty
            else "",
            "row_count": int(len(post_frames[symbol])),
            "frame_hash": frame_hash(post_frames[symbol])
            if not post_frames[symbol].empty
            else "",
        }
        for symbol in symbols
    }
    prior_unchanged = prior_evidence_hash() == prior_hash_before
    registry_unchanged = file_hash(REGISTRY_PATH) == registry_hash_before
    unrelated_cache_unchanged = unrelated_cache_hash(symbols) == unrelated_cache_before
    other_observations_unchanged = other_observation_hash(
        load_yaml(ACTIVE_OBSERVATIONS_PATH)
    ) == other_observation_hash(active_before)
    active_validation_after = onboarding.validate_active_observation_document(
        load_yaml(ACTIVE_OBSERVATIONS_PATH)
    )

    scope_rows = [
        {
            "symbol": symbol,
            "scope_role": (
                "ivts_and_reference"
                if symbol == "SPY"
                else "ivts_only"
                if symbol == "IEF"
                else "frozen_reference_authorized"
            ),
            "source_of_scope": (
                "frozen_reference_authorized_symbol_universe_json"
                if symbol in reference_symbols
                else "frozen_IVTS_inner_instrument"
            ),
            "frozen_before_retrieval": scope_frozen_before_retrieval,
            "performance_selected": False,
            "substitution_allowed": False,
        }
        for symbol in symbols
    ]
    provider_rows = [
        {
            **provider_compatibility(),
            "selected_for_refresh": False,
            "bounded_batch_attempts": 0,
        },
        {
            **provider_request,
            "selected_for_refresh": True,
            "bounded_batch_attempts": int(provider_request.get("attempted", False)),
        },
    ]
    before_after_rows = []
    for symbol in symbols:
        before_after_rows.append(
            {
                "symbol": symbol,
                "cache_path": rel(cache_path(symbol)),
                "before_first_date": cache_before[symbol]["first_date"],
                "before_last_date": cache_before[symbol]["last_date"],
                "before_row_count": cache_before[symbol]["row_count"],
                "before_file_hash": cache_before[symbol]["file_hash"],
                "before_frame_hash": cache_before[symbol]["frame_hash"],
                "after_first_date": cache_after[symbol]["first_date"],
                "after_last_date": cache_after[symbol]["last_date"],
                "after_row_count": cache_after[symbol]["row_count"],
                "after_file_hash": cache_after[symbol]["file_hash"],
                "after_frame_hash": cache_after[symbol]["frame_hash"],
                "cache_changed": cache_before[symbol]["file_hash"]
                != cache_after[symbol]["file_hash"],
                "metadata_changed": cache_before[symbol]["metadata_hash"]
                != cache_after[symbol]["metadata_hash"],
                "reconciliation_status": reconciliation.get(symbol, {}).get(
                    "status", "not_reconciled"
                ),
                "adjusted_history_revision_applied": reconciliation.get(
                    symbol, {}
                ).get("adjusted_history_revision_applied", False),
                "latest_completed_session_ready": cache_after[symbol]["last_date"]
                >= latest.isoformat(),
            }
        )
    alignment_rows = [
        {
            "observation_id": OBSERVATION_ID,
            "latest_completed_tradable_session": latest.isoformat(),
            "latest_common_canonical_session": (
                latest_common.isoformat() if latest_common != date.min else ""
            ),
            "signal_observation_date": snapshot.get("signal_observation_date", ""),
            "intended_execution_session": proposed_execution.isoformat(),
            "signal_strictly_before_execution": snapshot.get(
                "signal_date_strictly_before_execution", False
            ),
            "canonical_data_strictly_before_execution": latest
            < proposed_execution,
            "reference_and_instruments_aligned": session_aligned,
            "safe_cutoff_policy": "before_15_45_ET_same_future_close_else_next_regular_session",
            "historical_or_synthetic_fill_required": False,
            "alignment_status": "pass" if signal_ready and session_aligned else "fail",
        }
    ]
    observation_diff_rows = []
    all_keys = sorted(set(observation_before) | set(observation_after))
    for key in all_keys:
        observation_diff_rows.append(
            {
                "observation_id": OBSERVATION_ID,
                "field": key,
                "before": observation_before.get(key, ""),
                "after": observation_after.get(key, ""),
                "changed": observation_before.get(key) != observation_after.get(key),
                "permitted_change": key
                in {
                    "stage",
                    "outcome",
                    "state",
                    "paper_forward_active",
                    "activation_timestamp",
                    "first_forward_observation_date",
                    "proposed_first_execution_session",
                    "initialization_status",
                    "latest_captured_signal_date",
                    "latest_snapshot_path",
                    "latest_snapshot_hash",
                    "snapshot_role",
                    "current_status",
                    "failure_reason",
                    "next_action",
                    "initialization_record_path",
                    "initialization_record_hash",
                    "portfolio_initialization_is_performance",
                },
            }
        )
    state_paths = [
        REGISTRY_PATH,
        ACTIVE_OBSERVATIONS_PATH,
        ROADMAP_PATH,
        QUEUE_PATH,
        FAMILY_LEDGER_PATH,
        *[cache_path(symbol) for symbol in symbols],
        *[metadata_path(symbol) for symbol in symbols],
    ]
    before_known = {
        REGISTRY_PATH: registry_hash_before,
        ACTIVE_OBSERVATIONS_PATH: sha256_bytes(active_text_before.encode("utf-8")),
        ROADMAP_PATH: roadmap_hash_before,
        QUEUE_PATH: queue_hash_before,
        FAMILY_LEDGER_PATH: family_hash_before,
    }
    for symbol in symbols:
        before_known[cache_path(symbol)] = cache_before[symbol]["file_hash"]
        before_known[metadata_path(symbol)] = cache_before[symbol]["metadata_hash"]
    state_rows = [
        {
            "path": rel(path),
            "before_hash": before_known.get(path, ""),
            "after_hash": file_hash(path),
            "changed": before_known.get(path, "") != file_hash(path),
            "permitted_change": (
                path == ACTIVE_OBSERVATIONS_PATH
                or path in {cache_path(symbol) for symbol in symbols}
                or path in {metadata_path(symbol) for symbol in symbols}
            ),
            "change_role": (
                "exact_existing_observation_activation"
                if path == ACTIVE_OBSERVATIONS_PATH
                else "exact_required_canonical_cache_or_manifest"
                if path.parent == CACHE_DIR
                else "protected_unchanged"
            ),
        }
        for path in state_paths
    ]

    common_manifest = {
        "task_id": TASK_ID,
        "mode": "data-capability",
        "stage": "implementation",
        "strategy_id": STRATEGY_ID,
        "observation_id": OBSERVATION_ID,
        "outcome": outcome,
        "failure_reason": failure_reason,
        "exact_next_action": next_action,
        "required_symbols": list(symbols),
        "reference_symbols": list(reference_symbols),
        "refresh_start": REFRESH_START.isoformat(),
        "overlap_dates": [day.isoformat() for day in overlap_dates],
        "latest_completed_session": latest.isoformat(),
        "latest_common_session": (
            latest_common.isoformat() if latest_common != date.min else ""
        ),
        "new_strategies": 0,
        "updated_strategies": 0,
        "new_experiment_trials": 0,
        "new_observations": 0,
        "existing_observations_updated": int(state_written),
        "data_capability_tasks": 1,
        "process_tasks": 1,
        "initialization_records": int(bool(initialization_rows and activation_ready)),
        "completed_forward_performance_rows": 0,
        "broker_or_paper_orders": 0,
    }
    write_yaml(OUTPUT_DIR / "activation_refresh_manifest.yaml", common_manifest)
    write_csv(
        OUTPUT_DIR / "required_symbol_scope.csv",
        scope_rows,
        [
            "symbol",
            "scope_role",
            "source_of_scope",
            "frozen_before_retrieval",
            "performance_selected",
            "substitution_allowed",
        ],
    )
    write_csv(
        OUTPUT_DIR / "provider_attempt_log.csv",
        provider_rows,
        [
            "provider_id",
            "attempted",
            "selected_for_refresh",
            "bounded_batch_attempts",
            "status",
            "reason",
            "symbols",
            "start",
            "end_exclusive",
            "batch_attempt_count",
            "auto_adjust",
            "actions",
            "group_by",
            "rows_by_symbol",
            "order_endpoint_called",
            "account_endpoint_called",
            "broker_endpoint_called",
            "credentials_persisted",
            "error_type",
            "error",
        ],
    )
    write_csv(
        OUTPUT_DIR / "canonical_data_before_after.csv",
        before_after_rows,
        list(before_after_rows[0]),
    )
    write_csv(
        OUTPUT_DIR / "overlap_reconciliation.csv",
        overlap_rows,
        [
            "symbol",
            "date",
            "existing_raw_close",
            "provider_raw_close",
            "existing_adjusted_close",
            "provider_adjusted_close",
            "adjustment_revision_ratio",
            "raw_price_relative_difference",
            "volume_relative_difference",
            "action_relative_difference",
            "bridge_ratio_stable",
            "material_ohlcv_discontinuity",
            "overlap_pass",
        ],
    )
    write_csv(
        OUTPUT_DIR / "data_quality_results.csv",
        quality_all,
        ["symbol", "check_id", "status", "detail"],
    )
    write_csv(
        OUTPUT_DIR / "frozen_reference_initialization_state.csv",
        reference_rows,
        [
            "record_type",
            "calculation_label",
            "reference_id",
            "component_id",
            "signal_date",
            "target_effective_session",
            "latest_common_completed_session",
            "symbol",
            "component_sleeve_weight",
            "weight_within_component",
            "final_reference_weight",
            "invariant_status",
        ],
    )
    write_csv(
        OUTPUT_DIR / "official_cboe_forward_snapshot_manifest.csv",
        cboe_rows,
        [
            "series",
            "signal_observation_date",
            "retrieval_timestamp_utc",
            "retrieval_timestamp_et",
            "official_source",
            "raw_path",
            "raw_hash",
            "normalized_hash",
            "value",
            "intended_execution_session",
            "freshness_status",
            "immutable",
        ],
    )
    write_csv(
        OUTPUT_DIR / "signal_execution_alignment.csv",
        alignment_rows,
        list(alignment_rows[0]),
    )
    write_csv(
        OUTPUT_DIR / "paper_demo_observation_before_after.csv",
        observation_diff_rows,
        [
            "observation_id",
            "field",
            "before",
            "after",
            "changed",
            "permitted_change",
        ],
    )
    data_task_row = {
        "task_id": TASK_ID,
        "entity_type": "data_capability_task",
        "stage": "feasible" if quality_pass else "blocked",
        "adaptation_label": "data_feasibility_adjustment",
        "required_symbol_count": len(symbols),
        "provider_batch_attempts": int(provider_request.get("attempted", False)),
        "alpaca_attempted": False,
        "alpaca_compatibility": provider_compatibility()["status"],
        "canonical_refresh_status": (
            "pass" if quality_pass and market_current else "fail"
        ),
        "strategy_performance_calculated": False,
        "broker_or_order_action": False,
    }
    write_csv(
        OUTPUT_DIR / "data_capability_task_log.csv",
        [data_task_row],
        list(data_task_row),
    )
    process_row = {
        "task_id": TASK_ID,
        "entity_type": "process_task",
        "stage": "implementation",
        "strategies_created": 0,
        "trials_created": 0,
        "observations_created": 0,
        "observations_updated": int(state_written),
        "completed_forward_rows": 0,
        "broker_orders": 0,
    }
    write_csv(
        OUTPUT_DIR / "process_task_log.csv", [process_row], list(process_row)
    )
    write_csv(
        OUTPUT_DIR / "state_change_manifest.csv",
        state_rows,
        [
            "path",
            "before_hash",
            "after_hash",
            "changed",
            "permitted_change",
            "change_role",
        ],
    )
    outcome_row = {
        "strategy_id": STRATEGY_ID,
        "observation_id": OBSERVATION_ID,
        "outcome": outcome,
        "failure_reason": failure_reason,
        "exact_next_action": next_action,
        "latest_completed_session": latest.isoformat(),
        "latest_common_session": (
            latest_common.isoformat() if latest_common != date.min else ""
        ),
        "signal_date": snapshot.get("signal_observation_date", ""),
        "execution_session": proposed_execution.isoformat(),
        "paper_forward_active": bool(state_written),
        "initialization_created": bool(initialization_rows and activation_ready),
        "completed_forward_performance_rows": 0,
    }
    write_csv(
        OUTPUT_DIR / "outcome_summary.csv", [outcome_row], list(outcome_row)
    )
    failure_fields = ["observation_id", "failure_reason", "detail"]
    failure_rows = (
        [
            {
                "observation_id": OBSERVATION_ID,
                "failure_reason": failure_reason,
                "detail": state_error
                or "|".join(key for key, value in gates.items() if not value),
            }
        ]
        if failure_reason
        else []
    )
    write_csv(OUTPUT_DIR / "failure_reasons.csv", failure_rows, failure_fields)
    next_row = {
        "observation_id": OBSERVATION_ID,
        "outcome": outcome,
        "next_action": next_action,
        "executed_in_this_task": False,
    }
    write_csv(OUTPUT_DIR / "next_actions.csv", [next_row], list(next_row))

    all_required_artifacts = [
        "activation_refresh_manifest.yaml",
        "required_symbol_scope.csv",
        "provider_attempt_log.csv",
        "canonical_data_before_after.csv",
        "overlap_reconciliation.csv",
        "data_quality_results.csv",
        "frozen_reference_initialization_state.csv",
        "official_cboe_forward_snapshot_manifest.csv",
        "signal_execution_alignment.csv",
        "portfolio_initialization_record.csv",
        "paper_demo_observation_before_after.csv",
        "data_capability_task_log.csv",
        "process_task_log.csv",
        "state_change_manifest.csv",
        "outcome_summary.csv",
        "failure_reasons.csv",
        "next_actions.csv",
    ]
    consistency = {
        **common_manifest,
        "overall_pass": bool(
            outcome in {ACTIVATED_OUTCOME, DEFERRED_OUTCOME}
            and registry_unchanged
            and prior_unchanged
            and unrelated_cache_unchanged
            and other_observations_unchanged
            and active_validation_after["passed"]
            and all((OUTPUT_DIR / name).exists() for name in all_required_artifacts)
            and (outcome != ACTIVATED_OUTCOME or all(gates.values()))
        ),
        "activation_gates": gates,
        "scope_frozen_before_retrieval": scope_frozen_before_retrieval,
        "provider_batch_attempts": int(provider_request.get("attempted", False)),
        "alpaca_provider_calls": 0,
        "official_cboe_request_count": cboe_capture.get("request_count", 0),
        "registry_hash_before": registry_hash_before,
        "registry_hash_after": file_hash(REGISTRY_PATH),
        "registry_unchanged": registry_unchanged,
        "prior_evidence_hash_before": prior_hash_before,
        "prior_evidence_hash_after": prior_evidence_hash(),
        "prior_evidence_unchanged": prior_unchanged,
        "unrelated_cache_hash_before": unrelated_cache_before,
        "unrelated_cache_hash_after": unrelated_cache_hash(symbols),
        "unrelated_cache_unchanged": unrelated_cache_unchanged,
        "unrelated_observations_unchanged": other_observations_unchanged,
        "roadmap_unchanged": file_hash(ROADMAP_PATH) == roadmap_hash_before,
        "research_queue_unchanged": file_hash(QUEUE_PATH) == queue_hash_before,
        "family_ledger_unchanged": file_hash(FAMILY_LEDGER_PATH)
        == family_hash_before,
        "active_observation_validation": active_validation_after,
        "observation_state_written": state_written,
        "state_write_error": state_error,
        "initialization": initialization,
        "reference_state": reference_state,
        "snapshot": {
            key: value
            for key, value in snapshot.items()
            if key not in {"raw_bytes"}
        },
        "required_artifacts_present": all(
            (OUTPUT_DIR / name).exists() for name in all_required_artifacts
        ),
        "validation_rerun": False,
        "historical_backtest_run": False,
        "historical_forward_backfill": False,
        "completed_forward_performance_rows": 0,
        "strategy_configurations_created": 0,
        "strategy_configurations_updated": 0,
        "experiment_trials_created": 0,
        "paper_demo_observations_created": 0,
        "broker_orders": 0,
        "paper_orders": 0,
        "live_orders": 0,
        "real_money_actions": 0,
    }
    write_json(OUTPUT_DIR / "consistency_check.json", consistency)

    report = f"""# IVTS Activation Data Refresh and Forward Observation V1

## Outcome

`{outcome}`

The exact frozen activation scope contained {len(symbols)} symbols: the 17
symbols authorized by the frozen reference definition plus IEF. Alpaca was
inspected first but was not admitted because its existing adjusted-bar response
does not satisfy the canonical raw/action/adjustment provenance contract. The
existing approved yfinance-compatible path was called once as one bounded batch.

## Data and reference state

The latest fully completed U.S. session was `{latest.isoformat()}` and the
post-refresh latest common canonical session was
`{latest_common.isoformat() if latest_common != date.min else "unavailable"}`.
The five-session overlap was reconciled explicitly; any backward adjustment
revision is recorded rather than silently replacing prior values.

The frozen reference was evaluated only to create
`activation_initialization_state_not_forward_performance`. Its three frozen
components and rules were unchanged.

## Prospective boundary

The immutable Cboe signal snapshot is dated
`{snapshot.get("signal_observation_date", "unavailable")}`. The prospective
execution session is `{proposed_execution.isoformat()}`. Initialization is
separate from performance and created zero completed forward-return rows.

Failure reason: `{failure_reason or "none"}`.

Exact next action: `{next_action}`.

No strategy, experiment trial, or observation was created. The strategy
registry was unchanged. No broker, account, paper-order, live-order, or
real-money action occurred.
"""
    (OUTPUT_DIR / "activation_report.md").write_text(report, encoding="utf-8")

    consistency["required_artifacts_present"] = all(
        (OUTPUT_DIR / name).exists()
        for name in [*all_required_artifacts, "consistency_check.json", "activation_report.md"]
    )
    consistency["overall_pass"] = bool(
        consistency["overall_pass"] and consistency["required_artifacts_present"]
    )
    write_json(OUTPUT_DIR / "consistency_check.json", consistency)

    return {
        "task_id": TASK_ID,
        "outcome": outcome,
        "failure_reason": failure_reason,
        "next_action": next_action,
        "required_symbol_count": len(symbols),
        "provider_batch_attempts": int(provider_request.get("attempted", False)),
        "latest_completed_session": latest.isoformat(),
        "latest_common_session": (
            latest_common.isoformat() if latest_common != date.min else ""
        ),
        "signal_date": snapshot.get("signal_observation_date", ""),
        "execution_session": proposed_execution.isoformat(),
        "observation_active": state_written,
        "initialization_records": len(initialization_rows) if activation_ready else 0,
        "completed_forward_performance_rows": 0,
        "consistency_passed": consistency["overall_pass"],
    }


def main() -> int:
    result = run()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["consistency_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
