from __future__ import annotations

import csv
import hashlib
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import REGISTRY_PATH, ROADMAP_PATH, ROOT
from strategy_lab.research_os.objective_reset.objective_reset_review import (
    COMPACT_STATE_PATH,
    load_yaml,
    replace_or_append_section,
    strategy_snapshot,
    write_json,
    write_text,
)
from strategy_lab.research_os.objective_reset.revised_objective_batch_config import (
    ALLOWED_RESULT_STATUSES,
    BATCH_ID,
    EXCLUDED_FAMILIES,
    FORBIDDEN_STATUSES,
    INCLUDED_FAMILIES,
    INITIAL_STATUS,
    MAX_FAMILIES,
    MAX_TOTAL_VARIANTS,
    OLD_DOLLAR_TARGET_IS_HARD_GATE,
    STRETCH_DIAGNOSTICS_ARE_PROMOTION_GATES,
)
from strategy_lab.research_os.objective_reset.revised_objective_sandbox_batch import (
    BATCH_OUTPUT_DIR,
    OUTPUT_DIR as IMPLEMENTATION_DIR,
    aggregate_score_summary,
    benchmark_revised_summary,
    evaluate_revised_variants,
    family_summaries_revised,
    load_revised_dry_run_plan,
    md_batch_family_summary,
    md_do_not_promote_revised,
    md_family_actionability,
    md_future_preregistration_candidates,
    preflight_universe_availability,
    read_csv_rows,
    reference_returns,
    validate_variant_plan,
    write_csv,
)
from strategy_lab.research_os.objective_reset.revised_objective_sandbox_scoring_fix_v3_audit import (
    OUTPUT_DIR as SCORING_FIX_V3_AUDIT_DIR,
)


OUTPUT_DIR = Path("evidence") / "objective_reset" / "revised_objective_sandbox_batch_v3_rerun" / "latest"

NEXT_ACTION_AUDIT = "audit_fixed_scoring_revised_objective_sandbox_rerun"
NEXT_ACTION_FAMILY = "pre_register_one_revised_objective_family"
NEXT_ACTION_MANUAL = "manual_review_required_after_fixed_scoring_rerun"
NEXT_ACTION_PREFLIGHT_MANUAL = "manual_review_required_after_fixed_scoring_rerun_preflight"
NEXT_ACTION_OBSERVE = "continue_paper_forward_observation_only"
NEXT_ACTION_PAUSE = "pause_expansion_and_wait_for_manual_direction"
VALID_NEXT_ACTIONS = {
    NEXT_ACTION_AUDIT,
    NEXT_ACTION_FAMILY,
    NEXT_ACTION_MANUAL,
    NEXT_ACTION_PREFLIGHT_MANUAL,
    NEXT_ACTION_OBSERVE,
    NEXT_ACTION_PAUSE,
}

MANIFEST_FLAGS = {
    "fixed_scoring_rerun": True,
    "batch_id": BATCH_ID,
    "scoring_version": "v3",
    "new_unregistered_variants_created": False,
    "new_family_added": False,
    "formal_discovery_run": False,
    "strategy_discovery_run": False,
    "candidate_exhaustive_run": False,
    "paper_forward_review": False,
    "paper_forward_activation": False,
    "indicator_library_dependency_added": False,
    "provider_download": False,
    "intraday_data_used": False,
    "broker_orders_submitted": False,
    "broker_orders_cancelled": False,
    "live_orders": False,
    "real_money_recommendation": False,
    "active_strategy_state_changed": False,
    "rejected_strategy_state_changed": False,
    "exact_rejected_variants_reopened": False,
    "intraday_research_remains_paused": True,
    "old_dollar_target_is_hard_gate": False,
    "stretch_diagnostics_are_promotion_gates": False,
    "sandbox_results_non_promotable": True,
    "sandbox_can_create_paper_candidates": False,
    "best_single_variant_promoted": False,
}

REQUIRED_FILES = (
    "fixed_scoring_rerun_manifest.json",
    "fixed_scoring_rerun_summary.md",
    "fixed_scoring_rerun_preflight_report.md",
    "batch_002_v3_variant_results.csv",
    "batch_002_v3_family_summary.csv",
    "batch_002_v3_family_summary.md",
    "standalone_growth_score_v3_summary.csv",
    "portfolio_contribution_score_v3_summary.csv",
    "stretch_diagnostic_score_v3_summary.csv",
    "risk_integrity_score_v3_summary.csv",
    "overfit_risk_score_v3_summary.csv",
    "practicality_score_v3_summary.csv",
    "benchmark_comparison_v3_summary.csv",
    "family_actionability_v3_review.md",
    "future_preregistration_candidates_v3.md",
    "do_not_promote_v3.md",
    "fixed_scoring_rerun_next_action.md",
    "fixed_scoring_rerun_consistency_check.json",
)

