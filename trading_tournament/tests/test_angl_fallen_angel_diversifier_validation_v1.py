from __future__ import annotations

import csv
import json
from pathlib import Path

import pandas as pd
import pytest
import yaml

from strategy_lab.research_os.research import angl_fallen_angel_diversifier_validation_v1 as validation


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "validation" / "angl_fallen_angel_diversifier_validation_v1" / "latest"
STRATEGY_ID = "ice_vaneck_us_fallen_angel_angl_v1"
PARENT_TRIAL_ID = "rerun_fast_source_v3__ice_vaneck_us_fallen_angel_angl_v1__data_feasibility_adjustment_child"
VALIDATION_TRIAL_ID = "validation_angl__ice_vaneck_us_fallen_angel_angl_v1__validation_variant_child"
PORTFOLIO_IDS = {
    "frozen_reference_100pct",
    f"{STRATEGY_ID}_candidate_20pct",
    "HYG_buy_hold_20pct_control",
    "monthly_rebalanced_50_50_HYG_JNK_20pct_control",
}
STANDALONE_IDS = {"ANGL", "HYG_buy_hold", "monthly_rebalanced_50_50_HYG_JNK"}
ALL_RESULT_IDS = STANDALONE_IDS | PORTFOLIO_IDS
COSTS = {"0", "5", "10"}
OUTCOME_NEXT_ACTION = {
    "validation_positive": "direction_owner_review_angl_paper_demo_eligibility_v1",
    "validation_mixed": "direction_owner_review_angl_validation_mixed_v1",
    "validation_failed": "direction_owner_review_close_angl_after_validation_v1",
    "validation_data_or_methodology_blocked": "direction_owner_review_angl_validation_block_v1",
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


def rows_for_cost(rows: list[dict[str, str]], key: str = "cost_assumption_bps") -> dict[str, set[str]]:
    by_entity: dict[str, set[str]] = {}
    for row in rows:
        entity = row.get("entity_id") or row.get("portfolio_id")
        by_entity.setdefault(entity, set()).add(row[key])
    return by_entity


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
        "portfolio_contribution_results.csv",
        "outcome_summary.csv",
        "failure_reasons.csv",
        "next_actions.csv",
        "consistency_check.json",
        "validation_report.md",
    }
    assert sorted(name for name in required if not (EVIDENCE / name).exists()) == []
    manifest = read_yaml("validation_manifest.yaml")
    assert manifest["validation_id"] == "angl_fallen_angel_diversifier_validation_v1"
    assert manifest["mode"] == "validation"
    assert manifest["lane"] == "validation"
    assert manifest["stage"] == "validation"
    assert manifest["strategy_id"] == STRATEGY_ID
    assert manifest["parent_trial_id"] == PARENT_TRIAL_ID
    assert manifest["validation_trial_id"] == VALIDATION_TRIAL_ID
    assert manifest["primary_cost_assumption_bps"] == 5.0
    assert set(str(int(cost)) for cost in manifest["cost_diagnostics_bps"]) == COSTS
    assert manifest["provider_download"] is False
    assert manifest["source_research_or_completion"] is False
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
    assert trial["strategy_id"] == STRATEGY_ID
    assert card["family_id"] == "fallen_angel_credit_anomaly"
    assert trial["trial_id"] == VALIDATION_TRIAL_ID
    assert trial["parent_trial_id"] == PARENT_TRIAL_ID
    assert trial["adaptation_label"] == "validation_variant"
    assert trial["changed_fields_from_parent"] == "validation_diagnostics_only"
    assert trial["strategy_definition_changed"] == "false"
    assert trial["instruments_changed"] == "false"
    assert trial["parameters_changed"] == "false"
    assert trial["benchmarks_changed"] == "false"
    assert trial["timeframe_selected_from_performance"] == "false"
    assert "ANGL|HYG|JNK" == card["instrument_universe"]
    assert "unknown" not in "|".join(card.values()).lower()
    assert "unknown" not in "|".join(trial.values()).lower()


def test_benchmarks_and_process_entities_are_separate() -> None:
    benchmarks = read_csv("benchmark_reference_log.csv")
    process_rows = read_csv("process_task_log.csv")
    assert {row["benchmark_or_control_id"] for row in benchmarks} == {
        "HYG_buy_hold",
        "monthly_rebalanced_50_50_HYG_JNK",
        "frozen_current_active_vm_dsr_usci_combo",
    }
    assert {row["entity_type"] for row in benchmarks} == {"benchmark_reference"}
    assert {row["stage"] for row in benchmarks} == {"benchmark_reference_only"}
    assert {row["counted_as_strategy"] for row in benchmarks} == {"false"}
    assert {row["counted_as_trial"] for row in benchmarks} == {"false"}
    assert process_rows == [
        {
            "task_id": "angl_fallen_angel_diversifier_validation_v1",
            "entity_type": "process_task",
            "stage": "validation",
            "outcome": read_json("consistency_check.json")["outcome"],
            "exact_next_action": read_json("consistency_check.json")["exact_next_action"],
            "strategy_counted": "false",
            "trial_counted": "false",
        }
    ]


