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
from strategy_lab.research_os.research.global_multi_asset_etf_momentum_bounded_design import (
    FAMILY_ID,
    LANE_ID,
    NEXT_ACTION_RUN,
    RANKED_ASSETS,
    REQUIRED_SYMBOLS,
    RUN_READY,
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
    trade_count_and_turnover,
    weight_invariant_report,
    write_csv,
)


SOURCE_DESIGN_DIR = (
    Path("evidence") / "research_recovery" / "global_multi_asset_etf_momentum_bounded_design" / "latest"
)
SOURCE_CONTEXT_DIR = Path("evidence") / "multi_asset_lab" / "fast_exploration_batch1" / "latest"
OUTPUT_DIR = (
    Path("evidence") / "research_recovery" / "global_multi_asset_etf_momentum_bounded_run" / "latest"
)

EXPECTED_ROW_COUNT = 6
WEIGHT_TOLERANCE = 1e-6
PROJECT_START_EQUITY = 3000.0
PROJECT_STOP_DRAWDOWN = -600.0
PROJECT_TARGET_300 = 3300.0
PROJECT_TARGET_400 = 3400.0

NEXT_ACTION_AUDIT = "audit_global_multi_asset_etf_momentum_bounded_lane_results"
NEXT_ACTION_FIX = "fix_global_multi_asset_bounded_lane_run_methodology_issue"
NEXT_ACTION_CACHE = "restore_or_revalidate_global_multi_asset_local_cache_before_bounded_run"
VALID_NEXT_ACTIONS = {NEXT_ACTION_AUDIT, NEXT_ACTION_FIX, NEXT_ACTION_CACHE}

