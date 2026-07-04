from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from strategy_lab.research_os.research.regional_international_momentum_bounded_run import (
    ALLOWED_LABELS,
    EXPECTED_ROW_COUNT,
    LANE_ID,
    half_bil_weights,
    regional_source_weights,
)


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "research_recovery" / "regional_international_momentum_bounded_run" / "latest"
DESIGN = ROOT / "evidence" / "research_recovery" / "regional_international_momentum_bounded_design" / "latest"


def load_manifest() -> dict:
    return json.loads((EVIDENCE / "regional_international_momentum_bounded_run_manifest.json").read_text(encoding="utf-8"))


def load_consistency() -> dict:
    return json.loads(
        (EVIDENCE / "regional_international_momentum_bounded_run_consistency_check.json").read_text(encoding="utf-8")
    )


def test_regional_bounded_run_guardrails_and_outputs() -> None:
    manifest = load_manifest()
    consistency = load_consistency()

    assert manifest["regional_international_momentum_bounded_lane_run"] is True
    assert manifest["lane_id"] == LANE_ID
    assert manifest["family_id"] == "regional_international_momentum"
    assert manifest["source_design_run_ready"] is True
    assert manifest["source_design_next_action_correct"] is True
    assert manifest["source_lineage_verified"] is True
    assert manifest["source_context_only"] is True
    assert manifest["variant_count_planned"] == EXPECTED_ROW_COUNT
    assert manifest["variant_count_evaluated"] == EXPECTED_ROW_COUNT
    assert manifest["source_context_row_count"] == 2
    assert manifest["risk_control_row_count"] == 2
    assert manifest["control_row_count"] == 3
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
    assert manifest["commodity_continued"] is False
    assert manifest["macro_gld_continued"] is False
    assert manifest["volatility_throttle_continued"] is False
    assert manifest["managed_futures_reopened"] is False
    assert manifest["high_return_tactical_continued"] is False
    assert manifest["next_action"] in {
        "audit_regional_international_momentum_bounded_lane_results",
        "fix_regional_international_momentum_bounded_lane_run_methodology_issue",
        "restore_or_revalidate_regional_international_momentum_local_cache_before_bounded_run",
    }
    assert consistency["consistency_passed"] is True

    for filename in [
        "regional_international_momentum_bounded_row_results.csv",
        "regional_international_momentum_bounded_numeric_criteria_results.csv",
        "source_context_reproduction_report.md",
        "data_alignment_effective_window_report.md",
        "symbol_coverage_report.md",
        "baseline_comparator_report.md",
        "exposure_invariant_report.md",
        "role_label_summary.md",
        "regional_international_momentum_bounded_run_summary.md",
        "do_not_promote_from_regional_international_momentum_bounded_run.md",
    ]:
        assert (EVIDENCE / filename).exists(), filename


def test_regional_rows_match_design_and_remain_non_promotable() -> None:
    manifest = load_manifest()
    results = pd.read_csv(EVIDENCE / "regional_international_momentum_bounded_row_results.csv")
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

    source_rows = results[results["variant_role"].str.startswith("source_context")]
    assert (source_rows["research_only_label"] == "regional_signal_source_context_too_risky").all()

    control_rows = results[
        results["variant_role"].isin(["comparator_control", "cash_control", "regional_passive_context_control"])
    ]
    assert (control_rows["research_only_label"] == "regional_signal_control_only").all()

    pass_rows = results[results["research_only_label"] == "regional_signal_risk_control_pass"]
    assert set(pass_rows["variant_role"]).issubset({"risk_control_half_bil_spy_gate", "risk_control_half_bil_top2"})


def test_alignment_and_symbol_coverage_are_reported() -> None:
    alignment = pd.read_csv(EVIDENCE / "data_alignment_effective_window_report.csv")
    coverage = pd.read_csv(EVIDENCE / "symbol_coverage_report.csv")

    assert len(alignment) == EXPECTED_ROW_COUNT
    assert (alignment["alignment_status"] == "per_asset_availability_with_bil_spy_common_frame").all()
    required_symbols = {"SPY", "EWJ", "EWU", "EWG", "EWY", "INDA", "EFA", "EEM", "BIL"}
    assert required_symbols.issubset(set(coverage["symbol"]))
    required = coverage[coverage["symbol"].isin(required_symbols)]
    assert (required["status"] == "cache_ready").all()


def test_source_spy_gate_risk_off_forces_bil() -> None:
    index = pd.bdate_range("2020-01-01", periods=260)
    prices = pd.DataFrame(
        {
            "SPY": list(range(360, 100, -1)),
            "EWJ": list(range(100, 360)),
            "EWU": list(range(100, 360)),
            "EWG": list(range(360, 100, -1)),
            "EWY": list(range(360, 100, -1)),
            "INDA": list(range(360, 100, -1)),
            "EFA": list(range(360, 100, -1)),
            "EEM": list(range(360, 100, -1)),
            "BIL": [100.0] * 260,
        },
        index=index,
        dtype=float,
    )

    weights = regional_source_weights(prices, top_n=2, spy_gate=True)
    last = weights.iloc[-1]

    assert last["BIL"] == 1.0
    assert float(last.drop(labels=["BIL"]).sum()) == 0.0
    assert float(last.sum()) <= 1.0


def test_half_bil_risk_control_uses_bil_as_remainder() -> None:
    index = pd.bdate_range("2020-01-01", periods=260)
    prices = pd.DataFrame(
        {
            "SPY": list(range(100, 360)),
            "EWJ": list(range(100, 360)),
            "EWU": list(range(100, 360)),
            "EWG": list(range(360, 100, -1)),
            "EWY": list(range(360, 100, -1)),
            "INDA": list(range(360, 100, -1)),
            "EFA": list(range(360, 100, -1)),
            "EEM": list(range(360, 100, -1)),
            "BIL": [100.0] * 260,
        },
        index=index,
        dtype=float,
    )

    source = regional_source_weights(prices, top_n=2, spy_gate=False)
    weights = half_bil_weights(source)
    last = weights.iloc[-1]
    risky = last.drop(labels=["BIL"]).sum()

    assert risky <= 0.5 + 1e-9
    assert last["BIL"] >= 0.5 - 1e-9
    assert float(last.sum()) <= 1.0 + 1e-9
