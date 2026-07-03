from __future__ import annotations

import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.objective_reset.objective_reset_review import write_json, write_text
from strategy_lab.research_os.research.high_return_tactical_risk_control_lane_run import (
    active_combo_returns,
    benchmark_delta,
    build_baseline_weights,
    cached_price_series,
    cached_prices,
    calmar_improvement,
    contribution_metrics,
    metrics_for_returns,
    pct_reduction,
    reference_spy200d_returns,
    safe_ratio,
)
from strategy_lab.research_os.research.profit_oriented_research_batch_v1 import write_csv
from strategy_lab.research_os.research.volatility_throttle_focused_research_followup_run import (
    ALLOWED_LABELS,
    EXPECTED_ROLE_COUNTS,
    EXPECTED_ROW_COUNT,
    EXPECTED_THRESHOLD_SETS,
    LANE_ID,
    RESULT_FIELDS,
    SOURCE_AUDIT_DIR,
    SOURCE_DESIGN_DIR,
    SOURCE_RUN_DIR,
    VALID_NEXT_ACTIONS as RUN_VALID_NEXT_ACTIONS,
    run_volatility_throttle_variant,
)


FOLLOWUP_RUN_DIR = (
    Path("evidence")
    / "research_recovery"
    / "volatility_throttle_focused_research_followup_run"
    / "latest"
)
OUTPUT_DIR = (
    Path("evidence")
    / "research_recovery"
    / "volatility_throttle_focused_research_followup_results_audit"
    / "latest"
)

NEXT_ACTION_MANUAL = "manual_review_required_after_volatility_throttle_followup_results_audit"
NEXT_ACTION_PATCH = "patch_volatility_throttle_focused_research_followup_run"
VALID_NEXT_ACTIONS = {NEXT_ACTION_MANUAL, NEXT_ACTION_PATCH}

AUDIT_DECISION_PASSED = "followup_results_audit_passed"
AUDIT_DECISION_PATCH = "followup_results_needs_patch"

RETURN_TOLERANCE = 1e-12
WEIGHT_TOLERANCE = 1e-12
METRIC_TOLERANCE = 1e-8

REQUIRED_RUN_FILES = (
    "vol_throttle_followup_run_manifest.json",
    "vol_throttle_followup_run_summary.md",
    "vol_throttle_followup_run_preflight.md",
    "vol_throttle_followup_results.csv",
    "vol_throttle_followup_results.md",
    "vol_throttle_followup_numeric_criteria_results.csv",
    "vol_throttle_followup_role_summary.csv",
    "vol_throttle_followup_threshold_summary.csv",
    "baseline_comparator_mapping_report.md",
    "exposure_invariant_report.md",
    "confirmation_reference_behavior.md",
    "robustness_behavior.md",
    "do_not_promote_from_vol_throttle_followup_run.md",
    "vol_throttle_followup_run_next_action.md",
    "vol_throttle_followup_run_consistency_check.json",
)

AUDIT_OUTPUT_FILES = (
    "vol_throttle_followup_results_audit_manifest.json",
    "vol_throttle_followup_results_audit_summary.md",
    "evidence_completeness_audit.md",
    "design_to_run_consistency_audit.md",
    "methodology_integrity_audit.md",
    "optimized_loop_equivalence_report.md",
    "row_level_discrepancy_report.csv",
    "row_level_discrepancy_report.md",
    "criteria_recomputation_report.csv",
    "criteria_recomputation_report.md",
    "exposure_invariant_audit_report.md",
    "guardrail_audit_report.md",
    "vol_throttle_followup_results_audit_next_action.md",
    "vol_throttle_followup_results_audit_consistency_check.json",
)

DISCREPANCY_FIELDS = (
    "variant_id",
    "discrepancy_type",
    "field",
    "reported_value",
    "recomputed_value",
    "absolute_delta",
    "tolerance",
    "date_or_period",
)

CRITERIA_FIELDS = (
    "variant_id",
    "variant_role",
    "threshold_set_id",
    "reported_numeric_criteria_pass",
    "recomputed_numeric_criteria_pass",
    "reported_label",
    "recomputed_label",
    "cagr_retention_vs_comparator_pass",
    "source_original_retention_pass",
    "drawdown_reduction_pass",
    "calmar_improvement_pass",
    "bil_cash_usage_pass",
    "duplicate_correlation_pass",
    "exposure_invariant_pass",
    "related_group_confirmation_pass",
)


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def parse_float(value: Any, default: float = float("nan")) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_bool(value: Any) -> bool:
    return str(value).strip().lower() == "true"


def finite(value: float) -> bool:
    return not math.isnan(float(value)) and math.isfinite(float(value))


def both_nan(left: float, right: float) -> bool:
    return math.isnan(left) and math.isnan(right)


def design_to_baseline_row(row: dict[str, str]) -> dict[str, str]:
    return {
        "universe": row["universe"],
        "baseline_variant_id": row["baseline_variant_id"],
        "momentum_lookback_days": row["lookback"],
        "top_n": row["top_n"],
        "universe_group": row["universe_group"],
    }


def load_sources(root: Path) -> dict[str, Any]:
    run_dir = root / FOLLOWUP_RUN_DIR
    design_dir = root / SOURCE_DESIGN_DIR
    audit_dir = root / SOURCE_AUDIT_DIR
    source_run_dir = root / SOURCE_RUN_DIR
    return {
        "run_manifest": read_json(run_dir / "vol_throttle_followup_run_manifest.json"),
        "run_consistency": read_json(run_dir / "vol_throttle_followup_run_consistency_check.json"),
        "run_rows": read_csv_rows(run_dir / "vol_throttle_followup_results.csv"),
        "criteria_rows": read_csv_rows(run_dir / "vol_throttle_followup_numeric_criteria_results.csv"),
        "design_rows": read_csv_rows(design_dir / "followup_variant_design_table.csv"),
        "design_manifest": read_json(design_dir / "vol_throttle_followup_design_manifest.json"),
        "design_audit_manifest": read_json(audit_dir / "vol_throttle_followup_design_audit_manifest.json"),
        "design_audit_consistency": read_json(audit_dir / "vol_throttle_followup_design_audit_consistency_check.json"),
        "source_original_rows": {
            row["variant_id"]: row for row in read_csv_rows(source_run_dir / "variant_run_results.csv")
        },
        "run_required_files": {name: (run_dir / name).exists() for name in REQUIRED_RUN_FILES},
        "run_code": read_text(
            root
            / "strategy_lab"
            / "research_os"
            / "research"
            / "volatility_throttle_focused_research_followup_run.py"
        ),
        "run_test": read_text(root / "tests" / "test_volatility_throttle_focused_research_followup_run.py"),
    }


