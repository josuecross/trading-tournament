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
from strategy_lab.research_os.research.commodity_basket_etf_momentum_bounded_design import (
    FAMILY_ID,
    LANE_ID,
)
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
    rolling_window_stats,
    trade_count_and_turnover,
    weight_invariant_report,
    write_csv,
)


SOURCE_DESIGN_DIR = (
    Path("evidence") / "research_recovery" / "commodity_basket_etf_momentum_bounded_design" / "latest"
)
READINESS_DIR = (
    Path("evidence") / "research_recovery" / "commodity_basket_readiness_reconciliation" / "latest"
)
CACHE_REVALIDATION_DIR = (
    Path("evidence") / "research_recovery" / "commodity_basket_local_cache_revalidation" / "latest"
)
OUTPUT_DIR = (
    Path("evidence") / "research_recovery" / "commodity_basket_etf_momentum_bounded_run" / "latest"
)

EXPECTED_ROW_COUNT = 6
WEIGHT_TOLERANCE = 1e-6
COMMODITY_SYMBOLS = ("DBC", "PDBC", "COMT", "GSG", "USCI")
CORE_COMPARATOR_SYMBOLS = ("BIL", "SPY", "GLD")

NEXT_ACTION_AUDIT = "audit_commodity_basket_etf_momentum_bounded_lane_results"
NEXT_ACTION_FIX = "fix_commodity_basket_etf_momentum_bounded_lane_methodology_issue"
NEXT_ACTION_CACHE = "restore_or_revalidate_local_commodity_cache_before_bounded_run"
VALID_NEXT_ACTIONS = {NEXT_ACTION_AUDIT, NEXT_ACTION_FIX, NEXT_ACTION_CACHE}

ALLOWED_LABELS = {
    "commodity_signal_diagnostic_pass",
    "commodity_signal_control_context",
    "commodity_signal_risk_budget_breach",
    "commodity_signal_too_cash_heavy",
    "commodity_signal_duplicate_combo",
    "commodity_signal_contribution_too_small",
    "commodity_signal_data_blocked",
    "commodity_signal_weak",
}

RESULT_FIELDS = (
    "lane_id",
    "family_id",
    "variant_id",
    "role",
    "concept",
    "universe",
    "lookback",
    "top_n",
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
    "same_window_return_vs_bil",
    "same_window_return_vs_spy",
    "same_window_return_vs_spy200d_frozen_control",
    "static_all_weather_benchmark_control_comparison",
    "average_bil_cash_share",
    "max_bil_cash_share",
    "turnover",
    "trade_count",
    "average_exposure",
    "max_daily_exposure",
    "max_daily_weight_sum",
    "average_weight_sum",
    "weight_sum_violation_count",
    "negative_weight_violation_count",
    "nan_weight_count",
    "impossible_cash_and_risky_exposure_days",
    "correlation_to_spy200d",
    "correlation_to_static_all_weather",
    "correlation_to_active_combo",
    "duplicate_reference_correlation",
    "active_vm_dsr_combo_max_drawdown_improvement",
    "active_vm_dsr_combo_total_return_drag",
    "baseline_variant_id",
    "baseline_total_return",
    "baseline_cagr",
    "baseline_max_drawdown",
    "baseline_calmar_or_return_drawdown_proxy",
    "baseline_total_return_delta",
    "worst_180_day_window",
    "best_180_day_window",
    "positive_180_day_window_ratio",
    "stop_hit_rate_180d_proxy",
    "p_target_400_before_stop_180d_proxy",
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
    "role",
    "concept",
    "exposure_invariant_pass",
    "max_daily_exposure",
    "max_daily_exposure_pass",
    "max_daily_weight_sum",
    "max_daily_weight_sum_pass",
    "stop_hit_rate_180d_proxy",
    "stop_hit_rate_180d_pass",
    "worst_180_day_window",
    "worst_180_day_window_pass",
    "p_target_400_before_stop_180d_proxy",
    "p_target_400_before_stop_180d_pass",
    "average_bil_cash_share",
    "standalone_bil_share_pass",
    "same_window_return_vs_bil",
    "bil_return_delta_pass",
    "duplicate_reference_correlation",
    "duplicate_reference_pass",
    "active_vm_dsr_combo_max_drawdown_improvement",
    "portfolio_drawdown_improvement_pass",
    "active_vm_dsr_combo_total_return_drag",
    "portfolio_return_drag_pass",
    "correlation_to_active_combo",
    "active_combo_correlation_pass",
    "standalone_criteria_pass",
    "portfolio_contribution_criteria_pass",
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
    "bil_spy_gld_limited_end_date",
    "common_date_count",
    "alignment_status",
)

BASELINE_FIELDS = (
    "variant_id",
    "baseline_variant_id",
    "baseline_total_return",
    "baseline_cagr",
    "baseline_max_drawdown",
    "baseline_calmar_or_return_drawdown_proxy",
    "strategy_total_return",
    "strategy_cagr",
    "strategy_max_drawdown",
    "baseline_total_return_delta",
    "same_window_return_vs_bil",
    "same_window_return_vs_spy",
    "same_window_return_vs_spy200d_frozen_control",
    "static_all_weather_benchmark_control_comparison",
)

