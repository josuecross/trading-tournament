from __future__ import annotations

import csv
import json
from pathlib import Path

import pandas as pd
import pytest

from strategy_lab.research_os.research import splv_static_low_vol_factor_validation_v1 as validation


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "splv_static_low_vol_factor_validation_v1" / "latest"


@pytest.fixture(scope="module", autouse=True)
def generated_validation_evidence() -> dict[str, object]:
    return validation.run()


def read_json(name: str) -> dict[str, object]:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def read_csv(name: str) -> list[dict[str, str]]:
    with (EVIDENCE / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def candidate_rows(name: str) -> list[dict[str, str]]:
    return [row for row in read_csv(name) if row["benchmark_id"] == "SPY_buy_hold"]


def test_required_artifacts_exist() -> None:
    required = {
        "validation_manifest.json",
        "validation_summary.md",
        "monthly_start_90d_results.csv",
        "monthly_start_180d_results.csv",
        "non_overlapping_90d_results.csv",
        "non_overlapping_180d_results.csv",
        "full_period_metrics.csv",
        "chronological_thirds_metrics.csv",
        "benchmark_win_rates.csv",
        "return_risk_joint_outcomes.csv",
        "benchmark_relative_metrics.csv",
        "accounting_and_alignment_invariants.csv",
        "validation_outcome.json",
        "exact_variant_research_memory.csv",
        "artifact_lineage.csv",
        "consistency_check.json",
    }
    missing = sorted(name for name in required if not (EVIDENCE / name).exists())
    assert missing == []


def test_manifest_freezes_candidate_and_prior_screen_cache_hash() -> None:
    manifest = read_json("validation_manifest.json")
    assert manifest["candidate_id"] == validation.CANDIDATE_ID
    assert manifest["candidate_instrument"] == "SPLV"
    assert manifest["splv_cache_hash_matches_screen"] is True
    assert manifest["provider_download"] is False
    assert manifest["intraday_data_used"] is False
    assert manifest["promotion_authorized"] is False
    assert manifest["paper_demo_authorized"] is False
    assert manifest["parameter_wrapper_benchmark_or_period_selection_after_results_allowed"] is False
    assert manifest["manifest_consistency_passed_before_performance"] is True


def test_exhaustive_monthly_start_window_generation() -> None:
    manifest = read_json("validation_manifest.json")
    rows = candidate_rows("monthly_start_90d_results.csv")
    primary = manifest["primary_common_valid_period"]
    splv = validation.read_close("SPLV")
    spy = validation.read_close("SPY")
    dates = splv.dropna().index.intersection(spy.dropna().index).sort_values()
    expected = validation.generate_monthly_start_periods(dates, 90)
    assert len(rows) == len(expected)
    assert len(rows) == manifest["window_generation_rules"]["monthly_start_90_count"]
    for row, period in zip(rows[:12], expected[:12]):
        assert row["window_start"] == str(period.start_date.date())
        assert row["window_end"] == str(period.end_date.date())
        assert pd.Timestamp(row["window_start"]).day <= 7
    assert rows[0]["window_start"] == primary["start"]


def test_monthly_180_generation_count_matches_manifest() -> None:
    manifest = read_json("validation_manifest.json")
    rows = candidate_rows("monthly_start_180d_results.csv")
    assert len(rows) == manifest["window_generation_rules"]["monthly_start_180_count"]
    assert all(row["horizon_days"] == "180" for row in rows)


def test_deterministic_non_overlapping_windows() -> None:
    rows90 = candidate_rows("non_overlapping_90d_results.csv")
    rows180 = candidate_rows("non_overlapping_180d_results.csv")
    assert rows90
    assert rows180
    for rows, horizon in [(rows90, 90), (rows180, 180)]:
        for prev, current in zip(rows, rows[1:]):
            assert prev["window_end"] == current["window_start"]
        assert all(int(row["trading_return_days"]) == horizon for row in rows)


def test_mechanical_chronological_third_boundaries() -> None:
    manifest = read_json("validation_manifest.json")
    thirds = manifest["window_generation_rules"]["chronological_third_boundaries"]
    rows = [row for row in read_csv("chronological_thirds_metrics.csv") if row["benchmark_id"] == "SPY_buy_hold"]
    assert len(rows) == 3
    assert [row["period_id"] for row in rows] == [
        "chronological_third_early",
        "chronological_third_middle",
        "chronological_third_recent",
    ]
    assert [row["window_start"] for row in rows] == [third["start"] for third in thirds]
    assert [row["window_end"] for row in rows] == [third["end"] for third in thirds]


def test_full_period_buy_and_hold_accounting() -> None:
    full = [row for row in read_csv("full_period_metrics.csv") if row["benchmark_id"] == "SPY_buy_hold"][0]
    manifest = read_json("validation_manifest.json")
    assert full["window_start"] == manifest["primary_common_valid_period"]["start"]
    assert full["window_end"] == manifest["primary_common_valid_period"]["end"]
    assert full["entry_cost_treatment"] == "direct_buy_hold_entry_cost_applied_equally"
    assert full["actual_shares_held"] == "True"
    assert full["no_artificial_daily_or_quarterly_turnover"] == "True"


def test_date_alignment_with_each_benchmark() -> None:
    for filename in [
        "monthly_start_90d_results.csv",
        "monthly_start_180d_results.csv",
        "non_overlapping_90d_results.csv",
        "non_overlapping_180d_results.csv",
    ]:
        rows = read_csv(filename)
        assert rows
        available = [row for row in rows if row["benchmark_available"] == "True"]
        assert available
        assert all(row["matching_dates_used"] == "True" for row in available)


def test_equal_entry_cost_treatment_for_direct_buy_hold_comparisons() -> None:
    rows = read_csv("monthly_start_90d_results.csv")
    direct = [row for row in rows if row["benchmark_id"] in {"SPY_buy_hold", "BIL_cash_proxy"}]
    assert direct
    assert all(row["entry_cost_treatment"] == "direct_buy_hold_entry_cost_applied_equally" for row in direct)
    native = [row for row in rows if row["benchmark_id"] in {validation.ACTIVE_VM_ID, validation.ACTIVE_COMBO_ID, "SPY_200d_trend_model"}]
    assert native
    assert all(row["entry_cost_treatment"] == "native_frozen_series_costs_preserved" for row in native)


def test_no_provider_calls_alternative_wrappers_or_parameters() -> None:
    manifest = read_json("validation_manifest.json")
    invariants = read_csv("accounting_and_alignment_invariants.csv")[0]
    assert manifest["candidate_instrument"] == "SPLV"
    assert invariants["no_provider_call_or_cache_refresh"] == "True"
    assert invariants["no_bil_or_tactical_logic"] == "True"
    assert invariants["actual_etf_shares_held"] == "True"
    assert invariants["no_artificial_daily_or_quarterly_turnover"] == "True"


def test_benchmark_relative_tables_have_stable_ordering() -> None:
    rows = read_csv("benchmark_relative_metrics.csv")
    keys = [(row["validation_set"], row["horizon_days"], row["benchmark_id"]) for row in rows]
    assert keys == sorted(keys, key=lambda item: (["monthly_start", "non_overlapping"].index(item[0]), int(item[1]), validation.BENCHMARK_IDS.index(item[2])))


def test_outcome_is_non_promotional_and_allowed() -> None:
    outcome = read_json("validation_outcome.json")
    memory = read_csv("exact_variant_research_memory.csv")[0]
    assert outcome["validation_outcome"] in validation.VALIDATION_OUTCOMES
    assert outcome["promotion_authorized"] is False
    assert outcome["paper_demo_authorized"] is False
    assert outcome["candidate_exhaustive_authorized"] is False
    assert outcome["strategy_variants_created"] is False
    assert memory["splv_variants_created"] == "False"
    assert memory["usmv_tested"] == "False"
    assert memory["timing_overlay_added"] == "False"


def test_registry_and_active_states_unchanged() -> None:
    invariants = read_csv("accounting_and_alignment_invariants.csv")[0]
    check = read_json("consistency_check.json")
    assert invariants["registry_byte_identical"] == "True"
    assert invariants["active_vm_state_unchanged"] == "True"
    assert invariants["active_combo_state_unchanged"] == "True"
    assert check["registry_byte_identical"] is True
    assert check["active_observations_unchanged"] is True
    assert check["active_combo_unchanged"] is True


def test_generation_is_deterministic() -> None:
    first_manifest = read_json("validation_manifest.json")
    first_outcome = read_json("validation_outcome.json")
    first_relative = (EVIDENCE / "benchmark_relative_metrics.csv").read_text(encoding="utf-8")
    rerun = validation.run()
    second_manifest = read_json("validation_manifest.json")
    second_outcome = read_json("validation_outcome.json")
    second_relative = (EVIDENCE / "benchmark_relative_metrics.csv").read_text(encoding="utf-8")
    assert rerun["consistency_passed"] is True
    assert second_manifest == first_manifest
    assert second_outcome == first_outcome
    assert second_relative == first_relative
