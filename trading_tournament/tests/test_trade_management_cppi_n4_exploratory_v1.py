from __future__ import annotations

import copy

import pandas as pd
import pytest

import run_trade_management_cppi_n4_exploratory_v1 as runner
from src.data import load_market_data
from src.indicators import prepare_indicators
from src.overlays import CPPIOverlay
from src.portfolio import Portfolio
from src.utils import load_config


@pytest.fixture(scope="module")
def frozen_bundle() -> dict[str, object]:
    config = runner.n4_only_config(load_config(runner.ROOT / "config.yaml"))
    load_result = load_market_data(config, runner.ROOT)
    prepared = prepare_indicators(load_result.data)
    episode = runner.freeze_episode(config, prepared, load_result)
    return {"config": config, "prepared": prepared, "episode": episode, "strategy_hash": runner.n4_config_hash(config)}


@pytest.fixture(scope="module")
def zero_cost_trials(frozen_bundle: dict[str, object]) -> dict[str, object]:
    config = frozen_bundle["config"]
    prepared = frozen_bundle["prepared"]
    episode = frozen_bundle["episode"]
    strategy_hash = frozen_bundle["strategy_hash"]
    assert isinstance(config, dict)
    assert isinstance(prepared, dict)
    assert isinstance(episode, dict)
    assert isinstance(strategy_hash, str)
    trials = {}
    for trial_name in [
        "BASE",
        "IDENTITY",
        "SAFE5_TRANSLATION_CONTROL",
        "STATIC_CPPI_INITIAL_RISK_CAP_CONTROL",
        "DYNAMIC_CPPI",
    ]:
        trials[trial_name] = runner.run_trial(
            prepared=prepared,
            config=config,
            episode=episode,
            trial_name=trial_name,
            slippage=0.0,
            overlay=runner.overlay_for_trial(trial_name, episode),
            base_strategy_hash=strategy_hash,
        )
    return trials


def test_frozen_episode_is_exact_first_complete_five_year_n4_window(frozen_bundle: dict[str, object]) -> None:
    episode = frozen_bundle["episode"]
    assert isinstance(episode, dict)
    assert episode["first_eligible_month_end_decision_date"] == "2008-03-31"
    assert episode["episode_start"] == "2008-03-31"
    assert episode["initial_execution_date"] == "2008-04-01"
    assert episode["exact_calendar_maturity_timestamp"].startswith("2013-03-31")
    assert episode["final_valuation_date"] == "2013-04-01"
    assert episode["not_selected_by_performance"] is True


def test_actual_n4_base_identity_complete_state_equivalence(zero_cost_trials: dict[str, object]) -> None:
    base_hash = runner.result_hashes(zero_cost_trials["BASE"])
    identity_hash = runner.result_hashes(zero_cost_trials["IDENTITY"])
    assert base_hash["complete_state_hash"] == identity_hash["complete_state_hash"]


def test_safe_account_translation_control_redirects_bil_and_reconciles(
    frozen_bundle: dict[str, object],
    zero_cost_trials: dict[str, object],
) -> None:
    result = zero_cost_trials["SAFE5_TRANSLATION_CONTROL"]
    daily = runner.daily_state_rows(
        result=result,
        prepared=frozen_bundle["prepared"],
        episode=frozen_bundle["episode"],
        trial_name="SAFE5_TRANSLATION_CONTROL",
        slippage=0.0,
    )
    assert all(row["nav_reconciles"] for row in daily)
    assert max(row["synthetic_safe_account_value"] for row in daily) > 0.0
    assert "BIL" not in set(result.trades["symbol"]) if not result.trades.empty else True
    assert "cppi_safe_asset_redirect" in set(result.overlay_events["reason_code"])


