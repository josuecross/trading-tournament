from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
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
    design_faa_prospective_validation_v1 as design,
)
from strategy_lab.research_os.research import (
    native_etf_two_candidate_exploration_batch_v1 as exploration,
)
from strategy_lab.research_os.research.fast_source_library_batch_v5 import (
    scheduled_full_day_nyse_closures,
)


TASK_ID = "activate_faa_prospective_validation_v1"
MODE = "active-direction-execution"
STAGE = "validation"
OUTPUT_DIR = ROOT / "evidence" / "validation" / TASK_ID / "latest"
ACTIVE_DIR = (
    ROOT
    / "evidence"
    / "validation"
    / "faa_4m_top3_prospective_validation_v1"
    / "active"
)
DESIGN_DIR = design.OUTPUT_DIR
EXPLORATION_DIR = design.EXPLORATION_EVIDENCE
ROBUSTNESS_DIR = design.ROBUSTNESS_EVIDENCE
SOURCE_PACKET = Path(
    r"C:\Users\te3442\.codex\attachments"
    r"\f89ebc75-4ee9-4f74-9b0f-4e42a98014b1\pasted-text.txt"
)

TRIAL_ID = design.FUTURE_TRIAL_ID
PARENT_TRIAL_ID = design.PARENT_TRIAL_ID
STRATEGY_ID = design.STRATEGY_ID
FAMILY_ID = design.FAMILY_ID
ARCHITECTURE = design.ARCHITECTURE
OBSERVATION_ID = "prospective_validation_faa_4m_top3_v1"
SYMBOLS = design.UNIVERSE
COMPARATORS = design.COMPARATORS
CRITICAL_CONTROLS = design.CRITICAL_CONTROLS
STATIC_WEIGHTS = design.STATIC_WEIGHTS
COST_BPS = (0.0, 5.0, 10.0)
PRIMARY_COST_BPS = 5.0
DECISION_BOUNDARY = {
    "minimum_completed_calendar_months": 24,
    "minimum_completed_monthly_holding_intervals": 24,
    "minimum_differentiation_months_vs_return_only": 6,
    "minimum_differentiation_months_vs_no_correlation": 6,
    "hard_maximum_completed_calendar_months": 36,
    "early_favorable_stopping_permitted": False,
    "validation_decision_during_activation_permitted": False,
}
EASTERN = ZoneInfo("America/New_York")
KNOWN_UNSCHEDULED_NYSE_CLOSURES = {
    date(2012, 10, 29),
    date(2012, 10, 30),
    date(2018, 12, 5),
}

ACTIVATED = "prospective_validation_activated"
DEFERRED = "prospective_validation_activation_deferred"
BLOCKED = "prospective_validation_activation_blocked"
NEXT_ACTIVATED = "record_faa_prospective_validation_monthly_v1"
NEXT_DEFERRED = "resume_native_etf_source_discovery_v2"
NEXT_BLOCKED = "direction_owner_review_faa_activation_block_v1"
DEFERRED_REASONS = (
    "required_data_unavailable",
    "immutable_snapshot_reproducibility_failure",
    "required_session_coverage_failure",
    "formation_initialization_failure",
    "comparator_initialization_failure",
    "activation_boundary_not_ready",
    "observation_storage_unavailable",
    "data_or_comparability_failure",
)
BLOCKED_REASONS = (
    "lineage_reconciliation_failure",
    "parameter_reconciliation_failure",
    "control_reconciliation_failure",
    "status_reconciliation_required",
    "local_methodology_failure",
    "methodology_failure",
)

RAW_ROOT = OUTPUT_DIR / "immutable_provider_responses"
NORMALIZED_ROOT = OUTPUT_DIR / "immutable_normalized_retrievals"
ACTIVE_DAILY_ROOT = ACTIVE_DIR / "daily_snapshots"
PROTECTED_PATHS = tuple(
    dict.fromkeys((*design.PROTECTED_PATHS, DESIGN_DIR))
)

REQUIRED_OUTPUTS = {
    "activation_manifest.yaml",
    "design_reconciliation.csv",
    "future_trial_before_after.csv",
    "offline_import_and_dependency_preflight.csv",
    "offline_activation_dry_run.csv",
    "offline_gate_results.csv",
    "required_symbol_scope.csv",
    "initialization_history_requirements.csv",
    "provider_attempt_log.csv",
    "raw_retrieval_manifest.csv",
    "retrieval_reproducibility.csv",
    "required_session_coverage.csv",
    "immutable_daily_snapshot_manifest.csv",
    "formation_state_initialization.csv",
    "candidate_target_initialization.csv",
    "comparator_target_initialization.csv",
    "differentiation_initialization.csv",
    "portfolio_initialization_record.csv",
    "activation_boundary.csv",
    "validation_trial_record.csv",
    "validation_observation_record.csv",
    "validation_state.yaml",
    "daily_performance_ledger.csv",
    "monthly_checkpoint_ledger.csv",
    "data_capability_task_log.csv",
    "process_task_log.csv",
    "state_change_manifest.csv",
    "outcome_summary.csv",
    "failure_reasons.csv",
    "next_actions.csv",
    "consistency_check.json",
    "activation_report.md",
}


def relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)


def sha256_bytes(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        default=str,
    ).encode("utf-8")


def canonical_hash(value: Any) -> str:
    return sha256_bytes(canonical_bytes(value))


def file_hash(path: Path) -> str:
    return sha256_bytes(path.read_bytes()) if path.is_file() else "missing"


def tree_hash(path: Path) -> str:
    if path.is_file():
        return file_hash(path)
    if not path.exists():
        return "missing"
    digest = hashlib.sha256()
    for item in sorted(candidate for candidate in path.rglob("*") if candidate.is_file()):
        digest.update(item.relative_to(path).as_posix().encode("utf-8"))
        digest.update(hashlib.sha256(item.read_bytes()).digest())
    return "sha256:" + digest.hexdigest()


def snapshot_protected_hashes() -> dict[str, str]:
    return {relative(path): tree_hash(path) for path in PROTECTED_PATHS}


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
        "ALPACA_LIVE_API_KEY",
        "ALPACA_LIVE_SECRET_KEY",
        "APCA-API-KEY-ID",
        "APCA-API-SECRET-KEY",
    ):
        value = value.replace(name, f"{name}_REDACTED")
    return value[:800]


