from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.objective_reset.objective_reset_review import write_json, write_text
from strategy_lab.research_os.research.profit_oriented_research_batch_v1 import write_csv


SOURCE_ID = "cci_correction"
FAMILY_ID = "equity_index_cci_pullback_trend_bias"
LANE_ID = "public_source_cci_correction_bounded_bt_lane_v1"

INTAKE_DIR = Path("evidence") / "research_recovery" / "public_source_intake_validation" / "latest"
BATCH_INTAKE_DIR = Path("evidence") / "research_recovery" / "public_source_batch_intake_validation" / "latest"
DESIGN_DIR = Path("evidence") / "research_recovery" / "public_source_cci_correction_bounded_bt_design" / "latest"
RUN_DIR = Path("evidence") / "research_recovery" / "public_source_cci_correction_bounded_bt_run" / "latest"
AUDIT_DIR = (
    Path("evidence")
    / "research_recovery"
    / "public_source_cci_correction_bounded_bt_results_audit"
    / "latest"
)
OUTPUT_DIR = (
    Path("evidence")
    / "research_recovery"
    / "public_source_cci_correction_final_state_reconciliation"
    / "latest"
)

INTAKE_MANIFEST = INTAKE_DIR / "public_source_intake_validation_manifest.json"
BATCH_INTAKE_DECISIONS = BATCH_INTAKE_DIR / "eligibility_decisions.csv"
DESIGN_MANIFEST = DESIGN_DIR / "public_source_cci_correction_bounded_bt_design_manifest.json"
RUN_MANIFEST = RUN_DIR / "public_source_cci_correction_bounded_bt_run_manifest.json"
RUN_ROWS = RUN_DIR / "row_level_results.csv"
AUDIT_MANIFEST = AUDIT_DIR / "public_source_cci_correction_bounded_bt_results_audit_manifest.json"

FINAL_STATUS = "completed_diagnostic_control_weak_context_only_no_continuation_authorized"
NEXT_ACTION = "direction_owner_select_next_public_source_candidate"
STALE_POINTERS = (
    "audit_public_source_cci_correction_bounded_bt_results",
    "direction_owner_review_required_after_cci_control_weak_results_audit",
    "create_public_source_cci_correction_robustness_report",
    "run_public_source_cci_correction_robustness",
    "audit_public_source_cci_correction_robustness_results",
)

STATUS_FILES_TO_SCAN = (
    Path("strategy_lab") / "RESEARCH_ROADMAP.md",
    Path("strategy_lab") / "strategy_registry.yaml",
    Path("strategy_lab") / "research_os" / "research" / "research_queue.yaml",
    Path("evidence") / "research_state" / "latest" / "research_state_manifest.json",
    Path("evidence") / "research_state" / "latest" / "current_research_state.md",
)

REQUIRED_FILES = (
    "public_source_cci_correction_final_state_reconciliation_manifest.json",
    "public_source_cci_correction_final_state_reconciliation_summary.md",
    "evidence_paths_inspected.md",
    "evidence_chain_status.csv",
    "evidence_chain_status.md",
    "cci_correction_current_status.md",
    "no_continuation_reasons.md",
    "queue_status_review.md",
    "guardrail_checklist.json",
    "status_file_scan.csv",
    "public_source_cci_correction_final_state_reconciliation_next_action.md",
    "public_source_cci_correction_final_state_reconciliation_consistency_check.json",
)


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() == "true"


def parse_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def batch_decision(rows: list[dict[str, str]]) -> str:
    for row in rows:
        if row.get("source_id") == SOURCE_ID or row.get("candidate_id") == SOURCE_ID:
            return row.get("eligibility_decision") or row.get("decision") or ""
    return "not_found_in_batch_decisions"


def primary_run_row(rows: list[dict[str, str]]) -> dict[str, str]:
    return next((row for row in rows if row.get("variant_id") == "cci_correction_spy_bil_primary_v1"), {})


