from __future__ import annotations

import csv
import inspect
import json
import math
from pathlib import Path

import pandas as pd
import yaml

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.research import run_deferred_structural_source_batch_v2 as batch


OUTPUT_DIR = ROOT / "evidence" / "research_recovery" / batch.BATCH_ID / "latest"
EXPECTED_FILES = {
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
    "calendar_year_results.csv",
    "portfolio_contribution_results.csv",
    "portfolio_rebalance_events.csv",
    "turnover_cost_reconciliation.csv",
    "invariant_results.csv",
    "exploratory_followup_candidates.csv",
    "failure_reasons.csv",
    "next_actions.csv",
    "outcome_summary.csv",
    "cohort_funnel_counts.json",
    "consistency_check.json",
    "batch_report.md",
}
STRATEGY_IDS = {
    "invesco_sp_us_spinoff_csd_v1",
    "nasdaq_buyback_achievers_pkw_v1",
}


def rows(name: str) -> list[dict[str, str]]:
    with (OUTPUT_DIR / name).open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def payload(name: str) -> dict:
    return json.loads((OUTPUT_DIR / name).read_text(encoding="utf-8"))


def test_required_packet_and_exact_entity_counts() -> None:
    assert {path.name for path in OUTPUT_DIR.iterdir() if path.is_file()} == EXPECTED_FILES
    sources = rows("source_library_records.csv")
    strategies = rows("strategy_cards.csv")
    trials = rows("trial_ledger.csv")
    processes = rows("process_task_log.csv")
    benchmarks = rows("benchmark_reference_log.csv")
    assert len(sources) == 2
    assert len(strategies) == 2
    assert len(trials) == 2
    assert len(processes) == 1
    assert len(benchmarks) == 4
    assert {row["entity_type"] for row in sources} == {"source_library_record"}
    assert {row["entity_type"] for row in strategies} == {"strategy_configuration"}
    assert {row["entity_type"] for row in trials} == {"experiment_trial"}
    assert {row["entity_type"] for row in processes} == {"process_task"}
    assert {row["entity_type"] for row in benchmarks} == {"benchmark_reference"}


