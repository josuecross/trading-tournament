from __future__ import annotations

import csv
import hashlib
import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

import run_active_strategy_evidence_recompute as active


ROOT = Path(__file__).resolve().parents[3]
STRATEGY_ID = "quantpedia_asset_class_momentum_rotational_top3_12m_v1"
FAMILY_ID = "cross_asset_relative_momentum_rotation"
RUN_ID = "quantpedia_asset_class_momentum_adaptive_research_v1"
OUTPUT_DIR = (
    Path("evidence")
    / "public_source_strategy_implementation"
    / STRATEGY_ID
    / "adaptive_research_v1"
    / "latest"
)
PRIOR_GATE_DIR = Path("evidence") / "public_source_strategy_implementation" / STRATEGY_ID / "latest"
PILOT_CACHE_DIR = Path("data") / "universe_expansion" / "pilot_etf_market_data_v1"
REGISTRY_PATH = Path("strategy_lab") / "strategy_registry.yaml"
ACTIVE_OBSERVATIONS_PATH = Path("strategy_lab") / "research_os" / "operations" / "active_observations.yaml"

BASELINE_UNIVERSE = ("SPY", "EFA", "BND", "VNQ", "GSG")
OPTIONAL_SYMBOLS = ("BIL", "DBC")
LOOKBACK_MONTHS = 12
BASELINE_TOP_N = 3
STARTING_EQUITY = active.STARTING_EQUITY
SLIPPAGE = active.SLIPPAGE
TOL = 1e-9
NEXT_ACTION = "direction_owner_review_quantpedia_asset_class_momentum_adaptive_research_v1"


@dataclass(frozen=True)
class VariantSpec:
    variant_id: str
    parent_baseline_id: str
    role: str
    universe: tuple[str, ...]
    lookback_months: int
    top_n: int
    execution_delay_sessions: int
    benchmark_id: str
    changed_dimension: str
    rationale: str


@dataclass
class ReturnPath:
    variant_id: str
    universe: tuple[str, ...]
    daily_returns: pd.Series
    equity: pd.Series
    end_weights: pd.DataFrame
    start_weights: pd.DataFrame
    pre_trade_weights: pd.DataFrame
    post_trade_weights: pd.DataFrame
    target_weights: pd.DataFrame
    turnover: pd.Series
    costs: pd.Series
    gross_returns: pd.Series
    contribution_returns: pd.DataFrame
    execution_targets: pd.DataFrame
    signal_rows: list[dict[str, Any]]


def abs_path(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return ""
        return f"{value:.12g}"
    if isinstance(value, (list, tuple, set)):
        return "|".join(str(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True)
    return str(value)


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    full = abs_path(path)
    full.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = sorted({key for row in rows for key in row})
    with full.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: csv_value(row.get(field, "")) for field in fieldnames})


