from __future__ import annotations

import csv
import json
from pathlib import Path

from strategy_lab.research_os.research.high_return_tactical_risk_control_lane_design import (
    LANE_ID,
    OUTPUT_DIR,
    SOURCE_FAMILY,
    VALID_NEXT_ACTIONS,
    run,
)


ROOT = Path(__file__).resolve().parents[1]


def load_manifest() -> dict:
    output = ROOT / OUTPUT_DIR
    return json.loads((output / "risk_control_lane_design_manifest.json").read_text(encoding="utf-8"))


def load_consistency() -> dict:
    output = ROOT / OUTPUT_DIR
    return json.loads((output / "risk_control_lane_consistency_check.json").read_text(encoding="utf-8"))


def load_variants() -> list[dict[str, str]]:
    output = ROOT / OUTPUT_DIR
    with (output / "variant_design_table.csv").open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_design_packet_guardrails_and_required_files() -> None:
    result = run(ROOT)
    output = Path(result["output_dir"])
    manifest = load_manifest()
    consistency = load_consistency()

    assert manifest["risk_control_lane_design_only"] is True
    assert manifest["lane_id"] == LANE_ID
    assert manifest["source_family"] == SOURCE_FAMILY
    assert manifest["source_methodology_fixed"] is True
    assert manifest["source_labeling_fixed"] is True
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
    assert manifest["macro_gld_remains_lineage_blocked_visible"] is True
    assert manifest["alpaca_execution_module_delegated"] is True
    assert (output / "variant_design_table.csv").exists()
    assert (output / "frozen_rule_summaries.md").exists()
    assert (output / "success_failure_criteria.md").exists()
    assert manifest["leverage_allowed"] is False
    assert manifest["shorting_allowed"] is False
    assert manifest["options_allowed"] is False
    assert manifest["direct_futures_allowed"] is False
    assert manifest["max_exposure_allowed"] <= 1.0
    assert manifest["next_action"] in VALID_NEXT_ACTIONS
    assert consistency["consistency_passed"] is True


def test_variant_design_is_small_focused_and_non_promotable() -> None:
    run(ROOT)
    manifest = load_manifest()
    variants = load_variants()

    assert len(variants) == 24
    assert manifest["variant_count_planned"] == 24
    assert manifest["risk_control_concepts_count"] == 4
    assert len({row["universe_group"] for row in variants}) == 2
    assert {int(row["momentum_lookback_days"]) for row in variants} == {63, 126, 252}
    assert {row["risk_control_concept"] for row in variants} == {
        "spy200d_regime_filter",
        "realized_volatility_throttle",
        "strategy_drawdown_guard",
        "regime_plus_volatility_guard",
    }
    assert all(int(row["top_n"]) == 2 for row in variants)
    assert all(float(row["exposure_cap"]) <= 1.0 for row in variants)
    assert all(row["status"] == "non_promotable_preregistered_design" for row in variants)
    assert all(row["promotion_eligible"] == "False" for row in variants)
    assert all(row["paper_forward_eligible"] == "False" for row in variants)
    assert all(row["leverage_allowed"] == "False" for row in variants)
    assert all(row["shorting_allowed"] == "False" for row in variants)
    assert all(row["options_allowed"] == "False" for row in variants)
    assert all(row["direct_futures_allowed"] == "False" for row in variants)
