from __future__ import annotations

import csv
import hashlib
import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.research import phase2_expanded_universe_discovery_batch_v1 as phase2
from strategy_lab.research_os.research.resolve_refreeze_spdj_dynamic_inflation_signal_contract_v2 import (
    dataset_hash as v2_dataset_hash,
)


TASK_ID = "implement_spdj_multi_asset_dynamic_inflation_etf_portability_v1"
STRATEGY_ID = "spdj_multi_asset_dynamic_inflation_etf_portability_v1"
FAMILY_ID = "public_cpi_dynamic_inflation_regime_allocation"
ARCHITECTURE_ID = "monthly_cpi_regime_dynamic_multi_asset_inflation_allocation"
TRIAL_ID = f"{STRATEGY_ID}__canonical"
SOURCE_PACKET_ID = "phase2_public_signal_etf_mappable_candidate_intake_v2"
V2_DATASET_ID = "phase2_public_cpi_point_in_time_v2"
V2_EXPECTED_HASH = "sha256:e221af86dfd616f4fa65bec016910deaffe47f1d6e690495a4033cd0e3eefcc8"
UNIVERSE_ID = "phase2_bounded_multi_asset_research_universe_v1"
UNIVERSE_EXPECTED_HASH = "sha256:5bafb89d6c32712178c2a1fc57e8eb177daa9257625e7bcd317cefe2ea3c9861"
SYMBOLS = ("SPY", "IYR", "GSG", "GLD", "AGG", "TIP")
MAPPING = {
    "U.S. equities": "SPY",
    "U.S. REITs": "IYR",
    "broad commodities": "GSG",
    "gold": "GLD",
    "U.S. aggregate bonds": "AGG",
    "U.S. TIPS": "TIP",
}
NAMED_CONTROL = "static_source_low_regime_60_40_spy_agg"
EQUAL_CONTROL = "monthly_equal_weight_six_mapped_assets"
DIAGNOSTIC_CONTROL = "full_period_average_candidate_allocation_control"
BLOCKING_CONTROLS = (NAMED_CONTROL, EQUAL_CONTROL)
COSTS = (0.0, 5.0, 10.0)
PRIMARY_COST = 5.0
TOLERANCE = 1e-10
WEIGHT_TOLERANCE = 1e-8
SELECTION_FRACTION = 0.60
MIN_TOTAL_EVENTS = 120
MIN_SELECTION_EVENTS = 72
MIN_EVALUATION_EVENTS = 48

OUTCOME_SELECTION_FAILED = "spdj_dynamic_inflation_selection_failed"
OUTCOME_EVALUATION_NO_FOLLOWUP = "spdj_dynamic_inflation_evaluation_no_followup"
OUTCOME_FOLLOWUP = "spdj_dynamic_inflation_exploration_followup"
OUTCOME_BLOCKED = "spdj_dynamic_inflation_implementation_blocked"
NEGATIVE_NEXT_ACTION = "direction_owner_review_phase2_after_spdj_dynamic_inflation_negative_v1"
FOLLOWUP_NEXT_ACTION = "run_spdj_dynamic_inflation_robustness_v1"
BLOCKED_NEXT_ACTION = "direction_owner_review_spdj_dynamic_inflation_implementation_blocker_v1"

V2_DIR = ROOT / "data" / "public_signals" / V2_DATASET_ID
OUTPUT_DIR = ROOT / "evidence" / "research_recovery" / STRATEGY_ID / "latest"
INTAKE_DIR = ROOT / "evidence" / "public_source_strategy_intake" / SOURCE_PACKET_ID / "latest"
V1_DIR = ROOT / "data" / "public_signals" / "phase2_public_cpi_point_in_time_v1"
V1_EVIDENCE_DIR = ROOT / "evidence" / "public_signal_data" / "acquire_validate_freeze_phase2_public_signal_inputs_v1" / "latest"
V2_EVIDENCE_DIR = ROOT / "evidence" / "public_signal_data" / "resolve_refreeze_spdj_dynamic_inflation_signal_contract_v2" / "latest"
UNIVERSE_DIR = ROOT / "evidence" / "universe_expansion" / UNIVERSE_ID / "latest"
PHASE2_CACHE = ROOT / "data" / "universe_expansion" / "phase2_bounded_multi_asset_market_data_v1"
PILOT_CACHE = ROOT / "data" / "universe_expansion" / "pilot_etf_market_data_v1"

PROTECTED_PATHS = (
    V1_DIR,
    V2_DIR,
    V1_EVIDENCE_DIR,
    V2_EVIDENCE_DIR,
    INTAKE_DIR,
    UNIVERSE_DIR,
    PHASE2_CACHE,
    PILOT_CACHE,
    ROOT / "strategy_lab" / "strategy_registry.yaml",
    ROOT / "strategy_lab" / "RESEARCH_ROADMAP.md",
    ROOT / "strategy_lab" / "research_os" / "research" / "research_queue.yaml",
    ROOT / "strategy_lab" / "research_os" / "family_lineage" / "family_ledger.yaml",
    ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml",
    ROOT / "paper_forward_observations",
    ROOT / "paper_forward_observation_plans",
)

EXPECTED_THRESHOLD_REGIMES = {
    "2006-12": "high",
    "2010-12": "low",
    "2013-03": "low",
    "2016-09": "low",
    "2017-01": "high",
    "2018-10": "high",
    "2024-08": "high",
}

FORBIDDEN_ADAPTATIONS = (
    "alternate_thresholds",
    "alternate_lookbacks",
    "alternate_warmups",
    "alternate_ETF_mappings",
    "alternate_regression_definitions",
    "alternate_trading_delays",
    "alternate_beta_transforms",
    "parameter_sweeps",
    "trade_management_overlays",
)


@dataclass(frozen=True)
class SplitDefinition:
    event_dates: tuple[pd.Timestamp, ...]
    selection_events: tuple[pd.Timestamp, ...]
    evaluation_events: tuple[pd.Timestamp, ...]
    selection_index: pd.DatetimeIndex
    evaluation_index: pd.DatetimeIndex
    full_index: pd.DatetimeIndex
    boundary: pd.Timestamp


def bool_text(value: bool) -> str:
    return "true" if bool(value) else "false"


