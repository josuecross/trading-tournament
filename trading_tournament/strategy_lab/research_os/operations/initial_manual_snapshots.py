from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.objective_reset.objective_reset_review import replace_or_append_section, write_json, write_text
from strategy_lab.research_os.operations.manual_observation_logs_review import LOG_ROOT
from strategy_lab.research_os.operations.observation_checkpoint import DSR_ID, VM_ID, active_observation_status
from strategy_lab.research_os.split_tracks import ACTIVE_OBSERVATIONS_PATH, OPERATIONS_STATE_PATH, RESEARCH_QUEUE_PATH


OUTPUT_DIR = Path("evidence") / "operations_observation" / "create_initial_manual_observation_snapshots" / "latest"
STATIC_ALL_WEATHER_ID = "static_all_weather_benchmark_v1"

NEXT_ACTION_MANUAL_INPUT = "manual_input_required_for_initial_observation_snapshots"
NEXT_ACTION_WAIT = "wait_for_next_paper_forward_observation_checkpoint"
NEXT_ACTION_PAUSE_LOGS = "pause_observation_due_to_missing_logs"
NEXT_ACTION_REVIEW_LOGS = "manual_review_required_for_observation_logs"
NEXT_ACTION_PAUSE = "pause_expansion_and_wait_for_manual_direction"
VALID_NEXT_ACTIONS = {
    NEXT_ACTION_MANUAL_INPUT,
    NEXT_ACTION_WAIT,
    NEXT_ACTION_PAUSE_LOGS,
    NEXT_ACTION_REVIEW_LOGS,
    NEXT_ACTION_PAUSE,
}

REQUIRED_OUTPUT_FILES = (
    "initial_manual_snapshots_manifest.json",
    "initial_manual_snapshots_summary.md",
    "vm_initial_snapshot_review.md",
    "dsr_initial_snapshot_review.md",
    "manual_input_checklist.md",
    "missing_values_after_initial_snapshot.md",
    "target_weight_status.md",
    "no_broker_no_live_confirmation.md",
    "initial_manual_snapshots_next_action.md",
    "initial_manual_snapshots_consistency_check.json",
)

