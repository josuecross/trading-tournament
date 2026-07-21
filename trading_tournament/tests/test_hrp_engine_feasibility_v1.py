from __future__ import annotations

import ast
import inspect
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src import hrp
from src.overlays import IdentityOverlay
from src.portfolio import Portfolio
from src.strategies import EntrySignal


def _covariance(values: list[list[float]], assets: tuple[str, ...] = ("A", "B", "C", "D")) -> pd.DataFrame:
    return pd.DataFrame(values, index=list(assets), columns=list(assets), dtype=float)


def _four_asset_returns() -> pd.DataFrame:
    dates = pd.bdate_range("2024-01-02", periods=252)
    x = np.arange(252, dtype=float)
    data = {
        "A": 0.001 + 0.0020 * np.sin(x / 9.0),
        "B": 0.0005 + 0.0015 * np.cos(x / 11.0),
        "C": 0.0002 + 0.0010 * np.sin(x / 7.0 + 0.3),
        "D": 0.0001 + 0.0025 * np.cos(x / 13.0 + 0.2),
    }
    return pd.DataFrame(data, index=dates)


def test_distance_formula_matches_source_rule() -> None:
    correlation = pd.DataFrame([[1.0, 0.5], [0.5, 1.0]], index=["A", "B"], columns=["A", "B"])

    distance = hrp.correlation_distance(correlation)

    assert distance.loc["A", "B"] == pytest.approx(np.sqrt((1.0 - 0.5) / 2.0))
    assert distance.loc["A", "A"] == 0.0


def test_deterministic_single_linkage_and_quasi_diagonalization() -> None:
    distance = pd.DataFrame(
        [
            [0.0, 0.1, 0.8, 0.8],
            [0.1, 0.0, 0.8, 0.8],
            [0.8, 0.8, 0.0, 0.1],
            [0.8, 0.8, 0.1, 0.0],
        ],
        index=["A", "B", "C", "D"],
        columns=["A", "B", "C", "D"],
    )

    first = hrp.single_linkage(distance)
    second = hrp.single_linkage(distance)

    assert first.equals(second)
    assert first.iloc[0].to_dict() == {"left": 0.0, "right": 1.0, "distance": 0.1, "sample_count": 2.0}
    assert first.iloc[1].to_dict() == {"left": 2.0, "right": 3.0, "distance": 0.1, "sample_count": 2.0}
    assert hrp.quasi_diagonalize(first, ("A", "B", "C", "D")) == ("A", "B", "C", "D")


def test_recursive_bisection_and_cluster_variance_are_inverse_variance_based() -> None:
    cov = _covariance(
        [
            [1.0, 0.0, 0.0, 0.0],
            [0.0, 4.0, 0.0, 0.0],
            [0.0, 0.0, 9.0, 0.0],
            [0.0, 0.0, 0.0, 16.0],
        ]
    )

    assert hrp.cluster_variance(cov, ("A", "B")) == pytest.approx(0.8)

    weights, variances, allocations = hrp.recursive_bisection(cov, ("A", "B", "C", "D"))

    assert len(variances) == 6
    assert allocations[0].left_variance == pytest.approx(0.8)
    assert allocations[0].right_variance == pytest.approx(5.76)
    assert weights.sum() == pytest.approx(1.0)
    assert (weights >= 0.0).all()
    assert weights.loc["A"] > weights.loc["B"] > weights.loc["C"] > weights.loc["D"]


def test_singular_covariance_supported_without_matrix_inversion() -> None:
    cov = _covariance(
        [
            [1.0, 1.0, 0.2, 0.2],
            [1.0, 1.0, 0.2, 0.2],
            [0.2, 0.2, 1.0, 0.9],
            [0.2, 0.2, 0.9, 1.0],
        ]
    )

    result = hrp.hrp_from_covariance(cov)

    assert np.isfinite(result.weights.to_numpy()).all()
    assert (result.weights >= 0.0).all()
    assert result.weights.sum() == pytest.approx(1.0)

    source = inspect.getsource(hrp)
    assert ".inv(" not in source
    assert "linalg" not in source


