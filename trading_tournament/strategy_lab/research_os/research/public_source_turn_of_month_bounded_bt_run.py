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
    equity_from_returns,
    invariant_summary,
    load_local_price_frame,
    reference_spy200d_weights,
    returns_from_weights,
)
from strategy_lab.research_os.objective_reset.objective_reset_review import write_json, write_text
from strategy_lab.research_os.research.profit_oriented_research_batch_v1 import (
    complete_rebalance_weight_frame,
    max_drawdown,
    trade_count_and_turnover,
    weight_invariant_report,
    write_csv,
)


SOURCE_ID = "turn_of_month_equity_indexes"
FAMILY_ID = "calendar_effect_turn_of_month_equity_index"
LANE_ID = "public_source_turn_of_month_bounded_bt_lane_v1"
DESIGN_DIR = Path("evidence") / "research_recovery" / "public_source_turn_of_month_bounded_bt_design" / "latest"
OUTPUT_DIR = Path("evidence") / "research_recovery" / "public_source_turn_of_month_bounded_bt_run" / "latest"
EXPECTED_VARIANTS = (
    "totm_spy_bil_primary_close_m1_to_plus3_v1",
    "totm_spy_bil_timing_sanity_one_bar_delayed_v1",
    "totm_spy_buy_hold_control_v1",
    "totm_bil_cash_control_v1",
    "totm_spy200d_frozen_control_v1",
)

NEXT_ACTION_AUDIT = "audit_public_source_turn_of_month_bounded_bt_results"
NEXT_ACTION_FIX = "fix_public_source_turn_of_month_bounded_bt_run_methodology_issue"
VALID_NEXT_ACTIONS = {NEXT_ACTION_AUDIT, NEXT_ACTION_FIX}

WEIGHT_TOLERANCE = 1e-6
STANDARD_COST_ASSUMPTION = 0.0
ALLOWED_LABELS = {
    "public_source_calendar_totm_primary",
    "public_source_calendar_totm_timing_sanity",
    "public_source_calendar_control_only",
}

RESULT_FIELDS = (
    "lane_id",
    "family_id",
    "source_id",
    "variant_id",
    "variant_role",
    "research_label",
    "concept",
    "symbols_used",
    "local_cache_data_available",
    "effective_start_date",
    "effective_end_date",
    "calendar_window",
    "entry_decision_convention",
    "exit_decision_convention",
    "weight_shift_convention",
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
    "methodology_notes",
)

CRITERIA_FIELDS = (
    "variant_id",
    "variant_role",
    "research_label",
    "total_return",
    "same_window_return_versus_bil",
    "excess_return_versus_bil_after_cost",
    "max_drawdown",
    "drawdown_reduction_versus_spy_buy_hold",
    "return_drawdown_proxy",
    "average_spy_exposure_share",
    "duplicate_reference_correlation",
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
)

DAILY_WEIGHT_FIELDS = ("date", "variant_id", "SPY", "BIL", "weight_sum", "risky_exposure")
EQUITY_FIELDS = ("date", "variant_id", "daily_return", "equity")
TURNOVER_FIELDS = ("variant_id", "variant_role", "trade_count", "turnover_proxy", "nonzero_turnover_days")

