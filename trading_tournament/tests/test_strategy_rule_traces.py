from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

import run_strategy_rule_trace as trace


def write_cache(root: Path, symbol: str, periods: int = 340, drift: float = 0.001) -> None:
    dates = pd.bdate_range("2024-01-01", periods=periods)
    price = 100.0
    rows = []
    for date in dates:
        price *= 1.0 + drift
        rows.append({"date": date.date().isoformat(), "adj_close": price, "open": price, "high": price, "low": price, "close": price})
    path = root / "data" / "cache" / f"{symbol}.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)


def test_trace_writes_diagnostic_rows_without_research_run(tmp_path: Path) -> None:
    for symbol, drift in [("SPY", 0.001), ("QQQ", 0.0012), ("EFA", 0.0006), ("EEM", 0.0004), ("IWM", 0.0005), ("GLD", 0.0003), ("IEF", 0.0002), ("BIL", 0.00001)]:
        write_cache(tmp_path, symbol, drift=drift)
    result = trace.trace_strategy(tmp_path, "gtaa_top3_trend_filter_v1", 3)
    path = Path(result["output_path"])
    rows = pd.read_csv(path)
    assert result["row_count"] == 3
    assert "weights" in rows.columns
    for payload in rows["weights"]:
        weights = json.loads(payload)
        assert abs(sum(weights.values()) - 1.0) < 1e-9
    assert set(rows["rebalance"].unique()) == {True}


def test_trace_bil_fallback_when_no_assets_qualify(tmp_path: Path) -> None:
    for symbol in ["SPY", "QQQ", "EFA", "EEM", "IWM", "GLD", "IEF", "BIL"]:
        write_cache(tmp_path, symbol, drift=-0.001 if symbol != "BIL" else 0.00001)
    result = trace.trace_strategy(tmp_path, "gtaa_top3_trend_filter_v1", 1)
    rows = pd.read_csv(result["output_path"])
    assert float(rows.iloc[0]["BIL_weight"]) == 1.0


def test_trace_supports_requested_strategy_ids(tmp_path: Path) -> None:
    for symbol in ["SPY", "QQQ", "EFA", "EEM", "IWM", "GLD", "IEF", "BIL", "DBMF", "KMLM", "CTA"]:
        write_cache(tmp_path, symbol, drift=0.0007 if symbol != "BIL" else 0.00001)
    for strategy_id in [
        "gtaa_top3_trend_filter_v1",
        "dm_paa_breadth_protection_v1",
        "mf_wrapper_top1_trend_v1",
        "gror_balanced_momentum_60_40_v1",
    ]:
        result = trace.trace_strategy(tmp_path, strategy_id, 2)
        assert Path(result["output_path"]).exists()
        assert result["row_count"] == 2
