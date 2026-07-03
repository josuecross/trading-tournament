from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import yaml

from strategy_lab.research_os.research.profit_oriented_queue_resolution_after_high_return_robustness import (
    COMPLETED_EXCLUDED,
    NEXT_ACTION_DIRECTION_OWNER,
    OUTPUT_DIR,
    VALID_NEXT_ACTIONS,
)


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / OUTPUT_DIR


def load_manifest() -> dict:
    return json.loads((EVIDENCE / "queue_resolution_manifest.json").read_text(encoding="utf-8"))


def load_consistency() -> dict:
    return json.loads((EVIDENCE / "queue_resolution_consistency_check.json").read_text(encoding="utf-8"))


def test_queue_resolution_guardrails_and_exhaustion_state() -> None:
    manifest = load_manifest()
    consistency = load_consistency()

    assert manifest["queue_resolution_after_high_return_robustness_only"] is True
    assert manifest["source_of_truth_state_inspected_only"] is True
    assert manifest["selected_task"] == "none"
    assert manifest["selected_family_or_lane"] == "none"
    assert manifest["unique_executable_bounded_task_found"] is False
    assert manifest["executable_eligible_item_count"] == 0
    assert manifest["queue_exhaustion_found"] is True
    assert set(COMPLETED_EXCLUDED).issubset(set(manifest["completed_excluded_lanes"]))
    assert manifest["source_queue_status_file_updated"] is True
    assert manifest["new_strategy_discovery_run"] is False
    assert manifest["new_research_batch_run"] is False
    assert manifest["new_backtests_run"] is False
    assert manifest["new_performance_metrics_from_raw_data_computed"] is False
    assert manifest["new_families_created"] is False
    assert manifest["new_variants_created"] is False
    assert manifest["hidden_parameter_grid_created"] is False
    assert manifest["provider_download"] is False
    assert manifest["intraday_data_used"] is False
    assert manifest["leverage_used"] is False
    assert manifest["shorting_used"] is False
    assert manifest["options_used"] is False
    assert manifest["direct_futures_used"] is False
    assert manifest["broker_api_called"] is False
    assert manifest["broker_orders_submitted"] is False
    assert manifest["broker_orders_cancelled"] is False
    assert manifest["broker_orders_reconciled"] is False
    assert manifest["live_orders"] is False
    assert manifest["real_money_recommendation"] is False
    assert manifest["promotion_candidates_created"] is False
    assert manifest["candidate_exhaustive_run"] is False
    assert manifest["paper_forward_activation"] is False
    assert manifest["new_paper_forward_candidate_created"] is False
    assert manifest["best_single_variant_promoted"] is False
    assert manifest["active_vm_preserved"] is True
    assert manifest["active_dsr_preserved"] is True
    assert manifest["static_all_weather_benchmark_control_only"] is True
    assert manifest["exact_rejected_variants_reopened"] is False
    assert manifest["diagnostic_evidence_treated_as_deployment_approval"] is False
    assert manifest["next_action"] in VALID_NEXT_ACTIONS
    assert manifest["next_action"] == NEXT_ACTION_DIRECTION_OWNER
    assert consistency["consistency_passed"] is True


def test_candidate_table_records_exclusions_and_ambiguity() -> None:
    manifest = load_manifest()
    rows = pd.read_csv(EVIDENCE / "candidate_queue_table.csv")

    assert len(rows) >= len(COMPLETED_EXCLUDED)
    assert set(COMPLETED_EXCLUDED).issubset(set(rows["item_id"]))
    assert "ambiguous_not_selected" in set(rows["selection_status"])
    assert "executable_now" not in set(rows["selection_status"])
    assert manifest["registry_research_sample_review_row_count"] >= 1
    assert manifest["ambiguous_item_group_count"] >= 1

    high_return = rows[rows["item_id"] == "high_return_tactical_etf_equity_index_bounded_lane_v1"].iloc[0]
    commodity = rows[rows["item_id"] == "commodity_basket_etf_momentum_bounded_lane_v1"].iloc[0]
    managed = rows[rows["item_id"] == "managed_futures_etf_wrapper"].iloc[0]

    assert high_return["selection_status"] == "excluded_completed_for_now"
    assert commodity["selection_status"] == "excluded_completed_for_now"
    assert managed["selection_status"] == "not_eligible"


def test_source_queue_no_longer_marks_commodity_run_ready() -> None:
    queue = yaml.safe_load((ROOT / "strategy_lab" / "research_os" / "research" / "research_queue.yaml").read_text())
    active = queue["active_bounded_research_task"]

    assert active["id"] == "commodity_basket_etf_momentum_bounded_lane_v1"
    assert active["status"] == "completed_for_now"
    assert active["next_action"] == NEXT_ACTION_DIRECTION_OWNER
    assert active["authorizes_backtests"] is False
    assert active["authorizes_discovery"] is False
    assert active["authorizes_provider_download"] is False
    assert active["authorizes_candidate_exhaustive"] is False
    assert active["authorizes_paper_forward"] is False


def test_queue_resolution_required_artifacts_exist() -> None:
    for filename in [
        "queue_resolution_manifest.json",
        "queue_resolution_summary.md",
        "sources_inspected.md",
        "completed_excluded_lanes.md",
        "candidate_queue_table.csv",
        "queue_exhaustion_report.md",
        "queue_status_update.md",
        "guardrail_checklist.json",
        "queue_resolution_next_action.md",
        "queue_resolution_consistency_check.json",
    ]:
        assert (EVIDENCE / filename).exists(), filename
