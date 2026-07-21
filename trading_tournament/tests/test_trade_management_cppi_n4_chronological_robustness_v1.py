from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

import run_trade_management_cppi_n4_chronological_robustness_v1 as runner
from src.data import load_market_data
from src.indicators import prepare_indicators
from src.utils import load_config


@pytest.fixture(scope="module")
def selected_episodes() -> list[dict]:
    cfg = runner.correction.n4_only_config(load_config(runner.ROOT / "config.yaml"))
    load_result = load_market_data(cfg, runner.ROOT)
    prepared = prepare_indicators(load_result.data)
    return runner.select_new_episodes(config=cfg, prepared=prepared, load_result=load_result)


def test_non_overlapping_episode_selection_is_earliest_deterministic(selected_episodes: list[dict]) -> None:
    assert [episode["episode_label"] for episode in selected_episodes] == ["NEW_EPISODE_1", "NEW_EPISODE_2"]
    assert selected_episodes[0]["episode_start"] == "2013-04-30"
    assert selected_episodes[0]["initial_execution_date"] == "2013-05-01"
    assert selected_episodes[1]["episode_start"] == "2018-05-31"
    assert selected_episodes[1]["initial_execution_date"] == "2018-06-01"


def test_episode_maturity_is_exactly_five_calendar_years(selected_episodes: list[dict]) -> None:
    for episode in selected_episodes:
        start = pd.Timestamp(episode["episode_start"])
        maturity = pd.Timestamp(episode["exact_calendar_maturity_timestamp"])
        assert maturity == start + pd.DateOffset(years=5)
        assert pd.Timestamp(episode["final_valuation_date"]) >= maturity


def test_chronological_isolation_has_no_overlap_with_anchor_or_each_other(selected_episodes: list[dict]) -> None:
    anchor_final = pd.Timestamp("2013-04-01")
    first = selected_episodes[0]
    second = selected_episodes[1]
    assert pd.Timestamp(first["episode_start"]) > anchor_final
    assert pd.Timestamp(second["episode_start"]) > pd.Timestamp(first["final_valuation_date"])


def test_selection_freezes_before_results(selected_episodes: list[dict]) -> None:
    for episode in selected_episodes:
        assert episode["selected_before_performance_results"] is True
        assert episode["not_selected_by_return_drawdown_regime_or_overlay_behavior"] is True
        assert episode["selection_reason"] == runner.SELECTION_REASON


def _artifact(path: str) -> Path:
    target = runner.OUT_DIR / path
    if not target.exists():
        pytest.skip(f"{path} has not been generated yet")
    return target


def test_generated_identity_equivalence_passes_for_each_episode_and_cost() -> None:
    identity = pd.read_csv(_artifact("identity_equivalence.csv"))
    assert len(identity) == 6
    assert identity["complete_state_hash_match"].all()


def test_generated_safe_persistence_passes_for_each_safe_trial() -> None:
    diagnostics = pd.read_csv(_artifact("safe_persistence_diagnostics.csv"))
    assert len(diagnostics) == 18
    assert (diagnostics["safe_ledger_persistence_rate"] >= 0.99).all()
    assert (diagnostics["maximum_unexplained_end_of_day_broker_cash"] <= runner.BROKER_CASH_TOLERANCE).all()
    assert (diagnostics["internal_transfer_modeled_cost"] == 0.0).all()


def test_attribution_reconciles_total_dynamic_minus_base_by_episode_and_cost() -> None:
    attribution = pd.read_csv(_artifact("attribution_decomposition.csv"))
    for (episode_label, bps), group in attribution.groupby(["episode_label", "slippage_bps_per_side"]):
        by_effect = group.set_index("effect")["terminal_nav_delta"]
        chain = (
            by_effect["SAFE_SLEEVE_SUBSTITUTION"]
            + by_effect["STATIC_TARGET_CAP_EFFECT"]
            + by_effect["DYNAMIC_CPPI_INCREMENTAL_EFFECT"]
        )
        assert chain == pytest.approx(by_effect["TOTAL_DYNAMIC_MINUS_BASE"])


