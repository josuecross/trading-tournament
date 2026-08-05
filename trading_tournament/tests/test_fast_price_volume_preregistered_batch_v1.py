from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from strategy_lab.research_os.research import (
    fast_price_volume_preregistered_batch_v1 as batch,
)


OUTPUT = batch.OUTPUT_DIR


def rows(name: str) -> list[dict[str, str]]:
    with (OUTPUT / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def payload(name: str) -> dict:
    return json.loads((OUTPUT / name).read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture(scope="module", autouse=True)
def generated_evidence() -> None:
    result = batch.run()
    assert result["overall_pass"] is True


def test_required_artifacts_and_exact_scope() -> None:
    required = {
        "batch_manifest.yaml",
        "source_and_rule_lineage.csv",
        "strategy_cards.csv",
        "trial_ledger.csv",
        "benchmark_reference_log.csv",
        "process_task_log.csv",
        "data_preflight_reconciliation.csv",
        "all_trial_results.csv",
        "control_results.csv",
        "chronological_half_results.csv",
        "portfolio_contribution_results.csv",
        "decelerated_psar_diagnostics.csv",
        "cmf20_diagnostics.csv",
        "kvo_diagnostics.csv",
        "force13_diagnostics.csv",
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
    assert manifest["strategy_configuration_count"] == 4
    assert manifest["canonical_experiment_trial_count"] == 4


def test_preregistered_entities_and_lineage_are_separate() -> None:
    sources = rows("source_and_rule_lineage.csv")
    strategies = rows("strategy_cards.csv")
    trials = rows("trial_ledger.csv")
    benchmarks = rows("benchmark_reference_log.csv")
    process = rows("process_task_log.csv")
    assert len(sources) == len(strategies) == len(trials) == 4
    assert len(benchmarks) == 20
    assert len(process) == 1
    assert {row["entity_type"] for row in sources} == {"source_library_record"}
    assert {row["entity_type"] for row in strategies} == {"strategy_configuration"}
    assert {row["entity_type"] for row in trials} == {"experiment_trial"}
    assert {row["entity_type"] for row in benchmarks} == {"benchmark_reference"}
    assert all(row["parent_trial_id"] == "" for row in trials)
    assert all(row["adaptation_label"] == "" for row in trials)
    assert all(row["optimization_performed"].lower() == "false" for row in trials)
    assert all(row["post_result_adaptation_allowed"].lower() == "false" for row in trials)


def test_spy_bil_preflight_and_no_provider_access() -> None:
    preflight = rows("data_preflight_reconciliation.csv")
    assert {row["symbol"] for row in preflight} == {"SPY", "BIL"}
    assert all(row["preflight_status"] == "pass" for row in preflight)
    assert all(row["provider_accessed"].lower() == "false" for row in preflight)
    assert all(row["canonical_file_hash"].startswith("sha256:") for row in preflight)
    assert all(row["canonical_frame_hash"].startswith("sha256:") for row in preflight)
    assert len({row["common_evaluation_start"] for row in preflight}) == 1
    assert len({row["common_evaluation_end"] for row in preflight}) == 1


def test_psar_contract_decelerates_and_original_control_does_not() -> None:
    ohlcv = batch.market.load_adjusted_ohlcv("SPY")
    candidate = batch.psar_frame(ohlcv, True)
    original = batch.psar_frame(ohlcv, False)
    assert set(candidate["trend"].unique()) <= {
        "uninitialized",
        "uptrend",
        "downtrend",
    }
    assert candidate["AF"].between(0.02, 0.20).all()
    assert original["AF"].between(0.02, 0.20).all()
    low_change = candidate["change3"].notna() & (candidate["change3"] <= 0.02)
    nonreversal = ~candidate["reversal"].astype(bool)
    assert (candidate.loc[low_change & nonreversal, "AF"] == 0.02).any()
    assert not candidate["AF"].equals(original["AF"])
    diagnostic = rows("decelerated_psar_diagnostics.csv")
    assert diagnostic
    assert all(
        not row["authorized_execution_date"]
        or pd.Timestamp(row["authorized_execution_date"]) > pd.Timestamp(row["signal_date"])
        for row in diagnostic
    )


def test_cmf_formula_zero_range_and_volume_weighting() -> None:
    diagnostic = rows("cmf20_diagnostics.csv")
    valid = [row for row in diagnostic if row["signal_valid"].lower() == "true"]
    assert valid
    sample = valid[len(valid) // 2]
    high = float(sample["adjusted_high"])
    low = float(sample["adjusted_low"])
    close = float(sample["adjusted_close"])
    expected = 0.0 if high == low else ((close - low) - (high - close)) / (high - low)
    assert np.isclose(float(sample["money_flow_multiplier"]), expected, atol=1e-12)
    assert "CLP20_control" in sample
    assert all(np.isfinite(float(row["CMF20"])) for row in valid)


def test_kvo_formula_and_frozen_ema_convention() -> None:
    diagnostic = rows("kvo_diagnostics.csv")
    valid = [row for row in diagnostic if row["signal_valid"].lower() == "true"]
    assert valid
    sample = valid[0]
    assert np.isclose(
        float(sample["KVO"]),
        float(sample["EMA34_volume_force"]) - float(sample["EMA55_volume_force"]),
        atol=1e-9,
    )
    assert sample["ema_initialization"] == (
        "recursive_adjust_false_first_finite_seed_output_after_span_valid_observations"
    )
    manifest = yaml.safe_load((OUTPUT / "batch_manifest.yaml").read_text(encoding="utf-8"))
    assert manifest["EMA_initialization_convention"] == sample["ema_initialization"]


def test_force_index_formula_and_price_only_control() -> None:
    diagnostic = rows("force13_diagnostics.csv")
    usable = [row for row in diagnostic if row["adjusted_close_change"]]
    assert usable
    sample = usable[len(usable) // 2]
    expected = float(sample["adjusted_close_change"]) * float(sample["adjusted_volume"])
    assert np.isclose(float(sample["Force1"]), expected, rtol=1e-12, atol=1e-6)
    assert "price_change_EMA13_control" in sample
    valid = [row for row in diagnostic if row["signal_valid"].lower() == "true"]
    assert valid


def test_results_costs_halves_controls_and_transitions_are_visible() -> None:
    trial_rows = rows("all_trial_results.csv")
    control_rows = rows("control_results.csv")
    halves = rows("chronological_half_results.csv")
    assert len(trial_rows) == 12
    by_strategy: dict[str, set[float]] = {}
    for row in trial_rows:
        by_strategy.setdefault(row["strategy_id"], set()).add(
            float(row["cost_assumption_bps"])
        )
        assert row["transition_count"] != ""
    assert all(costs == {0.0, 5.0, 10.0} for costs in by_strategy.values())
    assert len(control_rows) == 4 * 5 * 3
    assert {row["period_label"] for row in halves} == {
        "first_chronological_half",
        "second_chronological_half",
    }
    assert all(float(row["cost_assumption_bps"]) == 5.0 for row in halves)
    assert all("not_validation" in row["period_role"] for row in halves)


def test_exposure_controls_use_exact_mechanical_candidate_target_weight() -> None:
    outcomes = rows("outcome_summary.csv")
    for row in outcomes:
        weight = float(row["mechanical_full_period_average_target_SPY_weight"])
        assert 0.0 <= weight <= 1.0
        card = next(card for card in batch.CARDS if card.strategy_id == row["strategy_id"])
        controls = [
            control
            for control in rows("benchmark_reference_log.csv")
            if control["strategy_id"] == card.strategy_id
        ]
        assert sum(control["exposure_matched_control"].lower() == "true" for control in controls) == 1


def test_portfolio_contribution_is_explicit_monthly_80_20() -> None:
    portfolio = rows("portfolio_contribution_results.csv")
    assert len(portfolio) == 4 * 4 * 3
    assert {
        row["strategy_id"] for row in portfolio
    } == set(batch.EXPECTED_STRATEGY_IDS)
    assert all(
        row["portfolio_id"] == "100pct_frozen_reference"
        or "80pct_reference_20pct" in row["portfolio_id"]
        for row in portfolio
    )
    assert all(row["daily_fixed_weight_return_blend_used"].lower() == "false" for row in portfolio)
    assert all(float(row["maximum_gross_exposure"]) <= 1.0 + 1e-9 for row in portfolio)


def test_invariants_funnel_and_exact_next_action_reconcile() -> None:
    invariants = rows("invariant_results.csv")
    assert invariants
    assert all(row["invariant_pass"].lower() == "true" for row in invariants)
    assert all(row["negative_weights_present"].lower() == "false" for row in invariants)
    assert all(row["leverage_used"].lower() == "false" for row in invariants)
    assert all(
        row["same_period_price_signal_return_used"].lower() == "false"
        for row in invariants
    )
    funnel = payload("cohort_funnel_counts.json")
    assert funnel["outcome_count_reconciles"] is True
    assert funnel["canonical_experiment_trial_count"] == 4
    consistency = payload("consistency_check.json")
    expected = (
        batch.NEXT_REVIEW
        if funnel["total_followup_count"]
        else (
            batch.NEXT_BLOCKED
            if funnel["executed_candidate_count"] < 3
            else batch.NEXT_ALL_CLOSED
        )
    )
    assert consistency["exact_next_action"] == expected
    assert consistency["overall_pass"] is True


def test_protected_state_caches_prior_evidence_and_serial_rerun_are_deterministic() -> None:
    protected_before = {
        path: sha256(path) for path in batch.PROTECTED_STATE_PATHS if path.exists()
    }
    cache_before = {
        path: sha256(path) for path in batch.cache_inventory_files()
    }
    first = batch.run()
    artifact_names = {path.name for path in OUTPUT.iterdir() if path.is_file()}
    first_bytes = {name: (OUTPUT / name).read_bytes() for name in artifact_names}
    second = batch.run()
    second_bytes = {name: (OUTPUT / name).read_bytes() for name in artifact_names}
    protected_after = {
        path: sha256(path) for path in batch.PROTECTED_STATE_PATHS if path.exists()
    }
    cache_after = {
        path: sha256(path) for path in batch.cache_inventory_files()
    }
    assert first["overall_pass"] is True
    assert second["overall_pass"] is True
    assert first_bytes == second_bytes
    assert protected_before == protected_after
    assert cache_before == cache_after