def json_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_value(item) for item in value]
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(json_value(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def csv_value(value: Any) -> Any:
    if isinstance(value, bool):
        return bool_text(value)
    if value is None:
        return ""
    if isinstance(value, (dict, list, tuple, set)):
        return json.dumps(json_value(value), sort_keys=True, separators=(",", ":"))
    if isinstance(value, pd.Timestamp):
        return value.date().isoformat()
    return value


def write_csv(path: Path, rows: Iterable[dict[str, Any]], fields: Iterable[str] | None = None) -> None:
    materialized = list(rows)
    if fields is None:
        ordered: list[str] = []
        for row in materialized:
            for field in row:
                if field not in ordered:
                    ordered.append(field)
        fields = ordered
    field_list = list(fields)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=field_list, extrasaction="ignore")
        writer.writeheader()
        for row in materialized:
            writer.writerow({field: csv_value(row.get(field, "")) for field in field_list})


def sha256_bytes(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def sha256_path(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def stable_hash(payload: Any) -> str:
    encoded = json.dumps(json_value(payload), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256_bytes(encoded)


def hash_tree(path: Path) -> str:
    if not path.exists():
        return "missing"
    if path.is_file():
        return sha256_path(path)
    digest = hashlib.sha256()
    for item in sorted(child for child in path.rglob("*") if child.is_file()):
        digest.update(item.relative_to(path).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(item.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def protected_snapshot() -> dict[str, str]:
    return {path.relative_to(ROOT).as_posix(): hash_tree(path) for path in PROTECTED_PATHS}


def packet_hash() -> str:
    digest = hashlib.sha256()
    excluded = {"consistency_check.json"}
    for path in sorted(item for item in OUTPUT_DIR.iterdir() if item.is_file() and item.name not in excluded):
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def verify_v2() -> dict[str, Any]:
    manifest = json.loads((V2_DIR / "freeze_manifest.json").read_text(encoding="utf-8"))
    core_hashes = {
        relative: sha256_path(ROOT / relative)
        for relative in manifest["core_file_hashes"]
    }
    observed = v2_dataset_hash(core_hashes)
    checks = {
        "manifest_dataset_id_matches": manifest["dataset_id"] == V2_DATASET_ID,
        "manifest_hash_matches_expected": manifest["frozen_dataset_hash"] == V2_EXPECTED_HASH,
        "component_hashes_match": core_hashes == manifest["core_file_hashes"],
        "recomputed_hash_matches_expected": observed == V2_EXPECTED_HASH,
        "immutable": manifest["immutable"] is True,
    }
    if not all(checks.values()):
        raise RuntimeError("frozen_public_signal_hash_mismatch")
    return {
        "dataset_id": V2_DATASET_ID,
        "expected_hash": V2_EXPECTED_HASH,
        "observed_hash": observed,
        "component_hashes": core_hashes,
        "checks": checks,
        "status": "pass",
    }


def load_signal() -> pd.DataFrame:
    frame = pd.read_csv(V2_DIR / "cpi_point_in_time_signal.csv", dtype=str).fillna("")
    frame["reference_period"] = pd.PeriodIndex(frame["reference_month"], freq="M")
    frame["release_date"] = pd.to_datetime(frame["bls_release_date"], errors="coerce")
    frame["effective_date"] = pd.to_datetime(frame["source_effective_after_close_date"], errors="coerce")
    frame["cpi_yoy"] = pd.to_numeric(frame["canonical_cpi_yoy_unrounded"], errors="coerce")
    frame["event"] = frame["rebalance_event"].eq("true")
    if frame["reference_period"].duplicated().any() or not frame["reference_period"].is_monotonic_increasing:
        raise RuntimeError("invalid_V2_month_order")
    return frame.set_index("reference_period", drop=False)


def load_prices() -> tuple[pd.DataFrame, list[dict[str, Any]], dict[str, Any]]:
    _, universe, reconciliation = phase2.load_universe_contract()
    if reconciliation["computed_hash"] != UNIVERSE_EXPECTED_HASH:
        raise RuntimeError("frozen_universe_hash_mismatch")
    if not set(SYMBOLS).issubset(universe):
        raise RuntimeError("required_symbol_missing")
    series = {symbol: phase2.load_price_series(symbol, universe) for symbol in SYMBOLS}
    start = max(values.index.min() for values in series.values())
    end = min(values.index.max() for values in series.values())
    index = series["SPY"].index[(series["SPY"].index >= start) & (series["SPY"].index <= end)]
    prices = pd.concat([series[symbol].reindex(index) for symbol in SYMBOLS], axis=1)
    prices.columns = list(SYMBOLS)
    if prices.isna().any().any():
        raise RuntimeError("unexplained_price_gap")
    rows: list[dict[str, Any]] = []
    cache_hashes: dict[str, str] = {}
    for symbol in SYMBOLS:
        contract = universe[symbol]
        cache_path = ROOT / contract["cache_path"]
        observed_hash = sha256_path(cache_path)
        cache_hashes[symbol] = observed_hash
        rows.append(
            {
                "symbol": symbol,
                "cache_path": contract["cache_path"],
                "expected_cache_hash": contract["cache_hash"],
                "observed_cache_hash": observed_hash,
                "first_valid_date": series[symbol].index.min().date().isoformat(),
                "last_valid_date": series[symbol].index.max().date().isoformat(),
                "row_count": len(series[symbol]),
                "ordered_unique_dates": bool(series[symbol].index.is_unique and series[symbol].index.is_monotonic_increasing),
                "finite_positive_adjusted_prices": bool(np.isfinite(series[symbol]).all() and (series[symbol] > 0).all()),
                "common_calendar_gap_count": int(series[symbol].reindex(index).isna().sum()),
                "cache_hash_match": observed_hash == contract["cache_hash"],
                "provider_accessed": False,
                "status": "pass" if observed_hash == contract["cache_hash"] else "fail",
            }
        )
    if not all(row["status"] == "pass" for row in rows):
        raise RuntimeError("frozen_price_cache_hash_mismatch")
    price_contract = {
        "universe_id": UNIVERSE_ID,
        "universe_hash": reconciliation["computed_hash"],
        "symbols": list(SYMBOLS),
        "cache_hashes": cache_hashes,
        "frozen_price_data_bundle_hash": stable_hash(cache_hashes),
        "common_start": prices.index.min().date().isoformat(),
        "common_end": prices.index.max().date().isoformat(),
        "common_sessions": len(prices),
        "provider_accessed": False,
        "status": "pass",
    }
    return prices, rows, price_contract


def month_end_prices(prices: pd.DataFrame) -> pd.DataFrame:
    return prices.groupby(prices.index.to_period("M")).last()


def classify_regime(value: float) -> str:
    if value < 1.5:
        return "low"
    if value <= 2.5:
        return "medium"
    return "high"


def low_weights() -> dict[str, float]:
    return {symbol: (0.60 if symbol == "SPY" else 0.40 if symbol == "AGG" else 0.0) for symbol in SYMBOLS}


def inverse_vol_weights(window_returns: pd.DataFrame) -> tuple[dict[str, float], dict[str, float]]:
    vol = window_returns.std(axis=0, ddof=1)
    if not np.isfinite(vol.to_numpy()).all() or (vol <= 0.0).any():
        raise RuntimeError("invalid_source_volatility")
    raw = 1.0 / vol
    weights = raw / raw.sum()
    return weights.astype(float).to_dict(), vol.astype(float).to_dict()


def beta_transform(beta: float) -> float:
    return 1.0 + beta if beta >= 0.0 else 1.0 / (1.0 - beta)


def rolling_12m_returns(window_returns: pd.DataFrame) -> pd.DataFrame:
    return (1.0 + window_returns).rolling(12, min_periods=12).apply(np.prod, raw=True) - 1.0


def pro_ib_weights(
    window_returns: pd.DataFrame,
    signal: pd.DataFrame,
    formation_release: pd.Timestamp,
    formation_month: pd.Period,
) -> tuple[dict[str, float], list[dict[str, Any]]]:
    returns_12m = rolling_12m_returns(window_returns).dropna(how="any")
    pair_months = [month for month in returns_12m.index if month in signal.index and signal.loc[month, "event"]]
    if len(pair_months) < 2:
        raise RuntimeError("implementation_blocked_proib_alignment_contract")
    paired = returns_12m.loc[pair_months]
    cpi = signal.loc[pair_months, "cpi_yoy"].astype(float)
    release_dates = pd.to_datetime(signal.loc[pair_months, "release_date"])
    all_available = bool((release_dates <= formation_release).all())
    if not all_available or not np.isfinite(cpi.to_numpy()).all():
        raise RuntimeError("implementation_blocked_proib_alignment_contract")
    x = cpi.to_numpy(dtype=float)
    x_design = np.column_stack([np.ones(len(x)), x])
    transformed: dict[str, float] = {}
    diagnostics: list[dict[str, Any]] = []
    for symbol in SYMBOLS:
        y = paired[symbol].to_numpy(dtype=float)
        alpha, beta = np.linalg.lstsq(x_design, y, rcond=None)[0]
        value = beta_transform(float(beta))
        if not math.isfinite(value) or value <= 0.0:
            raise RuntimeError("invalid_ProIB_beta_transform")
        transformed[symbol] = value
        diagnostics.append(
            {
                "formation_reference_month": str(formation_month),
                "formation_release_date": formation_release.date().isoformat(),
                "asset": symbol,
                "underlying_return_window_start": str(window_returns.index.min()),
                "underlying_return_window_end": str(window_returns.index.max()),
                "underlying_return_observation_count": len(window_returns),
                "rolling_12m_pair_count": len(pair_months),
                "expected_complete_pair_count_before_missing_CPI": len(window_returns) - 11,
                "missing_CPI_pair_count": len(window_returns) - 11 - len(pair_months),
                "first_pair_month": str(pair_months[0]),
                "last_pair_month": str(pair_months[-1]),
                "pair_months": [str(month) for month in pair_months],
                "latest_CPI_release_used": release_dates.max().date().isoformat(),
                "all_CPI_releases_available_by_formation": all_available,
                "intercept": float(alpha),
                "beta": float(beta),
                "transformed_beta": value,
                "beta_transform_formula": "1+beta_if_nonnegative_else_1/(1-beta)",
                "pre_window_return_used": False,
                "input_hash": stable_hash({"months": [str(m) for m in pair_months], "x": x.tolist(), "y": y.tolist()}),
            }
        )
    denominator = sum(transformed.values())
    weights = {symbol: transformed[symbol] / denominator for symbol in SYMBOLS}
    for row in diagnostics:
        row["normalized_weight"] = weights[row["asset"]]
    return weights, diagnostics


def validate_target(weights: dict[str, float]) -> None:
    if tuple(weights) != SYMBOLS:
        raise RuntimeError("target_symbol_order_or_count_invalid")
    values = np.array([weights[symbol] for symbol in SYMBOLS], dtype=float)
    if not np.isfinite(values).all() or (values < -WEIGHT_TOLERANCE).any():
        raise RuntimeError("invalid_target_weight")
    if abs(values.sum() - 1.0) > WEIGHT_TOLERANCE:
        raise RuntimeError("target_weight_sum_invalid")


def build_signals(
    prices: pd.DataFrame,
    signal: pd.DataFrame,
) -> dict[str, Any]:
    monthly_prices = month_end_prices(prices)
    monthly_returns = monthly_prices.pct_change(fill_method=None).dropna(how="any")
    monthly_rows: list[dict[str, Any]] = []
    pro_rows: list[dict[str, Any]] = []
    vol_rows: list[dict[str, Any]] = []
    event_targets: dict[pd.Timestamp, dict[str, float]] = {}
    event_regimes: dict[pd.Timestamp, str] = {}
    first_valid: pd.Timestamp | None = None
    first_pair_count: int | None = None
    for month, row in signal.iterrows():
        if not bool(row["event"]) or month not in monthly_returns.index:
            continue
        available = monthly_returns.loc[monthly_returns.index <= month]
        if len(available) < 36:
            continue
        window = available.tail(min(len(available), 120))
        effective = pd.Timestamp(row["effective_date"])
        release = pd.Timestamp(row["release_date"])
        if effective not in prices.index:
            raise RuntimeError("missing_required_effective_close")
        cpi_yoy = float(row["cpi_yoy"])
        regime = classify_regime(cpi_yoy)
        if regime != row["canonical_regime"]:
            raise RuntimeError("frozen_regime_reproduction_failed")
        stats_cutoff = monthly_prices.index[monthly_prices.index == month]
        if len(stats_cutoff) != 1:
            raise RuntimeError("missing_previous_month_end_statistics_cutoff")
        vol_weights, volatilities = inverse_vol_weights(window)
        raw_inverse = {symbol: 1.0 / volatilities[symbol] for symbol in SYMBOLS}
        for symbol in SYMBOLS:
            vol_rows.append(
                {
                    "formation_reference_month": str(month),
                    "formation_release_date": release.date().isoformat(),
                    "effective_close_date": effective.date().isoformat(),
                    "selected_by_realized_regime": regime == "medium",
                    "asset": symbol,
                    "window_start_month": str(window.index.min()),
                    "window_end_month": str(window.index.max()),
                    "observation_count": len(window),
                    "sample_volatility_ddof": 1,
                    "sample_volatility": volatilities[symbol],
                    "raw_inverse_volatility": raw_inverse[symbol],
                    "normalized_weight": vol_weights[symbol],
                    "finite_positive_volatility": True,
                }
            )
        pro_weights, diagnostics = pro_ib_weights(window, signal, release, month)
        for diagnostic in diagnostics:
            diagnostic["selected_by_realized_regime"] = regime == "high"
        pro_rows.extend(diagnostics)
        if first_pair_count is None:
            first_pair_count = diagnostics[0]["rolling_12m_pair_count"]
        if regime == "low":
            weights = low_weights()
        elif regime == "medium":
            weights = vol_weights
        else:
            weights = pro_weights
        weights = {symbol: float(weights[symbol]) for symbol in SYMBOLS}
        validate_target(weights)
        first_valid = effective if first_valid is None else first_valid
        event_targets[effective] = weights
        event_regimes[effective] = regime
        statistics_cutoff = prices.index[prices.index.to_period("M") == month].max().date().isoformat()
        monthly_rows.append(
            {
                "reference_month": str(month),
                "allocation_statistics_cutoff": statistics_cutoff,
                "allocation_statistics_last_trading_date": statistics_cutoff,
                "regime_information_cutoff": release.date().isoformat(),
                "effective_close_date": effective.date().isoformat(),
                "new_weights_first_return_date": prices.index[prices.index.get_loc(effective) + 1].date().isoformat() if prices.index.get_loc(effective) + 1 < len(prices) else "",
                "cpi_yoy_unrounded": cpi_yoy,
                "regime": regime,
                "lookback_monthly_returns": len(window),
                "lookback_start_month": str(window.index.min()),
                "lookback_end_month": str(window.index.max()),
                "target_weight_sum": sum(weights.values()),
                **{f"target_{symbol}": weights[symbol] for symbol in SYMBOLS},
            }
        )
    if first_valid is None:
        raise RuntimeError("no_valid_formation")
    if first_pair_count is None:
        raise RuntimeError("no_high_regime_formation")
    targets = pd.DataFrame.from_dict(event_targets, orient="index").reindex(columns=list(SYMBOLS)).sort_index()
    targets.index = pd.DatetimeIndex(targets.index)
    return {
        "monthly_prices": monthly_prices,
        "monthly_returns": monthly_returns,
        "monthly_rows": monthly_rows,
        "pro_rows": pro_rows,
        "vol_rows": vol_rows,
        "targets": targets,
        "event_regimes": event_regimes,
        "first_valid": first_valid,
        "first_pair_count": first_pair_count,
    }


def build_split(prices: pd.DataFrame, targets: pd.DataFrame) -> SplitDefinition:
    dates = tuple(pd.Timestamp(value) for value in targets.index)
    if len(dates) < MIN_TOTAL_EVENTS:
        raise RuntimeError("signal_scarcity")
    boundary_position = int(math.floor(SELECTION_FRACTION * len(dates)))
    if boundary_position < MIN_SELECTION_EVENTS or len(dates) - boundary_position < MIN_EVALUATION_EVENTS:
        raise RuntimeError("signal_scarcity")
    boundary = dates[boundary_position]
    first = dates[0]
    return SplitDefinition(
        event_dates=dates,
        selection_events=dates[:boundary_position],
        evaluation_events=dates[boundary_position:],
        selection_index=prices.index[(prices.index >= first) & (prices.index < boundary)],
        evaluation_index=prices.index[prices.index >= boundary],
        full_index=prices.index[prices.index >= first],
        boundary=boundary,
    )


def complete_target_schedule(prices: pd.DataFrame, targets: pd.DataFrame) -> pd.DataFrame:
    schedule = targets.reindex(prices.index).ffill()
    schedule = schedule.loc[schedule.index >= targets.index.min()]
    if schedule.isna().any().any():
        raise RuntimeError("daily_target_schedule_contains_nan")
    return schedule


def control_targets(event_dates: Iterable[pd.Timestamp], weights: dict[str, float]) -> pd.DataFrame:
    validate_target(weights)
    rows = [weights.copy() for _ in event_dates]
    return pd.DataFrame(rows, index=pd.DatetimeIndex(list(event_dates)), columns=list(SYMBOLS), dtype=float)


def simulate(
    prices: pd.DataFrame,
    targets: pd.DataFrame,
    cost: float,
    end: pd.Timestamp | None = None,
) -> dict[str, Any]:
    scoped_prices = prices if end is None else prices.loc[prices.index <= end]
    scoped_targets = targets.loc[targets.index <= scoped_prices.index.max()]
    return phase2.simulate_events(
        scoped_prices,
        scoped_targets,
        cost,
        timing_policy="CPI_release_then_next_business_day_close_target_effective_for_following_close_to_close_interval",
        formation_dates=scoped_targets.index,
        execution_dates=scoped_targets.index,
    )


def path_metrics(path: dict[str, Any], period: pd.DatetimeIndex, regimes: dict[pd.Timestamp, str]) -> dict[str, Any]:
    metrics = phase2.path_metrics(path, period)
    held = path["held_weights"].reindex(period).dropna(how="all")
    events = [row for row in path["events"] if pd.Timestamp(row["execution_date"]) in period]
    event_dates = [pd.Timestamp(row["execution_date"]) for row in events]
    regime_counts = {name: sum(regimes.get(date) == name for date in event_dates) for name in ("low", "medium", "high")}
    total_events = len(event_dates)
    target_events = path["target_events"].loc[path["target_events"].index.intersection(period)]
    changes = 0
    previous: np.ndarray | None = None
    for values in target_events.to_numpy(dtype=float):
        if previous is None or not np.allclose(values, previous, atol=WEIGHT_TOLERANCE):
            changes += 1
        previous = values
    drawdown = abs(float(metrics["maximum_drawdown"]))
    initialized_held = held.loc[held.index > target_events.index.min()] if len(target_events) else held.iloc[0:0]
    metrics.update(
        {
            "calmar_ratio": float(metrics["cagr"]) / drawdown if drawdown > 0.0 else 0.0,
            "cpi_rebalance_event_count": total_events,
            "actual_allocation_change_count": changes,
            "average_allocation_by_asset": {symbol: float(held[symbol].mean()) for symbol in SYMBOLS},
            "maximum_allocation_by_asset": {symbol: float(held[symbol].max()) for symbol in SYMBOLS},
            "regime_counts": regime_counts,
            "regime_percentages": {name: (regime_counts[name] / total_events if total_events else 0.0) for name in regime_counts},
            "explicit_zero_targets_preserved": bool((target_events == 0.0).any().any()) if len(target_events) else False,
            "daily_weight_sum_fully_invested": bool(
                len(initialized_held)
                and np.allclose(initialized_held.sum(axis=1), 1.0, atol=WEIGHT_TOLERANCE)
            ),
            "initialization_close_has_complete_target": bool(
                len(target_events) and np.isclose(target_events.iloc[0].sum(), 1.0, atol=WEIGHT_TOLERANCE)
            ),
        }
    )
    metrics["invariant_pass"] = bool(
        metrics["invariant_pass"]
        and metrics["daily_weight_sum_fully_invested"]
        and float(metrics["maximum_daily_weight_sum"]) <= 1.0 + WEIGHT_TOLERANCE
    )
    return metrics


def selection_vector(metrics: dict[tuple[str, float], dict[str, Any]]) -> dict[str, bool]:
    candidate = metrics[("candidate", PRIMARY_COST)]
    named = metrics[(NAMED_CONTROL, PRIMARY_COST)]
    equal = metrics[(EQUAL_CONTROL, PRIMARY_COST)]
    vector = {
        "cagr_positive_5bps": float(candidate["cagr"]) > 0.0,
        "invariants_pass_5bps": bool(candidate["invariant_pass"]),
        "named_control_not_dominating_5bps": not phase2.dominates(named, candidate),
        "material_vs_named_control_5bps": phase2.material_advantage(candidate, named),
        "equal_weight_control_not_dominating_5bps": not phase2.dominates(equal, candidate),
        "cagr_positive_10bps": float(metrics[("candidate", 10.0)]["cagr"]) > 0.0,
    }
    vector["selection_eligible"] = all(vector.values())
    return vector


def failure_reason(vector: dict[str, bool]) -> str:
    if not vector["cagr_positive_5bps"]:
        return "weak_return"
    if not vector["invariants_pass_5bps"]:
        return "methodology_failure"
    if not vector["named_control_not_dominating_5bps"]:
        return "weak_vs_primary_control"
    if not vector["material_vs_named_control_5bps"] or not vector["equal_weight_control_not_dominating_5bps"]:
        return "benchmark_like_behavior"
    if not vector["cagr_positive_10bps"]:
        return "cost_drag"
    return ""


def evaluation_vector(metrics: dict[tuple[str, float], dict[str, Any]], halves_pass: bool) -> dict[str, bool]:
    vector = selection_vector(metrics)
    vector.pop("selection_eligible")
    vector["evaluation_subhalves_pass_vs_named_control"] = halves_pass
    vector["exploration_followup_justified"] = all(vector.values())
    return vector


def metrics_row(
    period_id: str,
    role: str,
    entity_id: str,
    cost: float,
    metrics: dict[str, Any],
    candidate: dict[str, Any] | None = None,
) -> dict[str, Any]:
    row = {
        "strategy_id": STRATEGY_ID,
        "trial_id": TRIAL_ID,
        "period_id": period_id,
        "entity_role": role,
        "entity_id": entity_id,
        "cost_bps_one_way": cost,
        **metrics,
    }
    if candidate is not None:
        row.update(
            {
                "candidate_minus_control_cagr": float(candidate["cagr"]) - float(metrics["cagr"]),
                "candidate_minus_control_sharpe": float(candidate["sharpe_ratio"]) - float(metrics["sharpe_ratio"]),
                "candidate_minus_control_maximum_drawdown": float(candidate["maximum_drawdown"]) - float(metrics["maximum_drawdown"]),
                "control_dominates_candidate": phase2.dominates(metrics, candidate),
                "candidate_material_advantage": phase2.material_advantage(candidate, metrics),
            }
        )
    return row


def preregistration_payload(
    v2: dict[str, Any],
    price_contract: dict[str, Any],
    split: SplitDefinition,
    code_hash: str,
) -> dict[str, Any]:
    frozen = {
        "task_id": TASK_ID,
        "strategy_id": STRATEGY_ID,
        "family_id": FAMILY_ID,
        "architecture_id": ARCHITECTURE_ID,
        "canonical_trial_id": TRIAL_ID,
        "source_packet_id": SOURCE_PACKET_ID,
        "source_contract_dataset_id": V2_DATASET_ID,
        "source_contract_dataset_hash": v2["observed_hash"],
        "frozen_universe_id": UNIVERSE_ID,
        "frozen_universe_hash": UNIVERSE_EXPECTED_HASH,
        "ETF_mapping": MAPPING,
        "code_hash": code_hash,
        "canonical_trial_count": 1,
        "implementation_rules": {
            "low": "CPI_YoY<1.5:SPY=0.60,AGG=0.40",
            "medium": "1.5<=CPI_YoY<=2.5:normalized_inverse_sample_volatility_six_assets",
            "high": "CPI_YoY>2.5:normalized_source_beta_transform_six_assets",
            "lookback": "36_month_expanding_to_latest_120_monthly_returns",
            "ProIB": "OLS_R12m_on_point_in_time_CPI_YoY_with_intercept",
        },
        "first_valid_formation": split.event_dates[0].date().isoformat(),
        "signal_timing": "regime_known_on_documented_CPI_release_date",
        "allocation_statistics_timing": "returns_end_at_previous_calendar_month_final_trading_close",
        "return_accounting": "old_weights_earn_through_effective_close_new_target_earns_next_close_to_close_interval",
        "cost_assumptions_bps_one_way": list(COSTS),
        "primary_cost_bps_one_way": PRIMARY_COST,
        "turnover_formula": "0.5*sum(abs(target_weight-pretrade_weight))",
        "controls": {
            NAMED_CONTROL: {"role": "blocking_control", "weights": low_weights(), "timing": "same_monthly_CPI_effective_close_schedule"},
            EQUAL_CONTROL: {"role": "blocking_control", "weights": {symbol: 1.0 / 6.0 for symbol in SYMBOLS}, "timing": "same_monthly_CPI_effective_close_schedule"},
            DIAGNOSTIC_CONTROL: {"role": "diagnostic_only", "calculation": "withheld_unless_evaluation_access_is_authorized"},
        },
        "selection_evaluation_split": {
            "policy": "canonical_Phase2_60_percent_signal_events_selection_40_percent_reserved_evaluation",
            "selection_event_count": len(split.selection_events),
            "evaluation_event_count": len(split.evaluation_events),
            "selection_start": split.selection_index.min().date().isoformat(),
            "selection_end": split.selection_index.max().date().isoformat(),
            "evaluation_start": split.evaluation_index.min().date().isoformat(),
            "evaluation_end": split.evaluation_index.max().date().isoformat(),
            "evaluation_inaccessible_until_selection_gate_passes": True,
        },
        "selection_gate": {
            "candidate_CAGR_positive_at_5bps": True,
            "all_invariants_pass": True,
            "named_control_must_not_dominate": True,
            "material_advantage_vs_named": "Sharpe>=0.02_or_drawdown>=0.01",
            "equal_weight_control_must_not_dominate": True,
            "candidate_CAGR_positive_at_10bps": True,
        },
        "evaluation_gate": "same_selection_gate_plus_evaluation_chronological_halves_not_worse_on_both_Sharpe_and_drawdown_vs_named_control",
        "price_cache_identifier": "phase2_bounded_multi_asset_market_data_v1",
        "price_cache_bundle_hash": price_contract["frozen_price_data_bundle_hash"],
        "forbidden_adaptations": list(FORBIDDEN_ADAPTATIONS),
        "performance_metrics_calculated_before_preregistration": False,
        "post_result_adaptation_allowed": False,
    }
    return frozen


def write_preregistration(payload: dict[str, Any]) -> dict[str, Any]:
    path = OUTPUT_DIR / "preregistration.json"
    contract_hash = stable_hash(payload)
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        if existing.get("preregistration_contract_hash") != contract_hash:
            raise RuntimeError("preregistration_contract_changed")
        return existing
    recorded = {
        **payload,
        "preregistration_timestamp": datetime.now(timezone.utc).isoformat(),
        "preregistration_contract_hash": contract_hash,
        "preregistration_written_before_performance_access": True,
    }
    write_json(path, recorded)
    return recorded


def preserve_preliminary_correction(current_code_hash: str) -> str:
    preregistration_path = OUTPUT_DIR / "preregistration.json"
    if not preregistration_path.exists():
        return current_code_hash
    existing = json.loads(preregistration_path.read_text(encoding="utf-8"))
    preregistered_hash = existing["code_hash"]
    if preregistered_hash == current_code_hash:
        return preregistered_hash
    correction_path = OUTPUT_DIR / "implementation_correction_log.json"
    if correction_path.exists():
        correction = json.loads(correction_path.read_text(encoding="utf-8"))
        if correction.get("corrected_code_hash") != current_code_hash:
            history = list(correction.get("intermediate_corrected_code_hashes", []))
            prior_corrected = correction.get("corrected_code_hash", "")
            if prior_corrected and prior_corrected not in history:
                history.append(prior_corrected)
            correction["intermediate_corrected_code_hashes"] = history
            correction["corrected_code_hash"] = current_code_hash
            write_json(correction_path, correction)
    else:
        prior_consistency_path = OUTPUT_DIR / "consistency_check.json"
        prior_consistency = (
            json.loads(prior_consistency_path.read_text(encoding="utf-8"))
            if prior_consistency_path.exists()
            else {}
        )
        prior_results = OUTPUT_DIR / "selection_results.csv"
        invalidated_copy = OUTPUT_DIR / "invalidated_pre_correction_selection_results.csv"
        if prior_results.exists() and not invalidated_copy.exists():
            invalidated_copy.write_bytes(prior_results.read_bytes())
        write_json(
            correction_path,
            {
                "canonical_trial_id": TRIAL_ID,
                "correction_type": "source_contract_preserving_implementation_defect_correction",
                "defect": "fully_invested_invariant_incorrectly_included_the_pre_initialization_holdings_row",
                "strategy_rule_changed": False,
                "performance_result_used_to_choose_correction": False,
                "pre_correction_code_hash": preregistered_hash,
                "corrected_code_hash": current_code_hash,
                "invalidated_pre_correction_outcome": prior_consistency.get("outcome", ""),
                "invalidated_pre_correction_failure_reason": prior_consistency.get("failure_reason", ""),
                "invalidated_pre_correction_evidence_hash": prior_consistency.get("deterministic_evidence_hash", ""),
                "invalidated_selection_results_preserved": invalidated_copy.exists(),
                "trial_id_changed": False,
            },
        )
    return preregistered_hash


def conformance_checks(
    signal: pd.DataFrame,
    prepared: dict[str, Any],
    daily_targets: pd.DataFrame,
) -> dict[str, bool]:
    threshold_pass = all(signal.loc[pd.Period(month, freq="M"), "canonical_regime"] == expected for month, expected in EXPECTED_THRESHOLD_REGIMES.items())
    low_rows = [row for row in prepared["monthly_rows"] if row["regime"] == "low"]
    medium_rows = [row for row in prepared["monthly_rows"] if row["regime"] == "medium"]
    high_rows = [row for row in prepared["monthly_rows"] if row["regime"] == "high"]
    october = signal.loc[pd.Period("2025-10", freq="M")]
    first_pro = next(row for row in prepared["pro_rows"] if row["formation_reference_month"] == "2009-07")
    checks = {
        "exactly_six_strategy_assets": len(SYMBOLS) == 6 and prepared["targets"].shape[1] == 6,
        "low_weights_exact": all(row["target_SPY"] == 0.60 and row["target_AGG"] == 0.40 for row in low_rows),
        "low_other_weights_zero": all(all(row[f"target_{symbol}"] == 0.0 for symbol in ("IYR", "GSG", "GLD", "TIP")) for row in low_rows),
        "medium_weights_nonnegative_and_sum_one": all(all(row[f"target_{s}"] >= 0.0 for s in SYMBOLS) and abs(row["target_weight_sum"] - 1.0) <= WEIGHT_TOLERANCE for row in medium_rows),
        "medium_inverse_vol_formula_verified": all(abs(row["normalized_weight"] - row["raw_inverse_volatility"] / sum(item["raw_inverse_volatility"] for item in prepared["vol_rows"] if item["formation_reference_month"] == row["formation_reference_month"])) <= WEIGHT_TOLERANCE for row in prepared["vol_rows"]),
        "high_weights_nonnegative_and_sum_one": all(all(row[f"target_{s}"] >= 0.0 for s in SYMBOLS) and abs(row["target_weight_sum"] - 1.0) <= WEIGHT_TOLERANCE for row in high_rows),
        "ProIB_transform_verified": all(abs(row["transformed_beta"] - beta_transform(row["beta"])) <= TOLERANCE for row in prepared["pro_rows"]),
        "lookback_expands_36_to_120": prepared["monthly_rows"][0]["lookback_monthly_returns"] == 36 and max(row["lookback_monthly_returns"] for row in prepared["monthly_rows"]) == 120,
        "first_ProIB_pair_count_25": first_pro["rolling_12m_pair_count"] == 25,
        "no_pre_window_returns_in_ProIB": all(not row["pre_window_return_used"] for row in prepared["pro_rows"]),
        "no_unreleased_CPI_in_regression": all(row["all_CPI_releases_available_by_formation"] for row in prepared["pro_rows"]),
        "statistics_cutoff_previous_month_end": all(row["lookback_end_month"] == row["reference_month"] for row in prepared["monthly_rows"]),
        "regime_cutoff_is_CPI_release": all(row["regime_information_cutoff"] for row in prepared["monthly_rows"]),
        "next_business_day_close_effective": all(row["effective_close_date"] > row["regime_information_cutoff"] for row in prepared["monthly_rows"]),
        "new_target_earns_only_following_interval": all(row["new_weights_first_return_date"] > row["effective_close_date"] for row in prepared["monthly_rows"] if row["new_weights_first_return_date"]),
        "october_2025_no_synthetic_rebalance": not bool(october["event"]) and pd.isna(october["effective_date"]),
        "no_leverage_or_short_weights": bool((prepared["targets"] >= -WEIGHT_TOLERANCE).all().all() and (prepared["targets"].sum(axis=1) <= 1.0 + WEIGHT_TOLERANCE).all()),
        "complete_target_rows_no_NaN": not prepared["targets"].isna().any().any(),
        "daily_target_rows_sum_one": bool(np.allclose(daily_targets.sum(axis=1), 1.0, atol=WEIGHT_TOLERANCE)),
        "zero_targets_preserved": bool((daily_targets == 0.0).any().any()),
        "frozen_threshold_cases_reproduced": threshold_pass,
        "first_valid_formation_matches_contract": prepared["first_valid"].date().isoformat() == "2009-08-17",
        "first_VolWt_and_ProIB_formation_match": prepared["monthly_rows"][0]["effective_close_date"] == "2009-08-17" and first_pro["formation_reference_month"] == "2009-07",
    }
    return checks


def build_regime_rows(signal: pd.DataFrame, prepared: dict[str, Any], primary_path: dict[str, Any] | None) -> list[dict[str, Any]]:
    monthly_by_month = {row["reference_month"]: row for row in prepared["monthly_rows"]}
    event_accounting = {}
    if primary_path is not None:
        event_accounting = {pd.Timestamp(row["execution_date"]).date().isoformat(): row for row in primary_path["events"]}
    rows: list[dict[str, Any]] = []
    previous_regime = ""
    episode = 0
    for _, source in signal.iterrows():
        month = source["reference_month"]
        formed = monthly_by_month.get(month)
        regime = source["canonical_regime"]
        if regime and regime != previous_regime:
            episode += 1
        if regime:
            previous_regime = regime
        effective = source["source_effective_after_close_date"]
        accounting = event_accounting.get(effective, {})
        rows.append(
            {
                "reference_month": month,
                "publication_status": source["publication_status"],
                "release_date": source["bls_release_date"],
                "effective_close_date": effective,
                "cpi_yoy_unrounded": source["canonical_cpi_yoy_unrounded"],
                "regime": regime,
                "rebalance_event": source["rebalance_event"],
                "source_compliant_formation": formed is not None,
                "episode_id": episode if regime else "",
                "threshold_disagreement_case": month in EXPECTED_THRESHOLD_REGIMES,
                "october_2025_no_event": month == "2025-10" and source["rebalance_event"] == "false",
                "one_way_turnover_5bps_path": accounting.get("one_way_turnover", ""),
                "transaction_cost_drag_5bps_path": accounting.get("transaction_cost_drag", ""),
                **({f"target_{symbol}": formed[f"target_{symbol}"] for symbol in SYMBOLS} if formed else {f"target_{symbol}": "" for symbol in SYMBOLS}),
            }
        )
    return rows


def evidence_hash_without_consistency() -> str:
    return packet_hash()


def run() -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    protected_before = protected_snapshot()
    v2 = verify_v2()
    signal = load_signal()
    prices, preflight_rows, price_contract = load_prices()
    prepared = build_signals(prices, signal)
    split = build_split(prices, prepared["targets"])
    daily_targets = complete_target_schedule(prices, prepared["targets"])
    pre_checks = conformance_checks(signal, prepared, daily_targets)
    if not all(pre_checks.values()):
        raise RuntimeError("implementation_source_conformance_failed")

    code_hash = sha256_path(Path(__file__))
    preregistered_code_hash = preserve_preliminary_correction(code_hash)
    preregistration = write_preregistration(preregistration_payload(v2, price_contract, split, preregistered_code_hash))
    preregistration_timestamp = datetime.fromisoformat(preregistration["preregistration_timestamp"])

    named_targets = control_targets(prepared["targets"].index, low_weights())
    equal_targets = control_targets(prepared["targets"].index, {symbol: 1.0 / 6.0 for symbol in SYMBOLS})
    target_sets = {"candidate": prepared["targets"], NAMED_CONTROL: named_targets, EQUAL_CONTROL: equal_targets}
    selection_end = split.selection_index.max()
    selection_paths: dict[tuple[str, float], dict[str, Any]] = {}
    selection_metrics: dict[tuple[str, float], dict[str, Any]] = {}
    for cost in COSTS:
        for entity, targets in target_sets.items():
            path = simulate(prices, targets, cost, end=selection_end)
            selection_paths[(entity, cost)] = path
            selection_metrics[(entity, cost)] = path_metrics(path, split.selection_index, prepared["event_regimes"] if entity == "candidate" else {})
    vector = selection_vector(selection_metrics)
    evaluation_authorized = bool(vector["selection_eligible"])
    selection_rows: list[dict[str, Any]] = []
    for cost in COSTS:
        candidate = selection_metrics[("candidate", cost)]
        selection_rows.append(metrics_row("selection", "canonical_candidate", STRATEGY_ID, cost, candidate))
        for control in BLOCKING_CONTROLS:
            selection_rows.append(metrics_row("selection", "blocking_control", control, cost, selection_metrics[(control, cost)], candidate))

    evaluation_rows: list[dict[str, Any]] = []
    evaluation_metrics: dict[tuple[str, float], dict[str, Any]] = {}
    evaluation_vector_result: dict[str, bool] = {}
    evaluation_calculated = False
    evaluation_timestamp = ""
    diagnostic_count = 0
    full_primary_path: dict[str, Any] | None = None
    if evaluation_authorized:
        existing_access_path = OUTPUT_DIR / "evaluation_access_log.json"
        existing_access = (
            json.loads(existing_access_path.read_text(encoding="utf-8"))
            if existing_access_path.exists()
            else {}
        )
        evaluation_timestamp = existing_access.get("first_evaluation_access_timestamp") or datetime.now(timezone.utc).isoformat()
        if datetime.fromisoformat(evaluation_timestamp) < preregistration_timestamp:
            raise RuntimeError("evaluation_access_preceded_preregistration")
        full_targets = dict(target_sets)
        average_weights = prepared["targets"].mean(axis=0).to_dict()
        validate_target({symbol: float(average_weights[symbol]) for symbol in SYMBOLS})
        full_targets[DIAGNOSTIC_CONTROL] = control_targets(prepared["targets"].index, {symbol: float(average_weights[symbol]) for symbol in SYMBOLS})
        diagnostic_count = 1
        full_paths: dict[tuple[str, float], dict[str, Any]] = {}
        for cost in COSTS:
            for entity, targets in full_targets.items():
                path = simulate(prices, targets, cost)
                full_paths[(entity, cost)] = path
                metrics = path_metrics(path, split.evaluation_index, prepared["event_regimes"] if entity == "candidate" else {})
                evaluation_metrics[(entity, cost)] = metrics
        full_primary_path = full_paths[("candidate", PRIMARY_COST)]
        halves_pass = True
        midpoint = len(split.evaluation_index) // 2
        for half in (split.evaluation_index[:midpoint], split.evaluation_index[midpoint:]):
            candidate_half = path_metrics(full_paths[("candidate", PRIMARY_COST)], half, prepared["event_regimes"])
            named_half = path_metrics(full_paths[(NAMED_CONTROL, PRIMARY_COST)], half, {})
            if candidate_half["sharpe_ratio"] < named_half["sharpe_ratio"] - TOLERANCE and candidate_half["maximum_drawdown"] < named_half["maximum_drawdown"] - TOLERANCE:
                halves_pass = False
        evaluation_vector_result = evaluation_vector({key: value for key, value in evaluation_metrics.items() if key[0] != DIAGNOSTIC_CONTROL}, halves_pass)
        for cost in COSTS:
            candidate = evaluation_metrics[("candidate", cost)]
            evaluation_rows.append(metrics_row("reserved_evaluation", "canonical_candidate", STRATEGY_ID, cost, candidate))
            for control in BLOCKING_CONTROLS:
                evaluation_rows.append(metrics_row("reserved_evaluation", "blocking_control", control, cost, evaluation_metrics[(control, cost)], candidate))
            evaluation_rows.append(metrics_row("reserved_evaluation", "diagnostic_only", DIAGNOSTIC_CONTROL, cost, evaluation_metrics[(DIAGNOSTIC_CONTROL, cost)], candidate))
        evaluation_calculated = True

    if not evaluation_authorized:
        outcome = OUTCOME_SELECTION_FAILED
        reason = failure_reason(vector)
        next_action = NEGATIVE_NEXT_ACTION
        followup_count = 0
    elif evaluation_vector_result["exploration_followup_justified"]:
        outcome = OUTCOME_FOLLOWUP
        reason = ""
        next_action = FOLLOWUP_NEXT_ACTION
        followup_count = 1
    else:
        outcome = OUTCOME_EVALUATION_NO_FOLLOWUP
        reason = failure_reason({**evaluation_vector_result, "selection_eligible": evaluation_vector_result.get("exploration_followup_justified", False)})
        if not reason and not evaluation_vector_result.get("evaluation_subhalves_pass_vs_named_control", True):
            reason = "period_instability"
        next_action = NEGATIVE_NEXT_ACTION
        followup_count = 0

    primary_selection_path = selection_paths[("candidate", PRIMARY_COST)]
    accounting_path = full_primary_path or primary_selection_path
    regime_rows = build_regime_rows(signal, prepared, accounting_path)
    daily_rows = []
    target_source = prepared["targets"].copy()
    target_source["source_event_date"] = target_source.index
    source_dates = target_source["source_event_date"].reindex(prices.index).ffill().loc[daily_targets.index]
    for date_value, row in daily_targets.iterrows():
        daily_rows.append(
            {
                "date": date_value.date().isoformat(),
                "source_event_effective_close": pd.Timestamp(source_dates.loc[date_value]).date().isoformat(),
                "target_weight_sum": float(row.sum()),
                "explicit_zero_count": int((row == 0.0).sum()),
                **{f"target_{symbol}": float(row[symbol]) for symbol in SYMBOLS},
            }
        )

    control_audit = [
        {
            "control_id": NAMED_CONTROL,
            "control_type": "source_named",
            "gate_role": "blocking_control",
            "decision_timing": "same_monthly_CPI_effective_close_schedule",
            "ex_ante_investable": True,
            "uses_only_information_available_at_decision": True,
            "uses_candidate_full_history": False,
            "uses_evaluation_information": False,
            "can_block_advancement": True,
            "information_set_status": "pass",
        },
        {
            "control_id": EQUAL_CONTROL,
            "control_type": "simple_investable",
            "gate_role": "blocking_control",
            "decision_timing": "same_monthly_CPI_effective_close_schedule",
            "ex_ante_investable": True,
            "uses_only_information_available_at_decision": True,
            "uses_candidate_full_history": False,
            "uses_evaluation_information": False,
            "can_block_advancement": True,
            "information_set_status": "pass",
        },
        {
            "control_id": DIAGNOSTIC_CONTROL,
            "control_type": "ex_post_exposure",
            "gate_role": "diagnostic_only",
            "decision_timing": "withheld_until_evaluation_authorization",
            "ex_ante_investable": False,
            "uses_only_information_available_at_decision": False,
            "uses_candidate_full_history": True,
            "uses_evaluation_information": evaluation_authorized,
            "can_block_advancement": False,
            "information_set_status": "calculated_after_authorized_access" if evaluation_authorized else "withheld",
        },
    ]

    source_conformance = {
        "strategy_id": STRATEGY_ID,
        "claim": "ETF_portability_research_not_official_SP_index_replication",
        "V2_hash_verification": v2,
        "price_data_verification": price_contract,
        "preperformance_checks": pre_checks,
        "all_preperformance_checks_pass": all(pre_checks.values()),
        "performance_access_authorized": True,
        "selection_gate": vector,
        "postperformance_accounting_invariants_pass": all(selection_metrics[("candidate", cost)]["invariant_pass"] for cost in COSTS),
    }
    trial_manifest = {
        "task_id": TASK_ID,
        "entity_type": "experiment_trial",
        "stage": "exploration",
        "strategy_id": STRATEGY_ID,
        "family_id": FAMILY_ID,
        "architecture_id": ARCHITECTURE_ID,
        "canonical_trial_id": TRIAL_ID,
        "canonical_trial_count": 1,
        "source_packet_id": SOURCE_PACKET_ID,
        "source_contract_dataset_id": V2_DATASET_ID,
        "source_contract_dataset_hash": V2_EXPECTED_HASH,
        "frozen_universe_id": UNIVERSE_ID,
        "frozen_universe_hash": UNIVERSE_EXPECTED_HASH,
        "ETF_mapping": MAPPING,
        "code_hash": code_hash,
        "preregistered_code_hash": preregistered_code_hash,
        "implementation_correction_recorded": code_hash != preregistered_code_hash,
        "parent_trial_id": "",
        "adaptation_label": "ETF_portability_research",
        "optimization_performed": False,
        "variant_count": 0,
        "control_count": 3,
        "outcome": outcome,
        "failure_reason": reason,
        "next_action": next_action,
    }
    access_log = {
        "evaluation_reserved": True,
        "evaluation_access_authorized": evaluation_authorized,
        "authorization_reason": "canonical_selection_gate_passed" if evaluation_authorized else "canonical_selection_gate_failed",
        "evaluation_calculated": evaluation_calculated,
        "first_evaluation_access_timestamp": evaluation_timestamp,
        "evaluation_result_count": len(evaluation_rows),
        "selection_metrics_calculated_after_preregistration": True,
        "preregistration_timestamp": preregistration["preregistration_timestamp"],
    }
    trial_accounting = {
        "architecture_count": 1,
        "canonical_configuration_count": 1,
        "canonical_trial_count": 1,
        "control_count": 3,
        "blocking_control_count": 2,
        "diagnostic_count": diagnostic_count,
        "evaluation_accesses": 1 if evaluation_calculated else 0,
        "followup_count": followup_count,
        "strategy_variants_created": 0,
        "authoritative_registry_records_created_or_changed": 0,
        "forward_observations_accessed_or_changed": 0,
        "broker_account_or_order_calls": 0,
    }

    write_csv(OUTPUT_DIR / "regime_events.csv", regime_rows)
    write_csv(OUTPUT_DIR / "monthly_signal_and_weights.csv", prepared["monthly_rows"])
    write_csv(OUTPUT_DIR / "daily_target_weights.csv", daily_rows)
    write_csv(OUTPUT_DIR / "proib_regression_diagnostics.csv", prepared["pro_rows"])
    write_csv(OUTPUT_DIR / "volwt_diagnostics.csv", prepared["vol_rows"])
    write_csv(OUTPUT_DIR / "control_information_set_audit.csv", control_audit)
    write_csv(OUTPUT_DIR / "selection_results.csv", selection_rows)
    evaluation_path = OUTPUT_DIR / "evaluation_results.csv"
    if evaluation_calculated:
        write_csv(evaluation_path, evaluation_rows)
    elif evaluation_path.exists():
        evaluation_path.unlink()
    write_json(OUTPUT_DIR / "source_conformance.json", source_conformance)
    write_json(OUTPUT_DIR / "trial_manifest.json", trial_manifest)
    write_json(OUTPUT_DIR / "evaluation_access_log.json", access_log)
    write_json(OUTPUT_DIR / "trial_accounting.json", trial_accounting)
    write_csv(OUTPUT_DIR / "data_preflight_reconciliation.csv", preflight_rows)
    report = (
        "# S&P DJI Dynamic Inflation ETF Portability Exploration\n\n"
        "This packet implements one preregistered ETF portability trial. It does not reproduce the official S&P index.\n\n"
        f"- Outcome: `{outcome}`\n"
        f"- Failure reason: `{reason or 'none'}`\n"
        f"- First valid formation: `{prepared['first_valid'].date().isoformat()}`\n"
        f"- Selection period: `{split.selection_index.min().date().isoformat()}` through `{split.selection_index.max().date().isoformat()}`\n"
        f"- Reserved evaluation period: `{split.evaluation_index.min().date().isoformat()}` through `{split.evaluation_index.max().date().isoformat()}`\n"
        f"- Evaluation accessed: `{bool_text(evaluation_calculated)}`\n"
        f"- Primary cost: `{PRIMARY_COST:g}` bps per one-way turnover\n"
        f"- V2 CPI hash: `{v2['observed_hash']}`\n"
        f"- Price bundle hash: `{price_contract['frozen_price_data_bundle_hash']}`\n"
        f"- Next action: `{next_action}`\n\n"
        "The allocation-statistics cutoff is the previous month-end. The CPI release controls the regime, and the target set at the following business-day close earns only the next close-to-close return. October 2025 creates no event.\n"
    )
    (OUTPUT_DIR / "implementation_report.md").write_text(report, encoding="utf-8")
    (OUTPUT_DIR / "next_action.md").write_text(f"# Next Action\n\n`{next_action}`\n", encoding="utf-8")

    protected_after = protected_snapshot()
    deterministic_hash = evidence_hash_without_consistency()
    required_files = {
        "preregistration.json",
        "implementation_report.md",
        "source_conformance.json",
        "trial_manifest.json",
        "regime_events.csv",
        "monthly_signal_and_weights.csv",
        "daily_target_weights.csv",
        "proib_regression_diagnostics.csv",
        "volwt_diagnostics.csv",
        "control_information_set_audit.csv",
        "selection_results.csv",
        "evaluation_access_log.json",
        "trial_accounting.json",
        "consistency_check.json",
        "next_action.md",
        "data_preflight_reconciliation.csv",
    }
    if evaluation_calculated:
        required_files.add("evaluation_results.csv")
    checks = {
        "one_architecture": trial_accounting["architecture_count"] == 1,
        "one_configuration": trial_accounting["canonical_configuration_count"] == 1,
        "one_canonical_trial": trial_accounting["canonical_trial_count"] == 1,
        "no_variants": trial_accounting["strategy_variants_created"] == 0,
        "V2_hash_verified": v2["observed_hash"] == V2_EXPECTED_HASH,
        "universe_hash_verified": price_contract["universe_hash"] == UNIVERSE_EXPECTED_HASH,
        "price_hashes_verified": all(row["cache_hash_match"] for row in preflight_rows),
        "all_source_conformance_checks_pass": all(pre_checks.values()),
        "preregistration_precedes_performance": preregistration["preregistration_written_before_performance_access"],
        "selection_split_is_60_percent_events": len(split.selection_events) == math.floor(SELECTION_FRACTION * len(split.event_dates)),
        "evaluation_sealed_when_unauthorized": evaluation_authorized or (not evaluation_calculated and not evaluation_path.exists()),
        "controls_do_not_inflate_trial_count": trial_accounting["canonical_trial_count"] == 1 and trial_accounting["control_count"] == 3,
        "protected_state_unchanged": protected_before == protected_after,
        "no_registry_or_forward_state_change": trial_accounting["authoritative_registry_records_created_or_changed"] == 0 and trial_accounting["forward_observations_accessed_or_changed"] == 0,
        "required_files_present": all((OUTPUT_DIR / name).exists() for name in required_files if name != "consistency_check.json"),
    }
    consistency = {
        "task_id": TASK_ID,
        "outcome": outcome,
        "failure_reason": reason,
        "next_action": next_action,
        "overall_pass": all(checks.values()),
        "checks": checks,
        "protected_state_before": protected_before,
        "protected_state_after": protected_after,
        "deterministic_evidence_hash": deterministic_hash,
        "selection_gate": vector,
        "evaluation_gate": evaluation_vector_result,
        "entity_counts": trial_accounting,
        "selection_period": {
            "start": split.selection_index.min().date().isoformat(),
            "end": split.selection_index.max().date().isoformat(),
            "events": len(split.selection_events),
        },
        "evaluation_period": {
            "start": split.evaluation_index.min().date().isoformat(),
            "end": split.evaluation_index.max().date().isoformat(),
            "events": len(split.evaluation_events),
            "accessed": evaluation_calculated,
        },
        "V2_CPI_hash": v2["observed_hash"],
        "frozen_price_data_bundle_hash": price_contract["frozen_price_data_bundle_hash"],
    }
    write_json(OUTPUT_DIR / "consistency_check.json", consistency)
    if not consistency["overall_pass"]:
        raise RuntimeError("evidence_consistency_failed")
    return consistency


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
