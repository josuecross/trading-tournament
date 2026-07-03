from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.objective_reset.objective_reset_review import write_json, write_text
from strategy_lab.research_os.research.profit_oriented_research_batch_v1 import write_csv


OUTPUT_DIR = (
    Path("evidence")
    / "research_recovery"
    / "profit_oriented_queue_resolution_after_high_return_robustness"
    / "latest"
)

NEXT_ACTION_DIRECTION_OWNER = "direction_owner_decision_required_before_new_research"
NEXT_ACTION_AUTHORIZE_NEW_DISCOVERY = "authorize_new_bounded_research_discovery"
NEXT_ACTION_MONITOR_ONLY = "monitor_existing_paper_forward_observations_only"
VALID_NEXT_ACTIONS = {
    NEXT_ACTION_DIRECTION_OWNER,
    NEXT_ACTION_AUTHORIZE_NEW_DISCOVERY,
    NEXT_ACTION_MONITOR_ONLY,
}

COMPLETED_EXCLUDED = (
    "high_return_tactical_etf_equity_index_bounded_lane_v1",
    "commodity_basket_etf_momentum_bounded_lane_v1",
    "macro_gld_duration_risk_off_confirmation_report",
    "volatility_throttle_focused_research_lane_v1",
    "managed_futures_etf_wrapper",
)

REQUIRED_FILES = (
    "queue_resolution_manifest.json",
    "queue_resolution_summary.md",
    "sources_inspected.md",
    "completed_excluded_lanes.md",
    "candidate_queue_table.csv",
    "queue_exhaustion_report.md",
    "queue_status_update.md",
    "guardrail_checklist.json",
    "queue_resolution_next_action.md",
    "queue_resolution_consistency_check.json",
)

TABLE_FIELDS = (
    "source",
    "item_id",
    "family_or_lane",
    "source_status",
    "selection_status",
    "reason",
    "existing_evidence_path",
)


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def registry_rows(registry: dict[str, Any]) -> list[dict[str, Any]]:
    rows = registry.get("strategies")
    return rows if isinstance(rows, list) else []


def manifest_at(root: Path, relative: str, filename: str) -> dict[str, Any]:
    return read_json(root / relative / "latest" / filename)


def recovery_path(root: Path, relative: str) -> str:
    path = root / relative / "latest"
    return str(path.resolve()) if path.exists() else str(path)


def research_sample_review_count(registry: dict[str, Any]) -> int:
    rows = registry_rows(registry)
    return sum(
        1
        for row in rows
        if "research_sample_review" in str(row.get("allowed_next_actions", row.get("allowed_next_action", "")))
        and row.get("paper_forward_active") is False
        and row.get("candidate_exhaustive_run") is False
    )