RESULT_FIELD_ORDER = (
    "variant_id",
    "batch_id",
    "family_id",
    "objective_lane",
    "variant_role",
    "universe_group",
    "symbols",
    "indicator_concepts",
    "parameter_profile",
    "parameter_set",
    "status",
    "promotable",
    "paper_candidate_allowed",
    "sandbox_results_can_promote",
    "paper_candidates_can_be_created",
    "standalone_growth_score",
    "portfolio_contribution_score",
    "stretch_diagnostic_score",
    "risk_integrity_score",
    "overfit_risk_score",
    "practicality_score",
    "standalone_growth_score_v3",
    "portfolio_contribution_score_v3",
    "stretch_diagnostic_score_v3",
    "risk_integrity_score_v3",
    "overfit_risk_score_v3",
    "practicality_score_v3",
    "cash_allocation_penalty_v3",
    "underinvestment_penalty_v3",
    "benchmark_lag_penalty_v3",
    "return_drag_penalty_v3",
    "duplicate_penalty_v3",
    "risk_gate_status_v3",
    "score_saturation_flag_v3",
    "score_floor_collapse_flag_v3",
    "score_interpretation_status_v3",
    "ending_equity",
    "total_return",
    "annualized_return",
    "volatility",
    "sharpe",
    "max_drawdown",
    "max_drawdown_pct",
    "risk_buffer_vs_minus_600",
    "stop_risk_breach_flag",
    "180d_median_final_equity",
    "180d_mean_final_equity",
    "180d_worst_final_equity",
    "180d_worst_drawdown",
    "target_300_before_stop_rate",
    "target_400_before_stop_rate",
    "stop_hit_rate",
    "delta_vs_active_combo_180d_median",
    "active_combo_180d_median_final_equity",
    "portfolio_return_risk_improvement",
    "active_combo_improvement",
    "active_vm_dsr_pair_improvement",
    "correlation_reduction",
    "drawdown_contribution",
    "volatility_contribution",
    "return_drag_penalty",
    "contribution_vs_static_all_weather_control",
    "duplicate_penalty",
    "portfolio_level_risk_adjusted_improvement",
    "corr_vs_active_combo",
    "corr_vs_active_vm",
    "corr_vs_active_dsr",
    "corr_vs_spy",
    "corr_vs_qqq",
    "corr_vs_static_all_weather",
    "trade_count",
    "avg_turnover",
    "avg_cash_allocation",
    "avg_symbols_held",
    "max_symbol_weight",
    "data_window_length",
    "start_date",
    "end_date",
    "positive_180d_progress",
    "acceptable_drawdown_risk_integrity",
    "useful_contribution_evidence",
    "high_overfit_risk",
    "stretch_diagnostic_hit",
    "data_blocked",
    "block_reason",
)

FAMILY_FIELD_ORDER = (
    "family_id",
    "family_status",
    "variants_evaluated",
    "data_blocked_variants",
    "median_standalone_growth_score",
    "median_portfolio_contribution_score",
    "median_risk_integrity_score",
    "median_overfit_risk_score",
    "median_practicality_score",
    "best_variant_by_standalone_growth_score",
    "best_standalone_growth_score",
    "best_variant_by_portfolio_contribution_score",
    "best_portfolio_contribution_score",
    "positive_180d_progress_variants",
    "acceptable_drawdown_risk_integrity_variants",
    "useful_contribution_evidence_variants",
    "high_overfit_risk_variants",
    "stretch_diagnostic_hits",
    "family_level_interpretation",
    "actionable_now",
    "future_preregistration_candidate",
)


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def hash_tree(root: Path) -> dict[str, str]:
    if not root.exists():
        return {}
    return {str(path.relative_to(root)): sha256_file(path) for path in sorted(root.glob("*")) if path.is_file()}


