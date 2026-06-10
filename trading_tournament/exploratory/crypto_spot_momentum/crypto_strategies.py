from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd


CRYPTO_STRATEGY_VERSION = "tier1_crypto_spot_momentum_v1"


@dataclass(frozen=True)
class StrategySimulation:
    strategy: str
    equity_curve: pd.DataFrame
    weights: pd.DataFrame
    rebalances: pd.DataFrame
    asset_contributions: dict[str, float]
    turnover_estimate: float


def price_matrix(data: pd.DataFrame, field: str = "adj_close") -> pd.DataFrame:
    wide = data.pivot(index="date", columns="symbol", values=field).sort_index()
    return wide.ffill()


def _rebalance_mask(index: pd.DatetimeIndex, frequency: str) -> pd.Series:
    dates = pd.Series(index=index, data=index)
    if frequency == "monthly":
        return dates.dt.to_period("M").ne(dates.shift(-1).dt.to_period("M"))
    if frequency == "weekly":
        return dates.dt.to_period("W").ne(dates.shift(-1).dt.to_period("W"))
    if frequency == "daily":
        return pd.Series(True, index=index)
    raise ValueError(f"Unsupported rebalance frequency: {frequency}")


def _signal_to_effective_weights(
    signal_weights: pd.DataFrame,
    activation_start: pd.Timestamp | None = None,
) -> pd.DataFrame:
    if activation_start is not None:
        signal_weights = signal_weights.copy()
        signal_weights.loc[signal_weights.index < pd.Timestamp(activation_start), :] = np.nan
    shifted = signal_weights.shift(1)
    return shifted.ffill().fillna(0.0).clip(lower=0.0, upper=1.0)


