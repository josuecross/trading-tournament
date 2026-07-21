from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

import numpy as np
import pandas as pd


HRP_STRATEGY_ID = "hrp_core_multi_asset_monthly_252d_v1"
TRADING_DAYS = 252
WEIGHT_TOLERANCE = 1e-10
VARIANCE_FLOOR = 1e-15


class HRPDataError(ValueError):
    """Raised when HRP inputs would require invented or dropped data."""


@dataclass(frozen=True)
class RecursiveAllocation:
    level: int
    parent_cluster: tuple[str, ...]
    left_cluster: tuple[str, ...]
    right_cluster: tuple[str, ...]
    left_variance: float
    right_variance: float
    left_allocation: float
    right_allocation: float


@dataclass(frozen=True)
class HRPResult:
    weights: pd.Series
    ordered_assets: tuple[str, ...]
    covariance: pd.DataFrame
    correlation: pd.DataFrame
    distance: pd.DataFrame
    linkage: pd.DataFrame
    cluster_variances: tuple[dict[str, Any], ...]
    recursive_allocations: tuple[RecursiveAllocation, ...]


def _coerce_order(instrument_order: Iterable[str]) -> tuple[str, ...]:
    order = tuple(str(symbol) for symbol in instrument_order)
    if not order:
        raise HRPDataError("instrument_order must contain at least one asset")
    if len(order) != len(set(order)):
        raise HRPDataError("instrument_order contains duplicate assets")
    return order


def _align_frame(frame: pd.DataFrame, instrument_order: Iterable[str] | None, *, name: str) -> pd.DataFrame:
    if not isinstance(frame, pd.DataFrame):
        raise HRPDataError(f"{name} must be a pandas DataFrame")
    if frame.empty:
        raise HRPDataError(f"{name} is empty")
    if instrument_order is None:
        order = _coerce_order(frame.columns)
    else:
        order = _coerce_order(instrument_order)
        if set(frame.columns) != set(order):
            raise HRPDataError(f"{name} columns must match the frozen instrument order exactly")
    aligned = frame.loc[:, list(order)].astype(float)
    values = aligned.to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise HRPDataError(f"{name} contains missing or nonfinite values")
    return aligned


def sample_covariance(returns: pd.DataFrame, instrument_order: Iterable[str] | None = None) -> pd.DataFrame:
    aligned = _align_frame(returns, instrument_order, name="returns")
    if len(aligned.index) < 2:
        raise HRPDataError("at least two return observations are required")
    covariance = aligned.cov(ddof=1)
    return _validate_square(covariance, aligned.columns, name="covariance")


def pearson_correlation_from_covariance(covariance: pd.DataFrame) -> pd.DataFrame:
    cov = _validate_square(covariance, covariance.columns, name="covariance")
    values = cov.to_numpy(dtype=float)
    diagonal = np.diag(values)
    if np.any(diagonal < -VARIANCE_FLOOR):
        raise HRPDataError("covariance diagonal contains negative variance")
    std = np.sqrt(np.maximum(diagonal, 0.0))
    correlation = np.zeros_like(values, dtype=float)
    for i in range(values.shape[0]):
        for j in range(values.shape[1]):
            if i == j:
                correlation[i, j] = 1.0
            elif std[i] <= VARIANCE_FLOOR or std[j] <= VARIANCE_FLOOR:
                correlation[i, j] = 0.0
            else:
                correlation[i, j] = values[i, j] / (std[i] * std[j])
    correlation = np.clip(correlation, -1.0, 1.0)
    correlation = (correlation + correlation.T) / 2.0
    np.fill_diagonal(correlation, 1.0)
    return pd.DataFrame(correlation, index=cov.index, columns=cov.columns)


def correlation_distance(correlation: pd.DataFrame) -> pd.DataFrame:
    corr = _validate_square(correlation, correlation.columns, name="correlation")
    clipped = corr.clip(lower=-1.0, upper=1.0)
    distance = np.sqrt((1.0 - clipped.to_numpy(dtype=float)) / 2.0)
    distance = (distance + distance.T) / 2.0
    np.fill_diagonal(distance, 0.0)
    return pd.DataFrame(distance, index=corr.index, columns=corr.columns)


