from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from strategy_lab.research_os.research.volatility_throttle_focused_research_followup_run import (
    EXPECTED_ROLE_COUNTS,
    EXPECTED_THRESHOLD_SETS,
    LANE_ID,
    OUTPUT_DIR,
    VALID_NEXT_ACTIONS,
    volatility_multiplier_for_thresholds,
)


ROOT = Path(__file__).resolve().parents[1]


def output_dir() -> Path:
    return ROOT / OUTPUT_DIR


def load_manifest() -> dict:
    return json.loads((output_dir() / "vol_throttle_followup_run_manifest.json").read_text(encoding="utf-8"))


def load_consistency() -> dict:
    return json.loads((output_dir() / "vol_throttle_followup_run_consistency_check.json").read_text(encoding="utf-8"))


def test_volatility_throttle_followup_run_guardrails_and_counts() -> None:
    manifest = load_manifest()
    consistency = load_consistency()
    out = output_dir()

    assert manifest["volatility_throttle_followup_run"] is True
    assert manifest["lane_id"] == LANE_ID
    assert manifest["source_design_audit_run_ready"] is True
    assert manifest["row_count"] == 18
    assert manifest["role_counts"] == EXPECTED_ROLE_COUNTS
    assert set(manifest["threshold_set_counts"]) == EXPECTED_THRESHOLD_SETS
    assert manifest["threshold_set_count"] == 3
    assert manifest["data_source_used"] == "local_cache_only"
    assert manifest["uses_local_cache_only"] is True
    assert manifest["provider_download"] is False
    assert manifest["intraday_data_used"] is False
    assert manifest["broker_api_called"] is False
    assert manifest["broker_orders_submitted"] is False
    assert manifest["broker_orders_cancelled"] is False
    assert manifest["broker_orders_reconciled"] is False
    assert manifest["broker_paper_live_path_touched"] is False
    assert manifest["live_orders"] is False
    assert manifest["real_money_recommendation"] is False
    assert manifest["new_family_created"] is False
    assert manifest["new_families_created"] is False
    assert manifest["new_unrelated_variant_created"] is False
    assert manifest["new_variants_created"] is False
    assert manifest["new_strategy_discovery_run"] is False
    assert manifest["promotion_candidates_created"] is False
    assert manifest["candidate_exhaustive_run"] is False
    assert manifest["paper_forward_activation"] is False
    assert manifest["new_paper_forward_candidate_created"] is False
    assert manifest["best_single_variant_promoted"] is False
    assert manifest["research_outputs_remain_non_promotable"] is True
    assert manifest["active_vm_preserved"] is True
    assert manifest["active_dsr_preserved"] is True
    assert manifest["static_all_weather_benchmark_control_only"] is True
    assert manifest["macro_gld_lineage_recovery_run"] is False
    assert manifest["alpaca_execution_module_delegated"] is True
    assert (out / "vol_throttle_followup_results.csv").exists()
    assert (out / "vol_throttle_followup_numeric_criteria_results.csv").exists()
    assert (out / "do_not_promote_from_vol_throttle_followup_run.md").exists()
    assert manifest["next_action"] in VALID_NEXT_ACTIONS
    assert consistency["consistency_passed"] is True


def test_volatility_throttle_followup_results_are_bounded_and_non_promotable() -> None:
    manifest = load_manifest()
    results = pd.read_csv(output_dir() / "vol_throttle_followup_results.csv")

    assert len(results) == 18
    assert results["variant_role"].value_counts().to_dict() == EXPECTED_ROLE_COUNTS
    assert set(results["threshold_set_id"].unique()) == EXPECTED_THRESHOLD_SETS
    assert manifest["max_daily_exposure"] <= 1.000001
    assert manifest["max_daily_weight_sum"] <= 1.000001
    assert manifest["exposure_invariant_passed"] is True
    assert (results["max_daily_exposure"] <= 1.000001).all()
    assert (results["max_daily_weight_sum"] <= 1.000001).all()
    assert (results["promotion_eligibility"].astype(str).str.lower() == "false").all()
    assert (results["paper_forward_eligibility"].astype(str).str.lower() == "false").all()
    assert results["vol_throttle_research_label"].isin(
        {
            "vol_throttle_signal_confirmed",
            "vol_throttle_signal_threshold_sensitive",
            "vol_throttle_signal_too_defensive",
            "vol_throttle_signal_drawdown_reduction_below_threshold",
            "vol_throttle_signal_duplicate_reference",
            "vol_throttle_signal_weak",
            "vol_throttle_signal_data_blocked",
        }
    ).all()


def test_numeric_criteria_columns_exist_and_are_boolean_like() -> None:
    criteria = pd.read_csv(output_dir() / "vol_throttle_followup_numeric_criteria_results.csv")
    required = {
        "cagr_retention_vs_comparator_pass",
        "source_original_retention_pass",
        "drawdown_reduction_pass",
        "calmar_improvement_pass",
        "bil_cash_usage_pass",
        "duplicate_correlation_pass",
        "exposure_invariant_pass",
        "numeric_criteria_pass",
        "related_group_confirmation_pass",
    }

    assert required.issubset(criteria.columns)
    for column in required:
        assert criteria[column].astype(str).str.lower().isin({"true", "false"}).all()


def test_volatility_threshold_function_preserves_approved_sets() -> None:
    kwargs = {
        "normal_threshold": 0.25,
        "high_threshold": 0.35,
        "normal_multiplier": 1.0,
        "high_vol_multiplier": 0.5,
        "extreme_vol_multiplier": 0.25,
    }

    assert volatility_multiplier_for_thresholds(float("nan"), enough_history=False, **kwargs) == 1.0
    assert volatility_multiplier_for_thresholds(0.25, enough_history=True, **kwargs) == 1.0
    assert volatility_multiplier_for_thresholds(0.30, enough_history=True, **kwargs) == 0.5
    assert volatility_multiplier_for_thresholds(0.36, enough_history=True, **kwargs) == 0.25
