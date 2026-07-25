from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest
import yaml

from strategy_lab.research_os.research import reconcile_missing_hrp_registry_record_and_close_v1 as reconciliation


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "lifecycle" / "reconcile_missing_hrp_registry_record_and_close_v1" / "latest"
REGISTRY = ROOT / "strategy_lab" / "strategy_registry.yaml"
STRATEGY_ID = "lopez_de_prado_hrp_five_asset_v1"
FAMILY_ID = "hierarchical_risk_parity_allocation"
EXPLORATION_TRIAL_ID = "fast_source_v4__lopez_de_prado_hrp_five_asset_v1__canonical"
VALIDATION_TRIAL_ID = "validation_hrp__lopez_de_prado_hrp_five_asset_v1__validation_variant_child"
BENCHMARKS = {
    "frozen_current_active_vm_dsr_usci_combo",
    "monthly_equal_weight_same_five_etfs",
    "clare_inverse_volatility_five_asset_risk_parity_v1",
    "static_initial_hrp_weight_control",
    "IEF_single_asset_20pct_control",
    "BIL_cash_20pct_control",
}
EXPECTED_PARAMETERS = {
    "return_type": "daily_log_return",
    "lookback_trading_days": 252,
    "covariance_estimator": "sample_covariance",
    "distance_formula": "sqrt((1-rho)/2)",
    "linkage_method": "single",
    "tie_break": "lexical_ticker_order",
    "rebalance_frequency": "monthly",
    "execution": "month_end_signal_next_available_session_close",
    "warmup_rule": "equal_weights_before_252_observations",
}


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


def load_registry_record() -> dict[str, object]:
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


def test_required_artifacts_and_manifest_counts() -> None:
    required = {
        "reconciliation_manifest.yaml",
        "duplicate_and_alias_check.csv",
        "configuration_fingerprint.csv",
        "strategy_cards.csv",
        "trial_ledger.csv",
        "process_task_log.csv",
        "benchmark_reference_log.csv",
        "registry_record_before_after.csv",
        "state_change_manifest.csv",
        "outcome_summary.csv",
        "failure_reasons.csv",
        "next_actions.csv",
        "consistency_check.json",
        "reconciliation_report.md",
    }
    assert sorted(name for name in required if not (EVIDENCE / name).exists()) == []
    manifest = read_yaml("reconciliation_manifest.yaml")
    assert manifest["task_id"] == "reconcile_missing_hrp_registry_record_and_close_v1"
    assert manifest["mode"] == "standardization-patch"
    assert manifest["stage"] == "correction"
    assert manifest["strategy_id"] == STRATEGY_ID
    assert manifest["family_id"] == FAMILY_ID
    assert manifest["process_outcome"] == "lifecycle_reconciliation_completed"
    assert manifest["process_failure_reason"] == ""
    assert (manifest["authoritative_strategy_records_created"], manifest["authoritative_strategy_records_updated"]) in {
        (1, 0),
        (0, 1),
    }
    assert manifest["total_exact_hrp_records_after_reconciliation"] == 1
    assert manifest["existing_experiment_trials_carried_forward"] == 2
    assert manifest["new_experiment_trials"] == 0
    assert manifest["benchmark_references"] == 6
    assert manifest["process_tasks"] == 1
    assert manifest["paper_demo_observations_changed"] == 0
    assert manifest["new_research_candidates_created"] == 0
    assert manifest["exact_next_action"] == "refresh_strategy_source_library_v2"


