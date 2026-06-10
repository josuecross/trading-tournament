from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pandas as pd


TARGET_LEVELS = ("300", "400", "600", "900", "1200")
REQUIRED_WINDOW_COLUMNS = {"window_start", "window_end"}


def _as_series(values: pd.Series | pd.DataFrame, value_col: str = "equity") -> pd.Series:
    if isinstance(values, pd.Series):
        series = values.copy()
    elif value_col in values:
        series = values[value_col].copy()
        if "date" in values:
            series.index = pd.to_datetime(values["date"])
    else:
        raise ValueError(f"Expected Series or DataFrame with `{value_col}` column.")
    series.index = pd.to_datetime(series.index)
    return series.astype(float).sort_index()


def _normalize_weights(
    weights: Mapping[str, float] | pd.Series | pd.DataFrame,
    index: pd.Index,
    columns: pd.Index,
) -> pd.DataFrame:
    if isinstance(weights, pd.DataFrame):
        frame = weights.reindex(index=index, columns=columns).fillna(0.0).astype(float)
    elif isinstance(weights, pd.Series):
        frame = pd.DataFrame([weights.reindex(columns).fillna(0.0).astype(float)] * len(index), index=index, columns=columns)
    else:
        series = pd.Series(dict(weights), dtype=float).reindex(columns).fillna(0.0)
        frame = pd.DataFrame([series] * len(index), index=index, columns=columns)
    row_sums = frame.sum(axis=1).replace(0.0, 1.0)
    return frame.div(row_sums, axis=0).fillna(0.0)


def _unavailable_row(experiment_id: str, status: str, **extra: Any) -> pd.DataFrame:
    row = {
        "experiment_id": experiment_id,
        "contribution_status": status,
        "drawdown_overlap_status": status,
    }
    row.update(extra)
    return pd.DataFrame([row])


def _equity_from_component_returns(
    component_returns: pd.DataFrame,
    weights: Mapping[str, float] | pd.Series | pd.DataFrame,
    starting_equity: float,
) -> tuple[pd.Series, pd.DataFrame, pd.DataFrame]:
    returns = component_returns.copy().astype(float).replace([float("inf"), float("-inf")], pd.NA).fillna(0.0)
    returns.index = pd.to_datetime(returns.index)
    returns = returns.sort_index()
    weights_frame = _normalize_weights(weights, returns.index, returns.columns)
    equity_values: list[float] = []
    contribution_rows: list[dict[str, float]] = []
    equity = float(starting_equity)
    for pos, date in enumerate(returns.index):
        row: dict[str, float] = {}
        if pos == 0:
            for component_id in returns.columns:
                row[str(component_id)] = 0.0
            equity_values.append(equity)
            contribution_rows.append(row)
            continue
        for component_id in returns.columns:
            contribution = equity * float(weights_frame.loc[date, component_id]) * float(returns.loc[date, component_id])
            row[str(component_id)] = contribution
        equity += sum(row.values())
        equity_values.append(equity)
        contribution_rows.append(row)
    equity_series = pd.Series(equity_values, index=returns.index, name="equity")
    contribution_frame = pd.DataFrame(contribution_rows, index=returns.index).fillna(0.0)
    return equity_series, contribution_frame, weights_frame


def _drawdown_points(equity: pd.Series) -> tuple[pd.Timestamp | None, pd.Timestamp | None, float]:
    if equity.empty:
        return None, None, float("nan")
    high_water = equity.cummax()
    drawdown = equity - high_water
    trough = drawdown.idxmin()
    peak_candidates = equity.loc[:trough]
    peak = peak_candidates.idxmax() if not peak_candidates.empty else trough
    return pd.Timestamp(peak), pd.Timestamp(trough), float(drawdown.loc[trough])