def fixed_scoring_preflight(root: Path, plan_rows: list[dict[str, str]], max_variants: int) -> dict[str, Any]:
    registry = load_yaml(root / REGISTRY_PATH)
    metadata = registry.get("registry", {})
    implementation_manifest = read_json(root / IMPLEMENTATION_DIR / "revised_objective_sandbox_implementation_manifest.json")
    v3_audit_manifest = read_json(root / SCORING_FIX_V3_AUDIT_DIR / "scoring_fix_v3_audit_manifest.json")
    v3_audit_check = read_json(root / SCORING_FIX_V3_AUDIT_DIR / "scoring_fix_v3_audit_consistency_check.json")
    universe_rows = preflight_universe_availability(root)
    universe_map = {str(row["universe_group"]): row for row in universe_rows}
    failures: list[str] = []
    warnings: list[str] = []

    expected_next = "rerun_revised_objective_sandbox_batch_with_fixed_scoring"
    if metadata.get("current_next_action") != expected_next or metadata.get("official_current_next_action") != expected_next:
        failures.append("registry current/official next action is not rerun_revised_objective_sandbox_batch_with_fixed_scoring")
    if v3_audit_manifest.get("next_action") != expected_next:
        failures.append("v3 audit manifest does not authorize fixed-scoring rerun")
    if v3_audit_manifest.get("v3_calibration_accepted") is not True:
        failures.append("v3 calibration is not accepted")
    if v3_audit_manifest.get("rerun_with_fixed_scoring_recommended") is not True:
        failures.append("v3 audit did not recommend fixed-scoring rerun")
    if v3_audit_check.get("consistency_passed") is not True:
        failures.append("v3 audit consistency check did not pass")
    if implementation_manifest.get("batch_id") != BATCH_ID:
        failures.append("implementation manifest batch id mismatch")
    if not plan_rows:
        failures.append("dry-run variant plan is missing")
    if len(plan_rows) != 80:
        failures.append(f"planned variant count expected 80, found {len(plan_rows)}")
    if len(plan_rows) > max_variants or len(plan_rows) > MAX_TOTAL_VARIANTS:
        failures.append("planned variant count exceeds authorized fixed-scoring rerun limit")

    family_ids = sorted({str(row.get("family_id", "")) for row in plan_rows})
    if tuple(family_ids) != tuple(sorted(INCLUDED_FAMILIES)):
        failures.append("included families do not match preregistration")
    if len(family_ids) != MAX_FAMILIES:
        failures.append(f"planned family count expected {MAX_FAMILIES}, found {len(family_ids)}")
    excluded_seen = sorted(set(family_ids) & set(EXCLUDED_FAMILIES))
    if excluded_seen:
        failures.append(f"excluded families present in dry-run plan: {excluded_seen}")

    forbidden_seen = sorted({row.get("status", "") for row in plan_rows if row.get("status", "") in FORBIDDEN_STATUSES})
    if forbidden_seen:
        failures.append(f"forbidden statuses present in dry-run plan: {forbidden_seen}")
    for row in plan_rows:
        variant_id = row.get("variant_id", "<unknown>")
        if row.get("batch_id") != BATCH_ID:
            failures.append(f"variant has wrong batch id: {variant_id}")
        if row.get("promotable") != "false":
            failures.append(f"variant is promotable: {variant_id}")
        if row.get("paper_candidate_allowed") != "false":
            failures.append(f"variant can create paper candidate: {variant_id}")
        if row.get("status") != INITIAL_STATUS:
            failures.append(f"variant status is not non_promotable_exploration: {variant_id}")
        if row.get("old_dollar_target_is_hard_gate") != "false":
            failures.append(f"old dollar target encoded as hard gate: {variant_id}")
        if row.get("stretch_diagnostics_are_promotion_gates") != "false":
            failures.append(f"stretch diagnostics encoded as promotion gate: {variant_id}")
        group_id = str(row.get("universe_group", ""))
        universe = universe_map.get(group_id)
        if not universe or not universe.get("eligible_for_future_sandbox_run"):
            failures.append(f"local approved/cache-present daily data insufficient for universe group: {group_id}")
        elif int(universe.get("row_count", 0)) < 180:
            warnings.append(f"limited daily history for universe group: {group_id}")

    try:
        refs = reference_returns(root)
        for ref_id in ("SPY", "QQQ", "BIL", "active_vm", "active_dsr", "active_combo", "static_all_weather"):
            if ref_id not in refs or refs[ref_id].empty:
                failures.append(f"reference return series unavailable: {ref_id}")
    except Exception as exc:
        failures.append(f"reference return preflight failed: {exc}")

    if metadata.get("intraday_research_remains_paused") is not True:
        failures.append("intraday is not marked paused in registry")
    strategy_ids = {str(row.get("id", "")) for row in registry.get("strategies", [])}
    for strategy_id in (
        "paper_forward_vm_quality_lowvol_proxy_v1",
        "paper_forward_dsr_sector_equal_weight_defensive_filter_v1",
    ):
        if strategy_id not in strategy_ids:
            failures.append(f"active/frozen observation missing from registry: {strategy_id}")
    if "static_all_weather_benchmark_v1" not in strategy_ids and metadata.get("static_all_weather_benchmark_control_status") != "benchmark_control_accepted":
        warnings.append("static_all_weather_benchmark_v1 not explicitly listed as benchmark/control in registry")

    exact_rejected_reopened = [
        str(row.get("id", ""))
        for row in registry.get("strategies", [])
        if str(row.get("id", "")).startswith("mfv_")
        and (row.get("paper_forward_active") is True or str(row.get("status", "")).startswith("active"))
    ]
    if exact_rejected_reopened:
        failures.append(f"exact rejected managed-futures variants appear reopened: {exact_rejected_reopened}")

    return {
        "preflight_passed": not failures,
        "failures": sorted(set(failures)),
        "warnings": sorted(set(warnings)),
        "variant_count_planned": len(plan_rows),
        "family_count_planned": len(family_ids),
        "included_families": family_ids,
        "excluded_families": list(EXCLUDED_FAMILIES),
        "max_variants_requested": max_variants,
        "old_dollar_target_is_hard_gate": OLD_DOLLAR_TARGET_IS_HARD_GATE,
        "stretch_diagnostics_are_promotion_gates": STRETCH_DIAGNOSTICS_ARE_PROMOTION_GATES,
        "provider_download_required": False,
        "intraday_research_remains_paused": metadata.get("intraday_research_remains_paused") is True,
        "v3_audit_packet_exists": bool(v3_audit_manifest),
        "v3_audit_accepted": v3_audit_check.get("consistency_passed") is True
        and v3_audit_manifest.get("v3_calibration_accepted") is True,
        "data_preflight_rows": universe_rows,
    }


