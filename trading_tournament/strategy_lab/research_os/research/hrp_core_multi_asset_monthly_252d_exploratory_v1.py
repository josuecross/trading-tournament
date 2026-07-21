from __future__ import annotations

import csv
import hashlib
import json
import math
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

from src import hrp


ROOT = Path(__file__).resolve().parents[3]
ARTIFACT_ID = "hrp_core_multi_asset_monthly_252d_exploratory_v1"
OUTPUT_DIR = Path("reports") / "strategy_research" / ARTIFACT_ID
FEASIBILITY_DIR = Path("reports") / "strategy_research" / "hrp_engine_feasibility_v1"
DATA_DIR = Path("data") / "universe_expansion" / "pilot_etf_market_data_v1"

FROZEN_SYMBOLS: tuple[str, ...] = ("SPY", "EFA", "EEM", "IYR", "IEF", "TLT", "LQD", "HYG", "GLD", "DBC")
FROZEN_UNIVERSE_HASH = "d4ea7b0c0703581ec4e634b2432e603733beae2f286401a5130acade2e5a6e99"
LOOKBACK = 252
STARTING_NAV = 3000.0
TRADING_DAYS = 252
TOL = 1e-10

COST_LEVELS_BPS: tuple[int, ...] = (0, 5, 10)
METHODS: tuple[str, ...] = ("HRP", "HRP_IDENTITY", "EQUAL_WEIGHT_1N", "INVERSE_VARIANCE_252D")
PRIMARY_METHODS: tuple[str, ...] = ("HRP", "EQUAL_WEIGHT_1N", "INVERSE_VARIANCE_252D")
CONTROL_METHODS: tuple[str, ...] = ("EQUAL_WEIGHT_1N", "INVERSE_VARIANCE_252D")

STATIC_CLUSTERS: dict[str, tuple[str, ...]] = {
    "global_equity": ("SPY", "EFA", "EEM"),
    "real_estate": ("IYR",),
    "us_treasury": ("IEF", "TLT"),
    "credit": ("LQD", "HYG"),
    "real_assets": ("GLD", "DBC"),
}
ASSET_TO_CLUSTER = {symbol: cluster for cluster, symbols in STATIC_CLUSTERS.items() for symbol in symbols}

FAILURE_CODES = (
    "IDENTITY_EQUIVALENCE_FAILED",
    "INSUFFICIENT_COMMON_HISTORY",
    "NONFINITE_COVARIANCE",
    "NONFINITE_CORRELATION",
    "INVALID_CLUSTERING_RESULT",
    "NONDETERMINISTIC_CLUSTERING",
    "INVALID_HRP_WEIGHTS",
    "INVALID_CONTROL_WEIGHTS",
    "DYNAMIC_UNIVERSE_CHANGE",
    "NEXT_OPEN_UNAVAILABLE",
    "ACCOUNTING_RECONCILIATION_FAILED",
)


@dataclass(frozen=True)
class FrozenDates:
    common_start: pd.Timestamp
    common_end: pd.Timestamp
    first_signal_date: pd.Timestamp
    first_execution_date: pd.Timestamp
    evaluation_start: pd.Timestamp
    evaluation_end: pd.Timestamp
    signal_dates: tuple[pd.Timestamp, ...]
    execution_dates: tuple[pd.Timestamp, ...]
    blocks: tuple[dict[str, str], ...]


@dataclass(frozen=True)
class PriceData:
    open: pd.DataFrame
    close: pd.DataFrame
    raw_coverage: list[dict[str, Any]]
    common_dates: pd.DatetimeIndex
    file_hashes: dict[str, str]


@dataclass(frozen=True)
class MethodWeights:
    weights: dict[str, pd.DataFrame]
    hrp_diagnostics: list[dict[str, Any]]
    risk_rows: list[dict[str, Any]]
    rebalance_failures: list[dict[str, Any]]


@dataclass(frozen=True)
class TrialPath:
    method_id: str
    cost_bps_per_side: int
    daily_returns: pd.Series
    nav: pd.Series
    end_weights: pd.DataFrame
    pre_trade_weights: pd.DataFrame
    post_trade_weights: pd.DataFrame
    cost_return: pd.Series
    cost_dollars: pd.Series
    gross_traded_notional_pct: pd.Series
    one_way_turnover: pd.Series
    orders_count: pd.Series
    fills_count: pd.Series
    cash: pd.Series
    state_hash: str
    execution_dates: tuple[pd.Timestamp, ...]


def run(root: Path = ROOT) -> dict[str, Any]:
    output_dir = root / OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    prices = load_price_data(root)
    dates = freeze_evaluation_dates(prices)
    source_hashes = source_and_worktree_hashes(root, prices)
    trial_registry = registered_trials()
    frozen_universe = frozen_universe_payload()
    config = configuration_payload(dates)
    pre_registered = pre_registered_manifest(source_hashes, frozen_universe, prices, dates, config, trial_registry)

    write_json(output_dir / "source_and_worktree_hashes.json", source_hashes)
    write_json(output_dir / "frozen_universe.json", frozen_universe)
    write_csv(output_dir / "data_coverage.csv", prices.raw_coverage, data_coverage_fields())
    write_csv(output_dir / "trial_registry.csv", trial_registry, trial_registry_fields())
    write_json(output_dir / "pre_registered_manifest.json", pre_registered)

    method_weights = build_method_weights(prices, dates)
    paths: dict[tuple[str, int], TrialPath] = {}
    for cost_bps in COST_LEVELS_BPS:
        for method_id in METHODS:
            base_method = "HRP" if method_id == "HRP_IDENTITY" else method_id
            paths[(method_id, cost_bps)] = simulate_path(
                method_id=method_id,
                cost_bps_per_side=cost_bps,
                execution_weights=method_weights.weights[base_method],
                prices=prices,
                dates=dates,
            )

    identity_rows, identity_failures = identity_equivalence_rows(paths)
    failure_registry = list(method_weights.rebalance_failures) + identity_failures
    completed_registry = completed_trial_registry(trial_registry, paths, failure_registry)
    metrics_rows = build_metrics_rows(paths, dates)
    subperiod_rows = build_subperiod_metrics(paths, dates)
    monthly_weight_rows = build_monthly_weight_rows(method_weights.weights, dates)
    risk_rows = replicate_risk_rows_by_cost(method_weights.risk_rows)
    turnover_rows = build_turnover_rows(paths)
    concentration_rows = build_concentration_rows(paths)
    cluster_stability_rows = build_cluster_stability_rows(method_weights.hrp_diagnostics)
    classification, comparison_text = classify_and_compare(metrics_rows, subperiod_rows, concentration_rows, identity_rows, failure_registry, dates)

    write_csv(output_dir / "trial_registry.csv", completed_registry, trial_registry_fields())
    write_csv(output_dir / "identity_equivalence.csv", identity_rows, identity_equivalence_fields())
    write_csv(output_dir / "metrics.csv", metrics_rows, metrics_fields())
    write_csv(output_dir / "subperiod_metrics.csv", subperiod_rows, subperiod_metrics_fields())
    write_csv(output_dir / "monthly_weights.csv", monthly_weight_rows, monthly_weights_fields())
    write_jsonl(output_dir / "monthly_clusters.jsonl", method_weights.hrp_diagnostics)
    write_csv(output_dir / "risk_contributions.csv", risk_rows, risk_contribution_fields())
    write_csv(output_dir / "turnover_and_costs.csv", turnover_rows, turnover_fields())
    write_csv(output_dir / "concentration_diagnostics.csv", concentration_rows, concentration_fields())
    write_csv(output_dir / "cluster_stability.csv", cluster_stability_rows, cluster_stability_fields())
    write_csv(output_dir / "rebalance_failures.csv", method_weights.rebalance_failures, failure_fields())
    write_csv(output_dir / "failure_registry.csv", failure_registry, failure_fields())
    write_text(output_dir / "comparison.md", comparison_text)
    write_text(output_dir / "test_results.txt", "Test command output is recorded after the test run.\n")
    write_text(output_dir / "source_of_truth_update.md", source_of_truth_update(classification, dates))

    return {
        "artifact_dir": str(output_dir),
        "classification": classification,
        "dates": dates_payload(dates),
        "trial_count": len(trial_registry),
        "failure_count": len(failure_registry),
        "identity_equivalence_passed": all(row["equivalence_status"] == "PASS" for row in identity_rows),
        "metrics": metrics_rows,
    }


