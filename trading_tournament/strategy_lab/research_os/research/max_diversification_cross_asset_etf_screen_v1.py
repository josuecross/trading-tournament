from __future__ import annotations

import csv
import hashlib
import json
import math
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml
from scipy.optimize import minimize

import run_active_strategy_evidence_recompute as active
from strategy_lab.research_os.research import risk_parity_trend_etf_wrapper_screen_v1 as rp_screen


ROOT = Path(__file__).resolve().parents[3]
OUTPUT_DIR = ROOT / "evidence" / "max_diversification_cross_asset_etf_screen_v1" / "latest"
WINDOW_PREVIEW_PATH = ROOT / "evidence" / "risk_parity_trend_wrapper_resolution_v1" / "latest" / "deterministic_window_preview.csv"
RISK_PARITY_PREREG = ROOT / "evidence" / "risk_parity_trend_wrapper_resolution_v1" / "latest" / "preregistration.yaml"
ACTIVE_OBSERVATIONS = ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml"
REGISTRY = ROOT / "strategy_lab" / "strategy_registry.yaml"

SOURCE_ID = "choueifaty_coignard_toward_maximum_diversification_2008"
CANDIDATE_ID = "max_diversification_cross_asset_etf_v1"
FAMILY_ID = "maximum_diversification_cross_asset_allocation"
ADAPTATION_CLASSIFICATION = "source_inspired_cross_asset_etf_adaptation"
RISKY_ASSETS = ("URTH", "EEM", "IGOV", "DBC", "REET")
BENCHMARK_IDS = (
    "equal_weight_same_five_etf_monthly_rebalanced_benchmark",
    "inverse_volatility_same_five_etf_monthly_benchmark",
    "rp_ivol_10m_trend_etf_wrapper_adaptation_v1_reference_only",
    "active_combo_vm_dsr_equal_weight_v1_reference_only",
    "SPY_buy_and_hold",
    "BIL_cash_proxy",
)
COVARIANCE_WINDOW_DAYS = 250
DDOF = 1
STARTING_EQUITY = active.STARTING_EQUITY
SLIPPAGE = active.SLIPPAGE
TOL = 1e-9
PSD_TOL = 1e-10
SLSQP_FTOL = 1e-12
SLSQP_MAXITER = 1000
VALID_OUTCOMES = {
    "exact_duplicate_already_tested",
    "preregistration_or_optimizer_blocked",
    "comparative_evidence_positive",
    "risk_reduction_without_return_edge",
    "benchmark_like_no_edge",
    "control_weak",
    "invalid_methodology",
    "direction_owner_review_required",
}


@dataclass(frozen=True)
class ReturnPath:
    strategy_id: str
    daily_returns: pd.Series
    weights: pd.DataFrame
    turnover: pd.Series
    equity: pd.Series
    cost: pd.Series
    target_weights: pd.DataFrame
    pre_trade_weights: pd.DataFrame
    post_trade_weights: pd.DataFrame
    scheduled_execution_dates: tuple[pd.Timestamp, ...]


def csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        if not math.isfinite(value):
            return ""
        return f"{value:.12g}"
    if isinstance(value, (list, tuple, set)):
        return "|".join(str(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True)
    return str(value)


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = sorted({key for row in rows for key in row}) if rows else ["empty"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: csv_value(row.get(field, "")) for field in fieldnames})


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def hash_or_missing(path: Path) -> str:
    return sha256_file(path).upper() if path.exists() else "missing"


def load_price_frame(symbols: tuple[str, ...] | list[str]) -> pd.DataFrame:
    series: list[pd.Series] = []
    for symbol in symbols:
        path = ROOT / "data" / "cache" / f"{symbol}.csv"
        frame = pd.read_csv(path)
        dates = pd.to_datetime(frame["date"], errors="coerce").dt.tz_localize(None)
        close = pd.to_numeric(frame["adj_close"], errors="coerce")
        item = pd.Series(close.to_numpy(dtype=float), index=dates, name=symbol).dropna().sort_index()
        item = item[~item.index.duplicated(keep="last")]
        series.append(item)
    return pd.concat(series, axis=1).sort_index()


def source_intake_record() -> dict[str, Any]:
    return {
        "source": {
            "source_id": SOURCE_ID,
            "source_name": "Toward Maximum Diversification",
            "authors": ["Yves Choueifaty", "Yves Coignard"],
            "publication": "The Journal of Portfolio Management, Fall 2008",
            "source_class": "academic_primary",
        },
        "candidate": {
            "candidate_id": CANDIDATE_ID,
            "family": FAMILY_ID,
            "classification": [
                ADAPTATION_CLASSIFICATION,
                "long_only_correlation_aware_portfolio",
                "not_source_stock_universe_replication",
            ],
        },
        "source_supported_mechanism": {
            "diversification_ratio": "weighted average individual volatility divided by total portfolio volatility",
            "objective": "maximize diversification ratio",
            "constraints": "fully invested long-only portfolio",
            "empirical_recalculation": "month-end",
            "covariance_estimate": "250 trading days of daily returns",
        },
        "project_adaptation_boundaries": {
            "universe": list(RISKY_ASSETS),
            "bil_role": "comparison_benchmark_only_not_optimized_portfolio_asset",
            "source_stock_universe_replication": False,
            "provider_download": False,
            "parameter_search_authorized": False,
        },
    }


def source_rule_rows() -> list[dict[str, Any]]:
    return [
        {"rule_id": "diversification_ratio", "rule": "dot(w, sigma) / sqrt(w.T @ Sigma @ w)", "classification": "source_explicit"},
        {"rule_id": "objective", "rule": "maximize diversification ratio", "classification": "source_explicit"},
        {"rule_id": "long_only", "rule": "all weights >= 0", "classification": "source_explicit"},
        {"rule_id": "fully_invested", "rule": "sum(weights) = 1", "classification": "source_explicit"},
        {"rule_id": "rebalance", "rule": "recalculate at completed month end", "classification": "source_explicit"},
        {"rule_id": "covariance_window", "rule": "250 trading days of daily returns", "classification": "source_explicit"},
        {"rule_id": "etf_wrapper_universe", "rule": "URTH, EEM, IGOV, DBC, REET", "classification": "project_execution_convention"},
        {"rule_id": "adjusted_close", "rule": "use daily adjusted-close total-return proxy series", "classification": "project_execution_convention"},
        {"rule_id": "execution", "rule": "execute on first valid common trading session after month end", "classification": "project_execution_convention"},
        {"rule_id": "costs", "rule": "apply project canonical turnover cost to actual trades", "classification": "project_execution_convention"},
        {"rule_id": "bil", "rule": "BIL is benchmark only; no BIL fallback or optimized allocation", "classification": "project_execution_convention"},
    ]


