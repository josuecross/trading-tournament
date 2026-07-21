from __future__ import annotations

import sys

import numpy as np
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from src.backtester import Backtester
from src.overlays import CPPIOverlay, IdentityOverlay, OverlayDataError
from src.portfolio import Portfolio, Position
from src.strategies import EntrySignal


def _project_config() -> dict:
    return {
        "starting_equity": 3000.0,
        "hard_stop_equity": 1000.0,
        "project_stop": {"mode": "absolute_floor", "absolute_floor_equity": 1000.0},
        "target_profit_1": 300.0,
        "target_profit_2": 400.0,
        "max_daily_loss": 900.0,
        "max_weekly_loss": 1800.0,
        "max_open_risk": 1000.0,
        "max_cluster_open_risk": 1000.0,
        "max_position_notional_pct": 1.0,
        "reserve_cash_buffer": 0.0,
        "warmup_days": 0,
    }


def _config(strategy: str = "D_mean_reversion") -> dict:
    return {
        "project": _project_config(),
        "universe": {"symbols": ["SPY", "BIL"], "clusters": {"equity_index": ["SPY"], "cash": ["BIL"]}},
        "strategy_order": [strategy],
        "strategies": {
            strategy: {
                "enabled": True,
                "allocation": 3000.0,
                "max_strategy_loss": 999.0,
                "risk_per_trade": 30.0,
                "max_positions": 3,
                "max_holding_days": 20,
                "initial_atr_multiple": 1.5,
                "trailing_atr_multiple": 2.5,
            }
        },
        "benchmarks": {"spy": "SPY", "cash_proxy": "BIL", "initial_value": 3000.0},
    }


def _synthetic_data() -> dict[str, pd.DataFrame]:
    dates = pd.date_range("2020-01-01", periods=10, freq="B")
    frame = pd.DataFrame(
        {
            "date": dates,
            "open": [100.0] * 10,
            "high": [102.0] * 10,
            "low": [99.0] * 10,
            "close": [100.0, 99.0, 100.5, 101.0, 101.5, 102.0, 102.5, 103.0, 103.5, 104.0],
            "adj_close": [100.0, 99.0, 100.5, 101.0, 101.5, 102.0, 102.5, 103.0, 103.5, 104.0],
            "volume": [1000] * 10,
            "sma_5": [99.0] * 10,
            "sma_50": [90.0] * 10,
            "sma_100": [90.0] * 10,
            "sma_200": [90.0] * 10,
            "ema_10": [100.0] * 10,
            "atr_20": [1.0] * 10,
            "atr_10": [1.0] * 10,
            "rsi_2": [5.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0],
            "bb_lower": [90.0] * 10,
            "bb_upper": [110.0] * 10,
            "rv_20": [0.1] * 10,
            "ret_63": [0.1] * 10,
            "ret_126": [0.1] * 10,
            "ret_252": [0.1] * 10,
            "high_20": [99.0] * 10,
            "avg_volume_20": [1000.0] * 10,
            "atr_10_percentile": [0.2] * 10,
            "market_regime": ["bull_normal_volatility"] * 10,
        }
    )
    return {"SPY": frame}


def _overlay(calendar: list[pd.Timestamp] | None = None) -> CPPIOverlay:
    overlay = CPPIOverlay(risky_assets={"SPY"}, safe_assets={"BIL"})
    calendar = calendar or list(pd.date_range("2020-01-31", periods=3, freq="B"))
    overlay.bind(
        run_id="unit",
        base_strategy_id="base",
        base_strategy_hash="hash",
        data={},
        indexed_data={},
        calendar=calendar,
        config=_config(),
    )
    return overlay


def _target(symbol: str, weight: float, date: str = "2020-01-31") -> EntrySignal:
    return EntrySignal(
        date=pd.Timestamp(date),
        strategy="N2_absolute_trend_taa",
        symbol=symbol,
        requested_risk=1.0,
        metadata={"target_weight": weight, "atr": 1.0},
    )


def test_initial_five_year_floor_and_risky_exposure_are_source_exact() -> None:
    overlay = _overlay([pd.Timestamp("2020-01-31")])
    state = overlay.cppi_state(pd.Timestamp("2020-01-31"), 3000.0)

    expected_floor = 3000.0 * np.exp(-0.05 * 5.0)
    expected_fraction = 3.0 * (3000.0 - expected_floor) / 3000.0
    assert state["floor"] == pytest.approx(expected_floor)
    assert state["risky_fraction"] == pytest.approx(expected_fraction)
    assert state["risky_fraction"] == pytest.approx(0.6636, abs=0.001)


