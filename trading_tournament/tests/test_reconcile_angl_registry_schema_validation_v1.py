from __future__ import annotations

import csv
import json
from pathlib import Path

import yaml

from run_strategy_lab import validate_registry_data
from strategy_lab.research_os.research import reconcile_angl_registry_schema_validation_v1 as reconciliation


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "standardization" / "reconcile_angl_registry_schema_validation_v1" / "latest"
REGISTRY = ROOT / "strategy_lab" / "strategy_registry.yaml"
OBSERVATIONS = ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml"


def read_csv(name: str) -> list[dict[str, str]]:
    with (EVIDENCE / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_json(name: str) -> dict[str, object]:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def read_yaml(name: str) -> dict[str, object]:
    return yaml.safe_load((EVIDENCE / name).read_text(encoding="utf-8"))


def registry_record() -> dict[str, object]:
    payload = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    rows = [
        row
        for row in payload["strategies"]
        if (row.get("id") == reconciliation.STRATEGY_ID or row.get("strategy_id") == reconciliation.STRATEGY_ID)
    ]
    assert len(rows) == 1
    return rows[0]


def observation_record() -> dict[str, object]:
    payload = yaml.safe_load(OBSERVATIONS.read_text(encoding="utf-8"))
    rows = [
        row
        for row in payload["active_observations"]
        if row.get("observation_id") == reconciliation.OBSERVATION_ID
    ]
    assert len(rows) == 1
    return rows[0]


def test_required_artifacts_and_counts() -> None:
    required = {
        "patch_manifest.yaml",
        "validator_errors_before.csv",
        "field_mapping_decisions.csv",
        "strategy_cards.csv",
        "trial_ledger.csv",
        "paper_demo_observations.csv",
        "process_task_log.csv",
        "benchmark_reference_log.csv",
        "registry_record_before_after.csv",
        "validator_results_after.csv",
        "state_change_manifest.csv",
        "outcome_summary.csv",
        "failure_reasons.csv",
        "next_actions.csv",
        "consistency_check.json",
        "patch_report.md",
    }
    assert sorted(name for name in required if not (EVIDENCE / name).exists()) == []
    manifest = read_yaml("patch_manifest.yaml")
    assert manifest["process_outcome"] == "registry_schema_reconciliation_completed"
    assert manifest["strategy_configurations_created"] == 0
    assert manifest["strategy_configurations_updated"] == 1
    assert manifest["experiment_trials_created"] == 0
    assert manifest["existing_trials_carried_forward"] == 3
    assert manifest["paper_demo_observations_created"] == 0
    assert manifest["paper_demo_observations_updated"] == 0
    assert manifest["benchmark_references"] == 3
    assert manifest["process_tasks"] == 1
    assert manifest["new_research_candidates"] == 0
    assert manifest["exact_project_next_action"] == "refresh_strategy_source_library_v2"


def test_registry_record_uses_valid_schema_enums_and_preserves_semantics() -> None:
    record = registry_record()
    assert record["entity_type"] == "strategy_configuration"
    assert record["strategy_architecture"] == "structural_fallen_angel_credit_sleeve"
    assert record["source_or_research_lineage"] == "strategy_source_library_refresh_v1"
    assert record["instrument_universe"] == "ANGL"
    assert record["parameters"] == reconciliation.FROZEN_PARAMETERS
    assert set(record["benchmark_or_control"]) == set(reconciliation.BENCHMARKS)
    assert record["lane"] == "paper_forward"
    assert record["credibility_tier"] == "tier4_paper_forward"
    assert record["status"] == "gated"
    assert record["implementation_status"] == "implemented"
    assert record["allowed_next_action"] == "no_action"
    assert record["allowed_next_actions"] == ["no_action"]
    assert record["stage"] == "paper_demo_eligible"
    assert record["outcome"] == "paper_demo_eligible"
    assert record["route"] == "diversifier_only"
    assert record["paper_demo_eligible"] is True
    assert record["paper_forward_active"] is False
    assert record["standalone_100pct_angl_observation_approved"] is False
    assert record["real_money_authorized"] is False
    assert record["validation_trial_id"] == reconciliation.VALIDATION_TRIAL_ID
    assert record["methodology_correction_trial_id"] == reconciliation.METHODOLOGY_TRIAL_ID
    assert record["observation_id"] == reconciliation.OBSERVATION_ID
    assert record["observation_stage"] == "blocked"
    assert record["observation_outcome"] == "observation_invalid_or_incomplete"
    assert record["observation_next_action"] == reconciliation.OBSERVATION_NEXT_ACTION
    assert reconciliation.required_semantics_complete(record) is True


def test_registry_validator_has_zero_angl_and_hrp_errors() -> None:
    payload = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    result = validate_registry_data(payload)
    assert result["passed"] is True
    assert reconciliation.angl_errors(result) == []
    assert reconciliation.hrp_errors(result) == []
    after = read_csv("validator_results_after.csv")
    assert after == [
        {
            "validator_passed": "true",
            "total_errors": "0",
            "angl_errors": "0",
            "hrp_errors": "0",
            "new_errors_caused_by_patch": "false",
            "errors": "",
        }
    ]


def test_exact_pre_patch_errors_and_field_mappings_are_recorded() -> None:
    errors = read_csv("validator_errors_before.csv")
    mappings = read_csv("field_mapping_decisions.csv")
    expected_fields = {
        "allowed_next_actions",
        "promotion_reason",
        "primary_failure_mode",
        "lane",
        "credibility_tier",
        "status",
        "implementation_status",
        "allowed_next_action",
    }
    assert len(errors) == 8
    assert len(mappings) == 8
    assert {row["field"] for row in errors} == expected_fields
    assert {row["field"] for row in mappings} == expected_fields
    assert all(row["accepted_schema_or_enum"] for row in mappings)
    assert all(row["minimum_compliant_correction"] for row in mappings)
    assert all(row["authoritative_evidence"] for row in mappings)


def test_observation_remains_blocked_inactive_and_unduplicated() -> None:
    observation = observation_record()
    assert observation["entity_type"] == "paper_demo_observation"
    assert observation["stage"] == "blocked"
    assert observation["outcome"] == "observation_invalid_or_incomplete"
    assert observation["failure_reason"] == "methodology_failure"
    assert observation["adaptation_label"] == "paper_demo_observation_fix"
    assert observation["next_action"] == reconciliation.OBSERVATION_NEXT_ACTION
    assert observation["paper_forward_active"] is False
    evidence_rows = read_csv("paper_demo_observations.csv")
    assert len(evidence_rows) == 1
    assert evidence_rows[0]["created"] == "false"
    assert evidence_rows[0]["updated"] == "false"


def test_trial_lineage_is_read_only_and_entity_types_remain_separate() -> None:
    trials = read_csv("trial_ledger.csv")
    assert len(trials) == 3
    assert {row["entity_type"] for row in trials} == {"experiment_trial"}
    assert {row["read_only"] for row in trials} == {"true"}
    assert {row["new_experiment_trial_created"] for row in trials} == {"false"}
    assert {row["trial_id"] for row in trials} == {
        reconciliation.EXPLORATION_TRIAL_ID,
        reconciliation.VALIDATION_TRIAL_ID,
        reconciliation.METHODOLOGY_TRIAL_ID,
    }
    validation = next(row for row in trials if row["trial_id"] == reconciliation.VALIDATION_TRIAL_ID)
    methodology = next(row for row in trials if row["trial_id"] == reconciliation.METHODOLOGY_TRIAL_ID)
    assert validation["parent_trial_id"] == reconciliation.EXPLORATION_TRIAL_ID
    assert methodology["parent_trial_id"] == reconciliation.VALIDATION_TRIAL_ID
    assert read_csv("strategy_cards.csv")[0]["entity_type"] == "strategy_configuration"
    assert read_csv("paper_demo_observations.csv")[0]["entity_type"] == "paper_demo_observation"
    assert {row["entity_type"] for row in read_csv("benchmark_reference_log.csv")} == {"benchmark_reference"}
    assert read_csv("process_task_log.csv")[0]["entity_type"] == "process_task"


def test_only_registry_changed_and_prior_evidence_is_unchanged() -> None:
    check = read_json("consistency_check.json")
    assert check["consistency_passed"] is True
    assert check["source_of_truth_changed_paths"] == ["strategy_lab/strategy_registry.yaml"]
    assert check["all_source_of_truth_changes_permitted"] is True
    assert check["input_evidence_hashes_unchanged"] is True
    assert check["active_observations_unchanged"] is True
    assert check["strategy_configurations_created"] == 0
    assert check["experiment_trials_created"] == 0
    assert check["paper_demo_observations_created"] == 0
    assert check["paper_demo_observations_updated"] == 0
    assert check["new_research_candidates"] == 0
    for flag in reconciliation.FORBIDDEN_FLAGS:
        assert check[flag] is False


def test_outcomes_failures_next_actions_and_entity_counts_are_exact() -> None:
    outcome = read_csv("outcome_summary.csv")[0]
    failure = read_csv("failure_reasons.csv")[0]
    next_actions = read_csv("next_actions.csv")
    assert outcome["process_outcome"] == "registry_schema_reconciliation_completed"
    assert outcome["strategy_stage"] == "paper_demo_eligible"
    assert outcome["strategy_outcome"] == "paper_demo_eligible"
    assert outcome["observation_stage"] == "blocked"
    assert outcome["observation_outcome"] == "observation_invalid_or_incomplete"
    assert outcome["observation_failure_reason"] == "methodology_failure"
    assert failure["entity_type"] == "paper_demo_observation"
    assert failure["failure_reason"] == "methodology_failure"
    assert failure["strategy_validation_failure"] == "false"
    assert {row["exact_next_action"] for row in next_actions} == {
        reconciliation.OBSERVATION_NEXT_ACTION,
        "refresh_strategy_source_library_v2",
    }
    assert {row["execute_now"] for row in next_actions} == {"false"}
