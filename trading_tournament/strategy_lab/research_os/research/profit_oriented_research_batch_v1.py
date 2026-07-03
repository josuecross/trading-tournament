from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import DATA_CACHE_DIR, ROOT
from strategy_lab.research_os.objective_reset.objective_reset_review import replace_or_append_section, write_json, write_text
from strategy_lab.research_os.operations.observation_checkpoint import DSR_ID, VM_ID
from strategy_lab.research_os.split_tracks import ACTIVE_OBSERVATIONS_PATH, OPERATIONS_STATE_PATH, RESEARCH_STATE_PATH


OBSERVATION_OUTPUT_DIR = (
    Path("evidence") / "operations_observation" / "observation_loop_delegated_to_alpaca_module" / "latest"
)
RESEARCH_OUTPUT_DIR = Path("evidence") / "research_recovery" / "profit_oriented_research_batch_v1" / "latest"
FAMILY_LEDGER_PATH = Path("strategy_lab") / "research_os" / "family_lineage" / "family_ledger.yaml"
ACTIVE_COMBO_EQUITY_PATH = Path("evidence") / "active_combo_benchmark" / "latest" / "active_combo_equity_series.csv"
STATIC_ALL_WEATHER_ID = "static_all_weather_benchmark_v1"

BATCH_ID = "profit_oriented_research_batch_v1"
TRACK_ID = "profit_oriented_research_track_v1"
WEIGHT_TOLERANCE = 1e-6
SEVERE_DRAWDOWN_THRESHOLD = -0.35
EXTREME_DRAWDOWN_THRESHOLD = -0.50
HIGH_RETURN_CAGR_THRESHOLD = 0.08
NEAR_ZERO_DRAWDOWN_TOLERANCE_THRESHOLD = 5.0
DIVERSIFIER_SCORE_THRESHOLD = 58.0
DIVERSIFIER_CORRELATION_THRESHOLD = 0.80

NEXT_ACTION_AUDIT = "audit_profit_oriented_research_batch_v1"
NEXT_ACTION_BATCH2 = "design_profit_oriented_research_batch_v2"
NEXT_ACTION_GLD = "recover_gld_macro_family_lineage"
NEXT_ACTION_FIX = "fix_research_batch_v1_methodology_issue"
NEXT_ACTION_PAUSE = "pause_expansion_and_wait_for_manual_direction"
VALID_NEXT_ACTIONS = {NEXT_ACTION_AUDIT, NEXT_ACTION_BATCH2, NEXT_ACTION_GLD, NEXT_ACTION_FIX, NEXT_ACTION_PAUSE}

ALLOWED_LABELS = {
    "research_signal_promising",
    "research_signal_high_risk",
    "research_signal_risk_control_required",
    "research_signal_high_risk_diversifier",
    "research_signal_diversifier",
    "research_signal_needs_robustness",
    "research_signal_weak",
    "research_signal_data_blocked",
    "research_signal_duplicate",
    "research_signal_rejected",
    "research_signal_lineage_blocked",
}
FORBIDDEN_LABELS = {
    "promotion_review_candidate",
    "candidate_exhaustive_candidate",
    "paper_forward_candidate",
    "live_ready",
    "demo_active_new",
    "real_money_candidate",
}

OBSERVATION_REQUIRED_FILES = (
    "observation_delegation_manifest.json",
    "observation_delegation_summary.md",
    "alpaca_execution_module_boundary.md",
    "manual_snapshot_loop_status.md",
    "operations_research_boundary.md",
    "observation_delegation_next_action.md",
)

RESEARCH_REQUIRED_FILES = (
    "profit_research_batch_manifest.json",
    "profit_research_batch_summary.md",
    "local_cache_inventory.md",
    "research_track_policy_v1.md",
    "family_selection_rationale.md",
    "profit_research_variant_results.csv",
    "profit_research_family_summary.csv",
    "profit_research_family_summary.md",
    "high_profit_high_risk_signals.md",
    "portfolio_diversifier_signals.md",
    "gld_macro_lineage_status.md",
    "false_negative_recovery_review.md",
    "methodology_notes.md",
    "do_not_promote_from_profit_research_batch_v1.md",
    "profit_research_batch_next_action.md",
    "profit_research_batch_consistency_check.json",
)

MANIFEST_FLAGS = {
    "profit_oriented_research_batch": True,
    "batch_id": BATCH_ID,
    "historical_research_only": True,
    "uses_local_cache_only": True,
    "provider_download": False,
    "intraday_data_used": False,
    "broker_api_called": False,
    "broker_orders_submitted": False,
    "broker_orders_cancelled": False,
    "broker_orders_reconciled": False,
    "live_orders": False,
    "real_money_recommendation": False,
    "new_paper_forward_candidate_created": False,
    "paper_forward_activation": False,
    "candidate_exhaustive_run": False,
    "promotion_candidates_created": False,
    "best_single_variant_promoted": False,
    "manual_observation_loop_blocking_research": False,
    "alpaca_execution_module_delegated": True,
    "active_vm_preserved": True,
    "active_dsr_preserved": True,
    "static_all_weather_benchmark_control_only": True,
    "exact_rejected_variants_reopened_without_new_hypothesis": False,
    "old_dollar_target_is_hard_gate": False,
    "low_drawdown_is_hard_discovery_gate": False,
    "research_outputs_non_promotable": True,
}


@dataclass(frozen=True)
class Variant:
    family_id: str
    variant_id: str
    strategy_type: str
    universe: tuple[str, ...]
    params: dict[str, Any]
    rule_summary: str
    parameter_sensitivity_group: str


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False, width=120, allow_unicode=False), encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: csv_value(row.get(field, "")) for field in fieldnames})


def csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return ""
    if isinstance(value, (list, tuple)):
        return "|".join(str(v) for v in value)
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True)
    return str(value)


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    if math.isnan(value) or math.isinf(value):
        return 0.0
    return max(low, min(high, value))


def scaled(value: float, low: float, high: float) -> float:
    if math.isnan(value) or math.isinf(value) or high == low:
        return 0.0
    return clamp(100.0 * (value - low) / (high - low))


def cache_inventory(root: Path) -> list[dict[str, Any]]:
    rows = []
    cache_dir = root / DATA_CACHE_DIR
    for path in sorted(cache_dir.glob("*.csv")):
        symbol = path.stem.upper()
        try:
            df = pd.read_csv(path, usecols=lambda c: c in {"date", "adj_close", "close", "symbol"})
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
            price_col = "adj_close" if "adj_close" in df.columns else "close"
            prices = pd.to_numeric(df[price_col], errors="coerce")
            valid = df[df["date"].notna() & prices.notna()]
            rows.append(
                {
                    "symbol": symbol,
                    "path": str(path.resolve()),
                    "rows": int(len(valid)),
                    "first_date": valid["date"].min().date().isoformat() if not valid.empty else "",
                    "last_date": valid["date"].max().date().isoformat() if not valid.empty else "",
                    "has_adj_close": "adj_close" in df.columns,
                    "status": "cache_ready" if len(valid) >= 252 else "cache_short_or_invalid",
                }
            )
        except Exception as exc:  # pragma: no cover - defensive for malformed local files.
            rows.append(
                {
                    "symbol": symbol,
                    "path": str(path.resolve()),
                    "rows": 0,
                    "first_date": "",
                    "last_date": "",
                    "has_adj_close": False,
                    "status": f"cache_error:{exc}",
                }
            )
    return rows


def inventory_symbols(inventory: list[dict[str, Any]]) -> set[str]:
    return {str(row["symbol"]) for row in inventory if row.get("status") == "cache_ready"}


def load_price_series(root: Path, symbol: str) -> pd.Series:
    path = root / DATA_CACHE_DIR / f"{symbol}.csv"
    if not path.exists():
        return pd.Series(dtype=float, name=symbol)
    df = pd.read_csv(path)
    if "date" not in df.columns:
        return pd.Series(dtype=float, name=symbol)
    price_col = "adj_close" if "adj_close" in df.columns else "close"
    if price_col not in df.columns:
        return pd.Series(dtype=float, name=symbol)
    dates = pd.to_datetime(df["date"], errors="coerce")
    prices = pd.to_numeric(df[price_col], errors="coerce")
    series = pd.Series(prices.to_numpy(), index=dates, name=symbol).dropna()
    series = series[~series.index.isna()].sort_index()
    series = series[~series.index.duplicated(keep="last")]
    return series


