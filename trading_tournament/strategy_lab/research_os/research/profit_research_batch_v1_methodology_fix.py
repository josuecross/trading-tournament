from __future__ import annotations

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
    FORBIDDEN_LABELS,
    MANIFEST_FLAGS as BATCH_MANIFEST_FLAGS,
    RESEARCH_OUTPUT_DIR as OLD_BATCH_OUTPUT_DIR,
    WEIGHT_TOLERANCE,
    build_variant_plan,
    complete_rebalance_weight_frame,
    diversifier_md,
    evaluate_batch,
    family_fieldnames,
    family_summary_md,
    high_risk_md,
    variant_fieldnames,
    weight_invariant_report,
    write_csv,
)
from strategy_lab.research_os.split_tracks import RESEARCH_STATE_PATH


OUTPUT_DIR = Path("evidence") / "research_recovery" / "profit_oriented_research_batch_v1_methodology_fix" / "latest"
AUDIT_OUTPUT_DIR = Path("evidence") / "research_recovery" / "profit_oriented_research_batch_v1_audit" / "latest"

NEXT_ACTION_AUDIT_FIXED = "audit_profit_oriented_research_batch_v1_after_methodology_fix"
NEXT_ACTION_FIX_AGAIN = "fix_profit_research_batch_v1_methodology_issue_again"
NEXT_ACTION_MANUAL = "manual_review_required_after_methodology_fix"
NEXT_ACTION_PAUSE = "pause_expansion_and_wait_for_manual_direction"
VALID_NEXT_ACTIONS = {
    NEXT_ACTION_AUDIT_FIXED,
    NEXT_ACTION_FIX_AGAIN,
    NEXT_ACTION_MANUAL,
    NEXT_ACTION_PAUSE,
}

REQUIRED_OUTPUT_FILES = (
    "methodology_fix_manifest.json",
    "methodology_fix_summary.md",
    "root_cause_analysis.md",
    "weight_construction_fix.md",
    "cash_bil_fix.md",
    "exposure_invariant_report.md",
    "synthetic_weight_tests.md",
    "pre_fix_vs_post_fix_comparison.md",
    "corrected_profit_research_variant_results.csv",
    "corrected_profit_research_family_summary.csv",
    "corrected_profit_research_family_summary.md",
    "corrected_high_profit_high_risk_signals.md",
    "corrected_portfolio_diversifier_signals.md",
    "invalidated_prior_batch_v1_results.md",
    "do_not_promote_after_methodology_fix.md",
    "methodology_fix_next_action.md",
    "methodology_fix_consistency_check.json",
)

MANIFEST_FLAGS = {
    "methodology_fix_only": True,
    "batch_id_fixed": BATCH_ID,
    "same_variant_set_rerun": True,
    "new_research_batch_run": False,
    "new_strategy_discovery_run": False,
    "new_variants_created": False,
    "new_families_created": False,
    "provider_download": False,
    "uses_local_cache_only": True,
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
    "old_batch_v1_results_invalidated_or_superseded": True,
}


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def rows_to_frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def load_old_rows(root: Path) -> pd.DataFrame:
    path = root / OLD_BATCH_OUTPUT_DIR / "profit_research_variant_results.csv"
    return pd.read_csv(path) if path.exists() else pd.DataFrame()


def load_old_families(root: Path) -> pd.DataFrame:
    path = root / OLD_BATCH_OUTPUT_DIR / "profit_research_family_summary.csv"
    return pd.read_csv(path) if path.exists() else pd.DataFrame()


