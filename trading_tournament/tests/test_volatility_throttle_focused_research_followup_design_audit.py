from __future__ import annotations

import json
from pathlib import Path

from strategy_lab.research_os.research.volatility_throttle_focused_research_followup_design_audit import (
    DECISION_RUN_READY,
    LANE_ID,
    NEXT_ACTION_RUN,
    OUTPUT_DIR,
    VALID_NEXT_ACTIONS,
    run,
)


ROOT = Path(__file__).resolve().parents[1]


def output_dir() -> Path:
    return ROOT / OUTPUT_DIR


def load_manifest() -> dict:
    return json.loads((output_dir() / "vol_throttle_followup_design_audit_manifest.json").read_text(encoding="utf-8"))


def load_consistency() -> dict:
    return json.loads((output_dir() / "vol_throttle_followup_design_audit_consistency_check.json").read_text(encoding="utf-8"))


def test_volatility_throttle_followup_design_audit_guardrails_and_files() -> None:
    result = run(ROOT)
    manifest = load_manifest()
    consistency = load_consistency()
    output = Path(result["output_dir"])

    assert manifest["vol_throttle_followup_design_audit_only"] is True
    assert manifest["lane_id_audited"] == LANE_ID
    assert manifest["source_design_evidence_reviewed"] is True
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
    assert (output / "variant_role_audit.md").exists()
    assert (output / "threshold_set_audit.md").exists()
    assert (output / "volatility_rule_audit.md").exists()
    assert (output / "baseline_comparator_audit.md").exists()
    assert (output / "success_failure_criteria_audit.md").exists()
    assert (output / "run_readiness_decision.md").exists()
    assert manifest["next_action"] in VALID_NEXT_ACTIONS
    assert consistency["consistency_passed"] is True


def test_numeric_criteria_allow_run_ready_decision() -> None:
    run(ROOT)
    manifest = load_manifest()

    assert manifest["planned_variant_count_reviewed"] == 18
    assert manifest["confirmation_reference_rows_count"] == 6
    assert manifest["new_robustness_rows_count"] == 12
    assert manifest["threshold_set_count"] == 3
    assert manifest["variant_roles_unambiguous"] is True
    assert manifest["thresholds_explicit"] is True
    assert manifest["volatility_rules_explicit"] is True
    assert manifest["baseline_comparator_policy_explicit"] is True
    assert manifest["vague_criteria_found"] is False
    assert manifest["success_failure_criteria_measurable"] is True
    assert manifest["run_readiness_decision"] == DECISION_RUN_READY
    assert manifest["next_action"] == NEXT_ACTION_RUN
