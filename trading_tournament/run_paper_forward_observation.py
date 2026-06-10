from __future__ import annotations

import argparse
import json
import math
import shutil
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml

from src.backtester import Backtester
from src.data import load_market_data
from src.indicators import prepare_indicators
from src.utils import load_config
from src.validation import strategy_variant_config


REPO_ROOT = Path(__file__).resolve().parent
OUTPUT_ROOT = REPO_ROOT / "evidence" / "paper_forward_runs"
LATEST_ZIP = OUTPUT_ROOT / "latest_paper_forward_packet.zip"
CHECKPOINT_HISTORY_NAME = "paper_forward_checkpoints.csv"
MONTHLY_DECISION_NAME = "monthly_decision_checkpoints.csv"
COMBO_STRATEGY = "combo_SPY200d_GLD_50_50_v1"
COMBO_CONFIG_PATH = REPO_ROOT / "paper_forward_observations" / COMBO_STRATEGY / "observation_config.yaml"
STARTING_EQUITY = 3000.0
TARGET_300 = 3300.0
TARGET_400 = 3400.0
ABSOLUTE_STOP = 2400.0
TRAILING_DRAWDOWN = 600.0
STANDARD_SLIPPAGE = 0.0005
RISK_FRAMEWORK_NAME = "balanced_speculative_research_v1"
REQUIRED_FILES = [
    "README_FOR_ADVISOR.md",
    "paper_forward_summary.md",
    "paper_forward_status.csv",
    "risk_status.csv",
    "signal_snapshot.csv",
    "benchmark_comparison.csv",
    CHECKPOINT_HISTORY_NAME,
    MONTHLY_DECISION_NAME,
    "warnings_and_limitations.md",
    "paper_forward_manifest.json",
]
COMBO_BLOCKED_STATUSES = {
    "activation_blocked_rule_hash_missing",
    "activation_waiting_for_data",
    "active_waiting_for_next_cached_trading_day",
}
WATCHLIST = {
    "SPY_200d_trend_model": "primary_watchlist_candidate",
    "current_no_cash_proxy_alpha_AB": "strategy_control",
    "SPY_buy_hold": "aggressive_benchmark",
    "BIL_cash_proxy": "defensive_benchmark",
}
HISTORICAL_BASELINE = {
    "SPY_200d_trend_model": (0.251, 0.104, 0.005, 3114.12, -661.49),
    "current_no_cash_proxy_alpha_AB": (0.126, 0.034, 0.000, 3024.79, -406.02),
    "SPY_buy_hold": (0.329, 0.158, 0.068, 3162.17, -1329.58),
    "BIL_cash_proxy": (0.000, 0.000, 0.000, 2999.81, -24.67),
    COMBO_STRATEGY: (math.nan, math.nan, math.nan, STARTING_EQUITY, math.nan),
}


RISK_FRAMEWORK_FIELDS = [
    "risk_framework_name",
    "risk_band",
    "risk_budget_used_pct",
    "target_300_progress_pct",
    "target_400_progress_pct",
    "drawdown_warning_hit",
    "drawdown_review_hit",
    "hard_stop_hit",
    "risk_framework_status",
    "paper_forward_allowed_by_risk_framework",
]

CHECKPOINT_COLUMNS = [
    "checkpoint_timestamp_utc",
    "run_id",
    "observation_start_date",
    "observation_end_date",
    "strategy",
    "role",
    "current_equity",
    "current_return",
    "target_300_hit",
    "target_400_hit",
    "any_project_stop_hit",
    "first_project_stop_date",
    "high_water_mark",
    "current_drawdown_dollars",
    "current_drawdown_pct",
    "max_drawdown_dollars",
    "target_300_distance",
    "target_400_distance",
    "distance_to_absolute_stop",
    "distance_to_trailing_stop",
    "risk_band",
    "risk_budget_used_pct",
    "target_300_progress_pct",
    "target_400_progress_pct",
    "signal_state",
    "current_position_symbols",
    "status",
    "notes",
]

MONTHLY_DECISION_COLUMNS = [
    "checkpoint_month",
    "latest_run_id",
    "observation_start_date",
    "latest_observation_end_date",
    "primary_strategy",
    "primary_current_equity",
    "primary_current_return",
    "primary_target_300_distance",
    "primary_target_400_distance",
    "primary_distance_to_absolute_stop",
    "primary_distance_to_trailing_stop",
    "primary_risk_band",
    "primary_signal_state",
    "primary_status",
    "spy_buy_hold_equity",
    "current_no_cash_proxy_alpha_AB_equity",
    "bil_cash_proxy_equity",
    "primary_vs_spy_buy_hold",
    "primary_vs_current_no_cash_proxy_alpha_AB",
    "primary_vs_bil",
    "primary_vs_spy200d_control",
    "combo_observation_status",
    "combo_replaces_spy200d",
    "historical_90d_target_300_before_stop",
    "historical_90d_target_400_before_stop",
    "historical_90d_any_stop_hit",
    "historical_90d_median_stop_equity",
    "current_vs_historical_interpretation",
    "decision",
    "decision_reason",
    "forbidden_actions",
]


@dataclass(frozen=True)
class StopState:
    target_300_hit: bool
    target_300_date: str
    target_400_hit: bool
    target_400_date: str
    absolute_floor_stop_hit: bool
    trailing_drawdown_stop_hit: bool
    any_project_stop_hit: bool
    first_project_stop_date: str
    high_water_mark: float
    current_drawdown_dollars: float
    current_drawdown_pct: float
    max_drawdown_dollars: float
    max_drawdown_pct: float
    stop_enforced_current_equity: float


def utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def normalize_date(value: str | None) -> str | None:
    if value in {None, "", "latest"}:
        return None
    return pd.Timestamp(value).date().isoformat()


def load_adjusted_price_cache(symbols: list[str]) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for symbol in symbols:
        path = REPO_ROOT / "data" / "cache" / f"{symbol}.csv"
        if not path.exists():
            continue
        df = pd.read_csv(path)
        needed = {"date", "close", "symbol"}
        if not needed.issubset(df.columns):
            continue
        df["date"] = pd.to_datetime(df["date"])
        df["close"] = pd.to_numeric(df["close"], errors="coerce")
        df["symbol"] = symbol
        frames.append(df[["date", "close", "symbol"]].dropna(subset=["date", "close"]))
    if not frames:
        return pd.DataFrame(columns=["date", "close", "symbol"])
    return pd.concat(frames, ignore_index=True).sort_values(["symbol", "date"])


def maybe_refresh_cache(no_network: bool, force_refresh: bool) -> str:
    if no_network:
        return "network disabled; existing ETF cache only"
    if not force_refresh:
        return "existing ETF cache reused; no refresh requested"
    config = load_config(REPO_ROOT / "config.yaml")
    config["project_root"] = str(REPO_ROOT)
    config.setdefault("data", {})["use_cache"] = True
    config.setdefault("data", {})["refresh_cache"] = True
    load_market_data(config, REPO_ROOT)
    return "ETF cache refresh requested through existing yfinance loader"


def select_observation_prices(prices: pd.DataFrame, start_date: str, end_date: str | None) -> tuple[pd.DataFrame, str, str, str]:
    if prices.empty:
        return prices, start_date, end_date or "", "insufficient_data"
    start_ts = pd.Timestamp(start_date)
    end_ts = pd.Timestamp(end_date) if end_date else prices.index.max()
    selected = prices.loc[(prices.index >= start_ts) & (prices.index <= end_ts)].copy()
    if selected.empty:
        return selected, start_date, pd.Timestamp(prices.index.max()).date().isoformat(), "no_new_data"
    return selected, pd.Timestamp(selected.index.min()).date().isoformat(), pd.Timestamp(selected.index.max()).date().isoformat(), "ok"


def benchmark_weights(full_prices: pd.DataFrame, strategy: str) -> pd.DataFrame:
    weights = pd.DataFrame(0.0, index=full_prices.index, columns=full_prices.columns)
    if strategy == "SPY_buy_hold":
        if "SPY" in weights:
            weights.loc[full_prices["SPY"].notna(), "SPY"] = 1.0
    elif strategy == "BIL_cash_proxy":
        if "BIL" in weights:
            weights.loc[full_prices["BIL"].notna(), "BIL"] = 1.0
    elif strategy == "SPY_200d_trend_model":
        spy = full_prices["SPY"] if "SPY" in full_prices else pd.Series(index=full_prices.index, dtype=float)
        sma = spy.rolling(200, min_periods=200).mean()
        risk_on = spy > sma
        weights.loc[risk_on.fillna(False), "SPY"] = 1.0
        if "BIL" in weights:
            weights.loc[~risk_on.fillna(False) & full_prices["BIL"].notna(), "BIL"] = 1.0
    else:
        raise ValueError(f"Unknown benchmark strategy: {strategy}")
    return weights.shift(1).ffill().fillna(0.0)


def buy_hold_symbol_weights(full_prices: pd.DataFrame, symbol: str) -> pd.DataFrame:
    weights = pd.DataFrame(0.0, index=full_prices.index, columns=full_prices.columns)
    if symbol in weights:
        weights.loc[full_prices[symbol].notna(), symbol] = 1.0
    return weights.shift(1).ffill().fillna(0.0)


