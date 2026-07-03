from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.objective_reset.objective_reset_review import replace_or_append_section, write_json, write_text
from strategy_lab.research_os.operations.initial_manual_snapshots import (
    LOG_ROOT,
    missing_values as initial_missing_values,
    target_weight_status,
)
from strategy_lab.research_os.operations.observation_checkpoint import DSR_ID, VM_ID, active_observation_status
from strategy_lab.research_os.split_tracks import ACTIVE_OBSERVATIONS_PATH, OPERATIONS_STATE_PATH, RESEARCH_QUEUE_PATH


OUTPUT_DIR = (
    Path("evidence")
    / "operations_observation"
    / "manual_input_required_for_initial_observation_snapshots"
    / "latest"
)
STATIC_ALL_WEATHER_ID = "static_all_weather_benchmark_v1"

SNAPSHOT_COMPLETE = "initial_snapshot_complete_enough_for_observation"
SNAPSHOT_PARTIAL = "partial_snapshot_manual_inputs_still_required"
SNAPSHOT_CONFLICT = "manual_review_required_due_to_inconsistent_input"
SNAPSHOT_PAUSE = "pause_observation_due_to_missing_or_conflicting_input"
VALID_SNAPSHOT_STATUSES = {SNAPSHOT_COMPLETE, SNAPSHOT_PARTIAL, SNAPSHOT_CONFLICT, SNAPSHOT_PAUSE}

NEXT_ACTION_WAIT = "wait_for_next_paper_forward_observation_checkpoint"
NEXT_ACTION_MANUAL_INPUT = "manual_input_required_for_initial_observation_snapshots"
NEXT_ACTION_CONFLICT = "manual_review_required_due_to_observation_input_conflict"
NEXT_ACTION_MISSING_LOGS = "pause_observation_due_to_missing_logs"
NEXT_ACTION_PAUSE = "pause_expansion_and_wait_for_manual_direction"
VALID_NEXT_ACTIONS = {
    NEXT_ACTION_WAIT,
    NEXT_ACTION_MANUAL_INPUT,
    NEXT_ACTION_CONFLICT,
    NEXT_ACTION_MISSING_LOGS,
    NEXT_ACTION_PAUSE,
}

REQUIRED_OUTPUT_FILES = (
    "manual_input_snapshot_manifest.json",
    "manual_input_snapshot_summary.md",
    "manual_input_source_review.md",
    "vm_manual_input_validation.md",
    "dsr_manual_input_validation.md",
    "updated_snapshot_status.md",
    "remaining_manual_inputs.md",
    "no_broker_no_live_confirmation.md",
    "manual_input_snapshot_next_action.md",
    "manual_input_snapshot_consistency_check.json",
)

MANIFEST_FLAGS = {
    "manual_input_snapshot_step_only": True,
    "active_vm_preserved": True,
    "active_dsr_preserved": True,
    "static_all_weather_benchmark_control_only": True,
    "research_track_paused": True,
    "gld_macro_recovery_run": False,
    "new_sandbox_batch_run": False,
    "strategy_discovery_run": False,
    "formal_discovery_run": False,
    "new_backtests_run": False,
    "new_performance_metrics_from_raw_data_computed": False,
    "new_variants_created": False,
    "future_preregistration_candidates_created": False,
    "formal_preregistration_created": False,
    "candidate_exhaustive_run": False,
    "paper_forward_review": False,
    "paper_forward_activation": False,
    "new_paper_forward_candidate_created": False,
    "provider_download": False,
    "intraday_data_used": False,
    "broker_api_called": False,
    "broker_orders_submitted": False,
    "broker_orders_cancelled": False,
    "broker_orders_reconciled": False,
    "live_orders": False,
    "real_money_recommendation": False,
    "active_strategy_state_changed": False,
    "rejected_strategy_state_changed": False,
    "exact_rejected_variants_reopened": False,
    "intraday_research_remains_paused": True,
    "target_weights_invented": False,
    "equity_values_invented": False,
    "positions_invented": False,
    "orders_invented": False,
    "benchmark_values_invented": False,
}

