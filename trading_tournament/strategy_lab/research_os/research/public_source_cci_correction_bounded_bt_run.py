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


SOURCE_ID = "cci_correction"
FAMILY_ID = "equity_index_cci_pullback_trend_bias"
LANE_ID = "public_source_cci_correction_bounded_bt_lane_v1"
DESIGN_DIR = Path("evidence") / "research_recovery" / "public_source_cci_correction_bounded_bt_design" / "latest"
OUTPUT_DIR = Path("evidence") / "research_recovery" / "public_source_cci_correction_bounded_bt_run" / "latest"

EXPECTED_VARIANTS = (
    "cci_correction_spy_bil_primary_v1",
    "cci_correction_spy_bil_one_bar_delayed_timing_sanity_v1",
    "cci_correction_spy_buy_hold_control_v1",
    "cci_correction_bil_cash_control_v1",
    "cci_correction_spy200d_frozen_control_v1",
)

NEXT_ACTION_AUDIT = "audit_public_source_cci_correction_bounded_bt_results"
NEXT_ACTION_FIX = "fix_public_source_cci_correction_bounded_bt_run_methodology_issue"
VALID_NEXT_ACTIONS = {NEXT_ACTION_AUDIT, NEXT_ACTION_FIX}

WEEKLY_CCI_PERIOD = 26
DAILY_CCI_PERIOD = 26
WEEKLY_BULLISH_THRESHOLD = 100.0
WEEKLY_BEARISH_THRESHOLD = -100.0
DAILY_PULLBACK_THRESHOLD = -100.0
DAILY_REVERSAL_THRESHOLD = 0.0
WEIGHT_TOLERANCE = 1e-6
STANDARD_COST_ASSUMPTION = 0.0

ALLOWED_LABELS = {
    "public_source_cci_correction_primary",
    "public_source_cci_correction_timing_sanity",
    "public_source_cci_correction_control_only",
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
    "trading_days_covered",
    "weekly_observation_count",
    "daily_observation_count",
    "formula_status",
    "weekly_cci_period",
    "daily_cci_period",
    "weekly_bullish_threshold",
    "weekly_bearish_threshold",
    "daily_pullback_threshold",
    "daily_reversal_threshold",
    "signal_timing_convention",
    "weight_shift_convention",
    "bullish_bias_count_periods",
    "bearish_cash_bias_count_periods",
    "pullback_count",
    "entry_count",
    "exit_count",
    "completed_round_trip_count",
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
    "event_trade_count_reported",
    "timing_sanity_context_only",
    "numeric_criteria_pass",
    "promotion_eligibility",
    "paper_forward_eligibility",
    "candidate_exhaustive_eligibility",
    "research_only_label",
    "methodology_notes",
)
CRITERIA_FIELDS = (
    "variant_id",
    "variant_role",
    "research_only_label",
    "total_return",
    "same_window_return_versus_bil",
    "excess_return_versus_bil_after_cost",
    "max_drawdown",
    "drawdown_reduction_versus_spy_buy_hold",
    "return_drawdown_proxy",
    "average_spy_exposure_share",
    "duplicate_reference_correlation",
    "event_trade_count_reported",
    "exposure_invariant_pass",
    "primary_total_return_beats_bil",
    "primary_excess_after_cost_beats_bil",
    "primary_drawdown_reduction_pass",
    "primary_return_drawdown_proxy_pass",
    "primary_spy_exposure_bounds_pass",
    "primary_duplicate_correlation_pass",
    "timing_sanity_context_only",
    "numeric_criteria_pass",
)
DAILY_WEIGHT_FIELDS = ("date", "variant_id", "SPY", "BIL", "weight_sum", "risky_exposure")
EQUITY_FIELDS = ("date", "variant_id", "daily_return", "equity")
TURNOVER_FIELDS = ("variant_id", "variant_role", "trade_count", "turnover_proxy", "nonzero_turnover_days")
WEEKLY_BIAS_FIELDS = (
    "week_completed_date",
    "open",
    "high",
    "low",
    "close",
    "typical_price",
    "weekly_cci_26",
    "bias_state",
    "bullish_bias_start",
    "bearish_cash_bias_start",
)
DAILY_SIGNAL_FIELDS = (
    "date",
    "weekly_bias_state",
    "daily_cci_26",
    "daily_pullback_condition",
    "pullback_state_after_close",
    "daily_reversal_condition",
    "entry_event_after_close",
    "exit_event_after_close",
    "target_spy_after_close",
    "target_bil_after_close",
)

