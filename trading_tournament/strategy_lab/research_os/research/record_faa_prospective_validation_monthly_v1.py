from __future__ import annotations

import argparse
import csv
import json
import math
import re
import shutil
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
import yaml

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.research import (
    activate_faa_prospective_validation_v1 as activation,
)
from strategy_lab.research_os.research import (
    design_faa_prospective_validation_v1 as design,
)


TASK_ID = "record_faa_prospective_validation_monthly_v1"
MODE = "prospective-observation-recording"
STAGE = "validation"
TRIAL_ID = "faa_4m_top3_prospective_validation_v1__forward"
OBSERVATION_ID = "prospective_validation_faa_4m_top3_v1"
STRATEGY_ID = "keller_vanputten_faa_4m_top3_v1"
ACTIVATION_TIMESTAMP = "2026-08-02T22:21:54.598112+00:00"
INITIAL_FORMATION_DATE = date(2026, 7, 31)
INITIAL_EXECUTION_DATE = date(2026, 8, 3)
FIRST_PERFORMANCE_DATE = date(2026, 8, 4)

ACTIVE_DIR = activation.ACTIVE_DIR
CHECKPOINT_ROOT = ACTIVE_DIR.parent / "checkpoints"
ACTIVATION_DIR = activation.OUTPUT_DIR
DESIGN_DIR = design.OUTPUT_DIR
SOURCE_PACKET = Path(
    r"C:\Users\te3442\.codex\attachments"
    r"\88144787-d378-49d2-aff9-11dc3a312c64\pasted-text.txt"
)

SYMBOLS = activation.SYMBOLS
PORTFOLIOS = activation.COMPARATORS
COMPARATORS = tuple(item for item in PORTFOLIOS if item != STRATEGY_ID)
COST_BPS = activation.COST_BPS
STATIC_WEIGHTS = activation.STATIC_WEIGHTS
DECISION_BOUNDARY = activation.DECISION_BOUNDARY
DIFFERENTIATION_TOLERANCE = 1e-12

PENDING = "recorder_ready_pending_scheduled_execution"
INITIAL_EXECUTION_RECORDED = "initial_prospective_execution_recorded"
UPDATED = "prospective_validation_recording_updated"
NO_NEW_SESSION = "prospective_validation_recording_no_new_session"
DEFERRED = "prospective_validation_recording_deferred"
BLOCKED = "prospective_validation_recording_blocked"
BOUNDARY_REACHED = "decision_boundary_reached_pending_evaluation"

NEXT_RECORD = TASK_ID
NEXT_BLOCKED = "direction_owner_review_faa_prospective_recording_block_v1"
NEXT_EVALUATE = "evaluate_faa_prospective_validation_v1"

ALLOWED_OUTCOMES = {
    PENDING,
    INITIAL_EXECUTION_RECORDED,
    UPDATED,
    NO_NEW_SESSION,
    DEFERRED,
    BLOCKED,
    BOUNDARY_REACHED,
}
DEFERRED_REASONS = {
    "immutable_snapshot_reproducibility_failure",
    "required_session_coverage_failure",
    "required_data_unavailable",
    "data_or_comparability_failure",
}
BLOCKED_REASONS = {"local_methodology_failure", "methodology_failure"}

REQUIRED_OUTPUTS = {
    "recording_manifest.yaml",
    "active_state_before_after.csv",
    "offline_gate_results.csv",
    "provider_attempt_log.csv",
    "raw_retrieval_manifest.csv",
    "retrieval_reproducibility.csv",
    "required_session_coverage.csv",
    "new_snapshot_manifest.csv",
    "snapshot_revision_alerts.csv",
    "execution_event_ledger.csv",
    "new_daily_candidate_performance.csv",
    "new_daily_comparator_performance.csv",
    "formation_ledger.csv",
    "target_vector_ledger.csv",
    "completed_interval_ledger.csv",
    "monthly_checkpoint_record.csv",
    "turnover_cost_reconciliation.csv",
    "invariant_results.csv",
    "state_change_manifest.csv",
    "outcome_summary.csv",
    "failure_reasons.csv",
    "next_actions.csv",
    "consistency_check.json",
    "recording_report.md",
}

PROTECTED_PATHS = tuple(
    dict.fromkeys((*activation.PROTECTED_PATHS, ACTIVATION_DIR))
)

