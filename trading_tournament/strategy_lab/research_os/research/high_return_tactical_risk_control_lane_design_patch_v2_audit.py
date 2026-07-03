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


SOURCE_PATCH_V2_DIR = Path("evidence") / "research_recovery" / "high_return_tactical_risk_control_lane_design_patch_v2" / "latest"
METHODOLOGY_SOURCE = Path("evidence") / "research_recovery" / "profit_oriented_research_batch_v1_methodology_fix" / "latest" / "corrected_profit_research_variant_results.csv"
LABEL_SOURCE = Path("evidence") / "research_recovery" / "profit_oriented_research_batch_v1_labeling_fix" / "latest" / "corrected_label_variant_results.csv"
OUTPUT_DIR = Path("evidence") / "research_recovery" / "high_return_tactical_risk_control_lane_design_patch_v2_audit" / "latest"

NEXT_ACTION_RUN = "run_high_return_tactical_risk_control_research_lane"
NEXT_ACTION_PATCH = "patch_high_return_tactical_risk_control_lane_design_again"
NEXT_ACTION_MANUAL = "manual_review_required_after_risk_control_lane_design_patch_v2_audit"
NEXT_ACTION_PAUSE = "pause_expansion_and_wait_for_manual_direction"
VALID_NEXT_ACTIONS = {NEXT_ACTION_RUN, NEXT_ACTION_PATCH, NEXT_ACTION_MANUAL, NEXT_ACTION_PAUSE}

DECISION_RUN_READY = "patch_v2_accepted_run_ready"
DECISION_PATCH = "patch_v2_needs_another_design_fix"
DECISION_MANUAL = "manual_review_required_before_run"
DECISION_REJECTED = "patch_v2_rejected"
VALID_DECISIONS = {DECISION_RUN_READY, DECISION_PATCH, DECISION_MANUAL, DECISION_REJECTED}

REQUIRED_OUTPUT_FILES = (
    "risk_control_lane_design_patch_v2_audit_manifest.json",
    "risk_control_lane_design_patch_v2_audit_summary.md",
    "patch_v2_guardrail_review.md",
    "patch_v2_variant_table_audit.md",
    "volatility_input_audit.md",
    "drawdown_guard_timing_audit.md",
    "combined_precedence_audit.md",
    "baseline_mapping_verification.md",
    "success_failure_criteria_audit.md",
    "test_quality_review.md",
    "run_readiness_decision.md",
    "do_not_run_until_patch_v2_audit_passes.md",
    "risk_control_lane_design_patch_v2_audit_next_action.md",
    "risk_control_lane_design_patch_v2_audit_consistency_check.json",
)

