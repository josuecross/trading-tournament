from __future__ import annotations

import argparse
import csv
import io
import json
import math
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.research import (
    record_psar_standard_paper_demo_observation_v1 as common,
)
from strategy_lab.research_os.research import (
    record_psar_standard_paper_demo_virtual_execution_v1 as market_data,
)


TASK_ID = "record_faa_standard_paper_demo_observation_v1"
STAGE = "paper-demo-onboarding"
OBSERVATION_ID = "paper_demo_faa_4m_top3_v1"
STRATEGY_ID = "keller_vanputten_faa_4m_top3_v1"
OUTCOME_INITIALIZED = "faa_standard_observation_initialized"
OUTCOME_PENDING = "faa_standard_observation_recording_pending"
OUTCOME_BLOCKED = "faa_standard_observation_recording_blocked"
NEXT_RECORD = TASK_ID
NEXT_BLOCKED = "direction_owner_review_faa_standard_recording_block_v1"

EXECUTION_DATE = date(2026, 8, 3)
FIRST_PERFORMANCE_DATE = date(2026, 8, 4)
SIGNAL_DATE = date(2026, 7, 31)
EVENT_LABEL = "standard_observation_current_target_initialization"
INITIALIZED_STATUS = "initialized_active_recording"
PRIMARY_COST_BPS = 5.0
EXPECTED_TARGET = {
    "AGG": 0.0,
    "EFA": 0.0,
    "GSG": 0.0,
    "SHY": 1.0 / 3.0,
    "SPY": 1.0 / 3.0,
    "VNQ": 1.0 / 3.0,
    "VWO": 0.0,
}
TARGET_HASH = common.canonical_hash(EXPECTED_TARGET)

RUN_ROOT = ROOT / "evidence" / "paper_demo_observation" / TASK_ID
ONBOARDING_DIR = (
    ROOT
    / "evidence"
    / "paper_demo_onboarding"
    / "correct_faa_stage_and_onboard_paper_demo_observation_v1"
    / "latest"
)
OBSERVATION_DIR = ROOT / "paper_forward_observations" / OBSERVATION_ID
OBSERVATION_YAML = OBSERVATION_DIR / "active_observation.yaml"
COMPONENT_LEDGER = OBSERVATION_DIR / "component_forward_ledger.csv"
ACTIVE_OBSERVATIONS_PATH = ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml"
REGISTRY_PATH = ROOT / "strategy_lab" / "strategy_registry.yaml"
SOURCE_PACKET = Path(
    r"C:\Users\te3442\.codex\attachments"
    r"\2d088518-1b12-41fc-bd9d-4bb7228a8870\pasted-text.txt"
)

PROTECTED_PATHS = (
    ROOT / "data" / "cache",
    ONBOARDING_DIR,
    ROOT / "paper_forward_observations" / "paper_demo_decelerated_psar_20pct_diversifier_v1",
    ROOT / "strategy_lab" / "RESEARCH_ROADMAP.md",
    ROOT / "strategy_lab" / "research_os" / "research" / "research_queue.yaml",
    ROOT / "strategy_lab" / "research_os" / "family_lineage" / "family_ledger.yaml",
)