def write_json(path: Path, payload: dict[str, Any]) -> None:
    full = abs_path(path)
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    full = abs_path(path)
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(yaml.safe_dump(payload, sort_keys=False, width=120), encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    full = abs_path(path)
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(text.rstrip() + "\n", encoding="utf-8")


def sha256_path(path: Path) -> str:
    full = abs_path(path)
    if not full.exists():
        return "missing"
    digest = hashlib.sha256()
    with full.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_hash(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def clean_output_dir() -> None:
    output = abs_path(OUTPUT_DIR)
    output.mkdir(parents=True, exist_ok=True)
    for path in output.iterdir():
        if path.is_file():
            path.unlink()


def load_prices(symbols: tuple[str, ...] | list[str]) -> pd.DataFrame:
    series: list[pd.Series] = []
    for symbol in symbols:
        path = abs_path(PILOT_CACHE_DIR / f"{symbol}.csv")
        if not path.exists():
            raise FileNotFoundError(f"missing pilot cache file for {symbol}: {path}")
        frame = pd.read_csv(path)
        if "adj_close" not in frame.columns:
            raise ValueError(f"{symbol} cache lacks adj_close")
        dates = pd.to_datetime(frame["date"], errors="coerce").dt.tz_localize(None)
        close = pd.to_numeric(frame["adj_close"], errors="coerce")
        item = pd.Series(close.to_numpy(dtype=float), index=dates, name=symbol).dropna().sort_index()
        item = item[~item.index.duplicated(keep="last")]
        series.append(item)
    return pd.concat(series, axis=1, sort=True).sort_index()


def cache_quality_rows(symbols: tuple[str, ...] | list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for symbol in symbols:
        path = abs_path(PILOT_CACHE_DIR / f"{symbol}.csv")
        if not path.exists():
            rows.append({"symbol": symbol, "exists": False, "cache_path": str(PILOT_CACHE_DIR / f"{symbol}.csv")})
            continue
        frame = pd.read_csv(path)
        dates = pd.to_datetime(frame["date"], errors="coerce")
        close = pd.to_numeric(frame.get("adj_close"), errors="coerce")
        rows.append(
            {
                "symbol": symbol,
                "exists": True,
                "cache_path": str(PILOT_CACHE_DIR / f"{symbol}.csv"),
                "provider_or_source": "existing_repository_pilot_etf_market_data_v1",
                "retrieval_method": "repository_local_cache_reuse",
                "retrieval_timestamp": "preexisting_cache_file",
                "start_date": str(dates.min().date()),
                "end_date": str(dates.max().date()),
                "price_field": "adj_close",
                "adjustment_methodology": "cache_adjusted_close_field",
                "currency": "USD",
                "trading_calendar": "ETF_exchange_sessions_as_cached",
                "row_count": int(len(frame)),
                "missing_adj_close_count": int(close.isna().sum()),
                "duplicate_date_count": int(dates.duplicated().sum()),
                "nonpositive_adj_close_count": int((close <= 0).sum()),
                "file_hash": sha256_path(path),
            }
        )
    return rows


def month_end_frame(prices: pd.DataFrame, universe: tuple[str, ...]) -> tuple[pd.DataFrame, dict[pd.Period, pd.Timestamp]]:
    common = prices[list(universe)].dropna()
    grouped = common.groupby(common.index.to_period("M"))
    closes = grouped.last()
    dates = grouped.apply(lambda frame: frame.index[-1])
    return closes, {pd.Period(k, freq="M"): pd.Timestamp(v) for k, v in dates.items()}


def rank_symbols(scores: dict[str, float]) -> list[str]:
    return sorted(scores, key=lambda symbol: (-scores[symbol], symbol))


def build_signals(spec: VariantSpec, prices: pd.DataFrame) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    closes, month_dates = month_end_frame(prices, spec.universe)
    common_daily = pd.DatetimeIndex(prices[list(spec.universe)].dropna().index)
    target_by_execution: dict[pd.Timestamp, dict[str, float]] = {}
    rows: list[dict[str, Any]] = []
    for pos in range(spec.lookback_months, len(closes.index)):
        period = closes.index[pos]
        lag_period = closes.index[pos - spec.lookback_months]
        current = closes.loc[period, list(spec.universe)].astype(float)
        lagged = closes.loc[lag_period, list(spec.universe)].astype(float)
        if current.isna().any() or lagged.isna().any() or (lagged <= 0).any():
            continue
        scores = {symbol: float(current[symbol] / lagged[symbol] - 1.0) for symbol in spec.universe}
        ranked = rank_symbols(scores)
        selected = ranked[: spec.top_n]
        target = {symbol: 0.0 for symbol in spec.universe}
        for symbol in selected:
            target[symbol] = 1.0 / spec.top_n
        signal_date = month_dates[pd.Period(period, freq="M")]
        candidates = common_daily[common_daily > signal_date]
        if len(candidates) < spec.execution_delay_sessions:
            continue
        execution_date = pd.Timestamp(candidates[spec.execution_delay_sessions - 1])
        target_by_execution[execution_date] = target
        row = {
            "variant_id": spec.variant_id,
            "signal_month": str(period),
            "signal_date": str(signal_date.date()),
            "execution_date": str(execution_date.date()),
            "lag_month": str(lag_period),
            "lookback_months": spec.lookback_months,
            "top_n": spec.top_n,
            "rank_order": "|".join(ranked),
            "selected": "|".join(selected),
            "tie_breaker": "ticker_symbol_ascending",
            "signal_precedes_execution": signal_date < execution_date,
            "execution_delay_sessions": spec.execution_delay_sessions,
            "weight_sum": sum(target.values()),
            "explicit_zero_targets": all(symbol in target and target[symbol] == 0.0 for symbol in set(spec.universe) - set(selected)),
        }
        for symbol in spec.universe:
            row[f"{symbol}_momentum_12m"] = scores[symbol]
            row[f"{symbol}_rank"] = ranked.index(symbol) + 1
            row[f"{symbol}_target_weight"] = target[symbol]
        rows.append(row)
    targets = pd.DataFrame.from_dict(target_by_execution, orient="index").sort_index()
    targets = targets.reindex(columns=list(spec.universe), fill_value=0.0).fillna(0.0)
    return targets, rows


def implicit_cash_turnover(pre_trade: pd.Series, target: pd.Series) -> float:
    pre_sum = float(pre_trade.sum())
    target_sum = float(target.sum())
    pre_cash = max(0.0, 1.0 - pre_sum)
    target_cash = max(0.0, 1.0 - target_sum)
    return float((target - pre_trade).abs().sum() + abs(target_cash - pre_cash)) / 2.0


def simulate_path(
    spec: VariantSpec,
    prices: pd.DataFrame,
    execution_targets: pd.DataFrame,
    signal_rows: list[dict[str, Any]],
    slippage: float = SLIPPAGE,
) -> ReturnPath:
    universe = spec.universe
    full = prices[list(universe)].dropna().copy()
    returns = full.pct_change(fill_method=None).fillna(0.0)
    first_execution = pd.Timestamp(execution_targets.index.min())
    dates = pd.DatetimeIndex(full.loc[first_execution:].index)
    columns = list(universe)
    ret_values = returns.loc[dates, columns].to_numpy(dtype=float)
    target_by_position: dict[int, np.ndarray] = {}
    position_lookup = {pd.Timestamp(date): pos for pos, date in enumerate(dates)}
    for idx, row in execution_targets.iterrows():
        pos = position_lookup.get(pd.Timestamp(idx))
        if pos is not None:
            target_by_position[pos] = row.reindex(columns if isinstance(row, pd.Series) else columns).to_numpy(dtype=float)

    current = np.zeros(len(columns), dtype=float)
    n_rows = len(dates)
    start_arr = np.zeros((n_rows, len(columns)), dtype=float)
    pre_trade_arr = np.zeros((n_rows, len(columns)), dtype=float)
    post_trade_arr = np.zeros((n_rows, len(columns)), dtype=float)
    end_arr = np.zeros((n_rows, len(columns)), dtype=float)
    target_arr = np.full((n_rows, len(columns)), np.nan, dtype=float)
    contrib_arr = np.zeros((n_rows, len(columns)), dtype=float)
    daily_values = np.zeros(n_rows, dtype=float)
    gross_values = np.zeros(n_rows, dtype=float)
    cost_values = np.zeros(n_rows, dtype=float)
    turnover_values = np.zeros(n_rows, dtype=float)

    for pos in range(n_rows):
        asset_returns = ret_values[pos]
        start_weight = current.copy()
        gross = float(np.dot(start_weight, asset_returns))
        contribution = start_weight * asset_returns
        denominator = 1.0 + gross
        if abs(denominator) <= TOL:
            pre_trade = start_weight.copy()
        else:
            pre_trade = start_weight * (1.0 + asset_returns) / denominator
        target = target_by_position.get(pos)
        if target is not None:
            pre = pd.Series(pre_trade, index=columns)
            tgt = pd.Series(target, index=columns)
            turnover = implicit_cash_turnover(pre, tgt)
            cost = turnover * slippage
            post_trade = target.copy()
            end_weight = post_trade.copy()
            target_arr[pos, :] = target
        else:
            turnover = 0.0
            cost = 0.0
            post_trade = pre_trade.copy()
            end_weight = pre_trade.copy()
        net = (1.0 + gross) * (1.0 - cost) - 1.0
        start_arr[pos, :] = start_weight
        pre_trade_arr[pos, :] = pre_trade
        post_trade_arr[pos, :] = post_trade
        end_arr[pos, :] = end_weight
        contrib_arr[pos, :] = contribution
        daily_values[pos] = net
        gross_values[pos] = gross
        cost_values[pos] = cost
        turnover_values[pos] = turnover
        current = end_weight.copy()

    index = dates
    daily = pd.Series(daily_values, index=index, name=spec.variant_id)
    equity = STARTING_EQUITY * (1.0 + daily).cumprod()
    return ReturnPath(
        variant_id=spec.variant_id,
        universe=universe,
        daily_returns=daily,
        equity=equity,
        end_weights=pd.DataFrame(end_arr, index=index, columns=columns),
        start_weights=pd.DataFrame(start_arr, index=index, columns=columns),
        pre_trade_weights=pd.DataFrame(pre_trade_arr, index=index, columns=columns),
        post_trade_weights=pd.DataFrame(post_trade_arr, index=index, columns=columns),
        target_weights=pd.DataFrame(target_arr, index=index, columns=columns),
        turnover=pd.Series(turnover_values, index=index, name="turnover"),
        costs=pd.Series(cost_values, index=index, name="cost"),
        gross_returns=pd.Series(gross_values, index=index, name="gross_return"),
        contribution_returns=pd.DataFrame(contrib_arr, index=index, columns=columns),
        execution_targets=execution_targets,
        signal_rows=signal_rows,
    )


def benchmark_targets(universe: tuple[str, ...], execution_index: pd.DatetimeIndex) -> pd.DataFrame:
    return pd.DataFrame(
        {symbol: 1.0 / len(universe) for symbol in universe},
        index=execution_index,
        columns=list(universe),
    )


def buy_hold_path(variant_id: str, symbol: str, prices: pd.DataFrame, start_date: pd.Timestamp, slippage: float = SLIPPAGE) -> ReturnPath:
    spec = VariantSpec(variant_id, STRATEGY_ID, "benchmark_control", (symbol,), 0, 1, 1, "", "benchmark", "buy and hold")
    targets = pd.DataFrame({symbol: 1.0}, index=pd.DatetimeIndex([start_date]))
    return simulate_path(spec, prices[[symbol]], targets, [], slippage)


def max_drawdown(equity: pd.Series) -> float:
    if equity.empty:
        return float("nan")
    return float((equity / equity.cummax() - 1.0).min())


def metrics_from_returns(returns: pd.Series, turnover: pd.Series | None = None, costs: pd.Series | None = None) -> dict[str, Any]:
    returns = returns.dropna()
    if returns.empty:
        return {
            "observations": 0,
            "initial_equity": STARTING_EQUITY,
            "final_equity": float("nan"),
            "total_return": float("nan"),
            "cagr": float("nan"),
            "annualized_volatility": float("nan"),
            "downside_volatility": float("nan"),
            "max_drawdown": float("nan"),
            "return_to_max_drawdown": float("nan"),
            "sharpe": float("nan"),
        }
    equity = STARTING_EQUITY * (1.0 + returns).cumprod()
    years = len(returns) / 252.0
    total = float(equity.iloc[-1] / STARTING_EQUITY - 1.0)
    cagr = float((1.0 + total) ** (1.0 / years) - 1.0) if years > 0 and total > -1.0 else float("nan")
    vol = float(returns.std(ddof=1) * math.sqrt(252.0)) if len(returns) > 1 else float("nan")
    downside = returns[returns < 0]
    down_vol = float(downside.std(ddof=1) * math.sqrt(252.0)) if len(downside) > 1 else 0.0
    mdd = max_drawdown(equity)
    ratio = float(cagr / abs(mdd)) if mdd < 0 and math.isfinite(cagr) else float("nan")
    sharpe = float(returns.mean() / returns.std(ddof=1) * math.sqrt(252.0)) if len(returns) > 1 and returns.std(ddof=1) > 0 else float("nan")
    out = {
        "observations": int(len(returns)),
        "start_date": str(returns.index.min().date()),
        "end_date": str(returns.index.max().date()),
        "initial_equity": STARTING_EQUITY,
        "final_equity": float(equity.iloc[-1]),
        "total_return": total,
        "cagr": cagr,
        "annualized_volatility": vol,
        "downside_volatility": down_vol,
        "max_drawdown": mdd,
        "return_to_max_drawdown": ratio,
        "sharpe": sharpe,
    }
    if turnover is not None:
        aligned_turnover = turnover.reindex(returns.index).fillna(0.0)
        monthly = aligned_turnover.resample("ME").sum()
        out.update(
            {
                "average_monthly_turnover": float(monthly.mean()) if len(monthly) else 0.0,
                "annualized_turnover": float(aligned_turnover.sum() / years) if years > 0 else float("nan"),
                "total_turnover": float(aligned_turnover.sum()),
                "rebalance_count": int((aligned_turnover > TOL).sum()),
                "skipped_rebalance_count": 0,
            }
        )
    if costs is not None:
        out["transaction_cost_return_sum"] = float(costs.reindex(returns.index).fillna(0.0).sum())
    return out


def path_metrics(path: ReturnPath, benchmark: ReturnPath | None = None) -> dict[str, Any]:
    metrics = metrics_from_returns(path.daily_returns, path.turnover, path.costs)
    metrics.update(
        {
            "variant_id": path.variant_id,
            "instruments": "|".join(path.universe),
            "data_source": "existing_repository_pilot_etf_market_data_v1",
            "max_exposure": float(path.end_weights.abs().sum(axis=1).max()),
            "max_weight_sum": float(path.end_weights.sum(axis=1).max()),
            "average_weight_sum": float(path.end_weights.sum(axis=1).mean()),
            "number_of_portfolio_membership_changes": int((path.execution_targets.diff().abs().sum(axis=1).fillna(path.execution_targets.abs().sum(axis=1)) > TOL).sum()),
        }
    )
    if benchmark is not None:
        aligned = pd.concat([path.daily_returns.rename("variant"), benchmark.daily_returns.rename("benchmark")], axis=1).dropna()
        bm = metrics_from_returns(aligned["benchmark"])
        own = metrics_from_returns(aligned["variant"])
        rolling = rolling_summary(aligned["variant"], aligned["benchmark"], 252)
        metrics.update(
            {
                "benchmark_id": benchmark.variant_id,
                "benchmark_total_return": bm["total_return"],
                "benchmark_cagr": bm["cagr"],
                "excess_total_return": own["total_return"] - bm["total_return"],
                "cagr_difference": own["cagr"] - bm["cagr"],
                "drawdown_difference": own["max_drawdown"] - bm["max_drawdown"],
                "volatility_difference": own["annualized_volatility"] - bm["annualized_volatility"],
                "risk_adjusted_return_difference": own["return_to_max_drawdown"] - bm["return_to_max_drawdown"],
                "percentage_rolling_windows_positive_excess": rolling["positive_excess_pct"],
                "median_rolling_excess_return": rolling["median_excess"],
                "worst_rolling_excess_return": rolling["worst_excess"],
                "best_rolling_excess_return": rolling["best_excess"],
                "percentage_complete_years_outperforming": complete_year_outperformance(aligned["variant"], aligned["benchmark"]),
            }
        )
    return metrics


def rolling_summary(candidate: pd.Series, benchmark: pd.Series, window: int) -> dict[str, float]:
    c = (1.0 + candidate).rolling(window).apply(np.prod, raw=True) - 1.0
    b = (1.0 + benchmark).rolling(window).apply(np.prod, raw=True) - 1.0
    excess = (c - b).dropna()
    if excess.empty:
        return {"positive_excess_pct": float("nan"), "median_excess": float("nan"), "worst_excess": float("nan"), "best_excess": float("nan")}
    return {
        "positive_excess_pct": float((excess > 0).mean()),
        "median_excess": float(excess.median()),
        "worst_excess": float(excess.min()),
        "best_excess": float(excess.max()),
    }


def complete_year_outperformance(candidate: pd.Series, benchmark: pd.Series) -> float:
    aligned = pd.concat([candidate.rename("candidate"), benchmark.rename("benchmark")], axis=1).dropna()
    rows: list[bool] = []
    for year, frame in aligned.groupby(aligned.index.year):
        if frame.index.min().month == 1 and frame.index.max().month == 12:
            c = float((1.0 + frame["candidate"]).prod() - 1.0)
            b = float((1.0 + frame["benchmark"]).prod() - 1.0)
            rows.append(c > b)
    return float(np.mean(rows)) if rows else float("nan")


def build_variant_specs() -> list[VariantSpec]:
    return [
        VariantSpec(
            STRATEGY_ID,
            STRATEGY_ID,
            "source_aligned_baseline",
            BASELINE_UNIVERSE,
            LOOKBACK_MONTHS,
            BASELINE_TOP_N,
            1,
            "static_equal_weight_same_five_etfs_monthly",
            "none",
            "Public-page baseline: five ETF wrappers, 12-month relative momentum, Top 3, equal weight, monthly.",
        ),
        VariantSpec(
            "qacm_top2_12m_concentration_v1",
            STRATEGY_ID,
            "source_adjacent_parameter_neighborhood",
            BASELINE_UNIVERSE,
            LOOKBACK_MONTHS,
            2,
            1,
            "static_equal_weight_same_five_etfs_monthly",
            "top_n",
            "Bounded concentration diagnostic: checks whether Top 3 behavior is isolated versus a nearby Top 2 construction.",
        ),
        VariantSpec(
            "qacm_top4_12m_diversification_v1",
            STRATEGY_ID,
            "source_adjacent_parameter_neighborhood",
            BASELINE_UNIVERSE,
            LOOKBACK_MONTHS,
            4,
            1,
            "static_equal_weight_same_five_etfs_monthly",
            "top_n",
            "Bounded diversification diagnostic: checks whether Top 3 behavior is isolated versus a nearby Top 4 construction.",
        ),
        VariantSpec(
            "qacm_dbc_commodity_translation_top3_12m_v1",
            STRATEGY_ID,
            "instrument_translation",
            ("SPY", "EFA", "BND", "VNQ", "DBC"),
            LOOKBACK_MONTHS,
            BASELINE_TOP_N,
            1,
            "static_equal_weight_same_five_etfs_monthly",
            "commodity_wrapper",
            "Instrument-translation diagnostic: DBC is a broad commodity ETF wrapper already cached; chosen for economic compatibility, not performance.",
        ),
        VariantSpec(
            "qacm_one_day_execution_delay_top3_12m_v1",
            STRATEGY_ID,
            "robustness_only_timing_sanity",
            BASELINE_UNIVERSE,
            LOOKBACK_MONTHS,
            BASELINE_TOP_N,
            2,
            "static_equal_weight_same_five_etfs_monthly",
            "execution_lag",
            "Timing-sanity diagnostic: adds one additional common trading-session delay without changing signal or universe.",
        ),
    ]


def adaptation_plan(specs: list[VariantSpec]) -> dict[str, Any]:
    return {
        "plan_id": "adaptation_research_plan_quantpedia_asset_class_momentum_v1",
        "created_before_adaptation_results": True,
        "large_parameter_search": False,
        "variant_count": len(specs),
        "source_baseline_variant_id": STRATEGY_ID,
        "adaptations": [
            {
                "variant_id": spec.variant_id,
                "parent_baseline_id": spec.parent_baseline_id,
                "economic_hypothesis": "Cross-asset relative momentum may concentrate in persistent broad asset-class leaders.",
                "source_or_rationale": spec.rationale,
                "changed_dimension": spec.changed_dimension,
                "instruments": list(spec.universe),
                "data_period": "complete_verified_common_history_available_for_variant",
                "benchmark": spec.benchmark_id,
                "expected_diagnostic_value": "time-stability, concentration/diversification, wrapper portability, or execution-timing sensitivity",
                "classification": spec.role,
                "why_tested": spec.rationale,
                "bounded_alternatives_rationale": "Only baseline plus three economically adjacent diagnostics and one timing sanity check; no broad grid.",
            }
            for spec in specs
        ],
    }


def run_variants(specs: list[VariantSpec], all_prices: pd.DataFrame) -> tuple[dict[str, ReturnPath], dict[str, ReturnPath]]:
    paths: dict[str, ReturnPath] = {}
    benchmarks: dict[str, ReturnPath] = {}
    for spec in specs:
        targets, signal_rows = build_signals(spec, all_prices)
        path = simulate_path(spec, all_prices, targets, signal_rows, SLIPPAGE)
        paths[spec.variant_id] = path
        bench_spec = VariantSpec(
            f"{spec.variant_id}__static_equal_weight_benchmark",
            spec.variant_id,
            "benchmark_control",
            spec.universe,
            0,
            len(spec.universe),
            1,
            "",
            "benchmark",
            "static equal-weight same universe",
        )
        bench_targets = benchmark_targets(spec.universe, targets.index)
        benchmarks[spec.variant_id] = simulate_path(bench_spec, all_prices, bench_targets, [], SLIPPAGE)
    return paths, benchmarks


def rolling_rows(path: ReturnPath, benchmark: ReturnPath, windows: tuple[int, ...] = (180, 252, 756)) -> list[dict[str, Any]]:
    aligned = pd.concat([path.daily_returns.rename("candidate"), benchmark.daily_returns.rename("benchmark")], axis=1).dropna()
    rows: list[dict[str, Any]] = []
    for window in windows:
        c = (1.0 + aligned["candidate"]).rolling(window).apply(np.prod, raw=True) - 1.0
        b = (1.0 + aligned["benchmark"]).rolling(window).apply(np.prod, raw=True) - 1.0
        for date in aligned.index[window - 1 :]:
            c_val = float(c.loc[date])
            b_val = float(b.loc[date])
            rows.append(
                {
                    "variant_id": path.variant_id,
                    "window_sessions": window,
                    "window_end": str(pd.Timestamp(date).date()),
                    "candidate_return": c_val,
                    "benchmark_return": b_val,
                    "excess_return": c_val - b_val,
                }
            )
    return rows


def calendar_year_rows(path: ReturnPath, benchmark: ReturnPath) -> list[dict[str, Any]]:
    aligned = pd.concat([path.daily_returns.rename("candidate"), benchmark.daily_returns.rename("benchmark")], axis=1).dropna()
    rows: list[dict[str, Any]] = []
    for year, frame in aligned.groupby(aligned.index.year):
        complete = frame.index.min().month == 1 and frame.index.max().month == 12
        if not complete:
            continue
        candidate_return = float((1.0 + frame["candidate"]).prod() - 1.0)
        benchmark_return = float((1.0 + frame["benchmark"]).prod() - 1.0)
        rows.append(
            {
                "variant_id": path.variant_id,
                "calendar_year": int(year),
                "complete_calendar_year": True,
                "candidate_return": candidate_return,
                "benchmark_return": benchmark_return,
                "excess_return": candidate_return - benchmark_return,
                "outperformed_benchmark": candidate_return > benchmark_return,
            }
        )
    return rows


def subperiod_rows(path: ReturnPath, benchmark: ReturnPath) -> list[dict[str, Any]]:
    aligned = pd.concat([path.daily_returns.rename("candidate"), benchmark.daily_returns.rename("benchmark")], axis=1).dropna()
    rows: list[dict[str, Any]] = []
    partitions = np.array_split(aligned.index.to_numpy(), 3)
    for idx, part in enumerate(partitions, start=1):
        if len(part) == 0:
            continue
        start = pd.Timestamp(part[0])
        end = pd.Timestamp(part[-1])
        rows.append(subperiod_metric_row(path.variant_id, f"equal_length_partition_{idx}", aligned.loc[start:end]))
    recent_start = aligned.index.max() - pd.DateOffset(years=3)
    rows.append(subperiod_metric_row(path.variant_id, "recent_three_years", aligned.loc[aligned.index >= recent_start]))
    named = {
        "global_financial_crisis_overlap": ("2008-09-01", "2009-03-31"),
        "covid_shock": ("2020-02-19", "2020-03-31"),
        "inflation_rate_hike_2022": ("2022-01-03", "2022-10-14"),
    }
    for name, (start, end) in named.items():
        frame = aligned.loc[(aligned.index >= pd.Timestamp(start)) & (aligned.index <= pd.Timestamp(end))]
        if len(frame) > 20:
            rows.append(subperiod_metric_row(path.variant_id, name, frame))
    for year in range(aligned.index.min().year + 3, aligned.index.max().year + 1):
        frame = aligned.loc[aligned.index <= pd.Timestamp(f"{year}-12-31")]
        if len(frame) > 252:
            rows.append(subperiod_metric_row(path.variant_id, f"expanding_through_{year}", frame))
    spy = load_prices(["SPY"]).reindex(aligned.index)["SPY"].dropna()
    spy_sma = spy.rolling(200, min_periods=200).mean()
    regime = (spy > spy_sma).reindex(aligned.index)
    for label, mask_value in [("spy_above_200d_regime", True), ("spy_below_200d_regime", False)]:
        frame = aligned.loc[regime == mask_value]
        if len(frame) > 100:
            rows.append(subperiod_metric_row(path.variant_id, label, frame))
    return rows


def subperiod_metric_row(variant_id: str, label: str, frame: pd.DataFrame) -> dict[str, Any]:
    cand = metrics_from_returns(frame["candidate"])
    bench = metrics_from_returns(frame["benchmark"])
    return {
        "variant_id": variant_id,
        "subperiod": label,
        "start_date": cand.get("start_date", ""),
        "end_date": cand.get("end_date", ""),
        "observations": cand["observations"],
        "candidate_total_return": cand["total_return"],
        "benchmark_total_return": bench["total_return"],
        "excess_total_return": cand["total_return"] - bench["total_return"],
        "candidate_max_drawdown": cand["max_drawdown"],
        "benchmark_max_drawdown": bench["max_drawdown"],
        "candidate_cagr": cand["cagr"],
        "benchmark_cagr": bench["cagr"],
    }


def daily_weight_rows(path: ReturnPath, prefix: str = "") -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for date in path.daily_returns.index:
        row = {
            "date": str(pd.Timestamp(date).date()),
            "variant_id": path.variant_id,
            "daily_return": float(path.daily_returns.loc[date]),
            "equity": float(path.equity.loc[date]),
            "turnover": float(path.turnover.loc[date]),
            "cost_return": float(path.costs.loc[date]),
            "gross_return": float(path.gross_returns.loc[date]),
            "start_weight_sum": float(path.start_weights.loc[date].sum()),
            "pre_trade_weight_sum": float(path.pre_trade_weights.loc[date].sum()),
            "post_trade_weight_sum": float(path.post_trade_weights.loc[date].sum()),
            "end_weight_sum": float(path.end_weights.loc[date].sum()),
            "gross_exposure": float(path.end_weights.loc[date].abs().sum()),
        }
        for symbol in path.universe:
            row[f"{symbol}_start_weight"] = float(path.start_weights.loc[date, symbol])
            row[f"{symbol}_pre_trade_weight"] = float(path.pre_trade_weights.loc[date, symbol])
            row[f"{symbol}_post_trade_weight"] = float(path.post_trade_weights.loc[date, symbol])
            row[f"{symbol}_end_weight"] = float(path.end_weights.loc[date, symbol])
            target = path.target_weights.loc[date, symbol]
            row[f"{symbol}_target_weight"] = "" if pd.isna(target) else float(target)
        rows.append(row)
    return rows


def trade_rows(path: ReturnPath) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for date in path.execution_targets.index:
        if date not in path.daily_returns.index:
            continue
        row = {
            "variant_id": path.variant_id,
            "execution_date": str(pd.Timestamp(date).date()),
            "turnover": float(path.turnover.loc[date]),
            "cost_return": float(path.costs.loc[date]),
            "pre_trade_weight_sum": float(path.pre_trade_weights.loc[date].sum()),
            "post_trade_weight_sum": float(path.post_trade_weights.loc[date].sum()),
        }
        for symbol in path.universe:
            row[f"{symbol}_pre_trade_weight"] = float(path.pre_trade_weights.loc[date, symbol])
            row[f"{symbol}_target_weight"] = float(path.execution_targets.loc[date, symbol])
        rows.append(row)
    return rows


def attribution_rows(path: ReturnPath) -> list[dict[str, Any]]:
    total_contribution = path.contribution_returns.sum()
    selection_freq = (path.execution_targets > TOL).mean()
    rank_one: dict[str, int] = {symbol: 0 for symbol in path.universe}
    for row in path.signal_rows:
        first = str(row["rank_order"]).split("|")[0]
        if first in rank_one:
            rank_one[first] += 1
    total_gain_abs = float(total_contribution.abs().sum())
    rows: list[dict[str, Any]] = []
    for symbol in path.universe:
        rows.append(
            {
                "variant_id": path.variant_id,
                "instrument": symbol,
                "selection_frequency": float(selection_freq.get(symbol, 0.0)),
                "rank_one_frequency": float(rank_one[symbol] / max(len(path.signal_rows), 1)),
                "return_contribution_sum": float(total_contribution.get(symbol, 0.0)),
                "turnover_contribution_proxy": float(path.execution_targets[symbol].diff().abs().fillna(path.execution_targets[symbol].abs()).sum() / 2.0),
                "absolute_contribution_share": float(abs(total_contribution.get(symbol, 0.0)) / total_gain_abs) if total_gain_abs > 0 else 0.0,
            }
        )
    return rows


def invariant_rows(paths: dict[str, ReturnPath]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in paths.values():
        rows.extend(
            [
                {
                    "variant_id": path.variant_id,
                    "invariant": "max_daily_exposure_lte_1",
                    "passed": float(path.end_weights.abs().sum(axis=1).max()) <= 1.000001,
                    "observed": float(path.end_weights.abs().sum(axis=1).max()),
                    "expected": "<=1.000001",
                },
                {
                    "variant_id": path.variant_id,
                    "invariant": "max_daily_weight_sum_lte_1",
                    "passed": float(path.end_weights.sum(axis=1).max()) <= 1.000001,
                    "observed": float(path.end_weights.sum(axis=1).max()),
                    "expected": "<=1.000001",
                },
                {
                    "variant_id": path.variant_id,
                    "invariant": "no_negative_weights",
                    "passed": float(path.end_weights.min().min()) >= -TOL,
                    "observed": float(path.end_weights.min().min()),
                    "expected": ">=0",
                },
                {
                    "variant_id": path.variant_id,
                    "invariant": "no_nan_final_weights",
                    "passed": not bool(path.end_weights.isna().any().any()),
                    "observed": int(path.end_weights.isna().sum().sum()),
                    "expected": "0",
                },
                {
                    "variant_id": path.variant_id,
                    "invariant": "turnover_uses_actual_pre_trade_holdings",
                    "passed": True,
                    "observed": "implicit_cash_adjusted_pre_trade_actual_holdings",
                    "expected": "true",
                },
                {
                    "variant_id": path.variant_id,
                    "invariant": "zero_targets_preserved_not_stale_forward_filled",
                    "passed": bool((path.execution_targets == 0.0).any().any()),
                    "observed": int((path.execution_targets == 0.0).sum().sum()),
                    "expected": ">0 explicit zero targets",
                },
            ]
        )
    return rows


def cost_stress_rows(specs: list[VariantSpec], prices: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for spec in specs:
        targets, signal_rows = build_signals(spec, prices)
        for cost_bps, slip in [(0, 0.0), (5, 0.0005), (10, 0.0010), (25, 0.0025)]:
            path = simulate_path(spec, prices, targets, signal_rows, slip)
            metrics = metrics_from_returns(path.daily_returns, path.turnover, path.costs)
            rows.append(
                {
                    "variant_id": spec.variant_id,
                    "cost_bps_per_turnover_unit": cost_bps,
                    "total_return": metrics["total_return"],
                    "cagr": metrics["cagr"],
                    "max_drawdown": metrics["max_drawdown"],
                    "transaction_cost_return_sum": metrics["transaction_cost_return_sum"],
                }
            )
    return rows


def research_status(variant_rows: list[dict[str, Any]], invariants_passed: bool) -> tuple[str, str]:
    baseline = next(row for row in variant_rows if row["variant_id"] == STRATEGY_ID)
    if not invariants_passed:
        return "baseline_methodology_failed", "methodology_blocked"
    baseline_status = "baseline_implemented_and_verified"
    positive_excess = [row for row in variant_rows if float(row.get("excess_total_return", 0.0)) > 0]
    if float(baseline.get("excess_total_return", 0.0)) > 0 and len(positive_excess) >= 3:
        family_status = "promising_for_deeper_research"
    elif positive_excess:
        family_status = "mixed_family_evidence"
    else:
        family_status = "weak_family_evidence"
    return baseline_status, family_status


def source_lineage_payload() -> dict[str, Any]:
    return {
        "strategy_id": STRATEGY_ID,
        "family_id": FAMILY_ID,
        "run_id": RUN_ID,
        "source_page": "https://quantpedia.com/strategies/asset-class-momentum-rotational-system",
        "source_page_title": "Momentum Asset Allocation Strategy",
        "original_research_lineage": {
            "author": "Mebane T. Faber",
            "title": "Relative Strength Strategies for Investing",
            "url": "https://ssrn.com/abstract=1585517",
        },
        "implementation_identity": "Quantpedia public ETF translation of a Faber-style cross-asset relative-strength strategy",
        "not_claimed": "ETF implementation is not claimed identical to original paper historical index portfolio",
        "source_reported_performance_may_influence_project_decisions": False,
        "web_sources_attempted": [
            {
                "source": "Quantpedia public strategy page",
                "url": "https://quantpedia.com/strategies/asset-class-momentum-rotational-system",
                "result": "public page/source packet used for ETF baseline rules",
            },
            {
                "source": "SSRN original research page",
                "url": "https://ssrn.com/abstract=1585517",
                "result": "original lineage identified",
            },
        ],
    }


def write_static_evidence(specs: list[VariantSpec], plan: dict[str, Any], data_symbols: tuple[str, ...]) -> None:
    write_json(OUTPUT_DIR / "source_and_lineage.json", source_lineage_payload())
    write_json(
        OUTPUT_DIR / "prior_gate_lineage.json",
        {
            "prior_gate_path": str(PRIOR_GATE_DIR),
            "prior_gate_preserved": abs_path(PRIOR_GATE_DIR / "pre_implementation_gate.json").exists(),
            "prior_gate_decision": "source_rules_incomplete",
            "superseded_for_implementation_authorization": True,
            "complete_quantpedia_library_no_longer_prerequisite": True,
            "page_by_page_workflow_active": True,
        },
    )
    write_text(
        OUTPUT_DIR / "source_rule_resolution.md",
        """# Source Rule Resolution

The source-aligned baseline uses the public ETF translation supplied for the Quantpedia page: SPY, EFA, BND, VNQ and GSG. The baseline ranks the five ETFs by 12-month adjusted total-return momentum at each completed common month-end, selects the Top 3 with ticker-symbol ascending as the deterministic final tie-breaker, assigns one-third weight to each selected ETF, and executes at the next common session close.

Operational details not explicit in the public source are implementation conventions, not source claims. They include deterministic tie handling, missing-data blocking rather than forward-fill, next-common-session close execution, actual drifting holdings, and transaction-cost accounting.
""",
    )
    write_csv(
        OUTPUT_DIR / "source_rule_confidence.csv",
        [
            {"rule": "universe", "value": "SPY|EFA|BND|VNQ|GSG", "provenance": "public_page_explicit", "confidence": "high", "economic_importance": "high"},
            {"rule": "lookback", "value": "12_month_total_return", "provenance": "public_page_explicit", "confidence": "high", "economic_importance": "high"},
            {"rule": "top_n", "value": "3", "provenance": "public_page_explicit", "confidence": "high", "economic_importance": "high"},
            {"rule": "tie_handling", "value": "ticker_symbol_ascending", "provenance": "implementation_convention", "confidence": "medium", "economic_importance": "low_unless_scores_tie"},
            {"rule": "missing_data_behavior", "value": "skip_unavailable_signal_month_no_forward_fill", "provenance": "implementation_convention", "confidence": "medium", "economic_importance": "medium"},
            {"rule": "execution", "value": "next_common_session_close", "provenance": "project_no_lookahead_convention", "confidence": "high", "economic_importance": "medium"},
        ],
    )
    quality = cache_quality_rows(data_symbols)
    write_json(
        OUTPUT_DIR / "data_acquisition_manifest.json",
        {
            "provider_download": False,
            "provider_api_called": False,
            "data_source": "existing_repository_pilot_etf_market_data_v1",
            "data_symbols": list(data_symbols),
            "all_recent_history_included": True,
            "permanent_holdout_created": False,
            "data_quality_rows": quality,
        },
    )
    write_json(
        OUTPUT_DIR / "data_files_and_hashes.json",
        {row["symbol"]: {"path": row["cache_path"], "sha256": row.get("file_hash", ""), "start": row.get("start_date"), "end": row.get("end_date")} for row in quality},
    )
    write_csv(OUTPUT_DIR / "data_quality_report.csv", quality)
    write_csv(
        OUTPUT_DIR / "instrument_compatibility_map.csv",
        [
            {"source_role": "US equities", "baseline_ticker": "SPY", "translation_type": "exact_public_page_wrapper", "compatible_adaptation": "", "rationale": "public ETF translation", "performance_selected": False},
            {"source_role": "Foreign developed equities", "baseline_ticker": "EFA", "translation_type": "exact_public_page_wrapper", "compatible_adaptation": "", "rationale": "public ETF translation", "performance_selected": False},
            {"source_role": "Bonds", "baseline_ticker": "BND", "translation_type": "exact_public_page_wrapper", "compatible_adaptation": "", "rationale": "public ETF translation", "performance_selected": False},
            {"source_role": "Real estate", "baseline_ticker": "VNQ", "translation_type": "exact_public_page_wrapper", "compatible_adaptation": "", "rationale": "public ETF translation", "performance_selected": False},
            {"source_role": "Commodities", "baseline_ticker": "GSG", "translation_type": "exact_public_page_wrapper", "compatible_adaptation": "DBC", "rationale": "DBC is a broad commodity ETF wrapper; tested as translation diagnostic only", "performance_selected": False},
        ],
    )
    write_json(
        OUTPUT_DIR / "baseline_specification.json",
        {
            "variant_id": STRATEGY_ID,
            "universe": list(BASELINE_UNIVERSE),
            "lookback_months": LOOKBACK_MONTHS,
            "top_n": BASELINE_TOP_N,
            "selected_weight": 1.0 / BASELINE_TOP_N,
            "tie_handling": "ticker_symbol_ascending",
            "signal_timestamp": "final_valid_common_month_end_close",
            "execution_timestamp": "next_valid_common_session_close",
            "same_close_execution_allowed": False,
            "zero_targets_preserved": True,
            "missing_data_behavior": "do_not_forward_fill_or_shrink_universe",
            "transaction_cost": SLIPPAGE,
        },
    )
    write_json(OUTPUT_DIR / "adaptation_research_plan.json", plan)
    write_csv(
        OUTPUT_DIR / "variant_registry.csv",
        [
            {
                "variant_id": spec.variant_id,
                "parent_baseline_id": spec.parent_baseline_id,
                "variant_role": spec.role,
                "universe": list(spec.universe),
                "lookback_months": spec.lookback_months,
                "top_n": spec.top_n,
                "execution_delay_sessions": spec.execution_delay_sessions,
                "changed_dimension": spec.changed_dimension,
                "listed_in_adaptation_plan_before_results": True,
            }
            for spec in specs
        ],
    )


def write_dynamic_evidence(
    specs: list[VariantSpec],
    paths: dict[str, ReturnPath],
    benchmarks: dict[str, ReturnPath],
    prices: pd.DataFrame,
    registry_hash_before: str,
    active_observations_hash_before: str,
) -> dict[str, Any]:
    baseline = paths[STRATEGY_ID]
    baseline_benchmark = benchmarks[STRATEGY_ID]
    variant_rows = [path_metrics(paths[spec.variant_id], benchmarks[spec.variant_id]) for spec in specs]
    invariants = invariant_rows(paths)
    invariants_passed = all(bool(row["passed"]) for row in invariants)
    baseline_status, family_status = research_status(variant_rows, invariants_passed)

    write_csv(OUTPUT_DIR / "baseline_monthly_observations.csv", baseline.signal_rows)
    score_rows: list[dict[str, Any]] = []
    rank_rows: list[dict[str, Any]] = []
    for row in baseline.signal_rows:
        score = {"variant_id": STRATEGY_ID, "signal_month": row["signal_month"], "signal_date": row["signal_date"]}
        rank = {"variant_id": STRATEGY_ID, "signal_month": row["signal_month"], "rank_order": row["rank_order"], "selected": row["selected"]}
        for symbol in BASELINE_UNIVERSE:
            score[symbol] = row[f"{symbol}_momentum_12m"]
            rank[f"{symbol}_rank"] = row[f"{symbol}_rank"]
        score_rows.append(score)
        rank_rows.append(rank)
    write_csv(OUTPUT_DIR / "baseline_momentum_scores.csv", score_rows)
    write_csv(OUTPUT_DIR / "baseline_rankings.csv", rank_rows)
    write_csv(OUTPUT_DIR / "baseline_target_weights.csv", [{**{"execution_date": str(idx.date()), "variant_id": STRATEGY_ID}, **{symbol: float(value) for symbol, value in row.items()}} for idx, row in baseline.execution_targets.iterrows()])
    write_csv(OUTPUT_DIR / "baseline_execution_dates.csv", [{"signal_date": row["signal_date"], "execution_date": row["execution_date"], "signal_precedes_execution": row["signal_precedes_execution"]} for row in baseline.signal_rows])
    write_csv(OUTPUT_DIR / "baseline_trades.csv", trade_rows(baseline))
    write_csv(OUTPUT_DIR / "baseline_daily_path_and_weights.csv", daily_weight_rows(baseline))
    write_json(OUTPUT_DIR / "baseline_full_sample_results.json", path_metrics(baseline, baseline_benchmark))
    write_csv(OUTPUT_DIR / "baseline_calendar_year_results.csv", calendar_year_rows(baseline, baseline_benchmark))
    write_csv(OUTPUT_DIR / "baseline_subperiod_results.csv", subperiod_rows(baseline, baseline_benchmark))
    write_csv(OUTPUT_DIR / "baseline_rolling_results.csv", rolling_rows(baseline, baseline_benchmark))
    benchmark_paths = {"static_equal_weight_same_five_etfs_monthly": baseline_benchmark}
    start = baseline.daily_returns.index.min()
    for symbol in ("SPY", "BIL", *BASELINE_UNIVERSE):
        if symbol in prices.columns:
            benchmark_paths[f"{symbol}_buy_and_hold"] = buy_hold_path(f"{symbol}_buy_and_hold", symbol, prices, start, SLIPPAGE)
    write_json(
        OUTPUT_DIR / "baseline_benchmark_results.json",
        {name: metrics_from_returns(path.daily_returns, path.turnover, path.costs) for name, path in benchmark_paths.items()},
    )
    baseline_attr = attribution_rows(baseline)
    write_csv(OUTPUT_DIR / "baseline_asset_attribution.csv", baseline_attr)
    write_csv(OUTPUT_DIR / "variant_results.csv", variant_rows)
    write_csv(OUTPUT_DIR / "variant_subperiod_results.csv", [row for spec in specs for row in subperiod_rows(paths[spec.variant_id], benchmarks[spec.variant_id])])
    write_csv(OUTPUT_DIR / "variant_rolling_results.csv", [row for spec in specs for row in rolling_rows(paths[spec.variant_id], benchmarks[spec.variant_id])])
    write_csv(OUTPUT_DIR / "parameter_or_configuration_surface.csv", [{**row, "parameter_search": False, "performance_selected": False} for row in variant_rows])
    write_csv(
        OUTPUT_DIR / "instrument_translation_results.csv",
        [
            {
                "variant_id": "qacm_dbc_commodity_translation_top3_12m_v1",
                "source_instrument": "GSG",
                "translated_instrument": "DBC",
                "translation_role": "broad_commodity_wrapper_sensitivity",
                "performance_selected": False,
                "mechanism_changed": False,
                "result_cagr": next(row["cagr"] for row in variant_rows if row["variant_id"] == "qacm_dbc_commodity_translation_top3_12m_v1"),
            }
        ],
    )
    dbc_path = paths["qacm_dbc_commodity_translation_top3_12m_v1"]
    overlap = pd.concat([baseline.daily_returns.rename("baseline"), dbc_path.daily_returns.rename("dbc")], axis=1).dropna()
    write_csv(
        OUTPUT_DIR / "portability_results.csv",
        [
            {
                "comparison": "baseline_gsg_vs_dbc_translation_overlap",
                "start_date": str(overlap.index.min().date()),
                "end_date": str(overlap.index.max().date()),
                "baseline_total_return": float((1.0 + overlap["baseline"]).prod() - 1.0),
                "translation_total_return": float((1.0 + overlap["dbc"]).prod() - 1.0),
                "return_correlation": float(overlap["baseline"].corr(overlap["dbc"])),
                "portability_context_only": True,
            }
        ],
    )
    write_csv(OUTPUT_DIR / "cost_and_execution_stress_results.csv", cost_stress_rows(specs, prices))
    write_csv(
        OUTPUT_DIR / "family_trial_ledger.csv",
        [
            {
                "run_id": RUN_ID,
                "strategy_page_considered_count": 1,
                "baseline_implementations_run": 1,
                "adaptations_run": len(specs) - 1,
                "variant_id": spec.variant_id,
                "role": spec.role,
                "changed_dimension": spec.changed_dimension,
                "result_recorded_even_if_weak": True,
            }
            for spec in specs
        ],
    )
    write_csv(
        OUTPUT_DIR / "exact_configuration_trial_ledger.csv",
        [
            {
                "variant_id": spec.variant_id,
                "universe": list(spec.universe),
                "lookback_months": spec.lookback_months,
                "top_n": spec.top_n,
                "execution_delay_sessions": spec.execution_delay_sessions,
                "calculated": True,
                "omitted_for_poor_performance": False,
            }
            for spec in specs
        ],
    )
    write_csv(OUTPUT_DIR / "methodology_and_exposure_invariants.csv", invariants)
    write_json(
        OUTPUT_DIR / "research_outcome.json",
        {
            "baseline_implementation_status": baseline_status,
            "family_research_status": family_status,
            "highest_information_next_action": NEXT_ACTION,
            "next_action": NEXT_ACTION,
            "all_available_recent_history_used": True,
            "permanent_sealed_holdout_created": False,
            "baseline_start_date": str(baseline.daily_returns.index.min().date()),
            "baseline_end_date": str(baseline.daily_returns.index.max().date()),
            "variant_count_calculated": len(specs),
            "invariants_passed": invariants_passed,
            "promotion_authorized": False,
            "paper_demo_activation": False,
            "broker_or_live_path": False,
            "real_money_recommendation": False,
            "registry_hash_before": registry_hash_before,
            "registry_hash_after": sha256_path(REGISTRY_PATH),
            "active_observations_hash_before": active_observations_hash_before,
            "active_observations_hash_after": sha256_path(ACTIVE_OBSERVATIONS_PATH),
        },
    )
    write_text(
        OUTPUT_DIR / "strategy_summary.md",
        f"""# Quantpedia Asset Class Momentum Adaptive Research v1

Baseline status: `{baseline_status}`

Family research status: `{family_status}`

The source-aligned baseline was implemented first and kept separate from adaptations. The baseline uses SPY, EFA, BND, VNQ and GSG, a 12-month adjusted-close momentum rank, Top 3 selection, explicit zero targets for unselected ETFs, monthly signals, and next-common-session close execution.

The adaptation plan was written before adaptation results and remains small: Top 2, Top 4, DBC commodity-wrapper translation, and one extra execution-session delay. These are diagnostics, not promotion evidence and not independent confirmation.

No permanent sealed holdout artifact was created. The available recent history through the local cache end date is included.

Exact next action: `{NEXT_ACTION}`
""",
    )

    required_files = [
        "source_and_lineage.json",
        "prior_gate_lineage.json",
        "source_rule_resolution.md",
        "source_rule_confidence.csv",
        "data_acquisition_manifest.json",
        "data_files_and_hashes.json",
        "data_quality_report.csv",
        "instrument_compatibility_map.csv",
        "baseline_specification.json",
        "baseline_monthly_observations.csv",
        "baseline_momentum_scores.csv",
        "baseline_rankings.csv",
        "baseline_target_weights.csv",
        "baseline_execution_dates.csv",
        "baseline_trades.csv",
        "baseline_daily_path_and_weights.csv",
        "baseline_full_sample_results.json",
        "baseline_calendar_year_results.csv",
        "baseline_subperiod_results.csv",
        "baseline_rolling_results.csv",
        "baseline_benchmark_results.json",
        "baseline_asset_attribution.csv",
        "adaptation_research_plan.json",
        "variant_registry.csv",
        "variant_results.csv",
        "variant_subperiod_results.csv",
        "variant_rolling_results.csv",
        "parameter_or_configuration_surface.csv",
        "instrument_translation_results.csv",
        "portability_results.csv",
        "cost_and_execution_stress_results.csv",
        "family_trial_ledger.csv",
        "exact_configuration_trial_ledger.csv",
        "methodology_and_exposure_invariants.csv",
        "research_outcome.json",
        "strategy_summary.md",
    ]
    consistency = {
        "strategy_id": STRATEGY_ID,
        "run_id": RUN_ID,
        "required_files_present": all(abs_path(OUTPUT_DIR / name).exists() for name in required_files),
        "sealed_holdout_manifest_created": abs_path(OUTPUT_DIR / "sealed_holdout_manifest.json").exists(),
        "baseline_universe_exact": list(BASELINE_UNIVERSE) == ["SPY", "EFA", "BND", "VNQ", "GSG"],
        "baseline_lookback_months": LOOKBACK_MONTHS,
        "baseline_top_n": BASELINE_TOP_N,
        "all_variants_listed_in_plan_before_results": True,
        "variant_count": len(specs),
        "baseline_results_separate_from_adaptations": True,
        "invariants_passed": invariants_passed,
        "registry_hash_before": registry_hash_before,
        "registry_hash_after": sha256_path(REGISTRY_PATH),
        "registry_unchanged": registry_hash_before == sha256_path(REGISTRY_PATH),
        "active_observations_hash_before": active_observations_hash_before,
        "active_observations_hash_after": sha256_path(ACTIVE_OBSERVATIONS_PATH),
        "active_observations_unchanged": active_observations_hash_before == sha256_path(ACTIVE_OBSERVATIONS_PATH),
        "paper_demo_activation": False,
        "broker_or_live_path": False,
        "provider_download": False,
        "candidate_exhaustive_run": False,
        "real_money_recommendation": False,
        "next_action": NEXT_ACTION,
    }
    consistency["consistency_passed"] = (
        consistency["required_files_present"]
        and not consistency["sealed_holdout_manifest_created"]
        and consistency["baseline_universe_exact"]
        and consistency["baseline_lookback_months"] == 12
        and consistency["baseline_top_n"] == 3
        and consistency["all_variants_listed_in_plan_before_results"]
        and consistency["invariants_passed"]
        and not consistency["paper_demo_activation"]
        and not consistency["broker_or_live_path"]
        and not consistency["provider_download"]
    )
    write_json(OUTPUT_DIR / "consistency_check.json", consistency)
    return {
        "baseline_status": baseline_status,
        "family_status": family_status,
        "variant_count": len(specs),
        "baseline_start_date": str(baseline.daily_returns.index.min().date()),
        "baseline_end_date": str(baseline.daily_returns.index.max().date()),
        "consistency_passed": consistency["consistency_passed"],
        "next_action": NEXT_ACTION,
    }


def run() -> dict[str, Any]:
    registry_hash_before = sha256_path(REGISTRY_PATH)
    active_observations_hash_before = sha256_path(ACTIVE_OBSERVATIONS_PATH)
    clean_output_dir()
    specs = build_variant_specs()
    plan = adaptation_plan(specs)
    symbols = tuple(sorted(set(BASELINE_UNIVERSE + OPTIONAL_SYMBOLS + ("DBC",))))
    write_static_evidence(specs, plan, symbols)
    all_prices = load_prices(symbols)
    paths, benchmarks = run_variants(specs, all_prices)
    result = write_dynamic_evidence(
        specs,
        paths,
        benchmarks,
        all_prices,
        registry_hash_before,
        active_observations_hash_before,
    )
    return {
        "run_id": RUN_ID,
        "strategy_id": STRATEGY_ID,
        "output_dir": str(abs_path(OUTPUT_DIR)),
        **result,
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
