from __future__ import annotations

import csv
import json

import pytest

from strategy_lab.research_os.research import run_spdj_dynamic_inflation_robustness_v1 as subject


def rows(name: str) -> list[dict[str, str]]:
    with (subject.OUTPUT_DIR / name).open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


@pytest.fixture(scope="module", autouse=True)
def completed_run():
    result = subject.run()
    assert result["overall_pass"] is True
    return result


def test_parent_hashes_and_correction_lineage_reconcile() -> None:
    result = json.loads((subject.OUTPUT_DIR / "consistency_check.json").read_text(encoding="utf-8"))
    assert result["parent_evidence_hash"] == subject.PARENT_EVIDENCE_HASH
    assert result["parent_code_hash"] == subject.PARENT_CODE_HASH
    assert result["checks"]["parent_evidence_unchanged"] is True
    assert result["checks"]["corrected_parent_code_hash_matches"] is True


def test_parent_selection_and_evaluation_reproduce_exactly() -> None:
    reproduction = rows("parent_reproduction.csv")
    assert reproduction
    assert all(row["reproduction_pass"] == "true" for row in reproduction)
    counts = next(row for row in reproduction if row["period_id"] == "required_parent_counts")
    assert counts["selection_events"] == "true"
    assert counts["evaluation_events"] == "true"
    assert counts["total_events"] == "true"
    assert counts["first_valid_formation"] == "true"


def test_robustness_preregistration_freezes_axes_before_results() -> None:
    prereg = json.loads((subject.OUTPUT_DIR / "robustness_preregistration.json").read_text(encoding="utf-8"))
    assert prereg["written_before_robustness_results"] is True
    assert prereg["robustness_axes"]["bootstrap"]["replications"] == 10_000
    assert prereg["robustness_axes"]["bootstrap"]["block_length_months"] == 12
    assert prereg["robustness_axes"]["chronological_partition_algorithm"].startswith("ordered_numpy_array_split")
    assert prereg["strategy_variant_count"] == 0


def test_pareto_dominance_uses_only_sharpe_and_drawdown() -> None:
    candidate = {"sharpe_ratio": 1.0, "maximum_drawdown": -0.20}
    assert subject.pareto_dominates({"sharpe_ratio": 1.1, "maximum_drawdown": -0.19}, candidate)
    assert not subject.pareto_dominates({"sharpe_ratio": 1.1, "maximum_drawdown": -0.21}, candidate)
    assert not subject.pareto_dominates({"sharpe_ratio": 0.9, "maximum_drawdown": -0.19}, candidate)


def test_cost_gate_uses_only_frozen_cost_schedule() -> None:
    cost_rows = rows("cost_robustness.csv")
    assert {float(row["cost_bps_one_way"]) for row in cost_rows} == {0.0, 5.0, 10.0}
    gates = json.loads((subject.OUTPUT_DIR / "robustness_gate_results.json").read_text(encoding="utf-8"))
    assert set(gates["cost_gate_components"]) == {
        "candidate_CAGR_positive_5bps",
        "candidate_Sharpe_positive_5bps",
        f"{subject.NAMED_CONTROL}_does_not_dominate_5bps",
        f"{subject.EQUAL_CONTROL}_does_not_dominate_5bps",
        "candidate_CAGR_positive_10bps",
        "candidate_Sharpe_positive_10bps",
        f"{subject.NAMED_CONTROL}_does_not_dominate_10bps",
        f"{subject.EQUAL_CONTROL}_does_not_dominate_10bps",
    }


def test_four_blocks_are_mechanical_and_cover_203_events() -> None:
    result = json.loads((subject.OUTPUT_DIR / "robustness_gate_results.json").read_text(encoding="utf-8"))
    counts = result["four_block_summary"]["block_event_counts"]
    assert counts == [51, 51, 51, 50]
    assert sum(counts) == 203
    assert max(counts) - min(counts) <= 1
    assert len(rows("chronological_block_results.csv")) == 12