def test_kill_state_classification_helper_labels_base_safe_killed_static_dynamic_survive() -> None:
    kills = pd.DataFrame(
        [
            {"trial_name": "BASE", "n4_killed": True},
            {"trial_name": "SAFE5_TRANSLATION_CONTROL", "n4_killed": True},
            {"trial_name": "STATIC_CPPI_INITIAL_RISK_CAP_CONTROL", "n4_killed": False},
            {"trial_name": "DYNAMIC_CPPI", "n4_killed": False},
        ]
    )
    assert runner.kill_state_pattern(kills) == "BASE_AND_SAFE5_KILLED_STATIC_AND_DYNAMIC_SURVIVE"


def test_dynamic_vs_static_mechanism_labeling_is_not_survival_when_both_survive() -> None:
    metrics = [_metric("STATIC_CPPI_INITIAL_RISK_CAP_CONTROL", 0.10, 3300.0), _metric("DYNAMIC_CPPI", 0.15, 3450.0), _metric("BASE", 0.02, 3060.0), _metric("SAFE5_TRANSLATION_CONTROL", 0.08, 3240.0)]
    attribution = [
        {"episode_label": "E", "slippage_bps_per_side": 0.0, "effect": "TOTAL_DYNAMIC_MINUS_BASE", "safe_rate_accrual_delta": 50.0, "post_base_kill_participation": 25.0},
        {"episode_label": "E", "slippage_bps_per_side": 0.0, "effect": "DYNAMIC_CPPI_INCREMENTAL_EFFECT", "post_base_kill_participation": 0.0},
    ]
    kills = [
        {"episode_label": "E", "slippage_bps_per_side": 0.0, "trial_name": "BASE", "n4_killed": False},
        {"episode_label": "E", "slippage_bps_per_side": 0.0, "trial_name": "SAFE5_TRANSLATION_CONTROL", "n4_killed": False},
        {"episode_label": "E", "slippage_bps_per_side": 0.0, "trial_name": "STATIC_CPPI_INITIAL_RISK_CAP_CONTROL", "n4_killed": False},
        {"episode_label": "E", "slippage_bps_per_side": 0.0, "trial_name": "DYNAMIC_CPPI", "n4_killed": False},
    ]
    rows = runner.mechanism_classification_rows(metrics_rows=metrics, attribution_rows=attribution, kill_rows=kills, failure_rows=[])
    assert rows[0]["kill_state_pattern"] == "ALL_TRIALS_SURVIVE"
    assert rows[0]["dynamic_vs_static_mechanism"] in {
        "DYNAMIC_ALLOCATION_INCREMENTAL",
        "DYNAMIC_RISK_ADJUSTED_IMPROVEMENT",
        "DYNAMIC_EXPOSURE_INCREASE_ONLY",
    }


def test_cross_episode_decision_generation_requires_three_complete_episodes() -> None:
    matrix = [
        {"episode_label": "ANCHOR_EPISODE", "slippage_bps_per_side": 5.0, "return_difference_dynamic_minus_static": 0.01, "episode_level_classification": "DYNAMIC_BETTER_THAN_STATIC"},
        {"episode_label": "ANCHOR_EPISODE", "slippage_bps_per_side": 10.0, "return_difference_dynamic_minus_static": 0.01, "episode_level_classification": "DYNAMIC_BETTER_THAN_STATIC"},
        {"episode_label": "NEW_EPISODE_1", "slippage_bps_per_side": 5.0, "return_difference_dynamic_minus_static": -0.01, "episode_level_classification": "DYNAMIC_WORSE_THAN_STATIC"},
        {"episode_label": "NEW_EPISODE_1", "slippage_bps_per_side": 10.0, "return_difference_dynamic_minus_static": -0.01, "episode_level_classification": "DYNAMIC_WORSE_THAN_STATIC"},
    ]
    assert runner.cross_episode_conclusion(matrix_rows=matrix, concentration_rows=[], safe_diagnostics_rows=[]) == "INSUFFICIENT_COMPLETE_EPISODES"


def _metric(trial_name: str, total_return: float, terminal_nav: float) -> dict:
    return {
        "episode_label": "E",
        "episode_id": "E",
        "trial_name": trial_name,
        "slippage_bps_per_side": 0.0,
        "initial_nav": 3000.0,
        "terminal_nav": terminal_nav,
        "total_return": total_return,
        "return_to_drawdown": total_return / 0.05,
        "maximum_drawdown": -0.05,
        "average_risky_exposure": 0.4 if trial_name != "DYNAMIC_CPPI" else 0.5,
        "turnover": 1.0 if trial_name != "DYNAMIC_CPPI" else 1.1,
        "corrected_modeled_transaction_cost": 0.0,
    }