REQUIRED_FILES = (
    "commodity_basket_bounded_run_manifest.json",
    "commodity_basket_bounded_run_consistency_check.json",
    "commodity_basket_bounded_row_results.csv",
    "commodity_basket_bounded_numeric_criteria_results.csv",
    "data_alignment_effective_window_report.csv",
    "data_alignment_effective_window_report.md",
    "symbol_coverage_report.csv",
    "symbol_coverage_report.md",
    "baseline_comparator_report.csv",
    "baseline_comparator_report.md",
    "exposure_invariant_report.md",
    "commodity_basket_bounded_label_summary.md",
    "commodity_basket_bounded_run_summary.md",
    "do_not_promote_from_commodity_basket_bounded_run.md",
    "commodity_basket_bounded_run_next_action.md",
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
        if value in ("", None):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def finite(value: Any) -> bool:
    return math.isfinite(parse_float(value))


def safe_corr(left: pd.Series, right: pd.Series) -> float:
    aligned = pd.concat([left.rename("left"), right.rename("right")], axis=1, sort=False).dropna()
    if len(aligned) < 252:
        return float("nan")
    return float(aligned["left"].corr(aligned["right"]))


def available_symbols(root: Path) -> set[str]:
    return {str(row["symbol"]) for row in cache_inventory(root) if row.get("status") == "cache_ready"}


def row_universe(row: dict[str, str]) -> list[str]:
    return [symbol for symbol in row["universe"].split("|") if symbol]


def required_symbols(row: dict[str, str]) -> list[str]:
    symbols = set(row_universe(row))
    symbols.update(CORE_COMPARATOR_SYMBOLS)
    return sorted(symbols)


def price_ranges(root: Path, symbols: list[str]) -> dict[str, dict[str, Any]]:
    inventory = {row["symbol"]: row for row in cache_inventory(root)}
    return {
        symbol: {
            "first_date": inventory.get(symbol, {}).get("first_date", ""),
            "last_date": inventory.get(symbol, {}).get("last_date", ""),
            "rows": inventory.get(symbol, {}).get("rows", 0),
            "status": inventory.get(symbol, {}).get("status", "missing"),
            "path": inventory.get(symbol, {}).get("path", ""),
        }
        for symbol in symbols
    }


def aligned_price_frame(root: Path, row: dict[str, str]) -> tuple[pd.DataFrame, dict[str, Any]]:
    symbols = required_symbols(row)
    available = available_symbols(root)
    missing = [symbol for symbol in symbols if symbol not in available]
    ranges = price_ranges(root, symbols)
    if missing:
        return pd.DataFrame(), {
            "variant_id": row["variant_id"],
            "required_symbols": "|".join(symbols),
            "missing_symbols": "|".join(missing),
            "effective_start_date": "",
            "effective_end_date": "",
            "limiting_start_symbols": "",
            "limiting_end_symbols": "",
            "bil_spy_gld_limited_end_date": False,
            "common_date_count": 0,
            "alignment_status": "data_blocked_missing_symbols",
            "ranges": ranges,
        }
    prices = load_prices(root, tuple(symbols))
    if prices.empty:
        return pd.DataFrame(), {
            "variant_id": row["variant_id"],
            "required_symbols": "|".join(symbols),
            "missing_symbols": "",
            "effective_start_date": "",
            "effective_end_date": "",
            "limiting_start_symbols": "",
            "limiting_end_symbols": "",
            "bil_spy_gld_limited_end_date": False,
            "common_date_count": 0,
            "alignment_status": "data_blocked_empty_price_frame",
            "ranges": ranges,
        }
    common = prices.dropna(subset=symbols).index
    if len(common) == 0:
        return pd.DataFrame(), {
            "variant_id": row["variant_id"],
            "required_symbols": "|".join(symbols),
            "missing_symbols": "",
            "effective_start_date": "",
            "effective_end_date": "",
            "limiting_start_symbols": "",
            "limiting_end_symbols": "",
            "bil_spy_gld_limited_end_date": False,
            "common_date_count": 0,
            "alignment_status": "data_blocked_no_common_dates",
            "ranges": ranges,
        }
    first_dates = {symbol: ranges[symbol]["first_date"] for symbol in symbols}
    last_dates = {symbol: ranges[symbol]["last_date"] for symbol in symbols}
    max_first = max(first_dates.values())
    min_last = min(last_dates.values())
    limiting_start = [symbol for symbol, value in first_dates.items() if value == max_first]
    limiting_end = [symbol for symbol, value in last_dates.items() if value == min_last]
    aligned = prices.loc[common, symbols].copy()
    return aligned, {
        "variant_id": row["variant_id"],
        "required_symbols": "|".join(symbols),
        "missing_symbols": "",
        "effective_start_date": aligned.index.min().date().isoformat(),
        "effective_end_date": aligned.index.max().date().isoformat(),
        "limiting_start_symbols": "|".join(limiting_start),
        "limiting_end_symbols": "|".join(limiting_end),
        "bil_spy_gld_limited_end_date": any(symbol in CORE_COMPARATOR_SYMBOLS for symbol in limiting_end),
        "common_date_count": int(len(aligned)),
        "alignment_status": "common_date_aligned",
        "ranges": ranges,
    }


def target_template(columns: list[str]) -> dict[str, float]:
    return {symbol: 0.0 for symbol in columns}


def normalize_target(target: dict[str, float], columns: list[str]) -> dict[str, float]:
    clean = {symbol: max(0.0, float(target.get(symbol, 0.0))) for symbol in columns}
    total = sum(clean.values())
    if total > 1.0 + WEIGHT_TOLERANCE:
        for symbol in clean:
            clean[symbol] /= total
    if "BIL" in clean:
        risky = sum(value for symbol, value in clean.items() if symbol != "BIL")
        clean["BIL"] = max(0.0, min(1.0, 1.0 - risky)) if total <= 1.0 + WEIGHT_TOLERANCE else clean["BIL"]
    return clean


def commodity_tsmom_weights(
    prices: pd.DataFrame,
    *,
    lookback: int,
    top_n: int,
    trend_filter: bool,
) -> pd.DataFrame:
    columns = list(prices.columns)
    commodity_columns = [symbol for symbol in COMMODITY_SYMBOLS if symbol in prices.columns]
    scores = prices[commodity_columns].pct_change(lookback, fill_method=None).shift(1)
    prior_prices = prices[commodity_columns].shift(1)
    sma_200 = prior_prices.rolling(200, min_periods=100).mean()
    trend = prior_prices > sma_200
    rebalance_targets: dict[pd.Timestamp, dict[str, float]] = {}

    for date in prices.index[month_rebalance_mask(prices.index)]:
        target = target_template(columns)
        score_row = scores.loc[date].dropna().sort_values(ascending=False)
        selected = list(score_row.head(top_n).index)
        slot = 1.0 / max(top_n, 1)
        for symbol in selected:
            score_ok = float(score_row.get(symbol, float("nan"))) > 0.0
            trend_ok = bool(trend.loc[date].get(symbol, False)) if trend_filter else True
            if score_ok and trend_ok:
                target[symbol] += slot
            else:
                target["BIL"] += slot
        target["BIL"] += slot * max(0, top_n - len(selected))
        rebalance_targets[pd.Timestamp(date)] = normalize_target(target, columns)
    return complete_rebalance_weight_frame(prices.index, columns, rebalance_targets)


def half_bil_weights(prices: pd.DataFrame, *, lookback: int, top_n: int) -> pd.DataFrame:
    base = commodity_tsmom_weights(prices, lookback=lookback, top_n=top_n, trend_filter=False)
    weights = pd.DataFrame(0.0, index=base.index, columns=base.columns)
    risky_cols = [column for column in base.columns if column != "BIL"]
    weights[risky_cols] = base[risky_cols] * 0.5
    if "BIL" in weights.columns:
        weights["BIL"] = 1.0 - weights[risky_cols].sum(axis=1)
    return weights


def spy200d_component_weights(prices: pd.DataFrame) -> pd.DataFrame:
    columns = list(prices.columns)
    weights = pd.DataFrame(0.0, index=prices.index, columns=columns)
    if not {"SPY", "BIL"}.issubset(prices.columns):
        return weights
    prior_spy = prices["SPY"].shift(1)
    prior_sma = prices["SPY"].shift(1).rolling(200, min_periods=100).mean()
    risk_on = (prior_spy > prior_sma).fillna(False)
    weights.loc[risk_on, "SPY"] = 1.0
    weights.loc[~risk_on, "BIL"] = 1.0
    return weights


def combo_spy200d_gld_weights(prices: pd.DataFrame) -> pd.DataFrame:
    columns = list(prices.columns)
    weights = pd.DataFrame(0.0, index=prices.index, columns=columns)
    spy200d = spy200d_component_weights(prices)
    weights = weights.add(spy200d * 0.5, fill_value=0.0)
    if "GLD" in weights.columns:
        weights["GLD"] = weights["GLD"] + 0.5
    if "BIL" in weights.columns:
        risky = weights.drop(columns=["BIL"]).sum(axis=1)
        weights["BIL"] = np.maximum(weights["BIL"], 1.0 - risky)
    return weights.reindex(columns=columns).fillna(0.0)


def static_all_weather_returns(root: Path, index: pd.DatetimeIndex) -> pd.Series:
    symbols = ("SPY", "IEF", "GLD", "BIL")
    if not set(symbols).issubset(available_symbols(root)):
        return pd.Series(dtype=float, name="static_all_weather")
    prices = load_prices(root, symbols).dropna(subset=list(symbols))
    if prices.empty:
        return pd.Series(dtype=float, name="static_all_weather")
    weights = pd.DataFrame(0.0, index=prices.index, columns=list(symbols))
    weights["SPY"] = 0.30
    weights["IEF"] = 0.40
    weights["GLD"] = 0.20
    weights["BIL"] = 0.10
    daily = portfolio_returns(prices, weights).rename("static_all_weather")
    return daily.reindex(index).dropna()


def portfolio_returns(prices: pd.DataFrame, weights: pd.DataFrame) -> pd.Series:
    returns = prices.pct_change(fill_method=None).fillna(0.0)
    weights = weights.reindex(prices.index).ffill().fillna(0.0).reindex(columns=prices.columns, fill_value=0.0)
    return (weights.shift(1).fillna(0.0) * returns).sum(axis=1)


def strategy_weights(row: dict[str, str], prices: pd.DataFrame) -> pd.DataFrame:
    lookback = int(float(row["lookback_days"]))
    top_n = int(float(row["top_n"]))
    concept = row["concept"]
    if concept == "commodity_tsmom_top2_126":
        return commodity_tsmom_weights(prices, lookback=lookback, top_n=top_n, trend_filter=False)
    if concept == "commodity_tsmom_top2_126_200d_filter":
        return commodity_tsmom_weights(prices, lookback=lookback, top_n=top_n, trend_filter=True)
    if concept == "commodity_tsmom_top2_126_half_bil":
        return half_bil_weights(prices, lookback=lookback, top_n=top_n)
    if concept == "active_combo_plus_commodity_80_20":
        commodity = commodity_tsmom_weights(prices, lookback=lookback, top_n=top_n, trend_filter=False)
        combo = combo_spy200d_gld_weights(prices)
        weights = 0.8 * combo + 0.2 * commodity
        return weights.reindex(columns=prices.columns).fillna(0.0)
    if concept == "gld_buy_hold_control":
        weights = pd.DataFrame(0.0, index=prices.index, columns=prices.columns)
        weights["GLD"] = 1.0
        return weights
    if concept == "bil_cash_control":
        weights = pd.DataFrame(0.0, index=prices.index, columns=prices.columns)
        weights["BIL"] = 1.0
        return weights
    weights = pd.DataFrame(0.0, index=prices.index, columns=prices.columns)
    weights["BIL"] = 1.0
    return weights


def baseline_weights(row: dict[str, str], prices: pd.DataFrame) -> pd.DataFrame:
    baseline = row["baseline_variant_id"]
    lookback = int(float(row["lookback_days"])) if row["lookback_days"] else 126
    top_n = int(float(row["top_n"])) if row["top_n"] else 2
    if baseline == "commodity_basket_tsmom_top2_v1":
        return commodity_tsmom_weights(prices, lookback=lookback, top_n=top_n, trend_filter=False)
    if baseline == "combo_SPY200d_GLD_50_50_v1":
        return combo_spy200d_gld_weights(prices)
    if baseline == "GLD_buy_hold":
        control = dict(row)
        control["concept"] = "gld_buy_hold_control"
        return strategy_weights(control, prices)
    if baseline == "BIL_cash_proxy":
        control = dict(row)
        control["concept"] = "bil_cash_control"
        return strategy_weights(control, prices)
    return strategy_weights(row, prices)


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
    exposure_cols = [col for col in weights.columns if col != "BIL"]
    risky = weights[exposure_cols].sum(axis=1) if exposure_cols else pd.Series(0.0, index=weights.index)
    cash = weights["BIL"] if "BIL" in weights.columns else (1.0 - risky).clip(lower=0.0)
    invariant = weight_invariant_report(weights, tolerance=WEIGHT_TOLERANCE)
    rolling = rolling_window_stats(eq)
    rolling_returns = (eq / eq.shift(180) - 1.0).dropna()
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
        "worst_180_day_window": rolling["worst_180d_window"],
        "best_180_day_window": rolling["best_180d_window"],
        "positive_180_day_window_ratio": rolling["positive_180d_window_ratio"],
        "stop_hit_rate_180d_proxy": float((rolling_returns <= -0.20).mean()) if not rolling_returns.empty else float("nan"),
        "p_target_400_before_stop_180d_proxy": float((rolling_returns >= (400.0 / 3000.0)).mean())
        if not rolling_returns.empty
        else float("nan"),
    }


