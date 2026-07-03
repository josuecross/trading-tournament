from __future__ import annotations

import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.objective_reset.objective_reset_review import (
    replace_or_append_section,
    write_json,
    write_text,
)
from strategy_lab.research_os.research.volatility_throttle_focused_research_followup_design import (
    LANE_ID,
    SOURCE_CONCEPT,
    SOURCE_LANE_ID,
)
from strategy_lab.research_os.split_tracks import RESEARCH_STATE_PATH


SOURCE_DESIGN_DIR = (
    Path("evidence") / "research_recovery" / "volatility_throttle_focused_research_followup_design" / "latest"
)
OUTPUT_DIR = Path("evidence") / "research_recovery" / "volatility_throttle_focused_research_followup_design_audit" / "latest"

NEXT_ACTION_RUN = "run_volatility_throttle_focused_research_followup"
NEXT_ACTION_PATCH = "patch_volatility_throttle_focused_research_followup_design"
NEXT_ACTION_MANUAL = "manual_review_required_after_vol_throttle_followup_design_audit"
NEXT_ACTION_PAUSE = "pause_expansion_and_wait_for_manual_direction"
VALID_NEXT_ACTIONS = {NEXT_ACTION_RUN, NEXT_ACTION_PATCH, NEXT_ACTION_MANUAL, NEXT_ACTION_PAUSE}

DECISION_RUN_READY = "followup_design_run_ready"
DECISION_PATCH = "followup_design_needs_patch"
DECISION_MANUAL = "manual_review_required_before_followup_run"
DECISION_REJECTED = "followup_design_rejected"

VAGUE_CRITERIA_TERMS = (
    "close to",
    "within reason",
    "materially",
    "not excessive",
    "meaningful",
    "reasonable",
    "enough",
)

REQUIRED_OUTPUT_FILES = (
    "vol_throttle_followup_design_audit_manifest.json",
    "vol_throttle_followup_design_audit_summary.md",
    "design_guardrail_review.md",
    "variant_role_audit.md",
    "threshold_set_audit.md",
    "volatility_rule_audit.md",
    "baseline_comparator_audit.md",
    "success_failure_criteria_audit.md",
    "run_readiness_decision.md",
    "do_not_run_until_followup_design_audit_passes.md",
    "vol_throttle_followup_design_audit_next_action.md",
    "vol_throttle_followup_design_audit_consistency_check.json",
)

