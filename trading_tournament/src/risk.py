from __future__ import annotations

from typing import Any

import pandas as pd


PROJECT_STOP_MODES = {"absolute_floor", "trailing_drawdown", "both"}


def project_stop_config(config: dict[str, Any]) -> dict[str, Any]:
    project = config.get("project", {})
    stop = dict(project.get("project_stop", {}) or {})
    mode = stop.get("mode", "absolute_floor")
    if mode not in PROJECT_STOP_MODES:
        raise ValueError(f"Unsupported project_stop.mode: {mode}")
    return {
        "mode": mode,
        "absolute_floor_equity": float(
            stop.get("absolute_floor_equity", project.get("hard_stop_equity", 2400.0))
        ),
        "trailing_drawdown_dollars": float(stop.get("trailing_drawdown_dollars", 600.0)),
    }


def evaluate_project_stop(
    equity: float,
    high_water_mark: float,
    config: dict[str, Any],
) -> dict[str, Any]:
    stop = project_stop_config(config)
    absolute_hit = equity <= stop["absolute_floor_equity"]
    trailing_hit = equity <= high_water_mark - stop["trailing_drawdown_dollars"]
    mode = stop["mode"]
    active_absolute = absolute_hit and mode in {"absolute_floor", "both"}
    active_trailing = trailing_hit and mode in {"trailing_drawdown", "both"}
    first_type = ""
    if active_absolute and active_trailing:
        first_type = "absolute_floor_stop_hit,trailing_drawdown_stop_hit"
    elif active_absolute:
        first_type = "absolute_floor_stop_hit"
    elif active_trailing:
        first_type = "trailing_drawdown_stop_hit"
    return {
        "mode": mode,
        "absolute_floor_stop_hit": bool(absolute_hit),
        "trailing_drawdown_stop_hit": bool(trailing_hit),
        "absolute_floor_stop_active": bool(active_absolute),
        "trailing_drawdown_stop_active": bool(active_trailing),
        "any_project_stop_active": bool(active_absolute or active_trailing),
        "first_project_stop_type": first_type,
        "drawdown_at_stop": float(equity - high_water_mark),
    }


def compute_target_timing(equity_curve: pd.DataFrame, config: dict[str, Any]) -> dict[str, Any]:
    if equity_curve.empty:
        return {}
    frame = equity_curve.copy()
    frame["date"] = pd.to_datetime(frame["date"])
    starting = float(config["project"]["starting_equity"])
    targets = {
        "target_300": starting + float(config["project"]["target_profit_1"]),
        "target_400": starting + float(config["project"]["target_profit_2"]),
    }
    def bool_col(name: str) -> pd.Series:
        if name in frame:
            return frame[name].fillna(False).astype(bool)
        return pd.Series(False, index=frame.index)

    absolute_dates = frame.loc[bool_col("absolute_floor_stop_active"), "date"]
    trailing_dates = frame.loc[bool_col("trailing_drawdown_stop_active"), "date"]
    any_dates = frame.loc[
        (bool_col("absolute_floor_stop_active") | bool_col("trailing_drawdown_stop_active")),
        "date",
    ]
    first_absolute = absolute_dates.min() if not absolute_dates.empty else pd.NaT
    first_trailing = trailing_dates.min() if not trailing_dates.empty else pd.NaT
    first_any = any_dates.min() if not any_dates.empty else pd.NaT
    out: dict[str, Any] = {}
    for label, target_value in targets.items():
        hit_rows = frame.loc[frame["equity"] >= target_value]
        hit = not hit_rows.empty
        first_date = hit_rows.iloc[0]["date"] if hit else pd.NaT
        equity_at_target = float(hit_rows.iloc[0]["equity"]) if hit else float("nan")
        trading_days = int(hit_rows.index[0]) + 1 if hit else pd.NA
        out[f"{label}_hit"] = bool(hit)
        out[f"{label}_first_date"] = first_date.date().isoformat() if hit else ""
        out[f"{label}_trading_days"] = trading_days
        out[f"equity_at_{label}"] = equity_at_target
        out[f"{label}_before_absolute_stop"] = bool(hit and (pd.isna(first_absolute) or first_date <= first_absolute))
        out[f"{label}_before_trailing_stop"] = bool(hit and (pd.isna(first_trailing) or first_date <= first_trailing))
        out[f"{label}_before_any_stop"] = bool(hit and (pd.isna(first_any) or first_date <= first_any))
    out["absolute_floor_stop_hit"] = bool(not absolute_dates.empty)
    out["absolute_floor_stop_date"] = first_absolute.date().isoformat() if not pd.isna(first_absolute) else ""
    out["trailing_drawdown_stop_hit"] = bool(not trailing_dates.empty)
    out["trailing_drawdown_stop_date"] = first_trailing.date().isoformat() if not pd.isna(first_trailing) else ""
    out["any_project_stop_hit"] = bool(not any_dates.empty)
    out["first_project_stop_date"] = first_any.date().isoformat() if not pd.isna(first_any) else ""
    if not pd.isna(first_any):
        stop_row = frame.loc[frame["date"] == first_any].iloc[0]
        out["first_project_stop_type"] = (
            "absolute_floor_stop_hit"
            if bool(stop_row.get("absolute_floor_stop_active", False))
            else "trailing_drawdown_stop_hit"
        )
        if bool(stop_row.get("absolute_floor_stop_active", False)) and bool(stop_row.get("trailing_drawdown_stop_active", False)):
            out["first_project_stop_type"] = "absolute_floor_stop_hit,trailing_drawdown_stop_hit"
        out["equity_at_first_project_stop"] = float(stop_row["equity"])
        out["high_water_mark_at_stop"] = float(stop_row.get("high_water_mark", stop_row["equity"]))
        out["drawdown_at_stop"] = float(stop_row.get("drawdown_dollars", 0.0))
    else:
        out["first_project_stop_type"] = ""
        out["equity_at_first_project_stop"] = float("nan")
        out["high_water_mark_at_stop"] = float("nan")
        out["drawdown_at_stop"] = float("nan")
    return out


def target_timing_frame(equity_curve: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    timing = compute_target_timing(equity_curve, config)
    return pd.DataFrame([timing]) if timing else pd.DataFrame()
