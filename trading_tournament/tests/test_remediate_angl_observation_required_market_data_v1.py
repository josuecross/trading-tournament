from __future__ import annotations

import csv
import json
from pathlib import Path

import pandas as pd
import pytest
import yaml

from strategy_lab.research_os.research import (
    remediate_angl_observation_required_market_data_v1 as task,
)


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "data_capability" / task.TASK_ID / "latest"


@pytest.fixture(scope="module", autouse=True)
def evidence_ready() -> None:
    assert (EVIDENCE / "consistency_check.json").exists(), (
        "Run the dedicated serial remediation runner before focused tests."
    )


def rows(name: str) -> list[dict[str, str]]:
    with (EVIDENCE / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def payload(name: str) -> dict[str, object]:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def test_required_packet_and_exact_entity_counts() -> None:
    required = {
        "remediation_manifest.yaml",
        "strategy_cards.csv",
        "trial_ledger.csv",
        "paper_demo_observations.csv",
        "data_capability_task_log.csv",
        "process_task_log.csv",
        "provider_failure_root_cause.csv",
        "per_symbol_refresh_results.csv",
        "data_source_manifest.csv",
        "data_coverage.csv",
        "data_integrity_checks.csv",
        "overlap_history_reconciliation.csv",
        "cache_reload_reconciliation.csv",
        "reference_input_sufficiency.csv",
        "common_session_sufficiency.csv",
        "state_change_manifest.csv",
        "outcome_summary.csv",
        "failure_reasons.csv",
        "next_actions.csv",
        "consistency_check.json",
        "remediation_report.md",
    }
    assert required.issubset({path.name for path in EVIDENCE.iterdir()})
    manifest = yaml.safe_load((EVIDENCE / "remediation_manifest.yaml").read_text(encoding="utf-8"))
    assert manifest["strategy_configurations_created"] == 0
    assert manifest["experiment_trials_created"] == 0
    assert manifest["observations_created"] == 0
    assert manifest["observations_activated"] == 0
    assert manifest["data_capability_tasks"] == 20
    assert manifest["process_tasks"] == 1


def test_exact_20_symbols_processed_once_and_independently() -> None:
    refresh = rows("per_symbol_refresh_results.csv")
    tasks = rows("data_capability_task_log.csv")
    assert len(refresh) == len(tasks) == 20
    assert tuple(row["symbol"] for row in refresh) == task.TARGET_SYMBOLS
    assert tuple(row["symbol"] for row in tasks) == task.TARGET_SYMBOLS
    assert {row["attempt_count"] for row in refresh} == {"1"}
    assert {row["provider_attempted"] for row in refresh} == {task.PROVIDER_ID}
    assert {row["alpaca_attempted"] for row in refresh} == {"false"}
    assert {row["entity_type"] for row in tasks} == {"data_capability_task"}
    assert {row["adaptation_label"] for row in tasks} == {task.ADAPTATION_LABEL}
    assert {row["stage"] for row in tasks}.issubset({"feasible", "blocked"})
    assert {row["counted_as_strategy_trial_or_observation"] for row in tasks} == {"false"}


def test_provider_root_cause_and_single_supported_path_are_explicit() -> None:
    root_cause = rows("provider_failure_root_cause.csv")
    assert len(root_cause) == 1
    assert root_cause[0]["prior_call_shape"] == "one_20_symbol_batch"
    assert root_cause[0]["remediation"] == (
        "one existing-provider request and isolated staged transaction per symbol"
    )
    assert root_cause[0]["alpaca_retried"] == "false"
    source = rows("data_source_manifest.csv")
    assert len(source) == 20
    assert {row["provider_path"] for row in source} == {"src.data._download_yfinance"}
    assert {row["canonical_builder"] for row in source} == {"src.data.build_adjusted_ohlc"}
    assert {row["normal_reload_interface"] for row in source} == {"src.data.load_symbol_data"}
    assert {row["provider_attempt_count"] for row in source} == {"1"}


def test_adjustment_rebuild_is_explicit_and_raw_history_changes_are_rejected() -> None:
    dates = pd.date_range("2026-07-20", periods=3, freq="B")
    raw = pd.DataFrame(
        {
            "date": dates,
            "raw_open": [10.0, 11.0, 12.0],
            "raw_high": [10.5, 11.5, 12.5],
            "raw_low": [9.5, 10.5, 11.5],
            "raw_close": [10.0, 11.0, 12.0],
            "raw_adj_close": [10.0, 11.0, 12.0],
            "raw_volume": [100.0, 110.0, 120.0],
            "dividends": [0.0, 0.0, 0.0],
            "stock_splits": [0.0, 0.0, 0.0],
        }
    )
    old = task.build_adjusted_ohlc(raw, "ANGL")
    rebuilt_raw = raw.copy()
    rebuilt_raw.loc[0, "raw_adj_close"] = 9.0
    rebuilt_raw.loc[0, "dividends"] = 1.0
    rebuilt = task.build_adjusted_ohlc(rebuilt_raw, "ANGL")
    accepted = task.overlap_reconciliation("ANGL", old, rebuilt)
    assert accepted["acceptable"] is True
    assert accepted["reconciliation_classification"] == "legitimate_adjustment_history_rebuild"
    assert accepted["raw_rows_changed"] == 0
    assert accepted["corporate_action_rows_changed"] == 1
    revised_raw = rebuilt_raw.copy()
    revised_raw.loc[0, "raw_close"] = 10.25
    revised = task.build_adjusted_ohlc(revised_raw, "ANGL")
    rejected = task.overlap_reconciliation("ANGL", old, revised)
    assert rejected["acceptable"] is False
    assert rejected["reconciliation_classification"] == "provider_history_revision_requires_rejection"


def test_feasible_symbols_pass_integrity_overlap_and_normal_reload() -> None:
    refresh = {row["symbol"]: row for row in rows("per_symbol_refresh_results.csv")}
    integrity = rows("data_integrity_checks.csv")
    overlap = {row["symbol"]: row for row in rows("overlap_history_reconciliation.csv")}
    reloads = {row["symbol"]: row for row in rows("cache_reload_reconciliation.csv")}
    for symbol, result in refresh.items():
        symbol_checks = [row for row in integrity if row["symbol"] == symbol]
        if result["stage"] == "feasible":
            assert symbol_checks
            assert {row["status"] for row in symbol_checks} == {"pass"}
            assert overlap[symbol]["acceptable"] == "true"
            assert reloads[symbol]["reload_pass"] == "true"
            assert reloads[symbol]["staged_and_reloaded_hashes_match"] == "true"
            assert result["failure_reason"] == ""
        else:
            assert result["cache_before_hash"] == result["cache_after_hash"]
            assert result["failure_reason"] in {
                "data_unavailable",
                "capability_missing",
                "data_or_comparability_failure",
                "methodology_failure",
            }


def test_common_session_and_reference_sufficiency_are_data_only() -> None:
    common = rows("common_session_sufficiency.csv")
    reference = rows("reference_input_sufficiency.csv")
    assert len(common) == 1
    assert common[0]["required_session"] == "2026-07-24"
    assert common[0]["strategy_performance_calculated"] == "false"
    assert common[0]["virtual_position_trade_or_nav_created"] == "false"
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


def test_strategy_trials_and_observation_are_read_only() -> None:
    strategy = rows("strategy_cards.csv")
    trials = rows("trial_ledger.csv")
    observations = rows("paper_demo_observations.csv")
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
    assert len(observations) == 1
    assert observations[0]["observation_id"] == task.OBSERVATION_ID
    assert observations[0]["stage"] == "blocked"
    assert observations[0]["outcome"] == "observation_invalid_or_incomplete"
    assert observations[0]["failure_reason"] == "data_unavailable"
    assert observations[0]["activated_in_this_task"] == "false"
    assert observations[0]["forward_record_created"] == "false"
    assert len(process) == 1
    assert process[0]["entity_type"] == "process_task"
    assert process[0]["stage"] == "feasibility"


def test_state_reconciliation_and_guardrails_pass() -> None:
    state = rows("state_change_manifest.csv")
    protected = [
        row for row in state if row["path_type"] == "protected_state_or_operational_observation"
    ]
    assert protected
    assert {row["changed"] for row in protected} == {"false"}
    assert all(row["change_permitted"] == "true" or row["changed"] == "false" for row in state)
    consistency = payload("consistency_check.json")
    assert consistency["consistency_passed"] is True
    assert consistency["exactly_20_symbols_processed"] is True
    assert consistency["one_attempt_per_symbol"] is True
    assert consistency["exactly_one_existing_provider_path_used"] is True
    assert consistency["alpaca_retried"] is False
    assert consistency["blocked_symbol_prior_cache_preserved"] is True
    assert consistency["protected_state_hashes_unchanged"] is True
    assert consistency["prior_evidence_hashes_unchanged"] is True
    assert consistency["unrelated_cache_hashes_unchanged"] is True
    assert consistency["unexpected_changes"] == []
    assert consistency["strategy_performance_calculated"] is False
    assert consistency["virtual_positions_trades_or_nav_created"] is False
    assert consistency["broker_account_position_order_endpoint_called"] is False
    assert consistency["paper_or_live_order_submitted"] is False
    assert consistency["real_money_action"] is False


def test_outcome_and_next_actions_follow_only_data_sufficiency() -> None:
    outcome = rows("outcome_summary.csv")[0]
    next_actions = {row["action_scope"]: row for row in rows("next_actions.csv")}
    assert outcome["data_outcome"] in {task.OUTCOME_READY, task.OUTCOME_BLOCKED}
    if outcome["symbols_blocked"] == "0":
        assert outcome["data_outcome"] == task.OUTCOME_READY
        assert outcome["observation_next_action"] == task.NEXT_READY
    else:
        assert outcome["data_outcome"] == task.OUTCOME_BLOCKED
        assert outcome["observation_next_action"] == task.NEXT_BLOCKED
    assert outcome["project_discovery_next_action"] == task.PROJECT_NEXT_ACTION
    assert next_actions["ANGL_observation"]["execute_in_this_task"] == "false"
    assert next_actions["separate_project_discovery"]["exact_next_action"] == task.PROJECT_NEXT_ACTION
    assert next_actions["separate_project_discovery"]["execute_in_this_task"] == "false"
