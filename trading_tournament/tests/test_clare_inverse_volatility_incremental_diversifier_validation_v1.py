from __future__ import annotations

import csv
import json
from pathlib import Path

import pandas as pd
import pytest
import yaml

from strategy_lab.research_os.research import clare_inverse_volatility_incremental_diversifier_validation_v1 as validation


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "validation" / validation.VALIDATION_ID / "latest"
STRATEGY_ID = validation.STRATEGY_ID
PARENT_TRIAL_ID = (
    "rerun_fast_source_v3__clare_inverse_volatility_five_asset_risk_parity_v1__"
    "data_feasibility_adjustment_child"
)
COSTS = {"0", "5", "10"}
CONTROL_IDS = {
    "monthly_equal_weight_same_five_etfs",
    "initial_equal_weight_same_five_etfs_buy_and_hold",
    "static_initial_inverse_volatility_weight_control",
    "IEF_single_asset_20pct_control",
    "BIL_cash_20pct_control",
}
PORTFOLIO_IDS = {
    "frozen_reference_100pct",
    f"{STRATEGY_ID}_candidate_20pct",
    "monthly_equal_weight_same_five_etfs_20pct_control",
    "initial_equal_weight_same_five_etfs_buy_and_hold_20pct_control",
    "static_initial_inverse_volatility_weight_control_20pct_control",
    "IEF_single_asset_20pct_control",
    "BIL_cash_20pct_control",
}


@pytest.fixture(scope="module", autouse=True)
def generated_validation() -> dict[str, object]:
    return validation.run()


