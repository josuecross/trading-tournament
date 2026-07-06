from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from strategy_lab.research_os.research.public_source_larry_connors_rsi2_bounded_bt_robustness import (
    ALLOWED_ROBUSTNESS_LABELS,
    EXPECTED_VARIANTS,
    LANE_ID,
    OUTPUT_DIR,
    VALID_NEXT_ACTIONS,
)


ROOT = Path(__file__).resolve().parents[1]


def evidence_dir() -> Path:
    return ROOT / OUTPUT_DIR


def load_manifest() -> dict:
    return json.loads(
        (
            evidence_dir()
            / "public_source_larry_connors_rsi2_bounded_bt_robustness_manifest.json"
        ).read_text(encoding="utf-8")
    )


def load_consistency() -> dict:
    return json.loads(
        (
            evidence_dir()
            / "public_source_larry_connors_rsi2_bounded_bt_robustness_consistency_check.json"
        ).read_text(encoding="utf-8")
    )


def test_robustness_manifest_guardrails_and_exact_rows() -> None:
    manifest = load_manifest()
    consistency = load_consistency()

    assert manifest["public_source_larry_connors_rsi2_robustness_report"] is True
    assert manifest["source_id"] == "larry_connors_rsi2_mean_reversion"
    assert manifest["family_id"] == "short_term_equity_mean_reversion"
    assert manifest["lane_id"] == LANE_ID
    assert manifest["source_results_audit_passed"] is True
    assert manifest["same_5_rows_evaluated"] is True
    assert manifest["rows_evaluated"] == 5
    assert manifest["approved_variant_ids"] == list(EXPECTED_VARIANTS)
    assert set(manifest["evaluated_variant_ids"]) == set(EXPECTED_VARIANTS)
    assert manifest["new_rows_added"] is False
    assert manifest["new_variants_created"] is False
    assert manifest["new_indicators_added"] is False
    assert manifest["threshold_sweep_created"] is False
    assert manifest["timing_delay_optimized"] is False
    assert manifest["next_action"] in VALID_NEXT_ACTIONS
    assert consistency["consistency_passed"] is True


def test_cost_stress_rows_and_primary_result() -> None:
    manifest = load_manifest()
    stress = pd.read_csv(evidence_dir() / "base_vs_cost_stress.csv")

    assert set(stress["variant_id"]) == set(EXPECTED_VARIANTS)
    assert len(stress) == 5
    assert set(stress["robustness_label"]) <= ALLOWED_ROBUSTNESS_LABELS
    assert manifest["cost_model"] == "evaluation_only_cost_per_turnover_unit"
    assert manifest["cost_stress_bps"] == [10, 25]

    primary = stress.loc[stress["variant_id"] == "connors_rsi2_spy_bil_primary_v1"].iloc[0]
    assert bool(primary["base_numeric_criteria_pass"]) is True
    assert bool(primary["stress_10bps_numeric_criteria_pass"]) is False
    assert bool(primary["stress_25bps_numeric_criteria_pass"]) is False
    assert primary["robustness_label"] == "connors_rsi2_robustness_cost_sensitive"
    assert manifest["primary_row_base_pass"] is True
    assert manifest["primary_row_10bps_stress_pass"] is False
    assert manifest["primary_row_25bps_stress_pass"] is False
    assert (stress["stress_10bps_cagr"] <= stress["base_cagr"] + 1e-12).all()
    assert (stress["stress_25bps_cagr"] <= stress["stress_10bps_cagr"] + 1e-12).all()


def test_subperiod_rolling_and_event_stability_outputs() -> None:
    manifest = load_manifest()
    subperiod = pd.read_csv(evidence_dir() / "subperiod_performance.csv")
    rolling = pd.read_csv(evidence_dir() / "rolling_window_weakness.csv")
    events = pd.read_csv(evidence_dir() / "trade_event_stability_report.csv")

    assert len(subperiod) == 15
    assert set(subperiod["variant_id"]) == set(EXPECTED_VARIANTS)
    assert set(subperiod["period_id"]) == {
        "subperiod_2007_2014",
        "subperiod_2015_2020",
        "subperiod_2021_latest",
    }
    assert len(rolling) == 5
    assert set(rolling["variant_id"]) == set(EXPECTED_VARIANTS)
    assert len(events) == 5
    assert set(events["variant_id"]) == set(EXPECTED_VARIANTS)

    primary_events = events.loc[events["variant_id"] == "connors_rsi2_spy_bil_primary_v1"].iloc[0]
    assert primary_events["event_reconstruction_status"] == "reconstructed_from_shifted_spy_exposure"
    assert int(primary_events["event_count"]) == manifest["primary_event_trade_count"]
    assert manifest["primary_event_trade_count"] > 30
    assert float(primary_events["average_holding_days"]) > 0.0
    assert bool(primary_events["event_unstable"]) is False
    assert manifest["primary_row_subperiod_failure_count"] == 0
    assert isinstance(manifest["primary_row_rolling_window_weakness"], bool)


def test_timing_sanity_controls_sample_and_invariants() -> None:
    manifest = load_manifest()
    stress = pd.read_csv(evidence_dir() / "base_vs_cost_stress.csv")

    timing = stress.loc[stress["variant_role"] == "timing_sanity"].iloc[0]
    controls = stress.loc[stress["variant_role"] == "control"]
    assert timing["robustness_label"] == "connors_rsi2_robustness_context_only"
    assert manifest["timing_sanity_context_result"] is True
    assert manifest["timing_delay_optimization_recommended"] is False
    assert len(controls) == 3
    assert controls["robustness_label"].eq("connors_rsi2_robustness_control_only").all()
    assert manifest["control_row_count"] == 3
    assert manifest["control_rows_control_only"] is True
    assert manifest["sample_adequacy_primary_classification"] == "adequate_diagnostic_sample"
    assert float(manifest["sample_adequacy_calendar_years"]) >= 19.0
    assert int(manifest["sample_adequacy_trading_days"]) >= 4700
    assert int(manifest["sample_adequacy_event_count"]) >= 700
    assert manifest["invariant_failures"] == 0
    assert manifest["max_daily_exposure"] <= 1.000001
    assert manifest["max_daily_weight_sum"] <= 1.000001


def test_no_forbidden_actions_and_required_files() -> None:
    manifest = load_manifest()
    consistency = load_consistency()
    stress = pd.read_csv(evidence_dir() / "base_vs_cost_stress.csv")

    assert manifest["uses_local_cache_only"] is True
    assert manifest["provider_download"] is False
    assert manifest["intraday_data_used"] is False
    assert manifest["public_source_scraped"] is False
    assert manifest["public_strategy_list_ingested"] is False
    assert manifest["percent_b_continued"] is False
    assert manifest["turn_of_month_rerun"] is False
    assert manifest["faber_taa_designed_or_retested"] is False
    assert manifest["new_strategy_discovery_run"] is False
    assert manifest["new_research_batch_run"] is False
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
    assert manifest["outputs_diagnostic_only"] is True
    assert manifest["outputs_non_promotable"] is True
    assert manifest["candidate_exhaustive_ready"] is False
    assert manifest["paper_demo_eligible"] is False
    assert stress["promotion_eligibility"].astype(str).str.lower().eq("false").all()
    assert stress["paper_forward_eligibility"].astype(str).str.lower().eq("false").all()
    assert stress["candidate_exhaustive_eligibility"].astype(str).str.lower().eq("false").all()
    assert all(consistency["required_files"].values())
    for filename in consistency["required_files"]:
        assert (evidence_dir() / filename).exists(), filename