def test_floor_grows_to_guarantee_at_maturity() -> None:
    overlay = _overlay([pd.Timestamp("2020-01-31")])
    maturity = overlay.episode_maturity
    assert maturity is not None

    assert overlay.floor_value(maturity) == pytest.approx(3000.0)


def test_risky_exposure_rises_with_cushion_and_falls_when_cushion_contracts() -> None:
    overlay = _overlay([pd.Timestamp("2020-01-31")])
    low = overlay.cppi_state(pd.Timestamp("2020-01-31"), 2800.0)
    high = overlay.cppi_state(pd.Timestamp("2020-01-31"), 3300.0)

    assert high["risky_fraction"] > low["risky_fraction"]
    assert low["risky_fraction"] < 0.6636


def test_managed_targets_never_exceed_base_or_one_hundred_percent() -> None:
    overlay = _overlay([pd.Timestamp("2020-01-31"), pd.Timestamp("2020-02-03")])
    portfolio = Portfolio(_config(), 0.0)
    batch = overlay.on_signal_batch(
        date=pd.Timestamp("2020-01-31"),
        entries=[_target("SPY", 0.90), _target("BIL", 0.10)],
        exits=[],
        portfolio=portfolio,
        rows={},
        equity=3000.0,
        pending_exit_ids=set(),
    )

    assert len(batch.entries) == 1
    managed = batch.entries[0].metadata["target_weight"]
    assert managed <= 0.90
    assert managed <= 1.0
    assert overlay.leverage_allowed is False


def test_safe_account_accrues_exactly_and_reconciles_with_nav() -> None:
    portfolio = Portfolio(_config(), 0.0)
    portfolio.transfer_cash_to_synthetic_safe(1000.0)
    accrued = portfolio.accrue_synthetic_safe_account(pd.Timestamp("2020-01-02"), 0.05)
    accrued += portfolio.accrue_synthetic_safe_account(pd.Timestamp("2020-01-03"), 0.05)

    expected = 1000.0 * np.exp(0.05 / 365.0)
    equity, _ = portfolio.mark_to_market({})
    assert portfolio.synthetic_safe_account_value == pytest.approx(expected)
    assert accrued == pytest.approx(expected - 1000.0)
    assert equity == pytest.approx(portfolio.cash + portfolio.synthetic_safe_account_value)


def test_month_end_calculation_is_submitted_for_next_open_execution() -> None:
    calendar = [pd.Timestamp("2020-01-31"), pd.Timestamp("2020-02-03")]
    overlay = _overlay(calendar)
    portfolio = Portfolio(_config(), 0.0)
    portfolio.transfer_cash_to_synthetic_safe(100.0)
    portfolio.accrue_synthetic_safe_account(pd.Timestamp("2020-01-31"), 0.05)

    overlay.on_signal_batch(
        date=pd.Timestamp("2020-01-31"),
        entries=[_target("SPY", 0.80), _target("BIL", 0.20)],
        exits=[],
        portfolio=portfolio,
        rows={},
        equity=3000.0,
        pending_exit_ids=set(),
    )
    assert overlay.pending_safe_release_date == pd.Timestamp("2020-02-03")
    resize_events = overlay.events_frame()[overlay.events_frame()["reason_code"] == "cppi_resize"]
    assert resize_events["data_quality_flags"].str.contains('"same_close_execution":false').any()

    overlay.on_before_order_fills(date=pd.Timestamp("2020-02-03"), portfolio=portfolio, rows={})
    assert portfolio.synthetic_safe_account_value > 100.0
    assert portfolio.cash == pytest.approx(2900.0)


def test_residual_broker_cash_sweeps_to_synthetic_safe_after_next_open_fills() -> None:
    overlay = _overlay([pd.Timestamp("2020-01-31"), pd.Timestamp("2020-02-03")])
    portfolio = Portfolio(_config(), 0.0)

    overlay.on_signal_batch(
        date=pd.Timestamp("2020-01-31"),
        entries=[_target("SPY", 0.50)],
        exits=[],
        portfolio=portfolio,
        rows={},
        equity=3000.0,
        pending_exit_ids=set(),
    )
    assert overlay.pending_safe_sweep_date == pd.Timestamp("2020-02-03")

    overlay.process_position_lifecycle(
        date=pd.Timestamp("2020-02-03"),
        portfolio=portfolio,
        rows={},
        slippage_pct=0.0,
    )

    assert portfolio.cash == pytest.approx(0.0)
    assert portfolio.synthetic_safe_account_value == pytest.approx(3000.0)
    transfers = overlay.events_frame()[overlay.events_frame()["reason_code"] == "cppi_safe_account_transfer"]
    assert transfers["proposed_order"].str.contains("broker_cash_to_synthetic_safe").any()