def test_authoritative_registry_record_is_exact_complete_and_closed() -> None:
    record = load_registry_record()
    assert record["id"] == STRATEGY_ID
    assert record["strategy_id"] == STRATEGY_ID
    assert record["family_id"] == FAMILY_ID
    assert record["display_name"] == "Five-Asset Hierarchical Risk Parity"
    assert record["entity_type"] == "strategy_configuration"
    assert record["strategy_architecture"] == "hierarchical_risk_based_multi_asset_allocation"
    assert record["source_or_research_lineage"] == "strategy_source_library_refresh_v1__lopez_de_prado_hrp"
    assert record["instrument_universe"] == "SPY|EEM|IEF|DBC|VNQ"
    assert record["parameters"] == EXPECTED_PARAMETERS
    assert set(record["benchmark_or_control"]) == BENCHMARKS
    assert record["stage"] == "closed"
    assert record["lane"] == "archive"
    assert record["instrument_family"] == "ETF"
    assert record["version"] == "v1"
    assert record["parent_id"] == EXPLORATION_TRIAL_ID
    assert record["credibility_tier"] == "blocked"
    assert record["status"] == "rejected"
    assert record["current_status"] == "closed"
    assert record["outcome"] == "validation_failed"
    assert record["trial_id"] == VALIDATION_TRIAL_ID
    assert record["parent_trial_id"] == EXPLORATION_TRIAL_ID
    assert record["adaptation_label"] == "validation_variant"
    assert record["failure_reason"] == "benchmark_like_behavior"
    assert record["decision_reason"] == "IEF_or_BIL_economically_replicates_HRP_contribution"
    assert record["next_action"] == "do_not_retest_exact_hrp_five_asset_configuration"
    assert record["allowed_next_action"] == "no_action"
    assert record["allowed_next_actions"] == ["no_action"]
    assert record["paper_demo_eligible"] is False
    assert record["paper_demo_active"] is False
    assert record["benchmark_reference_only"] is False
    assert record["real_money_authorized"] is False
    assert record["real_money_recommendation"] is False
    assert record["family_level_interpretation"] == "exact_configuration_closed_no_incremental_value"
    assert record["registration_reason"] == "retrospective_status_reconciliation"
    assert record["closure_scope"] == "exact_five_etf_252d_sample_cov_single_linkage_monthly_next_session_close_configuration_only"
    assert record["implementation_status"] == "archived"
    assert record["instrument_lane"] == "ETF"
    assert record["evidence_tier"] == "blocked"
    assert record["primary_failure_mode"] == "benchmark_like_behavior"
    assert record["duplication_risk"] == "exact_configuration_no_incremental_value"
    assert record["evidence_needed"] == "none_for_exact_closed_configuration"
    assert record["blocked_reason"] == "benchmark_like_behavior"
    assert reconciliation.required_record_complete(record) is True
    assert "unknown" not in yaml.safe_dump(record).lower()
    assert "unmapped" not in yaml.safe_dump(record).lower()


def test_duplicate_and_alias_check_has_no_unresolved_equivalent_alias() -> None:
    rows = read_csv("duplicate_and_alias_check.csv")
    assert len(rows) == 1
    row = rows[0]
    assert row["duplicate_check_result"] in {
        "clear_to_create_one_closed_record",
        "exact_record_exists",
    }
    assert row["match_type"] in {"no_exact_record_no_equivalent_alias", "exact_strategy_id"}
    assert row["strategy_id"] in {"", STRATEGY_ID}
    assert "alias" not in row["duplicate_check_result"]


def test_configuration_fingerprint_is_deterministic_and_source_defined() -> None:
    rows = read_csv("configuration_fingerprint.csv")
    by_field = {row["field"]: row["value"] for row in rows}
    fingerprints = {row["fingerprint"] for row in rows}
    assert len(fingerprints) == 1
    assert next(iter(fingerprints)) == reconciliation.configuration_fingerprint()
    assert by_field["family_id"] == FAMILY_ID
    assert by_field["instrument_universe"] == "SPY|EEM|IEF|DBC|VNQ"
    assert by_field["lookback_trading_days"] == "252"
    assert by_field["covariance_estimator"] == "sample_covariance"
    assert by_field["linkage_method"] == "single"
    assert by_field["tie_break"] == "lexical_ticker_order"
    assert by_field["rebalance_frequency"] == "monthly"
    assert by_field["execution"] == "month_end_signal_next_available_session_close"


def test_strategy_card_trial_lineage_and_benchmark_entities_are_separate() -> None:
    cards = read_csv("strategy_cards.csv")
    trials = read_csv("trial_ledger.csv")
    benchmarks = read_csv("benchmark_reference_log.csv")
    process = read_csv("process_task_log.csv")
    assert len(cards) == 1
    assert cards[0]["entity_type"] == "strategy_configuration"
    assert cards[0]["stage"] == "closed"
    assert cards[0]["outcome"] == "validation_failed"
    assert cards[0]["benchmark_reference_only"] == "false"
    assert len(trials) == 2
    assert {row["entity_type"] for row in trials} == {"experiment_trial"}
    assert {row["trial_id"] for row in trials} == {EXPLORATION_TRIAL_ID, VALIDATION_TRIAL_ID}
    assert {row["new_experiment_trial_created"] for row in trials} == {"false"}
    assert {row["counted_as_new_trial"] for row in trials} == {"false"}
    validation_trial = next(row for row in trials if row["trial_id"] == VALIDATION_TRIAL_ID)
    assert validation_trial["parent_trial_id"] == EXPLORATION_TRIAL_ID
    assert validation_trial["changed_fields_from_parent"] == (
        "validation_diagnostics_and_predeclared_simple_controls_only"
    )
    assert validation_trial["outcome"] == "validation_failed"
    assert validation_trial["failure_reason"] == "benchmark_like_behavior"
    assert {row["benchmark_or_control_id"] for row in benchmarks} == BENCHMARKS
    assert {row["entity_type"] for row in benchmarks} == {"benchmark_reference"}
    assert {row["stage"] for row in benchmarks} == {"benchmark_reference_only"}
    assert {row["counted_as_strategy"] for row in benchmarks} == {"false"}
    assert {row["counted_as_trial"] for row in benchmarks} == {"false"}
    assert {row["counted_as_observation"] for row in benchmarks} == {"false"}
    assert process == [
        {
            "task_id": "reconcile_missing_hrp_registry_record_and_close_v1",
            "entity_type": "process_task",
            "stage": "correction",
            "outcome": "lifecycle_reconciliation_completed",
            "failure_reason": "",
            "exact_next_action": "refresh_strategy_source_library_v2",
            "strategy_counted": "false",
            "experiment_trial_counted": "false",
        }
    ]