def load_price_data(root: Path = ROOT) -> PriceData:
    open_series: list[pd.Series] = []
    close_series: list[pd.Series] = []
    coverage: list[dict[str, Any]] = []
    hashes: dict[str, str] = {}
    for symbol in FROZEN_SYMBOLS:
        path = root / DATA_DIR / f"{symbol}.csv"
        if not path.exists():
            raise FileNotFoundError(path)
        file_hash = sha256_file(path)
        hashes[symbol] = file_hash
        frame = pd.read_csv(path)
        dates = pd.to_datetime(frame["date"], errors="coerce").dt.tz_localize(None)
        open_px = pd.to_numeric(frame["open"], errors="coerce")
        close_px = pd.to_numeric(frame["adj_close"], errors="coerce")
        clean = pd.DataFrame({"date": dates, "open": open_px, "adj_close": close_px}).dropna()
        clean = clean[(clean["open"] > 0.0) & (clean["adj_close"] > 0.0)].sort_values("date")
        clean = clean.drop_duplicates("date", keep="last")
        clean = clean.set_index("date")
        open_series.append(clean["open"].rename(symbol))
        close_series.append(clean["adj_close"].rename(symbol))
        coverage.append(
            {
                "symbol": symbol,
                "data_file": str((DATA_DIR / f"{symbol}.csv")).replace("\\", "/"),
                "sha256": file_hash,
                "first_valid_date": clean.index.min().date().isoformat(),
                "last_valid_date": clean.index.max().date().isoformat(),
                "valid_open_adjclose_rows": int(len(clean.index)),
                "duplicate_dates_after_cleaning": 0,
                "nonpositive_or_missing_rows_removed": int(len(frame.index) - len(clean.index)),
            }
        )
    open_frame = pd.concat(open_series, axis=1).sort_index()
    close_frame = pd.concat(close_series, axis=1).sort_index()
    common = open_frame.join(close_frame, how="inner", lsuffix="_open", rsuffix="_close").dropna()
    common_dates = pd.DatetimeIndex(common.index)
    return PriceData(
        open=open_frame.loc[common_dates, list(FROZEN_SYMBOLS)].astype(float),
        close=close_frame.loc[common_dates, list(FROZEN_SYMBOLS)].astype(float),
        raw_coverage=coverage,
        common_dates=common_dates,
        file_hashes=hashes,
    )


def freeze_evaluation_dates(prices: PriceData) -> FrozenDates:
    if tuple(prices.close.columns) != FROZEN_SYMBOLS or tuple(prices.open.columns) != FROZEN_SYMBOLS:
        raise ValueError("DYNAMIC_UNIVERSE_CHANGE")
    common_dates = prices.common_dates
    month_end_dates = tuple(pd.Timestamp(group.index[-1]) for _, group in prices.close.groupby(prices.close.index.to_period("M")))
    signal_dates: list[pd.Timestamp] = []
    execution_dates: list[pd.Timestamp] = []
    for signal_date in month_end_dates:
        signal_pos = common_dates.get_loc(signal_date)
        if signal_pos < LOOKBACK:
            continue
        if signal_pos + 1 >= len(common_dates):
            continue
        returns = common_returns(prices.close, signal_date)
        if len(returns.index) != LOOKBACK:
            continue
        signal_dates.append(signal_date)
        execution_dates.append(pd.Timestamp(common_dates[signal_pos + 1]))
    if not signal_dates:
        raise ValueError("INSUFFICIENT_COMMON_HISTORY")
    evaluation_start = execution_dates[0]
    evaluation_end = pd.Timestamp(common_dates[-1])
    return FrozenDates(
        common_start=pd.Timestamp(common_dates[0]),
        common_end=pd.Timestamp(common_dates[-1]),
        first_signal_date=signal_dates[0],
        first_execution_date=execution_dates[0],
        evaluation_start=evaluation_start,
        evaluation_end=evaluation_end,
        signal_dates=tuple(signal_dates),
        execution_dates=tuple(execution_dates),
        blocks=tuple(chronological_blocks(evaluation_start, evaluation_end)),
    )


def common_returns(close: pd.DataFrame, signal_date: pd.Timestamp) -> pd.DataFrame:
    returns = close.loc[:signal_date, list(FROZEN_SYMBOLS)].pct_change(fill_method=None).iloc[1:]
    window = returns.tail(LOOKBACK)
    if len(window.index) != LOOKBACK:
        raise ValueError("INSUFFICIENT_COMMON_HISTORY")
    if window.isna().any().any() or not np.isfinite(window.to_numpy(dtype=float)).all():
        raise ValueError("INSUFFICIENT_COMMON_HISTORY")
    return window


def chronological_blocks(start: pd.Timestamp, end: pd.Timestamp) -> list[dict[str, str]]:
    blocks: list[dict[str, str]] = []
    block_start = pd.Timestamp(start)
    block_id = 1
    while block_start <= end:
        next_start = block_start + pd.DateOffset(years=5)
        block_end = min(pd.Timestamp(end), next_start - pd.Timedelta(days=1))
        blocks.append(
            {
                "block_id": f"BLOCK_{block_id:02d}",
                "start_date": block_start.date().isoformat(),
                "end_date": block_end.date().isoformat(),
            }
        )
        block_start = next_start
        block_id += 1
    return blocks


def build_method_weights(prices: PriceData, dates: FrozenDates) -> MethodWeights:
    hrp_rows: list[dict[str, Any]] = []
    risk_rows: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    weight_frames = {method: pd.DataFrame(index=list(dates.execution_dates), columns=list(FROZEN_SYMBOLS), dtype=float) for method in PRIMARY_METHODS}

    for signal_date, execution_date in zip(dates.signal_dates, dates.execution_dates):
        returns = common_returns(prices.close, signal_date)
        try:
            hrp_result = hrp.hrp_weights_from_returns(returns, FROZEN_SYMBOLS)
            hrp_repeat = hrp.hrp_weights_from_returns(returns, FROZEN_SYMBOLS)
            if hrp_result.ordered_assets != hrp_repeat.ordered_assets or not np.allclose(hrp_result.weights, hrp_repeat.weights, atol=0.0, rtol=0.0):
                raise ValueError("NONDETERMINISTIC_CLUSTERING")
            validate_weights(hrp_result.weights, "INVALID_HRP_WEIGHTS")
        except Exception as exc:
            failures.append(failure_row(signal_date, execution_date, "HRP", failure_code_from_exception(exc), str(exc)))
            continue

        cov = hrp.sample_covariance(returns, FROZEN_SYMBOLS)
        equal = pd.Series(1.0 / len(FROZEN_SYMBOLS), index=list(FROZEN_SYMBOLS), dtype=float)
        inverse = hrp.inverse_variance_weights(cov).reindex(list(FROZEN_SYMBOLS))
        validate_weights(equal, "INVALID_CONTROL_WEIGHTS")
        validate_weights(inverse, "INVALID_CONTROL_WEIGHTS")
        weight_frames["HRP"].loc[execution_date] = hrp_result.weights.reindex(list(FROZEN_SYMBOLS))
        weight_frames["EQUAL_WEIGHT_1N"].loc[execution_date] = equal
        weight_frames["INVERSE_VARIANCE_252D"].loc[execution_date] = inverse

        hrp_rows.append(hrp_diagnostic_row(signal_date, execution_date, returns, hrp_result))
        for method_id, weights in (("HRP", hrp_result.weights), ("EQUAL_WEIGHT_1N", equal), ("INVERSE_VARIANCE_252D", inverse)):
            risk_rows.extend(risk_contribution_rows(method_id, signal_date, execution_date, cov, weights.reindex(list(FROZEN_SYMBOLS))))

    cleaned_frames: dict[str, pd.DataFrame] = {}
    for method_id, frame in weight_frames.items():
        if frame.isna().any().any():
            missing = frame[frame.isna().any(axis=1)]
            for execution_date in missing.index:
                failures.append(failure_row(pd.NaT, execution_date, method_id, "INVALID_CONTROL_WEIGHTS" if method_id != "HRP" else "INVALID_HRP_WEIGHTS", "missing target weights"))
            frame = frame.dropna()
        cleaned_frames[method_id] = frame.astype(float)
    return MethodWeights(weights=cleaned_frames, hrp_diagnostics=hrp_rows, risk_rows=risk_rows, rebalance_failures=failures)


