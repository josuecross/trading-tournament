from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd


TRADING_DAYS = 252

INVALID_INSUFFICIENT_CALIBRATION_HISTORY = "INVALID_INSUFFICIENT_CALIBRATION_HISTORY"
INVALID_DEGENERATE_VOLATILITY_CALIBRATION = "INVALID_DEGENERATE_VOLATILITY_CALIBRATION"
INVALID_NONFINITE_VOLATILITY_TARGET = "INVALID_NONFINITE_VOLATILITY_TARGET"
INVALID_NON_DYNAMIC_VOLATILITY_SCALER = "INVALID_NON_DYNAMIC_VOLATILITY_SCALER"
PASS_DYNAMIC_VOLATILITY_SCALER = "PASS_DYNAMIC_VOLATILITY_SCALER"


@dataclass
class VolatilityCalibration:
    status: str
    invalidity_code: str
    evaluation_start: str
    calibration_start: str
    calibration_end: str
    selected_return_start: str
    selected_return_end: str
    valid_return_count_available: int
    selected_return_count: int
    rolling_volatility_count: int
    positive_rolling_volatility_count: int
    target_volatility: float
    selected_returns: pd.Series
    rolling_volatility: pd.Series

    def to_record(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "invalidity_code": self.invalidity_code,
            "evaluation_start": self.evaluation_start,
            "calibration_start": self.calibration_start,
            "calibration_end": self.calibration_end,
            "selected_return_start": self.selected_return_start,
            "selected_return_end": self.selected_return_end,
            "valid_return_count_available": self.valid_return_count_available,
            "selected_return_count": self.selected_return_count,
            "rolling_volatility_count": self.rolling_volatility_count,
            "positive_rolling_volatility_count": self.positive_rolling_volatility_count,
            "target_volatility": self.target_volatility,
        }


def _empty_calibration(
    *,
    code: str,
    evaluation_start: pd.Timestamp,
    calibration_frame: pd.DataFrame,
    available_returns: int,
) -> VolatilityCalibration:
    dates = pd.to_datetime(calibration_frame["date"]) if not calibration_frame.empty else pd.Series(dtype="datetime64[ns]")
    start = dates.min().date().isoformat() if len(dates) else ""
    end = dates.max().date().isoformat() if len(dates) else ""
    return VolatilityCalibration(
        status="invalid",
        invalidity_code=code,
        evaluation_start=evaluation_start.date().isoformat(),
        calibration_start=start,
        calibration_end=end,
        selected_return_start="",
        selected_return_end="",
        valid_return_count_available=int(available_returns),
        selected_return_count=0,
        rolling_volatility_count=0,
        positive_rolling_volatility_count=0,
        target_volatility=np.nan,
        selected_returns=pd.Series(dtype=float),
        rolling_volatility=pd.Series(dtype=float),
    )


def calibrate_volatility_target_from_equity(
    equity_curve: pd.DataFrame,
    *,
    evaluation_start: str | pd.Timestamp,
    return_count: int = 252,
    lookback: int = 63,
    min_rolling_volatility_estimates: int = 126,
    min_target_volatility: float = 1e-8,
) -> VolatilityCalibration:
    frame = equity_curve.copy()
    frame["date"] = pd.to_datetime(frame["date"])
    frame = frame.sort_values("date")
    eval_start = pd.Timestamp(evaluation_start)
    calibration_frame = frame[frame["date"] < eval_start].copy()
    returns = calibration_frame["equity"].astype(float).pct_change()
    returns.index = calibration_frame["date"]
    finite_returns = returns[np.isfinite(returns)]
    available_returns = int(len(finite_returns))
    if available_returns < return_count:
        return _empty_calibration(
            code=INVALID_INSUFFICIENT_CALIBRATION_HISTORY,
            evaluation_start=eval_start,
            calibration_frame=calibration_frame,
            available_returns=available_returns,
        )

    selected = finite_returns.tail(return_count).copy()
    rolling = selected.rolling(window=lookback, min_periods=lookback).std() * np.sqrt(TRADING_DAYS)
    finite_rolling = rolling[np.isfinite(rolling)]
    positive = finite_rolling[finite_rolling > 0.0]
    if len(finite_rolling) < min_rolling_volatility_estimates:
        code = INVALID_INSUFFICIENT_CALIBRATION_HISTORY
        target = np.nan
    elif positive.empty:
        code = INVALID_DEGENERATE_VOLATILITY_CALIBRATION
        target = 0.0
    else:
        target = float(positive.median())
        if not np.isfinite(target):
            code = INVALID_NONFINITE_VOLATILITY_TARGET
        elif target <= min_target_volatility:
            code = INVALID_DEGENERATE_VOLATILITY_CALIBRATION
        else:
            code = ""

    status = "valid" if not code else "invalid"
    return VolatilityCalibration(
        status=status,
        invalidity_code=code,
        evaluation_start=eval_start.date().isoformat(),
        calibration_start=calibration_frame["date"].min().date().isoformat() if not calibration_frame.empty else "",
        calibration_end=calibration_frame["date"].max().date().isoformat() if not calibration_frame.empty else "",
        selected_return_start=selected.index.min().date().isoformat(),
        selected_return_end=selected.index.max().date().isoformat(),
        valid_return_count_available=available_returns,
        selected_return_count=int(len(selected)),
        rolling_volatility_count=int(len(finite_rolling)),
        positive_rolling_volatility_count=int(len(positive)),
        target_volatility=target,
        selected_returns=selected,
        rolling_volatility=finite_rolling,
    )