def _recovery_points(equity: pd.Series) -> tuple[pd.Timestamp | None, pd.Timestamp | None, float]:
    peak, trough, _drawdown = _drawdown_points(equity)
    if peak is None or trough is None:
        return None, None, float("nan")
    peak_value = float(equity.loc[peak])
    after_trough = equity.loc[trough:]
    recovered = after_trough[after_trough >= peak_value]
    if recovered.empty:
        return pd.Timestamp(trough), None, float("nan")
    recovery_end = pd.Timestamp(recovered.index[0])
    return pd.Timestamp(trough), recovery_end, float(equity.loc[recovery_end] - equity.loc[trough])


def _date_label(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    return pd.to_datetime(value).date().isoformat()


def compute_incremental_target_windows(
    windows: pd.DataFrame,
    experiment_id: str = "",
) -> pd.DataFrame:
    """Add incremental target-hit flags versus combo and top2 benchmark flags."""
    if windows.empty:
        return pd.DataFrame()
    frame = windows.copy()
    if experiment_id and "experiment_id" in frame:
        frame = frame[frame["experiment_id"].astype(str).eq(experiment_id)].copy()
    if "combination_id" in frame and "experiment_id" not in frame:
        frame = frame.rename(columns={"combination_id": "experiment_id"})
    required = REQUIRED_WINDOW_COLUMNS | {"target_300_hit", "target_400_hit"}
    if not required.issubset(frame.columns):
        return _unavailable_row(experiment_id or "unknown", "unavailable_missing_target_flags")
    column_aliases = {
        "benchmark_combo_target_300_hit": "combo_benchmark_target_300_hit",
        "benchmark_combo_target_400_hit": "combo_benchmark_target_400_hit",
        "benchmark_top2_target_300_hit": "top2_benchmark_target_300_hit",
        "benchmark_top2_target_400_hit": "top2_benchmark_target_400_hit",
    }
    for canonical, existing in column_aliases.items():
        if canonical not in frame and existing in frame:
            frame[canonical] = frame[existing]
    for column in column_aliases:
        if column not in frame:
            frame[column] = False
    frame["incremental_300_vs_combo"] = frame["target_300_hit"].astype(bool) & ~frame["benchmark_combo_target_300_hit"].astype(bool)
    frame["incremental_400_vs_combo"] = frame["target_400_hit"].astype(bool) & ~frame["benchmark_combo_target_400_hit"].astype(bool)
    frame["incremental_300_vs_top2"] = frame["target_300_hit"].astype(bool) & ~frame["benchmark_top2_target_300_hit"].astype(bool)
    frame["incremental_400_vs_top2"] = frame["target_400_hit"].astype(bool) & ~frame["benchmark_top2_target_400_hit"].astype(bool)
    return frame


def compute_target_window_attribution(
    windows: pd.DataFrame,
    experiment_id: str = "",
) -> pd.DataFrame:
    """Return target-hit and benchmark-incremental attribution rows."""
    frame = compute_incremental_target_windows(windows, experiment_id=experiment_id)
    if frame.empty or "contribution_status" in frame:
        return frame
    for target in TARGET_LEVELS:
        column = f"target_{target}_hit"
        if column not in frame:
            frame[column] = False
    keep = [
        "experiment_id",
        "horizon",
        "cost_mode",
        "window_start",
        "window_end",
        "target_300_hit",
        "target_400_hit",
        "target_600_hit",
        "target_900_hit",
        "target_1200_hit",
        "benchmark_combo_target_300_hit",
        "benchmark_combo_target_400_hit",
        "benchmark_top2_target_300_hit",
        "benchmark_top2_target_400_hit",
        "incremental_300_vs_combo",
        "incremental_400_vs_combo",
        "incremental_300_vs_top2",
        "incremental_400_vs_top2",
    ]
    for column in keep:
        if column not in frame:
            frame[column] = ""
    return frame[keep].copy()


def compute_component_contribution(
    component_returns: pd.DataFrame | None,
    weights: Mapping[str, float] | pd.Series | pd.DataFrame | None,
    *,
    experiment_id: str,
    horizon: int | None = None,
    window_start: Any = "",
    window_end: Any = "",
    starting_equity: float = 3000.0,
) -> pd.DataFrame:
    """Compute additive component contribution for a window of component returns."""
    if component_returns is None or weights is None or component_returns.empty:
        return _unavailable_row(experiment_id, "unavailable_missing_component_returns", horizon=horizon, window_start=window_start, window_end=window_end)
    equity, contributions, weights_frame = _equity_from_component_returns(component_returns, weights, starting_equity)
    peak, trough, _drawdown = _drawdown_points(equity)
    recovery_start, recovery_end, _recovery_amount = _recovery_points(equity)
    rows: list[dict[str, Any]] = []
    for component_id in contributions.columns:
        drawdown_contribution: float | str = ""
        recovery_contribution: float | str = ""
        if peak is not None and trough is not None:
            drawdown_slice = contributions.loc[peak:trough]
            drawdown_contribution = float(drawdown_slice[component_id].sum())
        if recovery_start is not None and recovery_end is not None:
            recovery_slice = contributions.loc[recovery_start:recovery_end]
            recovery_contribution = float(recovery_slice[component_id].sum())
        component_weight = float(weights_frame[component_id].median()) if component_id in weights_frame else float("nan")
        total_contribution = float(contributions[component_id].sum())
        rows.append(
            {
                "experiment_id": experiment_id,
                "horizon": horizon if horizon is not None else len(component_returns),
                "window_start": _date_label(window_start) or _date_label(component_returns.index[0]),
                "window_end": _date_label(window_end) or _date_label(component_returns.index[-1]),
                "component_id": component_id,
                "component_weight": component_weight,
                "component_return_contribution": total_contribution,
                "component_final_equity_contribution": total_contribution,
                "component_drawdown_contribution": drawdown_contribution,
                "component_recovery_contribution": recovery_contribution,
                "contribution_status": "available",
            }
        )
    return pd.DataFrame(rows)


def compute_drawdown_attribution(
    component_returns: pd.DataFrame | None = None,
    weights: Mapping[str, float] | pd.Series | pd.DataFrame | None = None,
    *,
    experiment_id: str,
    equity_curve: pd.Series | pd.DataFrame | None = None,
    component_daily_contributions: pd.DataFrame | None = None,
    horizon: int | None = None,
    window_start: Any = "",
    window_end: Any = "",
    benchmark_drawdown_overlap: bool | str | None = None,
    starting_equity: float = 3000.0,
) -> pd.DataFrame:
    """Attribute the worst drawdown period to component contribution streams."""
    if component_daily_contributions is not None and equity_curve is not None:
        equity = _as_series(equity_curve)
        contributions = component_daily_contributions.copy().astype(float).fillna(0.0)
        contributions.index = pd.to_datetime(contributions.index)
    elif component_returns is not None and weights is not None and not component_returns.empty:
        equity, contributions, _weights_frame = _equity_from_component_returns(component_returns, weights, starting_equity)
    else:
        return _unavailable_row(experiment_id, "unavailable_missing_component_drawdown_inputs", horizon=horizon, window_start=window_start, window_end=window_end)
    peak, trough, worst_drawdown = _drawdown_points(equity)
    rows: list[dict[str, Any]] = []
    for component_id in contributions.columns:
        drawdown_slice = contributions.loc[peak:trough] if peak is not None and trough is not None else pd.DataFrame()
        rows.append(
            {
                "experiment_id": experiment_id,
                "horizon": horizon if horizon is not None else len(equity),
                "window_start": _date_label(window_start) or _date_label(equity.index[0]),
                "window_end": _date_label(window_end) or _date_label(equity.index[-1]),
                "worst_drawdown": worst_drawdown,
                "worst_drawdown_start": _date_label(peak),
                "worst_drawdown_end": _date_label(trough),
                "component_id": component_id,
                "component_drawdown_contribution": float(drawdown_slice[component_id].sum()) if not drawdown_slice.empty else "",
                "benchmark_drawdown_overlap": benchmark_drawdown_overlap if benchmark_drawdown_overlap is not None else "",
                "drawdown_overlap_status": "available",
            }
        )
    return pd.DataFrame(rows)


def compute_recovery_attribution(
    component_returns: pd.DataFrame | None = None,
    weights: Mapping[str, float] | pd.Series | pd.DataFrame | None = None,
    *,
    experiment_id: str,
    equity_curve: pd.Series | pd.DataFrame | None = None,
    component_daily_contributions: pd.DataFrame | None = None,
    horizon: int | None = None,
    window_start: Any = "",
    window_end: Any = "",
    starting_equity: float = 3000.0,
) -> pd.DataFrame:
    """Attribute recovery from the worst drawdown trough back to its prior high."""
    if component_daily_contributions is not None and equity_curve is not None:
        equity = _as_series(equity_curve)
        contributions = component_daily_contributions.copy().astype(float).fillna(0.0)
        contributions.index = pd.to_datetime(contributions.index)
    elif component_returns is not None and weights is not None and not component_returns.empty:
        equity, contributions, _weights_frame = _equity_from_component_returns(component_returns, weights, starting_equity)
    else:
        return _unavailable_row(experiment_id, "unavailable_missing_component_recovery_inputs", horizon=horizon, window_start=window_start, window_end=window_end)
    recovery_start, recovery_end, recovery_amount = _recovery_points(equity)
    rows: list[dict[str, Any]] = []
    for component_id in contributions.columns:
        recovery_contribution: float | str = ""
        if recovery_start is not None and recovery_end is not None:
            recovery_contribution = float(contributions.loc[recovery_start:recovery_end, component_id].sum())
        rows.append(
            {
                "experiment_id": experiment_id,
                "horizon": horizon if horizon is not None else len(equity),
                "window_start": _date_label(window_start) or _date_label(equity.index[0]),
                "window_end": _date_label(window_end) or _date_label(equity.index[-1]),
                "recovery_start": _date_label(recovery_start),
                "recovery_end": _date_label(recovery_end),
                "recovery_amount": recovery_amount,
                "component_id": component_id,
                "component_recovery_contribution": recovery_contribution,
            }
        )
    return pd.DataFrame(rows)


def extract_worst_n_drawdown_windows(
    windows: pd.DataFrame,
    n: int = 5,
    *,
    experiment_id: str = "",
) -> pd.DataFrame:
    """Rank the worst N drawdown windows from a window-level diagnostics table."""
    if windows.empty or "worst_drawdown" not in windows:
        return _unavailable_row(experiment_id or "unknown", "unavailable_missing_worst_drawdown")
    frame = windows.copy()
    if "combination_id" in frame and "experiment_id" not in frame:
        frame = frame.rename(columns={"combination_id": "experiment_id"})
    if experiment_id:
        frame = frame[frame["experiment_id"].astype(str).eq(experiment_id)].copy()
    frame = frame.sort_values("worst_drawdown", ascending=True).head(n).copy()
    frame["rank"] = range(1, len(frame) + 1)
    aliases = {
        "overlap_with_combo": "combo_drawdown_overlap_flags_if_available",
        "overlap_with_top2": "top2_drawdown_overlap_flags_if_available",
        "overlap_with_spy200d": "spy200d_drawdown_overlap_flags_if_available",
    }
    for canonical, existing in aliases.items():
        if canonical not in frame:
            frame[canonical] = frame[existing] if existing in frame else ""
    if "target_hit_before_stop" not in frame:
        target_cols = [col for col in ["target_300_hit", "target_400_hit", "target_600_hit"] if col in frame]
        frame["target_hit_before_stop"] = frame[target_cols].astype(bool).any(axis=1) if target_cols else ""
    keep = [
        "experiment_id",
        "horizon",
        "rank",
        "window_start",
        "window_end",
        "worst_drawdown",
        "stop_hit",
        "target_hit_before_stop",
        "overlap_with_combo",
        "overlap_with_top2",
        "overlap_with_spy200d",
    ]
    for column in keep:
        if column not in frame:
            frame[column] = ""
    return frame[keep].copy()


def compute_drawdown_coincidence_detail(
    candidate_curve: pd.Series | pd.DataFrame,
    benchmark_curves: Mapping[str, pd.Series | pd.DataFrame],
    *,
    experiment_id: str,
    threshold: float = -0.05,
) -> pd.DataFrame:
    """Measure how often candidate drawdown days coincide with benchmark drawdown days."""
    candidate = _as_series(candidate_curve)
    candidate_drawdown = candidate / candidate.cummax() - 1.0
    candidate_stress = candidate_drawdown <= threshold
    rows: list[dict[str, Any]] = []
    for benchmark_id, curve in benchmark_curves.items():
        benchmark = _as_series(curve)
        shared = candidate.index.intersection(benchmark.index)
        if len(shared) == 0:
            rows.append(
                {
                    "experiment_id": experiment_id,
                    "benchmark_id": benchmark_id,
                    "drawdown_coincidence_rate": "",
                    "candidate_drawdown_day_count": 0,
                    "benchmark_drawdown_day_count": 0,
                    "overlap_day_count": 0,
                    "drawdown_overlap_status": "unavailable_no_common_dates",
                }
            )
            continue
        benchmark_drawdown = benchmark / benchmark.cummax() - 1.0
        left = candidate_stress.loc[shared]
        right = (benchmark_drawdown.loc[shared] <= threshold)
        candidate_count = int(left.sum())
        overlap = int((left & right).sum())
        rate = overlap / candidate_count if candidate_count else 0.0
        rows.append(
            {
                "experiment_id": experiment_id,
                "benchmark_id": benchmark_id,
                "drawdown_coincidence_rate": rate,
                "candidate_drawdown_day_count": candidate_count,
                "benchmark_drawdown_day_count": int(right.sum()),
                "overlap_day_count": overlap,
                "drawdown_overlap_status": "available",
            }
        )
    return pd.DataFrame(rows)


def summarize_diversification_diagnostics(
    target_attribution: pd.DataFrame | None = None,
    drawdown_coincidence: pd.DataFrame | None = None,
    *,
    experiment_id: str,
    correlation_to_primary: float | None = None,
    high_correlation_threshold: float = 0.90,
) -> pd.DataFrame:
    """Summarize duplicate/diversification posture from attribution diagnostics."""
    incremental_hits = 0
    if target_attribution is not None and not target_attribution.empty:
        incremental_cols = [col for col in target_attribution.columns if col.startswith("incremental_")]
        if incremental_cols:
            incremental_hits = int(target_attribution[incremental_cols].astype(bool).sum().sum())
    avg_drawdown_overlap: float | str = ""
    if drawdown_coincidence is not None and not drawdown_coincidence.empty and "drawdown_coincidence_rate" in drawdown_coincidence:
        numeric = pd.to_numeric(drawdown_coincidence["drawdown_coincidence_rate"], errors="coerce").dropna()
        avg_drawdown_overlap = float(numeric.mean()) if not numeric.empty else ""
    duplicate_warning = bool(correlation_to_primary is not None and correlation_to_primary >= high_correlation_threshold and incremental_hits == 0)
    diversification_status = "duplicate_or_near_duplicate" if duplicate_warning else "possibly_diversifying"
    if incremental_hits == 0 and avg_drawdown_overlap != "" and float(avg_drawdown_overlap) < 0.60:
        diversification_status = "drawdown_reducer_not_target_additive"
    return pd.DataFrame(
        [
            {
                "experiment_id": experiment_id,
                "incremental_target_hit_count": incremental_hits,
                "average_drawdown_coincidence_rate": avg_drawdown_overlap,
                "correlation_to_primary": correlation_to_primary if correlation_to_primary is not None else "",
                "duplicate_warning": duplicate_warning,
                "diversification_status": diversification_status,
            }
        ]
    )
