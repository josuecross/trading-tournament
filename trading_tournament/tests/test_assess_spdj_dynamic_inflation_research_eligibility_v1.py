from __future__ import annotations

import csv
import json

import pytest

from strategy_lab.research_os.research import assess_spdj_dynamic_inflation_research_eligibility_v1 as subject


@pytest.fixture(scope="module", autouse=True)
def completed_run():
    result = subject.run()
    assert result["overall_pass"] is True
    return result


def payload(name: str) -> dict:
    return json.loads((subject.OUTPUT_DIR / name).read_text(encoding="utf-8"))


def caveats() -> list[dict[str, str]]:
    with (subject.OUTPUT_DIR / "caveat_register.csv").open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_exact_identity_and_outcome() -> None:
    decision = payload("eligibility_decision.json")
    assert decision["strategy_id"] == subject.STRATEGY_ID
    assert decision["family_id"] == subject.FAMILY_ID
    assert decision["canonical_trial_id"] == subject.CANONICAL_TRIAL_ID
    assert decision["robustness_trial_id"] == subject.ROBUSTNESS_TRIAL_ID
    assert decision["eligibility_status"] == "spdj_dynamic_inflation_research_eligible_for_handoff"


def test_all_six_eligibility_gates_pass() -> None:
    gates = payload("eligibility_gate_results.json")
    assert gates["all_gates_pass"] is True
    assert len(gates["gates"]) == 6
    assert {gate["status"] for gate in gates["gates"].values()} == {"pass"}


def test_hash_namespaces_are_explicit_and_reconciled() -> None:
    reconciliation = payload("source_and_data_reconciliation.json")
    namespaces = reconciliation["hash_namespaces"]
    assert namespaces["logical_normalized_CPI_dataset"]["hash"] == subject.EXPECTED_CPI_HASH
    assert namespaces["price_bundle"]["hash"] == subject.EXPECTED_PRICE_BUNDLE_HASH
    assert namespaces["frozen_universe_packet"]["logical_hash"] == subject.EXPECTED_UNIVERSE_HASH
    assert namespaces["CPI_V2_directory_artifact"]["hash"] != subject.EXPECTED_CPI_HASH
    assert all(row["matches"] for row in reconciliation["artifact_hash_reconciliation"].values())


def test_exploration_reconciles_without_new_performance() -> None:
    exploration = payload("exploration_reconciliation.json")
    assert exploration["status"] == "reconciled"
    assert exploration["outcome"] == subject.EXPECTED_EXPLORATION_OUTCOME
    assert exploration["deterministic_evidence_hash"] == subject.EXPECTED_EXPLORATION_HASH
    assert exploration["selection_period"]["events"] == 121
    assert exploration["evaluation_period"]["events"] == 82
    assert exploration["new_performance_calculations"] == 0


def test_robustness_reconciles_without_rerun() -> None:
    robustness = payload("robustness_reconciliation.json")
    assert robustness["status"] == "reconciled"
    assert robustness["outcome"] == subject.EXPECTED_ROBUSTNESS_OUTCOME
    assert robustness["deterministic_evidence_hash"] == subject.EXPECTED_ROBUSTNESS_HASH
    assert robustness["four_block_summary"]["simultaneous_control_dominance_block_count"] == 0
    assert robustness["bootstrap_summary"]["replications"] == 10_000
    assert robustness["new_robustness_calculations"] == 0


def test_source_contract_and_mapping_are_complete() -> None:
    source = payload("source_and_data_reconciliation.json")
    assert source["status"] == "reconciled"
    assert all(source["source_contract_checks"].values())
    mapping = {row["symbol"]: row["classification"] for row in source["mapping"]}
    assert set(mapping) == set(subject.SYMBOLS)
    assert mapping["GSG"] == "exact_match"
    assert all(mapping[symbol] == "economically_close_source_preserving_proxy" for symbol in set(subject.SYMBOLS) - {"GSG"})


