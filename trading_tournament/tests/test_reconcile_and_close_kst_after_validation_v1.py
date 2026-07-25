from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest
import yaml

from strategy_lab.research_os.research import reconcile_and_close_kst_after_validation_v1 as reconciliation


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "lifecycle" / "reconcile_and_close_kst_after_validation_v1" / "latest"
REGISTRY = ROOT / "strategy_lab" / "strategy_registry.yaml"
STRATEGY_ID = "pring_kst_default_centerline_spy_bil_v1"
FAMILY_ID = "multi_cycle_smoothed_roc_momentum"
EXPLORATION_TRIAL_ID = "fast_source_v5__pring_kst_default_centerline_spy_bil_v1__canonical"
VALIDATION_TRIAL_ID = "pring_kst_incremental_standalone_validation_v1__validation_child"
BENCHMARKS = {
    "SPY_buy_and_hold",
    "SPY_30_session_ROC_sign_SPY_BIL",
    "SPY_200d_frozen_control",
    "static_6878_SPY_3122_BIL_monthly_rebalanced",
}
EXPECTED_PARAMETERS = {
    "roc_periods": [10, 15, 20, 30],
    "smoothing_periods": [10, 10, 10, 15],
    "component_weights": [1, 2, 3, 4],
    "centerline": 0,
    "signal_line": "unused",
    "spy_rule": "hold_SPY_when_KST_strictly_positive",
    "bil_rule": "hold_BIL_when_KST_nonpositive_or_before_warmup",
    "signal_timestamp": "completed_daily_close",
    "execution": "completed_close_signal_applied_to_following_session",
    "costs_tested_bps": [0, 5, 10],
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
    assert manifest["task_id"] == "reconcile_and_close_kst_after_validation_v1"
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
    assert manifest["total_exact_kst_records_after_reconciliation"] == 1
    assert manifest["existing_experiment_trials_carried_forward"] == 2
    assert manifest["new_experiment_trials"] == 0
    assert manifest["benchmark_references"] == 4
    assert manifest["process_tasks"] == 1
    assert manifest["paper_demo_observations_changed"] == 0
    assert manifest["new_research_candidates_created"] == 0
    assert manifest["exact_next_action"] == "evaluate_deferred_structural_source_records_v2"


def test_authoritative_registry_record_is_exact_complete_and_closed() -> None:
    record = load_registry_record()
    assert record["id"] == STRATEGY_ID
    assert record["strategy_id"] == STRATEGY_ID
    assert record["family_id"] == FAMILY_ID
    assert record["display_name"] == "Pring KST Multi-Cycle Centerline State"
    assert record["entity_type"] == "strategy_configuration"
    assert record["strategy_architecture"] == "weighted_multi_horizon_smoothed_rate_of_change_filter"
    assert record["source_or_research_lineage"] == "strategy_source_library_refresh_v2:src_pring_kst_1992_v1"
    assert record["instrument_universe"] == "SPY|BIL"
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
    assert record["failure_reason"] == "period_instability"
    assert record["primary_failure_reason"] == "period_instability"
    assert record["next_action"] == "do_not_retest_exact_kst_default_centerline_configuration"
    assert record["allowed_next_action"] == "no_action"
    assert record["allowed_next_actions"] == ["no_action"]
    assert record["paper_demo_eligible"] is False
    assert record["paper_demo_active"] is False
    assert record["paper_forward_active"] is False
    assert record["benchmark_reference_only"] is False
    assert record["real_money_authorized"] is False
    assert record["real_money_recommendation"] is False
    assert record["family_level_interpretation"] == "exact_configuration_closed_period_instability"
    assert record["registration_reason"] == "retrospective_status_reconciliation"
    assert record["implementation_status"] == "archived"
    assert record["instrument_lane"] == "ETF"
    assert record["evidence_tier"] == "blocked"
    assert record["primary_failure_mode"] == "period_instability"
    assert record["blocked_reason"] == "period_instability"
    assert reconciliation.required_record_complete(record) is True
    dumped = yaml.safe_dump(record).lower()
    assert "unknown" not in dumped
    assert "unmapped" not in dumped


def test_duplicate_alias_check_and_fingerprint_are_deterministic() -> None:
    rows = read_csv("duplicate_and_alias_check.csv")
    assert len(rows) == 1
    assert rows[0]["duplicate_check_result"] in {"clear_to_create_one_closed_record", "exact_record_exists"}
    assert rows[0]["match_type"] in {"no_exact_record_no_equivalent_alias", "exact_strategy_id"}
    fingerprint_rows = read_csv("configuration_fingerprint.csv")
    by_field = {row["field"]: row["value"] for row in fingerprint_rows}
    assert {row["fingerprint"] for row in fingerprint_rows} == {reconciliation.configuration_fingerprint()}
    assert by_field["family_id"] == FAMILY_ID
    assert by_field["instrument_universe"] == "SPY|BIL"
    assert by_field["roc_periods"] == "10|15|20|30"
    assert by_field["smoothing_periods"] == "10|10|10|15"
    assert by_field["component_weights"] == "1|2|3|4"
    assert by_field["centerline"] == "0"
    assert by_field["signal_line"] == "unused"
    assert by_field["execution"] == "completed_close_signal_applied_to_following_session"


def test_equivalent_alias_blocks_without_writing_registry() -> None:
    registry = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    alias = reconciliation.target_registry_record()
    alias["id"] = "equivalent_kst_alias_v1"
    alias["strategy_id"] = "equivalent_kst_alias_v1"
    registry["strategies"] = [
        row
        for row in registry["strategies"]
        if (row.get("strategy_id") or row.get("id")) != STRATEGY_ID
    ] + [alias]
    exact, aliases = reconciliation.inspect_registry(registry)
    before = sha256(REGISTRY)
    result = reconciliation.apply_reconciliation(registry, exact, aliases, True)
    after = sha256(REGISTRY)
    assert exact == []
    assert len(aliases) == 1
    assert aliases[0]["match_type"] == "exact_configuration_alias"
    assert result[:4] == ("lifecycle_reconciliation_blocked", "status_reconciliation_required", 0, 0)
    assert before == after


def test_strategy_trial_benchmark_and_process_entities_are_separate() -> None:
    cards = read_csv("strategy_cards.csv")
    trials = read_csv("trial_ledger.csv")
    benchmarks = read_csv("benchmark_reference_log.csv")
    process = read_csv("process_task_log.csv")
    assert len(cards) == 1
    assert cards[0]["entity_type"] == "strategy_configuration"
    assert cards[0]["stage"] == "closed"
    assert cards[0]["outcome"] == "validation_failed"
    assert len(trials) == 2
    assert {row["entity_type"] for row in trials} == {"experiment_trial"}
    assert {row["trial_id"] for row in trials} == {EXPLORATION_TRIAL_ID, VALIDATION_TRIAL_ID}
    assert {row["new_experiment_trial_created"] for row in trials} == {"false"}
    assert {row["counted_as_new_trial"] for row in trials} == {"false"}
    exploration = next(row for row in trials if row["trial_id"] == EXPLORATION_TRIAL_ID)
    assert exploration["stage"] == "exploration"
    assert exploration["outcome"] == "exploratory_followup_candidate_standalone"
    validation = next(row for row in trials if row["trial_id"] == VALIDATION_TRIAL_ID)
    assert validation["parent_trial_id"] == EXPLORATION_TRIAL_ID
    assert validation["stage"] == "validation"
    assert validation["adaptation_label"] == "validation_variant"
    assert validation["changed_fields_from_parent"] == (
        "validation_diagnostics_and_predeclared_exposure_and_trend_controls_only"
    )
    assert validation["outcome"] == "validation_failed"
    assert validation["failure_reason"] == "period_instability"
    assert {row["benchmark_or_control_id"] for row in benchmarks} == BENCHMARKS
    assert {row["entity_type"] for row in benchmarks} == {"benchmark_reference"}
    assert {row["stage"] for row in benchmarks} == {"benchmark_reference_only"}
    assert {row["counted_as_strategy"] for row in benchmarks} == {"false"}
    assert {row["counted_as_trial"] for row in benchmarks} == {"false"}
    assert {row["counted_as_observation"] for row in benchmarks} == {"false"}
    assert process == [
        {
            "task_id": "reconcile_and_close_kst_after_validation_v1",
            "entity_type": "process_task",
            "stage": "correction",
            "outcome": "lifecycle_reconciliation_completed",
            "failure_reason": "",
            "exact_next_action": "evaluate_deferred_structural_source_records_v2",
            "strategy_counted": "false",
            "experiment_trial_counted": "false",
        }
    ]


def test_outcomes_and_next_actions_are_exact() -> None:
    outcome = read_csv("outcome_summary.csv")[0]
    failures = read_csv("failure_reasons.csv")
    next_actions = read_csv("next_actions.csv")
    assert outcome["process_outcome"] == "lifecycle_reconciliation_completed"
    assert outcome["total_exact_kst_records_after_reconciliation"] == "1"
    assert outcome["existing_experiment_trials_carried_forward"] == "2"
    assert outcome["new_experiment_trials"] == "0"
    assert outcome["strategy_stage"] == "closed"
    assert outcome["strategy_outcome"] == "validation_failed"
    assert outcome["strategy_failure_reason"] == "period_instability"
    assert outcome["strategy_next_action"] == "do_not_retest_exact_kst_default_centerline_configuration"
    assert outcome["project_next_action"] == "evaluate_deferred_structural_source_records_v2"
    assert failures == [
        {
            "entity_type": "strategy_configuration",
            "entity_id": STRATEGY_ID,
            "stage": "closed",
            "outcome": "validation_failed",
            "failure_reason": "period_instability",
            "decision_reason": "rolling_control_dominance_and_negative_median_sharpe_differences",
        }
    ]
    assert {row["execute_now"] for row in next_actions} == {"false"}
    assert {row["exact_next_action"] for row in next_actions} == {
        "do_not_retest_exact_kst_default_centerline_configuration",
        "evaluate_deferred_structural_source_records_v2",
    }


def test_state_changes_are_limited_and_prior_evidence_is_unchanged() -> None:
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
    assert not any(path.startswith("data/cache/") for path in changed)
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
    assert check["total_exact_kst_records_after_reconciliation"] == 1
