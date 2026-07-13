from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "active_observation_evidence_reconciliation" / "latest"
VM_ID = "paper_forward_vm_quality_lowvol_proxy_v1"
DSR_ID = "paper_forward_dsr_sector_equal_weight_defensive_filter_v1"


def read_json(name: str):
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def read_csv(name: str):
    with (EVIDENCE / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_reconciliation_packet_exists() -> None:
    required = [
        "active_observation_evidence_reconciliation.json",
        "active_observation_evidence_reconciliation.md",
        "vm_quality_lowvol_proxy_v1_evidence_chain.csv",
        "dsr_sector_equal_weight_defensive_filter_v1_evidence_chain.csv",
        "artifact_lineage.csv",
        "missing_or_conflicting_evidence.csv",
        "superseded_evidence.csv",
        "reconciliation_consistency_check.json",
    ]
    for filename in required:
        assert (EVIDENCE / filename).exists(), filename


def test_only_two_active_observations_are_reconciled() -> None:
    manifest = read_json("active_observation_evidence_reconciliation.json")
    assert manifest["target_active_observation_ids"] == [VM_ID, DSR_ID]
    assert set(manifest["observations"]) == {VM_ID, DSR_ID}
    assert manifest["reconciliation_only"] is True


def test_vm_chain_classifies_e2_to_e6_conservatively() -> None:
    rows = read_csv("vm_quality_lowvol_proxy_v1_evidence_chain.csv")
    by_stage = {row["evidence_stage"]: row for row in rows}

    assert set(by_stage) == {"E2", "E3", "E4", "E5", "E6"}
    assert by_stage["E2"]["classification"] == "partial_existing_evidence"
    assert by_stage["E3"]["classification"] == "partial_existing_evidence"
    assert by_stage["E4"]["classification"] == "partial_existing_evidence"
    assert by_stage["E5"]["classification"] == "missing_existing_evidence"
    assert by_stage["E6"]["classification"] == "conversation_recovered_only"


def test_dsr_chain_keeps_material_mismatch_visible() -> None:
    rows = read_csv("dsr_sector_equal_weight_defensive_filter_v1_evidence_chain.csv")
    by_stage = {row["evidence_stage"]: row for row in rows}

    assert set(by_stage) == {"E2", "E3", "E4", "E5", "E6"}
    assert by_stage["E4"]["classification"] == "conflicting_existing_evidence"
    assert "material" in by_stage["E4"]["notes"].lower()


def test_missing_and_conflicting_evidence_is_reported() -> None:
    rows = read_csv("missing_or_conflicting_evidence.csv")
    assert rows
    assert any(row["active_observation_id"] == DSR_ID and row["issue_type"] == "conflicting_existing_evidence" for row in rows)
    assert any(row["evidence_stage"] == "E5" and "robustness" in row["requirements_or_conflict"] for row in rows)


def test_superseded_metrics_do_not_change_active_state() -> None:
    rows = read_csv("superseded_evidence.csv")
    assert {row["active_observation_id"] for row in rows} == {VM_ID, DSR_ID}
    assert all(row["superseded_scope"] == "conversation_recovered_quantitative_metrics_only" for row in rows)
    assert all(row["decision_effect"] == "does_not_change_canonical_active_state" for row in rows)
    dsr = next(row for row in rows if row["active_observation_id"] == DSR_ID)
    assert dsr["supersession_status"] == "historical_unverified_non_comparable_not_used_as_current_diagnostic_reference"
    assert "current_diagnostic_only" in dsr["notes"]


def test_config_matches_recovered_activation_but_not_independent_e6() -> None:
    manifest = read_json("active_observation_evidence_reconciliation.json")
    for active_id in [VM_ID, DSR_ID]:
        observation = manifest["observations"][active_id]
        assert observation["config_match"]["matches_recovered_activation_detail"] is True
        assert observation["highest_independently_verified_sel_level"] == "E1"
        assert observation["reconstructed_stages"]["E6"] == "conversation_recovered_only"


def test_guardrails_and_hashes_show_no_state_mutation() -> None:
    consistency = read_json("reconciliation_consistency_check.json")
    assert consistency["consistency_passed"] is True
    assert consistency["canonical_hashes_unchanged"] is True
    assert consistency["active_observation_ids_unchanged"] is True
    assert consistency["no_strategy_metrics_recomputed"] is True
    assert consistency["no_backtest_run"] is True
    assert consistency["no_source_artifact_rewritten"] is True
    assert consistency["no_lifecycle_state_changed"] is True
    assert consistency["no_paper_demo_state_changed"] is True


def test_no_sel_parser_change_or_evidence_inflation() -> None:
    manifest = read_json("active_observation_evidence_reconciliation.json")
    assert manifest["sel_parser_changed"] is False
    assert manifest["sel_deterministic_mappings_required"] == []
    assert all(
        observation["highest_independently_verified_sel_level"] == "E1"
        for observation in manifest["observations"].values()
    )