MANIFEST_FLAGS = {
    "initial_manual_snapshot_step_only": True,
    "manual_input_required": True,
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
            writer.writerow({field: row.get(field, "unknown") or "unknown" for field in fieldnames})


def research_track_paused(root: Path) -> bool:
    queue = load_yaml(root / RESEARCH_QUEUE_PATH)
    return (
        queue.get("current_expansion_status") == "paused"
        and queue.get("sandbox_batch_authorized") is False
        and queue.get("strategy_discovery_authorized") is False
        and queue.get("candidate_exhaustive_authorized") is False
        and queue.get("paper_forward_candidate_creation_authorized") is False
    )


def target_weight_status(strategy_id: str) -> str:
    if strategy_id in {VM_ID, DSR_ID}:
        return "unknown_current_signal_required"
    return "unknown"


def initial_checkpoint_md(created_utc: str, strategy_id: str, detail: dict[str, Any]) -> str:
    missing = "\n".join(f"- `{item}`" for item in missing_values(strategy_id))
    return f"""# Initial Manual Observation Checkpoint

Checkpoint ID: `initial_manual_snapshot_{strategy_id}`

Created UTC: `{created_utc}`

Observation ID: `{strategy_id}`

Strategy ID: `{strategy_id}`

Active/frozen status: `{detail['status']}` / frozen `{detail['frozen']}` / rules frozen `{detail['rules_frozen']}`

Frozen rules reference: `frozen_rules_reference.md`

Rule hash/checksum status: `unknown`

Start date status: `unknown`

Target allocation status: `{target_weight_status(strategy_id)}`

Observed allocation status: `unknown`

Equity/account snapshot status: `unknown`

Position snapshot status: `unknown`

Order snapshot status: `unknown`

Benchmark snapshot status: `unknown`

Open order status: `unknown`

Stale position check status: `unknown`

Broker/API issue status: `unknown`

Unexplained P&L status: `unknown`

## Missing Evidence

{missing}

## Decision

`manual_input_required_before_clean_observation`

No broker API call was made. No order was submitted, canceled, reconciled, or simulated. No live order path was touched. No real-money recommendation was made.
"""


def metadata_payload(created_utc: str, strategy_id: str, detail: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "initial_manual_snapshot_created_manual_input_required",
        "created_utc": created_utc,
        "observation_id": strategy_id,
        "strategy_id": strategy_id,
        "active_observation_source_path": detail["path"],
        "active_observation_file_exists": detail["exists"],
        "active_observation_status": detail["status"],
        "paper_forward_active": detail["paper_forward_active"],
        "frozen": detail["frozen"],
        "rules_frozen": detail["rules_frozen"],
        "start_date": "unknown",
        "rule_hash_or_checksum": "unknown",
        "last_checkpoint_timestamp": created_utc,
        "next_checkpoint_due_date": "manual_input_required",
        "checkpoint_cadence": "manual_input_required",
        "target_allocation_status": target_weight_status(strategy_id),
        "target_weights_available": False,
        "observed_weights_available": False,
        "latest_equity_snapshot_available": False,
        "latest_positions_available": False,
        "latest_orders_available": False,
        "latest_benchmark_snapshot_available": False,
        "broker_derived_values": False,
        "invented_target_weights": False,
        "invented_equity": False,
        "invented_positions": False,
        "invented_orders": False,
        "invented_benchmark_values": False,
        "manual_input_required": True,
        "real_money_recommendation": False,
    }


def target_allocation_payload(created_utc: str, strategy_id: str) -> dict[str, Any]:
    return {
        "status": "initial_manual_snapshot_created_manual_input_required",
        "created_utc": created_utc,
        "observation_id": strategy_id,
        "strategy_id": strategy_id,
        "target_weight_status": target_weight_status(strategy_id),
        "target_weights": "unknown_current_signal_required",
        "observed_weights": "unknown",
        "cash_weight": "unknown",
        "source": "frozen_rules_require_current_signal_or_manual_input",
        "calculated_from_market_data": False,
        "broker_derived_values": False,
        "invented_values": False,
        "manual_input_required": True,
    }


def missing_values(strategy_id: str) -> list[str]:
    base = [
        "observation_start_date",
        "rule_hash_or_checksum",
        "current_intended_target_weights",
        "current_actual_observed_weights",
        "current_account_or_equity_value",
        "current_positions",
        "current_open_orders",
        "current_rejected_or_canceled_orders",
        "benchmark_snapshot_date_and_values",
        "broker_or_api_issues",
        "unexplained_pnl",
        "next_checkpoint_cadence",
    ]
    if strategy_id in {VM_ID, DSR_ID}:
        base.append("current_signal_state_required_for_exact_target_weights")
    return base


def write_initial_snapshots(root: Path, created_utc: str, strategy_id: str) -> dict[str, Any]:
    detail = active_observation_status(root, strategy_id)
    log_dir = root / LOG_ROOT / strategy_id
    log_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "latest_manual_checkpoint": log_dir / "latest_manual_checkpoint.md",
        "initial_manual_checkpoint": log_dir / "initial_manual_checkpoint.md",
        "observation_metadata": log_dir / "observation_metadata.yaml",
        "target_allocation_snapshot": log_dir / "target_allocation_snapshot.yaml",
        "initial_position_snapshot": log_dir / "initial_position_snapshot.csv",
        "initial_order_snapshot": log_dir / "initial_order_snapshot.csv",
        "initial_equity_snapshot": log_dir / "initial_equity_snapshot.csv",
        "initial_benchmark_snapshot": log_dir / "initial_benchmark_snapshot.csv",
        "issues_log": log_dir / "issues_log.md",
        "notes": log_dir / "notes.md",
    }
    checkpoint = initial_checkpoint_md(created_utc, strategy_id, detail)
    write_text(files["latest_manual_checkpoint"], checkpoint)
    write_text(files["initial_manual_checkpoint"], checkpoint)
    write_yaml(files["observation_metadata"], metadata_payload(created_utc, strategy_id, detail))
    write_yaml(files["target_allocation_snapshot"], target_allocation_payload(created_utc, strategy_id))
    write_csv_rows(
        files["initial_position_snapshot"],
        ["as_of_utc", "observation_id", "symbol", "quantity", "market_value", "source", "notes"],
        [
            {
                "as_of_utc": created_utc,
                "observation_id": strategy_id,
                "symbol": "unknown",
                "quantity": "unknown",
                "market_value": "unknown",
                "source": "manual_input_required",
                "notes": "positions_not_available_no_broker_query",
            }
        ],
    )
    write_csv_rows(
        files["initial_order_snapshot"],
        ["as_of_utc", "observation_id", "order_id", "symbol", "side", "quantity", "status", "source", "notes"],
        [
            {
                "as_of_utc": created_utc,
                "observation_id": strategy_id,
                "order_id": "unknown",
                "symbol": "unknown",
                "side": "unknown",
                "quantity": "unknown",
                "status": "unknown",
                "source": "manual_input_required",
                "notes": "orders_not_available_no_broker_query",
            }
        ],
    )
    write_csv_rows(
        files["initial_equity_snapshot"],
        ["as_of_utc", "observation_id", "account_value", "cash_value", "source", "notes"],
        [
            {
                "as_of_utc": created_utc,
                "observation_id": strategy_id,
                "account_value": "unknown",
                "cash_value": "unknown",
                "source": "manual_input_required",
                "notes": "equity_not_available_no_broker_query",
            }
        ],
    )
    write_csv_rows(
        files["initial_benchmark_snapshot"],
        ["as_of_utc", "observation_id", "benchmark_id", "level_or_value", "source", "notes"],
        [
            {
                "as_of_utc": created_utc,
                "observation_id": strategy_id,
                "benchmark_id": "unknown",
                "level_or_value": "unknown",
                "source": "manual_input_required",
                "notes": "benchmark_values_not_available_no_data_download",
            }
        ],
    )
    write_text(
        files["issues_log"],
        f"""# Issues Log

Status: `initial_manual_snapshot_created_manual_input_required`

Created UTC: `{created_utc}`

- Broker/API issues: `unknown`
- Missing logs: `manual_input_required`
- Unexplained P&L: `unknown`

No broker API call was made and no order action occurred.
""",
    )
    write_text(
        files["notes"],
        f"""# Notes

Status: `initial_manual_snapshot_created_manual_input_required`

Created UTC: `{created_utc}`

Manual input is required before observation can be considered clean. No operational values are invented in this snapshot.
""",
    )
    return {
        "strategy_id": strategy_id,
        "snapshot_created": True,
        "decision": "manual_input_required_before_clean_observation",
        "target_weight_status": target_weight_status(strategy_id),
        "missing_values": missing_values(strategy_id),
        "files": {key: str(path.resolve()) for key, path in files.items()},
    }