def guardrails() -> dict[str, bool]:
    return {
        "cci_robustness_run": False,
        "cci_backtest_rerun": False,
        "cci_results_reaudit": False,
        "cci_periods_tuned": False,
        "cci_thresholds_tuned": False,
        "cci_timing_tuned": False,
        "cci_exit_logic_tuned": False,
        "daily_only_variants_added": False,
        "weekly_only_variants_added": False,
        "alternate_cci_periods_added": False,
        "alternate_thresholds_added": False,
        "alternate_exits_added": False,
        "filters_added": False,
        "stop_loss_or_profit_target_added": False,
        "short_or_inverse_exposure_added": False,
        "new_variants_created": False,
        "next_public_source_selected_by_codex": False,
        "public_source_scraped": False,
        "public_strategy_list_ingested": False,
        "coppock_continued": False,
        "larry_connors_continued": False,
        "percent_b_continued": False,
        "turn_of_month_continued": False,
        "faber_taa_continued": False,
        "provider_download": False,
        "intraday_data_used": False,
        "new_packages_installed": False,
        "strategy_discovery_run": False,
        "candidate_exhaustive_run": False,
        "promotion_candidates_created": False,
        "best_single_variant_promoted": False,
        "paper_demo_observation_activated": False,
        "broker_api_called": False,
        "broker_orders_submitted": False,
        "broker_orders_cancelled": False,
        "broker_orders_reconciled": False,
        "live_orders": False,
        "real_money_recommendation": False,
    }


def evidence_paths(root: Path) -> list[dict[str, Any]]:
    paths = [
        ("intake_evidence", INTAKE_DIR),
        ("batch_intake_evidence", BATCH_INTAKE_DIR),
        ("design_evidence", DESIGN_DIR),
        ("bounded_run_evidence", RUN_DIR),
        ("results_audit_evidence", AUDIT_DIR),
        ("intake_manifest", INTAKE_MANIFEST),
        ("batch_intake_decisions", BATCH_INTAKE_DECISIONS),
        ("design_manifest", DESIGN_MANIFEST),
        ("run_manifest", RUN_MANIFEST),
        ("run_row_level_results", RUN_ROWS),
        ("results_audit_manifest", AUDIT_MANIFEST),
    ]
    return [
        {
            "name": name,
            "path": str((root / relative).resolve()),
            "exists": (root / relative).exists(),
        }
        for name, relative in paths
    ]


def scan_status_files(root: Path) -> list[dict[str, str]]:
    matches: list[dict[str, str]] = []
    for relative_path in STATUS_FILES_TO_SCAN:
        path = root / relative_path
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for stale_pointer in STALE_POINTERS:
            if stale_pointer in text:
                matches.append(
                    {
                        "path": str(relative_path),
                        "matched_text": stale_pointer,
                        "action": "not_updated_by_reconciliation_runner",
                        "reason": "no_safe_automatic_queue_status_update_convention_used",
                    }
                )
    return matches


