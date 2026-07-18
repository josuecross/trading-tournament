from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest
import yaml

from strategy_lab.research_os.research import forward_operational_reinitialization_vm_dsr_combo_v1 as reinit


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "forward_operational_reinitialization_vm_dsr_combo_v1" / "latest"
REPAIR = ROOT / "evidence" / "repair_vm_dsr_observation_data_and_state_v1" / "latest"


def read_json(name: str) -> dict[str, object]:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def read_csv(name: str) -> list[dict[str, str]]:
    with (EVIDENCE / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def obs_yaml(observation_id: str) -> dict[str, object]:
    return yaml.safe_load((ROOT / "paper_forward_observations" / observation_id / "active_observation.yaml").read_text(encoding="utf-8"))


@pytest.fixture(scope="module", autouse=True)
def generated_reinitialization_packet() -> dict[str, object]:
    return reinit.run()


def test_required_artifacts_exist() -> None:
    required = {
        "reinitialization_manifest.json",
        "direction_owner_reinitialization_decision.json",
        "prior_repair_packet_hashes.json",
        "historical_recovery_exhaustion_record.json",
        "authorized_symbol_universe.json",
        "observation_data_refresh_manifest.csv",
        "provider_requests_and_results.csv",
        "operational_snapshot_hashes.csv",
        "frozen_t0_derivation.csv",
        "vm_frozen_rule_verification.json",
        "dsr_frozen_rule_verification.json",
        "vm_initial_target_derivation.csv",
        "dsr_initial_target_derivation.csv",
        "vm_operational_initialization.json",
        "dsr_operational_initialization.json",
        "vm_component_forward_ledger.csv",
        "dsr_component_forward_ledger.csv",
        "usci_state_preservation_and_update.json",
        "active_combo_forward_reference_rebaseline.json",
        "derived_combo_operational_reinitialization.json",
        "derived_combo_component_index_baselines.csv",
        "continuity_and_unobserved_period_disclosure.json",
        "protected_state_verification.json",
        "research_cache_and_evidence_immutability.json",
        "broker_and_order_safety_check.json",
        "source_of_truth_changes.csv",
        "operational_outcome.json",
        "reinitialization_summary.md",
        "consistency_check.json",
    }
    assert sorted(name for name in required if not (EVIDENCE / name).exists()) == []


def test_prior_repair_packet_remains_byte_identical() -> None:
    hashes = read_json("prior_repair_packet_hashes.json")
    assert hashes["byte_identical"] is True
    assert hashes["hashes_before"] == hashes["hashes_after"]
    assert set(hashes["hashes_before"]) == {path.relative_to(ROOT).as_posix() for path in REPAIR.iterdir() if path.is_file()}


def test_historical_recovery_is_not_attempted_again() -> None:
    manifest = read_json("reinitialization_manifest.json")
    exhaustion = read_json("historical_recovery_exhaustion_record.json")
    assert manifest["historical_recovery_attempted"] is False
    assert exhaustion["recovery_hierarchy_not_repeated"] is True


def test_no_missing_historical_baseline_is_fabricated() -> None:
    exhaustion = read_json("historical_recovery_exhaustion_record.json")
    continuity = read_json("continuity_and_unobserved_period_disclosure.json")
    assert exhaustion["no_missing_baseline_fabricated"] is True
    assert continuity["no_return_equity_drawdown_holdings_or_performance_claim_for_prior_interval"] is True


def test_prior_interval_is_explicitly_unobserved() -> None:
    continuity = read_json("continuity_and_unobserved_period_disclosure.json")
    assert continuity["vm_prior_interval_status"] == reinit.PRIOR_INTERVAL_STATUS
    assert continuity["dsr_prior_interval_status"] == reinit.PRIOR_INTERVAL_STATUS
    assert continuity["derived_prior_interval_status"] == reinit.PRIOR_INTERVAL_STATUS
    assert continuity["continuity_from_original_activation"] is False


def test_existing_observation_ids_are_retained() -> None:
    decision = read_json("direction_owner_reinitialization_decision.json")
    assert decision["retain_observation_ids"] == [reinit.VM_ID, reinit.DSR_ID, reinit.USCI_ID, reinit.DERIVED_ID]
    for observation_id in decision["retain_observation_ids"]:
        assert (ROOT / "paper_forward_observations" / observation_id / "active_observation.yaml").exists()


def test_no_duplicate_v2_observations_are_created() -> None:
    names = {path.name for path in (ROOT / "paper_forward_observations").iterdir() if path.is_dir()}
    assert not any(name.startswith(reinit.VM_ID + "_v2") for name in names)
    assert not any(name.startswith(reinit.DSR_ID + "_v2") for name in names)
    assert not any(name.startswith(reinit.DERIVED_ID + "_v2") for name in names)
    assert read_json("consistency_check.json")["no_duplicate_v2_observations_created"] is True


def test_only_authorized_symbols_are_refreshed() -> None:
    universe = read_json("authorized_symbol_universe.json")
    refresh = read_csv("observation_data_refresh_manifest.csv")
    assert universe["authorized_symbols"] == reinit.AUTHORIZED_SYMBOLS
    assert {row["symbol"] for row in refresh} == set(reinit.AUTHORIZED_SYMBOLS)
    assert universe["unauthorized_symbols_refreshed"] == []
    assert all(row["authorized"] == "true" for row in refresh)


def test_research_caches_and_research_evidence_remain_unchanged() -> None:
    immutable = read_json("research_cache_and_evidence_immutability.json")
    assert immutable["research_caches_unchanged"] is True
    assert immutable["historical_research_evidence_unchanged"] is True
    assert immutable["prior_repair_packet_unchanged"] is True


def test_t0_is_derived_deterministically_from_complete_current_data() -> None:
    manifest = read_json("reinitialization_manifest.json")
    rows = read_csv("frozen_t0_derivation.csv")
    assert manifest["t0"] == "2026-06-18"
    assert manifest["signal_date"] == "2026-06-17"
    assert {row["symbol"] for row in rows} == set(reinit.AUTHORIZED_SYMBOLS)
    assert all(row["included_in_t0_common_date"] == "true" for row in rows)
    assert all(row["t0_selection_rule"] == "latest_complete_common_session_across_authorized_operational_snapshots" for row in rows)


def test_vm_target_initialization_uses_frozen_rules_and_pre_execution_information() -> None:
    manifest = read_json("reinitialization_manifest.json")
    rules = read_json("vm_frozen_rule_verification.json")
    init = read_json("vm_operational_initialization.json")
    assert rules["rules_resolved"] is True
    assert rules["lookahead_used"] is False
    assert init["last_signal_date"] < manifest["t0"]
    assert init["target_allocation"] == {"QUAL": 0.5, "SPY": 0.5}


def test_dsr_target_initialization_uses_frozen_rules_and_pre_execution_information() -> None:
    manifest = read_json("reinitialization_manifest.json")
    rules = read_json("dsr_frozen_rule_verification.json")
    init = read_json("dsr_operational_initialization.json")
    assert rules["rules_resolved"] is True
    assert rules["lookahead_used"] is False
    assert init["last_signal_date"] < manifest["t0"]
    assert abs(sum(init["target_allocation"].values()) - 1.0) <= 1e-12


def test_initialization_costs_are_applied_once() -> None:
    vm = read_json("vm_operational_initialization.json")
    dsr = read_json("dsr_operational_initialization.json")
    assert vm["initialization_cost"] == 1.5
    assert dsr["initialization_cost"] == 1.5
    assert vm["post_cost_equity"] == 2998.5
    assert dsr["post_cost_equity"] == 2998.5


def test_vm_and_dsr_start_with_independent_3000_capital() -> None:
    assert read_json("vm_operational_initialization.json")["initial_virtual_capital"] == 3000.0
    assert read_json("dsr_operational_initialization.json")["initial_virtual_capital"] == 3000.0
    assert obs_yaml(reinit.VM_ID)["initial_virtual_capital"] == 3000.0
    assert obs_yaml(reinit.DSR_ID)["initial_virtual_capital"] == 3000.0


def test_component_holdings_shares_and_cash_are_explicit() -> None:
    for name in ["vm_operational_initialization.json", "dsr_operational_initialization.json"]:
        payload = read_json(name)
        assert payload["current_holdings"]
        assert payload["virtual_shares"]
        assert "cash" in payload
        assert payload["target_allocation"]


def test_no_synthetic_pre_t0_ledger_rows_exist() -> None:
    for name in ["vm_component_forward_ledger.csv", "dsr_component_forward_ledger.csv"]:
        rows = read_csv(name)
        assert len(rows) == 1
        assert rows[0]["date"] == "2026-06-18"
        assert rows[0]["row_type"] == "operational_initialization"


def test_usci_existing_committed_ledger_remains_intact() -> None:
    status = read_json("usci_state_preservation_and_update.json")
    obs = obs_yaml(reinit.USCI_ID)
    assert status["existing_committed_rows_preserved"] is True
    assert obs["latest_committed_observation_date"] == "2026-07-01"
    assert obs["latest_committed_forward_sessions"] == 8


def test_usci_is_not_reset() -> None:
    status = read_json("usci_state_preservation_and_update.json")
    obs = obs_yaml(reinit.USCI_ID)
    assert status["reset_to_3000"] is False
    assert obs["initial_observation_date"] == "2026-06-18"
    assert obs["latest_committed_virtual_equity"] != 3000.0


def test_active_combo_remains_reference_only() -> None:
    payload = read_json("active_combo_forward_reference_rebaseline.json")
    assert payload["role"] == "benchmark_reference_only"
    assert payload["historical_definition_changed"] is False
    assert payload["continuity_from_historical_series"] is False


def test_derived_combo_uses_separate_3000_account() -> None:
    payload = read_json("derived_combo_operational_reinitialization.json")
    obs = obs_yaml(reinit.DERIVED_ID)
    assert payload["initial_virtual_capital"] == 3000.0
    assert obs["initial_virtual_capital"] == 3000.0
    assert payload["initial_sleeves"] == {reinit.VM_ID: 1000.0, reinit.DSR_ID: 1000.0, reinit.USCI_ID: 1000.0}


def test_component_capital_is_not_reduced_to_fund_derived_combo() -> None:
    payload = read_json("derived_combo_operational_reinitialization.json")
    assert payload["component_capital_reduced_or_reserved"] is False
    assert read_json("consistency_check.json")["component_capital_not_reduced_for_derived_combo"] is True


def test_derived_component_indices_rebase_without_resetting_components() -> None:
    rows = read_csv("derived_combo_component_index_baselines.csv")
    assert {row["component_observation_id"] for row in rows} == {reinit.VM_ID, reinit.DSR_ID, reinit.USCI_ID}
    assert all(float(row["component_forward_index"]) == 1.0 for row in rows)
    assert all(row["component_state_reset"] == "false" for row in rows)


def test_sleeve_weights_drift_policy_after_initialization() -> None:
    obs = obs_yaml(reinit.DERIVED_ID)
    assert obs["drift_between_rebalances"] is True
    assert read_json("consistency_check.json")["sleeve_weights_drift_policy_preserved"] is True


def test_missing_returns_are_not_zero_or_forward_filled() -> None:
    obs = obs_yaml(reinit.DERIVED_ID)
    assert obs["missing_component_return_as_zero"] is False
    assert obs["forward_fill_missing_component_return"] is False
    check = read_json("consistency_check.json")
    assert check["missing_returns_not_zero_filled"] is True
    assert check["missing_returns_not_forward_filled"] is True


def test_component_costs_are_not_reapplied() -> None:
    obs = obs_yaml(reinit.DERIVED_ID)
    assert obs["component_costs_reapplied"] is False
    assert read_json("consistency_check.json")["component_costs_not_reapplied"] is True


def test_portfolio_transfer_costs_are_applied_once() -> None:
    obs = obs_yaml(reinit.DERIVED_ID)
    assert obs["portfolio_transfer_cost_rate"] == 0.0005
    assert read_json("consistency_check.json")["portfolio_transfer_cost_applied_once"] is True


def test_no_broker_api_or_orders() -> None:
    safety = read_json("broker_and_order_safety_check.json")
    assert safety["broker_api_called"] is False
    assert safety["paper_orders_created"] is False
    assert safety["live_orders"] is False


def test_no_real_money_flag_becomes_true() -> None:
    assert read_json("broker_and_order_safety_check.json")["real_money_recommendation"] is False
    assert read_json("reinitialization_manifest.json")["real_money_recommendation"] is False


def test_exposure_remains_at_or_below_one() -> None:
    assert read_json("consistency_check.json")["aggregate_exposure_lte_1"] is True
    assert sum(read_json("vm_operational_initialization.json")["target_allocation"].values()) <= 1.0
    assert sum(read_json("dsr_operational_initialization.json")["target_allocation"].values()) <= 1.0


def test_rerunning_with_unchanged_snapshots_is_idempotent() -> None:
    before = {row["source_of_truth_file"]: row["after_hash"] for row in read_csv("source_of_truth_changes.csv")}
    result = reinit.run()
    after = {row["source_of_truth_file"]: row["after_hash"] for row in read_csv("source_of_truth_changes.csv")}
    assert result["outcome"] == "forward_operational_reinitialization_passed"
    assert before == after
    assert read_json("consistency_check.json")["rerun_with_unchanged_snapshots_idempotent"] is True


def test_operational_outcome_and_next_action() -> None:
    outcome = read_json("operational_outcome.json")
    assert outcome["outcome"] == "forward_operational_reinitialization_passed"
    assert outcome["next_action"] == "resume_targeted_fast_discovery_while_reinitialized_observations_run"
    assert read_json("consistency_check.json")["consistency_passed"] is True
