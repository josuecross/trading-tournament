from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from strategy_lab.research_os.universe_expansion import faber_10m_sma_long_bil_portability_holdout_v1 as holdout


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "faber_10m_sma_long_bil_portability_holdout_v1" / "latest"
ORIGINAL = ROOT / "evidence" / "faber_10m_sma_long_bil_portability_v1" / "latest"
CORRECTION = ROOT / "evidence" / "faber_10m_sma_long_bil_portability_correction_v1" / "latest"
REGISTRY = ROOT / "strategy_lab" / "strategy_registry.yaml"
ACTIVE_OBSERVATIONS = ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml"


@pytest.fixture(scope="module", autouse=True)
def generated_holdout() -> dict[str, object]:
    return holdout.run()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def to_float(value: str) -> float:
    return float(value)


def test_required_holdout_files_exist() -> None:
    for name in holdout.OUTPUT_FILES:
        assert (EVIDENCE / name).exists(), name


def test_all_earlier_packets_remain_byte_identical() -> None:
    hashes = read_json(EVIDENCE / "formation_validation_packet_hashes.json")
    assert hashes["original_packet_byte_identical_after_holdout"] is True
    assert hashes["correction_packet_byte_identical_after_holdout"] is True
    assert hashes["all_earlier_packets_byte_identical_after_holdout"] is True
    assert hashes["original_packet_hashes_before"] == hashes["original_packet_hashes_after"]
    assert hashes["correction_packet_hashes_before"] == hashes["correction_packet_hashes_after"]
    assert read_json(EVIDENCE / "consistency_check.json")["all_earlier_packets_byte_identical"] is True


def test_holdout_dates_are_exactly_frozen() -> None:
    dates = read_json(EVIDENCE / "frozen_holdout_dates.json")
    assert dates["holdout_start"] == "2022-01-03"
    assert dates["holdout_end"] == "2026-07-16"
    assert dates["endpoint_extended"] is False
    assert dates["data_refreshed"] is False
    rows = read_csv(EVIDENCE / "holdout_instrument_results.csv")
    assert {row["initial_date"] for row in rows} == {"2022-01-03"}
    assert {row["final_date"] for row in rows} == {"2026-07-16"}


def test_no_non_holdout_dates_are_used_for_holdout_metrics() -> None:
    rows = read_csv(EVIDENCE / "holdout_instrument_results.csv")
    rel = read_csv(EVIDENCE / "holdout_benchmark_relative_metrics.csv")
    assert {row["period"] for row in rows} == {"holdout"}
    assert {row["period"] for row in rel} == {"holdout"}
    assert read_json(EVIDENCE / "frozen_holdout_dates.json")["holdout_metrics_window_only"] is True


def test_source_rule_and_ten_month_parameter_are_unchanged() -> None:
    lineage = read_json(EVIDENCE / "authoritative_lineage.json")
    check = read_json(EVIDENCE / "consistency_check.json")
    assert lineage["source_rule_changed"] is False
    assert lineage["ten_month_parameter_changed"] is False
    assert check["source_parameter_months"] == 10
    assert check["source_rule_changed"] is False
    assert check["ten_month_parameter_changed"] is False


def test_all_43_trials_remain_present() -> None:
    ledger = read_csv(EVIDENCE / "exact_configuration_trial_ledger_update.csv")
    results = read_csv(EVIDENCE / "holdout_instrument_results.csv")
    assert len(ledger) == 43
    assert len(results) == 43
    assert [row["symbol"] for row in ledger] == list(holdout.faber.RISKY_INSTRUMENTS)
    assert {row["record_retained_even_if_success_fail_error_or_excluded"] for row in ledger} == {"true"}


