from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from strategy_lab.research_os.research.global_multi_asset_etf_momentum_bounded_run import (
    ALLOWED_LABELS,
    EXPECTED_ROW_COUNT,
    LANE_ID,
    global_tsmom_weights,
    selected_defensive_weights,
)


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "research_recovery" / "global_multi_asset_etf_momentum_bounded_run" / "latest"
DESIGN = ROOT / "evidence" / "research_recovery" / "global_multi_asset_etf_momentum_bounded_design" / "latest"


def load_manifest() -> dict:
    return json.loads((EVIDENCE / "global_multi_asset_bounded_run_manifest.json").read_text(encoding="utf-8"))


def load_consistency() -> dict:
    return json.loads((EVIDENCE / "global_multi_asset_bounded_run_consistency_check.json").read_text(encoding="utf-8"))


def test_global_multi_asset_bounded_run_guardrails_and_outputs() -> None:
    manifest = load_manifest()
    consistency = load_consistency()

    assert manifest["global_multi_asset_bounded_lane_run"] is True
    assert manifest["lane_id"] == LANE_ID
    assert manifest["family_id"] == "global_multi_asset_etf_momentum"
    assert manifest["source_design_run_ready"] is True
    assert manifest["source_design_next_action_correct"] is True
    assert manifest["source_exploratory_context_only"] is True
    assert manifest["source_metrics_reused_as_current_performance_proof"] is False
    assert manifest["variant_count_planned"] == EXPECTED_ROW_COUNT
    assert manifest["variant_count_evaluated"] == EXPECTED_ROW_COUNT
    assert manifest["new_rows_added"] is False
    assert manifest["new_assets_added"] is False
    assert manifest["new_lookbacks_added"] is False
    assert manifest["new_concepts_added"] is False
    assert manifest["new_variants_created"] is False
    assert manifest["new_families_created"] is False
    assert manifest["hidden_parameter_grid_created"] is False
    assert manifest["strategy_discovery_run"] is False
    assert manifest["new_research_batch_run"] is False
    assert manifest["uses_local_cache_only"] is True
    assert manifest["provider_refresh_run"] is False
    assert manifest["provider_download"] is False
    assert manifest["intraday_data_used"] is False
    assert manifest["leverage_allowed"] is False
    assert manifest["shorting_allowed"] is False
    assert manifest["options_allowed"] is False
    assert manifest["direct_futures_allowed"] is False
    assert manifest["margin_allowed"] is False
    assert manifest["forex_allowed"] is False
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
    assert manifest["next_action"] in {
        "audit_global_multi_asset_etf_momentum_bounded_lane_results",
        "fix_global_multi_asset_bounded_lane_run_methodology_issue",
        "restore_or_revalidate_global_multi_asset_local_cache_before_bounded_run",
    }
    assert consistency["consistency_passed"] is True

    for filename in [
        "global_multi_asset_bounded_row_results.csv",
        "global_multi_asset_bounded_numeric_criteria_results.csv",
        "data_alignment_effective_window_report.md",
        "symbol_coverage_report.md",
        "baseline_comparator_report.md",
        "exposure_invariant_report.md",
        "role_label_summary.md",
        "source_lineage_context_report.md",
        "global_multi_asset_bounded_run_summary.md",
        "do_not_promote_from_global_multi_asset_bounded_run.md",
    ]:
        assert (EVIDENCE / filename).exists(), filename


def test_global_multi_asset_rows_match_design_and_are_non_promotable() -> None:
    manifest = load_manifest()
    results = pd.read_csv(EVIDENCE / "global_multi_asset_bounded_row_results.csv")
    design = pd.read_csv(DESIGN / "planned_variant_design_table.csv")

    assert set(results["variant_id"]) == set(design["variant_id"])
    assert manifest["data_blocked_row_count"] == 0
    assert manifest["max_daily_exposure"] <= 1.000001
    assert manifest["max_daily_weight_sum"] <= 1.000001
    assert manifest["exposure_invariant_passed"] is True
    assert (results["exposure_invariant_pass"].astype(str).str.lower() == "true").all()
    assert (results["promotion_eligibility"].astype(str).str.lower() == "false").all()
    assert (results["paper_forward_eligibility"].astype(str).str.lower() == "false").all()
    assert (results["candidate_exhaustive_eligibility"].astype(str).str.lower() == "false").all()
    assert set(results["research_only_label"]).issubset(ALLOWED_LABELS)
    assert set(results["variant_role"]) == {
        "selected_confirmation",
        "uncontrolled_source_baseline_context",
        "portfolio_contribution_context",
        "comparator_control",
        "cash_control",
        "commodity_real_asset_control",
    }
    control_roles = {"comparator_control", "cash_control", "commodity_real_asset_control"}
    controls = results[results["variant_role"].isin(control_roles)]
    assert (controls["research_only_label"] == "global_multi_asset_signal_control_only").all()


def test_alignment_and_symbol_coverage_are_reported() -> None:
    alignment = pd.read_csv(EVIDENCE / "data_alignment_effective_window_report.csv")
    coverage = pd.read_csv(EVIDENCE / "symbol_coverage_report.csv")

    assert len(alignment) == EXPECTED_ROW_COUNT
    assert (alignment["alignment_status"] == "common_date_aligned").all()
    required_symbols = {"SPY", "QQQ", "IWM", "EFA", "EEM", "IEF", "TLT", "GLD", "PDBC", "COMT", "BIL"}
    assert required_symbols.issubset(set(coverage["symbol"]))
    required = coverage[coverage["symbol"].isin(required_symbols)]
    assert (required["status"] == "cache_ready").all()


def test_global_tsmom_routes_failed_slots_to_bil() -> None:
    index = pd.bdate_range("2020-01-01", periods=180)
    prices = pd.DataFrame(
        {
            "SPY": range(100, 280),
            "QQQ": range(100, 280),
            "IWM": range(280, 100, -1),
            "EFA": range(280, 100, -1),
            "EEM": range(280, 100, -1),
            "IEF": range(280, 100, -1),
            "TLT": range(280, 100, -1),
            "GLD": range(280, 100, -1),
            "PDBC": range(280, 100, -1),
            "COMT": range(280, 100, -1),
            "BIL": [100.0] * 180,
        },
        index=index,
        dtype=float,
    )

    weights = global_tsmom_weights(prices, lookback=126, top_n=2)
    last = weights.iloc[-1]

    assert last["SPY"] + last["QQQ"] == 1.0
    assert last["BIL"] == 0.0
    assert float(last.sum()) <= 1.0


def test_selected_defensive_bil_is_remainder_not_additive() -> None:
    index = pd.bdate_range("2020-01-01", periods=180)
    prices = pd.DataFrame(
        {
            "SPY": range(100, 280),
            "QQQ": range(100, 280),
            "IWM": range(280, 100, -1),
            "EFA": range(280, 100, -1),
            "EEM": range(280, 100, -1),
            "IEF": range(280, 100, -1),
            "TLT": range(280, 100, -1),
            "GLD": range(280, 100, -1),
            "PDBC": range(280, 100, -1),
            "COMT": range(280, 100, -1),
            "BIL": [100.0] * 180,
        },
        index=index,
        dtype=float,
    )

    weights = selected_defensive_weights(prices)
    last = weights.iloc[-1]
    risky = last.drop(labels=["BIL"]).sum()

    assert risky <= 0.5 + 1e-9
    assert last["BIL"] >= 0.5 - 1e-9
    assert float(last.sum()) <= 1.0 + 1e-9
