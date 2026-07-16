from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from strategy_lab.research_os.research import angl_static_fallen_angel_credit_validation_v1 as validation


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "angl_static_fallen_angel_credit_validation_v1" / "latest"
SCREEN_EVIDENCE = ROOT / "evidence" / "angl_static_fallen_angel_credit_screen_v1" / "latest"


@pytest.fixture(scope="module", autouse=True)
def generated_validation() -> dict[str, object]:
    return validation.run()


def read_json(name: str) -> dict[str, object]:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def read_csv(name: str) -> list[dict[str, str]]:
    with (EVIDENCE / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_required_artifacts_exist() -> None:
    required = {
        "validation_manifest.json",
        "screen_packet_consistency_correction.csv",
        "monthly_start_90d_results.csv",
        "monthly_start_180d_results.csv",
        "monthly_start_252d_results.csv",
        "monthly_start_504d_results.csv",
        "non_overlapping_180d_results.csv",
        "non_overlapping_252d_results.csv",
        "non_overlapping_504d_results.csv",
        "calendar_year_results.csv",
        "full_period_metrics.csv",
        "chronological_thirds_metrics.csv",
        "methodology_regime_metrics.csv",
        "rolling_excess_return_diagnostics.csv",
        "return_risk_joint_outcomes.csv",
        "risk_context_diagnostics.csv",
        "accounting_and_alignment_invariants.csv",
        "validation_summary.md",
        "validation_outcome.json",
        "exact_variant_research_memory.csv",
        "artifact_lineage.csv",
        "consistency_check.json",
    }
    assert sorted(name for name in required if not (EVIDENCE / name).exists()) == []


def test_screen_packet_regime3_wording_inconsistency_is_corrected() -> None:
    correction = read_csv("screen_packet_consistency_correction.csv")[0]
    caveat = (SCREEN_EVIDENCE / "source_and_methodology_caveats.md").read_text(encoding="utf-8")
    assert correction["correction_type"] == "wording_only"
    assert correction["screen_metrics_changed"] == "false"
    assert correction["screen_outcome_changed"] == "false"
    assert correction["descriptive_only_claim_removed_when_not_applicable"] == "true"
    assert "descriptive-only sample" not in caveat.lower()
    assert "hard-evidence eligible" in caveat


def test_regime3_hard_evidence_eligible_and_shorter_sample_caveated() -> None:
    regimes = {row["period_id"]: row for row in read_csv("methodology_regime_metrics.csv")}
    regime3 = regimes["methodology_regime_3_amended_h0cf_methodology"]
    assert int(regime3["trading_day_count"]) == 618
    assert regime3["evidence_weight"] == "hard_evidence_eligible"
    assert regime3["shorter_post_amendment_sample_caveat"] == "true"
    assert regime3["post_2023_short_sample_caveat"] == "true"


def test_monthly_start_windows_are_generated_deterministically() -> None:
    rows = read_csv("monthly_start_252d_results.csv")
    assert rows
    assert rows[0]["window_start"] == validation.COMMON_START
    assert {row["selection_algorithm"] for row in rows} == {"first_common_trading_session_of_each_calendar_month"}
    assert {row["overlapping_windows_not_statistically_independent"] for row in rows} == {"true"}
    assert {row["performance_computed_at_definition_time"] for row in rows} == {"false"}


def test_non_overlapping_windows_begin_at_first_common_date() -> None:
    for name in ("non_overlapping_180d_results.csv", "non_overlapping_252d_results.csv", "non_overlapping_504d_results.csv"):
        rows = read_csv(name)
        assert rows[0]["window_start"] == validation.COMMON_START
        assert {row["selection_algorithm"] for row in rows} == {
            "consecutive_windows_from_first_common_date_final_incomplete_remainder_discarded"
        }
        assert all(row["window_valid"] == "true" for row in rows)


def test_calendar_year_classification_is_deterministic() -> None:
    rows = read_csv("calendar_year_results.csv")
    by_year = {row["calendar_year"]: row for row in rows}
    assert by_year["2012"]["coverage_classification"] == "partial_year_context_only"
    assert by_year["2026"]["coverage_classification"] == "partial_year_context_only"
    assert by_year["2013"]["coverage_classification"] == "complete_calendar_year"
    assert by_year["2025"]["included_in_complete_year_win_rate"] == "true"


def test_rolling_diagnostics_do_not_create_strategy_signal() -> None:
    rows = read_csv("rolling_excess_return_diagnostics.csv")
    assert {row["rolling_horizon_days"] for row in rows} == {"252", "504"}
    assert {row["diagnostic_only_no_strategy_signal"] for row in rows} == {"true"}
    assert any(row["final_observation_negative"] == "true" for row in rows)


def test_actual_etf_shares_and_equal_costs_are_used() -> None:
    manifest = read_json("validation_manifest.json")
    invariants = {row["invariant_id"]: row for row in read_csv("accounting_and_alignment_invariants.csv")}
    assert manifest["transaction_cost_convention"]["standard_slippage_pct_per_side"] == pytest.approx(0.0005)
    assert set(manifest["transaction_cost_convention"]["identical_treatment_for"]) == {"ANGL", "HYG", "BIL", "IEF"}
    assert invariants["actual_etf_shares_and_equal_costs_used"]["invariant_passed"] == "true"


def test_angl_hyg_dates_are_aligned() -> None:
    manifest = read_json("validation_manifest.json")
    rows = read_csv("monthly_start_180d_results.csv")
    assert manifest["common_start"] == validation.COMMON_START
    assert manifest["common_end"] == validation.COMMON_END
    assert manifest["common_row_count"] == 3568
    assert {row["matching_angl_hyg_dates_used"] for row in rows if row["window_valid"] == "true"} == {"true"}


def test_hyg_primary_benchmark_and_context_only_assets() -> None:
    outcome = read_json("validation_outcome.json")
    risk = read_csv("risk_context_diagnostics.csv")
    assert outcome["primary_benchmark"] == "HYG"
    assert all(row["descriptive_only_no_duration_causal_claim"] == "true" for row in risk)
    assert all(row["duration_neutral_strategy_created"] == "false" for row in risk)


def test_no_provider_wrapper_benchmark_filter_or_date_search() -> None:
    manifest = read_json("validation_manifest.json")
    check = read_json("consistency_check.json")
    assert manifest["no_provider_call"] is True
    assert manifest["provider_download"] is False
    assert manifest["no_alternative_wrapper_benchmark_filter_or_date_search"] is True
    assert check["no_provider_call"] is True
    assert check["no_alternative_wrapper_benchmark_filter_or_date_search"] is True


def test_registry_active_observations_and_pause_remain_unchanged() -> None:
    check = read_json("consistency_check.json")
    assert check["registry_byte_identical"] is True
    assert check["active_observations_unchanged"] is True
    assert check["external_source_pause_remains_active"] is True


def test_outcome_is_non_promotional_and_state_neutral() -> None:
    outcome = read_json("validation_outcome.json")
    memory = read_csv("exact_variant_research_memory.csv")[0]
    assert outcome["validation_outcome"] in validation.ALLOWED_OUTCOMES
    assert outcome["promotion_authorized"] is False
    assert outcome["paper_demo_authorized"] is False
    assert outcome["candidate_exhaustive_authorized"] is False
    assert outcome["strategy_state_changed"] is False
    assert memory["lifecycle_status_changed"] == "false"
    assert memory["do_not_test_another_fallen_angel_etf_automatically"] == "true"


def test_generation_is_deterministic() -> None:
    first_manifest = read_json("validation_manifest.json")
    first_outcome = read_json("validation_outcome.json")
    first_rolling = (EVIDENCE / "rolling_excess_return_diagnostics.csv").read_text(encoding="utf-8")
    result = validation.run()
    assert result["consistency_passed"] is True
    assert read_json("validation_manifest.json") == first_manifest
    assert read_json("validation_outcome.json") == first_outcome
    assert (EVIDENCE / "rolling_excess_return_diagnostics.csv").read_text(encoding="utf-8") == first_rolling


def test_consistency_check_passes() -> None:
    assert read_json("consistency_check.json")["consistency_passed"] is True
