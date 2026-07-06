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
    write_csv,
)


SOURCE_ID = "coppock_curve_monthly_equity_signal"
FAMILY_ID = "long_term_equity_index_momentum_zero_cross"
LANE_ID = "public_source_coppock_curve_bounded_bt_lane_v1"
DESIGN_DIR = Path("evidence") / "research_recovery" / "public_source_coppock_curve_bounded_bt_design" / "latest"
OUTPUT_DIR = Path("evidence") / "research_recovery" / "public_source_coppock_curve_bounded_bt_run" / "latest"

EXPECTED_VARIANTS = (
    "coppock_spy_bil_monthly_zero_cross_primary_v1",
    "coppock_spy_bil_one_month_delayed_timing_sanity_v1",
    "coppock_spy_buy_hold_control_v1",
    "coppock_bil_cash_control_v1",
    "coppock_spy200d_frozen_control_v1",
)
SIMILARITY_CONTEXTS = (
    "spy200d_trend_control",
    "global_multi_asset",
    "macro_gld_duration_risk_off",
    "high_return_tactical_equity",
    "volatility_throttle_volatility_managed_equity",
    "turn_of_month_calendar_effect",
    "mean_reversion_rejected_or_existing_candidate",
    "price_band_money_flow_confirmation",
)

NEXT_ACTION_AUDIT = "audit_public_source_coppock_curve_bounded_bt_results"
NEXT_ACTION_FIX = "fix_public_source_coppock_curve_bounded_bt_run_methodology_issue"
VALID_NEXT_ACTIONS = {NEXT_ACTION_AUDIT, NEXT_ACTION_FIX}

ROC_PERIODS = (14, 11)
WMA_SMOOTHING_PERIOD = 10
SIGNAL_THRESHOLD = 0.0
WEIGHT_TOLERANCE = 1e-6
STANDARD_COST_ASSUMPTION = 0.0
SPARSE_ROUND_TRIP_THRESHOLD = 3

ALLOWED_LABELS = {
    "public_source_coppock_curve_primary",
    "public_source_coppock_curve_timing_sanity",
    "public_source_coppock_curve_control_only",
    "public_source_coppock_curve_sparse_context_only",
}

RESULT_FIELDS = (
    "lane_id",
    "family_id",
    "source_id",
    "variant_id",
    "variant_role",
    "research_label",
    "symbols_used",
    "effective_start_date",
    "effective_end_date",
    "monthly_observation_count",
    "trading_days_covered",
    "formula_status",
    "roc_periods",
    "wma_smoothing_period",
    "signal_threshold",
    "signal_timing_convention",
    "weight_shift_convention",
    "positive_zero_cross_entry_count",
    "negative_zero_cross_exit_count",
    "completed_round_trip_event_count",
    "average_holding_duration",
    "median_holding_duration",
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
    "turnover_proxy",
    "trade_count",
    "sparse_signal_label",
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
    "primary_sparse_signal_adequacy_pass",
    "timing_sanity_context_only",
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
    "positive_zero_cross_entry_count",
    "negative_zero_cross_exit_count",
    "completed_round_trip_event_count",
    "sparse_signal_label",
    "exposure_invariant_pass",
    "primary_total_return_beats_bil",
    "primary_excess_after_cost_beats_bil",
    "primary_drawdown_reduction_pass",
    "primary_return_drawdown_proxy_pass",
    "primary_spy_exposure_bounds_pass",
    "primary_duplicate_correlation_pass",
    "primary_sparse_signal_adequacy_pass",
    "timing_sanity_context_only",
    "numeric_criteria_pass",
)
DAILY_WEIGHT_FIELDS = ("date", "variant_id", "SPY", "BIL", "weight_sum", "risky_exposure")
EQUITY_FIELDS = ("date", "variant_id", "daily_return", "equity")
TURNOVER_FIELDS = ("variant_id", "variant_role", "trade_count", "turnover_proxy", "nonzero_turnover_days")
EVENT_FIELDS = (
    "event_number",
    "signal_month",
    "signal_close_date",
    "primary_effective_date",
    "timing_sanity_effective_date",
    "signal_type",
    "previous_coppock",
    "coppock",
    "active_after_signal",
)

REQUIRED_FILES = (
    "public_source_coppock_curve_bounded_bt_run_manifest.json",
    "public_source_coppock_curve_bounded_bt_run_consistency_check.json",
    "row_level_results.csv",
    "numeric_criteria_results.csv",
    "monthly_coppock_formula_calculation_report.md",
    "monthly_signal_timing_no_lookahead_report.md",
    "monthly_signal_event_table.csv",
    "daily_target_weights.csv",
    "equity_curve_returns.csv",
    "rebalance_turnover_report.csv",
    "rebalance_turnover_report.md",
    "sparse_signal_adequacy_report.md",
    "baseline_control_comparison_report.md",
    "exposure_invariant_report.md",
    "similarity_risk_report.md",
    "sell_exit_caveat_carry_forward_report.md",
    "role_label_summary.md",
    "public_source_coppock_curve_bounded_bt_run_summary.md",
    "do_not_promote_from_public_source_coppock_curve_run.md",
    "public_source_coppock_curve_bounded_bt_run_next_action.md",
)


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
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
    return read_json(root / DESIGN_DIR / "public_source_coppock_curve_bounded_bt_design_manifest.json")


def target(spy: float, bil: float) -> dict[str, float]:
    return {"SPY": float(spy), "BIL": float(bil)}


def weighted_moving_average(values: np.ndarray) -> float:
    weights = np.arange(1, len(values) + 1, dtype=float)
    return float(np.dot(values, weights) / weights.sum())