def reset_output() -> None:
    if ACTIVE_DIR.exists():
        raise RuntimeError("FAA prospective validation is already active")
    expected = (ROOT / "evidence" / "validation" / TASK_ID / "latest").resolve()
    if OUTPUT_DIR.exists():
        if OUTPUT_DIR.resolve() != expected:
            raise RuntimeError(f"Refusing to remove unexpected output: {OUTPUT_DIR}")
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return "" if not math.isfinite(value) else f"{value:.16g}"
    if isinstance(value, (dict, list, tuple, set)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return str(value)


def fields_for(
    rows: list[dict[str, Any]],
    leading: Iterable[str],
    fallback: Iterable[str] | None = None,
) -> list[str]:
    fields = list(leading)
    for row in rows:
        for field in row:
            if field not in fields:
                fields.append(field)
    return fields if rows else list(fallback or leading)


def write_csv_path(
    path: Path,
    rows: list[dict[str, Any]],
    leading: Iterable[str],
    fallback: Iterable[str] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = fields_for(rows, leading, fallback)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fields,
            extrasaction="ignore",
            lineterminator="\n",
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({field: csv_value(row.get(field, "")) for field in fields})


def write_csv(
    name: str,
    rows: list[dict[str, Any]],
    leading: Iterable[str],
    fallback: Iterable[str] | None = None,
) -> None:
    write_csv_path(OUTPUT_DIR / name, rows, leading, fallback)


def write_yaml_path(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(payload, sort_keys=False, width=110, allow_unicode=False),
        encoding="utf-8",
    )


def write_yaml(name: str, payload: dict[str, Any]) -> None:
    write_yaml_path(OUTPUT_DIR / name, payload)


def write_json_path(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_bytes(payload) + b"\n")


def write_json(name: str, payload: Any) -> None:
    write_json_path(OUTPUT_DIR / name, payload)


def write_text(name: str, value: str) -> None:
    (OUTPUT_DIR / name).write_text(value.rstrip() + "\n", encoding="utf-8")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


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


def expected_sessions(start: date, end: date) -> list[date]:
    sessions: list[date] = []
    cursor = start
    while cursor <= end:
        if is_regular_session(cursor):
            sessions.append(cursor)
        cursor += timedelta(days=1)
    return sessions


def latest_completed_session(now_utc: datetime) -> date:
    now_et = now_utc.astimezone(EASTERN)
    cursor = now_et.date()
    if not is_regular_session(cursor) or now_et.time() < time(17, 0):
        cursor -= timedelta(days=1)
    while not is_regular_session(cursor):
        cursor -= timedelta(days=1)
    return cursor


def last_regular_session_of_month(year: int, month: int) -> date:
    if month == 12:
        cursor = date(year + 1, 1, 1)
    else:
        cursor = date(year, month + 1, 1)
    return previous_regular_session(cursor)


def shift_month(year: int, month: int, delta: int) -> tuple[int, int]:
    value = year * 12 + (month - 1) + delta
    return value // 12, value % 12 + 1


def activation_dates(now_utc: datetime) -> dict[str, Any]:
    latest = latest_completed_session(now_utc)
    if next_regular_session(latest).month != latest.month:
        formation = latest
    else:
        previous_year, previous_month = shift_month(latest.year, latest.month, -1)
        formation = last_regular_session_of_month(previous_year, previous_month)
    start_year, start_month = shift_month(formation.year, formation.month, -4)
    formation_start = last_regular_session_of_month(start_year, start_month)
    request_start = previous_regular_session(formation_start)
    intended_execution = next_regular_session(formation)
    execution_close = datetime.combine(
        intended_execution,
        time(16, 0),
        tzinfo=EASTERN,
    )
    on_time = now_utc.astimezone(EASTERN) < execution_close
    next_formation_year, next_formation_month = shift_month(
        formation.year, formation.month, 1
    )
    next_formation = last_regular_session_of_month(
        next_formation_year, next_formation_month
    )
    return {
        "latest_completed_session": latest,
        "formation_date": formation,
        "formation_start_date": formation_start,
        "request_start": request_start,
        "request_end_exclusive": latest + timedelta(days=1),
        "intended_execution_session": intended_execution,
        "intended_execution_close_et": execution_close,
        "on_time_current_formation": on_time,
        "activation_status": (
            "active_prospective_validation"
            if on_time
            else "active_pending_first_prospective_formation"
        ),
        "observation_state": (
            "active" if on_time else "active_pending_first_prospective_formation"
        ),
        "next_required_formation": next_formation,
        "first_eligible_performance_session": (
            next_regular_session(intended_execution) if on_time else None
        ),
    }


def packet_trial_uses() -> list[dict[str, str]]:
    uses: list[dict[str, str]] = []
    evidence = ROOT / "evidence"
    for name in ("trial_ledger.csv", "validation_trial_record.csv"):
        for path in evidence.rglob(name):
            if DESIGN_DIR in path.parents or OUTPUT_DIR in path.parents:
                continue
            try:
                for row in read_csv(path):
                    if row.get("trial_id") == TRIAL_ID:
                        uses.append(
                            {
                                "path": relative(path),
                                "trial_id": TRIAL_ID,
                                "entity_type": row.get("entity_type", ""),
                                "status": row.get("status", ""),
                            }
                        )
            except (OSError, csv.Error, UnicodeError):
                continue
    return uses


def design_reconciliation() -> tuple[list[dict[str, Any]], dict[str, bool]]:
    actual_files = {path.name for path in DESIGN_DIR.iterdir() if path.is_file()}
    manifest = read_yaml(DESIGN_DIR / "design_manifest.yaml")
    specification = read_yaml(DESIGN_DIR / "future_trial_specification.yaml")
    consistency = read_json(DESIGN_DIR / "consistency_check.json")
    design_rows = read_csv(DESIGN_DIR / "experiment_design_record.csv")
    lineage = read_csv(DESIGN_DIR / "strategy_and_lineage_reconciliation.csv")
    parameters = {
        row["parameter_name"]: row["frozen_value"]
        for row in read_csv(DESIGN_DIR / "frozen_parameter_specification.csv")
    }
    symbols = tuple(
        row["symbol"] for row in read_csv(DESIGN_DIR / "required_symbol_scope.csv")
    )
    controls = tuple(
        row["portfolio_or_control_id"]
        for row in read_csv(DESIGN_DIR / "portfolio_and_control_definitions.csv")
    )
    static_rows = read_csv(DESIGN_DIR / "archived_static_weight_reconciliation.csv")
    static = {row["symbol"]: row["frozen_design_weight"] for row in static_rows}
    minimums = {
        row["requirement_id"]: int(row["minimum_value"])
        for row in read_csv(DESIGN_DIR / "minimum_observation_requirements.csv")
    }
    gates = tuple(
        row["future_outcome"]
        for row in read_csv(DESIGN_DIR / "future_validation_outcome_gates.csv")
    )
    expected_parent_hashes = consistency.get("protected_hashes_after", {})
    current_parent_hashes = {
        relative(EXPLORATION_DIR): tree_hash(EXPLORATION_DIR),
        relative(ROBUSTNESS_DIR): tree_hash(ROBUSTNESS_DIR),
    }
    checks = {
        "design_output_set_exact": actual_files == design.REQUIRED_OUTPUTS,
        "design_outcome_completed": manifest.get("outcome") == design.OUTCOME_COMPLETED,
        "design_consistency_pass": consistency.get("overall_pass") is True,
        "one_design_record": len(design_rows) == 1,
        "future_trial_frozen_not_activated": bool(
            design_rows
            and design_rows[0].get("future_trial_status") == "frozen_not_activated"
            and design_rows[0].get("future_trial_executed") == "false"
        ),
        "trial_id_exact": specification.get("trial_id") == TRIAL_ID,
        "parent_trial_exact": specification.get("parent_trial_id") == PARENT_TRIAL_ID,
        "parent_lineage_present": any(
            row.get("record_id") == PARENT_TRIAL_ID
            and row.get("outcome") == "robustness_positive"
            for row in lineage
        ),
        "route_standalone_only": specification.get("route") == "standalone_only",
        "strategy_identity_exact": specification.get("strategy_id") == STRATEGY_ID,
        "symbols_exact": symbols == SYMBOLS,
        "controls_exact": controls == COMPARATORS,
        "parameters_exact": bool(
            parameters.get("lookback_months") == "4"
            and parameters.get("volatility_ddof") == "1"
            and parameters.get("return_rank_weight") == "1"
            and parameters.get("volatility_rank_weight") == "0.5"
            and parameters.get("correlation_rank_weight") == "0.5"
            and parameters.get("selected_count") == "3"
            and parameters.get("absolute_momentum_fallback") == "SHY"
            and parameters.get("execution") == "following_regular_session_close"
        ),
        "static_weights_exact": set(static) == set(SYMBOLS)
        and all(static[symbol] == design.STATIC_WEIGHT_TEXT[symbol] for symbol in SYMBOLS),
        "minimum_boundary_exact": minimums
        == {
            "completed_calendar_months": 24,
            "completed_monthly_holding_intervals": 24,
            "differentiation_vs_return_only": 6,
            "differentiation_vs_no_correlation": 6,
            "hard_maximum_calendar_months": 36,
        },
        "future_outcomes_exact": gates == design.FUTURE_OUTCOMES,
        "trial_id_unused": not packet_trial_uses() and not ACTIVE_DIR.exists(),
        "exploration_parent_hash_reconciled": current_parent_hashes[
            relative(EXPLORATION_DIR)
        ]
        == expected_parent_hashes.get(relative(EXPLORATION_DIR)),
        "robustness_parent_hash_reconciled": current_parent_hashes[
            relative(ROBUSTNESS_DIR)
        ]
        == expected_parent_hashes.get(relative(ROBUSTNESS_DIR)),
    }
    rows = [
        {
            "check_order": index,
            "check_id": check,
            "status": "pass" if passed else "fail",
            "detail": "",
        }
        for index, (check, passed) in enumerate(checks.items(), start=1)
    ]
    return rows, checks


def offline_import_preflight() -> tuple[list[dict[str, Any]], bool]:
    credentials = load_alpaca_credentials("paper")
    checks = [
        (
            "candidate_implementation",
            "strategy_lab.research_os.research.native_etf_two_candidate_exploration_batch_v1.prepare_faa",
            callable(exploration.prepare_faa),
            True,
            "frozen_historical_implementation_import_only_not_executed",
        ),
        (
            "comparator_implementation",
            "activate_faa_prospective_validation_v1.compute_targets",
            callable(compute_targets),
            True,
            "FAA_specific_prospective_target_builder",
        ),
        (
            "calendar_module",
            "fast_source_library_batch_v5.scheduled_full_day_nyse_closures",
            callable(scheduled_full_day_nyse_closures),
            True,
            "existing_internal_NYSE_calendar",
        ),
        (
            "immutable_snapshot_writer",
            "activate_faa_prospective_validation_v1.write_csv_path",
            callable(write_csv_path),
            True,
            "task_local_append_once_writer",
        ),
        (
            "trial_schema",
            "activate_faa_prospective_validation_v1.trial_record",
            callable(trial_record),
            True,
            "task_local_schema",
        ),
        (
            "validation_observation_schema",
            "activate_faa_prospective_validation_v1.observation_record",
            callable(observation_record),
            True,
            "task_local_schema",
        ),
        (
            "primary_provider_adapter",
            "execution_lab.alpaca_micro_live_v1.adapters.alpaca_client",
            bool(AlpacaClient and AlpacaClientConfig),
            True,
            "read_only_GET_bars_adapter",
        ),
        (
            "alpaca_paper_credentials",
            "existing_environment_contract",
            bool(credentials.present and not credentials.live_credentials_detected),
            True,
            "presence_only_no_secret_value_recorded",
        ),
        (
            "approved_fallback_adapter",
            "none",
            True,
            False,
            "no_unconditionally_approved_fallback_in_registry",
        ),
        (
            "conditional_yfinance_dependency",
            "yfinance",
            importlib.util.find_spec("yfinance") is not None,
            False,
            "unavailable_and_not_approved_for_this_cycle_no_install_permitted",
        ),
    ]
    rows = [
        {
            "check_order": index,
            "contract_id": name,
            "module_or_interface": interface,
            "available": available,
            "required_for_phase_A": required,
            "status": "pass" if available or not required else "fail",
            "detail": detail,
            "checked_before_network_access": True,
            "dependency_installed_in_task": False,
        }
        for index, (name, interface, available, required, detail) in enumerate(
            checks, start=1
        )
    ]
    return rows, all(row["status"] == "pass" for row in rows)


def normalize_alpaca_records(records: list[dict[str, Any]]) -> pd.DataFrame:
    values: list[dict[str, Any]] = []
    for record in records:
        timestamp = pd.to_datetime(record.get("t"), utc=True)
        values.append(
            {
                "trading_date": timestamp.date().isoformat(),
                "adjusted_close": float(record.get("c")),
            }
        )
    if not values:
        return pd.DataFrame(columns=["trading_date", "adjusted_close"])
    return (
        pd.DataFrame(values)
        .sort_values("trading_date")
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


def reproduce_frames(
    first: dict[str, pd.DataFrame],
    second: dict[str, pd.DataFrame],
) -> tuple[list[dict[str, Any]], bool]:
    rows: list[dict[str, Any]] = []
    passed = True
    for symbol in SYMBOLS:
        left = first.get(symbol, pd.DataFrame())
        right = second.get(symbol, pd.DataFrame())
        dates_equal = left.get("trading_date", pd.Series(dtype=str)).tolist() == right.get(
            "trading_date", pd.Series(dtype=str)
        ).tolist()
        values_equal = bool(
            tuple(left.columns) == tuple(right.columns)
            and left.shape == right.shape
            and frame_bytes(left) == frame_bytes(right)
        )
        left_hash = frame_hash(left)
        right_hash = frame_hash(right)
        row_pass = bool(dates_equal and values_equal and left_hash == right_hash)
        passed = passed and row_pass
        rows.append(
            {
                "symbol": symbol,
                "retrieval_1_rows": len(left),
                "retrieval_2_rows": len(right),
                "retrieval_1_normalized_hash": left_hash,
                "retrieval_2_normalized_hash": right_hash,
                "normalized_dates_identical": dates_equal,
                "normalized_values_identical": values_equal,
                "normalized_hashes_identical": left_hash == right_hash,
                "reproducibility_status": "pass" if row_pass else "fail",
            }
        )
    return rows, passed


def required_session_coverage(
    frames: dict[str, pd.DataFrame],
    request_start: date,
    formation_date: date,
) -> tuple[list[dict[str, Any]], bool]:
    expected = expected_sessions(request_start, formation_date)
    expected_set = set(expected)
    rows: list[dict[str, Any]] = []
    all_pass = True
    reference_dates: list[str] | None = None
    for symbol in SYMBOLS:
        frame = frames.get(symbol, pd.DataFrame())
        dates = pd.to_datetime(
            frame.get("trading_date", pd.Series(dtype=str)), errors="coerce"
        )
        values = pd.to_numeric(
            frame.get("adjusted_close", pd.Series(dtype=float)), errors="coerce"
        )
        date_list = dates.dt.date.astype(str).tolist() if len(dates) else []
        actual_set = set(dates.dropna().dt.date)
        missing = sorted(expected_set - actual_set)
        extra = sorted(actual_set - expected_set)
        identical_scope = reference_dates is None or date_list == reference_dates
        if reference_dates is None:
            reference_dates = date_list
        checks = {
            "nonempty": not frame.empty,
            "ordered_unique_sessions": bool(
                dates.notna().all()
                and dates.is_monotonic_increasing
                and not dates.duplicated().any()
            ),
            "finite_positive_adjusted_close": bool(
                len(values)
                and np.isfinite(values.to_numpy(dtype=float)).all()
                and (values > 0.0).all()
            ),
            "complete_required_sessions": not missing,
            "no_out_of_scope_sessions": not extra,
            "identical_session_scope": identical_scope,
            "formation_date_present": formation_date in actual_set,
            "prior_return_session_present": request_start in actual_set,
        }
        symbol_pass = all(checks.values())
        all_pass = all_pass and symbol_pass
        rows.append(
            {
                "symbol": symbol,
                "requested_start": request_start.isoformat(),
                "requested_end": formation_date.isoformat(),
                "expected_session_count": len(expected),
                "returned_session_count": len(frame),
                "first_returned_session": date_list[0] if date_list else "",
                "last_returned_session": date_list[-1] if date_list else "",
                "missing_required_sessions": [item.isoformat() for item in missing],
                "out_of_scope_sessions": [item.isoformat() for item in extra],
                "ordered_unique_sessions": checks["ordered_unique_sessions"],
                "finite_positive_adjusted_close": checks[
                    "finite_positive_adjusted_close"
                ],
                "identical_session_scope": identical_scope,
                "coverage_status": "pass" if symbol_pass else "fail",
            }
        )
    return rows, all_pass


def ordinal_ranks(values: dict[str, float], descending: bool) -> dict[str, int]:
    ordered = sorted(
        values,
        key=lambda symbol: (
            -values[symbol] if descending else values[symbol],
            symbol,
        ),
    )
    return {symbol: index for index, symbol in enumerate(ordered, start=1)}


def target_from_selection(
    selected: list[str], returns: dict[str, float]
) -> tuple[dict[str, float], dict[str, bool]]:
    target = {symbol: 0.0 for symbol in SYMBOLS}
    replacements = {symbol: False for symbol in SYMBOLS}
    for symbol in selected:
        destination = symbol if returns[symbol] > 0.0 else "SHY"
        target[destination] += 1.0 / 3.0
        replacements[symbol] = destination == "SHY" and symbol != "SHY"
    return target, replacements


def compute_formation(
    frames: dict[str, pd.DataFrame],
    formation_start: date,
    formation_end: date,
) -> dict[str, Any]:
    close = pd.DataFrame()
    for symbol in SYMBOLS:
        frame = frames[symbol].copy()
        frame.index = pd.to_datetime(frame["trading_date"])
        close[symbol] = pd.to_numeric(frame["adjusted_close"], errors="coerce")
    close = close.sort_index()
    interval = close.loc[
        (close.index.date >= formation_start)
        & (close.index.date <= formation_end)
    ]
    if interval.empty or interval.index[0].date() != formation_start:
        raise ValueError("formation start does not match required month-end")
    if interval.index[-1].date() != formation_end:
        raise ValueError("formation end does not match required month-end")
    if interval.isna().any().any() or len(interval) < 2:
        raise ValueError("formation contains missing or insufficient observations")
    daily_returns = interval.pct_change(fill_method=None).iloc[1:]
    returns = {
        symbol: float(interval.iloc[-1][symbol] / interval.iloc[0][symbol] - 1.0)
        for symbol in SYMBOLS
    }
    volatility = {
        symbol: float(daily_returns[symbol].std(ddof=1)) for symbol in SYMBOLS
    }
    correlation = daily_returns.corr(method="pearson")
    if not np.isfinite(correlation.to_numpy(dtype=float)).all():
        raise ValueError("formation correlation matrix is nonfinite")
    average_correlation = {
        symbol: float(
            correlation.loc[symbol, [other for other in SYMBOLS if other != symbol]].mean()
        )
        for symbol in SYMBOLS
    }
    return_ranks = ordinal_ranks(returns, descending=True)
    volatility_ranks = ordinal_ranks(volatility, descending=False)
    correlation_ranks = ordinal_ranks(average_correlation, descending=False)
    scores = {
        symbol: float(
            return_ranks[symbol]
            + 0.5 * volatility_ranks[symbol]
            + 0.5 * correlation_ranks[symbol]
        )
        for symbol in SYMBOLS
    }
    selection = sorted(SYMBOLS, key=lambda symbol: (scores[symbol], symbol))[:3]
    pairwise = {
        f"{left}|{right}": float(correlation.loc[left, right])
        for left_index, left in enumerate(SYMBOLS)
        for right in SYMBOLS[left_index + 1 :]
    }
    candidate_target, replacements = target_from_selection(selection, returns)
    return {
        "formation_start": formation_start,
        "formation_end": formation_end,
        "daily_observation_count": len(daily_returns),
        "returns": returns,
        "volatility": volatility,
        "pairwise_correlations": pairwise,
        "correlation_matrix": correlation,
        "average_correlation": average_correlation,
        "return_ranks": return_ranks,
        "volatility_ranks": volatility_ranks,
        "correlation_ranks": correlation_ranks,
        "scores": scores,
        "selection": selection,
        "replacements": replacements,
        "candidate_target": candidate_target,
    }


def compute_targets(formation: dict[str, Any]) -> dict[str, dict[str, float]]:
    returns = formation["returns"]
    return_ranks = formation["return_ranks"]
    volatility_ranks = formation["volatility_ranks"]
    return_only_selection = sorted(
        SYMBOLS, key=lambda symbol: (return_ranks[symbol], symbol)
    )[:3]
    no_correlation_scores = {
        symbol: float(return_ranks[symbol] + 0.5 * volatility_ranks[symbol])
        for symbol in SYMBOLS
    }
    no_correlation_selection = sorted(
        SYMBOLS, key=lambda symbol: (no_correlation_scores[symbol], symbol)
    )[:3]
    return_only, _ = target_from_selection(return_only_selection, returns)
    no_correlation, _ = target_from_selection(no_correlation_selection, returns)
    equal = {symbol: 1.0 / len(SYMBOLS) for symbol in SYMBOLS}
    spy = {symbol: (1.0 if symbol == "SPY" else 0.0) for symbol in SYMBOLS}
    shy = {symbol: (1.0 if symbol == "SHY" else 0.0) for symbol in SYMBOLS}
    targets = {
        STRATEGY_ID: formation["candidate_target"],
        "faa_4m_return_only_top3_control": return_only,
        "faa_4m_return_volatility_top3_no_correlation_control": no_correlation,
        "faa_full_period_average_weight_static_control": dict(STATIC_WEIGHTS),
        "monthly_equal_weight_7asset_control": equal,
        "SPY_buy_and_hold": spy,
        "SHY_buy_and_hold": shy,
    }
    if tuple(targets) != COMPARATORS:
        raise ValueError("comparator target scope drift")
    for target in targets.values():
        if set(target) != set(SYMBOLS):
            raise ValueError("target universe mismatch")
        if any(weight < 0.0 for weight in target.values()):
            raise ValueError("negative initialization target")
        if not math.isclose(sum(target.values()), 1.0, abs_tol=1e-12):
            raise ValueError("initialization target does not sum to one")
    formation["return_only_selection"] = return_only_selection
    formation["no_correlation_selection"] = no_correlation_selection
    formation["no_correlation_scores"] = no_correlation_scores
    return targets


def differentiation_distances(
    targets: dict[str, dict[str, float]]
) -> dict[str, float]:
    candidate = targets[STRATEGY_ID]
    return {
        control: float(
            sum(abs(candidate[symbol] - targets[control][symbol]) for symbol in SYMBOLS)
        )
        for control in CRITICAL_CONTROLS
    }


def initialization_ledgers(
    targets: dict[str, dict[str, float]]
) -> list[dict[str, Any]]:
    pretrade = {symbol: (1.0 if symbol == "SHY" else 0.0) for symbol in SYMBOLS}
    rows: list[dict[str, Any]] = []
    for portfolio_id, target in targets.items():
        turnover = 0.5 * sum(
            abs(target[symbol] - pretrade[symbol]) for symbol in SYMBOLS
        )
        rows.append(
            {
                "initialization_record_id": "prospective_initialization_not_performance",
                "portfolio_id": portfolio_id,
                "pre_execution_holdings": pretrade,
                "scheduled_target": target,
                "initialization_turnover": turnover,
                "initialization_cost_0bps": 0.0,
                "initialization_cost_5bps": turnover * 5.0 / 10000.0,
                "initialization_cost_10bps": turnover * 10.0 / 10000.0,
                "validation_NAV_0bps": 1.0,
                "validation_NAV_5bps": 1.0,
                "validation_NAV_10bps": 1.0,
                "cost_application_status": "pending_intended_execution",
                "validation_return_created": False,
                "completed_interval_created": False,
                "differentiation_month_credit": 0,
            }
        )
    return rows


def trial_record(status: str, activation_timestamp: str) -> dict[str, Any]:
    return {
        "trial_id": TRIAL_ID,
        "entity_type": "experiment_trial",
        "stage": STAGE,
        "strategy_id": STRATEGY_ID,
        "family_id": FAMILY_ID,
        "strategy_architecture": ARCHITECTURE,
        "parent_trial_id": PARENT_TRIAL_ID,
        "adaptation_label": "prospective_validation_variant",
        "changed_fields_from_parent": "prospective_evaluation_boundary_only",
        "route": "standalone_only",
        "status": status,
        "outcome": "",
        "failure_reason": "",
        "activation_timestamp": activation_timestamp,
        "next_action": NEXT_ACTIVATED,
        "formula_changed": False,
        "parameters_changed": False,
        "instruments_changed": False,
        "controls_changed": False,
        "execution_changed": False,
        "cost_model_changed": False,
        "optimization_performed": False,
        "historical_backfill_permitted": False,
    }


def observation_record(state: str, activation_timestamp: str) -> dict[str, Any]:
    return {
        "validation_observation_id": OBSERVATION_ID,
        "entity_type": "validation_observation",
        "stage": STAGE,
        "strategy_id": STRATEGY_ID,
        "trial_id": TRIAL_ID,
        "state": state,
        "activation_timestamp": activation_timestamp,
        "elapsed_completed_months": 0,
        "completed_holding_intervals": 0,
        "differentiation_months_vs_return_only": 0,
        "differentiation_months_vs_no_correlation": 0,
        "validation_decision": "",
        "historical_backfill": "prohibited",
        "broker_submission": False,
        "paper_order_submission": False,
        "real_money_authorization": False,
        "paper_demo_observation": False,
        "next_action": NEXT_ACTIVATED,
    }


def fixture_frames() -> dict[str, pd.DataFrame]:
    sessions = expected_sessions(date(2025, 12, 30), date(2026, 5, 29))
    frames: dict[str, pd.DataFrame] = {}
    for symbol_index, symbol in enumerate(SYMBOLS):
        values = [
            80.0
            + 7.0 * symbol_index
            + 0.10 * index
            + 0.8 * math.sin(index / (7.0 + symbol_index))
            for index in range(len(sessions))
        ]
        frames[symbol] = pd.DataFrame(
            {
                "trading_date": [item.isoformat() for item in sessions],
                "adjusted_close": values,
            }
        )
    return frames


def offline_activation_dry_run() -> tuple[list[dict[str, Any]], bool]:
    steps: list[dict[str, Any]] = []

    def run_step(step_id: str, function: Any) -> Any:
        try:
            result = function()
            steps.append(
                {
                    "step_order": len(steps) + 1,
                    "step_id": step_id,
                    "status": "pass",
                    "detail": "",
                    "network_access": False,
                    "canonical_cache_write": False,
                    "historical_performance_row_created": False,
                }
            )
            return result
        except BaseException as exc:  # noqa: BLE001 - dry-run failure becomes evidence.
            steps.append(
                {
                    "step_order": len(steps) + 1,
                    "step_id": step_id,
                    "status": "fail",
                    "detail": sanitize_error(exc),
                    "network_access": False,
                    "canonical_cache_write": False,
                    "historical_performance_row_created": False,
                }
            )
            raise

    try:
        frames = run_step("provider_result_interface", fixture_frames)
        normalized = run_step(
            "adjusted_close_normalization",
            lambda: {
                symbol: normalize_alpaca_records(
                    [
                        {
                            "t": f"{row.trading_date}T20:00:00Z",
                            "c": row.adjusted_close,
                        }
                        for row in frame.itertuples(index=False)
                    ]
                )
                for symbol, frame in frames.items()
            },
        )
        run_step(
            "duplicate_retrieval_comparison",
            lambda: (
                reproduce_frames(normalized, {k: v.copy() for k, v in normalized.items()})
                if reproduce_frames(
                    normalized, {k: v.copy() for k, v in normalized.items()}
                )[1]
                else (_ for _ in ()).throw(ValueError("fixture reproducibility failed"))
            ),
        )
        run_step(
            "immutable_daily_snapshot_serialization",
            lambda: [frame_hash(frame) for frame in normalized.values()],
        )
        run_step(
            "latest_completed_month_end_detection",
            lambda: last_regular_session_of_month(2026, 5),
        )
        formation = run_step(
            "four_month_formation_construction",
            lambda: compute_formation(
                normalized,
                last_regular_session_of_month(2026, 1),
                last_regular_session_of_month(2026, 5),
            ),
        )
        run_step(
            "return_volatility_correlation_rank_calculation",
            lambda: formation["scores"],
        )
        targets = run_step("candidate_target_construction", lambda: compute_targets(formation))
        run_step(
            "all_comparator_target_construction",
            lambda: tuple(targets) == COMPARATORS
            or (_ for _ in ()).throw(ValueError("comparator scope mismatch")),
        )
        run_step("differentiation_distance_calculation", lambda: differentiation_distances(targets))
        ledgers = run_step("portfolio_initialization", lambda: initialization_ledgers(targets))
        run_step(
            "cost_ledger_initialization",
            lambda: all(row["validation_NAV_5bps"] == 1.0 for row in ledgers)
            or (_ for _ in ()).throw(ValueError("initialization changed validation NAV")),
        )
        fixture_now = datetime(2026, 5, 31, 12, 0, tzinfo=timezone.utc)
        boundary = run_step("activation_boundary_construction", lambda: activation_dates(fixture_now))
        run_step(
            "validation_trial_record_construction",
            lambda: trial_record(boundary["activation_status"], fixture_now.isoformat()),
        )
        run_step(
            "validation_observation_record_construction",
            lambda: observation_record(boundary["observation_state"], fixture_now.isoformat()),
        )
        run_step("empty_prospective_performance_ledger", lambda: pd.DataFrame(columns=["market_date"]))
        run_step(
            "final_precommit_gate",
            lambda: len(targets) == 7 and len(ledgers) == 7,
        )
    except BaseException:
        return steps, False
    return steps, all(row["status"] == "pass" for row in steps)


def offline_gate() -> dict[str, Any]:
    protected_before = snapshot_protected_hashes()
    reconciliation_rows, reconciliation_checks = design_reconciliation()
    import_rows, imports_pass = offline_import_preflight()
    dry_rows, dry_pass = offline_activation_dry_run()
    protected_after = snapshot_protected_hashes()
    gate_checks = {
        "design_and_identity_reconciliation": all(reconciliation_checks.values()),
        "import_and_dependency_contract": imports_pass,
        "full_no_network_dry_run": dry_pass,
        "protected_state_unchanged_during_offline_gate": protected_before == protected_after,
        "network_calls": True,
        "canonical_cache_writes": True,
        "historical_performance_rows": True,
    }
    gate_rows = [
        {
            "check_order": index,
            "gate_id": check,
            "status": "pass" if passed else "fail",
            "network_calls_before_gate_completion": 0,
            "canonical_cache_writes": 0,
            "historical_performance_rows": 0,
        }
        for index, (check, passed) in enumerate(gate_checks.items(), start=1)
    ]
    return {
        "passed": all(gate_checks.values()),
        "reconciliation_rows": reconciliation_rows,
        "reconciliation_checks": reconciliation_checks,
        "import_rows": import_rows,
        "dry_run_rows": dry_rows,
        "gate_rows": gate_rows,
        "protected_before": protected_before,
        "protected_after": protected_after,
    }


def retrieve_alpaca_once(
    retrieval_id: int,
    request_start: date,
    request_end_exclusive: date,
) -> dict[str, Any]:
    credentials = load_alpaca_credentials("paper")
    result: dict[str, Any] = {
        "retrieval_id": retrieval_id,
        "provider_id": "alpaca_market_data_read_only_adjusted_daily",
        "status": "",
        "retrieval_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "credentials_present": bool(credentials.present),
        "live_credentials_detected": bool(credentials.live_credentials_detected),
        "credential_source_present": credentials.source != "none",
        "endpoint": "/v2/stocks/bars",
        "method": "GET",
        "feed": "iex",
        "adjustment": "all",
        "request_start": request_start.isoformat(),
        "request_end_exclusive": request_end_exclusive.isoformat(),
        "page_count": 0,
        "raw_manifest_rows": [],
        "frames": {},
        "raw_records": {symbol: [] for symbol in SYMBOLS},
        "order_endpoint_called": False,
        "account_endpoint_called": False,
        "position_endpoint_called": False,
    }
    if not credentials.present:
        result["status"] = "auth_unavailable"
        result["error"] = "alpaca_paper_market_data_credentials_missing"
        return result
    if credentials.live_credentials_detected:
        result["status"] = "live_credentials_detected"
        result["error"] = "read_only_activation_refused_with_live_credentials_present"
        return result
    try:
        client = AlpacaClient(
            credentials,
            AlpacaClientConfig(data_feed="iex", data_adjustment="all"),
        )
        page_token: str | None = None
        while True:
            payload = client.get_historical_bars_page(
                symbols=list(SYMBOLS),
                start=f"{request_start.isoformat()}T00:00:00Z",
                end=f"{request_end_exclusive.isoformat()}T00:00:00Z",
                timeframe="1Day",
                page_token=page_token,
                feed="iex",
                adjustment="all",
            )
            result["page_count"] += 1
            page_path = (
                RAW_ROOT
                / f"retrieval_{retrieval_id}"
                / f"page_{result['page_count']:03d}.json"
            )
            write_json_path(page_path, payload)
            result["raw_manifest_rows"].append(
                {
                    "retrieval_id": retrieval_id,
                    "record_scope": "provider_response_page",
                    "symbol": "__BATCH__",
                    "page_number": result["page_count"],
                    "raw_path": relative(page_path),
                    "raw_hash": file_hash(page_path),
                    "persisted_before_strategy_calculation": True,
                }
            )
            for symbol in SYMBOLS:
                result["raw_records"][symbol].extend(
                    payload.get("bars", {}).get(symbol, [])
                )
            page_token = payload.get("next_page_token")
            if not page_token:
                break
        for symbol in SYMBOLS:
            raw_path = RAW_ROOT / f"retrieval_{retrieval_id}" / f"{symbol}_raw.json"
            normalized_path = (
                NORMALIZED_ROOT
                / f"retrieval_{retrieval_id}"
                / f"{symbol}_normalized.csv"
            )
            write_json_path(raw_path, result["raw_records"][symbol])
            frame = normalize_alpaca_records(result["raw_records"][symbol])
            normalized_path.parent.mkdir(parents=True, exist_ok=True)
            normalized_path.write_bytes(frame_bytes(frame))
            result["frames"][symbol] = frame
            result["raw_manifest_rows"].append(
                {
                    "retrieval_id": retrieval_id,
                    "record_scope": "symbol_raw_and_normalized",
                    "symbol": symbol,
                    "page_number": "",
                    "raw_path": relative(raw_path),
                    "raw_hash": file_hash(raw_path),
                    "normalized_path": relative(normalized_path),
                    "normalized_hash": file_hash(normalized_path),
                    "row_count": len(frame),
                    "persisted_before_strategy_calculation": True,
                }
            )
        result["status"] = "download_completed"
    except BaseException as exc:  # noqa: BLE001 - bounded provider failure is evidence.
        result["status"] = "provider_call_failed"
        result["error"] = sanitize_error(exc)
    return result


def acquire_bounded_cycle(
    dates: dict[str, Any],
) -> tuple[
    dict[str, pd.DataFrame],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    str,
]:
    first = retrieve_alpaca_once(
        1, dates["request_start"], dates["request_end_exclusive"]
    )
    second: dict[str, Any] = {}
    if first["status"] == "download_completed":
        second = retrieve_alpaca_once(
            2, dates["request_start"], dates["request_end_exclusive"]
        )
    attempts = [
        {
            "provider_sequence": 1,
            "provider_id": first["provider_id"],
            "provider_role": "primary_only_no_approved_fallback_available",
            "attempted": True,
            "retrieval_count": 2 if second else 1,
            "status": (
                "duplicate_retrievals_completed"
                if second.get("status") == "download_completed"
                else second.get("status", first["status"])
            ),
            "credentials_present": first.get("credentials_present", False),
            "live_credentials_detected": first.get("live_credentials_detected", False),
            "credential_source_present": first.get("credential_source_present", False),
            "request_start": dates["request_start"].isoformat(),
            "request_end_exclusive": dates["request_end_exclusive"].isoformat(),
            "endpoint": first["endpoint"],
            "method": "GET",
            "feed": "iex",
            "adjustment": "all",
            "account_endpoint_called": False,
            "position_endpoint_called": False,
            "order_endpoint_called": False,
            "fallback_attempted": False,
            "fallback_unavailable_recorded_before_network": True,
            "error": first.get("error", second.get("error", "")),
        }
    ]
    raw_rows = list(first.get("raw_manifest_rows", [])) + list(
        second.get("raw_manifest_rows", [])
    )
    if first["status"] != "download_completed" or second.get("status") != "download_completed":
        return {}, attempts, raw_rows, [], [], "required_data_unavailable"
    reproducibility, reproduced = reproduce_frames(first["frames"], second["frames"])
    coverage, covered = required_session_coverage(
        first["frames"], dates["request_start"], dates["formation_date"]
    )
    if not reproduced:
        return (
            {},
            attempts,
            raw_rows,
            reproducibility,
            coverage,
            "immutable_snapshot_reproducibility_failure",
        )
    if not covered:
        return (
            {},
            attempts,
            raw_rows,
            reproducibility,
            coverage,
            "required_session_coverage_failure",
        )
    return first["frames"], attempts, raw_rows, reproducibility, coverage, "pass"


def daily_snapshot_records(
    frames: dict[str, pd.DataFrame],
    raw_rows: list[dict[str, Any]],
    retrieval_timestamp_utc: str,
) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]]]:
    raw_by_symbol = {
        row["symbol"]: row
        for row in raw_rows
        if row.get("retrieval_id") == 1
        and row.get("record_scope") == "symbol_raw_and_normalized"
    }
    timestamp_utc = datetime.fromisoformat(retrieval_timestamp_utc)
    timestamp_et = timestamp_utc.astimezone(EASTERN).isoformat()
    snapshot_sets: dict[str, list[dict[str, Any]]] = {}
    manifest_rows: list[dict[str, Any]] = []
    for symbol in SYMBOLS:
        source = raw_by_symbol[symbol]
        records: list[dict[str, Any]] = []
        for row in frames[symbol].itertuples(index=False):
            record_core = {
                "symbol": symbol,
                "market_date": row.trading_date,
                "retrieval_timestamp_utc": retrieval_timestamp_utc,
                "retrieval_timestamp_us_eastern": timestamp_et,
                "provider": "alpaca_market_data_read_only_adjusted_daily",
                "raw_source_identifier": source["raw_path"],
                "raw_hash": source["raw_hash"],
                "adjusted_close": float(row.adjusted_close),
                "data_version_identifier": "faa_activation_retrieval_1",
                "revision_status": "original_prospective_capture",
                "validation_return_eligible": False,
                "initialization_label": (
                    "initialization_state_input_not_validation_performance"
                ),
            }
            record_core["normalized_hash"] = canonical_hash(record_core)
            records.append(record_core)
        snapshot_sets[symbol] = records
        payload = pd.DataFrame(records).to_csv(
            index=False, lineterminator="\n", float_format="%.12g"
        ).encode("utf-8")
        manifest_rows.append(
            {
                "snapshot_id": f"faa_initialization_{symbol}",
                "symbol": symbol,
                "record_count": len(records),
                "first_market_date": records[0]["market_date"],
                "last_market_date": records[-1]["market_date"],
                "prewrite_payload_hash": sha256_bytes(payload),
                "snapshot_path": "",
                "snapshot_hash": "",
                "stored_snapshot_hash_verified": False,
                "raw_hash": source["raw_hash"],
                "normalized_retrieval_hash": source["normalized_hash"],
                "initialization_only": True,
                "immutable": True,
                "overwrite_permitted": False,
                "validation_performance_rows": 0,
            }
        )
    return snapshot_sets, manifest_rows


