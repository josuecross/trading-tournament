from __future__ import annotations

import csv
import json
from decimal import Decimal

import pytest

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.research import acquire_validate_freeze_phase2_public_signal_inputs_v1 as subject


DATA = subject.DATA_DIR
EVIDENCE = subject.OUTPUT_DIR


def rows(path):
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


@pytest.fixture(scope="module", autouse=True)
def completed_run():
    result = subject.run()
    assert result["overall_pass"] is True
    return result


def test_modern_and_legacy_bls_release_parsers() -> None:
    modern = b"""<html><head><title>CPI test</title></head><body>embargoed until 8:30 a.m. (ET)
    <table><caption>Table 1. Consumer Price Index</caption><tr><th>All items</th>
    <td>100.000</td><td>299.170</td><td>306.746</td><td>308.417</td><td>3.1</td></tr></table></body></html>"""
    parsed = subject.parse_release_payload(
        reference_month="2024-01", release_url="https://www.bls.gov/cpi_02132024.htm",
        release_date="2024-02-13", content=modern, content_type="text/html"
    )
    assert parsed["cpi_all_items_nsa_level_as_published"] == "308.417"
    assert parsed["cpi_yoy_percent_as_published"] == "3.1"
    assert parsed["prior_year_level_in_same_release"] == "299.170"
    assert parsed["release_time_et"] == "08:30:00 America/New_York"

    legacy = b"""CONSUMER PRICE INDEX\nUNTIL 8:30 A.M. (EDT)\nTable 1. CPI-U\n
 All items....................................    100.000     202.9     203.5      4.1      0.3\n"""
    parsed = subject.parse_release_payload(
        reference_month="2006-07", release_url="https://www.bls.gov/cpi_08162006.txt",
        release_date="2006-08-16", content=legacy, content_type="text/plain"
    )
    assert parsed["cpi_all_items_nsa_level_as_published"] == "203.5"
    assert parsed["cpi_yoy_percent_as_published"] == "4.1"


def test_required_data_and_evidence_files_exist() -> None:
    assert subject.REQUIRED_DATA_FILES <= {path.name for path in DATA.iterdir() if path.is_file()}
    assert subject.REQUIRED_EVIDENCE_FILES == {path.name for path in EVIDENCE.iterdir() if path.is_file()}


def test_canonical_records_are_unique_ordered_and_positive() -> None:
    signal = rows(DATA / "cpi_point_in_time_signal.csv")
    months = [row["reference_month"] for row in signal]
    releases = [row["bls_release_date"] for row in signal]
    assert months == sorted(months)
    assert len(months) == len(set(months))
    assert releases == sorted(releases)
    assert len(releases) == len(set(releases))
    assert all(Decimal(row["cpi_all_items_nsa_level_as_published"]) > 0 for row in signal)
    assert all(Decimal(row["computed_yoy_from_same_vintage"]).is_finite() for row in signal)


def test_no_lookahead_and_business_date_contract() -> None:
    signal = rows(DATA / "cpi_point_in_time_signal.csv")
    assert all(row["signal_available_timestamp"].startswith(row["bls_release_date"]) for row in signal)
    assert all(row["source_effective_after_close_date"] > row["bls_release_date"] for row in signal)
    assert all(row["next_business_day_after_release"] == row["source_effective_after_close_date"] for row in signal)
    assert all(row["forward_fill_used"] == "false" for row in signal)
    assert all(row["interpolation_used"] == "false" for row in signal)
    assert all(row["current_revised_history_used"] == "false" for row in signal)


def test_officially_unpublished_month_is_visible_not_filled() -> None:
    reconciliation = rows(DATA / "release_reconciliation.csv")
    missing = [row for row in reconciliation if row["release_status"] == "officially_not_published"]
    readiness = json.loads((EVIDENCE / "signal_readiness.json").read_text(encoding="utf-8"))
    assert len(missing) == readiness["missing_reference_month_count"]
    assert all(row["reference_month"] not in {item["reference_month"] for item in rows(DATA / "cpi_point_in_time_signal.csv")} for row in missing)


def test_published_and_computed_yoy_are_disclosed_without_favorable_choice() -> None:
    signal = rows(DATA / "cpi_point_in_time_signal.csv")
    allowed = {"exact_reconciliation", "rounding_only_difference", "unresolved_difference"}
    assert {row["source_reconciliation_status"] for row in signal} <= allowed
    assert all(row["cpi_yoy_percent_as_published"] for row in signal)
    assert all(row["computed_yoy_from_same_vintage"] for row in signal)
    boundary = rows(EVIDENCE / "threshold_boundary_audit.csv")
    assert all(row["audit_status"] in {"audited_no_regime_change", "threshold_rounding_requires_source_decision"} for row in boundary)


def test_regimes_follow_frozen_thresholds() -> None:
    signal = rows(DATA / "cpi_point_in_time_signal.csv")
    assert all(row["signal_regime"] == subject.regime(Decimal(row["cpi_yoy_percent_as_published"])) for row in signal)


def test_warmup_ambiguity_is_not_silently_resolved() -> None:
    readiness = json.loads((EVIDENCE / "signal_readiness.json").read_text(encoding="utf-8"))
    assert readiness["warmup_contract_status"] == "warmup_rule_requires_source_reconciliation"
    assert readiness["first_valid_volwt_formation"]
    assert readiness["first_valid_proib_formation"] == "unresolved"
    assert readiness["global_first_source_compliant_formation"] == "unresolved"
    assert len(readiness["proib_candidate_dates"]) == 2


def test_freeze_hash_and_raw_regeneration_are_deterministic(completed_run) -> None:
    first = completed_run
    second = subject.run()
    assert second["frozen_dataset_hash"] == first["frozen_dataset_hash"]
    assert second["deterministic_evidence_packet_hash"] == first["deterministic_evidence_packet_hash"]
    freeze = json.loads((DATA / "freeze_manifest.json").read_text(encoding="utf-8"))
    assert freeze["deterministic_from_preserved_raw_inputs"] is True


def test_no_strategy_trial_performance_or_external_trading_action() -> None:
    consistency = json.loads((EVIDENCE / "consistency_check.json").read_text(encoding="utf-8"))
    counts = consistency["entity_counts"]
    assert counts["strategy_configurations_created"] == 0
    assert counts["experiment_trials_created"] == 0
    assert counts["backtests_run"] == 0
    assert counts["performance_metrics_calculated"] == 0
    assert counts["forward_observations_accessed_or_changed"] == 0
    assert counts["alpaca_or_broker_calls"] == 0
    assert consistency["checks"]["protected_state_unchanged"] is True
    assert all(consistency["checks"].values())
