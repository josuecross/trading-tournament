from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from strategy_lab.research_os.research.macro_gld_duration_risk_off_bounded_run import (
    ALLOWED_LABELS,
    LANE_ID,
    canary_target,
    gated_barbell_target,
)


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "research_recovery" / "macro_gld_duration_risk_off_bounded_run" / "latest"


def load_manifest() -> dict:
    return json.loads((EVIDENCE / "macro_gld_bounded_run_manifest.json").read_text(encoding="utf-8"))


def load_consistency() -> dict:
    return json.loads((EVIDENCE / "macro_gld_bounded_run_consistency_check.json").read_text(encoding="utf-8"))


def test_macro_gld_bounded_run_guardrails_and_outputs() -> None:
    manifest = load_manifest()
    consistency = load_consistency()

    assert manifest["macro_gld_bounded_lane_run"] is True
    assert manifest["lane_id"] == LANE_ID
    assert manifest["family_id"] == "macro_gld_duration_risk_off"
    assert manifest["source_design_run_ready"] is True
    assert manifest["variant_count_planned"] == 8
    assert manifest["variant_count_evaluated"] == 8
    assert manifest["new_rows_added"] is False
    assert manifest["new_concepts_added"] is False
    assert manifest["new_lookbacks_added"] is False
    assert manifest["new_universes_added"] is False
    assert manifest["hidden_parameter_grid_created"] is False
    assert manifest["new_strategy_discovery_run"] is False
    assert manifest["new_research_batch_run"] is False
    assert manifest["new_families_created"] is False
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
    assert manifest["next_action"] in {
        "audit_macro_gld_duration_risk_off_bounded_research_lane_results",
        "fix_macro_gld_duration_risk_off_bounded_run_methodology_issue",
    }
    assert consistency["consistency_passed"] is True

    for filename in [
        "macro_gld_bounded_row_results.csv",
        "macro_gld_bounded_numeric_criteria_results.csv",
        "exposure_invariant_report.md",
        "baseline_comparator_report.md",
        "macro_gld_bounded_label_summary.md",
        "macro_gld_bounded_run_summary.md",
        "do_not_promote_from_macro_gld_bounded_run.md",
    ]:
        assert (EVIDENCE / filename).exists(), filename


def test_macro_gld_bounded_run_results_are_bounded_and_non_promotable() -> None:
    manifest = load_manifest()
    results = pd.read_csv(EVIDENCE / "macro_gld_bounded_row_results.csv")
    design = pd.read_csv(
        ROOT
        / "evidence"
        / "research_recovery"
        / "macro_gld_duration_risk_off_bounded_design"
        / "latest"
        / "planned_variant_design_table.csv"
    )

    assert set(results["variant_id"]) == set(design["variant_id"])
    assert manifest["max_daily_exposure"] <= 1.000001
    assert manifest["max_daily_weight_sum"] <= 1.000001
    assert manifest["exposure_invariant_passed"] is True
    assert (results["exposure_invariant_pass"].astype(str).str.lower() == "true").all()
    assert (results["promotion_eligibility"].astype(str).str.lower() == "false").all()
    assert (results["paper_forward_eligibility"].astype(str).str.lower() == "false").all()
    assert (results["candidate_exhaustive_eligibility"].astype(str).str.lower() == "false").all()
    assert set(results["research_only_label"]).issubset(ALLOWED_LABELS)


def test_cash_replacement_targets_do_not_exceed_total_exposure() -> None:
    symbols = ["SPY", "GLD", "TLT", "IEF", "BIL"]
    scores = pd.Series({"GLD": 0.2, "TLT": 0.1, "IEF": 0.0, "BIL": 0.03})
    trend = pd.Series({"SPY": False, "GLD": False, "TLT": False, "IEF": False})

    risk_off = canary_target(symbols=symbols, scores=scores, trend=trend, spy_risk_on=False, top_n=1)

    assert risk_off["BIL"] == 1.0
    assert sum(value for symbol, value in risk_off.items() if symbol != "BIL") == 0.0
    assert sum(risk_off.values()) <= 1.0


def test_gated_barbell_failed_sleeves_route_to_bil() -> None:
    symbols = ["SPY", "GLD", "IEF", "BIL"]
    prior_returns = pd.Series({"SPY": -0.1, "GLD": 0.2, "IEF": -0.1})
    trend = pd.Series({"SPY": False, "GLD": True, "IEF": False})

    target = gated_barbell_target(symbols=symbols, prior_returns=prior_returns, trend=trend)

    assert target["SPY"] == 0.0
    assert target["GLD"] == 0.5
    assert target["IEF"] == 0.0
    assert target["BIL"] == 0.5
    assert sum(target.values()) <= 1.0
