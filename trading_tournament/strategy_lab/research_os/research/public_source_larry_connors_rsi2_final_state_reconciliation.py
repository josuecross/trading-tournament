from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.objective_reset.objective_reset_review import write_json, write_text
from strategy_lab.research_os.research.profit_oriented_research_batch_v1 import write_csv


SOURCE_ID = "larry_connors_rsi2_mean_reversion"
FAMILY_ID = "short_term_equity_mean_reversion"
LANE_ID = "public_source_larry_connors_rsi2_bounded_bt_lane_v1"

INTAKE_DIR = Path("evidence") / "research_recovery" / "public_source_intake_validation" / "latest"
BATCH_INTAKE_DIR = Path("evidence") / "research_recovery" / "public_source_batch_intake_validation" / "latest"
DESIGN_DIR = Path("evidence") / "research_recovery" / "public_source_larry_connors_rsi2_bounded_bt_design" / "latest"
RUN_DIR = Path("evidence") / "research_recovery" / "public_source_larry_connors_rsi2_bounded_bt_run" / "latest"
AUDIT_DIR = Path("evidence") / "research_recovery" / "public_source_larry_connors_rsi2_bounded_bt_results_audit" / "latest"
ROBUSTNESS_DIR = Path("evidence") / "research_recovery" / "public_source_larry_connors_rsi2_bounded_bt_robustness" / "latest"
SAMPLE_ADEQUACY_DIR = Path("evidence") / "research_recovery" / "backtest_sample_adequacy_report" / "latest"
OUTPUT_DIR = (
    Path("evidence")
    / "research_recovery"
    / "public_source_larry_connors_rsi2_final_state_reconciliation"
    / "latest"
)

INTAKE_MANIFEST = INTAKE_DIR / "public_source_intake_validation_manifest.json"
BATCH_INTAKE_DECISIONS = BATCH_INTAKE_DIR / "eligibility_decisions.csv"
DESIGN_MANIFEST = DESIGN_DIR / "public_source_larry_connors_rsi2_bounded_bt_design_manifest.json"
RUN_MANIFEST = RUN_DIR / "public_source_larry_connors_rsi2_bounded_bt_run_manifest.json"
RUN_ROWS = RUN_DIR / "row_level_results.csv"
AUDIT_MANIFEST = AUDIT_DIR / "public_source_larry_connors_rsi2_bounded_bt_results_audit_manifest.json"
ROBUSTNESS_MANIFEST = ROBUSTNESS_DIR / "public_source_larry_connors_rsi2_bounded_bt_robustness_manifest.json"
ROBUSTNESS_STRESS = ROBUSTNESS_DIR / "base_vs_cost_stress.csv"
SAMPLE_ADEQUACY_TABLE = SAMPLE_ADEQUACY_DIR / "sample_adequacy_table.csv"

FINAL_STATUS = "completed_diagnostic_context_only_cost_sensitive_rolling_weak_no_continuation_authorized"
NEXT_ACTION = "direction_owner_select_next_public_source_candidate"
STALE_NEXT_ACTION = "audit_public_source_larry_connors_rsi2_robustness_results"

STATUS_FILES_TO_SCAN = (
    Path("strategy_lab") / "RESEARCH_ROADMAP.md",
    Path("strategy_lab") / "strategy_registry.yaml",
    Path("strategy_lab") / "research_os" / "research" / "research_queue.yaml",
    Path("evidence") / "research_state" / "latest" / "research_state_manifest.json",
    Path("evidence") / "research_state" / "latest" / "current_research_state.md",
)

