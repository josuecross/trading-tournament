from __future__ import annotations

import csv
import json
from pathlib import Path

import pandas as pd

from strategy_lab.research_os.research.public_source_adx_dmi_bounded_bt_results_audit import (
    AUDIT_PASSED_BUT_CONTROL_WEAK,
    LANE_ID,
    NEXT_ACTION_CONTROL_WEAK,
    bool_series,
)


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = (
    ROOT
    / "evidence"
    / "research_recovery"
    / "public_source_adx_dmi_bounded_bt_results_audit"
    / "latest"
)


def load_manifest() -> dict:
    return json.loads(
        (EVIDENCE / "public_source_adx_dmi_bounded_bt_results_audit_manifest.json").read_text(
            encoding="utf-8"
        )
    )


def load_consistency() -> dict:
    return json.loads(
        (EVIDENCE / "public_source_adx_dmi_bounded_bt_results_audit_consistency_check.json").read_text(
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

    assert manifest["public_source_adx_dmi_results_audit_only"] is True
    assert manifest["source_id"] == "adx_dmi_trend_strength_crossover"
    assert manifest["family_id"] == "equity_index_adx_dmi_trend_strength"
    assert manifest["lane_id"] == LANE_ID
    assert manifest["source_run_evidence_reviewed"] is True
    assert manifest["source_design_evidence_reviewed"] is True
    assert manifest["methodology_patch_evidence_reviewed"] is True
    assert manifest["run_consistency_passed"] is True
    assert manifest["patch_evidence_consistency_passed"] is True
    assert manifest["variant_count_reviewed"] == 5
    assert manifest["variant_count_exact_5"] is True
    assert consistency["consistency_passed"] is True


def test_saved_evidence_reproduces_and_corrected_signal_logic_passes() -> None:
    manifest = load_manifest()
    discrepancies = load_discrepancies()
    events = manifest["event_count_semantics"]

    assert manifest["formula_value_recomputation_passed"] is True
    assert manifest["formula_value_discrepancy_count"] == 0
    assert manifest["run_implementation_recomputed_matches_saved_evidence"] is True
    assert manifest["row_level_discrepancy_count"] == 0
    assert discrepancies == []
    assert manifest["signal_logic_audit_passed"] is True
    assert manifest["event_count_semantics_audit_passed"] is True
    assert manifest["signal_logic_methodology_issue_requires_patch"] is False
    assert events["cross_fields_are_true_transition_events"] is True
    assert events["state_days_reported_separately"] is True
    assert events["saved_bullish_cross_count"] == events["true_bullish_crossover_events"]
    assert events["saved_bearish_cross_count"] == events["true_bearish_crossover_events"]
    assert events["saved_bullish_cross_count"] < events["raw_bullish_directional_state_days"]
    assert events["saved_bearish_cross_count"] < events["raw_bearish_directional_state_days"]
    assert events["saved_adx_confirmed_entry_signal_count"] == events[
        "true_adx_confirmed_bullish_crossover_events"
    ]
    assert events["actual_entry_events_from_exposure_changes"] == events[
        "true_adx_confirmed_bullish_crossover_events"
    ]


def test_criteria_recomputed_from_corrected_source_rule() -> None:
    manifest = load_manifest()
    criteria = load_criteria()
    primary = next(row for row in criteria if row["variant_id"] == "adx_dmi_spy_bil_primary_v1")

    assert manifest["criteria_recomputation_passed_against_run_implementation"] is True
    assert manifest["criteria_mismatch_count"] == 0
    assert primary["numeric_criteria_pass_recomputed"] == "True"
    assert primary["numeric_criteria_pass_run_evidence"] == "True"
    assert primary["criteria_match"] == "True"
    assert primary["source_signal_logic_valid_for_criteria"] == "True"


def test_control_weakness_is_documented_without_promotion() -> None:
    manifest = load_manifest()
    control = manifest["control_comparison"]

    assert manifest["control_weakness_detected"] is True
    assert control["primary_underperforms_spy_buy_hold_total_return"] is True
    assert control["primary_underperforms_spy200d_total_return"] is True
    assert control["primary_lower_drawdown_than_spy_buy_hold"] is True
    assert control["primary_lower_drawdown_than_spy200d"] is True
    assert control["primary_proxy_above_spy_buy_hold"] is True
    assert control["primary_proxy_above_spy200d"] is True
    assert control["primary_behaves_like_low_exposure_defensive_timing"] is True


def test_audit_decision_and_next_action_record_control_weak_pass() -> None:
    manifest = load_manifest()

    assert manifest["audit_decision"] == AUDIT_PASSED_BUT_CONTROL_WEAK
    assert manifest["next_action"] == NEXT_ACTION_CONTROL_WEAK
    assert manifest["signal_logic_methodology_issue_requires_patch"] is False


def test_patch_evidence_consistency_is_verified() -> None:
    manifest = load_manifest()
    patch = manifest["patch_evidence_consistency"]

    assert patch["methodology_patch_id_valid"] is True
    assert patch["previous_audit_decision_valid"] is True
    assert patch["previous_run_superseded"] is True
    assert patch["corrected_run_path_matches"] is True
    assert patch["formula_contract_unchanged"] is True
    assert patch["period_and_threshold_unchanged"] is True
    assert patch["variants_preserved"] is True
    assert patch["no_expansion_or_tuning"] is True
    assert patch["state_and_event_counts_agree"] is True


def test_guardrails_and_non_promotable_outputs_remain_intact() -> None:
    manifest = load_manifest()

    assert manifest["uses_local_cache_only"] is True
    assert manifest["provider_download"] is False
    assert manifest["intraday_data_used"] is False
    assert manifest["public_source_scraped"] is False
    assert manifest["extra_public_sources_ingested"] is False
    assert manifest["adx_dmi_parameters_tuned"] is False
    assert manifest["new_variants_created"] is False
    assert manifest["new_filters_exits_or_indicators_added"] is False
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
    assert manifest["bollinger_continuation"] is False
    assert manifest["macd_stochastic_continuation"] is False
    assert manifest["cci_continuation"] is False
    assert manifest["coppock_continuation"] is False
    assert manifest["larry_connors_continuation"] is False
    assert manifest["percent_b_continuation"] is False
    assert manifest["turn_of_the_month_continuation"] is False
    assert manifest["faber_taa_retest"] is False
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


def test_bool_series_parses_saved_boolean_text() -> None:
    series = pd.Series(["True", "False", True, False, "", "true"])
    parsed = bool_series(series)

    assert parsed.tolist() == [True, False, True, False, False, True]
