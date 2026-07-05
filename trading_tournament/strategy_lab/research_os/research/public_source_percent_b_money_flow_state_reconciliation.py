from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.objective_reset.objective_reset_review import write_json, write_text
from strategy_lab.research_os.research.profit_oriented_research_batch_v1 import write_csv


SOURCE_ID = "percent_b_money_flow"
LANE_ID = "public_source_percent_b_money_flow_bounded_bt_lane_v1"
FAMILY_ID = "price_band_money_flow_confirmation"

DESIGN_DIR = (
    Path("evidence")
    / "research_recovery"
    / "public_source_percent_b_money_flow_bounded_bt_design"
    / "latest"
)
RUN_DIR = (
    Path("evidence")
    / "research_recovery"
    / "public_source_percent_b_money_flow_bounded_bt_run"
    / "latest"
)
BATCH_INTAKE_DIR = (
    Path("evidence") / "research_recovery" / "public_source_batch_intake_validation" / "latest"
)
INTAKE_DIR = Path("evidence") / "research_recovery" / "public_source_intake_validation" / "latest"
SOURCE_INTAKE_PATH = (
    Path("strategy_lab")
    / "research_os"
    / "public_strategy_sources"
    / "intake_candidates"
    / "percent_b_money_flow.yaml"
)
OUTPUT_DIR = (
    Path("evidence")
    / "research_recovery"
    / "public_source_percent_b_money_flow_state_reconciliation"
    / "latest"
)

DESIGN_MANIFEST = DESIGN_DIR / "public_source_percent_b_money_flow_bounded_bt_design_manifest.json"
DESIGN_ROWS = DESIGN_DIR / "planned_row_table.csv"
RUN_MANIFEST = RUN_DIR / "public_source_percent_b_money_flow_bounded_bt_run_manifest.json"
RUN_CONSISTENCY = RUN_DIR / "public_source_percent_b_money_flow_bounded_bt_run_consistency_check.json"
RUN_ROWS = RUN_DIR / "row_level_results.csv"
RUN_CRITERIA = RUN_DIR / "numeric_criteria_results.csv"

STALE_RUN_NEXT_ACTION = "run_public_source_percent_b_money_flow_bounded_bt_lane"
NEXT_ACTION = "select_next_public_source_candidate_or_review_batch_candidates"
FALLBACK_NEXT_ACTION = "percent_b_money_flow_completed_failed_no_rerun_authorized"
PRIMARY_VARIANT_ID = "percent_b_mfi_spy_bil_primary_v1"
PRE_REGISTERED_EXPOSURE_UPPER_BOUND = 0.45

STATUS_FILES_TO_SCAN = (
    Path("strategy_lab") / "RESEARCH_ROADMAP.md",
    Path("strategy_lab") / "strategy_registry.yaml",
    Path("strategy_lab") / "research_os" / "research" / "research_queue.yaml",
    Path("evidence") / "research_state" / "latest" / "research_state_manifest.json",
    Path("evidence") / "research_state" / "latest" / "current_research_state.md",
)

