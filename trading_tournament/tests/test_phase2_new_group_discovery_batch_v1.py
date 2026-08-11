from __future__ import annotations

import csv
import json
import math

import numpy as np
import pytest

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.research import phase2_new_group_discovery_batch_v1 as subject


OUTPUT = ROOT / "evidence" / "research_recovery" / subject.TASK_ID / "latest"
INTAKE = ROOT / "evidence" / "public_source_strategy_intake" / subject.INTAKE_ID / "latest"


def rows(directory, name: str) -> list[dict[str, str]]:
    with (directory / name).open("r", newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


@pytest.fixture(scope="module", autouse=True)
def completed_run() -> dict[str, object]:
    result = subject.run()
    assert result["overall_pass"] is True
    return result


def test_intake_scope_is_exact_and_materialized_before_research() -> None:
    consistency = json.loads((INTAKE / "consistency_check.json").read_text(encoding="utf-8"))
    assert consistency["overall_pass"] is True
    assert consistency["selected_external_strategies"] == 0
    assert consistency["selected_internal_architectures"] == 1
    assert consistency["proposed_canonical_trials"] == 4
    assert consistency["unresolved_material_fields"] == 0
    assert consistency["provider_requirements"] == 0
    assert {path.name for path in INTAKE.iterdir() if path.is_file()} == subject.REQUIRED_INTAKE_OUTPUTS


def test_phase2_hash_pair_mapping_and_accepted_symbols() -> None:
    hash_rows = rows(OUTPUT, "phase2_universe_hash_reconciliation.csv")
    assert hash_rows[0]["observed_hash"] == subject.EXPECTED_UNIVERSE_HASH
    assert hash_rows[0]["status"] == "pass"
    mapping = rows(OUTPUT, "pair_mapping.csv")
    assert tuple((row["industry"], row["parent_sector"]) for row in mapping) == subject.PAIR_MAPPINGS
    assert all(row["membership_source"] == "phase2_nonperformance_addition" for row in mapping)
    preflight = rows(OUTPUT, "data_preflight_reconciliation.csv")
    assert {row["symbol"] for row in preflight} == set(subject.ACCOUNTING_UNIVERSE)
    assert all(row["accepted_symbol"] == "true" and row["status"] == "pass" for row in preflight)


def test_relative_log_return_and_persistence_fixtures() -> None:
    parent_values = np.ones(5)
    industry = np.exp(np.array([0.0, 0.1, 0.2, 0.3, 0.4]))
    rel1, rel2, score = subject.relative_fixture(industry, parent_values, 4)
    assert rel1 == pytest.approx(0.2)
    assert rel2 == pytest.approx(0.2)
    assert score == pytest.approx(0.2)

    reversal = np.exp(np.array([0.0, 0.1, 0.2, 0.15, 0.1]))
    rel1, rel2, score = subject.relative_fixture(reversal, parent_values, 4)
    assert rel1 > 0.0
    assert rel2 < 0.0
    assert score == rel2
    assert rel1 + rel2 > 0.0


def test_fixed_slot_target_and_explicit_parent_zeroes() -> None:
    target = subject.fixed_slot_target(["IBB", "SMH"], 3)
    assert target["IBB"] == pytest.approx(1.0 / 3.0)
    assert target["SMH"] == pytest.approx(1.0 / 3.0)
    assert target["BIL"] == pytest.approx(1.0 / 3.0)
    assert sum(target.values()) == pytest.approx(1.0)
    assert all(target[parent] == 0.0 for parent in subject.PARENTS)
    assert target["SPY"] == 0.0


def test_sample_gate_and_optimization_split_are_reproducible() -> None:
    split = rows(OUTPUT, "selection_segment_definition.csv")[0]
    assert split["total_valid_monthly_formations"] == "227"
    assert split["selection_formation_count"] == "136"
    assert split["evaluation_formation_count"] == "91"
    assert split["sample_gate_total_120"] == "true"
    assert split["sample_gate_selection_72"] == "true"
    assert split["sample_gate_evaluation_48"] == "true"
    assert split["performance_used_to_select_boundary"] == "false"


def test_exact_four_trials_controls_and_complete_panel() -> None:
    cards = rows(OUTPUT, "strategy_cards.csv")
    ledger = rows(OUTPUT, "trial_ledger.csv")
    assert len(cards) == len(ledger) == 4
    assert {row["strategy_id"] for row in cards} == {config.strategy_id for config in subject.CONFIGS}
    assert {row["trial_id"] for row in ledger} == {config.trial_id for config in subject.CONFIGS}
    benchmarks = rows(OUTPUT, "benchmark_reference_log.csv")
    assert len(benchmarks) == 4 * len(subject.ALL_CONTROLS)
    assert all(row["entity_type"] == "benchmark_reference" for row in benchmarks)
    signals = rows(OUTPUT, "monthly_pair_signal_ledger.csv")
    assert len(signals) == 4 * 227 * 7
    assert all(row["complete_panel"] == "true" for row in signals)
    assert all(row["formation_date"] < row["execution_date"] for row in signals)


def test_control_first_selection_closes_without_evaluation_access() -> None:
    selection = [row for row in rows(OUTPUT, "selection_segment_results.csv") if float(row["cost_bps_one_way"]) == 5.0]
    assert len(selection) == 4
    assert all(float(row["candidate_cagr"]) > 0.0 for row in selection)
    assert all(row["selection_eligible"] == "false" for row in selection)
    assert all(row["static_equal_control_not_dominating_5bps"] == "false" for row in selection)
    winners = rows(OUTPUT, "architecture_winner_selection.csv")
    assert all(row["selected_winner"] == "false" and row["evaluation_accessed"] == "false" for row in winners)
    assert rows(OUTPUT, "evaluation_segment_results.csv") == []
    assert rows(OUTPUT, "evaluation_subhalf_results.csv") == []
    assert rows(OUTPUT, "post_selection_full_period_diagnostics.csv") == []


def test_failure_precedence_outcome_and_entity_counts() -> None:
    failures = rows(OUTPUT, "failure_vectors.csv")
    assert len(failures) == 4
    assert all(row["primary_failure_reason"] == "no_selection_eligible_configuration" for row in failures)
    assert all("static_equal_control_not_dominating_5bps" in row["failed_selection_criteria"] for row in failures)
    consistency = json.loads((OUTPUT / "consistency_check.json").read_text(encoding="utf-8"))
    assert consistency["task_outcome"] == "phase2_new_group_no_followup"
    assert consistency["winner_trial_id"] == ""
    assert consistency["followup_count"] == 0
    assert consistency["exact_next_action"] == subject.NO_FOLLOWUP_ACTION
    counts = consistency["entity_counts"]
    assert counts["internal_architectures"] == 1
    assert counts["strategy_configurations"] == counts["canonical_optimization_trials"] == 4
    assert counts["external_source_strategies"] == 0
    assert counts["evaluation_access_count"] == 0


def test_turnover_costs_invariants_and_nonwinner_boundary() -> None:
    turnover = rows(OUTPUT, "turnover_cost_reconciliation.csv")
    assert max(float(row["absolute_reconciliation_difference"]) for row in turnover) <= 1e-12
    invariants = rows(OUTPUT, "invariant_results.csv")
    assert len(invariants) == 4
    assert all(row["overall_invariant_pass"] == "true" for row in invariants)
    assert all(row["nonwinner_simulation_stops_at_selection_boundary"] == "true" for row in invariants)
    assert all(row["simulation_last_date"] == row["selection_segment_end"] for row in invariants)


def test_required_outputs_and_deterministic_rerun(completed_run: dict[str, object]) -> None:
    assert {path.name for path in OUTPUT.iterdir() if path.is_file()} == subject.REQUIRED_OUTPUTS
    first_hash = completed_run["deterministic_core_hash"]
    second = subject.run()
    assert second["overall_pass"] is True
    assert second["deterministic_core_hash"] == first_hash
    assert second["checks"]["protected_state_and_caches_unchanged"] is True
    assert all(value is False for value in second["forbidden_actions"].values())