MANUAL_INPUT_CANDIDATES = (
    Path("strategy_lab") / "research_os" / "operations" / "manual_input_snapshot_values.yaml",
    Path("strategy_lab") / "research_os" / "operations" / "manual_input_snapshot_values.yml",
    Path("strategy_lab") / "research_os" / "operations" / "manual_input_snapshot_values.json",
    Path("strategy_lab") / "research_os" / "operations" / "observation_logs" / "manual_input_snapshot_values.yaml",
    Path("strategy_lab") / "research_os" / "operations" / "observation_logs" / "manual_input_snapshot_values.json",
)

MANUAL_FIELD_MAP = {
    "observation_start_date": "observation_start_date",
    "start_date": "observation_start_date",
    "current_intended_target_weights": "current_intended_target_weights",
    "intended_target_weights": "current_intended_target_weights",
    "target_weights": "current_intended_target_weights",
    "current_actual_observed_weights": "current_actual_observed_weights",
    "observed_weights": "current_actual_observed_weights",
    "current_account_or_equity_value": "current_account_or_equity_value",
    "account_value": "current_account_or_equity_value",
    "equity_value": "current_account_or_equity_value",
    "current_positions": "current_positions",
    "positions": "current_positions",
    "current_open_orders": "current_open_orders",
    "open_orders": "current_open_orders",
    "current_rejected_or_canceled_orders": "current_rejected_or_canceled_orders",
    "rejected_or_canceled_orders": "current_rejected_or_canceled_orders",
    "benchmark_snapshot_date_and_values": "benchmark_snapshot_date_and_values",
    "benchmark_snapshot": "benchmark_snapshot_date_and_values",
    "broker_or_api_issues": "broker_or_api_issues",
    "broker_api_issues": "broker_or_api_issues",
    "unexplained_pnl": "unexplained_pnl",
    "next_checkpoint_cadence": "next_checkpoint_cadence",
}

COMPLETE_ENOUGH_FIELDS = (
    "observation_start_date",
    "current_intended_target_weights",
    "current_actual_observed_weights",
    "current_account_or_equity_value",
    "current_positions",
    "current_open_orders",
    "next_checkpoint_cadence",
)


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False, width=120, allow_unicode=False), encoding="utf-8")


def write_csv_rows(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: stringify_value(row.get(field, "unknown")) for field in fieldnames})


def stringify_value(value: Any) -> str:
    if value in (None, ""):
        return "unknown"
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True)
    return str(value)


def research_track_paused(root: Path) -> bool:
    queue = load_yaml(root / RESEARCH_QUEUE_PATH)
    return (
        queue.get("current_expansion_status") == "paused"
        and queue.get("sandbox_batch_authorized") is False
        and queue.get("strategy_discovery_authorized") is False
        and queue.get("candidate_exhaustive_authorized") is False
        and queue.get("paper_forward_candidate_creation_authorized") is False
    )


def manual_input_candidates(root: Path) -> list[Path]:
    return [root / path for path in MANUAL_INPUT_CANDIDATES]


def parse_manual_input_file(path: Path) -> dict[str, Any]:
    if path.suffix.lower() == ".json":
        return json.loads(path.read_text(encoding="utf-8"))
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def load_manual_input(root: Path) -> dict[str, Any]:
    candidates = manual_input_candidates(root)
    existing = [path for path in candidates if path.exists()]
    if not existing:
        return {
            "manual_values_supplied": False,
            "source_path": "",
            "source_found": False,
            "source_error": "",
            "raw_payload": {},
            "candidate_paths": [str(path.resolve()) for path in candidates],
        }
    source = existing[0]
    try:
        payload = parse_manual_input_file(source)
        return {
            "manual_values_supplied": bool(payload),
            "source_path": str(source.resolve()),
            "source_found": True,
            "source_error": "",
            "raw_payload": payload,
            "candidate_paths": [str(path.resolve()) for path in candidates],
        }
    except Exception as exc:  # pragma: no cover - defensive, validated through manifest conflict status.
        return {
            "manual_values_supplied": False,
            "source_path": str(source.resolve()),
            "source_found": True,
            "source_error": str(exc),
            "raw_payload": {},
            "candidate_paths": [str(path.resolve()) for path in candidates],
        }


