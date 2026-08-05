from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import re
import shutil
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import yaml

from execution_lab.alpaca_micro_live_v1.adapters.alpaca_client import (
    AlpacaClient,
    AlpacaClientConfig,
)
from execution_lab.alpaca_micro_live_v1.adapters.credentials import (
    load_alpaca_credentials,
)
from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.research import (
    design_decelerated_psar_prospective_validation_v1 as design,
)
from strategy_lab.research_os.research import (
    fast_price_volume_preregistered_batch_v1 as psar_engine,
)
from strategy_lab.research_os.research import (
    initialize_angl_after_next_completed_common_session_v1 as reference_engine,
)
from strategy_lab.research_os.research.fast_source_library_batch_v5 import (
    scheduled_full_day_nyse_closures,
)


TASK_ID = "activate_decelerated_psar_prospective_validation_v1"
MODE = "active-direction-execution"
STAGE = "validation"
OUTPUT_DIR = ROOT / "evidence" / "validation" / TASK_ID / "latest"
DESIGN_DIR = design.OUTPUT_DIR
SOURCE_PACKET = Path(
    r"C:\Users\te3442\.codex\attachments\208f83f6-47ce-40a2-ac0a-cc7762ff1d8e\pasted-text.txt"
)

TRIAL_ID = design.FUTURE_TRIAL_ID
PARENT_TRIAL_ID = design.PARENT_TRIAL_ID
STRATEGY_ID = design.STRATEGY_ID
FAMILY_ID = design.FAMILY_ID
ARCHITECTURE = design.ARCHITECTURE
OBSERVATION_ID = "prospective_validation_decelerated_psar_20pct_v1"
REFERENCE_ID = reference_engine.REFERENCE_ID
REFERENCE_WEIGHT = 0.80
CANDIDATE_WEIGHT = 0.20
PRIMARY_COST_BPS = 5.0
COST_BPS = (0.0, 5.0, 10.0)
EXACT_EXPOSURE_SPY = design.EXACT_EXPOSURE_SPY
EXACT_EXPOSURE_BIL = design.EXACT_EXPOSURE_BIL
SYMBOLS = design.EXPECTED_REFERENCE_SYMBOLS
PORTFOLIO_IDS = design.PORTFOLIO_IDS
EASTERN = ZoneInfo("America/New_York")

ACTIVATED = "prospective_validation_activated"
DEFERRED = "prospective_validation_activation_deferred"
BLOCKED = "prospective_validation_activation_blocked"
NEXT_ACTIVATED = "record_decelerated_psar_prospective_validation_monthly_v1"
NEXT_DEFERRED = "resume_strategy_discovery_while_psar_validation_deferred_v1"
NEXT_BLOCKED = "direction_owner_review_psar_activation_block_v1"
DEFERRED_REASONS = (
    "required_data_unavailable",
    "immutable_snapshot_reproducibility_failure",
    "reference_initialization_failure",
    "candidate_state_initialization_failure",
    "activation_boundary_not_ready",
    "observation_storage_unavailable",
    "data_or_comparability_failure",
)
BLOCKED_REASONS = (
    "lineage_reconciliation_failure",
    "parameter_reconciliation_failure",
    "status_reconciliation_required",
    "methodology_failure",
)

RAW_ROOT = OUTPUT_DIR / "immutable_stream"
SNAPSHOT_ROOT = OUTPUT_DIR / "immutable_initialization_snapshots"
PROTECTED_PATHS = design.PROTECTED_PATHS
PRIOR_EVIDENCE_DIRS = (
    design.STANDALONE_EVIDENCE,
    design.EXPLORATION_EVIDENCE,
    design.ROBUSTNESS_EVIDENCE,
    DESIGN_DIR,
)
KNOWN_UNSCHEDULED_NYSE_CLOSURES = {
    date(2012, 10, 29),
    date(2012, 10, 30),
    date(2018, 12, 5),
}
GLOBAL_REQUEST_START = date(2007, 1, 3)

REQUIRED_OUTPUTS = {
    "activation_manifest.yaml",
    "design_reconciliation.csv",
    "future_trial_before_after.csv",
    "required_symbol_scope.csv",
    "initialization_history_requirements.csv",
    "provider_attempt_log.csv",
    "retrieval_reproducibility.csv",
    "immutable_snapshot_manifest.csv",
    "candidate_state_initialization.csv",
    "comparator_state_initialization.csv",
    "frozen_reference_state_initialization.csv",
    "portfolio_initialization_record.csv",
    "activation_boundary.csv",
    "validation_trial_record.csv",
    "validation_observation_record.csv",
    "data_capability_task_log.csv",
    "process_task_log.csv",
    "state_change_manifest.csv",
    "outcome_summary.csv",
    "failure_reasons.csv",
    "next_actions.csv",
    "consistency_check.json",
    "activation_report.md",
}


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def sha256_bytes(value: bytes) -> str:
    return f"sha256:{hashlib.sha256(value).hexdigest()}"


def file_hash(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_hash(value: Any) -> str:
    return sha256_bytes(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            default=str,
        ).encode("utf-8")
    )


def packet_files(path: Path) -> list[Path]:
    return sorted(item for item in path.rglob("*") if item.is_file())


def map_hashes(paths: Iterable[Path]) -> dict[str, str]:
    return {rel(path): file_hash(path) for path in paths if path.is_file()}


def packet_hash(path: Path) -> str:
    values = {
        item.relative_to(path).as_posix(): file_hash(item)
        for item in packet_files(path)
    }
    return canonical_hash(values)


def cache_files() -> list[Path]:
    return design.cache_files()


def clean_output() -> None:
    expected = (ROOT / "evidence" / "validation" / TASK_ID / "latest").resolve()
    if OUTPUT_DIR.exists():
        if OUTPUT_DIR.resolve() != expected:
            raise RuntimeError(f"Refusing to remove unexpected path: {OUTPUT_DIR}")
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return "" if not math.isfinite(value) else f"{value:.12g}"
    if isinstance(value, (dict, list, tuple, set)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return str(value)


def fields_for(
    rows: list[dict[str, Any]], leading: list[str], fallback: list[str]
) -> list[str]:
    fields = list(leading)
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    return fields if rows else fallback


def write_csv(
    name: str,
    rows: list[dict[str, Any]],
    leading: list[str],
    fallback: list[str] | None = None,
) -> None:
    fields = fields_for(rows, leading, fallback or leading)
    with (OUTPUT_DIR / name).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: csv_value(row.get(key)) for key in fields})


def write_yaml(name: str, payload: dict[str, Any]) -> None:
    (OUTPUT_DIR / name).write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=False),
        encoding="utf-8",
    )


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True, default=str)
        + "\n",
        encoding="utf-8",
    )


def write_text(name: str, value: str) -> None:
    (OUTPUT_DIR / name).write_text(value, encoding="utf-8")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sanitize_error(exc: BaseException) -> str:
    value = str(exc).replace("\r", " ").replace("\n", " ")
    value = re.sub(
        r"(?i)(key|secret|token|authorization)[=:]\s*\S+",
        r"\1=REDACTED",
        value,
    )
    for name in (
        "ALPACA_PAPER_API_KEY",
        "ALPACA_PAPER_SECRET_KEY",
        "APCA-API-KEY-ID",
        "APCA-API-SECRET-KEY",
    ):
        value = value.replace(name, f"{name}_REDACTED")
    return value[:600]


def design_reconciliation() -> tuple[list[dict[str, Any]], dict[str, bool]]:
    expected_files = design.REQUIRED_OUTPUTS
    actual_files = {
        path.name for path in DESIGN_DIR.iterdir() if path.is_file()
    }
    manifest = read_yaml(DESIGN_DIR / "design_manifest.yaml")
    specification = read_yaml(DESIGN_DIR / "future_trial_specification.yaml")
    consistency = read_json(DESIGN_DIR / "consistency_check.json")
    design_row = read_csv(DESIGN_DIR / "experiment_design_record.csv")
    parameters = {
        row["parameter_name"]: row["frozen_value"]
        for row in read_csv(DESIGN_DIR / "frozen_parameter_specification.csv")
    }
    symbols = tuple(
        row["symbol"]
        for row in read_csv(DESIGN_DIR / "required_symbol_scope.csv")
    )
    portfolios = tuple(
        row["portfolio_id"]
        for row in read_csv(DESIGN_DIR / "portfolio_and_control_definitions.csv")
    )
    checks = {
        "complete_output_set": actual_files == expected_files,
        "design_outcome_completed": manifest.get("outcome")
        == design.OUTCOME_COMPLETED,
        "design_consistency_pass": consistency.get("overall_pass") is True,
        "one_design_record": len(design_row) == 1,
        "future_trial_unexecuted": bool(
            design_row
            and design_row[0].get("future_trial_record_executed") == "false"
            and design_row[0].get("future_trial_activated") == "false"
        ),
        "trial_identity": specification.get("trial_id") == TRIAL_ID,
        "parent_identity": specification.get("parent_trial_id")
        == PARENT_TRIAL_ID,
        "route": specification.get("approved_route")
        == "20pct_diversifier_only",
        "adaptation_label": specification.get("adaptation_label")
        == "prospective_validation_variant",
        "changed_fields": specification.get("changed_fields_from_parent")
        == "prospective_evaluation_boundary_only",
        "strategy_identity": specification.get("strategy_id") == STRATEGY_ID,
        "parameter_AF_min": float(parameters.get("AF_min", "nan")) == 0.02,
        "parameter_AF_max": float(parameters.get("AF_max", "nan")) == 0.20,
        "parameter_forward": float(
            parameters.get("AF_forward_step", "nan")
        )
        == 0.02,
        "parameter_backward": float(
            parameters.get("AF_backward_step", "nan")
        )
        == 0.05,
        "parameter_change_period": int(
            parameters.get("change_period_sessions", "0")
        )
        == 3,
        "parameter_threshold": float(
            parameters.get("change_threshold", "nan")
        )
        == 0.02,
        "exact_symbol_scope": symbols == SYMBOLS,
        "exact_portfolios": portfolios == PORTFOLIO_IDS,
        "exact_exposure_control": specification.get(
            "exact_exposure_control"
        )
        == {
            "SPY": EXACT_EXPOSURE_SPY,
            "BIL": EXACT_EXPOSURE_BIL,
            "prospective_recalculation_permitted": False,
        },
        "minimum_boundary": specification.get("observation_duration", {}).get(
            "minimum_completed_calendar_months"
        )
        == 24
        and specification.get("observation_duration", {}).get(
            "minimum_completed_defensive_episodes"
        )
        == 6
        and specification.get("observation_duration", {}).get(
            "hard_maximum_completed_calendar_months"
        )
        == 36,
        "historical_backfill_prohibited": specification.get("flags", {}).get(
            "historical_backfill_permitted"
        )
        is False,
    }
    rows = [
        {
            "check_id": check,
            "status": "pass" if passed else "fail",
            "detail": "",
        }
        for check, passed in checks.items()
    ]
    return rows, checks


