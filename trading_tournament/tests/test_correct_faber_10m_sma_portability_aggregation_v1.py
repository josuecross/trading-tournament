from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from strategy_lab.research_os.universe_expansion import correct_faber_10m_sma_portability_aggregation_v1 as correction


ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = ROOT / "evidence" / "faber_10m_sma_long_bil_portability_v1" / "latest"
EVIDENCE = ROOT / "evidence" / "faber_10m_sma_long_bil_portability_correction_v1" / "latest"
REGISTRY = ROOT / "strategy_lab" / "strategy_registry.yaml"
ACTIVE_OBSERVATIONS = ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml"


@pytest.fixture(scope="module", autouse=True)
def generated_correction() -> dict[str, object]:
    return correction.run()


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


def test_required_correction_files_exist() -> None:
    for name in correction.OUTPUT_FILES:
        assert (EVIDENCE / name).exists(), name


def test_original_packet_remains_byte_identical() -> None:
    immutable = read_json(EVIDENCE / "original_packet_immutability_check.json")
    assert immutable["original_packet_byte_identical_after_correction"] is True
    assert immutable["original_packet_hashes_before"] == immutable["original_packet_hashes_after"]
    assert read_json(EVIDENCE / "consistency_check.json")["original_packet_byte_identical"] is True


def test_group_summaries_use_only_instrument_buy_and_hold() -> None:
    groups = read_csv(EVIDENCE / "corrected_validation_group_summary.csv")
    assert {row["primary_benchmark_only"] for row in groups} == {"true"}
    assert {row["bil_diagnostic_rows_excluded"] for row in groups} == {"true"}
    population = read_csv(EVIDENCE / "benchmark_population_audit.csv")
    validation = [row for row in population if row["period"] == "validation"]
    assert all(int(row["mixed_benchmark_row_count"]) == int(row["primary_benchmark_row_count"]) + int(row["bil_diagnostic_row_count"]) for row in validation)


def test_adding_or_removing_bil_diagnostic_rows_cannot_change_decisions() -> None:
    candidates, original_rel, _outcome = correction.load_original_results(ROOT)
    corrected = correction.corrected_relative_rows(candidates, original_rel)
    classes = correction.corrected_classifications(corrected)
    base_groups = correction.group_summary("validation", corrected, classes)
    base_metrics = correction.compute_family_metrics(
        [row for row in corrected if row["period"] == "validation" and row["benchmark"] == correction.PRIMARY_BENCHMARK],
        base_groups,
        classes,
        True,
    )
    no_bil = [row for row in corrected if row["benchmark"] != correction.CASH_BENCHMARK]
    double_bil = corrected + [dict(row) for row in corrected if row["benchmark"] == correction.CASH_BENCHMARK]
    for altered in (no_bil, double_bil):
        altered_groups = correction.group_summary("validation", altered, classes)
        altered_metrics = correction.compute_family_metrics(
            [row for row in altered if row["period"] == "validation" and row["benchmark"] == correction.PRIMARY_BENCHMARK],
            altered_groups,
            classes,
            True,
        )
        assert altered_groups == base_groups
        assert altered_metrics == base_metrics


def test_spy_excluded_only_from_independent_decision_aggregates() -> None:
    classes = read_csv(EVIDENCE / "corrected_instrument_classifications.csv")
    spy = [row for row in classes if row["symbol"] == "SPY"][0]
    assert spy["known_overlap_anchor"] == "true"
    assert spy["counts_as_independent_family_evidence"] == "false"
    broad = [row for row in read_csv(EVIDENCE / "corrected_validation_group_summary.csv") if row["economic_group"] == "us_broad_size_style_factors"][0]
    assert int(broad["recorded_instrument_count"]) == 8
    assert int(broad["independent_decision_instrument_count"]) == 7


def test_all_other_42_independent_trials_remain_present() -> None:
    classes = read_csv(EVIDENCE / "corrected_instrument_classifications.csv")
    independent = [row for row in classes if row["counts_as_independent_family_evidence"] == "true"]
    assert len(classes) == 43
    assert len(independent) == 42
    assert {row["symbol"] for row in independent} == {row["symbol"] for row in classes} - {"SPY"}