def monthly_coppock_frame(prices: pd.DataFrame) -> pd.DataFrame:
    if prices.empty or "SPY" not in prices.columns:
        return pd.DataFrame()
    spy = prices["SPY"].dropna().astype(float)
    rows: list[dict[str, Any]] = []
    for period, series in spy.groupby(spy.index.to_period("M")):
        close_date = pd.Timestamp(series.index.max())
        rows.append(
            {
                "signal_month": str(period),
                "signal_close_date": close_date,
                "monthly_close": float(series.loc[close_date]),
            }
        )
    monthly = pd.DataFrame(rows)
    if monthly.empty:
        return monthly
    monthly = monthly.set_index("signal_close_date").sort_index()
    close = monthly["monthly_close"]
    monthly["roc_14"] = close / close.shift(ROC_PERIODS[0]) - 1.0
    monthly["roc_11"] = close / close.shift(ROC_PERIODS[1]) - 1.0
    monthly["roc_sum"] = monthly["roc_14"] + monthly["roc_11"]
    monthly["coppock"] = monthly["roc_sum"].rolling(WMA_SMOOTHING_PERIOD, min_periods=WMA_SMOOTHING_PERIOD).apply(
        weighted_moving_average,
        raw=True,
    )
    monthly["previous_coppock"] = monthly["coppock"].shift(1)
    monthly["positive_zero_cross"] = (monthly["previous_coppock"] < SIGNAL_THRESHOLD) & (
        monthly["coppock"] > SIGNAL_THRESHOLD
    )
    monthly["negative_zero_cross"] = (monthly["previous_coppock"] > SIGNAL_THRESHOLD) & (
        monthly["coppock"] < SIGNAL_THRESHOLD
    )
    return monthly


def next_trading_date(index: pd.DatetimeIndex, after_date: pd.Timestamp) -> pd.Timestamp | None:
    position = index.searchsorted(pd.Timestamp(after_date), side="right")
    if position >= len(index):
        return None
    return pd.Timestamp(index[position])


def delayed_month_effective_date(
    prices_index: pd.DatetimeIndex,
    monthly: pd.DataFrame,
    signal_close_date: pd.Timestamp,
) -> pd.Timestamp | None:
    if signal_close_date not in monthly.index:
        return None
    position = monthly.index.get_loc(signal_close_date)
    if isinstance(position, slice) or isinstance(position, np.ndarray):
        return None
    delayed_position = int(position) + 1
    if delayed_position >= len(monthly.index):
        return None
    delayed_signal_close = pd.Timestamp(monthly.index[delayed_position])
    return next_trading_date(prices_index, delayed_signal_close)


def first_valid_run_start(prices_index: pd.DatetimeIndex, monthly: pd.DataFrame) -> pd.Timestamp | None:
    valid = monthly.loc[monthly["coppock"].notna()] if not monthly.empty and "coppock" in monthly else pd.DataFrame()
    if valid.empty:
        return None
    return next_trading_date(prices_index, pd.Timestamp(valid.index.min()))


def coppock_events(prices_index: pd.DatetimeIndex, monthly: pd.DataFrame) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    active = False
    for signal_close_date, row in monthly.iterrows():
        if not finite(row.get("coppock")) or not finite(row.get("previous_coppock")):
            continue
        signal_type = ""
        if not active and bool(row.get("positive_zero_cross")):
            active = True
            signal_type = "positive_zero_cross_entry"
        elif active and bool(row.get("negative_zero_cross")):
            active = False
            signal_type = "negative_zero_cross_exit"
        if not signal_type:
            continue
        primary_date = next_trading_date(prices_index, pd.Timestamp(signal_close_date))
        if primary_date is None:
            continue
        events.append(
            {
                "event_number": len(events) + 1,
                "signal_month": str(row["signal_month"]),
                "signal_close_date": pd.Timestamp(signal_close_date).date().isoformat(),
                "primary_effective_date": primary_date.date().isoformat(),
                "timing_sanity_effective_date": (
                    delayed_month_effective_date(prices_index, monthly, pd.Timestamp(signal_close_date)).date().isoformat()
                    if delayed_month_effective_date(prices_index, monthly, pd.Timestamp(signal_close_date)) is not None
                    else ""
                ),
                "signal_type": signal_type,
                "previous_coppock": float(row["previous_coppock"]),
                "coppock": float(row["coppock"]),
                "active_after_signal": active,
            }
        )
    return events


def target_map_from_events(
    events: list[dict[str, Any]],
    initial_date: pd.Timestamp,
    *,
    delayed: bool = False,
) -> dict[pd.Timestamp, dict[str, float]]:
    targets: dict[pd.Timestamp, dict[str, float]] = {pd.Timestamp(initial_date): target(0.0, 1.0)}
    date_key = "timing_sanity_effective_date" if delayed else "primary_effective_date"
    for event in events:
        raw_date = event.get(date_key)
        if not raw_date:
            continue
        effective_date = pd.Timestamp(str(raw_date))
        if event["signal_type"] == "positive_zero_cross_entry":
            targets[effective_date] = target(1.0, 0.0)
        elif event["signal_type"] == "negative_zero_cross_exit":
            targets[effective_date] = target(0.0, 1.0)
    return targets


def constant_weights(index: pd.DatetimeIndex, spy: float, bil: float) -> pd.DataFrame:
    return complete_rebalance_weight_frame(index, ["SPY", "BIL"], {index[0]: target(spy, bil)})