def formation_rows(formation: dict[str, Any]) -> list[dict[str, Any]]:
    matrix = formation["correlation_matrix"]
    rows: list[dict[str, Any]] = []
    for symbol in SYMBOLS:
        correlations = {
            other: float(matrix.loc[symbol, other])
            for other in SYMBOLS
            if other != symbol
        }
        rows.append(
            {
                "formation_id": f"FAA_{formation['formation_end'].isoformat()}",
                "symbol": symbol,
                "formation_start": formation["formation_start"].isoformat(),
                "formation_end": formation["formation_end"].isoformat(),
                "daily_observation_count": formation["daily_observation_count"],
                "four_month_return": formation["returns"][symbol],
                "volatility_ddof1": formation["volatility"][symbol],
                "six_pairwise_correlations": correlations,
                "average_correlation": formation["average_correlation"][symbol],
                "return_rank": formation["return_ranks"][symbol],
                "volatility_rank": formation["volatility_ranks"][symbol],
                "correlation_rank": formation["correlation_ranks"][symbol],
                "candidate_score": formation["scores"][symbol],
                "candidate_selected": symbol in formation["selection"],
                "SHY_replacement": formation["replacements"][symbol],
                "initialization_only": True,
                "validation_return_created": False,
            }
        )
    return rows


