from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from strategy_lab.research_os.research import fast_source_library_batch_v6 as batch


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "research_recovery" / batch.BATCH_ID / "latest"

REQUIRED_ARTIFACTS = {
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
    "turnover_cost_reconciliation.csv",
    "recovery_signal_diagnostics.csv",
    "olmar_weight_diagnostics.csv",
    "dogs_vintage_diagnostics.csv",
    "high52_vintage_diagnostics.csv",
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
        "Run the dedicated V6 serial runner before focused tests."
    )


def rows(name: str) -> list[dict[str, str]]:
    with (EVIDENCE / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def json_payload(name: str) -> dict:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def yaml_payload(name: str) -> dict:
    return yaml.safe_load((EVIDENCE / name).read_text(encoding="utf-8"))


def test_exact_scope_required_artifacts_and_preregistration() -> None:
    assert REQUIRED_ARTIFACTS.issubset({path.name for path in EVIDENCE.iterdir()})
    manifest = yaml_payload("batch_manifest.yaml")
    assert manifest["batch_id"] == batch.BATCH_ID
    assert manifest["mode"] == "fast-progress"
    assert manifest["stage"] == "exploration"
    assert tuple(manifest["strategy_ids"]) == batch.EXPECTED_STRATEGY_IDS
    assert manifest["strategy_configuration_count"] == 4
    assert manifest["canonical_experiment_trial_count"] == 4
    assert manifest["preregistration_written_before_performance_calculation"] is True
    assert manifest["preregistration_checkpoint_hash"].startswith("sha256:")
    assert manifest["validation_claimed"] is False
    assert manifest["promotion_authorized"] is False
    assert manifest["paper_demo_authorized"] is False
    assert manifest["lifecycle_state_changed"] is False


def test_strategy_and_trial_metadata_are_complete_and_canonical() -> None:
    strategies = rows("strategy_cards.csv")
    trials = rows("trial_ledger.csv")
    assert len(strategies) == len(trials) == 4
    assert tuple(row["strategy_id"] for row in strategies) == batch.EXPECTED_STRATEGY_IDS
    assert {row["entity_type"] for row in strategies} == {"strategy_configuration"}
    assert {row["entity_type"] for row in trials} == {"experiment_trial"}
    assert {row["stage"] for row in strategies + trials} == {"exploration"}
    assert len({row["trial_id"] for row in trials}) == 4
    assert {row["parent_trial_id"] for row in trials} == {""}
    assert {row["adaptation_label"] for row in trials} == {""}
    assert {row["results_viewed_before_preregistration"] for row in trials} == {
        "false"
    }
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
    assert all(all(row[field] not in {"", "unknown", "unmapped"} for field in required) for row in strategies)


def test_source_packet_and_controls_remain_separate_entities() -> None:
    sources = rows("source_library_records.csv")
    benchmarks = rows("benchmark_reference_log.csv")
    process = rows("process_task_log.csv")
    assert len(sources) == 4
    assert {row["entity_type"] for row in sources} == {"source_library_record"}
    assert {row["stage"] for row in sources} == {"source_extracted"}
    assert {row["counted_as_strategy"] for row in sources} == {"false"}
    assert {row["entity_type"] for row in benchmarks} == {"benchmark_reference"}
    assert {row["stage"] for row in benchmarks} == {"benchmark_reference_only"}
    assert {row["counted_as_strategy"] for row in benchmarks} == {"false"}
    assert {row["counted_as_trial"] for row in benchmarks} == {"false"}
    assert len(process) == 1
    assert process[0]["entity_type"] == "process_task"
    assert process[0]["stage"] == "exploration"
    assert process[0]["strategy_counted"] == "false"
    assert process[0]["trial_counted"] == "false"
    assert not any(
        "PAMR" in row["benchmark_or_control_id"]
        or "ANTICOR" in row["benchmark_or_control_id"]
        for row in benchmarks
    )


def test_recovery_score_uses_max_drawdown_trough() -> None:
    index = pd.date_range("2024-01-01", periods=30, freq="B")
    base = np.array(
        [100, 105, 110, 100, 90, 80, 82, 84, 86, 88] + list(np.linspace(89, 100, 20)),
        dtype=float,
    )
    prices = pd.DataFrame(
        {symbol: base * (1.0 + position * 0.001) for position, symbol in enumerate(batch.SECTOR_UNIVERSE)},
        index=index,
    )
    inputs = batch.weekly_recovery_inputs(prices, index[-1])
    assert inputs is not None
    recovery, troughs, cumulative = inputs
    expected_trough = index[5].date().isoformat()
    assert set(troughs.values()) == {expected_trough}
    assert np.isclose(recovery["XLB"], np.log(base[-1] / base[5]))
    assert np.isclose(cumulative["XLB"], np.log(base[-1] / base[0]))


def test_olmar_simplex_and_frozen_parameters() -> None:
    projected = batch.project_simplex(np.array([2.0, -1.0, 0.5]))
    assert np.isclose(projected.sum(), 1.0)
    assert (projected >= 0.0).all()
    card = next(card for card in batch.CARDS if card.strategy_id == "li_hoi_olmar5_sector_etf_v1")
    assert card.parameters["moving_average_window"] == 5
    assert card.parameters["epsilon"] == 10.0
    diagnostics = rows("olmar_weight_diagnostics.csv")
    daily = [row for row in diagnostics if row["record_type"] == "daily_target"]
    summary = [row for row in diagnostics if row["record_type"] == "summary"]
    assert daily and len(summary) == 1
    assert all(np.isclose(sum(json.loads(row["target_weights"]).values()), 1.0) for row in daily)
    assert all(min(json.loads(row["target_weights"]).values()) >= -1e-12 for row in daily)
    assert 0.0 <= float(summary[0]["percentage_days_any_weight_exceeds_50pct"]) <= 1.0


def test_data_preflight_blocks_country_without_substitution_or_provider_call() -> None:
    preflight = rows("data_preflight_reconciliation.csv")
    country = [
        row
        for row in preflight
        if row["strategy_id"] == "dogs_world_country_reversal_5x5_v1"
    ]
    missing = {
        row["symbol"] for row in country if row["preflight_status"] == "fail"
    }
    assert missing == {"ACWI", "EWI", "EWL", "EWM", "EWN", "EWP", "EWS", "EWT", "EWW"}
    assert all(row["bounded_provider_attempt_count"] == "0" for row in country)
    assert rows("data_capability_task_log.csv") == []
    outcomes = {row["strategy_id"]: row for row in rows("outcome_summary.csv")}
    dogs = outcomes["dogs_world_country_reversal_5x5_v1"]
    assert dogs["executed"] == "false"
    assert dogs["outcome"] == "inconclusive_data_issue"
    assert dogs["failure_reason"] == "data_unavailable"
    assert all(symbol in dogs["missing_symbols"] for symbol in missing)


def test_executable_results_costs_halves_and_invariants_reconcile() -> None:
    trial_results = rows("all_trial_results.csv")
    controls = rows("control_results.csv")
    halves = rows("chronological_half_results.csv")
    invariants = rows("invariant_results.csv")
    executed_ids = {
        "choi_recovery_sector_contrarian_6x6_v1",
        "li_hoi_olmar5_sector_etf_v1",
        "george_hwang_52week_high_sector_v1",
    }
    executed_trials = [row for row in trial_results if row["strategy_id"] in executed_ids]
    assert {row["cost_assumption_bps"] for row in executed_trials} == {"0", "5", "10"}
    assert len(executed_trials) == 9
    assert {
        row["period_label"]
        for row in halves
        if row["strategy_id"] in executed_ids
    } == {"first_chronological_half", "second_chronological_half"}
    assert all(
        "not_clean_sealed_or_validation" in row["period_role"]
        for row in halves
        if row["strategy_id"] in executed_ids
    )
    assert controls
    assert invariants
    assert {row["invariant_pass"] for row in invariants} == {"true"}
    assert {row["explicit_zero_weights"] for row in invariants} == {"true"}
    assert {row["natural_drift_between_rebalances"] for row in invariants} == {
        "true"
    }
    assert {row["stale_weight_forward_fill_used"] for row in invariants} == {
        "false"
    }
    assert {row["negative_weights_present"] for row in invariants} == {"false"}
    assert {row["same_period_price_signal_return_used"] for row in invariants} == {
        "false"
    }


def test_turnover_uses_drifted_pretrade_weights_and_costs() -> None:
    turnover = rows("turnover_cost_reconciliation.csv")
    assert turnover
    assert {
        row["turnover_formula"] for row in turnover
    } == {"0.5*sum(abs(target_weight-pretrade_weight))"}
    assert {row["natural_drift_between_rebalances"] for row in turnover} == {
        "true"
    }
    five_bps = [
        row
        for row in turnover
        if row["cost_assumption_bps"] == "5"
        and float(row["total_one_way_turnover"]) > 0.0
    ]
    assert five_bps
    assert all(float(row["transaction_cost_drag"]) > 0.0 for row in five_bps)

    index = pd.date_range("2024-01-02", periods=3, freq="B")
    reference = pd.Series([0.0, 1.0, 0.0], index=index)
    sleeve = pd.Series([0.0, 0.0, 0.0], index=index)
    path = batch.portfolio_accounting.simulate_two_component_portfolio(
        reference, sleeve, "test_80_20", 0.0
    )
    second_month = path["daily_df"].iloc[1]
    assert np.isclose(second_month["one_way_turnover"], 0.0)
    assert np.isclose(path["daily_df"].iloc[2]["max_daily_weight_sum"], 1.0)


def test_portfolio_contribution_is_monthly_80_20_not_fixed_return_blend() -> None:
    portfolios = rows("portfolio_contribution_results.csv")
    assert portfolios
    constructions = {row["portfolio_construction"] for row in portfolios}
    assert constructions == {
        "100pct_frozen_reference",
        "monthly_rebalanced_80pct_reference_plus_20pct_candidate_or_principal_control_with_natural_drift",
    }
    assert {
        row["period_label"] for row in portfolios
    } == {"full_period", "first_chronological_half", "second_chronological_half"}
    check = json_payload("consistency_check.json")
    assert check["portfolio_contribution_uses_monthly_rebalanced_80_20_natural_drift"] is True
    assert check["daily_fixed_weight_return_blend_used"] is False


def test_candidate_specific_diagnostics_are_present() -> None:
    recovery = rows("recovery_signal_diagnostics.csv")
    high52 = rows("high52_vintage_diagnostics.csv")
    dogs = rows("dogs_vintage_diagnostics.csv")
    assert recovery
    assert high52
    assert dogs == []
    assert any(row["signal_complete"] == "true" for row in recovery)
    assert all(row["maximum_drawdown_trough_dates"] for row in recovery if row["signal_complete"] == "true")
    assert any(row["warmup_complete"] == "true" for row in high52)
    assert all(
        0 <= int(row["selection_overlap_count"]) <= 3
        for row in high52
        if row["warmup_complete"] == "true"
    )


def test_outcomes_funnel_and_next_action_are_arithmetically_consistent() -> None:
    outcomes = rows("outcome_summary.csv")
    funnel = json_payload("cohort_funnel_counts.json")
    assert len(outcomes) == 4
    assert funnel["source_library_records_referenced"] == 4
    assert funnel["strategy_configurations_considered"] == 4
    assert funnel["experiment_trials_recorded"] == 4
    assert funnel["experiment_trials_executed"] == 3
    assert funnel["inconclusive_data_issue"] == 1
    assert (
        funnel["standalone_followup_candidates"]
        + funnel["diversifier_followup_candidates"]
        + funnel["closed_exploration"]
        + funnel["inconclusive_data_issue"]
        + funnel["blocked_feasibility"]
        == 4
    )
    followups = [
        row
        for row in outcomes
        if row["outcome"].startswith("exploratory_followup_candidate_")
    ]
    expected = (
        batch.NEXT_REVIEW
        if followups
        else batch.NEXT_ALL_CLOSED
    )
    assert funnel["exact_next_action"] == expected
    assert all(row["validation_claimed"] == "false" for row in outcomes)
    assert all(row["promotion_authorized"] == "false" for row in outcomes)


def test_protected_state_prior_evidence_cache_and_guardrails_reconcile() -> None:
    check = json_payload("consistency_check.json")
    assert check["consistency_passed"] is True
    assert check["protected_state_unchanged"] is True
    assert check["prior_evidence_unchanged"] is True
    assert check["cache_changes_authorized_and_logged"] is True
    assert check["cache_changed_paths"] == []
    assert check["bounded_provider_attempt_count"] == 0
    assert check["all_executed_invariants_passed"] is True
    assert check["source_packet_attachment_present"] is True
    assert check["source_packet_unchanged"] is True
    assert check["preregistration_checkpoint_written_before_performance_calculation"] is True
    assert not any(check["forbidden_actions"].values())
    active = yaml.safe_load(
        (
            ROOT
            / "strategy_lab"
            / "research_os"
            / "operations"
            / "active_observations.yaml"
        ).read_text(encoding="utf-8")
    )
    angl = [
        row
        for row in active["active_observations"]
        if row.get("observation_id") == "paper_forward_angl_20pct_diversifier_v1"
    ]
    assert len(angl) == 1
    assert angl[0]["stage"] == "deferred"
    assert angl[0]["paper_demo_active"] is False


def test_frozen_core_hash_is_deterministic() -> None:
    first = batch.deterministic_core_hash()
    second = batch.deterministic_core_hash()
    assert first == second
    assert first.startswith("sha256:")
