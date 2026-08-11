from __future__ import annotations

import csv
import json

from strategy_lab.research_os.research import implement_forward_observation_handoff_standard_v1 as subject


def csv_rows(name: str) -> list[dict[str, str]]:
    with (subject.OUTPUT_DIR / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_evidence_regenerates_deterministically() -> None:
    first = subject.run()
    second = subject.run()
    assert first["overall_pass"] is True
    assert second["overall_pass"] is True
    assert first["deterministic_evidence_hash"] == second["deterministic_evidence_hash"]


def test_standard_readiness_is_complete_and_migration_ready() -> None:
    readiness = json.loads((subject.OUTPUT_DIR / "standardization_readiness.json").read_text(encoding="utf-8"))
    assert readiness["task_outcome"] == "forward_observation_handoff_standard_v1_implemented"
    assert readiness["schema_id"] == "forward_observation_handoff_standard_v1"
    assert readiness["schema_version"] == 1
    assert readiness["ready_for_strategy_migration"] is True
    assert readiness["legacy_runtime_backward_compatibility"] == "preserved_dual_path"
    assert readiness["microtrading_fail_closed"] is True


def test_spdj_is_structurally_representable_without_import_or_target() -> None:
    result = json.loads((subject.OUTPUT_DIR / "spdj_structural_compatibility.json").read_text(encoding="utf-8"))
    assert result["structural_compatibility"] == "standard_structurally_representable_validate_only"
    assert result["external_CPI_release_signal"] is True
    assert result["point_in_time_signal"] is True
    assert result["previous_month_end_statistics_cutoff"] is True
    assert result["next_market_session_effective_after_close"] is True
    assert result["no_release_no_event"] is True
    assert result["pending_target_before_effective_time"] is True
    assert result["cross_session_idempotency"] is True
    assert result["strategy_imported"] is False
    assert result["strategy_activated"] is False
    assert result["current_target_calculated"] is False


def test_internal_capture_has_adapter_and_exact_gaps() -> None:
    result = json.loads((subject.OUTPUT_DIR / "internal_capture_structural_compatibility.json").read_text(encoding="utf-8"))
    assert result["structural_compatibility"] == "standard_adapter_available_contract_enrichment_required"
    assert len(result["enrichment_gaps"]) == 7
    assert result["rules_invented"] is False
    assert result["strategy_imported"] is False


def test_liveness_reconciles_historical_running_session_as_stale() -> None:
    rows = {row["case"]: row for row in csv_rows("liveness_reconciliation_results.csv")}
    assert rows["fresh_running"]["authoritative_current_liveness"] == "active"
    assert rows["audited_historical_running_session"]["persisted_status"] == "running"
    assert rows["audited_historical_running_session"]["authoritative_current_liveness"] == "stale"
    assert rows["completed_terminal"]["authoritative_current_liveness"] == "terminal"


def test_state_restart_pending_and_no_event_pass() -> None:
    state = json.loads((subject.OUTPUT_DIR / "state_model_validation.json").read_text(encoding="utf-8"))
    assert state["state_persisted_and_reloaded"] is True
    assert state["cross_session_duplicate_result"] == "duplicate_event"
    assert state["pending_target_created"] is True
    assert state["pending_promoted_to_current"] is True
    assert state["no_event_preserved_current_target"] is True
    assert state["no_event_created_synthetic_event"] is False
    assert state["orders_or_execution_objects_created"] == 0


def test_lifecycle_and_microtrading_fail_closed() -> None:
    rows = csv_rows("lifecycle_transition_matrix.csv")
    assert all(row["result"] == "allowed" for row in rows if row["expected"] == "allowed")
    assert all(row["result"] == "microtrading_promotion_not_authorized" for row in rows if row["next_state"].startswith("microtrading"))
    micro = json.loads((subject.OUTPUT_DIR / "microtrading_fail_closed_validation.json").read_text(encoding="utf-8"))
    assert micro["transition_enabled"] is False
    assert micro["live_submission_supported"] is False


def test_deployment_and_research_contract_are_separate() -> None:
    result = json.loads((subject.OUTPUT_DIR / "deployment_profile_validation.json").read_text(encoding="utf-8"))
    assert result["inactive_profile_valid"] is True
    assert result["research_contract_contains_receiver_notional_or_submission_fields"] is False
    assert result["deployment_formula_override_result"] == "invalid_identity_binding"
    assert result["live_submission_result"] == "microtrading_promotion_not_authorized"


def test_importer_modes_are_inactive_and_fail_closed() -> None:
    result = json.loads((subject.OUTPUT_DIR / "importer_validation.json").read_text(encoding="utf-8"))
    assert result["standard_validate_only"]["acceptance_status"] == "contract_validated"
    assert result["synthetic_import_inactive"]["acceptance_status"] == "validated_not_active"
    assert result["synthetic_import_storage_was_temporary"] is True
    assert result["corrupt_package_result"] == "package_integrity_failure"
    assert result["persistent_real_handoff_imports"] == 0
    assert result["strategy_activations"] == 0


def test_target_execution_boundary_has_no_broker_dependencies() -> None:
    result = json.loads((subject.OUTPUT_DIR / "execution_boundary_validation.json").read_text(encoding="utf-8"))
    assert result["target_weights_present"] is True
    assert result["orders_present_in_standard_result"] is False
    assert result["quantities_present_in_standard_result"] is False
    assert result["standard_imports_broker_adapter"] is False
    assert result["standard_calls_submit_order"] is False


def test_legacy_runtime_and_handoffs_are_unchanged() -> None:
    result = json.loads((subject.OUTPUT_DIR / "backward_compatibility.json").read_text(encoding="utf-8"))
    assert result["overall_pass"] is True
    assert result["VM_calculator_and_spec_unchanged"] is True
    assert result["DSR_calculator_and_spec_unchanged"] is True
    assert result["VM_registry_entry_unchanged"] is True
    assert result["historical_session_unchanged"] is True
    assert result["legacy_strategy_migrations"] == 0
    assert result["legacy_strategy_activations"] == 0


def test_safety_counts_and_protected_state_pass() -> None:
    result = json.loads((subject.OUTPUT_DIR / "consistency_check.json").read_text(encoding="utf-8"))
    assert result["overall_pass"] is True
    assert result["checks"]["protected_state_unchanged"] is True
    assert result["protected_state_before"] == result["protected_state_after"]
    for field in ["market_data_network_calls", "external_signal_calls", "broker_calls", "account_calls", "order_submissions", "fills", "current_target_calculations", "observation_mutations", "strategy_activations", "strategy_migrations", "microtrading_transitions"]:
        assert result[field] == 0


def test_required_evidence_and_standard_artifacts_exist() -> None:
    assert all((subject.OUTPUT_DIR / name).exists() for name in subject.REQUIRED_FILES)
    for name in ["handoff.schema.json", "deployment_profile.schema.json", "receiver_acceptance.schema.json", "strategy_state.schema.json", "lifecycle_event.schema.json", "README.md"]:
        assert (subject.STANDARD_ROOT / name).exists()


def test_exact_next_action_is_not_executed() -> None:
    readiness = json.loads((subject.OUTPUT_DIR / "standardization_readiness.json").read_text(encoding="utf-8"))
    assert readiness["next_action"] == "pilot_import_validate_spdj_under_forward_observation_standard_v1"
    assert readiness["next_action_executed"] is False
