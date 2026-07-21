from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

import run_trade_management_cppi_n4_methodology_correction_v1 as runner
from src.backtester import BacktestResult, Backtester
from src.overlays import CPPIOverlay
from src.portfolio import Portfolio, Position
from src.strategies import EntrySignal


def _config() -> dict:
    return {
        "project": {
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
        },
        "universe": {"symbols": ["SPY", "BIL"], "clusters": {"equity_index": ["SPY"], "cash": ["BIL"]}},
        "strategy_order": [runner.STRATEGY_ID],
        "strategies": {
            runner.STRATEGY_ID: {
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


def _rows(open_price: float = 100.0) -> dict[str, pd.Series]:
    return {"SPY": pd.Series({"open": open_price, "close": open_price, "high": open_price, "low": open_price})}


def _entry(weight: float, symbol: str = "SPY") -> EntrySignal:
    return EntrySignal(
        date=pd.Timestamp("2020-01-31"),
        strategy=runner.STRATEGY_ID,
        symbol=symbol,
        requested_risk=1.0,
        metadata={"target_weight": weight, "atr": 1.0},
    )


def _safe5(calendar: list[pd.Timestamp] | None = None) -> runner.Safe5TranslationControl:
    overlay = runner.Safe5TranslationControl()
    overlay.bind(
        run_id="unit",
        base_strategy_id=runner.STRATEGY_ID,
        base_strategy_hash="hash",
        data={},
        indexed_data={},
        calendar=calendar or [pd.Timestamp("2020-01-31"), pd.Timestamp("2020-02-03"), pd.Timestamp("2020-02-04")],
        config=_config(),
    )
    return overlay


def _sweep_initial_cash(overlay: runner.Safe5TranslationControl, portfolio: Portfolio) -> None:
    overlay.on_before_order_fills(date=pd.Timestamp("2020-01-31"), portfolio=portfolio, rows=_rows())
    overlay.on_end_of_day(date=pd.Timestamp("2020-01-31"), portfolio=portfolio, rows=_rows(), slippage_pct=0.0)


def test_prior_defect_reproduced_from_frozen_exploratory_output() -> None:
    summary = runner.prior_defect_summary()

    assert summary["prior_package_found"] is True
    by_trial = {row["trial_name"]: row for row in summary["rows"]}
    assert by_trial["SAFE5_TRANSLATION_CONTROL"]["daily_observations"] == 1260
    assert by_trial["SAFE5_TRANSLATION_CONTROL"]["days_safe_positive"] == 61
    assert by_trial["DYNAMIC_CPPI"]["days_safe_positive"] == 61

    first = summary["first_bad_release"]
    assert first["first_incorrect_release_date"] == "2008-04-02"
    assert first["pending_market_order_required_funding"] is False
    assert first["amount_released"] == pytest.approx(258.13459738500063)
    assert first["end_of_day_broker_cash"] == pytest.approx(258.13459738500063)
    assert first["end_of_day_safe_balance"] == pytest.approx(0.0)
    assert first["next_date_balance_swept_back"] == "2008-05-01"


def test_safe_capital_persists_across_normal_non_execution_day() -> None:
    overlay = _safe5()
    portfolio = Portfolio(_config(), 0.0)
    _sweep_initial_cash(overlay, portfolio)

    overlay.on_before_order_fills(date=pd.Timestamp("2020-02-03"), portfolio=portfolio, rows=_rows())
    overlay.on_end_of_day(date=pd.Timestamp("2020-02-03"), portfolio=portfolio, rows=_rows(), slippage_pct=0.0)

    assert portfolio.cash == pytest.approx(0.0)
    assert portfolio.synthetic_safe_account_value > 3000.0
    assert not overlay.events_frame()["proposed_order"].str.contains("synthetic_safe_to_broker_cash").any()


def test_weekend_safe_accrual_uses_all_elapsed_calendar_days() -> None:
    overlay = _safe5()
    portfolio = Portfolio(_config(), 0.0)
    _sweep_initial_cash(overlay, portfolio)

    overlay.on_before_order_fills(date=pd.Timestamp("2020-02-03"), portfolio=portfolio, rows=_rows())

    expected = 3000.0 * np.exp(0.05 * 3.0 / 365.0)
    assert portfolio.synthetic_safe_account_value == pytest.approx(expected)
    accrual = overlay.events_frame()[overlay.events_frame()["reason_code"].eq("cppi_safe_account_accrual")]
    state = json.loads(accrual.iloc[-1]["state_after"])
    assert state["elapsed_calendar_days"] == 3


def test_no_pending_order_means_no_safe_release() -> None:
    overlay = _safe5()
    portfolio = Portfolio(_config(), 0.0)
    _sweep_initial_cash(overlay, portfolio)
    overlay.pending_safe_release_date = pd.Timestamp("2020-02-03")

    overlay.on_before_order_fills(date=pd.Timestamp("2020-02-03"), portfolio=portfolio, rows=_rows(), pending_entries=[])

    assert portfolio.cash == pytest.approx(0.0)
    assert portfolio.synthetic_safe_account_value > 3000.0
    transfer_events = overlay.events_frame()[overlay.events_frame()["reason_code"].eq("cppi_safe_account_transfer")]
    assert not transfer_events["proposed_order"].str.contains("synthetic_safe_to_broker_cash").any()


def test_only_required_purchase_funding_is_released() -> None:
    overlay = _safe5()
    portfolio = Portfolio(_config(), 0.0)
    _sweep_initial_cash(overlay, portfolio)
    overlay.pending_safe_release_date = pd.Timestamp("2020-02-03")

    overlay.on_before_order_fills(
        date=pd.Timestamp("2020-02-03"),
        portfolio=portfolio,
        rows=_rows(),
        pending_entries=[_entry(0.20)],
    )

    nav, _ = portfolio.mark_to_market(_rows())
    released = portfolio.cash
    assert released == pytest.approx(nav * 0.20)
    release = overlay.events_frame()[overlay.events_frame()["proposed_order"].str.contains("synthetic_safe_to_broker_cash")].iloc[-1]
    proposed = json.loads(release["proposed_order"])
    assert float(proposed["required_safe_release"]) == pytest.approx(released)


def test_unused_funding_is_returned_the_same_day() -> None:
    overlay = _safe5()
    portfolio = Portfolio(_config(), 0.0)
    _sweep_initial_cash(overlay, portfolio)
    overlay.pending_safe_release_date = pd.Timestamp("2020-02-03")
    overlay.on_before_order_fills(
        date=pd.Timestamp("2020-02-03"),
        portfolio=portfolio,
        rows=_rows(),
        pending_entries=[_entry(0.20)],
    )

    released = portfolio.cash
    overlay.on_end_of_day(date=pd.Timestamp("2020-02-03"), portfolio=portfolio, rows=_rows(), slippage_pct=0.0)

    assert released > 0.0
    assert portfolio.cash == pytest.approx(0.0)
    assert portfolio.synthetic_safe_account_value > 3000.0


def test_rejected_order_funding_is_returned() -> None:
    overlay = _safe5()
    portfolio = Portfolio(_config(), 0.0)
    _sweep_initial_cash(overlay, portfolio)
    overlay.pending_safe_release_date = pd.Timestamp("2020-02-03")
    overlay.on_before_order_fills(
        date=pd.Timestamp("2020-02-03"),
        portfolio=portfolio,
        rows=_rows(),
        pending_entries=[_entry(0.10)],
    )
    assert portfolio.cash > 0.0

    overlay.on_end_of_day(date=pd.Timestamp("2020-02-03"), portfolio=portfolio, rows=_rows(), slippage_pct=0.0)

    assert portfolio.cash == pytest.approx(0.0)
    assert "end_of_day_safe_persistence" in "".join(overlay.events_frame()["proposed_order"].astype(str))


def test_end_of_day_broker_cash_tolerance_is_enforced_by_failure_registry() -> None:
    daily = [
        {
            "trial_name": "SAFE5_TRANSLATION_CONTROL",
            "slippage_bps_per_side": 0.0,
            "date": "2020-01-31",
            "broker_cash": 0.01,
            "synthetic_safe_account_value": 100.0,
            "nav_reconciliation_error": 0.0,
        }
    ]
    diagnostics = runner.safe_persistence_diagnostic_rows(
        daily_rows_all=daily,
        safe_event_rows_all=[],
        accrual_rows=[],
        results={(0.0, "SAFE5_TRANSLATION_CONTROL"): _empty_result()},
    )
    failures = runner.failure_registry_rows(
        reconciliation_all=[],
        identity_rows=[],
        daily_rows_all=daily,
        safe_diagnostics=diagnostics,
        accrual_rows=[],
        safe_event_rows=[],
    )

    residual = [row for row in failures if row["check_id"] == "RESIDUAL_BROKER_CASH_SWEEP"][0]
    assert residual["status"] == "FAIL"
    assert residual["failure_code"] == "FAIL_RESIDUAL_BROKER_CASH_NOT_SWEPT"


def test_no_duplicate_safe_accrual_on_same_day() -> None:
    overlay = _safe5()
    portfolio = Portfolio(_config(), 0.0)
    _sweep_initial_cash(overlay, portfolio)

    overlay.on_before_order_fills(date=pd.Timestamp("2020-02-03"), portfolio=portfolio, rows=_rows())
    value_after_first = portfolio.synthetic_safe_account_value
    overlay.on_before_order_fills(date=pd.Timestamp("2020-02-03"), portfolio=portfolio, rows=_rows())

    assert portfolio.synthetic_safe_account_value == pytest.approx(value_after_first)
    accrual_events = overlay.events_frame()[overlay.events_frame()["reason_code"].eq("cppi_safe_account_accrual")]
    assert len(accrual_events) == 1


def test_kill_rules_remain_unchanged_and_kill_date_attribution_is_deterministic() -> None:
    results = _fake_results_for_kill_attribution()
    daily = _fake_daily_rows_for_kill_attribution()

    first = runner.strategy_kill_attribution_rows(results=results, daily_rows_all=daily)
    second = runner.strategy_kill_attribution_rows(results=results, daily_rows_all=daily)

    assert first == second
    base = [row for row in first if row["trial_name"] == "BASE" and row["slippage_bps_per_side"] == 0.0][0]
    dynamic = [row for row in first if row["trial_name"] == "DYNAMIC_CPPI" and row["slippage_bps_per_side"] == 0.0][0]
    assert base["n4_killed"] is True
    assert base["kill_decision_date"] == "2020-01-03"
    assert dynamic["n4_killed"] is False
    assert dynamic["risk_control_survival_effect"] == pytest.approx(10.0)


def test_base_and_identity_remain_exactly_equivalent() -> None:
    data = _synthetic_data()
    cfg = _identity_config()
    base = Backtester(data, cfg).run("base", "2020-01-01", "2020-01-20", 0.0, lightweight_outputs=True)
    identity = Backtester(data, cfg).run(
        "identity",
        "2020-01-01",
        "2020-01-20",
        0.0,
        lightweight_outputs=True,
        overlay=runner.IdentityOverlay(),
        run_id="identity-unit",
    )

    assert_frame_equal(base.equity_curve, identity.equity_curve)
    assert_frame_equal(base.trades, identity.trades)


def test_corrected_controls_share_safe_ledger_contract() -> None:
    controls = [_safe5(), runner.StaticCPPIInitialRiskCapControl(), CPPIOverlay(risky_assets={"SPY"}, safe_assets={"BIL"})]
    for overlay in controls[1:]:
        overlay.bind(
            run_id="unit",
            base_strategy_id=runner.STRATEGY_ID,
            base_strategy_hash="hash",
            data={},
            indexed_data={},
            calendar=[pd.Timestamp("2020-01-31"), pd.Timestamp("2020-02-03")],
            config=_config(),
        )
    for overlay in controls:
        portfolio = Portfolio(_config(), 0.0)
        overlay.on_before_order_fills(date=pd.Timestamp("2020-01-31"), portfolio=portfolio, rows=_rows())
        overlay.on_end_of_day(date=pd.Timestamp("2020-01-31"), portfolio=portfolio, rows=_rows(), slippage_pct=0.0)
        overlay.pending_safe_release_date = pd.Timestamp("2020-02-03")
        overlay.on_before_order_fills(date=pd.Timestamp("2020-02-03"), portfolio=portfolio, rows=_rows(), pending_entries=[])
        assert portfolio.cash == pytest.approx(0.0)
        assert portfolio.synthetic_safe_account_value > 3000.0


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


def _identity_config() -> dict:
    cfg = _config()
    cfg["strategy_order"] = ["D_mean_reversion"]
    cfg["strategies"] = {
        "D_mean_reversion": {
            "enabled": True,
            "allocation": 3000.0,
            "max_strategy_loss": 999.0,
            "risk_per_trade": 30.0,
            "max_positions": 3,
            "max_holding_days": 20,
            "initial_atr_multiple": 1.5,
            "trailing_atr_multiple": 2.5,
        }
    }
    return cfg


def _empty_result(
    lifecycle: pd.DataFrame | None = None,
    trades: pd.DataFrame | None = None,
) -> BacktestResult:
    return BacktestResult(
        trades=trades if trades is not None else pd.DataFrame(columns=["entry_date", "exit_date", "pnl"]),
        skipped_signals=pd.DataFrame(),
        strategy_metrics=pd.DataFrame(),
        equity_curve=pd.DataFrame(),
        benchmark_curve=pd.DataFrame(),
        monthly_returns=pd.DataFrame(),
        regime_performance=pd.DataFrame(),
        target_timing=pd.DataFrame(),
        risk_events=pd.DataFrame(),
        strategy_lifecycle_events=(
            lifecycle
            if lifecycle is not None
            else pd.DataFrame(columns=["date", "strategy", "event_type", "event_reason", "strategy_pnl", "project_equity"])
        ),
        overlay_events=pd.DataFrame(),
        killed_strategies=[],
        metadata={},
    )


def _fake_results_for_kill_attribution() -> dict[tuple[float, str], BacktestResult]:
    results: dict[tuple[float, str], BacktestResult] = {}
    kill_lifecycle = pd.DataFrame(
        [
            {
                "date": "2020-01-03",
                "strategy": runner.STRATEGY_ID,
                "event_type": "strategy_disabled_loss_budget",
                "event_reason": "strategy_loss_budget_hit",
                "strategy_pnl": -100.0,
                "project_equity": 2900.0,
            }
        ]
    )
    for slippage in runner.SLIPPAGES:
        for trial_name in runner.TRIAL_NAMES:
            lifecycle = kill_lifecycle if trial_name in {"BASE", "SAFE5_TRANSLATION_CONTROL", "STATIC_CPPI_INITIAL_RISK_CAP_CONTROL"} else None
            pnl_after = 30.0 if trial_name == "DYNAMIC_CPPI" else 20.0
            trades = pd.DataFrame(
                [
                    {"entry_date": "2020-01-02", "exit_date": "2020-01-03", "pnl": -5.0},
                    {"entry_date": "2020-01-06", "exit_date": "2020-01-07", "pnl": pnl_after},
                ]
            )
            results[(slippage, trial_name)] = _empty_result(lifecycle=lifecycle, trades=trades)
    return results


def _fake_daily_rows_for_kill_attribution() -> list[dict]:
    rows: list[dict] = []
    dates = ["2020-01-02", "2020-01-03", "2020-01-06", "2020-01-07"]
    for slippage in runner.SLIPPAGES:
        for trial_name in runner.TRIAL_NAMES:
            for date in dates:
                rows.append(
                    {
                        "trial_name": trial_name,
                        "slippage_bps_per_side": slippage * 10000.0,
                        "date": date,
                        "actual_risky_exposure": 0.0 if date == "2020-01-07" else 0.5,
                    }
                )
    return rows
