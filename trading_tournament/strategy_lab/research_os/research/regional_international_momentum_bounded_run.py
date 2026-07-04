from __future__ import annotations

import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.objective_reset.objective_reset_review import write_json, write_text
from strategy_lab.research_os.research.profit_oriented_research_batch_v1 import (
    active_combo_returns,
    benchmark_delta,
    cache_inventory,
    complete_rebalance_weight_frame,
    contribution_metrics,
    equity_curve,
    load_prices,
    max_drawdown,
    month_rebalance_mask,
    trade_count_and_turnover,
    weight_invariant_report,
    write_csv,
)
from strategy_lab.research_os.research.regional_international_momentum_bounded_design import (
    FAMILY_ID,
    LANE_ID,
    NEXT_ACTION_RUN,
    REQUIRED_SYMBOLS,
    RUN_READY,
)


SOURCE_DESIGN_DIR = (
    Path("evidence") / "research_recovery" / "regional_international_momentum_bounded_design" / "latest"
)
SOURCE_RESULTS = (
    Path("evidence")
    / "parallel_research_discovery"
    / "expanded_universe_batch_1"
    / "latest"
    / "expanded_universe_batch_1_results.csv"
)
OUTPUT_DIR = (
    Path("evidence") / "research_recovery" / "regional_international_momentum_bounded_run" / "latest"
)

EXPECTED_ROW_COUNT = 7
WEIGHT_TOLERANCE = 1e-6
PROJECT_START_EQUITY = 3000.0
PROJECT_STOP_DRAWDOWN = -600.0
RISK_CONTROL_ROLES = {"risk_control_half_bil_spy_gate", "risk_control_half_bil_top2"}
SOURCE_CONTEXT_ROLES = {"source_context_spy_gate", "source_context_top2_bil"}
CONTROL_ROLES = {"comparator_control", "cash_control", "regional_passive_context_control"}
REGIONAL_ASSETS = ("EWJ", "EWU", "EWG", "EWY", "INDA", "EFA", "EEM")
CORE_COMPARATOR_SYMBOLS = ("SPY", "BIL", "EFA", "EEM", "GLD", "IEF")

NEXT_ACTION_AUDIT = "audit_regional_international_momentum_bounded_lane_results"
NEXT_ACTION_FIX = "fix_regional_international_momentum_bounded_lane_run_methodology_issue"
NEXT_ACTION_CACHE = "restore_or_revalidate_regional_international_momentum_local_cache_before_bounded_run"
VALID_NEXT_ACTIONS = {NEXT_ACTION_AUDIT, NEXT_ACTION_FIX, NEXT_ACTION_CACHE}

ALLOWED_LABELS = {
    "regional_signal_data_blocked",
    "regional_signal_source_context_too_risky",
    "regional_signal_risk_control_pass",
    "regional_signal_return_destroyed",
    "regional_signal_drawdown_not_fixed",
    "regional_signal_too_cash_heavy",
    "regional_signal_duplicate_reference",
    "regional_signal_control_only",
}

RESULT_FIELDS = (
    "lane_id",
    "family_id",
    "variant_id",
    "variant_role",
    "source_registry_id",
    "source_context_status",
    "concept",
    "universe_group",
    "universe",
    "lookback",
    "top_n",
    "rebalance_frequency",
    "effective_start_date",
    "effective_end_date",
    "symbols_used",
    "comparator_references",
    "data_availability_status",
    "missing_symbols",
    "cagr",
    "total_return",
    "max_drawdown",
    "volatility",
    "calmar_or_return_drawdown_proxy",
    "worst_180_day_drawdown_project_dollars",
    "risk_buffer_vs_minus_600",
    "cagr_retention_vs_source_context",
    "total_return_retention_vs_source_context",
    "max_drawdown_reduction_vs_source_context",
    "average_bil_cash_share",
    "max_bil_cash_share",
    "duplicate_reference_correlation",
    "correlation_to_active_combo",
    "correlation_to_spy200d",
    "correlation_to_efa_eem_equal_weight",
    "same_window_return_vs_bil",
    "same_window_return_vs_spy",
    "same_window_return_vs_spy200d_frozen_control",
    "same_window_return_vs_efa_eem_equal_weight",
    "static_all_weather_benchmark_control_comparison",
    "active_vm_dsr_combo_max_drawdown_improvement",
    "active_vm_dsr_combo_total_return_drag",
    "baseline_variant_id",
    "baseline_total_return",
    "baseline_cagr",
    "baseline_max_drawdown",
    "baseline_total_return_delta",
    "trade_count",
    "turnover",
    "average_exposure",
    "max_daily_exposure",
    "max_daily_weight_sum",
    "average_weight_sum",
    "weight_sum_violation_count",
    "negative_weight_violation_count",
    "nan_weight_count",
    "impossible_cash_and_risky_exposure_days",
    "exposure_invariant_pass",
    "numeric_criteria_pass",
    "research_only_label",
    "promotion_eligibility",
    "paper_forward_eligibility",
    "candidate_exhaustive_eligibility",
    "methodology_notes",
)

CRITERIA_FIELDS = (
    "variant_id",
    "variant_role",
    "concept",
    "source_context_variant_id",
    "cagr_retention_vs_source_context",
    "cagr_retention_pass",
    "total_return_retention_vs_source_context",
    "total_return_retention_pass",
    "max_drawdown_reduction_vs_source_context",
    "max_drawdown_reduction_pass",
    "worst_180_day_drawdown_project_dollars",
    "worst_180_day_drawdown_pass",
    "risk_buffer_vs_minus_600",
    "risk_buffer_pass",
    "average_bil_cash_share",
    "bil_cash_share_pass",
    "duplicate_reference_correlation",
    "duplicate_reference_correlation_pass",
    "max_daily_exposure",
    "max_daily_exposure_pass",
    "max_daily_weight_sum",
    "max_daily_weight_sum_pass",
    "exposure_invariant_pass",
    "numeric_criteria_pass",
    "research_only_label",
)

ALIGNMENT_FIELDS = (
    "variant_id",
    "required_symbols",
    "missing_symbols",
    "effective_start_date",
    "effective_end_date",
    "limiting_start_symbols",
    "limiting_end_symbols",
    "common_date_count",
    "alignment_status",
)

SOURCE_REPRO_FIELDS = (
    "source_registry_id",
    "source_context_variant_id",
    "source_evidence_found",
    "source_decision",
    "source_180d_worst_drawdown",
    "source_risk_buffer_vs_minus_600",
    "recomputed_cagr",
    "recomputed_total_return",
    "recomputed_max_drawdown",
    "recomputed_worst_180_day_drawdown_project_dollars",
    "recomputed_risk_buffer_vs_minus_600",
    "source_context_reproduction_status",
)

BASELINE_FIELDS = (
    "variant_id",
    "variant_role",
    "baseline_variant_id",
    "baseline_total_return",
    "baseline_cagr",
    "baseline_max_drawdown",
    "strategy_total_return",
    "strategy_cagr",
    "strategy_max_drawdown",
    "baseline_total_return_delta",
    "same_window_return_vs_bil",
    "same_window_return_vs_spy",
    "same_window_return_vs_spy200d_frozen_control",
    "same_window_return_vs_efa_eem_equal_weight",
    "static_all_weather_benchmark_control_comparison",
)

