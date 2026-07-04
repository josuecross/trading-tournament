from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "research_recovery" / "public_source_turn_of_month_bounded_bt_design" / "latest"


def load_manifest() -> dict:
    return json.loads((EVIDENCE / "public_source_turn_of_month_bounded_bt_design_manifest.json").read_text(encoding="utf-8"))


def load_consistency() -> dict:
    return json.loads(
        (EVIDENCE / "public_source_turn_of_month_bounded_bt_design_consistency_check.json").read_text(encoding="utf-8")
    )


def load_rows() -> list[dict[str, str]]:
    with (EVIDENCE / "planned_row_table.csv").open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_manifest_design_only_and_run_ready() -> None:
    manifest = load_manifest()
    consistency = load_consistency()

    assert manifest["public_source_turn_of_month_bounded_bt_design_only"] is True
    assert manifest["source_id"] == "turn_of_month_equity_indexes"
    assert manifest["source_intake_eligibility_decision"] == "eligible_for_bounded_bt_design"
    assert manifest["lane_id"] == "public_source_turn_of_month_bounded_bt_lane_v1"
    assert manifest["family_id"] == "calendar_effect_turn_of_month_equity_index"
    assert manifest["run_readiness_decision"] == "public_source_turn_of_month_bounded_bt_design_run_ready"
    assert manifest["run_readiness_blocker"] == "none"
    assert manifest["next_action"] == "run_public_source_turn_of_month_bounded_bt_lane"
    assert consistency["consistency_passed"] is True


def test_planned_rows_are_small_bounded_and_non_promotable() -> None:
    manifest = load_manifest()
    rows = load_rows()

    assert manifest["planned_row_count"] == 5
    assert manifest["planned_row_count_between_3_and_5"] is True
    assert manifest["planned_row_count_lte_6"] is True
    assert manifest["primary_source_row_count"] == 1
    assert manifest["timing_sanity_row_count"] == 1
    assert manifest["control_row_count"] == 3
    assert {row["variant_id"] for row in rows} == {
        "totm_spy_bil_primary_close_m1_to_plus3_v1",
        "totm_spy_bil_timing_sanity_one_bar_delayed_v1",
        "totm_spy_buy_hold_control_v1",
        "totm_bil_cash_control_v1",
        "totm_spy200d_frozen_control_v1",
    }
    assert {row["research_label"] for row in rows} == {
        "public_source_calendar_totm_primary",
        "public_source_calendar_totm_timing_sanity",
        "public_source_calendar_control_only",
    }
    assert all(row["promotion_eligibility"] == "False" for row in rows)
    assert all(row["paper_forward_eligibility"] == "False" for row in rows)
    assert all(row["candidate_exhaustive_eligibility"] == "False" for row in rows)


def test_cache_bt_adapter_and_timing_requirements() -> None:
    manifest = load_manifest()
    cache_rows = list(csv.DictReader((EVIDENCE / "local_cache_availability.csv").open(newline="", encoding="utf-8")))
    timing = (EVIDENCE / "calendar_timing_convention.md").read_text(encoding="utf-8")

    assert manifest["uses_only_spy_and_bil"] is True
    assert manifest["spy_cache_ready"] is True
    assert manifest["bil_cache_ready"] is True
    assert manifest["local_cache_complete"] is True
    assert {row["symbol"]: row["cache_status"] for row in cache_rows} == {"SPY": "cache_ready", "BIL": "cache_ready"}
    assert manifest["bt_adapter_control_poc_passed"] is True
    assert manifest["bt_adapter_multasset_poc_passed"] is True
    assert manifest["bt_adapter_ready_for_design"] is True
    assert manifest["calendar_timing_convention_frozen"] is True
    assert manifest["no_lookahead_timing_documented"] is True
    assert "one common trading day before month-end" in timing
    assert "third available common trading day" in timing
    assert "one-bar shift" in timing


def test_guardrails_no_run_backtest_design_expansion_or_execution_paths() -> None:
    manifest = load_manifest()

    assert manifest["bounded_bt_design_created"] is True
    assert manifest["bounded_bt_lane_run"] is False
    assert manifest["strategy_backtest_run"] is False
    assert manifest["strategy_implemented"] is False
    assert manifest["public_source_scraped"] is False
    assert manifest["public_strategy_list_ingested"] is False
    assert manifest["faber_taa_designed_or_retested"] is False
    assert manifest["calendar_parameter_sweep_created"] is False
    assert manifest["optimization_run"] is False
    assert manifest["provider_download"] is False
    assert manifest["intraday_data_used"] is False
    assert manifest["new_packages_installed"] is False
    assert manifest["current_backtester_replaced"] is False
    assert manifest["strategy_discovery_run"] is False
    assert manifest["candidate_exhaustive_run"] is False
    assert manifest["promotion_candidates_created"] is False
    assert manifest["paper_forward_activation"] is False
    assert manifest["broker_api_called"] is False
    assert manifest["broker_orders_submitted"] is False
    assert manifest["broker_orders_cancelled"] is False
    assert manifest["broker_orders_reconciled"] is False
    assert manifest["live_orders"] is False
    assert manifest["real_money_recommendation"] is False
    assert manifest["public_source_presence_is_profitability_proof"] is False
    assert manifest["outputs_non_promotable"] is True


def test_required_design_evidence_files_exist() -> None:
    required = [
        "public_source_turn_of_month_bounded_bt_design_summary.md",
        "source_intake_review.md",
        "local_cache_availability.csv",
        "local_cache_availability.md",
        "planned_row_table.csv",
        "planned_row_table.md",
        "calendar_timing_convention.md",
        "baseline_control_policy.md",
        "numeric_success_failure_criteria.md",
        "bt_adapter_readiness.md",
        "guardrail_checklist.json",
        "exposure_invariant_requirements.md",
        "run_readiness_decision.md",
        "public_source_turn_of_month_bounded_bt_design_next_action.md",
    ]
    for filename in required:
        assert (EVIDENCE / filename).exists(), filename