def build_weights(
    variant_id: str,
    prices: pd.DataFrame,
    full_prices: pd.DataFrame,
    events: list[dict[str, Any]],
) -> pd.DataFrame:
    common_index = pd.DatetimeIndex(prices.index)
    if variant_id == "coppock_spy_bil_monthly_zero_cross_primary_v1":
        targets = target_map_from_events(events, pd.Timestamp(common_index[0]), delayed=False)
        return complete_rebalance_weight_frame(common_index, ["SPY", "BIL"], targets, tolerance=WEIGHT_TOLERANCE)
    if variant_id == "coppock_spy_bil_one_month_delayed_timing_sanity_v1":
        targets = target_map_from_events(events, pd.Timestamp(common_index[0]), delayed=True)
        return complete_rebalance_weight_frame(common_index, ["SPY", "BIL"], targets, tolerance=WEIGHT_TOLERANCE)
    if variant_id == "coppock_spy_buy_hold_control_v1":
        return constant_weights(common_index, 1.0, 0.0)
    if variant_id == "coppock_bil_cash_control_v1":
        return constant_weights(common_index, 0.0, 1.0)
    if variant_id == "coppock_spy200d_frozen_control_v1":
        control = reference_spy200d_weights(full_prices).reindex(common_index).ffill().fillna(0.0)
        return control.reindex(columns=["SPY", "BIL"], fill_value=0.0)
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
        "trading_days_covered": int(len(daily)),
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


