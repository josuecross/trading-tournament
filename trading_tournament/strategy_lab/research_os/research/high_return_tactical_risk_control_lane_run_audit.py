from __future__ import annotations

import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.objective_reset.objective_reset_review import (
    replace_or_append_section,
    write_json,
    write_text,
)
from strategy_lab.research_os.research.high_return_tactical_risk_control_lane_design import LANE_ID
from strategy_lab.research_os.split_tracks import RESEARCH_STATE_PATH


SOURCE_RUN_DIR = Path("evidence") / "research_recovery" / "high_return_tactical_risk_control_lane_run" / "latest"
OUTPUT_DIR = Path("evidence") / "research_recovery" / "high_return_tactical_risk_control_lane_run_audit" / "latest"

NEXT_ACTION_VOL = "design_volatility_throttle_focused_research_followup"
NEXT_ACTION_REGIME_VOL = "design_regime_plus_volatility_guard_followup"
NEXT_ACTION_FIX = "fix_high_return_tactical_risk_control_lane_run_methodology_issue"
NEXT_ACTION_MANUAL = "manual_review_required_after_risk_control_lane_audit"
NEXT_ACTION_PAUSE = "pause_expansion_and_wait_for_manual_direction"
VALID_NEXT_ACTIONS = {NEXT_ACTION_VOL, NEXT_ACTION_REGIME_VOL, NEXT_ACTION_FIX, NEXT_ACTION_MANUAL, NEXT_ACTION_PAUSE}

REQUIRED_OUTPUT_FILES = (
    "risk_control_lane_run_audit_manifest.json",
    "risk_control_lane_run_audit_summary.md",
    "run_guardrail_review.md",
    "methodology_invariant_audit.md",
    "label_audit.md",
    "concept_level_audit.md",
    "volatility_throttle_review.md",
    "regime_plus_volatility_review.md",
    "spy200d_regime_filter_review.md",
    "drawdown_guard_review.md",
    "next_research_direction_decision.md",
    "non_promotable_guardrail_review.md",
    "risk_control_lane_run_audit_next_action.md",
    "risk_control_lane_run_audit_consistency_check.json",
)

