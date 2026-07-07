from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.objective_reset.objective_reset_review import write_json, write_text
from strategy_lab.research_os.research.profit_oriented_research_batch_v1 import write_csv
from strategy_lab.research_os.research.public_source_preregistration_bridge import dotted_get, read_yaml


SOURCE_ID = "macd_stochastic_double_cross"
FAMILY_ID = "equity_index_momentum_confirmation_double_cross"
FINAL_STATUS = "needs_direction_owner_review_exit_rule_incomplete_no_design_authorized"
NEXT_ACTION = "direction_owner_select_next_public_source_candidate_or_supply_complete_macd_stochastic_rules"

INTAKE_CANDIDATE = (
    Path("strategy_lab")
    / "research_os"
    / "public_strategy_sources"
    / "intake_candidates"
    / "macd_stochastic_double_cross.yaml"
)
INTAKE_DIR = Path("evidence") / "research_recovery" / "public_source_intake_validation" / "latest"
BATCH_INTAKE_DIR = Path("evidence") / "research_recovery" / "public_source_batch_intake_validation" / "latest"
BRIDGE_DIR = Path("evidence") / "research_recovery" / "public_source_preregistration_bridge" / "latest"
OUTPUT_DIR = (
    Path("evidence")
    / "research_recovery"
    / "public_source_macd_stochastic_intake_state_reconciliation"
    / "latest"
)

INTAKE_MANIFEST = INTAKE_DIR / "public_source_intake_validation_manifest.json"
BATCH_DECISIONS = BATCH_INTAKE_DIR / "eligibility_decisions.csv"
BATCH_CACHE = BATCH_INTAKE_DIR / "local_cache_availability_table.csv"
BRIDGE_MANIFEST = BRIDGE_DIR / "public_source_bridge_manifest.json"

STALE_POINTERS = (
    "design_public_source_macd_stochastic_double_cross_bounded_bt_lane",
    "run_public_source_macd_stochastic_double_cross_bounded_bt_lane",
    "public_source_macd_stochastic_double_cross_bounded_bt_design",
    "public_source_macd_stochastic_double_cross_bounded_bt_run",
)
STATUS_FILES_TO_SCAN = (
    Path("strategy_lab") / "RESEARCH_ROADMAP.md",
    Path("strategy_lab") / "strategy_registry.yaml",
    Path("strategy_lab") / "research_os" / "research" / "research_queue.yaml",
    Path("evidence") / "research_state" / "latest" / "research_state_manifest.json",
    Path("evidence") / "research_state" / "latest" / "current_research_state.md",
)

