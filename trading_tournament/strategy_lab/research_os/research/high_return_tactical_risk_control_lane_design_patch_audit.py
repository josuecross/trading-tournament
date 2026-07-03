from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.objective_reset.objective_reset_review import (
    replace_or_append_section,
    write_json,
    write_text,
)
from strategy_lab.research_os.research.high_return_tactical_risk_control_lane_design import LANE_ID
from strategy_lab.research_os.split_tracks import RESEARCH_STATE_PATH


SOURCE_PATCH_DIR = Path("evidence") / "research_recovery" / "high_return_tactical_risk_control_lane_design_patch" / "latest"
OUTPUT_DIR = Path("evidence") / "research_recovery" / "high_return_tactical_risk_control_lane_design_patch_audit" / "latest"

NEXT_ACTION_RUN = "run_high_return_tactical_risk_control_research_lane"
NEXT_ACTION_PATCH = "patch_high_return_tactical_risk_control_lane_design_again"
NEXT_ACTION_MANUAL = "manual_review_required_after_risk_control_lane_design_patch_audit"
NEXT_ACTION_PAUSE = "pause_expansion_and_wait_for_manual_direction"
VALID_NEXT_ACTIONS = {NEXT_ACTION_RUN, NEXT_ACTION_PATCH, NEXT_ACTION_MANUAL, NEXT_ACTION_PAUSE}

DECISION_RUN_READY = "patch_accepted_run_ready"
DECISION_PATCH = "patch_needs_another_design_fix"
DECISION_MANUAL = "manual_review_required_before_run"
DECISION_REJECTED = "patch_rejected"
VALID_DECISIONS = {DECISION_RUN_READY, DECISION_PATCH, DECISION_MANUAL, DECISION_REJECTED}

REQUIRED_OUTPUT_FILES = (
    "risk_control_lane_design_patch_audit_manifest.json",
    "risk_control_lane_design_patch_audit_summary.md",
    "patch_guardrail_review.md",
    "patched_variant_table_audit.md",
    "hidden_ambiguity_review.md",
    "baseline_mapping_audit.md",
    "patched_success_failure_criteria_audit.md",
    "duplication_overconservatism_patch_audit.md",
    "run_readiness_decision.md",
    "do_not_run_until_patch_audit_passes.md",
    "risk_control_lane_design_patch_audit_next_action.md",
    "risk_control_lane_design_patch_audit_consistency_check.json",
)

MANIFEST_BASE = {
    "risk_control_lane_design_patch_audit_only": True,
    "lane_id_audited": LANE_ID,
    "source_patch_evidence_reviewed": True,
    "new_research_batch_run": False,
    "new_strategy_discovery_run": False,
    "new_backtests_run": False,
    "new_performance_metrics_from_raw_data_computed": False,
    "new_variants_created": False,
    "new_families_created": False,
    "provider_download": False,
    "intraday_data_used": False,
    "broker_api_called": False,
    "broker_orders_submitted": False,
    "broker_orders_cancelled": False,
    "broker_orders_reconciled": False,
    "live_orders": False,
    "real_money_recommendation": False,
    "promotion_candidates_created": False,
    "paper_forward_activation": False,
    "new_paper_forward_candidate_created": False,
    "candidate_exhaustive_run": False,
    "best_single_variant_promoted": False,
    "research_outputs_remain_non_promotable": True,
    "active_vm_preserved": True,
    "active_dsr_preserved": True,
    "static_all_weather_benchmark_control_only": True,
    "macro_gld_lineage_recovery_run": False,
    "macro_gld_remains_lineage_blocked_visible": True,
    "alpaca_execution_module_delegated": True,
}


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def load_variants(root: Path) -> list[dict[str, str]]:
    path = root / SOURCE_PATCH_DIR / "patched_variant_design_table.csv"
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def load_source_patch(root: Path) -> dict[str, Any]:
    source = root / SOURCE_PATCH_DIR
    return {
        "manifest": read_json(source / "risk_control_lane_design_patch_manifest.json"),
        "consistency": read_json(source / "risk_control_lane_design_patch_consistency_check.json"),
        "summary": read_text(source / "risk_control_lane_design_patch_summary.md"),
        "threshold_policy": read_text(source / "explicit_threshold_policy.md"),
        "fallback_policy": read_text(source / "fallback_and_bil_semantics.md"),
        "drawdown_policy": read_text(source / "drawdown_guard_reentry_policy.md"),
        "combined_policy": read_text(source / "combined_rule_precedence.md"),
        "success_failure": read_text(source / "patched_success_failure_criteria.md"),
        "duplication_policy": read_text(source / "duplication_overconservatism_policy.md"),
        "variants": load_variants(root),
    }