def build_candidate_table(root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    roadmap = root / "strategy_lab" / "RESEARCH_ROADMAP.md"
    registry_path = root / "strategy_lab" / "strategy_registry.yaml"
    queue_path = root / "strategy_lab" / "research_os" / "research" / "research_queue.yaml"
    ledger_path = root / "strategy_lab" / "research_os" / "family_lineage" / "family_ledger.yaml"
    research_state_path = root / "evidence" / "research_state" / "latest" / "research_state_manifest.json"

    registry = read_yaml(registry_path)
    queue = read_yaml(queue_path)
    ledger = read_yaml(ledger_path)
    research_state = read_json(research_state_path)
    ledger_entries = ledger.get("entries") if isinstance(ledger.get("entries"), list) else []
    ledger_by_id = {row.get("family_id"): row for row in ledger_entries if isinstance(row, dict)}
    registry_ambiguous_count = research_sample_review_count(registry)

    rows: list[dict[str, Any]] = []

    high_return = manifest_at(
        root,
        "evidence/research_recovery/high_return_tactical_etf_equity_index_bounded_robustness",
        "high_return_tactical_bounded_robustness_manifest.json",
    )
    if high_return:
        rows.append(
            {
                "source": "evidence/research_recovery/high_return_tactical_etf_equity_index_bounded_robustness/latest",
                "item_id": "high_return_tactical_etf_equity_index_bounded_lane_v1",
                "family_or_lane": "high_return_tactical_etf_equity_index",
                "source_status": "completed_context_only_after_robustness",
                "selection_status": "excluded_completed_for_now",
                "reason": (
                    "Robustness packet evaluated six rows; all survived cost stress, but all rows had rolling-window "
                    "weakness and all were downgraded to context-only after robustness filters."
                ),
                "existing_evidence_path": high_return.get("evidence_path", ""),
            }
        )

    commodity = manifest_at(
        root,
        "evidence/research_recovery/commodity_basket_etf_momentum_bounded_run",
        "commodity_basket_bounded_run_manifest.json",
    )
    if commodity:
        rows.append(
            {
                "source": "evidence/research_recovery/commodity_basket_etf_momentum_bounded_run/latest",
                "item_id": "commodity_basket_etf_momentum_bounded_lane_v1",
                "family_or_lane": "commodity_basket_etf_momentum_v1",
                "source_status": "completed_weak_diagnostic",
                "selection_status": "excluded_completed_for_now",
                "reason": (
                    "Bounded commodity run completed with interpretable evidence; only one control/comparator row "
                    "passed and no commodity diagnostic-pass row remains to run immediately."
                ),
                "existing_evidence_path": commodity.get("evidence_path", ""),
            }
        )

    macro = manifest_at(
        root,
        "evidence/research_recovery/macro_gld_duration_risk_off_confirmation_report",
        "macro_gld_confirmation_manifest.json",
    )
    if macro:
        rows.append(
            {
                "source": "evidence/research_recovery/macro_gld_duration_risk_off_confirmation_report/latest",
                "item_id": "macro_gld_duration_risk_off_confirmation_report",
                "family_or_lane": "macro_gld_duration_risk_off",
                "source_status": "diagnostic_confirmation_complete",
                "selection_status": "excluded_completed_for_now",
                "reason": "Macro/GLD confirmation is accepted as diagnostic evidence only and is excluded from immediate continuation.",
                "existing_evidence_path": macro.get("evidence_path", ""),
            }
        )

    volatility = manifest_at(
        root,
        "evidence/research_recovery/volatility_throttle_focused_research_followup_results_audit",
        "vol_throttle_followup_results_audit_manifest.json",
    )
    if volatility:
        rows.append(
            {
                "source": "evidence/research_recovery/volatility_throttle_focused_research_followup_results_audit/latest",
                "item_id": "volatility_throttle_focused_research_lane_v1",
                "family_or_lane": "high_return_tactical_etf_equity_index",
                "source_status": "diagnostic_followup_complete",
                "selection_status": "excluded_completed_for_now",
                "reason": "Volatility-throttle follow-up is complete for now; threshold tuning is not authorized.",
                "existing_evidence_path": recovery_path(
                    root,
                    "evidence/research_recovery/volatility_throttle_focused_research_followup_results_audit",
                ),
            }
        )

    managed = ledger_by_id.get("managed_futures_etf_wrapper")
    if managed:
        rows.append(
            {
                "source": "strategy_lab/research_os/family_lineage/family_ledger.yaml",
                "item_id": "managed_futures_etf_wrapper",
                "family_or_lane": "managed_futures_etf_wrapper",
                "source_status": managed.get("current_status", ""),
                "selection_status": "not_eligible",
                "reason": "Family ledger marks managed futures closed under current mechanics with future_research_allowed=false.",
                "existing_evidence_path": managed.get("authoritative_evidence_path", ""),
            }
        )

    gld_queue_present = any(
        isinstance(item, dict) and item.get("id") == "recover_gld_macro_family_lineage"
        for item in queue.get("queued_governance_reviews", [])
    )
    if gld_queue_present:
        rows.append(
            {
                "source": "strategy_lab/research_os/research/research_queue.yaml",
                "item_id": "recover_gld_macro_family_lineage",
                "family_or_lane": "gld_macro_risk_off",
                "source_status": "queued_governance_review",
                "selection_status": "excluded_by_direction",
                "reason": "Current direction excludes continuing Macro/GLD now; this is governance lineage, not a bounded evidence-generation run.",
                "existing_evidence_path": recovery_path(root, "evidence/research_recovery/gld_macro_family_lineage_recovery"),
            }
        )

    active_task = queue.get("active_bounded_research_task") if isinstance(queue.get("active_bounded_research_task"), dict) else {}
    if active_task:
        rows.append(
            {
                "source": "strategy_lab/research_os/research/research_queue.yaml",
                "item_id": active_task.get("id", ""),
                "family_or_lane": active_task.get("family_id", ""),
                "source_status": active_task.get("status", ""),
                "selection_status": "not_executable",
                "reason": (
                    f"Active bounded task now records next_action `{active_task.get('next_action', '')}` and "
                    f"blocker/status `{active_task.get('blocker', '')}`; it is not a run-ready next bounded task."
                ),
                "existing_evidence_path": ";".join(str(path) for path in active_task.get("source_evidence", [])),
            }
        )

    if registry_ambiguous_count:
        rows.append(
            {
                "source": "strategy_lab/strategy_registry.yaml",
                "item_id": "registry_research_sample_review_rows",
                "family_or_lane": "multiple",
                "source_status": f"{registry_ambiguous_count} rows",
                "selection_status": "ambiguous_not_selected",
                "reason": "Registry contains multiple research_sample_review rows but no current queue/roadmap/ledger source prioritizes exactly one.",
                "existing_evidence_path": "",
            }
        )

    source_context = {
        "roadmap_inspected": roadmap.exists(),
        "registry_inspected": registry_path.exists(),
        "queue_inspected": queue_path.exists(),
        "ledger_inspected": ledger_path.exists(),
        "research_state_inspected": research_state_path.exists(),
        "active_bounded_research_task_id": active_task.get("id", ""),
        "active_bounded_research_task_status": active_task.get("status", ""),
        "active_bounded_research_task_next_action": active_task.get("next_action", ""),
        "registry_research_sample_review_row_count": registry_ambiguous_count,
        "research_state_next_family": research_state.get("research_queue_reprioritization_next_family", ""),
        "research_state_next_allowed_action": research_state.get("research_queue_reprioritization_next_allowed_action", ""),
        "source_queue_status_file_updated": active_task.get("status") == "completed_for_now"
        and active_task.get("next_action") == NEXT_ACTION_DIRECTION_OWNER,
    }
    return rows, source_context


def manifest_payload(created: str, output: Path, rows: list[dict[str, Any]], source_context: dict[str, Any]) -> dict[str, Any]:
    executable = [row for row in rows if row["selection_status"] == "executable_now"]
    selected = executable[0] if len(executable) == 1 else None
    blocked_or_excluded = [
        row
        for row in rows
        if row["selection_status"]
        in {"excluded_completed_for_now", "not_eligible", "excluded_by_direction", "not_executable"}
    ]
    ambiguous = [row for row in rows if row["selection_status"] == "ambiguous_not_selected"]
    next_action = selected["item_id"] if selected else NEXT_ACTION_DIRECTION_OWNER
    return {
        "created_utc": created,
        "evidence_path": str(output.resolve()),
        "queue_resolution_after_high_return_robustness_only": True,
        "source_of_truth_state_inspected_only": True,
        "selected_task": selected["item_id"] if selected else "none",
        "selected_family_or_lane": selected["family_or_lane"] if selected else "none",
        "selected_next_executable_action": next_action if selected else "none",
        "unique_executable_bounded_task_found": selected is not None,
        "executable_eligible_item_count": len(executable),
        "completed_excluded_lane_count": sum(1 for row in rows if row["selection_status"] == "excluded_completed_for_now"),
        "blocked_or_excluded_item_count": len(blocked_or_excluded),
        "ambiguous_item_group_count": len(ambiguous),
        "queue_exhaustion_found": selected is None,
        "queue_exhaustion_reason": (
            "No unique existing bounded evidence-generation task remains after excluding completed high-return, "
            "commodity, Macro/GLD, volatility-throttle, and managed-futures items; registry research_sample rows are ambiguous."
            if selected is None
            else ""
        ),
        "completed_excluded_lanes": list(COMPLETED_EXCLUDED),
        "source_queue_status_file_updated": source_context["source_queue_status_file_updated"],
        "new_strategy_discovery_run": False,
        "new_research_batch_run": False,
        "new_backtests_run": False,
        "new_performance_metrics_from_raw_data_computed": False,
        "new_families_created": False,
        "new_variants_created": False,
        "hidden_parameter_grid_created": False,
        "provider_download": False,
        "intraday_data_used": False,
        "leverage_used": False,
        "shorting_used": False,
        "options_used": False,
        "direct_futures_used": False,
        "broker_api_called": False,
        "broker_orders_submitted": False,
        "broker_orders_cancelled": False,
        "broker_orders_reconciled": False,
        "live_orders": False,
        "real_money_recommendation": False,
        "promotion_candidates_created": False,
        "candidate_exhaustive_run": False,
        "paper_forward_activation": False,
        "new_paper_forward_candidate_created": False,
        "best_single_variant_promoted": False,
        "active_vm_preserved": True,
        "active_dsr_preserved": True,
        "static_all_weather_benchmark_control_only": True,
        "exact_rejected_variants_reopened": False,
        "diagnostic_evidence_treated_as_deployment_approval": False,
        "next_action": next_action,
        **source_context,
    }


def sources_inspected_md(manifest: dict[str, Any]) -> str:
    return f"""# Sources Inspected

- `strategy_lab/RESEARCH_ROADMAP.md`: `{manifest['roadmap_inspected']}`
- `strategy_lab/strategy_registry.yaml`: `{manifest['registry_inspected']}`
- `strategy_lab/research_os/research/research_queue.yaml`: `{manifest['queue_inspected']}`
- `strategy_lab/research_os/family_lineage/family_ledger.yaml`: `{manifest['ledger_inspected']}`
- `evidence/research_state/latest/research_state_manifest.json`: `{manifest['research_state_inspected']}`
- Latest `evidence/research_recovery/*/latest` packets for completed high-return, commodity, Macro/GLD, volatility-throttle, and managed-futures context.

Registry `research_sample_review` row count: `{manifest['registry_research_sample_review_row_count']}`

Active bounded research task after queue-status update: `{manifest['active_bounded_research_task_id']}` / `{manifest['active_bounded_research_task_status']}`.
"""


def completed_excluded_md() -> str:
    lines = ["# Completed / Excluded Lanes", ""]
    explanations = {
        "high_return_tactical_etf_equity_index_bounded_lane_v1": "Completed robustness; downgraded to context-only after robustness filters.",
        "commodity_basket_etf_momentum_bounded_lane_v1": "Completed bounded run; weak diagnostic evidence with only control row passing.",
        "macro_gld_duration_risk_off_confirmation_report": "Diagnostic confirmation complete; no continuation authorized now.",
        "volatility_throttle_focused_research_lane_v1": "Diagnostic follow-up complete; no threshold tuning authorized now.",
        "managed_futures_etf_wrapper": "Family ledger marks closed under current mechanics with future_research_allowed=false.",
    }
    for item in COMPLETED_EXCLUDED:
        lines.append(f"- `{item}`: {explanations[item]}")
    return "\n".join(lines) + "\n"


def summary_md(manifest: dict[str, Any]) -> str:
    return f"""# Profit-Oriented Queue Resolution After High-Return Robustness

Selected task: `{manifest['selected_task']}`

Selected family/lane: `{manifest['selected_family_or_lane']}`

Unique executable bounded task found: `{manifest['unique_executable_bounded_task_found']}`

Executable eligible item count: `{manifest['executable_eligible_item_count']}`

Completed/excluded lane count: `{manifest['completed_excluded_lane_count']}`

Blocked or excluded item count: `{manifest['blocked_or_excluded_item_count']}`

Ambiguous item group count: `{manifest['ambiguous_item_group_count']}`

Queue exhaustion found: `{manifest['queue_exhaustion_found']}`

Queue exhaustion reason: `{manifest['queue_exhaustion_reason']}`

Source queue/status file updated: `{manifest['source_queue_status_file_updated']}`

No research lane, backtest, discovery, provider download, intraday data, candidate_exhaustive, promotion, paper-forward activation, broker/live path, or real-money path was run.

Exact next action: `{manifest['next_action']}`
"""


def queue_exhaustion_md(manifest: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    lines = [
        "# Queue Exhaustion Report",
        "",
        f"Selected task: `{manifest['selected_task']}`",
        "",
        f"Reason: `{manifest['queue_exhaustion_reason']}`",
        "",
        "Candidate disposition:",
    ]
    for row in rows:
        lines.append(
            f"- `{row['item_id']}` from `{row['source']}`: `{row['selection_status']}` - {row['reason']}"
        )
    lines.append("")
    lines.append("No arbitrary selection was made from registry `research_sample_review` rows.")
    return "\n".join(lines) + "\n"


def queue_status_update_md(manifest: dict[str, Any]) -> str:
    return f"""# Queue Status Update

Source-of-truth queue/status file updated: `{manifest['source_queue_status_file_updated']}`

Updated file:

- `strategy_lab/research_os/research/research_queue.yaml`

Updated status:

- Active bounded task ID: `{manifest['active_bounded_research_task_id']}`
- Active bounded task status: `{manifest['active_bounded_research_task_status']}`
- Active bounded task next action: `{manifest['active_bounded_research_task_next_action']}`

No new queue item, family, variant, or hidden parameter grid was created.
"""


def next_action_md(next_action: str) -> str:
    return f"""# Queue Resolution Next Action

Exact next action:

`{next_action}`

Do not execute it in this task.
"""


def guardrail_check(manifest: dict[str, Any]) -> dict[str, Any]:
    checks = {
        "queue_resolution_only": manifest["queue_resolution_after_high_return_robustness_only"] is True,
        "source_state_only": manifest["source_of_truth_state_inspected_only"] is True,
        "no_strategy_discovery": manifest["new_strategy_discovery_run"] is False,
        "no_research_batch": manifest["new_research_batch_run"] is False,
        "no_backtests": manifest["new_backtests_run"] is False,
        "no_raw_metrics": manifest["new_performance_metrics_from_raw_data_computed"] is False,
        "no_new_family_or_variant": manifest["new_families_created"] is False
        and manifest["new_variants_created"] is False,
        "no_hidden_grid": manifest["hidden_parameter_grid_created"] is False,
        "no_provider_intraday": manifest["provider_download"] is False and manifest["intraday_data_used"] is False,
        "no_leverage_short_options_futures": manifest["leverage_used"] is False
        and manifest["shorting_used"] is False
        and manifest["options_used"] is False
        and manifest["direct_futures_used"] is False,
        "no_broker_live_real_money": manifest["broker_api_called"] is False
        and manifest["broker_orders_submitted"] is False
        and manifest["broker_orders_cancelled"] is False
        and manifest["broker_orders_reconciled"] is False
        and manifest["live_orders"] is False
        and manifest["real_money_recommendation"] is False,
        "no_candidate_promotion_paper": manifest["promotion_candidates_created"] is False
        and manifest["candidate_exhaustive_run"] is False
        and manifest["paper_forward_activation"] is False
        and manifest["new_paper_forward_candidate_created"] is False
        and manifest["best_single_variant_promoted"] is False,
        "active_state_preserved": manifest["active_vm_preserved"] is True and manifest["active_dsr_preserved"] is True,
        "static_all_weather_control_only": manifest["static_all_weather_benchmark_control_only"] is True,
        "rejected_not_reopened": manifest["exact_rejected_variants_reopened"] is False,
        "diagnostic_not_deployment": manifest["diagnostic_evidence_treated_as_deployment_approval"] is False,
        "next_action_valid": manifest["next_action"] in VALID_NEXT_ACTIONS,
    }
    checks["guardrails_passed"] = all(checks.values())
    return checks


def consistency_check(manifest: dict[str, Any], output: Path, rows: list[dict[str, Any]]) -> dict[str, Any]:
    required = {name: (output / name).exists() for name in REQUIRED_FILES}
    required["queue_resolution_consistency_check.json"] = True
    guardrails = read_json(output / "guardrail_checklist.json")
    checks = {
        "queue_resolution_only": manifest["queue_resolution_after_high_return_robustness_only"] is True,
        "sources_inspected": all(
            manifest[key]
            for key in [
                "roadmap_inspected",
                "registry_inspected",
                "queue_inspected",
                "ledger_inspected",
                "research_state_inspected",
            ]
        ),
        "source_queue_updated": manifest["source_queue_status_file_updated"] is True,
        "no_selected_task": manifest["selected_task"] == "none",
        "no_executable_items": manifest["executable_eligible_item_count"] == 0,
        "queue_exhaustion_found": manifest["queue_exhaustion_found"] is True,
        "candidate_rows_exist": len(rows) >= len(COMPLETED_EXCLUDED),
        "completed_excluded_lanes_recorded": set(COMPLETED_EXCLUDED).issubset(set(manifest["completed_excluded_lanes"])),
        "registry_ambiguity_recorded": manifest["registry_research_sample_review_row_count"] >= 1
        and manifest["ambiguous_item_group_count"] >= 1,
        "guardrails_passed": guardrails.get("guardrails_passed") is True,
        "required_files_present": all(required.values()),
        "required_files": required,
    }
    checks["consistency_passed"] = all(value is True for key, value in checks.items() if key != "required_files")
    return checks


def write_outputs(root: Path, created: str, rows: list[dict[str, Any]], source_context: dict[str, Any]) -> dict[str, Any]:
    output = root / OUTPUT_DIR
    output.mkdir(parents=True, exist_ok=True)
    manifest = manifest_payload(created, output, rows, source_context)
    write_json(output / "queue_resolution_manifest.json", manifest)
    write_text(output / "queue_resolution_summary.md", summary_md(manifest))
    write_text(output / "sources_inspected.md", sources_inspected_md(manifest))
    write_text(output / "completed_excluded_lanes.md", completed_excluded_md())
    write_csv(output / "candidate_queue_table.csv", rows, list(TABLE_FIELDS))
    write_text(output / "queue_exhaustion_report.md", queue_exhaustion_md(manifest, rows))
    write_text(output / "queue_status_update.md", queue_status_update_md(manifest))
    write_json(output / "guardrail_checklist.json", guardrail_check(manifest))
    write_text(output / "queue_resolution_next_action.md", next_action_md(manifest["next_action"]))
    check = consistency_check(manifest, output, rows)
    write_json(output / "queue_resolution_consistency_check.json", check)
    return {**manifest, "output_dir": str(output.resolve()), "consistency_passed": check["consistency_passed"]}


def run(root: Path = ROOT) -> dict[str, Any]:
    created = now_utc()
    rows, source_context = build_candidate_table(root)
    return write_outputs(root, created, rows, source_context)


if __name__ == "__main__":
    result = run()
    print(
        json.dumps(
            {
                "output_dir": result["output_dir"],
                "selected_task": result["selected_task"],
                "executable_eligible_item_count": result["executable_eligible_item_count"],
                "queue_exhaustion_found": result["queue_exhaustion_found"],
                "source_queue_status_file_updated": result["source_queue_status_file_updated"],
                "next_action": result["next_action"],
                "consistency_passed": result["consistency_passed"],
            },
            indent=2,
            sort_keys=True,
        )
    )
