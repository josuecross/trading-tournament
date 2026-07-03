from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.objective_reset.objective_reset_review import replace_or_append_section, write_json, write_text
from strategy_lab.research_os.split_tracks import RESEARCH_STATE_PATH


BATCH_ID = "profit_oriented_research_batch_v1"
SOURCE_DIR = Path("evidence") / "research_recovery" / "profit_oriented_research_batch_v1" / "latest"
OUTPUT_DIR = Path("evidence") / "research_recovery" / "profit_oriented_research_batch_v1_audit" / "latest"
SOURCE_CODE_PATH = Path("strategy_lab") / "research_os" / "research" / "profit_oriented_research_batch_v1.py"

NEXT_ACTION_FIX = "fix_profit_research_batch_v1_methodology_issue"
NEXT_ACTION_GLD = "recover_gld_macro_family_lineage"
NEXT_ACTION_BATCH2 = "design_profit_oriented_research_batch_v2"
NEXT_ACTION_MANUAL = "manual_review_required_after_profit_batch_v1_audit"
NEXT_ACTION_PAUSE = "pause_expansion_and_wait_for_manual_direction"
VALID_NEXT_ACTIONS = {NEXT_ACTION_FIX, NEXT_ACTION_GLD, NEXT_ACTION_BATCH2, NEXT_ACTION_MANUAL, NEXT_ACTION_PAUSE}

REQUIRED_OUTPUT_FILES = (
    "profit_batch_v1_audit_manifest.json",
    "profit_batch_v1_audit_summary.md",
    "methodology_validity_review.md",
    "exposure_and_weighting_audit.md",
    "cash_bil_handling_audit.md",
    "return_calculation_audit.md",
    "trade_count_turnover_audit.md",
    "benchmark_alignment_audit.md",
    "scoring_and_labeling_audit.md",
    "family_deeper_research_review.md",
    "gld_macro_lineage_review.md",
    "non_promotable_guardrail_review.md",
    "profit_batch_v1_audit_next_action.md",
    "profit_batch_v1_audit_consistency_check.json",
)

MANIFEST_FLAGS = {
    "profit_batch_v1_audit_only": True,
    "batch_id_audited": BATCH_ID,
    "new_research_batch_run": False,
    "new_strategy_discovery_run": False,
    "new_backtests_run": False,
    "new_performance_metrics_from_raw_data_computed": False,
    "new_variants_created": False,
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
    "manual_observation_loop_blocking_research": False,
    "alpaca_execution_module_delegated": True,
}


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def load_source_artifacts(root: Path) -> dict[str, Any]:
    source = root / SOURCE_DIR
    variants = pd.read_csv(source / "profit_research_variant_results.csv")
    families = pd.read_csv(source / "profit_research_family_summary.csv")
    return {
        "source_dir": source,
        "manifest": read_json(source / "profit_research_batch_manifest.json"),
        "consistency": read_json(source / "profit_research_batch_consistency_check.json"),
        "variants": variants,
        "families": families,
        "source_code": read_text(root / SOURCE_CODE_PATH),
        "gld_lineage_text": read_text(source / "gld_macro_lineage_status.md"),
        "methodology_text": read_text(source / "methodology_notes.md"),
    }


