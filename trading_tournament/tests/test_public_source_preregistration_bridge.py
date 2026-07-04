from __future__ import annotations

import json
from pathlib import Path

import yaml

from strategy_lab.research_os.research.public_source_preregistration_bridge import (
    DECISION_CONSTRAINT_BLOCKED,
    DECISION_DUPLICATE,
    DECISION_ELIGIBLE,
    DECISION_INCOMPLETE,
    DECISION_REVIEW,
    NEXT_ACTION,
    VALID_ELIGIBILITY_DECISIONS,
    evaluate_intake,
    find_constraint_blocks,
)


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "strategy_lab" / "research_os" / "public_strategy_sources"
EVIDENCE = ROOT / "evidence" / "research_recovery" / "public_source_preregistration_bridge" / "latest"


def load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_manifest() -> dict:
    return json.loads((EVIDENCE / "public_source_bridge_manifest.json").read_text(encoding="utf-8"))


def load_consistency() -> dict:
    return json.loads((EVIDENCE / "public_source_bridge_consistency_check.json").read_text(encoding="utf-8"))


def complete_synthetic_intake() -> dict:
    return {
        "schema_version": 1,
        "intake_status": "manual_source_supplied_for_validation",
        "source": {
            "source_name": "Synthetic manual source placeholder",
            "source_url_or_citation": "Manual citation supplied by owner",
            "source_type": "public academic",
            "source_evidence_public_context_only": True,
        },
        "strategy_description": {
            "strategy_family": "synthetic constraint test",
            "claimed_hypothesis": "test classifier only",
            "rule_clarity": "clear",
            "instruments": ["SPY", "BIL"],
            "timeframe": "daily",
        },
        "rules": {
            "entry_rule": "manual test entry",
            "exit_rule": "manual test exit",
            "ranking_selection_rule": "none",
            "rebalance_frequency": "monthly",
            "risk_controls": "none",
        },
        "data_and_execution": {
            "data_requirements": ["local daily adjusted close"],
            "execution_assumptions": "monthly rebalance using local cache only",
        },
        "project_screening": {
            "project_constraint_violations": [],
            "similar_already_tested_project_families": [],
            "do_not_retest_match": "none",
            "allowed_next_action": "source_intake_incomplete",
        },
        "governance": {
            "public_strategy_selected_by_user": True,
            "source_scraped_by_codex": False,
            "strategy_implemented": False,
            "backtest_run": False,
            "promotion_or_paper_forward_allowed": False,
        },
    }


def test_bridge_manifest_guardrails_and_prerequisites() -> None:
    manifest = load_manifest()
    consistency = load_consistency()

    assert manifest["public_source_preregistration_bridge_only"] is True
    assert manifest["blank_example_intake_created"] is True
    assert manifest["blank_intake_eligibility_decision"] == DECISION_INCOMPLETE
    assert set(manifest["valid_eligibility_decisions"]) == VALID_ELIGIBILITY_DECISIONS
    assert manifest["family_similarity_group_count"] == 12
    assert manifest["bt_control_poc_passed"] is True
    assert manifest["bt_multasset_poc_passed"] is True
    assert manifest["bt_adapter_target_weight_contract_validated"] is True
    assert manifest["can_accept_manual_public_source_later"] is True
    assert manifest["can_route_to_future_bounded_bt_design_after_complete_intake"] is True
    assert manifest["bounded_bt_design_created"] is False
    assert manifest["next_action"] == NEXT_ACTION
    assert consistency["consistency_passed"] is True


def test_no_public_strategy_scrape_backtest_or_execution_paths() -> None:
    manifest = load_manifest()

    assert manifest["public_strategy_selected"] is False
    assert manifest["public_source_scraped"] is False
    assert manifest["public_strategy_list_ingested"] is False
    assert manifest["public_strategy_implemented"] is False
    assert manifest["strategy_backtest_run"] is False
    assert manifest["strategy_discovery_run"] is False
    assert manifest["new_strategy_discovery_run"] is False
    assert manifest["broad_research_batch_run"] is False
    assert manifest["new_research_batch_run"] is False
    assert manifest["provider_download"] is False
    assert manifest["intraday_data_used"] is False
    assert manifest["new_packages_installed"] is False
    assert manifest["candidate_exhaustive_run"] is False
    assert manifest["promotion_candidates_created"] is False
    assert manifest["best_single_variant_promoted"] is False
    assert manifest["paper_forward_activation"] is False
    assert manifest["new_paper_forward_candidate_created"] is False
    assert manifest["broker_api_called"] is False
    assert manifest["broker_orders_submitted"] is False
    assert manifest["broker_orders_cancelled"] is False
    assert manifest["broker_orders_reconciled"] is False
    assert manifest["live_orders"] is False
    assert manifest["real_money_recommendation"] is False
    assert manifest["current_backtester_replaced"] is False
    assert manifest["public_source_presence_is_profitability_proof"] is False
    assert manifest["outputs_diagnostic_only"] is True