def test_canonical_drawdown_improvement_sign_semantics() -> None:
    assert correction.canonical_drawdown_improvement(-0.10, -0.30) == pytest.approx(0.20)
    assert correction.canonical_drawdown_improvement(-0.30, -0.30) == pytest.approx(0.0)
    assert correction.canonical_drawdown_improvement(-0.40, -0.20) == pytest.approx(-0.20)


def test_smaller_drawdown_cannot_receive_negative_improvement() -> None:
    rows = read_csv(EVIDENCE / "corrected_benchmark_relative_metrics.csv")
    for row in rows:
        candidate = to_float(row["candidate_maximum_drawdown"])
        benchmark = to_float(row["reconstructed_benchmark_maximum_drawdown"])
        improvement = to_float(row["canonical_drawdown_improvement"])
        if abs(candidate) < abs(benchmark):
            assert improvement > 0.0


def test_worse_drawdown_cannot_receive_positive_improvement() -> None:
    rows = read_csv(EVIDENCE / "corrected_benchmark_relative_metrics.csv")
    for row in rows:
        candidate = to_float(row["candidate_maximum_drawdown"])
        benchmark = to_float(row["reconstructed_benchmark_maximum_drawdown"])
        improvement = to_float(row["canonical_drawdown_improvement"])
        if abs(candidate) > abs(benchmark):
            assert improvement < 0.0


def test_group_medians_equal_direct_primary_benchmark_medians() -> None:
    rows = read_csv(EVIDENCE / "corrected_benchmark_relative_metrics.csv")
    group_rows = read_csv(EVIDENCE / "corrected_validation_group_summary.csv")
    for group in group_rows:
        values = [
            to_float(row["excess_total_return"])
            for row in rows
            if row["period"] == "validation"
            and row["benchmark"] == correction.PRIMARY_BENCHMARK
            and row["economic_group"] == group["economic_group"]
            and row["symbol"] != "SPY"
        ]
        dd_values = [
            to_float(row["canonical_drawdown_improvement"])
            for row in rows
            if row["period"] == "validation"
            and row["benchmark"] == correction.PRIMARY_BENCHMARK
            and row["economic_group"] == group["economic_group"]
            and row["symbol"] != "SPY"
        ]
        assert to_float(group["median_excess_total_return"]) == pytest.approx(float(np.median(values)))
        assert to_float(group["median_canonical_drawdown_improvement"]) == pytest.approx(float(np.median(dd_values)))


def test_family_medians_equal_direct_42_independent_primary_rows() -> None:
    rows = read_csv(EVIDENCE / "corrected_benchmark_relative_metrics.csv")
    independent = [
        row for row in rows
        if row["period"] == "validation" and row["benchmark"] == correction.PRIMARY_BENCHMARK and row["symbol"] != "SPY"
    ]
    metrics = read_json(EVIDENCE / "corrected_family_metrics.json")
    assert len(independent) == 42
    assert metrics["overall_median_validation_excess_total_return"] == pytest.approx(float(np.median([to_float(row["excess_total_return"]) for row in independent])))
    assert metrics["overall_median_validation_canonical_drawdown_improvement"] == pytest.approx(float(np.median([to_float(row["canonical_drawdown_improvement"]) for row in independent])))


def test_instrument_classifications_use_canonical_sign() -> None:
    rows = read_csv(EVIDENCE / "corrected_instrument_classifications.csv")
    for row in rows:
        excess = to_float(row["excess_total_return"])
        improvement = to_float(row["canonical_drawdown_improvement"])
        ratio = to_float(row["return_to_drawdown_ratio_difference"])
        label = row["validation_classification"]
        if label == "return_and_drawdown_improved":
            assert excess > 0.0 and improvement > 0.0 and ratio > 0.0
        elif label == "return_improved_only":
            assert excess > 0.0 and improvement <= 0.0
        elif label == "drawdown_improved_only":
            assert excess <= 0.0 and improvement >= 0.05 and ratio > 0.0
        elif label == "no_instrument_edge":
            assert not (excess > 0.0 and improvement > 0.0 and ratio > 0.0)
        else:
            assert label == "instrument_methodology_blocked"