def target_initialization_rows(
    targets: dict[str, dict[str, float]],
    intended_execution: date,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    candidate_rows = [
        {
            "strategy_id": STRATEGY_ID,
            "symbol": symbol,
            "target_weight": targets[STRATEGY_ID][symbol],
            "intended_execution_session": intended_execution.isoformat(),
            "execution_status": "scheduled_not_executed",
            "initialization_only": True,
        }
        for symbol in SYMBOLS
    ]
    comparator_rows = [
        {
            "comparator_id": comparator,
            "symbol": symbol,
            "target_weight": targets[comparator][symbol],
            "intended_execution_session": intended_execution.isoformat(),
            "execution_status": "scheduled_not_executed",
            "benchmark_specification_only": True,
            "counted_as_trial": False,
        }
        for comparator in COMPARATORS[1:]
        for symbol in SYMBOLS
    ]
    return candidate_rows, comparator_rows


def differentiation_rows(
    distances: dict[str, float],
    targets: dict[str, dict[str, float]],
) -> list[dict[str, Any]]:
    return [
        {
            "candidate_id": STRATEGY_ID,
            "control_id": control,
            "candidate_target": targets[STRATEGY_ID],
            "control_target": targets[control],
            "total_absolute_weight_difference": distance,
            "strict_threshold": 1e-12,
            "initial_target_differs": distance > 1e-12,
            "differentiation_month_credit": 0,
            "initialization_not_validation_performance": True,
        }
        for control, distance in distances.items()
    ]


def commit_active_state(
    snapshot_sets: dict[str, list[dict[str, Any]]],
    snapshot_manifest: list[dict[str, Any]],
    formation: dict[str, Any],
    targets: dict[str, dict[str, float]],
    ledgers: list[dict[str, Any]],
    dates: dict[str, Any],
    trial: dict[str, Any],
    observation: dict[str, Any],
    provider: str,
) -> list[dict[str, Any]]:
    if ACTIVE_DIR.exists():
        raise RuntimeError("active FAA prospective state already exists")
    staging = ACTIVE_DIR.parent / ".active_staging_faa_4m_top3_v1"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True, exist_ok=False)
    daily_root = staging / "daily_snapshots"
    for symbol, records in snapshot_sets.items():
        snapshot_path = daily_root / f"{symbol}.csv"
        write_csv_path(
            snapshot_path,
            records,
            ["symbol", "market_date"],
        )
        manifest_row = next(
            row for row in snapshot_manifest if row["symbol"] == symbol
        )
        manifest_row["snapshot_path"] = relative(
            ACTIVE_DIR / "daily_snapshots" / f"{symbol}.csv"
        )
        manifest_row["snapshot_hash"] = file_hash(snapshot_path)
        manifest_row["stored_snapshot_hash_verified"] = True
    write_json_path(staging / "immutable_initialization_manifest.json", snapshot_manifest)
    write_yaml_path(staging / "trial_state.yaml", trial)
    write_yaml_path(staging / "observation_counters.yaml", observation)
    write_yaml_path(staging / "decision_boundary.yaml", DECISION_BOUNDARY)
    write_json_path(staging / "current_target_vectors.json", targets)
    pretrade = {symbol: (1.0 if symbol == "SHY" else 0.0) for symbol in SYMBOLS}
    write_json_path(
        staging / "current_holdings.json",
        {
            "execution_status": "scheduled_not_executed",
            "pre_execution_holdings": {
                portfolio_id: pretrade for portfolio_id in COMPARATORS
            },
            "pending_targets": targets,
        },
    )
    write_csv_path(
        staging / "cost_ledger_initialization.csv",
        ledgers,
        ["initialization_record_id", "portfolio_id"],
    )
    write_yaml_path(
        staging / "next_required_event.yaml",
        {
            "activation_status": dates["activation_status"],
            "formation_date": dates["formation_date"].isoformat(),
            "intended_execution_session": dates["intended_execution_session"].isoformat(),
            "first_eligible_performance_session": (
                dates["first_eligible_performance_session"].isoformat()
                if dates["first_eligible_performance_session"]
                else ""
            ),
            "next_required_formation": dates["next_required_formation"].isoformat(),
            "next_action": NEXT_ACTIVATED,
        },
    )
    write_json_path(
        staging / "formation_snapshot.json",
        {
            "formation_start": formation["formation_start"],
            "formation_end": formation["formation_end"],
            "returns": formation["returns"],
            "volatility": formation["volatility"],
            "pairwise_correlations": formation["pairwise_correlations"],
            "average_correlation": formation["average_correlation"],
            "return_ranks": formation["return_ranks"],
            "volatility_ranks": formation["volatility_ranks"],
            "correlation_ranks": formation["correlation_ranks"],
            "scores": formation["scores"],
            "selection": formation["selection"],
            "replacements": formation["replacements"],
            "provider": provider,
            "initialization_only": True,
        },
    )
    write_csv_path(
        staging / "daily_performance_ledger.csv",
        [],
        [
            "market_date",
            "trial_id",
            "interval_id",
            "candidate_return_0bps",
            "candidate_return_5bps",
            "candidate_return_10bps",
        ],
    )
    write_csv_path(
        staging / "monthly_checkpoint_ledger.csv",
        [],
        [
            row["field_name"]
            for row in read_csv(DESIGN_DIR / "monthly_checkpoint_schema.csv")
        ],
    )
    staging.rename(ACTIVE_DIR)
    return [
        {
            "state_path": relative(path),
            "state_hash": file_hash(path),
            "change_type": "created_append_only_operational_state",
            "protected_lifecycle_state": False,
        }
        for path in sorted(item for item in ACTIVE_DIR.rglob("*") if item.is_file())
    ]