def load_prices(root: Path, symbols: tuple[str, ...]) -> pd.DataFrame:
    series = [load_price_series(root, symbol) for symbol in symbols]
    series = [s for s in series if not s.empty]
    if not series:
        return pd.DataFrame()
    return pd.concat(series, axis=1, sort=False).sort_index()


def month_rebalance_mask(index: pd.DatetimeIndex) -> pd.Series:
    month = pd.Series(index.to_period("M"), index=index)
    return month.ne(month.shift(1)).fillna(True)


def complete_rebalance_weight_frame(
    index: pd.DatetimeIndex,
    columns: list[str],
    rebalance_targets: dict[pd.Timestamp, dict[str, float]],
    *,
    tolerance: float = WEIGHT_TOLERANCE,
) -> pd.DataFrame:
    weights = pd.DataFrame(np.nan, index=index, columns=columns, dtype=float)
    for raw_date, target in rebalance_targets.items():
        date = pd.Timestamp(raw_date)
        if date not in weights.index:
            continue
        row = pd.Series(0.0, index=columns, dtype=float)
        for symbol, value in target.items():
            if symbol in row.index:
                row[symbol] = float(value)
        row_sum = float(row.sum())
        if row.isna().any():
            raise ValueError(f"rebalance target contains NaN weights for {date.date()}")
        if float(row.min()) < -tolerance:
            raise ValueError(f"rebalance target contains negative weights for {date.date()}")
        if row_sum > 1.0 + tolerance:
            raise ValueError(f"rebalance target exceeds 100% allocation for {date.date()}: {row_sum:.6f}")
        weights.loc[date] = row
    weights = weights.ffill().fillna(0.0)
    assert_weight_invariants(weights, tolerance=tolerance)
    return weights


def assert_weight_invariants(weights: pd.DataFrame, *, tolerance: float = WEIGHT_TOLERANCE) -> None:
    if weights.empty:
        return
    sums = weights.sum(axis=1)
    if int(weights.isna().sum().sum()) > 0:
        raise ValueError("weight matrix contains NaN values after final fill")
    if float(weights.min().min()) < -tolerance:
        raise ValueError("weight matrix contains negative weights")
    if float(sums.max()) > 1.0 + tolerance:
        raise ValueError(f"weight matrix exceeds 100% allocation: {float(sums.max()):.6f}")
    if "BIL" in weights.columns:
        risky = weights.drop(columns=["BIL"]).sum(axis=1)
        impossible = (weights["BIL"] >= 1.0 - tolerance) & (risky > tolerance)
        if bool(impossible.any()):
            raise ValueError("BIL/cash fallback is additive with risky exposure")


def weight_invariant_report(weights: pd.DataFrame, *, tolerance: float = WEIGHT_TOLERANCE) -> dict[str, Any]:
    if weights.empty:
        return {
            "max_daily_weight_sum": 0.0,
            "average_weight_sum": 0.0,
            "max_daily_exposure": 0.0,
            "weight_sum_violation_count": 0,
            "negative_weight_violation_count": 0,
            "nan_weight_count": 0,
            "impossible_cash_and_risky_exposure_days": 0,
        }
    sums = weights.sum(axis=1)
    exposure_cols = [col for col in weights.columns if col != "BIL"]
    risky = weights[exposure_cols].sum(axis=1) if exposure_cols else pd.Series(0.0, index=weights.index)
    cash = weights["BIL"] if "BIL" in weights.columns else pd.Series(0.0, index=weights.index)
    return {
        "max_daily_weight_sum": float(sums.max()),
        "average_weight_sum": float(sums.mean()),
        "max_daily_exposure": float(risky.max()),
        "weight_sum_violation_count": int((sums > 1.0 + tolerance).sum()),
        "negative_weight_violation_count": int((weights < -tolerance).sum().sum()),
        "nan_weight_count": int(weights.isna().sum().sum()),
        "impossible_cash_and_risky_exposure_days": int(((cash >= 1.0 - tolerance) & (risky > tolerance)).sum()),
    }


def backtest_momentum(root: Path, variant: Variant) -> tuple[pd.Series, pd.DataFrame]:
    prices = load_prices(root, variant.universe)
    if prices.empty or len(prices.dropna(how="all")) < 252:
        return pd.Series(dtype=float), pd.DataFrame()
    prices = prices.ffill()
    returns = prices.pct_change(fill_method=None).fillna(0.0)
    lookback = int(variant.params.get("lookback", 126))
    top_n = int(variant.params.get("top_n", 1))
    trend_filter = bool(variant.params.get("trend_filter", False))
    cash_symbol = "BIL" if "BIL" in prices.columns else None
    scores = prices.pct_change(lookback, fill_method=None).shift(1)
    trend = prices.shift(1) > prices.shift(1).rolling(200, min_periods=100).mean()
    rebalance_targets: dict[pd.Timestamp, dict[str, float]] = {}
    for date in prices.index[month_rebalance_mask(prices.index)]:
        score = scores.loc[date].dropna()
        if trend_filter:
            score = score[trend.loc[date].reindex(score.index).fillna(False)]
        if cash_symbol and cash_symbol in score.index:
            score = score.drop(cash_symbol, errors="ignore")
        selected = list(score.sort_values(ascending=False).head(top_n).index)
        target = {symbol: 0.0 for symbol in prices.columns}
        if selected:
            selected_weight = 1.0 / len(selected)
            for symbol in selected:
                target[symbol] = selected_weight
        elif cash_symbol:
            target[cash_symbol] = 1.0
        rebalance_targets[pd.Timestamp(date)] = target
    weights = complete_rebalance_weight_frame(prices.index, list(prices.columns), rebalance_targets)
    daily = (weights.shift(1).fillna(0.0) * returns).sum(axis=1)
    return daily, weights


def backtest_static(root: Path, variant: Variant) -> tuple[pd.Series, pd.DataFrame]:
    prices = load_prices(root, variant.universe)
    if prices.empty or len(prices.dropna(how="all")) < 252:
        return pd.Series(dtype=float), pd.DataFrame()
    prices = prices.ffill()
    returns = prices.pct_change(fill_method=None).fillna(0.0)
    raw_weights = variant.params.get("weights", {})
    columns = list(prices.columns)
    weights = pd.DataFrame(0.0, index=prices.index, columns=columns)
    if raw_weights:
        total = sum(float(raw_weights.get(symbol, 0.0)) for symbol in columns)
        for symbol in columns:
            weights[symbol] = float(raw_weights.get(symbol, 0.0)) / total if total else 0.0
    else:
        for symbol in columns:
            weights[symbol] = 1.0 / len(columns)
    assert_weight_invariants(weights)
    daily = (weights.shift(1).fillna(0.0) * returns).sum(axis=1)
    return daily, weights