def simulate_path(
    *,
    method_id: str,
    cost_bps_per_side: int,
    execution_weights: pd.DataFrame,
    prices: PriceData,
    dates: FrozenDates,
) -> TrialPath:
    cost_rate = float(cost_bps_per_side) / 10000.0
    eval_dates = pd.DatetimeIndex([date for date in prices.common_dates if dates.evaluation_start <= date <= dates.evaluation_end])
    close = prices.close.loc[:, list(FROZEN_SYMBOLS)]
    open_px = prices.open.loc[:, list(FROZEN_SYMBOLS)]
    execution_lookup = {pd.Timestamp(date): execution_weights.loc[date].astype(float) for date in execution_weights.index}
    current_weights = pd.Series(0.0, index=list(FROZEN_SYMBOLS), dtype=float)
    nav_previous_close = STARTING_NAV
    previous_close_date = prices.common_dates[prices.common_dates.get_loc(eval_dates[0]) - 1]

    returns_rows: list[float] = []
    nav_rows: list[float] = []
    end_weight_rows: list[pd.Series] = []
    pre_weight_rows: list[pd.Series] = []
    post_weight_rows: list[pd.Series] = []
    cost_return_rows: list[float] = []
    cost_dollar_rows: list[float] = []
    gross_trade_rows: list[float] = []
    one_way_rows: list[float] = []
    order_rows: list[int] = []
    fill_rows: list[int] = []
    cash_rows: list[float] = []

    for date in eval_dates:
        prev_close = close.loc[previous_close_date].astype(float)
        today_open = open_px.loc[date].astype(float)
        overnight_returns = today_open / prev_close - 1.0
        open_gross = float((current_weights * overnight_returns).sum())
        nav_open = nav_previous_close * (1.0 + open_gross)
        if abs(1.0 + open_gross) <= TOL:
            pre_trade = current_weights.copy()
        else:
            pre_trade = current_weights * (1.0 + overnight_returns) / (1.0 + open_gross)
        pre_trade = pre_trade.reindex(list(FROZEN_SYMBOLS)).fillna(0.0).astype(float)

        if date in execution_lookup:
            post_trade = execution_lookup[date].copy()
            validate_weights(post_trade, "INVALID_CONTROL_WEIGHTS")
            delta = post_trade - pre_trade
            gross_traded = float(delta.abs().sum())
            one_way = float(max(delta.clip(lower=0.0).sum(), (-delta.clip(upper=0.0)).sum()))
            orders = int((delta.abs() > 1e-8).sum())
            fills = orders
        else:
            post_trade = pre_trade.copy()
            gross_traded = 0.0
            one_way = 0.0
            orders = 0
            fills = 0

        cost_return = gross_traded * cost_rate
        nav_after_cost = nav_open * (1.0 - cost_return)
        cost_dollars = nav_open * cost_return
        intraday_returns = close.loc[date].astype(float) / today_open - 1.0
        intraday_gross = float((post_trade * intraday_returns).sum())
        nav_close = nav_after_cost * (1.0 + intraday_gross)
        daily_return = nav_close / nav_previous_close - 1.0
        denominator = 1.0 + intraday_gross
        if abs(denominator) <= TOL:
            end_weights = post_trade.copy()
        else:
            end_weights = post_trade * (1.0 + intraday_returns) / denominator
        end_weights = end_weights.reindex(list(FROZEN_SYMBOLS)).fillna(0.0).astype(float)
        validate_weights(end_weights, "ACCOUNTING_RECONCILIATION_FAILED", allow_small_drift=True)

        returns_rows.append(float(daily_return))
        nav_rows.append(float(nav_close))
        end_weight_rows.append(end_weights)
        pre_weight_rows.append(pre_trade)
        post_weight_rows.append(post_trade)
        cost_return_rows.append(float(cost_return))
        cost_dollar_rows.append(float(cost_dollars))
        gross_trade_rows.append(float(gross_traded))
        one_way_rows.append(float(one_way))
        order_rows.append(orders)
        fill_rows.append(fills)
        cash_rows.append(0.0)

        current_weights = end_weights
        nav_previous_close = nav_close
        previous_close_date = date

    daily_returns = pd.Series(returns_rows, index=eval_dates, name=method_id)
    nav = pd.Series(nav_rows, index=eval_dates, name=method_id)
    end_weights = pd.DataFrame(end_weight_rows, index=eval_dates, columns=list(FROZEN_SYMBOLS))
    pre_weights = pd.DataFrame(pre_weight_rows, index=eval_dates, columns=list(FROZEN_SYMBOLS))
    post_weights = pd.DataFrame(post_weight_rows, index=eval_dates, columns=list(FROZEN_SYMBOLS))
    cost_return = pd.Series(cost_return_rows, index=eval_dates)
    cost_dollars = pd.Series(cost_dollar_rows, index=eval_dates)
    gross_trade = pd.Series(gross_trade_rows, index=eval_dates)
    one_way_turnover = pd.Series(one_way_rows, index=eval_dates)
    orders_count = pd.Series(order_rows, index=eval_dates)
    fills_count = pd.Series(fill_rows, index=eval_dates)
    cash = pd.Series(cash_rows, index=eval_dates)
    state_hash = state_hash_payload(
        daily_returns=daily_returns,
        nav=nav,
        end_weights=end_weights,
        pre_weights=pre_weights,
        post_weights=post_weights,
        cost_return=cost_return,
        gross_trade=gross_trade,
        cash=cash,
    )
    return TrialPath(
        method_id=method_id,
        cost_bps_per_side=cost_bps_per_side,
        daily_returns=daily_returns,
        nav=nav,
        end_weights=end_weights,
        pre_trade_weights=pre_weights,
        post_trade_weights=post_weights,
        cost_return=cost_return,
        cost_dollars=cost_dollars,
        gross_traded_notional_pct=gross_trade,
        one_way_turnover=one_way_turnover,
        orders_count=orders_count,
        fills_count=fills_count,
        cash=cash,
        state_hash=state_hash,
        execution_dates=tuple(pd.Timestamp(date) for date in execution_weights.index),
    )


def validate_weights(weights: pd.Series, failure_code: str, *, allow_small_drift: bool = False) -> None:
    values = weights.reindex(list(FROZEN_SYMBOLS))
    if values.isna().any() or not np.isfinite(values.to_numpy(dtype=float)).all():
        raise ValueError(failure_code)
    if (values < -1e-8).any():
        raise ValueError(failure_code)
    tolerance = 1e-7 if allow_small_drift else 1e-9
    if abs(float(values.sum()) - 1.0) > tolerance:
        raise ValueError(failure_code)


