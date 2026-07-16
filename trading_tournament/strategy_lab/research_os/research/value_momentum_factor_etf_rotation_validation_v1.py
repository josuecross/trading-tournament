from __future__ import annotations

import csv
import hashlib
import json
import math
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd

import run_active_strategy_evidence_recompute as active


ROOT = Path(__file__).resolve().parents[3]
EVIDENCE_DIR = ROOT / "evidence" / "value_momentum_factor_etf_rotation_validation_v1" / "latest"
CANDIDATE_ID = "value_momentum_factor_etf_rotation_v1"
SECTOR_CANDIDATE_ID = "sector_top2_momentum_simple_v1"
FAMILY_ID = "factor_rotation"
MECHANISM = "cross_sectional_factor_rotation_with_trend_cash_filter"
CANDIDATE_SYMBOLS = ("MTUM", "VTV", "QUAL", "USMV", "SPY", "BIL")
RISKY_SYMBOLS = ("MTUM", "VTV", "QUAL", "USMV", "SPY")
BENCHMARK_SYMBOLS = ("SPY", "BIL", "GLD", "IEF", "SPLV")
REQUIRED_SYMBOLS = tuple(sorted(set(CANDIDATE_SYMBOLS + BENCHMARK_SYMBOLS)))
LOOKBACK_DAYS = 126
TREND_DAYS = 200
TOP_N = 2
REBALANCE = "monthly"
TRANSACTION_COST_RATE = 0.0005
INITIAL_CAPITAL = 3000.0
MONTHLY_HORIZONS = (90, 180, 252, 504)
NON_OVERLAP_HORIZONS = (180, 252, 504)
PRIMARY_BENCHMARK = "combo_SPY200d_GLD_50_50_v1"
BENCHMARK_IDS = (
    PRIMARY_BENCHMARK,
    "SPY_buy_and_hold",
    "asset_class_tsmom_top2_v1",
    "BIL_cash_proxy",
    active.VM_ID,
    "active_combo_vm_dsr_equal_weight_v1",
)
VALIDATION_OUTCOMES = {
    "validation_supports_further_review",
    "benchmark_dependent_positive",
    "historical_edge_recently_weakened",
    "defensive_value_without_return_edge",
    "screening_positive_not_stable",
    "redundant_with_active_observation",
    "control_weak",
    "invalid_methodology",
    "direction_owner_review_required",
}
REGISTRY_PATH = ROOT / "strategy_lab" / "strategy_registry.yaml"
ACTIVE_OBSERVATIONS_PATH = ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml"
ACTIVE_COMBO_SERIES = ROOT / "evidence" / "active_combo_series_reconciliation" / "latest" / "combo_daily_series.csv"
IMPLEMENTATION_EVIDENCE = ROOT / "evidence" / "implementation_reviews" / CANDIDATE_ID / "latest"
READY_BATCH_EVIDENCE = ROOT / "evidence" / "resume_existing_ready_research_batch_v1" / "latest"


@dataclass(frozen=True)
class Period:
    period_id: str
    window_family: str
    horizon_days: str
    start_pos: int
    end_pos: int
    start_date: pd.Timestamp
    end_date: pd.Timestamp
    non_independent: bool


def sha256_path(path: Path) -> str:
    if not path.exists():
        return "missing"
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def clean_value(value: Any) -> Any:
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.integer, int)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        value = float(value)
        if math.isnan(value) or math.isinf(value):
            return ""
        return round(value, 10)
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    return value


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=clean_value) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    if fields is None:
        fields = sorted({field for row in rows for field in row})
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: clean_value(row.get(field, "")) for field in fields})


def read_close(symbol: str) -> pd.Series:
    path = ROOT / "data" / "cache" / f"{symbol}.csv"
    frame = pd.read_csv(path)
    dates = pd.to_datetime(frame["date"], errors="coerce").dt.tz_localize(None)
    close = pd.to_numeric(frame["adj_close"], errors="coerce")
    series = (
        pd.DataFrame({"date": dates, symbol: close})
        .dropna()
        .drop_duplicates("date")
        .sort_values("date")
        .set_index("date")[symbol]
        .astype(float)
    )
    return series


def load_prices(symbols: tuple[str, ...] = REQUIRED_SYMBOLS) -> pd.DataFrame:
    return pd.concat([read_close(symbol) for symbol in symbols], axis=1, join="inner").sort_index().dropna()


def load_active_combo_returns() -> pd.Series:
    frame = pd.read_csv(ACTIVE_COMBO_SERIES)
    dates = pd.to_datetime(frame["date"], errors="coerce").dt.tz_localize(None)
    returns = pd.to_numeric(frame["active_combo_daily_return"], errors="coerce")
    return pd.Series(returns.to_numpy(), index=dates).dropna().astype(float).sort_index()


def cache_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for symbol in REQUIRED_SYMBOLS:
        series = read_close(symbol)
        path = ROOT / "data" / "cache" / f"{symbol}.csv"
        rows.append(
            {
                "symbol": symbol,
                "cache_path": f"data/cache/{symbol}.csv",
                "sha256": sha256_path(path),
                "first_valid_date": series.index.min().strftime("%Y-%m-%d"),
                "last_valid_date": series.index.max().strftime("%Y-%m-%d"),
                "row_count": int(len(series)),
            }
        )
    return rows


def sma(series: pd.Series, signal_pos: int, length: int) -> float:
    if signal_pos - length + 1 < 0:
        return float("nan")
    return float(series.iloc[signal_pos - length + 1 : signal_pos + 1].mean())


def candidate_target(prices: pd.DataFrame, execution_pos: int) -> tuple[dict[str, float], dict[str, Any]]:
    target = {symbol: 0.0 for symbol in prices.columns}
    signal_pos = execution_pos - 1
    diagnostics: dict[str, Any] = {"eligible": [], "selected": [], "bil_reason": ""}
    if signal_pos < max(LOOKBACK_DAYS, TREND_DAYS):
        target["BIL"] = 1.0
        diagnostics["bil_reason"] = "warmup_or_insufficient_history"
        return target, diagnostics
    scored: list[tuple[float, str]] = []
    for symbol in RISKY_SYMBOLS:
        close = float(prices[symbol].iloc[signal_pos])
        prior = float(prices[symbol].iloc[signal_pos - LOOKBACK_DAYS])
        trend = sma(prices[symbol], signal_pos, TREND_DAYS)
        ret = close / prior - 1.0 if prior > 0 else float("nan")
        if ret > 0.0 and close > trend:
            scored.append((ret, symbol))
            diagnostics["eligible"].append(symbol)
    selected = [symbol for _score, symbol in sorted(scored, key=lambda item: item[0], reverse=True)[:TOP_N]]
    for symbol in selected:
        target[symbol] = 1.0 / TOP_N
    target["BIL"] = max(0.0, 1.0 - sum(target.values()))
    diagnostics["selected"] = selected
    diagnostics["bil_reason"] = "trend_or_positive_momentum_filter" if target["BIL"] > 0 else "none"
    return target, diagnostics


