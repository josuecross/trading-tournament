from __future__ import annotations

import argparse
import csv
import io
import json
import math
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any

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
from execution_lab.alpaca_micro_live_v1.data.alpaca_historical_bars import (
    parse_bars_response,
)
from strategy_lab.research_os.research import (
    record_psar_standard_paper_demo_observation_v1 as freeze,
)


TASK_ID = "record_psar_standard_paper_demo_observation_v1"
STAGE = "paper-demo-onboarding"
OUTCOME_INITIALIZED = "psar_standard_observation_initialized"
OUTCOME_PENDING = "psar_standard_observation_recording_pending"
OUTCOME_BLOCKED = "psar_standard_observation_recording_blocked"
NEXT_RECORD = TASK_ID
NEXT_BLOCKED = "direction_owner_review_psar_standard_recording_block_v1"

PRIOR_RUN_ID = "20260803T180001656265Z"
PRIOR_RUN_DIR = freeze.RUN_ROOT / PRIOR_RUN_ID
PRIOR_FREEZE_RECORD = PRIOR_RUN_DIR / "target_freeze_record.csv"
EXECUTION_DATE = date(2026, 8, 3)
FIRST_PERFORMANCE_DATE = date(2026, 8, 4)
TARGET_HASH = "sha256:8e47821d0e2e402798426c6e0ec53fe35bd68819c7f2d7771350572e64d960e3"
EVENT_LABEL = "standard_observation_current_target_initialization"
INITIALIZED_STATUS = "initialized_active_recording"
SOURCE_PACKET = Path(
    r"C:\Users\te3442\.codex\attachments"
    r"\98be480b-7ab4-4d0c-a1c5-da0bf67bdf1a\pasted-text.txt"
)

REQUIRED_OUTPUTS = {
    "recording_manifest.yaml",
    "prior_target_freeze_reconciliation.csv",
    "provider_attempt_log.csv",
    "required_session_coverage.csv",
    "execution_price_reconciliation.csv",
    "virtual_initialization_record.csv",
    "execution_event_ledger.csv",
    "virtual_holdings_after.csv",
    "turnover_cost_reconciliation.csv",
    "new_performance_rows.csv",
    "observation_state_before_after.csv",
    "state_change_manifest.csv",
    "outcome_summary.csv",
    "failure_reasons.csv",
    "next_actions.csv",
    "consistency_check.json",
    "recording_report.md",
}


def load_frozen_target() -> tuple[dict[str, float], dict[str, str]]:
    rows = freeze.read_csv(PRIOR_FREEZE_RECORD)
    if len(rows) != 1:
        raise RuntimeError("prior target-freeze record must contain exactly one row")
    row = rows[0]
    target = {
        str(symbol): float(weight)
        for symbol, weight in json.loads(row["combined_target"]).items()
    }
    if row.get("target_hash") != TARGET_HASH or freeze.canonical_hash(target) != TARGET_HASH:
        raise RuntimeError("prior frozen target hash mismatch")
    if row.get("observation_id") != freeze.OBSERVATION_ID:
        raise RuntimeError("prior target-freeze observation mismatch")
    if row.get("event_label") != EVENT_LABEL:
        raise RuntimeError("prior target-freeze event label mismatch")
    if row.get("scheduled_execution_date") != EXECUTION_DATE.isoformat():
        raise RuntimeError("prior scheduled execution date mismatch")
    if row.get("first_eligible_performance_date") != FIRST_PERFORMANCE_DATE.isoformat():
        raise RuntimeError("prior first eligible performance date mismatch")
    return dict(sorted(target.items())), row


def close_completed(now: datetime) -> bool:
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    eastern_now = now.astimezone(freeze.repair.prior_activation.EASTERN)
    close_boundary = datetime.combine(
        EXECUTION_DATE,
        time(16, 0),
        tzinfo=freeze.repair.prior_activation.EASTERN,
    )
    return eastern_now >= close_boundary


def calculate_virtual_initialization(
    target: dict[str, float],
    prices: dict[str, float],
    initial_capital: float,
) -> dict[str, Any]:
    if set(target) != set(prices):
        raise RuntimeError("execution prices do not match the frozen target symbols")
    if not math.isclose(sum(target.values()), 1.0, abs_tol=1e-12):
        raise RuntimeError("frozen target does not sum to one")
    if any(weight < 0 for weight in target.values()):
        raise RuntimeError("frozen target contains a negative weight")
    if any(not math.isfinite(price) or price <= 0 for price in prices.values()):
        raise RuntimeError("execution price is nonfinite or nonpositive")

    turnover = 1.0
    cost = initial_capital * turnover * freeze.PRIMARY_COST_BPS / 10000.0
    post_cost_equity = initial_capital - cost
    shares = {
        symbol: post_cost_equity * target[symbol] / prices[symbol]
        for symbol in sorted(target)
    }
    holdings = {
        symbol: shares[symbol] * prices[symbol]
        for symbol in sorted(target)
    }
    residual_cash = post_cost_equity - sum(holdings.values())
    if abs(residual_cash) < 1e-9:
        residual_cash = 0.0
    return {
        "initial_virtual_capital": initial_capital,
        "initialization_turnover": turnover,
        "transaction_cost": cost,
        "post_cost_equity": post_cost_equity,
        "prices": dict(sorted(prices.items())),
        "shares": shares,
        "holdings": holdings,
        "residual_cash": residual_cash,
    }


