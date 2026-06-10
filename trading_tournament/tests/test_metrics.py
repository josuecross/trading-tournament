from __future__ import annotations

import pandas as pd

from src.backtester import Backtester, simulate_long_intraday_exit
from src.metrics import expectancy, max_drawdown, profit_factor
from src.portfolio import Position


def test_max_drawdown_calculation():
    dd_dollars, dd_pct = max_drawdown(pd.Series([100.0, 120.0, 90.0, 130.0]))

    assert dd_dollars == -30.0
    assert round(dd_pct, 4) == -0.25


def test_profit_factor_and_expectancy_calculation():
    trades = pd.DataFrame({"pnl": [10.0, -5.0, 15.0], "r_multiple": [1.0, -0.5, 1.5]})

    assert profit_factor(trades) == 5.0
    exp_dollars, exp_r = expectancy(trades)
    assert round(exp_dollars, 4) == 6.6667
    assert round(exp_r, 4) == 0.6667


def _position(stop=95.0, target=110.0) -> Position:
    return Position(
        trade_id=1,
        strategy="C_swing_trend_pullback",
        symbol="SPY",
        entry_date=pd.Timestamp("2020-01-02"),
        entry_price=100.0,
        stop_price=stop,
        target_price=target,
        shares=1.0,
        risk_amount=5.0,
        requested_risk=5.0,
        market_regime_at_entry="bull_normal_volatility",
    )


def test_same_bar_stop_target_assumes_stop_first():
    row = pd.Series({"open": 100.0, "high": 111.0, "low": 94.0, "close": 105.0})

    exit_price, reason = simulate_long_intraday_exit(_position(), row, slippage_pct=0.0)

    assert exit_price == 95.0
    assert reason == "stop_loss"


def test_gap_through_stop_fills_at_open():
    row = pd.Series({"open": 93.0, "high": 100.0, "low": 92.0, "close": 96.0})

    exit_price, reason = simulate_long_intraday_exit(_position(), row, slippage_pct=0.0)

    assert exit_price == 93.0
    assert reason == "stop_loss_gap"


def _risk_config(hard_stop=2400.0, max_strategy_loss=1.0) -> dict:
    return {
        "project": {
            "starting_equity": 3000.0,
            "hard_stop_equity": hard_stop,
            "target_profit_1": 300.0,
            "target_profit_2": 400.0,
            "max_daily_loss": 90.0,
            "max_weekly_loss": 180.0,
            "max_open_risk": 150.0,
            "max_cluster_open_risk": 150.0,
            "max_position_notional_pct": 0.40,
            "reserve_cash_buffer": 300.0,
            "warmup_days": 0,
        },
        "universe": {"symbols": ["SPY"], "clusters": {"equity_index": ["SPY"]}},
        "strategy_order": ["D_mean_reversion"],
        "strategies": {
            "D_mean_reversion": {
                "enabled": True,
                "allocation": 250.0,
                "max_strategy_loss": max_strategy_loss,
                "risk_per_trade": 30.0,
                "max_positions": 2,
                "max_holding_days": 5,
                "initial_atr_multiple": 1.5,
            }
        },
        "benchmarks": {"spy": "SPY", "cash_proxy": "BIL", "initial_value": 3000.0},
    }


def _synthetic_mean_reversion_data() -> dict[str, pd.DataFrame]:
    dates = pd.date_range("2020-01-01", periods=6, freq="B")
    df = pd.DataFrame(
        {
            "date": dates,
            "open": [100, 100, 100, 100, 100, 100],
            "high": [101, 101, 101, 101, 101, 101],
            "low": [99, 98, 99, 99, 99, 99],
            "close": [100, 99, 100, 100, 100, 100],
            "adj_close": [100, 99, 100, 100, 100, 100],
            "volume": [1000] * 6,
            "sma_5": [99] * 6,
            "sma_50": [90] * 6,
            "sma_100": [90] * 6,
            "sma_200": [90] * 6,
            "ema_10": [100] * 6,
            "atr_20": [1.0] * 6,
            "atr_10": [1.0] * 6,
            "rsi_2": [5, 50, 50, 50, 50, 50],
            "bb_lower": [90] * 6,
            "bb_upper": [110] * 6,
            "rv_20": [0.1] * 6,
            "ret_63": [0.1] * 6,
            "ret_126": [0.1] * 6,
            "high_20": [99] * 6,
            "avg_volume_20": [1000] * 6,
            "atr_10_percentile": [0.2] * 6,
            "market_regime": ["bull_normal_volatility"] * 6,
        }
    )
    return {"SPY": df}


def test_no_same_bar_lookahead_entry_and_strategy_loss_budget_disable():
    bt = Backtester(_synthetic_mean_reversion_data(), _risk_config(max_strategy_loss=1.0))

    result = bt.run("test", "2020-01-01", "2020-01-10", slippage_pct=0.0)

    assert "D_mean_reversion" in result.killed_strategies
    assert not result.trades.empty
    assert pd.Timestamp(result.trades.loc[0, "entry_date"]) > pd.Timestamp(result.trades.loc[0, "entry_signal_date"])


def test_project_stop_enforcement():
    bt = Backtester(_synthetic_mean_reversion_data(), _risk_config(hard_stop=2999.0, max_strategy_loss=999.0))

    result = bt.run("test", "2020-01-01", "2020-01-10", slippage_pct=0.0)

    assert result.metadata["project_stop_hit"] is True
