from __future__ import annotations

import sys

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from src.backtester import Backtester
from src.overlays import (
    ExposureCapsOverlay,
    IdentityOverlay,
    LaggedVolatilityTargetOverlay,
    OverlayDataError,
    RebalanceBandOverlay,
    TimeStopOverlay,
    WideATRCatastrophicStopOverlay,
    simulate_atr_stop_exit,
)
from src.portfolio import Portfolio, Position, entry_slippage_cost_from_fill, exit_slippage_cost_from_fill
from src.strategies import EntrySignal, ExitSignal
from src.trade_management_calibration import (
    INVALID_INSUFFICIENT_CALIBRATION_HISTORY,
    INVALID_NON_DYNAMIC_VOLATILITY_SCALER,
    calibrate_volatility_target_from_equity,
    dynamic_scale_diagnostics_from_values,
    static_control_scale_from_capped_scales,
)
from run_trade_management_overlay_canonical_exploratory import (
    CLASS_APPLICABLE_NO_EFFECT,
    CLASS_NOT_APPLICABLE_STRATEGY_LIFECYCLE,
    classify_exposure_caps_trial,
    classify_wide_atr_trial,
)


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
        "universe": {"symbols": ["SPY", "QQQ", "IWM"], "clusters": {"equity_index": ["SPY", "QQQ", "IWM"]}},
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


