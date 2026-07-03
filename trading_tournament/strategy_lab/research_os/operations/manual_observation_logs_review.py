from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.objective_reset.objective_reset_review import replace_or_append_section, write_json, write_text
from strategy_lab.research_os.operations.observation_checkpoint import DSR_ID, VM_ID, active_observation_status
from strategy_lab.research_os.split_tracks import ACTIVE_OBSERVATIONS_PATH, OPERATIONS_STATE_PATH, RESEARCH_QUEUE_PATH


OUTPUT_DIR = Path("evidence") / "operations_observation" / "manual_review_required_for_observation_logs" / "latest"
LOG_ROOT = Path("strategy_lab") / "research_os" / "operations" / "observation_logs"
STATIC_ALL_WEATHER_ID = "static_all_weather_benchmark_v1"

NEXT_ACTION_CREATE_SNAPSHOTS = "create_initial_manual_observation_snapshots"
NEXT_ACTION_WAIT = "wait_for_next_paper_forward_observation_checkpoint"
NEXT_ACTION_REVIEW = "manual_review_required_for_observation_logs"
NEXT_ACTION_PAUSE_LOGS = "pause_observation_due_to_missing_logs"
NEXT_ACTION_PAUSE = "pause_expansion_and_wait_for_manual_direction"
VALID_NEXT_ACTIONS = {
    NEXT_ACTION_CREATE_SNAPSHOTS,
    NEXT_ACTION_WAIT,
    NEXT_ACTION_REVIEW,
    NEXT_ACTION_PAUSE_LOGS,
    NEXT_ACTION_PAUSE,
}

REQUIRED_OUTPUT_FILES = (
    "observation_logs_review_manifest.json",
    "observation_logs_review_summary.md",
    "active_observation_log_inventory.md",
    "vm_observation_log_review.md",
    "dsr_observation_log_review.md",
    "canonical_observation_log_schema.md",
    "manual_checkpoint_template.md",
    "manual_snapshot_requirements.md",
    "no_broker_no_live_policy.md",
    "missing_observation_evidence.md",
    "observation_log_repair_plan.md",
    "observation_logs_next_action.md",
    "observation_logs_consistency_check.json",
)