def exposure_findings(corrected: pd.DataFrame) -> dict[str, Any]:
    if corrected.empty:
        return {
            "average_exposure_gt_1_count_after_fix": 0,
            "average_exposure_gt_2_count_after_fix": 0,
            "max_daily_exposure_after_fix": 0.0,
            "max_daily_weight_sum_after_fix": 0.0,
            "weight_sum_violation_count_after_fix": 0,
            "negative_weight_violation_count_after_fix": 0,
            "nan_weight_count_after_fix": 0,
            "impossible_cash_bil_plus_risky_row_count_after_fix": 0,
            "impossible_cash_and_risky_exposure_days_after_fix": 0,
            "high_cash_high_cagr_count_after_fix": 0,
        }
    avg_exposure = numeric(corrected["average_exposure"])
    max_exposure = numeric(corrected.get("max_daily_exposure", pd.Series([0.0] * len(corrected))))
    max_weight_sum = numeric(corrected.get("max_daily_weight_sum", pd.Series([0.0] * len(corrected))))
    cash = numeric(corrected["cash_bil_allocation_share"])
    cagr = numeric(corrected["cagr"])
    impossible_rows = corrected[(cash >= 1.0 - WEIGHT_TOLERANCE) & (avg_exposure > WEIGHT_TOLERANCE)]
    return {
        "average_exposure_gt_1_count_after_fix": int((avg_exposure > 1.0 + WEIGHT_TOLERANCE).sum()),
        "average_exposure_gt_2_count_after_fix": int((avg_exposure > 2.0).sum()),
        "max_daily_exposure_after_fix": float(max_exposure.max(skipna=True)),
        "max_daily_weight_sum_after_fix": float(max_weight_sum.max(skipna=True)),
        "weight_sum_violation_count_after_fix": int(
            numeric(corrected.get("weight_sum_violation_count", pd.Series([0] * len(corrected)))).sum()
        ),
        "negative_weight_violation_count_after_fix": int(
            numeric(corrected.get("negative_weight_violation_count", pd.Series([0] * len(corrected)))).sum()
        ),
        "nan_weight_count_after_fix": int(numeric(corrected.get("nan_weight_count", pd.Series([0] * len(corrected)))).sum()),
        "impossible_cash_bil_plus_risky_row_count_after_fix": int(len(impossible_rows)),
        "impossible_cash_and_risky_exposure_days_after_fix": int(
            numeric(corrected.get("impossible_cash_and_risky_exposure_days", pd.Series([0] * len(corrected)))).sum()
        ),
        "high_cash_high_cagr_count_after_fix": int(((cash > 0.30) & (cagr > 0.10)).sum()),
    }


def invariants_pass(findings: dict[str, Any]) -> bool:
    return (
        findings["average_exposure_gt_1_count_after_fix"] == 0
        and findings["average_exposure_gt_2_count_after_fix"] == 0
        and findings["max_daily_exposure_after_fix"] <= 1.0 + WEIGHT_TOLERANCE
        and findings["max_daily_weight_sum_after_fix"] <= 1.0 + WEIGHT_TOLERANCE
        and findings["weight_sum_violation_count_after_fix"] == 0
        and findings["negative_weight_violation_count_after_fix"] == 0
        and findings["nan_weight_count_after_fix"] == 0
        and findings["impossible_cash_bil_plus_risky_row_count_after_fix"] == 0
        and findings["impossible_cash_and_risky_exposure_days_after_fix"] == 0
    )


