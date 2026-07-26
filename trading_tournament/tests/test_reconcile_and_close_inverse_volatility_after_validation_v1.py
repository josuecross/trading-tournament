from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest
import yaml

from strategy_lab.research_os.research import reconcile_and_close_inverse_volatility_after_validation_v1 as reconciliation


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "lifecycle" / reconciliation.TASK_ID / "latest"
REGISTRY = ROOT / "strategy_lab" / "strategy_registry.yaml"
STRATEGY_ID = reconciliation.STRATEGY_ID
EXPLORATION_TRIAL_ID = reconciliation.EXPLORATION_TRIAL_ID
VALIDATION_TRIAL_ID = reconciliation.VALIDATION_TRIAL_ID
BENCHMARKS = set(reconciliation.BENCHMARKS_AND_CONTROLS)


@pytest.fixture(scope="module", autouse=True)
def generated_reconciliation() -> dict[str, object]:
    return reconciliation.run()


def read_csv(name: str) -> list[dict[str, str]]:
    with (EVIDENCE / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_json(name: str) -> dict[str, object]:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def read_yaml(name: str) -> dict[str, object]:
    return yaml.safe_load((EVIDENCE / name).read_text(encoding="utf-8"))


def registry_record() -> dict[str, object]:
    registry = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    records = [
        row
        for row in registry["strategies"]
        if isinstance(row, dict) and (row.get("strategy_id") or row.get("id")) == STRATEGY_ID
    ]
    assert len(records) == 1
    return records[0]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_required_artifacts_and_counts() -> None:
    required = {
        "reconciliation_manifest.yaml",
        "duplicate_and_alias_check.csv",
        "configuration_fingerprint.csv",
        "strategy_cards.csv",
        "trial_ledger.csv",
        "benchmark_reference_log.csv",
        "process_task_log.csv",
        "registry_record_before_after.csv",
        "state_change_manifest.csv",
        "outcome_summary.csv",
        "failure_reasons.csv",
        "next_actions.csv",
        "consistency_check.json",
        "reconciliation_report.md",
    }
    assert not [name for name in required if not (EVIDENCE / name).exists()]
    manifest = read_yaml("reconciliation_manifest.yaml")
    assert manifest["task_id"] == reconciliation.TASK_ID
    assert manifest["mode"] == "standardization-patch"
    assert manifest["stage"] == "correction"
    assert manifest["process_outcome"] == "lifecycle_reconciliation_completed"
    assert (
        manifest["authoritative_strategy_records_created"],
        manifest["authoritative_strategy_records_updated"],
    ) in {(1, 0), (0, 1)}
    assert manifest["total_exact_configuration_records_after_reconciliation"] == 1
    assert manifest["existing_experiment_trials_carried_forward"] == 2
    assert manifest["new_experiment_trials"] == 0
    assert manifest["benchmark_references"] == 6
    assert manifest["process_tasks"] == 1
    assert manifest["paper_demo_observations_changed"] == 0
    assert manifest["new_research_candidates_created"] == 0
    assert manifest["exact_next_action"] == "refresh_strategy_source_library_v4"


def test_registry_has_one_complete_closed_exact_configuration() -> None:
    record = registry_record()
    assert record["id"] == record["strategy_id"] == STRATEGY_ID
    assert record["family_id"] == "risk_parity_inverse_volatility_or_vol_targeting"
    assert record["display_name"] == "Five-Asset Inverse-Volatility Allocation"
    assert record["entity_type"] == "strategy_configuration"
    assert record["strategy_architecture"] == "monthly_inverse_volatility_multi_asset_allocation"
    assert record["source_or_research_lineage"] == "strategy_source_library_refresh_v1__clare_inverse_volatility"
    assert record["instrument_universe"] == "SPY|EEM|IEF|DBC|VNQ"
    assert record["parameters"] == reconciliation.FROZEN_PARAMETERS
    assert record["configuration_constraints"] == reconciliation.CONFIGURATION_CONSTRAINTS
    assert set(record["benchmark_or_control"]) == BENCHMARKS
    assert record["stage"] == record["current_status"] == "closed"
    assert record["status"] == "rejected"
    assert record["outcome"] == "validation_failed"
    assert record["trial_id"] == VALIDATION_TRIAL_ID
    assert record["parent_trial_id"] == EXPLORATION_TRIAL_ID
    assert record["adaptation_label"] == "validation_variant"
    assert record["failure_reason"] == record["primary_failure_reason"] == "benchmark_like_behavior"
    assert (
        record["decision_reason"]
        == "static_initial_inverse_volatility_control_replicates_or_exceeds_dynamic_inverse_volatility"
    )
    assert record["next_action"] == "do_not_retest_exact_dynamic_inverse_volatility_configuration"
    assert record["paper_demo_eligible"] is False
    assert record["paper_demo_active"] is False
    assert record["real_money_authorized"] is False
    assert (
        record["family_level_interpretation"]
        == "exact_configuration_closed_no_incremental_dynamic_weighting_value"
    )
    assert record["registration_reason"] == "retrospective_status_reconciliation"
    assert (
        record["closure_scope"]
        == "exact_five_etf_12_month_sample_std_inverse_volatility_monthly_equal_weight_warmup_next_session_close_configuration_only"
    )
    assert record["configuration_fingerprint"] == reconciliation.configuration_fingerprint()
    assert reconciliation.required_record_complete(record) is True
    dumped = yaml.safe_dump(record).lower()
    assert "unknown" not in dumped
    assert "unmapped" not in dumped


def test_duplicate_alias_check_and_fingerprint_are_deterministic() -> None:
    duplicates = read_csv("duplicate_and_alias_check.csv")
    assert len(duplicates) == 1
    assert duplicates[0]["match_type"] == "exact_strategy_id"
    assert duplicates[0]["duplicate_check_result"] == "exact_record_exists"
    assert duplicates[0]["strategy_id"] == STRATEGY_ID
    rows = read_csv("configuration_fingerprint.csv")
    by_field = {row["field"]: row["value"] for row in rows}
    assert {row["fingerprint"] for row in rows} == {reconciliation.configuration_fingerprint()}
    assert by_field["instrument_universe"] == "SPY|EEM|IEF|DBC|VNQ"
    assert by_field["volatility_window_months"] == "12"
    assert by_field["sample_standard_deviation_ddof"] == "1"
    assert by_field["weighting"] == "inverse_volatility_normalized_to_1"
    assert by_field["leverage"] == "none"
    assert by_field["weight_caps"] == "none"
    assert by_field["trend_filter"] == "none"
    assert by_field["volatility_target"] == "none"


def test_two_existing_trials_are_read_only_and_no_new_trial_exists() -> None:
    trials = read_csv("trial_ledger.csv")
    assert len(trials) == 2
    assert {row["entity_type"] for row in trials} == {"experiment_trial"}
    assert {row["trial_id"] for row in trials} == {EXPLORATION_TRIAL_ID, VALIDATION_TRIAL_ID}
    assert {row["read_only"] for row in trials} == {"true"}
    assert {row["new_experiment_trial_created"] for row in trials} == {"false"}
    assert {row["counted_as_new_trial"] for row in trials} == {"false"}
    exploration = next(row for row in trials if row["trial_id"] == EXPLORATION_TRIAL_ID)
    assert exploration["stage"] == "exploration"
    assert exploration["adaptation_label"] == "data_feasibility_adjustment"
    assert exploration["outcome"] == "exploratory_followup_candidate_diversifier"
    validation = next(row for row in trials if row["trial_id"] == VALIDATION_TRIAL_ID)
    assert validation["parent_trial_id"] == EXPLORATION_TRIAL_ID
    assert validation["stage"] == "validation"
    assert validation["adaptation_label"] == "validation_variant"
    assert (
        validation["changed_fields_from_parent"]
        == "validation_diagnostics_and_predeclared_static_and_simple_exposure_controls_only"
    )
    assert validation["outcome"] == "validation_failed"
    assert validation["failure_reason"] == "benchmark_like_behavior"
    assert validation["next_action"] == "do_not_retest_exact_dynamic_inverse_volatility_configuration"


def test_benchmarks_and_process_task_are_separate() -> None:
    benchmarks = read_csv("benchmark_reference_log.csv")
    assert {row["benchmark_or_control_id"] for row in benchmarks} == BENCHMARKS
    assert {row["entity_type"] for row in benchmarks} == {"benchmark_reference"}
    assert {row["stage"] for row in benchmarks} == {"benchmark_reference_only"}
    assert {row["counted_as_strategy"] for row in benchmarks} == {"false"}
    assert {row["counted_as_trial"] for row in benchmarks} == {"false"}
    assert {row["counted_as_observation"] for row in benchmarks} == {"false"}
    process = read_csv("process_task_log.csv")
    assert process == [
        {
            "task_id": reconciliation.TASK_ID,
            "entity_type": "process_task",
            "stage": "correction",
            "outcome": "lifecycle_reconciliation_completed",
            "failure_reason": "",
            "exact_next_action": "refresh_strategy_source_library_v4",
            "strategy_counted": "false",
            "experiment_trial_counted": "false",
        }
    ]


def test_outcome_failure_and_next_actions_are_exact() -> None:
    outcome = read_csv("outcome_summary.csv")[0]
    assert outcome["process_outcome"] == "lifecycle_reconciliation_completed"
    assert outcome["strategy_stage"] == "closed"
    assert outcome["strategy_outcome"] == "validation_failed"
    assert outcome["strategy_failure_reason"] == "benchmark_like_behavior"
    assert outcome["strategy_next_action"] == "do_not_retest_exact_dynamic_inverse_volatility_configuration"
    assert outcome["project_next_action"] == "refresh_strategy_source_library_v4"
    assert read_csv("failure_reasons.csv") == [
        {
            "entity_type": "strategy_configuration",
            "entity_id": STRATEGY_ID,
            "stage": "closed",
            "outcome": "validation_failed",
            "failure_reason": "benchmark_like_behavior",
            "decision_reason": (
                "static_initial_inverse_volatility_control_replicates_or_exceeds_"
                "dynamic_inverse_volatility"
            ),
        }
    ]
    assert {row["execute_now"] for row in read_csv("next_actions.csv")} == {"false"}
    assert {row["exact_next_action"] for row in read_csv("next_actions.csv")} == {
        "do_not_retest_exact_dynamic_inverse_volatility_configuration",
        "refresh_strategy_source_library_v4",
    }


def test_only_permitted_authoritative_state_changed_and_no_forbidden_work_occurred() -> None:
    check = read_json("consistency_check.json")
    changed = {
        row["path"]
        for row in read_csv("state_change_manifest.csv")
        if row["changed"] == "true"
    }
    assert check["consistency_passed"] is True
    assert check["input_evidence_hashes_unchanged"] is True
    assert check["all_source_of_truth_changes_permitted"] is True
    assert changed <= {"strategy_lab/strategy_registry.yaml"}
    assert check["new_experiment_trials"] == 0
    assert check["paper_demo_observations_changed"] == 0
    assert check["new_research_candidates_created"] == 0
    for flag in reconciliation.FORBIDDEN_FLAGS:
        assert check[flag] is False


def test_generation_is_idempotent() -> None:
    before_record = registry_record()
    before_hash = sha256(REGISTRY)
    result = reconciliation.run()
    after_record = registry_record()
    after_hash = sha256(REGISTRY)
    check = read_json("consistency_check.json")
    assert result["process_outcome"] == "lifecycle_reconciliation_completed"
    assert result["authoritative_strategy_records_created"] == 0
    assert result["authoritative_strategy_records_updated"] == 1
    assert result["new_experiment_trials"] == 0
    assert before_record == after_record
    assert before_hash == after_hash
    assert check["source_of_truth_changed_paths"] == []
    assert check["total_exact_configuration_records_after_reconciliation"] == 1
