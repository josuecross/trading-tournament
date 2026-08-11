from __future__ import annotations

import csv
import json

import pytest

from strategy_lab.research_os.research import export_spdj_dynamic_inflation_forward_observation_handoff_v1 as subject


@pytest.fixture(scope="module", autouse=True)
def completed_run():
    result = subject.run()
    assert result["overall_pass"] is True
    return result


def payload(path):
    return json.loads(path.read_text(encoding="utf-8"))


def csv_rows(path):
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_exact_eligibility_domain_status_reconciles() -> None:
    manifest = payload(subject.PACKAGE_DIR / "handoff_manifest.json")
    consistency = payload(subject.OUTPUT_DIR / "consistency_check.json")
    assert manifest["research_eligibility_status"] == subject.ELIGIBILITY_STATUS
    assert manifest["research_eligibility_status"] != "completed"
    assert consistency["checks"]["eligibility_packet_hash_reconciles"] is True


def test_strategy_identity_and_trial_lineage_are_frozen() -> None:
    contract = payload(subject.PACKAGE_DIR / "strategy_contract.json")
    lineage = payload(subject.PACKAGE_DIR / "lineage_manifest.json")
    assert contract["strategy_id"] == subject.STRATEGY_ID
    assert contract["canonical_trial_id"] == subject.CANONICAL_TRIAL_ID
    assert contract["robustness_trial_id"] == subject.ROBUSTNESS_TRIAL_ID
    assert lineage["canonical_trial_count"] == 1
    assert lineage["robustness_trial_count"] == 1
    assert lineage["strategy_variant_count"] == 0


def test_exact_six_symbol_mapping_is_preserved() -> None:
    rows = csv_rows(subject.PACKAGE_DIR / "instrument_mapping.csv")
    mapping = {row["symbol"]: row for row in rows}
    assert set(mapping) == set(subject.SYMBOLS)
    assert mapping["GSG"]["mapping_classification"] == "exact_match"
    assert all(mapping[symbol]["mapping_classification"] == "economically_close_source_preserving_proxy" for symbol in set(subject.SYMBOLS) - {"GSG"})
    assert {row["silent_substitution_allowed"] for row in rows} == {"false"}


def test_signal_threshold_and_no_release_contract_are_exact() -> None:
    signal = payload(subject.PACKAGE_DIR / "signal_contract.json")
    assert signal["canonical_signal"] == "cpi_yoy_unrounded_from_point_in_time_CPIAUCNS_levels"
    assert signal["formula"] == "100 * (CPI_t / CPI_t_minus_12 - 1)"
    assert signal["regimes"] == {"low": "CPI_YoY < 1.5", "medium": "1.5 <= CPI_YoY <= 2.5", "high": "CPI_YoY > 2.5"}
    assert signal["no_release_behavior"]["state"] == "no_release_no_event"
    assert signal["no_release_behavior"]["rebalance_event"] is False


def test_weight_algorithms_and_tolerances_are_frozen() -> None:
    contract = payload(subject.PACKAGE_DIR / "strategy_contract.json")
    fixtures = payload(subject.PACKAGE_DIR / "golden_fixture_manifest.json")
    assert contract["target_algorithms"]["low"]["SPY"] == 0.6
    assert contract["target_algorithms"]["low"]["AGG"] == 0.4
    assert contract["target_algorithms"]["medium"]["volatility"] == "sample standard deviation using ddof=1"
    assert contract["target_algorithms"]["high"]["first_36_month_window_complete_pair_count"] == 25
    assert fixtures["weight_absolute_tolerance"] == subject.WEIGHT_TOLERANCE
    assert fixtures["formula_absolute_tolerance"] == subject.FORMULA_TOLERANCE


def test_golden_fixtures_cover_every_required_case() -> None:
    manifest = payload(subject.PACKAGE_DIR / "golden_fixture_manifest.json")
    rows = csv_rows(subject.PACKAGE_DIR / "golden_conformance_fixtures.csv")
    assert manifest["fixture_count"] == len(rows) == 15
    assert manifest["coverage"]["all_three_regimes_represented"] is True
    assert manifest["coverage"]["low_regime_count"] >= 2
    assert manifest["coverage"]["medium_regime_count"] >= 2
    assert manifest["coverage"]["high_regime_count"] >= 2
    assert manifest["coverage"]["all_seven_threshold_disagreements_represented"] is True
    assert manifest["coverage"]["October_2025_no_event_represented"] is True
    assert manifest["coverage"]["post_120_month_event_represented"] is True
    assert manifest["coverage"]["regime_transition_represented"] is True


