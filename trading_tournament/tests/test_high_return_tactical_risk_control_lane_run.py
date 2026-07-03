from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from strategy_lab.research_os.research.high_return_tactical_risk_control_lane_run import (
    LANE_ID,
    OUTPUT_DIR,
    VALID_NEXT_ACTIONS,
    apply_multiplier_to_weights,
    combined_risky_multiplier,
    drawdown_guard_multiplier,
    volatility_multiplier,
)


ROOT = Path(__file__).resolve().parents[1]


def output_dir() -> Path:
    return ROOT / OUTPUT_DIR


def load_manifest() -> dict:
    return json.loads((output_dir() / "risk_control_lane_run_manifest.json").read_text(encoding="utf-8"))


def load_consistency() -> dict:
    return json.loads((output_dir() / "risk_control_lane_run_consistency_check.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def lane_run_result() -> dict:
    output = output_dir()
    assert (output / "risk_control_lane_run_manifest.json").exists()
    return {"output_dir": str(output)}


def test_risk_control_lane_run_guardrails_and_outputs(lane_run_result: dict) -> None:
    manifest = load_manifest()
    consistency = load_consistency()
    output = Path(lane_run_result["output_dir"])

    assert manifest["risk_control_lane_run"] is True
    assert manifest["lane_id"] == LANE_ID
    assert manifest["source_design_patch_v2_audit_passed"] is True
    assert manifest["variant_count_planned"] == 24
    assert manifest["new_variants_created"] is False
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
    assert manifest["paper_forward_activation"] is False
    assert manifest["new_paper_forward_candidate_created"] is False
    assert manifest["candidate_exhaustive_run"] is False
    assert manifest["best_single_variant_promoted"] is False
    assert manifest["research_outputs_remain_non_promotable"] is True
    assert manifest["active_vm_preserved"] is True
    assert manifest["active_dsr_preserved"] is True
    assert manifest["static_all_weather_benchmark_control_only"] is True
    assert manifest["macro_gld_lineage_recovery_run"] is False
    assert manifest["alpaca_execution_module_delegated"] is True
    assert (output / "variant_run_results.csv").exists()
    assert (output / "family_run_summary.csv").exists()
    assert (output / "baseline_comparison_results.csv").exists()
    assert (output / "exposure_invariant_report.md").exists()
    assert (output / "cash_bil_invariant_report.md").exists()
    assert (output / "do_not_promote_from_risk_control_lane_run.md").exists()
    assert manifest["next_action"] in VALID_NEXT_ACTIONS
    assert consistency["consistency_passed"] is True


def test_risk_control_lane_run_invariants_and_baseline_completeness(lane_run_result: dict) -> None:
    manifest = load_manifest()
    results = pd.read_csv(output_dir() / "variant_run_results.csv")

    assert manifest["variant_count_evaluated"] == 24
    assert manifest["max_daily_exposure"] <= 1.000001
    assert manifest["exposure_invariant_passed"] is True
    assert manifest["cash_bil_invariant_passed"] is True
    assert manifest["baseline_comparison_missing_count"] == 0 or manifest["data_blocked_variant_count"] > 0
    assert (results["promotion_eligibility"].astype(str).str.lower() == "false").all()
    assert (results["paper_forward_eligibility"].astype(str).str.lower() == "false").all()
    assert results["risk_control_research_label"].isin(
        {
            "risk_control_signal_promising",
            "risk_control_signal_tradeoff_interesting",
            "risk_control_signal_return_destroyed",
            "risk_control_signal_drawdown_not_fixed",
            "risk_control_signal_duplicate_existing_active",
            "risk_control_signal_data_blocked",
            "risk_control_signal_weak",
        }
    ).all()


def test_spy_risk_off_and_bil_remainder_not_additive() -> None:
    base = pd.Series({"SPY": 0.5, "QQQ": 0.5, "BIL": 0.0})
    risk_off = apply_multiplier_to_weights(base, 0.0)
    half_risk = apply_multiplier_to_weights(base, 0.5)

    assert risk_off["BIL"] == 1.0
    assert risk_off[["SPY", "QQQ"]].sum() == 0.0
    assert half_risk[["SPY", "QQQ"]].sum() == 0.5
    assert half_risk["BIL"] == 0.5
    assert half_risk.sum() <= 1.0


def test_volatility_throttle_uses_prior_window_categories() -> None:
    assert volatility_multiplier(float("nan"), enough_history=False) == 1.0
    assert volatility_multiplier(0.24) == 1.0
    assert volatility_multiplier(0.25) == 1.0
    assert volatility_multiplier(0.30) == 0.5
    assert volatility_multiplier(0.35) == 0.5
    assert volatility_multiplier(0.36) == 0.25


def test_drawdown_guard_uses_prior_controlled_drawdown_state() -> None:
    assert drawdown_guard_multiplier(-0.05, guard_active=False, active_multiplier=1.0) == (1.0, False)
    assert drawdown_guard_multiplier(-0.16, guard_active=False, active_multiplier=1.0) == (0.5, True)
    assert drawdown_guard_multiplier(-0.26, guard_active=True, active_multiplier=0.5) == (0.0, True)
    assert drawdown_guard_multiplier(-0.12, guard_active=True, active_multiplier=0.0) == (0.0, True)
    assert drawdown_guard_multiplier(-0.09, guard_active=True, active_multiplier=0.0) == (1.0, False)


def test_combined_controls_use_most_defensive_multiplier() -> None:
    assert combined_risky_multiplier(1.0, 0.5, 0.25) == 0.25
    assert combined_risky_multiplier(1.0, 0.5) == 0.5
    assert combined_risky_multiplier(1.0) == 1.0
