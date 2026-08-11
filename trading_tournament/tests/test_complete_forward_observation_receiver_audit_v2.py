import csv
import json

from strategy_lab.research_os.research import complete_forward_observation_receiver_audit_v2 as subject


def rows(name: str) -> list[dict[str, str]]:
    with (subject.OUTPUT_DIR / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_audit_regenerates_deterministically() -> None:
    first = subject.run()
    second = subject.run()
    assert first["overall_pass"] is True
    assert second["overall_pass"] is True
    assert first["deterministic_audit_hash"] == second["deterministic_audit_hash"]


def test_prior_inventory_and_hash_reconcile() -> None:
    result = json.loads((subject.OUTPUT_DIR / "consistency_check.json").read_text(encoding="utf-8"))
    assert result["checks"]["prior_audit_hash_reconciles"] is True
    assert result["checks"]["exactly_15_unique_research_strategies"] is True


def test_receiver_counts_are_receiver_authoritative() -> None:
    counts = json.loads((subject.OUTPUT_DIR / "receiver_authoritative_counts.json").read_text(encoding="utf-8"))
    assert counts["receiver_application_strategy_registry_count"] == 4
    assert counts["receiver_registered"] == 2
    assert counts["receiver_imported"] == 0
    assert counts["receiver_validated"] == 2
    assert counts["paper_demo_initialized"] == 2
    assert counts["paper_demo_active"] == 2
    assert counts["paper_demo_paused_or_disabled"] == 0
    assert counts["microtrading_eligible"] == 0
    assert counts["microtrading_active"] == 0
    assert counts["receiver_not_found"] == 13
    assert counts["research_legacy_historical_counts"]["paper_demo_currently_active_in_legacy_research_evidence"] == 9


def test_aliases_are_explicit_and_unique() -> None:
    aliases = rows("strategy_identity_aliases.csv")
    assert len(aliases) == 2
    assert len({row["research_strategy_id"] for row in aliases}) == 2
    assert len({row["receiver_strategy_id"] for row in aliases}) == 2
    assert {row["identity_confidence"] for row in aliases} == {"high"}


def test_legacy_ambiguities_resolve_to_receiver_absence() -> None:
    reconciled = {row["research_strategy_id"]: row for row in rows("cross_repository_strategy_reconciliation.csv")}
    for strategy_id in {"SPY_200d_trend_model", "profit_combo_SPY200d_GLD_50_50_v1"}:
        assert reconciled[strategy_id]["receiver_state"] == "receiver_not_found"
        assert "resolved as absent" in reconciled[strategy_id]["receiver_state_caveat"]


def test_active_state_is_persisted_but_stale() -> None:
    active = [row for row in rows("cross_repository_strategy_reconciliation.csv") if row["paper_demo_active"] == "true"]
    assert len(active) == 2
    assert all("stale" in row["receiver_state_caveat"] for row in active)


def test_formal_handoff_compatibility_is_bounded() -> None:
    compatibility = {row["strategy_id"]: row["classification"] for row in rows("formal_handoff_compatibility.csv")}
    assert compatibility == {
        "internal_capture_asymmetry_63d_top3_v1": "requires_strategy_specific_adapter",
        "spdj_multi_asset_dynamic_inflation_etf_portability_v1": "receiver_architecture_incompatible",
    }


def test_migration_counts_reconcile() -> None:
    migration = rows("migration_matrix_v2.csv")
    counts: dict[str, int] = {}
    for row in migration:
        counts[row["classification"]] = counts.get(row["classification"], 0) + 1
    assert counts == {
        "contract_materialization_required": 11,
        "receiver_adapter_only": 2,
        "retirement_candidate_due_to_unreconciled_legacy_state": 2,
    }
    assert sum(row["active_legacy_contract_debt"] == "true" for row in migration) == 2

    decision = json.loads((subject.OUTPUT_DIR / "final_standardization_decision.json").read_text(encoding="utf-8"))
    assert decision["migration_counts"] == {
        "already_standard_compatible": 0,
        "field_mapping_only": 0,
        "receiver_adapter_only": 2,
        "contract_materialization_required": 11,
        "rule_reconstruction_required": 0,
        "retirement_candidate_due_to_unreconciled_legacy_state": 2,
    }


def test_standardization_and_next_action_are_exact() -> None:
    decision = json.loads((subject.OUTPUT_DIR / "final_standardization_decision.json").read_text(encoding="utf-8"))
    assert decision["audit_outcome"] == "forward_observation_receiver_audit_complete"
    assert decision["decision"] == "standardization_required_before_scaling"
    assert decision["common_schema_id"] == "forward_observation_handoff_standard_v1"
    assert decision["next_action"] == "implement_forward_observation_handoff_standard_v1"
    assert decision["next_action_executed"] is False


def test_receiver_architecture_classifications_are_recorded() -> None:
    assert "partial_target_execution_separation" in (subject.OUTPUT_DIR / "receiver_strategy_interface.md").read_text(encoding="utf-8")
    assert "partially_generic_state_contract" in (subject.OUTPUT_DIR / "receiver_state_contract.md").read_text(encoding="utf-8")
    assert "timing_model_material_gap" in (subject.OUTPUT_DIR / "receiver_timing_contract.md").read_text(encoding="utf-8")
    assert "manual_strategy_registration" in (subject.OUTPUT_DIR / "receiver_handoff_import_capability.md").read_text(encoding="utf-8")
    assert "microtrading_promotion_contract_missing" in (subject.OUTPUT_DIR / "microtrading_promotion_audit.md").read_text(encoding="utf-8")


def test_protected_state_and_safety_counts_pass() -> None:
    result = json.loads((subject.OUTPUT_DIR / "consistency_check.json").read_text(encoding="utf-8"))
    assert result["checks"]["protected_state_unchanged"] is True
    assert result["protected_state_before"] == result["protected_state_after"]
    assert result["network_market_data_calls"] == 0
    assert result["broker_calls"] == 0
    assert result["order_calls"] == 0
    assert result["current_target_calculations"] == 0
    assert result["observation_mutations"] == 0
    assert result["strategy_activations"] == 0
    assert result["microtrading_changes"] == 0


def test_all_required_artifacts_exist() -> None:
    assert all((subject.OUTPUT_DIR / name).exists() for name in subject.REQUIRED_FILES)
