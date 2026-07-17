from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

from strategy_lab.research_os.research import current_paper_forward_update_and_reconciliation_v1 as update


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "current_paper_forward_update_and_reconciliation_v1" / "latest"


def read_json(name: str) -> dict[str, object]:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def read_csv(name: str) -> list[dict[str, str]]:
    with (EVIDENCE / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_required_artifacts_exist() -> None:
    required = {
        "update_manifest.json",
        "provider_and_snapshot_manifest.json",
        "active_observation_state_before.csv",
        "component_update_results.csv",
        "component_daily_forward_returns.csv",
        "common_date_resolution.csv",
        "active_combo_benchmark_update.csv",
        "derived_combo_daily_ledger.csv",
        "derived_combo_sleeve_weights.csv",
        "monthly_rebalance_events.csv",
        "portfolio_transfer_costs.csv",
        "missing_and_stale_component_dates.csv",
        "observation_monitoring_snapshot.csv",
        "protected_state_verification.json",
        "broker_and_order_safety_check.json",
        "source_of_truth_changes.csv",
        "operational_outcome.json",
        "update_summary.md",
        "consistency_check.json",
    }
    assert sorted(name for name in required if not (EVIDENCE / name).exists()) == []


def test_allowed_blocked_outcome_is_recorded() -> None:
    outcome = read_json("operational_outcome.json")
    assert outcome["outcome"] == "component_observation_update_blocked"
    assert outcome["allowed_outcome"] is True
    assert outcome["derived_combo_advanced_beyond_activation"] is False
    assert outcome["final_derived_observation_session"] == update.ACTIVATION_DATE
    assert outcome["next_action"] == update.NEXT_ACTION_BLOCKED


def test_manifest_records_operational_not_research_or_promotion() -> None:
    manifest = read_json("update_manifest.json")
    assert manifest["operational_update_task"] is True
    assert manifest["historical_backtest_run"] is False
    assert manifest["candidate_validation_run"] is False
    assert manifest["performance_review_decision"] is False
    assert manifest["promotion_task"] is False
    assert manifest["strategy_discovery_run"] is False


def test_no_provider_download_or_cache_refresh() -> None:
    manifest = read_json("update_manifest.json")
    provider = read_json("provider_and_snapshot_manifest.json")
    assert manifest["provider_download"] is False
    assert manifest["cache_refresh"] is False
    assert provider["provider_download"] is False
    assert provider["provider_api_called"] is False
    assert provider["cache_refresh"] is False
    assert provider["research_cache_rewritten"] is False


def test_approved_observation_refresh_path_limitation_is_visible() -> None:
    provider = read_json("provider_and_snapshot_manifest.json")
    assert "SPY_GLD_BIL" in str(provider["approved_provider_refresh_path_found"])
    assert set(provider["vm_required_symbols"]) == set(update.VM_SYMBOLS)
    assert set(provider["dsr_required_symbols"]) == set(update.DSR_SYMBOLS)


def test_all_active_observations_are_in_state_before_file() -> None:
    rows = read_csv("active_observation_state_before.csv")
    assert {row["observation_id"] for row in rows} == set(update.OBSERVATION_IDS)
    assert all(row["paper_forward_active"] == "True" for row in rows)
    assert all(row["frozen"] == "True" for row in rows)


def test_every_update_starts_from_prior_recorded_state_or_reports_unresolved_state() -> None:
    rows = {row["observation_id"]: row for row in read_csv("component_update_results.csv")}
    assert rows[update.VM_ID]["starting_observation_date"] == "unresolved_authoritative_forward_state"
    assert rows[update.DSR_ID]["starting_observation_date"] == "unresolved_authoritative_forward_state"
    assert rows[update.USCI_ID]["starting_observation_date"] == update.ACTIVATION_DATE
    assert rows[update.DERIVED_ID]["starting_observation_date"] == update.ACTIVATION_DATE


def test_component_capital_is_not_reduced_or_reserved() -> None:
    manifest = read_json("update_manifest.json")
    consistency = read_json("consistency_check.json")
    assert manifest["component_capital_reduced_or_reserved"] is False
    assert consistency["component_capital_not_reduced_or_reserved"] is True


def test_component_observations_are_checked_independently() -> None:
    rows = {row["observation_id"]: row for row in read_csv("component_update_results.csv")}
    assert rows[update.VM_ID]["update_status"] == "blocked"
    assert rows[update.DSR_ID]["update_status"] == "blocked"
    assert rows[update.USCI_ID]["update_status"] == "forward_rows_available_not_committed_due_component_group_blocker"
    assert rows[update.DERIVED_ID]["update_status"] == "not_advanced_component_observation_blocked"


def test_derived_uses_component_forward_returns_only_and_does_not_use_history_nav_substitution() -> None:
    returns = read_csv("component_daily_forward_returns.csv")
    assert returns
    assert {row["component_observation_id"] for row in returns} == {update.USCI_ID}
    assert all(row["used_by_derived_combo"] == "False" for row in returns)
    assert all(row["committed_to_component_state"] == "False" for row in returns)
    consistency = read_json("consistency_check.json")
    assert consistency["derived_uses_component_forward_returns_only"] is True


def test_derived_advances_only_on_complete_common_dates() -> None:
    resolution = read_csv("common_date_resolution.csv")
    summary = resolution[0]
    assert summary["latest_complete_common_component_session"] == update.ACTIVATION_DATE
    assert summary["derived_combo_can_advance"] == "False"
    assert all(row["complete_common_component_date"] in {"", "False"} for row in resolution[1:])


def test_missing_returns_are_not_zero_filled_or_forward_filled() -> None:
    missing = read_csv("missing_and_stale_component_dates.csv")
    assert any(row["derived_action"] == "do_not_advance_no_fill" for row in missing)
    consistency = read_json("consistency_check.json")
    assert consistency["missing_component_returns_not_zero_filled"] is True
    assert consistency["missing_component_returns_not_forward_filled"] is True
    assert consistency["no_partial_date_advance"] is True


def test_fixed_one_third_daily_averaging_is_prohibited() -> None:
    ledger = read_csv("derived_combo_daily_ledger.csv")
    assert len(ledger) == 1
    assert ledger[0]["forward_return_source"] == "activation_state_only_no_new_common_component_date"
    assert read_json("consistency_check.json")["fixed_daily_one_third_averaging_prohibited"] is True


def test_sleeve_weights_drift_policy_is_preserved_but_no_new_drift_is_fabricated() -> None:
    weights = read_csv("derived_combo_sleeve_weights.csv")
    assert len(weights) == 1
    assert abs(float(weights[0]["vm_sleeve_weight"]) - 1.0 / 3.0) < 1e-12
    assert float(weights[0]["aggregate_exposure"]) <= 1.0
    assert read_json("consistency_check.json")["sleeve_weights_drift_policy_preserved"] is True


def test_july_rebalance_is_not_processed_without_first_common_july_session() -> None:
    manifest = read_json("update_manifest.json")
    rebalance = read_csv("monthly_rebalance_events.csv")[0]
    assert manifest["july_monthly_rebalance_processed"] is False
    assert rebalance["event_status"] == "blocked_no_complete_common_component_session"
    assert rebalance["times_processed"] == "0"
    assert read_json("consistency_check.json")["july_first_common_session_rebalance_at_most_once"] is True


def test_rebalance_costs_and_component_costs_are_not_fabricated() -> None:
    costs = read_csv("portfolio_transfer_costs.csv")[0]
    assert float(costs["transfer_cost"]) == 0.0
    assert costs["component_costs_reapplied"] == "False"
    consistency = read_json("consistency_check.json")
    assert consistency["portfolio_transfer_cost_applied_once"] is True
    assert consistency["internal_component_costs_not_reapplied"] is True


def test_active_combo_remains_benchmark_reference_only() -> None:
    rows = read_csv("active_combo_benchmark_update.csv")
    assert rows[0]["benchmark_id"] == update.ACTIVE_COMBO_ID
    assert rows[0]["role"] == "benchmark_reference_only"
    assert rows[0]["definition_changed"] == "False"
    assert read_json("consistency_check.json")["active_combo_reference_only"] is True


def test_no_broker_api_or_orders_or_real_money_path() -> None:
    safety = read_json("broker_and_order_safety_check.json")
    for key, value in safety.items():
        assert value is False
    consistency = read_json("consistency_check.json")
    assert consistency["no_broker_api_called"] is True
    assert consistency["no_paper_or_live_order_created"] is True
    assert consistency["no_real_money_flag_true"] is True


def test_aggregate_exposure_lte_one() -> None:
    weights = read_csv("derived_combo_sleeve_weights.csv")
    assert max(float(row["aggregate_exposure"]) for row in weights) <= 1.0
    assert read_json("consistency_check.json")["aggregate_exposure_lte_1"] is True


def test_source_of_truth_files_are_not_changed() -> None:
    rows = read_csv("source_of_truth_changes.csv")
    assert rows
    assert all(row["changed"] == "False" for row in rows)
    protected = read_json("protected_state_verification.json")
    assert protected["protected_files_unchanged"] is True
    assert protected["hashes_before"] == protected["hashes_after"]


def test_rerun_with_unchanged_snapshots_is_idempotent_for_outcome_and_state() -> None:
    outcome_before = read_json("operational_outcome.json")["outcome"]
    protected = read_json("protected_state_verification.json")
    assert outcome_before == "component_observation_update_blocked"
    assert protected["hashes_before"] == protected["hashes_after"]
    assert read_json("consistency_check.json")["rerun_with_unchanged_snapshots_outcome_idempotent"] is True


def test_consistency_check_passes_for_blocker_packet() -> None:
    consistency = read_json("consistency_check.json")
    assert consistency["consistency_passed"] is True
    assert consistency["component_observation_update_blocked"] is True
