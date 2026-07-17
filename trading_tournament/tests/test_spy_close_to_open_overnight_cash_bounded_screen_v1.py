from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest

from strategy_lab.research_os.research import spy_close_to_open_overnight_cash_bounded_screen_v1 as screen


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "spy_close_to_open_overnight_cash_bounded_screen_v1" / "latest"


@pytest.fixture(scope="module", autouse=True)
def generated_screen() -> dict[str, object]:
    assert (EVIDENCE / "screening_outcome.json").exists(), "SPY overnight bounded screen evidence must already exist"
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
        "provider_acquisition_manifest.json",
        "cache_and_adjustment_manifest.json",
        "valid_and_skipped_overnight_intervals.csv",
        "frozen_chronological_blocks.csv",
        "full_period_metrics.csv",
        "chronological_block_results.csv",
        "calendar_year_results.csv",
        "spy_relative_metrics.csv",
        "gross_net_cost_diagnostics.csv",
        "overnight_intraday_decomposition.csv",
        "accounting_timing_and_data_invariants.csv",
        "screening_outcome.json",
        "exact_variant_research_memory.csv",
        "screen_summary.md",
        "consistency_check.json",
        "mna_direction_level_memory.json",
    }
    assert sorted(name for name in required if not (EVIDENCE / name).exists()) == []


def test_only_spy_may_be_acquired_and_no_intraday_download() -> None:
    provider = read_json("provider_acquisition_manifest.json")
    check = read_json("consistency_check.json")
    assert provider["authorized_download_symbols"] == ["SPY"]
    assert set(provider["downloaded_symbols_this_run"]).issubset({"SPY"})
    assert provider["intraday_bars_downloaded"] is False
    assert provider["alternate_equity_etf_downloaded"] is False
    assert provider["futures_or_index_data_downloaded"] is False
    assert check["only_SPY_provider_acquisition_authorized"] is True
    assert check["no_intraday_bars_downloaded"] is True


def test_candidate_buys_only_at_close_and_sells_next_valid_open() -> None:
    prereg = read_json("source_and_preregistration.json")
    rules = prereg["frozen_rules"]
    check = read_json("consistency_check.json")
    assert rules["entry"].startswith("buy SPY at official regular-session close")
    assert rules["exit"].startswith("sell complete SPY position at official regular-session open")
    assert check["candidate_buys_only_at_session_close"] is True
    assert check["candidate_sells_only_at_next_valid_session_open"] is True


def test_weekend_and_exchange_holiday_intervals_remain_valid_overnight_holdings() -> None:
    intervals = read_csv("valid_and_skipped_overnight_intervals.csv")
    weekend_rows = [row for row in intervals if row["interval_valid"] == "true" and row["weekend_or_exchange_holiday_interval"] == "true"]
    assert weekend_rows
    assert max(int(row["calendar_gap_days"]) for row in weekend_rows) > 1
    assert read_json("consistency_check.json")["weekend_and_holiday_intervals_retained"] is True


def test_intraday_exposure_is_zero_and_open_to_close_strategy_not_created() -> None:
    invariants = read_csv("accounting_timing_and_data_invariants.csv")[0]
    decomposition = read_csv("overnight_intraday_decomposition.csv")[0]
    assert invariants["intraday_exposure"] == "0"
    assert invariants["open_to_close_strategy_created"] == "false"
    assert decomposition["open_to_close_is_diagnostic_only"] == "true"
    assert decomposition["open_to_close_strategy_created"] == "false"


def test_no_next_open_information_used_before_prior_close_entry() -> None:
    invariants = read_csv("accounting_timing_and_data_invariants.csv")[0]
    intervals = read_csv("valid_and_skipped_overnight_intervals.csv")
    assert invariants["no_lookahead_result"] == "true"
    assert invariants["entry_uses_next_open_information"] == "false"
    assert all(row["entry_uses_prior_close_only"] == "true" for row in intervals)


