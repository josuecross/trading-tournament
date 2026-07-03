from __future__ import annotations

import csv
import json
from pathlib import Path

from strategy_lab.research_os.research.high_return_tactical_risk_control_lane_design_patch_v2 import (
    LANE_ID,
    OUTPUT_DIR,
    VALID_NEXT_ACTIONS,
    run,
)


ROOT = Path(__file__).resolve().parents[1]


def load_manifest() -> dict:
    output = ROOT / OUTPUT_DIR
    return json.loads((output / "risk_control_lane_design_patch_v2_manifest.json").read_text(encoding="utf-8"))


def load_consistency() -> dict:
    output = ROOT / OUTPUT_DIR
    return json.loads((output / "risk_control_lane_design_patch_v2_consistency_check.json").read_text(encoding="utf-8"))


def load_variants() -> list[dict[str, str]]:
    output = ROOT / OUTPUT_DIR
    with (output / "patched_v2_variant_design_table.csv").open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def load_baselines() -> list[dict[str, str]]:
    output = ROOT / OUTPUT_DIR
    with (output / "baseline_mapping_table.csv").open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_patch_v2_guardrails_and_required_files() -> None:
    result = run(ROOT)
    output = Path(result["output_dir"])
    manifest = load_manifest()
    consistency = load_consistency()

    assert manifest["risk_control_lane_design_patch_v2_only"] is True
    assert manifest["lane_id"] == LANE_ID
    assert manifest["source_patch_audit_reviewed"] is True
    assert manifest["new_research_batch_run"] is False
    assert manifest["new_strategy_discovery_run"] is False
    assert manifest["new_backtests_run"] is False
    assert manifest["new_performance_metrics_from_raw_data_computed"] is False
    assert manifest["new_variants_created"] is False
    assert manifest["new_families_created"] is False
    assert manifest["provider_download"] is False
    assert manifest["intraday_data_used"] is False
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
    assert manifest["active_vm_preserved"] is True
    assert manifest["active_dsr_preserved"] is True
    assert manifest["static_all_weather_benchmark_control_only"] is True
    assert manifest["macro_gld_lineage_recovery_run"] is False
    assert manifest["alpaca_execution_module_delegated"] is True
    assert manifest["variant_count_planned"] <= 24
    assert manifest["volatility_input_explicit_after_patch_v2"] is True
    assert manifest["drawdown_guard_timing_explicit_after_patch_v2"] is True
    assert manifest["controlled_equity_tracking_explicit"] is True
    assert manifest["combined_rule_precedence_explicit_after_patch_v2"] is True
    assert (output / "baseline_mapping_table.csv").exists()
    assert manifest["baseline_mapping_missing_count"] == 0 or manifest["next_action"] != "audit_high_return_tactical_risk_control_lane_design_patch_v2"
    assert manifest["all_variant_rules_explicit_after_patch_v2"] is True
    assert manifest["thresholds_explicit_after_patch_v2"] is True
    assert manifest["fallback_rules_explicit_after_patch_v2"] is True
    assert manifest["reentry_rules_explicit_after_patch_v2"] is True
    assert manifest["success_failure_criteria_measurable_after_patch_v2"] is True
    assert manifest["max_exposure_allowed"] <= 1.0
    assert manifest["leverage_allowed"] is False
    assert manifest["shorting_allowed"] is False
    assert manifest["options_allowed"] is False
    assert manifest["direct_futures_allowed"] is False
    assert (output / "remaining_ambiguity_review.md").exists()
    assert manifest["next_action"] in VALID_NEXT_ACTIONS
    assert consistency["consistency_passed"] is True


def test_patch_v2_baseline_mapping_and_variant_fields() -> None:
    run(ROOT)
    manifest = load_manifest()
    variants = load_variants()
    baselines = load_baselines()
    required_fields = {
        "baseline_variant_id",
        "baseline_family",
        "baseline_universe_group",
        "baseline_universe",
        "baseline_lookback",
        "baseline_top_n",
        "baseline_rebalance_frequency",
        "baseline_corrected_methodology_source",
        "baseline_corrected_label_source",
        "same_window_baseline_comparison_required",
    }

    assert len(variants) == 24
    assert manifest["variant_count_changed"] is False
    assert required_fields.issubset(set(variants[0].keys()))
    assert len(baselines) == 24
    assert manifest["baseline_mapping_complete_count"] == 24
    assert manifest["baseline_mapping_missing_count"] == 0
    assert manifest["baseline_mapping_explicit_after_patch_v2"] is True
    assert all(row["baseline_mapping_status"] == "baseline_mapping_complete" for row in baselines)
    assert all(row["baseline_found_in_methodology_source"] == "True" for row in baselines)
    assert all(row["baseline_found_in_label_source"] == "True" for row in baselines)
    assert all(row["same_window_baseline_comparison_required"] == "True" for row in variants)
    assert all(row["promotion_eligible"] == "False" for row in variants)
    assert all(row["paper_forward_eligible"] == "False" for row in variants)
