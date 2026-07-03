from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "research_recovery" / "macro_gld_duration_risk_off_bounded_design" / "latest"
MANIFEST = EVIDENCE / "macro_gld_bounded_design_manifest.json"
CONSISTENCY = EVIDENCE / "macro_gld_bounded_design_consistency_check.json"

VALID_NEXT_ACTIONS = {
    "run_macro_gld_duration_risk_off_bounded_research_lane",
    "macro_gld_bounded_design_blocked",
}

REJECTED_OR_CONTEXT_VARIANTS = {
    "gld_gror_balanced_momentum_clean_v1",
    "gld_ief_spy_defensive_rotation_v1",
    "gror_balanced_momentum_60_40_v1",
    "mgd_macro_mom63_top1_trend",
    "mgd_macro_mom63_top2_trend",
    "mgd_macro_mom126_top1_trend",
    "mgd_macro_mom126_top2_trend",
    "mgd_macro_mom252_top1_trend",
    "mgd_macro_mom252_top2_trend",
    "mgd_static_spy_gld_tlt_60_20_20",
    "mgd_static_gld_tlt_bil_equal",
    "mgd_static_gld_ief_bil_equal",
    "mgd_static_gld_spy_bil_equal",
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_design_manifest_guardrails() -> None:
    manifest = load_json(MANIFEST)

    assert manifest["macro_gld_bounded_design_only"] is True
    assert manifest["lane_id"] == "macro_gld_duration_risk_off_bounded_lane_v1"
    assert manifest["source_family"] == "macro_gld_duration_risk_off"
    assert manifest["source_task"] == "recover_gld_macro_family_lineage"
    assert manifest["lineage_recovery_evidence_reviewed"] is True
    assert manifest["selection_from_existing_roadmap_registry_only"] is True

    assert manifest["new_research_lane_run"] is False
    assert manifest["new_research_batch_run"] is False
    assert manifest["new_strategy_discovery_run"] is False
    assert manifest["new_backtests_run"] is False
    assert manifest["new_performance_metrics_from_raw_data_computed"] is False
    assert manifest["new_variants_created_for_execution"] is False
    assert manifest["new_family_created"] is False
    assert manifest["hidden_parameter_grid_created"] is False
    assert manifest["provider_download"] is False
    assert manifest["intraday_data_used"] is False
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
    assert manifest["exact_rejected_variants_reopened"] is False
    assert manifest["alpaca_execution_module_delegated"] is True


def test_planned_design_rows_are_bounded_and_non_promotable() -> None:
    manifest = load_json(MANIFEST)
    rows = load_csv(EVIDENCE / "planned_variant_design_table.csv")
    variant_ids = {row["variant_id"] for row in rows}

    assert manifest["planned_variant_count"] == 8
    assert manifest["planned_variant_count_between_6_and_12"] is True
    assert 6 <= len(rows) <= 12
    assert len(variant_ids) == len(rows)
    assert not (variant_ids & REJECTED_OR_CONTEXT_VARIANTS)
    assert {row["family_id"] for row in rows} == {"macro_gld_duration_risk_off"}
    assert all(row["promotion_eligibility"] == "False" for row in rows)
    assert all(row["paper_forward_eligibility"] == "False" for row in rows)
    assert all(row["candidate_exhaustive_eligibility"] == "False" for row in rows)
    assert all(row["static_all_weather_role"] == "benchmark_control_only_not_candidate" for row in rows)
    assert all(float(row["max_daily_exposure"]) <= 1.0 for row in rows)
    assert all(float(row["max_daily_weight_sum"]) <= 1.0 for row in rows)


def test_required_design_evidence_and_readiness() -> None:
    manifest = load_json(MANIFEST)
    consistency = load_json(CONSISTENCY)

    required = [
        "macro_gld_bounded_design_manifest.json",
        "macro_gld_bounded_design_summary.md",
        "source_lineage_context_review.md",
        "planned_variant_design_table.csv",
        "planned_variant_design_table.md",
        "variant_role_definitions.md",
        "frozen_rule_summaries.md",
        "baseline_comparator_policy.md",
        "numeric_success_failure_criteria.md",
        "guardrail_checklist.md",
        "exposure_invariant_requirements.md",
        "historical_lineage_context_summary.md",
        "rejected_variant_exclusion_policy.md",
        "run_readiness_decision.md",
        "do_not_promote_from_macro_gld_design.md",
        "macro_gld_bounded_design_next_action.md",
        "macro_gld_bounded_design_consistency_check.json",
    ]
    for filename in required:
        assert (EVIDENCE / filename).exists(), filename

    criteria = (EVIDENCE / "numeric_success_failure_criteria.md").read_text(encoding="utf-8")
    invariants = (EVIDENCE / "exposure_invariant_requirements.md").read_text(encoding="utf-8")

    assert "CAGR `>= 0.0600`" in criteria
    assert "Max drawdown `>= -0.3000`" in criteria
    assert "Average BIL/cash share `<= 0.5500`" in criteria
    assert "Max daily exposure must be `<= 1.0`" in invariants
    assert "Zero target weights must remain zero" in invariants
    assert "stale-forward-filled" in invariants

    assert manifest["run_readiness_decision"] == "macro_gld_bounded_design_run_ready"
    assert manifest["next_action"] in VALID_NEXT_ACTIONS
    assert manifest["next_action"] == "run_macro_gld_duration_risk_off_bounded_research_lane"
    assert consistency["consistency_passed"] is True
