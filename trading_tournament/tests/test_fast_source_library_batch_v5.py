from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from strategy_lab.research_os.research import fast_source_library_batch_v5 as batch


REQUIRED_ARTIFACTS = [
    "batch_manifest.yaml",
    "source_record_references.csv",
    "strategy_cards.csv",
    "trial_ledger.csv",
    "benchmark_reference_log.csv",
    "process_task_log.csv",
    "data_preflight_reconciliation.csv",
    "all_trial_results.csv",
    "control_results.csv",
    "chronological_half_results.csv",
    "calendar_event_diagnostics.csv",
    "indicator_state_diagnostics.csv",
    "cost_diagnostics.csv",
    "invariant_results.csv",
    "exploratory_followup_candidates.csv",
    "failure_reasons.csv",
    "next_actions.csv",
    "outcome_summary.csv",
    "cohort_funnel_counts.json",
    "batch_report.md",
    "consistency_check.json",
]


def setup_module() -> None:
    batch.run()


def _rows(name: str) -> list[dict[str, str]]:
    with (batch.OUTPUT_DIR / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _json(name: str) -> dict:
    return json.loads((batch.OUTPUT_DIR / name).read_text(encoding="utf-8"))


def _yaml(name: str) -> dict:
    return yaml.safe_load((batch.OUTPUT_DIR / name).read_text(encoding="utf-8"))


def test_exact_scope_and_required_artifacts() -> None:
    for artifact in REQUIRED_ARTIFACTS:
        assert (batch.OUTPUT_DIR / artifact).exists(), artifact
    manifest = _yaml("batch_manifest.yaml")
    assert manifest["batch_id"] == "fast_source_library_batch_v5"
    assert tuple(manifest["strategy_ids"]) == batch.EXPECTED_STRATEGY_IDS
    assert manifest["strategy_count"] == 4
    assert manifest["canonical_trial_count"] == 4
    assert manifest["stage"] == "exploration"
    assert manifest["cost_assumptions_bps_per_one_way_turnover"] == [0.0, 5.0, 10.0]
    assert manifest["primary_cost_bps"] == 5.0
    assert manifest["validation_claimed"] is False
    assert manifest["promotion_authorized"] is False
    assert manifest["paper_demo_authorized"] is False


def test_frozen_source_specs_are_parsed_without_variants_or_unknown_metadata() -> None:
    cards = batch.load_cards()
    assert tuple(card.strategy_id for card in cards) == batch.EXPECTED_STRATEGY_IDS
    by_id = {card.strategy_id: card for card in cards}
    assert by_id["chande_aroon_oscillator_25_90_spy_bil_v1"].parameters["parameters"] == {
        "lookback_sessions": 25,
        "bullish_threshold": 90.0,
        "bearish_threshold": -90.0,
        "extreme_tie_rule": "most_recent_occurrence",
    }
    assert by_id["pring_kst_default_centerline_spy_bil_v1"].parameters["parameters"] == {
        "roc_periods": [10, 15, 20, 30],
        "smoothing_SMAs": [10, 10, 10, 15],
        "component_weights": [1.0, 2.0, 3.0, 4.0],
        "centerline": 0.0,
    }
    cards_rows = _rows("strategy_cards.csv")
    trials = _rows("trial_ledger.csv")
    assert len(cards_rows) == len(trials) == 4
    assert {row["entity_type"] for row in cards_rows} == {"strategy_configuration"}
    assert {row["entity_type"] for row in trials} == {"experiment_trial"}
    assert {row["stage"] for row in cards_rows + trials} == {"exploration"}
    assert all(row["parent_trial_id"] == "" and row["adaptation_label"] == "" for row in trials)
    required = {
        "strategy_id",
        "family_id",
        "display_name",
        "strategy_architecture",
        "source_or_research_lineage",
        "instrument_universe",
        "parameters",
        "benchmark_or_control",
        "trial_id",
        "outcome",
        "next_action",
    }
    assert all(all(row[field] for field in required) for row in cards_rows)


def test_aroon_tie_rule_and_kst_formula_are_frozen() -> None:
    values = np.array([5.0, 10.0, 7.0, 10.0])
    assert batch._most_recent_extreme_score(values, True, 4) == 100.0
    assert batch._most_recent_extreme_score(np.array([5.0, 1.0, 4.0, 1.0]), False, 4) == 100.0

    index = pd.date_range("2020-01-01", periods=80, freq="B")
    close = pd.Series(np.linspace(100.0, 160.0, len(index)), index=index)
    actual = batch.kst_value(close)
    expected = sum(
        weight
        * (100.0 * (close / close.shift(roc_period) - 1.0)).rolling(
            smoothing, min_periods=smoothing
        ).mean()
        for roc_period, smoothing, weight in zip(
            (10, 15, 20, 30), (10, 10, 10, 15), (1.0, 2.0, 3.0, 4.0)
        )
    )
    pd.testing.assert_series_equal(actual, expected.rename("kst"))


def test_calendar_rules_are_prior_close_and_do_not_use_future_or_unscheduled_closures() -> None:
    assert date_value("2018-12-05") not in batch.scheduled_full_day_nyse_closures(2018)
    prices = batch.prior.load_price_frame(("SPY", "BIL")).dropna()
    events, episodes = batch.preholiday_schedule(prices.index)
    assert episodes
    assert len({episode["active_start"] for episode in episodes}) == len(episodes)
    assert all(
        0 < (episode["closure_date"] - episode["active_start"]).days <= 4
        for episode in episodes
    )
    assert all(
        prices.index.get_loc(episode["active_start"])
        == prices.index.get_loc(episode["signal_date"]) + 1
        for episode in episodes
    )
    assert set(events.columns) == {"SPY", "BIL"}

    january_events, january_episodes = batch.january_schedule(prices.index, "SPY")
    path = batch.simulate_path(
        prices,
        january_events,
        0.0,
        "known_calendar_target_set_at_prior_close_for_following_active_session",
    )
    held = path["held_weights"]["SPY"] > 0.5
    assert held.any()
    assert all(timestamp.month == 1 for timestamp in held.index[held])
    assert len(january_episodes) == len(set(prices.index.year)) - 1


def date_value(value: str):
    return pd.Timestamp(value).date()


def test_actual_pretrade_turnover_and_following_session_timing() -> None:
    index = pd.date_range("2024-01-02", periods=3, freq="B")
    prices = pd.DataFrame(
        {
            "A": [100.0, 200.0, 200.0],
            "B": [100.0, 100.0, 100.0],
        },
        index=index,
    )
    events = batch.event_frame(
        index,
        ("A", "B"),
        {
            index[0]: {"A": 0.5, "B": 0.5},
            index[1]: {"A": 0.5, "B": 0.5},
        },
    )
    path = batch.simulate_path(prices, events, 0.0, "test")
    assert path["returns"].iloc[0] == 0.0
    assert path["returns"].iloc[1] == 0.5
    assert np.isclose(path["turnover"].iloc[0], 0.5)
    assert np.isclose(path["turnover"].iloc[1], 1.0 / 6.0)
    assert np.isclose(path["held_weights"].iloc[1]["A"], 0.5)


def test_cache_preflight_and_matching_dates_pass_without_provider_access() -> None:
    rows = _rows("data_preflight_reconciliation.csv")
    assert len(rows) == 9
    assert {row["symbol"] for row in rows} == {"SPY", "BIL", "IWM"}
    assert all(row["candidate_preflight_status"] == "pass" for row in rows)
    assert all(row["ordered_unique_dates"] == "true" for row in rows)
    assert all(row["nonfinite_value_count"] == "0" for row in rows)
    assert all(row["nonpositive_price_count"] == "0" for row in rows)
    assert all(row["invalid_ohlc_count"] == "0" for row in rows)
    assert all(row["adjustment_compatibility_mismatch_count"] == "0" for row in rows)
    assert all(row["internal_common_calendar_gap_count"] == "0" for row in rows)
    assert {row["candidate_common_start"] for row in rows} == {"2007-05-30"}
    assert {row["candidate_common_end"] for row in rows} == {"2026-06-18"}
    consistency = _json("consistency_check.json")
    assert consistency["forbidden_actions"]["provider_download"] is False


def test_results_controls_halves_diagnostics_and_gate_reconcile() -> None:
    trials = _rows("all_trial_results.csv")
    controls = _rows("control_results.csv")
    halves = _rows("chronological_half_results.csv")
    invariants = _rows("invariant_results.csv")
    assert len(trials) == 4 * 3
    assert len(controls) == 4 * 2 * 3
    assert len(halves) == (4 + 8) * 3 * 2
    assert len(invariants) == 4 * 3 + 4 * 2 * 3
    assert {row["cost_assumption_bps"] for row in trials + controls} == {"0", "5", "10"}
    assert {row["period_label"] for row in halves} == {
        "first_chronological_half",
        "second_chronological_half",
    }
    assert all("not_clean_or_sealed_holdout" in row["period_role"] for row in halves)
    assert all(row["invariant_pass"] == "true" for row in invariants)
    assert all(row["target_zero_weights_preserved"] == "true" for row in invariants)
    assert all(row["stale_weight_forward_fill_used"] == "false" for row in invariants)
    assert all(row["same_period_price_signal_return_used"] == "false" for row in invariants)

    indicator = _rows("indicator_state_diagnostics.csv")
    calendar = _rows("calendar_event_diagnostics.csv")
    assert len(indicator) == 2 * 3
    assert len(calendar) == 2 * 3
    assert all(int(row["entry_count"]) < 200 for row in indicator)
    assert all(int(row["active_window_count"]) > 0 for row in calendar)


def test_entity_separation_funnel_outcomes_and_next_action() -> None:
    benchmarks = _rows("benchmark_reference_log.csv")
    process = _rows("process_task_log.csv")
    outcomes = _rows("outcome_summary.csv")
    funnel = _json("cohort_funnel_counts.json")
    assert len(benchmarks) == 8
    assert {row["entity_type"] for row in benchmarks} == {"benchmark_reference"}
    assert {row["stage"] for row in benchmarks} == {"benchmark_reference_only"}
    assert all(row["counted_as_strategy"] == "false" for row in benchmarks)
    assert len(process) == 1
    assert process[0]["entity_type"] == "process_task"
    assert process[0]["strategy_count"] == process[0]["trial_count"] == "0"
    assert len(outcomes) == 4
    assert funnel["source_library_records_referenced"] == 4
    assert funnel["strategy_configurations_considered"] == 4
    assert funnel["experiment_trials_recorded"] == 4
    assert funnel["experiment_trials_executed"] == 4
    assert funnel["benchmark_references"] == 8
    assert funnel["process_tasks"] == 1
    assert (
        funnel["standalone_followup_candidates"]
        + funnel["closed_strategies"]
        + funnel["blocked_or_inconclusive_strategies"]
        == 4
    )
    assert funnel["exact_next_action"] == "direction_owner_review_fast_source_library_batch_v5"


def test_protected_state_and_output_generation_are_deterministic() -> None:
    consistency = _json("consistency_check.json")
    assert consistency["status"] == "pass"
    assert consistency["protected_state_unchanged"] is True
    assert consistency["input_evidence_unchanged"] is True
    assert consistency["all_forbidden_actions_false"] is True
    protected_before = batch.protected_hashes()
    first = {name: (batch.OUTPUT_DIR / name).read_bytes() for name in REQUIRED_ARTIFACTS}
    batch.run()
    second = {name: (batch.OUTPUT_DIR / name).read_bytes() for name in REQUIRED_ARTIFACTS}
    assert first == second
    assert protected_before == batch.protected_hashes()