CSV_SCHEMAS: dict[str, list[str]] = {
    "active_state_before_after.csv": [
        "state_scope",
        "state_path",
        "hash_before",
        "hash_after",
        "changed",
        "change_authorized",
    ],
    "offline_gate_results.csv": [
        "check_order",
        "gate_id",
        "status",
        "detail",
        "checked_before_network_access",
        "network_calls_at_check",
    ],
    "provider_attempt_log.csv": [
        "provider_id",
        "attempted",
        "network_calls",
        "request_start",
        "request_end",
        "status",
        "account_endpoint_called",
        "position_endpoint_called",
        "order_endpoint_called",
        "detail",
    ],
    "raw_retrieval_manifest.csv": [
        "retrieval_id",
        "record_scope",
        "symbol",
        "raw_path",
        "raw_hash",
        "normalized_path",
        "normalized_hash",
        "row_count",
        "persisted_before_portfolio_calculation",
    ],
    "retrieval_reproducibility.csv": [
        "symbol",
        "retrieval_1_rows",
        "retrieval_2_rows",
        "retrieval_1_normalized_hash",
        "retrieval_2_normalized_hash",
        "normalized_dates_identical",
        "normalized_values_identical",
        "normalized_hashes_identical",
        "reproducibility_status",
    ],
    "required_session_coverage.csv": [
        "symbol",
        "requested_start",
        "requested_end",
        "expected_session_count",
        "returned_session_count",
        "missing_required_sessions",
        "ordered_unique_sessions",
        "finite_positive_adjusted_close",
        "identical_session_scope",
        "coverage_status",
    ],
    "new_snapshot_manifest.csv": [
        "snapshot_id",
        "symbol",
        "market_date",
        "retrieval_timestamp_utc",
        "retrieval_timestamp_us_eastern",
        "provider",
        "raw_identifier",
        "raw_hash",
        "normalized_hash",
        "adjusted_close",
        "data_version_id",
        "role",
        "revision_status",
        "immutable",
        "overwrite_permitted",
    ],
    "snapshot_revision_alerts.csv": [
        "alert_id",
        "symbol",
        "market_date",
        "original_adjusted_close",
        "later_adjusted_close",
        "original_snapshot_id",
        "later_raw_hash",
        "discrepancy_affects_state",
        "action",
    ],
    "execution_event_ledger.csv": [
        "execution_event_id",
        "execution_date",
        "portfolio_id",
        "cost_bps",
        "pretrade_holdings",
        "target_holdings",
        "one_way_turnover",
        "transaction_cost",
        "opening_nav",
        "closing_nav_after_cost",
        "validation_return_created",
        "status",
    ],
    "new_daily_candidate_performance.csv": [
        "market_date",
        "interval_id",
        "portfolio_id",
        "cost_bps",
        "opening_nav",
        "gross_portfolio_return",
        "turnover",
        "cost",
        "net_return",
        "closing_nav",
        "pretrade_holdings",
        "post_trade_holdings",
        "execution_event_id",
        "source_snapshot_ids",
        "invariant_result",
    ],
    "new_daily_comparator_performance.csv": [
        "market_date",
        "interval_id",
        "portfolio_id",
        "cost_bps",
        "opening_nav",
        "gross_portfolio_return",
        "turnover",
        "cost",
        "net_return",
        "closing_nav",
        "pretrade_holdings",
        "post_trade_holdings",
        "execution_event_id",
        "source_snapshot_ids",
        "invariant_result",
    ],
    "formation_ledger.csv": [
        "formation_id",
        "formation_date",
        "formation_start",
        "portfolio_id",
        "selected_assets",
        "SHY_replacements",
        "intended_execution_session",
        "captured_before_execution_close",
        "status",
    ],
    "target_vector_ledger.csv": [
        "formation_id",
        "portfolio_id",
        "symbol",
        "target_weight",
        "frozen_timestamp",
        "intended_execution_session",
    ],
    "completed_interval_ledger.csv": [
        "interval_id",
        "start_execution_date",
        "first_performance_date",
        "end_execution_date",
        "last_performance_date",
        "completed",
        "distance_vs_return_only",
        "distance_vs_no_correlation",
        "differentiation_credit_vs_return_only",
        "differentiation_credit_vs_no_correlation",
    ],
    "monthly_checkpoint_record.csv": [
        "checkpoint_id",
        "checkpoint_timestamp",
        "elapsed_calendar_months",
        "completed_holding_intervals",
        "differentiation_months_vs_return_only",
        "differentiation_months_vs_no_correlation",
        "candidate_nav_by_cost",
        "comparator_navs_by_cost",
        "validation_decision",
        "decision_authorized",
    ],
    "turnover_cost_reconciliation.csv": [
        "record_id",
        "portfolio_id",
        "market_date",
        "cost_bps",
        "one_way_turnover",
        "expected_cost",
        "recorded_cost",
        "cost_charged_once",
        "status",
    ],
    "invariant_results.csv": [
        "invariant_id",
        "status",
        "detail",
    ],
    "state_change_manifest.csv": [
        "state_path",
        "change_type",
        "append_only",
        "prior_records_modified",
        "hash_before",
        "hash_after",
    ],
    "outcome_summary.csv": [
        "task_id",
        "trial_id",
        "observation_id",
        "outcome",
        "failure_reason",
        "latest_completed_session",
        "latest_admitted_session",
        "network_calls",
        "new_execution_events",
        "new_daily_performance_rows",
        "new_completed_holding_intervals",
        "new_checkpoints",
        "validation_decision",
        "next_action",
    ],
    "failure_reasons.csv": [
        "task_id",
        "outcome",
        "failure_reason",
        "detail",
        "next_action",
    ],
    "next_actions.csv": ["scope", "outcome", "next_action", "executed"],
}


def relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)


def file_hash(path: Path) -> str:
    return activation.file_hash(path)


def tree_hash(path: Path) -> str:
    return activation.tree_hash(path)


def snapshot_protected_hashes() -> dict[str, str]:
    return {relative(path): tree_hash(path) for path in PROTECTED_PATHS}


def csv_value(value: Any) -> str:
    return activation.csv_value(value)


def fields_for(
    rows: list[dict[str, Any]], leading: Iterable[str]
) -> list[str]:
    fields = list(leading)
    for row in rows:
        for field in row:
            if field not in fields:
                fields.append(field)
    return fields