def baseline_metrics(daily: pd.Series) -> dict[str, Any]:
    metrics = metrics_for_returns(daily, pd.DataFrame(index=daily.index))
    return {
        "baseline_total_return": metrics.get("total_return", float("nan")),
        "baseline_cagr": metrics.get("cagr", float("nan")),
        "baseline_max_drawdown": metrics.get("max_drawdown", float("nan")),
        "baseline_calmar_or_return_drawdown_proxy": metrics.get("calmar_or_return_drawdown_proxy", float("nan")),
    }


def criteria_flags(row: dict[str, Any]) -> dict[str, Any]:
    max_exposure = parse_float(row.get("max_daily_exposure"))
    max_weight = parse_float(row.get("max_daily_weight_sum"))
    stop_rate = parse_float(row.get("stop_hit_rate_180d_proxy"))
    worst_180 = parse_float(row.get("worst_180_day_window"))
    p400 = parse_float(row.get("p_target_400_before_stop_180d_proxy"))
    avg_bil = parse_float(row.get("average_bil_cash_share"))
    bil_delta = parse_float(row.get("same_window_return_vs_bil"))
    duplicate_corr = parse_float(row.get("duplicate_reference_correlation"))
    active_dd_delta = parse_float(row.get("active_vm_dsr_combo_max_drawdown_improvement"))
    active_return_drag = parse_float(row.get("active_vm_dsr_combo_total_return_drag"))
    active_corr = parse_float(row.get("correlation_to_active_combo"))
    exposure_pass = (
        row.get("exposure_invariant_pass") is True
        and max_exposure <= 1.000001
        and max_weight <= 1.000001
    )
    standalone_pass = (
        exposure_pass
        and finite(stop_rate)
        and stop_rate <= 0.0250
        and finite(worst_180)
        and worst_180 >= -0.2000
        and finite(p400)
        and p400 >= 0.2500
        and avg_bil <= 0.6000
        and bil_delta > 0.0
    )
    portfolio_pass = (
        exposure_pass
        and (not finite(duplicate_corr) or duplicate_corr < 0.9000)
        and finite(active_dd_delta)
        and active_dd_delta >= 0.0300
        and finite(active_return_drag)
        and active_return_drag >= -0.0200
        and (not finite(active_corr) or active_corr < 0.9000)
    )
    return {
        "max_daily_exposure_pass": max_exposure <= 1.000001,
        "max_daily_weight_sum_pass": max_weight <= 1.000001,
        "stop_hit_rate_180d_pass": finite(stop_rate) and stop_rate <= 0.0250,
        "worst_180_day_window_pass": finite(worst_180) and worst_180 >= -0.2000,
        "p_target_400_before_stop_180d_pass": finite(p400) and p400 >= 0.2500,
        "standalone_bil_share_pass": avg_bil <= 0.6000,
        "bil_return_delta_pass": bil_delta > 0.0,
        "duplicate_reference_pass": not finite(duplicate_corr) or duplicate_corr < 0.9000,
        "portfolio_drawdown_improvement_pass": finite(active_dd_delta) and active_dd_delta >= 0.0300,
        "portfolio_return_drag_pass": finite(active_return_drag) and active_return_drag >= -0.0200,
        "active_combo_correlation_pass": not finite(active_corr) or active_corr < 0.9000,
        "standalone_criteria_pass": standalone_pass,
        "portfolio_contribution_criteria_pass": portfolio_pass,
        "numeric_criteria_pass": standalone_pass or portfolio_pass,
    }


