from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .portfolio import is_backtest_strategy


def max_drawdown(equity: pd.Series) -> tuple[float, float]:
    if equity.empty:
        return 0.0, 0.0
    running_peak = equity.cummax()
    drawdown_dollars = equity - running_peak
    drawdown_pct = equity / running_peak - 1.0
    return float(drawdown_dollars.min()), float(drawdown_pct.min())


def recovery_time_days(equity: pd.Series) -> int:
    if equity.empty:
        return 0
    peak = equity.iloc[0]
    current_underwater = 0
    longest = 0
    for value in equity:
        if value >= peak:
            peak = value
            current_underwater = 0
        else:
            current_underwater += 1
            longest = max(longest, current_underwater)
    return int(longest)


def profit_factor(trades: pd.DataFrame) -> float:
    if trades.empty or "pnl" not in trades:
        return np.nan
    gross_profit = trades.loc[trades["pnl"] > 0, "pnl"].sum()
    gross_loss = -trades.loc[trades["pnl"] < 0, "pnl"].sum()
    if gross_loss == 0:
        return float("inf") if gross_profit > 0 else np.nan
    return float(gross_profit / gross_loss)


def expectancy(trades: pd.DataFrame) -> tuple[float, float]:
    if trades.empty:
        return np.nan, np.nan
    return float(trades["pnl"].mean()), float(trades["r_multiple"].mean())


def consecutive_losses(trades: pd.DataFrame) -> int:
    longest = 0
    current = 0
    if trades.empty:
        return 0
    for pnl in trades.sort_values("exit_date")["pnl"]:
        if pnl < 0:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return int(longest)


def largest_win_contribution_pct(trades: pd.DataFrame) -> float:
    if trades.empty:
        return np.nan
    wins = trades.loc[trades["pnl"] > 0, "pnl"]
    gross_profit = wins.sum()
    if gross_profit <= 0:
        return np.nan
    return float(wins.max() / gross_profit)


def sharpe_ratio(equity: pd.Series) -> float:
    returns = equity.pct_change().dropna()
    if returns.empty or returns.std() == 0:
        return np.nan
    return float(np.sqrt(252) * returns.mean() / returns.std())


def sortino_ratio(equity: pd.Series) -> float:
    returns = equity.pct_change().dropna()
    downside = returns[returns < 0]
    if returns.empty or downside.std() == 0:
        return np.nan
    return float(np.sqrt(252) * returns.mean() / downside.std())


def cagr(equity: pd.Series, dates: pd.Series) -> float:
    if equity.empty or len(equity) < 2:
        return np.nan
    start = float(equity.iloc[0])
    end = float(equity.iloc[-1])
    if start <= 0:
        return np.nan
    days = max((pd.Timestamp(dates.iloc[-1]) - pd.Timestamp(dates.iloc[0])).days, 1)
    years = days / 365.25
    return float((end / start) ** (1 / years) - 1)


def _metrics_for_equity_and_trades(
    name: str,
    trades: pd.DataFrame,
    equity: pd.Series,
    dates: pd.Series,
    starting_value: float,
    spy_total_return: float,
    time_in_market: float,
    project_targets: dict[str, float],
    hard_stop_applicable: bool = True,
) -> dict[str, Any]:
    final_equity = float(equity.iloc[-1]) if not equity.empty else starting_value
    total_return = final_equity / starting_value - 1.0 if starting_value else np.nan
    wins = trades.loc[trades["pnl"] > 0, "pnl"] if not trades.empty else pd.Series(dtype=float)
    losses = trades.loc[trades["pnl"] < 0, "pnl"] if not trades.empty else pd.Series(dtype=float)
    exp_dollars, exp_r = expectancy(trades)
    max_dd, max_dd_pct = max_drawdown(equity)
    return {
        "name": name,
        "total_return": total_return,
        "cagr": cagr(equity, dates) if not equity.empty else np.nan,
        "win_rate": float((trades["pnl"] > 0).mean()) if not trades.empty else np.nan,
        "average_win": float(wins.mean()) if not wins.empty else np.nan,
        "average_loss": float(losses.mean()) if not losses.empty else np.nan,
        "profit_factor": profit_factor(trades),
        "expectancy_per_trade_dollars": exp_dollars,
        "expectancy_per_trade_r": exp_r,
        "average_r_multiple": float(trades["r_multiple"].mean()) if not trades.empty else np.nan,
        "sharpe_ratio": sharpe_ratio(equity),
        "sortino_ratio": sortino_ratio(equity),
        "max_drawdown": max_dd,
        "max_drawdown_pct": max_dd_pct,
        "volatility": float(equity.pct_change().std() * np.sqrt(252)) if len(equity) > 1 else np.nan,
        "consecutive_losses": consecutive_losses(trades),
        "recovery_time_after_drawdown_days": recovery_time_days(equity),
        "benchmark_relative_return_vs_spy": total_return - spy_total_return,
        "number_of_trades": int(len(trades)),
        "time_in_market": time_in_market,
        "final_equity": final_equity,
        "target_300_reached": bool((equity >= project_targets["target_300"]).any()) if not equity.empty else False,
        "target_400_reached": bool((equity >= project_targets["target_400"]).any()) if not equity.empty else False,
        "project_stop_hit": (
            bool((equity <= project_targets["hard_stop"]).any())
            if hard_stop_applicable and not equity.empty
            else False
        ),
        "largest_winning_trade_contribution_pct": largest_win_contribution_pct(trades),
    }