def test_spy_anchor_excluded_only_from_independent_aggregates() -> None:
    classes = read_csv(EVIDENCE / "holdout_instrument_classifications.csv")
    spy = [row for row in classes if row["symbol"] == "SPY"][0]
    assert spy["known_overlap_anchor"] == "true"
    assert spy["counts_as_independent_family_evidence"] == "false"
    assert len([row for row in classes if row["counts_as_independent_family_evidence"] == "true"]) == 42
    broad = [row for row in read_csv(EVIDENCE / "holdout_group_summary.csv") if row["economic_group"] == "us_broad_size_style_factors"][0]
    assert int(broad["recorded_instrument_count"]) == 8
    assert int(broad["independent_instrument_count"]) == 7


def test_bil_diagnostic_rows_cannot_alter_group_or_family_outcomes() -> None:
    rel = read_csv(EVIDENCE / "holdout_benchmark_relative_metrics.csv")
    family = read_json(EVIDENCE / "family_holdout_metrics.json")
    primary = [
        row for row in rel
        if row["benchmark"] == holdout.PRIMARY_BENCHMARK and row["symbol"] != "SPY"
    ]
    no_bil = [row for row in rel if row["benchmark"] != holdout.CASH_BENCHMARK and row["symbol"] != "SPY"]
    doubled = primary + [row for row in rel if row["benchmark"] == holdout.CASH_BENCHMARK] * 2
    assert len(primary) == 42
    assert no_bil == primary
    assert family["median_holdout_excess_total_return"] == pytest.approx(float(np.median([to_float(row["excess_total_return"]) for row in primary])))
    assert family["median_holdout_canonical_drawdown_improvement"] == pytest.approx(float(np.median([to_float(row["canonical_drawdown_improvement"]) for row in primary])))
    assert float(np.median([to_float(row["excess_total_return"]) for row in doubled if row["benchmark"] == holdout.PRIMARY_BENCHMARK and row["symbol"] != "SPY"])) == pytest.approx(family["median_holdout_excess_total_return"])


def test_canonical_drawdown_semantics_are_positive_is_better() -> None:
    rows = read_csv(EVIDENCE / "holdout_benchmark_relative_metrics.csv")
    for row in rows:
        candidate = to_float(row["candidate_maximum_drawdown"])
        benchmark = to_float(row["benchmark_maximum_drawdown"])
        improvement = to_float(row["canonical_drawdown_improvement"])
        assert improvement == pytest.approx(abs(benchmark) - abs(candidate))
        if abs(candidate) < abs(benchmark):
            assert improvement > 0.0
        if abs(candidate) > abs(benchmark):
            assert improvement < 0.0


def test_no_instrument_or_group_removed_from_results() -> None:
    groups = read_csv(EVIDENCE / "holdout_group_summary.csv")
    assert [row["economic_group"] for row in groups] == list(holdout.correction.GROUPS)
    assert sum(int(row["recorded_instrument_count"]) for row in groups) == 43
    assert read_json(EVIDENCE / "consistency_check.json")["no_instrument_or_group_removed"] is True


def test_no_parameter_or_wrapper_alternative_is_calculated() -> None:
    check = read_json(EVIDENCE / "consistency_check.json")
    invariants = read_csv(EVIDENCE / "accounting_timing_data_and_exposure_invariants.csv")
    assert check["no_parameter_or_wrapper_alternative_calculated"] is True
    assert {row["no_parameter_or_wrapper_alternative_calculated"] for row in invariants} == {"true"}


def test_group_medians_use_only_primary_benchmark_rows() -> None:
    rel = read_csv(EVIDENCE / "holdout_benchmark_relative_metrics.csv")
    groups = read_csv(EVIDENCE / "holdout_group_summary.csv")
    for group in groups:
        rows = [
            row for row in rel
            if row["benchmark"] == holdout.PRIMARY_BENCHMARK
            and row["economic_group"] == group["economic_group"]
            and row["symbol"] != "SPY"
        ]
        assert group["primary_benchmark_only"] == "true"
        assert group["bil_diagnostic_rows_excluded"] == "true"
        assert to_float(group["median_excess_total_return"]) == pytest.approx(float(np.median([to_float(row["excess_total_return"]) for row in rows])))
        assert to_float(group["median_canonical_drawdown_improvement"]) == pytest.approx(float(np.median([to_float(row["canonical_drawdown_improvement"]) for row in rows])))


