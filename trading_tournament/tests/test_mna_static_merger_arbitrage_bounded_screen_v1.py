from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest

from strategy_lab.research_os.research import mna_static_merger_arbitrage_bounded_screen_v1 as screen


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "mna_static_merger_arbitrage_bounded_screen_v1" / "latest"


@pytest.fixture(scope="module", autouse=True)
def generated_screen() -> dict[str, object]:
    assert (EVIDENCE / "screening_outcome.json").exists(), "MNA bounded screen evidence must already exist"
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
        "fund_and_methodology_continuity.csv",
        "provider_acquisition_manifest.json",
        "cache_manifest.json",
        "frozen_chronological_blocks.csv",
        "frozen_methodology_regimes.csv",
        "full_period_metrics.csv",
        "chronological_block_results.csv",
        "methodology_regime_results.csv",
        "calendar_year_results.csv",
        "bil_relative_metrics.csv",
        "spy_risk_comparison.csv",
        "diversification_and_redundancy.csv",
        "accounting_data_and_exposure_invariants.csv",
        "screening_outcome.json",
        "exact_variant_research_memory.csv",
        "screen_summary.md",
        "consistency_check.json",
    }
    assert sorted(name for name in required if not (EVIDENCE / name).exists()) == []


def test_only_mna_may_be_acquired_and_existing_bil_spy_not_refreshed() -> None:
    provider = read_json("provider_acquisition_manifest.json")
    check = read_json("consistency_check.json")
    assert provider["authorized_download_symbols"] == ["MNA"]
    assert set(provider["downloaded_symbols_this_run"]).issubset({"MNA"})
    assert set(provider["downloaded_symbols_ever"]).issubset({"MNA"})
    assert provider["BIL_cache_refreshed"] is False
    assert provider["SPY_cache_refreshed"] is False
    assert provider["alternative_merger_arbitrage_product_downloaded"] is False
    assert provider["new_benchmark_downloaded"] is False
    assert check["only_MNA_provider_acquisition_authorized"] is True
    assert check["BIL_cache_not_refreshed"] is True
    assert check["SPY_cache_not_refreshed"] is True


def test_preregistration_freezes_exact_mna_wrapper_and_bil_primary_benchmark() -> None:
    prereg = read_json("source_and_preregistration.json")
    fingerprint = read_json("candidate_fingerprint.json")
    rules = prereg["frozen_candidate_rules"]
    assert prereg["candidate_id"] == screen.CANDIDATE_ID
    assert prereg["canonical_family"] == "event_driven_merger_arbitrage"
    assert rules["candidate_asset"] == "MNA"
    assert rules["primary_benchmark"] == "BIL_cash_proxy"
    assert rules["external_rebalance"] == "none after initial purchase"
    assert rules["BIL_switch"] is False
    assert rules["deal_level_reconstruction"] is False
    assert rules["acquirer_short_reconstruction"] is False
    assert rules["index_backfill_used"] is False
    assert fingerprint["weighting_method"] == "100pct_MNA"
    assert fingerprint["strategy_fingerprint"]


def test_adjusted_total_return_prices_are_used_and_validated() -> None:
    cache = read_json("cache_manifest.json")
    rows = {row["symbol"]: row for row in cache["series"]}
    for symbol in {"MNA", "BIL", "SPY"}:
        assert rows[symbol]["adjusted_price_validation_result"] == "pass"
        assert rows[symbol]["missing_adj_close_count"] == 0
    assert cache["adjusted_prices_required"] is True
    assert cache["raw_close_substitution_allowed"] is False
    invariants = read_csv("accounting_data_and_exposure_invariants.csv")[0]
    assert invariants["adjusted_prices_used"] == "true"
    assert invariants["raw_close_substitution_used"] == "false"


def test_mna_is_purchased_once_and_held_without_deal_reconstruction_or_project_shorts() -> None:
    invariants = read_csv("accounting_data_and_exposure_invariants.csv")[0]
    check = read_json("consistency_check.json")
    assert invariants["initial_turnover"] == "1"
    assert invariants["subsequent_external_turnover"] == "0"
    assert invariants["portfolio_trade_count"] == "1"
    assert invariants["deal_level_positions_reconstructed"] == "false"
    assert invariants["acquirer_short_or_hedge_positions_created_by_project"] == "false"
    assert invariants["individual_merger_deal_database_created"] == "false"
    assert check["MNA_purchased_once_and_held"] is True
    assert check["no_deal_level_positions_reconstructed"] is True
    assert check["no_project_short_or_hedge_positions_created"] is True


def test_no_alternative_merger_arbitrage_product_enters() -> None:
    provider = read_json("provider_acquisition_manifest.json")
    invariants = read_csv("accounting_data_and_exposure_invariants.csv")[0]
    assert set(provider["forbidden_merger_arbitrage_products"]) == {"ARB", "MRGR", "MARB"}
    assert provider["alternative_merger_arbitrage_product_downloaded"] is False
    assert invariants["alternative_merger_arbitrage_product_used"] == "false"


def test_regime_boundaries_are_frozen_before_performance() -> None:
    regimes = {row["regime_id"]: row for row in read_csv("frozen_methodology_regimes.csv")}
    check = read_json("consistency_check.json")
    assert regimes["regime_1_pre_2019_12_31_amendments"]["end_date"] <= "2019-12-30"
    assert regimes["regime_2_2019_12_31_to_2020_05_31"]["start_date"] >= "2019-12-31"
    assert regimes["regime_3_2020_06_01_to_2024_06_02"]["start_date"] >= "2020-06-01"
    assert regimes["transition_2024_06_03_to_2024_06_11"]["included_in_regime_specific_outcome_metrics"] == "false"
    assert regimes["regime_4_current_methodology_from_2024_06_12"]["start_date"] >= "2024-06-12"
    assert all(row["methodology_boundary_frozen_before_performance"] == "true" for row in regimes.values())
    assert check["regime_boundaries_frozen_before_performance"] is True