def evidence_chain_rows(
    intake_manifest: dict[str, Any],
    batch_rows: list[dict[str, str]],
    design_manifest: dict[str, Any],
    run_manifest: dict[str, Any],
    audit_manifest: dict[str, Any],
) -> list[dict[str, Any]]:
    return [
        {
            "stage": "intake",
            "status": intake_manifest.get("eligibility_decision", ""),
            "passed": intake_manifest.get("source_id") == SOURCE_ID
            and intake_manifest.get("eligibility_decision") == "eligible_for_bounded_bt_design",
            "evidence_path": intake_manifest.get("evidence_path", ""),
            "notes": "single-source intake eligible; public-source presence is context only",
        },
        {
            "stage": "batch_intake",
            "status": batch_decision(batch_rows),
            "passed": batch_decision(batch_rows) == "eligible_for_bounded_bt_design",
            "evidence_path": str((ROOT / BATCH_INTAKE_DIR).resolve()),
            "notes": "batch intake decision inspected for CCI",
        },
        {
            "stage": "bounded_design",
            "status": design_manifest.get("run_readiness_decision", ""),
            "passed": design_manifest.get("run_readiness_decision")
            == "public_source_cci_correction_bounded_bt_design_run_ready",
            "evidence_path": design_manifest.get("evidence_path", ""),
            "notes": "design run-ready with source-backed CCI parameters",
        },
        {
            "stage": "bounded_run",
            "status": "completed_primary_base_passed" if run_manifest.get("primary_row_numeric_criteria_pass") else "run_missing_or_failed",
            "passed": run_manifest.get("public_source_cci_correction_bounded_bt_lane_run") is True
            and run_manifest.get("variant_count_evaluated") == 5
            and run_manifest.get("results_interpretable") is True
            and run_manifest.get("usable_diagnostic_evidence") is True
            and run_manifest.get("primary_row_numeric_criteria_pass") is True,
            "evidence_path": run_manifest.get("evidence_path", ""),
            "notes": "bounded run completed exact five rows; diagnostic non-promotable",
        },
        {
            "stage": "results_audit",
            "status": audit_manifest.get("audit_decision", ""),
            "passed": audit_manifest.get("audit_decision")
            == "public_source_cci_correction_results_passed_but_control_weak"
            and audit_manifest.get("total_discrepancy_count") == 0
            and audit_manifest.get("criteria_recomputation_passed") is True
            and audit_manifest.get("exposure_invariant_audit_passed") is True,
            "evidence_path": audit_manifest.get("evidence_path", ""),
            "notes": "mechanics passed; serious SPY/SPY_200d control weakness recorded",
        },
        {
            "stage": "final_closeout",
            "status": FINAL_STATUS,
            "passed": True,
            "evidence_path": str((ROOT / OUTPUT_DIR).resolve()),
            "notes": "direction-owner decision closes CCI as diagnostic/control-weak/context-only",
        },
    ]


def no_continuation_reasons(audit_manifest: dict[str, Any]) -> dict[str, Any]:
    control = audit_manifest.get("control_comparison", {})
    return {
        "spy_buy_hold_total_return_materially_exceeded_primary": control.get(
            "primary_underperforms_spy_buy_hold_total_return"
        )
        is True,
        "spy200d_total_return_exceeded_primary": control.get("primary_underperforms_spy200d_total_return") is True,
        "spy200d_max_drawdown_better_than_primary": control.get("primary_underperforms_spy200d_max_drawdown") is True,
        "spy200d_return_drawdown_proxy_better_than_primary": control.get(
            "primary_underperforms_spy200d_return_drawdown_proxy"
        )
        is True,
        "audit_serious_interpretation_weakness": audit_manifest.get("serious_interpretation_weakness") is True,
        "timing_sanity_context_only": audit_manifest.get("timing_sanity_context_only") is True,
        "similarity_to_equity_timing_controls_weakens_interpretation": audit_manifest.get("similarity_contexts_preserved")
        is True
        and audit_manifest.get("spy200d_control_dominates_primary") is True,
    }


