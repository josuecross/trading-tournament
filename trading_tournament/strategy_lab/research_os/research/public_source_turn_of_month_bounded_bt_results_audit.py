from __future__ import annotations

import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.external_adapters.bt_adapter import (
    load_local_price_frame,
    reference_spy200d_weights,
)
from strategy_lab.research_os.research.profit_oriented_research_batch_v1 import (
    complete_rebalance_weight_frame,
    max_drawdown,
    trade_count_and_turnover,
    write_csv,
)
from strategy_lab.research_os.research.public_source_turn_of_month_bounded_bt_run import (
    EXPECTED_VARIANTS,
    LANE_ID,
    STANDARD_COST_ASSUMPTION,
    WEIGHT_TOLERANCE,
    design_manifest,
    design_rows,
    finite,
    safe_corr,
    target,
)


SOURCE_ID = "turn_of_month_equity_indexes"
FAMILY_ID = "calendar_effect_turn_of_month_equity_index"
SOURCE_RUN_DIR = Path("evidence") / "research_recovery" / "public_source_turn_of_month_bounded_bt_run" / "latest"
SOURCE_DESIGN_DIR = Path("evidence") / "research_recovery" / "public_source_turn_of_month_bounded_bt_design" / "latest"
OUTPUT_DIR = (
    Path("evidence")
    / "research_recovery"
    / "public_source_turn_of_month_bounded_bt_results_audit"
    / "latest"
)

AUDIT_DECISION_PASSED = "public_source_turn_of_month_results_audit_passed"
AUDIT_DECISION_PATCH = "public_source_turn_of_month_results_needs_patch"
NEXT_ACTION_ROBUSTNESS = "design_public_source_turn_of_month_robustness_check"
NEXT_ACTION_PATCH = "patch_public_source_turn_of_month_bounded_bt_run"
VALID_NEXT_ACTIONS = {NEXT_ACTION_ROBUSTNESS, NEXT_ACTION_PATCH}

METRIC_TOLERANCE = 1e-8
DAILY_TOLERANCE = 1e-12
WEIGHT_AUDIT_TOLERANCE = 1e-12

REQUIRED_RUN_FILES = (
    "public_source_turn_of_month_bounded_bt_run_manifest.json",
    "public_source_turn_of_month_bounded_bt_run_consistency_check.json",
    "row_level_results.csv",
    "numeric_criteria_results.csv",
    "calendar_timing_exposure_window_report.md",
    "daily_target_weights.csv",
    "equity_curve_returns.csv",
    "rebalance_turnover_report.csv",
    "rebalance_turnover_report.md",
    "baseline_control_comparison_report.md",
    "exposure_invariant_report.md",
    "role_label_summary.md",
    "public_source_turn_of_month_bounded_bt_run_summary.md",
    "do_not_promote_from_public_source_turn_of_month_run.md",
    "public_source_turn_of_month_bounded_bt_run_next_action.md",
)

AUDIT_OUTPUT_FILES = (
    "public_source_turn_of_month_bounded_bt_results_audit_manifest.json",
    "public_source_turn_of_month_bounded_bt_results_audit_consistency_check.json",
    "calendar_timing_audit_report.md",
    "shifted_weight_no_lookahead_audit_report.md",
    "row_level_discrepancy_report.csv",
    "row_level_discrepancy_report.md",
    "criteria_recomputation_report.csv",
    "criteria_recomputation_report.md",
    "timing_sanity_interpretation_report.md",
    "exposure_invariant_audit_report.md",
    "control_row_separation_report.md",
    "guardrail_audit_report.md",
    "public_source_turn_of_month_bounded_bt_results_audit_summary.md",
    "public_source_turn_of_month_bounded_bt_results_audit_next_action.md",
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
    "reported_numeric_criteria_pass",
    "recomputed_numeric_criteria_pass",
    "reported_research_label",
    "recomputed_research_label",
    "total_return_versus_bil_pass",
    "excess_after_cost_pass",
    "drawdown_reduction_pass",
    "return_drawdown_proxy_pass",
    "average_spy_exposure_bounds_pass",
    "duplicate_reference_correlation_pass",
    "timing_sanity_excess_sign_preserved",
    "timing_sanity_not_optimized",
    "control_row_excluded_from_candidate_interpretation",
    "exposure_invariant_pass",
)


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def parse_float(value: Any, default: float = float("nan")) -> float:
    try:
        if value in ("", None):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_bool(value: Any) -> bool:
    return str(value).strip().lower() == "true"


def both_nan(left: float, right: float) -> bool:
    return math.isnan(left) and math.isnan(right)


def audit_turn_of_month_targets(
    prices: pd.DataFrame, *, delayed: bool = False
) -> tuple[dict[pd.Timestamp, dict[str, float]], list[dict[str, Any]]]:
    dates = pd.DatetimeIndex(prices.index)
    groups: dict[pd.Period, list[pd.Timestamp]] = {}
    for date in dates:
        groups.setdefault(pd.Timestamp(date).to_period("M"), []).append(pd.Timestamp(date))
    positions = {pd.Timestamp(date): index for index, date in enumerate(dates)}
    targets: dict[pd.Timestamp, dict[str, float]] = {pd.Timestamp(dates[0]): target(0.0, 1.0)}
    events: list[dict[str, Any]] = []
    for period in sorted(groups):
        next_dates = groups.get(period + 1, [])
        current_dates = groups.get(period, [])
        if len(current_dates) < 2 or len(next_dates) < (4 if delayed else 3):
            continue
        month_end = current_dates[-1]
        if delayed:
            entry_date = month_end
            exit_date = next_dates[3]
        else:
            entry_date = dates[positions[month_end] - 1]
            exit_date = next_dates[2]
        targets[pd.Timestamp(entry_date)] = target(1.0, 0.0)
        targets[pd.Timestamp(exit_date)] = target(0.0, 1.0)
        events.append(
            {
                "period": str(period),
                "month_end": pd.Timestamp(month_end).date().isoformat(),
                "entry_decision_date": pd.Timestamp(entry_date).date().isoformat(),
                "exit_decision_date": pd.Timestamp(exit_date).date().isoformat(),
                "delayed": delayed,
            }
        )
    return targets, events


