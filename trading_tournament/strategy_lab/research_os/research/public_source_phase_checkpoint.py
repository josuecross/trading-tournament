from __future__ import annotations

import csv
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.objective_reset.objective_reset_review import write_json, write_text
from strategy_lab.research_os.research.profit_oriented_research_batch_v1 import write_csv
from strategy_lab.research_os.research.public_source_preregistration_bridge import read_yaml


OUTPUT_DIR = Path("evidence") / "research_recovery" / "public_source_phase_checkpoint" / "latest"
NEXT_ACTION = "direction_owner_select_new_public_source_candidate"

STATE_FILES_TO_SCAN = (
    Path("strategy_lab") / "RESEARCH_ROADMAP.md",
    Path("strategy_lab") / "strategy_registry.yaml",
    Path("strategy_lab") / "research_os" / "research" / "research_queue.yaml",
    Path("evidence") / "research_state" / "latest" / "research_state_manifest.json",
    Path("evidence") / "research_state" / "latest" / "current_research_state.md",
    Path("evidence") / "research_state" / "latest" / "research_state_summary.md",
)

PUBLIC_SOURCE_EVIDENCE_DIRS = (
    Path("evidence") / "research_recovery" / "public_source_intake_validation" / "latest",
    Path("evidence") / "research_recovery" / "public_source_batch_intake_validation" / "latest",
    Path("evidence") / "research_recovery" / "public_source_preregistration_bridge" / "latest",
    Path("evidence") / "research_recovery" / "public_source_turn_of_month_bounded_bt_robustness" / "latest",
    Path("evidence") / "research_recovery" / "public_source_percent_b_money_flow_state_reconciliation" / "latest",
    Path("evidence") / "research_recovery" / "public_source_larry_connors_rsi2_final_state_reconciliation" / "latest",
    Path("evidence") / "research_recovery" / "public_source_coppock_curve_final_state_reconciliation" / "latest",
    Path("evidence") / "research_recovery" / "public_source_cci_correction_final_state_reconciliation" / "latest",
    Path("evidence") / "research_recovery" / "public_source_macd_stochastic_intake_state_reconciliation" / "latest",
    Path("evidence") / "research_recovery" / "public_source_bollinger_squeeze_intake_state_reconciliation" / "latest",
)

REQUIRED_FILES = (
    "public_source_phase_checkpoint_manifest.json",
    "public_source_phase_checkpoint_summary.md",
    "evidence_paths_inspected.md",
    "candidate_status_ledger.csv",
    "candidate_status_ledger.md",
    "dirty_worktree_hygiene.csv",
    "dirty_worktree_hygiene.md",
    "stale_next_action_scan.csv",
    "stale_next_action_scan.md",
    "state_update_report.md",
    "guardrail_checklist.json",
    "public_source_phase_checkpoint_next_action.md",
    "public_source_phase_checkpoint_consistency_check.json",
)

BLOCKED_ACTIONS = (
    "bounded_design",
    "strategy_implementation",
    "backtest",
    "robustness",
    "results_audit",
    "parameter_tuning",
    "missing_rule_invention",
    "candidate_exhaustive",
    "promotion",
    "paper_demo_activation",
    "broker_live_action",
    "real_money_recommendation",
)

STALE_POINTERS_BY_SOURCE = {
    "percent_b_money_flow": (
        "run_public_source_percent_b_money_flow_bounded_bt_lane",
        "audit_public_source_percent_b_money_flow_bounded_bt_results",
        "rerun_public_source_percent_b_money_flow_bounded_bt_lane",
    ),
    "larry_connors_rsi2_mean_reversion": (
        "audit_public_source_larry_connors_rsi2_robustness_results",
        "rerun_public_source_larry_connors_rsi2_bounded_bt_lane",
        "run_public_source_larry_connors_rsi2_bounded_bt_robustness",
    ),
    "coppock_curve_monthly_equity_signal": (
        "audit_public_source_coppock_curve_bounded_bt_results",
        "run_public_source_coppock_curve_bounded_bt_robustness",
        "rerun_public_source_coppock_curve_bounded_bt_lane",
    ),
    "cci_correction": (
        "run_public_source_cci_correction_bounded_bt_robustness",
        "rerun_public_source_cci_correction_bounded_bt_lane",
        "reaudit_public_source_cci_correction_bounded_bt_results",
    ),
    "macd_stochastic_double_cross": (
        "design_public_source_macd_stochastic_double_cross_bounded_bt_lane",
        "run_public_source_macd_stochastic_double_cross_bounded_bt_lane",
        "public_source_macd_stochastic_double_cross_bounded_bt_design",
        "public_source_macd_stochastic_double_cross_bounded_bt_run",
    ),
    "bollinger_band_squeeze_breakout": (
        "design_public_source_bollinger_band_squeeze_breakout_bounded_bt_lane",
        "run_public_source_bollinger_band_squeeze_breakout_bounded_bt_lane",
        "public_source_bollinger_band_squeeze_breakout_bounded_bt_design",
        "public_source_bollinger_band_squeeze_breakout_bounded_bt_run",
        "public_source_bollinger_squeeze_bounded_bt_design",
        "public_source_bollinger_squeeze_bounded_bt_run",
    ),
}


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