def read_csv(name: str) -> list[dict[str, str]]:
    with (EVIDENCE / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_json(name: str) -> dict[str, object]:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def read_yaml(name: str) -> dict[str, object]:
    return yaml.safe_load((EVIDENCE / name).read_text(encoding="utf-8"))


def test_required_artifacts_and_frozen_manifest() -> None:
    required = {
        "validation_manifest.yaml",
        "strategy_cards.csv",
        "trial_ledger.csv",
        "benchmark_reference_log.csv",
        "process_task_log.csv",
        "reproduction_check.csv",
        "full_period_results.csv",
        "chronological_half_results.csv",
        "rolling_36_month_results.csv",
        "rolling_60_month_results.csv",
        "rolling_window_summary.csv",
        "calendar_year_results.csv",
        "monthly_weight_diagnostics.csv",
        "weight_concentration_summary.csv",
        "portfolio_contribution_results.csv",
        "portfolio_rebalance_events.csv",
        "turnover_cost_reconciliation.csv",
        "outcome_summary.csv",
        "failure_reasons.csv",
        "next_actions.csv",
        "consistency_check.json",
        "validation_report.md",
    }
    assert not [name for name in required if not (EVIDENCE / name).exists()]
    manifest = read_yaml("validation_manifest.yaml")
    assert manifest["validation_id"] == validation.VALIDATION_ID
    assert manifest["mode"] == manifest["lane"] == manifest["stage"] == "validation"
    assert manifest["strategy_id"] == STRATEGY_ID
    assert manifest["parent_trial_id"] == PARENT_TRIAL_ID
    assert manifest["frozen_universe"] == ["SPY", "EEM", "IEF", "DBC", "VNQ"]
    assert manifest["volatility_window_months"] == 12
    assert manifest["sample_standard_deviation_ddof"] == 1
    assert manifest["weighting_rule"] == "inverse_volatility_normalized_to_1"
    assert manifest["provider_download"] is False
    assert manifest["paper_demo_eligibility_or_activation"] is False


def test_exactly_one_strategy_and_one_child_trial() -> None:
    cards = read_csv("strategy_cards.csv")
    trials = read_csv("trial_ledger.csv")
    assert len(cards) == len(trials) == 1
    assert cards[0]["strategy_id"] == STRATEGY_ID
    assert cards[0]["entity_type"] == "strategy_configuration"
    assert cards[0]["strategy_architecture"] == "monthly_inverse_volatility_multi_asset_allocation"
    assert cards[0]["source_or_research_lineage"] == "strategy_source_library_refresh_v1__clare_inverse_volatility"
    assert trials[0]["entity_type"] == "experiment_trial"
    assert trials[0]["trial_id"] == validation.VALIDATION_TRIAL_ID
    assert trials[0]["parent_trial_id"] == PARENT_TRIAL_ID
    assert trials[0]["adaptation_label"] == "validation_variant"
    assert (
        trials[0]["changed_fields_from_parent"]
        == "validation_diagnostics_and_predeclared_static_and_simple_exposure_controls_only"
    )
    for field in (
        "strategy_definition_changed",
        "parameters_changed",
        "instruments_changed",
        "universe_changed",
        "execution_changed",
        "cost_model_changed",
        "optimization_performed",
        "timeframe_selected_from_results",
    ):
        assert trials[0][field] == "false"
    assert trials[0]["new_validation_controls_added"] == "true"
    assert "unknown" not in "|".join(cards[0].values()).lower()
    assert "unknown" not in "|".join(trials[0].values()).lower()


def test_benchmarks_and_process_task_remain_separate_entities() -> None:
    benchmarks = read_csv("benchmark_reference_log.csv")
    assert {row["benchmark_or_control_id"] for row in benchmarks} == {
        "frozen_current_active_vm_dsr_usci_combo",
        *CONTROL_IDS,
    }
    assert {row["entity_type"] for row in benchmarks} == {"benchmark_reference"}
    assert {row["stage"] for row in benchmarks} == {"benchmark_reference_only"}
    assert {row["counted_as_strategy"] for row in benchmarks} == {"false"}
    assert {row["counted_as_trial"] for row in benchmarks} == {"false"}
    process = read_csv("process_task_log.csv")
    assert len(process) == 1
    assert process[0]["entity_type"] == "process_task"
    assert process[0]["stage"] == "validation"


def test_legacy_parent_reproduction_gate_passes() -> None:
    rows = read_csv("reproduction_check.csv")
    assert rows
    assert {row["reproduction_status"] for row in rows} == {"pass"}
    assert {row["reproduction_method"] for row in rows} == {"legacy_exploratory_accounting_replay_only"}
    expected = {
        STRATEGY_ID,
        "monthly_equal_weight_same_five_etfs",
        "initial_equal_weight_no_rebalance",
        "frozen_reference_100pct",
        f"{STRATEGY_ID}_candidate_20pct",
        "monthly_equal_weight_same_five_etfs_20pct_control",
        "initial_equal_weight_no_rebalance_20pct_control",
    }
    assert expected.issubset({row["entity_id"] for row in rows})
    assert all(float(row["absolute_difference"]) <= float(row["tolerance"]) for row in rows)


def test_dynamic_weights_use_frozen_12_month_ddof_one_formula() -> None:
    rows = read_csv("monthly_weight_diagnostics.csv")
    assert rows
    non_warmup = next(row for row in rows if row["warmup_equal_weight"] == "false")
    prices = validation.accounting.load_price_frame(validation.SYMBOLS)
    monthly_returns = validation.monthly_return_frame(prices)
    signal_date = pd.Timestamp(non_warmup["signal_date"])
    expected = validation.inverse_volatility_weights_from_monthly_returns(
        monthly_returns.loc[:signal_date].tail(12)
    )
    for symbol in validation.SYMBOLS:
        assert float(non_warmup[f"{symbol}_weight"]) == pytest.approx(expected[symbol], abs=1e-12)
    assert sum(float(non_warmup[f"{symbol}_weight"]) for symbol in validation.SYMBOLS) == pytest.approx(1.0)
    assert any(row["warmup_equal_weight"] == "true" for row in rows)


def test_full_results_costs_and_invariants() -> None:
    rows = read_csv("full_period_results.csv")
    by_entity: dict[str, set[str]] = {}
    for row in rows:
        by_entity.setdefault(row["entity_id"], set()).add(row["cost_assumption_bps"])
    assert all(costs == COSTS for costs in by_entity.values())
    assert {row["timing_invariant_status"] for row in rows} == {"pass"}
    assert {row["numeric_invariant_status"] for row in rows} == {"pass"}
    assert {row["exposure_invariant_status"] for row in rows} == {"pass"}
    assert {row["weight_invariant_status"] for row in rows} == {"pass"}
    assert {row["invariant_pass"] for row in rows} == {"true"}
    assert all(float(row["max_daily_exposure"]) <= 1.000001 for row in rows)
    assert all(float(row["max_daily_weight_sum"]) <= 1.000001 for row in rows)


def test_portfolios_use_monthly_rebalanced_holdings_with_drift_and_costs() -> None:
    rows = read_csv("portfolio_contribution_results.csv")
    events = read_csv("portfolio_rebalance_events.csv")
    assert {row["portfolio_id"] for row in rows} == PORTFOLIO_IDS
    assert {row["cost_assumption_bps"] for row in rows} == COSTS
    assert {row["period_label"] for row in rows} == {
        "full_period",
        "first_chronological_half",
        "second_chronological_half",
    }
    assert all(
        row["portfolio_construction"] in {"100pct_frozen_reference", "monthly_rebalanced_80_20"}
        for row in rows
    )
    candidate_events = [
        row
        for row in events
        if row["portfolio_id"] == f"{STRATEGY_ID}_candidate_20pct"
        and row["cost_assumption_bps"] == "5"
    ]
    assert candidate_events[0]["event_type"] == "initial_establishment"
    assert any(row["event_type"] == "monthly_rebalance_next_session_close" for row in candidate_events)
    assert any(abs(float(row["pretrade_sleeve_weight"]) - 0.2) > 1e-4 for row in candidate_events[1:])
    assert {row["post_trade_reference_weight"] for row in candidate_events} == {"0.8"}
    assert {row["post_trade_sleeve_weight"] for row in candidate_events} == {"0.2"}
    assert sum(float(row["one_way_turnover"]) for row in candidate_events) > 0.0
    assert sum(float(row["transaction_cost_drag"]) for row in candidate_events) > 0.0


def test_rolling_windows_include_every_predeclared_control() -> None:
    expected_controls = PORTFOLIO_IDS - {
        "frozen_reference_100pct",
        f"{STRATEGY_ID}_candidate_20pct",
    }
    for months in (36, 60):
        rows = read_csv(f"rolling_{months}_month_results.csv")
        assert rows
        assert {row["window_months"] for row in rows} == {str(months)}
        assert {row["control_portfolio_id"] for row in rows} == expected_controls
        assert {row["cost_assumption_bps"] for row in rows} == COSTS
        assert any(row["control_dominates_inverse_volatility"] == "true" for row in rows)
        assert any(float(row["sharpe_ratio_difference"]) <= 0.0 for row in rows)


def test_halves_and_calendar_years_are_diagnostics_not_trials() -> None:
    halves = read_csv("chronological_half_results.csv")
    assert {row["half_label"] for row in halves} == {
        "first_chronological_half",
        "second_chronological_half",
    }
    assert {row["half_source"] for row in halves} == {"chronological_half_not_clean_holdout"}
    assert read_csv("calendar_year_results.csv")
    assert len(read_csv("trial_ledger.csv")) == 1
    report = (EVIDENCE / "validation_report.md").read_text(encoding="utf-8").lower()
    assert "no chronological half is treated as a clean or sealed holdout" in report


def test_outcome_reason_and_next_action_contract() -> None:
    outcome = read_csv("outcome_summary.csv")[0]
    assert outcome["outcome"] == "validation_failed"
    assert outcome["primary_failure_reason"] == "benchmark_like_behavior"
    assert (
        outcome["decision_reason"]
        == "static_initial_inverse_volatility_control_replicates_or_exceeds_dynamic_inverse_volatility"
    )
    assert outcome["next_action"] == "direction_owner_review_close_inverse_volatility_after_validation_v1"
    assert {row["exact_next_action"] for row in read_csv("next_actions.csv")} == {
        outcome["next_action"]
    }
    assert {row["execute_now"] for row in read_csv("next_actions.csv")} == {"false"}


def test_protected_state_prior_evidence_and_cache_are_unchanged() -> None:
    check = read_json("consistency_check.json")
    assert check["consistency_passed"] is True
    assert check["protected_state_hashes_unchanged"] is True
    assert check["input_evidence_hashes_unchanged"] is True
    assert check["protected_cache_hashes_unchanged"] is True
    assert check["prior_exploratory_state"] == {
        "stage": "exploratory_followup_diversifier",
        "outcome": "exploratory_followup_candidate_diversifier",
    }
    for flag in validation.FORBIDDEN_FLAGS:
        assert check[flag] is False


def test_generation_is_deterministic() -> None:
    first = read_json("consistency_check.json")
    first_report = (EVIDENCE / "validation_report.md").read_text(encoding="utf-8")
    result = validation.run()
    second = read_json("consistency_check.json")
    assert result["reproduction_passed"] is True
    assert result["outcome"] == "validation_failed"
    assert second["deterministic_core_hash"] == first["deterministic_core_hash"]
    assert (EVIDENCE / "validation_report.md").read_text(encoding="utf-8") == first_report
