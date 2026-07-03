from __future__ import annotations

import csv
import json
from pathlib import Path

from strategy_lab.research_os.research.high_return_tactical_risk_control_lane_design_patch import (
    LANE_ID,
    OUTPUT_DIR,
    VALID_NEXT_ACTIONS,
    run,
)


ROOT = Path(__file__).resolve().parents[1]


def load_manifest() -> dict:
    output = ROOT / OUTPUT_DIR
    return json.loads((output / "risk_control_lane_design_patch_manifest.json").read_text(encoding="utf-8"))


def load_consistency() -> dict:
    output = ROOT / OUTPUT_DIR
    return json.loads((output / "risk_control_lane_design_patch_consistency_check.json").read_text(encoding="utf-8"))


def load_variants() -> list[dict[str, str]]:
    output = ROOT / OUTPUT_DIR
    with (output / "patched_variant_design_table.csv").open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_design_patch_guardrails_and_required_files() -> None:
    result = run(ROOT)
    output = Path(result["output_dir"])
    manifest = load_manifest()
    consistency = load_consistency()

    assert manifest["risk_control_lane_design_patch_only"] is True
    assert manifest["lane_id"] == LANE_ID
    assert manifest["source_design_audit_reviewed"] is True
    assert manifest["new_research_batch_run"] is False
    assert manifest["new_strategy_discovery_run"] is False
    assert manifest["new_backtests_run"] is False
    assert manifest["new_performance_metrics_from_raw_data_computed"] is False
    assert manifest["new_variants_created"] is False
    assert manifest["new_families_created"] is False
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
    assert manifest["variant_count_planned"] <= 24
    assert manifest["all_variant_rules_explicit_after_patch"] is True
    assert manifest["thresholds_explicit_after_patch"] is True
    assert manifest["fallback_rules_explicit_after_patch"] is True
    assert manifest["reentry_rules_explicit_after_patch"] is True
    assert manifest["success_failure_criteria_measurable_after_patch"] is True
    assert manifest["max_exposure_allowed"] <= 1.0
    assert manifest["leverage_allowed"] is False
    assert manifest["shorting_allowed"] is False
    assert manifest["options_allowed"] is False
    assert manifest["direct_futures_allowed"] is False
    assert (output / "patched_variant_design_table.csv").exists()
    assert (output / "patched_frozen_rule_summaries.md").exists()
    assert (output / "explicit_threshold_policy.md").exists()
    assert (output / "fallback_and_bil_semantics.md").exists()
    assert (output / "drawdown_guard_reentry_policy.md").exists()
    assert (output / "combined_rule_precedence.md").exists()
    assert manifest["next_action"] in VALID_NEXT_ACTIONS
    assert consistency["consistency_passed"] is True


def test_patched_variant_rules_are_explicit_and_non_promotable() -> None:
    run(ROOT)
    manifest = load_manifest()
    variants = load_variants()
    combined_text = "\n".join(
        " ".join(
            row[field]
            for field in ("risk_control_rule", "fallback_allocation", "cash_bil_handling_rule")
        )
        for row in variants
    )

    assert len(variants) == 24
    assert manifest["variant_count_changed"] is False
    assert {row["risk_control_concept"] for row in variants} == {
        "spy200d_regime_filter",
        "realized_volatility_throttle",
        "strategy_drawdown_guard",
        "regime_plus_volatility_guard",
    }
    assert "25%" in combined_text
    assert "35%" in combined_text
    assert "-15%" in combined_text
    assert "-25%" in combined_text
    assert "-10%" in combined_text
    assert "volatility throttle cannot override" in combined_text
    assert "BIL or BIL remainder" not in combined_text
    assert "preregistered high-volatility threshold" not in combined_text
    assert "recovery condition" not in combined_text
    assert all(float(row["exposure_cap"]) <= 1.0 for row in variants)
    assert all(row["promotion_eligible"] == "False" for row in variants)
    assert all(row["paper_forward_eligible"] == "False" for row in variants)