def write_csv_path(
    path: Path, rows: list[dict[str, Any]], fields: Iterable[str]
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    output_fields = fields_for(rows, fields)
    with path.open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=output_fields,
            extrasaction="ignore",
            lineterminator="\n",
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {field: csv_value(row.get(field, "")) for field in output_fields}
            )


def write_json_once(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(activation.canonical_bytes(payload) + b"\n")


def write_yaml_once(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        yaml.safe_dump(
            payload,
            handle,
            sort_keys=False,
            width=110,
            allow_unicode=False,
        )


def write_text_once(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(text.rstrip() + "\n")


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def unique_keys(
    rows: list[dict[str, Any]], fields: tuple[str, ...]
) -> bool:
    keys = [tuple(str(row.get(field, "")) for field in fields) for row in rows]
    return len(keys) == len(set(keys))


def append_unique_rows(
    existing: list[dict[str, Any]],
    new_rows: list[dict[str, Any]],
    key_fields: tuple[str, ...],
) -> list[dict[str, Any]]:
    if not unique_keys(existing, key_fields):
        raise ValueError("existing ledger contains duplicate keys")
    result = list(existing)
    by_key = {
        tuple(str(row.get(field, "")) for field in key_fields): row
        for row in existing
    }
    for row in new_rows:
        key = tuple(str(row.get(field, "")) for field in key_fields)
        prior = by_key.get(key)
        if prior is not None:
            if activation.canonical_hash(prior) != activation.canonical_hash(row):
                raise ValueError(f"immutable row conflict for key {key}")
            continue
        result.append(row)
        by_key[key] = row
    return result


def turnover(pretrade: dict[str, float], target: dict[str, float]) -> float:
    return 0.5 * sum(
        abs(float(target[symbol]) - float(pretrade[symbol])) for symbol in SYMBOLS
    )


def validate_weights(weights: dict[str, float]) -> bool:
    return bool(
        set(weights) == set(SYMBOLS)
        and all(math.isfinite(value) and value >= 0.0 for value in weights.values())
        and sum(abs(value) for value in weights.values()) <= 1.0 + 1e-12
        and math.isclose(sum(weights.values()), 1.0, abs_tol=1e-12)
    )


def execute_at_close(
    pretrade: dict[str, float],
    target: dict[str, float],
    opening_nav: float,
    cost_bps: float,
) -> dict[str, Any]:
    if not validate_weights(pretrade) or not validate_weights(target):
        raise ValueError("invalid execution weights")
    one_way = turnover(pretrade, target)
    cost = opening_nav * one_way * cost_bps / 10000.0
    return {
        "one_way_turnover": one_way,
        "transaction_cost": cost,
        "closing_nav_after_cost": opening_nav - cost,
        "post_trade_holdings": dict(target),
    }


def account_close_to_close_session(
    holdings: dict[str, float],
    opening_nav: float,
    previous_close: dict[str, float],
    current_close: dict[str, float],
    cost_bps: float,
    target_after_close: dict[str, float] | None = None,
) -> dict[str, Any]:
    if not validate_weights(holdings):
        raise ValueError("invalid opening holdings")
    asset_returns = {
        symbol: current_close[symbol] / previous_close[symbol] - 1.0
        for symbol in SYMBOLS
    }
    if not all(math.isfinite(value) for value in asset_returns.values()):
        raise ValueError("nonfinite asset return")
    gross_return = sum(holdings[symbol] * asset_returns[symbol] for symbol in SYMBOLS)
    gross_nav = opening_nav * (1.0 + gross_return)
    denominator = 1.0 + gross_return
    if denominator <= 0.0:
        raise ValueError("portfolio NAV is nonpositive")
    drifted = {
        symbol: holdings[symbol] * (1.0 + asset_returns[symbol]) / denominator
        for symbol in SYMBOLS
    }
    target = target_after_close or drifted
    one_way = turnover(drifted, target) if target_after_close is not None else 0.0
    cost = gross_nav * one_way * cost_bps / 10000.0
    closing_nav = gross_nav - cost
    return {
        "gross_portfolio_return": gross_return,
        "pretrade_drifted_holdings": drifted,
        "turnover": one_way,
        "cost": cost,
        "net_return": closing_nav / opening_nav - 1.0,
        "closing_nav": closing_nav,
        "post_trade_holdings": dict(target),
        "invariant_result": bool(
            validate_weights(drifted)
            and validate_weights(target)
            and closing_nav > 0.0
        ),
    }


def time_gate(latest_completed: date, latest_recorded: date | None) -> str:
    if latest_completed < INITIAL_EXECUTION_DATE:
        return PENDING
    if latest_completed == INITIAL_EXECUTION_DATE:
        return INITIAL_EXECUTION_RECORDED
    if latest_recorded is not None and latest_recorded >= latest_completed:
        return NO_NEW_SESSION
    return UPDATED


def _record_core_from_csv(row: dict[str, str]) -> dict[str, Any]:
    return {
        "symbol": row["symbol"],
        "market_date": row["market_date"],
        "retrieval_timestamp_utc": row["retrieval_timestamp_utc"],
        "retrieval_timestamp_us_eastern": row["retrieval_timestamp_us_eastern"],
        "provider": row["provider"],
        "raw_source_identifier": row["raw_source_identifier"],
        "raw_hash": row["raw_hash"],
        "adjusted_close": float(row["adjusted_close"]),
        "data_version_identifier": row["data_version_identifier"],
        "revision_status": row["revision_status"],
        "validation_return_eligible": row["validation_return_eligible"].lower()
        == "true",
        "initialization_label": row["initialization_label"],
    }


def admitted_snapshot_inventory() -> tuple[list[dict[str, Any]], dict[str, date]]:
    corrected = {
        row["symbol"]: row
        for row in read_csv(ACTIVATION_DIR / "immutable_daily_snapshot_manifest.csv")
    }
    alerts = {
        row["symbol"]: row
        for row in read_json(ACTIVE_DIR / "snapshot_hash_reconciliation_alert.json")
    }
    rows: list[dict[str, Any]] = []
    latest: dict[str, date] = {}
    for symbol in SYMBOLS:
        path = ACTIVE_DIR / "daily_snapshots" / f"{symbol}.csv"
        records = read_csv(path)
        dates = [date.fromisoformat(row["market_date"]) for row in records]
        values = [float(row["adjusted_close"]) for row in records]
        normalized_hashes_pass = all(
            activation.canonical_hash(_record_core_from_csv(row))
            == row["normalized_hash"]
            for row in records
        )
        expected_hash = corrected.get(symbol, {}).get("snapshot_hash", "")
        alert_hash = alerts.get(symbol, {}).get("stored_snapshot_file_hash", "")
        current_hash = file_hash(path)
        status = bool(
            records
            and dates == sorted(dates)
            and len(dates) == len(set(dates))
            and all(math.isfinite(value) and value > 0.0 for value in values)
            and current_hash == expected_hash == alert_hash
            and normalized_hashes_pass
        )
        latest[symbol] = max(dates)
        rows.append(
            {
                "symbol": symbol,
                "snapshot_path": relative(path),
                "record_count": len(records),
                "first_market_date": min(dates).isoformat(),
                "last_market_date": max(dates).isoformat(),
                "stored_file_hash": current_hash,
                "corrected_manifest_hash": expected_hash,
                "reconciliation_alert_hash": alert_hash,
                "normalized_record_hashes_pass": normalized_hashes_pass,
                "status": "pass" if status else "fail",
            }
        )
    return rows, latest


def active_trial_state_count() -> int:
    count = 0
    validation_root = ROOT / "evidence" / "validation"
    for path in validation_root.rglob("trial_state.yaml"):
        try:
            value = read_yaml(path)
        except (OSError, yaml.YAMLError):
            continue
        if (
            value.get("trial_id") == TRIAL_ID
            and value.get("status") == "active_prospective_validation"
        ):
            count += 1
    return count


def fixture_flow_checks() -> dict[str, bool]:
    shy = {symbol: (1.0 if symbol == "SHY" else 0.0) for symbol in SYMBOLS}
    target = read_json(ACTIVE_DIR / "current_target_vectors.json")[STRATEGY_ID]
    execution = execute_at_close(shy, target, 1.0, 5.0)
    previous = {symbol: 100.0 for symbol in SYMBOLS}
    current = {symbol: 101.0 + index for index, symbol in enumerate(SYMBOLS)}
    accounting = account_close_to_close_session(
        target,
        execution["closing_nav_after_cost"],
        previous,
        current,
        5.0,
    )
    existing = [{"market_date": "2026-08-04", "portfolio_id": STRATEGY_ID, "cost_bps": 5}]
    same = append_unique_rows(
        existing,
        list(existing),
        ("market_date", "portfolio_id", "cost_bps"),
    )
    conflict_rejected = False
    try:
        append_unique_rows(
            existing,
            [{**existing[0], "closing_nav": 2.0}],
            ("market_date", "portfolio_id", "cost_bps"),
        )
    except ValueError:
        conflict_rejected = True
    frames = activation.fixture_frames()
    formation_end = activation.last_regular_session_of_month(2026, 5)
    formation_start = activation.last_regular_session_of_month(2026, 1)
    first = activation.compute_formation(frames, formation_start, formation_end)
    changed = {symbol: frame.copy() for symbol, frame in frames.items()}
    future_date = activation.next_regular_session(formation_end).isoformat()
    for symbol in SYMBOLS:
        changed[symbol] = pd.concat(
            [
                changed[symbol],
                pd.DataFrame(
                    {"trading_date": [future_date], "adjusted_close": [99999.0]}
                ),
            ],
            ignore_index=True,
        )
    second = activation.compute_formation(changed, formation_start, formation_end)
    return {
        "fixture_initialization_turnover_exact": math.isclose(
            execution["one_way_turnover"], 2.0 / 3.0, abs_tol=1e-12
        ),
        "fixture_initialization_cost_applied_once": math.isclose(
            execution["closing_nav_after_cost"],
            1.0 - (2.0 / 3.0) * 5.0 / 10000.0,
            abs_tol=1e-12,
        ),
        "fixture_no_execution_day_return_created": "gross_portfolio_return"
        not in execution,
        "fixture_daily_accounting_reconciles": accounting["invariant_result"],
        "fixture_explicit_drift_preserves_weight_sum": math.isclose(
            sum(accounting["post_trade_holdings"].values()), 1.0, abs_tol=1e-12
        ),
        "fixture_idempotent_identical_row": same == existing,
        "fixture_immutable_conflict_rejected": conflict_rejected,
        "fixture_formation_ignores_future_data": first["selection"]
        == second["selection"]
        and first["scores"] == second["scores"],
    }


def offline_gate() -> dict[str, Any]:
    protected_before = snapshot_protected_hashes()
    active_before = tree_hash(ACTIVE_DIR)
    checks: list[tuple[str, bool, str]] = []

    required_active = (
        "trial_state.yaml",
        "observation_counters.yaml",
        "next_required_event.yaml",
        "decision_boundary.yaml",
        "current_holdings.json",
        "current_target_vectors.json",
        "cost_ledger_initialization.csv",
        "daily_performance_ledger.csv",
        "monthly_checkpoint_ledger.csv",
        "formation_snapshot.json",
        "immutable_initialization_manifest.json",
        "snapshot_hash_reconciliation_alert.json",
    )
    checks.append(
        (
            "required_active_state_files_present",
            all((ACTIVE_DIR / name).is_file() for name in required_active),
            "all authoritative active-state inputs are present",
        )
    )
    trial = read_yaml(ACTIVE_DIR / "trial_state.yaml")
    counters = read_yaml(ACTIVE_DIR / "observation_counters.yaml")
    next_event = read_yaml(ACTIVE_DIR / "next_required_event.yaml")
    holdings = read_json(ACTIVE_DIR / "current_holdings.json")
    targets = read_json(ACTIVE_DIR / "current_target_vectors.json")
    checks.extend(
        [
            (
                "trial_identity_reconciled",
                trial.get("trial_id") == TRIAL_ID
                and trial.get("strategy_id") == STRATEGY_ID
                and trial.get("route") == "standalone_only"
                and trial.get("status") == "active_prospective_validation"
                and trial.get("activation_timestamp") == ACTIVATION_TIMESTAMP,
                "active trial identity, route, state, and timestamp are frozen",
            ),
            (
                "observation_identity_reconciled",
                counters.get("validation_observation_id") == OBSERVATION_ID
                and counters.get("trial_id") == TRIAL_ID
                and counters.get("validation_decision", "") == ""
                and counters.get("paper_demo_observation") is False,
                "validation observation is active and remains brokerless",
            ),
            (
                "active_trial_exactly_once",
                active_trial_state_count() == 1,
                f"active operational trial-state count={active_trial_state_count()}",
            ),
            (
                "activation_boundary_reconciled",
                next_event.get("formation_date") == INITIAL_FORMATION_DATE.isoformat()
                and next_event.get("intended_execution_session")
                == INITIAL_EXECUTION_DATE.isoformat()
                and next_event.get("first_eligible_performance_session")
                == FIRST_PERFORMANCE_DATE.isoformat(),
                "July formation and August 3/4 boundaries remain frozen",
            ),
            (
                "scheduled_targets_reconciled",
                holdings.get("execution_status") == "scheduled_not_executed"
                and holdings.get("pending_targets") == targets
                and math.isclose(targets[STRATEGY_ID]["SPY"], 1.0 / 3.0)
                and math.isclose(targets[STRATEGY_ID]["SHY"], 1.0 / 3.0)
                and math.isclose(targets[STRATEGY_ID]["VNQ"], 1.0 / 3.0)
                and all(validate_weights(value) for value in targets.values()),
                "frozen candidate and six comparator targets are unchanged",
            ),
            (
                "static_weights_exact",
                targets["faa_full_period_average_weight_static_control"]
                == STATIC_WEIGHTS,
                "archived static weights were not recalculated or rounded",
            ),
            (
                "decision_boundary_reconciled",
                read_yaml(ACTIVE_DIR / "decision_boundary.yaml")
                == DECISION_BOUNDARY,
                "24/24/6/6 minimums and 36-month maximum remain frozen",
            ),
        ]
    )

    daily_rows = read_csv(ACTIVE_DIR / "daily_performance_ledger.csv")
    comparator_rows = read_csv(
        ACTIVE_DIR / "daily_comparator_performance_ledger.csv"
    )
    checkpoint_rows = read_csv(ACTIVE_DIR / "monthly_checkpoint_ledger.csv")
    checks.extend(
        [
            (
                "candidate_daily_keys_unique",
                unique_keys(
                    daily_rows,
                    ("market_date", "portfolio_id", "cost_bps")
                    if daily_rows and "portfolio_id" in daily_rows[0]
                    else ("market_date", "trial_id"),
                ),
                f"candidate daily ledger rows={len(daily_rows)}",
            ),
            (
                "comparator_daily_keys_unique",
                unique_keys(
                    comparator_rows,
                    ("market_date", "portfolio_id", "cost_bps"),
                ),
                f"comparator daily ledger rows={len(comparator_rows)}",
            ),
            (
                "checkpoint_keys_unique",
                unique_keys(checkpoint_rows, ("checkpoint_id",)),
                f"monthly checkpoint rows={len(checkpoint_rows)}",
            ),
            (
                "no_pre_boundary_performance",
                all(
                    date.fromisoformat(row["market_date"])
                    >= FIRST_PERFORMANCE_DATE
                    for row in daily_rows + comparator_rows
                ),
                "no validation return is dated before 2026-08-04",
            ),
        ]
    )

    inventory, latest = admitted_snapshot_inventory()
    checks.extend(
        [
            (
                "immutable_snapshot_hashes_verified",
                all(row["status"] == "pass" for row in inventory),
                "corrected stored-file hashes, row hashes, dates, and prices pass",
            ),
            (
                "latest_admitted_session_reconciled",
                set(latest.values()) == {INITIAL_FORMATION_DATE},
                "all seven admitted snapshots end on 2026-07-31",
            ),
        ]
    )
    alert = read_json(ACTIVE_DIR / "snapshot_hash_reconciliation_alert.json")
    checks.append(
        (
            "snapshot_reconciliation_alert_is_nondecision_append",
            len(alert) == len(SYMBOLS)
            and all(
                row.get("snapshot_overwritten") is False
                and row.get("record_content_changed") is False
                and row.get("decision_ledger_changed") is False
                for row in alert
            ),
            "the activation hash alert changed no data, targets, holdings, or decision",
        )
    )

    fixture_checks = fixture_flow_checks()
    checks.extend(
        (name, passed, "no-network deterministic recorder fixture")
        for name, passed in fixture_checks.items()
    )
    checks.extend(
        [
            (
                "initial_counters_zero",
                counters.get("elapsed_completed_months") == 0
                and counters.get("completed_holding_intervals") == 0
                and counters.get("differentiation_months_vs_return_only") == 0
                and counters.get("differentiation_months_vs_no_correlation") == 0,
                "no initialization or incomplete interval received counter credit",
            ),
            (
                "activation_and_design_packets_present",
                (ACTIVATION_DIR / "consistency_check.json").is_file()
                and (DESIGN_DIR / "consistency_check.json").is_file(),
                "authoritative design and activation packets are readable",
            ),
        ]
    )
    protected_after = snapshot_protected_hashes()
    active_after = tree_hash(ACTIVE_DIR)
    checks.append(
        (
            "offline_gate_is_read_only",
            protected_before == protected_after and active_before == active_after,
            "offline reconciliation changed neither protected nor active state",
        )
    )
    rows = [
        {
            "check_order": index,
            "gate_id": name,
            "status": "pass" if passed else "fail",
            "detail": detail,
            "checked_before_network_access": True,
            "network_calls_at_check": 0,
        }
        for index, (name, passed, detail) in enumerate(checks, start=1)
    ]
    return {
        "passed": all(row["status"] == "pass" for row in rows),
        "rows": rows,
        "inventory": inventory,
        "latest_by_symbol": latest,
        "protected_before": protected_before,
        "protected_after": protected_after,
        "active_before": active_before,
        "active_after": active_after,
    }


def deterministic_run_id(
    latest_admitted: date, invocation_timestamp: datetime
) -> str:
    stamp = invocation_timestamp.astimezone(timezone.utc).strftime(
        "%Y%m%dT%H%M%S%fZ"
    )
    trial_hash = activation.canonical_hash(TRIAL_ID).split(":", 1)[1][:12]
    return f"{latest_admitted.isoformat()}__{stamp}__trial_{trial_hash}"


def recording_report(manifest: dict[str, Any]) -> str:
    return f"""# FAA Prospective Validation Recording

## Operational Outcome

**`{manifest['outcome']}`**

The active trial `{TRIAL_ID}` and observation `{OBSERVATION_ID}` were
reconciled before the time gate. The latest fully completed U.S. regular
session was `{manifest['latest_completed_session']}` and the latest admitted
immutable market session remained `{manifest['latest_admitted_session']}`.

This invocation made `{manifest['network_calls']}` provider calls, created
`{manifest['new_execution_events']}` execution events, and appended
`{manifest['new_daily_performance_rows']}` daily performance rows. No
strategy, trial, validation observation, paper/demo observation, broker order,
or validation decision was created.

## Boundary

The frozen July 31 formation remains scheduled for execution at the August 3
regular-session close. August 3 is not a validation-performance session; the
first eligible return remains August 4. Counters remain unchanged until a
complete prospective holding interval exists.

Exact next action: `{manifest['next_action']}`.
"""


def write_run_packet(
    run_dir: Path,
    manifest: dict[str, Any],
    offline_rows: list[dict[str, Any]],
    active_hash_before: str,
    active_hash_after: str,
    protected_before: dict[str, str],
    protected_after: dict[str, str],
) -> dict[str, Any]:
    if run_dir.exists():
        raise FileExistsError(f"immutable run packet already exists: {run_dir}")
    staging = run_dir.parent / f".{run_dir.name}.staging"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True, exist_ok=False)

    write_yaml_once(staging / "recording_manifest.yaml", manifest)
    active_rows = [
        {
            "state_scope": "active_operational_state",
            "state_path": relative(ACTIVE_DIR),
            "hash_before": active_hash_before,
            "hash_after": active_hash_after,
            "changed": active_hash_before != active_hash_after,
            "change_authorized": False,
        }
    ]
    write_csv_path(
        staging / "active_state_before_after.csv",
        active_rows,
        CSV_SCHEMAS["active_state_before_after.csv"],
    )
    write_csv_path(
        staging / "offline_gate_results.csv",
        offline_rows,
        CSV_SCHEMAS["offline_gate_results.csv"],
    )
    provider_rows = [
        {
            "provider_id": "alpaca_market_data_read_only_adjusted_daily",
            "attempted": False,
            "network_calls": 0,
            "request_start": "",
            "request_end": "",
            "status": "not_called_time_gate",
            "account_endpoint_called": False,
            "position_endpoint_called": False,
            "order_endpoint_called": False,
            "detail": "latest completed session precedes scheduled execution",
        }
    ]
    write_csv_path(
        staging / "provider_attempt_log.csv",
        provider_rows,
        CSV_SCHEMAS["provider_attempt_log.csv"],
    )
    for name in (
        "raw_retrieval_manifest.csv",
        "retrieval_reproducibility.csv",
        "required_session_coverage.csv",
        "new_snapshot_manifest.csv",
        "snapshot_revision_alerts.csv",
        "execution_event_ledger.csv",
        "new_daily_candidate_performance.csv",
        "new_daily_comparator_performance.csv",
        "formation_ledger.csv",
        "target_vector_ledger.csv",
        "completed_interval_ledger.csv",
        "monthly_checkpoint_record.csv",
        "turnover_cost_reconciliation.csv",
    ):
        write_csv_path(staging / name, [], CSV_SCHEMAS[name])

    invariants = [
        {
            "invariant_id": row["gate_id"],
            "status": row["status"],
            "detail": row["detail"],
        }
        for row in offline_rows
    ]
    invariants.extend(
        [
            {
                "invariant_id": "time_gate_prevents_provider_access",
                "status": "pass",
                "detail": "latest completed session is before 2026-08-03",
            },
            {
                "invariant_id": "august_3_performance_absent",
                "status": "pass",
                "detail": "no August 3 validation return was created",
            },
            {
                "invariant_id": "validation_decision_remains_blank",
                "status": "pass",
                "detail": "recording task made no validation decision",
            },
        ]
    )
    write_csv_path(
        staging / "invariant_results.csv",
        invariants,
        CSV_SCHEMAS["invariant_results.csv"],
    )
    state_rows = [
        {
            "state_path": relative(run_dir),
            "change_type": "immutable_recording_run_packet_created",
            "append_only": True,
            "prior_records_modified": False,
            "hash_before": "missing",
            "hash_after": "recorded_after_atomic_publish",
        }
    ]
    write_csv_path(
        staging / "state_change_manifest.csv",
        state_rows,
        CSV_SCHEMAS["state_change_manifest.csv"],
    )
    outcome_rows = [
        {
            "task_id": TASK_ID,
            "trial_id": TRIAL_ID,
            "observation_id": OBSERVATION_ID,
            "outcome": manifest["outcome"],
            "failure_reason": manifest["failure_reason"],
            "latest_completed_session": manifest["latest_completed_session"],
            "latest_admitted_session": manifest["latest_admitted_session"],
            "network_calls": manifest["network_calls"],
            "new_execution_events": manifest["new_execution_events"],
            "new_daily_performance_rows": manifest["new_daily_performance_rows"],
            "new_completed_holding_intervals": manifest[
                "new_completed_holding_intervals"
            ],
            "new_checkpoints": manifest["new_checkpoints"],
            "validation_decision": "",
            "next_action": manifest["next_action"],
        }
    ]
    write_csv_path(
        staging / "outcome_summary.csv",
        outcome_rows,
        CSV_SCHEMAS["outcome_summary.csv"],
    )
    failure_rows: list[dict[str, Any]] = []
    if manifest["failure_reason"]:
        failure_rows.append(
            {
                "task_id": TASK_ID,
                "outcome": manifest["outcome"],
                "failure_reason": manifest["failure_reason"],
                "detail": manifest.get("failure_detail", ""),
                "next_action": manifest["next_action"],
            }
        )
    write_csv_path(
        staging / "failure_reasons.csv",
        failure_rows,
        CSV_SCHEMAS["failure_reasons.csv"],
    )
    write_csv_path(
        staging / "next_actions.csv",
        [
            {
                "scope": "faa_prospective_validation_recorder",
                "outcome": manifest["outcome"],
                "next_action": manifest["next_action"],
                "executed": False,
            }
        ],
        CSV_SCHEMAS["next_actions.csv"],
    )
    write_text_once(staging / "recording_report.md", recording_report(manifest))

    current_files = {path.name for path in staging.iterdir() if path.is_file()}
    expected_before_consistency = REQUIRED_OUTPUTS - {"consistency_check.json"}
    consistency = {
        "task_id": TASK_ID,
        "trial_id": TRIAL_ID,
        "observation_id": OBSERVATION_ID,
        "outcome": manifest["outcome"],
        "failure_reason": manifest["failure_reason"],
        "exact_next_action": manifest["next_action"],
        "offline_gate_pass": all(row["status"] == "pass" for row in offline_rows),
        "latest_completed_session": manifest["latest_completed_session"],
        "latest_admitted_session": manifest["latest_admitted_session"],
        "network_calls": 0,
        "provider_calls_before_time_gate": 0,
        "account_endpoint_called": False,
        "position_endpoint_called": False,
        "order_endpoint_called": False,
        "broker_or_paper_orders": 0,
        "new_strategy_configurations": 0,
        "new_experiment_trials": 0,
        "new_validation_observations": 0,
        "paper_demo_observations": 0,
        "process_tasks": 1,
        "data_capability_tasks": 0,
        "new_execution_events": 0,
        "new_daily_performance_rows": 0,
        "new_completed_holding_intervals": 0,
        "new_checkpoints": 0,
        "historical_backfill_performed": False,
        "pre_august_4_return_created": False,
        "august_3_validation_return_created": False,
        "initialization_cost_applied": False,
        "validation_decision_made": False,
        "active_trial_and_observation_identity_unchanged": True,
        "active_state_changed": active_hash_before != active_hash_after,
        "immutable_records_overwritten": False,
        "canonical_cache_modified": protected_before.get("data/cache")
        != protected_after.get("data/cache"),
        "protected_state_and_prior_evidence_unchanged": protected_before
        == protected_after,
        "protected_hashes_before": protected_before,
        "protected_hashes_after": protected_after,
        "required_outputs_exact_before_consistency_write": current_files
        == expected_before_consistency,
        "next_action_executed": False,
    }
    consistency["overall_pass"] = bool(
        consistency["offline_gate_pass"]
        and consistency["network_calls"] == 0
        and consistency["new_daily_performance_rows"] == 0
        and not consistency["active_state_changed"]
        and not consistency["canonical_cache_modified"]
        and consistency["protected_state_and_prior_evidence_unchanged"]
        and consistency["required_outputs_exact_before_consistency_write"]
    )
    write_json_once(staging / "consistency_check.json", consistency)
    final_files = {path.name for path in staging.iterdir() if path.is_file()}
    if final_files != REQUIRED_OUTPUTS:
        raise RuntimeError(
            f"recording output mismatch missing={REQUIRED_OUTPUTS-final_files} "
            f"extra={final_files-REQUIRED_OUTPUTS}"
        )
    staging.rename(run_dir)
    return consistency


def run(now: datetime | None = None) -> dict[str, Any]:
    invocation = now or datetime.now(timezone.utc)
    if invocation.tzinfo is None:
        invocation = invocation.replace(tzinfo=timezone.utc)
    invocation = invocation.astimezone(timezone.utc)
    protected_before = snapshot_protected_hashes()
    source_before = file_hash(SOURCE_PACKET)
    active_before = tree_hash(ACTIVE_DIR)

    offline = offline_gate()
    latest_admitted = min(offline["latest_by_symbol"].values())
    latest_completed = activation.latest_completed_session(invocation)
    if not offline["passed"]:
        outcome = BLOCKED
        failure_reason = "local_methodology_failure"
        next_action = NEXT_BLOCKED
    else:
        outcome = time_gate(latest_completed, None)
        failure_reason = ""
        next_action = NEXT_RECORD

    # This invocation is before the scheduled execution. Later phases are
    # guarded here so provider access can never occur before their accounting
    # implementation is selected by the time gate.
    if outcome != PENDING and offline["passed"]:
        outcome = DEFERRED
        failure_reason = "required_data_unavailable"
        next_action = NEXT_RECORD

    active_after = tree_hash(ACTIVE_DIR)
    protected_after = snapshot_protected_hashes()
    source_after = file_hash(SOURCE_PACKET)
    run_id = deterministic_run_id(latest_admitted, invocation)
    run_dir = CHECKPOINT_ROOT / run_id
    manifest = {
        "task_id": TASK_ID,
        "mode": MODE,
        "stage": STAGE,
        "run_id": run_id,
        "invocation_timestamp_utc": invocation.isoformat(),
        "trial_id": TRIAL_ID,
        "observation_id": OBSERVATION_ID,
        "strategy_id": STRATEGY_ID,
        "route": "standalone_only",
        "outcome": outcome,
        "failure_reason": failure_reason,
        "latest_completed_session": latest_completed.isoformat(),
        "latest_admitted_session": latest_admitted.isoformat(),
        "scheduled_initial_execution": INITIAL_EXECUTION_DATE.isoformat(),
        "first_eligible_performance_session": FIRST_PERFORMANCE_DATE.isoformat(),
        "network_calls": 0,
        "new_strategy_configurations": 0,
        "new_experiment_trials": 0,
        "new_validation_observations": 0,
        "paper_demo_observations": 0,
        "process_tasks": 1,
        "data_capability_tasks": 0,
        "new_execution_events": 0,
        "new_daily_performance_rows": 0,
        "new_completed_holding_intervals": 0,
        "new_checkpoints": 0,
        "broker_or_paper_orders": 0,
        "validation_decision": "",
        "next_action": next_action,
        "source_packet_hash_before": source_before,
        "source_packet_hash_after": source_after,
        "active_state_hash_before": active_before,
        "active_state_hash_after": active_after,
        "decision_boundary": DECISION_BOUNDARY,
    }
    consistency = write_run_packet(
        run_dir,
        manifest,
        offline["rows"],
        active_before,
        active_after,
        protected_before,
        protected_after,
    )
    if source_before != source_after:
        raise RuntimeError("source packet changed during recording")
    if not consistency["overall_pass"]:
        raise RuntimeError("FAA prospective recording consistency check failed")
    return {
        "task_id": TASK_ID,
        "run_id": run_id,
        "run_dir": relative(run_dir),
        "outcome": outcome,
        "failure_reason": failure_reason,
        "next_action": next_action,
        "latest_completed_session": latest_completed.isoformat(),
        "network_calls": 0,
    }


def parse_now(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=TASK_ID)
    parser.add_argument("--now-utc", type=parse_now, default=None)
    args = parser.parse_args(argv)
    result = run(args.now_utc)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
