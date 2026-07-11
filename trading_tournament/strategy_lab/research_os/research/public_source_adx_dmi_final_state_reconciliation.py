from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.objective_reset.objective_reset_review import write_json, write_text
from strategy_lab.research_os.research.profit_oriented_research_batch_v1 import write_csv


SOURCE_ID = "adx_dmi_trend_strength_crossover"
FAMILY_ID = "equity_index_adx_dmi_trend_strength"
LANE_ID = "public_source_adx_dmi_bounded_bt_lane_v1"
FORMULA_CONTRACT = "adx_dmi_wilder_contract_v1"
METHODOLOGY_PATCH_ID = "adx_dmi_true_crossover_event_patch_v1"

FINAL_STATUS = "completed_diagnostic_control_weak_low_exposure_context_only_no_continuation_authorized"
NEXT_ACTION = "direction_owner_select_next_public_source_candidate"
CORRECTED_AUDIT_DECISION = "public_source_adx_dmi_corrected_results_passed_but_control_weak"
PREVIOUS_AUDIT_DECISION = "public_source_adx_dmi_results_needs_patch"

INTAKE_DIR = Path("evidence") / "research_recovery" / "public_source_intake_validation" / "latest"
BATCH_INTAKE_DIR = Path("evidence") / "research_recovery" / "public_source_batch_intake_validation" / "latest"
DESIGN_DIR = (
    Path("evidence")
    / "research_recovery"
    / "public_source_adx_dmi_bounded_bt_design"
    / "latest"
)
RUN_DIR = Path("evidence") / "research_recovery" / "public_source_adx_dmi_bounded_bt_run" / "latest"
PATCH_DIR = (
    Path("evidence")
    / "research_recovery"
    / "public_source_adx_dmi_methodology_patch"
    / "latest"
)
AUDIT_DIR = (
    Path("evidence")
    / "research_recovery"
    / "public_source_adx_dmi_bounded_bt_results_audit"
    / "latest"
)
OUTPUT_DIR = (
    Path("evidence")
    / "research_recovery"
    / "public_source_adx_dmi_final_state_reconciliation"
    / "latest"
)

INTAKE_MANIFEST = INTAKE_DIR / "public_source_intake_validation_manifest.json"
BATCH_INTAKE_DECISIONS = BATCH_INTAKE_DIR / "eligibility_decisions.csv"
DESIGN_MANIFEST = DESIGN_DIR / "public_source_adx_dmi_bounded_bt_design_manifest.json"
RUN_MANIFEST = RUN_DIR / "public_source_adx_dmi_bounded_bt_run_manifest.json"
PATCH_MANIFEST = PATCH_DIR / "adx_dmi_methodology_patch_manifest.json"
AUDIT_MANIFEST = AUDIT_DIR / "public_source_adx_dmi_bounded_bt_results_audit_manifest.json"
FINAL_AUDIT_DECISION_FILE = AUDIT_DIR / "final_audit_decision.md"

STATUS_FILES_TO_SCAN = (
    Path("strategy_lab") / "RESEARCH_ROADMAP.md",
    Path("strategy_lab") / "strategy_registry.yaml",
    Path("strategy_lab") / "research_os" / "research" / "research_queue.yaml",
    Path("evidence") / "research_state" / "latest" / "research_state_manifest.json",
    Path("evidence") / "research_state" / "latest" / "current_research_state.md",
)

STALE_POINTERS = (
    "direction_owner_review_required_after_adx_dmi_corrected_control_weak_results_audit",
    "run_public_source_adx_dmi_robustness",
    "create_public_source_adx_dmi_robustness_report",
    "audit_public_source_adx_dmi_robustness_results",
    "rerun_public_source_adx_dmi_bounded_bt_lane",
    "audit_public_source_adx_dmi_bounded_bt_results",
)

