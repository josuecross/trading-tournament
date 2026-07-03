from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from strategy_lab.research_os.research.volatility_throttle_focused_research_followup_design import (
    LANE_ID,
    OUTPUT_DIR,
    SOURCE_CONCEPT,
    SOURCE_LANE_ID,
    VALID_NEXT_ACTIONS,
)


ROOT = Path(__file__).resolve().parents[1]


def output_dir() -> Path:
    return ROOT / OUTPUT_DIR


def load_manifest() -> dict:
    return json.loads((output_dir() / "vol_throttle_followup_design_manifest.json").read_text(encoding="utf-8"))


def load_consistency() -> dict:
    return json.loads((output_dir() / "vol_throttle_followup_consistency_check.json").read_text(encoding="utf-8"))


def criteria_text() -> str:
    return (output_dir() / "success_failure_criteria.md").read_text(encoding="utf-8")


def test_volatility_throttle_followup_design_guardrails_and_required_files() -> None:
    manifest = load_manifest()
    consistency = load_consistency()
    output = output_dir()

    assert manifest["volatility_throttle_followup_design_only"] is True
    assert manifest["lane_id"] == LANE_ID
    assert manifest["source_lane"] == SOURCE_LANE_ID
    assert manifest["source_concept"] == SOURCE_CONCEPT
    assert manifest["source_audit_reviewed"] is True
    assert manifest["new_research_batch_run"] is False
    assert manifest["new_strategy_discovery_run"] is False
    assert manifest["new_backtests_run"] is False
    assert manifest["new_performance_metrics_from_raw_data_computed"] is False
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
    assert manifest["planned_variant_count"] <= 18
    assert manifest["threshold_set_count"] <= 3
    assert manifest["includes_drawdown_guard"] is False
    assert manifest["includes_macro_gld"] is False
    assert manifest["includes_managed_futures"] is False
    assert manifest["leverage_allowed"] is False
    assert manifest["shorting_allowed"] is False
    assert manifest["options_allowed"] is False
    assert manifest["direct_futures_allowed"] is False
    assert (output / "followup_variant_design_table.csv").exists()
    assert (output / "success_failure_criteria.md").exists()
    assert (output / "do_not_promote_from_followup_design.md").exists()
    assert manifest["next_action"] in VALID_NEXT_ACTIONS
    assert consistency["consistency_passed"] is True


def test_volatility_throttle_followup_design_table_scope() -> None:
    manifest = load_manifest()
    rows = pd.read_csv(output_dir() / "followup_variant_design_table.csv")

    assert len(rows) == 18
    assert rows["source_concept"].eq(SOURCE_CONCEPT).all()
    assert rows["lane_id"].eq(LANE_ID).all()
    assert rows["volatility_window"].eq(60).all()
    assert rows["exposure_cap"].astype(float).le(1.0).all()
    assert rows["promotion_eligibility"].astype(str).str.lower().eq("false").all()
    assert rows["paper_forward_eligibility"].astype(str).str.lower().eq("false").all()
    assert set(rows["threshold_set_id"]) == {
        "original_25_35_100_50_25",
        "less_defensive_30_40_100_60_30",
        "more_defensive_20_30_100_40_20",
    }
    assert not rows["threshold_set_id"].str.contains("drawdown", case=False).any()
    assert not rows["universe"].str.contains("GLD").any()
    assert manifest["planned_variant_count_lte_18"] is True
    assert manifest["threshold_set_count_lte_3"] is True


def test_volatility_throttle_followup_design_criteria_are_numeric() -> None:
    text = criteria_text()
    lowered = text.lower()

    assert "close to" not in lowered
    assert "within reason" not in lowered
    assert "meaningful" not in lowered
    assert "reasonable" not in lowered
    assert "enough" not in lowered
    assert "CAGR retention must be `>= 70%`" in text
    assert "CAGR retention versus that source row must be `>= 85%`" in text
    assert "Max drawdown reduction must be `>= 25%`" in text
    assert "Calmar or return/drawdown proxy improvement versus baseline must be `> 0.0`" in text
    assert "Average BIL/cash share must be `< 35%`" in text
    assert "Duplicate/reference correlation must be `< 0.90`" in text
    assert "max daily exposure `<= 1.000001`" in text
    assert "At least `2` related rows" in text
