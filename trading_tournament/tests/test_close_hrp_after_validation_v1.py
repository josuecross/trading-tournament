from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest
import yaml

from strategy_lab.research_os.research import close_hrp_after_validation_v1 as closure


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "lifecycle" / "close_hrp_after_validation_v1" / "latest"
STRATEGY_ID = "lopez_de_prado_hrp_five_asset_v1"
VALIDATION_TRIAL_ID = "validation_hrp__lopez_de_prado_hrp_five_asset_v1__validation_variant_child"
PARENT_TRIAL_ID = "fast_source_v4__lopez_de_prado_hrp_five_asset_v1__canonical"


@pytest.fixture(scope="module", autouse=True)
def generated_closure() -> dict[str, object]:
    return closure.run()


def read_csv(name: str) -> list[dict[str, str]]:
    with (EVIDENCE / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_json(name: str) -> dict[str, object]:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def read_yaml(name: str) -> dict[str, object]:
    return yaml.safe_load((EVIDENCE / name).read_text(encoding="utf-8"))


def test_required_artifacts_and_blocked_manifest() -> None:
    required = {
        "closure_manifest.yaml",
        "strategy_cards.csv",
        "trial_ledger.csv",
        "process_task_log.csv",
        "benchmark_reference_log.csv",
        "closure_decision.csv",
        "state_change_manifest.csv",
        "outcome_summary.csv",
        "failure_reasons.csv",
        "next_actions.csv",
        "consistency_check.json",
        "closure_report.md",
    }
    assert sorted(name for name in required if not (EVIDENCE / name).exists()) == []
    manifest = read_yaml("closure_manifest.yaml")
    assert manifest["task_id"] == "close_hrp_after_validation_v1"
    assert manifest["mode"] == "active-direction-execution"
    assert manifest["lane"] == "targeted_lifecycle_closure"
    assert manifest["task_stage"] == "correction"
    assert manifest["strategy_id"] == STRATEGY_ID
    assert manifest["process_outcome"] == "lifecycle_recording_blocked"
    assert manifest["process_failure_reason"] == "status_reconciliation_required"
    assert manifest["strategy_configurations_updated"] == 0
    assert manifest["new_experiment_trials"] == 0
    assert manifest["paper_demo_observations_changed"] == 0
    assert manifest["exact_next_action"] == "direction_owner_review_hrp_closure_block_v1"


def test_blocked_because_exact_registry_record_is_absent() -> None:
    check = read_json("consistency_check.json")
    assert check["consistency_passed"] is True
    assert check["closure_supported"] is False
    assert check["registry_record_count_before"] == 0
    assert check["registry_record_count_after"] == 0
    assert check["exactly_one_existing_hrp_strategy_record_found"] is False
    assert check["process_failure_reason"] == "status_reconciliation_required"
    assert check["decision_reason"] == "exact_hrp_strategy_record_absent_from_strategy_registry"
    assert check["blocker_details"] == ["registry_record_count=0"]
    assert check["no_partial_state_update_when_blocked"] is True


def test_strategy_card_preserves_failed_validation_without_claiming_closure_update() -> None:
    rows = read_csv("strategy_cards.csv")
    assert len(rows) == 1
    row = rows[0]
    assert row["strategy_id"] == STRATEGY_ID
    assert row["family_id"] == "hierarchical_risk_parity_allocation"
    assert row["display_name"] == "Five-Asset Hierarchical Risk Parity"
    assert row["entity_type"] == "strategy_configuration"
    assert row["stage"] == "validation"
    assert row["outcome"] == "validation_failed"
    assert row["failure_reason"] == "benchmark_like_behavior"
    assert row["trial_id"] == VALIDATION_TRIAL_ID
    assert row["parent_trial_id"] == PARENT_TRIAL_ID
    assert row["adaptation_label"] == "validation_variant"
    assert row["next_action"] == "direction_owner_review_hrp_closure_block_v1"
    assert row["family_level_interpretation"] == "exact_configuration_closed_no_incremental_value"
    assert row["lifecycle_recording_status"] == "blocked_no_source_of_truth_update"
    assert row["counted_as_strategy_configuration_update"] == "false"
    assert "unknown" not in "|".join(row.values()).lower()


def test_trial_is_carried_forward_and_no_new_trial_created() -> None:
    rows = read_csv("trial_ledger.csv")
    assert len(rows) == 1
    row = rows[0]
    assert row["entity_type"] == "experiment_trial"
    assert row["stage"] == "validation"
    assert row["trial_id"] == VALIDATION_TRIAL_ID
    assert row["parent_trial_id"] == PARENT_TRIAL_ID
    assert row["adaptation_label"] == "validation_variant"
    assert row["changed_fields_from_parent"] == "validation_diagnostics_and_predeclared_simple_controls_only"
    assert row["outcome"] == "validation_failed"
    assert row["failure_reason"] == "benchmark_like_behavior"
    assert row["next_action"] == "do_not_retest_exact_hrp_five_asset_configuration"
    assert row["new_experiment_trial_created"] == "false"
    assert row["counted_as_new_trial"] == "false"


def test_benchmarks_process_and_funnel_counts_are_separate() -> None:
    benchmarks = read_csv("benchmark_reference_log.csv")
    process = read_csv("process_task_log.csv")
    outcome = read_csv("outcome_summary.csv")[0]
    assert {row["benchmark_or_control_id"] for row in benchmarks} == {
        "frozen_current_active_vm_dsr_usci_combo",
        "monthly_equal_weight_same_five_etfs",
        "clare_inverse_volatility_five_asset_risk_parity_v1",
        "static_initial_hrp_weight_control",
        "IEF_single_asset_20pct_control",
        "BIL_cash_20pct_control",
    }
    assert {row["entity_type"] for row in benchmarks} == {"benchmark_reference"}
    assert {row["stage"] for row in benchmarks} == {"benchmark_reference_only"}
    assert {row["counted_as_strategy"] for row in benchmarks} == {"false"}
    assert {row["counted_as_trial"] for row in benchmarks} == {"false"}
    assert {row["approved_by_this_task"] for row in benchmarks} == {"false"}
    assert process == [
        {
            "task_id": "close_hrp_after_validation_v1",
            "display_name": "Close HRP After Failed Validation",
            "entity_type": "process_task",
            "stage": "correction",
            "outcome": "lifecycle_recording_blocked",
            "failure_reason": "status_reconciliation_required",
            "exact_next_action": "direction_owner_review_hrp_closure_block_v1",
            "strategy_counted": "false",
            "trial_counted": "false",
        }
    ]
    assert outcome["strategy_configurations_updated"] == "0"
    assert outcome["existing_experiment_trials_carried_forward"] == "1"
    assert outcome["new_experiment_trials"] == "0"
    assert outcome["benchmark_references"] == "6"
    assert outcome["process_tasks"] == "1"
    assert outcome["paper_demo_observations_changed"] == "0"


def test_closure_decision_uses_authoritative_validation_facts() -> None:
    row = read_csv("closure_decision.csv")[0]
    assert row["closure_decision"] == "blocked"
    assert row["strategy_outcome"] == "validation_failed"
    assert row["strategy_failure_reason"] == "benchmark_like_behavior"
    assert row["decision_reason"] == "exact_hrp_strategy_record_absent_from_strategy_registry"
    assert row["family_level_interpretation"] == "exact_configuration_closed_no_incremental_value"
    assert row["rolling_36_median_sharpe_difference_vs_best_control"] == "-0.0932387867065"
    assert row["rolling_60_median_sharpe_difference_vs_best_control"] == "-0.0680303046563"
    assert row["rolling_36_positive_sharpe_difference_count"] == "0"
    assert row["rolling_60_positive_sharpe_difference_count"] == "0"
    assert row["rolling_36_control_dominated_window_pct"] == "0.806451612903"
    assert row["rolling_60_control_dominated_window_pct"] == "0.984732824427"
    assert row["average_IEF_weight"] == "0.736271881035"
    assert row["percentage_months_IEF_largest_allocation"] == "0.948497854077"


def test_state_hashes_and_validation_evidence_are_unchanged() -> None:
    check = read_json("consistency_check.json")
    state_rows = read_csv("state_change_manifest.csv")
    assert check["source_of_truth_changed_paths"] == []
    assert check["all_source_of_truth_changes_permitted"] is True
    assert check["validation_evidence_hashes_unchanged"] is True
    assert {row["changed"] for row in state_rows} == {"false"}
    assert {row["change_description"] for row in state_rows} == {"unchanged"}


def test_failure_reasons_next_actions_and_forbidden_flags() -> None:
    failures = read_csv("failure_reasons.csv")
    next_actions = read_csv("next_actions.csv")
    check = read_json("consistency_check.json")
    assert {
        (row["entity_type"], row["failure_reason"])
        for row in failures
    } == {
        ("strategy_configuration", "benchmark_like_behavior"),
        ("process_task", "status_reconciliation_required"),
    }
    assert {row["execute_now"] for row in next_actions} == {"false"}
    assert {row["exact_next_action"] for row in next_actions} == {
        "",
        "direction_owner_review_hrp_closure_block_v1",
    }
    for flag in closure.FORBIDDEN_FLAGS:
        assert check[flag] is False


def test_generation_is_deterministic() -> None:
    first = read_json("consistency_check.json")
    first_report = (EVIDENCE / "closure_report.md").read_text(encoding="utf-8")
    result = closure.run()
    second = read_json("consistency_check.json")
    assert result["consistency_passed"] is True
    assert second == first
    assert (EVIDENCE / "closure_report.md").read_text(encoding="utf-8") == first_report
