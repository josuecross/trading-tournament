from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest
import yaml

from strategy_lab.research_os.research import (
    correct_ivts_timing_gate_and_run_official_daily_close_exploration_v3 as task,
)


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "correction" / task.TASK_ID / "latest"


@pytest.fixture(scope="module", autouse=True)
def evidence_ready() -> None:
    assert (EVIDENCE / "consistency_check.json").exists(), (
        "Run the dedicated V3 correction runner before focused tests."
    )


def rows(name: str) -> list[dict[str, str]]:
    with (EVIDENCE / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def json_payload(name: str) -> dict:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def yaml_payload(name: str) -> dict:
    return yaml.safe_load((EVIDENCE / name).read_text(encoding="utf-8"))


def test_required_outputs_and_correction_metadata() -> None:
    assert set(task.REQUIRED_ARTIFACTS).issubset(
        {path.name for path in EVIDENCE.iterdir()}
    )
    manifest = yaml_payload("correction_manifest.yaml")
    assert manifest["task_id"] == task.TASK_ID
    assert manifest["mode"] == "correction"
    assert manifest["stage"] == "exploration"
    assert manifest["strategy_id"] == task.STRATEGY_ID
    assert manifest["timing_policy"] == (
        "official_daily_close_following_session_execution_v1"
    )
    assert manifest["official_history_gate_passed"] is True
    assert manifest["lineage_gate_passed"] is False
    assert manifest["child_trial_created"] is False
    assert manifest["performance_executed"] is False


def test_official_histories_are_retrieved_twice_and_reproduce() -> None:
    reproducibility = rows("official_history_reproducibility.csv")
    assert len(reproducibility) == 4
    assert {row["series"] for row in reproducibility} == {"VIX", "VIX3M"}
    for series in ("VIX", "VIX3M"):
        pair = [row for row in reproducibility if row["series"] == series]
        assert {row["attempt"] for row in pair} == {"1", "2"}
        assert pair[0]["normalized_frame_hash"] == pair[1][
            "normalized_frame_hash"
        ]
        assert {row["normalized_snapshots_match"] for row in pair} == {"true"}
        assert {row["status"] for row in pair} == {
            "official_history_reproduced"
        }
        assert all(row["raw_bytes_hash"].startswith("sha256:") for row in pair)
        assert all(row["retrieval_timestamp_utc"] for row in pair)
        assert all(int(row["duplicate_date_count"]) == 0 for row in pair)
    assert len(list((EVIDENCE / "raw").glob("*.csv"))) == 4


def test_history_manifest_has_required_non_vintage_labels() -> None:
    manifest = rows("official_cboe_history_manifest.csv")
    assert len(manifest) == 2
    assert {row["series"] for row in manifest} == {"VIX", "VIX3M"}
    assert {row["data_provenance"] for row in manifest} == {
        "official_cboe_daily_history"
    }
    assert {row["vintage_status"] for row in manifest} == {
        "current_history_non_vintage"
    }
    assert {row["same_day_return_allowed"] for row in manifest} == {"false"}
    assert {row["normalized_snapshots_match"] for row in manifest} == {"true"}
    assert all(int(row["row_count"]) > 4000 for row in manifest)


def test_timing_correction_is_explicit_and_conservative() -> None:
    timing = rows("timing_methodology_correction.csv")
    assert len(timing) == 1
    correction = timing[0]
    assert correction["intraday_generation_timestamp_required"] == "false"
    assert correction["official_daily_close_required"] == "true"
    assert correction["observation_date_return_allowed"] == "false"
    assert correction["observation_date_close_execution_allowed"] == "false"
    assert correction["following_open_execution_allowed"] == "false"
    assert correction["following_regular_session_close_required"] == "true"
    assert correction["missing_execution_price_behavior"] == (
        "block_signal_no_forward_fill"
    )
    assert correction["strategy_rule_changed"] == "false"
    assert correction["execution_rule_changed"] == "false"


def test_vintage_policy_does_not_overclaim() -> None:
    policy = rows("data_vintage_and_revision_policy.csv")
    assert len(policy) == 1
    row = policy[0]
    assert row["exploratory_use_authorized"] == "true"
    assert row["validation_vintage_safety_established"] == "false"
    assert row["paper_demo_eligibility_supported"] == "false"
    assert row["revision_sensitivity_deferred"] == "true"
    assert row["vintage_status"] == "current_history_non_vintage"


def test_strategy_contract_and_controls_remain_frozen() -> None:
    strategy = rows("strategy_cards.csv")
    assert len(strategy) == 1
    parameters = json.loads(strategy[0]["parameters"])
    assert parameters["ratio"] == "VIX_close/VIX3M_close"
    assert parameters["median_length"] == 5
    assert parameters["thresholds"] == [0.96, 1.02]
    assert parameters["targets"] == ["1.0|0.0", "0.5|0.5", "0.0|1.0"]
    assert parameters["execution"] == "following_regular_session_close"
    benchmarks = rows("benchmark_reference_log.csv")
    assert len(benchmarks) == 6
    assert {row["benchmark_id"] for row in benchmarks} == set(task.BENCHMARKS)
    assert {row["entity_type"] for row in benchmarks} == {"benchmark_reference"}
    assert {row["performance_executed"] for row in benchmarks} == {"false"}


def test_missing_v2_parent_is_detected_not_guessed() -> None:
    manifest = yaml_payload("correction_manifest.yaml")
    assert manifest["V2_trial_ledger_row_count"] == 0
    assert manifest["V2_parent_trial_id_from_ledger"] == ""
    assert manifest["V2_manifest_child_trial_created"] is False
    assert manifest["V2_manifest_conditional_child_trial_id"] == (
        task.v2.CONDITIONAL_CHILD_TRIAL_ID
    )
    failure = rows("failure_reasons.csv")
    assert failure[0]["V2_trial_ledger_row_count"] == "0"
    assert failure[0]["conditional_id_was_never_created"] == "true"
    assert failure[0]["fabricated_parent_used"] == "false"


def test_only_existing_v1_trial_is_carried_and_no_child_is_created() -> None:
    trials = rows("trial_ledger.csv")
    assert len(trials) == 1
    assert trials[0]["trial_id"] == task.v1.TRIAL_ID
    assert trials[0]["record_role"] == "prior_blocked_trial_reference"
    assert trials[0]["created_in_v3"] == "false"
    assert trials[0]["outcome"] == "inconclusive_data_issue"
    funnel = json_payload("cohort_funnel_counts.json")
    assert funnel["prior_blocked_experiment_trials_requested"] == 2
    assert funnel["prior_blocked_experiment_trials_located"] == 1
    assert funnel["missing_prior_V2_trial_records"] == 1
    assert funnel["new_child_experiment_trials"] == 0


def test_no_performance_signal_holdings_turnover_or_cost_was_calculated() -> None:
    assert rows("all_trial_results.csv") == []
    assert rows("control_results.csv") == []
    assert rows("chronological_half_results.csv") == []
    assert rows("portfolio_contribution_results.csv") == []
    assert rows("state_signal_diagnostics.csv") == []
    turnover = rows("turnover_cost_reconciliation.csv")
    assert len(turnover) == 1
    assert turnover[0]["actual_holdings_model_executed"] == "false"
    assert turnover[0]["one_way_turnover"] == ""
    assert turnover[0]["transaction_cost"] == ""


def test_methodology_boundary_stays_diagnostic_only() -> None:
    rows_ = rows("methodology_boundary_log.csv")
    assert len(rows_) == 1
    assert rows_[0]["effective_date"] == "2025-02-10"
    assert rows_[0]["diagnostic_only"] == "true"
    assert rows_[0]["thresholds_changed"] == "false"
    assert rows_[0]["strategy_variant_created"] == "false"
    assert rows_[0]["observations_excluded"] == "false"


def test_outcome_next_action_and_protection_are_exact() -> None:
    outcome = rows("outcome_summary.csv")
    assert len(outcome) == 1
    assert outcome[0]["outcome"] == "blocked_feasibility"
    assert outcome[0]["failure_reason"] == "methodology_failure"
    assert outcome[0]["official_history_gate_passed"] == "true"
    assert outcome[0]["lineage_gate_passed"] == "false"
    assert outcome[0]["child_trial_created"] == "false"
    actions = rows("next_actions.csv")
    assert actions[0]["exact_next_action"] == (
        "defer_ivts_lane_and_select_next_targeted_family_sprint_v1"
    )
    check = json_payload("consistency_check.json")
    assert check["overall_pass"] is True
    assert check["protected_state_unchanged"] is True
    assert check["cache_unchanged"] is True
    assert check["V1_evidence_unchanged"] is True
    assert check["V2_evidence_unchanged"] is True
    assert not any(check["forbidden_actions"].values())


def test_normalization_is_deterministic() -> None:
    raw = (
        b"DATE,OPEN,HIGH,LOW,CLOSE\n"
        b"01/03/2024,14,16,13,15\n"
        b"01/02/2024,13,15,12,14\n"
    )
    first = task.normalize_official_history(raw, "VIX")
    second = task.normalize_official_history(raw, "VIX")
    assert task.normalized_frame_hash(first) == task.normalized_frame_hash(second)
    assert [date.date().isoformat() for date in first["DATE"]] == [
        "2024-01-02",
        "2024-01-03",
    ]
