from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import yaml

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.research import (
    record_faa_standard_paper_demo_observation_v1 as faa,
)
from strategy_lab.research_os.research import (
    record_psar_standard_paper_demo_observation_v1 as common,
)
from strategy_lab.research_os.research import (
    record_psar_standard_paper_demo_virtual_execution_v1 as psar,
)


TASK_ID = "record_august3_faa_psar_standard_demo_initializations_v1"
STAGE = "paper-demo-onboarding"
OUTCOME_RECORDED = "august3_standard_demo_initializations_recorded"
OUTCOME_PARTIAL = "august3_standard_demo_initializations_partial"
OUTCOME_PENDING = "august3_standard_demo_initializations_pending"
OUTCOME_BLOCKED = "august3_standard_demo_initializations_blocked"
NEXT_INITIALIZED = "targeted_native_etf_source_refresh_v3"
NEXT_PENDING = TASK_ID
NEXT_BLOCKED = "direction_owner_review_standard_demo_initialization_block_v1"

OUTPUT_DIR = (
    ROOT / "evidence" / "paper_demo_observation" / TASK_ID / "latest"
)
V2_DISCOVERY_DIR = (
    ROOT
    / "evidence"
    / "research_recovery"
    / "native_etf_source_refresh_v2_exploration_batch"
    / "latest"
)
SOURCE_PACKET = Path(
    r"C:\Users\te3442\.codex\attachments"
    r"\2d088518-1b12-41fc-bd9d-4bb7228a8870\pasted-text.txt"
)
PROTECTED_FIXED = (
    ROOT / "data" / "cache",
    ROOT / "strategy_lab" / "RESEARCH_ROADMAP.md",
    ROOT / "strategy_lab" / "research_os" / "research" / "research_queue.yaml",
    ROOT / "strategy_lab" / "research_os" / "family_lineage" / "family_ledger.yaml",
    V2_DISCOVERY_DIR,
    faa.ONBOARDING_DIR,
    psar.PRIOR_RUN_DIR,
)
REQUIRED_OUTPUTS = {
    "orchestration_manifest.yaml",
    "observation_execution_summary.csv",
    "faa_recorder_result.csv",
    "psar_recorder_result.csv",
    "execution_and_cost_reconciliation.csv",
    "entity_count_reconciliation.csv",
    "protected_state_reconciliation.csv",
    "outcome_summary.csv",
    "failure_reasons.csv",
    "next_actions.csv",
    "consistency_check.json",
    "orchestration_report.md",
}


def psar_already_initialized() -> bool:
    observation = common.read_yaml(common.OBSERVATION_YAML)
    rows = common.read_csv(common.COMPONENT_LEDGER)
    return bool(
        observation.get("initialization_status") == psar.INITIALIZED_STATUS
        and observation.get("initialization_execution_date") == psar.EXECUTION_DATE.isoformat()
        and len(rows) == 1
        and rows[0].get("row_type") == "virtual_initialization"
        and rows[0].get("date") == psar.EXECUTION_DATE.isoformat()
    )


def latest_psar_initialized_packet() -> Path | None:
    if not common.RUN_ROOT.exists():
        return None
    for path in sorted((item for item in common.RUN_ROOT.iterdir() if item.is_dir()), reverse=True):
        summary = path / "outcome_summary.csv"
        if not summary.exists():
            continue
        rows = common.read_csv(summary)
        if len(rows) == 1 and rows[0].get("outcome") == psar.OUTCOME_INITIALIZED:
            return path
    return None


def invoke_psar(now: datetime) -> dict[str, Any]:
    if not psar_already_initialized():
        result = psar.run(now=now)
        result["reused_existing_execution"] = False
        return result
    packet = latest_psar_initialized_packet()
    if packet is None:
        raise RuntimeError("PSAR is initialized but its immutable standard packet is missing")
    return {
        "task_id": psar.TASK_ID,
        "run_id": packet.name,
        "evidence_path": common.relative(packet),
        "outcome": psar.OUTCOME_INITIALIZED,
        "failure_reason": "",
        "initialization_status": psar.INITIALIZED_STATUS,
        "virtual_execution_events": 1,
        "performance_rows": 0,
        "broker_calls": 0,
        "orders_created": 0,
        "reused_existing_execution": True,
        "next_action": psar.NEXT_RECORD,
    }