ALLOWED_LABELS = {
    "global_multi_asset_signal_diagnostic_pass",
    "global_multi_asset_signal_context_only",
    "global_multi_asset_signal_control_only",
    "global_multi_asset_signal_data_blocked",
    "global_multi_asset_signal_too_cash_heavy",
    "global_multi_asset_signal_risk_budget_breach",
    "global_multi_asset_signal_return_diluted",
    "global_multi_asset_signal_duplicate_reference",
    "global_multi_asset_signal_contribution_context_pass",
    "global_multi_asset_signal_contribution_too_small",
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
    "stop_hit_rate_180d",
    "worst_180_day_drawdown_project_dollars",
    "p_target_300_before_stop_180d",
    "p_target_400_before_stop_180d",
    "median_final_equity_180d",
    "average_bil_cash_share",
    "max_bil_cash_share",
    "score_delta_vs_bil_cash_proxy",
    "score_delta_vs_active_combo",
    "correlation_to_active_combo",
    "correlation_to_spy200d",
    "duplicate_reference_correlation",
    "active_vm_dsr_combo_max_drawdown_improvement",
    "active_vm_dsr_combo_total_return_drag",
    "same_window_return_vs_bil",
    "same_window_return_vs_spy",
    "same_window_return_vs_spy200d_frozen_control",
    "same_window_return_vs_gld",
    "static_all_weather_benchmark_control_comparison",
    "baseline_variant_id",
    "baseline_total_return",
    "baseline_cagr",
    "baseline_max_drawdown",
    "baseline_calmar_or_return_drawdown_proxy",
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
    "exposure_invariant_pass",
    "max_daily_exposure",
    "max_daily_exposure_pass",
    "max_daily_weight_sum",
    "max_daily_weight_sum_pass",
    "stop_hit_rate_180d",
    "stop_hit_rate_180d_pass",
    "worst_180_day_drawdown_project_dollars",
    "worst_180_day_drawdown_pass",
    "p_target_300_before_stop_180d",
    "p_target_300_before_stop_pass",
    "p_target_400_before_stop_180d",
    "p_target_400_before_stop_pass",
    "median_final_equity_180d",
    "median_final_equity_pass",
    "average_bil_cash_share",
    "bil_cash_share_pass",
    "score_delta_vs_bil_cash_proxy",
    "score_delta_vs_bil_pass",
    "score_delta_vs_active_combo",
    "score_delta_vs_active_combo_pass",
    "correlation_to_active_combo",
    "active_combo_correlation_pass",
    "correlation_to_spy200d",
    "spy200d_correlation_pass",
    "selected_confirmation_criteria_pass",
    "baseline_context_criteria_pass",
    "portfolio_context_criteria_pass",
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

BASELINE_FIELDS = (
    "variant_id",
    "variant_role",
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
    "same_window_return_vs_gld",
    "static_all_weather_benchmark_control_comparison",
)

REQUIRED_FILES = (
    "global_multi_asset_bounded_run_manifest.json",
    "global_multi_asset_bounded_run_consistency_check.json",
    "global_multi_asset_bounded_row_results.csv",
    "global_multi_asset_bounded_numeric_criteria_results.csv",
    "data_alignment_effective_window_report.csv",
    "data_alignment_effective_window_report.md",
    "symbol_coverage_report.csv",
    "symbol_coverage_report.md",
    "baseline_comparator_report.csv",
    "baseline_comparator_report.md",
    "exposure_invariant_report.md",
    "role_label_summary.md",
    "source_lineage_context_report.md",
    "global_multi_asset_bounded_run_summary.md",
    "do_not_promote_from_global_multi_asset_bounded_run.md",
    "global_multi_asset_bounded_run_next_action.md",
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
    symbols = list(REQUIRED_SYMBOLS)
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
            "common_date_count": 0,
            "alignment_status": "data_blocked_missing_symbols",
            "ranges": ranges,
        }
    prices = load_prices(root, tuple(symbols))
    common = prices.dropna(subset=symbols).index if not prices.empty else pd.Index([])
    if len(common) == 0:
        return pd.DataFrame(), {
            "variant_id": row["variant_id"],
            "required_symbols": "|".join(symbols),
            "missing_symbols": "",
            "effective_start_date": "",
            "effective_end_date": "",
            "limiting_start_symbols": "",
            "limiting_end_symbols": "",
            "common_date_count": 0,
            "alignment_status": "data_blocked_no_common_dates",
            "ranges": ranges,
        }
    first_dates = {symbol: ranges[symbol]["first_date"] for symbol in symbols}
    last_dates = {symbol: ranges[symbol]["last_date"] for symbol in symbols}
    max_first = max(first_dates.values())
    min_last = min(last_dates.values())
    aligned = prices.loc[common, symbols].copy()
    return aligned, {
        "variant_id": row["variant_id"],
        "required_symbols": "|".join(symbols),
        "missing_symbols": "",
        "effective_start_date": aligned.index.min().date().isoformat(),
        "effective_end_date": aligned.index.max().date().isoformat(),
        "limiting_start_symbols": "|".join([symbol for symbol, value in first_dates.items() if value == max_first]),
        "limiting_end_symbols": "|".join([symbol for symbol, value in last_dates.items() if value == min_last]),
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
        clean["BIL"] = max(0.0, min(1.0, 1.0 - risky))
    return clean


def global_tsmom_weights(prices: pd.DataFrame, *, lookback: int = 126, top_n: int = 2) -> pd.DataFrame:
    columns = list(prices.columns)
    ranked = [symbol for symbol in RANKED_ASSETS if symbol in prices.columns]
    scores = prices[ranked].pct_change(lookback, fill_method=None).shift(1)
    rebalance_targets: dict[pd.Timestamp, dict[str, float]] = {}
    for date in prices.index[month_rebalance_mask(prices.index)]:
        target = target_template(columns)
        score_row = scores.loc[date].dropna().sort_values(ascending=False)
        selected = list(score_row.head(top_n).index)
        slot = 1.0 / max(top_n, 1)
        for symbol in selected:
            if float(score_row.get(symbol, float("nan"))) > 0.0:
                target[symbol] += slot
            else:
                target["BIL"] += slot
        target["BIL"] += slot * max(0, top_n - len(selected))
        rebalance_targets[pd.Timestamp(date)] = normalize_target(target, columns)
    return complete_rebalance_weight_frame(prices.index, columns, rebalance_targets)


def selected_defensive_weights(prices: pd.DataFrame) -> pd.DataFrame:
    base = global_tsmom_weights(prices, lookback=126, top_n=2)
    weights = pd.DataFrame(0.0, index=base.index, columns=base.columns)
    risky_cols = [column for column in base.columns if column != "BIL"]
    weights[risky_cols] = base[risky_cols] * 0.5
    if "BIL" in weights.columns:
        weights["BIL"] = 1.0 - weights[risky_cols].sum(axis=1)
    return weights


def spy200d_component_weights(prices: pd.DataFrame) -> pd.DataFrame:
    columns = list(prices.columns)
    weights = pd.DataFrame(0.0, index=prices.index, columns=columns)
    prior_spy = prices["SPY"].shift(1)
    prior_sma = prices["SPY"].shift(1).rolling(200, min_periods=100).mean()
    risk_on = prior_spy > prior_sma
    rebalance_targets: dict[pd.Timestamp, dict[str, float]] = {}
    for date in prices.index[month_rebalance_mask(prices.index)]:
        target = target_template(columns)
        if bool(risk_on.loc[date]):
            target["SPY"] = 1.0
        else:
            target["BIL"] = 1.0
        rebalance_targets[pd.Timestamp(date)] = normalize_target(target, columns)
    return complete_rebalance_weight_frame(prices.index, columns, rebalance_targets)


def combo_spy200d_gld_weights(prices: pd.DataFrame) -> pd.DataFrame:
    columns = list(prices.columns)
    spy200d = spy200d_component_weights(prices)
    weights = pd.DataFrame(0.0, index=prices.index, columns=columns)
    weights = weights.add(spy200d * 0.5, fill_value=0.0)
    if "GLD" in weights.columns:
        weights["GLD"] = weights["GLD"] + 0.5
    if "BIL" in weights.columns:
        risky = weights.drop(columns=["BIL"]).sum(axis=1)
        weights["BIL"] = np.maximum(weights["BIL"], 1.0 - risky)
    return weights.reindex(columns=columns).fillna(0.0)


def combo_plus_global_weights(prices: pd.DataFrame) -> pd.DataFrame:
    base = global_tsmom_weights(prices, lookback=126, top_n=2)
    combo = combo_spy200d_gld_weights(prices)
    weights = 0.8 * combo + 0.2 * base
    return weights.reindex(columns=prices.columns).fillna(0.0)


def bil_control_weights(prices: pd.DataFrame) -> pd.DataFrame:
    weights = pd.DataFrame(0.0, index=prices.index, columns=prices.columns)
    weights["BIL"] = 1.0
    return weights


def gld_control_weights(prices: pd.DataFrame) -> pd.DataFrame:
    weights = pd.DataFrame(0.0, index=prices.index, columns=prices.columns)
    weights["GLD"] = 1.0
    return weights


def strategy_weights(row: dict[str, str], prices: pd.DataFrame) -> pd.DataFrame:
    concept = row["concept"]
    if concept == "fixed_50pct_global_multi_asset_tsmom_top2_50pct_bil":
        return selected_defensive_weights(prices)
    if concept == "global_multi_asset_tsmom_top2":
        return global_tsmom_weights(prices, lookback=126, top_n=2)
    if concept == "active_combo_plus_global_multi_asset_sleeve":
        return combo_plus_global_weights(prices)
    if concept == "spy200d_frozen_control":
        return spy200d_component_weights(prices)
    if concept == "bil_cash_proxy_control":
        return bil_control_weights(prices)
    if concept == "gld_buy_hold_control":
        return gld_control_weights(prices)
    return bil_control_weights(prices)


def baseline_weights(row: dict[str, str], prices: pd.DataFrame) -> pd.DataFrame:
    baseline = row["baseline_variant_id"]
    if baseline == "global_multi_asset_tsmom_top2_v1":
        return global_tsmom_weights(prices, lookback=126, top_n=2)
    if baseline == "combo_SPY200d_GLD_50_50_v1":
        return combo_spy200d_gld_weights(prices)
    if baseline == "SPY_200d_trend_model":
        return spy200d_component_weights(prices)
    if baseline == "BIL_cash_proxy":
        return bil_control_weights(prices)
    if baseline == "GLD_buy_hold":
        return gld_control_weights(prices)
    return strategy_weights(row, prices)


def portfolio_returns(prices: pd.DataFrame, weights: pd.DataFrame) -> pd.Series:
    returns = prices.pct_change(fill_method=None).fillna(0.0)
    aligned_weights = weights.reindex(prices.index).ffill().fillna(0.0).reindex(columns=prices.columns, fill_value=0.0)
    return (aligned_weights.shift(1).fillna(0.0) * returns).sum(axis=1)


def static_all_weather_returns(prices: pd.DataFrame) -> pd.Series:
    columns = ["SPY", "IEF", "GLD", "BIL"]
    weights = pd.DataFrame(0.0, index=prices.index, columns=prices.columns)
    weights["SPY"] = 0.30
    weights["IEF"] = 0.40
    weights["GLD"] = 0.20
    weights["BIL"] = 0.10
    return portfolio_returns(prices, weights).rename("static_all_weather")


def project_window_stats(daily: pd.Series, window: int = 180) -> dict[str, float]:
    daily = daily.dropna()
    if len(daily) <= window:
        return {
            "stop_hit_rate_180d": float("nan"),
            "worst_180_day_drawdown_project_dollars": float("nan"),
            "p_target_300_before_stop_180d": float("nan"),
            "p_target_400_before_stop_180d": float("nan"),
            "median_final_equity_180d": float("nan"),
        }
    final_equities: list[float] = []
    drawdowns: list[float] = []
    stop_hits = 0
    target_300_before_stop = 0
    target_400_before_stop = 0
    values = daily.to_numpy(dtype=float)
    for start in range(0, len(values) - window + 1):
        path = PROJECT_START_EQUITY * np.cumprod(1.0 + values[start : start + window])
        full_path = np.concatenate([[PROJECT_START_EQUITY], path])
        running_peak = np.maximum.accumulate(full_path)
        dollar_drawdown = full_path - running_peak
        worst_drawdown = float(dollar_drawdown.min())
        drawdowns.append(worst_drawdown)
        final_equities.append(float(full_path[-1]))
        stop_index = np.where(dollar_drawdown <= PROJECT_STOP_DRAWDOWN)[0]
        target_300_index = np.where(full_path >= PROJECT_TARGET_300)[0]
        target_400_index = np.where(full_path >= PROJECT_TARGET_400)[0]
        first_stop = int(stop_index[0]) if len(stop_index) else math.inf
        first_target_300 = int(target_300_index[0]) if len(target_300_index) else math.inf
        first_target_400 = int(target_400_index[0]) if len(target_400_index) else math.inf
        if first_stop < math.inf:
            stop_hits += 1
        if first_target_300 < first_stop:
            target_300_before_stop += 1
        if first_target_400 < first_stop:
            target_400_before_stop += 1
    count = float(len(final_equities))
    return {
        "stop_hit_rate_180d": stop_hits / count,
        "worst_180_day_drawdown_project_dollars": min(drawdowns),
        "p_target_300_before_stop_180d": target_300_before_stop / count,
        "p_target_400_before_stop_180d": target_400_before_stop / count,
        "median_final_equity_180d": float(np.median(final_equities)),
    }


def score_delta_180d(strategy_returns: pd.Series, reference_returns: pd.Series) -> float:
    aligned = pd.concat([strategy_returns.rename("strategy"), reference_returns.rename("reference")], axis=1).dropna()
    if len(aligned) <= 180:
        return float("nan")
    strategy = project_window_stats(aligned["strategy"])["median_final_equity_180d"]
    reference = project_window_stats(aligned["reference"])["median_final_equity_180d"]
    return strategy - reference if finite(strategy) and finite(reference) else float("nan")


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


def baseline_metrics(daily: pd.Series) -> dict[str, Any]:
    metrics = metrics_for_returns(daily, pd.DataFrame(index=daily.index))
    return {
        "baseline_total_return": metrics.get("total_return", float("nan")),
        "baseline_cagr": metrics.get("cagr", float("nan")),
        "baseline_max_drawdown": metrics.get("max_drawdown", float("nan")),
        "baseline_calmar_or_return_drawdown_proxy": metrics.get("calmar_or_return_drawdown_proxy", float("nan")),
    }


def criteria_flags(row: dict[str, Any]) -> dict[str, Any]:
    role = row.get("variant_role")
    max_exposure = parse_float(row.get("max_daily_exposure"))
    max_weight = parse_float(row.get("max_daily_weight_sum"))
    stop_rate = parse_float(row.get("stop_hit_rate_180d"))
    worst_180 = parse_float(row.get("worst_180_day_drawdown_project_dollars"))
    p300 = parse_float(row.get("p_target_300_before_stop_180d"))
    p400 = parse_float(row.get("p_target_400_before_stop_180d"))
    median_final = parse_float(row.get("median_final_equity_180d"))
    avg_bil = parse_float(row.get("average_bil_cash_share"))
    bil_delta = parse_float(row.get("score_delta_vs_bil_cash_proxy"))
    active_delta = parse_float(row.get("score_delta_vs_active_combo"))
    active_corr = parse_float(row.get("correlation_to_active_combo"))
    spy200d_corr = parse_float(row.get("correlation_to_spy200d"))
    exposure_pass = (
        row.get("exposure_invariant_pass") is True
        and max_exposure <= 1.000001
        and max_weight <= 1.000001
    )
    selected_pass = (
        role == "selected_confirmation"
        and exposure_pass
        and finite(stop_rate)
        and stop_rate <= 0.0250
        and finite(worst_180)
        and worst_180 >= -450.0
        and finite(p300)
        and p300 >= 0.5000
        and finite(p400)
        and p400 >= 0.2500
        and finite(median_final)
        and median_final >= 3250.0
        and avg_bil <= 0.6000
        and (not finite(active_corr) or active_corr < 0.9000)
        and finite(bil_delta)
        and bil_delta > 0.0
    )
    baseline_pass = (
        role == "uncontrolled_source_baseline_context"
        and exposure_pass
        and finite(median_final)
        and median_final >= 3400.0
        and finite(worst_180)
        and worst_180 >= -650.0
        and finite(stop_rate)
        and stop_rate <= 0.0750
    )
    portfolio_pass = (
        role == "portfolio_contribution_context"
        and exposure_pass
        and (not finite(active_corr) or active_corr < 0.9000)
        and finite(worst_180)
        and worst_180 >= -550.0
        and finite(median_final)
        and median_final >= 3300.0
        and (not finite(active_delta) or active_delta >= 0.0)
    )
    return {
        "max_daily_exposure_pass": max_exposure <= 1.000001,
        "max_daily_weight_sum_pass": max_weight <= 1.000001,
        "stop_hit_rate_180d_pass": finite(stop_rate) and stop_rate <= 0.0250,
        "worst_180_day_drawdown_pass": finite(worst_180) and worst_180 >= -450.0,
        "p_target_300_before_stop_pass": finite(p300) and p300 >= 0.5000,
        "p_target_400_before_stop_pass": finite(p400) and p400 >= 0.2500,
        "median_final_equity_pass": finite(median_final) and median_final >= 3250.0,
        "bil_cash_share_pass": avg_bil <= 0.6000,
        "score_delta_vs_bil_pass": finite(bil_delta) and bil_delta > 0.0,
        "score_delta_vs_active_combo_pass": not finite(active_delta) or active_delta >= 0.0,
        "active_combo_correlation_pass": not finite(active_corr) or active_corr < 0.9000,
        "spy200d_correlation_pass": not finite(spy200d_corr) or spy200d_corr < 0.9000,
        "selected_confirmation_criteria_pass": selected_pass,
        "baseline_context_criteria_pass": baseline_pass,
        "portfolio_context_criteria_pass": portfolio_pass,
        "numeric_criteria_pass": selected_pass or baseline_pass or portfolio_pass,
    }


def label_row(row: dict[str, Any], flags: dict[str, Any]) -> str:
    role = row.get("variant_role")
    if row.get("data_availability_status") != "cache_ready":
        return "global_multi_asset_signal_data_blocked"
    if role in {"comparator_control", "cash_control", "commodity_real_asset_control"}:
        return "global_multi_asset_signal_control_only"
    if row.get("exposure_invariant_pass") is not True:
        return "global_multi_asset_signal_risk_budget_breach"
    if role == "portfolio_contribution_context":
        return (
            "global_multi_asset_signal_contribution_context_pass"
            if flags["portfolio_context_criteria_pass"]
            else "global_multi_asset_signal_contribution_too_small"
        )
    if flags["active_combo_correlation_pass"] is False or flags["spy200d_correlation_pass"] is False:
        return "global_multi_asset_signal_duplicate_reference"
    if flags["bil_cash_share_pass"] is False:
        return "global_multi_asset_signal_too_cash_heavy"
    if flags["stop_hit_rate_180d_pass"] is False or flags["worst_180_day_drawdown_pass"] is False:
        return "global_multi_asset_signal_risk_budget_breach"
    if flags["median_final_equity_pass"] is False:
        return "global_multi_asset_signal_return_diluted"
    if role == "selected_confirmation" and flags["selected_confirmation_criteria_pass"] is True:
        return "global_multi_asset_signal_diagnostic_pass"
    return "global_multi_asset_signal_context_only"


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
        "research_only_label": "global_multi_asset_signal_data_blocked",
        "promotion_eligibility": False,
        "paper_forward_eligibility": False,
        "candidate_exhaustive_eligibility": False,
        "methodology_notes": reason,
    }


def evaluate_row(
    root: Path,
    row: dict[str, str],
    active_returns: pd.Series,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    prices, alignment = aligned_price_frame(root, row)
    if prices.empty or len(prices) < 252:
        blocked = data_blocked_row(row, alignment, "required common-date local cache history unavailable")
        return blocked, alignment, {}, {}

    weights = strategy_weights(row, prices)
    daily = portfolio_returns(prices, weights).rename(row["variant_id"])
    baseline_w = baseline_weights(row, prices)
    baseline_daily = portfolio_returns(prices, baseline_w).rename(row["baseline_variant_id"])

    bil_returns = portfolio_returns(prices, bil_control_weights(prices)).rename("BIL")
    gld_returns = portfolio_returns(prices, gld_control_weights(prices)).rename("GLD")
    spy_buy_hold_weights = pd.DataFrame(0.0, index=prices.index, columns=prices.columns)
    spy_buy_hold_weights["SPY"] = 1.0
    spy_returns = portfolio_returns(prices, spy_buy_hold_weights).rename("SPY")
    spy200d_returns = portfolio_returns(prices, spy200d_component_weights(prices)).rename("SPY_200d")
    static_returns = static_all_weather_returns(prices).rename("static_all_weather")

    metrics = metrics_for_returns(daily, weights)
    baseline = baseline_metrics(baseline_daily)
    contribution = contribution_metrics(daily, active_returns)
    score_delta_active = score_delta_180d(daily, active_returns) if not active_returns.empty else float("nan")
    corr_spy200d = safe_corr(daily, spy200d_returns)
    corr_active = contribution["active_combo_correlation"]
    duplicate_values = [value for value in (corr_spy200d, corr_active) if finite(value)]
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
        "score_delta_vs_bil_cash_proxy": score_delta_180d(daily, bil_returns),
        "score_delta_vs_active_combo": score_delta_active,
        "correlation_to_active_combo": corr_active,
        "correlation_to_spy200d": corr_spy200d,
        "duplicate_reference_correlation": duplicate_reference,
        "active_vm_dsr_combo_max_drawdown_improvement": contribution["active_combo_blend_drawdown_delta"],
        "active_vm_dsr_combo_total_return_drag": contribution["active_combo_blend_total_return_delta"],
        "same_window_return_vs_bil": benchmark_delta(daily, bil_returns),
        "same_window_return_vs_spy": benchmark_delta(daily, spy_returns),
        "same_window_return_vs_spy200d_frozen_control": benchmark_delta(daily, spy200d_returns),
        "same_window_return_vs_gld": benchmark_delta(daily, gld_returns),
        "static_all_weather_benchmark_control_comparison": benchmark_delta(daily, static_returns),
        "baseline_variant_id": row["baseline_variant_id"],
        **baseline,
        "baseline_total_return_delta": metrics["total_return"] - baseline["baseline_total_return"]
        if finite(baseline["baseline_total_return"])
        else float("nan"),
        "exposure_invariant_pass": invariant_pass,
        "promotion_eligibility": False,
        "paper_forward_eligibility": False,
        "candidate_exhaustive_eligibility": False,
        "methodology_notes": "approved 6-row global multi-asset bounded run; fresh current-cache diagnostics; source exploratory evidence context only",
    }
    flags = criteria_flags(result)
    result["numeric_criteria_pass"] = flags["numeric_criteria_pass"]
    result["research_only_label"] = label_row(result, flags)
    criteria = {field: result.get(field, "") for field in CRITERIA_FIELDS}
    criteria.update(flags)
    criteria["variant_id"] = row["variant_id"]
    criteria["variant_role"] = row["variant_role"]
    criteria["concept"] = row["concept"]
    criteria["research_only_label"] = result["research_only_label"]
    baseline_row = {field: result.get(field, "") for field in BASELINE_FIELDS}
    baseline_row["strategy_total_return"] = result["total_return"]
    baseline_row["strategy_cagr"] = result["cagr"]
    baseline_row["strategy_max_drawdown"] = result["max_drawdown"]
    return result, alignment, criteria, baseline_row


def load_preflight(root: Path) -> dict[str, Any]:
    design = read_json(root / SOURCE_DESIGN_DIR / "global_multi_asset_bounded_design_manifest.json")
    source_context_exists = (root / SOURCE_CONTEXT_DIR).exists()
    return {
        "design_run_ready": design.get("run_readiness_decision") == RUN_READY,
        "design_next_action_correct": design.get("next_action") == NEXT_ACTION_RUN,
        "source_context_exists": source_context_exists,
        "source_context_status": design.get("source_evidence_context_status") == "older_exploratory_context_only",
        "local_cache_complete": design.get("local_cache_complete") is True,
        "provider_download_required": False,
        "intraday_data_required": False,
    }


def evaluate_lane(root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    design_rows = read_csv_rows(root / SOURCE_DESIGN_DIR / "planned_variant_design_table.csv")
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
                "median_180d_final_equity": float(
                    pd.to_numeric(subset["median_final_equity_180d"], errors="coerce").median()
                ),
                "median_average_bil_cash_share": float(
                    pd.to_numeric(subset["average_bil_cash_share"], errors="coerce").median()
                ),
            }
        )
    return summary


