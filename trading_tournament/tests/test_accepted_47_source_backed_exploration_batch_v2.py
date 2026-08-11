from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from strategy_lab.research_os.research import accepted_47_source_backed_exploration_batch_v2 as batch


def test_materialized_intake_has_exact_file_set_and_no_trial_entities() -> None:
    assert {path.name for path in batch.SOURCE_DIR.iterdir() if path.is_file()} == set(
        batch.SOURCE_FILES
    )
    manifest = yaml.safe_load((batch.SOURCE_DIR / "intake_manifest.yaml").read_text(encoding="utf-8"))
    assert manifest["experiment_trial_entities_created"] == 0
    assert manifest["provider_requirement_count"] == 0


def test_source_packet_reconciles_exact_candidates_trials_and_families() -> None:
    specs, reconciliation = batch.load_source_packet()
    assert reconciliation["pass"]
    assert [spec.strategy_id for spec in specs] == [batch.MCA_ID, batch.HYG_ID]
    assert [spec.trial_id for spec in specs] == [batch.MCA_TRIAL, batch.HYG_TRIAL]
    assert len({spec.family_id for spec in specs}) == 2


def test_mca_frozen_formula_fixture_pins_rank_orientation_and_weights() -> None:
    result = batch.formula_fixture_result()
    assert result["pass"]
    assert result["observed_diagnostics"]["ranks"] == [2.0, 1.0, 3.0]
    assert np.allclose(
        result["observed_weights"],
        [0.38143896754606743, 0.4607880171964826, 0.15777301525744994],
        atol=1e-14,
        rtol=0.0,
    )


def test_mca_zero_off_diagonal_dispersion_is_invalid() -> None:
    correlation = np.full((3, 3), 0.2)
    np.fill_diagonal(correlation, 1.0)
    with pytest.raises(ValueError, match="dispersion"):
        batch.minimum_correlation_from_matrix(correlation, np.array([0.1, 0.2, 0.3]))


def test_sma_seeded_ema_uses_first_100_values_then_alpha_2_over_101() -> None:
    index = pd.bdate_range("2024-01-01", periods=101)
    values = pd.Series(np.arange(1.0, 102.0), index=index)
    ema = batch.sma_seeded_ema(values, 100)
    expected_seed = float(values.iloc[:100].mean())
    expected_next = (2.0 / 101.0) * 101.0 + (99.0 / 101.0) * expected_seed
    assert ema.iloc[:99].isna().all()
    assert ema.iloc[99] == expected_seed
    assert ema.iloc[100] == pytest.approx(expected_next, abs=1e-14)


def test_following_session_is_strictly_later() -> None:
    index = pd.DatetimeIndex(["2024-01-02", "2024-01-03", "2024-01-05"])
    assert batch.following_session(index, pd.Timestamp("2024-01-03")) == pd.Timestamp(
        "2024-01-05"
    )


def test_mca_ledger_has_exact_window_and_lagged_execution() -> None:
    ledger = pd.read_csv(batch.OUTPUT_DIR / "mca_weekly_allocation_ledger.csv")
    valid = ledger[ledger["formation_valid"].astype(str).str.lower() == "true"].copy()
    assert len(valid) > 104
    assert (valid["formation_window_closes"] == 61).all()
    assert (valid["formation_window_returns"] == 60).all()
    assert (
        pd.to_datetime(valid["execution_date"]) > pd.to_datetime(valid["signal_date"])
    ).all()


def test_hyg_ledger_uses_full_hyg_history_ema_seed_and_executes_later() -> None:
    ledger = pd.read_csv(batch.OUTPUT_DIR / "hyg_daily_signal_ledger.csv")
    hyg = batch.base.load_frame("HYG")["close"]
    full_ema = batch.sma_seeded_ema(hyg, 100)
    recorded_average = pd.to_numeric(ledger["hyg_sma_seeded_ema100"], errors="coerce")
    first_recorded_position = int(np.flatnonzero(recorded_average.notna().to_numpy())[0])
    first_recorded_date = pd.Timestamp(ledger.iloc[first_recorded_position]["signal_date"])
    recorded = float(recorded_average.iloc[first_recorded_position])
    assert recorded == pytest.approx(float(full_ema.loc[first_recorded_date]), abs=1e-14)
    assert full_ema.first_valid_index() == hyg.index[99]
    changed = ledger[
        ledger["execution_status"] == "target_change_scheduled_following_session_close"
    ]
    assert (
        pd.to_datetime(changed["intended_execution_date"])
        > pd.to_datetime(changed["signal_date"])
    ).all()


def test_turnover_contract_prices_full_rotation_once() -> None:
    prior = np.array([1.0, 0.0])
    target = np.array([0.0, 1.0])
    turnover = 0.5 * np.abs(target - prior).sum()
    assert turnover == 1.0
    assert turnover * 5.0 / 10000.0 == 0.0005


def test_evidence_packet_has_exact_outputs_and_entity_counts() -> None:
    assert {path.name for path in batch.OUTPUT_DIR.iterdir() if path.is_file()} == set(
        batch.REQUIRED_OUTPUTS
    )
    cards = pd.read_csv(batch.OUTPUT_DIR / "strategy_cards.csv")
    trials = pd.read_csv(batch.OUTPUT_DIR / "trial_ledger.csv")
    benchmarks = pd.read_csv(batch.OUTPUT_DIR / "benchmark_reference_log.csv")
    funnel = json.loads((batch.OUTPUT_DIR / "cohort_funnel_counts.json").read_text(encoding="utf-8"))
    assert len(cards) == len(trials) == 2
    assert len(benchmarks) == 10
    assert funnel["strategy_configurations"] == 2
    assert funnel["canonical_experiment_trials"] == 2
    assert funnel["data_capability_tasks"] == 0


def test_both_outcomes_and_exact_next_action_are_recorded() -> None:
    outcomes = pd.read_csv(batch.OUTPUT_DIR / "outcome_summary.csv")
    next_actions = pd.read_csv(batch.OUTPUT_DIR / "next_actions.csv")
    assert set(outcomes["outcome"]) == {"exploratory_followup_candidate_standalone"}
    assert outcomes["minimum_evidence_pass"].astype(str).str.lower().eq("true").all()
    assert outcomes["lightweight_concentration_pass"].astype(str).str.lower().eq("true").all()
    assert next_actions.iloc[0]["exact_next_action"] == (
        "direction_owner_review_accepted_47_source_backed_batch_v2"
    )


def test_no_provider_broker_lifecycle_or_cache_write_capability_is_imported() -> None:
    source = Path(batch.__file__).read_text(encoding="utf-8").lower()
    prohibited = ("import requests", "submit_order", "place_order", "active_observations.yaml\").write", "strategy_registry.yaml\").write")
    assert not any(token in source for token in prohibited)
    consistency = json.loads((batch.OUTPUT_DIR / "consistency_check.json").read_text(encoding="utf-8"))
    assert consistency["overall_pass"]
    assert consistency["protected_state_cache_source_packet_and_prior_evidence_unchanged"]
