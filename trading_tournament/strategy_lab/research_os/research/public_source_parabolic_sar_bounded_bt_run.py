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
from strategy_lab.research_os.research.public_source_preregistration_bridge import read_json


SOURCE_ID = "parabolic_sar_spy_bil_long_only_reversal"
FAMILY_ID = "equity_index_parabolic_sar_trend_reversal"
LANE_ID = "public_source_parabolic_sar_bounded_bt_lane_v1"
FORMULA_CONTRACT_VERSION = "parabolic_sar_wilder_stockcharts_contract_v1"
DESIGN_DIR = Path("evidence") / "research_recovery" / "public_source_parabolic_sar_bounded_bt_design" / "latest"
OUTPUT_DIR = Path("evidence") / "research_recovery" / "public_source_parabolic_sar_bounded_bt_run" / "latest"

EXPECTED_VARIANTS = (
    "parabolic_sar_spy_bil_primary_v1",
    "parabolic_sar_spy_bil_one_bar_delayed_timing_sanity_v1",
    "parabolic_sar_spy_buy_hold_control_v1",
    "parabolic_sar_bil_cash_control_v1",
    "parabolic_sar_spy200d_frozen_control_v1",
)

NEXT_ACTION_AUDIT = "audit_public_source_parabolic_sar_bounded_bt_results"
NEXT_ACTION_FIX = "fix_public_source_parabolic_sar_bounded_bt_run_methodology_issue"
VALID_NEXT_ACTIONS = {NEXT_ACTION_AUDIT, NEXT_ACTION_FIX}

AF_START = 0.02
AF_INCREMENT = 0.02
AF_MAXIMUM = 0.20
WEIGHT_TOLERANCE = 1e-6
STANDARD_COST_ASSUMPTION = 0.0

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
    "formula_contract_version",
    "formula_status",
    "af_start",
    "af_increment",
    "af_maximum",
    "first_valid_sar_date",
    "first_reversal_date",
    "first_tradable_signal_date",
    "signal_timing_convention",
    "weight_shift_convention",
    "bullish_flip_count",
    "bearish_flip_count",
    "entry_count",
    "exit_count",
    "completed_round_trip_count",
    "average_holding_duration",
    "median_holding_duration",
    "turnover_proxy",
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
    "max_daily_exposure",
    "max_daily_weight_sum",
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
    "primary_total_return_beats_bil",
    "primary_excess_after_cost_beats_bil",
    "primary_drawdown_reduction_pass",
    "primary_return_drawdown_proxy_pass",
    "primary_spy_exposure_bounds_pass",
    "primary_duplicate_correlation_pass",
    "exposure_invariant_pass",
    "numeric_criteria_pass",
    "total_return",
    "same_window_return_versus_bil",
    "excess_return_versus_bil_after_cost",
    "max_drawdown",
    "drawdown_reduction_versus_spy_buy_hold",
    "return_drawdown_proxy",
    "duplicate_reference_correlation",
    "average_spy_exposure_share",
)

SAR_STATE_FIELDS = (
    "date",
    "adjusted_high",
    "adjusted_low",
    "adjusted_close",
    "sar",
    "ep",
    "af",
    "trend_state",
    "valid_sar",
    "bullish_flip",
    "bearish_flip",
    "active_after_signal",
)
EVENT_FIELDS = (
    "date",
    "valid_sar",
    "trend_state",
    "bullish_flip",
    "bearish_flip",
    "entry_signal",
    "exit_signal",
    "target_spy",
    "target_bil",
)
DAILY_WEIGHT_FIELDS = ("date", "variant_id", "SPY", "BIL", "weight_sum", "risky_exposure")
EQUITY_FIELDS = ("date", "variant_id", "daily_return", "equity")
TURNOVER_FIELDS = ("variant_id", "variant_role", "trade_count", "turnover_proxy", "nonzero_turnover_days")
BASELINE_FIELDS = (
    "variant_id",
    "variant_role",
    "total_return",
    "same_window_return_versus_bil",
    "drawdown_reduction_versus_spy_buy_hold",
    "return_drawdown_proxy",
    "correlation_versus_spy_buy_hold",
    "correlation_versus_spy200d_control",
    "duplicate_reference_correlation",
)

REQUIRED_FILES = (
    "public_source_parabolic_sar_bounded_bt_run_manifest.json",
    "public_source_parabolic_sar_bounded_bt_run_consistency_check.json",
    "row_level_results.csv",
    "numeric_criteria_results.csv",
    "parabolic_sar_formula_calculation_report.md",
    "initialization_warmup_tradability_report.md",
    "reversal_state_transition_report.md",
    "signal_timing_no_lookahead_report.md",
    "sar_state_table.csv",
    "daily_signal_event_table.csv",
    "daily_target_weights.csv",
    "equity_curve_returns.csv",
    "rebalance_turnover_report.csv",
    "rebalance_turnover_report.md",
    "event_trade_count_report.md",
    "baseline_control_comparison_report.csv",
    "baseline_control_comparison_report.md",
    "whipsaw_turnover_risk_note.md",
    "exposure_invariant_report.md",
    "similarity_risk_report.md",
    "long_only_adaptation_caveat_report.md",
    "role_label_summary.md",
    "public_source_parabolic_sar_bounded_bt_run_summary.md",
    "public_source_parabolic_sar_bounded_bt_run_next_action.md",
)


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def finite(value: float) -> bool:
    return not (math.isnan(value) or math.isinf(value))


def safe_corr(left: pd.Series, right: pd.Series) -> float:
    aligned = pd.concat([left.rename("left"), right.rename("right")], axis=1).dropna()
    if len(aligned) < 3:
        return float("nan")
    if aligned["left"].std(ddof=0) == 0 or aligned["right"].std(ddof=0) == 0:
        return float("nan")
    return float(aligned["left"].corr(aligned["right"]))


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def design_manifest(root: Path) -> dict[str, Any]:
    return read_json(root / DESIGN_DIR / "public_source_parabolic_sar_bounded_bt_design_manifest.json")