REQUIRED_FILES = (
    "regional_international_momentum_bounded_run_manifest.json",
    "regional_international_momentum_bounded_run_consistency_check.json",
    "regional_international_momentum_bounded_row_results.csv",
    "regional_international_momentum_bounded_numeric_criteria_results.csv",
    "source_context_reproduction_report.csv",
    "source_context_reproduction_report.md",
    "data_alignment_effective_window_report.csv",
    "data_alignment_effective_window_report.md",
    "symbol_coverage_report.csv",
    "symbol_coverage_report.md",
    "baseline_comparator_report.csv",
    "baseline_comparator_report.md",
    "exposure_invariant_report.md",
    "role_label_summary.md",
    "regional_international_momentum_bounded_run_summary.md",
    "do_not_promote_from_regional_international_momentum_bounded_run.md",
    "regional_international_momentum_bounded_run_next_action.md",
)


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def parse_float(value: Any, default: float = float("nan")) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def finite(value: Any) -> bool:
    return math.isfinite(parse_float(value))


def safe_corr(left: pd.Series, right: pd.Series) -> float:
    aligned = pd.concat([left.rename("left"), right.rename("right")], axis=1).dropna()
    if len(aligned) < 252:
        return float("nan")
    return float(aligned["left"].corr(aligned["right"]))


def normalize_target(target: dict[str, float], columns: list[str]) -> dict[str, float]:
    clean = {symbol: max(0.0, float(target.get(symbol, 0.0))) for symbol in columns}
    total = sum(clean.values())
    if total > 1.0 + WEIGHT_TOLERANCE:
        for symbol in clean:
            clean[symbol] /= total
    if "BIL" in clean:
        risky = sum(value for symbol, value in clean.items() if symbol != "BIL")
        clean["BIL"] = max(clean.get("BIL", 0.0), 1.0 - risky)
        total = sum(clean.values())
        if total > 1.0 + WEIGHT_TOLERANCE:
            clean["BIL"] = max(0.0, 1.0 - sum(value for symbol, value in clean.items() if symbol != "BIL"))
    return clean


def available_at(close: pd.DataFrame, symbol: str, t: int, lookback: int = 0) -> bool:
    return bool(
        symbol in close.columns
        and t - lookback >= 0
        and pd.notna(close.iloc[t][symbol])
        and pd.notna(close.iloc[t - lookback][symbol])
    )


def source_eligible(close: pd.DataFrame, symbol: str, t: int) -> bool:
    if symbol not in close.columns or t < 200 or pd.isna(close.iloc[t][symbol]):
        return False
    window = close[symbol].iloc[t - 199 : t + 1].dropna()
    return bool(len(window) >= 200 and float(close.iloc[t][symbol]) > float(window.mean()))


def source_ret126(close: pd.DataFrame, symbol: str, t: int) -> float:
    return float(close.iloc[t][symbol] / close.iloc[t - 126][symbol] - 1.0) if available_at(close, symbol, t, 126) else float("nan")


def source_vol60(close: pd.DataFrame, symbol: str, t: int) -> float:
    if symbol not in close.columns or t < 60:
        return float("nan")
    returns = close[symbol].pct_change(fill_method=None).iloc[t - 59 : t + 1].dropna()
    return float(returns.std()) if len(returns) >= 45 else float("nan")


def source_ranked(close: pd.DataFrame, symbols: list[str], t: int) -> list[str]:
    scored: list[tuple[str, float]] = []
    for symbol in symbols:
        if symbol == "BIL" or not source_eligible(close, symbol, t):
            continue
        ret = source_ret126(close, symbol, t)
        vol = source_vol60(close, symbol, t)
        score = ret / vol if np.isfinite(ret) and np.isfinite(vol) and vol > 0 else float("nan")
        if np.isfinite(score):
            scored.append((symbol, score))
    return [symbol for symbol, _score in sorted(scored, key=lambda item: item[1], reverse=True)]


def top2_target(close: pd.DataFrame, columns: list[str], signal_pos: int, top_n: int, *, spy_gate: bool) -> dict[str, float]:
    target = {symbol: 0.0 for symbol in columns}
    if signal_pos < 0:
        if "BIL" in target:
            target["BIL"] = 1.0
        return normalize_target(target, columns)
    if spy_gate and not source_eligible(close, "SPY", signal_pos):
        if "BIL" in target:
            target["BIL"] = 1.0
        return normalize_target(target, columns)
    available_regional = [symbol for symbol in REGIONAL_ASSETS if symbol in columns]
    picks = source_ranked(close, available_regional, signal_pos)[:top_n]
    slot = 1.0 / max(top_n, 1)
    for symbol in picks:
        target[symbol] += slot
    if "BIL" in target:
        target["BIL"] += slot * max(0, top_n - len(picks))
    return normalize_target(target, columns)


def regional_source_weights(prices: pd.DataFrame, *, top_n: int = 2, spy_gate: bool = False) -> pd.DataFrame:
    columns = list(prices.columns)
    rebalance_targets: dict[pd.Timestamp, dict[str, float]] = {}
    for date in prices.index[month_rebalance_mask(prices.index)]:
        pos = int(prices.index.get_loc(date))
        signal_pos = pos - 1
        rebalance_targets[pd.Timestamp(date)] = top2_target(prices, columns, signal_pos, top_n, spy_gate=spy_gate)
    return complete_rebalance_weight_frame(prices.index, columns, rebalance_targets)


def half_bil_weights(source: pd.DataFrame) -> pd.DataFrame:
    weights = pd.DataFrame(0.0, index=source.index, columns=source.columns)
    risky_cols = [column for column in source.columns if column != "BIL"]
    if risky_cols:
        weights[risky_cols] = source[risky_cols] * 0.5
    if "BIL" in weights.columns:
        weights["BIL"] = 1.0 - weights[risky_cols].sum(axis=1)
    return weights.reindex(columns=source.columns).fillna(0.0)


def spy200d_weights(prices: pd.DataFrame) -> pd.DataFrame:
    columns = list(prices.columns)
    prior_spy = prices["SPY"].shift(1)
    prior_sma = prices["SPY"].shift(1).rolling(200, min_periods=100).mean()
    risk_on = prior_spy > prior_sma
    rebalance_targets: dict[pd.Timestamp, dict[str, float]] = {}
    for date in prices.index[month_rebalance_mask(prices.index)]:
        target = {symbol: 0.0 for symbol in columns}
        if bool(risk_on.loc[date]):
            target["SPY"] = 1.0
        elif "BIL" in target:
            target["BIL"] = 1.0
        rebalance_targets[pd.Timestamp(date)] = normalize_target(target, columns)
    return complete_rebalance_weight_frame(prices.index, columns, rebalance_targets)


def bil_weights(prices: pd.DataFrame) -> pd.DataFrame:
    weights = pd.DataFrame(0.0, index=prices.index, columns=prices.columns)
    if "BIL" in weights.columns:
        weights["BIL"] = 1.0
    return weights


def efa_eem_equal_weight(prices: pd.DataFrame) -> pd.DataFrame:
    weights = pd.DataFrame(0.0, index=prices.index, columns=prices.columns)
    for symbol in ("EFA", "EEM"):
        if symbol in weights.columns:
            weights[symbol] = 0.5
    return weights


def static_all_weather_returns(root: Path, index: pd.DatetimeIndex) -> pd.Series:
    symbols = ("SPY", "IEF", "GLD", "BIL")
    prices = load_prices(root, symbols).ffill()
    if prices.empty or not set(symbols).issubset(prices.columns):
        return pd.Series(dtype=float, name="static_all_weather")
    returns = prices.pct_change(fill_method=None).fillna(0.0)
    weights = pd.DataFrame(0.0, index=prices.index, columns=list(symbols))
    weights["SPY"] = 0.30
    weights["IEF"] = 0.40
    weights["GLD"] = 0.20
    weights["BIL"] = 0.10
    daily = (weights.shift(1).fillna(0.0) * returns).sum(axis=1).rename("static_all_weather")
    return daily.reindex(index).dropna()