def hrp_diagnostic_row(signal_date: pd.Timestamp, execution_date: pd.Timestamp, returns: pd.DataFrame, result: hrp.HRPResult) -> dict[str, Any]:
    return {
        "strategy_id": ARTIFACT_ID,
        "method_id": "HRP",
        "signal_date": signal_date.date().isoformat(),
        "execution_date": execution_date.date().isoformat(),
        "return_sample_start": returns.index[0].date().isoformat(),
        "return_sample_end": returns.index[-1].date().isoformat(),
        "return_sample_observations": int(len(returns.index)),
        "covariance_hash": stable_hash(frame_payload(result.covariance)),
        "correlation_hash": stable_hash(frame_payload(result.correlation)),
        "distance_matrix_hash": stable_hash(frame_payload(result.distance)),
        "linkage_result": result.linkage.to_dict("records"),
        "quasi_diagonal_asset_order": result.ordered_assets,
        "cluster_hierarchy": linkage_hierarchy(result.linkage),
        "cluster_variances": result.cluster_variances,
        "recursive_allocations": [allocation.__dict__ for allocation in result.recursive_allocations],
        "final_target_weights": series_payload(result.weights),
        "asset_risk_contributions": asset_risk_contributions(result.covariance, result.weights),
        "cluster_risk_contributions": cluster_risk_contributions(result.covariance, result.weights),
        "state_hash": stable_hash(
            {
                "linkage": result.linkage.to_dict("records"),
                "order": result.ordered_assets,
                "weights": series_payload(result.weights),
            }
        ),
    }


def risk_contribution_rows(
    method_id: str,
    signal_date: pd.Timestamp,
    execution_date: pd.Timestamp,
    covariance: pd.DataFrame,
    weights: pd.Series,
) -> list[dict[str, Any]]:
    asset_rc = asset_risk_contributions(covariance, weights)
    cluster_rc = cluster_risk_contributions(covariance, weights)
    cluster_weights = static_cluster_weights(weights)
    rows: list[dict[str, Any]] = []
    for symbol in FROZEN_SYMBOLS:
        cluster = ASSET_TO_CLUSTER[symbol]
        rows.append(
            {
                "method_id": method_id,
                "cost_bps_per_side": "",
                "signal_date": signal_date.date().isoformat(),
                "execution_date": execution_date.date().isoformat(),
                "asset": symbol,
                "static_cluster": cluster,
                "asset_weight": float(weights[symbol]),
                "asset_risk_contribution": float(asset_rc[symbol]),
                "cluster_weight": float(cluster_weights[cluster]),
                "cluster_risk_contribution": float(cluster_rc[cluster]),
            }
        )
    return rows


def asset_risk_contributions(covariance: pd.DataFrame, weights: pd.Series) -> dict[str, float]:
    w = weights.reindex(list(FROZEN_SYMBOLS)).astype(float)
    cov = covariance.loc[list(FROZEN_SYMBOLS), list(FROZEN_SYMBOLS)].astype(float)
    portfolio_variance = float(w.to_numpy() @ cov.to_numpy() @ w.to_numpy())
    if portfolio_variance <= TOL:
        return {symbol: 0.0 for symbol in FROZEN_SYMBOLS}
    marginal = cov.to_numpy() @ w.to_numpy()
    contributions = w.to_numpy() * marginal / portfolio_variance
    return {symbol: float(value) for symbol, value in zip(FROZEN_SYMBOLS, contributions)}


def cluster_risk_contributions(covariance: pd.DataFrame, weights: pd.Series) -> dict[str, float]:
    asset_rc = asset_risk_contributions(covariance, weights)
    return {cluster: float(sum(asset_rc[symbol] for symbol in symbols)) for cluster, symbols in STATIC_CLUSTERS.items()}


def static_cluster_weights(weights: pd.Series) -> dict[str, float]:
    return {cluster: float(weights.reindex(symbols).sum()) for cluster, symbols in STATIC_CLUSTERS.items()}


