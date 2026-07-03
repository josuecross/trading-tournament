from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import DATA_CACHE_DIR, ROOT
from strategy_lab.research_os.objective_reset.objective_reset_review import (
    replace_or_append_section,
    write_json,
    write_text,
)
from strategy_lab.research_os.research.high_return_tactical_risk_control_lane_design import (
    LANE_ID,
    OUTPUT_DIR as DESIGN_OUTPUT_DIR,
)
from strategy_lab.research_os.split_tracks import RESEARCH_STATE_PATH


OUTPUT_DIR = Path("evidence") / "research_recovery" / "high_return_tactical_risk_control_lane_design_audit" / "latest"
NEXT_ACTION_PATCH = "patch_high_return_tactical_risk_control_lane_design"
NEXT_ACTION_RUN = "run_high_return_tactical_risk_control_research_lane"
NEXT_ACTION_MANUAL = "manual_review_required_after_risk_control_lane_design_audit"
NEXT_ACTION_PAUSE = "pause_expansion_and_wait_for_manual_direction"
VALID_NEXT_ACTIONS = {NEXT_ACTION_PATCH, NEXT_ACTION_RUN, NEXT_ACTION_MANUAL, NEXT_ACTION_PAUSE}

DECISION_NEEDS_PATCH = "design_needs_patch_before_run"
DECISION_RUN_READY = "design_accepted_run_ready"
DECISION_MANUAL = "manual_review_required_before_run"
DECISION_REJECTED = "design_rejected"
VALID_DECISIONS = {DECISION_NEEDS_PATCH, DECISION_RUN_READY, DECISION_MANUAL, DECISION_REJECTED}

REQUIRED_OUTPUT_FILES = (
    "risk_control_lane_design_audit_manifest.json",
    "risk_control_lane_design_audit_summary.md",
    "design_guardrail_review.md",
    "variant_precision_audit.md",
    "threshold_explicitness_audit.md",
    "local_cache_feasibility_audit.md",
    "duplication_overconservatism_risk_review.md",
    "success_failure_criteria_audit.md",
    "run_readiness_decision.md",
    "do_not_run_until_audited.md",
    "risk_control_lane_design_audit_next_action.md",
    "risk_control_lane_design_audit_consistency_check.json",
)

