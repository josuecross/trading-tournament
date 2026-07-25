from __future__ import annotations

import csv
import json

import pandas as pd
import yaml

from strategy_lab.research_os.research import (
    pring_kst_incremental_standalone_validation_v1 as validation,
)


REQUIRED_ARTIFACTS = [
    "validation_manifest.yaml",
    "strategy_cards.csv",
    "trial_ledger.csv",
    "process_task_log.csv",
    "benchmark_reference_log.csv",
    "reproduction_check.csv",
    "full_period_results.csv",
    "chronological_half_results.csv",
    "rolling_36_month_results.csv",
    "rolling_60_month_results.csv",
    "rolling_window_summary.csv",
    "calendar_year_results.csv",
    "signal_state_diagnostics.csv",
    "holding_episode_results.csv",
    "exposure_control_reconciliation.csv",
    "turnover_cost_reconciliation.csv",
    "outcome_summary.csv",
    "failure_reasons.csv",
    "next_actions.csv",
    "consistency_check.json",
    "validation_report.md",
]


def setup_module() -> None:
    validation.run()


def rows(name: str) -> list[dict[str, str]]:
    with (validation.OUTPUT_DIR / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def json_payload(name: str) -> dict:
    return json.loads((validation.OUTPUT_DIR / name).read_text(encoding="utf-8"))


def yaml_payload(name: str) -> dict:
    return yaml.safe_load((validation.OUTPUT_DIR / name).read_text(encoding="utf-8"))


def test_required_artifacts_and_exact_single_strategy_scope() -> None:
    for artifact in REQUIRED_ARTIFACTS:
        assert (validation.OUTPUT_DIR / artifact).exists(), artifact
    manifest = yaml_payload("validation_manifest.yaml")
    assert manifest["task_id"] == "pring_kst_incremental_standalone_validation_v1"
    assert manifest["strategy_id"] == "pring_kst_default_centerline_spy_bil_v1"
    assert manifest["strategy_count"] == 1
    assert manifest["validation_trial_count"] == 1
    assert manifest["benchmark_reference_count"] == 4
    assert manifest["rolling_windows_months"] == [36, 60]
    assert manifest["cost_assumptions_bps"] == [0.0, 5.0, 10.0]
    assert manifest["exposure_matched_control"] == {
        "id": "static_6878_SPY_3122_BIL_monthly_rebalanced",
        "SPY": 0.6878,
        "BIL": 0.3122,
        "optimization_performed": False,
    }
    assert manifest["promotion_or_paper_demo_authorized"] is False


def test_strategy_card_and_single_validation_child_lineage_are_complete() -> None:
    cards = rows("strategy_cards.csv")
    trials = rows("trial_ledger.csv")
    assert len(cards) == len(trials) == 1
    card = cards[0]
    trial = trials[0]
    assert card["entity_type"] == "strategy_configuration"
    assert card["stage"] == "validation"
    assert card["strategy_architecture"] == "weighted_multi_horizon_smoothed_rate_of_change_filter"
    assert card["instrument_universe"] == "SPY|BIL"
    assert "strategy_source_library_refresh_v2:src_pring_kst_1992_v1" in card["source_or_research_lineage"]
    assert trial["entity_type"] == "experiment_trial"
    assert trial["parent_trial_id"] == "fast_source_v5__pring_kst_default_centerline_spy_bil_v1__canonical"
    assert trial["adaptation_label"] == "validation_variant"
    assert (
        trial["changed_fields_from_parent"]
        == "validation_diagnostics_and_predeclared_exposure_and_trend_controls_only"
    )
    for field in (
        "strategy_rule_changed",
        "parameters_changed",
        "instruments_changed",
        "execution_changed",
        "cost_model_changed",
        "optimization_performed",
        "timeframe_selected_from_performance",
    ):
        assert trial[field] == "false"
    assert trial["validation_controls_added"] == "true"
    assert trial["exposure_matched_control_derived_after_exploration"] == "true"


def test_four_controls_and_process_task_remain_separate_entities() -> None:
    benchmarks = rows("benchmark_reference_log.csv")
    process = rows("process_task_log.csv")
    assert {row["benchmark_reference_id"] for row in benchmarks} == set(validation.CONTROL_IDS)
    assert {row["entity_type"] for row in benchmarks} == {"benchmark_reference"}
    assert {row["stage"] for row in benchmarks} == {"benchmark_reference_only"}
    assert all(row["counted_as_strategy"] == "false" for row in benchmarks)
    assert all(row["counted_as_trial"] == "false" for row in benchmarks)
    assert all(row["counted_as_observation"] == "false" for row in benchmarks)
    static = next(row for row in benchmarks if row["benchmark_reference_id"] == validation.STATIC_CONTROL)
    assert static["control_role"] == "post_exploration_exposure_matching_control"
    assert static["performance_optimized"] == "false"
    assert len(process) == 1
    assert process[0]["entity_type"] == "process_task"
    assert process[0]["strategy_count"] == process[0]["trial_count"] == "0"


def test_v5_reproduction_gate_passes_at_strict_tolerance() -> None:
    reproduction = rows("reproduction_check.csv")
    assert len(reproduction) == 3 * 11
    assert {row["entity_id"] for row in reproduction} == {
        validation.STRATEGY_ID,
        validation.SPY_CONTROL,
        validation.ROC30_CONTROL,
    }
    assert {row["reproduction_status"] for row in reproduction} == {"pass"}
    assert max(float(row["absolute_difference"]) for row in reproduction) <= 1e-10
    kst = {
        row["metric"]: float(row["recomputed_value"])
        for row in reproduction
        if row["entity_id"] == validation.STRATEGY_ID
    }
    assert abs(kst["sharpe_ratio"] - 0.652563525624) <= 1e-10
    assert abs(kst["maximum_drawdown"] - (-0.19768938469)) <= 1e-10
    assert abs(kst["average_risky_exposure"] - 0.687799791449) <= 1e-10
    assert kst["turnover"] == 114.5
    assert kst["trade_or_rebalance_count"] == 115.0


def test_full_period_halves_costs_and_accounting_invariants_are_complete() -> None:
    full = rows("full_period_results.csv")
    halves = rows("chronological_half_results.csv")
    turnover = rows("turnover_cost_reconciliation.csv")
    entities = {validation.STRATEGY_ID, *validation.CONTROL_IDS}
    assert len(full) == 5 * 3
    assert len(halves) == 5 * 3 * 2
    assert {row["entity_id"] for row in full} == entities
    assert {row["cost_assumption_bps"] for row in full} == {"0", "5", "10"}
    assert {row["period_label"] for row in halves} == {
        "first_chronological_half",
        "second_chronological_half",
    }
    assert all("not_clean_or_sealed_holdout" in row["half_source"] for row in halves)
    assert all(row["invariant_pass"] == "true" for row in full)
    assert all(float(row["maximum_gross_exposure"]) <= 1.0 + 1e-10 for row in full)
    assert all(float(row["maximum_daily_weight_sum"]) <= 1.0 + 1e-10 for row in full)
    assert len(turnover) == 5 * 3
    assert all(row["actual_pretrade_holdings_used"] == "true" for row in turnover)
    assert all(row["explicit_zero_weights_preserved"] == "true" for row in turnover)
    assert all(row["stale_weight_forward_fill_used"] == "false" for row in turnover)
    assert all(row["invariant_pass"] == "true" for row in turnover)


def assert_true_calendar_windows(window_rows: list[dict[str, str]], months: int) -> None:
    assert window_rows
    for row in window_rows:
        start = pd.Timestamp(row["window_start"])
        end = pd.Timestamp(row["window_end"])
        cutoff = end - pd.DateOffset(months=months)
        assert cutoff <= start <= cutoff + pd.Timedelta(days=7)
        assert int(row["trading_days"]) > 0


def test_rolling_windows_include_every_control_cost_and_unfavorable_result() -> None:
    rolling_36 = rows("rolling_36_month_results.csv")
    rolling_60 = rows("rolling_60_month_results.csv")
    assert_true_calendar_windows(rolling_36, 36)
    assert_true_calendar_windows(rolling_60, 60)
    for rolling_rows, expected_windows in ((rolling_36, 193), (rolling_60, 170)):
        assert {row["control_id"] for row in rolling_rows} == set(validation.CONTROL_IDS)
        assert {row["cost_assumption_bps"] for row in rolling_rows} == {"0", "5", "10"}
        assert len(rolling_rows) == expected_windows * 4 * 3
        assert all(row["numeric_invariant_status"] == "pass" for row in rolling_rows)
        assert all(row["timing_invariant_status"] == "pass" for row in rolling_rows)
        assert all(row["exposure_weight_invariant_status"] == "pass" for row in rolling_rows)
        assert any(row["control_dominates_kst"] == "true" for row in rolling_rows)
        assert any(float(row["sharpe_ratio_difference"]) < 0.0 for row in rolling_rows)

    summary = rows("rolling_window_summary.csv")
    best = {
        int(row["window_months"]): row
        for row in summary
        if row["cost_assumption_bps"] == "5"
        and row["comparison_scope"] == "best_non_buy_and_hold_control_per_window"
    }
    assert float(best[36]["median_sharpe_ratio_difference"]) < 0.0
    assert float(best[60]["median_sharpe_ratio_difference"]) < 0.0
    assert float(best[36]["control_dominated_window_fraction"]) > 0.5
    assert float(best[60]["control_dominated_window_fraction"]) > 0.5


def test_calendar_signal_episode_and_exposure_diagnostics_are_complete() -> None:
    calendar = rows("calendar_year_results.csv")
    summary_rows = [
        row for row in rows("signal_state_diagnostics.csv")
        if row["diagnostic_scope"] == "full_period_summary"
    ]
    episodes = rows("holding_episode_results.csv")
    exposure = rows("exposure_control_reconciliation.csv")
    assert {row["entity_id"] for row in calendar} == {
        validation.STRATEGY_ID,
        *validation.CONTROL_IDS,
    }
    assert {row["cost_assumption_bps"] for row in calendar} == {"0", "5", "10"}
    assert all(row["descriptive_only"] == "true" for row in calendar)
    assert len(summary_rows) == 1
    signal = summary_rows[0]
    assert signal["entry_count"] == "58"
    assert signal["exit_count"] == "57"
    assert signal["holding_episode_count"] == "58"
    assert signal["state_change_count"] == "115"
    assert len(episodes) == 58
    assert all(int(row["holding_duration_sessions"]) > 0 for row in episodes)
    assert len(exposure) == 3
    assert {row["frozen_static_spy_target"] for row in exposure} == {"0.6878"}
    assert {row["frozen_static_bil_target"] for row in exposure} == {"0.3122"}
    assert all(row["performance_optimized_weight"] == "false" for row in exposure)
    assert all(row["benchmark_reference_only"] == "true" for row in exposure)


def test_validation_decision_failure_reason_and_next_action_follow_contract() -> None:
    outcome = rows("outcome_summary.csv")[0]
    checks = json.loads(outcome["decision_checks"])
    assert outcome["outcome"] == "validation_failed"
    assert outcome["primary_failure_reason"] == "period_instability"
    assert checks["reproduction_pass"] is True
    assert checks["invariant_pass"] is True
    assert checks["full_period_dominating_controls"] == []
    assert checks["rolling_36_requirement_pass"] is False
    assert checks["rolling_60_requirement_pass"] is False
    assert checks["rolling_36_domination_requirement_pass"] is False
    assert checks["rolling_60_domination_requirement_pass"] is False
    assert outcome["next_action"] == "direction_owner_review_close_kst_after_validation_v1"
    assert outcome["next_action_executed"] == "false"
    assert outcome["promotion_or_paper_demo_authorized"] == "false"
    failures = rows("failure_reasons.csv")
    assert len(failures) == 1
    assert failures[0]["primary_failure_reason"] == "period_instability"
    assert failures[0]["exact_configuration_only"] == "true"
    assert failures[0]["family_closed"] == "false"
    assert {row["execute_now"] for row in rows("next_actions.csv")} == {"false"}


def test_protected_inputs_cache_and_generation_are_deterministic() -> None:
    consistency = json_payload("consistency_check.json")
    assert consistency["status"] == "pass"
    assert consistency["protected_state_and_cache_unchanged"] is True
    assert consistency["prior_evidence_unchanged"] is True
    assert consistency["all_forbidden_actions_false"] is True
    assert consistency["benchmark_reference_count"] == 4
    protected_before = validation.hash_paths(validation.PROTECTED_PATHS)
    first = {
        artifact: (validation.OUTPUT_DIR / artifact).read_bytes()
        for artifact in REQUIRED_ARTIFACTS
    }
    validation.run()
    second = {
        artifact: (validation.OUTPUT_DIR / artifact).read_bytes()
        for artifact in REQUIRED_ARTIFACTS
    }
    assert first == second
    assert protected_before == validation.hash_paths(validation.PROTECTED_PATHS)
