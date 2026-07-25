from __future__ import annotations

import csv
import json
from pathlib import Path

import pandas as pd
import pytest
import yaml

from strategy_lab.research_os.research import angl_80_20_portfolio_construction_methodology_correction_v1 as correction


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "correction" / "angl_80_20_portfolio_construction_methodology_correction_v1" / "latest"
STRATEGY_ID = "ice_vaneck_us_fallen_angel_angl_v1"
PREVIOUS_TRIAL_ID = "validation_angl__ice_vaneck_us_fallen_angel_angl_v1__validation_variant_child"
CORRECTION_TRIAL_ID = "correction_angl__ice_vaneck_us_fallen_angel_angl_v1__methodology_correction_child"
PORTFOLIO_IDS = {
    "frozen_reference_100pct",
    f"{STRATEGY_ID}_candidate_20pct",
    "HYG_buy_hold_20pct_control",
    "monthly_rebalanced_50_50_HYG_JNK_20pct_control",
}
COSTS = {"0", "5", "10"}
OUTCOME_NEXT_ACTION = {
    "validation_positive": "direction_owner_review_angl_paper_demo_eligibility_v2",
    "validation_mixed": "direction_owner_review_angl_corrected_validation_mixed_v1",
    "validation_failed": "direction_owner_review_close_angl_after_methodology_correction_v1",
    "validation_data_or_methodology_blocked": "direction_owner_review_angl_methodology_block_v1",
}


@pytest.fixture(scope="module", autouse=True)
def generated_correction() -> dict[str, object]:
    return correction.run()