def md_preflight(preflight: dict[str, Any]) -> str:
    failures = "\n".join(f"- {item}" for item in preflight["failures"]) or "- none"
    warnings = "\n".join(f"- {item}" for item in preflight["warnings"]) or "- none"
    return f"""# Fixed-Scoring Rerun Preflight Report

Preflight passed: `{preflight['preflight_passed']}`

Batch ID: `{BATCH_ID}`

Scoring version: `v3`

Variant count planned: `{preflight['variant_count_planned']}`

Family count planned: `{preflight['family_count_planned']}`

Included families: `{', '.join(preflight['included_families']) or 'none'}`

Excluded families: `{', '.join(preflight['excluded_families']) or 'none'}`

V3 audit packet exists: `{preflight['v3_audit_packet_exists']}`

V3 audit accepted: `{preflight['v3_audit_accepted']}`

Old $300-$400 target is hard gate: `{preflight['old_dollar_target_is_hard_gate']}`

Stretch diagnostics are promotion gates: `{preflight['stretch_diagnostics_are_promotion_gates']}`

Provider download required: `{preflight['provider_download_required']}`

Intraday remains paused: `{preflight['intraday_research_remains_paused']}`

Failures:

{failures}

Warnings:

{warnings}

Local approved/cache-present daily data was checked. No provider data was downloaded.
"""


def md_summary(manifest: dict[str, Any], family_rows: list[dict[str, Any]]) -> str:
    family_bits = "\n".join(
        f"- `{row['family_id']}`: `{row['family_status']}`, median standalone v3 `{row['median_standalone_growth_score']}`, median contribution v3 `{row['median_portfolio_contribution_score']}`, median risk v3 `{row['median_risk_integrity_score']}`"
        for row in family_rows
    )
    return f"""# Fixed-Scoring V3 Rerun Summary

Fixed-scoring rerun: `{manifest['fixed_scoring_rerun']}`

Batch ID: `{manifest['batch_id']}`

Scoring version: `{manifest['scoring_version']}`

Preflight passed: `{manifest['preflight_passed']}`

Variant count planned: `{manifest['variant_count_planned']}`

Variant count evaluated: `{manifest['variant_count_evaluated']}`

Families evaluated: `{manifest['family_count_evaluated']}`

Future preregistration candidate count: `{manifest['sandbox_future_preregistration_candidate_count']}`

Families actionable now: `{manifest['families_actionable_count']}`

Family-level v3 findings:

{family_bits or '- none'}

Next action: `{manifest['next_action']}`

All results remain sandbox-only and non-promotable. No formal discovery, candidate_exhaustive, paper-forward action, provider download, intraday data, broker/live path, or real-money recommendation occurred.
"""


def md_family_actionability_v3(family_rows: list[dict[str, Any]]) -> str:
    base = md_family_actionability(family_rows)
    return base.replace("# Family Actionability Review", "# Family Actionability V3 Review") + """

V3 scoring is applied to every row. No row or family can become promotable from this rerun.
"""