def manual_input_checklist_md(snapshot_rows: list[dict[str, Any]]) -> str:
    lines = ["# Manual Input Checklist", ""]
    requests = [
        "Observation start date",
        "Current intended target weights",
        "Current actual observed weights",
        "Current account/equity value if applicable",
        "Current positions if applicable",
        "Current open orders if any",
        "Current rejected/canceled orders if any",
        "Benchmark snapshot date and values if available",
        "Any broker/API issues",
        "Any unexplained P&L",
        "Next checkpoint cadence",
    ]
    for row in snapshot_rows:
        lines.append(f"## `{row['strategy_id']}`")
        for item in requests:
            lines.append(f"- {item}: `manual_input_required`")
        lines.append("")
    return "\n".join(lines)


def missing_values_md(snapshot_rows: list[dict[str, Any]]) -> str:
    lines = ["# Missing Values After Initial Snapshot", ""]
    for row in snapshot_rows:
        lines.append(f"## `{row['strategy_id']}`")
        for value in row["missing_values"]:
            lines.append(f"- `{value}`")
        lines.append("")
    return "\n".join(lines)


def target_weight_status_md(snapshot_rows: list[dict[str, Any]]) -> str:
    lines = ["# Target Weight Status", ""]
    for row in snapshot_rows:
        lines.extend(
            [
                f"## `{row['strategy_id']}`",
                "",
                f"- Target weight status: `{row['target_weight_status']}`",
                "- Exact target weights were not invented.",
                "- Current signal calculation was not performed.",
                "- Prices were not downloaded.",
                "- Broker data was not queried.",
                "",
            ]
        )
    return "\n".join(lines)