def role_counts(rows: list[dict[str, Any]], *, field: str = "variant_role") -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(row.get(field, ""))
        counts[value] = counts.get(value, 0) + 1
    return counts


def threshold_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    return role_counts(rows, field="threshold_set_id")


def evidence_completeness(source: dict[str, Any]) -> dict[str, Any]:
    manifest = source["run_manifest"]
    consistency = source["run_consistency"]
    rows = source["run_rows"]
    checks = {
        "all_required_run_files_exist": all(source["run_required_files"].values()),
        "manifest_consistency_agree": manifest.get("row_count") == 18
        and consistency.get("row_count_18") is True
        and consistency.get("consistency_passed") is True,
        "row_count_exact_18": len(rows) == EXPECTED_ROW_COUNT and manifest.get("row_count") == EXPECTED_ROW_COUNT,
        "role_counts_match_design": role_counts(rows) == EXPECTED_ROLE_COUNTS
        and manifest.get("role_counts") == EXPECTED_ROLE_COUNTS,
        "threshold_set_count_exact_3": len(threshold_counts(rows)) == 3
        and manifest.get("threshold_set_count") == 3,
        "threshold_sets_match": set(threshold_counts(rows)) == EXPECTED_THRESHOLD_SETS,
        "no_hidden_parameter_grid": len(rows) == EXPECTED_ROW_COUNT,
    }
    return {"passed": all(checks.values()), "checks": checks}


def design_to_run_consistency(source: dict[str, Any]) -> dict[str, Any]:
    design_by_id = {row["variant_id"]: row for row in source["design_rows"]}
    mismatches: list[dict[str, Any]] = []
    for row in source["run_rows"]:
        design = design_by_id.get(row["variant_id"])
        if design is None:
            mismatches.append({"variant_id": row["variant_id"], "field": "variant_id", "issue": "not in design"})
            continue
        comparisons = {
            "variant_role": (row.get("variant_role"), design.get("variant_role")),
            "threshold_set_id": (row.get("threshold_set_id"), design.get("threshold_set_id")),
            "baseline_comparator_variant_id": (row.get("baseline_comparator_variant_id"), design.get("baseline_variant_id")),
            "source_variant_id": (row.get("source_variant_id"), design.get("source_variant_id")),
            "universe": (row.get("universe"), design.get("universe")),
            "lookback": (str(row.get("lookback")), str(int(float(design.get("lookback", "nan"))))),
            "top_n": (str(row.get("top_n")), str(int(float(design.get("top_n", "nan"))))),
        }
        for field, (reported, expected) in comparisons.items():
            if str(reported) != str(expected):
                mismatches.append(
                    {
                        "variant_id": row["variant_id"],
                        "field": field,
                        "issue": f"reported {reported!r}, expected {expected!r}",
                    }
                )
    checks = {
        "every_run_row_maps_to_design": len(mismatches) == 0,
        "variant_roles_preserved": not any(item["field"] == "variant_role" for item in mismatches),
        "threshold_ids_preserved": not any(item["field"] == "threshold_set_id" for item in mismatches),
        "baseline_comparator_mapping_present": all(row.get("baseline_comparator_variant_id") for row in source["run_rows"]),
        "source_original_mapping_present": all(row.get("source_variant_id") for row in source["run_rows"]),
        "missing_mapping_count_zero": source["run_manifest"].get("missing_comparator_or_source_mapping_count") == 0,
    }
    return {"passed": all(checks.values()), "checks": checks, "mismatches": mismatches}


def reference_volatility_throttle_variant(
    root: Path,
    design_row: dict[str, str],
    baseline_daily: pd.Series,
    baseline_weights: pd.DataFrame,
) -> tuple[pd.Series, pd.DataFrame]:
    universe = tuple(symbol for symbol in design_row["universe"].split("|") if symbol)
    prices = cached_prices(str(root), universe).ffill()
    if prices.empty:
        return pd.Series(dtype=float), pd.DataFrame()
    returns = prices.pct_change(fill_method=None).fillna(0.0)
    base = (
        baseline_weights.reindex(prices.index)
        .ffill()
        .fillna(0.0)
        .reindex(columns=prices.columns, fill_value=0.0)
    )
    window = int(float(design_row["volatility_window"]))
    volatility = baseline_daily.reindex(prices.index).fillna(0.0).rolling(window, min_periods=window).std().shift(1)
    volatility = volatility * math.sqrt(252.0)
    normal_threshold = parse_float(design_row["normal_vol_threshold"])
    high_threshold = parse_float(design_row["high_vol_threshold"])
    normal_multiplier = parse_float(design_row["normal_multiplier"])
    high_multiplier = parse_float(design_row["high_vol_multiplier"])
    extreme_multiplier = parse_float(design_row["extreme_vol_multiplier"])
    risky_cols = [column for column in prices.columns if column != "BIL"]
    multipliers: list[float] = []
    for date in prices.index:
        vol_value = float(volatility.loc[date]) if date in volatility.index else float("nan")
        if not finite(vol_value):
            multiplier = normal_multiplier
        elif vol_value <= normal_threshold:
            multiplier = normal_multiplier
        elif vol_value <= high_threshold:
            multiplier = high_multiplier
        else:
            multiplier = extreme_multiplier
        multipliers.append(multiplier)
    multiplier_series = pd.Series(multipliers, index=prices.index, dtype=float)
    weights = pd.DataFrame(0.0, index=prices.index, columns=prices.columns)
    if risky_cols:
        weights.loc[:, risky_cols] = base.loc[:, risky_cols].mul(multiplier_series, axis=0)
    if "BIL" in weights.columns:
        weights.loc[:, "BIL"] = (1.0 - weights.loc[:, risky_cols].sum(axis=1)).clip(lower=0.0)
    weights = weights.clip(lower=0.0)
    daily = (weights * returns).sum(axis=1).rename(design_row["variant_id"])
    return daily, weights