def test_outcomes_failure_reasons_and_next_actions_are_exact() -> None:
    outcome = read_csv("outcome_summary.csv")[0]
    failures = read_csv("failure_reasons.csv")
    next_actions = read_csv("next_actions.csv")
    assert outcome["process_outcome"] == "lifecycle_reconciliation_completed"
    assert outcome["total_exact_hrp_records_after_reconciliation"] == "1"
    assert outcome["existing_experiment_trials_carried_forward"] == "2"
    assert outcome["new_experiment_trials"] == "0"
    assert outcome["benchmark_references"] == "6"
    assert outcome["process_tasks"] == "1"
    assert outcome["paper_demo_observations_changed"] == "0"
    assert outcome["new_research_candidates_created"] == "0"
    assert outcome["strategy_stage"] == "closed"
    assert outcome["strategy_outcome"] == "validation_failed"
    assert outcome["strategy_failure_reason"] == "benchmark_like_behavior"
    assert outcome["strategy_next_action"] == "do_not_retest_exact_hrp_five_asset_configuration"
    assert outcome["project_next_action"] == "refresh_strategy_source_library_v2"
    assert failures == [
        {
            "entity_type": "strategy_configuration",
            "entity_id": STRATEGY_ID,
            "stage": "closed",
            "outcome": "validation_failed",
            "failure_reason": "benchmark_like_behavior",
            "decision_reason": "IEF_or_BIL_economically_replicates_HRP_contribution",
        }
    ]
    assert {row["execute_now"] for row in next_actions} == {"false"}
    assert {row["exact_next_action"] for row in next_actions} == {
        "do_not_retest_exact_hrp_five_asset_configuration",
        "refresh_strategy_source_library_v2",
    }


def test_state_changes_are_limited_and_forbidden_work_flags_are_false() -> None:
    check = read_json("consistency_check.json")
    state_rows = read_csv("state_change_manifest.csv")
    changed = {row["path"] for row in state_rows if row["changed"] == "true"}
    assert check["consistency_passed"] is True
    assert check["all_source_of_truth_changes_permitted"] is True
    assert check["input_evidence_hashes_unchanged"] is True
    assert changed <= {"strategy_lab/strategy_registry.yaml"}
    assert "strategy_lab/research_os/operations/active_observations.yaml" not in changed
    assert "strategy_lab/research_os/research/research_queue.yaml" not in changed
    assert "strategy_lab/research_os/family_lineage/family_ledger.yaml" not in changed
    assert "strategy_lab/RESEARCH_ROADMAP.md" not in changed
    assert check["new_experiment_trials"] == 0
    assert check["paper_demo_observations_changed"] == 0
    assert check["new_research_candidates_created"] == 0
    for flag in reconciliation.FORBIDDEN_FLAGS:
        assert check[flag] is False


def test_generation_is_idempotent_after_exact_record_exists() -> None:
    record_before = load_registry_record()
    registry_hash_before = sha256(REGISTRY)
    result = reconciliation.run()
    record_after = load_registry_record()
    registry_hash_after = sha256(REGISTRY)
    check = read_json("consistency_check.json")
    assert result["consistency_passed"] is True
    assert result["authoritative_strategy_records_created"] == 0
    assert result["authoritative_strategy_records_updated"] == 1
    assert record_after == record_before
    assert registry_hash_after == registry_hash_before
    assert check["source_of_truth_changed_paths"] == []
    assert check["total_exact_hrp_records_after_reconciliation"] == 1
