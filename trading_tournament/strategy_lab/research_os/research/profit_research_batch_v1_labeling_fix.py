from __future__ import annotations

import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.objective_reset.objective_reset_review import replace_or_append_section, write_json, write_text
from strategy_lab.research_os.research.profit_oriented_research_batch_v1 import (
    ALLOWED_LABELS,
    BATCH_ID,
    DIVERSIFIER_CORRELATION_THRESHOLD,
    DIVERSIFIER_SCORE_THRESHOLD,
    EXTREME_DRAWDOWN_THRESHOLD,
    HIGH_RETURN_CAGR_THRESHOLD,
    NEAR_ZERO_DRAWDOWN_TOLERANCE_THRESHOLD,
    SEVERE_DRAWDOWN_THRESHOLD,
    WEIGHT_TOLERANCE,
    label_row,
)
from strategy_lab.research_os.split_tracks import RESEARCH_STATE_PATH


SOURCE_DIR = Path("evidence") / "research_recovery" / "profit_oriented_research_batch_v1_methodology_fix" / "latest"
AUDIT_DIR = Path("evidence") / "research_recovery" / "profit_oriented_research_batch_v1_after_methodology_fix_audit" / "latest"
OUTPUT_DIR = Path("evidence") / "research_recovery" / "profit_oriented_research_batch_v1_labeling_fix" / "latest"

NEXT_ACTION_AUDIT = "audit_profit_oriented_research_batch_v1_labeling_fix"
NEXT_ACTION_FIX_AGAIN = "fix_profit_research_batch_v1_labeling_issue_again"
NEXT_ACTION_GLD = "recover_gld_macro_family_lineage"
NEXT_ACTION_BATCH2 = "design_profit_oriented_research_batch_v2"
NEXT_ACTION_MANUAL = "manual_review_required_after_labeling_fix"
VALID_NEXT_ACTIONS = {NEXT_ACTION_AUDIT, NEXT_ACTION_FIX_AGAIN, NEXT_ACTION_GLD, NEXT_ACTION_BATCH2, NEXT_ACTION_MANUAL}

RISK_LABELS = {
    "research_signal_high_risk",
    "research_signal_risk_control_required",
    "research_signal_high_risk_diversifier",
}
FAVORABLE_LABELS = {
    "research_signal_diversifier",
    "research_signal_needs_robustness",
    "research_signal_promising",
}

REQUIRED_OUTPUT_FILES = (
    "labeling_fix_manifest.json",
    "labeling_fix_summary.md",
    "label_policy_v1.md",
    "labeling_root_cause.md",
    "corrected_label_variant_results.csv",
    "corrected_label_family_summary.csv",
    "high_return_high_drawdown_relabeling.md",
    "diversifier_label_validation.md",
    "macro_gld_lineage_label_status.md",
    "pre_label_fix_vs_post_label_fix_comparison.md",
    "deeper_research_flags_after_label_fix.md",
    "do_not_promote_after_labeling_fix.md",
    "labeling_fix_next_action.md",
    "labeling_fix_consistency_check.json",
)

MANIFEST_FLAGS = {
    "labeling_fix_only": True,
    "batch_id_fixed": BATCH_ID,
    "uses_corrected_methodology_outputs": True,
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
    "exposure_methodology_reopened": False,
    "diversifier_label_requires_risk_check": True,
}


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return ""
    if isinstance(value, bool):
        return str(value)
    return str(value)


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: csv_value(row.get(field, "")) for field in fieldnames})


def load_source(root: Path) -> dict[str, Any]:
    source = root / SOURCE_DIR
    return {
        "source": source,
        "methodology_manifest": read_json(source / "methodology_fix_manifest.json"),
        "methodology_consistency": read_json(source / "methodology_fix_consistency_check.json"),
        "methodology_rows": pd.read_csv(source / "corrected_profit_research_variant_results.csv"),
        "methodology_families": pd.read_csv(source / "corrected_profit_research_family_summary.csv"),
        "audit_manifest": read_json(root / AUDIT_DIR / "corrected_batch_audit_manifest.json"),
        "audit_scoring_label": read_text(root / AUDIT_DIR / "corrected_scoring_label_audit.md"),
    }


def row_dicts(df: pd.DataFrame) -> list[dict[str, Any]]:
    return df.where(pd.notna(df), "").to_dict(orient="records")


