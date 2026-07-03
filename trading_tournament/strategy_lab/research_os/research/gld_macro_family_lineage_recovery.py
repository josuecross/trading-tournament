from __future__ import annotations

import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.objective_reset.objective_reset_review import write_json, write_text
from strategy_lab.research_os.research.profit_oriented_research_batch_v1 import write_csv


TASK_ID = "recover_gld_macro_family_lineage"
FAMILY_ID = "macro_gld_duration_risk_off"
OUTPUT_DIR = Path("evidence") / "research_recovery" / "gld_macro_family_lineage_recovery" / "latest"

LABEL_FIX_DIR = Path("evidence") / "research_recovery" / "profit_oriented_research_batch_v1_labeling_fix" / "latest"
LABEL_AUDIT_DIR = (
    Path("evidence") / "research_recovery" / "profit_oriented_research_batch_v1_labeling_fix_audit" / "latest"
)
LINEAGE_LEDGER = Path("strategy_lab") / "research_os" / "family_lineage" / "family_ledger.yaml"
ROADMAP = Path("strategy_lab") / "RESEARCH_ROADMAP.md"
REGISTRY = Path("strategy_lab") / "strategy_registry.yaml"

NEXT_ACTION_DESIGN = "design_macro_gld_duration_risk_off_bounded_research_lane"
NEXT_ACTION_BLOCKED = "block_macro_gld_research_until_lineage_inputs_completed"
VALID_NEXT_ACTIONS = {NEXT_ACTION_DESIGN, NEXT_ACTION_BLOCKED}

KEYWORDS = (
    "gld",
    "gold",
    "macro",
    "risk_off",
    "risk-off",
    "risk_on",
    "risk-on",
    "gror",
    "global_risk_on_risk_off",
    "all_weather",
    "duration",
)

REQUIRED_OUTPUT_FILES = (
    "gld_macro_lineage_recovery_manifest.json",
    "gld_macro_lineage_recovery_summary.md",
    "selected_task_rationale.md",
    "source_evidence_inventory.md",
    "corrected_macro_rows.csv",
    "lineage_recovery_table.csv",
    "registry_macro_gld_snippets.md",
    "historical_decision_timeline.md",
    "lineage_recovery_findings.md",
    "blockers_and_data_gaps.md",
    "do_not_promote_from_lineage_recovery.md",
    "gld_macro_lineage_recovery_next_action.md",
    "gld_macro_lineage_recovery_consistency_check.json",
)

MACRO_ROW_FIELDS = (
    "variant_id",
    "family_id",
    "universe",
    "total_return",
    "cagr",
    "max_drawdown",
    "portfolio_contribution_score",
    "lineage_status",
    "research_label",
    "promotion_eligibility",
    "paper_forward_eligibility",
)

LINEAGE_FIELDS = (
    "variant_id",
    "family_id",
    "lineage_status_before_recovery",
    "lineage_status_after_recovery",
    "research_label",
    "historical_evidence_source",
    "current_interpretation",
    "promotion_eligibility",
    "paper_forward_eligibility",
)


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def parse_float(value: Any, default: float = float("nan")) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_registry_blocks(text: str) -> list[dict[str, str]]:
    blocks = re.split(r"(?m)^- id:\s*", text)
    entries: list[dict[str, str]] = []
    for raw in blocks[1:]:
        lines = raw.splitlines()
        if not lines:
            continue
        entry_id = lines[0].strip()
        block = "- id: " + raw
        if not any(keyword in block.lower() for keyword in KEYWORDS):
            continue
        fields = {
            "id": entry_id,
            "strategy_family": extract_yaml_scalar(block, "strategy_family"),
            "status": extract_yaml_scalar(block, "status"),
            "current_status": extract_yaml_scalar(block, "current_status"),
            "latest_evidence_path": extract_yaml_scalar(block, "latest_evidence_path"),
            "allowed_next_action": extract_yaml_scalar(block, "allowed_next_action"),
            "candidate_exhaustive_run": extract_yaml_scalar(block, "candidate_exhaustive_run"),
            "paper_forward_active": extract_yaml_scalar(block, "paper_forward_active"),
            "real_money_recommendation": extract_yaml_scalar(block, "real_money_recommendation"),
        }
        entries.append(fields)
    return entries