def run_synthetic_weight_tests() -> list[dict[str, Any]]:
    index = pd.date_range("2020-01-01", periods=8, freq="D")
    cases: list[tuple[str, list[str], dict[pd.Timestamp, dict[str, float]], Any]] = [
        (
            "top1 selection changes from A to B and A becomes zero",
            ["A", "B", "BIL"],
            {index[0]: {"A": 1.0}, index[4]: {"B": 1.0}},
            lambda weights: weights.loc[index[4], "A"] == 0.0 and weights.loc[index[4], "B"] == 1.0,
        ),
        (
            "top2 selection changes and old non-selected asset becomes zero",
            ["A", "B", "C", "BIL"],
            {index[0]: {"A": 0.5, "B": 0.5}, index[4]: {"B": 0.5, "C": 0.5}},
            lambda weights: weights.loc[index[4], "A"] == 0.0 and weights.loc[index[4], "C"] == 0.5,
        ),
        (
            "no eligible assets sets BIL fallback to one",
            ["A", "B", "BIL"],
            {index[0]: {"BIL": 1.0}},
            lambda weights: weights.loc[index[3], "BIL"] == 1.0 and weights.loc[index[3], "A"] == 0.0,
        ),
        (
            "eligible rebalance after BIL fallback removes BIL",
            ["A", "BIL"],
            {index[0]: {"BIL": 1.0}, index[4]: {"A": 1.0}},
            lambda weights: weights.loc[index[4], "BIL"] == 0.0 and weights.loc[index[4], "A"] == 1.0,
        ),
        (
            "partial allocation assigns BIL only to the remainder",
            ["A", "BIL"],
            {index[0]: {"A": 0.4, "BIL": 0.6}},
            lambda weights: weights.loc[index[2], "A"] == 0.4 and weights.loc[index[2], "BIL"] == 0.6,
        ),
        (
            "daily forward fill preserves last complete rebalance row",
            ["A", "B", "BIL"],
            {index[0]: {"A": 0.5, "B": 0.5}, index[4]: {"BIL": 1.0}},
            lambda weights: weights.loc[index[6], "A"] == 0.0 and weights.loc[index[6], "BIL"] == 1.0,
        ),
    ]
    results: list[dict[str, Any]] = []
    for name, columns, targets, assertion in cases:
        try:
            weights = complete_rebalance_weight_frame(index, columns, targets)
            report = weight_invariant_report(weights)
            passed = bool(assertion(weights)) and report["max_daily_weight_sum"] <= 1.0 + WEIGHT_TOLERANCE
            details = f"max_daily_weight_sum={report['max_daily_weight_sum']:.6f}"
        except Exception as exc:  # pragma: no cover - the test suite asserts this does not happen.
            passed = False
            details = str(exc)
        results.append({"case": name, "passed": passed, "details": details})
    return results


def synthetic_tests_pass(results: list[dict[str, Any]]) -> bool:
    return bool(results) and all(row["passed"] is True for row in results)


def label_counts(df: pd.DataFrame) -> dict[str, int]:
    if df.empty or "research_label" not in df.columns:
        return {}
    return {str(key): int(value) for key, value in df["research_label"].value_counts().sort_index().items()}


def family_deeper_count(families: list[dict[str, Any]]) -> int:
    return int(sum(1 for family in families if family.get("deserves_deeper_research") is True))


def build_manifest(
    created_utc: str,
    output: Path,
    old_rows: pd.DataFrame,
    corrected_rows: list[dict[str, Any]],
    corrected_families: list[dict[str, Any]],
    exposure: dict[str, Any],
    synthetic_results: list[dict[str, Any]],
) -> dict[str, Any]:
    corrected = rows_to_frame(corrected_rows)
    old_ids = set(old_rows["variant_id"].astype(str)) if not old_rows.empty and "variant_id" in old_rows.columns else set()
    corrected_ids = set(corrected["variant_id"].astype(str)) if not corrected.empty and "variant_id" in corrected.columns else set()
    plan_ids = {variant.variant_id for variant in build_variant_plan()}
    labels = set(corrected["research_label"].astype(str)) if not corrected.empty else set()
    fixed = invariants_pass(exposure) and synthetic_tests_pass(synthetic_results)
    same_set = corrected_ids == plan_ids and (not old_ids or corrected_ids == old_ids)
    next_action = NEXT_ACTION_AUDIT_FIXED if fixed and same_set else NEXT_ACTION_FIX_AGAIN
    return {
        "created_utc": created_utc,
        **MANIFEST_FLAGS,
        "evidence_path": str(output.resolve()),
        "same_variant_set_verified": bool(same_set),
        "planned_variant_count": int(len(plan_ids)),
        "corrected_variant_count": int(len(corrected_rows)),
        "corrected_family_count": int(corrected["family_id"].nunique()) if not corrected.empty else 0,
        "old_variant_count": int(len(old_rows)),
        "weight_forward_fill_bug_fixed": bool(synthetic_tests_pass(synthetic_results) and exposure["average_exposure_gt_1_count_after_fix"] == 0),
        "cash_bil_accumulation_bug_fixed": bool(
            exposure["impossible_cash_bil_plus_risky_row_count_after_fix"] == 0
            and exposure["impossible_cash_and_risky_exposure_days_after_fix"] == 0
        ),
        **exposure,
        "families_marked_for_deeper_research_after_fix": family_deeper_count(corrected_families),
        "forbidden_labels_present": sorted(labels.intersection(FORBIDDEN_LABELS)),
        "allowed_labels_only": labels.issubset(ALLOWED_LABELS),
        "synthetic_weight_tests_passed": synthetic_tests_pass(synthetic_results),
        "corrected_results_regenerated_from_fixed_weights": True,
        "next_action": next_action,
    }


