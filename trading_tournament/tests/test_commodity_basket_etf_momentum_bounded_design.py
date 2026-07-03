from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "research_recovery" / "commodity_basket_etf_momentum_bounded_design" / "latest"
MANIFEST = EVIDENCE / "commodity_basket_bounded_design_manifest.json"
CONSISTENCY = EVIDENCE / "commodity_basket_bounded_design_consistency_check.json"
QUEUE = ROOT / "strategy_lab" / "research_os" / "research" / "research_queue.yaml"


VALID_NEXT_ACTIONS = {
    "run_commodity_basket_etf_momentum_bounded_lane",
    "restore_or_revalidate_local_commodity_cache_before_bounded_run",
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_manifest_guardrails_and_selected_task() -> None:
    manifest = load_json(MANIFEST)

    assert manifest["commodity_basket_bounded_design_only"] is True
    assert manifest["lane_id"] == "commodity_basket_etf_momentum_bounded_lane_v1"
    assert manifest["family_id"] == "commodity_basket_etf_momentum_v1"
    assert manifest["selected_task"] == "design_commodity_basket_etf_momentum_bounded_lane"
    assert manifest["selected_from_existing_source_of_truth"] is True
    assert manifest["queue_source_of_truth_entry_updated"] is True

    assert manifest["new_research_batch_run"] is False
    assert manifest["new_strategy_discovery_run"] is False
    assert manifest["new_backtests_run"] is False
    assert manifest["new_performance_metrics_from_raw_data_computed"] is False
    assert manifest["new_family_created"] is False
    assert manifest["new_variants_created"] is False
    assert manifest["hidden_parameter_grid_created"] is False
    assert manifest["commodity_lane_run"] is False
    assert manifest["provider_download"] is False
    assert manifest["intraday_data_used"] is False
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
    assert manifest["research_outputs_remain_non_promotable"] is True

    assert manifest["active_vm_preserved"] is True
    assert manifest["active_dsr_preserved"] is True
    assert manifest["static_all_weather_benchmark_control_only"] is True
    assert manifest["managed_futures_reopened"] is False
    assert manifest["macro_gld_continued"] is False
    assert manifest["volatility_throttle_continued"] is False


def test_queue_source_of_truth_has_exact_commodity_task() -> None:
    queue_text = QUEUE.read_text(encoding="utf-8")

    assert "active_bounded_research_task:" in queue_text
    assert "id: commodity_basket_etf_momentum_bounded_lane_v1" in queue_text
    assert "family_id: commodity_basket_etf_momentum_v1" in queue_text
    assert "selected_step: design_commodity_basket_etf_momentum_bounded_lane" in queue_text
    assert "run_readiness_decision: commodity_basket_bounded_design_run_ready" in queue_text
    assert "cache_revalidation_status: completed_raw_price_history_ready" in queue_text
    assert "next_action: run_commodity_basket_etf_momentum_bounded_lane" in queue_text
    assert "authorizes_provider_download: false" in queue_text
    assert "authorizes_candidate_exhaustive: false" in queue_text


def test_design_rows_are_bounded_and_non_promotable() -> None:
    manifest = load_json(MANIFEST)
    rows = load_csv(EVIDENCE / "commodity_basket_bounded_variant_design_table.csv")

    assert manifest["planned_row_count"] == 6
    assert manifest["planned_row_count_between_6_and_12"] is True
    assert 6 <= len(rows) <= 12
    assert len({row["variant_id"] for row in rows}) == len(rows)
    assert {row["family_id"] for row in rows} == {"commodity_basket_etf_momentum_v1"}
    assert all(row["promotion_eligibility"] == "False" for row in rows)
    assert all(row["paper_forward_eligibility"] == "False" for row in rows)
    assert all(row["candidate_exhaustive_eligibility"] == "False" for row in rows)
    assert all(float(row["max_daily_exposure"]) <= 1.0 for row in rows)
    assert all(float(row["max_daily_weight_sum"]) <= 1.0 for row in rows)
    assert any(row["variant_role"] == "portfolio_contribution_context" for row in rows)
    assert any(row["variant_role"] == "comparator_control" for row in rows)
    assert any(row["variant_role"] == "cash_control" for row in rows)


def test_cache_blocker_and_required_design_artifacts() -> None:
    manifest = load_json(MANIFEST)
    consistency = load_json(CONSISTENCY)

    required = [
        "commodity_basket_bounded_design_manifest.json",
        "commodity_basket_bounded_design_summary.md",
        "source_commodity_evidence_review.md",
        "commodity_basket_bounded_variant_design_table.csv",
        "commodity_basket_bounded_variant_design_table.md",
        "baseline_comparator_policy.md",
        "numeric_success_failure_criteria.md",
        "exposure_invariant_policy.md",
        "guardrail_checklist.md",
        "local_cache_preflight.md",
        "queue_source_of_truth_update.md",
        "do_not_promote_from_commodity_basket_design.md",
        "commodity_basket_bounded_design_next_action.md",
        "commodity_basket_bounded_design_consistency_check.json",
    ]
    for filename in required:
        assert (EVIDENCE / filename).exists(), filename

    criteria = (EVIDENCE / "numeric_success_failure_criteria.md").read_text(encoding="utf-8")
    invariants = (EVIDENCE / "exposure_invariant_policy.md").read_text(encoding="utf-8")

    assert "Worst 180-day drawdown `>= -600.0000`" in criteria
    assert "Correlation to active combo or SPY_200d reference `< 0.9000`" in criteria
    assert "Max daily exposure must be `<= 1.0`" in invariants
    assert "stale-forward-fill" in invariants

    assert manifest["run_readiness_decision"] == "commodity_basket_bounded_design_run_ready"
    assert manifest["run_readiness_blocker"] == "none"
    assert manifest["local_cache_missing_commodity_wrapper_symbols"] == []
    assert set(manifest["local_cache_available_symbols"]) >= {"DBC", "PDBC", "COMT", "GSG", "USCI", "BIL", "SPY", "GLD"}
    assert manifest["next_action"] in VALID_NEXT_ACTIONS
    assert manifest["next_action"] == "run_commodity_basket_etf_momentum_bounded_lane"
    assert consistency["consistency_passed"] is True
