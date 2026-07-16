from __future__ import annotations

import csv
import json
from pathlib import Path

import yaml

from strategy_lab.research_os.research.risk_parity_trend_single_source_preregistration_v1 import (
    FAMILY_ID,
    SOURCE_ID,
    run,
)


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_DIR = ROOT / "evidence" / "risk_parity_trend_single_source_preregistration_v1" / "latest"
INTAKE_PATH = (
    ROOT
    / "strategy_lab"
    / "research_os"
    / "public_strategy_sources"
    / "intake_candidates"
    / f"{SOURCE_ID}.yaml"
)


def _json(name: str) -> dict:
    return json.loads((EVIDENCE_DIR / name).read_text(encoding="utf-8"))


def _csv(name: str) -> list[dict[str, str]]:
    with (EVIDENCE_DIR / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def setup_module() -> None:
    run()


def test_required_artifacts_exist_and_no_partial_preregistration_when_blocked() -> None:
    required = {
        "decision.json",
        "decision.md",
        "source_intake_record.yaml",
        "source_rule_extraction.csv",
        "source_support_trace.csv",
        "etf_wrapper_mapping.csv",
        "local_cache_feasibility.csv",
        "closest_prior_variants.csv",
        "material_distinction_review.csv",
        "missing_or_ambiguous_fields.csv",
        "consistency_check.json",
    }
    for name in required:
        assert (EVIDENCE_DIR / name).exists(), name
    assert not (EVIDENCE_DIR / "preregistration.yaml").exists()
    assert not (EVIDENCE_DIR / "preregistration.md").exists()


def test_exactly_one_external_source_is_evaluated_and_intake_record_is_created() -> None:
    assert INTAKE_PATH.exists()
    intake = yaml.safe_load(INTAKE_PATH.read_text(encoding="utf-8"))
    assert intake["source"]["source_id"] == SOURCE_ID
    assert intake["source"]["source_type"] == "academic_primary"
    assert intake["strategy_description"]["strategy_family"] == FAMILY_ID

    decision = _json("decision.json")
    assert decision["source_count_evaluated"] == 1
    assert decision["source_id"] == SOURCE_ID
    assert decision["family"] == FAMILY_ID
    assert decision["normalized_source_class"] == "academic_primary"
    assert decision["outcome"] == "source_not_ready"


def test_frozen_source_rules_are_recorded_with_provenance() -> None:
    rows = {row["rule_field"]: row for row in _csv("source_rule_extraction.csv")}
    assert rows["volatility_window"]["extracted_rule"] == "preceding 12 months"
    assert rows["volatility_window"]["classification"] == "source_explicit"
    assert "Section 3.1" in rows["volatility_window"]["support_reference"]
    assert rows["trend_window"]["extracted_rule"] == "10-month moving average"
    assert rows["trend_window"]["classification"] == "source_explicit"
    assert rows["risk_off_rule"]["classification"] == "source_explicit"
    assert "Treasury bills" in rows["risk_off_rule"]["extracted_rule"]


def test_below_trend_weight_moves_to_bil_not_redistributed() -> None:
    decision = _json("decision.json")
    assert decision["below_trend_weight_destination"] == "BIL"
    support_rows = {row["rule_field"]: row for row in _csv("source_support_trace.csv")}
    assert support_rows["risk_off_rule"]["supports_rule"] == "true"
    assert "source_explicit" == support_rows["risk_off_rule"]["classification"]


def test_no_leverage_or_shorting_or_parameter_search_is_introduced() -> None:
    decision = _json("decision.json")
    assert decision["no_leverage"] is True
    assert decision["no_shorting"] is True
    assert decision["no_backtest_run"] is True
    assert decision["no_parameter_search_authorized"] is True
    assert decision["no_strategy_implementation"] is True


def test_gld_is_not_used_as_broad_commodity_wrapper() -> None:
    mapping = _csv("etf_wrapper_mapping.csv")
    commodity_rows = [row for row in mapping if row["source_asset_class"] == "Broad commodities"]
    assert len(commodity_rows) == 1
    assert commodity_rows[0]["local_ticker"] == "DBC"
    assert commodity_rows[0]["local_ticker"] != "GLD"

    check = _json("consistency_check.json")
    assert check["gld_cannot_represent_broad_commodities"] is True


def test_missing_or_materially_non_equivalent_asset_classes_block_preregistration() -> None:
    decision = _json("decision.json")
    assert decision["blocker"] == "etf_wrapper_mapping_unavailable_or_materially_non_equivalent"
    assert "Government bonds" in decision["blocking_asset_classes"]
    assert "Global real estate" in decision["blocking_asset_classes"]
    assert decision["preregistration_created"] is False

    missing = {row["blocking_field"]: row for row in _csv("missing_or_ambiguous_fields.csv")}
    assert "etf_wrapper_mapping.Government bonds" in missing
    assert "etf_wrapper_mapping.Global real estate" in missing
    assert "direct cache-ready materially equivalent ETF wrapper" in missing["etf_wrapper_mapping.Government bonds"]["source_evidence_absent"]


def test_wrapper_table_rejects_silent_substitutions() -> None:
    mapping = {row["source_asset_class"]: row for row in _csv("etf_wrapper_mapping.csv")}
    assert mapping["Government bonds"]["mapping_status"] == "unavailable_materially_non_equivalent"
    assert mapping["Government bonds"]["local_ticker"] == ""
    assert "IEF/TLT" in mapping["Government bonds"]["material_differences_from_source_index"]
    assert mapping["Global real estate"]["mapping_status"] == "unavailable_materially_non_equivalent"
    assert "XLRE is US real estate only" in mapping["Global real estate"]["material_differences_from_source_index"]


def test_material_distinction_is_compared_with_existing_fingerprints() -> None:
    prior = _csv("closest_prior_variants.csv")
    names = {row["prior_variant_or_family"] for row in prior}
    assert "static_all_weather_benchmark_v1" in names
    assert "macro_gld_duration_risk_off_bounded_lane_v1 / MGD survivor rows" in names
    assert "multi_asset_trend_risk_control / top-N global asset rows" in names

    review = _csv("material_distinction_review.csv")[0]
    assert review["family"] == FAMILY_ID
    assert review["inverse_volatility_new_or_distinct"] == "true"
    assert review["mechanism_originates_in_supplied_source"] == "true"
    assert review["material_distinction_result"] == "provisionally_materially_distinct_but_mapping_blocked"


def test_no_lifecycle_evidence_level_active_observation_or_paper_demo_state_changes() -> None:
    decision = _json("decision.json")
    assert decision["no_lifecycle_or_paper_demo_state_change"] is True
    assert decision["provider_download"] is False
    assert decision["intraday_data_used"] is False
    assert decision["candidate_exhaustive_run"] is False
    assert decision["promotion_or_paper_demo_activation"] is False


def test_generation_is_deterministic_and_consistent() -> None:
    first = run()
    second = run()
    assert first["outcome"] == second["outcome"]
    assert first["blocking_asset_classes"] == second["blocking_asset_classes"]
    check = _json("consistency_check.json")
    assert check["consistency_passed"] is True
    assert check["exactly_one_external_source_evaluated"] is True
    assert check["risk_parity_uses_frozen_12_month_volatility_window"] is True
    assert check["trend_signal_uses_frozen_10_month_moving_average"] is True
    assert check["below_trend_weight_moves_to_bil"] is True
    assert check["missing_asset_classes_block_preregistration"] is True
    assert check["no_backtest_or_parameter_search"] is True