def md_next_action(next_action: str) -> str:
    return f"""# Fixed-Scoring Rerun Next Action

Exact next action: `{next_action}`

Do not run the next action in this fixed-scoring rerun task.
"""


def decide_next_action(family_rows: list[dict[str, Any]], preflight_passed: bool) -> str:
    if not preflight_passed:
        return NEXT_ACTION_PREFLIGHT_MANUAL
    if not family_rows:
        return NEXT_ACTION_MANUAL
    future_candidates = [row for row in family_rows if row.get("future_preregistration_candidate")]
    if len(future_candidates) == 1 and all(
        row.get("family_status") in {"sandbox_family_weak", "sandbox_data_blocked", "sandbox_future_preregistration_candidate"}
        for row in family_rows
    ):
        return NEXT_ACTION_FAMILY
    if all(row.get("family_status") in {"sandbox_family_weak", "sandbox_data_blocked"} for row in family_rows):
        return NEXT_ACTION_OBSERVE
    return NEXT_ACTION_AUDIT


def update_metadata(root: Path, output: Path, created_utc: str, manifest: dict[str, Any]) -> tuple[bool, bool, bool]:
    registry_path = root / REGISTRY_PATH
    registry = load_yaml(registry_path)
    metadata = registry.setdefault("registry", {})
    before_metadata = deepcopy(metadata)
    metadata.update(
        {
            "fixed_scoring_revised_objective_sandbox_rerun_path": str(output.resolve()),
            "fixed_scoring_revised_objective_sandbox_rerun_status": "completed_non_promotable_v3_rerun",
            "fixed_scoring_revised_objective_sandbox_rerun_created_utc": created_utc,
            "current_research_mode": "fixed_scoring_revised_objective_sandbox_rerun_completed",
            "current_next_action": manifest["next_action"],
            "official_current_next_action": manifest["next_action"],
            "next_action": manifest["next_action"],
            "fixed_scoring_revised_objective_sandbox_rerun": True,
            "fixed_scoring_revised_objective_sandbox_rerun_batch_id": manifest["batch_id"],
            "fixed_scoring_revised_objective_sandbox_rerun_scoring_version": manifest["scoring_version"],
            "fixed_scoring_revised_objective_sandbox_rerun_variant_count_planned": manifest["variant_count_planned"],
            "fixed_scoring_revised_objective_sandbox_rerun_variant_count_evaluated": manifest["variant_count_evaluated"],
            "fixed_scoring_revised_objective_sandbox_rerun_family_count_evaluated": manifest["family_count_evaluated"],
            "fixed_scoring_revised_objective_sandbox_rerun_future_preregistration_candidate_count": manifest[
                "sandbox_future_preregistration_candidate_count"
            ],
            "fixed_scoring_revised_objective_sandbox_rerun_results_non_promotable": True,
            "fixed_scoring_revised_objective_sandbox_rerun_can_create_paper_candidates": False,
            "fixed_scoring_revised_objective_sandbox_rerun_formal_discovery_run": False,
            "fixed_scoring_revised_objective_sandbox_rerun_strategy_discovery_run": False,
            "fixed_scoring_revised_objective_sandbox_rerun_provider_download": False,
            "fixed_scoring_revised_objective_sandbox_rerun_intraday_data_used": False,
            "fixed_scoring_revised_objective_sandbox_rerun_candidate_exhaustive_run": False,
            "fixed_scoring_revised_objective_sandbox_rerun_paper_forward_action": False,
            "fixed_scoring_revised_objective_sandbox_rerun_real_money_recommendation": False,
            "intraday_research_remains_paused": True,
        }
    )
    registry_path.write_text(yaml.safe_dump(registry, sort_keys=False, width=120, allow_unicode=False), encoding="utf-8")

    roadmap_path = root / ROADMAP_PATH
    before_roadmap = roadmap_path.read_text(encoding="utf-8") if roadmap_path.exists() else "# Research Roadmap\n"
    compact_section = f"""## Compact Current State

- Updated UTC: `{created_utc}`
- Current research mode: `fixed_scoring_revised_objective_sandbox_rerun_completed`
- Official current next action: `{manifest['next_action']}`
- Fixed-scoring v3 rerun evidence: `{output.resolve()}`
- Batch ID: `{manifest['batch_id']}`
- Scoring version: `{manifest['scoring_version']}`
- Variant count planned: `{manifest['variant_count_planned']}`
- Variant count evaluated: `{manifest['variant_count_evaluated']}`
- Families evaluated: `{manifest['family_count_evaluated']}`
- Future preregistration candidate count: `{manifest['sandbox_future_preregistration_candidate_count']}`
- Families actionable now: `{manifest['families_actionable_count']}`
- Sandbox results are non-promotable: `true`
- Sandbox cannot create paper candidates.
- Active VM and active DSR preserved.
- `static_all_weather_benchmark_v1` remains benchmark/control only.
- Exact rejected variants remain closed.
- Intraday remains paused: `true`
- This rerun did not run formal discovery, candidate_exhaustive, paper-forward action, provider download, intraday data, broker/live path, or real-money recommendation.
"""
    section = f"""## Fixed-Scoring Revised Objective Sandbox Rerun

- Created UTC: `{created_utc}`
- Evidence path: `{output.resolve()}`
- Batch ID: `{manifest['batch_id']}`
- Scoring version: `{manifest['scoring_version']}`
- Variant count planned: `{manifest['variant_count_planned']}`
- Variant count evaluated: `{manifest['variant_count_evaluated']}`
- Families evaluated: `{manifest['family_count_evaluated']}`
- Future preregistration candidate count: `{manifest['sandbox_future_preregistration_candidate_count']}`
- Families directly actionable now: `{manifest['families_actionable_count']}`
- Best single variant promoted: `false`
- Next action: `{manifest['next_action']}`
- Do not run the next action in this rerun task.
"""
    after_roadmap = replace_or_append_section(before_roadmap, "## Compact Current State", compact_section)
    after_roadmap = replace_or_append_section(after_roadmap, "## Fixed-Scoring Revised Objective Sandbox Rerun", section)
    write_text(roadmap_path, after_roadmap)

    compact_path = root / COMPACT_STATE_PATH
    before_compact = compact_path.read_text(encoding="utf-8") if compact_path.exists() else ""
    after_compact = f"""# Current Tournament State

Created UTC: `{created_utc}`

Current research mode: `fixed_scoring_revised_objective_sandbox_rerun_completed`

Current next action: `{manifest['next_action']}`

Fixed-scoring v3 rerun evidence: `{output.resolve()}`

## Fixed-Scoring Rerun

- Batch ID: `{manifest['batch_id']}`
- Scoring version: `{manifest['scoring_version']}`
- Variant count planned: `{manifest['variant_count_planned']}`
- Variant count evaluated: `{manifest['variant_count_evaluated']}`
- Families evaluated: `{manifest['family_count_evaluated']}`
- Future preregistration candidate count: `{manifest['sandbox_future_preregistration_candidate_count']}`
- Families actionable now: `{manifest['families_actionable_count']}`
- Sandbox results are non-promotable.
- Sandbox cannot create paper candidates.
- Single safest next action: `{manifest['next_action']}`

## Protected State

- `paper_forward_vm_quality_lowvol_proxy_v1` remains active/accepted/frozen.
- `paper_forward_dsr_sector_equal_weight_defensive_filter_v1` remains active/accepted/frozen.
- `static_all_weather_benchmark_v1` remains benchmark/control only.
- Exact rejected variants remain closed.
- Intraday research remains paused.

## Forbidden Actions

- No formal strategy discovery.
- No candidate_exhaustive.
- No paper-forward review or activation.
- No provider download.
- No intraday data use.
- No indicator library dependency.
- No broker/live-order path or order action.
- No real-money recommendation.
"""
    write_text(compact_path, after_compact)
    return before_metadata != metadata, before_roadmap != after_roadmap, before_compact != after_compact