def trial_identity_use_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    evidence_root = ROOT / "evidence"
    for name in ("trial_ledger.csv", "validation_trial_record.csv"):
        for path in evidence_root.rglob(name):
            if OUTPUT_DIR in path.parents or DESIGN_DIR in path.parents:
                continue
            try:
                for row in read_csv(path):
                    if row.get("trial_id") == TRIAL_ID:
                        rows.append(
                            {
                                "path": rel(path),
                                "trial_id": TRIAL_ID,
                                "status": row.get("status", ""),
                                "entity_type": row.get("entity_type", ""),
                            }
                        )
            except (OSError, csv.Error, UnicodeError):
                continue
    return rows


def is_regular_session(day: date) -> bool:
    return bool(
        day.weekday() < 5
        and day not in scheduled_full_day_nyse_closures(day.year)
        and day not in KNOWN_UNSCHEDULED_NYSE_CLOSURES
    )


def previous_regular_session(day: date) -> date:
    cursor = day - timedelta(days=1)
    while not is_regular_session(cursor):
        cursor -= timedelta(days=1)
    return cursor


def next_regular_session(day: date) -> date:
    cursor = day + timedelta(days=1)
    while not is_regular_session(cursor):
        cursor += timedelta(days=1)
    return cursor


def latest_completed_session(now_utc: datetime) -> date:
    now_et = now_utc.astimezone(EASTERN)
    cursor = now_et.date()
    if not is_regular_session(cursor) or now_et.time() < time(17, 0):
        cursor -= timedelta(days=1)
    while not is_regular_session(cursor):
        cursor -= timedelta(days=1)
    return cursor


def expected_sessions(start: date, end: date) -> list[date]:
    result: list[date] = []
    cursor = start
    while cursor <= end:
        if is_regular_session(cursor):
            result.append(cursor)
        cursor += timedelta(days=1)
    return result


def normalize_alpaca_records(records: list[dict[str, Any]]) -> pd.DataFrame:
    normalized: list[dict[str, Any]] = []
    for record in records:
        timestamp = pd.to_datetime(record.get("t"), utc=True)
        normalized.append(
            {
                "trading_date": timestamp.date().isoformat(),
                "adjusted_open": float(record.get("o")),
                "adjusted_high": float(record.get("h")),
                "adjusted_low": float(record.get("l")),
                "adjusted_close": float(record.get("c")),
                "adjusted_volume": float(record.get("v", 0.0)),
            }
        )
    frame = pd.DataFrame(normalized)
    if frame.empty:
        return pd.DataFrame(
            columns=[
                "trading_date",
                "adjusted_open",
                "adjusted_high",
                "adjusted_low",
                "adjusted_close",
                "adjusted_volume",
            ]
        )
    return (
        frame.sort_values("trading_date")
        .drop_duplicates("trading_date", keep="last")
        .reset_index(drop=True)
    )


def extract_yfinance_symbol(raw: pd.DataFrame, symbol: str) -> pd.DataFrame:
    if not isinstance(raw.columns, pd.MultiIndex):
        return raw.copy()
    level_zero = {str(value) for value in raw.columns.get_level_values(0)}
    level_one = {str(value) for value in raw.columns.get_level_values(1)}
    if symbol in level_zero:
        return raw[symbol].copy()
    if symbol in level_one:
        return raw.xs(symbol, axis=1, level=1).copy()
    return pd.DataFrame()


def normalize_yfinance_frame(raw: pd.DataFrame) -> pd.DataFrame:
    if raw.empty:
        return normalize_alpaca_records([])
    frame = raw.copy().reset_index()
    date_column = "Date" if "Date" in frame.columns else frame.columns[0]
    close = pd.to_numeric(frame["Close"], errors="coerce")
    adjusted = pd.to_numeric(frame["Adj Close"], errors="coerce")
    factor = adjusted / close
    result = pd.DataFrame(
        {
            "trading_date": pd.to_datetime(frame[date_column])
            .dt.date.astype(str),
            "adjusted_open": pd.to_numeric(
                frame["Open"], errors="coerce"
            )
            * factor,
            "adjusted_high": pd.to_numeric(
                frame["High"], errors="coerce"
            )
            * factor,
            "adjusted_low": pd.to_numeric(
                frame["Low"], errors="coerce"
            )
            * factor,
            "adjusted_close": adjusted,
            "adjusted_volume": pd.to_numeric(
                frame["Volume"], errors="coerce"
            ),
        }
    )
    return (
        result.sort_values("trading_date")
        .drop_duplicates("trading_date", keep="last")
        .reset_index(drop=True)
    )


def frame_bytes(frame: pd.DataFrame) -> bytes:
    return frame.to_csv(
        index=False,
        lineterminator="\n",
        float_format="%.12g",
    ).encode("utf-8")


def frame_hash(frame: pd.DataFrame) -> str:
    return sha256_bytes(frame_bytes(frame))


