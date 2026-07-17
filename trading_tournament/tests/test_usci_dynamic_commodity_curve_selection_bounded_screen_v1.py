from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest

from strategy_lab.research_os.research import usci_dynamic_commodity_curve_selection_bounded_screen_v1 as screen


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "usci_dynamic_commodity_curve_selection_bounded_screen_v1" / "latest"


@pytest.fixture(scope="module", autouse=True)
def generated_screen() -> dict[str, object]:
    assert (EVIDENCE / "screening_outcome.json").exists(), "prior USCI bounded screen evidence must already exist"
    return read_json("screening_outcome.json")


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
        "frozen_methodology_regimes.csv",
        "full_period_metrics.csv",
        "chronological_block_results.csv",
        "methodology_regime_results.csv",
        "calendar_year_results.csv",
        "benchmark_relative_metrics.csv",
        "correlation_and_capture_diagnostics.csv",
        "accounting_data_and_exposure_invariants.csv",
        "screening_outcome.json",
        "exact_variant_research_memory.csv",
        "screen_summary.md",
        "consistency_check.json",
    }
    assert sorted(name for name in required if not (EVIDENCE / name).exists()) == []


def test_only_usci_and_dbc_may_be_acquired_and_valid_caches_not_refreshed() -> None:
    provider = read_json("provider_acquisition_manifest.json")
    check = read_json("consistency_check.json")
    assert set(provider["authorized_download_symbols"]) == {"USCI", "DBC"}
    assert set(provider["downloaded_symbols_this_run"]).issubset({"USCI", "DBC"})
    assert set(provider["downloaded_symbols_ever"]).issubset({"USCI", "DBC"})
    assert provider["forbidden_product_downloaded"] is False
    assert provider["SPY_cache_refreshed"] is False
    assert provider["BIL_cache_refreshed"] is False
    assert provider["USCI_cache_refreshed"] is False
    assert provider["DBC_cache_refreshed"] is False
    assert check["only_USCI_and_DBC_provider_acquisition_authorized"] is True
    assert check["valid_caches_not_refreshed"] is True


def test_preregistration_freezes_exact_usci_wrapper_and_dbc_primary_benchmark() -> None:
    prereg = read_json("source_and_preregistration.json")
    fingerprint = read_json("candidate_fingerprint.json")
    rules = prereg["frozen_candidate_rules"]
    assert prereg["candidate_id"] == screen.CANDIDATE_ID
    assert prereg["canonical_family"] == "commodity_curve_selection"
    assert rules["candidate_asset"] == "USCI"
    assert rules["primary_benchmark"] == "DBC_buy_and_hold"
    assert rules["external_rebalance"] == "none after initial purchase"
    assert rules["BIL_switch"] is False
    assert rules["underlying_futures_reconstruction"] is False
    assert rules["manual_collateral_return_added"] is False
    assert rules["index_backfill_used"] is False
    assert fingerprint["weighting_method"] == "100pct_USCI"
    assert fingerprint["strategy_fingerprint"]


def test_adjusted_total_return_prices_are_validated() -> None:
    cache = read_json("cache_manifest.json")
    rows = {row["symbol"]: row for row in cache["series"]}
    for symbol in {"USCI", "DBC", "BIL", "SPY"}:
        assert rows[symbol]["adjusted_price_validation_result"] == "pass"
        assert rows[symbol]["missing_adj_close_count"] == 0
    assert cache["adjusted_prices_required"] is True
    assert cache["raw_close_substitution_allowed"] is False
    invariants = read_csv("accounting_data_and_exposure_invariants.csv")[0]
    assert invariants["adjusted_prices_used"] == "true"
    assert invariants["raw_close_substitution_used"] == "false"


def test_usci_and_dbc_are_purchased_once_and_held_without_timing_or_bil_switch() -> None:
    invariants = read_csv("accounting_data_and_exposure_invariants.csv")[0]
    check = read_json("consistency_check.json")
    assert invariants["initial_turnover"] == "1"
    assert invariants["subsequent_external_turnover"] == "0"
    assert invariants["portfolio_trade_count"] == "1"
    assert invariants["no_BIL_switch"] == "true"
    assert invariants["no_market_timing_signal"] == "true"
    assert check["USCI_purchased_once_and_held"] is True
    assert check["DBC_purchased_once_and_held"] is True
    assert check["no_BIL_switch_or_timing_overlay"] is True


def test_no_futures_reconstruction_or_extra_commodity_product() -> None:
    invariants = read_csv("accounting_data_and_exposure_invariants.csv")[0]
    provider = read_json("provider_acquisition_manifest.json")
    assert invariants["underlying_futures_reconstruction_used"] == "false"
    assert invariants["underlying_index_internal_turnover_estimated_or_added"] == "false"
    assert invariants["manual_collateral_return_added"] == "false"
    assert invariants["no_additional_commodity_product"] == "true"
    assert set(provider["forbidden_commodity_products"]) == {"SDCI", "GSG", "PDBC", "COMT"}