REQUIRED_FILES = (
    "percent_b_state_reconciliation_manifest.json",
    "percent_b_state_reconciliation_summary.md",
    "evidence_paths_inspected.md",
    "chronology_decision.md",
    "percent_b_current_status.md",
    "queue_status_review.md",
    "guardrail_checklist.json",
    "percent_b_state_reconciliation_next_action.md",
    "percent_b_state_reconciliation_consistency_check.json",
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


def variant_ids(rows: list[dict[str, str]]) -> list[str]:
    return [row.get("variant_id", "") for row in rows if row.get("variant_id")]


def primary_row(rows: list[dict[str, str]]) -> dict[str, str]:
    return next((row for row in rows if row.get("variant_id") == PRIMARY_VARIANT_ID), {})


def scan_status_files(root: Path) -> list[dict[str, str]]:
    matches: list[dict[str, str]] = []
    for relative_path in STATUS_FILES_TO_SCAN:
        path = root / relative_path
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if STALE_RUN_NEXT_ACTION in text:
            matches.append(
                {
                    "path": str(relative_path),
                    "matched_text": STALE_RUN_NEXT_ACTION,
                    "action": "not_updated_by_reconciliation_runner",
                    "reason": "status_file_contains_stale_percent_b_run_next_action",
                }
            )
    return matches


def evidence_paths(root: Path) -> list[dict[str, Any]]:
    paths = [
        ("design_evidence", DESIGN_DIR),
        ("run_evidence", RUN_DIR),
        ("batch_intake_evidence", BATCH_INTAKE_DIR),
        ("intake_evidence", INTAKE_DIR),
        ("source_intake_candidate", SOURCE_INTAKE_PATH),
        ("design_manifest", DESIGN_MANIFEST),
        ("run_manifest", RUN_MANIFEST),
        ("run_row_level_results", RUN_ROWS),
        ("run_numeric_criteria", RUN_CRITERIA),
    ]
    return [
        {
            "name": name,
            "path": str((root / relative).resolve()),
            "exists": (root / relative).exists(),
        }
        for name, relative in paths
    ]


def chronology_decision(
    design_manifest: dict[str, Any],
    run_manifest: dict[str, Any],
    design_rows: list[dict[str, str]],
    run_rows: list[dict[str, str]],
) -> tuple[str, bool, str]:
    if not run_manifest:
        return (
            "run_evidence_missing",
            False,
            "Run manifest missing; stale design status cannot be superseded from local evidence.",
        )
    design_set = set(variant_ids(design_rows))
    run_set = set(run_manifest.get("evaluated_variant_ids") or variant_ids(run_rows))
    exact_variant_match = bool(design_set) and design_set == run_set
    run_complete = (
        run_manifest.get("public_source_percent_b_money_flow_bounded_bt_lane_run") is True
        and run_manifest.get("variant_count_planned") == 5
        and run_manifest.get("variant_count_evaluated") == 5
        and exact_variant_match
    )
    run_downstream = (
        run_complete
        and run_manifest.get("source_design_run_ready") is True
        and run_manifest.get("source_id") == design_manifest.get("source_id") == SOURCE_ID
        and run_manifest.get("lane_id") == design_manifest.get("lane_id") == LANE_ID
    )
    if run_downstream:
        return (
            "design_packet_stale_relative_to_completed_run",
            True,
            "Run evidence evaluates the exact five planned design rows and is logically downstream of the design packet, even if regenerated design timestamps are later.",
        )
    return (
        "run_evidence_missing",
        False,
        "Run evidence exists but did not verify as the completed downstream Percent B run.",
    )


def guardrails() -> dict[str, bool]:
    return {
        "percent_b_lane_rerun": False,
        "backtest_run": False,
        "bounded_run_implementation_created": False,
        "design_regenerated": False,
        "robustness_report_created": False,
        "results_audit_created": False,
        "criteria_relaxed": False,
        "thresholds_tuned": False,
        "public_source_scraped": False,
        "additional_public_sources_ingested": False,
        "provider_download": False,
        "intraday_data_used": False,
        "new_packages_installed": False,
        "strategy_discovery_run": False,
        "candidate_exhaustive_run": False,
        "promotion_candidates_created": False,
        "paper_demo_observation_activated": False,
        "broker_api_called": False,
        "broker_orders_submitted": False,
        "broker_orders_cancelled": False,
        "broker_orders_reconciled": False,
        "live_orders": False,
        "real_money_recommendation": False,
        "public_source_or_high_return_treated_as_profitability_proof": False,
    }


def build_manifest(root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    design_manifest = read_json(root / DESIGN_MANIFEST)
    run_manifest = read_json(root / RUN_MANIFEST)
    run_consistency = read_json(root / RUN_CONSISTENCY)
    design_rows = read_csv_rows(root / DESIGN_ROWS)
    run_rows = read_csv_rows(root / RUN_ROWS)
    criteria_rows = read_csv_rows(root / RUN_CRITERIA)
    primary = primary_row(run_rows)
    primary_criteria = primary_row(criteria_rows) or primary
    status_matches = scan_status_files(root)
    chronology, downstream, chronology_note = chronology_decision(design_manifest, run_manifest, design_rows, run_rows)

    primary_exposure = parse_float(primary.get("average_spy_exposure_share"))
    primary_criteria_pass = parse_bool(primary_criteria.get("numeric_criteria_pass"))
    primary_exposure_pass = parse_bool(primary_criteria.get("primary_spy_exposure_bounds_pass"))
    failure_reason = (
        "average_spy_exposure_above_pre_registered_sparse_signal_bound"
        if primary and not primary_criteria_pass and not primary_exposure_pass
        else "not_applicable_or_unverified"
    )
    queue_updated = False
    next_action = NEXT_ACTION if downstream else FALLBACK_NEXT_ACTION
    manifest = {
        "created_utc": now_utc(),
        "evidence_path": str((root / OUTPUT_DIR).resolve()),
        "percent_b_money_flow_state_reconciliation_only": True,
        "source_id": SOURCE_ID,
        "lane_id": LANE_ID,
        "family_id": FAMILY_ID,
        "design_evidence_exists": (root / DESIGN_MANIFEST).exists(),
        "run_evidence_exists": (root / RUN_MANIFEST).exists(),
        "batch_intake_evidence_exists": (root / BATCH_INTAKE_DIR).exists(),
        "public_source_intake_evidence_exists": (root / INTAKE_DIR).exists(),
        "source_intake_candidate_exists": (root / SOURCE_INTAKE_PATH).exists(),
        "design_created_utc": design_manifest.get("created_utc", ""),
        "run_created_utc": run_manifest.get("created_utc", ""),
        "design_next_action": design_manifest.get("next_action", ""),
        "run_next_action": run_manifest.get("next_action", ""),
        "chronology_decision": chronology,
        "chronology_note": chronology_note,
        "run_logically_downstream_of_design": downstream,
        "design_variant_count": len(design_rows),
        "run_variant_count": len(run_rows),
        "design_run_variant_set_match": set(variant_ids(design_rows))
        == set(run_manifest.get("evaluated_variant_ids") or variant_ids(run_rows)),
        "current_percent_b_status": "completed_diagnostic_failed_pre_registered_criteria_no_rerun_authorized",
        "variant_count_planned": run_manifest.get("variant_count_planned", 0),
        "variant_count_evaluated": run_manifest.get("variant_count_evaluated", 0),
        "data_blocked_row_count": run_manifest.get("data_blocked_row_count", 0),
        "primary_row_numeric_criteria_pass": run_manifest.get("primary_row_numeric_criteria_pass"),
        "primary_failure_reason": failure_reason,
        "primary_average_spy_exposure_share": primary_exposure,
        "pre_registered_spy_exposure_upper_bound": PRE_REGISTERED_EXPOSURE_UPPER_BOUND,
        "primary_total_return": parse_float(primary.get("total_return")),
        "primary_max_drawdown": parse_float(primary.get("max_drawdown")),
        "primary_drawdown_reduction_versus_spy_buy_hold": parse_float(
            primary.get("drawdown_reduction_versus_spy_buy_hold")
        ),
        "primary_spy_exposure_bounds_pass": primary_exposure_pass,
        "exposure_invariant_passed": run_manifest.get("exposure_invariant_passed"),
        "max_daily_exposure": run_manifest.get("max_daily_exposure"),
        "max_daily_weight_sum": run_manifest.get("max_daily_weight_sum"),
        "invariant_failure_count": run_manifest.get("invariant_failure_count"),
        "run_consistency_passed": run_consistency.get("consistency_passed"),
        "results_interpretable": run_manifest.get("results_interpretable"),
        "usable_diagnostic_evidence": run_manifest.get("usable_diagnostic_evidence"),
        "outputs_diagnostic_only": run_manifest.get("outputs_diagnostic_only"),
        "outputs_non_promotable": run_manifest.get("outputs_non_promotable"),
        "candidate_exhaustive_ready": run_manifest.get("candidate_exhaustive_ready"),
        "paper_demo_eligible": run_manifest.get("paper_demo_eligible"),
        "queue_status_file_updated": queue_updated,
        "queue_status_update_reason": "no_current_queue_pointer_to_percent_b_run_next_action_found"
        if not status_matches
        else "stale_percent_b_pointer_found_but_not_auto_updated_by_reconciliation_runner",
        "stale_status_pointer_count": len(status_matches),
        "stale_status_pointer_paths": [match["path"] for match in status_matches],
        "current_authorized_next_action": next_action,
        "next_action": next_action,
        **guardrails(),
    }
    support = {
        "design_manifest": design_manifest,
        "run_manifest": run_manifest,
        "run_consistency": run_consistency,
        "design_rows": design_rows,
        "run_rows": run_rows,
        "criteria_rows": criteria_rows,
        "primary_row": primary,
        "primary_criteria": primary_criteria,
        "status_matches": status_matches,
        "evidence_paths": evidence_paths(root),
    }
    return manifest, support


def evidence_paths_md(paths: list[dict[str, Any]]) -> str:
    lines = ["# Evidence Paths Inspected", ""]
    for row in paths:
        lines.append(f"- `{row['name']}`: `{row['path']}` (exists: `{row['exists']}`)")
    return "\n".join(lines) + "\n"


def chronology_md(manifest: dict[str, Any]) -> str:
    return f"""# Chronology Decision

Decision: `{manifest['chronology_decision']}`

Run logically downstream of design: `{manifest['run_logically_downstream_of_design']}`

Design created UTC: `{manifest['design_created_utc']}`

Run created UTC: `{manifest['run_created_utc']}`

Design next action: `{manifest['design_next_action']}`

Run next action: `{manifest['run_next_action']}`

Design/run variant set match: `{manifest['design_run_variant_set_match']}`

Note: {manifest['chronology_note']}
"""


def status_md(manifest: dict[str, Any]) -> str:
    return f"""# Current Percent B Status

Current status: `{manifest['current_percent_b_status']}`

Rows planned/evaluated: `{manifest['variant_count_planned']} / {manifest['variant_count_evaluated']}`

Data-blocked rows: `{manifest['data_blocked_row_count']}`

Primary row criteria pass: `{manifest['primary_row_numeric_criteria_pass']}`

Primary failure reason: `{manifest['primary_failure_reason']}`

Primary average SPY exposure: `{manifest['primary_average_spy_exposure_share']:.4f}`

Pre-registered sparse-signal exposure upper bound: `{manifest['pre_registered_spy_exposure_upper_bound']:.4f}`

Primary total return: `{manifest['primary_total_return']:.4f}`

Primary max drawdown: `{manifest['primary_max_drawdown']:.4f}`

Primary drawdown reduction versus SPY buy-hold: `{manifest['primary_drawdown_reduction_versus_spy_buy_hold']:.4f}`

Exposure invariant passed: `{manifest['exposure_invariant_passed']}`

Invariant failures: `{manifest['invariant_failure_count']}`

Results interpretable: `{manifest['results_interpretable']}`

Usable diagnostic evidence: `{manifest['usable_diagnostic_evidence']}`

Outputs diagnostic/non-promotable: `{manifest['outputs_diagnostic_only']}` / `{manifest['outputs_non_promotable']}`

Candidate-exhaustive ready: `{manifest['candidate_exhaustive_ready']}`

Paper/demo eligible: `{manifest['paper_demo_eligible']}`
"""


def queue_review_md(manifest: dict[str, Any], matches: list[dict[str, str]]) -> str:
    lines = [
        "# Queue / Status Review",
        "",
        f"Queue/status file updated: `{manifest['queue_status_file_updated']}`",
        "",
        f"Reason: `{manifest['queue_status_update_reason']}`",
        "",
        f"Stale status pointer count: `{manifest['stale_status_pointer_count']}`",
        "",
    ]
    if matches:
        lines.append("Stale pointers found:")
        for match in matches:
            lines.append(f"- `{match['path']}`: `{match['matched_text']}`")
    else:
        lines.append("No stale Percent B run next-action pointer was found in roadmap, registry, research queue, or latest research-state files.")
    lines.append("")
    lines.append(f"Current authorized next action recorded by reconciliation: `{manifest['current_authorized_next_action']}`")
    return "\n".join(lines) + "\n"


def summary_md(manifest: dict[str, Any]) -> str:
    return f"""# Percent B Money Flow State Reconciliation

Source ID: `{manifest['source_id']}`

Lane ID: `{manifest['lane_id']}`

Chronology decision: `{manifest['chronology_decision']}`

Current Percent B status: `{manifest['current_percent_b_status']}`

Run evidence exists: `{manifest['run_evidence_exists']}`

Run consistency passed: `{manifest['run_consistency_passed']}`

Primary row criteria pass: `{manifest['primary_row_numeric_criteria_pass']}`

Primary failure reason: `{manifest['primary_failure_reason']}`

Queue/status file updated: `{manifest['queue_status_file_updated']}`

Current authorized next action: `{manifest['current_authorized_next_action']}`

No Percent B rerun, backtest, design regeneration, robustness report, results audit, criterion relaxation, threshold tuning, source scraping, provider download, intraday data use, strategy discovery, candidate_exhaustive, promotion, paper/demo activation, broker/live path, or real-money recommendation occurred.
"""


def next_action_md(next_action: str) -> str:
    return f"""# Percent B State Reconciliation Next Action

Exact next action:

`{next_action}`

Do not execute the next action in this task.
"""


def consistency_check(manifest: dict[str, Any], output: Path) -> dict[str, Any]:
    required = {name: (output / name).exists() for name in REQUIRED_FILES}
    required["percent_b_state_reconciliation_consistency_check.json"] = True
    checks: dict[str, Any] = {
        "reconciliation_only": manifest["percent_b_money_flow_state_reconciliation_only"] is True,
        "correct_source_lane_family": manifest["source_id"] == SOURCE_ID
        and manifest["lane_id"] == LANE_ID
        and manifest["family_id"] == FAMILY_ID,
        "design_and_run_evidence_exist": manifest["design_evidence_exists"] is True
        and manifest["run_evidence_exists"] is True,
        "chronology_reconciled": manifest["chronology_decision"]
        == "design_packet_stale_relative_to_completed_run"
        and manifest["run_logically_downstream_of_design"] is True,
        "completed_run_verified": manifest["variant_count_planned"] == 5
        and manifest["variant_count_evaluated"] == 5
        and manifest["data_blocked_row_count"] == 0,
        "primary_failed_for_sparse_exposure_bound": manifest["primary_row_numeric_criteria_pass"] is False
        and manifest["primary_failure_reason"] == "average_spy_exposure_above_pre_registered_sparse_signal_bound"
        and manifest["primary_average_spy_exposure_share"] > manifest["pre_registered_spy_exposure_upper_bound"]
        and manifest["primary_spy_exposure_bounds_pass"] is False,
        "invariants_and_run_consistency_clean": manifest["exposure_invariant_passed"] is True
        and manifest["invariant_failure_count"] == 0
        and manifest["run_consistency_passed"] is True,
        "diagnostic_non_promotable": manifest["outputs_diagnostic_only"] is True
        and manifest["outputs_non_promotable"] is True
        and manifest["candidate_exhaustive_ready"] is False
        and manifest["paper_demo_eligible"] is False,
        "queue_not_mutated_without_safe_pointer": manifest["queue_status_file_updated"] is False,
        "next_action_moves_on": manifest["next_action"] in {NEXT_ACTION, FALLBACK_NEXT_ACTION},
        "guardrails_clean": all(
            manifest[key] is False
            for key in guardrails()
        ),
        "required_files_present": all(required.values()),
        "required_files": required,
    }
    checks["consistency_passed"] = all(
        value is True for key, value in checks.items() if key != "required_files"
    )
    return checks


def run(root: Path = ROOT) -> dict[str, Any]:
    output = root / OUTPUT_DIR
    output.mkdir(parents=True, exist_ok=True)
    manifest, support = build_manifest(root)

    write_json(output / "percent_b_state_reconciliation_manifest.json", manifest)
    write_text(output / "percent_b_state_reconciliation_summary.md", summary_md(manifest))
    write_text(output / "evidence_paths_inspected.md", evidence_paths_md(support["evidence_paths"]))
    write_text(output / "chronology_decision.md", chronology_md(manifest))
    write_text(output / "percent_b_current_status.md", status_md(manifest))
    write_text(output / "queue_status_review.md", queue_review_md(manifest, support["status_matches"]))
    write_json(output / "guardrail_checklist.json", guardrails())
    write_text(output / "percent_b_state_reconciliation_next_action.md", next_action_md(manifest["next_action"]))
    write_csv(
        output / "status_file_scan.csv",
        support["status_matches"],
        ["path", "matched_text", "action", "reason"],
    )
    check = consistency_check(manifest, output)
    write_json(output / "percent_b_state_reconciliation_consistency_check.json", check)
    return {**manifest, "output_dir": str(output.resolve()), "consistency_passed": check["consistency_passed"]}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
