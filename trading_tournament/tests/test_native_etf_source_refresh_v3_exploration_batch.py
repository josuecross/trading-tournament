from __future__ import annotations

import csv
import json

import numpy as np
import pandas as pd
import pytest

from strategy_lab.research_os.research import (
    native_etf_source_refresh_v3_exploration_batch as task,
)


def test_preregistered_entity_counts_and_lineage_are_exact() -> None:
    strategies = task.strategy_rows()
    trials = task.trial_rows()
    assert len(task.source_rows()) == 2
    assert len(strategies) == 2
    assert len(trials) == 2
    assert len({row["family_id"] for row in strategies}) == 2
    assert {row["trial_id"] for row in trials} == {
        task.PERCENTILE_TRIAL,
        task.GROWTH_TRIAL,
    }
    assert all(row["parent_trial_id"] == "" for row in trials)
    assert all(row["adaptation_label"] == "" for row in trials)
    assert all(row["optimization_performed"] is False for row in trials)
    assert all(row["provider_access_performed"] is False for row in trials)


def test_percentile_contract_is_excel_type7_linear() -> None:
    values = np.array([1.0, 2.0, 3.0, 4.0])
    assert task.percentile_type7(values, 0.75) == pytest.approx(3.25)
    assert task.percentile_type7(values, 0.25) == pytest.approx(1.75)


def test_percentile_hysteresis_uses_strict_inequalities_and_initial_minus_one() -> None:
    assert task.update_hysteresis_state(None, 11.0, 10.0, 5.0) == -1
    assert task.update_hysteresis_state(-1, 10.0, 10.0, 5.0) == -1
    assert task.update_hysteresis_state(-1, 10.01, 10.0, 5.0) == 1
    assert task.update_hysteresis_state(1, 5.0, 10.0, 5.0) == 1
    assert task.update_hysteresis_state(1, 4.99, 10.0, 5.0) == -1


def test_percentile_weight_denominator_includes_negative_raw_scores() -> None:
    scores = {"SPY": 1.0, "VNQ": 0.5, "LQD": 0.0, "DBC": -0.5}
    volatilities = {symbol: 1.0 for symbol in task.PERCENTILE_RISKY}
    target = task.channel_allocation(scores, volatilities, use_volatility=False)
    assert target["SPY"] == pytest.approx(0.5)
    assert target["VNQ"] == pytest.approx(0.25)
    assert target["LQD"] == pytest.approx(0.0)
    assert target["DBC"] == pytest.approx(0.0)
    assert target["SHY"] == pytest.approx(0.25)
    assert sum(target.values()) == pytest.approx(1.0)


def test_original_growth_inflation_basket_weights_are_exact() -> None:
    returns = pd.DataFrame(
        {
            "XLE": [0.10], "XLI": [0.06], "XLF": [0.03], "XLB": [0.00],
            "XLU": [-0.03], "XLV": [0.06], "XLP": [0.00],
        }
    )
    positive, negative = task.growth_basket_returns(returns)
    assert positive.iloc[0] == pytest.approx(0.065)
    assert negative.iloc[0] == pytest.approx(0.01)


def test_cumulative_inflation_indexes_start_at_one_without_smoothing() -> None:
    values = pd.Series([np.nan, 0.10, -0.05])
    index = task.cumulative_index_from_returns(values)
    assert index.iloc[0] == pytest.approx(1.0)
    assert index.iloc[1] == pytest.approx(1.10)
    assert index.iloc[2] == pytest.approx(1.045)


def test_growth_and_inflation_equality_retains_prior_state() -> None:
    assert task.update_direction_state(None, 1.0, 1.0, "up", "down") is None
    assert task.update_direction_state("up", 1.0, 1.0, "up", "down") == "up"
    assert task.update_direction_state("down", 2.0, 1.0, "up", "down") == "up"


@pytest.fixture(scope="module")
def prepared_data() -> tuple[dict[str, pd.DataFrame], dict[str, bool]]:
    _rows, frames, candidate_pass = task.preflight()
    return frames, candidate_pass


def test_existing_cache_preflight_passes_without_provider(
    prepared_data: tuple[dict[str, pd.DataFrame], dict[str, bool]],
) -> None:
    frames, candidate_pass = prepared_data
    assert set(frames) == set(task.REQUIRED_SYMBOLS)
    assert candidate_pass == {task.PERCENTILE_ID: True, task.GROWTH_ID: True}


def test_prepared_event_targets_are_fully_invested_and_nonnegative(
    prepared_data: tuple[dict[str, pd.DataFrame], dict[str, bool]],
) -> None:
    frames, _ = prepared_data
    for prepared in (
        task.prepare_percentile_channels(frames),
        task.prepare_growth_inflation(frames),
    ):
        events = prepared["candidate_events"]
        assert np.allclose(events.sum(axis=1), 1.0)
        assert (events.to_numpy(dtype=float) >= 0.0).all()
        assert len(prepared["valid_formations"]) > 0


def test_required_packet_is_complete_and_consistent_after_run() -> None:
    if not task.OUTPUT_DIR.exists():
        pytest.skip("V3 serial runner has not generated the packet")
    assert {path.name for path in task.OUTPUT_DIR.iterdir() if path.is_file()} == task.REQUIRED_FILES
    consistency = json.loads((task.OUTPUT_DIR / "consistency_check.json").read_text(encoding="utf-8"))
    assert consistency["exactly_two_canonical_trials"] is True
    assert consistency["provider_access_zero"] is True
    assert consistency["protected_state_cache_prior_evidence_unchanged"] is True
    assert consistency["overall_pass"] is True
    outcomes = list(csv.DictReader((task.OUTPUT_DIR / "outcome_summary.csv").open(newline="", encoding="utf-8")))
    assert len(outcomes) == 2
    assert {row["strategy_id"] for row in outcomes} == {task.PERCENTILE_ID, task.GROWTH_ID}
