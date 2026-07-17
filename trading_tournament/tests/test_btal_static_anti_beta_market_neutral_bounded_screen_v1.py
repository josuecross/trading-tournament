from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest

from strategy_lab.research_os.research import btal_static_anti_beta_market_neutral_bounded_screen_v1 as screen


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "btal_static_anti_beta_market_neutral_bounded_screen_v1" / "latest"


@pytest.fixture(scope="module", autouse=True)
def generated_screen() -> dict[str, object]:
    assert (EVIDENCE / "screening_outcome.json").exists(), "BTAL bounded screen evidence must already exist"
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
        "spy_beta_correlation_and_drawdown.csv",
        "rolling_correlation_diagnostics.csv",
        "diversification_and_redundancy.csv",
        "accounting_data_and_exposure_invariants.csv",
        "screening_outcome.json",
        "exact_variant_research_memory.csv",
        "overnight_direction_level_memory.json",
        "screen_summary.md",
        "consistency_check.json",
    }
    assert sorted(name for name in required if not (EVIDENCE / name).exists()) == []


def test_only_btal_may_be_acquired_and_bil_spy_not_refreshed() -> None:
    provider = read_json("provider_acquisition_manifest.json")
    check = read_json("consistency_check.json")
    assert provider["authorized_download_symbols"] == ["BTAL"]
    assert set(provider["downloaded_symbols_this_run"]).issubset({"BTAL"})
    assert set(provider["downloaded_symbols_ever"]).issubset({"BTAL"})
    assert provider["BIL_cache_refreshed"] is False
    assert provider["SPY_cache_refreshed"] is False
    assert provider["alternative_anti_beta_product_downloaded"] is False
    assert provider["underlying_index_or_constituents_downloaded"] is False
    assert check["only_BTAL_provider_acquisition_authorized"] is True
    assert check["BIL_cache_not_refreshed"] is True
    assert check["SPY_cache_not_refreshed"] is True


def test_adjusted_total_return_prices_are_used() -> None:
    cache = read_json("cache_manifest.json")
    rows = {row["symbol"]: row for row in cache["series"]}
    for symbol in {"BTAL", "BIL", "SPY"}:
        assert rows[symbol]["adjusted_price_validation_result"] == "pass"
        assert rows[symbol]["missing_adj_close_count"] == 0
    assert cache["adjusted_prices_required"] is True
    assert cache["raw_close_substitution_allowed"] is False
    invariants = read_csv("accounting_data_and_exposure_invariants.csv")[0]
    assert invariants["adjusted_prices_used"] == "true"
    assert invariants["raw_close_substitution_used"] == "false"


def test_btal_is_bought_once_and_held_without_constituent_reconstruction() -> None:
    prereg = read_json("source_and_preregistration.json")
    invariants = read_csv("accounting_data_and_exposure_invariants.csv")[0]
    assert prereg["frozen_candidate_rules"]["candidate_asset"] == "BTAL"
    assert prereg["frozen_candidate_rules"]["external_rebalance"] == "none after initial purchase"
    assert invariants["initial_project_turnover"] == "1"
    assert invariants["project_trade_count"] == "1"
    assert invariants["underlying_long_or_short_securities_reconstructed"] == "false"
    assert invariants["alternative_anti_beta_product_used"] == "false"


def test_no_project_level_short_or_leveraged_position_is_created() -> None:
    prereg = read_json("source_and_preregistration.json")
    invariants = read_csv("accounting_data_and_exposure_invariants.csv")[0]
    assert prereg["frozen_candidate_rules"]["project_level_shorting"] is False
    assert prereg["frozen_candidate_rules"]["project_level_leverage"] is False
    assert invariants["project_level_short_position_created"] == "false"
    assert invariants["project_level_leverage_created"] == "false"
    assert read_json("consistency_check.json")["no_project_level_short_or_leveraged_position"] is True


def test_no_alternative_anti_beta_product_enters_screen() -> None:
    provider = read_json("provider_acquisition_manifest.json")
    assert provider["alternative_anti_beta_product_downloaded"] is False
    assert provider["underlying_index_or_constituents_downloaded"] is False
    assert set(provider["forbidden_market_neutral_products"]) == {"BTALX", "MOM", "CHEP", "QMN", "CSM"}


def test_february_2022_methodology_boundary_is_frozen_before_performance() -> None:
    regimes = {row["regime_id"]: row for row in read_csv("frozen_methodology_regimes.csv")}
    check = read_json("consistency_check.json")
    assert regimes["regime_1_passive_index_tracking_history"]["end_date"] <= "2022-02-13"
    assert regimes["regime_2_current_active_rules_based_history"]["start_date"] >= "2022-02-14"
    assert all(row["methodology_boundary_frozen_before_performance"] == "true" for row in regimes.values())
    assert check["methodology_boundary_frozen"] is True


def test_chronological_blocks_are_frozen_and_dates_match() -> None:
    blocks = read_csv("frozen_chronological_blocks.csv")
    block_results = read_csv("chronological_block_results.csv")
    check = read_json("consistency_check.json")
    assert len(blocks) == 5
    assert len(block_results) == 5
    assert all(row["frozen_before_performance"] == "true" for row in blocks)
    assert all(row["performance_computed_at_definition_time"] == "false" for row in blocks)
    assert check["chronological_blocks_frozen_before_performance"] is True
    assert check["BTAL_BIL_SPY_matching_dates"] is True


