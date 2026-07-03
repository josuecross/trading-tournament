from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from strategy_lab.research_os.research.profit_oriented_registry_research_sample_triage import (
    NEXT_ACTION_SHORTLIST,
    OUTPUT_DIR,
)


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / OUTPUT_DIR


def load_manifest() -> dict:
    return json.loads((EVIDENCE / "triage_manifest.json").read_text(encoding="utf-8"))


def load_consistency() -> dict:
    return json.loads((EVIDENCE / "triage_consistency_check.json").read_text(encoding="utf-8"))


def test_registry_triage_guardrails() -> None:
    manifest = load_manifest()
    guardrails = json.loads((EVIDENCE / "guardrail_checklist.json").read_text(encoding="utf-8"))

    assert manifest["registry_research_sample_triage_only"] is True
    assert manifest["existing_saved_evidence_metrics_read"] is True
    assert manifest["new_research_batch_run"] is False
    assert manifest["new_strategy_discovery_run"] is False
    assert manifest["new_backtests_run"] is False
    assert manifest["new_performance_metrics_from_raw_data_computed"] is False
    assert manifest["new_families_created"] is False
    assert manifest["new_variants_created"] is False
    assert manifest["hidden_parameter_grid_created"] is False
    assert manifest["provider_download"] is False
    assert manifest["intraday_data_used"] is False
    assert manifest["leverage_used"] is False
    assert manifest["shorting_used"] is False
    assert manifest["options_used"] is False
    assert manifest["direct_futures_used"] is False
    assert manifest["broker_api_called"] is False
    assert manifest["broker_orders_submitted"] is False
    assert manifest["broker_orders_cancelled"] is False
    assert manifest["broker_orders_reconciled"] is False
    assert manifest["live_orders"] is False
    assert manifest["real_money_recommendation"] is False
    assert manifest["candidate_exhaustive_run"] is False
    assert manifest["promotion_candidates_created"] is False
    assert manifest["paper_forward_activation"] is False
    assert manifest["new_paper_forward_candidate_created"] is False
    assert manifest["best_single_variant_promoted"] is False
    assert manifest["active_vm_preserved"] is True
    assert manifest["active_dsr_preserved"] is True
    assert manifest["static_all_weather_benchmark_control_only"] is True
    assert manifest["exact_rejected_variants_reopened"] is False
    assert manifest["diagnostic_evidence_treated_as_deployment_approval"] is False
    assert manifest["completed_high_return_tactical_excluded"] is True
    assert manifest["completed_commodity_excluded"] is True
    assert manifest["completed_macro_gld_excluded"] is True
    assert manifest["completed_volatility_throttle_excluded"] is True
    assert manifest["managed_futures_excluded"] is True
    assert guardrails["guardrails_passed"] is True


def test_registry_triage_counts_and_tables() -> None:
    manifest = load_manifest()
    candidates = pd.read_csv(EVIDENCE / "registry_candidate_table.csv")
    excluded = pd.read_csv(EVIDENCE / "excluded_candidate_table.csv")
    ranking = pd.read_csv(EVIDENCE / "ranking_scoring_table.csv")

    assert manifest["total_research_sample_review_rows_inspected"] == 70
    assert len(candidates) == manifest["total_research_sample_review_rows_inspected"]
    assert len(excluded) == manifest["rows_excluded"]
    assert len(ranking) == manifest["rows_eligible_after_filters"]
    assert manifest["rows_excluded"] + manifest["rows_eligible_after_filters"] == 70
    assert set(candidates["disposition"]).issubset({"excluded", "eligible_ranked"})
    assert len(ranking) >= 1
    assert ranking["triage_score"].is_monotonic_decreasing


def test_completed_or_blocked_families_not_selected() -> None:
    manifest = load_manifest()
    candidates = pd.read_csv(EVIDENCE / "registry_candidate_table.csv").fillna("")

    forbidden_tokens = [
        "high_return_tactical",
        "commodity",
        "macro_gld",
        "gld_macro",
        "volatility_throttle",
        "managed_futures",
    ]
    selected = str(manifest["selected_strategy_id"]).lower() + " " + str(manifest["selected_family"]).lower()
    assert not any(token in selected for token in forbidden_tokens)

    excluded_text = " ".join(
        candidates[candidates["disposition"] == "excluded"]["exclusion_reasons"].astype(str).tolist()
    ).lower()
    assert "commodity" in excluded_text
    assert "managed_futures" in excluded_text
    assert "macro/gld" in excluded_text or "gold lineage" in excluded_text


def test_next_action_semantics_and_consistency() -> None:
    manifest = load_manifest()
    consistency = load_consistency()

    if manifest["clear_winner_found"]:
        assert manifest["selected_strategy_id"] != "none"
        assert manifest["selected_family"] != "none"
        assert manifest["next_action"].startswith("design_")
        assert manifest["next_action"].endswith("_bounded_lane")
    else:
        assert manifest["selected_strategy_id"] == "none"
        assert manifest["selected_family"] == "none"
        assert manifest["next_action"] == NEXT_ACTION_SHORTLIST
        assert (EVIDENCE / "ambiguity_no_safe_candidate_report.md").exists()

    assert consistency["consistency_passed"] is True
    assert consistency["row_counts_reconcile"] is True
    assert consistency["required_files_present"] is True


def test_required_artifacts_exist() -> None:
    for filename in [
        "triage_manifest.json",
        "registry_candidate_table.csv",
        "excluded_candidate_table.csv",
        "ranking_scoring_table.csv",
        "selected_candidate_report.md",
        "guardrail_checklist.json",
        "triage_summary.md",
        "registry_triage_next_action.md",
        "triage_consistency_check.json",
    ]:
        assert (EVIDENCE / filename).exists(), filename