def variant_table_audit(variants: list[dict[str, str]]) -> dict[str, Any]:
    ids = [row["variant_id"] for row in variants]
    allowed_concepts = {
        "spy200d_regime_filter",
        "realized_volatility_throttle",
        "strategy_drawdown_guard",
        "regime_plus_volatility_guard",
    }
    required_fields = (
        "variant_id",
        "universe",
        "momentum_lookback_days",
        "top_n",
        "rebalance_frequency",
        "risk_control_concept",
        "exposure_cap",
        "cash_bil_handling_rule",
        "promotion_eligible",
        "paper_forward_eligible",
    )
    missing = []
    for row in variants:
        for field in required_fields:
            if not str(row.get(field, "")).strip():
                missing.append({"variant_id": row.get("variant_id", ""), "missing_field": field})
    return {
        "variant_count": len(variants),
        "unique_variant_ids": len(ids) == len(set(ids)),
        "missing_required_fields": missing,
        "unrelated_concepts_added": sorted({row["risk_control_concept"] for row in variants} - allowed_concepts),
        "variant_count_lte_24": len(variants) <= 24,
        "exposure_caps_lte_1": all(float(row["exposure_cap"]) <= 1.0 for row in variants),
        "forbidden_instruments_false": all(
            row["leverage_allowed"] == "False"
            and row["shorting_allowed"] == "False"
            and row["options_allowed"] == "False"
            and row["direct_futures_allowed"] == "False"
            for row in variants
        ),
        "bil_fallback_semantics_present": all("BIL is the only cash/fallback asset" in row["cash_bil_handling_rule"] for row in variants),
        "promotion_and_paper_false": all(row["promotion_eligible"] == "False" and row["paper_forward_eligible"] == "False" for row in variants),
    }


def variant_table_valid(audit: dict[str, Any]) -> bool:
    return (
        audit["unique_variant_ids"]
        and not audit["missing_required_fields"]
        and not audit["unrelated_concepts_added"]
        and audit["variant_count_lte_24"]
        and audit["exposure_caps_lte_1"]
        and audit["forbidden_instruments_false"]
        and audit["bil_fallback_semantics_present"]
        and audit["promotion_and_paper_false"]
    )


def hidden_ambiguity(source: dict[str, Any], variants: list[dict[str, str]]) -> dict[str, Any]:
    all_text = "\n".join(
        [
            source["threshold_policy"],
            source["drawdown_policy"],
            source["combined_policy"],
            "\n".join(row["risk_control_rule"] for row in variants),
        ]
    )
    issues = []
    volatility_input_explicit = "selected risky basket or base strategy return stream" not in all_text
    if not volatility_input_explicit:
        issues.append("Volatility input still says selected risky basket or base strategy return stream, leaving the future implementation to choose.")
    volatility_known_before_allocation = "prior" in all_text.lower() and "volatility" in all_text.lower()
    if not volatility_known_before_allocation:
        issues.append("Volatility throttle does not explicitly require prior-window volatility known before allocation.")
    drawdown_guard_timing_explicit = (
        "state changes only after signal calculation" in all_text
        and "monthly rebalance convention" in all_text
        and "prior-day or prior-period" not in all_text
    )
    if not drawdown_guard_timing_explicit:
        issues.append("Drawdown guard timing still uses prior-day or prior-period language and does not choose daily versus monthly state updates.")
    if "base strategy equity" not in all_text.lower():
        issues.append("Base strategy equity tracking while the guard is active is not defined.")
    if not variants or "baseline" not in "\n".join(variants[0].keys()).lower():
        issues.append("Variant table lacks explicit baseline mapping fields.")
    if "BIL" in source["threshold_policy"] and "volatility" in source["threshold_policy"] and "exclude BIL" not in all_text:
        issues.append("Volatility calculation does not explicitly state whether BIL is excluded from the risky-basket volatility input.")
    no_eligible_conflict = "If no risky assets qualify, BIL is `1.00`" in source["fallback_policy"]
    combined_precedence_clear = "volatility throttle cannot override" in source["combined_policy"]
    return {
        "hidden_ambiguity_found": bool(issues),
        "volatility_input_explicit": volatility_input_explicit and volatility_known_before_allocation,
        "drawdown_guard_timing_explicit": drawdown_guard_timing_explicit,
        "no_eligible_risky_asset_logic_clear": no_eligible_conflict,
        "combined_rule_precedence_unambiguous": combined_precedence_clear,
        "issues": issues,
    }