def extract_yaml_scalar(block: str, key: str) -> str:
    match = re.search(rf"(?m)^\s*{re.escape(key)}:\s*(.*)$", block)
    return match.group(1).strip().strip("'\"") if match else ""


def load_sources(root: Path) -> dict[str, Any]:
    corrected_rows = read_csv_rows(root / LABEL_FIX_DIR / "corrected_label_variant_results.csv")
    family_summary = read_csv_rows(root / LABEL_FIX_DIR / "corrected_label_family_summary.csv")
    label_audit = read_json(root / LABEL_AUDIT_DIR / "labeling_fix_audit_manifest.json")
    registry_text = read_text(root / REGISTRY)
    roadmap_text = read_text(root / ROADMAP)
    ledger_text = read_text(root / LINEAGE_LEDGER)
    macro_rows = [row for row in corrected_rows if row.get("family_id") == FAMILY_ID]
    macro_family = [row for row in family_summary if row.get("family_id") == FAMILY_ID]
    registry_entries = parse_registry_blocks(registry_text)
    return {
        "corrected_rows": corrected_rows,
        "family_summary": family_summary,
        "macro_rows": macro_rows,
        "macro_family": macro_family[0] if macro_family else {},
        "label_audit": label_audit,
        "macro_label_status": read_text(root / LABEL_FIX_DIR / "macro_gld_lineage_label_status.md"),
        "macro_direction_review": read_text(root / LABEL_AUDIT_DIR / "macro_gld_lineage_direction_review.md"),
        "ledger_text": ledger_text,
        "roadmap_text": roadmap_text,
        "registry_entries": registry_entries,
    }


def source_inventory(root: Path) -> list[dict[str, Any]]:
    paths = [
        root / LABEL_FIX_DIR / "corrected_label_variant_results.csv",
        root / LABEL_FIX_DIR / "corrected_label_family_summary.csv",
        root / LABEL_FIX_DIR / "macro_gld_lineage_label_status.md",
        root / LABEL_AUDIT_DIR / "macro_gld_lineage_direction_review.md",
        root / LABEL_AUDIT_DIR / "labeling_fix_audit_manifest.json",
        root / LINEAGE_LEDGER,
        root / ROADMAP,
        root / REGISTRY,
        root / "evidence" / "parallel_research_discovery" / "second_expansion_with_lane_framework" / "latest",
        root / "evidence" / "parallel_research_discovery" / "third_expansion_with_lane_framework" / "latest",
        root / "evidence" / "benchmark_controls" / "static_all_weather_benchmark_v1" / "latest",
    ]
    return [
        {
            "path": str(path.resolve()),
            "exists": path.exists(),
            "kind": "directory" if path.is_dir() else "file",
        }
        for path in paths
    ]