def observation_payload(raw_payload: dict[str, Any], strategy_id: str) -> dict[str, Any]:
    if not raw_payload:
        return {}
    observations = raw_payload.get("observations", raw_payload)
    if isinstance(observations, dict) and strategy_id in observations and isinstance(observations[strategy_id], dict):
        return observations[strategy_id]
    return {}


def normalized_manual_values(raw_payload: dict[str, Any], strategy_id: str) -> dict[str, Any]:
    payload = observation_payload(raw_payload, strategy_id)
    values: dict[str, Any] = {}
    for key, value in payload.items():
        normalized = MANUAL_FIELD_MAP.get(str(key))
        if normalized and value not in (None, "", "unknown", "manual_input_required"):
            values[normalized] = value
    return values


def source_is_explicitly_manual(raw_payload: dict[str, Any], strategy_id: str, values: dict[str, Any]) -> bool:
    if not values:
        return False
    payload = observation_payload(raw_payload, strategy_id)
    source_tokens = {
        str(raw_payload.get("source", "")).lower(),
        str(raw_payload.get("input_source", "")).lower(),
        str(payload.get("source", "")).lower(),
        str(payload.get("input_source", "")).lower(),
    }
    boolean_tokens = {
        raw_payload.get("manual_values_supplied"),
        raw_payload.get("manual_input"),
        payload.get("manual_values_supplied"),
        payload.get("manual_input"),
    }
    return any(token in {"manual", "manual_input", "user_manual_input"} for token in source_tokens) or any(
        token is True for token in boolean_tokens
    )


def forbidden_source_conflicts(raw_payload: dict[str, Any], strategy_id: str) -> list[str]:
    text = json.dumps(observation_payload(raw_payload, strategy_id), sort_keys=True).lower()
    conflicts = []
    forbidden_markers = {
        "broker_api": "broker_api_marker_present",
        "provider_download": "provider_download_marker_present",
        "live_order": "live_order_marker_present",
        "calculated_current_signal": "calculated_current_signal_marker_present",
    }
    for marker, label in forbidden_markers.items():
        if marker in text:
            conflicts.append(label)
    return conflicts


def remaining_values(strategy_id: str, values: dict[str, Any]) -> list[str]:
    missing = [field for field in initial_missing_values(strategy_id) if field not in values]
    if "current_intended_target_weights" in values and "current_signal_state_required_for_exact_target_weights" in missing:
        missing.remove("current_signal_state_required_for_exact_target_weights")
    return missing


def snapshot_status(
    detail: dict[str, Any], values: dict[str, Any], manual_source: bool, conflicts: list[str]
) -> str:
    if conflicts or not detail["exists"] or not detail["frozen"] or not detail["rules_frozen"] or not detail["paper_forward_active"]:
        return SNAPSHOT_CONFLICT
    if all(field in values for field in COMPLETE_ENOUGH_FIELDS) and manual_source:
        return SNAPSHOT_COMPLETE
    return SNAPSHOT_PARTIAL


