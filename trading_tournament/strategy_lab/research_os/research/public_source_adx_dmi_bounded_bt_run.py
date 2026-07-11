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


SOURCE_ID = "adx_dmi_trend_strength_crossover"
FAMILY_ID = "equity_index_adx_dmi_trend_strength"
LANE_ID = "public_source_adx_dmi_bounded_bt_lane_v1"
DESIGN_DIR = Path("evidence") / "research_recovery" / "public_source_adx_dmi_bounded_bt_design" / "latest"
OUTPUT_DIR = Path("evidence") / "research_recovery" / "public_source_adx_dmi_bounded_bt_run" / "latest"
PATCH_OUTPUT_DIR = Path("evidence") / "research_recovery" / "public_source_adx_dmi_methodology_patch" / "latest"

EXPECTED_VARIANTS = (
    "adx_dmi_spy_bil_primary_v1",
    "adx_dmi_spy_bil_one_bar_delayed_timing_sanity_v1",
    "adx_dmi_spy_buy_hold_control_v1",
    "adx_dmi_bil_cash_control_v1",
    "adx_dmi_spy200d_frozen_control_v1",
)

NEXT_ACTION_AUDIT = "audit_public_source_adx_dmi_bounded_bt_results"
NEXT_ACTION_FIX = "fix_public_source_adx_dmi_bounded_bt_run_methodology_issue"
VALID_NEXT_ACTIONS = {NEXT_ACTION_AUDIT, NEXT_ACTION_FIX}

FORMULA_CONTRACT_VERSION = "adx_dmi_wilder_contract_v1"
DMI_ADX_PERIOD = 14
ADX_THRESHOLD = 25.0
WEIGHT_TOLERANCE = 1e-6
STANDARD_COST_ASSUMPTION = 0.0