def macro_output_rows(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        out.append({field: row.get(field, "") for field in MACRO_ROW_FIELDS})
    return out


def lineage_rows(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        out.append(
            {
                "variant_id": row.get("variant_id", ""),
                "family_id": row.get("family_id", ""),
                "lineage_status_before_recovery": row.get("lineage_status", ""),
                "lineage_status_after_recovery": "lineage_recovered_context_only_not_reopened",
                "research_label": row.get("research_label", ""),
                "historical_evidence_source": str((ROOT / LABEL_FIX_DIR / "corrected_label_variant_results.csv").resolve()),
                "current_interpretation": "macro_gld_existing_research_row_visible_for_future_bounded_design_only",
                "promotion_eligibility": row.get("promotion_eligibility", "False"),
                "paper_forward_eligibility": row.get("paper_forward_eligibility", "False"),
            }
        )
    return out


def selected_task_rationale_md() -> str:
    return """# Selected Task Rationale

Selected task: `recover_gld_macro_family_lineage`

Selection basis from existing project state:

- The completed volatility-throttle lane is excluded from this step by direction-owner instruction.
- The family ledger marks `gld_macro_risk_off` as `lineage_recovery_needed`.
- The family ledger lists `recover_gld_macro_family_lineage` as the required next review before reopening macro/GLD research.
- The profit batch v1 labeling-fix audit records `macro_gld_lineage_recovery_supported: true`.
- Corrected batch v1 evidence contains `10` `macro_gld_duration_risk_off` rows, all labeled lineage-blocked research-only.

This task does not create a new family, run broad discovery, tune thresholds, promote a result, or activate paper-forward.
"""


def source_inventory_md(inventory: list[dict[str, Any]]) -> str:
    lines = ["# Source Evidence Inventory", ""]
    for row in inventory:
        lines.append(f"- `{row['path']}`: exists `{row['exists']}`, kind `{row['kind']}`")
    return "\n".join(lines) + "\n"


def registry_snippets_md(entries: list[dict[str, str]]) -> str:
    lines = ["# Registry Macro / GLD Snippets", "", f"Relevant registry entries found: `{len(entries)}`", ""]
    for row in entries:
        lines.append(
            f"- `{row['id']}`: family `{row['strategy_family']}`, status `{row['status'] or row['current_status']}`, "
            f"allowed next `{row['allowed_next_action']}`, evidence `{row['latest_evidence_path']}`"
        )
    return "\n".join(lines) + "\n"


def timeline_md() -> str:
    return """# Historical Decision Timeline

- `second_expansion_with_lane_framework`: included `gld_gror_balanced_momentum_clean_v1`; rejected with no promotion candidate.
- `third_expansion_with_lane_framework`: included `gld_ief_spy_defensive_rotation_v1` and `static_all_weather_benchmark_v1`; GLD/IEF/SPY defensive rotation rejected, static all-weather accepted as benchmark/control only.
- `static_all_weather_benchmark_v1`: preserved as benchmark/control only for macro, diversifier, conservative allocation, and portfolio-contribution reviews.
- `profit_oriented_research_batch_v1_labeling_fix`: relabeled Macro/GLD rows as `research_signal_lineage_blocked`.
- `profit_oriented_research_batch_v1_labeling_fix_audit`: accepted label fix and recorded Macro/GLD lineage recovery as supported.
- `family_ledger.yaml`: requires `recover_gld_macro_family_lineage` before reopening macro/GLD research.
"""


def findings_md(rows: list[dict[str, Any]], family_summary: dict[str, str]) -> str:
    median_cagr = family_summary.get("median_cagr", "")
    median_drawdown = family_summary.get("median_max_drawdown", "")
    contribution = family_summary.get("median_portfolio_contribution_score", "")
    return f"""# Lineage Recovery Findings

Macro/GLD corrected rows recovered: `{len(rows)}`

Median corrected family CAGR: `{median_cagr}`

Median corrected family max drawdown: `{median_drawdown}`

Median corrected portfolio contribution score: `{contribution}`

All recovered rows remain diagnostic/non-promotable. The recovery makes the family lineage visible enough for a future bounded design step, but it does not reopen exact rejected variants or approve paper-forward/demo/live use.
"""


def blockers_md(inventory: list[dict[str, Any]], rows: list[dict[str, Any]]) -> str:
    missing = [row["path"] for row in inventory if not row["exists"]]
    return f"""# Blockers And Data Gaps

Missing source evidence paths: `{len(missing)}`

Recovered Macro/GLD rows: `{len(rows)}`

Lineage blocker after this packet:

- Promotion remains blocked.
- Paper-forward remains blocked.
- Exact rejected variants remain closed.
- Future research still requires a separate bounded design/preregistration step.

Missing paths:

{chr(10).join(f'- `{path}`' for path in missing) if missing else '- None'}
"""


def do_not_promote_md() -> str:
    return """# Do Not Promote From Lineage Recovery

This packet is lineage/evidence recovery only.

It creates no:

- strategy discovery
- new family
- new variant
- promotion-review candidate
- candidate_exhaustive candidate
- paper-forward candidate
- paper-forward activation
- broker/live action
- real-money recommendation
"""


def next_action_md(next_action: str) -> str:
    return f"""# GLD / Macro Lineage Recovery Next Action

Exact next action:

`{next_action}`

Do not run the next action in this task.
"""


def build_manifest(created: str, output: Path, sources: dict[str, Any], inventory: list[dict[str, Any]], rows: list[dict[str, Any]]) -> dict[str, Any]:
    missing_sources = [row for row in inventory if not row["exists"]]
    label_audit = sources["label_audit"]
    ledger_support = "recover_gld_macro_family_lineage" in sources["ledger_text"]
    lineage_recovery_supported = label_audit.get("macro_gld_lineage_recovery_supported") is True
    all_rows_non_promotable = all(str(row.get("promotion_eligibility", "")).lower() == "false" for row in rows)
    all_rows_not_paper = all(str(row.get("paper_forward_eligibility", "")).lower() == "false" for row in rows)
    completed = (
        lineage_recovery_supported
        and ledger_support
        and len(rows) == 10
        and all_rows_non_promotable
        and all_rows_not_paper
        and not missing_sources
    )
    next_action = NEXT_ACTION_DESIGN if completed else NEXT_ACTION_BLOCKED
    return {
        "created_utc": created,
        "evidence_path": str(output.resolve()),
        "selected_task": TASK_ID,
        "selected_family": FAMILY_ID,
        "selection_from_existing_roadmap_registry_only": True,
        "volatility_throttle_lane_excluded": True,
        "lineage_recovery_only": True,
        "historical_evidence_generation_only": True,
        "new_strategy_discovery_run": False,
        "new_research_batch_run": False,
        "new_backtests_run": False,
        "new_performance_metrics_from_raw_data_computed": False,
        "new_variants_created": False,
        "new_families_created": False,
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
        "best_single_variant_promoted": False,
        "research_outputs_remain_non_promotable": True,
        "active_vm_preserved": True,
        "active_dsr_preserved": True,
        "static_all_weather_benchmark_control_only": True,
        "exact_rejected_variants_reopened": False,
        "alpaca_execution_module_delegated": True,
        "lineage_recovery_supported_by_label_audit": lineage_recovery_supported,
        "ledger_requires_recovery_before_reopening": ledger_support,
        "macro_rows_recovered_count": len(rows),
        "all_recovered_rows_non_promotable": all_rows_non_promotable,
        "all_recovered_rows_not_paper_forward": all_rows_not_paper,
        "source_evidence_missing_count": len(missing_sources),
        "usable_diagnostic_evidence": completed,
        "lineage_recovery_completed": completed,
        "next_action": next_action,
    }


def summary_md(manifest: dict[str, Any]) -> str:
    return f"""# GLD / Macro Family Lineage Recovery

Selected task: `{manifest['selected_task']}`

Selected family: `{manifest['selected_family']}`

Macro rows recovered: `{manifest['macro_rows_recovered_count']}`

Lineage recovery supported by label audit: `{manifest['lineage_recovery_supported_by_label_audit']}`

Ledger requires recovery before reopening: `{manifest['ledger_requires_recovery_before_reopening']}`

Source evidence missing count: `{manifest['source_evidence_missing_count']}`

Usable diagnostic evidence: `{manifest['usable_diagnostic_evidence']}`

Lineage recovery completed: `{manifest['lineage_recovery_completed']}`

No promotion, paper-forward, candidate_exhaustive, provider download, intraday, broker/live, or real-money path occurred.

Exact next action: `{manifest['next_action']}`
"""


def consistency_check(manifest: dict[str, Any], output: Path) -> dict[str, Any]:
    required = {name: (output / name).exists() for name in REQUIRED_OUTPUT_FILES}
    required["gld_macro_lineage_recovery_consistency_check.json"] = True
    checks = {
        "selected_task_correct": manifest["selected_task"] == TASK_ID,
        "selected_family_correct": manifest["selected_family"] == FAMILY_ID,
        "selection_from_existing_state": manifest["selection_from_existing_roadmap_registry_only"] is True,
        "volatility_lane_excluded": manifest["volatility_throttle_lane_excluded"] is True,
        "lineage_recovery_only": manifest["lineage_recovery_only"] is True,
        "no_discovery": manifest["new_strategy_discovery_run"] is False,
        "no_new_batch_or_backtests": manifest["new_research_batch_run"] is False and manifest["new_backtests_run"] is False,
        "no_raw_metrics": manifest["new_performance_metrics_from_raw_data_computed"] is False,
        "no_new_variants_or_families": manifest["new_variants_created"] is False and manifest["new_families_created"] is False,
        "no_hidden_grid": manifest["hidden_parameter_grid_created"] is False,
        "no_provider_download": manifest["provider_download"] is False,
        "no_intraday": manifest["intraday_data_used"] is False,
        "no_broker": manifest["broker_api_called"] is False
        and manifest["broker_orders_submitted"] is False
        and manifest["broker_orders_cancelled"] is False
        and manifest["broker_orders_reconciled"] is False,
        "no_live_or_real_money": manifest["live_orders"] is False and manifest["real_money_recommendation"] is False,
        "no_promotion_candidate_exhaustive_or_paper": manifest["promotion_candidates_created"] is False
        and manifest["candidate_exhaustive_run"] is False
        and manifest["paper_forward_activation"] is False
        and manifest["new_paper_forward_candidate_created"] is False,
        "active_state_preserved": manifest["active_vm_preserved"] is True and manifest["active_dsr_preserved"] is True,
        "static_all_weather_control_only": manifest["static_all_weather_benchmark_control_only"] is True,
        "rejected_not_reopened": manifest["exact_rejected_variants_reopened"] is False,
        "lineage_supported": manifest["lineage_recovery_supported_by_label_audit"] is True,
        "ledger_requires_recovery": manifest["ledger_requires_recovery_before_reopening"] is True,
        "macro_rows_recovered": manifest["macro_rows_recovered_count"] == 10,
        "rows_non_promotable": manifest["all_recovered_rows_non_promotable"] is True,
        "rows_not_paper": manifest["all_recovered_rows_not_paper_forward"] is True,
        "next_action_valid": manifest["next_action"] in VALID_NEXT_ACTIONS,
        "required_files_present": all(required.values()),
        "required_files": required,
    }
    checks["consistency_passed"] = all(value is True for key, value in checks.items() if key != "required_files")
    return checks


def write_outputs(root: Path, created: str, sources: dict[str, Any]) -> dict[str, Any]:
    output = root / OUTPUT_DIR
    output.mkdir(parents=True, exist_ok=True)
    inventory = source_inventory(root)
    macro_rows = macro_output_rows(sources["macro_rows"])
    recovered = lineage_rows(sources["macro_rows"])
    manifest = build_manifest(created, output, sources, inventory, macro_rows)
    write_json(output / "gld_macro_lineage_recovery_manifest.json", manifest)
    write_text(output / "gld_macro_lineage_recovery_summary.md", summary_md(manifest))
    write_text(output / "selected_task_rationale.md", selected_task_rationale_md())
    write_text(output / "source_evidence_inventory.md", source_inventory_md(inventory))
    write_csv(output / "corrected_macro_rows.csv", macro_rows, list(MACRO_ROW_FIELDS))
    write_csv(output / "lineage_recovery_table.csv", recovered, list(LINEAGE_FIELDS))
    write_text(output / "registry_macro_gld_snippets.md", registry_snippets_md(sources["registry_entries"]))
    write_text(output / "historical_decision_timeline.md", timeline_md())
    write_text(output / "lineage_recovery_findings.md", findings_md(macro_rows, sources["macro_family"]))
    write_text(output / "blockers_and_data_gaps.md", blockers_md(inventory, macro_rows))
    write_text(output / "do_not_promote_from_lineage_recovery.md", do_not_promote_md())
    write_text(output / "gld_macro_lineage_recovery_next_action.md", next_action_md(manifest["next_action"]))
    consistency = consistency_check(manifest, output)
    write_json(output / "gld_macro_lineage_recovery_consistency_check.json", consistency)
    return {**manifest, "output_dir": str(output.resolve()), "consistency_passed": consistency["consistency_passed"]}


def run(root: Path = ROOT) -> dict[str, Any]:
    created = now_utc()
    sources = load_sources(root)
    return write_outputs(root, created, sources)


if __name__ == "__main__":
    result = run()
    print(
        json.dumps(
            {
                "output_dir": result["output_dir"],
                "selected_task": result["selected_task"],
                "selected_family": result["selected_family"],
                "macro_rows_recovered_count": result["macro_rows_recovered_count"],
                "usable_diagnostic_evidence": result["usable_diagnostic_evidence"],
                "next_action": result["next_action"],
                "consistency_passed": result["consistency_passed"],
            },
            indent=2,
        )
    )
