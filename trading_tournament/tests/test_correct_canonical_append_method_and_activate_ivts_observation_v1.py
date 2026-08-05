from __future__ import annotations

import csv
import json

import pandas as pd
import yaml

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.research import (
    correct_canonical_append_method_and_activate_ivts_observation_v1 as task,
)


OUTPUT = ROOT / "evidence" / "correction" / task.TASK_ID / "latest"


def rows(name: str) -> list[dict[str, str]]:
    with (OUTPUT / name).open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def check() -> dict:
    return json.loads((OUTPUT / "consistency_check.json").read_text(encoding="utf-8"))


def test_exact_captured_batch_reused_without_market_provider_download() -> None:
    reconciliation = rows("captured_provider_hash_reconciliation.csv")
    assert len(reconciliation) == 18
    assert {row["symbol"] for row in reconciliation} == set(task.EXPECTED_RAW_HASHES)
    assert all(row["actual_row_count"] == "29" for row in reconciliation)
    assert all(row["hash_reconciliation_pass"] == "true" for row in reconciliation)
    assert all(row["provider_download_called_in_correction"] == "false" for row in reconciliation)
    assert check()["market_data_provider_downloads"] == 0


def test_historical_bytes_are_preserved_and_failed_gate_writes_no_cache() -> None:
    bridge = rows("bridge_factor_reconciliation.csv")
    assert len(bridge) == 18
    assert all(row["historical_rows_rewritten"] == "false" for row in bridge)
    assert all(row["historical_byte_prefix_unchanged"] == "true" for row in bridge)
    assert all(row["fixed_bridge_for_complete_appended_segment"] == "true" for row in bridge)
    assert all(row["status"] == "pass" for row in bridge)
    atomic = rows("atomic_cache_update_manifest.csv")
    assert len(atomic) == 18
    assert all(row["atomic_transaction_committed"] == "false" for row in atomic)
    assert all(row["cache_updated"] == "false" for row in atomic)
    assert all(row["metadata_updated"] == "false" for row in atomic)
    before_after = rows("proposed_canonical_before_after.csv")
    assert all(row["before_file_hash"] == row["after_file_hash"] for row in before_after)
    assert all(row["before_row_count"] == row["after_row_count"] for row in before_after)
    assert all(row["before_last_date"] == row["after_last_date"] for row in before_after)
    metadata = rows("acquisition_metadata_before_after.csv")
    assert all(row["before_hash"] == row["after_hash"] for row in metadata)
    assert all(row["metadata_updated"] == "false" for row in metadata)


def test_provider_adjusted_returns_are_preserved_exactly() -> None:
    returns = rows("appended_return_reconciliation.csv")
    assert returns
    assert all(row["return_reconciliation_pass"] == "true" for row in returns)
    assert max(abs(float(row["difference"])) for row in returns) <= 1e-10
    assert all(row["dividend_cash_added_separately"] == "false" for row in returns)
    assert all(row["stale_price_forward_filled"] == "false" for row in returns)


def test_named_distributions_explain_adjustment_boundaries() -> None:
    actions = rows("corporate_action_reconciliation.csv")
    for symbol, action_date in task.NAMED_ACTIONS.items():
        matches = [
            row
            for row in actions
            if row["symbol"] == symbol and row["action_date"] == action_date.isoformat()
        ]
        assert len(matches) == 1
        assert matches[0]["named_required_reconciliation"] == "true"
        assert matches[0]["reconciliation_status"] == "pass"
        assert abs(float(matches[0]["return_difference"])) <= task.ACTION_RETURN_TOLERANCE
    assert all(row["separate_dividend_cash_added"] == "false" for row in actions)
    failed = {
        (row["symbol"], row["action_date"])
        for row in actions
        if row["reconciliation_status"] == "fail"
    }
    assert failed == {("XLC", "2026-06-22"), ("XLE", "2026-06-22")}


def test_overlap_classification_surfaces_unexplained_raw_price_mismatch() -> None:
    discrepancies = rows("overlap_discrepancy_classification.csv")
    assert discrepancies
    allowed = {
        "exact_match",
        "stable_backward_adjustment_revision",
        "corporate_action_boundary_revision",
        "raw_price_revision_within_tolerance",
        "volume_revision_nonblocking",
        "unexplained_raw_price_mismatch",
    }
    assert {row["classification"] for row in discrepancies} <= allowed
    blocking = [row for row in discrepancies if row["blocking"] == "true"]
    assert len(blocking) == 1
    assert blocking[0]["symbol"] == "USCI"
    assert blocking[0]["date"] == "2026-07-01"
    assert blocking[0]["field_group"] == "raw_ohlc"
    assert blocking[0]["classification"] == "unexplained_raw_price_mismatch"
    assert float(blocking[0]["relative_difference"]) > task.RAW_OHLC_TOLERANCE


