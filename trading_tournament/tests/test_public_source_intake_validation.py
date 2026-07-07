from __future__ import annotations

import json
from pathlib import Path

from strategy_lab.research_os.research.public_source_intake_validation import (
    DECISION_ELIGIBLE,
    DECISION_INCOMPLETE,
    DECISION_REVIEW,
    evaluate_candidate,
    next_action_for,
    read_yaml,
)
from strategy_lab.research_os.research.public_source_preregistration_bridge import (
    CONSTRAINT_FILTER_PATH,
    FAMILY_MAP_PATH,
    is_missing,
)


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "research_recovery" / "public_source_intake_validation" / "latest"


def load_manifest() -> dict:
    return json.loads((EVIDENCE / "public_source_intake_validation_manifest.json").read_text(encoding="utf-8"))


def load_consistency() -> dict:
    return json.loads(
        (EVIDENCE / "public_source_intake_validation_consistency_check.json").read_text(encoding="utf-8")
    )


def complete_synthetic_intake(rule_clarity: str = "clear") -> dict:
    return {
        "schema_version": 1,
        "intake_status": "manual_source_supplied_for_validation",
        "source": {
            "source_name": "Synthetic manual public source",
            "source_url_or_citation": "Manual citation supplied by owner",
            "source_type": "public article",
            "source_evidence_public_context_only": True,
        },
        "strategy_description": {
            "strategy_family": "synthetic nonduplicate public source",
            "claimed_hypothesis": "test bounded-design routing only",
            "rule_clarity": rule_clarity,
            "instruments": ["SPY", "BIL"],
            "timeframe": "daily",
        },
        "rules": {
            "entry_rule": "Use a frozen synthetic entry rule for unit testing",
            "exit_rule": "Use a frozen synthetic exit rule for unit testing",
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


def test_manifest_records_selected_bollinger_squeeze_candidate_as_review_required_intake() -> None:
    manifest = load_manifest()
    consistency = load_consistency()

    assert manifest["public_source_intake_validation_only"] is True
    assert manifest["candidate_file_count"] == 1
    assert manifest["manual_source_supplied"] is True
    assert manifest["source_id"] == "bollinger_band_squeeze_breakout"
    assert manifest["intake_candidate_path"].endswith("bollinger_band_squeeze_breakout.yaml")
    assert manifest["eligibility_decision"] == DECISION_REVIEW
    assert manifest["next_action"] == "direction_owner_review_required_for_public_source_intake"
    assert manifest["exact_missing_fields"] == []
    assert manifest["local_cache_checked"] is True
    assert manifest["rule_clarity_status"] == "unclear_or_not_freezable"
    assert manifest["long_only_adaptation_status"] == "long_only_caveat_explicit"
    assert manifest["setup_definition_completeness_status"] == (
        "needs_direction_owner_review_six_month_low_threshold_not_freezable"
    )
    assert manifest["directional_confirmation_completeness_status"] == (
        "needs_direction_owner_review_extra_confirmation_not_source_backed_enough_to_freeze"
    )
    assert manifest["exit_rule_completeness_status"] == (
        "needs_direction_owner_review_exit_rule_not_source_backed_enough_to_freeze"
    )
    assert manifest["indicator_defaults_completeness_status"] == (
        "bollinger_defaults_source_backed_setup_exit_review_required"
    )
    assert "low_volatility_quality_proxy" in manifest["family_similarity_hits"]
    assert "spy200d_trend_control" in manifest["family_similarity_hits"]
    assert "global_multi_asset" in manifest["family_similarity_hits"]
    assert "macro_gld_duration_risk_off" in manifest["family_similarity_hits"]
    assert "high_return_tactical_equity" in manifest["family_similarity_hits"]
    assert "volatility_throttle_volatility_managed_equity" in manifest["family_similarity_hits"]
    assert "turn_of_month_calendar_effect" in manifest["family_similarity_hits"]
    assert "mean_reversion_rejected_or_existing_candidate" in manifest["family_similarity_hits"]
    assert "price_band_money_flow_confirmation" in manifest["family_similarity_hits"]
    assert "larry_connors_rsi2_mean_reversion" in manifest["family_similarity_hits"]
    assert "coppock_curve_monthly_equity_signal" in manifest["family_similarity_hits"]
    assert "cci_correction" in manifest["family_similarity_hits"]
    assert "macd_stochastic_double_cross" in manifest["family_similarity_hits"]
    assert consistency["consistency_passed"] is True


def test_no_source_selection_design_backtest_or_execution_paths() -> None:
    manifest = load_manifest()

    assert manifest["bounded_bt_design_created"] is False
    assert manifest["public_strategy_selected_by_codex"] is False
    assert manifest["public_source_scraped"] is False
    assert manifest["public_strategy_list_ingested"] is False
    assert manifest["public_strategy_implemented"] is False
    assert manifest["strategy_backtest_run"] is False
    assert manifest["strategy_discovery_run"] is False
    assert manifest["broad_research_batch_run"] is False
    assert manifest["new_packages_installed"] is False
    assert manifest["provider_download"] is False
    assert manifest["intraday_data_used"] is False
    assert manifest["leverage_short_options_futures_forex_margin_derivatives_crypto_used"] is False
    assert manifest["candidate_exhaustive_run"] is False
    assert manifest["promotion_candidates_created"] is False
    assert manifest["paper_forward_activation"] is False
    assert manifest["broker_api_called"] is False
    assert manifest["broker_orders_submitted"] is False
    assert manifest["broker_orders_cancelled"] is False
    assert manifest["broker_orders_reconciled"] is False
    assert manifest["live_orders"] is False
    assert manifest["real_money_recommendation"] is False
    assert manifest["current_backtester_replaced"] is False
    assert manifest["public_source_presence_is_profitability_proof"] is False
    assert manifest["outputs_diagnostic_only"] is True


def test_required_evidence_outputs_exist() -> None:
    required = [
        "candidate_file_inventory.csv",
        "source_summary.md",
        "required_field_validation_report.md",
        "constraint_filter_report.md",
        "family_similarity_do_not_retest_report.md",
        "local_cache_availability_report.csv",
        "local_cache_availability_report.md",
        "long_only_adaptation_caveat_report.md",
        "setup_definition_completeness_report.md",
        "directional_confirmation_completeness_report.md",
        "exit_rule_completeness_report.md",
        "indicator_defaults_completeness_report.md",
        "eligibility_decision.md",
        "guardrail_checklist.json",
        "public_source_intake_validation_next_action.md",
    ]
    for filename in required:
        assert (EVIDENCE / filename).exists(), filename


def test_future_clean_manual_intake_routes_to_bounded_design_only() -> None:
    constraint_filter = read_yaml(ROOT / CONSTRAINT_FILTER_PATH)
    family_map = read_yaml(ROOT / FAMILY_MAP_PATH)
    result = evaluate_candidate(
        ROOT,
        Path("synthetic_manual_public_source.yaml"),
        1,
        complete_synthetic_intake(),
        None,
        constraint_filter,
        family_map,
    )

    assert result["eligibility_decision"] == DECISION_ELIGIBLE
    assert next_action_for(result["eligibility_decision"], result["source_id"]).startswith(
        "design_public_source_synthetic_manual_public_source_bounded_bt_lane"
    )


def test_unclear_manual_rules_require_direction_owner_review() -> None:
    constraint_filter = read_yaml(ROOT / CONSTRAINT_FILTER_PATH)
    family_map = read_yaml(ROOT / FAMILY_MAP_PATH)
    result = evaluate_candidate(
        ROOT,
        Path("synthetic_unclear_source.yaml"),
        1,
        complete_synthetic_intake(rule_clarity="unclear"),
        None,
        constraint_filter,
        family_map,
    )

    assert result["eligibility_decision"] == DECISION_REVIEW
    assert next_action_for(result["eligibility_decision"], result["source_id"]) == (
        "direction_owner_review_required_for_public_source_intake"
    )


def test_fill_me_placeholders_are_missing_values() -> None:
    assert is_missing("FILL_ME") is True
    assert is_missing("FILL_ME_OR_NOT_APPLICABLE") is True
    assert is_missing(["FILL_ME"]) is True