def test_zero_and_near_zero_variance_weights_remain_finite() -> None:
    cov = _covariance(
        [
            [0.0, 0.0, 0.0, 0.0],
            [0.0, 1e-16, 0.0, 0.0],
            [0.0, 0.0, 0.04, 0.0],
            [0.0, 0.0, 0.0, 0.09],
        ]
    )

    result = hrp.hrp_from_covariance(cov)

    assert np.isfinite(result.weights.to_numpy()).all()
    assert (result.weights >= 0.0).all()
    assert result.weights.sum() == pytest.approx(1.0)


def test_stable_tie_breaking_uses_frozen_instrument_order() -> None:
    correlation_values = np.full((4, 4), 0.5)
    np.fill_diagonal(correlation_values, 1.0)
    correlation = pd.DataFrame(correlation_values, index=["A", "B", "C", "D"], columns=["A", "B", "C", "D"])
    distance = hrp.correlation_distance(correlation)

    linkage = hrp.single_linkage(distance, ("A", "B", "C", "D"))

    assert hrp.quasi_diagonalize(linkage, ("A", "B", "C", "D")) == ("A", "B", "C", "D")
    assert list(linkage[["left", "right"]].itertuples(index=False, name=None)) == [(0, 1), (4, 2), (5, 3)]


def test_shuffled_input_is_reindexed_to_frozen_order_without_changing_result() -> None:
    returns = _four_asset_returns()

    expected = hrp.hrp_weights_from_returns(returns, ("A", "B", "C", "D"))
    shuffled = hrp.hrp_weights_from_returns(returns[["C", "A", "D", "B"]], ("A", "B", "C", "D"))

    pd.testing.assert_series_equal(expected.weights, shuffled.weights)
    assert expected.ordered_assets == shuffled.ordered_assets


def test_missing_data_fails_closed_and_assets_are_not_dropped() -> None:
    returns = _four_asset_returns()
    returns.iloc[5, 2] = np.nan

    with pytest.raises(hrp.HRPDataError, match="missing|nonfinite"):
        hrp.hrp_weights_from_returns(returns, ("A", "B", "C", "D"))

    with pytest.raises(hrp.HRPDataError, match="match the frozen instrument order"):
        hrp.hrp_weights_from_returns(returns[["A", "B", "C"]], ("A", "B", "C", "D"))


def test_expected_return_input_is_not_part_of_hrp_contract() -> None:
    returns = _four_asset_returns()

    with pytest.raises(TypeError):
        hrp.hrp_weights_from_returns(returns, ("A", "B", "C", "D"), expected_returns=pd.Series(dtype=float))


def test_252_day_target_weight_integration_and_identity_equivalence() -> None:
    assets = ("A", "B", "C", "D")
    returns = _four_asset_returns()
    signal_date = returns.index[-1]
    execution_date = signal_date + pd.offsets.BDay(1)
    prices = _price_data_from_returns(returns, execution_date)

    returns_window = hrp.daily_returns_window_from_price_data(prices, assets, signal_date, lookback=252)
    result = hrp.hrp_weights_from_returns(returns_window, assets)
    signals = [
        EntrySignal(
            date=signal_date,
            strategy=hrp.HRP_STRATEGY_ID,
            symbol=symbol,
            requested_risk=1.0,
            notes="one-date HRP target-weight fixture",
            metadata={"target_weight": float(result.weights.loc[symbol]), "atr": 1.0},
        )
        for symbol in assets
    ]
    portfolio = Portfolio(_hrp_accounting_config(assets), slippage_pct=0.0)
    identity = IdentityOverlay()
    identity.bind(
        run_id="hrp_identity_fixture",
        base_strategy_id=hrp.HRP_STRATEGY_ID,
        base_strategy_hash="synthetic_fixture",
        data=prices,
        indexed_data={symbol: frame.set_index("date", drop=False) for symbol, frame in prices.items()},
        calendar=list(prices["A"]["date"]),
        config=portfolio.config,
    )

    batch = identity.on_signal_batch(
        date=signal_date,
        entries=signals,
        exits=[],
        portfolio=portfolio,
        rows={},
        equity=portfolio.starting_equity,
        pending_exit_ids=set(),
    )

    assert batch.entries == signals
    assert batch.exits == []

    for signal in batch.entries:
        next_open = float(prices[signal.symbol].loc[prices[signal.symbol]["date"] == execution_date, "open"].iloc[0])
        position = portfolio.attempt_open_position(
            signal=signal,
            entry_date=execution_date,
            entry_price=next_open,
            stop_price=next_open - 1.0,
            target_price=None,
            project_equity=portfolio.starting_equity,
            strategy_pnl=0.0,
            market_regime="synthetic_non_performance_fixture",
            high_water_mark=portfolio.starting_equity,
            current_drawdown=0.0,
        )
        assert position is not None

    actual_weights = {position.symbol: position.shares * position.entry_price / portfolio.starting_equity for position in portfolio.positions}
    for symbol in assets:
        assert actual_weights[symbol] == pytest.approx(float(result.weights.loc[symbol]))
    assert sum(actual_weights.values()) + portfolio.cash / portfolio.starting_equity == pytest.approx(1.0)
    assert portfolio.cash >= -1e-7
    assert execution_date > signal_date