def consistency_check(manifest: dict[str, Any], output: Path) -> dict[str, Any]:
    rows = read_csv_rows(output / "batch_002_v3_variant_results.csv")
    statuses = {row.get("status", "") for row in rows}
    check = {
        "fixed_scoring_rerun_mode": manifest["fixed_scoring_rerun"] is True,
        "batch_id_correct": manifest["batch_id"] == BATCH_ID,
        "scoring_version_v3": manifest["scoring_version"] == "v3",
        "no_unregistered_variants": manifest["new_unregistered_variants_created"] is False,
        "no_new_family": manifest["new_family_added"] is False,
        "no_formal_strategy_discovery": manifest["strategy_discovery_run"] is False and manifest["formal_discovery_run"] is False,
        "no_candidate_exhaustive": manifest["candidate_exhaustive_run"] is False,
        "no_paper_forward_action": manifest["paper_forward_review"] is False and manifest["paper_forward_activation"] is False,
        "no_provider_download": manifest["provider_download"] is False,
        "no_intraday_data_used": manifest["intraday_data_used"] is False,
        "no_indicator_library_dependency_added": manifest["indicator_library_dependency_added"] is False,
        "no_broker_live_action": manifest["broker_orders_submitted"] is False
        and manifest["broker_orders_cancelled"] is False
        and manifest["live_orders"] is False,
        "no_real_money_recommendation": manifest["real_money_recommendation"] is False,
        "active_strategy_state_preserved": manifest["active_strategy_state_changed"] is False,
        "rejected_strategy_state_preserved": manifest["rejected_strategy_state_changed"] is False,
        "exact_rejected_variants_not_reopened": manifest["exact_rejected_variants_reopened"] is False,
        "intraday_remains_paused": manifest["intraday_research_remains_paused"] is True,
        "old_dollar_target_is_not_hard_gate": manifest["old_dollar_target_is_hard_gate"] is False,
        "stretch_diagnostics_are_not_promotion_gates": manifest["stretch_diagnostics_are_promotion_gates"] is False,
        "variant_count_planned_bounded": manifest["variant_count_planned"] <= MAX_TOTAL_VARIANTS,
        "variant_count_evaluated_bounded": manifest["variant_count_evaluated"] <= MAX_TOTAL_VARIANTS,
        "every_result_allowed_status": statuses <= set(ALLOWED_RESULT_STATUSES),
        "forbidden_statuses_absent": not (statuses & set(FORBIDDEN_STATUSES)),
        "no_result_promotable": all(row.get("promotable") == "false" for row in rows),
        "no_result_paper_candidate_allowed": all(row.get("paper_candidate_allowed") == "false" for row in rows),
        "v3_standalone_score_exists": all("standalone_growth_score_v3" in row for row in rows),
        "v3_contribution_score_exists": all("portfolio_contribution_score_v3" in row for row in rows),
        "v3_risk_score_exists": all("risk_integrity_score_v3" in row for row in rows),
        "v3_risk_gate_exists": all("risk_gate_status_v3" in row for row in rows),
        "v3_saturation_floor_flags_exist": all(
            "score_saturation_flag_v3" in row and "score_floor_collapse_flag_v3" in row for row in rows
        ),
        "family_summary_exists": (output / "batch_002_v3_family_summary.csv").exists(),
        "future_preregistration_candidates_file_exists": (output / "future_preregistration_candidates_v3.md").exists(),
        "do_not_promote_file_exists": (output / "do_not_promote_v3.md").exists(),
        "next_action_valid": manifest["next_action"] in VALID_NEXT_ACTIONS,
        "manifest_flags_match_strict_scope": all(manifest.get(key) == value for key, value in MANIFEST_FLAGS.items()),
        "required_files_exist": all((output / name).exists() for name in REQUIRED_FILES),
    }
    check["consistency_passed"] = all(check.values())
    return check