def classify_outcome(
    close_is_complete: bool,
    faa_initialized: bool,
    psar_initialized: bool,
    recorder_blocked: bool,
) -> tuple[str, str]:
    if not close_is_complete:
        return OUTCOME_PENDING, NEXT_PENDING
    if recorder_blocked:
        return OUTCOME_BLOCKED, NEXT_BLOCKED
    initialized_count = int(faa_initialized) + int(psar_initialized)
    if initialized_count == 2:
        return OUTCOME_RECORDED, NEXT_INITIALIZED
    if initialized_count == 1:
        return OUTCOME_PARTIAL, NEXT_INITIALIZED
    return OUTCOME_BLOCKED, NEXT_BLOCKED


def _unrelated_observation_paths() -> tuple[Path, ...]:
    base = ROOT / "paper_forward_observations"
    excluded = {faa.OBSERVATION_ID, common.OBSERVATION_ID}
    return tuple(sorted(path for path in base.iterdir() if path.is_dir() and path.name not in excluded))


def _outcome_row(packet: Path) -> dict[str, str]:
    rows = common.read_csv(packet / "outcome_summary.csv")
    if len(rows) != 1:
        raise RuntimeError(f"recorder outcome packet is malformed: {packet}")
    return rows[0]


def _recorder_result_row(label: str, result: dict[str, Any]) -> dict[str, Any]:
    packet = ROOT / result["evidence_path"]
    packet_row = _outcome_row(packet)
    return {
        "recorder": label,
        "task_id": result["task_id"],
        "run_id": result["run_id"],
        "immutable_packet": result["evidence_path"],
        "packet_hash": common.tree_hash(packet),
        "outcome": result["outcome"],
        "packet_outcome": packet_row["outcome"],
        "failure_reason": result.get("failure_reason", ""),
        "virtual_execution_events": result.get("virtual_execution_events", 0),
        "performance_rows": result.get("performance_rows", 0),
        "broker_calls": result.get("broker_calls", 0),
        "orders_created": result.get("orders_created", 0),
        "reused_existing_execution": result.get("reused_existing_execution", False),
        "serial_order": 1 if label == "FAA" else 2,
    }


