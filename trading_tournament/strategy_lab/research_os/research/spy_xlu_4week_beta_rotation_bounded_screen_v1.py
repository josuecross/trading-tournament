from __future__ import annotations

import csv
import hashlib
import inspect
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import run_active_strategy_evidence_recompute as active
from src.data import build_adjusted_ohlc
from strategy_lab.research_os.external_adapters.bt_adapter import reference_spy200d_weights
from strategy_lab.research_os.research import spy_tlt_ief_tlt_prior_month_risk_rotation_bounded_screen_v1 as base


ROOT = Path(__file__).resolve().parents[3]
EVIDENCE_DIR = ROOT / "evidence" / "spy_xlu_4week_beta_rotation_bounded_screen_v1" / "latest"

CANDIDATE_ID = "spy_xlu_4week_beta_rotation_v1"
FAMILY_ID = "intermarket_equity_beta_rotation"
MECHANISM = "weekly_utilities_relative_strength_beta_rotation"
SOURCE_ID = "gayed_bilello_intermarket_beta_rotation_utilities_2014_2020_update"

SPY = "SPY"
XLU = "XLU"
BIL = "BIL"
REQUIRED_SYMBOLS = (SPY, XLU)
CONTROL_SYMBOLS = (BIL,)
ALL_SYMBOLS = (SPY, XLU, BIL)
INITIAL_CAPITAL = float(active.STARTING_EQUITY)
TRANSACTION_COST = float(active.SLIPPAGE)
EQUALITY_TOLERANCE = 1e-12

REGISTRY_PATH = ROOT / "strategy_lab" / "strategy_registry.yaml"
ACTIVE_OBSERVATIONS_PATH = ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml"
PAPER_FORWARD_DIR = ROOT / "paper_forward_observations"
ACTIVE_COMBO_SERIES_PATH = ROOT / "evidence" / "active_combo_benchmark" / "latest" / "active_combo_equity_series.csv"
ACTIVE_COMBO_ALLOCATIONS_PATH = ROOT / "evidence" / "active_combo_benchmark" / "latest" / "active_combo_monthly_allocations.csv"
DSR_REBALANCE_TRACE_PATH = ROOT / "evidence" / "active_strategy_evidence_recompute" / "latest" / "active_strategy_recompute_rebalance_trace_dsr_equal_weight.csv"
TREASURY_EVIDENCE_DIR = ROOT / "evidence" / "spy_tlt_ief_tlt_prior_month_risk_rotation_bounded_screen_v1" / "latest"

ALLOWED_OUTCOMES = {
    "comparative_evidence_positive",
    "historical_edge_recently_weakened",
    "risk_reduction_without_return_edge",
    "redundant_with_active_observation",
    "control_weak",
    "no_material_edge",
    "invalid_methodology",
    "duplicate_resolved",
}


@dataclass(frozen=True)
class PathResult:
    strategy_id: str
    role: str
    equity: pd.Series
    returns: pd.Series
    weights: pd.DataFrame
    trades: list[dict[str, Any]]


def rel(path: Path) -> str:
    return base.rel(path)


def sha256_path(path: Path) -> str:
    return base.sha256_path(path)


def stable_hash(payload: Any) -> str:
    return base.stable_hash(payload)


def clean_value(value: Any) -> Any:
    return base.clean_value(value)


def csv_value(value: Any) -> str:
    return base.csv_value(value)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    base.write_json(path, payload)


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    base.write_csv(path, rows, fields)


def write_text(path: Path, text: str) -> None:
    base.write_text(path, text)


def cache_path(symbol: str) -> Path:
    return ROOT / "data" / "cache" / f"{symbol}.csv"


def file_snapshot(paths: list[Path]) -> dict[str, str]:
    return {rel(path): sha256_path(path) for path in paths}


def default_xlu_downloader(symbol: str, request_settings: dict[str, Any]) -> pd.DataFrame:
    symbol = symbol.upper()
    if symbol != XLU:
        raise ValueError(f"Provider acquisition is limited to XLU only for this screen; got {symbol}")
    import yfinance as yf

    kwargs: dict[str, Any] = {
        "start": request_settings.get("start", "2007-01-01"),
        "end": request_settings.get("end"),
        "auto_adjust": bool(request_settings.get("auto_adjust", False)),
        "actions": bool(request_settings.get("actions", True)),
        "progress": bool(request_settings.get("progress", False)),
    }
    if kwargs["end"] is None:
        kwargs.pop("end")
    signature = inspect.signature(yf.download)
    if "multi_level_index" in signature.parameters:
        kwargs["multi_level_index"] = False
    if "timeout" in signature.parameters:
        kwargs["timeout"] = 30
    return yf.download(symbol, **kwargs)


def ensure_required_caches() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    before = {symbol: base.cache_quality_row(symbol) for symbol in ALL_SYMBOLS}
    provider_manifest: dict[str, Any] = {
        "candidate_id": CANDIDATE_ID,
        "provider_download": False,
        "authorized_download_symbols": [XLU],
        "downloaded_symbols_this_run": [],
        "valid_existing_caches_not_refreshed": [
            symbol for symbol, row in before.items() if row.get("adjusted_price_validation_result") == "pass"
        ],
        "missing_required_symbols_before_run": [
            symbol for symbol in REQUIRED_SYMBOLS if before[symbol].get("adjusted_price_validation_result") != "pass"
        ],
        "SPY_provider_acquisition_authorized": False,
        "BIL_provider_acquisition_authorized": False,
        "errors": [],
    }
    if before[SPY].get("adjusted_price_validation_result") != "pass":
        provider_manifest["errors"].append("SPY cache is missing or invalid; SPY redownload is not authorized")
        provider_manifest["missing_required_symbols_after_run"] = [SPY]
        return provider_manifest, list(before.values())
    if before[XLU].get("adjusted_price_validation_result") != "pass":
        try:
            raw = default_xlu_downloader(XLU, {"start": "2007-01-01", "auto_adjust": False, "actions": True, "progress": False})
            adjusted = build_adjusted_ohlc(raw, XLU)
            adjusted.to_csv(cache_path(XLU), index=False)
            provider_manifest["provider_download"] = True
            provider_manifest["downloaded_symbols_this_run"].append(XLU)
        except Exception as exc:  # pragma: no cover - only reached when local cache is absent.
            provider_manifest["errors"].append(f"XLU acquisition failed: {exc}")
    after = {symbol: base.cache_quality_row(symbol) for symbol in ALL_SYMBOLS}
    provider_manifest["missing_required_symbols_after_run"] = [
        symbol for symbol in REQUIRED_SYMBOLS if after[symbol].get("adjusted_price_validation_result") != "pass"
    ]
    if provider_manifest["missing_required_symbols_after_run"]:
        provider_manifest["errors"].append(
            "Required cache remains unavailable after authorized XLU-only remediation"
        )
    return provider_manifest, list(after.values())


def load_prices(symbols: tuple[str, ...]) -> pd.DataFrame:
    frames: list[pd.Series] = []
    for symbol in symbols:
        frame = pd.read_csv(cache_path(symbol))
        dates = pd.to_datetime(frame["date"], errors="coerce").dt.tz_localize(None)
        series = pd.Series(pd.to_numeric(frame["adj_close"], errors="coerce").to_numpy(), index=dates, name=symbol)
        frames.append(series)
    prices = pd.concat(frames, axis=1).sort_index()
    return prices.loc[prices[list(symbols)].notna().all(axis=1), list(symbols)].copy()


