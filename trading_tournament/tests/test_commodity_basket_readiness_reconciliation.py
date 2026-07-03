from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "research_recovery" / "commodity_basket_readiness_reconciliation" / "latest"
MANIFEST = EVIDENCE / "readiness_reconciliation_manifest.json"
CONSISTENCY = EVIDENCE / "readiness_reconciliation_consistency_check.json"

REQUIRED = {"DBC", "PDBC", "COMT", "GSG", "USCI", "BIL", "SPY", "GLD"}
REFRESHED = {"DBC", "PDBC", "COMT", "GSG", "USCI"}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_readiness_reconciliation_manifest_ready_and_guardrailed() -> None:
    manifest = load_json(MANIFEST)

    assert manifest["commodity_readiness_reconciliation_only"] is True
    assert manifest["family_id"] == "commodity_basket_etf_momentum_v1"
    assert manifest["lane_id"] == "commodity_basket_etf_momentum_bounded_lane_v1"
    assert manifest["uploaded_review_package_stale_or_incomplete"] is True
    assert manifest["all_required_symbols_available"] is True
    assert manifest["provider_refreshed_symbols_passed"] is True
    assert manifest["cache_revalidation_decision"] == "commodity_basket_cache_ready_for_bounded_run"
    assert manifest["bounded_design_run_readiness_decision"] == "commodity_basket_bounded_design_run_ready"
    assert manifest["queue_next_action"] == "run_commodity_basket_etf_momentum_bounded_lane"
    assert manifest["contradictions_found_count"] == 0
    assert manifest["final_decision"] == "commodity_basket_ready_to_run_verified"
    assert manifest["next_action"] == "run_commodity_basket_etf_momentum_bounded_lane"

    assert manifest["commodity_lane_run"] is False
    assert manifest["new_backtests_run"] is False
    assert manifest["new_strategy_discovery_run"] is False
    assert manifest["new_research_batch_run"] is False
    assert manifest["provider_download_this_step"] is False
    assert manifest["intraday_data_used"] is False
    assert manifest["new_family_created"] is False
    assert manifest["new_variants_created"] is False
    assert manifest["six_row_design_changed"] is False
    assert manifest["candidate_exhaustive_run"] is False
    assert manifest["promotion_candidates_created"] is False
    assert manifest["paper_forward_activation"] is False
    assert manifest["broker_api_called"] is False
    assert manifest["live_orders"] is False
    assert manifest["real_money_recommendation"] is False


def test_reconciliation_tables_show_current_ready_state() -> None:
    availability = load_csv(EVIDENCE / "current_required_symbol_availability.csv")
    provider = load_csv(EVIDENCE / "provider_refresh_summary.csv")

    assert {row["symbol"] for row in availability} == REQUIRED
    assert all(row["status"] == "available_raw_price_history" for row in availability)
    assert all(row["cache_exists"] == "True" for row in availability)
    assert all(row["is_raw_price_history"] == "True" for row in availability)
    assert all(int(row["row_count"]) >= 380 for row in availability)

    assert {row["symbol"] for row in provider} == REFRESHED
    assert all(row["download_status"] == "downloaded_pass" for row in provider)
    assert all(row["quality_status"] in {"pass", "warning"} for row in provider)
    assert all(row["sha256"] for row in provider)


def test_reconciliation_files_and_consistency() -> None:
    consistency = load_json(CONSISTENCY)
    required_files = [
        "readiness_reconciliation_manifest.json",
        "readiness_reconciliation_summary.md",
        "evidence_folder_status.csv",
        "evidence_folder_status.md",
        "current_required_symbol_availability.csv",
        "current_required_symbol_availability.md",
        "provider_refresh_summary.csv",
        "provider_refresh_summary.md",
        "cache_revalidation_decision.md",
        "bounded_design_readiness_decision.md",
        "queue_source_of_truth.md",
        "contradiction_review.md",
        "guardrail_checklist.md",
        "readiness_reconciliation_next_action.md",
        "readiness_reconciliation_consistency_check.json",
    ]
    for filename in required_files:
        assert (EVIDENCE / filename).exists(), filename
    assert consistency["consistency_passed"] is True
