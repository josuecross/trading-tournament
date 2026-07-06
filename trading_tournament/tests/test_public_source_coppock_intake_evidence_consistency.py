from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = (
    ROOT
    / "evidence"
    / "research_recovery"
    / "public_source_coppock_intake_evidence_consistency"
    / "latest"
)


def load_manifest() -> dict:
    return json.loads((EVIDENCE / "coppock_intake_evidence_consistency_manifest.json").read_text(encoding="utf-8"))


def load_consistency() -> dict:
    return json.loads(
        (EVIDENCE / "coppock_intake_evidence_consistency_consistency_check.json").read_text(encoding="utf-8")
    )


def test_coppock_candidate_specific_evidence_is_consistent() -> None:
    manifest = load_manifest()
    consistency = load_consistency()

    assert manifest["coppock_intake_evidence_consistency_verification_only"] is True
    assert manifest["source_id"] == "coppock_curve_monthly_equity_signal"
    assert manifest["coppock_yaml_valid"] is True
    assert manifest["candidate_specific_evidence_valid"] is True
    assert manifest["source_fields_complete"] is True
    assert manifest["constraint_blockers"] == []
    assert manifest["spy_cache_ready"] is True
    assert manifest["bil_cache_ready"] is True
    assert manifest["eligibility_decision"] == "eligible_for_bounded_bt_design"
    assert manifest["batch_eligibility_decision"] == "eligible_for_bounded_bt_design"
    assert manifest["verification_decision"] == "coppock_intake_evidence_consistent_ready_for_design"
    assert consistency["consistency_passed"] is True


def test_larry_change_was_reverted_and_bridge_is_generic() -> None:
    manifest = load_manifest()
    bridge = (EVIDENCE / "generic_bridge_evidence_explanation.md").read_text(encoding="utf-8")
    larry = (EVIDENCE / "larry_connors_yaml_change_report.md").read_text(encoding="utf-8")

    assert manifest["larry_connors_yaml_change_report"] == "unrelated_reverted"
    assert manifest["larry_connors_yaml_current_diff_present"] is False
    assert "Current Larry diff:" in larry
    assert "none" in larry
    assert manifest["generic_bridge_blank_intake_expected"] is True
    assert "infrastructure/blank-template bridge check" in bridge
    assert "should not be used as the Coppock eligibility decision" in bridge


def test_similarity_and_do_not_retest_status_are_explicit() -> None:
    manifest = load_manifest()

    expected = {
        "spy200d_trend_control",
        "global_multi_asset",
        "macro_gld_duration_risk_off",
        "high_return_tactical_equity",
        "volatility_throttle_volatility_managed_equity",
        "turn_of_month_calendar_effect",
        "mean_reversion_rejected_or_existing_candidate",
        "price_band_money_flow_confirmation",
    }
    assert expected.issubset(set(manifest["similarity_hits"]))
    assert manifest["similarity_hits_expected"] is True
    assert manifest["duplicate_do_not_retest_decision"] is False


def test_no_design_backtest_or_execution_paths() -> None:
    manifest = load_manifest()
    guardrails = json.loads((EVIDENCE / "guardrail_checklist.json").read_text(encoding="utf-8"))

    expected_false = [
        "coppock_bounded_design_created",
        "coppock_implemented",
        "coppock_backtest_run",
        "different_public_source_selected",
        "public_source_scraped",
        "public_strategy_list_ingested",
        "coppock_parameters_tuned",
        "daily_or_weekly_variants_added",
        "filters_stops_signal_lines_divergence_or_alternate_exits_added",
        "larry_connors_continued",
        "percent_b_continued",
        "turn_of_month_continued",
        "faber_taa_retested",
        "provider_download",
        "intraday_data_used",
        "new_packages_installed",
        "candidate_exhaustive_run",
        "promotion_candidates_created",
        "paper_demo_activation",
        "broker_api_called",
        "broker_orders_submitted",
        "broker_orders_cancelled",
        "broker_orders_reconciled",
        "live_orders",
        "real_money_recommendation",
    ]
    for key in expected_false:
        assert manifest[key] is False
        assert guardrails[key] is False


def test_required_consistency_files_exist() -> None:
    required = [
        "coppock_intake_evidence_consistency_manifest.json",
        "git_diff_summary.md",
        "coppock_yaml_validation_report.md",
        "larry_connors_yaml_change_report.md",
        "candidate_specific_evidence_location_report.md",
        "generic_bridge_evidence_explanation.md",
        "similarity_do_not_retest_confirmation.md",
        "guardrail_checklist.json",
        "coppock_intake_evidence_consistency_next_action.md",
        "coppock_intake_evidence_consistency_consistency_check.json",
    ]
    for filename in required:
        assert (EVIDENCE / filename).exists(), filename
