from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = (
    ROOT
    / "evidence"
    / "research_recovery"
    / "next_registry_candidate_bounded_design_after_global_multi_asset"
    / "latest"
)


def load_manifest() -> dict:
    return json.loads((EVIDENCE / "next_registry_candidate_bounded_design_manifest.json").read_text(encoding="utf-8"))


def load_consistency() -> dict:
    return json.loads(
        (EVIDENCE / "next_registry_candidate_bounded_design_consistency_check.json").read_text(encoding="utf-8")
    )


def test_next_candidate_packet_records_tie_blocker() -> None:
    manifest = load_manifest()
    consistency = load_consistency()

    assert manifest["next_registry_candidate_bounded_design_after_global_multi_asset"] is True
    assert manifest["existing_triage_ranking_inspected"] is True
    assert manifest["global_multi_asset_left_failed_diagnostic"] is True
    assert manifest["global_multi_asset_audit_run"] is False
    assert manifest["global_multi_asset_continued_or_tuned"] is False
    assert manifest["bounded_design_created"] is False
    assert manifest["ambiguity_blocker_created"] is True
    assert manifest["selected_candidate"] == "none"
    assert manifest["selected_family"] == "none"
    assert manifest["eligible_after_exclusions_count"] == 5
    assert manifest["top_tie_found"] is True
    assert manifest["top_tie_count"] == 2
    assert set(manifest["top_tied_candidate_ids"]) == {
        "rim_regional_momentum_with_spy_gate_v1",
        "rim_regional_top2_momentum_bil_v1",
    }
    assert manifest["run_readiness_decision"] == "next_registry_candidate_bounded_design_blocked"
    assert manifest["run_readiness_blocker"] == "ambiguous_top_triage_score_tie"
    assert manifest["next_action"] == "resolve_next_registry_candidate_tie_before_bounded_design"
    assert consistency["consistency_passed"] is True


def test_guardrails_prevent_run_discovery_promotion_and_broker_paths() -> None:
    manifest = load_manifest()

    assert manifest["new_strategy_run"] is False
    assert manifest["new_backtests_run"] is False
    assert manifest["new_strategy_discovery_run"] is False
    assert manifest["new_research_batch_run"] is False
    assert manifest["new_families_created"] is False
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
    assert manifest["high_return_tactical_continued"] is False
    assert manifest["commodity_continued"] is False
    assert manifest["macro_gld_continued"] is False
    assert manifest["volatility_throttle_continued"] is False
    assert manifest["managed_futures_reopened"] is False
    assert manifest["crypto_continued"] is False
    assert manifest["regional_momentum_continued"] is False
    assert manifest["global_multi_asset_continued"] is False


def test_evidence_files_and_cache_table_exist() -> None:
    required = [
        "triage_ranking_after_exclusions.csv",
        "exclusions_applied.md",
        "candidate_selection_decision.md",
        "ambiguity_blocker.md",
        "source_lineage_assessment.md",
        "local_cache_availability.csv",
        "local_cache_availability.md",
        "planned_variant_design_table_not_created.md",
        "variant_roles_not_created.md",
        "baseline_comparator_policy_not_created.md",
        "numeric_success_failure_criteria_not_created.md",
        "guardrail_checklist.json",
        "exposure_invariant_requirements.md",
        "run_readiness_decision.md",
        "next_registry_candidate_bounded_design_next_action.md",
    ]
    for filename in required:
        assert (EVIDENCE / filename).exists(), filename

    cache = pd.read_csv(EVIDENCE / "local_cache_availability.csv")
    assert set(cache["strategy_id"]) == {
        "rim_regional_momentum_with_spy_gate_v1",
        "rim_regional_top2_momentum_bil_v1",
    }
    assert (cache["cache_status"] == "cache_ready").all()


def test_filtered_ranking_excludes_global_multi_asset_and_keeps_top_tie_visible() -> None:
    ranking = pd.read_csv(EVIDENCE / "triage_ranking_after_exclusions.csv")
    eligible = ranking[ranking["disposition_after_global_multi_asset_exclusion"] == "eligible_after_global_multi_asset_exclusion"]

    assert not (eligible["family"] == "global_multi_asset_etf_momentum").any()
    top_score = eligible["triage_score"].max()
    top = eligible[eligible["triage_score"] == top_score]
    assert set(top["strategy_id"]) == {
        "rim_regional_momentum_with_spy_gate_v1",
        "rim_regional_top2_momentum_bil_v1",
    }
