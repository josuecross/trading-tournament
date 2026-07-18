from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

from strategy_lab.research_os.universe_expansion import faber_10m_sma_long_bil_portability_v1 as faber


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "faber_10m_sma_long_bil_portability_v1" / "latest"
REGISTRY = ROOT / "strategy_lab" / "strategy_registry.yaml"
ACTIVE_OBSERVATIONS = ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@pytest.fixture(scope="module", autouse=True)
def generated_evidence() -> dict[str, object]:
    return faber.run()


def read_csv(name: str) -> list[dict[str, str]]:
    with (EVIDENCE / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_json(name: str) -> dict[str, object]:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def synthetic_monthly(prices: list[float]) -> pd.DataFrame:
    periods = pd.period_range("2020-01", periods=len(prices), freq="M")
    dates = [period.to_timestamp(how="end").normalize() for period in periods]
    return pd.DataFrame({"period": periods.astype(str), "observation_date": dates, "adj_close": prices})


def test_required_outputs_exist() -> None:
    for name in faber.OUTPUT_FILES:
        assert (EVIDENCE / name).exists(), name


def test_prior_universe_packets_remain_byte_identical() -> None:
    payload = read_json("pilot_universe_hash_verification.json")
    assert payload["prior_universe_packets_byte_identical"] is True
    assert payload["protected_before"] == payload["protected_after"]
    assert read_json("consistency_check.json")["prior_universe_packets_byte_identical"] is True


def test_only_frozen_43_risky_instruments_and_bil_are_used() -> None:
    ledger = read_csv("exact_configuration_trial_ledger.csv")
    assert [row["symbol"] for row in ledger] == list(faber.RISKY_INSTRUMENTS)
    assert len(ledger) == 43
    source = read_json("source_and_preregistration.json")
    assert source["instruments"] == list(faber.RISKY_INSTRUMENTS)
    assert source["cash_proxy"] == "BIL"
    assert read_json("consistency_check.json")["only_frozen_43_risky_instruments_and_bil_used"] is True


def test_no_reserve_or_off_list_wrapper_enters() -> None:
    symbols = {row["symbol"] for row in read_csv("exact_configuration_trial_ledger.csv")}
    forbidden = {"XLC", "XLRE", "IFRA", "DBE", "VOO", "IVV", "VNQ", "REET"}
    assert symbols.isdisjoint(forbidden)
    assert read_json("consistency_check.json")["no_reserve_or_off_list_wrapper_entered"] is True


def test_source_parameter_is_exactly_10_months() -> None:
    source = read_json("source_and_preregistration.json")
    assert source["frozen_rule"]["parameter_months"] == 10
    assert read_json("consistency_check.json")["source_parameter_months"] == 10


def test_each_valid_sma_uses_exactly_ten_monthly_adjusted_closes() -> None:
    signals = read_csv("frozen_signal_dates.csv")
    valid = [row for row in signals if row["signal_status"] in {"positive_signal_select_risky", "negative_signal_select_bil", "equal_signal_retain_prior_allocation"}]
    assert valid
    assert {row["sma_observation_count"] for row in valid} == {"10"}


def test_signal_month_end_precedes_execution_and_same_close_is_impossible() -> None:
    executions = read_csv("frozen_execution_dates.csv")
    assert executions
    assert all(pd.Timestamp(row["signal_month_end_date"]) < pd.Timestamp(row["execution_date"]) for row in executions)
    assert {row["same_close_execution"] for row in executions} == {"false"}


def test_positive_signal_selects_risky_instrument() -> None:
    common_index = pd.date_range("2020-10-30", periods=3, freq="B")
    signals, executions, _skips = faber.build_signal_schedule("TEST", synthetic_monthly([1, 2, 3, 4, 5, 6, 7, 8, 9, 10]), common_index)
    assert signals[-1]["signal_status"] == "positive_signal_select_risky"
    assert signals[-1]["target_risky_weight"] == 1.0
    assert executions[-1]["target_bil_weight"] == 0.0


def test_negative_signal_selects_bil() -> None:
    common_index = pd.date_range("2020-10-30", periods=3, freq="B")
    signals, executions, _skips = faber.build_signal_schedule("TEST", synthetic_monthly([10, 9, 8, 7, 6, 5, 4, 3, 2, 1]), common_index)
    assert signals[-1]["signal_status"] == "negative_signal_select_bil"
    assert signals[-1]["target_risky_weight"] == 0.0
    assert executions[-1]["target_bil_weight"] == 1.0


def test_equal_signal_retains_prior_allocation_and_generates_no_trade() -> None:
    common_index = pd.date_range("2020-10-30", periods=3, freq="B")
    signals, executions, skips = faber.build_signal_schedule("TEST", synthetic_monthly([1] * 10), common_index)
    assert signals[-1]["signal_status"] == "equal_signal_retain_prior_allocation"
    assert signals[-1]["target_risky_weight"] == ""
    assert not executions
    assert skips[-1]["trade_generated"] is False


def test_missing_signal_data_retain_prior_allocation() -> None:
    common_index = pd.date_range("2020-10-30", periods=3, freq="B")
    signals, executions, skips = faber.build_signal_schedule("TEST", synthetic_monthly([1, 2, 3, None, 5, 6, 7, 8, 9, 10]), common_index)
    assert signals[-1]["signal_status"] == "invalid_signal_retain_prior_allocation"
    assert not executions
    assert skips[-1]["retained_prior_allocation"] is True


def test_no_prices_are_forward_filled_and_no_pre_inception_data_are_used() -> None:
    invariants = read_csv("accounting_timing_data_and_exposure_invariants.csv")
    assert {row["no_forward_filled_prices"] for row in invariants} == {"true"}
    assert {row["no_pre_inception_data_used"] for row in invariants} == {"true"}


def test_actual_holdings_can_drift_between_rebalances() -> None:
    dates = pd.to_datetime(["2020-01-02", "2020-01-03", "2020-01-06"])
    prices = pd.DataFrame({"A": [100.0, 110.0, 121.0], "B": [100.0, 100.0, 100.0]}, index=dates)
    events = pd.DataFrame({"A": [0.5], "B": [0.5]}, index=[dates[0]])
    path = faber.simulate_path("synthetic", prices, events, ["A", "B"], {"A": 0.5, "B": 0.5})
    assert float(path.post_trade_weights.at[dates[1], "A"]) > 0.5
    assert float(path.post_trade_weights.at[dates[2], "A"]) > float(path.post_trade_weights.at[dates[1], "A"])


def test_turnover_uses_actual_pre_trade_holdings() -> None:
    dates = pd.to_datetime(["2020-01-02", "2020-01-03", "2020-01-06"])
    prices = pd.DataFrame({"A": [100.0, 110.0, 110.0], "B": [100.0, 100.0, 100.0]}, index=dates)
    events = pd.DataFrame({"A": [0.5, 0.5], "B": [0.5, 0.5]}, index=[dates[0], dates[2]])
    path = faber.simulate_path("synthetic", prices, events, ["A", "B"], {"A": 0.5, "B": 0.5})
    pre_a = float(path.pre_trade_weights.at[dates[2], "A"])
    pre_b = float(path.pre_trade_weights.at[dates[2], "B"])
    expected = 0.5 * (abs(0.5 - pre_a) + abs(0.5 - pre_b))
    assert float(path.turnover.at[dates[2]]) == pytest.approx(expected)
    assert expected > 0.0


def test_exposure_never_exceeds_one() -> None:
    check = read_json("consistency_check.json")
    assert check["max_exposure"] <= 1.000001
    assert check["max_weight_sum"] <= 1.000001
    assert check["exposure_invariants_passed"] is True


def test_every_exact_trial_remains_in_ledger() -> None:
    ledger = read_csv("exact_configuration_trial_ledger.csv")
    assert len(ledger) == 43
    assert {row["record_retained_even_if_success_fail_error_or_excluded"] for row in ledger} == {"true"}
    assert read_json("consistency_check.json")["all_exact_trials_in_ledger"] is True


def test_spy_is_known_overlap_anchor_and_not_independent_evidence() -> None:
    spy = [row for row in read_csv("exact_configuration_trial_ledger.csv") if row["symbol"] == "SPY"][0]
    assert spy["known_overlap_anchor"] == "true"
    assert spy["counts_as_independent_family_evidence"] == "false"
    outcome = read_json("family_outcome.json")
    assert outcome["known_overlap_anchor"] == "SPY"
    assert outcome["independent_decision_instrument_count"] == 42


def test_no_parameter_alternative_or_performance_selection_is_calculated() -> None:
    assert read_json("consistency_check.json")["parameter_alternative_calculated"] is False
    assert read_json("consistency_check.json")["instrument_or_group_selected_from_performance"] is False
    assert {row["no_parameter_alternative"] for row in read_csv("frozen_signal_dates.csv")} == {"true"}


def test_no_pair_generation_or_portfolio_creation() -> None:
    check = read_json("consistency_check.json")
    assert check["pair_generation"] is False
    assert check["portfolio_created_from_tested_instruments"] is False


def test_holdout_dates_are_frozen_but_no_holdout_performance_is_generated() -> None:
    sealed = read_json("sealed_holdout_manifest.json")
    assert sealed["holdout_start"] == "2022-01-03"
    assert sealed["holdout_end"] == "2026-07-16"
    assert sealed["holdout_performance_calculated"] is False
    assert read_json("family_outcome.json")["holdout_performance_calculated"] is False
    assert read_json("consistency_check.json")["no_holdout_performance_calculated"] is True


def test_no_holdout_result_file_exists() -> None:
    names = {path.name for path in EVIDENCE.iterdir() if path.is_file()}
    assert not any(name.startswith("holdout_") for name in names)
    assert "sealed_holdout_manifest.json" in names


def test_result_tables_do_not_include_holdout_dates() -> None:
    for name in [
        "formation_instrument_results.csv",
        "validation_instrument_results.csv",
        "formation_group_summary.csv",
        "validation_group_summary.csv",
        "benchmark_relative_metrics.csv",
        "group_equal_weight_control_metrics.csv",
    ]:
        text = (EVIDENCE / name).read_text(encoding="utf-8")
        assert "2022-" not in text
        assert "2023-" not in text
        assert "2024-" not in text
        assert "2025-" not in text
        assert "2026-" not in text


def test_active_observations_and_registry_remain_unchanged() -> None:
    before = {REGISTRY: sha256(REGISTRY), ACTIVE_OBSERVATIONS: sha256(ACTIVE_OBSERVATIONS)}
    result = faber.run()
    after = {REGISTRY: sha256(REGISTRY), ACTIVE_OBSERVATIONS: sha256(ACTIVE_OBSERVATIONS)}
    assert result["consistency_passed"] is True
    assert before == after
    check = read_json("consistency_check.json")
    assert check["registry_byte_identical"] is True
    assert check["active_observations_byte_identical"] is True


def test_output_generation_is_deterministic() -> None:
    before = {path.name: sha256(path) for path in sorted(EVIDENCE.iterdir()) if path.is_file()}
    faber.run()
    after = {path.name: sha256(path) for path in sorted(EVIDENCE.iterdir()) if path.is_file()}
    assert before == after


def test_family_outcome_and_next_action_are_exact() -> None:
    outcome = read_json("family_outcome.json")
    assert outcome["primary_outcome"] in {
        "portable_positive_distribution",
        "mixed_distribution",
        "failed_distribution",
        "data_or_methodology_blocked",
    }
    assert outcome["primary_outcome"] == "mixed_distribution"
    assert outcome["next_action"] == "direction_owner_review_first_portability_batch_v1"
