from __future__ import annotations

import csv
import json

import yaml

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.research import (
    paper_demo_eligibility_and_handoff_internal_capture_asymmetry_63d_top3_v1 as task,
)


ELIGIBILITY = ROOT / "evidence" / "paper_demo_eligibility" / task.STRATEGY_ID / "latest"
HANDOFF = ROOT / "evidence" / "handoff" / task.STRATEGY_ID / "latest"


def rows(path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_run_creates_required_eligibility_and_handoff_packets() -> None:
    result = task.run()
    assert result["trading_tournament_eligibility_status"] == "paper_demo_eligible"
    assert result["handoff_status"] == "ready_for_forward_observation_app"
    assert result["forward_observation_app_operational_status"] == "not_evaluated_by_trading_tournament"
    assert result["next_action"] == task.NEXT_IMPORT_ACTION
    assert result["next_action_executed"] is False
    assert {path.name for path in ELIGIBILITY.iterdir() if path.is_file()} == task.ELIGIBILITY_REQUIRED_OUTPUTS
    assert {path.name for path in HANDOFF.iterdir() if path.is_file()} == task.HANDOFF_REQUIRED_OUTPUTS


def test_identity_and_lineage_are_reconciled_without_new_trial() -> None:
    identity = rows(ELIGIBILITY / "strategy_identity_reconciliation.csv")
    assert all(row["status"] == "pass" for row in identity)
    lineage = {row["lineage_item"]: row["observed"] for row in rows(ELIGIBILITY / "exploration_lineage_reconciliation.csv")}
    assert lineage["architectures_preregistered_in_parent_batch"] == "3"
    assert lineage["canonical_configurations_preregistered"] == "12"
    assert lineage["configurations_actually_performance_executed"] == "8"
    assert lineage["architecture_a_configurations_executed"] == "4"
    assert lineage["selected_winner"] == task.STRATEGY_ID
    counts = json.loads((ELIGIBILITY / "entity_count_reconciliation.json").read_text(encoding="utf-8"))
    assert counts["new_strategy_configurations"] == 0
    assert counts["new_experiment_trials"] == 0
    assert counts["paper_demo_eligibility_decisions"] == 1
    assert counts["handoff_export_packets"] == 1
    assert counts["paper_demo_observations"] == 0
    assert counts["virtual_positions"] == 0
    assert counts["broker_records"] == 0


def test_robustness_positive_is_consumed_not_rerun() -> None:
    robustness = rows(ELIGIBILITY / "robustness_lineage_reconciliation.csv")
    by_check = {row["check_id"]: row for row in robustness}
    assert by_check["robustness_outcome_positive"]["status"] == "pass"
    assert by_check["blocking_gates_passed"]["status"] == "pass"
    assert by_check["protected_state_reconciliation"]["status"] == "pass"
    assert by_check["robustness_not_rerun"]["status"] == "pass"
    process = rows(ELIGIBILITY / "process_task_log.csv")[0]
    assert process["robustness_rerun"] == "false"
    assert process["market_data_retrieval"] == "false"
    assert process["current_signal_calculated"] == "false"
    assert process["paper_demo_observation_created"] == "false"


def test_frozen_contract_and_fingerprint() -> None:
    spec = yaml.safe_load((ELIGIBILITY / "frozen_strategy_spec.yaml").read_text(encoding="utf-8"))
    assert spec["parameters"]["lookback_sessions"] == 63
    assert spec["parameters"]["top_k"] == 3
    assert spec["universe"]["risky_assets"] == list(task.UNIVERSE)
    assert spec["universe"]["fallback"] == "BIL"
    assert spec["execution_assumptions"]["execution_timestamp_convention"] == "following_regular_session_close"
    fingerprint = (HANDOFF / "strategy_configuration_fingerprint.txt").read_text(encoding="utf-8").strip()
    assert fingerprint == task.strategy_configuration_sha256()
    assert spec["strategy_configuration_sha256"] == fingerprint


def test_handoff_yaml_and_json_are_semantically_identical() -> None:
    yaml_payload = yaml.safe_load((HANDOFF / "strategy_handoff.yaml").read_text(encoding="utf-8"))
    json_payload = json.loads((HANDOFF / "strategy_handoff.json").read_text(encoding="utf-8"))
    validation = json.loads((HANDOFF / "handoff_validation.json").read_text(encoding="utf-8"))
    assert yaml_payload == json_payload
    assert validation["yaml_json_semantic_equivalence"] is True
    assert validation["same_canonical_semantic_hash"] is True
    assert validation["handoff_schema_valid"] is True
    assert validation["no_secrets_api_keys_account_ids_or_broker_configuration"] is True
    assert json_payload["consumer_module"] == "forward_observation_app"
    assert json_payload["forward_observation_app_operational_status"] == "not_evaluated_by_trading_tournament"
    assert json_payload["execute_next_action_in_this_task"] is False


def test_registry_lifecycle_record_ready_but_not_observation_active() -> None:
    registry = yaml.safe_load(task.REGISTRY_PATH.read_text(encoding="utf-8"))
    records = [row for row in registry["strategies"] if row.get("strategy_id") == task.STRATEGY_ID]
    assert len(records) == 1
    record = records[0]
    assert record["outcome"] == "paper_demo_eligible"
    assert record["handoff_status"] == "ready_for_forward_observation_app"
    assert record["forward_observation_app_operational_status"] == "not_evaluated_by_trading_tournament"
    assert record["paper_demo_active"] is False
    assert record["paper_forward_active"] is False
    assert record["paper_orders"] is False
    assert record["live_orders"] is False
    assert record["broker_integration"] is False
    assert record["configuration_fingerprint"] == task.strategy_configuration_sha256()


def test_research_evidence_is_recorded_as_historical_not_forward() -> None:
    evidence = {row["metric"]: row for row in rows(ELIGIBILITY / "research_evidence_summary.csv")}
    assert evidence["5bps_full_period_CAGR"]["value"] == "0.100088259048"
    assert evidence["5bps_full_period_Sharpe"]["value"] == "0.731377572748"
    assert evidence["5bps_maximum_drawdown"]["value"] == "-0.386152422549"
    assert evidence["10bps_CAGR"]["value"] == "0.0975654657787"
    assert all(row["forward_performance_expectation"] == "not_expected_forward_performance" for row in evidence.values())
    caveats = {row["caveat_id"]: row for row in rows(ELIGIBILITY / "known_caveats.csv")}
    assert "cross_sectional_yaml_contract_disclosure" in caveats
    assert caveats["cross_sectional_yaml_contract_disclosure"]["requires_robustness_reopen"] == "false"


def test_consistency_and_deterministic_regeneration() -> None:
    before = json.loads((ELIGIBILITY / "consistency_check.json").read_text(encoding="utf-8"))
    before_hash = before["deterministic_output_hash_excluding_consistency"]
    result = task.run()
    after = json.loads((ELIGIBILITY / "consistency_check.json").read_text(encoding="utf-8"))
    assert result["consistency_passed"] is True
    assert after["overall_pass"] is True
    assert after["checks"]["protected_state_reconciliation"] is True
    assert after["checks"]["required_eligibility_outputs_present"] is True
    assert after["checks"]["required_handoff_outputs_present"] is True
    assert after["deterministic_output_hash_excluding_consistency"] == before_hash