def dynamic_scale_diagnostics_from_values(
    *,
    estimated_volatility: list[float] | pd.Series,
    raw_scale: list[float] | pd.Series,
    capped_scale: list[float] | pd.Series,
    target_volatility: float,
    scale_floor: float = 0.25,
    scale_cap: float = 1.0,
    min_target_volatility: float = 1e-8,
    concentration_threshold: float = 0.95,
    min_between_bounds_pct: float = 0.05,
    min_scale_std: float = 1e-12,
    rounded_decimals: int = 6,
) -> dict[str, Any]:
    est = pd.Series(estimated_volatility, dtype=float).replace([np.inf, -np.inf], np.nan).dropna()
    raw = pd.Series(raw_scale, dtype=float).replace([np.inf, -np.inf], np.nan).dropna()
    capped = pd.Series(capped_scale, dtype=float).replace([np.inf, -np.inf], np.nan).dropna()
    count = int(len(capped))
    floor_pct = float((np.isclose(capped, scale_floor)).mean()) if count else np.nan
    cap_pct = float((np.isclose(capped, scale_cap)).mean()) if count else np.nan
    between = (capped > scale_floor) & (capped < scale_cap)
    between_pct = float(between.mean()) if count else np.nan
    scale_std = float(capped.std(ddof=0)) if count else np.nan
    target_valid = np.isfinite(target_volatility) and float(target_volatility) > min_target_volatility
    non_dynamic = (
        not target_valid
        or count == 0
        or floor_pct >= concentration_threshold
        or cap_pct >= concentration_threshold
        or between_pct < min_between_bounds_pct
        or (np.isfinite(scale_std) and scale_std <= min_scale_std)
    )
    return {
        "target_volatility": float(target_volatility) if np.isfinite(target_volatility) else np.nan,
        "estimated_volatility_count": int(len(est)),
        "estimated_volatility_min": float(est.min()) if len(est) else np.nan,
        "estimated_volatility_p25": float(est.quantile(0.25)) if len(est) else np.nan,
        "estimated_volatility_median": float(est.median()) if len(est) else np.nan,
        "estimated_volatility_p75": float(est.quantile(0.75)) if len(est) else np.nan,
        "estimated_volatility_max": float(est.max()) if len(est) else np.nan,
        "raw_scale_min": float(raw.min()) if len(raw) else np.nan,
        "raw_scale_median": float(raw.median()) if len(raw) else np.nan,
        "raw_scale_max": float(raw.max()) if len(raw) else np.nan,
        "capped_scale_min": float(capped.min()) if count else np.nan,
        "capped_scale_median": float(capped.median()) if count else np.nan,
        "capped_scale_max": float(capped.max()) if count else np.nan,
        "floor_decision_pct": floor_pct,
        "cap_decision_pct": cap_pct,
        "between_bounds_decision_pct": between_pct,
        "distinct_rounded_scale_values": int(capped.round(rounded_decimals).nunique()) if count else 0,
        "average_scale": float(capped.mean()) if count else np.nan,
        "scale_standard_deviation": scale_std,
        "applicable_decision_count": count,
        "status": INVALID_NON_DYNAMIC_VOLATILITY_SCALER if non_dynamic else PASS_DYNAMIC_VOLATILITY_SCALER,
    }


def dynamic_scale_diagnostics_from_events(
    events: pd.DataFrame,
    *,
    target_volatility: float,
    scale_floor: float = 0.25,
    scale_cap: float = 1.0,
) -> dict[str, Any]:
    estimated: list[float] = []
    raw: list[float] = []
    capped: list[float] = []
    if not events.empty:
        frame = events[events.get("reason_code", pd.Series(dtype=str)) == "lagged_vol_scale"]
        for _, event in frame.iterrows():
            proposed = _json_cell(event.get("proposed_order"))
            flags = _json_cell(event.get("data_quality_flags"))
            _append_float(estimated, proposed.get("estimated_volatility"))
            _append_float(raw, flags.get("raw_scale"))
            _append_float(capped, flags.get("capped_scale"))
    return dynamic_scale_diagnostics_from_values(
        estimated_volatility=estimated,
        raw_scale=raw,
        capped_scale=capped,
        target_volatility=target_volatility,
        scale_floor=scale_floor,
        scale_cap=scale_cap,
    )


def capped_scales_from_events(events: pd.DataFrame) -> list[float]:
    scales: list[float] = []
    if events.empty:
        return scales
    for _, event in events.iterrows():
        flags = _json_cell(event.get("data_quality_flags"))
        _append_float(scales, flags.get("capped_scale"))
    return scales


def static_control_scale_from_capped_scales(scales: list[float] | pd.Series) -> float:
    series = pd.Series(scales, dtype=float).replace([np.inf, -np.inf], np.nan).dropna()
    if series.empty:
        raise ValueError("No finite calibration dynamic scales are available.")
    return float(series.median())


def _json_cell(value: Any) -> dict[str, Any]:
    if not isinstance(value, str) or not value:
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _append_float(values: list[float], value: Any) -> None:
    if value is None:
        return
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return
    if np.isfinite(parsed):
        values.append(parsed)
