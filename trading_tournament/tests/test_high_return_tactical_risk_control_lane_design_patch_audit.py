from __future__ import annotations

import json
from pathlib import Path

from strategy_lab.research_os.research.high_return_tactical_risk_control_lane_design_patch_audit import (
    LANE_ID,
    OUTPUT_DIR,
    VALID_NEXT_ACTIONS,
    run,
)


ROOT = Path(__file__).resolve().parents[1]


def load_manifest() -> dict:
    output = ROOT / OUTPUT_DIR
    return json.loads((output / "risk_control_lane_design_patch_audit_manifest.json").read_text(encoding="utf-8"))


def load_consistency() -> dict:
    output = ROOT / OUTPUT_DIR
    return json.loads((output / "risk_control_lane_design_patch_audit_consistency_check.json").read_text(encoding="utf-8"))


def test_patch_audit_guardrails_and_required_files() -> None:
    result = run(ROOT)
    output = Path(result["output_dir"])
    manifest = load_manifest()
    consistency = load_consistency()

    assert manifest["risk_control_lane_design_patch_audit_only"] is True
    assert manifest["lane_id_audited"] == LANE_ID
    assert manifest["source_patch_evidence_reviewed"] is True
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
    assert (output / "patched_variant_table_audit.md").exists()
    assert (output / "hidden_ambiguity_review.md").exists()
    assert (output / "baseline_mapping_audit.md").exists()
    assert (output / "patched_success_failure_criteria_audit.md").exists()
    assert (output / "run_readiness_decision.md").exists()
    assert manifest["next_action"] in VALID_NEXT_ACTIONS
    assert consistency["consistency_passed"] is True


def test_patch_audit_requires_another_design_fix() -> None:
    run(ROOT)
    manifest = load_manifest()

    assert manifest["variant_count_reviewed"] == 24
    assert manifest["variant_table_valid"] is True
    assert manifest["hidden_ambiguity_found"] is True
    assert manifest["volatility_input_explicit"] is False
    assert manifest["drawdown_guard_timing_explicit"] is False
    assert manifest["baseline_mapping_explicit"] is True
    assert manifest["success_failure_criteria_measurable"] is True
    assert manifest["duplication_overconservatism_risk_blocking"] is False
    assert manifest["run_readiness_decision"] == "patch_needs_another_design_fix"
    assert manifest["next_action"] == "patch_high_return_tactical_risk_control_lane_design_again"