def label_row(row: dict[str, Any], flags: dict[str, Any]) -> str:
    if row.get("data_availability_status") != "cache_ready":
        return "commodity_signal_data_blocked"
    if row.get("role") in {"comparator_control", "cash_control"}:
        return "commodity_signal_control_context"
    if row.get("exposure_invariant_pass") is not True:
        return "commodity_signal_risk_budget_breach"
    if flags["duplicate_reference_pass"] is False:
        return "commodity_signal_duplicate_combo"
    if flags["standalone_bil_share_pass"] is False:
        return "commodity_signal_too_cash_heavy"
    if flags["stop_hit_rate_180d_pass"] is False or flags["worst_180_day_window_pass"] is False:
        return "commodity_signal_risk_budget_breach"
    if flags["numeric_criteria_pass"] is True:
        return "commodity_signal_diagnostic_pass"
    if (
        flags["portfolio_drawdown_improvement_pass"] is False
        or flags["portfolio_return_drag_pass"] is False
        or flags["active_combo_correlation_pass"] is False
    ):
        return "commodity_signal_contribution_too_small"
    return "commodity_signal_weak"


def data_blocked_row(row: dict[str, str], alignment: dict[str, Any], reason: str) -> dict[str, Any]:
    return {
        "lane_id": LANE_ID,
        "family_id": FAMILY_ID,
        "variant_id": row.get("variant_id", ""),
        "role": row.get("variant_role", ""),
        "concept": row.get("concept", ""),
        "universe": row.get("universe", ""),
        "lookback": row.get("lookback_days", ""),
        "top_n": row.get("top_n", ""),
        "effective_start_date": "",
        "effective_end_date": "",
        "symbols_used": "",
        "comparator_references": row.get("comparator_references", ""),
        "data_availability_status": "data_blocked",
        "missing_symbols": alignment.get("missing_symbols", ""),
        "exposure_invariant_pass": False,
        "numeric_criteria_pass": False,
        "research_only_label": "commodity_signal_data_blocked",
        "promotion_eligibility": False,
        "paper_forward_eligibility": False,
        "candidate_exhaustive_eligibility": False,
        "methodology_notes": reason,
    }