def run_revised_objective_sandbox_batch_v3_rerun(
    root: Path = ROOT,
    *,
    batch_id: str = BATCH_ID,
    max_variants: int = MAX_TOTAL_VARIANTS,
    rerun_label: str = "fixed_scoring_v3",
    update_project_metadata: bool = True,
) -> dict[str, Any]:
    if batch_id != BATCH_ID:
        raise ValueError(f"unexpected revised-objective batch id: {batch_id}")
    if rerun_label != "fixed_scoring_v3":
        raise ValueError(f"unexpected fixed-scoring rerun label: {rerun_label}")
    root = root.resolve()
    created_utc = now_utc()
    output = root / OUTPUT_DIR
    output.mkdir(parents=True, exist_ok=True)

    original_batch_hashes_before = hash_tree(root / BATCH_OUTPUT_DIR)
    before_strategies = strategy_snapshot(root)
    plan_rows = load_revised_dry_run_plan(root)
    preflight = fixed_scoring_preflight(root, plan_rows, max_variants)
    variant_results: list[dict[str, Any]] = []
    benchmark_rows: list[dict[str, Any]] = []
    family_rows: list[dict[str, Any]] = []
    if preflight["preflight_passed"]:
        validate_variant_plan(plan_rows, batch_id=batch_id, max_variants=max_variants)
        variant_results, benchmark_rows = evaluate_revised_variants(root, plan_rows[:max_variants])
        family_rows = family_summaries_revised(variant_results)

    next_action = decide_next_action(family_rows, preflight["preflight_passed"])
    after_strategies = strategy_snapshot(root)
    future_count = sum(1 for row in family_rows if row.get("future_preregistration_candidate"))
    actionable_count = 0
    manifest = {
        "created_utc": created_utc,
        "output_dir": str(output.resolve()),
        **MANIFEST_FLAGS,
        "rerun_label": rerun_label,
        "variant_count_planned": preflight["variant_count_planned"],
        "variant_count_evaluated": len(variant_results),
        "family_count_evaluated": len({row.get("family_id") for row in variant_results}),
        "sandbox_future_preregistration_candidate_count": future_count,
        "families_actionable_count": actionable_count,
        "v3_scoring_applied": True,
        "preflight_passed": preflight["preflight_passed"],
        "preflight_failures": preflight["failures"],
        "preflight_warnings": preflight["warnings"],
        "included_families": list(INCLUDED_FAMILIES),
        "excluded_families": list(EXCLUDED_FAMILIES),
        "next_action": next_action,
    }
    if before_strategies != after_strategies:
        manifest["active_strategy_state_changed"] = True
        manifest["rejected_strategy_state_changed"] = True

    write_text(output / "fixed_scoring_rerun_preflight_report.md", md_preflight(preflight))
    write_csv(output / "batch_002_v3_variant_results.csv", variant_results, list(RESULT_FIELD_ORDER))
    write_csv(output / "batch_002_v3_family_summary.csv", family_rows, list(FAMILY_FIELD_ORDER))
    write_text(output / "batch_002_v3_family_summary.md", md_batch_family_summary(family_rows).replace("# Batch 002 Family Summary", "# Batch 002 V3 Family Summary"))

    score_summary_files = {
        "standalone_growth_score_v3": "standalone_growth_score_v3_summary.csv",
        "portfolio_contribution_score_v3": "portfolio_contribution_score_v3_summary.csv",
        "stretch_diagnostic_score_v3": "stretch_diagnostic_score_v3_summary.csv",
        "risk_integrity_score_v3": "risk_integrity_score_v3_summary.csv",
        "overfit_risk_score_v3": "overfit_risk_score_v3_summary.csv",
        "practicality_score_v3": "practicality_score_v3_summary.csv",
    }
    for score_name, file_name in score_summary_files.items():
        rows = aggregate_score_summary(variant_results, score_name)
        write_csv(
            output / file_name,
            rows,
            ["family_id", "variants", f"median_{score_name}", f"best_{score_name}", f"worst_{score_name}"],
        )
    write_csv(
        output / "benchmark_comparison_v3_summary.csv",
        benchmark_revised_summary(benchmark_rows),
        [
            "family_id",
            "benchmark_id",
            "variant_count",
            "median_delta_180d_median_final_equity",
            "best_delta_180d_median_final_equity",
            "median_correlation",
        ],
    )
    write_text(output / "family_actionability_v3_review.md", md_family_actionability_v3(family_rows))
    write_text(output / "future_preregistration_candidates_v3.md", md_future_preregistration_candidates(family_rows))
    write_text(output / "do_not_promote_v3.md", md_do_not_promote_revised())
    write_text(output / "fixed_scoring_rerun_next_action.md", md_next_action(next_action))

    original_batch_hashes_after = hash_tree(root / BATCH_OUTPUT_DIR)
    manifest["original_batch_outputs_changed"] = original_batch_hashes_before != original_batch_hashes_after
    manifest["registry_metadata_updated"] = False
    manifest["roadmap_updated"] = False
    manifest["compact_state_updated"] = False
    if update_project_metadata:
        registry_updated, roadmap_updated, compact_updated = update_metadata(root, output, created_utc, manifest)
        manifest["registry_metadata_updated"] = registry_updated
        manifest["roadmap_updated"] = roadmap_updated
        manifest["compact_state_updated"] = compact_updated

    write_text(output / "fixed_scoring_rerun_summary.md", md_summary(manifest, family_rows))
    write_json(output / "fixed_scoring_rerun_manifest.json", manifest)
    write_json(output / "fixed_scoring_rerun_consistency_check.json", {"consistency_passed": False})
    consistency = consistency_check(manifest, output)
    write_json(output / "fixed_scoring_rerun_consistency_check.json", consistency)

    return {
        "output_dir": str(output),
        "batch_id": batch_id,
        "scoring_version": "v3",
        "preflight_passed": preflight["preflight_passed"],
        "variant_count_planned": manifest["variant_count_planned"],
        "variant_count_evaluated": manifest["variant_count_evaluated"],
        "family_count_evaluated": manifest["family_count_evaluated"],
        "sandbox_future_preregistration_candidate_count": future_count,
        "families_actionable_count": actionable_count,
        "next_action": next_action,
        "consistency_passed": consistency["consistency_passed"],
    }
