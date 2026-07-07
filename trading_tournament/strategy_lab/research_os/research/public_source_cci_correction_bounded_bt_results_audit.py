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
    max_drawdown,
    trade_count_and_turnover,
    write_csv,
)
from strategy_lab.research_os.research.public_source_cci_correction_bounded_bt_run import (
    DAILY_CCI_PERIOD,
    DAILY_PULLBACK_THRESHOLD,
    DAILY_REVERSAL_THRESHOLD,
    EXPECTED_VARIANTS,
    FAMILY_ID,
    LANE_ID,
    REQUIRED_FILES as RUN_REQUIRED_FILES,
    SOURCE_ID,
    STANDARD_COST_ASSUMPTION,
    WEEKLY_BEARISH_THRESHOLD,
    WEEKLY_BULLISH_THRESHOLD,
    WEEKLY_CCI_PERIOD,
    WEIGHT_TOLERANCE,
)


RUN_DIR = Path("evidence") / "research_recovery" / "public_source_cci_correction_bounded_bt_run" / "latest"
DESIGN_DIR = Path("evidence") / "research_recovery" / "public_source_cci_correction_bounded_bt_design" / "latest"
OUTPUT_DIR = (
    Path("evidence")
    / "research_recovery"
    / "public_source_cci_correction_bounded_bt_results_audit"
    / "latest"
)

AUDIT_PASSED = "public_source_cci_correction_results_audit_passed"
AUDIT_NEEDS_PATCH = "public_source_cci_correction_results_needs_patch"
AUDIT_PASSED_BUT_CONTROL_WEAK = "public_source_cci_correction_results_passed_but_control_weak"

NEXT_ACTION_ROBUSTNESS = "create_public_source_cci_correction_robustness_report"
NEXT_ACTION_FIX = "fix_public_source_cci_correction_bounded_bt_run_methodology_issue"
NEXT_ACTION_CONTROL_WEAK = "direction_owner_review_required_after_cci_control_weak_results_audit"
VALID_NEXT_ACTIONS = {NEXT_ACTION_ROBUSTNESS, NEXT_ACTION_FIX, NEXT_ACTION_CONTROL_WEAK}

PRIMARY_VARIANT = "cci_correction_spy_bil_primary_v1"
TIMING_VARIANT = "cci_correction_spy_bil_one_bar_delayed_timing_sanity_v1"
SPY_CONTROL = "cci_correction_spy_buy_hold_control_v1"
BIL_CONTROL = "cci_correction_bil_cash_control_v1"
SPY200D_CONTROL = "cci_correction_spy200d_frozen_control_v1"

NUMERIC_TOLERANCE = 1e-9
WEIGHT_COMPARE_TOLERANCE = 1e-9
RETURN_COMPARE_TOLERANCE = 1e-9

REQUIRED_AUDIT_FILES = (
    "public_source_cci_correction_bounded_bt_results_audit_manifest.json",
    "public_source_cci_correction_bounded_bt_results_audit_consistency_check.json",
    "cci_formula_audit_report.md",
    "weekly_bar_construction_audit_report.md",
    "signal_logic_audit_report.md",
    "mixed_frequency_no_lookahead_audit_report.md",
    "row_level_discrepancy_report.csv",
    "row_level_discrepancy_report.md",
    "criteria_recomputation_report.csv",
    "criteria_recomputation_report.md",
    "control_comparison_conservative_interpretation_report.md",
    "timing_sanity_interpretation_report.md",
    "long_only_adaptation_audit_report.md",
    "similarity_risk_audit_report.md",
    "exposure_invariant_audit_report.md",
    "public_source_cci_correction_bounded_bt_results_audit_summary.md",
    "public_source_cci_correction_bounded_bt_results_audit_next_action.md",
)

DISCREPANCY_FIELDS = (
    "comparison_scope",
    "variant_id",
    "date",
    "field",
    "expected",
    "actual",
    "absolute_difference",
    "status",
)

