from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "research_recovery" / "macro_gld_duration_risk_off_bounded_robustness" / "latest"


def load_manifest() -> dict:
    return json.loads((EVIDENCE / "macro_gld_bounded_robustness_manifest.json").read_text(encoding="utf-8"))


def load_consistency() -> dict:
    return json.loads((EVIDENCE / "macro_gld_bounded_robustness_consistency_check.json").read_text(encoding="utf-8"))


def test_macro_gld_robustness_guardrails_and_files() -> None:
    manifest = load_manifest()
    consistency = load_consistency()

    assert manifest["macro_gld_bounded_robustness_report"] is True
    assert manifest["lane_id"] == "macro_gld_duration_risk_off_bounded_lane_v1"
    assert manifest["family_id"] == "macro_gld_duration_risk_off"
    assert manifest["same_8_rows_evaluated"] is True
    assert manifest["rows_evaluated"] == 8
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
    assert manifest["invariant_failures"] == 0
    assert consistency["consistency_passed"] is True

    for filename in [
        "base_vs_stress_row_results.csv",
        "subperiod_performance.csv",
        "rolling_window_weakness.csv",
        "comparator_robustness_report.md",
        "exposure_invariant_report.md",
        "macro_gld_bounded_robustness_summary.md",
        "do_not_promote_from_macro_gld_robustness.md",
    ]:
        assert (EVIDENCE / filename).exists(), filename


def test_robustness_uses_same_rows_and_cost_stress() -> None:
    manifest = load_manifest()
    stress = pd.read_csv(EVIDENCE / "base_vs_stress_row_results.csv")
    run_rows = pd.read_csv(
        ROOT
        / "evidence"
        / "research_recovery"
        / "macro_gld_duration_risk_off_bounded_run"
        / "latest"
        / "macro_gld_bounded_row_results.csv"
    )

    assert set(stress["variant_id"]) == set(run_rows["variant_id"])
    assert len(stress) == 8
    assert manifest["cost_model"] == "evaluation_only_cost_per_turnover_unit"
    assert manifest["cost_stress_bps"] == [10, 25]
    assert (stress["promotion_eligibility"].astype(str).str.lower() == "false").all()
    assert (stress["paper_forward_eligibility"].astype(str).str.lower() == "false").all()
    assert (stress["stress_10bps_cagr"] <= stress["base_cagr"] + 1e-12).all()
    assert (stress["stress_25bps_cagr"] <= stress["stress_10bps_cagr"] + 1e-12).all()


def test_subperiod_and_rolling_outputs_cover_all_rows() -> None:
    subperiod = pd.read_csv(EVIDENCE / "subperiod_performance.csv")
    rolling = pd.read_csv(EVIDENCE / "rolling_window_weakness.csv")
    stress = pd.read_csv(EVIDENCE / "base_vs_stress_row_results.csv")

    assert len(subperiod) == 24
    assert set(subperiod["variant_id"]) == set(stress["variant_id"])
    assert set(subperiod["period_id"]) == {
        "subperiod_2007_2014",
        "subperiod_2015_2020",
        "subperiod_2021_latest",
    }
    assert len(rolling) == 8
    assert set(rolling["variant_id"]) == set(stress["variant_id"])
    assert "unacceptable_rolling_weakness" in rolling.columns
