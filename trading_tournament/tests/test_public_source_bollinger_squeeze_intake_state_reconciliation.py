from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = (
    ROOT
    / "evidence"
    / "research_recovery"
    / "public_source_bollinger_squeeze_intake_state_reconciliation"
    / "latest"
)


def load_manifest() -> dict:
    return json.loads(
        (EVIDENCE / "bollinger_squeeze_intake_state_reconciliation_manifest.json").read_text(
            encoding="utf-8"
        )
    )


def load_consistency() -> dict:
    return json.loads(
        (EVIDENCE / "bollinger_squeeze_intake_state_reconciliation_consistency_check.json").read_text(
            encoding="utf-8"
        )
    )


def read_rows(filename: str) -> list[dict[str, str]]:
    with (EVIDENCE / filename).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_reconciliation_locks_bollinger_review_required_state() -> None:
    manifest = load_manifest()
    consistency = load_consistency()

    assert manifest["bollinger_squeeze_intake_state_reconciliation_only"] is True
    assert manifest["source_id"] == "bollinger_band_squeeze_breakout"
    assert manifest["family_id"] == "equity_index_volatility_contraction_breakout"
    assert manifest["final_status_locked"] is True
    assert manifest["final_bollinger_squeeze_status"] == "needs_direction_owner_review_no_design_authorized"
    assert manifest["single_source_intake_decision"] == "needs_direction_owner_review"
    assert manifest["batch_intake_decision"] == "needs_direction_owner_review"
    assert consistency["consistency_passed"] is True


def test_review_required_reasons_and_non_duplicate_cache_state_are_recorded() -> None:
    manifest = load_manifest()
    rows = read_rows("bollinger_squeeze_intake_status.csv")
    status_by_check = {row["check"]: row for row in rows}

    assert manifest["constraint_blocker_count"] == 0
    assert manifest["missing_required_field_count"] == 0
    assert manifest["spy_cache_ready"] is True
    assert manifest["bil_cache_ready"] is True
    assert manifest["duplicate_or_do_not_retest_blocker"] is False
    assert manifest["family_similarity_hit_count"] == 13
    assert manifest["long_only_adaptation_explicit"] is True
    assert manifest["setup_threshold_not_freezable"] is True
    assert manifest["directional_confirmation_not_source_backed_enough_to_freeze"] is True
    assert manifest["exit_rule_not_source_backed_enough_to_freeze"] is True
    assert manifest["rule_clarity_not_freezable"] is True
    assert status_by_check["setup_definition_completeness"]["passed"] == "True"
    assert status_by_check["directional_confirmation_completeness"]["passed"] == "True"
    assert status_by_check["exit_rule_completeness"]["passed"] == "True"


def test_design_backtest_tuning_confirmation_and_execution_are_not_authorized() -> None:
    manifest = load_manifest()

    expected_false = [
        "bounded_design_authorized",
        "strategy_implementation_authorized",
        "backtest_authorized",
        "parameter_tuning_authorized",
        "setup_threshold_invention_authorized",
        "directional_confirmation_invention_authorized",
        "exit_rule_invention_authorized",
        "extra_confirmation_indicator_authorized",
        "support_resistance_discretion_authorized",
        "stop_loss_authorized",
        "profit_target_authorized",
        "robustness_authorized",
        "candidate_exhaustive_authorized",
        "promotion_authorized",
        "paper_demo_activation_authorized",
        "broker_live_action_authorized",
    ]
    for key in expected_false:
        assert manifest[key] is False
    assert manifest["outputs_diagnostic_only"] is True
    assert manifest["outputs_non_promotable"] is True


def test_guardrails_prevent_forbidden_reconciliation_side_effects() -> None:
    manifest = load_manifest()
    guardrails = json.loads((EVIDENCE / "guardrail_checklist.json").read_text(encoding="utf-8"))

    expected_false = [
        "bounded_design_created",
        "strategy_implemented",
        "backtest_run",
        "setup_threshold_invented_or_frozen",
        "directional_confirmation_invented_or_frozen",
        "exit_rule_invented_or_frozen",
        "bollinger_period_tuned",
        "bollinger_standard_deviation_tuned",
        "bandwidth_threshold_tuned",
        "six_month_window_tuned",
        "confirmation_logic_tuned",
        "exit_rule_tuned",
        "rsi_confirmation_added",
        "macd_confirmation_added",
        "mfi_confirmation_added",
        "volume_filter_added",
        "obv_confirmation_added",
        "cmf_confirmation_added",
        "support_resistance_discretion_added",
        "stop_loss_added",
        "profit_target_added",
        "alternate_exits_added",
        "volatility_filter_added",
        "short_or_inverse_exposure_added",
        "leverage_options_futures_intraday_added",
        "robustness_run",
        "next_public_source_selected_by_codex",
        "public_source_scraped",
        "public_strategy_list_ingested",
        "macd_stochastic_continued",
        "cci_continued",
        "coppock_continued",
        "larry_connors_continued",
        "percent_b_continued",
        "turn_of_month_continued",
        "faber_taa_continued",
        "provider_download",
        "intraday_data_used",
        "new_packages_installed",
        "strategy_discovery_run",
        "candidate_exhaustive_run",
        "promotion_candidates_created",
        "paper_demo_observation_activated",
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


def test_queue_dirty_status_and_next_action_are_recorded_without_mutation() -> None:
    manifest = load_manifest()
    rows = read_rows("status_file_scan.csv")
    dirty_note = (EVIDENCE / "dirty_worktree_note.md").read_text(encoding="utf-8")

    assert manifest["queue_status_file_updated"] is False
    assert manifest["queue_status_update_reason"] == "no_safe_automatic_queue_status_update_convention_used"
    assert manifest["stale_design_pointer_count"] == len(rows)
    assert "unrelated dirty files were left untouched" in dirty_note
    assert (
        manifest["final_authorized_next_action"]
        == "direction_owner_select_next_public_source_candidate_or_supply_complete_bollinger_rules"
    )
    assert manifest["next_action"] == manifest["final_authorized_next_action"]


def test_required_reconciliation_files_exist() -> None:
    required = [
        "bollinger_squeeze_intake_state_reconciliation_manifest.json",
        "bollinger_squeeze_intake_state_reconciliation_summary.md",
        "evidence_paths_inspected.md",
        "bollinger_squeeze_intake_status.csv",
        "bollinger_squeeze_intake_status.md",
        "review_required_reasons.md",
        "queue_status_review.md",
        "dirty_worktree_note.md",
        "guardrail_checklist.json",
        "status_file_scan.csv",
        "bollinger_squeeze_intake_state_reconciliation_next_action.md",
        "bollinger_squeeze_intake_state_reconciliation_consistency_check.json",
    ]
    for filename in required:
        assert (EVIDENCE / filename).exists(), filename
