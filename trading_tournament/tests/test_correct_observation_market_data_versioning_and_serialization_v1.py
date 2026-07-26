from __future__ import annotations

import csv
import json
from pathlib import Path

import pandas as pd
import pytest
import yaml

from strategy_lab.research_os.research import (
    correct_observation_market_data_versioning_and_serialization_v1 as task,
)


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "correction" / task.TASK_ID / "latest"


@pytest.fixture(scope="module", autouse=True)
def evidence_ready() -> None:
    assert (EVIDENCE / "consistency_check.json").exists(), (
        "Run the dedicated serial correction runner before focused tests."
    )


def rows(name: str) -> list[dict[str, str]]:
    with (EVIDENCE / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def payload(name: str) -> dict[str, object]:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def test_required_packet_is_complete() -> None:
    expected = {
        "correction_manifest.yaml",
        "strategy_cards.csv",
        "trial_ledger.csv",
        "paper_demo_observations.csv",
        "data_capability_task_log.csv",
        "process_task_log.csv",
        "provider_fetch_reproducibility.csv",
        "exact_overlap_field_differences.csv",
        "history_revision_classification.csv",
        "canonical_normalization_spec.yaml",
        "serialization_root_causes.csv",
        "serialization_hash_reconciliation.csv",
        "xlc_ohlc_violation_analysis.csv",
        "staged_data_integrity_checks.csv",
        "data_version_manifest.csv",
        "cohort_commit_decision.csv",
        "cache_before_after.csv",
        "cache_reload_reconciliation.csv",
        "reference_input_sufficiency.csv",
        "common_session_sufficiency.csv",
        "state_change_manifest.csv",
        "outcome_summary.csv",
        "failure_reasons.csv",
        "next_actions.csv",
        "consistency_check.json",
        "correction_report.md",
    }
    assert expected.issubset({path.name for path in EVIDENCE.iterdir()})


def test_exact_symbols_receive_two_fetches_from_one_provider() -> None:
    fetches = rows("provider_fetch_reproducibility.csv")
    tasks = rows("data_capability_task_log.csv")
    assert len(fetches) == len(tasks) == 20
    assert tuple(row["symbol"] for row in fetches) == task.TARGET_SYMBOLS
    assert tuple(row["symbol"] for row in tasks) == task.TARGET_SYMBOLS
    assert {row["candidate_fetch_attempts"] for row in fetches} == {"1"}
    assert {row["verification_fetch_attempts"] for row in fetches} == {"1"}
    assert {row["provider"] for row in fetches} == {task.PROVIDER_ID}
    assert {row["alpaca_attempted"] for row in fetches} == {"false"}
    assert {row["entity_type"] for row in tasks} == {"data_capability_task"}
    assert {row["adaptation_label"] for row in tasks} == {"methodology_correction"}
    assert {row["stage"] for row in tasks}.issubset({"feasible", "blocked"})


def test_canonical_hash_round_trip_includes_every_column(tmp_path: Path) -> None:
    symbol = "JNK"
    source = pd.read_csv(task.cache_path(symbol))
    canonical = task.canonicalize_frame(source, symbol)
    staged = tmp_path / "JNK.csv"
    task.write_canonical_csv(staged, canonical, symbol)
    reloaded = pd.read_csv(staged)
    assert task.canonical_frame_hash(canonical, symbol) == task.canonical_frame_hash(
        reloaded, symbol
    )
    spec = yaml.safe_load((EVIDENCE / "canonical_normalization_spec.yaml").read_text())
    assert spec["column_order"] == list(task.NORMALIZED_COLUMNS)
    assert spec["hash_columns_omitted"] == []
    assert spec["negative_zero"] == "normalized to positive zero"
    assert spec["missing_value_representation"] == task.MISSING_SENTINEL


def test_prior_serialization_failures_are_root_caused_and_corrected() -> None:
    prior_failures = {"JNK", "QUAL", "XLP", "XLY"}
    root_causes = {
        row["symbol"]: row for row in rows("serialization_root_causes.csv")
    }
    reconciliation = {
        row["symbol"]: row for row in rows("serialization_hash_reconciliation.csv")
    }
    assert {
        symbol
        for symbol, row in root_causes.items()
        if row["prior_serialization_failure_reported"] == "true"
    } == prior_failures
    for symbol in prior_failures:
        assert "derived binary floats" in root_causes[symbol]["root_cause"]
        assert root_causes[symbol]["columns_omitted_from_corrected_hash"] == ""
        assert root_causes[symbol]["hash_comparison_weakened"] == "false"
        assert reconciliation[symbol]["hashes_match"] == "true"


def test_field_level_revision_ledger_is_complete_and_typed() -> None:
    differences = rows("exact_overlap_field_differences.csv")
    revision = rows("history_revision_classification.csv")
    assert differences
    assert len(revision) == 20
    assert {row["symbol"] for row in revision} == set(task.TARGET_SYMBOLS)
    assert {
        row["field_category"] for row in differences
    }.issubset(
        {
            "raw_price",
            "raw_volume",
            "dividend",
            "split",
            "adjustment_factor",
            "adjusted_price",
        }
    )
    assert all(row["date"] and row["field"] for row in differences)
    assert all(row["candidate_matches_verification"] in {"true", "false"} for row in differences)
    assert all(int(row["missing_prior_dates"]) == 0 for row in revision)
    reported_one_row_symbols = {
        "ANGL",
        "BIL",
        "DBC",
        "HYG",
        "SPLV",
        "SPY",
        "USCI",
        "USMV",
        "XLB",
        "XLE",
        "XLF",
        "XLI",
        "XLK",
        "XLU",
        "XLV",
    }
    by_symbol = {row["symbol"]: row for row in revision}
    assert all(int(by_symbol[symbol]["raw_volume_rows_changed"]) == 1 for symbol in reported_one_row_symbols)
    assert all(
        int(by_symbol[symbol]["raw_price_rows_changed"]) in {0, 1}
        for symbol in reported_one_row_symbols
    )
    assert {
        by_symbol[symbol]["raw_overlap_revision_classification"]
        for symbol in reported_one_row_symbols
    }.issubset(
        {
            "raw_volume_revision_only",
            "corporate_action_restatement",
            "recent_session_price_correction",
        }
    )


def test_xlc_is_not_clipped_and_only_passes_as_numerically_immaterial() -> None:
    analysis = rows("xlc_ohlc_violation_analysis.csv")
    assert analysis
    assert {row["symbol"] for row in analysis} == {"XLC"}
    assert {row["row_deleted_or_clipped"] for row in analysis} == {"false"}
    if analysis[0]["analysis_status"] == "exact_violation_measured":
        for row in analysis:
            assert row["verification_fetch_same_values"] == "true"
            if row["raw_ohlc_relationship_valid"] == "true":
                assert row["numerically_immaterial"] == "true"
                assert float(row["violation_magnitude"]) <= float(row["strict_tolerance"])
            else:
                assert row["numerically_immaterial"] == "false"
                assert float(row["violation_magnitude"]) > float(row["strict_tolerance"])
                assert rows("outcome_summary.csv")[0]["outcome"] == task.OUTCOME_BLOCKED
    else:
        assert analysis[0]["numerically_immaterial"] == "true"


def test_integrity_serialization_and_provider_reproducibility_gate_commit() -> None:
    integrity = rows("staged_data_integrity_checks.csv")
    commit = rows("cohort_commit_decision.csv")
    outcome = rows("outcome_summary.csv")[0]
    assert len(commit) == 1
    committed = commit[0]["cohort_committed"] == "true"
    if committed:
        assert {row["status"] for row in integrity} == {"pass"}
        assert outcome["outcome"] == task.OUTCOME_READY
        assert outcome["cache_files_updated"] == "20"
        assert outcome["metadata_files_updated"] == "20"
    else:
        assert outcome["outcome"] == task.OUTCOME_BLOCKED
        assert outcome["cache_files_updated"] == "0"
        assert outcome["metadata_files_updated"] == "0"


def test_cohort_cache_transaction_is_all_or_none() -> None:
    cache = rows("cache_before_after.csv")
    commit = rows("cohort_commit_decision.csv")[0]
    assert len(cache) == 40
    changed = [row for row in cache if row["changed"] == "true"]
    assert len(changed) in {0, 40}
    assert commit["target_files_changed"] in {"0", "40"}
    assert commit["mixed_observation_data_version_created"] == "false"
    versions = rows("data_version_manifest.csv")
    assert len(versions) == 20
    if commit["cohort_committed"] == "true":
        version_ids = {row["data_version_id"] for row in versions}
        assert len(version_ids) == 1
        assert "" not in version_ids
        assert {row["admitted_to_canonical_cache"] for row in versions} == {"true"}
        reloads = rows("cache_reload_reconciliation.csv")
        assert {row["reload_pass"] for row in reloads} == {"true"}
        assert {row["reload_hash_match"] for row in reloads} == {"true"}
    else:
        assert {row["admitted_to_canonical_cache"] for row in versions} == {"false"}


def test_reference_sufficiency_is_data_only() -> None:
    common = rows("common_session_sufficiency.csv")[0]
    reference = rows("reference_input_sufficiency.csv")
    assert common["required_session"] == "2026-07-24"
    assert common["strategy_performance_calculated"] == "false"
    assert common["virtual_position_trade_or_nav_created"] == "false"
    assert {
        "VM_observation_inputs",
        "DSR_observation_inputs",
        "USCI_observation_inputs",
        "frozen_current_active_vm_dsr_usci_combo",
        "ANGL_candidate_input",
        "HYG_control_input",
        "JNK_control_input",
    } == {row["reference_or_input_id"] for row in reference}
    assert {row["strategy_performance_calculated"] for row in reference} == {"false"}
    assert {row["virtual_position_trade_or_nav_created"] for row in reference} == {"false"}


def test_strategy_trials_observation_and_process_remain_separate() -> None:
    strategy = rows("strategy_cards.csv")
    trials = rows("trial_ledger.csv")
    observation = rows("paper_demo_observations.csv")
    process = rows("process_task_log.csv")
    assert len(strategy) == 1
    assert strategy[0]["entity_type"] == "strategy_configuration"
    assert strategy[0]["stage"] == "paper_demo_eligible"
    assert strategy[0]["outcome"] == "paper_demo_eligible"
    assert strategy[0]["route"] == "diversifier_only"
    assert strategy[0]["created_in_this_task"] == "false"
    assert trials
    assert {row["entity_type"] for row in trials} == {"experiment_trial"}
    assert {row["read_only"] for row in trials} == {"true"}
    assert {row["new_trial_created"] for row in trials} == {"false"}
    assert len(observation) == 1
    assert observation[0]["stage"] == "blocked"
    assert observation[0]["outcome"] == "observation_invalid_or_incomplete"
    assert observation[0]["created_in_this_task"] == "false"
    assert observation[0]["activated_in_this_task"] == "false"
    assert observation[0]["forward_record_created"] == "false"
    assert len(process) == 1
    assert process[0]["entity_type"] == "process_task"
    assert process[0]["stage"] == "correction"
    assert process[0]["adaptation_label"] == "methodology_correction"


def test_protected_state_guardrails_and_next_actions() -> None:
    state = rows("state_change_manifest.csv")
    consistency = payload("consistency_check.json")
    protected = [
        row
        for row in state
        if row["path_type"]
        in {
            "protected_source_of_truth",
            "protected_operational_forward_state",
            "protected_prior_evidence",
            "protected_unrelated_cache",
        }
    ]
    assert protected
    assert {row["changed"] for row in protected} == {"false"}
    assert consistency["consistency_passed"] is True
    assert consistency["exactly_20_data_tasks"] is True
    assert consistency["candidate_and_verification_fetch_per_symbol"] is True
    assert consistency["total_provider_fetches"] == 40
    assert consistency["alpaca_retried"] is False
    assert consistency["cohort_commit_all_or_none"] is True
    assert consistency["protected_state_and_prior_evidence_unchanged"] is True
    assert consistency["unrelated_cache_hashes_unchanged"] is True
    assert consistency["unexpected_changes"] == []
    assert consistency["strategy_configurations_created"] == 0
    assert consistency["experiment_trials_created"] == 0
    assert consistency["observations_created"] == 0
    assert consistency["observations_activated"] == 0
    assert consistency["forward_records_created"] == 0
    assert consistency["strategy_performance_calculated"] is False
    assert consistency["broker_account_position_order_endpoint_called"] is False
    outcome = rows("outcome_summary.csv")[0]
    actions = {row["action_scope"]: row for row in rows("next_actions.csv")}
    expected = task.NEXT_READY if outcome["outcome"] == task.OUTCOME_READY else task.NEXT_BLOCKED
    assert outcome["observation_next_action"] == expected
    assert outcome["project_discovery_next_action"] == task.PROJECT_NEXT_ACTION
    assert actions["ANGL_observation"]["execute_in_this_task"] == "false"
    assert actions["separate_project_discovery"]["execute_in_this_task"] == "false"


def test_source_contains_no_broker_or_observation_execution() -> None:
    source = Path(task.__file__).read_text(encoding="utf-8")
    assert "submit_order(" not in source
    assert "get_account(" not in source
    assert "get_positions(" not in source
    assert "initialize_angl_after_next_completed_common_session_v1 import" not in source
