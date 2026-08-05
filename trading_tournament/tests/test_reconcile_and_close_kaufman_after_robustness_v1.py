from __future__ import annotations

import csv
import json

import pytest
import yaml

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.research import (
    reconcile_and_close_kaufman_after_robustness_v1 as task,
)


OUTPUT = ROOT / "evidence" / "lifecycle" / task.TASK_ID / "latest"
REGISTRY = ROOT / "strategy_lab" / "strategy_registry.yaml"


@pytest.fixture(scope="module", autouse=True)
def evidence_ready() -> None:
    assert (OUTPUT / "consistency_check.json").exists()


def rows(name: str) -> list[dict[str, str]]:
    with (OUTPUT / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def check() -> dict:
    return json.loads((OUTPUT / "consistency_check.json").read_text())


def registry_record() -> dict:
    registry = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    matches = [
        row
        for row in registry["strategies"]
        if (row.get("strategy_id") or row.get("id")) == task.STRATEGY_ID
    ]
    assert len(matches) == 1
    return matches[0]


def test_exact_outputs_and_entity_counts() -> None:
    assert {path.name for path in OUTPUT.iterdir()} == task.REQUIRED_OUTPUTS
    manifest = yaml.safe_load((OUTPUT / "reconciliation_manifest.yaml").read_text())
    assert manifest["process_outcome"] == task.PROCESS_OUTCOME_SUCCESS
    assert (
        manifest["authoritative_strategy_records_created"]
        + manifest["authoritative_strategy_records_updated"]
        == 1
    )
    assert manifest["exact_configuration_records_after_success"] == 1
    assert manifest["existing_experiment_trials_carried_forward"] == 4
    assert manifest["new_experiment_trials"] == 0
    assert manifest["benchmark_references_carried_forward"] == 6
    assert manifest["process_tasks_created"] == 1
    assert manifest["paper_demo_observations_changed"] == 0
    assert manifest["new_strategy_candidates_created"] == 0


def test_duplicate_screen_and_fingerprint_are_deterministic() -> None:
    duplicate = rows("duplicate_and_alias_check.csv")
    assert len(duplicate) == 1
    assert duplicate[0]["match_type"] in {
        "no_exact_record_no_equivalent_alias",
        "exact_strategy_id",
    }
    assert duplicate[0]["authoritative_change_allowed"] == "true"
    fingerprint = rows("configuration_fingerprint.csv")
    assert fingerprint
    assert len({row["fingerprint"] for row in fingerprint}) == 1
    assert {row["deterministic"] for row in fingerprint} == {"true"}
    assert fingerprint[0]["fingerprint"] == task.configuration_fingerprint()


def test_registry_has_one_exact_closed_record() -> None:
    record = registry_record()
    assert record["stage"] == "closed"
    assert record["outcome"] == "robustness_failed"
    assert record["failure_reason"] == "concentration_risk"
    assert record["primary_failure_reason"] == "concentration_risk"
    assert record["decision_reason"] == (
        "single_trade_concentration_exceeded_frozen_50pct_limit"
    )
    assert record["strongest_contributing_trade"] == (
        "2020-03-31_to_2020-09-09"
    )
    assert record["largest_trade_fraction_of_additive_excess"] == pytest.approx(
        1.1337989832791708
    )
    assert record["additive_excess_after_removing_strongest_trade"] == pytest.approx(
        -0.006514
    )
    assert record["next_action"] == task.STRATEGY_NEXT_ACTION
    assert task.required_record_complete(record) is True


def test_both_route_failures_remain_visible() -> None:
    record = registry_record()
    assert record["secondary_failure_evidence"] == "standalone_period_instability"
    assert record["standalone_outcome"] == "closed_exploration"
    assert record["standalone_failure_reason"] == "period_instability"
    assert record["diversifier_route"] == "20pct_diversifier_only"
    assert record["diversifier_outcome"] == "robustness_failed"
    assert record["diversifier_failure_reason"] == "concentration_risk"


def test_configuration_and_scope_are_frozen_and_narrow() -> None:
    record = registry_record()
    parameters = record["parameters"]
    assert parameters["channel_contract"] == "TradingView_Rule_2_only"
    assert parameters["rule"] == 2
    assert parameters["period_sessions"] == 40
    assert parameters["active_asset"] == "SPY"
    assert parameters["inactive_asset"] == "BIL"
    assert parameters["execution_timestamp"] == "next_regular_session_open"
    assert parameters["outer_candidate_weight"] == pytest.approx(0.2)
    assert parameters["outer_reference_weight"] == pytest.approx(0.8)
    assert record["family_level_interpretation"] == task.FAMILY_INTERPRETATION
    assert "configuration_only" not in record["family_level_interpretation"]
    assert "families remain" in record["notes"].lower()


def test_no_validation_paper_demo_or_real_money_authorization() -> None:
    record = registry_record()
    for field in (
        "independent_validation_claimed",
        "validation_supported",
        "paper_demo_eligible",
        "paper_demo_active",
        "paper_forward_active",
        "paper_forward_allowed_by_risk_framework",
        "further_same_period_diagnostic_authorized",
        "real_money_authorized",
        "real_money_recommendation",
    ):
        assert record[field] is False


def test_four_existing_trials_are_read_only_and_no_new_trial_exists() -> None:
    trials = rows("trial_ledger.csv")
    assert len(trials) == 4
    assert [row["trial_id"] for row in trials] == [
        task.STANDALONE_TRIAL_ID,
        task.FOLLOWUP_TRIAL_ID,
        task.ROBUSTNESS_TRIAL_ID,
        task.RESOLUTION_TRIAL_ID,
    ]
    assert [row["outcome"] for row in trials] == [
        "closed_exploration",
        "exploratory_followup_candidate_diversifier",
        "robustness_mixed",
        "robustness_failed",
    ]
    assert {row["read_only"] for row in trials} == {"true"}
    assert {row["new_experiment_trial_created"] for row in trials} == {"false"}
    assert {row["counted_as_new_trial"] for row in trials} == {"false"}


def test_benchmarks_and_process_task_remain_separate() -> None:
    benchmarks = rows("benchmark_reference_log.csv")
    process = rows("process_task_log.csv")
    assert len(benchmarks) == 6
    assert {row["entity_type"] for row in benchmarks} == {
        "benchmark_reference"
    }
    assert {row["stage"] for row in benchmarks} == {
        "benchmark_reference_only"
    }
    assert len(process) == 1
    assert process[0]["entity_type"] == "process_task"
    assert process[0]["stage"] == "correction"
    assert process[0]["strategy_counted"] == "false"
    assert process[0]["experiment_trial_counted"] == "false"


def test_registry_state_change_is_atomic_and_only_permitted_path_changed() -> None:
    state = rows("state_change_manifest.csv")
    changed = {row["path"] for row in state if row["changed"] == "true"}
    assert changed == {"strategy_lab/strategy_registry.yaml"}
    assert {row["change_permitted"] for row in state if row["changed"] == "true"} == {
        "true"
    }
    assert not any(
        row["path"] != "strategy_lab/strategy_registry.yaml"
        and row["changed"] == "true"
        for row in state
    )


def test_consistency_and_registry_validation_pass() -> None:
    payload = check()
    assert payload["status"] == "pass"
    assert payload["consistency_passed"] is True
    assert payload["evidence_gate_passed"] is True
    assert payload["registry_validation_passed"] is True
    assert payload["registry_validation_errors"] == []
    assert payload["exact_configuration_records_after_reconciliation"] == 1
    assert payload["unresolved_equivalent_alias_count_after_reconciliation"] == 0
    assert payload["authoritative_record_complete"] is True
    assert payload["closure_scope_is_exact_configuration_only"] is True
    assert payload["new_experiment_trials"] == 0
    assert payload["paper_demo_observations_changed"] == 0
    assert payload["new_strategy_candidates_created"] == 0
    assert payload["input_evidence_hashes_unchanged"] is True
    assert payload["prior_evidence_unchanged"] is True
    assert payload["market_data_caches_unchanged"] is True
    assert payload["all_source_of_truth_changes_permitted"] is True
    assert payload["exact_next_action"] == task.STRATEGY_NEXT_ACTION
    assert payload["next_action_executed"] is False
    for flag in task.FORBIDDEN_FLAGS:
        assert payload[flag] is False


def test_target_record_is_idempotent_in_memory() -> None:
    record = registry_record()
    assert record == task.target_registry_record()
    registry = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    exact, aliases = task.inspect_registry(registry)
    assert len(exact) == 1
    assert aliases == []
