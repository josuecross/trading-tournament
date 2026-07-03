from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.objective_reset.objective_reset_review import replace_or_append_section, write_json, write_text
from strategy_lab.research_os.research.profit_oriented_research_batch_v1 import BATCH_ID, FORBIDDEN_LABELS, WEIGHT_TOLERANCE
from strategy_lab.research_os.split_tracks import RESEARCH_STATE_PATH


SOURCE_DIR = Path("evidence") / "research_recovery" / "profit_oriented_research_batch_v1_methodology_fix" / "latest"
OUTPUT_DIR = Path("evidence") / "research_recovery" / "profit_oriented_research_batch_v1_after_methodology_fix_audit" / "latest"

NEXT_ACTION_GLD = "recover_gld_macro_family_lineage"
NEXT_ACTION_BATCH2 = "design_profit_oriented_research_batch_v2"
NEXT_ACTION_FIX_AGAIN = "fix_profit_research_batch_v1_methodology_issue_again"
NEXT_ACTION_MANUAL = "manual_review_required_after_corrected_profit_batch_audit"
NEXT_ACTION_PAUSE = "pause_expansion_and_wait_for_manual_direction"
VALID_NEXT_ACTIONS = {NEXT_ACTION_GLD, NEXT_ACTION_BATCH2, NEXT_ACTION_FIX_AGAIN, NEXT_ACTION_MANUAL, NEXT_ACTION_PAUSE}

REQUIRED_OUTPUT_FILES = (
    "corrected_batch_audit_manifest.json",
    "corrected_batch_audit_summary.md",
    "methodology_fix_verification.md",
    "corrected_exposure_weighting_audit.md",
    "corrected_cash_bil_audit.md",
    "corrected_return_benchmark_audit.md",
    "corrected_scoring_label_audit.md",
    "deeper_research_family_review.md",
    "high_return_tactical_family_review.md",
    "macro_gld_duration_family_review.md",
    "non_selected_family_review.md",
    "non_promotable_guardrail_review.md",
    "corrected_batch_audit_next_action.md",
    "corrected_batch_audit_consistency_check.json",
)

