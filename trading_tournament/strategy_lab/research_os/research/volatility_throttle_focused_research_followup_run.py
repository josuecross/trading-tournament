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
    WEIGHT_TOLERANCE,
    active_combo_returns,
    available_symbols,
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
from strategy_lab.research_os.research.volatility_throttle_focused_research_followup_design import LANE_ID


SOURCE_DESIGN_DIR = (
    Path("evidence")
    / "research_recovery"
    / "volatility_throttle_focused_research_followup_design"
    / "latest"
)
SOURCE_AUDIT_DIR = (
    Path("evidence")
    / "research_recovery"
    / "volatility_throttle_focused_research_followup_design_audit"
    / "latest"
)
SOURCE_RUN_DIR = Path("evidence") / "research_recovery" / "high_return_tactical_risk_control_lane_run" / "latest"
OUTPUT_DIR = (
    Path("evidence")
    / "research_recovery"
    / "volatility_throttle_focused_research_followup_run"
    / "latest"
)

NEXT_ACTION_AUDIT = "audit_volatility_throttle_focused_research_followup_results"
NEXT_ACTION_FIX = "fix_volatility_throttle_focused_research_followup_methodology_issue"
NEXT_ACTION_MANUAL = "manual_review_required_after_volatility_throttle_followup_run"
NEXT_ACTION_PAUSE = "pause_expansion_and_wait_for_manual_direction"
VALID_NEXT_ACTIONS = {NEXT_ACTION_AUDIT, NEXT_ACTION_FIX, NEXT_ACTION_MANUAL, NEXT_ACTION_PAUSE}

EXPECTED_ROW_COUNT = 18
EXPECTED_THRESHOLD_SETS = {
    "original_25_35_100_50_25",
    "less_defensive_30_40_100_60_30",
    "more_defensive_20_30_100_40_20",
}
EXPECTED_ROLE_COUNTS = {
    "confirmation_reference": 6,
    "minimal_robustness_less_defensive": 6,
    "minimal_robustness_more_defensive": 6,
}

ALLOWED_LABELS = {
    "vol_throttle_signal_confirmed",
    "vol_throttle_signal_threshold_sensitive",
    "vol_throttle_signal_too_defensive",
    "vol_throttle_signal_drawdown_reduction_below_threshold",
    "vol_throttle_signal_duplicate_reference",
    "vol_throttle_signal_weak",
    "vol_throttle_signal_data_blocked",
}

RESULT_FIELDS = (
    "lane_id",
    "variant_id",
    "variant_role",
    "threshold_set_id",
    "source_variant_id",
    "baseline_comparator_variant_id",
    "source_evidence_path",
    "universe_group",
    "universe",
    "lookback",
    "top_n",
    "start_date",
    "end_date",
    "cagr",
    "max_drawdown",
    "total_return",
    "volatility",
    "calmar_or_return_drawdown_proxy",
    "baseline_cagr",
    "baseline_max_drawdown",
    "baseline_total_return",
    "baseline_calmar_or_return_drawdown_proxy",
    "drawdown_reduction_vs_comparator",
    "cagr_retention_vs_comparator",
    "calmar_improvement_vs_comparator",
    "source_original_cagr",
    "source_original_max_drawdown",
    "cagr_retention_vs_source_original_vol_throttle",
    "average_bil_cash_share",
    "max_bil_cash_share",
    "average_exposure",
    "max_daily_exposure",
    "max_daily_weight_sum",
    "average_weight_sum",
    "weight_sum_violation_count",
    "negative_weight_violation_count",
    "nan_weight_count",
    "impossible_cash_and_risky_exposure_days",
    "duplicate_reference_correlation",
    "spy200d_reference_correlation",
    "active_combo_correlation",
    "active_combo_blend_total_return_delta",
    "active_combo_blend_drawdown_delta",
    "baseline_correlation",
    "spy_total_return_delta",
    "bil_cash_total_return_delta",
    "trade_count",
    "rebalance_count",
    "turnover_proxy",
    "cagr_retention_vs_comparator_pass",
    "source_original_retention_pass",
    "drawdown_reduction_pass",
    "calmar_improvement_pass",
    "bil_cash_usage_pass",
    "duplicate_correlation_pass",
    "exposure_invariant_pass",
    "numeric_criteria_pass",
    "related_group_confirmation_pass",
    "vol_throttle_research_label",
    "data_availability_status",
    "missing_symbols",
    "promotion_eligibility",
    "paper_forward_eligibility",
    "methodology_notes",
)