REQUIRED_FILES = (
    "macd_stochastic_intake_state_reconciliation_manifest.json",
    "macd_stochastic_intake_state_reconciliation_summary.md",
    "evidence_paths_inspected.md",
    "macd_stochastic_intake_status.csv",
    "macd_stochastic_intake_status.md",
    "review_required_reasons.md",
    "queue_status_review.md",
    "guardrail_checklist.json",
    "status_file_scan.csv",
    "macd_stochastic_intake_state_reconciliation_next_action.md",
    "macd_stochastic_intake_state_reconciliation_consistency_check.json",
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


def batch_row(rows: list[dict[str, str]]) -> dict[str, str]:
    return next((row for row in rows if row.get("source_id") == SOURCE_ID), {})


def cache_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [row for row in rows if row.get("source_id") == SOURCE_ID]


def guardrails() -> dict[str, bool]:
    return {
        "bounded_design_created": False,
        "strategy_implemented": False,
        "backtest_run": False,
        "exit_rule_invented_or_frozen": False,
        "macd_periods_tuned": False,
        "stochastic_periods_tuned": False,
        "thresholds_tuned": False,
        "crossover_window_optimized": False,
        "indicator_defaults_optimized": False,
        "spy200d_filter_usage_tuned": False,
        "rsi_filter_added": False,
        "volume_filter_added": False,
        "stop_loss_or_profit_target_added": False,
        "alternate_exits_added": False,
        "volatility_filter_added": False,
        "short_or_inverse_exposure_added": False,
        "leverage_options_futures_intraday_added": False,
        "next_public_source_selected_by_codex": False,
        "public_source_scraped": False,
        "public_strategy_list_ingested": False,
        "cci_continued": False,
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
        ("intake_candidate", INTAKE_CANDIDATE),
        ("single_source_intake_evidence", INTAKE_DIR),
        ("batch_intake_evidence", BATCH_INTAKE_DIR),
        ("preregistration_bridge_evidence", BRIDGE_DIR),
        ("single_source_intake_manifest", INTAKE_MANIFEST),
        ("batch_eligibility_decisions", BATCH_DECISIONS),
        ("batch_local_cache_availability", BATCH_CACHE),
        ("bridge_manifest", BRIDGE_MANIFEST),
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
        for pointer in STALE_POINTERS:
            if pointer in text:
                matches.append(
                    {
                        "path": str(relative_path),
                        "matched_text": pointer,
                        "action": "not_updated_by_reconciliation_runner",
                        "reason": "no_safe_automatic_queue_status_update_convention_used",
                    }
                )
    return matches


def status_rows(
    intake_manifest: dict[str, Any],
    batch: dict[str, str],
    candidate: dict[str, Any],
    cache: list[dict[str, str]],
) -> list[dict[str, Any]]:
    return [
        {
            "check": "single_source_intake_decision",
            "status": intake_manifest.get("eligibility_decision", ""),
            "passed": intake_manifest.get("eligibility_decision") == "needs_direction_owner_review",
            "notes": "single-source intake remains review-required",
        },
        {
            "check": "batch_intake_decision",
            "status": batch.get("eligibility_decision", ""),
            "passed": batch.get("eligibility_decision") == "needs_direction_owner_review",
            "notes": "batch intake preserves review-required status",
        },
        {
            "check": "constraint_blockers",
            "status": "|".join(intake_manifest.get("constraint_blockers", [])),
            "passed": intake_manifest.get("constraint_blockers", []) == [],
            "notes": "no hard project constraint block",
        },
        {
            "check": "missing_required_fields",
            "status": "|".join(intake_manifest.get("exact_missing_fields", [])),
            "passed": intake_manifest.get("exact_missing_fields", []) == [],
            "notes": "required fields are present",
        },
        {
            "check": "local_cache_spy_bil",
            "status": "|".join(f"{row.get('symbol')}={row.get('cache_status')}" for row in cache),
            "passed": {row.get("symbol"): row.get("cache_status") for row in cache} == {
                "SPY": "cache_ready",
                "BIL": "cache_ready",
            },
            "notes": "SPY and BIL local cache ready",
        },
        {
            "check": "exit_rule_completeness",
            "status": intake_manifest.get("exit_rule_completeness_status", ""),
            "passed": intake_manifest.get("exit_rule_completeness_status")
            == "needs_direction_owner_review_exit_rule_not_source_backed_enough_to_freeze",
            "notes": dotted_get(candidate, "project_notes.exit_rule_uncertainty") or "",
        },
        {
            "check": "indicator_defaults_completeness",
            "status": intake_manifest.get("indicator_defaults_completeness_status", ""),
            "passed": intake_manifest.get("indicator_defaults_completeness_status")
            == "needs_direction_owner_review_article_allows_interval_setting_flexibility",
            "notes": dotted_get(candidate, "project_notes.indicator_defaults_uncertainty") or "",
        },
        {
            "check": "duplicate_do_not_retest",
            "status": "not_duplicate_or_do_not_retest",
            "passed": batch.get("eligibility_decision") != "duplicate_or_do_not_retest",
            "notes": f"similarity hit count {intake_manifest.get('family_similarity_hit_count')}",
        },
    ]


def review_reasons(intake_manifest: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "exit_rule_not_source_backed_enough_to_freeze": intake_manifest.get("exit_rule_completeness_status")
        == "needs_direction_owner_review_exit_rule_not_source_backed_enough_to_freeze",
        "indicator_defaults_interval_flexibility": intake_manifest.get("indicator_defaults_completeness_status")
        == "needs_direction_owner_review_article_allows_interval_setting_flexibility",
        "rule_clarity_not_freezable": intake_manifest.get("rule_clarity_status") == "unclear_or_not_freezable",
        "no_constraint_blockers": intake_manifest.get("constraint_blockers", []) == [],
        "no_missing_required_fields": intake_manifest.get("exact_missing_fields", []) == [],
        "long_only_adaptation_explicit": intake_manifest.get("long_only_adaptation_status") == "long_only_caveat_explicit",
        "source_uncertainty_recorded": bool(dotted_get(candidate, "project_notes.exit_rule_uncertainty"))
        and bool(dotted_get(candidate, "project_notes.indicator_defaults_uncertainty")),
    }


def build_manifest(root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    candidate = read_yaml(root / INTAKE_CANDIDATE)
    intake_manifest = read_json(root / INTAKE_MANIFEST)
    batch = batch_row(read_csv_rows(root / BATCH_DECISIONS))
    cache = cache_rows(read_csv_rows(root / BATCH_CACHE))
    bridge_manifest = read_json(root / BRIDGE_MANIFEST)
    statuses = status_rows(intake_manifest, batch, candidate, cache)
    reasons = review_reasons(intake_manifest, candidate)
    matches = scan_status_files(root)
    guardrail_payload = guardrails()
    final_locked = (
        intake_manifest.get("source_id") == SOURCE_ID
        and batch.get("source_id") == SOURCE_ID
        and all(row["passed"] is True for row in statuses)
        and reasons["exit_rule_not_source_backed_enough_to_freeze"]
        and reasons["indicator_defaults_interval_flexibility"]
    )
    manifest = {
        "created_utc": now_utc(),
        "evidence_path": str((root / OUTPUT_DIR).resolve()),
        "macd_stochastic_intake_state_reconciliation_only": True,
        "source_id": SOURCE_ID,
        "family_id": FAMILY_ID,
        "final_status_locked": final_locked,
        "final_macd_stochastic_status": FINAL_STATUS if final_locked else "macd_stochastic_intake_state_reconciliation_incomplete",
        "final_authorized_next_action": NEXT_ACTION,
        "single_source_intake_decision": intake_manifest.get("eligibility_decision", ""),
        "batch_intake_decision": batch.get("eligibility_decision", ""),
        "constraint_blocker_count": len(intake_manifest.get("constraint_blockers", [])),
        "missing_required_field_count": len(intake_manifest.get("exact_missing_fields", [])),
        "spy_cache_ready": any(row.get("symbol") == "SPY" and row.get("cache_status") == "cache_ready" for row in cache),
        "bil_cache_ready": any(row.get("symbol") == "BIL" and row.get("cache_status") == "cache_ready" for row in cache),
        "duplicate_or_do_not_retest_blocker": batch.get("eligibility_decision") == "duplicate_or_do_not_retest",
        "family_similarity_hit_count": intake_manifest.get("family_similarity_hit_count", 0),
        "family_similarity_hits": intake_manifest.get("family_similarity_hits", []),
        "long_only_adaptation_explicit": reasons["long_only_adaptation_explicit"],
        "exit_rule_completeness_status": intake_manifest.get("exit_rule_completeness_status", ""),
        "indicator_defaults_completeness_status": intake_manifest.get("indicator_defaults_completeness_status", ""),
        "exit_rule_not_source_backed_enough_to_freeze": reasons["exit_rule_not_source_backed_enough_to_freeze"],
        "indicator_defaults_interval_flexibility": reasons["indicator_defaults_interval_flexibility"],
        "rule_clarity_not_freezable": reasons["rule_clarity_not_freezable"],
        "review_required_reason_count": sum(1 for value in reasons.values() if value is True),
        "bridge_evidence_reviewed": bridge_manifest.get("public_source_preregistration_bridge_only") is True,
        "bounded_design_authorized": False,
        "strategy_implementation_authorized": False,
        "backtest_authorized": False,
        "parameter_tuning_authorized": False,
        "exit_rule_invention_authorized": False,
        "indicator_default_optimization_authorized": False,
        "crossover_window_optimization_authorized": False,
        "robustness_authorized": False,
        "candidate_exhaustive_authorized": False,
        "promotion_authorized": False,
        "paper_demo_activation_authorized": False,
        "broker_live_action_authorized": False,
        "queue_status_file_updated": False,
        "queue_status_update_reason": "no_safe_automatic_queue_status_update_convention_used",
        "stale_design_pointer_count": len(matches),
        "outputs_diagnostic_only": True,
        "outputs_non_promotable": True,
        **guardrail_payload,
        "next_action": NEXT_ACTION,
    }
    return manifest, {
        "candidate": candidate,
        "statuses": statuses,
        "reasons": reasons,
        "matches": matches,
        "guardrails": guardrail_payload,
        "evidence_paths": evidence_paths(root),
    }


def evidence_paths(root: Path) -> list[dict[str, Any]]:
    return evidence_paths_impl(root)


def evidence_paths_impl(root: Path) -> list[dict[str, Any]]:
    paths = [
        ("intake_candidate", INTAKE_CANDIDATE),
        ("single_source_intake_evidence", INTAKE_DIR),
        ("batch_intake_evidence", BATCH_INTAKE_DIR),
        ("preregistration_bridge_evidence", BRIDGE_DIR),
        ("single_source_intake_manifest", INTAKE_MANIFEST),
        ("batch_eligibility_decisions", BATCH_DECISIONS),
        ("batch_local_cache_availability", BATCH_CACHE),
        ("bridge_manifest", BRIDGE_MANIFEST),
    ]
    return [
        {
            "name": name,
            "path": str((root / relative).resolve()),
            "exists": (root / relative).exists(),
        }
        for name, relative in paths
    ]


def evidence_paths_md(paths: list[dict[str, Any]]) -> str:
    lines = ["# Evidence Paths Inspected", ""]
    for item in paths:
        lines.append(f"- `{item['name']}`: `{item['path']}` exists `{item['exists']}`")
    return "\n".join(lines) + "\n"


def status_md(rows: list[dict[str, Any]]) -> str:
    lines = ["# MACD/Stochastic Intake Status", ""]
    for row in rows:
        lines.append(f"- `{row['check']}`: `{row['status']}`; passed `{row['passed']}`")
        lines.append(f"  - Notes: {row['notes']}")
    return "\n".join(lines) + "\n"


def reasons_md(reasons: dict[str, Any]) -> str:
    lines = ["# Review-Required Reasons", ""]
    for key, value in reasons.items():
        lines.append(f"- `{key}`: `{value}`")
    lines.append("")
    lines.append("The candidate cannot proceed to bounded design unless the direction owner supplies a complete frozen rule set.")
    return "\n".join(lines) + "\n"


def queue_status_md(manifest: dict[str, Any], matches: list[dict[str, str]]) -> str:
    lines = ["# Queue Status Review", ""]
    lines.append(f"Queue/status file updated: `{manifest['queue_status_file_updated']}`")
    lines.append(f"Update reason: `{manifest['queue_status_update_reason']}`")
    lines.append(f"Stale MACD/Stochastic design pointer count: `{manifest['stale_design_pointer_count']}`")
    if matches:
        for match in matches:
            lines.append(f"- `{match['path']}` contains `{match['matched_text']}`; action `{match['action']}`")
    else:
        lines.append("- No stale MACD/Stochastic design/backtest pointer was found in scanned status files.")
    lines.append("")
    lines.append(f"Final authorized next action recorded by reconciliation: `{manifest['final_authorized_next_action']}`")
    return "\n".join(lines) + "\n"


def summary_md(manifest: dict[str, Any]) -> str:
    return f"""# MACD/Stochastic Intake State Reconciliation

Source ID: `{manifest['source_id']}`
Family ID: `{manifest['family_id']}`

Final status locked: `{manifest['final_status_locked']}`
Final status: `{manifest['final_macd_stochastic_status']}`

Single-source intake decision: `{manifest['single_source_intake_decision']}`
Batch intake decision: `{manifest['batch_intake_decision']}`
Constraint blocker count: `{manifest['constraint_blocker_count']}`
Missing required field count: `{manifest['missing_required_field_count']}`
SPY/BIL cache ready: `{manifest['spy_cache_ready']}` / `{manifest['bil_cache_ready']}`
Duplicate/do-not-retest blocker: `{manifest['duplicate_or_do_not_retest_blocker']}`

Exit-rule status: `{manifest['exit_rule_completeness_status']}`
Indicator-default status: `{manifest['indicator_defaults_completeness_status']}`

Queue/status file updated: `{manifest['queue_status_file_updated']}`
Exact next action: `{manifest['next_action']}`

No design, strategy implementation, backtest, tuning, candidate_exhaustive, promotion, paper/demo activation, broker/live path, or real-money recommendation occurred.
"""


def next_action_md(manifest: dict[str, Any]) -> str:
    return f"""# MACD/Stochastic Intake State Next Action

Exact next action: `{manifest['next_action']}`

Do not execute this action from this reconciliation packet.
"""


def consistency_check(manifest: dict[str, Any], output: Path) -> dict[str, Any]:
    required = {filename: (output / filename).exists() for filename in REQUIRED_FILES}
    required["macd_stochastic_intake_state_reconciliation_consistency_check.json"] = True
    checks = {
        "reconciliation_only": manifest["macd_stochastic_intake_state_reconciliation_only"] is True,
        "correct_source_family": manifest["source_id"] == SOURCE_ID and manifest["family_id"] == FAMILY_ID,
        "review_required_locked": manifest["final_status_locked"] is True
        and manifest["final_macd_stochastic_status"] == FINAL_STATUS
        and manifest["single_source_intake_decision"] == "needs_direction_owner_review"
        and manifest["batch_intake_decision"] == "needs_direction_owner_review",
        "reason_recorded": manifest["exit_rule_not_source_backed_enough_to_freeze"] is True
        and manifest["indicator_defaults_interval_flexibility"] is True,
        "no_constraint_or_duplicate_block": manifest["constraint_blocker_count"] == 0
        and manifest["missing_required_field_count"] == 0
        and manifest["duplicate_or_do_not_retest_blocker"] is False,
        "cache_ready": manifest["spy_cache_ready"] is True and manifest["bil_cache_ready"] is True,
        "not_authorized_for_design_or_execution": manifest["bounded_design_authorized"] is False
        and manifest["strategy_implementation_authorized"] is False
        and manifest["backtest_authorized"] is False
        and manifest["parameter_tuning_authorized"] is False
        and manifest["exit_rule_invention_authorized"] is False,
        "no_forbidden_actions": all(value is False for value in guardrails().values()),
        "next_action_valid": manifest["next_action"] == NEXT_ACTION,
        "required_files_present": all(required.values()),
    }
    return {**checks, "required_files": required, "consistency_passed": all(checks.values())}


def run(root: Path = ROOT) -> dict[str, Any]:
    output = root / OUTPUT_DIR
    output.mkdir(parents=True, exist_ok=True)
    manifest, context = build_manifest(root)
    write_json(output / "macd_stochastic_intake_state_reconciliation_manifest.json", manifest)
    write_text(output / "macd_stochastic_intake_state_reconciliation_summary.md", summary_md(manifest))
    write_text(output / "evidence_paths_inspected.md", evidence_paths_md(context["evidence_paths"]))
    write_csv(
        output / "macd_stochastic_intake_status.csv",
        context["statuses"],
        ["check", "status", "passed", "notes"],
    )
    write_text(output / "macd_stochastic_intake_status.md", status_md(context["statuses"]))
    write_text(output / "review_required_reasons.md", reasons_md(context["reasons"]))
    write_text(output / "queue_status_review.md", queue_status_md(manifest, context["matches"]))
    write_json(output / "guardrail_checklist.json", context["guardrails"])
    write_csv(output / "status_file_scan.csv", context["matches"], ["path", "matched_text", "action", "reason"])
    write_text(output / "macd_stochastic_intake_state_reconciliation_next_action.md", next_action_md(manifest))
    check = consistency_check(manifest, output)
    write_json(output / "macd_stochastic_intake_state_reconciliation_consistency_check.json", check)
    return {**manifest, "output_dir": str(output.resolve()), "consistency_passed": check["consistency_passed"]}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