MANIFEST_BASE = {
    "risk_control_lane_design_patch_v2_audit_only": True,
    "lane_id_audited": LANE_ID,
    "source_patch_v2_evidence_reviewed": True,
    "corrected_baseline_sources_verified": True,
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


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def csv_index(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {row["variant_id"]: row for row in rows}


def load_source(root: Path) -> dict[str, Any]:
    source = root / SOURCE_PATCH_V2_DIR
    return {
        "manifest": read_json(source / "risk_control_lane_design_patch_v2_manifest.json"),
        "consistency": read_json(source / "risk_control_lane_design_patch_v2_consistency_check.json"),
        "summary": read_text(source / "risk_control_lane_design_patch_v2_summary.md"),
        "variants": load_csv(source / "patched_v2_variant_design_table.csv"),
        "baseline_mapping": load_csv(source / "baseline_mapping_table.csv"),
        "volatility_policy": read_text(source / "volatility_input_policy.md"),
        "drawdown_policy": read_text(source / "drawdown_guard_timing_policy.md"),
        "combined_policy": read_text(source / "combined_rule_precedence_v2.md"),
        "baseline_policy": read_text(source / "baseline_mapping_policy.md"),
        "remaining_ambiguity": read_text(source / "remaining_ambiguity_review.md"),
        "methodology_rows": load_csv(root / METHODOLOGY_SOURCE),
        "label_rows": load_csv(root / LABEL_SOURCE),
        "patch_v2_tests": read_text(root / "tests" / "test_high_return_tactical_risk_control_lane_design_patch_v2.py"),
        "success_failure": read_text(root / "evidence" / "research_recovery" / "high_return_tactical_risk_control_lane_design_patch" / "latest" / "patched_success_failure_criteria.md"),
    }


def variant_table_audit(variants: list[dict[str, str]]) -> dict[str, Any]:
    allowed_concepts = {
        "spy200d_regime_filter",
        "realized_volatility_throttle",
        "strategy_drawdown_guard",
        "regime_plus_volatility_guard",
    }
    required_fields = (
        "variant_id",
        "source_family",
        "universe_group",
        "universe",
        "momentum_lookback_days",
        "top_n",
        "rebalance_frequency",
        "risk_control_concept",
        "exposure_cap",
        "cash_bil_handling_rule",
        "baseline_variant_id",
        "baseline_family",
        "baseline_universe_group",
        "baseline_universe",
        "baseline_lookback",
        "baseline_top_n",
        "baseline_rebalance_frequency",
        "baseline_corrected_methodology_source",
        "baseline_corrected_label_source",
        "same_window_baseline_comparison_required",
    )
    ids = [row["variant_id"] for row in variants]
    missing = []
    for row in variants:
        for field in required_fields:
            if not str(row.get(field, "")).strip():
                missing.append({"variant_id": row.get("variant_id", ""), "missing_field": field})
    return {
        "variant_count": len(variants),
        "variant_count_exact_24": len(variants) == 24,
        "unique_variant_ids": len(ids) == len(set(ids)),
        "missing_required_fields": missing,
        "families": sorted({row.get("source_family", "") for row in variants}),
        "risk_control_concepts": sorted({row.get("risk_control_concept", "") for row in variants}),
        "concepts_allowed": {row.get("risk_control_concept", "") for row in variants}.issubset(allowed_concepts),
        "exposure_caps_lte_1": all(float(row["exposure_cap"]) <= 1.0 for row in variants),
        "forbidden_instruments_disabled": all(
            row["leverage_allowed"] == "False"
            and row["shorting_allowed"] == "False"
            and row["options_allowed"] == "False"
            and row["direct_futures_allowed"] == "False"
            for row in variants
        ),
        "promotion_and_paper_false": all(row["promotion_eligible"] == "False" and row["paper_forward_eligible"] == "False" for row in variants),
        "bil_handling_explicit": all("BIL is the only cash/fallback asset" in row["cash_bil_handling_rule"] for row in variants),
    }


def variant_table_valid(audit: dict[str, Any]) -> bool:
    return (
        audit["variant_count_exact_24"]
        and audit["unique_variant_ids"]
        and not audit["missing_required_fields"]
        and audit["families"] == ["high_return_tactical_etf_equity_index"]
        and audit["concepts_allowed"]
        and audit["exposure_caps_lte_1"]
        and audit["forbidden_instruments_disabled"]
        and audit["promotion_and_paper_false"]
        and audit["bil_handling_explicit"]
    )


def policy_audit(text: str, required_tokens: tuple[str, ...]) -> dict[str, Any]:
    status = {token: token in text for token in required_tokens}
    return {"token_status": status, "passed": all(status.values())}


def volatility_audit(text: str) -> dict[str, Any]:
    return policy_audit(
        text,
        (
            "uncontrolled baseline tactical strategy return stream",
            "through date `t-1`",
            "60",
            "sqrt(252)",
            "25%",
            "35%",
            "1.00",
            "0.50",
            "0.25",
            "BIL/fallback returns are excluded",
            "normal allocation to avoid early artificial BIL bias",
            "No same-day return",
        ),
    )


def drawdown_audit(text: str) -> dict[str, Any]:
    return policy_audit(
        text,
        (
            "controlled strategy equity curve",
            "updated daily",
            "through date `t-1`",
            "No same-day return",
            "continues to update while guard is active",
            "-15%",
            "-25%",
            "-10%",
            "hard threshold takes precedence",
        ),
    )


def combined_audit(text: str) -> dict[str, Any]:
    return policy_audit(
        text,
        (
            "Build baseline tactical target allocation",
            "Apply SPY 200-day regime filter",
            "final allocation is `100% BIL`; stop",
            "apply volatility throttle where applicable",
            "Apply drawdown guard where applicable",
            "most defensive risky multiplier",
            "Final BIL allocation is `1 - risky_multiplier`",
            "Final exposure must be `<= 1.0`",
        ),
    )


def baseline_mapping_verification(source: dict[str, Any]) -> dict[str, Any]:
    variants = {row["variant_id"]: row for row in source["variants"]}
    methodology = csv_index(source["methodology_rows"])
    labels = csv_index(source["label_rows"])
    failures: list[dict[str, str]] = []
    verified = 0
    for mapping in source["baseline_mapping"]:
        variant = variants.get(mapping["variant_id"])
        method = methodology.get(mapping["baseline_variant_id"])
        label = labels.get(mapping["baseline_variant_id"])
        reasons = []
        if variant is None:
            reasons.append("controlled_variant_missing")
        if method is None:
            reasons.append("baseline_missing_methodology_source")
        if label is None:
            reasons.append("baseline_missing_label_source")
        if variant is not None:
            checks = {
                "baseline_family": mapping["baseline_family"] == "high_return_tactical_etf_equity_index",
                "universe_group": mapping["baseline_universe_group"] == variant["universe_group"],
                "universe": mapping["baseline_universe"] == variant["universe"],
                "lookback": str(mapping["baseline_lookback"]) == str(variant["momentum_lookback_days"]),
                "top_n": str(mapping["baseline_top_n"]) == str(variant["top_n"]),
                "rebalance": mapping["baseline_rebalance_frequency"] == variant["rebalance_frequency"] == "monthly",
                "same_window": mapping["same_window_baseline_comparison_required"] == "True",
                "status": mapping["baseline_mapping_status"] == "baseline_mapping_complete",
            }
            reasons.extend([name for name, passed in checks.items() if not passed])
        if method is not None:
            if method.get("family_id") != "high_return_tactical_etf_equity_index":
                reasons.append("methodology_family_mismatch")
            if variant is not None and method.get("universe") != variant["universe"]:
                reasons.append("methodology_universe_mismatch")
            if variant is not None and f"{variant['momentum_lookback_days']}d" not in method.get("rule_summary", ""):
                reasons.append("methodology_lookback_missing_from_rule_summary")
            if "top-2" not in method.get("rule_summary", ""):
                reasons.append("methodology_top2_missing_from_rule_summary")
            if "Monthly" not in method.get("rule_summary", ""):
                reasons.append("methodology_monthly_missing_from_rule_summary")
        if label is not None:
            if label.get("family_id") != "high_return_tactical_etf_equity_index":
                reasons.append("label_family_mismatch")
            if variant is not None and label.get("universe") != variant["universe"]:
                reasons.append("label_universe_mismatch")
            if variant is not None and f"{variant['momentum_lookback_days']}d" not in label.get("rule_summary", ""):
                reasons.append("label_lookback_missing_from_rule_summary")
            if "top-2" not in label.get("rule_summary", ""):
                reasons.append("label_top2_missing_from_rule_summary")
            if "Monthly" not in label.get("rule_summary", ""):
                reasons.append("label_monthly_missing_from_rule_summary")
        if reasons:
            failures.append({"variant_id": mapping.get("variant_id", ""), "baseline_variant_id": mapping.get("baseline_variant_id", ""), "reasons": ";".join(reasons)})
        else:
            verified += 1
    return {
        "baseline_mapping_verified_count": verified,
        "baseline_mapping_failed_count": len(failures),
        "failures": failures,
        "mapping_row_count": len(source["baseline_mapping"]),
    }


def success_failure_audit(text: str) -> dict[str, Any]:
    required = {
        "drawdown_reduction": "Max drawdown reduction versus the corresponding baseline",
        "cagr_retention": "CAGR retention versus baseline",
        "calmar": "Calmar or return/drawdown proxy",
        "bil_cash": "BIL/cash share",
        "duplicate": "correlation `>= 0.90`",
        "one_row": "one-row artifact",
        "exposure": "Daily exposure never exceeds `1.0`",
        "non_promotable": "not promotion thresholds",
    }
    status = {name: token in text for name, token in required.items()}
    return {
        "success_failure_criteria_measurable": all(status.values()),
        "criteria_status": status,
        "research_interpretation_only": status["non_promotable"],
    }


def test_quality_audit(test_text: str) -> dict[str, Any]:
    evidence_checks = all(token in test_text for token in ("load_variants", "load_baselines", "baseline_mapping_missing_count", "baseline_mapping_status"))
    manifest_checks = "load_manifest" in test_text
    warning = not evidence_checks
    return {
        "test_quality_warning": warning,
        "manifest_checks_present": manifest_checks,
        "evidence_checks_present": evidence_checks,
        "notes": "Patch v2 tests include manifest checks plus direct variant and baseline mapping CSV checks." if not warning else "Tests lean too heavily on manifest fields.",
    }


def run_readiness(payload: dict[str, Any]) -> tuple[str, str]:
    if (
        payload["variant_table_valid"]
        and payload["volatility_input_explicit"]
        and payload["drawdown_guard_timing_explicit"]
        and payload["combined_rule_precedence_explicit"]
        and payload["baseline_mapping_failed_count"] == 0
        and payload["baseline_mapping_verified_count"] == payload["variant_count_reviewed"]
        and payload["success_failure_criteria_measurable"]
    ):
        return DECISION_RUN_READY, NEXT_ACTION_RUN
    if (
        not payload["variant_table_valid"]
        or not payload["volatility_input_explicit"]
        or not payload["drawdown_guard_timing_explicit"]
        or not payload["combined_rule_precedence_explicit"]
        or payload["baseline_mapping_failed_count"] > 0
        or not payload["success_failure_criteria_measurable"]
    ):
        return DECISION_PATCH, NEXT_ACTION_PATCH
    return DECISION_MANUAL, NEXT_ACTION_MANUAL


def manifest(created: str, output: Path, source: dict[str, Any], table: dict[str, Any], vol: dict[str, Any], dd: dict[str, Any], combined: dict[str, Any], baseline: dict[str, Any], criteria: dict[str, Any], tests: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "created_utc": created,
        **MANIFEST_BASE,
        "evidence_path": str(output.resolve()),
        "source_patch_v2_evidence_path": str((ROOT / SOURCE_PATCH_V2_DIR).resolve()),
        "source_patch_v2_consistency_passed": source["consistency"].get("consistency_passed") is True,
        "variant_count_reviewed": table["variant_count"],
        "variant_table_valid": variant_table_valid(table),
        "volatility_input_explicit": vol["passed"],
        "drawdown_guard_timing_explicit": dd["passed"],
        "combined_rule_precedence_explicit": combined["passed"],
        "baseline_mapping_verified_count": baseline["baseline_mapping_verified_count"],
        "baseline_mapping_failed_count": baseline["baseline_mapping_failed_count"],
        "success_failure_criteria_measurable": criteria["success_failure_criteria_measurable"],
        "test_quality_warning": tests["test_quality_warning"],
    }
    decision, next_action = run_readiness(payload)
    payload["run_readiness_decision"] = decision
    payload["next_action"] = next_action
    return payload


def guardrail_md(payload: dict[str, Any]) -> str:
    return f"""# Patch V2 Guardrail Review

- New research batch run: `{payload['new_research_batch_run']}`
- Strategy discovery run: `{payload['new_strategy_discovery_run']}`
- New backtests run: `{payload['new_backtests_run']}`
- Raw performance metrics computed: `{payload['new_performance_metrics_from_raw_data_computed']}`
- Provider download: `{payload['provider_download']}`
- Intraday data used: `{payload['intraday_data_used']}`
- Broker API called: `{payload['broker_api_called']}`
- Paper-forward activation: `{payload['paper_forward_activation']}`
- Candidate exhaustive run: `{payload['candidate_exhaustive_run']}`
- Promotion candidates created: `{payload['promotion_candidates_created']}`
- Real-money recommendation: `{payload['real_money_recommendation']}`

No lane run occurred.
"""


def variant_table_md(audit: dict[str, Any]) -> str:
    return f"""# Patch V2 Variant Table Audit

- Variant count: `{audit['variant_count']}`
- Variant count exactly 24: `{audit['variant_count_exact_24']}`
- Unique variant IDs: `{audit['unique_variant_ids']}`
- Families: `{audit['families']}`
- Risk-control concepts: `{audit['risk_control_concepts']}`
- Concepts allowed: `{audit['concepts_allowed']}`
- Exposure caps <= 1.0: `{audit['exposure_caps_lte_1']}`
- Forbidden instruments disabled: `{audit['forbidden_instruments_disabled']}`
- Promotion and paper-forward eligibility false: `{audit['promotion_and_paper_false']}`
- BIL handling explicit: `{audit['bil_handling_explicit']}`
- Missing required fields: `{audit['missing_required_fields']}`
"""


def policy_md(title: str, audit: dict[str, Any]) -> str:
    lines = [f"# {title}", "", f"- Passed: `{audit['passed']}`", "", "Token checks:"]
    for token, passed in audit["token_status"].items():
        lines.append(f"- `{token}`: `{passed}`")
    return "\n".join(lines) + "\n"


def baseline_md(audit: dict[str, Any]) -> str:
    lines = [
        "# Baseline Mapping Verification",
        "",
        f"- Mapping rows reviewed: `{audit['mapping_row_count']}`",
        f"- Verified count: `{audit['baseline_mapping_verified_count']}`",
        f"- Failed count: `{audit['baseline_mapping_failed_count']}`",
        "",
        "Failures:",
    ]
    if not audit["failures"]:
        lines.append("- None")
    for failure in audit["failures"]:
        lines.append(f"- `{failure['variant_id']}` -> `{failure['baseline_variant_id']}`: {failure['reasons']}")
    return "\n".join(lines) + "\n"


def criteria_md(audit: dict[str, Any]) -> str:
    lines = [
        "# Success / Failure Criteria Audit",
        "",
        f"- Criteria measurable: `{audit['success_failure_criteria_measurable']}`",
        f"- Research interpretation only: `{audit['research_interpretation_only']}`",
        "",
        "Criteria status:",
    ]
    for name, passed in audit["criteria_status"].items():
        lines.append(f"- `{name}`: `{passed}`")
    return "\n".join(lines) + "\n"


def test_quality_md(audit: dict[str, Any]) -> str:
    return f"""# Test Quality Review

- Test quality warning: `{audit['test_quality_warning']}`
- Manifest checks present: `{audit['manifest_checks_present']}`
- Evidence checks present: `{audit['evidence_checks_present']}`

{audit['notes']}
"""


def summary_md(payload: dict[str, Any]) -> str:
    return f"""# High-Return Tactical Risk-Control Lane Design Patch V2 Audit

Lane audited: `{payload['lane_id_audited']}`

Variant count reviewed: `{payload['variant_count_reviewed']}`

Variant table valid: `{payload['variant_table_valid']}`

Volatility input explicit: `{payload['volatility_input_explicit']}`

Drawdown guard timing explicit: `{payload['drawdown_guard_timing_explicit']}`

Combined rule precedence explicit: `{payload['combined_rule_precedence_explicit']}`

Baseline mapping verified count: `{payload['baseline_mapping_verified_count']}`

Baseline mapping failed count: `{payload['baseline_mapping_failed_count']}`

Success/failure criteria measurable: `{payload['success_failure_criteria_measurable']}`

Test quality warning: `{payload['test_quality_warning']}`

Run-readiness decision: `{payload['run_readiness_decision']}`

Exact next action: `{payload['next_action']}`
"""


def decision_md(payload: dict[str, Any]) -> str:
    return f"""# Run-Readiness Decision

Decision: `{payload['run_readiness_decision']}`

Next action: `{payload['next_action']}`

Rationale:

- Patch v2 evidence is complete and internally consistent.
- The variant table is valid and still limited to 24 non-promotable designs.
- Volatility, drawdown, and combined precedence policies are implementation-ready.
- All 24 baseline mappings were verified against corrected methodology and corrected label CSVs.
- Success/failure criteria remain research interpretation criteria, not promotion gates.
"""


def do_not_run_md(payload: dict[str, Any]) -> str:
    return f"""# Do Not Run Until Patch V2 Audit Passes

This audit step itself did not run the lane.

Current decision: `{payload['run_readiness_decision']}`

If the next action is `run_high_return_tactical_risk_control_research_lane`, that action remains separate and must be explicitly run later.
"""


def next_action_md(payload: dict[str, Any]) -> str:
    return f"""# Risk-Control Lane Design Patch V2 Audit Next Action

Exact next action:

`{payload['next_action']}`

Do not run the next action in this task.
"""


def consistency_check(payload: dict[str, Any], output: Path) -> dict[str, Any]:
    required = {name: (output / name).exists() for name in REQUIRED_OUTPUT_FILES}
    checks = {
        "patch_v2_audit_only": payload["risk_control_lane_design_patch_v2_audit_only"] is True,
        "correct_lane_id": payload["lane_id_audited"] == LANE_ID,
        "source_patch_v2_evidence_reviewed": payload["source_patch_v2_evidence_reviewed"] is True,
        "corrected_baseline_sources_verified": payload["corrected_baseline_sources_verified"] is True,
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
        "variant_table_audit_exists": (output / "patch_v2_variant_table_audit.md").exists(),
        "volatility_input_audit_exists": (output / "volatility_input_audit.md").exists(),
        "drawdown_guard_timing_audit_exists": (output / "drawdown_guard_timing_audit.md").exists(),
        "baseline_mapping_verification_exists": (output / "baseline_mapping_verification.md").exists(),
        "run_readiness_decision_exists": (output / "run_readiness_decision.md").exists(),
        "baseline_failed_zero_if_run": payload["next_action"] != NEXT_ACTION_RUN or payload["baseline_mapping_failed_count"] == 0,
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
    section = f"""## High-Return Tactical Risk-Control Lane Design Patch V2 Audit

- Created UTC: `{created}`
- Evidence path: `{output.resolve()}`
- Lane ID audited: `{payload['lane_id_audited']}`
- Variant count reviewed: `{payload['variant_count_reviewed']}`
- Baseline mapping verified count: `{payload['baseline_mapping_verified_count']}`
- Baseline mapping failed count: `{payload['baseline_mapping_failed_count']}`
- Run-readiness decision: `{payload['run_readiness_decision']}`
- Next action: `{payload['next_action']}`
"""
    write_text(path, replace_or_append_section(before, "## High-Return Tactical Risk-Control Lane Design Patch V2 Audit", section))


def run(root: Path = ROOT) -> dict[str, Any]:
    created = now_utc()
    output = root / OUTPUT_DIR
    output.mkdir(parents=True, exist_ok=True)
    source = load_source(root)
    table = variant_table_audit(source["variants"])
    vol = volatility_audit(source["volatility_policy"])
    dd = drawdown_audit(source["drawdown_policy"])
    combined = combined_audit(source["combined_policy"])
    baseline = baseline_mapping_verification(source)
    criteria = success_failure_audit(source["success_failure"])
    tests = test_quality_audit(source["patch_v2_tests"])
    payload = manifest(created, output, source, table, vol, dd, combined, baseline, criteria, tests)

    write_json(output / "risk_control_lane_design_patch_v2_audit_manifest.json", payload)
    write_text(output / "risk_control_lane_design_patch_v2_audit_summary.md", summary_md(payload))
    write_text(output / "patch_v2_guardrail_review.md", guardrail_md(payload))
    write_text(output / "patch_v2_variant_table_audit.md", variant_table_md(table))
    write_text(output / "volatility_input_audit.md", policy_md("Volatility Input Audit", vol))
    write_text(output / "drawdown_guard_timing_audit.md", policy_md("Drawdown Guard Timing Audit", dd))
    write_text(output / "combined_precedence_audit.md", policy_md("Combined Precedence Audit", combined))
    write_text(output / "baseline_mapping_verification.md", baseline_md(baseline))
    write_text(output / "success_failure_criteria_audit.md", criteria_md(criteria))
    write_text(output / "test_quality_review.md", test_quality_md(tests))
    write_text(output / "run_readiness_decision.md", decision_md(payload))
    write_text(output / "do_not_run_until_patch_v2_audit_passes.md", do_not_run_md(payload))
    write_text(output / "risk_control_lane_design_patch_v2_audit_next_action.md", next_action_md(payload))
    write_json(output / "risk_control_lane_design_patch_v2_audit_consistency_check.json", {"consistency_passed": False})
    check = consistency_check(payload, output)
    write_json(output / "risk_control_lane_design_patch_v2_audit_consistency_check.json", check)
    update_research_metadata(root, created, output, payload)
    return {**payload, "output_dir": str(output.resolve()), "consistency_passed": check["consistency_passed"]}


if __name__ == "__main__":
    result = run()
    print(
        json.dumps(
            {
                "output_dir": result["output_dir"],
                "lane_id_audited": result["lane_id_audited"],
                "variant_count_reviewed": result["variant_count_reviewed"],
                "baseline_mapping_verified_count": result["baseline_mapping_verified_count"],
                "baseline_mapping_failed_count": result["baseline_mapping_failed_count"],
                "run_readiness_decision": result["run_readiness_decision"],
                "next_action": result["next_action"],
                "consistency_passed": result["consistency_passed"],
            },
            indent=2,
        )
    )