def test_volume_is_nonblocking_and_unused_by_reference_rules() -> None:
    volume = rows("volume_boundary_assessment.csv")
    assert len(volume) == 3
    assert all(row["volume_used_by_frozen_rule"] == "false" for row in volume)
    assert all(row["immutable_pre_anchor_volume_preserved"] == "true" for row in volume)
    assert all(row["assessment_status"] == "pass" for row in volume)


def test_existing_canonical_caches_remain_valid_and_unchanged() -> None:
    before_after = {row["symbol"]: row for row in rows("proposed_canonical_before_after.csv")}
    for symbol in task.required_symbols():
        frame = pd.read_csv(task.cache_path(symbol))
        assert tuple(frame.columns) == task.CANONICAL_COLUMNS
        dates = pd.to_datetime(frame["date"])
        assert dates.is_monotonic_increasing
        assert not dates.duplicated().any()
        assert dates.iloc[-1].strftime("%Y-%m-%d") == before_after[symbol][
            "before_last_date"
        ]
        prices = frame[["open", "high", "low", "close", "adj_close"]].astype(float)
        assert (prices > 0.0).all().all()
        assert (prices["high"] >= prices[["open", "close"]].max(axis=1) - 1e-10).all()
        assert (prices["low"] <= prices[["open", "close"]].min(axis=1) + 1e-10).all()


def test_failed_data_gate_creates_no_initialization_or_performance_rows() -> None:
    reference = rows("frozen_reference_initialization_state.csv")
    assert reference == []
    initialization = rows("portfolio_initialization_record.csv")
    assert initialization == []
    assert check()["completed_forward_performance_rows"] == 0
    assert check()["official_cboe_requests"] == 0


def test_exact_existing_observation_remains_deferred_without_duplicate() -> None:
    payload = yaml.safe_load(task.ACTIVE_OBSERVATIONS_PATH.read_text(encoding="utf-8"))
    matches = task.prior.matching_observation(payload)
    assert len(matches) == 1
    observation = matches[0]
    assert observation["stage"] == "deferred"
    assert observation["paper_forward_active"] is False
    assert observation["initialization_status"] == "not_initialized_deferred"
    assert observation["historical_forward_records_created"] == 0
    assert observation["forward_records_created"] == 0
    assert observation["standalone_eligible"] is False
    assert observation["broker_submission"] is False
    assert observation["paper_orders"] is False
    assert observation["live_orders"] is False
    assert observation["real_money_authorized"] is False
    diffs = rows("paper_demo_observation_before_after.csv")
    assert all(row["changed"] == "false" for row in diffs)


def test_protected_state_entity_counts_and_consistency() -> None:
    consistency = check()
    assert consistency["outcome"] == task.DEFERRED_OUTCOME
    assert consistency["failure_reason"] == "unexplained_canonical_data_mismatch"
    assert consistency["exact_next_action"] == task.DEFERRED_NEXT_ACTION
    assert consistency["canonical_caches_updated"] == 0
    assert consistency["official_cboe_requests"] == 0
    assert consistency["state_written"] is False
    assert consistency["registry_unchanged"] is True
    assert consistency["prior_evidence_unchanged"] is True
    assert consistency["unrelated_cache_unchanged"] is True
    assert consistency["other_observations_unchanged"] is True
    assert consistency["roadmap_unchanged"] is True
    assert consistency["research_queue_unchanged"] is True
    assert consistency["family_ledger_unchanged"] is True
    assert consistency["strategies_created"] == 0
    assert consistency["strategies_updated"] == 0
    assert consistency["experiment_trials_created"] == 0
    assert consistency["observations_created"] == 0
    assert consistency["historical_backtest_run"] is False
    assert consistency["validation_rerun"] is False
    assert consistency["broker_orders"] == 0
    assert consistency["paper_orders"] == 0
    assert consistency["live_orders"] == 0
    assert consistency["real_money_actions"] == 0
    assert consistency["activation_gates"][
        "captured_provider_hashes_and_rows_reconcile"
    ]
    assert not consistency["activation_gates"][
        "overlap_discrepancies_classified_without_blocker"
    ]
    assert not consistency["activation_gates"][
        "named_and_all_corporate_actions_reconcile"
    ]
    assert consistency["blocking_reconciliation_details"] == [
        "USCI:2026-07-01:raw_ohlc:unexplained_raw_price_mismatch",
        "XLC:2026-06-22:corporate_action:unexplained_corporate_action_mismatch",
        "XLE:2026-06-22:corporate_action:unexplained_corporate_action_mismatch",
    ]
    assert consistency["overall_pass"] is True