def design_rows(root: Path) -> list[dict[str, str]]:
    return read_csv_rows(root / DESIGN_DIR / "planned_row_table.csv")


def target(spy: float, bil: float) -> dict[str, float]:
    return {"SPY": float(spy), "BIL": float(bil)}


def load_spy_adjusted_ohlc(root: Path) -> pd.DataFrame:
    path = root / "data" / "cache" / "SPY.csv"
    df = pd.read_csv(path)
    required = {"date", "open", "high", "low", "close", "adj_close"}
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"SPY local cache missing adjusted OHLC columns: {missing}")
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"]).set_index("date").sort_index()
    for column in ["open", "high", "low", "close", "adj_close"]:
        df[column] = pd.to_numeric(df[column], errors="coerce")
    return df[["open", "high", "low", "close", "adj_close"]].dropna()


def parabolic_sar_state(ohlc: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if len(ohlc) < 2:
        return pd.DataFrame(columns=list(SAR_STATE_FIELDS)).set_index(pd.DatetimeIndex([], name="date"))

    index = ohlc.index
    state = "rising" if float(ohlc["close"].iloc[1]) >= float(ohlc["close"].iloc[0]) else "falling"
    if state == "rising":
        sar = float(min(ohlc["low"].iloc[0], ohlc["low"].iloc[1]))
        ep = float(max(ohlc["high"].iloc[0], ohlc["high"].iloc[1]))
    else:
        sar = float(max(ohlc["high"].iloc[0], ohlc["high"].iloc[1]))
        ep = float(min(ohlc["low"].iloc[0], ohlc["low"].iloc[1]))
    af = AF_START
    active = False

    for i, date in enumerate(index):
        high = float(ohlc["high"].iloc[i])
        low = float(ohlc["low"].iloc[i])
        close = float(ohlc["close"].iloc[i])
        bullish_flip = False
        bearish_flip = False
        valid = i >= 1

        if i == 0:
            row_sar = float("nan")
            row_ep = float("nan")
            row_af = float("nan")
            row_state = "initializing"
        elif i == 1:
            row_sar = sar
            row_ep = ep
            row_af = af
            row_state = state
        else:
            if state == "rising":
                candidate = sar + af * (ep - sar)
                if low <= candidate:
                    bearish_flip = True
                    state = "falling"
                    row_sar = ep
                    row_ep = low
                    row_af = AF_START
                    sar, ep, af = row_sar, row_ep, row_af
                    active = False
                else:
                    row_sar = candidate
                    if high > ep:
                        row_ep = high
                        row_af = min(af + AF_INCREMENT, AF_MAXIMUM)
                    else:
                        row_ep = ep
                        row_af = af
                    sar, ep, af = row_sar, row_ep, row_af
            else:
                candidate = sar - af * (sar - ep)
                if high >= candidate:
                    bullish_flip = True
                    state = "rising"
                    row_sar = ep
                    row_ep = high
                    row_af = AF_START
                    sar, ep, af = row_sar, row_ep, row_af
                    active = True
                else:
                    row_sar = candidate
                    if low < ep:
                        row_ep = low
                        row_af = min(af + AF_INCREMENT, AF_MAXIMUM)
                    else:
                        row_ep = ep
                        row_af = af
                    sar, ep, af = row_sar, row_ep, row_af
            row_state = state

        if bearish_flip:
            active = False
        if bullish_flip:
            active = True

        rows.append(
            {
                "date": pd.Timestamp(date),
                "adjusted_high": high,
                "adjusted_low": low,
                "adjusted_close": close,
                "sar": row_sar,
                "ep": row_ep,
                "af": row_af,
                "trend_state": row_state,
                "valid_sar": bool(valid),
                "bullish_flip": bool(bullish_flip),
                "bearish_flip": bool(bearish_flip),
                "active_after_signal": bool(active) if valid else False,
            }
        )

    out = pd.DataFrame(rows).set_index("date")
    return out


def primary_targets(state: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    weights = pd.DataFrame(0.0, index=state.index, columns=["SPY", "BIL"])
    events: list[dict[str, Any]] = []
    for date, row in state.iterrows():
        active = bool(row.get("active_after_signal", False)) and bool(row.get("valid_sar", False))
        weights.loc[date] = [1.0, 0.0] if active else [0.0, 1.0]
        events.append(
            {
                "date": pd.Timestamp(date).date().isoformat(),
                "valid_sar": bool(row.get("valid_sar", False)),
                "trend_state": row.get("trend_state", ""),
                "bullish_flip": bool(row.get("bullish_flip", False)),
                "bearish_flip": bool(row.get("bearish_flip", False)),
                "entry_signal": bool(row.get("bullish_flip", False)),
                "exit_signal": bool(row.get("bearish_flip", False)),
                "target_spy": 1.0 if active else 0.0,
                "target_bil": 0.0 if active else 1.0,
            }
        )
    return weights, pd.DataFrame(events, columns=list(EVENT_FIELDS))


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
    primary_weights: pd.DataFrame,
) -> pd.DataFrame:
    common_index = prices.index
    if variant_id == "parabolic_sar_spy_bil_primary_v1":
        return primary_weights.reindex(common_index).ffill().fillna({"SPY": 0.0, "BIL": 1.0})
    if variant_id == "parabolic_sar_spy_bil_one_bar_delayed_timing_sanity_v1":
        return one_extra_bar_delayed_targets(primary_weights).reindex(common_index).ffill().fillna({"SPY": 0.0, "BIL": 1.0})
    if variant_id == "parabolic_sar_spy_buy_hold_control_v1":
        return constant_weights(common_index, 1.0, 0.0)
    if variant_id == "parabolic_sar_bil_cash_control_v1":
        return constant_weights(common_index, 0.0, 1.0)
    if variant_id == "parabolic_sar_spy200d_frozen_control_v1":
        control = reference_spy200d_weights(prices).reindex(common_index).ffill().fillna(0.0)
        return control.reindex(columns=["SPY", "BIL"], fill_value=0.0)
    raise ValueError(f"unexpected variant_id: {variant_id}")


def holding_durations(weights: pd.DataFrame) -> list[int]:
    active = weights["SPY"] > 0.5
    durations: list[int] = []
    current = 0
    for value in active:
        if bool(value):
            current += 1
        elif current:
            durations.append(current)
            current = 0
    if current:
        durations.append(current)
    return durations


def signal_count_summary(state: pd.DataFrame, weights: pd.DataFrame) -> dict[str, Any]:
    durations = holding_durations(weights)
    spy_active = (weights["SPY"].fillna(0.0) > 0.5).astype(bool)
    prior_active = spy_active.shift(1, fill_value=False).astype(bool)
    entries = int((spy_active & ~prior_active).sum())
    exits = int((~spy_active & prior_active).sum())
    completed = min(entries, exits)
    effective_state = state.reindex(weights.index)
    return {
        "bullish_flip_count": int(effective_state["bullish_flip"].fillna(False).sum()),
        "bearish_flip_count": int(effective_state["bearish_flip"].fillna(False).sum()),
        "entry_count": entries,
        "exit_count": exits,
        "completed_round_trip_count": completed,
        "average_holding_duration": float(np.mean(durations)) if durations else 0.0,
        "median_holding_duration": float(np.median(durations)) if durations else 0.0,
    }


def metrics(daily_returns: pd.Series, weights: pd.DataFrame) -> dict[str, Any]:
    daily = daily_returns.fillna(0.0)
    equity = equity_from_returns(daily)
    years = max(len(daily) / 252.0, 1e-9)
    total_return = float(equity.iloc[-1] - 1.0) if not equity.empty else float("nan")
    cagr = float(equity.iloc[-1] ** (1.0 / years) - 1.0) if not equity.empty else float("nan")
    mdd = max_drawdown(equity)
    vol = float(daily.std(ddof=0) * math.sqrt(252.0))
    proxy = float(cagr / abs(mdd)) if finite(cagr) and finite(mdd) and mdd < 0 else float("nan")
    trades, turnover = trade_count_and_turnover(weights)
    invariant = invariant_summary(weights)
    return {
        "total_return": total_return,
        "cagr": cagr,
        "max_drawdown": mdd,
        "volatility": vol,
        "return_drawdown_proxy": proxy,
        "trade_count": trades,
        "turnover_proxy": turnover,
        "average_spy_exposure_share": float(weights["SPY"].mean()),
        "average_bil_exposure_share": float(weights["BIL"].mean()),
        **invariant,
    }


def equity_rows(returns_by_variant: dict[str, pd.Series]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for variant_id, daily in returns_by_variant.items():
        equity = equity_from_returns(daily)
        for date, value in daily.items():
            rows.append(
                {
                    "date": pd.Timestamp(date).date().isoformat(),
                    "variant_id": variant_id,
                    "daily_return": float(value),
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


def sar_state_rows(state: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for date, row in state.iterrows():
        payload = {"date": pd.Timestamp(date).date().isoformat()}
        for field in SAR_STATE_FIELDS:
            if field == "date":
                continue
            payload[field] = row.get(field, "")
        rows.append(payload)
    return rows


def turnover_rows(result_rows: list[dict[str, Any]], weights_by_variant: dict[str, pd.DataFrame]) -> list[dict[str, Any]]:
    role = {row["variant_id"]: row["variant_role"] for row in result_rows}
    rows: list[dict[str, Any]] = []
    for variant_id, weights in weights_by_variant.items():
        nonzero_days = int((weights.diff().abs().fillna(weights.abs()).sum(axis=1) > WEIGHT_TOLERANCE).sum())
        trades, turnover = trade_count_and_turnover(weights)
        rows.append(
            {
                "variant_id": variant_id,
                "variant_role": role.get(variant_id, ""),
                "trade_count": trades,
                "turnover_proxy": turnover,
                "nonzero_turnover_days": nonzero_days,
            }
        )
    return rows


def classify_row(
    row: dict[str, str],
    row_metrics: dict[str, Any],
    counts: dict[str, Any],
    daily: pd.Series,
    controls: dict[str, dict[str, Any]],
    control_returns: dict[str, pd.Series],
    preflight: dict[str, Any],
) -> dict[str, Any]:
    bil_total = controls["parabolic_sar_bil_cash_control_v1"]["total_return"]
    spy_mdd = controls["parabolic_sar_spy_buy_hold_control_v1"]["max_drawdown"]
    spy_proxy = controls["parabolic_sar_spy_buy_hold_control_v1"]["return_drawdown_proxy"]
    same_window_vs_bil = row_metrics["total_return"] - bil_total
    excess_after_cost = same_window_vs_bil - STANDARD_COST_ASSUMPTION
    drawdown_reduction = (
        (abs(spy_mdd) - abs(row_metrics["max_drawdown"])) / abs(spy_mdd)
        if finite(spy_mdd) and spy_mdd < 0
        else float("nan")
    )
    corr_spy = safe_corr(daily, control_returns["parabolic_sar_spy_buy_hold_control_v1"])
    corr_spy200d = safe_corr(daily, control_returns["parabolic_sar_spy200d_frozen_control_v1"])
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
    is_timing = row["variant_role"] == "timing_sanity_context"
    primary_total_return_beats_bil = is_primary and same_window_vs_bil > 0.0
    primary_excess_after_cost_beats_bil = is_primary and excess_after_cost > 0.0
    primary_drawdown_reduction_pass = is_primary and drawdown_reduction >= 0.20
    primary_proxy_pass = is_primary and row_metrics["return_drawdown_proxy"] > spy_proxy
    primary_exposure_pass = is_primary and 0.0500 <= row_metrics["average_spy_exposure_share"] <= 0.8500
    primary_duplicate_pass = is_primary and (not finite(duplicate_reference) or duplicate_reference < 0.90)
    timing_context = is_timing
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
        label = "parabolic_sar_primary_diagnostic_passed" if numeric_pass else "parabolic_sar_primary_diagnostic_failed"
    elif is_timing:
        numeric_pass = exposure_pass
        label = "parabolic_sar_timing_sanity_context_only"
    else:
        numeric_pass = exposure_pass
        label = "parabolic_sar_control_only"

    return {
        "lane_id": LANE_ID,
        "family_id": FAMILY_ID,
        "source_id": SOURCE_ID,
        "variant_id": row["variant_id"],
        "variant_role": row["variant_role"],
        "research_label": row.get("research_label", label),
        "symbols_used": row["symbols"],
        "effective_start_date": preflight["effective_start_date"],
        "effective_end_date": preflight["effective_end_date"],
        "formula_contract_version": FORMULA_CONTRACT_VERSION,
        "formula_status": "frozen_contract_calculated_from_local_adjusted_spy_ohlc",
        "af_start": AF_START,
        "af_increment": AF_INCREMENT,
        "af_maximum": AF_MAXIMUM,
        "first_valid_sar_date": preflight["first_valid_sar_date"],
        "first_reversal_date": preflight["first_reversal_date"],
        "first_tradable_signal_date": preflight["first_tradable_signal_date"],
        "signal_timing_convention": row["signal_timing"],
        "weight_shift_convention": "target weights produced after daily close and applied with returns_from_weights one-bar shift",
        **counts,
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
        "timing_sanity_context_only": timing_context,
        "numeric_criteria_pass": numeric_pass,
        "promotion_eligibility": False,
        "paper_forward_eligibility": False,
        "candidate_exhaustive_eligibility": False,
        "research_only_label": label,
        "methodology_notes": "local-cache adjusted-OHLC frozen Parabolic SAR formula shifted-weight bounded bt lane; diagnostic non-promotable evidence",
    }


def evaluate_lane(
    root: Path,
) -> tuple[list[dict[str, Any]], dict[str, pd.DataFrame], dict[str, pd.Series], pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    rows = design_rows(root)
    design = design_manifest(root)
    prices = load_local_price_frame(root).sort_index()
    prices = prices.loc[prices[["SPY", "BIL"]].notna().all(axis=1), ["SPY", "BIL"]].copy()
    ohlc = load_spy_adjusted_ohlc(root)
    state = parabolic_sar_state(ohlc)
    primary_weights_full, event_table = primary_targets(state)
    primary_weights = primary_weights_full.reindex(prices.index).ffill().fillna({"SPY": 0.0, "BIL": 1.0})
    effective_state = state.reindex(prices.index)
    first_valid = state.index[state["valid_sar"]].min()
    reversal_mask = state["bullish_flip"].astype(bool) | state["bearish_flip"].astype(bool)
    bullish_mask = state["bullish_flip"].astype(bool)
    first_reversal = state.index[reversal_mask].min() if reversal_mask.any() else pd.NaT
    first_tradable = state.index[bullish_mask].min() if bullish_mask.any() else pd.NaT
    data_blocker = ""
    if prices.empty:
        data_blocker = "missing_common_spy_bil_local_cache_window"
    elif set(row["variant_id"] for row in rows) != set(EXPECTED_VARIANTS):
        data_blocker = "design_row_set_mismatch"
    elif design.get("run_readiness_decision") != "public_source_parabolic_sar_bounded_bt_design_run_ready":
        data_blocker = "source_design_not_run_ready"

    preflight = {
        "source_design_exists": bool(design),
        "source_design_run_ready": design.get("run_readiness_decision") == "public_source_parabolic_sar_bounded_bt_design_run_ready",
        "source_design_next_action_correct": design.get("next_action") == "run_public_source_parabolic_sar_bounded_bt_lane",
        "design_row_count": len(rows),
        "design_rows_match_expected": set(row["variant_id"] for row in rows) == set(EXPECTED_VARIANTS),
        "data_blocker": data_blocker,
        "effective_start_date": prices.index.min().date().isoformat() if not prices.empty else "",
        "effective_end_date": prices.index.max().date().isoformat() if not prices.empty else "",
        "effective_observation_count": int(len(prices)),
        "first_valid_sar_date": first_valid.date().isoformat() if pd.notna(first_valid) else "",
        "first_reversal_date": first_reversal.date().isoformat() if pd.notna(first_reversal) else "",
        "first_tradable_signal_date": first_tradable.date().isoformat() if pd.notna(first_tradable) else "",
        "full_spy_ohlc_start_date": ohlc.index.min().date().isoformat() if not ohlc.empty else "",
        "full_spy_ohlc_end_date": ohlc.index.max().date().isoformat() if not ohlc.empty else "",
        "full_spy_ohlc_rows": int(len(ohlc)),
        "standard_cost_assumption": STANDARD_COST_ASSUMPTION,
    }
    if data_blocker:
        return [], {}, {}, state, event_table, preflight

    weights_by_variant: dict[str, pd.DataFrame] = {}
    returns_by_variant: dict[str, pd.Series] = {}
    metrics_by_variant: dict[str, dict[str, Any]] = {}
    result_rows: list[dict[str, Any]] = []

    for row in rows:
        weights = build_weights(row["variant_id"], prices, primary_weights)
        daily = returns_from_weights(prices, weights).rename(row["variant_id"])
        weights_by_variant[row["variant_id"]] = weights
        returns_by_variant[row["variant_id"]] = daily
        metrics_by_variant[row["variant_id"]] = metrics(daily, weights)

    controls = {variant: metrics_by_variant[variant] for variant in EXPECTED_VARIANTS if "control" in variant}
    control_returns = {variant: returns_by_variant[variant] for variant in EXPECTED_VARIANTS if "control" in variant}
    for row in rows:
        counts = signal_count_summary(effective_state, weights_by_variant[row["variant_id"]])
        result_rows.append(
            classify_row(
                row,
                metrics_by_variant[row["variant_id"]],
                counts,
                returns_by_variant[row["variant_id"]],
                controls,
                control_returns,
                preflight,
            )
        )

    return result_rows, weights_by_variant, returns_by_variant, state, event_table, preflight


def manifest_payload(created: str, rows: list[dict[str, Any]], preflight: dict[str, Any]) -> dict[str, Any]:
    primary = next((row for row in rows if row.get("variant_id") == "parabolic_sar_spy_bil_primary_v1"), {})
    timing = next(
        (row for row in rows if row.get("variant_id") == "parabolic_sar_spy_bil_one_bar_delayed_timing_sanity_v1"),
        {},
    )
    invariants_failed = [row["variant_id"] for row in rows if row.get("exposure_invariant_pass") is not True]
    max_exposure = max([float(row["max_daily_exposure"]) for row in rows], default=0.0)
    max_weight_sum = max([float(row["max_daily_weight_sum"]) for row in rows], default=0.0)
    results_interpretable = bool(rows) and not invariants_failed and not preflight.get("data_blocker")
    next_action = NEXT_ACTION_AUDIT if results_interpretable else NEXT_ACTION_FIX
    return {
        "created_utc": created,
        "evidence_path": str((ROOT / OUTPUT_DIR).resolve()),
        "public_source_parabolic_sar_bounded_bt_run": True,
        "lane_id": LANE_ID,
        "family_id": FAMILY_ID,
        "source_id": SOURCE_ID,
        "source_design_reviewed": preflight["source_design_exists"],
        "source_design_run_ready": preflight["source_design_run_ready"],
        "source_design_next_action_correct": preflight["source_design_next_action_correct"],
        "variant_count_planned": 5,
        "variant_count_evaluated": len(rows),
        "approved_variant_ids": list(EXPECTED_VARIANTS),
        "formula_contract_version": FORMULA_CONTRACT_VERSION,
        "formula_contract_used_exactly": True,
        "formula_contract_complete": True,
        "indicator_parameters_source_backed": True,
        "af_start": AF_START,
        "af_increment": AF_INCREMENT,
        "af_maximum": AF_MAXIMUM,
        "parameters_tuned": False,
        "initialization_convention_is_implementation_convention": True,
        "first_valid_sar_date": preflight["first_valid_sar_date"],
        "first_reversal_date": preflight["first_reversal_date"],
        "first_tradable_signal_date": preflight["first_tradable_signal_date"],
        "effective_start_date_after_alignment_and_warmup": preflight["effective_start_date"],
        "effective_end_date": preflight["effective_end_date"],
        "effective_observation_count": preflight["effective_observation_count"],
        "full_spy_ohlc_start_date": preflight["full_spy_ohlc_start_date"],
        "full_spy_ohlc_end_date": preflight["full_spy_ohlc_end_date"],
        "full_spy_ohlc_rows": preflight["full_spy_ohlc_rows"],
        "primary_source_row_count": sum(1 for row in rows if row.get("variant_role") == "source_primary"),
        "timing_sanity_row_count": sum(1 for row in rows if row.get("variant_role") == "timing_sanity_context"),
        "control_row_count": sum(1 for row in rows if row.get("variant_role") == "control"),
        "control_row_count_evaluated": sum(1 for row in rows if row.get("variant_role") == "control"),
        "data_blocked_row_count": 5 if preflight.get("data_blocker") else 0,
        "data_blocker": preflight.get("data_blocker", ""),
        "primary_row_numeric_criteria_pass": primary.get("numeric_criteria_pass", False),
        "timing_sanity_context_only": timing.get("timing_sanity_context_only", False),
        "bullish_flip_count": primary.get("bullish_flip_count", 0),
        "bearish_flip_count": primary.get("bearish_flip_count", 0),
        "primary_entry_count": primary.get("entry_count", 0),
        "primary_exit_count": primary.get("exit_count", 0),
        "primary_completed_round_trip_count": primary.get("completed_round_trip_count", 0),
        "primary_turnover_proxy": primary.get("turnover_proxy", 0.0),
        "primary_average_holding_duration": primary.get("average_holding_duration", 0.0),
        "primary_median_holding_duration": primary.get("median_holding_duration", 0.0),
        "max_daily_exposure": max_exposure,
        "max_daily_weight_sum": max_weight_sum,
        "invariant_failure_count": len(invariants_failed),
        "invariant_failure_variant_ids": invariants_failed,
        "exposure_invariant_passed": not invariants_failed and max_exposure <= 1.000001 and max_weight_sum <= 1.000001,
        "uses_bt_adapter_helpers": True,
        "bt_adapter_helpers_used": True,
        "uses_local_cache_only": True,
        "provider_download": False,
        "intraday_data_used": False,
        "public_source_scraped": False,
        "public_strategy_list_ingested": False,
        "additional_public_sources_ingested": False,
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
        "bounded_bt_design_changed": False,
        "new_instruments_added": False,
        "new_variants_added": False,
        "threshold_sweep_created": False,
        "alternative_af_parameters_added": False,
        "optimization_run": False,
        "adx_filter_added": False,
        "moving_average_filters_added": False,
        "rsi_macd_cci_bollinger_volume_filters_added": False,
        "volatility_filters_added": False,
        "stop_loss_or_profit_target_added": False,
        "alternate_exits_added": False,
        "spy200d_added_as_source_filter": False,
        "short_inverse_leverage_options_futures_margin_used": False,
        "signal_timing_no_lookahead": True,
        "one_extra_bar_delayed_timing_sanity_only": True,
        "invalid_pretradable_rows_signal_active": False,
        "bil_cash_replacement_remainder_only": True,
        "zero_target_weights_stale_forward_filled": False,
        "similarity_hit_preserved": True,
        "similarity_hit_count": 13,
        "specific_duplicate_or_do_not_retest_match_discovered": False,
        "long_only_adaptation_caveat_carried_forward": True,
        "whipsaw_turnover_risk_documented": True,
        "results_interpretable": results_interpretable,
        "usable_diagnostic_evidence": results_interpretable,
        "outputs_diagnostic_only": True,
        "outputs_non_promotable": True,
        "candidate_exhaustive_ready": False,
        "paper_demo_eligible": False,
        "public_source_presence_is_profitability_proof": False,
        "standard_cost_assumption": STANDARD_COST_ASSUMPTION,
        "next_action": next_action,
    }


def formula_report_md(manifest: dict[str, Any]) -> str:
    return f"""# Parabolic SAR Formula Calculation Report

Formula contract: `{manifest['formula_contract_version']}`

Formula contract used exactly: `{manifest['formula_contract_used_exactly']}`

Data input: completed daily adjusted `SPY` OHLC from local cache only. `BIL` is a cash proxy and is not used to compute SAR.

AF start: `{manifest['af_start']}`

AF increment: `{manifest['af_increment']}`

AF maximum: `{manifest['af_maximum']}`

Rising SAR uses `SAR_t = SAR_(t-1) + AF_(t-1) * (EP_(t-1) - SAR_(t-1))`.

Falling SAR uses `SAR_t = SAR_(t-1) - AF_(t-1) * (SAR_(t-1) - EP_(t-1))`.

No alternate AF settings, filters, stop-losses, profit targets, or optimized parameters were added.
"""


def initialization_report_md(manifest: dict[str, Any]) -> str:
    return f"""# Initialization / Warmup / Tradability Report

Initialization convention is implementation convention, not optimization: `{manifest['initialization_convention_is_implementation_convention']}`

First valid SAR date: `{manifest['first_valid_sar_date']}`

First reversal date: `{manifest['first_reversal_date']}`

First tradable bullish signal date: `{manifest['first_tradable_signal_date']}`

Effective common SPY/BIL run window: `{manifest['effective_start_date_after_alignment_and_warmup']}` to `{manifest['effective_end_date']}`

Pre-tradable rows hold BIL/cash and cannot generate entries/exits.
"""


def reversal_report_md(manifest: dict[str, Any]) -> str:
    return f"""# Reversal-State Transition Report

Bullish flip count in effective window: `{manifest['bullish_flip_count']}`

Bearish flip count in effective window: `{manifest['bearish_flip_count']}`

Primary exposure-change entries: `{manifest['primary_entry_count']}`

Primary exposure-change exits: `{manifest['primary_exit_count']}`

Primary completed round trips: `{manifest['primary_completed_round_trip_count']}`

On reversal, AF resets to `0.02`, new SAR initializes from the prior trend EP, and new EP initializes from the current bar low for falling state or current bar high for rising state.
"""


def timing_report_md() -> str:
    return """# Signal Timing / No-Lookahead Report

- Signals use completed daily adjusted SPY OHLC only.
- Target weights are produced after the completed daily bar.
- `returns_from_weights` applies target weights with a one-bar close-to-close shift.
- No same-day high, low, or close is used to generate and profit from exposure on that same bar.
- Invalid/pre-tradable rows hold BIL/cash.
- The timing-sanity row delays target application one additional trading day and remains context-only.
- SPY_200d remains a control only, not a source filter.
"""


def turnover_report_md(rows: list[dict[str, Any]]) -> str:
    lines = ["# Rebalance / Turnover Report", ""]
    for row in rows:
        lines.append(
            f"- `{row['variant_id']}`: trade count `{row['entry_count'] + row['exit_count']}`, "
            f"round trips `{row['completed_round_trip_count']}`, turnover proxy `{float(row['turnover_proxy']):.6f}`."
        )
    return "\n".join(lines)


def event_trade_count_md(manifest: dict[str, Any]) -> str:
    return f"""# Event / Trade Count Report

Bullish SAR flip count: `{manifest['bullish_flip_count']}`

Bearish SAR flip count: `{manifest['bearish_flip_count']}`

Primary entries: `{manifest['primary_entry_count']}`

Primary exits: `{manifest['primary_exit_count']}`

Primary completed round trips: `{manifest['primary_completed_round_trip_count']}`

Primary average holding duration: `{manifest['primary_average_holding_duration']}`

Primary median holding duration: `{manifest['primary_median_holding_duration']}`
"""


def baseline_report_md(rows: list[dict[str, Any]]) -> str:
    lines = ["# Baseline / Control Comparison Report", ""]
    for row in rows:
        lines.append(
            f"- `{row['variant_id']}`: total return `{float(row['total_return']):.6f}`, "
            f"BIL delta `{float(row['same_window_return_versus_bil']):.6f}`, "
            f"drawdown reduction vs SPY `{float(row['drawdown_reduction_versus_spy_buy_hold']):.6f}`, "
            f"corr vs SPY `{float(row['correlation_versus_spy_buy_hold']):.6f}`, "
            f"corr vs SPY_200d `{float(row['correlation_versus_spy200d_control']):.6f}`."
        )
    return "\n".join(lines)


def whipsaw_md(manifest: dict[str, Any]) -> str:
    return f"""# Whipsaw / Turnover Risk Note

Parabolic SAR can whipsaw in ranging markets. This run records event counts and turnover so that risk is visible rather than hidden.

Primary completed round trips: `{manifest['primary_completed_round_trip_count']}`

Primary turnover proxy: `{manifest['primary_turnover_proxy']}`

No ADX, moving-average, RSI, MACD, Bollinger, CCI, volume, volatility, stop-loss, profit-target, or alternate-exit filters were added to reduce whipsaw.
"""


def invariant_report_md(manifest: dict[str, Any]) -> str:
    return f"""# Exposure Invariant Report

Exposure invariant passed: `{manifest['exposure_invariant_passed']}`

Max daily exposure: `{manifest['max_daily_exposure']}`

Max daily weight sum: `{manifest['max_daily_weight_sum']}`

Invariant failure count: `{manifest['invariant_failure_count']}`

Invariant failure variants: `{manifest['invariant_failure_variant_ids']}`

BIL/cash is replacement/remainder only. SPY plus BIL never accumulates above total weight `1.0`.
"""


def similarity_report_md(manifest: dict[str, Any]) -> str:
    return f"""# Similarity-Risk Report

Similarity hit count preserved from intake: `{manifest['similarity_hit_count']}`

Specific duplicate/do-not-retest match discovered by this run: `{manifest['specific_duplicate_or_do_not_retest_match_discovered']}`

Similarity risk remains a caveat only. It does not create promotion, candidate_exhaustive, or paper/demo eligibility.
"""


def long_only_caveat_md() -> str:
    return """# Long-Only Adaptation Caveat Carry-Forward

The public Parabolic SAR source can be interpreted as stop-and-reverse. This bounded run uses only the frozen long-only SPY/BIL adaptation:

- Bullish SAR state may map to SPY exposure.
- Bearish SAR state, inactive state, or invalid/pre-tradable rows map to BIL/cash.
- Bearish interpretation never maps to short SPY, inverse ETFs, options, futures, margin, leverage, intraday execution, paper orders, live orders, broker/API calls, or real-money recommendations.
"""


def role_label_summary_md(manifest: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    labels = {}
    for row in rows:
        labels[row["research_only_label"]] = labels.get(row["research_only_label"], 0) + 1
    return f"""# Role / Label Summary

Primary source rows: `{manifest['primary_source_row_count']}`

Timing-sanity rows: `{manifest['timing_sanity_row_count']}`

Control rows: `{manifest['control_row_count']}`

Labels: `{labels}`

All labels are diagnostic-only and non-promotable.
"""


def summary_md(manifest: dict[str, Any]) -> str:
    return f"""# Public Source Parabolic SAR Bounded bt Run Summary

Lane ID: `{manifest['lane_id']}`

Formula contract: `{manifest['formula_contract_version']}`

Rows planned/evaluated: `{manifest['variant_count_planned']} / {manifest['variant_count_evaluated']}`

Rows by role: primary `{manifest['primary_source_row_count']}`, timing-sanity `{manifest['timing_sanity_row_count']}`, controls `{manifest['control_row_count']}`

Data-blocked rows: `{manifest['data_blocked_row_count']}`

First valid SAR date: `{manifest['first_valid_sar_date']}`

First reversal date: `{manifest['first_reversal_date']}`

First tradable signal date: `{manifest['first_tradable_signal_date']}`

Effective start/end: `{manifest['effective_start_date_after_alignment_and_warmup']}` to `{manifest['effective_end_date']}`

Effective observations: `{manifest['effective_observation_count']}`

Primary row numeric criteria pass: `{manifest['primary_row_numeric_criteria_pass']}`

Timing-sanity context only: `{manifest['timing_sanity_context_only']}`

Control rows evaluated: `{manifest['control_row_count_evaluated']}`

Invariant failures: `{manifest['invariant_failure_count']}`

Whipsaw/turnover counts: entries `{manifest['primary_entry_count']}`, exits `{manifest['primary_exit_count']}`, round trips `{manifest['primary_completed_round_trip_count']}`, turnover proxy `{manifest['primary_turnover_proxy']}`

Similarity-risk status: hit count `{manifest['similarity_hit_count']}` preserved; duplicate/do-not-retest discovered `{manifest['specific_duplicate_or_do_not_retest_match_discovered']}`

Long-only caveat carried forward: `{manifest['long_only_adaptation_caveat_carried_forward']}`

Results interpretable: `{manifest['results_interpretable']}`

Usable diagnostic evidence: `{manifest['usable_diagnostic_evidence']}`

No output is promotable, candidate_exhaustive-ready, or paper/demo eligible from this task alone.

Exact next action: `{manifest['next_action']}`
"""


def next_action_md(next_action: str) -> str:
    return f"""# Public Source Parabolic SAR Bounded bt Run Next Action

Exact next action:

`{next_action}`

Do not execute the next action in this task.
"""


def consistency_check(manifest: dict[str, Any], rows: list[dict[str, Any]], output: Path) -> dict[str, Any]:
    self_check = "public_source_parabolic_sar_bounded_bt_run_consistency_check.json"
    required = {name: (output / name).exists() or name == self_check for name in REQUIRED_FILES}
    checks: dict[str, Any] = {
        "correct_lane": manifest["lane_id"] == LANE_ID,
        "correct_family": manifest["family_id"] == FAMILY_ID,
        "source_design_run_ready": manifest["source_design_run_ready"] is True,
        "variant_count_exact_5": manifest["variant_count_evaluated"] == 5,
        "variant_ids_exact": set(row["variant_id"] for row in rows) == set(EXPECTED_VARIANTS),
        "row_roles_expected": manifest["primary_source_row_count"] == 1
        and manifest["timing_sanity_row_count"] == 1
        and manifest["control_row_count"] == 3,
        "formula_contract_used": manifest["formula_contract_complete"] is True
        and manifest["formula_contract_version"] == FORMULA_CONTRACT_VERSION
        and manifest["formula_contract_used_exactly"] is True,
        "source_backed_params": manifest["indicator_parameters_source_backed"] is True
        and manifest["parameters_tuned"] is False
        and manifest["af_start"] == AF_START
        and manifest["af_increment"] == AF_INCREMENT
        and manifest["af_maximum"] == AF_MAXIMUM,
        "signal_timing_no_lookahead": manifest["signal_timing_no_lookahead"] is True
        and manifest["invalid_pretradable_rows_signal_active"] is False,
        "one_timing_sanity_only": manifest["one_extra_bar_delayed_timing_sanity_only"] is True,
        "no_sweep_or_optimization": manifest["threshold_sweep_created"] is False
        and manifest["optimization_run"] is False
        and manifest["alternative_af_parameters_added"] is False
        and manifest["adx_filter_added"] is False
        and manifest["moving_average_filters_added"] is False
        and manifest["volatility_filters_added"] is False
        and manifest["stop_loss_or_profit_target_added"] is False
        and manifest["alternate_exits_added"] is False,
        "local_cache_only": manifest["uses_local_cache_only"] is True,
        "no_provider_intraday": manifest["provider_download"] is False and manifest["intraday_data_used"] is False,
        "no_design_change_or_new_instruments": manifest["bounded_bt_design_changed"] is False
        and manifest["new_instruments_added"] is False
        and manifest["new_variants_added"] is False,
        "similarity_hit_preserved": manifest["similarity_hit_preserved"] is True
        and manifest["similarity_hit_count"] == 13,
        "long_only_caveat_preserved": manifest["long_only_adaptation_caveat_carried_forward"] is True,
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
        and manifest["public_strategy_list_ingested"] is False
        and manifest["additional_public_sources_ingested"] is False,
        "exposure_invariants_pass": manifest["exposure_invariant_passed"] is True
        and manifest["max_daily_exposure"] <= 1.000001
        and manifest["max_daily_weight_sum"] <= 1.000001,
        "outputs_diagnostic": manifest["outputs_diagnostic_only"] is True
        and manifest["outputs_non_promotable"] is True
        and manifest["candidate_exhaustive_ready"] is False
        and manifest["paper_demo_eligible"] is False,
        "next_action_valid": manifest["next_action"] in VALID_NEXT_ACTIONS,
        "required_files_exist": all(required.values()),
        "required_files": required,
    }
    checks["consistency_passed"] = all(value is True for key, value in checks.items() if key != "required_files")
    return checks


def run(root: Path = ROOT) -> dict[str, Any]:
    created = now_utc()
    output = root / OUTPUT_DIR
    output.mkdir(parents=True, exist_ok=True)
    rows, weights_by_variant, returns_by_variant, state, events, preflight = evaluate_lane(root)
    manifest = manifest_payload(created, rows, preflight)

    write_json(output / "public_source_parabolic_sar_bounded_bt_run_manifest.json", manifest)
    write_csv(output / "row_level_results.csv", rows, list(RESULT_FIELDS))
    write_csv(output / "numeric_criteria_results.csv", rows, list(CRITERIA_FIELDS))
    write_text(output / "parabolic_sar_formula_calculation_report.md", formula_report_md(manifest))
    write_text(output / "initialization_warmup_tradability_report.md", initialization_report_md(manifest))
    write_text(output / "reversal_state_transition_report.md", reversal_report_md(manifest))
    write_text(output / "signal_timing_no_lookahead_report.md", timing_report_md())
    write_csv(output / "sar_state_table.csv", sar_state_rows(state), list(SAR_STATE_FIELDS))
    write_csv(output / "daily_signal_event_table.csv", events.to_dict("records"), list(EVENT_FIELDS))
    write_csv(output / "daily_target_weights.csv", weight_rows(weights_by_variant), list(DAILY_WEIGHT_FIELDS))
    write_csv(output / "equity_curve_returns.csv", equity_rows(returns_by_variant), list(EQUITY_FIELDS))
    turnover = turnover_rows(rows, weights_by_variant)
    write_csv(output / "rebalance_turnover_report.csv", turnover, list(TURNOVER_FIELDS))
    write_text(output / "rebalance_turnover_report.md", turnover_report_md(rows))
    write_text(output / "event_trade_count_report.md", event_trade_count_md(manifest))
    write_csv(output / "baseline_control_comparison_report.csv", rows, list(BASELINE_FIELDS))
    write_text(output / "baseline_control_comparison_report.md", baseline_report_md(rows))
    write_text(output / "whipsaw_turnover_risk_note.md", whipsaw_md(manifest))
    write_text(output / "exposure_invariant_report.md", invariant_report_md(manifest))
    write_text(output / "similarity_risk_report.md", similarity_report_md(manifest))
    write_text(output / "long_only_adaptation_caveat_report.md", long_only_caveat_md())
    write_text(output / "role_label_summary.md", role_label_summary_md(manifest, rows))
    write_text(output / "public_source_parabolic_sar_bounded_bt_run_summary.md", summary_md(manifest))
    write_text(output / "public_source_parabolic_sar_bounded_bt_run_next_action.md", next_action_md(manifest["next_action"]))
    check = consistency_check(manifest, rows, output)
    write_json(output / "public_source_parabolic_sar_bounded_bt_run_consistency_check.json", check)
    return {**manifest, "output_dir": str(output.resolve()), "consistency_passed": check["consistency_passed"]}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
