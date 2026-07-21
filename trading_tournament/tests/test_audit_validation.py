from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from src.backtester import BacktestResult
from src.risk import compute_target_timing, evaluate_project_stop
from src.strategies import N1, N2, N3, N4, StrategyEngine
from src.validation import (
    ROLLING_CANDIDATE_VARIANTS,
    VARIANTS,
    _chunk_start_indices,
    _rolling_cache_key,
    _select_window_starts,
    apply_validation_mode,
    build_rolling_sample_plan,
    candidate_gate_results,
    consistency_check,
    create_evidence_bundle,
    make_audit_packet,
    r_multiple_diagnostics,
    rolling_decision_from_summary,
    strategy_variant_config,
    summarize_independent_rolling_windows,
    summarize_rolling_windows,
    validation_mode_settings,
    write_evidence_summary,
)


def base_config() -> dict:
    return {
        "project": {
            "starting_equity": 3000.0,
            "hard_stop_equity": 2400.0,
            "target_profit_1": 300.0,
            "target_profit_2": 400.0,
            "project_stop": {
                "mode": "both",
                "absolute_floor_equity": 2400.0,
                "trailing_drawdown_dollars": 600.0,
            },
            "min_stop_distance_pct": 0.0025,
            "min_actual_risk_utilization_pct": 0.25,
        },
        "strategy_order": [
            "A_ETF_sector_momentum",
            "B_ETF_trend_following",
            "C_swing_trend_pullback",
            "E_breakout_vcb",
            "D_mean_reversion",
        ],
        "universe": {"symbols": ["SPY", "BIL", "SHY"]},
        "strategies": {
            "A_ETF_sector_momentum": {"enabled": True},
            "B_ETF_trend_following": {"enabled": True},
            "C_swing_trend_pullback": {"enabled": True},
            "D_mean_reversion": {"enabled": True},
            "E_breakout_vcb": {"enabled": True},
        },
        "rolling_validation": {"method": "all_possible", "max_windows_per_group": None},
    }


def evidence_strategy_config() -> dict:
    cfg = base_config()
    cfg["strategy_order"] = [N1, N2, N3, N4]
    cfg["universe"] = {"symbols": ["SPY", "QQQ", "IEF", "TLT", "GLD", "BIL", "SHY"], "clusters": {}}
    common = {"enabled": True, "allocation": 900.0, "max_strategy_loss": 220.0, "risk_per_trade": 220.0, "max_positions": 4}
    cfg["strategies"] = {
        N1: {
            **common,
            "top_n": 2,
            "max_asset_weight": 0.5,
            "initial_atr_multiple": 2.5,
            "trailing_atr_multiple": 2.5,
            "defensive_atr_multiple": 3.5,
            "risk_assets": ["SPY", "QQQ", "IEF", "TLT", "GLD"],
            "defensive_assets": ["BIL", "SHY", "IEF"],
            "risk_off_allowed_assets": ["IEF", "TLT", "GLD"],
        },
        N2: {
            **common,
            "risk_on_top_n": 3,
            "max_asset_weight": 0.5,
            "initial_atr_multiple": 3.0,
            "trailing_atr_multiple": 3.0,
            "defensive_atr_multiple": 3.5,
            "assets": ["SPY", "QQQ", "IWM", "IEF", "TLT", "GLD", "BIL"],
            "defensive_assets": ["BIL", "SHY", "IEF", "TLT", "GLD"],
        },
        N3: {
            **common,
            "top_n": 2,
            "max_asset_weight": 0.5,
            "initial_atr_multiple": 2.5,
            "trailing_atr_multiple": 2.5,
            "defensive_atr_multiple": 3.5,
            "high_vol_risk_asset_scale": 0.5,
            "risk_assets": ["SPY", "QQQ", "IEF", "TLT", "GLD"],
            "defensive_assets": ["BIL", "SHY", "IEF"],
            "risk_off_allowed_assets": ["IEF", "TLT", "GLD"],
        },
        N4: {
            **common,
            "max_asset_weight": 0.4,
            "initial_atr_multiple": 3.5,
            "trailing_atr_multiple": 3.5,
            "assets": ["SPY", "IEF", "TLT", "GLD"],
        },
    }
    return cfg


