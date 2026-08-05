from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest
import yaml

from strategy_lab.research_os.research import (
    resume_strategy_discovery_while_psar_validation_deferred_v1 as task,
)


OUTPUT = task.OUTPUT_DIR


@pytest.fixture(scope="module", autouse=True)
def generated_packet() -> dict[str, object]:
    return task.run()


def rows(name: str) -> list[dict[str, str]]:
    with (OUTPUT / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def payload(name: str) -> dict:
    return json.loads((OUTPUT / name).read_text(encoding="utf-8"))


def manifest() -> dict:
    return yaml.safe_load((OUTPUT / "batch_manifest.yaml").read_text(encoding="utf-8"))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_required_outputs_exist() -> None:
    actual = {path.name for path in OUTPUT.iterdir() if path.is_file()}
    assert actual == task.REQUIRED_OUTPUTS


def test_shortfall_outcome_is_exact_and_performance_is_locked() -> None:
    value = manifest()
    summary = rows("outcome_summary.csv")[0]
    assert value["outcome"] == task.OUTCOME
    assert value["exact_next_action"] == task.NEXT_ACTION
    assert value["candidate_gate"]["eligible_candidate_count"] < 4
    assert value["candidate_gate"]["performance_authorized"] is False
    assert summary["performance_trials_executed"] == "0"


def test_inventory_and_funnel_counts_reconcile() -> None:
    inventory = rows("internal_candidate_inventory.csv")
    counts = payload("cohort_funnel_counts.json")
    assert len(inventory) == counts["total_internal_records_screened"]
    assert len(inventory) >= 100
    assert sum(row["source_complete"] == "True" for row in inventory) == (
        counts["source_complete_records"]
    )
    categories = {
        "exact_duplicate": "exact_duplicates",
        "data_blocked": "data_blocked_records",
        "capability_blocked": "capability_blocked_records",
        "incomplete": "incomplete_records",
    }
    for category, key in categories.items():
        assert sum(
            row["primary_blocker_category"] == category for row in inventory
        ) == counts[key]
    assert counts["eligible_records"] == 0


def test_every_v2_selected_source_record_was_already_tested() -> None:
    inventory = {row["candidate_id"]: row for row in rows("internal_candidate_inventory.csv")}
    v2 = task.read_yaml(task.V2_RECORDS)["records"]
    assert len(v2) == 6
    for source in v2:
        row = inventory[source["proposed_strategy_id"]]
        assert row["source_complete"] == "True"
        assert row["eligible"] == "False"
        assert row["primary_blocker_category"] == "exact_duplicate"


def test_v5_queue_produces_no_eligible_configuration() -> None:
    inventory = {row["candidate_id"]: row for row in rows("internal_candidate_inventory.csv")}
    for source in task.read_csv(task.V5_QUEUE):
        assert inventory[source["candidate_id"]]["eligible"] == "False"
    assert inventory["gatev_distance_pairs_12m_6m_2sd"][
        "primary_blocker_category"
    ] == "capability_blocked"
    assert inventory["research_affiliates_growth_inflation_taa"][
        "primary_blocker_category"
    ] == "data_blocked"


def test_protected_exact_configurations_do_not_reenter() -> None:
    inventory = {row["candidate_id"]: row for row in rows("internal_candidate_inventory.csv")}
    represented = task.PROTECTED_EXACT_CONFIGURATIONS & inventory.keys()
    assert represented
    for candidate_id in represented:
        assert inventory[candidate_id]["eligible"] == "False"
    assert rows("selected_candidate_cohort.csv") == []


def test_prior_controls_and_source_aliases_are_not_promoted() -> None:
    duplicates = {row["candidate_id"]: row for row in rows("duplicate_screening.csv")}
    for source_id, reference in task.SOURCE_ALIAS_TO_TESTED_OR_CONTROL.items():
        assert duplicates[source_id]["duplicate_reference"] == reference
        assert duplicates[source_id]["excluded"] == "True"


def test_zero_trial_files_have_headers_and_zero_rows() -> None:
    for name in (
        "source_library_records.csv",
        "strategy_cards.csv",
        "trial_ledger.csv",
        "benchmark_reference_log.csv",
        "data_preflight_reconciliation.csv",
        "all_trial_results.csv",
        "control_results.csv",
        "chronological_half_results.csv",
        "portfolio_contribution_results.csv",
        "turnover_cost_reconciliation.csv",
        "invariant_results.csv",
        "exploratory_followup_candidates.csv",
    ):
        assert (OUTPUT / name).read_text(encoding="utf-8").splitlines()
        assert rows(name) == []


def test_psar_deferred_state_is_preserved_exactly() -> None:
    psar = rows("psar_deferred_state_reconciliation.csv")
    assert len(psar) == 1
    assert psar[0]["strategy"] == "barbara_decelerated_psar_spy_bil_v1"
    assert psar[0]["route"] == "20pct_diversifier_only"
    assert psar[0]["historical_status"] == "robustness_positive"
    assert psar[0]["prospective_status"] == "activation_deferred"
    assert psar[0]["new_psar_trials_created"] == "0"
    assert psar[0]["new_activation_attempts"] == "0"
    assert psar[0]["counted_in_this_exploration_cohort"] == "False"


def test_entity_counts_remain_separate() -> None:
    counts = payload("cohort_funnel_counts.json")
    assert counts["source_library_records_created"] == 0
    assert counts["strategy_configurations_created"] == 0
    assert counts["experiment_trials_created"] == 0
    assert counts["benchmark_references_created"] == 0
    assert counts["data_capability_tasks_created"] == 0
    assert counts["process_tasks_created"] == 1
    assert len(rows("process_task_log.csv")) == 1


def test_protected_state_caches_and_prior_psar_packets_are_unchanged() -> None:
    consistency = payload("consistency_check.json")
    assert consistency["overall_pass"] is True
    assert consistency["protected_state_cache_and_prior_psar_unchanged"] is True
    assert consistency["protected_hashes_before"] == consistency["protected_hashes_after"]


def test_no_disallowed_actions_occurred() -> None:
    consistency = payload("consistency_check.json")
    for key in (
        "provider_access_performed",
        "source_research_performed",
        "source_completion_performed",
        "new_dependency_installed",
        "psar_analysis_performed",
        "psar_activation_attempted",
        "prior_controls_promoted",
        "lifecycle_state_changed",
        "paper_demo_observations_changed",
        "broker_or_order_path_touched",
        "real_money_action_performed",
    ):
        assert consistency[key] is False


def test_generation_is_deterministic() -> None:
    names = (
        "batch_manifest.yaml",
        "internal_candidate_inventory.csv",
        "cohort_funnel_counts.json",
        "consistency_check.json",
    )
    before = {name: digest(OUTPUT / name) for name in names}
    task.run()
    assert {name: digest(OUTPUT / name) for name in names} == before
