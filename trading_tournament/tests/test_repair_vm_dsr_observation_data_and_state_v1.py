from __future__ import annotations

import csv
import json
from pathlib import Path

import yaml

from strategy_lab.research_os.research import repair_vm_dsr_observation_data_and_state_v1 as repair


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "repair_vm_dsr_observation_data_and_state_v1" / "latest"
PRIOR = ROOT / "evidence" / "current_paper_forward_update_and_reconciliation_v1" / "latest"


def read_json(name: str) -> dict[str, object]:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def read_csv(name: str) -> list[dict[str, str]]:
    with (EVIDENCE / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_required_artifacts_exist() -> None:
    required = {
        "repair_manifest.json",
        "prior_blocked_packet_hashes.json",
        "authoritative_state_source_inventory.csv",
        "vm_state_recovery.json",
        "dsr_state_recovery.json",
        "state_recovery_lineage.csv",
        "authorized_symbol_universe.json",
        "observation_data_refresh_manifest.csv",
        "provider_requests_and_results.csv",
        "observation_snapshot_hashes.csv",
        "component_state_before.csv",
        "component_daily_update_ledger.csv",
        "component_state_after.csv",
        "independent_commit_verification.csv",
        "active_combo_reference_update.csv",
        "complete_common_date_resolution.csv",
        "derived_combo_daily_ledger.csv",
        "derived_combo_monthly_rebalance.csv",
        "missing_and_stale_dates.csv",
        "research_cache_and_evidence_immutability.json",
        "broker_and_order_safety_check.json",
        "operational_outcome.json",
        "source_of_truth_changes.csv",
        "repair_summary.md",
        "consistency_check.json",
    }
    assert sorted(name for name in required if not (EVIDENCE / name).exists()) == []


def test_previous_blocked_packet_remains_byte_identical() -> None:
    hashes = read_json("prior_blocked_packet_hashes.json")
    assert hashes["byte_identical"] is True
    assert hashes["hashes_before"] == hashes["hashes_after"]
    assert set(hashes["hashes_before"]) == {str(path.relative_to(ROOT)).replace("\\", "/") for path in PRIOR.iterdir() if path.is_file()}


def test_state_recovery_follows_frozen_source_hierarchy() -> None:
    lineage = read_csv("state_recovery_lineage.csv")
    by_id = {row["observation_id"]: row for row in lineage}
    assert by_id[repair.VM_ID]["hierarchy_result"] == "blocked_at_all_levels"
    assert by_id[repair.DSR_ID]["hierarchy_result"] == "blocked_at_all_levels"
    assert by_id[repair.USCI_ID]["hierarchy_result"] == "activation_initialization_record_used"
    assert by_id[repair.VM_ID]["option_4_used"] == "False"
    assert by_id[repair.DSR_ID]["option_4_used"] == "False"


def test_vm_dsr_capital_and_holdings_are_not_invented() -> None:
    vm = read_json("vm_state_recovery.json")
    dsr = read_json("dsr_state_recovery.json")
    for payload in [vm, dsr]:
        assert payload["authoritative_state_recovered"] is False
        assert "initial_virtual_capital" in payload["blocking_fields_missing"]
        assert "actual_current_holdings_or_target_allocation" in payload["blocking_fields_missing"]
        assert "derived_combo_1000_dollar_sleeve" in payload["not_used_as_baseline"]


def test_missing_authoritative_baseline_produces_blocked_outcome() -> None:
    outcome = read_json("operational_outcome.json")
    assert outcome["outcome"] == "observation_state_recovery_blocked"
    assert outcome["vm_state_recovery_status"] == "blocked"
    assert outcome["dsr_state_recovery_status"] == "blocked"


def test_only_frozen_active_observation_symbols_may_be_refreshed() -> None:
    universe = read_json("authorized_symbol_universe.json")
    assert universe["authorized_symbols"] == repair.AUTHORIZED_SYMBOLS
    assert universe["unauthorized_symbols_refreshed"] == []
    refresh = read_csv("observation_data_refresh_manifest.csv")
    assert {row["symbol"] for row in refresh} == set(repair.AUTHORIZED_SYMBOLS)
    assert all(row["authorized"] == "True" for row in refresh)


def test_valid_current_snapshots_are_not_refreshed() -> None:
    rows = {row["symbol"]: row for row in read_csv("observation_data_refresh_manifest.csv")}
    assert rows["USCI"]["refresh_status"] == "valid_current_snapshot_reused_without_refresh"
    assert rows["DBC"]["refresh_status"] == "valid_current_snapshot_reused_without_refresh"
    assert rows["USCI"]["refresh_requested"] == "False"


def test_historical_research_caches_are_not_modified() -> None:
    immutable = read_json("research_cache_and_evidence_immutability.json")
    assert immutable["research_caches_unchanged"] is True
    assert immutable["research_cache_hashes_before"] == immutable["research_cache_hashes_after"]
    assert immutable["historical_evidence_unchanged"] is True


def test_independent_components_commit_independently() -> None:
    rows = {row["observation_id"]: row for row in read_csv("independent_commit_verification.csv")}
    assert rows[repair.USCI_ID]["committed_independently"] == "True"
    assert rows[repair.USCI_ID]["blocked_by_other_components"] == "False"
    assert rows[repair.VM_ID]["commit_status"] == "state_recovery_blocked"
    assert rows[repair.DSR_ID]["commit_status"] == "state_recovery_blocked"


def test_usci_commits_even_when_vm_or_dsr_remains_blocked() -> None:
    state_after = {row["observation_id"]: row for row in read_csv("component_state_after.csv")}
    assert state_after[repair.USCI_ID]["commit_status"] == "committed_independent_forward_update"
    assert state_after[repair.USCI_ID]["latest_committed_observation_date"] == "2026-07-01"
    obs = yaml.safe_load((ROOT / "paper_forward_observations" / repair.USCI_ID / "active_observation.yaml").read_text(encoding="utf-8"))
    assert obs["latest_committed_observation_date"] == "2026-07-01"
    assert obs["latest_committed_forward_sessions"] == 8


def test_component_updates_start_from_prior_authoritative_state() -> None:
    before = {row["observation_id"]: row for row in read_csv("component_state_before.csv")}
    assert before[repair.VM_ID]["baseline_status"] == "blocked_missing_authoritative_state"
    assert before[repair.DSR_ID]["baseline_status"] == "blocked_missing_authoritative_state"
    assert before[repair.USCI_ID]["baseline_status"] == "available"


def test_component_sessions_are_processed_sequentially() -> None:
    rows = [row for row in read_csv("component_daily_update_ledger.csv") if row["component_observation_id"] == repair.USCI_ID]
    assert len(rows) == 8
    assert [int(row["session_sequence"]) for row in rows] == list(range(1, 9))
    assert rows[0]["date"] == "2026-06-22"
    assert rows[-1]["date"] == "2026-07-01"


def test_missing_data_are_not_zero_filled_or_forward_filled() -> None:
    missing = read_csv("missing_and_stale_dates.csv")
    assert missing
    assert all(row["action"] == "do_not_fill_do_not_advance_derived" for row in missing)
    consistency = read_json("consistency_check.json")
    assert consistency["missing_data_not_zero_filled"] is True
    assert consistency["missing_data_not_forward_filled"] is True


def test_active_combo_remains_reference_only() -> None:
    row = read_csv("active_combo_reference_update.csv")[0]
    assert row["benchmark_id"] == repair.ACTIVE_COMBO_ID
    assert row["role"] == "benchmark_reference_only"
    assert row["updated"] == "False"
    assert row["definition_changed"] == "False"


def test_derived_combo_advances_only_on_complete_common_dates() -> None:
    rows = read_csv("complete_common_date_resolution.csv")
    assert all(row["derived_combo_can_advance"] == "False" for row in rows)
    assert any(row["usci_complete"] == "True" and row["vm_complete"] == "False" for row in rows)


def test_constant_daily_one_third_averaging_is_prohibited() -> None:
    row = read_csv("derived_combo_daily_ledger.csv")[0]
    assert row["constant_one_third_daily_averaging_used"] == "False"
    assert read_json("consistency_check.json")["constant_daily_one_third_averaging_prohibited"] is True


def test_july_rebalance_occurs_at_most_once() -> None:
    row = read_csv("derived_combo_monthly_rebalance.csv")[0]
    assert row["month"] == "2026-07"
    assert row["rebalance_processed"] == "False"
    assert row["times_processed"] == "0"


def test_rebalance_turnover_uses_actual_pre_rebalance_sleeves() -> None:
    consistency = read_json("consistency_check.json")
    assert consistency["rebalance_turnover_uses_actual_pre_rebalance_sleeves"] is True


def test_component_costs_are_not_reapplied() -> None:
    consistency = read_json("consistency_check.json")
    assert consistency["component_costs_not_reapplied"] is True


def test_portfolio_transfer_costs_are_applied_once() -> None:
    row = read_csv("derived_combo_monthly_rebalance.csv")[0]
    assert float(row["portfolio_transfer_cost"]) == 0.0
    assert read_json("consistency_check.json")["portfolio_transfer_cost_applied_once"] is True


def test_component_capital_is_not_reduced_to_fund_derived_observation() -> None:
    consistency = read_json("consistency_check.json")
    derived = read_csv("derived_combo_daily_ledger.csv")[0]
    assert float(derived["derived_total_equity"]) == 3000.0
    assert consistency["component_capital_not_reduced_for_derived_observation"] is True


def test_no_broker_api_or_orders() -> None:
    safety = read_json("broker_and_order_safety_check.json")
    assert safety["broker_api_called"] is False
    assert safety["paper_orders_created"] is False
    assert safety["live_orders"] is False


def test_no_real_money_flag_becomes_true() -> None:
    safety = read_json("broker_and_order_safety_check.json")
    manifest = read_json("repair_manifest.json")
    assert safety["real_money_recommendation"] is False
    assert manifest["real_money_recommendation"] is False


def test_aggregate_exposure_remains_at_or_below_one() -> None:
    assert read_json("consistency_check.json")["aggregate_exposure_lte_1"] is True


def test_rerunning_with_unchanged_provider_snapshots_is_idempotent() -> None:
    before_outcome = read_json("operational_outcome.json")["outcome"]
    before_usci_date = yaml.safe_load((ROOT / "paper_forward_observations" / repair.USCI_ID / "active_observation.yaml").read_text(encoding="utf-8"))["latest_committed_observation_date"]
    after_usci_date = yaml.safe_load((ROOT / "paper_forward_observations" / repair.USCI_ID / "active_observation.yaml").read_text(encoding="utf-8"))["latest_committed_observation_date"]
    assert before_outcome == "observation_state_recovery_blocked"
    assert after_usci_date == before_usci_date == "2026-07-01"
    assert read_json("consistency_check.json")["rerun_with_unchanged_snapshots_idempotent"] is True


def test_generation_guardrails() -> None:
    manifest = read_json("repair_manifest.json")
    assert manifest["historical_backtest_run"] is False
    assert manifest["strategy_redesign"] is False
    assert manifest["performance_review_decision"] is False
    assert manifest["source_discovery_task"] is False
    assert manifest["provider_download"] is False
    assert manifest["broker_api_called"] is False
    assert manifest["paper_orders_created"] is False
    assert manifest["live_orders"] is False
    assert manifest["next_action"] == repair.NEXT_ACTION