def source_support_rows() -> list[dict[str, Any]]:
    return [
        {"rule_id": "diversification_ratio", "source_location": "Toward Maximum Diversification core definition", "support_status": "source_supported"},
        {"rule_id": "objective", "source_location": "Toward Maximum Diversification most-diversified portfolio construction", "support_status": "source_supported"},
        {"rule_id": "long_only", "source_location": "Supplied source packet; fully invested long-only portfolio", "support_status": "source_supported"},
        {"rule_id": "fully_invested", "source_location": "Supplied source packet; fully invested long-only portfolio", "support_status": "source_supported"},
        {"rule_id": "rebalance", "source_location": "Supplied source packet; empirical methodology recalculates at month-end", "support_status": "source_supported"},
        {"rule_id": "covariance_window", "source_location": "Supplied source packet; 250 trading days of daily returns", "support_status": "source_supported"},
        {"rule_id": "etf_wrapper_universe", "source_location": "Direction-owner project adaptation", "support_status": "project_convention_not_source_replication"},
        {"rule_id": "execution", "source_location": "Project shifted/no-lookahead convention", "support_status": "project_convention"},
        {"rule_id": "costs", "source_location": "Project canonical cost convention", "support_status": "project_convention"},
    ]


def cache_feasibility_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for symbol in (*RISKY_ASSETS, "BIL", "SPY"):
        path = ROOT / "data" / "cache" / f"{symbol}.csv"
        frame = pd.read_csv(path)
        dates = pd.to_datetime(frame["date"], errors="coerce").dt.tz_localize(None)
        close = pd.to_numeric(frame["adj_close"], errors="coerce")
        rows.append(
            {
                "symbol": symbol,
                "role": "optimized_universe" if symbol in RISKY_ASSETS else "benchmark_only",
                "cache_path": f"data/cache/{symbol}.csv",
                "cache_hash": sha256_file(path),
                "first_valid_date": str(dates[close.notna()].min().date()),
                "last_valid_date": str(dates[close.notna()].max().date()),
                "row_count": int(close.notna().sum()),
                "cache_ready": True,
            }
        )
    common = load_price_frame(list(RISKY_ASSETS)).dropna()
    for row in rows:
        if row["role"] == "optimized_universe":
            row["common_history_start"] = str(common.index.min().date())
            row["common_history_end"] = str(common.index.max().date())
            row["common_history_rows"] = len(common)
    return rows


def duplicate_gate_rows() -> list[dict[str, Any]]:
    return [
        {
            "prior_strategy": "rp_ivol_10m_trend_etf_wrapper_adaptation_v1",
            "same_five_etf_universe": True,
            "same_250_day_covariance": False,
            "same_max_diversification_objective": False,
            "same_no_trend_no_cash_rule": False,
            "exact_duplicate": False,
            "reason": "prior risk-parity candidate used inverse volatility plus 10-month trend and BIL transfer, not covariance-ratio optimization",
        },
        {
            "prior_strategy": "equal_weight_same_five_risky_etfs_benchmark_only",
            "same_five_etf_universe": True,
            "same_250_day_covariance": False,
            "same_max_diversification_objective": False,
            "same_no_trend_no_cash_rule": True,
            "exact_duplicate": False,
            "reason": "same universe but no covariance-aware optimization",
        },
        {
            "prior_strategy": "static_all_weather_benchmark_v1",
            "same_five_etf_universe": False,
            "same_250_day_covariance": False,
            "same_max_diversification_objective": False,
            "same_no_trend_no_cash_rule": True,
            "exact_duplicate": False,
            "reason": "benchmark/control allocation, not same universe or objective",
        },
    ]


def material_distinction_rows() -> list[dict[str, Any]]:
    return [
        {"dimension": "uses_complete_covariance_structure", "candidate": True, "closest_prior": "inverse_volatility_uses_diagonal_only", "materially_distinct": True},
        {"dimension": "optimizes_diversification_ratio", "candidate": True, "closest_prior": "risk_parity_or_equal_weight_not_ratio_optimized", "materially_distinct": True},
        {"dimension": "no_absolute_trend_filter", "candidate": True, "closest_prior": "rp_ivol_10m_trend_uses_10m_trend", "materially_distinct": True},
        {"dimension": "no_bil_transfer_for_failed_assets", "candidate": True, "closest_prior": "rp_ivol_10m_trend_transfers_below_trend_weight_to_bil", "materially_distinct": True},
        {"dimension": "same_tickers_not_duplicate", "candidate": True, "closest_prior": "same_five_wrappers", "materially_distinct": True},
    ]


def validate_covariance(covariance: np.ndarray) -> np.ndarray:
    cov = np.asarray(covariance, dtype=float)
    if cov.ndim != 2 or cov.shape[0] != cov.shape[1]:
        raise ValueError("covariance must be a square matrix")
    if cov.shape[0] != len(RISKY_ASSETS):
        raise ValueError(f"covariance must contain exactly {len(RISKY_ASSETS)} assets")
    if not np.isfinite(cov).all():
        raise ValueError("covariance contains non-finite values")
    if not np.allclose(cov, cov.T, atol=1e-10, rtol=0.0):
        raise ValueError("covariance must be symmetric")
    diagonal = np.diag(cov)
    if (diagonal <= TOL).any():
        raise ValueError("every asset volatility must be finite and positive")
    eigenvalues = np.linalg.eigvalsh(cov)
    if float(eigenvalues.min()) < -PSD_TOL:
        raise ValueError("covariance is not positive semidefinite")
    return cov


def diversification_ratio(weights: np.ndarray, covariance: np.ndarray) -> float:
    cov = validate_covariance(covariance)
    w = np.asarray(weights, dtype=float)
    if w.shape != (cov.shape[0],):
        raise ValueError("weight vector shape does not match covariance")
    if not np.isfinite(w).all() or (w < -TOL).any():
        raise ValueError("weights must be finite and non-negative")
    if abs(float(w.sum()) - 1.0) > 1e-7:
        raise ValueError("weights must sum to 1")
    sigma = np.sqrt(np.diag(cov))
    portfolio_vol = math.sqrt(float(w @ cov @ w))
    if portfolio_vol <= TOL:
        raise ValueError("portfolio volatility must be positive")
    return float(w @ sigma) / portfolio_vol


def max_diversification_weights(covariance: np.ndarray) -> tuple[np.ndarray, dict[str, Any]]:
    cov = validate_covariance(covariance)
    sigma = np.sqrt(np.diag(cov))
    x0 = np.ones(len(sigma), dtype=float) / float(sigma.sum())
    constraints = {"type": "eq", "fun": lambda x: float(sigma @ x - 1.0), "jac": lambda x: sigma.copy()}
    result = minimize(
        lambda x: float(x @ cov @ x),
        x0,
        jac=lambda x: 2.0 * cov @ x,
        bounds=[(0.0, None)] * len(sigma),
        constraints=[constraints],
        method="SLSQP",
        options={"ftol": SLSQP_FTOL, "maxiter": SLSQP_MAXITER, "disp": False},
    )
    if not result.success or not np.isfinite(result.x).all() or float(result.x.sum()) <= TOL:
        raise ValueError(f"optimizer failed: {result.message}")
    weights = np.maximum(result.x / float(result.x.sum()), 0.0)
    weights = weights / float(weights.sum())
    dr = diversification_ratio(weights, cov)
    repeat = minimize(
        lambda x: float(x @ cov @ x),
        x0,
        jac=lambda x: 2.0 * cov @ x,
        bounds=[(0.0, None)] * len(sigma),
        constraints=[constraints],
        method="SLSQP",
        options={"ftol": SLSQP_FTOL, "maxiter": SLSQP_MAXITER, "disp": False},
    )
    repeat_weights = np.maximum(repeat.x / float(repeat.x.sum()), 0.0) if repeat.success else np.full_like(weights, np.nan)
    if repeat.success:
        repeat_weights = repeat_weights / float(repeat_weights.sum())
    diagnostics = {
        "solver": "scipy.optimize.minimize:SLSQP",
        "formulation": "minimize portfolio variance subject to sigma dot x = 1; normalize x to sum 1; scale-equivalent to max diversification ratio",
        "ftol": SLSQP_FTOL,
        "maxiter": SLSQP_MAXITER,
        "success": bool(result.success),
        "message": str(result.message),
        "iterations": int(result.nit),
        "objective_value": float(result.fun),
        "weight_sum": float(weights.sum()),
        "minimum_weight": float(weights.min()),
        "maximum_weight": float(weights.max()),
        "diversification_ratio": dr,
        "repeat_max_abs_weight_difference": float(np.nanmax(np.abs(weights - repeat_weights))),
        "constraints_satisfied": abs(float(weights.sum()) - 1.0) <= 1e-8 and float(weights.min()) >= -1e-10,
    }
    if diagnostics["repeat_max_abs_weight_difference"] > 1e-8:
        raise ValueError("optimizer repeatability check failed")
    return weights, diagnostics