def audit_findings(artifacts: dict[str, Any]) -> dict[str, Any]:
    variants: pd.DataFrame = artifacts["variants"]
    families: pd.DataFrame = artifacts["families"]
    code = artifacts["source_code"]

    exposure = numeric(variants["average_exposure"])
    cash = numeric(variants["cash_bil_allocation_share"])
    cagr = numeric(variants["cagr"])
    mdd = numeric(variants["max_drawdown"])
    high_exposure = variants[exposure > 1.000001].copy()
    high_cash_high_cagr = variants[(cash > 0.30) & (cagr > 0.10)].copy()
    severe_exposure = variants[exposure > 2.0].copy()
    non_promotable_ok = (
        variants["promotion_eligibility"].astype(str).str.lower().eq("false").all()
        and variants["paper_forward_eligibility"].astype(str).str.lower().eq("false").all()
    )
    forbidden_labels = {
        "promotion_review_candidate",
        "candidate_exhaustive_candidate",
        "paper_forward_candidate",
        "live_ready",
        "demo_active_new",
        "real_money_candidate",
    }
    labels = set(variants["research_label"].astype(str))
    forbidden_labels_present = sorted(labels.intersection(forbidden_labels))

    ffill_weight_bug_pattern = (
        "weights = weights.replace(0.0, np.nan).ffill().fillna(0.0)" in code
        and "weights.shift(1).fillna(0.0) * returns" in code
    )
    bil_selection_exclusion_present = 'score = score.drop(cash_symbol, errors="ignore")' in code
    static_normalization_present = "weights[symbol] = float(raw_weights.get(symbol, 0.0)) / total" in code
    breakout_fallback_present = "weights[cash_symbol] = 1.0 - exposure" in code

    deeper_marked = families[families["deserves_deeper_research"].astype(str).str.lower() == "true"]
    gld_rows = variants[variants["family_id"] == "macro_gld_duration_risk_off"]
    gld_lineage_block = (
        not gld_rows.empty
        and gld_rows["lineage_status"].astype(str).eq("lineage_incomplete_research_only").all()
    )

    exposure_issue = len(high_exposure) > 0 or ffill_weight_bug_pattern
    cash_issue = len(high_cash_high_cagr) > 0
    return_issue = exposure_issue
    scoring_issue = exposure_issue or cash_issue or len(deeper_marked) > 0
    methodology_valid = not (exposure_issue or cash_issue or return_issue or scoring_issue)

    return {
        "source_variant_count": int(len(variants)),
        "source_family_count": int(variants["family_id"].nunique()),
        "source_manifest_consistency_passed": artifacts["consistency"].get("consistency_passed") is True,
        "average_exposure_gt_1_count": int(len(high_exposure)),
        "average_exposure_gt_2_count": int(len(severe_exposure)),
        "max_average_exposure": float(exposure.max(skipna=True)),
        "high_cash_high_cagr_count": int(len(high_cash_high_cagr)),
        "max_cash_bil_allocation_share": float(cash.max(skipna=True)),
        "max_cagr": float(cagr.max(skipna=True)),
        "worst_max_drawdown": float(mdd.min(skipna=True)),
        "ffill_weight_bug_pattern_found": ffill_weight_bug_pattern,
        "bil_selection_exclusion_present": bil_selection_exclusion_present,
        "static_weight_normalization_present": static_normalization_present,
        "breakout_cash_replacement_present": breakout_fallback_present,
        "promotion_eligibility_all_false": bool(non_promotable_ok),
        "forbidden_labels_present": forbidden_labels_present,
        "deeper_research_families_marked_count": int(len(deeper_marked)),
        "deeper_research_families_marked": list(deeper_marked["family_id"].astype(str)),
        "families_deeper_research_accepted_count": 0,
        "gld_macro_lineage_blocks_deeper_research": bool(gld_lineage_block),
        "methodology_valid": bool(methodology_valid),
        "exposure_weighting_issue_found": bool(exposure_issue),
        "cash_bil_issue_found": bool(cash_issue),
        "return_calculation_issue_found": bool(return_issue),
        "benchmark_alignment_issue_found": False,
        "scoring_labeling_issue_found": bool(scoring_issue),
        "next_action": NEXT_ACTION_FIX if not methodology_valid else (NEXT_ACTION_GLD if gld_lineage_block else NEXT_ACTION_BATCH2),
    }


def table_sample(df: pd.DataFrame, columns: list[str], limit: int = 12) -> str:
    if df.empty:
        return "None."
    clipped = df[columns].head(limit)
    lines = ["| " + " | ".join(columns) + " |", "|" + "|".join("---" for _ in columns) + "|"]
    for _, row in clipped.iterrows():
        lines.append("| " + " | ".join(str(row.get(col, "")) for col in columns) + " |")
    return "\n".join(lines)