def evidence_data() -> dict[str, pd.DataFrame]:
    dates = pd.to_datetime(["2020-01-30", "2020-01-31", "2020-02-03"])
    values = {
        "SPY": (100, 90, 0.10, 0.20, 0.05),
        "QQQ": (120, 100, 0.30, 0.40, 0.04),
        "IEF": (105, 100, 0.03, 0.04, 0.02),
        "TLT": (110, 100, 0.05, 0.06, 0.03),
        "GLD": (115, 100, 0.06, 0.07, 0.08),
        "BIL": (100, 100, 0.01, 0.01, 0.005),
        "SHY": (101, 100, 0.015, 0.015, 0.006),
        "IWM": (90, 100, -0.10, -0.20, 0.06),
    }
    out = {}
    for symbol, (close, sma200, ret126, ret252, rv60) in values.items():
        out[symbol] = pd.DataFrame(
            {
                "date": dates,
                "open": close,
                "high": close * 1.01,
                "low": close * 0.99,
                "close": close,
                "sma_200": sma200,
                "ret_63": ret126 / 2,
                "ret_126": ret126,
                "ret_252": ret252,
                "atr_20": 2.0,
                "rv_20": 0.2,
                "rv_60": rv60,
                "spy_rv_20_q75": 0.25,
            }
        )
    return out


class EmptyPortfolio:
    def has_position(self, strategy: str, symbol: str) -> bool:
        return False


def evidence_engine(strategy: str, data: dict[str, pd.DataFrame] | None = None) -> StrategyEngine:
    cfg = evidence_strategy_config()
    cfg["strategy_order"] = [strategy]
    for name, scfg in cfg["strategies"].items():
        scfg["enabled"] = name == strategy
    return StrategyEngine(data or evidence_data(), cfg)


def test_dual_momentum_taa_uses_only_eligible_assets_and_excludes_below_200sma():
    data = evidence_data()
    data["QQQ"].loc[:, "close"] = 80.0
    data["QQQ"].loc[:, "open"] = 80.0
    data["QQQ"].loc[:, "high"] = 81.0
    data["QQQ"].loc[:, "low"] = 79.0
    engine = evidence_engine(N1, data)

    weights = engine._monthly_target_weights(N1, pd.Timestamp("2020-01-31"))

    assert "QQQ" not in weights
    assert "SPY" in weights
    assert sum(weights.values()) <= 1.000001


def test_dual_momentum_taa_sends_unused_allocation_to_defensive_assets():
    data = evidence_data()
    for symbol in ["SPY", "QQQ", "IEF", "TLT", "GLD"]:
        data[symbol].loc[:, "close"] = 80.0
        data[symbol].loc[:, "ret_126"] = 0.0
        data[symbol].loc[:, "ret_252"] = 0.0
    engine = evidence_engine(N1, data)

    weights = engine._monthly_target_weights(N1, pd.Timestamp("2020-01-31"))

    assert weights
    assert set(weights).issubset({"BIL", "SHY", "IEF"})
    assert sum(weights.values()) <= 1.000001


def test_absolute_trend_taa_switches_to_defensive_when_spy_below_200sma():
    data = evidence_data()
    data["SPY"].loc[:, "close"] = 80.0
    engine = evidence_engine(N2, data)

    weights = engine._monthly_target_weights(N2, pd.Timestamp("2020-01-31"))

    assert weights
    assert set(weights).issubset({"BIL", "SHY", "IEF", "TLT", "GLD"})
    assert "QQQ" not in weights


def test_dual_momentum_vol_scaled_reduces_risk_asset_exposure_in_high_vol():
    normal = evidence_engine(N3, evidence_data())
    high_vol_data = evidence_data()
    high_vol_data["SPY"].loc[:, "rv_20"] = 0.35
    high_vol = evidence_engine(N3, high_vol_data)

    normal_weights = normal._monthly_target_weights(N3, pd.Timestamp("2020-01-31"))
    high_vol_weights = high_vol._monthly_target_weights(N3, pd.Timestamp("2020-01-31"))
    normal_risk_weight = normal_weights.get("QQQ", 0.0) + normal_weights.get("SPY", 0.0)
    high_vol_risk_weight = high_vol_weights.get("QQQ", 0.0) + high_vol_weights.get("SPY", 0.0)

    assert high_vol_risk_weight < normal_risk_weight
    assert high_vol_risk_weight == pytest.approx(normal_risk_weight * 0.5)