def test_adjusted_open_is_constructed_consistently() -> None:
    manifest = read_json("cache_and_adjustment_manifest.json")
    intervals = read_csv("valid_and_skipped_overnight_intervals.csv")
    sample = next(row for row in intervals if row["interval_valid"] == "true")
    expected = float(sample["exit_raw_open"]) * float(sample["exit_adjustment_factor"])
    assert float(sample["exit_adjusted_open"]) == pytest.approx(expected)
    assert manifest["adjustment_method"] == "adjusted_open_t = raw_open_t * (adjusted_close_t / raw_close_t)"
    assert read_json("consistency_check.json")["adjusted_open_constructed_consistently"] is True


def test_raw_open_is_never_compared_with_adjusted_close_and_no_forward_fill() -> None:
    manifest = read_json("cache_and_adjustment_manifest.json")
    invariants = read_csv("accounting_timing_and_data_invariants.csv")[0]
    intervals = read_csv("valid_and_skipped_overnight_intervals.csv")
    assert manifest["raw_open_compared_with_adjusted_close"] is False
    assert manifest["forward_fill_used"] is False
    assert invariants["raw_open_compared_with_adjusted_close"] == "false"
    assert invariants["prices_forward_filled"] == "false"
    assert all(row["no_forward_fill"] == "true" for row in intervals)


def test_missing_opens_or_closes_are_skipped_by_rule() -> None:
    manifest = read_json("cache_and_adjustment_manifest.json")
    intervals = read_csv("valid_and_skipped_overnight_intervals.csv")
    skipped = [row for row in intervals if row["interval_valid"] == "false"]
    assert int(manifest["skipped_interval_count"]) == len(skipped)
    assert all(row["skip_reason"] for row in skipped)


def test_costs_apply_to_both_legs_of_every_completed_cycle() -> None:
    cost = read_csv("gross_net_cost_diagnostics.csv")[0]
    valid = int(cost["valid_overnight_count"])
    assert int(cost["number_of_purchases"]) == valid
    assert int(cost["number_of_sales"]) == valid
    assert int(cost["total_trade_count"]) == valid * 2
    assert cost["costs_applied_to_entry_and_exit"] == "true"


def test_gross_diagnostics_do_not_control_outcome() -> None:
    outcome = read_json("screening_outcome.json")
    assert outcome["gross_diagnostic_controls_outcome"] is False
    assert read_json("consistency_check.json")["gross_diagnostic_not_outcome_controlling"] is True


def test_spy_benchmark_timestamps_match_candidate_timestamps() -> None:
    prereg = read_json("source_and_preregistration.json")
    relative = read_csv("spy_relative_metrics.csv")[0]
    invariants = read_csv("accounting_timing_and_data_invariants.csv")[0]
    assert prereg["pre_performance_freeze"]["primary_benchmark"] == "SPY_buy_and_hold_matching_timestamps"
    assert relative["primary_benchmark"] == "SPY_buy_and_hold_matching_timestamps"
    assert invariants["matching_timestamp_benchmark_validation"] == "true"


def test_exposure_never_exceeds_one() -> None:
    invariants = read_csv("accounting_timing_and_data_invariants.csv")[0]
    assert float(invariants["maximum_exposure"]) <= 1.000001
    assert float(invariants["maximum_weight_sum"]) <= 1.000001
    assert read_json("consistency_check.json")["exposure_never_exceeds_1"] is True


def test_existing_observations_and_mna_evidence_remain_unchanged() -> None:
    invariants = read_csv("accounting_timing_and_data_invariants.csv")[0]
    mna_memory = read_json("mna_direction_level_memory.json")
    assert invariants["existing_VM_DSR_USCI_combo_states_unchanged"] == "true"
    assert invariants["MNA_original_evidence_packet_unchanged"] == "true"
    assert mna_memory["original_formal_outcome_preserved"] == "methodology_regime_instability"
    assert mna_memory["direction_level_interpretation"] == "diversification_value_without_sufficient_cash_edge"
    assert mna_memory["current_regime_validation_authorized"] is False


def test_no_paper_demo_broker_order_or_promotion() -> None:
    outcome = read_json("screening_outcome.json")
    invariants = read_csv("accounting_timing_and_data_invariants.csv")[0]
    assert invariants["paper_forward_or_broker_order_created"] == "false"
    assert outcome["promotion_authorized"] is False
    assert outcome["paper_demo_authorized"] is False
    assert outcome["candidate_exhaustive_authorized"] is False
    assert outcome["real_money_recommendation"] is False


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
