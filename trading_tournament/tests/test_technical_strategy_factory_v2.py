from __future__ import annotations

import csv
import json
import math

import numpy as np
import pandas as pd
import pytest
import yaml

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.research import technical_strategy_factory_v2 as subject


OUTPUT = ROOT / "evidence" / "technical_factory" / subject.TASK_ID / "latest"


def rows(name: str) -> list[dict[str, str]]:
    with (OUTPUT / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


@pytest.fixture(scope="session")
def frames() -> dict[str, pd.DataFrame]:
    _, loaded, passed = subject.preflight()
    assert passed
    return loaded


def spec(code: str) -> subject.VariantSpec:
    return next(item for item in subject.VARIANTS if item.code == code)


def first_valid(diagnostics: pd.DataFrame) -> pd.Series:
    return diagnostics[diagnostics["signal_valid"].astype(bool)].iloc[0]


def test_exact_factory_grid_and_unique_lineage() -> None:
    assert len(subject.PARAMETER_GRIDS) == 6
    assert len(subject.VARIANTS) == 24
    assert all(len(grid) == 4 for grid in subject.PARAMETER_GRIDS.values())
    assert len({item.strategy_id for item in subject.VARIANTS}) == 24
    assert len({item.trial_id for item in subject.VARIANTS}) == 24
    assert not any("factory_v1_" in item.strategy_id for item in subject.VARIANTS)


def test_credit_ratio_formula(frames: dict[str, pd.DataFrame]) -> None:
    item = subject.prepare_variant(spec("A1"), frames)
    row = first_valid(item["diagnostics"])
    date = pd.Timestamp(row["signal_date"])
    position = int(item["prices"].index.get_loc(date))
    lookback = int(row["lookback_sessions"])
    ratio = item["prices"]["HYG"] / item["prices"]["IEF"]
    expected_return = float(ratio.iloc[position] / ratio.iloc[position - lookback] - 1.0)
    expected_drawdown = float(
        ratio.iloc[position] / ratio.iloc[position - lookback + 1:position + 1].max() - 1.0
    )
    assert math.isclose(float(row["ratio_return"]), expected_return, abs_tol=1e-14)
    assert math.isclose(float(row["ratio_drawdown"]), expected_drawdown, abs_tol=1e-14)


def test_semivariance_formula(frames: dict[str, pd.DataFrame]) -> None:
    item = subject.prepare_variant(spec("B1"), frames)
    row = first_valid(item["diagnostics"])
    date = pd.Timestamp(row["signal_date"])
    position = int(item["prices"].index.get_loc(date))
    lookback = int(row["lookback_sessions"])
    values = item["prices"]["SPY"].pct_change(fill_method=None).iloc[
        position - lookback + 1:position + 1
    ].to_numpy(dtype=float)
    upside = float(np.mean(np.maximum(values, 0.0) ** 2))
    downside = float(np.mean(np.minimum(values, 0.0) ** 2))
    assert math.isclose(float(row["upside_semivariance"]), upside, abs_tol=1e-16)
    assert math.isclose(float(row["downside_semivariance"]), downside, abs_tol=1e-16)
    assert math.isclose(float(row["asymmetry_ratio"]), downside / upside, abs_tol=1e-14)


def test_cooldown_holds_exact_completed_performance_sessions() -> None:
    index = pd.bdate_range("2026-01-02", periods=40)
    prices = pd.DataFrame({"SPY": np.linspace(100.0, 104.0, len(index)), "BIL": 100.0}, index=index)
    trigger = pd.Series(False, index=index)
    trigger.iloc[21] = True
    events, _, _ = subject.cooldown_events(prices, trigger, 5)
    ordered = sorted(events)
    bil_entry = index[22]
    spy_exit = index[27]
    assert events[bil_entry]["BIL"] == 1.0
    assert events[spy_exit]["SPY"] == 1.0
    assert index.get_loc(spy_exit) - index.get_loc(bil_entry) == 5
    assert ordered.index(spy_exit) > ordered.index(bil_entry)


def test_residual_momentum_formula(frames: dict[str, pd.DataFrame]) -> None:
    item = subject.prepare_variant(spec("D1"), frames)
    row = first_valid(item["diagnostics"])
    date = pd.Timestamp(row["signal_date"])
    position = int(item["prices"].index.get_loc(date))
    lookback = int(row["lookback_sessions"])
    returns = item["prices"].pct_change(fill_method=None)
    market = returns["SPY"].iloc[position - lookback + 1:position + 1].to_numpy(dtype=float)
    sector = str(row["sector"])
    values = returns[sector].iloc[position - lookback + 1:position + 1].to_numpy(dtype=float)
    design = np.column_stack([np.ones(lookback), market])
    residual = values - design @ np.linalg.lstsq(design, values, rcond=None)[0]
    assert math.isclose(float(row["residual_score"]), float(residual.sum()), abs_tol=1e-16)


def test_capture_ratio_formula(frames: dict[str, pd.DataFrame]) -> None:
    item = subject.prepare_variant(spec("E1"), frames)
    row = first_valid(item["diagnostics"])
    date = pd.Timestamp(row["signal_date"])
    position = int(item["prices"].index.get_loc(date))
    lookback = int(row["lookback_sessions"])
    returns = item["prices"].pct_change(fill_method=None)
    market = returns["SPY"].iloc[position - lookback + 1:position + 1]
    sector_values = returns[str(row["sector"])].iloc[position - lookback + 1:position + 1]
    upside = float(sector_values[market.to_numpy() > 0.0].mean() / market[market > 0.0].mean())
    downside = float(sector_values[market.to_numpy() < 0.0].mean() / market[market < 0.0].mean())
    assert math.isclose(float(row["upside_capture"]), upside, abs_tol=1e-14)
    assert math.isclose(float(row["downside_capture"]), downside, abs_tol=1e-14)
    assert math.isclose(float(row["capture_score"]), upside - downside, abs_tol=1e-14)


def test_adjusted_open_decomposition_is_corporate_action_consistent(
    frames: dict[str, pd.DataFrame]
) -> None:
    item = subject.prepare_variant(spec("F1"), frames)
    assert item["adjusted_open_identity_max_error"] <= 1e-10


def test_required_output_set_and_frozen_artifacts() -> None:
    assert {path.name for path in OUTPUT.iterdir() if path.is_file()} == subject.REQUIRED_FILES
    consistency = json.loads((OUTPUT / "consistency_check.json").read_text(encoding="utf-8"))
    assert consistency["checks"]["preperformance_artifacts_immutable"] is True
    assert consistency["checks"]["selected_variant_route_freeze_immutable"] is True


def test_entity_and_route_counts_reconcile() -> None:
    assert len(rows("strategy_cards.csv")) == 24
    assert len(rows("trial_ledger.csv")) == 24
    assert len(rows("route_catalog.csv")) == 48
    assert len(rows("benchmark_reference_log.csv")) == 132
    assert len(rows("walk_forward_folds.csv")) == 30
    counts = json.loads((OUTPUT / "cohort_funnel_counts.json").read_text(encoding="utf-8"))
    assert counts["strategy_configurations"] == 24
    assert counts["canonical_experiment_trials"] == 24
    assert counts["total_route_fold_evaluations"] == 192
    assert counts["paper_demo_observations"] == 0


def test_both_routes_and_all_fold_boundaries_are_visible() -> None:
    matrix = rows("fold_pass_matrix.csv")
    assert len(matrix) == 192
    assert {row["route"] for row in matrix} == {"standalone", "20pct_diversifier"}
    for strategy_id in {row["strategy_id"] for row in matrix}:
        subset = [row for row in matrix if row["strategy_id"] == strategy_id]
        assert {(row["route"], row["fold_id"]) for row in subset} == {
            (route, f"fold_{fold}")
            for route in ("standalone", "20pct_diversifier") for fold in range(1, 5)
        }


def test_representative_diversifier_pass_flag_recomputes() -> None:
    matrix_row = rows("fold_pass_matrix.csv")[1]
    key = (matrix_row["strategy_id"], matrix_row["route"], matrix_row["fold_id"])
    source = rows("diversifier_fold_results.csv") if key[1] == "20pct_diversifier" else rows("standalone_fold_results.csv")
    subset = [
        row for row in source
        if (row["strategy_id"], row["route"], row["period_id"]) == key
    ]
    roles = {row["result_role"]: row for row in subset}
    candidate = {field: float(roles["candidate"][field]) for field in ("total_return", "cagr", "sharpe_ratio", "maximum_drawdown")}
    named = {field: float(roles["named_same_purpose_control"][field]) for field in ("total_return", "cagr", "sharpe_ratio", "maximum_drawdown")}
    static = {field: float(roles["exposure_static_control"][field]) for field in ("total_return", "cagr", "sharpe_ratio", "maximum_drawdown")}
    if key[1] == "standalone":
        expected = bool(
            candidate["total_return"] > 0.0
            and not subject.dominates(named, candidate)
            and not subject.dominates(static, candidate)
            and subject.material_advantage(candidate, named)
            and subject.material_advantage(candidate, static)
        )
    else:
        reference = {field: float(roles["frozen_reference"][field]) for field in ("total_return", "cagr", "sharpe_ratio", "maximum_drawdown")}
        expected = bool(
            subject.material_advantage(candidate, reference)
            and not subject.worse_on_both(candidate, reference)
            and not subject.dominates(named, candidate)
            and not subject.dominates(static, candidate)
            and subject.material_advantage(candidate, named)
            and subject.material_advantage(candidate, static)
        )
    assert (matrix_row["fold_pass"] == "true") is expected


def test_route_selection_tie_break_and_final_isolation() -> None:
    decisions = rows("variant_route_selection_decisions.csv")
    assert len(decisions) == 48
    selected = [row for row in decisions if row["selected_for_final_evaluation"] == "true"]
    assert all(row["selection_eligible"] == "true" and row["lexicographic_rank"] == "1" for row in selected)
    freeze = rows("selected_variant_route_freeze.csv")
    frozen = {
        row["selected_strategy_id"]: row["selected_route"]
        for row in freeze if row["selected_strategy_id"]
    }
    final = rows("final_evaluation_results.csv")
    assert {row["strategy_id"] for row in final} == set(frozen)
    assert all(row["route"] == frozen[row["strategy_id"]] for row in final)


def test_signal_and_execution_timing_invariants_pass() -> None:
    invariants = rows("invariant_results.csv")
    assert len(invariants) == 25
    assert all(row["overall_pass"] == "true" for row in invariants)
    assert all(
        row.get("following_regular_session_close_execution", "true") == "true"
        for row in invariants if row["architecture_id"] != "factory_v2_global"
    )


def test_consistency_protected_state_and_determinism() -> None:
    consistency = json.loads((OUTPUT / "consistency_check.json").read_text(encoding="utf-8"))
    assert consistency["overall_pass"] is True
    assert consistency["checks"]["deterministic_rerun_passed"] is True
    assert consistency["checks"]["protected_state_cache_and_prior_evidence_unchanged"] is True
    assert consistency["checks"]["no_Factory_V1_identifier_reused"] is True


def test_outcome_and_next_action_are_bounded() -> None:
    outcomes = rows("outcome_summary.csv")
    assert len(outcomes) == 6
    assert {row["architecture_outcome"] for row in outcomes} <= {
        "factory_exploratory_followup_candidate",
        "factory_architecture_closed",
        "factory_architecture_blocked",
    }
    manifest = yaml.safe_load((OUTPUT / "factory_manifest.yaml").read_text(encoding="utf-8"))
    allowed = {
        "direction_owner_review_technical_strategy_factory_v2_candidates",
        "direction_owner_review_technical_factory_two_pilot_yield_v1",
        "direction_owner_review_technical_factory_v2_block_v1",
    }
    assert manifest["exact_next_action"] in allowed
    report = (OUTPUT / "factory_report.md").read_text(encoding="utf-8")
    assert "not validation or robustness" in report
    assert "No provider" in report