def test_initial_cost_equivalent_and_project_exposure_invariants() -> None:
    full = {row["symbol"]: row for row in read_csv("full_period_metrics.csv")}
    invariants = read_csv("accounting_data_and_exposure_invariants.csv")[0]
    assert float(full["BTAL"]["total_project_transaction_cost"]) == pytest.approx(float(full["BIL"]["total_project_transaction_cost"]))
    assert float(full["BTAL"]["total_project_transaction_cost"]) == pytest.approx(float(full["SPY"]["total_project_transaction_cost"]))
    assert float(invariants["maximum_project_exposure"]) <= 1.000001
    assert float(invariants["maximum_project_weight_sum"]) <= 1.000001
    assert invariants["invariants_passed"] == "true"


def test_rolling_correlations_are_descriptive_and_cannot_affect_holdings() -> None:
    rolling = read_csv("rolling_correlation_diagnostics.csv")
    invariants = read_csv("accounting_data_and_exposure_invariants.csv")[0]
    assert rolling
    assert all(row["descriptive_only"] == "true" for row in rolling[:10])
    assert all(row["affects_holdings"] == "false" for row in rolling[:10])
    assert invariants["rolling_correlation_affects_holdings"] == "false"
    assert read_json("consistency_check.json")["rolling_correlations_descriptive_only"] is True


def test_overnight_packet_remains_unchanged_and_direction_memory_is_recorded() -> None:
    memory = read_json("overnight_direction_level_memory.json")
    invariants = read_csv("accounting_data_and_exposure_invariants.csv")[0]
    assert memory["original_formal_outcome_preserved"] == "no_material_edge"
    assert memory["direction_level_failure_interpretation"] == "gross_anomaly_without_comparative_edge_and_daily_turnover_cost_destruction"
    assert memory["further_overnight_validation_authorized"] is False
    assert invariants["overnight_packet_unchanged"] == "true"


def test_existing_observations_remain_unchanged_and_no_orders_are_created() -> None:
    invariants = read_csv("accounting_data_and_exposure_invariants.csv")[0]
    check = read_json("consistency_check.json")
    assert invariants["existing_VM_DSR_USCI_combo_states_unchanged"] == "true"
    assert invariants["paper_forward_or_broker_order_created"] == "false"
    assert check["existing_observation_states_unchanged"] is True
    assert check["no_paper_demo_or_broker_order"] is True


def test_duplicate_gate_is_exact_and_vm_splv_mna_controls_are_not_duplicates() -> None:
    rows = {row["reviewed_id"]: row for row in read_csv("duplicate_review.csv")}
    assert rows["repository_prior_BTAL_mentions"]["exact_corrected_methodology_duplicate"] == "false"
    assert rows["repository_prior_BTAL_mentions"]["decision"] == "no_prior_exact_BTAL_BIL_primary_static_wrapper_corrected_methodology_screen_found"
    assert rows["VM_SPLV_QUAL_pairs_MNA_covered_call_active_combo"]["decision"] == "not_duplicate_materially_distinct_short_high_beta_negative_beta_wrapper"


def test_bil_is_primary_and_spy_negative_beta_diagnostics_exist() -> None:
    bil = read_csv("bil_relative_metrics.csv")[0]
    spy = read_csv("spy_beta_correlation_and_drawdown.csv")[0]
    assert bil["primary_benchmark"] == "BIL_cash_proxy"
    assert spy["secondary_risk_benchmark"] == "SPY_buy_and_hold"
    assert "full_period_daily_return_correlation_with_SPY" in spy
    assert "estimated_full_period_beta_to_SPY" in spy


def test_outcome_is_frozen_non_promotional_and_family_preserved() -> None:
    outcome = read_json("screening_outcome.json")
    memory = read_csv("exact_variant_research_memory.csv")[0]
    assert outcome["outcome"] in screen.ALLOWED_OUTCOMES
    assert outcome["promotion_authorized"] is False
    assert outcome["paper_demo_authorized"] is False
    assert outcome["candidate_exhaustive_authorized"] is False
    assert outcome["real_money_recommendation"] is False
    assert memory["broader_market_neutral_anti_beta_family_closed"] == "false"


def test_diversification_rows_are_non_optimized_comparisons() -> None:
    rows = read_csv("diversification_and_redundancy.csv")
    assert {row["reference_id"] for row in rows} == {
        "paper_forward_vm_quality_lowvol_proxy_v1",
        "paper_forward_dsr_sector_equal_weight_defensive_filter_v1",
        "paper_forward_usci_dynamic_commodity_curve_selection_wrapper_v1",
        "active_combo_vm_dsr_equal_weight_v1",
    }
    assert all(row["optimized_combination_calculated"] == "false" for row in rows)


def test_output_generation_is_deterministic() -> None:
    outcome_hash = sha256(EVIDENCE / "screening_outcome.json")
    metrics_hash = sha256(EVIDENCE / "full_period_metrics.csv")
    blocks_hash = sha256(EVIDENCE / "frozen_chronological_blocks.csv")
    assert read_json("consistency_check.json")["consistency_passed"] is True
    assert sha256(EVIDENCE / "screening_outcome.json") == outcome_hash
    assert sha256(EVIDENCE / "full_period_metrics.csv") == metrics_hash
    assert sha256(EVIDENCE / "frozen_chronological_blocks.csv") == blocks_hash


def test_consistency_check_passes() -> None:
    assert read_json("consistency_check.json")["consistency_passed"] is True