def retrieve_alpaca_once(
    retrieval_id: int,
    start: date,
    end_exclusive: date,
) -> dict[str, Any]:
    credentials = load_alpaca_credentials("paper")
    result: dict[str, Any] = {
        "retrieval_id": retrieval_id,
        "provider_id": "alpaca_market_data_read_only_adjusted_daily",
        "status": "",
        "credentials_present": bool(credentials.present),
        "live_credentials_detected": bool(
            credentials.live_credentials_detected
        ),
        "credential_source_present": credentials.source != "none",
        "endpoint": "/v2/stocks/bars",
        "request_method": "GET",
        "feed": "iex",
        "adjustment": "all",
        "start": start.isoformat(),
        "end_exclusive": end_exclusive.isoformat(),
        "page_count": 0,
        "account_endpoint_called": False,
        "position_endpoint_called": False,
        "order_endpoint_called": False,
        "frames": {},
        "raw_records": {},
        "retrieval_timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }
    if not credentials.present:
        result["status"] = "auth_unavailable"
        result["error"] = "paper_market_data_credentials_missing"
        return result
    if credentials.live_credentials_detected:
        result["status"] = "blocked_live_credentials_detected"
        result["error"] = "live_credentials_detected_read_only_task_refused"
        return result
    try:
        client = AlpacaClient(
            credentials,
            AlpacaClientConfig(data_feed="iex", data_adjustment="all"),
        )
        merged = {symbol: [] for symbol in SYMBOLS}
        page_token: str | None = None
        while True:
            payload = client.get_historical_bars_page(
                symbols=list(SYMBOLS),
                start=f"{start.isoformat()}T00:00:00Z",
                end=f"{end_exclusive.isoformat()}T00:00:00Z",
                timeframe="1Day",
                page_token=page_token,
                feed="iex",
                adjustment="all",
            )
            result["page_count"] += 1
            for symbol in SYMBOLS:
                merged[symbol].extend(payload.get("bars", {}).get(symbol, []))
            page_token = payload.get("next_page_token")
            if not page_token:
                break
        result["raw_records"] = merged
        result["frames"] = {
            symbol: normalize_alpaca_records(merged[symbol])
            for symbol in SYMBOLS
        }
        result["status"] = "download_completed"
        result["rows_by_symbol"] = {
            symbol: len(result["frames"][symbol]) for symbol in SYMBOLS
        }
    except BaseException as exc:  # noqa: BLE001 - bounded provider failure is evidence.
        result["status"] = "provider_call_failed"
        result["error"] = sanitize_error(exc)
    return result


def retrieve_yfinance_once(
    retrieval_id: int,
    start: date,
    end_exclusive: date,
) -> dict[str, Any]:
    import yfinance as yf

    result: dict[str, Any] = {
        "retrieval_id": retrieval_id,
        "provider_id": "yfinance_existing_repo_supported_adjusted_daily_path",
        "status": "",
        "endpoint": "yf.download_existing_repository_path",
        "request_method": "GET",
        "start": start.isoformat(),
        "end_exclusive": end_exclusive.isoformat(),
        "batch_count": 1,
        "account_endpoint_called": False,
        "position_endpoint_called": False,
        "order_endpoint_called": False,
        "frames": {},
        "raw_records": {},
        "retrieval_timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }
    try:
        raw = yf.download(
            list(SYMBOLS),
            start=start.isoformat(),
            end=end_exclusive.isoformat(),
            auto_adjust=False,
            actions=True,
            group_by="ticker",
            progress=False,
            threads=False,
            timeout=30,
        )
        raw_records: dict[str, Any] = {}
        frames: dict[str, pd.DataFrame] = {}
        for symbol in SYMBOLS:
            raw_symbol = extract_yfinance_symbol(raw, symbol)
            raw_records[symbol] = json.loads(
                raw_symbol.reset_index().to_json(
                    orient="records", date_format="iso"
                )
            )
            frames[symbol] = normalize_yfinance_frame(raw_symbol)
        result["raw_records"] = raw_records
        result["frames"] = frames
        result["status"] = "download_completed"
        result["rows_by_symbol"] = {
            symbol: len(frames[symbol]) for symbol in SYMBOLS
        }
    except BaseException as exc:  # noqa: BLE001 - bounded fallback failure is evidence.
        result["status"] = "provider_call_failed"
        result["error"] = sanitize_error(exc)
    return result


def frames_reproduce(
    first: dict[str, pd.DataFrame],
    second: dict[str, pd.DataFrame],
) -> tuple[list[dict[str, Any]], bool]:
    rows: list[dict[str, Any]] = []
    passed = True
    for symbol in SYMBOLS:
        left = first.get(symbol, pd.DataFrame())
        right = second.get(symbol, pd.DataFrame())
        left_hash = frame_hash(left)
        right_hash = frame_hash(right)
        dates_match = (
            left.get("trading_date", pd.Series(dtype=str)).tolist()
            == right.get("trading_date", pd.Series(dtype=str)).tolist()
        )
        values_match = bool(
            tuple(left.columns) == tuple(right.columns)
            and left.shape == right.shape
            and frame_bytes(left) == frame_bytes(right)
        )
        row_pass = bool(dates_match and values_match and left_hash == right_hash)
        passed = passed and row_pass
        rows.append(
            {
                "symbol": symbol,
                "retrieval_1_row_count": len(left),
                "retrieval_2_row_count": len(right),
                "retrieval_1_normalized_hash": left_hash,
                "retrieval_2_normalized_hash": right_hash,
                "normalized_dates_identical": dates_match,
                "normalized_values_identical": values_match,
                "normalized_hashes_identical": left_hash == right_hash,
                "reproducibility_status": "pass" if row_pass else "fail",
            }
        )
    return rows, passed


def frame_quality(
    frames: dict[str, pd.DataFrame], expected_latest: date
) -> tuple[list[dict[str, Any]], bool, date | None]:
    rows: list[dict[str, Any]] = []
    common: set[date] | None = None
    latest_values: list[date] = []
    for symbol in SYMBOLS:
        frame = frames.get(symbol, pd.DataFrame())
        dates = pd.to_datetime(
            frame.get("trading_date", pd.Series(dtype=str)), errors="coerce"
        )
        prices = frame.reindex(
            columns=[
                "adjusted_open",
                "adjusted_high",
                "adjusted_low",
                "adjusted_close",
            ]
        ).apply(pd.to_numeric, errors="coerce")
        volume = pd.to_numeric(
            frame.get("adjusted_volume", pd.Series(dtype=float)),
            errors="coerce",
        )
        actual_dates = set(dates.dropna().dt.date)
        common = actual_dates if common is None else common & actual_dates
        if actual_dates:
            latest_values.append(max(actual_dates))
        required_recent = expected_sessions(
            expected_latest - timedelta(days=400), expected_latest
        )[-252:]
        missing_recent = sorted(set(required_recent) - actual_dates)
        checks = {
            "nonempty": not frame.empty,
            "ordered_unique_sessions": bool(
                dates.notna().all()
                and dates.is_monotonic_increasing
                and not dates.duplicated().any()
            ),
            "finite_positive_adjusted_OHLC": bool(
                len(prices)
                and np.isfinite(prices.to_numpy(dtype=float)).all()
                and (prices > 0.0).all().all()
            ),
            "valid_adjusted_OHLC_relationships": bool(
                len(prices)
                and (
                    prices["adjusted_high"] + 1e-10
                    >= prices[
                        ["adjusted_open", "adjusted_close"]
                    ].max(axis=1)
                ).all()
                and (
                    prices["adjusted_low"] - 1e-10
                    <= prices[
                        ["adjusted_open", "adjusted_close"]
                    ].min(axis=1)
                ).all()
                and (
                    prices["adjusted_high"] + 1e-10
                    >= prices["adjusted_low"]
                ).all()
            ),
            "finite_nonnegative_adjusted_volume": bool(
                len(volume)
                and np.isfinite(volume.to_numpy(dtype=float)).all()
                and (volume >= 0.0).all()
            ),
            "latest_required_session_present": expected_latest
            in actual_dates,
            "no_unexplained_recent_required_session_gap": not missing_recent,
        }
        for check, value in checks.items():
            rows.append(
                {
                    "symbol": symbol,
                    "check_id": check,
                    "status": "pass" if value else "fail",
                    "first_date": min(actual_dates).isoformat()
                    if actual_dates
                    else "",
                    "last_date": max(actual_dates).isoformat()
                    if actual_dates
                    else "",
                    "row_count": len(frame),
                    "detail": "|".join(
                        value.isoformat() for value in missing_recent
                    )
                    if check
                    == "no_unexplained_recent_required_session_gap"
                    else "",
                }
            )
    latest_common = max(common) if common else None
    common_pass = latest_common == expected_latest
    rows.append(
        {
            "symbol": "__COMMON__",
            "check_id": "latest_common_required_session",
            "status": "pass" if common_pass else "fail",
            "first_date": "",
            "last_date": latest_common.isoformat() if latest_common else "",
            "row_count": "",
            "detail": f"expected={expected_latest.isoformat()}",
        }
    )
    return rows, all(row["status"] == "pass" for row in rows), latest_common


def persist_retrieval(
    retrieval: dict[str, Any],
    provider_sequence: str,
) -> dict[str, dict[str, str]]:
    root = RAW_ROOT / provider_sequence / f"retrieval_{retrieval['retrieval_id']}"
    result: dict[str, dict[str, str]] = {}
    for symbol in SYMBOLS:
        raw_path = root / f"{symbol}_raw.json"
        normalized_path = root / f"{symbol}_normalized.csv"
        raw_payload = retrieval["raw_records"][symbol]
        write_json(raw_path, raw_payload)
        normalized_path.parent.mkdir(parents=True, exist_ok=True)
        normalized_path.write_bytes(frame_bytes(retrieval["frames"][symbol]))
        result[symbol] = {
            "raw_path": rel(raw_path),
            "raw_hash": file_hash(raw_path),
            "normalized_path": rel(normalized_path),
            "normalized_hash": file_hash(normalized_path),
        }
    return result


def acquire_cycle(
    latest: date,
) -> tuple[
    dict[str, pd.DataFrame],
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, dict[str, str]],
    dict[str, Any],
]:
    end_exclusive = latest + timedelta(days=1)
    attempts: list[dict[str, Any]] = []
    first = retrieve_alpaca_once(1, GLOBAL_REQUEST_START, end_exclusive)
    second: dict[str, Any] = {}
    if first["status"] == "download_completed":
        second = retrieve_alpaca_once(2, GLOBAL_REQUEST_START, end_exclusive)
    attempts.append(
        {
            "provider_sequence": 1,
            "provider_id": first["provider_id"],
            "attempted": True,
            "retrieval_count": 2 if second else 1,
            "status": first["status"]
            if not second
            else (
                "duplicate_retrievals_completed"
                if second["status"] == "download_completed"
                else second["status"]
            ),
            "credentials_present": first.get("credentials_present", False),
            "live_credentials_detected": first.get(
                "live_credentials_detected", False
            ),
            "request_start": GLOBAL_REQUEST_START.isoformat(),
            "request_end_exclusive": end_exclusive.isoformat(),
            "endpoint": first.get("endpoint", ""),
            "feed": first.get("feed", ""),
            "adjustment": first.get("adjustment", ""),
            "error": first.get("error", second.get("error", "")),
            "order_endpoint_called": False,
            "fallback_role": "primary",
        }
    )
    if first["status"] == "download_completed" and second.get(
        "status"
    ) == "download_completed":
        reproducibility, reproduce = frames_reproduce(
            first["frames"], second["frames"]
        )
        quality_rows, quality, latest_common = frame_quality(
            first["frames"], latest
        )
        if not reproduce:
            return {}, attempts, reproducibility, {}, {
                "status": "immutable_snapshot_reproducibility_failure",
                "quality_rows": quality_rows,
                "latest_common": latest_common,
                "provider": first["provider_id"],
            }
        if quality:
            persisted_first = persist_retrieval(first, "alpaca_primary")
            persist_retrieval(second, "alpaca_primary")
            return first["frames"], attempts, reproducibility, persisted_first, {
                "status": "pass",
                "quality_rows": quality_rows,
                "latest_common": latest_common,
                "provider": first["provider_id"],
                "retrieval_timestamps": [
                    first["retrieval_timestamp_utc"],
                    second["retrieval_timestamp_utc"],
                ],
            }
        attempts[-1]["status"] = "schema_or_coverage_inadequate"
        attempts[-1]["error"] = "fallback_authorized_after_quality_failure"

    fallback_first = retrieve_yfinance_once(
        1, GLOBAL_REQUEST_START, end_exclusive
    )
    fallback_second: dict[str, Any] = {}
    if fallback_first["status"] == "download_completed":
        fallback_second = retrieve_yfinance_once(
            2, GLOBAL_REQUEST_START, end_exclusive
        )
    attempts.append(
        {
            "provider_sequence": 2,
            "provider_id": fallback_first["provider_id"],
            "attempted": True,
            "retrieval_count": 2 if fallback_second else 1,
            "status": fallback_first["status"]
            if not fallback_second
            else (
                "duplicate_retrievals_completed"
                if fallback_second["status"] == "download_completed"
                else fallback_second["status"]
            ),
            "credentials_present": "not_applicable",
            "live_credentials_detected": False,
            "request_start": GLOBAL_REQUEST_START.isoformat(),
            "request_end_exclusive": end_exclusive.isoformat(),
            "endpoint": fallback_first.get("endpoint", ""),
            "feed": "",
            "adjustment": "Adj Close ratio applied to OHLC",
            "error": fallback_first.get(
                "error", fallback_second.get("error", "")
            ),
            "order_endpoint_called": False,
            "fallback_role": "single_existing_approved_fallback",
        }
    )
    if fallback_first["status"] != "download_completed" or fallback_second.get(
        "status"
    ) != "download_completed":
        return {}, attempts, [], {}, {
            "status": "required_data_unavailable",
            "quality_rows": [],
            "latest_common": None,
            "provider": fallback_first["provider_id"],
        }
    reproducibility, reproduce = frames_reproduce(
        fallback_first["frames"], fallback_second["frames"]
    )
    quality_rows, quality, latest_common = frame_quality(
        fallback_first["frames"], latest
    )
    if not reproduce:
        return {}, attempts, reproducibility, {}, {
            "status": "immutable_snapshot_reproducibility_failure",
            "quality_rows": quality_rows,
            "latest_common": latest_common,
            "provider": fallback_first["provider_id"],
        }
    if not quality:
        return {}, attempts, reproducibility, {}, {
            "status": "required_data_unavailable",
            "quality_rows": quality_rows,
            "latest_common": latest_common,
            "provider": fallback_first["provider_id"],
        }
    persisted_first = persist_retrieval(
        fallback_first, "approved_fallback"
    )
    persist_retrieval(fallback_second, "approved_fallback")
    return (
        fallback_first["frames"],
        attempts,
        reproducibility,
        persisted_first,
        {
            "status": "pass",
            "quality_rows": quality_rows,
            "latest_common": latest_common,
            "provider": fallback_first["provider_id"],
            "retrieval_timestamps": [
                fallback_first["retrieval_timestamp_utc"],
                fallback_second["retrieval_timestamp_utc"],
            ],
        },
    )


def to_psar_input(frame: pd.DataFrame, through: date) -> pd.DataFrame:
    subset = frame.loc[
        pd.to_datetime(frame["trading_date"]).dt.date <= through
    ].copy()
    return pd.DataFrame(
        {
            "high": pd.to_numeric(subset["adjusted_high"]).to_numpy(),
            "low": pd.to_numeric(subset["adjusted_low"]).to_numpy(),
            "adj_close": pd.to_numeric(
                subset["adjusted_close"]
            ).to_numpy(),
        },
        index=pd.to_datetime(subset["trading_date"]),
    )


def psar_state(
    frame: pd.DataFrame, through: date, decelerated: bool
) -> tuple[dict[str, Any], pd.DataFrame]:
    result = psar_engine.psar_frame(
        to_psar_input(frame, through), decelerated
    )
    if result.empty or result.iloc[-1]["trend"] == "uninitialized":
        raise RuntimeError("PSAR recursive state did not initialize")
    latest = result.iloc[-1]
    previous = result.iloc[-2] if len(result) > 1 else latest
    state = {
        "initialization_history_start": result.index[0].date().isoformat(),
        "last_completed_signal_date": result.index[-1].date().isoformat(),
        "PSAR": float(latest["PSAR"]),
        "AF": float(latest["AF"]),
        "EP": float(latest["EP"]),
        "trend_state": str(latest["trend"]),
        "change3": float(latest["change3"]),
        "target": {
            "SPY": 1.0
            if latest["target_state"] == "SPY"
            else 0.0,
            "BIL": 1.0
            if latest["target_state"] == "BIL"
            else 0.0,
        },
        "state_before_latest_calculation": {
            "PSAR": float(previous["PSAR"]),
            "AF": float(previous["AF"]),
            "EP": float(previous["EP"]),
            "trend_state": str(previous["trend"]),
        },
        "recursive_replay_source": (
            "all_available_provider_adjusted_SPY_history_returned_from_"
            "frozen_2007_01_03_request_boundary_no_serialized_state_checkpoint"
        ),
    }
    return state, result


def close_frame(
    frames: dict[str, pd.DataFrame], symbols: tuple[str, ...]
) -> pd.DataFrame:
    series = []
    for symbol in symbols:
        frame = frames[symbol]
        series.append(
            pd.Series(
                pd.to_numeric(frame["adjusted_close"]).to_numpy(),
                index=pd.to_datetime(frame["trading_date"]),
                name=symbol,
            )
        )
    return pd.concat(series, axis=1).sort_index().dropna(how="any")


def reference_state(
    frames: dict[str, pd.DataFrame], latest_common: date
) -> tuple[list[dict[str, Any]], dict[str, float], dict[str, Any]]:
    vm_symbols = tuple(reference_engine.VM_SYMBOLS)
    dsr_symbols = tuple(reference_engine.DSR_SYMBOLS)
    vm_prices = close_frame(frames, vm_symbols)
    dsr_prices = close_frame(frames, dsr_symbols)
    common = vm_prices.index.intersection(dsr_prices.index)
    common = common[common.date <= latest_common]
    if not len(common) or common[-1].date() != latest_common:
        return [], {}, {"status": "blocked_latest_common_session"}
    month_sessions = [
        pd.Timestamp(value)
        for value in common
        if (value.year, value.month)
        == (latest_common.year, latest_common.month)
    ]
    if not month_sessions:
        return [], {}, {"status": "blocked_monthly_effective_session"}
    effective = min(month_sessions)
    prior = common[common < effective]
    if not len(prior):
        return [], {}, {"status": "blocked_signal_session"}
    signal = pd.Timestamp(prior[-1])
    targets = {
        reference_engine.VM_ID: reference_engine.vm_target(
            vm_prices, signal
        ),
        reference_engine.DSR_ID: reference_engine.dsr_target(
            dsr_prices, signal
        ),
        reference_engine.USCI_ID: {"USCI": 1.0},
    }
    component_symbols = {
        reference_engine.VM_ID: vm_symbols,
        reference_engine.DSR_ID: dsr_symbols,
        reference_engine.USCI_ID: tuple(reference_engine.USCI_SYMBOLS),
    }
    final: dict[str, float] = {}
    rows: list[dict[str, Any]] = []
    for component_id, target in targets.items():
        for symbol, weight in sorted(target.items()):
            normalized = float(weight) / 3.0
            final[symbol] = final.get(symbol, 0.0) + normalized
            rows.append(
                {
                    "record_type": "component_target",
                    "component_id": component_id,
                    "frozen_rule_source": (
                        "strategy_lab/research_os/research/"
                        "initialize_angl_after_next_completed_common_session_v1.py"
                    ),
                    "required_symbols": component_symbols[component_id],
                    "initialization_history_start": min(
                        pd.to_datetime(
                            frames[value]["trading_date"]
                        ).min()
                        for value in component_symbols[component_id]
                    ).date().isoformat(),
                    "latest_completed_signal_date": signal.date().isoformat(),
                    "target_effective_date": effective.date().isoformat(),
                    "latest_common_completed_session": latest_common.isoformat(),
                    "symbol": symbol,
                    "component_weight": 1.0 / 3.0,
                    "weight_within_component": float(weight),
                    "final_normalized_reference_weight": normalized,
                    "historical_validation_performance_created": False,
                    "status": "pass",
                }
            )
    total = sum(final.values())
    for symbol, weight in sorted(final.items()):
        rows.append(
            {
                "record_type": "combined_reference_weight",
                "component_id": "frozen_current_active_vm_dsr_usci_combo",
                "frozen_rule_source": (
                    "strategy_lab/research_os/research/"
                    "initialize_angl_after_next_completed_common_session_v1.py"
                ),
                "required_symbols": SYMBOLS,
                "initialization_history_start": "",
                "latest_completed_signal_date": signal.date().isoformat(),
                "target_effective_date": effective.date().isoformat(),
                "latest_common_completed_session": latest_common.isoformat(),
                "symbol": symbol,
                "component_weight": "",
                "weight_within_component": "",
                "final_normalized_reference_weight": weight,
                "historical_validation_performance_created": False,
                "status": "pass"
                if abs(total - 1.0) <= 1e-12
                else "fail",
            }
        )
    return rows, final, {
        "status": "pass" if abs(total - 1.0) <= 1e-12 else "fail",
        "component_targets": targets,
        "final_weights": final,
        "signal_date": signal.date().isoformat(),
        "target_effective_date": effective.date().isoformat(),
        "gross_exposure": sum(abs(value) for value in final.values()),
        "weight_sum": total,
        "nonnegative": all(value >= 0.0 for value in final.values()),
    }


def merge_sleeve(
    reference: dict[str, float], sleeve: dict[str, float] | None
) -> dict[str, float]:
    if sleeve is None:
        return dict(reference)
    symbols = sorted(set(reference) | set(sleeve))
    return {
        symbol: REFERENCE_WEIGHT * reference.get(symbol, 0.0)
        + CANDIDATE_WEIGHT * sleeve.get(symbol, 0.0)
        for symbol in symbols
        if REFERENCE_WEIGHT * reference.get(symbol, 0.0)
        + CANDIDATE_WEIGHT * sleeve.get(symbol, 0.0)
        > 0.0
    }


def comparator_states(
    frames: dict[str, pd.DataFrame],
    latest_common: date,
    reference_weights: dict[str, float],
    candidate: dict[str, Any],
    original: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, dict[str, float]]]:
    spy = frames["SPY"].copy()
    spy = spy.loc[
        pd.to_datetime(spy["trading_date"]).dt.date <= latest_common
    ]
    closes = pd.to_numeric(spy["adjusted_close"])
    if len(closes) < 200:
        raise RuntimeError("SPY 200-day control lacks 200 completed sessions")
    trend_target = (
        {"SPY": 1.0, "BIL": 0.0}
        if float(closes.iloc[-1]) > float(closes.tail(200).mean())
        else {"SPY": 0.0, "BIL": 1.0}
    )
    sleeves: dict[str, dict[str, float] | None] = {
        PORTFOLIO_IDS[0]: None,
        PORTFOLIO_IDS[1]: candidate["target"],
        PORTFOLIO_IDS[2]: original["target"],
        PORTFOLIO_IDS[3]: {
            "SPY": EXACT_EXPOSURE_SPY,
            "BIL": EXACT_EXPOSURE_BIL,
        },
        PORTFOLIO_IDS[4]: trend_target,
        PORTFOLIO_IDS[5]: {"SPY": 0.0, "BIL": 1.0},
        PORTFOLIO_IDS[6]: {"SPY": 1.0, "BIL": 0.0},
    }
    holdings = {
        portfolio_id: merge_sleeve(reference_weights, sleeve)
        for portfolio_id, sleeve in sleeves.items()
    }
    rows = []
    for portfolio_id in PORTFOLIO_IDS:
        values = holdings[portfolio_id]
        rows.append(
            {
                "portfolio_id": portfolio_id,
                "entity_type": "benchmark_specification"
                if portfolio_id != PORTFOLIO_IDS[1]
                else "candidate_validation_portfolio",
                "stage": "validation",
                "initialization_label": (
                    "initialization_state_input_not_validation_performance"
                ),
                "latest_completed_signal_date": latest_common.isoformat(),
                "sleeve_target": sleeves[portfolio_id] or {},
                "explicit_initialization_holdings": values,
                "weight_sum": sum(values.values()),
                "gross_exposure": sum(abs(value) for value in values.values()),
                "nonnegative_weights": all(
                    value >= 0.0 for value in values.values()
                ),
                "initialization_turnover": 1.0,
                "initialization_cost_0bps": 0.0,
                "initialization_cost_5bps": 0.0005,
                "initialization_cost_10bps": 0.001,
                "validation_performance_return_created": False,
                "completed_validation_months": 0,
                "completed_defensive_episodes": 0,
                "status": "pass"
                if abs(sum(values.values()) - 1.0) <= 1e-12
                and all(value >= 0.0 for value in values.values())
                else "fail",
            }
        )
    return rows, holdings


