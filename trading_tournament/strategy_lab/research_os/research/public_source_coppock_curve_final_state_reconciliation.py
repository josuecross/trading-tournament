from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.objective_reset.objective_reset_review import write_json, write_text
from strategy_lab.research_os.research.profit_oriented_research_batch_v1 import write_csv


SOURCE_ID = "coppock_curve_monthly_equity_signal"
FAMILY_ID = "long_term_equity_index_momentum_zero_cross"
LANE_ID = "public_source_coppock_curve_bounded_bt_lane_v1"

INTAKE_DIR = Path("evidence") / "research_recovery" / "public_source_intake_validation" / "latest"
BATCH_INTAKE_DIR = Path("evidence") / "research_recovery" / "public_source_batch_intake_validation" / "latest"
INTAKE_CONSISTENCY_DIR = (
    Path("evidence") / "research_recovery" / "public_source_coppock_intake_evidence_consistency" / "latest"
)
DESIGN_DIR = Path("evidence") / "research_recovery" / "public_source_coppock_curve_bounded_bt_design" / "latest"
RUN_DIR = Path("evidence") / "research_recovery" / "public_source_coppock_curve_bounded_bt_run" / "latest"
OUTPUT_DIR = (
    Path("evidence")
    / "research_recovery"
    / "public_source_coppock_curve_final_state_reconciliation"
    / "latest"
)

INTAKE_MANIFEST = INTAKE_DIR / "public_source_intake_validation_manifest.json"
BATCH_INTAKE_DECISIONS = BATCH_INTAKE_DIR / "eligibility_decisions.csv"
INTAKE_CONSISTENCY_MANIFEST = INTAKE_CONSISTENCY_DIR / "coppock_intake_evidence_consistency_manifest.json"
DESIGN_MANIFEST = DESIGN_DIR / "public_source_coppock_curve_bounded_bt_design_manifest.json"
RUN_MANIFEST = RUN_DIR / "public_source_coppock_curve_bounded_bt_run_manifest.json"
RUN_ROWS = RUN_DIR / "row_level_results.csv"
RUN_CRITERIA = RUN_DIR / "numeric_criteria_results.csv"

FINAL_STATUS = "completed_diagnostic_sparse_context_only_failed_criteria_no_continuation_authorized"
NEXT_ACTION = "direction_owner_select_next_public_source_candidate"
STALE_NEXT_ACTION = "audit_public_source_coppock_curve_bounded_bt_results"

STATUS_FILES_TO_SCAN = (
    Path("strategy_lab") / "RESEARCH_ROADMAP.md",
    Path("strategy_lab") / "strategy_registry.yaml",
    Path("strategy_lab") / "research_os" / "research" / "research_queue.yaml",
    Path("evidence") / "research_state" / "latest" / "research_state_manifest.json",
    Path("evidence") / "research_state" / "latest" / "current_research_state.md",
)

