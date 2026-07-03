from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from strategy_lab.research_os.research.global_multi_asset_etf_momentum_bounded_design import (
    FAMILY_ID,
    LANE_ID,
    NEXT_ACTION_RUN,
    OUTPUT_DIR,
    REQUIRED_SYMBOLS,
    RUN_READY,
    SELECTED_STRATEGY_ID,
)


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / OUTPUT_DIR


def load_manifest() -> dict:
    return json.loads((EVIDENCE / "global_multi_asset_bounded_design_manifest.json").read_text(encoding="utf-8"))


def load_consistency() -> dict:
    return json.loads(
        (EVIDENCE / "global_multi_asset_bounded_design_consistency_check.json").read_text(encoding="utf-8")
    )


def test_global_multi_asset_design_guardrails() -> None:
    manifest = load_manifest()
    consistency = load_consistency()

    assert manifest["global_multi_asset_bounded_design_only"] is True
    assert manifest["lane_id"] == LANE_ID
    assert manifest["family_id"] == FAMILY_ID
    assert manifest["selected_strategy_id"] == SELECTED_STRATEGY_ID
    assert manifest["triage_evidence_reviewed"] is True
    assert manifest["registry_reviewed"] is True
    assert manifest["roadmap_reviewed"] is True
    assert manifest["queue_reviewed"] is True
    assert manifest["family_ledger_reviewed"] is True
    assert manifest["source_evidence_context_status"] == "older_exploratory_context_only"
    assert manifest["source_evidence_promotion_evidence"] is False
    assert manifest["source_evidence_candidate_exhaustive_ready"] is False
    assert manifest["triage_score_treated_as_strategy_success"] is False

    assert manifest["new_research_batch_run"] is False
    assert manifest["new_strategy_discovery_run"] is False
    assert manifest["new_backtests_run"] is False
    assert manifest["new_performance_metrics_from_raw_data_computed"] is False
    assert manifest["new_family_created"] is False
    assert manifest["new_variants_created"] is False
    assert manifest["hidden_parameter_grid_created"] is False
    assert manifest["global_multi_asset_lane_run"] is False
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
    assert manifest["high_return_tactical_continued"] is False
    assert manifest["commodity_continued"] is False
    assert manifest["macro_gld_continued"] is False
    assert manifest["volatility_throttle_continued"] is False
    assert manifest["managed_futures_reopened"] is False
    assert manifest["crypto_continued"] is False
    assert manifest["regional_momentum_continued"] is False
    assert consistency["consistency_passed"] is True


def test_local_cache_preflight_and_run_readiness() -> None:
    manifest = load_manifest()
    cache = pd.read_csv(EVIDENCE / "local_cache_availability.csv")

    assert set(manifest["required_symbols"]) == set(REQUIRED_SYMBOLS)
    assert set(manifest["local_cache_available_symbols"]) == set(REQUIRED_SYMBOLS)
    assert manifest["local_cache_missing_symbols"] == []
    assert manifest["local_cache_complete"] is True
    assert set(cache["symbol"]) == set(REQUIRED_SYMBOLS)
    assert cache["available"].astype(str).str.lower().eq("true").all()
    assert manifest["run_readiness_decision"] == RUN_READY
    assert manifest["run_readiness_blocker"] == "none"
    assert manifest["next_action"] == NEXT_ACTION_RUN


def test_planned_rows_are_bounded_and_source_centered() -> None:
    manifest = load_manifest()
    rows = pd.read_csv(EVIDENCE / "planned_variant_design_table.csv")

    assert manifest["planned_row_count"] == 6
    assert manifest["planned_row_count_between_6_and_10"] is True
    assert manifest["planned_row_count_lte_12"] is True
    assert len(rows) == 6
    assert rows["lane_id"].eq(LANE_ID).all()
    assert rows["family_id"].eq(FAMILY_ID).all()
    assert rows["variant_id"].is_unique
    assert "gma_bounded_selected_defensive_50_top2_126_v1" in set(rows["variant_id"])
    assert SELECTED_STRATEGY_ID in set(rows["source_registry_id"])
    assert rows["promotion_eligibility"].astype(str).str.lower().eq("false").all()
    assert rows["paper_forward_eligibility"].astype(str).str.lower().eq("false").all()
    assert rows["candidate_exhaustive_eligibility"].astype(str).str.lower().eq("false").all()
    assert rows["max_daily_exposure"].astype(float).le(1.0).all()
    assert rows["max_daily_weight_sum"].astype(float).le(1.0).all()
    assert any(rows["variant_role"].eq("selected_confirmation"))
    assert any(rows["variant_role"].eq("uncontrolled_source_baseline_context"))
    assert any(rows["variant_role"].eq("portfolio_contribution_context"))
    assert any(rows["variant_role"].eq("cash_control"))
    assert any(rows["variant_role"].eq("commodity_real_asset_control"))


def test_no_unapproved_assets_or_forbidden_continuations() -> None:
    rows = pd.read_csv(EVIDENCE / "planned_variant_design_table.csv")
    allowed = set(REQUIRED_SYMBOLS)
    used = {
        symbol
        for universe in rows["universe"].astype(str)
        for symbol in universe.split("|")
        if symbol
    }
    assert used.issubset(allowed)
    combined_text = " ".join(rows.astype(str).agg(" ".join, axis=1)).lower()
    assert "drawdown_guard" not in combined_text
    assert "managed_futures" not in combined_text
    assert "crypto" not in combined_text
    assert "high_return_tactical" not in combined_text
    assert "volatility_throttle" not in combined_text


def test_required_artifacts_and_numeric_policies_exist() -> None:
    required = [
        "global_multi_asset_bounded_design_manifest.json",
        "global_multi_asset_bounded_design_summary.md",
        "source_lineage_assessment.md",
        "local_cache_availability.csv",
        "local_cache_preflight.md",
        "eligibility_decision.md",
        "planned_variant_design_table.csv",
        "planned_variant_design_table.md",
        "variant_roles.md",
        "baseline_comparator_policy.md",
        "numeric_success_failure_criteria.md",
        "guardrail_checklist.json",
        "exposure_invariant_requirements.md",
        "rejected_closed_variant_exclusion_rule.md",
        "do_not_promote_from_global_multi_asset_design.md",
        "global_multi_asset_bounded_design_next_action.md",
        "global_multi_asset_bounded_design_consistency_check.json",
    ]
    for filename in required:
        assert (EVIDENCE / filename).exists(), filename

    criteria = (EVIDENCE / "numeric_success_failure_criteria.md").read_text(encoding="utf-8")
    exposure = (EVIDENCE / "exposure_invariant_requirements.md").read_text(encoding="utf-8")
    exclusion = (EVIDENCE / "rejected_closed_variant_exclusion_rule.md").read_text(encoding="utf-8")

    assert "Worst 180-day drawdown `>= -450.0000`" in criteria
    assert "180-day median final equity `>= 3250.0000`" in criteria
    assert "Daily equity return correlation to active combo `< 0.9000`" in criteria
    assert "Max daily exposure must be `<= 1.0`" in exposure
    assert "stale-forward-fill" in exposure
    assert "high-return tactical continuation" in exclusion
    assert "Macro/GLD continuation" in exclusion