def methodology_fix_summary_md(manifest: dict[str, Any]) -> str:
    return f"""# Profit Research Batch V1 Methodology Fix

Batch fixed: `{manifest['batch_id_fixed']}`

Same frozen variant set rerun: `{manifest['same_variant_set_verified']}`

Corrected variants evaluated: `{manifest['corrected_variant_count']}`

Maximum daily exposure after fix: `{manifest['max_daily_exposure_after_fix']:.6f}`

Average-exposure > 1 count after fix: `{manifest['average_exposure_gt_1_count_after_fix']}`

Average-exposure > 2 count after fix: `{manifest['average_exposure_gt_2_count_after_fix']}`

Impossible cash/BIL plus risky rows after fix: `{manifest['impossible_cash_bil_plus_risky_row_count_after_fix']}`

Synthetic weight tests passed: `{manifest['synthetic_weight_tests_passed']}`

Old batch v1 outputs are treated as contaminated and superseded by this methodology-fix packet.

Corrected outputs remain non-promotable and require audit before any deeper research decision.

Exact next action: `{manifest['next_action']}`
"""


def root_cause_md() -> str:
    return """# Root Cause Analysis

The audit traced the contaminated batch v1 results to monthly momentum weight construction.

The unsafe pattern converted deliberate zero weights into missing values before forward fill. That made old selected assets survive after a later rebalance selected a different set of assets. In a long-only ETF wrapper this creates impossible exposure, because prior risky allocations and BIL/cash fallback can accumulate above 100%.

The consequence was contaminated returns, CAGR, drawdown, benchmark deltas, contribution metrics, and research labels. Those old outputs are invalidated/superseded and are not decision-grade.
"""


def weight_fix_md() -> str:
    return """# Weight Construction Fix

The patched engine now creates explicit full target rows at each rebalance date.

Rules enforced:

- Every symbol receives an explicit target weight at each rebalance.
- Non-selected assets are set to `0.0`.
- Deliberate zeros are never converted to missing values.
- Complete rebalance rows are forward-filled between rebalance dates.
- Daily weight sums must stay at or below `1.0` within floating tolerance.
- Negative weights, NaN weights, and additive BIL plus risky exposure raise invariant failures.

This preserves the intended monthly signal timing while preventing stale allocations from accumulating.
"""


def cash_bil_fix_md() -> str:
    return """# Cash / BIL Fix

BIL is handled as fallback or unallocated capital only.

If risky assets use the full allocation, BIL is `0.0`. If no risky asset qualifies, BIL may be `1.0`. If a rule intentionally uses partial risky exposure, BIL can receive only the remainder.

The methodology-fix report checks both row-level and day-level impossible cash plus risky exposure.
"""