def single_linkage(distance: pd.DataFrame, instrument_order: Iterable[str] | None = None) -> pd.DataFrame:
    order_input = distance.columns if instrument_order is None else instrument_order
    dist = _validate_square(distance, order_input, name="distance")
    order = tuple(dist.columns)
    n_assets = len(order)
    if n_assets == 1:
        return _empty_linkage()

    matrix = dist.to_numpy(dtype=float)
    clusters: dict[int, tuple[int, ...]] = {idx: (idx,) for idx in range(n_assets)}
    active = list(range(n_assets))
    next_id = n_assets
    rows: list[dict[str, float | int]] = []

    while len(active) > 1:
        best: tuple[float, int, tuple[int, ...], tuple[int, ...], int, int] | None = None
        for pos_a, cluster_a in enumerate(active):
            for cluster_b in active[pos_a + 1 :]:
                left_id, right_id = _ordered_cluster_pair(cluster_a, cluster_b, clusters)
                d = _single_link_distance(matrix, clusters[left_id], clusters[right_id])
                key = (
                    float(d),
                    min(clusters[left_id]),
                    tuple(clusters[left_id]),
                    tuple(clusters[right_id]),
                    left_id,
                    right_id,
                )
                if best is None or key < best:
                    best = key
        if best is None:
            raise HRPDataError("single-linkage clustering could not find a merge")
        distance_value, _, _, _, left_id, right_id = best
        merged = tuple(sorted(clusters[left_id] + clusters[right_id]))
        rows.append(
            {
                "left": int(left_id),
                "right": int(right_id),
                "distance": float(distance_value),
                "sample_count": int(len(merged)),
            }
        )
        active = [cluster_id for cluster_id in active if cluster_id not in {left_id, right_id}]
        clusters[next_id] = merged
        active.append(next_id)
        active.sort(key=lambda cluster_id: (clusters[cluster_id][0], clusters[cluster_id], cluster_id))
        next_id += 1

    return pd.DataFrame(rows, columns=["left", "right", "distance", "sample_count"])


def quasi_diagonalize(linkage: pd.DataFrame, instrument_order: Iterable[str]) -> tuple[str, ...]:
    order = _coerce_order(instrument_order)
    n_assets = len(order)
    if n_assets == 1:
        return order
    if len(linkage.index) != n_assets - 1:
        raise HRPDataError("linkage row count must equal n_assets - 1")
    children: dict[int, tuple[int, int]] = {}
    for row_index, row in linkage.reset_index(drop=True).iterrows():
        cluster_id = n_assets + int(row_index)
        children[cluster_id] = (int(row["left"]), int(row["right"]))

    def expand(node_id: int) -> tuple[str, ...]:
        if node_id < n_assets:
            return (order[node_id],)
        if node_id not in children:
            raise HRPDataError("linkage references an unknown cluster")
        left, right = children[node_id]
        return expand(left) + expand(right)

    return expand(n_assets + len(linkage.index) - 1)


def inverse_variance_weights(covariance: pd.DataFrame) -> pd.Series:
    cov = _validate_square(covariance, covariance.columns, name="covariance")
    diagonal = np.diag(cov.to_numpy(dtype=float))
    if np.any(diagonal < -VARIANCE_FLOOR):
        raise HRPDataError("covariance diagonal contains negative variance")
    variances = np.maximum(diagonal, 0.0)
    near_zero = variances <= VARIANCE_FLOOR
    weights = np.zeros(len(variances), dtype=float)
    if np.any(near_zero):
        weights[near_zero] = 1.0 / float(np.sum(near_zero))
    else:
        reciprocal = 1.0 / variances
        weights = reciprocal / reciprocal.sum()
    return pd.Series(weights, index=cov.index, dtype=float)


