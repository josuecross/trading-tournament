from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "research_recovery" / "commodity_basket_provider_refresh" / "latest"
MANIFEST = EVIDENCE / "provider_refresh_manifest.json"
CONSISTENCY = EVIDENCE / "provider_refresh_consistency_check.json"

AUTHORIZED = {"DBC", "PDBC", "COMT", "GSG", "USCI"}
REQUIRED = AUTHORIZED | {"BIL", "SPY", "GLD"}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_provider_refresh_manifest_guardrails() -> None:
    manifest = load_json(MANIFEST)

    assert manifest["commodity_provider_refresh_only"] is True
    assert manifest["family_id"] == "commodity_basket_etf_momentum_v1"
    assert manifest["lane_id"] == "commodity_basket_etf_momentum_bounded_lane_v1"
    assert set(manifest["authorized_refresh_symbols"]) == AUTHORIZED
    assert set(manifest["required_symbols"]) == REQUIRED
    assert set(manifest["downloaded_symbols"]).issubset(AUTHORIZED)
    assert manifest["unrelated_symbols_refreshed"] == []

    assert manifest["provider_download"] is True
    assert manifest["provider_api_called"] is True
    assert manifest["keyed_provider_used"] is False
    assert manifest["api_key_or_secret_written"] is False
    assert manifest["raw_ohlcv_in_evidence"] is False
    assert manifest["summary_metrics_converted_to_price_history"] is False
    assert manifest["intraday_data_used"] is False
    assert manifest["commodity_lane_run"] is False
    assert manifest["new_backtests_run"] is False
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


def test_refreshed_symbols_and_cache_quality() -> None:
    manifest = load_json(MANIFEST)
    refresh_rows = load_csv(EVIDENCE / "symbol_refresh_table.csv")
    quality_rows = load_csv(EVIDENCE / "data_quality_summary.csv")
    availability = load_csv(EVIDENCE / "required_symbol_availability.csv")
    hash_rows = load_csv(EVIDENCE / "hash_report.csv")

    assert {row["symbol"] for row in refresh_rows} == AUTHORIZED
    assert {row["symbol"] for row in quality_rows} == AUTHORIZED
    assert {row["symbol"] for row in availability} == REQUIRED
    assert {row["symbol"] for row in hash_rows} == AUTHORIZED

    if manifest["run_readiness_decision"] == "commodity_basket_cache_ready_for_bounded_run":
        assert set(manifest["downloaded_symbols"]) == AUTHORIZED
        assert manifest["failed_symbols"] == []
        assert manifest["all_required_symbols_available"] is True
        assert all(row["download_status"] == "downloaded_pass" for row in refresh_rows)
        assert all(row["quality_status"] in {"pass", "warning"} for row in quality_rows)
        assert all(int(row["row_count"]) >= 380 for row in quality_rows)
        assert all(row["status"] == "available_raw_price_history" for row in availability)
        assert all(row["sha256"] for row in hash_rows)
    else:
        assert manifest["run_readiness_decision"] == "commodity_basket_cache_still_blocked"
        assert manifest["blocked_symbols"]
        assert any(row["quality_status"] == "fail" for row in quality_rows) or any(
            row["status"] != "available_raw_price_history" for row in availability
        )


def test_required_files_and_consistency() -> None:
    consistency = load_json(CONSISTENCY)
    required = [
        "provider_refresh_manifest.json",
        "provider_source.md",
        "symbol_refresh_table.csv",
        "cache_write_manifest.csv",
        "required_symbol_availability.csv",
        "data_quality_summary.csv",
        "hash_report.csv",
        "missing_invalid_data_report.md",
        "guardrail_checklist.md",
        "provider_refresh_summary.md",
        "provider_refresh_next_action.md",
        "provider_refresh_consistency_check.json",
    ]
    for filename in required:
        assert (EVIDENCE / filename).exists(), filename
    assert consistency["consistency_passed"] is True