def exposure_report_md(manifest: dict[str, Any]) -> str:
    return f"""# Exposure Invariant Report

Result: `{'pass' if manifest['next_action'] == NEXT_ACTION_AUDIT_FIXED else 'fail'}`

- Maximum daily exposure after fix: `{manifest['max_daily_exposure_after_fix']:.6f}`
- Maximum daily weight sum after fix: `{manifest['max_daily_weight_sum_after_fix']:.6f}`
- Average-exposure > 1 count: `{manifest['average_exposure_gt_1_count_after_fix']}`
- Average-exposure > 2 count: `{manifest['average_exposure_gt_2_count_after_fix']}`
- Weight-sum violation count: `{manifest['weight_sum_violation_count_after_fix']}`
- Negative-weight violation count: `{manifest['negative_weight_violation_count_after_fix']}`
- NaN weight count: `{manifest['nan_weight_count_after_fix']}`
- Impossible cash/BIL plus risky row count: `{manifest['impossible_cash_bil_plus_risky_row_count_after_fix']}`
- Impossible cash/BIL plus risky day count: `{manifest['impossible_cash_and_risky_exposure_days_after_fix']}`

All corrected results remain research-only and non-promotable.
"""


def synthetic_tests_md(results: list[dict[str, Any]]) -> str:
    lines = [
        "# Synthetic Weight Tests",
        "",
        "| case | passed | details |",
        "|---|---:|---|",
    ]
    for row in results:
        lines.append(f"| {row['case']} | `{row['passed']}` | {row['details']} |")
    return "\n".join(lines) + "\n"


def comparison_md(old_rows: pd.DataFrame, corrected_rows: pd.DataFrame, old_families: pd.DataFrame, corrected_families: list[dict[str, Any]]) -> str:
    old_exposure = exposure_findings(old_rows.rename(columns={"max_daily_exposure": "average_exposure"})) if not old_rows.empty else {}
    corrected_exposure = exposure_findings(corrected_rows)
    old_label_counts = label_counts(old_rows)
    corrected_label_counts = label_counts(corrected_rows)
    old_deeper = int(
        (old_families["deserves_deeper_research"].astype(str).str.lower() == "true").sum()
    ) if not old_families.empty and "deserves_deeper_research" in old_families.columns else 0
    corrected_deeper = family_deeper_count(corrected_families)
    return f"""# Pre-Fix Vs Post-Fix Comparison

The pre-fix batch v1 evidence is contaminated by impossible exposure and is superseded.

| metric | pre-fix saved output | post-fix corrected output |
|---|---:|---:|
| variants | {len(old_rows)} | {len(corrected_rows)} |
| average exposure > 1 | {int((numeric(old_rows['average_exposure']) > 1.0 + WEIGHT_TOLERANCE).sum()) if not old_rows.empty else 0} | {corrected_exposure['average_exposure_gt_1_count_after_fix']} |
| average exposure > 2 | {int((numeric(old_rows['average_exposure']) > 2.0).sum()) if not old_rows.empty else 0} | {corrected_exposure['average_exposure_gt_2_count_after_fix']} |
| max average exposure | {float(numeric(old_rows['average_exposure']).max(skipna=True)) if not old_rows.empty else 0.0:.6f} | {float(numeric(corrected_rows['average_exposure']).max(skipna=True)) if not corrected_rows.empty else 0.0:.6f} |
| max daily exposure | unavailable in old output | {corrected_exposure['max_daily_exposure_after_fix']:.6f} |
| deeper-research families marked | {old_deeper} | {corrected_deeper} |

Pre-fix labels: `{old_label_counts}`

Post-fix labels: `{corrected_label_counts}`

Corrected labels are still non-promotable and require audit before any research follow-up.
"""


def invalidated_prior_md(root: Path) -> str:
    audit_manifest = read_json(root / AUDIT_OUTPUT_DIR / "profit_batch_v1_audit_manifest.json")
    return f"""# Invalidated Prior Batch V1 Results

Prior evidence path: `{(root / OLD_BATCH_OUTPUT_DIR).resolve()}`

Audit evidence path: `{(root / AUDIT_OUTPUT_DIR).resolve()}`

Audit methodology valid: `{audit_manifest.get('methodology_valid')}`

The prior `profit_oriented_research_batch_v1/latest` outputs are contaminated by the exposure/weighting bug and are superseded by this methodology-fix packet.

Do not use the prior high-profit, high-risk, diversifier, benchmark-delta, contribution, or deeper-research labels for decisions.
"""