REQUIRED_FILES = (
    "larry_connors_rsi2_final_state_reconciliation_manifest.json",
    "larry_connors_rsi2_final_state_reconciliation_summary.md",
    "evidence_paths_inspected.md",
    "evidence_chain_status.csv",
    "evidence_chain_status.md",
    "larry_connors_rsi2_current_status.md",
    "queue_status_review.md",
    "guardrail_checklist.json",
    "status_file_scan.csv",
    "larry_connors_rsi2_final_state_reconciliation_next_action.md",
    "larry_connors_rsi2_final_state_reconciliation_consistency_check.json",
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
        "robustness_audit_run": False,
        "larry_connors_backtest_rerun": False,
        "larry_connors_robustness_rerun": False,
        "rsi_period_tuned": False,
        "rsi_threshold_tuned": False,
        "sma_periods_tuned": False,
        "timing_delay_optimized": False,
        "threshold_sweep_created": False,
        "new_variants_created": False,
        "new_exits_stops_filters_added": False,
        "new_indicators_added": False,
        "next_public_source_selected_by_codex": False,
        "public_source_scraped": False,
        "public_strategy_list_ingested": False,
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
        ("design_evidence", DESIGN_DIR),
        ("bounded_run_evidence", RUN_DIR),
        ("results_audit_evidence", AUDIT_DIR),
        ("robustness_evidence", ROBUSTNESS_DIR),
        ("sample_adequacy_evidence", SAMPLE_ADEQUACY_DIR),
        ("intake_manifest", INTAKE_MANIFEST),
        ("design_manifest", DESIGN_MANIFEST),
        ("run_manifest", RUN_MANIFEST),
        ("results_audit_manifest", AUDIT_MANIFEST),
        ("robustness_manifest", ROBUSTNESS_MANIFEST),
        ("robustness_stress_table", ROBUSTNESS_STRESS),
        ("sample_adequacy_table", SAMPLE_ADEQUACY_TABLE),
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
    return next((row for row in rows if row.get("variant_id") == "connors_rsi2_spy_bil_primary_v1"), {})


def primary_robustness_row(rows: list[dict[str, str]]) -> dict[str, str]:
    return next((row for row in rows if row.get("variant_id") == "connors_rsi2_spy_bil_primary_v1"), {})


def sample_adequacy_row(rows: list[dict[str, str]]) -> dict[str, str]:
    return next((row for row in rows if row.get("variant_id") == "connors_rsi2_spy_bil_primary_v1"), {})


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
    design_manifest: dict[str, Any],
    run_manifest: dict[str, Any],
    audit_manifest: dict[str, Any],
    robustness_manifest: dict[str, Any],
    sample_row: dict[str, str],
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
            "stage": "bounded_design",
            "status": design_manifest.get("run_readiness_decision", ""),
            "passed": design_manifest.get("run_readiness_decision")
            == "public_source_larry_connors_rsi2_bounded_bt_design_run_ready",
            "evidence_path": design_manifest.get("evidence_path", ""),
            "notes": "design run-ready with source-backed RSI/SMA parameters",
        },
        {
            "stage": "bounded_run",
            "status": "completed_primary_base_passed" if run_manifest.get("primary_row_numeric_criteria_pass") else "completed_primary_base_failed",
            "passed": run_manifest.get("public_source_larry_connors_rsi2_bounded_bt_lane_run") is True
            and run_manifest.get("variant_count_evaluated") == 5
            and run_manifest.get("primary_row_numeric_criteria_pass") is True,
            "evidence_path": run_manifest.get("evidence_path", ""),
            "notes": "bounded run completed exact five rows; diagnostic non-promotable",
        },
        {
            "stage": "results_audit",
            "status": audit_manifest.get("final_audit_decision", ""),
            "passed": audit_manifest.get("final_audit_decision") == "public_source_larry_connors_rsi2_results_audit_passed",
            "evidence_path": audit_manifest.get("evidence_path", ""),
            "notes": "RSI/SMA, no-lookahead, criteria, controls, and invariants verified",
        },
        {
            "stage": "sample_adequacy",
            "status": sample_row.get("sample_adequacy_classification", ""),
            "passed": sample_row.get("sample_adequacy_classification") == "adequate_diagnostic_sample",
            "evidence_path": str((ROOT / SAMPLE_ADEQUACY_DIR).resolve()),
            "notes": "adequate diagnostic sample only; not promotion evidence",
        },
        {
            "stage": "robustness",
            "status": "cost_sensitive_and_rolling_weak",
            "passed": robustness_manifest.get("robustness_evidence_usable") is True
            and robustness_manifest.get("primary_row_10bps_stress_pass") is False
            and robustness_manifest.get("primary_row_25bps_stress_pass") is False
            and robustness_manifest.get("primary_row_rolling_window_weakness") is True,
            "evidence_path": robustness_manifest.get("evidence_path", ""),
            "notes": "robustness usable but blocks continuation: cost-sensitive and rolling-window weak",
        },
    ]