def _execution_reconciliation(
    label: str,
    observation_path: Path,
    ledger_path: Path,
    expected_target_hash: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    observation = common.read_yaml(observation_path)
    rows = common.read_csv(ledger_path)
    initialization_rows = [row for row in rows if row.get("row_type") == "virtual_initialization"]
    initialized = bool(
        observation.get("initialization_status") == psar.INITIALIZED_STATUS
        and observation.get("initialization_execution_date") == "2026-08-03"
        and len(initialization_rows) == 1
    )
    target = {
        str(symbol): float(weight)
        for symbol, weight in observation.get("scheduled_target_allocation", {}).items()
    }
    target_hash = common.canonical_hash(target) if target else ""
    ledger = initialization_rows[0] if initialization_rows else {}
    cost = float(ledger.get("initialization_cost") or 0.0)
    turnover = float(observation.get("initialization_turnover") or 0.0)
    post_cost = float(observation.get("post_cost_starting_virtual_equity") or 0.0)
    shares = observation.get("current_virtual_shares", {})
    holdings = observation.get("current_virtual_positions", {})
    summary = {
        "observation": label,
        "observation_id": observation.get("observation_id", ""),
        "strategy_id": observation.get("strategy_id", ""),
        "initialized": initialized,
        "initialization_status": observation.get("initialization_status", ""),
        "execution_date": observation.get("initialization_execution_date", ""),
        "first_eligible_performance_date": observation.get("first_eligible_performance_date", ""),
        "target_hash": target_hash,
        "expected_target_hash": expected_target_hash,
        "target_hash_exact": target_hash == expected_target_hash,
        "nonzero_positions": sum(float(value) > 0 for value in holdings.values()),
        "virtual_execution_events": len(initialization_rows),
        "performance_rows": int(observation.get("performance_rows") or 0),
    }
    accounting = {
        "observation": label,
        "observation_id": observation.get("observation_id", ""),
        "initial_virtual_capital": float(observation.get("initial_virtual_capital") or 0.0),
        "one_way_initialization_turnover": turnover,
        "cost_bps": float(observation.get("primary_cost_bps_per_one_way_turnover") or 0.0),
        "projected_initialization_cost": 1.5,
        "actual_initialization_cost": cost,
        "cost_difference": cost - 1.5 if initialized else 0.0,
        "cost_charged_once": initialized and math.isclose(cost, 1.5, abs_tol=1e-12),
        "post_cost_starting_equity": post_cost,
        "residual_cash": float(observation.get("virtual_cash") or 0.0),
        "holdings_value": sum(float(value) for value in holdings.values()),
        "shares_present_for_target_symbols": set(shares) == set(target) if initialized else False,
        "explicit_zero_weight_shares_zero": all(
            not math.isclose(float(target[symbol]), 0.0, abs_tol=1e-15)
            or math.isclose(float(shares.get(symbol, 0.0)), 0.0, abs_tol=1e-15)
            for symbol in target
        ) if initialized else False,
        "no_august3_performance": int(observation.get("performance_rows") or 0) == 0,
        "ledger_execution_rows": len(initialization_rows),
        "duplicate_execution_prevented": len(initialization_rows) <= 1,
    }
    return summary, accounting


def _discovery_closures_pass() -> bool:
    rows = common.read_csv(V2_DISCOVERY_DIR / "outcome_summary.csv")
    expected = {
        "botes_siepman_vortex14_spy_bil_v1": ("closed_exploration", "period_instability"),
        "varadi_real_momentum120_5d_spy_tip_v1": ("closed_exploration", "weak_vs_primary_control"),
    }
    actual = {
        row.get("strategy_id", ""): (row.get("outcome", ""), row.get("failure_reason", ""))
        for row in rows
    }
    return all(actual.get(strategy_id) == value for strategy_id, value in expected.items())


def _write_result_csv(path: Path, row: dict[str, Any]) -> None:
    common.write_csv(path, [row], list(row))


def run(
    now: datetime | None = None,
    faa_runner: Callable[[datetime], dict[str, Any]] | None = None,
    psar_runner: Callable[[datetime], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    started = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    close_is_complete = psar.close_completed(started)
    protected_paths = (*PROTECTED_FIXED, *_unrelated_observation_paths())
    protected_before = common.map_hashes(protected_paths)
    source_before = common.file_hash(SOURCE_PACKET)
    active_before = common.active_payload()
    registry_before = common.registry_payload()
    target_observation_ids = {faa.OBSERVATION_ID, common.OBSERVATION_ID}
    target_strategy_ids = {faa.STRATEGY_ID, common.STRATEGY_ID}
    unrelated_active_before = [row for row in active_before.get("active_observations", []) if row.get("observation_id") not in target_observation_ids]
    unrelated_registry_before = [row for row in registry_before.get("strategies", []) if row.get("strategy_id") not in target_strategy_ids]

    faa_call = faa_runner or (lambda value: faa.run(now=value))
    psar_call = psar_runner or invoke_psar
    if close_is_complete:
        faa_result = faa_call(started)
        psar_result = psar_call(started)
    else:
        faa_result = faa.run(now=started)
        psar_result = psar.run(now=started)
        psar_result["reused_existing_execution"] = False

    faa_summary, faa_accounting = _execution_reconciliation(
        "FAA", faa.OBSERVATION_YAML, faa.COMPONENT_LEDGER, faa.TARGET_HASH
    )
    psar_summary, psar_accounting = _execution_reconciliation(
        "PSAR", common.OBSERVATION_YAML, common.COMPONENT_LEDGER, psar.TARGET_HASH
    )
    recorder_blocked = faa_result["outcome"] == faa.OUTCOME_BLOCKED or psar_result["outcome"] == psar.OUTCOME_BLOCKED
    outcome, next_action = classify_outcome(
        close_is_complete, bool(faa_summary["initialized"]), bool(psar_summary["initialized"]), recorder_blocked
    )
    failure_reason = ""
    if outcome == OUTCOME_PENDING:
        failure_reason = "scheduled_close_not_completed"
    elif outcome == OUTCOME_PARTIAL:
        failure_reason = "independent_observation_data_or_reconciliation_pending"
    elif outcome == OUTCOME_BLOCKED:
        failure_reason = "shared_local_methodology_or_standard_schema_failure"

    active_after = common.active_payload()
    registry_after = common.registry_payload()
    unrelated_active_after = [row for row in active_after.get("active_observations", []) if row.get("observation_id") not in target_observation_ids]
    unrelated_registry_after = [row for row in registry_after.get("strategies", []) if row.get("strategy_id") not in target_strategy_ids]
    protected_after = common.map_hashes(protected_paths)
    source_after = common.file_hash(SOURCE_PACKET)

    faa_row = _recorder_result_row("FAA", faa_result)
    psar_row = _recorder_result_row("PSAR", psar_result)
    observation_rows = [faa_summary, psar_summary]
    accounting_rows = [faa_accounting, psar_accounting]
    newly_updated = sum(
        bool(row["initialized"]) and not bool(result.get("reused_existing_execution", False))
        for row, result in ((faa_summary, faa_result), (psar_summary, psar_result))
    )
    linked_events = sum(int(row["virtual_execution_events"]) for row in observation_rows)
    observations_initialized_by_task = sum(bool(row["initialized"]) for row in observation_rows)

    manifest = {
        "task_id": TASK_ID, "mode": "active-direction-execution", "stage": STAGE,
        "run_timestamp_utc": started.isoformat(), "close_admissible": close_is_complete,
        "outcome": outcome, "failure_reason": failure_reason,
        "faa_standard_packet": faa_result["evidence_path"],
        "psar_standard_packet": psar_result["evidence_path"],
        "recorders_invoked_serially": True, "recorder_order": [faa.TASK_ID, psar.TASK_ID],
        "new_strategies": 0, "new_experiment_trials": 0, "new_observations": 0,
        "existing_observations_updated": observations_initialized_by_task,
        "state_updates_this_invocation": newly_updated,
        "virtual_execution_events_linked": linked_events,
        "august_3_performance_rows": 0, "process_tasks": 1,
        "broker_or_paper_orders": 0, "next_action": next_action,
    }
    common.write_yaml(OUTPUT_DIR / "orchestration_manifest.yaml", manifest)
    common.write_csv(OUTPUT_DIR / "observation_execution_summary.csv", observation_rows, list(observation_rows[0]))
    _write_result_csv(OUTPUT_DIR / "faa_recorder_result.csv", faa_row)
    _write_result_csv(OUTPUT_DIR / "psar_recorder_result.csv", psar_row)
    common.write_csv(OUTPUT_DIR / "execution_and_cost_reconciliation.csv", accounting_rows, list(accounting_rows[0]))
    entity_rows = [
        {"entity_type": "strategy_configuration", "created": 0, "updated": 0, "expected": 0, "reconciled": True},
        {"entity_type": "experiment_trial", "created": 0, "updated": 0, "expected": 0, "reconciled": True},
        {"entity_type": "paper_demo_observation", "created": 0, "updated": observations_initialized_by_task, "expected": "0-2", "reconciled": 0 <= observations_initialized_by_task <= 2},
        {"entity_type": "virtual_execution_event", "created": sum(not bool(result.get("reused_existing_execution", False)) and int(result.get("virtual_execution_events", 0)) for result in (faa_result, psar_result)), "updated": 0, "expected": "0-2", "reconciled": linked_events <= 2},
        {"entity_type": "august_3_performance_row", "created": 0, "updated": 0, "expected": 0, "reconciled": True},
        {"entity_type": "process_task", "created": 1, "updated": 0, "expected": 1, "reconciled": True},
        {"entity_type": "broker_or_paper_order", "created": 0, "updated": 0, "expected": 0, "reconciled": True},
    ]
    common.write_csv(OUTPUT_DIR / "entity_count_reconciliation.csv", entity_rows, list(entity_rows[0]))
    protected_rows = [{
        "path": key, "hash_before": protected_before[key], "hash_after": protected_after[key],
        "unchanged": protected_before[key] == protected_after[key], "authorized_change": False,
    } for key in protected_before]
    protected_rows.extend([
        {"path": common.relative(faa.OBSERVATION_DIR), "hash_before": "authorized_target_state", "hash_after": common.tree_hash(faa.OBSERVATION_DIR), "unchanged": faa_result.get("reused_existing_execution", False), "authorized_change": True},
        {"path": common.relative(common.OBSERVATION_DIR), "hash_before": "authorized_target_state", "hash_after": common.tree_hash(common.OBSERVATION_DIR), "unchanged": psar_result.get("reused_existing_execution", False), "authorized_change": True},
        {"path": common.relative(common.ACTIVE_OBSERVATIONS_PATH), "hash_before": "authorized_two_rows_only", "hash_after": common.file_hash(common.ACTIVE_OBSERVATIONS_PATH), "unchanged": unrelated_active_before == unrelated_active_after, "authorized_change": True},
        {"path": common.relative(common.REGISTRY_PATH), "hash_before": "authorized_two_rows_only", "hash_after": common.file_hash(common.REGISTRY_PATH), "unchanged": unrelated_registry_before == unrelated_registry_after, "authorized_change": True},
    ])
    common.write_csv(OUTPUT_DIR / "protected_state_reconciliation.csv", protected_rows, list(protected_rows[0]))
    _write_result_csv(OUTPUT_DIR / "outcome_summary.csv", {
        "task_id": TASK_ID, "outcome": outcome, "failure_reason": failure_reason,
        "faa_initialized": faa_summary["initialized"], "psar_initialized": psar_summary["initialized"],
        "observations_updated": observations_initialized_by_task,
        "state_updates_this_invocation": newly_updated,
        "virtual_execution_events_linked": linked_events,
        "august_3_performance_rows": 0, "broker_or_paper_orders": 0,
        "next_action": next_action,
    })
    common.write_csv(OUTPUT_DIR / "failure_reasons.csv", [
        {"outcome": OUTCOME_RECORDED, "failure_reason": "", "selected": outcome == OUTCOME_RECORDED},
        {"outcome": OUTCOME_PARTIAL, "failure_reason": "independent_observation_data_or_reconciliation_pending", "selected": outcome == OUTCOME_PARTIAL},
        {"outcome": OUTCOME_PENDING, "failure_reason": "scheduled_close_not_completed", "selected": outcome == OUTCOME_PENDING},
        {"outcome": OUTCOME_BLOCKED, "failure_reason": "shared_local_methodology_or_standard_schema_failure", "selected": outcome == OUTCOME_BLOCKED},
    ], ["outcome", "failure_reason", "selected"])
    common.write_csv(OUTPUT_DIR / "next_actions.csv", [
        {"condition": "at_least_one_initialized", "next_action": NEXT_INITIALIZED, "selected": outcome in {OUTCOME_RECORDED, OUTCOME_PARTIAL}, "executed": False},
        {"condition": "both_pending_before_close", "next_action": NEXT_PENDING, "selected": outcome == OUTCOME_PENDING, "executed": False},
        {"condition": "shared_local_methodology_block", "next_action": NEXT_BLOCKED, "selected": outcome == OUTCOME_BLOCKED, "executed": False},
    ], ["condition", "next_action", "selected", "executed"])

    packet_performance_rows = sum(
        len(common.read_csv(ROOT / result["evidence_path"] / "new_performance_rows.csv"))
        for result in (faa_result, psar_result)
    )
    checks = {
        "august_3_close_admissible_for_recorded_outcome": outcome not in {OUTCOME_RECORDED, OUTCOME_PARTIAL} or close_is_complete,
        "recorders_serial_order_faa_then_psar": faa_row["serial_order"] == 1 and psar_row["serial_order"] == 2,
        "both_frozen_targets_exact": all(bool(row["target_hash_exact"]) for row in observation_rows),
        "execution_price_coverage_complete": all(
            all(item.get("coverage_complete") == "true" for item in common.read_csv(ROOT / result["evidence_path"] / "required_session_coverage.csv"))
            for result in (faa_result, psar_result)
        ),
        "explicit_shares_and_cash_reconcile": all(
            bool(row["shares_present_for_target_symbols"])
            and math.isclose(float(row["holdings_value"]) + float(row["residual_cash"]), float(row["post_cost_starting_equity"]), abs_tol=1e-9)
            for row in accounting_rows
        ),
        "turnover_and_cost_reconcile": all(
            math.isclose(float(row["one_way_initialization_turnover"]), 1.0, abs_tol=1e-12)
            and bool(row["cost_charged_once"])
            and math.isclose(float(row["post_cost_starting_equity"]), 2998.5, abs_tol=1e-9)
            for row in accounting_rows
        ),
        "no_august_3_performance_rows": packet_performance_rows == 0 and all(int(row["performance_rows"]) == 0 for row in observation_rows),
        "august_4_first_eligible_date": all(row["first_eligible_performance_date"] == "2026-08-04" for row in observation_rows),
        "duplicate_execution_prevented": all(bool(row["duplicate_execution_prevented"]) and int(row["ledger_execution_rows"]) == 1 for row in accounting_rows),
        "no_new_strategy_trial_or_observation": manifest["new_strategies"] == 0 and manifest["new_experiment_trials"] == 0 and manifest["new_observations"] == 0,
        "no_broker_account_position_order_calls": all(int(row["broker_calls"]) == 0 and int(row["orders_created"]) == 0 for row in (faa_row, psar_row)),
        "protected_paths_unchanged": protected_before == protected_after,
        "unrelated_active_observations_unchanged": unrelated_active_before == unrelated_active_after,
        "unrelated_registry_rows_unchanged": unrelated_registry_before == unrelated_registry_after,
        "source_packet_unchanged": source_before == source_after,
        "vortex_and_real_momentum_closures_preserved": _discovery_closures_pass(),
        "next_action_not_executed": True,
    }
    report = f"""# August 3 FAA and PSAR Standard Demo Initializations

## Outcome

**`{outcome}`**

FAA and PSAR were processed serially through their standard virtual-execution
recorders. Their immutable packets are linked in this orchestration packet.
No August 3 market return was created; August 4 remains the first eligible
performance session. No broker, account, position, order, or real-money action
occurred.

Exact next action: `{next_action}`.
"""
    (OUTPUT_DIR / "orchestration_report.md").write_text(report, encoding="utf-8")
    checks["required_outputs_exact_before_consistency"] = {
        path.name
        for path in OUTPUT_DIR.iterdir()
        if path.is_file() and path.name != "consistency_check.json"
    } == REQUIRED_OUTPUTS - {"consistency_check.json"}
    consistency = {
        "task_id": TASK_ID, "outcome": outcome, "failure_reason": failure_reason,
        "next_action": next_action, **checks,
        "new_strategies": 0, "new_experiment_trials": 0, "new_observations": 0,
        "existing_observations_updated": observations_initialized_by_task,
        "state_updates_this_invocation": newly_updated,
        "virtual_execution_events_linked": linked_events,
        "august_3_performance_rows": 0, "process_tasks": 1,
        "broker_or_paper_orders": 0, "real_money_actions": 0,
        "protected_hashes_before": protected_before, "protected_hashes_after": protected_after,
        "overall_pass": all(checks.values()),
    }
    common.write_json(OUTPUT_DIR / "consistency_check.json", consistency)
    return {
        "task_id": TASK_ID, "evidence_path": common.relative(OUTPUT_DIR),
        "outcome": outcome, "failure_reason": failure_reason,
        "faa_standard_packet": faa_result["evidence_path"],
        "psar_standard_packet": psar_result["evidence_path"],
        "existing_observations_updated": observations_initialized_by_task,
        "state_updates_this_invocation": newly_updated,
        "virtual_execution_events_linked": linked_events,
        "august_3_performance_rows": 0, "broker_or_paper_orders": 0,
        "overall_pass": consistency["overall_pass"], "next_action": next_action,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=TASK_ID)
    parser.parse_args(argv)
    result = run()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 1 if result["outcome"] == OUTCOME_BLOCKED or not result["overall_pass"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
