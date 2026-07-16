from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

from strategy_lab.research_os.research import spy_halloween_nov_apr_bil_bounded_screen_v1 as screen


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "spy_halloween_nov_apr_bil_bounded_screen_v1" / "latest"


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
        "cache_manifest.json",
        "frozen_switch_dates.csv",
        "frozen_evaluation_blocks.csv",
        "full_period_metrics.csv",
        "chronological_block_results.csv",
        "calendar_year_results.csv",
        "benchmark_relative_metrics.csv",
        "accounting_and_exposure_invariants.csv",
        "screening_outcome.json",
        "exact_variant_research_memory.csv",
        "screen_summary.md",
        "consistency_check.json",
    }
    assert sorted(name for name in required if not (EVIDENCE / name).exists()) == []


def test_source_preregistration_and_fingerprint_are_exact() -> None:
    prereg = read_json("source_and_preregistration.json")
    fingerprint = read_json("candidate_fingerprint.json")
    assert prereg["candidate_id"] == screen.CANDIDATE_ID
    assert prereg["source"]["doi"] == "10.1257/000282802762024683"
    assert prereg["frozen_rules"]["universe"] == ["SPY", "BIL"]
    assert prereg["frozen_rules"]["lookback"] == "none"
    assert prereg["frozen_rules"]["market_derived_filter"] == "none"
    assert prereg["parameter_search_prohibited"] is True
    assert fingerprint["family"] == "equity_calendar_seasonality"
    assert fingerprint["rebalance_frequency"] == "twice_yearly_april_october_close"


def test_april_and_october_switch_dates_generated_correctly() -> None:
    dates = pd.to_datetime(
        [
            "2024-04-26",
            "2024-04-29",
            "2024-04-30",
            "2024-05-01",
            "2024-10-29",
            "2024-10-30",
            "2024-10-31",
            "2024-11-01",
        ]
    )
    rows = screen.generate_switch_dates(pd.DatetimeIndex(dates), pd.DatetimeIndex(dates))
    april = next(row for row in rows if row["switch_month"] == 4)
    october = next(row for row in rows if row["switch_month"] == 10)
    assert str(april["execution_date"]) == "2024-04-30"
    assert april["target_after_close"] == "BIL"
    assert str(october["execution_date"]) == "2024-10-31"
    assert october["target_after_close"] == "SPY"


def test_missing_scheduled_date_delays_to_next_common_valid_session() -> None:
    spy_dates = pd.to_datetime(["2024-04-29", "2024-04-30", "2024-05-01"])
    bil_dates = pd.to_datetime(["2024-04-29", "2024-05-01"])
    rows = screen.generate_switch_dates(pd.DatetimeIndex(spy_dates), pd.DatetimeIndex(bil_dates))
    april = next(row for row in rows if row["switch_month"] == 4)
    assert str(april["scheduled_switch_date"]) == "2024-04-30"
    assert str(april["execution_date"]) == "2024-05-01"
    assert april["delayed_to_next_common_session"] is True


def test_strategy_holds_only_spy_in_nov_apr_and_bil_in_may_oct() -> None:
    dates = pd.to_datetime(["2024-04-29", "2024-04-30", "2024-05-01", "2024-10-30", "2024-10-31", "2024-11-01"])
    prices = pd.DataFrame({"SPY": [100, 101, 102, 103, 104, 105], "BIL": [50, 50.1, 50.2, 50.3, 50.4, 50.5]}, index=dates)
    switches = screen.generate_switch_dates(pd.DatetimeIndex(dates), pd.DatetimeIndex(dates))
    path, _stats = screen.simulate_path(prices, switches, cost=True)
    by_date = {row["date"]: row for row in path.to_dict("records")}
    assert by_date[pd.Timestamp("2024-04-29").date()]["SPY_weight"] == pytest.approx(1.0)
    assert by_date[pd.Timestamp("2024-05-01").date()]["BIL_weight"] == pytest.approx(1.0)
    assert by_date[pd.Timestamp("2024-11-01").date()]["SPY_weight"] == pytest.approx(1.0)