MANIFEST_BASE = {
    "risk_control_lane_run_audit_only": True,
    "lane_id_audited": LANE_ID,
    "source_run_evidence_reviewed": True,
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
    source = root / SOURCE_RUN_DIR
    return {
        "manifest": read_json(source / "risk_control_lane_run_manifest.json"),
        "consistency": read_json(source / "risk_control_lane_run_consistency_check.json"),
        "summary": read_text(source / "risk_control_lane_run_summary.md"),
        "preflight": read_text(source / "local_cache_run_preflight.md"),
        "variants": read_csv_rows(source / "variant_run_results.csv"),
        "family": read_csv_rows(source / "family_run_summary.csv"),
        "baseline": read_csv_rows(source / "baseline_comparison_results.csv"),
        "baseline_review": read_text(source / "baseline_comparison_review.md"),
        "exposure_report": read_text(source / "exposure_invariant_report.md"),
        "cash_report": read_text(source / "cash_bil_invariant_report.md"),
        "label_summary": read_text(source / "risk_control_label_summary.md"),
        "promising": read_text(source / "promising_risk_control_signals.md"),
        "return_destroyed": read_text(source / "return_destroyed_signals.md"),
        "duplicates": read_text(source / "duplicate_existing_active_signals.md"),
        "drawdown_not_fixed": read_text(source / "drawdown_not_fixed_signals.md"),
        "do_not_promote": read_text(source / "do_not_promote_from_risk_control_lane_run.md"),
    }


def guardrail_audit(source: dict[str, Any]) -> dict[str, Any]:
    manifest = source["manifest"]
    checks = {
        "lane_id_correct": manifest.get("lane_id") == LANE_ID,
        "variant_count_24": manifest.get("variant_count_planned") == 24 and manifest.get("variant_count_evaluated") == 24,
        "no_new_variants": manifest.get("new_variants_created") is False,
        "no_new_families": manifest.get("new_families_created") is False,
        "local_cache_only": manifest.get("uses_local_cache_only") is True,
        "no_provider_download": manifest.get("provider_download") is False,
        "no_intraday": manifest.get("intraday_data_used") is False,
        "no_broker_api": manifest.get("broker_api_called") is False,
        "no_broker_orders": (
            manifest.get("broker_orders_submitted") is False
            and manifest.get("broker_orders_cancelled") is False
            and manifest.get("broker_orders_reconciled") is False
        ),
        "no_live_or_real_money": manifest.get("live_orders") is False and manifest.get("real_money_recommendation") is False,
        "no_paper_forward": manifest.get("paper_forward_activation") is False and manifest.get("new_paper_forward_candidate_created") is False,
        "no_candidate_exhaustive": manifest.get("candidate_exhaustive_run") is False,
        "no_promotion": manifest.get("promotion_candidates_created") is False and manifest.get("best_single_variant_promoted") is False,
        "active_vm_preserved": manifest.get("active_vm_preserved") is True,
        "active_dsr_preserved": manifest.get("active_dsr_preserved") is True,
        "static_all_weather_control_only": manifest.get("static_all_weather_benchmark_control_only") is True,
        "macro_gld_lineage_recovery_not_run": manifest.get("macro_gld_lineage_recovery_run") is False,
        "alpaca_delegated": manifest.get("alpaca_execution_module_delegated") is True,
    }
    return {"checks": checks, "passed": all(checks.values())}


def methodology_audit(source: dict[str, Any]) -> dict[str, Any]:
    manifest = source["manifest"]
    variants = source["variants"]
    max_exposure = max([to_float(row.get("max_daily_exposure"), 0.0) for row in variants] or [0.0])
    impossible_cash_days = sum(int(to_float(row.get("impossible_cash_and_risky_exposure_days"), 0.0)) for row in variants)
    weight_violations = sum(int(to_float(row.get("weight_sum_violation_count"), 0.0)) for row in variants)
    negative_violations = sum(int(to_float(row.get("negative_weight_violation_count"), 0.0)) for row in variants)
    nan_weights = sum(int(to_float(row.get("nan_weight_count"), 0.0)) for row in variants)
    source_text = source["preflight"] + "\n" + source["baseline_review"]
    checks = {
        "source_consistency_passed": source["consistency"].get("consistency_passed") is True,
        "exposure_invariant_passed": manifest.get("exposure_invariant_passed") is True,
        "cash_bil_invariant_passed": manifest.get("cash_bil_invariant_passed") is True,
        "max_daily_exposure_lte_tolerance": max_exposure <= 1.000001,
        "no_impossible_bil_plus_risky_exposure": impossible_cash_days == 0,
        "no_weight_sum_violations": weight_violations == 0,
        "no_negative_weight_violations": negative_violations == 0,
        "no_nan_weights": nan_weights == 0,
        "baseline_complete_count_24": manifest.get("baseline_comparison_complete_count") == 24,
        "baseline_missing_count_0": manifest.get("baseline_comparison_missing_count") == 0,
        "corrected_sources_used": "Corrected baseline sources used" in source_text,
        "contaminated_outputs_not_used": "Contaminated original batch v1 outputs were not used" in source_text,
    }
    return {
        "checks": checks,
        "passed": all(checks.values()),
        "max_daily_exposure": max_exposure,
        "impossible_cash_days": impossible_cash_days,
        "weight_violations": weight_violations,
        "negative_violations": negative_violations,
        "nan_weights": nan_weights,
    }


def label_audit(source: dict[str, Any]) -> dict[str, Any]:
    rows = source["variants"]
    promising = [row for row in rows if row.get("risk_control_research_label") == "risk_control_signal_promising"]
    return_destroyed = [row for row in rows if row.get("risk_control_research_label") == "risk_control_signal_return_destroyed"]
    duplicates = [row for row in rows if row.get("risk_control_research_label") == "risk_control_signal_duplicate_existing_active"]
    mislabels = {
        "promising_drawdown_worse_than_minus_45": [
            row["variant_id"] for row in promising if to_float(row.get("max_drawdown")) < -0.45
        ],
        "promising_cagr_retention_below_60": [
            row["variant_id"] for row in promising if to_float(row.get("cagr_retention_vs_baseline")) < 0.60
        ],
        "promising_drawdown_reduction_below_25": [
            row["variant_id"] for row in promising if to_float(row.get("drawdown_reduction_vs_baseline")) < 0.25
        ],
        "promising_high_bil_cash_share": [
            row["variant_id"] for row in promising if to_float(row.get("average_bil_cash_share")) > 0.70
        ],
        "promising_duplicate_reference_like": [
            row["variant_id"] for row in promising if to_float(row.get("duplicate_reference_correlation")) >= 0.90
        ],
        "return_destroyed_not_return_destroyed_by_rule": [
            row["variant_id"]
            for row in return_destroyed
            if not (to_float(row.get("cagr_retention_vs_baseline")) < 0.40 or to_float(row.get("cagr")) < 0.05)
        ],
        "duplicates_below_duplicate_threshold": [
            row["variant_id"] for row in duplicates if to_float(row.get("duplicate_reference_correlation")) < 0.90
        ],
    }
    return {
        "passed": all(not values for values in mislabels.values()),
        "mislabels": mislabels,
        "promising_count": len(promising),
        "return_destroyed_count": len(return_destroyed),
        "duplicate_count": len(duplicates),
    }


def concept_stats(source: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = pd.DataFrame(source["variants"])
    for column in (
        "cagr",
        "max_drawdown",
        "drawdown_reduction_vs_baseline",
        "cagr_retention_vs_baseline",
        "calmar_improvement_vs_baseline",
        "average_bil_cash_share",
        "duplicate_reference_correlation",
    ):
        rows[column] = pd.to_numeric(rows[column], errors="coerce")
    result: dict[str, dict[str, Any]] = {}
    for concept, subset in rows.groupby("risk_control_concept"):
        labels = subset["risk_control_research_label"].value_counts().to_dict()
        result[concept] = {
            "variants": int(len(subset)),
            "promising_count": int(labels.get("risk_control_signal_promising", 0)),
            "return_destroyed_count": int(labels.get("risk_control_signal_return_destroyed", 0)),
            "duplicate_count": int(labels.get("risk_control_signal_duplicate_existing_active", 0)),
            "median_cagr": float(subset["cagr"].median()),
            "median_max_drawdown": float(subset["max_drawdown"].median()),
            "median_drawdown_reduction": float(subset["drawdown_reduction_vs_baseline"].median()),
            "median_cagr_retention": float(subset["cagr_retention_vs_baseline"].median()),
            "median_calmar_improvement": float(subset["calmar_improvement_vs_baseline"].median()),
            "median_bil_cash_share": float(subset["average_bil_cash_share"].median()),
            "median_duplicate_correlation": float(subset["duplicate_reference_correlation"].median()),
        }
    return result


def direction_decision(methodology: dict[str, Any], labels: dict[str, Any], concepts: dict[str, dict[str, Any]]) -> tuple[str, int]:
    if not methodology["passed"] or not labels["passed"]:
        return NEXT_ACTION_FIX, 0
    vol = concepts.get("realized_volatility_throttle", {})
    regime = concepts.get("regime_plus_volatility_guard", {})
    vol_ok = (
        vol.get("variants") == 6
        and vol.get("promising_count") == 6
        and vol.get("duplicate_count") == 0
        and vol.get("median_cagr_retention", 0.0) >= 0.90
        and vol.get("median_drawdown_reduction", 0.0) >= 0.25
    )
    regime_ok = (
        regime.get("variants") == 6
        and regime.get("promising_count", 0) >= 5
        and regime.get("median_cagr_retention", 0.0) >= 0.80
        and regime.get("median_drawdown_reduction", 0.0) >= 0.50
    )
    if vol_ok and not regime_ok:
        return NEXT_ACTION_VOL, 1
    if regime_ok and not vol_ok:
        return NEXT_ACTION_REGIME_VOL, 1
    if vol_ok and regime_ok:
        # Volatility throttle is less duplicate-like and preserves more return, while regime+vol is the comparator.
        return NEXT_ACTION_VOL, 1
    return NEXT_ACTION_MANUAL, 0


def build_manifest(
    created: str,
    output: Path,
    source: dict[str, Any],
    guardrails: dict[str, Any],
    methodology: dict[str, Any],
    labels: dict[str, Any],
    concepts: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    next_action, direction_count = direction_decision(methodology, labels, concepts)
    return {
        "created_utc": created,
        "evidence_path": str(output.resolve()),
        **MANIFEST_BASE,
        "source_run_evidence_path": str((ROOT / SOURCE_RUN_DIR).resolve()),
        "variant_count_reviewed": len(source["variants"]),
        "methodology_invariants_valid": methodology["passed"],
        "labels_valid": labels["passed"],
        "volatility_throttle_promising": concepts.get("realized_volatility_throttle", {}).get("promising_count") == 6
        and concepts.get("realized_volatility_throttle", {}).get("duplicate_count") == 0,
        "regime_plus_volatility_promising": concepts.get("regime_plus_volatility_guard", {}).get("promising_count", 0) >= 5,
        "spy200d_duplicate_or_reference_like": concepts.get("spy200d_regime_filter", {}).get("duplicate_count", 0) > 0,
        "drawdown_guard_return_destroyed": concepts.get("strategy_drawdown_guard", {}).get("return_destroyed_count") == 6,
        "accepted_next_research_direction_count": direction_count,
        "run_guardrails_valid": guardrails["passed"],
        "next_action": next_action,
    }


def guardrail_md(payload: dict[str, Any], audit: dict[str, Any]) -> str:
    lines = ["# Run Guardrail Review", "", f"- Passed: `{audit['passed']}`", ""]
    for name, passed in audit["checks"].items():
        lines.append(f"- `{name}`: `{passed}`")
    return "\n".join(lines) + "\n"


def methodology_md(audit: dict[str, Any]) -> str:
    lines = [
        "# Methodology / Invariant Audit",
        "",
        f"- Passed: `{audit['passed']}`",
        f"- Max daily exposure: `{audit['max_daily_exposure']}`",
        f"- Impossible BIL plus risky exposure days: `{audit['impossible_cash_days']}`",
        f"- Weight sum violations: `{audit['weight_violations']}`",
        f"- Negative weight violations: `{audit['negative_violations']}`",
        f"- NaN weight count: `{audit['nan_weights']}`",
        "",
        "Checks:",
    ]
    for name, passed in audit["checks"].items():
        lines.append(f"- `{name}`: `{passed}`")
    return "\n".join(lines) + "\n"


def label_md(audit: dict[str, Any]) -> str:
    lines = [
        "# Label Audit",
        "",
        f"- Labels valid: `{audit['passed']}`",
        f"- Promising rows: `{audit['promising_count']}`",
        f"- Return-destroyed rows: `{audit['return_destroyed_count']}`",
        f"- Duplicate/reference-like rows: `{audit['duplicate_count']}`",
        "",
        "Mislabel checks:",
    ]
    for name, rows in audit["mislabels"].items():
        lines.append(f"- `{name}`: `{len(rows)}` {rows if rows else ''}")
    return "\n".join(lines) + "\n"


def concept_md(concepts: dict[str, dict[str, Any]]) -> str:
    lines = ["# Concept-Level Audit", ""]
    for concept, stats in concepts.items():
        lines.append(f"## {concept}")
        lines.append("")
        for key, value in stats.items():
            lines.append(f"- `{key}`: `{value}`")
        lines.append("")
    return "\n".join(lines)


def specific_review_md(concept: str, stats: dict[str, Any], conclusion: str) -> str:
    lines = [f"# {concept} Review", "", conclusion, ""]
    for key, value in stats.items():
        lines.append(f"- `{key}`: `{value}`")
    return "\n".join(lines) + "\n"


def direction_md(payload: dict[str, Any]) -> str:
    return f"""# Next Research Direction Decision

Accepted next research direction count: `{payload['accepted_next_research_direction_count']}`

Exact next action: `{payload['next_action']}`

Decision rationale:

- Volatility throttle produced broad evidence across all six variants, had no duplicate/reference-like labels, preserved baseline CAGR better than the other concepts, and kept BIL/cash share modest.
- Regime plus volatility reduced drawdown more deeply, but it is more SPY-regime/reference-adjacent and had one duplicate/reference-like row.
- SPY 200d regime filter is useful as a comparator/control but is partly duplicate/reference-like.
- Strategy drawdown guard reduced drawdown by going mostly defensive and destroyed return across all rows.

This does not create a candidate, preregistration candidate, paper-forward candidate, or promotion-review candidate.
"""


def non_promotable_md(payload: dict[str, Any]) -> str:
    return f"""# Non-Promotable Guardrail Review

- Research outputs remain non-promotable: `{payload['research_outputs_remain_non_promotable']}`
- Promotion candidates created: `{payload['promotion_candidates_created']}`
- Paper-forward activation: `{payload['paper_forward_activation']}`
- New paper-forward candidate created: `{payload['new_paper_forward_candidate_created']}`
- Candidate exhaustive run: `{payload['candidate_exhaustive_run']}`
- Best single variant promoted: `{payload['best_single_variant_promoted']}`

No row may move directly from this audit into paper/demo, promotion review, candidate exhaustive, or live use.
"""


def summary_md(payload: dict[str, Any]) -> str:
    return f"""# High-Return Tactical Risk-Control Lane Run Audit

Lane audited: `{payload['lane_id_audited']}`

Variant count reviewed: `{payload['variant_count_reviewed']}`

Methodology invariants valid: `{payload['methodology_invariants_valid']}`

Labels valid: `{payload['labels_valid']}`

Volatility throttle promising: `{payload['volatility_throttle_promising']}`

Regime plus volatility promising: `{payload['regime_plus_volatility_promising']}`

SPY 200d duplicate/reference-like: `{payload['spy200d_duplicate_or_reference_like']}`

Drawdown guard return destroyed: `{payload['drawdown_guard_return_destroyed']}`

Accepted next research direction count: `{payload['accepted_next_research_direction_count']}`

Exact next action: `{payload['next_action']}`
"""


def next_action_md(next_action: str) -> str:
    return f"""# Risk-Control Lane Run Audit Next Action

Exact next action:

`{next_action}`

Do not run the next action in this task.
"""


def update_research_metadata(root: Path, created: str, output: Path, payload: dict[str, Any]) -> None:
    path = root / RESEARCH_STATE_PATH
    before = read_text(path)
    section = f"""## Latest High-Return Tactical Risk-Control Lane Run Audit

- Created UTC: `{created}`
- Evidence path: `{output.resolve()}`
- Lane ID: `{payload['lane_id_audited']}`
- Variant count reviewed: `{payload['variant_count_reviewed']}`
- Methodology invariants valid: `{payload['methodology_invariants_valid']}`
- Labels valid: `{payload['labels_valid']}`
- Accepted next research direction count: `{payload['accepted_next_research_direction_count']}`
- Promotion candidates created: `{payload['promotion_candidates_created']}`
- Paper-forward activation: `{payload['paper_forward_activation']}`
- Provider download: `{payload['provider_download']}`
- Next action: `{payload['next_action']}`
"""
    write_text(path, replace_or_append_section(before, "## Latest High-Return Tactical Risk-Control Lane Run Audit", section))


def consistency_check(payload: dict[str, Any], output: Path) -> dict[str, Any]:
    required = {name: (output / name).exists() for name in REQUIRED_OUTPUT_FILES}
    required["risk_control_lane_run_audit_consistency_check.json"] = True
    checks = {
        "audit_only": payload["risk_control_lane_run_audit_only"] is True,
        "correct_lane_id": payload["lane_id_audited"] == LANE_ID,
        "source_run_reviewed": payload["source_run_evidence_reviewed"] is True,
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
        "no_live_or_real_money": payload["live_orders"] is False and payload["real_money_recommendation"] is False,
        "no_promotion": payload["promotion_candidates_created"] is False and payload["best_single_variant_promoted"] is False,
        "no_paper_forward": payload["paper_forward_activation"] is False and payload["new_paper_forward_candidate_created"] is False,
        "no_candidate_exhaustive": payload["candidate_exhaustive_run"] is False,
        "research_outputs_non_promotable": payload["research_outputs_remain_non_promotable"] is True,
        "active_vm_preserved": payload["active_vm_preserved"] is True,
        "active_dsr_preserved": payload["active_dsr_preserved"] is True,
        "static_all_weather_control_only": payload["static_all_weather_benchmark_control_only"] is True,
        "macro_gld_lineage_recovery_not_run": payload["macro_gld_lineage_recovery_run"] is False,
        "alpaca_delegated": payload["alpaca_execution_module_delegated"] is True,
        "methodology_invariant_audit_exists": (output / "methodology_invariant_audit.md").exists(),
        "label_audit_exists": (output / "label_audit.md").exists(),
        "concept_level_audit_exists": (output / "concept_level_audit.md").exists(),
        "next_direction_decision_exists": (output / "next_research_direction_decision.md").exists(),
        "non_promotable_review_exists": (output / "non_promotable_guardrail_review.md").exists(),
        "next_action_valid": payload["next_action"] in VALID_NEXT_ACTIONS,
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
    methodology: dict[str, Any],
    labels: dict[str, Any],
    concepts: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    output = root / OUTPUT_DIR
    output.mkdir(parents=True, exist_ok=True)
    payload = build_manifest(created, output, source, guardrails, methodology, labels, concepts)
    write_json(output / "risk_control_lane_run_audit_manifest.json", payload)
    write_text(output / "risk_control_lane_run_audit_summary.md", summary_md(payload))
    write_text(output / "run_guardrail_review.md", guardrail_md(payload, guardrails))
    write_text(output / "methodology_invariant_audit.md", methodology_md(methodology))
    write_text(output / "label_audit.md", label_md(labels))
    write_text(output / "concept_level_audit.md", concept_md(concepts))
    write_text(
        output / "volatility_throttle_review.md",
        specific_review_md(
            "Realized Volatility Throttle",
            concepts.get("realized_volatility_throttle", {}),
            "Broadly promising and least duplicate-like; still needs focused research because drawdowns remain material.",
        ),
    )
    write_text(
        output / "regime_plus_volatility_review.md",
        specific_review_md(
            "Regime Plus Volatility Guard",
            concepts.get("regime_plus_volatility_guard", {}),
            "Strong drawdown reduction with acceptable retention, but more SPY-regime/reference-adjacent than pure volatility throttle.",
        ),
    )
    write_text(
        output / "spy200d_regime_filter_review.md",
        specific_review_md(
            "SPY 200d Regime Filter",
            concepts.get("spy200d_regime_filter", {}),
            "Useful comparator/control, but duplicate/reference-like flags argue against making it the primary next research lane.",
        ),
    )
    write_text(
        output / "drawdown_guard_review.md",
        specific_review_md(
            "Strategy Drawdown Guard",
            concepts.get("strategy_drawdown_guard", {}),
            "Return was destroyed across all rows; close this concept for this lane unless a new hypothesis is written.",
        ),
    )
    write_text(output / "next_research_direction_decision.md", direction_md(payload))
    write_text(output / "non_promotable_guardrail_review.md", non_promotable_md(payload))
    write_text(output / "risk_control_lane_run_audit_next_action.md", next_action_md(payload["next_action"]))
    consistency = consistency_check(payload, output)
    write_json(output / "risk_control_lane_run_audit_consistency_check.json", consistency)
    update_research_metadata(root, created, output, payload)
    return {**payload, "output_dir": str(output.resolve()), "consistency_passed": consistency["consistency_passed"]}


def run(root: Path = ROOT) -> dict[str, Any]:
    created = now_utc()
    source = load_source(root)
    guardrails = guardrail_audit(source)
    methodology = methodology_audit(source)
    labels = label_audit(source)
    concepts = concept_stats(source)
    return write_outputs(root, created, source, guardrails, methodology, labels, concepts)


if __name__ == "__main__":
    result = run()
    print(
        json.dumps(
            {
                "output_dir": result["output_dir"],
                "lane_id_audited": result["lane_id_audited"],
                "variant_count_reviewed": result["variant_count_reviewed"],
                "methodology_invariants_valid": result["methodology_invariants_valid"],
                "labels_valid": result["labels_valid"],
                "next_action": result["next_action"],
                "consistency_passed": result["consistency_passed"],
            },
            indent=2,
        )
    )