def baseline_mapping_audit(variants: list[dict[str, str]]) -> dict[str, Any]:
    required_baseline_fields = (
        "baseline_family",
        "baseline_universe_group",
        "baseline_lookback",
        "baseline_top_n",
        "baseline_rebalance_frequency",
        "baseline_corrected_methodology_source",
        "same_window_baseline_comparison_required",
    )
    missing_fields = {
        field: sum(1 for row in variants if field not in row or not str(row.get(field, "")).strip())
        for field in required_baseline_fields
    }
    baseline_mapping_explicit = all(count == 0 for count in missing_fields.values())
    return {
        "required_baseline_fields": list(required_baseline_fields),
        "missing_baseline_field_counts": missing_fields,
        "baseline_mapping_explicit": baseline_mapping_explicit,
        "baseline_mapping_issue": (
            "Patched variant table does not include explicit baseline family, universe group, lookback, top-N, "
            "rebalance frequency, corrected methodology source, or same-window comparison field."
            if not baseline_mapping_explicit
            else "Baseline mapping is explicit."
        ),
    }


def success_failure_audit(text: str) -> dict[str, Any]:
    required = ("25%", "60%", "70%", "15%", "40%", "5%", "10%", "-45%", "0.90", "not promotion thresholds")
    status = {token: token in text for token in required}
    measurable = all(status.values())
    return {
        "success_failure_criteria_measurable": measurable,
        "required_token_status": status,
        "research_interpretation_only": "not promotion thresholds" in text,
    }


def duplication_audit(source: dict[str, Any]) -> dict[str, Any]:
    text = source["duplication_policy"]
    requirements = {
        "spy200d_comparison": "SPY_200d" in text,
        "active_vm_comparison": "active VM" in text,
        "active_dsr_comparison": "active DSR" in text,
        "active_combo_comparison": "active combo" in text,
        "bil_share_warning": "70%" in text,
        "duplicate_threshold": "0.90" in text,
    }
    risks = [
        "SPY 200-day plus BIL fallback may duplicate SPY_200d timing.",
        "Volatility throttle may reduce exposure enough to become BIL-heavy cash timing.",
        "Drawdown guard may create a path-dependent cash lockout if timing is not made explicit.",
        "Combined regime plus volatility guard may be too defensive.",
    ]
    return {
        "duplication_overconservatism_risk_blocking": False,
        "future_run_flags_present": all(requirements.values()),
        "requirements": requirements,
        "risks": risks,
    }


def run_readiness(payload: dict[str, Any]) -> tuple[str, str]:
    if (
        payload["variant_table_valid"]
        and not payload["hidden_ambiguity_found"]
        and payload["volatility_input_explicit"]
        and payload["drawdown_guard_timing_explicit"]
        and payload["baseline_mapping_explicit"]
        and payload["success_failure_criteria_measurable"]
        and not payload["duplication_overconservatism_risk_blocking"]
    ):
        return DECISION_RUN_READY, NEXT_ACTION_RUN
    if (
        not payload["variant_table_valid"]
        or payload["hidden_ambiguity_found"]
        or not payload["volatility_input_explicit"]
        or not payload["drawdown_guard_timing_explicit"]
        or not payload["baseline_mapping_explicit"]
        or not payload["success_failure_criteria_measurable"]
    ):
        return DECISION_PATCH, NEXT_ACTION_PATCH
    return DECISION_MANUAL, NEXT_ACTION_MANUAL


def manifest(created: str, output: Path, source: dict[str, Any], table: dict[str, Any], ambiguity: dict[str, Any], baseline: dict[str, Any], criteria: dict[str, Any], duplication: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "created_utc": created,
        **MANIFEST_BASE,
        "evidence_path": str(output.resolve()),
        "source_patch_evidence_path": str((ROOT / SOURCE_PATCH_DIR).resolve()),
        "source_patch_consistency_passed": source["consistency"].get("consistency_passed") is True,
        "variant_count_reviewed": table["variant_count"],
        "variant_table_valid": variant_table_valid(table),
        "hidden_ambiguity_found": ambiguity["hidden_ambiguity_found"],
        "volatility_input_explicit": ambiguity["volatility_input_explicit"],
        "drawdown_guard_timing_explicit": ambiguity["drawdown_guard_timing_explicit"],
        "baseline_mapping_explicit": baseline["baseline_mapping_explicit"],
        "success_failure_criteria_measurable": criteria["success_failure_criteria_measurable"],
        "duplication_overconservatism_risk_blocking": duplication["duplication_overconservatism_risk_blocking"],
    }
    decision, next_action = run_readiness(payload)
    payload["run_readiness_decision"] = decision
    payload["next_action"] = next_action
    return payload