def test_no_release_fixture_does_not_fabricate_target() -> None:
    row = next(item for item in csv_rows(subject.PACKAGE_DIR / "golden_conformance_fixtures.csv") if item["reference_month"] == "2025-10")
    assert row["event_status"] == "no_release_no_event"
    assert row["persist_previous_target"] == "true"
    assert row["expected_target_SPY"] == ""
    assert row["values_absent_reason"] == "no_target_materialized_for_no_release_event"


def test_reference_code_and_CPI_assets_are_immutable_copies() -> None:
    snapshot = subject.REFERENCE_DIR / subject.CANONICAL_CODE.name
    assert subject.sha256_file(snapshot) == subject.EXPECTED_CODE_HASH
    for name in ("cpi_point_in_time_signal.csv", "data_dictionary.json", "source_manifest.json", "warmup_contract.json", "missing_release_exception.csv"):
        assert subject.sha256_file(subject.HISTORICAL_CPI_DIR / name) == subject.sha256_file(subject.CPI_V2_DATA_DIR / name)


def test_interface_separates_targets_from_positions() -> None:
    interface = payload(subject.PACKAGE_DIR / "forward_observation_interface_contract.json")
    assert "strategy_target" in interface["outputs"]
    assert "share_quantities" not in interface["outputs"]
    assert "share_quantities" in interface["receiver_owned_outputs"]
    assert interface["current_target_calculation_requested"] is False


def test_state_machine_is_specification_only() -> None:
    state = payload(subject.PACKAGE_DIR / "strategy_state_machine.json")
    assert state["specification_only"] is True
    assert state["persistent_live_state_included"] is False
    assert set(state["states"]) == {"waiting_for_cpi_release", "cpi_release_received", "target_calculated", "pending_effective_close", "target_effective", "no_release_no_event"}


def test_all_six_caveats_are_carried_forward_exactly() -> None:
    source = (subject.ELIGIBILITY_DIR / "caveat_register.csv").read_bytes()
    exported = (subject.PACKAGE_DIR / "caveat_register.csv").read_bytes()
    assert exported == source
    rows = csv_rows(subject.PACKAGE_DIR / "caveat_register.csv")
    assert [row["caveat_id"] for row in rows] == ["C1", "C2", "C3", "C4", "C5", "C6"]
    assert not any(row["classification"] == "blocking" for row in rows)


def test_secret_and_absolute_path_hygiene_pass() -> None:
    hygiene = payload(subject.OUTPUT_DIR / "hygiene_scan.json")
    assert hygiene["secret_scan_pass"] is True
    assert hygiene["absolute_path_hygiene_pass"] is True
    assert hygiene["secret_hits"] == []
    assert hygiene["absolute_path_hits"] == []


def test_no_operational_or_research_activity_is_created() -> None:
    accounting = payload(subject.OUTPUT_DIR / "trial_accounting.json")
    for key in (
        "new_canonical_trials", "new_robustness_trials", "strategy_variants",
        "new_performance_calculations", "new_evaluation_accesses",
        "forward_observation_accesses", "provider_calls_for_current_state",
        "broker_calls", "current_signal_calculations", "current_target_calculations",
        "observation_ledger_mutations", "orders", "fills", "live_or_paper_positions",
    ):
        assert accounting[key] == 0
    assert accounting["handoff_exports_created"] == 1


def test_package_content_hash_is_self_verifying() -> None:
    manifest = payload(subject.PACKAGE_DIR / "handoff_manifest.json")
    assert manifest["package_content_hash"] == subject.normalized_package_hash()
    assert manifest["transport_archive_hash"] is None


def test_required_files_and_protected_state_reconcile() -> None:
    consistency = payload(subject.OUTPUT_DIR / "consistency_check.json")
    assert consistency["overall_pass"] is True
    assert consistency["checks"]["all_protected_state_unchanged"] is True
    assert all((subject.PACKAGE_DIR / name).exists() for name in subject.PACKAGE_REQUIRED_FILES)
    assert all((subject.OUTPUT_DIR / name).exists() for name in subject.OUTSIDE_REQUIRED_FILES)


def test_deterministic_regeneration_preserves_timestamp_and_hash(completed_run) -> None:
    created_before = payload(subject.PACKAGE_DIR / "handoff_manifest.json")["created_at"]
    second = subject.run()
    created_after = payload(subject.PACKAGE_DIR / "handoff_manifest.json")["created_at"]
    assert created_after == created_before
    assert second["package_content_hash"] == completed_run["package_content_hash"]
    assert second["overall_pass"] is True