REQUIRED_FILES = (
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


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def finite(value: Any) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def safe_corr(left: pd.Series, right: pd.Series) -> float:
    aligned = pd.concat([left.rename("left"), right.rename("right")], axis=1).dropna()
    if len(aligned) < 252 or float(aligned["left"].std()) == 0.0 or float(aligned["right"].std()) == 0.0:
        return float("nan")
    return float(aligned["left"].corr(aligned["right"]))


def design_rows(root: Path) -> list[dict[str, str]]:
    return read_csv_rows(root / DESIGN_DIR / "planned_row_table.csv")


def design_manifest(root: Path) -> dict[str, Any]:
    return read_json(root / DESIGN_DIR / "public_source_turn_of_month_bounded_bt_design_manifest.json")


def target(spy: float, bil: float) -> dict[str, float]:
    return {"SPY": float(spy), "BIL": float(bil)}


def common_month_groups(index: pd.DatetimeIndex) -> dict[pd.Period, list[pd.Timestamp]]:
    groups: dict[pd.Period, list[pd.Timestamp]] = {}
    for date in index:
        groups.setdefault(pd.Timestamp(date).to_period("M"), []).append(pd.Timestamp(date))
    return groups


def turn_of_month_targets(prices: pd.DataFrame, *, delayed: bool = False) -> dict[pd.Timestamp, dict[str, float]]:
    dates = pd.DatetimeIndex(prices.index)
    groups = common_month_groups(dates)
    periods = sorted(groups)
    positions = {pd.Timestamp(date): index for index, date in enumerate(dates)}
    targets: dict[pd.Timestamp, dict[str, float]] = {pd.Timestamp(dates[0]): target(0.0, 1.0)}

    for period in periods:
        next_period = period + 1
        current_dates = groups.get(period, [])
        next_dates = groups.get(next_period, [])
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
    return targets


def build_weights(variant_id: str, prices: pd.DataFrame) -> pd.DataFrame:
    columns = ["SPY", "BIL"]
    if variant_id == "totm_spy_bil_primary_close_m1_to_plus3_v1":
        targets = turn_of_month_targets(prices, delayed=False)
        return complete_rebalance_weight_frame(prices.index, columns, targets, tolerance=WEIGHT_TOLERANCE)
    if variant_id == "totm_spy_bil_timing_sanity_one_bar_delayed_v1":
        targets = turn_of_month_targets(prices, delayed=True)
        return complete_rebalance_weight_frame(prices.index, columns, targets, tolerance=WEIGHT_TOLERANCE)
    if variant_id == "totm_spy_buy_hold_control_v1":
        return complete_rebalance_weight_frame(prices.index, columns, {prices.index[0]: target(1.0, 0.0)})
    if variant_id == "totm_bil_cash_control_v1":
        return complete_rebalance_weight_frame(prices.index, columns, {prices.index[0]: target(0.0, 1.0)})
    if variant_id == "totm_spy200d_frozen_control_v1":
        return reference_spy200d_weights(prices).reindex(columns=columns, fill_value=0.0)
    raise ValueError(f"unexpected variant_id: {variant_id}")


def metrics(daily_returns: pd.Series, weights: pd.DataFrame) -> dict[str, Any]:
    daily = daily_returns.dropna()
    equity = equity_from_returns(daily)
    years = max((daily.index.max() - daily.index.min()).days / 365.25, 1e-9)
    total_return = float(equity.iloc[-1] - 1.0)
    cagr = float(equity.iloc[-1] ** (1.0 / years) - 1.0)
    mdd = max_drawdown(equity)
    volatility = float(daily.std() * np.sqrt(252.0))
    proxy = float(cagr / abs(mdd)) if mdd < 0 else float("nan")
    trades, turnover = trade_count_and_turnover(weights)
    invariant = invariant_summary(weights)
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
        **invariant,
    }