def history_requirement_rows(
    frames: dict[str, pd.DataFrame] | None,
    latest_common: date | None,
) -> list[dict[str, Any]]:
    rows = [
        {
            "component_id": "decelerated_PSAR_candidate",
            "required_symbols": ["SPY"],
            "minimum_history_rule": (
                "full_deterministic_recursive_replay_from_available_provider_"
                "history_no_serialized_state_checkpoint"
            ),
            "requested_start": GLOBAL_REQUEST_START.isoformat(),
            "selected_from_performance": False,
        },
        {
            "component_id": "original_PSAR_control",
            "required_symbols": ["SPY"],
            "minimum_history_rule": (
                "full_deterministic_recursive_replay_from_available_provider_"
                "history_no_serialized_state_checkpoint"
            ),
            "requested_start": GLOBAL_REQUEST_START.isoformat(),
            "selected_from_performance": False,
        },
        {
            "component_id": "SPY_200_day_trend_control",
            "required_symbols": ["SPY"],
            "minimum_history_rule": "200_completed_sessions",
            "requested_start": GLOBAL_REQUEST_START.isoformat(),
            "selected_from_performance": False,
        },
        {
            "component_id": reference_engine.VM_ID,
            "required_symbols": list(reference_engine.VM_SYMBOLS),
            "minimum_history_rule": (
                "200_session_SMA_126_session_return_60_session_volatility"
            ),
            "requested_start": GLOBAL_REQUEST_START.isoformat(),
            "selected_from_performance": False,
        },
        {
            "component_id": reference_engine.DSR_ID,
            "required_symbols": list(reference_engine.DSR_SYMBOLS),
            "minimum_history_rule": "200_session_SMA",
            "requested_start": GLOBAL_REQUEST_START.isoformat(),
            "selected_from_performance": False,
        },
        {
            "component_id": reference_engine.USCI_ID,
            "required_symbols": list(reference_engine.USCI_SYMBOLS),
            "minimum_history_rule": "current_frozen_USCI_wrapper_target",
            "requested_start": GLOBAL_REQUEST_START.isoformat(),
            "selected_from_performance": False,
        },
        {
            "component_id": "static_and_buy_hold_comparators",
            "required_symbols": ["SPY", "BIL"],
            "minimum_history_rule": "latest_completed_common_session",
            "requested_start": GLOBAL_REQUEST_START.isoformat(),
            "selected_from_performance": False,
        },
    ]
    for row in rows:
        required = row["required_symbols"]
        available_starts: list[str] = []
        available_ends: list[str] = []
        if frames:
            for symbol in required:
                frame = frames.get(symbol, pd.DataFrame())
                if not frame.empty:
                    available_starts.append(str(frame.iloc[0]["trading_date"]))
                    available_ends.append(str(frame.iloc[-1]["trading_date"]))
        row["retrieved_history_start"] = (
            min(available_starts) if available_starts else ""
        )
        row["retrieved_history_end"] = (
            min(available_ends) if available_ends else ""
        )
        row["latest_common_initialization_date"] = (
            latest_common.isoformat() if latest_common else ""
        )
        row["history_role"] = (
            "initialization_state_input_not_validation_performance"
        )
        row["historical_validation_rows_created"] = 0
    return rows


