from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from strategy_lab.research_os.research import technical_strategy_factory_v1 as factory


def read_rows(name: str) -> list[dict[str, str]]:
    with (factory.OUTPUT_DIR / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_factory_grid_has_exactly_six_architectures_and_twenty_four_trials() -> None:
    assert len(factory.PARAMETER_GRIDS) == 6
    assert len(factory.VARIANTS) == 24
    assert all(len(grid) == 4 for grid in factory.PARAMETER_GRIDS.values())
    assert len({spec.strategy_id for spec in factory.VARIANTS}) == 24
    assert len({spec.trial_id for spec in factory.VARIANTS}) == 24


def test_frozen_universes_use_only_authorized_symbols() -> None:
    authorized = {"SPY", "BIL", *factory.SECTORS}
    assert set(factory.REQUIRED_SYMBOLS) == authorized
    assert all(set(spec.universe) <= authorized for spec in factory.VARIANTS)


def test_inclusive_linear_percentile_rank_matches_reference_cases() -> None:
    assert factory.percentile_rank_inclusive_linear(np.array([1.0, 2.0, 3.0]), 1.0) == 0.0
    assert factory.percentile_rank_inclusive_linear(np.array([1.0, 2.0, 3.0]), 2.0) == 0.5
    assert factory.percentile_rank_inclusive_linear(np.array([1.0, 2.0, 3.0]), 3.0) == 1.0
    assert factory.percentile_rank_inclusive_linear(np.array([1.0, 1.0, 2.0]), 1.0) == 0.25


def test_regression_state_recovers_exponential_trend_and_unit_r_squared() -> None:
    slope = 0.001
    prices = np.exp(2.0 + slope * np.arange(60, dtype=float))
    annualized, r_squared = factory.regression_state(prices)
    assert np.isclose(annualized, np.exp(slope * 252.0) - 1.0, atol=1e-12)
    assert np.isclose(r_squared, 1.0, atol=1e-12)


def test_next_session_is_strictly_after_signal_date() -> None:
    index = pd.bdate_range("2024-01-02", periods=4)
    assert factory.next_session(index, index[1]) == index[2]
    assert factory.next_session(index, index[-1]) is None


def test_signed_target_turnover_cost_and_signal_session_ownership() -> None:
    index = pd.bdate_range("2024-01-02", periods=3)
    prices = pd.DataFrame(
        {"SPY": [100.0, 110.0, 121.0], "BIL": [100.0, 100.0, 100.0]}, index=index
    )
    events = factory.event_frame(
        index,
        factory.SPY_UNIVERSE,
        {
            index[0]: {"SPY": 0.0, "BIL": 1.0},
            index[2]: {"SPY": 1.0, "BIL": 0.0},
        },
    )
    path = factory.accounting.simulate_path(prices, events, 5.0, "probe")
    assert np.isclose(path["returns"].iloc[1], 0.0)
    assert np.isclose(path["turnover"].iloc[2], 1.0)
    assert np.isclose(path["cost"].iloc[2], 5.0 / 10000.0)
    assert np.isclose(path["returns"].iloc[2], -5.0 / 10000.0)


def test_development_truncation_structurally_excludes_final_prices() -> None:
    index = pd.bdate_range("2024-01-02", periods=6)
    prices = pd.DataFrame({"SPY": np.arange(100.0, 106.0), "BIL": 100.0}, index=index)
    events = factory.event_frame(
        index,
        factory.SPY_UNIVERSE,
        {index[0]: {"SPY": 0.0, "BIL": 1.0}, index[4]: {"SPY": 1.0, "BIL": 0.0}},
    )
    prepared = {
        "prices": prices,
        "candidate_events": events,
        "control_events": {"control": events},
        "candidate_targets": events.reindex(index).ffill().fillna(0.0),
        "execution_calendar": index,
    }
    truncated = factory.truncate_prepared(prepared, index[3])
    assert truncated["prices"].index[-1] == index[3]
    assert index[4] not in truncated["candidate_events"].index
    assert truncated["selection_view_only"] is True


def test_frozen_artifacts_have_matching_before_and_after_hashes() -> None:
    consistency = json.loads((factory.OUTPUT_DIR / "consistency_check.json").read_text(encoding="utf-8"))
    assert consistency["preperformance_hashes_before"] == consistency["preperformance_hashes_after"]
    assert consistency["selected_variant_freeze_hash_before"] == consistency["selected_variant_freeze_hash_after"]


def test_entity_and_control_counts_reconcile() -> None:
    assert len(read_rows("strategy_cards.csv")) == 24
    assert len(read_rows("trial_ledger.csv")) == 24
    assert len(read_rows("benchmark_reference_log.csv")) == 128
    assert len(read_rows("walk_forward_pass_matrix.csv")) == 96
    cards = read_rows("strategy_cards.csv")
    trials = read_rows("trial_ledger.csv")
    assert {row["entity_type"] for row in cards} == {"strategy_configuration"}
    assert {row["entity_type"] for row in trials} == {"experiment_trial"}


def test_walk_forward_folds_and_final_segment_are_disjoint() -> None:
    rows = read_rows("walk_forward_folds.csv")
    for architecture in factory.PARAMETER_GRIDS:
        selected = [row for row in rows if row["architecture_id"] == architecture]
        folds = [row for row in selected if row["period_role"] == "walk_forward_selection"]
        final = next(row for row in selected if row["final_segment"] == "true")
        assert len(folds) == 4
        assert all(pd.Timestamp(row["evaluation_end"]) < pd.Timestamp(final["evaluation_start"]) for row in folds)
        assert all(row["used_for_variant_selection"] == "true" for row in folds)
        assert final["used_for_variant_selection"] == "false"


def test_only_frozen_selected_variants_have_final_results() -> None:
    frozen = read_rows("selected_variant_freeze.csv")
    selected = {row["selected_strategy_id"] for row in frozen if row["selected_strategy_id"]}
    final = read_rows("final_evaluation_results.csv")
    assert {row["strategy_id"] for row in final} == selected
    assert len(selected) <= 6
    decisions = read_rows("variant_selection_decisions.csv")
    for architecture in factory.PARAMETER_GRIDS:
        assert sum(
            row["selected_for_final_evaluation"] == "true"
            for row in decisions
            if row["architecture_id"] == architecture
        ) <= 1


def test_selection_rule_is_exact_and_final_segment_is_prohibited() -> None:
    payload = yaml.safe_load((factory.OUTPUT_DIR / "selection_rule.yaml").read_text(encoding="utf-8"))
    assert payload["primary_cost_bps"] == 5
    assert payload["selection_eligibility"] == "at_least_3_of_4_folds"
    assert payload["maximum_selected_per_architecture"] == 1
    assert payload["final_segment_used_for_selection"] is False


def test_multiple_testing_ledger_preserves_all_trials() -> None:
    rows = read_rows("multiple_testing_ledger.csv")
    trials = [row for row in rows if row["record_type"] == "canonical_trial"]
    summary = next(row for row in rows if row["record_type"] == "factory_summary")
    assert len(trials) == 24
    assert summary["total_trials"] == "24"
    assert summary["walk_forward_fold_evaluations"] == "96"
    assert summary["promotion_adjusted_statistic_calculated"] == "false"


def test_required_output_set_and_consistency_pass() -> None:
    actual = {path.name for path in factory.OUTPUT_DIR.iterdir() if path.is_file()}
    assert actual == factory.REQUIRED_FILES
    consistency = json.loads((factory.OUTPUT_DIR / "consistency_check.json").read_text(encoding="utf-8"))
    assert consistency["overall_pass"] is True
    assert all(consistency["checks"].values())


def test_no_network_or_provider_module_is_imported() -> None:
    source = Path(factory.__file__).read_text(encoding="utf-8")
    prohibited = ("import requests", "from requests", "urllib.request", "alpaca", "yfinance")
    assert not any(token in source.lower() for token in prohibited)
