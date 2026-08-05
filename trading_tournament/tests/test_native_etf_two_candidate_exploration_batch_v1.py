from __future__ import annotations

import csv
import json

import numpy as np
import pandas as pd

from strategy_lab.research_os.research import (
    native_etf_two_candidate_exploration_batch_v1 as batch,
)


def read_rows(name: str) -> list[dict[str, str]]:
    with (batch.OUTPUT_DIR / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_scope_has_exactly_two_distinct_frozen_candidates() -> None:
    strategies = batch.strategy_definitions()
    assert [row["strategy_id"] for row in strategies] == [batch.VIX_ID, batch.FAA_ID]
    assert len({row["family_id"] for row in strategies}) == 2
    assert [row["trial_id"] for row in strategies] == [batch.VIX_TRIAL, batch.FAA_TRIAL]
    assert all(row["parent_trial_id"] == "" for row in strategies)
    assert all(row["adaptation_label"] == "" for row in strategies)


def test_gate_override_is_process_record_not_strategy_or_trial() -> None:
    rows = read_rows("gate_override_record.csv")
    assert len(rows) == 1
    row = rows[0]
    assert row["qualified_cohort_minimum"] == "2"
    assert row["qualified_cohort_maximum"] == "4"
    assert row["minimum_distinct_families"] == "2"
    assert row["entity_type"] == "direction_owner_process_record"
    assert row["counted_as_strategy"] == "false"
    assert row["counted_as_trial"] == "false"


def test_deterministic_rank_ties_are_lexical() -> None:
    values = pd.Series({"ZZZ": 1.0, "AAA": 1.0, "MMM": 2.0})
    descending = batch.deterministic_ranks(values, ascending=False)
    ascending = batch.deterministic_ranks(values, ascending=True)
    assert descending == {"MMM": 1, "AAA": 2, "ZZZ": 3}
    assert ascending == {"AAA": 1, "ZZZ": 2, "MMM": 3}


def test_vix_fix_cross_executes_at_following_session_close() -> None:
    dates = pd.bdate_range("2024-01-02", periods=7)
    indicator = pd.Series([np.nan, 1.2, 0.8, 0.7, 1.3, 1.2, 1.1], index=dates)
    average = pd.Series([np.nan, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0], index=dates)
    events, diagnostics = batch.state_events(indicator, average, dates, "probe")
    assert events.loc[dates[0]].to_dict() == {"SPY": 0.0, "BIL": 1.0}
    assert events.loc[dates[3]].to_dict() == {"SPY": 1.0, "BIL": 0.0}
    assert events.loc[dates[5]].to_dict() == {"SPY": 0.0, "BIL": 1.0}
    entry = diagnostics.loc[diagnostics["entry_cross"]].iloc[0]
    exit_row = diagnostics.loc[diagnostics["exit_cross"]].iloc[0]
    assert entry["signal_date"] == dates[2].date().isoformat()
    assert entry["intended_execution_date"] == dates[3].date().isoformat()
    assert exit_row["signal_date"] == dates[4].date().isoformat()
    assert exit_row["intended_execution_date"] == dates[5].date().isoformat()
    assert (diagnostics["state_duration_sessions"] >= 0).all()


def test_faa_absolute_momentum_replacements_aggregate_in_shy() -> None:
    returns = pd.Series(
        {"SPY": 0.20, "EFA": -0.05, "VWO": -0.02, "SHY": 0.01, "AGG": 0.0, "GSG": 0.0, "VNQ": 0.0}
    )
    scores = {"SPY": 1.0, "EFA": 2.0, "VWO": 3.0, "SHY": 4.0, "AGG": 5.0, "GSG": 6.0, "VNQ": 7.0}
    target, selected, replacements = batch._selected_target(
        returns, scores, batch.FAA_UNIVERSE
    )
    assert selected == ["SPY", "EFA", "VWO"]
    assert replacements == ["EFA", "VWO"]
    assert target["SPY"] == 1.0 / 3.0
    assert target["SHY"] == 2.0 / 3.0
    assert np.isclose(sum(target.values()), 1.0)
    assert all(value >= 0.0 for value in target.values())


def test_signed_target_change_turnover_and_cost_are_exact() -> None:
    index = pd.bdate_range("2024-01-02", periods=3)
    prices = pd.DataFrame({"SPY": 100.0, "BIL": 100.0}, index=index)
    events = batch.accounting.event_frame(
        index,
        batch.VIX_UNIVERSE,
        {
            index[0]: {"SPY": 0.0, "BIL": 1.0},
            index[1]: {"SPY": 1.0, "BIL": 0.0},
        },
    )
    path = batch.accounting.simulate_path(prices, events, 5.0, "probe")
    assert np.isclose(path["turnover"].iloc[0], 0.5)
    assert np.isclose(path["turnover"].iloc[1], 1.0)
    assert np.isclose(path["cost"].iloc[0], 0.5 * 5.0 / 10000.0)
    assert np.isclose(path["cost"].iloc[1], 1.0 * 5.0 / 10000.0)


def test_generated_vix_formula_matches_frozen_definition() -> None:
    _, frames = batch.data_preflight()
    prepared = batch.prepare_vix(frames)
    diagnostics = prepared["diagnostics"]
    signal = diagnostics.loc[
        (diagnostics["row_type"] == "signal") & diagnostics["vix_fix"].notna()
    ].iloc[0]
    date_value = pd.Timestamp(signal["signal_date"])
    spy = frames["SPY"]
    location = spy.index.get_loc(date_value)
    window = spy.iloc[location - 19 : location + 1]
    highest = float(window["close"].max())
    expected = 100.0 * (highest - float(spy.loc[date_value, "low"])) / highest
    assert np.isclose(signal["highest_close20"], highest)
    assert np.isclose(signal["vix_fix"], expected)


def test_generated_faa_formations_use_all_seven_assets_and_frozen_score() -> None:
    rows = read_rows("faa_diagnostics.csv")
    valid = pd.DataFrame(
        row for row in rows if row["row_type"] == "formation_asset"
    )
    first_date = valid["formation_date"].min()
    formation = valid.loc[valid["formation_date"] == first_date]
    assert set(formation["asset"]) == set(batch.FAA_UNIVERSE)
    assert len(formation) == 7
    assert sum(value == "true" for value in formation["selected_candidate"]) == 3
    for _, row in formation.iterrows():
        expected = (
            float(row["return_rank"])
            + 0.5 * float(row["volatility_rank"])
            + 0.5 * float(row["correlation_rank"])
        )
        assert np.isclose(float(row["faa_score"]), expected)
    assert np.isclose(formation["candidate_target_weight"].astype(float).sum(), 1.0)


def test_evidence_entity_counts_and_prohibited_actions() -> None:
    funnel = json.loads((batch.OUTPUT_DIR / "cohort_funnel_counts.json").read_text())
    assert funnel["source_library_records"] == 2
    assert funnel["strategy_configurations"] == 2
    assert funnel["canonical_experiment_trials"] == 2
    assert funnel["distinct_families"] == 2
    assert funnel["data_capability_tasks"] == 0
    assert funnel["validation_observations"] == 0
    assert funnel["paper_demo_observations"] == 0
    manifest = (batch.OUTPUT_DIR / "batch_manifest.yaml").read_text()
    assert "provider_access_performed: false" in manifest
    assert "validation_performed: false" in manifest
    assert "lifecycle_state_changed: false" in manifest
    assert "barbara_decelerated_psar_spy_bil_v1" not in manifest


def test_all_benchmark_rows_remain_references() -> None:
    rows = read_rows("benchmark_reference_log.csv")
    assert len(rows) == len(batch.VIX_CONTROLS) + len(batch.FAA_CONTROLS)
    assert all(row["entity_type"] == "benchmark_reference" for row in rows)
    assert all(row["stage"] == "benchmark_reference_only" for row in rows)
    assert all(row["counted_as_strategy"] == "false" for row in rows)
    assert all(row["counted_as_trial"] == "false" for row in rows)


def test_all_generated_invariants_and_consistency_pass() -> None:
    invariants = read_rows("invariant_results.csv")
    assert invariants
    assert all(row["status"] == "pass" for row in invariants)
    consistency = json.loads((batch.OUTPUT_DIR / "consistency_check.json").read_text())
    assert consistency["overall_pass"] is True
    assert consistency["protected_state_cache_and_prior_evidence_unchanged"] is True
    assert consistency["exactly_two_canonical_trials"] is True


def test_all_required_outputs_exist() -> None:
    assert all((batch.OUTPUT_DIR / name).is_file() for name in batch.REQUIRED_FILES)