def exposure_audit_md(variants: pd.DataFrame, findings: dict[str, Any]) -> str:
    exposure = numeric(variants["average_exposure"])
    high = variants[exposure > 1.000001].sort_values("average_exposure", ascending=False)
    sample = table_sample(
        high,
        ["family_id", "variant_id", "average_exposure", "cash_bil_allocation_share", "cagr", "max_drawdown", "research_label"],
    )
    return f"""# Exposure And Weighting Audit

Result: `blocking_issue`

Variants with `average_exposure > 1.0`: `{findings['average_exposure_gt_1_count']}`

Variants with `average_exposure > 2.0`: `{findings['average_exposure_gt_2_count']}`

Maximum saved average exposure: `{findings['max_average_exposure']:.6f}`

The saved output shows impossible long-only/unlevered exposure for multiple monthly momentum variants. This is not an intended high-risk feature; it is consistent with an unintended weight accumulation bug.

Source-code pattern found: `weights = weights.replace(0.0, np.nan).ffill().fillna(0.0)`. Because zero weights are converted to NaN before forward fill, previously selected assets can remain allocated after a later rebalance selects new assets. That can make top-N allocations accumulate above 100%.

## Affected Sample

{sample}
"""


def cash_audit_md(variants: pd.DataFrame, findings: dict[str, Any]) -> str:
    cash = numeric(variants["cash_bil_allocation_share"])
    cagr = numeric(variants["cagr"])
    suspicious = variants[(cash > 0.30) & (cagr > 0.10)].sort_values("cagr", ascending=False)
    sample = table_sample(
        suspicious,
        ["family_id", "variant_id", "average_exposure", "cash_bil_allocation_share", "cagr", "research_label"],
    )
    return f"""# Cash / BIL Handling Audit

Result: `blocking_issue`

Rows with cash/BIL share above `0.30` and CAGR above `0.10`: `{findings['high_cash_high_cagr_count']}`

Maximum cash/BIL allocation share: `{findings['max_cash_bil_allocation_share']:.6f}`

Many rows report `cash_bil_allocation_share = 1.0` while also reporting large risky exposure and high CAGR. That is internally inconsistent for an unlevered ETF/fund-wrapper strategy. It suggests BIL/cash was retained from prior fallback allocations while risky allocations accumulated on top.

## Suspicious Sample

{sample}
"""


def return_audit_md(findings: dict[str, Any]) -> str:
    return f"""# Return Calculation Audit

Result: `blocked_by_weighting_issue`

The code uses shifted weights for monthly momentum and static sleeves, which is directionally appropriate for no-lookahead handling. However, the shifted weights are downstream of the weight-accumulation defect, so reported returns, CAGR, drawdown, benchmark deltas, contribution scores, and labels cannot be trusted.

Breakout logic uses prior-close information to form same-day close-to-close exposure and appears less exposed to the monthly forward-fill bug, but the batch-level output remains non-interpretable until the shared methodology is fixed.

Return calculation issue found: `{findings['return_calculation_issue_found']}`
"""


def benchmark_audit_md(findings: dict[str, Any]) -> str:
    return f"""# Benchmark Alignment Audit

Result: `alignment_code_mostly_valid_but_interpretation_blocked`

Same-window benchmark alignment appears to be implemented by concatenating strategy returns with SPY/BIL or active-combo returns and dropping non-overlapping dates. I did not find a separate benchmark-window alignment defect.

However, because strategy returns are contaminated by invalid accumulated weights, the benchmark deltas and active VM/DSR contribution comparisons are not decision-grade.

Benchmark alignment issue found: `{findings['benchmark_alignment_issue_found']}`
"""


def scoring_audit_md(families: pd.DataFrame, findings: dict[str, Any]) -> str:
    marked = ", ".join(findings["deeper_research_families_marked"]) or "none"
    return f"""# Scoring And Labeling Audit

Result: `not_decision_grade`

High-return/high-drawdown rows were labeled as `research_signal_high_risk`, which is conceptually correct for the new research track. The problem is that the high-return evidence is methodologically contaminated by invalid exposure.

Families marked for deeper research by the batch: `{marked}`

Accepted deeper-research families after audit: `{findings['families_deeper_research_accepted_count']}`

The deeper-research flags are rejected for now. They may be reconsidered only after the weighting/cash methodology is repaired and the batch is rerun or diagnostically corrected under audit.
"""


def family_review_md(families: pd.DataFrame, findings: dict[str, Any]) -> str:
    lines = ["# Family Deeper Research Review", "", "Audit decision: `reject_current_deeper_research_flags`", ""]
    for _, row in families.iterrows():
        lines.extend(
            [
                f"## `{row['family_id']}`",
                "",
                f"- Batch deeper-research flag: `{row['deserves_deeper_research']}`",
                f"- Family status from batch: `{row['family_research_status']}`",
                f"- Audit accepted for deeper research now: `False`",
                "- Reason: batch-level exposure/cash methodology defect blocks interpretation.",
                "",
            ]
        )
    return "\n".join(lines)