def test_reproduction_gate_passes_for_prior_5bps_results() -> None:
    rows = read_csv("reproduction_check.csv")
    assert len(rows) == 35
    assert {row["entity_id"] for row in rows} == ALL_RESULT_IDS
    assert {row["reproduction_status"] for row in rows} == {"pass"}
    assert {row["tolerance"] for row in rows} == {"1e-09"}
    assert all(float(row["absolute_difference"]) <= float(row["tolerance"]) for row in rows)


def test_full_period_controls_portfolios_costs_and_invariants() -> None:
    rows = read_csv("full_period_results.csv")
    assert rows_for_cost(rows) == {entity_id: COSTS for entity_id in ALL_RESULT_IDS}
    assert {row["timing_invariant_status"] for row in rows} == {"pass_project_shifted_weight_no_lookahead"}
    assert {row["numeric_invariant_status"] for row in rows} == {"pass"}
    assert {row["exposure_invariant_status"] for row in rows} == {"pass"}
    assert {row["weight_invariant_status"] for row in rows} == {"pass"}
    assert {row["invariant_pass"] for row in rows} == {"true"}
    primary = [row for row in rows if row["cost_assumption_bps"] == "5"]
    assert {row["max_daily_exposure"] for row in primary} == {"1"}
    assert {row["max_daily_weight_sum"] for row in primary} == {"1"}


def test_chronological_halves_are_diagnostics_not_clean_holdouts() -> None:
    rows = read_csv("chronological_half_results.csv")
    assert rows_for_cost(rows) == {entity_id: COSTS for entity_id in ALL_RESULT_IDS}
    assert {row["half_label"] for row in rows} == {"first_chronological_half", "second_chronological_half"}
    assert {row["half_source"] for row in rows} == {"chronological_half_not_clean_holdout"}
    assert {row["invariant_pass"] for row in rows} == {"true"}


def assert_true_calendar_windows(rows: list[dict[str, str]], months: int) -> None:
    assert rows
    assert {row["window_months"] for row in rows} == {str(months)}
    for row in rows:
        start = pd.Timestamp(row["window_start"])
        end = pd.Timestamp(row["window_end"])
        cutoff = end - pd.DateOffset(months=months)
        assert start >= cutoff
        assert start <= cutoff + pd.Timedelta(days=7)
        assert int(row["trading_days"]) > 0


def test_rolling_windows_are_true_calendar_spans_and_include_unfavorable_rows() -> None:
    rows_36 = read_csv("rolling_36_month_results.csv")
    rows_60 = read_csv("rolling_60_month_results.csv")
    assert_true_calendar_windows(rows_36, 36)
    assert_true_calendar_windows(rows_60, 60)
    for rows in (rows_36, rows_60):
        assert {row["cost_assumption_bps"] for row in rows} == COSTS
        assert {row["control_portfolio_id"] for row in rows} == {
            "HYG_buy_hold_20pct_control",
            "monthly_rebalanced_50_50_HYG_JNK_20pct_control",
        }
        assert {row["candidate_portfolio_id"] for row in rows} == {f"{STRATEGY_ID}_candidate_20pct"}
        assert {row["timing_invariant_status"] for row in rows} == {"pass_project_shifted_weight_no_lookahead"}
    assert any(row["control_dominates_angl"] == "true" for row in rows_36)
    assert any(float(row["sharpe_ratio_difference"]) <= 0.0 for row in rows_36)
    consistency = read_json("consistency_check.json")
    summary = read_csv("rolling_window_summary.csv")
    primary = {(row["window_months"], row["cost_assumption_bps"]): row for row in summary}
    assert int(primary[("36", "5")]["window_count"]) == consistency["rolling_36_window_count_primary"]
    assert int(primary[("60", "5")]["window_count"]) == consistency["rolling_60_window_count_primary"]


def test_calendar_year_results_are_descriptive_not_trials() -> None:
    rows = read_csv("calendar_year_results.csv")
    assert rows
    assert rows_for_cost(rows) == {entity_id: COSTS for entity_id in ALL_RESULT_IDS}
    assert {"2012", "2026"}.issubset({row["calendar_year"] for row in rows})
    assert len(read_csv("trial_ledger.csv")) == 1


def test_validation_outcome_failure_reason_and_next_action_contract() -> None:
    outcome = read_csv("outcome_summary.csv")[0]
    next_actions = read_csv("next_actions.csv")
    assert outcome["outcome"] in OUTCOME_NEXT_ACTION
    assert outcome["next_action"] == OUTCOME_NEXT_ACTION[outcome["outcome"]]
    assert {row["exact_next_action"] for row in next_actions} == {outcome["next_action"]}
    assert {row["execute_now"] for row in next_actions} == {"false"}
    if outcome["outcome"] == "validation_positive":
        assert outcome["primary_failure_reason"] == ""
        assert read_csv("failure_reasons.csv") == []


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
    assert check["excluded_clare_nvi_and_other_candidates"] is True


def test_generation_is_deterministic() -> None:
    first = read_json("consistency_check.json")
    first_report = (EVIDENCE / "validation_report.md").read_text(encoding="utf-8")
    result = validation.run()
    second = read_json("consistency_check.json")
    assert result["reproduction_passed"] is True
    assert second["consistency_passed"] is True
    assert second["deterministic_core_hash"] == first["deterministic_core_hash"]
    assert (EVIDENCE / "validation_report.md").read_text(encoding="utf-8") == first_report