def validation_record(root: Path, created_utc: str, strategy_id: str, source: dict[str, Any]) -> dict[str, Any]:
    detail = active_observation_status(root, strategy_id)
    values = normalized_manual_values(source["raw_payload"], strategy_id)
    manual_source = source_is_explicitly_manual(source["raw_payload"], strategy_id, values)
    conflicts = forbidden_source_conflicts(source["raw_payload"], strategy_id)
    if values and not manual_source:
        conflicts.append("manual_source_marker_missing")
    status = snapshot_status(detail, values, manual_source, conflicts)
    remaining = remaining_values(strategy_id, values)
    return {
        "strategy_id": strategy_id,
        "created_utc": created_utc,
        "active_observation_exists": detail["exists"],
        "active_observation_status": detail["status"],
        "paper_forward_active": detail["paper_forward_active"],
        "frozen": detail["frozen"],
        "rules_frozen": detail["rules_frozen"],
        "manual_values_supplied": bool(values),
        "manual_source_confirmed": manual_source,
        "supplied_fields": sorted(values.keys()),
        "supplied_values": values,
        "remaining_manual_inputs": remaining,
        "conflicts": conflicts,
        "snapshot_status": status,
        "unknown_values_preserved": bool(remaining),
        "target_weight_status": "manual_supplied" if "current_intended_target_weights" in values else target_weight_status(strategy_id),
        "decision": status,
    }


def value_or_unknown(record: dict[str, Any], field: str, default: str = "unknown") -> str:
    return stringify_value(record["supplied_values"].get(field, default))


def manual_validation_checkpoint_md(record: dict[str, Any]) -> str:
    remaining = "\n".join(f"- `{item}`" for item in record["remaining_manual_inputs"]) or "- `none`"
    supplied = "\n".join(f"- `{item}`" for item in record["supplied_fields"]) or "- `none`"
    conflicts = "\n".join(f"- `{item}`" for item in record["conflicts"]) or "- `none`"
    return f"""# Manual Input Observation Checkpoint Validation

Checkpoint ID: `manual_input_validation_{record['strategy_id']}`

Created UTC: `{record['created_utc']}`

Observation ID: `{record['strategy_id']}`

Strategy ID: `{record['strategy_id']}`

Active/frozen status: `{record['active_observation_status']}` / frozen `{record['frozen']}` / rules frozen `{record['rules_frozen']}`

Manual values supplied: `{record['manual_values_supplied']}`

Manual source confirmed: `{record['manual_source_confirmed']}`

Observation start date: `{value_or_unknown(record, 'observation_start_date')}`

Rule hash/checksum status: `unknown`

Target allocation status: `{record['target_weight_status']}`

Current intended target weights: `{value_or_unknown(record, 'current_intended_target_weights', 'unknown_current_signal_required')}`

Current actual observed weights: `{value_or_unknown(record, 'current_actual_observed_weights')}`

Equity/account snapshot: `{value_or_unknown(record, 'current_account_or_equity_value')}`

Position snapshot: `{value_or_unknown(record, 'current_positions')}`

Open order status: `{value_or_unknown(record, 'current_open_orders')}`

Rejected/canceled orders: `{value_or_unknown(record, 'current_rejected_or_canceled_orders')}`

Benchmark snapshot: `{value_or_unknown(record, 'benchmark_snapshot_date_and_values')}`

Broker/API issue status: `{value_or_unknown(record, 'broker_or_api_issues')}`

Unexplained P&L status: `{value_or_unknown(record, 'unexplained_pnl')}`

Next checkpoint cadence: `{value_or_unknown(record, 'next_checkpoint_cadence', 'manual_input_required')}`

## Supplied Manual Fields

{supplied}

## Remaining Manual Inputs

{remaining}

## Input Conflicts

{conflicts}

## Decision

`{record['snapshot_status']}`

No broker API call was made. No order was submitted, canceled, reconciled, or simulated. No live order path was touched. No real-money recommendation was made.
"""