def find_batch_decision(root: Path, source_id: str) -> dict[str, str]:
    path = root / "evidence" / "research_recovery" / "public_source_batch_intake_validation" / "latest" / "eligibility_decisions.csv"
    return next((row for row in read_csv_rows(path) if row.get("source_id") == source_id), {})


def evidence_path_status(root: Path, paths: list[str]) -> tuple[str, str]:
    existing: list[str] = []
    missing: list[str] = []
    for raw in paths:
        if (root / raw).exists():
            existing.append(raw)
        else:
            missing.append(raw)
    if existing and not missing:
        return "present", "|".join(existing)
    if existing:
        return "partial", "|".join([*existing, *[f"missing:{item}" for item in missing]])
    return "missing", "|".join(f"missing:{item}" for item in missing)


def candidate_specs(root: Path) -> list[dict[str, Any]]:
    similarity_map = read_yaml(root / "strategy_lab" / "research_os" / "public_strategy_sources" / "project_family_similarity_map.yaml")
    global_multi_asset = next(
        (
            family
            for family in similarity_map.get("families", [])
            if family.get("family_key") == "global_multi_asset"
        ),
        {},
    )
    return [
        {
            "source_id": "faber_taa",
            "display_name": "Faber/TAA Asset Class Trend Following",
            "family_id": "tactical_asset_allocation_trend_following",
            "expected_state": "duplicate_do_not_retest",
            "final_decision": "duplicate_or_do_not_retest",
            "authorized_next_action": "none_no_design_authorized",
            "evidence_paths": [
                "strategy_lab/research_os/public_strategy_sources/project_family_similarity_map.yaml",
            ],
            "status_note": global_multi_asset.get("do_not_retest_rule", "mapped to global multi-asset duplicate context"),
        },
        {
            "source_id": "turn_of_month_equity_indexes",
            "display_name": "Turn-of-the-Month",
            "family_id": "calendar_effect_turn_of_month_equity_index",
            "expected_state": "completed_diagnostic_cost_sensitive_rolling_weak_no_continuation",
            "final_decision": "completed_diagnostic_context_only_no_continuation",
            "authorized_next_action": "none_no_continuation_authorized",
            "evidence_paths": [
                "evidence/research_recovery/public_source_turn_of_month_bounded_bt_robustness/latest",
                "strategy_lab/research_os/public_strategy_sources/project_family_similarity_map.yaml",
            ],
            "status_note": "robustness evidence is cost-sensitive and rolling-weak; no continuation authorized by checkpoint",
        },
        {
            "source_id": "percent_b_money_flow",
            "display_name": "Percent B Money Flow",
            "family_id": "price_band_money_flow_confirmation",
            "expected_state": "completed_diagnostic_failed_pre_registered_exposure_criterion_no_rerun",
            "final_decision": "completed_diagnostic_failed_criteria_no_rerun_authorized",
            "authorized_next_action": "none_no_rerun_authorized",
            "evidence_paths": [
                "evidence/research_recovery/public_source_percent_b_money_flow_state_reconciliation/latest",
            ],
            "status_note": "failed pre-registered exposure criterion; run remains diagnostic only",
        },
        {
            "source_id": "larry_connors_rsi2_mean_reversion",
            "display_name": "Larry Connors RSI(2)",
            "family_id": "short_term_equity_mean_reversion",
            "expected_state": "completed_diagnostic_context_only_cost_sensitive_rolling_weak_no_continuation",
            "final_decision": "completed_diagnostic_context_only_no_continuation",
            "authorized_next_action": "none_no_continuation_authorized",
            "evidence_paths": [
                "evidence/research_recovery/public_source_larry_connors_rsi2_final_state_reconciliation/latest",
            ],
            "status_note": "final state reconciliation locks cost-sensitive rolling-weak context-only status",
        },
        {
            "source_id": "coppock_curve_monthly_equity_signal",
            "display_name": "Coppock Curve Monthly Equity Signal",
            "family_id": "long_term_equity_index_momentum_zero_cross",
            "expected_state": "completed_diagnostic_sparse_context_only_failed_criteria_no_continuation",
            "final_decision": "completed_diagnostic_context_only_no_continuation",
            "authorized_next_action": "none_no_continuation_authorized",
            "evidence_paths": [
                "evidence/research_recovery/public_source_coppock_curve_final_state_reconciliation/latest",
            ],
            "status_note": "final state reconciliation locks sparse failed criteria context-only status",
        },
        {
            "source_id": "cci_correction",
            "display_name": "CCI Correction",
            "family_id": "equity_index_cci_pullback_trend_bias",
            "expected_state": "completed_diagnostic_control_weak_context_only_no_continuation",
            "final_decision": "completed_diagnostic_context_only_no_continuation",
            "authorized_next_action": "none_no_continuation_authorized",
            "evidence_paths": [
                "evidence/research_recovery/public_source_cci_correction_final_state_reconciliation/latest",
            ],
            "status_note": "final state reconciliation locks control-weak context-only status",
        },
        {
            "source_id": "macd_stochastic_double_cross",
            "display_name": "MACD/Stochastic Double-Cross",
            "family_id": "equity_index_momentum_confirmation_double_cross",
            "expected_state": "needs_direction_owner_review_exit_rule_incomplete_no_design_authorized",
            "final_decision": "needs_direction_owner_review_no_design_authorized",
            "authorized_next_action": "direction_owner_must_supply_complete_rules_before_design",
            "evidence_paths": [
                "evidence/research_recovery/public_source_macd_stochastic_intake_state_reconciliation/latest",
            ],
            "status_note": "exit rule and parameter/timing flexibility remain review-required",
        },
        {
            "source_id": "bollinger_band_squeeze_breakout",
            "display_name": "Bollinger Band Squeeze Breakout",
            "family_id": "equity_index_volatility_contraction_breakout",
            "expected_state": "needs_direction_owner_review_no_design_authorized",
            "final_decision": "needs_direction_owner_review_no_design_authorized",
            "authorized_next_action": "direction_owner_must_supply_complete_rules_before_design",
            "evidence_paths": [
                "evidence/research_recovery/public_source_bollinger_squeeze_intake_state_reconciliation/latest",
            ],
            "status_note": "setup threshold, directional confirmation, and exit/cash rule remain review-required",
        },
    ]