def relabel_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    relabeled: list[dict[str, Any]] = []
    for row in rows:
        updated = dict(row)
        updated["source_methodology_research_label"] = str(updated.get("research_label", ""))
        updated["pre_label_fix_research_label"] = legacy_label_row(updated)
        updated["research_label"] = label_row(updated)
        updated["label_policy_version"] = "profit_research_label_policy_v1"
        updated["risk_classification"] = risk_classification(updated)
        updated["labeling_notes"] = labeling_notes(updated)
        updated["deeper_research_eligible_after_label_fix"] = False
        relabeled.append(updated)
    return relabeled


def legacy_label_row(row: dict[str, Any]) -> str:
    cagr = float(row.get("cagr", 0.0) or 0.0)
    mdd = float(row.get("max_drawdown", 0.0) or 0.0)
    hist = float(row.get("historical_profit_score", 0.0) or 0.0)
    risk = float(row.get("risk_adjusted_score", 0.0) or 0.0)
    contrib = float(row.get("portfolio_contribution_score", 0.0) or 0.0)
    corr = row.get("active_combo_correlation", float("nan"))
    if isinstance(corr, str) or corr == "":
        corr = float("nan")
    if not math.isnan(float(corr)) and float(corr) > 0.92 and contrib < 45:
        return "research_signal_duplicate"
    if hist >= 65 and mdd < -0.25:
        return "research_signal_high_risk"
    if contrib >= 58 and (math.isnan(float(corr)) or float(corr) < 0.80):
        return "research_signal_diversifier"
    if hist >= 62 and risk >= 45:
        return "research_signal_promising"
    if cagr > 0.07 and risk < 35:
        return "research_signal_needs_robustness"
    if cagr < 0.0 and mdd < -0.30:
        return "research_signal_rejected"
    return "research_signal_weak"


def risk_classification(row: dict[str, Any]) -> str:
    cagr = float(row.get("cagr", 0.0) or 0.0)
    mdd = float(row.get("max_drawdown", 0.0) or 0.0)
    label = str(row.get("research_label", ""))
    if label == "research_signal_lineage_blocked":
        return "lineage_blocked"
    if mdd <= EXTREME_DRAWDOWN_THRESHOLD and cagr >= HIGH_RETURN_CAGR_THRESHOLD:
        return "extreme_drawdown_high_return"
    if mdd <= SEVERE_DRAWDOWN_THRESHOLD:
        return "severe_drawdown"
    if label == "research_signal_diversifier":
        return "diversifier_with_risk_check"
    return "ordinary_research_risk"


def labeling_notes(row: dict[str, Any]) -> str:
    label = str(row.get("research_label", ""))
    cagr = float(row.get("cagr", 0.0) or 0.0)
    mdd = float(row.get("max_drawdown", 0.0) or 0.0)
    lineage = str(row.get("lineage_status", ""))
    if label == "research_signal_lineage_blocked":
        return "macro_or_gld_lineage_incomplete_research_only"
    if label in RISK_LABELS:
        return "high_return_or_severe_drawdown_requires_risk_control_before_deeper_research"
    if label == "research_signal_diversifier":
        return "diversifier_label_requires_contribution_risk_and_active_combo_checks"
    if cagr < 0.03 or mdd <= -0.25:
        return "weak_or_mixed_profile"
    if lineage == "lineage_incomplete_research_only":
        return "lineage_incomplete"
    return "ordinary_research_label"


def high_return_severe_underlabeled_count(df: pd.DataFrame, label_column: str) -> int:
    cagr = numeric(df["cagr"])
    mdd = numeric(df["max_drawdown"])
    labels = df[label_column].astype(str)
    mask = (cagr >= HIGH_RETURN_CAGR_THRESHOLD) & (mdd <= SEVERE_DRAWDOWN_THRESHOLD) & ~labels.isin(RISK_LABELS)
    return int(mask.sum())


def favorable_zero_drawdown_label_count(df: pd.DataFrame, label_column: str) -> int:
    drawdown_score = numeric(df["drawdown_tolerance_score"])
    labels = df[label_column].astype(str)
    return int(((drawdown_score <= NEAR_ZERO_DRAWDOWN_TOLERANCE_THRESHOLD) & labels.isin(FAVORABLE_LABELS)).sum())