def build_manifest(root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    intake_manifest = read_json(root / INTAKE_MANIFEST)
    batch_rows = read_csv_rows(root / BATCH_INTAKE_DECISIONS)
    design_manifest = read_json(root / DESIGN_MANIFEST)
    run_manifest = read_json(root / RUN_MANIFEST)
    run_rows = read_csv_rows(root / RUN_ROWS)
    audit_manifest = read_json(root / AUDIT_MANIFEST)
    primary = primary_run_row(run_rows)
    chain = evidence_chain_rows(intake_manifest, batch_rows, design_manifest, run_manifest, audit_manifest)
    reasons = no_continuation_reasons(audit_manifest)
    status_matches = scan_status_files(root)
    guardrail_payload = guardrails()
    final_locked = all(parse_bool(row["passed"]) for row in chain) and all(reasons.values())
    control = audit_manifest.get("control_comparison", {})
    manifest = {
        "created_utc": now_utc(),
        "evidence_path": str((root / OUTPUT_DIR).resolve()),
        "public_source_cci_correction_final_state_reconciliation_only": True,
        "source_id": SOURCE_ID,
        "family_id": FAMILY_ID,
        "lane_id": LANE_ID,
        "final_status_locked": final_locked,
        "final_cci_correction_status": FINAL_STATUS if final_locked else "final_state_reconciliation_incomplete",
        "final_authorized_next_action": NEXT_ACTION,
        "intake_eligible": chain[0]["passed"],
        "batch_intake_decision": chain[1]["status"],
        "design_run_ready": chain[2]["passed"],
        "bounded_run_completed": run_manifest.get("public_source_cci_correction_bounded_bt_lane_run") is True,
        "bounded_run_exact_5_rows": run_manifest.get("variant_count_evaluated") == 5,
        "run_interpretable": run_manifest.get("results_interpretable") is True,
        "run_usable_diagnostic_evidence": run_manifest.get("usable_diagnostic_evidence") is True,
        "run_primary_base_criteria_pass": run_manifest.get("primary_row_numeric_criteria_pass") is True,
        "results_audit_mechanics_passed": audit_manifest.get("total_discrepancy_count") == 0
        and audit_manifest.get("criteria_recomputation_passed") is True
        and audit_manifest.get("exposure_invariant_audit_passed") is True,
        "results_audit_decision": audit_manifest.get("audit_decision", ""),
        "serious_interpretation_weakness": audit_manifest.get("serious_interpretation_weakness") is True,
        "primary_numeric_criteria_pass": audit_manifest.get("primary_numeric_criteria_pass_recomputed") is True,
        "primary_total_return": control.get("primary_total_return"),
        "spy_buy_hold_total_return": control.get("spy_buy_hold_total_return"),
        "spy200d_total_return": control.get("spy200d_total_return"),
        "primary_max_drawdown": control.get("primary_max_drawdown"),
        "spy200d_max_drawdown": control.get("spy200d_max_drawdown"),
        "primary_return_drawdown_proxy": control.get("primary_return_drawdown_proxy"),
        "spy200d_return_drawdown_proxy": control.get("spy200d_return_drawdown_proxy"),
        "spy200d_dominates_primary_metric_count": control.get("spy200d_dominates_primary_metric_count"),
        "timing_sanity_context_only": audit_manifest.get("timing_sanity_context_only") is True,
        "long_only_adaptation_verified": audit_manifest.get("long_only_adaptation_preserved") is True,
        "similarity_contexts_preserved": audit_manifest.get("similarity_contexts_preserved") is True,
        "specific_duplicate_or_do_not_retest_match_discovered": audit_manifest.get(
            "specific_duplicate_or_do_not_retest_match_discovered"
        )
        is True,
        "not_promotable": True,
        "not_candidate_exhaustive_ready": True,
        "not_paper_demo_eligible": True,
        "not_broker_live_eligible": True,
        "not_real_money_relevant": True,
        "continuation_authorized": False,
        "robustness_run_authorized": False,
        "results_reaudit_authorized": False,
        "rerun_authorized": False,
        "parameter_tuning_authorized": False,
        "daily_weekly_variant_expansion_authorized": False,
        "alternate_exits_filters_stops_authorized": False,
        "short_inverse_exposure_authorized": False,
        "candidate_exhaustive_authorized": False,
        "promotion_authorized": False,
        "paper_demo_activation_authorized": False,
        "broker_live_action_authorized": False,
        "queue_status_file_updated": False,
        "queue_status_update_reason": "no_safe_automatic_queue_status_update_convention_used",
        "stale_status_pointer_count": len(status_matches),
        "primary_research_label": primary.get("research_only_label", primary.get("research_label", "")),
        "outputs_diagnostic_only": True,
        "outputs_non_promotable": True,
        **guardrail_payload,
        "next_action": NEXT_ACTION,
    }
    context = {
        "chain": chain,
        "reasons": reasons,
        "status_matches": status_matches,
        "guardrails": guardrail_payload,
        "evidence_paths": evidence_paths(root),
    }
    return manifest, context


def evidence_paths_md(paths: list[dict[str, Any]]) -> str:
    lines = ["# Evidence Paths Inspected", ""]
    for item in paths:
        lines.append(f"- `{item['name']}`: `{item['path']}` exists `{item['exists']}`")
    return "\n".join(lines) + "\n"


def evidence_chain_md(rows: list[dict[str, Any]]) -> str:
    lines = ["# Evidence Chain Status", ""]
    for row in rows:
        lines.append(f"- `{row['stage']}`: `{row['status']}`; passed `{row['passed']}`")
        lines.append(f"  - Notes: {row['notes']}")
    return "\n".join(lines) + "\n"


def current_status_md(manifest: dict[str, Any]) -> str:
    return f"""# CCI Correction Current Status

Final status: `{manifest['final_cci_correction_status']}`

This source is diagnostic/context-only. It is not promotable, not candidate_exhaustive-ready, not paper/demo eligible, not broker/live eligible, and not real-money relevant.

Primary numeric criteria passed: `{manifest['primary_numeric_criteria_pass']}`
Serious interpretation weakness: `{manifest['serious_interpretation_weakness']}`
SPY_200d dominated primary metric count: `{manifest['spy200d_dominates_primary_metric_count']}`
"""


def no_continuation_md(reasons: dict[str, Any]) -> str:
    lines = ["# No Continuation Reasons", ""]
    for key, value in reasons.items():
        lines.append(f"- `{key}`: `{value}`")
    lines.append("")
    lines.append(
        "No robustness run, rerun, re-audit, parameter tuning, alternate CCI design, candidate_exhaustive, promotion, paper/demo activation, broker/live action, or real-money recommendation is authorized by this closeout."
    )
    return "\n".join(lines) + "\n"


def queue_status_md(manifest: dict[str, Any], matches: list[dict[str, str]]) -> str:
    lines = ["# Queue Status Review", ""]
    lines.append(f"Queue/status file updated: `{manifest['queue_status_file_updated']}`")
    lines.append(f"Update reason: `{manifest['queue_status_update_reason']}`")
    lines.append(f"Stale CCI continuation pointer count: `{manifest['stale_status_pointer_count']}`")
    if matches:
        for match in matches:
            lines.append(f"- `{match['path']}` contains `{match['matched_text']}`; action `{match['action']}`")
    else:
        lines.append("- No stale CCI continuation pointer was found in scanned status files.")
    lines.append("")
    lines.append(f"Final authorized next action recorded by reconciliation: `{manifest['final_authorized_next_action']}`")
    return "\n".join(lines) + "\n"


def summary_md(manifest: dict[str, Any]) -> str:
    return f"""# CCI Correction Final State Reconciliation

Source ID: `{manifest['source_id']}`
Lane ID: `{manifest['lane_id']}`

Evidence chain locked: `{manifest['final_status_locked']}`
Final status: `{manifest['final_cci_correction_status']}`

Mechanics passed in results audit: `{manifest['results_audit_mechanics_passed']}`
Results audit decision: `{manifest['results_audit_decision']}`
Serious control-comparison weakness: `{manifest['serious_interpretation_weakness']}`

Primary total return: `{manifest['primary_total_return']}`
SPY buy-hold total return: `{manifest['spy_buy_hold_total_return']}`
SPY_200d total return: `{manifest['spy200d_total_return']}`
Primary max drawdown: `{manifest['primary_max_drawdown']}`
SPY_200d max drawdown: `{manifest['spy200d_max_drawdown']}`
Primary return/drawdown proxy: `{manifest['primary_return_drawdown_proxy']}`
SPY_200d return/drawdown proxy: `{manifest['spy200d_return_drawdown_proxy']}`

Queue/status file updated: `{manifest['queue_status_file_updated']}`
Exact next action: `{manifest['next_action']}`
"""


def next_action_md(manifest: dict[str, Any]) -> str:
    return f"""# CCI Correction Final State Next Action

Exact next action: `{manifest['next_action']}`

Do not execute this action from this reconciliation packet.
"""


def consistency_check(manifest: dict[str, Any], output: Path) -> dict[str, Any]:
    required = {filename: (output / filename).exists() for filename in REQUIRED_FILES}
    required["public_source_cci_correction_final_state_reconciliation_consistency_check.json"] = True
    checks = {
        "reconciliation_only": manifest["public_source_cci_correction_final_state_reconciliation_only"] is True,
        "correct_source_family_lane": manifest["source_id"] == SOURCE_ID
        and manifest["family_id"] == FAMILY_ID
        and manifest["lane_id"] == LANE_ID,
        "evidence_chain_complete": manifest["intake_eligible"] is True
        and manifest["design_run_ready"] is True
        and manifest["bounded_run_completed"] is True
        and manifest["run_interpretable"] is True
        and manifest["run_usable_diagnostic_evidence"] is True
        and manifest["results_audit_mechanics_passed"] is True,
        "final_status_locked": manifest["final_status_locked"] is True
        and manifest["final_cci_correction_status"] == FINAL_STATUS,
        "control_weak_no_continuation": manifest["serious_interpretation_weakness"] is True
        and manifest["continuation_authorized"] is False
        and manifest["robustness_run_authorized"] is False
        and manifest["rerun_authorized"] is False,
        "not_actionable": manifest["not_promotable"] is True
        and manifest["not_candidate_exhaustive_ready"] is True
        and manifest["not_paper_demo_eligible"] is True
        and manifest["not_broker_live_eligible"] is True
        and manifest["not_real_money_relevant"] is True,
        "no_forbidden_actions": all(value is False for value in guardrails().values()),
        "next_action_valid": manifest["next_action"] == NEXT_ACTION,
        "required_files_present": all(required.values()),
    }
    return {**checks, "required_files": required, "consistency_passed": all(checks.values())}


def run(root: Path = ROOT) -> dict[str, Any]:
    output = root / OUTPUT_DIR
    output.mkdir(parents=True, exist_ok=True)
    manifest, context = build_manifest(root)
    write_json(output / "public_source_cci_correction_final_state_reconciliation_manifest.json", manifest)
    write_text(output / "public_source_cci_correction_final_state_reconciliation_summary.md", summary_md(manifest))
    write_text(output / "evidence_paths_inspected.md", evidence_paths_md(context["evidence_paths"]))
    write_csv(
        output / "evidence_chain_status.csv",
        context["chain"],
        ["stage", "status", "passed", "evidence_path", "notes"],
    )
    write_text(output / "evidence_chain_status.md", evidence_chain_md(context["chain"]))
    write_text(output / "cci_correction_current_status.md", current_status_md(manifest))
    write_text(output / "no_continuation_reasons.md", no_continuation_md(context["reasons"]))
    write_text(output / "queue_status_review.md", queue_status_md(manifest, context["status_matches"]))
    write_json(output / "guardrail_checklist.json", context["guardrails"])
    write_csv(
        output / "status_file_scan.csv",
        context["status_matches"],
        ["path", "matched_text", "action", "reason"],
    )
    write_text(output / "public_source_cci_correction_final_state_reconciliation_next_action.md", next_action_md(manifest))
    check = consistency_check(manifest, output)
    write_json(output / "public_source_cci_correction_final_state_reconciliation_consistency_check.json", check)
    return {**manifest, "output_dir": str(output.resolve()), "consistency_passed": check["consistency_passed"]}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