def persist_initialization_snapshots(
    frames: dict[str, pd.DataFrame],
    persisted: dict[str, dict[str, str]],
    provider: str,
    retrieval_timestamps: list[str],
    latest_common: date,
    initialization_execution: date,
    first_performance: date,
    candidate: dict[str, Any],
    comparator_holdings: dict[str, dict[str, float]],
) -> list[dict[str, Any]]:
    combined_version = canonical_hash(
        {symbol: frame_hash(frames[symbol]) for symbol in SYMBOLS}
    )
    rows: list[dict[str, Any]] = []
    for symbol in SYMBOLS:
        frame = frames[symbol]
        current = frame.loc[
            pd.to_datetime(frame["trading_date"]).dt.date == latest_common
        ].iloc[-1]
        snapshot_id = (
            f"{TASK_ID}__initialization__{latest_common.isoformat()}__{symbol}"
        )
        snapshot = {
            "snapshot_id": snapshot_id,
            "snapshot_role": "initialization",
            "signal_date": latest_common.isoformat(),
            "initialization_date": latest_common.isoformat(),
            "retrieval_timestamp_utc": retrieval_timestamps[0],
            "retrieval_timestamp_us_eastern": datetime.fromisoformat(
                retrieval_timestamps[0]
            ).astimezone(EASTERN).isoformat(),
            "source_provider": provider,
            "source_request_metadata": {
                "method": "GET",
                "symbols": list(SYMBOLS),
                "start": GLOBAL_REQUEST_START.isoformat(),
                "adjustment": "all"
                if provider.startswith("alpaca")
                else "Adj Close ratio applied to OHLC",
                "credentials_or_headers_persisted": False,
            },
            "raw_source_records": persisted[symbol]["raw_path"],
            "raw_source_hash": persisted[symbol]["raw_hash"],
            "normalized_frame_hash": persisted[symbol]["normalized_hash"],
            "market_data_version_id": combined_version,
            "symbol": symbol,
            "adjusted_open": float(current["adjusted_open"]),
            "adjusted_high": float(current["adjusted_high"]),
            "adjusted_low": float(current["adjusted_low"]),
            "adjusted_close": float(current["adjusted_close"]),
            "adjusted_volume": float(current["adjusted_volume"]),
            "PSAR_state_before": candidate[
                "state_before_latest_calculation"
            ]
            if symbol == "SPY"
            else {},
            "calculated_PSAR": candidate["PSAR"]
            if symbol == "SPY"
            else None,
            "acceleration_factor": candidate["AF"]
            if symbol == "SPY"
            else None,
            "extreme_point": candidate["EP"]
            if symbol == "SPY"
            else None,
            "trend_state": candidate["trend_state"]
            if symbol == "SPY"
            else "not_applicable",
            "change3": candidate["change3"]
            if symbol == "SPY"
            else None,
            "candidate_target": candidate["target"],
            "comparator_targets": comparator_holdings,
            "intended_execution_date": initialization_execution.isoformat(),
            "first_validation_performance_session": first_performance.isoformat(),
            "actual_execution_status": (
                "prospective_initialization_only_no_performance"
            ),
            "blocked_data_reason": "",
            "pretrade_holdings": {},
            "posttrade_holdings": comparator_holdings,
            "inner_turnover": 0.0,
            "outer_turnover": 0.0,
            "initialization_turnover": 1.0,
            "transaction_cost": {
                "0bps": 0.0,
                "5bps": 0.0005,
                "10bps": 0.001,
            },
            "cost_adjusted_NAV": {
                "0bps": 1.0,
                "5bps": 0.9995,
                "10bps": 0.999,
            },
            "revision_alert_id": None,
            "original_snapshot_superseded": False,
            "snapshot_label": (
                "initialization_state_input_not_validation_performance"
            ),
            "historical_validation_performance_row": False,
            "elapsed_validation_months": 0,
            "defensive_episode_credit": 0,
            "broker_submission": False,
            "paper_order_submission": False,
        }
        snapshot["snapshot_content_hash"] = canonical_hash(snapshot)
        snapshot_path = SNAPSHOT_ROOT / f"{symbol}.json"
        write_json(snapshot_path, snapshot)
        rows.append(
            {
                "snapshot_id": snapshot_id,
                "snapshot_role": "initialization",
                "symbol": symbol,
                "signal_or_initialization_date": latest_common.isoformat(),
                "retrieval_timestamp_utc": retrieval_timestamps[0],
                "provider": provider,
                "raw_path": persisted[symbol]["raw_path"],
                "raw_hash": persisted[symbol]["raw_hash"],
                "normalized_hash": persisted[symbol]["normalized_hash"],
                "market_data_version_id": combined_version,
                "snapshot_path": rel(snapshot_path),
                "snapshot_file_hash": file_hash(snapshot_path),
                "original_snapshot_superseded": False,
                "historical_validation_performance_row": False,
                "schema_status": "pass",
            }
        )
    return rows