def gld_review_md(findings: dict[str, Any]) -> str:
    return f"""# GLD / Macro Lineage Review

GLD/macro rows are marked `lineage_incomplete_research_only` in the batch output.

Lineage blocks deeper macro research: `{findings['gld_macro_lineage_blocks_deeper_research']}`

The batch did not formally reopen old GLD/GROR variants, and outputs remain non-promotable. If methodology is fixed and macro remains interesting, GLD/macro lineage recovery should still occur before any deeper macro-specific research decision.
"""


def non_promotable_md(findings: dict[str, Any]) -> str:
    return f"""# Non-Promotable Guardrail Review

Promotion eligibility all false: `{findings['promotion_eligibility_all_false']}`

Forbidden labels present: `{findings['forbidden_labels_present']}`

No paper-forward candidate, candidate_exhaustive candidate, promotion-review candidate, live-ready row, or real-money candidate was created by this audit.
"""


def methodology_validity_md(findings: dict[str, Any]) -> str:
    return f"""# Methodology Validity Review

Methodology valid enough for next research direction: `{findings['methodology_valid']}`

Blocking issue: `exposure_weighting_cash_bil_methodology_defect`

The saved batch results are useful as a defect-discovery artifact, but not reliable enough to decide the next research direction. The reported high-profit and deeper-research signals should not be accepted until the weighting/cash/BIL implementation is fixed.
"""


def turnover_md() -> str:
    return """# Trade Count / Turnover Audit

Result: `not_decision_grade`

Trade count and turnover are computed from weight changes. Because the weight matrix can accumulate stale allocations, turnover and trade-count outputs are not reliable for affected monthly momentum families. Static and breakout rows may be less affected, but the batch-level family conclusions should be treated as blocked until the shared weighting logic is repaired.
"""


def summary_md(findings: dict[str, Any]) -> str:
    return f"""# Profit-Oriented Research Batch V1 Audit Summary

Methodology valid: `{findings['methodology_valid']}`

Exposure/weighting issue found: `{findings['exposure_weighting_issue_found']}`

Cash/BIL issue found: `{findings['cash_bil_issue_found']}`

Return calculation issue found: `{findings['return_calculation_issue_found']}`

Scoring/labeling issue found: `{findings['scoring_labeling_issue_found']}`

Families accepted for deeper research now: `{findings['families_deeper_research_accepted_count']}`

Exact next action: `{findings['next_action']}`
"""


def next_action_md(next_action: str) -> str:
    return f"""# Profit Batch V1 Audit Next Action

Exact next action:

`{next_action}`

Do not run the next action in this audit task.
"""


def manifest(created_utc: str, output: Path, findings: dict[str, Any]) -> dict[str, Any]:
    return {
        "created_utc": created_utc,
        **MANIFEST_FLAGS,
        "evidence_path": str(output.resolve()),
        **findings,
    }


def consistency_check(m: dict[str, Any], output: Path) -> dict[str, Any]:
    required = {name: (output / name).exists() for name in REQUIRED_OUTPUT_FILES}
    check = {
        "audit_only_mode": m["profit_batch_v1_audit_only"] is True,
        "batch_id_audited": m["batch_id_audited"] == BATCH_ID,
        "no_new_research_batch": m["new_research_batch_run"] is False,
        "no_strategy_discovery": m["new_strategy_discovery_run"] is False,
        "no_new_backtests": m["new_backtests_run"] is False,
        "no_raw_data_metrics": m["new_performance_metrics_from_raw_data_computed"] is False,
        "no_provider_download": m["provider_download"] is False,
        "no_intraday_data": m["intraday_data_used"] is False,
        "no_broker_api": m["broker_api_called"] is False,
        "no_broker_orders": (
            m["broker_orders_submitted"] is False
            and m["broker_orders_cancelled"] is False
            and m["broker_orders_reconciled"] is False
        ),
        "no_live_orders": m["live_orders"] is False,
        "no_real_money": m["real_money_recommendation"] is False,
        "no_promotion_candidates": m["promotion_candidates_created"] is False,
        "no_paper_forward_activation": m["paper_forward_activation"] is False,
        "no_new_paper_forward_candidate": m["new_paper_forward_candidate_created"] is False,
        "no_candidate_exhaustive": m["candidate_exhaustive_run"] is False,
        "best_single_variant_not_promoted": m["best_single_variant_promoted"] is False,
        "research_outputs_remain_non_promotable": m["research_outputs_remain_non_promotable"] is True,
        "active_vm_preserved": m["active_vm_preserved"] is True,
        "active_dsr_preserved": m["active_dsr_preserved"] is True,
        "static_all_weather_control_only": m["static_all_weather_benchmark_control_only"] is True,
        "next_action_valid": m["next_action"] in VALID_NEXT_ACTIONS,
        "required_files_present": all(required.values()),
        "required_files": required,
    }
    check["consistency_passed"] = all(value is True for key, value in check.items() if key != "required_files")
    return check