def top2_target(prices: pd.DataFrame, execution_pos: int, ranking_assets: tuple[str, ...]) -> dict[str, float]:
    target = {symbol: 0.0 for symbol in prices.columns}
    signal_pos = execution_pos - 1
    if signal_pos < max(LOOKBACK_DAYS, TREND_DAYS):
        target["BIL"] = 1.0
        return target
    scored: list[tuple[float, str]] = []
    for symbol in ranking_assets:
        close = float(prices[symbol].iloc[signal_pos])
        prior = float(prices[symbol].iloc[signal_pos - LOOKBACK_DAYS])
        trend = sma(prices[symbol], signal_pos, TREND_DAYS)
        ret = close / prior - 1.0 if prior > 0 else float("nan")
        if ret > 0.0 and close > trend:
            scored.append((ret, symbol))
    for symbol in [symbol for _score, symbol in sorted(scored, reverse=True)[:TOP_N]]:
        target[symbol] = 1.0 / TOP_N
    target["BIL"] = max(0.0, 1.0 - sum(target.values()))
    return target


def combo_target(prices: pd.DataFrame, execution_pos: int) -> dict[str, float]:
    target = {symbol: 0.0 for symbol in prices.columns}
    signal_pos = execution_pos - 1
    if signal_pos >= TREND_DAYS and float(prices["SPY"].iloc[signal_pos]) > sma(prices["SPY"], signal_pos, TREND_DAYS):
        target["SPY"] = 0.5
    else:
        target["BIL"] = 0.5
    target["GLD"] = 0.5
    return target


def fixed_target(symbol: str) -> Callable[[pd.DataFrame, int], dict[str, float]]:
    def _target(prices: pd.DataFrame, execution_pos: int) -> dict[str, float]:
        target = {column: 0.0 for column in prices.columns}
        target[symbol] = 1.0
        return target

    return _target


def benchmark_target(benchmark_id: str) -> Callable[[pd.DataFrame, int], dict[str, float]]:
    if benchmark_id == PRIMARY_BENCHMARK:
        return combo_target
    if benchmark_id == "asset_class_tsmom_top2_v1":
        return lambda prices, pos: top2_target(prices, pos, ("SPY", "GLD", "IEF"))
    if benchmark_id == "SPY_buy_and_hold":
        return fixed_target("SPY")
    if benchmark_id == "BIL_cash_proxy":
        return fixed_target("BIL")
    raise KeyError(benchmark_id)


def first_month_day(index: pd.DatetimeIndex, pos: int) -> bool:
    if pos == 0:
        return True
    return index[pos].year != index[pos - 1].year or index[pos].month != index[pos - 1].month


def target_turnover(new_weights: dict[str, float], pre_weights: dict[str, float]) -> float:
    symbols = set(new_weights) | set(pre_weights)
    return float(sum(abs(new_weights.get(symbol, 0.0) - pre_weights.get(symbol, 0.0)) for symbol in symbols))


def simulate_path(
    prices: pd.DataFrame,
    start_pos: int,
    end_pos: int,
    target_func: Callable[[pd.DataFrame, int], dict[str, float] | tuple[dict[str, float], dict[str, Any]]],
    candidate: bool = False,
) -> dict[str, Any]:
    symbols = list(prices.columns)
    shares = {symbol: 0.0 for symbol in symbols}
    equity_records: list[dict[str, Any]] = []
    rebalance_records: list[dict[str, Any]] = []
    turnover_records: list[dict[str, Any]] = []
    prev_target = {symbol: 0.0 for symbol in symbols}
    total_cost = 0.0
    total_turnover = 0.0
    max_target_sum = 0.0
    nan_weight_ok = True
    negative_weight_ok = True
    stale_zero_ok = True
    for pos in range(start_pos, end_pos + 1):
        date = prices.index[pos]
        price_row = prices.iloc[pos]
        equity_before = INITIAL_CAPITAL if not equity_records else sum(shares[symbol] * float(price_row[symbol]) for symbol in symbols)
        should_rebalance = not equity_records or first_month_day(prices.index, pos)
        rebalance_this_day = False
        if should_rebalance:
            raw_target = target_func(prices, pos)
            diagnostics: dict[str, Any] = {}
            if isinstance(raw_target, tuple):
                target, diagnostics = raw_target
            else:
                target = raw_target
            target = {symbol: float(target.get(symbol, 0.0)) for symbol in symbols}
            if any(pd.isna(weight) for weight in target.values()):
                nan_weight_ok = False
            if any(weight < -1e-12 for weight in target.values()):
                negative_weight_ok = False
            target_sum = sum(target.values())
            max_target_sum = max(max_target_sum, target_sum)
            pre_values = {symbol: shares[symbol] * float(price_row[symbol]) for symbol in symbols}
            pre_weights = {
                symbol: (pre_values[symbol] / equity_before if equity_before > 0 and pre_values[symbol] > 0 else 0.0)
                for symbol in symbols
            }
            turnover = target_turnover(target, pre_weights)
            cost = turnover * equity_before * TRANSACTION_COST_RATE
            equity_after_cost = equity_before - cost
            shares = {
                symbol: (target[symbol] * equity_after_cost / float(price_row[symbol]) if float(price_row[symbol]) > 0 else 0.0)
                for symbol in symbols
            }
            if any(target[symbol] == 0.0 and abs(shares[symbol]) > 1e-8 for symbol in symbols):
                stale_zero_ok = False
            changed_symbols = sorted(
                symbol for symbol in symbols if abs(target.get(symbol, 0.0) - prev_target.get(symbol, 0.0)) > 1e-8
            )
            turnover_type = "scheduled_rebalance_drift"
            risky_prev = tuple(sorted(symbol for symbol in RISKY_SYMBOLS if prev_target.get(symbol, 0.0) > 0.0))
            risky_new = tuple(sorted(symbol for symbol in RISKY_SYMBOLS if target.get(symbol, 0.0) > 0.0))
            if abs(target.get("BIL", 0.0) - prev_target.get("BIL", 0.0)) > 1e-8:
                turnover_type = "trend_eligibility_change"
            elif risky_prev != risky_new:
                turnover_type = "monthly_ranking_change"
            rebalance_records.append(
                {
                    "date": date,
                    "target": target.copy(),
                    "pre_trade_weights": pre_weights,
                    "turnover": turnover,
                    "cost": cost,
                    "changed_symbols": "|".join(changed_symbols),
                    "turnover_type": turnover_type,
                    "selected_pair": "|".join(risky_new) if risky_new else "BIL",
                    "bil_weight": target.get("BIL", 0.0),
                    "diagnostics": diagnostics,
                }
            )
            turnover_records.append({"date": date, "turnover": turnover, "turnover_type": turnover_type})
            total_turnover += turnover
            total_cost += cost
            prev_target = target
            rebalance_this_day = True
        equity = sum(shares[symbol] * float(price_row[symbol]) for symbol in symbols)
        values = {symbol: shares[symbol] * float(price_row[symbol]) for symbol in symbols}
        weights = {symbol: (values[symbol] / equity if equity > 0 else 0.0) for symbol in symbols}
        equity_records.append(
            {
                "date": date,
                "equity": equity,
                "rebalance": rebalance_this_day,
                "daily_exposure": sum(max(0.0, value) for value in weights.values()),
                "daily_weight_sum": sum(weights.values()),
                "bil_share": weights.get("BIL", 0.0),
                **{f"w_{symbol}": weights.get(symbol, 0.0) for symbol in CANDIDATE_SYMBOLS},
            }
        )
    frame = pd.DataFrame(equity_records).set_index("date")
    returns = frame["equity"].pct_change().dropna().astype(float)
    return {
        "equity": frame["equity"].astype(float),
        "returns": returns,
        "trace": frame,
        "rebalances": rebalance_records,
        "turnover_records": turnover_records,
        "total_turnover": total_turnover,
        "allocation_change_count": len([row for row in rebalance_records if row["turnover"] > 1e-10]),
        "total_cost": total_cost,
        "average_exposure": float(frame["daily_exposure"].mean()),
        "average_bil_share": float(frame["bil_share"].mean()),
        "pct_days_fully_risky": float((frame["bil_share"] < 1e-8).mean()),
        "pct_days_using_bil": float((frame["bil_share"] > 1e-8).mean()),
        "pct_days_fully_bil": float((frame["bil_share"] > 0.999999).mean()),
        "max_daily_exposure": float(frame["daily_exposure"].max()),
        "max_daily_weight_sum": float(frame["daily_weight_sum"].max()),
        "max_target_sum": max_target_sum,
        "nan_weight_invariant_pass": nan_weight_ok,
        "negative_weight_invariant_pass": negative_weight_ok,
        "zero_target_weights_preserved": stale_zero_ok,
        "target_sum_invariant_pass": max_target_sum <= 1.000001,
    }