def test_exactly_two_normal_switches_per_complete_year() -> None:
    rows = read_csv("frozen_switch_dates.csv")
    by_year: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        by_year.setdefault(row["switch_year"], []).append(row)
    complete_years = [year for year in by_year if year not in {"2007", "2026"}]
    assert complete_years
    assert all(len(by_year[year]) == 2 for year in complete_years)
    assert all({row["switch_month"] for row in by_year[year]} == {"4", "10"} for year in complete_years)


def test_no_market_signal_or_lookback_is_introduced() -> None:
    prereg = read_json("source_and_preregistration.json")
    check = read_json("consistency_check.json")
    assert prereg["frozen_rules"]["ranking"] == "none"
    assert prereg["frozen_rules"]["lookback"] == "none"
    assert prereg["frozen_rules"]["market_derived_filter"] == "none"
    assert check["no_market_derived_signal"] is True
    assert check["no_calendar_parameter_search"] is True


def test_actual_holdings_cost_accounting_and_exposure_invariants() -> None:
    invariants = read_csv("accounting_and_exposure_invariants.csv")[0]
    assert invariants["actual_holdings_accounting_used"] == "true"
    assert invariants["BIL_cash_replacement_remainder_only"] == "true"
    assert float(invariants["max_daily_exposure"]) <= 1.000001
    assert float(invariants["max_daily_weight_sum"]) <= 1.000001
    assert invariants["zero_target_weights_not_stale_forward_filled"] == "true"
    assert invariants["prices_not_forward_filled"] == "true"
    assert invariants["invariants_passed"] == "true"


def test_blocks_are_frozen_and_benchmark_dates_match() -> None:
    blocks = read_csv("frozen_evaluation_blocks.csv")
    block_results = read_csv("chronological_block_results.csv")
    check = read_json("consistency_check.json")
    assert len(blocks) == 5
    assert len(block_results) == 5
    assert all(row["frozen_before_performance"] == "true" for row in blocks)
    assert check["evaluation_blocks_frozen_before_performance"] is True
    assert check["SPY_benchmark_dates_match_candidate_dates"] is True


def test_turn_of_month_is_not_rerun_and_duplicate_gate_is_narrow() -> None:
    rows = read_csv("duplicate_review.csv")
    tom = next(row for row in rows if row["reviewed_id"] == "spy_turn_of_month_bil_v1")
    halloween = next(row for row in rows if row["reviewed_id"] == "sell_in_may_halloween_effect")
    check = read_json("consistency_check.json")
    assert tom["decision"] == "materially_distinct_not_rerun"
    assert halloween["decision"] == "intake_only_not_blocking"
    assert check["turn_of_month_not_rerun"] is True


def test_outcome_and_exact_variant_memory() -> None:
    outcome = read_json("screening_outcome.json")
    memory = read_csv("exact_variant_research_memory.csv")[0]
    assert outcome["outcome"] in screen.ALLOWED_OUTCOMES
    assert outcome["outcome"] == "risk_reduction_without_return_edge"
    assert outcome["primary_failure_reason"] == "Weak versus primary benchmark"
    assert memory["exact_candidate_closed_for_immediate_retesting"] == "true"
    assert memory["broader_family_closed"] == "false"
    assert memory["lifecycle_state_changed"] == "false"


def test_registry_active_observations_and_guardrails_unchanged() -> None:
    invariants = read_csv("accounting_and_exposure_invariants.csv")[0]
    outcome = read_json("screening_outcome.json")
    check = read_json("consistency_check.json")
    assert invariants["registry_byte_identical"] == "true"
    assert invariants["active_observations_unchanged"] == "true"
    assert outcome["provider_download"] is False
    assert outcome["promotion_authorized"] is False
    assert outcome["paper_demo_authorized"] is False
    assert outcome["candidate_exhaustive_authorized"] is False
    assert check["real_money_recommendation"] is False


def test_generation_is_deterministic() -> None:
    outcome_hash = sha256(EVIDENCE / "screening_outcome.json")
    metrics_hash = sha256(EVIDENCE / "full_period_metrics.csv")
    switch_hash = sha256(EVIDENCE / "frozen_switch_dates.csv")
    rerun = screen.run()
    assert rerun["consistency_passed"] is True
    assert sha256(EVIDENCE / "screening_outcome.json") == outcome_hash
    assert sha256(EVIDENCE / "full_period_metrics.csv") == metrics_hash
    assert sha256(EVIDENCE / "frozen_switch_dates.csv") == switch_hash