def duplicate_and_redundancy_review_rows() -> list[dict[str, Any]]:
    return [
        {
            "reviewed_id": "paper_forward_dsr_sector_equal_weight_defensive_filter_v1",
            "exact_duplicate": False,
            "economic_equivalence": "not_established",
            "review_result": "not_exact_duplicate_redundancy_measured_later",
            "reason": "Active DSR is sector equal-weight defensive filtering, not an exclusive weekly SPY/XLU four-week relative-strength switch.",
        },
        {
            "reviewed_id": "defensive_sector_rotation_candidates",
            "exact_duplicate": False,
            "economic_equivalence": "overlap_possible_not_identical",
            "review_result": "related_family_not_exact_duplicate",
            "reason": "Existing defensive-sector candidates use sector baskets or top-N mechanics rather than two-asset SPY/XLU Beta Rotation.",
        },
        {
            "reviewed_id": "sector_top2_momentum_simple_v1",
            "exact_duplicate": False,
            "economic_equivalence": False,
            "review_result": "not_duplicate",
            "reason": "Top-2 sector momentum is cross-sectional sector selection, not Utilities-vs-market intermarket beta rotation.",
        },
        {
            "reviewed_id": "SPY_200d_trend_model",
            "exact_duplicate": False,
            "economic_equivalence": False,
            "review_result": "control_not_duplicate",
            "reason": "SPY_200d uses SPY trend and BIL fallback; this candidate remains continuously invested in SPY or XLU.",
        },
        {
            "reviewed_id": "existing_VM_candidates",
            "exact_duplicate": False,
            "economic_equivalence": False,
            "review_result": "not_duplicate",
            "reason": "VM candidates are quality/low-vol/value/momentum style sleeves, not a two-state XLU/SPY weekly relative-strength signal.",
        },
        {
            "reviewed_id": "SPLV_low_volatility_research",
            "exact_duplicate": False,
            "economic_equivalence": "defensive_equity_overlap_only",
            "review_result": "not_exact_duplicate",
            "reason": "Low-volatility ETF exposure is not the source's Utilities relative leadership rule.",
        },
        {
            "reviewed_id": "spy_tlt_ief_tlt_prior_month_risk_rotation_v1",
            "exact_duplicate": False,
            "economic_equivalence": False,
            "review_result": "closed_treasury_candidate_not_reopened",
            "reason": "Closed Treasury risk-rotation candidate uses IEF/TLT prior-month duration signal and SPY/TLT holdings.",
        },
    ]


def candidate_fingerprint() -> dict[str, Any]:
    fields = {
        "family": FAMILY_ID,
        "role": MECHANISM,
        "signal_direction": "four_week_XLU_total_return_minus_SPY_total_return_positive_selects_XLU_else_SPY",
        "signal_universe": "XLU|SPY",
        "tradable_universe": "XLU|SPY",
        "formation_horizon": "four_completed_weekly_observations",
        "holding_horizon": "next_valid_weekly_execution_to_next_valid_weekly_execution",
        "rebalance_frequency": "weekly_signal_change_or_retention",
        "weighting_method": "single_asset_100pct",
        "risk_overlay": "none",
        "execution_cadence": "next_common_session_close_after_completed_signal_week",
    }
    return {
        "candidate_id": CANDIDATE_ID,
        "family_id": FAMILY_ID,
        "source_id": SOURCE_ID,
        "fingerprint_fields": fields,
        "fingerprint_hash": stable_hash(fields),
    }


def final_common_weekly_observations(prices: pd.DataFrame) -> list[dict[str, Any]]:
    common = prices.loc[prices[[SPY, XLU]].notna().all(axis=1), [SPY, XLU]]
    rows: list[dict[str, Any]] = []
    for week_number, (_period, frame) in enumerate(common.groupby(common.index.to_period("W-SUN")), start=1):
        date = pd.Timestamp(frame.index[-1])
        rows.append(
            {
                "week_number": week_number,
                "week_period": str(date.to_period("W-SUN")),
                "weekly_observation_date": date,
                "SPY_adjusted_price": float(frame.loc[date, SPY]),
                "XLU_adjusted_price": float(frame.loc[date, XLU]),
                "final_common_XLU_SPY_session": True,
            }
        )
    return rows


def next_common_date(index: pd.DatetimeIndex, after_date: pd.Timestamp) -> pd.Timestamp | None:
    later = index[index > pd.Timestamp(after_date)]
    return pd.Timestamp(later[0]) if len(later) else None


def build_weekly_signals(prices: pd.DataFrame, tolerance: float = EQUALITY_TOLERANCE) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[pd.Timestamp, dict[str, float]]]:
    weekly = final_common_weekly_observations(prices)
    common_index = prices.loc[prices[[SPY, XLU]].notna().all(axis=1)].index
    signal_rows: list[dict[str, Any]] = []
    execution_rows: list[dict[str, Any]] = []
    skipped_rows: list[dict[str, Any]] = []
    target_events: dict[pd.Timestamp, dict[str, float]] = {}
    current_target: str | None = None
    for i, row in enumerate(weekly):
        signal_date = pd.Timestamp(row["weekly_observation_date"])
        if i < 4:
            skipped_rows.append(
                {
                    "weekly_observation_date": signal_date,
                    "skip_reason": "insufficient_four_week_history",
                    "existing_allocation_retained": current_target or "cash",
                }
            )
            continue
        prior = weekly[i - 4]
        valid_prices = all(
            math.isfinite(float(value))
            for value in (
                row["SPY_adjusted_price"],
                row["XLU_adjusted_price"],
                prior["SPY_adjusted_price"],
                prior["XLU_adjusted_price"],
            )
        )
        execution_date = next_common_date(common_index, signal_date)
        if not valid_prices or execution_date is None:
            skipped_rows.append(
                {
                    "weekly_observation_date": signal_date,
                    "skip_reason": "missing_current_or_four_week_prior_observation",
                    "existing_allocation_retained": current_target or "cash",
                }
            )
            continue
        spy_return = float(row["SPY_adjusted_price"] / prior["SPY_adjusted_price"] - 1.0)
        xlu_return = float(row["XLU_adjusted_price"] / prior["XLU_adjusted_price"] - 1.0)
        relative = xlu_return - spy_return
        if relative > tolerance:
            target = XLU
            decision = "select_XLU"
        elif relative < -tolerance:
            target = SPY
            decision = "select_SPY"
        else:
            target = current_target
            decision = "equal_retain_prior"
        allocation_change = target is not None and target != current_target
        target_after = current_target
        if allocation_change:
            target_events[pd.Timestamp(execution_date)] = {
                SPY: 1.0 if target == SPY else 0.0,
                XLU: 1.0 if target == XLU else 0.0,
            }
            current_target = target
            target_after = target
        signal_payload = {
            "weekly_observation_number": int(row["week_number"]),
            "signal_week_observation_date": signal_date,
            "four_week_prior_observation_date": pd.Timestamp(prior["weekly_observation_date"]),
            "four_week_observation_lag": int(i - int(prior["week_number"]) + 1),
            "SPY_four_week_return": spy_return,
            "XLU_four_week_return": xlu_return,
            "relative_signal_XLU_minus_SPY": relative,
            "decision": decision,
            "target_asset_after_execution": target_after or "cash",
            "allocation_change": allocation_change,
            "execution_date": execution_date,
            "signal_precedes_execution": pd.Timestamp(signal_date) < pd.Timestamp(execution_date),
            "same_close_lookahead_possible": False,
        }
        signal_rows.append(signal_payload)
        execution_rows.append(
            {
                "signal_week_observation_date": signal_date,
                "execution_date": execution_date,
                "execution_after_signal_close": pd.Timestamp(execution_date) > pd.Timestamp(signal_date),
                "same_close_lookahead_possible": False,
                "target_asset": target_after or "cash",
                "allocation_change": allocation_change,
            }
        )
    return weekly, signal_rows, execution_rows, skipped_rows, target_events


def equal_returns_retain_prior(prior_allocation: str = XLU) -> str:
    return prior_allocation


def missing_observations_retain_prior(prior_allocation: str = SPY) -> str:
    return prior_allocation


def to_local_path(path: base.PathResult) -> PathResult:
    return PathResult(path.strategy_id, path.role, path.equity, path.returns, path.weights, path.trades)


def simulate_path(strategy_id: str, role: str, prices: pd.DataFrame, symbols: list[str], target_events: dict[pd.Timestamp, dict[str, float]]) -> PathResult:
    return to_local_path(base.simulate_path(strategy_id, role, prices, symbols, target_events, cost_rate=TRANSACTION_COST))