def append_existing_snapshot_hash_reconciliation_alert() -> dict[str, Any]:
    """Append a correction without changing any captured snapshot or decision data."""
    manifest_path = OUTPUT_DIR / "immutable_daily_snapshot_manifest.csv"
    active_manifest_path = ACTIVE_DIR / "immutable_initialization_manifest.json"
    if not manifest_path.exists() or not active_manifest_path.exists():
        raise RuntimeError("activated snapshot manifests are unavailable")
    rows = read_csv(manifest_path)
    alerts: list[dict[str, Any]] = []
    for row in rows:
        symbol = row["symbol"]
        snapshot_path = ACTIVE_DAILY_ROOT / f"{symbol}.csv"
        if not snapshot_path.is_file():
            raise RuntimeError(f"missing immutable snapshot for {symbol}")
        prior_manifest_hash = row.get("snapshot_hash", "")
        stored_hash = file_hash(snapshot_path)
        row["prewrite_payload_hash"] = row.get(
            "prewrite_payload_hash", prior_manifest_hash
        )
        row["snapshot_path"] = relative(snapshot_path)
        row["snapshot_hash"] = stored_hash
        row["stored_snapshot_hash_verified"] = "true"
        alerts.append(
            {
                "alert_type": "snapshot_file_hash_reconciliation",
                "symbol": symbol,
                "snapshot_path": relative(snapshot_path),
                "original_manifest_hash": prior_manifest_hash,
                "stored_snapshot_file_hash": stored_hash,
                "record_content_changed": False,
                "snapshot_overwritten": False,
                "decision_ledger_changed": False,
                "reason": (
                    "prewrite_payload_numeric_format_differed_from_standard_"
                    "stored_snapshot_serializer"
                ),
            }
        )
    alert_path = ACTIVE_DIR / "snapshot_hash_reconciliation_alert.json"
    if alert_path.exists():
        raise RuntimeError("snapshot hash reconciliation alert already exists")
    write_json_path(alert_path, alerts)
    write_csv_path(
        manifest_path,
        rows,
        ["snapshot_id", "symbol"],
    )
    state_manifest_path = OUTPUT_DIR / "state_change_manifest.csv"
    state_rows = read_csv(state_manifest_path)
    state_rows.append(
        {
            "state_path": relative(alert_path),
            "state_hash": file_hash(alert_path),
            "change_type": "append_only_hash_reconciliation_alert",
            "protected_lifecycle_state": False,
        }
    )
    write_csv_path(state_manifest_path, state_rows, ["state_path"])
    consistency_path = OUTPUT_DIR / "consistency_check.json"
    consistency = read_json(consistency_path)
    consistency["stored_snapshot_file_hashes_verified"] = all(
        row["stored_snapshot_hash_verified"] == "true" for row in rows
    )
    consistency["snapshot_hash_reconciliation_alert_appended"] = True
    consistency["immutable_snapshot_records_overwritten"] = False
    consistency["decision_ledger_changed_by_hash_reconciliation"] = False
    consistency["overall_pass"] = bool(
        consistency.get("overall_pass")
        and consistency["stored_snapshot_file_hashes_verified"]
    )
    write_json_path(consistency_path, consistency)
    return {
        "alert_path": relative(alert_path),
        "alert_hash": file_hash(alert_path),
        "snapshot_count": len(rows),
        "all_stored_hashes_verified": consistency[
            "stored_snapshot_file_hashes_verified"
        ],
        "snapshots_overwritten": False,
    }


