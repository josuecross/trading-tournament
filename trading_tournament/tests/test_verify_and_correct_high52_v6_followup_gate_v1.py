from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
import pytest
import yaml

from strategy_lab.research_os.research import fast_source_library_batch_v6 as v6
from strategy_lab.research_os.research import (
    verify_and_correct_high52_v6_followup_gate_v1 as verification,
)


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = (
    ROOT
    / "evidence"
    / "correction"
    / verification.TASK_ID
    / "latest"
)

REQUIRED_ARTIFACTS = {
    "verification_manifest.yaml",
    "strategy_cards.csv",
    "trial_ledger.csv",
    "benchmark_reference_log.csv",
    "process_task_log.csv",
    "frozen_gate_specification.csv",
    "metric_reproduction.csv",
    "chronological_half_gate_check.csv",
    "full_gate_recalculation.csv",
    "gate_logic_root_cause.csv",
    "decision_override.csv",
    "code_change_manifest.csv",
    "outcome_summary.csv",
    "failure_reasons.csv",
    "next_actions.csv",
    "consistency_check.json",
    "verification_report.md",
}


@pytest.fixture(scope="module", autouse=True)
def evidence_ready() -> None:
    assert (EVIDENCE / "consistency_check.json").exists(), (
        "Run the targeted High52 verification runner before focused tests."
    )