def test_gap_below_floor_records_shortfall_without_repairing_capital() -> None:
    overlay = _overlay([pd.Timestamp("2020-01-31"), pd.Timestamp("2020-02-03")])
    portfolio = Portfolio(_config(), 0.0)
    portfolio.cash = overlay.floor_value(pd.Timestamp("2020-01-31")) - 10.0

    overlay.process_position_lifecycle(
        date=pd.Timestamp("2020-01-31"),
        portfolio=portfolio,
        rows={},
        slippage_pct=0.0,
    )

    equity, _ = portfolio.mark_to_market({})
    assert not overlay.cash_locked
    assert overlay.floor_shortfall_amount == pytest.approx(10.0)
    assert equity == pytest.approx(overlay.floor_value(pd.Timestamp("2020-01-31")) - 10.0)
    assert "cppi_intraperiod_floor_shortfall" in set(overlay.events_frame()["reason_code"])


def test_cash_lock_is_permanent_and_blocks_risky_reentry_before_maturity() -> None:
    overlay = _overlay([pd.Timestamp("2020-01-31"), pd.Timestamp("2020-02-03")])
    portfolio = Portfolio(_config(), 0.0)
    portfolio.cash = overlay.floor_value(pd.Timestamp("2020-01-31")) - 1.0
    overlay.process_position_lifecycle(
        date=pd.Timestamp("2020-01-31"),
        portfolio=portfolio,
        rows={},
        slippage_pct=0.0,
    )

    batch = overlay.on_signal_batch(
        date=pd.Timestamp("2020-01-31"),
        entries=[_target("SPY", 0.80)],
        exits=[],
        portfolio=portfolio,
        rows={},
        equity=portfolio.cash,
        pending_exit_ids=set(),
    )

    assert overlay.cash_locked
    assert batch.entries == []
    assert "cppi_cash_lock" in set(overlay.events_frame()["reason_code"])


def test_fail_closed_for_missing_nav_unsupported_intent_and_ambiguous_mapping() -> None:
    overlay = _overlay([pd.Timestamp("2020-01-31")])
    portfolio = Portfolio(_config(), 0.0)
    with pytest.raises(OverlayDataError):
        overlay.on_signal_batch(
            date=pd.Timestamp("2020-01-31"),
            entries=[_target("SPY", 0.80)],
            exits=[],
            portfolio=portfolio,
            rows={},
            equity=np.nan,
            pending_exit_ids=set(),
        )

    with pytest.raises(OverlayDataError):
        overlay.on_signal_batch(
            date=pd.Timestamp("2020-01-31"),
            entries=[EntrySignal(pd.Timestamp("2020-01-31"), "B_ETF_trend_following", "SPY", 10.0, metadata={})],
            exits=[],
            portfolio=portfolio,
            rows={},
            equity=3000.0,
            pending_exit_ids=set(),
        )

    with pytest.raises(OverlayDataError):
        overlay.on_signal_batch(
            date=pd.Timestamp("2020-01-31"),
            entries=[_target("QQQ", 0.80)],
            exits=[],
            portfolio=portfolio,
            rows={},
            equity=3000.0,
            pending_exit_ids=set(),
        )


def test_negative_safe_account_transfers_are_rejected() -> None:
    portfolio = Portfolio(_config(), 0.0)
    with pytest.raises(ValueError):
        portfolio.transfer_cash_to_synthetic_safe(-1.0)
    with pytest.raises(ValueError):
        portfolio.transfer_synthetic_safe_to_cash(1.0)


def test_base_plus_identity_equivalence_remains_unchanged() -> None:
    data = _synthetic_data()
    cfg = _config()
    base = Backtester(data, cfg).run("base", "2020-01-01", "2020-01-20", 0.0, lightweight_outputs=True)
    identity = Backtester(data, cfg).run(
        "identity",
        "2020-01-01",
        "2020-01-20",
        0.0,
        lightweight_outputs=True,
        overlay=IdentityOverlay(),
        run_id="identity-unit",
    )

    assert_frame_equal(base.equity_curve, identity.equity_curve)
    assert_frame_equal(base.trades, identity.trades)


def test_no_paper_demo_live_broker_modules_are_imported_by_cppi_overlay() -> None:
    forbidden = ("alpaca", "broker", "live", "paper_forward")
    loaded = {name for name in sys.modules if any(token in name.lower() for token in forbidden)}
    assert not any(name.startswith("alpaca") for name in loaded)
    assert "src.overlays" in sys.modules