def simulate_weighted_curve(prices: pd.DataFrame, weights: pd.DataFrame, cost: float = STANDARD_SLIPPAGE) -> tuple[pd.DataFrame, float, int]:
    prices = prices.reindex(weights.index).reindex(columns=weights.columns).ffill()
    returns = prices.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    equity_values: list[float] = []
    prev_equity = STARTING_EQUITY
    prev_weights = pd.Series(0.0, index=weights.columns)
    turnover = 0.0
    rebalances = 0
    for date in prices.index:
        current = weights.loc[date].fillna(0.0).clip(0.0, 1.0)
        total = float(current.sum())
        if total > 1.0:
            current = current / total
        day_turnover = float((current - prev_weights).abs().sum())
        day_cost = prev_equity * day_turnover * cost
        gross = float((current * returns.loc[date]).sum())
        equity = max(0.0, prev_equity * (1.0 + gross) - day_cost)
        equity_values.append(equity)
        if day_turnover > 1e-9:
            rebalances += 1
            turnover += day_turnover
        prev_equity = equity
        prev_weights = current
    curve = pd.DataFrame({"date": prices.index, "equity": equity_values})
    return curve, turnover, rebalances


def sleeve_return_stream(prices: pd.DataFrame, weights: pd.DataFrame, cost: float = STANDARD_SLIPPAGE) -> pd.Series:
    curve, _turnover, _rebalances = simulate_weighted_curve(prices, weights, cost)
    return curve.set_index("date")["equity"].pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan).fillna(0.0)


def monthly_combo_targets(index: pd.Index) -> pd.DataFrame:
    targets = pd.DataFrame(0.0, index=index, columns=["SPY_200d_trend_model", "GLD_buy_hold"])
    month = pd.Series(pd.to_datetime(index).to_period("M"), index=index)
    rebalance = month.ne(month.shift(1))
    targets.loc[rebalance, "SPY_200d_trend_model"] = 0.5
    targets.loc[rebalance, "GLD_buy_hold"] = 0.5
    return targets.replace(0.0, np.nan).ffill().fillna(0.0)


def combo_curve_from_sleeves(full_prices: pd.DataFrame, observation_prices: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, int]:
    spy_weights = benchmark_weights(full_prices, "SPY_200d_trend_model")
    gld_weights = buy_hold_symbol_weights(full_prices, "GLD")
    sleeve_returns = pd.DataFrame(
        {
            "SPY_200d_trend_model": sleeve_return_stream(full_prices, spy_weights),
            "GLD_buy_hold": sleeve_return_stream(full_prices, gld_weights),
        }
    ).reindex(observation_prices.index).fillna(0.0)
    if not sleeve_returns.empty:
        # The first observation row initializes the paper/demo account; returns
        # before --start-date must not leak into the active observation window.
        sleeve_returns.iloc[0] = 0.0
    targets = monthly_combo_targets(observation_prices.index)
    prev_equity = STARTING_EQUITY
    prev_targets = pd.Series(0.0, index=targets.columns)
    equities: list[float] = []
    rebalances = 0
    for dt in observation_prices.index:
        current = targets.loc[dt].fillna(0.0).clip(0.0, 1.0)
        turnover = float((current - prev_targets).abs().sum())
        if turnover > 1e-9:
            rebalances += 1
        equity = max(0.0, prev_equity * (1.0 + float((current * sleeve_returns.loc[dt]).sum())) - prev_equity * turnover * STANDARD_SLIPPAGE)
        equities.append(equity)
        prev_equity = equity
        prev_targets = current
    symbol_weights = (
        spy_weights.reindex(observation_prices.index).fillna(0.0).mul(targets["SPY_200d_trend_model"], axis=0)
        + gld_weights.reindex(observation_prices.index).fillna(0.0).mul(targets["GLD_buy_hold"], axis=0)
    ).fillna(0.0)
    return pd.DataFrame({"date": observation_prices.index, "equity": equities}), symbol_weights, rebalances


def stop_state(equity: pd.Series, dates: pd.Series | pd.Index) -> StopState:
    equity = pd.Series(equity, dtype=float).reset_index(drop=True)
    dates = pd.to_datetime(pd.Series(dates)).reset_index(drop=True)
    if equity.empty:
        equity = pd.Series([STARTING_EQUITY])
        dates = pd.Series([pd.Timestamp.today().normalize()])
    high = equity.cummax()
    drawdown = equity - high
    drawdown_pct = drawdown / high.replace(0, np.nan)
    absolute = equity <= ABSOLUTE_STOP
    trailing = equity <= high - TRAILING_DRAWDOWN
    stopped = absolute | trailing
    first_stop_idx: int | None = int(np.flatnonzero(stopped.to_numpy())[0]) if stopped.any() else None

    def target(target_equity: float) -> tuple[bool, str]:
        hit = equity >= target_equity
        if not hit.any():
            return False, ""
        idx = int(np.flatnonzero(hit.to_numpy())[0])
        return True, dates.iloc[idx].date().isoformat()

    target_300_hit, target_300_date = target(TARGET_300)
    target_400_hit, target_400_date = target(TARGET_400)
    current_equity = float(equity.iloc[-1])
    stop_equity = float(equity.iloc[first_stop_idx]) if first_stop_idx is not None else current_equity
    return StopState(
        target_300_hit=target_300_hit,
        target_300_date=target_300_date,
        target_400_hit=target_400_hit,
        target_400_date=target_400_date,
        absolute_floor_stop_hit=bool(absolute.any()),
        trailing_drawdown_stop_hit=bool(trailing.any()),
        any_project_stop_hit=bool(stopped.any()),
        first_project_stop_date=dates.iloc[first_stop_idx].date().isoformat() if first_stop_idx is not None else "",
        high_water_mark=float(high.iloc[-1]),
        current_drawdown_dollars=float(drawdown.iloc[-1]),
        current_drawdown_pct=float(drawdown_pct.iloc[-1]) if pd.notna(drawdown_pct.iloc[-1]) else 0.0,
        max_drawdown_dollars=float(drawdown.min()),
        max_drawdown_pct=float(drawdown_pct.min()) if drawdown_pct.notna().any() else 0.0,
        stop_enforced_current_equity=stop_equity,
    )


def status_from_stop(state: StopState, data_state: str) -> str:
    if data_state in COMBO_BLOCKED_STATUSES:
        return data_state
    if data_state == "no_new_data":
        return "no_new_data"
    if data_state != "ok":
        return "insufficient_data"
    if state.any_project_stop_hit:
        return "stopped"
    if state.target_400_hit:
        return "target_400_reached"
    if state.target_300_hit:
        return "target_300_reached"
    return "active_observation"


def risk_label(row: pd.Series) -> str:
    if bool(row["any_project_stop_hit"]):
        return "stopped"
    if pd.isna(row["current_equity"]):
        return "insufficient_data"
    if float(row["target_400_distance"]) <= 50:
        return "near_target_400"
    if float(row["target_300_distance"]) <= 50:
        return "near_target_300"
    if float(row["distance_to_trailing_stop"]) <= 100 or float(row["current_drawdown_dollars"]) <= -300:
        return "drawdown_warning"
    return "normal"


def risk_band_from_drawdown(drawdown_dollars: float, stop_hit: bool = False) -> str:
    if stop_hit or drawdown_dollars <= -TRAILING_DRAWDOWN:
        return "hard_stop"
    if drawdown_dollars <= -450.0:
        return "review"
    if drawdown_dollars <= -300.0:
        return "warning"
    return "normal"


def risk_framework_status(row: pd.Series) -> str:
    if str(row.get("status", "")) in COMBO_BLOCKED_STATUSES:
        return "activation_blocked"
    if bool(row.get("any_project_stop_hit", False)):
        return "stopped"
    if bool(row.get("target_400_hit", False)):
        return "target_400_reached"
    if bool(row.get("target_300_hit", False)):
        return "target_300_reached"
    drawdown = float(row.get("max_drawdown_dollars", 0.0))
    if drawdown <= -450.0:
        return "active_review"
    if drawdown <= -300.0:
        return "active_warning"
    if pd.isna(row.get("current_equity", math.nan)):
        return "insufficient_data"
    return "active_normal"


def risk_framework_fields(row: pd.Series) -> dict[str, Any]:
    current = float(row.get("current_equity", STARTING_EQUITY)) if pd.notna(row.get("current_equity", math.nan)) else STARTING_EQUITY
    drawdown = float(row.get("max_drawdown_dollars", 0.0)) if pd.notna(row.get("max_drawdown_dollars", math.nan)) else 0.0
    stop_hit = bool(row.get("any_project_stop_hit", False))
    status = str(row.get("status", ""))
    return {
        "risk_framework_name": RISK_FRAMEWORK_NAME,
        "risk_band": risk_band_from_drawdown(drawdown, stop_hit),
        "risk_budget_used_pct": abs(drawdown) / TRAILING_DRAWDOWN,
        "target_300_progress_pct": max(0.0, current - STARTING_EQUITY) / (TARGET_300 - STARTING_EQUITY),
        "target_400_progress_pct": max(0.0, current - STARTING_EQUITY) / (TARGET_400 - STARTING_EQUITY),
        "drawdown_warning_hit": drawdown <= -300.0,
        "drawdown_review_hit": drawdown <= -450.0,
        "hard_stop_hit": stop_hit or drawdown <= -TRAILING_DRAWDOWN,
        "risk_framework_status": risk_framework_status(row),
        "paper_forward_allowed_by_risk_framework": status not in COMBO_BLOCKED_STATUSES,
    }


