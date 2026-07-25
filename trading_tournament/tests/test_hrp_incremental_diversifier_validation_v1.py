from __future__ import annotations

import csv
import json
from pathlib import Path

import pandas as pd
import pytest
import yaml

from strategy_lab.research_os.research import hrp_incremental_diversifier_validation_v1 as validation


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "validation" / "hrp_incremental_diversifier_validation_v1" / "latest"
STRATEGY_ID = "lopez_de_prado_hrp_five_asset_v1"
PARENT_TRIAL_ID = "fast_source_v4__lopez_de_prado_hrp_five_asset_v1__canonical"
VALIDATION_TRIAL_ID = "validation_hrp__lopez_de_prado_hrp_five_asset_v1__validation_variant_child"
STANDALONE_IDS = {
    "HRP",
    "monthly_equal_weight_same_five_etfs",
    "clare_inverse_volatility_five_asset_risk_parity_v1",
    "static_initial_hrp_weight_control",
    "IEF_buy_hold",
    "BIL_cash_proxy",
}
PORTFOLIO_IDS = {
    "frozen_reference_100pct",
    f"{STRATEGY_ID}_candidate_20pct",
    "monthly_equal_weight_same_five_etfs_20pct_control",
    "clare_inverse_volatility_five_asset_risk_parity_v1_20pct_control",
    "static_initial_hrp_weight_control_20pct_control",
    "IEF_single_asset_20pct_control",
    "BIL_cash_20pct_control",
}
ALL_RESULT_IDS = STANDALONE_IDS | PORTFOLIO_IDS
COSTS = {"0", "5", "10"}
NEXT_ACTION_BY_OUTCOME = {
    "validation_positive": "direction_owner_review_hrp_paper_demo_eligibility_v1",
    "validation_mixed": "direction_owner_review_hrp_validation_mixed_v1",
    "validation_failed": "direction_owner_review_close_hrp_after_validation_v1",
    "validation_data_or_methodology_blocked": "direction_owner_review_hrp_validation_block_v1",
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


def costs_by_entity(rows: list[dict[str, str]]) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for row in rows:
        entity = row.get("entity_id") or row.get("portfolio_id")
        out.setdefault(entity, set()).add(row["cost_assumption_bps"])
    return out


def test_required_artifacts_and_manifest_scope() -> None:
    required = {
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
        "hrp_monthly_weights.csv",
        "hrp_weight_concentration_summary.csv",
        "hrp_cluster_ordering_summary.csv",
        "portfolio_contribution_results.csv",
        "portfolio_rebalance_events.csv",
        "turnover_cost_reconciliation.csv",
        "outcome_summary.csv",
        "failure_reasons.csv",
        "next_actions.csv",
        "consistency_check.json",
        "validation_report.md",
    }
    assert sorted(name for name in required if not (EVIDENCE / name).exists()) == []
    manifest = read_yaml("validation_manifest.yaml")
    assert manifest["validation_id"] == "hrp_incremental_diversifier_validation_v1"
    assert manifest["mode"] == "validation"
    assert manifest["lane"] == "validation"
    assert manifest["stage"] == "validation"
    assert manifest["strategy_id"] == STRATEGY_ID
    assert manifest["parent_trial_id"] == PARENT_TRIAL_ID
    assert manifest["validation_trial_id"] == VALIDATION_TRIAL_ID
    assert manifest["frozen_universe"] == ["SPY", "EEM", "IEF", "DBC", "VNQ"]
    assert manifest["lookback_trading_days"] == 252
    assert manifest["covariance_estimator"] == "sample_covariance"
    assert manifest["linkage_method"] == "single"
    assert manifest["tie_breaking_rule"] == "lexical_ticker_order"
    assert set(str(int(cost)) for cost in manifest["cost_diagnostics_bps"]) == COSTS
    assert manifest["provider_download"] is False
    assert manifest["paper_demo_eligibility_or_activation"] is False


def test_single_strategy_card_and_validation_trial_lineage() -> None:
    cards = read_csv("strategy_cards.csv")
    trials = read_csv("trial_ledger.csv")
    assert len(cards) == 1
    assert len(trials) == 1
    card = cards[0]
    trial = trials[0]
    assert card["entity_type"] == "strategy_configuration"
    assert trial["entity_type"] == "experiment_trial"
    assert card["strategy_id"] == STRATEGY_ID
    assert card["stage"] == "validation"
    assert trial["stage"] == "validation"
    assert trial["trial_id"] == VALIDATION_TRIAL_ID
    assert trial["parent_trial_id"] == PARENT_TRIAL_ID
    assert trial["adaptation_label"] == "validation_variant"
    assert trial["changed_fields_from_parent"] == "validation_diagnostics_and_predeclared_simple_controls_only"
    assert trial["strategy_definition_changed"] == "false"
    assert trial["hrp_strategy_definition_changed"] == "false"
    assert trial["parameters_changed"] == "false"
    assert trial["instruments_changed"] == "false"
    assert trial["universe_changed"] == "false"
    assert trial["execution_changed"] == "false"
    assert trial["cost_model_changed"] == "false"
    assert trial["new_validation_controls_added"] == "true"
    assert trial["timeframe_selected_from_results"] == "false"
    assert "unknown" not in "|".join(card.values()).lower()
    assert "unknown" not in "|".join(trial.values()).lower()


def test_benchmark_references_are_separate_and_complete() -> None:
    benchmarks = read_csv("benchmark_reference_log.csv")
    assert {row["benchmark_or_control_id"] for row in benchmarks} == {
        "frozen_current_active_vm_dsr_usci_combo",
        "monthly_equal_weight_same_five_etfs",
        "clare_inverse_volatility_five_asset_risk_parity_v1",
        "static_initial_hrp_weight_control",
        "IEF_single_asset_20pct_control",
        "BIL_cash_20pct_control",
    }
    assert {row["entity_type"] for row in benchmarks} == {"benchmark_reference"}
    assert {row["stage"] for row in benchmarks} == {"benchmark_reference_only"}
    assert {row["counted_as_strategy"] for row in benchmarks} == {"false"}
    assert {row["counted_as_trial"] for row in benchmarks} == {"false"}
    inverse_refs = [row for row in benchmarks if row["benchmark_or_control_id"] == "clare_inverse_volatility_five_asset_risk_parity_v1"]
    assert len(inverse_refs) == 1
    assert inverse_refs[0]["reference_role"] == "same_purpose_control_benchmark_only"


def test_reproduction_gate_passes_for_parent_5bps_results() -> None:
    rows = read_csv("reproduction_check.csv")
    assert rows
    assert {row["reproduction_status"] for row in rows} == {"pass"}
    assert {row["tolerance"] for row in rows} == {"1e-09"}
    assert {
        "HRP",
        "monthly_equal_weight_same_five_etfs",
        "clare_inverse_volatility_five_asset_risk_parity_v1",
        "frozen_reference_100pct",
        f"{STRATEGY_ID}_candidate_20pct",
        "monthly_equal_weight_same_five_etfs_20pct_control",
        "clare_inverse_volatility_five_asset_risk_parity_v1_20pct_control",
    }.issubset({row["entity_id"] for row in rows})
    assert all(float(row["absolute_difference"]) <= float(row["tolerance"]) for row in rows)


def test_full_period_results_have_all_controls_costs_and_invariants() -> None:
    rows = read_csv("full_period_results.csv")
    assert costs_by_entity(rows) == {entity: COSTS for entity in ALL_RESULT_IDS}
    assert {row["timing_invariant_status"] for row in rows} == {"pass"}
    assert {row["numeric_invariant_status"] for row in rows} == {"pass"}
    assert {row["exposure_invariant_status"] for row in rows} == {"pass"}
    assert {row["weight_invariant_status"] for row in rows} == {"pass"}
    assert {row["invariant_pass"] for row in rows} == {"true"}
    primary = [row for row in rows if row["cost_assumption_bps"] == "5"]
    assert all(float(row["max_daily_exposure"]) <= 1.000001 for row in primary)
    assert all(float(row["max_daily_weight_sum"]) <= 1.000001 for row in primary)


def test_portfolio_contribution_uses_monthly_rebalanced_80_20_and_actual_turnover() -> None:
    rows = read_csv("portfolio_contribution_results.csv")
    events = read_csv("portfolio_rebalance_events.csv")
    turnover = read_csv("turnover_cost_reconciliation.csv")
    assert {row["portfolio_id"] for row in rows} == PORTFOLIO_IDS
    assert {row["cost_assumption_bps"] for row in rows} == COSTS
    assert {row["period_label"] for row in rows} == {"full_period", "first_chronological_half", "second_chronological_half"}
    assert {row["half_source"] for row in rows if row["period_label"] != "full_period"} == {"chronological_half_not_clean_holdout"}
    assert all(row["portfolio_construction"] in {"100pct_frozen_reference", "monthly_rebalanced_80_20"} for row in rows)
    candidate_events = [
        row
        for row in events
        if row["portfolio_id"] == f"{STRATEGY_ID}_candidate_20pct" and row["cost_assumption_bps"] == "5"
    ]
    assert candidate_events
    assert candidate_events[0]["event_type"] == "initial_establishment"
    assert any(row["event_type"] == "monthly_rebalance_next_session_close" for row in candidate_events)
    assert any(abs(float(row["pretrade_sleeve_weight"]) - 0.2) > 1e-4 for row in candidate_events[1:])
    assert {row["post_trade_reference_weight"] for row in candidate_events} == {"0.8"}
    assert {row["post_trade_sleeve_weight"] for row in candidate_events} == {"0.2"}
    primary_turnover = {
        row["portfolio_id"] or row["entity_id"]: row
        for row in turnover
        if row["record_scope"] == "portfolio_contribution" and row["cost_assumption_bps"] == "5"
    }
    assert float(primary_turnover[f"{STRATEGY_ID}_candidate_20pct"]["total_one_way_turnover"]) > 0.0
    assert primary_turnover[f"{STRATEGY_ID}_candidate_20pct"]["rebalance_policy"] == "monthly_rebalanced_80_20_with_natural_drift"


def test_chronological_halves_are_diagnostics_not_clean_holdouts() -> None:
    rows = read_csv("chronological_half_results.csv")
    assert {row["half_label"] for row in rows} == {"first_chronological_half", "second_chronological_half"}
    assert {row["half_source"] for row in rows} == {"chronological_half_not_clean_holdout"}
    assert {row["invariant_pass"] for row in rows} == {"true"}
    assert "clean_holdout" not in (EVIDENCE / "validation_report.md").read_text(encoding="utf-8")


def assert_rolling_windows(rows: list[dict[str, str]], months: int) -> None:
    assert rows
    assert {row["window_months"] for row in rows} == {str(months)}
    assert {row["cost_assumption_bps"] for row in rows} == COSTS
    assert {row["candidate_portfolio_id"] for row in rows} == {f"{STRATEGY_ID}_candidate_20pct"}
    assert {row["control_portfolio_id"] for row in rows} == PORTFOLIO_IDS - {
        "frozen_reference_100pct",
        f"{STRATEGY_ID}_candidate_20pct",
    }
    for row in rows[:20]:
        start = pd.Timestamp(row["window_start"])
        end = pd.Timestamp(row["window_end"])
        cutoff = end - pd.DateOffset(months=months)
        assert start >= cutoff
        assert start <= cutoff + pd.Timedelta(days=7)


def test_rolling_windows_compare_against_all_controls_and_keep_unfavorable_results() -> None:
    rows_36 = read_csv("rolling_36_month_results.csv")
    rows_60 = read_csv("rolling_60_month_results.csv")
    assert_rolling_windows(rows_36, 36)
    assert_rolling_windows(rows_60, 60)
    assert any(row["control_dominates_hrp"] == "true" for row in rows_36)
    assert any(row["control_dominates_hrp"] == "true" for row in rows_60)
    assert any(float(row["sharpe_ratio_difference"]) <= 0.0 for row in rows_36)
    summary = read_csv("rolling_window_summary.csv")
    check = read_json("consistency_check.json")
    primary = {(row["window_months"], row["cost_assumption_bps"]): row for row in summary}
    assert int(primary[("36", "5")]["window_count"]) == check["rolling_36_window_count_primary"]
    assert int(primary[("60", "5")]["window_count"]) == check["rolling_60_window_count_primary"]


def test_hrp_weight_and_cluster_diagnostics_are_visible() -> None:
    rows = read_csv("hrp_monthly_weights.csv")
    summary = read_csv("hrp_weight_concentration_summary.csv")
    clusters = read_csv("hrp_cluster_ordering_summary.csv")
    check = read_json("consistency_check.json")
    assert len(rows) == check["hrp_monthly_weight_rows"]
    assert rows
    assert clusters
    assert {row["instrument"] for row in summary if row["summary_scope"] == "instrument_weight"} == {
        "SPY",
        "EEM",
        "IEF",
        "DBC",
        "VNQ",
    }
    assert any(row["warmup_equal_weight"] == "true" for row in rows)
    assert any(row["cluster_ordering"] != "equal_weight_warmup" for row in rows)
    concentration = next(row for row in summary if row["summary_scope"] == "portfolio_concentration")
    assert float(concentration["median_effective_number_of_holdings"]) > 0.0
    assert int(concentration["unique_cluster_ordering_count"]) >= 1
    weights = check["static_initial_hrp_frozen_weights"]
    assert abs(sum(float(value) for value in weights.values()) - 1.0) < 1e-9
    assert check["static_initial_hrp_warmup_behavior"] == "monthly_equal_weight_until_first_valid_252_day_hrp_signal"


def test_calendar_year_results_are_descriptive_not_trials() -> None:
    rows = read_csv("calendar_year_results.csv")
    assert rows
    assert STANDALONE_IDS.issubset(set(costs_by_entity(rows)))
    assert PORTFOLIO_IDS.issubset(set(costs_by_entity(rows)))
    assert len(read_csv("trial_ledger.csv")) == 1


def test_validation_outcome_failure_reason_and_next_action_contract() -> None:
    outcome = read_csv("outcome_summary.csv")[0]
    failures = read_csv("failure_reasons.csv")
    next_actions = read_csv("next_actions.csv")
    assert outcome["outcome"] in NEXT_ACTION_BY_OUTCOME
    assert outcome["next_action"] == NEXT_ACTION_BY_OUTCOME[outcome["outcome"]]
    assert {row["exact_next_action"] for row in next_actions} == {outcome["next_action"]}
    assert {row["execute_now"] for row in next_actions} == {"false"}
    if outcome["outcome"] == "validation_failed":
        assert outcome["primary_failure_reason"] in validation.ALLOWED_FAILURE_REASONS
        assert failures == [
            {
                "strategy_id": STRATEGY_ID,
                "family_id": "hierarchical_risk_parity_allocation",
                "trial_id": VALIDATION_TRIAL_ID,
                "stage": "validation",
                "outcome": "validation_failed",
                "primary_failure_reason": outcome["primary_failure_reason"],
                "decision_reason": outcome["decision_reason"],
            }
        ]


def test_protected_state_inputs_cache_and_forbidden_work_unchanged() -> None:
    check = read_json("consistency_check.json")
    assert check["consistency_passed"] is True
    assert check["protected_state_hashes_unchanged"] is True
    assert check["input_evidence_hashes_unchanged"] is True
    assert check["protected_cache_hashes_unchanged"] is True
    assert check["prior_exploratory_state"]["stage"] == "exploratory_followup_diversifier"
    assert check["prior_exploratory_state"]["outcome"] == "exploratory_followup_candidate_diversifier"
    for flag in validation.FORBIDDEN_FLAGS:
        assert check[flag] is False


def test_generation_is_deterministic() -> None:
    first = read_json("consistency_check.json")
    first_report = (EVIDENCE / "validation_report.md").read_text(encoding="utf-8")
    result = validation.run()
    second = read_json("consistency_check.json")
    assert result["reproduction_passed"] is True
    assert second["consistency_passed"] is True
    assert second["deterministic_core_hash"] == first["deterministic_core_hash"]
    assert (EVIDENCE / "validation_report.md").read_text(encoding="utf-8") == first_report