def no_broker_confirmation_md() -> str:
    return """# No-Broker / No-Live Confirmation

- Broker API called: `false`
- Orders submitted: `false`
- Orders canceled: `false`
- Orders reconciled: `false`
- Orders simulated: `false`
- Live order path touched: `false`
- Real-money recommendation made: `false`

If account or broker information is needed, it must be entered manually by the project owner in a future checkpoint file.
"""


def snapshot_review_md(title: str, row: dict[str, Any]) -> str:
    files = "\n".join(f"- `{name}`: `{path}`" for name, path in row["files"].items())
    missing = "\n".join(f"- `{value}`" for value in row["missing_values"])
    return f"""# {title}

- Snapshot created: `{row['snapshot_created']}`
- Decision: `{row['decision']}`
- Target weight status: `{row['target_weight_status']}`

## Created / Updated Files

{files}

## Missing Values

{missing}
"""


def summary_md(m: dict[str, Any]) -> str:
    return f"""# Initial Manual Observation Snapshots Summary

Exact next action: `{m['next_action']}`

Manual input required: `{m['manual_input_required']}`

VM initial snapshot created: `{m['vm_initial_snapshot_created']}`

DSR initial snapshot created: `{m['dsr_initial_snapshot_created']}`

Unknown values preserved: `{m['unknown_values_preserved']}`

No target weights, equity values, positions, orders, or benchmark values were invented.
"""


def next_action_md(next_action: str) -> str:
    return f"""# Initial Manual Snapshots Next Action

Exact next action:

`{next_action}`

Do not run the next action in this snapshot task.
"""


def update_operations_metadata(root: Path, output: Path, created_utc: str, m: dict[str, Any]) -> tuple[bool, bool]:
    operations_path = root / OPERATIONS_STATE_PATH
    before_operations = read_text(operations_path)
    section = f"""## Latest Initial Manual Observation Snapshots

- Created UTC: `{created_utc}`
- Evidence path: `{output.resolve()}`
- VM initial snapshot created: `{m['vm_initial_snapshot_created']}`
- DSR initial snapshot created: `{m['dsr_initial_snapshot_created']}`
- Manual input required: `{m['manual_input_required']}`
- Unknown values preserved: `{m['unknown_values_preserved']}`
- Next action: `{m['next_action']}`
- No broker API call, order action, live path, or real-money recommendation was authorized.
"""
    after_operations = replace_or_append_section(before_operations, "## Latest Initial Manual Observation Snapshots", section)
    write_text(operations_path, after_operations)

    active_path = root / ACTIVE_OBSERVATIONS_PATH
    active_payload = load_yaml(active_path)
    before_active = yaml.safe_dump(active_payload, sort_keys=False, width=120, allow_unicode=False)
    active_payload["latest_initial_manual_observation_snapshots"] = {
        "created_utc": created_utc,
        "evidence_path": str(output.resolve()),
        "vm_initial_snapshot_created": m["vm_initial_snapshot_created"],
        "dsr_initial_snapshot_created": m["dsr_initial_snapshot_created"],
        "manual_input_required": m["manual_input_required"],
        "next_action": m["next_action"],
    }
    write_yaml(active_path, active_payload)
    after_active = yaml.safe_dump(active_payload, sort_keys=False, width=120, allow_unicode=False)
    return before_operations != after_operations, before_active != after_active


def manifest(created_utc: str, root: Path, output: Path, snapshot_rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "created_utc": created_utc,
        **MANIFEST_FLAGS,
        "evidence_path": str(output.resolve()),
        "current_active_observation_count": 2,
        "active_observation_ids": [VM_ID, DSR_ID],
        "vm_initial_snapshot_created": snapshot_rows[0]["snapshot_created"],
        "dsr_initial_snapshot_created": snapshot_rows[1]["snapshot_created"],
        "unknown_values_preserved": True,
        "snapshot_rows": snapshot_rows,
        "research_queue_paused": research_track_paused(root),
        "next_action": NEXT_ACTION_MANUAL_INPUT,
    }


