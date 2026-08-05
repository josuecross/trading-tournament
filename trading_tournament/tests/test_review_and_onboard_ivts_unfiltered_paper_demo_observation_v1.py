from __future__ import annotations

import csv
import json
from pathlib import Path

import yaml

from run_strategy_lab import validate_registry_data
from strategy_lab.research_os.research import (
    review_and_onboard_ivts_unfiltered_paper_demo_observation_v1 as task,
)


def rows(name: str) -> list[dict[str, str]]:
    with (task.OUTPUT_DIR / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def consistency() -> dict[str, object]:
    return json.loads(
        (task.OUTPUT_DIR / "consistency_check.json").read_text(encoding="utf-8")
    )


def test_required_artifacts_and_consistency() -> None:
    assert all((task.OUTPUT_DIR / name).exists() for name in task.REQUIRED_ARTIFACTS)
    assert consistency()["overall_pass"] is True


def test_eligibility_is_only_the_frozen_20pct_diversifier_route() -> None:
    manifest = yaml.safe_load(
        (task.OUTPUT_DIR / "eligibility_manifest.yaml").read_text(encoding="utf-8")
    )
    assert manifest["route"] == "20pct_diversifier_only"
    assert manifest["approved_sleeve_weight"] == 0.2
    assert manifest["approved_reference_weight"] == 0.8
    assert manifest["standalone_eligible"] is False
    assert manifest["broker_eligible"] is False
    assert manifest["real_money_authorized"] is False
    assert manifest["historical_vintage_safety_established"] is False
    assert manifest["principal_caveat"] == (
        "historical_signal_data_current_history_non_vintage"
    )


def test_validation_is_reconciled_without_rerun() -> None:
    reconciliation = rows("eligibility_evidence_reconciliation.csv")
    assert len(reconciliation) == 10
    assert all(row["status"] == "pass" for row in reconciliation)
    assert all(row["validation_rerun_performed"] == "false" for row in reconciliation)
    assert consistency()["validation_rerun_performed"] is False


def test_duplicate_screen_and_fingerprint_are_deterministic() -> None:
    duplicate = rows("duplicate_and_alias_check.csv")
    assert len(duplicate) == 5
    assert next(row for row in duplicate if row["check_id"] == "exact_strategy_id")[
        "match_count"
    ] == "0"
    assert next(row for row in duplicate if row["check_id"] == "exact_observation_id")[
        "match_count"
    ] == "0"
    fingerprint = rows("configuration_fingerprint.csv")[0]
    assert fingerprint["configuration_fingerprint"] == task.canonical_hash(
        task.configuration_payload()
    )
    assert float(fingerprint["outer_sleeve_weight"]) == 0.2


def test_exact_entity_counts_and_lineage() -> None:
    trials = rows("trial_ledger.csv")
    benchmarks = rows("benchmark_reference_log.csv")
    process = rows("process_task_log.csv")
    assert len(trials) == 1
    assert trials[0]["trial_id"] == task.VALIDATION_TRIAL_ID
    assert trials[0]["lineage_role"] == "carried_forward_read_only"
    assert trials[0]["new_experiment_trial_created"] == "false"
    assert len(benchmarks) == 4
    assert {row["benchmark_reference_id"] for row in benchmarks} == set(
        task.COMPARATORS
    )
    assert len(process) == 1
    assert consistency()["new_experiment_trials"] == 0


def test_official_capture_is_bounded_reproducible_and_immutable() -> None:
    capture = rows("official_forward_capture_reproducibility.csv")
    assert len(capture) == 4
    assert {row["series"] for row in capture} == {"VIX", "VIX3M"}
    assert {row["attempt"] for row in capture} == {"1", "2"}
    assert all(row["duplicate_retrieval_matches"] == "true" for row in capture)
    assert all(row["raw_hash"] and row["normalized_hash"] for row in capture)
    for row in capture:
        path = task.ROOT / row["raw_path"]
        assert path.exists()
        assert task.file_hash(path) == row["raw_hash"]
    snapshot_paths = list((task.OUTPUT_DIR / "forward_snapshots").rglob("snapshot_record.json"))
    assert len(snapshot_paths) == 1
    snapshot = json.loads(snapshot_paths[0].read_text(encoding="utf-8"))
    assert snapshot["immutable_original_snapshot"] is True
    assert snapshot["later_revision_may_replace_original"] is False
    assert snapshot["historical_backfill"] is False
    assert snapshot["signal_date_strictly_before_execution"] is True


def test_operational_gate_is_explicit_and_no_forward_row_is_backfilled() -> None:
    probe = rows("forward_data_operational_probe.csv")
    boundary = rows("activation_boundary.csv")[0]
    observation = rows("paper_demo_observation_record.csv")[0]
    assert len(probe) == 10
    assert boundary["historical_forward_rows_created"] == "0"
    assert boundary["historical_backfill"] == "false"
    assert boundary["first_forward_observation_date"] == ""
    assert observation["historical_backfill"] == "prohibited"
    assert observation["forward_records_created"] == "0"
    if any(row["status"] == "fail" for row in probe):
        assert observation["stage"] == "deferred"
        assert observation["outcome"] == task.DEFERRED_OUTCOME


def test_registry_and_observation_records_are_unique_and_valid() -> None:
    registry = yaml.safe_load(task.REGISTRY_PATH.read_text(encoding="utf-8"))
    active = yaml.safe_load(task.ACTIVE_OBSERVATIONS_PATH.read_text(encoding="utf-8"))
    strategy = task.matching_strategy_records(registry)
    observation = task.matching_observation_records(active)
    assert len(strategy) == 1
    assert len(observation) == 1
    assert validate_registry_data(registry)["passed"] is True
    assert task.validate_active_observation_document(active)["passed"] is True
    assert strategy[0]["stage"] == "paper_demo_eligible"
    assert strategy[0]["route"] == "diversifier_only"
    assert strategy[0]["standalone_eligible"] is False
    assert strategy[0]["historical_vintage_safety_established"] is False
    assert observation[0]["observation_id"] == task.OBSERVATION_ID
    assert observation[0]["broker_submission"] is False
    assert observation[0]["real_money_authorized"] is False


def test_only_permitted_state_changed_and_prior_evidence_is_unchanged() -> None:
    check = consistency()
    changed = set(check["changed_state_paths"])
    assert changed == {
        "strategy_lab/strategy_registry.yaml",
        "strategy_lab/research_os/operations/active_observations.yaml",
    }
    assert check["only_permitted_state_changes"] is True
    assert check["roadmap_unchanged"] is True
    assert check["research_queue_unchanged"] is True
    assert check["family_ledger_unchanged"] is True
    assert check["prior_evidence_unchanged"] is True
    assert check["cache_unchanged"] is True


def test_no_broker_order_or_forbidden_action() -> None:
    check = consistency()
    assert check["broker_orders"] == 0
    assert check["forward_records_created"] == 0
    assert check["historical_backfill_performed"] is False
    assert check["standalone_eligibility_granted"] is False
    assert not any(check["forbidden_actions"].values())