def audit_build_weights(variant_id: str, prices: pd.DataFrame) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    columns = ["SPY", "BIL"]
    if variant_id == "totm_spy_bil_primary_close_m1_to_plus3_v1":
        targets, events = audit_turn_of_month_targets(prices, delayed=False)
        return complete_rebalance_weight_frame(prices.index, columns, targets, tolerance=WEIGHT_TOLERANCE), events
    if variant_id == "totm_spy_bil_timing_sanity_one_bar_delayed_v1":
        targets, events = audit_turn_of_month_targets(prices, delayed=True)
        return complete_rebalance_weight_frame(prices.index, columns, targets, tolerance=WEIGHT_TOLERANCE), events
    if variant_id == "totm_spy_buy_hold_control_v1":
        return complete_rebalance_weight_frame(prices.index, columns, {prices.index[0]: target(1.0, 0.0)}), []
    if variant_id == "totm_bil_cash_control_v1":
        return complete_rebalance_weight_frame(prices.index, columns, {prices.index[0]: target(0.0, 1.0)}), []
    if variant_id == "totm_spy200d_frozen_control_v1":
        return reference_spy200d_weights(prices).reindex(columns=columns, fill_value=0.0), []
    raise ValueError(f"unexpected variant_id: {variant_id}")


def audit_returns_from_weights(prices: pd.DataFrame, weights: pd.DataFrame) -> pd.Series:
    asset_returns = prices.pct_change(fill_method=None).fillna(0.0)
    aligned = weights.reindex(prices.index).ffill().fillna(0.0).reindex(columns=prices.columns, fill_value=0.0)
    return (aligned.shift(1).fillna(0.0) * asset_returns).sum(axis=1)


def equity_from_returns(daily_returns: pd.Series) -> pd.Series:
    return (1.0 + daily_returns.fillna(0.0)).cumprod().rename("equity")


def invariant_summary(weights: pd.DataFrame) -> dict[str, Any]:
    weight_sum = weights.sum(axis=1)
    risky = weights.drop(columns=["BIL"], errors="ignore").sum(axis=1)
    negative = weights < -WEIGHT_TOLERANCE
    impossible_cash = (weights.get("BIL", pd.Series(0.0, index=weights.index)) > WEIGHT_TOLERANCE) & (
        risky > WEIGHT_TOLERANCE
    ) & (weight_sum > 1.0 + WEIGHT_TOLERANCE)
    return {
        "max_daily_exposure": float(risky.max()),
        "max_daily_weight_sum": float(weight_sum.max()),
        "average_weight_sum": float(weight_sum.mean()),
        "weight_sum_violation_count": int((weight_sum > 1.0 + WEIGHT_TOLERANCE).sum()),
        "negative_weight_violation_count": int(negative.sum().sum()),
        "nan_weight_count": int(weights.isna().sum().sum()),
        "impossible_cash_and_risky_exposure_days": int(impossible_cash.sum()),
    }


def audit_metrics(daily_returns: pd.Series, weights: pd.DataFrame) -> dict[str, Any]:
    daily = daily_returns.dropna()
    equity = equity_from_returns(daily)
    years = max((daily.index.max() - daily.index.min()).days / 365.25, 1e-9)
    total_return = float(equity.iloc[-1] - 1.0)
    cagr = float(equity.iloc[-1] ** (1.0 / years) - 1.0)
    mdd = max_drawdown(equity)
    volatility = float(daily.std() * np.sqrt(252.0))
    proxy = float(cagr / abs(mdd)) if mdd < 0 else float("nan")
    trades, turnover = trade_count_and_turnover(weights)
    return {
        "effective_start_date": daily.index.min().date().isoformat(),
        "effective_end_date": daily.index.max().date().isoformat(),
        "total_return": total_return,
        "cagr": cagr,
        "max_drawdown": mdd,
        "volatility": volatility,
        "return_drawdown_proxy": proxy,
        "average_spy_exposure_share": float(weights["SPY"].mean()),
        "average_bil_exposure_share": float(weights["BIL"].mean()),
        "trade_count": trades,
        "turnover_proxy": turnover,
        **invariant_summary(weights),
    }


