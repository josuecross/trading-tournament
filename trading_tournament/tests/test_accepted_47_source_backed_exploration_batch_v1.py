from __future__ import annotations

import numpy as np
import pandas as pd

from strategy_lab.research_os.research import accepted_47_source_backed_exploration_batch_v1 as batch


def test_source_packet_reconciles_without_bypass() -> None:
    specs, reconciliation = batch.load_source_packet()
    assert reconciliation["pass"]
    assert len(specs) == 2
    assert len({spec.family_id for spec in specs}) == 2


def test_frozen_trial_ids_and_universes() -> None:
    specs, _ = batch.load_source_packet()
    by_id = {spec.strategy_id: spec for spec in specs}
    assert by_id[batch.CAA_ID].trial_id == batch.CAA_TRIAL
    assert by_id[batch.TPP_ID].trial_id == batch.TPP_TRIAL
    assert by_id[batch.CAA_ID].universe == batch.CAA_UNIVERSE
    assert by_id[batch.TPP_ID].universe == batch.TPP_UNIVERSE


def test_optimizer_equivalence_fixtures_pass() -> None:
    rows = batch.optimizer_equivalence_fixtures()
    assert len(rows) == 5
    assert all(row["fixture_pass"] for row in rows)


def test_two_asset_target_volatility_interpolation() -> None:
    weights, diagnostic = batch.efficient_target_weights(
        np.array([0.04, 0.08]),
        np.diag([0.01, 0.04]),
        np.ones(2),
        0.10,
        np.array([0.5, 0.5]),
    )
    assert np.allclose(weights, [0.6, 0.4], atol=1e-8, rtol=0.0)
    assert diagnostic["target_volatility_interpolated"]
    assert diagnostic["constraints_satisfied"]


def test_minimum_variance_fixture() -> None:
    weights, diagnostic = batch.minimum_variance_weights(
        np.diag([0.01, 0.04]), np.ones(2), np.array([0.5, 0.5])
    )
    assert np.allclose(weights, [0.8, 0.2], atol=1e-8, rtol=0.0)
    assert diagnostic["kkt_residual"] <= 1e-8


def test_caa_caps_and_repeatability() -> None:
    mu = np.linspace(0.01, 0.08, 8)
    covariance = np.diag(np.linspace(0.005, 0.04, 8))
    prior = np.full(8, 0.125)
    first, _ = batch.efficient_target_weights(mu, covariance, batch.CAA_CAPS, 0.10, prior)
    second, _ = batch.efficient_target_weights(mu, covariance, batch.CAA_CAPS, 0.10, prior)
    assert np.array_equal(first, second)
    assert np.isclose(first.sum(), 1.0)
    assert np.all(first <= batch.CAA_CAPS + 1e-8)
    assert np.all(first >= -1e-10)


def test_tpp_inverse_volatility_and_scaling() -> None:
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
    target, diagnostic = batch._tpp_weights(returns, 79, ["SPY", "IEF", "GLD"])
    assert np.isclose(sum(target.values()), 1.0)
    assert target["BIL"] >= 0.0
    assert 0.0 <= diagnostic["scale"] <= 1.0
    assert target["IEF"] > target["SPY"]


def test_tpp_no_selected_assets_holds_bil() -> None:
    returns = pd.DataFrame(0.0, index=pd.bdate_range("2024-01-01", periods=80), columns=batch.TPP_UNIVERSE)
    target, diagnostic = batch._tpp_weights(returns, 79, [])
    assert target == {"SPY": 0.0, "IEF": 0.0, "GLD": 0.0, "BIL": 1.0}
    assert diagnostic["scale"] == 0.0


def test_following_session_is_strictly_later() -> None:
    index = pd.DatetimeIndex(["2024-01-02", "2024-01-03", "2024-01-05"])
    assert batch.following_session(index, pd.Timestamp("2024-01-03")) == pd.Timestamp("2024-01-05")


def test_required_symbols_are_accepted_and_no_provider_dependency() -> None:
    assert set(batch.REQUIRED_SYMBOLS) <= batch.accepted_symbols()
    source = batch.Path(batch.__file__).read_text(encoding="utf-8").lower()
    assert "requests" not in source
    assert "submit_order" not in source


def test_turnover_formula_for_full_rotation() -> None:
    prior = np.array([1.0, 0.0])
    target = np.array([0.0, 1.0])
    assert np.isclose(0.5 * np.abs(target - prior).sum(), 1.0)