def test_inverse_vol_defensive_allocation_weights_sum_and_cap():
    engine = evidence_engine(N4, evidence_data())

    weights = engine._monthly_target_weights(N4, pd.Timestamp("2020-01-31"))

    assert sum(weights.values()) <= 1.000001
    assert all(weight <= 0.400001 for symbol, weight in weights.items() if symbol != "BIL")


def test_bil_shy_are_not_alpha_ranked_when_risk_slots_are_full():
    data = evidence_data()
    data["BIL"].loc[:, "ret_63"] = 10.0
    data["BIL"].loc[:, "ret_126"] = 0.01
    data["SHY"].loc[:, "ret_63"] = 9.0
    data["SHY"].loc[:, "ret_126"] = 9.0
    data["SHY"].loc[:, "ret_252"] = 9.0
    engine = evidence_engine(N1, data)

    weights = engine._monthly_target_weights(N1, pd.Timestamp("2020-01-31"))

    assert "BIL" not in weights
    assert "SHY" not in weights
    assert set(weights).issubset({"SPY", "QQQ", "IEF", "TLT", "GLD"})


def test_new_evidence_variants_are_registered_for_all_possible_rolling():
    expected = {
        "evidence_dual_momentum_taa",
        "evidence_absolute_trend_taa",
        "evidence_dual_momentum_vol_scaled",
        "evidence_inverse_vol_defensive",
        "evidence_core_combo",
    }

    assert expected.issubset(VARIANTS)
    assert expected.issubset(set(ROLLING_CANDIDATE_VARIANTS))


def test_absolute_and_trailing_project_stop_modes():
    cfg = base_config()
    assert evaluate_project_stop(2399.0, 3000.0, cfg)["absolute_floor_stop_active"] is True
    assert evaluate_project_stop(2399.0, 3000.0, cfg)["trailing_drawdown_stop_active"] is True

    cfg["project"]["project_stop"]["mode"] = "trailing_drawdown"
    result = evaluate_project_stop(3000.0, 3601.0, cfg)
    assert result["absolute_floor_stop_active"] is False
    assert result["trailing_drawdown_stop_active"] is True


def test_target_before_stop_logic():
    cfg = base_config()
    curve = pd.DataFrame(
        {
            "date": pd.date_range("2020-01-01", periods=4),
            "equity": [3000.0, 3310.0, 3500.0, 2890.0],
            "high_water_mark": [3000.0, 3310.0, 3500.0, 3500.0],
            "absolute_floor_stop_active": [False, False, False, False],
            "trailing_drawdown_stop_active": [False, False, False, True],
        }
    )
    timing = compute_target_timing(curve, cfg)

    assert timing["target_300_hit"] is True
    assert timing["target_300_before_any_stop"] is True
    assert timing["target_400_hit"] is True
    assert timing["target_400_before_any_stop"] is True
    assert timing["trailing_drawdown_stop_hit"] is True


def test_rolling_window_summary_aggregates_rates():
    rolling = pd.DataFrame(
        {
            "horizon_trading_days": [90, 90],
            "window_id": ["a", "b"],
            "final_equity": [3300.0, 2900.0],
            "target_300_hit": [True, False],
            "target_300_before_any_stop": [True, False],
            "target_400_hit": [False, False],
            "target_400_before_any_stop": [False, False],
            "absolute_floor_stop_hit": [False, False],
            "trailing_drawdown_stop_hit": [False, True],
            "any_project_stop_hit": [False, True],
            "max_drawdown_dollars": [-100.0, -700.0],
            "number_of_trades": [5, 3],
            "total_return": [0.1, -0.033],
        }
    )
    summary = summarize_rolling_windows(rolling)

    assert summary.loc[0, "number_of_windows"] == 2
    assert summary.loc[0, "pct_windows_target_300_hit"] == 0.5
    assert summary.loc[0, "pct_windows_any_stop_hit"] == 0.5