def build_manifest(root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    intake_manifest = read_json(root / INTAKE_MANIFEST)
    batch_rows = read_csv_rows(root / BATCH_INTAKE_DECISIONS)
    design_manifest = read_json(root / DESIGN_MANIFEST)
    run_manifest = read_json(root / RUN_MANIFEST)
    run_rows = read_csv_rows(root / RUN_ROWS)
    audit_manifest = read_json(root / AUDIT_MANIFEST)
    robustness_manifest = read_json(root / ROBUSTNESS_MANIFEST)
    robustness_rows = read_csv_rows(root / ROBUSTNESS_STRESS)
    sample_rows = read_csv_rows(root / SAMPLE_ADEQUACY_TABLE)
    primary_run = primary_run_row(run_rows)
    primary_robust = primary_robustness_row(robustness_rows)
    primary_sample = sample_adequacy_row(sample_rows)
    chain = evidence_chain_rows(
        intake_manifest,
        batch_rows,
        design_manifest,
        run_manifest,
        audit_manifest,
        robustness_manifest,
        primary_sample,
    )
    status_matches = scan_status_files(root)
    queue_updated = False
    all_chain_passed = all(row["passed"] is True for row in chain)
    final_locked = (
        all_chain_passed
        and parse_bool(primary_robust.get("base_numeric_criteria_pass"))
        and not parse_bool(primary_robust.get("stress_10bps_numeric_criteria_pass"))
        and not parse_bool(primary_robust.get("stress_25bps_numeric_criteria_pass"))
        and primary_robust.get("robustness_label") == "connors_rsi2_robustness_cost_sensitive"
        and robustness_manifest.get("primary_row_rolling_window_weakness") is True
        and robustness_manifest.get("robustness_evidence_usable") is True
    )
    manifest = {
        "created_utc": now_utc(),
        "evidence_path": str((root / OUTPUT_DIR).resolve()),
        "larry_connors_rsi2_final_state_reconciliation_only": True,
        "source_id": SOURCE_ID,
        "family_id": FAMILY_ID,
        "lane_id": LANE_ID,
        "intake_eligible": intake_manifest.get("eligibility_decision") == "eligible_for_bounded_bt_design",
        "batch_intake_decision": batch_decision(batch_rows),
        "design_run_ready": design_manifest.get("run_readiness_decision")
        == "public_source_larry_connors_rsi2_bounded_bt_design_run_ready",
        "bounded_run_completed": run_manifest.get("public_source_larry_connors_rsi2_bounded_bt_lane_run") is True,
        "bounded_run_exact_5_rows": run_manifest.get("variant_count_evaluated") == 5,
        "run_primary_base_criteria_pass": run_manifest.get("primary_row_numeric_criteria_pass") is True,
        "results_audit_passed": audit_manifest.get("final_audit_decision")
        == "public_source_larry_connors_rsi2_results_audit_passed",
        "robustness_completed": robustness_manifest.get("public_source_larry_connors_rsi2_robustness_report") is True,
        "robustness_evidence_usable": robustness_manifest.get("robustness_evidence_usable") is True,
        "primary_robustness_label": primary_robust.get("robustness_label", ""),
        "primary_base_pass": parse_bool(primary_robust.get("base_numeric_criteria_pass")),
        "primary_10bps_stress_pass": parse_bool(primary_robust.get("stress_10bps_numeric_criteria_pass")),
        "primary_25bps_stress_pass": parse_bool(primary_robust.get("stress_25bps_numeric_criteria_pass")),
        "primary_subperiod_failure_count": robustness_manifest.get("primary_row_subperiod_failure_count"),
        "primary_rolling_window_weakness": robustness_manifest.get("primary_row_rolling_window_weakness"),
        "primary_event_trade_count": robustness_manifest.get("primary_event_trade_count"),
        "primary_average_holding_days": robustness_manifest.get("primary_average_holding_days"),
        "primary_median_holding_days": robustness_manifest.get("primary_median_holding_days"),
        "primary_worst_event_return": robustness_manifest.get("primary_worst_event_return"),
        "primary_event_unstable": robustness_manifest.get("primary_event_unstable"),
        "sample_adequacy_primary_classification": robustness_manifest.get("sample_adequacy_primary_classification"),
        "sample_adequacy_calendar_years": robustness_manifest.get("sample_adequacy_calendar_years"),
        "sample_adequacy_trading_days": robustness_manifest.get("sample_adequacy_trading_days"),
        "sample_adequacy_event_count": robustness_manifest.get("sample_adequacy_event_count"),
        "timing_sanity_context_only": robustness_manifest.get("timing_sanity_context_result") is True,
        "timing_delay_optimization_recommended": robustness_manifest.get("timing_delay_optimization_recommended") is True,
        "controls_control_only": robustness_manifest.get("control_rows_control_only") is True,
        "exposure_invariant_passed": run_manifest.get("exposure_invariant_passed") is True
        and robustness_manifest.get("invariant_failures") == 0,
        "max_daily_exposure": robustness_manifest.get("max_daily_exposure"),
        "max_daily_weight_sum": robustness_manifest.get("max_daily_weight_sum"),
        "final_status_locked": final_locked,
        "final_larry_connors_rsi2_status": FINAL_STATUS if final_locked else "final_state_reconciliation_incomplete",
        "not_promotable": True,
        "not_candidate_exhaustive_ready": True,
        "not_paper_demo_eligible": True,
        "not_broker_live_eligible": True,
        "not_real_money_relevant": True,
        "continuation_authorized": False,
        "robustness_audit_authorized": False,
        "parameter_tuning_authorized": False,
        "timing_delay_optimization_authorized": False,
        "threshold_sweeps_authorized": False,
        "new_variants_authorized": False,
        "new_exits_stops_filters_authorized": False,
        "rerun_authorized": False,
        "candidate_exhaustive_authorized": False,
        "promotion_authorized": False,
        "paper_demo_activation_authorized": False,
        "broker_live_action_authorized": False,
        "queue_status_file_updated": queue_updated,
        "queue_status_update_reason": "no_safe_automatic_queue_status_update_convention_used",
        "stale_status_pointer_count": len(status_matches),
        "stale_status_pointer_paths": [match["path"] for match in status_matches],
        "final_authorized_next_action": NEXT_ACTION,
        "next_action": NEXT_ACTION,
        **guardrails(),
    }
    support = {
        "intake_manifest": intake_manifest,
        "design_manifest": design_manifest,
        "run_manifest": run_manifest,
        "audit_manifest": audit_manifest,
        "robustness_manifest": robustness_manifest,
        "primary_run": primary_run,
        "primary_robustness": primary_robust,
        "primary_sample": primary_sample,
        "chain_rows": chain,
        "status_matches": status_matches,
        "evidence_paths": evidence_paths(root),
    }
    return manifest, support


def evidence_paths_md(paths: list[dict[str, Any]]) -> str:
    lines = ["# Evidence Paths Inspected", ""]
    for row in paths:
        lines.append(f"- `{row['name']}`: `{row['path']}` (exists: `{row['exists']}`)")
    return "\n".join(lines) + "\n"


def chain_status_md(rows: list[dict[str, Any]]) -> str:
    lines = ["# Evidence-Chain Status", ""]
    for row in rows:
        lines.append(f"- `{row['stage']}`: `{row['status']}` (passed: `{row['passed']}`)")
        lines.append(f"  Evidence: `{row['evidence_path']}`")
        lines.append(f"  Notes: {row['notes']}")
    return "\n".join(lines) + "\n"


def current_status_md(manifest: dict[str, Any]) -> str:
    return f"""# Larry Connors RSI(2) Current Status

Final status: `{manifest['final_larry_connors_rsi2_status']}`

Final status locked: `{manifest['final_status_locked']}`

Rows evaluated in run/robustness: `5 / 5`

Primary base pass: `{manifest['primary_base_pass']}`

Primary 10 bps stress pass: `{manifest['primary_10bps_stress_pass']}`

Primary 25 bps stress pass: `{manifest['primary_25bps_stress_pass']}`

Primary robustness label: `{manifest['primary_robustness_label']}`

Primary subperiod failures: `{manifest['primary_subperiod_failure_count']}`

Primary rolling-window weakness: `{manifest['primary_rolling_window_weakness']}`

Primary reconstructed events: `{manifest['primary_event_trade_count']}`

Average / median holding days: `{manifest['primary_average_holding_days']}` / `{manifest['primary_median_holding_days']}`

Worst event return: `{manifest['primary_worst_event_return']}`

Event unstable: `{manifest['primary_event_unstable']}`

Sample adequacy: `{manifest['sample_adequacy_primary_classification']}` over `{manifest['sample_adequacy_calendar_years']}` calendar years and `{manifest['sample_adequacy_trading_days']}` trading days.

This is completed diagnostic/context-only evidence. It is not promotable, not candidate_exhaustive-ready, not paper/demo eligible, not broker/live eligible, and not real-money relevant.
"""


def queue_review_md(manifest: dict[str, Any], matches: list[dict[str, str]]) -> str:
    lines = [
        "# Queue / Status Review",
        "",
        f"Queue/status file updated: `{manifest['queue_status_file_updated']}`",
        "",
        f"Reason: `{manifest['queue_status_update_reason']}`",
        "",
        f"Stale robustness-audit pointer count: `{manifest['stale_status_pointer_count']}`",
        "",
    ]
    if matches:
        lines.append("Stale pointers found:")
        for match in matches:
            lines.append(f"- `{match['path']}`: `{match['matched_text']}`")
        lines.append("")
        lines.append("No file was auto-edited because this reconciliation runner does not have a safe queue/status mutation convention.")
    else:
        lines.append("No stale Larry Connors robustness-audit next-action pointer was found in roadmap, registry, research queue, or latest research-state files.")
    lines.append("")
    lines.append(f"Final authorized next action recorded by reconciliation: `{manifest['final_authorized_next_action']}`")
    return "\n".join(lines) + "\n"


def summary_md(manifest: dict[str, Any]) -> str:
    return f"""# Larry Connors RSI(2) Final State Reconciliation

Source ID: `{manifest['source_id']}`

Lane ID: `{manifest['lane_id']}`

Final status: `{manifest['final_larry_connors_rsi2_status']}`

Final status locked: `{manifest['final_status_locked']}`

Evidence chain: intake eligible `{manifest['intake_eligible']}`, design run-ready `{manifest['design_run_ready']}`, bounded run completed `{manifest['bounded_run_completed']}`, results audit passed `{manifest['results_audit_passed']}`, robustness usable `{manifest['robustness_evidence_usable']}`.

Robustness limitation: primary row is `{manifest['primary_robustness_label']}`, 10 bps stress pass `{manifest['primary_10bps_stress_pass']}`, 25 bps stress pass `{manifest['primary_25bps_stress_pass']}`, rolling-window weakness `{manifest['primary_rolling_window_weakness']}`.

No continuation is authorized for Larry Connors RSI(2). No robustness audit, parameter tuning, timing-delay optimization, threshold sweep, rerun, candidate_exhaustive, promotion, paper/demo activation, broker/live action, or real-money recommendation occurred.

Exact next action:

`{manifest['next_action']}`

Do not execute the next action in this task.
"""


def next_action_md(next_action: str) -> str:
    return f"""# Larry Connors RSI(2) Final State Next Action

Exact next action:

`{next_action}`

Do not execute the next action in this task.
"""


def consistency_check(manifest: dict[str, Any], output: Path) -> dict[str, Any]:
    required = {name: (output / name).exists() for name in REQUIRED_FILES}
    required["larry_connors_rsi2_final_state_reconciliation_consistency_check.json"] = True
    checks: dict[str, Any] = {
        "reconciliation_only": manifest["larry_connors_rsi2_final_state_reconciliation_only"] is True,
        "correct_source_lane_family": manifest["source_id"] == SOURCE_ID
        and manifest["lane_id"] == LANE_ID
        and manifest["family_id"] == FAMILY_ID,
        "evidence_chain_complete": manifest["intake_eligible"] is True
        and manifest["design_run_ready"] is True
        and manifest["bounded_run_completed"] is True
        and manifest["bounded_run_exact_5_rows"] is True
        and manifest["run_primary_base_criteria_pass"] is True
        and manifest["results_audit_passed"] is True
        and manifest["robustness_completed"] is True
        and manifest["robustness_evidence_usable"] is True,
        "robustness_limitation_recorded": manifest["primary_robustness_label"]
        == "connors_rsi2_robustness_cost_sensitive"
        and manifest["primary_base_pass"] is True
        and manifest["primary_10bps_stress_pass"] is False
        and manifest["primary_25bps_stress_pass"] is False
        and manifest["primary_rolling_window_weakness"] is True,
        "timing_and_controls_locked": manifest["timing_sanity_context_only"] is True
        and manifest["timing_delay_optimization_recommended"] is False
        and manifest["controls_control_only"] is True,
        "invariants_clean": manifest["exposure_invariant_passed"] is True
        and manifest["max_daily_exposure"] <= 1.000001
        and manifest["max_daily_weight_sum"] <= 1.000001,
        "final_status_locked": manifest["final_status_locked"] is True
        and manifest["final_larry_connors_rsi2_status"] == FINAL_STATUS
        and manifest["continuation_authorized"] is False,
        "not_actionable": manifest["not_promotable"] is True
        and manifest["not_candidate_exhaustive_ready"] is True
        and manifest["not_paper_demo_eligible"] is True
        and manifest["not_broker_live_eligible"] is True
        and manifest["not_real_money_relevant"] is True,
        "no_unauthorized_next_steps": manifest["robustness_audit_authorized"] is False
        and manifest["parameter_tuning_authorized"] is False
        and manifest["timing_delay_optimization_authorized"] is False
        and manifest["threshold_sweeps_authorized"] is False
        and manifest["new_variants_authorized"] is False
        and manifest["rerun_authorized"] is False
        and manifest["candidate_exhaustive_authorized"] is False
        and manifest["promotion_authorized"] is False
        and manifest["paper_demo_activation_authorized"] is False
        and manifest["broker_live_action_authorized"] is False,
        "queue_not_mutated": manifest["queue_status_file_updated"] is False,
        "guardrails_clean": all(manifest[key] is False for key in guardrails()),
        "next_action_valid": manifest["next_action"] == NEXT_ACTION,
        "required_files_present": all(required.values()),
        "required_files": required,
    }
    checks["consistency_passed"] = all(value is True for key, value in checks.items() if key != "required_files")
    return checks


def run(root: Path = ROOT) -> dict[str, Any]:
    output = root / OUTPUT_DIR
    output.mkdir(parents=True, exist_ok=True)
    manifest, support = build_manifest(root)

    write_json(output / "larry_connors_rsi2_final_state_reconciliation_manifest.json", manifest)
    write_text(output / "larry_connors_rsi2_final_state_reconciliation_summary.md", summary_md(manifest))
    write_text(output / "evidence_paths_inspected.md", evidence_paths_md(support["evidence_paths"]))
    write_csv(
        output / "evidence_chain_status.csv",
        support["chain_rows"],
        ["stage", "status", "passed", "evidence_path", "notes"],
    )
    write_text(output / "evidence_chain_status.md", chain_status_md(support["chain_rows"]))
    write_text(output / "larry_connors_rsi2_current_status.md", current_status_md(manifest))
    write_text(output / "queue_status_review.md", queue_review_md(manifest, support["status_matches"]))
    write_json(output / "guardrail_checklist.json", guardrails())
    write_csv(
        output / "status_file_scan.csv",
        support["status_matches"],
        ["path", "matched_text", "action", "reason"],
    )
    write_text(output / "larry_connors_rsi2_final_state_reconciliation_next_action.md", next_action_md(manifest["next_action"]))
    check = consistency_check(manifest, output)
    write_json(output / "larry_connors_rsi2_final_state_reconciliation_consistency_check.json", check)
    return {**manifest, "output_dir": str(output.resolve()), "consistency_passed": check["consistency_passed"]}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
