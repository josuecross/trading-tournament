from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "research_recovery" / "profit_research_queue_next_task_selection" / "latest"


def manifest() -> dict:
    return json.loads((EVIDENCE / "queue_next_task_selection_manifest.json").read_text(encoding="utf-8"))


def guardrails() -> dict:
    return json.loads((EVIDENCE / "queue_selection_guardrail_check.json").read_text(encoding="utf-8"))


def test_queue_selection_blocker_packet_guardrails() -> None:
    m = manifest()
    c = guardrails()

    assert m["queue_next_task_selection_only"] is True
    assert m["selection_from_existing_roadmap_registry_ledger_only"] is True
    assert m["completed_macro_gld_excluded"] is True
    assert m["completed_volatility_throttle_excluded"] is True
    assert m["selected_task"] == "none"
    assert m["eligible_executable_item_count"] == 0
    assert m["blocker_found"] is True
    assert m["new_strategy_discovery_run"] is False
    assert m["new_research_batch_run"] is False
    assert m["new_backtests_run"] is False
    assert m["new_performance_metrics_from_raw_data_computed"] is False
    assert m["new_families_created"] is False
    assert m["new_variants_created"] is False
    assert m["hidden_parameter_grid_created"] is False
    assert m["provider_download"] is False
    assert m["intraday_data_used"] is False
    assert m["broker_api_called"] is False
    assert m["broker_orders_submitted"] is False
    assert m["broker_orders_cancelled"] is False
    assert m["broker_orders_reconciled"] is False
    assert m["live_orders"] is False
    assert m["real_money_recommendation"] is False
    assert m["promotion_candidates_created"] is False
    assert m["candidate_exhaustive_run"] is False
    assert m["paper_forward_activation"] is False
    assert m["new_paper_forward_candidate_created"] is False
    assert m["active_vm_preserved"] is True
    assert m["active_dsr_preserved"] is True
    assert m["static_all_weather_benchmark_control_only"] is True
    assert m["exact_rejected_variants_reopened"] is False
    assert c["consistency_passed"] is True


def test_review_rows_capture_exclusions_and_blockers() -> None:
    rows = pd.read_csv(EVIDENCE / "eligible_item_review.csv")
    ids = set(rows["item_id"].astype(str))

    assert "macro_gld_duration_risk_off_confirmation_report" in ids
    assert "volatility_throttle_focused_research_lane_v1" in ids
    assert "recover_gld_macro_family_lineage" in ids
    assert "managed_futures_etf_wrapper" in ids
    assert "registry_research_sample_review_rows" in ids
    assert set(rows["selection_status"]).issuperset(
        {"excluded_by_instruction", "not_eligible", "blocked_not_executable_now", "ambiguous_not_selected"}
    )
    assert "executable_now" not in set(rows["selection_status"])


def test_required_files_and_next_action() -> None:
    m = manifest()
    expected = {
        "queue_next_task_selection_manifest.json",
        "queue_next_task_selection_summary.md",
        "source_state_review.md",
        "eligible_item_review.csv",
        "blocker_report.md",
        "queue_selection_guardrail_check.json",
        "queue_selection_next_action.md",
    }
    assert expected.issubset({path.name for path in EVIDENCE.iterdir() if path.is_file()})
    assert m["next_action"] in {
        "update_profit_oriented_research_queue_with_next_bounded_task",
        "run_selected_bounded_profit_research_task",
    }
