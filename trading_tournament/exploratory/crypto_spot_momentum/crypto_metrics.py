from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def max_drawdown(equity: pd.Series) -> tuple[float, float, pd.Series, pd.Series]:
    if equity.empty:
        empty = pd.Series(dtype=float)
        return 0.0, 0.0, empty, empty
    high_water = equity.cummax()
    drawdown_dollars = equity - high_water
    drawdown_pct = drawdown_dollars / high_water.replace(0, np.nan)
    return float(drawdown_dollars.min()), float(drawdown_pct.min()), high_water, drawdown_dollars


def target_and_stop_state(equity_curve: pd.DataFrame, project_cfg: dict[str, Any]) -> dict[str, Any]:
    if equity_curve.empty:
        return {
            "target_300_hit": False,
            "target_300_first_date": "",
            "target_300_before_stop": False,
            "target_400_hit": False,
            "target_400_first_date": "",
            "target_400_before_stop": False,
            "absolute_floor_stop_hit": False,
            "trailing_drawdown_stop_hit": False,
            "any_project_stop_hit": False,
            "first_project_stop_date": "",
            "time_to_target_300_days": "",
            "time_to_target_400_days": "",
        }

    df = equity_curve.copy()
    df["date"] = pd.to_datetime(df["date"])
    equity = df["equity"].astype(float)
    hwm = equity.cummax()
    absolute_hit = equity <= float(project_cfg["project_stop_equity"])
    trailing_hit = equity <= hwm - float(project_cfg["trailing_drawdown_dollars"])
    mode = project_cfg.get("project_stop_mode", "both")
    if mode == "absolute_floor":
        any_hit = absolute_hit
    elif mode == "trailing_drawdown":
        any_hit = trailing_hit
    else:
        any_hit = absolute_hit | trailing_hit

    first_stop_date = ""
    if any_hit.any():
        first_stop_date = df.loc[any_hit, "date"].iloc[0].date().isoformat()

    def first_target(target: float) -> tuple[bool, str, bool, Any]:
        hit_mask = equity >= target
        if not hit_mask.any():
            return False, "", False, ""
        target_date = df.loc[hit_mask, "date"].iloc[0]
        if first_stop_date:
            before_stop = target_date <= pd.Timestamp(first_stop_date)
        else:
            before_stop = True
        days = int((df["date"] <= target_date).sum() - 1)
        return True, target_date.date().isoformat(), bool(before_stop), days

    t300 = first_target(float(project_cfg["target_300_equity"]))
    t400 = first_target(float(project_cfg["target_400_equity"]))
    return {
        "target_300_hit": t300[0],
        "target_300_first_date": t300[1],
        "target_300_before_stop": t300[2],
        "target_400_hit": t400[0],
        "target_400_first_date": t400[1],
        "target_400_before_stop": t400[2],
        "absolute_floor_stop_hit": bool(absolute_hit.any()),
        "trailing_drawdown_stop_hit": bool(trailing_hit.any()),
        "any_project_stop_hit": bool(any_hit.any()),
        "first_project_stop_date": first_stop_date,
        "time_to_target_300_days": t300[3],
        "time_to_target_400_days": t400[3],
    }


