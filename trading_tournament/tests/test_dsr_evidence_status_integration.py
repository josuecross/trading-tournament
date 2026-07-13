from __future__ import annotations

import csv
import json
from pathlib import Path

from strategy_lab.research_os.research.dsr_evidence_status import DSR_ACTIVE_ID, load_dsr_evidence_status
from strategy_lab.research_os.research.dsr_evidence_status_integration import run_dsr_evidence_status_integration


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "dsr_evidence_status_integration" / "latest"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path):
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_conservative_dsr_status_fallback_when_packet_missing(tmp_path: Path) -> None:
    status = load_dsr_evidence_status(tmp_path)

    assert status["source_packet_valid"] is False
    assert status["historical_recovered_metrics"]["best_final_equity"] == 4071.04
    assert status["historical_metric_evidence_status"] == "unverified_non_comparable"
    assert status["current_diagnostic_metrics"]["best_final_equity"] == "unknown"
    assert status["metric_eligible_for_evidence_stage"]["E4"] is False
    assert status["canonical_lifecycle_status"] == "active"
    assert status["highest_independent_sel_level"] == "E1"


def test_sel_dsr_decision_separates_lifecycle_and_metric_evidence() -> None:
    decisions = read_json(ROOT / "evidence" / "strategy_evidence_library" / "latest" / "sel_decisions.json")
    dsr = next(row for row in decisions if row["variant_id"] == DSR_ACTIVE_ID)

    assert dsr["project_status"] == "active"
    assert dsr["canonical_lifecycle_status"] == "active"
    assert dsr["evidence_level"] == "E1"
    assert dsr["verified_evidence_level"] == "E1"
    assert dsr["missing_evidence_stages"] == ["E2", "E3", "E4", "E5", "E6"]
    assert dsr["historical_recovered_metrics"]["best_final_equity"] == 4071.04
    assert dsr["historical_metric_evidence_status"] == "unverified_non_comparable"
    assert dsr["current_diagnostic_metrics"]["best_final_equity"] == 3481.6998
    assert dsr["current_diagnostic_role"] == "current_sampled_window_diagnostic"
    assert dsr["metric_comparability"] == "non_comparable"
    assert dsr["metric_eligible_for_evidence_stage"]["E4"] is False
    assert "not_qualifying_e4" in dsr["evidence_warning"]
    assert dsr["source_artifact_provenance"]


def test_dashboard_dsr_metric_warning_is_present_without_deactivation() -> None:
    manifest = read_json(ROOT / "evidence" / "research_state" / "latest" / "research_state_manifest.json")
    active_rows = read_csv(ROOT / "evidence" / "research_state" / "latest" / "active_observations.csv")
    dsr_row = next(row for row in active_rows if row["strategy"] == DSR_ACTIVE_ID)

    assert manifest["dsr_historical_metric_evidence_status"] == "unverified_non_comparable"
    assert manifest["dsr_current_diagnostic_evidence_status"] == "reproducible_diagnostic_only"
    assert manifest["dsr_metric_eligible_for_e4"] is False
    assert manifest["dsr_highest_independent_sel_level"] == "E1"
    assert dsr_row["status"] == "active_paper_demo_observation"
    assert dsr_row["paper_forward_active"] == "True"
    assert "unverified_non_comparable" in dsr_row["notes"]
    assert "reproducible_diagnostic_only" in dsr_row["notes"]


def test_integration_packet_exists_and_has_zero_unsafe_references() -> None:
    result = run_dsr_evidence_status_integration(ROOT)
    manifest = read_json(EVIDENCE / "dsr_evidence_status_integration.json")
    consistency = read_json(EVIDENCE / "integration_consistency_check.json")
    refs = read_csv(EVIDENCE / "remaining_unsafe_references.csv")

    assert result["consistency_passed"] is True
    assert manifest["target_active_observation_id"] == DSR_ACTIVE_ID
    assert manifest["historical_metric_evidence_status"] == "unverified_non_comparable"
    assert manifest["current_diagnostic_evidence_status"] == "reproducible_diagnostic_only"
    assert manifest["unsafe_unresolved_reference_count"] == 0
    assert consistency["integration_consistency_passed"] is True
    assert refs
    assert not [row for row in refs if row["unsafe_unresolved"] == "True"]


def test_metric_consumer_inventory_and_classification_are_complete() -> None:
    run_dsr_evidence_status_integration(ROOT)
    inventory = read_csv(EVIDENCE / "metric_consumer_inventory.csv")
    classifications = read_csv(EVIDENCE / "metric_classification.csv")
    changes = read_csv(EVIDENCE / "consumer_changes.csv")

    paths = {row["consumer_path"] for row in inventory}
    assert "strategy_lab/research_os/strategy_evidence_library/builder.py" in paths
    assert "run_research_state_dashboard.py" in paths
    assert "run_advisor_consistency_check.py" in paths
    assert {row["evidence_status"] for row in classifications} == {
        "unverified_non_comparable",
        "reproducible_diagnostic_only",
    }
    assert all(row["decision_effect"] for row in changes)