def test_group_pass_counts_are_recomputed_from_corrected_values() -> None:
    groups = read_csv(EVIDENCE / "corrected_validation_group_summary.csv")
    metrics = read_json(EVIDENCE / "corrected_family_metrics.json")
    assert metrics["groups_passed_validation"] == sum(row["group_validation_passed"] == "true" for row in groups)
    assert metrics["groups_passed_validation"] == 0


def test_family_outcome_recomputed_not_copied() -> None:
    check = read_json(EVIDENCE / "consistency_check.json")
    analysis = read_json(EVIDENCE / "outcome_change_analysis.json")
    defect_rows = [
        row for row in read_csv(EVIDENCE / "defect_reproduction.csv")
        if row["defect"] == "mixed_benchmark_population"
    ]
    assert check["family_outcome_recomputed_not_copied"] is True
    assert analysis["original_primary_outcome"] == "mixed_distribution"
    assert analysis["original_groups_passed_validation"] == 4
    assert analysis["corrected_groups_passed_validation"] == 0
    assert sum(row["original_group_validation_passed"] == "true" for row in defect_rows) == 4
    assert {row["corrected_group_validation_passed"] for row in defect_rows} == {"false"}
    assert any(
        to_float(row["corrected_primary_only_validation_median_excess"])
        != pytest.approx(to_float(row["original_reported_validation_median_excess"]))
        for row in defect_rows
    )


def test_signals_trades_costs_and_exposures_match_original() -> None:
    rows = read_csv(EVIDENCE / "accounting_signal_trade_and_cost_match.csv")
    assert rows
    assert {row["matches_original"] for row in rows} == {"true"}
    assert read_json(EVIDENCE / "consistency_check.json")["signals_trades_costs_and_exposures_match_original"] is True


def test_no_holdout_price_signal_or_result_is_loaded() -> None:
    holdout = read_json(EVIDENCE / "holdout_seal_verification.json")
    assert holdout["holdout_price_signal_or_result_loaded"] is False
    assert holdout["holdout_performance_calculated"] is False
    assert holdout["sealed_holdout_manifest_unchanged"] is True


def test_no_holdout_result_file_is_created() -> None:
    names = {path.name for path in EVIDENCE.iterdir() if path.is_file()}
    assert "holdout_seal_verification.json" in names
    assert not any(name.startswith("holdout_") and name != "holdout_seal_verification.json" for name in names)
    assert read_json(EVIDENCE / "consistency_check.json")["holdout_result_file_created"] is False


def test_no_instrument_group_or_parameter_is_selected() -> None:
    check = read_json(EVIDENCE / "consistency_check.json")
    outcome = read_json(EVIDENCE / "corrected_family_outcome.json")
    assert check["winning_group_selected"] is False
    assert check["winning_ticker_selected"] is False
    assert check["parameter_selected_or_changed"] is False
    assert outcome["winning_group_selected"] is False
    assert outcome["winning_ticker_selected"] is False


def test_active_observations_and_registry_remain_unchanged() -> None:
    before = {REGISTRY: sha256(REGISTRY), ACTIVE_OBSERVATIONS: sha256(ACTIVE_OBSERVATIONS)}
    result = correction.run()
    after = {REGISTRY: sha256(REGISTRY), ACTIVE_OBSERVATIONS: sha256(ACTIVE_OBSERVATIONS)}
    assert result["consistency_passed"] is True
    assert before == after
    check = read_json(EVIDENCE / "consistency_check.json")
    assert check["registry_byte_identical"] is True
    assert check["active_observations_byte_identical"] is True


def test_output_generation_is_deterministic() -> None:
    before = {path.name: sha256(path) for path in sorted(EVIDENCE.iterdir()) if path.is_file()}
    correction.run()
    after = {path.name: sha256(path) for path in sorted(EVIDENCE.iterdir()) if path.is_file()}
    assert before == after


def test_corrected_outcome_and_next_action() -> None:
    outcome = read_json(EVIDENCE / "corrected_family_outcome.json")
    assert outcome["corrected_primary_outcome"] == "mixed_distribution"
    assert outcome["next_action"] == "direction_owner_review_corrected_mixed_portability_distribution"