def symbol_coverage_rows(root: Path, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ranges = price_ranges(root, list(REQUIRED_SYMBOLS))
    out = []
    for symbol in REQUIRED_SYMBOLS:
        used_by = [row["variant_id"] for row in rows if symbol in str(row.get("symbols_used", "")).split("|")]
        out.append(
            {
                "symbol": symbol,
                "required": True,
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
        and preflight["local_cache_complete"]
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
        "global_multi_asset_bounded_lane_run": True,
        "lane_id": LANE_ID,
        "family_id": FAMILY_ID,
        "source_design_run_ready": preflight["design_run_ready"],
        "source_design_next_action_correct": preflight["design_next_action_correct"],
        "source_exploratory_context_exists": preflight["source_context_exists"],
        "source_exploratory_context_only": preflight["source_context_status"],
        "source_metrics_reused_as_current_performance_proof": False,
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
        "leverage_allowed": False,
        "shorting_allowed": False,
        "options_allowed": False,
        "direct_futures_allowed": False,
        "margin_allowed": False,
        "forex_allowed": False,
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
        "high_return_tactical_continued": False,
        "commodity_continued": False,
        "macro_gld_continued": False,
        "volatility_throttle_continued": False,
        "managed_futures_reopened": False,
        "crypto_continued": False,
        "regional_momentum_continued": False,
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
    rows: list[dict[str, Any]],
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
    selected = [row for row in rows if row.get("variant_role") == "selected_confirmation"]
    baseline = [row for row in rows if row.get("variant_role") == "uncontrolled_source_baseline_context"]
    portfolio = [row for row in rows if row.get("variant_role") == "portfolio_contribution_context"]
    controls = [row for row in rows if row.get("variant_role") in {"comparator_control", "cash_control", "commodity_real_asset_control"}]
    limits = [
        f"- `{row['variant_id']}`: `{row['effective_start_date']}` to `{row['effective_end_date']}`, "
        f"start limited by `{row['limiting_start_symbols']}`, end limited by `{row['limiting_end_symbols']}`"
        for row in alignments
    ]
    return f"""# Global Multi-Asset ETF Momentum Bounded Run

Lane ID: `{manifest['lane_id']}`

Rows planned: `{manifest['variant_count_planned']}`

Rows evaluated: `{manifest['variant_count_evaluated']}`

Data-blocked rows: `{manifest['data_blocked_row_count']}`

Rows passed numeric criteria: `{manifest['rows_passed_numeric_criteria']}`

Rows failed numeric criteria: `{manifest['rows_failed_numeric_criteria']}`

Invariant failures: `{manifest['invariant_failure_count']}`

Results interpretable: `{manifest['results_interpretable']}`

Usable diagnostic evidence produced: `{manifest['usable_diagnostic_evidence']}`

Selected confirmation result:

{row_summary_lines(selected)}

Baseline/context result:

{row_summary_lines(baseline)}

Portfolio-contribution context result:

{row_summary_lines(portfolio)}

Control row results:

{row_summary_lines(controls)}

Pass/fail by concept:

{chr(10).join(concept_lines)}

Rows by role:

{chr(10).join(role_lines)}

Research-only label counts:

{chr(10).join(label_lines)}

Date-alignment limitations:

{chr(10).join(limits)}

Older exploratory source evidence was treated as lineage context only. Current diagnostics were recomputed from local cache.

No output is promotable, candidate_exhaustive-ready, or paper-forward eligible.

Exact next action: `{manifest['next_action']}`
"""


def row_summary_lines(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "- None"
    return "\n".join(
        f"- `{row['variant_id']}`: label `{row['research_only_label']}`, numeric pass `{row['numeric_criteria_pass']}`, "
        f"CAGR `{parse_float(row.get('cagr')):.6f}`, max drawdown `{parse_float(row.get('max_drawdown')):.6f}`, "
        f"median 180d equity `{parse_float(row.get('median_final_equity_180d')):.2f}`"
        for row in rows
    )


def alignment_md(alignments: list[dict[str, Any]]) -> str:
    lines = ["# Data Alignment / Effective Date Window Report", ""]
    for row in alignments:
        lines.append(
            f"- `{row['variant_id']}`: `{row['effective_start_date']}` to `{row['effective_end_date']}`; "
            f"start limited by `{row['limiting_start_symbols']}`; end limited by `{row['limiting_end_symbols']}`"
        )
    lines.append("")
    lines.append("Rows use common-date alignment across all approved required symbols and controls.")
    lines.append("No symbol history is forward-filled before inception.")
    lines.append("Rows are not extended beyond the latest common available comparator/control date.")
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
            f"- `{row['variant_id']}` vs `{row['baseline_variant_id']}`: baseline total-return delta "
            f"`{parse_float(row.get('baseline_total_return_delta')):.6f}`, BIL score delta "
            f"`{parse_float(row.get('score_delta_vs_bil_cash_proxy')):.2f}`, active-combo score delta "
            f"`{parse_float(row.get('score_delta_vs_active_combo')):.2f}`, SPY_200d return delta "
            f"`{parse_float(row.get('same_window_return_vs_spy200d_frozen_control')):.6f}`"
        )
    lines.append("")
    lines.append("Static all-weather remains benchmark/control only and is not converted into candidate status.")
    lines.append("The 80/20 combo-plus-global row remains portfolio-contribution context only.")
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


def role_label_summary_md(manifest: dict[str, Any], role_summary: list[dict[str, Any]]) -> str:
    role_lines = [
        f"- `{row['variant_role']}`: rows `{row['row_count']}`, pass `{row['numeric_pass_count']}`, fail `{row['numeric_fail_count']}`"
        for row in role_summary
    ]
    label_lines = [f"- `{label}`: `{manifest[f'{label}_count']}`" for label in sorted(ALLOWED_LABELS)]
    return "# Role / Label Summary\n\nRoles:\n\n" + "\n".join(role_lines) + "\n\nLabels:\n\n" + "\n".join(label_lines) + "\n"


def source_lineage_md(manifest: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    source_rows = [
        f"- `{row['variant_id']}` uses source registry ID `{row['source_registry_id']}` with context status `{row['source_context_status']}`."
        for row in rows
    ]
    return f"""# Source Lineage / Context Report

Source exploratory evidence exists: `{manifest['source_exploratory_context_exists']}`

Source exploratory evidence context only: `{manifest['source_exploratory_context_only']}`

Source metrics reused as current performance proof: `{manifest['source_metrics_reused_as_current_performance_proof']}`

{chr(10).join(source_rows)}

This run recomputes current diagnostics from local cache. Older exploratory evidence is lineage context only and does not create promotion, candidate_exhaustive, or paper-forward eligibility.
"""


def do_not_promote_md() -> str:
    return """# Do Not Promote From Global Multi-Asset Bounded Run

This run is diagnostic historical research evidence only.

It creates no promotion-review candidate, candidate_exhaustive candidate, paper-forward candidate, paper-forward activation, broker/live action, or real-money recommendation.
"""


def next_action_md(next_action: str) -> str:
    return f"""# Global Multi-Asset Bounded Run Next Action

Exact next action:

`{next_action}`

Do not execute the next action in this task.
"""


def consistency_check(manifest: dict[str, Any], rows: list[dict[str, Any]], output: Path) -> dict[str, Any]:
    required = {name: (output / name).exists() for name in REQUIRED_FILES}
    required["global_multi_asset_bounded_run_consistency_check.json"] = True
    labels = {row.get("research_only_label", "") for row in rows}
    roles = {row.get("variant_role", "") for row in rows}
    checks = {
        "correct_lane_id": manifest["lane_id"] == LANE_ID,
        "correct_family_id": manifest["family_id"] == FAMILY_ID,
        "source_design_run_ready": manifest["source_design_run_ready"] is True,
        "source_design_next_action_correct": manifest["source_design_next_action_correct"] is True,
        "variant_count_exact_6": manifest["variant_count_evaluated"] == EXPECTED_ROW_COUNT,
        "role_separation_preserved": roles
        == {
            "selected_confirmation",
            "uncontrolled_source_baseline_context",
            "portfolio_contribution_context",
            "comparator_control",
            "cash_control",
            "commodity_real_asset_control",
        },
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
        "no_leverage_or_derivatives": manifest["leverage_allowed"] is False
        and manifest["shorting_allowed"] is False
        and manifest["options_allowed"] is False
        and manifest["direct_futures_allowed"] is False
        and manifest["margin_allowed"] is False
        and manifest["forex_allowed"] is False,
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
        "other_tracks_not_continued": manifest["high_return_tactical_continued"] is False
        and manifest["commodity_continued"] is False
        and manifest["macro_gld_continued"] is False
        and manifest["volatility_throttle_continued"] is False
        and manifest["managed_futures_reopened"] is False
        and manifest["crypto_continued"] is False
        and manifest["regional_momentum_continued"] is False,
        "source_metrics_not_reused": manifest["source_metrics_reused_as_current_performance_proof"] is False,
        "allowed_labels_only": labels.issubset(ALLOWED_LABELS),
        "all_rows_non_promotable": all(row.get("promotion_eligibility") is False for row in rows),
        "all_rows_not_paper": all(row.get("paper_forward_eligibility") is False for row in rows),
        "all_rows_not_candidate_exhaustive": all(row.get("candidate_exhaustive_eligibility") is False for row in rows),
        "max_daily_exposure_lte_1": manifest["max_daily_exposure"] <= 1.000001,
        "max_daily_weight_sum_lte_1": manifest["max_daily_weight_sum"] <= 1.000001,
        "exposure_invariant_passed": manifest["exposure_invariant_passed"] is True,
        "row_results_exist": (output / "global_multi_asset_bounded_row_results.csv").exists(),
        "criteria_results_exist": (output / "global_multi_asset_bounded_numeric_criteria_results.csv").exists(),
        "alignment_report_exists": (output / "data_alignment_effective_window_report.md").exists(),
        "symbol_coverage_report_exists": (output / "symbol_coverage_report.md").exists(),
        "baseline_report_exists": (output / "baseline_comparator_report.md").exists(),
        "source_lineage_report_exists": (output / "source_lineage_context_report.md").exists(),
        "do_not_promote_exists": (output / "do_not_promote_from_global_multi_asset_bounded_run.md").exists(),
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
    role_summary = pass_fail_summary(rows, "variant_role")
    coverage = symbol_coverage_rows(root, rows)

    write_json(output / "global_multi_asset_bounded_run_manifest.json", manifest)
    write_csv(output / "global_multi_asset_bounded_row_results.csv", rows, list(RESULT_FIELDS))
    write_csv(output / "global_multi_asset_bounded_numeric_criteria_results.csv", criteria, list(CRITERIA_FIELDS))
    write_csv(output / "data_alignment_effective_window_report.csv", alignments, list(ALIGNMENT_FIELDS))
    write_text(output / "data_alignment_effective_window_report.md", alignment_md(alignments))
    write_csv(output / "symbol_coverage_report.csv", coverage, list(coverage[0].keys()) if coverage else [])
    write_text(output / "symbol_coverage_report.md", coverage_md(coverage))
    write_csv(output / "baseline_comparator_report.csv", baseline_rows, list(BASELINE_FIELDS))
    write_text(output / "baseline_comparator_report.md", baseline_md(rows))
    write_csv(output / "global_multi_asset_bounded_concept_summary.csv", concept_summary, list(concept_summary[0].keys()) if concept_summary else [])
    write_csv(output / "global_multi_asset_bounded_role_summary.csv", role_summary, list(role_summary[0].keys()) if role_summary else [])
    write_text(output / "exposure_invariant_report.md", invariant_md(manifest, rows))
    write_text(output / "role_label_summary.md", role_label_summary_md(manifest, role_summary))
    write_text(output / "source_lineage_context_report.md", source_lineage_md(manifest, rows))
    write_text(output / "global_multi_asset_bounded_run_summary.md", summary_md(manifest, concept_summary, role_summary, alignments, rows))
    write_text(output / "do_not_promote_from_global_multi_asset_bounded_run.md", do_not_promote_md())
    write_text(output / "global_multi_asset_bounded_run_next_action.md", next_action_md(manifest["next_action"]))
    check = consistency_check(manifest, rows, output)
    write_json(output / "global_multi_asset_bounded_run_consistency_check.json", check)
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