ALLOWED_LABELS = {
    "public_source_adx_dmi_primary",
    "public_source_adx_dmi_timing_sanity",
    "public_source_adx_dmi_control_only",
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
    "formula_contract_version",
    "formula_status",
    "first_valid_di_date",
    "first_valid_adx_date",
    "dmi_adx_period",
    "adx_threshold",
    "signal_timing_convention",
    "weight_shift_convention",
    "di_crossover_count",
    "adx_confirmed_entry_count",
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
    "entry_exit_counts_reported",
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
    "di_crossover_count",
    "adx_confirmed_entry_count",
    "exit_count",
    "completed_round_trip_count",
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
STATE_FIELDS = (
    "date",
    "high",
    "low",
    "adj_close",
    "true_range",
    "positive_dm",
    "negative_dm",
    "smoothed_tr",
    "smoothed_positive_dm",
    "smoothed_negative_dm",
    "positive_di",
    "negative_di",
    "dx",
    "adx",
    "di_bullish_state",
    "di_bearish_state",
    "bullish_cross",
    "bearish_cross",
    "adx_confirmed_bullish_cross",
    "valid_signal_row",
)
EVENT_FIELDS = (
    "date",
    "event_type",
    "positive_di",
    "negative_di",
    "adx",
    "active_after_event",
    "notes",
)
DAILY_WEIGHT_FIELDS = ("date", "variant_id", "SPY", "BIL", "weight_sum", "risky_exposure")
EQUITY_FIELDS = ("date", "variant_id", "daily_return", "equity")
TURNOVER_FIELDS = ("variant_id", "variant_role", "trade_count", "turnover_proxy", "nonzero_turnover_days")

REQUIRED_FILES = (
    "public_source_adx_dmi_bounded_bt_run_manifest.json",
    "public_source_adx_dmi_bounded_bt_run_consistency_check.json",
    "row_level_results.csv",
    "numeric_criteria_results.csv",
    "adx_dmi_formula_calculation_report.md",
    "warmup_effective_start_report.md",
    "signal_timing_no_lookahead_report.md",
    "adx_dmi_state_table.csv",
    "daily_signal_event_table.csv",
    "daily_target_weights.csv",
    "equity_curve_returns.csv",
    "rebalance_turnover_report.csv",
    "rebalance_turnover_report.md",
    "corrected_signal_event_count_report.md",
    "baseline_control_comparison_report.md",
    "exposure_invariant_report.md",
    "methodology_patch_supersession_note.md",
    "similarity_risk_report.md",
    "long_only_adaptation_caveat_carry_forward.md",
    "role_label_summary.md",
    "public_source_adx_dmi_bounded_bt_run_summary.md",
    "do_not_promote_from_public_source_adx_dmi_run.md",
    "public_source_adx_dmi_bounded_bt_run_next_action.md",
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
    return read_json(root / DESIGN_DIR / "public_source_adx_dmi_bounded_bt_design_manifest.json")


def target(spy: float, bil: float) -> dict[str, float]:
    return {"SPY": float(spy), "BIL": float(bil)}


def load_spy_adjusted_ohlc(root: Path) -> pd.DataFrame:
    path = root / "data" / "cache" / "SPY.csv"
    if not path.exists():
        return pd.DataFrame()
    raw = pd.read_csv(path)
    required = ["date", "high", "low", "close", "adj_close"]
    if any(column not in raw.columns for column in required):
        return pd.DataFrame()
    dates = pd.to_datetime(raw["date"], errors="coerce")
    frame = pd.DataFrame(index=dates)
    for column in ["high", "low", "close", "adj_close"]:
        frame[column] = pd.to_numeric(raw[column], errors="coerce").to_numpy()
    frame = frame[~frame.index.isna()].sort_index()
    frame = frame[~frame.index.duplicated(keep="last")]
    return frame.dropna(subset=["high", "low", "adj_close"])


def adx_dmi_frame(spy_ohlc: pd.DataFrame, period: int = DMI_ADX_PERIOD) -> pd.DataFrame:
    frame = spy_ohlc.copy()
    high = frame["high"].astype(float)
    low = frame["low"].astype(float)
    close = frame["adj_close"].astype(float)
    previous_high = high.shift(1)
    previous_low = low.shift(1)
    previous_close = close.shift(1)
    tr = pd.concat(
        [
            high - low,
            (high - previous_close).abs(),
            (low - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    up_move = high - previous_high
    down_move = previous_low - low
    positive_dm = up_move.where((up_move > down_move) & (up_move > 0.0), 0.0)
    negative_dm = down_move.where((down_move > up_move) & (down_move > 0.0), 0.0)
    positive_dm = positive_dm.where(previous_high.notna(), np.nan)
    negative_dm = negative_dm.where(previous_low.notna(), np.nan)
    tr = tr.where(previous_close.notna(), np.nan)

    smoothed_tr = pd.Series(np.nan, index=frame.index, dtype=float)
    smoothed_positive_dm = pd.Series(np.nan, index=frame.index, dtype=float)
    smoothed_negative_dm = pd.Series(np.nan, index=frame.index, dtype=float)
    raw = pd.DataFrame({"tr": tr, "positive_dm": positive_dm, "negative_dm": negative_dm}).dropna()
    if len(raw) >= period:
        seed_index = raw.index[period - 1]
        smoothed_tr.loc[seed_index] = float(raw["tr"].iloc[:period].sum())
        smoothed_positive_dm.loc[seed_index] = float(raw["positive_dm"].iloc[:period].sum())
        smoothed_negative_dm.loc[seed_index] = float(raw["negative_dm"].iloc[:period].sum())
        prior_tr = smoothed_tr.loc[seed_index]
        prior_positive = smoothed_positive_dm.loc[seed_index]
        prior_negative = smoothed_negative_dm.loc[seed_index]
        for date, row in raw.iloc[period:].iterrows():
            prior_tr = prior_tr - (prior_tr / period) + float(row["tr"])
            prior_positive = prior_positive - (prior_positive / period) + float(row["positive_dm"])
            prior_negative = prior_negative - (prior_negative / period) + float(row["negative_dm"])
            smoothed_tr.loc[date] = prior_tr
            smoothed_positive_dm.loc[date] = prior_positive
            smoothed_negative_dm.loc[date] = prior_negative

    positive_di = 100.0 * smoothed_positive_dm / smoothed_tr.replace(0.0, np.nan)
    negative_di = 100.0 * smoothed_negative_dm / smoothed_tr.replace(0.0, np.nan)
    di_denominator = (positive_di + negative_di).replace(0.0, np.nan)
    dx = 100.0 * (positive_di - negative_di).abs() / di_denominator

    adx = pd.Series(np.nan, index=frame.index, dtype=float)
    valid_dx = dx.dropna()
    if len(valid_dx) >= period:
        seed_index = valid_dx.index[period - 1]
        prior_adx = float(valid_dx.iloc[:period].mean())
        adx.loc[seed_index] = prior_adx
        for date, value in valid_dx.iloc[period:].items():
            prior_adx = ((prior_adx * (period - 1)) + float(value)) / period
            adx.loc[date] = prior_adx

    out = pd.DataFrame(index=frame.index)
    out["high"] = high
    out["low"] = low
    out["adj_close"] = close
    out["true_range"] = tr
    out["positive_dm"] = positive_dm
    out["negative_dm"] = negative_dm
    out["smoothed_tr"] = smoothed_tr
    out["smoothed_positive_dm"] = smoothed_positive_dm
    out["smoothed_negative_dm"] = smoothed_negative_dm
    out["positive_di"] = positive_di
    out["negative_di"] = negative_di
    out["dx"] = dx
    out["adx"] = adx
    out["valid_signal_row"] = out[["positive_di", "negative_di", "adx"]].notna().all(axis=1)
    out["di_bullish_state"] = (positive_di > negative_di) & out["valid_signal_row"]
    out["di_bearish_state"] = (negative_di > positive_di) & out["valid_signal_row"]
    prior_positive_di = positive_di.shift(1)
    prior_negative_di = negative_di.shift(1)
    prior_di_valid = prior_positive_di.notna() & prior_negative_di.notna()
    out["bullish_cross"] = (
        out["valid_signal_row"]
        & prior_di_valid
        & (positive_di > negative_di)
        & (prior_positive_di <= prior_negative_di)
    )
    out["bearish_cross"] = (
        out["valid_signal_row"]
        & prior_di_valid
        & (negative_di > positive_di)
        & (prior_negative_di <= prior_positive_di)
    )
    out["adx_confirmed_bullish_cross"] = out["bullish_cross"] & (out["adx"] > ADX_THRESHOLD) & out["valid_signal_row"]
    return out


def primary_adx_targets(state: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    weights = pd.DataFrame(0.0, index=state.index, columns=["SPY", "BIL"])
    events: list[dict[str, Any]] = []
    active = False
    for date, row in state.iterrows():
        valid = bool(row.get("valid_signal_row", False))
        entry = valid and bool(row.get("adx_confirmed_bullish_cross", False))
        exit_signal = valid and bool(row.get("bearish_cross", False))
        event_type = ""
        if active and exit_signal:
            active = False
            event_type = "exit_to_bil_on_bearish_di_cross"
        elif not active and entry:
            active = True
            event_type = "entry_to_spy_on_adx_confirmed_bullish_di_cross"
        if event_type:
            events.append(
                {
                    "date": pd.Timestamp(date).date().isoformat(),
                    "event_type": event_type,
                    "positive_di": float(row["positive_di"]),
                    "negative_di": float(row["negative_di"]),
                    "adx": float(row["adx"]),
                    "active_after_event": active,
                    "notes": "source_primary_adx_dmi_event",
                }
            )
        weights.loc[date] = [1.0, 0.0] if active else [0.0, 1.0]
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
    state: pd.DataFrame,
    primary_weights: pd.DataFrame,
) -> pd.DataFrame:
    common_index = pd.DatetimeIndex(prices.index)
    if variant_id == "adx_dmi_spy_bil_primary_v1":
        return primary_weights.reindex(common_index).ffill().fillna({"SPY": 0.0, "BIL": 1.0})
    if variant_id == "adx_dmi_spy_bil_one_bar_delayed_timing_sanity_v1":
        return one_extra_bar_delayed_targets(primary_weights).reindex(common_index).ffill().fillna({"SPY": 0.0, "BIL": 1.0})
    if variant_id == "adx_dmi_spy_buy_hold_control_v1":
        return constant_weights(common_index, 1.0, 0.0)
    if variant_id == "adx_dmi_bil_cash_control_v1":
        return constant_weights(common_index, 0.0, 1.0)
    if variant_id == "adx_dmi_spy200d_frozen_control_v1":
        control = reference_spy200d_weights(prices).reindex(common_index).ffill().fillna(0.0)
        return control.reindex(columns=["SPY", "BIL"], fill_value=0.0)
    raise ValueError(f"unexpected variant_id: {variant_id}")


def holding_durations(weights: pd.DataFrame) -> list[int]:
    active = weights["SPY"] > 0.5
    durations: list[int] = []
    current = 0
    for is_active in active:
        if bool(is_active):
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
    return {
        "di_crossover_count": int(
            state["bullish_cross"].fillna(False).sum() + state["bearish_cross"].fillna(False).sum()
        ),
        "adx_confirmed_entry_count": entries,
        "exit_count": exits,
        "completed_round_trip_count": min(entries, exits),
        "average_holding_duration": float(np.mean(durations)) if durations else 0.0,
        "median_holding_duration": float(np.median(durations)) if durations else 0.0,
    }


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


def state_rows(state: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for date, row in state.iterrows():
        payload = {"date": pd.Timestamp(date).date().isoformat()}
        for field in STATE_FIELDS:
            if field == "date":
                continue
            value = row.get(field)
            if isinstance(value, (bool, np.bool_)):
                payload[field] = bool(value)
            elif pd.isna(value):
                payload[field] = ""
            else:
                payload[field] = float(value) if isinstance(value, (int, float, np.floating)) else value
        rows.append(payload)
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
    signal_counts: dict[str, Any],
    first_valid_di: str,
    first_valid_adx: str,
) -> dict[str, Any]:
    bil_total = controls["adx_dmi_bil_cash_control_v1"]["total_return"]
    spy_mdd = controls["adx_dmi_spy_buy_hold_control_v1"]["max_drawdown"]
    spy_proxy = controls["adx_dmi_spy_buy_hold_control_v1"]["return_drawdown_proxy"]
    same_window_vs_bil = row_metrics["total_return"] - bil_total
    excess_after_cost = same_window_vs_bil - STANDARD_COST_ASSUMPTION
    drawdown_reduction = (
        (abs(spy_mdd) - abs(row_metrics["max_drawdown"])) / abs(spy_mdd)
        if finite(spy_mdd) and spy_mdd < 0
        else float("nan")
    )
    corr_spy = safe_corr(daily, control_returns["adx_dmi_spy_buy_hold_control_v1"])
    corr_spy200d = safe_corr(daily, control_returns["adx_dmi_spy200d_frozen_control_v1"])
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
    primary_exposure_pass = is_primary and 0.0500 <= row_metrics["average_spy_exposure_share"] <= 0.8500
    primary_duplicate_pass = is_primary and (not finite(duplicate_reference) or duplicate_reference < 0.90)
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
        "formula_contract_version": FORMULA_CONTRACT_VERSION,
        "formula_status": "frozen_wilder_adx_dmi_contract_v1_exact",
        "first_valid_di_date": first_valid_di,
        "first_valid_adx_date": first_valid_adx,
        "dmi_adx_period": DMI_ADX_PERIOD,
        "adx_threshold": ADX_THRESHOLD,
        "signal_timing_convention": row["signal_timing"],
        "weight_shift_convention": "target weights produced after daily close and applied with returns_from_weights one-bar shift",
        **signal_counts,
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
        "entry_exit_counts_reported": True,
        "timing_sanity_context_only": is_timing,
        "numeric_criteria_pass": numeric_pass,
        "promotion_eligibility": False,
        "paper_forward_eligibility": False,
        "candidate_exhaustive_eligibility": False,
        "methodology_notes": "local-cache adjusted-OHLC frozen ADX/DMI formula shifted-weight bounded bt lane; diagnostic non-promotable evidence",
    }


def evaluate_lane(
    root: Path,
) -> tuple[list[dict[str, Any]], dict[str, pd.DataFrame], dict[str, pd.Series], pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    rows = design_rows(root)
    design = design_manifest(root)
    prices = load_local_price_frame(root).sort_index()
    if not prices.empty:
        prices = prices.loc[prices[["SPY", "BIL"]].notna().all(axis=1), ["SPY", "BIL"]].copy()
    spy_ohlc = load_spy_adjusted_ohlc(root)
    full_state = adx_dmi_frame(spy_ohlc) if not spy_ohlc.empty else pd.DataFrame()
    state = full_state.reindex(prices.index) if not prices.empty and not full_state.empty else pd.DataFrame()
    data_blocker = ""
    if len(rows) != len(EXPECTED_VARIANTS) or {row["variant_id"] for row in rows} != set(EXPECTED_VARIANTS):
        data_blocker = "design_variant_set_mismatch"
    elif prices.empty:
        data_blocker = "missing_spy_bil_local_adjusted_close_cache"
    elif spy_ohlc.empty:
        data_blocker = "missing_spy_adjusted_ohlc_cache"
    elif state[["positive_di", "negative_di", "adx"]].dropna().empty:
        data_blocker = "indicator_warmup_invalid_no_valid_adx_dmi_rows"

    weights_by_variant: dict[str, pd.DataFrame] = {}
    returns_by_variant: dict[str, pd.Series] = {}
    metrics_by_variant: dict[str, dict[str, Any]] = {}
    event_table = pd.DataFrame(columns=list(EVENT_FIELDS))
    if not data_blocker:
        primary_weights, event_table = primary_adx_targets(state)
        for row in rows:
            variant_id = row["variant_id"]
            weights = build_weights(variant_id, prices, state, primary_weights)
            daily = returns_from_weights(prices, weights).rename(variant_id)
            weights_by_variant[variant_id] = weights
            returns_by_variant[variant_id] = daily
            metrics_by_variant[variant_id] = metrics(daily, weights)

    first_valid_di = ""
    first_valid_adx = ""
    if not full_state.empty:
        di_valid = full_state[["positive_di", "negative_di"]].dropna()
        adx_valid = full_state["adx"].dropna()
        first_valid_di = di_valid.index.min().date().isoformat() if not di_valid.empty else ""
        first_valid_adx = adx_valid.index.min().date().isoformat() if not adx_valid.empty else ""

    result_rows: list[dict[str, Any]] = []
    if not data_blocker:
        for row in rows:
            counts = signal_count_summary(state, weights_by_variant[row["variant_id"]])
            if row["variant_role"] == "control":
                counts = {
                    "di_crossover_count": 0,
                    "adx_confirmed_entry_count": 0,
                    "exit_count": 0,
                    "completed_round_trip_count": 0,
                    "average_holding_duration": 0.0,
                    "median_holding_duration": 0.0,
                }
            result_rows.append(
                result_for_row(
                    row,
                    metrics_by_variant[row["variant_id"]],
                    returns_by_variant[row["variant_id"]],
                    metrics_by_variant,
                    returns_by_variant,
                    counts,
                    first_valid_di,
                    first_valid_adx,
                )
            )

    valid_signal_rows = state[["positive_di", "negative_di", "adx"]].dropna() if not state.empty else pd.DataFrame()
    effective_start = max(
        [date for date in (prices.index.min().date().isoformat() if not prices.empty else "", first_valid_adx) if date],
        default="",
    )
    preflight = {
        "source_design_run_ready": design.get("run_readiness_decision") == "public_source_adx_dmi_bounded_bt_design_run_ready",
        "source_design_next_action_correct": design.get("next_action") == "run_public_source_adx_dmi_bounded_bt_lane",
        "formula_contract_version": design.get("formula_contract_version", ""),
        "formula_contract_complete": design.get("formula_contract_complete") is True,
        "design_row_count": len(rows),
        "evaluated_variant_ids": [row["variant_id"] for row in result_rows],
        "uses_local_cache_only": True,
        "provider_download_required": False,
        "intraday_data_required": False,
        "data_blocker": data_blocker,
        "effective_start_date": effective_start,
        "effective_end_date": prices.index.max().date().isoformat() if not prices.empty else "",
        "first_valid_di_date": first_valid_di,
        "first_valid_adx_date": first_valid_adx,
        "valid_signal_row_count": int(len(valid_signal_rows)),
        "raw_bullish_directional_state_day_count": int(state["di_bullish_state"].fillna(False).sum())
        if not state.empty
        else 0,
        "raw_bearish_directional_state_day_count": int(state["di_bearish_state"].fillna(False).sum())
        if not state.empty
        else 0,
        "bullish_cross_count": int(state["bullish_cross"].fillna(False).sum()) if not state.empty else 0,
        "bearish_cross_count": int(state["bearish_cross"].fillna(False).sum()) if not state.empty else 0,
        "adx_confirmed_entry_signal_count": int(state["adx_confirmed_bullish_cross"].fillna(False).sum())
        if not state.empty
        else 0,
        "event_count": int(len(event_table)),
    }
    return result_rows, weights_by_variant, returns_by_variant, state, event_table, preflight


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
        and preflight["formula_contract_complete"]
        and preflight["formula_contract_version"] == FORMULA_CONTRACT_VERSION
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
        "public_source_adx_dmi_bounded_bt_lane_run": True,
        "source_id": SOURCE_ID,
        "family_id": FAMILY_ID,
        "lane_id": LANE_ID,
        "source_design_run_ready": preflight["source_design_run_ready"],
        "source_design_next_action_correct": preflight["source_design_next_action_correct"],
        "formula_contract_version": FORMULA_CONTRACT_VERSION,
        "formula_contract_complete": preflight["formula_contract_complete"],
        "formula_contract_used_exactly": True,
        "indicator_formula_implemented": True,
        "indicator_formula": "frozen Wilder ADX/DMI contract using local adjusted SPY OHLC",
        "indicator_parameters_source_backed": True,
        "dmi_adx_period": DMI_ADX_PERIOD,
        "adx_threshold": ADX_THRESHOLD,
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
        "first_valid_di_date": preflight["first_valid_di_date"],
        "first_valid_adx_date": preflight["first_valid_adx_date"],
        "effective_start_date_after_alignment_and_warmup": preflight["effective_start_date"],
        "effective_end_date": preflight["effective_end_date"],
        "valid_signal_row_count": preflight["valid_signal_row_count"],
        "methodology_patch_applied": True,
        "methodology_patch_id": "adx_dmi_true_crossover_event_patch_v1",
        "previous_adx_dmi_run_superseded": True,
        "previous_audit_decision": "public_source_adx_dmi_results_needs_patch",
        "prior_cross_flags_were_directional_state_days": True,
        "cross_fields_are_true_transition_events": True,
        "raw_bullish_directional_state_day_count": preflight["raw_bullish_directional_state_day_count"],
        "raw_bearish_directional_state_day_count": preflight["raw_bearish_directional_state_day_count"],
        "true_bullish_crossover_event_count": preflight["bullish_cross_count"],
        "true_bearish_crossover_event_count": preflight["bearish_cross_count"],
        "bullish_cross_count": preflight["bullish_cross_count"],
        "bearish_cross_count": preflight["bearish_cross_count"],
        "adx_confirmed_entry_signal_count": preflight["adx_confirmed_entry_signal_count"],
        "event_count": preflight["event_count"],
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
        "adx_alone_creates_exposure": False,
        "invalid_indicator_rows_signal_active": False,
        "threshold_sweep_created": False,
        "optimization_run": False,
        "other_indicators_added": False,
        "spy200d_added_as_source_filter": False,
        "moving_average_filters_added": False,
        "volatility_filters_added": False,
        "stop_loss_or_profit_target_added": False,
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
        "similarity_hit_preserved": True,
        "similarity_hit_count": 12,
        "specific_duplicate_or_do_not_retest_match_discovered": False,
        "long_only_adaptation_caveat_carried_forward": True,
        "outputs_diagnostic_only": True,
        "outputs_non_promotable": True,
        "candidate_exhaustive_ready": False,
        "paper_demo_eligible": False,
        "results_interpretable": interpretable,
        "usable_diagnostic_evidence": interpretable,
        "next_action": next_action,
    }


def formula_report_md(state: pd.DataFrame, preflight: dict[str, Any]) -> str:
    return f"""# ADX/DMI Formula Calculation Report

Formula contract version: `{FORMULA_CONTRACT_VERSION}`

Formula status: `frozen_wilder_adx_dmi_contract_v1_exact`

Implementation:

- Uses completed daily adjusted SPY OHLC from local cache only.
- Previous close is prior completed adjusted close.
- `TR = max(high - low, abs(high - previous_close), abs(low - previous_close))`.
- `up_move = high - previous_high`.
- `down_move = previous_low - low`.
- `+DM = up_move if up_move > down_move and up_move > 0 else 0`.
- `-DM = down_move if down_move > up_move and down_move > 0 else 0`.
- Wilder smoothing period is `{DMI_ADX_PERIOD}`.
- Initial smoothed TR, +DM, and -DM use rolling sum of first `{DMI_ADX_PERIOD}` raw components.
- Smoothed update is `next_smoothed = prior_smoothed - (prior_smoothed / 14) + current_raw_component`.
- `+DI = 100 * smoothed(+DM) / smoothed(TR)`.
- `-DI = 100 * smoothed(-DM) / smoothed(TR)`.
- `DX = 100 * abs(+DI - -DI) / (+DI + -DI)`.
- Initial ADX is arithmetic mean of first `{DMI_ADX_PERIOD}` valid DX values.
- ADX update is `ADX_t = ((ADX_{{t-1}} * 13) + DX_t) / 14`.
- Zero denominators produce NaN, not infinity.
- Invalid ADX/+DI/-DI rows are never signal-active.

Valid signal rows: `{preflight['valid_signal_row_count']}`

Bullish DI crosses: `{preflight['bullish_cross_count']}`

Bearish DI crosses: `{preflight['bearish_cross_count']}`

ADX-confirmed entry signals: `{preflight['adx_confirmed_entry_signal_count']}`

No external ADX/DMI library, provider download, scraping, intraday data, or optimized parameter setting was used.
"""


def warmup_report_md(preflight: dict[str, Any]) -> str:
    return f"""# Warmup / Effective Start Report

First valid +DI/-DI date: `{preflight['first_valid_di_date']}`

First valid ADX date: `{preflight['first_valid_adx_date']}`

Effective start date after SPY/BIL alignment and indicator warmup: `{preflight['effective_start_date']}`

Effective end date: `{preflight['effective_end_date']}`

Rows before valid +DI, -DI, and ADX hold BIL/cash and cannot generate entries/exits.
"""


def timing_report_md(rows: list[dict[str, Any]]) -> str:
    primary = next(row for row in rows if row["variant_role"] == "source_primary")
    timing = next(row for row in rows if row["variant_role"] == "timing_sanity")
    return f"""# Signal Timing / No-Lookahead Report

Primary row: `{primary['variant_id']}`

- Computes ADX(14), +DI(14), and -DI(14) through the completed daily close.
- Produces target weights after the signal close.
- Uses `returns_from_weights`, which applies target weights with a one-bar close-to-close shift.
- ADX alone never creates bullish exposure.
- Invalid indicator rows hold BIL/cash.
- Primary row enters only on an ADX-confirmed bullish +DI/-DI cross.
- Primary row exits on bearish -DI/+DI cross.
- SPY_200d remains a control only, not a source filter.

Timing-sanity row: `{timing['variant_id']}`

- Uses the same signal and exit logic.
- Delays target weights one additional trading day before the standard shifted return convention.
- Timing-sanity row is context only and is not an optimized variant.

Primary ADX-confirmed entry count: `{primary['adx_confirmed_entry_count']}`

Primary exit count: `{primary['exit_count']}`

Primary completed round-trip count: `{primary['completed_round_trip_count']}`
"""


def turnover_report_md(rows: list[dict[str, Any]]) -> str:
    lines = ["# Rebalance / Turnover Report", ""]
    for row in rows:
        lines.append(
            f"- `{row['variant_id']}`: trade count `{row['trade_count']}`, turnover proxy `{float(row['turnover_proxy']):.6f}`"
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


def corrected_signal_event_count_report_md(manifest: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    primary = next((row for row in rows if row["variant_role"] == "source_primary"), {})
    return f"""# Corrected Signal / Event Count Report

Methodology patch: `{manifest['methodology_patch_id']}`

Previous audit decision superseded: `{manifest['previous_audit_decision']}`

The corrected `bullish_cross` and `bearish_cross` fields now represent true transition events, not every directional-state day.

- Raw bullish directional-state days: `{manifest['raw_bullish_directional_state_day_count']}`
- Raw bearish directional-state days: `{manifest['raw_bearish_directional_state_day_count']}`
- True bullish crossover events: `{manifest['true_bullish_crossover_event_count']}`
- True bearish crossover events: `{manifest['true_bearish_crossover_event_count']}`
- ADX-confirmed bullish crossover events: `{manifest['adx_confirmed_entry_signal_count']}`
- Primary exposure-change entries: `{primary.get('adx_confirmed_entry_count', 'not_available')}`
- Primary exposure-change exits: `{primary.get('exit_count', 'not_available')}`
- Primary completed round trips: `{primary.get('completed_round_trip_count', 'not_available')}`

Invalid warmup rows cannot generate cross events. ADX alone cannot generate exposure.
"""


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


def supersession_note_md(manifest: dict[str, Any]) -> str:
    return f"""# ADX/DMI Methodology Supersession Note

The prior ADX/DMI bounded run evidence was audited and failed with decision `{manifest['previous_audit_decision']}`.

This corrected run supersedes that failed evidence for diagnostic interpretation because it applies:

`{manifest['methodology_patch_id']}`

The formula contract, ADX/DMI period, ADX threshold, row set, instruments, controls, timing-sanity role, and numeric criteria thresholds were not changed.

This packet remains diagnostic and non-promotable.
"""


def similarity_report_md(manifest: dict[str, Any]) -> str:
    return f"""# Similarity Risk Report

Similarity hit count preserved from intake: `{manifest['similarity_hit_count']}`

Specific duplicate/do-not-retest match discovered by this run: `{manifest['specific_duplicate_or_do_not_retest_match_discovered']}`

Design treatment preserved:

- Do not treat public-source presence or this run as proof of profitability.
- Do not add SPY_200d as a source filter.
- Do not add thresholds, alternate periods, stops, profit targets, alternate exits, or other indicators.
- Keep this output diagnostic and non-promotable.
"""


def long_only_report_md() -> str:
    return """# Long-Only Adaptation Caveat Carry-Forward

The public ADX/DMI materials can discuss bullish and bearish directional interpretation. This bounded run uses only the frozen long-only SPY/BIL adaptation:

- Bullish ADX-confirmed +DI/-DI cross may map to SPY exposure.
- Bearish -DI dominance, inactive state, or invalid indicator rows map to BIL/cash.
- Bearish interpretation never maps to short SPY, inverse ETFs, options, futures, margin, leverage, intraday execution, paper orders, live orders, broker/API calls, or real-money recommendations.
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


def summary_md(manifest: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    primary = next((row for row in rows if row["variant_role"] == "source_primary"), {})
    timing = next((row for row in rows if row["variant_role"] == "timing_sanity"), {})
    return f"""# Public Source ADX/DMI Bounded bt Run

Lane ID: `{manifest['lane_id']}`

Formula contract: `{manifest['formula_contract_version']}`

Rows planned/evaluated: `{manifest['variant_count_planned']} / {manifest['variant_count_evaluated']}`

Rows by role: primary `{manifest['primary_source_row_count']}`, timing-sanity `{manifest['timing_sanity_row_count']}`, controls `{manifest['control_row_count']}`

Data-blocked rows: `{manifest['data_blocked_row_count']}`

First valid +DI/-DI date: `{manifest['first_valid_di_date']}`

First valid ADX date: `{manifest['first_valid_adx_date']}`

Effective start/end: `{manifest['effective_start_date_after_alignment_and_warmup']}` to `{manifest['effective_end_date']}`

Primary row numeric criteria pass: `{manifest['primary_row_numeric_criteria_pass']}`

Timing-sanity context only: `{manifest['timing_sanity_context_only']}`

Control rows evaluated: `{manifest['control_row_count_evaluated']}`

Invariant failures: `{manifest['invariant_failure_count']}`

Event counts: bullish crosses `{manifest['bullish_cross_count']}`, bearish crosses `{manifest['bearish_cross_count']}`, ADX-confirmed entries `{manifest['adx_confirmed_entry_signal_count']}`

Raw directional-state days: bullish `{manifest['raw_bullish_directional_state_day_count']}`, bearish `{manifest['raw_bearish_directional_state_day_count']}`

Methodology patch applied: `{manifest['methodology_patch_id']}`

Similarity-risk status: hit count `{manifest['similarity_hit_count']}` preserved; duplicate/do-not-retest discovered `{manifest['specific_duplicate_or_do_not_retest_match_discovered']}`

Long-only caveat carried forward: `{manifest['long_only_adaptation_caveat_carried_forward']}`

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
    return """# Do Not Promote From Public Source ADX/DMI Run

This packet is diagnostic historical research evidence only.

It creates no promotion-review candidate, candidate_exhaustive candidate, paper/demo candidate, paper/demo activation, broker/live action, or real-money recommendation.
"""


def next_action_md(next_action: str) -> str:
    return f"""# Public Source ADX/DMI Bounded bt Run Next Action

Exact next action:

`{next_action}`

Do not execute the next action in this task.
"""


def methodology_patch_manifest(manifest: dict[str, Any], output: Path, run_output: Path) -> dict[str, Any]:
    return {
        "created_utc": manifest["created_utc"],
        "evidence_path": str(output.resolve()),
        "corrected_run_evidence_path": str(run_output.resolve()),
        "methodology_patch_only": True,
        "source_id": SOURCE_ID,
        "family_id": FAMILY_ID,
        "lane_id": LANE_ID,
        "methodology_patch_id": manifest["methodology_patch_id"],
        "previous_audit_decision": manifest["previous_audit_decision"],
        "previous_adx_dmi_run_superseded": manifest["previous_adx_dmi_run_superseded"],
        "formula_contract_version": manifest["formula_contract_version"],
        "formula_contract_changed": False,
        "dmi_adx_period": manifest["dmi_adx_period"],
        "adx_threshold": manifest["adx_threshold"],
        "thresholds_changed": False,
        "variant_count_planned": manifest["variant_count_planned"],
        "variant_count_evaluated": manifest["variant_count_evaluated"],
        "approved_variant_ids": manifest["approved_variant_ids"],
        "new_variants_created": False,
        "new_instruments_added": False,
        "filters_or_exits_added": False,
        "raw_bullish_directional_state_day_count": manifest["raw_bullish_directional_state_day_count"],
        "raw_bearish_directional_state_day_count": manifest["raw_bearish_directional_state_day_count"],
        "true_bullish_crossover_event_count": manifest["true_bullish_crossover_event_count"],
        "true_bearish_crossover_event_count": manifest["true_bearish_crossover_event_count"],
        "adx_confirmed_entry_signal_count": manifest["adx_confirmed_entry_signal_count"],
        "cross_fields_are_true_transition_events": manifest["cross_fields_are_true_transition_events"],
        "exposure_invariant_passed": manifest["exposure_invariant_passed"],
        "outputs_diagnostic_only": True,
        "outputs_non_promotable": True,
        "provider_download": False,
        "intraday_data_used": False,
        "public_source_scraped": False,
        "strategy_discovery_run": False,
        "candidate_exhaustive_run": False,
        "promotion_candidates_created": False,
        "paper_forward_activation": False,
        "broker_api_called": False,
        "live_orders": False,
        "real_money_recommendation": False,
        "next_action": manifest["next_action"],
    }


def methodology_patch_summary_md(patch: dict[str, Any]) -> str:
    return f"""# ADX/DMI Methodology Patch Summary

Patch ID: `{patch['methodology_patch_id']}`

The audit-failed ADX/DMI run is superseded by the corrected run evidence at:

`{patch['corrected_run_evidence_path']}`

What changed:

- `bullish_cross` now means a true transition event from `+DI <= -DI` to `+DI > -DI`.
- `bearish_cross` now means a true transition event from `-DI <= +DI` to `-DI > +DI`.
- `adx_confirmed_bullish_cross` now requires a true bullish crossover and `ADX > 25`.
- Directional-state days are reported separately from crossover events.

What did not change:

- Formula contract: `{patch['formula_contract_version']}`
- ADX/DMI period: `{patch['dmi_adx_period']}`
- ADX threshold: `{patch['adx_threshold']}`
- Approved row count: `{patch['variant_count_evaluated']}`
- Instruments, controls, criteria thresholds, no-lookahead convention, and non-promotable status.

Corrected counts:

- Raw bullish state days: `{patch['raw_bullish_directional_state_day_count']}`
- Raw bearish state days: `{patch['raw_bearish_directional_state_day_count']}`
- True bullish crossover events: `{patch['true_bullish_crossover_event_count']}`
- True bearish crossover events: `{patch['true_bearish_crossover_event_count']}`
- ADX-confirmed bullish crossover events: `{patch['adx_confirmed_entry_signal_count']}`

Exact next action: `{patch['next_action']}`
"""


def methodology_patch_count_report_md(patch: dict[str, Any]) -> str:
    return f"""# Corrected ADX/DMI Count Report

Directional states and crossover events are now separate:

| Count | Value |
| --- | ---: |
| Raw bullish directional-state days | `{patch['raw_bullish_directional_state_day_count']}` |
| Raw bearish directional-state days | `{patch['raw_bearish_directional_state_day_count']}` |
| True bullish crossover events | `{patch['true_bullish_crossover_event_count']}` |
| True bearish crossover events | `{patch['true_bearish_crossover_event_count']}` |
| ADX-confirmed bullish crossover events | `{patch['adx_confirmed_entry_signal_count']}` |

Patch status: cross fields are true transition events = `{patch['cross_fields_are_true_transition_events']}`.
"""


def methodology_patch_consistency_check(patch: dict[str, Any], output: Path) -> dict[str, Any]:
    required = {
        "adx_dmi_methodology_patch_manifest.json": (output / "adx_dmi_methodology_patch_manifest.json").exists(),
        "adx_dmi_methodology_patch_summary.md": (output / "adx_dmi_methodology_patch_summary.md").exists(),
        "corrected_signal_event_count_report.md": (output / "corrected_signal_event_count_report.md").exists(),
        "adx_dmi_methodology_patch_next_action.md": (output / "adx_dmi_methodology_patch_next_action.md").exists(),
    }
    checks = {
        "methodology_patch_only": patch["methodology_patch_only"] is True,
        "correct_lane": patch["source_id"] == SOURCE_ID and patch["family_id"] == FAMILY_ID and patch["lane_id"] == LANE_ID,
        "formula_contract_unchanged": patch["formula_contract_changed"] is False
        and patch["formula_contract_version"] == FORMULA_CONTRACT_VERSION,
        "thresholds_unchanged": patch["thresholds_changed"] is False
        and patch["dmi_adx_period"] == DMI_ADX_PERIOD
        and patch["adx_threshold"] == ADX_THRESHOLD,
        "exact_variant_set_preserved": patch["variant_count_evaluated"] == 5
        and patch["approved_variant_ids"] == list(EXPECTED_VARIANTS),
        "cross_events_separate_from_state_days": patch["cross_fields_are_true_transition_events"] is True
        and patch["true_bullish_crossover_event_count"] < patch["raw_bullish_directional_state_day_count"]
        and patch["true_bearish_crossover_event_count"] < patch["raw_bearish_directional_state_day_count"],
        "no_forbidden_actions": patch["provider_download"] is False
        and patch["intraday_data_used"] is False
        and patch["public_source_scraped"] is False
        and patch["strategy_discovery_run"] is False
        and patch["candidate_exhaustive_run"] is False
        and patch["promotion_candidates_created"] is False
        and patch["paper_forward_activation"] is False
        and patch["broker_api_called"] is False
        and patch["live_orders"] is False
        and patch["real_money_recommendation"] is False,
        "outputs_remain_diagnostic": patch["outputs_diagnostic_only"] is True and patch["outputs_non_promotable"] is True,
        "required_files_present": all(required.values()),
    }
    return {**checks, "required_files": required, "consistency_passed": all(checks.values())}


def write_methodology_patch_packet(manifest: dict[str, Any], run_output: Path, root: Path = ROOT) -> None:
    patch_output = root / PATCH_OUTPUT_DIR
    patch_output.mkdir(parents=True, exist_ok=True)
    patch = methodology_patch_manifest(manifest, patch_output, run_output)
    write_json(patch_output / "adx_dmi_methodology_patch_manifest.json", patch)
    write_text(patch_output / "adx_dmi_methodology_patch_summary.md", methodology_patch_summary_md(patch))
    write_text(patch_output / "corrected_signal_event_count_report.md", methodology_patch_count_report_md(patch))
    write_text(patch_output / "adx_dmi_methodology_patch_next_action.md", next_action_md(patch["next_action"]))
    check = methodology_patch_consistency_check(patch, patch_output)
    write_json(patch_output / "adx_dmi_methodology_patch_consistency_check.json", check)


def consistency_check(manifest: dict[str, Any], rows: list[dict[str, Any]], output: Path) -> dict[str, Any]:
    required = {name: (output / name).exists() for name in REQUIRED_FILES}
    required["public_source_adx_dmi_bounded_bt_run_consistency_check.json"] = True
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
        "formula_contract_used": manifest["formula_contract_complete"] is True
        and manifest["formula_contract_version"] == FORMULA_CONTRACT_VERSION
        and manifest["formula_contract_used_exactly"] is True,
        "source_backed_params": manifest["indicator_parameters_source_backed"] is True
        and manifest["parameters_tuned"] is False
        and manifest["dmi_adx_period"] == 14
        and manifest["adx_threshold"] == 25.0,
        "signal_timing_no_lookahead": manifest["signal_timing_no_lookahead"] is True
        and manifest["adx_alone_creates_exposure"] is False
        and manifest["invalid_indicator_rows_signal_active"] is False
        and manifest["cross_fields_are_true_transition_events"] is True,
        "one_timing_sanity_only": manifest["one_extra_bar_delayed_timing_sanity_only"] is True,
        "no_sweep_or_optimization": manifest["threshold_sweep_created"] is False
        and manifest["optimization_run"] is False
        and manifest["other_indicators_added"] is False
        and manifest["spy200d_added_as_source_filter"] is False
        and manifest["moving_average_filters_added"] is False
        and manifest["volatility_filters_added"] is False
        and manifest["stop_loss_or_profit_target_added"] is False
        and manifest["alternate_exits_added"] is False,
        "local_cache_only": manifest["uses_local_cache_only"] is True,
        "no_provider_intraday": manifest["provider_download"] is False and manifest["intraday_data_used"] is False,
        "no_design_change_or_new_instruments": manifest["bounded_bt_design_changed"] is False
        and manifest["new_instruments_added"] is False,
        "similarity_hit_preserved": manifest["similarity_hit_preserved"] is True
        and manifest["similarity_hit_count"] == 12,
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
        and manifest["public_strategy_list_ingested"] is False,
        "exposure_invariants_pass": manifest["exposure_invariant_passed"] is True
        and manifest["max_daily_exposure"] <= 1.000001
        and manifest["max_daily_weight_sum"] <= 1.000001,
        "methodology_patch_applied": manifest["methodology_patch_applied"] is True
        and manifest["previous_adx_dmi_run_superseded"] is True
        and manifest["true_bullish_crossover_event_count"] < manifest["raw_bullish_directional_state_day_count"]
        and manifest["true_bearish_crossover_event_count"] < manifest["raw_bearish_directional_state_day_count"],
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
    rows, weights_by_variant, returns_by_variant, state, events, preflight = evaluate_lane(root)
    manifest = manifest_payload(created, output, rows, preflight)

    write_json(output / "public_source_adx_dmi_bounded_bt_run_manifest.json", manifest)
    write_csv(output / "row_level_results.csv", rows, list(RESULT_FIELDS))
    write_csv(output / "numeric_criteria_results.csv", rows, list(CRITERIA_FIELDS))
    write_text(output / "adx_dmi_formula_calculation_report.md", formula_report_md(state, preflight))
    write_text(output / "warmup_effective_start_report.md", warmup_report_md(preflight))
    write_text(output / "signal_timing_no_lookahead_report.md", timing_report_md(rows))
    write_csv(output / "adx_dmi_state_table.csv", state_rows(state), list(STATE_FIELDS))
    write_csv(output / "daily_signal_event_table.csv", events.to_dict("records"), list(EVENT_FIELDS))
    write_csv(output / "daily_target_weights.csv", weight_rows(weights_by_variant), list(DAILY_WEIGHT_FIELDS))
    write_csv(output / "equity_curve_returns.csv", equity_rows(returns_by_variant), list(EQUITY_FIELDS))
    turnover = turnover_rows(rows, weights_by_variant)
    write_csv(output / "rebalance_turnover_report.csv", turnover, list(TURNOVER_FIELDS))
    write_text(output / "rebalance_turnover_report.md", turnover_report_md(rows))
    write_text(output / "corrected_signal_event_count_report.md", corrected_signal_event_count_report_md(manifest, rows))
    write_text(output / "baseline_control_comparison_report.md", baseline_report_md(rows))
    write_text(output / "exposure_invariant_report.md", invariant_report_md(manifest))
    write_text(output / "methodology_patch_supersession_note.md", supersession_note_md(manifest))
    write_text(output / "similarity_risk_report.md", similarity_report_md(manifest))
    write_text(output / "long_only_adaptation_caveat_carry_forward.md", long_only_report_md())
    write_text(output / "role_label_summary.md", role_label_summary_md(manifest, rows))
    write_text(output / "public_source_adx_dmi_bounded_bt_run_summary.md", summary_md(manifest, rows))
    write_text(output / "do_not_promote_from_public_source_adx_dmi_run.md", do_not_promote_md())
    write_text(output / "public_source_adx_dmi_bounded_bt_run_next_action.md", next_action_md(manifest["next_action"]))
    check = consistency_check(manifest, rows, output)
    write_json(output / "public_source_adx_dmi_bounded_bt_run_consistency_check.json", check)
    write_methodology_patch_packet(manifest, output, root)
    return {**manifest, "output_dir": str(output.resolve()), "consistency_passed": check["consistency_passed"]}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