def do_not_promote_md() -> str:
    return """# Do Not Promote After Methodology Fix

The corrected same-batch rerun is diagnostic and non-promotable.

It creates no promotion-review candidates, no candidate-exhaustive candidates, no paper-forward candidates, no broker path, and no real-money recommendation.

The only allowed next decision after a successful methodology fix is an audit of the corrected evidence.
"""


def next_action_md(next_action: str) -> str:
    return f"""# Methodology Fix Next Action

Exact next action:

`{next_action}`

Do not run the next action in this task.
"""


def consistency_check(manifest: dict[str, Any], output: Path, corrected_rows: pd.DataFrame) -> dict[str, Any]:
    required = {name: (output / name).exists() for name in REQUIRED_OUTPUT_FILES}
    labels = set(corrected_rows["research_label"].astype(str)) if not corrected_rows.empty else set()
    check = {
        "methodology_fix_only": manifest["methodology_fix_only"] is True,
        "same_batch_id_fixed": manifest["batch_id_fixed"] == BATCH_ID,
        "same_variant_set_rerun": manifest["same_variant_set_rerun"] is True,
        "same_variant_set_verified": manifest["same_variant_set_verified"] is True,
        "no_new_research_batch": manifest["new_research_batch_run"] is False,
        "no_new_strategy_discovery": manifest["new_strategy_discovery_run"] is False,
        "no_new_variants": manifest["new_variants_created"] is False,
        "no_new_families": manifest["new_families_created"] is False,
        "no_provider_download": manifest["provider_download"] is False,
        "local_cache_only": manifest["uses_local_cache_only"] is True,
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
        "manual_observation_loop_not_blocking": manifest["manual_observation_loop_blocking_research"] is False,
        "alpaca_execution_module_delegated": manifest["alpaca_execution_module_delegated"] is True,
        "old_batch_invalidated_or_superseded": manifest["old_batch_v1_results_invalidated_or_superseded"] is True,
        "weight_forward_fill_bug_fixed": manifest["weight_forward_fill_bug_fixed"] is True,
        "cash_bil_accumulation_bug_fixed": manifest["cash_bil_accumulation_bug_fixed"] is True,
        "corrected_variant_results_exist": (output / "corrected_profit_research_variant_results.csv").exists(),
        "corrected_family_summary_exists": (output / "corrected_profit_research_family_summary.csv").exists(),
        "exposure_invariant_report_exists": (output / "exposure_invariant_report.md").exists(),
        "synthetic_weight_tests_file_exists": (output / "synthetic_weight_tests.md").exists(),
        "average_exposure_gt_1_zero": manifest["average_exposure_gt_1_count_after_fix"] == 0,
        "average_exposure_gt_2_zero": manifest["average_exposure_gt_2_count_after_fix"] == 0,
        "max_daily_exposure_bounded": manifest["max_daily_exposure_after_fix"] <= 1.0 + WEIGHT_TOLERANCE,
        "max_daily_weight_sum_bounded": manifest["max_daily_weight_sum_after_fix"] <= 1.0 + WEIGHT_TOLERANCE,
        "no_impossible_cash_bil_plus_risky_rows": manifest["impossible_cash_bil_plus_risky_row_count_after_fix"] == 0,
        "no_impossible_cash_bil_plus_risky_days": manifest["impossible_cash_and_risky_exposure_days_after_fix"] == 0,
        "allowed_labels_only": labels.issubset(ALLOWED_LABELS),
        "forbidden_labels_absent": not labels.intersection(FORBIDDEN_LABELS),
        "do_not_promote_file_exists": (output / "do_not_promote_after_methodology_fix.md").exists(),
        "next_action_valid": manifest["next_action"] in VALID_NEXT_ACTIONS,
        "required_files_present": all(required.values()),
        "required_files": required,
    }
    check["consistency_passed"] = all(value is True for key, value in check.items() if key != "required_files")
    return check