def compute_strategy_metrics(
    trades: pd.DataFrame,
    equity_curve: pd.DataFrame,
    config: dict[str, Any],
    benchmark_curve: pd.DataFrame | None = None,
) -> pd.DataFrame:
    if equity_curve.empty:
        return pd.DataFrame()
    dates = pd.to_datetime(equity_curve["date"])
    starting = float(config["project"]["starting_equity"])
    target_info = {
        "target_300": starting + float(config["project"]["target_profit_1"]),
        "target_400": starting + float(config["project"]["target_profit_2"]),
        "hard_stop": float(config["project"]["hard_stop_equity"]),
    }

    spy_total_return = 0.0
    if benchmark_curve is not None and not benchmark_curve.empty and "SPY_buy_hold" in benchmark_curve:
        spy_total_return = benchmark_curve["SPY_buy_hold"].iloc[-1] / benchmark_curve["SPY_buy_hold"].iloc[0] - 1

    rows: list[dict[str, Any]] = []
    combined_time = float((equity_curve["open_positions"] > 0).mean()) if "open_positions" in equity_curve else np.nan
    combined_row = _metrics_for_equity_and_trades(
        "combined_tournament",
        trades,
        equity_curve["equity"],
        dates,
        starting,
        spy_total_return,
        combined_time,
        target_info,
        True,
    )
    if "absolute_floor_stop_active" in equity_curve or "trailing_drawdown_stop_active" in equity_curve:
        abs_hit = bool(equity_curve.get("absolute_floor_stop_active", pd.Series(False, index=equity_curve.index)).fillna(False).astype(bool).any())
        trail_hit = bool(equity_curve.get("trailing_drawdown_stop_active", pd.Series(False, index=equity_curve.index)).fillna(False).astype(bool).any())
        combined_row["project_stop_hit"] = abs_hit or trail_hit
    rows.append(combined_row)

    for strategy, cfg in config["strategies"].items():
        if not is_backtest_strategy(strategy, cfg):
            continue
        strategy_trades = trades.loc[trades["strategy"] == strategy].copy() if not trades.empty else trades.copy()
        pnl_col = f"{strategy}_total_pnl"
        open_col = f"{strategy}_open_positions"
        allocation = float(cfg.get("allocation", 0.0))
        strategy_equity = allocation + equity_curve[pnl_col] if pnl_col in equity_curve else pd.Series(allocation, index=equity_curve.index)
        time_in_market = float((equity_curve[open_col] > 0).mean()) if open_col in equity_curve else 0.0
        strategy_targets = {
            "target_300": allocation + float(config["project"]["target_profit_1"]),
            "target_400": allocation + float(config["project"]["target_profit_2"]),
            "hard_stop": float("-inf"),
        }
        rows.append(
            _metrics_for_equity_and_trades(
                strategy,
                strategy_trades,
                strategy_equity,
                dates,
                allocation,
                spy_total_return,
                time_in_market,
                strategy_targets,
                False,
            )
        )

    return pd.DataFrame(rows)