def portfolio_returns(prices: pd.DataFrame, weights: pd.DataFrame) -> pd.Series:
    returns = prices.pct_change(fill_method=None).fillna(0.0)
    aligned_weights = weights.reindex(prices.index).ffill().fillna(0.0).reindex(columns=prices.columns, fill_value=0.0)
    return (aligned_weights.shift(1).fillna(0.0) * returns).sum(axis=1)


def project_window_stats(daily: pd.Series, window: int = 180) -> dict[str, float]:
    daily = daily.dropna()
    if len(daily) <= window:
        return {
            "worst_180_day_drawdown_project_dollars": float("nan"),
            "risk_buffer_vs_minus_600": float("nan"),
        }
    values = daily.to_numpy(dtype=float)
    drawdowns: list[float] = []
    for start in range(0, len(values) - window + 1):
        path = PROJECT_START_EQUITY * np.cumprod(1.0 + values[start : start + window])
        full_path = np.concatenate([[PROJECT_START_EQUITY], path])
        running_peak = np.maximum.accumulate(full_path)
        drawdowns.append(float((full_path - running_peak).min()))
    worst = min(drawdowns)
    return {
        "worst_180_day_drawdown_project_dollars": worst,
        "risk_buffer_vs_minus_600": worst - PROJECT_STOP_DRAWDOWN,
    }


def metrics_for_returns(daily: pd.Series, weights: pd.DataFrame) -> dict[str, Any]:
    daily = daily.dropna()
    if daily.empty:
        return {}
    eq = equity_curve(daily)
    years = max((daily.index.max() - daily.index.min()).days / 365.25, 1e-9)
    total_return = float(eq.iloc[-1] - 1.0)
    cagr = float(eq.iloc[-1] ** (1.0 / years) - 1.0)
    volatility = float(daily.std() * np.sqrt(252.0))
    mdd = max_drawdown(eq)
    calmar = float(cagr / abs(mdd)) if mdd < 0 else float("nan")
    trades, turnover = trade_count_and_turnover(weights)
    exposure_cols = [column for column in weights.columns if column != "BIL"]
    risky = weights[exposure_cols].sum(axis=1) if exposure_cols else pd.Series(0.0, index=weights.index)
    cash = weights["BIL"] if "BIL" in weights.columns else (1.0 - risky).clip(lower=0.0)
    invariant = weight_invariant_report(weights, tolerance=WEIGHT_TOLERANCE)
    return {
        "effective_start_date": daily.index.min().date().isoformat(),
        "effective_end_date": daily.index.max().date().isoformat(),
        "total_return": total_return,
        "cagr": cagr,
        "max_drawdown": mdd,
        "volatility": volatility,
        "calmar_or_return_drawdown_proxy": calmar,
        "trade_count": trades,
        "turnover": turnover,
        "average_exposure": float(risky.mean()) if len(risky) else 0.0,
        "average_bil_cash_share": float(cash.mean()) if len(cash) else 0.0,
        "max_bil_cash_share": float(cash.max()) if len(cash) else 0.0,
        **invariant,
        **project_window_stats(daily),
    }


def price_ranges(root: Path, symbols: list[str]) -> dict[str, dict[str, Any]]:
    inventory = {row["symbol"]: row for row in cache_inventory(root)}
    ranges: dict[str, dict[str, Any]] = {}
    for symbol in symbols:
        info = inventory.get(symbol, {})
        ranges[symbol] = {
            "symbol": symbol,
            "status": info.get("status", "missing"),
            "rows": info.get("rows", 0),
            "first_date": info.get("first_date", ""),
            "last_date": info.get("last_date", ""),
            "path": info.get("path", ""),
        }
    return ranges


def aligned_price_frame(root: Path, row: dict[str, str]) -> tuple[pd.DataFrame, dict[str, Any]]:
    row_symbols = [symbol for symbol in row["universe"].split("|") if symbol]
    symbols = list(dict.fromkeys(row_symbols + ["SPY", "BIL", "EFA", "EEM"]))
    ranges = price_ranges(root, symbols)
    missing = [symbol for symbol in row_symbols if ranges[symbol]["status"] != "cache_ready"]
    if missing:
        return pd.DataFrame(), {
            "variant_id": row["variant_id"],
            "required_symbols": "|".join(row_symbols),
            "missing_symbols": "|".join(missing),
            "effective_start_date": "",
            "effective_end_date": "",
            "limiting_start_symbols": "",
            "limiting_end_symbols": "",
            "common_date_count": 0,
            "alignment_status": "data_blocked_missing_required_symbols",
        }
    prices = load_prices(root, tuple(symbols)).sort_index().ffill()
    if prices.empty or "BIL" not in prices.columns or "SPY" not in prices.columns:
        return pd.DataFrame(), {
            "variant_id": row["variant_id"],
            "required_symbols": "|".join(row_symbols),
            "missing_symbols": "",
            "effective_start_date": "",
            "effective_end_date": "",
            "limiting_start_symbols": "",
            "limiting_end_symbols": "",
            "common_date_count": 0,
            "alignment_status": "data_blocked_no_comparator_frame",
        }
    ready = prices[["BIL", "SPY"]].notna().all(axis=1)
    aligned = prices.loc[ready].copy()
    first_dates = {symbol: ranges[symbol]["first_date"] for symbol in row_symbols if ranges[symbol]["first_date"]}
    last_dates = {symbol: ranges[symbol]["last_date"] for symbol in row_symbols if ranges[symbol]["last_date"]}
    max_first = max(first_dates.values()) if first_dates else ""
    min_last = min(last_dates.values()) if last_dates else ""
    return aligned, {
        "variant_id": row["variant_id"],
        "required_symbols": "|".join(row_symbols),
        "missing_symbols": "",
        "effective_start_date": aligned.index.min().date().isoformat() if not aligned.empty else "",
        "effective_end_date": aligned.index.max().date().isoformat() if not aligned.empty else "",
        "limiting_start_symbols": "|".join([symbol for symbol, value in first_dates.items() if value == max_first]),
        "limiting_end_symbols": "|".join([symbol for symbol, value in last_dates.items() if value == min_last]),
        "common_date_count": int(len(aligned)),
        "alignment_status": "per_asset_availability_with_bil_spy_common_frame",
    }


def weights_for_row(row: dict[str, str], prices: pd.DataFrame) -> pd.DataFrame:
    role = row["variant_role"]
    top_n = int(float(row["top_n"])) if row.get("top_n") else 2
    if role == "source_context_spy_gate":
        return regional_source_weights(prices, top_n=top_n, spy_gate=True)
    if role == "source_context_top2_bil":
        return regional_source_weights(prices, top_n=top_n, spy_gate=False)
    if role == "risk_control_half_bil_spy_gate":
        return half_bil_weights(regional_source_weights(prices, top_n=top_n, spy_gate=True))
    if role == "risk_control_half_bil_top2":
        return half_bil_weights(regional_source_weights(prices, top_n=top_n, spy_gate=False))
    if role == "comparator_control":
        return spy200d_weights(prices)
    if role == "cash_control":
        return bil_weights(prices)
    if role == "regional_passive_context_control":
        return efa_eem_equal_weight(prices)
    return bil_weights(prices)


