from __future__ import annotations

import csv
import json
from pathlib import Path

import yaml

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.research import (
    refresh_ivts_activation_data_and_activate_forward_observation_v1 as task,
)


OUTPUT = ROOT / "evidence" / "paper_demo" / task.TASK_ID / "latest"


def rows(name: str) -> list[dict[str, str]]:
    with (OUTPUT / name).open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def consistency() -> dict:
    return json.loads((OUTPUT / "consistency_check.json").read_text(encoding="utf-8"))


def test_exact_frozen_symbol_scope_and_no_substitution() -> None:
    scope = rows("required_symbol_scope.csv")
    expected = set(task.frozen_reference_symbols()) | {"IEF"}
    assert {row["symbol"] for row in scope} == expected
    assert len(scope) == 18
    assert all(row["frozen_before_retrieval"] == "true" for row in scope)
    assert all(row["performance_selected"] == "false" for row in scope)
    assert all(row["substitution_allowed"] == "false" for row in scope)


def test_one_approved_provider_batch_and_alpaca_schema_decision() -> None:
    provider = rows("provider_attempt_log.csv")
    attempted = [row for row in provider if row["attempted"] == "true"]
    assert len(attempted) == 1
    assert attempted[0]["bounded_batch_attempts"] == "1"
    alpaca = next(row for row in provider if row["provider_id"] == "alpaca_market_data")
    assert alpaca["attempted"] == "false"
    assert "not_compatible" in alpaca["status"]
    assert all(row["order_endpoint_called"] == "false" for row in provider)


def test_overlap_failure_is_explicit_and_blocks_cache_admission() -> None:
    overlap = rows("overlap_reconciliation.csv")
    assert len(overlap) == 18 * 5
    failed = [row for row in overlap if row["overlap_pass"] == "false"]
    assert failed
    assert {"BIL", "IEF", "SPLV", "SPY", "USMV"} <= {
        row["symbol"] for row in failed
    }
    spy = [row for row in failed if row["symbol"] == "SPY"]
    assert spy
    assert all(row["bridge_ratio_stable"] == "false" for row in spy)
    assert all(row["material_ohlcv_discontinuity"] == "true" for row in spy)
    quality = rows("data_quality_results.csv")
    assert len(quality) == 18 * 10
    assert any(row["status"] == "fail" for row in quality)
    before_after = rows("canonical_data_before_after.csv")
    assert all(row["cache_changed"] == "false" for row in before_after)
    assert all(row["metadata_changed"] == "false" for row in before_after)


def test_reference_is_not_reconstructed_after_failed_market_gate() -> None:
    reference = rows("frozen_reference_initialization_state.csv")
    assert reference == []
    check = consistency()
    assert check["reference_state"]["status"] == "not_run"
    assert check["activation_gates"]["frozen_reference_current_targets"] is False


def test_no_signal_capture_is_used_after_failed_market_gate() -> None:
    manifest = rows("official_cboe_forward_snapshot_manifest.csv")
    assert manifest == []
    alignment = rows("signal_execution_alignment.csv")[0]
    assert alignment["signal_strictly_before_execution"] == "false"
    assert alignment["historical_or_synthetic_fill_required"] == "false"
    check = consistency()
    assert check["official_cboe_request_count"] == 0
    assert check["snapshot"] == {}


def test_failed_gate_creates_no_initialization_or_forward_performance() -> None:
    init = rows("portfolio_initialization_record.csv")
    assert init == []
    check = consistency()
    assert check["initialization"]["status"] == "not_created"
    assert check["initialization_records"] == 0
    assert check["completed_forward_performance_rows"] == 0


def test_exact_existing_observation_remains_deferred_without_duplicate() -> None:
    payload = yaml.safe_load(task.ACTIVE_OBSERVATIONS_PATH.read_text(encoding="utf-8"))
    matches = task.matching_observation(payload)
    assert len(matches) == 1
    observation = matches[0]
    assert observation["stage"] == "deferred"
    assert observation["state"] == "deferred_activation_boundary_not_ready"
    assert observation["paper_forward_active"] is False
    assert observation["outcome"] == task.DEFERRED_OUTCOME
    assert observation["failure_reason"] == "activation_boundary_not_ready"
    assert observation["historical_forward_records_created"] == 0
    assert observation["forward_records_created"] == 0
    assert observation["initialization_status"] == "not_initialized_deferred"
    assert observation["broker_submission"] is False
    assert observation["paper_orders"] is False
    assert observation["live_orders"] is False
    assert observation["real_money_authorized"] is False


def test_registry_prior_evidence_and_unrelated_state_are_unchanged() -> None:
    check = consistency()
    assert check["registry_unchanged"] is True
    assert check["prior_evidence_unchanged"] is True
    assert check["unrelated_cache_unchanged"] is True
    assert check["unrelated_observations_unchanged"] is True
    assert check["roadmap_unchanged"] is True
    assert check["research_queue_unchanged"] is True
    assert check["family_ledger_unchanged"] is True


def test_entity_counts_and_forbidden_actions_are_zero() -> None:
    check = consistency()
    assert check["strategy_configurations_created"] == 0
    assert check["strategy_configurations_updated"] == 0
    assert check["experiment_trials_created"] == 0
    assert check["paper_demo_observations_created"] == 0
    assert check["validation_rerun"] is False
    assert check["historical_backtest_run"] is False
    assert check["historical_forward_backfill"] is False
    assert check["broker_orders"] == 0
    assert check["paper_orders"] == 0
    assert check["live_orders"] == 0
    assert check["real_money_actions"] == 0


def test_output_generation_and_state_are_consistent() -> None:
    check = consistency()
    assert check["outcome"] == task.DEFERRED_OUTCOME
    assert check["failure_reason"] == "canonical_market_data_refresh_failed"
    assert check["exact_next_action"] == task.DEFERRED_NEXT_ACTION
    assert check["provider_batch_attempts"] == 1
    assert check["official_cboe_request_count"] == 0
    assert check["activation_gates"]["one_bounded_approved_provider_refresh"] is True
    assert check["activation_gates"]["five_session_overlap_reconciliation"] is False
    assert check["observation_state_written"] is False
    assert check["required_artifacts_present"] is True
    assert check["overall_pass"] is True
