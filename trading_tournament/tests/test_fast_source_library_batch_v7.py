from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from strategy_lab.research_os.research import fast_source_library_batch_v7 as batch


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
    "absorption_ratio_diagnostics.csv",
    "fip_signal_diagnostics.csv",
    "low_max_signal_diagnostics.csv",
    "high_volume_event_diagnostics.csv",
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
        "Run the dedicated V7 serial runner before focused tests."
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
    assert manifest["batch_id"] == "fast_source_library_batch_v7"
    assert manifest["mode"] == "fast-progress"
    assert manifest["stage"] == "exploration"
    assert tuple(manifest["strategy_ids"]) == batch.EXPECTED_STRATEGY_IDS
    assert manifest["strategy_configuration_count"] == 4
    assert manifest["canonical_experiment_trial_count"] == 4
    assert manifest["executed_trial_count"] == 4
    assert manifest["preregistration_written_before_performance_calculation"] is True
    assert manifest["preregistration_checkpoint_hash"].startswith("sha256:")
    assert manifest["validation_claimed"] is False
    assert manifest["lifecycle_state_changed"] is False


def test_strategy_trial_and_control_entities_are_separate_and_complete() -> None:
    strategies = rows("strategy_cards.csv")
    trials = rows("trial_ledger.csv")
    sources = rows("source_library_records.csv")
    benchmarks = rows("benchmark_reference_log.csv")
    process = rows("process_task_log.csv")
    assert len(strategies) == len(trials) == len(sources) == 4
    assert tuple(row["strategy_id"] for row in strategies) == batch.EXPECTED_STRATEGY_IDS
    assert {row["entity_type"] for row in strategies} == {"strategy_configuration"}
    assert {row["entity_type"] for row in trials} == {"experiment_trial"}
    assert {row["entity_type"] for row in sources} == {"source_library_record"}
    assert {row["entity_type"] for row in benchmarks} == {"benchmark_reference"}
    assert {row["stage"] for row in strategies + trials} == {"exploration"}
    assert {row["parent_trial_id"] for row in trials} == {""}
    assert {row["adaptation_label"] for row in trials} == {""}
    assert len({row["trial_id"] for row in trials}) == 4
    assert len(process) == 1
    assert process[0]["entity_type"] == "process_task"
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
    assert all(
        all(row[field] not in {"", "unknown", "unmapped"} for field in required)
        for row in strategies + trials
    )


def test_preflight_uses_exact_cache_without_provider_attempt() -> None:
    preflight = rows("data_preflight_reconciliation.csv")
    assert {row["symbol"] for row in preflight} == set(batch.COMMON_REQUIRED_SYMBOLS)
    assert {row["candidate_preflight_status"] for row in preflight} == {"pass"}
    assert {row["ordered_unique_dates"] for row in preflight} == {"true"}
    assert {row["finite_positive_prices"] for row in preflight} == {"true"}
    assert {row["finite_nonnegative_adjusted_volume"] for row in preflight} == {
        "true"
    }
    assert {row["valid_ohlc_relationships"] for row in preflight} == {"true"}
    assert {row["canonical_adjustment_compatible"] for row in preflight} == {
        "true"
    }
    assert rows("data_capability_task_log.csv") == []