def rows(name: str) -> list[dict[str, str]]:
    with (EVIDENCE / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def json_payload(name: str) -> dict:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def yaml_payload(name: str) -> dict:
    return yaml.safe_load((EVIDENCE / name).read_text(encoding="utf-8"))


def test_required_artifacts_and_exact_scope() -> None:
    assert REQUIRED_ARTIFACTS.issubset({path.name for path in EVIDENCE.iterdir()})
    manifest = yaml_payload("verification_manifest.yaml")
    assert manifest["task_id"] == verification.TASK_ID
    assert manifest["mode"] == "verify"
    assert manifest["stage"] == "verification"
    assert manifest["strategy_id"] == verification.STRATEGY_ID
    assert manifest["frozen_same_purpose_control"] == (
        "six_month_total_return_top3_overlapping"
    )
    assert manifest["primary_cost_bps"] == 5.0


def test_metric_reproduction_and_disputed_values() -> None:
    reproduction = rows("metric_reproduction.csv")
    assert len(reproduction) == 36
    assert {row["reproduction_pass"] for row in reproduction} == {"true"}
    assert max(
        float(row["maximum_absolute_numeric_difference"])
        for row in reproduction
    ) <= verification.REPRODUCTION_TOLERANCE
    second = rows("chronological_half_gate_check.csv")[1]
    assert second["period_label"] == "second_chronological_half"
    assert np.isclose(float(second["candidate_sharpe_ratio"]), 0.694485051656)
    assert np.isclose(
        float(second["candidate_maximum_drawdown"]), -0.319632637644
    )
    assert np.isclose(float(second["control_sharpe_ratio"]), 0.778221568029)
    assert np.isclose(
        float(second["control_maximum_drawdown"]), -0.318726423146
    )


def test_literal_half_gate_regression_worse_on_both_fails() -> None:
    candidate = {
        "sharpe_ratio": 0.694485051656,
        "maximum_drawdown": -0.319632637644,
    }
    control = {
        "sharpe_ratio": 0.778221568029,
        "maximum_drawdown": -0.318726423146,
    }
    assert v6.worse_on_both_sharpe_and_drawdown(candidate, control) is True
    half_rows = rows("chronological_half_gate_check.csv")
    first, second = half_rows
    assert first["half_period_gate_failed"] == "false"
    assert second["candidate_worse_on_sharpe"] == "true"
    assert second["candidate_worse_on_drawdown"] == "true"
    assert second["and_operator_required"] == "true"
    assert second["half_period_gate_failed"] == "true"
    assert second["decision_tolerance_used"] == "false"


def test_full_frozen_gate_recalculation_closes_requirement_five() -> None:
    gate = rows("full_gate_recalculation.csv")
    assert [int(row["requirement_id"]) for row in gate] == list(range(1, 8))
    failed = [
        int(row["requirement_id"])
        for row in gate
        if row["requirement_pass"] == "false"
    ]
    assert failed == [5]
    requirement_five = gate[4]
    assert verification.DECISION_REASON in requirement_five["failure_detail"]
    assert all(
        row["post_result_exception_allowed"] == "false"
        for row in rows("frozen_gate_specification.csv")
    )


def test_root_cause_is_wrong_control_not_performance_calculation() -> None:
    causes = {row["check_id"]: row for row in rows("gate_logic_root_cause.csv")}
    wrong_control = causes["comparison_control_selection"]
    assert wrong_control["defect_present"] == "true"
    assert wrong_control["causal"] == "true"
    assert "monthly_equal_weight_nine_sector" in wrong_control["finding"]
    assert "six_month_total_return_top3_overlapping" in wrong_control["finding"]
    assert causes["maximum_drawdown_sign"]["defect_present"] == "false"
    assert causes["and_vs_or"]["defect_present"] == "false"
    assert causes["rounded_values"]["defect_present"] == "false"
    assert causes["hidden_decision_tolerance"]["causal"] == "false"


def test_high52_uses_explicit_frozen_control_and_other_selection_is_unchanged() -> None:
    high52 = next(card for card in v6.CARDS if card.strategy_id == verification.STRATEGY_ID)
    controls = {
        "six_month_total_return_top3_overlapping": {
            "sharpe_ratio": 0.586978844354,
            "maximum_drawdown": -0.492414600703,
        },
        "monthly_equal_weight_nine_sector": {
            "sharpe_ratio": 0.595329490792,
            "maximum_drawdown": -0.532794339966,
        },
    }
    selected, _ = v6.followup_gate_control(high52, controls)
    assert selected == "six_month_total_return_top3_overlapping"

    recovery = next(card for card in v6.CARDS if card.strategy_id.startswith("choi_"))
    recovery_controls = {
        "six_week_cumulative_return_bottom3_overlapping": {
            "sharpe_ratio": 0.517028978696,
            "maximum_drawdown": -0.595428872513,
        },
        "weekly_equal_weight_nine_sector": {
            "sharpe_ratio": 0.598251927254,
            "maximum_drawdown": -0.528582897136,
        },
    }
    original, _ = v6.best_by_sharpe(recovery_controls)
    corrected, _ = v6.followup_gate_control(recovery, recovery_controls)
    assert corrected == original == "weekly_equal_weight_nine_sector"


def test_decision_override_and_entity_counts() -> None:
    decision = rows("decision_override.csv")
    assert len(decision) == 1
    assert decision[0]["original_outcome"] == (
        "exploratory_followup_candidate_standalone"
    )
    assert decision[0]["corrected_stage"] == "closed"
    assert decision[0]["corrected_outcome"] == "closed_exploration"
    assert decision[0]["failure_reason"] == "period_instability"
    assert decision[0]["decision_reason"] == verification.DECISION_REASON
    assert decision[0]["project_next_action"] == verification.PROJECT_NEXT_ACTION
    assert decision[0]["new_experiment_trial_created"] == "false"

    strategies = rows("strategy_cards.csv")
    trials = rows("trial_ledger.csv")
    benchmarks = rows("benchmark_reference_log.csv")
    process = rows("process_task_log.csv")
    assert len(strategies) == len(trials) == len(process) == 1
    assert len(benchmarks) == 3
    assert strategies[0]["entity_type"] == "strategy_configuration"
    assert strategies[0]["strategy_configuration_created_in_task"] == "false"
    assert strategies[0]["strategy_configuration_carried_forward"] == "true"
    assert trials[0]["entity_type"] == "experiment_trial"
    assert trials[0]["stage"] == "exploration"
    assert trials[0]["parent_trial_id"] == ""
    assert trials[0]["adaptation_label"] == ""
    assert trials[0]["read_only"] == "true"
    assert trials[0]["experiment_trial_created_in_task"] == "false"
    assert {row["entity_type"] for row in benchmarks} == {"benchmark_reference"}
    assert {row["stage"] for row in benchmarks} == {"benchmark_reference_only"}
    assert process[0]["entity_type"] == "process_task"
    assert process[0]["adaptation_label"] == "methodology_correction"


def test_consistency_hashes_and_prohibited_actions() -> None:
    check = json_payload("consistency_check.json")
    assert check["consistency_passed"] is True
    assert check["original_v6_evidence_unchanged"] is True
    assert check["protected_state_unchanged"] is True
    assert check["cache_unchanged"] is True
    assert check["prior_evidence_unchanged"] is True
    assert check["frozen_source_packet_unchanged"] is True
    assert check["unrelated_v6_strategy_outcomes_unchanged"] is True
    assert check["strategy_results_changed"] is False
    assert check["strategy_definition_changed"] is False
    assert check["strategy_configurations_created"] == 0
    assert check["experiment_trials_created"] == 0
    assert check["validation_trials_created"] == 0
    assert check["lifecycle_records_changed"] == 0
    assert check["validation_executed"] is False
    assert check["provider_accessed"] is False
    assert check["paper_demo_action_taken"] is False
    assert check["broker_or_order_action_taken"] is False
    assert check["exact_next_action"] == verification.PROJECT_NEXT_ACTION
    assert check["next_action_executed"] is False