def test_no_execution_connected_imports_in_hrp_module() -> None:
    tree = ast.parse(Path(hrp.__file__).read_text(encoding="utf-8"))
    imported_modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.append(node.module)

    forbidden_roots = {"alpaca", "broker", "brokers", "live", "paper", "demo"}
    assert not any(module.split(".")[0] in forbidden_roots for module in imported_modules)


def _price_data_from_returns(returns: pd.DataFrame, execution_date: pd.Timestamp) -> dict[str, pd.DataFrame]:
    price_index = pd.Index([returns.index[0] - pd.offsets.BDay(1), *returns.index, execution_date])
    data: dict[str, pd.DataFrame] = {}
    for symbol in returns.columns:
        series = pd.Series(index=price_index, dtype=float)
        series.iloc[0] = 100.0
        for idx, date in enumerate(returns.index, start=1):
            series.loc[date] = series.iloc[idx - 1] * (1.0 + float(returns.loc[date, symbol]))
        series.loc[execution_date] = series.loc[returns.index[-1]] * 1.001
        frame = pd.DataFrame(
            {
                "date": price_index,
                "open": series.to_numpy(dtype=float),
                "high": series.to_numpy(dtype=float) * 1.01,
                "low": series.to_numpy(dtype=float) * 0.99,
                "close": series.to_numpy(dtype=float),
                "adj_close": series.to_numpy(dtype=float),
                "volume": [1000] * len(price_index),
                "symbol": symbol,
            }
        )
        data[symbol] = frame
    return data


def _hrp_accounting_config(assets: tuple[str, ...]) -> dict:
    return {
        "project": {
            "starting_equity": 100000.0,
            "hard_stop_equity": 0.0,
            "target_profit_1": 0.0,
            "target_profit_2": 0.0,
            "max_daily_loss": 100000.0,
            "max_weekly_loss": 100000.0,
            "max_open_risk": 100000.0,
            "max_cluster_open_risk": 100000.0,
            "max_position_notional_pct": 1.0,
            "reserve_cash_buffer": 0.0,
            "warmup_days": 0,
        },
        "universe": {"symbols": list(assets), "clusters": {"synthetic_multi_asset": list(assets)}},
        "strategy_order": [hrp.HRP_STRATEGY_ID],
        "strategies": {
            hrp.HRP_STRATEGY_ID: {
                "enabled": True,
                "allocation": 100000.0,
                "max_strategy_loss": 100000.0,
                "risk_per_trade": 1.0,
                "max_positions": len(assets),
                "initial_atr_multiple": 3.0,
            }
        },
        "benchmarks": {"spy": "A", "cash_proxy": "A", "initial_value": 100000.0},
    }