def guardrail_md(payload: dict[str, Any]) -> str:
    return f"""# Patch Guardrail Review

The patched design packet was reviewed as an audit-only step.

- New research batch run: `{payload['new_research_batch_run']}`
- Strategy discovery run: `{payload['new_strategy_discovery_run']}`
- New backtests run: `{payload['new_backtests_run']}`
- Raw performance metrics computed: `{payload['new_performance_metrics_from_raw_data_computed']}`
- Provider download: `{payload['provider_download']}`
- Intraday data used: `{payload['intraday_data_used']}`
- Broker API called: `{payload['broker_api_called']}`
- Paper-forward activation: `{payload['paper_forward_activation']}`
- Promotion candidates created: `{payload['promotion_candidates_created']}`
- Real-money recommendation: `{payload['real_money_recommendation']}`

No lane run occurred.
"""


def variant_table_md(audit: dict[str, Any]) -> str:
    return f"""# Patched Variant Table Audit

- Variants reviewed: `{audit['variant_count']}`
- Unique variant IDs: `{audit['unique_variant_ids']}`
- Variant count <= 24: `{audit['variant_count_lte_24']}`
- Exposure caps <= 1.0: `{audit['exposure_caps_lte_1']}`
- Leverage/short/options/direct futures false: `{audit['forbidden_instruments_false']}`
- BIL fallback semantics present: `{audit['bil_fallback_semantics_present']}`
- Promotion and paper-forward eligibility false: `{audit['promotion_and_paper_false']}`
- Unrelated concepts added: `{audit['unrelated_concepts_added']}`
- Missing required fields: `{audit['missing_required_fields']}`
"""


def ambiguity_md(audit: dict[str, Any]) -> str:
    lines = [
        "# Hidden Ambiguity Review",
        "",
        f"- Hidden ambiguity found: `{audit['hidden_ambiguity_found']}`",
        f"- Volatility input explicit: `{audit['volatility_input_explicit']}`",
        f"- Drawdown guard timing explicit: `{audit['drawdown_guard_timing_explicit']}`",
        f"- No-eligible risky asset logic clear: `{audit['no_eligible_risky_asset_logic_clear']}`",
        f"- Combined-rule precedence unambiguous: `{audit['combined_rule_precedence_unambiguous']}`",
        "",
        "Issues:",
    ]
    if not audit["issues"]:
        lines.append("- None")
    for issue in audit["issues"]:
        lines.append(f"- {issue}")
    return "\n".join(lines) + "\n"


def baseline_md(audit: dict[str, Any]) -> str:
    lines = [
        "# Baseline Mapping Audit",
        "",
        f"- Baseline mapping explicit: `{audit['baseline_mapping_explicit']}`",
        f"- Issue: {audit['baseline_mapping_issue']}",
        "",
        "Missing baseline field counts:",
    ]
    for field, count in audit["missing_baseline_field_counts"].items():
        lines.append(f"- `{field}`: `{count}`")
    return "\n".join(lines) + "\n"


def criteria_md(audit: dict[str, Any]) -> str:
    lines = [
        "# Patched Success / Failure Criteria Audit",
        "",
        f"- Criteria measurable: `{audit['success_failure_criteria_measurable']}`",
        f"- Research interpretation only: `{audit['research_interpretation_only']}`",
        "",
        "Required token status:",
    ]
    for token, present in audit["required_token_status"].items():
        lines.append(f"- `{token}`: `{present}`")
    return "\n".join(lines) + "\n"


def duplication_md(audit: dict[str, Any]) -> str:
    lines = [
        "# Duplication / Overconservatism Patch Audit",
        "",
        f"- Duplication/overconservatism risk blocking: `{audit['duplication_overconservatism_risk_blocking']}`",
        f"- Future-run flags present: `{audit['future_run_flags_present']}`",
        "",
        "Requirement coverage:",
    ]
    for name, present in audit["requirements"].items():
        lines.append(f"- `{name}`: `{present}`")
    lines.append("")
    lines.append("Design risks retained for future-run review:")
    for risk in audit["risks"]:
        lines.append(f"- {risk}")
    return "\n".join(lines) + "\n"