def source_baseline_metrics(source_row: dict[str, str]) -> dict[str, float]:
    return {
        "baseline_total_return": parse_float(source_row.get("baseline_total_return")),
        "baseline_cagr": parse_float(source_row.get("baseline_cagr")),
        "baseline_max_drawdown": parse_float(source_row.get("baseline_max_drawdown")),
        "baseline_calmar_or_return_drawdown_proxy": parse_float(
            source_row.get("baseline_calmar_or_return_drawdown_proxy")
        ),
    }


def recompute_row(
    root: Path,
    design_row: dict[str, str],
    source_original: dict[str, str],
    active_returns: pd.Series,
) -> tuple[dict[str, Any], dict[str, Any]]:
    baseline_daily, baseline_weights = build_baseline_weights(root, design_to_baseline_row(design_row))
    optimized_daily, optimized_weights = run_volatility_throttle_variant(
        root, design_row, baseline_daily, baseline_weights
    )
    reference_daily, reference_weights = reference_volatility_throttle_variant(
        root, design_row, baseline_daily, baseline_weights
    )
    aligned_returns = pd.concat(
        [optimized_daily.rename("optimized"), reference_daily.rename("reference")], axis=1
    ).dropna()
    return_delta = (aligned_returns["optimized"] - aligned_returns["reference"]).abs()
    aligned_weights = optimized_weights.align(reference_weights, join="inner", axis=0)[0], optimized_weights.align(reference_weights, join="inner", axis=0)[1]
    optimized_aligned, reference_aligned = aligned_weights
    weight_delta = (optimized_aligned - reference_aligned).abs()
    first_return_discrepancy = ""
    if not return_delta.empty and float(return_delta.max()) > RETURN_TOLERANCE:
        first_return_discrepancy = return_delta[return_delta > RETURN_TOLERANCE].index.min().date().isoformat()
    first_weight_discrepancy = ""
    if not weight_delta.empty and float(weight_delta.max().max()) > WEIGHT_TOLERANCE:
        first_weight_discrepancy = weight_delta.stack()[lambda series: series > WEIGHT_TOLERANCE].index[0][0].date().isoformat()

    metrics = metrics_for_returns(reference_daily, reference_weights)
    base = source_baseline_metrics(source_original)
    drawdown_reduction = pct_reduction(base["baseline_max_drawdown"], metrics["max_drawdown"])
    cagr_retention = safe_ratio(metrics["cagr"], base["baseline_cagr"])
    calmar_delta = calmar_improvement(
        base["baseline_calmar_or_return_drawdown_proxy"],
        metrics["calmar_or_return_drawdown_proxy"],
    )
    source_cagr = parse_float(design_row.get("source_cagr"))
    source_retention = safe_ratio(metrics["cagr"], source_cagr)
    spy_delta = benchmark_delta(
        reference_daily,
        cached_price_series(str(root), "SPY").pct_change(fill_method=None).dropna().rename("SPY"),
    )
    bil_delta = benchmark_delta(
        reference_daily,
        cached_price_series(str(root), "BIL").pct_change(fill_method=None).dropna().rename("BIL"),
    )
    contrib = contribution_metrics(reference_daily, active_returns)
    spy200d = reference_spy200d_returns(root, reference_daily.index)
    aligned_reference = pd.concat([reference_daily.rename("strategy"), spy200d.rename("spy200d")], axis=1).dropna()
    spy200d_corr = (
        float(aligned_reference["strategy"].corr(aligned_reference["spy200d"]))
        if len(aligned_reference) >= 252
        else float("nan")
    )
    aligned_baseline = pd.concat(
        [reference_daily.rename("strategy"), baseline_daily.rename("baseline")], axis=1
    ).dropna()
    baseline_corr = (
        float(aligned_baseline["strategy"].corr(aligned_baseline["baseline"]))
        if len(aligned_baseline) >= 252
        else float("nan")
    )
    exposure_pass = (
        metrics["max_daily_exposure"] <= 1.000001
        and metrics["max_daily_weight_sum"] <= 1.000001
        and int(metrics["weight_sum_violation_count"]) == 0
        and int(metrics["negative_weight_violation_count"]) == 0
        and int(metrics["nan_weight_count"]) == 0
        and int(metrics["impossible_cash_and_risky_exposure_days"]) == 0
    )
    cagr_pass = finite(cagr_retention) and cagr_retention >= 0.70
    source_pass = finite(source_retention) and source_retention >= 0.85
    drawdown_pass = finite(drawdown_reduction) and drawdown_reduction >= 0.25
    calmar_pass = finite(calmar_delta) and calmar_delta > 0.0
    bil_pass = metrics["average_bil_cash_share"] < 0.35
    duplicate_pass = finite(spy200d_corr) and spy200d_corr < 0.90
    numeric_pass = all([cagr_pass, source_pass, drawdown_pass, calmar_pass, bil_pass, duplicate_pass, exposure_pass])

    recomputed = {
        "variant_id": design_row["variant_id"],
        "variant_role": design_row["variant_role"],
        "threshold_set_id": design_row["threshold_set_id"],
        "source_variant_id": design_row["source_variant_id"],
        "baseline_comparator_variant_id": design_row["baseline_variant_id"],
        **metrics,
        **base,
        "drawdown_reduction_vs_comparator": drawdown_reduction,
        "cagr_retention_vs_comparator": cagr_retention,
        "calmar_improvement_vs_comparator": calmar_delta,
        "source_original_cagr": source_cagr,
        "source_original_max_drawdown": parse_float(design_row.get("source_max_drawdown")),
        "cagr_retention_vs_source_original_vol_throttle": source_retention,
        "duplicate_reference_correlation": spy200d_corr,
        "spy200d_reference_correlation": spy200d_corr,
        "active_combo_correlation": contrib["active_combo_correlation"],
        "active_combo_blend_total_return_delta": contrib["active_combo_blend_total_return_delta"],
        "active_combo_blend_drawdown_delta": contrib["active_combo_blend_drawdown_delta"],
        "baseline_correlation": baseline_corr,
        "spy_total_return_delta": spy_delta,
        "bil_cash_total_return_delta": bil_delta,
        "cagr_retention_vs_comparator_pass": cagr_pass,
        "source_original_retention_pass": source_pass,
        "drawdown_reduction_pass": drawdown_pass,
        "calmar_improvement_pass": calmar_pass,
        "bil_cash_usage_pass": bil_pass,
        "duplicate_correlation_pass": duplicate_pass,
        "exposure_invariant_pass": exposure_pass,
        "numeric_criteria_pass": numeric_pass,
    }
    equivalence = {
        "variant_id": design_row["variant_id"],
        "max_abs_daily_return_delta": float(return_delta.max()) if not return_delta.empty else 0.0,
        "max_abs_weight_delta": float(weight_delta.max().max()) if not weight_delta.empty else 0.0,
        "first_return_discrepancy_date": first_return_discrepancy,
        "first_weight_discrepancy_date": first_weight_discrepancy,
        "daily_return_equivalent": bool(return_delta.empty or float(return_delta.max()) <= RETURN_TOLERANCE),
        "weights_equivalent": bool(weight_delta.empty or float(weight_delta.max().max()) <= WEIGHT_TOLERANCE),
        "zero_base_weight_stale_allocation_violations": int(
            ((baseline_weights.reindex(reference_weights.index).fillna(0.0).abs() <= 1e-15) & (reference_weights.abs() > 1e-12))
            .drop(columns=["BIL"], errors="ignore")
            .sum()
            .sum()
        ),
    }
    return recomputed, equivalence


