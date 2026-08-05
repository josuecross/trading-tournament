from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from strategy_lab.research_os.research import (
    multi_family_fast_exploration_batch_v1 as batch,
)


OUTPUT = batch.OUTPUT_DIR


def csv_rows(name: str) -> list[dict[str, str]]:
    with (OUTPUT / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def json_payload(name: str) -> dict:
    return json.loads((OUTPUT / name).read_text(encoding="utf-8"))


def test_required_artifacts_and_exact_scope() -> None:
    required = {
        "batch_manifest.yaml",
        "source_library_records.csv",
        "strategy_cards.csv",
        "trial_ledger.csv",
        "benchmark_reference_log.csv",
        "data_capability_task_log.csv",
        "process_task_log.csv",
        "data_preflight_reconciliation.csv",
        "all_trial_results.csv",
        "control_results.csv",
        "chronological_half_results.csv",
        "portfolio_contribution_results.csv",
        "beta_rotation_diagnostics.csv",
        "adaptive_top4_diagnostics.csv",
        "rati_rank_and_allocation_diagnostics.csv",
        "es_implied_beta_diagnostics.csv",
        "halloween_state_diagnostics.csv",
        "turnover_cost_reconciliation.csv",
        "invariant_results.csv",
        "exploratory_followup_candidates.csv",
        "outcome_summary.csv",
        "failure_reasons.csv",
        "next_actions.csv",
        "cohort_funnel_counts.json",
        "consistency_check.json",
        "batch_report.md",
    }
    assert required == {path.name for path in OUTPUT.iterdir() if path.is_file()}
    manifest = yaml.safe_load((OUTPUT / "batch_manifest.yaml").read_text(encoding="utf-8"))
    assert tuple(manifest["strategy_ids"]) == batch.EXPECTED_STRATEGY_IDS
    assert manifest["strategy_configuration_count"] == 5
    assert manifest["canonical_experiment_trial_count"] == 5


def test_entity_separation_and_complete_canonical_lineage() -> None:
    sources = csv_rows("source_library_records.csv")
    strategies = csv_rows("strategy_cards.csv")
    trials = csv_rows("trial_ledger.csv")
    process = csv_rows("process_task_log.csv")
    assert len(sources) == len(strategies) == len(trials) == 5
    assert len(process) == 1
    assert {row["entity_type"] for row in sources} == {"source_library_record"}
    assert {row["entity_type"] for row in strategies} == {"strategy_configuration"}
    assert {row["entity_type"] for row in trials} == {"experiment_trial"}
    assert len({row["trial_id"] for row in trials}) == 5
    assert all(row["parent_trial_id"] == "" for row in trials)
    assert all(row["adaptation_label"] == "" for row in trials)
    assert all(row["optimization_performed"].lower() == "false" for row in trials)
    required = {
        "strategy_id",
        "family_id",
        "display_name",
        "strategy_architecture",
        "source_or_research_lineage",
        "instrument_universe",
        "parameters",
        "benchmark_or_control",
        "stage",
        "trial_id",
        "outcome",
        "next_action",
    }
    assert all(all(row[field] for field in required) for row in strategies + trials)


def test_bounded_provider_tasks_are_exact_and_read_only() -> None:
    tasks = csv_rows("data_capability_task_log.csv")
    assert {row["symbol"] for row in tasks} == set(batch.FROZEN_INITIAL_MISSING_SYMBOLS)
    assert all(row["entity_type"] == "data_capability_task" for row in tasks)
    assert all(int(row["attempt_count"]) <= 1 for row in tasks)
    assert all(row["api_secrets_persisted"].lower() == "false" for row in tasks)
    assert all(
        row["broker_or_order_endpoint_called"].lower() == "false" for row in tasks
    )
    assert all(
        row["preferred_provider_reason_not_admitted"]
        for row in tasks
        if row["preferred_provider_status"] == "returned_bars"
    )
    allowed = set(batch.EXPECTED_STRATEGY_IDS[1:3])
    for row in tasks:
        assert set(row["authorized_candidate_ids"].split("|")) <= allowed


def test_beta_rotation_formula_timing_and_controls() -> None:
    rows = [
        row
        for row in csv_rows("beta_rotation_diagnostics.csv")
        if row["signal_valid"].lower() == "true"
    ]
    assert rows
    first = rows[0]
    prices = batch.market.load_price_frame(("SPY", "XLU"))
    signal = pd.Timestamp(first["formation_date"])
    prior = pd.Timestamp(first["lookback_week_end"])
    expected = (
        (prices.loc[signal, "XLU"] / prices.loc[prior, "XLU"])
        / (prices.loc[signal, "SPY"] / prices.loc[prior, "SPY"])
        - 1.0
    )
    assert np.isclose(float(first["relative_strength_value"]), expected, atol=1e-12)
    assert pd.Timestamp(first["authorized_execution_date"]) > signal
    benchmarks = csv_rows("benchmark_reference_log.csv")
    ids = {
        row["benchmark_or_control_id"]
        for row in benchmarks
        if row["strategy_id"] == batch.EXPECTED_STRATEGY_IDS[0]
    }
    assert ids == set(batch.CARDS[0].controls)


def test_adaptive_top4_uses_full_universe_and_exactly_four() -> None:
    outcomes = {row["strategy_id"]: row for row in csv_rows("outcome_summary.csv")}
    if outcomes[batch.EXPECTED_STRATEGY_IDS[1]]["executed"] != "True":
        return
    rows = [
        row
        for row in csv_rows("adaptive_top4_diagnostics.csv")
        if row["record_type"] == "formation_asset"
        and row["valid_full_universe_formation"] == "True"
    ]
    assert rows
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        grouped.setdefault(row["formation_date"], []).append(row)
    for formation in grouped.values():
        assert len(formation) == 14
        assert sum(row["selected_top4"] == "True" for row in formation) == 4
        assert len({int(row["rank_3m"]) for row in formation}) == 14


def test_rati_tuesday_execution_risky_cap_and_weight_floor_contract() -> None:
    outcomes = {row["strategy_id"]: row for row in csv_rows("outcome_summary.csv")}
    if outcomes[batch.EXPECTED_STRATEGY_IDS[2]]["executed"] != "True":
        return
    rows = [
        row
        for row in csv_rows("rati_rank_and_allocation_diagnostics.csv")
        if row["signal_complete"] == "True" and row["execution_date"]
    ]
    assert rows
    assert all(pd.Timestamp(row["execution_date"]).weekday() == 1 for row in rows)
    assert max(float(row["aggregate_risky_weight"]) for row in rows) <= 0.5 + 1e-12
    for row in rows:
        weight = float(row["final_weight"])
        floor = float(row["weight_floor"])
        if row["symbol"] != "BIL" and weight > 0.0:
            selected = row["final_non_cash_selection"].split("|")
            if len(selected) < len(batch.RATI_UNIVERSE) - 1:
                assert weight > floor - 1e-12


def test_empirical_es_formula_and_top2_selection() -> None:
    values = np.array([-4.0, -2.0, 1.0, 5.0])
    assert batch.empirical_es(values, 0.5) == -3.0
    outcomes = {row["strategy_id"]: row for row in csv_rows("outcome_summary.csv")}
    if outcomes[batch.EXPECTED_STRATEGY_IDS[3]]["executed"] != "True":
        return
    rows = [
        row
        for row in csv_rows("es_implied_beta_diagnostics.csv")
        if row["complete_formation_valid"] == "True"
    ]
    assert rows
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        grouped.setdefault(row["formation_date"], []).append(row)
    for formation in grouped.values():
        assert len(formation) == 9
        assert sum(row["candidate_selected"] == "True" for row in formation) == 2
        scores = [float(row["relative_ES_score"]) for row in formation]
        assert np.isfinite(scores).all()


def test_halloween_transitions_are_following_session_and_complete_cycles() -> None:
    rows = [
        row
        for row in csv_rows("halloween_state_diagnostics.csv")
        if row["execution_status"] == "executed"
    ]
    assert rows
    for row in rows:
        signal = pd.Timestamp(row["signal_date"])
        execution = pd.Timestamp(row["authorized_execution_date"])
        assert execution > signal
        if signal.month == 4:
            assert row["season_transition"] == "to_BIL"
        elif signal.month == 10:
            assert row["season_transition"] == "to_SPY"
        else:
            raise AssertionError("unexpected Halloween signal month")


def test_costs_halves_turnover_and_invariants_reconcile() -> None:
    trial_rows = csv_rows("all_trial_results.csv")
    by_strategy: dict[str, set[float]] = {}
    for row in trial_rows:
        by_strategy.setdefault(row["strategy_id"], set()).add(
            float(row["cost_assumption_bps"])
        )
    assert all(costs == {0.0, 5.0, 10.0} for costs in by_strategy.values())
    halves = csv_rows("chronological_half_results.csv")
    assert all(float(row["cost_assumption_bps"]) == 5.0 for row in halves)
    assert {
        row["period_label"] for row in halves
    } <= {"first_chronological_half", "second_chronological_half"}
    invariants = csv_rows("invariant_results.csv")
    assert invariants
    assert all(row["invariant_pass"].lower() == "true" for row in invariants)
    assert all(
        row["negative_weights_present"].lower() == "false" for row in invariants
    )
    assert all(row["leverage_used"].lower() == "false" for row in invariants)
    assert all(
        row["same_period_price_signal_return_used"].lower() == "false"
        for row in invariants
    )


def test_portfolio_contribution_uses_only_declared_routes_and_explicit_80_20() -> None:
    rows = csv_rows("portfolio_contribution_results.csv")
    routed = set(batch.EXPECTED_STRATEGY_IDS[1:4])
    assert {row["strategy_id"] for row in rows} <= routed
    assert all(
        row["portfolio_id"] == "100pct_frozen_reference"
        or "80pct_reference_20pct" in row["portfolio_id"]
        for row in rows
    )
    assert all(
        float(row["maximum_gross_exposure"]) <= 1.0 + 1e-9 for row in rows
    )


def test_outcomes_funnel_and_next_action_are_arithmetically_consistent() -> None:
    outcomes = csv_rows("outcome_summary.csv")
    funnel = json_payload("cohort_funnel_counts.json")
    assert len(outcomes) == 5
    assert funnel["outcome_count_reconciles"] is True
    assert sum(funnel["outcomes"].values()) == 5
    followups = sum(
        row["outcome"].startswith("exploratory_followup_candidate_")
        for row in outcomes
    )
    assert funnel["followup_candidate_count"] == followups
    batch_next = [
        row for row in csv_rows("next_actions.csv") if row["scope"] == "batch"
    ][0]
    assert batch_next["exact_next_action"] in {
        batch.NEXT_REVIEW,
        batch.NEXT_ALL_CLOSED,
        batch.NEXT_BLOCKED,
    }


def test_protected_state_source_prior_evidence_and_cache_scope_reconcile() -> None:
    check = json_payload("consistency_check.json")
    assert check["overall_pass"] is True
    assert check["protected_state_unchanged"] is True
    assert check["prior_evidence_unchanged"] is True
    assert check["source_packet_unchanged"] is True
    assert check["cache_changes_authorized_and_logged"] is True
    assert check["unrelated_cache_files_unchanged"] is True
    assert check["preregistration_written_before_performance_calculation"] is True
    assert check["forbidden_actions"] == batch.FORBIDDEN_FLAGS


def test_frozen_core_hash_is_deterministic() -> None:
    assert batch.deterministic_core_hash() == batch.deterministic_core_hash()