def baseline_weights(row: dict[str, str], prices: pd.DataFrame) -> pd.DataFrame:
    baseline = row["baseline_variant_id"]
    if baseline == "rim_regional_momentum_with_spy_gate_v1":
        return regional_source_weights(prices, top_n=2, spy_gate=True)
    if baseline == "rim_regional_top2_momentum_bil_v1":
        return regional_source_weights(prices, top_n=2, spy_gate=False)
    if baseline == "SPY_200d_trend_model":
        return spy200d_weights(prices)
    if baseline == "BIL_cash_proxy":
        return bil_weights(prices)
    if baseline == "EFA_EEM_equal_weight_passive_context":
        return efa_eem_equal_weight(prices)
    return weights_for_row(row, prices)


def source_evidence_rows(root: Path) -> dict[str, dict[str, str]]:
    path = root / SOURCE_RESULTS
    if not path.exists():
        return {}
    rows = read_csv_rows(path)
    return {row.get("strategy_id", ""): row for row in rows}


def data_blocked_row(row: dict[str, str], alignment: dict[str, Any], reason: str) -> dict[str, Any]:
    return {
        "lane_id": LANE_ID,
        "family_id": FAMILY_ID,
        "variant_id": row.get("variant_id", ""),
        "variant_role": row.get("variant_role", ""),
        "source_registry_id": row.get("source_registry_id", ""),
        "source_context_status": row.get("source_context_status", ""),
        "concept": row.get("concept", ""),
        "universe_group": row.get("universe_group", ""),
        "universe": row.get("universe", ""),
        "lookback": row.get("lookback_days", ""),
        "top_n": row.get("top_n", ""),
        "rebalance_frequency": row.get("rebalance_frequency", ""),
        "effective_start_date": "",
        "effective_end_date": "",
        "symbols_used": "",
        "comparator_references": row.get("comparator_references", ""),
        "data_availability_status": "data_blocked",
        "missing_symbols": alignment.get("missing_symbols", ""),
        "exposure_invariant_pass": False,
        "numeric_criteria_pass": False,
        "research_only_label": "regional_signal_data_blocked",
        "promotion_eligibility": False,
        "paper_forward_eligibility": False,
        "candidate_exhaustive_eligibility": False,
        "methodology_notes": reason,
    }


def evaluate_row(root: Path, row: dict[str, str], active_returns: pd.Series) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    prices, alignment = aligned_price_frame(root, row)
    if prices.empty or len(prices) < 252:
        blocked = data_blocked_row(row, alignment, "required local-cache history unavailable")
        return blocked, alignment, {}

    weights = weights_for_row(row, prices)
    daily = portfolio_returns(prices, weights).rename(row["variant_id"])
    baseline_w = baseline_weights(row, prices)
    baseline_daily = portfolio_returns(prices, baseline_w).rename(row["baseline_variant_id"])
    bil_returns = portfolio_returns(prices, bil_weights(prices)).rename("BIL")
    spy_weights = pd.DataFrame(0.0, index=prices.index, columns=prices.columns)
    spy_weights["SPY"] = 1.0
    spy_returns = portfolio_returns(prices, spy_weights).rename("SPY")
    spy200d_returns = portfolio_returns(prices, spy200d_weights(prices)).rename("SPY_200d")
    efa_eem_returns = portfolio_returns(prices, efa_eem_equal_weight(prices)).rename("EFA_EEM_equal_weight")
    static_returns = static_all_weather_returns(root, daily.index)
    contribution = contribution_metrics(daily, active_returns)

    metrics = metrics_for_returns(daily, weights)
    baseline = metrics_for_returns(baseline_daily, baseline_w)
    corr_spy200d = safe_corr(daily, spy200d_returns)
    corr_efa_eem = safe_corr(daily, efa_eem_returns)
    corr_active = contribution["active_combo_correlation"]
    duplicate_values = [value for value in (corr_spy200d, corr_efa_eem, corr_active) if finite(value)]
    duplicate_reference = max(duplicate_values) if duplicate_values else float("nan")
    invariant_pass = (
        metrics["max_daily_exposure"] <= 1.000001
        and metrics["max_daily_weight_sum"] <= 1.000001
        and int(metrics["weight_sum_violation_count"]) == 0
        and int(metrics["negative_weight_violation_count"]) == 0
        and int(metrics["nan_weight_count"]) == 0
        and int(metrics["impossible_cash_and_risky_exposure_days"]) == 0
    )

    result = {
        "lane_id": LANE_ID,
        "family_id": FAMILY_ID,
        "variant_id": row["variant_id"],
        "variant_role": row["variant_role"],
        "source_registry_id": row["source_registry_id"],
        "source_context_status": row["source_context_status"],
        "concept": row["concept"],
        "universe_group": row["universe_group"],
        "universe": row["universe"],
        "lookback": int(float(row["lookback_days"])),
        "top_n": int(float(row["top_n"])),
        "rebalance_frequency": row["rebalance_frequency"],
        "symbols_used": "|".join(prices.columns),
        "comparator_references": row["comparator_references"],
        "data_availability_status": "cache_ready",
        "missing_symbols": "",
        **metrics,
        "cagr_retention_vs_source_context": float("nan"),
        "total_return_retention_vs_source_context": float("nan"),
        "max_drawdown_reduction_vs_source_context": float("nan"),
        "duplicate_reference_correlation": duplicate_reference,
        "correlation_to_active_combo": corr_active,
        "correlation_to_spy200d": corr_spy200d,
        "correlation_to_efa_eem_equal_weight": corr_efa_eem,
        "same_window_return_vs_bil": benchmark_delta(daily, bil_returns),
        "same_window_return_vs_spy": benchmark_delta(daily, spy_returns),
        "same_window_return_vs_spy200d_frozen_control": benchmark_delta(daily, spy200d_returns),
        "same_window_return_vs_efa_eem_equal_weight": benchmark_delta(daily, efa_eem_returns),
        "static_all_weather_benchmark_control_comparison": benchmark_delta(daily, static_returns) if not static_returns.empty else float("nan"),
        "active_vm_dsr_combo_max_drawdown_improvement": contribution["active_combo_blend_drawdown_delta"],
        "active_vm_dsr_combo_total_return_drag": contribution["active_combo_blend_total_return_delta"],
        "baseline_variant_id": row["baseline_variant_id"],
        "baseline_total_return": baseline.get("total_return", float("nan")),
        "baseline_cagr": baseline.get("cagr", float("nan")),
        "baseline_max_drawdown": baseline.get("max_drawdown", float("nan")),
        "baseline_total_return_delta": metrics["total_return"] - baseline.get("total_return", float("nan"))
        if finite(baseline.get("total_return", float("nan")))
        else float("nan"),
        "exposure_invariant_pass": invariant_pass,
        "numeric_criteria_pass": False,
        "research_only_label": "regional_signal_control_only"
        if row["variant_role"] in CONTROL_ROLES
        else "regional_signal_source_context_too_risky",
        "promotion_eligibility": False,
        "paper_forward_eligibility": False,
        "candidate_exhaustive_eligibility": False,
        "methodology_notes": "approved seven-row regional/international bounded diagnostic run using local cache only",
    }
    baseline_row = {field: result.get(field, "") for field in BASELINE_FIELDS}
    baseline_row["strategy_total_return"] = result["total_return"]
    baseline_row["strategy_cagr"] = result["cagr"]
    baseline_row["strategy_max_drawdown"] = result["max_drawdown"]
    return result, alignment, baseline_row


