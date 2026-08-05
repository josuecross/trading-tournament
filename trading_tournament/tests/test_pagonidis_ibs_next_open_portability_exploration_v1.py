from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from strategy_lab.research_os.research import (
    pagonidis_ibs_next_open_portability_exploration_v1 as task,
)


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = (
    ROOT
    / "evidence"
    / "research_recovery"
    / task.TASK_ID
    / "latest"
)


@pytest.fixture(scope="module", autouse=True)
def evidence_ready() -> None:
    assert (EVIDENCE / "consistency_check.json").exists(), (
        "Run the dedicated serial runner before focused tests."
    )


def rows(name: str) -> list[dict[str, str]]:
    with (EVIDENCE / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def json_payload(name: str) -> dict:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def yaml_payload(name: str) -> dict:
    return yaml.safe_load((EVIDENCE / name).read_text(encoding="utf-8"))


def test_exact_scope_outputs_and_entities() -> None:
    assert {path.name for path in EVIDENCE.iterdir()} == task.REQUIRED_OUTPUTS
    manifest = yaml_payload("batch_manifest.yaml")
    assert manifest["task_id"] == task.TASK_ID
    assert manifest["stage"] == "exploration"
    assert manifest["strategy_ids"] == [task.STRATEGY_ID]
    assert manifest["source_library_record_count"] == 1
    assert manifest["strategy_configuration_count"] == 1
    assert manifest["canonical_experiment_trial_count"] == 1
    assert manifest["benchmark_reference_count"] == 4
    assert manifest["process_task_count"] == 1
    assert manifest["data_capability_task_count"] == 0
    assert manifest["paper_demo_observation_count"] == 0
    assert manifest["source_replication_claimed"] is False
    assert manifest["validation_claimed"] is False


def test_source_translation_is_explicit_and_v5_is_not_revised() -> None:
    source = rows("source_translation_record.csv")
    assert len(source) == 1
    row = source[0]
    assert row["entity_type"] == "source_library_record"
    assert row["source_status"] == "source_complete_but_execution_translated"
    assert row["translation_label"] == "execution_portability_test"
    assert row["source_ibs_signal_retained"] == "true"
    assert row["source_threshold_retained"] == "true"
    assert row["source_asset_class_intent_retained"] == "true"
    assert row["source_entry_timing_retained"] == "false"
    assert row["project_execution_translation"] == "signal_close_t_to_open_t_plus_1"
    assert row["project_exit"] == "close_t_plus_1"
    assert (
        row["source_return_interval_omitted"]
        == "close_t_to_open_t_plus_1_overnight_component"
    )
    assert row["exact_source_replication_claimed"] == "false"
    assert row["v5_rejection_revised_or_overwritten"] == "false"


def test_canonical_trial_is_frozen_before_performance() -> None:
    strategies = rows("strategy_cards.csv")
    trials = rows("trial_ledger.csv")
    process = rows("process_task_log.csv")
    benchmarks = rows("benchmark_reference_log.csv")
    assert len(strategies) == len(trials) == len(process) == 1
    assert len(benchmarks) == 4
    assert trials[0]["trial_id"] == task.TRIAL_ID
    assert trials[0]["parent_trial_id"] == ""
    assert trials[0]["adaptation_label"] == "exploratory_variant"
    assert trials[0]["changed_fields_from_source"] == (
        "execution_entry_and_return_interval_only"
    )
    assert trials[0]["source_rule_changed"] == "false"
    assert trials[0]["threshold_changed"] == "false"
    assert trials[0]["instrument_changed"] == "false"
    assert trials[0]["execution_changed_from_source"] == "true"
    assert trials[0]["optimization_performed"] == "false"
    assert {
        row["entity_type"] for row in benchmarks
    } == {"benchmark_reference"}
    assert {
        row["stage"] for row in benchmarks
    } == {"benchmark_reference_only"}
    consistency = json_payload("consistency_check.json")
    assert (
        consistency["preregistration_written_before_performance_calculation"]
        is True
    )
    assert consistency["preregistration_checkpoint_hash"].startswith("sha256:")


def test_preflight_uses_canonical_adjusted_ohlcv_without_provider() -> None:
    preflight = rows("data_preflight_reconciliation.csv")
    assert {row["symbol"] for row in preflight} == {"SPY", "BIL"}
    assert {row["candidate_preflight_status"] for row in preflight} == {"pass"}
    assert {row["ordered_unique_dates"] for row in preflight} == {"true"}
    assert {row["finite_positive_adjusted_ohlc"] for row in preflight} == {
        "true"
    }
    assert {row["finite_nonnegative_adjusted_volume"] for row in preflight} == {
        "true"
    }
    assert {row["valid_adjusted_ohlc_relationships"] for row in preflight} == {
        "true"
    }
    assert {row["canonical_adjustment_compatible"] for row in preflight} == {
        "true"
    }
    assert {row["identical_common_dates"] for row in preflight} == {"true"}
    assert {row["provider_accessed"] for row in preflight} == {"false"}
    assert all(row["cache_file_hash"].startswith("sha256:") for row in preflight)
    assert all(row["canonical_frame_hash"].startswith("sha256:") for row in preflight)


def test_ibs_formula_is_strict_and_zero_range_is_inactive() -> None:
    index = pd.date_range("2020-01-01", periods=4, freq="D")
    frame = pd.DataFrame(
        {
            "high": [10.0, 10.0, 10.0, 10.0],
            "low": [0.0, 0.0, 0.0, 10.0],
            "close": [1.9, 2.0, 2.1, 10.0],
        },
        index=index,
    )
    ibs = task.calculate_ibs(frame)
    assert ibs.iloc[0] < task.IBS_THRESHOLD
    assert ibs.iloc[1] == pytest.approx(task.IBS_THRESHOLD)
    assert not bool(ibs.iloc[1] < task.IBS_THRESHOLD)
    assert ibs.iloc[2] > task.IBS_THRESHOLD
    assert np.isnan(ibs.iloc[3])
    diagnostics = rows("ibs_signal_diagnostics.csv")
    assert {row["strict_threshold"] for row in diagnostics} == {"IBS<0.20"}
    for row in diagnostics:
        if row["IBS"]:
            assert (row["active_signal"] == "true") == (
                float(row["IBS"]) < task.IBS_THRESHOLD
            )


def test_signal_is_shifted_to_next_open_and_never_uses_spy_overnight() -> None:
    diagnostics = rows("ibs_signal_diagnostics.csv")
    ledger = rows("session_trade_ledger.csv")
    assert len(diagnostics) == len(ledger) > 1000
    for signal, trade in zip(diagnostics, ledger):
        assert signal["date"] == trade["signal_date"]
        assert signal["next_session_execution_date"] == trade["execution_date"]
        assert pd.Timestamp(trade["signal_date"]) < pd.Timestamp(
            trade["execution_date"]
        )
        assert trade["signal_known_after_completed_close"] == "true"
        assert trade["SPY_overnight_return_used"] == "false"
        assert trade["same_close_fill_used"] == "false"
        assert trade["entry_timestamp"] == "regular_session_open"
        assert trade["exit_timestamp"] == "regular_session_close"


def test_active_events_have_two_separate_turnover_and_cost_events() -> None:
    ledger = rows("session_trade_ledger.csv")
    active = [
        row for row in ledger if float(row["target_SPY_weight_at_open"]) > 0.0
    ]
    inactive = [
        row for row in ledger if float(row["target_SPY_weight_at_open"]) == 0.0
    ]
    assert active and inactive
    for row in active:
        assert float(row["open_one_way_turnover"]) == pytest.approx(1.0)
        assert float(row["close_one_way_turnover"]) == pytest.approx(1.0)
        assert float(row["total_one_way_turnover"]) == pytest.approx(2.0)
        assert float(row["open_transaction_cost_fraction"]) > 0.0
        assert float(row["close_transaction_cost_fraction"]) > 0.0
        assert row["end_of_session_SPY_weight"] == "0"
        assert row["end_of_session_BIL_weight"] == "1"
    for row in inactive:
        assert float(row["open_one_way_turnover"]) == 0.0
        assert float(row["close_one_way_turnover"]) == 0.0
    turnover = rows("turnover_cost_reconciliation.csv")
    assert {
        row["turnover_formula"] for row in turnover
    } == {"0.5*sum(abs(target_weight-pretrade_weight))"}
    assert {
        row["open_and_close_events_netted_together"] for row in turnover
    } == {"false"}


def test_controls_and_exposure_match_are_frozen() -> None:
    benchmarks = rows("benchmark_reference_log.csv")
    assert {row["benchmark_id"] for row in benchmarks} == set(task.CONTROL_IDS)
    exposure = rows("exposure_control_reconciliation.csv")
    assert len(exposure) == 3
    assert {row["cost_assumption_bps"] for row in exposure} == {"0", "5", "10"}
    assert {row["matches_candidate_active_fraction"] for row in exposure} == {
        "true"
    }
    assert {row["optimized_or_rounded"] for row in exposure} == {"false"}
    assert {row["strategy_variant"] for row in exposure} == {"false"}
    for row in exposure:
        assert float(row["mechanical_exposure_fraction"]) == pytest.approx(
            float(row["control_daily_SPY_weight"])
        )
        assert float(row["control_daily_SPY_weight"]) + float(
            row["control_daily_BIL_weight"]
        ) == pytest.approx(1.0)


def test_result_cost_and_half_tables_are_complete() -> None:
    candidate = rows("all_trial_results.csv")
    controls = rows("control_results.csv")
    halves = rows("chronological_half_results.csv")
    assert len(candidate) == 3
    assert len(controls) == 12
    assert len(halves) == 10
    assert {row["cost_assumption_bps"] for row in candidate} == {"0", "5", "10"}
    assert {row["row_id"] for row in controls} == set(task.CONTROL_IDS)
    assert {
        row["period_label"] for row in halves
    } == {"first_chronological_half", "second_chronological_half"}
    assert {
        row["period_role"] for row in halves
    } == {"chronological_half_not_clean_holdout"}
    assert all(row["period_label"] == "full_period" for row in candidate + controls)


def test_invariants_pass_and_explicit_zeros_are_preserved() -> None:
    invariants = rows("invariant_results.csv")
    assert len(invariants) == 15
    assert {row["invariant_pass"] for row in invariants} == {"true"}
    assert {row["numeric_invariant_status"] for row in invariants} == {"pass"}
    assert {row["weight_invariant_status"] for row in invariants} == {"pass"}
    assert {row["exposure_invariant_status"] for row in invariants} == {"pass"}
    assert all(
        float(row["maximum_gross_exposure"]) <= 1.0 + 1e-10
        for row in invariants
    )
    assert all(
        float(row["maximum_daily_weight_sum"]) <= 1.0 + 1e-10
        for row in invariants
    )
    candidate = [row for row in invariants if row["row_id"] == task.STRATEGY_ID]
    assert {row["no_SPY_overnight_return_attributed"] for row in candidate} == {
        "true"
    }
    assert {row["every_intraday_entry_has_close_exit"] for row in candidate} == {
        "true"
    }
    assert {row["explicit_zero_weights_preserved"] for row in candidate} == {
        "true"
    }
    assert {row["stale_weight_forward_fill_used"] for row in candidate} == {
        "false"
    }


def test_outcome_next_action_and_funnel_reconcile() -> None:
    summary = rows("outcome_summary.csv")
    assert len(summary) == 1
    outcome = summary[0]["outcome"]
    assert outcome in task.ALLOWED_OUTCOMES
    expected = task.exact_next_action(outcome)
    assert summary[0]["exact_next_action"] == expected
    assert summary[0]["exact_source_replication_claimed"] == "false"
    assert summary[0]["execution_portability_test"] == "true"
    assert summary[0]["validation_claimed"] == "false"
    next_actions = rows("next_actions.csv")
    assert {row["exact_next_action"] for row in next_actions} == {expected}
    assert {row["execute_in_this_task"] for row in next_actions} == {"false"}
    funnel = json_payload("cohort_funnel_counts.json")
    assert funnel["source_library_records"] == 1
    assert funnel["strategy_configurations"] == 1
    assert funnel["experiment_trials"] == 1
    assert funnel["benchmark_references"] == 4
    assert funnel["process_tasks"] == 1
    assert funnel["data_capability_tasks"] == 0
    assert funnel["paper_demo_observations"] == 0
    assert sum(funnel["outcomes"].values()) == 1


def test_state_hashes_and_determinism_reconcile() -> None:
    consistency = json_payload("consistency_check.json")
    assert consistency["status"] == "pass"
    assert consistency["consistency_passed"] is True
    assert consistency["V5_evidence_unchanged"] is True
    assert consistency["protected_state_unchanged"] is True
    assert consistency["market_data_caches_unchanged"] is True
    assert consistency["prior_evidence_unchanged"] is True
    assert consistency["source_reported_performance_used"] is False
    assert consistency["post_result_parameter_or_threshold_change"] is False
    assert consistency["deterministic_frozen_core_hash"] == (
        task.deterministic_core_hash()
    )
    assert not any(consistency["forbidden_actions"].values())