MANIFEST_FLAGS = {
    "manual_observation_log_review_only": True,
    "observation_logs_missing_or_not_available": True,
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


def write_csv(path: Path, fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()


def research_queue_paused(root: Path) -> bool:
    queue = load_yaml(root / RESEARCH_QUEUE_PATH)
    return (
        queue.get("current_expansion_status") == "paused"
        and queue.get("sandbox_batch_authorized") is False
        and queue.get("strategy_discovery_authorized") is False
        and queue.get("candidate_exhaustive_authorized") is False
        and queue.get("paper_forward_candidate_creation_authorized") is False
    )


def existing_log_inventory(root: Path, strategy_id: str) -> dict[str, Any]:
    detail = active_observation_status(root, strategy_id)
    log_dir = root / LOG_ROOT / strategy_id
    return {
        "strategy_id": strategy_id,
        "active_observation_file_exists": detail["exists"],
        "active_observation_status": detail["status"],
        "active_observation_frozen": detail["frozen"],
        "active_observation_rules_frozen": detail["rules_frozen"],
        "canonical_log_dir_exists_before_review": log_dir.exists(),
        "observation_metadata_file_exists": (log_dir / "observation_metadata.yaml").exists(),
        "frozen_rules_reference_exists": (log_dir / "frozen_rules_reference.md").exists(),
        "rule_hash_or_checksum_exists": False,
        "start_date_exists": False,
        "target_allocation_snapshot_exists": (log_dir / "target_allocation_snapshot.yaml").exists(),
        "latest_intended_target_weights_exists": False,
        "latest_observed_weights_exists": False,
        "latest_account_equity_snapshot_exists": False,
        "latest_benchmark_snapshot_exists": False,
        "latest_position_snapshot_exists": False,
        "latest_order_snapshot_exists": False,
        "open_order_record_exists": False,
        "stale_position_check_exists": False,
        "broker_api_issue_log_exists": (log_dir / "issues_log.md").exists(),
        "manual_notes_file_exists": (log_dir / "notes.md").exists(),
        "last_checkpoint_timestamp_exists": False,
        "next_checkpoint_due_date_or_cadence_exists": False,
        "rule_summary": detail["rule_summary"],
        "universe": detail["universe"],
        "minimum_days_before_judgment": detail["minimum_days_before_judgment"],
        "current_checkpoint_status": detail["current_checkpoint_status"],
    }


def missing_items(inventory: dict[str, Any]) -> list[str]:
    required_fields = [
        "observation_metadata_file_exists",
        "frozen_rules_reference_exists",
        "rule_hash_or_checksum_exists",
        "start_date_exists",
        "target_allocation_snapshot_exists",
        "latest_intended_target_weights_exists",
        "latest_observed_weights_exists",
        "latest_account_equity_snapshot_exists",
        "latest_benchmark_snapshot_exists",
        "latest_position_snapshot_exists",
        "latest_order_snapshot_exists",
        "open_order_record_exists",
        "stale_position_check_exists",
        "broker_api_issue_log_exists",
        "manual_notes_file_exists",
        "last_checkpoint_timestamp_exists",
        "next_checkpoint_due_date_or_cadence_exists",
    ]
    return [field.replace("_exists", "") for field in required_fields if inventory.get(field) is not True]


def manual_checkpoint_template(strategy_id: str = "unknown") -> str:
    return f"""# Manual Observation Checkpoint Template

Status: `placeholder_created_manual_input_required`

No broker API was called to create this template. Enter values manually.

## Checkpoint Metadata

- Checkpoint date/time UTC: `unknown`
- Observation ID: `{strategy_id}`
- Strategy ID: `{strategy_id}`
- Frozen rule reference: `frozen_rules_reference.md`
- Rule hash/checksum: `unknown`
- Operator/reviewer: `unknown`

## Target And Observed Weights

- Target weights: `unknown`
- Observed weights: `unknown`
- Target allocation source: `unknown`

## Account / Benchmark

- Equity/account value: `unknown`
- Cash value: `unknown`
- Benchmark references: `unknown`

## Positions / Orders

- Positions: `unknown`
- Open orders: `unknown`
- Rejected/canceled orders: `unknown`
- Stale positions: `unknown`

## Issues

- Unexplained P&L: `unknown`
- Missing logs: `unknown`
- Broker/API issues: `unknown`
- Notes: `unknown`

## Decision

Choose one:

- `continue_observation`
- `manual_review_required`
- `pause_observation_due_to_logging_issue`
- `pause_observation_due_to_broker_or_state_issue`
"""


def frozen_rules_reference_md(strategy_id: str, detail: dict[str, Any]) -> str:
    rules = "\n".join(f"- {line}" for line in detail.get("rule_summary", [])) or "- unknown"
    universe = ", ".join(detail.get("universe", [])) or "unknown"
    return f"""# Frozen Rules Reference

Status: `placeholder_created_manual_input_required`

Observation ID: `{strategy_id}`

Rule hash/checksum: `unknown`

Rule source: recovered active observation YAML.

Universe: `{universe}`

## Frozen Rule Summary

{rules}

No target allocations, broker/account values, positions, orders, or benchmark levels are invented in this reference.
"""


def observation_metadata_payload(created_utc: str, strategy_id: str, detail: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "placeholder_created_manual_input_required",
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
        "last_checkpoint_timestamp": "unknown",
        "next_checkpoint_due_date": "unknown",
        "checkpoint_cadence": "unknown",
        "minimum_days_before_judgment": detail["minimum_days_before_judgment"] or "unknown",
        "target_allocations_available": False,
        "latest_equity_snapshot_available": False,
        "latest_positions_available": False,
        "latest_orders_available": False,
        "broker_derived_values": False,
        "invented_equity": False,
        "invented_positions": False,
        "invented_orders": False,
        "real_money_recommendation": False,
    }


def target_allocation_placeholder(created_utc: str, strategy_id: str) -> dict[str, Any]:
    return {
        "status": "placeholder_created_manual_input_required",
        "created_utc": created_utc,
        "observation_id": strategy_id,
        "strategy_id": strategy_id,
        "target_weights": "unknown",
        "observed_weights": "unknown",
        "cash_weight": "unknown",
        "source": "manual_input_required",
        "broker_derived_values": False,
        "invented_values": False,
    }


def issues_log_md() -> str:
    return """# Issues Log

Status: `placeholder_created_manual_input_required`

No broker API was called.

## Entries

- `unknown`: manual input required.
"""


def notes_md() -> str:
    return """# Notes

Status: `placeholder_created_manual_input_required`

Manual observation notes are required. No operational facts are invented in this placeholder.
"""


def create_placeholders(root: Path, created_utc: str, strategy_id: str) -> list[str]:
    detail = active_observation_status(root, strategy_id)
    log_dir = root / LOG_ROOT / strategy_id
    log_dir.mkdir(parents=True, exist_ok=True)
    write_yaml(log_dir / "observation_metadata.yaml", observation_metadata_payload(created_utc, strategy_id, detail))
    write_text(log_dir / "frozen_rules_reference.md", frozen_rules_reference_md(strategy_id, detail))
    write_yaml(log_dir / "target_allocation_snapshot.yaml", target_allocation_placeholder(created_utc, strategy_id))
    write_text(log_dir / "manual_checkpoint_template.md", manual_checkpoint_template(strategy_id))
    write_text(log_dir / "latest_manual_checkpoint.md", manual_checkpoint_template(strategy_id))
    write_csv(log_dir / "position_snapshot_template.csv", ["as_of_utc", "symbol", "quantity", "market_value", "source", "notes"])
    write_csv(log_dir / "order_snapshot_template.csv", ["as_of_utc", "order_id", "symbol", "side", "quantity", "status", "source", "notes"])
    write_csv(log_dir / "equity_snapshot_template.csv", ["as_of_utc", "account_value", "cash_value", "source", "notes"])
    write_csv(log_dir / "benchmark_snapshot_template.csv", ["as_of_utc", "benchmark_id", "level_or_value", "source", "notes"])
    write_text(log_dir / "issues_log.md", issues_log_md())
    write_text(log_dir / "notes.md", notes_md())
    return [
        str((log_dir / name).resolve())
        for name in (
            "observation_metadata.yaml",
            "frozen_rules_reference.md",
            "target_allocation_snapshot.yaml",
            "manual_checkpoint_template.md",
            "latest_manual_checkpoint.md",
            "position_snapshot_template.csv",
            "order_snapshot_template.csv",
            "equity_snapshot_template.csv",
            "benchmark_snapshot_template.csv",
            "issues_log.md",
            "notes.md",
        )
    ]


def schema_md() -> str:
    return """# Canonical Observation Log Schema

Canonical root:

`strategy_lab/research_os/operations/observation_logs/`

Each active observation folder supports:

1. `observation_metadata.yaml`
2. `frozen_rules_reference.md`
3. `target_allocation_snapshot.yaml`
4. `manual_checkpoint_template.md`
5. `latest_manual_checkpoint.md`
6. `position_snapshot_template.csv`
7. `order_snapshot_template.csv`
8. `equity_snapshot_template.csv`
9. `benchmark_snapshot_template.csv`
10. `issues_log.md`
11. `notes.md`

Placeholders use `status: placeholder_created_manual_input_required` and `unknown` for missing facts. No broker-derived values, equity, positions, orders, or benchmark levels are invented.
"""


def snapshot_requirements_md() -> str:
    return """# Manual Snapshot Requirements

Before observation is considered clean, each active observation needs:

- checkpoint timestamp
- observation ID and strategy ID
- frozen rules reference
- rule hash or checksum
- operator/reviewer
- target weights
- observed weights
- equity/account value
- benchmark references
- positions
- open orders
- rejected/canceled orders
- stale position check
- unexplained P&L review
- missing log review
- broker/API issue review
- notes
- decision

All values must be entered manually by the project owner unless a separately authorized data path is approved later.
"""


def no_broker_policy_md() -> str:
    return """# No-Broker / No-Live Policy

This review confirms:

- no broker API call was made
- no order was submitted
- no order was canceled
- no order was reconciled
- no live order path was touched
- no real-money recommendation was made

If broker/account information is needed, the project owner must enter it manually in a future checkpoint file. This task does not authorize broker integration, live orders, or real-money trading.
"""


def inventory_md(inventories: list[dict[str, Any]]) -> str:
    lines = ["# Active Observation Log Inventory", ""]
    for item in inventories:
        missing = ", ".join(missing_items(item)) or "none"
        lines.extend(
            [
                f"## `{item['strategy_id']}`",
                "",
                f"- Active observation file exists: `{item['active_observation_file_exists']}`",
                f"- Active observation status: `{item['active_observation_status']}`",
                f"- Frozen/rules frozen: `{item['active_observation_frozen']}` / `{item['active_observation_rules_frozen']}`",
                f"- Canonical log directory existed before review: `{item['canonical_log_dir_exists_before_review']}`",
                f"- Missing items before repair placeholders: `{missing}`",
                "",
            ]
        )
    return "\n".join(lines)


def review_md(title: str, item: dict[str, Any]) -> str:
    missing = "\n".join(f"- `{name}`" for name in missing_items(item)) or "- none"
    return f"""# {title}

- Active observation file exists: `{item['active_observation_file_exists']}`
- Status: `{item['active_observation_status']}`
- Frozen: `{item['active_observation_frozen']}`
- Rules frozen: `{item['active_observation_rules_frozen']}`
- Minimum days before judgment: `{item['minimum_days_before_judgment']}`
- Current checkpoint status: `{item['current_checkpoint_status']}`

## Missing Evidence Before Placeholder Creation

{missing}

Placeholders were created with unknown values and manual-input-required status. No target weights, account values, positions, orders, benchmark levels, or rule hashes were invented.
"""


def missing_evidence_md(inventories: list[dict[str, Any]]) -> str:
    lines = ["# Missing Observation Evidence", ""]
    for item in inventories:
        lines.append(f"## `{item['strategy_id']}`")
        for name in missing_items(item):
            lines.append(f"- `{name}`")
        lines.append("")
    return "\n".join(lines)


def repair_plan_md(next_action: str) -> str:
    return f"""# Observation Log Repair Plan

1. Use the canonical folder for each active observation.
2. Fill `latest_manual_checkpoint.md` with a dated manual checkpoint.
3. Fill target allocation, position, order, equity, and benchmark templates from project-owner supplied information only.
4. Add rule hash/checksum if available.
5. Record any missing fields explicitly as `unknown`.
6. Re-run an observation-only checkpoint after manual snapshots are entered.

Exact next action:

`{next_action}`
"""


def summary_md(m: dict[str, Any]) -> str:
    return f"""# Observation Logs Manual Review Summary

Exact next action: `{m['next_action']}`

Active observations reviewed:

- `{VM_ID}`
- `{DSR_ID}`

Observation logs missing or not available: `{m['observation_logs_missing_or_not_available']}`

Canonical log schema created: `{m['canonical_log_schema_created']}`

Manual checkpoint template created: `{m['manual_checkpoint_template_created']}`

Placeholder snapshots created: `{m['placeholder_snapshots_created']}`

No broker API call, order submission, order cancellation, order reconciliation, live order path, or real-money recommendation occurred.
"""


def next_action_md(next_action: str) -> str:
    return f"""# Observation Logs Next Action

Exact next action:

`{next_action}`

Do not run the next action in this review task.
"""


def update_operations_metadata(root: Path, output: Path, created_utc: str, m: dict[str, Any]) -> tuple[bool, bool]:
    operations_path = root / OPERATIONS_STATE_PATH
    before_operations = read_text(operations_path)
    section = f"""## Latest Manual Observation Logs Review

- Created UTC: `{created_utc}`
- Evidence path: `{output.resolve()}`
- Canonical log schema created: `{m['canonical_log_schema_created']}`
- Manual checkpoint template created: `{m['manual_checkpoint_template_created']}`
- Placeholder snapshots created: `{m['placeholder_snapshots_created']}`
- Observation logs missing or not available: `{m['observation_logs_missing_or_not_available']}`
- Next action: `{m['next_action']}`
- No broker API call, order action, live path, or real-money recommendation was authorized.
"""
    after_operations = replace_or_append_section(before_operations, "## Latest Manual Observation Logs Review", section)
    write_text(operations_path, after_operations)

    active_path = root / ACTIVE_OBSERVATIONS_PATH
    active_payload = load_yaml(active_path)
    before_active = yaml.safe_dump(active_payload, sort_keys=False, width=120, allow_unicode=False)
    active_payload["latest_manual_observation_logs_review"] = {
        "created_utc": created_utc,
        "evidence_path": str(output.resolve()),
        "canonical_log_schema_created": m["canonical_log_schema_created"],
        "manual_checkpoint_template_created": m["manual_checkpoint_template_created"],
        "placeholder_snapshots_created": m["placeholder_snapshots_created"],
        "next_action": m["next_action"],
    }
    write_yaml(active_path, active_payload)
    after_active = yaml.safe_dump(active_payload, sort_keys=False, width=120, allow_unicode=False)
    return before_operations != after_operations, before_active != after_active


def manifest(created_utc: str, root: Path, output: Path, inventories: list[dict[str, Any]], placeholder_files: dict[str, list[str]]) -> dict[str, Any]:
    return {
        "created_utc": created_utc,
        **MANIFEST_FLAGS,
        "evidence_path": str(output.resolve()),
        "current_active_observation_count": 2,
        "active_observation_ids": [VM_ID, DSR_ID],
        "canonical_log_schema_created": True,
        "manual_checkpoint_template_created": True,
        "placeholder_snapshots_created": True,
        "placeholder_files": placeholder_files,
        "active_observation_inventory": inventories,
        "research_queue_paused": research_queue_paused(root),
        "next_action": NEXT_ACTION_CREATE_SNAPSHOTS,
    }


def consistency_check(m: dict[str, Any], output: Path, root: Path) -> dict[str, Any]:
    required = {name: (output / name).exists() for name in REQUIRED_OUTPUT_FILES}
    log_dirs_exist = all((root / LOG_ROOT / strategy_id).exists() for strategy_id in (VM_ID, DSR_ID))
    check = {
        "manual_observation_log_review_only": m["manual_observation_log_review_only"] is True,
        "observation_logs_missing_status_recorded": m["observation_logs_missing_or_not_available"] is True,
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
        "canonical_observation_log_schema_exists": (output / "canonical_observation_log_schema.md").exists() and log_dirs_exist,
        "manual_checkpoint_template_exists": (output / "manual_checkpoint_template.md").exists(),
        "missing_evidence_file_exists": (output / "missing_observation_evidence.md").exists(),
        "no_broker_policy_exists": (output / "no_broker_no_live_policy.md").exists(),
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
    inventories_before = [existing_log_inventory(root, strategy_id) for strategy_id in (VM_ID, DSR_ID)]
    placeholder_files = {strategy_id: create_placeholders(root, created, strategy_id) for strategy_id in (VM_ID, DSR_ID)}
    m = manifest(created, root, output, inventories_before, placeholder_files)

    write_text(output / "observation_logs_review_summary.md", summary_md(m))
    write_text(output / "active_observation_log_inventory.md", inventory_md(inventories_before))
    write_text(output / "vm_observation_log_review.md", review_md("VM Observation Log Review", inventories_before[0]))
    write_text(output / "dsr_observation_log_review.md", review_md("DSR Observation Log Review", inventories_before[1]))
    write_text(output / "canonical_observation_log_schema.md", schema_md())
    write_text(output / "manual_checkpoint_template.md", manual_checkpoint_template())
    write_text(output / "manual_snapshot_requirements.md", snapshot_requirements_md())
    write_text(output / "no_broker_no_live_policy.md", no_broker_policy_md())
    write_text(output / "missing_observation_evidence.md", missing_evidence_md(inventories_before))
    write_text(output / "observation_log_repair_plan.md", repair_plan_md(m["next_action"]))
    write_text(output / "observation_logs_next_action.md", next_action_md(m["next_action"]))

    operations_updated, active_observations_updated = update_operations_metadata(root, output, created, m)
    m.update({"operations_state_updated": operations_updated, "active_observations_metadata_updated": active_observations_updated})
    write_json(output / "observation_logs_review_manifest.json", m)
    write_json(output / "observation_logs_consistency_check.json", {"consistency_passed": False})
    check = consistency_check(m, output, root)
    write_json(output / "observation_logs_consistency_check.json", check)
    return {**m, "consistency_passed": check["consistency_passed"], "output_dir": str(output.resolve())}


if __name__ == "__main__":
    result = run()
    print(
        json.dumps(
            {
                "output_dir": result["output_dir"],
                "next_action": result["next_action"],
                "placeholder_snapshots_created": result["placeholder_snapshots_created"],
                "consistency_passed": result["consistency_passed"],
            },
            indent=2,
        )
    )