def update_research_state(root: Path, created_utc: str, output: Path, m: dict[str, Any]) -> None:
    path = root / RESEARCH_STATE_PATH
    before = read_text(path)
    section = f"""## Latest Profit Batch V1 Audit

- Created UTC: `{created_utc}`
- Evidence path: `{output.resolve()}`
- Methodology valid: `{m['methodology_valid']}`
- Exposure/weighting issue found: `{m['exposure_weighting_issue_found']}`
- Cash/BIL issue found: `{m['cash_bil_issue_found']}`
- Families accepted for deeper research: `{m['families_deeper_research_accepted_count']}`
- Next action: `{m['next_action']}`
- No provider download, intraday data, broker/live action, promotion, candidate_exhaustive, paper-forward activation, or real-money recommendation occurred.
"""
    write_text(path, replace_or_append_section(before, "## Latest Profit Batch V1 Audit", section))


def run(root: Path = ROOT) -> dict[str, Any]:
    created = now_utc()
    output = root / OUTPUT_DIR
    output.mkdir(parents=True, exist_ok=True)
    artifacts = load_source_artifacts(root)
    findings = audit_findings(artifacts)
    m = manifest(created, output, findings)

    variants: pd.DataFrame = artifacts["variants"]
    families: pd.DataFrame = artifacts["families"]
    write_text(output / "profit_batch_v1_audit_summary.md", summary_md(findings))
    write_text(output / "methodology_validity_review.md", methodology_validity_md(findings))
    write_text(output / "exposure_and_weighting_audit.md", exposure_audit_md(variants, findings))
    write_text(output / "cash_bil_handling_audit.md", cash_audit_md(variants, findings))
    write_text(output / "return_calculation_audit.md", return_audit_md(findings))
    write_text(output / "trade_count_turnover_audit.md", turnover_md())
    write_text(output / "benchmark_alignment_audit.md", benchmark_audit_md(findings))
    write_text(output / "scoring_and_labeling_audit.md", scoring_audit_md(families, findings))
    write_text(output / "family_deeper_research_review.md", family_review_md(families, findings))
    write_text(output / "gld_macro_lineage_review.md", gld_review_md(findings))
    write_text(output / "non_promotable_guardrail_review.md", non_promotable_md(findings))
    write_text(output / "profit_batch_v1_audit_next_action.md", next_action_md(findings["next_action"]))
    write_json(output / "profit_batch_v1_audit_manifest.json", m)
    write_json(output / "profit_batch_v1_audit_consistency_check.json", {"consistency_passed": False})
    check = consistency_check(m, output)
    write_json(output / "profit_batch_v1_audit_consistency_check.json", check)
    update_research_state(root, created, output, m)
    return {**m, "consistency_passed": check["consistency_passed"], "output_dir": str(output.resolve())}


if __name__ == "__main__":
    result = run()
    print(
        json.dumps(
            {
                "output_dir": result["output_dir"],
                "methodology_valid": result["methodology_valid"],
                "exposure_weighting_issue_found": result["exposure_weighting_issue_found"],
                "cash_bil_issue_found": result["cash_bil_issue_found"],
                "next_action": result["next_action"],
                "consistency_passed": result["consistency_passed"],
            },
            indent=2,
        )
    )
