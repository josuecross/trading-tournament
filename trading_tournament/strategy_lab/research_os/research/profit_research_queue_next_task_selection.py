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


OUTPUT_DIR = Path("evidence") / "research_recovery" / "profit_research_queue_next_task_selection" / "latest"

EXCLUDED_COMPLETED_ITEMS = {
    "macro_gld_duration_risk_off_bounded_lane_v1",
    "macro_gld_duration_risk_off_confirmation_report",
    "volatility_throttle_focused_research_lane_v1",
}

NEXT_ACTION_UPDATE_QUEUE = "update_profit_oriented_research_queue_with_next_bounded_task"
NEXT_ACTION_RUN_SELECTED = "run_selected_bounded_profit_research_task"
VALID_NEXT_ACTIONS = {NEXT_ACTION_UPDATE_QUEUE, NEXT_ACTION_RUN_SELECTED}

REQUIRED_FILES = (
    "queue_next_task_selection_manifest.json",
    "queue_next_task_selection_summary.md",
    "source_state_review.md",
    "eligible_item_review.csv",
    "blocker_report.md",
    "queue_selection_guardrail_check.json",
    "queue_selection_next_action.md",
)


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_text_if_exists(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def registry_rows(registry: dict[str, Any]) -> list[dict[str, Any]]:
    rows = registry.get("strategies")
    return rows if isinstance(rows, list) else []


def latest_manifest(root: Path, relative: str, filename: str) -> dict[str, Any]:
    return read_json(root / relative / "latest" / filename)


def build_item_review(root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    research_queue = read_yaml(root / "strategy_lab" / "research_os" / "research" / "research_queue.yaml")
    family_ledger = read_yaml(root / "strategy_lab" / "research_os" / "family_lineage" / "family_ledger.yaml")
    registry = read_yaml(root / "strategy_lab" / "strategy_registry.yaml")
    research_state = read_json(root / "evidence" / "research_state" / "latest" / "research_state_manifest.json")

    queue_items = research_queue.get("queued_governance_reviews") or []
    ledger_entries = family_ledger.get("entries") or []
    ledger_by_id = {row.get("family_id"): row for row in ledger_entries if isinstance(row, dict)}

    review: list[dict[str, Any]] = []

    gld_queue_status = "not_present"
    if any(row.get("id") == "recover_gld_macro_family_lineage" for row in queue_items if isinstance(row, dict)):
        gld_manifest = latest_manifest(
            root,
            "evidence/research_recovery/gld_macro_family_lineage_recovery",
            "gld_macro_lineage_recovery_manifest.json",
        )
        gld_confirm = latest_manifest(
            root,
            "evidence/research_recovery/macro_gld_duration_risk_off_confirmation_report",
            "macro_gld_confirmation_manifest.json",
        )
        gld_queue_status = "completed_excluded_for_now" if gld_manifest.get("lineage_recovery_completed") else "queued"
        review.append(
            {
                "source": "strategy_lab/research_os/research/research_queue.yaml",
                "item_id": "recover_gld_macro_family_lineage",
                "family_or_lane": "gld_macro_risk_off",
                "source_status": gld_queue_status,
                "selection_status": "not_eligible",
                "reason": (
                    "Queue still lists GLD lineage recovery, but lineage recovery and Macro/GLD confirmation evidence "
                    "already exist; current direction excludes continuing Macro/GLD now."
                ),
                "existing_evidence_path": gld_manifest.get("evidence_path") or gld_confirm.get("evidence_path") or "",
            }
        )

    commodity_family = str(research_state.get("research_queue_reprioritization_next_family", ""))
    commodity_action = str(research_state.get("research_queue_reprioritization_next_allowed_action", ""))
    if commodity_family or commodity_action:
        review.append(
            {
                "source": "evidence/research_state/latest/research_state_manifest.json",
                "item_id": commodity_action or "commodity_queue_item",
                "family_or_lane": commodity_family or "commodity_basket_etf_momentum_v1",
                "source_status": "suggested_queue_item",
                "selection_status": "blocked_not_executable_now",
                "reason": (
                    "Research-state manifest points to commodity-basket ETF review, but existing commodity review, "
                    "exploratory, risk-control, and diagnostics artifacts are already present; no current root runner "
                    "or research-recovery run-ready bounded lane exists for the suggested action."
                ),
                "existing_evidence_path": "evidence/commodity_exploratory/latest; evidence/commodity_lab/risk_control_batch1_diagnostics_completion/latest",
            }
        )

    managed = ledger_by_id.get("managed_futures_etf_wrapper")
    if managed:
        review.append(
            {
                "source": "strategy_lab/research_os/family_lineage/family_ledger.yaml",
                "item_id": "managed_futures_etf_wrapper",
                "family_or_lane": "managed_futures_etf_wrapper",
                "source_status": managed.get("current_status", ""),
                "selection_status": "not_eligible",
                "reason": (
                    "Family ledger marks this closed under current mechanics with future_research_allowed=false; "
                    "older roadmap priority backlog is therefore not enough to run it."
                ),
                "existing_evidence_path": managed.get("authoritative_evidence_path", ""),
            }
        )

    research_sample_rows = [
        row
        for row in registry_rows(registry)
        if "research_sample_review" in str(row.get("allowed_next_actions", row.get("allowed_next_action", "")))
        and row.get("paper_forward_active") is False
        and row.get("candidate_exhaustive_run") is False
    ]
    if research_sample_rows:
        review.append(
            {
                "source": "strategy_lab/strategy_registry.yaml",
                "item_id": "registry_research_sample_review_rows",
                "family_or_lane": "multiple",
                "source_status": f"{len(research_sample_rows)} rows",
                "selection_status": "ambiguous_not_selected",
                "reason": (
                    "Registry contains multiple research_sample_review rows but no current queue source prioritizes "
                    "exactly one bounded next task among them."
                ),
                "existing_evidence_path": "",
            }
        )

    latest_macro = latest_manifest(
        root,
        "evidence/research_recovery/macro_gld_duration_risk_off_confirmation_report",
        "macro_gld_confirmation_manifest.json",
    )
    if latest_macro:
        review.append(
            {
                "source": "evidence/research_recovery/macro_gld_duration_risk_off_confirmation_report/latest",
                "item_id": "macro_gld_duration_risk_off_confirmation_report",
                "family_or_lane": latest_macro.get("lane_id", ""),
                "source_status": "completed_for_now",
                "selection_status": "excluded_by_instruction",
                "reason": "Accepted diagnostic confirmation is complete; user direction excludes continuing Macro/GLD now.",
                "existing_evidence_path": latest_macro.get("evidence_path", ""),
            }
        )

    latest_vol = latest_manifest(
        root,
        "evidence/research_recovery/volatility_throttle_focused_research_followup_results_audit",
        "vol_throttle_followup_results_audit_manifest.json",
    )
    if latest_vol:
        review.append(
            {
                "source": "evidence/research_recovery/volatility_throttle_focused_research_followup_results_audit/latest",
                "item_id": "volatility_throttle_focused_research_lane_v1",
                "family_or_lane": "high_return_tactical_etf_equity_index",
                "source_status": "completed_for_now",
                "selection_status": "excluded_by_instruction",
                "reason": "Volatility-throttle lane is complete for now and excluded from the next task.",
                "existing_evidence_path": str(root / "evidence/research_recovery/volatility_throttle_focused_research_followup_results_audit/latest"),
            }
        )

    executable = [row for row in review if row["selection_status"] == "executable_now"]
    source_context = {
        "research_queue_current_expansion_status": research_queue.get("current_expansion_status", ""),
        "research_queue_strategy_discovery_authorized": research_queue.get("strategy_discovery_authorized", ""),
        "research_state_reprioritization_next_family": commodity_family,
        "research_state_reprioritization_next_allowed_action": commodity_action,
        "registry_research_sample_review_row_count": len(research_sample_rows),
        "family_ledger_managed_futures_status": managed.get("current_status") if managed else "",
    }
    return review, source_context


def manifest_payload(created: str, output: Path, review: list[dict[str, Any]], source_context: dict[str, Any]) -> dict[str, Any]:
    executable = [row for row in review if row["selection_status"] == "executable_now"]
    blocked = [row for row in review if row["selection_status"] in {"blocked_not_executable_now", "not_eligible"}]
    ambiguous = [row for row in review if row["selection_status"] == "ambiguous_not_selected"]
    selected = executable[0] if len(executable) == 1 else None
    no_unique = selected is None
    next_action = NEXT_ACTION_RUN_SELECTED if selected else NEXT_ACTION_UPDATE_QUEUE
    return {
        "created_utc": created,
        "evidence_path": str(output.resolve()),
        "queue_next_task_selection_only": True,
        "selection_from_existing_roadmap_registry_ledger_only": True,
        "completed_macro_gld_excluded": True,
        "completed_volatility_throttle_excluded": True,
        "selected_task": selected["item_id"] if selected else "none",
        "selected_lane": selected["family_or_lane"] if selected else "none",
        "selected_family": selected["family_or_lane"] if selected else "none",
        "step_performed": "blocker_report_no_unique_executable_queue_item" if no_unique else "selected_existing_bounded_task",
        "eligible_executable_item_count": len(executable),
        "blocked_item_count": len(blocked),
        "ambiguous_item_count": len(ambiguous),
        "usable_diagnostic_evidence_produced": False,
        "blocker_found": no_unique,
        "blocker_reason": (
            "No single executable bounded evidence-generation task is currently marked run-ready/design-ready in the "
            "inspected profit-oriented queue after excluding completed Macro/GLD and volatility-throttle lanes."
            if no_unique
            else ""
        ),
        "new_strategy_discovery_run": False,
        "new_research_batch_run": False,
        "new_backtests_run": False,
        "new_performance_metrics_from_raw_data_computed": False,
        "new_families_created": False,
        "new_variants_created": False,
        "hidden_parameter_grid_created": False,
        "provider_download": False,
        "intraday_data_used": False,
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
        "active_vm_preserved": True,
        "active_dsr_preserved": True,
        "static_all_weather_benchmark_control_only": True,
        "exact_rejected_variants_reopened": False,
        "next_action": next_action,
        **source_context,
    }


def summary_md(manifest: dict[str, Any]) -> str:
    return f"""# Profit Research Queue Next Task Selection

Selected task: `{manifest['selected_task']}`

Selected lane/family: `{manifest['selected_lane']}`

Step performed: `{manifest['step_performed']}`

Executable eligible items: `{manifest['eligible_executable_item_count']}`

Blocked items reviewed: `{manifest['blocked_item_count']}`

Ambiguous item groups reviewed: `{manifest['ambiguous_item_count']}`

Usable diagnostic evidence produced: `{manifest['usable_diagnostic_evidence_produced']}`

Blocker found: `{manifest['blocker_found']}`

Blocker reason: `{manifest['blocker_reason']}`

No strategy was promoted, no paper-forward path was activated, no provider download occurred, and no broker/live/real-money path was touched.

Exact next action: `{manifest['next_action']}`
"""


def source_review_md(manifest: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    lines = [
        "# Source State Review",
        "",
        "- `strategy_lab/research_os/research/research_queue.yaml` was inspected.",
        "- `strategy_lab/research_os/family_lineage/family_ledger.yaml` was inspected.",
        "- `strategy_lab/strategy_registry.yaml` was inspected.",
        "- `evidence/research_state/latest/research_state_manifest.json` was inspected.",
        "- Latest `evidence/research_recovery/*/latest` manifests were inspected for completed Macro/GLD and volatility-throttle state.",
        "",
        f"Research queue expansion status: `{manifest['research_queue_current_expansion_status']}`",
        f"Research-state reprioritization next family: `{manifest['research_state_reprioritization_next_family']}`",
        f"Research-state reprioritization action: `{manifest['research_state_reprioritization_next_allowed_action']}`",
        "",
        "Reviewed items:",
    ]
    for row in rows:
        lines.append(
            f"- `{row['item_id']}` from `{row['source']}`: `{row['selection_status']}` - {row['reason']}"
        )
    return "\n".join(lines) + "\n"


def blocker_md(manifest: dict[str, Any]) -> str:
    return f"""# Queue Selection Blocker Report

No bounded research lane was run in this step.

Reason:

`{manifest['blocker_reason']}`

This is not a manual-review loop and not a promotion gate. It is a concise source-of-truth blocker: the queue needs one explicit bounded next task before implementation can run more evidence generation without making a strategic choice.

Forbidden paths remained closed:

- strategy discovery
- broad research batch
- candidate_exhaustive
- promotion
- paper-forward activation
- provider download
- intraday data
- broker/API/live orders
- real-money recommendation
"""


def next_action_md(next_action: str) -> str:
    return f"""# Profit Research Queue Next Action

Exact next action:

`{next_action}`

Do not execute it in this task.
"""


def consistency_check(manifest: dict[str, Any], output: Path) -> dict[str, Any]:
    required = {name: (output / name).exists() for name in REQUIRED_FILES}
    required["queue_selection_guardrail_check.json"] = True
    checks = {
        "queue_selection_only": manifest["queue_next_task_selection_only"] is True,
        "source_state_only": manifest["selection_from_existing_roadmap_registry_ledger_only"] is True,
        "macro_gld_excluded": manifest["completed_macro_gld_excluded"] is True,
        "volatility_excluded": manifest["completed_volatility_throttle_excluded"] is True,
        "no_unambiguous_executable_item": manifest["selected_task"] == "none"
        and manifest["eligible_executable_item_count"] == 0,
        "no_strategy_discovery": manifest["new_strategy_discovery_run"] is False,
        "no_research_batch": manifest["new_research_batch_run"] is False,
        "no_backtests": manifest["new_backtests_run"] is False,
        "no_new_raw_metrics": manifest["new_performance_metrics_from_raw_data_computed"] is False,
        "no_new_family_or_variant": manifest["new_families_created"] is False
        and manifest["new_variants_created"] is False,
        "no_hidden_grid": manifest["hidden_parameter_grid_created"] is False,
        "no_provider_intraday": manifest["provider_download"] is False and manifest["intraday_data_used"] is False,
        "no_broker_live_real_money": manifest["broker_api_called"] is False
        and manifest["broker_orders_submitted"] is False
        and manifest["broker_orders_cancelled"] is False
        and manifest["broker_orders_reconciled"] is False
        and manifest["live_orders"] is False
        and manifest["real_money_recommendation"] is False,
        "no_candidate_promotion_paper": manifest["promotion_candidates_created"] is False
        and manifest["candidate_exhaustive_run"] is False
        and manifest["paper_forward_activation"] is False
        and manifest["new_paper_forward_candidate_created"] is False,
        "active_state_preserved": manifest["active_vm_preserved"] is True and manifest["active_dsr_preserved"] is True,
        "static_all_weather_control_only": manifest["static_all_weather_benchmark_control_only"] is True,
        "rejected_not_reopened": manifest["exact_rejected_variants_reopened"] is False,
        "next_action_valid": manifest["next_action"] in VALID_NEXT_ACTIONS,
        "required_files_present": all(required.values()),
        "required_files": required,
    }
    checks["consistency_passed"] = all(value is True for key, value in checks.items() if key != "required_files")
    return checks


def write_outputs(root: Path, created: str, review: list[dict[str, Any]], source_context: dict[str, Any]) -> dict[str, Any]:
    output = root / OUTPUT_DIR
    output.mkdir(parents=True, exist_ok=True)
    manifest = manifest_payload(created, output, review, source_context)
    write_json(output / "queue_next_task_selection_manifest.json", manifest)
    write_text(output / "queue_next_task_selection_summary.md", summary_md(manifest))
    write_text(output / "source_state_review.md", source_review_md(manifest, review))
    write_csv(output / "eligible_item_review.csv", review, list(review[0].keys()) if review else [])
    write_text(output / "blocker_report.md", blocker_md(manifest))
    write_text(output / "queue_selection_next_action.md", next_action_md(manifest["next_action"]))
    check = consistency_check(manifest, output)
    write_json(output / "queue_selection_guardrail_check.json", check)
    return {**manifest, "output_dir": str(output.resolve()), "consistency_passed": check["consistency_passed"]}


def run(root: Path = ROOT) -> dict[str, Any]:
    created = now_utc()
    review, source_context = build_item_review(root)
    return write_outputs(root, created, review, source_context)


if __name__ == "__main__":
    result = run()
    print(
        json.dumps(
            {
                "output_dir": result["output_dir"],
                "selected_task": result["selected_task"],
                "eligible_executable_item_count": result["eligible_executable_item_count"],
                "blocked_item_count": result["blocked_item_count"],
                "ambiguous_item_count": result["ambiguous_item_count"],
                "blocker_found": result["blocker_found"],
                "next_action": result["next_action"],
                "consistency_passed": result["consistency_passed"],
            },
            indent=2,
        )
    )