def compute_strategy_metrics(
    strategy: str,
    slippage_label: str,
    fee_slippage_per_side: float,
    equity_curve: pd.DataFrame,
    weights: pd.DataFrame,
    rebalances: pd.DataFrame,
    asset_contributions: dict[str, float],
    turnover_estimate: float,
    project_cfg: dict[str, Any],
) -> dict[str, Any]:
    if equity_curve.empty:
        base = {
            "strategy": strategy,
            "slippage_label": slippage_label,
            "fee_slippage_per_side": fee_slippage_per_side,
            "final_equity": np.nan,
            "total_return": np.nan,
            "CAGR": np.nan,
            "volatility": np.nan,
            "max_drawdown_dollars": np.nan,
            "max_drawdown_pct": np.nan,
            "number_of_rebalances": 0,
            "turnover_estimate": 0.0,
            "time_in_market": 0.0,
            "best_asset_contribution": "",
            "worst_rolling_window_return": np.nan,
        }
        base.update(target_and_stop_state(equity_curve, project_cfg))
        return base

    df = equity_curve.copy()
    df["date"] = pd.to_datetime(df["date"])
    equity = df["equity"].astype(float)
    start_equity = float(project_cfg["starting_equity"])
    total_return = float(equity.iloc[-1] / start_equity - 1.0)
    days = max(1, int((df["date"].iloc[-1] - df["date"].iloc[0]).days))
    cagr = float((equity.iloc[-1] / start_equity) ** (365.25 / days) - 1.0) if equity.iloc[-1] > 0 else -1.0
    returns = df["daily_return"].astype(float)
    volatility = float(returns.std(ddof=0) * np.sqrt(365.0))
    dd_dollars, dd_pct, _, _ = max_drawdown(equity)
    time_in_market = float((weights.sum(axis=1) > 1e-9).mean()) if not weights.empty else 0.0
    contributions = {k: float(v) for k, v in asset_contributions.items()}
    best_asset = max(contributions, key=contributions.get) if contributions else ""
    rolling_return = equity.pct_change(30, fill_method=None)

    metrics = {
        "strategy": strategy,
        "slippage_label": slippage_label,
        "fee_slippage_per_side": fee_slippage_per_side,
        "credibility_tier": "Tier 1 exploratory screen",
        "final_validation": False,
        "candidate_validation": False,
        "paper_forward_ready": False,
        "real_money_recommendation": False,
        "final_equity": float(equity.iloc[-1]),
        "total_return": total_return,
        "CAGR": cagr,
        "volatility": volatility,
        "max_drawdown_dollars": dd_dollars,
        "max_drawdown_pct": dd_pct,
        "number_of_rebalances": int(len(rebalances)),
        "turnover_estimate": float(turnover_estimate),
        "time_in_market": time_in_market,
        "best_asset_contribution": best_asset,
        "worst_rolling_window_return": float(rolling_return.min()) if rolling_return.notna().any() else np.nan,
    }
    metrics.update(target_and_stop_state(equity_curve, project_cfg))
    return metrics


def summarize_rolling_windows(results: pd.DataFrame) -> pd.DataFrame:
    if results.empty:
        return pd.DataFrame()
    grouped = results.groupby(["strategy", "slippage_label", "horizon"], dropna=False)
    rows: list[dict[str, Any]] = []
    for keys, group in grouped:
        strategy, slippage_label, horizon = keys
        rows.append(
            {
                "strategy": strategy,
                "slippage_label": slippage_label,
                "horizon": int(horizon),
                "credibility_tier": "Tier 1 exploratory screen",
                "final_validation": False,
                "candidate_validation": False,
                "paper_forward_ready": False,
                "sampled_results_are_final": False,
                "number_of_windows": int(len(group)),
                "mean_final_equity": float(group["final_equity"].mean()),
                "median_final_equity": float(group["final_equity"].median()),
                "pct_windows_target_300_hit": float(group["target_300_hit"].mean()),
                "pct_windows_target_300_before_stop": float(group["target_300_before_stop"].mean()),
                "pct_windows_target_400_hit": float(group["target_400_hit"].mean()),
                "pct_windows_target_400_before_stop": float(group["target_400_before_stop"].mean()),
                "pct_windows_any_project_stop_hit": float(group["any_project_stop_hit"].mean()),
                "median_max_drawdown_pct": float(group["max_drawdown_pct"].median()),
                "worst_max_drawdown_pct": float(group["max_drawdown_pct"].min()),
                "median_rebalances": float(group["number_of_rebalances"].median()),
                "pct_windows_positive_return": float((group["total_return"] > 0).mean()),
                "pct_windows_below_2400": float((group["final_equity"] < 2400).mean()),
                "pct_windows_above_3300": float((group["final_equity"] >= 3300).mean()),
                "pct_windows_above_3400": float((group["final_equity"] >= 3400).mean()),
            }
        )
    return pd.DataFrame(rows)