def holding_stats(events: list[dict[str, Any]], trading_index: pd.DatetimeIndex) -> dict[str, Any]:
    positions = {pd.Timestamp(date).date().isoformat(): idx for idx, date in enumerate(trading_index)}
    durations: list[int] = []
    open_entry: str | None = None
    for event in events:
        effective = str(event["primary_effective_date"])
        if event["signal_type"] == "positive_zero_cross_entry":
            open_entry = effective
        elif event["signal_type"] == "negative_zero_cross_exit" and open_entry is not None:
            if open_entry in positions and effective in positions:
                durations.append(int(positions[effective] - positions[open_entry]))
            open_entry = None
    return {
        "completed_round_trip_event_count": len(durations),
        "average_holding_duration": float(np.mean(durations)) if durations else float("nan"),
        "median_holding_duration": float(np.median(durations)) if durations else float("nan"),
        "holding_durations": durations,
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


def sparse_label(event_stats: dict[str, Any], role: str, default_label: str) -> tuple[str, str, bool]:
    if role != "source_primary":
        return "not_applicable_control_or_timing", default_label, True
    sparse = int(event_stats["completed_round_trip_event_count"]) < SPARSE_ROUND_TRIP_THRESHOLD
    if sparse:
        return "sparse_context_only_low_completed_round_trip_count", "public_source_coppock_curve_sparse_context_only", False
    return "sample_adequacy_not_flagged_sparse", default_label, True


def result_for_row(
    row: dict[str, str],
    row_metrics: dict[str, Any],
    daily: pd.Series,
    controls: dict[str, dict[str, Any]],
    control_returns: dict[str, pd.Series],
    preflight: dict[str, Any],
) -> dict[str, Any]:
    bil_total = controls["coppock_bil_cash_control_v1"]["total_return"]
    spy_mdd = controls["coppock_spy_buy_hold_control_v1"]["max_drawdown"]
    spy_proxy = controls["coppock_spy_buy_hold_control_v1"]["return_drawdown_proxy"]
    same_window_vs_bil = row_metrics["total_return"] - bil_total
    excess_after_cost = same_window_vs_bil - STANDARD_COST_ASSUMPTION
    drawdown_reduction = (
        (abs(spy_mdd) - abs(row_metrics["max_drawdown"])) / abs(spy_mdd)
        if finite(spy_mdd) and spy_mdd < 0
        else float("nan")
    )
    corr_spy = safe_corr(daily, control_returns["coppock_spy_buy_hold_control_v1"])
    corr_spy200d = safe_corr(daily, control_returns["coppock_spy200d_frozen_control_v1"])
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
    sparse_signal_label, research_label, sparse_pass = sparse_label(
        preflight["event_stats"],
        row["variant_role"],
        row["research_label"],
    )
    primary_total_return_beats_bil = is_primary and same_window_vs_bil > 0.0
    primary_excess_after_cost_beats_bil = is_primary and excess_after_cost > 0.0
    primary_drawdown_reduction_pass = is_primary and drawdown_reduction >= 0.20
    primary_proxy_pass = is_primary and row_metrics["return_drawdown_proxy"] > spy_proxy
    primary_exposure_pass = is_primary and 0.0500 <= row_metrics["average_spy_exposure_share"] <= 0.9500
    primary_duplicate_pass = is_primary and (not finite(duplicate_reference) or duplicate_reference < 0.9500)
    timing_context = is_timing
    numeric_pass = exposure_pass
    if is_primary:
        numeric_pass = all(
            (
                primary_total_return_beats_bil,
                primary_excess_after_cost_beats_bil,
                primary_drawdown_reduction_pass,
                primary_proxy_pass,
                primary_exposure_pass,
                primary_duplicate_pass,
                sparse_pass,
                exposure_pass,
            )
        )

    return {
        "lane_id": LANE_ID,
        "family_id": FAMILY_ID,
        "source_id": SOURCE_ID,
        "variant_id": row["variant_id"],
        "variant_role": row["variant_role"],
        "research_label": research_label,
        "symbols_used": row["symbols"],
        "monthly_observation_count": preflight["monthly_observation_count"],
        "formula_status": "coppock_roc14_plus_roc11_wma10_completed_monthly_adjusted_close"
        if row["variant_role"] in {"source_primary", "timing_sanity"}
        else "not_applicable_control",
        "roc_periods": "14|11" if row["variant_role"] in {"source_primary", "timing_sanity"} else "not_applicable_control",
        "wma_smoothing_period": WMA_SMOOTHING_PERIOD
        if row["variant_role"] in {"source_primary", "timing_sanity"}
        else "not_applicable_control",
        "signal_threshold": SIGNAL_THRESHOLD
        if row["variant_role"] in {"source_primary", "timing_sanity"}
        else "not_applicable_control",
        "signal_timing_convention": row["signal_timing"],
        "weight_shift_convention": "monthly signal target is set on eligible trading date and returns_from_weights applies one-bar close-to-close shift",
        "positive_zero_cross_entry_count": preflight["positive_zero_cross_entry_count"]
        if row["variant_role"] in {"source_primary", "timing_sanity"}
        else 0,
        "negative_zero_cross_exit_count": preflight["negative_zero_cross_exit_count"]
        if row["variant_role"] in {"source_primary", "timing_sanity"}
        else 0,
        "completed_round_trip_event_count": preflight["event_stats"]["completed_round_trip_event_count"]
        if row["variant_role"] in {"source_primary", "timing_sanity"}
        else 0,
        "average_holding_duration": preflight["event_stats"]["average_holding_duration"]
        if row["variant_role"] in {"source_primary", "timing_sanity"}
        else float("nan"),
        "median_holding_duration": preflight["event_stats"]["median_holding_duration"]
        if row["variant_role"] in {"source_primary", "timing_sanity"}
        else float("nan"),
        **row_metrics,
        "same_window_return_versus_bil": same_window_vs_bil,
        "return_after_standard_cost_assumption": row_metrics["total_return"] - STANDARD_COST_ASSUMPTION,
        "excess_return_versus_bil_after_cost": excess_after_cost,
        "drawdown_reduction_versus_spy_buy_hold": drawdown_reduction,
        "correlation_versus_spy_buy_hold": corr_spy,
        "correlation_versus_spy200d_control": corr_spy200d,
        "duplicate_reference_correlation": duplicate_reference,
        "sparse_signal_label": sparse_signal_label,
        "exposure_invariant_pass": exposure_pass,
        "primary_total_return_beats_bil": primary_total_return_beats_bil,
        "primary_excess_after_cost_beats_bil": primary_excess_after_cost_beats_bil,
        "primary_drawdown_reduction_pass": primary_drawdown_reduction_pass,
        "primary_return_drawdown_proxy_pass": primary_proxy_pass,
        "primary_spy_exposure_bounds_pass": primary_exposure_pass,
        "primary_duplicate_correlation_pass": primary_duplicate_pass,
        "primary_sparse_signal_adequacy_pass": is_primary and sparse_pass,
        "timing_sanity_context_only": timing_context,
        "numeric_criteria_pass": numeric_pass,
        "promotion_eligibility": False,
        "paper_forward_eligibility": False,
        "candidate_exhaustive_eligibility": False,
        "methodology_notes": "local-cache completed-month Coppock zero-cross shifted-weight bounded bt lane; diagnostic non-promotable evidence",
    }


def evaluate_lane(
    root: Path,
) -> tuple[list[dict[str, Any]], dict[str, pd.DataFrame], dict[str, pd.Series], pd.DataFrame, list[dict[str, Any]], dict[str, Any]]:
    rows = design_rows(root)
    design = design_manifest(root)
    full_prices = load_local_price_frame(root).sort_index()
    if not full_prices.empty:
        full_prices = full_prices.loc[full_prices[["SPY", "BIL"]].notna().all(axis=1), ["SPY", "BIL"]].copy()
    monthly = monthly_coppock_frame(full_prices)
    run_start = first_valid_run_start(pd.DatetimeIndex(full_prices.index), monthly) if not full_prices.empty else None
    data_blocker = ""
    if full_prices.empty:
        data_blocker = "missing_spy_bil_local_adjusted_close_cache"
    elif monthly.empty:
        data_blocker = "monthly_conversion_failed_no_completed_monthly_closes"
    elif run_start is None:
        data_blocker = "coppock_warmup_invalid_no_first_valid_monthly_signal"

    prices = full_prices.loc[run_start:].copy() if not data_blocker and run_start is not None else pd.DataFrame()
    events = coppock_events(pd.DatetimeIndex(full_prices.index), monthly) if not data_blocker else []
    events = [event for event in events if pd.Timestamp(event["primary_effective_date"]) in prices.index] if not prices.empty else []
    valid_monthly = monthly.loc[monthly["coppock"].notna()] if not monthly.empty else pd.DataFrame()
    monthly_eval = valid_monthly.loc[valid_monthly.index >= pd.Timestamp(run_start)] if run_start is not None and not valid_monthly.empty else valid_monthly
    event_stats = holding_stats(events, pd.DatetimeIndex(prices.index)) if not prices.empty else {
        "completed_round_trip_event_count": 0,
        "average_holding_duration": float("nan"),
        "median_holding_duration": float("nan"),
        "holding_durations": [],
    }

    weights_by_variant: dict[str, pd.DataFrame] = {}
    returns_by_variant: dict[str, pd.Series] = {}
    metrics_by_variant: dict[str, dict[str, Any]] = {}
    if not data_blocker:
        for row in rows:
            variant_id = row["variant_id"]
            weights = build_weights(variant_id, prices, full_prices, events)
            daily = returns_from_weights(prices, weights).rename(variant_id)
            weights_by_variant[variant_id] = weights
            returns_by_variant[variant_id] = daily
            metrics_by_variant[variant_id] = metrics(daily, weights)

    preflight = {
        "source_design_run_ready": design.get("run_readiness_decision")
        == "public_source_coppock_curve_bounded_bt_design_run_ready",
        "source_design_next_action_correct": design.get("next_action") == "run_public_source_coppock_curve_bounded_bt_lane",
        "design_row_count": len(rows),
        "evaluated_variant_ids": [],
        "uses_local_cache_only": True,
        "provider_download_required": False,
        "intraday_data_required": False,
        "data_blocker": data_blocker,
        "effective_start_date": prices.index.min().date().isoformat() if not prices.empty else "",
        "effective_end_date": prices.index.max().date().isoformat() if not prices.empty else "",
        "raw_common_cache_start_date": full_prices.index.min().date().isoformat() if not full_prices.empty else "",
        "raw_common_cache_end_date": full_prices.index.max().date().isoformat() if not full_prices.empty else "",
        "first_valid_coppock_close_date": monthly.loc[monthly["coppock"].notna()].index.min().date().isoformat()
        if not monthly.empty and monthly["coppock"].notna().any()
        else "",
        "first_valid_effective_trading_date": pd.Timestamp(run_start).date().isoformat() if run_start is not None else "",
        "monthly_observation_count": int(len(monthly_eval)),
        "effective_calendar_years": float((prices.index.max() - prices.index.min()).days / 365.25)
        if not prices.empty
        else 0.0,
        "effective_trading_days": int(len(prices)),
        "completed_monthly_close_count": int(len(monthly)),
        "valid_coppock_monthly_count": int(monthly["coppock"].notna().sum()) if not monthly.empty else 0,
        "positive_zero_cross_entry_count": sum(1 for event in events if event["signal_type"] == "positive_zero_cross_entry"),
        "negative_zero_cross_exit_count": sum(1 for event in events if event["signal_type"] == "negative_zero_cross_exit"),
        "event_stats": event_stats,
        "similarity_contexts": list(SIMILARITY_CONTEXTS),
        "sell_exit_caveat": "Coppock original use was mainly buy-signal focused; positive-to-negative zero-cross exit is carried forward as source-supported/common analyst use.",
    }

    result_rows: list[dict[str, Any]] = []
    if not data_blocker:
        for row in rows:
            result_rows.append(
                result_for_row(
                    row,
                    metrics_by_variant[row["variant_id"]],
                    returns_by_variant[row["variant_id"]],
                    metrics_by_variant,
                    returns_by_variant,
                    preflight,
                )
            )
    preflight["evaluated_variant_ids"] = [row["variant_id"] for row in result_rows]
    return result_rows, weights_by_variant, returns_by_variant, monthly, events, preflight


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
    max_exposure = max([float(row["max_daily_exposure"]) for row in rows], default=0.0)
    max_weight_sum = max([float(row["max_daily_weight_sum"]) for row in rows], default=0.0)
    primary = next((row for row in rows if row["variant_role"] == "source_primary"), {})
    timing = next((row for row in rows if row["variant_role"] == "timing_sanity"), {})
    variant_ids = {row["variant_id"] for row in rows}
    interpretable = (
        preflight["source_design_run_ready"]
        and not preflight["data_blocker"]
        and len(rows) == len(EXPECTED_VARIANTS)
        and variant_ids == set(EXPECTED_VARIANTS)
        and not invariants_failed
    )
    next_action = NEXT_ACTION_AUDIT if interpretable else NEXT_ACTION_FIX
    counts = role_counts(rows)
    return {
        "created_utc": created,
        "evidence_path": str(output.resolve()),
        "public_source_coppock_curve_bounded_bt_lane_run": True,
        "source_id": SOURCE_ID,
        "family_id": FAMILY_ID,
        "lane_id": LANE_ID,
        "source_design_run_ready": preflight["source_design_run_ready"],
        "source_design_next_action_correct": preflight["source_design_next_action_correct"],
        "formula_implemented": True,
        "formula_status": "coppock_roc14_plus_roc11_wma10_completed_monthly_adjusted_close",
        "roc_periods": list(ROC_PERIODS),
        "wma_smoothing_period": WMA_SMOOTHING_PERIOD,
        "signal_threshold": SIGNAL_THRESHOLD,
        "source_backed_parameters": True,
        "parameters_tuned": False,
        "variant_count_planned": len(EXPECTED_VARIANTS),
        "variant_count_evaluated": len(rows),
        "approved_variant_ids": list(EXPECTED_VARIANTS),
        "evaluated_variant_ids": [row["variant_id"] for row in rows],
        "primary_source_row_count": counts["primary_source"],
        "timing_sanity_row_count": counts["timing_sanity"],
        "control_row_count": counts["control"],
        "data_blocked_row_count": len(EXPECTED_VARIANTS) if preflight["data_blocker"] else 0,
        "data_blocker": preflight["data_blocker"] or "none",
        "raw_common_cache_start_date": preflight["raw_common_cache_start_date"],
        "raw_common_cache_end_date": preflight["raw_common_cache_end_date"],
        "first_valid_coppock_close_date": preflight["first_valid_coppock_close_date"],
        "first_valid_effective_trading_date": preflight["first_valid_effective_trading_date"],
        "effective_start_date": preflight["effective_start_date"],
        "effective_end_date": preflight["effective_end_date"],
        "effective_calendar_years": preflight["effective_calendar_years"],
        "effective_trading_days": preflight["effective_trading_days"],
        "completed_monthly_close_count": preflight["completed_monthly_close_count"],
        "valid_coppock_monthly_count": preflight["valid_coppock_monthly_count"],
        "monthly_observation_count": preflight["monthly_observation_count"],
        "positive_zero_cross_entry_count": preflight["positive_zero_cross_entry_count"],
        "negative_zero_cross_exit_count": preflight["negative_zero_cross_exit_count"],
        "completed_round_trip_event_count": preflight["event_stats"]["completed_round_trip_event_count"],
        "average_holding_duration": preflight["event_stats"]["average_holding_duration"],
        "median_holding_duration": preflight["event_stats"]["median_holding_duration"],
        "sparse_round_trip_threshold": SPARSE_ROUND_TRIP_THRESHOLD,
        "sparse_signal_context_only": preflight["event_stats"]["completed_round_trip_event_count"]
        < SPARSE_ROUND_TRIP_THRESHOLD,
        "primary_row_numeric_criteria_pass": primary.get("numeric_criteria_pass") is True,
        "primary_sparse_signal_label": primary.get("sparse_signal_label", ""),
        "timing_sanity_context_only": timing.get("timing_sanity_context_only") is True,
        "control_row_count_evaluated": counts["control"],
        "invariant_failure_count": len(invariants_failed),
        "invariant_failure_variant_ids": invariants_failed,
        "max_daily_exposure": max_exposure,
        "max_daily_weight_sum": max_weight_sum,
        "exposure_invariant_passed": not invariants_failed and max_exposure <= 1.000001 and max_weight_sum <= 1.000001,
        "monthly_conversion_documented": True,
        "roc_warmup_documented": True,
        "wma_warmup_documented": True,
        "signal_timing_no_lookahead": True,
        "completed_month_close_only": True,
        "one_additional_completed_month_timing_sanity_only": True,
        "sell_exit_caveat_preserved": True,
        "similarity_contexts_preserved": list(SIMILARITY_CONTEXTS),
        "similarity_context_count": len(SIMILARITY_CONTEXTS),
        "specific_duplicate_or_do_not_retest_match_discovered": False,
        "daily_coppock_variants_added": False,
        "weekly_coppock_variants_added": False,
        "alternate_roc_periods_added": False,
        "alternate_smoothing_periods_added": False,
        "signal_lines_added": False,
        "moving_average_filters_added": False,
        "volatility_filters_added": False,
        "stop_loss_or_profit_target_added": False,
        "holding_period_exit_added": False,
        "divergence_rules_added": False,
        "additional_exits_added": False,
        "parameter_sweep_created": False,
        "optimization_run": False,
        "uses_local_cache_only": True,
        "provider_download": False,
        "intraday_data_used": False,
        "new_instruments_added": False,
        "bounded_bt_design_changed": False,
        "bounded_run_implementation_created": True,
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
        "current_backtester_replaced": False,
        "bt_adapter_helpers_used": True,
        "larry_connors_continued": False,
        "percent_b_continued": False,
        "turn_of_month_continued": False,
        "faber_taa_retested": False,
        "outputs_diagnostic_only": True,
        "outputs_non_promotable": True,
        "candidate_exhaustive_ready": False,
        "paper_demo_eligible": False,
        "results_interpretable": interpretable,
        "usable_diagnostic_evidence": interpretable,
        "next_action": next_action,
    }


def formula_report_md(monthly: pd.DataFrame, preflight: dict[str, Any]) -> str:
    return f"""# Monthly Coppock Formula / Calculation Report

Formula status: `implemented`

Formula:

- Convert SPY local daily adjusted close into completed monthly closes.
- Compute ROC(14) on completed monthly closes.
- Compute ROC(11) on completed monthly closes.
- Sum ROC(14) and ROC(11).
- Compute a 10-period weighted moving average of that sum using linear weights 1 through 10.
- Zero-cross threshold is `0`.

Month-end close selection: last local-cache trading date for each calendar month.

Completed monthly close count: `{preflight['completed_monthly_close_count']}`

Valid Coppock monthly count after ROC/WMA warmup: `{preflight['valid_coppock_monthly_count']}`

First valid Coppock close date: `{preflight['first_valid_coppock_close_date'] or 'none'}`

First effective trading date after warmup: `{preflight['first_valid_effective_trading_date'] or 'none'}`

Effective run window: `{preflight['effective_start_date'] or 'none'}` to `{preflight['effective_end_date'] or 'none'}`

Monthly observations in effective window: `{preflight['monthly_observation_count']}`

No source scraping, provider download, intraday data, alternate ROC period, alternate smoothing period, or parameter tuning was used.
"""


def timing_report_md(preflight: dict[str, Any]) -> str:
    return f"""# Monthly Signal Timing / No-Lookahead Report

Primary timing:

- Signals are computed only after the completed month-end close.
- A target change becomes eligible on the next available trading date after that completed monthly close.
- Project returns use `returns_from_weights`, which applies target weights with a one-bar close-to-close shift.
- No same-day month-end close is used to create and profit from a signal.

Timing-sanity row:

- Uses the same source signal and exit logic.
- Target application is delayed by one additional completed month.
- It is context only and not a tuned or optimized variant.

Positive zero-cross entry events: `{preflight['positive_zero_cross_entry_count']}`

Negative zero-cross exit events: `{preflight['negative_zero_cross_exit_count']}`

Completed round trips: `{preflight['event_stats']['completed_round_trip_event_count']}`
"""


def sparse_report_md(preflight: dict[str, Any]) -> str:
    stats = preflight["event_stats"]
    sparse = int(stats["completed_round_trip_event_count"]) < SPARSE_ROUND_TRIP_THRESHOLD
    durations = stats["holding_durations"]
    return f"""# Sparse-Signal Adequacy Report

Positive zero-cross entries: `{preflight['positive_zero_cross_entry_count']}`

Negative zero-cross exits: `{preflight['negative_zero_cross_exit_count']}`

Completed round-trip events: `{stats['completed_round_trip_event_count']}`

Average holding duration, trading days: `{stats['average_holding_duration']}`

Median holding duration, trading days: `{stats['median_holding_duration']}`

Holding durations, trading days: `{durations}`

Effective calendar years: `{preflight['effective_calendar_years']}`

Effective trading days: `{preflight['effective_trading_days']}`

Effective monthly observations: `{preflight['monthly_observation_count']}`

Sparse/context-only forced: `{sparse}`

Sparse threshold: fewer than `{SPARSE_ROUND_TRIP_THRESHOLD}` completed round trips.
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


def invariant_report_md(manifest: dict[str, Any]) -> str:
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


def similarity_report_md(manifest: dict[str, Any]) -> str:
    lines = ["# Similarity Risk Report", ""]
    lines.append("Similarity contexts carried forward:")
    lines.append("")
    for context in manifest["similarity_contexts_preserved"]:
        lines.append(f"- `{context}`")
    lines.append("")
    lines.append(
        f"Specific duplicate/do-not-retest match discovered by this run: `{manifest['specific_duplicate_or_do_not_retest_match_discovered']}`"
    )
    lines.append("")
    lines.append("Similarity is preserved as context only. It is not treated as a blocker in this run.")
    return "\n".join(lines) + "\n"


def sell_exit_caveat_md() -> str:
    return """# Sell / Exit Caveat Carry-Forward Report

Coppock's original use was mainly buy-signal focused.

This bounded run uses the validated public-source intake convention:

- Enter or hold SPY after a completed monthly negative-to-positive Coppock zero-cross.
- Exit to BIL/cash after a completed monthly positive-to-negative Coppock zero-cross.

The positive-to-negative zero-cross exit is treated as source-supported/common analyst use, but this caveat remains visible in run evidence.

No alternate exit rules, stop-losses, profit targets, holding-period exits, volatility filters, moving-average filters, signal lines, or divergence rules were added.
"""


def role_label_summary_md(manifest: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    labels = {label: sum(1 for row in rows if row["research_label"] == label) for label in ALLOWED_LABELS}
    return f"""# Role / Label Summary

Primary source rows: `{manifest['primary_source_row_count']}`

Timing-sanity rows: `{manifest['timing_sanity_row_count']}`

Control rows: `{manifest['control_row_count']}`

Sparse/context-only forced: `{manifest['sparse_signal_context_only']}`

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
    primary = next((row for row in rows if row["variant_role"] == "source_primary"), {})
    timing = next((row for row in rows if row["variant_role"] == "timing_sanity"), {})
    return f"""# Public Source Coppock Curve Bounded bt Run

Lane ID: `{manifest['lane_id']}`

Rows planned/evaluated: `{manifest['variant_count_planned']} / {manifest['variant_count_evaluated']}`

Rows by role: primary `{manifest['primary_source_row_count']}`, timing-sanity `{manifest['timing_sanity_row_count']}`, controls `{manifest['control_row_count']}`

Data-blocked rows: `{manifest['data_blocked_row_count']}`

Primary row numeric criteria pass: `{manifest['primary_row_numeric_criteria_pass']}`

Timing-sanity context only: `{manifest['timing_sanity_context_only']}`

Control rows evaluated: `{manifest['control_row_count_evaluated']}`

Invariant failures: `{manifest['invariant_failure_count']}`

Formula/data limitations: completed monthly close conversion from local daily adjusted close; no intraday execution model.

Positive zero-cross entries: `{manifest['positive_zero_cross_entry_count']}`

Negative zero-cross exits: `{manifest['negative_zero_cross_exit_count']}`

Completed round-trip events: `{manifest['completed_round_trip_event_count']}`

Sparse/context-only forced: `{manifest['sparse_signal_context_only']}`

Effective history: `{manifest['effective_calendar_years']}` calendar years, `{manifest['effective_trading_days']}` trading days, `{manifest['monthly_observation_count']}` monthly observations.

Similarity-risk status: `{manifest['similarity_context_count']}` contexts preserved; duplicate/do-not-retest discovered `{manifest['specific_duplicate_or_do_not_retest_match_discovered']}`.

Sell/exit caveat preserved: `{manifest['sell_exit_caveat_preserved']}`

Results interpretable: `{manifest['results_interpretable']}`

Usable diagnostic evidence: `{manifest['usable_diagnostic_evidence']}`

Primary total return: `{primary.get('total_return', 'not_available')}`

Primary max drawdown: `{primary.get('max_drawdown', 'not_available')}`

Timing-sanity total return: `{timing.get('total_return', 'not_available')}`

No output is promotable, candidate_exhaustive-ready, or paper/demo eligible.

Exact next action: `{manifest['next_action']}`
"""


def do_not_promote_md() -> str:
    return """# Do Not Promote From Public Source Coppock Curve Run

This packet is diagnostic historical research evidence only.

It creates no promotion-review candidate, candidate_exhaustive candidate, paper/demo candidate, paper/demo activation, broker/live action, or real-money recommendation.
"""


def next_action_md(next_action: str) -> str:
    return f"""# Public Source Coppock Curve Bounded bt Run Next Action

Exact next action:

`{next_action}`

Do not execute the next action in this task.
"""


def consistency_check(manifest: dict[str, Any], rows: list[dict[str, Any]], output: Path) -> dict[str, Any]:
    required = {name: (output / name).exists() for name in REQUIRED_FILES}
    required["public_source_coppock_curve_bounded_bt_run_consistency_check.json"] = True
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
        "formula_implemented": manifest["formula_implemented"] is True,
        "source_parameters_frozen": manifest["roc_periods"] == [14, 11]
        and manifest["wma_smoothing_period"] == 10
        and manifest["signal_threshold"] == 0.0
        and manifest["source_backed_parameters"] is True
        and manifest["parameters_tuned"] is False,
        "monthly_timing_no_lookahead": manifest["monthly_conversion_documented"] is True
        and manifest["signal_timing_no_lookahead"] is True
        and manifest["completed_month_close_only"] is True,
        "one_timing_sanity_only": manifest["one_additional_completed_month_timing_sanity_only"] is True,
        "sparse_signal_reported": manifest["positive_zero_cross_entry_count"] >= 0
        and manifest["negative_zero_cross_exit_count"] >= 0
        and manifest["completed_round_trip_event_count"] >= 0,
        "similarity_context_preserved": manifest["similarity_contexts_preserved"] == list(SIMILARITY_CONTEXTS)
        and manifest["specific_duplicate_or_do_not_retest_match_discovered"] is False,
        "sell_exit_caveat_preserved": manifest["sell_exit_caveat_preserved"] is True,
        "no_coppock_expansion_or_extra_exits": manifest["daily_coppock_variants_added"] is False
        and manifest["weekly_coppock_variants_added"] is False
        and manifest["alternate_roc_periods_added"] is False
        and manifest["alternate_smoothing_periods_added"] is False
        and manifest["signal_lines_added"] is False
        and manifest["moving_average_filters_added"] is False
        and manifest["volatility_filters_added"] is False
        and manifest["stop_loss_or_profit_target_added"] is False
        and manifest["holding_period_exit_added"] is False
        and manifest["divergence_rules_added"] is False
        and manifest["additional_exits_added"] is False
        and manifest["parameter_sweep_created"] is False
        and manifest["optimization_run"] is False,
        "local_cache_only": manifest["uses_local_cache_only"] is True,
        "no_provider_intraday": manifest["provider_download"] is False and manifest["intraday_data_used"] is False,
        "no_design_change_or_new_instruments": manifest["bounded_bt_design_changed"] is False
        and manifest["new_instruments_added"] is False,
        "other_public_sources_not_continued": manifest["larry_connors_continued"] is False
        and manifest["percent_b_continued"] is False
        and manifest["turn_of_month_continued"] is False
        and manifest["faber_taa_retested"] is False,
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
        "no_scrape_or_extra_sources": manifest["public_source_scraped"] is False
        and manifest["public_strategy_list_ingested"] is False,
        "exposure_invariants_pass": manifest["exposure_invariant_passed"] is True
        and manifest["max_daily_exposure"] <= 1.000001
        and manifest["max_daily_weight_sum"] <= 1.000001,
        "all_rows_non_promotable": all(row["promotion_eligibility"] is False for row in rows),
        "all_rows_not_candidate_or_paper": all(row["candidate_exhaustive_eligibility"] is False for row in rows)
        and all(row["paper_forward_eligibility"] is False for row in rows),
        "outputs_diagnostic": manifest["outputs_diagnostic_only"] is True
        and manifest["outputs_non_promotable"] is True
        and manifest["candidate_exhaustive_ready"] is False
        and manifest["paper_demo_eligible"] is False,
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
    rows, weights_by_variant, returns_by_variant, monthly, events, preflight = evaluate_lane(root)
    manifest = manifest_payload(created, output, rows, preflight)

    write_json(output / "public_source_coppock_curve_bounded_bt_run_manifest.json", manifest)
    write_csv(output / "row_level_results.csv", rows, list(RESULT_FIELDS))
    write_csv(output / "numeric_criteria_results.csv", rows, list(CRITERIA_FIELDS))
    write_text(output / "monthly_coppock_formula_calculation_report.md", formula_report_md(monthly, preflight))
    write_text(output / "monthly_signal_timing_no_lookahead_report.md", timing_report_md(preflight))
    write_csv(output / "monthly_signal_event_table.csv", events, list(EVENT_FIELDS))
    write_csv(output / "daily_target_weights.csv", weight_rows(weights_by_variant), list(DAILY_WEIGHT_FIELDS))
    write_csv(output / "equity_curve_returns.csv", equity_rows(returns_by_variant), list(EQUITY_FIELDS))
    turnover = turnover_rows(rows, weights_by_variant)
    write_csv(output / "rebalance_turnover_report.csv", turnover, list(TURNOVER_FIELDS))
    write_text(output / "rebalance_turnover_report.md", turnover_report_md(rows))
    write_text(output / "sparse_signal_adequacy_report.md", sparse_report_md(preflight))
    write_text(output / "baseline_control_comparison_report.md", baseline_report_md(rows))
    write_text(output / "exposure_invariant_report.md", invariant_report_md(manifest))
    write_text(output / "similarity_risk_report.md", similarity_report_md(manifest))
    write_text(output / "sell_exit_caveat_carry_forward_report.md", sell_exit_caveat_md())
    write_text(output / "role_label_summary.md", role_label_summary_md(manifest, rows))
    write_text(output / "public_source_coppock_curve_bounded_bt_run_summary.md", summary_md(manifest, rows))
    write_text(output / "do_not_promote_from_public_source_coppock_curve_run.md", do_not_promote_md())
    write_text(output / "public_source_coppock_curve_bounded_bt_run_next_action.md", next_action_md(manifest["next_action"]))
    check = consistency_check(manifest, rows, output)
    write_json(output / "public_source_coppock_curve_bounded_bt_run_consistency_check.json", check)
    return {**manifest, "output_dir": str(output.resolve()), "consistency_passed": check["consistency_passed"]}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