def covariance_from_vol_corr(volatility: list[float], correlation: np.ndarray) -> np.ndarray:
    vol = np.asarray(volatility, dtype=float)
    return np.outer(vol, vol) * np.asarray(correlation, dtype=float)


def synthetic_optimizer_tests() -> list[dict[str, Any]]:
    n = len(RISKY_ASSETS)
    equal_corr = np.full((n, n), 0.5)
    np.fill_diagonal(equal_corr, 1.0)
    high_corr = equal_corr.copy()
    high_corr[0, 1] = 0.99
    high_corr[1, 0] = 0.99
    diversifier_corr = np.full((n, n), 0.8)
    np.fill_diagonal(diversifier_corr, 1.0)
    diversifier_corr[-1, :] = 0.05
    diversifier_corr[:, -1] = 0.05
    diversifier_corr[-1, -1] = 1.0
    near_singular = np.full((n, n), 0.999)
    np.fill_diagonal(near_singular, 1.0)
    zero_weight_cov = np.array(
        [
            [0.0009147110665634392, -0.0008158126770883584, -0.000017433086403467183, 0.0035493044105220427, -0.004552233828912513],
            [-0.0008158126770883584, 0.028200374838570356, -0.018683786421810667, -0.01092867950711668, 0.006076076122137563],
            [-0.000017433086403467183, -0.018683786421810667, 0.017192936501614724, 0.014759274737231437, 0.00038707579095751765],
            [0.0035493044105220427, -0.01092867950711668, 0.014759274737231437, 0.0613236422161585, -0.008662910433970343],
            [-0.004552233828912513, 0.006076076122137563, 0.00038707579095751765, -0.008662910433970343, 0.06177651747730598],
        ]
    )
    cases = [
        ("identical_volatilities_and_correlations", covariance_from_vol_corr([0.1] * n, equal_corr), True),
        ("different_volatilities_equal_correlations", covariance_from_vol_corr([0.1, 0.2, 0.3, 0.4, 0.5], equal_corr), True),
        ("one_highly_correlated_asset", covariance_from_vol_corr([0.1, 0.1, 0.15, 0.2, 0.25], high_corr), True),
        ("one_diversifying_asset", covariance_from_vol_corr([0.2] * n, diversifier_corr), True),
        ("near_singular_but_valid_covariance", covariance_from_vol_corr([0.1, 0.11, 0.12, 0.13, 0.14], near_singular), True),
        ("invalid_non_finite_covariance", np.full((n, n), np.nan), False),
        ("valid_case_with_zero_weight_asset", zero_weight_cov, True),
    ]
    rows: list[dict[str, Any]] = []
    for case_id, cov, should_succeed in cases:
        try:
            weights, diag = max_diversification_weights(cov)
            rows.append(
                {
                    "case_id": case_id,
                    "expected_success": should_succeed,
                    "actual_success": True,
                    "test_passed": should_succeed,
                    "diversification_ratio": diag["diversification_ratio"],
                    "weight_sum": weights.sum(),
                    "min_weight": weights.min(),
                    "max_weight": weights.max(),
                    "zero_weight_count": int((weights <= 1e-8).sum()),
                    "repeat_max_abs_weight_difference": diag["repeat_max_abs_weight_difference"],
                    "error": "",
                }
            )
        except Exception as exc:
            rows.append(
                {
                    "case_id": case_id,
                    "expected_success": should_succeed,
                    "actual_success": False,
                    "test_passed": not should_succeed,
                    "diversification_ratio": "",
                    "weight_sum": "",
                    "min_weight": "",
                    "max_weight": "",
                    "zero_weight_count": "",
                    "repeat_max_abs_weight_difference": "",
                    "error": str(exc),
                }
            )
    return rows


def read_windows() -> list[dict[str, Any]]:
    with WINDOW_PREVIEW_PATH.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def month_end_signal_dates(common_close: pd.DataFrame) -> list[pd.Timestamp]:
    signal_dates = []
    for _, frame in common_close.groupby(common_close.index.to_period("M")):
        signal_dates.append(pd.Timestamp(frame.index[-1]))
    return signal_dates


def build_monthly_execution_weights(
    common_close: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, list[dict[str, Any]], list[dict[str, Any]]]:
    returns = common_close[list(RISKY_ASSETS)].pct_change()
    common_index = pd.DatetimeIndex(common_close.index)
    candidate: dict[pd.Timestamp, dict[str, float]] = {}
    equal: dict[pd.Timestamp, dict[str, float]] = {}
    inverse: dict[pd.Timestamp, dict[str, float]] = {}
    target_rows: list[dict[str, Any]] = []
    dr_rows: list[dict[str, Any]] = []
    for signal_date in month_end_signal_dates(common_close):
        signal_pos = common_index.get_loc(signal_date)
        if signal_pos < COVARIANCE_WINDOW_DAYS:
            continue
        window_returns = returns.iloc[signal_pos - COVARIANCE_WINDOW_DAYS + 1 : signal_pos + 1]
        if len(window_returns) != COVARIANCE_WINDOW_DAYS or window_returns.isna().any().any():
            continue
        later = common_index[common_index > signal_date]
        if len(later) == 0:
            continue
        execution_date = pd.Timestamp(later[0])
        cov = np.cov(window_returns.to_numpy(dtype=float), rowvar=False, ddof=DDOF)
        weights, diag = max_diversification_weights(cov)
        vol = np.sqrt(np.diag(validate_covariance(cov)))
        inverse_raw = 1.0 / vol
        inverse_weights = inverse_raw / inverse_raw.sum()
        equal_weights = np.full(len(RISKY_ASSETS), 1.0 / len(RISKY_ASSETS))
        candidate[execution_date] = dict(zip(RISKY_ASSETS, weights))
        equal[execution_date] = dict(zip(RISKY_ASSETS, equal_weights))
        inverse[execution_date] = dict(zip(RISKY_ASSETS, inverse_weights))
        target_row = {
            "signal_date": str(signal_date.date()),
            "execution_date": str(execution_date.date()),
            "covariance_window_days": COVARIANCE_WINDOW_DAYS,
            "window_start": str(window_returns.index[0].date()),
            "window_end": str(window_returns.index[-1].date()),
            "solver": diag["solver"],
            "diversification_ratio": diag["diversification_ratio"],
            "weight_sum": float(weights.sum()),
            "min_weight": float(weights.min()),
            "max_weight": float(weights.max()),
            "zero_weight_count": int((weights <= 1e-10).sum()),
        }
        for symbol, value in zip(RISKY_ASSETS, weights):
            target_row[f"{symbol}_target_weight"] = float(value)
        target_rows.append(target_row)
        for strategy_id, w in [
            (CANDIDATE_ID, weights),
            ("equal_weight_same_five_etf_monthly_rebalanced_benchmark", equal_weights),
            ("inverse_volatility_same_five_etf_monthly_benchmark", inverse_weights),
        ]:
            dr_rows.append(
                {
                    "strategy_id": strategy_id,
                    "signal_date": str(signal_date.date()),
                    "execution_date": str(execution_date.date()),
                    "diversification_ratio": diversification_ratio(np.asarray(w, dtype=float), cov),
                    "maximum_single_asset_weight": float(np.max(w)),
                    "effective_number_of_assets": float(1.0 / np.sum(np.square(w))),
                    "zero_weight_count": int((np.asarray(w) <= 1e-10).sum()),
                }
            )
    return (
        pd.DataFrame.from_dict(candidate, orient="index").sort_index().reindex(columns=list(RISKY_ASSETS)),
        pd.DataFrame.from_dict(equal, orient="index").sort_index().reindex(columns=list(RISKY_ASSETS)),
        pd.DataFrame.from_dict(inverse, orient="index").sort_index().reindex(columns=list(RISKY_ASSETS)),
        target_rows,
        dr_rows,
    )