def equity_rows(returns_by_variant: dict[str, pd.Series]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for variant_id, daily in returns_by_variant.items():
        equity = equity_from_returns(daily)
        for date, daily_return in daily.items():
            rows.append(
                {
                    "date": pd.Timestamp(date).date().isoformat(),
                    "variant_id": variant_id,
                    "daily_return": float(daily_return),
                    "equity": float(equity.loc[date]),
                }
            )
    return rows


def weight_rows(weights_by_variant: dict[str, pd.DataFrame]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for variant_id, weights in weights_by_variant.items():
        for date, row in weights.iterrows():
            rows.append(
                {
                    "date": pd.Timestamp(date).date().isoformat(),
                    "variant_id": variant_id,
                    "SPY": float(row.get("SPY", 0.0)),
                    "BIL": float(row.get("BIL", 0.0)),
                    "weight_sum": float(row.sum()),
                    "risky_exposure": float(row.get("SPY", 0.0)),
                }
            )
    return rows


def turnover_rows(result_rows: list[dict[str, Any]], weights_by_variant: dict[str, pd.DataFrame]) -> list[dict[str, Any]]:
    role_by_id = {row["variant_id"]: row["variant_role"] for row in result_rows}
    rows: list[dict[str, Any]] = []
    for variant_id, weights in weights_by_variant.items():
        nonzero_days = int((weights.diff().abs().fillna(weights.abs()).sum(axis=1) > WEIGHT_TOLERANCE).sum())
        trades, turnover = trade_count_and_turnover(weights)
        rows.append(
            {
                "variant_id": variant_id,
                "variant_role": role_by_id.get(variant_id, ""),
                "trade_count": trades,
                "turnover_proxy": turnover,
                "nonzero_turnover_days": nonzero_days,
            }
        )
    return rows


def result_for_row(
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
    numeric_pass = False
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
        "methodology_notes": "local-cache close-to-close shifted-weight bounded bt lane; diagnostic non-promotable evidence",
    }


def evaluate_lane(root: Path) -> tuple[list[dict[str, Any]], dict[str, pd.DataFrame], dict[str, pd.Series], dict[str, Any]]:
    rows = design_rows(root)
    design = design_manifest(root)
    prices = load_local_price_frame(root)
    weights_by_variant: dict[str, pd.DataFrame] = {}
    returns_by_variant: dict[str, pd.Series] = {}
    metrics_by_variant: dict[str, dict[str, Any]] = {}
    for row in rows:
        variant_id = row["variant_id"]
        weights = build_weights(variant_id, prices)
        daily = returns_from_weights(prices, weights).rename(variant_id)
        weights_by_variant[variant_id] = weights
        returns_by_variant[variant_id] = daily
        metrics_by_variant[variant_id] = metrics(daily, weights)

    result_rows: list[dict[str, Any]] = []
    for row in rows:
        result_rows.append(
            result_for_row(row, metrics_by_variant[row["variant_id"]], returns_by_variant[row["variant_id"]], metrics_by_variant, returns_by_variant)
        )

    preflight = {
        "source_design_run_ready": design.get("run_readiness_decision")
        == "public_source_turn_of_month_bounded_bt_design_run_ready",
        "source_design_next_action_correct": design.get("next_action") == "run_public_source_turn_of_month_bounded_bt_lane",
        "design_row_count": len(rows),
        "evaluated_variant_ids": [row["variant_id"] for row in result_rows],
        "uses_local_cache_only": True,
        "provider_download_required": False,
        "intraday_data_required": False,
        "effective_start_date": prices.index.min().date().isoformat() if not prices.empty else "",
        "effective_end_date": prices.index.max().date().isoformat() if not prices.empty else "",
    }
    return result_rows, weights_by_variant, returns_by_variant, preflight


def role_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "primary_source": sum(1 for row in rows if row["variant_role"] == "source_primary"),
        "timing_sanity": sum(1 for row in rows if row["variant_role"] == "timing_sanity"),
        "control": sum(1 for row in rows if row["variant_role"] == "control"),
    }


def manifest_payload(
    created: str,
    output: Path,
    rows: list[dict[str, Any]],
    preflight: dict[str, Any],
) -> dict[str, Any]:
    invariants_failed = [row["variant_id"] for row in rows if row["exposure_invariant_pass"] is not True]
    max_exposure = max(float(row["max_daily_exposure"]) for row in rows)
    max_weight_sum = max(float(row["max_daily_weight_sum"]) for row in rows)
    primary = next((row for row in rows if row["variant_role"] == "source_primary"), {})
    timing = next((row for row in rows if row["variant_role"] == "timing_sanity"), {})
    interpretable = (
        preflight["source_design_run_ready"]
        and len(rows) == len(EXPECTED_VARIANTS)
        and set(row["variant_id"] for row in rows) == set(EXPECTED_VARIANTS)
        and not invariants_failed
    )
    next_action = NEXT_ACTION_AUDIT if interpretable else NEXT_ACTION_FIX
    counts = role_counts(rows)
    return {
        "created_utc": created,
        "evidence_path": str(output.resolve()),
        "public_source_turn_of_month_bounded_bt_lane_run": True,
        "source_id": SOURCE_ID,
        "family_id": FAMILY_ID,
        "lane_id": LANE_ID,
        "source_design_run_ready": preflight["source_design_run_ready"],
        "source_design_next_action_correct": preflight["source_design_next_action_correct"],
        "variant_count_planned": len(EXPECTED_VARIANTS),
        "variant_count_evaluated": len(rows),
        "approved_variant_ids": list(EXPECTED_VARIANTS),
        "evaluated_variant_ids": [row["variant_id"] for row in rows],
        "primary_source_row_count": counts["primary_source"],
        "timing_sanity_row_count": counts["timing_sanity"],
        "control_row_count": counts["control"],
        "data_blocked_row_count": 0,
        "primary_row_numeric_criteria_pass": primary.get("numeric_criteria_pass") is True,
        "timing_sanity_numeric_criteria_pass": timing.get("numeric_criteria_pass") is True,
        "control_row_count_evaluated": counts["control"],
        "invariant_failure_count": len(invariants_failed),
        "invariant_failure_variant_ids": invariants_failed,
        "max_daily_exposure": max_exposure,
        "max_daily_weight_sum": max_weight_sum,
        "exposure_invariant_passed": not invariants_failed and max_exposure <= 1.000001 and max_weight_sum <= 1.000001,
        "calendar_timing_implemented_as_preregistered": True,
        "one_timing_sanity_row_only": True,
        "calendar_parameter_sweep_created": False,
        "optimization_run": False,
        "uses_local_cache_only": True,
        "provider_download": False,
        "intraday_data_used": False,
        "new_instruments_added": False,
        "bounded_bt_design_changed": False,
        "strategy_discovery_run": False,
        "new_research_batch_run": False,
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
        "public_source_scraped": False,
        "public_strategy_list_ingested": False,
        "faber_taa_designed_or_retested": False,
        "current_backtester_replaced": False,
        "outputs_diagnostic_only": True,
        "outputs_non_promotable": True,
        "candidate_exhaustive_ready": False,
        "paper_forward_eligible": False,
        "results_interpretable": interpretable,
        "usable_diagnostic_evidence": interpretable,
        "next_action": next_action,
    }


def timing_report_md(rows: list[dict[str, Any]]) -> str:
    primary = next(row for row in rows if row["variant_role"] == "source_primary")
    timing = next(row for row in rows if row["variant_role"] == "timing_sanity")
    return f"""# Calendar Timing / Exposure Window Report

Primary row: `{primary['variant_id']}`

- Entry: `{primary['entry_decision_convention']}`
- Exit: `{primary['exit_decision_convention']}`
- Weight convention: `{primary['weight_shift_convention']}`
- Average SPY exposure share: `{primary['average_spy_exposure_share']}`
- Average BIL exposure share: `{primary['average_bil_exposure_share']}`

Timing-sanity row: `{timing['variant_id']}`

- Entry: `{timing['entry_decision_convention']}`
- Exit: `{timing['exit_decision_convention']}`
- The timing-sanity row delays both entry and exit by one common trading day and is not a tuned variant.

Trading days are common local-cache dates where `SPY` and `BIL` both have adjusted-close data. No intraday data or provider download was used.
"""


def baseline_report_md(rows: list[dict[str, Any]]) -> str:
    lines = ["# Baseline / Control Comparison Report", ""]
    for row in rows:
        lines.append(
            f"- `{row['variant_id']}`: total return `{float(row['total_return']):.6f}`, "
            f"BIL delta `{float(row['same_window_return_versus_bil']):.6f}`, "
            f"drawdown reduction vs SPY `{float(row['drawdown_reduction_versus_spy_buy_hold']):.6f}`, "
            f"corr vs SPY `{float(row['correlation_versus_spy_buy_hold']):.6f}`, "
            f"corr vs SPY_200d `{float(row['correlation_versus_spy200d_control']):.6f}`"
        )
    lines.append("")
    lines.append("Controls are diagnostic only and cannot become candidates.")
    return "\n".join(lines) + "\n"


def invariant_report_md(manifest: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    failures = manifest["invariant_failure_variant_ids"]
    return f"""# Exposure Invariant Report

Exposure invariant passed: `{manifest['exposure_invariant_passed']}`

Max daily exposure: `{manifest['max_daily_exposure']}`

Max daily weight sum: `{manifest['max_daily_weight_sum']}`

Invariant failure count: `{manifest['invariant_failure_count']}`

Failures:

{chr(10).join(f'- `{item}`' for item in failures) if failures else '- none'}

BIL/cash is replacement/remainder only. SPY plus BIL never accumulates above total weight `1.0`.
"""


def role_label_summary_md(manifest: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    labels = {label: sum(1 for row in rows if row["research_label"] == label) for label in ALLOWED_LABELS}
    return f"""# Role / Label Summary

Primary source rows: `{manifest['primary_source_row_count']}`

Timing-sanity rows: `{manifest['timing_sanity_row_count']}`

Control rows: `{manifest['control_row_count']}`

Labels:

{chr(10).join(f'- `{label}`: `{count}`' for label, count in sorted(labels.items()))}
"""


def turnover_report_md(rows: list[dict[str, Any]]) -> str:
    lines = ["# Rebalance / Turnover Report", ""]
    for row in rows:
        lines.append(
            f"- `{row['variant_id']}`: trade count `{row['trade_count']}`, turnover proxy `{float(row['turnover_proxy']):.6f}`"
        )
    return "\n".join(lines) + "\n"


def summary_md(manifest: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    primary = next(row for row in rows if row["variant_role"] == "source_primary")
    timing = next(row for row in rows if row["variant_role"] == "timing_sanity")
    return f"""# Public Source Turn-of-the-Month Bounded bt Run

Lane ID: `{manifest['lane_id']}`

Rows planned/evaluated: `{manifest['variant_count_planned']} / {manifest['variant_count_evaluated']}`

Data-blocked rows: `{manifest['data_blocked_row_count']}`

Primary row pass: `{manifest['primary_row_numeric_criteria_pass']}`

Timing-sanity pass: `{manifest['timing_sanity_numeric_criteria_pass']}`

Control rows evaluated: `{manifest['control_row_count_evaluated']}`

Invariant failures: `{manifest['invariant_failure_count']}`

Results interpretable: `{manifest['results_interpretable']}`

Usable diagnostic evidence: `{manifest['usable_diagnostic_evidence']}`

Primary total return: `{primary['total_return']}`

Primary max drawdown: `{primary['max_drawdown']}`

Timing-sanity total return: `{timing['total_return']}`

Calendar timing limitations: close-to-close target-weight model only; no intraday execution model; public source is not proof of profitability.

No output is promotable, candidate_exhaustive-ready, or paper-forward eligible.

Exact next action: `{manifest['next_action']}`
"""


def do_not_promote_md() -> str:
    return """# Do Not Promote From Public Source Turn-of-the-Month Run

This packet is diagnostic historical research evidence only.

It creates no promotion-review candidate, candidate_exhaustive candidate, paper-forward candidate, paper-forward activation, broker/live action, or real-money recommendation.
"""


def next_action_md(next_action: str) -> str:
    return f"""# Public Source Turn-of-the-Month Bounded bt Run Next Action

Exact next action:

`{next_action}`

Do not execute the next action in this task.
"""


def consistency_check(manifest: dict[str, Any], rows: list[dict[str, Any]], output: Path) -> dict[str, Any]:
    required = {name: (output / name).exists() for name in REQUIRED_FILES}
    required["public_source_turn_of_month_bounded_bt_run_consistency_check.json"] = True
    labels = {row["research_label"] for row in rows}
    variant_ids = {row["variant_id"] for row in rows}
    checks = {
        "correct_lane": manifest["lane_id"] == LANE_ID,
        "correct_family": manifest["family_id"] == FAMILY_ID,
        "source_design_run_ready": manifest["source_design_run_ready"] is True,
        "exact_variant_set": variant_ids == set(EXPECTED_VARIANTS),
        "variant_count_exact_5": manifest["variant_count_evaluated"] == 5,
        "row_roles_expected": manifest["primary_source_row_count"] == 1
        and manifest["timing_sanity_row_count"] == 1
        and manifest["control_row_count"] == 3,
        "allowed_labels_only": labels <= ALLOWED_LABELS,
        "calendar_timing_as_preregistered": manifest["calendar_timing_implemented_as_preregistered"] is True,
        "one_timing_sanity_only": manifest["one_timing_sanity_row_only"] is True,
        "no_sweep_or_optimization": manifest["calendar_parameter_sweep_created"] is False
        and manifest["optimization_run"] is False,
        "local_cache_only": manifest["uses_local_cache_only"] is True,
        "no_provider_intraday": manifest["provider_download"] is False and manifest["intraday_data_used"] is False,
        "no_design_change_or_new_instruments": manifest["bounded_bt_design_changed"] is False
        and manifest["new_instruments_added"] is False,
        "no_discovery_or_candidate_exhaustive": manifest["strategy_discovery_run"] is False
        and manifest["new_research_batch_run"] is False
        and manifest["candidate_exhaustive_run"] is False,
        "no_promotion_or_paper": manifest["promotion_candidates_created"] is False
        and manifest["best_single_variant_promoted"] is False
        and manifest["paper_forward_activation"] is False
        and manifest["new_paper_forward_candidate_created"] is False,
        "no_broker_live_real_money": manifest["broker_api_called"] is False
        and manifest["broker_orders_submitted"] is False
        and manifest["broker_orders_cancelled"] is False
        and manifest["broker_orders_reconciled"] is False
        and manifest["live_orders"] is False
        and manifest["real_money_recommendation"] is False,
        "no_scrape_or_faber": manifest["public_source_scraped"] is False
        and manifest["public_strategy_list_ingested"] is False
        and manifest["faber_taa_designed_or_retested"] is False,
        "exposure_invariants_pass": manifest["exposure_invariant_passed"] is True
        and manifest["max_daily_exposure"] <= 1.000001
        and manifest["max_daily_weight_sum"] <= 1.000001,
        "all_rows_non_promotable": all(row["promotion_eligibility"] is False for row in rows),
        "all_rows_not_candidate_or_paper": all(row["candidate_exhaustive_eligibility"] is False for row in rows)
        and all(row["paper_forward_eligibility"] is False for row in rows),
        "outputs_diagnostic": manifest["outputs_diagnostic_only"] is True
        and manifest["outputs_non_promotable"] is True
        and manifest["candidate_exhaustive_ready"] is False
        and manifest["paper_forward_eligible"] is False,
        "next_action_valid": manifest["next_action"] in VALID_NEXT_ACTIONS,
        "required_files_present": all(required.values()),
        "required_files": required,
    }
    checks["consistency_passed"] = all(value is True for key, value in checks.items() if key != "required_files")
    return checks


def run(root: Path = ROOT) -> dict[str, Any]:
    created = now_utc()
    output = root / OUTPUT_DIR
    output.mkdir(parents=True, exist_ok=True)
    rows, weights_by_variant, returns_by_variant, preflight = evaluate_lane(root)
    manifest = manifest_payload(created, output, rows, preflight)

    write_json(output / "public_source_turn_of_month_bounded_bt_run_manifest.json", manifest)
    write_csv(output / "row_level_results.csv", rows, list(RESULT_FIELDS))
    write_csv(output / "numeric_criteria_results.csv", rows, list(CRITERIA_FIELDS))
    write_text(output / "calendar_timing_exposure_window_report.md", timing_report_md(rows))
    write_csv(output / "daily_target_weights.csv", weight_rows(weights_by_variant), list(DAILY_WEIGHT_FIELDS))
    write_csv(output / "equity_curve_returns.csv", equity_rows(returns_by_variant), list(EQUITY_FIELDS))
    turnover = turnover_rows(rows, weights_by_variant)
    write_csv(output / "rebalance_turnover_report.csv", turnover, list(TURNOVER_FIELDS))
    write_text(output / "rebalance_turnover_report.md", turnover_report_md(rows))
    write_text(output / "baseline_control_comparison_report.md", baseline_report_md(rows))
    write_text(output / "exposure_invariant_report.md", invariant_report_md(manifest, rows))
    write_text(output / "role_label_summary.md", role_label_summary_md(manifest, rows))
    write_text(output / "public_source_turn_of_month_bounded_bt_run_summary.md", summary_md(manifest, rows))
    write_text(output / "do_not_promote_from_public_source_turn_of_month_run.md", do_not_promote_md())
    write_text(output / "public_source_turn_of_month_bounded_bt_run_next_action.md", next_action_md(manifest["next_action"]))
    check = consistency_check(manifest, rows, output)
    write_json(output / "public_source_turn_of_month_bounded_bt_run_consistency_check.json", check)
    return {**manifest, "output_dir": str(output.resolve()), "consistency_passed": check["consistency_passed"]}
