from __future__ import annotations

import csv
import json
from pathlib import Path

import pandas as pd
import yaml

from strategy_lab.research_os.research import (
    repair_and_retry_decelerated_psar_prospective_activation_v1 as task,
)


OUTPUT = task.OUTPUT_DIR


def rows(name: str) -> list[dict[str, str]]:
    with (OUTPUT / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def payload(name: str) -> dict:
    return json.loads((OUTPUT / name).read_text(encoding="utf-8"))


def manifest() -> dict:
    return yaml.safe_load(
        (OUTPUT / "repair_manifest.yaml").read_text(encoding="utf-8")
    )


def test_alias_failure_reproduces_and_authoritative_contract_is_complete() -> None:
    alias = task.reproduce_alias_error()
    assert alias["status"] == "pass"
    assert alias["exception_type"] == "AttributeError"
    assert alias["exception_message"] == (
        "initialization reference module alias did not expose VM_ID"
    )
    assert alias["expected_symbol"] == "VM_ID"
    assert "VM_ID" not in alias["actual_exported_symbols"]

    contract, passed = task.reference_import_contract_rows(
        task.synthetic_frames()
    )
    assert passed is True
    assert {row["contract_item"] for row in contract} >= {
        "VM_ID",
        "DSR_ID",
        "USCI_ID",
        "REFERENCE_ID",
        "vm_target",
        "dsr_target",
        "reference_symbols",
        "VM_target_schema",
        "DSR_target_schema",
        "USCI_target_schema",
    }
    assert {row["status"] for row in contract} == {"pass"}
    assert {row["guessed_identifier_fallback_used"] for row in contract} == {
        False
    }
    assert task.REFERENCE_ID == task.reference_engine.REFERENCE_ID
    assert task.prior_activation.REFERENCE_ID == task.reference_engine.REFERENCE_ID


def test_offline_dry_run_reaches_precommit_without_network(tmp_path: Path) -> None:
    before = task._NETWORK_CALL_COUNT
    result, passed, state = task.offline_dry_run(tmp_path / "offline")
    after = task._NETWORK_CALL_COUNT
    assert passed is True
    assert before == after
    assert {row["status"] for row in result} == {"pass"}
    assert result[-1]["step_id"] == "final_precommit_activation_gate"
    assert state["candidate"]["target"] in (
        {"SPY": 1.0, "BIL": 0.0},
        {"SPY": 0.0, "BIL": 1.0},
    )
    assert len(state["holdings"]) == len(task.PORTFOLIO_IDS)
    assert all(
        abs(sum(weights.values()) - 1.0) <= 1e-12
        for weights in state["holdings"].values()
    )


def test_required_packet_and_phase_a_gate_are_complete() -> None:
    assert {path.name for path in OUTPUT.iterdir() if path.is_file()} == (
        task.REQUIRED_OUTPUTS
    )
    value = manifest()
    assert value["phase_a_no_network_gate_passed"] is True
    assert value["network_calls_phase_a"] == 0
    assert value["replacement_provider_cycles"] == 1
    assert value["further_retry_authorized"] is False
    gate = rows("offline_gate_results.csv")
    assert gate
    assert {row["status"] for row in gate} == {"pass"}
    assert {row["network_calls_before"] for row in gate} == {"0"}
    assert {row["network_calls_after"] for row in gate} == {"0"}


def test_terminal_local_failure_is_exact_and_retry_is_closed() -> None:
    value = manifest()
    assert value["outcome"] == task.REPAIR_FAILED
    assert value["failure_reason"] == task.LOCAL_FAILURE
    assert value["exact_next_action"] == task.NEXT_DEFERRED
    assert value["replacement_runner_completed_without_exception"] is False
    assert value["evidence_finalization_completed"] is True
    assert value["further_retry_authorized"] is False
    attempts = rows("provider_attempt_log.csv")
    fallback = [
        row
        for row in attempts
        if row["provider_id"]
        == "yfinance_existing_repo_supported_adjusted_daily_path"
    ]
    assert len(fallback) == 1
    assert fallback[0]["status"] == "local_dependency_import_failure"
    assert fallback[0]["network_call_made"] == "false"


def test_prior_deferred_packet_and_zero_admitted_cycle_reconcile() -> None:
    reconciliation = rows("prior_activation_reconciliation.csv")
    assert reconciliation
    assert {row["status"] for row in reconciliation} == {"pass"}
    checks = {row["check_id"] for row in reconciliation}
    assert "prior_outcome_deferred" in checks
    assert "prior_admitted_retrieval_count_zero" in checks
    assert "prior_snapshot_count_zero" in checks
    assert "prior_error_matches_alias_defect" in checks


def test_provider_cycle_is_bounded_and_returned_data_are_durable() -> None:
    attempts = rows("provider_attempt_log.csv")
    raw = rows("raw_retrieval_manifest.csv")
    assert attempts
    assert {row["provider_sequence"] for row in attempts}.issubset({"1", "2"})
    assert {row["order_endpoint_called"] for row in attempts} == {"false"}
    assert {row["fallback_role"] for row in attempts}.issubset(
        {"primary", "single_existing_approved_fallback"}
    )
    returned = [
        row for row in attempts if row["raw_response_persisted"] == "true"
    ]
    assert returned
    assert raw
    assert {
        row["persisted_before_state_initialization"] for row in raw
    } == {"true"}
    assert {row["canonical_cache_modified"] for row in raw} == {"false"}
    for row in raw:
        if row["normalized_path"]:
            path = task.ROOT / row["normalized_path"]
            assert path.is_file()
            assert task.file_hash(path) == row["normalized_hash"]


def test_duplicate_retrieval_and_snapshot_contracts_match_outcome() -> None:
    value = manifest()
    reproducibility = rows("retrieval_reproducibility.csv")
    snapshots = rows("immutable_snapshot_manifest.csv")
    if value["outcome"] == task.ACTIVATED:
        assert len(reproducibility) == len(task.SYMBOLS)
        assert {row["reproducibility_status"] for row in reproducibility} == {
            "pass"
        }
        assert len(snapshots) == len(task.SYMBOLS)
        assert {row["schema_status"] for row in snapshots} == {"pass"}
        assert {row["symbol"] for row in snapshots} == set(task.SYMBOLS)
    else:
        assert value["outcome"] in {
            task.DEFERRED,
            task.REPAIR_FAILED,
            task.BLOCKED,
        }


def test_activation_entities_are_exact_and_never_backfilled() -> None:
    value = manifest()
    trials = rows("validation_trial_record.csv")
    observations = rows("validation_observation_record.csv")
    initializations = rows("portfolio_initialization_record.csv")
    if value["outcome"] == task.ACTIVATED:
        assert len(trials) == len(observations) == len(initializations) == 1
        assert trials[0]["trial_id"] == task.TRIAL_ID
        assert trials[0]["parent_trial_id"] == task.PARENT_TRIAL_ID
        assert trials[0]["status"] == "active_prospective_validation"
        assert observations[0]["validation_observation_id"] == (
            task.OBSERVATION_ID
        )
        assert observations[0]["elapsed_completed_months"] == "0"
        assert observations[0]["completed_defensive_episodes"] == "0"
        assert observations[0]["historical_backfill"] == "prohibited"
        assert initializations[0]["record_type"] == (
            "prospective_initialization_not_performance"
        )
        assert initializations[0]["initialization_creates_return"] == "false"
        assert (
            initializations[0]["completed_validation_performance_rows"] == "0"
        )
    else:
        assert trials == observations == initializations == []
    assert value["completed_validation_performance_rows"] == 0
    assert value["paper_demo_observations_created"] == 0
    assert value["broker_or_paper_orders"] == 0


def test_initialized_portfolios_are_nonnegative_and_fully_invested() -> None:
    value = manifest()
    comparators = rows("comparator_state_initialization.csv")
    if value["outcome"] != task.ACTIVATED:
        return
    portfolio_rows = [
        row for row in comparators if row["portfolio_id"] in task.PORTFOLIO_IDS
    ]
    assert len(portfolio_rows) == len(task.PORTFOLIO_IDS)
    assert {row["status"] for row in portfolio_rows} == {"pass"}
    assert {row["nonnegative_weights"] for row in portfolio_rows} == {"true"}
    assert all(abs(float(row["weight_sum"]) - 1.0) <= 1e-12 for row in portfolio_rows)
    assert all(
        abs(float(row["gross_exposure"]) - 1.0) <= 1e-12
        for row in portfolio_rows
    )


def test_boundary_is_strictly_prospective_when_activated() -> None:
    value = manifest()
    boundary = rows("activation_boundary.csv")
    assert len(boundary) == 1
    if value["outcome"] == task.ACTIVATED:
        assert boundary[0]["boundary_status"] == "pass"
        assert boundary[0]["valid_US_regular_session"] == "true"
        assert boundary[0]["strictly_after_task_completion"] == "true"
        assert (
            boundary[0]["strictly_after_all_initialization_snapshots"] == "true"
        )
        assert (
            boundary[0]["strictly_after_latest_completed_signal_date"] == "true"
        )
        assert boundary[0]["historical_execution_created"] == "false"
        assert boundary[0]["start_selected_from_market_conditions"] == "false"


def test_consistency_proves_no_protected_or_lifecycle_change() -> None:
    check = payload("consistency_check.json")
    assert check["overall_pass"] is True
    assert check["phase_a_no_network_gate_passed"] is True
    assert check["original_alias_failure_reproduced"] is True
    assert check["reference_import_contract_passed"] is True
    assert check["offline_full_activation_dry_run_passed"] is True
    assert check["provider_response_evidence_durable"] is True
    assert check["protected_state_unchanged"] is True
    assert check["historical_canonical_caches_unchanged"] is True
    assert check["prior_PSAR_evidence_unchanged"] is True
    assert check["historical_validation_performance_calculated"] is False
    assert check["historical_backfill_performed"] is False
    assert check["authoritative_lifecycle_state_changed"] is False
    assert check["order_endpoint_called"] is False
    assert check["broker_submission"] is False
    assert check["paper_order_submission"] is False
    assert check["real_money_authorization"] is False


def test_normalized_frames_remain_ordered_unique_and_finite() -> None:
    value = manifest()
    if value["outcome"] != task.ACTIVATED:
        return
    complete = [
        row
        for row in rows("raw_retrieval_manifest.csv")
        if row["record_type"] == "complete_normalized_frame"
        and row["retrieval_id"] == "1"
    ]
    assert len(complete) >= len(task.SYMBOLS)
    selected: dict[str, dict[str, str]] = {}
    for row in complete:
        selected.setdefault(row["symbol"], row)
    assert set(selected) == set(task.SYMBOLS)
    for symbol, row in selected.items():
        frame = pd.read_csv(task.ROOT / row["normalized_path"])
        dates = pd.to_datetime(frame["trading_date"])
        assert dates.is_monotonic_increasing
        assert dates.is_unique
        assert (frame[["adjusted_open", "adjusted_high", "adjusted_low", "adjusted_close"]] > 0).all().all()
        assert (frame["adjusted_volume"] >= 0).all()
        assert (frame["adjusted_high"] >= frame[["adjusted_open", "adjusted_close", "adjusted_low"]].max(axis=1)).all(), symbol
        assert (frame["adjusted_low"] <= frame[["adjusted_open", "adjusted_close", "adjusted_high"]].min(axis=1)).all(), symbol