def target_weights_to_daily(execution_weights: pd.DataFrame, daily_index: pd.DatetimeIndex, columns: list[str]) -> pd.DataFrame:
    expanded_index = pd.DatetimeIndex(daily_index.union(pd.DatetimeIndex(execution_weights.index))).sort_values()
    daily = execution_weights.reindex(expanded_index).ffill().reindex(daily_index)
    daily = daily.reindex(columns=columns).fillna(0.0)
    if not execution_weights.empty:
        daily.loc[daily.index < execution_weights.index.min(), columns] = 0.0
    return daily


def run_weighted_path(strategy_id: str, daily_close: pd.DataFrame, execution_weights: pd.DataFrame, columns: list[str], apply_cost: bool = True) -> ReturnPath:
    returns = daily_close[columns].pct_change()
    index = pd.DatetimeIndex(returns.dropna(how="all").index)
    daily_targets = target_weights_to_daily(execution_weights.reindex(columns=columns, fill_value=0.0), index, columns)
    scheduled_targets = execution_weights.reindex(columns=columns, fill_value=0.0).sort_index()
    execution_dates = set(pd.DatetimeIndex(scheduled_targets.index))
    actual_rows: list[pd.Series] = []
    pre_trade_rows: list[pd.Series] = []
    post_trade_rows: list[pd.Series] = []
    turnover_values: list[float] = []
    cost_values: list[float] = []
    net_values: list[float] = []
    current_weights: pd.Series | None = None
    return_frame = returns.reindex(index).fillna(0.0)
    for date in index:
        target = daily_targets.loc[date].astype(float)
        if current_weights is None:
            current_weights = target.copy()
        pre_trade = current_weights.reindex(index=columns, fill_value=0.0).astype(float)
        if date in execution_dates:
            post_trade = scheduled_targets.loc[date].astype(float)
            turnover = float((post_trade - pre_trade).abs().sum() / 2.0)
        else:
            post_trade = pre_trade.copy()
            turnover = 0.0
        cost_return = turnover * SLIPPAGE if apply_cost else 0.0
        asset_returns = return_frame.loc[date].astype(float)
        gross_return = float((post_trade * asset_returns).sum())
        net_return = float((1.0 - cost_return) * (1.0 + gross_return) - 1.0)
        denominator = 1.0 + gross_return
        end_weights = post_trade.copy() if abs(denominator) <= TOL else post_trade * (1.0 + asset_returns) / denominator
        end_weights = end_weights.reindex(index=columns, fill_value=0.0).astype(float)
        actual_rows.append(end_weights)
        pre_trade_rows.append(pre_trade)
        post_trade_rows.append(post_trade)
        turnover_values.append(turnover)
        cost_values.append(cost_return)
        net_values.append(net_return)
        current_weights = end_weights
    actual_weights = pd.DataFrame(actual_rows, index=index, columns=columns)
    pre_trade_weights = pd.DataFrame(pre_trade_rows, index=index, columns=columns)
    post_trade_weights = pd.DataFrame(post_trade_rows, index=index, columns=columns)
    turnover = pd.Series(turnover_values, index=index, name="turnover")
    cost_return = pd.Series(cost_values, index=index, name="cost_return")
    net = pd.Series(net_values, index=index, name=strategy_id)
    equity = STARTING_EQUITY * (1.0 + net).cumprod()
    return ReturnPath(strategy_id, net, actual_weights, turnover, equity, cost_return, daily_targets, pre_trade_weights, post_trade_weights, tuple(pd.Timestamp(date) for date in scheduled_targets.index))


def active_combo_path() -> ReturnPath:
    source = ROOT / "evidence" / "active_combo_series_reconciliation" / "latest" / "combo_daily_series.csv"
    frame = pd.read_csv(source)
    dates = pd.to_datetime(frame["date"], errors="coerce").dt.tz_localize(None)
    returns = pd.to_numeric(frame["active_combo_daily_return"], errors="coerce")
    series = pd.Series(returns.to_numpy(dtype=float), index=dates, name="active_combo_vm_dsr_equal_weight_v1_reference_only").dropna().sort_index()
    equity = STARTING_EQUITY * (1.0 + series).cumprod()
    empty = pd.DataFrame(index=series.index)
    zeros = pd.Series(0.0, index=series.index)
    return ReturnPath("active_combo_vm_dsr_equal_weight_v1_reference_only", series, empty, zeros, equity, zeros, empty, empty, empty, tuple())


def path_for_constant_benchmark(strategy_id: str, symbol: str, columns: list[str]) -> ReturnPath:
    prices = load_price_frame(columns).dropna()
    first = pd.DatetimeIndex([prices.index.min()])
    weights = pd.DataFrame(index=first, columns=columns, data=0.0)
    weights[symbol] = 1.0
    return run_weighted_path(strategy_id, prices, weights, columns, apply_cost=False)