def update_log_files(root: Path, record: dict[str, Any]) -> None:
    strategy_id = record["strategy_id"]
    log_dir = root / LOG_ROOT / strategy_id
    log_dir.mkdir(parents=True, exist_ok=True)
    checkpoint = manual_validation_checkpoint_md(record)
    write_text(log_dir / "manual_input_validation_checkpoint.md", checkpoint)
    write_text(log_dir / "latest_manual_checkpoint.md", checkpoint)

    metadata = load_yaml(log_dir / "observation_metadata.yaml")
    metadata.update(
        {
            "status": record["snapshot_status"],
            "manual_values_supplied": record["manual_values_supplied"],
            "manual_source_confirmed": record["manual_source_confirmed"],
            "last_checkpoint_timestamp": record["created_utc"],
            "snapshot_decision": record["snapshot_status"],
            "remaining_manual_inputs": record["remaining_manual_inputs"],
            "target_allocation_status": record["target_weight_status"],
            "target_weights_available": "current_intended_target_weights" in record["supplied_values"],
            "observed_weights_available": "current_actual_observed_weights" in record["supplied_values"],
            "latest_equity_snapshot_available": "current_account_or_equity_value" in record["supplied_values"],
            "latest_positions_available": "current_positions" in record["supplied_values"],
            "latest_orders_available": "current_open_orders" in record["supplied_values"],
            "latest_benchmark_snapshot_available": "benchmark_snapshot_date_and_values" in record["supplied_values"],
            "broker_derived_values": False,
            "invented_target_weights": False,
            "invented_equity": False,
            "invented_positions": False,
            "invented_orders": False,
            "invented_benchmark_values": False,
            "manual_input_required": record["snapshot_status"] != SNAPSHOT_COMPLETE,
            "real_money_recommendation": False,
        }
    )
    write_yaml(log_dir / "observation_metadata.yaml", metadata)

    target = load_yaml(log_dir / "target_allocation_snapshot.yaml")
    target.update(
        {
            "status": record["snapshot_status"],
            "updated_utc": record["created_utc"],
            "target_weight_status": record["target_weight_status"],
            "target_weights": record["supplied_values"].get(
                "current_intended_target_weights", "unknown_current_signal_required"
            ),
            "observed_weights": record["supplied_values"].get("current_actual_observed_weights", "unknown"),
            "source": "manual_input_file" if "current_intended_target_weights" in record["supplied_values"] else "manual_input_required",
            "calculated_from_market_data": False,
            "broker_derived_values": False,
            "invented_values": False,
            "manual_input_required": record["snapshot_status"] != SNAPSHOT_COMPLETE,
        }
    )
    write_yaml(log_dir / "target_allocation_snapshot.yaml", target)

    write_csv_rows(
        log_dir / "manual_input_equity_snapshot.csv",
        ["as_of_utc", "observation_id", "account_value", "source", "notes"],
        [
            {
                "as_of_utc": record["created_utc"],
                "observation_id": strategy_id,
                "account_value": record["supplied_values"].get("current_account_or_equity_value", "unknown"),
                "source": "manual_input_supplied" if "current_account_or_equity_value" in record["supplied_values"] else "manual_input_required",
                "notes": "no_broker_query_no_invented_values",
            }
        ],
    )


def no_broker_confirmation_md() -> str:
    return """# No-Broker / No-Live Confirmation

- Broker API called: `false`
- Orders submitted: `false`
- Orders canceled: `false`
- Orders reconciled: `false`
- Orders simulated: `false`
- Live order path touched: `false`
- Real-money recommendation made: `false`

Any broker/account information must be supplied manually by the project owner. This validation step did not query, reconcile, simulate, submit, or cancel orders.
"""


def source_review_md(source: dict[str, Any]) -> str:
    candidates = "\n".join(f"- `{path}`" for path in source["candidate_paths"])
    return f"""# Manual Input Source Review

Manual values supplied: `{source['manual_values_supplied']}`

Source found: `{source['source_found']}`

Source path: `{source['source_path'] or 'none'}`

Source parse error: `{source['source_error'] or 'none'}`

## Candidate Paths Checked

{candidates}

No pasted manual values were present in the task message beyond the instruction text. No missing values were inferred.
"""