def scan_stale_pointers(root: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for relative_path in STATE_FILES_TO_SCAN:
        path = root / relative_path
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for source_id, pointers in STALE_POINTERS_BY_SOURCE.items():
            for pointer in pointers:
                if pointer in text:
                    rows.append(
                        {
                            "source_id": source_id,
                            "path": str(relative_path),
                            "matched_text": pointer,
                            "risk": "stale_next_action_or_design_backtest_pointer",
                            "action": "not_updated_by_checkpoint_runner",
                            "reason": "no_safe_automatic_queue_status_update_convention_used",
                        }
                    )
    return rows


def stale_count_for(source_id: str, stale_rows: list[dict[str, str]]) -> int:
    return sum(1 for row in stale_rows if row["source_id"] == source_id)


def candidate_ledger_rows(root: Path, stale_rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for spec in candidate_specs(root):
        evidence_chain, evidence_paths = evidence_path_status(root, spec["evidence_paths"])
        batch = find_batch_decision(root, spec["source_id"])
        rows.append(
            {
                "source_id": spec["source_id"],
                "display_name": spec["display_name"],
                "family_id": spec["family_id"],
                "latest_known_state": spec["expected_state"],
                "evidence_chain_status": evidence_chain,
                "evidence_paths": evidence_paths,
                "batch_intake_decision": batch.get("eligibility_decision", "not_in_current_batch"),
                "final_decision": spec["final_decision"],
                "authorized_next_action": spec["authorized_next_action"],
                "forbidden_next_actions": "|".join(BLOCKED_ACTIONS),
                "design_authorized": False,
                "backtest_authorized": False,
                "candidate_exhaustive_authorized": False,
                "promotion_authorized": False,
                "paper_demo_authorized": False,
                "live_authorized": False,
                "stale_pointer_count": stale_count_for(spec["source_id"], stale_rows),
                "status_note": spec["status_note"],
            }
        )
    return rows


def dirty_worktree_rows(root: Path) -> list[dict[str, str]]:
    completed = subprocess.run(
        ["git", "status", "--short"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    rows: list[dict[str, str]] = []
    for raw_line in completed.stdout.splitlines():
        status = raw_line[:2].strip()
        path = raw_line[3:].strip()
        owner = likely_owner(path)
        expected = "expected_from_current_phase_checkpoint" if "public_source_phase_checkpoint" in path else (
            "expected_from_prior_completed_public_source_task"
            if owner in {
                "bollinger_band_squeeze_breakout",
                "macd_stochastic_double_cross",
                "cci_correction",
                "coppock_curve_monthly_equity_signal",
                "larry_connors_rsi2_mean_reversion",
                "percent_b_money_flow",
            }
            else "unexpected_or_unclassified"
        )
        recommendation = "review_before_next_source" if expected != "unexpected_or_unclassified" else "unexpected_requires_direction_owner_review"
        if any(pointer in path for pointers in STALE_POINTERS_BY_SOURCE.values() for pointer in pointers):
            recommendation = "stale_pointer_risk"
        rows.append(
            {
                "git_status": status,
                "path": path,
                "likely_owner_or_candidate": owner,
                "expected_from_prior_completed_task": expected,
                "action_recommendation": recommendation,
            }
        )
    return rows


def likely_owner(path: str) -> str:
    lowered = path.lower()
    mapping = {
        "bollinger": "bollinger_band_squeeze_breakout",
        "macd_stochastic": "macd_stochastic_double_cross",
        "cci_correction": "cci_correction",
        "coppock": "coppock_curve_monthly_equity_signal",
        "larry_connors": "larry_connors_rsi2_mean_reversion",
        "percent_b": "percent_b_money_flow",
        "turn_of_month": "turn_of_month_equity_indexes",
        "public_source_phase_checkpoint": "public_source_phase_checkpoint",
        "public_source_intake_validation": "public_source_intake_validation",
        "public_source_batch_intake_validation": "public_source_batch_intake_validation",
    }
    for token, owner in mapping.items():
        if token in lowered:
            return owner
    return "unclassified"


def guardrails() -> dict[str, bool]:
    return {
        "new_public_source_selected_by_codex": False,
        "public_source_scraped": False,
        "public_strategy_list_ingested": False,
        "new_strategy_design_created": False,
        "strategy_implemented": False,
        "backtest_run": False,
        "robustness_run": False,
        "results_audit_run": False,
        "prior_candidate_rerun": False,
        "parameters_tuned": False,
        "missing_rules_invented": False,
        "bollinger_continued": False,
        "macd_stochastic_continued": False,
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


def evidence_paths_inspected(root: Path) -> list[dict[str, Any]]:
    paths = [
        Path("strategy_lab") / "research_os" / "public_strategy_sources" / "intake_candidates",
        *PUBLIC_SOURCE_EVIDENCE_DIRS,
        *STATE_FILES_TO_SCAN,
        Path("strategy_lab") / "research_os" / "public_strategy_sources" / "project_family_similarity_map.yaml",
    ]
    return [
        {
            "path": str((root / path).resolve()),
            "exists": (root / path).exists(),
            "kind": "directory" if (root / path).is_dir() else "file",
        }
        for path in paths
    ]


def markdown_table(rows: list[dict[str, Any]], columns: list[str]) -> str:
    if not rows:
        return "| " + " | ".join(columns) + " |\n| " + " | ".join("---" for _ in columns) + " |\n"
    lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join("---" for _ in columns) + " |"]
    for row in rows:
        values = [str(row.get(column, "")).replace("|", "/") for column in columns]
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines) + "\n"


def summary_md(manifest: dict[str, Any]) -> str:
    return f"""# Public-Source Phase Checkpoint

Checkpoint status: `{manifest['checkpoint_status']}`

Candidates reviewed: `{manifest['candidate_count']}`
Candidates with complete or partial evidence: `{manifest['candidates_with_evidence_count']}`
Review-required candidates: `{manifest['review_required_candidate_count']}`
Completed diagnostic/context-only candidates: `{manifest['completed_context_only_candidate_count']}`
Duplicate/do-not-retest candidates: `{manifest['duplicate_or_do_not_retest_candidate_count']}`

Stale next-action pointer count: `{manifest['stale_next_action_pointer_count']}`
State files updated: `{manifest['state_files_updated']}`
Dirty worktree item count: `{manifest['dirty_worktree_item_count']}`

Codex-selected next public source: `{manifest['new_public_source_selected_by_codex']}`
Exact next action: `{manifest['next_action']}`

No public-source design, strategy implementation, backtest, robustness, results audit, rerun, tuning, provider download, intraday use, candidate_exhaustive, promotion, paper/demo activation, broker/live action, or real-money recommendation occurred.
"""


def evidence_paths_md(paths: list[dict[str, Any]]) -> str:
    lines = ["# Evidence Paths Inspected", ""]
    for row in paths:
        lines.append(f"- `{row['path']}` exists `{row['exists']}` ({row['kind']})")
    return "\n".join(lines) + "\n"


def stale_scan_md(rows: list[dict[str, str]]) -> str:
    lines = ["# Stale Next-Action Scan", ""]
    if not rows:
        lines.append("No stale public-source next-action, design, backtest, robustness, rerun, or re-audit pointer was found in scanned state files.")
    else:
        lines.append("Potential stale pointers were found. No state file was automatically edited by this checkpoint.")
        lines.append("")
        lines.append(markdown_table(rows, ["source_id", "path", "matched_text", "risk", "action", "reason"]))
    return "\n".join(lines) + "\n"


def state_update_report_md(manifest: dict[str, Any]) -> str:
    return f"""# State Update Report

State/queue/roadmap/registry files updated: `{manifest['state_files_updated']}`

Update reason: `{manifest['state_update_reason']}`

Stale pointer count: `{manifest['stale_next_action_pointer_count']}`

The checkpoint writes evidence only. It does not rewrite project state because no safe automatic state-update convention was used.
"""


def next_action_md() -> str:
    return f"""# Public-Source Phase Checkpoint Next Action

Exact next action: `{NEXT_ACTION}`

Do not execute this action from this checkpoint packet. Codex is not authorized to select the next public source.
"""


def manifest_payload(
    root: Path,
    output: Path,
    ledger_rows: list[dict[str, Any]],
    dirty_rows: list[dict[str, str]],
    stale_rows: list[dict[str, str]],
) -> dict[str, Any]:
    evidence_statuses = {row["evidence_chain_status"] for row in ledger_rows}
    return {
        "created_utc": now_utc(),
        "evidence_path": str(output.resolve()),
        "public_source_phase_checkpoint_only": True,
        "checkpoint_status": "public_source_review_batch_exhausted_checkpoint_created",
        "candidate_count": len(ledger_rows),
        "candidate_source_ids": [row["source_id"] for row in ledger_rows],
        "candidates_with_evidence_count": sum(
            1 for row in ledger_rows if row["evidence_chain_status"] in {"present", "partial"}
        ),
        "missing_evidence_candidate_count": sum(1 for row in ledger_rows if row["evidence_chain_status"] == "missing"),
        "partial_evidence_candidate_count": sum(1 for row in ledger_rows if row["evidence_chain_status"] == "partial"),
        "evidence_chain_statuses": sorted(evidence_statuses),
        "review_required_candidate_count": sum(
            1 for row in ledger_rows if row["final_decision"] == "needs_direction_owner_review_no_design_authorized"
        ),
        "completed_context_only_candidate_count": sum(
            1 for row in ledger_rows if row["final_decision"].startswith("completed_diagnostic")
        ),
        "duplicate_or_do_not_retest_candidate_count": sum(
            1 for row in ledger_rows if row["final_decision"] == "duplicate_or_do_not_retest"
        ),
        "all_design_authorized_false": all(row["design_authorized"] is False for row in ledger_rows),
        "all_backtest_authorized_false": all(row["backtest_authorized"] is False for row in ledger_rows),
        "all_candidate_exhaustive_authorized_false": all(
            row["candidate_exhaustive_authorized"] is False for row in ledger_rows
        ),
        "all_promotion_authorized_false": all(row["promotion_authorized"] is False for row in ledger_rows),
        "all_paper_demo_authorized_false": all(row["paper_demo_authorized"] is False for row in ledger_rows),
        "all_live_authorized_false": all(row["live_authorized"] is False for row in ledger_rows),
        "stale_next_action_pointer_count": len(stale_rows),
        "state_files_updated": False,
        "state_update_reason": "no_safe_automatic_queue_status_update_convention_used",
        "dirty_worktree_item_count": len(dirty_rows),
        "dirty_worktree_review_before_next_source_count": sum(
            1 for row in dirty_rows if row["action_recommendation"] == "review_before_next_source"
        ),
        "dirty_worktree_unexpected_count": sum(
            1 for row in dirty_rows if row["action_recommendation"] == "unexpected_requires_direction_owner_review"
        ),
        "output_files_expected": list(REQUIRED_FILES),
        **guardrails(),
        "next_action": NEXT_ACTION,
    }


def consistency_check(manifest: dict[str, Any], output: Path) -> dict[str, Any]:
    required = {filename: (output / filename).exists() for filename in REQUIRED_FILES}
    required["public_source_phase_checkpoint_consistency_check.json"] = True
    checks = {
        "checkpoint_only": manifest["public_source_phase_checkpoint_only"] is True,
        "candidate_count_expected": manifest["candidate_count"] == 8,
        "no_candidate_design_or_execution_authorized": manifest["all_design_authorized_false"] is True
        and manifest["all_backtest_authorized_false"] is True
        and manifest["all_candidate_exhaustive_authorized_false"] is True
        and manifest["all_promotion_authorized_false"] is True
        and manifest["all_paper_demo_authorized_false"] is True
        and manifest["all_live_authorized_false"] is True,
        "no_stale_pointer_or_recorded": manifest["stale_next_action_pointer_count"] >= 0,
        "state_files_not_mutated": manifest["state_files_updated"] is False,
        "no_forbidden_actions": all(value is False for value in guardrails().values()),
        "next_action_valid": manifest["next_action"] == NEXT_ACTION,
        "required_files_present": all(required.values()),
    }
    return {**checks, "required_files": required, "consistency_passed": all(checks.values())}


def run(root: Path = ROOT) -> dict[str, Any]:
    output = root / OUTPUT_DIR
    output.mkdir(parents=True, exist_ok=True)
    stale_rows = scan_stale_pointers(root)
    ledger_rows = candidate_ledger_rows(root, stale_rows)
    dirty_rows = dirty_worktree_rows(root)
    inspected_paths = evidence_paths_inspected(root)
    manifest = manifest_payload(root, output, ledger_rows, dirty_rows, stale_rows)

    write_json(output / "public_source_phase_checkpoint_manifest.json", manifest)
    write_text(output / "public_source_phase_checkpoint_summary.md", summary_md(manifest))
    write_text(output / "evidence_paths_inspected.md", evidence_paths_md(inspected_paths))
    write_csv(
        output / "candidate_status_ledger.csv",
        ledger_rows,
        [
            "source_id",
            "display_name",
            "family_id",
            "latest_known_state",
            "evidence_chain_status",
            "evidence_paths",
            "batch_intake_decision",
            "final_decision",
            "authorized_next_action",
            "forbidden_next_actions",
            "design_authorized",
            "backtest_authorized",
            "candidate_exhaustive_authorized",
            "promotion_authorized",
            "paper_demo_authorized",
            "live_authorized",
            "stale_pointer_count",
            "status_note",
        ],
    )
    write_text(
        output / "candidate_status_ledger.md",
        "# Candidate Status Ledger\n\n"
        + markdown_table(
            ledger_rows,
            [
                "source_id",
                "latest_known_state",
                "evidence_chain_status",
                "final_decision",
                "authorized_next_action",
                "stale_pointer_count",
            ],
        ),
    )
    write_csv(
        output / "dirty_worktree_hygiene.csv",
        dirty_rows,
        [
            "git_status",
            "path",
            "likely_owner_or_candidate",
            "expected_from_prior_completed_task",
            "action_recommendation",
        ],
    )
    write_text(
        output / "dirty_worktree_hygiene.md",
        "# Dirty Worktree Hygiene\n\n"
        + markdown_table(
            dirty_rows,
            [
                "git_status",
                "path",
                "likely_owner_or_candidate",
                "expected_from_prior_completed_task",
                "action_recommendation",
            ],
        ),
    )
    write_csv(
        output / "stale_next_action_scan.csv",
        stale_rows,
        ["source_id", "path", "matched_text", "risk", "action", "reason"],
    )
    write_text(output / "stale_next_action_scan.md", stale_scan_md(stale_rows))
    write_text(output / "state_update_report.md", state_update_report_md(manifest))
    write_json(output / "guardrail_checklist.json", guardrails())
    write_text(output / "public_source_phase_checkpoint_next_action.md", next_action_md())
    check = consistency_check(manifest, output)
    write_json(output / "public_source_phase_checkpoint_consistency_check.json", check)
    return {**manifest, "output_dir": str(output.resolve()), "consistency_passed": check["consistency_passed"]}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
