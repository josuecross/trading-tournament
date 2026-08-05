from __future__ import annotations

import csv
import json
from pathlib import Path

import yaml

from strategy_lab.research_os.research import (
    reconcile_and_close_ibs_after_validation_v1 as reconciliation,
)


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = (
    ROOT
    / "evidence"
    / "lifecycle"
    / reconciliation.TASK_ID
    / "latest"
)
REGISTRY = ROOT / "strategy_lab" / "strategy_registry.yaml"


def rows(name: str) -> list[dict[str, str]]:
    with (EVIDENCE / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def json_payload(name: str) -> dict:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def yaml_payload(name: str) -> dict:
    return yaml.safe_load((EVIDENCE / name).read_text(encoding="utf-8"))


def registry_record() -> dict:
    registry = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    matches = [
        record
        for record in registry["strategies"]
        if isinstance(record, dict)
        and (record.get("strategy_id") or record.get("id"))
        == reconciliation.STRATEGY_ID
    ]
    assert len(matches) == 1
    return matches[0]


def test_required_artifacts_and_counts() -> None:
    assert {path.name for path in EVIDENCE.iterdir()} == (
        reconciliation.REQUIRED_OUTPUTS
    )
    manifest = yaml_payload("reconciliation_manifest.yaml")
    assert manifest["task_id"] == reconciliation.TASK_ID
    assert manifest["mode"] == "standardization-patch"
    assert manifest["stage"] == "correction"
    assert manifest["process_outcome"] == "lifecycle_reconciliation_completed"
    assert manifest["process_failure_reason"] == ""
    assert (
        manifest["authoritative_strategy_records_created"],
        manifest["authoritative_strategy_records_updated"],
    ) in {(1, 0), (0, 1)}
    assert manifest["total_exact_configuration_records_after_reconciliation"] == 1
    assert manifest["existing_experiment_trials_carried_forward"] == 2
    assert manifest["new_experiment_trials"] == 0
    assert manifest["benchmark_references"] == 4
    assert manifest["process_tasks"] == 1
    assert manifest["observations_changed"] == 0
    assert manifest["new_research_candidates_created"] == 0
    assert manifest["exact_next_action"] == (
        "direction_owner_review_long_short_relative_value_capability_v1"
    )


def test_authoritative_record_is_complete_and_exactly_closed() -> None:
    record = registry_record()
    assert record["id"] == reconciliation.STRATEGY_ID
    assert record["strategy_id"] == reconciliation.STRATEGY_ID
    assert record["family_id"] == reconciliation.FAMILY_ID
    assert record["display_name"] == "SPY IBS Next-Open Intraday Portability"
    assert record["entity_type"] == "strategy_configuration"
    assert record["strategy_architecture"] == reconciliation.ARCHITECTURE
    assert record["source_or_research_lineage"] == reconciliation.SOURCE_LINEAGE
    assert record["instrument_universe"] == "SPY|BIL"
    assert record["parameters"] == reconciliation.FROZEN_PARAMETERS
    assert set(record["benchmark_or_control"]) == set(reconciliation.BENCHMARKS)
    assert record["stage"] == "closed"
    assert record["outcome"] == "validation_failed"
    assert record["current_status"] == "closed"
    assert record["trial_id"] == reconciliation.VALIDATION_TRIAL_ID
    assert record["parent_trial_id"] == reconciliation.EXPLORATION_TRIAL_ID
    assert record["adaptation_label"] == "validation_variant"
    assert record["failure_reason"] == "cost_drag"
    assert record["primary_failure_reason"] == "cost_drag"
    assert record["decision_reason"] == (
        "break_even_one_way_cost_below_10bps_and_negative_return_at_10bps"
    )
    assert record["secondary_diagnostic"] == (
        "second_half_and_rolling_period_instability"
    )
    assert record["next_action"] == (
        "do_not_retest_exact_ibs_next_open_portability_configuration"
    )
    assert record["paper_demo_eligible"] is False
    assert record["paper_demo_active"] is False
    assert record["real_money_authorized"] is False
    assert record["family_level_interpretation"] == (
        "exact_execution_portability_configuration_closed_cost_and_stability_failure"
    )
    assert record["registration_reason"] == "retrospective_status_reconciliation"
    assert reconciliation.required_record_complete(record) is True
    serialized = yaml.safe_dump(record).lower()
    assert "unknown" not in serialized
    assert "unmapped" not in serialized


def test_fingerprint_and_alias_detection_are_deterministic() -> None:
    fingerprint_rows = rows("configuration_fingerprint.csv")
    assert {
        row["fingerprint"] for row in fingerprint_rows
    } == {reconciliation.configuration_fingerprint()}
    fields = {row["field"]: row["value"] for row in fingerprint_rows}
    assert fields["family_id"] == reconciliation.FAMILY_ID
    assert fields["instrument_universe"] == "SPY|BIL"
    assert fields["ibs_threshold"] == "0.2"
    assert fields["comparison"] == "strict_less_than"
    assert fields["entry_timestamp"] == "regular_session_open_t_plus_1"
    assert fields["exit_timestamp"] == "regular_session_close_t_plus_1"
    assert fields["SPY_overnight_return_included"] == "false"

    registry = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    alias = reconciliation.target_registry_record()
    alias["id"] = "equivalent_ibs_alias_v1"
    alias["strategy_id"] = "equivalent_ibs_alias_v1"
    registry["strategies"] = [
        record
        for record in registry["strategies"]
        if (record.get("strategy_id") or record.get("id"))
        != reconciliation.STRATEGY_ID
    ] + [alias]
    exact, aliases = reconciliation.inspect_registry(registry)
    assert exact == []
    assert len(aliases) == 1
    assert aliases[0]["match_type"] == "exact_configuration_alias"


def test_trials_benchmarks_and_process_remain_separate() -> None:
    trials = rows("trial_ledger.csv")
    benchmarks = rows("benchmark_reference_log.csv")
    process = rows("process_task_log.csv")
    assert len(trials) == 2
    assert {row["entity_type"] for row in trials} == {"experiment_trial"}
    assert {row["trial_id"] for row in trials} == {
        reconciliation.EXPLORATION_TRIAL_ID,
        reconciliation.VALIDATION_TRIAL_ID,
    }
    assert {row["read_only"] for row in trials} == {"true"}
    assert {row["new_experiment_trial_created"] for row in trials} == {"false"}
    validation = next(
        row
        for row in trials
        if row["trial_id"] == reconciliation.VALIDATION_TRIAL_ID
    )
    assert validation["parent_trial_id"] == reconciliation.EXPLORATION_TRIAL_ID
    assert validation["stage"] == "validation"
    assert validation["outcome"] == "validation_failed"
    assert validation["failure_reason"] == "cost_drag"
    assert validation["next_action"] == reconciliation.STRATEGY_NEXT_ACTION
    assert len(benchmarks) == 4
    assert {row["benchmark_or_control_id"] for row in benchmarks} == set(
        reconciliation.BENCHMARKS
    )
    assert {row["entity_type"] for row in benchmarks} == {
        "benchmark_reference"
    }
    assert {row["stage"] for row in benchmarks} == {
        "benchmark_reference_only"
    }
    assert process == [
        {
            "task_id": reconciliation.TASK_ID,
            "entity_type": "process_task",
            "stage": "correction",
            "outcome": "lifecycle_reconciliation_completed",
            "failure_reason": "",
            "exact_next_action": (
                "direction_owner_review_long_short_relative_value_capability_v1"
            ),
            "strategy_counted": "false",
            "experiment_trial_counted": "false",
        }
    ]


def test_decisive_validation_evidence_is_preserved_not_recomputed() -> None:
    check = json_payload("consistency_check.json")
    assert check["evidence_gate_passed"] is True
    assert check["evidence_gate_blockers"] == []
    assert check["input_evidence_hashes_unchanged"] is True
    failures = rows("failure_reasons.csv")
    assert failures == [
        {
            "entity_type": "strategy_configuration",
            "entity_id": reconciliation.STRATEGY_ID,
            "stage": "closed",
            "outcome": "validation_failed",
            "failure_reason": "cost_drag",
            "decision_reason": reconciliation.DECISION_REASON,
            "secondary_evidence": reconciliation.SECONDARY_DIAGNOSTIC,
        }
    ]


def test_closure_scope_does_not_close_the_family() -> None:
    record = registry_record()
    assert "configuration_only" in record["closure_scope"]
    assert record["family_level_interpretation"] == (
        "exact_execution_portability_configuration_closed_cost_and_stability_failure"
    )
    assert "does not close all ibs" in record["notes"].lower()
    assert record["forbidden_next_actions"][0] == "retest_exact_configuration"
    registry = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    matches = [
        item
        for item in registry["strategies"]
        if (item.get("strategy_id") or item.get("id"))
        == reconciliation.STRATEGY_ID
    ]
    assert len(matches) == 1


def test_outcomes_and_next_actions_are_exact() -> None:
    outcome = rows("outcome_summary.csv")[0]
    assert outcome["process_outcome"] == "lifecycle_reconciliation_completed"
    assert outcome["strategy_stage"] == "closed"
    assert outcome["strategy_outcome"] == "validation_failed"
    assert outcome["strategy_failure_reason"] == "cost_drag"
    assert outcome["strategy_decision_reason"] == reconciliation.DECISION_REASON
    assert outcome["strategy_secondary_evidence"] == (
        reconciliation.SECONDARY_DIAGNOSTIC
    )
    assert outcome["strategy_next_action"] == reconciliation.STRATEGY_NEXT_ACTION
    assert outcome["project_next_action"] == (
        reconciliation.PROJECT_NEXT_ACTION_SUCCESS
    )
    assert outcome["existing_experiment_trials_carried_forward"] == "2"
    assert outcome["new_experiment_trials"] == "0"
    actions = rows("next_actions.csv")
    assert {row["execute_now"] for row in actions} == {"false"}
    assert {row["exact_next_action"] for row in actions} == {
        reconciliation.STRATEGY_NEXT_ACTION,
        reconciliation.PROJECT_NEXT_ACTION_SUCCESS,
    }


def test_state_changes_are_limited_to_registry() -> None:
    check = json_payload("consistency_check.json")
    state = rows("state_change_manifest.csv")
    changed = {row["path"] for row in state if row["changed"] == "true"}
    assert check["status"] == "pass"
    assert check["consistency_passed"] is True
    assert check["all_source_of_truth_changes_permitted"] is True
    assert check["prior_evidence_unchanged"] is True
    assert changed <= {"strategy_lab/strategy_registry.yaml"}
    assert "strategy_lab/RESEARCH_ROADMAP.md" not in changed
    assert (
        "strategy_lab/research_os/research/research_queue.yaml" not in changed
    )
    assert (
        "strategy_lab/research_os/family_lineage/family_ledger.yaml"
        not in changed
    )
    assert (
        "strategy_lab/research_os/operations/active_observations.yaml"
        not in changed
    )
    assert not any(path.startswith("data/cache/") for path in changed)
    assert check["new_experiment_trials"] == 0
    assert check["observations_changed"] == 0
    assert check["new_research_candidates_created"] == 0
    for flag in reconciliation.FORBIDDEN_FLAGS:
        assert check[flag] is False


def test_registry_record_update_is_idempotent_in_memory() -> None:
    record = registry_record()
    assert record == reconciliation.target_registry_record()
    registry = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    exact, aliases = reconciliation.inspect_registry(registry)
    assert len(exact) == 1
    assert aliases == []
    assert reconciliation.required_record_complete(record) is True