def evaluate_row(root: Path, row: dict[str, str], active_returns: pd.Series) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    prices, alignment = aligned_price_frame(root, row)
    if prices.empty or len(prices) < 252:
        blocked = data_blocked_row(row, alignment, "required common-date local cache history unavailable")
        return blocked, alignment, {}, {}

    weights = strategy_weights(row, prices)
    daily = portfolio_returns(prices, weights).rename(row["variant_id"])
    baseline_w = baseline_weights(row, prices)
    baseline_daily = portfolio_returns(prices, baseline_w).rename(row["baseline_variant_id"])
    metrics = metrics_for_returns(daily, weights)
    baseline = baseline_metrics(baseline_daily)

    bil_weights = pd.DataFrame(0.0, index=prices.index, columns=prices.columns)
    bil_weights["BIL"] = 1.0
    bil_returns = portfolio_returns(prices, bil_weights).rename("BIL")
    spy_returns = portfolio_returns(prices, spy200d_component_weights(prices))
    spy_buy_hold_weights = pd.DataFrame(0.0, index=prices.index, columns=prices.columns)
    spy_buy_hold_weights["SPY"] = 1.0
    spy_buy_hold_returns = portfolio_returns(prices, spy_buy_hold_weights).rename("SPY")
    spy200d = spy_returns.rename("SPY_200d")
    static_returns = static_all_weather_returns(root, daily.index)
    contribution = contribution_metrics(daily, active_returns)

    invariant_pass = (
        metrics["max_daily_exposure"] <= 1.000001
        and metrics["max_daily_weight_sum"] <= 1.000001
        and int(metrics["weight_sum_violation_count"]) == 0
        and int(metrics["negative_weight_violation_count"]) == 0
        and int(metrics["nan_weight_count"]) == 0
        and int(metrics["impossible_cash_and_risky_exposure_days"]) == 0
    )
    corr_spy200d = safe_corr(daily, spy200d)
    corr_static = safe_corr(daily, static_returns)
    corr_active = contribution["active_combo_correlation"]
    duplicate_values = [value for value in (corr_spy200d, corr_static, corr_active) if finite(value)]
    duplicate_reference = max(duplicate_values) if duplicate_values else float("nan")

    result = {
        "lane_id": LANE_ID,
        "family_id": FAMILY_ID,
        "variant_id": row["variant_id"],
        "role": row["variant_role"],
        "concept": row["concept"],
        "universe": row["universe"],
        "lookback": int(float(row["lookback_days"])),
        "top_n": int(float(row["top_n"])),
        "symbols_used": "|".join(prices.columns),
        "comparator_references": row["comparator_references"],
        "data_availability_status": "cache_ready",
        "missing_symbols": "",
        **metrics,
        "same_window_return_vs_bil": benchmark_delta(daily, bil_returns),
        "same_window_return_vs_spy": benchmark_delta(daily, spy_buy_hold_returns),
        "same_window_return_vs_spy200d_frozen_control": benchmark_delta(daily, spy200d),
        "static_all_weather_benchmark_control_comparison": benchmark_delta(daily, static_returns)
        if not static_returns.empty
        else float("nan"),
        "correlation_to_spy200d": corr_spy200d,
        "correlation_to_static_all_weather": corr_static,
        "correlation_to_active_combo": corr_active,
        "duplicate_reference_correlation": duplicate_reference,
        "active_vm_dsr_combo_max_drawdown_improvement": contribution["active_combo_blend_drawdown_delta"],
        "active_vm_dsr_combo_total_return_drag": contribution["active_combo_blend_total_return_delta"],
        "baseline_variant_id": row["baseline_variant_id"],
        **baseline,
        "baseline_total_return_delta": metrics["total_return"] - baseline["baseline_total_return"]
        if finite(baseline["baseline_total_return"])
        else float("nan"),
        "exposure_invariant_pass": invariant_pass,
        "promotion_eligibility": False,
        "paper_forward_eligibility": False,
        "candidate_exhaustive_eligibility": False,
        "methodology_notes": "approved 6-row commodity basket bounded run; local cache only; common-date aligned; diagnostic non-promotable evidence",
    }
    flags = criteria_flags(result)
    result["numeric_criteria_pass"] = flags["numeric_criteria_pass"]
    result["research_only_label"] = label_row(result, flags)
    criteria = {**{field: result.get(field, "") for field in CRITERIA_FIELDS}, **flags}
    criteria["variant_id"] = row["variant_id"]
    criteria["role"] = row["variant_role"]
    criteria["concept"] = row["concept"]
    criteria["research_only_label"] = result["research_only_label"]
    baseline_row = {field: result.get(field, "") for field in BASELINE_FIELDS}
    return result, alignment, criteria, baseline_row