def test_yaml_template_filter_and_family_map_exist_and_are_bounded() -> None:
    intake = load_yaml(SOURCE_DIR / "public_strategy_source_intake_template.yaml")
    constraint_filter = load_yaml(SOURCE_DIR / "public_strategy_constraint_filter.yaml")
    family_map = load_yaml(SOURCE_DIR / "project_family_similarity_map.yaml")

    assert intake["intake_status"] == "blank_template_manual_input_required"
    assert intake["governance"]["public_strategy_selected_by_user"] is False
    assert intake["governance"]["source_scraped_by_codex"] is False
    assert intake["governance"]["strategy_implemented"] is False
    assert "source.source_name" in constraint_filter["required_complete_intake_fields"]
    prohibited = constraint_filter["hard_constraint_blocks"]["prohibited_data_or_instrument_features"]
    for item in ["intraday_data", "options", "futures", "leverage", "shorting", "margin", "forex", "crypto"]:
        assert item in prohibited

    family_keys = {row["family_key"] for row in family_map["families"]}
    assert {
        "volatility_throttle_volatility_managed_equity",
        "macro_gld_duration_risk_off",
        "commodity_basket_etf_momentum",
        "high_return_tactical_equity",
        "global_multi_asset",
        "turn_of_month_calendar_effect",
        "mean_reversion_rejected_or_existing_candidate",
        "spy200d_trend_control",
        "low_volatility_quality_proxy",
        "regional_international_momentum",
        "managed_futures_etf_wrapper",
        "crypto_deferred",
    } == family_keys


def test_required_evidence_outputs_exist() -> None:
    required = [
        "public_source_bridge_summary.md",
        "intake_template_validation.md",
        "constraint_filter_validation.md",
        "family_similarity_mapping_report.md",
        "public_family_exclusion_map.csv",
        "preregistration_eligibility_report.md",
        "blank_intake_evaluation.json",
        "local_cache_symbol_inventory.csv",
        "adapter_readiness_report.md",
        "guardrail_checklist.json",
        "public_source_bridge_next_action.md",
    ]
    for filename in required:
        assert (EVIDENCE / filename).exists(), filename

    blank_eval = json.loads((EVIDENCE / "blank_intake_evaluation.json").read_text(encoding="utf-8"))
    assert blank_eval["eligibility_decision"] == DECISION_INCOMPLETE
    assert blank_eval["blank_required_field_count"] > 0


def test_classifier_blocks_constraints_duplicates_and_allows_clean_manual_intake() -> None:
    constraint_filter = load_yaml(SOURCE_DIR / "public_strategy_constraint_filter.yaml")
    family_map = load_yaml(SOURCE_DIR / "project_family_similarity_map.yaml")

    clean = complete_synthetic_intake()
    assert evaluate_intake(clean, constraint_filter, family_map, ROOT)["eligibility_decision"] == DECISION_ELIGIBLE

    intraday = complete_synthetic_intake()
    intraday["data_and_execution"]["data_requirements"] = ["intraday_data"]
    assert evaluate_intake(intraday, constraint_filter, family_map, ROOT)["eligibility_decision"] == DECISION_CONSTRAINT_BLOCKED

    missing_symbol = complete_synthetic_intake()
    missing_symbol["strategy_description"]["instruments"] = ["SPY", "NOT_A_SYMBOL"]
    assert (
        evaluate_intake(missing_symbol, constraint_filter, family_map, ROOT)["eligibility_decision"]
        == DECISION_CONSTRAINT_BLOCKED
    )

    duplicate = complete_synthetic_intake()
    duplicate["strategy_description"]["strategy_family"] = "global multi asset"
    duplicate["strategy_description"]["claimed_hypothesis"] = "global tactical asset allocation top N ETF momentum"
    assert evaluate_intake(duplicate, constraint_filter, family_map, ROOT)["eligibility_decision"] == DECISION_DUPLICATE

    mean_reversion = complete_synthetic_intake()
    mean_reversion["strategy_description"]["strategy_family"] = "short_term_equity_mean_reversion"
    mean_reversion["rules"]["entry_rule"] = "Enter when RSI(2) is oversold."
    assert evaluate_intake(mean_reversion, constraint_filter, family_map, ROOT)["eligibility_decision"] == DECISION_REVIEW

    golden_cross = complete_synthetic_intake()
    golden_cross["strategy_description"]["strategy_family"] = "moving_average_trend_crossover"
    golden_cross["rules"]["entry_rule"] = "Enter SPY after a golden cross of the 50-day moving average above the 200-day moving average."
    assert evaluate_intake(golden_cross, constraint_filter, family_map, ROOT)["eligibility_decision"] == DECISION_DUPLICATE


def test_constraint_filter_does_not_block_negated_prohibited_features() -> None:
    constraint_filter = load_yaml(SOURCE_DIR / "public_strategy_constraint_filter.yaml")
    clean = complete_synthetic_intake()
    clean["data_and_execution"]["execution_assumptions"] = (
        "monthly rebalance only; no options/futures; no shorting; no leverage"
    )
    clean["rules"]["risk_controls"] = "long-only; no margin; no derivatives"

    assert find_constraint_blocks(clean, constraint_filter, ROOT) == []

    blocked = complete_synthetic_intake()
    blocked["data_and_execution"]["execution_assumptions"] = "requires leverage and options"
    assert "leverage" in find_constraint_blocks(blocked, constraint_filter, ROOT)
    assert "options" in find_constraint_blocks(blocked, constraint_filter, ROOT)
