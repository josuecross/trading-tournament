from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

import pandas as pd

from strategy_integrity_core import (
    STARTING_EQUITY,
    STRATEGY_SPECS,
    load_cached_close,
    monthly_rebalance_mask,
    normalize_with_bil,
    prepare_indicators,
    rank_assets,
)


ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = Path("evidence") / "implementation_integrity_audit" / "latest"


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def add(weights: dict[str, float], symbol: str, amount: float) -> None:
    weights[symbol] = weights.get(symbol, 0.0) + amount


def symbols_available(indicators: dict[str, Any], symbols: list[str]) -> list[str]:
    return [symbol for symbol in symbols if symbol in indicators["close"].columns]


def weights_for_strategy(strategy_id: str, indicators: dict[str, Any], date: pd.Timestamp) -> tuple[dict[str, float], str, list[tuple[str, float]], list[str]]:
    weights: dict[str, float] = {}
    warnings: list[str] = []
    spec = STRATEGY_SPECS[strategy_id]

    if strategy_id == "gtaa_top3_trend_filter_v1":
        assets = symbols_available(indicators, ["SPY", "QQQ", "EFA", "EEM", "IWM", "GLD", "IEF"])
        ranks = rank_assets(indicators, date, assets)[:3]
        for symbol, _ in ranks:
            add(weights, symbol, 1 / 3)
        reason = "top3 above 200d SMA by 126d return"
    elif strategy_id == "dm_paa_breadth_protection_v1":
        risky = symbols_available(indicators, ["SPY", "QQQ", "EFA", "EEM", "IWM"])
        positives = [symbol for symbol, _ in rank_assets(indicators, date, risky, require_positive_return=True)]
        if len(positives) < 2:
            ranks = rank_assets(indicators, date, symbols_available(indicators, ["GLD", "IEF"]), require_positive_return=True)[:1]
            add(weights, ranks[0][0] if ranks else "BIL", 0.5)
            add(weights, "BIL", 0.5)
            reason = "PAA breadth defensive branch"
        else:
            ranks = rank_assets(indicators, date, symbols_available(indicators, ["SPY", "QQQ", "EFA", "EEM", "IWM", "GLD", "IEF"]), risk_adjusted=True, require_positive_return=True)[:2]
            for symbol, _ in ranks:
                add(weights, symbol, 0.5)
            reason = "PAA positive breadth top2 risk-adjusted branch"
    elif strategy_id == "mf_wrapper_top1_trend_v1":
        wrappers = symbols_available(indicators, ["DBMF", "KMLM", "CTA", "FMF", "WTMF"])
        ranks = rank_assets(indicators, date, wrappers)[:1]
        add(weights, ranks[0][0] if ranks else "BIL", 1.0)
        reason = "top managed-futures wrapper above 200d SMA by 126d return"
        if len(wrappers) < 2:
            warnings.append("short wrapper availability")
    elif strategy_id == "gror_balanced_momentum_60_40_v1":
        risk_ranks = rank_assets(indicators, date, symbols_available(indicators, ["SPY", "QQQ"]))
        defensive_ranks = rank_assets(indicators, date, symbols_available(indicators, ["GLD", "IEF"]))
        ranks = risk_ranks + defensive_ranks
        spy_above = bool("SPY" in indicators["above200"].columns and indicators["above200"].at[date, "SPY"])
        if spy_above and risk_ranks:
            add(weights, risk_ranks[0][0], 0.6)
        else:
            add(weights, "BIL", 0.6)
        if defensive_ranks:
            add(weights, defensive_ranks[0][0], 0.4)
        else:
            add(weights, "BIL", 0.4)
        reason = "GROR 60/40 risk-on plus defensive branch"
    else:
        ranks = []
        add(weights, "BIL", 1.0)
        reason = f"trace fallback for unsupported strategy type {spec.rule_type}"
        warnings.append("unsupported trace strategy")
    return normalize_with_bil(weights), reason, ranks, warnings


def trace_strategy(root: Path, strategy_id: str, limit: int) -> dict[str, Any]:
    if strategy_id not in STRATEGY_SPECS:
        raise ValueError(f"unknown strategy: {strategy_id}")
    spec = STRATEGY_SPECS[strategy_id]
    symbols = list(dict.fromkeys([*spec.universe, "BIL"]))
    close = load_cached_close(root, symbols)
    if close.empty or len(close) < 260:
        raise RuntimeError(f"insufficient cached adjusted data for {strategy_id}: {symbols}")
    indicators = prepare_indicators(close)
    rebalances = monthly_rebalance_mask(close.index)
    rows: list[dict[str, Any]] = []
    equity = STARTING_EQUITY
    prior_weights: dict[str, float] = {}
    for idx, date in enumerate(close.index):
        if idx < 252 or not bool(rebalances.loc[date]):
            continue
        signal_date = close.index[idx - 1]
        weights, reason, ranks, warnings = weights_for_strategy(strategy_id, indicators, signal_date)
        available_assets = [symbol for symbol in spec.universe if symbol in close.columns]
        eligible_assets = [symbol for symbol in available_assets if symbol != "BIL" and bool(indicators["above200"].at[signal_date, symbol])]
        turnover = sum(abs(weights.get(symbol, 0.0) - prior_weights.get(symbol, 0.0)) for symbol in set(weights) | set(prior_weights))
        row = {
            "rebalance_date": str(date.date()),
            "available_assets": ";".join(available_assets),
            "eligible_assets": ";".join(eligible_assets),
            "ranks": json.dumps({symbol: score for symbol, score in ranks}, sort_keys=True),
            "selected_assets": ";".join(symbol for symbol, weight in weights.items() if symbol != "BIL" and weight > 0),
            "weights": json.dumps(weights, sort_keys=True),
            "BIL_weight": weights.get("BIL", 0.0),
            "reason": reason,
            "signal_values": json.dumps(
                {
                    symbol: {
                        "above_200d": bool(indicators["above200"].at[signal_date, symbol]) if symbol in close else False,
                        "ret126": None if symbol not in close or pd.isna(indicators["ret126"].at[signal_date, symbol]) else float(indicators["ret126"].at[signal_date, symbol]),
                    }
                    for symbol in available_assets
                    if symbol in close.columns
                },
                sort_keys=True,
            ),
            "warnings": ";".join(warnings),
            "rebalance": True,
            "signal_date": str(signal_date.date()),
            "portfolio_equity_before": equity,
            "portfolio_equity_after": equity,
            "turnover": turnover,
        }
        rows.append(row)
        prior_weights = weights
        if len(rows) >= limit:
            break
    output_dir = root / OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"rule_trace_{strategy_id}.csv"
    write_csv(
        path,
        rows,
        [
            "rebalance_date",
            "available_assets",
            "eligible_assets",
            "ranks",
            "selected_assets",
            "weights",
            "BIL_weight",
            "reason",
            "signal_values",
            "warnings",
            "rebalance",
            "signal_date",
            "portfolio_equity_before",
            "portfolio_equity_after",
            "turnover",
        ],
    )
    return {"strategy_id": strategy_id, "output_path": str(path), "row_count": len(rows)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Write diagnostic-only strategy rule traces from cached adjusted ETF data.")
    parser.add_argument("--strategy", required=True)
    parser.add_argument("--limit", type=int, default=12)
    args = parser.parse_args()
    result = trace_strategy(ROOT, args.strategy, args.limit)
    print(f"strategy={result['strategy_id']}")
    print(f"trace_path={result['output_path']}")
    print(f"row_count={result['row_count']}")
    print("research_run=false")
    print("provider_api_called=false")
    print("data_downloaded=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