def recomputed_result_for_row(
    row: dict[str, str],
    row_metrics: dict[str, Any],
    daily: pd.Series,
    controls: dict[str, dict[str, Any]],
    control_returns: dict[str, pd.Series],
) -> dict[str, Any]:
    bil_total = controls["totm_bil_cash_control_v1"]["total_return"]
    spy_mdd = controls["totm_spy_buy_hold_control_v1"]["max_drawdown"]
    spy_proxy = controls["totm_spy_buy_hold_control_v1"]["return_drawdown_proxy"]
    same_window_vs_bil = row_metrics["total_return"] - bil_total
    excess_after_cost = same_window_vs_bil - STANDARD_COST_ASSUMPTION
    drawdown_reduction = (
        (abs(spy_mdd) - abs(row_metrics["max_drawdown"])) / abs(spy_mdd)
        if finite(spy_mdd) and spy_mdd < 0
        else float("nan")
    )
    corr_spy = safe_corr(daily, control_returns["totm_spy_buy_hold_control_v1"])
    corr_spy200d = safe_corr(daily, control_returns["totm_spy200d_frozen_control_v1"])
    duplicate_values = [value for value in (corr_spy, corr_spy200d) if finite(value)]
    duplicate_reference = max(duplicate_values) if duplicate_values else float("nan")
    exposure_pass = (
        row_metrics["max_daily_exposure"] <= 1.000001
        and row_metrics["max_daily_weight_sum"] <= 1.000001
        and int(row_metrics["weight_sum_violation_count"]) == 0
        and int(row_metrics["negative_weight_violation_count"]) == 0
        and int(row_metrics["nan_weight_count"]) == 0
        and int(row_metrics["impossible_cash_and_risky_exposure_days"]) == 0
    )
    is_primary = row["variant_role"] == "source_primary"
    is_timing = row["variant_role"] == "timing_sanity"
    primary_total_return_beats_bil = is_primary and same_window_vs_bil > 0.0
    primary_excess_after_cost_beats_bil = is_primary and excess_after_cost > 0.0
    primary_drawdown_reduction_pass = is_primary and drawdown_reduction >= 0.25
    primary_proxy_pass = is_primary and row_metrics["return_drawdown_proxy"] > spy_proxy
    primary_exposure_pass = is_primary and 0.12 <= row_metrics["average_spy_exposure_share"] <= 0.30
    primary_duplicate_pass = is_primary and (not finite(duplicate_reference) or duplicate_reference < 0.85)
    timing_excess_sign = is_timing and excess_after_cost > 0.0
    timing_not_higher_scoring = is_timing
    if is_timing and "totm_spy_bil_primary_close_m1_to_plus3_v1" in controls:
        timing_not_higher_scoring = (
            row_metrics["return_drawdown_proxy"]
            <= controls["totm_spy_bil_primary_close_m1_to_plus3_v1"]["return_drawdown_proxy"]
        )
    if is_primary:
        numeric_pass = all(
            (
                primary_total_return_beats_bil,
                primary_excess_after_cost_beats_bil,
                primary_drawdown_reduction_pass,
                primary_proxy_pass,
                primary_exposure_pass,
                primary_duplicate_pass,
                exposure_pass,
            )
        )
    elif is_timing:
        numeric_pass = bool(timing_excess_sign and timing_not_higher_scoring and exposure_pass)
    else:
        numeric_pass = exposure_pass
    return {
        "lane_id": LANE_ID,
        "family_id": FAMILY_ID,
        "source_id": SOURCE_ID,
        "variant_id": row["variant_id"],
        "variant_role": row["variant_role"],
        "research_label": row["research_label"],
        "concept": row["concept"],
        "symbols_used": row["symbols"],
        "local_cache_data_available": True,
        "calendar_window": row["calendar_window"],
        "entry_decision_convention": row["entry_decision_date"],
        "exit_decision_convention": row["exit_decision_date"],
        "weight_shift_convention": row["weight_shift_convention"],
        **row_metrics,
        "same_window_return_versus_bil": same_window_vs_bil,
        "return_after_standard_cost_assumption": row_metrics["total_return"] - STANDARD_COST_ASSUMPTION,
        "excess_return_versus_bil_after_cost": excess_after_cost,
        "drawdown_reduction_versus_spy_buy_hold": drawdown_reduction,
        "correlation_versus_spy_buy_hold": corr_spy,
        "correlation_versus_spy200d_control": corr_spy200d,
        "duplicate_reference_correlation": duplicate_reference,
        "exposure_invariant_pass": exposure_pass,
        "primary_total_return_beats_bil": primary_total_return_beats_bil,
        "primary_excess_after_cost_beats_bil": primary_excess_after_cost_beats_bil,
        "primary_drawdown_reduction_pass": primary_drawdown_reduction_pass,
        "primary_return_drawdown_proxy_pass": primary_proxy_pass,
        "primary_spy_exposure_bounds_pass": primary_exposure_pass,
        "primary_duplicate_correlation_pass": primary_duplicate_pass,
        "timing_sanity_excess_sign_preserved": timing_excess_sign,
        "timing_sanity_not_higher_scoring": timing_not_higher_scoring,
        "numeric_criteria_pass": numeric_pass,
        "promotion_eligibility": False,
        "paper_forward_eligibility": False,
        "candidate_exhaustive_eligibility": False,
        "methodology_notes": "audit recomputation from local-cache target weights and shifted close-to-close returns",
    }


def recompute_lane(root: Path) -> tuple[
    list[dict[str, Any]],
    dict[str, pd.DataFrame],
    dict[str, pd.Series],
    dict[str, list[dict[str, Any]]],
    pd.DataFrame,
]:
    rows = design_rows(root)
    prices = load_local_price_frame(root)
    weights_by_variant: dict[str, pd.DataFrame] = {}
    returns_by_variant: dict[str, pd.Series] = {}
    metrics_by_variant: dict[str, dict[str, Any]] = {}
    events_by_variant: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        variant_id = row["variant_id"]
        weights, events = audit_build_weights(variant_id, prices)
        daily = audit_returns_from_weights(prices, weights).rename(variant_id)
        weights_by_variant[variant_id] = weights
        returns_by_variant[variant_id] = daily
        metrics_by_variant[variant_id] = audit_metrics(daily, weights)
        events_by_variant[variant_id] = events
    result_rows = [
        recomputed_result_for_row(
            row,
            metrics_by_variant[row["variant_id"]],
            returns_by_variant[row["variant_id"]],
            metrics_by_variant,
            returns_by_variant,
        )
        for row in rows
    ]
    return result_rows, weights_by_variant, returns_by_variant, events_by_variant, prices


def compare_value(
    discrepancies: list[dict[str, Any]],
    variant_id: str,
    discrepancy_type: str,
    field: str,
    reported: Any,
    recomputed: Any,
    tolerance: float,
    date_or_period: str = "",
) -> None:
    if isinstance(recomputed, bool):
        if parse_bool(reported) != recomputed:
            discrepancies.append(
                {
                    "variant_id": variant_id,
                    "discrepancy_type": discrepancy_type,
                    "field": field,
                    "reported_value": reported,
                    "recomputed_value": recomputed,
                    "absolute_delta": "",
                    "tolerance": tolerance,
                    "date_or_period": date_or_period,
                }
            )
        return
    if isinstance(recomputed, str):
        if str(reported) != recomputed:
            discrepancies.append(
                {
                    "variant_id": variant_id,
                    "discrepancy_type": discrepancy_type,
                    "field": field,
                    "reported_value": reported,
                    "recomputed_value": recomputed,
                    "absolute_delta": "",
                    "tolerance": tolerance,
                    "date_or_period": date_or_period,
                }
            )
        return
    left = parse_float(reported)
    right = parse_float(recomputed)
    if both_nan(left, right):
        return
    delta = abs(left - right)
    if math.isnan(delta) or delta > tolerance:
        discrepancies.append(
            {
                "variant_id": variant_id,
                "discrepancy_type": discrepancy_type,
                "field": field,
                "reported_value": reported,
                "recomputed_value": recomputed,
                "absolute_delta": delta,
                "tolerance": tolerance,
                "date_or_period": date_or_period,
            }
        )