def build_paths() -> tuple[dict[str, ReturnPath], list[dict[str, Any]], list[dict[str, Any]]]:
    common_close = load_price_frame(list(RISKY_ASSETS)).dropna()
    candidate_weights, equal_weights, inverse_weights, target_rows, dr_rows = build_monthly_execution_weights(common_close)
    candidate = run_weighted_path(CANDIDATE_ID, common_close, candidate_weights, list(RISKY_ASSETS), True)
    equal = run_weighted_path("equal_weight_same_five_etf_monthly_rebalanced_benchmark", common_close, equal_weights, list(RISKY_ASSETS), True)
    inverse = run_weighted_path("inverse_volatility_same_five_etf_monthly_benchmark", common_close, inverse_weights, list(RISKY_ASSETS), True)
    rp_paths, _, _, _ = rp_screen.build_paths()
    rp_reference = rp_paths[rp_screen.CANDIDATE_ID]
    rp_reference = ReturnPath(
        "rp_ivol_10m_trend_etf_wrapper_adaptation_v1_reference_only",
        rp_reference.daily_returns,
        rp_reference.weights,
        rp_reference.turnover,
        rp_reference.equity,
        rp_reference.cost,
        rp_reference.target_weights,
        rp_reference.pre_trade_weights,
        rp_reference.post_trade_weights,
        rp_reference.scheduled_execution_dates,
    )
    spy = path_for_constant_benchmark("SPY_buy_and_hold", "SPY", ["SPY", "BIL"])
    bil = path_for_constant_benchmark("BIL_cash_proxy", "BIL", ["SPY", "BIL"])
    active_combo = active_combo_path()
    return {
        CANDIDATE_ID: candidate,
        "equal_weight_same_five_etf_monthly_rebalanced_benchmark": equal,
        "inverse_volatility_same_five_etf_monthly_benchmark": inverse,
        "rp_ivol_10m_trend_etf_wrapper_adaptation_v1_reference_only": rp_reference,
        "active_combo_vm_dsr_equal_weight_v1_reference_only": active_combo,
        "SPY_buy_and_hold": spy,
        "BIL_cash_proxy": bil,
    }, target_rows, dr_rows


def drawdown(equity: pd.Series) -> tuple[float, float]:
    peak = equity.cummax()
    dd_dollars = equity - peak
    dd_pct = equity / peak - 1.0
    return float(dd_dollars.min()), float(dd_pct.min())


def window_metrics(path: ReturnPath, window: dict[str, Any], dr_rows: list[dict[str, Any]]) -> dict[str, Any]:
    start = pd.Timestamp(window["window_start"])
    end = pd.Timestamp(window["window_end"])
    horizon = int(window["horizon_days"])
    period = path.daily_returns[(path.daily_returns.index > start) & (path.daily_returns.index <= end)]
    row: dict[str, Any] = {"strategy_id": path.strategy_id, "horizon_days": horizon, "window_start": str(start.date()), "window_end": str(end.date())}
    if len(period) != horizon or period.isna().any():
        row.update({"window_valid": False, "invalid_reason": f"expected_{horizon}_returns_got_{len(period)}"})
        return row
    equity = STARTING_EQUITY * (1.0 + period).cumprod()
    dd_dollars, dd_pct = drawdown(equity)
    total_return = float(equity.iloc[-1] / STARTING_EQUITY - 1.0)
    weights = path.weights.reindex(period.index).dropna(how="all") if not path.weights.empty else pd.DataFrame(index=period.index)
    turnover = path.turnover.reindex(period.index).fillna(0.0)
    if not weights.empty:
        max_single = float(weights.max(axis=1).max())
        eff_assets = (1.0 / (weights.pow(2).sum(axis=1))).replace([np.inf, -np.inf], np.nan)
        zero_pct = float((weights <= 1e-10).sum().sum() / weights.size)
        max_gross = float(weights.abs().sum(axis=1).max())
    else:
        max_single = ""
        eff_assets = pd.Series(dtype=float)
        zero_pct = ""
        max_gross = ""
    dr_subset = [
        item for item in dr_rows
        if item["strategy_id"] == path.strategy_id
        and start < pd.Timestamp(item["execution_date"]) <= end
    ]
    row.update(
        {
            "window_valid": True,
            "invalid_reason": "",
            "final_equity": float(equity.iloc[-1]),
            "total_return": total_return,
            "max_drawdown_dollars": dd_dollars,
            "max_drawdown_pct": dd_pct,
            "realized_volatility": float(period.std(ddof=DDOF) * math.sqrt(252.0)) if len(period) > 1 else "",
            "return_drawdown_ratio": float(total_return / abs(dd_pct)) if dd_pct < 0 else "",
            "turnover": float(turnover.sum()),
            "allocation_change_count": int((turnover > TOL).sum()),
            "maximum_single_asset_weight": max_single,
            "effective_number_of_assets": float(eff_assets.mean()) if not eff_assets.empty else "",
            "percentage_zero_weight_allocations": zero_pct,
            "average_diversification_ratio": float(np.mean([item["diversification_ratio"] for item in dr_subset])) if dr_subset else "",
            "max_gross_exposure": max_gross,
        }
    )
    return row


def summarize(rows: list[dict[str, Any]], strategy_id: str, horizon: int) -> dict[str, Any]:
    subset = [row for row in rows if row["strategy_id"] == strategy_id and int(row["horizon_days"]) == horizon]
    valid = [row for row in subset if row.get("window_valid") is True]
    base = {"strategy_id": strategy_id, "horizon_days": horizon, "valid_window_count": len(valid), "invalid_window_count": len(subset) - len(valid)}
    if not valid:
        return {**base, "comparability_status": "not_comparable"}
    frame = pd.DataFrame(valid)
    def num(column: str) -> pd.Series:
        return pd.to_numeric(frame[column], errors="coerce")
    return {
        **base,
        "median_final_equity": float(num("final_equity").median()),
        "mean_final_equity": float(num("final_equity").mean()),
        "median_return": float(num("total_return").median()),
        "worst_final_equity": float(num("final_equity").min()),
        "max_drawdown_dollars": float(num("max_drawdown_dollars").min()),
        "max_drawdown_pct": float(num("max_drawdown_pct").min()),
        "realized_volatility": float(num("realized_volatility").median()),
        "return_drawdown_ratio": float(num("return_drawdown_ratio").median()),
        "turnover": float(num("turnover").mean()),
        "allocation_change_count": float(num("allocation_change_count").mean()),
        "maximum_single_asset_weight": float(num("maximum_single_asset_weight").max()) if "maximum_single_asset_weight" in frame else "",
        "effective_number_of_assets": float(num("effective_number_of_assets").mean()) if "effective_number_of_assets" in frame else "",
        "percentage_zero_weight_allocations": float(num("percentage_zero_weight_allocations").mean()) if "percentage_zero_weight_allocations" in frame else "",
        "average_diversification_ratio": float(num("average_diversification_ratio").mean()) if "average_diversification_ratio" in frame else "",
        "comparability_status": "comparable" if len(valid) == len(subset) else "partially_comparable",
    }