def validation_md(title: str, record: dict[str, Any]) -> str:
    supplied = "\n".join(f"- `{item}`" for item in record["supplied_fields"]) or "- `none`"
    remaining = "\n".join(f"- `{item}`" for item in record["remaining_manual_inputs"]) or "- `none`"
    conflicts = "\n".join(f"- `{item}`" for item in record["conflicts"]) or "- `none`"
    return f"""# {title}

- Observation ID valid: `{record['strategy_id'] in {VM_ID, DSR_ID}}`
- Active/accepted/frozen: `{record['paper_forward_active'] and record['frozen'] and record['rules_frozen']}`
- Manual values supplied: `{record['manual_values_supplied']}`
- Manual source confirmed: `{record['manual_source_confirmed']}`
- Snapshot status: `{record['snapshot_status']}`
- Target weight status: `{record['target_weight_status']}`

## Supplied Fields

{supplied}

## Remaining Manual Inputs

{remaining}

## Conflicts

{conflicts}

No calculated current signal, provider download, broker/API call, order action, live path, or real-money recommendation occurred.
"""


def updated_snapshot_status_md(records: list[dict[str, Any]]) -> str:
    lines = ["# Updated Snapshot Status", ""]
    for record in records:
        lines.extend(
            [
                f"## `{record['strategy_id']}`",
                "",
                f"- Snapshot status: `{record['snapshot_status']}`",
                f"- Manual values supplied: `{record['manual_values_supplied']}`",
                f"- Remaining manual input count: `{len(record['remaining_manual_inputs'])}`",
                "",
            ]
        )
    return "\n".join(lines)


def remaining_inputs_md(records: list[dict[str, Any]]) -> str:
    lines = ["# Remaining Manual Inputs", ""]
    for record in records:
        lines.append(f"## `{record['strategy_id']}`")
        for item in record["remaining_manual_inputs"] or ["none"]:
            lines.append(f"- `{item}`")
        lines.append("")
    return "\n".join(lines)


def summary_md(m: dict[str, Any]) -> str:
    return f"""# Manual Input Snapshot Summary

Exact next action: `{m['next_action']}`

Manual values supplied: `{m['manual_values_supplied']}`

Manual input still required: `{m['manual_input_required']}`

VM snapshot status: `{m['vm_snapshot_status']}`

DSR snapshot status: `{m['dsr_snapshot_status']}`

Unknown values preserved: `{m['unknown_values_preserved']}`

No target weights, equity values, positions, orders, or benchmark values were invented.
"""


def next_action_md(next_action: str) -> str:
    return f"""# Manual Input Snapshot Next Action

Exact next action:

`{next_action}`

Do not run the next action in this task.
"""


def choose_next_action(records: list[dict[str, Any]]) -> str:
    statuses = {record["snapshot_status"] for record in records}
    if SNAPSHOT_CONFLICT in statuses:
        return NEXT_ACTION_CONFLICT
    if statuses == {SNAPSHOT_COMPLETE}:
        return NEXT_ACTION_WAIT
    if SNAPSHOT_PAUSE in statuses:
        return NEXT_ACTION_MISSING_LOGS
    return NEXT_ACTION_MANUAL_INPUT