REQUIRED_OUTPUTS = {
    "recording_manifest.yaml",
    "prior_target_reconciliation.csv",
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


def read_target_snapshot_hash() -> str:
    rows = common.read_csv(ONBOARDING_DIR / "initial_signal_reconciliation.csv")
    matches = [row for row in rows if row.get("check_id") == "target_vector_exact"]
    if len(matches) != 1 or matches[0].get("status") != "pass":
        raise RuntimeError("FAA onboarding target snapshot is missing or invalid")
    return matches[0]["snapshot_hash"]


def load_frozen_target(observation: dict[str, Any] | None = None) -> dict[str, float]:
    payload = observation or common.read_yaml(OBSERVATION_YAML)
    target = {
        str(symbol): float(weight)
        for symbol, weight in payload.get("scheduled_target_allocation", {}).items()
    }
    target = dict(sorted(target.items()))
    if target != EXPECTED_TARGET:
        raise RuntimeError("FAA scheduled target does not match the frozen July 31 target")
    if common.canonical_hash(target) != TARGET_HASH:
        raise RuntimeError("FAA frozen target hash mismatch")
    return target


def close_completed(now: datetime) -> bool:
    return market_data.close_completed(now)


def calculate_virtual_initialization(
    target: dict[str, float], prices: dict[str, float], initial_capital: float
) -> dict[str, Any]:
    result = market_data.calculate_virtual_initialization(target, prices, initial_capital)
    expected_cost = initial_capital * PRIMARY_COST_BPS / 10000.0
    if not math.isclose(float(result["transaction_cost"]), expected_cost, abs_tol=1e-12):
        raise RuntimeError("FAA initialization cost does not reconcile")
    return result


def _ledger_rows() -> list[dict[str, str]]:
    return common.read_csv(COMPONENT_LEDGER)


def already_initialized() -> bool:
    observation = common.read_yaml(OBSERVATION_YAML)
    rows = _ledger_rows()
    return bool(
        observation.get("initialization_status") == INITIALIZED_STATUS
        and observation.get("initialization_execution_date") == EXECUTION_DATE.isoformat()
        and len(rows) == 1
        and rows[0].get("row_type") == "virtual_initialization"
        and rows[0].get("date") == EXECUTION_DATE.isoformat()
    )


def latest_initialized_packet() -> Path | None:
    if not RUN_ROOT.exists():
        return None
    for path in sorted((item for item in RUN_ROOT.iterdir() if item.is_dir()), reverse=True):
        summary = path / "outcome_summary.csv"
        if not summary.exists():
            continue
        rows = common.read_csv(summary)
        if len(rows) == 1 and rows[0].get("outcome") == OUTCOME_INITIALIZED:
            return path
    return None


def append_initialization_ledger(row: dict[str, Any]) -> None:
    if _ledger_rows():
        raise RuntimeError("FAA standard component ledger is not empty")
    with COMPONENT_LEDGER.open("r", encoding="utf-8-sig", newline="") as handle:
        fields = next(csv.reader(handle))
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerow({field: common.csv_value(row.get(field)) for field in fields})
    common.atomic_write_text(COMPONENT_LEDGER, buffer.getvalue())


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
            "latest_operational_update_evidence_path": common.relative(output_dir),
            "latest_operational_update_utc": completed_at,
            "historical_backfill": False,
            "paper_orders": False,
            "live_orders": False,
            "order_placement": False,
            "next_action": NEXT_RECORD,
        }
    )
    active_after = json.loads(json.dumps(active))
    active_rows = [
        row
        for row in active_after.get("active_observations", [])
        if row.get("observation_id") == OBSERVATION_ID
    ]
    if len(active_rows) != 1:
        raise RuntimeError("FAA active observation row is missing or duplicated")
    active_rows[0].update(
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
    registry_rows = [
        row
        for row in registry_after.get("strategies", [])
        if row.get("strategy_id") == STRATEGY_ID
    ]
    if len(registry_rows) != 1:
        raise RuntimeError("FAA registry row is missing or duplicated")
    registry_rows[0].update(
        {
            "initialization_status": INITIALIZED_STATUS,
            "status": "active_paper_demo_observation",
            "latest_evidence_path": common.relative(output_dir),
            "latest_operational_update_utc": completed_at,
            "next_action": NEXT_RECORD,
        }
    )
    return observation_after, active_after, registry_after


def _report(outcome: str, next_action: str, initialized: bool) -> str:
    detail = (
        "The frozen July 31 target was initialized virtually at the August 3 adjusted close. "
        "The $1.50 cost was charged once and no August 3 performance row was created."
        if initialized
        else "No virtual initialization was committed; positions, costs, and performance remain unchanged."
    )
    return f"""# FAA Standard Paper/Demo Virtual Initialization

## Outcome

**`{outcome}`**

{detail}

August 4, 2026 remains the first eligible performance date. No strategy,
trial, observation, broker call, paper order, or real-money action was created.

Exact next action: `{next_action}`.
"""


def run(now: datetime | None = None) -> dict[str, Any]:
    if already_initialized():
        packet = latest_initialized_packet()
        if packet is None:
            raise RuntimeError("FAA is initialized but its immutable standard packet is missing")
        return {
            "task_id": TASK_ID,
            "run_id": packet.name,
            "evidence_path": common.relative(packet),
            "outcome": OUTCOME_INITIALIZED,
            "failure_reason": "",
            "initialization_status": INITIALIZED_STATUS,
            "virtual_execution_events": 1,
            "performance_rows": 0,
            "broker_calls": 0,
            "orders_created": 0,
            "reused_existing_execution": True,
            "next_action": NEXT_RECORD,
        }

    started = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    output_dir = RUN_ROOT / common.run_id(started)
    output_dir.mkdir(parents=True, exist_ok=False)
    protected_before = common.map_hashes(PROTECTED_PATHS)
    source_before = common.file_hash(SOURCE_PACKET)
    observation_before = common.read_yaml(OBSERVATION_YAML)
    active_before = common.active_payload()
    registry_before = common.registry_payload()
    unrelated_active_before = [
        row for row in active_before.get("active_observations", [])
        if row.get("observation_id") != OBSERVATION_ID
    ]
    unrelated_registry_before = [
        row for row in registry_before.get("strategies", [])
        if row.get("strategy_id") != STRATEGY_ID
    ]

    provider: dict[str, Any] = {
        "attempt": {
            "provider": "alpaca_market_data",
            "attempted": False,
            "bounded_cycles": 0,
            "status": "not_attempted",
            "account_endpoint_called": False,
            "position_endpoint_called": False,
            "order_endpoint_called": False,
            "broker_calls": 0,
            "orders_created": 0,
        },
        "coverage": [], "price_rows": [], "prices": {}, "success": False,
    }
    target_rows: list[dict[str, Any]] = []
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
        target = load_frozen_target(observation_before)
        onboarding_hash = read_target_snapshot_hash()
        local_checks = {
            "onboarding_target_snapshot_present": onboarding_hash.startswith("sha256:"),
            "target_hash_exact": common.canonical_hash(target) == TARGET_HASH,
            "scheduled_status_exact": observation_before.get("initialization_status") == "scheduled_for_first_prospective_execution",
            "scheduled_execution_exact": observation_before.get("scheduled_first_execution_date") == EXECUTION_DATE.isoformat(),
            "signal_date_exact": observation_before.get("frozen_signal_date") == SIGNAL_DATE.isoformat(),
            "first_performance_date_exact": observation_before.get("first_eligible_performance_date") == FIRST_PERFORMANCE_DATE.isoformat(),
            "initial_capital_exact": math.isclose(float(observation_before.get("initial_virtual_capital", 0.0)), 3000.0, abs_tol=1e-12),
            "no_prior_virtual_execution": _ledger_rows() == [] and not observation_before.get("initialization_execution_date") and not observation_before.get("current_virtual_positions"),
            "regular_session_date": common.repair.prior_activation.next_regular_session(date(2026, 8, 2)) == EXECUTION_DATE,
        }
        for symbol, weight in target.items():
            target_rows.append(
                {
                    "observation_id": OBSERVATION_ID,
                    "signal_date": SIGNAL_DATE.isoformat(),
                    "symbol": symbol,
                    "onboarding_weight": weight,
                    "observation_weight": float(observation_before["scheduled_target_allocation"][symbol]),
                    "weight_exact": float(observation_before["scheduled_target_allocation"][symbol]) == weight,
                    "canonical_target_hash": TARGET_HASH,
                    "onboarding_snapshot_hash": onboarding_hash,
                    "target_recalculated": False,
                }
            )
        if not all(local_checks.values()):
            raise RuntimeError("FAA local target or observation reconciliation failed")
    except BaseException as exc:  # noqa: BLE001
        outcome = OUTCOME_BLOCKED
        failure_reason = "local_methodology_failure"
        next_action = NEXT_BLOCKED
        provider["attempt"]["status"] = "not_attempted_local_methodology_failure"
        provider["attempt"]["error"] = common.sanitize_error(exc)
        target = EXPECTED_TARGET
    else:
        if not close_completed(started):
            outcome = OUTCOME_PENDING
            failure_reason = "scheduled_close_not_completed"
            next_action = NEXT_RECORD
        else:
            provider = market_data.retrieve_execution_prices(output_dir, tuple(sorted(target)))
            if not provider["success"]:
                outcome = OUTCOME_PENDING
                failure_reason = "required_standard_market_data_unavailable"
                next_action = NEXT_RECORD
            else:
                try:
                    initialization = calculate_virtual_initialization(
                        target, provider["prices"], float(observation_before["initial_virtual_capital"])
                    )
                    completed_at = datetime.now(timezone.utc).isoformat()
                    data_hashes = {row["symbol"]: row["normalized_hash"] for row in provider["price_rows"]}
                    append_initialization_ledger(
                        {
                            "observation_id": OBSERVATION_ID,
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
                            "signal_date": SIGNAL_DATE.isoformat(),
                            "rebalance_reference_date": EXECUTION_DATE.isoformat(),
                            "data_snapshot_hashes": data_hashes,
                            "strategy_fingerprint": observation_before["strategy_fingerprint"],
                            "orders_created": 0,
                            "broker_calls": 0,
                            "status": INITIALIZED_STATUS,
                        }
                    )
                    observation_after, active_after, registry_after = initialized_states(
                        observation_before, active_before, registry_before, initialization, output_dir, completed_at
                    )
                    common.write_yaml(OBSERVATION_YAML, observation_after)
                    common.atomic_write_text(ACTIVE_OBSERVATIONS_PATH, yaml.safe_dump(active_after, sort_keys=False, width=110, allow_unicode=False))
                    common.atomic_write_text(REGISTRY_PATH, yaml.safe_dump(registry_after, sort_keys=False, width=110, allow_unicode=False))
                    initialization_rows = [{
                        "observation_id": OBSERVATION_ID,
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
                    }]
                    execution_rows = [{
                        "observation_id": OBSERVATION_ID,
                        "event_label": EVENT_LABEL,
                        "intended_execution_date": EXECUTION_DATE.isoformat(),
                        "completed_execution_date": EXECUTION_DATE.isoformat(),
                        "status": "completed_virtual_execution",
                        "virtual_execution": True,
                        "broker_order": False,
                        "performance_row_created": False,
                    }]
                    holding_rows = [{
                        "observation_id": OBSERVATION_ID,
                        "as_of": EXECUTION_DATE.isoformat(),
                        "symbol": symbol,
                        "adjusted_close": initialization["prices"][symbol],
                        "target_weight": target[symbol],
                        "shares": initialization["shares"][symbol],
                        "market_value": initialization["holdings"][symbol],
                        "post_cost_weight": initialization["holdings"][symbol] / initialization["post_cost_equity"],
                    } for symbol in sorted(target)]
                    holding_rows.append({
                        "observation_id": OBSERVATION_ID, "as_of": EXECUTION_DATE.isoformat(),
                        "symbol": "CASH", "adjusted_close": 1.0, "target_weight": 0.0,
                        "shares": initialization["residual_cash"], "market_value": initialization["residual_cash"],
                        "post_cost_weight": initialization["residual_cash"] / initialization["post_cost_equity"],
                    })
                    turnover_rows = [{
                        "observation_id": OBSERVATION_ID,
                        "status": "completed_virtual_initialization",
                        "initialization_turnover": initialization["initialization_turnover"],
                        "primary_cost_bps": PRIMARY_COST_BPS,
                        "projected_cost": 1.5,
                        "actual_cost": initialization["transaction_cost"],
                        "cost_difference": initialization["transaction_cost"] - 1.5,
                        "cost_charged_count": 1,
                    }]
                    outcome = OUTCOME_INITIALIZED
                    next_action = NEXT_RECORD
                except BaseException as exc:  # noqa: BLE001
                    outcome = OUTCOME_BLOCKED
                    failure_reason = "local_methodology_failure"
                    next_action = NEXT_BLOCKED
                    provider["attempt"]["error"] = common.sanitize_error(exc)

    initialized = outcome == OUTCOME_INITIALIZED
    ledger_rows = _ledger_rows()
    protected_after = common.map_hashes(PROTECTED_PATHS)
    source_after = common.file_hash(SOURCE_PACKET)
    active_final = common.active_payload()
    registry_final = common.registry_payload()
    unrelated_active_after = [row for row in active_final.get("active_observations", []) if row.get("observation_id") != OBSERVATION_ID]
    unrelated_registry_after = [row for row in registry_final.get("strategies", []) if row.get("strategy_id") != STRATEGY_ID]

    manifest = {
        "task_id": TASK_ID, "stage": STAGE, "run_id": output_dir.name,
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(), "outcome": outcome,
        "failure_reason": failure_reason, "observation_id": OBSERVATION_ID,
        "strategy_id": STRATEGY_ID, "execution_date": EXECUTION_DATE.isoformat(),
        "first_eligible_performance_date": FIRST_PERFORMANCE_DATE.isoformat(),
        "target_hash": TARGET_HASH, "target_recalculated": False,
        "new_strategies": 0, "new_experiment_trials": 0, "new_observations": 0,
        "existing_observations_updated": 1 if initialized else 0,
        "virtual_execution_events": len(execution_rows), "performance_rows": 0,
        "broker_or_paper_orders": 0, "next_action": next_action,
    }
    common.write_yaml(output_dir / "recording_manifest.yaml", manifest)
    common.write_csv(output_dir / "prior_target_reconciliation.csv", target_rows, ["observation_id", "signal_date", "symbol", "onboarding_weight", "observation_weight", "weight_exact", "canonical_target_hash", "onboarding_snapshot_hash", "target_recalculated"])
    common.write_csv(output_dir / "provider_attempt_log.csv", [provider["attempt"]], ["provider", "attempted", "bounded_cycles", "status", "account_endpoint_called", "position_endpoint_called", "order_endpoint_called", "broker_calls", "orders_created"])
    common.write_csv(output_dir / "required_session_coverage.csv", provider["coverage"], ["symbol", "required_session", "returned_rows", "exact_session_rows", "ordered_unique_sessions", "valid_adjusted_OHLC", "coverage_complete", "normalized_hash"])
    common.write_csv(output_dir / "execution_price_reconciliation.csv", provider["price_rows"], ["symbol", "execution_date", "adjusted_close", "timestamp", "provider", "feed", "adjustment", "normalized_hash", "admissible"])
    common.write_csv(output_dir / "virtual_initialization_record.csv", initialization_rows, ["observation_id", "execution_date", "event_label", "initial_virtual_capital", "initialization_prices", "target_weights", "virtual_shares", "residual_virtual_cash", "initialization_turnover", "transaction_cost", "post_cost_starting_virtual_equity", "performance_row_created"])
    common.write_csv(output_dir / "execution_event_ledger.csv", execution_rows, ["observation_id", "event_label", "intended_execution_date", "completed_execution_date", "status", "virtual_execution", "broker_order", "performance_row_created"])
    common.write_csv(output_dir / "virtual_holdings_after.csv", holding_rows, ["observation_id", "as_of", "symbol", "adjusted_close", "target_weight", "shares", "market_value", "post_cost_weight"])
    common.write_csv(output_dir / "turnover_cost_reconciliation.csv", turnover_rows, ["observation_id", "status", "initialization_turnover", "primary_cost_bps", "projected_cost", "actual_cost", "cost_difference", "cost_charged_count"])
    common.write_csv(output_dir / "new_performance_rows.csv", performance_rows, ["observation_id", "date", "return", "post_cost_equity"])
    common.write_csv(output_dir / "observation_state_before_after.csv", [{
        "observation_id": OBSERVATION_ID,
        "before_initialization_status": observation_before.get("initialization_status", ""),
        "after_initialization_status": observation_after.get("initialization_status", ""),
        "performance_rows_before": 0, "performance_rows_after": 0,
        "historical_backfill": False,
    }], ["observation_id", "before_initialization_status", "after_initialization_status", "performance_rows_before", "performance_rows_after", "historical_backfill"])
    state_rows = [{
        "scope": scope, "path": common.relative(path),
        "change": change if initialized else "none", "authorized": initialized,
    } for scope, path, change in (
        ("FAA_observation", OBSERVATION_YAML, "virtual_initialization_state"),
        ("FAA_component_ledger", COMPONENT_LEDGER, "append_one_initialization_row"),
        ("FAA_active_inventory", ACTIVE_OBSERVATIONS_PATH, "initialization_status_only"),
        ("FAA_registry", REGISTRY_PATH, "initialization_status_and_evidence_pointer_only"),
    )]
    for path in PROTECTED_PATHS:
        key = common.relative(path)
        state_rows.append({"scope": "protected_state_or_prior_evidence", "path": key, "change": "none", "authorized": False, "before_hash": protected_before[key], "after_hash": protected_after[key], "unchanged": protected_before[key] == protected_after[key]})
    common.write_csv(output_dir / "state_change_manifest.csv", state_rows, ["scope", "path", "change", "authorized", "before_hash", "after_hash", "unchanged"])
    common.write_csv(output_dir / "outcome_summary.csv", [{
        "task_id": TASK_ID, "run_id": output_dir.name, "observation_id": OBSERVATION_ID,
        "outcome": outcome, "failure_reason": failure_reason, "next_action": next_action,
        "virtual_execution_events": len(execution_rows), "performance_rows": 0,
        "broker_or_paper_orders": 0,
    }], ["task_id", "run_id", "observation_id", "outcome", "failure_reason", "next_action", "virtual_execution_events", "performance_rows", "broker_or_paper_orders"])
    common.write_csv(output_dir / "failure_reasons.csv", [
        {"outcome": OUTCOME_PENDING, "failure_reason": "scheduled_close_not_completed", "selected": failure_reason == "scheduled_close_not_completed"},
        {"outcome": OUTCOME_PENDING, "failure_reason": "required_standard_market_data_unavailable", "selected": failure_reason == "required_standard_market_data_unavailable"},
        {"outcome": OUTCOME_BLOCKED, "failure_reason": "local_methodology_failure", "selected": failure_reason == "local_methodology_failure"},
    ], ["outcome", "failure_reason", "selected"])
    common.write_csv(output_dir / "next_actions.csv", [
        {"outcome": OUTCOME_INITIALIZED, "next_action": NEXT_RECORD, "selected": outcome == OUTCOME_INITIALIZED, "executed": False},
        {"outcome": OUTCOME_PENDING, "next_action": NEXT_RECORD, "selected": outcome == OUTCOME_PENDING, "executed": False},
        {"outcome": OUTCOME_BLOCKED, "next_action": NEXT_BLOCKED, "selected": outcome == OUTCOME_BLOCKED, "executed": False},
    ], ["outcome", "next_action", "selected", "executed"])
    (output_dir / "recording_report.md").write_text(_report(outcome, next_action, initialized), encoding="utf-8")

    checks = {
        **local_checks,
        "source_packet_unchanged": source_before == source_after,
        "protected_state_unchanged": protected_before == protected_after,
        "unrelated_active_observations_unchanged": unrelated_active_before == unrelated_active_after,
        "unrelated_registry_records_unchanged": unrelated_registry_before == unrelated_registry_after,
        "target_never_recalculated": all(not row["target_recalculated"] for row in target_rows),
        "provider_called_only_after_close": not provider["attempt"].get("attempted", False) or close_completed(started),
        "no_account_position_or_order_API": not provider["attempt"].get("account_endpoint_called", False) and not provider["attempt"].get("position_endpoint_called", False) and not provider["attempt"].get("order_endpoint_called", False),
        "execution_event_count_valid": len(execution_rows) == (1 if initialized else 0),
        "zero_performance_rows": performance_rows == [],
        "no_august_3_performance": all(row.get("date") != EXECUTION_DATE.isoformat() for row in performance_rows),
        "first_eligible_performance_date_preserved": observation_after.get("first_eligible_performance_date") == FIRST_PERFORMANCE_DATE.isoformat(),
        "cost_reconciles_if_initialized": not initialized or (len(turnover_rows) == 1 and math.isclose(float(turnover_rows[0]["actual_cost"]), 1.5, abs_tol=1e-12) and turnover_rows[0]["cost_charged_count"] == 1),
        "ledger_row_count_valid": len(ledger_rows) == (1 if initialized else 0),
        "no_historical_backfill": observation_after.get("historical_backfill") is False,
        "entity_counts_reconcile": manifest["new_strategies"] == 0 and manifest["new_experiment_trials"] == 0 and manifest["new_observations"] == 0,
        "no_broker_or_paper_orders": manifest["broker_or_paper_orders"] == 0,
        "required_outputs_exact_before_consistency": {path.name for path in output_dir.iterdir() if path.is_file()} == REQUIRED_OUTPUTS - {"consistency_check.json"},
        "next_action_not_executed": True,
    }
    common.write_json(output_dir / "consistency_check.json", {
        "task_id": TASK_ID, "run_id": output_dir.name, "outcome": outcome,
        "failure_reason": failure_reason, "next_action": next_action, **checks,
        "new_strategies": 0, "new_experiment_trials": 0, "new_observations": 0,
        "existing_paper_demo_observations_updated": 1 if initialized else 0,
        "virtual_execution_events": len(execution_rows), "performance_rows": 0,
        "broker_calls": 0, "paper_orders": 0, "live_orders": 0,
        "real_money_actions": 0, "protected_hashes_before": protected_before,
        "protected_hashes_after": protected_after, "overall_pass": all(checks.values()),
    })
    return {
        "task_id": TASK_ID, "run_id": output_dir.name,
        "evidence_path": common.relative(output_dir), "outcome": outcome,
        "failure_reason": failure_reason,
        "initialization_status": observation_after.get("initialization_status", ""),
        "virtual_execution_events": len(execution_rows), "performance_rows": 0,
        "broker_calls": 0, "orders_created": 0, "reused_existing_execution": False,
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
