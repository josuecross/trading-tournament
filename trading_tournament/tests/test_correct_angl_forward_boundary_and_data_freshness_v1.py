from __future__ import annotations

import csv
import json
import re
from pathlib import Path

import pytest
import yaml

from strategy_lab.research_os.research import correct_angl_forward_boundary_and_data_freshness_v1 as correction


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "correction" / "correct_angl_forward_boundary_and_data_freshness_v1" / "latest"
STRATEGY_ID = "ice_vaneck_us_fallen_angel_angl_v1"
OBSERVATION_ID = "paper_forward_angl_20pct_diversifier_v1"
PARENT_TRIAL_ID = "correction_angl__ice_vaneck_us_fallen_angel_angl_v1__methodology_correction_child"
NEXT_ACTION = "initialize_angl_after_next_completed_common_session_v1"


@pytest.fixture(scope="module", autouse=True)
def evidence_ready() -> None:
    if not (EVIDENCE / "consistency_check.json").exists():
        correction.run()


def read_csv(name: str) -> list[dict[str, str]]:
    with (EVIDENCE / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_json(name: str) -> dict[str, object]:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def read_yaml(name: str) -> dict[str, object]:
    return yaml.safe_load((EVIDENCE / name).read_text(encoding="utf-8"))


def test_required_artifacts_and_manifest_blocked_scope() -> None:
    required = {
        "correction_manifest.yaml",
        "strategy_cards.csv",
        "trial_ledger.csv",
        "paper_demo_observations.csv",
        "process_task_log.csv",
        "benchmark_reference_log.csv",
        "prior_boundary_defect.csv",
        "market_data_refresh_manifest.csv",
        "data_freshness.csv",
        "reference_state_reconciliation.csv",
        "forward_boundary_decision.csv",
        "historical_reconciliation_records.csv",
        "forward_observation_records.csv",
        "initial_target_weights.csv",
        "initial_virtual_positions.csv",
        "initial_virtual_trades.csv",
        "initial_virtual_nav.csv",
        "control_virtual_nav.csv",
        "idempotency_check.csv",
        "state_change_manifest.csv",
        "outcome_summary.csv",
        "failure_reasons.csv",
        "next_actions.csv",
        "consistency_check.json",
        "correction_report.md",
    }
    assert sorted(name for name in required if not (EVIDENCE / name).exists()) == []
    manifest = read_yaml("correction_manifest.yaml")
    assert manifest["correction_id"] == "correct_angl_forward_boundary_and_data_freshness_v1"
    assert manifest["mode"] == "correction"
    assert manifest["lane"] == "paper_demo_observation_correction"
    assert manifest["stage"] == "correction"
    assert manifest["primary_entity_type"] == "paper_demo_observation"
    assert manifest["adaptation_label"] == "paper_demo_observation_fix"
    assert manifest["strategy_id"] == STRATEGY_ID
    assert manifest["observation_id"] == OBSERVATION_ID
    assert manifest["observation_stage"] == "blocked"
    assert manifest["observation_outcome"] == "observation_invalid_or_incomplete"
    assert manifest["primary_failure_reason"] == "methodology_failure"
    assert manifest["defect_type"] == "forward_boundary_precedes_activation"
    assert manifest["funnel_counts"]["eligible_strategy_configurations"] == 1
    assert manifest["funnel_counts"]["paper_demo_observations"] == 1
    assert manifest["funnel_counts"]["active_observations"] == 0
    assert manifest["funnel_counts"]["blocked_observations"] == 1
    assert manifest["funnel_counts"]["new_experiment_trials"] == 0
    assert manifest["exact_next_action"] == NEXT_ACTION


def test_prior_boundary_defect_is_explicit_and_june_18_is_historical_only() -> None:
    defect = read_csv("prior_boundary_defect.csv")[0]
    assert defect["observation_id"] == OBSERVATION_ID
    assert defect["prior_observation_outcome"] == "observation_invalid_or_incomplete"
    assert defect["primary_failure_reason"] == "methodology_failure"
    assert defect["defect_type"] == "forward_boundary_precedes_activation"
    assert defect["original_activation_timestamp"] == "2026-07-24T00:00:00+00:00"
    assert defect["original_first_forward_observation_date"] == "2026-06-18"
    assert defect["original_latest_common_data_date"] == "2026-06-18"
    assert int(defect["days_boundary_preceded_activation"]) == 36
    assert defect["return_previously_counted_as_forward_evidence"] == "false"
    assert defect["trade_position_or_nav_previously_mislabeled_forward"] == "true"
    assert defect["corrected_classification_for_june_18"] == "historical_reconciliation_only"
    historical = read_csv("historical_reconciliation_records.csv")
    assert historical
    assert {row["corrected_record_classification"] for row in historical} == {"historical_reconciliation_only"}
    assert {row["forward_observation_evidence"] for row in historical} == {"false"}


def test_entity_separation_and_no_new_trial() -> None:
    strategy = read_csv("strategy_cards.csv")
    trial = read_csv("trial_ledger.csv")
    observation = read_csv("paper_demo_observations.csv")
    benchmarks = read_csv("benchmark_reference_log.csv")
    process = read_csv("process_task_log.csv")
    assert len(strategy) == 1
    assert strategy[0]["entity_type"] == "strategy_configuration"
    assert strategy[0]["stage"] == "paper_demo_eligible"
    assert strategy[0]["outcome"] == "paper_demo_eligible"
    assert strategy[0]["route"] == "diversifier_only"
    assert strategy[0]["strategy_validation_repeated"] == "false"
    assert strategy[0]["new_strategy_configuration_created"] == "false"
    assert len(trial) == 1
    assert trial[0]["entity_type"] == "experiment_trial_lineage_read_only"
    assert trial[0]["trial_id"] == PARENT_TRIAL_ID
    assert trial[0]["new_experiment_trial_created"] == "false"
    assert len(observation) == 1
    assert observation[0]["entity_type"] == "paper_demo_observation"
    assert observation[0]["stage"] == "blocked"
    assert observation[0]["outcome"] == "observation_invalid_or_incomplete"
    assert observation[0]["failure_reason"] == "methodology_failure"
    assert observation[0]["corrected_first_forward_observation_date"] == ""
    assert observation[0]["next_action"] == NEXT_ACTION
    assert {row["entity_type"] for row in benchmarks} == {"benchmark_reference"}
    assert {row["stage"] for row in benchmarks} == {"benchmark_reference_only"}
    assert {row["counted_as_strategy"] for row in benchmarks} == {"false"}
    assert {row["counted_as_trial"] for row in benchmarks} == {"false"}
    assert process[0]["entity_type"] == "process_task"
    assert process[0]["stage"] == "correction"
    assert process[0]["adaptation_label"] == "paper_demo_observation_fix"
    assert process[0]["trial_counted"] == "false"


def test_data_freshness_reference_state_and_boundary_gate_block_activation() -> None:
    freshness = read_csv("data_freshness.csv")
    symbols = {row["symbol"] for row in freshness}
    assert {"ANGL", "HYG", "JNK", "SPY", "BIL", "USCI", "QUAL", "SPLV", "USMV", "XLK", "XLF"}.issubset(symbols)
    assert all(row["cache_exists"] == "true" for row in freshness)
    by_symbol = {row["symbol"]: row for row in freshness}
    assert by_symbol["HYG"]["latest_available_date"] == "2026-06-18"
    assert by_symbol["JNK"]["latest_available_date"] == "2026-06-18"
    assert by_symbol["ANGL"]["latest_available_date"] == "2026-07-15"
    refresh = read_csv("market_data_refresh_manifest.csv")
    assert len(refresh) == len(freshness)
    assert {row["refresh_attempted"] for row in refresh} == {"false"}
    assert {row["provider_download_performed"] for row in refresh} == {"false"}
    assert {row["broker_or_order_endpoint_called"] for row in refresh} == {"false"}
    assert {row["cache_changed"] for row in refresh} == {"false"}
    reference = read_csv("reference_state_reconciliation.csv")
    ref_row = next(row for row in reference if row["reference_or_component_id"] == "frozen_current_active_vm_dsr_usci_combo")
    assert ref_row["latest_reproducible_state_date"] == "2026-06-18"
    assert ref_row["after_correction_activation"] == "false"
    assert ref_row["reconciliation_status"] == "blocked_no_post_correction_reference_state"
    boundary = read_csv("forward_boundary_decision.csv")[0]
    assert boundary["valid_first_forward_session_exists"] == "false"
    assert boundary["activation_gate_status"] == "blocked"
    assert boundary["decision"] == "no_valid_completed_common_session_after_correction_activation"
    assert boundary["next_action"] == NEXT_ACTION


def test_forward_and_initial_virtual_files_are_header_only_while_blocked() -> None:
    for name in [
        "forward_observation_records.csv",
        "initial_target_weights.csv",
        "initial_virtual_positions.csv",
        "initial_virtual_trades.csv",
        "initial_virtual_nav.csv",
        "control_virtual_nav.csv",
    ]:
        assert read_csv(name) == []
    idempotency = read_csv("idempotency_check.csv")
    assert {row["status"] for row in idempotency} == {"pass"}
    assert {row["check_id"] for row in idempotency} == {
        "existing_observation_record_updated_in_place",
        "no_forward_trade_created_without_valid_session",
        "same_session_rerun_would_not_duplicate_trade",
    }


def test_authoritative_state_is_corrected_in_place_and_existing_observations_preserved() -> None:
    active_text = (ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml").read_text(encoding="utf-8")
    assert len(re.findall(rf"(?m)^- observation_id: {re.escape(OBSERVATION_ID)}$", active_text)) == 1
    active = yaml.safe_load(active_text)
    observations = active["active_observations"]
    row = next(row for row in observations if row.get("observation_id") == OBSERVATION_ID)
    assert row["entity_type"] == "paper_demo_observation"
    assert row["stage"] == "blocked"
    assert row["outcome"] == "observation_invalid_or_incomplete"
    assert row["state"] == "blocked_observation_invalid_or_incomplete"
    assert row["paper_forward_active"] is False
    assert row["failure_reason"] == "methodology_failure"
    assert row["defect_type"] == "forward_boundary_precedes_activation"
    assert row["adaptation_label"] == "paper_demo_observation_fix"
    assert row["original_first_forward_observation_date"] == "2026-06-18"
    assert row["corrected_first_forward_observation_date"] == ""
    assert row["first_forward_observation_date"] == ""
    assert row["next_action"] == NEXT_ACTION
    assert {
        "paper_forward_vm_quality_lowvol_proxy_v1",
        "paper_forward_dsr_sector_equal_weight_defensive_filter_v1",
        "paper_forward_usci_dynamic_commodity_curve_selection_wrapper_v1",
        "paper_forward_combo_vm_dsr_usci_equal_weight_monthly_v1",
    }.issubset({obs.get("strategy_id") for obs in observations})


def test_strategy_registry_remains_eligible_and_only_next_action_changes() -> None:
    registry_text = (ROOT / "strategy_lab" / "strategy_registry.yaml").read_text(encoding="utf-8")
    assert len(re.findall(rf"(?m)^- id: {re.escape(STRATEGY_ID)}$", registry_text)) == 1
    registry = yaml.safe_load(registry_text)
    row = next(row for row in registry["strategies"] if row.get("id") == STRATEGY_ID)
    assert row["entity_type"] == "strategy_configuration"
    assert row["stage"] == "paper_demo_eligible"
    assert row["outcome"] == "paper_demo_eligible"
    assert row["route"] == "diversifier_only"
    assert row["paper_orders"] is False
    assert row["live_orders"] is False
    assert row["real_money_recommendation"] is False
    assert row["next_action"] == NEXT_ACTION
    assert row["allowed_next_action"] == NEXT_ACTION


def test_state_change_manifest_and_consistency_flags() -> None:
    state = read_csv("state_change_manifest.csv")
    state_rows = {row["path"]: row for row in state if row["path_type"] == "authoritative_state"}
    assert state_rows["strategy_lab/RESEARCH_ROADMAP.md"]["changed"] == "false"
    assert state_rows["strategy_lab/research_os/research/research_queue.yaml"]["changed"] == "false"
    assert state_rows["strategy_lab/research_os/family_lineage/family_ledger.yaml"]["changed"] == "false"
    assert state_rows["strategy_lab/research_os/operations/active_observations.yaml"]["changed"] == "true"
    assert state_rows["strategy_lab/research_os/operations/active_observations.yaml"]["action"] == "updated_in_place"
    assert state_rows["strategy_lab/strategy_registry.yaml"]["action"] in {"next_action_updated", "already_current"}
    cache_rows = [row for row in state if row["path_type"] == "market_data_cache"]
    assert cache_rows
    assert {row["changed"] for row in cache_rows} == {"false"}
    consistency = read_json("consistency_check.json")
    assert consistency["consistency_passed"] is True
    assert consistency["prior_observation_invalid_or_incomplete_recorded"] is True
    assert consistency["june_18_reclassified_historical_only"] is True
    assert consistency["valid_first_forward_session_exists"] is False
    assert consistency["observation_stage"] == "blocked"
    assert consistency["strategy_stage"] == "paper_demo_eligible"
    assert consistency["new_strategy_configuration_created"] is False
    assert consistency["new_experiment_trials_created"] == 0
    assert consistency["forward_observation_rows_created"] == 0
    assert consistency["initial_virtual_trade_rows_created"] == 0
    assert consistency["prior_onboarding_evidence_unchanged"] is True
    assert consistency["validation_and_methodology_correction_evidence_unchanged"] is True
    assert consistency["only_permitted_state_changes"] is True
    assert consistency["research_queue_unchanged"] is True
    assert consistency["family_ledger_unchanged"] is True
    assert consistency["roadmap_unchanged"] is True
    assert consistency["broker_order_submitted"] is False
    assert consistency["paper_order_submitted"] is False
    assert consistency["live_order_submitted"] is False
    assert consistency["account_accessed"] is False
    assert consistency["real_money_action"] is False
    assert consistency["exact_next_action"] == NEXT_ACTION