def backtest_breakout(root: Path, variant: Variant) -> tuple[pd.Series, pd.DataFrame]:
    symbol = variant.universe[0]
    cash_symbol = "BIL"
    prices = load_prices(root, (symbol, cash_symbol))
    if symbol not in prices.columns or len(prices[symbol].dropna()) < 252:
        return pd.Series(dtype=float), pd.DataFrame()
    prices = prices.ffill()
    asset = prices[symbol]
    returns = prices.pct_change(fill_method=None).fillna(0.0)
    lookback = int(variant.params.get("breakout_lookback", 55))
    exit_sma = int(variant.params.get("exit_sma", 100))
    prior_high = asset.shift(2).rolling(lookback, min_periods=max(20, lookback // 2)).max()
    sma = asset.shift(1).rolling(exit_sma, min_periods=max(20, exit_sma // 2)).mean()
    exposure = ((asset.shift(1) > prior_high) & (asset.shift(1) > sma)).astype(float)
    weights = pd.DataFrame(0.0, index=prices.index, columns=prices.columns)
    weights[symbol] = exposure
    if cash_symbol in weights.columns:
        weights[cash_symbol] = 1.0 - exposure
    assert_weight_invariants(weights)
    daily = (weights * returns).sum(axis=1)
    return daily, weights


def backtest_variant(root: Path, variant: Variant) -> tuple[pd.Series, pd.DataFrame]:
    if variant.strategy_type == "monthly_momentum":
        return backtest_momentum(root, variant)
    if variant.strategy_type == "static_sleeve":
        return backtest_static(root, variant)
    if variant.strategy_type == "breakout":
        return backtest_breakout(root, variant)
    return pd.Series(dtype=float), pd.DataFrame()


def equity_curve(returns: pd.Series, starting: float = 1.0) -> pd.Series:
    returns = returns.dropna()
    if returns.empty:
        return pd.Series(dtype=float)
    return starting * (1.0 + returns).cumprod()


def max_drawdown(equity: pd.Series) -> float:
    if equity.empty:
        return float("nan")
    return float((equity / equity.cummax() - 1.0).min())


def rolling_window_stats(equity: pd.Series, window: int = 180) -> dict[str, float]:
    if len(equity) <= window:
        return {"worst_180d_window": float("nan"), "best_180d_window": float("nan"), "positive_180d_window_ratio": float("nan")}
    returns = equity / equity.shift(window) - 1.0
    returns = returns.dropna()
    return {
        "worst_180d_window": float(returns.min()) if not returns.empty else float("nan"),
        "best_180d_window": float(returns.max()) if not returns.empty else float("nan"),
        "positive_180d_window_ratio": float((returns > 0).mean()) if not returns.empty else float("nan"),
    }


def trade_count_and_turnover(weights: pd.DataFrame) -> tuple[int, float]:
    if weights.empty:
        return 0, 0.0
    diff = weights.diff().abs().fillna(weights.abs())
    trade_count = int((diff.sum(axis=1) > 1e-6).sum())
    years = max((weights.index.max() - weights.index.min()).days / 365.25, 1e-9)
    turnover_proxy = float(diff.sum(axis=1).sum() / (2.0 * years))
    return trade_count, turnover_proxy


def active_combo_returns(root: Path) -> pd.Series:
    path = root / ACTIVE_COMBO_EQUITY_PATH
    if not path.exists():
        return pd.Series(dtype=float, name="active_combo")
    df = pd.read_csv(path)
    if "date" not in df.columns:
        return pd.Series(dtype=float, name="active_combo")
    dates = pd.to_datetime(df["date"], errors="coerce")
    if "active_combo_daily_return" in df.columns:
        returns = pd.to_numeric(df["active_combo_daily_return"], errors="coerce")
    elif "active_combo_equity" in df.columns:
        returns = pd.to_numeric(df["active_combo_equity"], errors="coerce").pct_change(fill_method=None)
    else:
        return pd.Series(dtype=float, name="active_combo")
    return pd.Series(returns.to_numpy(), index=dates, name="active_combo").dropna().sort_index()


def benchmark_returns(root: Path, symbol: str) -> pd.Series:
    prices = load_price_series(root, symbol)
    return prices.pct_change(fill_method=None).dropna().rename(symbol)


def contribution_metrics(strategy_returns: pd.Series, active_returns: pd.Series) -> dict[str, float]:
    if strategy_returns.empty or active_returns.empty:
        return {
            "active_combo_correlation": float("nan"),
            "active_combo_blend_total_return_delta": float("nan"),
            "active_combo_blend_drawdown_delta": float("nan"),
        }
    aligned = pd.concat(
        [strategy_returns.rename("strategy"), active_returns.rename("active_combo")], axis=1, sort=False
    ).dropna()
    if len(aligned) < 252:
        return {
            "active_combo_correlation": float("nan"),
            "active_combo_blend_total_return_delta": float("nan"),
            "active_combo_blend_drawdown_delta": float("nan"),
        }
    blend = 0.8 * aligned["active_combo"] + 0.2 * aligned["strategy"]
    active_eq = equity_curve(aligned["active_combo"])
    blend_eq = equity_curve(blend)
    active_total = float(active_eq.iloc[-1] - 1.0)
    blend_total = float(blend_eq.iloc[-1] - 1.0)
    return {
        "active_combo_correlation": float(aligned["strategy"].corr(aligned["active_combo"])),
        "active_combo_blend_total_return_delta": blend_total - active_total,
        "active_combo_blend_drawdown_delta": max_drawdown(blend_eq) - max_drawdown(active_eq),
    }


def evaluate_variant(root: Path, variant: Variant, available_symbols: set[str], active_returns: pd.Series) -> dict[str, Any]:
    missing = [symbol for symbol in variant.universe if symbol not in available_symbols]
    base = {
        "batch_id": BATCH_ID,
        "family_id": variant.family_id,
        "variant_id": variant.variant_id,
        "universe": list(variant.universe),
        "rule_summary": variant.rule_summary,
        "parameter_sensitivity_group": variant.parameter_sensitivity_group,
        "promotion_eligibility": False,
        "paper_forward_eligibility": False,
    }
    if missing:
        return {
            **base,
            "data_availability_status": "research_signal_data_blocked",
            "missing_symbols": missing,
            "research_label": "research_signal_data_blocked",
            "promotion_eligibility_score": 0.0,
        }

    daily, weights = backtest_variant(root, variant)
    if daily.empty or weights.empty or len(daily.dropna()) < 252:
        return {
            **base,
            "data_availability_status": "research_signal_data_blocked",
            "missing_symbols": [],
            "research_label": "research_signal_data_blocked",
            "promotion_eligibility_score": 0.0,
        }

    daily = daily.dropna()
    eq = equity_curve(daily)
    years = max((daily.index.max() - daily.index.min()).days / 365.25, 1e-9)
    total_return = float(eq.iloc[-1] - 1.0)
    cagr = float(eq.iloc[-1] ** (1.0 / years) - 1.0)
    volatility = float(daily.std() * np.sqrt(252.0))
    mdd = max_drawdown(eq)
    calmar = float(cagr / abs(mdd)) if mdd < 0 else float("nan")
    trades, turnover = trade_count_and_turnover(weights)
    exposure_cols = [col for col in weights.columns if col != "BIL"]
    avg_exposure = float(weights[exposure_cols].sum(axis=1).mean()) if exposure_cols else 0.0
    cash_bil_share = float(weights["BIL"].mean()) if "BIL" in weights.columns else max(0.0, 1.0 - avg_exposure)
    invariant = weight_invariant_report(weights)
    rolling = rolling_window_stats(eq)

    spy_returns = benchmark_returns(root, "SPY")
    bil_returns = benchmark_returns(root, "BIL")
    spy_delta = benchmark_delta(daily, spy_returns)
    bil_delta = benchmark_delta(daily, bil_returns)
    contrib = contribution_metrics(daily, active_returns)

    historical_profit_score = scaled(cagr, -0.05, 0.25)
    risk_adjusted_score = scaled(calmar if not math.isnan(calmar) else -0.5, -0.5, 2.5)
    drawdown_tolerance_score = clamp(100.0 * (1.0 + mdd / 0.45)) if not math.isnan(mdd) else 0.0
    contribution_score = portfolio_contribution_score(contrib)
    practicality_score = implementation_practicality_score(trades, turnover, years, avg_exposure)
    research_interest_score = max(
        0.55 * historical_profit_score + 0.25 * risk_adjusted_score + 0.20 * practicality_score,
        0.60 * contribution_score + 0.20 * drawdown_tolerance_score + 0.20 * practicality_score,
    )

    row = {
        **base,
        "data_availability_status": "cache_ready",
        "missing_symbols": [],
        "start_date": daily.index.min().date().isoformat(),
        "end_date": daily.index.max().date().isoformat(),
        "total_return": total_return,
        "cagr": cagr,
        "max_drawdown": mdd,
        "volatility": volatility,
        "calmar_or_return_drawdown_proxy": calmar,
        "benchmark_comparison": "same-window local-cache comparison",
        "spy_total_return_delta": spy_delta,
        "bil_cash_total_return_delta": bil_delta,
        "active_vm_dsr_contribution_comparison": "active_combo_80_20_blend_proxy",
        "active_combo_correlation": contrib["active_combo_correlation"],
        "active_combo_blend_total_return_delta": contrib["active_combo_blend_total_return_delta"],
        "active_combo_blend_drawdown_delta": contrib["active_combo_blend_drawdown_delta"],
        "trade_count": trades,
        "turnover_proxy": turnover,
        "average_exposure": avg_exposure,
        "cash_bil_allocation_share": cash_bil_share,
        "max_daily_exposure": invariant["max_daily_exposure"],
        "max_daily_weight_sum": invariant["max_daily_weight_sum"],
        "average_weight_sum": invariant["average_weight_sum"],
        "weight_sum_violation_count": invariant["weight_sum_violation_count"],
        "negative_weight_violation_count": invariant["negative_weight_violation_count"],
        "nan_weight_count": invariant["nan_weight_count"],
        "impossible_cash_and_risky_exposure_days": invariant["impossible_cash_and_risky_exposure_days"],
        "worst_180_day_window": rolling["worst_180d_window"],
        "best_180_day_window": rolling["best_180d_window"],
        "positive_180_day_window_ratio": rolling["positive_180d_window_ratio"],
        "regime_notes": regime_notes(cagr, mdd, contribution_score, cash_bil_share),
        "historical_profit_score": historical_profit_score,
        "risk_adjusted_score": risk_adjusted_score,
        "drawdown_tolerance_score": drawdown_tolerance_score,
        "robustness_score": 50.0,
        "portfolio_contribution_score": contribution_score,
        "implementation_practicality_score": practicality_score,
        "research_interest_score": research_interest_score,
        "promotion_eligibility_score": 0.0,
    }
    if variant.family_id == "macro_gld_duration_risk_off":
        row["lineage_status"] = "lineage_incomplete_research_only"
    else:
        row["lineage_status"] = "lineage_not_blocking_research_batch"
    row["research_label"] = label_row(row)
    return row


def benchmark_delta(strategy_returns: pd.Series, benchmark: pd.Series) -> float:
    aligned = pd.concat([strategy_returns.rename("strategy"), benchmark.rename("benchmark")], axis=1, sort=False).dropna()
    if len(aligned) < 252:
        return float("nan")
    return float(equity_curve(aligned["strategy"]).iloc[-1] - equity_curve(aligned["benchmark"]).iloc[-1])


def portfolio_contribution_score(contrib: dict[str, float]) -> float:
    corr = contrib.get("active_combo_correlation", float("nan"))
    total_delta = contrib.get("active_combo_blend_total_return_delta", float("nan"))
    dd_delta = contrib.get("active_combo_blend_drawdown_delta", float("nan"))
    if math.isnan(corr) or math.isnan(total_delta) or math.isnan(dd_delta):
        return 0.0
    corr_score = scaled(0.85 - corr, -0.15, 0.85)
    return_score = scaled(total_delta, -0.05, 0.12)
    dd_score = scaled(dd_delta, -0.08, 0.08)
    return clamp(0.35 * corr_score + 0.35 * return_score + 0.30 * dd_score)


def implementation_practicality_score(trade_count: int, turnover: float, years: float, avg_exposure: float) -> float:
    trade_score = clamp(100.0 - max(0.0, trade_count / max(years, 1.0) - 18.0) * 3.0)
    turnover_score = clamp(100.0 - max(0.0, turnover - 6.0) * 8.0)
    history_score = scaled(years, 2.0, 12.0)
    exposure_score = 100.0 if avg_exposure >= 0.25 else 55.0
    return clamp(0.30 * trade_score + 0.25 * turnover_score + 0.25 * history_score + 0.20 * exposure_score)


def regime_notes(cagr: float, mdd: float, contribution_score: float, cash_share: float) -> str:
    notes = []
    if cagr > 0.12 and mdd < -0.25:
        notes.append("high_return_high_drawdown")
    if contribution_score > 55:
        notes.append("portfolio_contribution_candidate_for_research")
    if cash_share > 0.45:
        notes.append("cash_or_bil_heavy")
    if not notes:
        notes.append("ordinary_historical_profile")
    return ";".join(notes)


def label_row(row: dict[str, Any]) -> str:
    cagr = float(row.get("cagr", 0.0) or 0.0)
    mdd = float(row.get("max_drawdown", 0.0) or 0.0)
    hist = float(row.get("historical_profit_score", 0.0) or 0.0)
    risk = float(row.get("risk_adjusted_score", 0.0) or 0.0)
    contrib = float(row.get("portfolio_contribution_score", 0.0) or 0.0)
    drawdown_tolerance = float(row.get("drawdown_tolerance_score", 0.0) or 0.0)
    active_combo_delta = float(row.get("active_combo_blend_total_return_delta", 0.0) or 0.0)
    active_combo_drawdown_delta = float(row.get("active_combo_blend_drawdown_delta", 0.0) or 0.0)
    lineage_status = str(row.get("lineage_status", ""))
    corr = row.get("active_combo_correlation", float("nan"))
    if isinstance(corr, str) or corr == "":
        corr = float("nan")
    severe_drawdown = mdd <= SEVERE_DRAWDOWN_THRESHOLD
    extreme_drawdown = mdd <= EXTREME_DRAWDOWN_THRESHOLD
    high_return = cagr >= HIGH_RETURN_CAGR_THRESHOLD
    near_zero_drawdown_tolerance = drawdown_tolerance <= NEAR_ZERO_DRAWDOWN_TOLERANCE_THRESHOLD
    contribution_evidence = (
        contrib >= DIVERSIFIER_SCORE_THRESHOLD
        and (math.isnan(float(corr)) or float(corr) < DIVERSIFIER_CORRELATION_THRESHOLD)
        and active_combo_delta > 0.0
        and active_combo_drawdown_delta > -0.03
    )
    if lineage_status == "lineage_incomplete_research_only" and (cagr > 0.03 or contrib >= 50):
        return "research_signal_lineage_blocked"
    if not math.isnan(float(corr)) and float(corr) > 0.92 and contrib < 45:
        return "research_signal_duplicate"
    if high_return and (extreme_drawdown or near_zero_drawdown_tolerance):
        return "research_signal_high_risk"
    if high_return and severe_drawdown:
        return "research_signal_high_risk_diversifier" if contribution_evidence else "research_signal_high_risk"
    if severe_drawdown or near_zero_drawdown_tolerance:
        return "research_signal_risk_control_required"
    if contribution_evidence:
        return "research_signal_diversifier"
    if hist >= 62 and risk >= 45:
        return "research_signal_promising"
    if cagr > 0.07 and risk < 35:
        return "research_signal_needs_robustness"
    if cagr < 0.0 and mdd < -0.30:
        return "research_signal_rejected"
    return "research_signal_weak"


def apply_robustness(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    df = pd.DataFrame(rows)
    if df.empty or "historical_profit_score" not in df.columns:
        return rows
    for (family, group), idx in df.groupby(["family_id", "parameter_sensitivity_group"]).groups.items():
        subset = df.loc[idx]
        if len(subset) < 2:
            score = 35.0
        else:
            dispersion = float(pd.to_numeric(subset["historical_profit_score"], errors="coerce").std(skipna=True) or 0.0)
            positive_ratio = float((pd.to_numeric(subset["cagr"], errors="coerce") > 0.0).mean())
            score = clamp(70.0 - dispersion + 30.0 * positive_ratio)
        for row_index in idx:
            rows[int(row_index)]["robustness_score"] = score
            if rows[int(row_index)]["research_label"] == "research_signal_weak" and score < 40 and float(
                rows[int(row_index)].get("historical_profit_score", 0.0) or 0.0
            ) > 55:
                rows[int(row_index)]["research_label"] = "research_signal_needs_robustness"
    return rows


def build_variant_plan() -> list[Variant]:
    variants: list[Variant] = []

    equity_universes = {
        "equity_growth_core": ("SPY", "QQQ", "IWM", "DIA", "XLK", "SCHG", "MTUM", "BIL"),
        "equity_sector_growth": ("XLK", "XLY", "XLF", "XLE", "XLV", "XLI", "BIL"),
    }
    for universe_name, universe in equity_universes.items():
        for lookback in (63, 126, 252):
            for top_n in (1, 2):
                variants.append(
                    Variant(
                        "high_return_tactical_etf_equity_index",
                        f"hrt_{universe_name}_mom{lookback}_top{top_n}",
                        "monthly_momentum",
                        universe,
                        {"lookback": lookback, "top_n": top_n, "trend_filter": False},
                        f"Monthly top-{top_n} {lookback}d momentum among high-beta ETF/index wrappers.",
                        f"{universe_name}_mom{lookback}",
                    )
                )

    macro_universe = ("SPY", "GLD", "TLT", "IEF", "AGG", "BIL")
    for lookback in (63, 126, 252):
        for top_n in (1, 2):
            variants.append(
                Variant(
                    "macro_gld_duration_risk_off",
                    f"mgd_macro_mom{lookback}_top{top_n}_trend",
                    "monthly_momentum",
                    macro_universe,
                    {"lookback": lookback, "top_n": top_n, "trend_filter": True},
                    f"Monthly top-{top_n} macro/risk-off ETF wrapper momentum with 200d trend filter.",
                    f"macro_mom{lookback}",
                )
            )
    for name, weights in {
        "spy_gld_tlt_60_20_20": {"SPY": 0.60, "GLD": 0.20, "TLT": 0.20},
        "gld_tlt_bil_equal": {"GLD": 1 / 3, "TLT": 1 / 3, "BIL": 1 / 3},
        "gld_ief_bil_equal": {"GLD": 1 / 3, "IEF": 1 / 3, "BIL": 1 / 3},
        "gld_spy_bil_equal": {"GLD": 1 / 3, "SPY": 1 / 3, "BIL": 1 / 3},
    }.items():
        variants.append(
            Variant(
                "macro_gld_duration_risk_off",
                f"mgd_static_{name}",
                "static_sleeve",
                tuple(weights.keys()),
                {"weights": weights},
                f"Static macro/risk-off wrapper sleeve: {name}.",
                "macro_static_sleeves",
            )
        )

    mf_universe = ("DBMF", "KMLM", "CTA", "FMF", "WTMF", "BIL")
    for lookback in (63, 126, 252):
        for top_n in (1, 2):
            variants.append(
                Variant(
                    "managed_futures_trend_following_etf_wrapper",
                    f"mftf_wrapper_mom{lookback}_top{top_n}",
                    "monthly_momentum",
                    mf_universe,
                    {"lookback": lookback, "top_n": top_n, "trend_filter": False},
                    f"Monthly top-{top_n} managed-futures ETF-wrapper momentum map.",
                    f"mftf_mom{lookback}",
                )
            )
    for name, weights in {
        "dbmf_kmlm_equal": {"DBMF": 0.50, "KMLM": 0.50},
        "cta_dbmf_kmlm_equal": {"CTA": 1 / 3, "DBMF": 1 / 3, "KMLM": 1 / 3},
        "managed_futures_bil_barbell": {"DBMF": 0.35, "KMLM": 0.35, "BIL": 0.30},
    }.items():
        variants.append(
            Variant(
                "managed_futures_trend_following_etf_wrapper",
                f"mftf_static_{name}",
                "static_sleeve",
                tuple(weights.keys()),
                {"weights": weights},
                f"Static managed-futures ETF-wrapper sleeve: {name}.",
                "mftf_static_sleeves",
            )
        )

    for symbol in ("QQQ", "SPY", "XLK", "IWM", "XLE", "GLD"):
        for lookback in (20, 55, 100):
            variants.append(
                Variant(
                    "breakout_trend_momentum_high_risk",
                    f"btm_{symbol.lower()}_donchian{lookback}",
                    "breakout",
                    (symbol, "BIL"),
                    {"breakout_lookback": lookback, "exit_sma": 100},
                    f"{symbol} prior-high breakout with 100d exit SMA and BIL fallback.",
                    f"breakout_{symbol}",
                )
            )

    diversifier_static = {
        "gld_tlt_bil": {"GLD": 0.40, "TLT": 0.40, "BIL": 0.20},
        "managed_futures_pair": {"DBMF": 0.50, "KMLM": 0.50},
        "defensive_lowvol_cash": {"USMV": 0.35, "SPLV": 0.35, "BIL": 0.30},
        "duration_credit_cash": {"IEF": 0.40, "AGG": 0.35, "BIL": 0.25},
        "gold_managed_futures_duration": {"GLD": 0.34, "DBMF": 0.33, "IEF": 0.33},
        "international_lowvol_cash": {"EFAV": 0.35, "EEMV": 0.35, "BIL": 0.30},
    }
    for name, weights in diversifier_static.items():
        variants.append(
            Variant(
                "portfolio_diversifier_contribution",
                f"pdc_static_{name}",
                "static_sleeve",
                tuple(weights.keys()),
                {"weights": weights},
                f"Static portfolio diversifier/contribution sleeve: {name}.",
                "pdc_static_sleeves",
            )
        )
    for lookback in (63, 126, 252):
        variants.append(
            Variant(
                "portfolio_diversifier_contribution",
                f"pdc_defensive_mom{lookback}_top2",
                "monthly_momentum",
                ("GLD", "TLT", "IEF", "AGG", "DBMF", "KMLM", "USMV", "SPLV", "BIL"),
                {"lookback": lookback, "top_n": 2, "trend_filter": False},
                f"Monthly top-2 diversified defensive sleeve momentum using {lookback}d lookback.",
                f"pdc_defensive_mom{lookback}",
            )
        )
    return variants


def evaluate_batch(root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    inventory = cache_inventory(root)
    available = inventory_symbols(inventory)
    active_returns = active_combo_returns(root)
    variants = build_variant_plan()
    rows = [evaluate_variant(root, variant, available, active_returns) for variant in variants]
    rows = apply_robustness(rows)
    families = family_summary(rows)
    return inventory, rows, families


def family_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not rows:
        return []
    df = pd.DataFrame(rows)
    summaries = []
    for family_id, group in df.groupby("family_id", sort=True):
        evaluated = group[group["research_label"] != "research_signal_data_blocked"].copy()
        if evaluated.empty:
            summaries.append(
                {
                    "family_id": family_id,
                    "variants_evaluated": 0,
                    "data_blocked_variants": int((group["research_label"] == "research_signal_data_blocked").sum()),
                    "family_research_status": "data_blocked",
                    "recommended_for_deeper_research": False,
                }
            )
            continue
        for col in (
            "historical_profit_score",
            "risk_adjusted_score",
            "portfolio_contribution_score",
            "research_interest_score",
            "cagr",
            "max_drawdown",
        ):
            evaluated[col] = pd.to_numeric(evaluated[col], errors="coerce")
        label_counts = evaluated["research_label"].value_counts().to_dict()
        deeper_count = sum(
            int(label_counts.get(label, 0))
            for label in ("research_signal_promising", "research_signal_high_risk", "research_signal_diversifier")
        )
        recommended = deeper_count >= 2 or int(label_counts.get("research_signal_promising", 0)) >= 1
        status = "deeper_research_worthy" if recommended else "research_context_only"
        if int(label_counts.get("research_signal_high_risk", 0)) > deeper_count / 2 and deeper_count:
            status = "high_profit_high_risk_map_only"
        summaries.append(
            {
                "family_id": family_id,
                "variants_evaluated": int(len(evaluated)),
                "data_blocked_variants": int((group["research_label"] == "research_signal_data_blocked").sum()),
                "best_variant_by_historical_profit": best_variant(evaluated, "historical_profit_score"),
                "best_variant_by_risk_adjusted_score": best_variant(evaluated, "risk_adjusted_score"),
                "best_variant_by_portfolio_contribution": best_variant(evaluated, "portfolio_contribution_score"),
                "median_cagr": float(evaluated["cagr"].median()),
                "median_max_drawdown": float(evaluated["max_drawdown"].median()),
                "median_historical_profit_score": float(evaluated["historical_profit_score"].median()),
                "median_risk_adjusted_score": float(evaluated["risk_adjusted_score"].median()),
                "median_portfolio_contribution_score": float(evaluated["portfolio_contribution_score"].median()),
                "robustness_across_variants": "broad" if deeper_count >= 3 else "limited_or_mixed",
                "risk_profile": family_risk_profile(evaluated),
                "evidence_broad_or_one_row": "broad" if deeper_count >= 3 else "not_one_row_promoted_but_evidence_mixed",
                "deserves_deeper_research": bool(recommended),
                "should_be_abandoned": bool(label_counts.get("research_signal_rejected", 0) >= len(evaluated) * 0.7),
                "needs_methodology_or_data_audit": family_id == "macro_gld_duration_risk_off",
                "family_research_status": status,
                "research_signal_promising_count": int(label_counts.get("research_signal_promising", 0)),
                "research_signal_high_risk_count": int(label_counts.get("research_signal_high_risk", 0)),
                "research_signal_diversifier_count": int(label_counts.get("research_signal_diversifier", 0)),
                "research_signal_weak_count": int(label_counts.get("research_signal_weak", 0)),
                "research_signal_duplicate_count": int(label_counts.get("research_signal_duplicate", 0)),
            }
        )
    return summaries


def best_variant(df: pd.DataFrame, column: str) -> str:
    if df.empty or column not in df.columns:
        return ""
    ordered = df.sort_values(column, ascending=False)
    return str(ordered.iloc[0]["variant_id"])


def family_risk_profile(df: pd.DataFrame) -> str:
    median_mdd = float(pd.to_numeric(df["max_drawdown"], errors="coerce").median())
    median_cagr = float(pd.to_numeric(df["cagr"], errors="coerce").median())
    if median_cagr > 0.10 and median_mdd < -0.25:
        return "high_return_high_drawdown"
    if median_mdd > -0.15:
        return "lower_drawdown"
    if median_cagr < 0.03:
        return "low_return_or_cash_heavy"
    return "mixed"


def observation_delegation_manifest(created_utc: str, output: Path) -> dict[str, Any]:
    return {
        "created_utc": created_utc,
        "status": "observation_manual_snapshot_loop_delegated_to_alpaca_module",
        "manual_observation_loop_blocking_research": False,
        "alpaca_execution_module_delegated": True,
        "active_vm_preserved": True,
        "active_dsr_preserved": True,
        "static_all_weather_benchmark_control_only": True,
        "new_paper_forward_candidate_created": False,
        "paper_forward_activation": False,
        "broker_api_called": False,
        "broker_orders_submitted": False,
        "broker_orders_cancelled": False,
        "broker_orders_reconciled": False,
        "live_orders": False,
        "real_money_recommendation": False,
        "missing_manual_snapshots_unresolved": True,
        "research_track_unblocked": True,
        "evidence_path": str(output.resolve()),
        "next_action": BATCH_ID,
    }


def write_observation_delegation(root: Path, created_utc: str) -> dict[str, Any]:
    output = root / OBSERVATION_OUTPUT_DIR
    output.mkdir(parents=True, exist_ok=True)
    manifest = observation_delegation_manifest(created_utc, output)
    write_json(output / "observation_delegation_manifest.json", manifest)
    write_text(
        output / "observation_delegation_summary.md",
        f"""# Observation Loop Delegation Summary

Status: `observation_manual_snapshot_loop_delegated_to_alpaca_module`

The missing manual account/equity/position/order snapshot loop remains unresolved, but it is no longer a blocker to historical strategy research.

Active VM and active DSR remain frozen research-supported observations. No new paper-forward candidate, broker action, live action, or real-money recommendation was created.
""",
    )
    write_text(
        output / "alpaca_execution_module_boundary.md",
        """# Alpaca Execution Module Boundary

Real paper/demo execution, account snapshots, positions, orders, fills, reconciliation, and operational demo validation are delegated to the separate Alpaca module/application.

This repository preserves strategy definitions, historical evidence, target-generation logic, and research lineage only.
""",
    )
    write_text(
        output / "manual_snapshot_loop_status.md",
        """# Manual Snapshot Loop Status

- Manual values supplied: `false`
- VM snapshot status: `partial_snapshot_manual_inputs_still_required`
- DSR snapshot status: `partial_snapshot_manual_inputs_still_required`
- Research blocker: `false`

Observation folders and templates are retained as optional/manual support files.
""",
    )
    write_text(
        output / "operations_research_boundary.md",
        """# Operations / Research Boundary

Research may continue using local historical data. Execution validation belongs to the Alpaca execution module.

Historical research outputs from this repository are non-promotable until separate governance, promotion, and execution-module validation steps occur.
""",
    )
    write_text(
        output / "observation_delegation_next_action.md",
        f"""# Observation Delegation Next Action

Delegation checkpoint complete. Research step authorized in this run:

`{BATCH_ID}`
""",
    )
    update_delegation_metadata(root, created_utc, output)
    return manifest


def update_delegation_metadata(root: Path, created_utc: str, output: Path) -> None:
    operations_path = root / OPERATIONS_STATE_PATH
    before_operations = read_text(operations_path)
    section = f"""## Observation Manual Snapshot Loop Delegated

- Created UTC: `{created_utc}`
- Evidence path: `{output.resolve()}`
- Status: `observation_manual_snapshot_loop_delegated_to_alpaca_module`
- Manual observation snapshots remain unresolved but no longer block historical research.
- Alpaca execution module owns paper/demo execution logs, account snapshots, orders, fills, and reconciliation.
- No broker API call, order action, live path, or real-money recommendation occurred.
"""
    write_text(
        operations_path,
        replace_or_append_section(before_operations, "## Observation Manual Snapshot Loop Delegated", section),
    )
    active_path = root / ACTIVE_OBSERVATIONS_PATH
    active_payload = load_yaml(active_path)
    active_payload["observation_manual_snapshot_loop_delegated_to_alpaca_module"] = {
        "created_utc": created_utc,
        "evidence_path": str(output.resolve()),
        "manual_observation_loop_blocking_research": False,
        "alpaca_execution_module_delegated": True,
        "active_vm_preserved": True,
        "active_dsr_preserved": True,
    }
    write_yaml(active_path, active_payload)


def research_manifest(created_utc: str, output: Path, rows: list[dict[str, Any]], families: list[dict[str, Any]]) -> dict[str, Any]:
    labels = pd.Series([row.get("research_label", "") for row in rows])
    next_action = NEXT_ACTION_AUDIT if rows and not any(label in FORBIDDEN_LABELS for label in labels) else NEXT_ACTION_FIX
    return {
        "created_utc": created_utc,
        **MANIFEST_FLAGS,
        "evidence_path": str(output.resolve()),
        "families_evaluated_count": int(len({row["family_id"] for row in rows})),
        "variants_planned_count": int(len(build_variant_plan())),
        "variants_evaluated_count": int(len(rows)),
        "research_signal_promising_count": int((labels == "research_signal_promising").sum()),
        "research_signal_high_risk_count": int((labels == "research_signal_high_risk").sum()),
        "research_signal_diversifier_count": int((labels == "research_signal_diversifier").sum()),
        "research_signal_data_blocked_count": int((labels == "research_signal_data_blocked").sum()),
        "families_recommended_for_deeper_research_count": int(
            sum(1 for family in families if family.get("deserves_deeper_research") is True)
        ),
        "forbidden_labels_present": sorted(set(labels).intersection(FORBIDDEN_LABELS)),
        "next_action": next_action,
    }


def write_research_outputs(root: Path, created_utc: str, inventory: list[dict[str, Any]], rows: list[dict[str, Any]], families: list[dict[str, Any]]) -> dict[str, Any]:
    output = root / RESEARCH_OUTPUT_DIR
    output.mkdir(parents=True, exist_ok=True)
    manifest = research_manifest(created_utc, output, rows, families)

    write_json(output / "profit_research_batch_manifest.json", manifest)
    write_text(output / "profit_research_batch_summary.md", research_summary_md(manifest, families))
    write_text(output / "local_cache_inventory.md", local_cache_inventory_md(inventory))
    write_text(output / "research_track_policy_v1.md", research_track_policy_md())
    write_text(output / "family_selection_rationale.md", family_selection_rationale_md())
    write_csv(output / "profit_research_variant_results.csv", rows, variant_fieldnames())
    write_csv(output / "profit_research_family_summary.csv", families, family_fieldnames())
    write_text(output / "profit_research_family_summary.md", family_summary_md(families))
    write_text(output / "high_profit_high_risk_signals.md", high_risk_md(rows))
    write_text(output / "portfolio_diversifier_signals.md", diversifier_md(rows))
    write_text(output / "gld_macro_lineage_status.md", gld_macro_lineage_md(root, rows))
    write_text(output / "false_negative_recovery_review.md", false_negative_recovery_md(rows, families))
    write_text(output / "methodology_notes.md", methodology_notes_md())
    write_text(output / "do_not_promote_from_profit_research_batch_v1.md", do_not_promote_md())
    write_text(output / "profit_research_batch_next_action.md", next_action_md(manifest["next_action"]))
    write_json(output / "profit_research_batch_consistency_check.json", {"consistency_passed": False})
    check = consistency_check(manifest, output, rows)
    write_json(output / "profit_research_batch_consistency_check.json", check)
    update_research_metadata(root, created_utc, output, manifest)
    return {**manifest, "consistency_passed": check["consistency_passed"]}


def variant_fieldnames() -> list[str]:
    return [
        "batch_id",
        "family_id",
        "variant_id",
        "universe",
        "rule_summary",
        "data_availability_status",
        "missing_symbols",
        "start_date",
        "end_date",
        "total_return",
        "cagr",
        "max_drawdown",
        "volatility",
        "calmar_or_return_drawdown_proxy",
        "benchmark_comparison",
        "spy_total_return_delta",
        "bil_cash_total_return_delta",
        "active_vm_dsr_contribution_comparison",
        "active_combo_correlation",
        "active_combo_blend_total_return_delta",
        "active_combo_blend_drawdown_delta",
        "trade_count",
        "turnover_proxy",
        "average_exposure",
        "cash_bil_allocation_share",
        "max_daily_exposure",
        "max_daily_weight_sum",
        "average_weight_sum",
        "weight_sum_violation_count",
        "negative_weight_violation_count",
        "nan_weight_count",
        "impossible_cash_and_risky_exposure_days",
        "worst_180_day_window",
        "best_180_day_window",
        "positive_180_day_window_ratio",
        "parameter_sensitivity_group",
        "regime_notes",
        "research_label",
        "promotion_eligibility",
        "paper_forward_eligibility",
        "historical_profit_score",
        "risk_adjusted_score",
        "drawdown_tolerance_score",
        "robustness_score",
        "portfolio_contribution_score",
        "implementation_practicality_score",
        "research_interest_score",
        "promotion_eligibility_score",
        "lineage_status",
    ]


def family_fieldnames() -> list[str]:
    return [
        "family_id",
        "variants_evaluated",
        "data_blocked_variants",
        "best_variant_by_historical_profit",
        "best_variant_by_risk_adjusted_score",
        "best_variant_by_portfolio_contribution",
        "median_cagr",
        "median_max_drawdown",
        "median_historical_profit_score",
        "median_risk_adjusted_score",
        "median_portfolio_contribution_score",
        "robustness_across_variants",
        "risk_profile",
        "evidence_broad_or_one_row",
        "deserves_deeper_research",
        "should_be_abandoned",
        "needs_methodology_or_data_audit",
        "family_research_status",
        "research_signal_promising_count",
        "research_signal_high_risk_count",
        "research_signal_diversifier_count",
        "research_signal_weak_count",
        "research_signal_duplicate_count",
    ]


def local_cache_inventory_md(inventory: list[dict[str, Any]]) -> str:
    ready = [row for row in inventory if row["status"] == "cache_ready"]
    symbols = ", ".join(row["symbol"] for row in ready)
    lines = [
        "# Local Cache Inventory",
        "",
        f"Cache-ready symbols: `{len(ready)}`",
        "",
        f"Symbols: `{symbols}`",
        "",
        "No provider download was attempted. Missing symbols are data-blocked.",
        "",
        "## Inventory",
        "",
        "| symbol | rows | first date | last date | status |",
        "|---|---:|---|---|---|",
    ]
    for row in inventory:
        lines.append(f"| {row['symbol']} | {row['rows']} | {row['first_date']} | {row['last_date']} | {row['status']} |")
    return "\n".join(lines)


def research_track_policy_md() -> str:
    labels = "\n".join(f"- `{label}`" for label in sorted(ALLOWED_LABELS))
    forbidden = "\n".join(f"- `{label}`" for label in sorted(FORBIDDEN_LABELS))
    return f"""# Profit-Oriented Research Track V1

Track ID: `{TRACK_ID}`

This track is historical-data-first. Discovery metrics are not promotion gates.

The batch may map historical profitability, drawdown, return/drawdown tradeoff, regime behavior, robustness, benchmark comparison, contribution, exposure/cash behavior, and implementation complexity.

Low drawdown is not a hard discovery gate. The old `$300-$400` target is not used as a hard gate. High-return/high-drawdown rows are classified, not promoted or instantly discarded.

## Allowed Exploration Labels

{labels}

## Forbidden Labels

{forbidden}
"""


def family_selection_rationale_md() -> str:
    return """# Family Selection Rationale

The batch uses the project's actual bottlenecks rather than random strategy generation:

- `high_return_tactical_etf_equity_index`: tests whether prior gates suppressed profitable but riskier standalone ETF ideas.
- `macro_gld_duration_risk_off`: recovers GLD/duration/risk-off evidence as research-only while lineage remains incomplete.
- `managed_futures_trend_following_etf_wrapper`: tests ETF/fund-wrapper trend streams without direct futures.
- `breakout_trend_momentum_high_risk`: preserves high-return trend/breakout signals even when too risky for promotion.
- `portfolio_diversifier_contribution`: maps sleeves that may help active VM/DSR or benchmark portfolios.
"""


def research_summary_md(manifest: dict[str, Any], families: list[dict[str, Any]]) -> str:
    deeper = [family["family_id"] for family in families if family.get("deserves_deeper_research") is True]
    return f"""# Profit-Oriented Research Batch V1 Summary

Batch ID: `{BATCH_ID}`

Variants planned: `{manifest['variants_planned_count']}`

Variants evaluated: `{manifest['variants_evaluated_count']}`

Families evaluated: `{manifest['families_evaluated_count']}`

Manual observation loop blocking research: `{manifest['manual_observation_loop_blocking_research']}`

Alpaca execution module delegated: `{manifest['alpaca_execution_module_delegated']}`

Research outputs non-promotable: `{manifest['research_outputs_non_promotable']}`

Families recommended for deeper research: `{', '.join(deeper) if deeper else 'none'}`

Exact next action: `{manifest['next_action']}`
"""


def family_summary_md(families: list[dict[str, Any]]) -> str:
    lines = ["# Profit Research Family Summary", ""]
    for family in families:
        lines.extend(
            [
                f"## `{family['family_id']}`",
                "",
                f"- Variants evaluated: `{family.get('variants_evaluated', 0)}`",
                f"- Best by historical profit: `{family.get('best_variant_by_historical_profit', '')}`",
                f"- Best by risk-adjusted score: `{family.get('best_variant_by_risk_adjusted_score', '')}`",
                f"- Best by portfolio contribution: `{family.get('best_variant_by_portfolio_contribution', '')}`",
                f"- Risk profile: `{family.get('risk_profile', '')}`",
                f"- Evidence breadth: `{family.get('evidence_broad_or_one_row', '')}`",
                f"- Deserves deeper research: `{family.get('deserves_deeper_research', False)}`",
                f"- Needs methodology/data audit: `{family.get('needs_methodology_or_data_audit', False)}`",
                "",
            ]
        )
    return "\n".join(lines)


def high_risk_md(rows: list[dict[str, Any]]) -> str:
    selected = sorted(
        [row for row in rows if row.get("research_label") == "research_signal_high_risk"],
        key=lambda row: float(row.get("historical_profit_score", 0.0) or 0.0),
        reverse=True,
    )
    lines = ["# High-Profit / High-Risk Signals", ""]
    if not selected:
        lines.append("No high-profit/high-risk research labels were produced.")
    for row in selected[:20]:
        lines.append(
            f"- `{row['variant_id']}` / `{row['family_id']}`: CAGR `{float(row.get('cagr', 0.0)):.4f}`, "
            f"max drawdown `{float(row.get('max_drawdown', 0.0)):.4f}`, label `{row['research_label']}`"
        )
    return "\n".join(lines)


def diversifier_md(rows: list[dict[str, Any]]) -> str:
    selected = sorted(
        [row for row in rows if row.get("research_label") == "research_signal_diversifier"],
        key=lambda row: float(row.get("portfolio_contribution_score", 0.0) or 0.0),
        reverse=True,
    )
    lines = ["# Portfolio Diversifier Signals", ""]
    if not selected:
        lines.append("No rows met the diversifier research-label threshold.")
    for row in selected[:20]:
        lines.append(
            f"- `{row['variant_id']}` / `{row['family_id']}`: contribution score "
            f"`{float(row.get('portfolio_contribution_score', 0.0)):.2f}`, active-combo correlation "
            f"`{float(row.get('active_combo_correlation', float('nan'))):.4f}`"
        )
    return "\n".join(lines)


def gld_macro_lineage_md(root: Path, rows: list[dict[str, Any]]) -> str:
    ledger = load_yaml(root / FAMILY_LEDGER_PATH)
    entries = ledger.get("entries", [])
    gld = next((entry for entry in entries if entry.get("family_id") == "gld_macro_risk_off"), {})
    macro_rows = [row for row in rows if row.get("family_id") == "macro_gld_duration_risk_off"]
    labels = pd.Series([row.get("research_label", "") for row in macro_rows]).value_counts().to_dict()
    return f"""# GLD / Macro Lineage Status

Ledger status: `{gld.get('current_status', 'unknown')}`

Lineage recovery needed: `{gld.get('lineage_recovery_needed', True)}`

Batch interpretation status: `lineage_incomplete_research_only`

Macro variants evaluated: `{len(macro_rows)}`

Research labels: `{labels}`

These rows are research-only. They do not reopen old GLD/GROR variants and cannot become promotable without a separate lineage recovery review.
"""


def false_negative_recovery_md(rows: list[dict[str, Any]], families: list[dict[str, Any]]) -> str:
    high_risk_count = sum(1 for row in rows if row.get("research_label") == "research_signal_high_risk")
    diversifier_count = sum(1 for row in rows if row.get("research_label") == "research_signal_diversifier")
    deeper = [family["family_id"] for family in families if family.get("deserves_deeper_research") is True]
    return f"""# False-Negative Recovery Review

This batch intentionally avoids using low drawdown or the old `$300-$400` target as hard discovery gates.

High-risk historically profitable rows found: `{high_risk_count}`

Portfolio-diversifier rows found: `{diversifier_count}`

Families with enough non-promotable research interest for deeper review: `{', '.join(deeper) if deeper else 'none'}`

No best row was promoted. Any deeper work requires audit and separate preregistration.
"""


def methodology_notes_md() -> str:
    return """# Methodology Notes

- Data source: local `data/cache/*.csv` only.
- Price field: `adj_close` when present, otherwise `close`.
- Signal timing: monthly momentum signals use prior close information and apply weights to subsequent daily returns.
- Breakout signals use prior-high and prior-SMA information with BIL fallback where available.
- No provider APIs, intraday data, broker APIs, order paths, or live paths were used.
- Parameter maps are family-level research maps, not best-row promotion tools.
- Results are non-promotable and require audit before any further action.
"""


def do_not_promote_md() -> str:
    return """# Do Not Promote From Profit Research Batch V1

This batch is non-promotable by design.

Forbidden direct outcomes:

- `promotion_review_candidate`
- `candidate_exhaustive_candidate`
- `paper_forward_candidate`
- `demo_active_new`
- `live_ready`
- `real_money_candidate`

Historical profitability can justify only a later audit or preregistered research step, never direct activation.
"""


def next_action_md(next_action: str) -> str:
    return f"""# Profit Research Batch Next Action

Exact next action:

`{next_action}`

Do not run the next action in this task.
"""


def update_research_metadata(root: Path, created_utc: str, output: Path, manifest: dict[str, Any]) -> None:
    research_path = root / RESEARCH_STATE_PATH
    before_research = read_text(research_path)
    section = f"""## Latest Profit-Oriented Research Batch V1

- Created UTC: `{created_utc}`
- Evidence path: `{output.resolve()}`
- Batch ID: `{BATCH_ID}`
- Manual observation loop blocking research: `{manifest['manual_observation_loop_blocking_research']}`
- Variants evaluated: `{manifest['variants_evaluated_count']}`
- Families evaluated: `{manifest['families_evaluated_count']}`
- Promotion candidates created: `{manifest['promotion_candidates_created']}`
- Paper-forward activation: `{manifest['paper_forward_activation']}`
- Provider download: `{manifest['provider_download']}`
- Next action: `{manifest['next_action']}`
"""
    write_text(research_path, replace_or_append_section(before_research, "## Latest Profit-Oriented Research Batch V1", section))


def consistency_check(manifest: dict[str, Any], output: Path, rows: list[dict[str, Any]]) -> dict[str, Any]:
    required = {name: (output / name).exists() for name in RESEARCH_REQUIRED_FILES}
    labels = {row.get("research_label", "") for row in rows}
    check = {
        "observation_manual_loop_not_blocking": manifest["manual_observation_loop_blocking_research"] is False,
        "alpaca_execution_module_delegated": manifest["alpaca_execution_module_delegated"] is True,
        "historical_research_only": manifest["historical_research_only"] is True,
        "local_cache_only": manifest["uses_local_cache_only"] is True,
        "no_provider_download": manifest["provider_download"] is False,
        "no_intraday": manifest["intraday_data_used"] is False,
        "no_broker_api": manifest["broker_api_called"] is False,
        "no_broker_orders": (
            manifest["broker_orders_submitted"] is False
            and manifest["broker_orders_cancelled"] is False
            and manifest["broker_orders_reconciled"] is False
        ),
        "no_live_or_real_money": manifest["live_orders"] is False and manifest["real_money_recommendation"] is False,
        "no_paper_forward_activation": manifest["paper_forward_activation"] is False,
        "no_new_paper_forward_candidate": manifest["new_paper_forward_candidate_created"] is False,
        "no_candidate_exhaustive": manifest["candidate_exhaustive_run"] is False,
        "no_promotion_candidates": manifest["promotion_candidates_created"] is False,
        "no_best_single_variant_promoted": manifest["best_single_variant_promoted"] is False,
        "active_vm_preserved": manifest["active_vm_preserved"] is True,
        "active_dsr_preserved": manifest["active_dsr_preserved"] is True,
        "static_all_weather_control_only": manifest["static_all_weather_benchmark_control_only"] is True,
        "old_dollar_target_not_hard_gate": manifest["old_dollar_target_is_hard_gate"] is False,
        "low_drawdown_not_hard_discovery_gate": manifest["low_drawdown_is_hard_discovery_gate"] is False,
        "research_outputs_non_promotable": manifest["research_outputs_non_promotable"] is True,
        "variant_results_exist": (output / "profit_research_variant_results.csv").exists() and bool(rows),
        "family_summary_exists": (output / "profit_research_family_summary.csv").exists(),
        "high_risk_file_exists": (output / "high_profit_high_risk_signals.md").exists(),
        "diversifier_file_exists": (output / "portfolio_diversifier_signals.md").exists(),
        "do_not_promote_file_exists": (output / "do_not_promote_from_profit_research_batch_v1.md").exists(),
        "allowed_labels_only": labels.issubset(ALLOWED_LABELS),
        "forbidden_labels_absent": not labels.intersection(FORBIDDEN_LABELS),
        "next_action_valid": manifest["next_action"] in VALID_NEXT_ACTIONS,
        "required_files_present": all(required.values()),
        "required_files": required,
    }
    check["consistency_passed"] = all(value is True for key, value in check.items() if key != "required_files")
    return check


def run(root: Path = ROOT) -> dict[str, Any]:
    created = now_utc()
    observation_manifest = write_observation_delegation(root, created)
    inventory, rows, families = evaluate_batch(root)
    research_manifest_result = write_research_outputs(root, created, inventory, rows, families)
    return {
        "observation_output_dir": str((root / OBSERVATION_OUTPUT_DIR).resolve()),
        "research_output_dir": str((root / RESEARCH_OUTPUT_DIR).resolve()),
        "observation_manifest": observation_manifest,
        **research_manifest_result,
    }


if __name__ == "__main__":
    result = run()
    print(
        json.dumps(
            {
                "observation_output_dir": result["observation_output_dir"],
                "research_output_dir": result["research_output_dir"],
                "batch_id": result["batch_id"],
                "variants_evaluated_count": result["variants_evaluated_count"],
                "families_evaluated_count": result["families_evaluated_count"],
                "next_action": result["next_action"],
                "consistency_passed": result["consistency_passed"],
            },
            indent=2,
        )
    )