def risk_control_criteria(row: dict[str, Any], source_row: dict[str, Any] | None) -> dict[str, Any]:
    if not source_row:
        cagr_retention = total_retention = drawdown_reduction = float("nan")
        source_variant_id = ""
    else:
        source_variant_id = str(source_row.get("variant_id", ""))
        source_cagr = parse_float(source_row.get("cagr"))
        source_total = parse_float(source_row.get("total_return"))
        source_mdd = parse_float(source_row.get("max_drawdown"))
        cagr_retention = parse_float(row.get("cagr")) / source_cagr if source_cagr > 0 else float("nan")
        total_retention = parse_float(row.get("total_return")) / source_total if source_total > 0 else float("nan")
        drawdown_reduction = (abs(source_mdd) - abs(parse_float(row.get("max_drawdown")))) / abs(source_mdd) if source_mdd < 0 else float("nan")
    avg_bil = parse_float(row.get("average_bil_cash_share"))
    duplicate = parse_float(row.get("duplicate_reference_correlation"))
    max_exposure = parse_float(row.get("max_daily_exposure"))
    max_weight = parse_float(row.get("max_daily_weight_sum"))
    worst_180 = parse_float(row.get("worst_180_day_drawdown_project_dollars"))
    risk_buffer = parse_float(row.get("risk_buffer_vs_minus_600"))
    flags = {
        "cagr_retention_pass": finite(cagr_retention) and cagr_retention >= 0.6000,
        "total_return_retention_pass": finite(total_retention) and total_retention >= 0.6000,
        "max_drawdown_reduction_pass": finite(drawdown_reduction) and drawdown_reduction >= 0.2500,
        "worst_180_day_drawdown_pass": finite(worst_180) and worst_180 >= -500.0000,
        "risk_buffer_pass": finite(risk_buffer) and risk_buffer >= 100.0000,
        "bil_cash_share_pass": finite(avg_bil) and avg_bil <= 0.6500,
        "duplicate_reference_correlation_pass": (not finite(duplicate)) or duplicate < 0.9000,
        "max_daily_exposure_pass": finite(max_exposure) and max_exposure <= 1.000001,
        "max_daily_weight_sum_pass": finite(max_weight) and max_weight <= 1.000001,
    }
    exposure_pass = row.get("exposure_invariant_pass") is True
    numeric_pass = all(flags.values()) and exposure_pass
    if numeric_pass:
        label = "regional_signal_risk_control_pass"
    elif flags["cagr_retention_pass"] is False or flags["total_return_retention_pass"] is False:
        label = "regional_signal_return_destroyed"
    elif flags["max_drawdown_reduction_pass"] is False or flags["worst_180_day_drawdown_pass"] is False or flags["risk_buffer_pass"] is False:
        label = "regional_signal_drawdown_not_fixed"
    elif flags["bil_cash_share_pass"] is False:
        label = "regional_signal_too_cash_heavy"
    elif flags["duplicate_reference_correlation_pass"] is False:
        label = "regional_signal_duplicate_reference"
    else:
        label = "regional_signal_drawdown_not_fixed"
    return {
        "variant_id": row["variant_id"],
        "variant_role": row["variant_role"],
        "concept": row["concept"],
        "source_context_variant_id": source_variant_id,
        "cagr_retention_vs_source_context": cagr_retention,
        "total_return_retention_vs_source_context": total_retention,
        "max_drawdown_reduction_vs_source_context": drawdown_reduction,
        "worst_180_day_drawdown_project_dollars": worst_180,
        "risk_buffer_vs_minus_600": risk_buffer,
        "average_bil_cash_share": avg_bil,
        "duplicate_reference_correlation": duplicate,
        "max_daily_exposure": max_exposure,
        "max_daily_weight_sum": max_weight,
        "exposure_invariant_pass": exposure_pass,
        "numeric_criteria_pass": numeric_pass,
        "research_only_label": label,
        **flags,
    }