def test_usci_december_2020_methodology_boundary_is_frozen() -> None:
    regimes = {row["regime_id"]: row for row in read_csv("frozen_methodology_regimes.csv")}
    check = read_json("consistency_check.json")
    assert regimes["USCI_regime_1_pre_2020_methodology_change"]["end_date"] == "2020-12-23"
    assert regimes["USCI_regime_2_post_2020_methodology_change"]["start_date"] == "2020-12-24"
    assert all(row["methodology_boundary_frozen_before_performance"] == "true" for row in regimes.values())
    assert check["USCI_2020_12_24_boundary_frozen"] is True


def test_blocks_are_frozen_and_candidate_benchmark_dates_match() -> None:
    blocks = read_csv("frozen_evaluation_blocks.csv")
    block_results = read_csv("chronological_block_results.csv")
    check = read_json("consistency_check.json")
    assert len(blocks) == 5
    assert len(block_results) == 5
    assert all(row["frozen_before_performance"] == "true" for row in blocks)
    assert all(row["performance_computed_at_definition_time"] == "false" for row in blocks)
    assert check["chronological_blocks_frozen_before_performance"] is True
    assert check["candidate_and_benchmark_dates_match"] is True


def test_initial_transaction_cost_equivalent_and_exposure_invariants() -> None:
    full = {row["symbol"]: row for row in read_csv("full_period_metrics.csv")}
    invariants = read_csv("accounting_data_and_exposure_invariants.csv")[0]
    assert float(full["USCI"]["total_external_transaction_cost"]) == pytest.approx(float(full["DBC"]["total_external_transaction_cost"]))
    assert float(full["USCI"]["total_external_transaction_cost"]) == pytest.approx(float(full["BIL"]["total_external_transaction_cost"]))
    assert float(full["USCI"]["total_external_transaction_cost"]) == pytest.approx(float(full["SPY"]["total_external_transaction_cost"]))
    assert float(invariants["max_daily_exposure"]) <= 1.000001
    assert float(invariants["max_daily_weight_sum"]) <= 1.000001
    assert invariants["invariants_passed"] == "true"


def test_duplicate_gate_preserves_xyld_and_halloween_without_rerun() -> None:
    rows = {row["reviewed_id"]: row for row in read_csv("duplicate_review.csv")}
    check = read_json("consistency_check.json")
    assert rows["repository_prior_USCI_mentions"]["decision"] == "prior_USCI_mentions_are_commodity_basket_or_data_context_not_exact_static_USCI_vs_DBC_screen"
    assert rows["commodity_basket_etf_momentum_v1"]["exact_corrected_methodology_duplicate"] == "false"
    assert rows["xyld_static_sp500_covered_call_v1"]["decision"] == "xyld_result_preserved_not_rerun"
    assert rows["spy_halloween_nov_apr_bil_v1"]["decision"] == "halloween_result_preserved_not_rerun"
    assert check["xyld_not_rerun"] is True
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


def test_outcome_is_pre_registered_non_promotional_and_regime_based() -> None:
    outcome = read_json("screening_outcome.json")
    relative = read_csv("benchmark_relative_metrics.csv")[0]
    memory = read_csv("exact_variant_research_memory.csv")[0]
    assert outcome["outcome"] in screen.ALLOWED_OUTCOMES
    assert outcome["outcome"] == "methodology_regime_instability"
    assert float(relative["regime_1_excess_return_versus_DBC"]) < 0
    assert float(relative["regime_2_excess_return_versus_DBC"]) > 0
    assert outcome["promotion_authorized"] is False
    assert outcome["paper_demo_authorized"] is False
    assert outcome["candidate_exhaustive_authorized"] is False
    assert outcome["real_money_recommendation"] is False
    assert memory["exact_candidate_closed_for_immediate_retesting"] == "true"
    assert memory["broader_commodity_curve_selection_family_closed"] == "false"


def test_generation_is_deterministic() -> None:
    outcome_hash = sha256(EVIDENCE / "screening_outcome.json")
    metrics_hash = sha256(EVIDENCE / "full_period_metrics.csv")
    regimes_hash = sha256(EVIDENCE / "frozen_methodology_regimes.csv")
    assert read_json("consistency_check.json")["consistency_passed"] is True
    assert sha256(EVIDENCE / "screening_outcome.json") == outcome_hash
    assert sha256(EVIDENCE / "full_period_metrics.csv") == metrics_hash
    assert sha256(EVIDENCE / "frozen_methodology_regimes.csv") == regimes_hash


def test_consistency_check_passes() -> None:
    assert read_json("consistency_check.json")["consistency_passed"] is True
