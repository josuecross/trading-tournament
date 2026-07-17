from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest

from strategy_lab.research_os.research import usci_current_methodology_validation_v1 as validation


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "usci_current_methodology_validation_v1" / "latest"
PRIOR_SCREEN = ROOT / "evidence" / "usci_dynamic_commodity_curve_selection_bounded_screen_v1" / "latest"
REGISTRY = ROOT / "strategy_lab" / "strategy_registry.yaml"
ACTIVE_OBSERVATIONS = ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml"


@pytest.fixture(scope="module", autouse=True)
def generated_validation() -> dict[str, object]:
    assert (EVIDENCE / "validation_outcome.json").exists(), "USCI current-methodology validation evidence must exist"
    return read_json("validation_outcome.json")


def read_json(name: str) -> dict[str, object]:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def read_csv(name: str) -> list[dict[str, str]]:
    with (EVIDENCE / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_prior_json(name: str) -> dict[str, object]:
    return json.loads((PRIOR_SCREEN / name).read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def test_required_artifacts_exist() -> None:
    required = {
        "validation_manifest.json",
        "prior_screen_lineage.json",
        "cache_hash_verification.json",
        "frozen_transition_interval.csv",
        "frozen_rolling_window_definitions.csv",
        "frozen_non_overlapping_windows.csv",
        "frozen_chronological_thirds.csv",
        "full_current_regime_metrics.csv",
        "monthly_start_90d_results.csv",
        "monthly_start_180d_results.csv",
        "monthly_start_252d_results.csv",
        "monthly_start_504d_results.csv",
        "non_overlapping_180d_results.csv",
        "non_overlapping_252d_results.csv",
        "non_overlapping_504d_results.csv",
        "chronological_thirds_results.csv",
        "calendar_year_results.csv",
        "rolling_summary.csv",
        "correlation_and_capture_diagnostics.csv",
        "accounting_data_and_alignment_invariants.csv",
        "validation_outcome.json",
        "exact_variant_research_memory.csv",
        "validation_summary.md",
        "consistency_check.json",
    }
    assert sorted(name for name in required if not (EVIDENCE / name).exists()) == []


def test_original_bounded_screen_evidence_remains_unchanged() -> None:
    lineage = read_json("prior_screen_lineage.json")
    prior_hashes = lineage["prior_screen_hashes_before_validation"]
    assert lineage["prior_screen_outcome"] == "methodology_regime_instability"
    assert lineage["prior_bounded_screen_remains_authoritative_for_full_history"] is True
    for relative_path, expected_hash in prior_hashes.items():
        assert sha256(ROOT / str(relative_path)) == expected_hash
    assert read_json("consistency_check.json")["prior_bounded_screen_unchanged"] is True


def test_candidate_fingerprint_is_unchanged() -> None:
    lineage = read_json("prior_screen_lineage.json")
    prior_packet_fingerprint = read_prior_json("candidate_fingerprint.json")
    assert lineage["prior_candidate_fingerprint"] == prior_packet_fingerprint
    assert prior_packet_fingerprint["candidate_id"] == validation.CANDIDATE_ID
    assert prior_packet_fingerprint["strategy_fingerprint"] == "2748AB65A5290C55FBDA12300C0C0601A9B7B90FEAAAC38A2F9E30240B7A213B"
    assert read_json("consistency_check.json")["candidate_fingerprint_unchanged"] is True


def test_current_regime_dates_are_frozen_independently_of_performance() -> None:
    manifest = read_json("validation_manifest.json")
    rolling_defs = read_csv("frozen_rolling_window_definitions.csv")
    non_overlap_defs = read_csv("frozen_non_overlapping_windows.csv")
    thirds = read_csv("frozen_chronological_thirds.csv")
    assert manifest["current_methodology_start"] == "2021-01-04"
    assert manifest["current_methodology_end"] == "2026-06-18"
    assert manifest["transition_interval"] == ["2020-12-24", "2020-12-31"]
    assert all(row["frozen_before_performance"] == "true" for row in rolling_defs + non_overlap_defs + thirds)
    assert all(row["performance_computed_at_definition_time"] == "false" for row in rolling_defs + non_overlap_defs + thirds)
    assert read_json("consistency_check.json")["current_regime_start_frozen"] is True


def test_transition_sessions_are_excluded_consistently() -> None:
    transition = read_csv("frozen_transition_interval.csv")[0]
    calendar = {row["period_id"]: row for row in read_csv("calendar_year_results.csv")}
    assert transition["start_date"] == "2020-12-24"
    assert transition["end_date"] == "2020-12-31"
    assert transition["included_in_validation_metrics"] == "false"
    assert calendar["transition_2020_12_24_to_2020_12_31"]["included_in_validation_outcome"] == "false"
    assert calendar["2021"]["start_date"] == "2021-01-04"
    assert calendar["2021"]["period_type"] == "complete_calendar_year"
    assert read_json("consistency_check.json")["transition_sessions_excluded"] is True


def test_no_cache_download_or_refresh_and_hashes_match_prior() -> None:
    cache = read_json("cache_hash_verification.json")
    rows = cache["rows"]
    assert cache["provider_download"] is False
    assert cache["provider_refresh"] is False
    assert cache["cache_hash_verification_passed"] is True
    assert cache["hash_mismatches"] == []
    assert {row["symbol"] for row in rows} == {"USCI", "DBC", "BIL", "SPY"}
    assert all(row["hash_matches_prior_screen"] is True for row in rows)
    assert all(sha256(ROOT / row["cache_path"]) == row["cache_hash"] for row in rows)
    check = read_json("consistency_check.json")
    assert check["no_cache_download_or_refresh"] is True
    assert check["cache_hashes_match_prior"] is True


def test_only_usci_dbc_bil_spy_are_used() -> None:
    manifest = read_json("validation_manifest.json")
    cache_symbols = {row["symbol"] for row in read_json("cache_hash_verification.json")["rows"]}
    assert cache_symbols == {"USCI", "DBC", "BIL", "SPY"}
    assert manifest["primary_benchmark"] == "DBC_buy_and_hold"
    assert manifest["secondary_context"] == ["BIL_cash_proxy", "SPY_buy_and_hold"]
    assert manifest["no_alternative_commodity_wrapper"] is True
    assert read_json("consistency_check.json")["only_USCI_DBC_BIL_SPY_used"] is True


def test_monthly_start_windows_are_deterministic_and_result_aligned() -> None:
    definitions = read_csv("frozen_rolling_window_definitions.csv")
    by_horizon = {90: 62, 180: 58, 252: 54, 504: 42}
    for horizon, expected_count in by_horizon.items():
        rows = [row for row in definitions if int(row["horizon_days"]) == horizon]
        results = read_csv(f"monthly_start_{horizon}d_results.csv")
        assert len(rows) == expected_count
        assert len(results) == expected_count
        assert [row["window_id"] for row in rows] == [row["window_id"] for row in results]
        assert all(int(row["trading_day_count"]) == horizon for row in rows)
    assert definitions[0]["start_date"] == "2021-01-04"
    assert read_json("consistency_check.json")["monthly_start_windows_deterministic"] is True


def test_non_overlapping_windows_start_from_frozen_regime_start() -> None:
    rows = read_csv("frozen_non_overlapping_windows.csv")
    by_horizon = {180: 7, 252: 5, 504: 2}
    for horizon, expected_count in by_horizon.items():
        horizon_rows = [row for row in rows if int(row["horizon_days"]) == horizon]
        results = read_csv(f"non_overlapping_{horizon}d_results.csv")
        assert len(horizon_rows) == expected_count
        assert len(results) == expected_count
        assert horizon_rows[0]["start_date"] == "2021-01-04"
        assert int(horizon_rows[0]["start_index"]) == 0
        assert [int(row["start_index"]) for row in horizon_rows] == [idx * horizon for idx in range(expected_count)]
    assert read_json("consistency_check.json")["non_overlapping_windows_start_from_frozen_regime_start"] is True


def test_chronological_thirds_are_frozen_before_performance() -> None:
    thirds = read_csv("frozen_chronological_thirds.csv")
    results = read_csv("chronological_thirds_results.csv")
    assert [row["third_id"] for row in thirds] == ["early_current_regime", "middle_current_regime", "recent_current_regime"]
    assert [row["third_id"] for row in thirds] == [row["third_id"] for row in results]
    assert [int(row["trading_day_count"]) for row in thirds] == [457, 457, 457]
    assert thirds[0]["start_date"] == "2021-01-04"
    assert thirds[-1]["end_date"] == "2026-06-18"
    assert read_json("consistency_check.json")["chronological_thirds_frozen_before_performance"] is True


def test_candidate_and_benchmark_dates_match() -> None:
    full = read_csv("full_current_regime_metrics.csv")
    assert {row["symbol"] for row in full} == {"USCI", "DBC", "BIL", "SPY"}
    assert {row["start_date"] for row in full} == {"2021-01-04"}
    assert {row["end_date"] for row in full} == {"2026-06-18"}
    for artifact in (
        "monthly_start_90d_results.csv",
        "monthly_start_180d_results.csv",
        "monthly_start_252d_results.csv",
        "monthly_start_504d_results.csv",
        "non_overlapping_180d_results.csv",
        "non_overlapping_252d_results.csv",
        "non_overlapping_504d_results.csv",
        "chronological_thirds_results.csv",
    ):
        assert all(row["start_date"] <= row["end_date"] for row in read_csv(artifact))
    assert read_json("consistency_check.json")["candidate_and_benchmark_dates_match"] is True


def test_adjusted_total_return_prices_are_used() -> None:
    cache_rows = read_json("cache_hash_verification.json")["rows"]
    invariants = read_csv("accounting_data_and_alignment_invariants.csv")[0]
    assert all(row["adjusted_price_validation_result"] == "pass" for row in cache_rows)
    assert all(row["missing_adj_close_count"] == 0 for row in cache_rows)
    assert invariants["adjusted_total_return_prices_used"] == "true"
    assert read_json("consistency_check.json")["adjusted_total_return_prices_used"] is True


def test_no_futures_timing_bil_switch_or_alternative_wrapper() -> None:
    manifest = read_json("validation_manifest.json")
    invariants = read_csv("accounting_data_and_alignment_invariants.csv")[0]
    assert manifest["no_futures_reconstruction"] is True
    assert manifest["no_timing_signal"] is True
    assert manifest["no_BIL_switch"] is True
    assert manifest["no_alternative_commodity_wrapper"] is True
    assert invariants["futures_reconstructed"] == "false"
    assert invariants["timing_signal_added"] == "false"
    assert invariants["BIL_switch_added"] == "false"
    assert invariants["alternative_commodity_wrapper_added"] == "false"
    check = read_json("consistency_check.json")
    assert check["no_futures_reconstructed"] is True
    assert check["no_timing_BIL_switch_or_alt_wrapper"] is True


def test_registry_active_observations_vm_dsr_active_combo_and_source_queue_unchanged() -> None:
    invariants = read_csv("accounting_data_and_alignment_invariants.csv")[0]
    check = read_json("consistency_check.json")
    assert REGISTRY.exists()
    assert ACTIVE_OBSERVATIONS.exists()
    assert invariants["registry_byte_identical"] == "true"
    assert invariants["active_observations_unchanged"] == "true"
    assert invariants["vm_dsr_active_combo_unchanged"] == "true"
    assert invariants["automatic_external_source_selection_paused"] == "true"
    assert check["registry_byte_identical"] is True
    assert check["vm_dsr_active_combo_unchanged"] is True
    assert check["automatic_external_source_selection_paused"] is True


def test_outcome_and_memory_are_non_promotional() -> None:
    outcome = read_json("validation_outcome.json")
    memory = read_csv("exact_variant_research_memory.csv")[0]
    assert outcome["outcome"] in validation.ALLOWED_OUTCOMES
    assert outcome["outcome"] == "historical_edge_recently_weakened"
    assert outcome["exact_candidate_closed_for_immediate_retesting"] is True
    assert outcome["promotion_authorized"] is False
    assert outcome["paper_demo_authorized"] is False
    assert outcome["candidate_exhaustive_authorized"] is False
    assert outcome["real_money_recommendation"] is False
    assert memory["original_bounded_screen_outcome"] == "methodology_regime_instability"
    assert memory["broader_commodity_curve_selection_family_closed"] == "false"
    assert memory["no_lifecycle_or_evidence_level_change"] == "true"


def test_output_generation_is_deterministic_and_does_not_change_prior_screen() -> None:
    output_files = [
        "validation_manifest.json",
        "cache_hash_verification.json",
        "full_current_regime_metrics.csv",
        "rolling_summary.csv",
        "validation_outcome.json",
        "consistency_check.json",
    ]
    prior_hashes = {path: sha256(path) for path in PRIOR_SCREEN.glob("*") if path.is_file()}
    before = {name: sha256(EVIDENCE / name) for name in output_files}
    result = validation.run()
    after = {name: sha256(EVIDENCE / name) for name in output_files}
    assert result["consistency_passed"] is True
    assert result["provider_download"] is False
    assert before == after
    assert {path: sha256(path) for path in PRIOR_SCREEN.glob("*") if path.is_file()} == prior_hashes


def test_consistency_check_passes() -> None:
    check = read_json("consistency_check.json")
    assert check["consistency_passed"] is True