def load_preflight(root: Path) -> dict[str, Any]:
    design = read_json(root / SOURCE_DESIGN_DIR / "commodity_basket_bounded_design_manifest.json")
    readiness = read_json(root / READINESS_DIR / "readiness_reconciliation_manifest.json")
    cache = read_json(root / CACHE_REVALIDATION_DIR / "cache_revalidation_manifest.json")
    return {
        "design_run_ready": design.get("run_readiness_decision") == "commodity_basket_bounded_design_run_ready",
        "design_next_action_correct": design.get("next_action") == "run_commodity_basket_etf_momentum_bounded_lane",
        "readiness_verified": readiness.get("final_decision") == "commodity_basket_ready_to_run_verified",
        "readiness_next_action_correct": readiness.get("next_action") == "run_commodity_basket_etf_momentum_bounded_lane",
        "cache_ready": cache.get("run_readiness_decision") == "commodity_basket_cache_ready_for_bounded_run",
        "cache_missing_symbols": cache.get("missing_symbols", []),
        "provider_download_required": False,
        "intraday_data_required": False,
    }


def evaluate_lane(root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    design_rows = read_csv_rows(root / SOURCE_DESIGN_DIR / "commodity_basket_bounded_variant_design_table.csv")
    active_returns = active_combo_returns(root)
    rows: list[dict[str, Any]] = []
    alignments: list[dict[str, Any]] = []
    criteria: list[dict[str, Any]] = []
    baseline_rows: list[dict[str, Any]] = []
    for row in design_rows:
        result, alignment, criteria_row, baseline_row = evaluate_row(root, row, active_returns)
        rows.append(result)
        alignments.append({field: alignment.get(field, "") for field in ALIGNMENT_FIELDS})
        if criteria_row:
            criteria.append(criteria_row)
        if baseline_row:
            baseline_rows.append(baseline_row)
    preflight = {
        **load_preflight(root),
        "planned_row_count_from_design": len(design_rows),
        "planned_variant_ids": [row["variant_id"] for row in design_rows],
        "evaluated_variant_ids": [row["variant_id"] for row in rows],
    }
    return rows, alignments, criteria, baseline_rows, preflight


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
    required = {symbol for row in rows for symbol in str(row.get("symbols_used", "")).split("|") if symbol}
    required.update(CORE_COMPARATOR_SYMBOLS)
    required.update(COMMODITY_SYMBOLS)
    ranges = price_ranges(root, sorted(required))
    out = []
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


def manifest_payload(
    created: str,
    output: Path,
    rows: list[dict[str, Any]],
    preflight: dict[str, Any],
) -> dict[str, Any]:
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
        and preflight["readiness_verified"]
        and preflight["cache_ready"]
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
        "commodity_basket_bounded_lane_run": True,
        "lane_id": LANE_ID,
        "family_id": FAMILY_ID,
        "source_design_run_ready": preflight["design_run_ready"],
        "source_readiness_reconciliation_verified": preflight["readiness_verified"],
        "source_cache_revalidation_ready": preflight["cache_ready"],
        "variant_count_planned": EXPECTED_ROW_COUNT,
        "variant_count_evaluated": len(rows),
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
        "macro_gld_continued": False,
        "volatility_throttle_continued": False,
        "managed_futures_reopened": False,
        "data_blocked_row_count": len(data_blocked),
        "rows_passed_numeric_criteria": sum(1 for row in rows if row.get("numeric_criteria_pass") is True),
        "rows_failed_numeric_criteria": sum(1 for row in rows if row.get("numeric_criteria_pass") is not True),
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
        f"- `{row['role']}`: pass `{row['numeric_pass_count']}`, fail `{row['numeric_fail_count']}`"
        for row in role_summary
    ]
    limits = [
        f"- `{row['variant_id']}`: `{row['effective_start_date']}` to `{row['effective_end_date']}`, start limited by `{row['limiting_start_symbols']}`, end limited by `{row['limiting_end_symbols']}`"
        for row in alignments
    ]
    return f"""# Commodity Basket ETF Momentum Bounded Run

Lane ID: `{manifest['lane_id']}`

Rows planned: `{manifest['variant_count_planned']}`

Rows evaluated: `{manifest['variant_count_evaluated']}`

Data-blocked rows: `{manifest['data_blocked_row_count']}`

Rows passed numeric criteria: `{manifest['rows_passed_numeric_criteria']}`

Rows failed numeric criteria: `{manifest['rows_failed_numeric_criteria']}`

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

No output is promotable, candidate_exhaustive-ready, or paper-forward eligible.

Exact next action: `{manifest['next_action']}`
"""


