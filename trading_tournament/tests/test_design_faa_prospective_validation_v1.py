from __future__ import annotations

import csv
import json

import yaml

from strategy_lab.research_os.research import (
    design_faa_prospective_validation_v1 as task,
)


OUTPUT = task.OUTPUT_DIR


def rows(name: str) -> list[dict[str, str]]:
    with (OUTPUT / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def json_payload(name: str) -> dict:
    return json.loads((OUTPUT / name).read_text(encoding="utf-8"))


def yaml_payload(name: str) -> dict:
    return yaml.safe_load((OUTPUT / name).read_text(encoding="utf-8"))


def test_required_outputs_and_design_only_counts() -> None:
    assert {path.name for path in OUTPUT.iterdir() if path.is_file()} == (
        task.REQUIRED_OUTPUTS
    )
    manifest = yaml_payload("design_manifest.yaml")
    assert manifest["new_strategy_configurations"] == 0
    assert manifest["experiment_trials_executed"] == 0
    assert manifest["validation_observations"] == 0
    assert manifest["paper_demo_observations"] == 0
    assert manifest["experiment_design_records"] == 1
    assert manifest["future_trial_specifications"] == 1
    assert manifest["benchmark_specifications"] == 7
    assert manifest["process_tasks"] == 1
    assert manifest["data_capability_tasks"] == 0
    assert manifest["historical_performance_recalculated"] is False


def test_future_trial_identity_lineage_and_status_are_frozen() -> None:
    spec = yaml_payload("future_trial_specification.yaml")
    lineage = rows("strategy_and_lineage_reconciliation.csv")
    assert spec["trial_id"] == task.FUTURE_TRIAL_ID
    assert spec["parent_trial_id"] == task.PARENT_TRIAL_ID
    assert spec["adaptation_label"] == "prospective_validation_variant"
    assert spec["changed_fields_from_parent"] == (
        "prospective_evaluation_boundary_only"
    )
    assert spec["record_status"] == "frozen_not_activated"
    assert spec["route"] == "standalone_only"
    assert all(value is False for value in spec["flags"].values())
    assert lineage[-1]["record_type"] == "future_trial_specification"
    assert lineage[-1]["outcome"] == "frozen_not_activated"
    assert lineage[-1]["executed_trial"] == "false"


def test_faa_formula_universe_and_execution_are_exact() -> None:
    spec = yaml_payload("future_trial_specification.yaml")
    symbols = rows("required_symbol_scope.csv")
    parameters = {
        row["parameter_name"]: row["frozen_value"]
        for row in rows("frozen_parameter_specification.csv")
    }
    assert tuple(spec["universe"]) == task.UNIVERSE
    assert tuple(row["symbol"] for row in symbols) == task.UNIVERSE
    assert spec["ranking"]["score"] == (
        "1.0*ReturnRank+0.5*VolatilityRank+0.5*CorrelationRank"
    )
    assert spec["selection_and_allocation"]["selected_count"] == 3
    assert spec["selection_and_allocation"]["zero_or_negative_replacement"] == (
        "SHY"
    )
    assert spec["execution"]["timestamp"] == (
        "following_regular_session_close"
    )
    assert parameters["lookback_months"] == "4"
    assert parameters["volatility_ddof"] == "1"
    assert parameters["route"] == "standalone_only"


def test_primary_claim_is_risk_focused_and_cagr_limit_is_explicit() -> None:
    spec = yaml_payload("future_trial_specification.yaml")
    assert "risk-adjusted and downside behavior" in spec["prospective_claim"]
    limits = spec["claim_limits"]
    assert limits["higher_CAGR_than_return_only_claimed"] is False
    assert limits["historical_return_only_higher_CAGR_limitation_preserved"]
    assert limits["independent_historical_validation_claimed"] is False
    assert limits["paper_demo_eligibility_claimed"] is False


def test_exact_comparators_and_static_weights_are_frozen() -> None:
    controls = rows("portfolio_and_control_definitions.csv")
    static = rows("archived_static_weight_reconciliation.csv")
    assert tuple(row["portfolio_or_control_id"] for row in controls) == (
        task.COMPARATORS
    )
    assert {
        row["portfolio_or_control_id"]
        for row in controls
        if row["critical_control"] == "true"
    } == set(task.CRITICAL_CONTROLS)
    observed = {
        row["symbol"]: float(row["frozen_design_weight"]) for row in static
    }
    assert observed == task.STATIC_WEIGHTS
    assert {row["prospective_recalculation_permitted"] for row in static} == {
        "false"
    }
    assert {row["reconciliation_pass"] for row in static} == {"true"}


def test_daily_and_monthly_snapshots_are_immutable_and_complete() -> None:
    daily = {row["field_name"]: row for row in rows(
        "prospective_daily_snapshot_schema.csv"
    )}
    monthly = {row["field_name"]: row for row in rows(
        "prospective_monthly_formation_schema.csv"
    )}
    assert {
        "symbol",
        "market_date",
        "retrieval_timestamp_utc",
        "retrieval_timestamp_us_eastern",
        "provider",
        "raw_source_identifier",
        "raw_hash",
        "normalized_hash",
        "adjusted_close",
        "data_version_identifier",
        "revision_status",
    } <= daily.keys()
    assert {
        "pairwise_correlations",
        "average_correlation_by_asset",
        "combined_scores",
        "selected_slots",
        "SHY_replacements",
        "candidate_target_vector",
        "comparator_target_vectors",
        "intended_execution_session",
        "monthly_rebalance_turnover",
        "transaction_cost_by_ledger",
        "cost_adjusted_NAV",
    } <= monthly.keys()
    assert {
        row["immutable_after_capture"] for row in list(daily.values()) + list(
            monthly.values()
        )
    } == {"true"}
    assert {
        row["original_rows_overwritable"] for row in list(daily.values()) + list(
            monthly.values()
        )
    } == {"false"}


def test_boundary_and_component_differentiation_are_fixed() -> None:
    spec = yaml_payload("future_trial_specification.yaml")
    differences = rows("component_differentiation_definition.csv")
    boundary = spec["prospective_boundary"]
    minimum = spec["minimum_evidence"]
    assert boundary["initialization_label"] == (
        "initialization_state_input_not_validation_performance"
    )
    assert boundary["gap_after_historical_robustness_end_backfill_permitted"] is False
    assert boundary["retrospective_validation_NAV_permitted"] is False
    assert minimum["minimum_completed_calendar_months"] == 24
    assert minimum["minimum_completed_monthly_holding_intervals"] == 24
    assert minimum["hard_maximum_completed_calendar_months"] == 36
    assert minimum["early_favorable_stop_permitted"] is False
    assert {row["comparison_id"] for row in differences} == set(
        task.CRITICAL_CONTROLS[:2]
    )
    assert {float(row["strict_threshold"]) for row in differences} == {1e-12}


def test_future_outcomes_and_positive_gate_are_complete() -> None:
    gates = rows("future_validation_outcome_gates.csv")
    assert tuple(row["future_outcome"] for row in gates) == task.FUTURE_OUTCOMES
    positive = gates[0]
    conditions = set(json.loads(positive["conditions"]))
    assert {
        "at_least_6_differentiation_months_vs_both_component_controls",
        "neither_return_only_nor_no_correlation_dominates_on_CAGR_Sharpe_drawdown",
        "materiality_vs_each_component_control_Sharpe_0_02_or_drawdown_0_01",
        "static_average_weights_do_not_dominate",
        "return_only_differentiation_average_excess_nonnegative_and_win_rate_over_50pct",
        "no_correlation_differentiation_average_excess_nonnegative_and_win_rate_over_50pct",
    } <= conditions
    assert positive["validated_claim"] == (
        "exact_faa_4m_top3_standalone_configuration_under_prospective_snapshot_data"
    )
    assert positive["automatic_paper_demo_eligibility"] == "false"


def test_activation_readiness_is_specified_but_not_executed() -> None:
    readiness = rows("activation_readiness_checklist.csv")
    next_actions = rows("next_actions.csv")
    assert len(readiness) == 10
    assert {row["status_in_design_task"] for row in readiness} == {
        "specified_not_executed"
    }
    assert {row["bounded_readiness_attempts_allowed"] for row in readiness} == {
        "1"
    }
    assert {row["activation_authorized_in_this_task"] for row in readiness} == {
        "false"
    }
    assert {row["execute_in_this_task"] for row in next_actions} == {"false"}


def test_vix_fix_remains_deferred_without_design_or_trial() -> None:
    rows_ = rows("vix_fix_deferred_state_reconciliation.csv")
    assert len(rows_) == 1
    assert rows_[0]["outcome"] == "robustness_mixed"
    assert rows_[0]["failure_reason"] == "period_instability"
    assert rows_[0]["interpretation"] == (
        "historically_promising_not_ready_for_prospective_validation"
    )
    assert rows_[0]["prospective_validation_design_created"] == "false"
    assert rows_[0]["future_trial_created"] == "false"


def test_consistency_and_exact_next_action_pass() -> None:
    check = json_payload("consistency_check.json")
    assert check["overall_pass"] is True
    assert check["schema_validation_pass"] is True
    assert check["protected_state_and_prior_evidence_unchanged"] is True
    assert check["historical_performance_recalculated"] is False
    assert check["future_trial_activated"] is False
    assert check["provider_access"] is False
    assert check["lifecycle_state_changed"] is False
    assert check["paper_demo_action"] is False
    assert check["broker_or_order_action"] is False
    assert check["exact_next_action"] == task.NEXT_COMPLETED
