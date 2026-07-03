from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from strategy_lab.research_os.research.high_return_tactical_etf_equity_index_bounded_design import (
    FAMILY_ID,
    LANE_ID,
    OUTPUT_DIR,
    VALID_NEXT_ACTIONS,
)


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / OUTPUT_DIR


def load_manifest() -> dict:
    return json.loads((EVIDENCE / "high_return_tactical_bounded_design_manifest.json").read_text(encoding="utf-8"))


def load_consistency() -> dict:
    return json.loads((EVIDENCE / "high_return_tactical_bounded_design_consistency_check.json").read_text(encoding="utf-8"))


def test_high_return_tactical_bounded_design_guardrails() -> None:
    manifest = load_manifest()
    consistency = load_consistency()

    assert manifest["high_return_tactical_bounded_design_only"] is True
    assert manifest["lane_id"] == LANE_ID
    assert manifest["family_id"] == FAMILY_ID
    assert manifest["source_roadmap_registry_ledger_reviewed"] is True
    assert manifest["corrected_label_evidence_reviewed"] is True
    assert manifest["corrected_risk_control_evidence_reviewed"] is True
    assert manifest["pre_fix_stale_weight_results_used_as_evidence"] is False
    assert manifest["commodity_continued"] is False
    assert manifest["macro_gld_continued"] is False
    assert manifest["managed_futures_reopened"] is False
    assert manifest["new_research_batch_run"] is False
    assert manifest["new_strategy_discovery_run"] is False
    assert manifest["new_backtests_run"] is False
    assert manifest["new_performance_metrics_from_raw_data_computed"] is False
    assert manifest["new_family_created"] is False
    assert manifest["new_variants_created"] is False
    assert manifest["hidden_parameter_grid_created"] is False
    assert manifest["provider_download"] is False
    assert manifest["intraday_data_used"] is False
    assert manifest["leverage_allowed"] is False
    assert manifest["shorting_allowed"] is False
    assert manifest["options_allowed"] is False
    assert manifest["direct_futures_allowed"] is False
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
    assert manifest["active_vm_preserved"] is True
    assert manifest["active_dsr_preserved"] is True
    assert manifest["static_all_weather_benchmark_control_only"] is True
    assert manifest["next_action"] in VALID_NEXT_ACTIONS
    assert consistency["consistency_passed"] is True


def test_high_return_tactical_design_rows_are_small_and_frozen() -> None:
    manifest = load_manifest()
    rows = pd.read_csv(EVIDENCE / "planned_variant_design_table.csv")

    assert manifest["run_readiness_decision"] == "high_return_tactical_bounded_design_run_ready"
    assert manifest["planned_row_count"] == 6
    assert manifest["planned_row_count_between_6_and_12"] is True
    assert len(rows) == 6
    assert rows["family_id"].eq(FAMILY_ID).all()
    assert rows["lane_id"].eq(LANE_ID).all()
    assert rows["concept"].eq("realized_volatility_throttle_original_threshold").all()
    assert rows["volatility_window"].astype(int).eq(60).all()
    assert rows["normal_vol_threshold"].astype(float).eq(0.25).all()
    assert rows["high_vol_threshold"].astype(float).eq(0.35).all()
    assert rows["high_vol_multiplier"].astype(float).eq(0.50).all()
    assert rows["extreme_vol_multiplier"].astype(float).eq(0.25).all()
    assert rows["promotion_eligibility"].astype(str).str.lower().eq("false").all()
    assert rows["paper_forward_eligibility"].astype(str).str.lower().eq("false").all()
    assert rows["candidate_exhaustive_eligibility"].astype(str).str.lower().eq("false").all()
    assert not rows["variant_id"].str.contains("drawdown_guard", case=False).any()
    assert manifest["threshold_tuning_added"] is False
    assert manifest["threshold_set_count"] == 1


def test_high_return_tactical_required_artifacts_and_numeric_criteria() -> None:
    required = [
        "high_return_tactical_bounded_design_manifest.json",
        "high_return_tactical_bounded_design_summary.md",
        "source_evidence_review.md",
        "eligibility_decision.md",
        "planned_variant_design_table.csv",
        "planned_variant_design_table.md",
        "baseline_comparator_policy.md",
        "numeric_success_failure_criteria.md",
        "exposure_invariant_policy.md",
        "rejected_variant_exclusion.md",
        "guardrail_checklist.md",
        "do_not_promote_from_high_return_tactical_bounded_design.md",
        "high_return_tactical_bounded_design_next_action.md",
        "high_return_tactical_bounded_design_consistency_check.json",
    ]
    for filename in required:
        assert (EVIDENCE / filename).exists(), filename

    criteria = (EVIDENCE / "numeric_success_failure_criteria.md").read_text(encoding="utf-8")
    exclusion = (EVIDENCE / "rejected_variant_exclusion.md").read_text(encoding="utf-8")
    exposure = (EVIDENCE / "exposure_invariant_policy.md").read_text(encoding="utf-8")

    assert "CAGR retention versus uncontrolled baseline must be `>= 70%`" in criteria
    assert "Max drawdown reduction versus uncontrolled baseline must be `>= 25%`" in criteria
    assert "Average BIL/cash share must be `<= 35%`" in criteria
    assert "Duplicate/reference correlation must be `< 0.90`" in criteria
    assert "At least `2` related rows" in criteria
    assert "strategy_drawdown_guard" in exclusion
    assert "BIL/cash is replacement/remainder only" in exposure
    assert "stale-forward-fill" in exposure