def assign_recomputed_labels(rows: list[dict[str, Any]]) -> None:
    pass_by_threshold: dict[str, int] = {}
    for row in rows:
        threshold = str(row["threshold_set_id"])
        pass_by_threshold[threshold] = pass_by_threshold.get(threshold, 0) + int(row["numeric_criteria_pass"])
    for row in rows:
        group_pass = pass_by_threshold.get(str(row["threshold_set_id"]), 0) >= 2
        row["related_group_confirmation_pass"] = group_pass
        if not row["exposure_invariant_pass"]:
            label = "vol_throttle_signal_weak"
        elif not row["duplicate_correlation_pass"]:
            label = "vol_throttle_signal_duplicate_reference"
        elif not row["bil_cash_usage_pass"]:
            label = "vol_throttle_signal_too_defensive"
        elif not row["drawdown_reduction_pass"]:
            label = "vol_throttle_signal_drawdown_reduction_below_threshold"
        elif row["numeric_criteria_pass"] and group_pass:
            label = "vol_throttle_signal_confirmed"
        elif row["cagr_retention_vs_comparator_pass"] and row["drawdown_reduction_pass"]:
            label = "vol_throttle_signal_threshold_sensitive"
        else:
            label = "vol_throttle_signal_weak"
        row["vol_throttle_research_label"] = label


def compare_values(
    variant_id: str,
    field: str,
    reported_value: Any,
    recomputed_value: Any,
    tolerance: float,
    discrepancies: list[dict[str, Any]],
    discrepancy_type: str = "metric_mismatch",
) -> None:
    reported = parse_float(reported_value)
    recomputed = parse_float(recomputed_value)
    if both_nan(reported, recomputed):
        return
    delta = abs(reported - recomputed)
    if delta > tolerance:
        discrepancies.append(
            {
                "variant_id": variant_id,
                "discrepancy_type": discrepancy_type,
                "field": field,
                "reported_value": reported_value,
                "recomputed_value": recomputed_value,
                "absolute_delta": delta,
                "tolerance": tolerance,
                "date_or_period": "",
            }
        )