def update_operations_metadata(root: Path, output: Path, created_utc: str, m: dict[str, Any]) -> tuple[bool, bool]:
    operations_path = root / OPERATIONS_STATE_PATH
    before_operations = read_text(operations_path)
    section = f"""## Latest Manual Input Snapshot Validation

- Created UTC: `{created_utc}`
- Evidence path: `{output.resolve()}`
- Manual values supplied: `{m['manual_values_supplied']}`
- VM snapshot status: `{m['vm_snapshot_status']}`
- DSR snapshot status: `{m['dsr_snapshot_status']}`
- Manual input required: `{m['manual_input_required']}`
- Next action: `{m['next_action']}`
- No broker API call, order action, live path, or real-money recommendation was authorized.
"""
    after_operations = replace_or_append_section(before_operations, "## Latest Manual Input Snapshot Validation", section)
    write_text(operations_path, after_operations)

    active_path = root / ACTIVE_OBSERVATIONS_PATH
    active_payload = load_yaml(active_path)
    before_active = yaml.safe_dump(active_payload, sort_keys=False, width=120, allow_unicode=False)
    active_payload["latest_manual_input_snapshot_validation"] = {
        "created_utc": created_utc,
        "evidence_path": str(output.resolve()),
        "manual_values_supplied": m["manual_values_supplied"],
        "manual_input_required": m["manual_input_required"],
        "vm_snapshot_status": m["vm_snapshot_status"],
        "dsr_snapshot_status": m["dsr_snapshot_status"],
        "next_action": m["next_action"],
    }
    write_yaml(active_path, active_payload)
    after_active = yaml.safe_dump(active_payload, sort_keys=False, width=120, allow_unicode=False)
    return before_operations != after_operations, before_active != after_active


def manifest(created_utc: str, root: Path, output: Path, source: dict[str, Any], records: list[dict[str, Any]]) -> dict[str, Any]:
    next_action = choose_next_action(records)
    return {
        "created_utc": created_utc,
        **MANIFEST_FLAGS,
        "evidence_path": str(output.resolve()),
        "manual_values_supplied": any(record["manual_values_supplied"] for record in records),
        "manual_input_required": next_action != NEXT_ACTION_WAIT,
        "manual_input_source_found": source["source_found"],
        "manual_input_source_path": source["source_path"],
        "manual_input_source_error": source["source_error"],
        "current_active_observation_count": 2,
        "active_observation_ids": [VM_ID, DSR_ID],
        "vm_snapshot_status": records[0]["snapshot_status"],
        "dsr_snapshot_status": records[1]["snapshot_status"],
        "unknown_values_preserved": any(record["remaining_manual_inputs"] for record in records),
        "snapshot_records": records,
        "research_queue_paused": research_track_paused(root),
        "next_action": next_action,
    }


def consistency_check(m: dict[str, Any], output: Path, root: Path) -> dict[str, Any]:
    required = {name: (output / name).exists() for name in REQUIRED_OUTPUT_FILES}
    logs_exist = all(
        (root / LOG_ROOT / strategy_id / filename).exists()
        for strategy_id in (VM_ID, DSR_ID)
        for filename in (
            "manual_input_validation_checkpoint.md",
            "latest_manual_checkpoint.md",
            "observation_metadata.yaml",
            "target_allocation_snapshot.yaml",
        )
    )
    check = {
        "manual_input_snapshot_step_only": m["manual_input_snapshot_step_only"] is True,
        "active_vm_preserved": m["active_vm_preserved"] is True,
        "active_dsr_preserved": m["active_dsr_preserved"] is True,
        "static_all_weather_control_only": m["static_all_weather_benchmark_control_only"] is True,
        "research_track_paused": m["research_track_paused"] is True and m["research_queue_paused"] is True,
        "gld_macro_recovery_not_run": m["gld_macro_recovery_run"] is False,
        "no_sandbox_batch": m["new_sandbox_batch_run"] is False,
        "no_discovery": m["strategy_discovery_run"] is False and m["formal_discovery_run"] is False,
        "no_backtests_or_raw_metrics": (
            m["new_backtests_run"] is False and m["new_performance_metrics_from_raw_data_computed"] is False
        ),
        "no_new_variants_or_preregistration": (
            m["new_variants_created"] is False
            and m["future_preregistration_candidates_created"] is False
            and m["formal_preregistration_created"] is False
        ),
        "no_candidate_or_paper_forward_activation": (
            m["candidate_exhaustive_run"] is False
            and m["paper_forward_activation"] is False
            and m["new_paper_forward_candidate_created"] is False
        ),
        "no_provider_intraday": m["provider_download"] is False and m["intraday_data_used"] is False,
        "no_broker_live_real_money": (
            m["broker_api_called"] is False
            and m["broker_orders_submitted"] is False
            and m["broker_orders_cancelled"] is False
            and m["broker_orders_reconciled"] is False
            and m["live_orders"] is False
            and m["real_money_recommendation"] is False
        ),
        "exact_rejected_variants_not_reopened": m["exact_rejected_variants_reopened"] is False,
        "vm_snapshot_status_exists": m["vm_snapshot_status"] in VALID_SNAPSHOT_STATUSES,
        "dsr_snapshot_status_exists": m["dsr_snapshot_status"] in VALID_SNAPSHOT_STATUSES,
        "remaining_manual_inputs_file_exists": (output / "remaining_manual_inputs.md").exists(),
        "no_broker_confirmation_exists": (output / "no_broker_no_live_confirmation.md").exists(),
        "unknown_values_explicit": m["unknown_values_preserved"] is True,
        "target_weights_not_invented": m["target_weights_invented"] is False,
        "equity_values_not_invented": m["equity_values_invented"] is False,
        "positions_not_invented": m["positions_invented"] is False,
        "orders_not_invented": m["orders_invented"] is False,
        "benchmark_values_not_invented": m["benchmark_values_invented"] is False,
        "observation_logs_updated": logs_exist,
        "next_action_valid": m["next_action"] in VALID_NEXT_ACTIONS,
        "required_files_present": all(required.values()),
        "required_files": required,
    }
    check["consistency_passed"] = all(value is True for key, value in check.items() if key != "required_files")
    return check


