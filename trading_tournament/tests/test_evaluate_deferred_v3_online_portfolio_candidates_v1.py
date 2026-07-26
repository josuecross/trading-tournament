from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from strategy_lab.research_os.research import (
    evaluate_deferred_v3_online_portfolio_candidates_v1 as batch,
)


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = (
    ROOT
    / "evidence"
    / "research_recovery"
    / batch.TASK_ID
    / "latest"
)

REQUIRED_ARTIFACTS = {
    "batch_manifest.yaml",
    "source_library_records.csv",
    "strategy_cards.csv",
    "trial_ledger.csv",
    "benchmark_reference_log.csv",
    "process_task_log.csv",
    "data_preflight_reconciliation.csv",
    "all_trial_results.csv",
    "control_results.csv",
    "chronological_half_results.csv",
    "portfolio_contribution_results.csv",
    "turnover_cost_reconciliation.csv",
    "pamr_weight_diagnostics.csv",
    "anticor_expert_diagnostics.csv",
    "anticor_claim_transfer_diagnostics.csv",
    "invariant_results.csv",
    "exploratory_followup_candidates.csv",
    "failure_reasons.csv",
    "next_actions.csv",
    "outcome_summary.csv",
    "cohort_funnel_counts.json",
    "consistency_check.json",
    "batch_report.md",
}


@pytest.fixture(scope="module", autouse=True)
def evidence_ready() -> None:
    assert (EVIDENCE / "consistency_check.json").exists(), (
        "Run the dedicated deferred V3 serial runner before focused tests."
    )