def apply_labels_and_criteria(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    source_by_registry = {
        row["source_registry_id"]: row
        for row in rows
        if row.get("variant_role") in SOURCE_CONTEXT_ROLES and row.get("data_availability_status") == "cache_ready"
    }
    criteria_rows: list[dict[str, Any]] = []
    for row in rows:
        if row.get("data_availability_status") != "cache_ready":
            continue
        if row.get("variant_role") in RISK_CONTROL_ROLES:
            criteria = risk_control_criteria(row, source_by_registry.get(row.get("source_registry_id", "")))
            for key in (
                "cagr_retention_vs_source_context",
                "total_return_retention_vs_source_context",
                "max_drawdown_reduction_vs_source_context",
            ):
                row[key] = criteria[key]
            row["numeric_criteria_pass"] = criteria["numeric_criteria_pass"]
            row["research_only_label"] = criteria["research_only_label"]
            criteria_rows.append(criteria)
        else:
            criteria_rows.append(
                {
                    "variant_id": row["variant_id"],
                    "variant_role": row["variant_role"],
                    "concept": row["concept"],
                    "source_context_variant_id": "",
                    "cagr_retention_vs_source_context": "",
                    "cagr_retention_pass": False,
                    "total_return_retention_vs_source_context": "",
                    "total_return_retention_pass": False,
                    "max_drawdown_reduction_vs_source_context": "",
                    "max_drawdown_reduction_pass": False,
                    "worst_180_day_drawdown_project_dollars": row.get("worst_180_day_drawdown_project_dollars", ""),
                    "worst_180_day_drawdown_pass": False,
                    "risk_buffer_vs_minus_600": row.get("risk_buffer_vs_minus_600", ""),
                    "risk_buffer_pass": False,
                    "average_bil_cash_share": row.get("average_bil_cash_share", ""),
                    "bil_cash_share_pass": False,
                    "duplicate_reference_correlation": row.get("duplicate_reference_correlation", ""),
                    "duplicate_reference_correlation_pass": False,
                    "max_daily_exposure": row.get("max_daily_exposure", ""),
                    "max_daily_exposure_pass": parse_float(row.get("max_daily_exposure")) <= 1.000001,
                    "max_daily_weight_sum": row.get("max_daily_weight_sum", ""),
                    "max_daily_weight_sum_pass": parse_float(row.get("max_daily_weight_sum")) <= 1.000001,
                    "exposure_invariant_pass": row.get("exposure_invariant_pass", False),
                    "numeric_criteria_pass": False,
                    "research_only_label": row.get("research_only_label", ""),
                }
            )
    return criteria_rows


def source_reproduction_rows(root: Path, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sources = source_evidence_rows(root)
    out: list[dict[str, Any]] = []
    for row in rows:
        if row.get("variant_role") not in SOURCE_CONTEXT_ROLES:
            continue
        source = sources.get(row.get("source_registry_id", ""), {})
        out.append(
            {
                "source_registry_id": row.get("source_registry_id", ""),
                "source_context_variant_id": row.get("variant_id", ""),
                "source_evidence_found": bool(source),
                "source_decision": source.get("decision", ""),
                "source_180d_worst_drawdown": source.get("180d_worst_drawdown", ""),
                "source_risk_buffer_vs_minus_600": source.get("risk_buffer_vs_minus_600", ""),
                "recomputed_cagr": row.get("cagr", ""),
                "recomputed_total_return": row.get("total_return", ""),
                "recomputed_max_drawdown": row.get("max_drawdown", ""),
                "recomputed_worst_180_day_drawdown_project_dollars": row.get("worst_180_day_drawdown_project_dollars", ""),
                "recomputed_risk_buffer_vs_minus_600": row.get("risk_buffer_vs_minus_600", ""),
                "source_context_reproduction_status": "source_context_recomputed_current_cache_context_only"
                if bool(source)
                else "source_evidence_missing",
            }
        )
    return out


def load_preflight(root: Path) -> dict[str, Any]:
    design = read_json(root / SOURCE_DESIGN_DIR / "regional_international_momentum_bounded_design_manifest.json")
    return {
        "design_run_ready": design.get("run_readiness_decision") == RUN_READY,
        "design_next_action_correct": design.get("next_action") == NEXT_ACTION_RUN,
        "local_cache_complete_from_design": design.get("local_cache_complete") is True,
        "source_lineage_verified": design.get("source_lineage_verified") is True,
        "source_context_only": design.get("source_evidence_context_only") is True,
        "provider_download_required": False,
        "intraday_data_required": False,
    }


def evaluate_lane(root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    design_rows = read_csv_rows(root / SOURCE_DESIGN_DIR / "planned_variant_design_table.csv")
    active_returns = active_combo_returns(root)
    rows: list[dict[str, Any]] = []
    alignments: list[dict[str, Any]] = []
    baseline_rows: list[dict[str, Any]] = []
    for row in design_rows:
        result, alignment, baseline = evaluate_row(root, row, active_returns)
        rows.append(result)
        alignments.append({field: alignment.get(field, "") for field in ALIGNMENT_FIELDS})
        if baseline:
            baseline_rows.append(baseline)
    criteria = apply_labels_and_criteria(rows)
    source_repro = source_reproduction_rows(root, rows)
    preflight = {
        **load_preflight(root),
        "planned_row_count_from_design": len(design_rows),
        "planned_variant_ids": [row["variant_id"] for row in design_rows],
        "evaluated_variant_ids": [row["variant_id"] for row in rows],
    }
    return rows, alignments, criteria, baseline_rows, source_repro, preflight


def label_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {label: sum(1 for row in rows if row.get("research_only_label") == label) for label in ALLOWED_LABELS}


def pass_fail_summary(rows: list[dict[str, Any]], field: str) -> list[dict[str, Any]]:
    if not rows:
        return []
    df = pd.DataFrame(rows)
    summary: list[dict[str, Any]] = []
    for value, subset in df.groupby(field):
        numeric = subset["numeric_criteria_pass"].astype(bool)
        summary.append(
            {
                field: value,
                "row_count": int(len(subset)),
                "numeric_pass_count": int(numeric.sum()),
                "numeric_fail_count": int((~numeric).sum()),
                "median_cagr": float(pd.to_numeric(subset["cagr"], errors="coerce").median()),
                "median_max_drawdown": float(pd.to_numeric(subset["max_drawdown"], errors="coerce").median()),
                "median_average_bil_cash_share": float(
                    pd.to_numeric(subset["average_bil_cash_share"], errors="coerce").median()
                ),
            }
        )
    return summary


def symbol_coverage_rows(root: Path, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    required = {symbol for symbol in REQUIRED_SYMBOLS}
    required.update(CORE_COMPARATOR_SYMBOLS)
    ranges = price_ranges(root, sorted(required))
    out: list[dict[str, Any]] = []
    for symbol in sorted(required):
        used_by = [
            row["variant_id"]
            for row in rows
            if symbol in str(row.get("symbols_used", "")).split("|")
            or symbol in str(row.get("universe", "")).split("|")
        ]
        out.append(
            {
                "symbol": symbol,
                "status": ranges[symbol]["status"],
                "rows": ranges[symbol]["rows"],
                "first_date": ranges[symbol]["first_date"],
                "last_date": ranges[symbol]["last_date"],
                "used_by_variant_count": len(used_by),
                "used_by_variants": "|".join(used_by),
                "path": ranges[symbol]["path"],
            }
        )
    return out


def manifest_payload(created: str, output: Path, rows: list[dict[str, Any]], preflight: dict[str, Any]) -> dict[str, Any]:
    counts = label_counts(rows)
    data_blocked = [row for row in rows if row.get("data_availability_status") != "cache_ready"]
    invariant_failures = [row for row in rows if row.get("exposure_invariant_pass") is not True]
    max_exposure = max([parse_float(row.get("max_daily_exposure"), 0.0) for row in rows] or [0.0])
    max_weight = max([parse_float(row.get("max_daily_weight_sum"), 0.0) for row in rows] or [0.0])
    hard_invariants_pass = (
        not invariant_failures
        and max_exposure <= 1.000001
        and max_weight <= 1.000001
        and preflight["design_run_ready"]
        and preflight["design_next_action_correct"]
        and preflight["local_cache_complete_from_design"]
    )
    if data_blocked:
        next_action = NEXT_ACTION_CACHE
    elif hard_invariants_pass and len(rows) == EXPECTED_ROW_COUNT:
        next_action = NEXT_ACTION_AUDIT
    else:
        next_action = NEXT_ACTION_FIX
    return {
        "created_utc": created,
        "evidence_path": str(output.resolve()),
        "regional_international_momentum_bounded_lane_run": True,
        "lane_id": LANE_ID,
        "family_id": FAMILY_ID,
        "source_design_run_ready": preflight["design_run_ready"],
        "source_design_next_action_correct": preflight["design_next_action_correct"],
        "source_lineage_verified": preflight["source_lineage_verified"],
        "source_context_only": preflight["source_context_only"],
        "variant_count_planned": EXPECTED_ROW_COUNT,
        "variant_count_evaluated": len(rows),
        "source_context_row_count": sum(1 for row in rows if row.get("variant_role") in SOURCE_CONTEXT_ROLES),
        "risk_control_row_count": sum(1 for row in rows if row.get("variant_role") in RISK_CONTROL_ROLES),
        "control_row_count": sum(1 for row in rows if row.get("variant_role") in CONTROL_ROLES),
        "new_rows_added": False,
        "new_assets_added": False,
        "new_lookbacks_added": False,
        "new_concepts_added": False,
        "new_variants_created": False,
        "new_families_created": False,
        "hidden_parameter_grid_created": False,
        "strategy_discovery_run": False,
        "new_research_batch_run": False,
        "uses_local_cache_only": True,
        "provider_refresh_run": False,
        "provider_download": False,
        "intraday_data_used": False,
        "leverage_allowed": False,
        "shorting_allowed": False,
        "options_allowed": False,
        "direct_futures_allowed": False,
        "forex_allowed": False,
        "margin_allowed": False,
        "broker_api_called": False,
        "broker_orders_submitted": False,
        "broker_orders_cancelled": False,
        "broker_orders_reconciled": False,
        "live_orders": False,
        "real_money_recommendation": False,
        "promotion_candidates_created": False,
        "candidate_exhaustive_run": False,
        "paper_forward_activation": False,
        "new_paper_forward_candidate_created": False,
        "best_single_variant_promoted": False,
        "research_outputs_remain_non_promotable": True,
        "active_vm_preserved": True,
        "active_dsr_preserved": True,
        "static_all_weather_benchmark_control_only": True,
        "commodity_continued": False,
        "macro_gld_continued": False,
        "volatility_throttle_continued": False,
        "managed_futures_reopened": False,
        "high_return_tactical_continued": False,
        "data_blocked_row_count": len(data_blocked),
        "rows_passed_numeric_criteria": sum(1 for row in rows if row.get("numeric_criteria_pass") is True),
        "rows_failed_numeric_criteria": sum(1 for row in rows if row.get("numeric_criteria_pass") is not True),
        "risk_control_rows_passed": sum(
            1 for row in rows if row.get("variant_role") in RISK_CONTROL_ROLES and row.get("numeric_criteria_pass") is True
        ),
        "risk_control_rows_failed": sum(
            1 for row in rows if row.get("variant_role") in RISK_CONTROL_ROLES and row.get("numeric_criteria_pass") is not True
        ),
        "invariant_failure_count": len(invariant_failures),
        "max_daily_exposure": max_exposure,
        "max_daily_weight_sum": max_weight,
        "exposure_invariant_passed": hard_invariants_pass and not data_blocked,
        "results_interpretable": hard_invariants_pass and len(rows) == EXPECTED_ROW_COUNT and not data_blocked,
        "usable_diagnostic_evidence": hard_invariants_pass and len(rows) == EXPECTED_ROW_COUNT and not data_blocked,
        **{f"{label}_count": count for label, count in counts.items()},
        "next_action": next_action,
    }


def summary_md(
    manifest: dict[str, Any],
    concept_summary: list[dict[str, Any]],
    role_summary: list[dict[str, Any]],
    alignments: list[dict[str, Any]],
) -> str:
    label_lines = [f"- `{label}`: `{manifest[f'{label}_count']}`" for label in sorted(ALLOWED_LABELS)]
    concept_lines = [
        f"- `{row['concept']}`: pass `{row['numeric_pass_count']}`, fail `{row['numeric_fail_count']}`"
        for row in concept_summary
    ]
    role_lines = [
        f"- `{row['variant_role']}`: pass `{row['numeric_pass_count']}`, fail `{row['numeric_fail_count']}`"
        for row in role_summary
    ]
    limits = [
        f"- `{row['variant_id']}`: `{row['effective_start_date']}` to `{row['effective_end_date']}`; `{row['alignment_status']}`"
        for row in alignments
    ]
    return f"""# Regional / International Momentum Bounded Run

Lane ID: `{manifest['lane_id']}`

Rows planned: `{manifest['variant_count_planned']}`

Rows evaluated: `{manifest['variant_count_evaluated']}`

Data-blocked rows: `{manifest['data_blocked_row_count']}`

Risk-control rows passed: `{manifest['risk_control_rows_passed']}`

Risk-control rows failed: `{manifest['risk_control_rows_failed']}`

Invariant failures: `{manifest['invariant_failure_count']}`

Results interpretable: `{manifest['results_interpretable']}`

Usable diagnostic evidence produced: `{manifest['usable_diagnostic_evidence']}`

Pass/fail by concept:

{chr(10).join(concept_lines)}

Pass/fail by role:

{chr(10).join(role_lines)}

Research-only label counts:

{chr(10).join(label_lines)}

Date-alignment limitations:

{chr(10).join(limits)}

Source context rows remain context only. Control rows remain benchmark/control only.

No output is promotable, candidate_exhaustive-ready, or paper-forward eligible.

Exact next action: `{manifest['next_action']}`
"""


def alignment_md(alignments: list[dict[str, Any]]) -> str:
    lines = ["# Data Alignment / Effective Date Window Report", ""]
    for row in alignments:
        lines.append(
            f"- `{row['variant_id']}`: `{row['effective_start_date']}` to `{row['effective_end_date']}`; "
            f"required `{row['required_symbols']}`; status `{row['alignment_status']}`"
        )
    lines.append("")
    lines.append("Rows use per-asset availability inside the regional ranking and require a common BIL/SPY comparator frame.")
    lines.append("No symbol history is forward-filled before inception.")
    return "\n".join(lines) + "\n"


def coverage_md(coverage: list[dict[str, Any]]) -> str:
    lines = ["# Symbol Coverage Report", ""]
    for row in coverage:
        lines.append(
            f"- `{row['symbol']}`: `{row['status']}`, rows `{row['rows']}`, "
            f"`{row['first_date']}` to `{row['last_date']}`"
        )
    return "\n".join(lines) + "\n"


def baseline_md(rows: list[dict[str, Any]]) -> str:
    lines = ["# Baseline / Comparator Report", ""]
    for row in rows:
        lines.append(
            f"- `{row['variant_id']}` vs `{row['baseline_variant_id']}`: baseline delta "
            f"`{parse_float(row.get('baseline_total_return_delta')):.6f}`, BIL delta "
            f"`{parse_float(row.get('same_window_return_vs_bil')):.6f}`, SPY delta "
            f"`{parse_float(row.get('same_window_return_vs_spy')):.6f}`, SPY_200d delta "
            f"`{parse_float(row.get('same_window_return_vs_spy200d_frozen_control')):.6f}`, "
            f"EFA/EEM delta `{parse_float(row.get('same_window_return_vs_efa_eem_equal_weight')):.6f}`"
        )
    lines.append("")
    lines.append("Static all-weather remains benchmark/control only and is not converted into candidate status.")
    return "\n".join(lines) + "\n"


def source_repro_md(rows: list[dict[str, Any]]) -> str:
    lines = ["# Source Context Reproduction Report", ""]
    for row in rows:
        lines.append(
            f"- `{row['source_registry_id']}` / `{row['source_context_variant_id']}`: source decision "
            f"`{row['source_decision']}`, source 180d drawdown `{row['source_180d_worst_drawdown']}`, "
            f"current-cache recomputed 180d drawdown "
            f"`{parse_float(row.get('recomputed_worst_180_day_drawdown_project_dollars')):.6f}`, "
            f"status `{row['source_context_reproduction_status']}`"
        )
    lines.append("")
    lines.append("Source rows are context only and cannot create promotion or paper-forward eligibility.")
    return "\n".join(lines) + "\n"


def invariant_md(manifest: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    failures = [row["variant_id"] for row in rows if row.get("exposure_invariant_pass") is not True]
    impossible_days = sum(int(parse_float(row.get("impossible_cash_and_risky_exposure_days"), 0.0)) for row in rows)
    negative = sum(int(parse_float(row.get("negative_weight_violation_count"), 0.0)) for row in rows)
    nan_count = sum(int(parse_float(row.get("nan_weight_count"), 0.0)) for row in rows)
    return f"""# Exposure Invariant Report

- Max daily exposure: `{manifest['max_daily_exposure']}`
- Max daily weight sum: `{manifest['max_daily_weight_sum']}`
- Exposure invariant passed: `{manifest['exposure_invariant_passed']}`
- Invariant failure count: `{manifest['invariant_failure_count']}`
- Impossible BIL/cash plus risky exposure days: `{impossible_days}`
- Negative weight violations: `{negative}`
- NaN weight count: `{nan_count}`
- BIL/cash rule: replacement/remainder only; no BIL/cash accumulation above total exposure.
- Zero target rule: zero target weights remain zero and are not stale-forward-filled into old allocations.

Failures:

{chr(10).join(f'- `{variant}`' for variant in failures) if failures else '- None'}
"""


def label_summary_md(manifest: dict[str, Any]) -> str:
    return "# Regional / International Momentum Bounded Role and Label Summary\n\n" + "\n".join(
        f"- `{label}`: `{manifest[f'{label}_count']}`" for label in sorted(ALLOWED_LABELS)
    ) + "\n"


def do_not_promote_md() -> str:
    return """# Do Not Promote From Regional / International Momentum Bounded Run

This run is diagnostic historical research evidence only.

It creates no promotion-review candidate, candidate_exhaustive candidate, paper-forward candidate, paper-forward activation, broker/live action, or real-money recommendation.
"""


def next_action_md(next_action: str) -> str:
    return f"""# Regional / International Momentum Bounded Run Next Action

Exact next action:

`{next_action}`

Do not execute the next action in this task.
"""


def consistency_check(manifest: dict[str, Any], rows: list[dict[str, Any]], output: Path) -> dict[str, Any]:
    required = {name: (output / name).exists() for name in REQUIRED_FILES}
    required["regional_international_momentum_bounded_run_consistency_check.json"] = True
    labels = {row.get("research_only_label", "") for row in rows}
    checks = {
        "correct_lane_id": manifest["lane_id"] == LANE_ID,
        "correct_family_id": manifest["family_id"] == FAMILY_ID,
        "source_design_run_ready": manifest["source_design_run_ready"] is True,
        "source_design_next_action_correct": manifest["source_design_next_action_correct"] is True,
        "variant_count_exact_7": manifest["variant_count_evaluated"] == EXPECTED_ROW_COUNT,
        "source_context_rows_exact_2": manifest["source_context_row_count"] == 2,
        "risk_control_rows_exact_2": manifest["risk_control_row_count"] == 2,
        "control_rows_exact_3": manifest["control_row_count"] == 3,
        "no_design_expansion": manifest["new_rows_added"] is False
        and manifest["new_assets_added"] is False
        and manifest["new_lookbacks_added"] is False
        and manifest["new_concepts_added"] is False
        and manifest["hidden_parameter_grid_created"] is False,
        "no_discovery_or_broad_batch": manifest["strategy_discovery_run"] is False
        and manifest["new_research_batch_run"] is False,
        "no_new_family_or_variants": manifest["new_families_created"] is False
        and manifest["new_variants_created"] is False,
        "local_cache_only": manifest["uses_local_cache_only"] is True,
        "no_provider_refresh_or_download": manifest["provider_refresh_run"] is False
        and manifest["provider_download"] is False,
        "no_intraday": manifest["intraday_data_used"] is False,
        "no_broker_live_real_money": manifest["broker_api_called"] is False
        and manifest["broker_orders_submitted"] is False
        and manifest["broker_orders_cancelled"] is False
        and manifest["broker_orders_reconciled"] is False
        and manifest["live_orders"] is False
        and manifest["real_money_recommendation"] is False,
        "no_candidate_promotion_paper": manifest["promotion_candidates_created"] is False
        and manifest["candidate_exhaustive_run"] is False
        and manifest["paper_forward_activation"] is False
        and manifest["new_paper_forward_candidate_created"] is False
        and manifest["best_single_variant_promoted"] is False,
        "outputs_non_promotable": manifest["research_outputs_remain_non_promotable"] is True,
        "active_state_preserved": manifest["active_vm_preserved"] is True and manifest["active_dsr_preserved"] is True,
        "static_all_weather_control_only": manifest["static_all_weather_benchmark_control_only"] is True,
        "other_tracks_not_continued": manifest["commodity_continued"] is False
        and manifest["macro_gld_continued"] is False
        and manifest["volatility_throttle_continued"] is False
        and manifest["managed_futures_reopened"] is False
        and manifest["high_return_tactical_continued"] is False,
        "allowed_labels_only": labels.issubset(ALLOWED_LABELS),
        "all_rows_non_promotable": all(row.get("promotion_eligibility") is False for row in rows),
        "all_rows_not_paper": all(row.get("paper_forward_eligibility") is False for row in rows),
        "all_rows_not_candidate_exhaustive": all(row.get("candidate_exhaustive_eligibility") is False for row in rows),
        "controls_control_only": all(
            row.get("research_only_label") == "regional_signal_control_only"
            for row in rows
            if row.get("variant_role") in CONTROL_ROLES
        ),
        "source_context_too_risky_only": all(
            row.get("research_only_label") == "regional_signal_source_context_too_risky"
            for row in rows
            if row.get("variant_role") in SOURCE_CONTEXT_ROLES
        ),
        "risk_control_only_rows_can_pass": all(
            row.get("variant_role") in RISK_CONTROL_ROLES
            for row in rows
            if row.get("research_only_label") == "regional_signal_risk_control_pass"
        ),
        "max_daily_exposure_lte_1": manifest["max_daily_exposure"] <= 1.000001,
        "max_daily_weight_sum_lte_1": manifest["max_daily_weight_sum"] <= 1.000001,
        "exposure_invariant_passed": manifest["exposure_invariant_passed"] is True,
        "row_results_exist": (output / "regional_international_momentum_bounded_row_results.csv").exists(),
        "criteria_results_exist": (output / "regional_international_momentum_bounded_numeric_criteria_results.csv").exists(),
        "source_reproduction_report_exists": (output / "source_context_reproduction_report.md").exists(),
        "alignment_report_exists": (output / "data_alignment_effective_window_report.md").exists(),
        "symbol_coverage_report_exists": (output / "symbol_coverage_report.md").exists(),
        "baseline_report_exists": (output / "baseline_comparator_report.md").exists(),
        "do_not_promote_exists": (output / "do_not_promote_from_regional_international_momentum_bounded_run.md").exists(),
        "next_action_valid": manifest["next_action"] in VALID_NEXT_ACTIONS,
        "required_files_present": all(required.values()),
        "required_files": required,
    }
    checks["consistency_passed"] = all(value is True for key, value in checks.items() if key != "required_files")
    return checks


def write_outputs(
    root: Path,
    created: str,
    rows: list[dict[str, Any]],
    alignments: list[dict[str, Any]],
    criteria: list[dict[str, Any]],
    baseline_rows: list[dict[str, Any]],
    source_repro: list[dict[str, Any]],
    preflight: dict[str, Any],
) -> dict[str, Any]:
    output = root / OUTPUT_DIR
    output.mkdir(parents=True, exist_ok=True)
    manifest = manifest_payload(created, output, rows, preflight)
    concept_summary = pass_fail_summary(rows, "concept")
    role_summary = pass_fail_summary(rows, "variant_role")
    coverage = symbol_coverage_rows(root, rows)

    write_json(output / "regional_international_momentum_bounded_run_manifest.json", manifest)
    write_csv(output / "regional_international_momentum_bounded_row_results.csv", rows, list(RESULT_FIELDS))
    write_csv(output / "regional_international_momentum_bounded_numeric_criteria_results.csv", criteria, list(CRITERIA_FIELDS))
    write_csv(output / "source_context_reproduction_report.csv", source_repro, list(SOURCE_REPRO_FIELDS))
    write_text(output / "source_context_reproduction_report.md", source_repro_md(source_repro))
    write_csv(output / "data_alignment_effective_window_report.csv", alignments, list(ALIGNMENT_FIELDS))
    write_text(output / "data_alignment_effective_window_report.md", alignment_md(alignments))
    write_csv(output / "symbol_coverage_report.csv", coverage, list(coverage[0].keys()) if coverage else [])
    write_text(output / "symbol_coverage_report.md", coverage_md(coverage))
    write_csv(output / "baseline_comparator_report.csv", baseline_rows, list(BASELINE_FIELDS))
    write_text(output / "baseline_comparator_report.md", baseline_md(rows))
    write_csv(
        output / "regional_international_momentum_bounded_concept_summary.csv",
        concept_summary,
        list(concept_summary[0].keys()) if concept_summary else [],
    )
    write_csv(
        output / "regional_international_momentum_bounded_role_summary.csv",
        role_summary,
        list(role_summary[0].keys()) if role_summary else [],
    )
    write_text(output / "exposure_invariant_report.md", invariant_md(manifest, rows))
    write_text(output / "role_label_summary.md", label_summary_md(manifest))
    write_text(
        output / "regional_international_momentum_bounded_run_summary.md",
        summary_md(manifest, concept_summary, role_summary, alignments),
    )
    write_text(output / "do_not_promote_from_regional_international_momentum_bounded_run.md", do_not_promote_md())
    write_text(output / "regional_international_momentum_bounded_run_next_action.md", next_action_md(manifest["next_action"]))
    check = consistency_check(manifest, rows, output)
    write_json(output / "regional_international_momentum_bounded_run_consistency_check.json", check)
    return {**manifest, "output_dir": str(output.resolve()), "consistency_passed": check["consistency_passed"]}


def run(root: Path = ROOT) -> dict[str, Any]:
    created = now_utc()
    rows, alignments, criteria, baseline_rows, source_repro, preflight = evaluate_lane(root)
    return write_outputs(root, created, rows, alignments, criteria, baseline_rows, source_repro, preflight)