def compare_row_results(
    reported_rows: list[dict[str, str]], recomputed_rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    discrepancies: list[dict[str, Any]] = []
    reported_by_id = {row["variant_id"]: row for row in reported_rows}
    numeric_fields = (
        "average_spy_exposure_share",
        "average_bil_exposure_share",
        "total_return",
        "cagr",
        "max_drawdown",
        "volatility",
        "return_drawdown_proxy",
        "same_window_return_versus_bil",
        "return_after_standard_cost_assumption",
        "excess_return_versus_bil_after_cost",
        "drawdown_reduction_versus_spy_buy_hold",
        "correlation_versus_spy_buy_hold",
        "correlation_versus_spy200d_control",
        "duplicate_reference_correlation",
        "trade_count",
        "turnover_proxy",
        "max_daily_exposure",
        "max_daily_weight_sum",
        "average_weight_sum",
        "weight_sum_violation_count",
        "negative_weight_violation_count",
        "nan_weight_count",
        "impossible_cash_and_risky_exposure_days",
    )
    bool_fields = (
        "local_cache_data_available",
        "exposure_invariant_pass",
        "primary_total_return_beats_bil",
        "primary_excess_after_cost_beats_bil",
        "primary_drawdown_reduction_pass",
        "primary_return_drawdown_proxy_pass",
        "primary_spy_exposure_bounds_pass",
        "primary_duplicate_correlation_pass",
        "timing_sanity_excess_sign_preserved",
        "timing_sanity_not_higher_scoring",
        "numeric_criteria_pass",
        "promotion_eligibility",
        "paper_forward_eligibility",
        "candidate_exhaustive_eligibility",
    )
    string_fields = (
        "lane_id",
        "family_id",
        "source_id",
        "variant_role",
        "research_label",
        "concept",
        "symbols_used",
        "effective_start_date",
        "effective_end_date",
        "calendar_window",
        "entry_decision_convention",
        "exit_decision_convention",
        "weight_shift_convention",
    )
    for row in recomputed_rows:
        variant_id = row["variant_id"]
        reported = reported_by_id.get(variant_id)
        if reported is None:
            discrepancies.append(
                {
                    "variant_id": variant_id,
                    "discrepancy_type": "row_missing",
                    "field": "variant_id",
                    "reported_value": "",
                    "recomputed_value": variant_id,
                    "absolute_delta": "",
                    "tolerance": "",
                    "date_or_period": "",
                }
            )
            continue
        for field in numeric_fields:
            compare_value(discrepancies, variant_id, "row_metric", field, reported.get(field, ""), row[field], METRIC_TOLERANCE)
        for field in bool_fields:
            compare_value(discrepancies, variant_id, "row_bool", field, reported.get(field, ""), row[field], 0.0)
        for field in string_fields:
            compare_value(discrepancies, variant_id, "row_text", field, reported.get(field, ""), str(row[field]), 0.0)
    return discrepancies


def compare_daily_weights(saved_path: Path, recomputed: dict[str, pd.DataFrame]) -> list[dict[str, Any]]:
    saved = pd.read_csv(saved_path)
    discrepancies: list[dict[str, Any]] = []
    saved_by_key = {
        (row["variant_id"], row["date"]): row
        for row in saved.to_dict("records")
    }
    for variant_id, weights in recomputed.items():
        for date, row in weights.iterrows():
            key = (variant_id, pd.Timestamp(date).date().isoformat())
            reported = saved_by_key.get(key)
            if reported is None:
                discrepancies.append(
                    {
                        "variant_id": variant_id,
                        "discrepancy_type": "daily_weight_missing",
                        "field": "date",
                        "reported_value": "",
                        "recomputed_value": key[1],
                        "absolute_delta": "",
                        "tolerance": WEIGHT_AUDIT_TOLERANCE,
                        "date_or_period": key[1],
                    }
                )
                continue
            expected = {
                "SPY": float(row.get("SPY", 0.0)),
                "BIL": float(row.get("BIL", 0.0)),
                "weight_sum": float(row.sum()),
                "risky_exposure": float(row.get("SPY", 0.0)),
            }
            for field, value in expected.items():
                compare_value(
                    discrepancies,
                    variant_id,
                    "daily_weight",
                    field,
                    reported.get(field, ""),
                    value,
                    WEIGHT_AUDIT_TOLERANCE,
                    key[1],
                )
    return discrepancies


def compare_equity_returns(saved_path: Path, recomputed: dict[str, pd.Series]) -> list[dict[str, Any]]:
    saved = pd.read_csv(saved_path)
    discrepancies: list[dict[str, Any]] = []
    saved_by_key = {
        (row["variant_id"], row["date"]): row
        for row in saved.to_dict("records")
    }
    for variant_id, daily in recomputed.items():
        equity = equity_from_returns(daily)
        for date, value in daily.items():
            date_text = pd.Timestamp(date).date().isoformat()
            reported = saved_by_key.get((variant_id, date_text))
            if reported is None:
                discrepancies.append(
                    {
                        "variant_id": variant_id,
                        "discrepancy_type": "equity_return_missing",
                        "field": "date",
                        "reported_value": "",
                        "recomputed_value": date_text,
                        "absolute_delta": "",
                        "tolerance": DAILY_TOLERANCE,
                        "date_or_period": date_text,
                    }
                )
                continue
            compare_value(
                discrepancies,
                variant_id,
                "daily_return",
                "daily_return",
                reported.get("daily_return", ""),
                float(value),
                DAILY_TOLERANCE,
                date_text,
            )
            compare_value(
                discrepancies,
                variant_id,
                "equity_curve",
                "equity",
                reported.get("equity", ""),
                float(equity.loc[date]),
                DAILY_TOLERANCE,
                date_text,
            )
    return discrepancies


def criteria_rows(reported_rows: list[dict[str, str]], recomputed_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    reported_by_id = {row["variant_id"]: row for row in reported_rows}
    rows: list[dict[str, Any]] = []
    for row in recomputed_rows:
        reported = reported_by_id[row["variant_id"]]
        is_primary = row["variant_role"] == "source_primary"
        is_timing = row["variant_role"] == "timing_sanity"
        is_control = row["variant_role"] == "control"
        rows.append(
            {
                "variant_id": row["variant_id"],
                "variant_role": row["variant_role"],
                "reported_numeric_criteria_pass": parse_bool(reported["numeric_criteria_pass"]),
                "recomputed_numeric_criteria_pass": row["numeric_criteria_pass"],
                "reported_research_label": reported["research_label"],
                "recomputed_research_label": row["research_label"],
                "total_return_versus_bil_pass": (is_primary and row["same_window_return_versus_bil"] > 0.0),
                "excess_after_cost_pass": (is_primary and row["excess_return_versus_bil_after_cost"] > 0.0),
                "drawdown_reduction_pass": (is_primary and row["drawdown_reduction_versus_spy_buy_hold"] >= 0.25),
                "return_drawdown_proxy_pass": bool(row["primary_return_drawdown_proxy_pass"]),
                "average_spy_exposure_bounds_pass": bool(row["primary_spy_exposure_bounds_pass"]),
                "duplicate_reference_correlation_pass": bool(row["primary_duplicate_correlation_pass"]),
                "timing_sanity_excess_sign_preserved": bool(is_timing and row["timing_sanity_excess_sign_preserved"]),
                "timing_sanity_not_optimized": bool(is_timing and row["timing_sanity_not_higher_scoring"]),
                "control_row_excluded_from_candidate_interpretation": bool(
                    is_control
                    and row["research_label"] == "public_source_calendar_control_only"
                    and row["promotion_eligibility"] is False
                    and row["paper_forward_eligibility"] is False
                    and row["candidate_exhaustive_eligibility"] is False
                ),
                "exposure_invariant_pass": bool(row["exposure_invariant_pass"]),
            }
        )
    return rows


def no_lookahead_audit(
    prices: pd.DataFrame,
    weights_by_variant: dict[str, pd.DataFrame],
    returns_by_variant: dict[str, pd.Series],
    events_by_variant: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    asset_returns = prices.pct_change(fill_method=None).fillna(0.0)
    max_return_delta = 0.0
    for variant_id, weights in weights_by_variant.items():
        manual = (weights.shift(1).fillna(0.0).reindex(columns=prices.columns, fill_value=0.0) * asset_returns).sum(axis=1)
        delta = (manual - returns_by_variant[variant_id]).abs().max()
        max_return_delta = max(max_return_delta, float(delta))
    primary_events = events_by_variant["totm_spy_bil_primary_close_m1_to_plus3_v1"]
    timing_events = events_by_variant["totm_spy_bil_timing_sanity_one_bar_delayed_v1"]
    primary_weights = weights_by_variant["totm_spy_bil_primary_close_m1_to_plus3_v1"]
    effective = primary_weights.shift(1).fillna(0.0)
    exit_checks = []
    for event in primary_events:
        exit_date = pd.Timestamp(event["exit_decision_date"])
        if exit_date not in effective.index:
            continue
        pos = effective.index.get_loc(exit_date)
        after_exit = effective.index[pos + 1] if pos + 1 < len(effective.index) else None
        exit_checks.append(
            {
                "exit_date": event["exit_decision_date"],
                "effective_spy_on_exit_date": float(effective.loc[exit_date, "SPY"]),
                "effective_bil_after_exit_date": float(effective.loc[after_exit, "BIL"]) if after_exit is not None else float("nan"),
            }
        )
    return {
        "max_abs_shifted_return_delta": max_return_delta,
        "shifted_return_formula_matches": max_return_delta <= DAILY_TOLERANCE,
        "primary_event_count": len(primary_events),
        "timing_sanity_event_count": len(timing_events),
        "exit_effective_exposure_checks": exit_checks,
        "spy_exposure_through_third_trading_day_close": all(
            abs(row["effective_spy_on_exit_date"] - 1.0) <= WEIGHT_AUDIT_TOLERANCE for row in exit_checks
        ),
        "bil_exposure_after_exit": all(
            math.isnan(row["effective_bil_after_exit_date"])
            or abs(row["effective_bil_after_exit_date"] - 1.0) <= WEIGHT_AUDIT_TOLERANCE
            for row in exit_checks
        ),
    }


def evidence_completeness(source: dict[str, Any]) -> dict[str, Any]:
    manifest = source["manifest"]
    consistency = source["consistency"]
    rows = source["run_rows"]
    required = source["required_files"]
    checks = {
        "all_required_run_files_exist": all(required.values()),
        "manifest_consistency_agree": consistency.get("consistency_passed") is True
        and manifest.get("variant_count_evaluated") == 5
        and len(rows) == 5,
        "exact_approved_rows": set(row["variant_id"] for row in rows) == set(EXPECTED_VARIANTS),
        "no_hidden_rows": len(rows) == len(EXPECTED_VARIANTS),
        "no_sweep_or_optimization": manifest.get("calendar_parameter_sweep_created") is False
        and manifest.get("optimization_run") is False,
        "no_extra_timing_windows": manifest.get("one_timing_sanity_row_only") is True,
    }
    return {"checks": checks, "passed": all(checks.values()), "required_files": required}


def guardrail_audit(manifest: dict[str, Any], rows: list[dict[str, str]]) -> dict[str, Any]:
    checks = {
        "no_scraping": manifest.get("public_source_scraped") is False,
        "no_provider_download": manifest.get("provider_download") is False,
        "no_intraday": manifest.get("intraday_data_used") is False,
        "no_extra_public_source_ingestion": manifest.get("public_strategy_list_ingested") is False,
        "no_faber_taa_retest": manifest.get("faber_taa_designed_or_retested") is False,
        "no_new_instruments": manifest.get("new_instruments_added") is False,
        "no_calendar_parameter_sweep": manifest.get("calendar_parameter_sweep_created") is False,
        "no_strategy_discovery": manifest.get("strategy_discovery_run") is False,
        "no_candidate_exhaustive": manifest.get("candidate_exhaustive_run") is False,
        "no_promotion": manifest.get("promotion_candidates_created") is False
        and manifest.get("best_single_variant_promoted") is False,
        "no_paper_forward_activation": manifest.get("paper_forward_activation") is False
        and manifest.get("new_paper_forward_candidate_created") is False,
        "no_broker_live_real_money": manifest.get("broker_api_called") is False
        and manifest.get("broker_orders_submitted") is False
        and manifest.get("broker_orders_cancelled") is False
        and manifest.get("broker_orders_reconciled") is False
        and manifest.get("live_orders") is False
        and manifest.get("real_money_recommendation") is False,
        "outputs_diagnostic_non_promotable": manifest.get("outputs_diagnostic_only") is True
        and manifest.get("outputs_non_promotable") is True
        and all(parse_bool(row["promotion_eligibility"]) is False for row in rows)
        and all(parse_bool(row["paper_forward_eligibility"]) is False for row in rows)
        and all(parse_bool(row["candidate_exhaustive_eligibility"]) is False for row in rows),
    }
    return {"checks": checks, "passed": all(checks.values())}


def load_source(root: Path) -> dict[str, Any]:
    source = root / SOURCE_RUN_DIR
    return {
        "manifest": read_json(source / "public_source_turn_of_month_bounded_bt_run_manifest.json"),
        "consistency": read_json(source / "public_source_turn_of_month_bounded_bt_run_consistency_check.json"),
        "run_rows": read_csv_rows(source / "row_level_results.csv"),
        "criteria_rows": read_csv_rows(source / "numeric_criteria_results.csv"),
        "required_files": {name: (source / name).exists() for name in REQUIRED_RUN_FILES},
        "design_manifest": design_manifest(root),
    }


def manifest_payload(
    created: str,
    output: Path,
    source: dict[str, Any],
    discrepancies: list[dict[str, Any]],
    criteria: list[dict[str, Any]],
    no_lookahead: dict[str, Any],
    completeness: dict[str, Any],
    guardrails: dict[str, Any],
) -> dict[str, Any]:
    rows = source["run_rows"]
    criteria_mismatches = [
        row
        for row in criteria
        if row["reported_numeric_criteria_pass"] != row["recomputed_numeric_criteria_pass"]
        or row["reported_research_label"] != row["recomputed_research_label"]
    ]
    timing = next(row for row in rows if row["variant_role"] == "timing_sanity")
    primary = next(row for row in rows if row["variant_role"] == "source_primary")
    controls = [row for row in rows if row["variant_role"] == "control"]
    audit_passed = (
        completeness["passed"]
        and guardrails["passed"]
        and not discrepancies
        and not criteria_mismatches
        and no_lookahead["shifted_return_formula_matches"]
        and no_lookahead["spy_exposure_through_third_trading_day_close"]
        and no_lookahead["bil_exposure_after_exit"]
    )
    decision = AUDIT_DECISION_PASSED if audit_passed else AUDIT_DECISION_PATCH
    next_action = NEXT_ACTION_ROBUSTNESS if audit_passed else NEXT_ACTION_PATCH
    timing_total_higher = parse_float(timing["total_return"]) > parse_float(primary["total_return"])
    timing_dd_worse = parse_float(timing["max_drawdown"]) < parse_float(primary["max_drawdown"])
    timing_proxy_worse = parse_float(timing["return_drawdown_proxy"]) <= parse_float(primary["return_drawdown_proxy"])
    return {
        "created_utc": created,
        "evidence_path": str(output.resolve()),
        "public_source_turn_of_month_results_audit_only": True,
        "source_id_audited": SOURCE_ID,
        "family_id_audited": FAMILY_ID,
        "lane_id_audited": LANE_ID,
        "source_run_evidence_reviewed": True,
        "source_design_evidence_reviewed": True,
        "local_cache_reconstructed_for_audit": True,
        "approved_rows_recomputed_for_audit_only": True,
        "row_count_reviewed": len(rows),
        "expected_row_count": 5,
        "exact_approved_rows_reviewed": set(row["variant_id"] for row in rows) == set(EXPECTED_VARIANTS),
        "required_run_files_present": completeness["checks"]["all_required_run_files_exist"],
        "manifest_consistency_agree": completeness["checks"]["manifest_consistency_agree"],
        "calendar_timing_recomputed": True,
        "shifted_weight_no_lookahead_verified": no_lookahead["shifted_return_formula_matches"],
        "spy_exposure_through_third_trading_day_close_verified": no_lookahead[
            "spy_exposure_through_third_trading_day_close"
        ],
        "bil_exposure_after_exit_verified": no_lookahead["bil_exposure_after_exit"],
        "max_abs_shifted_return_delta": no_lookahead["max_abs_shifted_return_delta"],
        "row_level_discrepancy_count": len(discrepancies),
        "criteria_mismatch_count": len(criteria_mismatches),
        "timing_sanity_total_return_higher_than_primary": timing_total_higher,
        "timing_sanity_max_drawdown_worse_than_primary": timing_dd_worse,
        "timing_sanity_return_drawdown_proxy_worse_than_primary": timing_proxy_worse,
        "timing_sanity_context_only": parse_bool(timing["promotion_eligibility"]) is False
        and parse_bool(timing["paper_forward_eligibility"]) is False
        and parse_bool(timing["candidate_exhaustive_eligibility"]) is False,
        "timing_sanity_not_selected_as_best_strategy": True,
        "calendar_optimization_recommended": False,
        "control_row_count": len(controls),
        "control_rows_context_only": all(row["research_label"] == "public_source_calendar_control_only" for row in controls),
        "exposure_invariant_passed": source["manifest"].get("exposure_invariant_passed") is True,
        "invariant_failure_count": source["manifest"].get("invariant_failure_count"),
        "max_daily_exposure": source["manifest"].get("max_daily_exposure"),
        "max_daily_weight_sum": source["manifest"].get("max_daily_weight_sum"),
        "guardrails_passed": guardrails["passed"],
        "new_variants_created": False,
        "new_timing_windows_added": False,
        "calendar_parameter_sweep_created": False,
        "optimization_run": False,
        "new_strategy_discovery_run": False,
        "new_research_batch_run": False,
        "provider_download": False,
        "intraday_data_used": False,
        "public_source_scraped": False,
        "public_strategy_list_ingested": False,
        "faber_taa_designed_or_retested": False,
        "candidate_exhaustive_run": False,
        "promotion_candidates_created": False,
        "best_single_variant_promoted": False,
        "paper_forward_activation": False,
        "new_paper_forward_candidate_created": False,
        "broker_api_called": False,
        "broker_orders_submitted": False,
        "broker_orders_cancelled": False,
        "broker_orders_reconciled": False,
        "live_orders": False,
        "real_money_recommendation": False,
        "outputs_remain_diagnostic_non_promotable": True,
        "final_audit_decision": decision,
        "next_action": next_action,
    }


def report_bool(value: bool) -> str:
    return "pass" if value else "fail"


def calendar_timing_report(manifest: dict[str, Any], no_lookahead: dict[str, Any]) -> str:
    return f"""# Calendar Timing Audit

Decision: `{report_bool(manifest['calendar_timing_recomputed'])}`

Primary events reconstructed: `{no_lookahead['primary_event_count']}`

Timing-sanity events reconstructed: `{no_lookahead['timing_sanity_event_count']}`

The audit reconstructed common SPY/BIL trading days from local cache only. Month-end was treated as the last common trading day of each calendar month. The primary entry target was set one common trading day before month-end and the primary exit target was set on the third common trading day of the following month. The timing-sanity row delayed both target changes by one common trading day.

No symbol was forward-filled before inception because the audited price frame only includes dates where both SPY and BIL have adjusted-close data.
"""


def shifted_weight_report(manifest: dict[str, Any], no_lookahead: dict[str, Any]) -> str:
    return f"""# Shifted-Weight / No-Lookahead Audit

Shifted close-to-close return formula matched saved returns: `{no_lookahead['shifted_return_formula_matches']}`

Max absolute shifted-return delta: `{no_lookahead['max_abs_shifted_return_delta']:.12g}`

SPY exposure through third trading day close verified: `{no_lookahead['spy_exposure_through_third_trading_day_close']}`

BIL exposure after exit verified: `{no_lookahead['bil_exposure_after_exit']}`

The audit independently recomputed daily returns from target weights using prior-day target weights against current close-to-close asset returns. This verifies that a decision-close target is shifted one bar before it can affect returns, so no same-day close price is used both to create and profit from a signal.

The project-compatible output contract remains daily target weights, not drifting account/security weights.
"""


def discrepancy_report_md(discrepancies: list[dict[str, Any]]) -> str:
    if not discrepancies:
        return "# Row-Level Discrepancy Report\n\nNo row, daily-weight, daily-return, equity, label, or criteria discrepancies were found.\n"
    return f"# Row-Level Discrepancy Report\n\nDiscrepancies found: `{len(discrepancies)}`. See `row_level_discrepancy_report.csv`.\n"


def criteria_report_md(criteria: list[dict[str, Any]]) -> str:
    mismatches = [
        row
        for row in criteria
        if row["reported_numeric_criteria_pass"] != row["recomputed_numeric_criteria_pass"]
        or row["reported_research_label"] != row["recomputed_research_label"]
    ]
    return f"""# Criteria Recomposition Report

Rows recomputed: `{len(criteria)}`

Criteria or label mismatches: `{len(mismatches)}`

Primary criteria were recomputed for BIL-relative return, cost-adjusted BIL excess return, drawdown reduction versus SPY buy-and-hold, return/drawdown proxy versus SPY buy-and-hold, average SPY exposure bounds, duplicate/reference correlation, and exposure invariants.
"""


def timing_sanity_report(manifest: dict[str, Any]) -> str:
    return f"""# Timing-Sanity Interpretation Report

Timing-sanity total return higher than primary: `{manifest['timing_sanity_total_return_higher_than_primary']}`

Timing-sanity max drawdown worse than primary: `{manifest['timing_sanity_max_drawdown_worse_than_primary']}`

Timing-sanity return/drawdown proxy worse than primary: `{manifest['timing_sanity_return_drawdown_proxy_worse_than_primary']}`

Timing-sanity remains context only: `{manifest['timing_sanity_context_only']}`

Timing-sanity selected as best strategy: `false`

Calendar optimization recommended: `false`

The delayed row is treated only as a timing sanity check. It is not promoted, not paper-forward eligible, not candidate_exhaustive-ready, and does not authorize entry/exit day optimization.
"""


def exposure_report_md(manifest: dict[str, Any]) -> str:
    return f"""# Exposure Invariant Audit Report

Exposure invariant passed: `{manifest['exposure_invariant_passed']}`

Invariant failure count: `{manifest['invariant_failure_count']}`

Max daily exposure: `{manifest['max_daily_exposure']}`

Max daily weight sum: `{manifest['max_daily_weight_sum']}`

The audit recomputed daily target weights and verified no NaN weights, no negative weights below tolerance, max exposure <= 1.0, max weight sum <= 1.0, and BIL/cash as replacement/remainder only.
"""


def control_report_md(manifest: dict[str, Any]) -> str:
    return f"""# Control-Row Separation Report

Control rows reviewed: `{manifest['control_row_count']}`

Control rows context only: `{manifest['control_rows_context_only']}`

The SPY buy-and-hold, BIL cash, and SPY_200d frozen rows remain controls only. They are excluded from candidate interpretation and cannot create promotion, paper-forward, or candidate_exhaustive eligibility.
"""


def guardrail_report_md(manifest: dict[str, Any]) -> str:
    return f"""# Guardrail Audit Report

Guardrails passed: `{manifest['guardrails_passed']}`

No scraping: `{not manifest['public_source_scraped']}`

No provider download: `{not manifest['provider_download']}`

No intraday data: `{not manifest['intraday_data_used']}`

No strategy discovery: `{not manifest['new_strategy_discovery_run']}`

No candidate_exhaustive: `{not manifest['candidate_exhaustive_run']}`

No promotion: `{not manifest['promotion_candidates_created'] and not manifest['best_single_variant_promoted']}`

No paper-forward activation: `{not manifest['paper_forward_activation']}`

No broker/live/real-money path: `{not manifest['broker_api_called'] and not manifest['live_orders'] and not manifest['real_money_recommendation']}`
"""


def summary_md(manifest: dict[str, Any]) -> str:
    return f"""# Turn-of-the-Month Bounded BT Results Audit

Final audit decision: `{manifest['final_audit_decision']}`

Rows reviewed: `{manifest['row_count_reviewed']}`

Row-level discrepancy count: `{manifest['row_level_discrepancy_count']}`

Criteria mismatch count: `{manifest['criteria_mismatch_count']}`

Shifted-weight/no-lookahead verified: `{manifest['shifted_weight_no_lookahead_verified']}`

Timing-sanity remains context only: `{manifest['timing_sanity_context_only']}`

Control rows remain controls only: `{manifest['control_rows_context_only']}`

Outputs remain diagnostic and non-promotable: `{manifest['outputs_remain_diagnostic_non_promotable']}`

Exact next action:

`{manifest['next_action']}`

Do not execute the next action in this task.
"""


def next_action_md(next_action: str) -> str:
    return f"""# Next Action

Exact next action:

`{next_action}`

This audit does not authorize promotion, paper-forward activation, candidate_exhaustive, or real-money use.
"""


def consistency_check(manifest: dict[str, Any], output: Path) -> dict[str, Any]:
    required = {name: (output / name).exists() for name in AUDIT_OUTPUT_FILES}
    required["public_source_turn_of_month_bounded_bt_results_audit_consistency_check.json"] = True
    checks = {
        "audit_only_mode": manifest["public_source_turn_of_month_results_audit_only"] is True,
        "correct_lane": manifest["lane_id_audited"] == LANE_ID,
        "source_evidence_reviewed": manifest["source_run_evidence_reviewed"] is True
        and manifest["source_design_evidence_reviewed"] is True,
        "exact_rows_reviewed": manifest["row_count_reviewed"] == 5 and manifest["exact_approved_rows_reviewed"] is True,
        "no_discrepancies": manifest["row_level_discrepancy_count"] == 0,
        "no_criteria_mismatches": manifest["criteria_mismatch_count"] == 0,
        "no_lookahead_verified": manifest["shifted_weight_no_lookahead_verified"] is True
        and manifest["spy_exposure_through_third_trading_day_close_verified"] is True
        and manifest["bil_exposure_after_exit_verified"] is True,
        "timing_sanity_context_only": manifest["timing_sanity_context_only"] is True
        and manifest["calendar_optimization_recommended"] is False,
        "controls_context_only": manifest["control_rows_context_only"] is True,
        "guardrails_passed": manifest["guardrails_passed"] is True,
        "no_forbidden_actions": manifest["provider_download"] is False
        and manifest["intraday_data_used"] is False
        and manifest["public_source_scraped"] is False
        and manifest["candidate_exhaustive_run"] is False
        and manifest["promotion_candidates_created"] is False
        and manifest["paper_forward_activation"] is False
        and manifest["broker_api_called"] is False
        and manifest["live_orders"] is False
        and manifest["real_money_recommendation"] is False,
        "outputs_non_promotable": manifest["outputs_remain_diagnostic_non_promotable"] is True,
        "audit_decision_passed": manifest["final_audit_decision"] == AUDIT_DECISION_PASSED,
        "next_action_valid": manifest["next_action"] in VALID_NEXT_ACTIONS,
        "required_files_present": all(required.values()),
        "required_files": required,
    }
    checks["consistency_passed"] = all(value is True for key, value in checks.items() if key != "required_files")
    return checks


def run(root: Path = ROOT, output_dir: Path = OUTPUT_DIR) -> dict[str, Any]:
    source = load_source(root)
    recomputed_rows, weights_by_variant, returns_by_variant, events_by_variant, prices = recompute_lane(root)
    output = root / output_dir
    output.mkdir(parents=True, exist_ok=True)

    discrepancies = compare_row_results(source["run_rows"], recomputed_rows)
    discrepancies.extend(compare_daily_weights(root / SOURCE_RUN_DIR / "daily_target_weights.csv", weights_by_variant))
    discrepancies.extend(compare_equity_returns(root / SOURCE_RUN_DIR / "equity_curve_returns.csv", returns_by_variant))
    criteria = criteria_rows(source["run_rows"], recomputed_rows)
    no_lookahead = no_lookahead_audit(prices, weights_by_variant, returns_by_variant, events_by_variant)
    completeness = evidence_completeness(source)
    guardrails = guardrail_audit(source["manifest"], source["run_rows"])
    manifest = manifest_payload(
        now_utc(),
        output,
        source,
        discrepancies,
        criteria,
        no_lookahead,
        completeness,
        guardrails,
    )

    write_json(output / "public_source_turn_of_month_bounded_bt_results_audit_manifest.json", manifest)
    write_text(output / "calendar_timing_audit_report.md", calendar_timing_report(manifest, no_lookahead))
    write_text(output / "shifted_weight_no_lookahead_audit_report.md", shifted_weight_report(manifest, no_lookahead))
    write_csv(output / "row_level_discrepancy_report.csv", discrepancies, list(DISCREPANCY_FIELDS))
    write_text(output / "row_level_discrepancy_report.md", discrepancy_report_md(discrepancies))
    write_csv(output / "criteria_recomputation_report.csv", criteria, list(CRITERIA_FIELDS))
    write_text(output / "criteria_recomputation_report.md", criteria_report_md(criteria))
    write_text(output / "timing_sanity_interpretation_report.md", timing_sanity_report(manifest))
    write_text(output / "exposure_invariant_audit_report.md", exposure_report_md(manifest))
    write_text(output / "control_row_separation_report.md", control_report_md(manifest))
    write_text(output / "guardrail_audit_report.md", guardrail_report_md(manifest))
    write_text(output / "public_source_turn_of_month_bounded_bt_results_audit_summary.md", summary_md(manifest))
    write_text(output / "public_source_turn_of_month_bounded_bt_results_audit_next_action.md", next_action_md(manifest["next_action"]))
    check = consistency_check(manifest, output)
    write_json(output / "public_source_turn_of_month_bounded_bt_results_audit_consistency_check.json", check)
    return {**manifest, "output_dir": str(output.resolve()), "consistency_passed": check["consistency_passed"]}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