MANIFEST_BASE = {
    "vol_throttle_followup_design_audit_only": True,
    "lane_id_audited": LANE_ID,
    "source_design_evidence_reviewed": True,
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


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def to_float(value: Any, default: float = float("nan")) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def load_source(root: Path) -> dict[str, Any]:
    source = root / SOURCE_DESIGN_DIR
    return {
        "manifest": read_json(source / "vol_throttle_followup_design_manifest.json"),
        "consistency": read_json(source / "vol_throttle_followup_consistency_check.json"),
        "summary": read_text(source / "vol_throttle_followup_design_summary.md"),
        "source_review": read_text(source / "source_evidence_review.md"),
        "hypothesis": read_text(source / "volatility_throttle_hypothesis.md"),
        "variants": read_csv_rows(source / "followup_variant_design_table.csv"),
        "frozen_rules": read_text(source / "frozen_rule_summaries.md"),
        "threshold_policy": read_text(source / "threshold_set_policy.md"),
        "baseline_policy": read_text(source / "baseline_and_comparator_policy.md"),
        "criteria": read_text(source / "success_failure_criteria.md"),
        "do_not_promote": read_text(source / "do_not_promote_from_followup_design.md"),
        "design_code": read_text(root / "strategy_lab" / "research_os" / "research" / "volatility_throttle_focused_research_followup_design.py"),
        "design_tests": read_text(root / "tests" / "test_volatility_throttle_focused_research_followup_design.py"),
    }


def guardrail_audit(source: dict[str, Any]) -> dict[str, Any]:
    manifest = source["manifest"]
    checks = {
        "design_only_mode": manifest.get("volatility_throttle_followup_design_only") is True,
        "no_followup_run": manifest.get("new_research_batch_run") is False,
        "no_backtest": manifest.get("new_backtests_run") is False,
        "no_discovery": manifest.get("new_strategy_discovery_run") is False,
        "no_raw_performance_metrics": manifest.get("new_performance_metrics_from_raw_data_computed") is False,
        "no_provider_download": manifest.get("provider_download") is False,
        "no_intraday": manifest.get("intraday_data_used") is False,
        "no_broker_api": manifest.get("broker_api_called") is False,
        "no_broker_orders": (
            manifest.get("broker_orders_submitted") is False
            and manifest.get("broker_orders_cancelled") is False
            and manifest.get("broker_orders_reconciled") is False
        ),
        "no_live_or_real_money": manifest.get("live_orders") is False and manifest.get("real_money_recommendation") is False,
        "no_paper_forward": manifest.get("paper_forward_activation") is False
        and manifest.get("new_paper_forward_candidate_created") is False,
        "no_promotion": manifest.get("promotion_candidates_created") is False and manifest.get("best_single_variant_promoted") is False,
        "no_candidate_exhaustive": manifest.get("candidate_exhaustive_run") is False,
        "active_vm_preserved": manifest.get("active_vm_preserved") is True,
        "active_dsr_preserved": manifest.get("active_dsr_preserved") is True,
        "static_all_weather_control_only": manifest.get("static_all_weather_benchmark_control_only") is True,
        "macro_gld_not_run": manifest.get("macro_gld_lineage_recovery_run") is False,
        "alpaca_delegated": manifest.get("alpaca_execution_module_delegated") is True,
    }
    return {"passed": all(checks.values()), "checks": checks}


def variant_role_audit(rows: list[dict[str, str]]) -> dict[str, Any]:
    role_counts: dict[str, int] = {}
    for row in rows:
        role_counts[row.get("variant_role", "")] = role_counts.get(row.get("variant_role", ""), 0) + 1
    confirmation = [row for row in rows if row.get("variant_role") == "confirmation_reference"]
    robustness = [row for row in rows if row.get("variant_role") in {"minimal_robustness_less_defensive", "minimal_robustness_more_defensive"}]
    checks = {
        "planned_rows_18": len(rows) == 18,
        "confirmation_reference_rows_6": len(confirmation) == 6,
        "robustness_rows_12": len(robustness) == 12,
        "confirmation_rows_have_source_metrics": all(
            row.get("source_evidence_path")
            and row.get("source_cagr")
            and row.get("source_max_drawdown")
            and row.get("source_cagr_retention_vs_baseline")
            for row in confirmation
        ),
        "confirmation_rows_marked_as_references": all(row.get("variant_role") == "confirmation_reference" for row in confirmation),
        "robustness_thresholds_and_baselines_explicit": all(
            row.get("threshold_set_id") and row.get("baseline_variant_id") and row.get("source_evidence_path")
            for row in robustness
        ),
        "roles_do_not_include_drawdown_guard": not any("drawdown" in row.get("variant_role", "").lower() for row in rows),
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "role_counts": role_counts,
        "confirmation_reference_rows_count": len(confirmation),
        "new_robustness_rows_count": len(robustness),
    }


def threshold_set_audit(rows: list[dict[str, str]]) -> dict[str, Any]:
    threshold_sets = {row.get("threshold_set_id", "") for row in rows}
    expected = {
        "original_25_35_100_50_25",
        "less_defensive_30_40_100_60_30",
        "more_defensive_20_30_100_40_20",
    }
    numeric = all(
        not math.isnan(to_float(row.get("normal_vol_threshold")))
        and not math.isnan(to_float(row.get("high_vol_threshold")))
        and not math.isnan(to_float(row.get("normal_multiplier")))
        and not math.isnan(to_float(row.get("high_vol_multiplier")))
        and not math.isnan(to_float(row.get("extreme_vol_multiplier")))
        for row in rows
    )
    checks = {
        "threshold_set_count_exactly_3": len(threshold_sets) == 3,
        "expected_threshold_sets_present": threshold_sets == expected,
        "original_set_reference": all(
            row.get("variant_role") == "confirmation_reference"
            for row in rows
            if row.get("threshold_set_id") == "original_25_35_100_50_25"
        ),
        "less_defensive_set_explicit": any(row.get("threshold_set_id") == "less_defensive_30_40_100_60_30" for row in rows),
        "more_defensive_set_explicit": any(row.get("threshold_set_id") == "more_defensive_20_30_100_40_20" for row in rows),
        "thresholds_and_multipliers_numeric": numeric,
        "no_extra_hidden_parameter_grid": len(rows) == 18,
    }
    return {"passed": all(checks.values()), "checks": checks, "threshold_set_count": len(threshold_sets)}


def volatility_rule_audit(rows: list[dict[str, str]]) -> dict[str, Any]:
    checks = {
        "all_use_uncontrolled_baseline_returns": all(
            "uncontrolled baseline tactical returns" in row.get("volatility_input_rule", "") for row in rows
        ),
        "all_use_t_minus_1": all("t-1" in row.get("volatility_input_rule", "") for row in rows),
        "all_use_60_day_window": all(str(row.get("volatility_window")) == "60" for row in rows),
        "all_annualize_sqrt_252": all("sqrt(252)" in row.get("volatility_input_rule", "") for row in rows),
        "all_exclude_bil_fallback": all("exclude BIL/fallback" in row.get("volatility_input_rule", "") for row in rows),
        "insufficient_history_explicit": all(row.get("insufficient_history_rule") for row in rows),
        "bil_replacement_remainder_only": all("replacement/remainder" in row.get("bil_fallback_rule", "") for row in rows),
        "max_exposure_lte_1": all(to_float(row.get("exposure_cap")) <= 1.0 for row in rows),
    }
    return {"passed": all(checks.values()), "checks": checks}


def baseline_comparator_audit(rows: list[dict[str, str]], baseline_policy: str) -> dict[str, Any]:
    checks = {
        "every_row_has_baseline_variant_id": all(row.get("baseline_variant_id") for row in rows),
        "every_row_has_source_evidence_path": all(row.get("source_evidence_path") for row in rows),
        "same_source_mapping_fields_present": all(
            row.get("universe_group")
            and row.get("universe")
            and row.get("lookback")
            and row.get("top_n")
            and row.get("rebalance_frequency") == "monthly"
            for row in rows
        ),
        "original_volatility_throttle_reference_clear": "Original volatility-throttle source rows" in baseline_policy
        or "original volatility throttle" in baseline_policy.lower(),
        "regime_plus_volatility_comparator_only": "Regime plus volatility as comparator only" in baseline_policy,
        "spy200d_control_only": "SPY 200d regime filter as comparator/control only" in baseline_policy,
        "drawdown_guard_excluded": "Strategy drawdown guard" in baseline_policy and "Excluded" in baseline_policy,
        "macro_gld_excluded": "Macro/GLD lineage recovery" in baseline_policy,
        "managed_futures_excluded": "Managed futures" in baseline_policy,
    }
    return {"passed": all(checks.values()), "checks": checks}


def success_failure_criteria_audit(criteria_text: str) -> dict[str, Any]:
    lower = criteria_text.lower()
    found = [term for term in VAGUE_CRITERIA_TERMS if term in lower]
    numeric_checks = {
        "cagr_retention_threshold_present": "70%" in criteria_text,
        "drawdown_reduction_threshold_present": "25%" in criteria_text,
        "bil_cash_threshold_present": "35%" in criteria_text,
        "duplicate_correlation_threshold_present": "0.90" in criteria_text,
        "exposure_invariant_present": "Exposure invariant" in criteria_text,
    }
    measurable = all(numeric_checks.values()) and not found
    return {
        "passed": measurable,
        "success_failure_criteria_measurable": measurable,
        "vague_criteria_found": bool(found),
        "vague_terms_found": found,
        "numeric_checks": numeric_checks,
        "required_patch": "replace subjective retention clause with numeric CAGR retention >= 70% of baseline and optional >= 85% of source original-volatility-throttle row",
    }


def run_readiness(
    guardrails: dict[str, Any],
    roles: dict[str, Any],
    thresholds: dict[str, Any],
    volatility: dict[str, Any],
    baseline: dict[str, Any],
    criteria: dict[str, Any],
) -> tuple[str, str]:
    if not criteria["success_failure_criteria_measurable"] or criteria["vague_criteria_found"]:
        return DECISION_PATCH, NEXT_ACTION_PATCH
    if not (guardrails["passed"] and roles["passed"] and thresholds["passed"] and volatility["passed"] and baseline["passed"]):
        return DECISION_PATCH, NEXT_ACTION_PATCH
    return DECISION_RUN_READY, NEXT_ACTION_RUN


def build_manifest(
    created: str,
    output: Path,
    source: dict[str, Any],
    guardrails: dict[str, Any],
    roles: dict[str, Any],
    thresholds: dict[str, Any],
    volatility: dict[str, Any],
    baseline: dict[str, Any],
    criteria: dict[str, Any],
) -> dict[str, Any]:
    decision, next_action = run_readiness(guardrails, roles, thresholds, volatility, baseline, criteria)
    return {
        "created_utc": created,
        "evidence_path": str(output.resolve()),
        **MANIFEST_BASE,
        "source_design_evidence_path": str((ROOT / SOURCE_DESIGN_DIR).resolve()),
        "planned_variant_count_reviewed": len(source["variants"]),
        "confirmation_reference_rows_count": roles["confirmation_reference_rows_count"],
        "new_robustness_rows_count": roles["new_robustness_rows_count"],
        "threshold_set_count": thresholds["threshold_set_count"],
        "variant_roles_unambiguous": roles["passed"],
        "thresholds_explicit": thresholds["passed"],
        "volatility_rules_explicit": volatility["passed"],
        "baseline_comparator_policy_explicit": baseline["passed"],
        "success_failure_criteria_measurable": criteria["success_failure_criteria_measurable"],
        "vague_criteria_found": criteria["vague_criteria_found"],
        "vague_terms_found": criteria["vague_terms_found"],
        "run_readiness_decision": decision,
        "next_action": next_action,
    }


def dict_md(title: str, audit: dict[str, Any]) -> str:
    lines = [f"# {title}", "", f"- Passed: `{audit['passed']}`", ""]
    if "role_counts" in audit:
        lines.append(f"- Role counts: `{audit['role_counts']}`")
    if "threshold_set_count" in audit:
        lines.append(f"- Threshold set count: `{audit['threshold_set_count']}`")
    if "vague_criteria_found" in audit:
        lines.append(f"- Vague criteria found: `{audit['vague_criteria_found']}`")
        lines.append(f"- Vague terms found: `{audit['vague_terms_found']}`")
        lines.append(f"- Required patch: `{audit['required_patch']}`")
    lines.append("")
    lines.append("Checks:")
    for name, value in audit.get("checks", audit.get("numeric_checks", {})).items():
        lines.append(f"- `{name}`: `{value}`")
    return "\n".join(lines) + "\n"


def summary_md(payload: dict[str, Any]) -> str:
    return f"""# Volatility Throttle Focused Follow-Up Design Audit

Lane audited: `{payload['lane_id_audited']}`

Planned variant count reviewed: `{payload['planned_variant_count_reviewed']}`

Confirmation reference rows: `{payload['confirmation_reference_rows_count']}`

New robustness rows: `{payload['new_robustness_rows_count']}`

Threshold set count: `{payload['threshold_set_count']}`

Variant roles unambiguous: `{payload['variant_roles_unambiguous']}`

Thresholds explicit: `{payload['thresholds_explicit']}`

Volatility rules explicit: `{payload['volatility_rules_explicit']}`

Baseline/comparator policy explicit: `{payload['baseline_comparator_policy_explicit']}`

Success/failure criteria measurable: `{payload['success_failure_criteria_measurable']}`

Vague criteria found: `{payload['vague_criteria_found']}`

Run-readiness decision: `{payload['run_readiness_decision']}`

Exact next action: `{payload['next_action']}`
"""


def decision_md(payload: dict[str, Any]) -> str:
    if payload["run_readiness_decision"] == DECISION_PATCH:
        rationale = (
            "The design is otherwise bounded, but the success/failure criteria contain subjective language. "
            "The retention clause must be converted into a numeric rule before any follow-up run."
        )
    else:
        rationale = "All audit checks passed and criteria are numeric."
    return f"""# Run-Readiness Decision

Decision: `{payload['run_readiness_decision']}`

Next action: `{payload['next_action']}`

Rationale:

{rationale}
"""


def do_not_run_md(payload: dict[str, Any]) -> str:
    return f"""# Do Not Run Until Follow-Up Design Audit Passes

Current run-readiness decision: `{payload['run_readiness_decision']}`

Vague criteria found: `{payload['vague_criteria_found']}`

The follow-up lane must not be run until the design is patched and/or a later audit marks it run-ready.
"""


def next_action_md(next_action: str) -> str:
    return f"""# Volatility Throttle Follow-Up Design Audit Next Action

Exact next action:

`{next_action}`

Do not run the next action in this task.
"""


def update_research_metadata(root: Path, created: str, output: Path, payload: dict[str, Any]) -> None:
    path = root / RESEARCH_STATE_PATH
    before = read_text(path)
    section = f"""## Latest Volatility Throttle Focused Follow-Up Design Audit

- Created UTC: `{created}`
- Evidence path: `{output.resolve()}`
- Lane ID audited: `{payload['lane_id_audited']}`
- Planned variants reviewed: `{payload['planned_variant_count_reviewed']}`
- Vague criteria found: `{payload['vague_criteria_found']}`
- Run-readiness decision: `{payload['run_readiness_decision']}`
- New backtests run: `{payload['new_backtests_run']}`
- Provider download: `{payload['provider_download']}`
- Promotion candidates created: `{payload['promotion_candidates_created']}`
- Paper-forward activation: `{payload['paper_forward_activation']}`
- Next action: `{payload['next_action']}`
"""
    write_text(path, replace_or_append_section(before, "## Latest Volatility Throttle Focused Follow-Up Design Audit", section))


def consistency_check(payload: dict[str, Any], output: Path) -> dict[str, Any]:
    required = {name: (output / name).exists() for name in REQUIRED_OUTPUT_FILES}
    required["vol_throttle_followup_design_audit_consistency_check.json"] = True
    checks = {
        "audit_only": payload["vol_throttle_followup_design_audit_only"] is True,
        "correct_lane_id": payload["lane_id_audited"] == LANE_ID,
        "source_design_reviewed": payload["source_design_evidence_reviewed"] is True,
        "no_research_batch": payload["new_research_batch_run"] is False,
        "no_discovery": payload["new_strategy_discovery_run"] is False,
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
        "no_live_or_real_money": payload["live_orders"] is False and payload["real_money_recommendation"] is False,
        "no_promotion": payload["promotion_candidates_created"] is False and payload["best_single_variant_promoted"] is False,
        "no_paper_forward": payload["paper_forward_activation"] is False
        and payload["new_paper_forward_candidate_created"] is False,
        "no_candidate_exhaustive": payload["candidate_exhaustive_run"] is False,
        "research_outputs_non_promotable": payload["research_outputs_remain_non_promotable"] is True,
        "active_vm_preserved": payload["active_vm_preserved"] is True,
        "active_dsr_preserved": payload["active_dsr_preserved"] is True,
        "static_all_weather_control_only": payload["static_all_weather_benchmark_control_only"] is True,
        "macro_gld_not_run": payload["macro_gld_lineage_recovery_run"] is False,
        "alpaca_delegated": payload["alpaca_execution_module_delegated"] is True,
        "variant_role_audit_exists": (output / "variant_role_audit.md").exists(),
        "threshold_set_audit_exists": (output / "threshold_set_audit.md").exists(),
        "volatility_rule_audit_exists": (output / "volatility_rule_audit.md").exists(),
        "baseline_comparator_audit_exists": (output / "baseline_comparator_audit.md").exists(),
        "success_failure_criteria_audit_exists": (output / "success_failure_criteria_audit.md").exists(),
        "run_readiness_decision_exists": (output / "run_readiness_decision.md").exists(),
        "next_action_valid": payload["next_action"] in VALID_NEXT_ACTIONS,
        "vague_criteria_blocks_run": (not payload["vague_criteria_found"])
        or payload["next_action"] != NEXT_ACTION_RUN,
        "required_files_present": all(required.values()),
        "required_files": required,
    }
    checks["consistency_passed"] = all(value is True for key, value in checks.items() if key != "required_files")
    return checks


def write_outputs(
    root: Path,
    created: str,
    source: dict[str, Any],
    guardrails: dict[str, Any],
    roles: dict[str, Any],
    thresholds: dict[str, Any],
    volatility: dict[str, Any],
    baseline: dict[str, Any],
    criteria: dict[str, Any],
) -> dict[str, Any]:
    output = root / OUTPUT_DIR
    output.mkdir(parents=True, exist_ok=True)
    payload = build_manifest(created, output, source, guardrails, roles, thresholds, volatility, baseline, criteria)
    write_json(output / "vol_throttle_followup_design_audit_manifest.json", payload)
    write_text(output / "vol_throttle_followup_design_audit_summary.md", summary_md(payload))
    write_text(output / "design_guardrail_review.md", dict_md("Design Guardrail Review", guardrails))
    write_text(output / "variant_role_audit.md", dict_md("Variant Role Audit", roles))
    write_text(output / "threshold_set_audit.md", dict_md("Threshold Set Audit", thresholds))
    write_text(output / "volatility_rule_audit.md", dict_md("Volatility Rule Audit", volatility))
    write_text(output / "baseline_comparator_audit.md", dict_md("Baseline Comparator Audit", baseline))
    write_text(output / "success_failure_criteria_audit.md", dict_md("Success / Failure Criteria Audit", criteria))
    write_text(output / "run_readiness_decision.md", decision_md(payload))
    write_text(output / "do_not_run_until_followup_design_audit_passes.md", do_not_run_md(payload))
    write_text(output / "vol_throttle_followup_design_audit_next_action.md", next_action_md(payload["next_action"]))
    consistency = consistency_check(payload, output)
    write_json(output / "vol_throttle_followup_design_audit_consistency_check.json", consistency)
    update_research_metadata(root, created, output, payload)
    return {**payload, "output_dir": str(output.resolve()), "consistency_passed": consistency["consistency_passed"]}


def run(root: Path = ROOT) -> dict[str, Any]:
    created = now_utc()
    source = load_source(root)
    guardrails = guardrail_audit(source)
    roles = variant_role_audit(source["variants"])
    thresholds = threshold_set_audit(source["variants"])
    volatility = volatility_rule_audit(source["variants"])
    baseline = baseline_comparator_audit(source["variants"], source["baseline_policy"])
    criteria = success_failure_criteria_audit(source["criteria"])
    return write_outputs(root, created, source, guardrails, roles, thresholds, volatility, baseline, criteria)


if __name__ == "__main__":
    result = run()
    print(
        json.dumps(
            {
                "output_dir": result["output_dir"],
                "lane_id_audited": result["lane_id_audited"],
                "planned_variant_count_reviewed": result["planned_variant_count_reviewed"],
                "vague_criteria_found": result["vague_criteria_found"],
                "run_readiness_decision": result["run_readiness_decision"],
                "next_action": result["next_action"],
                "consistency_passed": result["consistency_passed"],
            },
            indent=2,
        )
    )
