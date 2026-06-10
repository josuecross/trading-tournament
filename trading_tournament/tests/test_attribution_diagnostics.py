from __future__ import annotations

from pathlib import Path

import pandas as pd

from research_diagnostics import attribution_diagnostics as diag


ROOT = Path(__file__).resolve().parents[1]


def synthetic_windows() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "experiment_id": "candidate",
                "horizon": 30,
                "cost_mode": "standard",
                "window_start": "2024-01-02",
                "window_end": "2024-02-14",
                "target_300_hit": True,
                "target_400_hit": False,
                "target_600_hit": False,
                "target_900_hit": False,
                "target_1200_hit": False,
                "benchmark_combo_target_300_hit": False,
                "benchmark_combo_target_400_hit": False,
                "benchmark_top2_target_300_hit": True,
                "benchmark_top2_target_400_hit": False,
                "worst_drawdown": -150.0,
                "stop_hit": False,
            },
            {
                "experiment_id": "candidate",
                "horizon": 30,
                "cost_mode": "standard",
                "window_start": "2024-03-01",
                "window_end": "2024-04-12",
                "target_300_hit": True,
                "target_400_hit": True,
                "target_600_hit": False,
                "target_900_hit": False,
                "target_1200_hit": False,
                "benchmark_combo_target_300_hit": True,
                "benchmark_combo_target_400_hit": True,
                "benchmark_top2_target_300_hit": True,
                "benchmark_top2_target_400_hit": True,
                "worst_drawdown": -300.0,
                "stop_hit": False,
            },
        ]
    )


def synthetic_component_returns() -> pd.DataFrame:
    index = pd.date_range("2024-01-02", periods=6, freq="B")
    return pd.DataFrame(
        {
            "sleeve_a": [0.0, 0.10, -0.20, 0.10, 0.05, 0.05],
            "sleeve_b": [0.0, 0.00, -0.05, 0.02, 0.03, 0.01],
        },
        index=index,
    )


def test_target_window_attribution_detects_incremental_target_hits() -> None:
    result = diag.compute_target_window_attribution(synthetic_windows(), experiment_id="candidate")
    first = result.iloc[0]
    assert bool(first["incremental_300_vs_combo"]) is True
    assert bool(first["incremental_300_vs_top2"]) is False
    assert bool(first["incremental_400_vs_combo"]) is False


def test_target_window_attribution_detects_no_incremental_hits() -> None:
    result = diag.compute_target_window_attribution(synthetic_windows(), experiment_id="candidate")
    second = result.iloc[1]
    assert bool(second["incremental_300_vs_combo"]) is False
    assert bool(second["incremental_400_vs_combo"]) is False
    assert bool(second["incremental_300_vs_top2"]) is False
    assert bool(second["incremental_400_vs_top2"]) is False


def test_component_contribution_sums_correctly_for_synthetic_returns() -> None:
    returns = synthetic_component_returns()
    weights = {"sleeve_a": 0.60, "sleeve_b": 0.40}
    result = diag.compute_component_contribution(
        returns,
        weights,
        experiment_id="combo_test",
        starting_equity=3000.0,
    )
    assert set(result["component_id"]) == {"sleeve_a", "sleeve_b"}
    contribution_sum = result["component_final_equity_contribution"].sum()
    equity, _contributions, _weights = diag._equity_from_component_returns(returns, weights, 3000.0)
    assert round(contribution_sum, 8) == round(float(equity.iloc[-1] - 3000.0), 8)


def test_drawdown_attribution_identifies_worst_drawdown_window() -> None:
    result = diag.compute_drawdown_attribution(
        synthetic_component_returns(),
        {"sleeve_a": 0.60, "sleeve_b": 0.40},
        experiment_id="combo_test",
        starting_equity=3000.0,
    )
    assert set(result["component_id"]) == {"sleeve_a", "sleeve_b"}
    assert result["worst_drawdown"].iloc[0] < 0
    assert result["worst_drawdown_start"].iloc[0] <= result["worst_drawdown_end"].iloc[0]
    assert result["drawdown_overlap_status"].eq("available").all()


def test_recovery_attribution_identifies_recovery_periods() -> None:
    returns = pd.DataFrame(
        {"sleeve_a": [0.0, 0.10, -0.20, 0.25, 0.02], "sleeve_b": [0.0, 0.0, -0.05, 0.05, 0.02]},
        index=pd.date_range("2024-01-02", periods=5, freq="B"),
    )
    result = diag.compute_recovery_attribution(
        returns,
        {"sleeve_a": 0.70, "sleeve_b": 0.30},
        experiment_id="combo_test",
        starting_equity=3000.0,
    )
    assert set(result["component_id"]) == {"sleeve_a", "sleeve_b"}
    assert result["recovery_start"].iloc[0] != ""
    assert result["recovery_end"].iloc[0] != ""
    assert pd.to_datetime(result["recovery_start"].iloc[0]) <= pd.to_datetime(result["recovery_end"].iloc[0])


def test_worst_n_drawdown_extraction_ranks_correctly() -> None:
    result = diag.extract_worst_n_drawdown_windows(synthetic_windows(), n=2, experiment_id="candidate")
    assert result["rank"].tolist() == [1, 2]
    assert result["worst_drawdown"].tolist() == [-300.0, -150.0]


def test_missing_optional_fields_return_unavailable_status() -> None:
    result = diag.compute_component_contribution(None, None, experiment_id="missing")
    assert result["contribution_status"].iloc[0] == "unavailable_missing_component_returns"
    target_result = diag.compute_target_window_attribution(pd.DataFrame({"experiment_id": ["missing"]}), experiment_id="missing")
    assert target_result["contribution_status"].iloc[0] == "unavailable_missing_target_flags"


def test_drawdown_coincidence_detail_is_deterministic() -> None:
    index = pd.date_range("2024-01-02", periods=5, freq="B")
    candidate = pd.Series([3000, 3100, 2800, 2850, 3200], index=index)
    benchmark = pd.Series([3000, 3050, 2750, 2800, 3100], index=index)
    first = diag.compute_drawdown_coincidence_detail(candidate, {"benchmark": benchmark}, experiment_id="candidate")
    second = diag.compute_drawdown_coincidence_detail(candidate, {"benchmark": benchmark}, experiment_id="candidate")
    pd.testing.assert_frame_equal(first, second)
    assert first["drawdown_overlap_status"].iloc[0] == "available"


def test_module_does_not_import_yfinance_or_broker_terms() -> None:
    source = (ROOT / "research_diagnostics" / "attribution_diagnostics.py").read_text(encoding="utf-8")
    forbidden = ["yfinance", "download(", "broker", "live_orders", "order_placement"]
    for token in forbidden:
        assert token not in source