def test_independent_rolling_summary_groups_by_variant_slippage_horizon():
    rolling = pd.DataFrame(
        {
            "variant_name": ["current_momentum_only_A", "current_momentum_only_A", "current_momentum_only_A"],
            "slippage_label": ["standard", "standard", "standard"],
            "horizon_trading_days": [90, 90, 90],
            "start_date": ["2020-01-01", "2020-02-01", "2020-03-01"],
            "final_equity": [3300.0, 2900.0, 3100.0],
            "total_return": [0.1, -0.033, 0.033],
            "target_300_hit": [True, False, False],
            "target_300_before_any_stop": [True, False, False],
            "target_400_hit": [False, False, False],
            "target_400_before_any_stop": [False, False, False],
            "absolute_floor_stop_hit": [False, False, False],
            "trailing_drawdown_stop_hit": [False, True, False],
            "any_project_stop_hit": [False, True, False],
            "max_drawdown_dollars": [-100.0, -700.0, -300.0],
            "number_of_trades": [5, 3, 4],
            "possible_window_count": [3, 3, 3],
            "window_sampling_method": ["all_possible", "all_possible", "all_possible"],
        }
    )
    summary = summarize_independent_rolling_windows(rolling)

    assert summary.loc[0, "variant_name"] == "current_momentum_only_A"
    assert summary.loc[0, "slippage_label"] == "standard"
    assert summary.loc[0, "number_of_windows"] == len(rolling)
    assert summary.loc[0, "pct_windows_target_300_before_stop"] == 1 / 3
    assert summary.loc[0, "pct_windows_trailing_stop_hit"] == 1 / 3
    assert summary.loc[0, "10th_percentile_final_equity"] == rolling["final_equity"].quantile(0.10)
    assert summary.loc[0, "window_sampling_method"] == "all_possible"


def test_all_possible_window_start_selection_exceeds_sample():
    exhaustive = _select_window_starts(100, None, "all_possible")
    sampled = _select_window_starts(100, 12, "deterministic_sample")

    assert len(exhaustive) == 100
    assert len(sampled) == 12
    assert len(exhaustive) > len(sampled)
    assert exhaustive == list(range(100))


def test_default_validation_mode_is_research_sample_and_not_nightly():
    cfg = base_config()
    settings = validation_mode_settings(cfg)

    assert settings["mode"] == "research_sample"
    assert settings["rolling_method"] == "deterministic_stratified_sample"
    assert settings["mark_as_final"] is False
    assert settings["mode"] != "nightly_full_exhaustive"


def test_smoke_mode_uses_fewer_sampled_windows_than_research_sample():
    cfg = base_config()
    smoke = apply_validation_mode(cfg, "smoke")
    research = apply_validation_mode(cfg, "research_sample")

    assert smoke["rolling_validation"]["method"] == "deterministic_stratified_sample"
    assert research["rolling_validation"]["method"] == "deterministic_stratified_sample"
    assert smoke["rolling_validation"]["max_windows_per_group"] < research["rolling_validation"]["max_windows_per_group"]


def test_candidate_exhaustive_uses_all_possible_for_finalists_only():
    cfg = apply_validation_mode(base_config(), "candidate_exhaustive")
    settings = validation_mode_settings(cfg)

    assert cfg["rolling_validation"]["method"] == "all_possible"
    assert settings["mark_as_final"] is True
    assert "nightly_full_exhaustive" != settings["mode"]
    assert "evidence_core_combo" in settings["variants"]


def test_deterministic_stratified_sample_plan_is_stable_and_bounded():
    cfg = base_config()
    cfg["execution"] = {"standard_slippage_pct_per_side": 0.0005, "stress_slippage_pct_per_side": 0.001}
    dates = list(pd.date_range("2020-01-01", periods=120, freq="B"))
    spy = pd.DataFrame(
        {
            "date": dates,
            "close": [100 + idx * 0.1 for idx in range(len(dates))],
            "sma_200": [100.0] * len(dates),
            "rv_20": [0.1 + (idx % 10) * 0.01 for idx in range(len(dates))],
        }
    )
    data = {"SPY": spy}

    first = build_rolling_sample_plan(
        data,
        cfg,
        dates,
        ["current_momentum_only_A"],
        ["standard"],
        [90],
        "deterministic_stratified_sample",
        24,
    )
    second = build_rolling_sample_plan(
        data,
        cfg,
        dates,
        ["current_momentum_only_A"],
        ["standard"],
        [90],
        "deterministic_stratified_sample",
        24,
    )

    assert len(first) <= 24
    assert len(first) == len(second)
    assert first["start_index"].tolist() == second["start_index"].tolist()
    assert (first["sampling_method"] == "deterministic_stratified_sample").all()