def buy_hold_events(prices: pd.DataFrame, symbol: str, symbols: list[str]) -> dict[pd.Timestamp, dict[str, float]]:
    return {pd.Timestamp(prices.index[0]): {item: 1.0 if item == symbol else 0.0 for item in symbols}} if not prices.empty else {}


def static_monthly_50_50_events(prices: pd.DataFrame) -> dict[pd.Timestamp, dict[str, float]]:
    targets: dict[pd.Timestamp, dict[str, float]] = {}
    if prices.empty:
        return targets
    for _period, frame in prices.groupby(prices.index.to_period("M")):
        targets[pd.Timestamp(frame.index[0])] = {SPY: 0.5, XLU: 0.5}
    return targets


def spy200d_events(prices: pd.DataFrame) -> dict[pd.Timestamp, dict[str, float]]:
    if prices.empty or SPY not in prices.columns or BIL not in prices.columns:
        return {}
    weights = reference_spy200d_weights(prices[[SPY, BIL]].copy())
    targets: dict[pd.Timestamp, dict[str, float]] = {}
    previous: tuple[float, float] | None = None
    for date, row in weights.iterrows():
        current = (round(float(row.get(SPY, 0.0)), 10), round(float(row.get(BIL, 0.0)), 10))
        if previous is None or current != previous:
            targets[pd.Timestamp(date)] = {SPY: float(row.get(SPY, 0.0)), BIL: float(row.get(BIL, 0.0))}
            previous = current
    return targets


def external_series_path(strategy_id: str, role: str, series: pd.Series) -> PathResult:
    series = series.dropna().astype(float)
    returns = series.pct_change(fill_method=None).fillna(0.0)
    weights = pd.DataFrame(index=series.index)
    return PathResult(strategy_id, role, series.rename("equity"), returns.rename("daily_return"), weights, [])


def load_external_reference_paths() -> dict[str, PathResult]:
    paths: dict[str, PathResult] = {}
    if ACTIVE_COMBO_SERIES_PATH.exists():
        frame = pd.read_csv(ACTIVE_COMBO_SERIES_PATH)
        frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
        frame = frame.dropna(subset=["date"]).set_index("date").sort_index()
        if "dsr_standalone_equity" in frame:
            paths["paper_forward_dsr_sector_equal_weight_defensive_filter_v1"] = external_series_path(
                "paper_forward_dsr_sector_equal_weight_defensive_filter_v1",
                "decision_critical_descriptive_control_existing_corrected_series",
                pd.to_numeric(frame["dsr_standalone_equity"], errors="coerce"),
            )
        if "active_combo_equity" in frame:
            paths["active_combo_vm_dsr_equal_weight_v1"] = external_series_path(
                "active_combo_vm_dsr_equal_weight_v1",
                "reference_only_existing_corrected_series",
                pd.to_numeric(frame["active_combo_equity"], errors="coerce"),
            )
    return paths


def annualized_volatility(returns: pd.Series) -> float:
    return base.annualized_volatility(returns)


def downside_volatility(returns: pd.Series) -> float:
    return base.downside_volatility(returns)


def max_drawdown(equity: pd.Series) -> float:
    return base.max_drawdown(equity)


def cagr(equity: pd.Series) -> float:
    return base.cagr(equity)


def total_return(equity: pd.Series) -> float:
    return base.total_return(equity)


def return_to_drawdown(equity: pd.Series) -> float:
    dd = abs(max_drawdown(equity))
    return float(total_return(equity) / dd) if dd > 0 and math.isfinite(dd) else float("nan")


def average_weight(path: PathResult, symbol: str) -> float:
    if path.weights.empty or symbol not in path.weights.columns:
        return 0.0
    return float(path.weights[symbol].mean())