def alignment_md(alignments: list[dict[str, Any]]) -> str:
    lines = ["# Data Alignment / Effective Date Window Report", ""]
    for row in alignments:
        lines.append(
            f"- `{row['variant_id']}`: `{row['effective_start_date']}` to `{row['effective_end_date']}`; "
            f"start limited by `{row['limiting_start_symbols']}`; end limited by `{row['limiting_end_symbols']}`; "
            f"BIL/SPY/GLD end limit `{row['bil_spy_gld_limited_end_date']}`"
        )
    lines.append("")
    lines.append("Rows use common-date alignment across required row symbols plus BIL, SPY, and GLD comparators.")
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
            f"`{parse_float(row.get('same_window_return_vs_spy200d_frozen_control')):.6f}`"
        )
    lines.append("")
    lines.append("Static all-weather remains benchmark/control only and is not converted into candidate status.")
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
    return "# Commodity Basket Bounded Label Summary\n\n" + "\n".join(
        f"- `{label}`: `{manifest[f'{label}_count']}`" for label in sorted(ALLOWED_LABELS)
    ) + "\n"


def do_not_promote_md() -> str:
    return """# Do Not Promote From Commodity Basket Bounded Run

This run is diagnostic historical research evidence only.

It creates no promotion-review candidate, candidate_exhaustive candidate, paper-forward candidate, paper-forward activation, broker/live action, or real-money recommendation.
"""


def next_action_md(next_action: str) -> str:
    return f"""# Commodity Basket Bounded Run Next Action

Exact next action:

`{next_action}`

Do not execute the next action in this task.
"""


