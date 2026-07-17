from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from strategy_lab.research_os.research import combo_vm_dsr_usci_equal_weight_monthly_validation_v1 as validation


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "combo_vm_dsr_usci_equal_weight_monthly_validation_v1" / "latest"
ORIGINAL = ROOT / "evidence" / "combo_vm_dsr_usci_equal_weight_monthly_bounded_screen_v1" / "latest"


def read_json(name: str) -> dict[str, object]:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def read_csv(name: str) -> list[dict[str, str]]:
    with (EVIDENCE / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_required_validation_artifacts_exist() -> None:
    required = {
        "validation_manifest.json",
        "original_packet_hashes.json",
        "component_lineage_verification.csv",
        "benchmark_normalization_check.csv",
        "calendar_period_classification.csv",
        "selection_conditioning_disclosure.json",
        "frozen_monthly_start_90d_windows.csv",
        "frozen_monthly_start_180d_windows.csv",
        "frozen_monthly_start_252d_windows.csv",
        "frozen_monthly_start_504d_windows.csv",
        "frozen_non_overlapping_180d_windows.csv",
        "frozen_non_overlapping_252d_windows.csv",
        "frozen_non_overlapping_504d_windows.csv",
        "frozen_chronological_thirds.csv",
        "current_period_full_metrics.csv",
        "monthly_start_rolling_results.csv",
        "monthly_start_rolling_summary.csv",
        "non_overlapping_window_results.csv",
        "chronological_thirds_results.csv",
        "complete_calendar_year_results.csv",
        "latest_window_diagnostics.csv",
        "full_wrapper_regime_diagnostic.csv",
        "component_contribution_by_period.csv",
        "cost_stress_results.csv",
        "persistence_analysis.csv",
        "accounting_lineage_alignment_invariants.csv",
        "validation_outcome.json",
        "exact_variant_research_memory.csv",
        "validation_summary.md",
        "consistency_check.json",
    }
    assert sorted(name for name in required if not (EVIDENCE / name).exists()) == []


def test_original_bounded_packet_remains_byte_identical() -> None:
    hashes = read_json("original_packet_hashes.json")
    assert hashes["byte_identical"] is True
    assert hashes["before"] == hashes["after"]
    for rel_path, before_hash in hashes["before"].items():
        assert rel_path.startswith("evidence/combo_vm_dsr_usci_equal_weight_monthly_bounded_screen_v1/latest/")
        path = ROOT / rel_path
        assert path.exists()
        assert before_hash == hashes["after"][rel_path]


def test_component_fingerprints_and_histories_match_original_packet() -> None:
    rows = read_csv("component_lineage_verification.csv")
    assert {row["component_id"] for row in rows} == {
        validation.VM_ID,
        validation.DSR_ID,
        validation.USCI_ID,
    }
    assert all(row["fingerprint_matches_original"] == "true" for row in rows)
    assert all(row["history_matches_original"] == "true" for row in rows)
    assert read_json("consistency_check.json")["component_fingerprints_and_histories_match_original"] is True


def test_candidate_rules_weights_and_active_state_are_unchanged() -> None:
    manifest = read_json("validation_manifest.json")
    consistency = read_json("consistency_check.json")
    assert manifest["candidate_id"] == validation.CANDIDATE_ID
    assert manifest["validation_only"] is True
    assert consistency["candidate_rules_and_weights_unchanged"] is True
    assert consistency["active_VM_DSR_USCI_observations_unchanged"] is True
    assert consistency["active_combo_byte_identical"] is True


def test_current_methodology_period_and_common_date_count_are_frozen() -> None:
    manifest = read_json("validation_manifest.json")
    assert manifest["current_methodology_start"] == "2021-01-04"
    assert manifest["current_methodology_end"] == "2026-06-18"
    assert manifest["common_date_count"] == 1371


def test_benchmark_rebasing_is_presentation_only() -> None:
    rows = read_csv("benchmark_normalization_check.csv")
    assert rows
    assert all(row["total_return_unchanged_by_rebase"] == "true" for row in rows)
    assert all(row["CAGR_unchanged_by_rebase"] == "true" for row in rows)
    assert all(row["drawdown_unchanged_by_rebase"] == "true" for row in rows)
    assert read_json("consistency_check.json")["benchmark_rebasing_does_not_change_return_or_risk"] is True


def test_current_period_metrics_use_rebased_presentation_scale() -> None:
    rows = {row["strategy_id"]: row for row in read_csv("current_period_full_metrics.csv")}
    assert abs(float(rows[validation.ACTIVE_COMBO_ID]["rebased_final_equity"]) - 3000.0 * (1.0 + float(rows[validation.ACTIVE_COMBO_ID]["total_return"]))) <= 1e-6
    assert abs(float(rows["SPY_buy_and_hold"]["rebased_final_equity"]) - 3000.0 * (1.0 + float(rows["SPY_buy_and_hold"]["total_return"]))) <= 1e-6
    assert abs(float(rows["BIL_cash_proxy"]["rebased_final_equity"]) - 3000.0 * (1.0 + float(rows["BIL_cash_proxy"]["total_return"]))) <= 1e-6


def test_partial_calendar_years_are_excluded_from_complete_year_win_counts() -> None:
    rows = {int(row["calendar_year"]): row for row in read_csv("calendar_period_classification.csv")}
    assert rows[2021]["classification"] == "partial_first_year"
    assert rows[2026]["classification"] == "partial_final_year"
    assert rows[2021]["included_in_complete_year_win_count"] == "false"
    assert rows[2026]["included_in_complete_year_win_count"] == "false"
    assert {year for year, row in rows.items() if row["included_in_complete_year_win_count"] == "true"} == {2022, 2023, 2024, 2025}


def test_monthly_start_windows_are_deterministic() -> None:
    for horizon in validation.MONTHLY_START_HORIZONS:
        rows = read_csv(f"frozen_monthly_start_{horizon}d_windows.csv")
        assert rows
        assert all(row["window_type"] == "monthly_start_overlapping_dependent" for row in rows)
        assert all(row["frozen_before_performance"] == "true" for row in rows)
        assert rows == sorted(rows, key=lambda row: row["start_date"])
    assert read_json("consistency_check.json")["monthly_start_windows_deterministic"] is True


def test_latest_windows_are_diagnostics_not_tactical_signals() -> None:
    rows = read_csv("latest_window_diagnostics.csv")
    assert {int(row["horizon_days"]) for row in rows} == {90, 180, 252, 504}
    assert all(row["window_type"] == "latest_complete_diagnostic" for row in rows)
    assert all(row["frozen_before_performance"] == "true" for row in rows)


def test_non_overlapping_windows_begin_at_frozen_start() -> None:
    for horizon in validation.NON_OVERLAPPING_HORIZONS:
        rows = read_csv(f"frozen_non_overlapping_{horizon}d_windows.csv")
        assert rows[0]["start_date"] == "2021-01-04"
        assert all(int(row["start_index"]) == index * horizon for index, row in enumerate(rows))
    assert read_json("consistency_check.json")["non_overlapping_windows_begin_at_frozen_start"] is True


def test_full_wrapper_regime_boundaries_are_fixed_and_not_current_labeled() -> None:
    rows = {row["regime_id"]: row for row in read_csv("full_wrapper_regime_diagnostic.csv")}
    assert rows["usci_historical_methodology_live_wrapper"]["end_date"] == "2020-12-23"
    assert rows["usci_historical_methodology_live_wrapper"]["methodology_label"] == "historical_USCI_methodology_not_current"
    assert rows["usci_transition_interval_descriptive_only"]["start_date"] == "2020-12-24"
    assert rows["usci_transition_interval_descriptive_only"]["end_date"] == "2020-12-31"
    assert rows["usci_current_methodology"]["start_date"] == "2021-01-04"
    assert rows["usci_current_methodology"]["end_date"] == "2026-06-18"
    assert all(row["historical_USCI_methodology_represented_as_current"] == "false" for row in rows.values())


def test_selection_conditioning_is_disclosed() -> None:
    disclosure = read_json("selection_conditioning_disclosure.json")
    assert disclosure["USCI_selected_after_strong_current_methodology_historical_results"] is True
    assert disclosure["combination_candidate_created_after_USCI_selection"] is True
    assert disclosure["current_methodology_combination_screen_is_not_independent_out_of_sample_evidence"] is True


def test_sleeve_drift_cost_application_and_cost_stress_are_recorded() -> None:
    invariants = read_csv("accounting_lineage_alignment_invariants.csv")[0]
    cost = read_csv("cost_stress_results.csv")[0]
    assert invariants["sleeve_values_drift_between_monthly_rebalances"] == "true"
    assert invariants["component_costs_reapplied"] == "false"
    assert invariants["portfolio_transfer_costs_applied_once"] == "true"
    assert cost["component_costs_changed"] == "false"
    assert cost["strategy_rules_changed"] == "false"
    assert read_json("consistency_check.json")["doubled_transfer_cost_stress_changes_no_strategy_rules"] is True


def test_cost_stress_preserves_validation_support_without_rule_changes() -> None:
    cost = read_csv("cost_stress_results.csv")[0]
    assert cost["canonical_outcome"] == "validation_supports_paper_forward_review"
    assert cost["stressed_outcome"] == "validation_supports_paper_forward_review"
    assert cost["primary_outcome_unchanged_under_cost_stress"] == "true"
    assert cost["strategy_rules_changed"] == "false"


def test_no_alternative_portfolio_or_paper_broker_path_is_created() -> None:
    memory = read_csv("exact_variant_research_memory.csv")[0]
    consistency = read_json("consistency_check.json")
    assert "leave_one_out_variants" in memory["immediate_variants_prohibited"]
    assert consistency["no_leave_one_out_or_alternative_weight_portfolio_created"] is True
    assert consistency["no_paper_demo_observation_or_broker_order"] is True
    assert consistency["paper_forward_activation"] is False
    assert consistency["promotion_authorized"] is False
    assert consistency["candidate_exhaustive_authorized"] is False
    assert consistency["real_money_recommendation"] is False


def test_persistence_and_component_contribution_are_recorded() -> None:
    persistence = read_csv("persistence_analysis.csv")[0]
    assert persistence["selection_conditioned_evidence"] == "true"
    assert int(persistence["positive_excess_chronological_thirds"]) == 2
    assert int(persistence["complete_calendar_years_beating_active_combo"]) == 3
    assert float(persistence["usci_pct_total_candidate_gain"]) > 0.5


def test_exposure_never_exceeds_one_and_output_is_deterministic() -> None:
    invariants = read_csv("accounting_lineage_alignment_invariants.csv")[0]
    consistency = read_json("consistency_check.json")
    assert float(invariants["maximum_exposure"]) <= 1.000001
    assert invariants["exposure_never_exceeds_1"] == "true"
    assert consistency["exposure_never_exceeds_1"] is True
    assert consistency["output_generation_deterministic"] is True
    assert consistency["consistency_passed"] is True


def test_validation_outcome_is_single_allowed_label() -> None:
    outcome = read_json("validation_outcome.json")
    assert outcome["validation_outcome"] in validation.ALLOWED_OUTCOMES
    assert outcome["paper_forward_activation"] is False
    assert outcome["promotion_authorized"] is False
    assert outcome["candidate_exhaustive_authorized"] is False
    assert outcome["real_money_recommendation"] is False
    assert outcome["next_action"] in {
        "direction_owner_paper_forward_eligibility_review_combo_vm_dsr_usci_equal_weight_monthly_v1",
        "record_combo_vm_dsr_usci_equal_weight_monthly_validation_memory_and_resume_source_queue",
    }


def test_validation_routes_to_review_without_activation() -> None:
    outcome = read_json("validation_outcome.json")
    assert outcome["validation_outcome"] == "validation_supports_paper_forward_review"
    assert outcome["paper_forward_eligibility_review_authorized_next"] is True
    assert outcome["paper_forward_activation"] is False


def test_validation_generation_is_deterministic() -> None:
    before = read_json("validation_outcome.json")
    before_hashes = read_json("original_packet_hashes.json")
    rerun = validation.run()
    after = read_json("validation_outcome.json")
    after_hashes = read_json("original_packet_hashes.json")
    assert rerun["validation_outcome"] == before["validation_outcome"]
    assert after == before
    assert after_hashes == before_hashes