def linkage_hierarchy(linkage: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for idx, row in linkage.reset_index(drop=True).iterrows():
        rows.append(
            {
                "merge_step": int(idx + 1),
                "new_cluster_id": int(len(FROZEN_SYMBOLS) + idx),
                "left": int(row["left"]),
                "right": int(row["right"]),
                "distance": float(row["distance"]),
                "sample_count": int(row["sample_count"]),
            }
        )
    return rows


def build_metrics_rows(paths: dict[tuple[str, int], TrialPath], dates: FrozenDates) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    metrics_by_key: dict[tuple[str, int], dict[str, Any]] = {}
    for key, path in paths.items():
        metrics = performance_metrics(path, dates)
        rows.append(metrics)
        metrics_by_key[key] = metrics
    diff_fields = numeric_metric_names()
    for cost in COST_LEVELS_BPS:
        hrp_metrics = metrics_by_key[("HRP", cost)]
        for control in CONTROL_METHODS:
            control_metrics = metrics_by_key[(control, cost)]
            row: dict[str, Any] = {
                "row_type": "difference",
                "method_id": f"HRP_MINUS_{control}",
                "control_method_id": control,
                "cost_bps_per_side": cost,
                "initial_nav": 0.0,
                "terminal_nav": hrp_metrics["terminal_nav"] - control_metrics["terminal_nav"],
            }
            for field in diff_fields:
                row[field] = safe_float(hrp_metrics.get(field)) - safe_float(control_metrics.get(field))
            rows.append(row)
    return rows


def performance_metrics(path: TrialPath, dates: FrozenDates) -> dict[str, Any]:
    returns = path.daily_returns.dropna()
    nav = path.nav.reindex(returns.index)
    total_return = float(nav.iloc[-1] / STARTING_NAV - 1.0)
    years = len(returns.index) / TRADING_DAYS
    ann_return = float((nav.iloc[-1] / STARTING_NAV) ** (1.0 / years) - 1.0) if years > 0 else float("nan")
    ann_vol = float(returns.std(ddof=1) * math.sqrt(TRADING_DAYS)) if len(returns.index) > 1 else float("nan")
    sharpe = float(ann_return / ann_vol) if ann_vol > TOL else float("nan")
    downside = returns[returns < 0.0]
    downside_vol = float(downside.std(ddof=1) * math.sqrt(TRADING_DAYS)) if len(downside.index) > 1 else float("nan")
    sortino = float(ann_return / downside_vol) if downside_vol > TOL else float("nan")
    drawdowns = nav / nav.cummax() - 1.0
    max_dd = float(drawdowns.min())
    dd_duration = max_drawdown_duration(drawdowns)
    rtd = float(total_return / abs(max_dd)) if max_dd < -TOL else float("nan")
    weights = path.end_weights.reindex(returns.index).astype(float)
    cluster_weight_frame = cluster_weight_frame_from_weights(weights)
    eff_holdings = 1.0 / (weights.pow(2).sum(axis=1))
    monthly_changes = path.gross_traded_notional_pct[path.gross_traded_notional_pct > TOL]
    return {
        "row_type": "trial",
        "method_id": path.method_id,
        "control_method_id": "",
        "cost_bps_per_side": path.cost_bps_per_side,
        "start_date": dates.evaluation_start.date().isoformat(),
        "end_date": dates.evaluation_end.date().isoformat(),
        "observations": int(len(returns.index)),
        "initial_nav": STARTING_NAV,
        "terminal_nav": float(nav.iloc[-1]),
        "total_return": total_return,
        "annualized_return": ann_return,
        "annualized_volatility": ann_vol,
        "maximum_drawdown": max_dd,
        "drawdown_duration_days": dd_duration,
        "sharpe": sharpe,
        "sortino": sortino,
        "return_to_drawdown": rtd,
        "worst_daily_return": float(returns.min()),
        "expected_shortfall_95": expected_shortfall(returns, 0.95),
        "one_way_turnover": float(path.one_way_turnover.sum()),
        "gross_traded_notional": float(path.gross_traded_notional_pct.sum()),
        "orders": int(path.orders_count.sum()),
        "fills": int(path.fills_count.sum()),
        "modeled_transaction_costs": float(path.cost_dollars.sum()),
        "average_asset_weight": float(weights.mean(axis=1).mean()),
        "maximum_asset_weight": float(weights.max(axis=1).max()),
        "minimum_asset_weight": float(weights.min(axis=1).min()),
        "average_effective_holdings": float(eff_holdings.mean()),
        "minimum_effective_holdings": float(eff_holdings.min()),
        "average_cluster_weight": float(cluster_weight_frame.mean(axis=1).mean()),
        "maximum_cluster_weight": float(cluster_weight_frame.max(axis=1).max()),
        "average_monthly_weight_change": float(monthly_changes.mean()) if len(monthly_changes.index) else 0.0,
        "maximum_monthly_weight_change": float(monthly_changes.max()) if len(monthly_changes.index) else 0.0,
        "rebalance_failures": 0,
        "skipped_rebalance_dates": 0,
        "complete_state_hash": path.state_hash,
    }


def build_subperiod_metrics(paths: dict[tuple[str, int], TrialPath], dates: FrozenDates) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    lookup: dict[tuple[str, int, str], dict[str, Any]] = {}
    for block in dates.blocks:
        start = pd.Timestamp(block["start_date"])
        end = pd.Timestamp(block["end_date"])
        for key, path in paths.items():
            mask = (path.daily_returns.index >= start) & (path.daily_returns.index <= end)
            sub_returns = path.daily_returns.loc[mask]
            if sub_returns.empty:
                continue
            sub_nav = STARTING_NAV * (1.0 + sub_returns).cumprod()
            synthetic = TrialPath(
                method_id=path.method_id,
                cost_bps_per_side=path.cost_bps_per_side,
                daily_returns=sub_returns,
                nav=sub_nav,
                end_weights=path.end_weights.loc[sub_returns.index],
                pre_trade_weights=path.pre_trade_weights.loc[sub_returns.index],
                post_trade_weights=path.post_trade_weights.loc[sub_returns.index],
                cost_return=path.cost_return.loc[sub_returns.index],
                cost_dollars=path.cost_dollars.loc[sub_returns.index],
                gross_traded_notional_pct=path.gross_traded_notional_pct.loc[sub_returns.index],
                one_way_turnover=path.one_way_turnover.loc[sub_returns.index],
                orders_count=path.orders_count.loc[sub_returns.index],
                fills_count=path.fills_count.loc[sub_returns.index],
                cash=path.cash.loc[sub_returns.index],
                state_hash=stable_hash({"method": path.method_id, "cost": path.cost_bps_per_side, "block": block["block_id"]}),
                execution_dates=tuple(date for date in path.execution_dates if start <= date <= end),
            )
            row = performance_metrics(synthetic, FrozenDates(start, end, start, start, start, end, tuple(), tuple(), tuple()))
            row["block_id"] = block["block_id"]
            row["block_start_date"] = block["start_date"]
            row["block_end_date"] = block["end_date"]
            rows.append(row)
            lookup[(path.method_id, path.cost_bps_per_side, block["block_id"])] = row
    for block in dates.blocks:
        for cost in COST_LEVELS_BPS:
            hrp_row = lookup.get(("HRP", cost, block["block_id"]))
            if not hrp_row:
                continue
            for control in CONTROL_METHODS:
                control_row = lookup.get((control, cost, block["block_id"]))
                if not control_row:
                    continue
                diff: dict[str, Any] = {
                    "row_type": "difference",
                    "method_id": f"HRP_MINUS_{control}",
                    "control_method_id": control,
                    "cost_bps_per_side": cost,
                    "block_id": block["block_id"],
                    "block_start_date": block["start_date"],
                    "block_end_date": block["end_date"],
                }
                for field in numeric_metric_names():
                    diff[field] = safe_float(hrp_row.get(field)) - safe_float(control_row.get(field))
                rows.append(diff)
    return rows


def cluster_weight_frame_from_weights(weights: pd.DataFrame) -> pd.DataFrame:
    data = {}
    for cluster, symbols in STATIC_CLUSTERS.items():
        data[cluster] = weights.loc[:, list(symbols)].sum(axis=1)
    return pd.DataFrame(data, index=weights.index)


def max_drawdown_duration(drawdowns: pd.Series) -> int:
    duration = 0
    max_duration = 0
    for value in drawdowns:
        if value < -TOL:
            duration += 1
            max_duration = max(max_duration, duration)
        else:
            duration = 0
    return int(max_duration)


def expected_shortfall(returns: pd.Series, confidence: float) -> float:
    if returns.empty:
        return float("nan")
    cutoff_count = max(1, int(math.ceil((1.0 - confidence) * len(returns.index))))
    return float(returns.sort_values().iloc[:cutoff_count].mean())


def identity_equivalence_rows(paths: dict[tuple[str, int], TrialPath]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for cost in COST_LEVELS_BPS:
        hrp_path = paths[("HRP", cost)]
        identity_path = paths[("HRP_IDENTITY", cost)]
        checks = {
            "monthly_signals_equal": tuple(hrp_path.execution_dates) == tuple(identity_path.execution_dates),
            "target_weights_equal": frame_equal(
                hrp_path.post_trade_weights.loc[list(hrp_path.execution_dates)],
                identity_path.post_trade_weights.loc[list(identity_path.execution_dates)],
            ),
            "orders_and_fills_equal": series_equal(hrp_path.orders_count, identity_path.orders_count) and series_equal(hrp_path.fills_count, identity_path.fills_count),
            "daily_positions_equal": frame_equal(hrp_path.end_weights, identity_path.end_weights),
            "daily_cash_and_nav_equal": series_equal(hrp_path.cash, identity_path.cash) and series_equal(hrp_path.nav, identity_path.nav),
            "transaction_costs_equal": series_equal(hrp_path.cost_return, identity_path.cost_return) and series_equal(hrp_path.cost_dollars, identity_path.cost_dollars),
            "complete_state_hash_equal": hrp_path.state_hash == identity_path.state_hash,
            "final_metrics_equal": abs(float(hrp_path.nav.iloc[-1]) - float(identity_path.nav.iloc[-1])) <= TOL,
        }
        passed = all(checks.values())
        row = {
            "cost_bps_per_side": cost,
            **checks,
            "hrp_state_hash": hrp_path.state_hash,
            "identity_state_hash": identity_path.state_hash,
            "equivalence_status": "PASS" if passed else "FAIL",
        }
        rows.append(row)
        if not passed:
            failures.append(failure_row(pd.NaT, pd.NaT, "HRP_IDENTITY", "IDENTITY_EQUIVALENCE_FAILED", json.dumps(checks, sort_keys=True)))
    return rows, failures


def build_monthly_weight_rows(weights: dict[str, pd.DataFrame], dates: FrozenDates) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    signal_by_execution = dict(zip(dates.execution_dates, dates.signal_dates))
    for method_id in METHODS:
        base = "HRP" if method_id == "HRP_IDENTITY" else method_id
        frame = weights[base]
        for execution_date, row in frame.iterrows():
            out = {
                "method_id": method_id,
                "signal_date": signal_by_execution[pd.Timestamp(execution_date)].date().isoformat(),
                "execution_date": pd.Timestamp(execution_date).date().isoformat(),
                "weight_sum": float(row.sum()),
                "min_weight": float(row.min()),
                "max_weight": float(row.max()),
                "effective_holdings": float(1.0 / row.pow(2).sum()),
            }
            for symbol in FROZEN_SYMBOLS:
                out[symbol] = float(row[symbol])
            rows.append(out)
    return rows


def replicate_risk_rows_by_cost(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for cost in COST_LEVELS_BPS:
        for row in rows:
            output.append({**row, "cost_bps_per_side": cost})
        for row in [item for item in rows if item["method_id"] == "HRP"]:
            output.append({**row, "method_id": "HRP_IDENTITY", "cost_bps_per_side": cost})
    return output


def build_turnover_rows(paths: dict[tuple[str, int], TrialPath]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in paths.values():
        execution_set = set(path.execution_dates)
        for date in path.daily_returns.index:
            rows.append(
                {
                    "method_id": path.method_id,
                    "cost_bps_per_side": path.cost_bps_per_side,
                    "date": date.date().isoformat(),
                    "is_execution_date": date in execution_set,
                    "gross_traded_notional_pct": float(path.gross_traded_notional_pct.loc[date]),
                    "one_way_turnover": float(path.one_way_turnover.loc[date]),
                    "transaction_cost_return": float(path.cost_return.loc[date]),
                    "transaction_cost_dollars": float(path.cost_dollars.loc[date]),
                    "orders": int(path.orders_count.loc[date]),
                    "fills": int(path.fills_count.loc[date]),
                    "nav": float(path.nav.loc[date]),
                    "cash": float(path.cash.loc[date]),
                }
            )
    return rows


def build_concentration_rows(paths: dict[tuple[str, int], TrialPath]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in paths.values():
        weights = path.end_weights
        cluster_weights = cluster_weight_frame_from_weights(weights)
        avg_asset = weights.mean(axis=0)
        max_asset = weights.max(axis=0)
        avg_cluster = cluster_weights.mean(axis=0)
        max_cluster = cluster_weights.max(axis=0)
        rows.append(
            {
                "method_id": path.method_id,
                "cost_bps_per_side": path.cost_bps_per_side,
                "top_average_asset": str(avg_asset.idxmax()),
                "top_average_asset_weight": float(avg_asset.max()),
                "top_max_asset": str(max_asset.idxmax()),
                "top_max_asset_weight": float(max_asset.max()),
                "top_average_cluster": str(avg_cluster.idxmax()),
                "top_average_cluster_weight": float(avg_cluster.max()),
                "top_max_cluster": str(max_cluster.idxmax()),
                "top_max_cluster_weight": float(max_cluster.max()),
                "average_effective_holdings": float((1.0 / weights.pow(2).sum(axis=1)).mean()),
                "one_asset_avg_gt_50pct": bool(avg_asset.max() > 0.50),
                "one_cluster_avg_gt_70pct": bool(avg_cluster.max() > 0.70),
            }
        )
    return rows


def build_cluster_stability_rows(hrp_diagnostics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    previous_signature = ""
    changes = 0
    for idx, item in enumerate(hrp_diagnostics, start=1):
        signature = stable_hash({"linkage": item["linkage_result"], "order": item["quasi_diagonal_asset_order"]})
        changed = idx > 1 and signature != previous_signature
        if changed:
            changes += 1
        rows.append(
            {
                "method_id": "HRP",
                "signal_date": item["signal_date"],
                "execution_date": item["execution_date"],
                "cluster_signature_hash": signature,
                "changed_from_previous": changed,
                "cumulative_cluster_membership_changes": changes,
                "cluster_stability_to_date": 1.0 - (changes / max(1, idx - 1)) if idx > 1 else 1.0,
            }
        )
        previous_signature = signature
    return rows


def classify_and_compare(
    metrics_rows: list[dict[str, Any]],
    subperiod_rows: list[dict[str, Any]],
    concentration_rows: list[dict[str, Any]],
    identity_rows: list[dict[str, Any]],
    failures: list[dict[str, Any]],
    dates: FrozenDates,
) -> tuple[str, str]:
    if failures or any(row["equivalence_status"] != "PASS" for row in identity_rows):
        classification = "DATA_OR_IMPLEMENTATION_INVALID"
    else:
        metric_lookup = {(row.get("method_id"), int(row.get("cost_bps_per_side", -1))): row for row in metrics_rows if row.get("row_type") == "trial"}
        concentration_lookup = {(row["method_id"], int(row["cost_bps_per_side"])): row for row in concentration_rows}
        hrp_5 = metric_lookup[("HRP", 5)]
        hrp_10 = metric_lookup[("HRP", 10)]
        concentrated = any(
            concentration_lookup[("HRP", cost)]["one_asset_avg_gt_50pct"] or concentration_lookup[("HRP", cost)]["one_cluster_avg_gt_70pct"]
            for cost in (5, 10)
        )
        if concentrated:
            classification = "CONCENTRATED"
        else:
            improvements = {control: 0 for control in CONTROL_METHODS}
            for cost, hrp_metric in ((5, hrp_5), (10, hrp_10)):
                for control in CONTROL_METHODS:
                    control_metric = metric_lookup[(control, cost)]
                    improvements[control] += downside_diversification_improvement_count(hrp_metric, control_metric)
            beats_equal = improvements["EQUAL_WEIGHT_1N"] >= 4
            beats_inverse = improvements["INVERSE_VARIANCE_252D"] >= 4
            zero_edge = downside_diversification_improvement_count(metric_lookup[("HRP", 0)], metric_lookup[("INVERSE_VARIANCE_252D", 0)]) >= 2
            cost_edge = beats_inverse
            if zero_edge and not cost_edge:
                classification = "COST_DOMINATED"
            elif beats_equal and not beats_inverse:
                classification = "CONTROL_WEAK"
            elif beats_equal and beats_inverse and evidence_in_multiple_blocks(subperiod_rows):
                return_damage = min(
                    hrp_5["annualized_return"] - metric_lookup[("EQUAL_WEIGHT_1N", 5)]["annualized_return"],
                    hrp_5["annualized_return"] - metric_lookup[("INVERSE_VARIANCE_252D", 5)]["annualized_return"],
                    hrp_10["annualized_return"] - metric_lookup[("EQUAL_WEIGHT_1N", 10)]["annualized_return"],
                    hrp_10["annualized_return"] - metric_lookup[("INVERSE_VARIANCE_252D", 10)]["annualized_return"],
                )
                classification = "WORTH_DEEPER_RESEARCH" if return_damage > -0.03 else "NO_MATERIAL_EDGE"
            elif not beats_equal and not beats_inverse:
                classification = "BENCHMARK_DOMINATED"
            else:
                classification = "NO_MATERIAL_EDGE"

    trial_metrics = [row for row in metrics_rows if row.get("row_type") == "trial" and row["method_id"] in PRIMARY_METHODS]
    lines = [
        f"# {ARTIFACT_ID} Comparison",
        "",
        f"Frozen evaluation range: `{dates.evaluation_start.date().isoformat()}` to `{dates.evaluation_end.date().isoformat()}`.",
        f"Final exploratory classification: `{classification}`.",
        "",
        "## Trial Metrics",
        "",
        "| method | bps | total return | ann return | ann vol | max DD | Sharpe | ES95 | turnover | top asset weight | top cluster weight |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    conc_lookup = {(row["method_id"], int(row["cost_bps_per_side"])): row for row in concentration_rows}
    for row in trial_metrics:
        conc = conc_lookup[(row["method_id"], int(row["cost_bps_per_side"]))]
        lines.append(
            f"| {row['method_id']} | {row['cost_bps_per_side']} | {row['total_return']:.4f} | {row['annualized_return']:.4f} | "
            f"{row['annualized_volatility']:.4f} | {row['maximum_drawdown']:.4f} | {row['sharpe']:.4f} | "
            f"{row['expected_shortfall_95']:.4f} | {row['gross_traded_notional']:.4f} | "
            f"{conc['top_average_asset_weight']:.4f} | {conc['top_average_cluster_weight']:.4f} |"
        )
    lines.extend(
        [
            "",
            "## Scope",
            "",
            "- Exactly 12 registered runs were executed.",
            "- HRP and Identity complete-state equality is required at each cost level.",
            "- No optional management overlay, parameter search, universe replacement, validation, promotion, or execution-connected path was invoked.",
        ]
    )
    return classification, "\n".join(lines) + "\n"


def downside_diversification_improvement_count(hrp_metric: dict[str, Any], control_metric: dict[str, Any]) -> int:
    count = 0
    if safe_float(hrp_metric["maximum_drawdown"]) > safe_float(control_metric["maximum_drawdown"]):
        count += 1
    if safe_float(hrp_metric["annualized_volatility"]) < safe_float(control_metric["annualized_volatility"]):
        count += 1
    if safe_float(hrp_metric["expected_shortfall_95"]) > safe_float(control_metric["expected_shortfall_95"]):
        count += 1
    if safe_float(hrp_metric["maximum_asset_weight"]) < safe_float(control_metric["maximum_asset_weight"]):
        count += 1
    if safe_float(hrp_metric["maximum_cluster_weight"]) < safe_float(control_metric["maximum_cluster_weight"]):
        count += 1
    if safe_float(hrp_metric["average_effective_holdings"]) > safe_float(control_metric["average_effective_holdings"]):
        count += 1
    return count


def evidence_in_multiple_blocks(subperiod_rows: list[dict[str, Any]]) -> bool:
    diff_rows = [
        row for row in subperiod_rows
        if row.get("row_type") == "difference"
        and row.get("method_id") in {"HRP_MINUS_EQUAL_WEIGHT_1N", "HRP_MINUS_INVERSE_VARIANCE_252D"}
        and int(row.get("cost_bps_per_side", -1)) in {5, 10}
    ]
    good_blocks = {
        row["block_id"]
        for row in diff_rows
        if safe_float(row.get("maximum_drawdown")) >= 0.0 or safe_float(row.get("annualized_volatility")) < 0.0
    }
    return len(good_blocks) >= 2


def registered_trials() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    trial_number = 1
    for method_id in METHODS:
        for cost in COST_LEVELS_BPS:
            rows.append(
                {
                    "trial_id": f"{ARTIFACT_ID}__{method_id}__{cost}bps",
                    "trial_number": trial_number,
                    "method_id": method_id,
                    "cost_bps_per_side": cost,
                    "portfolio_rule": "HRP source rules" if method_id in {"HRP", "HRP_IDENTITY"} else method_id,
                    "registered_before_performance": True,
                    "status": "REGISTERED",
                    "execution_status": "",
                    "complete_state_hash": "",
                    "terminal_nav": "",
                    "observations": "",
                    "failure_code": "",
                }
            )
            trial_number += 1
    return rows


def completed_trial_registry(
    registered: list[dict[str, Any]],
    paths: dict[tuple[str, int], TrialPath],
    failures: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    failure_by_method = {(row["method_id"], row["failure_code"]) for row in failures}
    rows: list[dict[str, Any]] = []
    for row in registered:
        method_id = str(row["method_id"])
        cost = int(row["cost_bps_per_side"])
        path = paths.get((method_id, cost))
        failed = [code for method, code in failure_by_method if method == method_id]
        out = dict(row)
        if path is None or failed:
            out.update(
                {
                    "status": "FAILED",
                    "execution_status": "FAILED",
                    "complete_state_hash": "",
                    "terminal_nav": "",
                    "observations": "",
                    "failure_code": ";".join(sorted(failed)) if failed else "ACCOUNTING_RECONCILIATION_FAILED",
                }
            )
        else:
            out.update(
                {
                    "status": "COMPLETED",
                    "execution_status": "COMPLETED",
                    "complete_state_hash": path.state_hash,
                    "terminal_nav": float(path.nav.iloc[-1]),
                    "observations": int(len(path.daily_returns.index)),
                    "failure_code": "",
                }
            )
        rows.append(out)
    return rows


def source_and_worktree_hashes(root: Path, prices: PriceData) -> dict[str, Any]:
    head = git_capture(root, ["rev-parse", "HEAD"])
    status = git_capture(root, ["status", "--short"])
    diff = git_capture(root, ["diff", "--binary"])
    untracked = "\n".join(line for line in status.splitlines() if line.startswith("??"))
    runner_path = root / "strategy_lab" / "research_os" / "research" / "hrp_core_multi_asset_monthly_252d_exploratory_v1.py"
    wrapper_path = root / "run_hrp_core_multi_asset_monthly_252d_exploratory_v1.py"
    return {
        "created_utc": datetime.now(UTC).isoformat(),
        "repository_head": head,
        "dirty_worktree_status": status,
        "dirty_worktree_status_hash": stable_hash(status),
        "tracked_diff_hash": stable_hash(diff),
        "untracked_status_hash": stable_hash(untracked),
        "hrp_source_path": "src/hrp.py",
        "hrp_source_sha256": sha256_file(root / "src" / "hrp.py"),
        "runner_source_path": str(runner_path.relative_to(root)).replace("\\", "/"),
        "runner_source_sha256": sha256_file(runner_path),
        "wrapper_source_path": str(wrapper_path.relative_to(root)).replace("\\", "/") if wrapper_path.exists() else "",
        "wrapper_source_sha256": sha256_file(wrapper_path) if wrapper_path.exists() else "",
        "configuration_hash": stable_hash({"symbols": FROZEN_SYMBOLS, "lookback": LOOKBACK, "cost_bps": COST_LEVELS_BPS, "methods": METHODS}),
        "data_hashes": prices.file_hashes,
        "feasibility_package_path": str(FEASIBILITY_DIR).replace("\\", "/"),
        "feasibility_package_preserved": True,
    }


def git_capture(root: Path, args: list[str]) -> str:
    try:
        completed = subprocess.run(["git", *args], cwd=root, check=False, capture_output=True, text=True)
    except OSError:
        return ""
    return completed.stdout.strip()


def frozen_universe_payload() -> dict[str, Any]:
    return {
        "strategy_id": ARTIFACT_ID,
        "symbols": list(FROZEN_SYMBOLS),
        "frozen_universe_hash": FROZEN_UNIVERSE_HASH,
        "reserve_instruments_forbidden": ["IVV", "VOO", "VEA", "VWO", "IAU", "GSG"],
        "static_clusters": STATIC_CLUSTERS,
        "dynamic_universe_changes_allowed": False,
    }


def configuration_payload(dates: FrozenDates) -> dict[str, Any]:
    return {
        "return_frequency": "daily",
        "lookback": LOOKBACK,
        "covariance_estimator": "ordinary_sample_covariance",
        "correlation_estimator": "ordinary_pearson",
        "distance": "sqrt((1 - correlation) / 2)",
        "linkage": "deterministic_single_linkage",
        "allocation": "quasi_diagonalization_plus_recursive_bisection",
        "cluster_variance": "inverse_variance_cluster_portfolio_variance",
        "rebalance_frequency": "calendar_month_end",
        "signal_time": "month_end_close",
        "execution_time": "next_valid_open",
        "long_only": True,
        "fully_invested": True,
        "leverage": False,
        "cash_filter": "none",
        "optional_management_overlays": 0,
        "cost_bps_per_side": list(COST_LEVELS_BPS),
        "initial_nav": STARTING_NAV,
        "registered_trial_count": len(METHODS) * len(COST_LEVELS_BPS),
        "chronological_blocks": list(dates.blocks),
    }


def pre_registered_manifest(
    hashes: dict[str, Any],
    universe: dict[str, Any],
    prices: PriceData,
    dates: FrozenDates,
    config: dict[str, Any],
    trials: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "artifact_id": ARTIFACT_ID,
        "created_utc": datetime.now(UTC).isoformat(),
        "source_and_worktree_hashes": hashes,
        "frozen_universe": universe,
        "data_coverage": prices.raw_coverage,
        "common_price_period": {
            "common_start": dates.common_start.date().isoformat(),
            "common_end": dates.common_end.date().isoformat(),
            "evaluation_start": dates.evaluation_start.date().isoformat(),
            "evaluation_end": dates.evaluation_end.date().isoformat(),
            "first_signal_date": dates.first_signal_date.date().isoformat(),
            "first_execution_date": dates.first_execution_date.date().isoformat(),
            "signal_count": len(dates.signal_dates),
            "execution_count": len(dates.execution_dates),
        },
        "rules": config,
        "required_control_portfolios": list(CONTROL_METHODS),
        "registered_trials": trials,
        "trial_count": len(trials),
        "chronological_diagnostic_blocks": list(dates.blocks),
        "classification_labels": [
            "WORTH_DEEPER_RESEARCH",
            "CONTROL_WEAK",
            "NO_MATERIAL_EDGE",
            "COST_DOMINATED",
            "BENCHMARK_DOMINATED",
            "CONCENTRATED",
            "DATA_OR_IMPLEMENTATION_INVALID",
        ],
        "advancement_rule": "exploratory only; no validation, promotion, or paper/demo eligibility",
        "performance_calculated_after_this_manifest": True,
    }


def failure_code_from_exception(exc: Exception) -> str:
    text = str(exc)
    for code in FAILURE_CODES:
        if code in text:
            return code
    if isinstance(exc, hrp.HRPDataError):
        return "INVALID_HRP_WEIGHTS"
    return "INVALID_CLUSTERING_RESULT"


def failure_row(signal_date: pd.Timestamp | pd.NaT, execution_date: pd.Timestamp | pd.NaT, method_id: str, code: str, reason: str) -> dict[str, Any]:
    return {
        "method_id": method_id,
        "signal_date": "" if pd.isna(signal_date) else pd.Timestamp(signal_date).date().isoformat(),
        "execution_date": "" if pd.isna(execution_date) else pd.Timestamp(execution_date).date().isoformat(),
        "failure_code": code,
        "failure_reason": reason,
    }


def state_hash_payload(**frames: Any) -> str:
    payload: dict[str, Any] = {}
    for name, value in frames.items():
        if isinstance(value, pd.DataFrame):
            payload[name] = frame_payload(value)
        elif isinstance(value, pd.Series):
            payload[name] = series_payload(value)
        else:
            payload[name] = value
    return stable_hash(payload)


def frame_payload(frame: pd.DataFrame) -> dict[str, Any]:
    return {
        "index": [str(pd.Timestamp(idx).date()) if isinstance(idx, pd.Timestamp) else str(idx) for idx in frame.index],
        "columns": [str(col) for col in frame.columns],
        "values": [[round(float(value), 12) for value in row] for row in frame.to_numpy(dtype=float)],
    }


def series_payload(series: pd.Series) -> dict[str, float]:
    return {str(idx.date()) if isinstance(idx, pd.Timestamp) else str(idx): round(float(value), 12) for idx, value in series.items()}


def stable_hash(value: Any) -> str:
    text = json.dumps(jsonable(value), sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def frame_equal(left: pd.DataFrame, right: pd.DataFrame) -> bool:
    return left.shape == right.shape and list(left.index) == list(right.index) and list(left.columns) == list(right.columns) and np.allclose(left.to_numpy(dtype=float), right.to_numpy(dtype=float), atol=1e-12, rtol=0.0)


def series_equal(left: pd.Series, right: pd.Series) -> bool:
    return left.shape == right.shape and list(left.index) == list(right.index) and np.allclose(left.to_numpy(dtype=float), right.to_numpy(dtype=float), atol=1e-12, rtol=0.0)


def safe_float(value: Any) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return float("nan")
    return parsed if math.isfinite(parsed) else float("nan")


def numeric_metric_names() -> list[str]:
    return [
        "total_return",
        "annualized_return",
        "annualized_volatility",
        "maximum_drawdown",
        "drawdown_duration_days",
        "sharpe",
        "sortino",
        "return_to_drawdown",
        "worst_daily_return",
        "expected_shortfall_95",
        "one_way_turnover",
        "gross_traded_notional",
        "orders",
        "fills",
        "modeled_transaction_costs",
        "maximum_asset_weight",
        "minimum_asset_weight",
        "average_effective_holdings",
        "maximum_cluster_weight",
        "average_monthly_weight_change",
        "maximum_monthly_weight_change",
    ]


def source_of_truth_update(classification: str, dates: FrozenDates) -> str:
    return f"""# Source Of Truth Update

`{ARTIFACT_ID}` completed its first bounded full-period exploratory run.

- Frozen universe: `{", ".join(FROZEN_SYMBOLS)}`.
- Evaluation range: `{dates.evaluation_start.date().isoformat()}` to `{dates.evaluation_end.date().isoformat()}`.
- Registered runs: `12`.
- Final exploratory classification: `{classification}`.
- Research stage: `research_only_exploration`.
- No tuning, optional management overlay, universe replacement, validation, promotion, paper/demo/live action, or broker invocation occurred.
"""


def dates_payload(dates: FrozenDates) -> dict[str, Any]:
    return {
        "common_start": dates.common_start.date().isoformat(),
        "common_end": dates.common_end.date().isoformat(),
        "evaluation_start": dates.evaluation_start.date().isoformat(),
        "evaluation_end": dates.evaluation_end.date().isoformat(),
        "first_signal_date": dates.first_signal_date.date().isoformat(),
        "first_execution_date": dates.first_execution_date.date().isoformat(),
        "signal_count": len(dates.signal_dates),
        "execution_count": len(dates.execution_dates),
    }


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: csv_value(row.get(field, "")) for field in fieldnames})


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(jsonable(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(jsonable(row), sort_keys=True, separators=(",", ":")) + "\n")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "True" if value else "False"
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return ""
        return f"{value:.12g}"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, (tuple, list, dict)):
        return json.dumps(jsonable(value), sort_keys=True, separators=(",", ":"))
    return str(value)


def jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): jsonable(inner) for key, inner in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(inner) for inner in value]
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    return value


def data_coverage_fields() -> list[str]:
    return ["symbol", "data_file", "sha256", "first_valid_date", "last_valid_date", "valid_open_adjclose_rows", "duplicate_dates_after_cleaning", "nonpositive_or_missing_rows_removed"]


def trial_registry_fields() -> list[str]:
    return ["trial_id", "trial_number", "method_id", "cost_bps_per_side", "portfolio_rule", "registered_before_performance", "status", "execution_status", "complete_state_hash", "terminal_nav", "observations", "failure_code"]


def identity_equivalence_fields() -> list[str]:
    return ["cost_bps_per_side", "monthly_signals_equal", "target_weights_equal", "orders_and_fills_equal", "daily_positions_equal", "daily_cash_and_nav_equal", "transaction_costs_equal", "complete_state_hash_equal", "final_metrics_equal", "hrp_state_hash", "identity_state_hash", "equivalence_status"]


def metrics_fields() -> list[str]:
    return ["row_type", "method_id", "control_method_id", "cost_bps_per_side", "start_date", "end_date", "observations", "initial_nav", "terminal_nav", *numeric_metric_names(), "average_asset_weight", "minimum_effective_holdings", "average_cluster_weight", "rebalance_failures", "skipped_rebalance_dates", "complete_state_hash"]


def subperiod_metrics_fields() -> list[str]:
    return ["row_type", "method_id", "control_method_id", "cost_bps_per_side", "block_id", "block_start_date", "block_end_date", "start_date", "end_date", "observations", "initial_nav", "terminal_nav", *numeric_metric_names(), "average_asset_weight", "minimum_effective_holdings", "average_cluster_weight", "rebalance_failures", "skipped_rebalance_dates", "complete_state_hash"]


def monthly_weights_fields() -> list[str]:
    return ["method_id", "signal_date", "execution_date", "weight_sum", "min_weight", "max_weight", "effective_holdings", *FROZEN_SYMBOLS]


def risk_contribution_fields() -> list[str]:
    return ["method_id", "cost_bps_per_side", "signal_date", "execution_date", "asset", "static_cluster", "asset_weight", "asset_risk_contribution", "cluster_weight", "cluster_risk_contribution"]


def turnover_fields() -> list[str]:
    return ["method_id", "cost_bps_per_side", "date", "is_execution_date", "gross_traded_notional_pct", "one_way_turnover", "transaction_cost_return", "transaction_cost_dollars", "orders", "fills", "nav", "cash"]


def concentration_fields() -> list[str]:
    return ["method_id", "cost_bps_per_side", "top_average_asset", "top_average_asset_weight", "top_max_asset", "top_max_asset_weight", "top_average_cluster", "top_average_cluster_weight", "top_max_cluster", "top_max_cluster_weight", "average_effective_holdings", "one_asset_avg_gt_50pct", "one_cluster_avg_gt_70pct"]


def cluster_stability_fields() -> list[str]:
    return ["method_id", "signal_date", "execution_date", "cluster_signature_hash", "changed_from_previous", "cumulative_cluster_membership_changes", "cluster_stability_to_date"]


def failure_fields() -> list[str]:
    return ["method_id", "signal_date", "execution_date", "failure_code", "failure_reason"]