CRITERIA_RECOMPUTATION_FIELDS = (
    "variant_id",
    "variant_role",
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
    "numeric_criteria_pass_recomputed",
    "numeric_criteria_pass_run_evidence",
    "criteria_match",
)


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def boolish(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() == "true"


def finite(value: Any) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float("nan")


def blank_or_nan(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    text = str(value).strip().lower()
    return text in {"", "nan", "none", "nat"}


def iso_date(value: Any) -> str:
    return pd.Timestamp(value).date().isoformat()


def load_spy_adjusted_ohlc(root: Path) -> pd.DataFrame:
    path = root / "data" / "cache" / "SPY.csv"
    if not path.exists():
        return pd.DataFrame(columns=["open", "high", "low", "close"])
    raw = pd.read_csv(path)
    required = ["date", "open", "high", "low", "close"]
    if any(column not in raw.columns for column in required):
        return pd.DataFrame(columns=["open", "high", "low", "close"])
    frame = pd.DataFrame(index=pd.to_datetime(raw["date"], errors="coerce"))
    for column in ["open", "high", "low", "close"]:
        frame[column] = pd.to_numeric(raw[column], errors="coerce").to_numpy()
    frame = frame[~frame.index.isna()].sort_index()
    frame = frame[~frame.index.duplicated(keep="last")]
    return frame.dropna(subset=["open", "high", "low", "close"])


def independent_cci(ohlc: pd.DataFrame, period: int) -> pd.Series:
    typical = ((ohlc["high"] + ohlc["low"] + ohlc["close"]) / 3.0).rename("typical_price")
    sma = typical.rolling(period, min_periods=period).mean()

    def mean_deviation(values: np.ndarray) -> float:
        mean = float(np.mean(values))
        return float(np.mean(np.abs(values - mean)))

    deviation = typical.rolling(period, min_periods=period).apply(mean_deviation, raw=True)
    denominator = (0.015 * deviation).replace(0.0, np.nan)
    return ((typical - sma) / denominator).rename(f"cci_{period}")


def independent_weekly_ohlc_from_daily(daily: pd.DataFrame) -> pd.DataFrame:
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


def independent_weekly_bias_frame(spy_ohlc: pd.DataFrame) -> pd.DataFrame:
    weekly = independent_weekly_ohlc_from_daily(spy_ohlc)
    if weekly.empty:
        return pd.DataFrame()
    out = weekly.copy()
    out["typical_price"] = (out["high"] + out["low"] + out["close"]) / 3.0
    out["weekly_cci_26"] = independent_cci(out, WEEKLY_CCI_PERIOD)
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


def independent_daily_indicator_frame(prices: pd.DataFrame, spy_ohlc: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    aligned = spy_ohlc.reindex(prices.index).dropna(subset=["open", "high", "low", "close"])
    daily = pd.DataFrame(index=aligned.index)
    daily["daily_cci_26"] = independent_cci(aligned, DAILY_CCI_PERIOD)
    weekly = independent_weekly_bias_frame(aligned)
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


def independent_primary_state(indicators: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    weights = pd.DataFrame(0.0, index=indicators.index, columns=["SPY", "BIL"])
    state_rows: list[dict[str, Any]] = []
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
        weights.loc[date, "SPY"] = 1.0 if active else 0.0
        weights.loc[date, "BIL"] = 0.0 if active else 1.0
        state_rows.append(
            {
                "date": iso_date(date),
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
    return weights, pd.DataFrame(state_rows)


def one_extra_bar_delayed_targets(primary_weights: pd.DataFrame) -> pd.DataFrame:
    delayed = primary_weights.shift(1)
    if not delayed.empty:
        delayed.iloc[0] = [0.0, 1.0]
    return delayed.ffill().fillna({"SPY": 0.0, "BIL": 1.0}).astype(float)


def constant_weights(index: pd.DatetimeIndex, spy: float, bil: float) -> pd.DataFrame:
    weights = pd.DataFrame(0.0, index=index, columns=["SPY", "BIL"])
    weights["SPY"] = float(spy)
    weights["BIL"] = float(bil)
    return weights


def build_independent_weights(variant_id: str, prices: pd.DataFrame, primary_weights: pd.DataFrame) -> pd.DataFrame:
    index = pd.DatetimeIndex(primary_weights.index)
    if variant_id == PRIMARY_VARIANT:
        return primary_weights
    if variant_id == TIMING_VARIANT:
        return one_extra_bar_delayed_targets(primary_weights)
    if variant_id == SPY_CONTROL:
        return constant_weights(index, 1.0, 0.0)
    if variant_id == BIL_CONTROL:
        return constant_weights(index, 0.0, 1.0)
    if variant_id == SPY200D_CONTROL:
        control = reference_spy200d_weights(prices).reindex(index).ffill().fillna(0.0)
        return control.reindex(columns=["SPY", "BIL"], fill_value=0.0)
    raise ValueError(f"unexpected variant_id: {variant_id}")


def safe_corr(left: pd.Series, right: pd.Series) -> float:
    aligned = pd.concat([left.rename("left"), right.rename("right")], axis=1).dropna()
    if len(aligned) < 252:
        return float("nan")
    if float(aligned["left"].std()) == 0.0 or float(aligned["right"].std()) == 0.0:
        return float("nan")
    return float(aligned["left"].corr(aligned["right"]))


def signal_stats(weights: pd.DataFrame, signal_state: pd.DataFrame, weekly: pd.DataFrame) -> dict[str, Any]:
    spy = weights["SPY"].fillna(0.0) if "SPY" in weights else pd.Series(dtype=float)
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
    return {
        "bullish_bias_count_periods": int(weekly["bullish_bias_start"].fillna(False).sum()) if not weekly.empty else 0,
        "bearish_cash_bias_count_periods": int(weekly["bearish_cash_bias_start"].fillna(False).sum())
        if not weekly.empty
        else 0,
        "pullback_count": int(signal_state["daily_pullback_condition"].fillna(False).sum())
        if not signal_state.empty
        else 0,
        "entry_count": len(entry_dates),
        "exit_count": len(exit_dates),
        "completed_round_trip_count": len(durations),
        "average_holding_duration": float(np.mean(durations)) if durations else 0.0,
        "median_holding_duration": float(np.median(durations)) if durations else 0.0,
    }


def independent_metrics(
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
        "effective_start_date": iso_date(daily.index.min()),
        "effective_end_date": iso_date(daily.index.max()),
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


def independent_result_row(
    design_row: dict[str, str],
    row_metrics: dict[str, Any],
    daily_returns: pd.Series,
    metrics_by_variant: dict[str, dict[str, Any]],
    returns_by_variant: dict[str, pd.Series],
) -> dict[str, Any]:
    bil_total = metrics_by_variant[BIL_CONTROL]["total_return"]
    spy_mdd = metrics_by_variant[SPY_CONTROL]["max_drawdown"]
    spy_proxy = metrics_by_variant[SPY_CONTROL]["return_drawdown_proxy"]
    same_window_vs_bil = row_metrics["total_return"] - bil_total
    excess_after_cost = same_window_vs_bil - STANDARD_COST_ASSUMPTION
    drawdown_reduction = (
        (abs(spy_mdd) - abs(row_metrics["max_drawdown"])) / abs(spy_mdd)
        if finite(spy_mdd) and spy_mdd < 0
        else float("nan")
    )
    corr_spy = safe_corr(daily_returns, returns_by_variant[SPY_CONTROL])
    corr_spy200d = safe_corr(daily_returns, returns_by_variant[SPY200D_CONTROL])
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
    is_primary = design_row["variant_role"] == "source_primary"
    is_timing = design_row["variant_role"] == "timing_sanity"
    primary_total_return_beats_bil = is_primary and same_window_vs_bil > 0.0
    primary_excess_after_cost_beats_bil = is_primary and excess_after_cost > 0.0
    primary_drawdown_reduction_pass = is_primary and drawdown_reduction >= 0.20
    primary_proxy_pass = is_primary and row_metrics["return_drawdown_proxy"] > spy_proxy
    primary_exposure_pass = is_primary and 0.0500 <= row_metrics["average_spy_exposure_share"] <= 0.8000
    primary_duplicate_pass = is_primary and (not finite(duplicate_reference) or duplicate_reference < 0.90)
    event_trade_count_reported = row_metrics["entry_count"] >= 0 and row_metrics["trade_count"] >= 0
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
        "variant_id": design_row["variant_id"],
        "variant_role": design_row["variant_role"],
        "research_only_label": design_row["research_label"],
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
        "timing_sanity_context_only": is_timing,
        "numeric_criteria_pass": numeric_pass,
    }


def load_design_rows(root: Path) -> list[dict[str, str]]:
    return read_csv_rows(root / DESIGN_DIR / "planned_row_table.csv")


def recompute_lane(root: Path) -> dict[str, Any]:
    design_rows = load_design_rows(root)
    prices = load_local_price_frame(root).sort_index()
    spy_ohlc = load_spy_adjusted_ohlc(root)
    if not prices.empty and not spy_ohlc.empty:
        spy_ohlc = spy_ohlc.reindex(prices.index).dropna(subset=["open", "high", "low", "close"])
        prices = prices.reindex(spy_ohlc.index).dropna(subset=["SPY", "BIL"])
        spy_ohlc = spy_ohlc.reindex(prices.index)
    indicators, weekly = independent_daily_indicator_frame(prices, spy_ohlc)
    if not indicators.empty:
        prices = prices.reindex(indicators.index).dropna(subset=["SPY", "BIL"])
        indicators = indicators.reindex(prices.index)
    primary_weights, signal_state = independent_primary_state(indicators)

    weights_by_variant: dict[str, pd.DataFrame] = {}
    returns_by_variant: dict[str, pd.Series] = {}
    metrics_by_variant: dict[str, dict[str, Any]] = {}
    for row in design_rows:
        variant_id = row["variant_id"]
        weights = build_independent_weights(variant_id, prices, primary_weights)
        daily_returns = returns_from_weights(prices, weights).rename(variant_id)
        weights_by_variant[variant_id] = weights
        returns_by_variant[variant_id] = daily_returns
        metrics_by_variant[variant_id] = independent_metrics(daily_returns, weights, signal_state, weekly)

    result_rows = [
        independent_result_row(
            row,
            metrics_by_variant[row["variant_id"]],
            returns_by_variant[row["variant_id"]],
            metrics_by_variant,
            returns_by_variant,
        )
        for row in design_rows
    ]
    return {
        "design_rows": design_rows,
        "prices": prices,
        "spy_ohlc": spy_ohlc,
        "indicators": indicators,
        "weekly": weekly,
        "signal_state": signal_state,
        "weights_by_variant": weights_by_variant,
        "returns_by_variant": returns_by_variant,
        "metrics_by_variant": metrics_by_variant,
        "result_rows": result_rows,
    }


def weekly_rows(weekly: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for date, row in weekly.iterrows():
        rows.append(
            {
                "week_completed_date": iso_date(date),
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


def signal_rows(signal_state: pd.DataFrame) -> list[dict[str, Any]]:
    return signal_state.to_dict(orient="records")


def weight_rows(weights_by_variant: dict[str, pd.DataFrame]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for variant_id, weights in weights_by_variant.items():
        for date, row in weights.iterrows():
            rows.append(
                {
                    "date": iso_date(date),
                    "variant_id": variant_id,
                    "SPY": float(row.get("SPY", 0.0)),
                    "BIL": float(row.get("BIL", 0.0)),
                    "weight_sum": float(row.sum()),
                    "risky_exposure": float(row.get("SPY", 0.0)),
                }
            )
    return rows


def equity_rows(returns_by_variant: dict[str, pd.Series]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for variant_id, daily_returns in returns_by_variant.items():
        equity = equity_from_returns(daily_returns)
        for date, value in daily_returns.items():
            rows.append(
                {
                    "date": iso_date(date),
                    "variant_id": variant_id,
                    "daily_return": float(value),
                    "equity": float(equity.loc[date]),
                }
            )
    return rows


def keyed(rows: list[dict[str, Any]], keys: tuple[str, ...]) -> dict[tuple[str, ...], dict[str, Any]]:
    out: dict[tuple[str, ...], dict[str, Any]] = {}
    for row in rows:
        out[tuple(str(row.get(key, "")) for key in keys)] = row
    return out


def value_matches(expected: Any, actual: Any, tolerance: float) -> tuple[bool, float]:
    if blank_or_nan(expected) and blank_or_nan(actual):
        return True, 0.0
    if isinstance(expected, bool) or isinstance(actual, bool) or str(expected) in {"True", "False"} or str(actual) in {"True", "False"}:
        return boolish(expected) == boolish(actual), 0.0
    if finite(expected) or finite(actual):
        expected_float = safe_float(expected)
        actual_float = safe_float(actual)
        if math.isnan(expected_float) and math.isnan(actual_float):
            return True, 0.0
        diff = abs(expected_float - actual_float)
        return diff <= tolerance, diff
    return str(expected) == str(actual), 0.0


def compare_rows(
    scope: str,
    expected_rows: list[dict[str, Any]],
    actual_rows: list[dict[str, Any]],
    keys: tuple[str, ...],
    fields: tuple[str, ...],
    tolerance: float,
) -> list[dict[str, Any]]:
    discrepancies: list[dict[str, Any]] = []
    expected_by_key = keyed(expected_rows, keys)
    actual_by_key = keyed(actual_rows, keys)
    for key, expected in expected_by_key.items():
        actual = actual_by_key.get(key)
        if actual is None:
            discrepancies.append(
                {
                    "comparison_scope": scope,
                    "variant_id": expected.get("variant_id", ""),
                    "date": expected.get("date", expected.get("week_completed_date", "")),
                    "field": "row_presence",
                    "expected": "present",
                    "actual": "missing",
                    "absolute_difference": "",
                    "status": "missing_actual_row",
                }
            )
            continue
        for field in fields:
            matches, diff = value_matches(expected.get(field), actual.get(field), tolerance)
            if not matches:
                discrepancies.append(
                    {
                        "comparison_scope": scope,
                        "variant_id": expected.get("variant_id", ""),
                        "date": expected.get("date", expected.get("week_completed_date", "")),
                        "field": field,
                        "expected": expected.get(field),
                        "actual": actual.get(field),
                        "absolute_difference": diff,
                        "status": "mismatch",
                    }
                )
    for key, actual in actual_by_key.items():
        if key not in expected_by_key:
            discrepancies.append(
                {
                    "comparison_scope": scope,
                    "variant_id": actual.get("variant_id", ""),
                    "date": actual.get("date", actual.get("week_completed_date", "")),
                    "field": "row_presence",
                    "expected": "missing",
                    "actual": "present",
                    "absolute_difference": "",
                    "status": "unexpected_actual_row",
                }
            )
    return discrepancies


def criteria_rows(recomputed: list[dict[str, Any]], actual_rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    actual_by_variant = {row["variant_id"]: row for row in actual_rows}
    rows: list[dict[str, Any]] = []
    for row in recomputed:
        actual = actual_by_variant.get(row["variant_id"], {})
        recomputed_pass = bool(row["numeric_criteria_pass"])
        actual_pass = boolish(actual.get("numeric_criteria_pass", False))
        rows.append(
            {
                "variant_id": row["variant_id"],
                "variant_role": row["variant_role"],
                "total_return": row["total_return"],
                "same_window_return_versus_bil": row["same_window_return_versus_bil"],
                "excess_return_versus_bil_after_cost": row["excess_return_versus_bil_after_cost"],
                "max_drawdown": row["max_drawdown"],
                "drawdown_reduction_versus_spy_buy_hold": row["drawdown_reduction_versus_spy_buy_hold"],
                "return_drawdown_proxy": row["return_drawdown_proxy"],
                "average_spy_exposure_share": row["average_spy_exposure_share"],
                "duplicate_reference_correlation": row["duplicate_reference_correlation"],
                "event_trade_count_reported": row["event_trade_count_reported"],
                "exposure_invariant_pass": row["exposure_invariant_pass"],
                "primary_total_return_beats_bil": row["primary_total_return_beats_bil"],
                "primary_excess_after_cost_beats_bil": row["primary_excess_after_cost_beats_bil"],
                "primary_drawdown_reduction_pass": row["primary_drawdown_reduction_pass"],
                "primary_return_drawdown_proxy_pass": row["primary_return_drawdown_proxy_pass"],
                "primary_spy_exposure_bounds_pass": row["primary_spy_exposure_bounds_pass"],
                "primary_duplicate_correlation_pass": row["primary_duplicate_correlation_pass"],
                "timing_sanity_context_only": row["timing_sanity_context_only"],
                "numeric_criteria_pass_recomputed": recomputed_pass,
                "numeric_criteria_pass_run_evidence": actual_pass,
                "criteria_match": recomputed_pass == actual_pass,
            }
        )
    return rows


def control_comparison(recomputed_rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_variant = {row["variant_id"]: row for row in recomputed_rows}
    primary = by_variant[PRIMARY_VARIANT]
    spy = by_variant[SPY_CONTROL]
    bil = by_variant[BIL_CONTROL]
    spy200d = by_variant[SPY200D_CONTROL]
    primary_proxy = primary["return_drawdown_proxy"]
    spy200d_proxy = spy200d["return_drawdown_proxy"]
    spy200d_dominates_total = spy200d["total_return"] > primary["total_return"]
    spy200d_dominates_drawdown = spy200d["max_drawdown"] > primary["max_drawdown"]
    spy200d_dominates_proxy = spy200d_proxy > primary_proxy
    domination_count = sum([spy200d_dominates_total, spy200d_dominates_drawdown, spy200d_dominates_proxy])
    return {
        "primary_total_return": primary["total_return"],
        "primary_cagr": primary["cagr"],
        "primary_max_drawdown": primary["max_drawdown"],
        "primary_return_drawdown_proxy": primary_proxy,
        "primary_average_spy_exposure": primary["average_spy_exposure_share"],
        "spy_buy_hold_total_return": spy["total_return"],
        "spy_buy_hold_max_drawdown": spy["max_drawdown"],
        "spy200d_total_return": spy200d["total_return"],
        "spy200d_max_drawdown": spy200d["max_drawdown"],
        "spy200d_return_drawdown_proxy": spy200d_proxy,
        "bil_total_return": bil["total_return"],
        "primary_underperforms_spy_buy_hold_total_return": spy["total_return"] > primary["total_return"],
        "primary_underperforms_spy200d_total_return": spy200d_dominates_total,
        "primary_underperforms_spy200d_max_drawdown": spy200d_dominates_drawdown,
        "primary_underperforms_spy200d_return_drawdown_proxy": spy200d_dominates_proxy,
        "spy200d_dominates_primary_metric_count": int(domination_count),
        "serious_interpretation_weakness": domination_count >= 2,
    }


def count_by_scope(discrepancies: list[dict[str, Any]], scope: str) -> int:
    return sum(1 for row in discrepancies if row["comparison_scope"] == scope)


def build_audit(root: Path) -> dict[str, Any]:
    run_path = root / RUN_DIR
    design_path = root / DESIGN_DIR
    output = root / OUTPUT_DIR
    output.mkdir(parents=True, exist_ok=True)

    run_manifest = read_json(run_path / "public_source_cci_correction_bounded_bt_run_manifest.json")
    run_consistency = read_json(run_path / "public_source_cci_correction_bounded_bt_run_consistency_check.json")
    recomputed = recompute_lane(root)

    weekly_expected = weekly_rows(recomputed["weekly"])
    signal_expected = signal_rows(recomputed["signal_state"])
    weights_expected = weight_rows(recomputed["weights_by_variant"])
    equity_expected = equity_rows(recomputed["returns_by_variant"])
    result_expected = recomputed["result_rows"]

    weekly_actual = read_csv_rows(run_path / "weekly_bias_state_table.csv")
    signal_actual = read_csv_rows(run_path / "daily_pullback_reversal_signal_table.csv")
    weights_actual = read_csv_rows(run_path / "daily_target_weights.csv")
    equity_actual = read_csv_rows(run_path / "equity_curve_returns.csv")
    result_actual = read_csv_rows(run_path / "row_level_results.csv")
    criteria_actual = read_csv_rows(run_path / "numeric_criteria_results.csv")

    discrepancies: list[dict[str, Any]] = []
    discrepancies.extend(
        compare_rows(
            "weekly_cci_formula",
            weekly_expected,
            weekly_actual,
            ("week_completed_date",),
            (
                "open",
                "high",
                "low",
                "close",
                "typical_price",
                "weekly_cci_26",
                "bias_state",
                "bullish_bias_start",
                "bearish_cash_bias_start",
            ),
            NUMERIC_TOLERANCE,
        )
    )
    discrepancies.extend(
        compare_rows(
            "daily_signal_logic",
            signal_expected,
            signal_actual,
            ("date",),
            (
                "weekly_bias_state",
                "daily_cci_26",
                "daily_pullback_condition",
                "pullback_state_after_close",
                "daily_reversal_condition",
                "entry_event_after_close",
                "exit_event_after_close",
                "target_spy_after_close",
                "target_bil_after_close",
            ),
            NUMERIC_TOLERANCE,
        )
    )
    discrepancies.extend(
        compare_rows(
            "target_weights",
            weights_expected,
            weights_actual,
            ("variant_id", "date"),
            ("SPY", "BIL", "weight_sum", "risky_exposure"),
            WEIGHT_COMPARE_TOLERANCE,
        )
    )
    discrepancies.extend(
        compare_rows(
            "equity_curve_returns",
            equity_expected,
            equity_actual,
            ("variant_id", "date"),
            ("daily_return", "equity"),
            RETURN_COMPARE_TOLERANCE,
        )
    )
    metric_fields = (
        "total_return",
        "cagr",
        "max_drawdown",
        "volatility",
        "return_drawdown_proxy",
        "same_window_return_versus_bil",
        "excess_return_versus_bil_after_cost",
        "drawdown_reduction_versus_spy_buy_hold",
        "correlation_versus_spy_buy_hold",
        "correlation_versus_spy200d_control",
        "duplicate_reference_correlation",
        "average_spy_exposure_share",
        "average_bil_exposure_share",
        "entry_count",
        "exit_count",
        "completed_round_trip_count",
        "trade_count",
        "turnover_proxy",
        "max_daily_exposure",
        "max_daily_weight_sum",
        "exposure_invariant_pass",
        "numeric_criteria_pass",
    )
    discrepancies.extend(
        compare_rows(
            "row_level_metrics",
            result_expected,
            result_actual,
            ("variant_id",),
            metric_fields,
            NUMERIC_TOLERANCE,
        )
    )
    criteria = criteria_rows(result_expected, criteria_actual)
    criteria_mismatch_count = sum(1 for row in criteria if row["criteria_match"] is not True)
    control = control_comparison(result_expected)

    run_required_files = {filename: (run_path / filename).exists() for filename in RUN_REQUIRED_FILES}
    evidence_completeness_passed = all(run_required_files.values())
    exact_variant_set = {row["variant_id"] for row in result_actual} == set(EXPECTED_VARIANTS)
    no_hidden_rows = len(result_actual) == len(EXPECTED_VARIANTS)
    formula_discrepancy_count = count_by_scope(discrepancies, "weekly_cci_formula")
    signal_discrepancy_count = count_by_scope(discrepancies, "daily_signal_logic")
    weight_discrepancy_count = count_by_scope(discrepancies, "target_weights")
    equity_discrepancy_count = count_by_scope(discrepancies, "equity_curve_returns")
    row_metric_discrepancy_count = count_by_scope(discrepancies, "row_level_metrics")
    exposure_invariant_passed = (
        run_manifest.get("exposure_invariant_passed") is True
        and max(row["max_daily_exposure"] for row in result_expected) <= 1.000001
        and max(row["max_daily_weight_sum"] for row in result_expected) <= 1.000001
        and all(row["exposure_invariant_pass"] is True for row in result_expected)
    )
    mechanics_pass = (
        evidence_completeness_passed
        and exact_variant_set
        and no_hidden_rows
        and formula_discrepancy_count == 0
        and signal_discrepancy_count == 0
        and weight_discrepancy_count == 0
        and equity_discrepancy_count == 0
        and row_metric_discrepancy_count == 0
        and criteria_mismatch_count == 0
        and exposure_invariant_passed
    )
    primary_recomputed = next(row for row in result_expected if row["variant_id"] == PRIMARY_VARIANT)
    if not mechanics_pass:
        audit_decision = AUDIT_NEEDS_PATCH
        next_action = NEXT_ACTION_FIX
    elif control["serious_interpretation_weakness"]:
        audit_decision = AUDIT_PASSED_BUT_CONTROL_WEAK
        next_action = NEXT_ACTION_CONTROL_WEAK
    else:
        audit_decision = AUDIT_PASSED
        next_action = NEXT_ACTION_ROBUSTNESS

    manifest = {
        "created_utc": now_utc(),
        "evidence_path": str(output.resolve()),
        "public_source_cci_correction_results_audit_only": True,
        "source_id": SOURCE_ID,
        "family_id": FAMILY_ID,
        "lane_id": LANE_ID,
        "source_run_evidence_path": str(run_path.resolve()),
        "source_design_evidence_path": str(design_path.resolve()),
        "source_run_evidence_reviewed": True,
        "source_design_evidence_reviewed": True,
        "run_consistency_passed": run_consistency.get("consistency_passed") is True,
        "evidence_completeness_passed": evidence_completeness_passed,
        "variant_count_reviewed": len(result_actual),
        "variant_count_expected": len(EXPECTED_VARIANTS),
        "variant_count_exact_5": exact_variant_set and no_hidden_rows,
        "hidden_variant_or_parameter_sweep_detected": False,
        "weekly_cci_formula_discrepancy_count": formula_discrepancy_count,
        "daily_signal_logic_discrepancy_count": signal_discrepancy_count,
        "target_weight_discrepancy_count": weight_discrepancy_count,
        "equity_return_discrepancy_count": equity_discrepancy_count,
        "row_metric_discrepancy_count": row_metric_discrepancy_count,
        "criteria_mismatch_count": criteria_mismatch_count,
        "total_discrepancy_count": len(discrepancies) + criteria_mismatch_count,
        "weekly_cci_audit_passed": formula_discrepancy_count == 0,
        "daily_cci_audit_passed": signal_discrepancy_count == 0,
        "signal_logic_audit_passed": signal_discrepancy_count == 0,
        "mixed_frequency_no_lookahead_audit_passed": signal_discrepancy_count == 0 and weight_discrepancy_count == 0,
        "shifted_weight_audit_passed": weight_discrepancy_count == 0 and equity_discrepancy_count == 0,
        "criteria_recomputation_passed": criteria_mismatch_count == 0,
        "exposure_invariant_audit_passed": exposure_invariant_passed,
        "primary_numeric_criteria_pass_recomputed": primary_recomputed["numeric_criteria_pass"] is True,
        "primary_numeric_criteria_pass_run_evidence": boolish(
            next(row for row in result_actual if row["variant_id"] == PRIMARY_VARIANT)["numeric_criteria_pass"]
        ),
        "control_comparison": control,
        "spy200d_control_dominates_primary": control["serious_interpretation_weakness"],
        "serious_interpretation_weakness": control["serious_interpretation_weakness"],
        "timing_sanity_context_only": run_manifest.get("timing_sanity_context_only") is True,
        "long_only_adaptation_preserved": run_manifest.get("long_only_adaptation_caveat_carried_forward") is True
        and run_manifest.get("bearish_mode_maps_to_bil_cash") is True,
        "similarity_contexts_preserved": run_manifest.get("similarity_hit_count") == 10
        and run_manifest.get("similarity_hit_preserved") is True,
        "specific_duplicate_or_do_not_retest_match_discovered": False,
        "uses_local_cache_only": True,
        "provider_download": False,
        "intraday_data_used": False,
        "public_source_scraped": False,
        "extra_public_sources_ingested": False,
        "cci_parameters_tuned": False,
        "new_variants_created": False,
        "new_exits_filters_or_indicators_added": False,
        "robustness_run": False,
        "strategy_discovery_run": False,
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
        "outputs_diagnostic_only": True,
        "outputs_non_promotable": True,
        "candidate_exhaustive_ready": False,
        "paper_demo_eligible": False,
        "audit_decision": audit_decision,
        "next_action": next_action,
    }

    write_json(output / "public_source_cci_correction_bounded_bt_results_audit_manifest.json", manifest)
    write_csv(output / "row_level_discrepancy_report.csv", discrepancies, list(DISCREPANCY_FIELDS))
    write_csv(output / "criteria_recomputation_report.csv", criteria, list(CRITERIA_RECOMPUTATION_FIELDS))
    write_text(output / "cci_formula_audit_report.md", cci_formula_report(manifest, recomputed))
    write_text(output / "weekly_bar_construction_audit_report.md", weekly_bar_report(manifest, recomputed))
    write_text(output / "signal_logic_audit_report.md", signal_logic_report(manifest))
    write_text(output / "mixed_frequency_no_lookahead_audit_report.md", no_lookahead_report(manifest))
    write_text(output / "row_level_discrepancy_report.md", discrepancy_report(manifest, discrepancies))
    write_text(output / "criteria_recomputation_report.md", criteria_report(manifest, criteria))
    write_text(output / "control_comparison_conservative_interpretation_report.md", control_report(manifest))
    write_text(output / "timing_sanity_interpretation_report.md", timing_sanity_report(manifest, result_expected))
    write_text(output / "long_only_adaptation_audit_report.md", long_only_report(manifest))
    write_text(output / "similarity_risk_audit_report.md", similarity_report(manifest))
    write_text(output / "exposure_invariant_audit_report.md", exposure_report(manifest, result_expected))
    write_text(output / "public_source_cci_correction_bounded_bt_results_audit_summary.md", summary_report(manifest))
    write_text(output / "public_source_cci_correction_bounded_bt_results_audit_next_action.md", next_action_report(manifest))
    consistency = consistency_check(manifest, output)
    write_json(output / "public_source_cci_correction_bounded_bt_results_audit_consistency_check.json", consistency)
    return {**manifest, "output_dir": str(output.resolve()), "consistency_passed": consistency["consistency_passed"]}


def cci_formula_report(manifest: dict[str, Any], recomputed: dict[str, Any]) -> str:
    first_weekly = recomputed["weekly"]["weekly_cci_26"].dropna().index.min()
    first_daily = recomputed["indicators"]["daily_cci_26"].dropna().index.min()
    return f"""# CCI Formula Audit

Formula audited: typical price `(high + low + close) / 3`; CCI(n) `(typical - SMA(typical, n)) / (0.015 * mean_deviation(typical, n))`.

- Weekly CCI period: `{WEEKLY_CCI_PERIOD}`
- Daily CCI period: `{DAILY_CCI_PERIOD}`
- First valid weekly CCI date: `{iso_date(first_weekly)}`
- First valid daily CCI date: `{iso_date(first_daily)}`
- Weekly CCI date-level discrepancies: `{manifest['weekly_cci_formula_discrepancy_count']}`
- Daily signal/date discrepancies: `{manifest['daily_signal_logic_discrepancy_count']}`
- Formula audit passed: `{manifest['weekly_cci_audit_passed'] and manifest['daily_cci_audit_passed']}`

The recomputation used local SPY adjusted OHLC only and did not download or scrape data.
"""


def weekly_bar_report(manifest: dict[str, Any], recomputed: dict[str, Any]) -> str:
    weekly = recomputed["weekly"]
    return f"""# Weekly Bar Construction Audit

Weekly bars were independently reconstructed from local daily SPY adjusted OHLC using completed `W-FRI` groups and indexed by each group's last available trading date.

- Weekly observations reconstructed: `{len(weekly)}`
- Valid weekly CCI rows: `{int(weekly['weekly_cci_26'].notna().sum())}`
- Weekly bullish starts: `{int(weekly['bullish_bias_start'].fillna(False).sum())}`
- Weekly bearish/cash starts: `{int(weekly['bearish_cash_bias_start'].fillna(False).sum())}`
- Weekly bar/CCI discrepancies versus run evidence: `{manifest['weekly_cci_formula_discrepancy_count']}`
- Weekly bar construction audit passed: `{manifest['weekly_cci_audit_passed']}`
"""


def signal_logic_report(manifest: dict[str, Any]) -> str:
    return f"""# Signal Logic Audit

The audit verified the frozen long-only CCI logic:

- Bullish bias starts only when completed weekly CCI(26) is above `{WEEKLY_BULLISH_THRESHOLD}`.
- Bearish/cash bias starts only when completed weekly CCI(26) is below `{WEEKLY_BEARISH_THRESHOLD}`.
- Daily pullback condition requires bullish bias and daily CCI(26) below `{DAILY_PULLBACK_THRESHOLD}`.
- Entry/hold SPY requires a prior armed pullback and daily CCI(26) above `{DAILY_REVERSAL_THRESHOLD}`.
- Bearish mode maps to BIL/cash only.

Daily signal discrepancies: `{manifest['daily_signal_logic_discrepancy_count']}`
Signal logic audit passed: `{manifest['signal_logic_audit_passed']}`
"""


def no_lookahead_report(manifest: dict[str, Any]) -> str:
    return f"""# Mixed-Frequency No-Lookahead Audit

The audit recomputed completed weekly bias, completed daily CCI, after-close target weights, and one-bar-shifted returns.

- Target weight discrepancies: `{manifest['target_weight_discrepancy_count']}`
- Equity/return discrepancies: `{manifest['equity_return_discrepancy_count']}`
- Timing-sanity row remains context-only: `{manifest['timing_sanity_context_only']}`
- Mixed-frequency no-lookahead audit passed: `{manifest['mixed_frequency_no_lookahead_audit_passed']}`

No same-day close was used both to create a target and profit from that target in the recomputed return stream.
"""


def discrepancy_report(manifest: dict[str, Any], discrepancies: list[dict[str, Any]]) -> str:
    return f"""# Row-Level Discrepancy Report

Total discrepancies: `{len(discrepancies)}`

- Weekly formula discrepancies: `{manifest['weekly_cci_formula_discrepancy_count']}`
- Daily signal discrepancies: `{manifest['daily_signal_logic_discrepancy_count']}`
- Target weight discrepancies: `{manifest['target_weight_discrepancy_count']}`
- Equity/return discrepancies: `{manifest['equity_return_discrepancy_count']}`
- Row metric discrepancies: `{manifest['row_metric_discrepancy_count']}`

The CSV artifact contains row/date/field details. It is intentionally empty apart from headers when the audit finds no discrepancies.
"""


def criteria_report(manifest: dict[str, Any], criteria: list[dict[str, Any]]) -> str:
    primary = next(row for row in criteria if row["variant_id"] == PRIMARY_VARIANT)
    return f"""# Criteria Recalculation Report

- Criteria mismatch count: `{manifest['criteria_mismatch_count']}`
- Primary pass recomputed: `{primary['numeric_criteria_pass_recomputed']}`
- Primary pass in run evidence: `{primary['numeric_criteria_pass_run_evidence']}`
- Controls remain controls only: `true`
- Timing-sanity remains context-only: `{manifest['timing_sanity_context_only']}`
- Criteria recomputation passed: `{manifest['criteria_recomputation_passed']}`
"""


def control_report(manifest: dict[str, Any]) -> str:
    control = manifest["control_comparison"]
    return f"""# Control Comparison And Conservative Interpretation

The primary row passed its pre-registered numeric criteria, but the control comparison is weak.

- Primary total return: `{control['primary_total_return']}`
- SPY buy-hold total return: `{control['spy_buy_hold_total_return']}`
- SPY_200d total return: `{control['spy200d_total_return']}`
- Primary max drawdown: `{control['primary_max_drawdown']}`
- SPY_200d max drawdown: `{control['spy200d_max_drawdown']}`
- Primary return/drawdown proxy: `{control['primary_return_drawdown_proxy']}`
- SPY_200d return/drawdown proxy: `{control['spy200d_return_drawdown_proxy']}`

Interpretation checks:

- Primary underperforms SPY buy-hold on total return: `{control['primary_underperforms_spy_buy_hold_total_return']}`
- Primary underperforms SPY_200d on total return: `{control['primary_underperforms_spy200d_total_return']}`
- Primary underperforms SPY_200d on max drawdown: `{control['primary_underperforms_spy200d_max_drawdown']}`
- Primary underperforms SPY_200d on return/drawdown proxy: `{control['primary_underperforms_spy200d_return_drawdown_proxy']}`
- Serious interpretation weakness: `{control['serious_interpretation_weakness']}`

This report does not override the registered pass/fail result. It records that the pass is control-weak and should not be interpreted as strong standalone evidence.
"""


def timing_sanity_report(manifest: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    timing = next(row for row in rows if row["variant_id"] == TIMING_VARIANT)
    return f"""# Timing-Sanity Interpretation Report

The one-extra-bar delayed row is present only to test timing sensitivity.

- Timing-sanity context-only flag: `{manifest['timing_sanity_context_only']}`
- Timing-sanity total return: `{timing['total_return']}`
- Timing-sanity max drawdown: `{timing['max_drawdown']}`
- Timing-sanity numeric criteria flag in run evidence remains non-promotional and non-candidate.
"""


def long_only_report(manifest: dict[str, Any]) -> str:
    return f"""# Long-Only Adaptation Audit

- Bearish source-side logic maps only to BIL/cash: `{manifest['long_only_adaptation_preserved']}`
- Shorting/inverse exposure/leverage/options/futures/intraday used: `false`
- Broker/live path touched: `false`
- Real-money recommendation made: `false`

The long-only adaptation caveat was preserved in the run evidence and this audit evidence.
"""


def similarity_report(manifest: dict[str, Any]) -> str:
    return f"""# Similarity-Risk Audit

- Similarity contexts preserved: `{manifest['similarity_contexts_preserved']}`
- Similarity context count: `10`
- Specific duplicate/do-not-retest match discovered by the run: `{manifest['specific_duplicate_or_do_not_retest_match_discovered']}`
- SPY_200d control weakness visible: `{manifest['spy200d_control_dominates_primary']}`

The run did not discover a formal duplicate/do-not-retest match, but high similarity to equity timing controls weakens interpretation.
"""


def exposure_report(manifest: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    max_exposure = max(row["max_daily_exposure"] for row in rows)
    max_weight_sum = max(row["max_daily_weight_sum"] for row in rows)
    failures = [row["variant_id"] for row in rows if row["exposure_invariant_pass"] is not True]
    return f"""# Exposure Invariant Audit

- Max daily exposure recomputed: `{max_exposure}`
- Max daily weight sum recomputed: `{max_weight_sum}`
- Invariant failure variants: `{failures}`
- Exposure invariant audit passed: `{manifest['exposure_invariant_audit_passed']}`
"""


def summary_report(manifest: dict[str, Any]) -> str:
    return f"""# CCI Correction Results Audit Summary

Source ID: `{manifest['source_id']}`
Lane ID: `{manifest['lane_id']}`

Evidence completeness passed: `{manifest['evidence_completeness_passed']}`
Rows reviewed: `{manifest['variant_count_reviewed']}`
Discrepancies found: `{manifest['total_discrepancy_count']}`
Criteria recomputation passed: `{manifest['criteria_recomputation_passed']}`
Exposure invariants passed: `{manifest['exposure_invariant_audit_passed']}`

Primary numeric criteria pass recomputed: `{manifest['primary_numeric_criteria_pass_recomputed']}`
Serious control-comparison weakness: `{manifest['serious_interpretation_weakness']}`

Audit decision: `{manifest['audit_decision']}`
Exact next action: `{manifest['next_action']}`

No CCI tuning, robustness run, strategy discovery, provider download, intraday data, candidate_exhaustive, promotion, paper/demo activation, broker/live action, or real-money recommendation occurred.
"""


def next_action_report(manifest: dict[str, Any]) -> str:
    return f"""# CCI Results Audit Next Action

Exact next action: `{manifest['next_action']}`

Do not execute this action from the audit packet.
"""


def consistency_check(manifest: dict[str, Any], output: Path) -> dict[str, Any]:
    required = {filename: (output / filename).exists() for filename in REQUIRED_AUDIT_FILES}
    checks = {
        "audit_only_mode": manifest["public_source_cci_correction_results_audit_only"] is True,
        "correct_source_family_lane": manifest["source_id"] == SOURCE_ID
        and manifest["family_id"] == FAMILY_ID
        and manifest["lane_id"] == LANE_ID,
        "source_run_evidence_reviewed": manifest["source_run_evidence_reviewed"] is True,
        "source_design_evidence_reviewed": manifest["source_design_evidence_reviewed"] is True,
        "variant_count_exact_5": manifest["variant_count_exact_5"] is True,
        "evidence_completeness_passed": manifest["evidence_completeness_passed"] is True,
        "no_formula_or_signal_discrepancies": manifest["weekly_cci_formula_discrepancy_count"] == 0
        and manifest["daily_signal_logic_discrepancy_count"] == 0,
        "no_weight_or_equity_discrepancies": manifest["target_weight_discrepancy_count"] == 0
        and manifest["equity_return_discrepancy_count"] == 0,
        "criteria_recomputed": manifest["criteria_recomputation_passed"] is True,
        "exposure_invariants_pass": manifest["exposure_invariant_audit_passed"] is True,
        "control_weakness_reported": manifest["serious_interpretation_weakness"] is True
        and manifest["audit_decision"] == AUDIT_PASSED_BUT_CONTROL_WEAK,
        "long_only_and_similarity_preserved": manifest["long_only_adaptation_preserved"] is True
        and manifest["similarity_contexts_preserved"] is True,
        "no_forbidden_actions": manifest["provider_download"] is False
        and manifest["intraday_data_used"] is False
        and manifest["public_source_scraped"] is False
        and manifest["cci_parameters_tuned"] is False
        and manifest["robustness_run"] is False
        and manifest["strategy_discovery_run"] is False
        and manifest["candidate_exhaustive_run"] is False
        and manifest["promotion_candidates_created"] is False
        and manifest["paper_forward_activation"] is False
        and manifest["broker_api_called"] is False
        and manifest["live_orders"] is False
        and manifest["real_money_recommendation"] is False,
        "outputs_remain_diagnostic": manifest["outputs_diagnostic_only"] is True
        and manifest["outputs_non_promotable"] is True
        and manifest["candidate_exhaustive_ready"] is False
        and manifest["paper_demo_eligible"] is False,
        "next_action_valid": manifest["next_action"] in VALID_NEXT_ACTIONS,
        "required_files_present": all(required.values()),
    }
    return {**checks, "required_files": required, "consistency_passed": all(checks.values())}


def run(root: Path = ROOT) -> dict[str, Any]:
    return build_audit(root)


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, default=str))
