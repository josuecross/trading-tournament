from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from strategy_lab.research_os.research.volatility_throttle_focused_research_followup_results_audit import (
    AUDIT_DECISION_PASSED,
    LANE_ID,
    OUTPUT_DIR,
    VALID_NEXT_ACTIONS,
)


ROOT = Path(__file__).resolve().parents[1]


def output_dir() -> Path:
    return ROOT / OUTPUT_DIR


def load_manifest() -> dict:
    return json.loads(
        (output_dir() / "vol_throttle_followup_results_audit_manifest.json").read_text(encoding="utf-8")
    )


def load_consistency() -> dict:
    return json.loads(
        (output_dir() / "vol_throttle_followup_results_audit_consistency_check.json").read_text(encoding="utf-8")
    )


def test_results_audit_guardrails_and_decision() -> None:
    manifest = load_manifest()
    consistency = load_consistency()
    out = output_dir()

    assert manifest["vol_throttle_followup_results_audit_only"] is True
    assert manifest["lane_id_audited"] == LANE_ID
    assert manifest["source_run_evidence_reviewed"] is True
    assert manifest["source_design_evidence_reviewed"] is True
    assert manifest["optimized_loop_equivalence_checked"] is True
    assert manifest["approved_rows_replayed_for_audit_only"] is True
    assert manifest["approved_row_count_replayed"] == 18
    assert manifest["new_strategy_discovery_run"] is False
    assert manifest["new_research_batch_run"] is False
    assert manifest["new_variants_created"] is False
    assert manifest["new_families_created"] is False
    assert manifest["thresholds_changed"] is False
    assert manifest["provider_download"] is False
    assert manifest["intraday_data_used"] is False
    assert manifest["broker_api_called"] is False
    assert manifest["broker_orders_submitted"] is False
    assert manifest["broker_orders_cancelled"] is False
    assert manifest["broker_orders_reconciled"] is False
    assert manifest["live_orders"] is False
    assert manifest["real_money_recommendation"] is False
    assert manifest["paper_forward_activation"] is False
    assert manifest["new_paper_forward_candidate_created"] is False
    assert manifest["candidate_exhaustive_run"] is False
    assert manifest["promotion_candidates_created"] is False
    assert manifest["best_single_variant_promoted"] is False
    assert manifest["research_outputs_remain_non_promotable"] is True
    assert manifest["active_vm_preserved"] is True
    assert manifest["active_dsr_preserved"] is True
    assert manifest["macro_gld_lineage_recovery_run"] is False
    assert manifest["final_audit_decision"] == AUDIT_DECISION_PASSED
    assert manifest["next_action"] in VALID_NEXT_ACTIONS
    assert (out / "row_level_discrepancy_report.csv").exists()
    assert (out / "optimized_loop_equivalence_report.md").exists()
    assert (out / "criteria_recomputation_report.csv").exists()
    assert (out / "exposure_invariant_audit_report.md").exists()
    assert (out / "guardrail_audit_report.md").exists()
    assert consistency["consistency_passed"] is True


def test_results_audit_recomputed_counts_and_zero_discrepancies() -> None:
    manifest = load_manifest()
    discrepancies = pd.read_csv(output_dir() / "row_level_discrepancy_report.csv")
    criteria = pd.read_csv(output_dir() / "criteria_recomputation_report.csv")

    assert manifest["row_count_reviewed"] == 18
    assert manifest["row_level_discrepancy_count"] == 0
    assert manifest["metric_discrepancy_count"] == 0
    assert manifest["criteria_mismatch_count"] == 0
    assert manifest["label_mismatch_count"] == 0
    assert manifest["optimized_loop_equivalence_failure_count"] == 0
    assert manifest["stale_zero_weight_violation_count"] == 0
    assert discrepancies.empty
    assert len(criteria) == 18
    assert manifest["numeric_pass_count"] == 10
    assert manifest["numeric_fail_count"] == 8
    assert manifest["confirmation_pass_count"] == 6
    assert manifest["confirmation_row_count"] == 6
    assert manifest["robustness_pass_count"] == 4
    assert manifest["robustness_row_count"] == 12
    assert manifest["vol_throttle_signal_confirmed_count"] == 10
    assert manifest["vol_throttle_signal_threshold_sensitive_count"] == 3
    assert manifest["vol_throttle_signal_drawdown_reduction_below_threshold_count"] == 4
    assert manifest["vol_throttle_signal_weak_count"] == 1
    assert manifest["vol_throttle_signal_duplicate_reference_count"] == 0
    assert manifest["vol_throttle_signal_too_defensive_count"] == 0
    assert manifest["vol_throttle_signal_data_blocked_count"] == 0


def test_results_audit_integrity_sections_pass() -> None:
    manifest = load_manifest()

    assert manifest["run_manifest_consistency_passed"] is True
    assert manifest["evidence_completeness_passed"] is True
    assert manifest["design_to_run_consistency_passed"] is True
    assert manifest["methodology_integrity_passed"] is True
    assert manifest["guardrails_passed"] is True
    assert manifest["aggregate_counts_match"] is True
    assert manifest["exposure_invariant_passed"] is True
    assert manifest["max_abs_daily_return_delta"] <= 1e-12
    assert manifest["max_abs_weight_delta"] <= 1e-12