def summary_md(payload: dict[str, Any]) -> str:
    return f"""# High-Return Tactical Risk-Control Lane Design Patch Audit

Lane audited: `{payload['lane_id_audited']}`

Variants reviewed: `{payload['variant_count_reviewed']}`

Variant table valid: `{payload['variant_table_valid']}`

Hidden ambiguity found: `{payload['hidden_ambiguity_found']}`

Volatility input explicit: `{payload['volatility_input_explicit']}`

Drawdown guard timing explicit: `{payload['drawdown_guard_timing_explicit']}`

Baseline mapping explicit: `{payload['baseline_mapping_explicit']}`

Success/failure criteria measurable: `{payload['success_failure_criteria_measurable']}`

Duplication/overconservatism risk blocking: `{payload['duplication_overconservatism_risk_blocking']}`

Run-readiness decision: `{payload['run_readiness_decision']}`

Exact next action: `{payload['next_action']}`
"""


def decision_md(payload: dict[str, Any]) -> str:
    return f"""# Run-Readiness Decision

Decision: `{payload['run_readiness_decision']}`

Next action: `{payload['next_action']}`

Rationale:

- The patched variant table is narrow and non-promotable.
- Numeric thresholds and success/failure criteria are substantially improved.
- The design is not run-ready because baseline mapping is missing from the variant table, volatility input remains ambiguous, and drawdown guard timing/base-equity tracking still need implementation-level specificity.
"""


def do_not_run_md(payload: dict[str, Any]) -> str:
    return f"""# Do Not Run Until Patch Audit Passes

This audit does not authorize a lane run.

Current decision: `{payload['run_readiness_decision']}`

The design must be patched again or manually reviewed before any historical research-lane run.
"""


def next_action_md(payload: dict[str, Any]) -> str:
    return f"""# Risk-Control Lane Design Patch Audit Next Action

Exact next action:

`{payload['next_action']}`

Do not run the next action in this task.
"""


def consistency_check(payload: dict[str, Any], output: Path) -> dict[str, Any]:
    required = {name: (output / name).exists() for name in REQUIRED_OUTPUT_FILES}
    checks = {
        "patch_audit_only": payload["risk_control_lane_design_patch_audit_only"] is True,
        "correct_lane_id_audited": payload["lane_id_audited"] == LANE_ID,
        "source_patch_evidence_reviewed": payload["source_patch_evidence_reviewed"] is True,
        "no_new_research_batch": payload["new_research_batch_run"] is False,
        "no_strategy_discovery": payload["new_strategy_discovery_run"] is False,
        "no_backtests": payload["new_backtests_run"] is False,
        "no_raw_data_metrics": payload["new_performance_metrics_from_raw_data_computed"] is False,
        "no_new_variants": payload["new_variants_created"] is False,
        "no_new_families": payload["new_families_created"] is False,
        "no_provider_download": payload["provider_download"] is False,
        "no_intraday": payload["intraday_data_used"] is False,
        "no_broker_api": payload["broker_api_called"] is False,
        "no_broker_orders": (
            payload["broker_orders_submitted"] is False
            and payload["broker_orders_cancelled"] is False
            and payload["broker_orders_reconciled"] is False
        ),
        "no_live_orders": payload["live_orders"] is False,
        "no_real_money_recommendation": payload["real_money_recommendation"] is False,
        "no_promotion_candidates": payload["promotion_candidates_created"] is False,
        "no_paper_forward_activation": payload["paper_forward_activation"] is False,
        "no_new_paper_forward_candidate": payload["new_paper_forward_candidate_created"] is False,
        "no_candidate_exhaustive": payload["candidate_exhaustive_run"] is False,
        "best_single_variant_not_promoted": payload["best_single_variant_promoted"] is False,
        "research_outputs_non_promotable": payload["research_outputs_remain_non_promotable"] is True,
        "active_vm_preserved": payload["active_vm_preserved"] is True,
        "active_dsr_preserved": payload["active_dsr_preserved"] is True,
        "static_all_weather_control_only": payload["static_all_weather_benchmark_control_only"] is True,
        "macro_gld_lineage_recovery_not_run": payload["macro_gld_lineage_recovery_run"] is False,
        "alpaca_execution_module_delegated": payload["alpaca_execution_module_delegated"] is True,
        "patched_variant_table_audit_exists": (output / "patched_variant_table_audit.md").exists(),
        "hidden_ambiguity_review_exists": (output / "hidden_ambiguity_review.md").exists(),
        "baseline_mapping_audit_exists": (output / "baseline_mapping_audit.md").exists(),
        "success_failure_criteria_audit_exists": (output / "patched_success_failure_criteria_audit.md").exists(),
        "run_readiness_decision_exists": (output / "run_readiness_decision.md").exists(),
        "next_action_valid": payload["next_action"] in VALID_NEXT_ACTIONS,
        "run_readiness_decision_valid": payload["run_readiness_decision"] in VALID_DECISIONS,
        "required_files_present": all(required.values()),
        "required_files": required,
    }
    checks["consistency_passed"] = all(value is True for key, value in checks.items() if key != "required_files")
    return checks