def cluster_variance(covariance: pd.DataFrame, assets: Iterable[str]) -> float:
    asset_tuple = _coerce_order(assets)
    cov = _validate_square(covariance, covariance.columns, name="covariance")
    if not set(asset_tuple).issubset(set(cov.columns)):
        raise HRPDataError("cluster assets must be present in covariance")
    sub_cov = cov.loc[list(asset_tuple), list(asset_tuple)]
    weights = inverse_variance_weights(sub_cov).to_numpy(dtype=float)
    variance = float(weights @ sub_cov.to_numpy(dtype=float) @ weights)
    if abs(variance) <= VARIANCE_FLOOR:
        return 0.0
    if variance < 0.0:
        raise HRPDataError("cluster variance is negative")
    return variance


def recursive_bisection(
    covariance: pd.DataFrame,
    ordered_assets: Iterable[str],
) -> tuple[pd.Series, tuple[dict[str, Any], ...], tuple[RecursiveAllocation, ...]]:
    order = _coerce_order(ordered_assets)
    cov = _validate_square(covariance, covariance.columns, name="covariance")
    if set(order) != set(cov.columns):
        raise HRPDataError("ordered assets must match covariance assets")

    weights = pd.Series(1.0, index=list(order), dtype=float)
    clusters = [list(order)]
    allocations: list[RecursiveAllocation] = []
    variance_records: list[dict[str, Any]] = []
    level = 0

    while clusters:
        next_clusters: list[list[str]] = []
        for cluster in clusters:
            if len(cluster) <= 1:
                continue
            split = len(cluster) // 2
            left = cluster[:split]
            right = cluster[split:]
            left_variance = cluster_variance(cov, left)
            right_variance = cluster_variance(cov, right)
            denominator = left_variance + right_variance
            if denominator <= VARIANCE_FLOOR:
                left_allocation = 0.5
            else:
                left_allocation = 1.0 - left_variance / denominator
            right_allocation = 1.0 - left_allocation
            weights.loc[left] *= left_allocation
            weights.loc[right] *= right_allocation
            allocation = RecursiveAllocation(
                level=level,
                parent_cluster=tuple(cluster),
                left_cluster=tuple(left),
                right_cluster=tuple(right),
                left_variance=float(left_variance),
                right_variance=float(right_variance),
                left_allocation=float(left_allocation),
                right_allocation=float(right_allocation),
            )
            allocations.append(allocation)
            variance_records.extend(
                [
                    {
                        "level": level,
                        "parent_cluster": tuple(cluster),
                        "cluster": tuple(left),
                        "variance": float(left_variance),
                    },
                    {
                        "level": level,
                        "parent_cluster": tuple(cluster),
                        "cluster": tuple(right),
                        "variance": float(right_variance),
                    },
                ]
            )
            next_clusters.extend([left, right])
        clusters = next_clusters
        level += 1

    normalized = _normalize_weights(weights)
    return normalized, tuple(variance_records), tuple(allocations)


def hrp_from_covariance(
    covariance: pd.DataFrame,
    instrument_order: Iterable[str] | None = None,
) -> HRPResult:
    order_input = covariance.columns if instrument_order is None else instrument_order
    cov = _validate_square(covariance, order_input, name="covariance")
    order = tuple(cov.columns)
    corr = pearson_correlation_from_covariance(cov)
    distance = correlation_distance(corr)
    linkage = single_linkage(distance, order)
    ordered_assets = quasi_diagonalize(linkage, order)
    weights_ordered, variances, allocations = recursive_bisection(cov, ordered_assets)
    weights = weights_ordered.reindex(order)
    weights = _normalize_weights(weights)
    _assert_weight_invariants(weights)
    return HRPResult(
        weights=weights,
        ordered_assets=ordered_assets,
        covariance=cov,
        correlation=corr,
        distance=distance,
        linkage=linkage,
        cluster_variances=variances,
        recursive_allocations=allocations,
    )


def hrp_weights_from_returns(
    returns: pd.DataFrame,
    instrument_order: Iterable[str] | None = None,
) -> HRPResult:
    cov = sample_covariance(returns, instrument_order)
    return hrp_from_covariance(cov, instrument_order=cov.columns)