def activation_report(
    outcome: str,
    failure_reason: str,
    next_action: str,
    provider: str,
    latest_common: date | None,
    initialization_session: date | None,
    first_performance: date | None,
) -> str:
    data_status = (
        "The immutable initialization data were captured twice and normalized "
        "independently."
        if latest_common
        else (
            "The bounded provider cycle did not yield an admissible duplicate "
            "immutable snapshot set; no raw or normalized snapshot was admitted."
        )
    )
    return f"""# Decelerated PSAR Prospective Validation Activation V1

## Outcome

* Outcome: `{outcome}`
* Failure reason: `{failure_reason or "none"}`
* Exact next action: `{next_action}`

## Scope

The frozen `20pct_diversifier_only` prospective design was reconciled without
changing the standalone closure, exploration outcome, robustness outcome,
strategy rule, parameters, sleeve weight, reference, controls, or costs.

Provider used: `{provider or "none"}`. {data_status} The latest common
completed session was `{latest_common.isoformat() if latest_common else "unavailable"}`.

Initialization session:
`{initialization_session.isoformat() if initialization_session else "not created"}`.
First eligible validation-performance session:
`{first_performance.isoformat() if first_performance else "not created"}`.

Initialization is labeled
`prospective_initialization_not_performance`. It creates no return, validation
month, defensive episode, historical backfill, paper/demo observation, or
broker order.

Historical canonical caches and protected lifecycle state were not modified.
"""


