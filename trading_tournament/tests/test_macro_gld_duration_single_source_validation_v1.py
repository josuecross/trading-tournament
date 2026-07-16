from __future__ import annotations

import csv
import json
from pathlib import Path

from strategy_lab.research_os.research.macro_gld_duration_single_source_validation_v1 import run


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_DIR = ROOT / "evidence" / "macro_gld_duration_single_source_validation_v1" / "latest"
INTAKE_DIR = ROOT / "strategy_lab" / "research_os" / "public_strategy_sources" / "intake_candidates"
FAMILY_ID = "macro_gld_duration_risk_off"


def _json(name: str) -> dict:
    return json.loads((EVIDENCE_DIR / name).read_text(encoding="utf-8"))


def _csv(name: str) -> list[dict[str, str]]:
    with (EVIDENCE_DIR / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def setup_module() -> None:
    run()


def test_required_artifacts_exist_and_no_partial_preregistration() -> None:
    required = {
        "decision.json",
        "decision.md",
        "source_rule_extraction.csv",
        "source_support_trace.csv",
        "etf_wrapper_mapping.csv",
        "material_distinction_review.csv",
        "missing_or_ambiguous_fields.csv",
        "consistency_check.json",
    }
    for name in required:
        assert (EVIDENCE_DIR / name).exists(), name
    assert not (EVIDENCE_DIR / "preregistration.yaml").exists()
    assert not (EVIDENCE_DIR / "preregistration.md").exists()


def test_no_declared_macro_gld_source_packet_is_blocked_without_inference() -> None:
    decision = _json("decision.json")
    assert decision["family_id"] == FAMILY_ID
    assert decision["outcome"] == "source_not_ready"
    assert decision["blocker"] == "no_clearly_identifiable_single_new_source_packet"
    assert decision["source_packet_count"] == 0
    assert decision["source_ids_evaluated"] == []
    assert decision["preregistration_created"] is False
    assert decision["source_not_ready"] is True
    assert decision["missing_or_ambiguous_field_count"] >= 1
    assert decision["next_action"] == "supply_exactly_one_complete_macro_gld_duration_external_source_packet"


def test_exactly_one_source_requirement_is_enforced_against_current_intake_directory() -> None:
    declared_macro_packets = []
    for path in INTAKE_DIR.glob("*.yaml"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        if f"strategy_family: {FAMILY_ID}" in text or f'strategy_family: "{FAMILY_ID}"' in text:
            declared_macro_packets.append(path.name)
    assert declared_macro_packets == []

    check = _json("consistency_check.json")
    assert check["exactly_one_source_evaluated"] is False
    assert check["blocked_when_no_or_multiple_sources"] is True
    assert check["consistency_passed"] is True


def test_rule_extraction_records_missing_fields_instead_of_silent_inference() -> None:
    rows = _csv("source_rule_extraction.csv")
    assert rows
    assert {row["source_id"] for row in rows} == {"none"}
    assert {row["source_supported"] for row in rows} == {"false"}
    assert {row["status"] for row in rows} == {"missing_no_declared_macro_gld_source_packet"}
    required_fields = {
        "source_id",
        "source_name",
        "source_url_or_citation",
        "source_type",
        "author_or_authors",
        "publication_date",
        "entry_rule",
        "exit_rule",
        "risk_on_definition",
        "risk_off_definition",
        "gold_allocation_or_selection",
        "duration_allocation_or_selection",
        "lookbacks_and_parameters",
        "rebalance_cadence",
        "weighting",
        "bil_cash_fallback",
        "missing_signal_behavior",
        "signal_timestamp",
        "execution_timestamp",
    }
    assert required_fields.issubset({row["field"] for row in rows})


def test_similarity_references_are_not_treated_as_source_packets() -> None:
    support_rows = _csv("source_support_trace.csv")
    assert len(support_rows) == 1
    row = support_rows[0]
    assert row["source_id"] == "none"
    assert row["supports_rule"] == "false"
    assert "No YAML intake candidate declares" in row["notes"]
    assert "Similarity-only references" in row["notes"]


def test_wrapper_mapping_is_context_only_and_does_not_create_a_source_translation() -> None:
    rows = _csv("etf_wrapper_mapping.csv")
    wrappers = {row["project_etf_wrapper"]: row for row in rows}
    assert {"SPY", "GLD", "TLT", "IEF", "BIL"}.issubset(wrappers)
    assert all(row["mapping_directness"] == "not_evaluated_no_source_packet" for row in rows)
    assert all(row["local_cache_status"] == "cache_ready" for row in rows)


def test_material_distinction_is_not_claimed_without_a_source() -> None:
    rows = _csv("material_distinction_review.csv")
    assert len(rows) == 1
    row = rows[0]
    assert row["source_id"] == "none"
    assert row["material_distinction_result"] == "blocked_no_source_packet"
    assert row["materially_changed_mechanism"] == "not_proven"
    assert "mgd_bounded_canary_defensive_top1_126_v1" in row["closest_prior_variant"]


def test_missing_field_blocker_is_precise_and_actionable() -> None:
    rows = _csv("missing_or_ambiguous_fields.csv")
    assert len(rows) == 1
    row = rows[0]
    assert row["blocking_field"] == "single_new_source_packet"
    assert "No clearly identifiable new intake packet" in row["blocking_reason"]
    assert "Supply exactly one YAML packet" in row["resolution_question"]


def test_guardrails_and_prior_variant_closure_are_preserved() -> None:
    decision = _json("decision.json")
    check = _json("consistency_check.json")
    assert decision["no_parameter_search_authorized"] is True
    assert decision["no_backtest_run"] is True
    assert decision["no_strategy_implementation"] is True
    assert decision["no_lifecycle_or_paper_demo_state_change"] is True
    assert decision["provider_download"] is False
    assert decision["intraday_data_used"] is False
    assert decision["candidate_exhaustive_run"] is False
    assert decision["real_money_recommendation"] is False
    assert check["closed_variants_remain_closed"] is True
    assert check["no_parameter_search_or_backtest_authorized"] is True
    assert check["no_lifecycle_or_paper_demo_state_changes"] is True