def test_absorption_ratio_contract_and_state_diagnostics() -> None:
    card = batch.CARDS[0]
    assert card.parameters["covariance_window"] == 500
    assert card.parameters["exponential_half_life"] == 250
    assert card.parameters["absorbed_components"] == 2
    assert card.parameters["short_average"] == 15
    assert card.parameters["long_average_and_sample_sd"] == 252
    assert card.parameters["thresholds"] == [-1.0, 1.0]

    values = np.array([[1.0, 2.0], [2.0, 4.0], [4.0, 1.0]])
    weights = np.array([0.2, 0.3, 0.5])
    covariance = batch.weighted_covariance(values, weights)
    centered = values - np.sum(values * weights[:, None], axis=0)
    expected = (centered * weights[:, None]).T @ centered
    assert np.allclose(covariance, expected)

    diagnostics = rows("absorption_ratio_diagnostics.csv")
    valid = [row for row in diagnostics if row["absorption_ratio"]]
    assert valid
    for row in valid[:20]:
        eigenvalues = [float(row[f"eigenvalue_{number}"]) for number in range(1, 10)]
        assert all(
            eigenvalues[position] >= eigenvalues[position + 1] - 1e-14
            for position in range(8)
        )
        expected_ar = (eigenvalues[0] + eigenvalues[1]) / sum(eigenvalues)
        assert np.isclose(float(row["absorption_ratio"]), expected_ar, rtol=1e-9)
    for row in diagnostics:
        state = row["resulting_state"]
        expected_exposure = {"defensive": 0.0, "balanced": 0.5, "risk_on": 1.0}[state]
        assert np.isclose(float(row["target_SPY_exposure"]), expected_exposure)


def test_high_volume_anchor_blocks_and_qualifiers_are_frozen() -> None:
    diagnostics = rows("high_volume_event_diagnostics.csv")
    assert diagnostics
    for left, right in zip(diagnostics, diagnostics[1:]):
        left_anchor = pd.Timestamp(left["block_start"])
        right_anchor = pd.Timestamp(right["block_start"])
        prices = batch.market.load_price_frame(batch.CARDS[1].required_symbols)
        assert int(prices.index.get_loc(right_anchor)) - int(
            prices.index.get_loc(left_anchor)
        ) == 51
    for row in diagnostics:
        ranks = json.loads(row["dollar_volume_ranks_descending"])
        expected = sorted(symbol for symbol, rank in ranks.items() if int(rank) <= 5)
        assert json.loads(row["qualifying_sectors"]) == expected
        if row["holding_period_end"]:
            assert row["holding_return_session_count"] == "20"


def test_fip_formula_selection_and_vintage_contract() -> None:
    diagnostics = [
        row for row in rows("fip_signal_diagnostics.csv") if row["signal_complete"] == "true"
    ]
    assert diagnostics
    for row in diagnostics:
        pret = json.loads(row["PRET"])
        ids = json.loads(row["information_discreteness_ID"])
        ranks = json.loads(row["PRET_ranks_descending"])
        top3 = json.loads(row["top3_PRET_sectors"])
        assert sorted(top3, key=lambda symbol: (int(ranks[symbol]), symbol)) == top3
        expected = min(top3, key=lambda symbol: (float(ids[symbol]), symbol))
        assert row["selected_sector"] == expected
        assert all(symbol in pret for symbol in batch.SECTOR_UNIVERSE)
        assert 1 <= int(row["active_vintage_count"]) <= 6


def test_low_max_and_realized_volatility_ranks_are_independent() -> None:
    diagnostics = [
        row
        for row in rows("low_max_signal_diagnostics.csv")
        if row["signal_complete"] == "true"
    ]
    assert diagnostics
    for row in diagnostics:
        counts = json.loads(row["valid_return_count"])
        assert min(int(value) for value in counts.values()) >= 15
        max_ranks = json.loads(row["MAX_ranks_ascending"])
        vol_ranks = json.loads(row["volatility_ranks_ascending"])
        selected = json.loads(row["low_MAX_selected_sectors"])
        vol_selected = json.loads(row["low_volatility_selected_sectors"])
        assert selected == sorted(
            batch.SECTOR_UNIVERSE, key=lambda symbol: (int(max_ranks[symbol]), symbol)
        )[:3]
        assert vol_selected == sorted(
            batch.SECTOR_UNIVERSE, key=lambda symbol: (int(vol_ranks[symbol]), symbol)
        )[:3]