def consistency_check(manifest: dict[str, Any], rows: list[dict[str, Any]], output: Path) -> dict[str, Any]:
    required = {name: (output / name).exists() for name in REQUIRED_FILES}
    required["commodity_basket_bounded_run_consistency_check.json"] = True
    labels = {row.get("research_only_label", "") for row in rows}
    checks = {
        "correct_lane_id": manifest["lane_id"] == LANE_ID,
        "correct_family_id": manifest["family_id"] == FAMILY_ID,
        "source_design_run_ready": manifest["source_design_run_ready"] is True,
        "source_readiness_verified": manifest["source_readiness_reconciliation_verified"] is True,
        "source_cache_ready": manifest["source_cache_revalidation_ready"] is True,
        "variant_count_exact_6": manifest["variant_count_evaluated"] == EXPECTED_ROW_COUNT,
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
        "excluded_work_not_continued": manifest["macro_gld_continued"] is False
        and manifest["volatility_throttle_continued"] is False
        and manifest["managed_futures_reopened"] is False,
        "allowed_labels_only": labels.issubset(ALLOWED_LABELS),
        "all_rows_non_promotable": all(row.get("promotion_eligibility") is False for row in rows),
        "all_rows_not_paper": all(row.get("paper_forward_eligibility") is False for row in rows),
        "all_rows_not_candidate_exhaustive": all(row.get("candidate_exhaustive_eligibility") is False for row in rows),
        "max_daily_exposure_lte_1": manifest["max_daily_exposure"] <= 1.000001,
        "max_daily_weight_sum_lte_1": manifest["max_daily_weight_sum"] <= 1.000001,
        "exposure_invariant_passed": manifest["exposure_invariant_passed"] is True,
        "row_results_exist": (output / "commodity_basket_bounded_row_results.csv").exists(),
        "criteria_results_exist": (output / "commodity_basket_bounded_numeric_criteria_results.csv").exists(),
        "alignment_report_exists": (output / "data_alignment_effective_window_report.md").exists(),
        "symbol_coverage_report_exists": (output / "symbol_coverage_report.md").exists(),
        "baseline_report_exists": (output / "baseline_comparator_report.md").exists(),
        "do_not_promote_exists": (output / "do_not_promote_from_commodity_basket_bounded_run.md").exists(),
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
    preflight: dict[str, Any],
) -> dict[str, Any]:
    output = root / OUTPUT_DIR
    output.mkdir(parents=True, exist_ok=True)
    manifest = manifest_payload(created, output, rows, preflight)
    concept_summary = pass_fail_summary(rows, "concept")
    role_summary = pass_fail_summary(rows, "role")
    coverage = symbol_coverage_rows(root, rows)

    write_json(output / "commodity_basket_bounded_run_manifest.json", manifest)
    write_csv(output / "commodity_basket_bounded_row_results.csv", rows, list(RESULT_FIELDS))
    write_csv(output / "commodity_basket_bounded_numeric_criteria_results.csv", criteria, list(CRITERIA_FIELDS))
    write_csv(output / "data_alignment_effective_window_report.csv", alignments, list(ALIGNMENT_FIELDS))
    write_text(output / "data_alignment_effective_window_report.md", alignment_md(alignments))
    write_csv(output / "symbol_coverage_report.csv", coverage, list(coverage[0].keys()) if coverage else [])
    write_text(output / "symbol_coverage_report.md", coverage_md(coverage))
    write_csv(output / "baseline_comparator_report.csv", baseline_rows, list(BASELINE_FIELDS))
    write_text(output / "baseline_comparator_report.md", baseline_md(rows))
    write_csv(output / "commodity_basket_bounded_concept_summary.csv", concept_summary, list(concept_summary[0].keys()) if concept_summary else [])
    write_csv(output / "commodity_basket_bounded_role_summary.csv", role_summary, list(role_summary[0].keys()) if role_summary else [])
    write_text(output / "exposure_invariant_report.md", invariant_md(manifest, rows))
    write_text(output / "commodity_basket_bounded_label_summary.md", label_summary_md(manifest))
    write_text(output / "commodity_basket_bounded_run_summary.md", summary_md(manifest, concept_summary, role_summary, alignments))
    write_text(output / "do_not_promote_from_commodity_basket_bounded_run.md", do_not_promote_md())
    write_text(output / "commodity_basket_bounded_run_next_action.md", next_action_md(manifest["next_action"]))
    check = consistency_check(manifest, rows, output)
    write_json(output / "commodity_basket_bounded_run_consistency_check.json", check)
    return {**manifest, "output_dir": str(output.resolve()), "consistency_passed": check["consistency_passed"]}


def run(root: Path = ROOT) -> dict[str, Any]:
    created = now_utc()
    rows, alignments, criteria, baseline_rows, preflight = evaluate_lane(root)
    return write_outputs(root, created, rows, alignments, criteria, baseline_rows, preflight)


if __name__ == "__main__":
    result = run()
    print(
        json.dumps(
            {
                "output_dir": result["output_dir"],
                "lane_id": result["lane_id"],
                "variant_count_evaluated": result["variant_count_evaluated"],
                "data_blocked_row_count": result["data_blocked_row_count"],
                "rows_passed_numeric_criteria": result["rows_passed_numeric_criteria"],
                "exposure_invariant_passed": result["exposure_invariant_passed"],
                "results_interpretable": result["results_interpretable"],
                "next_action": result["next_action"],
                "consistency_passed": result["consistency_passed"],
            },
            indent=2,
        )
    )
