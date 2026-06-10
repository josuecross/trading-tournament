from __future__ import annotations

import pandas as pd

from src.portfolio import Portfolio, calculate_position_size
from src.strategies import EntrySignal


def minimal_config() -> dict:
    return {
        "project": {
            "starting_equity": 3000.0,
            "hard_stop_equity": 2400.0,
            "target_profit_1": 300.0,
            "target_profit_2": 400.0,
            "max_daily_loss": 90.0,
            "max_weekly_loss": 180.0,
            "max_open_risk": 150.0,
            "max_cluster_open_risk": 90.0,
            "max_position_notional_pct": 0.40,
            "reserve_cash_buffer": 300.0,
            "warmup_days": 0,
        },
        "universe": {
            "symbols": ["SPY"],
            "clusters": {"equity_index": ["SPY"]},
        },
        "strategies": {
            "D_mean_reversion": {
                "enabled": True,
                "allocation": 250.0,
                "max_strategy_loss": 60.0,
                "risk_per_trade": 30.0,
                "max_positions": 2,
                "max_holding_days": 5,
                "initial_atr_multiple": 1.5,
            }
        },
    }


def test_position_sizing_does_not_exceed_risk_dollars():
    shares, actual_risk, reason = calculate_position_size(
        entry_price=100.0,
        stop_price=95.0,
        risk_dollars=45.0,
        account_equity=3000.0,
        available_cash=3000.0,
        max_notional_pct=0.40,
    )

    assert reason is None
    assert actual_risk <= 45.0
    assert shares == 9.0


def test_invalid_stop_distance_is_skipped():
    shares, actual_risk, reason = calculate_position_size(
        entry_price=100.0,
        stop_price=100.0,
        risk_dollars=45.0,
        account_equity=3000.0,
        available_cash=3000.0,
        max_notional_pct=0.40,
    )

    assert shares == 0.0
    assert actual_risk == 0.0
    assert reason == "invalid_stop_distance"


def test_skipped_signal_logging_has_required_reason_and_columns():
    portfolio = Portfolio(minimal_config(), slippage_pct=0.0005)
    signal = EntrySignal(
        date=pd.Timestamp("2020-01-01"),
        strategy="D_mean_reversion",
        symbol="SPY",
        requested_risk=30.0,
    )

    portfolio.attempt_open_position(
        signal=signal,
        entry_date=pd.Timestamp("2020-01-02"),
        entry_price=100.0,
        stop_price=100.0,
        target_price=None,
        project_equity=3000.0,
        strategy_pnl=0.0,
        market_regime="bull_normal_volatility",
    )
    skipped = portfolio.skipped_frame()

    assert skipped.loc[0, "reason_skipped"] == "invalid_stop_distance"
    assert set(
        [
            "date",
            "strategy",
            "symbol",
            "signal_type",
            "reason_skipped",
            "requested_risk",
            "total_open_risk",
            "cluster_open_risk",
            "strategy_status",
            "strategy_pnl",
            "project_equity",
            "notes",
        ]
    ).issubset(skipped.columns)