def consistency_check(m: dict[str, Any], output: Path, root: Path) -> dict[str, Any]:
    required = {name: (output / name).exists() for name in REQUIRED_OUTPUT_FILES}
    snapshot_files_exist = all(
        (root / LOG_ROOT / strategy_id / filename).exists()
        for strategy_id in (VM_ID, DSR_ID)
        for filename in (
            "initial_manual_checkpoint.md",
            "position_snapshot_template.csv",
            "order_snapshot_template.csv",
            "equity_snapshot_template.csv",
            "benchmark_snapshot_template.csv",
            "initial_position_snapshot.csv",
            "initial_order_snapshot.csv",
            "initial_equity_snapshot.csv",
            "initial_benchmark_snapshot.csv",
        )
    )
    check = {
        "initial_manual_snapshot_step_only": m["initial_manual_snapshot_step_only"] is True,
        "manual_input_required": m["manual_input_required"] is True,
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
        "vm_initial_snapshot_exists": m["vm_initial_snapshot_created"] is True,
        "dsr_initial_snapshot_exists": m["dsr_initial_snapshot_created"] is True,
        "manual_input_checklist_exists": (output / "manual_input_checklist.md").exists(),
        "missing_values_file_exists": (output / "missing_values_after_initial_snapshot.md").exists(),
        "no_broker_confirmation_exists": (output / "no_broker_no_live_confirmation.md").exists(),
        "snapshot_files_exist": snapshot_files_exist,
        "unknown_values_explicit": m["unknown_values_preserved"] is True,
        "target_weights_not_invented": m["target_weights_invented"] is False,
        "equity_values_not_invented": m["equity_values_invented"] is False,
        "positions_not_invented": m["positions_invented"] is False,
        "orders_not_invented": m["orders_invented"] is False,
        "benchmark_values_not_invented": m["benchmark_values_invented"] is False,
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
    snapshot_rows = [write_initial_snapshots(root, created, strategy_id) for strategy_id in (VM_ID, DSR_ID)]
    m = manifest(created, root, output, snapshot_rows)

    write_text(output / "initial_manual_snapshots_summary.md", summary_md(m))
    write_text(output / "vm_initial_snapshot_review.md", snapshot_review_md("VM Initial Snapshot Review", snapshot_rows[0]))
    write_text(output / "dsr_initial_snapshot_review.md", snapshot_review_md("DSR Initial Snapshot Review", snapshot_rows[1]))
    write_text(output / "manual_input_checklist.md", manual_input_checklist_md(snapshot_rows))
    write_text(output / "missing_values_after_initial_snapshot.md", missing_values_md(snapshot_rows))
    write_text(output / "target_weight_status.md", target_weight_status_md(snapshot_rows))
    write_text(output / "no_broker_no_live_confirmation.md", no_broker_confirmation_md())
    write_text(output / "initial_manual_snapshots_next_action.md", next_action_md(m["next_action"]))

    operations_updated, active_observations_updated = update_operations_metadata(root, output, created, m)
    m.update({"operations_state_updated": operations_updated, "active_observations_metadata_updated": active_observations_updated})
    write_json(output / "initial_manual_snapshots_manifest.json", m)
    write_json(output / "initial_manual_snapshots_consistency_check.json", {"consistency_passed": False})
    check = consistency_check(m, output, root)
    write_json(output / "initial_manual_snapshots_consistency_check.json", check)
    return {**m, "consistency_passed": check["consistency_passed"], "output_dir": str(output.resolve())}


if __name__ == "__main__":
    result = run()
    print(
        json.dumps(
            {
                "output_dir": result["output_dir"],
                "next_action": result["next_action"],
                "manual_input_required": result["manual_input_required"],
                "consistency_passed": result["consistency_passed"],
            },
            indent=2,
        )
    )