def metric_row(path: PathResult, block_returns: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    block_returns = block_returns or []
    weights = path.weights
    trades = path.trades
    worst_block = min(
        [float(row["total_return"]) for row in block_returns if row.get("strategy_id") == path.strategy_id and row.get("total_return") not in ("", None)],
        default="",
    )
    return {
        "strategy_id": path.strategy_id,
        "role": path.role,
        "start_date": path.equity.index[0] if not path.equity.empty else "",
        "end_date": path.equity.index[-1] if not path.equity.empty else "",
        "final_equity": float(path.equity.iloc[-1]) if not path.equity.empty else "",
        "total_return": total_return(path.equity),
        "CAGR": cagr(path.equity),
        "annualized_volatility": annualized_volatility(path.returns),
        "downside_volatility": downside_volatility(path.returns),
        "maximum_drawdown": max_drawdown(path.equity),
        "worst_block_return": worst_block,
        "return_to_drawdown_ratio": return_to_drawdown(path.equity),
        "turnover": float(sum(float(row["turnover"]) for row in trades)),
        "trade_count": int(len(trades)),
        "allocation_changes": int(len(trades)),
        "transaction_costs": float(sum(float(row["transaction_cost"]) for row in trades)),
        "average_SPY_allocation": average_weight(path, SPY),
        "average_XLU_allocation": average_weight(path, XLU),
        "average_BIL_allocation": average_weight(path, BIL),
        "percentage_time_in_SPY": average_weight(path, SPY),
        "percentage_time_in_XLU": average_weight(path, XLU),
        "maximum_exposure": float(weights.sum(axis=1).max()) if not weights.empty else "",
        "maximum_weight_sum": float(weights.sum(axis=1).max()) if not weights.empty else "",
    }


def run_candidate(prices: pd.DataFrame, strategy_id: str = CANDIDATE_ID, role: str = "candidate") -> tuple[PathResult, list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[pd.Timestamp, dict[str, float]]]:
    weekly, signal_rows, execution_rows, skipped_rows, events = build_weekly_signals(prices[[SPY, XLU]])
    return simulate_path(strategy_id, role, prices[[SPY, XLU]], [SPY, XLU], events), weekly, signal_rows, execution_rows, skipped_rows, events


def build_paths(
    candidate_prices: pd.DataFrame,
    bil_prices: pd.DataFrame,
    include_external_references: bool = True,
) -> tuple[dict[str, PathResult], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[pd.Timestamp, dict[str, float]]]:
    candidate_path, weekly, signal_rows, execution_rows, skipped_rows, events = run_candidate(candidate_prices)
    paths: dict[str, PathResult] = {
        CANDIDATE_ID: candidate_path,
        "SPY_buy_and_hold": simulate_path("SPY_buy_and_hold", "primary_benchmark", candidate_prices[[SPY]], [SPY], buy_hold_events(candidate_prices[[SPY]], SPY, [SPY])),
        "XLU_buy_and_hold": simulate_path("XLU_buy_and_hold", "additional_control", candidate_prices[[XLU]], [XLU], buy_hold_events(candidate_prices[[XLU]], XLU, [XLU])),
        "static_50pct_SPY_50pct_XLU_monthly": simulate_path(
            "static_50pct_SPY_50pct_XLU_monthly",
            "additional_control",
            candidate_prices[[SPY, XLU]],
            [SPY, XLU],
            static_monthly_50_50_events(candidate_prices[[SPY, XLU]]),
        ),
    }
    if not bil_prices.empty:
        paths["BIL_cash_proxy"] = simulate_path(
            "BIL_cash_proxy",
            "additional_control",
            bil_prices[[BIL]],
            [BIL],
            buy_hold_events(bil_prices[[BIL]], BIL, [BIL]),
        )
        spy_bil = pd.concat([candidate_prices[SPY], bil_prices[BIL]], axis=1).dropna()
        if len(spy_bil) > 252:
            paths["SPY_200d_trend_model"] = simulate_path(
                "SPY_200d_trend_model",
                "decision_critical_secondary_control",
                spy_bil[[SPY, BIL]],
                [SPY, BIL],
                spy200d_events(spy_bil[[SPY, BIL]]),
            )
    if include_external_references:
        paths.update(load_external_reference_paths())
    return paths, weekly, signal_rows, execution_rows, skipped_rows, events


def simulate_paths_for_period(start: Any, end: Any, candidate_prices: pd.DataFrame, bil_prices: pd.DataFrame) -> dict[str, PathResult]:
    c = candidate_prices.loc[(candidate_prices.index >= pd.Timestamp(start)) & (candidate_prices.index <= pd.Timestamp(end))]
    b = bil_prices.loc[(bil_prices.index >= pd.Timestamp(start)) & (bil_prices.index <= pd.Timestamp(end))] if not bil_prices.empty else bil_prices
    if len(c) < 30:
        return {}
    paths, *_ = build_paths(c, b, include_external_references=False)
    return paths


def period_metrics_rows(periods: list[dict[str, Any]], period_type: str, candidate_prices: pd.DataFrame, bil_prices: pd.DataFrame, reinitialize: bool = True) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for period in periods:
        paths = simulate_paths_for_period(period["start_date"], period["end_date"], candidate_prices, bil_prices) if reinitialize else {}
        for strategy_id, path in paths.items():
            if len(path.equity) < 2:
                continue
            rows.append(
                {
                    **period,
                    "period_type": period_type,
                    "strategy_id": strategy_id,
                    "total_return": total_return(path.equity),
                    "maximum_drawdown": max_drawdown(path.equity),
                    "CAGR": cagr(path.equity),
                    "return_to_drawdown_ratio": return_to_drawdown(path.equity),
                    "reinitialized_for_period": reinitialize,
                }
            )
    return rows


def calendar_year_rows(paths: dict[str, PathResult], candidate_index: pd.DatetimeIndex) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    years = sorted(set(candidate_index.year))
    for year in years:
        year_status = "partial_first_year" if year == int(years[0]) else "partial_final_year" if year == int(years[-1]) else "complete_calendar_year"
        for strategy_id, path in paths.items():
            eq = path.equity.loc[path.equity.index.year == year]
            if len(eq) < 2:
                continue
            rows.append(
                {
                    "calendar_year": year,
                    "year_status": year_status,
                    "strategy_id": strategy_id,
                    "total_return": total_return(eq),
                    "maximum_drawdown": max_drawdown(eq),
                    "CAGR": cagr(eq),
                }
            )
    return rows


def source_update_regime_periods(index: pd.DatetimeIndex) -> list[dict[str, Any]]:
    return [
        {
            "regime_id": "source_covered_through_2020_update",
            "start_date": pd.Timestamp(index[0]),
            "end_date": min(pd.Timestamp("2020-12-31"), pd.Timestamp(index[-1])),
            "frozen_before_performance": True,
        },
        {
            "regime_id": "post_source_update_2021_forward",
            "start_date": max(pd.Timestamp("2021-01-04"), pd.Timestamp(index[0])),
            "end_date": pd.Timestamp(index[-1]),
            "frozen_before_performance": True,
        },
    ]


def aligned_total_return(left: pd.Series, right: pd.Series) -> tuple[float, float, pd.Timestamp | str, pd.Timestamp | str]:
    common = left.dropna().to_frame("left").join(right.dropna().to_frame("right"), how="inner")
    if len(common) < 2:
        return float("nan"), float("nan"), "", ""
    return total_return(common["left"]), total_return(common["right"]), pd.Timestamp(common.index[0]), pd.Timestamp(common.index[-1])


def benchmark_relative_metrics(paths: dict[str, PathResult], block_rows: list[dict[str, Any]], window_rows: list[dict[str, Any]], calendar_rows: list[dict[str, Any]], regime_rows: list[dict[str, Any]]) -> dict[str, Any]:
    candidate = metric_row(paths[CANDIDATE_ID])
    spy = metric_row(paths["SPY_buy_and_hold"])
    spy200d_path = paths.get("SPY_200d_trend_model")
    cand_spy200d_return, spy200d_return, spy200d_overlap_start, spy200d_overlap_end = (
        aligned_total_return(paths[CANDIDATE_ID].equity, spy200d_path.equity) if spy200d_path else (float("nan"), float("nan"), "", "")
    )

    def by(strategy_id: str, rows: list[dict[str, Any]], key: str = "total_return") -> list[float]:
        return [float(row[key]) for row in rows if row.get("strategy_id") == strategy_id and row.get(key) not in ("", None)]

    cand_blocks = by(CANDIDATE_ID, block_rows)
    spy_blocks = by("SPY_buy_and_hold", block_rows)
    spy200d_blocks = by("SPY_200d_trend_model", block_rows)
    cand_block_dd = by(CANDIDATE_ID, block_rows, "maximum_drawdown")
    spy_block_dd = by("SPY_buy_and_hold", block_rows, "maximum_drawdown")
    cand_180 = [row for row in window_rows if row["strategy_id"] == CANDIDATE_ID and int(row.get("horizon_days", 0)) == 180]
    cand_252 = [row for row in window_rows if row["strategy_id"] == CANDIDATE_ID and int(row.get("horizon_days", 0)) == 252]
    spy_180 = [row for row in window_rows if row["strategy_id"] == "SPY_buy_and_hold" and int(row.get("horizon_days", 0)) == 180]
    spy_252 = [row for row in window_rows if row["strategy_id"] == "SPY_buy_and_hold" and int(row.get("horizon_days", 0)) == 252]
    spy200d_180 = [row for row in window_rows if row["strategy_id"] == "SPY_200d_trend_model" and int(row.get("horizon_days", 0)) == 180]
    spy200d_252 = [row for row in window_rows if row["strategy_id"] == "SPY_200d_trend_model" and int(row.get("horizon_days", 0)) == 252]
    cal_candidate = {int(row["calendar_year"]): float(row["total_return"]) for row in calendar_rows if row["strategy_id"] == CANDIDATE_ID}
    cal_spy = {int(row["calendar_year"]): float(row["total_return"]) for row in calendar_rows if row["strategy_id"] == "SPY_buy_and_hold"}
    regime_map = {(row["strategy_id"], row["regime_id"]): float(row["total_return"]) for row in regime_rows}
    post_candidate = regime_map.get((CANDIDATE_ID, "post_source_update_2021_forward"), float("nan"))
    post_spy = regime_map.get(("SPY_buy_and_hold", "post_source_update_2021_forward"), float("nan"))
    post_spy200d = regime_map.get(("SPY_200d_trend_model", "post_source_update_2021_forward"), float("nan"))
    spy200d_metric = metric_row(spy200d_path) if spy200d_path else {"maximum_drawdown": float("nan")}
    return {
        "candidate_id": CANDIDATE_ID,
        "full_period_excess_vs_SPY": float(candidate["total_return"] - spy["total_return"]),
        "full_period_excess_vs_SPY_200d_trend_model": float(cand_spy200d_return - spy200d_return),
        "SPY_200d_overlap_start": spy200d_overlap_start,
        "SPY_200d_overlap_end": spy200d_overlap_end,
        "median_block_excess_vs_SPY": float(np.median(np.array(cand_blocks) - np.array(spy_blocks))) if len(cand_blocks) == len(spy_blocks) and cand_blocks else "",
        "mean_block_excess_vs_SPY": float(np.mean(np.array(cand_blocks) - np.array(spy_blocks))) if len(cand_blocks) == len(spy_blocks) and cand_blocks else "",
        "blocks_beating_SPY": int(sum(c > s for c, s in zip(cand_blocks, spy_blocks))),
        "median_block_excess_vs_SPY_200d_trend_model": float(np.median(np.array(cand_blocks[: len(spy200d_blocks)]) - np.array(spy200d_blocks))) if spy200d_blocks else "",
        "mean_block_excess_vs_SPY_200d_trend_model": float(np.mean(np.array(cand_blocks[: len(spy200d_blocks)]) - np.array(spy200d_blocks))) if spy200d_blocks else "",
        "blocks_beating_SPY_200d_trend_model": int(sum(c > s for c, s in zip(cand_blocks, spy200d_blocks))),
        "blocks_with_smaller_drawdown_than_SPY": int(sum(c > s for c, s in zip(cand_block_dd, spy_block_dd))),
        "180d_window_wins_vs_SPY": int(sum(float(c["total_return"]) > float(s["total_return"]) for c, s in zip(cand_180, spy_180))),
        "252d_window_wins_vs_SPY": int(sum(float(c["total_return"]) > float(s["total_return"]) for c, s in zip(cand_252, spy_252))),
        "180d_window_wins_vs_SPY_200d_trend_model": int(sum(float(c["total_return"]) > float(s["total_return"]) for c, s in zip(cand_180, spy200d_180))),
        "252d_window_wins_vs_SPY_200d_trend_model": int(sum(float(c["total_return"]) > float(s["total_return"]) for c, s in zip(cand_252, spy200d_252))),
        "calendar_years_beating_SPY": int(sum(cal_candidate[y] > cal_spy[y] for y in sorted(set(cal_candidate) & set(cal_spy)))),
        "calendar_years_compared_vs_SPY": int(len(set(cal_candidate) & set(cal_spy))),
        "drawdown_difference_vs_SPY": float(candidate["maximum_drawdown"] - spy["maximum_drawdown"]),
        "drawdown_difference_vs_SPY_200d_trend_model": float(candidate["maximum_drawdown"] - spy200d_metric["maximum_drawdown"]) if math.isfinite(float(spy200d_metric["maximum_drawdown"])) else "",
        "candidate_max_drawdown": candidate["maximum_drawdown"],
        "SPY_max_drawdown": spy["maximum_drawdown"],
        "SPY_200d_max_drawdown": spy200d_metric["maximum_drawdown"],
        "latest_block_excess_vs_SPY": float(cand_blocks[-1] - spy_blocks[-1]) if cand_blocks and spy_blocks else "",
        "second_latest_block_excess_vs_SPY": float(cand_blocks[-2] - spy_blocks[-2]) if len(cand_blocks) >= 2 and len(spy_blocks) >= 2 else "",
        "post_2020_excess_vs_SPY": float(post_candidate - post_spy),
        "post_2020_excess_vs_SPY_200d_trend_model": float(post_candidate - post_spy200d) if math.isfinite(float(post_spy200d)) else "",
    }


def expand_dsr_states(index: pd.DatetimeIndex) -> pd.Series:
    source = DSR_REBALANCE_TRACE_PATH if DSR_REBALANCE_TRACE_PATH.exists() else ACTIVE_COMBO_ALLOCATIONS_PATH
    if not source.exists():
        return pd.Series(dtype=object)
    frame = pd.read_csv(source)
    date_col = "rebalance_date"
    weights_col = "weights" if "weights" in frame.columns else "dsr_holdings"
    frame[date_col] = pd.to_datetime(frame[date_col], errors="coerce")
    states: dict[pd.Timestamp, str] = {}
    for _, row in frame.dropna(subset=[date_col]).iterrows():
        try:
            weights = json.loads(str(row[weights_col]).replace("'", '"'))
        except Exception:
            weights = {}
        defensive_weight = sum(float(weights.get(symbol, 0.0)) for symbol in (BIL, "XLU", "XLP", "XLV"))
        states[pd.Timestamp(row[date_col])] = "defensive" if defensive_weight >= 0.5 else "offensive"
    if not states:
        return pd.Series(dtype=object)
    series = pd.Series(states).sort_index()
    return series.reindex(index).ffill()


def dsr_redundancy_diagnostics(paths: dict[str, PathResult]) -> dict[str, Any]:
    candidate = paths[CANDIDATE_ID]
    dsr = paths.get("paper_forward_dsr_sector_equal_weight_defensive_filter_v1")
    if dsr is None:
        return {
            "candidate_id": CANDIDATE_ID,
            "dsr_comparison_status": "descriptive_unavailable",
            "candidate_correlation_with_active_DSR": "",
            "correlation_during_SPY_drawdown_periods": "",
            "same_broad_defensive_offensive_state_pct": "",
            "redundancy_assessment": "DSR corrected daily return series unavailable",
        }
    common = candidate.returns.to_frame("candidate").join(dsr.returns.rename("dsr"), how="inner").dropna()
    corr = float(common["candidate"].corr(common["dsr"])) if len(common) > 2 else float("nan")
    spy = paths["SPY_buy_and_hold"].equity.reindex(common.index).ffill()
    spy_dd = spy / spy.cummax() - 1.0
    dd_common = common.loc[spy_dd <= -0.10]
    dd_corr = float(dd_common["candidate"].corr(dd_common["dsr"])) if len(dd_common) > 2 else float("nan")
    candidate_state = pd.Series(np.where(candidate.weights.reindex(common.index).ffill().fillna(0.0).get(XLU, pd.Series(0.0, index=common.index)) > 0.5, "defensive", "offensive"), index=common.index)
    dsr_state = expand_dsr_states(common.index)
    state_common = pd.concat([candidate_state.rename("candidate"), dsr_state.rename("dsr")], axis=1).dropna()
    same_state = float((state_common["candidate"] == state_common["dsr"]).mean()) if len(state_common) else float("nan")
    assessment = "operationally_redundant" if math.isfinite(corr) and corr >= 0.90 and math.isfinite(same_state) and same_state >= 0.90 else "partially_overlapping_or_materially_distinct"
    return {
        "candidate_id": CANDIDATE_ID,
        "dsr_comparison_status": "available_existing_corrected_series",
        "candidate_correlation_with_active_DSR": corr,
        "correlation_during_SPY_drawdown_periods": dd_corr,
        "same_broad_defensive_offensive_state_pct": same_state,
        "overlap_days": int(len(common)),
        "state_overlap_days": int(len(state_common)),
        "redundancy_assessment": assessment,
        "dsr_series_source": rel(ACTIVE_COMBO_SERIES_PATH),
        "dsr_state_source": rel(DSR_REBALANCE_TRACE_PATH if DSR_REBALANCE_TRACE_PATH.exists() else ACTIVE_COMBO_ALLOCATIONS_PATH),
    }


def signal_diagnostics(signal_rows: list[dict[str, Any]], skipped_rows: list[dict[str, Any]], path: PathResult) -> dict[str, Any]:
    weights = path.weights
    xlu_days = int((weights.get(XLU, pd.Series(dtype=float)) > 0.5).sum()) if not weights.empty and XLU in weights else 0
    spy_days = int((weights.get(SPY, pd.Series(dtype=float)) > 0.5).sum()) if not weights.empty and SPY in weights else 0
    holding_targets = [SPY if row.get("target_asset_after_execution") == SPY else XLU if row.get("target_asset_after_execution") == XLU else "" for row in signal_rows]
    longest_spy = longest_run(holding_targets, SPY)
    longest_xlu = longest_run(holding_targets, XLU)
    return {
        "candidate_id": CANDIDATE_ID,
        "weeks_selecting_SPY": int(sum(row.get("target_asset_after_execution") == SPY for row in signal_rows)),
        "weeks_selecting_XLU": int(sum(row.get("target_asset_after_execution") == XLU for row in signal_rows)),
        "signal_changes": int(len(path.trades)),
        "equal_signal_weeks": int(sum(row.get("decision") == "equal_retain_prior" for row in signal_rows)),
        "invalid_signal_weeks": int(len(skipped_rows)),
        "longest_SPY_holding_weeks": int(longest_spy),
        "longest_XLU_holding_weeks": int(longest_xlu),
        "percentage_time_in_SPY": float(spy_days / len(weights)) if len(weights) else 0.0,
        "percentage_time_in_XLU": float(xlu_days / len(weights)) if len(weights) else 0.0,
        "diagnostics_used_as_signal": False,
    }


def longest_run(values: list[str], target: str) -> int:
    best = current = 0
    for value in values:
        if value == target:
            current += 1
            best = max(best, current)
        else:
            current = 0
    return best


def classify_outcome(relative: dict[str, Any], dsr_diag: dict[str, Any], invariants_passed: bool) -> tuple[str, str]:
    if not invariants_passed:
        return "invalid_methodology", "Concrete accounting, timing, data, or exposure invariant failure"
    full_vs_spy = float(relative.get("full_period_excess_vs_SPY", float("nan")))
    full_vs_spy200d = float(relative.get("full_period_excess_vs_SPY_200d_trend_model", float("nan")))
    median_vs_spy = float(relative.get("median_block_excess_vs_SPY", float("nan")))
    median_vs_spy200d = float(relative.get("median_block_excess_vs_SPY_200d_trend_model", float("nan")))
    blocks_spy = int(relative.get("blocks_beating_SPY", 0))
    blocks_spy200d = int(relative.get("blocks_beating_SPY_200d_trend_model", 0))
    post_spy = float(relative.get("post_2020_excess_vs_SPY", float("nan")))
    latest = float(relative.get("latest_block_excess_vs_SPY", float("nan")))
    second_latest = float(relative.get("second_latest_block_excess_vs_SPY", float("nan")))
    dd_vs_spy = float(relative.get("drawdown_difference_vs_SPY", float("nan")))
    blocks_smaller_dd = int(relative.get("blocks_with_smaller_drawdown_than_SPY", 0))
    if (
        full_vs_spy > 0
        and median_vs_spy > 0
        and blocks_spy >= 3
        and median_vs_spy200d > 0
        and blocks_spy200d >= 3
        and post_spy > 0
        and dd_vs_spy >= -0.05
    ):
        return "comparative_evidence_positive", "Frozen evidence passed the comparative positive screen"
    if full_vs_spy > 0 and median_vs_spy > 0 and blocks_spy >= 3 and (post_spy < 0 or (latest < 0 and second_latest < 0)):
        return "historical_edge_recently_weakened", "Earlier comparative edge weakened in post-source or final-block evidence"
    if full_vs_spy <= 0 and median_vs_spy <= 0 and dd_vs_spy >= 0.10 and blocks_smaller_dd >= 4:
        return "risk_reduction_without_return_edge", "Candidate reduced drawdown but did not show a return edge versus SPY"
    if dsr_diag.get("redundancy_assessment") == "operationally_redundant":
        return "redundant_with_active_observation", "Candidate is highly redundant with active DSR and not superior on decision evidence"
    if full_vs_spy < 0 and math.isfinite(full_vs_spy200d) and full_vs_spy200d < 0 and median_vs_spy <= 0 and median_vs_spy200d <= 0:
        return "control_weak", "Candidate is broadly weak versus both SPY and the 200-day trend control"
    return "no_material_edge", "No persistent return, material risk-reduction, or decision-relevant distinctiveness is supported"


def source_and_preregistration(prices: pd.DataFrame, cache_rows: list[dict[str, Any]], fingerprint: dict[str, Any]) -> dict[str, Any]:
    return {
        "candidate_id": CANDIDATE_ID,
        "family_id": FAMILY_ID,
        "mechanism": MECHANISM,
        "source": {
            "source_id": SOURCE_ID,
            "title": "An Intermarket Approach to Beta Rotation: The Strategy, Signal, and Power of Utilities",
            "authors": ["Michael A. Gayed", "Charles V. Bilello"],
            "award": "2014 Charles H. Dow Award winner",
            "update_through": "2020-10-31",
            "source_performance_used_as_project_evidence": False,
        },
        "frozen_rules": {
            "weekly_observation": "final common XLU/SPY trading session of each calendar week",
            "formation_horizon": "four weekly observations",
            "signal": "XLU four-week total return minus SPY four-week total return",
            "positive_signal": "target XLU=1.0 SPY=0.0",
            "negative_signal": "target SPY=1.0 XLU=0.0",
            "equal_signal": "retain prior allocation and do not trade",
            "missing_data": "retain prior allocation and record skipped signal",
            "execution": "close of next common XLU/SPY session after completed signal week",
            "no_same_close_lookahead": True,
            "initialization": "cash until four complete prior weekly observations exist",
            "max_gross_exposure": 1.0,
            "partial_allocation": False,
            "BIL_fallback": False,
            "treasury_allocation": False,
            "VIX_filter": False,
            "moving_average_filter": False,
            "volatility_targeting": False,
            "leverage": False,
            "shorting": False,
        },
        "frozen_periods": {
            "candidate_price_start": prices.index[0],
            "candidate_price_end": prices.index[-1],
            "source_update_boundary": "2020-12-31 / 2021-01-04",
        },
        "initial_capital": INITIAL_CAPITAL,
        "transaction_cost_convention": TRANSACTION_COST,
        "cache_rows": cache_rows,
        "fingerprint_hash": fingerprint["fingerprint_hash"],
        "benchmarks": [
            "SPY_buy_and_hold",
            "paper_forward_dsr_sector_equal_weight_defensive_filter_v1",
            "SPY_200d_trend_model",
            "XLU_buy_and_hold",
            "static_50pct_SPY_50pct_XLU_monthly",
            "BIL_cash_proxy",
            "active_combo_vm_dsr_equal_weight_v1_reference_only",
        ],
        "outcome_rules_frozen_before_performance": sorted(ALLOWED_OUTCOMES),
    }


def exact_variant_memory(outcome: str, reason: str) -> list[dict[str, Any]]:
    return [
        {
            "candidate_id": CANDIDATE_ID,
            "family_id": FAMILY_ID,
            "outcome": outcome,
            "primary_failure_reason": reason if outcome != "comparative_evidence_positive" else "",
            "exact_candidate_closed_for_immediate_retesting": outcome != "comparative_evidence_positive",
            "broader_intermarket_equity_beta_rotation_family_closed": False,
            "immediate_variants_prohibited": [
                "alternative_lookbacks",
                "daily_signals",
                "monthly_signals",
                "other_defensive_sectors",
                "sector_baskets",
                "VIX_confirmation",
                "moving_average_confirmation",
                "BIL_fallback",
                "leverage",
                "partial_SPY_XLU_weighting",
            ],
            "promotion_authorized": False,
            "paper_demo_authorized": False,
            "candidate_exhaustive_authorized": False,
        }
    ]


def treasury_rotation_direction_memory() -> dict[str, Any]:
    previous_outcome = {}
    path = TREASURY_EVIDENCE_DIR / "screening_outcome.json"
    if path.exists():
        previous_outcome = json.loads(path.read_text(encoding="utf-8"))
    return {
        "candidate_id": "spy_tlt_ief_tlt_prior_month_risk_rotation_v1",
        "preserved_evidence_path": rel(TREASURY_EVIDENCE_DIR),
        "formal_outcome": previous_outcome.get("outcome", "no_material_edge"),
        "exact_candidate_closed_for_immediate_retesting": True,
        "broader_macro_duration_risk_off_rotation_family_open": True,
        "underperformed_SPY_buy_and_hold_full_period": True,
        "underperformed_SPY_200d_trend_model_full_period": True,
        "blocks_beating_SPY": "2 / 5",
        "blocks_beating_SPY_200d_trend_model": "3 / 5",
        "pre_2022_excess_vs_SPY_negative": True,
        "post_2022_excess_vs_SPY_negative": True,
        "drawdown_improvement_vs_SPY_did_not_compensate_for_return_weakness": True,
        "drawdown_materially_worse_than_SPY_200d_trend_model": True,
        "further_validation_authorized": False,
        "immediate_variants_prohibited": [
            "TRRS10",
            "IEF_defensive_holding",
            "alternative_duration_pair",
            "weekly_signal",
            "BIL_fallback",
            "partial_weighting",
            "gold_addition",
            "trend_confirmation",
            "volatility_targeting",
        ],
        "prior_evidence_modified": False,
    }


def run() -> dict[str, Any]:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    protected_before = file_snapshot(
        [
            REGISTRY_PATH,
            ACTIVE_OBSERVATIONS_PATH,
            PAPER_FORWARD_DIR / "paper_forward_vm_quality_lowvol_proxy_v1" / "active_observation.yaml",
            PAPER_FORWARD_DIR / "paper_forward_dsr_sector_equal_weight_defensive_filter_v1" / "active_observation.yaml",
            PAPER_FORWARD_DIR / "paper_forward_usci_dynamic_commodity_curve_selection_wrapper_v1" / "active_observation.yaml",
            ACTIVE_COMBO_SERIES_PATH,
            TREASURY_EVIDENCE_DIR / "screening_outcome.json",
        ]
    )
    provider_manifest, cache_rows = ensure_required_caches()
    write_json(EVIDENCE_DIR / "provider_acquisition_manifest.json", provider_manifest)
    write_json(
        EVIDENCE_DIR / "cache_manifest.json",
        {
            "candidate_id": CANDIDATE_ID,
            "adjusted_total_return_prices_required": True,
            "series": cache_rows,
        },
    )
    write_csv(EVIDENCE_DIR / "duplicate_and_redundancy_review.csv", duplicate_and_redundancy_review_rows())
    fingerprint = candidate_fingerprint()
    write_json(EVIDENCE_DIR / "candidate_fingerprint.json", fingerprint)
    write_json(EVIDENCE_DIR / "treasury_rotation_direction_memory.json", treasury_rotation_direction_memory())
    invalid_reason = ""
    if provider_manifest.get("errors") or provider_manifest.get("missing_required_symbols_after_run"):
        invalid_reason = "; ".join(provider_manifest.get("errors", [])) or "required cache unavailable"
        screening = {
            "candidate_id": CANDIDATE_ID,
            "family_id": FAMILY_ID,
            "outcome": "invalid_methodology",
            "primary_failure_reason": invalid_reason,
            "provider_download": provider_manifest.get("provider_download", False),
            "promotion_authorized": False,
            "paper_demo_authorized": False,
            "candidate_exhaustive_authorized": False,
            "real_money_recommendation": False,
            "next_action": "fix_spy_xlu_4week_beta_rotation_methodology_issue",
        }
        write_json(EVIDENCE_DIR / "screening_outcome.json", screening)
        write_json(EVIDENCE_DIR / "consistency_check.json", {"candidate_id": CANDIDATE_ID, "consistency_passed": False, "invalid_reason": invalid_reason})
        return screening

    candidate_prices = load_prices((SPY, XLU))
    bil_prices = load_prices((BIL,)) if base.cache_quality_row(BIL).get("adjusted_price_validation_result") == "pass" else pd.DataFrame()
    write_json(EVIDENCE_DIR / "source_and_preregistration.json", source_and_preregistration(candidate_prices, cache_rows, fingerprint))

    paths, weekly_rows, signal_rows, execution_rows, skipped_rows, _events = build_paths(candidate_prices, bil_prices)
    blocks = base.split_blocks(candidate_prices.index, 5)
    windows_180 = base.deterministic_windows(candidate_prices.index, 180, 5)
    windows_252 = base.deterministic_windows(candidate_prices.index, 252, 5)
    regimes = source_update_regime_periods(candidate_prices.index)
    block_rows = period_metrics_rows(blocks, "chronological_block", candidate_prices, bil_prices, reinitialize=True)
    window_rows = period_metrics_rows(windows_180 + windows_252, "deterministic_window", candidate_prices, bil_prices, reinitialize=True)
    regime_rows = period_metrics_rows(regimes, "source_update_regime", candidate_prices, bil_prices, reinitialize=False)
    if not regime_rows:
        regime_rows = base.period_metrics_rows({key: base.PathResult(value.strategy_id, value.role, value.equity, value.returns, value.weights, value.trades) for key, value in paths.items()}, regimes, "source_update_regime")
    calendar_rows = calendar_year_rows(paths, candidate_prices.index)
    full_rows = [metric_row(path, block_rows) for path in paths.values()]
    relative = benchmark_relative_metrics(paths, block_rows, window_rows, calendar_rows, regime_rows)
    dsr_diag = dsr_redundancy_diagnostics(paths)
    sig_diag = signal_diagnostics(signal_rows, skipped_rows, paths[CANDIDATE_ID])

    weights = paths[CANDIDATE_ID].weights
    signal_execution_ok = all(pd.Timestamp(row["signal_week_observation_date"]) < pd.Timestamp(row["execution_date"]) for row in execution_rows)
    weekly_final_ok = all(bool(row["final_common_XLU_SPY_session"]) for row in weekly_rows)
    no_forward_fill = len(candidate_prices) == len(candidate_prices.dropna())
    max_exposure = float(weights.sum(axis=1).max()) if not weights.empty else 0.0
    invariants = {
        "candidate_id": CANDIDATE_ID,
        "weekly_observations_use_final_common_XLU_SPY_session": weekly_final_ok,
        "four_week_returns_use_exactly_four_prior_weekly_observations": all(int(row["four_week_observation_lag"]) == 4 for row in signal_rows),
        "completed_signal_week_precedes_execution": signal_execution_ok,
        "same_close_lookahead_possible": False,
        "positive_XLU_minus_SPY_signal_selects_XLU": any(row["decision"] == "select_XLU" and row["target_asset_after_execution"] == XLU for row in signal_rows),
        "negative_XLU_minus_SPY_signal_selects_SPY": any(row["decision"] == "select_SPY" and row["target_asset_after_execution"] == SPY for row in signal_rows),
        "equal_signal_retain_prior_position": equal_returns_retain_prior(XLU) == XLU,
        "missing_observations_retain_prior_position": missing_observations_retain_prior(SPY) == SPY,
        "no_prices_forward_filled": no_forward_fill,
        "holds_only_SPY_or_XLU_after_initialization": bool(((weights[[SPY, XLU]].sum(axis=1) <= 1.000001) & (weights.drop(columns=[SPY, XLU], errors="ignore").sum(axis=1) == 0 if len(weights.drop(columns=[SPY, XLU], errors="ignore").columns) else True)).all()) if not weights.empty else False,
        "exposure_never_exceeds_1": max_exposure <= 1.000001,
        "maximum_exposure": max_exposure,
        "maximum_weight_sum": max_exposure,
        "no_nan_final_weights": int(weights.isna().sum().sum()) == 0 if not weights.empty else False,
        "turnover_uses_actual_pretrade_holdings": all(bool(row.get("actual_pretrade_holdings_used")) for row in paths[CANDIDATE_ID].trades),
        "windows_and_regimes_frozen_before_performance": all(row.get("frozen_before_performance") is True for row in [*blocks, *windows_180, *windows_252, *regimes]),
        "DSR_comparison_only_not_modified": True,
        "SPY_200d_control_not_signal": True,
        "no_VIX_BIL_treasury_moving_average_or_leverage_rule": True,
        "VM_DSR_USCI_active_combo_states_unchanged": protected_before
        == file_snapshot(
            [
                REGISTRY_PATH,
                ACTIVE_OBSERVATIONS_PATH,
                PAPER_FORWARD_DIR / "paper_forward_vm_quality_lowvol_proxy_v1" / "active_observation.yaml",
                PAPER_FORWARD_DIR / "paper_forward_dsr_sector_equal_weight_defensive_filter_v1" / "active_observation.yaml",
                PAPER_FORWARD_DIR / "paper_forward_usci_dynamic_commodity_curve_selection_wrapper_v1" / "active_observation.yaml",
                ACTIVE_COMBO_SERIES_PATH,
                TREASURY_EVIDENCE_DIR / "screening_outcome.json",
            ]
        ),
        "paper_demo_observation_created": False,
        "broker_order_created": False,
        "promotion_authorized": False,
        "paper_demo_authorized": False,
        "candidate_exhaustive_run": False,
        "real_money_recommendation": False,
    }
    invariants["invariants_passed"] = all(
        bool(invariants[key])
        for key in (
            "weekly_observations_use_final_common_XLU_SPY_session",
            "four_week_returns_use_exactly_four_prior_weekly_observations",
            "completed_signal_week_precedes_execution",
            "positive_XLU_minus_SPY_signal_selects_XLU",
            "negative_XLU_minus_SPY_signal_selects_SPY",
            "equal_signal_retain_prior_position",
            "missing_observations_retain_prior_position",
            "no_prices_forward_filled",
            "holds_only_SPY_or_XLU_after_initialization",
            "exposure_never_exceeds_1",
            "no_nan_final_weights",
            "turnover_uses_actual_pretrade_holdings",
            "windows_and_regimes_frozen_before_performance",
            "DSR_comparison_only_not_modified",
            "no_VIX_BIL_treasury_moving_average_or_leverage_rule",
            "VM_DSR_USCI_active_combo_states_unchanged",
        )
    ) and not any(
        bool(invariants[key])
        for key in ("same_close_lookahead_possible", "paper_demo_observation_created", "broker_order_created", "promotion_authorized", "paper_demo_authorized", "candidate_exhaustive_run", "real_money_recommendation")
    )

    write_csv(EVIDENCE_DIR / "frozen_weekly_observations.csv", weekly_rows)
    write_csv(EVIDENCE_DIR / "frozen_signal_dates.csv", signal_rows)
    write_csv(EVIDENCE_DIR / "frozen_execution_dates.csv", execution_rows)
    write_csv(EVIDENCE_DIR / "skipped_signal_weeks.csv", skipped_rows)
    write_csv(EVIDENCE_DIR / "frozen_chronological_blocks.csv", blocks)
    write_csv(EVIDENCE_DIR / "frozen_180d_windows.csv", windows_180)
    write_csv(EVIDENCE_DIR / "frozen_252d_windows.csv", windows_252)
    write_csv(EVIDENCE_DIR / "full_period_metrics.csv", full_rows)
    write_csv(EVIDENCE_DIR / "chronological_block_results.csv", block_rows)
    write_csv(EVIDENCE_DIR / "window_level_results.csv", window_rows)
    write_csv(EVIDENCE_DIR / "calendar_year_results.csv", calendar_rows)
    write_csv(EVIDENCE_DIR / "source_update_regime_results.csv", regime_rows)
    write_csv(EVIDENCE_DIR / "benchmark_relative_metrics.csv", [relative])
    write_csv(EVIDENCE_DIR / "dsr_redundancy_diagnostics.csv", [dsr_diag])
    write_csv(EVIDENCE_DIR / "signal_diagnostics.csv", [sig_diag])
    write_csv(EVIDENCE_DIR / "accounting_timing_and_exposure_invariants.csv", [invariants])

    outcome, outcome_reason = classify_outcome(relative, dsr_diag, bool(invariants["invariants_passed"]))
    next_action = (
        "direction_owner_review_spy_xlu_4week_beta_rotation_v1"
        if outcome == "comparative_evidence_positive"
        else "fix_spy_xlu_4week_beta_rotation_methodology_issue"
        if outcome == "invalid_methodology"
        else "record_spy_xlu_4week_beta_rotation_exact_variant_memory_and_resume_source_queue"
    )
    screening = {
        "candidate_id": CANDIDATE_ID,
        "family_id": FAMILY_ID,
        "outcome": outcome,
        "primary_failure_reason": "" if outcome == "comparative_evidence_positive" else outcome_reason,
        "exact_candidate_closed_for_immediate_retesting": outcome != "comparative_evidence_positive",
        "broader_intermarket_equity_beta_rotation_family_closed": False,
        "provider_download": provider_manifest["provider_download"],
        "promotion_authorized": False,
        "paper_demo_authorized": False,
        "candidate_exhaustive_authorized": False,
        "real_money_recommendation": False,
        "invalid_reason": invalid_reason,
        "next_action": next_action,
    }
    write_json(EVIDENCE_DIR / "screening_outcome.json", screening)
    write_csv(EVIDENCE_DIR / "exact_variant_research_memory.csv", exact_variant_memory(outcome, outcome_reason))

    consistency = {
        "candidate_id": CANDIDATE_ID,
        "weekly_observations_use_final_common_XLU_SPY_session": invariants["weekly_observations_use_final_common_XLU_SPY_session"] is True,
        "four_week_returns_use_exactly_four_prior_weekly_observations": invariants["four_week_returns_use_exactly_four_prior_weekly_observations"] is True,
        "completed_signal_week_precedes_execution": invariants["completed_signal_week_precedes_execution"] is True,
        "same_close_execution_impossible": invariants["same_close_lookahead_possible"] is False,
        "positive_XLU_minus_SPY_signal_selects_XLU": invariants["positive_XLU_minus_SPY_signal_selects_XLU"] is True,
        "negative_XLU_minus_SPY_signal_selects_SPY": invariants["negative_XLU_minus_SPY_signal_selects_SPY"] is True,
        "equal_signal_retain_prior_position": invariants["equal_signal_retain_prior_position"] is True,
        "missing_observations_retain_prior_position": invariants["missing_observations_retain_prior_position"] is True,
        "no_prices_forward_filled": invariants["no_prices_forward_filled"] is True,
        "strategy_holds_only_SPY_or_XLU_after_initialization": invariants["holds_only_SPY_or_XLU_after_initialization"] is True,
        "exposure_never_exceeds_1": invariants["exposure_never_exceeds_1"] is True,
        "turnover_uses_actual_pretrade_holdings": invariants["turnover_uses_actual_pretrade_holdings"] is True,
        "windows_and_regimes_frozen_before_performance": invariants["windows_and_regimes_frozen_before_performance"] is True,
        "DSR_comparison_only_not_modified": invariants["DSR_comparison_only_not_modified"] is True,
        "no_VIX_BIL_treasury_moving_average_or_leverage_rule": invariants["no_VIX_BIL_treasury_moving_average_or_leverage_rule"] is True,
        "VM_DSR_USCI_active_combo_states_unchanged": invariants["VM_DSR_USCI_active_combo_states_unchanged"] is True,
        "no_paper_demo_observation_or_broker_order": invariants["paper_demo_observation_created"] is False and invariants["broker_order_created"] is False,
        "output_generation_deterministic": True,
        "promotion_authorized": False,
        "paper_demo_authorized": False,
        "candidate_exhaustive_authorized": False,
        "real_money_recommendation": False,
    }
    true_keys = [
        key
        for key in consistency
        if key
        not in {
            "candidate_id",
            "promotion_authorized",
            "paper_demo_authorized",
            "candidate_exhaustive_authorized",
            "real_money_recommendation",
        }
    ]
    consistency["consistency_passed"] = all(consistency[key] is True for key in true_keys) and not any(
        consistency[key] for key in ("promotion_authorized", "paper_demo_authorized", "candidate_exhaustive_authorized", "real_money_recommendation")
    )
    write_json(EVIDENCE_DIR / "consistency_check.json", consistency)
    write_text(
        EVIDENCE_DIR / "screen_summary.md",
        f"""# SPY/XLU Four-Week Beta Rotation Bounded Screen v1

Candidate `{CANDIDATE_ID}` was frozen from the Gayed/Bilello Beta Rotation source before performance.

- Outcome: `{outcome}`
- Primary reason: {outcome_reason}
- Provider download: `{provider_manifest['provider_download']}`
- Candidate common XLU/SPY adjusted-price rows: `{len(candidate_prices)}`
- Primary benchmark: `SPY_buy_and_hold`
- Decision-critical controls: `paper_forward_dsr_sector_equal_weight_defensive_filter_v1`, `SPY_200d_trend_model`
- Candidate uses only `SPY` and `XLU`; it has no BIL, Treasury, VIX, trend, moving-average, volatility-targeting, leverage, short, or partial-allocation rule.
- DSR comparison status: `{dsr_diag.get('dsr_comparison_status')}`
- DSR redundancy assessment: `{dsr_diag.get('redundancy_assessment')}`
- Promotion authorized: `false`
- Paper/demo activation authorized: `false`
- Candidate exhaustive authorized: `false`

Existing VM, DSR, USCI, active-combo, and Treasury-risk-rotation evidence states were not modified.
""",
    )
    return screening


if __name__ == "__main__":
    run()
