from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "research_recovery" / "regional_international_momentum_bounded_design" / "latest"


def load_manifest() -> dict:
    return json.loads((EVIDENCE / "regional_international_momentum_bounded_design_manifest.json").read_text(encoding="utf-8"))


def load_consistency() -> dict:
    return json.loads(
        (EVIDENCE / "regional_international_momentum_bounded_design_consistency_check.json").read_text(
            encoding="utf-8"
        )
    )


def test_regional_design_is_co_seeded_and_run_ready() -> None:
    manifest = load_manifest()
    consistency = load_consistency()

    assert manifest["regional_international_momentum_bounded_design_only"] is True
    assert manifest["lane_id"] == "regional_international_momentum_bounded_lane_v1"
    assert manifest["family_id"] == "regional_international_momentum"
    assert manifest["tie_resolution_evidence_reviewed"] is True
    assert manifest["tie_resolution_method"] == "co_seeded_family_design_using_both_tied_candidates"
    assert set(manifest["co_seed_source_candidate_ids"]) == {
        "rim_regional_momentum_with_spy_gate_v1",
        "rim_regional_top2_momentum_bil_v1",
    }
    assert manifest["source_lineage_verified"] is True
    assert manifest["source_evidence_context_only"] is True
    assert manifest["source_evidence_promotion_evidence"] is False
    assert manifest["local_cache_complete"] is True
    assert manifest["local_cache_missing_symbols"] == []
    assert manifest["planned_row_count"] == 7
    assert manifest["planned_row_count_between_6_and_8"] is True
    assert manifest["planned_row_count_lte_10"] is True
    assert manifest["source_context_row_count"] == 2
    assert manifest["risk_control_row_count"] == 2
    assert manifest["control_row_count"] == 3
    assert manifest["run_readiness_decision"] == "regional_international_momentum_bounded_design_run_ready"
    assert manifest["run_readiness_blocker"] == "none"
    assert manifest["next_action"] == "run_regional_international_momentum_bounded_lane"
    assert consistency["consistency_passed"] is True


def test_regional_design_guardrails_hold() -> None:
    manifest = load_manifest()

    assert manifest["regional_lane_run"] is False
    assert manifest["strategy_discovery_run"] is False
    assert manifest["new_research_batch_run"] is False
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
    assert manifest["forex_allowed"] is False
    assert manifest["margin_allowed"] is False
    assert manifest["candidate_exhaustive_run"] is False
    assert manifest["promotion_candidates_created"] is False
    assert manifest["best_single_variant_promoted"] is False
    assert manifest["paper_forward_activation"] is False
    assert manifest["new_paper_forward_candidate_created"] is False
    assert manifest["broker_api_called"] is False
    assert manifest["broker_orders_submitted"] is False
    assert manifest["broker_orders_cancelled"] is False
    assert manifest["broker_orders_reconciled"] is False
    assert manifest["live_orders"] is False
    assert manifest["real_money_recommendation"] is False
    assert manifest["active_vm_preserved"] is True
    assert manifest["active_dsr_preserved"] is True
    assert manifest["static_all_weather_benchmark_control_only"] is True
    assert manifest["global_multi_asset_continued"] is False
    assert manifest["high_return_tactical_continued"] is False
    assert manifest["commodity_continued"] is False
    assert manifest["macro_gld_continued"] is False
    assert manifest["volatility_throttle_continued"] is False
    assert manifest["managed_futures_reopened"] is False
    assert manifest["crypto_continued"] is False


def test_regional_design_rows_are_bounded_and_non_promotable() -> None:
    rows = pd.read_csv(EVIDENCE / "planned_variant_design_table.csv")

    assert len(rows) == 7
    assert set(rows["variant_id"]) == {
        "rim_bounded_source_spy_gate_top2_126_v1",
        "rim_bounded_source_top2_bil_126_v1",
        "rim_bounded_spy_gate_top2_half_bil_126_v1",
        "rim_bounded_top2_half_bil_126_v1",
        "rim_bounded_spy200d_control_v1",
        "rim_bounded_bil_cash_control_v1",
        "rim_bounded_efa_eem_equal_weight_control_v1",
    }
    assert set(rows["source_registry_id"]).issuperset(
        {"rim_regional_momentum_with_spy_gate_v1", "rim_regional_top2_momentum_bil_v1"}
    )
    assert (rows["promotion_eligibility"].astype(str).str.lower() == "false").all()
    assert (rows["paper_forward_eligibility"].astype(str).str.lower() == "false").all()
    assert (rows["candidate_exhaustive_eligibility"].astype(str).str.lower() == "false").all()
    assert rows["max_daily_exposure"].max() <= 1.0
    assert rows["max_daily_weight_sum"].max() <= 1.0
    forbidden_assets = {"BTC", "ETH", "GLD", "DBC", "PDBC", "COMT", "GSG", "USCI", "DBMF", "KMLM"}
    used_assets = set()
    for universe in rows["universe"]:
        used_assets.update(str(universe).split("|"))
    assert forbidden_assets.isdisjoint(used_assets)
    assert used_assets.issubset({"SPY", "EWJ", "EWU", "EWG", "EWY", "INDA", "EFA", "EEM", "BIL"})


def test_source_lineage_and_cache_files_exist() -> None:
    for filename in [
        "tie_resolution_co_seeded_design.md",
        "source_lineage_assessment.md",
        "local_cache_preflight.md",
        "eligibility_decision.md",
        "variant_roles.md",
        "baseline_comparator_policy.md",
        "numeric_success_failure_criteria.md",
        "guardrail_checklist.json",
        "exposure_invariant_requirements.md",
        "rejected_closed_variant_exclusion_rule.md",
        "run_readiness_decision.md",
        "regional_international_momentum_bounded_design_next_action.md",
    ]:
        assert (EVIDENCE / filename).exists(), filename

    lineage = pd.read_csv(EVIDENCE / "source_lineage_assessment.csv")
    cache = pd.read_csv(EVIDENCE / "local_cache_availability.csv")

    assert set(lineage["source_registry_id"]) == {
        "rim_regional_momentum_with_spy_gate_v1",
        "rim_regional_top2_momentum_bil_v1",
    }
    assert (lineage["source_row_found"].astype(str).str.lower() == "true").all()
    assert (lineage["registry_entry_found"].astype(str).str.lower() == "true").all()
    assert (lineage["source_decision"] == "too_risky").all()
    assert set(cache["symbol"]) == {"SPY", "EWJ", "EWU", "EWG", "EWY", "INDA", "EFA", "EEM", "BIL"}
    assert (cache["available"].astype(str).str.lower() == "true").all()
