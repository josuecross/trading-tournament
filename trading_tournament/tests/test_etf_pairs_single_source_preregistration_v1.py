from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest
import yaml

from strategy_lab.research_os.research import etf_pairs_single_source_preregistration_v1 as prereg


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "etf_pairs_single_source_preregistration_v1" / "latest"
INTAKE_PATH = (
    ROOT
    / "strategy_lab"
    / "research_os"
    / "public_strategy_sources"
    / "intake_candidates"
    / f"{prereg.SOURCE_ID}.yaml"
)


@pytest.fixture(scope="module", autouse=True)
def generated_packet() -> dict[str, object]:
    return prereg.run()


def read_json(name: str) -> dict[str, object]:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def read_csv(name: str) -> list[dict[str, str]]:
    with (EVIDENCE / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_required_artifacts_exist_and_no_preregistration_when_blocked() -> None:
    required = {
        "decision.json",
        "decision.md",
        "source_intake_record.yaml",
        "source_rule_extraction.csv",
        "source_support_trace.csv",
        "prior_pairs_and_spread_inventory.csv",
        "duplicate_gate.csv",
        "etf_universe_feasibility.csv",
        "short_accounting_feasibility.csv",
        "execution_and_cost_feasibility.csv",
        "material_distinction_review.csv",
        "missing_or_ambiguous_fields.csv",
        "consistency_check.json",
    }
    assert sorted(name for name in required if not (EVIDENCE / name).exists()) == []
    assert not (EVIDENCE / "preregistration.yaml").exists()
    assert not (EVIDENCE / "preregistration.md").exists()


def test_exactly_one_source_is_evaluated() -> None:
    decision = read_json("decision.json")
    assert INTAKE_PATH.exists()
    intake = yaml.safe_load(INTAKE_PATH.read_text(encoding="utf-8"))
    assert decision["source_count_evaluated"] == 1
    assert decision["source_id"] == prereg.SOURCE_ID
    assert decision["source_class"] == "academic_primary"
    assert intake["source"]["source_id"] == prereg.SOURCE_ID
    assert intake["strategy_description"]["strategy_family"] == prereg.FAMILY_ID


def test_no_backtest_or_provider_call_occurs() -> None:
    decision = read_json("decision.json")
    assert decision["no_backtest_run"] is True
    assert decision["strategy_implemented"] is False
    assert decision["no_provider_call"] is True
    assert decision["provider_download"] is False
    assert decision["intraday_data_used"] is False


def test_etf_universe_is_frozen_independently_of_performance() -> None:
    rows = read_csv("etf_universe_feasibility.csv")
    sector = next(row for row in rows if row["universe_id"] == "canonical_sector_etf_universe_from_active_dsr")
    assert sector["selection_basis"] == "existing fixed sector ETF universe in active strategy evidence recompute"
    assert sector["performance_selected"] == "false"
    assert sector["symbols"] == "|".join(prereg.SECTOR_UNIVERSE)
    assert sector["symbol_count"] == "10"
    assert sector["all_symbols_cache_ready"] == "true"


def test_leveraged_inverse_and_etn_products_are_excluded() -> None:
    rows = read_csv("etf_universe_feasibility.csv")
    sector = next(row for row in rows if row["universe_id"] == "canonical_sector_etf_universe_from_active_dsr")
    assert sector["leveraged_inverse_or_etn_present"] == "false"
    decision = read_json("decision.json")
    assert decision["leveraged_inverse_or_etn_excluded"] is True


def test_source_parameters_remain_fixed() -> None:
    rules = {row["rule_field"]: row for row in read_csv("source_rule_extraction.csv")}
    assert rules["formation_period"]["extracted_rule"] == "12 months"
    assert rules["trading_period"]["extracted_rule"] == "following six months"
    assert rules["entry_threshold"]["extracted_rule"] == "divergence greater than two formation-period spread standard deviations"
    assert rules["formation_period"]["classification"] == "source_explicit"
    assert rules["entry_threshold"]["classification"] == "source_explicit"
    decision = read_json("decision.json")
    assert decision["formation_months"] == 12
    assert decision["trading_months"] == 6
    assert decision["entry_threshold_standard_deviations"] == pytest.approx(2.0)


def test_same_close_execution_is_forbidden() -> None:
    rules = {row["rule_field"]: row for row in read_csv("source_rule_extraction.csv")}
    assert rules["delayed_execution"]["extracted_rule"] == "use delayed execution; same-close fills prohibited"
    decision = read_json("decision.json")
    assert decision["same_close_execution_forbidden"] is True


def test_long_and_short_legs_are_both_required() -> None:
    rules = {row["rule_field"]: row for row in read_csv("source_rule_extraction.csv")}
    assert "long relatively lower-priced" in rules["long_short_direction"]["extracted_rule"]
    assert "short relatively higher-priced" in rules["long_short_direction"]["extracted_rule"]
    decision = read_json("decision.json")
    assert decision["long_and_short_legs_required"] is True


def test_gross_and_net_exposure_convention_is_calculated_correctly() -> None:
    exposure = prereg.pair_sleeve_exposure()
    assert exposure["gross_exposure"] <= 1.0 + prereg.TOL
    assert exposure["net_exposure"] == pytest.approx(0.0)
    assert exposure["long_leg_weight"] == pytest.approx(abs(exposure["short_leg_weight"]))
    decision = read_json("decision.json")
    assert decision["gross_exposure_convention"] == pytest.approx(1.0)
    assert decision["net_exposure_convention"] == pytest.approx(0.0)


def test_unsupported_short_accounting_blocks_preregistration() -> None:
    decision = read_json("decision.json")
    assert decision["outcome"] == "source_not_ready"
    assert decision["blocker"] == "short_accounting_and_borrow_cost_model_missing"
    assert decision["short_accounting_supported"] is False
    assert decision["borrow_cost_assumption_available"] is False
    assert decision["preregistration_created"] is False
    rows = read_csv("short_accounting_feasibility.csv")
    blocking = [row for row in rows if row["blocks_preregistration"] == "true"]
    assert {row["requirement"] for row in blocking} >= {
        "negative_share_quantities",
        "long_short_mark_to_market_pnl",
        "short_entry_proceeds_and_cover_cash_flows",
        "borrow_cost",
    }


def test_no_prior_exact_variant_is_reopened() -> None:
    gate = read_csv("duplicate_gate.csv")
    assert all(row["prior_exact_match_found"] == "false" for row in gate)
    decision = read_json("decision.json")
    assert decision["exact_duplicate_found"] is False
    assert decision["no_prior_exact_variant_reopened"] is True


def test_material_distinction_is_reviewed_without_overriding_blocker() -> None:
    rows = read_csv("material_distinction_review.csv")
    assert rows
    assert all(row["distinct"] == "true" for row in rows)
    decision = read_json("decision.json")
    assert decision["objective_etf_universe_available"] is True
    assert decision["selected_feasible_universe_if_shorting_were_supported"] == "canonical_sector_etf_universe_from_active_dsr"
    assert decision["outcome"] == "source_not_ready"


def test_registry_and_active_observations_remain_unchanged() -> None:
    decision = read_json("decision.json")
    assert decision["registry_byte_identical"] is True
    assert decision["registry_hash_before"] == decision["registry_hash_after"]
    assert decision["active_observations_unchanged"] is True
    assert decision["active_observations_hash_before"] == decision["active_observations_hash_after"]
    assert decision["lifecycle_or_evidence_level_changed"] is False
    assert decision["promotion_or_paper_demo_activation"] is False


def test_consistency_check_passes() -> None:
    check = read_json("consistency_check.json")
    assert check["consistency_passed"] is True
    assert check["exactly_one_source_evaluated"] is True
    assert check["no_backtest_run"] is True
    assert check["no_provider_call"] is True
    assert check["etf_universe_frozen_independent_of_performance"] is True
    assert check["unsupported_short_accounting_blocks_preregistration"] is True
    assert check["formation_period_fixed_12_months"] is True
    assert check["trading_period_fixed_6_months"] is True
    assert check["entry_threshold_fixed_two_standard_deviations"] is True
    assert check["same_close_execution_forbidden"] is True
    assert check["long_and_short_legs_required"] is True


def test_generation_is_deterministic() -> None:
    first_decision = read_json("decision.json")
    first_missing = (EVIDENCE / "missing_or_ambiguous_fields.csv").read_text(encoding="utf-8")
    rerun = prereg.run()
    second_decision = read_json("decision.json")
    second_missing = (EVIDENCE / "missing_or_ambiguous_fields.csv").read_text(encoding="utf-8")
    assert rerun["consistency_passed"] is True
    assert second_decision == first_decision
    assert second_missing == first_missing
