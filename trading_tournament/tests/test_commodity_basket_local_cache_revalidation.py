from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "research_recovery" / "commodity_basket_local_cache_revalidation" / "latest"
MANIFEST = EVIDENCE / "cache_revalidation_manifest.json"
CONSISTENCY = EVIDENCE / "cache_revalidation_consistency_check.json"
QUEUE = ROOT / "strategy_lab" / "research_os" / "research" / "research_queue.yaml"


COMMODITY_WRAPPERS = {"DBC", "PDBC", "COMT", "GSG", "USCI"}
VALID_NEXT_ACTIONS = {
    "run_commodity_basket_etf_momentum_bounded_lane",
    "provide_existing_raw_commodity_cache_files_or_authorize_provider_refresh",
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_cache_revalidation_manifest_guardrails() -> None:
    manifest = load_json(MANIFEST)

    assert manifest["commodity_cache_revalidation_only"] is True
    assert manifest["family_id"] == "commodity_basket_etf_momentum_v1"
    assert manifest["lane_id"] == "commodity_basket_etf_momentum_bounded_lane_v1"
    assert manifest["step_id"] == "restore_or_revalidate_local_commodity_cache_before_bounded_run"

    assert manifest["summary_metrics_converted_to_price_history"] is False
    assert manifest["provider_download"] is False
    assert manifest["internet_used"] is False
    assert manifest["intraday_data_used"] is False
    assert manifest["new_backtests_run"] is False
    assert manifest["commodity_lane_run"] is False
    assert manifest["new_strategy_discovery_run"] is False
    assert manifest["new_research_batch_run"] is False
    assert manifest["new_family_created"] is False
    assert manifest["new_variants_created"] is False
    assert manifest["six_row_design_changed"] is False
    assert manifest["candidate_exhaustive_run"] is False
    assert manifest["promotion_candidates_created"] is False
    assert manifest["paper_forward_activation"] is False
    assert manifest["new_paper_forward_candidate_created"] is False
    assert manifest["broker_api_called"] is False
    assert manifest["broker_orders_submitted"] is False
    assert manifest["broker_orders_cancelled"] is False
    assert manifest["broker_orders_reconciled"] is False
    assert manifest["live_orders"] is False
    assert manifest["real_money_recommendation"] is False
    assert manifest["macro_gld_continued"] is False
    assert manifest["volatility_throttle_continued"] is False
    assert manifest["managed_futures_reopened"] is False
    assert manifest["active_vm_preserved"] is True
    assert manifest["active_dsr_preserved"] is True
    assert manifest["static_all_weather_benchmark_control_only"] is True


def test_required_symbols_are_proven_and_cache_is_ready() -> None:
    manifest = load_json(MANIFEST)
    rows = load_csv(EVIDENCE / "required_symbol_availability.csv")
    by_symbol = {row["symbol"]: row for row in rows}

    assert set(manifest["required_symbols"]) == COMMODITY_WRAPPERS | {"BIL", "SPY", "GLD"}
    assert manifest["missing_symbols"] == []
    assert set(manifest["restored_symbols"]) == set()
    assert set(manifest["reindexed_symbols"]) == set()
    assert manifest["raw_price_history_found_for_all_required_symbols"] is True
    assert manifest["run_readiness_decision"] == "commodity_basket_cache_ready_for_bounded_run"
    assert manifest["next_action"] == "run_commodity_basket_etf_momentum_bounded_lane"
    assert manifest["next_action"] in VALID_NEXT_ACTIONS

    for symbol in COMMODITY_WRAPPERS:
        assert by_symbol[symbol]["current_cache_exists"] == "True"
        assert by_symbol[symbol]["current_cache_is_raw_price_history"] == "True"
        assert by_symbol[symbol]["safe_to_restore_from_existing_artifact"] == "False"
        assert by_symbol[symbol]["status"] == "available_raw_price_history"
        assert int(by_symbol[symbol]["row_count"]) >= 380

    for symbol in {"BIL", "SPY", "GLD"}:
        assert by_symbol[symbol]["current_cache_exists"] == "True"
        assert by_symbol[symbol]["current_cache_is_raw_price_history"] == "True"
        assert by_symbol[symbol]["status"] == "available_raw_price_history"


def test_summary_artifacts_are_not_treated_as_raw_price_history() -> None:
    manifest = load_json(MANIFEST)
    locations = load_csv(EVIDENCE / "restored_reindexed_symbols.csv")
    raw_vs_summary = (EVIDENCE / "raw_price_history_vs_summary_evidence.md").read_text(encoding="utf-8")

    assert manifest["summary_only_locations_count"] >= 1
    assert manifest["raw_price_locations_with_commodity_wrappers_count"] == 1
    assert manifest["git_tracked_raw_commodity_files_found"] == []
    assert manifest["git_history_raw_commodity_files_found"] == []
    assert all(row["status"] == "not_restored_no_existing_raw_price_artifact" for row in locations)
    assert "cannot be used to restore OHLCV rows without fabricating data" in raw_vs_summary


def test_required_files_queue_and_consistency() -> None:
    consistency = load_json(CONSISTENCY)
    queue_text = QUEUE.read_text(encoding="utf-8")

    required = [
        "cache_revalidation_manifest.json",
        "required_symbol_availability.csv",
        "required_symbol_availability.md",
        "current_cache_locations_inspected.md",
        "historical_cache_evidence_locations_inspected.md",
        "restored_reindexed_symbols.csv",
        "restored_reindexed_symbols.md",
        "missing_symbols.md",
        "raw_price_history_vs_summary_evidence.md",
        "guardrail_checklist.md",
        "commodity_cache_revalidation_summary.md",
        "commodity_cache_revalidation_next_action.md",
        "cache_revalidation_consistency_check.json",
    ]
    for filename in required:
        assert (EVIDENCE / filename).exists(), filename

    assert "cache_revalidation_status: completed_raw_price_history_ready" in queue_text
    assert "next_action: run_commodity_basket_etf_momentum_bounded_lane" in queue_text
    assert consistency["consistency_passed"] is True