def daily_returns_window_from_price_data(
    price_data: dict[str, pd.DataFrame],
    assets: Iterable[str],
    as_of_date: pd.Timestamp,
    *,
    lookback: int = TRADING_DAYS,
    price_column: str = "adj_close",
) -> pd.DataFrame:
    order = _coerce_order(assets)
    if lookback <= 0:
        raise HRPDataError("lookback must be positive")
    prices: dict[str, pd.Series] = {}
    for symbol in order:
        frame = price_data.get(symbol)
        if frame is None:
            raise HRPDataError(f"missing price data for {symbol}")
        if "date" in frame.columns:
            indexed = frame.sort_values("date").set_index("date", drop=False)
        else:
            indexed = frame.sort_index()
        indexed.index = pd.to_datetime(indexed.index)
        if price_column not in indexed.columns:
            raise HRPDataError(f"missing {price_column} for {symbol}")
        series = indexed.loc[indexed.index <= pd.Timestamp(as_of_date), price_column].astype(float)
        if series.empty:
            raise HRPDataError(f"no prices available through {as_of_date.date()} for {symbol}")
        prices[symbol] = series
    price_frame = pd.DataFrame(prices).loc[:, list(order)]
    if price_frame.isna().any().any():
        raise HRPDataError("aligned price frame contains missing values")
    returns = price_frame.pct_change(fill_method=None).iloc[1:]
    returns = returns.tail(lookback)
    if len(returns.index) != lookback:
        raise HRPDataError(f"expected {lookback} daily returns, found {len(returns.index)}")
    return _align_frame(returns, order, name="returns")


def _validate_square(frame: pd.DataFrame, instrument_order: Iterable[str], *, name: str) -> pd.DataFrame:
    order = _coerce_order(instrument_order)
    if set(frame.index) != set(order) or set(frame.columns) != set(order):
        raise HRPDataError(f"{name} rows and columns must match the frozen instrument order")
    aligned = frame.loc[list(order), list(order)].astype(float)
    values = aligned.to_numpy(dtype=float)
    if values.shape[0] != values.shape[1]:
        raise HRPDataError(f"{name} must be square")
    if not np.isfinite(values).all():
        raise HRPDataError(f"{name} contains missing or nonfinite values")
    if not np.allclose(values, values.T, atol=WEIGHT_TOLERANCE, rtol=0.0):
        raise HRPDataError(f"{name} must be symmetric")
    return aligned


def _ordered_cluster_pair(
    cluster_a: int,
    cluster_b: int,
    clusters: dict[int, tuple[int, ...]],
) -> tuple[int, int]:
    left, right = sorted(
        (cluster_a, cluster_b),
        key=lambda cluster_id: (clusters[cluster_id][0], clusters[cluster_id], cluster_id),
    )
    return int(left), int(right)


def _single_link_distance(matrix: np.ndarray, left: tuple[int, ...], right: tuple[int, ...]) -> float:
    distances = [matrix[i, j] for i in left for j in right]
    value = float(np.min(distances))
    if not np.isfinite(value):
        raise HRPDataError("single-linkage distance is nonfinite")
    return value


def _normalize_weights(weights: pd.Series) -> pd.Series:
    values = weights.astype(float)
    if not np.isfinite(values.to_numpy(dtype=float)).all():
        raise HRPDataError("weights contain nonfinite values")
    values = values.clip(lower=0.0)
    total = float(values.sum())
    if total <= WEIGHT_TOLERANCE:
        raise HRPDataError("weights do not contain positive capital allocation")
    return values / total


def _assert_weight_invariants(weights: pd.Series) -> None:
    values = weights.to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise HRPDataError("weights contain nonfinite values")
    if np.any(values < -WEIGHT_TOLERANCE):
        raise HRPDataError("weights contain negative values")
    if abs(float(values.sum()) - 1.0) > WEIGHT_TOLERANCE:
        raise HRPDataError("weights do not sum to one")


def _empty_linkage() -> pd.DataFrame:
    return pd.DataFrame(columns=["left", "right", "distance", "sample_count"])