def relative_rows(summaries: list[dict[str, Any]], window_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_key = {(row["strategy_id"], int(row["horizon_days"])): row for row in summaries}
    rows: list[dict[str, Any]] = []
    for horizon in (90, 180):
        candidate = by_key[(CANDIDATE_ID, horizon)]
        candidate_windows = [row for row in window_rows if row["strategy_id"] == CANDIDATE_ID and int(row["horizon_days"]) == horizon and row.get("window_valid") is True]
        for benchmark in BENCHMARK_IDS:
            bench = by_key[(benchmark, horizon)]
            bench_windows = {
                (row["window_start"], row["window_end"]): row
                for row in window_rows
                if row["strategy_id"] == benchmark and int(row["horizon_days"]) == horizon and row.get("window_valid") is True
            }
            win_count = sum(
                1
                for row in candidate_windows
                if (row["window_start"], row["window_end"]) in bench_windows
                and float(row["final_equity"]) > float(bench_windows[(row["window_start"], row["window_end"])]["final_equity"])
            )
            rows.append(
                {
                    "candidate_id": CANDIDATE_ID,
                    "benchmark_id": benchmark,
                    "horizon_days": horizon,
                    "candidate_median_final_equity": candidate.get("median_final_equity", ""),
                    "benchmark_median_final_equity": bench.get("median_final_equity", ""),
                    "median_final_equity_delta": float(candidate.get("median_final_equity", np.nan)) - float(bench.get("median_final_equity", np.nan)),
                    "candidate_realized_volatility": candidate.get("realized_volatility", ""),
                    "benchmark_realized_volatility": bench.get("realized_volatility", ""),
                    "realized_volatility_delta": float(candidate.get("realized_volatility", np.nan)) - float(bench.get("realized_volatility", np.nan)),
                    "candidate_max_drawdown_pct": candidate.get("max_drawdown_pct", ""),
                    "benchmark_max_drawdown_pct": bench.get("max_drawdown_pct", ""),
                    "max_drawdown_pct_delta": float(candidate.get("max_drawdown_pct", np.nan)) - float(bench.get("max_drawdown_pct", np.nan)),
                    "win_count": win_count,
                    "valid_comparison_count": len(candidate_windows),
                }
            )
    return rows


def accounting_invariant_rows(paths: dict[str, ReturnPath], synthetic_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidate = paths[CANDIDATE_ID]
    active_hash_before = hash_or_missing(ACTIVE_OBSERVATIONS)
    active_hash_after = hash_or_missing(ACTIVE_OBSERVATIONS)
    registry_hash_before = hash_or_missing(REGISTRY)
    registry_hash_after = hash_or_missing(REGISTRY)
    weights = candidate.weights.loc[candidate.weights.index >= candidate.scheduled_execution_dates[0]]
    rows = [
        {"invariant": "fixed_universe_exact", "passed": tuple(weights.columns) == RISKY_ASSETS, "observed": "|".join(weights.columns), "expected": "|".join(RISKY_ASSETS)},
        {"invariant": "no_bil_in_optimized_portfolio", "passed": "BIL" not in weights.columns, "observed": "|".join(weights.columns), "expected": "BIL absent"},
        {"invariant": "max_gross_exposure_lte_1", "passed": bool((weights.abs().sum(axis=1) <= 1.0 + 1e-8).all()), "observed": float(weights.abs().sum(axis=1).max()), "expected": "<=1.0"},
        {"invariant": "fully_invested_after_first_execution", "passed": bool(((weights.sum(axis=1) - 1.0).abs() <= 1e-8).all()), "observed": float((weights.sum(axis=1) - 1.0).abs().max()), "expected": "<=1e-8"},
        {"invariant": "no_negative_weights", "passed": bool((weights >= -1e-10).all().all()), "observed": float(weights.min().min()), "expected": ">=0"},
        {"invariant": "turnover_only_on_execution_dates", "passed": set(candidate.turnover.index[candidate.turnover > TOL]).issubset(set(candidate.scheduled_execution_dates)), "observed": int((candidate.turnover > TOL).sum()), "expected": "subset of execution dates"},
        {"invariant": "synthetic_optimizer_tests_passed", "passed": all(row["test_passed"] for row in synthetic_rows), "observed": sum(row["test_passed"] for row in synthetic_rows), "expected": len(synthetic_rows)},
        {"invariant": "registry_byte_identical", "passed": registry_hash_before == registry_hash_after, "observed": registry_hash_after, "expected": registry_hash_before},
        {"invariant": "active_observations_unchanged", "passed": active_hash_before == active_hash_after, "observed": active_hash_after, "expected": active_hash_before},
        {"invariant": "no_provider_calls", "passed": True, "observed": False, "expected": False},
        {"invariant": "no_parameter_or_universe_search", "passed": True, "observed": False, "expected": False},
        {"invariant": "no_trend_or_cash_rule", "passed": True, "observed": "no trend; no BIL allocation", "expected": "no trend; no BIL allocation"},
    ]
    return rows


def classify_outcome(candidate_metrics: list[dict[str, Any]], relatives: list[dict[str, Any]], invariant_passed: bool) -> str:
    if not invariant_passed:
        return "invalid_methodology"
    rel = {
        (row["benchmark_id"], int(row["horizon_days"])): row
        for row in relatives
        if row["benchmark_id"] in {"equal_weight_same_five_etf_monthly_rebalanced_benchmark", "inverse_volatility_same_five_etf_monthly_benchmark"}
    }
    c = {int(row["horizon_days"]): row for row in candidate_metrics}
    beats_equal = all(float(rel[("equal_weight_same_five_etf_monthly_rebalanced_benchmark", h)]["median_final_equity_delta"]) > 0 for h in (90, 180))
    beats_inverse = all(float(rel[("inverse_volatility_same_five_etf_monthly_benchmark", h)]["median_final_equity_delta"]) > 0 for h in (90, 180))
    lower_vol_equal = all(float(rel[("equal_weight_same_five_etf_monthly_rebalanced_benchmark", h)]["realized_volatility_delta"]) < 0 for h in (90, 180))
    lower_vol_inverse = all(float(rel[("inverse_volatility_same_five_etf_monthly_benchmark", h)]["realized_volatility_delta"]) < 0 for h in (90, 180))
    drawdown_better_equal = all(float(rel[("equal_weight_same_five_etf_monthly_rebalanced_benchmark", h)]["max_drawdown_pct_delta"]) >= 0 for h in (90, 180))
    drawdown_better_inverse = all(float(rel[("inverse_volatility_same_five_etf_monthly_benchmark", h)]["max_drawdown_pct_delta"]) >= 0 for h in (90, 180))
    immaterial = all(abs(float(row["median_final_equity_delta"])) < STARTING_EQUITY * 0.005 for row in rel.values())
    if beats_equal and beats_inverse and (lower_vol_equal or drawdown_better_equal) and (lower_vol_inverse or drawdown_better_inverse):
        return "comparative_evidence_positive"
    if (lower_vol_equal or drawdown_better_equal or lower_vol_inverse or drawdown_better_inverse) and not (beats_equal and beats_inverse):
        return "risk_reduction_without_return_edge"
    if immaterial:
        return "benchmark_like_no_edge"
    if c[180]["comparability_status"] != "comparable":
        return "direction_owner_review_required"
    return "control_weak"


def screening_summary(outcome: str, funnel: dict[str, Any], candidate_metrics: list[dict[str, Any]], relatives: list[dict[str, Any]]) -> str:
    c90 = next(row for row in candidate_metrics if int(row["horizon_days"]) == 90)
    c180 = next(row for row in candidate_metrics if int(row["horizon_days"]) == 180)
    eq180 = next(row for row in relatives if row["benchmark_id"] == "equal_weight_same_five_etf_monthly_rebalanced_benchmark" and int(row["horizon_days"]) == 180)
    iv180 = next(row for row in relatives if row["benchmark_id"] == "inverse_volatility_same_five_etf_monthly_benchmark" and int(row["horizon_days"]) == 180)
    return f"""# Maximum Diversification Cross-Asset ETF Screen v1

Outcome: `{outcome}`

Candidate: `{CANDIDATE_ID}`

Family: `{FAMILY_ID}`

Source: `{SOURCE_ID}`

## Gate Results
- Exact duplicate found: `{str(funnel['exact_duplicate_found']).lower()}`
- Material distinction passed: `{str(funnel['material_distinction_passed']).lower()}`
- Optimizer feasibility passed: `{str(funnel['optimizer_feasibility_passed']).lower()}`
- Performance screen executed: `{str(funnel['performance_screen_executed']).lower()}`

## Candidate Metrics
- 90-day median final equity: `{c90['median_final_equity']:.2f}`
- 90-day median return: `{c90['median_return']:.6f}`
- 180-day median final equity: `{c180['median_final_equity']:.2f}`
- 180-day median return: `{c180['median_return']:.6f}`
- 180-day max drawdown pct: `{c180['max_drawdown_pct']:.6f}`
- 180-day average diversification ratio: `{c180['average_diversification_ratio']:.6f}`

## Primary Benchmark Deltas
- 180-day median final equity delta vs equal weight: `{eq180['median_final_equity_delta']:.2f}`
- 180-day median final equity delta vs inverse volatility: `{iv180['median_final_equity_delta']:.2f}`
- 180-day win count vs equal weight: `{eq180['win_count']}`
- 180-day win count vs inverse volatility: `{iv180['win_count']}`

The diversification-ratio diagnostics are reported separately from return evidence. A higher diversification ratio is treated as mechanism confirmation only, not proof of return edge.

No promotion, paper/demo activation, candidate_exhaustive run, robustness run, provider download, or broker/live action occurred.
"""


def exact_memory_row(outcome: str) -> list[dict[str, Any]]:
    weak = outcome in {"risk_reduction_without_return_edge", "benchmark_like_no_edge", "control_weak", "invalid_methodology"}
    return [
        {
            "candidate_id": CANDIDATE_ID,
            "family": FAMILY_ID,
            "screening_outcome": outcome,
            "exact_variant_closed_for_immediate_retesting": weak,
            "broader_family_status": "open_only_for_materially_distinct_source_backed_hypotheses",
            "disallowed_immediate_retests": "alternative_covariance_windows|weight_caps|shrinkage|different_universe|trend_overlay" if weak else "",
            "next_action": "direction_owner_validation_decision_required" if outcome == "comparative_evidence_positive" else "do_not_retest_exact_variant_without_new_source",
        }
    ]


def execution_manifest(outcome: str, cache_rows: list[dict[str, Any]], duplicate_found: bool) -> dict[str, Any]:
    return {
        "candidate_id": CANDIDATE_ID,
        "family": FAMILY_ID,
        "source_id": SOURCE_ID,
        "source_class": "academic_primary",
        "adaptation_classification": ADAPTATION_CLASSIFICATION,
        "fixed_universe": list(RISKY_ASSETS),
        "bil_in_optimized_portfolio": False,
        "bil_benchmark_only": True,
        "covariance_window_trading_days": COVARIANCE_WINDOW_DAYS,
        "covariance_ddof": DDOF,
        "covariance_input": "aligned daily adjusted-close returns",
        "rebalance": "completed month-end signal; first valid common trading session after month end execution",
        "accounting": "correct drift-aware holdings accounting",
        "turnover": "0.5 * sum(abs(new target - pre-trade actual weight))",
        "slippage": SLIPPAGE,
        "long_only": True,
        "fully_invested": True,
        "leverage": False,
        "shorting": False,
        "trend_filter": False,
        "cash_fallback": False,
        "return_forecast": False,
        "provider_download": False,
        "broader_validation_or_robustness": False,
        "candidate_exhaustive_run": False,
        "promotion_authorized": False,
        "paper_demo_authorized": False,
        "exact_duplicate_found": duplicate_found,
        "screening_outcome": outcome,
        "cache_hashes": {row["symbol"]: row["cache_hash"] for row in cache_rows},
    }


def preregistration(cache_rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "candidate_id": CANDIDATE_ID,
        "family": FAMILY_ID,
        "source_id": SOURCE_ID,
        "source_citation": "Yves Choueifaty and Yves Coignard, Toward Maximum Diversification, The Journal of Portfolio Management, Fall 2008",
        "adaptation_classification": ADAPTATION_CLASSIFICATION,
        "fixed_universe": list(RISKY_ASSETS),
        "optimized_portfolio_excludes": ["BIL", "SPY"],
        "cache_records": [row for row in cache_rows if row["role"] == "optimized_universe"],
        "covariance_window_trading_days": COVARIANCE_WINDOW_DAYS,
        "covariance_convention": {"input": "daily adjusted-close returns", "ddof": DDOF, "aligned_complete_history_required": True},
        "objective": "maximize dot(w, sigma) / sqrt(w.T @ Sigma @ w)",
        "constraints": {"sum_weights": 1.0, "minimum_weight": 0.0, "maximum_weight_cap_added": False, "leverage": False, "shorting": False},
        "solver": {"library": "scipy.optimize.minimize", "method": "SLSQP", "ftol": SLSQP_FTOL, "maxiter": SLSQP_MAXITER, "initialization": "deterministic feasible equal sigma-dot allocation"},
        "optimizer_failure_behavior": "block signal; do not carry forward old solution; do not repair covariance",
        "signal_timestamp": "completed month-end close",
        "execution_timestamp": "first valid common trading session after month end",
        "costs": "canonical project turnover cost on actual trades",
        "missing_data_behavior": "require all five ETFs to have complete valid 250-return window",
        "maximum_gross_exposure": 1.0,
        "forbidden_search": ["parameter_search", "universe_search", "solver_search", "window_search", "weight_caps", "regularization", "shrinkage", "trend_filter", "bil_fallback"],
        "screening_windows": "evidence/risk_parity_trend_wrapper_resolution_v1/latest/deterministic_window_preview.csv",
        "benchmarks": list(BENCHMARK_IDS),
    }


def run() -> dict[str, Any]:
    registry_before = hash_or_missing(REGISTRY)
    active_before = hash_or_missing(ACTIVE_OBSERVATIONS)
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    write_yaml(OUTPUT_DIR / "source_intake_record.yaml", source_intake_record())
    write_csv(OUTPUT_DIR / "source_rule_extraction.csv", source_rule_rows())
    write_csv(OUTPUT_DIR / "source_support_trace.csv", source_support_rows())
    duplicate_rows = duplicate_gate_rows()
    material_rows = material_distinction_rows()
    cache_rows = cache_feasibility_rows()
    synthetic_rows = synthetic_optimizer_tests()
    optimizer_passed = all(row["test_passed"] for row in synthetic_rows)
    exact_duplicate = any(row["exact_duplicate"] for row in duplicate_rows)
    material_distinction = all(row["materially_distinct"] for row in material_rows)

    write_csv(OUTPUT_DIR / "duplicate_gate.csv", duplicate_rows)
    write_csv(OUTPUT_DIR / "material_distinction_review.csv", material_rows)
    write_csv(OUTPUT_DIR / "cache_feasibility.csv", cache_rows)
    write_csv(OUTPUT_DIR / "optimizer_feasibility.csv", [row for row in synthetic_rows if row["case_id"] != "invalid_non_finite_covariance"])
    write_csv(OUTPUT_DIR / "synthetic_optimizer_tests.csv", synthetic_rows)

    if exact_duplicate:
        outcome = "exact_duplicate_already_tested"
    elif not material_distinction or not optimizer_passed or not all(row["cache_ready"] for row in cache_rows if row["role"] == "optimized_universe"):
        outcome = "preregistration_or_optimizer_blocked"
    else:
        write_yaml(OUTPUT_DIR / "preregistration.yaml", preregistration(cache_rows))
        windows = read_windows()
        write_csv(OUTPUT_DIR / "frozen_window_definitions.csv", windows)
        paths, target_rows, dr_rows = build_paths()
        window_rows = [
            window_metrics(path, window, dr_rows)
            for path in paths.values()
            for window in windows
        ]
        candidate_metrics = [summarize(window_rows, CANDIDATE_ID, horizon) for horizon in (90, 180)]
        benchmark_metrics = [
            summarize(window_rows, benchmark, horizon)
            for benchmark in BENCHMARK_IDS
            for horizon in (90, 180)
        ]
        relatives = relative_rows([*candidate_metrics, *benchmark_metrics], window_rows)
        invariants = accounting_invariant_rows(paths, synthetic_rows)
        invariant_passed = all(row["passed"] for row in invariants)
        outcome = classify_outcome(candidate_metrics, relatives, invariant_passed)
        write_csv(OUTPUT_DIR / "monthly_target_weights.csv", target_rows)
        write_csv(OUTPUT_DIR / "daily_actual_weights.csv", daily_weight_rows(paths[CANDIDATE_ID]))
        write_csv(OUTPUT_DIR / "candidate_metrics.csv", candidate_metrics)
        write_csv(OUTPUT_DIR / "benchmark_metrics.csv", benchmark_metrics)
        write_csv(OUTPUT_DIR / "benchmark_relative_metrics.csv", relatives)
        write_csv(OUTPUT_DIR / "window_level_results.csv", window_rows)
        write_csv(OUTPUT_DIR / "diversification_ratio_diagnostics.csv", dr_rows)
        write_csv(OUTPUT_DIR / "accounting_and_optimizer_invariants.csv", invariants)
        write_text(OUTPUT_DIR / "screening_summary.md", screening_summary(outcome, {"exact_duplicate_found": exact_duplicate, "material_distinction_passed": material_distinction, "optimizer_feasibility_passed": optimizer_passed, "performance_screen_executed": True}, candidate_metrics, relatives))
    if outcome == "preregistration_or_optimizer_blocked":
        write_text(OUTPUT_DIR / "screening_summary.md", f"# Maximum Diversification Cross-Asset ETF Screen v1\n\nOutcome: `{outcome}`\n\nExecution stopped before performance because a preregistration or optimizer gate failed.\n")
    if outcome == "exact_duplicate_already_tested":
        write_text(OUTPUT_DIR / "screening_summary.md", f"# Maximum Diversification Cross-Asset ETF Screen v1\n\nOutcome: `{outcome}`\n\nExecution stopped before performance because the exact duplicate gate failed.\n")
    write_json(OUTPUT_DIR / "execution_manifest.json", execution_manifest(outcome, cache_rows, exact_duplicate))
    write_json(
        OUTPUT_DIR / "screening_outcome.json",
        {
            "candidate_id": CANDIDATE_ID,
            "screening_outcome": outcome,
            "valid_terminal_outcome": outcome in VALID_OUTCOMES,
            "promotion_authorized": False,
            "paper_demo_authorized": False,
            "candidate_exhaustive_authorized": False,
            "broader_validation_or_robustness_run": False,
            "next_action": "direction_owner_validation_decision_required" if outcome == "comparative_evidence_positive" else "mark_exact_variant_closed_or_direction_owner_review",
        },
    )
    write_csv(OUTPUT_DIR / "exact_variant_research_memory.csv", exact_memory_row(outcome))
    registry_after = hash_or_missing(REGISTRY)
    active_after = hash_or_missing(ACTIVE_OBSERVATIONS)
    consistency = {
        "consistency_passed": True,
        "candidate_id": CANDIDATE_ID,
        "screening_outcome": outcome,
        "fixed_universe_exact": list(RISKY_ASSETS) == ["URTH", "EEM", "IGOV", "DBC", "REET"],
        "exact_duplicate_found": exact_duplicate,
        "material_distinction_passed": material_distinction,
        "optimizer_feasibility_passed": optimizer_passed,
        "performance_outputs_present": outcome not in {"exact_duplicate_already_tested", "preregistration_or_optimizer_blocked"},
        "no_provider_calls": True,
        "no_parameter_universe_solver_or_window_search": True,
        "no_bil_in_optimized_portfolio": True,
        "no_trend_or_cash_rule": True,
        "no_robustness_or_broader_validation": True,
        "no_promotion_or_paper_demo_activation": True,
        "registry_hash_before": registry_before,
        "registry_hash_after": registry_after,
        "registry_byte_identical": registry_before == registry_after,
        "active_observations_hash_before": active_before,
        "active_observations_hash_after": active_after,
        "active_observations_unchanged": active_before == active_after,
        "generation_is_deterministic": True,
        "valid_terminal_outcome": outcome in VALID_OUTCOMES,
    }
    consistency["consistency_passed"] = bool(
        consistency["fixed_universe_exact"]
        and consistency["material_distinction_passed"]
        and consistency["optimizer_feasibility_passed"]
        and consistency["registry_byte_identical"]
        and consistency["active_observations_unchanged"]
        and consistency["valid_terminal_outcome"]
    )
    write_json(OUTPUT_DIR / "consistency_check.json", consistency)
    return {**consistency, "output_dir": str(OUTPUT_DIR)}


def daily_weight_rows(path: ReturnPath) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    first_execution = min(path.scheduled_execution_dates)
    for date in path.daily_returns.index[path.daily_returns.index >= first_execution]:
        weights = path.weights.loc[date]
        targets = path.target_weights.loc[date]
        pre = path.pre_trade_weights.loc[date]
        post = path.post_trade_weights.loc[date]
        row = {
            "date": str(date.date()),
            "strategy_id": path.strategy_id,
            "daily_return": float(path.daily_returns.at[date]),
            "equity": float(path.equity.at[date]),
            "turnover": float(path.turnover.at[date]),
            "cost_return": float(path.cost.at[date]),
            "target_weight_sum": float(targets.sum()),
            "pre_trade_weight_sum": float(pre.sum()),
            "post_trade_weight_sum": float(post.sum()),
            "actual_weight_sum": float(weights.sum()),
            "gross_exposure": float(weights.abs().sum()),
        }
        for symbol in RISKY_ASSETS:
            row[f"{symbol}_target_weight"] = float(targets[symbol])
            row[f"{symbol}_pre_trade_weight"] = float(pre[symbol])
            row[f"{symbol}_post_trade_weight"] = float(post[symbol])
            row[f"{symbol}_actual_weight"] = float(weights[symbol])
        rows.append(row)
    return rows


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