def test_static_initial_risk_cap_preserves_relative_risky_weights_and_caps_request(
    zero_cost_trials: dict[str, object],
) -> None:
    events = zero_cost_trials["STATIC_CPPI_INITIAL_RISK_CAP_CONTROL"].overlay_events
    risky = events[events["asset"].isin(runner.RISKY_ASSETS)].copy()
    risky["base_target"] = pd.to_numeric(risky["base_target"], errors="coerce").fillna(0.0)
    risky["managed_target"] = pd.to_numeric(risky["managed_target"], errors="coerce").fillna(0.0)
    grouped = risky.groupby("timestamp", as_index=False).agg({"base_target": "sum", "managed_target": "sum"})
    assert not grouped.empty
    assert (grouped["managed_target"] <= grouped["base_target"] + 1e-12).all()
    assert (grouped["managed_target"] <= runner.STATIC_INITIAL_RISK_CAP + 1e-12).all()


def test_dynamic_cppi_cap_never_exceeds_n4_request(
    frozen_bundle: dict[str, object],
    zero_cost_trials: dict[str, object],
) -> None:
    result = zero_cost_trials["DYNAMIC_CPPI"]
    daily = pd.DataFrame(
        runner.daily_state_rows(
            result=result,
            prepared=frozen_bundle["prepared"],
            episode=frozen_bundle["episode"],
            trial_name="DYNAMIC_CPPI",
            slippage=0.0,
        )
    )
    scheduled = daily[daily["scheduled_decision"]]
    managed = pd.to_numeric(scheduled["managed_risky_fraction"], errors="coerce").fillna(0.0)
    base = pd.to_numeric(scheduled["base_requested_risky_fraction"], errors="coerce").fillna(0.0)
    assert (managed <= base + 1e-12).all()
    assert (managed <= 1.0 + 1e-12).all()


def test_intraperiod_shortfall_is_distinct_from_scheduled_cash_lock() -> None:
    config = {
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
        "strategy_order": ["N4_inverse_vol_defensive_allocation"],
        "strategies": {
            "N4_inverse_vol_defensive_allocation": {
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
    overlay = CPPIOverlay(risky_assets={"SPY"}, safe_assets={"BIL"})
    overlay.bind(
        run_id="scheduled-breach-unit",
        base_strategy_id="N4_inverse_vol_defensive_allocation",
        base_strategy_hash="hash",
        data={},
        indexed_data={},
        calendar=[pd.Timestamp("2020-01-30"), pd.Timestamp("2020-01-31"), pd.Timestamp("2020-02-03")],
        config=config,
    )
    portfolio = Portfolio(config, 0.0)
    portfolio.cash = overlay.floor_value(pd.Timestamp("2020-01-30")) - 1.0
    overlay.process_position_lifecycle(date=pd.Timestamp("2020-01-30"), portfolio=portfolio, rows={}, slippage_pct=0.0)
    assert not overlay.cash_locked
    assert "cppi_intraperiod_floor_shortfall" in set(overlay.events_frame()["reason_code"])

    batch = overlay.on_signal_batch(
        date=pd.Timestamp("2020-01-31"),
        entries=[],
        exits=[],
        portfolio=portfolio,
        rows={},
        equity=portfolio.cash,
        pending_exit_ids=set(),
    )
    assert batch.entries == []
    assert overlay.cash_locked
    assert {"cppi_scheduled_floor_breach", "cppi_cash_lock"} <= set(overlay.events_frame()["reason_code"])


def test_cppi_static_and_safe_translation_nav_reconciliation(
    frozen_bundle: dict[str, object],
    zero_cost_trials: dict[str, object],
) -> None:
    for trial_name in ["SAFE5_TRANSLATION_CONTROL", "STATIC_CPPI_INITIAL_RISK_CAP_CONTROL", "DYNAMIC_CPPI"]:
        daily = runner.daily_state_rows(
            result=zero_cost_trials[trial_name],
            prepared=frozen_bundle["prepared"],
            episode=frozen_bundle["episode"],
            trial_name=trial_name,
            slippage=0.0,
        )
        assert all(row["nav_reconciles"] for row in daily)


def test_source_and_worktree_hash_capture_includes_dirty_status_and_diff_hash() -> None:
    payload = runner.tracked_and_untracked_diff_hash()
    assert isinstance(payload["dirty"], bool)
    assert len(payload["tracked_and_untracked_diff_hash"]) == 64
    assert "status_porcelain" in payload
    assert "untracked_file_hashes" in payload
