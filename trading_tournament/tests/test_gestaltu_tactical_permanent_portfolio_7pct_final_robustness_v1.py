from __future__ import annotations

import csv
import json

import numpy as np
import pandas as pd

from strategy_lab.research_os.research import (
    gestaltu_tactical_permanent_portfolio_7pct_final_robustness_v1 as task,
)


def rows(name: str) -> list[dict[str, str]]:
    with (task.OUTPUT_DIR / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_frozen_identity_and_trial_lineage() -> None:
    assert task.STRATEGY_ID == "gestaltu_tactical_permanent_portfolio_7pct_v1"
    assert task.TRIAL_ID == "gestaltu_tactical_permanent_portfolio_7pct_final_robustness_v1__child"
    assert task.PARENT_TRIAL_ID == "accepted47_source_v1__tactical_permanent_portfolio__canonical"
    assert task.UNIVERSE == ("SPY", "IEF", "GLD", "BIL")


def test_source_and_parent_lineage_reconcile() -> None:
    spec, context = task.lineage_context()
    assert spec.strategy_id == task.STRATEGY_ID
    assert context["checks"]["pass"]
    assert context["checks"]["caa_remains_closed"]


def test_tpp_inverse_volatility_and_target_formula() -> None:
    index = pd.bdate_range("2024-01-01", periods=80)
    returns = pd.DataFrame(
        {
            "SPY": np.tile([0.01, -0.005], 40),
            "IEF": np.tile([0.002, -0.001], 40),
            "GLD": np.tile([0.006, -0.003], 40),
            "BIL": np.full(80, 0.0001),
        },
        index=index,
    )
    target, diagnostic = task.exploration._tpp_weights(
        returns, 79, ["SPY", "IEF", "GLD"]
    )
    vol = returns[["SPY", "IEF", "GLD"]].iloc[-21:].std(ddof=1)
    expected_initial = (1.0 / vol) / (1.0 / vol).sum()
    covariance = returns[["SPY", "IEF", "GLD"]].iloc[-60:].cov(ddof=1).to_numpy()
    expected_pre_scale = np.sqrt(252.0 * expected_initial.to_numpy() @ covariance @ expected_initial.to_numpy())
    expected_scale = min(1.0, 0.07 / expected_pre_scale)
    assert np.isclose(diagnostic["pre_scale_portfolio_volatility"], expected_pre_scale)
    assert np.isclose(diagnostic["scale"], expected_scale)
    assert np.isclose(sum(target.values()), 1.0)
    assert target["BIL"] >= 0.0


def test_signal_and_execution_sessions_are_frozen() -> None:
    spec, _ = task.lineage_context()
    frames = {symbol: task.exploration.load_frame(symbol) for symbol in task.UNIVERSE}
    prepared = task.exploration.prepare_tpp(spec, frames)
    for row in prepared["ledger"]:
        signal = pd.Timestamp(row["signal_date"])
        execution = pd.Timestamp(row["execution_date"])
        month = prepared["prices"].index[prepared["prices"].index.to_period("M") == signal.to_period("M")]
        assert signal == month[-2]
        assert execution == month[-1]
        assert execution > signal


def test_monthly_metrics_are_exact() -> None:
    values = np.array([0.01, -0.02, 0.03, 0.00])
    result = task.monthly_metrics(values)
    wealth = np.cumprod(1.0 + values)
    assert np.isclose(result["total_return"], wealth[-1] - 1.0)
    assert np.isclose(result["cagr"], wealth[-1] ** 3.0 - 1.0)


def test_paired_bootstrap_is_deterministic() -> None:
    rng = np.random.default_rng(42)
    frame = pd.DataFrame(
        rng.normal(0.005, 0.02, size=(72, 4)),
        columns=[task.STRATEGY_ID, *task.DECISIVE_CONTROLS],
    )
    first = task.paired_moving_block_bootstrap(frame, resamples=100, seed=task.BOOTSTRAP_SEED)
    second = task.paired_moving_block_bootstrap(frame, resamples=100, seed=task.BOOTSTRAP_SEED)
    assert first == second
    assert len(first) == 3


def test_required_packet_and_parent_reproduction_pass() -> None:
    assert all((task.OUTPUT_DIR / name).is_file() for name in task.REQUIRED_FILES)
    reproduction = rows("parent_reproduction_check.csv")
    assert reproduction
    assert {row["pass"] for row in reproduction} == {"true"}


def test_exactly_one_robustness_child_and_six_benchmarks() -> None:
    trials = rows("trial_ledger.csv")
    assert len(trials) == 1
    assert trials[0]["trial_id"] == task.TRIAL_ID
    assert trials[0]["parent_trial_id"] == task.PARENT_TRIAL_ID
    assert trials[0]["changed_fields_from_parent"] == "robustness_diagnostics_only"
    assert trials[0]["source_rule_changed"] == "false"
    benchmarks = rows("benchmark_reference_log.csv")
    assert len(benchmarks) == 6
    assert {row["benchmark_id"] for row in benchmarks} == set(task.ALL_CONTROLS)


def test_cost_stress_has_candidate_and_all_decisive_controls() -> None:
    results = rows("cost_stress_results.csv")
    assert len(results) == len(task.COSTS) * 4
    assert {float(row["cost_bps_one_way"]) for row in results} == set(task.COSTS)
    assert {row["series_id"] for row in results} == {task.STRATEGY_ID, *task.DECISIVE_CONTROLS}


def test_rolling_windows_retain_every_control_and_unfavorable_result() -> None:
    for filename, months in (("rolling_36_month_results.csv", 36), ("rolling_60_month_results.csv", 60)):
        result = rows(filename)
        assert result
        assert {int(row["window_months"]) for row in result} == {months}
        assert {row["comparison_control_id"] for row in result} == set(task.DECISIVE_CONTROLS)
        assert {row["unfavorable_result_retained"] for row in result} == {"true"}


def test_attribution_contains_all_assets_and_component_controls() -> None:
    result = rows("asset_component_attribution.csv")
    assets = {row["asset"] for row in result if row["record_type"] == "asset_detail"}
    summaries = {
        row["comparison_control_id"]
        for row in result
        if row["record_type"] == "control_concentration_summary"
    }
    assert assets == set(task.UNIVERSE)
    assert summaries == set(task.DECISIVE_CONTROLS)


def test_volatility_binding_excludes_cash_only_months() -> None:
    spec, _ = task.lineage_context()
    frames = {symbol: task.exploration.load_frame(symbol) for symbol in task.UNIVERSE}
    prepared = task.exploration.prepare_tpp(spec, frames)
    eligible = [row for row in prepared["ledger"] if row.get("selected_assets")]
    expected = np.mean([float(row["scale_factor"]) < 1.0 - task.TOLERANCE for row in eligible])
    diagnostics = rows("selection_and_scaling_diagnostics.csv")
    actual = next(
        float(row["value"])
        for row in diagnostics
        if row["diagnostic"] == "volatility_target_binding_frequency"
    )
    assert np.isclose(actual, expected)


def test_neutralization_replaces_without_deleting() -> None:
    result = rows("neutralization_results.csv")
    assert len(result) == 9
    assert {row["observations_deleted"] for row in result} == {"false"}
    assert {row["canonical_return_series_modified"] for row in result} == {"false"}
    assert {row["neutralized_against_control_id"] for row in result} == set(task.DECISIVE_CONTROLS)


def test_bootstrap_contract_and_determinism_are_recorded() -> None:
    result = rows("paired_block_bootstrap_results.csv")
    assert len(result) == 3
    assert {int(row["resamples"]) for row in result} == {5000}
    assert {int(row["moving_block_length_months"]) for row in result} == {12}
    assert {int(row["deterministic_seed"]) for row in result} == {20260806}
    assert {row["paired_cross_series_dependence_preserved"] for row in result} == {"true"}


def test_entity_counts_and_consistency_pass() -> None:
    funnel = json.loads((task.OUTPUT_DIR / "cohort_funnel_counts.json").read_text(encoding="utf-8"))
    consistency = json.loads((task.OUTPUT_DIR / "consistency_check.json").read_text(encoding="utf-8"))
    assert funnel["new_robustness_trials"] == 1
    assert funnel["new_strategy_configurations"] == 0
    assert funnel["validation_observations"] == 0
    assert funnel["paper_demo_observations"] == 0
    assert consistency["overall_pass"]
    assert consistency["protected_state_cache_source_and_prior_evidence_unchanged"]
