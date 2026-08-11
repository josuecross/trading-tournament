from __future__ import annotations

import csv
import json
from decimal import Decimal

import pytest

from strategy_lab.research_os.research import resolve_refreeze_spdj_dynamic_inflation_signal_contract_v2 as subject


def rows(path):
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


@pytest.fixture(scope="module", autouse=True)
def completed_run():
    result = subject.run()
    assert result["overall_pass"] is True
    return result


def test_v1_parent_is_preserved_byte_for_byte() -> None:
    consistency = json.loads((subject.OUTPUT_DIR / "consistency_check.json").read_text(encoding="utf-8"))
    assert consistency["parent_dataset_hash"] == subject.V1_EXPECTED_FROZEN_HASH
    assert consistency["parent_tree_hash_before"] == consistency["parent_tree_hash_after"]
    assert consistency["checks"]["V1_core_and_raw_hashes_match"] is True


def test_v2_schema_and_months_are_complete() -> None:
    signal = rows(subject.V2_DIR / "cpi_point_in_time_signal.csv")
    assert set(subject.SIGNAL_FIELDS) == set(signal[0])
    assert [row["reference_month"] for row in signal] == subject.month_range("2005-07", "2026-06")
    assert len(signal) == len({row["reference_month"] for row in signal})


def test_unrounded_yoy_is_recomputed_without_threshold_rounding() -> None:
    for row in rows(subject.V2_DIR / "cpi_point_in_time_signal.csv"):
        if row["rebalance_event"] != "true":
            continue
        current = Decimal(row["cpi_all_items_nsa_level_as_published"])
        prior = Decimal(row["prior_year_cpi_level"])
        recomputed = Decimal("100") * (current / prior - Decimal("1"))
        assert row["canonical_cpi_yoy_unrounded"] == subject.decimal_text(recomputed)
        assert row["canonical_regime"] == subject.regime(recomputed)


def test_all_seven_disagreements_recompute_to_expected_regimes() -> None:
    threshold = rows(subject.OUTPUT_DIR / "threshold_resolution.csv")
    assert len(threshold) == 7
    assert {row["reference_month"]: row["v2_canonical_unrounded_regime"] for row in threshold} == subject.EXPECTED_THRESHOLD_REGIMES
    assert all(row["recomputation_matches_expected"] == "true" for row in threshold)
    assert all(row["threshold_blocker_remaining"] == "false" for row in threshold)


def test_warmup_uses_36_underlying_returns_and_25_beta_pairs() -> None:
    warmup = json.loads((subject.V2_DIR / "warmup_contract.json").read_text(encoding="utf-8"))
    assert warmup["interpretation"] == subject.WARMUP_INTERPRETATION
    assert warmup["minimum_underlying_monthly_returns"] == 36
    assert warmup["first_valid_proib_regression_pair_count"] == 25
    assert warmup["expected_pair_count_from_36_month_window"] == 25
    assert len(warmup["first_valid_proib_pair_months"]) == 25


def test_volwt_proib_and_global_dates_are_mechanical() -> None:
    readiness = json.loads((subject.OUTPUT_DIR / "signal_readiness_v2.json").read_text(encoding="utf-8"))
    assert readiness["first_valid_volwt_formation"] == "2009-08-17"
    assert readiness["first_valid_proib_formation"] == "2009-08-17"
    assert readiness["global_first_source_compliant_formation"] == "2009-08-17"


def test_first_proib_pairs_have_no_lookahead_or_extra_prehistory() -> None:
    warmup = json.loads((subject.V2_DIR / "warmup_contract.json").read_text(encoding="utf-8"))
    assert warmup["first_valid_proib_pair_months"][0] == "2007-07"
    assert warmup["first_valid_proib_pair_months"][-1] == "2009-07"
    assert warmup["all_proib_pairs_point_in_time_available"] is True
    assert warmup["price_history_extended_before_permitted_window"] is False


def test_october_2025_is_explicit_no_release_no_imputation_event() -> None:
    signal = {row["reference_month"]: row for row in rows(subject.V2_DIR / "cpi_point_in_time_signal.csv")}
    october = signal["2025-10"]
    assert october["publication_status"] == "canceled_no_official_CPI_release"
    assert october["cpi_all_items_nsa_level_as_published"] == ""
    assert october["canonical_cpi_yoy_unrounded"] == ""
    assert october["canonical_regime"] == ""
    assert october["rebalance_event"] == "false"
    assert october["allocation_persistence_rule"] == subject.MISSING_RELEASE_RULE
    assert october["forward_fill_used"] == "false"
    assert october["interpolation_used"] == "false"
    assert october["imputation_used"] == "false"
    assert signal["2025-11"]["rebalance_event"] == "true"


def test_diff_is_limited_to_seven_regimes_and_one_missing_event() -> None:
    diff = rows(subject.OUTPUT_DIR / "v1_v2_signal_diff.csv")
    assert len(diff) == 8
    assert {row["reference_month"] for row in diff} == set(subject.EXPECTED_THRESHOLD_REGIMES) | {"2025-10"}
    assert all(row["cpi_level_changed"] == "false" for row in diff)
    assert all(row["prior_year_level_changed"] == "false" for row in diff)


def test_deterministic_regeneration_and_no_research_execution(completed_run) -> None:
    second = subject.run()
    assert second["V2_dataset_hash"] == completed_run["V2_dataset_hash"]
    assert second["deterministic_evidence_packet_hash"] == completed_run["deterministic_evidence_packet_hash"]
    consistency = json.loads((subject.OUTPUT_DIR / "consistency_check.json").read_text(encoding="utf-8"))
    assert consistency["overall_pass"] is True
    assert consistency["entity_counts"] == {
        "public_signal_datasets_created": 1,
        "strategy_configurations_created": 0,
        "experiment_trials_created": 0,
        "backtests_run": 0,
        "performance_metrics_calculated": 0,
        "forward_observations_accessed_or_changed": 0,
        "broker_or_account_calls": 0,
    }
    assert all(consistency["checks"].values())