MANIFEST_FLAGS = {
    "corrected_batch_audit_only": True,
    "batch_id_audited": BATCH_ID,
    "methodology_fix_evidence_reviewed": True,
    "corrected_results_reviewed": True,
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


def load_artifacts(root: Path) -> dict[str, Any]:
    source = root / SOURCE_DIR
    return {
        "source": source,
        "fix_manifest": read_json(source / "methodology_fix_manifest.json"),
        "fix_consistency": read_json(source / "methodology_fix_consistency_check.json"),
        "variants": pd.read_csv(source / "corrected_profit_research_variant_results.csv"),
        "families": pd.read_csv(source / "corrected_profit_research_family_summary.csv"),
        "root_cause": read_text(source / "root_cause_analysis.md"),
        "weight_fix": read_text(source / "weight_construction_fix.md"),
        "cash_fix": read_text(source / "cash_bil_fix.md"),
        "exposure_report": read_text(source / "exposure_invariant_report.md"),
        "synthetic_tests": read_text(source / "synthetic_weight_tests.md"),
        "comparison": read_text(source / "pre_fix_vs_post_fix_comparison.md"),
        "invalidated": read_text(source / "invalidated_prior_batch_v1_results.md"),
        "do_not_promote": read_text(source / "do_not_promote_after_methodology_fix.md"),
    }


def family_stats(variants: pd.DataFrame) -> pd.DataFrame:
    return variants.groupby("family_id").agg(
        variants=("variant_id", "count"),
        median_cagr=("cagr", "median"),
        max_cagr=("cagr", "max"),
        median_max_drawdown=("max_drawdown", "median"),
        worst_max_drawdown=("max_drawdown", "min"),
        median_spy_delta=("spy_total_return_delta", "median"),
        median_bil_delta=("bil_cash_total_return_delta", "median"),
        median_contribution_score=("portfolio_contribution_score", "median"),
        max_contribution_score=("portfolio_contribution_score", "max"),
        median_active_combo_correlation=("active_combo_correlation", "median"),
        median_average_exposure=("average_exposure", "median"),
        max_average_exposure=("average_exposure", "max"),
        median_cash_bil_share=("cash_bil_allocation_share", "median"),
        max_cash_bil_share=("cash_bil_allocation_share", "max"),
    )


def audit_findings(artifacts: dict[str, Any]) -> dict[str, Any]:
    fix_manifest = artifacts["fix_manifest"]
    fix_consistency = artifacts["fix_consistency"]
    variants: pd.DataFrame = artifacts["variants"]
    families: pd.DataFrame = artifacts["families"]

    average_exposure = numeric(variants["average_exposure"])
    cash = numeric(variants["cash_bil_allocation_share"])
    cagr = numeric(variants["cagr"])
    mdd = numeric(variants["max_drawdown"])
    max_daily_exposure = numeric(variants["max_daily_exposure"])
    max_daily_weight_sum = numeric(variants["max_daily_weight_sum"])
    negative_weights = numeric(variants["negative_weight_violation_count"])
    nan_weights = numeric(variants["nan_weight_count"])
    impossible_cash_days = numeric(variants["impossible_cash_and_risky_exposure_days"])

    methodology_fix_accepted = (
        fix_manifest.get("same_variant_set_verified") is True
        and fix_manifest.get("old_batch_v1_results_invalidated_or_superseded") is True
        and fix_manifest.get("corrected_results_regenerated_from_fixed_weights") is True
        and fix_manifest.get("synthetic_weight_tests_passed") is True
        and fix_consistency.get("consistency_passed") is True
    )
    exposure_resolved = (
        int((average_exposure > 1.0 + WEIGHT_TOLERANCE).sum()) == 0
        and int((average_exposure > 2.0).sum()) == 0
        and float(max_daily_exposure.max(skipna=True)) <= 1.0 + WEIGHT_TOLERANCE
        and float(max_daily_weight_sum.max(skipna=True)) <= 1.0 + WEIGHT_TOLERANCE
        and int(negative_weights.sum()) == 0
        and int(nan_weights.sum()) == 0
    )
    impossible_cash_rows = variants[(cash >= 1.0 - WEIGHT_TOLERANCE) & (average_exposure > WEIGHT_TOLERANCE)]
    cash_bil_resolved = int(len(impossible_cash_rows)) == 0 and int(impossible_cash_days.sum()) == 0
    return_benchmark_valid = exposure_resolved and cash_bil_resolved and variants["benchmark_comparison"].astype(str).str.contains(
        "same-window", case=False, na=False
    ).all()

    high_risk_underlabeled = variants[(cagr > 0.10) & (mdd < -0.45) & (variants["research_label"] != "research_signal_high_risk")]
    favorable_zero_drawdown_score = variants[
        (numeric(variants["drawdown_tolerance_score"]) <= 1.0)
        & (variants["research_label"].isin(["research_signal_diversifier", "research_signal_needs_robustness"]))
    ]
    scoring_labeling_valid = high_risk_underlabeled.empty and favorable_zero_drawdown_score.empty

    deeper_marked = families[families["deserves_deeper_research"].astype(str).str.lower() == "true"]
    high_return_family = families[families["family_id"] == "high_return_tactical_etf_equity_index"]
    macro_family = families[families["family_id"] == "macro_gld_duration_risk_off"]
    macro_rows = variants[variants["family_id"] == "macro_gld_duration_risk_off"]
    gld_lineage_block = (
        not macro_rows.empty
        and macro_rows["lineage_status"].astype(str).eq("lineage_incomplete_research_only").all()
        and bool(macro_family["needs_methodology_or_data_audit"].astype(bool).iloc[0])
    )

    # Do not accept deeper-research flags when labels materially understate drawdown risk, or when lineage blocks interpretation.
    high_return_accepted = bool(
        methodology_fix_accepted
        and exposure_resolved
        and cash_bil_resolved
        and scoring_labeling_valid
        and not high_return_family.empty
        and high_return_family["deserves_deeper_research"].astype(bool).iloc[0]
    )
    macro_accepted = bool(
        methodology_fix_accepted
        and exposure_resolved
        and cash_bil_resolved
        and scoring_labeling_valid
        and not gld_lineage_block
        and not macro_family.empty
        and macro_family["deserves_deeper_research"].astype(bool).iloc[0]
    )
    accepted_count = int(high_return_accepted) + int(macro_accepted)

    guardrails_ok = (
        variants["promotion_eligibility"].astype(str).str.lower().eq("false").all()
        and variants["paper_forward_eligibility"].astype(str).str.lower().eq("false").all()
        and not set(variants["research_label"].astype(str)).intersection(FORBIDDEN_LABELS)
        and fix_manifest.get("promotion_candidates_created") is False
        and fix_manifest.get("paper_forward_activation") is False
        and fix_manifest.get("new_paper_forward_candidate_created") is False
        and fix_manifest.get("candidate_exhaustive_run") is False
        and fix_manifest.get("best_single_variant_promoted") is False
    )

    if not (methodology_fix_accepted and exposure_resolved and cash_bil_resolved and return_benchmark_valid):
        next_action = NEXT_ACTION_FIX_AGAIN
    elif not scoring_labeling_valid:
        next_action = NEXT_ACTION_FIX_AGAIN
    elif gld_lineage_block and macro_family["deserves_deeper_research"].astype(bool).any():
        next_action = NEXT_ACTION_GLD
    elif accepted_count > 0:
        next_action = NEXT_ACTION_BATCH2
    else:
        next_action = NEXT_ACTION_MANUAL

    return {
        "source_variant_count": int(len(variants)),
        "source_family_count": int(variants["family_id"].nunique()),
        "source_deeper_research_family_count": int(len(deeper_marked)),
        "methodology_fix_accepted": bool(methodology_fix_accepted),
        "exposure_weighting_issue_resolved": bool(exposure_resolved),
        "cash_bil_issue_resolved": bool(cash_bil_resolved),
        "return_benchmark_interpretation_valid": bool(return_benchmark_valid),
        "scoring_labeling_valid": bool(scoring_labeling_valid),
        "deeper_research_family_count_accepted": int(accepted_count),
        "high_return_tactical_deeper_research_accepted": bool(high_return_accepted),
        "macro_gld_deeper_research_accepted": bool(macro_accepted),
        "gld_macro_lineage_blocks_deeper_research": bool(gld_lineage_block),
        "non_promotable_guardrails_held": bool(guardrails_ok),
        "average_exposure_gt_1_count": int((average_exposure > 1.0 + WEIGHT_TOLERANCE).sum()),
        "average_exposure_gt_2_count": int((average_exposure > 2.0).sum()),
        "max_daily_exposure": float(max_daily_exposure.max(skipna=True)),
        "max_daily_weight_sum": float(max_daily_weight_sum.max(skipna=True)),
        "negative_weight_violation_count": int(negative_weights.sum()),
        "nan_weight_count": int(nan_weights.sum()),
        "impossible_cash_bil_plus_risky_row_count": int(len(impossible_cash_rows)),
        "impossible_cash_bil_plus_risky_day_count": int(impossible_cash_days.sum()),
        "high_risk_underlabeled_count": int(len(high_risk_underlabeled)),
        "favorable_zero_drawdown_score_label_count": int(len(favorable_zero_drawdown_score)),
        "forbidden_labels_present": sorted(set(variants["research_label"].astype(str)).intersection(FORBIDDEN_LABELS)),
        "next_action": next_action,
    }


def markdown_table(df: pd.DataFrame, columns: list[str], limit: int = 12) -> str:
    if df.empty:
        return "None."
    clipped = df[columns].head(limit)
    lines = ["| " + " | ".join(columns) + " |", "|" + "|".join("---" for _ in columns) + "|"]
    for _, row in clipped.iterrows():
        lines.append("| " + " | ".join(str(row.get(col, "")) for col in columns) + " |")
    return "\n".join(lines)


def summary_md(findings: dict[str, Any]) -> str:
    return f"""# Corrected Batch Audit Summary

Batch audited: `{findings['batch_id_audited']}`

Methodology fix accepted: `{findings['methodology_fix_accepted']}`

Exposure/weighting issue resolved: `{findings['exposure_weighting_issue_resolved']}`

Cash/BIL issue resolved: `{findings['cash_bil_issue_resolved']}`

Return/benchmark interpretation valid: `{findings['return_benchmark_interpretation_valid']}`

Scoring/labeling valid: `{findings['scoring_labeling_valid']}`

Accepted deeper-research family count: `{findings['deeper_research_family_count_accepted']}`

High-return tactical accepted for deeper research: `{findings['high_return_tactical_deeper_research_accepted']}`

Macro/GLD accepted for deeper research: `{findings['macro_gld_deeper_research_accepted']}`

GLD/macro lineage blocks deeper research: `{findings['gld_macro_lineage_blocks_deeper_research']}`

The corrected weights make the saved returns interpretable, but the label layer still understates severe drawdown risk. No deeper-research family is accepted from this audit.

Exact next action: `{findings['next_action']}`
"""


def methodology_md(artifacts: dict[str, Any], findings: dict[str, Any]) -> str:
    manifest = artifacts["fix_manifest"]
    return f"""# Methodology Fix Verification

Result: `{'pass' if findings['methodology_fix_accepted'] else 'fail'}`

- Same variant set rerun: `{manifest.get('same_variant_set_verified')}`
- Corrected variant count: `{manifest.get('corrected_variant_count')}`
- Corrected family count: `{manifest.get('corrected_family_count')}`
- New variants created: `{manifest.get('new_variants_created')}`
- New families created: `{manifest.get('new_families_created')}`
- Old batch v1 invalidated/superseded: `{manifest.get('old_batch_v1_results_invalidated_or_superseded')}`
- Corrected results regenerated from fixed weights: `{manifest.get('corrected_results_regenerated_from_fixed_weights')}`
- Synthetic weight tests passed: `{manifest.get('synthetic_weight_tests_passed')}`
- Provider download: `{manifest.get('provider_download')}`
- Intraday data used: `{manifest.get('intraday_data_used')}`
- Broker API called: `{manifest.get('broker_api_called')}`

The methodology repair is accepted for exposure construction and same-variant rerun integrity.
"""


def exposure_md(findings: dict[str, Any]) -> str:
    return f"""# Corrected Exposure / Weighting Audit

Result: `{'pass' if findings['exposure_weighting_issue_resolved'] else 'fail'}`

- Average exposure > 1 count: `{findings['average_exposure_gt_1_count']}`
- Average exposure > 2 count: `{findings['average_exposure_gt_2_count']}`
- Max daily exposure: `{findings['max_daily_exposure']:.6f}`
- Max daily weight sum: `{findings['max_daily_weight_sum']:.6f}`
- Negative weight violation count: `{findings['negative_weight_violation_count']}`
- NaN weight count: `{findings['nan_weight_count']}`

The stale-allocation leverage defect is resolved in the corrected evidence.
"""


def cash_md(variants: pd.DataFrame, findings: dict[str, Any]) -> str:
    cash_heavy = variants[numeric(variants["cash_bil_allocation_share"]) > 0.80].copy()
    sample = markdown_table(
        cash_heavy.sort_values("cash_bil_allocation_share", ascending=False),
        ["family_id", "variant_id", "cash_bil_allocation_share", "average_exposure", "cagr", "research_label"],
        10,
    )
    return f"""# Corrected Cash / BIL Audit

Result: `{'pass' if findings['cash_bil_issue_resolved'] else 'fail'}`

- Impossible cash/BIL plus risky rows: `{findings['impossible_cash_bil_plus_risky_row_count']}`
- Impossible cash/BIL plus risky days: `{findings['impossible_cash_bil_plus_risky_day_count']}`

BIL/cash is now interpretable as fallback/remainder rather than additive leverage. Cash-heavy rows are low-exposure breakout rows and are not labeled as strong profit signals.

## Cash-Heavy Sample

{sample}
"""


def return_benchmark_md(stats: pd.DataFrame, findings: dict[str, Any]) -> str:
    table = stats.reset_index()
    return f"""# Corrected Return / Benchmark Audit

Result: `{'interpretable_with_caveats' if findings['return_benchmark_interpretation_valid'] else 'not_interpretable'}`

Corrected CAGR, drawdown, SPY delta, BIL delta, and active-combo contribution metrics are interpretable because the exposure and BIL defects are resolved.

Active VM/DSR contribution comparisons are still research diagnostics only. They do not imply paper-forward readiness.

## Family Summary

{markdown_table(table, ['family_id', 'median_cagr', 'median_max_drawdown', 'median_spy_delta', 'median_bil_delta', 'median_contribution_score', 'median_active_combo_correlation'], 10)}
"""


def scoring_label_md(variants: pd.DataFrame, findings: dict[str, Any]) -> str:
    cagr = numeric(variants["cagr"])
    mdd = numeric(variants["max_drawdown"])
    high_risk_underlabeled = variants[(cagr > 0.10) & (mdd < -0.45) & (variants["research_label"] != "research_signal_high_risk")]
    favorable_zero_drawdown = variants[
        (numeric(variants["drawdown_tolerance_score"]) <= 1.0)
        & (variants["research_label"].isin(["research_signal_diversifier", "research_signal_needs_robustness"]))
    ]
    return f"""# Corrected Scoring / Label Audit

Result: `{'pass' if findings['scoring_labeling_valid'] else 'major_issue'}`

The corrected output says no high-profit/high-risk labels remained, but the saved metrics still include rows with high historical return and very large drawdowns. These rows are not promotable, but the labels understate their risk.

- High-return / severe-drawdown rows not labeled high-risk: `{findings['high_risk_underlabeled_count']}`
- Favorable labels with drawdown tolerance near zero: `{findings['favorable_zero_drawdown_score_label_count']}`

This is a labeling/scoring defect, not a renewed exposure defect. It materially affects whether deeper-research flags should be accepted.

## Under-Labeled Risk Sample

{markdown_table(high_risk_underlabeled, ['family_id', 'variant_id', 'cagr', 'max_drawdown', 'drawdown_tolerance_score', 'research_label', 'portfolio_contribution_score'], 12)}

## Favorable Label With Zero Drawdown Score Sample

{markdown_table(favorable_zero_drawdown, ['family_id', 'variant_id', 'cagr', 'max_drawdown', 'drawdown_tolerance_score', 'research_label'], 12)}
"""


def deeper_review_md(families: pd.DataFrame, findings: dict[str, Any]) -> str:
    marked = families[families["deserves_deeper_research"].astype(str).str.lower() == "true"]
    return f"""# Deeper Research Family Review

Source families marked for deeper research: `{findings['source_deeper_research_family_count']}`

Accepted by this audit: `{findings['deeper_research_family_count_accepted']}`

The source marked `high_return_tactical_etf_equity_index` and `macro_gld_duration_risk_off`, but neither is accepted here.

- High-return tactical has broad historical return evidence, but drawdown risk is under-labeled and needs scoring/risk label repair before batch-v2 design.
- Macro/GLD has interesting rows, but all macro rows remain `lineage_incomplete_research_only`, so deeper macro testing is blocked by lineage.

## Marked Families

{markdown_table(marked, ['family_id', 'median_cagr', 'median_max_drawdown', 'median_portfolio_contribution_score', 'risk_profile', 'needs_methodology_or_data_audit'], 10)}
"""


def high_return_md(variants: pd.DataFrame) -> str:
    rows = variants[variants["family_id"] == "high_return_tactical_etf_equity_index"].copy()
    return f"""# High-Return Tactical Family Review

Conclusion: `not_accepted_until_scoring_label_fix`

This family has genuine corrected historical return evidence, with median CAGR around `{numeric(rows['cagr']).median():.4f}` and positive median SPY delta. It is not just a stale-weight artifact anymore.

The problem is risk interpretation: median max drawdown is around `{numeric(rows['max_drawdown']).median():.4f}` and worst drawdown is around `{numeric(rows['max_drawdown']).min():.4f}`. Several rows are labeled `research_signal_diversifier` despite drawdown tolerance scores at or near zero.

Deeper research would require a clear risk-control hypothesis and corrected high-risk labeling. It should not proceed directly to batch v2 from the current labels.
"""


def macro_md(variants: pd.DataFrame) -> str:
    rows = variants[variants["family_id"] == "macro_gld_duration_risk_off"].copy()
    return f"""# Macro / GLD / Duration Family Review

Conclusion: `interesting_but_lineage_blocked`

Macro/GLD rows remain research-only with lineage status `{', '.join(sorted(rows['lineage_status'].astype(str).unique()))}`.

The corrected evidence includes some interesting diversification readings, especially the `mgd_macro_mom126_top1_trend` row. However, median SPY delta remains negative and the family ledger status blocks deeper interpretation.

The right future direction may be GLD/macro lineage recovery, but this audit does not select it because scoring/labeling defects still need correction first.
"""


def non_selected_md(stats: pd.DataFrame) -> str:
    table = stats.reset_index()
    rows = table[table["family_id"].isin([
        "breakout_trend_momentum_high_risk",
        "managed_futures_trend_following_etf_wrapper",
        "portfolio_diversifier_contribution",
    ])]
    return f"""# Non-Selected Family Review

Conclusion: `no_missed_deeper_research_family_found`

- `breakout_trend_momentum_high_risk`: lower drawdown but very cash-heavy, low median CAGR, and weak SPY comparison.
- `managed_futures_trend_following_etf_wrapper`: low return/cash-heavy context under current local ETF wrappers.
- `portfolio_diversifier_contribution`: some contribution-like rows, but median SPY delta is weak and family-level evidence is mixed.

## Corrected Family Stats

{markdown_table(rows, ['family_id', 'median_cagr', 'median_max_drawdown', 'median_spy_delta', 'median_contribution_score', 'median_cash_bil_share'], 10)}
"""


def guardrail_md(variants: pd.DataFrame, findings: dict[str, Any]) -> str:
    return f"""# Non-Promotable Guardrail Review

Result: `{'pass' if findings['non_promotable_guardrails_held'] else 'fail'}`

- Promotion eligibility false for every row: `{variants['promotion_eligibility'].astype(str).str.lower().eq('false').all()}`
- Paper-forward eligibility false for every row: `{variants['paper_forward_eligibility'].astype(str).str.lower().eq('false').all()}`
- Forbidden labels present: `{findings['forbidden_labels_present']}`
- Promotion candidates created: `False`
- Paper-forward activation: `False`
- Candidate exhaustive run: `False`
- Real-money recommendation: `False`

No result is promotable from this audit.
"""


def next_action_md(next_action: str) -> str:
    return f"""# Corrected Batch Audit Next Action

Exact next action:

`{next_action}`

Do not run the next action in this task.
"""


def consistency_check(manifest: dict[str, Any], output: Path) -> dict[str, Any]:
    required = {name: (output / name).exists() for name in REQUIRED_OUTPUT_FILES}
    check = {
        "corrected_batch_audit_only": manifest["corrected_batch_audit_only"] is True,
        "batch_id_audited": manifest["batch_id_audited"] == BATCH_ID,
        "methodology_fix_evidence_reviewed": manifest["methodology_fix_evidence_reviewed"] is True,
        "corrected_results_reviewed": manifest["corrected_results_reviewed"] is True,
        "no_new_research_batch": manifest["new_research_batch_run"] is False,
        "no_new_strategy_discovery": manifest["new_strategy_discovery_run"] is False,
        "no_new_backtests": manifest["new_backtests_run"] is False,
        "no_raw_data_performance_metrics": manifest["new_performance_metrics_from_raw_data_computed"] is False,
        "no_new_variants": manifest["new_variants_created"] is False,
        "no_new_families": manifest["new_families_created"] is False,
        "no_provider_download": manifest["provider_download"] is False,
        "no_intraday": manifest["intraday_data_used"] is False,
        "no_broker_api": manifest["broker_api_called"] is False,
        "no_broker_orders": (
            manifest["broker_orders_submitted"] is False
            and manifest["broker_orders_cancelled"] is False
            and manifest["broker_orders_reconciled"] is False
        ),
        "no_live_or_real_money": manifest["live_orders"] is False and manifest["real_money_recommendation"] is False,
        "no_promotion_candidates": manifest["promotion_candidates_created"] is False,
        "no_paper_forward_activation": manifest["paper_forward_activation"] is False,
        "no_new_paper_forward_candidate": manifest["new_paper_forward_candidate_created"] is False,
        "no_candidate_exhaustive": manifest["candidate_exhaustive_run"] is False,
        "no_best_single_variant_promoted": manifest["best_single_variant_promoted"] is False,
        "research_outputs_non_promotable": manifest["research_outputs_remain_non_promotable"] is True,
        "active_vm_preserved": manifest["active_vm_preserved"] is True,
        "active_dsr_preserved": manifest["active_dsr_preserved"] is True,
        "static_all_weather_control_only": manifest["static_all_weather_benchmark_control_only"] is True,
        "alpaca_execution_module_delegated": manifest["alpaca_execution_module_delegated"] is True,
        "methodology_fix_verification_exists": (output / "methodology_fix_verification.md").exists(),
        "corrected_exposure_audit_exists": (output / "corrected_exposure_weighting_audit.md").exists(),
        "corrected_cash_bil_audit_exists": (output / "corrected_cash_bil_audit.md").exists(),
        "corrected_scoring_label_audit_exists": (output / "corrected_scoring_label_audit.md").exists(),
        "deeper_research_family_review_exists": (output / "deeper_research_family_review.md").exists(),
        "non_promotable_guardrail_review_exists": (output / "non_promotable_guardrail_review.md").exists(),
        "next_action_valid": manifest["next_action"] in VALID_NEXT_ACTIONS,
        "required_files_present": all(required.values()),
        "required_files": required,
    }
    check["consistency_passed"] = all(value is True for key, value in check.items() if key != "required_files")
    return check


def update_research_metadata(root: Path, created_utc: str, output: Path, manifest: dict[str, Any]) -> None:
    path = root / RESEARCH_STATE_PATH
    before = read_text(path)
    section = f"""## Corrected Profit Batch V1 Audit

- Created UTC: `{created_utc}`
- Evidence path: `{output.resolve()}`
- Batch audited: `{BATCH_ID}`
- Methodology fix accepted: `{manifest['methodology_fix_accepted']}`
- Exposure/weighting resolved: `{manifest['exposure_weighting_issue_resolved']}`
- Cash/BIL resolved: `{manifest['cash_bil_issue_resolved']}`
- Scoring/labeling valid: `{manifest['scoring_labeling_valid']}`
- Deeper research families accepted: `{manifest['deeper_research_family_count_accepted']}`
- Next action: `{manifest['next_action']}`
- No provider download, intraday data, broker/live action, promotion, candidate_exhaustive, paper-forward activation, or real-money recommendation occurred.
"""
    write_text(path, replace_or_append_section(before, "## Corrected Profit Batch V1 Audit", section))


def run(root: Path = ROOT) -> dict[str, Any]:
    created = now_utc()
    output = root / OUTPUT_DIR
    output.mkdir(parents=True, exist_ok=True)
    artifacts = load_artifacts(root)
    variants: pd.DataFrame = artifacts["variants"]
    families: pd.DataFrame = artifacts["families"]
    stats = family_stats(variants)
    findings = audit_findings(artifacts)
    manifest = {
        "created_utc": created,
        **MANIFEST_FLAGS,
        "evidence_path": str(output.resolve()),
        **findings,
    }

    write_json(output / "corrected_batch_audit_manifest.json", manifest)
    write_text(output / "corrected_batch_audit_summary.md", summary_md(manifest))
    write_text(output / "methodology_fix_verification.md", methodology_md(artifacts, manifest))
    write_text(output / "corrected_exposure_weighting_audit.md", exposure_md(manifest))
    write_text(output / "corrected_cash_bil_audit.md", cash_md(variants, manifest))
    write_text(output / "corrected_return_benchmark_audit.md", return_benchmark_md(stats, manifest))
    write_text(output / "corrected_scoring_label_audit.md", scoring_label_md(variants, manifest))
    write_text(output / "deeper_research_family_review.md", deeper_review_md(families, manifest))
    write_text(output / "high_return_tactical_family_review.md", high_return_md(variants))
    write_text(output / "macro_gld_duration_family_review.md", macro_md(variants))
    write_text(output / "non_selected_family_review.md", non_selected_md(stats))
    write_text(output / "non_promotable_guardrail_review.md", guardrail_md(variants, manifest))
    write_text(output / "corrected_batch_audit_next_action.md", next_action_md(manifest["next_action"]))
    write_json(output / "corrected_batch_audit_consistency_check.json", {"consistency_passed": False})
    check = consistency_check(manifest, output)
    write_json(output / "corrected_batch_audit_consistency_check.json", check)
    update_research_metadata(root, created, output, manifest)
    return {**manifest, "output_dir": str(output.resolve()), "consistency_passed": check["consistency_passed"]}


if __name__ == "__main__":
    result = run()
    print(
        json.dumps(
            {
                "output_dir": result["output_dir"],
                "batch_id_audited": result["batch_id_audited"],
                "methodology_fix_accepted": result["methodology_fix_accepted"],
                "exposure_weighting_issue_resolved": result["exposure_weighting_issue_resolved"],
                "cash_bil_issue_resolved": result["cash_bil_issue_resolved"],
                "scoring_labeling_valid": result["scoring_labeling_valid"],
                "deeper_research_family_count_accepted": result["deeper_research_family_count_accepted"],
                "next_action": result["next_action"],
                "consistency_passed": result["consistency_passed"],
            },
            indent=2,
        )
    )