REQUIRED_FILES = (
    "public_source_adx_dmi_final_state_reconciliation_manifest.json",
    "public_source_adx_dmi_final_state_reconciliation_summary.md",
    "evidence_paths_inspected.md",
    "evidence_chain_status.csv",
    "evidence_chain_status.md",
    "adx_dmi_final_current_status.md",
    "no_continuation_reasons.md",
    "not_authorized_actions.md",
    "queue_status_review.md",
    "guardrail_checklist.json",
    "status_file_scan.csv",
    "public_source_adx_dmi_final_state_reconciliation_next_action.md",
    "public_source_adx_dmi_final_state_reconciliation_consistency_check.json",
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


def batch_decision(rows: list[dict[str, str]]) -> str:
    for row in rows:
        if row.get("source_id") == SOURCE_ID or row.get("candidate_id") == SOURCE_ID:
            return row.get("eligibility_decision") or row.get("decision") or ""
    return "not_found_in_batch_decisions"


def guardrails() -> dict[str, bool]:
    return {
        "adx_dmi_robustness_run": False,
        "adx_dmi_rerun": False,
        "adx_dmi_results_reaudit": False,
        "adx_dmi_period_tuned": False,
        "adx_threshold_tuned": False,
        "signal_timing_tuned": False,
        "exit_logic_tuned": False,
        "alternate_adx_thresholds_added": False,
        "alternate_dmi_periods_added": False,
        "alternate_exits_added": False,
        "filters_added": False,
        "stop_loss_or_profit_target_added": False,
        "spy200d_source_filter_added": False,
        "short_or_inverse_exposure_added": False,
        "new_variants_created": False,
        "next_public_source_selected_by_codex": False,
        "public_source_scraped": False,
        "additional_public_sources_ingested": False,
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
        ("corrected_run_evidence", RUN_DIR),
        ("methodology_patch_evidence", PATCH_DIR),
        ("corrected_results_audit_evidence", AUDIT_DIR),
        ("intake_manifest", INTAKE_MANIFEST),
        ("batch_intake_decisions", BATCH_INTAKE_DECISIONS),
        ("design_manifest", DESIGN_MANIFEST),
        ("corrected_run_manifest", RUN_MANIFEST),
        ("methodology_patch_manifest", PATCH_MANIFEST),
        ("corrected_results_audit_manifest", AUDIT_MANIFEST),
        ("final_audit_decision_file", FINAL_AUDIT_DECISION_FILE),
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
    patch_manifest: dict[str, Any],
    audit_manifest: dict[str, Any],
) -> list[dict[str, Any]]:
    patch_consistency = audit_manifest.get("patch_evidence_consistency", {})
    event_semantics = audit_manifest.get("event_count_semantics", {})
    return [
        {
            "stage": "intake_validation",
            "status": intake_manifest.get("eligibility_decision", ""),
            "passed": intake_manifest.get("source_id") == SOURCE_ID
            and intake_manifest.get("eligibility_decision") == "eligible_for_bounded_bt_design",
            "evidence_path": str((ROOT / INTAKE_DIR).resolve()),
            "notes": "single public-source intake is eligible for bounded bt design",
        },
        {
            "stage": "batch_intake_validation",
            "status": batch_decision(batch_rows),
            "passed": batch_decision(batch_rows) == "eligible_for_bounded_bt_design",
            "evidence_path": str((ROOT / BATCH_INTAKE_DIR).resolve()),
            "notes": "batch intake row for ADX/DMI remained eligible",
        },
        {
            "stage": "bounded_design",
            "status": design_manifest.get("run_readiness_decision", ""),
            "passed": design_manifest.get("source_id") == SOURCE_ID
            and design_manifest.get("lane_id") == LANE_ID
            and design_manifest.get("formula_contract_version") == FORMULA_CONTRACT
            and design_manifest.get("formula_contract_complete") is True
            and design_manifest.get("run_readiness_decision")
            == "public_source_adx_dmi_bounded_bt_design_run_ready",
            "evidence_path": str((ROOT / DESIGN_DIR).resolve()),
            "notes": "design is run-ready with frozen Wilder ADX/DMI formula contract",
        },
        {
            "stage": "initial_results_audit_methodology_issue",
            "status": patch_manifest.get("previous_audit_decision", ""),
            "passed": patch_manifest.get("previous_audit_decision") == PREVIOUS_AUDIT_DECISION
            and patch_consistency.get("previous_run_superseded") is True,
            "evidence_path": str((ROOT / PATCH_DIR).resolve()),
            "notes": "methodology patch evidence records the pre-patch audit failure and superseded run",
        },
        {
            "stage": "true_crossover_methodology_patch",
            "status": patch_manifest.get("methodology_patch_id", ""),
            "passed": patch_manifest.get("methodology_patch_only") is True
            and patch_manifest.get("methodology_patch_id") == METHODOLOGY_PATCH_ID
            and patch_manifest.get("formula_contract_changed") is False
            and patch_manifest.get("thresholds_changed") is False
            and patch_manifest.get("new_variants_created") is False
            and patch_manifest.get("cross_fields_are_true_transition_events") is True,
            "evidence_path": str((ROOT / PATCH_DIR).resolve()),
            "notes": "patch corrected cross fields to true transition events without tuning or expansion",
        },
        {
            "stage": "corrected_bounded_run",
            "status": "corrected_run_completed" if run_manifest.get("methodology_patch_applied") else "missing_patch_run",
            "passed": run_manifest.get("public_source_adx_dmi_bounded_bt_lane_run") is True
            and run_manifest.get("methodology_patch_applied") is True
            and run_manifest.get("methodology_patch_id") == METHODOLOGY_PATCH_ID
            and run_manifest.get("variant_count_planned") == 5
            and run_manifest.get("variant_count_evaluated") == 5
            and run_manifest.get("exposure_invariant_passed") is True
            and run_manifest.get("invariant_failure_count") == 0,
            "evidence_path": str((ROOT / RUN_DIR).resolve()),
            "notes": "corrected run completed exact five approved rows with clean invariants",
        },
        {
            "stage": "corrected_event_count_semantics",
            "status": event_semantics.get("event_count_semantics_status", ""),
            "passed": event_semantics.get("event_count_semantics_audit_passed") is True
            and event_semantics.get("cross_fields_are_true_transition_events") is True
            and event_semantics.get("raw_bullish_directional_state_days") == 2760
            and event_semantics.get("raw_bearish_directional_state_days") == 2035
            and event_semantics.get("true_bullish_crossover_events") == 212
            and event_semantics.get("true_bearish_crossover_events") == 213
            and event_semantics.get("true_adx_confirmed_bullish_crossover_events") == 31
            and event_semantics.get("actual_completed_round_trips") == 31,
            "evidence_path": str((ROOT / AUDIT_DIR).resolve()),
            "notes": "state days and true crossover event counts are verified separately",
        },
        {
            "stage": "corrected_results_audit",
            "status": audit_manifest.get("audit_decision", ""),
            "passed": audit_manifest.get("audit_decision") == CORRECTED_AUDIT_DECISION
            and audit_manifest.get("patch_evidence_consistency_passed") is True
            and audit_manifest.get("formula_value_recomputation_passed") is True
            and audit_manifest.get("event_count_semantics_audit_passed") is True
            and audit_manifest.get("run_consistency_passed") is True
            and audit_manifest.get("criteria_recomputation_passed_against_run_implementation") is True
            and audit_manifest.get("exposure_invariant_audit_passed") is True
            and audit_manifest.get("control_weakness_detected") is True,
            "evidence_path": str((ROOT / AUDIT_DIR).resolve()),
            "notes": "mechanical audit passed but final audit decision is control-weak",
        },
        {
            "stage": "final_closeout",
            "status": FINAL_STATUS,
            "passed": True,
            "evidence_path": str((ROOT / OUTPUT_DIR).resolve()),
            "notes": "direction-owner decision closes ADX/DMI as diagnostic low-exposure context only",
        },
    ]


def no_continuation_reasons(audit_manifest: dict[str, Any]) -> dict[str, Any]:
    control = audit_manifest.get("control_comparison", {})
    return {
        "primary_total_return_far_below_spy_buy_hold": control.get(
            "primary_underperforms_spy_buy_hold_total_return"
        )
        is True,
        "primary_total_return_far_below_spy200d": control.get("primary_underperforms_spy200d_total_return") is True,
        "primary_average_exposure_is_sparse_low": float(control.get("primary_average_spy_exposure_share", 1.0))
        < 0.15,
        "audit_labels_result_control_weak": audit_manifest.get("control_weakness_detected") is True
        and audit_manifest.get("audit_decision") == CORRECTED_AUDIT_DECISION,
        "defensive_timing_not_strong_standalone_return_evidence": control.get(
            "primary_behaves_like_low_exposure_defensive_timing"
        )
        is True,
        "timing_sanity_context_only": audit_manifest.get("timing_sanity_context_only") is True,
        "similarity_to_equity_timing_controls_weakens_interpretation": audit_manifest.get(
            "similarity_contexts_preserved"
        )
        is True,
    }


def not_authorized_actions() -> dict[str, bool]:
    return {
        "robustness_run_authorized": False,
        "results_reaudit_authorized": False,
        "rerun_authorized": False,
        "parameter_tuning_authorized": False,
        "alternate_adx_thresholds_authorized": False,
        "alternate_dmi_periods_authorized": False,
        "alternate_exits_authorized": False,
        "filters_authorized": False,
        "stop_loss_authorized": False,
        "profit_target_authorized": False,
        "spy200d_source_filter_authorized": False,
        "short_inverse_authorized": False,
        "candidate_exhaustive_authorized": False,
        "promotion_authorized": False,
        "paper_demo_activation_authorized": False,
        "broker_live_action_authorized": False,
    }


def build_manifest(root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    intake_manifest = read_json(root / INTAKE_MANIFEST)
    batch_rows = read_csv_rows(root / BATCH_INTAKE_DECISIONS)
    design_manifest = read_json(root / DESIGN_MANIFEST)
    run_manifest = read_json(root / RUN_MANIFEST)
    patch_manifest = read_json(root / PATCH_MANIFEST)
    audit_manifest = read_json(root / AUDIT_MANIFEST)
    chain = evidence_chain_rows(
        intake_manifest,
        batch_rows,
        design_manifest,
        run_manifest,
        patch_manifest,
        audit_manifest,
    )
    reasons = no_continuation_reasons(audit_manifest)
    status_matches = scan_status_files(root)
    control = audit_manifest.get("control_comparison", {})
    event_semantics = audit_manifest.get("event_count_semantics", {})
    no_auth = not_authorized_actions()
    guardrail_payload = guardrails()
    evidence_chain_complete = all(row["passed"] is True for row in chain)
    final_locked = evidence_chain_complete and all(reasons.values())

    manifest = {
        "created_utc": now_utc(),
        "evidence_path": str((root / OUTPUT_DIR).resolve()),
        "public_source_adx_dmi_final_state_reconciliation_only": True,
        "source_id": SOURCE_ID,
        "family_id": FAMILY_ID,
        "lane_id": LANE_ID,
        "formula_contract_version": FORMULA_CONTRACT,
        "methodology_patch_id": METHODOLOGY_PATCH_ID,
        "final_status_locked": final_locked,
        "evidence_chain_complete": evidence_chain_complete,
        "final_adx_dmi_state": FINAL_STATUS if final_locked else "final_state_reconciliation_incomplete",
        "final_authorized_next_action": NEXT_ACTION,
        "intake_eligible": chain[0]["passed"],
        "batch_intake_decision": chain[1]["status"],
        "design_run_ready": chain[2]["passed"],
        "initial_results_audit_found_methodology_issue": chain[3]["passed"],
        "true_crossover_methodology_patch_completed": chain[4]["passed"],
        "corrected_run_completed": chain[5]["passed"],
        "corrected_event_counts_verified": chain[6]["passed"],
        "corrected_results_audit_mechanically_passed": chain[7]["passed"],
        "corrected_results_audit_decision": audit_manifest.get("audit_decision", ""),
        "patch_evidence_consistency_passed": audit_manifest.get("patch_evidence_consistency_passed") is True,
        "formula_recomputation_passed": audit_manifest.get("formula_value_recomputation_passed") is True,
        "corrected_event_semantics_passed": audit_manifest.get("event_count_semantics_audit_passed") is True,
        "saved_run_recomputation_passed": audit_manifest.get("run_consistency_passed") is True,
        "criteria_recomputation_passed": audit_manifest.get(
            "criteria_recomputation_passed_against_run_implementation"
        )
        is True,
        "exposure_invariants_passed": audit_manifest.get("exposure_invariant_audit_passed") is True,
        "timing_sanity_context_only": audit_manifest.get("timing_sanity_context_only") is True,
        "outputs_diagnostic_only": True,
        "outputs_non_promotable": audit_manifest.get("outputs_non_promotable") is True,
        "raw_bullish_directional_state_days": event_semantics.get("raw_bullish_directional_state_days"),
        "raw_bearish_directional_state_days": event_semantics.get("raw_bearish_directional_state_days"),
        "true_bullish_crossover_events": event_semantics.get("true_bullish_crossover_events"),
        "true_bearish_crossover_events": event_semantics.get("true_bearish_crossover_events"),
        "adx_confirmed_bullish_crossover_events": event_semantics.get(
            "true_adx_confirmed_bullish_crossover_events"
        ),
        "entries": event_semantics.get("actual_entry_events_from_exposure_changes"),
        "exits": event_semantics.get("actual_exit_events_from_exposure_changes"),
        "round_trips": event_semantics.get("actual_completed_round_trips"),
        "primary_total_return": control.get("primary_total_return"),
        "spy_buy_hold_total_return": control.get("spy_buy_hold_total_return"),
        "spy200d_total_return": control.get("spy200d_total_return"),
        "primary_max_drawdown": control.get("primary_max_drawdown"),
        "spy_buy_hold_max_drawdown": control.get("spy_buy_hold_max_drawdown"),
        "spy200d_max_drawdown": control.get("spy200d_max_drawdown"),
        "primary_return_drawdown_proxy": control.get("primary_return_drawdown_proxy"),
        "spy_buy_hold_return_drawdown_proxy": control.get("spy_buy_hold_return_drawdown_proxy"),
        "spy200d_return_drawdown_proxy": control.get("spy200d_return_drawdown_proxy"),
        "primary_average_spy_exposure_share": control.get("primary_average_spy_exposure_share"),
        "control_weakness_detected": control.get("control_weakness_detected") is True
        or audit_manifest.get("control_weakness_detected") is True,
        "primary_behaves_like_low_exposure_defensive_timing": control.get(
            "primary_behaves_like_low_exposure_defensive_timing"
        )
        is True,
        "primary_underperforms_spy_buy_hold_total_return": control.get(
            "primary_underperforms_spy_buy_hold_total_return"
        )
        is True,
        "primary_underperforms_spy200d_total_return": control.get("primary_underperforms_spy200d_total_return")
        is True,
        "not_promotable": True,
        "not_candidate_exhaustive_ready": True,
        "not_paper_demo_eligible": True,
        "not_broker_live_eligible": True,
        "not_real_money_relevant": True,
        "queue_status_file_updated": False,
        "roadmap_updated": False,
        "registry_updated": False,
        "state_files_changed": False,
        "queue_status_update_reason": "no_safe_automatic_queue_status_update_convention_used",
        "stale_status_pointer_count": len(status_matches),
        "stale_status_pointer_paths": [match["path"] for match in status_matches],
        **no_auth,
        **guardrail_payload,
        "next_action": NEXT_ACTION,
    }
    context = {
        "chain": chain,
        "reasons": reasons,
        "not_authorized": no_auth,
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
    return f"""# ADX/DMI Final Current Status

Final status: `{manifest['final_adx_dmi_state']}`

This source is completed diagnostic/context-only evidence. It is not promotable, not candidate_exhaustive-ready, not paper/demo eligible, not broker/live eligible, and not real-money relevant.

Corrected audit decision: `{manifest['corrected_results_audit_decision']}`

Primary total return: `{manifest['primary_total_return']}`

SPY buy-hold total return: `{manifest['spy_buy_hold_total_return']}`

SPY_200d total return: `{manifest['spy200d_total_return']}`

Primary average SPY exposure share: `{manifest['primary_average_spy_exposure_share']}`

Control weakness detected: `{manifest['control_weakness_detected']}`
"""


def no_continuation_md(reasons: dict[str, Any]) -> str:
    lines = ["# No Continuation Reasons", ""]
    for key, value in reasons.items():
        lines.append(f"- `{key}`: `{value}`")
    lines.append("")
    lines.append(
        "The ADX/DMI path is closed as diagnostic/control-weak/low-exposure/context-only. Passing the registered mechanical criteria does not authorize robustness, rerun, tuning, promotion, candidate_exhaustive, paper/demo, broker/live, or real-money action."
    )
    return "\n".join(lines) + "\n"


def not_authorized_md(actions: dict[str, bool]) -> str:
    lines = ["# Not Authorized Actions", ""]
    for key, value in actions.items():
        lines.append(f"- `{key}`: `{value}`")
    return "\n".join(lines) + "\n"


def queue_status_md(manifest: dict[str, Any], matches: list[dict[str, str]]) -> str:
    lines = ["# Queue Status Review", ""]
    lines.append(f"Queue/status file updated: `{manifest['queue_status_file_updated']}`")
    lines.append(f"Roadmap updated: `{manifest['roadmap_updated']}`")
    lines.append(f"Registry updated: `{manifest['registry_updated']}`")
    lines.append(f"State files changed: `{manifest['state_files_changed']}`")
    lines.append(f"Update reason: `{manifest['queue_status_update_reason']}`")
    lines.append(f"Stale ADX/DMI continuation pointer count: `{manifest['stale_status_pointer_count']}`")
    if matches:
        for match in matches:
            lines.append(f"- `{match['path']}` contains `{match['matched_text']}`; action `{match['action']}`")
    else:
        lines.append("- No stale ADX/DMI robustness or continuation pointer was found in scanned status files.")
    lines.append("")
    lines.append(f"Final authorized next action recorded by reconciliation: `{manifest['final_authorized_next_action']}`")
    return "\n".join(lines) + "\n"


def summary_md(manifest: dict[str, Any]) -> str:
    return f"""# ADX/DMI Final State Reconciliation

Source ID: `{manifest['source_id']}`

Family ID: `{manifest['family_id']}`

Lane ID: `{manifest['lane_id']}`

Formula contract: `{manifest['formula_contract_version']}`

Methodology patch ID: `{manifest['methodology_patch_id']}`

Evidence chain complete: `{manifest['evidence_chain_complete']}`

Final status: `{manifest['final_adx_dmi_state']}`

Corrected audit decision: `{manifest['corrected_results_audit_decision']}`

Corrected event counts verified: `{manifest['corrected_event_counts_verified']}`

Raw bullish / bearish state days: `{manifest['raw_bullish_directional_state_days']} / {manifest['raw_bearish_directional_state_days']}`

True bullish / bearish crossover events: `{manifest['true_bullish_crossover_events']} / {manifest['true_bearish_crossover_events']}`

ADX-confirmed bullish crossover events: `{manifest['adx_confirmed_bullish_crossover_events']}`

Entries / exits / round trips: `{manifest['entries']} / {manifest['exits']} / {manifest['round_trips']}`

Control weakness detected: `{manifest['control_weakness_detected']}`

Primary behaves like low-exposure defensive timing: `{manifest['primary_behaves_like_low_exposure_defensive_timing']}`

Queue/status file updated: `{manifest['queue_status_file_updated']}`

Exact next action: `{manifest['next_action']}`
"""


def next_action_md(manifest: dict[str, Any]) -> str:
    return f"""# ADX/DMI Final State Next Action

Exact next action:

`{manifest['next_action']}`

Do not execute the next action from this reconciliation packet.
"""


def consistency_check(manifest: dict[str, Any], output: Path) -> dict[str, Any]:
    required = {filename: (output / filename).exists() for filename in REQUIRED_FILES}
    required["public_source_adx_dmi_final_state_reconciliation_consistency_check.json"] = True
    checks: dict[str, Any] = {
        "reconciliation_only": manifest["public_source_adx_dmi_final_state_reconciliation_only"] is True,
        "correct_source_family_lane": manifest["source_id"] == SOURCE_ID
        and manifest["family_id"] == FAMILY_ID
        and manifest["lane_id"] == LANE_ID,
        "correct_formula_contract_and_patch": manifest["formula_contract_version"] == FORMULA_CONTRACT
        and manifest["methodology_patch_id"] == METHODOLOGY_PATCH_ID,
        "evidence_chain_complete": manifest["evidence_chain_complete"] is True,
        "final_status_locked": manifest["final_status_locked"] is True
        and manifest["final_adx_dmi_state"] == FINAL_STATUS,
        "corrected_audit_control_weak": manifest["corrected_results_audit_decision"] == CORRECTED_AUDIT_DECISION
        and manifest["control_weakness_detected"] is True
        and manifest["primary_underperforms_spy_buy_hold_total_return"] is True
        and manifest["primary_underperforms_spy200d_total_return"] is True
        and manifest["primary_behaves_like_low_exposure_defensive_timing"] is True,
        "not_actionable": manifest["not_promotable"] is True
        and manifest["not_candidate_exhaustive_ready"] is True
        and manifest["not_paper_demo_eligible"] is True
        and manifest["not_broker_live_eligible"] is True
        and manifest["not_real_money_relevant"] is True,
        "no_continuation_authorized": all(value is False for value in not_authorized_actions().values()),
        "no_forbidden_actions": all(value is False for value in guardrails().values()),
        "state_files_not_mutated": manifest["queue_status_file_updated"] is False
        and manifest["roadmap_updated"] is False
        and manifest["registry_updated"] is False
        and manifest["state_files_changed"] is False,
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

    write_json(output / "public_source_adx_dmi_final_state_reconciliation_manifest.json", manifest)
    write_text(output / "public_source_adx_dmi_final_state_reconciliation_summary.md", summary_md(manifest))
    write_text(output / "evidence_paths_inspected.md", evidence_paths_md(context["evidence_paths"]))
    write_csv(
        output / "evidence_chain_status.csv",
        context["chain"],
        ["stage", "status", "passed", "evidence_path", "notes"],
    )
    write_text(output / "evidence_chain_status.md", evidence_chain_md(context["chain"]))
    write_text(output / "adx_dmi_final_current_status.md", current_status_md(manifest))
    write_text(output / "no_continuation_reasons.md", no_continuation_md(context["reasons"]))
    write_text(output / "not_authorized_actions.md", not_authorized_md(context["not_authorized"]))
    write_text(output / "queue_status_review.md", queue_status_md(manifest, context["status_matches"]))
    write_json(output / "guardrail_checklist.json", context["guardrails"])
    write_csv(
        output / "status_file_scan.csv",
        context["status_matches"],
        ["path", "matched_text", "action", "reason"],
    )
    write_text(output / "public_source_adx_dmi_final_state_reconciliation_next_action.md", next_action_md(manifest))
    check = consistency_check(manifest, output)
    write_json(output / "public_source_adx_dmi_final_state_reconciliation_consistency_check.json", check)
    return {**manifest, "output_dir": str(output.resolve()), "consistency_passed": check["consistency_passed"]}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
