from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
import pandas as pd

from strategy_lab.research_os.research.public_source_cci_correction_bounded_bt_results_audit import (
    AUDIT_PASSED_BUT_CONTROL_WEAK,
    LANE_ID,
    NEXT_ACTION_CONTROL_WEAK,
    independent_cci,
)


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = (
    ROOT
    / "evidence"
    / "research_recovery"
    / "public_source_cci_correction_bounded_bt_results_audit"
    / "latest"
)


def load_manifest() -> dict:
    return json.loads(
        (EVIDENCE / "public_source_cci_correction_bounded_bt_results_audit_manifest.json").read_text(
            encoding="utf-8"
        )
    )


def load_consistency() -> dict:
    return json.loads(
        (EVIDENCE / "public_source_cci_correction_bounded_bt_results_audit_consistency_check.json").read_text(
            encoding="utf-8"
        )
    )


def load_discrepancies() -> list[dict[str, str]]:
    with (EVIDENCE / "row_level_discrepancy_report.csv").open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def load_criteria() -> list[dict[str, str]]:
    with (EVIDENCE / "criteria_recomputation_report.csv").open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_manifest_declares_audit_only_scope_and_correct_lane() -> None:
    manifest = load_manifest()
    consistency = load_consistency()

    assert manifest["public_source_cci_correction_results_audit_only"] is True
    assert manifest["source_id"] == "cci_correction"
    assert manifest["family_id"] == "equity_index_cci_pullback_trend_bias"
    assert manifest["lane_id"] == LANE_ID
    assert manifest["source_run_evidence_reviewed"] is True
    assert manifest["source_design_evidence_reviewed"] is True
    assert manifest["run_consistency_passed"] is True
    assert manifest["variant_count_reviewed"] == 5
    assert manifest["variant_count_exact_5"] is True
    assert consistency["consistency_passed"] is True


def test_recomputed_mechanics_have_no_discrepancies() -> None:
    manifest = load_manifest()
    discrepancies = load_discrepancies()

    assert manifest["evidence_completeness_passed"] is True
    assert manifest["weekly_cci_formula_discrepancy_count"] == 0
    assert manifest["daily_signal_logic_discrepancy_count"] == 0
    assert manifest["target_weight_discrepancy_count"] == 0
    assert manifest["equity_return_discrepancy_count"] == 0
    assert manifest["row_metric_discrepancy_count"] == 0
    assert manifest["criteria_mismatch_count"] == 0
    assert manifest["total_discrepancy_count"] == 0
    assert discrepancies == []


def test_criteria_recomputation_and_exposure_invariants_pass() -> None:
    manifest = load_manifest()
    criteria = load_criteria()
    primary = next(row for row in criteria if row["variant_id"] == "cci_correction_spy_bil_primary_v1")

    assert manifest["criteria_recomputation_passed"] is True
    assert manifest["primary_numeric_criteria_pass_recomputed"] is True
    assert manifest["primary_numeric_criteria_pass_run_evidence"] is True
    assert manifest["exposure_invariant_audit_passed"] is True
    assert primary["numeric_criteria_pass_recomputed"] == "True"
    assert primary["numeric_criteria_pass_run_evidence"] == "True"
    assert primary["criteria_match"] == "True"


def test_control_weakness_is_explicit_without_overriding_registered_pass() -> None:
    manifest = load_manifest()
    control = manifest["control_comparison"]

    assert manifest["audit_decision"] == AUDIT_PASSED_BUT_CONTROL_WEAK
    assert manifest["next_action"] == NEXT_ACTION_CONTROL_WEAK
    assert manifest["serious_interpretation_weakness"] is True
    assert control["primary_underperforms_spy_buy_hold_total_return"] is True
    assert control["primary_underperforms_spy200d_total_return"] is True
    assert control["primary_underperforms_spy200d_max_drawdown"] is True
    assert control["primary_underperforms_spy200d_return_drawdown_proxy"] is True
    assert control["spy200d_dominates_primary_metric_count"] >= 2


def test_guardrails_and_non_promotable_outputs_remain_intact() -> None:
    manifest = load_manifest()

    assert manifest["uses_local_cache_only"] is True
    assert manifest["provider_download"] is False
    assert manifest["intraday_data_used"] is False
    assert manifest["public_source_scraped"] is False
    assert manifest["extra_public_sources_ingested"] is False
    assert manifest["cci_parameters_tuned"] is False
    assert manifest["new_variants_created"] is False
    assert manifest["new_exits_filters_or_indicators_added"] is False
    assert manifest["robustness_run"] is False
    assert manifest["strategy_discovery_run"] is False
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


def test_required_audit_files_exist() -> None:
    consistency = load_consistency()

    assert consistency["required_files_present"] is True
    for filename, exists in consistency["required_files"].items():
        assert exists, filename
        assert (EVIDENCE / filename).exists(), filename


def test_independent_cci_formula_matches_hand_calculation_for_last_point() -> None:
    ohlc = pd.DataFrame(
        {
            "high": [11.0, 12.0, 13.0, 14.0],
            "low": [9.0, 10.0, 11.0, 12.0],
            "close": [10.0, 11.0, 12.0, 13.0],
        },
        index=pd.date_range("2024-01-01", periods=4, freq="D"),
    )
    cci = independent_cci(ohlc, period=3)
    typical = (ohlc["high"] + ohlc["low"] + ohlc["close"]) / 3.0
    window = typical.iloc[-3:].to_numpy()
    mean = float(window.mean())
    mean_deviation = float(np.mean(np.abs(window - mean)))
    expected_last = (float(typical.iloc[-1]) - mean) / (0.015 * mean_deviation)

    assert np.isclose(float(cci.iloc[-1]), expected_last)