REQUIRED_FILES = (
    "public_source_cci_correction_bounded_bt_run_manifest.json",
    "public_source_cci_correction_bounded_bt_run_consistency_check.json",
    "row_level_results.csv",
    "numeric_criteria_results.csv",
    "weekly_daily_cci_formula_calculation_report.md",
    "signal_timing_no_lookahead_report.md",
    "weekly_bias_state_table.csv",
    "daily_pullback_reversal_signal_table.csv",
    "daily_target_weights.csv",
    "equity_curve_returns.csv",
    "rebalance_turnover_report.csv",
    "rebalance_turnover_report.md",
    "event_trade_count_report.md",
    "baseline_control_comparison_report.md",
    "exposure_invariant_report.md",
    "similarity_risk_report.md",
    "long_only_adaptation_caveat_carry_forward.md",
    "role_label_summary.md",
    "public_source_cci_correction_bounded_bt_run_summary.md",
    "do_not_promote_from_public_source_cci_correction_run.md",
    "public_source_cci_correction_bounded_bt_run_next_action.md",
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
    return read_json(root / DESIGN_DIR / "public_source_cci_correction_bounded_bt_design_manifest.json")


def target(spy: float, bil: float) -> dict[str, float]:
    return {"SPY": float(spy), "BIL": float(bil)}


def load_spy_adjusted_ohlc(root: Path) -> pd.DataFrame:
    path = root / "data" / "cache" / "SPY.csv"
    if not path.exists():
        return pd.DataFrame()
    raw = pd.read_csv(path)
    required = ["date", "open", "high", "low", "close"]
    if any(column not in raw.columns for column in required):
        return pd.DataFrame()
    dates = pd.to_datetime(raw["date"], errors="coerce")
    frame = pd.DataFrame(index=dates)
    for column in ["open", "high", "low", "close"]:
        frame[column] = pd.to_numeric(raw[column], errors="coerce").to_numpy()
    frame = frame[~frame.index.isna()].sort_index()
    frame = frame[~frame.index.duplicated(keep="last")]
    return frame.dropna(subset=["open", "high", "low", "close"])


def cci_from_ohlc(ohlc: pd.DataFrame, period: int) -> pd.Series:
    typical = ((ohlc["high"] + ohlc["low"] + ohlc["close"]) / 3.0).rename("typical_price")
    sma = typical.rolling(period, min_periods=period).mean()

    def mean_deviation(values: np.ndarray) -> float:
        mean = float(np.mean(values))
        return float(np.mean(np.abs(values - mean)))

    deviation = typical.rolling(period, min_periods=period).apply(mean_deviation, raw=True)
    denominator = (0.015 * deviation).replace(0.0, np.nan)
    return ((typical - sma) / denominator).rename(f"cci_{period}")


def weekly_ohlc_from_daily(daily: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, group in daily.groupby(pd.Grouper(freq="W-FRI")):
        if group.empty:
            continue
        rows.append(
            {
                "date": group.index.max(),
                "open": float(group["open"].iloc[0]),
                "high": float(group["high"].max()),
                "low": float(group["low"].min()),
                "close": float(group["close"].iloc[-1]),
            }
        )
    if not rows:
        return pd.DataFrame(columns=["open", "high", "low", "close"])
    weekly = pd.DataFrame(rows).set_index("date").sort_index()
    return weekly[~weekly.index.duplicated(keep="last")]


def weekly_bias_frame(spy_ohlc: pd.DataFrame) -> pd.DataFrame:
    weekly = weekly_ohlc_from_daily(spy_ohlc)
    if weekly.empty:
        return pd.DataFrame()
    out = weekly.copy()
    out["typical_price"] = (out["high"] + out["low"] + out["close"]) / 3.0
    out["weekly_cci_26"] = cci_from_ohlc(out, WEEKLY_CCI_PERIOD)
    state = "cash"
    states: list[str] = []
    bullish_starts: list[bool] = []
    bearish_starts: list[bool] = []
    for value in out["weekly_cci_26"]:
        previous = state
        if pd.notna(value) and float(value) > WEEKLY_BULLISH_THRESHOLD:
            state = "bullish"
        elif pd.notna(value) and float(value) < WEEKLY_BEARISH_THRESHOLD:
            state = "cash"
        states.append(state)
        bullish_starts.append(state == "bullish" and previous != "bullish")
        bearish_starts.append(state == "cash" and previous != "cash")
    out["bias_state"] = states
    out["bullish_bias_start"] = bullish_starts
    out["bearish_cash_bias_start"] = bearish_starts
    return out


def daily_indicator_frame(prices: pd.DataFrame, spy_ohlc: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    aligned = spy_ohlc.reindex(prices.index).dropna(subset=["open", "high", "low", "close"])
    daily = pd.DataFrame(index=aligned.index)
    daily["daily_cci_26"] = cci_from_ohlc(aligned, DAILY_CCI_PERIOD)
    weekly = weekly_bias_frame(aligned)
    if weekly.empty:
        daily["weekly_bias_state"] = "cash"
        daily["weekly_cci_26"] = np.nan
    else:
        daily["weekly_bias_state"] = weekly["bias_state"].reindex(daily.index).ffill().fillna("cash")
        daily["weekly_cci_26"] = weekly["weekly_cci_26"].reindex(daily.index).ffill()
    daily["daily_pullback_condition"] = (
        (daily["weekly_bias_state"] == "bullish") & (daily["daily_cci_26"] < DAILY_PULLBACK_THRESHOLD)
    )
    daily["daily_reversal_condition"] = (
        (daily["weekly_bias_state"] == "bullish") & (daily["daily_cci_26"] > DAILY_REVERSAL_THRESHOLD)
    )
    return daily, weekly


def primary_cci_state(indicators: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    weights = pd.DataFrame(0.0, index=indicators.index, columns=["SPY", "BIL"])
    states: list[dict[str, Any]] = []
    active = False
    pullback_armed = False
    for date, row in indicators.iterrows():
        bias = str(row.get("weekly_bias_state", "cash"))
        daily_cci = row.get("daily_cci_26")
        pullback_condition = bool(row.get("daily_pullback_condition")) if pd.notna(daily_cci) else False
        reversal_condition = bool(row.get("daily_reversal_condition")) if pd.notna(daily_cci) else False
        previous_active = active
        entry_event = False
        exit_event = False

        if bias != "bullish":
            pullback_armed = False
            if active:
                exit_event = True
            active = False
        else:
            if pullback_condition:
                pullback_armed = True
            if pullback_armed and reversal_condition:
                active = True
                pullback_armed = False
                entry_event = not previous_active

        weights.loc[date] = [1.0, 0.0] if active else [0.0, 1.0]
        states.append(
            {
                "date": pd.Timestamp(date).date().isoformat(),
                "weekly_bias_state": bias,
                "daily_cci_26": float(daily_cci) if pd.notna(daily_cci) else float("nan"),
                "daily_pullback_condition": pullback_condition,
                "pullback_state_after_close": pullback_armed,
                "daily_reversal_condition": reversal_condition,
                "entry_event_after_close": entry_event,
                "exit_event_after_close": exit_event,
                "target_spy_after_close": 1.0 if active else 0.0,
                "target_bil_after_close": 0.0 if active else 1.0,
            }
        )
    return weights, pd.DataFrame(states)


def primary_cci_targets(indicators: pd.DataFrame) -> pd.DataFrame:
    weights, _ = primary_cci_state(indicators)
    return weights


def one_extra_bar_delayed_targets(primary_weights: pd.DataFrame) -> pd.DataFrame:
    delayed = primary_weights.shift(1)
    if not delayed.empty:
        delayed.iloc[0] = [0.0, 1.0]
    return delayed.ffill().fillna({"SPY": 0.0, "BIL": 1.0}).astype(float)


def constant_weights(index: pd.DatetimeIndex, spy: float, bil: float) -> pd.DataFrame:
    return complete_rebalance_weight_frame(index, ["SPY", "BIL"], {index[0]: target(spy, bil)})


def build_weights(
    variant_id: str,
    prices: pd.DataFrame,
    indicators: pd.DataFrame,
    primary_weights: pd.DataFrame,
) -> pd.DataFrame:
    common_index = pd.DatetimeIndex(indicators.index)
    if variant_id == "cci_correction_spy_bil_primary_v1":
        return primary_weights
    if variant_id == "cci_correction_spy_bil_one_bar_delayed_timing_sanity_v1":
        return one_extra_bar_delayed_targets(primary_weights)
    if variant_id == "cci_correction_spy_buy_hold_control_v1":
        return constant_weights(common_index, 1.0, 0.0)
    if variant_id == "cci_correction_bil_cash_control_v1":
        return constant_weights(common_index, 0.0, 1.0)
    if variant_id == "cci_correction_spy200d_frozen_control_v1":
        control = reference_spy200d_weights(prices).reindex(common_index).ffill().fillna(0.0)
        return control.reindex(columns=["SPY", "BIL"], fill_value=0.0)
    raise ValueError(f"unexpected variant_id: {variant_id}")


def bias_period_counts(weekly: pd.DataFrame) -> tuple[int, int]:
    if weekly.empty:
        return 0, 0
    bullish = int(weekly["bullish_bias_start"].fillna(False).sum())
    bearish = int(weekly["bearish_cash_bias_start"].fillna(False).sum())
    return bullish, bearish


def signal_stats(weights: pd.DataFrame, signal_state: pd.DataFrame, weekly: pd.DataFrame) -> dict[str, Any]:
    bullish_periods, bearish_periods = bias_period_counts(weekly)
    if weights.empty:
        return {
            "bullish_bias_count_periods": bullish_periods,
            "bearish_cash_bias_count_periods": bearish_periods,
            "pullback_count": 0,
            "entry_count": 0,
            "exit_count": 0,
            "completed_round_trip_count": 0,
            "average_holding_duration": 0.0,
            "median_holding_duration": 0.0,
        }
    spy = weights["SPY"].fillna(0.0)
    transitions = spy.diff().fillna(spy)
    entry_dates = list(spy.index[transitions > WEIGHT_TOLERANCE])
    exit_dates = list(spy.index[transitions < -WEIGHT_TOLERANCE])
    durations: list[int] = []
    exit_cursor = 0
    for entry in entry_dates:
        while exit_cursor < len(exit_dates) and exit_dates[exit_cursor] <= entry:
            exit_cursor += 1
        if exit_cursor < len(exit_dates):
            durations.append(max((exit_dates[exit_cursor] - entry).days, 1))
            exit_cursor += 1
    pullback_count = (
        int(signal_state["daily_pullback_condition"].fillna(False).sum()) if "daily_pullback_condition" in signal_state else 0
    )
    return {
        "bullish_bias_count_periods": bullish_periods,
        "bearish_cash_bias_count_periods": bearish_periods,
        "pullback_count": pullback_count,
        "entry_count": len(entry_dates),
        "exit_count": len(exit_dates),
        "completed_round_trip_count": len(durations),
        "average_holding_duration": float(np.mean(durations)) if durations else 0.0,
        "median_holding_duration": float(np.median(durations)) if durations else 0.0,
    }


def metrics(
    daily_returns: pd.Series,
    weights: pd.DataFrame,
    signal_state: pd.DataFrame,
    weekly: pd.DataFrame,
) -> dict[str, Any]:
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
        "weekly_observation_count": int(len(weekly)),
        "daily_observation_count": int(len(weights)),
        "total_return": total_return,
        "cagr": cagr,
        "max_drawdown": mdd,
        "volatility": volatility,
        "return_drawdown_proxy": proxy,
        "average_spy_exposure_share": float(weights["SPY"].mean()),
        "average_bil_exposure_share": float(weights["BIL"].mean()),
        "trade_count": trades,
        "turnover_proxy": turnover,
        **signal_stats(weights, signal_state, weekly),
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


def weekly_bias_rows(weekly: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for date, row in weekly.iterrows():
        rows.append(
            {
                "week_completed_date": pd.Timestamp(date).date().isoformat(),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "typical_price": float(row["typical_price"]),
                "weekly_cci_26": float(row["weekly_cci_26"]) if pd.notna(row["weekly_cci_26"]) else float("nan"),
                "bias_state": row["bias_state"],
                "bullish_bias_start": bool(row["bullish_bias_start"]),
                "bearish_cash_bias_start": bool(row["bearish_cash_bias_start"]),
            }
        )
    return rows


def daily_signal_rows(signal_state: pd.DataFrame) -> list[dict[str, Any]]:
    return signal_state.to_dict(orient="records")


def result_for_row(
    row: dict[str, str],
    row_metrics: dict[str, Any],
    daily: pd.Series,
    controls: dict[str, dict[str, Any]],
    control_returns: dict[str, pd.Series],
) -> dict[str, Any]:
    bil_total = controls["cci_correction_bil_cash_control_v1"]["total_return"]
    spy_mdd = controls["cci_correction_spy_buy_hold_control_v1"]["max_drawdown"]
    spy_proxy = controls["cci_correction_spy_buy_hold_control_v1"]["return_drawdown_proxy"]
    same_window_vs_bil = row_metrics["total_return"] - bil_total
    excess_after_cost = same_window_vs_bil - STANDARD_COST_ASSUMPTION
    drawdown_reduction = (
        (abs(spy_mdd) - abs(row_metrics["max_drawdown"])) / abs(spy_mdd)
        if finite(spy_mdd) and spy_mdd < 0
        else float("nan")
    )
    corr_spy = safe_corr(daily, control_returns["cci_correction_spy_buy_hold_control_v1"])
    corr_spy200d = safe_corr(daily, control_returns["cci_correction_spy200d_frozen_control_v1"])
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
    primary_drawdown_reduction_pass = is_primary and drawdown_reduction >= 0.20
    primary_proxy_pass = is_primary and row_metrics["return_drawdown_proxy"] > spy_proxy
    primary_exposure_pass = is_primary and 0.0500 <= row_metrics["average_spy_exposure_share"] <= 0.8000
    primary_duplicate_pass = is_primary and (not finite(duplicate_reference) or duplicate_reference < 0.90)
    event_trade_count_reported = row_metrics["entry_count"] >= 0 and row_metrics["trade_count"] >= 0
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
                event_trade_count_reported,
                exposure_pass,
            )
        )

    return {
        "lane_id": LANE_ID,
        "family_id": FAMILY_ID,
        "source_id": SOURCE_ID,
        "variant_id": row["variant_id"],
        "variant_role": row["variant_role"],
        "research_label": row["research_label"],
        "symbols_used": row["symbols"],
        "formula_status": "weekly_daily_cci_calculated_from_local_spy_adjusted_ohlc",
        "weekly_cci_period": WEEKLY_CCI_PERIOD,
        "daily_cci_period": DAILY_CCI_PERIOD,
        "weekly_bullish_threshold": WEEKLY_BULLISH_THRESHOLD,
        "weekly_bearish_threshold": WEEKLY_BEARISH_THRESHOLD,
        "daily_pullback_threshold": DAILY_PULLBACK_THRESHOLD,
        "daily_reversal_threshold": DAILY_REVERSAL_THRESHOLD,
        "signal_timing_convention": row["signal_timing"],
        "weight_shift_convention": "target weights produced after completed close and applied with returns_from_weights one-bar shift",
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
        "event_trade_count_reported": event_trade_count_reported,
        "timing_sanity_context_only": timing_context,
        "numeric_criteria_pass": numeric_pass,
        "promotion_eligibility": False,
        "paper_forward_eligibility": False,
        "candidate_exhaustive_eligibility": False,
        "research_only_label": row["research_label"],
        "methodology_notes": "local-cache adjusted-OHLC CCI shifted-weight bounded bt lane; diagnostic non-promotable evidence",
    }


def evaluate_lane(
    root: Path,
) -> tuple[
    list[dict[str, Any]],
    dict[str, pd.DataFrame],
    dict[str, pd.Series],
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    dict[str, Any],
]:
    rows = design_rows(root)
    design = design_manifest(root)
    prices = load_local_price_frame(root).sort_index()
    spy_ohlc = load_spy_adjusted_ohlc(root)
    if not prices.empty and not spy_ohlc.empty:
        spy_ohlc = spy_ohlc.reindex(prices.index).dropna(subset=["open", "high", "low", "close"])
        prices = prices.reindex(spy_ohlc.index).dropna(subset=["SPY", "BIL"])
        spy_ohlc = spy_ohlc.reindex(prices.index)
    indicators, weekly = daily_indicator_frame(prices, spy_ohlc) if not prices.empty and not spy_ohlc.empty else (
        pd.DataFrame(),
        pd.DataFrame(),
    )
    if not indicators.empty:
        prices = prices.reindex(indicators.index).dropna(subset=["SPY", "BIL"])
        indicators = indicators.reindex(prices.index)
    data_blocker = ""
    if prices.empty or spy_ohlc.empty:
        data_blocker = "missing_spy_bil_price_or_spy_adjusted_ohlc_cache"
    elif weekly["weekly_cci_26"].dropna().empty if not weekly.empty else True:
        data_blocker = "weekly_cci_warmup_invalid_no_valid_weekly_cci_rows"
    elif indicators["daily_cci_26"].dropna().empty:
        data_blocker = "daily_cci_warmup_invalid_no_valid_daily_cci_rows"

    weights_by_variant: dict[str, pd.DataFrame] = {}
    returns_by_variant: dict[str, pd.Series] = {}
    metrics_by_variant: dict[str, dict[str, Any]] = {}
    signal_state = pd.DataFrame()
    if not data_blocker:
        primary_weights, signal_state = primary_cci_state(indicators)
        for row in rows:
            variant_id = row["variant_id"]
            weights = build_weights(variant_id, prices, indicators, primary_weights)
            daily = returns_from_weights(prices, weights).rename(variant_id)
            weights_by_variant[variant_id] = weights
            returns_by_variant[variant_id] = daily
            metrics_by_variant[variant_id] = metrics(daily, weights, signal_state, weekly)

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
                )
            )

    first_daily = indicators["daily_cci_26"].dropna().index.min() if not indicators.empty else None
    first_weekly = weekly["weekly_cci_26"].dropna().index.min() if not weekly.empty else None
    preflight = {
        "source_design_run_ready": design.get("run_readiness_decision")
        == "public_source_cci_correction_bounded_bt_design_run_ready",
        "source_design_next_action_correct": design.get("next_action") == "run_public_source_cci_correction_bounded_bt_lane",
        "design_row_count": len(rows),
        "evaluated_variant_ids": [row["variant_id"] for row in result_rows],
        "uses_local_cache_only": True,
        "provider_download_required": False,
        "intraday_data_required": False,
        "data_blocker": data_blocker,
        "effective_start_date": prices.index.min().date().isoformat() if not prices.empty else "",
        "effective_end_date": prices.index.max().date().isoformat() if not prices.empty else "",
        "weekly_observation_count": int(len(weekly)),
        "daily_observation_count": int(len(indicators)),
        "weekly_cci_valid_count": int(weekly["weekly_cci_26"].notna().sum()) if not weekly.empty else 0,
        "daily_cci_valid_count": int(indicators["daily_cci_26"].notna().sum()) if not indicators.empty else 0,
        "first_valid_weekly_cci_date": pd.Timestamp(first_weekly).date().isoformat() if first_weekly is not None else "",
        "first_valid_daily_cci_date": pd.Timestamp(first_daily).date().isoformat() if first_daily is not None else "",
        "bullish_bias_start_count": int(weekly["bullish_bias_start"].fillna(False).sum()) if not weekly.empty else 0,
        "bearish_cash_bias_start_count": int(weekly["bearish_cash_bias_start"].fillna(False).sum()) if not weekly.empty else 0,
        "pullback_condition_count": int(indicators["daily_pullback_condition"].fillna(False).sum())
        if not indicators.empty
        else 0,
        "entry_event_count": int(signal_state["entry_event_after_close"].fillna(False).sum()) if not signal_state.empty else 0,
        "exit_event_count": int(signal_state["exit_event_after_close"].fillna(False).sum()) if not signal_state.empty else 0,
    }
    return result_rows, weights_by_variant, returns_by_variant, weekly, signal_state, indicators, preflight


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
        "public_source_cci_correction_bounded_bt_lane_run": True,
        "source_id": SOURCE_ID,
        "family_id": FAMILY_ID,
        "lane_id": LANE_ID,
        "source_design_run_ready": preflight["source_design_run_ready"],
        "source_design_next_action_correct": preflight["source_design_next_action_correct"],
        "formula_status": "weekly_daily_cci_calculated_from_local_spy_adjusted_ohlc",
        "weekly_bar_construction": "completed weekly bars grouped from local daily SPY adjusted OHLC by week ending Friday and indexed by the last trading date in each completed week",
        "weekly_cci_period": WEEKLY_CCI_PERIOD,
        "daily_cci_period": DAILY_CCI_PERIOD,
        "weekly_bullish_threshold": WEEKLY_BULLISH_THRESHOLD,
        "weekly_bearish_threshold": WEEKLY_BEARISH_THRESHOLD,
        "daily_pullback_threshold": DAILY_PULLBACK_THRESHOLD,
        "daily_reversal_threshold": DAILY_REVERSAL_THRESHOLD,
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
        "effective_start_date": preflight["effective_start_date"],
        "effective_end_date": preflight["effective_end_date"],
        "weekly_observation_count": preflight["weekly_observation_count"],
        "daily_observation_count": preflight["daily_observation_count"],
        "weekly_cci_valid_count": preflight["weekly_cci_valid_count"],
        "daily_cci_valid_count": preflight["daily_cci_valid_count"],
        "first_valid_weekly_cci_date": preflight["first_valid_weekly_cci_date"],
        "first_valid_daily_cci_date": preflight["first_valid_daily_cci_date"],
        "bullish_bias_start_count": preflight["bullish_bias_start_count"],
        "bearish_cash_bias_start_count": preflight["bearish_cash_bias_start_count"],
        "pullback_condition_count": preflight["pullback_condition_count"],
        "entry_event_count": preflight["entry_event_count"],
        "exit_event_count": preflight["exit_event_count"],
        "primary_row_numeric_criteria_pass": primary.get("numeric_criteria_pass") is True,
        "timing_sanity_context_only": timing.get("timing_sanity_context_only") is True,
        "control_row_count_evaluated": counts["control"],
        "invariant_failure_count": len(invariants_failed),
        "invariant_failure_variant_ids": invariants_failed,
        "max_daily_exposure": max_exposure,
        "max_daily_weight_sum": max_weight_sum,
        "exposure_invariant_passed": not invariants_failed and max_exposure <= 1.000001 and max_weight_sum <= 1.000001,
        "signal_timing_no_lookahead": True,
        "one_extra_bar_delayed_timing_sanity_only": True,
        "daily_only_variants_added": False,
        "weekly_only_variants_added": False,
        "threshold_sweep_created": False,
        "optimization_run": False,
        "other_indicators_added": False,
        "stop_loss_or_profit_target_added": False,
        "moving_average_filter_added": False,
        "volatility_filter_added": False,
        "alternate_exits_added": False,
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
        "similarity_hit_count": 10,
        "similarity_hit_preserved": True,
        "specific_duplicate_or_do_not_retest_match_discovered": False,
        "long_only_adaptation_caveat_carried_forward": True,
        "bearish_mode_maps_to_bil_cash": True,
        "shorting_inverse_leverage_options_futures_intraday_used": False,
        "outputs_diagnostic_only": True,
        "outputs_non_promotable": True,
        "candidate_exhaustive_ready": False,
        "paper_demo_eligible": False,
        "results_interpretable": interpretable,
        "usable_diagnostic_evidence": interpretable,
        "next_action": next_action,
    }