def update_research_metadata(root: Path, created_utc: str, output: Path, manifest: dict[str, Any]) -> None:
    path = root / RESEARCH_STATE_PATH
    before = read_text(path)
    section = f"""## Profit Research Batch V1 Methodology Fix

- Created UTC: `{created_utc}`
- Evidence path: `{output.resolve()}`
- Batch fixed: `{BATCH_ID}`
- Same variant set verified: `{manifest['same_variant_set_verified']}`
- Max daily exposure after fix: `{manifest['max_daily_exposure_after_fix']:.6f}`
- Average-exposure > 1 after fix: `{manifest['average_exposure_gt_1_count_after_fix']}`
- Old batch v1 results invalidated/superseded: `{manifest['old_batch_v1_results_invalidated_or_superseded']}`
- Promotion candidates created: `{manifest['promotion_candidates_created']}`
- Next action: `{manifest['next_action']}`
"""
    write_text(path, replace_or_append_section(before, "## Profit Research Batch V1 Methodology Fix", section))


def run(root: Path = ROOT) -> dict[str, Any]:
    created = now_utc()
    output = root / OUTPUT_DIR
    output.mkdir(parents=True, exist_ok=True)

    old_rows = load_old_rows(root)
    old_families = load_old_families(root)
    _, corrected_rows, corrected_families = evaluate_batch(root)
    corrected = rows_to_frame(corrected_rows)
    exposure = exposure_findings(corrected)
    synthetic_results = run_synthetic_weight_tests()
    manifest = build_manifest(created, output, old_rows, corrected_rows, corrected_families, exposure, synthetic_results)

    write_json(output / "methodology_fix_manifest.json", manifest)
    write_text(output / "methodology_fix_summary.md", methodology_fix_summary_md(manifest))
    write_text(output / "root_cause_analysis.md", root_cause_md())
    write_text(output / "weight_construction_fix.md", weight_fix_md())
    write_text(output / "cash_bil_fix.md", cash_bil_fix_md())
    write_text(output / "exposure_invariant_report.md", exposure_report_md(manifest))
    write_text(output / "synthetic_weight_tests.md", synthetic_tests_md(synthetic_results))
    write_text(output / "pre_fix_vs_post_fix_comparison.md", comparison_md(old_rows, corrected, old_families, corrected_families))
    write_csv(output / "corrected_profit_research_variant_results.csv", corrected_rows, variant_fieldnames())
    write_csv(output / "corrected_profit_research_family_summary.csv", corrected_families, family_fieldnames())
    write_text(output / "corrected_profit_research_family_summary.md", family_summary_md(corrected_families))
    write_text(output / "corrected_high_profit_high_risk_signals.md", high_risk_md(corrected_rows))
    write_text(output / "corrected_portfolio_diversifier_signals.md", diversifier_md(corrected_rows))
    write_text(output / "invalidated_prior_batch_v1_results.md", invalidated_prior_md(root))
    write_text(output / "do_not_promote_after_methodology_fix.md", do_not_promote_md())
    write_text(output / "methodology_fix_next_action.md", next_action_md(manifest["next_action"]))
    write_json(output / "methodology_fix_consistency_check.json", {"consistency_passed": False})
    check = consistency_check(manifest, output, corrected)
    write_json(output / "methodology_fix_consistency_check.json", check)
    update_research_metadata(root, created, output, manifest)
    return {**manifest, "output_dir": str(output.resolve()), "consistency_passed": check["consistency_passed"]}


if __name__ == "__main__":
    result = run()
    print(
        json.dumps(
            {
                "output_dir": result["output_dir"],
                "batch_id_fixed": result["batch_id_fixed"],
                "corrected_variant_count": result["corrected_variant_count"],
                "max_daily_exposure_after_fix": result["max_daily_exposure_after_fix"],
                "average_exposure_gt_1_count_after_fix": result["average_exposure_gt_1_count_after_fix"],
                "families_marked_for_deeper_research_after_fix": result["families_marked_for_deeper_research_after_fix"],
                "next_action": result["next_action"],
                "consistency_passed": result["consistency_passed"],
            },
            indent=2,
        )
    )
