from __future__ import annotations

import csv
import json

import numpy as np
import pandas as pd
import pytest

from strategy_lab.research_os.research import (
    native_etf_source_refresh_v2_exploration_batch as batch,
)


def test_exact_two_candidate_preregistration_contract() -> None:
    strategies = batch.strategy_rows()
    trials = batch.trial_rows()
    assert [row["strategy_id"] for row in strategies] == [batch.VORTEX_ID, batch.REAL_ID]
    assert {row["family_id"] for row in strategies} == {
        "cross_bar_vortex_directional_state",
        "inflation_adjusted_real_return_state",
    }
    assert [row["trial_id"] for row in trials] == [batch.VORTEX_TRIAL, batch.REAL_TRIAL]
    assert all(row["parent_trial_id"] == "" for row in trials)
    assert all(row["adaptation_label"] == "" for row in trials)
    assert all(row["optimization_performed"] is False for row in trials)
    assert len(batch.benchmark_rows()) == 10


def test_cache_preflight_is_complete_and_provider_free() -> None:
    rows, frames = batch.preflight()
    assert set(frames) == set(batch.REQUIRED_SYMBOLS)
    assert all(row["preflight_status"] == "pass" for row in rows)
    assert all(row["provider_access_performed"] is False for row in rows)
    assert all(not frame.empty for frame in frames.values())


def test_wilder_initialization_and_recursion_are_exact() -> None:
    index = pd.date_range("2026-01-01", periods=16, freq="D")
    values = pd.Series(np.arange(1.0, 17.0), index=index)
    smoothed = batch.wilder_smoothed(values, 14)
    assert smoothed.iloc[:13].isna().all()
    assert smoothed.iloc[13] == pytest.approx(sum(range(1, 15)))
    expected_15 = sum(range(1, 15)) - sum(range(1, 15)) / 14.0 + 15.0
    assert smoothed.iloc[14] == pytest.approx(expected_15)
    assert smoothed.iloc[15] == pytest.approx(expected_15 - expected_15 / 14.0 + 16.0)


def test_vortex_formula_events_and_explicit_weights() -> None:
    _, frames = batch.preflight()
    prepared = batch.prepare_vortex(frames)
    diagnostics = prepared["diagnostics"]
    eligible = diagnostics.loc[
        (diagnostics["row_type"] == "eligible_date") & diagnostics["signal_valid"]
    ].iloc[0]
    assert eligible["VI_plus"] == pytest.approx(
        eligible["rolling_VM_plus_sum14"] / eligible["rolling_TR_sum14"]
    )
    assert eligible["VI_minus"] == pytest.approx(
        eligible["rolling_VM_minus_sum14"] / eligible["rolling_TR_sum14"]
    )
    assert np.isclose(prepared["candidate_events"].sum(axis=1), 1.0).all()
    assert (prepared["candidate_events"] >= 0.0).all().all()
    assert prepared["transition_count"] >= 20


def test_real_momentum_formula_and_monthly_timing_are_frozen() -> None:
    _, frames = batch.preflight()
    prepared = batch.prepare_real_momentum(frames)
    daily = prepared["daily_diagnostics"].dropna(subset=["SmoothedInflation5", "RealMomentum120"])
    row = daily.iloc[0]
    assert row["InflationChange"] == pytest.approx(row["TIP_return"] - row["IEF_return"])
    assert row["RealEquityReturn"] == pytest.approx(row["SPY_return"] - row["SmoothedInflation5"])
    monthly = prepared["monthly_diagnostics"]
    valid = monthly.loc[monthly["formation_valid"] == True]  # noqa: E712
    assert len(valid) >= 48
    executable = valid.loc[valid["intended_execution_date"] != ""]
    assert all(
        pd.Timestamp(value) > pd.Timestamp(date_value)
        for date_value, value in zip(
            executable["formation_date"], executable["intended_execution_date"]
        )
    )
    assert (valid["execution_status"] == "blocked_missing_execution_session").sum() <= 1
    assert np.isclose(prepared["candidate_events"].sum(axis=1), 1.0).all()
    assert (prepared["candidate_events"] >= 0.0).all().all()


def test_evidence_packet_reconciles_after_serial_run() -> None:
    if not (batch.OUTPUT_DIR / "consistency_check.json").exists():
        pytest.skip("serial batch has not run")
    assert {path.name for path in batch.OUTPUT_DIR.iterdir() if path.is_file()} == batch.REQUIRED_FILES
    consistency = json.loads((batch.OUTPUT_DIR / "consistency_check.json").read_text(encoding="utf-8"))
    assert consistency["exactly_two_canonical_trials"] is True
    assert consistency["two_distinct_families"] is True
    assert consistency["provider_access_zero"] is True
    assert consistency["protected_state_cache_and_prior_evidence_unchanged"] is True
    assert consistency["overall_pass"] is True
    with (batch.OUTPUT_DIR / "trial_ledger.csv").open(newline="", encoding="utf-8") as handle:
        trials = list(csv.DictReader(handle))
    assert len(trials) == 2
    with (batch.OUTPUT_DIR / "portfolio_contribution_results.csv").open(
        newline="", encoding="utf-8"
    ) as handle:
        portfolios = list(csv.DictReader(handle))
    assert all("inner_turnover" in row and "outer_turnover" in row for row in portfolios)
    with (batch.OUTPUT_DIR / "real_momentum_monthly_signal_ledger.csv").open(
        newline="", encoding="utf-8"
    ) as handle:
        monthly = list(csv.DictReader(handle))
    summary_metrics = {row.get("summary_metric") for row in monthly}
    assert "state_duration_median_sessions" in summary_metrics
