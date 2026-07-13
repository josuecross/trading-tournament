from __future__ import annotations

import csv
import json
from pathlib import Path

from strategy_lab.research_os.research.strategy_family_coverage_and_next_discovery_v1 import (
    OUTPUT_DIR,
    PRIOR_PROMISING_FAMILIES,
    SIX_SCREENED_LANES,
)


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / OUTPUT_DIR


def load_json(name: str):
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def csv_rows(name: str) -> list[dict[str, str]]:
    with (EVIDENCE / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_required_family_coverage_artifacts_exist() -> None:
    required = [
        "family_coverage_summary.md",
        "family_coverage_matrix.csv",
        "tested_mechanism_concentration.csv",
        "exact_variant_do_not_retest.csv",
        "external_source_readiness.csv",
        "prior_promising_family_status.csv",
        "next_discovery_options.csv",
        "next_discovery_options.md",
        "missing_source_research_questions.csv",
        "coverage_consistency_check.json",
    ]
    for name in required:
        assert (EVIDENCE / name).exists(), name


def test_six_screened_lanes_are_exact_do_not_retest_memory() -> None:
    rows = csv_rows("exact_variant_do_not_retest.csv")
    lane_ids = {row["lane_id"] for row in rows}

    assert lane_ids == set(SIX_SCREENED_LANES)
    assert all(row["batch_id"] == "public_source_comparative_screening_batch_v1" for row in rows)
    assert all(row["ready_for_immediate_retest"] == "false" for row in rows)
    assert all(row["family_remains_open"] == "true" for row in rows)
    assert all(row["primary_variant_id"] for row in rows)


def test_coppock_and_percent_b_specific_closures_are_recorded() -> None:
    rows = {row["lane_id"]: row for row in csv_rows("exact_variant_do_not_retest.csv")}

    coppock = rows["public_source_coppock_curve_bounded_bt_lane_v1"]
    assert "benchmark-like" in coppock["concise_failure_reason"]
    assert "SPY buy-and-hold" in coppock["concise_failure_reason"]

    percent_b = rows["public_source_percent_b_money_flow_bounded_bt_lane_v1"]
    assert "four of ten" in percent_b["concise_failure_reason"]
    assert "zero sampled" in percent_b["concise_failure_reason"]
    assert "no robustness review authorized" in percent_b["concise_failure_reason"]


def test_external_source_readiness_excludes_closed_and_internal_sources() -> None:
    rows = csv_rows("external_source_readiness.csv")
    closed_source_ids = {
        "adx_dmi_trend_strength_crossover",
        "cci_correction",
        "coppock_curve_monthly_equity_signal",
        "larry_connors_rsi2_mean_reversion",
        "parabolic_sar_spy_bil_long_only_reversal",
        "percent_b_money_flow",
    }

    assert rows
    assert not (closed_source_ids & {row["source_id"] for row in rows})
    assert all(not row["source_class"].startswith("internal") for row in rows)
    assert all(row["readiness_classification"] != "ready_for_preregistration" for row in rows)


def test_prior_promising_families_remain_visible_and_non_promotable() -> None:
    rows = {row["family_id"]: row for row in csv_rows("prior_promising_family_status.csv")}

    assert set(PRIOR_PROMISING_FAMILIES).issubset(rows)
    assert rows["high_return_tactical_etf_equity_index"]["outputs_non_promotable"] == "true"
    assert rows["macro_gld_duration_risk_off"]["outputs_non_promotable"] == "true"
    assert "context" in rows["high_return_tactical_etf_equity_index"]["current_status"]
    assert "diagnostic" in rows["macro_gld_duration_risk_off"]["current_status"]


def test_family_matrix_includes_prior_families_and_active_combo_reference_only() -> None:
    family_rows = {row["family_id"]: row for row in csv_rows("family_coverage_matrix.csv")}
    consistency = load_json("coverage_consistency_check.json")

    assert "high_return_tactical_etf_equity_index" in family_rows
    assert "macro_gld_duration_risk_off" in family_rows
    assert family_rows["high_return_tactical_etf_equity_index"]["coverage_status"] == (
        "open_only_for_materially_distinct_hypothesis"
    )
    assert family_rows["macro_gld_duration_risk_off"]["coverage_status"] == (
        "open_only_for_materially_distinct_hypothesis"
    )
    assert consistency["active_combo_reference_only"] is True


def test_next_discovery_options_are_bounded_not_approved() -> None:
    rows = csv_rows("next_discovery_options.csv")

    assert 0 < len(rows) <= 3
    assert all(row["approved"] == "false" for row in rows)
    assert all(row["readiness_status"] != "approved" for row in rows)
    assert any(row["case_type"] == "case_a_existing_backlog_candidate" for row in rows)
    assert any(row["case_type"] == "case_b_source_research_gap" for row in rows)


def test_consistency_check_matches_strict_scope() -> None:
    consistency = load_json("coverage_consistency_check.json")

    assert consistency["consistency_passed"] is True
    assert consistency["screened_lane_ids_in_memory"] is True
    assert consistency["none_of_six_ready_for_immediate_retesting"] is True
    assert consistency["coppock_identified_as_sampled_benchmark_like"] is True
    assert consistency["percent_b_not_advanced_to_robustness"] is True
    assert consistency["internal_generated_sel_sources_excluded_from_external_candidates"] is True
    assert consistency["exact_rejected_variants_reopened"] is False
    assert consistency["active_vm_dsr_lifecycle_unchanged"] is True
    assert consistency["high_return_tactical_included"] is True
    assert consistency["macro_gld_included"] is True
    assert consistency["next_discovery_option_count_lte_3"] is True
    assert consistency["no_option_approved"] is True
    assert consistency["no_backtests_run"] is True
    assert consistency["no_provider_download"] is True
    assert consistency["no_strategy_implementation"] is True
    assert consistency["no_paper_demo_state_changed"] is True
