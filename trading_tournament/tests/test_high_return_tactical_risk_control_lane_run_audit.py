from __future__ import annotations

import json
from pathlib import Path

from strategy_lab.research_os.research.high_return_tactical_risk_control_lane_run_audit import (
    LANE_ID,
    OUTPUT_DIR,
    VALID_NEXT_ACTIONS,
    run,
)


ROOT = Path(__file__).resolve().parents[1]


def output_dir() -> Path:
    return ROOT / OUTPUT_DIR


def load_manifest() -> dict:
    return json.loads((output_dir() / "risk_control_lane_run_audit_manifest.json").read_text(encoding="utf-8"))


def load_consistency() -> dict:
    return json.loads((output_dir() / "risk_control_lane_run_audit_consistency_check.json").read_text(encoding="utf-8"))


def test_risk_control_lane_run_audit_guardrails_and_required_files() -> None:
    result = run(ROOT)
    manifest = load_manifest()
    consistency = load_consistency()
    output = Path(result["output_dir"])

    assert manifest["risk_control_lane_run_audit_only"] is True
    assert manifest["lane_id_audited"] == LANE_ID
    assert manifest["source_run_evidence_reviewed"] is True
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
    assert (output / "methodology_invariant_audit.md").exists()
    assert (output / "label_audit.md").exists()
    assert (output / "concept_level_audit.md").exists()
    assert (output / "next_research_direction_decision.md").exists()
    assert (output / "non_promotable_guardrail_review.md").exists()
    assert manifest["next_action"] in VALID_NEXT_ACTIONS
    assert consistency["consistency_passed"] is True


def test_risk_control_lane_run_audit_decision_fields() -> None:
    run(ROOT)
    manifest = load_manifest()

    assert manifest["variant_count_reviewed"] == 24
    assert manifest["methodology_invariants_valid"] is True
    assert manifest["labels_valid"] is True
    assert manifest["volatility_throttle_promising"] is True
    assert manifest["regime_plus_volatility_promising"] is True
    assert manifest["spy200d_duplicate_or_reference_like"] is True
    assert manifest["drawdown_guard_return_destroyed"] is True
    assert manifest["accepted_next_research_direction_count"] == 1