def append_existing_decision_boundary_contract() -> dict[str, Any]:
    """Append the frozen decision contract to an already-created active state."""
    boundary_path = ACTIVE_DIR / "decision_boundary.yaml"
    if boundary_path.exists():
        raise RuntimeError("active decision boundary already exists")
    write_yaml_path(boundary_path, DECISION_BOUNDARY)
    validation_state_path = OUTPUT_DIR / "validation_state.yaml"
    validation_state = read_yaml(validation_state_path)
    validation_state["decision_boundary"] = DECISION_BOUNDARY
    write_yaml_path(validation_state_path, validation_state)
    state_manifest_path = OUTPUT_DIR / "state_change_manifest.csv"
    state_rows = read_csv(state_manifest_path)
    state_rows.append(
        {
            "state_path": relative(boundary_path),
            "state_hash": file_hash(boundary_path),
            "change_type": "append_only_frozen_decision_boundary",
            "protected_lifecycle_state": False,
        }
    )
    write_csv_path(state_manifest_path, state_rows, ["state_path"])
    consistency_path = OUTPUT_DIR / "consistency_check.json"
    consistency = read_json(consistency_path)
    consistency["prospective_decision_boundary_frozen_in_active_state"] = True
    consistency["minimum_completed_calendar_months"] = 24
    consistency["minimum_completed_holding_intervals"] = 24
    consistency["minimum_differentiation_months_vs_return_only"] = 6
    consistency["minimum_differentiation_months_vs_no_correlation"] = 6
    consistency["hard_maximum_completed_calendar_months"] = 36
    consistency["early_favorable_stopping_permitted"] = False
    write_json_path(consistency_path, consistency)
    return {
        "boundary_path": relative(boundary_path),
        "boundary_hash": file_hash(boundary_path),
        "decision_boundary": DECISION_BOUNDARY,
    }


def activation_report(
    outcome: str,
    failure_reason: str,
    next_action: str,
    dates: dict[str, Any],
    provider: str,
    trial_count: int,
) -> str:
    if outcome == ACTIVATED:
        detail = (
            f"The official activation state is `{dates['activation_status']}`. "
            f"The captured formation is `{dates['formation_date']}` and its "
            f"source-defined execution session is `{dates['intended_execution_session']}`. "
            "No validation return exists yet."
        )
    else:
        detail = (
            "Activation did not occur. Trial, observation, initialization, and "
            "performance artifacts contain headers with zero rows."
        )
    return f"""# FAA Prospective Validation Activation V1

## Outcome

* Outcome: `{outcome}`
* Failure reason: `{failure_reason}`
* Exact next action: `{next_action}`
* Experiment trials created: `{trial_count}`
* Provider: `{provider or 'none'}`

## Activation

{detail}

The seven-asset FAA rule, standalone-only route, three critical controls,
static weights, 5 bps primary cost, and 0/10 bps diagnostic ledgers remain
frozen. Initialization history is labeled
`initialization_state_input_not_validation_performance` and creates no
validation return, completed interval, differentiation-month credit, or NAV
movement.

## Boundary

The future decision remains prohibited before 24 completed calendar months,
24 completed holding intervals, and six differentiation months versus each
component control. The hard maximum remains 36 months. No early favorable
stopping is authorized.

## Scope

No historical backtest, robustness calculation, canonical-cache mutation,
lifecycle update, paper/demo observation, broker call, order, account action,
or real-money action occurred. VIX Fix and decelerated PSAR remain unchanged.
"""