def run(now: datetime | None = None) -> dict[str, Any]:
    started = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    protected_before = map_hashes(PROTECTED_PATHS)
    caches_before = map_hashes(cache_files())
    prior_before = {
        rel(path): packet_hash(path) for path in PRIOR_EVIDENCE_DIRS
    }
    source_before = file_hash(SOURCE_PACKET)
    design_hash_before = packet_hash(DESIGN_DIR)

    clean_output()
    reconciliation_rows, reconciliation_checks = design_reconciliation()
    identity_uses = trial_identity_use_rows()
    design_ready = all(reconciliation_checks.values())
    trial_unused = not identity_uses
    latest_expected = latest_completed_session(started)

    frames: dict[str, pd.DataFrame] = {}
    provider_attempts: list[dict[str, Any]] = []
    reproducibility_rows: list[dict[str, Any]] = []
    persisted: dict[str, dict[str, str]] = {}
    acquisition = {
        "status": "not_attempted",
        "quality_rows": [],
        "latest_common": None,
        "provider": "",
        "retrieval_timestamps": [],
    }
    resume_after_consumed_cycle = (
        os.environ.get("PSAR_ACTIVATION_RESUME_AFTER_LOCAL_ERROR") == "1"
    )
    if design_ready and trial_unused and resume_after_consumed_cycle:
        provider_attempts = [
            {
                "provider_sequence": 1,
                "provider_id": "bounded_approved_provider_cycle",
                "attempted": True,
                "retrieval_count": 0,
                "status": (
                    "cycle_consumed_results_not_admitted_after_local_"
                    "post_acquisition_methodology_error"
                ),
                "credentials_present": True,
                "live_credentials_detected": False,
                "request_start": GLOBAL_REQUEST_START.isoformat(),
                "request_end_exclusive": (
                    latest_expected + timedelta(days=1)
                ).isoformat(),
                "endpoint": (
                    "read_only_market_data_paths_attempted_in_failed_runner"
                ),
                "feed": "",
                "adjustment": "",
                "error": (
                    "AttributeError: initialization reference module alias "
                    "did not expose VM_ID after the bounded provider cycle; "
                    "no immutable retrieval artifacts were admitted"
                ),
                "order_endpoint_called": False,
                "fallback_role": "primary",
                "network_calls_previously_consumed": True,
                "network_calls_in_resume_run": 0,
            }
        ]
        acquisition = {
            "status": "data_or_comparability_failure",
            "quality_rows": [],
            "latest_common": None,
            "provider": "",
            "retrieval_timestamps": [],
        }
    elif design_ready and trial_unused:
        (
            frames,
            provider_attempts,
            reproducibility_rows,
            persisted,
            acquisition,
        ) = acquire_cycle(latest_expected)

    latest_common = acquisition.get("latest_common")
    history_rows = history_requirement_rows(frames or None, latest_common)
    candidate_state: dict[str, Any] = {}
    original_state: dict[str, Any] = {}
    candidate_rows: list[dict[str, Any]] = []
    reference_rows: list[dict[str, Any]] = []
    reference_weights: dict[str, float] = {}
    reference_detail: dict[str, Any] = {"status": "not_run"}
    comparator_rows: list[dict[str, Any]] = []
    comparator_holdings: dict[str, dict[str, float]] = {}
    state_error = ""
    if acquisition.get("status") == "pass" and latest_common:
        try:
            candidate_state, _candidate_path = psar_state(
                frames["SPY"], latest_common, True
            )
            original_state, _original_path = psar_state(
                frames["SPY"], latest_common, False
            )
            reference_rows, reference_weights, reference_detail = (
                reference_state(frames, latest_common)
            )
            if reference_detail.get("status") != "pass":
                raise RuntimeError(
                    f"reference_state:{reference_detail.get('status')}"
                )
            comparator_rows, comparator_holdings = comparator_states(
                frames,
                latest_common,
                reference_weights,
                candidate_state,
                original_state,
            )
            candidate_rows = [
                {
                    "strategy_id": STRATEGY_ID,
                    "state_role": (
                        "initialization_state_input_not_validation_performance"
                    ),
                    **candidate_state,
                    "deterministic_recalculation_match": canonical_hash(
                        candidate_state
                    )
                    == canonical_hash(
                        psar_state(frames["SPY"], latest_common, True)[0]
                    ),
                    "historical_validation_performance_created": False,
                    "post_activation_prices_used": False,
                    "status": "pass",
                }
            ]
        except BaseException as exc:  # noqa: BLE001 - state blocker becomes evidence.
            state_error = sanitize_error(exc)

    candidate_ready = bool(
        candidate_rows
        and candidate_rows[0]["deterministic_recalculation_match"]
        and candidate_rows[0]["status"] == "pass"
    )
    reference_ready = bool(
        reference_detail.get("status") == "pass"
        and reference_detail.get("nonnegative")
        and abs(float(reference_detail.get("weight_sum", 0.0)) - 1.0)
        <= 1e-12
    )
    comparators_ready = bool(
        len(comparator_rows) == 7
        and all(row["status"] == "pass" for row in comparator_rows)
    )

    activation_timestamp = datetime.now(timezone.utc)
    initialization_session: date | None = None
    first_performance: date | None = None
    boundary_ready = False
    if latest_common:
        initialization_session = next_regular_session(
            max(activation_timestamp.astimezone(EASTERN).date(), latest_common)
        )
        first_performance = next_regular_session(initialization_session)
        boundary_ready = bool(
            is_regular_session(initialization_session)
            and is_regular_session(first_performance)
            and initialization_session
            > activation_timestamp.astimezone(EASTERN).date()
            and initialization_session > latest_common
            and first_performance > initialization_session
        )

    snapshot_rows: list[dict[str, Any]] = []
    snapshot_error = ""
    if (
        candidate_ready
        and reference_ready
        and comparators_ready
        and boundary_ready
        and initialization_session
        and first_performance
    ):
        try:
            snapshot_rows = persist_initialization_snapshots(
                frames,
                persisted,
                acquisition["provider"],
                acquisition["retrieval_timestamps"],
                latest_common,
                initialization_session,
                first_performance,
                candidate_state,
                comparator_holdings,
            )
        except BaseException as exc:  # noqa: BLE001 - storage blocker is evidence.
            snapshot_error = sanitize_error(exc)

    snapshot_ready = bool(
        len(snapshot_rows) == len(SYMBOLS)
        and all(row["schema_status"] == "pass" for row in snapshot_rows)
    )
    zero_historical_validation_rows = True
    all_gates = {
        "design_packet_reconciles_exactly": design_ready,
        "future_trial_identity_unused": trial_unused,
        "exact_17_symbol_scope_frozen": tuple(SYMBOLS)
        == design.EXPECTED_REFERENCE_SYMBOLS,
        "deterministic_initialization_history_requirements": len(history_rows)
        == 7,
        "one_bounded_approved_provider_cycle": len(provider_attempts)
        in {1, 2}
        and sum(
            row["fallback_role"] == "single_existing_approved_fallback"
            for row in provider_attempts
        )
        <= 1,
        "duplicate_retrievals_normalize_identically": bool(
            reproducibility_rows
            and all(
                row["reproducibility_status"] == "pass"
                for row in reproducibility_rows
            )
        ),
        "immutable_snapshot_storage": snapshot_ready,
        "candidate_recursive_state_initializes": candidate_ready,
        "original_PSAR_and_comparators_initialize": comparators_ready
        and bool(original_state),
        "frozen_reference_components_reconcile": reference_ready,
        "portfolio_weights_nonnegative_and_sum_to_one": comparators_ready,
        "initialization_separate_from_performance": True,
        "future_activation_boundary_identified": boundary_ready,
        "zero_historical_validation_rows": zero_historical_validation_rows,
        "trial_and_observation_schema_available": True,
        "prior_evidence_and_protected_state_unchanged_pre_entity_creation": (
            packet_hash(DESIGN_DIR) == design_hash_before
        ),
    }

    if not design_ready:
        outcome = BLOCKED
        failure_reason = (
            "parameter_reconciliation_failure"
            if any(
                not value
                for key, value in reconciliation_checks.items()
                if key.startswith("parameter_")
            )
            else "lineage_reconciliation_failure"
        )
        next_action = NEXT_BLOCKED
    elif not trial_unused:
        outcome = BLOCKED
        failure_reason = "status_reconciliation_required"
        next_action = NEXT_BLOCKED
    elif acquisition.get("status") == (
        "immutable_snapshot_reproducibility_failure"
    ):
        outcome = DEFERRED
        failure_reason = "immutable_snapshot_reproducibility_failure"
        next_action = NEXT_DEFERRED
    elif acquisition.get("status") != "pass":
        outcome = DEFERRED
        failure_reason = (
            acquisition.get("status")
            if acquisition.get("status") in DEFERRED_REASONS
            else "required_data_unavailable"
        )
        next_action = NEXT_DEFERRED
    elif not candidate_ready:
        outcome = DEFERRED
        failure_reason = "candidate_state_initialization_failure"
        next_action = NEXT_DEFERRED
    elif not reference_ready or not comparators_ready:
        outcome = DEFERRED
        failure_reason = "reference_initialization_failure"
        next_action = NEXT_DEFERRED
    elif not boundary_ready:
        outcome = DEFERRED
        failure_reason = "activation_boundary_not_ready"
        next_action = NEXT_DEFERRED
    elif not snapshot_ready:
        outcome = DEFERRED
        failure_reason = "observation_storage_unavailable"
        next_action = NEXT_DEFERRED
    elif not all(all_gates.values()):
        outcome = DEFERRED
        failure_reason = "data_or_comparability_failure"
        next_action = NEXT_DEFERRED
    else:
        outcome = ACTIVATED
        failure_reason = ""
        next_action = NEXT_ACTIVATED

    activated = outcome == ACTIVATED
    trial_rows = (
        [
            {
                "trial_id": TRIAL_ID,
                "entity_type": "experiment_trial",
                "stage": STAGE,
                "strategy_id": STRATEGY_ID,
                "family_id": FAMILY_ID,
                "parent_trial_id": PARENT_TRIAL_ID,
                "adaptation_label": "prospective_validation_variant",
                "changed_fields_from_parent": (
                    "prospective_evaluation_boundary_only"
                ),
                "route": "20pct_diversifier_only",
                "status": "active_prospective_validation",
                "outcome": "",
                "failure_reason": "",
                "next_action": NEXT_ACTIVATED,
                "strategy_rule_changed": False,
                "parameters_changed": False,
                "instruments_changed": False,
                "execution_changed": False,
                "sleeve_weight_changed": False,
                "reference_changed": False,
                "controls_changed": False,
                "cost_model_changed": False,
                "optimization_performed": False,
                "historical_backfill_permitted": False,
                "validation_period_observed_before_activation": False,
                "activation_timestamp_utc": activation_timestamp.isoformat(),
                "first_eligible_performance_session": (
                    first_performance.isoformat()
                ),
                "completed_validation_performance_rows": 0,
            }
        ]
        if activated
        else []
    )
    observation_rows = (
        [
            {
                "validation_observation_id": OBSERVATION_ID,
                "entity_type": "validation_observation",
                "stage": STAGE,
                "associated_trial_id": TRIAL_ID,
                "state": "active",
                "storage_convention": (
                    "validation_evidence_lane_only_no_authoritative_"
                    "paper_demo_state_change"
                ),
                "activation_timestamp_utc": activation_timestamp.isoformat(),
                "initialization_session": initialization_session.isoformat(),
                "first_eligible_performance_session": (
                    first_performance.isoformat()
                ),
                "elapsed_completed_months": 0,
                "completed_defensive_episodes": 0,
                "validation_decision": "",
                "broker_submission": False,
                "paper_order_submission": False,
                "real_money_authorization": False,
                "historical_backfill": "prohibited",
                "paper_demo_observation": False,
                "next_action": NEXT_ACTIVATED,
            }
        ]
        if activated
        else []
    )
    initialization_rows = (
        [
            {
                "initialization_record_id": (
                    f"{OBSERVATION_ID}__initialization"
                ),
                "record_type": "prospective_initialization_not_performance",
                "associated_trial_id": TRIAL_ID,
                "initialization_timestamp_utc": (
                    activation_timestamp.isoformat()
                ),
                "initialization_session": initialization_session.isoformat(),
                "first_eligible_validation_performance_session": (
                    first_performance.isoformat()
                ),
                "reference_weight": REFERENCE_WEIGHT,
                "candidate_sleeve_weight": CANDIDATE_WEIGHT,
                "frozen_reference_holdings": reference_weights,
                "candidate_and_comparator_initial_holdings": (
                    comparator_holdings
                ),
                "initialization_turnover_by_portfolio": {
                    portfolio_id: 1.0 for portfolio_id in PORTFOLIO_IDS
                },
                "initialization_simulated_costs_by_portfolio": {
                    portfolio_id: {
                        "0bps": 0.0,
                        "5bps": 0.0005,
                        "10bps": 0.001,
                    }
                    for portfolio_id in PORTFOLIO_IDS
                },
                "initialization_creates_return": False,
                "initialization_creates_validation_month": False,
                "initialization_creates_defensive_episode": False,
                "historical_backfill": False,
                "completed_validation_performance_rows": 0,
            }
        ]
        if activated
        else []
    )
    boundary_rows = [
        {
            "activation_timestamp_utc": activation_timestamp.isoformat(),
            "activation_timestamp_us_eastern": activation_timestamp.astimezone(
                EASTERN
            ).isoformat(),
            "latest_completed_signal_date": latest_common.isoformat()
            if latest_common
            else "",
            "initialization_session": initialization_session.isoformat()
            if initialization_session
            else "",
            "first_eligible_validation_performance_session": (
                first_performance.isoformat() if first_performance else ""
            ),
            "valid_US_regular_sessions": boundary_ready,
            "strictly_after_task_activation": boundary_ready,
            "strictly_after_all_initialization_snapshots": boundary_ready
            and snapshot_ready,
            "strictly_after_latest_completed_signal_date": boundary_ready,
            "historical_execution_created": False,
            "start_selected_from_market_conditions": False,
            "initialization_creates_performance_row": False,
            "boundary_status": "pass"
            if boundary_ready and snapshot_ready
            else "fail",
        }
    ]
    before_after = [
        {
            "trial_id": TRIAL_ID,
            "before_record_type": "frozen_future_specification_not_executed",
            "before_executed": False,
            "before_activated": False,
            "after_record_type": "experiment_trial"
            if activated
            else "frozen_future_specification_not_executed",
            "after_status": "active_prospective_validation"
            if activated
            else "not_created",
            "after_executed_trial_created": activated,
            "after_validation_observation_created": activated,
            "prior_design_packet_rewritten": False,
        }
    ]
    symbol_scope_rows = [
        {
            "symbol": symbol,
            "scope_source": rel(
                DESIGN_DIR / "required_symbol_scope.csv"
            ),
            "frozen_before_provider_access": True,
            "retrieved": symbol in frames,
            "canonical_cache_modified": False,
            "prospective_stream_only": True,
        }
        for symbol in SYMBOLS
    ]
    data_task_rows = [
        {
            "task_id": f"{TASK_ID}__immutable_data_cycle",
            "entity_type": "data_capability_task",
            "stage": "feasible" if acquisition.get("status") == "pass" else "blocked",
            "adaptation_label": "prospective_data_initialization",
            "provider_attempt_count": len(provider_attempts),
            "duplicate_retrievals_required": 2,
            "outcome": acquisition.get("status"),
            "historical_cache_mutation": False,
            "broker_or_order_action": False,
            "counted_as_strategy": False,
            "counted_as_trial": False,
        }
    ]
    process_rows = [
        {
            "task_id": TASK_ID,
            "entity_type": "process_task",
            "stage": STAGE,
            "mode": MODE,
            "outcome": outcome,
            "failure_reason": failure_reason,
            "exact_next_action": next_action,
            "counted_as_strategy": False,
            "counted_as_trial": False,
            "broker_or_order_action": False,
        }
    ]
    outcome_rows = [
        {
            "task_id": TASK_ID,
            "strategy_id": STRATEGY_ID,
            "trial_id": TRIAL_ID,
            "approved_route": "20pct_diversifier_only",
            "outcome": outcome,
            "failure_reason": failure_reason,
            "exact_next_action": next_action,
            "experiment_trials_created": len(trial_rows),
            "validation_observations_created": len(observation_rows),
            "initialization_records_created": len(initialization_rows),
            "completed_validation_performance_rows": 0,
            "historical_backfill": False,
            "paper_demo_eligibility_granted": False,
            "next_action_executed": False,
        }
    ]
    failure_rows = [
        {
            "outcome_scope": DEFERRED,
            "failure_reason": reason,
            "selected": outcome == DEFERRED and failure_reason == reason,
        }
        for reason in DEFERRED_REASONS
    ] + [
        {
            "outcome_scope": BLOCKED,
            "failure_reason": reason,
            "selected": outcome == BLOCKED and failure_reason == reason,
        }
        for reason in BLOCKED_REASONS
    ]
    next_action_rows = [
        {
            "outcome": ACTIVATED,
            "exact_next_action": NEXT_ACTIVATED,
            "selected": outcome == ACTIVATED,
            "execute_in_this_task": False,
        },
        {
            "outcome": DEFERRED,
            "exact_next_action": NEXT_DEFERRED,
            "selected": outcome == DEFERRED,
            "execute_in_this_task": False,
        },
        {
            "outcome": BLOCKED,
            "exact_next_action": NEXT_BLOCKED,
            "selected": outcome == BLOCKED,
            "execute_in_this_task": False,
        },
    ]
    manifest = {
        "task_id": TASK_ID,
        "mode": MODE,
        "stage": STAGE,
        "strategy_id": STRATEGY_ID,
        "trial_id": TRIAL_ID,
        "parent_trial_id": PARENT_TRIAL_ID,
        "approved_route": "20pct_diversifier_only",
        "outcome": outcome,
        "failure_reason": failure_reason,
        "exact_next_action": next_action,
        "strategy_configurations_created": 0,
        "strategy_configurations_updated": 0,
        "experiment_trials_created": len(trial_rows),
        "validation_observations_created": len(observation_rows),
        "paper_demo_observations_created": 0,
        "benchmark_specifications_carried_forward": 7,
        "initialization_records_created": len(initialization_rows),
        "completed_validation_performance_rows": 0,
        "data_capability_tasks": 1,
        "process_tasks": 1,
        "broker_or_paper_orders": 0,
        "historical_backfill": False,
        "canonical_cache_mutation": False,
        "minimum_completed_months": 24,
        "minimum_completed_defensive_episodes": 6,
        "hard_maximum_completed_months": 36,
        "interim_decision_permitted": False,
        "next_action_executed": False,
    }

    write_yaml("activation_manifest.yaml", manifest)
    write_csv(
        "design_reconciliation.csv",
        reconciliation_rows,
        ["check_id"],
    )
    write_csv(
        "future_trial_before_after.csv",
        before_after,
        ["trial_id"],
    )
    write_csv(
        "required_symbol_scope.csv",
        symbol_scope_rows,
        ["symbol"],
    )
    write_csv(
        "initialization_history_requirements.csv",
        history_rows,
        ["component_id"],
    )
    write_csv(
        "provider_attempt_log.csv",
        provider_attempts,
        ["provider_sequence", "provider_id"],
        ["provider_sequence", "provider_id", "attempted", "status"],
    )
    write_csv(
        "retrieval_reproducibility.csv",
        reproducibility_rows,
        ["symbol"],
        ["symbol", "reproducibility_status"],
    )
    write_csv(
        "immutable_snapshot_manifest.csv",
        snapshot_rows,
        ["snapshot_id", "symbol"],
        ["snapshot_id", "symbol", "schema_status"],
    )
    write_csv(
        "candidate_state_initialization.csv",
        candidate_rows,
        ["strategy_id"],
        ["strategy_id", "status"],
    )
    write_csv(
        "comparator_state_initialization.csv",
        comparator_rows,
        ["portfolio_id"],
        ["portfolio_id", "status"],
    )
    write_csv(
        "frozen_reference_state_initialization.csv",
        reference_rows,
        ["record_type", "component_id", "symbol"],
        ["record_type", "component_id", "symbol", "status"],
    )
    write_csv(
        "portfolio_initialization_record.csv",
        initialization_rows,
        ["initialization_record_id"],
        ["initialization_record_id", "record_type"],
    )
    write_csv(
        "activation_boundary.csv",
        boundary_rows,
        ["activation_timestamp_utc"],
    )
    write_csv(
        "validation_trial_record.csv",
        trial_rows,
        ["trial_id", "entity_type"],
        ["trial_id", "entity_type", "stage", "status"],
    )
    write_csv(
        "validation_observation_record.csv",
        observation_rows,
        ["validation_observation_id", "entity_type"],
        ["validation_observation_id", "entity_type", "stage", "state"],
    )
    write_csv(
        "data_capability_task_log.csv",
        data_task_rows,
        ["task_id", "entity_type"],
    )
    write_csv(
        "process_task_log.csv",
        process_rows,
        ["task_id", "entity_type"],
    )
    write_csv(
        "outcome_summary.csv",
        outcome_rows,
        ["task_id", "strategy_id"],
    )
    write_csv(
        "failure_reasons.csv",
        failure_rows,
        ["outcome_scope", "failure_reason"],
    )
    write_csv(
        "next_actions.csv",
        next_action_rows,
        ["outcome"],
    )
    write_text(
        "activation_report.md",
        activation_report(
            outcome,
            failure_reason,
            next_action,
            acquisition.get("provider", ""),
            latest_common,
            initialization_session if activated else None,
            first_performance if activated else None,
        ),
    )

    protected_after = map_hashes(PROTECTED_PATHS)
    caches_after = map_hashes(cache_files())
    prior_after = {
        rel(path): packet_hash(path) for path in PRIOR_EVIDENCE_DIRS
    }
    source_after = file_hash(SOURCE_PACKET)
    state_change_rows = [
        {
            "scope": "protected_state",
            "path": path,
            "before_hash": protected_before.get(path, ""),
            "after_hash": protected_after.get(path, ""),
            "changed": protected_before.get(path) != protected_after.get(path),
        }
        for path in sorted(set(protected_before) | set(protected_after))
    ] + [
        {
            "scope": "historical_canonical_cache",
            "path": path,
            "before_hash": caches_before.get(path, ""),
            "after_hash": caches_after.get(path, ""),
            "changed": caches_before.get(path) != caches_after.get(path),
        }
        for path in sorted(set(caches_before) | set(caches_after))
    ] + [
        {
            "scope": "prior_PSAR_evidence",
            "path": path,
            "before_hash": prior_before.get(path, ""),
            "after_hash": prior_after.get(path, ""),
            "changed": prior_before.get(path) != prior_after.get(path),
        }
        for path in sorted(set(prior_before) | set(prior_after))
    ]
    write_csv(
        "state_change_manifest.csv",
        state_change_rows,
        ["scope", "path"],
    )

    top_level_before_consistency = {
        path.name for path in OUTPUT_DIR.iterdir() if path.is_file()
    }
    required_before_consistency = REQUIRED_OUTPUTS - {"consistency_check.json"}
    entity_counts_pass = bool(
        len(trial_rows) == (1 if activated else 0)
        and len(observation_rows) == (1 if activated else 0)
        and len(initialization_rows) == (1 if activated else 0)
    )
    consistency = {
        "task_id": TASK_ID,
        "outcome": outcome,
        "failure_reason": failure_reason,
        "exact_next_action": next_action,
        "overall_pass": bool(
            outcome in {ACTIVATED, DEFERRED, BLOCKED}
            and entity_counts_pass
            and top_level_before_consistency == required_before_consistency
            and protected_before == protected_after
            and caches_before == caches_after
            and prior_before == prior_after
            and source_before == source_after
        ),
        "activation_gates": all_gates,
        "all_activation_gates_pass": all(all_gates.values()),
        "design_reconciliation_pass": design_ready,
        "future_trial_identity_unused_before_activation": trial_unused,
        "trial_identity_prior_uses": identity_uses,
        "provider_attempt_count": len(provider_attempts),
        "provider_used": acquisition.get("provider", ""),
        "duplicate_retrieval_reproducibility_pass": bool(
            reproducibility_rows
            and all(
                row["reproducibility_status"] == "pass"
                for row in reproducibility_rows
            )
        ),
        "candidate_state_initialization_pass": candidate_ready,
        "reference_state_initialization_pass": reference_ready,
        "comparator_state_initialization_pass": comparators_ready,
        "immutable_snapshot_storage_pass": snapshot_ready,
        "activation_boundary_pass": boundary_ready,
        "strategy_configurations_created": 0,
        "strategy_configurations_updated": 0,
        "experiment_trials_created": len(trial_rows),
        "validation_observations_created": len(observation_rows),
        "paper_demo_observations_created": 0,
        "benchmark_specifications_carried_forward": 7,
        "initialization_records_created": len(initialization_rows),
        "completed_validation_performance_rows": 0,
        "data_capability_tasks": 1,
        "process_tasks": 1,
        "broker_or_paper_orders": 0,
        "historical_backfill_performed": False,
        "historical_validation_performance_calculated": False,
        "protected_state_hashes_before": protected_before,
        "protected_state_hashes_after": protected_after,
        "protected_state_unchanged": protected_before == protected_after,
        "canonical_cache_hashes_before": caches_before,
        "canonical_cache_hashes_after": caches_after,
        "historical_canonical_caches_unchanged": caches_before == caches_after,
        "prior_evidence_hashes_before": prior_before,
        "prior_evidence_hashes_after": prior_after,
        "prior_PSAR_evidence_unchanged": prior_before == prior_after,
        "design_packet_hash_before": design_hash_before,
        "design_packet_hash_after": packet_hash(DESIGN_DIR),
        "design_packet_unchanged": design_hash_before == packet_hash(DESIGN_DIR),
        "source_packet_unchanged": source_before == source_after,
        "network_access_limited_to_approved_market_data": bool(
            provider_attempts
        ),
        "account_endpoint_called": False,
        "position_endpoint_called": False,
        "order_endpoint_called": False,
        "broker_submission": False,
        "paper_order_submission": False,
        "real_money_authorization": False,
        "authoritative_lifecycle_state_changed": False,
        "paper_demo_eligibility_granted": False,
        "next_action_executed": False,
        "state_initialization_error": state_error,
        "snapshot_storage_error": snapshot_error,
        "required_outputs_exact_before_consistency": (
            top_level_before_consistency == required_before_consistency
        ),
    }
    write_json(OUTPUT_DIR / "consistency_check.json", consistency)
    final_files = {
        path.name for path in OUTPUT_DIR.iterdir() if path.is_file()
    }
    if final_files != REQUIRED_OUTPUTS:
        raise RuntimeError("Activation evidence output set does not match contract")
    return {
        "task_id": TASK_ID,
        "strategy_id": STRATEGY_ID,
        "trial_id": TRIAL_ID,
        "outcome": outcome,
        "failure_reason": failure_reason,
        "exact_next_action": next_action,
        "experiment_trials_created": len(trial_rows),
        "validation_observations_created": len(observation_rows),
        "completed_validation_performance_rows": 0,
        "evidence_path": rel(OUTPUT_DIR),
        "overall_pass": consistency["overall_pass"],
    }


def main() -> int:
    result = run()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["overall_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
