from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "research_recovery" / "macro_gld_duration_risk_off_confirmation_report" / "latest"

SURVIVOR_IDS = {
    "mgd_bounded_canary_defensive_top1_126_v1",
    "mgd_bounded_canary_defensive_top2_126_v1",
    "mgd_bounded_canary_defensive_top2_252_v1",
    "mgd_bounded_barbell_gated_126_v1",
}

EXCLUDED_CONTEXT_IDS = {
    "mgd_bounded_canary_defensive_top1_252_v1",
    "mgd_bounded_gold_duration_sleeve_top1_126_v1",
    "mgd_bounded_gold_duration_sleeve_top1_252_v1",
    "mgd_bounded_barbell_gated_252_v1",
}


def load_manifest() -> dict:
    return json.loads((EVIDENCE / "macro_gld_confirmation_manifest.json").read_text(encoding="utf-8"))


def load_consistency() -> dict:
    return json.loads((EVIDENCE / "macro_gld_confirmation_consistency_check.json").read_text(encoding="utf-8"))


def test_confirmation_guardrails_and_outputs() -> None:
    manifest = load_manifest()
    consistency = load_consistency()

    assert manifest["macro_gld_confirmation_report"] is True
    assert manifest["lane_id"] == "macro_gld_duration_risk_off_bounded_lane_v1"
    assert manifest["family_id"] == "macro_gld_duration_risk_off"
    assert manifest["source_robustness_reviewed"] is True
    assert manifest["exact_survivor_rows_used"] is True
    assert manifest["excluded_context_rows_not_reopened"] is True
    assert manifest["rows_evaluated"] == 4
    assert manifest["new_strategy_discovery_run"] is False
    assert manifest["new_research_batch_run"] is False
    assert manifest["new_families_created"] is False
    assert manifest["new_rows_added"] is False
    assert manifest["new_concepts_added"] is False
    assert manifest["new_lookbacks_added"] is False
    assert manifest["new_universes_added"] is False
    assert manifest["hidden_parameter_grid_created"] is False
    assert manifest["uses_local_cache_only"] is True
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
    assert manifest["research_outputs_remain_non_promotable"] is True
    assert manifest["active_vm_preserved"] is True
    assert manifest["active_dsr_preserved"] is True
    assert manifest["static_all_weather_benchmark_control_only"] is True
    assert manifest["exact_rejected_variants_reopened"] is False
    assert manifest["rows_with_invariant_failures"] == 0
    assert consistency["consistency_passed"] is True

    for filename in [
        "survivor_confirmation_rows.csv",
        "comparator_contribution_diagnostic.md",
        "baseline_comparator_report.md",
        "subperiod_confirmation.csv",
        "rolling_weakness_confirmation.csv",
        "exposure_invariant_report.md",
        "macro_gld_confirmation_summary.md",
        "do_not_promote_from_macro_gld_confirmation.md",
    ]:
        assert (EVIDENCE / filename).exists(), filename


def test_exact_survivor_rows_and_no_promotion() -> None:
    rows = pd.read_csv(EVIDENCE / "survivor_confirmation_rows.csv")
    ids = set(rows["variant_id"])

    assert ids == SURVIVOR_IDS
    assert not (ids & EXCLUDED_CONTEXT_IDS)
    assert (rows["promotion_eligibility"].astype(str).str.lower() == "false").all()
    assert (rows["paper_forward_eligibility"].astype(str).str.lower() == "false").all()
    assert (rows["candidate_exhaustive_eligibility"].astype(str).str.lower() == "false").all()
    assert set(rows["confirmation_label"]).issubset(
        {
            "macro_gld_confirmation_candidate_diagnostic",
            "macro_gld_confirmation_context_only",
        }
    )


def test_confirmation_metrics_cover_cost_subperiod_rolling_and_contribution() -> None:
    manifest = load_manifest()
    rows = pd.read_csv(EVIDENCE / "survivor_confirmation_rows.csv")
    subperiod = pd.read_csv(EVIDENCE / "subperiod_confirmation.csv")
    rolling = pd.read_csv(EVIDENCE / "rolling_weakness_confirmation.csv")

    assert manifest["rows_passing_base_criteria"] == 4
    assert manifest["rows_passing_10bps_stress"] == 4
    assert manifest["rows_passing_25bps_stress"] == 4
    assert len(subperiod) == 12
    assert set(subperiod["variant_id"]) == SURVIVOR_IDS
    assert len(rolling) == 4
    assert set(rolling["variant_id"]) == SURVIVOR_IDS
    for column in [
        "comparator_references",
        "cagr",
        "total_return",
        "max_drawdown",
        "volatility",
        "calmar_or_return_drawdown_proxy",
        "same_window_return_vs_bil",
        "average_bil_cash_share",
        "correlation_to_spy200d",
        "correlation_to_static_all_weather",
        "correlation_to_active_combo",
        "active_vm_dsr_combo_max_drawdown_improvement",
        "active_vm_dsr_combo_total_return_drag",
    ]:
        assert column in rows.columns
    assert "active_combo_drawdown_overlap_ratio" in rows.columns
    assert "portfolio_contribution_classification" in rows.columns
    assert manifest["confirmation_evidence_usable"] is True
    assert manifest["next_action"] in {
        "return_to_profit_oriented_research_queue",
        "fix_macro_gld_duration_risk_off_confirmation_report_issue",
    }