REQUIRED_FILES = (
    "public_source_coppock_curve_final_state_reconciliation_manifest.json",
    "public_source_coppock_curve_final_state_reconciliation_summary.md",
    "evidence_paths_inspected.md",
    "evidence_chain_status.csv",
    "evidence_chain_status.md",
    "coppock_curve_current_status.md",
    "no_continuation_reasons.md",
    "queue_status_review.md",
    "guardrail_checklist.json",
    "status_file_scan.csv",
    "public_source_coppock_curve_final_state_reconciliation_next_action.md",
    "public_source_coppock_curve_final_state_reconciliation_consistency_check.json",
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


def guardrails() -> dict[str, bool]:
    return {
        "results_audit_run": False,
        "coppock_backtest_rerun": False,
        "coppock_robustness_run": False,
        "roc_periods_tuned": False,
        "wma_period_tuned": False,
        "threshold_tuned": False,
        "signal_timing_tuned": False,
        "exit_rule_tuned": False,
        "daily_coppock_variants_added": False,
        "weekly_coppock_variants_added": False,
        "alternate_roc_periods_added": False,
        "alternate_wma_periods_added": False,
        "signal_lines_added": False,
        "filters_added": False,
        "divergence_rules_added": False,
        "stop_losses_added": False,
        "profit_targets_added": False,
        "alternate_exits_added": False,
        "new_variants_created": False,
        "next_public_source_selected_by_codex": False,
        "public_source_scraped": False,
        "public_strategy_list_ingested": False,
        "larry_connors_continued": False,
        "percent_b_continued": False,
        "turn_of_month_continued": False,
        "faber_taa_designed_or_retested": False,
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
        ("intake_consistency_evidence", INTAKE_CONSISTENCY_DIR),
        ("design_evidence", DESIGN_DIR),
        ("bounded_run_evidence", RUN_DIR),
        ("intake_manifest", INTAKE_MANIFEST),
        ("batch_intake_decisions", BATCH_INTAKE_DECISIONS),
        ("intake_consistency_manifest", INTAKE_CONSISTENCY_MANIFEST),
        ("design_manifest", DESIGN_MANIFEST),
        ("run_manifest", RUN_MANIFEST),
        ("run_rows", RUN_ROWS),
        ("run_criteria", RUN_CRITERIA),
    ]
    return [
        {
            "name": name,
            "path": str((root / relative).resolve()),
            "exists": (root / relative).exists(),
        }
        for name, relative in paths
    ]


def batch_decision(rows: list[dict[str, str]]) -> str:
    for row in rows:
        if row.get("source_id") == SOURCE_ID or row.get("candidate_id") == SOURCE_ID:
            return row.get("eligibility_decision") or row.get("decision") or ""
    return "not_found_in_batch_decisions"


def primary_run_row(rows: list[dict[str, str]]) -> dict[str, str]:
    return next((row for row in rows if row.get("variant_id") == "coppock_spy_bil_monthly_zero_cross_primary_v1"), {})


def spy_control_row(rows: list[dict[str, str]]) -> dict[str, str]:
    return next((row for row in rows if row.get("variant_id") == "coppock_spy_buy_hold_control_v1"), {})


def scan_status_files(root: Path) -> list[dict[str, str]]:
    matches: list[dict[str, str]] = []
    for relative_path in STATUS_FILES_TO_SCAN:
        path = root / relative_path
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if STALE_NEXT_ACTION in text:
            matches.append(
                {
                    "path": str(relative_path),
                    "matched_text": STALE_NEXT_ACTION,
                    "action": "not_updated_by_reconciliation_runner",
                    "reason": "no_safe_automatic_queue_status_update_convention_used",
                }
            )
    return matches


def evidence_chain_rows(
    intake_manifest: dict[str, Any],
    batch_rows: list[dict[str, str]],
    consistency_manifest: dict[str, Any],
    design_manifest: dict[str, Any],
    run_manifest: dict[str, Any],
) -> list[dict[str, Any]]:
    return [
        {
            "stage": "intake",
            "status": intake_manifest.get("eligibility_decision", ""),
            "passed": intake_manifest.get("eligibility_decision") == "eligible_for_bounded_bt_design",
            "evidence_path": intake_manifest.get("evidence_path", ""),
            "notes": "single-source intake eligible; public source presence is not profitability proof",
        },
        {
            "stage": "batch_intake",
            "status": batch_decision(batch_rows),
            "passed": batch_decision(batch_rows) in {"eligible_for_bounded_bt_design", "not_found_in_batch_decisions"},
            "evidence_path": str((ROOT / BATCH_INTAKE_DIR).resolve()),
            "notes": "batch intake context inspected; no design or backtest performed here",
        },
        {
            "stage": "intake_consistency",
            "status": consistency_manifest.get("verification_decision", ""),
            "passed": consistency_manifest.get("verification_decision")
            == "coppock_intake_evidence_consistent_ready_for_design"
            and consistency_manifest.get("candidate_specific_evidence_valid") is True,
            "evidence_path": consistency_manifest.get("evidence_path", ""),
            "notes": "Coppock-specific intake consistency verified before design",
        },
        {
            "stage": "bounded_design",
            "status": design_manifest.get("run_readiness_decision", ""),
            "passed": design_manifest.get("run_readiness_decision")
            == "public_source_coppock_curve_bounded_bt_design_run_ready",
            "evidence_path": design_manifest.get("evidence_path", ""),
            "notes": "design run-ready with source-backed monthly Coppock parameters",
        },
        {
            "stage": "bounded_run",
            "status": "completed_sparse_context_only_primary_failed"
            if run_manifest.get("public_source_coppock_curve_bounded_bt_lane_run")
            else "missing_or_not_run",
            "passed": run_manifest.get("public_source_coppock_curve_bounded_bt_lane_run") is True
            and run_manifest.get("variant_count_evaluated") == 5
            and run_manifest.get("results_interpretable") is True
            and run_manifest.get("usable_diagnostic_evidence") is True,
            "evidence_path": run_manifest.get("evidence_path", ""),
            "notes": "bounded run completed exact five rows; primary criteria failed and sparse/context-only label applied",
        },
        {
            "stage": "final_closeout",
            "status": FINAL_STATUS,
            "passed": True,
            "evidence_path": "",
            "notes": "direction-owner decision closes Coppock without audit, robustness, rerun, tuning, or continuation",
        },
    ]


def no_continuation_reasons(run_manifest: dict[str, Any], primary: dict[str, str], spy_control: dict[str, str]) -> dict[str, Any]:
    primary_total = parse_float(primary.get("total_return"))
    spy_total = parse_float(spy_control.get("total_return"))
    drawdown_reduction = parse_float(primary.get("drawdown_reduction_versus_spy_buy_hold"))
    proxy_pass = parse_bool(primary.get("primary_return_drawdown_proxy_pass"))
    return {
        "only_one_completed_round_trip": int(run_manifest.get("completed_round_trip_event_count", 0)) == 1,
        "primary_numeric_criteria_failed": run_manifest.get("primary_row_numeric_criteria_pass") is False,
        "primary_label_sparse_context_only": primary.get("research_label")
        == "public_source_coppock_curve_sparse_context_only",
        "drawdown_reduction_effectively_zero": abs(drawdown_reduction) <= 1e-6,
        "return_drawdown_proxy_did_not_beat_spy": not proxy_pass,
        "spy_buy_hold_control_outperformed_primary": spy_total > primary_total,
        "average_spy_exposure_very_high": parse_float(primary.get("average_spy_exposure_share")) >= 0.90,
        "duplicate_reference_correlation_high": parse_float(primary.get("duplicate_reference_correlation")) >= 0.90,
    }


def build_manifest(root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    intake_manifest = read_json(root / INTAKE_MANIFEST)
    batch_rows = read_csv_rows(root / BATCH_INTAKE_DECISIONS)
    consistency_manifest = read_json(root / INTAKE_CONSISTENCY_MANIFEST)
    design_manifest = read_json(root / DESIGN_MANIFEST)
    run_manifest = read_json(root / RUN_MANIFEST)
    run_rows = read_csv_rows(root / RUN_ROWS)
    primary = primary_run_row(run_rows)
    spy_control = spy_control_row(run_rows)
    status_matches = scan_status_files(root)
    reasons = no_continuation_reasons(run_manifest, primary, spy_control)
    evidence_chain = evidence_chain_rows(intake_manifest, batch_rows, consistency_manifest, design_manifest, run_manifest)

    manifest = {
        "created_utc": now_utc(),
        "evidence_path": str((root / OUTPUT_DIR).resolve()),
        "public_source_coppock_curve_final_state_reconciliation_only": True,
        "source_id": SOURCE_ID,
        "family_id": FAMILY_ID,
        "lane_id": LANE_ID,
        "intake_eligible": intake_manifest.get("eligibility_decision") == "eligible_for_bounded_bt_design",
        "batch_intake_decision": batch_decision(batch_rows),
        "intake_consistency_verified": consistency_manifest.get("verification_decision")
        == "coppock_intake_evidence_consistent_ready_for_design",
        "candidate_specific_evidence_valid": consistency_manifest.get("candidate_specific_evidence_valid") is True,
        "design_run_ready": design_manifest.get("run_readiness_decision")
        == "public_source_coppock_curve_bounded_bt_design_run_ready",
        "bounded_run_completed": run_manifest.get("public_source_coppock_curve_bounded_bt_lane_run") is True,
        "bounded_run_exact_5_rows": run_manifest.get("variant_count_evaluated") == 5,
        "run_results_interpretable": run_manifest.get("results_interpretable") is True,
        "run_usable_diagnostic_evidence": run_manifest.get("usable_diagnostic_evidence") is True,
        "exposure_invariant_passed": run_manifest.get("exposure_invariant_passed") is True,
        "max_daily_exposure": run_manifest.get("max_daily_exposure"),
        "max_daily_weight_sum": run_manifest.get("max_daily_weight_sum"),
        "primary_numeric_criteria_pass": run_manifest.get("primary_row_numeric_criteria_pass") is True,
        "primary_label": primary.get("research_label", ""),
        "primary_total_return": parse_float(primary.get("total_return")),
        "spy_buy_hold_total_return": parse_float(spy_control.get("total_return")),
        "primary_cagr": parse_float(primary.get("cagr")),
        "primary_max_drawdown": parse_float(primary.get("max_drawdown")),
        "primary_drawdown_reduction_versus_spy": parse_float(primary.get("drawdown_reduction_versus_spy_buy_hold")),
        "primary_average_spy_exposure": parse_float(primary.get("average_spy_exposure_share")),
        "primary_duplicate_reference_correlation": parse_float(primary.get("duplicate_reference_correlation")),
        "positive_zero_cross_entry_count": run_manifest.get("positive_zero_cross_entry_count"),
        "negative_zero_cross_exit_count": run_manifest.get("negative_zero_cross_exit_count"),
        "completed_round_trip_event_count": run_manifest.get("completed_round_trip_event_count"),
        "monthly_observation_count": run_manifest.get("monthly_observation_count"),
        "effective_start_date": run_manifest.get("effective_start_date"),
        "effective_end_date": run_manifest.get("effective_end_date"),
        "final_status_locked": True,
        "final_coppock_curve_status": FINAL_STATUS,
        "final_authorized_next_action": NEXT_ACTION,
        "not_promotable": True,
        "not_candidate_exhaustive_ready": True,
        "not_paper_demo_eligible": True,
        "not_broker_live_eligible": True,
        "not_real_money_relevant": True,
        "continuation_authorized": False,
        "results_audit_authorized": False,
        "robustness_run_authorized": False,
        "rerun_authorized": False,
        "parameter_tuning_authorized": False,
        "daily_weekly_variant_authorized": False,
        "alternate_roc_wma_authorized": False,
        "signal_line_filter_divergence_stop_profit_target_authorized": False,
        "candidate_exhaustive_authorized": False,
        "promotion_authorized": False,
        "paper_demo_activation_authorized": False,
        "broker_live_action_authorized": False,
        "queue_status_file_updated": False,
        "queue_status_update_reason": "no_safe_automatic_queue_status_update_convention_used",
        "stale_status_pointer_count": len(status_matches),
        "next_action": NEXT_ACTION,
        **guardrails(),
        **reasons,
    }
    context = {
        "evidence_paths": evidence_paths(root),
        "evidence_chain": evidence_chain,
        "status_matches": status_matches,
        "no_continuation_reasons": reasons,
    }
    return manifest, context


def evidence_paths_md(paths: list[dict[str, Any]]) -> str:
    lines = ["# Evidence Paths Inspected", ""]
    for row in paths:
        lines.append(f"- `{row['name']}`: exists `{row['exists']}`, path `{row['path']}`")
    return "\n".join(lines) + "\n"


def evidence_chain_md(rows: list[dict[str, Any]]) -> str:
    lines = ["# Evidence Chain Status", ""]
    for row in rows:
        lines.append(f"- `{row['stage']}`: status `{row['status']}`, passed `{row['passed']}`")
        lines.append(f"  Evidence: `{row['evidence_path'] or 'this closeout packet'}`")
        lines.append(f"  Notes: {row['notes']}")
    return "\n".join(lines) + "\n"


def current_status_md(manifest: dict[str, Any]) -> str:
    return f"""# Coppock Curve Current Status

Final status:

`{manifest['final_coppock_curve_status']}`

This status is locked by direction-owner decision after the bounded run produced interpretable but failed diagnostic evidence.

Primary label: `{manifest['primary_label']}`

Primary numeric criteria pass: `{manifest['primary_numeric_criteria_pass']}`

Completed round trips: `{manifest['completed_round_trip_event_count']}`

Drawdown reduction versus SPY buy-hold: `{manifest['primary_drawdown_reduction_versus_spy']}`

SPY buy-hold total return: `{manifest['spy_buy_hold_total_return']}`

Primary total return: `{manifest['primary_total_return']}`

Average SPY exposure: `{manifest['primary_average_spy_exposure']}`

Duplicate/reference correlation: `{manifest['primary_duplicate_reference_correlation']}`

Coppock Curve is not promotable, not candidate_exhaustive-ready, not paper/demo eligible, not broker/live eligible, and not real-money relevant.
"""


def no_continuation_md(reasons: dict[str, Any]) -> str:
    lines = ["# No-Continuation Reasons", ""]
    for key, value in reasons.items():
        lines.append(f"- `{key}`: `{value}`")
    lines.append("")
    lines.append("No results audit, robustness run, rerun, parameter tuning, daily/weekly Coppock variant, alternate ROC/WMA setting, signal line, alternate exit, filter, stop-loss, profit target, candidate_exhaustive, promotion, paper/demo activation, broker/live action, or real-money path is authorized.")
    return "\n".join(lines) + "\n"


def queue_status_review_md(manifest: dict[str, Any], status_matches: list[dict[str, str]]) -> str:
    lines = ["# Queue / Status Review", ""]
    lines.append(f"Queue/status file updated: `{manifest['queue_status_file_updated']}`")
    lines.append("")
    lines.append(f"Update reason: `{manifest['queue_status_update_reason']}`")
    lines.append("")
    lines.append(f"Stale `{STALE_NEXT_ACTION}` pointer count: `{len(status_matches)}`")
    lines.append("")
    if status_matches:
        for row in status_matches:
            lines.append(f"- `{row['path']}`: `{row['matched_text']}`, action `{row['action']}`")
    else:
        lines.append("- no stale status pointer found in scanned files")
    lines.append("")
    lines.append("Final authorized next action:")
    lines.append("")
    lines.append(f"`{manifest['final_authorized_next_action']}`")
    return "\n".join(lines) + "\n"


def summary_md(manifest: dict[str, Any]) -> str:
    return f"""# Public Source Coppock Curve Final State Reconciliation

Source ID: `{manifest['source_id']}`

Lane ID: `{manifest['lane_id']}`

Final status: `{manifest['final_coppock_curve_status']}`

Evidence chain:

- Intake eligible: `{manifest['intake_eligible']}`
- Intake consistency verified: `{manifest['intake_consistency_verified']}`
- Design run-ready: `{manifest['design_run_ready']}`
- Bounded run completed: `{manifest['bounded_run_completed']}`
- Run interpretable: `{manifest['run_results_interpretable']}`
- Usable diagnostic evidence: `{manifest['run_usable_diagnostic_evidence']}`

No-continuation summary:

- Completed round trips: `{manifest['completed_round_trip_event_count']}`
- Primary numeric criteria pass: `{manifest['primary_numeric_criteria_pass']}`
- Primary label: `{manifest['primary_label']}`
- Drawdown reduction versus SPY: `{manifest['primary_drawdown_reduction_versus_spy']}`
- SPY buy-hold outperformed primary: `{manifest['spy_buy_hold_control_outperformed_primary']}`
- Average SPY exposure very high: `{manifest['average_spy_exposure_very_high']}`

Queue/status file updated: `{manifest['queue_status_file_updated']}`

No audit loop, rerun, robustness, tuning, promotion, candidate_exhaustive, paper/demo, broker/live action, or real-money recommendation occurred.

Exact next action: `{manifest['next_action']}`
"""


def next_action_md(next_action: str) -> str:
    return f"""# Public Source Coppock Curve Final State Reconciliation Next Action

Exact next action:

`{next_action}`

Do not execute the next action in this task.
"""


def consistency_check(manifest: dict[str, Any], context: dict[str, Any], output: Path) -> dict[str, Any]:
    required = {name: (output / name).exists() for name in REQUIRED_FILES}
    required["public_source_coppock_curve_final_state_reconciliation_consistency_check.json"] = True
    chain = context["evidence_chain"]
    checks = {
        "closeout_only": manifest["public_source_coppock_curve_final_state_reconciliation_only"] is True,
        "correct_source_family_lane": manifest["source_id"] == SOURCE_ID
        and manifest["family_id"] == FAMILY_ID
        and manifest["lane_id"] == LANE_ID,
        "evidence_chain_verified": manifest["intake_eligible"] is True
        and manifest["intake_consistency_verified"] is True
        and manifest["design_run_ready"] is True
        and manifest["bounded_run_completed"] is True
        and manifest["bounded_run_exact_5_rows"] is True
        and manifest["run_results_interpretable"] is True
        and manifest["run_usable_diagnostic_evidence"] is True
        and all(row["passed"] is True for row in chain),
        "final_status_locked": manifest["final_status_locked"] is True
        and manifest["final_coppock_curve_status"] == FINAL_STATUS,
        "failed_sparse_reasons_recorded": manifest["only_one_completed_round_trip"] is True
        and manifest["primary_numeric_criteria_failed"] is True
        and manifest["primary_label_sparse_context_only"] is True
        and manifest["drawdown_reduction_effectively_zero"] is True
        and manifest["return_drawdown_proxy_did_not_beat_spy"] is True
        and manifest["spy_buy_hold_control_outperformed_primary"] is True
        and manifest["average_spy_exposure_very_high"] is True,
        "outputs_not_actionable": manifest["not_promotable"] is True
        and manifest["not_candidate_exhaustive_ready"] is True
        and manifest["not_paper_demo_eligible"] is True
        and manifest["not_broker_live_eligible"] is True
        and manifest["not_real_money_relevant"] is True,
        "no_continuation_authorized": manifest["continuation_authorized"] is False
        and manifest["results_audit_authorized"] is False
        and manifest["robustness_run_authorized"] is False
        and manifest["rerun_authorized"] is False
        and manifest["parameter_tuning_authorized"] is False
        and manifest["candidate_exhaustive_authorized"] is False
        and manifest["promotion_authorized"] is False
        and manifest["paper_demo_activation_authorized"] is False
        and manifest["broker_live_action_authorized"] is False,
        "queue_status_review_recorded": manifest["queue_status_file_updated"] is False
        and manifest["queue_status_update_reason"] == "no_safe_automatic_queue_status_update_convention_used",
        "guardrails_clean": all(value is False for key, value in guardrails().items()),
        "next_action_valid": manifest["next_action"] == NEXT_ACTION,
        "required_files_present": all(required.values()),
        "required_files": required,
    }
    checks["consistency_passed"] = all(value is True for key, value in checks.items() if key != "required_files")
    return checks


def run(root: Path = ROOT) -> dict[str, Any]:
    output = root / OUTPUT_DIR
    output.mkdir(parents=True, exist_ok=True)
    manifest, context = build_manifest(root)

    write_json(output / "public_source_coppock_curve_final_state_reconciliation_manifest.json", manifest)
    write_text(output / "public_source_coppock_curve_final_state_reconciliation_summary.md", summary_md(manifest))
    write_text(output / "evidence_paths_inspected.md", evidence_paths_md(context["evidence_paths"]))
    write_csv(output / "evidence_chain_status.csv", context["evidence_chain"], ["stage", "status", "passed", "evidence_path", "notes"])
    write_text(output / "evidence_chain_status.md", evidence_chain_md(context["evidence_chain"]))
    write_text(output / "coppock_curve_current_status.md", current_status_md(manifest))
    write_text(output / "no_continuation_reasons.md", no_continuation_md(context["no_continuation_reasons"]))
    write_text(output / "queue_status_review.md", queue_status_review_md(manifest, context["status_matches"]))
    write_json(output / "guardrail_checklist.json", guardrails())
    write_csv(output / "status_file_scan.csv", context["status_matches"], ["path", "matched_text", "action", "reason"])
    write_text(output / "public_source_coppock_curve_final_state_reconciliation_next_action.md", next_action_md(manifest["next_action"]))
    check = consistency_check(manifest, context, output)
    write_json(output / "public_source_coppock_curve_final_state_reconciliation_consistency_check.json", check)
    return {**manifest, "output_dir": str(output.resolve()), "consistency_passed": check["consistency_passed"]}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