CRITERIA_FIELDS = (
    "variant_id",
    "variant_role",
    "threshold_set_id",
    "cagr_retention_vs_comparator",
    "cagr_retention_vs_comparator_pass",
    "cagr_retention_vs_source_original_vol_throttle",
    "source_original_retention_pass",
    "drawdown_reduction_vs_comparator",
    "drawdown_reduction_pass",
    "calmar_improvement_vs_comparator",
    "calmar_improvement_pass",
    "average_bil_cash_share",
    "bil_cash_usage_pass",
    "duplicate_reference_correlation",
    "duplicate_correlation_pass",
    "max_daily_exposure",
    "max_daily_weight_sum",
    "exposure_invariant_pass",
    "numeric_criteria_pass",
    "related_group_confirmation_pass",
    "vol_throttle_research_label",
)

REQUIRED_OUTPUT_FILES = (
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


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def parse_float(value: Any, default: float = float("nan")) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def bool_pass(value: bool) -> bool:
    return bool(value)


def finite(value: float) -> bool:
    return not math.isnan(float(value)) and math.isfinite(float(value))


def role_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        role = str(row.get("variant_role", ""))
        counts[role] = counts.get(role, 0) + 1
    return counts


def threshold_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        threshold = str(row.get("threshold_set_id", ""))
        counts[threshold] = counts.get(threshold, 0) + 1
    return counts


def load_sources(root: Path) -> dict[str, Any]:
    design_rows = read_csv_rows(root / SOURCE_DESIGN_DIR / "followup_variant_design_table.csv")
    source_rows = {
        row["variant_id"]: row for row in read_csv_rows(root / SOURCE_RUN_DIR / "variant_run_results.csv")
    }
    audit_manifest = read_json(root / SOURCE_AUDIT_DIR / "vol_throttle_followup_design_audit_manifest.json")
    audit_check = read_json(root / SOURCE_AUDIT_DIR / "vol_throttle_followup_design_audit_consistency_check.json")
    return {
        "design_rows": design_rows,
        "source_rows": source_rows,
        "audit_manifest": audit_manifest,
        "audit_check": audit_check,
    }


def design_to_baseline_row(row: dict[str, str]) -> dict[str, str]:
    return {
        "universe": row["universe"],
        "baseline_variant_id": row["baseline_variant_id"],
        "momentum_lookback_days": row["lookback"],
        "top_n": row["top_n"],
        "universe_group": row["universe_group"],
    }


def volatility_multiplier_for_thresholds(
    annualized_volatility: float | None,
    *,
    normal_threshold: float,
    high_threshold: float,
    normal_multiplier: float,
    high_vol_multiplier: float,
    extreme_vol_multiplier: float,
    enough_history: bool,
) -> float:
    if not enough_history or annualized_volatility is None or math.isnan(float(annualized_volatility)):
        return normal_multiplier
    if annualized_volatility <= normal_threshold:
        return normal_multiplier
    if annualized_volatility <= high_threshold:
        return high_vol_multiplier
    return extreme_vol_multiplier


def run_volatility_throttle_variant(
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
    baseline_input = baseline_daily.reindex(prices.index).fillna(0.0)
    realized_vol = baseline_input.rolling(window, min_periods=window).std().shift(1) * math.sqrt(252.0)
    normal_threshold = parse_float(design_row["normal_vol_threshold"])
    high_threshold = parse_float(design_row["high_vol_threshold"])
    normal_multiplier = parse_float(design_row["normal_multiplier"])
    high_multiplier = parse_float(design_row["high_vol_multiplier"])
    extreme_multiplier = parse_float(design_row["extreme_vol_multiplier"])
    multipliers = pd.Series(normal_multiplier, index=prices.index, dtype=float)
    enough_history = realized_vol.notna()
    multipliers.loc[enough_history & (realized_vol > normal_threshold) & (realized_vol <= high_threshold)] = high_multiplier
    multipliers.loc[enough_history & (realized_vol > high_threshold)] = extreme_multiplier

    weights = pd.DataFrame(0.0, index=prices.index, columns=prices.columns)
    risky_cols = [column for column in weights.columns if column != "BIL"]
    if risky_cols:
        weights.loc[:, risky_cols] = base.loc[:, risky_cols].mul(multipliers, axis=0)
    if "BIL" in weights.columns:
        weights.loc[:, "BIL"] = (1.0 - weights.loc[:, risky_cols].sum(axis=1)).clip(lower=0.0)
    weights = weights.clip(lower=0.0)
    daily = (weights * returns).sum(axis=1).rename(design_row["variant_id"])
    return daily, weights


def baseline_metrics(source_row: dict[str, str]) -> dict[str, float]:
    return {
        "baseline_total_return": parse_float(source_row.get("baseline_total_return")),
        "baseline_cagr": parse_float(source_row.get("baseline_cagr")),
        "baseline_max_drawdown": parse_float(source_row.get("baseline_max_drawdown")),
        "baseline_calmar_or_return_drawdown_proxy": parse_float(
            source_row.get("baseline_calmar_or_return_drawdown_proxy")
        ),
    }


def data_blocked_row(row: dict[str, str], missing: list[str], reason: str) -> dict[str, Any]:
    return {
        "lane_id": LANE_ID,
        "variant_id": row.get("variant_id", ""),
        "variant_role": row.get("variant_role", ""),
        "threshold_set_id": row.get("threshold_set_id", ""),
        "source_variant_id": row.get("source_variant_id", ""),
        "baseline_comparator_variant_id": row.get("baseline_variant_id", ""),
        "source_evidence_path": row.get("source_evidence_path", ""),
        "universe_group": row.get("universe_group", ""),
        "universe": row.get("universe", ""),
        "lookback": row.get("lookback", ""),
        "top_n": row.get("top_n", ""),
        "data_availability_status": "vol_throttle_signal_data_blocked",
        "missing_symbols": "|".join(missing),
        "vol_throttle_research_label": "vol_throttle_signal_data_blocked",
        "promotion_eligibility": False,
        "paper_forward_eligibility": False,
        "methodology_notes": reason,
        "cagr_retention_vs_comparator_pass": False,
        "source_original_retention_pass": False,
        "drawdown_reduction_pass": False,
        "calmar_improvement_pass": False,
        "bil_cash_usage_pass": False,
        "duplicate_correlation_pass": False,
        "exposure_invariant_pass": False,
        "numeric_criteria_pass": False,
        "related_group_confirmation_pass": False,
    }


def evaluate_design_row(
    root: Path,
    row: dict[str, str],
    source_rows: dict[str, dict[str, str]],
    local_symbols: set[str],
    active_returns: pd.Series,
) -> dict[str, Any]:
    universe = [symbol for symbol in row["universe"].split("|") if symbol]
    missing = [symbol for symbol in universe if symbol not in local_symbols]
    source = source_rows.get(row.get("source_variant_id", ""))
    if missing:
        return data_blocked_row(row, missing, "required local cache symbols missing")
    if source is None:
        return data_blocked_row(row, [], "mapped source original-volatility-throttle row missing")

    baseline_daily, baseline_weights = build_baseline_weights(root, design_to_baseline_row(row))
    daily, weights = run_volatility_throttle_variant(root, row, baseline_daily, baseline_weights)
    if daily.empty or weights.empty or len(daily.dropna()) < 252:
        return data_blocked_row(row, [], "insufficient local history after cache load")

    run_metrics = metrics_for_returns(daily, weights)
    base_metrics = baseline_metrics(source)
    drawdown_reduction = pct_reduction(base_metrics["baseline_max_drawdown"], run_metrics["max_drawdown"])
    cagr_retention = safe_ratio(run_metrics["cagr"], base_metrics["baseline_cagr"])
    calmar_delta = calmar_improvement(
        base_metrics["baseline_calmar_or_return_drawdown_proxy"],
        run_metrics["calmar_or_return_drawdown_proxy"],
    )
    source_cagr = parse_float(row.get("source_cagr"))
    source_retention = safe_ratio(run_metrics["cagr"], source_cagr)

    spy_delta = benchmark_delta(daily, cached_price_series(str(root), "SPY").pct_change(fill_method=None).dropna().rename("SPY"))
    bil_delta = benchmark_delta(daily, cached_price_series(str(root), "BIL").pct_change(fill_method=None).dropna().rename("BIL"))
    contrib = contribution_metrics(daily, active_returns)
    spy200d_returns = reference_spy200d_returns(root, daily.index)
    aligned_reference = pd.concat([daily.rename("strategy"), spy200d_returns.rename("spy200d")], axis=1).dropna()
    spy200d_corr = (
        float(aligned_reference["strategy"].corr(aligned_reference["spy200d"]))
        if len(aligned_reference) >= 252
        else float("nan")
    )
    aligned_baseline = pd.concat([daily.rename("strategy"), baseline_daily.rename("baseline")], axis=1).dropna()
    baseline_corr = (
        float(aligned_baseline["strategy"].corr(aligned_baseline["baseline"]))
        if len(aligned_baseline) >= 252
        else float("nan")
    )
    duplicate_corr = spy200d_corr

    exposure_pass = (
        run_metrics["max_daily_exposure"] <= 1.000001
        and run_metrics["max_daily_weight_sum"] <= 1.000001
        and int(run_metrics["weight_sum_violation_count"]) == 0
        and int(run_metrics["negative_weight_violation_count"]) == 0
        and int(run_metrics["nan_weight_count"]) == 0
        and int(run_metrics["impossible_cash_and_risky_exposure_days"]) == 0
    )
    cagr_pass = finite(cagr_retention) and cagr_retention >= 0.70
    source_pass = finite(source_retention) and source_retention >= 0.85
    drawdown_pass = finite(drawdown_reduction) and drawdown_reduction >= 0.25
    calmar_pass = finite(calmar_delta) and calmar_delta > 0.0
    bil_pass = run_metrics["average_bil_cash_share"] < 0.35
    duplicate_pass = finite(duplicate_corr) and duplicate_corr < 0.90
    numeric_pass = all([cagr_pass, source_pass, drawdown_pass, calmar_pass, bil_pass, duplicate_pass, exposure_pass])

    return {
        "lane_id": LANE_ID,
        "variant_id": row["variant_id"],
        "variant_role": row["variant_role"],
        "threshold_set_id": row["threshold_set_id"],
        "source_variant_id": row["source_variant_id"],
        "baseline_comparator_variant_id": row["baseline_variant_id"],
        "source_evidence_path": row["source_evidence_path"],
        "universe_group": row["universe_group"],
        "universe": row["universe"],
        "lookback": int(float(row["lookback"])),
        "top_n": int(float(row["top_n"])),
        **run_metrics,
        **base_metrics,
        "drawdown_reduction_vs_comparator": drawdown_reduction,
        "cagr_retention_vs_comparator": cagr_retention,
        "calmar_improvement_vs_comparator": calmar_delta,
        "source_original_cagr": source_cagr,
        "source_original_max_drawdown": parse_float(row.get("source_max_drawdown")),
        "cagr_retention_vs_source_original_vol_throttle": source_retention,
        "duplicate_reference_correlation": duplicate_corr,
        "spy200d_reference_correlation": spy200d_corr,
        "active_combo_correlation": contrib["active_combo_correlation"],
        "active_combo_blend_total_return_delta": contrib["active_combo_blend_total_return_delta"],
        "active_combo_blend_drawdown_delta": contrib["active_combo_blend_drawdown_delta"],
        "baseline_correlation": baseline_corr,
        "spy_total_return_delta": spy_delta,
        "bil_cash_total_return_delta": bil_delta,
        "cagr_retention_vs_comparator_pass": bool_pass(cagr_pass),
        "source_original_retention_pass": bool_pass(source_pass),
        "drawdown_reduction_pass": bool_pass(drawdown_pass),
        "calmar_improvement_pass": bool_pass(calmar_pass),
        "bil_cash_usage_pass": bool_pass(bil_pass),
        "duplicate_correlation_pass": bool_pass(duplicate_pass),
        "exposure_invariant_pass": bool_pass(exposure_pass),
        "numeric_criteria_pass": bool_pass(numeric_pass),
        "related_group_confirmation_pass": False,
        "data_availability_status": "cache_ready",
        "missing_symbols": "",
        "promotion_eligibility": False,
        "paper_forward_eligibility": False,
        "methodology_notes": "approved volatility-throttle focused follow-up; local cache only; non-promotable diagnostic research evidence",
    }


def assign_labels(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    numeric_pass_by_threshold: dict[str, int] = {}
    for row in rows:
        threshold = str(row.get("threshold_set_id", ""))
        numeric_pass_by_threshold[threshold] = numeric_pass_by_threshold.get(threshold, 0) + int(
            bool(row.get("numeric_criteria_pass"))
        )

    for row in rows:
        if row.get("data_availability_status") != "cache_ready":
            row["vol_throttle_research_label"] = "vol_throttle_signal_data_blocked"
            continue
        group_pass = numeric_pass_by_threshold.get(str(row.get("threshold_set_id", "")), 0) >= 2
        row["related_group_confirmation_pass"] = group_pass
        if not row.get("exposure_invariant_pass"):
            label = "vol_throttle_signal_weak"
        elif not row.get("duplicate_correlation_pass"):
            label = "vol_throttle_signal_duplicate_reference"
        elif not row.get("bil_cash_usage_pass"):
            label = "vol_throttle_signal_too_defensive"
        elif not row.get("drawdown_reduction_pass"):
            label = "vol_throttle_signal_drawdown_reduction_below_threshold"
        elif row.get("numeric_criteria_pass") and group_pass:
            label = "vol_throttle_signal_confirmed"
        elif row.get("cagr_retention_vs_comparator_pass") and row.get("drawdown_reduction_pass"):
            label = "vol_throttle_signal_threshold_sensitive"
        else:
            label = "vol_throttle_signal_weak"
        row["vol_throttle_research_label"] = label
    return rows


def evaluate_followup(root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    source = load_sources(root)
    design_rows = source["design_rows"]
    local_symbols = available_symbols(root)
    active_returns = active_combo_returns(root)
    rows = [
        evaluate_design_row(root, row, source["source_rows"], local_symbols, active_returns)
        for row in design_rows
    ]
    rows = assign_labels(rows)
    design_role_counts = role_counts(design_rows)
    design_threshold_counts = threshold_counts(design_rows)
    preflight = {
        "design_audit_run_ready": source["audit_manifest"].get("run_readiness_decision") == "followup_design_run_ready",
        "design_audit_next_action_correct": source["audit_manifest"].get("next_action")
        == "run_volatility_throttle_focused_research_followup",
        "design_audit_consistency_passed": source["audit_check"].get("consistency_passed") is True,
        "planned_row_count": len(design_rows),
        "planned_row_count_exact_18": len(design_rows) == EXPECTED_ROW_COUNT,
        "role_counts": design_role_counts,
        "role_counts_match_design": design_role_counts == EXPECTED_ROLE_COUNTS,
        "threshold_counts": design_threshold_counts,
        "threshold_sets_match_design": set(design_threshold_counts) == EXPECTED_THRESHOLD_SETS,
        "source_original_mapping_missing_count": sum(
            1 for row in design_rows if row.get("source_variant_id") not in source["source_rows"]
        ),
        "available_symbols_used": sorted({symbol for row in design_rows for symbol in row["universe"].split("|") if symbol in local_symbols}),
        "provider_download_required": False,
        "intraday_data_required": False,
    }
    return rows, preflight


def label_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {label: sum(1 for row in rows if row.get("vol_throttle_research_label") == label) for label in ALLOWED_LABELS}


def numeric_pass_count(rows: list[dict[str, Any]]) -> int:
    return sum(1 for row in rows if row.get("numeric_criteria_pass") is True)


def invariant_failures(rows: list[dict[str, Any]]) -> list[str]:
    return [row["variant_id"] for row in rows if row.get("exposure_invariant_pass") is not True]


def mapping_missing_count(rows: list[dict[str, Any]], preflight: dict[str, Any]) -> int:
    blocked_for_mapping = sum(
        1 for row in rows if row.get("data_availability_status") != "cache_ready" and "source" in str(row.get("methodology_notes", ""))
    )
    return int(preflight.get("source_original_mapping_missing_count", 0)) + blocked_for_mapping


def build_manifest(created: str, output: Path, rows: list[dict[str, Any]], preflight: dict[str, Any]) -> dict[str, Any]:
    counts = label_counts(rows)
    roles = role_counts(rows)
    thresholds = threshold_counts(rows)
    exposure_passed = not invariant_failures(rows)
    missing_mapping = mapping_missing_count(rows, preflight)
    row_count_ok = len(rows) == EXPECTED_ROW_COUNT
    interpretable = (
        row_count_ok
        and exposure_passed
        and missing_mapping == 0
        and preflight["design_audit_run_ready"]
        and preflight["role_counts_match_design"]
        and preflight["threshold_sets_match_design"]
    )
    next_action = NEXT_ACTION_AUDIT if interpretable else NEXT_ACTION_FIX
    max_exposure = max([parse_float(row.get("max_daily_exposure"), 0.0) for row in rows] or [0.0])
    max_weight_sum = max([parse_float(row.get("max_daily_weight_sum"), 0.0) for row in rows] or [0.0])
    return {
        "created_utc": created,
        "run_timestamp": created,
        "evidence_path": str(output.resolve()),
        "volatility_throttle_followup_run": True,
        "lane_id": LANE_ID,
        "source_lane": "high_return_tactical_risk_control_lane_v1",
        "source_concept": "realized_volatility_throttle",
        "source_design_audit_run_ready": preflight["design_audit_run_ready"],
        "row_count": len(rows),
        "role_counts": roles,
        "threshold_set_count": len(thresholds),
        "threshold_set_counts": thresholds,
        "data_source_used": "local_cache_only",
        "uses_local_cache_only": True,
        "provider_download": False,
        "intraday_data_used": False,
        "broker_api_called": False,
        "broker_orders_submitted": False,
        "broker_orders_cancelled": False,
        "broker_orders_reconciled": False,
        "broker_paper_live_path_touched": False,
        "live_orders": False,
        "real_money_recommendation": False,
        "new_family_created": False,
        "new_families_created": False,
        "new_unrelated_variant_created": False,
        "new_variants_created": False,
        "new_strategy_discovery_run": False,
        "new_research_batch_run": False,
        "new_backtests_outside_approved_lane": False,
        "promotion_candidates_created": False,
        "candidate_exhaustive_run": False,
        "paper_forward_activation": False,
        "new_paper_forward_candidate_created": False,
        "best_single_variant_promoted": False,
        "research_outputs_remain_non_promotable": True,
        "active_vm_preserved": True,
        "active_dsr_preserved": True,
        "static_all_weather_benchmark_control_only": True,
        "macro_gld_lineage_recovery_run": False,
        "macro_gld_remains_lineage_blocked_visible": True,
        "alpaca_execution_module_delegated": True,
        "confirmation_reference_row_count": roles.get("confirmation_reference", 0),
        "minimal_robustness_row_count": roles.get("minimal_robustness_less_defensive", 0)
        + roles.get("minimal_robustness_more_defensive", 0),
        "numeric_criteria_pass_count": numeric_pass_count(rows),
        "numeric_criteria_fail_count": len(rows) - numeric_pass_count(rows),
        "invariant_failure_count": len(invariant_failures(rows)),
        "missing_comparator_or_source_mapping_count": missing_mapping,
        "max_daily_exposure": max_exposure,
        "max_daily_weight_sum": max_weight_sum,
        "exposure_invariant_passed": exposure_passed and max_exposure <= 1.000001 and max_weight_sum <= 1.000001,
        "results_interpretable": interpretable,
        **{f"{label}_count": count for label, count in counts.items()},
        "next_action": next_action,
    }


def format_float(value: Any) -> str:
    parsed = parse_float(value)
    if not finite(parsed):
        return "nan"
    return f"{parsed:.6f}"


def summary_md(manifest: dict[str, Any]) -> str:
    label_lines = [
        f"- `{label}`: `{manifest[f'{label}_count']}`"
        for label in sorted(ALLOWED_LABELS)
    ]
    return f"""# Volatility Throttle Focused Research Follow-Up Run

Lane ID: `{manifest['lane_id']}`

Row count: `{manifest['row_count']}`

Role counts: `{manifest['role_counts']}`

Threshold set count: `{manifest['threshold_set_count']}`

Numeric criteria pass count: `{manifest['numeric_criteria_pass_count']}`

Numeric criteria fail count: `{manifest['numeric_criteria_fail_count']}`

Invariant failures: `{manifest['invariant_failure_count']}`

Missing comparator/source mappings: `{manifest['missing_comparator_or_source_mapping_count']}`

Results interpretable: `{manifest['results_interpretable']}`

Research-only labels:

{chr(10).join(label_lines)}

No output is promotable or paper-forward eligible.

Exact next action: `{manifest['next_action']}`
"""


def preflight_md(preflight: dict[str, Any]) -> str:
    return f"""# Volatility Throttle Follow-Up Run Preflight

- Design audit run-ready: `{preflight['design_audit_run_ready']}`
- Design audit next action correct: `{preflight['design_audit_next_action_correct']}`
- Design audit consistency passed: `{preflight['design_audit_consistency_passed']}`
- Planned rows: `{preflight['planned_row_count']}`
- Planned rows exactly 18: `{preflight['planned_row_count_exact_18']}`
- Role counts match design: `{preflight['role_counts_match_design']}`
- Threshold sets match design: `{preflight['threshold_sets_match_design']}`
- Source original mapping missing count: `{preflight['source_original_mapping_missing_count']}`
- Available local-cache symbols used: `{', '.join(preflight['available_symbols_used'])}`
- Provider download required: `{preflight['provider_download_required']}`
- Intraday data required: `{preflight['intraday_data_required']}`
"""


def rows_md(rows: list[dict[str, Any]]) -> str:
    lines = ["# Volatility Throttle Follow-Up Results", "", f"Rows: `{len(rows)}`", ""]
    for row in rows:
        lines.append(
            f"- `{row['variant_id']}`: role `{row['variant_role']}`, threshold `{row['threshold_set_id']}`, "
            f"CAGR `{format_float(row.get('cagr'))}`, max DD `{format_float(row.get('max_drawdown'))}`, "
            f"DD reduction `{format_float(row.get('drawdown_reduction_vs_comparator'))}`, "
            f"CAGR retention `{format_float(row.get('cagr_retention_vs_comparator'))}`, "
            f"label `{row.get('vol_throttle_research_label')}`"
        )
    return "\n".join(lines) + "\n"


def summary_table(rows: list[dict[str, Any]], field: str) -> list[dict[str, Any]]:
    df = pd.DataFrame(rows)
    if df.empty:
        return []
    out: list[dict[str, Any]] = []
    for value, subset in df.groupby(field):
        out.append(
            {
                field: value,
                "row_count": len(subset),
                "numeric_criteria_pass_count": int(subset["numeric_criteria_pass"].astype(bool).sum()),
                "confirmed_count": int((subset["vol_throttle_research_label"] == "vol_throttle_signal_confirmed").sum()),
                "threshold_sensitive_count": int(
                    (subset["vol_throttle_research_label"] == "vol_throttle_signal_threshold_sensitive").sum()
                ),
                "median_cagr": float(pd.to_numeric(subset["cagr"], errors="coerce").median()),
                "median_max_drawdown": float(pd.to_numeric(subset["max_drawdown"], errors="coerce").median()),
                "median_drawdown_reduction_vs_comparator": float(
                    pd.to_numeric(subset["drawdown_reduction_vs_comparator"], errors="coerce").median()
                ),
                "median_cagr_retention_vs_comparator": float(
                    pd.to_numeric(subset["cagr_retention_vs_comparator"], errors="coerce").median()
                ),
                "median_average_bil_cash_share": float(
                    pd.to_numeric(subset["average_bil_cash_share"], errors="coerce").median()
                ),
            }
        )
    return out


def behavior_md(title: str, rows: list[dict[str, Any]], role_filter: set[str]) -> str:
    filtered = [row for row in rows if row.get("variant_role") in role_filter]
    pass_count = numeric_pass_count(filtered)
    labels = label_counts(filtered)
    return f"""# {title}

Rows reviewed: `{len(filtered)}`

Numeric criteria pass count: `{pass_count}`

Numeric criteria fail count: `{len(filtered) - pass_count}`

Label counts:

{chr(10).join(f'- `{label}`: `{count}`' for label, count in sorted(labels.items()))}
"""


def mapping_report_md(manifest: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    missing = [row["variant_id"] for row in rows if row.get("data_availability_status") != "cache_ready"]
    return f"""# Baseline Comparator Mapping Report

Missing comparator/source mapping count: `{manifest['missing_comparator_or_source_mapping_count']}`

Data-blocked or mapping-blocked rows:

{chr(10).join(f'- `{variant}`' for variant in missing) if missing else '- None'}

Each non-blocked row used the mapped uncontrolled baseline comparator and source original-volatility-throttle row from the approved evidence paths.
"""


def invariant_report_md(manifest: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    failures = invariant_failures(rows)
    impossible_days = sum(int(parse_float(row.get("impossible_cash_and_risky_exposure_days"), 0.0)) for row in rows)
    return f"""# Exposure Invariant Report

- Max daily exposure: `{manifest['max_daily_exposure']}`
- Max daily weight sum: `{manifest['max_daily_weight_sum']}`
- Exposure invariant passed: `{manifest['exposure_invariant_passed']}`
- Invariant failure count: `{manifest['invariant_failure_count']}`
- Impossible risky plus BIL/cash overlap days: `{impossible_days}`

Failures:

{chr(10).join(f'- `{variant}`' for variant in failures) if failures else '- None'}
"""


def do_not_promote_md() -> str:
    return """# Do Not Promote From Volatility Throttle Follow-Up Run

This packet is diagnostic historical research evidence only.

It creates no:

- promotion-review candidate
- candidate_exhaustive candidate
- paper-forward candidate
- paper-forward activation
- broker/live action
- real-money recommendation

Any interpretation requires the explicit next audit step.
"""


def next_action_md(next_action: str) -> str:
    return f"""# Volatility Throttle Follow-Up Run Next Action

Exact next action:

`{next_action}`

Do not run the next action in this task.
"""


def consistency_check(manifest: dict[str, Any], output: Path, rows: list[dict[str, Any]]) -> dict[str, Any]:
    required = {name: (output / name).exists() for name in REQUIRED_OUTPUT_FILES}
    required["vol_throttle_followup_run_consistency_check.json"] = True
    labels = {row.get("vol_throttle_research_label", "") for row in rows}
    checks = {
        "correct_lane_id": manifest["lane_id"] == LANE_ID,
        "row_count_18": manifest["row_count"] == EXPECTED_ROW_COUNT,
        "role_counts_match_design": manifest["role_counts"] == EXPECTED_ROLE_COUNTS,
        "threshold_sets_match_design": set(manifest["threshold_set_counts"]) == EXPECTED_THRESHOLD_SETS,
        "threshold_set_count_3": manifest["threshold_set_count"] == 3,
        "local_cache_only": manifest["uses_local_cache_only"] is True,
        "no_provider_download": manifest["provider_download"] is False,
        "no_intraday": manifest["intraday_data_used"] is False,
        "no_broker_api": manifest["broker_api_called"] is False,
        "no_broker_orders": (
            manifest["broker_orders_submitted"] is False
            and manifest["broker_orders_cancelled"] is False
            and manifest["broker_orders_reconciled"] is False
        ),
        "no_broker_paper_live_path": manifest["broker_paper_live_path_touched"] is False,
        "no_live_or_real_money": manifest["live_orders"] is False and manifest["real_money_recommendation"] is False,
        "no_discovery": manifest["new_strategy_discovery_run"] is False,
        "no_new_family": manifest["new_family_created"] is False and manifest["new_families_created"] is False,
        "no_unrelated_or_new_variants": manifest["new_unrelated_variant_created"] is False
        and manifest["new_variants_created"] is False,
        "no_promotion": manifest["promotion_candidates_created"] is False and manifest["best_single_variant_promoted"] is False,
        "no_candidate_exhaustive": manifest["candidate_exhaustive_run"] is False,
        "no_paper_forward": manifest["paper_forward_activation"] is False
        and manifest["new_paper_forward_candidate_created"] is False,
        "non_promotable_outputs": manifest["research_outputs_remain_non_promotable"] is True,
        "active_vm_preserved": manifest["active_vm_preserved"] is True,
        "active_dsr_preserved": manifest["active_dsr_preserved"] is True,
        "static_all_weather_control_only": manifest["static_all_weather_benchmark_control_only"] is True,
        "macro_gld_not_run": manifest["macro_gld_lineage_recovery_run"] is False,
        "alpaca_delegated": manifest["alpaca_execution_module_delegated"] is True,
        "allowed_labels_only": labels.issubset(ALLOWED_LABELS),
        "promotion_eligibility_false": all(row.get("promotion_eligibility") is False for row in rows),
        "paper_forward_eligibility_false": all(row.get("paper_forward_eligibility") is False for row in rows),
        "max_daily_exposure_lte_1": manifest["max_daily_exposure"] <= 1.000001,
        "max_daily_weight_sum_lte_1": manifest["max_daily_weight_sum"] <= 1.000001,
        "exposure_invariant_passed": manifest["exposure_invariant_passed"] is True,
        "results_exist": (output / "vol_throttle_followup_results.csv").exists(),
        "criteria_results_exist": (output / "vol_throttle_followup_numeric_criteria_results.csv").exists(),
        "summary_exists": (output / "vol_throttle_followup_run_summary.md").exists(),
        "do_not_promote_exists": (output / "do_not_promote_from_vol_throttle_followup_run.md").exists(),
        "next_action_valid": manifest["next_action"] in VALID_NEXT_ACTIONS,
        "required_files_present": all(required.values()),
        "required_files": required,
    }
    checks["consistency_passed"] = all(value is True for key, value in checks.items() if key != "required_files")
    return checks


def write_outputs(root: Path, created: str, rows: list[dict[str, Any]], preflight: dict[str, Any]) -> dict[str, Any]:
    output = root / OUTPUT_DIR
    output.mkdir(parents=True, exist_ok=True)
    manifest = build_manifest(created, output, rows, preflight)
    role_summary = summary_table(rows, "variant_role")
    threshold_summary = summary_table(rows, "threshold_set_id")
    write_json(output / "vol_throttle_followup_run_manifest.json", manifest)
    write_text(output / "vol_throttle_followup_run_summary.md", summary_md(manifest))
    write_text(output / "vol_throttle_followup_run_preflight.md", preflight_md(preflight))
    write_csv(output / "vol_throttle_followup_results.csv", rows, list(RESULT_FIELDS))
    write_text(output / "vol_throttle_followup_results.md", rows_md(rows))
    write_csv(output / "vol_throttle_followup_numeric_criteria_results.csv", rows, list(CRITERIA_FIELDS))
    write_csv(output / "vol_throttle_followup_role_summary.csv", role_summary, list(role_summary[0].keys()) if role_summary else [])
    write_csv(
        output / "vol_throttle_followup_threshold_summary.csv",
        threshold_summary,
        list(threshold_summary[0].keys()) if threshold_summary else [],
    )
    write_text(output / "baseline_comparator_mapping_report.md", mapping_report_md(manifest, rows))
    write_text(output / "exposure_invariant_report.md", invariant_report_md(manifest, rows))
    write_text(output / "confirmation_reference_behavior.md", behavior_md("Confirmation Reference Behavior", rows, {"confirmation_reference"}))
    write_text(
        output / "robustness_behavior.md",
        behavior_md(
            "Robustness Behavior",
            rows,
            {"minimal_robustness_less_defensive", "minimal_robustness_more_defensive"},
        ),
    )
    write_text(output / "do_not_promote_from_vol_throttle_followup_run.md", do_not_promote_md())
    write_text(output / "vol_throttle_followup_run_next_action.md", next_action_md(manifest["next_action"]))
    consistency = consistency_check(manifest, output, rows)
    write_json(output / "vol_throttle_followup_run_consistency_check.json", consistency)
    return {**manifest, "output_dir": str(output.resolve()), "consistency_passed": consistency["consistency_passed"]}


def run(root: Path = ROOT) -> dict[str, Any]:
    created = now_utc()
    rows, preflight = evaluate_followup(root)
    return write_outputs(root, created, rows, preflight)


if __name__ == "__main__":
    result = run()
    print(
        json.dumps(
            {
                "output_dir": result["output_dir"],
                "lane_id": result["lane_id"],
                "row_count": result["row_count"],
                "threshold_set_count": result["threshold_set_count"],
                "numeric_criteria_pass_count": result["numeric_criteria_pass_count"],
                "invariant_failure_count": result["invariant_failure_count"],
                "results_interpretable": result["results_interpretable"],
                "next_action": result["next_action"],
                "consistency_passed": result["consistency_passed"],
            },
            indent=2,
        )
    )
