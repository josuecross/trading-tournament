from __future__ import annotations

import json
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from exploratory.crypto_spot_momentum.crypto_data import normalize_ohlcv
from exploratory.crypto_spot_momentum.crypto_metrics import target_and_stop_state
from exploratory.crypto_spot_momentum.crypto_reporting import write_evidence_packet
from exploratory.crypto_spot_momentum.crypto_strategies import generate_weights, simulate_strategy
from exploratory.crypto_spot_momentum.crypto_validation import sample_start_indices


def synthetic_crypto_data(days: int = 260) -> pd.DataFrame:
    dates = pd.date_range("2020-01-01", periods=days, freq="D")
    btc = 100 * (1.004 ** np.arange(days))
    eth = 120 * (0.998 ** np.arange(days))
    rows = []
    for symbol, values in {"BTC-USD": btc, "ETH-USD": eth}.items():
        for date, close in zip(dates, values):
            rows.append(
                {
                    "date": date,
                    "open": close * 0.99,
                    "high": close * 1.01,
                    "low": close * 0.98,
                    "close": close,
                    "adj_close": close,
                    "volume": 1000,
                    "symbol": symbol,
                    "source": "synthetic",
                }
            )
    return pd.DataFrame(rows)


def minimal_config() -> dict:
    return {
        "project": {
            "starting_equity": 3000,
            "target_300_equity": 3300,
            "target_400_equity": 3400,
            "project_stop_equity": 2400,
            "trailing_drawdown_dollars": 600,
            "project_stop_mode": "both",
        },
        "costs": {
            "standard_fee_slippage_per_side": 0.001,
            "stress_fee_slippage_per_side": 0.003,
            "notes": "test",
        },
        "strategies": {
            "enabled": ["crypto_time_series_momentum"],
            "crypto_time_series_momentum": {
                "role": "exploratory_strategy",
                "trend_sma_days": 200,
                "momentum_lookback_days": 90,
                "rebalance_frequency": "weekly",
            },
            "crypto_buy_hold_equal_weight": {
                "role": "benchmark",
                "rebalance_frequency": "monthly",
                "assets": ["BTC-USD", "ETH-USD"],
            },
        },
        "benchmarks": ["crypto_buy_hold_equal_weight", "cash_flat", "BTC_buy_hold", "ETH_buy_hold"],
    }


def test_data_normalization_with_synthetic_ohlcv() -> None:
    raw = pd.DataFrame(
        {
            "Date": pd.date_range("2024-01-01", periods=2),
            "Open": [1, 2],
            "High": [2, 3],
            "Low": [0.5, 1.5],
            "Close": [1.5, 2.5],
            "Volume": [10, 20],
        }
    )
    normalized = normalize_ohlcv(raw, "BTC-USD", "synthetic")
    assert list(normalized.columns) == ["date", "open", "high", "low", "close", "adj_close", "volume", "symbol", "source"]
    assert normalized["adj_close"].tolist() == normalized["close"].tolist()
    assert normalized["symbol"].unique().tolist() == ["BTC-USD"]


