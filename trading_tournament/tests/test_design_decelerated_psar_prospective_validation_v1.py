from __future__ import annotations

import csv
import json

import yaml

from strategy_lab.research_os.research import (
    design_decelerated_psar_prospective_validation_v1 as task,
)


OUTPUT = task.OUTPUT_DIR


def rows(name: str) -> list[dict[str, str]]:
    with (OUTPUT / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def json_payload(name: str) -> dict:
    return json.loads((OUTPUT / name).read_text(encoding="utf-8"))


def yaml_payload(name: str) -> dict:
    return yaml.safe_load((OUTPUT / name).read_text(encoding="utf-8"))


def test_required_outputs_and_design_only_entity_counts() -> None:
    assert {path.name for path in OUTPUT.iterdir() if path.is_file()} == (
        task.REQUIRED_OUTPUTS
    )
    manifest = yaml_payload("design_manifest.yaml")
    assert manifest["strategy_configurations_created"] == 0
    assert manifest["experiment_trials_executed"] == 0
    assert manifest["paper_demo_observations"] == 0
    assert manifest["experiment_design_records"] == 1
    assert manifest["process_tasks"] == 1
    assert manifest["benchmark_specifications"] == 7
    assert manifest["data_capability_tasks"] == 0
    assert manifest["historical_calculations_executed"] == 0


def test_future_trial_identity_and_lineage_are_frozen_without_execution() -> None:
    design = rows("experiment_design_record.csv")
    specification = yaml_payload("future_trial_specification.yaml")
    lineage = rows("strategy_and_lineage_reconciliation.csv")
    assert len(design) == 1
    assert design[0]["entity_type"] == "experiment_design"
    assert design[0]["future_trial_id"] == task.FUTURE_TRIAL_ID
    assert design[0]["future_parent_trial_id"] == task.PARENT_TRIAL_ID
    assert design[0]["future_trial_record_executed"] == "false"
    assert design[0]["future_trial_activated"] == "false"
    assert specification["trial_id"] == task.FUTURE_TRIAL_ID
    assert specification["parent_trial_id"] == task.PARENT_TRIAL_ID
    assert specification["adaptation_label"] == (
        "prospective_validation_variant"
    )
    assert specification["changed_fields_from_parent"] == (
        "prospective_evaluation_boundary_only"
    )
    assert specification["record_status"] == (
        "frozen_future_specification_not_executed"
    )
    assert all(value is False for value in specification["flags"].values())
    assert lineage[-3]["record_id"] == task.FUTURE_TRIAL_ID
    assert lineage[-3]["outcome"] == "not_executed_design_only"


def test_strategy_route_parameters_and_claim_remain_frozen() -> None:
    specification = yaml_payload("future_trial_specification.yaml")
    parameters = {
        row["parameter_name"]: row["frozen_value"]
        for row in rows("frozen_parameter_specification.csv")
    }
    assert specification["approved_route"] == "20pct_diversifier_only"
    assert specification["primary_claim"] == (
        "portfolio_downside_and_diversification_value"
    )
    strategy = specification["strategy"]
    assert strategy["AF_min"] == 0.02
    assert strategy["AF_max"] == 0.20
    assert strategy["AF_forward_step"] == 0.02
    assert strategy["AF_backward_step"] == 0.05
    assert strategy["change_period_sessions"] == 3
    assert strategy["change_threshold"] == 0.02
    assert strategy["acceleration_comparison"] == "change3 > 0.02"
    assert strategy["equality_branch"] == "deceleration"
    assert strategy["execution"] == "following_regular_session_close"
    assert strategy["library_PSAR_substitution_permitted"] is False
    assert float(parameters["candidate_sleeve_weight"]) == 0.20


def test_prospective_boundary_and_decision_duration_are_immutable() -> None:
    specification = yaml_payload("future_trial_specification.yaml")
    boundary = specification["prospective_boundary"]
    duration = specification["observation_duration"]
    boundary_rows = rows("activation_boundary_rules.csv")
    assert boundary["historical_forward_rows_prohibited"] is True
    assert boundary["gap_after_2026_06_18_backfill_prohibited"] is True
    assert boundary["historical_returns_as_prospective_observations_prohibited"]
    assert boundary["market_condition_start_selection_prohibited"] is True
    assert duration["minimum_completed_calendar_months"] == 24
    assert duration["minimum_completed_defensive_episodes"] == 6
    assert duration["hard_maximum_completed_calendar_months"] == 36
    assert duration["maximum_boundary_insufficient_episode_outcome"] == (
        "validation_inconclusive_insufficient_events"
    )
    assert duration["interim_decision_permitted"] is False
    assert {row["exception_permitted"] for row in boundary_rows} == {"false"}


def test_exact_symbol_scope_and_snapshot_contract_are_complete() -> None:
    symbols = rows("required_symbol_scope.csv")
    snapshots = {row["field_name"]: row for row in rows(
        "prospective_data_snapshot_schema.csv"
    )}
    assert tuple(row["symbol"] for row in symbols) == (
        task.EXPECTED_REFERENCE_SYMBOLS
    )
    assert len(symbols) == 17
    assert all(row["inferred_from_name"] == "false" for row in symbols)
    assert all(row["future_snapshot_required"] == "true" for row in symbols)
    required_snapshot_fields = {
        "signal_date",
        "retrieval_timestamp_utc",
        "retrieval_timestamp_us_eastern",
        "raw_source_records",
        "raw_source_hash",
        "normalized_frame_hash",
        "PSAR_state_before",
        "calculated_PSAR",
        "acceleration_factor",
        "extreme_point",
        "trend_state",
        "candidate_target",
        "comparator_targets",
        "intended_execution_date",
        "actual_execution_status",
        "blocked_data_reason",
        "inner_turnover",
        "outer_turnover",
        "initialization_turnover",
        "transaction_cost",
        "cost_adjusted_NAV",
    }
    assert required_snapshot_fields <= snapshots.keys()
    assert {
        snapshots[field]["immutable_after_capture"]
        for field in required_snapshot_fields
    } == {"true"}


def test_exact_comparators_costs_and_exposure_control_are_frozen() -> None:
    portfolios = rows("portfolio_and_control_definitions.csv")
    specification = yaml_payload("future_trial_specification.yaml")
    assert tuple(row["portfolio_id"] for row in portfolios) == (
        task.PORTFOLIO_IDS
    )
    assert len(portfolios) == 7
    assert {
        row["portfolio_id"]
        for row in portfolios
        if row["critical_control"] == "true"
    } == set(task.CRITICAL_CONTROLS)
    assert specification["exact_exposure_control"] == {
        "SPY": task.EXACT_EXPOSURE_SPY,
        "BIL": task.EXACT_EXPOSURE_BIL,
        "prospective_recalculation_permitted": False,
    }
    assert specification["costs_bps_per_one_way_turnover"] == {
        "primary": 5.0,
        "diagnostic_ledgers": [0.0, 10.0],
        "diagnostic_rows_create_trials": False,
    }


def test_future_outcomes_and_positive_gate_are_frozen() -> None:
    gates = rows("future_validation_outcome_gates.csv")
    assert tuple(row["future_outcome"] for row in gates) == (
        task.FUTURE_OUTCOMES
    )
    positive = gates[0]
    conditions = set(json.loads(positive["conditions"]))
    assert positive["future_outcome"] == "validation_positive"
    assert positive["decision_timing"] == "after_minimum_boundary_only"
    assert positive["validated_claim"] == (
        "exact_20pct_diversifier_route_under_prospective_snapshot_data"
    )
    assert positive["automatic_paper_demo_eligibility"] == "false"
    assert {
        "at_least_24_completed_months_and_6_completed_defensive_episodes",
        "candidate_reference_Sharpe_improvement_at_least_0_02_or_drawdown_improvement_at_least_0_01",
        "neither_critical_control_dominates_on_CAGR_Sharpe_and_drawdown",
        "reference_drawdown_improved_in_at_least_4_of_first_6_defensive_episodes",
        "at_10bps_candidate_not_worse_than_reference_on_both_Sharpe_and_drawdown",
    } <= conditions


def test_activation_remains_unexecuted_and_consistency_passes() -> None:
    readiness = rows("activation_readiness_checklist.csv")
    next_actions = rows("next_actions.csv")
    check = json_payload("consistency_check.json")
    assert readiness
    assert {row["status_in_design_task"] for row in readiness} == {
        "specified_not_executed"
    }
    assert {row["bounded_readiness_attempts_allowed"] for row in readiness} == {
        "1"
    }
    assert {row["failure_action"] for row in readiness} == {
        "remain_unactivated"
    }
    assert {row["execute_in_this_task"] for row in next_actions} == {"false"}
    assert check["overall_pass"] is True
    assert check["protected_state_unchanged"] is True
    assert check["market_data_caches_unchanged"] is True
    assert check["prior_PSAR_evidence_unchanged"] is True
    assert check["experiment_trials_executed"] == 0
    assert check["historical_calculations_executed"] == 0
    assert check["historical_backfill_performed"] is False
    assert check["trial_activated"] is False
    assert check["provider_access"] is False
    assert check["broker_or_order_action"] is False
    assert check["paper_demo_action"] is False
    assert check["exact_next_action"] == (
        "activate_decelerated_psar_prospective_validation_v1"
    )
