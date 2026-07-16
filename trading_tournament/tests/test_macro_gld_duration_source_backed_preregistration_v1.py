from __future__ import annotations

import csv
import json
from pathlib import Path

from strategy_lab.research_os.research.macro_gld_duration_source_backed_preregistration_v1 import (
    CONFIRMED_SURVIVOR_IDS,
    OUTPUT_DIR,
    OUTCOME_SOURCE_RESEARCH_REQUIRED,
)


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / OUTPUT_DIR


def load_json(name: str):
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def csv_rows(name: str) -> list[dict[str, str]]:
    with (EVIDENCE / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_required_external_source_required_artifacts_exist() -> None:
    required = [
        "decision.json",
        "decision.md",
        "prior_variant_fingerprints.csv",
        "exact_variants_closed.csv",
        "relevant_source_readiness.csv",
        "material_distinction_review.csv",
        "external_source_research_question.md",
        "consistency_check.json",
    ]
    for name in required:
        assert (EVIDENCE / name).exists(), name
    assert not (EVIDENCE / "preregistration.yaml").exists()
    assert not (EVIDENCE / "preregistration.md").exists()


def test_decision_is_one_allowed_external_source_research_required_outcome() -> None:
    decision = load_json("decision.json")

    assert decision["family_id"] == "macro_gld_duration_risk_off"
    assert decision["outcome"] == OUTCOME_SOURCE_RESEARCH_REQUIRED
    assert decision["external_source_research_required"] is True
    assert decision["preregistration_created"] is False
    assert decision["candidate_source_count"] == 0
    assert decision["no_backtest_run"] is True
    assert decision["no_strategy_implementation"] is True
    assert decision["provider_download"] is False
    assert decision["promotion_or_paper_demo_change"] is False


def test_prior_tested_space_includes_bounded_recovered_and_adjacent_rows() -> None:
    rows = csv_rows("prior_variant_fingerprints.csv")
    ids = {row["variant_id"] for row in rows}

    assert len(rows) >= 18
    assert CONFIRMED_SURVIVOR_IDS.issubset(ids)
    assert "mgd_macro_mom126_top1_trend" in ids
    assert "mgd_static_gld_ief_bil_equal" in ids
    assert "gld_gror_balanced_momentum_clean_v1" in ids
    assert "gld_ief_spy_defensive_rotation_v1" in ids
    assert any(row["source_or_origin"] == "internal_bounded_design_after_lineage_recovery" for row in rows)
    assert any(row["source_or_origin"] == "recovered_internal_profit_batch_context" for row in rows)
    assert any(row["source_or_origin"].startswith("family_status:") for row in rows)


def test_exact_survivors_and_recovered_rows_remain_closed() -> None:
    rows = csv_rows("exact_variants_closed.csv")
    closed_ids = {row["variant_id"] for row in rows}

    assert CONFIRMED_SURVIVOR_IDS.issubset(closed_ids)
    assert "mgd_macro_mom126_top1_trend" in closed_ids
    assert "gld_gror_balanced_momentum_clean_v1" in closed_ids
    assert "gld_ief_spy_defensive_rotation_v1" in closed_ids
    assert all(row["may_reopen_exact_variant"] == "false" for row in rows)
    assert all(row["closure_scope"] == "exact_variant_only" for row in rows)


def test_relevant_source_readiness_has_no_complete_external_macro_source() -> None:
    rows = csv_rows("relevant_source_readiness.csv")

    assert rows
    assert any(row["source_id"] == "no_complete_external_public_macro_source_found" for row in rows)
    assert all(row["readiness_decision"] != "candidate_source_ready" for row in rows)
    assert all(row["materially_differs_from_prior_fingerprints"] == "false" for row in rows)
    assert any(row["source_class"] == "project_similarity_routing_context_not_external_source" for row in rows)


def test_material_distinction_failed_without_source_not_from_results() -> None:
    rows = csv_rows("material_distinction_review.csv")

    assert len(rows) == 1
    row = rows[0]
    assert row["candidate_source_id"] == "none"
    assert row["material_distinction_result"] == "failed_no_complete_external_source"
    assert row["economically_meaningful_difference"] == "not_proven"
    assert "would_be_high" in row["post_result_tuning_risk"]


def test_external_source_question_is_precise_and_constrained() -> None:
    text = (EVIDENCE / "external_source_research_question.md").read_text(encoding="utf-8")

    assert "credible public or academic/practitioner source" in text
    assert "`SPY`, `GLD`, `IEF`, `TLT`, and `BIL`" in text
    assert "risk-on and risk-off state definitions" in text
    assert "long-only, unlevered" in text
    assert "relabeled form of the four confirmed survivor rows" in text


def test_consistency_check_passes_strict_scope() -> None:
    consistency = load_json("consistency_check.json")

    assert consistency["consistency_passed"] is True
    assert consistency["all_known_historical_family_variants_represented"] is True
    assert consistency["all_four_confirmed_survivors_represented"] is True
    assert consistency["all_four_confirmed_survivors_closed_for_retest"] is True
    assert consistency["no_exact_survivor_or_rejected_row_reopened"] is True
    assert consistency["no_parameter_search_authorized"] is True
    assert consistency["no_result_driven_rule_combination"] is True
    assert consistency["source_lineage_explicit_if_preregistration_created"] is True
    assert consistency["every_rule_field_resolved_if_preregistration_created"] is True
    assert consistency["active_vm_dsr_unchanged"] is True
    assert consistency["active_combo_reference_only"] is True
    assert consistency["no_backtest_run"] is True
    assert consistency["no_external_source_fabricated"] is True
    assert consistency["exactly_one_allowed_outcome"] is True
