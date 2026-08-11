import csv
import json
from pathlib import Path

from strategy_lab.research_os.research import (
    audit_forward_observation_handoff_inventory_and_contract_standardization_v1 as subject,
)


def read_csv(name: str) -> list[dict[str, str]]:
    with (subject.OUTPUT_DIR / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_serial_audit_passes_and_is_deterministic() -> None:
    first = subject.run()
    second = subject.run()
    assert first["overall_pass"] is True
    assert second["overall_pass"] is True
    assert first["deterministic_audit_hash"] == second["deterministic_audit_hash"]


def test_lifecycle_counts_are_explicit_and_reconciled() -> None:
    counts = json.loads((subject.OUTPUT_DIR / "lifecycle_counts.json").read_text(encoding="utf-8"))
    assert counts["total_forward_relevant_strategies"] == 15
    assert counts["research_eligible"] == 11
    assert counts["handoff_exported"] == 2
    assert counts["receiver_imported"] == 0
    assert counts["receiver_validated"] == 0
    assert counts["paper_demo_initialized"] == 11
    assert counts["paper_demo_active"] == 11
    assert counts["paper_demo_currently_active"] == 9
    assert counts["microtrading_eligible"] == 0
    assert counts["microtrading_active"] == 0
    assert counts["legacy_stage_ambiguous"] == 2
    assert sum(counts["current_exclusive_stage_counts"].values()) == 15


def test_inventory_has_unique_strategies_and_no_controls() -> None:
    rows = read_csv("strategy_lifecycle_inventory.csv")
    ids = [row["strategy_id"] for row in rows]
    assert len(ids) == len(set(ids)) == 15
    assert "SPY_buy_hold" not in ids
    assert "BIL_cash_proxy" not in ids
    assert "current_no_cash_proxy_alpha_AB" not in ids


def test_exports_are_not_miscounted_as_receiver_imports() -> None:
    rows = read_csv("strategy_lifecycle_inventory.csv")
    exported = [row for row in rows if row["handoff_id"]]
    assert len(exported) == 2
    assert {row["current_exclusive_stage"] for row in exported} == {"handoff_exported_not_imported"}
    assert {row["receiver_import_status"] for row in exported} == {"forward_application_evidence_unavailable"}


def test_contract_classifications_are_bounded() -> None:
    rows = read_csv("strategy_contract_completeness.csv")
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["classification"]] = counts.get(row["classification"], 0) + 1
    assert counts == {
        "contract_complete_machine_executable": 1,
        "contract_complete_but_adapter_required": 1,
        "legacy_contract_not_formalized": 13,
    }


def test_receiver_compatibility_is_not_fabricated() -> None:
    rows = read_csv("receiver_compatibility_matrix.csv")
    assert len(rows) == 15
    assert {row["receiver_classification"] for row in rows} == {"receiver_not_auditable_application_unavailable"}


def test_package_schemas_and_hashes_reconcile() -> None:
    rows = read_csv("handoff_package_inventory.csv")
    assert {(row["schema_name"], row["schema_version"]) for row in rows} == {
        ("legacy_internal_capture_handoff", "1"),
        ("spdj_forward_observation_handoff_schema_v1", "v1"),
    }
    consistency = json.loads((subject.OUTPUT_DIR / "consistency_check.json").read_text(encoding="utf-8"))
    assert consistency["checks"]["internal_semantic_hash_reconciles"] is True
    assert consistency["checks"]["spdj_package_hash_reconciles"] is True


def test_standardization_decision_and_microtrading_boundary() -> None:
    decision = json.loads((subject.OUTPUT_DIR / "standardization_decision.json").read_text(encoding="utf-8"))
    assert decision["decision"] == "standardization_required_before_scaling"
    assert decision["existing_schema_count"] == 2
    assert decision["machine_executable_contract_count"] == 1
    assert decision["human_interpretation_required_count"] == 13
    assert decision["material_contract_gap_count"] == 13
    assert decision["execution_boundary_gap"] == "execution_boundary_standardization_gap"
    assert decision["microtrading_promotion_contract_status"] == "microtrading_promotion_contract_missing"


def test_migration_scope_reconciles_all_strategies() -> None:
    rows = read_csv("migration_scope.csv")
    strategy_scopes = {"native_or_no_material_rule_change", "adapter_and_fixture_enrichment", "contract_materialization", "research_rule_reconstruction"}
    assert sum(int(row["strategy_count"]) for row in rows if row["scope"] in strategy_scopes) == 15


def test_required_files_exist_and_are_repo_relative() -> None:
    consistency = json.loads((subject.OUTPUT_DIR / "consistency_check.json").read_text(encoding="utf-8"))
    assert consistency["checks"]["all_required_files_exist"] is True
    assert consistency["hygiene"]["absolute_path_hits"] == []
    assert consistency["hygiene"]["secret_hits"] == []


def test_exact_incomplete_outcome_and_next_action() -> None:
    consistency = json.loads((subject.OUTPUT_DIR / "consistency_check.json").read_text(encoding="utf-8"))
    assert consistency["outcome"] == "forward_observation_handoff_audit_incomplete"
    assert consistency["next_action"] == "direction_owner_supply_forward_application_evidence_for_handoff_audit_v1"
    assert consistency["next_action_executed"] is False


def test_protected_state_is_unchanged() -> None:
    consistency = json.loads((subject.OUTPUT_DIR / "consistency_check.json").read_text(encoding="utf-8"))
    assert consistency["checks"]["protected_state_unchanged"] is True
    assert consistency["protected_state_before"] == consistency["protected_state_after"]


def test_no_backtest_network_broker_or_observation_mutation() -> None:
    consistency = json.loads((subject.OUTPUT_DIR / "consistency_check.json").read_text(encoding="utf-8"))
    assert consistency["strategy_backtests_run"] == 0
    assert consistency["network_calls"] == 0
    assert consistency["broker_calls"] == 0
    assert consistency["observation_mutations"] == 0
    assert consistency["microtrading_actions"] == 0