def invalid_diversifier_count(df: pd.DataFrame, label_column: str) -> int:
    labels = df[label_column].astype(str)
    mdd = numeric(df["max_drawdown"])
    drawdown_score = numeric(df["drawdown_tolerance_score"])
    contrib = numeric(df["portfolio_contribution_score"])
    corr = numeric(df["active_combo_correlation"])
    active_combo_delta = numeric(df["active_combo_blend_total_return_delta"])
    mask = labels.eq("research_signal_diversifier") & (
        (mdd <= SEVERE_DRAWDOWN_THRESHOLD)
        | (drawdown_score <= NEAR_ZERO_DRAWDOWN_TOLERANCE_THRESHOLD)
        | (contrib < DIVERSIFIER_SCORE_THRESHOLD)
        | (corr >= DIVERSIFIER_CORRELATION_THRESHOLD)
        | (active_combo_delta <= 0.0)
    )
    return int(mask.sum())


def exposure_invariants_valid(df: pd.DataFrame) -> bool:
    average_exposure = numeric(df["average_exposure"])
    max_daily_exposure = numeric(df["max_daily_exposure"])
    max_daily_weight_sum = numeric(df["max_daily_weight_sum"])
    negative_weights = numeric(df["negative_weight_violation_count"])
    nan_weights = numeric(df["nan_weight_count"])
    impossible_cash_days = numeric(df["impossible_cash_and_risky_exposure_days"])
    return (
        int((average_exposure > 1.0 + WEIGHT_TOLERANCE).sum()) == 0
        and float(max_daily_exposure.max(skipna=True)) <= 1.0 + WEIGHT_TOLERANCE
        and float(max_daily_weight_sum.max(skipna=True)) <= 1.0 + WEIGHT_TOLERANCE
        and int(negative_weights.sum()) == 0
        and int(nan_weights.sum()) == 0
        and int(impossible_cash_days.sum()) == 0
    )


def cash_bil_invariants_valid(df: pd.DataFrame) -> bool:
    average_exposure = numeric(df["average_exposure"])
    cash = numeric(df["cash_bil_allocation_share"])
    impossible_rows = df[(cash >= 1.0 - WEIGHT_TOLERANCE) & (average_exposure > WEIGHT_TOLERANCE)]
    return exposure_invariants_valid(df) and impossible_rows.empty


def macro_lineage_preserved(df: pd.DataFrame) -> bool:
    macro = df[df["family_id"] == "macro_gld_duration_risk_off"]
    return not macro.empty and macro["lineage_status"].astype(str).eq("lineage_incomplete_research_only").all()