def test_validation_and_holdout_metrics_remain_separately_reported() -> None:
    assert (CORRECTION / "corrected_validation_group_summary.csv").exists()
    assert (EVIDENCE / "validation_holdout_stability.csv").exists()
    check = read_json(EVIDENCE / "consistency_check.json")
    assert check["validation_and_holdout_metrics_separately_reported"] is True
    assert not any(path.name.startswith("combined_") for path in EVIDENCE.iterdir() if path.is_file())


def test_no_winning_ticker_or_group_selected() -> None:
    check = read_json(EVIDENCE / "consistency_check.json")
    outcome = read_json(EVIDENCE / "family_holdout_outcome.json")
    assert check["winning_ticker_selected"] is False
    assert check["winning_group_selected"] is False
    assert outcome["winning_ticker_selected"] is False
    assert outcome["winning_group_selected"] is False


def test_exposure_never_exceeds_one() -> None:
    check = read_json(EVIDENCE / "consistency_check.json")
    rows = read_csv(EVIDENCE / "accounting_timing_data_and_exposure_invariants.csv")
    assert check["max_exposure"] <= 1.000001
    assert check["max_weight_sum"] <= 1.000001
    assert check["exposure_invariants_passed"] is True
    assert all(to_float(row["max_exposure"]) <= 1.000001 for row in rows)
    assert all(to_float(row["max_weight_sum"]) <= 1.000001 for row in rows)


def test_active_observations_and_registry_remain_unchanged() -> None:
    before = {REGISTRY: sha256(REGISTRY), ACTIVE_OBSERVATIONS: sha256(ACTIVE_OBSERVATIONS)}
    result = holdout.run()
    after = {REGISTRY: sha256(REGISTRY), ACTIVE_OBSERVATIONS: sha256(ACTIVE_OBSERVATIONS)}
    assert result["consistency_passed"] is True
    assert before == after
    check = read_json(EVIDENCE / "consistency_check.json")
    assert check["registry_byte_identical"] is True
    assert check["active_observations_byte_identical"] is True


def test_no_paper_demo_or_broker_order_is_created() -> None:
    check = read_json(EVIDENCE / "consistency_check.json")
    manifest = read_json(EVIDENCE / "holdout_manifest.json")
    assert check["paper_demo_observation_created"] is False
    assert check["broker_order_created"] is False
    assert manifest["paper_demo_observation_created"] is False
    assert manifest["broker_order_created"] is False
    assert manifest["real_money_recommendation"] is False


def test_output_generation_is_deterministic() -> None:
    before = {path.name: sha256(path) for path in sorted(EVIDENCE.iterdir()) if path.is_file()}
    holdout.run()
    after = {path.name: sha256(path) for path in sorted(EVIDENCE.iterdir()) if path.is_file()}
    assert before == after


def test_holdout_outcome_and_next_action_are_exact() -> None:
    metrics = read_json(EVIDENCE / "family_holdout_metrics.json")
    outcome = read_json(EVIDENCE / "family_holdout_outcome.json")
    assert metrics["holdout_outcome"] == "holdout_does_not_confirm_portability"
    assert outcome["holdout_outcome"] == "holdout_does_not_confirm_portability"
    assert outcome["next_action"] == "direction_owner_select_second_portability_family"
    assert metrics["median_holdout_excess_total_return"] == pytest.approx(-0.11363022678419155)
    assert metrics["median_holdout_canonical_drawdown_improvement"] == pytest.approx(0.08280789771783026)
    assert metrics["return_to_drawdown_ratio_improved_count"] == 22
    assert metrics["defensive_groups_confirmed"] == 1