def test_candidate_gate_records_failures_benchmark_and_shadow_rows():
    variants = pd.DataFrame(
        [
            {
                "variant_name": "current_momentum_only_A",
                "slippage_label": "stress",
                "enabled_strategies": "A_ETF_sector_momentum",
                "final_equity": 2600.0,
                "total_return": -0.133,
                "max_drawdown_dollars": -400.0,
                "max_drawdown_pct": -0.13,
                "target_300_before_any_stop": False,
                "target_400_before_any_stop": False,
                "any_project_stop_hit": False,
                "number_of_trades": 10,
                "profit_factor": 0.8,
            },
            {
                "variant_name": "evidence_inverse_vol_defensive",
                "slippage_label": "stress",
                "enabled_strategies": N4,
                "final_equity": 2850.0,
                "total_return": -0.05,
                "max_drawdown_dollars": -80.0,
                "max_drawdown_pct": -0.03,
                "target_300_before_any_stop": False,
                "target_400_before_any_stop": False,
                "any_project_stop_hit": False,
                "number_of_trades": 5,
                "profit_factor": 0.7,
            },
            {
                "variant_name": "satellites_only_CDE",
                "slippage_label": "standard",
                "enabled_strategies": "C_swing_trend_pullback,D_mean_reversion,E_breakout_vcb",
                "final_equity": 2900.0,
                "total_return": -0.033,
                "max_drawdown_dollars": -120.0,
                "max_drawdown_pct": -0.04,
                "target_300_before_any_stop": False,
                "target_400_before_any_stop": False,
                "any_project_stop_hit": False,
                "number_of_trades": 5,
                "profit_factor": 1.2,
            },
        ]
    )

    gate = candidate_gate_results(variants)

    assert gate.loc[gate["variant_name"] == "current_momentum_only_A", "gate_status"].iloc[0] == "fail"
    assert gate.loc[gate["variant_name"] == "evidence_inverse_vol_defensive", "gate_status"].iloc[0] == "benchmark_only"
    assert gate.loc[gate["variant_name"] == "satellites_only_CDE", "gate_status"].iloc[0] == "shadow_only"


def test_rolling_cache_key_changes_when_config_hash_changes():
    base = _rolling_cache_key("data", "config1", "strategies", "v", "standard", 90, "sample", "research_sample", "plan", "both")
    changed = _rolling_cache_key("data", "config2", "strategies", "v", "standard", 90, "sample", "research_sample", "plan", "both")

    assert base != changed


def test_evidence_summary_labels_sampled_results_as_non_final(tmp_path: Path):
    headline = {
        "run_id": "run1",
        "project_stop_mode": "both",
        "selected_main_run_name": "full_standard",
        "validation_mode": "research_sample",
        "rolling_method": "deterministic_stratified_sample",
        "final_validation_completed": False,
        "sampled_results_are_final": False,
        "final_equity": 3300.0,
        "total_return": 0.1,
        "cagr": 0.02,
        "max_drawdown_dollars": -100.0,
        "max_drawdown_pct": -0.03,
        "number_of_trades": 3,
        "number_of_skipped_signals": 1,
        "absolute_floor_stop_hit": False,
        "trailing_drawdown_stop_hit": False,
        "any_project_stop_hit": False,
        "first_project_stop_type": "",
        "first_project_stop_date": "",
        "target_300_before_any_stop": True,
        "target_400_before_any_stop": False,
        "standard_slippage_final_equity": 3300.0,
        "stress_slippage_final_equity": 3200.0,
        "stress_slippage_delta": -100.0,
        "forward_test_recommendation_status": "watchlist",
    }

    write_evidence_summary(
        tmp_path,
        headline,
        {"passed": True, "errors": [], "warnings": []},
        pd.DataFrame(
            [
                {
                    "variant_name": "current_momentum_only_A",
                    "slippage_label": "standard",
                    "horizon_trading_days": 90,
                    "window_sampling_method": "deterministic_stratified_sample",
                    "possible_window_count": 100,
                    "pct_windows_target_300_before_stop": 0.1,
                    "pct_windows_target_400_before_stop": 0.0,
                    "median_max_drawdown": -50.0,
                    "worst_max_drawdown": -100.0,
                }
            ]
        ),
        pd.DataFrame(),
        pd.DataFrame(),
        pd.DataFrame(),
        pd.DataFrame(),
    )

    text = (tmp_path / "evidence_summary.md").read_text(encoding="utf-8")
    assert "not final exhaustive validation" in text