def test_correction_lineage_is_auditable_and_nonadaptive() -> None:
    lineage = payload("lineage_reconciliation.json")
    correction = lineage["correction_lineage"]
    assert correction["invalidated_selection_results_preserved"] is True
    assert correction["strategy_rule_changed"] is False
    assert correction["trial_id_changed"] is False
    assert correction["performance_result_used_to_choose_correction"] is False
    assert lineage["robustness_reproduced_corrected_parent"] is True


def test_implementation_integrity_passes() -> None:
    integrity = payload("implementation_integrity.json")
    assert integrity["status"] == "reconciled"
    assert integrity["observed_code_hash"] == subject.EXPECTED_CODE_HASH
    assert all(integrity["checks"].values())
    assert integrity["implementation_changed_by_task"] is False


def test_caveats_are_explicit_with_no_blockers() -> None:
    rows = caveats()
    assert [row["caveat_id"] for row in rows] == ["C1", "C2", "C3", "C4", "C5", "C6"]
    counts = {classification: sum(row["classification"] == classification for row in rows) for classification in {row["classification"] for row in rows}}
    assert counts == {"nonblocking_material": 5, "nonblocking_minor": 1}
    decision = payload("eligibility_decision.json")
    assert decision["blocking_caveat_count"] == 0
    assert decision["material_nonblocking_caveat_count"] == 5
    assert decision["minor_caveat_count"] == 1


def test_handoff_specification_is_complete_but_not_exported() -> None:
    handoff = payload("handoff_specification_readiness.json")
    assert handoff["overall_ready"] is True
    assert set(handoff["required_fields"]["tradable_symbols"]) == set(subject.SYMBOLS)
    assert handoff["October_2025_exception_representable"] is True
    assert handoff["handoff_export_executed"] is False
    assert handoff["forward_application_operational_health_tested"] is False


def test_trial_accounting_has_no_new_research_or_forward_activity() -> None:
    accounting = payload("trial_accounting.json")
    assert accounting["parent_canonical_trial_count"] == 1
    assert accounting["robustness_trial_count"] == 1
    assert accounting["eligibility_decisions_created_by_task"] == 1
    assert accounting["new_canonical_trials"] == 0
    assert accounting["new_robustness_trials"] == 0
    assert accounting["strategy_variants"] == 0
    assert accounting["new_performance_calculations"] == 0
    assert accounting["evaluation_accesses"] == 0
    assert accounting["forward_observation_accesses"] == 0
    assert accounting["handoffs_executed"] == 0
    assert accounting["provider_calls"] == 0
    assert accounting["broker_calls"] == 0


def test_protected_state_and_required_outputs_reconcile() -> None:
    consistency = payload("consistency_check.json")
    assert consistency["checks"]["protected_state_unchanged_during_task"] is True
    assert consistency["checks"]["all_required_artifacts_exist"] is True
    assert set(subject.REQUIRED_OUTPUTS).issubset({path.name for path in subject.OUTPUT_DIR.iterdir()})


def test_exact_next_action_is_recorded_not_executed() -> None:
    decision = payload("eligibility_decision.json")
    accounting = payload("trial_accounting.json")
    assert decision["next_action"] == "export_spdj_dynamic_inflation_forward_observation_handoff_v1"
    assert decision["next_action_executed"] is False
    assert accounting["handoffs_executed"] == 0


def test_deterministic_rerun_preserves_timestamp_and_packet_hash(completed_run) -> None:
    before_timestamp = payload("eligibility_decision.json")["eligibility_decision_timestamp"]
    second = subject.run()
    after_timestamp = payload("eligibility_decision.json")["eligibility_decision_timestamp"]
    assert after_timestamp == before_timestamp
    assert second["deterministic_eligibility_packet_hash"] == completed_run["deterministic_eligibility_packet_hash"]
    assert second["overall_pass"] is True