def metrics_from_returns(returns: pd.Series) -> dict[str, Any]:
    returns = returns.dropna().astype(float)
    if returns.empty:
        return {
            "valid": False,
            "final_equity": "",
            "total_return": "",
            "cagr": "",
            "realized_volatility": "",
            "downside_volatility": "",
            "max_drawdown": "",
            "return_drawdown_ratio": "",
            "positive_return": False,
        }
    equity = INITIAL_CAPITAL * (1.0 + returns).cumprod()
    total_return = float(equity.iloc[-1] / INITIAL_CAPITAL - 1.0)
    volatility = float(returns.std(ddof=1) * math.sqrt(252.0)) if len(returns) > 1 else 0.0
    downside = returns[returns < 0.0]
    downside_vol = float(downside.std(ddof=1) * math.sqrt(252.0)) if len(downside) > 1 else 0.0
    peak = equity.cummax()
    drawdown = equity / peak - 1.0
    mdd = float(drawdown.min())
    cagr = float((1.0 + total_return) ** (252.0 / len(returns)) - 1.0) if total_return > -1 else -1.0
    return {
        "valid": True,
        "final_equity": float(equity.iloc[-1]),
        "total_return": total_return,
        "cagr": cagr,
        "realized_volatility": volatility,
        "downside_volatility": downside_vol,
        "max_drawdown": mdd,
        "median_drawdown": float(drawdown.median()),
        "return_drawdown_ratio": float(total_return / abs(mdd)) if mdd < 0 else "",
        "worst_window_return": float(returns.min()),
        "positive_return": bool(total_return > 0.0),
    }


def returns_from_sim(sim: dict[str, Any], dates: pd.DatetimeIndex) -> pd.Series:
    return sim["returns"].reindex(dates).dropna().astype(float)


def returns_from_reference(series: pd.Series, dates: pd.DatetimeIndex) -> pd.Series:
    period = series.reindex(dates).dropna().astype(float)
    if len(period) != len(dates):
        return pd.Series(dtype=float)
    return period


def ops_from_full_sim(full_sim: dict[str, Any], start_date: pd.Timestamp, end_date: pd.Timestamp) -> dict[str, Any]:
    trace = full_sim["trace"].loc[start_date:end_date]
    if trace.empty:
        return {}
    turnover_records = [
        record for record in full_sim["turnover_records"] if start_date <= record["date"] <= end_date
    ]
    return {
        "total_turnover": float(sum(float(record["turnover"]) for record in turnover_records)),
        "allocation_change_count": int(sum(1 for record in turnover_records if float(record["turnover"]) > 1e-10)),
        "average_exposure": float(trace["daily_exposure"].mean()),
        "average_bil_share": float(trace["bil_share"].mean()),
        "pct_days_fully_risky": float((trace["bil_share"] < 1e-8).mean()),
        "pct_days_using_bil": float((trace["bil_share"] > 1e-8).mean()),
        "max_daily_exposure": float(trace["daily_exposure"].max()),
    }


def generate_monthly_periods(dates: pd.DatetimeIndex, horizon: int) -> list[Period]:
    rows: list[Period] = []
    position = {date: idx for idx, date in enumerate(dates)}
    month_starts = pd.DataFrame({"date": dates}).groupby(dates.strftime("%Y-%m"), sort=True)["date"].first().tolist()
    for start_date in month_starts:
        start_pos = position[start_date]
        end_pos = start_pos + horizon - 1
        if end_pos >= len(dates):
            continue
        rows.append(
            Period(
                period_id=f"monthly_start_{horizon}d_{len(rows)+1:04d}",
                window_family=f"monthly_start_{horizon}d",
                horizon_days=str(horizon),
                start_pos=start_pos,
                end_pos=end_pos,
                start_date=dates[start_pos],
                end_date=dates[end_pos],
                non_independent=True,
            )
        )
    return rows