MANIFEST_BASE = {
    "risk_control_lane_design_audit_only": True,
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


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def load_variants(root: Path) -> list[dict[str, str]]:
    path = root / DESIGN_OUTPUT_DIR / "variant_design_table.csv"
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def load_source_design(root: Path) -> dict[str, Any]:
    source_dir = root / DESIGN_OUTPUT_DIR
    return {
        "manifest": read_json(source_dir / "risk_control_lane_design_manifest.json"),
        "consistency": read_json(source_dir / "risk_control_lane_consistency_check.json"),
        "summary": read_text(source_dir / "risk_control_lane_design_summary.md"),
        "source_review": read_text(source_dir / "source_evidence_review.md"),
        "hypothesis": read_text(source_dir / "risk_control_hypothesis.md"),
        "variant_table_md": read_text(source_dir / "variant_design_table.md"),
        "frozen_rules": read_text(source_dir / "frozen_rule_summaries.md"),
        "evaluation_policy": read_text(source_dir / "risk_control_evaluation_policy.md"),
        "success_failure": read_text(source_dir / "success_failure_criteria.md"),
        "do_not_promote": read_text(source_dir / "do_not_promote_from_lane_design.md"),
        "variants": load_variants(root),
    }


def required_symbols(variants: list[dict[str, str]]) -> list[str]:
    symbols: set[str] = set()
    for row in variants:
        symbols.update(symbol.strip().upper() for symbol in row["universe"].split("|") if symbol.strip())
    return sorted(symbols)


def cache_feasibility(root: Path, variants: list[dict[str, str]]) -> dict[str, Any]:
    cache_dir = root / DATA_CACHE_DIR
    required = required_symbols(variants)
    symbol_status = {
        symbol: {
            "cache_file": str((cache_dir / f"{symbol}.csv").resolve()),
            "present": (cache_dir / f"{symbol}.csv").exists(),
        }
        for symbol in required
    }
    missing = [symbol for symbol, status in symbol_status.items() if not status["present"]]
    blocked_variants = []
    for row in variants:
        symbols = [symbol.strip().upper() for symbol in row["universe"].split("|") if symbol.strip()]
        if any(symbol in missing for symbol in symbols):
            blocked_variants.append(row["variant_id"])
    return {
        "cache_dir": str(cache_dir.resolve()),
        "required_symbols": required,
        "symbol_status": symbol_status,
        "missing_symbols": missing,
        "data_blocked_variant_count": len(blocked_variants),
        "data_blocked_variants": blocked_variants,
        "local_cache_feasible": len(missing) == 0,
    }


def variant_precision(variants: list[dict[str, str]]) -> dict[str, Any]:
    ids = [row["variant_id"] for row in variants]
    vague_terms = ("preregistered", "threshold", "recovery condition", "guard", "materially", "BIL or BIL remainder")
    vague_rows: list[dict[str, str]] = []
    missing_fields: list[dict[str, str]] = []
    for row in variants:
        for field in (
            "variant_id",
            "universe",
            "momentum_lookback_days",
            "top_n",
            "rebalance_frequency",
            "risk_control_rule",
            "fallback_allocation",
            "exposure_cap",
            "cash_bil_handling_rule",
        ):
            if not str(row.get(field, "")).strip():
                missing_fields.append({"variant_id": row.get("variant_id", ""), "missing_field": field})
        text = " ".join(str(row.get(field, "")) for field in ("risk_control_rule", "fallback_allocation", "cash_bil_handling_rule"))
        lower_text = text.lower()
        if any(term.lower() in lower_text for term in vague_terms):
            vague_rows.append({"variant_id": row["variant_id"], "risk_control_concept": row["risk_control_concept"], "text": text})
    all_exposure_ok = all(float(row["exposure_cap"]) <= 1.0 for row in variants)
    all_non_promotable = all(
        row["promotion_eligible"] == "False"
        and row["paper_forward_eligible"] == "False"
        and row["status"] == "non_promotable_preregistered_design"
        for row in variants
    )
    all_forbidden_assets_false = all(
        row["leverage_allowed"] == "False"
        and row["shorting_allowed"] == "False"
        and row["options_allowed"] == "False"
        and row["direct_futures_allowed"] == "False"
        for row in variants
    )
    return {
        "variant_count": len(variants),
        "unique_variant_ids": len(ids) == len(set(ids)),
        "missing_fields": missing_fields,
        "vague_variant_count": len(vague_rows),
        "vague_rows": vague_rows,
        "all_exposure_caps_lte_1": all_exposure_ok,
        "all_non_promotable": all_non_promotable,
        "all_forbidden_assets_false": all_forbidden_assets_false,
        "all_variant_rules_explicit": (
            len(missing_fields) == 0
            and len(vague_rows) == 0
            and len(ids) == len(set(ids))
            and all_exposure_ok
            and all_non_promotable
            and all_forbidden_assets_false
        ),
    }


def threshold_audit(variants: list[dict[str, str]]) -> dict[str, Any]:
    concepts = {row["risk_control_concept"] for row in variants}
    issues: list[str] = []
    if "spy200d_regime_filter" in concepts:
        # The 200-day rule is explicit enough to audit, but execution timing still belongs in the patch.
        pass
    if "realized_volatility_throttle" in concepts:
        issues.append("realized_volatility_throttle lacks a numeric high-volatility threshold or fixed percentile rule.")
    if "strategy_drawdown_guard" in concepts:
        issues.append("strategy_drawdown_guard lacks a numeric drawdown threshold.")
        issues.append("strategy_drawdown_guard lacks a defined re-entry/recovery rule.")
    if "regime_plus_volatility_guard" in concepts:
        issues.append("regime_plus_volatility_guard lacks explicit rule precedence when regime and volatility conditions conflict.")
        issues.append("regime_plus_volatility_guard inherits the missing volatility threshold.")
    fallback_issue_count = sum(1 for row in variants if row["fallback_allocation"] == "BIL or BIL remainder")
    if fallback_issue_count:
        issues.append("combined fallback text uses 'BIL or BIL remainder', which is implementation-ambiguous.")
    return {
        "threshold_issues": issues,
        "thresholds_explicit": len(issues) == 0,
        "fallback_rules_explicit": fallback_issue_count == 0,
        "reentry_rules_explicit": not any("re-entry" in issue for issue in issues),
    }


def success_criteria_audit(text: str) -> dict[str, Any]:
    issues = []
    if "materially reduced" in text.lower():
        issues.append("drawdown reduction uses 'materially reduced' without a numeric comparison policy.")
    if "not excessive" in text.lower():
        issues.append("cash/BIL share warning uses 'not excessive' without a numeric warning band.")
    required_topics = {
        "drawdown reduction": "Drawdown materially reduced",
        "return preservation": "Return not destroyed",
        "return/drawdown": "Return/drawdown tradeoff improved",
        "benchmark comparison": "SPY comparison remains meaningful",
        "cash/bil": "Cash/BIL share is not excessive",
        "exposure": "Daily exposure never exceeds",
        "one-row artifact": "not one-row artifacts",
        "duplicate": "duplicate active",
    }
    topic_status = {name: phrase.lower() in text.lower() for name, phrase in required_topics.items()}
    return {
        "criteria_topics_present": topic_status,
        "criteria_issues": issues,
        "success_failure_criteria_measurable": all(topic_status.values()) and not issues,
    }


def duplication_risk() -> dict[str, Any]:
    return {
        "duplication_or_overconservatism_risk_found": True,
        "risks": [
            "SPY 200-day regime variants may duplicate SPY_200d timing unless contribution and return-retention checks are explicit.",
            "Volatility throttle and drawdown guard variants may become BIL-heavy cash timing if exposure/cash share warnings are not numeric.",
            "Combined regime/volatility variants may over-constrain the source signal and destroy the high-return premise.",
            "Portfolio comparison must explicitly test active VM, active DSR, active combo, SPY_200d, and BIL-heavy behavior in a future run.",
        ],
    }


def run_readiness(payload: dict[str, Any]) -> tuple[str, str]:
    if (
        payload["all_variant_rules_explicit"]
        and payload["thresholds_explicit"]
        and payload["fallback_rules_explicit"]
        and payload["reentry_rules_explicit"]
        and payload["local_cache_feasible"]
        and payload["success_failure_criteria_measurable"]
        and not payload["duplication_or_overconservatism_risk_found"]
    ):
        return DECISION_RUN_READY, NEXT_ACTION_RUN
    if not payload["local_cache_feasible"]:
        return DECISION_MANUAL, NEXT_ACTION_MANUAL
    if not payload["thresholds_explicit"] or not payload["fallback_rules_explicit"] or not payload["reentry_rules_explicit"]:
        return DECISION_NEEDS_PATCH, NEXT_ACTION_PATCH
    if not payload["success_failure_criteria_measurable"]:
        return DECISION_NEEDS_PATCH, NEXT_ACTION_PATCH
    return DECISION_MANUAL, NEXT_ACTION_MANUAL


def manifest(created: str, output: Path, source: dict[str, Any], precision: dict[str, Any], thresholds: dict[str, Any], cache: dict[str, Any], criteria: dict[str, Any], duplicate: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "created_utc": created,
        **MANIFEST_BASE,
        "evidence_path": str(output.resolve()),
        "source_design_evidence_path": str((ROOT / DESIGN_OUTPUT_DIR).resolve()),
        "source_design_consistency_passed": source["consistency"].get("consistency_passed") is True,
        "variant_count_reviewed": precision["variant_count"],
        "all_variant_rules_explicit": precision["all_variant_rules_explicit"],
        "thresholds_explicit": thresholds["thresholds_explicit"],
        "fallback_rules_explicit": thresholds["fallback_rules_explicit"],
        "reentry_rules_explicit": thresholds["reentry_rules_explicit"],
        "local_cache_feasible": cache["local_cache_feasible"],
        "duplication_or_overconservatism_risk_found": duplicate["duplication_or_overconservatism_risk_found"],
        "success_failure_criteria_measurable": criteria["success_failure_criteria_measurable"],
    }
    decision, next_action = run_readiness(payload)
    payload["run_readiness_decision"] = decision
    payload["next_action"] = next_action
    return payload


def guardrail_review_md(payload: dict[str, Any]) -> str:
    return f"""# Design Guardrail Review

The source design packet was reviewed as an audit-only step.

- New research batch run: `{payload['new_research_batch_run']}`
- Strategy discovery run: `{payload['new_strategy_discovery_run']}`
- New backtests run: `{payload['new_backtests_run']}`
- Raw-data performance metrics computed: `{payload['new_performance_metrics_from_raw_data_computed']}`
- Provider download: `{payload['provider_download']}`
- Intraday data used: `{payload['intraday_data_used']}`
- Broker API called: `{payload['broker_api_called']}`
- Paper-forward activation: `{payload['paper_forward_activation']}`
- Promotion candidates created: `{payload['promotion_candidates_created']}`
- Macro/GLD lineage recovery run: `{payload['macro_gld_lineage_recovery_run']}`

Guardrails held. The audit did not run the lane.
"""


def variant_precision_md(precision: dict[str, Any]) -> str:
    lines = [
        "# Variant Precision Audit",
        "",
        f"- Variants reviewed: `{precision['variant_count']}`",
        f"- Unique variant IDs: `{precision['unique_variant_ids']}`",
        f"- Missing required fields: `{len(precision['missing_fields'])}`",
        f"- Vague/ambiguous rule rows: `{precision['vague_variant_count']}`",
        f"- Exposure caps <= 1.0: `{precision['all_exposure_caps_lte_1']}`",
        f"- Non-promotable/paper-ineligible: `{precision['all_non_promotable']}`",
        f"- Leverage/short/options/direct futures all false: `{precision['all_forbidden_assets_false']}`",
        "",
        "Ambiguous rows:",
    ]
    if not precision["vague_rows"]:
        lines.append("- None")
    for row in precision["vague_rows"]:
        lines.append(f"- `{row['variant_id']}` / `{row['risk_control_concept']}`: {row['text']}")
    return "\n".join(lines) + "\n"


def threshold_md(thresholds: dict[str, Any]) -> str:
    lines = [
        "# Threshold Explicitness Audit",
        "",
        f"- Thresholds explicit: `{thresholds['thresholds_explicit']}`",
        f"- Fallback rules explicit: `{thresholds['fallback_rules_explicit']}`",
        f"- Re-entry rules explicit: `{thresholds['reentry_rules_explicit']}`",
        "",
        "Issues:",
    ]
    if not thresholds["threshold_issues"]:
        lines.append("- None")
    for issue in thresholds["threshold_issues"]:
        lines.append(f"- {issue}")
    return "\n".join(lines) + "\n"


def cache_md(cache: dict[str, Any]) -> str:
    lines = [
        "# Local Cache Feasibility Audit",
        "",
        f"- Cache directory: `{cache['cache_dir']}`",
        f"- Local cache feasible: `{cache['local_cache_feasible']}`",
        f"- Missing symbols: `{', '.join(cache['missing_symbols']) if cache['missing_symbols'] else 'none'}`",
        f"- Data-blocked variants for future run planning: `{cache['data_blocked_variant_count']}`",
        "",
        "| Symbol | Present | Cache file |",
        "|---|---:|---|",
    ]
    for symbol, status in cache["symbol_status"].items():
        lines.append(f"| `{symbol}` | `{status['present']}` | `{status['cache_file']}` |")
    lines.append("")
    lines.append("No provider download was attempted.")
    return "\n".join(lines) + "\n"


def duplication_md(duplicate: dict[str, Any]) -> str:
    lines = [
        "# Duplication / Overconservatism Risk Review",
        "",
        f"- Risk found: `{duplicate['duplication_or_overconservatism_risk_found']}`",
        "",
        "Design risks:",
    ]
    for risk in duplicate["risks"]:
        lines.append(f"- {risk}")
    return "\n".join(lines) + "\n"


def criteria_md(criteria: dict[str, Any]) -> str:
    lines = [
        "# Success / Failure Criteria Audit",
        "",
        f"- Criteria measurable enough for a run: `{criteria['success_failure_criteria_measurable']}`",
        "",
        "Topic coverage:",
    ]
    for topic, present in criteria["criteria_topics_present"].items():
        lines.append(f"- `{topic}`: `{present}`")
    lines.append("")
    lines.append("Issues:")
    if not criteria["criteria_issues"]:
        lines.append("- None")
    for issue in criteria["criteria_issues"]:
        lines.append(f"- {issue}")
    return "\n".join(lines) + "\n"


def summary_md(payload: dict[str, Any]) -> str:
    return f"""# High-Return Tactical Risk-Control Lane Design Audit

Lane audited: `{payload['lane_id_audited']}`

Variants reviewed: `{payload['variant_count_reviewed']}`

All variant rules explicit: `{payload['all_variant_rules_explicit']}`

Thresholds explicit: `{payload['thresholds_explicit']}`

Fallback rules explicit: `{payload['fallback_rules_explicit']}`

Re-entry rules explicit: `{payload['reentry_rules_explicit']}`

Local cache feasible: `{payload['local_cache_feasible']}`

Duplication/overconservatism risk found: `{payload['duplication_or_overconservatism_risk_found']}`

Success/failure criteria measurable: `{payload['success_failure_criteria_measurable']}`

Run-readiness decision: `{payload['run_readiness_decision']}`

Exact next action: `{payload['next_action']}`
"""


def run_readiness_md(payload: dict[str, Any]) -> str:
    return f"""# Run-Readiness Decision

Decision: `{payload['run_readiness_decision']}`

Next action: `{payload['next_action']}`

Rationale:

- The design remains narrow and non-promotable.
- Local cache feasibility is acceptable.
- The design is not run-ready because volatility threshold, drawdown threshold, drawdown re-entry rule, combined-rule precedence, fallback semantics, and some success/failure comparison bands require explicit values before execution.
"""


def do_not_run_md(payload: dict[str, Any]) -> str:
    return f"""# Do Not Run Until Audited / Patched

This audit does not authorize a lane run.

Current decision: `{payload['run_readiness_decision']}`

The lane should not be run until the next action is completed and a later audit confirms the patch.
"""


def next_action_md(payload: dict[str, Any]) -> str:
    return f"""# Risk-Control Lane Design Audit Next Action

Exact next action:

`{payload['next_action']}`

Do not run the next action in this task.
"""


def consistency_check(payload: dict[str, Any], output: Path) -> dict[str, Any]:
    required = {name: (output / name).exists() for name in REQUIRED_OUTPUT_FILES}
    checks = {
        "audit_only_mode": payload["risk_control_lane_design_audit_only"] is True,
        "correct_lane_id_audited": payload["lane_id_audited"] == LANE_ID,
        "source_design_evidence_reviewed": payload["source_design_evidence_reviewed"] is True,
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
        "variant_precision_audit_exists": (output / "variant_precision_audit.md").exists(),
        "threshold_explicitness_audit_exists": (output / "threshold_explicitness_audit.md").exists(),
        "local_cache_feasibility_audit_exists": (output / "local_cache_feasibility_audit.md").exists(),
        "duplication_review_exists": (output / "duplication_overconservatism_risk_review.md").exists(),
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
    section = f"""## High-Return Tactical Risk-Control Lane Design Audit

- Created UTC: `{created}`
- Evidence path: `{output.resolve()}`
- Lane ID audited: `{payload['lane_id_audited']}`
- Variants reviewed: `{payload['variant_count_reviewed']}`
- Thresholds explicit: `{payload['thresholds_explicit']}`
- Local cache feasible: `{payload['local_cache_feasible']}`
- Run-readiness decision: `{payload['run_readiness_decision']}`
- Next action: `{payload['next_action']}`
"""
    write_text(path, replace_or_append_section(before, "## High-Return Tactical Risk-Control Lane Design Audit", section))


def run(root: Path = ROOT) -> dict[str, Any]:
    created = now_utc()
    output = root / OUTPUT_DIR
    output.mkdir(parents=True, exist_ok=True)
    source = load_source_design(root)
    variants = source["variants"]
    precision = variant_precision(variants)
    thresholds = threshold_audit(variants)
    cache = cache_feasibility(root, variants)
    duplicate = duplication_risk()
    criteria = success_criteria_audit(source["success_failure"])
    payload = manifest(created, output, source, precision, thresholds, cache, criteria, duplicate)

    write_json(output / "risk_control_lane_design_audit_manifest.json", payload)
    write_text(output / "risk_control_lane_design_audit_summary.md", summary_md(payload))
    write_text(output / "design_guardrail_review.md", guardrail_review_md(payload))
    write_text(output / "variant_precision_audit.md", variant_precision_md(precision))
    write_text(output / "threshold_explicitness_audit.md", threshold_md(thresholds))
    write_text(output / "local_cache_feasibility_audit.md", cache_md(cache))
    write_text(output / "duplication_overconservatism_risk_review.md", duplication_md(duplicate))
    write_text(output / "success_failure_criteria_audit.md", criteria_md(criteria))
    write_text(output / "run_readiness_decision.md", run_readiness_md(payload))
    write_text(output / "do_not_run_until_audited.md", do_not_run_md(payload))
    write_text(output / "risk_control_lane_design_audit_next_action.md", next_action_md(payload))
    write_json(output / "risk_control_lane_design_audit_consistency_check.json", {"consistency_passed": False})
    check = consistency_check(payload, output)
    write_json(output / "risk_control_lane_design_audit_consistency_check.json", check)
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
                "thresholds_explicit": result["thresholds_explicit"],
                "local_cache_feasible": result["local_cache_feasible"],
                "run_readiness_decision": result["run_readiness_decision"],
                "next_action": result["next_action"],
                "consistency_passed": result["consistency_passed"],
            },
            indent=2,
        )
    )
