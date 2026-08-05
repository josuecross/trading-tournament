from __future__ import annotations

import csv
import json
from pathlib import Path

import pandas as pd
import pytest
import yaml

from strategy_lab.research_os.research import (
    intermarket_ivts_herorats_portability_exploration_v1 as task,
)


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "research_recovery" / task.TASK_ID / "latest"


@pytest.fixture(scope="module", autouse=True)
def evidence_ready() -> None:
    assert (EVIDENCE / "consistency_check.json").exists(), (
        "Run the dedicated IVTS serial runner before focused tests."
    )


def rows(name: str) -> list[dict[str, str]]:
    with (EVIDENCE / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def payload(name: str) -> dict:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def manifest() -> dict:
    return yaml.safe_load((EVIDENCE / "batch_manifest.yaml").read_text(encoding="utf-8"))


def test_required_artifacts_and_exact_scope() -> None:
    assert set(task.REQUIRED_ARTIFACTS).issubset(
        {path.name for path in EVIDENCE.iterdir()}
    )
    data = manifest()
    assert data["task_id"] == task.TASK_ID
    assert data["mode"] == "fast-progress"
    assert data["stage"] == "exploration"
    assert data["strategy_ids"] == [task.STRATEGY_ID]
    assert data["trial_ids"] == [task.TRIAL_ID]
    assert data["benchmark_ids"] == list(task.BENCHMARKS)
    assert data["official_series"] == ["VIXCLS", "VXVCLS"]


def test_entity_separation_and_complete_lineage() -> None:
    sources = rows("source_library_records.csv")
    strategies = rows("strategy_cards.csv")
    trials = rows("trial_ledger.csv")
    benchmarks = rows("benchmark_reference_log.csv")
    data_tasks = rows("data_capability_task_log.csv")
    processes = rows("process_task_log.csv")
    assert len(sources) == len(strategies) == len(trials) == len(processes) == 1
    assert len(benchmarks) == 6
    assert len(data_tasks) == 2
    assert sources[0]["entity_type"] == "source_library_record"
    assert strategies[0]["entity_type"] == "strategy_configuration"
    assert trials[0]["entity_type"] == "experiment_trial"
    assert {row["entity_type"] for row in benchmarks} == {"benchmark_reference"}
    assert {row["entity_type"] for row in data_tasks} == {"data_capability_task"}
    assert processes[0]["entity_type"] == "process_task"
    assert trials[0]["parent_trial_id"] == ""
    assert trials[0]["adaptation_label"] == "exploratory_variant"
    assert trials[0]["performance_executed"] == "false"


def test_frozen_signal_contract() -> None:
    assert task.median5([1.0, 2.0, 3.0, 4.0, 5.0]) == 3.0
    assert task.median5([1.0, 2.0, 3.0, 4.0]) is None
    assert task.target_for_filtered_ratio(0.959999) == (1.0, 0.0, "risk_on")
    assert task.target_for_filtered_ratio(0.96) == (0.5, 0.5, "middle")
    assert task.target_for_filtered_ratio(1.02) == (0.5, 0.5, "middle")
    assert task.target_for_filtered_ratio(1.020001) == (0.0, 1.0, "defensive")
    strategy = rows("strategy_cards.csv")[0]
    parameters = json.loads(strategy["parameters"])
    assert parameters["ratio"] == "VIXCLS/VXVCLS"
    assert parameters["median_length"] == 5
    assert parameters["thresholds"] == [0.96, 1.02]
    assert parameters["targets"] == [
        "SPY_1_IEF_0",
        "SPY_0.5_IEF_0.5",
        "SPY_0_IEF_1",
    ]


def test_official_first_release_panels_are_date_level_only() -> None:
    series = rows("official_series_manifest.csv")
    assert {row["series_id"] for row in series} == {"VIXCLS", "VXVCLS"}
    assert {row["provider"] for row in series} == {"FRED_ALFRED"}
    assert {row["release_date_available"] for row in series} == {"true"}
    assert {
        row["historical_intraday_release_timestamp_available"] for row in series
    } == {"false"}
    assert all(int(row["valid_value_count"]) > 2500 for row in series)
    assert all(row["first_release_panel_hash"].startswith("sha256:") for row in series)
    timing = rows("publication_timing_reconciliation.csv")
    assert timing
    assert {row["publication_safe_execution_proven"] for row in timing} == {"false"}
    assert {row["authorized_execution_session"] for row in timing} == {""}
    assert any(
        row["observation_date"] == row["VIXCLS_first_release_date"]
        or row["observation_date"] == row["VXVCLS_first_release_date"]
        for row in timing
        if row["both_values_present"] == "true"
    )


def test_timing_gate_blocks_performance_without_invented_delay() -> None:
    assert rows("all_trial_results.csv") == []
    assert rows("control_results.csv") == []
    assert rows("chronological_half_results.csv") == []
    assert rows("portfolio_contribution_results.csv") == []
    diagnostics = rows("state_signal_diagnostics.csv")
    assert diagnostics
    assert {row["execution_authorized"] for row in diagnostics} == {"false"}
    assert {row["authorized_execution_session"] for row in diagnostics} == {""}
    assert all(row["turnover"] == "" and row["cost"] == "" for row in diagnostics)
    turnover = rows("turnover_cost_reconciliation.csv")
    assert turnover[0]["status"] == "not_run_publication_timing_block"


def test_methodology_boundary_is_diagnostic_only() -> None:
    methodology = rows("methodology_change_log.csv")
    assert len(methodology) == 1
    assert methodology[0]["effective_date"] == "2025-02-10"
    assert methodology[0]["diagnostic_only"] == "true"
    assert methodology[0]["thresholds_changed"] == "false"
    assert methodology[0]["strategy_variant_created"] == "false"
    diagnostics = rows("state_signal_diagnostics.csv")
    assert {row["methodology_period"] for row in diagnostics} == {
        "pre_2025_02_10",
        "post_2025_02_10",
    }


def test_outcome_failure_and_next_action_are_exact() -> None:
    outcome = rows("outcome_summary.csv")
    failures = rows("failure_reasons.csv")
    actions = rows("next_actions.csv")
    assert len(outcome) == len(failures) == len(actions) == 1
    assert outcome[0]["outcome"] == "inconclusive_data_issue"
    assert outcome[0]["failure_reason"] == "data_or_comparability_failure"
    assert outcome[0]["performance_executed"] == "false"
    assert failures[0]["primary_failure_reason"] == "data_or_comparability_failure"
    assert actions[0]["exact_next_action"] == (
        "direction_owner_review_ivts_publication_timing_block_v1"
    )
    assert rows("exploratory_followup_candidates.csv") == []


def test_funnel_and_consistency_reconcile() -> None:
    funnel = payload("cohort_funnel_counts.json")
    assert funnel == {
        "benchmark_references": 6,
        "data_capability_tasks": 2,
        "experiment_trials": 1,
        "exploratory_followup_candidates": 0,
        "inconclusive_data_issue": 1,
        "paper_demo_observations": 0,
        "performance_trials_executed": 0,
        "process_tasks": 1,
        "source_library_records": 1,
        "strategy_configurations": 1,
    }
    check = payload("consistency_check.json")
    assert check["overall_pass"] is True
    assert check["candidate_execution_authorized"] is False
    assert check["first_release_values_acquired"] is True
    assert check["historical_intraday_release_timestamps_acquired"] is False
    assert check["timing_gate_stopped_performance"] is True
    assert check["protected_state_unchanged"] is True
    assert check["canonical_cache_unchanged"] is True
    assert check["source_attachment_unchanged"] is True
    assert not any(check["forbidden_actions"].values())


def test_publication_panel_and_signal_diagnostics_are_deterministic() -> None:
    vix = pd.DataFrame(
        {
            "observation_date": pd.to_datetime(
                ["2014-04-17", "2014-04-18", "2014-04-21", "2014-04-22", "2014-04-23"]
            ),
            "value": [14.0, 15.0, 16.0, 17.0, 18.0],
            "release_date": pd.to_datetime(
                ["2014-04-17", "2014-04-21", "2014-04-21", "2014-04-22", "2014-04-23"]
            ),
        }
    )
    vxv = pd.DataFrame(
        {
            "observation_date": vix["observation_date"],
            "value": [15.0, 15.0, 15.0, 15.0, 15.0],
            "release_date": vix["release_date"],
        }
    )
    panel_one = task.build_publication_timing_panel(vix, vxv)
    panel_two = task.build_publication_timing_panel(vix, vxv)
    assert task.canonical_hash(panel_one.to_dict("records")) == task.canonical_hash(
        panel_two.to_dict("records")
    )
    first = task.build_signal_diagnostics(panel_one)
    second = task.build_signal_diagnostics(panel_two)
    assert task.canonical_hash(first) == task.canonical_hash(second)
    assert first[-1]["five_day_median"] == pytest.approx(16.0 / 15.0)
    assert all(row["execution_authorized"] is False for row in first)


def test_no_validation_replication_lifecycle_or_execution_claim() -> None:
    data = manifest()
    assert data["exact_source_replication_claimed"] is False
    assert data["validation_claimed"] is False
    assert data["paper_demo_eligibility_claimed"] is False
    assert data["lifecycle_state_changed"] is False
    assert data["optimization_performed"] is False
    assert data["post_result_adaptation_performed"] is False
    trial = rows("trial_ledger.csv")[0]
    assert trial["ratio_changed"] == "false"
    assert trial["median_length_changed"] == "false"
    assert trial["thresholds_changed"] == "false"
    assert trial["state_weights_changed"] == "false"
    assert trial["optimization_performed"] == "false"