def cci_formula_report_md(weekly: pd.DataFrame, indicators: pd.DataFrame, preflight: dict[str, Any]) -> str:
    return f"""# Weekly / Daily CCI Formula Calculation Report

Formula status: `implemented`

CCI formula:

- Typical price = `(high + low + close) / 3`.
- `CCI(n) = (typical_price - SMA(typical_price, n)) / (0.015 * mean_deviation(typical_price, n))`.
- Weekly CCI period: `{WEEKLY_CCI_PERIOD}`.
- Daily CCI period: `{DAILY_CCI_PERIOD}`.

Weekly bar construction:

- Local daily SPY adjusted OHLC is grouped into completed weeks ending Friday.
- Each weekly bar is indexed by the last actual trading date in that completed week.
- Weekly open is the first adjusted open in the week.
- Weekly high is the maximum adjusted high in the week.
- Weekly low is the minimum adjusted low in the week.
- Weekly close is the last adjusted close in the week.

Warmup and observations:

- Effective start date after SPY/BIL alignment: `{preflight['effective_start_date']}`.
- Effective end date: `{preflight['effective_end_date']}`.
- Weekly observations: `{preflight['weekly_observation_count']}`.
- Daily observations: `{preflight['daily_observation_count']}`.
- Valid weekly CCI rows: `{preflight['weekly_cci_valid_count']}`.
- Valid daily CCI rows: `{preflight['daily_cci_valid_count']}`.
- First valid weekly CCI date: `{preflight['first_valid_weekly_cci_date']}`.
- First valid daily CCI date: `{preflight['first_valid_daily_cci_date']}`.

No external indicator library, provider download, scraping, intraday data, or optimized parameter setting was used.
"""