def test_bootstrap_is_paired_deterministic_and_absolute_gate_is_explicit() -> None:
    summary = json.loads((subject.OUTPUT_DIR / "bootstrap_summary.json").read_text(encoding="utf-8"))
    comparisons = rows("bootstrap_control_comparison.csv")
    assert summary["replications"] == 10_000
    assert summary["block_length_months"] == 12
    assert summary["seed"] == subject.BOOTSTRAP_SEED
    assert summary["cross_series_dependence_preserved"] is True
    assert len(comparisons) == 2
    assert all(row["paired_sample_indices"] == "true" for row in comparisons)
    assert summary["bootstrap_absolute_viability_pass"] == (summary["candidate_CAGR_percentiles"]["p05"] > 0.0)


def test_rolling_windows_are_diagnostic_only_and_stepped_annually() -> None:
    rolling = rows("rolling_window_results.csv")
    assert rolling
    assert {int(row["window_months"]) for row in rolling} == {36}
    assert {int(row["step_months"]) for row in rolling} == {12}
    assert {row["gate_role"] for row in rolling} == {"diagnostic_only"}


def test_regime_and_transition_attribution_cover_frozen_states() -> None:
    regime = rows("regime_attribution.csv")
    transition = rows("transition_attribution.csv")
    assert {row["regime"] for row in regime} == {"low", "medium", "high"}
    assert all(row["gate_role"] == "diagnostic_only" for row in regime)
    assert "unchanged" in {row["transition"] for row in transition}
    assert sum(int(row["event_count"]) for row in transition) == 203


def test_timing_stresses_are_diagnostics_not_variants() -> None:
    timing = rows("timing_sensitivity.csv")
    assert {int(row["delay_business_days"]) for row in timing} == {0, 1, 2}
    assert all(row["signals_recomputed"] == "false" for row in timing if row["delay_business_days"] != "0")
    accounting = json.loads((subject.OUTPUT_DIR / "trial_accounting.json").read_text(encoding="utf-8"))
    assert accounting["strategy_variant_count"] == 0
    assert accounting["timing_diagnostics_counted_as_trials"] == 0


def test_control_roles_remain_frozen() -> None:
    audit = {row["control_id"]: row for row in rows("control_information_set_audit.csv")}
    assert audit[subject.NAMED_CONTROL]["control_role"] == "blocking_control"
    assert audit[subject.EQUAL_CONTROL]["control_role"] == "blocking_control"
    assert audit[subject.DIAGNOSTIC_CONTROL]["control_role"] == "diagnostic_only"
    assert audit[subject.DIAGNOSTIC_CONTROL]["can_determine_robustness"] == "false"


def test_trial_accounting_has_one_robustness_trial_and_no_variant() -> None:
    accounting = json.loads((subject.OUTPUT_DIR / "trial_accounting.json").read_text(encoding="utf-8"))
    assert accounting["parent_architecture_count"] == 1
    assert accounting["parent_canonical_configuration_count"] == 1
    assert accounting["parent_canonical_trial_count"] == 1
    assert accounting["robustness_trial_count"] == 1
    assert accounting["strategy_variant_count"] == 0


def test_no_provider_broker_forward_or_eligibility_action() -> None:
    accounting = json.loads((subject.OUTPUT_DIR / "trial_accounting.json").read_text(encoding="utf-8"))
    assert accounting["provider_calls"] == 0
    assert accounting["broker_calls"] == 0
    assert accounting["forward_observation_accesses"] == 0
    assert accounting["eligibility_decisions"] == 0
    assert accounting["handoffs"] == 0
    assert accounting["trade_management_overlays"] == 0


def test_protected_state_and_required_outputs_reconcile() -> None:
    consistency = json.loads((subject.OUTPUT_DIR / "consistency_check.json").read_text(encoding="utf-8"))
    assert consistency["checks"]["all_protected_state_unchanged"] is True
    assert consistency["checks"]["all_required_outputs_present"] is True
    assert set(subject.REQUIRED_OUTPUTS).issubset({path.name for path in subject.OUTPUT_DIR.iterdir()})


def test_deterministic_rerun_preserves_evidence_hash(completed_run) -> None:
    second = subject.run()
    assert second["deterministic_evidence_hash"] == completed_run["deterministic_evidence_hash"]
    assert second["overall_pass"] is True
