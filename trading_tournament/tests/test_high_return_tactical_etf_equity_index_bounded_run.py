from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from strategy_lab.research_os.research.high_return_tactical_etf_equity_index_bounded_run import (
    ALLOWED_LABELS,
    EXPECTED_ROW_COUNT,
    FAMILY_ID,
    LANE_ID,
    OUTPUT_DIR,
    VALID_NEXT_ACTIONS,
)


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / OUTPUT_DIR

APPROVED_VARIANT_IDS = {
    "hrt_bounded_vt_orig_equity_growth_core_mom63_top2_v1",
    "hrt_bounded_vt_orig_equity_growth_core_mom126_top2_v1",
    "hrt_bounded_vt_orig_equity_growth_core_mom252_top2_v1",
    "hrt_bounded_vt_orig_equity_sector_growth_mom63_top2_v1",
    "hrt_bounded_vt_orig_equity_sector_growth_mom126_top2_v1",
    "hrt_bounded_vt_orig_equity_sector_growth_mom252_top2_v1",
}


def load_manifest() -> dict:
    return json.loads((EVIDENCE / "high_return_tactical_bounded_run_manifest.json").read_text(encoding="utf-8"))


def load_consistency() -> dict:
    return json.loads((EVIDENCE / "high_return_tactical_bounded_run_consistency_check.json").read_text(encoding="utf-8"))


def test_high_return_tactical_bounded_run_guardrails_and_counts() -> None:
    manifest = load_manifest()
    consistency = load_consistency()

    assert manifest["high_return_tactical_bounded_run"] is True
    assert manifest["lane_id"] == LANE_ID
    assert manifest["family_id"] == FAMILY_ID
    assert manifest["source_design_run_ready"] is True
    assert manifest["source_followup_audit_passed"] is True
    assert manifest["variant_count_planned"] == EXPECTED_ROW_COUNT
    assert manifest["variant_count_evaluated"] == EXPECTED_ROW_COUNT
    assert manifest["data_blocked_variant_count"] == 0
    assert manifest["source_mapping_failure_count"] == 0
    assert manifest["new_research_batch_run"] is False
    assert manifest["new_strategy_discovery_run"] is False
    assert manifest["new_families_created"] is False
    assert manifest["new_variants_created"] is False
    assert manifest["hidden_parameter_grid_created"] is False
    assert manifest["threshold_tuning_added"] is False
    assert manifest["strategy_drawdown_guard_used"] is False
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
    assert manifest["paper_forward_activation"] is False
    assert manifest["new_paper_forward_candidate_created"] is False
    assert manifest["candidate_exhaustive_run"] is False
    assert manifest["best_single_variant_promoted"] is False
    assert manifest["research_outputs_remain_non_promotable"] is True
    assert manifest["outputs_promotable"] is False
    assert manifest["outputs_paper_forward_eligible"] is False
    assert manifest["outputs_candidate_exhaustive_ready"] is False
    assert manifest["active_vm_preserved"] is True
    assert manifest["active_dsr_preserved"] is True
    assert manifest["static_all_weather_benchmark_control_only"] is True
    assert manifest["commodity_continued"] is False
    assert manifest["macro_gld_continued"] is False
    assert manifest["volatility_throttle_threshold_tuning_continued"] is False
    assert manifest["managed_futures_reopened"] is False
    assert manifest["pre_fix_stale_weight_results_used"] is False
    assert manifest["next_action"] in VALID_NEXT_ACTIONS
    assert consistency["consistency_passed"] is True


def test_high_return_tactical_bounded_results_are_exact_design_rows() -> None:
    manifest = load_manifest()
    rows = pd.read_csv(EVIDENCE / "high_return_tactical_bounded_run_results.csv")

    assert len(rows) == EXPECTED_ROW_COUNT
    assert set(rows["variant_id"]) == APPROVED_VARIANT_IDS
    assert rows["lane_id"].eq(LANE_ID).all()
    assert rows["family_id"].eq(FAMILY_ID).all()
    assert rows["variant_role"].eq("risk_control_confirmation").all()
    assert rows["concept"].eq("realized_volatility_throttle_original_threshold").all()
    assert rows["source_mapping_status"].eq("source_mapping_verified").all()
    assert rows["data_availability_status"].eq("cache_ready").all()
    assert rows["source_variant_id"].str.startswith("vt_focus_orig_").all()
    assert rows["source_metric_mismatch_fields"].fillna("").eq("").all()
    assert rows["max_daily_exposure"].max() <= 1.000001
    assert rows["max_daily_weight_sum"].max() <= 1.000001
    assert rows["exposure_invariant_pass"].astype(str).str.lower().eq("true").all()
    assert rows["research_only_label"].isin(ALLOWED_LABELS).all()
    assert rows["promotion_eligibility"].astype(str).str.lower().eq("false").all()
    assert rows["paper_forward_eligibility"].astype(str).str.lower().eq("false").all()
    assert rows["candidate_exhaustive_eligibility"].astype(str).str.lower().eq("false").all()
    assert manifest["exposure_invariant_passed"] is True
    assert manifest["cash_bil_replacement_remainder_only"] is True


def test_high_return_tactical_bounded_required_artifacts_exist() -> None:
    required = [
        "high_return_tactical_bounded_run_manifest.json",
        "high_return_tactical_bounded_run_consistency_check.json",
        "high_return_tactical_bounded_run_results.csv",
        "high_return_tactical_bounded_numeric_criteria_results.csv",
        "source_mapping_verification_report.md",
        "data_alignment_effective_window_report.md",
        "baseline_comparator_report.md",
        "exposure_invariant_report.md",
        "high_return_tactical_bounded_label_summary.md",
        "high_return_tactical_bounded_run_summary.md",
        "high_return_tactical_bounded_run_next_action.md",
    ]
    for filename in required:
        assert (EVIDENCE / filename).exists(), filename

    criteria = pd.read_csv(EVIDENCE / "high_return_tactical_bounded_numeric_criteria_results.csv")
    expected_criteria = {
        "cagr_retention_vs_uncontrolled_baseline_pass",
        "source_original_retention_pass",
        "drawdown_reduction_pass",
        "calmar_improvement_pass",
        "bil_cash_usage_pass",
        "duplicate_reference_correlation_pass",
        "exposure_invariant_pass",
        "numeric_criteria_pass",
    }
    assert expected_criteria.issubset(criteria.columns)
    for column in expected_criteria:
        assert criteria[column].astype(str).str.lower().isin({"true", "false"}).all()
