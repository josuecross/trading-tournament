from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from strategy_lab.research_os.research.high_return_tactical_etf_equity_index_bounded_robustness import (
    EXPECTED_ROW_COUNT,
    FAMILY_ID,
    LANE_ID,
    OUTPUT_DIR,
    VALID_NEXT_ACTIONS,
)


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / OUTPUT_DIR


def load_manifest() -> dict:
    return json.loads((EVIDENCE / "high_return_tactical_bounded_robustness_manifest.json").read_text(encoding="utf-8"))


def load_consistency() -> dict:
    return json.loads(
        (EVIDENCE / "high_return_tactical_bounded_robustness_consistency_check.json").read_text(encoding="utf-8")
    )


def test_high_return_tactical_robustness_guardrails_and_counts() -> None:
    manifest = load_manifest()
    consistency = load_consistency()

    assert manifest["high_return_tactical_bounded_robustness_report"] is True
    assert manifest["lane_id"] == LANE_ID
    assert manifest["family_id"] == FAMILY_ID
    assert manifest["same_6_rows_evaluated"] is True
    assert manifest["rows_evaluated"] == EXPECTED_ROW_COUNT
    assert manifest["cost_model"] == "evaluation_only_cost_per_turnover_unit"
    assert manifest["cost_stress_bps"] == [10, 25]
    assert manifest["new_strategy_discovery_run"] is False
    assert manifest["new_research_batch_run"] is False
    assert manifest["new_families_created"] is False
    assert manifest["new_variants_created"] is False
    assert manifest["new_rows_added"] is False
    assert manifest["new_concepts_added"] is False
    assert manifest["new_lookbacks_added"] is False
    assert manifest["new_universes_added"] is False
    assert manifest["threshold_tuning_added"] is False
    assert manifest["drawdown_guard_rows_used"] is False
    assert manifest["hidden_parameter_grid_created"] is False
    assert manifest["uses_local_cache_only"] is True
    assert manifest["provider_download"] is False
    assert manifest["intraday_data_used"] is False
    assert manifest["leverage_used"] is False
    assert manifest["shorting_used"] is False
    assert manifest["options_used"] is False
    assert manifest["direct_futures_used"] is False
    assert manifest["broker_api_called"] is False
    assert manifest["broker_orders_submitted"] is False
    assert manifest["broker_orders_cancelled"] is False
    assert manifest["broker_orders_reconciled"] is False
    assert manifest["live_orders"] is False
    assert manifest["real_money_recommendation"] is False
    assert manifest["promotion_candidates_created"] is False
    assert manifest["candidate_exhaustive_run"] is False
    assert manifest["paper_forward_activation"] is False
    assert manifest["new_paper_forward_candidate_created"] is False
    assert manifest["best_single_variant_promoted"] is False
    assert manifest["research_outputs_remain_non_promotable"] is True
    assert manifest["outputs_promotable"] is False
    assert manifest["outputs_candidate_exhaustive_ready"] is False
    assert manifest["outputs_paper_forward_eligible"] is False
    assert manifest["active_vm_preserved"] is True
    assert manifest["active_dsr_preserved"] is True
    assert manifest["static_all_weather_benchmark_control_only"] is True
    assert manifest["commodity_continued"] is False
    assert manifest["macro_gld_continued"] is False
    assert manifest["volatility_throttle_threshold_tuning_continued"] is False
    assert manifest["managed_futures_reopened"] is False
    assert manifest["new_combo_strategy_created"] is False
    assert manifest["exact_rejected_variants_reopened"] is False
    assert manifest["pre_fix_stale_weight_results_used"] is False
    assert manifest["invariant_failures"] == 0
    assert manifest["base_run_metric_mismatch_count"] == 0
    assert manifest["next_action"] in VALID_NEXT_ACTIONS
    assert consistency["consistency_passed"] is True


def test_high_return_tactical_robustness_outputs_cover_same_rows() -> None:
    stress = pd.read_csv(EVIDENCE / "base_vs_stress_row_results.csv")
    run_rows = pd.read_csv(
        ROOT
        / "evidence"
        / "research_recovery"
        / "high_return_tactical_etf_equity_index_bounded_run"
        / "latest"
        / "high_return_tactical_bounded_run_results.csv"
    )

    assert len(stress) == EXPECTED_ROW_COUNT
    assert set(stress["variant_id"]) == set(run_rows["variant_id"])
    assert stress["base_numeric_criteria_pass"].astype(str).str.lower().isin({"true", "false"}).all()
    assert stress["stress_10bps_numeric_criteria_pass"].astype(str).str.lower().isin({"true", "false"}).all()
    assert stress["stress_25bps_numeric_criteria_pass"].astype(str).str.lower().isin({"true", "false"}).all()
    assert (stress["stress_10bps_cagr"] <= stress["base_cagr"] + 1e-12).all()
    assert (stress["stress_25bps_cagr"] <= stress["stress_10bps_cagr"] + 1e-12).all()
    assert stress["base_run_metric_mismatch_fields"].fillna("").eq("").all()
    assert (stress["promotion_eligibility"].astype(str).str.lower() == "false").all()
    assert (stress["paper_forward_eligibility"].astype(str).str.lower() == "false").all()
    assert (stress["candidate_exhaustive_eligibility"].astype(str).str.lower() == "false").all()


def test_high_return_tactical_robustness_required_artifacts_and_diagnostics() -> None:
    subperiod = pd.read_csv(EVIDENCE / "subperiod_performance.csv")
    rolling = pd.read_csv(EVIDENCE / "rolling_window_weakness.csv")
    comparator = pd.read_csv(EVIDENCE / "comparator_redundancy_contribution.csv")
    stress = pd.read_csv(EVIDENCE / "base_vs_stress_row_results.csv")

    for filename in [
        "high_return_tactical_bounded_robustness_manifest.json",
        "high_return_tactical_bounded_robustness_consistency_check.json",
        "base_vs_stress_row_results.csv",
        "subperiod_performance.csv",
        "rolling_window_weakness.csv",
        "rolling_window_weakness_report.md",
        "comparator_redundancy_contribution_report.md",
        "comparator_redundancy_contribution.csv",
        "exposure_invariant_report.md",
        "high_return_tactical_bounded_robustness_summary.md",
        "high_return_tactical_bounded_robustness_next_action.md",
        "do_not_promote_from_high_return_tactical_robustness.md",
    ]:
        assert (EVIDENCE / filename).exists(), filename

    assert len(subperiod) == EXPECTED_ROW_COUNT * 3
    assert set(subperiod["variant_id"]) == set(stress["variant_id"])
    assert set(subperiod["period_id"]) == {
        "subperiod_2007_2014",
        "subperiod_2015_2020",
        "subperiod_2021_latest",
    }
    assert len(rolling) == EXPECTED_ROW_COUNT
    assert set(rolling["variant_id"]) == set(stress["variant_id"])
    assert len(comparator) == EXPECTED_ROW_COUNT
    assert set(comparator["variant_id"]) == set(stress["variant_id"])
    assert "active_combo_relationship" in comparator.columns
