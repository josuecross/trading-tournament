from __future__ import annotations

import ast
import csv
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from strategy_lab.research_os.research import hrp_core_multi_asset_monthly_252d_exploratory_v1 as exploratory


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = ROOT / "reports" / "strategy_research" / exploratory.ARTIFACT_ID


def read_csv(name: str) -> list[dict[str, str]]:
    path = ARTIFACT_DIR / name
    assert path.exists(), f"missing artifact {path}"
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_json(name: str) -> dict[str, object]:
    path = ARTIFACT_DIR / name
    assert path.exists(), f"missing artifact {path}"
    return json.loads(path.read_text(encoding="utf-8"))


def test_monthly_252_day_rolling_estimation_and_no_lookahead() -> None:
    prices = exploratory.load_price_data(ROOT)
    dates = exploratory.freeze_evaluation_dates(prices)
    first_window = exploratory.common_returns(prices.close, dates.first_signal_date)

    assert len(first_window) == 252
    assert first_window.index[-1] == dates.first_signal_date
    assert dates.first_signal_date < dates.first_execution_date
    assert dates.evaluation_start == dates.first_execution_date
    assert tuple(prices.close.columns) == exploratory.FROZEN_SYMBOLS


def test_no_dynamic_universe_dropping_and_frozen_hash() -> None:
    frozen = read_json("frozen_universe.json")

    assert tuple(frozen["symbols"]) == exploratory.FROZEN_SYMBOLS
    assert frozen["frozen_universe_hash"] == exploratory.FROZEN_UNIVERSE_HASH
    assert frozen["dynamic_universe_changes_allowed"] is False


def test_trial_registration_has_exact_12_completed_runs() -> None:
    rows = read_csv("trial_registry.csv")

    assert len(rows) == 12
    assert {row["method_id"] for row in rows} == set(exploratory.METHODS)
    assert {int(row["cost_bps_per_side"]) for row in rows} == set(exploratory.COST_LEVELS_BPS)
    assert all(row["registered_before_performance"] == "True" for row in rows)
    assert all(row["status"] == "COMPLETED" for row in rows)
    assert all(row["failure_code"] == "" for row in rows)


def test_chronological_blocks_are_consecutive_and_start_at_evaluation_start() -> None:
    manifest = read_json("pre_registered_manifest.json")
    blocks = manifest["chronological_diagnostic_blocks"]
    evaluation_start = pd.Timestamp(manifest["common_price_period"]["evaluation_start"])

    assert pd.Timestamp(blocks[0]["start_date"]) == evaluation_start
    for previous, current in zip(blocks, blocks[1:]):
        assert pd.Timestamp(current["start_date"]) == pd.Timestamp(previous["start_date"]) + pd.DateOffset(years=5)
        assert pd.Timestamp(current["start_date"]) > pd.Timestamp(previous["end_date"])


def test_hrp_identity_complete_state_equivalence() -> None:
    rows = read_csv("identity_equivalence.csv")

    assert len(rows) == 3
    assert all(row["equivalence_status"] == "PASS" for row in rows)
    for row in rows:
        assert row["hrp_state_hash"] == row["identity_state_hash"]
        assert row["monthly_signals_equal"] == "True"
        assert row["daily_positions_equal"] == "True"
        assert row["daily_cash_and_nav_equal"] == "True"


def test_control_parity_and_weight_invariants() -> None:
    weights = pd.DataFrame(read_csv("monthly_weights.csv"))
    date_sets = {
        method: set(weights.loc[weights["method_id"] == method, "execution_date"])
        for method in exploratory.METHODS
    }

    assert len(set(map(tuple, (sorted(values) for values in date_sets.values())))) == 1
    for _, row in weights.iterrows():
        values = np.array([float(row[symbol]) for symbol in exploratory.FROZEN_SYMBOLS])
        assert np.isfinite(values).all()
        assert (values >= -1e-10).all()
        assert values.sum() == pytest.approx(1.0)


def test_cost_application_uses_gross_traded_notional() -> None:
    rows = read_csv("turnover_and_costs.csv")
    execution_rows = [row for row in rows if row["is_execution_date"] == "True"]

    assert execution_rows
    for row in execution_rows[:500]:
        bps = int(row["cost_bps_per_side"])
        expected = float(row["gross_traded_notional_pct"]) * bps / 10000.0
        assert float(row["transaction_cost_return"]) == pytest.approx(expected)
    assert all(float(row["transaction_cost_return"]) == 0.0 for row in execution_rows if int(row["cost_bps_per_side"]) == 0)


def test_cluster_and_concentration_diagnostics_exist() -> None:
    concentration = read_csv("concentration_diagnostics.csv")
    stability = read_csv("cluster_stability.csv")
    clusters_path = ARTIFACT_DIR / "monthly_clusters.jsonl"

    assert len(concentration) == 12
    assert stability
    assert clusters_path.exists()
    first_cluster = json.loads(clusters_path.read_text(encoding="utf-8").splitlines()[0])
    assert first_cluster["return_sample_observations"] == 252
    assert "linkage_result" in first_cluster
    assert "recursive_allocations" in first_cluster


def test_failure_registries_are_empty_but_schema_present() -> None:
    failures = read_csv("failure_registry.csv")
    rebalance_failures = read_csv("rebalance_failures.csv")

    assert failures == []
    assert rebalance_failures == []


def test_no_execution_connected_imports_in_exploratory_runner() -> None:
    tree = ast.parse(Path(exploratory.__file__).read_text(encoding="utf-8"))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)

    forbidden = {"alpaca", "broker", "brokers", "live", "paper", "demo"}
    assert not any(module.split(".")[0] in forbidden for module in imported)