def apply_risk_framework_to_status(status: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, row in status.iterrows():
        updated = row.to_dict()
        updated.update(risk_framework_fields(row))
        rows.append(updated)
    return pd.DataFrame(rows)


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def distance_fields(row: pd.Series) -> dict[str, float]:
    current = float(row.get("current_equity", STARTING_EQUITY)) if pd.notna(row.get("current_equity", math.nan)) else STARTING_EQUITY
    high = float(row.get("high_water_mark", current)) if pd.notna(row.get("high_water_mark", math.nan)) else current
    return {
        "distance_to_target_300": TARGET_300 - current,
        "distance_to_target_400": TARGET_400 - current,
        "target_300_distance": TARGET_300 - current,
        "target_400_distance": TARGET_400 - current,
        "distance_to_absolute_stop": current - ABSOLUTE_STOP,
        "distance_to_trailing_stop": current - (high - TRAILING_DRAWDOWN),
    }


def current_vs_historical_status(row: pd.Series, median_equity: float) -> str:
    if str(row.get("status", "")) in COMBO_BLOCKED_STATUSES:
        return str(row.get("status", "activation_blocked"))
    current_return = float(row.get("current_return", 0.0)) if pd.notna(row.get("current_return", math.nan)) else 0.0
    if bool(row.get("any_project_stop_hit", False)):
        return "worse_than_desired_stop_hit"
    if current_return >= 0.10:
        return "at_or_above_300_target"
    if int(row.get("days_elapsed", 0)) < 90:
        return "too_early_to_compare_to_90d_distribution"
    if float(row.get("current_equity", STARTING_EQUITY)) >= median_equity:
        return "above_historical_90d_median"
    return "below_historical_90d_median"


def decision_status_for_row(row: pd.Series) -> str:
    if str(row.get("status", "")) in COMBO_BLOCKED_STATUSES:
        return str(row.get("status", "activation_blocked"))
    if str(row.get("status", "")) in {"insufficient_data", "no_new_data"}:
        return "data_issue"
    if bool(row.get("any_project_stop_hit", False)):
        return "stopped"
    if bool(row.get("target_400_hit", False)) or bool(row.get("target_300_hit", False)):
        return "target_reached"
    if int(row.get("days_elapsed", 0)) < 30:
        return "inconclusive_too_early"
    return "continue_observation"


def enrich_status_for_decisions(status: pd.DataFrame) -> pd.DataFrame:
    if status.empty:
        return status.copy()
    status = apply_risk_framework_to_status(status)
    historical = load_historical_baseline()
    rows: list[dict[str, Any]] = []
    for _, row in status.iterrows():
        updated = row.to_dict()
        strategy = str(row["strategy"])
        p300, p400, stop, median_equity, _worst_dd = historical.get(strategy, HISTORICAL_BASELINE[strategy])
        updated.update(distance_fields(row))
        updated.update(
            {
                "historical_90d_target_300_before_stop": p300,
                "historical_90d_target_400_before_stop": p400,
                "historical_90d_any_stop_hit": stop,
                "current_vs_historical_status": current_vs_historical_status(row, median_equity),
                "decision_status": decision_status_for_row(row),
            }
        )
        rows.append(updated)
    return pd.DataFrame(rows)


def position_text(weights: pd.Series) -> tuple[str, str]:
    active = weights[weights.abs() > 1e-9].sort_values(ascending=False)
    if active.empty:
        return "cash", "{}"
    return ",".join(active.index.astype(str)), yaml.safe_dump({str(k): float(v) for k, v in active.items()}, sort_keys=True).strip()


def signal_for_spy_200d(full_prices: pd.DataFrame, as_of_date: pd.Timestamp) -> tuple[str, float, float, bool, str]:
    spy = full_prices["SPY"] if "SPY" in full_prices else pd.Series(dtype=float)
    close = float(spy.loc[as_of_date]) if as_of_date in spy.index and pd.notna(spy.loc[as_of_date]) else math.nan
    sma = spy.rolling(200, min_periods=200).mean()
    sma_value = float(sma.loc[as_of_date]) if as_of_date in sma.index and pd.notna(sma.loc[as_of_date]) else math.nan
    above = bool(close > sma_value) if pd.notna(close) and pd.notna(sma_value) else False
    return ("risk_on" if above else "cash"), close, sma_value, above, ("SPY close > 200-day SMA" if above else "SPY close <= 200-day SMA or SMA unavailable")


def build_benchmark_outputs(
    run_id: str,
    full_prices: pd.DataFrame,
    observation_prices: pd.DataFrame,
    strategy: str,
    role: str,
    start_date: str,
    end_date: str,
    data_state: str,
) -> tuple[dict[str, Any], pd.DataFrame, list[dict[str, Any]], float, int]:
    if observation_prices.empty:
        empty_state = stop_state(pd.Series([STARTING_EQUITY]), pd.Index([pd.Timestamp(start_date)]))
        return status_row(run_id, start_date, end_date, strategy, role, empty_state, data_state, "", "", "", 0), pd.DataFrame(), [], 0.0, 0
    weights = benchmark_weights(full_prices, strategy).reindex(observation_prices.index).fillna(0.0)
    curve, turnover, rebalances = simulate_weighted_curve(observation_prices, weights)
    state = stop_state(curve["equity"], curve["date"])
    latest_weights = weights.iloc[-1] if not weights.empty else pd.Series(dtype=float)
    symbols, target_weights = position_text(latest_weights)
    signal_state = {
        "SPY_buy_hold": "hold_spy",
        "BIL_cash_proxy": "hold_bil",
    }.get(strategy)
    if strategy == "SPY_200d_trend_model":
        signal_state = signal_for_spy_200d(full_prices, observation_prices.index[-1])[0]
    row = status_row(
        run_id,
        start_date,
        end_date,
        strategy,
        role,
        state,
        data_state,
        signal_state or "",
        symbols,
        target_weights,
        rebalances,
    )
    daily = daily_log(strategy, role, curve, weights, signal_state or "")
    snapshot = signal_snapshot_for_benchmark(strategy, role, full_prices, weights, observation_prices.index[-1])
    return row, daily, snapshot, turnover, rebalances


def build_current_ab_outputs(
    run_id: str,
    start_date: str,
    end_date: str,
    data_state: str,
) -> tuple[dict[str, Any], pd.DataFrame, list[dict[str, Any]], int]:
    role = WATCHLIST["current_no_cash_proxy_alpha_AB"]
    try:
        config = load_config(REPO_ROOT / "config.yaml")
        config["project_root"] = str(REPO_ROOT)
        data_result = load_market_data(config, REPO_ROOT)
        prepared = prepare_indicators(data_result.data)
        base = Backtester(prepared, config)
        full_range = config["date_ranges"]["full"]
        all_dates = base._effective_calendar(str(full_range["start"]), full_range.get("end") or config["data"].get("end_date"))
        obs_dates = [d for d in all_dates if pd.Timestamp(start_date) <= d <= pd.Timestamp(end_date)]
        if not obs_dates:
            raise RuntimeError("No observation dates after start date for current_no_cash_proxy_alpha_AB.")
        variant_cfg = strategy_variant_config(config, "current_no_cash_proxy_alpha_AB")
        result = Backtester(prepared, variant_cfg).run(
            "paper_forward_current_no_cash_proxy_alpha_AB",
            str(pd.Timestamp(start_date).date()),
            str(pd.Timestamp(end_date).date()),
            STANDARD_SLIPPAGE,
            dates_override=obs_dates,
            lightweight_outputs=True,
        )
        curve = result.equity_curve[["date", "equity"]].copy()
        state = stop_state(curve["equity"], curve["date"])
        final_marks = result.trades[result.trades.get("exit_reason", pd.Series(dtype=str)).eq("final_mark_to_market")] if not result.trades.empty else pd.DataFrame()
        symbols = ",".join(sorted(final_marks.get("symbol", pd.Series(dtype=str)).dropna().astype(str).unique())) if not final_marks.empty else "none_or_unavailable"
        status = status_row(
            run_id,
            start_date,
            end_date,
            "current_no_cash_proxy_alpha_AB",
            role,
            state,
            data_state,
            "engine_replayed_signal_snapshot_unavailable",
            symbols,
            "unavailable",
            len(result.trades),
        )
        daily = daily_log("current_no_cash_proxy_alpha_AB", role, curve, pd.DataFrame(index=pd.to_datetime(curve["date"])), "engine_replayed")
        snapshot = [
            {
                "as_of_date": end_date,
                "strategy": "current_no_cash_proxy_alpha_AB",
                "role": role,
                "symbol": "",
                "close": math.nan,
                "sma_200": math.nan,
                "above_sma_200": "",
                "signal": "unavailable",
                "target_weight": math.nan,
                "reason": "Existing A/B engine was replayed for equity, but it does not expose a compact latest-signal API here; no signal invented.",
                "data_quality_flag": "signal_snapshot_unavailable",
            }
        ]
        return status, daily, snapshot, len(result.trades)
    except Exception as exc:
        state = stop_state(pd.Series([STARTING_EQUITY]), pd.Index([pd.Timestamp(start_date)]))
        status = status_row(
            run_id,
            start_date,
            end_date,
            "current_no_cash_proxy_alpha_AB",
            role,
            state,
            "insufficient_data",
            "unavailable",
            "unavailable",
            "unavailable",
            0,
            interpretation=f"A/B replay unavailable: {exc}",
        )
        snapshot = [
            {
                "as_of_date": end_date,
                "strategy": "current_no_cash_proxy_alpha_AB",
                "role": role,
                "symbol": "",
                "close": math.nan,
                "sma_200": math.nan,
                "above_sma_200": "",
                "signal": "unavailable",
                "target_weight": math.nan,
                "reason": f"A/B replay unavailable: {exc}",
                "data_quality_flag": "insufficient_data",
            }
        ]
        return status, pd.DataFrame(), snapshot, 0


def load_combo_observation_config() -> dict[str, Any]:
    if not COMBO_CONFIG_PATH.exists():
        return {}
    with COMBO_CONFIG_PATH.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def combo_activation_status(config: dict[str, Any], data_state: str) -> str:
    if not config:
        return "activation_blocked_rule_hash_missing"
    if not bool(config.get("rule_hash_verified", False)) or not config.get("canonical_rule_hash"):
        return "activation_blocked_rule_hash_missing"
    if str(config.get("status", "")) in COMBO_BLOCKED_STATUSES:
        return str(config["status"])
    if data_state != "ok":
        return "active_waiting_for_next_cached_trading_day"
    return "active_paper_demo_observation"


def signal_snapshot_for_combo(role: str, full_prices: pd.DataFrame, weights: pd.DataFrame, as_of_date: pd.Timestamp) -> list[dict[str, Any]]:
    latest_weights = weights.loc[as_of_date] if as_of_date in weights.index else pd.Series(dtype=float)
    spy_signal, spy_close, spy_sma, spy_above, spy_reason = signal_for_spy_200d(full_prices, as_of_date)
    rows = [
        {
            "as_of_date": as_of_date.date().isoformat(),
            "strategy": COMBO_STRATEGY,
            "role": role,
            "symbol": "SPY",
            "close": spy_close,
            "sma_200": spy_sma,
            "above_sma_200": spy_above,
            "signal": f"spy_sleeve_{spy_signal}",
            "target_weight": float(latest_weights.get("SPY", 0.0)),
            "reason": f"SPY_200d sleeve: {spy_reason}",
            "data_quality_flag": "ok" if pd.notna(spy_close) and pd.notna(spy_sma) else "sma_or_close_unavailable",
        }
    ]
    for symbol, signal in [("GLD", "gld_buy_hold_sleeve"), ("BIL", "spy_sleeve_cash_fallback")]:
        close = float(full_prices[symbol].loc[as_of_date]) if symbol in full_prices and as_of_date in full_prices.index and pd.notna(full_prices[symbol].loc[as_of_date]) else math.nan
        rows.append(
            {
                "as_of_date": as_of_date.date().isoformat(),
                "strategy": COMBO_STRATEGY,
                "role": role,
                "symbol": symbol,
                "close": close,
                "sma_200": math.nan,
                "above_sma_200": "",
                "signal": signal if float(latest_weights.get(symbol, 0.0)) > 0 else "not_selected",
                "target_weight": float(latest_weights.get(symbol, 0.0)),
                "reason": "Combo target weight from fixed 50/50 SPY_200d and GLD sleeves.",
                "data_quality_flag": "ok" if pd.notna(close) else "close_unavailable",
            }
        )
    return rows


def build_combo_activation_outputs(
    run_id: str,
    start_date: str,
    end_date: str,
    data_state: str,
    full_prices: pd.DataFrame | None = None,
    observation_prices: pd.DataFrame | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    config = load_combo_observation_config()
    activation_status = combo_activation_status(config, data_state)
    role = "parallel_observation_candidate_blocked" if activation_status in COMBO_BLOCKED_STATUSES else "parallel_observation_candidate"
    if activation_status == "active_paper_demo_observation" and full_prices is not None and observation_prices is not None and not observation_prices.empty:
        curve, weights, rebalances = combo_curve_from_sleeves(full_prices, observation_prices)
        state = stop_state(curve["equity"], curve["date"])
        latest_weights = weights.iloc[-1] if not weights.empty else pd.Series(dtype=float)
        symbols, target_weights = position_text(latest_weights)
        row = status_row(
            run_id,
            start_date,
            end_date,
            COMBO_STRATEGY,
            role,
            state,
            "ok",
            "active_combo_observation",
            symbols,
            target_weights,
            rebalances,
            interpretation="Combo paper/demo observation is active as a separate simulated track; SPY_200d remains the frozen control and is not replaced.",
        )
        if row["status"] == "active_observation":
            row["status"] = "active_paper_demo_observation"
        daily = daily_log(COMBO_STRATEGY, role, curve, weights, "active_combo_observation")
        snapshots = signal_snapshot_for_combo(role, full_prices, weights, observation_prices.index[-1])
        row["_daily_log"] = daily
        return row, snapshots
    state = stop_state(pd.Series([STARTING_EQUITY]), pd.Index([pd.Timestamp(start_date)]))
    if activation_status == "activation_blocked_rule_hash_missing":
        interpretation = (
            "Combo paper/demo observation activation is blocked because the canonical rule hash is missing from existing evidence. "
            "SPY_200d remains the frozen control and is not replaced."
        )
        signal_state = "activation_blocked_rule_hash_missing"
        data_flag = "rule_hash_missing"
    elif activation_status in {"activation_waiting_for_data", "active_waiting_for_next_cached_trading_day"}:
        interpretation = (
            "Combo paper/demo observation is waiting for cached data after the requested activation date. "
            "No data was downloaded and no observation metrics were fabricated."
        )
        signal_state = "activation_waiting_for_data"
        data_flag = "waiting_for_cached_data"
    else:
        interpretation = (
            "Combo paper/demo observation activation gates are open, but active metrics were not computed because price data was unavailable."
        )
        signal_state = "active_combo_observation_unavailable"
        data_flag = "ok"
    row = status_row(
        run_id,
        start_date,
        end_date,
        COMBO_STRATEGY,
        role,
        state,
        activation_status,
        signal_state,
        "SPY,GLD,BIL",
        "unavailable",
        0,
        interpretation=interpretation,
    )
    snapshots = [
        {
            "as_of_date": end_date,
            "strategy": COMBO_STRATEGY,
            "role": role,
            "symbol": symbol,
            "close": math.nan,
            "sma_200": math.nan,
            "above_sma_200": "",
            "signal": signal_state,
            "target_weight": math.nan,
            "reason": interpretation,
            "data_quality_flag": data_flag,
        }
        for symbol in ["SPY", "GLD", "BIL"]
    ]
    return row, snapshots


def status_row(
    run_id: str,
    start_date: str,
    end_date: str,
    strategy: str,
    role: str,
    state: StopState,
    data_state: str,
    signal_state: str,
    current_position_symbols: str,
    current_target_weights: str,
    rebalances: int,
    interpretation: str = "",
) -> dict[str, Any]:
    current_equity = state.high_water_mark + state.current_drawdown_dollars
    status = status_from_stop(state, data_state)
    if not interpretation:
        if status == "stopped":
            interpretation = "Observation is stopped."
        elif status in COMBO_BLOCKED_STATUSES:
            interpretation = "Observation is blocked or waiting under the approved activation gates."
        else:
            interpretation = "Observation is active under fixed paper/demo rules."
    days_elapsed = max(0, len(pd.bdate_range(start_date, end_date)) - 1)
    return {
        "run_id": run_id,
        "observation_start_date": start_date,
        "observation_end_date": end_date,
        "strategy": strategy,
        "role": role,
        "starting_equity": STARTING_EQUITY,
        "current_equity": current_equity,
        "current_return": current_equity / STARTING_EQUITY - 1.0,
        "target_300_hit": state.target_300_hit,
        "target_300_date": state.target_300_date,
        "target_400_hit": state.target_400_hit,
        "target_400_date": state.target_400_date,
        "absolute_floor_stop_hit": state.absolute_floor_stop_hit,
        "trailing_drawdown_stop_hit": state.trailing_drawdown_stop_hit,
        "any_project_stop_hit": state.any_project_stop_hit,
        "first_project_stop_date": state.first_project_stop_date,
        "high_water_mark": state.high_water_mark,
        "current_drawdown_dollars": state.current_drawdown_dollars,
        "current_drawdown_pct": state.current_drawdown_pct,
        "max_drawdown_dollars": state.max_drawdown_dollars,
        "max_drawdown_pct": state.max_drawdown_pct,
        "stop_enforced_current_equity": state.stop_enforced_current_equity,
        "signal_state": signal_state,
        "current_position_symbols": current_position_symbols,
        "current_target_weights": current_target_weights,
        "last_signal_date": end_date,
        "last_rebalance_date": end_date if rebalances else "",
        "days_elapsed": days_elapsed,
        "status": status,
        "interpretation": interpretation,
    }


def daily_log(strategy: str, role: str, curve: pd.DataFrame, weights: pd.DataFrame, signal_state: str) -> pd.DataFrame:
    if curve.empty:
        return pd.DataFrame()
    out = curve.copy()
    out["date"] = pd.to_datetime(out["date"])
    out["strategy"] = strategy
    out["role"] = role
    out["daily_return"] = out["equity"].pct_change(fill_method=None).fillna(0.0)
    out["high_water_mark"] = out["equity"].cummax()
    out["drawdown_dollars"] = out["equity"] - out["high_water_mark"]
    out["drawdown_pct"] = out["drawdown_dollars"] / out["high_water_mark"].replace(0, np.nan)
    out["target_300_hit_to_date"] = out["equity"].cummax() >= TARGET_300
    out["target_400_hit_to_date"] = out["equity"].cummax() >= TARGET_400
    out["absolute_stop_hit_to_date"] = (out["equity"] <= ABSOLUTE_STOP).cummax()
    out["trailing_stop_hit_to_date"] = (out["equity"] <= out["high_water_mark"] - TRAILING_DRAWDOWN).cummax()
    symbols: list[str] = []
    target_weights: list[str] = []
    if not weights.empty:
        weights = weights.reindex(pd.to_datetime(out["date"])).fillna(0.0)
        for _, row in weights.iterrows():
            sym, wt = position_text(row)
            symbols.append(sym)
            target_weights.append(wt)
    else:
        symbols = ["unavailable"] * len(out)
        target_weights = ["unavailable"] * len(out)
    out["position_symbols"] = symbols
    out["target_weights"] = target_weights
    out["signal_state"] = signal_state
    out["notes"] = "paper-forward observation only; no live orders"
    out["date"] = out["date"].dt.date.astype(str)
    return out[
        [
            "date",
            "strategy",
            "role",
            "equity",
            "daily_return",
            "high_water_mark",
            "drawdown_dollars",
            "drawdown_pct",
            "target_300_hit_to_date",
            "target_400_hit_to_date",
            "absolute_stop_hit_to_date",
            "trailing_stop_hit_to_date",
            "position_symbols",
            "target_weights",
            "signal_state",
            "notes",
        ]
    ]


def signal_snapshot_for_benchmark(strategy: str, role: str, full_prices: pd.DataFrame, weights: pd.DataFrame, as_of_date: pd.Timestamp) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    latest_weights = weights.loc[as_of_date] if as_of_date in weights.index else pd.Series(dtype=float)
    if strategy == "SPY_200d_trend_model":
        signal, close, sma, above, reason = signal_for_spy_200d(full_prices, as_of_date)
        rows.append(
            {
                "as_of_date": as_of_date.date().isoformat(),
                "strategy": strategy,
                "role": role,
                "symbol": "SPY",
                "close": close,
                "sma_200": sma,
                "above_sma_200": above,
                "signal": signal,
                "target_weight": float(latest_weights.get("SPY", 0.0)),
                "reason": reason,
                "data_quality_flag": "ok" if pd.notna(close) and pd.notna(sma) else "sma_or_close_unavailable",
            }
        )
        rows.append(
            {
                "as_of_date": as_of_date.date().isoformat(),
                "strategy": strategy,
                "role": role,
                "symbol": "BIL",
                "close": float(full_prices["BIL"].loc[as_of_date]) if "BIL" in full_prices and as_of_date in full_prices.index and pd.notna(full_prices["BIL"].loc[as_of_date]) else math.nan,
                "sma_200": math.nan,
                "above_sma_200": "",
                "signal": "defensive_cash_proxy" if signal == "cash" else "not_selected",
                "target_weight": float(latest_weights.get("BIL", 0.0)),
                "reason": "BIL receives weight when SPY is below/at SMA200 or SPY SMA is unavailable.",
                "data_quality_flag": "ok",
            }
        )
        return rows
    symbol = "SPY" if strategy == "SPY_buy_hold" else "BIL"
    close = float(full_prices[symbol].loc[as_of_date]) if symbol in full_prices and as_of_date in full_prices.index and pd.notna(full_prices[symbol].loc[as_of_date]) else math.nan
    rows.append(
        {
            "as_of_date": as_of_date.date().isoformat(),
            "strategy": strategy,
            "role": role,
            "symbol": symbol,
            "close": close,
            "sma_200": math.nan,
            "above_sma_200": "",
            "signal": "hold_spy" if strategy == "SPY_buy_hold" else "hold_bil",
            "target_weight": float(latest_weights.get(symbol, 0.0)),
            "reason": "Fixed benchmark holding.",
            "data_quality_flag": "ok" if pd.notna(close) else "close_unavailable",
        }
    )
    return rows


def load_historical_baseline() -> dict[str, tuple[float, float, float, float, float]]:
    path = REPO_ROOT / "evidence" / "challenge_runs" / "latest" / "rolling_window_summary.csv"
    if not path.exists():
        return HISTORICAL_BASELINE
    try:
        rolling = pd.read_csv(path)
    except Exception:
        return HISTORICAL_BASELINE
    out = dict(HISTORICAL_BASELINE)
    subset = rolling[(rolling["horizon"].eq(90)) & (rolling["standard_or_stress"].eq("standard"))]
    for strategy in WATCHLIST:
        row = subset[subset["strategy"].eq(strategy)]
        if row.empty:
            continue
        r = row.iloc[0]
        out[strategy] = (
            float(r["pct_target_300_before_stop"]),
            float(r["pct_target_400_before_stop"]),
            float(r["pct_any_project_stop_hit"]),
            float(r["median_stop_enforced_final_equity"]),
            float(r["worst_max_drawdown"]),
        )
    return out


def benchmark_comparison(status: pd.DataFrame) -> pd.DataFrame:
    status = enrich_status_for_decisions(status)
    historical = load_historical_baseline()
    rows: list[dict[str, Any]] = []
    for _, row in status.iterrows():
        p300, p400, stop, median_equity, worst_dd = historical.get(row["strategy"], HISTORICAL_BASELINE[row["strategy"]])
        current_return = float(row["current_return"])
        comparison_status = current_vs_historical_status(row, median_equity)
        rows.append(
            {
                "strategy": row["strategy"],
                "role": row["role"],
                "current_return": current_return,
                "current_equity": row["current_equity"],
                "risk_framework_name": row.get("risk_framework_name", RISK_FRAMEWORK_NAME),
                "risk_band": row.get("risk_band", "normal"),
                "risk_framework_status": row.get("risk_framework_status", "active_normal"),
                "paper_forward_allowed_by_risk_framework": row.get("paper_forward_allowed_by_risk_framework", True),
                "historical_90d_pct_target_300_before_stop": p300,
                "historical_90d_pct_target_400_before_stop": p400,
                "historical_90d_pct_any_stop_hit": stop,
                "historical_90d_median_stop_enforced_equity": median_equity,
                "historical_90d_worst_drawdown": worst_dd,
                "current_vs_historical_status": comparison_status,
                "interpretation": "Historical rates are exact challenge-audit context, not a prediction or real-money validation.",
            }
        )
    return pd.DataFrame(rows)


def build_monthly_decision(status: pd.DataFrame, comparison: pd.DataFrame, run_id: str) -> pd.DataFrame:
    status = enrich_status_for_decisions(status)
    comparison = benchmark_comparison(status) if comparison.empty else comparison
    primary_rows = status[status["strategy"].eq("SPY_200d_trend_model")]
    if primary_rows.empty:
        return pd.DataFrame(columns=MONTHLY_DECISION_COLUMNS)
    primary = primary_rows.iloc[0]
    comparison_row = comparison[comparison["strategy"].eq("SPY_200d_trend_model")]
    comparison_status = (
        str(comparison_row.iloc[0]["current_vs_historical_status"])
        if not comparison_row.empty
        else str(primary.get("current_vs_historical_status", "unavailable"))
    )
    historical = load_historical_baseline()
    p300, p400, stop, median_equity, _worst_dd = historical["SPY_200d_trend_model"]

    def equity_for(strategy: str) -> float:
        row = status[status["strategy"].eq(strategy)]
        if row.empty:
            return math.nan
        return float(row.iloc[0]["current_equity"])

    spy_buy_hold_equity = equity_for("SPY_buy_hold")
    current_ab_equity = equity_for("current_no_cash_proxy_alpha_AB")
    bil_equity = equity_for("BIL_cash_proxy")
    primary_equity = float(primary["current_equity"])
    combo_equity = equity_for(COMBO_STRATEGY)

    decision = decision_status_for_row(primary)
    if decision == "stopped":
        reason = "Primary strategy hit a project stop; observation records the stop rather than changing rules."
    elif decision == "target_reached":
        reason = "+$400 target was hit before stop." if bool(primary["target_400_hit"]) else "+$300 target was hit before stop; aggressive +$400 target was not hit yet."
    elif decision == "inconclusive_too_early":
        reason = "Elapsed trading days are below 30, so the monthly checkpoint is too early for a decision."
    elif decision == "data_issue":
        reason = "Required paper-forward data or replay output is unavailable."
    else:
        reason = "No target or stop has been hit; continue frozen-rule observation."

    checkpoint_month = pd.Timestamp(primary["observation_end_date"]).strftime("%Y-%m")
    row = {
        "checkpoint_month": checkpoint_month,
        "latest_run_id": run_id,
        "observation_start_date": primary["observation_start_date"],
        "latest_observation_end_date": primary["observation_end_date"],
        "primary_strategy": "SPY_200d_trend_model",
        "primary_current_equity": primary_equity,
        "primary_current_return": primary["current_return"],
        "primary_target_300_distance": primary["target_300_distance"],
        "primary_target_400_distance": primary["target_400_distance"],
        "primary_distance_to_absolute_stop": primary["distance_to_absolute_stop"],
        "primary_distance_to_trailing_stop": primary["distance_to_trailing_stop"],
        "primary_risk_band": primary["risk_band"],
        "primary_signal_state": primary["signal_state"],
        "primary_status": primary["status"],
        "spy_buy_hold_equity": spy_buy_hold_equity,
        "current_no_cash_proxy_alpha_AB_equity": current_ab_equity,
        "bil_cash_proxy_equity": bil_equity,
        "primary_vs_spy_buy_hold": primary_equity - spy_buy_hold_equity if pd.notna(spy_buy_hold_equity) else math.nan,
        "primary_vs_current_no_cash_proxy_alpha_AB": primary_equity - current_ab_equity if pd.notna(current_ab_equity) else math.nan,
        "primary_vs_bil": primary_equity - bil_equity if pd.notna(bil_equity) else math.nan,
        "primary_vs_spy200d_control": 0.0,
        "combo_observation_status": str(status.loc[status["strategy"].eq(COMBO_STRATEGY), "status"].iloc[0]) if COMBO_STRATEGY in set(status["strategy"]) else "not_included",
        "combo_replaces_spy200d": False,
        "historical_90d_target_300_before_stop": p300,
        "historical_90d_target_400_before_stop": p400,
        "historical_90d_any_stop_hit": stop,
        "historical_90d_median_stop_equity": median_equity,
        "current_vs_historical_interpretation": comparison_status,
        "decision": decision,
        "decision_reason": reason,
        "forbidden_actions": "change_rules;tune_parameters;real_money_trading;broker_integration;add_diagnostic_rows_to_paper_forward",
    }
    rows = [row]
    combo_rows = status[status["strategy"].eq(COMBO_STRATEGY)]
    if not combo_rows.empty:
        combo = combo_rows.iloc[0]
        combo_decision = decision_status_for_row(combo)
        if combo_decision == "activation_blocked_rule_hash_missing":
            combo_reason = "Combo activation is blocked because canonical_rule_hash is missing; SPY_200d remains frozen control."
        elif combo_decision in {"activation_waiting_for_data", "active_waiting_for_next_cached_trading_day"}:
            combo_reason = "Combo activation is waiting for cached data after the requested activation date; no data download was performed."
        elif combo_decision == "data_issue":
            combo_reason = "Combo observation has a data issue and cannot be judged."
        else:
            combo_reason = "Combo observation is included beside SPY_200d; no judgment is allowed before 30 trading days."
        cp300, cp400, cstop, cmedian, _cworst = historical.get(COMBO_STRATEGY, HISTORICAL_BASELINE[COMBO_STRATEGY])
        rows.append(
            {
                "checkpoint_month": checkpoint_month,
                "latest_run_id": run_id,
                "observation_start_date": combo["observation_start_date"],
                "latest_observation_end_date": combo["observation_end_date"],
                "primary_strategy": COMBO_STRATEGY,
                "primary_current_equity": float(combo["current_equity"]),
                "primary_current_return": combo["current_return"],
                "primary_target_300_distance": combo["target_300_distance"],
                "primary_target_400_distance": combo["target_400_distance"],
                "primary_distance_to_absolute_stop": combo["distance_to_absolute_stop"],
                "primary_distance_to_trailing_stop": combo["distance_to_trailing_stop"],
                "primary_risk_band": combo["risk_band"],
                "primary_signal_state": combo["signal_state"],
                "primary_status": combo["status"],
                "spy_buy_hold_equity": spy_buy_hold_equity,
                "current_no_cash_proxy_alpha_AB_equity": current_ab_equity,
                "bil_cash_proxy_equity": bil_equity,
                "primary_vs_spy_buy_hold": float(combo["current_equity"]) - spy_buy_hold_equity if pd.notna(spy_buy_hold_equity) else math.nan,
                "primary_vs_current_no_cash_proxy_alpha_AB": float(combo["current_equity"]) - current_ab_equity if pd.notna(current_ab_equity) else math.nan,
                "primary_vs_bil": float(combo["current_equity"]) - bil_equity if pd.notna(bil_equity) else math.nan,
                "primary_vs_spy200d_control": float(combo["current_equity"]) - primary_equity,
                "combo_observation_status": combo["status"],
                "combo_replaces_spy200d": False,
                "historical_90d_target_300_before_stop": cp300,
                "historical_90d_target_400_before_stop": cp400,
                "historical_90d_any_stop_hit": cstop,
                "historical_90d_median_stop_equity": cmedian,
                "current_vs_historical_interpretation": str(combo.get("current_vs_historical_status", "unavailable")),
                "decision": combo_decision,
                "decision_reason": combo_reason,
                "forbidden_actions": "replace_spy200d;change_rules;tune_parameters;real_money_trading;broker_integration;place_live_orders",
            }
        )
    return pd.DataFrame(rows, columns=MONTHLY_DECISION_COLUMNS)


def checkpoint_history_frame(status: pd.DataFrame, run_id: str, checkpoint_timestamp_utc: str | None = None) -> pd.DataFrame:
    status = enrich_status_for_decisions(status)
    timestamp = checkpoint_timestamp_utc or utc_timestamp()
    rows: list[dict[str, Any]] = []
    for _, row in status.iterrows():
        rows.append(
            {
                "checkpoint_timestamp_utc": timestamp,
                "run_id": run_id,
                "observation_start_date": row["observation_start_date"],
                "observation_end_date": row["observation_end_date"],
                "strategy": row["strategy"],
                "role": row["role"],
                "current_equity": row["current_equity"],
                "current_return": row["current_return"],
                "target_300_hit": row["target_300_hit"],
                "target_400_hit": row["target_400_hit"],
                "any_project_stop_hit": row["any_project_stop_hit"],
                "first_project_stop_date": row["first_project_stop_date"],
                "high_water_mark": row["high_water_mark"],
                "current_drawdown_dollars": row["current_drawdown_dollars"],
                "current_drawdown_pct": row["current_drawdown_pct"],
                "max_drawdown_dollars": row["max_drawdown_dollars"],
                "target_300_distance": row["target_300_distance"],
                "target_400_distance": row["target_400_distance"],
                "distance_to_absolute_stop": row["distance_to_absolute_stop"],
                "distance_to_trailing_stop": row["distance_to_trailing_stop"],
                "risk_band": row["risk_band"],
                "risk_budget_used_pct": row["risk_budget_used_pct"],
                "target_300_progress_pct": row["target_300_progress_pct"],
                "target_400_progress_pct": row["target_400_progress_pct"],
                "signal_state": row["signal_state"],
                "current_position_symbols": row["current_position_symbols"],
                "status": row["status"],
                "notes": row.get("interpretation", "Paper-forward checkpoint only; not a trading signal."),
            }
        )
    return pd.DataFrame(rows, columns=CHECKPOINT_COLUMNS)


def update_checkpoint_outputs(status: pd.DataFrame, monthly_decision: pd.DataFrame, run_id: str) -> tuple[Path, Path]:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    checkpoint_path = OUTPUT_ROOT / CHECKPOINT_HISTORY_NAME
    monthly_path = OUTPUT_ROOT / MONTHLY_DECISION_NAME

    checkpoints = checkpoint_history_frame(status, run_id)
    if checkpoint_path.exists():
        existing = pd.read_csv(checkpoint_path)
        combined = pd.concat([existing, checkpoints], ignore_index=True)
    else:
        combined = checkpoints
    combined = combined.reindex(columns=CHECKPOINT_COLUMNS)
    combined = combined.drop_duplicates(subset=["run_id", "strategy"], keep="last")
    combined.to_csv(checkpoint_path, index=False)

    monthly_decision = monthly_decision.reindex(columns=MONTHLY_DECISION_COLUMNS)
    if monthly_path.exists():
        existing_monthly = pd.read_csv(monthly_path)
        if not monthly_decision.empty:
            current_month = str(monthly_decision.iloc[0]["checkpoint_month"])
            existing_monthly = existing_monthly[~existing_monthly["checkpoint_month"].astype(str).eq(current_month)]
        monthly_combined = pd.concat([existing_monthly, monthly_decision], ignore_index=True)
    else:
        monthly_combined = monthly_decision
    monthly_combined = monthly_combined.reindex(columns=MONTHLY_DECISION_COLUMNS)
    monthly_combined.to_csv(monthly_path, index=False)
    return checkpoint_path, monthly_path


def risk_status(status: pd.DataFrame) -> pd.DataFrame:
    status = enrich_status_for_decisions(status)
    rows = []
    for _, row in status.iterrows():
        high = float(row["high_water_mark"])
        current = float(row["current_equity"])
        target_300_distance = TARGET_300 - current
        target_400_distance = TARGET_400 - current
        distance_to_absolute_stop = current - ABSOLUTE_STOP
        distance_to_trailing_stop = current - (high - TRAILING_DRAWDOWN)
        if bool(row["any_project_stop_hit"]):
            risk_reward_position = "stopped"
        elif bool(row["target_300_hit"]) or bool(row["target_400_hit"]):
            risk_reward_position = "target_reached"
        else:
            nearest_stop = min(distance_to_absolute_stop, distance_to_trailing_stop)
            if abs(target_300_distance - nearest_stop) <= 25.0:
                risk_reward_position = "neutral"
            elif target_300_distance < nearest_stop:
                risk_reward_position = "closer_to_target"
            else:
                risk_reward_position = "closer_to_stop"
        item = {
            "strategy": row["strategy"],
            "role": row["role"],
            "current_equity": current,
            "high_water_mark": high,
            "current_drawdown_dollars": row["current_drawdown_dollars"],
            "current_drawdown_pct": row["current_drawdown_pct"],
            "distance_to_absolute_stop": distance_to_absolute_stop,
            "distance_to_trailing_stop": distance_to_trailing_stop,
            "distance_to_target_300": target_300_distance,
            "distance_to_target_400": target_400_distance,
            "target_300_distance": target_300_distance,
            "target_400_distance": target_400_distance,
            "max_drawdown_dollars": row["max_drawdown_dollars"],
            "any_project_stop_hit": row["any_project_stop_hit"],
            "risk_reward_position": risk_reward_position,
            "notes": "Distances are paper/demo observation metrics only.",
        }
        item["risk_status"] = "activation_blocked" if str(row.get("status", "")) in COMBO_BLOCKED_STATUSES else risk_label(pd.Series(item))
        item.update(risk_framework_fields(row))
        rows.append(item)
    return pd.DataFrame(rows)[
        [
            "strategy",
            "role",
            "current_equity",
            "high_water_mark",
            "current_drawdown_dollars",
            "current_drawdown_pct",
            "distance_to_absolute_stop",
            "distance_to_trailing_stop",
            "distance_to_target_300",
            "distance_to_target_400",
            "target_300_distance",
            "target_400_distance",
            "max_drawdown_dollars",
            "any_project_stop_hit",
            "risk_status",
            "risk_reward_position",
            "risk_framework_name",
            "risk_band",
            "risk_budget_used_pct",
            "target_300_progress_pct",
            "target_400_progress_pct",
            "drawdown_warning_hit",
            "drawdown_review_hit",
            "hard_stop_hit",
            "risk_framework_status",
            "paper_forward_allowed_by_risk_framework",
            "notes",
        ]
    ]


def build_assumptions(start_date: str, end_date: str, cache_note: str, no_network: bool, include_combo_observation: bool = False) -> dict[str, Any]:
    strategies = dict(WATCHLIST)
    if include_combo_observation:
        strategies[COMBO_STRATEGY] = "parallel_observation_candidate"
    combo_config = load_combo_observation_config() if include_combo_observation else {}
    return {
        "paper_demo_only": True,
        "broker_integration": False,
        "live_orders": False,
        "real_money_recommendation": False,
        "risk_framework": {
            "name": RISK_FRAMEWORK_NAME,
            "primary_challenge_target": TARGET_300,
            "aggressive_challenge_target": TARGET_400,
            "warning_drawdown_dollars": 300,
            "review_drawdown_dollars": 450,
            "hard_stop_drawdown_dollars": TRAILING_DRAWDOWN,
        },
        "observation_start_date": start_date,
        "observation_end_date": end_date,
        "starting_equity": STARTING_EQUITY,
        "target_300_equity": TARGET_300,
        "target_400_equity": TARGET_400,
        "absolute_stop_equity": ABSOLUTE_STOP,
        "trailing_drawdown_dollars": TRAILING_DRAWDOWN,
        "project_stop_mode": "both",
        "strategies": strategies,
        "combo_observation_requested": include_combo_observation,
        "combo_observation_status": combo_config.get("status", "not_requested") if include_combo_observation else "not_requested",
        "combo_rule_hash_verified": bool(combo_config.get("rule_hash_verified", False)) if include_combo_observation else False,
        "combo_canonical_rule_hash": combo_config.get("canonical_rule_hash", "") if include_combo_observation else "",
        "combo_replaces_spy200d": False,
        "data_source": "existing adjusted ETF cache; optional yfinance refresh only when requested",
        "cache_usage": cache_note,
        "network_disabled": no_network,
        "slippage_cost_assumption": STANDARD_SLIPPAGE,
        "limitations": [
            "Paper-forward observation only.",
            "No broker, no orders, no real-money recommendation.",
            "Yahoo/yfinance cache limitations apply.",
            "current_no_cash_proxy_alpha_AB latest signal extraction is unavailable in compact mode; equity is replayed with fixed rules.",
        ],
    }


def markdown_table(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "No rows."
    columns = list(frame.columns)
    lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join(["---"] * len(columns)) + " |"]
    for _, row in frame.iterrows():
        values = []
        for col in columns:
            value = row[col]
            if isinstance(value, float):
                value = f"{value:.4f}"
            values.append(str(value).replace("\n", " "))
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def build_summary(run_id: str, status: pd.DataFrame, signals: pd.DataFrame, comparison: pd.DataFrame, risk: pd.DataFrame, assumptions: dict[str, Any]) -> str:
    status = enrich_status_for_decisions(status)
    comparison = benchmark_comparison(status)
    risk = risk_status(status)
    monthly_decision = build_monthly_decision(status, comparison, run_id)
    status_table = markdown_table(status[["strategy", "role", "current_equity", "current_return", "status", "signal_state", "current_position_symbols"]])
    signal_table = markdown_table(signals[["strategy", "symbol", "signal", "target_weight", "reason", "data_quality_flag"]])
    risk_table = markdown_table(risk[["strategy", "risk_status", "current_equity", "target_300_distance", "distance_to_trailing_stop", "max_drawdown_dollars"]])
    framework_table = markdown_table(
        risk[["strategy", "risk_framework_status", "risk_band", "risk_budget_used_pct", "target_300_progress_pct", "target_400_progress_pct"]]
    )
    comparison_table = markdown_table(comparison[["strategy", "current_vs_historical_status", "historical_90d_pct_target_300_before_stop", "historical_90d_pct_any_stop_hit"]])
    monthly_table = markdown_table(
        monthly_decision[
            [
                "checkpoint_month",
                "latest_observation_end_date",
                "primary_strategy",
                "primary_current_equity",
                "primary_target_300_distance",
                "primary_target_400_distance",
                "primary_distance_to_absolute_stop",
                "primary_distance_to_trailing_stop",
                "primary_risk_band",
                "decision",
                "decision_reason",
            ]
        ]
    )
    historical_table = markdown_table(
        comparison[
            [
                "strategy",
                "historical_90d_pct_target_300_before_stop",
                "historical_90d_pct_target_400_before_stop",
                "historical_90d_pct_any_stop_hit",
                "historical_90d_median_stop_enforced_equity",
                "historical_90d_worst_drawdown",
                "current_vs_historical_status",
            ]
        ]
    )
    primary = status[status["strategy"].eq("SPY_200d_trend_model")].iloc[0]
    closest = risk.sort_values("target_300_distance").iloc[0]
    largest_dd = risk.sort_values("max_drawdown_dollars").iloc[0]
    active = not status["status"].isin(["stopped", "insufficient_data", "no_new_data", *COMBO_BLOCKED_STATUSES]).all()
    combo_rows = status[status["strategy"].eq(COMBO_STRATEGY)]
    if combo_rows.empty:
        combo_section = "Combo observation was not requested in this run."
    else:
        combo = combo_rows.iloc[0]
        spy_diff = float(combo["current_equity"]) - float(primary["current_equity"])
        if str(combo["status"]) in COMBO_BLOCKED_STATUSES:
            activation_note = "Full active combo observation is not active unless the canonical rule hash is verified and cached data supports the requested activation date."
        else:
            activation_note = "Combo is active as a separate simulated paper/demo observation because the canonical rule hash is verified and cached data supports the requested activation date."
        combo_section = (
            f"- combo_strategy: {COMBO_STRATEGY}\n"
            f"- combo_status: {combo['status']}\n"
            f"- combo_rule_hash_verified: {assumptions.get('combo_rule_hash_verified', False)}\n"
            f"- combo_canonical_rule_hash: {assumptions.get('combo_canonical_rule_hash') or 'missing'}\n"
            "- combo_replaces_spy200d: false\n"
            "- SPY_200d_frozen_control: true\n"
            f"- combo_current_equity_if_available: ${float(combo['current_equity']):,.2f}\n"
            f"- combo_distance_to_300_if_available: ${float(TARGET_300 - combo['current_equity']):,.2f}\n"
            f"- combo_distance_to_400_if_available: ${float(TARGET_400 - combo['current_equity']):,.2f}\n"
            f"- combo_distance_to_stop_if_available: ${float(combo['current_equity'] - ABSOLUTE_STOP):,.2f}\n"
            f"- combo_vs_spy200d_equity_difference: ${spy_diff:,.2f}\n"
            "- start_date_accounting: first observation row excludes pre-start returns; active equity may differ from $3,000 because initialization/rebalance costs are applied.\n"
            f"- activation_note: {activation_note}"
        )
    final = (
        f"SPY_200d_trend_model is {primary['status']} with equity ${float(primary['current_equity']):,.2f}. "
        f"It is ${float(TARGET_300 - primary['current_equity']):,.2f} from +$300 and "
        f"${float(primary['current_equity'] - (primary['high_water_mark'] - TRAILING_DRAWDOWN)):,.2f} above the trailing stop. "
        "No real-money action is implied."
    )
    return f"""# Paper-Forward Observation Summary

## 1. Research-Only Statement

This is paper/demo observation only. It does not recommend real-money trading, does not connect to a broker, and does not place orders.

## 2. Run Identity

- run_id: {run_id}
- output: `evidence/paper_forward_runs/runs/{run_id}/`
- compact file count: 10

## 3. Observation Period

- start: {assumptions['observation_start_date']}
- end: {assumptions['observation_end_date']}

## 4. Strategies Observed

{", ".join(status["strategy"].astype(str).tolist())}. Each row has its own independent $3,000 simulated paper account when active. Blocked rows are recorded as governance evidence only.

## 5. Current Status Table

{status_table}

## 6. Current Signals

{signal_table}

## 7. Distance To +300/+400 Targets

{risk_table}

## 8. Distance To Stops

See `risk_status.csv`; stop mode is both absolute floor $2,400 and high-water mark minus $600.

## 9. Historical 90-Day Context

{comparison_table}

## 10. Risk Framework Status

{framework_table}

SPY_200d_trend_model remains governed by `{RISK_FRAMEWORK_NAME}`. The observation should continue only while fixed rules remain unchanged and the row stays inside the project stop framework.

## 11. Monthly Decision Checkpoint

{monthly_table}

The checkpoint is a decision aid only. It forbids rule changes, parameter tuning, real-money trading, broker integration, and adding diagnostic rows to the active paper-forward observation.

## 12. Historical Expectation Comparison

{historical_table}

The historical context comes from the exact compact challenge audit baseline. It is not a prediction and does not validate real-money use.

## 13. Combo Parallel Observation Status

{combo_section}

The combo does not replace SPY_200d. SPY_200d remains the frozen paper-forward control until a separate governance decision says otherwise.

## 14. Rule Or Data Issues

current_no_cash_proxy_alpha_AB equity was replayed with existing fixed rules, but compact latest-signal extraction is marked unavailable rather than invented.

The combo row must not become active without a verified canonical rule hash and cached data through the observation start date. No data was downloaded in this run.

## 15. Observation Active?

{active}

## 16. Success Criteria

Success is reaching +$300 or +$400 before either project stop, while fixed rules remain unchanged.

## 17. Failure Criteria

Failure is hitting the absolute or trailing project stop, or discovering data/signal extraction problems that make the observation unauditable.

## 18. Final Current Conclusion

{final}

Closest to +$300: {closest['strategy']}. Largest drawdown so far: {largest_dd['strategy']}. This remains research-only paper observation.
"""


def build_warnings() -> str:
    return """# Warnings And Limitations

- Research-only paper/demo statement.
- No real-money recommendation.
- No broker integration.
- No live orders.
- This is paper-forward observation, not live trading.
- It does not validate a strategy.
- It observes fixed rules only.
- combo_SPY200d_GLD_50_50_v1, if included, is a separate paper/demo observation candidate and does not replace SPY_200d.
- Combo observation would be blocked if canonical_rule_hash is missing or required cached data is stale; blocked/waiting rows are not trading signals.
- Start-date accounting excludes pre-start returns; first-row active equity may reflect initialization/rebalance costs only.
- It should not trigger real trades.
- yfinance/Yahoo data limitations apply.
- Paper fills and simplified accounting are used.
- Taxes ignored.
- Cash yield simplified.
- Signals may differ from broker charts.
- current_no_cash_proxy_alpha_AB signal extraction may be limited if not available exactly.
- SPY_200d is a simple benchmark-like strategy, not a guaranteed edge.
- Hitting +300 or +400 once is not proof of reliability.
- Stopping out is valid evidence, not a reason to tune rules.
- Monthly checkpoints are decision aids, not trading signals.
- A checkpoint stop is evidence, not permission to redesign the rules.
- Exposure frontier and volatility-control diagnostics are not part of paper-forward observation.
- Risk Framework v1 applies +$300 as the primary challenge target, +$400 as aggressive, -10% as warning, -15% as review, and -20%/-$600 as hard stop.
- Paper-forward rows remain frozen and should not be changed in response to warning or review bands.
"""


def build_readme() -> str:
    return """# README For Advisor

This is the compact paper-forward observation packet. It contains exactly the 10 decision-focused files listed in the project instructions.

Read `paper_forward_summary.md` first, then `paper_forward_status.csv`, `risk_status.csv`, `signal_snapshot.csv`, `benchmark_comparison.csv`, and the checkpoint files.

This is research-only paper/demo observation. It does not place orders, does not connect to brokers, and is not a real-money recommendation.
"""


def write_chart(path: Path, daily: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(11, 8), sharex=True)
    if daily.empty:
        axes[0].text(0.5, 0.5, "No paper-forward daily data", ha="center")
    else:
        for strategy, group in daily.groupby("strategy"):
            dates = pd.to_datetime(group["date"])
            axes[0].plot(dates, group["equity"], label=strategy)
            axes[1].plot(dates, group["drawdown_dollars"], label=strategy)
        axes[0].axhline(TARGET_300, color="green", linestyle="--", linewidth=1, label="$3,300")
        axes[0].axhline(TARGET_400, color="darkgreen", linestyle="--", linewidth=1, label="$3,400")
        axes[0].axhline(ABSOLUTE_STOP, color="red", linestyle="--", linewidth=1, label="$2,400")
        axes[0].set_title("Paper-Forward Equity")
        axes[1].axhline(-TRAILING_DRAWDOWN, color="red", linestyle="--", linewidth=1)
        axes[1].set_title("Paper-Forward Drawdown Dollars")
        axes[0].legend(fontsize=8)
    plt.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def build_manifest(run_id: str, status: pd.DataFrame, assumptions: dict[str, Any], file_count: int) -> dict[str, Any]:
    combo_rows = status[status["strategy"].eq(COMBO_STRATEGY)]
    combo_status = str(combo_rows.iloc[0]["status"]) if not combo_rows.empty else "not_included"
    return {
        "run_id": run_id,
        "created_at_utc": utc_timestamp(),
        "paper_demo_only": True,
        "combo_observation_included": not combo_rows.empty,
        "combo_observation_status": combo_status,
        "combo_paper_forward_active": combo_status not in {
            "not_included",
            "insufficient_data",
            "no_new_data",
            *COMBO_BLOCKED_STATUSES,
        },
        "combo_replaces_spy200d": False,
        "spy200d_frozen_control": True,
        "rule_hash_verified": bool(assumptions.get("combo_rule_hash_verified", False)),
        "canonical_rule_hash": assumptions.get("combo_canonical_rule_hash", ""),
        "data_downloaded": False,
        "backtest_run": False,
        "profit_exploration_run": False,
        "strategy_rules_changed": False,
        "broker_integration": False,
        "live_orders": False,
        "order_placement": False,
        "real_money_recommendation": False,
        "raw_data_included": False,
        "latest_folder_file_count": file_count,
    }


def write_outputs(
    run_id: str,
    status: pd.DataFrame,
    daily: pd.DataFrame,
    signals: pd.DataFrame,
    comparison: pd.DataFrame,
    assumptions: dict[str, Any],
    risk: pd.DataFrame,
) -> tuple[Path, Path]:
    run_dir = OUTPUT_ROOT / "runs" / run_id
    latest_dir = OUTPUT_ROOT / "latest"
    if latest_dir.exists():
        shutil.rmtree(latest_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    status = enrich_status_for_decisions(status)
    comparison = benchmark_comparison(status)
    risk = risk_status(status)
    monthly_decision = build_monthly_decision(status, comparison, run_id)
    checkpoints = checkpoint_history_frame(status, run_id)
    (run_dir / "README_FOR_ADVISOR.md").write_text(build_readme(), encoding="utf-8")
    (run_dir / "paper_forward_summary.md").write_text(build_summary(run_id, status, signals, comparison, risk, assumptions), encoding="utf-8")
    status.to_csv(run_dir / "paper_forward_status.csv", index=False)
    del daily
    signals.to_csv(run_dir / "signal_snapshot.csv", index=False)
    comparison.to_csv(run_dir / "benchmark_comparison.csv", index=False)
    risk.to_csv(run_dir / "risk_status.csv", index=False)
    checkpoints.to_csv(run_dir / CHECKPOINT_HISTORY_NAME, index=False)
    monthly_decision.to_csv(run_dir / MONTHLY_DECISION_NAME, index=False)
    (run_dir / "warnings_and_limitations.md").write_text(build_warnings(), encoding="utf-8")
    (run_dir / "paper_forward_manifest.json").write_text(
        json.dumps(build_manifest(run_id, status, assumptions, len(REQUIRED_FILES)), indent=2) + "\n",
        encoding="utf-8",
    )
    files = [p.name for p in run_dir.iterdir() if p.is_file()]
    extra = sorted(set(files) - set(REQUIRED_FILES))
    missing = sorted(set(REQUIRED_FILES) - set(files))
    if extra or missing or len(files) > 10:
        raise RuntimeError(f"Paper-forward output contract failed. extra={extra} missing={missing} file_count={len(files)}")
    shutil.copytree(run_dir, latest_dir)
    if LATEST_ZIP.exists():
        LATEST_ZIP.unlink()
    with zipfile.ZipFile(LATEST_ZIP, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(latest_dir.iterdir()):
            if path.is_file():
                zf.write(path, path.name)
    update_checkpoint_outputs(status, monthly_decision, run_id)
    return run_dir, latest_dir


def run_observation(args: argparse.Namespace) -> tuple[Path, Path]:
    cache_note = maybe_refresh_cache(args.no_network, args.force_refresh)
    cache_symbols = ["SPY", "BIL"]
    if getattr(args, "include_combo_observation", False):
        cache_symbols.append("GLD")
    prices_long = load_adjusted_price_cache(cache_symbols)
    prices = prices_long.pivot(index="date", columns="symbol", values="close").sort_index().ffill()
    if args.start_date is None:
        raise SystemExit("--start-date is required for this first paper-forward observation run.")
    start = normalize_date(args.start_date)
    end_arg = normalize_date(args.end_date)
    observation_prices, observed_start, observed_end, data_state = select_observation_prices(prices, start or "", end_arg)
    run_id = utc_run_id()
    status_rows: list[dict[str, Any]] = []
    daily_frames: list[pd.DataFrame] = []
    signal_rows: list[dict[str, Any]] = []
    for strategy in ["SPY_200d_trend_model", "SPY_buy_hold", "BIL_cash_proxy"]:
        row, daily, snapshot, _turnover, _rebalances = build_benchmark_outputs(
            run_id,
            prices,
            observation_prices,
            strategy,
            WATCHLIST[strategy],
            observed_start,
            observed_end,
            data_state,
        )
        status_rows.append(row)
        if not daily.empty:
            daily_frames.append(daily)
        signal_rows.extend(snapshot)
    current_row, current_daily, current_snapshot, _current_trades = build_current_ab_outputs(run_id, observed_start, observed_end, data_state)
    status_rows.append(current_row)
    if not current_daily.empty:
        daily_frames.append(current_daily)
    signal_rows.extend(current_snapshot)
    if getattr(args, "include_combo_observation", False):
        combo_row, combo_snapshot = build_combo_activation_outputs(run_id, observed_start, observed_end, data_state, prices, observation_prices)
        combo_daily = combo_row.pop("_daily_log", pd.DataFrame())
        status_rows.append(combo_row)
        if isinstance(combo_daily, pd.DataFrame) and not combo_daily.empty:
            daily_frames.append(combo_daily)
        signal_rows.extend(combo_snapshot)
    status = apply_risk_framework_to_status(pd.DataFrame(status_rows))
    daily_log_frame = pd.concat(daily_frames, ignore_index=True) if daily_frames else pd.DataFrame()
    signals = pd.DataFrame(signal_rows)
    comparison = benchmark_comparison(status)
    risk = risk_status(status)
    assumptions = build_assumptions(observed_start, observed_end, cache_note, args.no_network, getattr(args, "include_combo_observation", False))
    return write_outputs(run_id, status, daily_log_frame, signals, comparison, assumptions, risk)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run compact paper-forward ETF observation.")
    parser.add_argument("--start-date", default=None)
    parser.add_argument("--end-date", default="latest")
    parser.add_argument("--reuse-cache", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--force-refresh", action="store_true")
    parser.add_argument("--no-network", action="store_true")
    parser.add_argument("--update-existing", action="store_true")
    parser.add_argument("--max-lookback-days", type=int, default=0)
    parser.add_argument("--include-combo-observation", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    del args.reuse_cache, args.update_existing, args.max_lookback_days
    run_dir, latest_dir = run_observation(args)
    print(f"paper_forward_run_dir={run_dir}")
    print(f"paper_forward_latest_dir={latest_dir}")
    print(f"paper_forward_file_count={len([p for p in latest_dir.iterdir() if p.is_file()])}")
    print("real_money_recommendation=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