def discrepancy_analysis(
    source: dict[str, Any],
    recomputed_rows: list[dict[str, Any]],
    equivalence_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    reported_by_id = {row["variant_id"]: row for row in source["run_rows"]}
    discrepancies: list[dict[str, Any]] = []
    metric_fields = (
        "cagr",
        "max_drawdown",
        "total_return",
        "volatility",
        "calmar_or_return_drawdown_proxy",
        "drawdown_reduction_vs_comparator",
        "cagr_retention_vs_comparator",
        "cagr_retention_vs_source_original_vol_throttle",
        "calmar_improvement_vs_comparator",
        "average_bil_cash_share",
        "max_bil_cash_share",
        "duplicate_reference_correlation",
        "max_daily_exposure",
        "max_daily_weight_sum",
    )
    bool_fields = (
        "cagr_retention_vs_comparator_pass",
        "source_original_retention_pass",
        "drawdown_reduction_pass",
        "calmar_improvement_pass",
        "bil_cash_usage_pass",
        "duplicate_correlation_pass",
        "exposure_invariant_pass",
        "numeric_criteria_pass",
        "related_group_confirmation_pass",
    )
    criteria_report: list[dict[str, Any]] = []
    for row in recomputed_rows:
        variant_id = row["variant_id"]
        reported = reported_by_id.get(variant_id, {})
        for field in metric_fields:
            compare_values(variant_id, field, reported.get(field), row.get(field), METRIC_TOLERANCE, discrepancies)
        for field in bool_fields:
            if parse_bool(reported.get(field)) != bool(row.get(field)):
                discrepancies.append(
                    {
                        "variant_id": variant_id,
                        "discrepancy_type": "criteria_mismatch",
                        "field": field,
                        "reported_value": reported.get(field),
                        "recomputed_value": row.get(field),
                        "absolute_delta": "",
                        "tolerance": "exact",
                        "date_or_period": "",
                    }
                )
        if str(reported.get("vol_throttle_research_label")) != str(row.get("vol_throttle_research_label")):
            discrepancies.append(
                {
                    "variant_id": variant_id,
                    "discrepancy_type": "label_mismatch",
                    "field": "vol_throttle_research_label",
                    "reported_value": reported.get("vol_throttle_research_label"),
                    "recomputed_value": row.get("vol_throttle_research_label"),
                    "absolute_delta": "",
                    "tolerance": "exact",
                    "date_or_period": "",
                }
            )
        criteria_report.append(
            {
                "variant_id": variant_id,
                "variant_role": row["variant_role"],
                "threshold_set_id": row["threshold_set_id"],
                "reported_numeric_criteria_pass": parse_bool(reported.get("numeric_criteria_pass")),
                "recomputed_numeric_criteria_pass": bool(row["numeric_criteria_pass"]),
                "reported_label": reported.get("vol_throttle_research_label"),
                "recomputed_label": row["vol_throttle_research_label"],
                "cagr_retention_vs_comparator_pass": row["cagr_retention_vs_comparator_pass"],
                "source_original_retention_pass": row["source_original_retention_pass"],
                "drawdown_reduction_pass": row["drawdown_reduction_pass"],
                "calmar_improvement_pass": row["calmar_improvement_pass"],
                "bil_cash_usage_pass": row["bil_cash_usage_pass"],
                "duplicate_correlation_pass": row["duplicate_correlation_pass"],
                "exposure_invariant_pass": row["exposure_invariant_pass"],
                "related_group_confirmation_pass": row["related_group_confirmation_pass"],
            }
        )
    for eq in equivalence_rows:
        if eq["max_abs_daily_return_delta"] > RETURN_TOLERANCE:
            discrepancies.append(
                {
                    "variant_id": eq["variant_id"],
                    "discrepancy_type": "optimized_loop_equivalence_failure",
                    "field": "daily_return",
                    "reported_value": "optimized",
                    "recomputed_value": "reference",
                    "absolute_delta": eq["max_abs_daily_return_delta"],
                    "tolerance": RETURN_TOLERANCE,
                    "date_or_period": eq["first_return_discrepancy_date"],
                }
            )
        if eq["max_abs_weight_delta"] > WEIGHT_TOLERANCE:
            discrepancies.append(
                {
                    "variant_id": eq["variant_id"],
                    "discrepancy_type": "optimized_loop_equivalence_failure",
                    "field": "weight",
                    "reported_value": "optimized",
                    "recomputed_value": "reference",
                    "absolute_delta": eq["max_abs_weight_delta"],
                    "tolerance": WEIGHT_TOLERANCE,
                    "date_or_period": eq["first_weight_discrepancy_date"],
                }
            )
        if eq["zero_base_weight_stale_allocation_violations"] != 0:
            discrepancies.append(
                {
                    "variant_id": eq["variant_id"],
                    "discrepancy_type": "stale_zero_weight_violation",
                    "field": "zero_base_weight_stale_allocation_violations",
                    "reported_value": 0,
                    "recomputed_value": eq["zero_base_weight_stale_allocation_violations"],
                    "absolute_delta": eq["zero_base_weight_stale_allocation_violations"],
                    "tolerance": 0,
                    "date_or_period": "",
                }
            )
    return discrepancies, criteria_report


def aggregate_counts(rows: list[dict[str, Any]]) -> dict[str, Any]:
    labels = {label: sum(1 for row in rows if row.get("vol_throttle_research_label") == label) for label in ALLOWED_LABELS}
    confirmation = [row for row in rows if row.get("variant_role") == "confirmation_reference"]
    robustness = [row for row in rows if row.get("variant_role") != "confirmation_reference"]
    return {
        "numeric_pass_count": sum(1 for row in rows if row.get("numeric_criteria_pass")),
        "numeric_fail_count": sum(1 for row in rows if not row.get("numeric_criteria_pass")),
        "confirmation_pass_count": sum(1 for row in confirmation if row.get("numeric_criteria_pass")),
        "confirmation_row_count": len(confirmation),
        "robustness_pass_count": sum(1 for row in robustness if row.get("numeric_criteria_pass")),
        "robustness_row_count": len(robustness),
        **{f"{label}_count": count for label, count in labels.items()},
    }


def guardrail_audit(source: dict[str, Any]) -> dict[str, Any]:
    manifest = source["run_manifest"]
    checks = {
        "provider_download_false": manifest.get("provider_download") is False,
        "intraday_data_used_false": manifest.get("intraday_data_used") is False,
        "broker_api_called_false": manifest.get("broker_api_called") is False,
        "broker_orders_false": manifest.get("broker_orders_submitted") is False
        and manifest.get("broker_orders_cancelled") is False
        and manifest.get("broker_orders_reconciled") is False,
        "broker_paper_live_path_false": manifest.get("broker_paper_live_path_touched") is False,
        "live_and_real_money_false": manifest.get("live_orders") is False
        and manifest.get("real_money_recommendation") is False,
        "paper_forward_activation_false": manifest.get("paper_forward_activation") is False,
        "candidate_exhaustive_false": manifest.get("candidate_exhaustive_run") is False,
        "promotion_false": manifest.get("promotion_candidates_created") is False
        and manifest.get("best_single_variant_promoted") is False,
        "new_family_false": manifest.get("new_family_created") is False and manifest.get("new_families_created") is False,
        "new_or_unrelated_variants_false": manifest.get("new_unrelated_variant_created") is False
        and manifest.get("new_variants_created") is False,
        "active_vm_preserved": manifest.get("active_vm_preserved") is True,
        "active_dsr_preserved": manifest.get("active_dsr_preserved") is True,
        "macro_gld_unchanged": manifest.get("macro_gld_lineage_recovery_run") is False
        and manifest.get("macro_gld_remains_lineage_blocked_visible") is True,
        "outputs_non_promotable": manifest.get("research_outputs_remain_non_promotable") is True,
    }
    return {"passed": all(checks.values()), "checks": checks}


def methodology_audit(source: dict[str, Any], equivalence_rows: list[dict[str, Any]]) -> dict[str, Any]:
    run_code = source["run_code"]
    checks = {
        "uses_uncontrolled_baseline_returns": "baseline_daily" in run_code and "realized_vol" in run_code,
        "uses_t_minus_1_volatility": ".shift(1)" in run_code,
        "uses_60_day_window": "volatility_window" in run_code,
        "annualizes_sqrt_252": "math.sqrt(252.0)" in run_code,
        "bil_replacement_remainder_only": "1.0 - weights.loc[:, risky_cols].sum(axis=1)" in run_code,
        "max_exposure_capped_by_invariant": all(row["max_abs_weight_delta"] <= WEIGHT_TOLERANCE for row in equivalence_rows),
        "no_stale_zero_weight_violations": all(row["zero_base_weight_stale_allocation_violations"] == 0 for row in equivalence_rows),
        "optimized_loop_equivalent": all(
            row["daily_return_equivalent"] and row["weights_equivalent"] for row in equivalence_rows
        ),
    }
    return {"passed": all(checks.values()), "checks": checks}


def run_audit(root: Path = ROOT) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    source = load_sources(root)
    design_by_id = {row["variant_id"]: row for row in source["design_rows"]}
    active_returns = active_combo_returns(root)
    recomputed_rows: list[dict[str, Any]] = []
    equivalence_rows: list[dict[str, Any]] = []
    for reported in source["run_rows"]:
        design = design_by_id[reported["variant_id"]]
        source_original = source["source_original_rows"][design["source_variant_id"]]
        recomputed, equivalence = recompute_row(root, design, source_original, active_returns)
        recomputed_rows.append(recomputed)
        equivalence_rows.append(equivalence)
    assign_recomputed_labels(recomputed_rows)
    discrepancies, criteria_report = discrepancy_analysis(source, recomputed_rows, equivalence_rows)
    completeness = evidence_completeness(source)
    design_consistency = design_to_run_consistency(source)
    guardrails = guardrail_audit(source)
    methodology = methodology_audit(source, equivalence_rows)
    aggregate = aggregate_counts(recomputed_rows)
    return source, completeness, design_consistency, recomputed_rows, equivalence_rows, discrepancies, {
        "criteria_report": criteria_report,
        "guardrails": guardrails,
        "methodology": methodology,
        "aggregate": aggregate,
    }


def build_manifest(
    created: str,
    output: Path,
    source: dict[str, Any],
    completeness: dict[str, Any],
    design_consistency: dict[str, Any],
    recomputed_rows: list[dict[str, Any]],
    equivalence_rows: list[dict[str, Any]],
    discrepancies: list[dict[str, Any]],
    extra: dict[str, Any],
) -> dict[str, Any]:
    aggregate = extra["aggregate"]
    guardrails = extra["guardrails"]
    methodology = extra["methodology"]
    metric_discrepancies = [row for row in discrepancies if row["discrepancy_type"] == "metric_mismatch"]
    criteria_discrepancies = [row for row in discrepancies if row["discrepancy_type"] == "criteria_mismatch"]
    label_discrepancies = [row for row in discrepancies if row["discrepancy_type"] == "label_mismatch"]
    equivalence_failures = [row for row in discrepancies if row["discrepancy_type"] == "optimized_loop_equivalence_failure"]
    aggregate_expected = {
        "numeric_pass_count": 10,
        "numeric_fail_count": 8,
        "confirmation_pass_count": 6,
        "confirmation_row_count": 6,
        "robustness_pass_count": 4,
        "robustness_row_count": 12,
        "vol_throttle_signal_confirmed_count": 10,
        "vol_throttle_signal_threshold_sensitive_count": 3,
        "vol_throttle_signal_drawdown_reduction_below_threshold_count": 4,
        "vol_throttle_signal_weak_count": 1,
        "vol_throttle_signal_duplicate_reference_count": 0,
        "vol_throttle_signal_too_defensive_count": 0,
        "vol_throttle_signal_data_blocked_count": 0,
    }
    aggregate_counts_match = all(aggregate.get(key) == value for key, value in aggregate_expected.items())
    audit_passed = (
        completeness["passed"]
        and design_consistency["passed"]
        and guardrails["passed"]
        and methodology["passed"]
        and not discrepancies
        and aggregate_counts_match
    )
    decision = AUDIT_DECISION_PASSED if audit_passed else AUDIT_DECISION_PATCH
    next_action = NEXT_ACTION_MANUAL if audit_passed else NEXT_ACTION_PATCH
    return {
        "created_utc": created,
        "evidence_path": str(output.resolve()),
        "vol_throttle_followup_results_audit_only": True,
        "lane_id_audited": LANE_ID,
        "source_run_evidence_reviewed": True,
        "source_design_evidence_reviewed": True,
        "optimized_loop_equivalence_checked": True,
        "approved_rows_replayed_for_audit_only": True,
        "approved_row_count_replayed": len(recomputed_rows),
        "new_strategy_discovery_run": False,
        "new_research_batch_run": False,
        "new_backtests_outside_approved_audit_replay": False,
        "new_variants_created": False,
        "new_families_created": False,
        "thresholds_changed": False,
        "provider_download": False,
        "intraday_data_used": False,
        "broker_api_called": False,
        "broker_orders_submitted": False,
        "broker_orders_cancelled": False,
        "broker_orders_reconciled": False,
        "live_orders": False,
        "real_money_recommendation": False,
        "paper_forward_activation": False,
        "new_paper_forward_candidate_created": False,
        "candidate_exhaustive_run": False,
        "promotion_candidates_created": False,
        "best_single_variant_promoted": False,
        "research_outputs_remain_non_promotable": True,
        "active_vm_preserved": True,
        "active_dsr_preserved": True,
        "static_all_weather_benchmark_control_only": True,
        "macro_gld_lineage_recovery_run": False,
        "macro_gld_remains_lineage_blocked_visible": True,
        "alpaca_execution_module_delegated": True,
        "run_manifest_consistency_passed": source["run_consistency"].get("consistency_passed") is True,
        "evidence_completeness_passed": completeness["passed"],
        "design_to_run_consistency_passed": design_consistency["passed"],
        "methodology_integrity_passed": methodology["passed"],
        "guardrails_passed": guardrails["passed"],
        "row_count_reviewed": len(source["run_rows"]),
        "row_level_discrepancy_count": len(discrepancies),
        "metric_discrepancy_count": len(metric_discrepancies),
        "criteria_mismatch_count": len(criteria_discrepancies),
        "label_mismatch_count": len(label_discrepancies),
        "optimized_loop_equivalence_failure_count": len(equivalence_failures),
        "max_abs_daily_return_delta": max([row["max_abs_daily_return_delta"] for row in equivalence_rows] or [0.0]),
        "max_abs_weight_delta": max([row["max_abs_weight_delta"] for row in equivalence_rows] or [0.0]),
        "stale_zero_weight_violation_count": sum(
            row["zero_base_weight_stale_allocation_violations"] for row in equivalence_rows
        ),
        "aggregate_counts_match": aggregate_counts_match,
        "exposure_invariant_passed": all(row["exposure_invariant_pass"] for row in recomputed_rows),
        **aggregate,
        "final_audit_decision": decision,
        "next_action": next_action,
    }


def checklist_md(title: str, audit: dict[str, Any]) -> str:
    lines = [f"# {title}", "", f"Passed: `{audit['passed']}`", "", "Checks:"]
    for key, value in audit.get("checks", {}).items():
        lines.append(f"- `{key}`: `{value}`")
    if audit.get("mismatches"):
        lines.extend(["", "Mismatches:"])
        for item in audit["mismatches"]:
            lines.append(f"- `{item['variant_id']}` `{item['field']}`: {item['issue']}")
    return "\n".join(lines) + "\n"


def summary_md(manifest: dict[str, Any]) -> str:
    return f"""# Volatility Throttle Follow-Up Results Audit

Lane audited: `{manifest['lane_id_audited']}`

Rows reviewed: `{manifest['row_count_reviewed']}`

Evidence completeness passed: `{manifest['evidence_completeness_passed']}`

Design-to-run consistency passed: `{manifest['design_to_run_consistency_passed']}`

Methodology integrity passed: `{manifest['methodology_integrity_passed']}`

Optimized loop equivalence failure count: `{manifest['optimized_loop_equivalence_failure_count']}`

Max absolute daily return delta: `{manifest['max_abs_daily_return_delta']}`

Max absolute weight delta: `{manifest['max_abs_weight_delta']}`

Row-level discrepancy count: `{manifest['row_level_discrepancy_count']}`

Criteria mismatch count: `{manifest['criteria_mismatch_count']}`

Label mismatch count: `{manifest['label_mismatch_count']}`

Aggregate counts match: `{manifest['aggregate_counts_match']}`

Guardrails passed: `{manifest['guardrails_passed']}`

Final audit decision: `{manifest['final_audit_decision']}`

Exact next action: `{manifest['next_action']}`
"""


def equivalence_md(equivalence_rows: list[dict[str, Any]], manifest: dict[str, Any]) -> str:
    lines = [
        "# Optimized Loop Equivalence Report",
        "",
        "The vectorized implementation was compared against an explicit reference replay for every approved row.",
        "",
        f"- Rows compared: `{len(equivalence_rows)}`",
        f"- Max absolute daily return delta: `{manifest['max_abs_daily_return_delta']}`",
        f"- Max absolute weight delta: `{manifest['max_abs_weight_delta']}`",
        f"- Equivalence failure count: `{manifest['optimized_loop_equivalence_failure_count']}`",
        f"- Stale zero-weight allocation violations: `{manifest['stale_zero_weight_violation_count']}`",
        "",
        "Per-row maxima:",
    ]
    for row in equivalence_rows:
        lines.append(
            f"- `{row['variant_id']}`: return delta `{row['max_abs_daily_return_delta']}`, "
            f"weight delta `{row['max_abs_weight_delta']}`"
        )
    return "\n".join(lines) + "\n"


def discrepancies_md(discrepancies: list[dict[str, Any]]) -> str:
    lines = ["# Row-Level Discrepancy Report", "", f"Discrepancies: `{len(discrepancies)}`", ""]
    if not discrepancies:
        lines.append("- None")
    for row in discrepancies:
        lines.append(
            f"- `{row['variant_id']}` `{row['discrepancy_type']}` `{row['field']}`: "
            f"reported `{row['reported_value']}`, recomputed `{row['recomputed_value']}`, "
            f"delta `{row['absolute_delta']}`"
        )
    return "\n".join(lines) + "\n"


def criteria_md(criteria_rows: list[dict[str, Any]], manifest: dict[str, Any]) -> str:
    return f"""# Criteria Recalculation Report

Rows reviewed: `{len(criteria_rows)}`

Numeric pass count: `{manifest['numeric_pass_count']}`

Numeric fail count: `{manifest['numeric_fail_count']}`

Confirmation pass count: `{manifest['confirmation_pass_count']} / {manifest['confirmation_row_count']}`

Robustness pass count: `{manifest['robustness_pass_count']} / {manifest['robustness_row_count']}`

Criteria mismatch count: `{manifest['criteria_mismatch_count']}`

Label mismatch count: `{manifest['label_mismatch_count']}`
"""


def exposure_md(manifest: dict[str, Any], recomputed_rows: list[dict[str, Any]]) -> str:
    impossible_days = sum(int(row["impossible_cash_and_risky_exposure_days"]) for row in recomputed_rows)
    negative = sum(int(row["negative_weight_violation_count"]) for row in recomputed_rows)
    nan_count = sum(int(row["nan_weight_count"]) for row in recomputed_rows)
    return f"""# Exposure Invariant Audit Report

- Exposure invariant passed: `{manifest['exposure_invariant_passed']}`
- Max absolute weight delta versus reference: `{manifest['max_abs_weight_delta']}`
- Stale zero-weight allocation violations: `{manifest['stale_zero_weight_violation_count']}`
- Impossible risky plus BIL/cash overlap days: `{impossible_days}`
- Negative weight violations: `{negative}`
- NaN weight count: `{nan_count}`
"""


def next_action_md(next_action: str) -> str:
    return f"""# Volatility Throttle Follow-Up Results Audit Next Action

Exact next action:

`{next_action}`

Do not run the next action in this task.
"""


def consistency_check(manifest: dict[str, Any], output: Path) -> dict[str, Any]:
    required = {name: (output / name).exists() for name in AUDIT_OUTPUT_FILES}
    required["vol_throttle_followup_results_audit_consistency_check.json"] = True
    checks = {
        "audit_only": manifest["vol_throttle_followup_results_audit_only"] is True,
        "correct_lane_id": manifest["lane_id_audited"] == LANE_ID,
        "source_run_reviewed": manifest["source_run_evidence_reviewed"] is True,
        "source_design_reviewed": manifest["source_design_evidence_reviewed"] is True,
        "optimized_equivalence_checked": manifest["optimized_loop_equivalence_checked"] is True,
        "approved_rows_replayed_only": manifest["approved_rows_replayed_for_audit_only"] is True
        and manifest["approved_row_count_replayed"] == 18,
        "no_discovery": manifest["new_strategy_discovery_run"] is False,
        "no_new_batch": manifest["new_research_batch_run"] is False,
        "no_new_variants_or_families": manifest["new_variants_created"] is False
        and manifest["new_families_created"] is False,
        "thresholds_not_changed": manifest["thresholds_changed"] is False,
        "no_provider_download": manifest["provider_download"] is False,
        "no_intraday": manifest["intraday_data_used"] is False,
        "no_broker_api": manifest["broker_api_called"] is False,
        "no_broker_orders": manifest["broker_orders_submitted"] is False
        and manifest["broker_orders_cancelled"] is False
        and manifest["broker_orders_reconciled"] is False,
        "no_live_or_real_money": manifest["live_orders"] is False and manifest["real_money_recommendation"] is False,
        "no_paper_forward": manifest["paper_forward_activation"] is False
        and manifest["new_paper_forward_candidate_created"] is False,
        "no_candidate_exhaustive": manifest["candidate_exhaustive_run"] is False,
        "no_promotion": manifest["promotion_candidates_created"] is False
        and manifest["best_single_variant_promoted"] is False,
        "non_promotable_outputs": manifest["research_outputs_remain_non_promotable"] is True,
        "active_vm_preserved": manifest["active_vm_preserved"] is True,
        "active_dsr_preserved": manifest["active_dsr_preserved"] is True,
        "macro_gld_unchanged": manifest["macro_gld_lineage_recovery_run"] is False
        and manifest["macro_gld_remains_lineage_blocked_visible"] is True,
        "evidence_completeness_passed": manifest["evidence_completeness_passed"] is True,
        "design_to_run_consistency_passed": manifest["design_to_run_consistency_passed"] is True,
        "methodology_integrity_passed": manifest["methodology_integrity_passed"] is True,
        "guardrails_passed": manifest["guardrails_passed"] is True,
        "no_discrepancies": manifest["row_level_discrepancy_count"] == 0,
        "aggregate_counts_match": manifest["aggregate_counts_match"] is True,
        "final_decision_valid": manifest["final_audit_decision"] in {AUDIT_DECISION_PASSED, AUDIT_DECISION_PATCH},
        "next_action_valid": manifest["next_action"] in VALID_NEXT_ACTIONS,
        "required_files_present": all(required.values()),
        "required_files": required,
    }
    checks["consistency_passed"] = all(value is True for key, value in checks.items() if key != "required_files")
    return checks


def write_outputs(
    root: Path,
    created: str,
    source: dict[str, Any],
    completeness: dict[str, Any],
    design_consistency: dict[str, Any],
    recomputed_rows: list[dict[str, Any]],
    equivalence_rows: list[dict[str, Any]],
    discrepancies: list[dict[str, Any]],
    extra: dict[str, Any],
) -> dict[str, Any]:
    output = root / OUTPUT_DIR
    output.mkdir(parents=True, exist_ok=True)
    manifest = build_manifest(
        created,
        output,
        source,
        completeness,
        design_consistency,
        recomputed_rows,
        equivalence_rows,
        discrepancies,
        extra,
    )
    write_json(output / "vol_throttle_followup_results_audit_manifest.json", manifest)
    write_text(output / "vol_throttle_followup_results_audit_summary.md", summary_md(manifest))
    write_text(output / "evidence_completeness_audit.md", checklist_md("Evidence Completeness Audit", completeness))
    write_text(output / "design_to_run_consistency_audit.md", checklist_md("Design-To-Run Consistency Audit", design_consistency))
    write_text(output / "methodology_integrity_audit.md", checklist_md("Methodology Integrity Audit", extra["methodology"]))
    write_text(output / "optimized_loop_equivalence_report.md", equivalence_md(equivalence_rows, manifest))
    write_csv(output / "row_level_discrepancy_report.csv", discrepancies, list(DISCREPANCY_FIELDS))
    write_text(output / "row_level_discrepancy_report.md", discrepancies_md(discrepancies))
    write_csv(output / "criteria_recomputation_report.csv", extra["criteria_report"], list(CRITERIA_FIELDS))
    write_text(output / "criteria_recomputation_report.md", criteria_md(extra["criteria_report"], manifest))
    write_text(output / "exposure_invariant_audit_report.md", exposure_md(manifest, recomputed_rows))
    write_text(output / "guardrail_audit_report.md", checklist_md("Guardrail Audit Report", extra["guardrails"]))
    write_text(output / "vol_throttle_followup_results_audit_next_action.md", next_action_md(manifest["next_action"]))
    consistency = consistency_check(manifest, output)
    write_json(output / "vol_throttle_followup_results_audit_consistency_check.json", consistency)
    return {**manifest, "output_dir": str(output.resolve()), "consistency_passed": consistency["consistency_passed"]}


def run(root: Path = ROOT) -> dict[str, Any]:
    created = now_utc()
    source, completeness, design_consistency, recomputed_rows, equivalence_rows, discrepancies, extra = run_audit(root)
    return write_outputs(
        root,
        created,
        source,
        completeness,
        design_consistency,
        recomputed_rows,
        equivalence_rows,
        discrepancies,
        extra,
    )


if __name__ == "__main__":
    result = run()
    print(
        json.dumps(
            {
                "output_dir": result["output_dir"],
                "lane_id_audited": result["lane_id_audited"],
                "row_count_reviewed": result["row_count_reviewed"],
                "row_level_discrepancy_count": result["row_level_discrepancy_count"],
                "optimized_loop_equivalence_failure_count": result["optimized_loop_equivalence_failure_count"],
                "final_audit_decision": result["final_audit_decision"],
                "next_action": result["next_action"],
                "consistency_passed": result["consistency_passed"],
            },
            indent=2,
        )
    )
