from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "research_recovery" / "public_source_phase_checkpoint" / "latest"


def load_manifest() -> dict:
    return json.loads((EVIDENCE / "public_source_phase_checkpoint_manifest.json").read_text(encoding="utf-8"))


def load_consistency() -> dict:
    return json.loads(
        (EVIDENCE / "public_source_phase_checkpoint_consistency_check.json").read_text(encoding="utf-8")
    )


def read_rows(filename: str) -> list[dict[str, str]]:
    with (EVIDENCE / filename).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_checkpoint_manifest_records_public_source_phase_only() -> None:
    manifest = load_manifest()
    consistency = load_consistency()

    assert manifest["public_source_phase_checkpoint_only"] is True
    assert manifest["checkpoint_status"] == "public_source_review_batch_exhausted_checkpoint_created"
    assert manifest["candidate_count"] == 8
    assert manifest["new_public_source_selected_by_codex"] is False
    assert manifest["next_action"] == "direction_owner_select_new_public_source_candidate"
    assert consistency["consistency_passed"] is True


def test_candidate_ledger_locks_expected_recent_public_source_statuses() -> None:
    rows = {row["source_id"]: row for row in read_rows("candidate_status_ledger.csv")}

    assert set(rows) == {
        "faber_taa",
        "turn_of_month_equity_indexes",
        "percent_b_money_flow",
        "larry_connors_rsi2_mean_reversion",
        "coppock_curve_monthly_equity_signal",
        "cci_correction",
        "macd_stochastic_double_cross",
        "bollinger_band_squeeze_breakout",
    }
    assert rows["faber_taa"]["final_decision"] == "duplicate_or_do_not_retest"
    assert rows["turn_of_month_equity_indexes"]["latest_known_state"] == (
        "completed_diagnostic_cost_sensitive_rolling_weak_no_continuation"
    )
    assert rows["percent_b_money_flow"]["latest_known_state"] == (
        "completed_diagnostic_failed_pre_registered_exposure_criterion_no_rerun"
    )
    assert rows["larry_connors_rsi2_mean_reversion"]["latest_known_state"] == (
        "completed_diagnostic_context_only_cost_sensitive_rolling_weak_no_continuation"
    )
    assert rows["coppock_curve_monthly_equity_signal"]["latest_known_state"] == (
        "completed_diagnostic_sparse_context_only_failed_criteria_no_continuation"
    )
    assert rows["cci_correction"]["latest_known_state"] == (
        "completed_diagnostic_control_weak_context_only_no_continuation"
    )
    assert rows["macd_stochastic_double_cross"]["latest_known_state"] == (
        "needs_direction_owner_review_exit_rule_incomplete_no_design_authorized"
    )
    assert rows["bollinger_band_squeeze_breakout"]["latest_known_state"] == (
        "needs_direction_owner_review_no_design_authorized"
    )


def test_candidate_ledger_blocks_design_execution_promotion_and_live_paths() -> None:
    rows = read_rows("candidate_status_ledger.csv")

    for row in rows:
        assert row["design_authorized"] == "False"
        assert row["backtest_authorized"] == "False"
        assert row["candidate_exhaustive_authorized"] == "False"
        assert row["promotion_authorized"] == "False"
        assert row["paper_demo_authorized"] == "False"
        assert row["live_authorized"] == "False"
        assert "candidate_exhaustive" in row["forbidden_next_actions"]
        assert "broker_live_action" in row["forbidden_next_actions"]


def test_dirty_worktree_hygiene_and_stale_scan_are_recorded() -> None:
    manifest = load_manifest()
    dirty_rows = read_rows("dirty_worktree_hygiene.csv")
    stale_rows = read_rows("stale_next_action_scan.csv")

    assert manifest["dirty_worktree_item_count"] == len(dirty_rows)
    assert manifest["stale_next_action_pointer_count"] == len(stale_rows)
    assert manifest["state_files_updated"] is False
    assert manifest["state_update_reason"] == "no_safe_automatic_queue_status_update_convention_used"
    assert any(row["likely_owner_or_candidate"] == "public_source_phase_checkpoint" for row in dirty_rows)


def test_guardrails_prevent_research_or_new_source_side_effects() -> None:
    manifest = load_manifest()
    guardrails = json.loads((EVIDENCE / "guardrail_checklist.json").read_text(encoding="utf-8"))

    expected_false = [
        "new_public_source_selected_by_codex",
        "public_source_scraped",
        "public_strategy_list_ingested",
        "new_strategy_design_created",
        "strategy_implemented",
        "backtest_run",
        "robustness_run",
        "results_audit_run",
        "prior_candidate_rerun",
        "parameters_tuned",
        "missing_rules_invented",
        "bollinger_continued",
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


def test_required_checkpoint_files_exist() -> None:
    required = [
        "public_source_phase_checkpoint_manifest.json",
        "public_source_phase_checkpoint_summary.md",
        "evidence_paths_inspected.md",
        "candidate_status_ledger.csv",
        "candidate_status_ledger.md",
        "dirty_worktree_hygiene.csv",
        "dirty_worktree_hygiene.md",
        "stale_next_action_scan.csv",
        "stale_next_action_scan.md",
        "state_update_report.md",
        "guardrail_checklist.json",
        "public_source_phase_checkpoint_next_action.md",
        "public_source_phase_checkpoint_consistency_check.json",
    ]
    for filename in required:
        assert (EVIDENCE / filename).exists(), filename
