from __future__ import annotations

import csv
import json
from pathlib import Path

from strategy_lab.research_os.research.low_volatility_factor_source_backed_preregistration_v1 import (
    ACTIVE_VM_ID,
    FAMILY_ID,
    SOURCE_ID,
    run,
)


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "low_volatility_factor_source_backed_preregistration_v1" / "latest"
REGISTRY = ROOT / "strategy_lab" / "strategy_registry.yaml"


def _json(name: str) -> dict:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def _csv(name: str) -> list[dict[str, str]]:
    with (EVIDENCE / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def setup_module() -> None:
    before = REGISTRY.read_bytes()
    run(ROOT)
    after = REGISTRY.read_bytes()
    assert after == before


def test_required_evidence_files_exist_and_partial_preregistration_absent() -> None:
    required = {
        "decision.json",
        "decision.md",
        "source_identity.csv",
        "source_rule_extraction.csv",
        "source_support_trace.csv",
        "active_vm_mechanism_fingerprint.csv",
        "prior_low_volatility_variant_fingerprints.csv",
        "material_distinction_review.csv",
        "etf_wrapper_feasibility.csv",
        "missing_or_ambiguous_fields.csv",
        "external_source_research_question.md",
        "consistency_check.json",
    }
    missing = sorted(name for name in required if not (EVIDENCE / name).exists())
    assert missing == []
    assert not (EVIDENCE / "preregistration.yaml").exists()
    assert not (EVIDENCE / "preregistration.md").exists()


def test_exactly_one_existing_low_volatility_source_is_evaluated() -> None:
    decision = _json("decision.json")
    assert decision["source_count_evaluated"] == 1
    assert decision["source_id"] == SOURCE_ID
    assert decision["family_id"] == FAMILY_ID
    assert decision["outcome"] == "external_source_research_required"
    assert decision["unique_associated_source"] is True

    source_identity = _csv("source_identity.csv")[0]
    assert source_identity["source_id"] == SOURCE_ID
    assert source_identity["next_discovery_rows"] == "1"
    assert source_identity["external_source_readiness_rows"] == "1"
    assert source_identity["external_public_source_backlog_rows"] == "1"


def test_material_source_rules_are_unresolved_and_block_preregistration() -> None:
    rows = {row["field"]: row for row in _csv("source_rule_extraction.csv")}
    unresolved = {
        "security_or_etf_selection_rule",
        "volatility_definition",
        "lookback_period",
        "ranking_direction",
        "number_or_proportion_selected",
        "weighting_rule",
        "rebalance_cadence",
        "entry_rule",
        "exit_or_replacement_rule",
        "risk_control_or_cash_behavior",
        "missing_data_behavior",
    }
    assert unresolved <= set(rows)
    assert all(rows[field]["classification"] == "unresolved" for field in unresolved)
    assert all(rows[field]["material"] == "true" for field in unresolved)

    decision = _json("decision.json")
    assert set(decision["blocking_fields"]) >= unresolved
    assert decision["preregistration_created"] is False


def test_no_active_vm_rule_fills_source_gap_and_active_vm_is_fingerprinted() -> None:
    decision = _json("decision.json")
    assert decision["active_vm_id"] == ACTIVE_VM_ID
    assert decision["active_vm_preserved"] is True
    assert decision["no_active_vm_rule_filled_source_gap"] is True

    rows = {row["dimension"]: row["active_vm_value"] for row in _csv("active_vm_mechanism_fingerprint.csv")}
    assert rows["strategy_id"] == "vm_quality_lowvol_proxy_v1"
    assert rows["status"] == "active_paper_demo_observation"
    assert rows["frozen"] == "true"
    assert "126-day return / 60-day realized volatility" in rows["ranking_signal"]
    assert rows["scales_total_equity_exposure_using_realized_volatility"].startswith("false")
    assert "cross-sectional ETF wrapper ranking" in rows["cross_sectional_or_single_asset"]


def test_material_distinction_is_not_claimed_without_source_rules() -> None:
    rows = _csv("material_distinction_review.csv")
    assert rows
    closest = rows[0]
    assert closest["closest_prior_strategy"] == ACTIVE_VM_ID
    assert closest["mechanism_based_distinction"] == "not_determinable_from_existing_source_record"
    assert closest["changed_dimensions_source_backed"] == "false"
    assert closest["decision"] == "external_source_research_required"


def test_prior_low_volatility_and_volatility_related_context_is_documented() -> None:
    rows = _csv("prior_low_volatility_variant_fingerprints.csv")
    names = {row["prior_strategy_or_family"] for row in rows}
    assert ACTIVE_VM_ID in names
    assert "lvq_lowvol_quality_top2_v1" in names
    assert "lvq_lowvol_quality_spy_regime_v1" in names
    assert "value_momentum_factor_etf_rotation_v1" in names
    assert "volatility_throttle_focused_research_lane_v1" in names


def test_cache_feasibility_is_checked_without_provider_download() -> None:
    rows = {row["local_etf_wrapper"]: row for row in _csv("etf_wrapper_feasibility.csv")}
    assert {"SPLV", "USMV", "SPY", "BIL"} <= set(rows)
    assert all(rows[symbol]["cache_ready"] == "true" for symbol in ("SPLV", "USMV", "SPY", "BIL"))
    assert all(rows[symbol]["feasibility_status"] == "cache_ready_but_rule_incomplete" for symbol in ("SPLV", "USMV", "SPY", "BIL"))

    decision = _json("decision.json")
    assert decision["no_provider_call"] is True
    assert decision["provider_download"] is False


def test_missing_fields_report_and_research_question_are_precise() -> None:
    missing = {row["field"]: row for row in _csv("missing_or_ambiguous_fields.csv")}
    assert "volatility_definition" in missing
    assert "entry_rule" in missing
    assert "rebalance_cadence" in missing
    assert "complete cited source rule" in missing["volatility_definition"]["source_evidence_absent"]

    question = (EVIDENCE / "external_source_research_question.md").read_text(encoding="utf-8")
    assert "volatility calculation" in question
    assert "active VM" in question
    assert "substitute a risky ETF inside active VM" in question


def test_no_backtest_strategy_state_or_paper_demo_change() -> None:
    decision = _json("decision.json")
    assert decision["no_backtest_or_performance_computation"] is True
    assert decision["no_strategy_implementation"] is True
    assert decision["candidate_exhaustive_run"] is False
    assert decision["paper_demo_activation"] is False
    assert decision["promotion"] is False
    assert decision["real_money_recommendation"] is False
    assert decision["no_registry_lifecycle_evidence_level_active_observation_or_paper_demo_state_change"] is True


def test_consistency_check_and_deterministic_result() -> None:
    first = run(ROOT)
    second = run(ROOT)
    assert first["outcome"] == second["outcome"]
    assert first["blocking_fields"] == second["blocking_fields"]

    check = _json("consistency_check.json")
    assert check["consistency_passed"] is True
    assert check["exactly_one_external_source_evaluated"] is True
    assert check["active_vm_remains_unchanged"] is True
    assert check["no_active_vm_rule_fills_source_rule_gap"] is True
    assert check["preregistration_absent_when_source_incomplete"] is True
    assert check["no_backtest_or_performance_computation"] is True
    assert check["drift_aware_holdings_accounting_required_later"] is True
    assert check["no_registry_or_lifecycle_state_change"] is True
    assert check["registry_hash_preserved"] is True