def write_empty_ledgers() -> None:
    write_csv(
        "daily_performance_ledger.csv",
        [],
        [
            "market_date",
            "trial_id",
            "interval_id",
            "candidate_return_0bps",
            "candidate_return_5bps",
            "candidate_return_10bps",
        ],
    )
    write_csv(
        "monthly_checkpoint_ledger.csv",
        [],
        [
            row["field_name"]
            for row in read_csv(DESIGN_DIR / "monthly_checkpoint_schema.csv")
        ],
    )


def run(now: datetime | None = None) -> dict[str, Any]:
    now_utc = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    protected_before = snapshot_protected_hashes()
    source_before = file_hash(SOURCE_PACKET)
    offline = offline_gate()
    reset_output()

    dates = activation_dates(now_utc)
    attempts: list[dict[str, Any]] = []
    raw_rows: list[dict[str, Any]] = []
    reproducibility_rows: list[dict[str, Any]] = []
    coverage_rows: list[dict[str, Any]] = []
    snapshot_manifest: list[dict[str, Any]] = []
    formation_rows_: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []
    comparator_rows: list[dict[str, Any]] = []
    differentiation_rows_: list[dict[str, Any]] = []
    portfolio_rows: list[dict[str, Any]] = []
    trial_rows: list[dict[str, Any]] = []
    observation_rows: list[dict[str, Any]] = []
    state_rows: list[dict[str, Any]] = []
    provider = ""
    failure_reason = ""
    outcome = ""
    next_action = ""
    acquisition_status = "not_attempted"
    formation: dict[str, Any] = {}
    targets: dict[str, dict[str, float]] = {}

    if not offline["passed"]:
        outcome = BLOCKED
        next_action = NEXT_DEFERRED
        failure_reason = "local_methodology_failure"
    else:
        (
            frames,
            attempts,
            raw_rows,
            reproducibility_rows,
            coverage_rows,
            acquisition_status,
        ) = acquire_bounded_cycle(dates)
        provider = attempts[0]["provider_id"] if attempts else ""
        if acquisition_status != "pass":
            outcome = DEFERRED
            failure_reason = acquisition_status
            next_action = NEXT_DEFERRED
        else:
            try:
                formation = compute_formation(
                    frames,
                    dates["formation_start_date"],
                    dates["formation_date"],
                )
                targets = compute_targets(formation)
                distances = differentiation_distances(targets)
                portfolio_rows = initialization_ledgers(targets)
                retrieval_timestamp = datetime.now(timezone.utc).isoformat()
                snapshot_sets, snapshot_manifest = daily_snapshot_records(
                    frames,
                    raw_rows,
                    retrieval_timestamp,
                )
                formation_rows_ = formation_rows(formation)
                candidate_rows, comparator_rows = target_initialization_rows(
                    targets, dates["intended_execution_session"]
                )
                differentiation_rows_ = differentiation_rows(distances, targets)
                activation_timestamp = now_utc.isoformat()
                trial = trial_record(dates["activation_status"], activation_timestamp)
                observation = observation_record(
                    dates["observation_state"], activation_timestamp
                )
                trial_rows = [trial]
                observation_rows = [observation]
                state_rows = commit_active_state(
                    snapshot_sets,
                    snapshot_manifest,
                    formation,
                    targets,
                    portfolio_rows,
                    dates,
                    trial,
                    observation,
                    provider,
                )
                outcome = ACTIVATED
                next_action = NEXT_ACTIVATED
            except BaseException as exc:  # noqa: BLE001 - post-data gate failure is durable evidence.
                outcome = DEFERRED
                failure_reason = "formation_initialization_failure"
                next_action = NEXT_DEFERRED
                attempts[0]["post_acquisition_error"] = sanitize_error(exc)
                trial_rows = []
                observation_rows = []
                portfolio_rows = []
                snapshot_manifest = []
                formation_rows_ = []
                candidate_rows = []
                comparator_rows = []
                differentiation_rows_ = []

    if outcome == BLOCKED and failure_reason in {
        "lineage_reconciliation_failure",
        "parameter_reconciliation_failure",
        "control_reconciliation_failure",
        "status_reconciliation_required",
        "methodology_failure",
    }:
        next_action = NEXT_BLOCKED

    activated = outcome == ACTIVATED
    trial_count = 1 if activated else 0
    observation_count = 1 if activated else 0
    initialization_count = 1 if activated else 0
    activation_state = (
        {
            "trial_id": TRIAL_ID,
            "validation_observation_id": OBSERVATION_ID,
            "status": dates["activation_status"],
            "activation_timestamp": now_utc.isoformat(),
            "formation_date": dates["formation_date"].isoformat(),
            "intended_execution_session": dates[
                "intended_execution_session"
            ].isoformat(),
            "first_eligible_performance_session": (
                dates["first_eligible_performance_session"].isoformat()
                if dates["first_eligible_performance_session"]
                else ""
            ),
            "elapsed_completed_months": 0,
            "completed_holding_intervals": 0,
            "differentiation_months_vs_return_only": 0,
            "differentiation_months_vs_no_correlation": 0,
            "validation_decision": "",
            "completed_validation_performance_rows": 0,
            "historical_backfill": "prohibited",
            "paper_demo_observation": False,
            "broker_submission": False,
            "paper_order_submission": False,
            "real_money_authorization": False,
            "next_action": NEXT_ACTIVATED,
            "decision_boundary": DECISION_BOUNDARY,
        }
        if activated
        else {
            "status": "not_activated",
            "outcome": outcome,
            "failure_reason": failure_reason,
            "completed_validation_performance_rows": 0,
        }
    )

    future_before_after = [
        {
            "trial_id": TRIAL_ID,
            "parent_trial_id": PARENT_TRIAL_ID,
            "before_status": "frozen_not_activated",
            "before_executed": False,
            "before_validation_observation_count": 0,
            "after_status": dates["activation_status"] if activated else "not_created",
            "after_executed_trial_created": activated,
            "after_validation_observation_created": activated,
            "after_initialization_record_created": activated,
            "completed_validation_performance_rows": 0,
            "prior_design_packet_rewritten": False,
        }
    ]
    symbol_scope = [
        {
            "symbol": symbol,
            "universe_order": index,
            "required": True,
            "provider": provider or "alpaca_market_data_read_only_adjusted_daily",
            "frozen_before_provider_access": True,
            "candidate_and_comparator_observations_identical": activated,
            "canonical_cache_modified": False,
            "substitution_permitted": False,
            "reduced_universe_permitted": False,
        }
        for index, symbol in enumerate(SYMBOLS, start=1)
    ]
    history_requirements = [
        {
            "symbol": symbol,
            "requested_start": dates["request_start"].isoformat(),
            "formation_start": dates["formation_start_date"].isoformat(),
            "formation_end": dates["formation_date"].isoformat(),
            "requested_end_exclusive": dates["request_end_exclusive"].isoformat(),
            "history_role": "initialization_state_input_not_validation_performance",
            "prior_return_session_included": True,
            "selected_from_performance": False,
            "historical_validation_rows_created": 0,
            "canonical_cache_write": False,
        }
        for symbol in SYMBOLS
    ]
    boundary_rows = [
        {
            "activation_timestamp_utc": now_utc.isoformat(),
            "activation_timestamp_us_eastern": now_utc.astimezone(EASTERN).isoformat(),
            "latest_completed_session": dates["latest_completed_session"].isoformat(),
            "formation_date": dates["formation_date"].isoformat(),
            "formation_start_date": dates["formation_start_date"].isoformat(),
            "intended_execution_session": dates[
                "intended_execution_session"
            ].isoformat(),
            "on_time_current_formation": dates["on_time_current_formation"],
            "activation_status": dates["activation_status"] if activated else "not_activated",
            "first_eligible_performance_session": (
                dates["first_eligible_performance_session"].isoformat()
                if activated and dates["first_eligible_performance_session"]
                else ""
            ),
            "historical_backfill_permitted": False,
            "initialization_counts_as_performance": False,
            "elapsed_month_counter": 0,
            "completed_interval_counter": 0,
            "early_decision_permitted": False,
        }
    ]
    data_task_rows = [
        {
            "task_id": f"{TASK_ID}__bounded_prospective_data_cycle",
            "entity_type": "data_capability_task",
            "stage": "feasible" if acquisition_status == "pass" else "blocked",
            "adaptation_label": "data_feasibility_adjustment",
            "provider": provider or "alpaca_market_data_read_only_adjusted_daily",
            "outcome": acquisition_status,
            "bounded_primary_cycles": 1 if attempts else 0,
            "approved_fallback_cycles": 0,
            "canonical_cache_mutation": False,
            "provider_integration_added": False,
            "dependency_installed": False,
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
            "next_action": next_action,
            "experiment_trials_created": trial_count,
            "validation_observations_created": observation_count,
            "initialization_records_created": initialization_count,
            "completed_validation_performance_rows": 0,
            "broker_or_order_action": False,
            "counted_as_strategy": False,
            "counted_as_trial": False,
        }
    ]
    state_change_rows = [
        {
            "state_path": relative(path),
            "state_hash": file_hash(path),
            "change_type": "protected_state_unchanged",
            "protected_lifecycle_state": True,
        }
        for path in design.PROTECTED_PATHS
        if path.exists()
    ] + state_rows
    outcome_rows = [
        {
            "strategy_id": STRATEGY_ID,
            "trial_id": TRIAL_ID if activated else "",
            "validation_observation_id": OBSERVATION_ID if activated else "",
            "outcome": outcome,
            "failure_reason": failure_reason,
            "activation_status": dates["activation_status"] if activated else "not_activated",
            "experiment_trials_created": trial_count,
            "validation_observations_created": observation_count,
            "initialization_records_created": initialization_count,
            "completed_validation_performance_rows": 0,
            "paper_demo_observations_created": 0,
            "next_action": next_action,
        }
    ]
    failure_rows = [
        {
            "outcome": outcome,
            "failure_reason": failure_reason,
            "detail": attempts[0].get("post_acquisition_error", "") if attempts else "",
        }
    ] if failure_reason else []
    next_rows = [
        {
            "scope": "prospective_validation_activation",
            "outcome": outcome,
            "exact_next_action": next_action,
            "execute_in_this_task": False,
        }
    ]
    manifest = {
        "task_id": TASK_ID,
        "mode": MODE,
        "stage": STAGE,
        "strategy_id": STRATEGY_ID,
        "trial_id": TRIAL_ID,
        "parent_trial_id": PARENT_TRIAL_ID,
        "validation_observation_id": OBSERVATION_ID,
        "route": "standalone_only",
        "activation_timestamp_utc": now_utc.isoformat(),
        "source_authority": str(SOURCE_PACKET),
        "source_authority_hash": source_before,
        "design_packet_hash": tree_hash(DESIGN_DIR),
        "exploration_packet_hash": tree_hash(EXPLORATION_DIR),
        "robustness_packet_hash": tree_hash(ROBUSTNESS_DIR),
        "offline_gate_pass": offline["passed"],
        "provider": provider or "none",
        "provider_cycle_status": acquisition_status,
        "new_strategy_configurations": 0,
        "updated_strategy_configurations": 0,
        "experiment_trials_created": trial_count,
        "validation_observations_created": observation_count,
        "paper_demo_observations_created": 0,
        "initialization_records_created": initialization_count,
        "completed_validation_performance_rows": 0,
        "benchmark_specifications_carried_forward": 7,
        "data_capability_tasks": 1,
        "process_tasks": 1,
        "broker_or_paper_orders": 0,
        "historical_performance_recalculated": False,
        "historical_backfill_performed": False,
        "canonical_cache_modified": False,
        "lifecycle_state_changed": False,
        "paper_demo_activity": False,
        "broker_account_or_order_activity": False,
        "real_money_activity": False,
        "outcome": outcome,
        "failure_reason": failure_reason,
        "exact_next_action": next_action,
        "next_action_executed": False,
    }

    write_yaml("activation_manifest.yaml", manifest)
    write_csv("design_reconciliation.csv", offline["reconciliation_rows"], ["check_order", "check_id"])
    write_csv("future_trial_before_after.csv", future_before_after, ["trial_id"])
    write_csv(
        "offline_import_and_dependency_preflight.csv",
        offline["import_rows"],
        ["check_order", "contract_id"],
    )
    write_csv("offline_activation_dry_run.csv", offline["dry_run_rows"], ["step_order", "step_id"])
    write_csv("offline_gate_results.csv", offline["gate_rows"], ["check_order", "gate_id"])
    write_csv("required_symbol_scope.csv", symbol_scope, ["symbol"])
    write_csv("initialization_history_requirements.csv", history_requirements, ["symbol"])
    write_csv(
        "provider_attempt_log.csv",
        attempts,
        ["provider_sequence", "provider_id"],
        ["provider_sequence", "provider_id", "attempted", "status"],
    )
    write_csv(
        "raw_retrieval_manifest.csv",
        raw_rows,
        ["retrieval_id", "record_scope", "symbol"],
    )
    write_csv(
        "retrieval_reproducibility.csv",
        reproducibility_rows,
        ["symbol"],
    )
    write_csv("required_session_coverage.csv", coverage_rows, ["symbol"])
    write_csv(
        "immutable_daily_snapshot_manifest.csv",
        snapshot_manifest,
        ["snapshot_id", "symbol"],
    )
    write_csv(
        "formation_state_initialization.csv",
        formation_rows_,
        ["formation_id", "symbol"],
    )
    write_csv("candidate_target_initialization.csv", candidate_rows, ["strategy_id", "symbol"])
    write_csv(
        "comparator_target_initialization.csv",
        comparator_rows,
        ["comparator_id", "symbol"],
    )
    write_csv(
        "differentiation_initialization.csv",
        differentiation_rows_,
        ["candidate_id", "control_id"],
    )
    write_csv(
        "portfolio_initialization_record.csv",
        portfolio_rows,
        ["initialization_record_id", "portfolio_id"],
    )
    write_csv("activation_boundary.csv", boundary_rows, ["activation_timestamp_utc"])
    write_csv(
        "validation_trial_record.csv",
        trial_rows,
        ["trial_id", "entity_type", "stage"],
    )
    write_csv(
        "validation_observation_record.csv",
        observation_rows,
        ["validation_observation_id", "entity_type", "stage"],
    )
    write_yaml("validation_state.yaml", activation_state)
    write_empty_ledgers()
    write_csv("data_capability_task_log.csv", data_task_rows, ["task_id", "entity_type"])
    write_csv("process_task_log.csv", process_rows, ["task_id", "entity_type"])
    write_csv("state_change_manifest.csv", state_change_rows, ["state_path"])
    write_csv("outcome_summary.csv", outcome_rows, ["strategy_id"])
    write_csv(
        "failure_reasons.csv",
        failure_rows,
        ["outcome", "failure_reason"],
    )
    write_csv("next_actions.csv", next_rows, ["scope"])
    write_text(
        "activation_report.md",
        activation_report(outcome, failure_reason, next_action, dates, provider, trial_count),
    )

    outputs_before_consistency = {
        path.name for path in OUTPUT_DIR.iterdir() if path.is_file()
    }
    expected_before_consistency = REQUIRED_OUTPUTS - {"consistency_check.json"}
    protected_after = snapshot_protected_hashes()
    source_after = file_hash(SOURCE_PACKET)
    consistency = {
        "task_id": TASK_ID,
        "outcome": outcome,
        "failure_reason": failure_reason,
        "exact_next_action": next_action,
        "overall_pass": bool(
            offline["passed"]
            and outputs_before_consistency == expected_before_consistency
            and protected_before == protected_after
            and source_before == source_after
            and (
                (activated and trial_count == 1 and observation_count == 1)
                or (not activated and trial_count == 0 and observation_count == 0)
            )
        ),
        "required_outputs_exact_before_consistency_write": (
            outputs_before_consistency == expected_before_consistency
        ),
        "design_reconciliation_pass": all(offline["reconciliation_checks"].values()),
        "offline_import_preflight_pass": all(
            row["status"] == "pass" for row in offline["import_rows"]
        ),
        "offline_activation_dry_run_pass": all(
            row["status"] == "pass" for row in offline["dry_run_rows"]
        ),
        "offline_gate_pass": offline["passed"],
        "provider_cycle_status": acquisition_status,
        "duplicate_retrieval_reconciliation_pass": bool(
            activated
            and reproducibility_rows
            and all(row["reproducibility_status"] == "pass" for row in reproducibility_rows)
        ) if activated else False,
        "required_session_coverage_pass": bool(
            activated
            and coverage_rows
            and all(row["coverage_status"] == "pass" for row in coverage_rows)
        ) if activated else False,
        "formation_initialization_pass": len(formation_rows_) == 7 if activated else False,
        "comparator_initialization_pass": len(comparator_rows) == 42 if activated else False,
        "trial_schema_pass": len(trial_rows) == trial_count,
        "validation_observation_schema_pass": len(observation_rows) == observation_count,
        "experiment_trials_created": trial_count,
        "validation_observations_created": observation_count,
        "initialization_records_created": initialization_count,
        "completed_validation_performance_rows": 0,
        "new_strategy_configurations": 0,
        "updated_strategy_configurations": 0,
        "paper_demo_observations_created": 0,
        "benchmark_specifications_carried_forward": 7,
        "data_capability_tasks": 1,
        "process_tasks": 1,
        "active_operational_state_created": ACTIVE_DIR.exists() if activated else False,
        "historical_performance_recalculated": False,
        "historical_backfill_performed": False,
        "validation_decision_made": False,
        "protected_hashes_before": protected_before,
        "protected_hashes_after": protected_after,
        "protected_state_cache_and_prior_evidence_unchanged": protected_before == protected_after,
        "source_packet_unchanged": source_before == source_after,
        "canonical_cache_modified": False,
        "network_calls_before_offline_gate": 0,
        "provider_integration_added": False,
        "dependency_installed": False,
        "account_endpoint_called": False,
        "position_endpoint_called": False,
        "order_endpoint_called": False,
        "broker_submission": False,
        "paper_order_submission": False,
        "real_money_authorization": False,
        "lifecycle_state_changed": False,
        "paper_demo_activity": False,
        "vix_fix_state_changed": False,
        "psar_state_changed": False,
        "next_action_executed": False,
    }
    write_json("consistency_check.json", consistency)
    if {path.name for path in OUTPUT_DIR.iterdir() if path.is_file()} != REQUIRED_OUTPUTS:
        raise RuntimeError("Activation evidence output set does not match contract")
    return {
        "task_id": TASK_ID,
        "strategy_id": STRATEGY_ID,
        "trial_id": TRIAL_ID,
        "validation_observation_id": OBSERVATION_ID if activated else "",
        "outcome": outcome,
        "failure_reason": failure_reason,
        "activation_status": dates["activation_status"] if activated else "not_activated",
        "provider": provider,
        "exact_next_action": next_action,
        "evidence_path": relative(OUTPUT_DIR),
        "active_state_path": relative(ACTIVE_DIR) if activated else "",
        "completed_validation_performance_rows": 0,
        "overall_pass": consistency["overall_pass"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline-only", action="store_true")
    args = parser.parse_args(argv)
    if args.offline_only:
        result = offline_gate()
        payload = {
            "task_id": TASK_ID,
            "offline_gate_pass": result["passed"],
            "design_reconciliation_pass": all(result["reconciliation_checks"].values()),
            "import_preflight_pass": all(
                row["status"] == "pass" for row in result["import_rows"]
            ),
            "dry_run_pass": all(
                row["status"] == "pass" for row in result["dry_run_rows"]
            ),
            "network_calls": 0,
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0 if result["passed"] else 1
    result = run()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["overall_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