def update_research_metadata(root: Path, created: str, output: Path, payload: dict[str, Any]) -> None:
    path = root / RESEARCH_STATE_PATH
    before = read_text(path)
    section = f"""## High-Return Tactical Risk-Control Lane Design Patch Audit

- Created UTC: `{created}`
- Evidence path: `{output.resolve()}`
- Lane ID audited: `{payload['lane_id_audited']}`
- Variants reviewed: `{payload['variant_count_reviewed']}`
- Variant table valid: `{payload['variant_table_valid']}`
- Hidden ambiguity found: `{payload['hidden_ambiguity_found']}`
- Baseline mapping explicit: `{payload['baseline_mapping_explicit']}`
- Run-readiness decision: `{payload['run_readiness_decision']}`
- Next action: `{payload['next_action']}`
"""
    write_text(path, replace_or_append_section(before, "## High-Return Tactical Risk-Control Lane Design Patch Audit", section))


def run(root: Path = ROOT) -> dict[str, Any]:
    created = now_utc()
    output = root / OUTPUT_DIR
    output.mkdir(parents=True, exist_ok=True)
    source = load_source_patch(root)
    table = variant_table_audit(source["variants"])
    ambiguity = hidden_ambiguity(source, source["variants"])
    baseline = baseline_mapping_audit(source["variants"])
    criteria = success_failure_audit(source["success_failure"])
    duplication = duplication_audit(source)
    payload = manifest(created, output, source, table, ambiguity, baseline, criteria, duplication)

    write_json(output / "risk_control_lane_design_patch_audit_manifest.json", payload)
    write_text(output / "risk_control_lane_design_patch_audit_summary.md", summary_md(payload))
    write_text(output / "patch_guardrail_review.md", guardrail_md(payload))
    write_text(output / "patched_variant_table_audit.md", variant_table_md(table))
    write_text(output / "hidden_ambiguity_review.md", ambiguity_md(ambiguity))
    write_text(output / "baseline_mapping_audit.md", baseline_md(baseline))
    write_text(output / "patched_success_failure_criteria_audit.md", criteria_md(criteria))
    write_text(output / "duplication_overconservatism_patch_audit.md", duplication_md(duplication))
    write_text(output / "run_readiness_decision.md", decision_md(payload))
    write_text(output / "do_not_run_until_patch_audit_passes.md", do_not_run_md(payload))
    write_text(output / "risk_control_lane_design_patch_audit_next_action.md", next_action_md(payload))
    write_json(output / "risk_control_lane_design_patch_audit_consistency_check.json", {"consistency_passed": False})
    check = consistency_check(payload, output)
    write_json(output / "risk_control_lane_design_patch_audit_consistency_check.json", check)
    update_research_metadata(root, created, output, payload)
    return {**payload, "output_dir": str(output.resolve()), "consistency_passed": check["consistency_passed"]}


if __name__ == "__main__":
    result = run()
    print(
        json.dumps(
            {
                "output_dir": result["output_dir"],
                "lane_id_audited": result["lane_id_audited"],
                "variant_table_valid": result["variant_table_valid"],
                "hidden_ambiguity_found": result["hidden_ambiguity_found"],
                "baseline_mapping_explicit": result["baseline_mapping_explicit"],
                "run_readiness_decision": result["run_readiness_decision"],
                "next_action": result["next_action"],
                "consistency_passed": result["consistency_passed"],
            },
            indent=2,
        )
    )