def read_csv(name: str) -> list[dict[str, str]]:
    with (EVIDENCE / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_json(name: str) -> dict[str, object]:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def read_yaml(name: str) -> dict[str, object]:
    return yaml.safe_load((EVIDENCE / name).read_text(encoding="utf-8"))


def cost_set(rows: list[dict[str, str]], id_field: str) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for row in rows:
        out.setdefault(row[id_field], set()).add(row["cost_assumption_bps"])
    return out


def test_required_artifacts_and_manifest_scope() -> None:
    required = {
        "correction_manifest.yaml",
        "strategy_cards.csv",
        "trial_ledger.csv",
        "process_task_log.csv",
        "benchmark_reference_log.csv",
        "prior_portfolio_method_classification.csv",
        "prior_result_reproduction.csv",
        "daily_nav_reconciliation.csv",
        "monthly_rebalance_events.csv",
        "turnover_cost_reconciliation.csv",
        "canonical_full_period_results.csv",
        "canonical_chronological_half_results.csv",
        "canonical_rolling_36_month_results.csv",
        "canonical_rolling_60_month_results.csv",
        "canonical_rolling_window_summary.csv",
        "buy_and_hold_drift_diagnostic.csv",
        "outcome_summary.csv",
        "failure_reasons.csv",
        "next_actions.csv",
        "consistency_check.json",
        "methodology_correction_report.md",
    }
    assert sorted(name for name in required if not (EVIDENCE / name).exists()) == []
    manifest = read_yaml("correction_manifest.yaml")
    assert manifest["correction_id"] == "angl_80_20_portfolio_construction_methodology_correction_v1"
    assert manifest["mode"] == "correction"
    assert manifest["lane"] == "targeted_methodology_correction"
    assert manifest["stage"] == "validation"
    assert manifest["adaptation_label"] == "methodology_correction"
    assert manifest["strategy_id"] == STRATEGY_ID
    assert manifest["prior_method_classification"] == "fixed_weight_return_blend"
    assert manifest["canonical_operational_policy"] == "monthly_rebalanced_80_20"
    assert manifest["diagnostic_policy"] == "initial_80_20_with_natural_drift"
    assert manifest["target_reference_weight"] == 0.8
    assert manifest["target_sleeve_weight"] == 0.2
    assert set(str(int(cost)) for cost in manifest["cost_diagnostics_bps"]) == COSTS
    assert manifest["paper_demo_eligibility_or_activation"] is False
    assert manifest["provider_download"] is False


def test_prior_method_is_classified_and_reproduced_before_correction() -> None:
    classification = read_csv("prior_portfolio_method_classification.csv")[0]
    assert classification["portfolio_method_classification"] == "fixed_weight_return_blend"
    assert classification["daily_holdings_or_weights_available"] == "false"
    assert classification["reported_zero_turnover_correct_for_prior_implementation"] == "true"
    assert classification["tradable_without_implicit_daily_rebalancing"] == "false"
    assert "0.8 * frozen_reference_daily_return + 0.2 * sleeve_daily_return" == classification["code_verified_mechanism"]
    reproduction = read_csv("prior_result_reproduction.csv")
    assert len(reproduction) == 20
    assert {row["portfolio_id"] for row in reproduction} == PORTFOLIO_IDS
    assert {row["reproduction_status"] for row in reproduction} == {"pass"}
    assert all(float(row["absolute_difference"]) <= float(row["tolerance"]) for row in reproduction)


def test_exactly_one_methodology_correction_child_trial() -> None:
    cards = read_csv("strategy_cards.csv")
    trials = read_csv("trial_ledger.csv")
    assert len(cards) == 1
    assert len(trials) == 1
    card = cards[0]
    trial = trials[0]
    assert card["entity_type"] == "strategy_configuration"
    assert trial["entity_type"] == "experiment_trial"
    assert card["strategy_id"] == STRATEGY_ID
    assert trial["trial_id"] == CORRECTION_TRIAL_ID
    assert trial["parent_trial_id"] == PREVIOUS_TRIAL_ID
    assert trial["adaptation_label"] == "methodology_correction"
    assert trial["changed_fields_from_parent"] == "portfolio_construction_accounting_rebalancing_turnover_and_costs_only"
    assert trial["base_strategy_changed"] == "false"
    assert trial["instruments_changed"] == "false"
    assert trial["sleeve_weight_changed"] == "false"
    assert trial["benchmarks_changed"] == "false"
    assert trial["evaluation_dates_selected_from_performance"] == "false"
    assert trial["validation_portfolio_methodology_changed_or_verified"] == "true"
    assert "ANGL|HYG|JNK" == trial["instrument_universe"]


def test_benchmark_and_process_entities_are_not_counted_as_strategies_or_trials() -> None:
    benchmarks = read_csv("benchmark_reference_log.csv")
    process = read_csv("process_task_log.csv")
    assert {row["benchmark_or_control_id"] for row in benchmarks} == {
        "HYG_buy_hold",
        "monthly_rebalanced_50_50_HYG_JNK",
        "frozen_current_active_vm_dsr_usci_combo",
    }
    assert {row["entity_type"] for row in benchmarks} == {"benchmark_reference"}
    assert {row["stage"] for row in benchmarks} == {"benchmark_reference_only"}
    assert {row["counted_as_strategy"] for row in benchmarks} == {"false"}
    assert {row["counted_as_trial"] for row in benchmarks} == {"false"}
    assert len(process) == 1
    assert process[0]["entity_type"] == "process_task"
    assert process[0]["adaptation_label"] == "methodology_correction"
    assert process[0]["strategy_counted"] == "false"
    assert process[0]["trial_counted"] == "false"


def test_canonical_monthly_rebalanced_portfolios_include_turnover_costs_and_events() -> None:
    full = read_csv("canonical_full_period_results.csv")
    turnover = read_csv("turnover_cost_reconciliation.csv")
    events = read_csv("monthly_rebalance_events.csv")
    assert cost_set(full, "portfolio_id") == {portfolio_id: COSTS for portfolio_id in PORTFOLIO_IDS}
    primary = {row["portfolio_id"]: row for row in full if row["cost_assumption_bps"] == "5"}
    assert primary[f"{STRATEGY_ID}_candidate_20pct"]["construction_policy"] == "monthly_rebalanced_80_20"
    assert float(primary[f"{STRATEGY_ID}_candidate_20pct"]["turnover"]) > 1.0
    assert int(primary[f"{STRATEGY_ID}_candidate_20pct"]["rebalance_count"]) == 171
    assert float(primary[f"{STRATEGY_ID}_candidate_20pct"]["transaction_cost_drag"]) > 0.0
    assert primary[f"{STRATEGY_ID}_candidate_20pct"]["invariant_pass"] == "true"
    assert primary["frozen_reference_100pct"]["turnover"] == "0"
    by_turnover = {row["portfolio_id"]: row for row in turnover if row["cost_assumption_bps"] == "5"}
    assert by_turnover[f"{STRATEGY_ID}_candidate_20pct"]["initial_establishment_charged"] == "true"
    assert by_turnover[f"{STRATEGY_ID}_candidate_20pct"]["monthly_rebalance_policy"] == "month_end_signal_next_available_session_close_execution"
    candidate_events = [
        row for row in events if row["portfolio_id"] == f"{STRATEGY_ID}_candidate_20pct" and row["cost_assumption_bps"] == "5"
    ]
    assert len(candidate_events) == int(primary[f"{STRATEGY_ID}_candidate_20pct"]["rebalance_count"])
    assert candidate_events[0]["event_type"] == "initial_establishment"
    assert float(candidate_events[0]["one_way_turnover"]) == pytest.approx(0.5)
    assert candidate_events[1]["event_type"] == "monthly_rebalance_next_session_close"
    assert candidate_events[1]["signal_date"] < candidate_events[1]["event_date"]
    assert {row["post_trade_reference_weight"] for row in candidate_events} == {"0.8"}
    assert {row["post_trade_sleeve_weight"] for row in candidate_events} == {"0.2"}


def test_daily_nav_reconciliation_records_drift_before_rebalancing() -> None:
    rows = read_csv("daily_nav_reconciliation.csv")
    candidate = [
        row for row in rows if row["portfolio_id"] == f"{STRATEGY_ID}_candidate_20pct" and row["cost_assumption_bps"] == "5"
    ]
    assert candidate
    assert candidate[0]["event_type"] == "initial_establishment"
    assert float(candidate[0]["post_trade_sleeve_weight"]) == pytest.approx(0.2)
    monthly_events = [row for row in candidate if row["event_type"] == "monthly_rebalance_next_session_close"]
    assert monthly_events
    assert any(abs(float(row["pretrade_sleeve_weight"]) - 0.2) > 1e-4 for row in monthly_events)
    assert {row["post_trade_sleeve_weight"] for row in monthly_events} == {"0.2"}
    assert all(float(row["max_daily_exposure"]) <= 1.0 + 1e-9 for row in candidate)
    assert all(float(row["max_daily_weight_sum"]) <= 1.0 + 1e-9 for row in candidate)


def test_half_and_rolling_diagnostics_are_visible_not_holdout_claims() -> None:
    halves = read_csv("canonical_chronological_half_results.csv")
    assert {row["half_label"] for row in halves} == {"first_chronological_half", "second_chronological_half"}
    assert {row["half_source"] for row in halves} == {"chronological_half_not_clean_holdout"}
    assert cost_set(halves, "portfolio_id") == {portfolio_id: COSTS for portfolio_id in PORTFOLIO_IDS}
    rows_36 = read_csv("canonical_rolling_36_month_results.csv")
    rows_60 = read_csv("canonical_rolling_60_month_results.csv")
    assert rows_36 and rows_60
    assert {row["control_portfolio_id"] for row in rows_36} == {
        "HYG_buy_hold_20pct_control",
        "monthly_rebalanced_50_50_HYG_JNK_20pct_control",
    }
    assert any(row["control_dominates_angl"] == "true" for row in rows_36)
    assert any(float(row["sharpe_ratio_difference"]) <= 0.0 for row in rows_36)
    summary = {(row["window_months"], row["cost_assumption_bps"]): row for row in read_csv("canonical_rolling_window_summary.csv")}
    assert int(summary[("36", "5")]["window_count"]) == read_json("consistency_check.json")["rolling_36_window_count_primary"]
    assert int(summary[("60", "5")]["window_count"]) == read_json("consistency_check.json")["rolling_60_window_count_primary"]
    assert float(summary[("36", "5")]["positive_sharpe_difference_pct"]) > 0.5
    assert float(summary[("60", "5")]["positive_sharpe_difference_pct"]) > 0.5


def test_drift_diagnostic_is_not_used_as_validation_decision() -> None:
    drift = read_csv("buy_and_hold_drift_diagnostic.csv")
    assert cost_set(drift, "portfolio_id") == {
        f"{STRATEGY_ID}_candidate_20pct": COSTS,
        "HYG_buy_hold_20pct_control": COSTS,
        "monthly_rebalanced_50_50_HYG_JNK_20pct_control": COSTS,
    }
    assert {row["construction_policy"] for row in drift} == {"initial_80_20_with_natural_drift"}
    assert {row["diagnostic_only"] for row in drift} == {"true"}
    assert {row["rebalance_count"] for row in drift if row["cost_assumption_bps"] == "5"} == {"1"}
    summary = read_csv("outcome_summary.csv")[0]
    assert summary["adaptation_label"] == "methodology_correction"
    assert summary["outcome"] in OUTCOME_NEXT_ACTION


def test_outcome_next_action_and_failure_reason_contract() -> None:
    summary = read_csv("outcome_summary.csv")[0]
    next_actions = read_csv("next_actions.csv")
    assert summary["outcome"] in OUTCOME_NEXT_ACTION
    assert summary["next_action"] == OUTCOME_NEXT_ACTION[summary["outcome"]]
    assert {row["exact_next_action"] for row in next_actions} == {summary["next_action"]}
    assert {row["execute_now"] for row in next_actions} == {"false"}
    if summary["outcome"] == "validation_positive":
        assert summary["primary_failure_reason"] == ""
        assert read_csv("failure_reasons.csv") == []
    else:
        assert read_csv("failure_reasons.csv")[0]["primary_failure_reason"] in {
            "weak_vs_primary_control",
            "cost_drag",
            "turnover_drag",
            "period_instability",
            "benchmark_like_behavior",
            "methodology_failure",
            "data_or_comparability_failure",
            "overfit_or_unstable",
        }


def test_protected_state_prior_evidence_cache_and_forbidden_work_unchanged() -> None:
    check = read_json("consistency_check.json")
    assert check["consistency_passed"] is True
    assert check["prior_validation_hashes_unchanged"] is True
    assert check["protected_state_hashes_unchanged"] is True
    assert check["protected_cache_hashes_unchanged"] is True
    assert check["prior_validation_trial_preserved"] is True
    assert check["strategy_definition_changed"] is False
    assert check["base_strategy_changed"] is False
    assert check["instruments_changed"] is False
    assert check["sleeve_weight_changed"] is False
    assert check["benchmarks_changed"] is False
    assert check["evaluation_dates_selected_from_performance"] is False
    for flag in correction.FORBIDDEN_FLAGS:
        assert check[flag] is False


def test_two_component_accounting_is_deterministic_on_toy_data() -> None:
    returns = pd.DataFrame(
        {
            "reference": [0.0, 0.01, -0.005, 0.002],
            "sleeve": [0.0, -0.002, 0.004, 0.006],
        },
        index=pd.to_datetime(["2026-01-30", "2026-02-02", "2026-02-27", "2026-03-02"]),
    )
    first = correction.simulate_two_component_portfolio(returns, "toy", "monthly_rebalanced_80_20", 5.0)
    second = correction.simulate_two_component_portfolio(returns, "toy", "monthly_rebalanced_80_20", 5.0)
    assert first["returns"].equals(second["returns"])
    assert first["turnover"].equals(second["turnover"])
    assert first["event_rows"] == second["event_rows"]
    assert first["event_rows"][0]["one_way_turnover"] == pytest.approx(0.5)
    assert {row["post_trade_sleeve_weight"] for row in first["event_rows"]} == {0.2}