def retrieve_execution_prices(
    output_dir: Path,
    symbols: tuple[str, ...],
) -> dict[str, Any]:
    retrieved_at = datetime.now(timezone.utc).isoformat()
    attempt = {
        "provider": "alpaca_market_data",
        "provider_role": "existing_standard_read_only_paper_demo_data_path",
        "attempted": True,
        "bounded_cycles": 1,
        "symbols": list(symbols),
        "execution_date": EXECUTION_DATE.isoformat(),
        "timeframe": "1Day",
        "feed": "iex",
        "adjustment": "all",
        "credentials_present": False,
        "live_credentials_detected": False,
        "page_count": 0,
        "row_count": 0,
        "status": "",
        "error": "",
        "account_endpoint_called": False,
        "position_endpoint_called": False,
        "order_endpoint_called": False,
        "broker_calls": 0,
        "orders_created": 0,
        "retrieval_timestamp_utc": retrieved_at,
    }
    coverage_rows: list[dict[str, Any]] = []
    price_rows: list[dict[str, Any]] = []
    prices: dict[str, float] = {}
    try:
        credentials = load_alpaca_credentials("paper")
        attempt["credentials_present"] = bool(credentials.present)
        attempt["live_credentials_detected"] = bool(credentials.live_credentials_detected)
        if not credentials.present or credentials.live_credentials_detected:
            attempt["status"] = "auth_or_environment_not_admitted"
            attempt["error"] = "approved non-live paper market-data credentials unavailable"
            return {"attempt": attempt, "coverage": coverage_rows, "price_rows": price_rows, "prices": prices, "success": False}

        client = AlpacaClient(
            credentials,
            AlpacaClientConfig(data_feed="iex", data_adjustment="all"),
        )
        merged: dict[str, Any] = {"bars": {symbol: [] for symbol in symbols}}
        raw_dir = output_dir / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        page_token: str | None = None
        raw_hashes: list[str] = []
        while True:
            payload = client.get_historical_bars_page(
                symbols=list(symbols),
                start=f"{EXECUTION_DATE.isoformat()}T00:00:00Z",
                end=f"{(EXECUTION_DATE + timedelta(days=1)).isoformat()}T00:00:00Z",
                timeframe="1Day",
                feed="iex",
                adjustment="all",
                page_token=page_token,
            )
            attempt["page_count"] += 1
            raw_path = raw_dir / f"execution_page_{attempt['page_count']:04d}.json"
            freeze.write_json(raw_path, payload)
            raw_hashes.append(freeze.file_hash(raw_path))
            for symbol in symbols:
                merged["bars"][symbol].extend(payload.get("bars", {}).get(symbol, []))
            page_token = payload.get("next_page_token")
            if not page_token:
                break
            if attempt["page_count"] >= 10:
                raise RuntimeError("bounded execution-price pagination limit exceeded")

        frames = parse_bars_response(merged, drop_incomplete_current_day=False)
        normalized_dir = output_dir / "normalized"
        normalized_dir.mkdir(parents=True, exist_ok=True)
        for symbol in symbols:
            frame = frames.get(symbol, pd.DataFrame()).copy()
            if not frame.empty:
                frame = frame[["date", "timestamp", "open", "high", "low", "close", "volume"]]
                frame = frame.sort_values("date").drop_duplicates("date", keep="last").reset_index(drop=True)
            normalized_path = normalized_dir / f"{symbol}.csv"
            frame.to_csv(normalized_path, index=False, lineterminator="\n")
            exact = frame.loc[frame["date"] == EXECUTION_DATE.isoformat()] if not frame.empty else frame
            valid = bool(
                len(exact) == 1
                and np.isfinite(exact[["open", "high", "low", "close"]].to_numpy(dtype=float)).all()
                and (exact[["open", "high", "low", "close"]] > 0).all().all()
                and float(exact.iloc[0]["high"]) >= max(float(exact.iloc[0][field]) for field in ("open", "low", "close"))
                and float(exact.iloc[0]["low"]) <= min(float(exact.iloc[0][field]) for field in ("open", "high", "close"))
            )
            coverage_rows.append(
                {
                    "symbol": symbol,
                    "required_session": EXECUTION_DATE.isoformat(),
                    "returned_rows": len(frame),
                    "exact_session_rows": len(exact),
                    "ordered_unique_sessions": bool(frame.empty or (frame["date"].is_monotonic_increasing and not frame["date"].duplicated().any())),
                    "valid_adjusted_OHLC": valid,
                    "coverage_complete": valid,
                    "normalized_hash": freeze.file_hash(normalized_path),
                }
            )
            if valid:
                close_price = float(exact.iloc[0]["close"])
                prices[symbol] = close_price
                price_rows.append(
                    {
                        "symbol": symbol,
                        "execution_date": EXECUTION_DATE.isoformat(),
                        "adjusted_close": close_price,
                        "timestamp": exact.iloc[0]["timestamp"],
                        "provider": "alpaca_market_data",
                        "feed": "iex",
                        "adjustment": "all",
                        "normalized_hash": freeze.file_hash(normalized_path),
                        "admissible": True,
                    }
                )
        attempt["row_count"] = sum(row["returned_rows"] for row in coverage_rows)
        attempt["raw_response_hashes"] = raw_hashes
        success = len(prices) == len(symbols) and all(row["coverage_complete"] for row in coverage_rows)
        attempt["status"] = "complete_august_3_adjusted_close_batch" if success else "incomplete_august_3_adjusted_close_batch"
        return {"attempt": attempt, "coverage": coverage_rows, "price_rows": price_rows, "prices": prices, "success": success}
    except BaseException as exc:  # noqa: BLE001 - provider failures remain auditable evidence.
        attempt["status"] = "provider_call_failed"
        attempt["error"] = freeze.sanitize_error(exc)
        return {"attempt": attempt, "coverage": coverage_rows, "price_rows": price_rows, "prices": prices, "success": False}