def _empty_weights(prices: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(0.0, index=prices.index, columns=prices.columns)


def _empty_signal_weights(prices: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(np.nan, index=prices.index, columns=prices.columns)


def _cash_flat_weights(prices: pd.DataFrame) -> pd.DataFrame:
    return _empty_weights(prices)


def generate_signal_weights(
    data: pd.DataFrame,
    strategy_name: str,
    strategy_config: dict[str, Any] | None = None,
) -> pd.DataFrame:
    prices = price_matrix(data)
    weights = _empty_weights(prices)
    cfg = strategy_config or {}

    if prices.empty:
        return weights

    signal_weights = _empty_signal_weights(prices)
    if strategy_name == "cash_flat":
        return _empty_signal_weights(prices)

    if strategy_name == "BTC_buy_hold":
        if "BTC-USD" in prices.columns:
            signal_weights.loc[prices["BTC-USD"].notna(), :] = 0.0
            signal_weights.loc[prices["BTC-USD"].notna(), "BTC-USD"] = 1.0
        return signal_weights

    if strategy_name == "ETH_buy_hold":
        if "ETH-USD" in prices.columns:
            signal_weights.loc[prices["ETH-USD"].notna(), :] = 0.0
            signal_weights.loc[prices["ETH-USD"].notna(), "ETH-USD"] = 1.0
        return signal_weights

    frequency = cfg.get("rebalance_frequency", "weekly")
    rebalance_mask = _rebalance_mask(prices.index, frequency)

    assets = cfg.get("assets") or list(prices.columns)
    assets = [asset for asset in assets if asset in prices.columns]
    if not assets:
        return signal_weights

    if strategy_name == "crypto_buy_hold_equal_weight":
        for dt in prices.index[rebalance_mask]:
            signal_weights.loc[dt, :] = 0.0
            available = [asset for asset in assets if pd.notna(prices.loc[dt, asset])]
            if available:
                allocation = min(1.0, 1.0 / len(available))
                signal_weights.loc[dt, available] = allocation
        return signal_weights

    momentum_lookback = int(cfg.get("momentum_lookback_days", 90))
    sma_days = int(cfg.get("trend_sma_days", 200))
    returns_lookback = prices.pct_change(momentum_lookback, fill_method=None)
    sma = prices.rolling(sma_days, min_periods=sma_days).mean()

    for dt in prices.index[rebalance_mask]:
        signal_weights.loc[dt, :] = 0.0
        if strategy_name == "crypto_time_series_momentum":
            eligible = [
                asset
                for asset in assets
                if pd.notna(prices.loc[dt, asset])
                and pd.notna(sma.loc[dt, asset])
                and pd.notna(returns_lookback.loc[dt, asset])
                and prices.loc[dt, asset] > sma.loc[dt, asset]
                and returns_lookback.loc[dt, asset] > 0
            ]
            if eligible:
                signal_weights.loc[dt, eligible] = min(1.0, 1.0 / len(eligible))
        elif strategy_name == "crypto_cross_sectional_momentum":
            scores = returns_lookback.loc[dt, assets].dropna().sort_values(ascending=False)
            scores = scores[scores > 0]
            top = list(scores.head(int(cfg.get("top_n", 1))).index)
            if top:
                signal_weights.loc[dt, top] = min(1.0, 1.0 / len(top))
        elif strategy_name == "crypto_dual_momentum_cash_filter":
            scores = returns_lookback.loc[dt, assets].dropna().sort_values(ascending=False)
            top: list[str] = []
            for asset, score in scores.items():
                if (
                    score > 0
                    and pd.notna(sma.loc[dt, asset])
                    and pd.notna(prices.loc[dt, asset])
                    and prices.loc[dt, asset] > sma.loc[dt, asset]
                ):
                    top.append(asset)
                if len(top) >= int(cfg.get("top_n", 1)):
                    break
            if top:
                signal_weights.loc[dt, top] = min(1.0, 1.0 / len(top))
        else:
            raise ValueError(f"Unknown crypto exploratory strategy: {strategy_name}")

    return signal_weights


def generate_weights(
    data: pd.DataFrame,
    strategy_name: str,
    strategy_config: dict[str, Any] | None = None,
    activation_start: pd.Timestamp | None = None,
) -> pd.DataFrame:
    prices = price_matrix(data)
    if strategy_name == "cash_flat":
        return _cash_flat_weights(prices)
    signal_weights = generate_signal_weights(data, strategy_name, strategy_config)
    return _signal_to_effective_weights(signal_weights, activation_start=activation_start)


def simulate_from_weights(
    prices: pd.DataFrame,
    weights: pd.DataFrame,
    starting_equity: float,
    fee_slippage_per_side: float,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, float], float]:
    common_index = prices.index.intersection(weights.index)
    prices = prices.loc[common_index]
    weights = weights.loc[common_index].reindex(columns=prices.columns).fillna(0.0)
    weights = weights.clip(lower=0.0, upper=1.0)
    row_sums = weights.sum(axis=1)
    divisors = row_sums.where(row_sums <= 1.0, row_sums).replace(0.0, np.nan)
    weights = weights.div(divisors, axis=0).fillna(0.0)

    returns = prices.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    equity_values: list[float] = []
    prev_equity = float(starting_equity)
    prev_weights = pd.Series(0.0, index=prices.columns)
    asset_contrib = pd.Series(0.0, index=prices.columns)
    rebalance_rows: list[dict[str, Any]] = []
    total_turnover = 0.0

    for dt in prices.index:
        current_weights = weights.loc[dt].fillna(0.0)
        turnover = float((current_weights - prev_weights).abs().sum())
        cost = prev_equity * turnover * fee_slippage_per_side
        gross_asset_returns = current_weights * returns.loc[dt]
        gross_return = float(gross_asset_returns.sum())
        asset_contrib = asset_contrib.add(prev_equity * gross_asset_returns, fill_value=0.0)
        equity = max(0.0, prev_equity * (1.0 + gross_return) - cost)
        if turnover > 1e-9:
            total_turnover += turnover
            for symbol, target_weight in current_weights[current_weights > 0].items():
                rebalance_rows.append(
                    {
                        "date": dt.date().isoformat(),
                        "symbol": symbol,
                        "target_weight": float(target_weight),
                        "turnover": turnover,
                        "cost_estimate": float(cost),
                    }
                )
            if current_weights.sum() <= 0:
                rebalance_rows.append(
                    {
                        "date": dt.date().isoformat(),
                        "symbol": "CASH",
                        "target_weight": 1.0,
                        "turnover": turnover,
                        "cost_estimate": float(cost),
                    }
                )
        equity_values.append(equity)
        prev_equity = equity
        prev_weights = current_weights

    equity_curve = pd.DataFrame(
        {
            "date": prices.index,
            "equity": equity_values,
            "daily_return": pd.Series(equity_values, index=prices.index).pct_change(fill_method=None).fillna(0.0).to_numpy(),
        }
    )
    rebalances = pd.DataFrame(rebalance_rows)
    return equity_curve, rebalances, asset_contrib.to_dict(), total_turnover


def simulate_strategy(
    data: pd.DataFrame,
    strategy_name: str,
    strategy_config: dict[str, Any] | None,
    starting_equity: float,
    fee_slippage_per_side: float,
    activation_start: pd.Timestamp | None = None,
    start_date: pd.Timestamp | None = None,
    end_date: pd.Timestamp | None = None,
    precomputed_signal_weights: pd.DataFrame | None = None,
) -> StrategySimulation:
    prices = price_matrix(data)
    if prices.empty:
        empty_curve = pd.DataFrame(columns=["date", "equity", "daily_return"])
        return StrategySimulation(strategy_name, empty_curve, pd.DataFrame(), pd.DataFrame(), {}, 0.0)

    if strategy_name == "cash_flat":
        weights = _cash_flat_weights(prices)
    elif precomputed_signal_weights is not None:
        weights = _signal_to_effective_weights(precomputed_signal_weights, activation_start=activation_start)
    else:
        weights = generate_weights(data, strategy_name, strategy_config, activation_start=activation_start)
    if start_date is not None:
        start_date = pd.Timestamp(start_date)
        prices = prices.loc[prices.index >= start_date]
        weights = weights.loc[weights.index >= start_date]
    if end_date is not None:
        end_date = pd.Timestamp(end_date)
        prices = prices.loc[prices.index <= end_date]
        weights = weights.loc[weights.index <= end_date]

    if not weights.empty:
        weights.iloc[0] = 0.0
    equity_curve, rebalances, contrib, turnover = simulate_from_weights(
        prices=prices,
        weights=weights,
        starting_equity=starting_equity,
        fee_slippage_per_side=fee_slippage_per_side,
    )
    rebalances.insert(0, "strategy", strategy_name) if not rebalances.empty else None
    return StrategySimulation(strategy_name, equity_curve, weights, rebalances, contrib, turnover)


def strategy_is_benchmark(strategy_name: str, config: dict[str, Any]) -> bool:
    if strategy_name in {"BTC_buy_hold", "ETH_buy_hold", "cash_flat"}:
        return True
    return config.get("strategies", {}).get(strategy_name, {}).get("role") == "benchmark"