def monthly_returns(equity_curve: pd.DataFrame, benchmark_curve: pd.DataFrame | None = None) -> pd.DataFrame:
    if equity_curve.empty:
        return pd.DataFrame()
    combined = equity_curve[["date", "equity"]].copy()
    combined["date"] = pd.to_datetime(combined["date"])
    combined = combined.set_index("date").resample("ME").last().pct_change()
    combined = combined.rename(columns={"equity": "combined_tournament"})

    if benchmark_curve is not None and not benchmark_curve.empty:
        bench = benchmark_curve.copy()
        bench["date"] = pd.to_datetime(bench["date"])
        bench = bench.set_index("date").resample("ME").last().pct_change()
        combined = combined.join(bench, how="outer")
    return combined.reset_index()


def regime_performance(trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame(
            columns=["market_regime_at_entry", "trades", "total_pnl", "win_rate", "average_r_multiple"]
        )
    grouped = trades.groupby("market_regime_at_entry", dropna=False)
    return grouped.agg(
        trades=("trade_id", "count"),
        total_pnl=("pnl", "sum"),
        win_rate=("pnl", lambda s: float((s > 0).mean())),
        average_r_multiple=("r_multiple", "mean"),
    ).reset_index()


def build_benchmark_curves(
    data: dict[str, pd.DataFrame],
    dates: list[pd.Timestamp],
    config: dict[str, Any],
) -> pd.DataFrame:
    if not dates:
        return pd.DataFrame()
    initial = float(config["benchmarks"]["initial_value"])
    date_index = pd.Index(pd.to_datetime(dates), name="date")
    prices = {}
    for symbol, df in data.items():
        series = df.set_index("date")["close"].reindex(date_index).ffill()
        prices[symbol] = series
    price_frame = pd.DataFrame(prices, index=date_index)

    out = pd.DataFrame({"date": date_index})
    spy_symbol = config["benchmarks"]["spy"]
    if spy_symbol in price_frame and price_frame[spy_symbol].notna().any():
        spy = price_frame[spy_symbol].dropna()
        out = out.merge(
            (initial * spy / spy.iloc[0]).rename("SPY_buy_hold").reset_index(),
            on="date",
            how="left",
        )
        out["SPY_buy_hold"] = out["SPY_buy_hold"].ffill()
    else:
        out["SPY_buy_hold"] = initial

    returns = price_frame.pct_change(fill_method=None)
    valid_returns = returns.drop(columns=[], errors="ignore")
    basket_returns = valid_returns.mean(axis=1, skipna=True).fillna(0.0)
    out["equal_weight_basket"] = initial * (1.0 + basket_returns).cumprod().values

    cash_symbol = config["benchmarks"]["cash_proxy"]
    if cash_symbol in price_frame and price_frame[cash_symbol].notna().any():
        cash = price_frame[cash_symbol].dropna()
        cash_curve = initial * cash / cash.iloc[0]
        out = out.merge(cash_curve.rename("BIL_cash_proxy").reset_index(), on="date", how="left")
        out["BIL_cash_proxy"] = out["BIL_cash_proxy"].ffill().fillna(initial)
    else:
        out["BIL_cash_proxy"] = initial

    if {"SPY", "IEF"}.issubset(price_frame.columns):
        simple_returns = returns[["SPY", "IEF"]].fillna(0.0)
        out["sixty_forty_spy_ief"] = initial * (1.0 + 0.60 * simple_returns["SPY"] + 0.40 * simple_returns["IEF"]).cumprod().values

    spy_data = data.get("SPY")
    if spy_data is not None and "sma_200" in spy_data:
        spy_signal = spy_data.set_index("date")[["close", "sma_200"]].reindex(date_index).ffill()
        spy_returns = returns["SPY"].fillna(0.0) if "SPY" in returns else pd.Series(0.0, index=date_index)
        cash_returns = returns[cash_symbol].fillna(0.0) if cash_symbol in returns else pd.Series(0.0, index=date_index)
        trend_returns = np.where(spy_signal["close"] > spy_signal["sma_200"], spy_returns, cash_returns)
        out["SPY_200d_trend_model"] = initial * pd.Series(trend_returns, index=date_index).add(1.0).cumprod().values
    return out