def rows(name: str) -> list[dict[str, str]]:
    with (EVIDENCE / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def json_payload(name: str) -> dict:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def yaml_payload(name: str) -> dict:
    return yaml.safe_load((EVIDENCE / name).read_text(encoding="utf-8"))


def test_exact_scope_artifacts_and_preregistration() -> None:
    assert REQUIRED_ARTIFACTS.issubset({path.name for path in EVIDENCE.iterdir()})
    manifest = yaml_payload("batch_manifest.yaml")
    assert manifest["batch_id"] == batch.TASK_ID
    assert manifest["mode"] == "fast-progress"
    assert manifest["stage"] == "exploration"
    assert tuple(manifest["strategy_ids"]) == batch.EXPECTED_STRATEGY_IDS
    assert manifest["strategy_configuration_count"] == 2
    assert manifest["canonical_experiment_trial_count"] == 2
    assert manifest["executed_trial_count"] == 2
    assert manifest["preregistration_written_before_performance_calculation"] is True
    assert manifest["preregistration_checkpoint_hash"].startswith("sha256:")
    assert manifest["validation_claimed"] is False
    assert manifest["lifecycle_state_changed"] is False


def test_strategy_trial_benchmark_and_process_entities_are_separate() -> None:
    strategies = rows("strategy_cards.csv")
    trials = rows("trial_ledger.csv")
    benchmarks = rows("benchmark_reference_log.csv")
    process = rows("process_task_log.csv")
    assert len(strategies) == len(trials) == 2
    assert len(benchmarks) == 6
    assert len(process) == 1
    assert {row["entity_type"] for row in strategies} == {"strategy_configuration"}
    assert {row["entity_type"] for row in trials} == {"experiment_trial"}
    assert {row["stage"] for row in strategies + trials} == {"exploration"}
    assert {row["parent_trial_id"] for row in trials} == {""}
    assert {row["adaptation_label"] for row in trials} == {""}
    assert {row["entity_type"] for row in benchmarks} == {"benchmark_reference"}
    assert {row["stage"] for row in benchmarks} == {"benchmark_reference_only"}
    assert {row["counted_as_strategy"] for row in benchmarks} == {"false"}
    assert {row["counted_as_trial"] for row in benchmarks} == {"false"}
    assert process[0]["entity_type"] == "process_task"
    assert process[0]["stage"] == "exploration"

    trial_ids = {row["strategy_id"] for row in trials}
    assert trial_ids == set(batch.EXPECTED_STRATEGY_IDS)
    assert "li_hoi_olmar5_sector_etf_v1" not in trial_ids
    assert "anticor_single_window_30_sector_v1" not in trial_ids


def test_frozen_parameters_and_universe() -> None:
    pamr, anticor = batch.CARDS
    assert pamr.parameters == {"variant": "PAMR-0", "epsilon": 0.5}
    assert anticor.parameters["expert_windows"] == list(range(2, 31))
    assert anticor.parameters["expert_count"] == 29
    assert pamr.universe == anticor.universe == batch.SECTOR_UNIVERSE
    strategy_rows = rows("strategy_cards.csv")
    assert all(
        json.loads(row["instrument_universe"]) == list(batch.SECTOR_UNIVERSE)
        for row in strategy_rows
    )


def test_pamr_formula_projection_and_next_session_timing() -> None:
    index = pd.date_range("2024-01-02", periods=4, freq="B")
    base = np.array([100.0, 101.0, 99.0, 102.0])
    prices = pd.DataFrame(
        {
            symbol: base * (1.0 + position * 0.001 * np.arange(len(base)))
            for position, symbol in enumerate(batch.SECTOR_UNIVERSE)
        },
        index=index,
    )
    candidate, controls, diagnostics = batch.pamr_event_sets(prices)
    assert tuple(controls) == batch.CARDS[0].controls
    first = diagnostics[0]
    x_t = prices.iloc[1].to_numpy() / prices.iloc[0].to_numpy()
    equal = batch.equal_target()
    loss = max(0.0, float(np.dot(equal, x_t)) - 0.5)
    centered = x_t - x_t.mean()
    denominator = float(np.dot(centered, centered))
    preliminary = equal - (loss / denominator) * centered
    expected = batch.v6.project_simplex(preliminary)
    target = np.array(
        [json.loads(json.dumps(first["target_weights"]))[symbol] for symbol in batch.SECTOR_UNIVERSE]
    )
    assert np.allclose(target, expected)
    assert first["signal_date"] == index[1].date().isoformat()
    assert first["execution_date"] == index[2].date().isoformat()
    assert np.allclose(candidate.loc[index[2]].to_numpy(), expected)
    assert np.isclose(target.sum(), 1.0)
    assert (target >= 0.0).all()


def test_anticor_update_is_deterministic_nonnegative_and_fully_invested() -> None:
    current = np.full(3, 1.0 / 3.0)
    x_t = np.array([1.01, 0.99, 1.00])
    first = np.array(
        [
            [0.02, -0.01, 0.00],
            [0.01, -0.02, 0.01],
            [0.03, -0.01, -0.01],
        ]
    )
    second = np.array(
        [
            [-0.01, 0.02, 0.00],
            [-0.02, 0.01, 0.01],
            [-0.01, 0.03, -0.01],
        ]
    )
    first_result, first_detail = batch.anticor_update(
        current, x_t, first, second
    )
    second_result, second_detail = batch.anticor_update(
        current, x_t, first, second
    )
    assert np.allclose(first_result, second_result)
    assert first_detail["valid_claim_count"] == second_detail["valid_claim_count"]
    assert np.isclose(first_result.sum(), 1.0)
    assert first_result.min() >= 0.0
    assert first_detail["total_transfer_amount"] >= 0.0


def test_data_preflight_uses_all_nine_cached_sectors_without_provider() -> None:
    preflight = rows("data_preflight_reconciliation.csv")
    assert len(preflight) == 18
    assert {row["symbol"] for row in preflight} == set(batch.SECTOR_UNIVERSE)
    assert {row["preflight_status"] for row in preflight} == {"pass"}
    assert {row["provider_accessed"] for row in preflight} == {"false"}
    assert all(row["canonical_hash"].startswith("sha256:") for row in preflight)
    assert len({row["common_evaluation_start"] for row in preflight}) == 1
    assert len({row["common_evaluation_end"] for row in preflight}) == 1


def test_exact_trial_costs_halves_controls_and_invariants() -> None:
    trials = rows("all_trial_results.csv")
    controls = rows("control_results.csv")
    halves = rows("chronological_half_results.csv")
    invariants = rows("invariant_results.csv")
    assert len(trials) == 6
    assert len(controls) == 18
    assert {row["cost_assumption_bps"] for row in trials + controls} == {
        "0",
        "5",
        "10",
    }
    assert {
        row["period_label"] for row in halves
    } == {"first_chronological_half", "second_chronological_half"}
    assert all("not_validation_or_sealed_holdout" in row["period_role"] for row in halves)
    assert {row["invariant_pass"] for row in invariants} == {"true"}
    assert {row["explicit_zero_weights"] for row in invariants} == {"true"}
    assert {row["stale_weight_forward_fill_used"] for row in invariants} == {
        "false"
    }
    assert {row["negative_weights_present"] for row in invariants} == {"false"}
    assert {row["leverage_present"] for row in invariants} == {"false"}
    assert {row["same_period_price_signal_return_used"] for row in invariants} == {
        "false"
    }


def test_pamr_diagnostics_include_weights_thresholds_and_yearly_turnover() -> None:
    diagnostics = rows("pamr_weight_diagnostics.csv")
    daily = [row for row in diagnostics if row["record_type"] == "daily_target"]
    annual = [row for row in diagnostics if row["record_type"] == "year_summary"]
    assert daily and annual
    assert all(row["loss"] and row["tau"] for row in daily)
    assert all(row["projection_distance"] for row in daily)
    assert all(row["target_weights"] for row in daily)
    assert all(row["annual_turnover"] for row in annual)
    assert any(row["any_weight_exceeds_50pct"] == "true" for row in daily)
    assert all(int(row["year"]) >= 2000 for row in annual)


def test_anticor_has_exactly_29_experts_and_wealth_shares_reconcile() -> None:
    path = EVIDENCE / "anticor_expert_diagnostics.csv"
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        first_execution = None
        sample: list[dict[str, str]] = []
        all_windows: set[int] = set()
        for row in reader:
            all_windows.add(int(row["expert_window"]))
            if first_execution is None:
                first_execution = row["execution_date"]
            if row["execution_date"] == first_execution:
                sample.append(row)
    assert all_windows == set(range(2, 31))
    assert len(sample) == 29
    assert np.isclose(
        sum(float(row["aggregate_wealth_share"]) for row in sample), 1.0
    )
    assert all(row["target_weights"] for row in sample)
    assert all(float(row["expert_nav"]) > 0.0 for row in sample)


def test_anticor_aggregate_costs_are_not_double_charged() -> None:
    claims = rows("anticor_claim_transfer_diagnostics.csv")
    assert claims
    assert {row["expert_costs_used_only_for_wealth_shares"] for row in claims} == {
        "true"
    }
    assert {row["aggregate_cost_charged_once"] for row in claims} == {"true"}
    assert {row["expert_and_aggregate_costs_double_charged"] for row in claims} == {
        "false"
    }
    assert all(
        np.isclose(sum(json.loads(row["aggregate_target"]).values()), 1.0)
        for row in claims
    )
    turnover = rows("turnover_cost_reconciliation.csv")
    anticor_candidate = [
        row
        for row in turnover
        if row["strategy_id"] == batch.ANTICOR_ID
        and row["record_scope"] == "candidate"
    ]
    assert len(anticor_candidate) == 3
    assert all(row["double_charged"] == "false" for row in anticor_candidate)


def test_portfolio_contribution_is_tradable_monthly_80_20() -> None:
    portfolios = rows("portfolio_contribution_results.csv")
    assert portfolios
    assert {
        row["portfolio_construction"] for row in portfolios
    } == {
        "100pct_frozen_reference",
        "monthly_rebalanced_80pct_reference_plus_20pct_candidate_or_control_with_natural_drift",
    }
    assert {
        row["period_label"] for row in portfolios
    } == {
        "full_period",
        "first_chronological_half",
        "second_chronological_half",
    }
    assert {row["invariant_pass"] for row in portfolios} == {"true"}


def test_outcomes_close_honestly_and_funnel_reconciles() -> None:
    outcomes = {row["strategy_id"]: row for row in rows("outcome_summary.csv")}
    assert outcomes[batch.PAMR_ID]["outcome"] == "closed_exploration"
    assert outcomes[batch.PAMR_ID]["failure_reason"] == "weak_return"
    assert outcomes[batch.ANTICOR_ID]["outcome"] == "closed_exploration"
    assert outcomes[batch.ANTICOR_ID]["failure_reason"] == (
        "weak_vs_primary_control"
    )
    funnel = json_payload("cohort_funnel_counts.json")
    assert funnel["strategy_configurations"] == 2
    assert funnel["canonical_experiment_trials"] == 2
    assert funnel["executed_experiment_trials"] == 2
    assert funnel["followup_candidates"] == 0
    assert funnel["closed_exploration"] == 2
    assert funnel["outcome_count_reconciles"] is True
    assert funnel["exact_next_action"] == "refresh_strategy_source_library_v4"


def test_protected_state_prior_evidence_cache_and_guardrails_reconcile() -> None:
    check = json_payload("consistency_check.json")
    assert check["consistency_passed"] is True
    assert check["protected_state_unchanged"] is True
    assert check["cache_unchanged"] is True
    assert check["prior_evidence_unchanged"] is True
    assert check["original_v6_evidence_unchanged"] is True
    assert check["high52_correction_evidence_unchanged"] is True
    assert check["source_packet_unchanged"] is True
    assert check["frozen_pamr_variant_and_epsilon"] is True
    assert check["frozen_anticor_windows_2_through_30"] is True
    assert check["olmar_and_anticor30_counted_only_as_benchmark_references"] is True
    assert check["aggregate_implementable_target_cost_charged_once"] is True
    assert check["expert_and_aggregate_costs_double_charged"] is False
    assert check["all_numeric_timing_exposure_weight_invariants_passed"] is True
    assert not any(check["forbidden_actions"].values())
    assert check["exact_next_action"] == "refresh_strategy_source_library_v4"
    assert check["next_action_executed"] is False
