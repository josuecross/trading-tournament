from __future__ import annotations

import csv
import json
from pathlib import Path

from strategy_lab.research_os.research import strategy_library_discovery_yield_checkpoint_v1 as checkpoint


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_DIR = ROOT / "evidence" / "strategy_library_discovery_yield_checkpoint_v1" / "latest"


REQUIRED_FILES = {
    "discovery_yield_summary.md",
    "source_pipeline_funnel.csv",
    "source_candidate_stage_inventory.csv",
    "screen_and_validation_outcomes.csv",
    "failure_taxonomy.csv",
    "mechanism_level_results.csv",
    "preliminary_positive_vs_validated.csv",
    "blocked_source_analysis.csv",
    "exact_variants_closed.csv",
    "library_process_impact.csv",
    "source_intake_lessons.md",
    "next_source_eligibility_filter.md",
    "next_source_research_brief.md",
    "artifact_lineage.csv",
    "consistency_check.json",
}


def _read_csv(name: str) -> list[dict[str, str]]:
    with (EVIDENCE_DIR / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _read_json(name: str) -> dict:
    return json.loads((EVIDENCE_DIR / name).read_text(encoding="utf-8"))


def _run_checkpoint() -> dict:
    return checkpoint.run()


def test_checkpoint_writes_required_files_and_expected_funnel_counts() -> None:
    result = _run_checkpoint()

    assert result["status"] == "library_improves_process_but_not_candidate_yield_yet"
    assert result["next_action"] == "direction_owner_decision_required_for_next_external_source_research"
    for filename in REQUIRED_FILES:
        assert (EVIDENCE_DIR / filename).exists(), filename

    funnel = {row["metric"]: int(row["count"]) for row in _read_csv("source_pipeline_funnel.csv")}
    assert funnel["external_sources_reviewed"] == 18
    assert funnel["sources_with_complete_rules"] == 14
    assert funnel["sources_blocked_by_incomplete_rules"] == 4
    assert funnel["sources_blocked_by_data_or_wrapper_mapping"] == 1
    assert funnel["sources_blocked_by_execution_or_accounting_requirements"] == 0
    assert funnel["preregistrations_created"] == 11
    assert funnel["bounded_screens_completed"] == 11
    assert funnel["preliminary_positive_screens"] == 4
    assert funnel["candidates_receiving_broader_validation"] == 6
    assert funnel["candidates_remaining_interesting_after_validation"] == 0
    assert funnel["exact_variants_closed"] == 11
    assert funnel["candidates_promoted_or_activated"] == 0


def test_artifact_lineage_uses_existing_latest_valid_artifacts() -> None:
    _run_checkpoint()

    lineage = _read_csv("artifact_lineage.csv")
    assert lineage
    missing = [row["artifact_path"] for row in lineage if not (ROOT / row["artifact_path"]).exists()]
    assert missing == []

    consistency = _read_json("consistency_check.json")
    assert consistency["latest_artifacts_exist"] is True
    assert consistency["superseded_metrics_excluded"] is True
    assert consistency["registry_byte_identical"] is True
    assert consistency["active_vm_and_dsr_unchanged"] is True
    assert consistency["active_combo_benchmark_reference_only"] is True
    assert consistency["active_combo_unchanged"] is True


def test_superseded_and_validated_results_are_classified_conservatively() -> None:
    _run_checkpoint()

    prelim = {
        row["candidate_id"]: row
        for row in _read_csv("preliminary_positive_vs_validated.csv")
    }
    splv = prelim["splv_static_low_vol_factor_wrapper_v1"]
    assert splv["preliminary_positive_screen"] == "true"
    assert splv["validation_completed"] == "true"
    assert splv["validation_supported_further_review"] == "false"
    assert "initial_sampled_positive_separated_from_validation" in splv["supersession_note"]

    inventory = {
        row["candidate_id"]: row
        for row in _read_csv("source_candidate_stage_inventory.csv")
    }
    risk_parity = inventory["rp_ivol_10m_trend_etf_wrapper_adaptation_v1"]
    assert "portfolio_accounting_review" in risk_parity["authoritative_evidence_path"]
    assert "corrected drifting holdings accounting" in risk_parity["notes"].lower()

    pairs = inventory["etf_pairs_distance_12m_6m_2sd_v1"]
    assert pairs["primary_failure_reason"] == "borrow_cost_drag"
    assert pairs["secondary_failure_reason"] == "transaction_cost_drag"

    tom = inventory["spy_turn_of_month_bil_v1"]
    assert tom["latest_outcome"] == "calendar_effect_present_but_no_strategy_edge"
    assert tom["exact_variant_closed"] == "true"


def test_exact_closed_variants_are_not_routed_to_immediate_retest() -> None:
    _run_checkpoint()

    rows = _read_csv("exact_variants_closed.csv")
    assert len(rows) == 11
    assert all(row["closed_status"] == "closed_for_immediate_retesting" for row in rows)
    assert all(row["immediate_retest_suggested"] == "false" for row in rows)

    consistency = _read_json("consistency_check.json")
    assert consistency["no_exact_closed_variant_suggested_for_immediate_retest"] is True
    assert consistency["no_candidate_promoted"] is True
    assert consistency["promoted_or_activated_count"] == 0


def test_next_source_brief_is_a_filter_not_a_strategy_selection() -> None:
    _run_checkpoint()

    brief = (EVIDENCE_DIR / "next_source_research_brief.md").read_text(encoding="utf-8")
    assert "No specific strategy is selected or approved here." in brief
    assert "non_equity_or_cross_asset_portfolio_contribution_with_moderate_turnover" in brief

    consistency = _read_json("consistency_check.json")
    assert consistency["next_source_research_brief_count"] == 1


def test_generation_is_deterministic_for_core_outputs() -> None:
    _run_checkpoint()
    first = {
        name: (EVIDENCE_DIR / name).read_bytes()
        for name in ["source_pipeline_funnel.csv", "artifact_lineage.csv", "consistency_check.json"]
    }

    _run_checkpoint()
    second = {
        name: (EVIDENCE_DIR / name).read_bytes()
        for name in ["source_pipeline_funnel.csv", "artifact_lineage.csv", "consistency_check.json"]
    }

    assert first == second
    assert _read_json("consistency_check.json")["generation_is_deterministic"] is True