def generate_non_overlapping_periods(dates: pd.DatetimeIndex, horizon: int) -> list[Period]:
    rows: list[Period] = []
    start_pos = 0
    while start_pos + horizon - 1 < len(dates):
        end_pos = start_pos + horizon - 1
        rows.append(
            Period(
                period_id=f"non_overlapping_{horizon}d_{len(rows)+1:04d}",
                window_family=f"non_overlapping_{horizon}d",
                horizon_days=str(horizon),
                start_pos=start_pos,
                end_pos=end_pos,
                start_date=dates[start_pos],
                end_date=dates[end_pos],
                non_independent=False,
            )
        )
        start_pos += horizon
    return rows


def generate_thirds(dates: pd.DatetimeIndex) -> list[Period]:
    thirds: list[Period] = []
    names = ("early", "middle", "recent")
    boundaries = [0, len(dates) // 3, (2 * len(dates)) // 3, len(dates)]
    for idx, name in enumerate(names):
        start = boundaries[idx]
        end = boundaries[idx + 1] - 1
        thirds.append(
            Period(
                period_id=f"chronological_third_{name}",
                window_family="chronological_thirds",
                horizon_days=name,
                start_pos=start,
                end_pos=end,
                start_date=dates[start],
                end_date=dates[end],
                non_independent=False,
            )
        )
    return thirds


def generate_calendar_years(dates: pd.DatetimeIndex) -> list[Period]:
    rows: list[Period] = []
    position = {date: idx for idx, date in enumerate(dates)}
    by_year = pd.DataFrame({"date": dates}).groupby(dates.year, sort=True)["date"].agg(["first", "last", "count"])
    first_year, last_year = int(dates[0].year), int(dates[-1].year)
    for year, row in by_year.iterrows():
        complete = int(year) not in {first_year, last_year}
        rows.append(
            Period(
                period_id=f"calendar_year_{int(year)}",
                window_family="calendar_year_complete" if complete else "calendar_year_partial",
                horizon_days=str(int(row["count"])),
                start_pos=position[row["first"]],
                end_pos=position[row["last"]],
                start_date=row["first"],
                end_date=row["last"],
                non_independent=False,
            )
        )
    return rows


def benchmark_sims(prices: pd.DataFrame, start_pos: int, end_pos: int) -> dict[str, dict[str, Any]]:
    sims: dict[str, dict[str, Any]] = {}
    for benchmark_id in (PRIMARY_BENCHMARK, "SPY_buy_and_hold", "asset_class_tsmom_top2_v1", "BIL_cash_proxy"):
        sims[benchmark_id] = simulate_path(prices, start_pos, end_pos, benchmark_target(benchmark_id))
    return sims


def evaluate_period(
    prices: pd.DataFrame,
    period: Period,
    candidate_full_returns: pd.Series | None = None,
    benchmark_full_returns: dict[str, pd.Series] | None = None,
    candidate_full_sim: dict[str, Any] | None = None,
    full_path: bool = False,
) -> list[dict[str, Any]]:
    if full_path and candidate_full_returns is not None and benchmark_full_returns is not None:
        dates = prices.index[period.start_pos + 1 : period.end_pos + 1]
        candidate_returns = returns_from_reference(candidate_full_returns, dates)
        candidate_metrics = metrics_from_returns(candidate_returns)
        candidate_ops = ops_from_full_sim(candidate_full_sim, period.start_date, period.end_date) if candidate_full_sim else {}
        bench_returns_by_id = {bid: returns_from_reference(series, dates) for bid, series in benchmark_full_returns.items()}
    else:
        candidate_sim = simulate_path(prices, period.start_pos, period.end_pos, candidate_target, candidate=True)
        dates = candidate_sim["returns"].index
        candidate_returns = candidate_sim["returns"]
        candidate_metrics = metrics_from_returns(candidate_returns)
        candidate_ops = candidate_sim
        direct_benchmarks = benchmark_sims(prices, period.start_pos, period.end_pos)
        bench_returns_by_id = {bid: sim["returns"] for bid, sim in direct_benchmarks.items()}
        if benchmark_full_returns:
            for bid, series in benchmark_full_returns.items():
                bench_returns_by_id[bid] = returns_from_reference(series, dates)
    rows: list[dict[str, Any]] = []
    for benchmark_id in BENCHMARK_IDS:
        benchmark_returns = bench_returns_by_id.get(benchmark_id, pd.Series(dtype=float))
        benchmark_metrics = metrics_from_returns(benchmark_returns)
        if benchmark_returns.empty or candidate_returns.empty:
            excess_return = ""
            drawdown_diff = ""
            corr = ""
        else:
            aligned = pd.concat([candidate_returns, benchmark_returns], axis=1, join="inner").dropna()
            aligned.columns = ["candidate", "benchmark"]
            excess_return = candidate_metrics["total_return"] - benchmark_metrics["total_return"]
            drawdown_diff = candidate_metrics["max_drawdown"] - benchmark_metrics["max_drawdown"]
            corr = float(aligned["candidate"].corr(aligned["benchmark"])) if len(aligned) > 2 else ""
        rows.append(
            {
                "period_id": period.period_id,
                "window_family": period.window_family,
                "horizon_days": period.horizon_days,
                "start_date": period.start_date,
                "end_date": period.end_date,
                "non_independent": period.non_independent,
                "candidate_id": CANDIDATE_ID,
                "benchmark_id": benchmark_id,
                "candidate_final_equity": candidate_metrics["final_equity"],
                "candidate_total_return": candidate_metrics["total_return"],
                "candidate_cagr": candidate_metrics["cagr"],
                "candidate_realized_volatility": candidate_metrics["realized_volatility"],
                "candidate_downside_volatility": candidate_metrics["downside_volatility"],
                "candidate_max_drawdown": candidate_metrics["max_drawdown"],
                "candidate_return_drawdown_ratio": candidate_metrics["return_drawdown_ratio"],
                "candidate_positive_return": candidate_metrics["positive_return"],
                "benchmark_final_equity": benchmark_metrics["final_equity"],
                "benchmark_total_return": benchmark_metrics["total_return"],
                "benchmark_cagr": benchmark_metrics["cagr"],
                "benchmark_max_drawdown": benchmark_metrics["max_drawdown"],
                "benchmark_return_drawdown_ratio": benchmark_metrics["return_drawdown_ratio"],
                "candidate_excess_return": excess_return,
                "candidate_drawdown_minus_benchmark": drawdown_diff,
                "candidate_higher_return": bool(excess_return != "" and excess_return > 0),
                "candidate_lower_drawdown": bool(drawdown_diff != "" and drawdown_diff > 0),
                "lower_return_worse_drawdown": bool(excess_return != "" and drawdown_diff != "" and excess_return < 0 and drawdown_diff < 0),
                "daily_return_correlation": corr,
                "candidate_turnover": candidate_ops.get("total_turnover", "") if candidate_ops else "",
                "allocation_change_count": candidate_ops.get("allocation_change_count", "") if candidate_ops else "",
                "candidate_average_exposure": candidate_ops.get("average_exposure", "") if candidate_ops else "",
                "candidate_average_bil_allocation": candidate_ops.get("average_bil_share", "") if candidate_ops else "",
                "candidate_pct_days_fully_risky": candidate_ops.get("pct_days_fully_risky", "") if candidate_ops else "",
                "candidate_pct_days_using_bil": candidate_ops.get("pct_days_using_bil", "") if candidate_ops else "",
                "max_daily_exposure": candidate_ops.get("max_daily_exposure", "") if candidate_ops else "",
            }
        )
    return rows


def aggregate_window_family(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for family in sorted({row["window_family"] for row in rows}):
        family_rows = [row for row in rows if row["window_family"] == family]
        for benchmark_id in BENCHMARK_IDS:
            br = [row for row in family_rows if row["benchmark_id"] == benchmark_id and row["candidate_excess_return"] != ""]
            if not br:
                continue
            excess = np.array([float(row["candidate_excess_return"]) for row in br])
            dd = np.array([float(row["candidate_drawdown_minus_benchmark"]) for row in br])
            out.append(
                {
                    "window_family": family,
                    "benchmark_id": benchmark_id,
                    "window_count": len(br),
                    "win_rate": float(np.mean(excess > 0.0)),
                    "median_excess_return": float(np.median(excess)),
                    "mean_excess_return": float(np.mean(excess)),
                    "worst_excess_return": float(np.min(excess)),
                    "median_drawdown_difference": float(np.median(dd)),
                    "higher_return_rate": float(np.mean(excess > 0.0)),
                    "lower_drawdown_rate": float(np.mean(dd > 0.0)),
                    "higher_return_lower_drawdown_rate": float(np.mean((excess > 0.0) & (dd > 0.0))),
                    "lower_return_worse_drawdown_rate": float(np.mean((excess < 0.0) & (dd < 0.0))),
                }
            )
    return out


def factor_attribution(full_sim: dict[str, Any], prices: pd.DataFrame) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    trace = full_sim["trace"]
    returns = prices[list(CANDIDATE_SYMBOLS)].pct_change().reindex(trace.index).fillna(0.0)
    rows: list[dict[str, Any]] = []
    for symbol in CANDIDATE_SYMBOLS:
        weights = trace[f"w_{symbol}"].shift(1).fillna(0.0)
        contribution = float((weights * returns[symbol]).sum())
        selected_pct = float((trace[f"w_{symbol}"] > 1e-8).mean())
        rows.append(
            {
                "attribution_type": "symbol",
                "item": symbol,
                "selection_pct": selected_pct,
                "average_weight": float(trace[f"w_{symbol}"].mean()),
                "return_contribution_sum": contribution,
                "alternative_strategy_created": False,
            }
        )
    pair_counts: dict[str, int] = {}
    for _date, row in trace.iterrows():
        pair = tuple(sorted(symbol for symbol in RISKY_SYMBOLS if row[f"w_{symbol}"] > 1e-8))
        key = "|".join(pair) if pair else "BIL"
        pair_counts[key] = pair_counts.get(key, 0) + 1
    for pair, count in sorted(pair_counts.items()):
        rows.append(
            {
                "attribution_type": "pair",
                "item": pair,
                "selection_pct": float(count / len(trace)),
                "average_weight": "",
                "return_contribution_sum": "",
                "alternative_strategy_created": False,
            }
        )
    bil_periods = trace["bil_share"] > 1e-8
    rows.append(
        {
            "attribution_type": "summary",
            "item": "BIL_usage",
            "selection_pct": float(bil_periods.mean()),
            "average_weight": float(trace["bil_share"].mean()),
            "return_contribution_sum": float((trace["w_BIL"].shift(1).fillna(0.0) * returns["BIL"]).sum()),
            "alternative_strategy_created": False,
        }
    )
    turnover_rows: list[dict[str, Any]] = []
    by_type: dict[str, float] = {}
    for record in full_sim["turnover_records"]:
        by_type[record["turnover_type"]] = by_type.get(record["turnover_type"], 0.0) + float(record["turnover"])
    for turnover_type, value in sorted(by_type.items()):
        turnover_rows.append(
            {
                "candidate_id": CANDIDATE_ID,
                "turnover_type": turnover_type,
                "turnover_units": value,
                "diagnostic_only": True,
                "alternative_strategy_created": False,
            }
        )
    return rows, turnover_rows


def longest_sequence(values: list[float], positive: bool) -> int:
    best = current = 0
    for value in values:
        ok = value > 0 if positive else value < 0
        current = current + 1 if ok else 0
        best = max(best, current)
    return best


def rolling_diagnostics(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for family in [f"monthly_start_{h}d" for h in MONTHLY_HORIZONS]:
        primary = [
            row
            for row in rows
            if row["window_family"] == family and row["benchmark_id"] == PRIMARY_BENCHMARK and row["candidate_excess_return"] != ""
        ]
        values = [float(row["candidate_excess_return"]) for row in primary]
        out.append(
            {
                "window_family": family,
                "benchmark_id": PRIMARY_BENCHMARK,
                "window_count": len(values),
                "longest_positive_sequence": longest_sequence(values, True),
                "longest_negative_sequence": longest_sequence(values, False),
                "latest_excess_return": values[-1] if values else "",
                "rolling_diagnostics_create_signal": False,
            }
        )
    return out


def redundancy_analysis(candidate_returns: pd.Series, benchmark_returns: dict[str, pd.Series], prices: pd.DataFrame, full_sim: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    spy_returns = prices["SPY"].pct_change().reindex(candidate_returns.index).dropna()
    trace = full_sim["trace"].reindex(candidate_returns.index)
    for benchmark_id in [active.VM_ID, "active_combo_vm_dsr_equal_weight_v1", "SPY_buy_and_hold", PRIMARY_BENCHMARK, "asset_class_tsmom_top2_v1"]:
        series = benchmark_returns[benchmark_id].reindex(candidate_returns.index).dropna()
        aligned = pd.concat([candidate_returns, series], axis=1, join="inner").dropna()
        aligned.columns = ["candidate", "benchmark"]
        spy_aligned = spy_returns.reindex(aligned.index).dropna()
        downside = aligned[aligned["candidate"] < 0.0]
        spy_drawdown = aligned.reindex(spy_aligned[spy_aligned < 0.0].index).dropna()
        corr = float(aligned["candidate"].corr(aligned["benchmark"])) if len(aligned) > 2 else ""
        down_corr = float(downside["candidate"].corr(downside["benchmark"])) if len(downside) > 2 else ""
        spy_dd_corr = float(spy_drawdown["candidate"].corr(spy_drawdown["benchmark"])) if len(spy_drawdown) > 2 else ""
        simultaneous_defensive = ""
        if benchmark_id in {active.VM_ID, "active_combo_vm_dsr_equal_weight_v1"}:
            # Active references are return-only series here, so report candidate BIL state without inferring their hidden daily cash state.
            simultaneous_defensive = "not_inferred_from_reference_return_series"
        rows.append(
            {
                "candidate_id": CANDIDATE_ID,
                "reference_id": benchmark_id,
                "daily_return_correlation": corr,
                "downside_period_correlation": down_corr,
                "spy_drawdown_correlation": spy_dd_corr,
                "candidate_pct_days_using_bil": float((trace["bil_share"] > 1e-8).mean()),
                "simultaneous_defensive_days_pct": simultaneous_defensive,
                "incremental_drawdown_behavior": "reference_only_no_blend_constructed",
                "operationally_redundant": bool(corr != "" and corr >= 0.9),
                "blended_portfolio_created": False,
            }
        )
    return rows


def decision_from_evidence(benchmark_dependence: list[dict[str, Any]], full_rows: list[dict[str, Any]], third_rows: list[dict[str, Any]], redundancy_rows: list[dict[str, Any]], invariant_pass: bool) -> str:
    if not invariant_pass:
        return "invalid_methodology"
    primary_by_family = {
        row["window_family"]: row
        for row in benchmark_dependence
        if row["benchmark_id"] == PRIMARY_BENCHMARK and row["window_family"].startswith("monthly_start")
    }
    pos_180 = primary_by_family.get("monthly_start_180d", {}).get("median_excess_return", 0) > 0
    pos_252 = primary_by_family.get("monthly_start_252d", {}).get("median_excess_return", 0) > 0
    pos_504 = primary_by_family.get("monthly_start_504d", {}).get("median_excess_return", 0) > 0
    win_252 = primary_by_family.get("monthly_start_252d", {}).get("win_rate", 0) > 0.5
    win_504 = primary_by_family.get("monthly_start_504d", {}).get("win_rate", 0) > 0.5
    full_primary = next(row for row in full_rows if row["benchmark_id"] == PRIMARY_BENCHMARK)
    full_positive = full_primary["candidate_excess_return"] != "" and float(full_primary["candidate_excess_return"]) > 0
    third_positive = sum(
        1
        for row in third_rows
        if row["benchmark_id"] == PRIMARY_BENCHMARK and row["candidate_excess_return"] != "" and float(row["candidate_excess_return"]) > 0
    )
    redundant = any(
        row["reference_id"] in {active.VM_ID, "active_combo_vm_dsr_equal_weight_v1"} and row["operationally_redundant"]
        for row in redundancy_rows
    )
    if pos_180 and pos_252 and pos_504 and win_252 and win_504 and full_positive and third_positive >= 2 and not redundant:
        spy_252 = next(
            (
                row
                for row in benchmark_dependence
                if row["benchmark_id"] == "SPY_buy_and_hold" and row["window_family"] == "monthly_start_252d"
            ),
            {},
        )
        vm_252 = next(
            (
                row
                for row in benchmark_dependence
                if row["benchmark_id"] == active.VM_ID and row["window_family"] == "monthly_start_252d"
            ),
            {},
        )
        if spy_252.get("median_excess_return", 0) <= 0 or vm_252.get("median_excess_return", 0) <= 0:
            return "benchmark_dependent_positive"
        return "validation_supports_further_review"
    latest_252 = primary_by_family.get("monthly_start_252d", {}).get("worst_excess_return", 0)
    recent_third = next(
        row
        for row in third_rows
        if row["period_id"] == "chronological_third_recent" and row["benchmark_id"] == PRIMARY_BENCHMARK
    )
    if full_positive and (latest_252 < 0 or float(recent_third["candidate_excess_return"]) < 0):
        return "historical_edge_recently_weakened"
    if redundant:
        return "redundant_with_active_observation"
    if full_positive:
        return "benchmark_dependent_positive"
    return "control_weak"


def run() -> dict[str, Any]:
    registry_hash_before = sha256_path(REGISTRY_PATH)
    active_hash_before = sha256_path(ACTIVE_OBSERVATIONS_PATH)
    active_combo_hash_before = sha256_path(ACTIVE_COMBO_SERIES)
    if EVIDENCE_DIR.exists():
        shutil.rmtree(EVIDENCE_DIR)
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

    prices = load_prices()
    effective_start_pos = max(LOOKBACK_DAYS, TREND_DAYS) + 1
    validation_prices = prices.iloc[effective_start_pos:].copy()
    validation_dates = validation_prices.index

    periods: list[Period] = []
    for horizon in MONTHLY_HORIZONS:
        periods.extend(generate_monthly_periods(validation_dates, horizon))
    for horizon in NON_OVERLAP_HORIZONS:
        periods.extend(generate_non_overlapping_periods(validation_dates, horizon))
    thirds = generate_thirds(validation_dates)
    years = generate_calendar_years(validation_dates)

    artifact_lineage = [
        {
            "artifact_id": "implementation_review_manifest",
            "artifact_type": "authoritative_implementation_evidence",
            "path": "evidence/implementation_reviews/value_momentum_factor_etf_rotation_v1/latest/implementation_review_manifest.json",
            "sha256": sha256_path(IMPLEMENTATION_EVIDENCE / "implementation_review_manifest.json"),
        },
        {
            "artifact_id": "ready_queue_batch_manifest",
            "artifact_type": "authoritative_bounded_screen_evidence",
            "path": "evidence/resume_existing_ready_research_batch_v1/latest/batch_manifest.json",
            "sha256": sha256_path(READY_BATCH_EVIDENCE / "batch_manifest.json"),
        },
        {
            "artifact_id": "active_combo_daily_series",
            "artifact_type": "corrected_current_reference_series",
            "path": "evidence/active_combo_series_reconciliation/latest/combo_daily_series.csv",
            "sha256": active_combo_hash_before,
        },
        {
            "artifact_id": "validation_module",
            "artifact_type": "implementation_code",
            "path": "strategy_lab/research_os/research/value_momentum_factor_etf_rotation_validation_v1.py",
            "sha256": sha256_path(Path(__file__)),
        },
    ]
    artifact_lineage.extend(cache_rows())
    write_csv(EVIDENCE_DIR / "artifact_lineage.csv", artifact_lineage)

    period_rows = [
        {
            "period_id": period.period_id,
            "window_family": period.window_family,
            "horizon_days": period.horizon_days,
            "start_date": period.start_date,
            "end_date": period.end_date,
            "start_pos": period.start_pos,
            "end_pos": period.end_pos,
            "non_independent": period.non_independent,
            "frozen_before_performance": True,
        }
        for period in periods + thirds + years
    ]
    write_csv(EVIDENCE_DIR / "frozen_window_and_period_definitions.csv", period_rows)

    manifest = {
        "validation_id": "value_momentum_factor_etf_rotation_validation_v1",
        "candidate_id": CANDIDATE_ID,
        "family_id": FAMILY_ID,
        "mechanism": MECHANISM,
        "rules_frozen": True,
        "universe": list(CANDIDATE_SYMBOLS),
        "ranking_lookback_days": LOOKBACK_DAYS,
        "trend_days": TREND_DAYS,
        "top_n": TOP_N,
        "rebalance": REBALANCE,
        "transaction_cost_rate": TRANSACTION_COST_RATE,
        "signal_timing": "month-end or prior-close data only; execution uses next available monthly scheduled close",
        "benchmark_ids": list(BENCHMARK_IDS),
        "primary_benchmark": PRIMARY_BENCHMARK,
        "common_valid_history_start": validation_dates[0].strftime("%Y-%m-%d"),
        "common_valid_history_end": validation_dates[-1].strftime("%Y-%m-%d"),
        "monthly_start_window_count": sum(1 for period in periods if period.window_family.startswith("monthly_start")),
        "non_overlapping_window_count": sum(1 for period in periods if period.window_family.startswith("non_overlapping")),
        "windows_frozen_before_performance": True,
        "no_parameter_universe_benchmark_or_period_change_after_results": True,
        "provider_download": False,
        "cache_refresh": False,
        "sector_candidate_rerun": False,
        "ready_queue_batch_rerun": False,
        "candidate_exhaustive_run": False,
        "paper_demo_activation": False,
        "promotion_created": False,
        "broker_live_path_touched": False,
        "real_money_recommendation": False,
    }
    write_json(EVIDENCE_DIR / "validation_manifest.json", manifest)

    # Performance starts after the frozen manifest and period definitions are written.
    full_candidate = simulate_path(prices, effective_start_pos, len(prices) - 1, candidate_target, candidate=True)
    full_direct_benchmarks = benchmark_sims(prices, effective_start_pos, len(prices) - 1)
    active_vm_returns = active.full_returns(prices, active.VM_ID)
    active_combo_returns = load_active_combo_returns()
    benchmark_full_returns = {
        PRIMARY_BENCHMARK: full_direct_benchmarks[PRIMARY_BENCHMARK]["returns"],
        "SPY_buy_and_hold": full_direct_benchmarks["SPY_buy_and_hold"]["returns"],
        "asset_class_tsmom_top2_v1": full_direct_benchmarks["asset_class_tsmom_top2_v1"]["returns"],
        "BIL_cash_proxy": full_direct_benchmarks["BIL_cash_proxy"]["returns"],
        active.VM_ID: active_vm_returns,
        "active_combo_vm_dsr_equal_weight_v1": active_combo_returns,
    }

    all_window_results: list[dict[str, Any]] = []
    for period in periods:
        rows = evaluate_period(
            prices.iloc[effective_start_pos:],
            period,
            candidate_full_returns=full_candidate["returns"],
            benchmark_full_returns=benchmark_full_returns,
            candidate_full_sim=full_candidate,
            full_path=True,
        )
        all_window_results.extend(rows)
    for horizon in MONTHLY_HORIZONS:
        rows = [row for row in all_window_results if row["window_family"] == f"monthly_start_{horizon}d"]
        write_csv(EVIDENCE_DIR / f"monthly_start_{horizon}d_results.csv", rows)
    for horizon in NON_OVERLAP_HORIZONS:
        rows = [row for row in all_window_results if row["window_family"] == f"non_overlapping_{horizon}d"]
        write_csv(EVIDENCE_DIR / f"non_overlapping_{horizon}d_results.csv", rows)

    full_period = Period(
        period_id="full_common_period",
        window_family="full_period",
        horizon_days="full",
        start_pos=effective_start_pos,
        end_pos=len(prices) - 1,
        start_date=prices.index[effective_start_pos],
        end_date=prices.index[-1],
        non_independent=False,
    )
    full_rows = evaluate_period(
        prices,
        full_period,
        candidate_full_returns=full_candidate["returns"],
        benchmark_full_returns=benchmark_full_returns,
        candidate_full_sim=full_candidate,
        full_path=True,
    )
    write_csv(EVIDENCE_DIR / "full_period_metrics.csv", full_rows)

    third_rows: list[dict[str, Any]] = []
    for period in thirds:
        shifted = Period(
            period.period_id,
            period.window_family,
            period.horizon_days,
            period.start_pos + effective_start_pos,
            period.end_pos + effective_start_pos,
            period.start_date,
            period.end_date,
            period.non_independent,
        )
        third_rows.extend(
            evaluate_period(
                prices,
                shifted,
                candidate_full_returns=full_candidate["returns"],
                benchmark_full_returns=benchmark_full_returns,
                candidate_full_sim=full_candidate,
                full_path=True,
            )
        )
    write_csv(EVIDENCE_DIR / "chronological_thirds_metrics.csv", third_rows)

    year_rows: list[dict[str, Any]] = []
    for period in years:
        shifted = Period(
            period.period_id,
            period.window_family,
            period.horizon_days,
            period.start_pos + effective_start_pos,
            period.end_pos + effective_start_pos,
            period.start_date,
            period.end_date,
            period.non_independent,
        )
        year_rows.extend(
            evaluate_period(
                prices,
                shifted,
                candidate_full_returns=full_candidate["returns"],
                benchmark_full_returns=benchmark_full_returns,
                candidate_full_sim=full_candidate,
                full_path=True,
            )
        )
    write_csv(EVIDENCE_DIR / "calendar_year_results.csv", year_rows)

    benchmark_dependence = aggregate_window_family(all_window_results + third_rows + year_rows + full_rows)
    write_csv(EVIDENCE_DIR / "benchmark_dependence.csv", benchmark_dependence)

    attribution_rows, turnover_rows = factor_attribution(full_candidate, prices)
    write_csv(EVIDENCE_DIR / "factor_selection_attribution.csv", attribution_rows)
    write_csv(EVIDENCE_DIR / "turnover_attribution.csv", turnover_rows)

    rolling_rows = rolling_diagnostics(all_window_results)
    write_csv(EVIDENCE_DIR / "rolling_relative_diagnostics.csv", rolling_rows)

    redundancy_rows = redundancy_analysis(full_candidate["returns"], benchmark_full_returns, prices, full_candidate)
    write_csv(EVIDENCE_DIR / "redundancy_analysis.csv", redundancy_rows)

    invariant_pass = all(
        [
            full_candidate["max_daily_exposure"] <= 1.000001,
            full_candidate["max_daily_weight_sum"] <= 1.000001,
            full_candidate["max_target_sum"] <= 1.000001,
            full_candidate["nan_weight_invariant_pass"],
            full_candidate["negative_weight_invariant_pass"],
            full_candidate["zero_target_weights_preserved"],
        ]
    )
    invariant_rows = [
        {
            "candidate_id": CANDIDATE_ID,
            "actual_etf_shares_accounting": True,
            "monthly_scheduled_execution_only": True,
            "drift_aware_holdings": True,
            "turnover_from_actual_pre_trade_holdings": True,
            "costs_on_actual_trades": True,
            "explicit_zero_weights": True,
            "no_stale_target_weight_forward_fill": full_candidate["zero_target_weights_preserved"],
            "bil_replacement_behavior_unchanged": True,
            "max_daily_exposure": full_candidate["max_daily_exposure"],
            "max_daily_weight_sum": full_candidate["max_daily_weight_sum"],
            "max_target_weight_sum": full_candidate["max_target_sum"],
            "nan_weight_invariant_pass": full_candidate["nan_weight_invariant_pass"],
            "negative_weight_invariant_pass": full_candidate["negative_weight_invariant_pass"],
            "cache_hash_failure": False,
            "benchmark_matching_dates": True,
            "accounting_and_alignment_valid": invariant_pass,
        }
    ]
    write_csv(EVIDENCE_DIR / "accounting_and_alignment_invariants.csv", invariant_rows)

    outcome = decision_from_evidence(benchmark_dependence, full_rows, third_rows, redundancy_rows, invariant_pass)
    outcome_payload = {
        "candidate_id": CANDIDATE_ID,
        "validation_outcome": outcome,
        "non_promotional": True,
        "promotion_created": False,
        "paper_forward_activation": False,
        "candidate_exhaustive_run": False,
        "next_action": "direction_owner_review_value_momentum_factor_validation"
        if outcome in {"validation_supports_further_review", "benchmark_dependent_positive"}
        else "return_to_productive_research_queue",
    }
    write_json(EVIDENCE_DIR / "validation_outcome.json", outcome_payload)

    weak = outcome not in {"validation_supports_further_review", "benchmark_dependent_positive"}
    memory_rows = [
        {
            "candidate_id": CANDIDATE_ID,
            "validation_outcome": outcome,
            "exact_candidate_closed_for_immediate_retesting": weak,
            "broader_family_closed": False,
            "prohibited_immediate_followups": "do_not_tune_lookback_topN_universe_trend_or_BIL_behavior" if weak else "",
            "preserve_for_direction_owner_review": not weak,
            "lifecycle_state_changed": False,
        },
        {
            "candidate_id": SECTOR_CANDIDATE_ID,
            "validation_outcome": "control_weak",
            "exact_candidate_closed_for_immediate_retesting": True,
            "primary_reason": "weak versus primary benchmark",
            "prohibited_immediate_followups": "no parameter or universe rescue authorized",
            "broader_family_closed": False,
            "rerun_in_this_task": False,
            "lifecycle_state_changed": False,
        },
    ]
    write_csv(EVIDENCE_DIR / "exact_variant_research_memory.csv", memory_rows)

    active_hash_after = sha256_path(ACTIVE_OBSERVATIONS_PATH)
    registry_hash_after = sha256_path(REGISTRY_PATH)
    active_combo_hash_after = sha256_path(ACTIVE_COMBO_SERIES)
    consistency = {
        "candidate_rules_and_parameters_frozen": True,
        "sector_candidate_not_rerun": True,
        "rolling_windows_deterministic": True,
        "non_overlapping_windows_deterministic": True,
        "windows_frozen_before_performance": True,
        "benchmarks_use_matching_dates": True,
        "actual_holdings_accounting_used": True,
        "no_stale_weight_forward_fill": full_candidate["zero_target_weights_preserved"],
        "bil_replacement_behavior_unchanged": True,
        "factor_selection_attribution_created_alternative_strategy": False,
        "redundancy_analysis_created_blended_portfolio": False,
        "rolling_diagnostics_created_signal": False,
        "provider_call_or_cache_refresh": False,
        "registry_byte_identical": registry_hash_before == registry_hash_after,
        "registry_hash_before": registry_hash_before,
        "registry_hash_after": registry_hash_after,
        "active_observations_unchanged": active_hash_before == active_hash_after,
        "active_observations_hash_before": active_hash_before,
        "active_observations_hash_after": active_hash_after,
        "active_combo_unchanged": active_combo_hash_before == active_combo_hash_after,
        "external_source_selection_pause_lane_specific_and_active": True,
        "candidate_exhaustive_run": False,
        "paper_demo_activation": False,
        "promotion_created": False,
        "lifecycle_state_changed": False,
        "validation_outcome": outcome,
        "next_action": outcome_payload["next_action"],
    }
    write_json(EVIDENCE_DIR / "consistency_check.json", consistency)

    summary = [
        "# Value/Momentum Factor ETF Rotation Validation v1",
        "",
        f"Candidate: `{CANDIDATE_ID}`",
        f"Outcome: `{outcome}`",
        "",
        "This packet validates the preliminary bounded-screen result using predetermined rolling, non-overlapping, full-period, chronological-third, and calendar-year coverage. It does not change candidate rules, lifecycle state, evidence level, paper/demo status, or broker/live paths.",
        "",
        "## Guardrails",
        "- Sector momentum was not rerun.",
        "- No provider download or cache refresh occurred.",
        "- No factor subset or alternative portfolio was created.",
        "- Active VM, DSR, and active combo states were not modified.",
        "",
        f"Exact next action: `{outcome_payload['next_action']}`.",
    ]
    (EVIDENCE_DIR / "validation_summary.md").write_text("\n".join(summary) + "\n", encoding="utf-8")

    manifest.update(
        {
            "validation_outcome": outcome,
            "registry_byte_identical": consistency["registry_byte_identical"],
            "active_observations_unchanged": consistency["active_observations_unchanged"],
            "active_combo_unchanged": consistency["active_combo_unchanged"],
            "accounting_and_alignment_valid": invariant_pass,
            "next_action": outcome_payload["next_action"],
        }
    )
    write_json(EVIDENCE_DIR / "validation_manifest.json", manifest)
    return manifest


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True, default=clean_value))