def test_all_possible_window_chunks_keep_all_starts_once():
    starts = _select_window_starts(100, None, "all_possible")
    chunks = _chunk_start_indices(starts, 30)
    flattened = [item for chunk in chunks for item in chunk]

    assert len(chunks) == 4
    assert flattened == starts
    assert len(flattened) == len(set(flattened))


def test_no_duplicate_rolling_window_keys_in_all_possible_selection():
    starts = _select_window_starts(10, None, "all_possible")
    rows = pd.DataFrame(
        {
            "variant_name": ["current_core_only_AB"] * len(starts),
            "slippage_label": ["standard"] * len(starts),
            "horizon_trading_days": [90] * len(starts),
            "start_date": [f"2020-01-{idx + 1:02d}" for idx in starts],
        }
    )

    assert rows.duplicated(["variant_name", "slippage_label", "horizon_trading_days", "start_date"]).sum() == 0


def test_rolling_decision_marks_no_cash_as_leading_watchlist_when_robust():
    summary = pd.DataFrame(
        [
            {
                "variant_name": variant,
                "slippage_label": slip,
                "horizon_trading_days": 90,
                "pct_windows_target_300_before_stop": rate300,
                "pct_windows_target_400_before_stop": rate400,
                "median_max_drawdown": dd,
                "worst_max_drawdown": dd * 2,
            }
            for variant, standard300, stress300, standard400, stress400, dd in [
                ("current_no_cash_proxy_alpha_AB", 0.30, 0.28, 0.12, 0.10, -150.0),
                ("current_core_only_AB", 0.20, 0.18, 0.08, 0.07, -180.0),
                ("current_momentum_only_A", 0.09, 0.08, 0.02, 0.01, -90.0),
                ("original_full_tournament", 0.05, 0.04, 0.01, 0.00, -250.0),
            ]
            for slip, rate300, rate400 in [
                ("standard", standard300, standard400),
                ("stress", stress300, stress400),
            ]
        ]
    )

    decision = rolling_decision_from_summary(summary)

    assert decision["best_candidate"] == "current_no_cash_proxy_alpha_AB"
    assert decision["candidate_status"] == "leading_watchlist_candidate"
    assert decision["cde_status"] == "remain_rejected_or_shadow_only"


def test_strategy_variant_config_enables_expected_strategies():
    cfg = strategy_variant_config(base_config(), "current_core_only_AB")
    enabled = [name for name, scfg in cfg["strategies"].items() if scfg["enabled"]]
    assert enabled == ["A_ETF_sector_momentum", "B_ETF_trend_following"]

    cfg = strategy_variant_config(base_config(), "current_no_cash_proxy_alpha_AB")
    assert "BIL" not in cfg["universe"]["symbols"]
    assert "SHY" not in cfg["universe"]["symbols"]


def test_r_multiple_diagnostics_counts_tiny_risk_and_sorts():
    cfg = base_config()
    trades = pd.DataFrame(
        {
            "symbol": ["BIL", "SPY"],
            "intended_risk_amount": [45.0, 45.0],
            "actual_risk_amount": [5.0, 45.0],
            "risk_utilization_pct": [5.0 / 45.0, 1.0],
            "stop_distance_pct": [0.001, 0.01],
            "r_multiple": [10.0, -1.0],
            "pnl": [50.0, -45.0],
        }
    )
    diag, top_r, top_pnl, bottom_pnl = r_multiple_diagnostics(trades, cfg)

    assert diag.loc[0, "would_exclude_min_stop_distance_pct_count"] == 1
    assert diag.loc[0, "would_exclude_min_actual_risk_utilization_count"] == 1
    assert top_r.iloc[0]["symbol"] == "BIL"
    assert top_pnl.iloc[0]["pnl"] == 50.0
    assert bottom_pnl.iloc[0]["pnl"] == -45.0