def test_chronological_blocks_are_frozen_and_dates_match() -> None:
    blocks = read_csv("frozen_chronological_blocks.csv")
    block_results = read_csv("chronological_block_results.csv")
    check = read_json("consistency_check.json")
    assert len(blocks) == 5
    assert len(block_results) == 5
    assert all(row["frozen_before_performance"] == "true" for row in blocks)
    assert all(row["performance_computed_at_definition_time"] == "false" for row in blocks)
    assert check["chronological_blocks_frozen_before_performance"] is True
    assert check["MNA_BIL_SPY_matching_dates"] is True


def test_initial_cost_equivalent_and_exposure_invariants() -> None:
    full = {row["symbol"]: row for row in read_csv("full_period_metrics.csv")}
    invariants = read_csv("accounting_data_and_exposure_invariants.csv")[0]
    assert float(full["MNA"]["total_project_level_transaction_cost"]) == pytest.approx(float(full["BIL"]["total_project_level_transaction_cost"]))
    assert float(full["MNA"]["total_project_level_transaction_cost"]) == pytest.approx(float(full["SPY"]["total_project_level_transaction_cost"]))
    assert float(invariants["max_daily_exposure"]) <= 1.000001
    assert float(invariants["max_daily_weight_sum"]) <= 1.000001
    assert invariants["initial_cost_equivalent_across_candidate_and_benchmarks"] == "true"
    assert invariants["invariants_passed"] == "true"


def test_existing_observations_remain_unchanged_and_no_orders_are_created() -> None:
    invariants = read_csv("accounting_data_and_exposure_invariants.csv")[0]
    check = read_json("consistency_check.json")
    assert invariants["existing_VM_DSR_USCI_combo_states_unchanged"] == "true"
    assert invariants["paper_forward_or_broker_order_created"] == "false"
    assert check["existing_observation_states_unchanged"] is True
    assert check["no_paper_demo_or_broker_order"] is True
    assert check["historical_observation_files_unchanged"] is True


def test_duplicate_gate_is_exact_and_non_mna_static_wrapper_precedents_are_not_duplicates() -> None:
    rows = {row["reviewed_id"]: row for row in read_csv("duplicate_review.csv")}
    assert rows["repository_prior_MNA_mentions"]["exact_corrected_methodology_duplicate"] == "false"
    assert rows["repository_prior_MNA_mentions"]["decision"] == "no_prior_exact_MNA_BIL_primary_static_wrapper_corrected_methodology_screen_found"
    assert rows["static_ETF_wrapper_precedents"]["decision"] == "static_wrapper_precedents_are_not_event_driven_merger_arbitrage_MNA"
    assert rows["market_neutral_pairs_lowvol_factor_rotation_USCI_VM_DSR"]["decision"] == "not_duplicate_under_exact_duplicate_gate"


def test_outcome_is_pre_registered_and_non_promotional() -> None:
    outcome = read_json("screening_outcome.json")
    memory = read_csv("exact_variant_research_memory.csv")[0]
    assert outcome["outcome"] in screen.ALLOWED_OUTCOMES
    assert outcome["promotion_authorized"] is False
    assert outcome["paper_demo_authorized"] is False
    assert outcome["candidate_exhaustive_authorized"] is False
    assert outcome["real_money_recommendation"] is False
    assert memory["broader_event_driven_merger_arbitrage_family_closed"] == "false"
    assert memory["promotion_authorized"] == "false"
    assert memory["paper_demo_authorized"] == "false"
    assert memory["candidate_exhaustive_authorized"] == "false"


def test_bil_is_primary_and_spy_is_secondary_risk_reference() -> None:
    bil = read_csv("bil_relative_metrics.csv")[0]
    spy = read_csv("spy_risk_comparison.csv")[0]
    assert bil["primary_benchmark"] == "BIL_cash_proxy"
    assert spy["secondary_reference"] == "SPY_buy_and_hold"
    assert "full_period_excess_total_return_versus_BIL" in bil
    assert "max_drawdown_difference_versus_SPY" in spy


def test_diversification_diagnostics_are_descriptive_only() -> None:
    rows = {row["reference_id"]: row for row in read_csv("diversification_and_redundancy.csv")}
    assert {"SPY", "paper_forward_vm_quality_lowvol_proxy_v1", "paper_forward_dsr_sector_equal_weight_defensive_filter_v1", "paper_forward_usci_dynamic_commodity_curve_selection_wrapper_v1", "active_combo_vm_dsr_equal_weight_v1"}.issubset(rows)
    assert all(row["descriptive_only_not_allocation_input"] == "true" for row in rows.values())


def test_generation_is_deterministic_without_rerunning_download() -> None:
    outcome_hash = sha256(EVIDENCE / "screening_outcome.json")
    metrics_hash = sha256(EVIDENCE / "full_period_metrics.csv")
    blocks_hash = sha256(EVIDENCE / "frozen_chronological_blocks.csv")
    assert read_json("consistency_check.json")["consistency_passed"] is True
    assert sha256(EVIDENCE / "screening_outcome.json") == outcome_hash
    assert sha256(EVIDENCE / "full_period_metrics.csv") == metrics_hash
    assert sha256(EVIDENCE / "frozen_chronological_blocks.csv") == blocks_hash


def test_consistency_check_passes() -> None:
    assert read_json("consistency_check.json")["consistency_passed"] is True