def test_sma200_and_90_day_momentum_eligibility_and_cash_when_none() -> None:
    data = synthetic_crypto_data()
    cfg = {"trend_sma_days": 200, "momentum_lookback_days": 90, "rebalance_frequency": "weekly"}
    weights = generate_weights(data, "crypto_time_series_momentum", cfg)
    last = weights.iloc[-1]
    assert last["BTC-USD"] > 0
    assert last["ETH-USD"] == 0

    declining = data.copy()
    declining.loc[declining["symbol"] == "BTC-USD", "adj_close"] = np.linspace(100, 50, len(declining) // 2)
    declining.loc[declining["symbol"] == "BTC-USD", "close"] = np.linspace(100, 50, len(declining) // 2)
    weights_declining = generate_weights(declining, "crypto_time_series_momentum", cfg)
    assert weights_declining.iloc[-1].sum() == 0


def test_no_leverage_weights_sum_to_one_or_less() -> None:
    data = synthetic_crypto_data()
    cfg = {"momentum_lookback_days": 90, "rebalance_frequency": "weekly", "top_n": 1}
    weights = generate_weights(data, "crypto_cross_sectional_momentum", cfg)
    assert (weights.sum(axis=1) <= 1.0 + 1e-12).all()
    assert (weights >= 0).all().all()


def test_buy_hold_equal_weight_behavior() -> None:
    data = synthetic_crypto_data()
    cfg = {"rebalance_frequency": "monthly", "assets": ["BTC-USD", "ETH-USD"]}
    weights = generate_weights(data, "crypto_buy_hold_equal_weight", cfg)
    invested = weights[weights.sum(axis=1) > 0].iloc[-1]
    assert abs(invested["BTC-USD"] - 0.5) < 1e-12
    assert abs(invested["ETH-USD"] - 0.5) < 1e-12


def test_cost_application_reduces_equity_when_rebalancing() -> None:
    data = synthetic_crypto_data()
    cfg = {"rebalance_frequency": "monthly", "assets": ["BTC-USD", "ETH-USD"]}
    no_cost = simulate_strategy(data, "crypto_buy_hold_equal_weight", cfg, 3000, 0.0)
    with_cost = simulate_strategy(data, "crypto_buy_hold_equal_weight", cfg, 3000, 0.01)
    assert with_cost.equity_curve["equity"].iloc[-1] < no_cost.equity_curve["equity"].iloc[-1]


def test_target_before_stop_and_trailing_stop_logic() -> None:
    dates = pd.date_range("2024-01-01", periods=5)
    curve = pd.DataFrame({"date": dates, "equity": [3000, 3320, 3500, 2800, 2400]})
    state = target_and_stop_state(curve, minimal_config()["project"])
    assert state["target_300_hit"] is True
    assert state["target_300_before_stop"] is True
    assert state["target_400_hit"] is True
    assert state["trailing_drawdown_stop_hit"] is True
    assert state["any_project_stop_hit"] is True

    curve2 = pd.DataFrame({"date": dates, "equity": [3000, 2500, 2400, 3400, 3500]})
    state2 = target_and_stop_state(curve2, minimal_config()["project"])
    assert state2["target_400_hit"] is True
    assert state2["target_400_before_stop"] is False


def test_rolling_sample_labels_are_non_final() -> None:
    data = synthetic_crypto_data(320)
    starts, possible = sample_start_indices(data, horizon=90, method="deterministic_sample", sample_size=12)
    assert len(starts) <= 12
    assert possible > len(starts)


def test_evidence_packet_excludes_raw_ohlcv_and_manifest_has_tier_labels(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    cfg = minimal_config()
    strategy_results = pd.DataFrame(
        [
            {
                "strategy": "crypto_time_series_momentum",
                "slippage_label": "standard",
                "final_equity": 3100,
                "target_300_hit": False,
                "target_300_first_date": "",
                "target_300_before_stop": False,
                "target_400_hit": False,
                "target_400_first_date": "",
                "target_400_before_stop": False,
                "any_project_stop_hit": False,
                "first_project_stop_date": "",
                "max_drawdown_dollars": -50,
                "max_drawdown_pct": -0.02,
            }
        ]
    )
    benchmark_results = strategy_results.assign(strategy="BTC_buy_hold")
    empty = pd.DataFrame()
    run_dir, latest_dir = write_evidence_packet(
        run_id="test_run",
        config=cfg,
        mode="smoke",
        source="synthetic",
        network_download_occurred=False,
        data_coverage=pd.DataFrame([{"symbol": "BTC-USD", "row_count": 2}]),
        warnings=["synthetic warning"],
        strategy_results=strategy_results,
        benchmark_results=benchmark_results,
        rolling_results=empty,
        rolling_summary=empty,
        equity_curves={},
        config_path=Path("config.yaml"),
    )
    manifest = json.loads((latest_dir / "exploratory_manifest.json").read_text())
    assert manifest["credibility_tier"] == "Tier 1 exploratory screen"
    assert manifest["final_validation"] is False
    assert manifest["candidate_validation"] is False
    assert manifest["paper_forward_ready"] is False
    assert manifest["real_money_recommendation"] is False
    names = [p.name for p in latest_dir.iterdir()]
    assert not any("ohlcv" in name.lower() for name in names)
    with zipfile.ZipFile(run_dir / "crypto_spot_momentum_exploratory_packet.zip") as zf:
        zipped = zf.namelist()
    assert not any("ohlcv" in name.lower() or "cache" in name.lower() for name in zipped)


def test_no_broker_or_trading_functionality_exists() -> None:
    code_dir = Path("exploratory/crypto_spot_momentum")
    python_text = "\n".join(path.read_text(encoding="utf-8") for path in code_dir.glob("*.py"))
    forbidden = ["create_order", "place_order", "submit_order", "margin", "perpetual", "futures"]
    lowered = python_text.lower()
    assert not any(term in lowered for term in forbidden)
