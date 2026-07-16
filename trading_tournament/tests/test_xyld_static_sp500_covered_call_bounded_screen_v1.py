from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest

from strategy_lab.research_os.research import xyld_static_sp500_covered_call_bounded_screen_v1 as screen


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "xyld_static_sp500_covered_call_bounded_screen_v1" / "latest"


@pytest.fixture(scope="module", autouse=True)
def generated_screen() -> dict[str, object]:
    return screen.run()


def read_json(name: str) -> dict[str, object]:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def read_csv(name: str) -> list[dict[str, str]]:
    with (EVIDENCE / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def test_required_artifacts_exist() -> None:
    required = {
        "source_and_preregistration.json",
        "candidate_fingerprint.json",
        "duplicate_review.csv",
        "fund_and_index_continuity.csv",
        "provider_acquisition_manifest.json",
        "cache_manifest.json",
        "frozen_evaluation_blocks.csv",
        "full_period_metrics.csv",
        "chronological_block_results.csv",
        "calendar_year_results.csv",
        "benchmark_relative_metrics.csv",
        "upside_downside_capture.csv",
        "accounting_data_and_exposure_invariants.csv",
        "screening_outcome.json",
        "exact_variant_research_memory.csv",
        "screen_summary.md",
        "consistency_check.json",
    }
    assert sorted(name for name in required if not (EVIDENCE / name).exists()) == []


def test_only_xyld_may_be_acquired_and_spy_bil_not_refreshed() -> None:
    provider = read_json("provider_acquisition_manifest.json")
    check = read_json("consistency_check.json")
    assert provider["authorized_download_symbols"] == ["XYLD"]
    assert set(provider["downloaded_symbols_this_run"]).issubset({"XYLD"})
    assert set(provider["downloaded_symbols_ever"]).issubset({"XYLD"})
    assert provider["alternative_covered_call_etf_downloaded"] is False
    assert provider["SPY_cache_refreshed"] is False
    assert provider["BIL_cache_refreshed"] is False
    assert check["SPY_cache_not_refreshed"] is True
    assert check["BIL_cache_not_refreshed"] is True


def test_preregistration_freezes_exact_static_wrapper_rules() -> None:
    prereg = read_json("source_and_preregistration.json")
    fingerprint = read_json("candidate_fingerprint.json")
    rules = prereg["frozen_candidate_rules"]
    assert prereg["candidate_id"] == screen.CANDIDATE_ID
    assert prereg["canonical_family"] == "option_premium_risk_premia"
    assert rules["candidate_asset"] == "XYLD"
    assert rules["uses_adjusted_total_return_prices"] is True
    assert rules["rebalance"] == "none after initial purchase"
    assert rules["BIL_switch"] is False
    assert rules["options_reconstruction_used"] is False
    assert rules["BXM_index_backfill_used"] is False
    assert fingerprint["rebalance_frequency"] == "none_after_initial_purchase"
    assert fingerprint["strategy_fingerprint"]


def test_adjusted_prices_are_validated_not_raw_distribution_excluding_close() -> None:
    cache = read_json("cache_manifest.json")
    rows = {row["symbol"]: row for row in cache["series"]}
    assert rows["XYLD"]["adjusted_price_validation_result"] == "pass"
    assert rows["XYLD"]["missing_adj_close_count"] == 0
    assert cache["adjusted_prices_required"] is True
    assert cache["raw_close_substitution_allowed"] is False
    invariants = read_csv("accounting_data_and_exposure_invariants.csv")[0]
    assert invariants["adjusted_prices_used"] == "true"
    assert invariants["raw_close_substitution_used"] == "false"
    assert invariants["distribution_yield_used_as_metric"] == "false"


def test_candidate_buys_xyld_once_without_bil_switch_or_timing_signal() -> None:
    invariants = read_csv("accounting_data_and_exposure_invariants.csv")[0]
    check = read_json("consistency_check.json")
    assert invariants["initial_turnover"] == "1"
    assert invariants["subsequent_turnover"] == "0"
    assert invariants["portfolio_trades"] == "1"
    assert invariants["no_rebalance_after_initial_purchase"] == "true"
    assert invariants["no_BIL_switch"] == "true"
    assert invariants["no_market_timing_signal"] == "true"
    assert check["candidate_buys_XYLD_once"] is True
    assert check["no_BIL_switch_or_timing_signal"] is True


def test_no_options_reconstruction_or_alternative_covered_call_etf() -> None:
    invariants = read_csv("accounting_data_and_exposure_invariants.csv")[0]
    provider = read_json("provider_acquisition_manifest.json")
    assert invariants["options_reconstruction_used"] == "false"
    assert invariants["alternative_covered_call_etf_used"] == "false"
    assert set(provider["forbidden_alternative_covered_call_etfs"]) == {"QYLD", "RYLD", "JEPI", "XYLG"}


def test_blocks_are_frozen_and_dates_match() -> None:
    blocks = read_csv("frozen_evaluation_blocks.csv")
    block_results = read_csv("chronological_block_results.csv")
    check = read_json("consistency_check.json")
    assert len(blocks) == 5
    assert len(block_results) == 5
    assert all(row["frozen_before_performance"] == "true" for row in blocks)
    assert all(row["performance_computed_at_definition_time"] == "false" for row in blocks)
    assert check["chronological_blocks_frozen_before_performance"] is True
    assert check["candidate_and_benchmark_dates_match"] is True


def test_initial_cost_equivalent_and_exposure_invariants() -> None:
    full = {row["symbol"]: row for row in read_csv("full_period_metrics.csv")}
    invariants = read_csv("accounting_data_and_exposure_invariants.csv")[0]
    assert float(full["XYLD"]["total_transaction_costs"]) == pytest.approx(float(full["SPY"]["total_transaction_costs"]))
    assert float(full["XYLD"]["total_transaction_costs"]) == pytest.approx(float(full["BIL"]["total_transaction_costs"]))
    assert float(invariants["max_daily_exposure"]) <= 1.000001
    assert float(invariants["max_daily_weight_sum"]) <= 1.000001
    assert invariants["zero_target_weights_not_stale_forward_filled"] == "true"
    assert invariants["invariants_passed"] == "true"


def test_duplicate_review_is_narrow_and_halloween_is_not_rerun() -> None:
    rows = {row["reviewed_id"]: row for row in read_csv("duplicate_review.csv")}
    check = read_json("consistency_check.json")
    assert rows["repository_prior_XYLD_mentions"]["decision"] == "no_prior_exact_XYLD_BXM_wrapper_screen_found"
    assert rows["spy_halloween_nov_apr_bil_v1"]["decision"] == "halloween_result_preserved_not_rerun"
    assert check["halloween_not_rerun"] is True


def test_registry_active_observations_and_external_source_pause_unchanged() -> None:
    invariants = read_csv("accounting_data_and_exposure_invariants.csv")[0]
    check = read_json("consistency_check.json")
    assert invariants["registry_byte_identical"] == "true"
    assert invariants["active_observations_unchanged"] == "true"
    assert invariants["vm_dsr_active_combo_unchanged"] == "true"
    assert invariants["automatic_external_source_selection_paused"] == "true"
    assert check["registry_byte_identical"] is True
    assert check["vm_dsr_active_combo_unchanged"] is True
    assert check["automatic_external_source_selection_paused"] is True


def test_outcome_is_pre_registered_and_non_promotional() -> None:
    outcome = read_json("screening_outcome.json")
    memory = read_csv("exact_variant_research_memory.csv")[0]
    assert outcome["outcome"] in screen.ALLOWED_OUTCOMES
    assert outcome["promotion_authorized"] is False
    assert outcome["paper_demo_authorized"] is False
    assert outcome["candidate_exhaustive_authorized"] is False
    assert outcome["real_money_recommendation"] is False
    assert memory["promotion_authorized"] == "false"
    assert memory["paper_demo_authorized"] == "false"
    assert memory["candidate_exhaustive_authorized"] == "false"


def test_generation_is_deterministic() -> None:
    outcome_hash = sha256(EVIDENCE / "screening_outcome.json")
    metrics_hash = sha256(EVIDENCE / "full_period_metrics.csv")
    blocks_hash = sha256(EVIDENCE / "frozen_evaluation_blocks.csv")
    result = screen.run()
    assert result["consistency_passed"] is True
    assert sha256(EVIDENCE / "screening_outcome.json") == outcome_hash
    assert sha256(EVIDENCE / "full_period_metrics.csv") == metrics_hash
    assert sha256(EVIDENCE / "frozen_evaluation_blocks.csv") == blocks_hash


def test_consistency_check_passes() -> None:
    assert read_json("consistency_check.json")["consistency_passed"] is True