def test_costs_halves_turnover_and_invariants_reconcile() -> None:
    trials = rows("all_trial_results.csv")
    controls = rows("control_results.csv")
    halves = rows("chronological_half_results.csv")
    invariants = rows("invariant_results.csv")
    assert len(trials) == 12
    assert {row["cost_assumption_bps"] for row in trials} == {"0", "5", "10"}
    assert controls and halves and invariants
    assert {
        row["period_label"] for row in halves
    } == {"first_chronological_half", "second_chronological_half"}
    assert all("not_clean" in row["period_role"] for row in halves)
    assert {row["invariant_pass"] for row in invariants} == {"true"}
    assert {row["explicit_zero_weights"] for row in invariants} == {"true"}
    assert {row["stale_weight_forward_fill_used"] for row in invariants} == {
        "false"
    }
    assert all(float(row["maximum_gross_exposure"]) <= 1.0 + 1e-9 for row in invariants)
    assert all(float(row["maximum_daily_weight_sum"]) <= 1.0 + 1e-9 for row in invariants)
    assert all(float(row["maximum_single_asset_weight"]) <= 1.0 + 1e-9 for row in invariants)
    turnover = rows("turnover_cost_reconciliation.csv")
    assert {
        row["turnover_formula"] for row in turnover
    } == {"0.5*sum(abs(target_weight-pretrade_weight))"}
    assert any(
        row["cost_assumption_bps"] == "5"
        and float(row["total_one_way_turnover"]) > 0.0
        and float(row["transaction_cost_drag"]) > 0.0
        for row in turnover
    )


def test_named_half_controls_outcomes_and_funnel_are_fixed() -> None:
    outcomes = rows("outcome_summary.csv")
    assert len(outcomes) == 4
    assert {row["outcome"] for row in outcomes} == {"closed_exploration"}
    assert {
        row["strategy_id"]: row["frozen_same_purpose_control"]
        for row in outcomes
    } == batch.EXPLICIT_FROZEN_FOLLOWUP_GATE_CONTROLS
    funnel = json_payload("cohort_funnel_counts.json")
    assert funnel["source_library_records_referenced"] == 4
    assert funnel["strategy_configurations_considered"] == 4
    assert funnel["experiment_trials_recorded"] == 4
    assert funnel["experiment_trials_executed"] == 4
    assert funnel["standalone_followup_candidates"] == 0
    assert funnel["diversifier_followup_candidates"] == 0
    assert funnel["closed_exploration"] == 4
    assert funnel["outcome_count_reconciles"] is True
    assert funnel["exact_next_action"] == batch.NEXT_ALL_CLOSED


def test_portfolio_contribution_is_monthly_80_20_with_natural_drift() -> None:
    portfolios = rows("portfolio_contribution_results.csv")
    assert portfolios
    assert {
        row["portfolio_construction"] for row in portfolios
    } == {
        "100pct_frozen_reference",
        "monthly_rebalanced_80pct_reference_plus_20pct_candidate_or_principal_control_with_natural_drift",
    }
    assert {
        row["period_label"] for row in portfolios
    } == {"full_period", "first_chronological_half", "second_chronological_half"}
    check = json_payload("consistency_check.json")
    assert check["portfolio_contribution_uses_monthly_rebalanced_80_20_natural_drift"] is True
    assert check["daily_fixed_weight_return_blend_used"] is False


def test_protected_state_cache_prior_evidence_and_guardrails_reconcile() -> None:
    check = json_payload("consistency_check.json")
    assert check["consistency_passed"] is True
    assert check["protected_state_unchanged"] is True
    assert check["prior_evidence_unchanged"] is True
    assert check["cache_changes_authorized_and_logged"] is True
    assert check["cache_changed_paths"] == []
    assert check["bounded_provider_attempt_count"] == 0
    assert check["all_executed_invariants_passed"] is True
    assert check["half_period_controls_selected_from_full_period_performance"] is False
    assert check["source_packet_attachment_present"] is True
    assert check["source_packet_unchanged"] is True
    assert not any(check["forbidden_actions"].values())


def test_frozen_core_hash_is_deterministic() -> None:
    first = batch.deterministic_core_hash()
    second = batch.deterministic_core_hash()
    assert first == second
    assert first.startswith("sha256:")