def test_exact_frozen_trial_lineage_and_complete_metadata() -> None:
    strategies = rows("strategy_cards.csv")
    trials = rows("trial_ledger.csv")
    assert {row["strategy_id"] for row in strategies} == STRATEGY_IDS
    assert {row["strategy_id"] for row in trials} == STRATEGY_IDS
    assert len({row["trial_id"] for row in trials}) == 2
    required = {
        "strategy_id",
        "family_id",
        "display_name",
        "entity_type",
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
    for row in (*strategies, *trials):
        assert all(row[field] for field in required)
        assert all(value.lower() not in {"unknown", "unmapped"} for value in row.values())
        assert row["stage"] == "exploration"
    assert {row["parent_trial_id"] for row in trials} == {""}
    assert {row["adaptation_label"] for row in trials} == {""}
    assert {row["changed_fields_from_parent"] for row in trials} == {"canonical_configuration_no_parent"}
    assert {row["route"] for row in trials} == {"diversifier"}


def test_cache_only_preflight_reproduces_frozen_periods_and_target_hashes() -> None:
    preflight = rows("data_preflight_reconciliation.csv")
    symbols = {row["symbol"]: row for row in preflight if row["record_type"] == "symbol_preflight"}
    assert set(symbols) == {"CSD", "IWR", "PKW", "SPY", "DGRO"}
    assert {row["load_source"] for row in symbols.values()} == {"cache"}
    assert all(row["preflight_status"] == "pass" for row in symbols.values())
    for symbol in ("CSD", "IWR", "PKW"):
        assert symbols[symbol]["expected_row_count_match"] == "true"
        assert symbols[symbol]["expected_date_range_match"] == "true"
        assert symbols[symbol]["expected_canonical_hash_match"] == "true"
    periods = {row["symbol"]: row for row in preflight if row["record_type"] == "candidate_common_period"}
    assert (periods["invesco_sp_us_spinoff_csd_v1"]["first_valid_date"], periods["invesco_sp_us_spinoff_csd_v1"]["last_valid_date"]) == (
        "2007-01-03",
        "2026-06-18",
    )
    assert (
        periods["nasdaq_buyback_achievers_pkw_v1"]["first_valid_date"],
        periods["nasdaq_buyback_achievers_pkw_v1"]["last_valid_date"],
    ) == ("2014-06-12", "2026-06-18")


def test_primary_and_fixed_cost_diagnostics_are_not_trials() -> None:
    candidate = rows("all_trial_results.csv")
    controls = rows("control_results.csv")
    assert len(candidate) == 6
    assert len(controls) == 12
    assert {float(row["cost_assumption_bps"]) for row in (*candidate, *controls)} == {0.0, 5.0, 10.0}
    assert len(rows("trial_ledger.csv")) == 2
    for strategy_id in STRATEGY_IDS:
        assert sum(row["strategy_id"] == strategy_id for row in candidate) == 3


def test_declared_control_dominance_recomputes_both_closures() -> None:
    candidates = {
        row["strategy_id"]: row
        for row in rows("all_trial_results.csv")
        if float(row["cost_assumption_bps"]) == batch.PRIMARY_COST_BPS
    }
    controls = rows("control_results.csv")
    outcomes = {row["strategy_id"]: row for row in rows("outcome_summary.csv")}
    for strategy_id, candidate in candidates.items():
        candidate_values = tuple(float(candidate[key]) for key in ("cagr", "sharpe_ratio", "maximum_drawdown"))
        relevant = [
            row
            for row in controls
            if row["strategy_id"] == strategy_id and float(row["cost_assumption_bps"]) == batch.PRIMARY_COST_BPS
        ]
        dominated = any(
            all(float(row[key]) >= value - 1e-12 for key, value in zip(("cagr", "sharpe_ratio", "maximum_drawdown"), candidate_values))
            and any(
                float(row[key]) > value + 1e-12
                for key, value in zip(("cagr", "sharpe_ratio", "maximum_drawdown"), candidate_values)
            )
            for row in relevant
        )
        assert dominated
        assert outcomes[strategy_id]["outcome"] == "closed_exploration"
        assert outcomes[strategy_id]["primary_failure_reason"] == "weak_vs_primary_control"


def test_chronological_halves_and_calendar_years_are_diagnostic_only() -> None:
    halves = rows("chronological_half_results.csv")
    assert {row["period_label"] for row in halves} == {"first_chronological_half", "second_chronological_half"}
    report = (OUTPUT_DIR / "batch_report.md").read_text(encoding="utf-8").lower()
    assert "neither half is a clean or sealed holdout" in report
    calendar = rows("calendar_year_results.csv")
    assert calendar
    assert {row["diagnostic_only"] for row in calendar} == {"true"}
    assert {row["clean_or_sealed_holdout"] for row in calendar} == {"false"}


def test_monthly_80_20_events_use_actual_pretrade_turnover_and_shifted_timing() -> None:
    events = rows("portfolio_rebalance_events.csv")
    assert events
    assert {row["portfolio_construction"] for row in events} == {"monthly_rebalanced_80_20"}
    for row in events:
        expected = 0.5 * (
            abs(float(row["post_trade_reference_weight"]) - float(row["pretrade_reference_weight"]))
            + abs(float(row["post_trade_sleeve_weight"]) - float(row["pretrade_sleeve_weight"]))
        )
        assert math.isclose(float(row["one_way_turnover"]), expected, rel_tol=0.0, abs_tol=1e-12)
        assert math.isclose(
            float(row["post_trade_reference_weight"]) + float(row["post_trade_sleeve_weight"]),
            1.0,
            rel_tol=0.0,
            abs_tol=1e-12,
        )
        if row["event_type"] != "initial_establishment":
            assert pd.Timestamp(row["signal_date"]) < pd.Timestamp(row["event_date"])
            assert pd.Timestamp(row["signal_date"]).to_period("M") != pd.Timestamp(row["event_date"]).to_period("M")


def test_cost_and_invariant_reconciliation_passes_without_double_counting() -> None:
    turnover = rows("turnover_cost_reconciliation.csv")
    assert turnover
    assert {row["component_cost_double_counted"] for row in turnover} == {"false"}
    assert {row["internal_etf_turnover_charged"] for row in turnover} == {"false"}
    invariants = rows("invariant_results.csv")
    evaluated = [row for row in invariants if row["scope"] in {"standalone", "portfolio_contribution"}]
    assert evaluated
    assert {row["status"] for row in evaluated} == {"pass"}


def test_funnel_and_exact_next_action_reconcile() -> None:
    funnel = payload("cohort_funnel_counts.json")
    assert funnel == {
        "benchmark_references": 4,
        "blocked_or_inconclusive_strategies": 0,
        "closed_strategies": 2,
        "diversifier_followup_candidates": 0,
        "experiment_trials_executed": 2,
        "process_tasks": 1,
        "source_library_records_referenced": 2,
        "strategy_configurations_considered": 2,
    }
    assert rows("exploratory_followup_candidates.csv") == []
    assert {row["exact_next_action"] for row in rows("next_actions.csv")} == {"refresh_strategy_source_library_v3"}
    assert {row["execute_now"] for row in rows("next_actions.csv")} == {"false"}


def test_protected_inputs_and_every_cache_file_are_unchanged() -> None:
    check = payload("consistency_check.json")
    assert check["consistency_passed"] is True
    assert check["protected_state_hashes_unchanged"] is True
    assert check["authoritative_input_hashes_unchanged"] is True
    assert check["all_cache_hashes_unchanged"] is True
    assert check["protected_state_hashes_before"] == check["protected_state_hashes_after"]
    assert check["authoritative_input_hashes_before"] == check["authoritative_input_hashes_after"]
    assert check["cache_hashes_before"] == check["cache_hashes_after"]


def test_no_provider_or_prohibited_action_path_and_deterministic_accounting() -> None:
    source = inspect.getsource(batch)
    assert "yfinance" not in source.lower()
    assert "alpaca" not in source.lower()
    assert "refresh_cache\": False" in source
    check = payload("consistency_check.json")
    for key in batch.FORBIDDEN_FLAGS:
        assert check[key] is False
    index = pd.bdate_range("2025-01-02", periods=70)
    reference = pd.Series(0.0002, index=index)
    sleeve = pd.Series(0.0004, index=index)
    first = accounting_result(reference, sleeve)
    second = accounting_result(reference, sleeve)
    pd.testing.assert_series_equal(first["returns"], second["returns"])
    assert first["event_rows"] == second["event_rows"]


def accounting_result(reference: pd.Series, sleeve: pd.Series) -> dict:
    return batch.accounting.simulate_two_component_portfolio(reference, sleeve, "toy", 5.0)