def append_initialization_ledger(row: dict[str, Any]) -> None:
    if freeze.read_csv(freeze.COMPONENT_LEDGER):
        raise RuntimeError("standard component ledger is not empty")
    with freeze.COMPONENT_LEDGER.open("r", encoding="utf-8-sig", newline="") as handle:
        fields = next(csv.reader(handle))
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerow({field: freeze.csv_value(row.get(field)) for field in fields})
    freeze.atomic_write_text(freeze.COMPONENT_LEDGER, buffer.getvalue())


def initialized_states(
    observation: dict[str, Any],
    active: dict[str, Any],
    registry: dict[str, Any],
    initialization: dict[str, Any],
    output_dir: Path,
    completed_at: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    observation_after = json.loads(json.dumps(observation))
    observation_after.update(
        {
            "initialization_status": INITIALIZED_STATUS,
            "current_checkpoint_status": "active_recording_no_performance_rows",
            "pre_execution_virtual_cash": 0.0,
            "pre_execution_virtual_positions": {},
            "pre_execution_virtual_shares": {},
            "current_virtual_equity": initialization["post_cost_equity"],
            "current_target_allocation": observation["scheduled_target_allocation"],
            "current_virtual_positions": initialization["holdings"],
            "current_virtual_shares": initialization["shares"],
            "virtual_cash": initialization["residual_cash"],
            "initialization_execution_date": EXECUTION_DATE.isoformat(),
            "initialization_turnover": initialization["initialization_turnover"],
            "initialization_cost": initialization["transaction_cost"],
            "post_cost_starting_virtual_equity": initialization["post_cost_equity"],
            "latest_committed_observation_date": EXECUTION_DATE.isoformat(),
            "latest_committed_virtual_equity": initialization["post_cost_equity"],
            "performance_rows": 0,
            "first_eligible_performance_date": FIRST_PERFORMANCE_DATE.isoformat(),
            "pending_reason": "",
            "latest_operational_update_id": TASK_ID,
            "latest_operational_update_evidence_path": freeze.relative(output_dir),
            "latest_operational_update_utc": completed_at,
            "historical_backfill": False,
            "paper_orders": False,
            "live_orders": False,
            "order_placement": False,
            "next_action": NEXT_RECORD,
        }
    )
    active_after = json.loads(json.dumps(active))
    matches = [row for row in active_after.get("active_observations", []) if row.get("observation_id") == freeze.OBSERVATION_ID]
    if len(matches) != 1:
        raise RuntimeError("active PSAR observation row is missing or duplicated")
    matches[0].update(
        {
            "initialization_status": INITIALIZED_STATUS,
            "current_checkpoint_status": "active_recording_no_performance_rows",
            "initialization_execution_date": EXECUTION_DATE.isoformat(),
            "first_eligible_performance_date": FIRST_PERFORMANCE_DATE.isoformat(),
            "current_virtual_equity": initialization["post_cost_equity"],
            "performance_rows": 0,
            "pending_reason": "",
            "latest_operational_update_utc": completed_at,
            "next_action": NEXT_RECORD,
        }
    )
    registry_after = json.loads(json.dumps(registry))
    strategy_rows = [row for row in registry_after.get("strategies", []) if row.get("strategy_id") == freeze.STRATEGY_ID]
    if len(strategy_rows) != 1:
        raise RuntimeError("PSAR registry row is missing or duplicated")
    strategy_rows[0].update(
        {
            "initialization_status": INITIALIZED_STATUS,
            "status": "active_paper_demo_observation",
            "latest_evidence_path": freeze.relative(output_dir),
            "latest_operational_update_utc": completed_at,
            "next_action": NEXT_RECORD,
        }
    )
    return observation_after, active_after, registry_after


def report_text(outcome: str, next_action: str, initialized: bool) -> str:
    detail = (
        "The frozen target was executed virtually at the August 3 adjusted close. "
        "The $1.50 initialization cost was charged once and no August 3 performance row was created."
        if initialized
        else "The August 3 regular-session close had not completed, so no provider call, position, cost, or performance row was created."
    )
    return f"""# PSAR Standard Paper/Demo Virtual Execution

## Outcome

**`{outcome}`**

{detail}

The target from `{PRIOR_RUN_ID}` remains unchanged. August 4, 2026 remains
the first eligible performance date. No strategy, trial, observation, broker
call, paper order, or real-money action was created.

Exact next action: `{next_action}`.
"""


def run(now: datetime | None = None) -> dict[str, Any]:
    started = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    output_dir = freeze.RUN_ROOT / freeze.run_id(started)
    output_dir.mkdir(parents=True, exist_ok=False)
    protected_paths = (*freeze.PROTECTED_PATHS, PRIOR_RUN_DIR)
    protected_before = freeze.map_hashes(protected_paths)
    source_before = freeze.file_hash(SOURCE_PACKET)
    observation_before = freeze.read_yaml(freeze.OBSERVATION_YAML)
    active_before = freeze.active_payload()
    registry_before = freeze.registry_payload()
    unrelated_active_before = [row for row in active_before.get("active_observations", []) if row.get("observation_id") != freeze.OBSERVATION_ID]
    unrelated_registry_before = [row for row in registry_before.get("strategies", []) if row.get("strategy_id") != freeze.STRATEGY_ID]

    target: dict[str, float] = {}
    prior_row: dict[str, str] = {}
    reconciliation_rows: list[dict[str, Any]] = []
    provider = {
        "attempt": {
            "provider": "alpaca_market_data",
            "attempted": False,
            "bounded_cycles": 0,
            "status": "not_attempted_before_scheduled_close",
            "account_endpoint_called": False,
            "position_endpoint_called": False,
            "order_endpoint_called": False,
            "broker_calls": 0,
            "orders_created": 0,
        },
        "coverage": [],
        "price_rows": [],
        "prices": {},
        "success": False,
    }
    initialization_rows: list[dict[str, Any]] = []
    execution_rows: list[dict[str, Any]] = []
    holding_rows: list[dict[str, Any]] = []
    turnover_rows: list[dict[str, Any]] = []
    performance_rows: list[dict[str, Any]] = []
    observation_after = observation_before
    active_after = active_before
    registry_after = registry_before
    failure_reason = ""

    local_checks: dict[str, bool] = {}
    try:
        target, prior_row = load_frozen_target()
        scheduled_target = {
            str(symbol): float(weight)
            for symbol, weight in observation_before.get("scheduled_target_allocation", {}).items()
        }
        local_checks = {
            "prior_freeze_hash_exact": freeze.canonical_hash(target) == TARGET_HASH,
            "observation_target_exact": scheduled_target == target,
            "observation_target_hash_exact": observation_before.get("target_freeze_hash") == TARGET_HASH,
            "scheduled_status_exact": observation_before.get("initialization_status") == "scheduled_for_first_prospective_execution",
            "scheduled_execution_exact": observation_before.get("scheduled_first_execution_date") == EXECUTION_DATE.isoformat(),
            "first_performance_date_exact": observation_before.get("first_eligible_performance_date") == FIRST_PERFORMANCE_DATE.isoformat(),
            "no_prior_virtual_execution": observation_before.get("current_target_allocation") == {} and freeze.read_csv(freeze.COMPONENT_LEDGER) == [],
            "regular_session_date": freeze.repair.prior_activation.next_regular_session(date(2026, 8, 2)) == EXECUTION_DATE,
        }
        for symbol in sorted(target):
            reconciliation_rows.append(
                {
                    "prior_run_id": PRIOR_RUN_ID,
                    "observation_id": freeze.OBSERVATION_ID,
                    "symbol": symbol,
                    "packet_weight": target[symbol],
                    "observation_scheduled_weight": scheduled_target.get(symbol, ""),
                    "weight_exact": scheduled_target.get(symbol) == target[symbol],
                    "target_hash": TARGET_HASH,
                    "packet_hash_exact": prior_row.get("target_hash") == TARGET_HASH,
                    "target_recalculated": False,
                }
            )
        if not all(local_checks.values()):
            raise RuntimeError("local frozen-target or observation schema reconciliation failed")
    except BaseException as exc:  # noqa: BLE001 - local failures are explicit blockers.
        outcome = OUTCOME_BLOCKED
        failure_reason = "local_methodology_failure"
        next_action = NEXT_BLOCKED
        provider["attempt"]["status"] = "not_attempted_local_methodology_failure"
        provider["attempt"]["error"] = freeze.sanitize_error(exc)
    else:
        if not close_completed(started):
            outcome = OUTCOME_PENDING
            failure_reason = "scheduled_close_not_completed"
            next_action = NEXT_RECORD
            projected_cost = float(observation_before["initial_virtual_capital"]) * freeze.PRIMARY_COST_BPS / 10000.0
            turnover_rows = [
                {
                    "observation_id": freeze.OBSERVATION_ID,
                    "status": "pending_scheduled_close",
                    "initialization_turnover": 1.0,
                    "primary_cost_bps": freeze.PRIMARY_COST_BPS,
                    "projected_cost": projected_cost,
                    "actual_cost": 0.0,
                    "cost_difference": "pending_execution",
                    "cost_charged_count": 0,
                }
            ]
        else:
            provider = retrieve_execution_prices(output_dir, tuple(sorted(target)))
            if not provider["success"]:
                outcome = OUTCOME_PENDING
                failure_reason = "required_standard_market_data_unavailable"
                next_action = NEXT_RECORD
            else:
                try:
                    initialization = calculate_virtual_initialization(
                        target,
                        provider["prices"],
                        float(observation_before["initial_virtual_capital"]),
                    )
                    completed_at = datetime.now(timezone.utc).isoformat()
                    data_hashes = {
                        row["symbol"]: row["normalized_hash"]
                        for row in provider["price_rows"]
                    }
                    ledger_row = {
                        "observation_id": freeze.OBSERVATION_ID,
                        "date": EXECUTION_DATE.isoformat(),
                        "row_type": "virtual_initialization",
                        "continuity_from_original_activation": False,
                        "prior_interval_status": "unobserved_before_standard_current_target_initialization",
                        "initial_virtual_capital": initialization["initial_virtual_capital"],
                        "post_cost_equity": initialization["post_cost_equity"],
                        "initialization_cost": initialization["transaction_cost"],
                        "target_weights": target,
                        "holdings": initialization["holdings"],
                        "shares": initialization["shares"],
                        "cash": initialization["residual_cash"],
                        "signal_date": prior_row["state_date"],
                        "rebalance_reference_date": EXECUTION_DATE.isoformat(),
                        "data_snapshot_hashes": data_hashes,
                        "strategy_fingerprint": observation_before["strategy_fingerprint"],
                        "orders_created": 0,
                        "broker_calls": 0,
                        "status": INITIALIZED_STATUS,
                        "reference_component_values": observation_before.get("scheduled_reference_target", {}),
                        "reference_component_weights": {"reference": freeze.REFERENCE_WEIGHT, "psar": freeze.PSAR_WEIGHT},
                        "psar_recursive_state": observation_before.get("latest_psar_recursive_state", {}),
                        "psar_sleeve_target": observation_before.get("scheduled_psar_sleeve_target", {}),
                        "combined_target_weights": target,
                        "inner_turnover": 0.0,
                        "outer_turnover": 0.0,
                        "total_turnover": initialization["initialization_turnover"],
                        "transaction_cost": initialization["transaction_cost"],
                        "intended_execution_date": EXECUTION_DATE.isoformat(),
                        "completed_execution_date": EXECUTION_DATE.isoformat(),
                        "missing_data_events": [],
                        "blocked_execution_reason": "",
                        "rule_deviations": [],
                    }
                    append_initialization_ledger(ledger_row)
                    observation_after, active_after, registry_after = initialized_states(
                        observation_before,
                        active_before,
                        registry_before,
                        initialization,
                        output_dir,
                        completed_at,
                    )
                    freeze.write_yaml(freeze.OBSERVATION_YAML, observation_after)
                    freeze.atomic_write_text(
                        freeze.ACTIVE_OBSERVATIONS_PATH,
                        yaml.safe_dump(active_after, sort_keys=False, width=110, allow_unicode=False),
                    )
                    freeze.atomic_write_text(
                        freeze.REGISTRY_PATH,
                        yaml.safe_dump(registry_after, sort_keys=False, width=110, allow_unicode=False),
                    )
                    initialization_rows = [
                        {
                            "observation_id": freeze.OBSERVATION_ID,
                            "execution_date": EXECUTION_DATE.isoformat(),
                            "event_label": EVENT_LABEL,
                            "initial_virtual_capital": initialization["initial_virtual_capital"],
                            "initialization_prices": initialization["prices"],
                            "target_weights": target,
                            "virtual_shares": initialization["shares"],
                            "residual_virtual_cash": initialization["residual_cash"],
                            "initialization_turnover": initialization["initialization_turnover"],
                            "transaction_cost": initialization["transaction_cost"],
                            "post_cost_starting_virtual_equity": initialization["post_cost_equity"],
                            "performance_row_created": False,
                        }
                    ]
                    execution_rows = [
                        {
                            "observation_id": freeze.OBSERVATION_ID,
                            "event_label": EVENT_LABEL,
                            "intended_execution_date": EXECUTION_DATE.isoformat(),
                            "completed_execution_date": EXECUTION_DATE.isoformat(),
                            "status": "completed_virtual_execution",
                            "virtual_execution": True,
                            "broker_order": False,
                            "performance_row_created": False,
                        }
                    ]
                    holding_rows = [
                        {
                            "observation_id": freeze.OBSERVATION_ID,
                            "as_of": EXECUTION_DATE.isoformat(),
                            "symbol": symbol,
                            "adjusted_close": initialization["prices"][symbol],
                            "target_weight": target[symbol],
                            "shares": initialization["shares"][symbol],
                            "market_value": initialization["holdings"][symbol],
                            "post_cost_weight": initialization["holdings"][symbol] / initialization["post_cost_equity"],
                        }
                        for symbol in sorted(target)
                    ]
                    holding_rows.append(
                        {
                            "observation_id": freeze.OBSERVATION_ID,
                            "as_of": EXECUTION_DATE.isoformat(),
                            "symbol": "CASH",
                            "adjusted_close": 1.0,
                            "target_weight": 0.0,
                            "shares": initialization["residual_cash"],
                            "market_value": initialization["residual_cash"],
                            "post_cost_weight": initialization["residual_cash"] / initialization["post_cost_equity"],
                        }
                    )
                    turnover_rows = [
                        {
                            "observation_id": freeze.OBSERVATION_ID,
                            "status": "completed_virtual_initialization",
                            "initialization_turnover": initialization["initialization_turnover"],
                            "primary_cost_bps": freeze.PRIMARY_COST_BPS,
                            "projected_cost": 1.5,
                            "actual_cost": initialization["transaction_cost"],
                            "cost_difference": initialization["transaction_cost"] - 1.5,
                            "cost_charged_count": 1,
                        }
                    ]
                    outcome = OUTCOME_INITIALIZED
                    next_action = NEXT_RECORD
                except BaseException as exc:  # noqa: BLE001 - initialization failures are local blockers.
                    outcome = OUTCOME_BLOCKED
                    failure_reason = "local_methodology_failure"
                    next_action = NEXT_BLOCKED
                    provider["attempt"]["error"] = freeze.sanitize_error(exc)

    protected_after = freeze.map_hashes(protected_paths)
    source_after = freeze.file_hash(SOURCE_PACKET)
    active_final = freeze.active_payload()
    registry_final = freeze.registry_payload()
    unrelated_active_after = [row for row in active_final.get("active_observations", []) if row.get("observation_id") != freeze.OBSERVATION_ID]
    unrelated_registry_after = [row for row in registry_final.get("strategies", []) if row.get("strategy_id") != freeze.STRATEGY_ID]
    ledger_rows = freeze.read_csv(freeze.COMPONENT_LEDGER)

    initialized = outcome == OUTCOME_INITIALIZED
    manifest = {
        "task_id": TASK_ID,
        "run_id": output_dir.name,
        "stage": STAGE,
        "started_utc": started.isoformat(),
        "prior_target_freeze_run_id": PRIOR_RUN_ID,
        "frozen_target_hash": TARGET_HASH,
        "scheduled_virtual_execution_date": EXECUTION_DATE.isoformat(),
        "first_eligible_performance_date": FIRST_PERFORMANCE_DATE.isoformat(),
        "outcome": outcome,
        "failure_reason": failure_reason,
        "next_action": next_action,
        "new_strategies": 0,
        "new_experiment_trials": 0,
        "new_observations": 0,
        "existing_paper_demo_observations_updated": 1 if initialized else 0,
        "virtual_execution_events": len(execution_rows),
        "performance_rows": 0,
        "broker_or_paper_orders": 0,
    }
    freeze.write_yaml(output_dir / "recording_manifest.yaml", manifest)
    freeze.write_csv(output_dir / "prior_target_freeze_reconciliation.csv", reconciliation_rows, ["prior_run_id", "observation_id", "symbol", "packet_weight", "observation_scheduled_weight", "weight_exact", "target_hash"])
    freeze.write_csv(output_dir / "provider_attempt_log.csv", [provider["attempt"]], ["provider", "attempted", "bounded_cycles", "status"])
    freeze.write_csv(output_dir / "required_session_coverage.csv", provider["coverage"], ["symbol", "required_session", "returned_rows", "exact_session_rows", "coverage_complete"])
    freeze.write_csv(output_dir / "execution_price_reconciliation.csv", provider["price_rows"], ["symbol", "execution_date", "adjusted_close", "timestamp", "provider", "adjustment", "admissible"])
    freeze.write_csv(output_dir / "virtual_initialization_record.csv", initialization_rows, ["observation_id", "execution_date", "event_label", "initial_virtual_capital", "post_cost_starting_virtual_equity"])
    freeze.write_csv(output_dir / "execution_event_ledger.csv", execution_rows, ["observation_id", "event_label", "intended_execution_date", "completed_execution_date", "status"])
    freeze.write_csv(output_dir / "virtual_holdings_after.csv", holding_rows, ["observation_id", "as_of", "symbol", "adjusted_close", "target_weight", "shares", "market_value", "post_cost_weight"])
    freeze.write_csv(output_dir / "turnover_cost_reconciliation.csv", turnover_rows, ["observation_id", "status", "initialization_turnover", "primary_cost_bps", "projected_cost", "actual_cost", "cost_difference", "cost_charged_count"])
    freeze.write_csv(output_dir / "new_performance_rows.csv", performance_rows, ["observation_id", "date", "return", "post_cost_equity"])
    freeze.write_csv(
        output_dir / "observation_state_before_after.csv",
        [{
            "observation_id": freeze.OBSERVATION_ID,
            "before_initialization_status": observation_before.get("initialization_status", ""),
            "after_initialization_status": observation_after.get("initialization_status", ""),
            "before_current_target": observation_before.get("current_target_allocation", {}),
            "after_current_target": observation_after.get("current_target_allocation", {}),
            "before_virtual_equity": observation_before.get("current_virtual_equity", ""),
            "after_virtual_equity": observation_after.get("current_virtual_equity", ""),
            "performance_rows_before": 0,
            "performance_rows_after": 0,
            "historical_backfill": False,
        }],
        ["observation_id", "before_initialization_status", "after_initialization_status", "performance_rows_before", "performance_rows_after"],
    )
    state_rows = [
        {
            "scope": scope,
            "path": freeze.relative(path),
            "change": change if initialized else "none",
            "authorized": initialized,
        }
        for scope, path, change in (
            ("PSAR_observation", freeze.OBSERVATION_YAML, "virtual_initialization_state"),
            ("PSAR_component_ledger", freeze.COMPONENT_LEDGER, "append_one_initialization_row"),
            ("PSAR_active_inventory", freeze.ACTIVE_OBSERVATIONS_PATH, "initialization_status_only"),
            ("PSAR_registry", freeze.REGISTRY_PATH, "initialization_status_and_evidence_pointer_only"),
        )
    ]
    for path in protected_paths:
        key = freeze.relative(path)
        state_rows.append({"scope": "protected_state_or_prior_evidence", "path": key, "change": "none", "authorized": False, "before_hash": protected_before[key], "after_hash": protected_after[key], "unchanged": protected_before[key] == protected_after[key]})
    freeze.write_csv(output_dir / "state_change_manifest.csv", state_rows, ["scope", "path", "change", "authorized"])
    freeze.write_csv(output_dir / "outcome_summary.csv", [{"task_id": TASK_ID, "run_id": output_dir.name, "observation_id": freeze.OBSERVATION_ID, "outcome": outcome, "failure_reason": failure_reason, "next_action": next_action, "virtual_execution_events": len(execution_rows), "performance_rows": 0, "broker_or_paper_orders": 0}], ["task_id", "run_id", "observation_id", "outcome", "failure_reason", "next_action"])
    freeze.write_csv(output_dir / "failure_reasons.csv", [
        {"outcome": OUTCOME_PENDING, "failure_reason": "scheduled_close_not_completed", "selected": failure_reason == "scheduled_close_not_completed"},
        {"outcome": OUTCOME_PENDING, "failure_reason": "required_standard_market_data_unavailable", "selected": failure_reason == "required_standard_market_data_unavailable"},
        {"outcome": OUTCOME_BLOCKED, "failure_reason": "local_methodology_failure", "selected": failure_reason == "local_methodology_failure"},
    ], ["outcome", "failure_reason", "selected"])
    freeze.write_csv(output_dir / "next_actions.csv", [
        {"outcome": OUTCOME_INITIALIZED, "next_action": NEXT_RECORD, "selected": outcome == OUTCOME_INITIALIZED, "executed": False},
        {"outcome": OUTCOME_PENDING, "next_action": NEXT_RECORD, "selected": outcome == OUTCOME_PENDING, "executed": False},
        {"outcome": OUTCOME_BLOCKED, "next_action": NEXT_BLOCKED, "selected": outcome == OUTCOME_BLOCKED, "executed": False},
    ], ["outcome", "next_action", "selected", "executed"])
    (output_dir / "recording_report.md").write_text(report_text(outcome, next_action, initialized), encoding="utf-8")

    top_level_before_consistency = {path.name for path in output_dir.iterdir() if path.is_file()}
    checks = {
        **local_checks,
        "prior_freeze_packet_unchanged": protected_before[freeze.relative(PRIOR_RUN_DIR)] == protected_after[freeze.relative(PRIOR_RUN_DIR)],
        "source_packet_unchanged": source_before == source_after,
        "protected_state_unchanged": protected_before == protected_after,
        "unrelated_active_observations_unchanged": unrelated_active_before == unrelated_active_after,
        "unrelated_registry_records_unchanged": unrelated_registry_before == unrelated_registry_after,
        "target_never_recalculated": all(not row["target_recalculated"] for row in reconciliation_rows),
        "provider_called_only_after_close": not provider["attempt"].get("attempted", False) or close_completed(started),
        "no_account_position_or_order_API": not provider["attempt"].get("account_endpoint_called", False) and not provider["attempt"].get("position_endpoint_called", False) and not provider["attempt"].get("order_endpoint_called", False),
        "execution_event_count_valid": len(execution_rows) == (1 if initialized else 0),
        "zero_performance_rows": performance_rows == [],
        "no_august_3_performance": all(row.get("date") != EXECUTION_DATE.isoformat() for row in performance_rows),
        "first_eligible_performance_date_preserved": observation_after.get("first_eligible_performance_date") == FIRST_PERFORMANCE_DATE.isoformat(),
        "cost_reconciles_if_initialized": not initialized or (len(turnover_rows) == 1 and math.isclose(float(turnover_rows[0]["actual_cost"]), 1.5, abs_tol=1e-12) and turnover_rows[0]["cost_charged_count"] == 1),
        "positions_created_only_if_initialized": bool(holding_rows) == initialized,
        "ledger_row_count_valid": len(ledger_rows) == (1 if initialized else 0),
        "no_historical_backfill": observation_after.get("historical_backfill") is False,
        "entity_counts_reconcile": manifest["new_strategies"] == 0 and manifest["new_experiment_trials"] == 0 and manifest["new_observations"] == 0,
        "no_broker_or_paper_orders": manifest["broker_or_paper_orders"] == 0,
        "required_outputs_exact_before_consistency": top_level_before_consistency == REQUIRED_OUTPUTS - {"consistency_check.json"},
        "next_action_not_executed": True,
    }
    consistency = {
        "task_id": TASK_ID,
        "run_id": output_dir.name,
        "outcome": outcome,
        "failure_reason": failure_reason,
        "next_action": next_action,
        **checks,
        "new_strategies": 0,
        "new_experiment_trials": 0,
        "new_observations": 0,
        "existing_paper_demo_observations_updated": 1 if initialized else 0,
        "virtual_execution_events": len(execution_rows),
        "performance_rows": 0,
        "broker_calls": 0,
        "paper_orders": 0,
        "live_orders": 0,
        "real_money_actions": 0,
        "protected_hashes_before": protected_before,
        "protected_hashes_after": protected_after,
        "overall_pass": all(checks.values()),
    }
    freeze.write_json(output_dir / "consistency_check.json", consistency)
    return {
        "task_id": TASK_ID,
        "run_id": output_dir.name,
        "evidence_path": freeze.relative(output_dir),
        "outcome": outcome,
        "failure_reason": failure_reason,
        "initialization_status": observation_after.get("initialization_status", ""),
        "virtual_execution_events": len(execution_rows),
        "performance_rows": 0,
        "broker_calls": 0,
        "orders_created": 0,
        "next_action": next_action,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=TASK_ID)
    parser.parse_args(argv)
    result = run()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 1 if result["outcome"] == OUTCOME_BLOCKED else 0


if __name__ == "__main__":
    raise SystemExit(main())