def test_audit_packet_files_and_manifest_counts(tmp_path: Path):
    cfg = base_config()
    cfg["execution"] = {"standard_slippage_pct_per_side": 0.0005, "stress_slippage_pct_per_side": 0.001}
    trades = pd.DataFrame(
        {
            "trade_id": [1],
            "strategy": ["A_ETF_sector_momentum"],
            "symbol": ["SPY"],
            "entry_date": ["2020-01-01"],
            "exit_date": ["2020-01-02"],
            "pnl": [10.0],
            "r_multiple": [1.0],
            "holding_days": [1],
        }
    )
    result = BacktestResult(
        trades=trades,
        skipped_signals=pd.DataFrame(),
        strategy_metrics=pd.DataFrame(
            [{"name": "combined_tournament", "final_equity": 3010.0, "total_return": 0.0033, "max_drawdown": 0.0}]
        ),
        equity_curve=pd.DataFrame({"date": ["2020-01-01"], "equity": [3010.0]}),
        benchmark_curve=pd.DataFrame(),
        monthly_returns=pd.DataFrame(),
        regime_performance=pd.DataFrame(),
        target_timing=pd.DataFrame(),
        risk_events=pd.DataFrame(),
        strategy_lifecycle_events=pd.DataFrame(),
        overlay_events=pd.DataFrame(),
        killed_strategies=[],
        metadata={
            "effective_first_trading_date": "2020-01-01",
            "effective_last_trading_date": "2020-01-02",
            "target_300_hit": False,
            "target_300_before_any_stop": False,
            "target_400_hit": False,
            "target_400_before_any_stop": False,
        },
    )
    (tmp_path / "trades.csv").write_text("a\n1\n", encoding="utf-8")
    rolling_summary = pd.DataFrame(
        [{"horizon_trading_days": 90, "pct_windows_target_300_hit": 0.5, "pct_windows_any_stop_hit": 0.0}]
    )
    variants = pd.DataFrame(
        [{"period": "full", "variant_name": "original_full_tournament", "slippage_label": "standard"}]
    )
    make_audit_packet(
        tmp_path,
        "test_run",
        result,
        cfg,
        {"run_timestamp_utc": "now", "project_stop_mode": "both"},
        pd.DataFrame({"symbol": ["SPY"], "status": ["valid"]}),
        pd.DataFrame({"period": ["full"]}),
        rolling_summary,
        variants,
        {"r_multiple_diagnostics": pd.DataFrame([{"total_trades": 1}])},
    )

    assert (tmp_path / "audit_packet" / "audit_summary.md").exists()
    assert (tmp_path / "audit_packet" / "README_FOR_AUDITOR.md").exists()
    assert (tmp_path / "audit_packet.zip").exists()


def test_consistency_check_passes_for_clean_evidence(tmp_path: Path):
    headline = {
        "run_id": "run1",
        "final_equity": 3300.0,
        "total_return": 0.1,
        "max_drawdown_dollars": -100.0,
        "max_drawdown_pct": -0.0333,
        "number_of_trades": 3,
        "project_stop_mode": "both",
        "absolute_floor_stop_hit": False,
        "trailing_drawdown_stop_hit": True,
        "any_project_stop_hit": True,
        "first_project_stop_date": "2020-03-01",
        "target_300_before_any_stop": True,
        "target_400_before_any_stop": False,
    }
    (tmp_path / "headline_metrics.json").write_text(__import__("json").dumps(headline), encoding="utf-8")
    (tmp_path / "key_findings.json").write_text(
        __import__("json").dumps(
            {
                "main_result": {
                    "final_equity": 3300.0,
                    "total_return": 0.1,
                    "max_drawdown_dollars": -100.0,
                    "number_of_trades": 3,
                },
                "risk_findings": {"any_project_stop_hit": True},
            }
        ),
        encoding="utf-8",
    )
    pd.DataFrame(
        [
            {
                "target_300_before_any_stop": True,
                "target_400_before_any_stop": False,
                "absolute_floor_stop_hit": False,
                "trailing_drawdown_stop_hit": True,
                "any_project_stop_hit": True,
                "first_project_stop_date": "2020-03-01",
            }
        ]
    ).to_csv(tmp_path / "target_timing.csv", index=False)
    pd.DataFrame(
        [
            {
                "variant_name": "original_full_tournament",
                "slippage_label": "standard",
                "final_equity": 3300.0,
                "target_300_before_any_stop": True,
                "target_400_before_any_stop": False,
            }
        ]
    ).to_csv(tmp_path / "strategy_variant_results.csv", index=False)
    (tmp_path / "run_metadata.json").write_text(
        __import__("json").dumps(
            {
                "project_stop_mode": "both",
                "headline_metrics": headline,
                "main_run": {
                    "target_300_before_any_stop": True,
                    "target_400_before_any_stop": False,
                },
            }
        ),
        encoding="utf-8",
    )
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "summary_report.md").write_text("Final equity: $3,300.00", encoding="utf-8")

    result = consistency_check(tmp_path, run_dir, headline)

    assert result["passed"] is True