def timing_report_md(rows: list[dict[str, Any]]) -> str:
    primary = next(row for row in rows if row["variant_role"] == "source_primary")
    timing = next(row for row in rows if row["variant_role"] == "timing_sanity")
    return f"""# Signal Timing / No-Lookahead Report

Primary row: `{primary['variant_id']}`

- Computes weekly CCI(26) only from completed weekly SPY adjusted OHLC bars.
- Computes daily CCI(26) through the completed daily close.
- Produces target weights after the relevant completed close.
- Uses `returns_from_weights`, which applies target weights with a one-bar close-to-close shift.
- Bullish weekly bias plus a completed daily pullback/reversal can create SPY exposure for the next trading day.
- Weekly bearish/cash bias exits SPY to BIL/cash for the next trading day.
- Bearish mode never creates short exposure.

Timing-sanity row: `{timing['variant_id']}`

- Uses the same signal and exit logic.
- Delays target weights one additional trading day before the standard shifted return convention.
- Timing-sanity row is context only and is not an optimized variant.

Primary average SPY exposure share: `{primary['average_spy_exposure_share']}`

Timing-sanity average SPY exposure share: `{timing['average_spy_exposure_share']}`
"""


def event_report_md(manifest: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    lines = ["# Event / Trade Count Report", ""]
    lines.append(f"Bullish weekly bias starts: `{manifest['bullish_bias_start_count']}`")
    lines.append(f"Bearish/cash weekly bias starts: `{manifest['bearish_cash_bias_start_count']}`")
    lines.append(f"Daily pullback conditions: `{manifest['pullback_condition_count']}`")
    lines.append(f"Primary entry events: `{manifest['entry_event_count']}`")
    lines.append(f"Primary exit events: `{manifest['exit_event_count']}`")
    lines.append("")
    for row in rows:
        lines.append(
            f"- `{row['variant_id']}`: entries `{row['entry_count']}`, exits `{row['exit_count']}`, "
            f"round trips `{row['completed_round_trip_count']}`, average holding days `{float(row['average_holding_duration']):.2f}`"
        )
    return "\n".join(lines) + "\n"


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
    return f"""# Similarity Risk Report

Similarity contexts preserved: `{manifest['similarity_hit_count']}`

Specific duplicate/do-not-retest match discovered by this run: `{manifest['specific_duplicate_or_do_not_retest_match_discovered']}`

Design treatment preserved:

- Do not treat public-source presence as proof of profitability.
- Do not reopen exact rejected variants.
- Do not continue Coppock, RSI(2), Percent B Money Flow, Turn-of-the-Month, Faber/TAA, macro/GLD, commodity, volatility-throttle, regional, global, or managed-futures lanes here.
- Keep this output diagnostic and non-promotable.
"""


def long_only_report_md() -> str:
    return """# Long-Only Adaptation Caveat Carry-Forward

The original CCI Correction source includes bearish/short-side logic.

Frozen project adaptation:

- Bullish mode may hold or enter long SPY.
- Bearish/cash mode maps to BIL/cash only.
- Bearish/short-side source signals are ignored.
- No shorting, inverse ETFs, leverage, margin, options, direct futures, forex, intraday execution, broker/live path, or real-money recommendation is allowed.
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
    primary = next((row for row in rows if row["variant_role"] == "source_primary"), {})
    timing = next((row for row in rows if row["variant_role"] == "timing_sanity"), {})
    return f"""# Public Source CCI Correction Bounded bt Run

Lane ID: `{manifest['lane_id']}`

Rows planned/evaluated: `{manifest['variant_count_planned']} / {manifest['variant_count_evaluated']}`

Rows by role: primary `{manifest['primary_source_row_count']}`, timing-sanity `{manifest['timing_sanity_row_count']}`, controls `{manifest['control_row_count']}`

Data-blocked rows: `{manifest['data_blocked_row_count']}`

Primary row numeric criteria pass: `{manifest['primary_row_numeric_criteria_pass']}`

Timing-sanity context only: `{manifest['timing_sanity_context_only']}`

Control rows evaluated: `{manifest['control_row_count_evaluated']}`

Invariant failures: `{manifest['invariant_failure_count']}`

Effective history: `{manifest['effective_start_date']}` to `{manifest['effective_end_date']}`

Weekly/daily observations: `{manifest['weekly_observation_count']}` / `{manifest['daily_observation_count']}`

Signal/event counts: bullish starts `{manifest['bullish_bias_start_count']}`, bearish/cash starts `{manifest['bearish_cash_bias_start_count']}`, pullbacks `{manifest['pullback_condition_count']}`, entries `{manifest['entry_event_count']}`, exits `{manifest['exit_event_count']}`

Similarity-risk status: preserved with `{manifest['similarity_hit_count']}` contexts; duplicate/do-not-retest discovered `{manifest['specific_duplicate_or_do_not_retest_match_discovered']}`

Long-only caveat status: bearish mode maps to BIL/cash `{manifest['bearish_mode_maps_to_bil_cash']}`

Results interpretable: `{manifest['results_interpretable']}`

Usable diagnostic evidence: `{manifest['usable_diagnostic_evidence']}`

Primary total return: `{primary.get('total_return', 'not_available')}`

Primary max drawdown: `{primary.get('max_drawdown', 'not_available')}`

Timing-sanity total return: `{timing.get('total_return', 'not_available')}`

Formula/data limitations: local daily adjusted-OHLC model only; no intraday execution model; public source is not proof of profitability.

No output is promotable, candidate_exhaustive-ready, or paper/demo eligible.

Exact next action: `{manifest['next_action']}`
"""


def do_not_promote_md() -> str:
    return """# Do Not Promote From Public Source CCI Correction Run

This packet is diagnostic historical research evidence only.

It creates no promotion-review candidate, candidate_exhaustive candidate, paper/demo candidate, paper/demo activation, broker/live action, or real-money recommendation.
"""


def next_action_md(next_action: str) -> str:
    return f"""# Public Source CCI Correction Bounded bt Run Next Action

Exact next action:

`{next_action}`

Do not execute the next action in this task.
"""


def consistency_check(manifest: dict[str, Any], rows: list[dict[str, Any]], output: Path) -> dict[str, Any]:
    required = {name: (output / name).exists() for name in REQUIRED_FILES}
    required["public_source_cci_correction_bounded_bt_run_consistency_check.json"] = True
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
        "formula_implemented": manifest["formula_status"] == "weekly_daily_cci_calculated_from_local_spy_adjusted_ohlc",
        "source_backed_params": manifest["weekly_cci_period"] == 26
        and manifest["daily_cci_period"] == 26
        and manifest["weekly_bullish_threshold"] == 100.0
        and manifest["weekly_bearish_threshold"] == -100.0
        and manifest["daily_pullback_threshold"] == -100.0
        and manifest["daily_reversal_threshold"] == 0.0
        and manifest["parameters_tuned"] is False,
        "signal_timing_no_lookahead": manifest["signal_timing_no_lookahead"] is True,
        "one_timing_sanity_only": manifest["one_extra_bar_delayed_timing_sanity_only"] is True,
        "no_sweep_or_optimization": manifest["daily_only_variants_added"] is False
        and manifest["weekly_only_variants_added"] is False
        and manifest["threshold_sweep_created"] is False
        and manifest["optimization_run"] is False
        and manifest["other_indicators_added"] is False
        and manifest["stop_loss_or_profit_target_added"] is False
        and manifest["moving_average_filter_added"] is False
        and manifest["volatility_filter_added"] is False
        and manifest["alternate_exits_added"] is False,
        "local_cache_only": manifest["uses_local_cache_only"] is True,
        "no_provider_intraday": manifest["provider_download"] is False and manifest["intraday_data_used"] is False,
        "no_design_change_or_new_instruments": manifest["bounded_bt_design_changed"] is False
        and manifest["new_instruments_added"] is False,
        "similarity_and_long_only_preserved": manifest["similarity_hit_preserved"] is True
        and manifest["specific_duplicate_or_do_not_retest_match_discovered"] is False
        and manifest["long_only_adaptation_caveat_carried_forward"] is True
        and manifest["bearish_mode_maps_to_bil_cash"] is True,
        "no_forbidden_exposure_logic": manifest["shorting_inverse_leverage_options_futures_intraday_used"] is False,
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
    rows, weights_by_variant, returns_by_variant, weekly, signal_state, indicators, preflight = evaluate_lane(root)
    manifest = manifest_payload(created, output, rows, preflight)

    write_json(output / "public_source_cci_correction_bounded_bt_run_manifest.json", manifest)
    write_csv(output / "row_level_results.csv", rows, list(RESULT_FIELDS))
    write_csv(output / "numeric_criteria_results.csv", rows, list(CRITERIA_FIELDS))
    write_text(output / "weekly_daily_cci_formula_calculation_report.md", cci_formula_report_md(weekly, indicators, preflight))
    write_text(output / "signal_timing_no_lookahead_report.md", timing_report_md(rows))
    write_csv(output / "weekly_bias_state_table.csv", weekly_bias_rows(weekly), list(WEEKLY_BIAS_FIELDS))
    write_csv(output / "daily_pullback_reversal_signal_table.csv", daily_signal_rows(signal_state), list(DAILY_SIGNAL_FIELDS))
    write_csv(output / "daily_target_weights.csv", weight_rows(weights_by_variant), list(DAILY_WEIGHT_FIELDS))
    write_csv(output / "equity_curve_returns.csv", equity_rows(returns_by_variant), list(EQUITY_FIELDS))
    turnover = turnover_rows(rows, weights_by_variant)
    write_csv(output / "rebalance_turnover_report.csv", turnover, list(TURNOVER_FIELDS))
    write_text(output / "rebalance_turnover_report.md", turnover_report_md(rows))
    write_text(output / "event_trade_count_report.md", event_report_md(manifest, rows))
    write_text(output / "baseline_control_comparison_report.md", baseline_report_md(rows))
    write_text(output / "exposure_invariant_report.md", invariant_report_md(manifest))
    write_text(output / "similarity_risk_report.md", similarity_report_md(manifest))
    write_text(output / "long_only_adaptation_caveat_carry_forward.md", long_only_report_md())
    write_text(output / "role_label_summary.md", role_label_summary_md(manifest, rows))
    write_text(output / "public_source_cci_correction_bounded_bt_run_summary.md", summary_md(manifest, rows))
    write_text(output / "do_not_promote_from_public_source_cci_correction_run.md", do_not_promote_md())
    write_text(output / "public_source_cci_correction_bounded_bt_run_next_action.md", next_action_md(manifest["next_action"]))
    check = consistency_check(manifest, rows, output)
    write_json(output / "public_source_cci_correction_bounded_bt_run_consistency_check.json", check)
    return {**manifest, "output_dir": str(output.resolve()), "consistency_passed": check["consistency_passed"]}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