def family_summary(df: pd.DataFrame, source_families: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for family_id, group in df.groupby("family_id", sort=True):
        labels = group["research_label"].astype(str).value_counts().to_dict()
        source = source_families[source_families["family_id"] == family_id]
        source_deeper = (
            bool(str(source.iloc[0]["deserves_deeper_research"]).lower() == "true") if not source.empty else False
        )
        if family_id == "macro_gld_duration_risk_off":
            status = "lineage_blocked_research_only"
        elif labels.get("research_signal_high_risk", 0) or labels.get("research_signal_high_risk_diversifier", 0):
            status = "risk_control_required_before_deeper_research"
        elif labels.get("research_signal_diversifier", 0):
            status = "diversifier_context_requires_audit"
        else:
            status = "research_context_only"
        rows.append(
            {
                "family_id": family_id,
                "variants_evaluated": int(len(group)),
                "source_deeper_research_flag": source_deeper,
                "deeper_research_eligible_after_label_fix": False,
                "family_status_after_label_fix": status,
                "median_cagr": float(numeric(group["cagr"]).median()),
                "median_max_drawdown": float(numeric(group["max_drawdown"]).median()),
                "median_portfolio_contribution_score": float(numeric(group["portfolio_contribution_score"]).median()),
                "research_signal_high_risk_count": int(labels.get("research_signal_high_risk", 0)),
                "research_signal_risk_control_required_count": int(labels.get("research_signal_risk_control_required", 0)),
                "research_signal_high_risk_diversifier_count": int(labels.get("research_signal_high_risk_diversifier", 0)),
                "research_signal_diversifier_count": int(labels.get("research_signal_diversifier", 0)),
                "research_signal_needs_robustness_count": int(labels.get("research_signal_needs_robustness", 0)),
                "research_signal_lineage_blocked_count": int(labels.get("research_signal_lineage_blocked", 0)),
                "research_signal_weak_count": int(labels.get("research_signal_weak", 0)),
            }
        )
    return rows


def variant_fieldnames(df: pd.DataFrame) -> list[str]:
    extras = [
        "source_methodology_research_label",
        "pre_label_fix_research_label",
        "label_policy_version",
        "risk_classification",
        "labeling_notes",
        "deeper_research_eligible_after_label_fix",
    ]
    return list(df.columns) + [field for field in extras if field not in df.columns]


def family_fieldnames() -> list[str]:
    return [
        "family_id",
        "variants_evaluated",
        "source_deeper_research_flag",
        "deeper_research_eligible_after_label_fix",
        "family_status_after_label_fix",
        "median_cagr",
        "median_max_drawdown",
        "median_portfolio_contribution_score",
        "research_signal_high_risk_count",
        "research_signal_risk_control_required_count",
        "research_signal_high_risk_diversifier_count",
        "research_signal_diversifier_count",
        "research_signal_needs_robustness_count",
        "research_signal_lineage_blocked_count",
        "research_signal_weak_count",
    ]


def label_counts(df: pd.DataFrame, column: str) -> dict[str, int]:
    return {str(key): int(value) for key, value in df[column].astype(str).value_counts().sort_index().items()}


def build_manifest(
    created_utc: str,
    output: Path,
    source: dict[str, Any],
    before: pd.DataFrame,
    after: pd.DataFrame,
    families: list[dict[str, Any]],
) -> dict[str, Any]:
    before_under = high_return_severe_underlabeled_count(after, "pre_label_fix_research_label")
    after_under = high_return_severe_underlabeled_count(after, "research_label")
    before_fav = favorable_zero_drawdown_label_count(after, "pre_label_fix_research_label")
    after_fav = favorable_zero_drawdown_label_count(after, "research_label")
    diversifier_invalid_after = invalid_diversifier_count(after, "research_label")
    exposure_ok = exposure_invariants_valid(after)
    cash_ok = cash_bil_invariants_valid(after)
    lineage_ok = macro_lineage_preserved(after)
    labels = set(after["research_label"].astype(str))
    deeper_count = int(sum(1 for row in families if row["deeper_research_eligible_after_label_fix"] is True))
    success = (
        after_under == 0
        and after_fav == 0
        and diversifier_invalid_after == 0
        and exposure_ok
        and cash_ok
        and lineage_ok
        and labels.issubset(ALLOWED_LABELS)
    )
    return {
        "created_utc": created_utc,
        **MANIFEST_FLAGS,
        "evidence_path": str(output.resolve()),
        "methodology_fix_evidence_path": str(source["source"].resolve()),
        "source_variant_count": int(len(before)),
        "corrected_label_variant_count": int(len(after)),
        "source_family_count": int(before["family_id"].nunique()),
        "corrected_label_family_count": int(after["family_id"].nunique()),
        "exposure_invariants_still_valid": bool(exposure_ok),
        "cash_bil_invariants_still_valid": bool(cash_ok),
        "high_return_severe_drawdown_underlabeled_count_before": int(before_under),
        "high_return_severe_drawdown_underlabeled_count_after": int(after_under),
        "favorable_zero_drawdown_score_label_count_before": int(before_fav),
        "favorable_zero_drawdown_score_label_count_after": int(after_fav),
        "invalid_diversifier_label_count_after": int(diversifier_invalid_after),
        "macro_gld_lineage_preserved": bool(lineage_ok),
        "deeper_research_family_count_after_label_fix": int(deeper_count),
        "allowed_labels_only": labels.issubset(ALLOWED_LABELS),
        "labels_after_fix": label_counts(after, "research_label"),
        "labels_before_fix": label_counts(after, "pre_label_fix_research_label"),
        "next_action": NEXT_ACTION_AUDIT if success else NEXT_ACTION_FIX_AGAIN,
    }


def md_table(df: pd.DataFrame, columns: list[str], limit: int = 12) -> str:
    if df.empty:
        return "None."
    clipped = df[columns].head(limit)
    lines = ["| " + " | ".join(columns) + " |", "|" + "|".join("---" for _ in columns) + "|"]
    for _, row in clipped.iterrows():
        lines.append("| " + " | ".join(str(row.get(col, "")) for col in columns) + " |")
    return "\n".join(lines)


def summary_md(manifest: dict[str, Any]) -> str:
    return f"""# Profit Research Batch V1 Labeling Fix

Batch fixed: `{manifest['batch_id_fixed']}`

Uses corrected methodology outputs: `{manifest['uses_corrected_methodology_outputs']}`

High-return/severe-drawdown under-labeled before: `{manifest['high_return_severe_drawdown_underlabeled_count_before']}`

High-return/severe-drawdown under-labeled after: `{manifest['high_return_severe_drawdown_underlabeled_count_after']}`

Favorable zero-drawdown-score labels before: `{manifest['favorable_zero_drawdown_score_label_count_before']}`

Favorable zero-drawdown-score labels after: `{manifest['favorable_zero_drawdown_score_label_count_after']}`

Invalid diversifier labels after: `{manifest['invalid_diversifier_label_count_after']}`

Exposure invariants still valid: `{manifest['exposure_invariants_still_valid']}`

Cash/BIL invariants still valid: `{manifest['cash_bil_invariants_still_valid']}`

Macro/GLD lineage preserved: `{manifest['macro_gld_lineage_preserved']}`

Exact next action: `{manifest['next_action']}`
"""


def label_policy_md() -> str:
    return f"""# Label Policy V1

This policy is for research labels only. It is not a promotion gate.

Thresholds:

- Severe drawdown: `{SEVERE_DRAWDOWN_THRESHOLD}`
- Extreme drawdown: `{EXTREME_DRAWDOWN_THRESHOLD}`
- High return CAGR: `{HIGH_RETURN_CAGR_THRESHOLD}`
- Near-zero drawdown tolerance score: `{NEAR_ZERO_DRAWDOWN_TOLERANCE_THRESHOLD}`
- Diversifier contribution score threshold: `{DIVERSIFIER_SCORE_THRESHOLD}`
- Diversifier active-combo correlation threshold: `{DIVERSIFIER_CORRELATION_THRESHOLD}`

Rules:

- High-return rows with severe or extreme drawdown must be labeled high-risk or risk-control-required.
- A plain diversifier label is not allowed when drawdown tolerance is near zero or drawdown is severe.
- Low correlation alone is not enough for a diversifier label.
- Macro/GLD rows with incomplete lineage remain lineage-blocked research-only rows.
- No label from this step can create a candidate, paper-forward action, or promotion path.
"""


def root_cause_md(audit_text: str) -> str:
    return f"""# Labeling Root Cause

The exposure/Cash-BIL methodology fix made corrected returns interpretable, but the label layer still allowed favorable labels to outrank severe drawdown.

Root issue:

- `research_signal_diversifier` and `research_signal_needs_robustness` could be assigned even when drawdown tolerance was near zero.
- High historical return with severe drawdown was not always classified as high-risk.
- Contribution-like score readings could turn high-drawdown rows into plain diversifier labels.

Prior audit excerpt source:

{audit_text[:1200]}
"""


def high_return_md(before: pd.DataFrame, after: pd.DataFrame, manifest: dict[str, Any]) -> str:
    cagr_before = numeric(before["cagr"])
    mdd_before = numeric(before["max_drawdown"])
    before_rows = before[(cagr_before >= HIGH_RETURN_CAGR_THRESHOLD) & (mdd_before <= SEVERE_DRAWDOWN_THRESHOLD)].copy()
    cagr_after = numeric(after["cagr"])
    mdd_after = numeric(after["max_drawdown"])
    after_rows = after[(cagr_after >= HIGH_RETURN_CAGR_THRESHOLD) & (mdd_after <= SEVERE_DRAWDOWN_THRESHOLD)].copy()
    return f"""# High-Return / High-Drawdown Relabeling

Under-labeled before: `{manifest['high_return_severe_drawdown_underlabeled_count_before']}`

Under-labeled after: `{manifest['high_return_severe_drawdown_underlabeled_count_after']}`

The relabeling preserves high-return rows as research evidence while making the risk explicit.

## Post-Fix Sample

{md_table(after_rows, ['family_id', 'variant_id', 'cagr', 'max_drawdown', 'pre_label_fix_research_label', 'research_label', 'risk_classification'], 14)}
"""


def diversifier_md(after: pd.DataFrame, manifest: dict[str, Any]) -> str:
    diversifiers = after[after["research_label"] == "research_signal_diversifier"].copy()
    return f"""# Diversifier Label Validation

Invalid diversifier labels after fix: `{manifest['invalid_diversifier_label_count_after']}`

Plain diversifier labels now require contribution evidence, active-combo correlation below threshold, positive active-combo blend return contribution, and no severe drawdown concealment.

High-risk contribution-like rows receive explicit high-risk labels instead of plain diversifier labels.

## Valid Diversifier Rows

{md_table(diversifiers, ['family_id', 'variant_id', 'cagr', 'max_drawdown', 'portfolio_contribution_score', 'active_combo_correlation', 'research_label'], 12)}
"""


def macro_md(after: pd.DataFrame) -> str:
    macro = after[after["family_id"] == "macro_gld_duration_risk_off"].copy()
    return f"""# Macro / GLD Lineage Label Status

Macro/GLD lineage preserved: `{macro_lineage_preserved(after)}`

All macro/GLD rows remain `lineage_incomplete_research_only` and cannot become accepted deeper-research rows from this label fix.

## Macro Rows

{md_table(macro, ['variant_id', 'cagr', 'max_drawdown', 'lineage_status', 'pre_label_fix_research_label', 'research_label'], 12)}
"""


def comparison_md(before: pd.DataFrame, after: pd.DataFrame) -> str:
    rows = []
    changed = after[after["pre_label_fix_research_label"].astype(str) != after["research_label"].astype(str)].copy()
    return f"""# Pre-Label-Fix Vs Post-Label-Fix Comparison

Labels before: `{label_counts(after, 'pre_label_fix_research_label')}`

Labels after: `{label_counts(after, 'research_label')}`

Rows relabeled: `{len(changed)}`

## Relabeled Sample

{md_table(changed, ['family_id', 'variant_id', 'pre_label_fix_research_label', 'research_label', 'risk_classification'], 20)}
"""


def deeper_flags_md(families: list[dict[str, Any]]) -> str:
    df = pd.DataFrame(families)
    return f"""# Deeper Research Flags After Label Fix

Accepted deeper-research families from this label fix: `0`

This patch fixes labels only. Family conclusions require the next independent audit.

High-return tactical rows are now explicit high-risk/risk-control research evidence.

Macro/GLD rows are lineage-blocked and require lineage recovery before deeper macro testing can be accepted.

## Family Status

{md_table(df, family_fieldnames(), 10)}
"""


def do_not_promote_md() -> str:
    return """# Do Not Promote After Labeling Fix

This labeling fix is non-promotable by design.

It creates no promotion-review candidates, no candidate-exhaustive candidates, no paper-forward candidates, no paper-forward activation, no broker/live action, and no real-money recommendation.
"""


def next_action_md(next_action: str) -> str:
    return f"""# Labeling Fix Next Action

Exact next action:

`{next_action}`

Do not run the next action in this task.
"""


def consistency_check(manifest: dict[str, Any], output: Path) -> dict[str, Any]:
    required = {name: (output / name).exists() for name in REQUIRED_OUTPUT_FILES}
    check = {
        "labeling_fix_only": manifest["labeling_fix_only"] is True,
        "correct_batch_id_fixed": manifest["batch_id_fixed"] == BATCH_ID,
        "uses_corrected_methodology_outputs": manifest["uses_corrected_methodology_outputs"] is True,
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
        "exposure_methodology_not_reopened": manifest["exposure_methodology_reopened"] is False,
        "exposure_invariants_still_valid": manifest["exposure_invariants_still_valid"] is True,
        "cash_bil_invariants_still_valid": manifest["cash_bil_invariants_still_valid"] is True,
        "high_return_severe_underlabeled_zero": manifest["high_return_severe_drawdown_underlabeled_count_after"] == 0,
        "favorable_zero_drawdown_labels_zero": manifest["favorable_zero_drawdown_score_label_count_after"] == 0,
        "diversifier_labels_require_risk_check": manifest["diversifier_label_requires_risk_check"] is True
        and manifest["invalid_diversifier_label_count_after"] == 0,
        "macro_gld_lineage_preserved": manifest["macro_gld_lineage_preserved"] is True,
        "deeper_research_flags_file_exists": (output / "deeper_research_flags_after_label_fix.md").exists(),
        "do_not_promote_file_exists": (output / "do_not_promote_after_labeling_fix.md").exists(),
        "next_action_valid": manifest["next_action"] in VALID_NEXT_ACTIONS,
        "required_files_present": all(required.values()),
        "required_files": required,
    }
    check["consistency_passed"] = all(value is True for key, value in check.items() if key != "required_files")
    return check


def update_research_metadata(root: Path, created_utc: str, output: Path, manifest: dict[str, Any]) -> None:
    path = root / RESEARCH_STATE_PATH
    before = read_text(path)
    section = f"""## Profit Batch V1 Labeling Fix

- Created UTC: `{created_utc}`
- Evidence path: `{output.resolve()}`
- Batch fixed: `{BATCH_ID}`
- High-return/severe-drawdown under-labeled after: `{manifest['high_return_severe_drawdown_underlabeled_count_after']}`
- Favorable zero-drawdown labels after: `{manifest['favorable_zero_drawdown_score_label_count_after']}`
- Diversifier label invalid count after: `{manifest['invalid_diversifier_label_count_after']}`
- Exposure invariants still valid: `{manifest['exposure_invariants_still_valid']}`
- Cash/BIL invariants still valid: `{manifest['cash_bil_invariants_still_valid']}`
- Next action: `{manifest['next_action']}`
"""
    write_text(path, replace_or_append_section(before, "## Profit Batch V1 Labeling Fix", section))


def run(root: Path = ROOT) -> dict[str, Any]:
    created = now_utc()
    output = root / OUTPUT_DIR
    output.mkdir(parents=True, exist_ok=True)
    source = load_source(root)
    before_df: pd.DataFrame = source["methodology_rows"].copy()
    relabeled_rows = relabel_rows(row_dicts(before_df))
    after_df = pd.DataFrame(relabeled_rows)
    families = family_summary(after_df, source["methodology_families"])
    manifest = build_manifest(created, output, source, before_df, after_df, families)

    write_json(output / "labeling_fix_manifest.json", manifest)
    write_text(output / "labeling_fix_summary.md", summary_md(manifest))
    write_text(output / "label_policy_v1.md", label_policy_md())
    write_text(output / "labeling_root_cause.md", root_cause_md(source["audit_scoring_label"]))
    write_csv(output / "corrected_label_variant_results.csv", relabeled_rows, variant_fieldnames(before_df))
    write_csv(output / "corrected_label_family_summary.csv", families, family_fieldnames())
    write_text(output / "high_return_high_drawdown_relabeling.md", high_return_md(before_df, after_df, manifest))
    write_text(output / "diversifier_label_validation.md", diversifier_md(after_df, manifest))
    write_text(output / "macro_gld_lineage_label_status.md", macro_md(after_df))
    write_text(output / "pre_label_fix_vs_post_label_fix_comparison.md", comparison_md(before_df, after_df))
    write_text(output / "deeper_research_flags_after_label_fix.md", deeper_flags_md(families))
    write_text(output / "do_not_promote_after_labeling_fix.md", do_not_promote_md())
    write_text(output / "labeling_fix_next_action.md", next_action_md(manifest["next_action"]))
    write_json(output / "labeling_fix_consistency_check.json", {"consistency_passed": False})
    check = consistency_check(manifest, output)
    write_json(output / "labeling_fix_consistency_check.json", check)
    update_research_metadata(root, created, output, manifest)
    return {**manifest, "output_dir": str(output.resolve()), "consistency_passed": check["consistency_passed"]}


if __name__ == "__main__":
    result = run()
    print(
        json.dumps(
            {
                "output_dir": result["output_dir"],
                "batch_id_fixed": result["batch_id_fixed"],
                "underlabeled_before": result["high_return_severe_drawdown_underlabeled_count_before"],
                "underlabeled_after": result["high_return_severe_drawdown_underlabeled_count_after"],
                "favorable_zero_drawdown_before": result["favorable_zero_drawdown_score_label_count_before"],
                "favorable_zero_drawdown_after": result["favorable_zero_drawdown_score_label_count_after"],
                "invalid_diversifier_label_count_after": result["invalid_diversifier_label_count_after"],
                "next_action": result["next_action"],
                "consistency_passed": result["consistency_passed"],
            },
            indent=2,
        )
    )