def _synthetic_d_data() -> dict[str, pd.DataFrame]:
    dates = pd.date_range("2020-01-01", periods=10, freq="B")
    df = pd.DataFrame(
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
    return {"SPY": df}


def _bind(overlay, data: dict[str, pd.DataFrame] | None = None) -> None:
    data = data or {}
    indexed = {symbol: frame.set_index("date", drop=False) for symbol, frame in data.items()}
    overlay.bind(
        run_id="unit",
        base_strategy_id="base",
        base_strategy_hash="hash",
        data=data,
        indexed_data=indexed,
        calendar=[],
        config=_config(),
    )


def _target_signal(symbol: str, weight: float) -> EntrySignal:
    return EntrySignal(
        date=pd.Timestamp("2020-01-31"),
        strategy="N2_absolute_trend_taa",
        symbol=symbol,
        requested_risk=1.0,
        metadata={"target_weight": weight, "atr": 1.0},
    )


def _position(shares: float = 1.0, bars_held: int = 0) -> Position:
    return Position(
        trade_id=1,
        strategy="B_ETF_trend_following",
        symbol="SPY",
        entry_date=pd.Timestamp("2020-01-02"),
        entry_price=100.0,
        stop_price=90.0,
        target_price=None,
        shares=shares,
        risk_amount=10.0,
        requested_risk=10.0,
        market_regime_at_entry="bull_normal_volatility",
        bars_held=bars_held,
    )


def _equity_curve_from_returns(returns: list[float], start: str = "2019-01-01") -> pd.DataFrame:
    dates = pd.date_range(start, periods=len(returns) + 1, freq="B")
    equity = [1000.0]
    for value in returns:
        equity.append(equity[-1] * (1.0 + value))
    return pd.DataFrame({"date": dates, "equity": equity})


def test_identity_overlay_reproduces_base_backtest_exactly() -> None:
    data = _synthetic_d_data()
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
    assert identity.overlay_events["reason_code"].isin({"identity_pass"}).all()


def test_overlay_disabled_repeated_runs_are_deterministic() -> None:
    first = Backtester(_synthetic_d_data(), _config()).run("base", "2020-01-01", "2020-01-20", 0.0, lightweight_outputs=True)
    second = Backtester(_synthetic_d_data(), _config()).run("base", "2020-01-01", "2020-01-20", 0.0, lightweight_outputs=True)

    assert_frame_equal(first.equity_curve, second.equity_curve)
    assert_frame_equal(first.trades, second.trades)


def test_trial_order_independence_for_base_and_identity_controls() -> None:
    data = _synthetic_d_data()
    cfg = _config()

    first_base = Backtester(data, cfg).run("base", "2020-01-01", "2020-01-20", 0.0, lightweight_outputs=True)
    identity = Backtester(data, cfg).run(
        "identity",
        "2020-01-01",
        "2020-01-20",
        0.0,
        lightweight_outputs=True,
        overlay=IdentityOverlay(),
        run_id="order-identity",
    )
    second_base = Backtester(data, cfg).run("base", "2020-01-01", "2020-01-20", 0.0, lightweight_outputs=True)

    assert_frame_equal(first_base.equity_curve, second_base.equity_curve)
    assert_frame_equal(first_base.trades, second_base.trades)
    assert_frame_equal(first_base.equity_curve, identity.equity_curve)
    assert_frame_equal(first_base.trades, identity.trades)


def test_volatility_calibration_uses_only_dates_before_evaluation() -> None:
    returns = [0.001 + (idx % 7) * 0.0001 for idx in range(280)] + [0.50] * 20
    equity = _equity_curve_from_returns(returns)
    eval_start = equity["date"].iloc[281]

    calibration = calibrate_volatility_target_from_equity(equity, evaluation_start=eval_start)

    assert calibration.status == "valid"
    assert pd.Timestamp(calibration.selected_returns.index.max()) < pd.Timestamp(eval_start)
    assert calibration.selected_returns.max() < 0.50


def test_volatility_calibration_selects_exactly_252_valid_returns_when_available() -> None:
    returns = [0.0005 + (idx % 11) * 0.0001 for idx in range(320)]
    equity = _equity_curve_from_returns(returns)

    calibration = calibrate_volatility_target_from_equity(
        equity,
        evaluation_start=equity["date"].iloc[-1] + pd.Timedelta(days=1),
    )

    assert calibration.status == "valid"
    assert calibration.selected_return_count == 252
    assert len(calibration.selected_returns) == 252


def test_volatility_calibration_target_is_median_positive_rolling_volatility() -> None:
    returns = [0.001 * ((idx % 9) - 4) for idx in range(300)]
    equity = _equity_curve_from_returns(returns)
    calibration = calibrate_volatility_target_from_equity(
        equity,
        evaluation_start=equity["date"].iloc[-1] + pd.Timedelta(days=1),
    )
    expected = calibration.selected_returns.rolling(window=63, min_periods=63).std()
    expected = expected * (252 ** 0.5)
    expected = expected[(expected > 0.0) & expected.notna()].median()

    assert calibration.status == "valid"
    assert calibration.target_volatility == pytest.approx(float(expected))


def test_volatility_calibration_preserves_zero_returns() -> None:
    returns = [0.0 if idx % 5 else 0.002 for idx in range(300)]
    equity = _equity_curve_from_returns(returns)

    calibration = calibrate_volatility_target_from_equity(
        equity,
        evaluation_start=equity["date"].iloc[-1] + pd.Timedelta(days=1),
    )

    assert calibration.status == "valid"
    assert int((calibration.selected_returns == 0.0).sum()) > 0
    assert calibration.selected_return_count == 252


def test_volatility_calibration_insufficient_history_fails_closed() -> None:
    equity = _equity_curve_from_returns([0.001] * 100)

    calibration = calibrate_volatility_target_from_equity(
        equity,
        evaluation_start=equity["date"].iloc[-1] + pd.Timedelta(days=1),
    )

    assert calibration.status == "invalid"
    assert calibration.invalidity_code == INVALID_INSUFFICIENT_CALIBRATION_HISTORY


def test_dynamic_behavior_guard_rejects_bound_concentration() -> None:
    diagnostics = dynamic_scale_diagnostics_from_values(
        estimated_volatility=[0.4] * 100,
        raw_scale=[0.1] * 100,
        capped_scale=[0.25] * 100,
        target_volatility=0.04,
    )

    assert diagnostics["status"] == INVALID_NON_DYNAMIC_VOLATILITY_SCALER


def test_static_control_scalar_is_calibration_derived_median_scale() -> None:
    assert static_control_scale_from_capped_scales([0.25, 0.50, 0.75]) == pytest.approx(0.50)


@pytest.mark.parametrize(
    ("weight", "expected_count"),
    [
        (0.0099, 0),
        (0.0100, 1),
        (0.0101, 1),
    ],
)
def test_rebalance_band_threshold_boundary_values(weight: float, expected_count: int) -> None:
    overlay = RebalanceBandOverlay(min_weight_delta=0.01, min_nav_order_pct=0.001)
    _bind(overlay)
    portfolio = Portfolio(_config("N2_absolute_trend_taa"), 0.0)
    batch = overlay.on_signal_batch(
        date=pd.Timestamp("2020-01-31"),
        entries=[_target_signal("SPY", weight)],
        exits=[],
        portfolio=portfolio,
        rows={},
        equity=1000.0,
        pending_exit_ids=set(),
    )

    assert len(batch.entries) == expected_count


def test_rebalance_band_nav_threshold_suppresses_tiny_order() -> None:
    overlay = RebalanceBandOverlay(min_weight_delta=0.0, min_nav_order_pct=0.001)
    _bind(overlay)
    batch = overlay.on_signal_batch(
        date=pd.Timestamp("2020-01-31"),
        entries=[_target_signal("SPY", 0.0009)],
        exits=[],
        portfolio=Portfolio(_config("N2_absolute_trend_taa"), 0.0),
        rows={},
        equity=1000.0,
        pending_exit_ids=set(),
    )

    assert batch.entries == []
    assert overlay.events_frame().iloc[-1]["reason_code"] == "below_nav_order"


def test_weight_only_overlays_noop_on_risk_dollar_intents_with_explicit_unit() -> None:
    signal = EntrySignal(
        date=pd.Timestamp("2020-01-31"),
        strategy="B_ETF_trend_following",
        symbol="SPY",
        requested_risk=45.0,
        metadata={"atr": 1.0},
    )
    rebalance = RebalanceBandOverlay()
    exposure = ExposureCapsOverlay()
    _bind(rebalance)
    _bind(exposure)

    rebalance_batch = rebalance.on_signal_batch(
        date=signal.date,
        entries=[signal],
        exits=[],
        portfolio=Portfolio(_config("B_ETF_trend_following"), 0.0),
        rows={},
        equity=1000.0,
        pending_exit_ids=set(),
    )
    exposure_batch = exposure.on_signal_batch(
        date=signal.date,
        entries=[signal],
        exits=[],
        portfolio=Portfolio(_config("B_ETF_trend_following"), 0.0),
        rows={},
        equity=1000.0,
        pending_exit_ids=set(),
    )

    assert rebalance_batch.entries == [signal]
    assert exposure_batch.entries == [signal]
    assert rebalance.events_frame().iloc[-1]["reason_code"] == "unsupported_intent_unit"
    assert exposure.events_frame().iloc[-1]["target_unit"] == "risk_amount_dollars"

    rebalance.on_signal_batch(
        date=signal.date + pd.Timedelta(days=1),
        entries=[signal],
        exits=[],
        portfolio=Portfolio(_config("B_ETF_trend_following"), 0.0),
        rows={},
        equity=1000.0,
        pending_exit_ids=set(),
    )
    assert int((rebalance.events_frame()["reason_code"] == "unsupported_intent_unit").sum()) == 1


def test_rebalance_band_does_not_suppress_unpaired_liquidation_exit() -> None:
    overlay = RebalanceBandOverlay(min_weight_delta=0.01, min_nav_order_pct=0.001)
    _bind(overlay)
    portfolio = Portfolio(_config("N2_absolute_trend_taa"), 0.0)
    pos = _position(bars_held=5)
    pos.strategy = "N2_absolute_trend_taa"
    portfolio.positions.append(pos)
    exit_signal = ExitSignal(
        date=pd.Timestamp("2020-01-31"),
        strategy=pos.strategy,
        symbol=pos.symbol,
        trade_id=pos.trade_id,
        reason="taa_trend_exit",
    )

    batch = overlay.on_signal_batch(
        date=exit_signal.date,
        entries=[],
        exits=[exit_signal],
        portfolio=portfolio,
        rows={"SPY": pd.Series({"close": 100.0})},
        equity=1000.0,
        pending_exit_ids=set(),
    )

    assert batch.exits == [exit_signal]


def test_lagged_volatility_scale_floor_and_cap() -> None:
    signal = _target_signal("SPY", 1.0)
    floor_overlay = LaggedVolatilityTargetOverlay(target_volatility=0.10, scale_floor=0.25, scale_cap=1.0)
    floor_overlay._estimate_volatility = lambda date, weights: (1.0, "2020-01-30")  # type: ignore[method-assign]
    floor_batch = floor_overlay.on_signal_batch(
        date=pd.Timestamp("2020-01-31"),
        entries=[signal],
        exits=[],
        portfolio=Portfolio(_config("N2_absolute_trend_taa"), 0.0),
        rows={},
        equity=1000.0,
        pending_exit_ids=set(),
    )

    cap_overlay = LaggedVolatilityTargetOverlay(target_volatility=0.10, scale_floor=0.25, scale_cap=1.0)
    cap_overlay._estimate_volatility = lambda date, weights: (0.01, "2020-01-30")  # type: ignore[method-assign]
    cap_batch = cap_overlay.on_signal_batch(
        date=pd.Timestamp("2020-01-31"),
        entries=[signal],
        exits=[],
        portfolio=Portfolio(_config("N2_absolute_trend_taa"), 0.0),
        rows={},
        equity=1000.0,
        pending_exit_ids=set(),
    )

    assert floor_batch.entries[0].metadata["target_weight"] == pytest.approx(0.25)
    assert cap_batch.entries[0].metadata["target_weight"] == pytest.approx(1.0)


def test_lagged_volatility_degenerate_target_fails_closed() -> None:
    with pytest.raises(OverlayDataError, match="INVALID_DEGENERATE_VOLATILITY_CALIBRATION"):
        LaggedVolatilityTargetOverlay(target_volatility=0.0)


def test_lagged_volatility_window_excludes_signal_bar() -> None:
    dates = pd.date_range("2020-01-01", periods=70, freq="B")
    close = pd.Series(100.0 + (pd.Series(range(70)) % 5).to_numpy(), index=dates)
    close.iloc[-1] = 1000.0
    data = {"SPY": pd.DataFrame({"date": dates, "close": close.values})}
    overlay = LaggedVolatilityTargetOverlay(target_volatility=0.10, lookback=63)
    _bind(overlay, data)

    returns, lookback_end = overlay._returns_window("SPY", dates[-1])

    assert lookback_end == dates[-2].date().isoformat()
    assert returns.abs().max() < 1.0


def test_exposure_caps_clip_multi_asset_targets_and_leave_cash() -> None:
    overlay = ExposureCapsOverlay(max_gross_exposure=1.0)
    _bind(overlay)
    batch = overlay.on_signal_batch(
        date=pd.Timestamp("2020-01-31"),
        entries=[_target_signal("SPY", 0.60), _target_signal("QQQ", 0.30), _target_signal("IWM", 0.20)],
        exits=[],
        portfolio=Portfolio(_config("N2_absolute_trend_taa"), 0.0),
        rows={},
        equity=1000.0,
        pending_exit_ids=set(),
    )
    targets = {entry.symbol: entry.metadata["target_weight"] for entry in batch.entries}

    assert targets == pytest.approx({"SPY": 0.35, "QQQ": 0.30, "IWM": 0.20})
    assert overlay.events_frame()["state_after"].str.contains("cash_weight_created").any()


def test_no_effect_cap_trial_classification() -> None:
    events = pd.DataFrame(
        [
            {
                "reason_code": "overlay_initialized",
                "decision_type": "pass_through",
            }
        ]
    )

    assert classify_exposure_caps_trial(events) == CLASS_APPLICABLE_NO_EFFECT


def test_atr_stop_activates_only_after_entry_bar() -> None:
    overlay = WideATRCatastrophicStopOverlay(atr_lookback=20, atr_multiple=4.0)
    _bind(overlay)
    portfolio = Portfolio(_config("B_ETF_trend_following"), 0.0)
    pos = _position(bars_held=0)
    portfolio.positions.append(pos)
    signal = EntrySignal(
        date=pd.Timestamp("2020-01-01"),
        strategy=pos.strategy,
        symbol=pos.symbol,
        requested_risk=10.0,
        metadata={"atr": 1.0},
    )
    overlay.on_after_entry_fill(
        date=pd.Timestamp("2020-01-02"),
        signal=signal,
        position=pos,
        proposed_order={},
        actual_fill={"fill_price": 100.0},
        modeled_cost=0.0,
    )
    row = pd.Series({"open": 100.0, "high": 101.0, "low": 95.0, "close": 96.0})

    overlay.process_position_lifecycle(date=pd.Timestamp("2020-01-02"), portfolio=portfolio, rows={"SPY": row}, slippage_pct=0.0)
    assert len(portfolio.positions) == 1

    pos.bars_held = 1
    overlay.process_position_lifecycle(date=pd.Timestamp("2020-01-03"), portfolio=portfolio, rows={"SPY": row}, slippage_pct=0.0)
    assert portfolio.positions == []
    assert portfolio.closed_trades[-1]["exit_price"] == pytest.approx(96.0)


def test_atr_overlay_does_not_preempt_base_stop_on_same_bar() -> None:
    overlay = WideATRCatastrophicStopOverlay(atr_lookback=20, atr_multiple=4.0)
    _bind(overlay)
    portfolio = Portfolio(_config("B_ETF_trend_following"), 0.0)
    pos = _position(bars_held=1)
    pos.stop_price = 98.0
    portfolio.positions.append(pos)
    pos.metadata["trade_management_overlay"] = {
        "OVL-STP-001": {
            "entry_atr": 1.0,
            "atr_lookback": 20,
            "atr_multiple": 4.0,
            "stop_level": 96.0,
            "active_after_bars_held": 1,
        }
    }
    row = pd.Series({"open": 100.0, "high": 101.0, "low": 95.0, "close": 96.0})

    overlay.process_position_lifecycle(date=pd.Timestamp("2020-01-03"), portfolio=portfolio, rows={"SPY": row}, slippage_pct=0.0)

    assert len(portfolio.positions) == 1
    assert portfolio.closed_trades == []
    assert overlay.events_frame().iloc[-1]["reason_code"] == "base_stop_precedence"
    assert classify_wide_atr_trial(overlay.events_frame()) == CLASS_NOT_APPLICABLE_STRATEGY_LIFECYCLE


def test_atr_stop_normal_touch_gap_and_short_symmetry() -> None:
    long_pos = _position(shares=1.0)
    short_pos = _position(shares=-1.0)

    normal = simulate_atr_stop_exit(long_pos, pd.Series({"open": 100.0, "high": 101.0, "low": 95.0, "close": 96.0}), 96.0, 0.0)
    gap = simulate_atr_stop_exit(long_pos, pd.Series({"open": 94.0, "high": 100.0, "low": 93.0, "close": 96.0}), 96.0, 0.0)
    short_normal = simulate_atr_stop_exit(short_pos, pd.Series({"open": 100.0, "high": 105.0, "low": 99.0, "close": 104.0}), 104.0, 0.0)
    short_gap = simulate_atr_stop_exit(short_pos, pd.Series({"open": 106.0, "high": 107.0, "low": 101.0, "close": 104.0}), 104.0, 0.0)

    assert normal is not None and normal.fill_price == pytest.approx(96.0)
    assert gap is not None and gap.fill_price == pytest.approx(94.0)
    assert short_normal is not None and short_normal.fill_price == pytest.approx(104.0)
    assert short_gap is not None and short_gap.fill_price == pytest.approx(106.0)


def test_atr_stop_missing_ohlc_fails_fast() -> None:
    with pytest.raises(Exception, match="Missing required OHLC"):
        simulate_atr_stop_exit(_position(), pd.Series({"open": 100.0, "high": 101.0, "close": 96.0}), 96.0, 0.0)


def test_slippage_cost_estimate_uses_unadjusted_reference_fill_once() -> None:
    assert entry_slippage_cost_from_fill(100.05, 10.0, 0.0005) == pytest.approx(0.5)
    assert exit_slippage_cost_from_fill(99.95, 10.0, 0.0005, "signal_exit") == pytest.approx(0.5)
    assert exit_slippage_cost_from_fill(100.0, 10.0, 0.0005, "final_mark_to_market") == 0.0


def test_time_stop_bar_count_boundaries() -> None:
    overlay = TimeStopOverlay(max_completed_bars=5, strategies=["B_ETF_trend_following"])
    _bind(overlay)
    portfolio = Portfolio(_config("B_ETF_trend_following"), 0.0)
    pos = _position(bars_held=4)
    portfolio.positions.append(pos)

    batch = overlay.on_signal_batch(
        date=pd.Timestamp("2020-01-10"),
        entries=[],
        exits=[],
        portfolio=portfolio,
        rows={},
        equity=1000.0,
        pending_exit_ids=set(),
    )
    assert batch.exits == []

    pos.bars_held = 5
    batch = overlay.on_signal_batch(
        date=pd.Timestamp("2020-01-13"),
        entries=[],
        exits=[],
        portfolio=portfolio,
        rows={},
        equity=1000.0,
        pending_exit_ids=set(),
    )
    assert len(batch.exits) == 1
    assert batch.exits[0].reason == "overlay_time_stop"


def test_overlay_event_ids_are_complete_unique_and_deterministic() -> None:
    def run_events() -> pd.DataFrame:
        overlay = IdentityOverlay()
        _bind(overlay)
        overlay.on_signal_batch(
            date=pd.Timestamp("2020-01-31"),
            entries=[_target_signal("SPY", 0.5)],
            exits=[],
            portfolio=Portfolio(_config("N2_absolute_trend_taa"), 0.0),
            rows={},
            equity=1000.0,
            pending_exit_ids=set(),
        )
        return overlay.events_frame()

    first = run_events()
    second = run_events()

    assert first["event_id"].is_unique
    assert not first[["event_id", "run_id", "overlay_id", "reason_code", "decision_phase"]].isna().any().any()
    assert_frame_equal(first, second)


def test_overlay_backtest_does_not_import_live_broker_modules() -> None:
    before = {name for name in sys.modules if name.startswith("execution_lab")}
    Backtester(_synthetic_d_data(), _config()).run(
        "identity",
        "2020-01-01",
        "2020-01-20",
        0.0,
        lightweight_outputs=True,
        overlay=IdentityOverlay(),
        run_id="broker-boundary",
    )
    after = {name for name in sys.modules if name.startswith("execution_lab")}

    assert after == before