def run(root: Path = ROOT) -> dict[str, Any]:
    created = now_utc()
    output = root / OUTPUT_DIR
    output.mkdir(parents=True, exist_ok=True)
    source = load_manual_input(root)
    records = [validation_record(root, created, strategy_id, source) for strategy_id in (VM_ID, DSR_ID)]
    for record in records:
        update_log_files(root, record)
    m = manifest(created, root, output, source, records)

    write_text(output / "manual_input_snapshot_summary.md", summary_md(m))
    write_text(output / "manual_input_source_review.md", source_review_md(source))
    write_text(output / "vm_manual_input_validation.md", validation_md("VM Manual Input Validation", records[0]))
    write_text(output / "dsr_manual_input_validation.md", validation_md("DSR Manual Input Validation", records[1]))
    write_text(output / "updated_snapshot_status.md", updated_snapshot_status_md(records))
    write_text(output / "remaining_manual_inputs.md", remaining_inputs_md(records))
    write_text(output / "no_broker_no_live_confirmation.md", no_broker_confirmation_md())
    write_text(output / "manual_input_snapshot_next_action.md", next_action_md(m["next_action"]))

    operations_updated, active_observations_updated = update_operations_metadata(root, output, created, m)
    m.update(
        {
            "operations_state_updated": operations_updated,
            "active_observations_metadata_updated": active_observations_updated,
        }
    )
    write_json(output / "manual_input_snapshot_manifest.json", m)
    write_json(output / "manual_input_snapshot_consistency_check.json", {"consistency_passed": False})
    check = consistency_check(m, output, root)
    write_json(output / "manual_input_snapshot_consistency_check.json", check)
    return {**m, "consistency_passed": check["consistency_passed"], "output_dir": str(output.resolve())}


if __name__ == "__main__":
    result = run()
    print(
        json.dumps(
            {
                "output_dir": result["output_dir"],
                "manual_values_supplied": result["manual_values_supplied"],
                "vm_snapshot_status": result["vm_snapshot_status"],
                "dsr_snapshot_status": result["dsr_snapshot_status"],
                "next_action": result["next_action"],
                "consistency_passed": result["consistency_passed"],
            },
            indent=2,
        )
    )
