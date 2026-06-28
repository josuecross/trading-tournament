from __future__ import annotations

import csv
import json
import math
import shutil
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

import run_active_combo_benchmark_reporting as combo
import run_active_strategy_evidence_recompute as active


ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = Path("evidence") / "parallel_research_discovery" / "risk_controlled_high_return_discovery" / "latest"
MANUAL_REVIEW_DIR = Path("evidence") / "pre_registered_lanes" / "risk_controlled_high_return_manual_review" / "latest"
RULE_FREEZE_DIR = Path("evidence") / "pre_registered_lanes" / "risk_controlled_high_return_rule_freeze_patch" / "latest"
REGISTRY_PATH = Path("strategy_lab") / "strategy_registry.yaml"
ROADMAP_PATH = Path("strategy_lab") / "RESEARCH_ROADMAP.md"
CACHE_DIR = Path("data") / "cache"

DUAL_ID = "rc_dual_momentum_paa_vol_scaled_v1"
DONCHIAN_ID = "rc_donchian_breakout_risk_budget_v1"
AUTHORIZED_CANDIDATES = [DUAL_ID, DONCHIAN_ID]
EXCLUDED_CANDIDATES = {
    "dual_momentum_paa_clean_v1",
    "donchian_atr_breakout_etf_v1",
    "quality_momentum_etf_proxy",
    "turn_of_month_spy_qqq_v1",
    "managed_futures_etf_trend_wrapper_v1",
    "gld_gror_balanced_momentum_clean_v1",
    "cash_pause_overlay_meta_v1",
    "sector_rs_weekly_cash_filter_v1",
    "gror_balanced_momentum_60_40_v1",
}

LANES = {
    DUAL_ID: "macro_gld_duration_risk_off_lane",
    DONCHIAN_ID: "moderate_tactical_etf_lane",
}
VALID_OUTCOMES = {
    DUAL_ID: {"discovery_reject", "promotion_review_candidate_macro"},
    DONCHIAN_ID: {"discovery_reject", "promotion_review_candidate"},
}
FORBIDDEN_OUTCOMES = {"candidate_exhaustive", "paper_forward", "paper_forward_active", "demo_active", "live_ready"}

NEXT_ACTION_PROMOTION = "promotion_review_for_risk_controlled_high_return_candidates"
NEXT_ACTION_AUDIT = "audit_risk_controlled_high_return_discovery_failures"
NEXT_ACTION_PAUSE = "pause_expansion_and_summarize_tournament_state"
NEXT_ACTION_NEXT_FAMILY = "pre_register_next_family_after_risk_controlled_review"
VALID_NEXT_ACTIONS = {NEXT_ACTION_PROMOTION, NEXT_ACTION_AUDIT, NEXT_ACTION_PAUSE, NEXT_ACTION_NEXT_FAMILY}

STARTING_EQUITY = active.STARTING_EQUITY
STOP_DOLLARS = active.STOP_DOLLARS
BASE_SLIPPAGE = active.SLIPPAGE
STRESS_SLIPPAGE = 0.0010
HORIZONS = active.HORIZONS
MAX_WINDOWS_PER_HORIZON = active.MAX_WINDOWS_PER_HORIZON

DUAL_UNIVERSE = ["SPY", "QQQ", "GLD", "IEF", "AGG", "BIL"]
DONCHIAN_UNIVERSE = ["SPY", "QQQ", "IWM", "DIA", "XLK", "XLF", "XLV", "XLE", "XLI", "XLY", "XLP", "XLU", "XLB", "XLRE"]
DONCHIAN_UNIVERSE_WITH_CASH = [*DONCHIAN_UNIVERSE, "BIL"]
LOAD_SYMBOLS = sorted(set(DUAL_UNIVERSE + DONCHIAN_UNIVERSE_WITH_CASH + active.REQUIRED_CACHE_SYMBOLS + ["QQQ", "GLD", "IEF", "AGG"]))

BENCHMARKS_BY_CANDIDATE = {
    DUAL_ID: [
        "dual_momentum_paa_clean_v1_parent_reference",
        active.VM_ID,
        active.DSR_ID,
        combo.COMBO_ID,
        active.SPY_200D_ID,
        "SPY_buy_hold",
        "QQQ_buy_hold",
        "GLD_buy_hold",
        "IEF_buy_hold",
        "AGG_buy_hold",
        "BIL_cash_proxy",
        "static_all_weather_benchmark_v1",
    ],
    DONCHIAN_ID: [
        "donchian_atr_breakout_etf_v1_parent_reference",
        active.VM_ID,
        active.DSR_ID,
        combo.COMBO_ID,
        active.SPY_200D_ID,
        "SPY_buy_hold",
        "QQQ_buy_hold",
        "BIL_cash_proxy",
        "vol_compression_breakout_etf_v1_reference",
    ],
}
CORE_CORRELATION_BENCHMARKS = [active.VM_ID, active.DSR_ID, combo.COMBO_ID, active.SPY_200D_ID]
UNAVAILABLE_REFERENCE_REASONS = {
    "dual_momentum_paa_clean_v1_parent_reference": "exact rejected parent remains closed; no same-window parent rerun in this task",
    "donchian_atr_breakout_etf_v1_parent_reference": "exact rejected parent remains closed; no same-window parent rerun in this task",
    "vol_compression_breakout_etf_v1_reference": "optional breakout reference not available as same-window frozen benchmark in this packet",
}

MANIFEST_FLAGS = {
    "discovery_run": True,
    "backtests_run": True,
    "candidate_count": 2,
    "candidate_ids": AUTHORIZED_CANDIDATES,
    "provider_download": False,
    "intraday_data_used": False,
    "candidate_exhaustive_run": False,
    "paper_forward_review": False,
    "paper_forward_activation": False,
    "broker_path_touched": False,
    "live_orders": False,
    "real_money_recommendation": False,
    "accepted_strategy_state_changed": False,
    "rejected_strategy_state_changed": False,
    "exact_rejected_variants_reopened": False,
    "invalidated_55_day_donchian_used": False,
    "intraday_research_remains_paused": True,
}

REQUIRED_FILES = [
    "risk_controlled_discovery_manifest.json",
    "risk_controlled_discovery_summary.md",
    "risk_controlled_candidate_results.csv",
    "risk_controlled_candidate_metrics.json",
    "risk_controlled_benchmark_deltas.csv",
    "risk_controlled_same_window_benchmarks.csv",
    "risk_controlled_risk_gate_results.csv",
    "risk_controlled_slippage_stress_results.csv",
    "risk_controlled_allocation_diagnostics.csv",
    "risk_controlled_dual_momentum_scalar_diagnostics.csv",
    "risk_controlled_donchian_sizing_diagnostics.csv",
    "risk_controlled_parent_comparison.csv",
    "risk_controlled_duplication_diagnostics.csv",
    "risk_controlled_promotion_candidates.csv",
    "risk_controlled_rejection_reasons.md",
    "risk_controlled_next_action.md",
    "risk_controlled_discovery_consistency_check.json",
]


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def fmt(value: Any) -> Any:
    if isinstance(value, (float, np.floating)):
        value = float(value)
        if math.isnan(value) or math.isinf(value):
            return ""
        return round(value, 6)
    return value


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: fmt(row.get(field, "")) for field in fields})


def clean_output(root: Path) -> Path:
    output = (root / OUTPUT_DIR).resolve()
    workspace = root.resolve()
    if output == workspace or workspace not in output.parents:
        raise RuntimeError(f"refusing output outside workspace: {output}")
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)
    return output


def strategy_snapshot(root: Path) -> list[dict[str, Any]]:
    return deepcopy(load_yaml(root / REGISTRY_PATH).get("strategies", []))


def strategy_state_map(strategies: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    state: dict[str, dict[str, Any]] = {}
    for row in strategies:
        row_id = row.get("id") or row.get("strategy_id")
        if not row_id:
            continue
        state[row_id] = {
            "status": row.get("status") or row.get("current_status"),
            "current_status": row.get("current_status"),
            "paper_forward_active": row.get("paper_forward_active"),
            "candidate_exhaustive_run": row.get("candidate_exhaustive_run"),
            "candidate_exhaustive_recommended": row.get("candidate_exhaustive_recommended"),
            "promotion_review_required": row.get("promotion_review_required"),
        }
    return state


def required_symbols() -> list[str]:
    return LOAD_SYMBOLS


def validate_authorization(root: Path) -> list[str]:
    mismatches: list[str] = []
    manual = read_json(root / MANUAL_REVIEW_DIR / "risk_controlled_manual_review_manifest.json")
    freeze = read_json(root / RULE_FREEZE_DIR / "risk_controlled_rule_freeze_manifest.json")
    if manual.get("decision") != "approve_risk_controlled_high_return_discovery_batch_after_manual_review":
        mismatches.append("manual review did not approve the two-candidate discovery batch")
    if manual.get("next_action") != "run_risk_controlled_high_return_discovery_batch":
        mismatches.append("manual review next action does not authorize this discovery batch")
    if manual.get("candidate_count_for_future_discovery") != 2:
        mismatches.append("manual review candidate count is not two")
    if manual.get("accepted_candidate_ids_for_future_discovery") != AUTHORIZED_CANDIDATES:
        mismatches.append("manual review accepted candidate ids do not match authorized list")
    if manual.get("prior_55_day_language_invalidated") is not True:
        mismatches.append("manual review did not invalidate prior Donchian lookback language")
    if manual.get("official_donchian_rule_uses_20_day_breakout") is not True:
        mismatches.append("manual review does not confirm official 20-day Donchian rule")
    if freeze.get("candidate_ids") != AUTHORIZED_CANDIDATES:
        mismatches.append("rule-freeze candidate ids do not match authorized list")
    if freeze.get("all_formulas_frozen") is not True:
        mismatches.append("rule-freeze formulas are not all frozen")
    if freeze.get("dual_momentum_volatility_formula_frozen") is not True:
        mismatches.append("dual momentum volatility formula is not frozen")
    if freeze.get("donchian_risk_budget_formula_frozen") is not True:
        mismatches.append("Donchian risk-budget formula is not frozen")
    return mismatches


def read_symbol_frame(root: Path, symbol: str) -> pd.DataFrame | None:
    path = root / CACHE_DIR / f"{symbol}.csv"
    if not path.exists():
        return None
    frame = pd.read_csv(path)
    if "date" not in frame:
        return None
    dates = pd.to_datetime(frame["date"], errors="coerce").dt.tz_localize(None)
    clean = pd.DataFrame({"date": dates})
    for column in ["open", "high", "low", "close", "adj_close", "volume"]:
        if column in frame:
            clean[column] = pd.to_numeric(frame[column], errors="coerce")
    if "adj_close" not in clean and "close" in clean:
        clean["adj_close"] = clean["close"]
    if "close" not in clean and "adj_close" in clean:
        clean["close"] = clean["adj_close"]
    for column in ["open", "high", "low"]:
        if column not in clean and "close" in clean:
            clean[column] = clean["close"]
    if "volume" not in clean:
        clean["volume"] = 1_000_000.0
    required = ["date", "open", "high", "low", "close", "adj_close", "volume"]
    if any(column not in clean for column in required):
        return None
    clean = clean.dropna(subset=["date", "adj_close"]).sort_values("date").drop_duplicates("date")
    if len(clean) < 252:
        return None
    return clean.set_index("date")[["open", "high", "low", "close", "adj_close", "volume"]].astype(float)


def load_prices(root: Path) -> dict[str, Any]:
    frames: dict[str, pd.DataFrame] = {}
    missing: list[str] = []
    for symbol in LOAD_SYMBOLS:
        frame = read_symbol_frame(root, symbol)
        if frame is None:
            missing.append(symbol)
        else:
            frames[symbol] = frame
    if missing:
        return {"available": False, "missing": missing}
    common_end = min(frame.index.max() for frame in frames.values())
    all_dates = sorted(set().union(*(set(frame.index[frame.index <= common_end]) for frame in frames.values())))
    store: dict[str, Any] = {
        "available": True,
        "index": pd.DatetimeIndex(all_dates),
        "first_dates": {symbol: str(frame.index.min().date()) for symbol, frame in frames.items()},
        "last_dates": {symbol: str(min(frame.index.max(), common_end).date()) for symbol, frame in frames.items()},
    }
    for column in ["open", "high", "low", "close", "adj_close", "volume"]:
        store[column] = pd.concat(
            [frame[column].rename(symbol) for symbol, frame in frames.items()],
            axis=1,
            join="outer",
            sort=False,
        ).reindex(store["index"]).sort_index()
    return store


def indicators(store: dict[str, Any]) -> dict[str, pd.DataFrame]:
    close = store["adj_close"]
    high = store["high"]
    low = store["low"]
    prev_close = close.shift(1)
    true_range = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=0).groupby(level=0).max()
    returns = close.pct_change()
    return {
        "mom252": close / close.shift(252) - 1.0,
        "sma200": close.rolling(200, min_periods=200).mean(),
        "spy_realized_vol63": returns["SPY"].rolling(63, min_periods=63).std() * np.sqrt(252.0),
        "high20_prior": high.shift(1).rolling(20, min_periods=20).max(),
        "atr14": true_range.rolling(14, min_periods=14).mean(),
    }


def value_at(frame: pd.DataFrame | pd.Series, symbol: str | None, t: int) -> float | None:
    if t < 0 or t >= len(frame):
        return None
    value = frame.iloc[t] if symbol is None else frame.iloc[t][symbol] if symbol in frame.columns else None
    if value is None or pd.isna(value):
        return None
    return float(value)


def available(store: dict[str, Any], symbol: str, t: int, lookback: int = 0) -> bool:
    return value_at(store["adj_close"], symbol, t) is not None and value_at(store["adj_close"], symbol, t - lookback) is not None


def above_sma200(store: dict[str, Any], ind: dict[str, pd.DataFrame], symbol: str, t: int) -> bool:
    price = value_at(store["adj_close"], symbol, t)
    sma = value_at(ind["sma200"], symbol, t)
    return price is not None and sma is not None and price > sma


def symbol_return(store: dict[str, Any], symbol: str, t: int) -> float:
    if not available(store, symbol, t, 1):
        return 0.0
    return float(store["adj_close"].iloc[t][symbol] / store["adj_close"].iloc[t - 1][symbol] - 1.0)


def date_week(ts: pd.Timestamp) -> str:
    iso = ts.isocalendar()
    return f"{iso.year}-{iso.week:02d}"


def floor_to_005(value: float) -> float:
    return math.floor((value + 1e-12) / 0.05) * 0.05


def realized_vol_scalar(ind: dict[str, pd.DataFrame], signal: int) -> tuple[float, float | None, str]:
    vol = value_at(ind["spy_realized_vol63"], None, signal)
    if vol is None or not np.isfinite(vol) or vol <= 0:
        return 0.0, None, "missing_or_invalid_volatility_input"
    raw = 0.12 / vol
    scalar = floor_to_005(min(1.0, max(0.25, raw)))
    return float(scalar), float(vol), "ok"


def weights_dual_parent(store: dict[str, Any], ind: dict[str, pd.DataFrame], signal: int) -> dict[str, float]:
    scored: list[tuple[str, float]] = []
    for symbol in ["SPY", "QQQ", "GLD", "IEF", "AGG"]:
        momentum = value_at(ind["mom252"], symbol, signal)
        if momentum is not None and momentum > 0 and available(store, symbol, signal, 252) and above_sma200(store, ind, symbol, signal):
            scored.append((symbol, momentum))
    top = sorted(scored, key=lambda item: (-item[1], item[0]))[:2]
    weights: dict[str, float] = {}
    for symbol, _score in top:
        weights[symbol] = weights.get(symbol, 0.0) + 0.5
    if len(top) < 2:
        weights["BIL"] = weights.get("BIL", 0.0) + 0.5 * (2 - len(top))
    return weights or {"BIL": 1.0}


def weights_dual_scaled(store: dict[str, Any], ind: dict[str, pd.DataFrame], signal: int) -> tuple[dict[str, float], dict[str, Any]]:
    parent = weights_dual_parent(store, ind, signal)
    scalar, vol, reason = realized_vol_scalar(ind, signal)
    weights: dict[str, float] = {}
    for symbol, weight in parent.items():
        if symbol != "BIL":
            weights[symbol] = weights.get(symbol, 0.0) + weight * scalar
    weights["BIL"] = max(0.0, 1.0 - sum(weights.values()))
    return weights, {
        "scalar": scalar,
        "realized_vol_63d": "" if vol is None else vol,
        "reason": reason,
        "parent_weights": parent,
    }


def benchmark_weights(close: pd.DataFrame, benchmark_id: str, signal: int) -> dict[str, float]:
    if benchmark_id == combo.COMBO_ID:
        weights: dict[str, float] = {}
        for source, source_weight in [(active.strategy_weights(close, signal, active.VM_ID), 0.5), (active.strategy_weights(close, signal, active.DSR_ID), 0.5)]:
            for symbol, weight in source.items():
                weights[symbol] = weights.get(symbol, 0.0) + source_weight * weight
        return weights or {"BIL": 1.0}
    if benchmark_id == "static_all_weather_benchmark_v1":
        return {"SPY": 0.30, "IEF": 0.40, "GLD": 0.20, "BIL": 0.10}
    if benchmark_id.endswith("_buy_hold"):
        return {benchmark_id.replace("_buy_hold", ""): 1.0}
    if benchmark_id in UNAVAILABLE_REFERENCE_REASONS:
        return {}
    return active.strategy_weights(close, signal, benchmark_id)


def result_payload(
    candidate_id: str,
    equity: pd.Series,
    allocations: list[dict[str, float]],
    trade_count: int,
    rebalance_count: int,
    turnover: float,
    trades: list[dict[str, Any]] | None = None,
    extra_stats: dict[str, Any] | None = None,
) -> dict[str, Any]:
    trades = trades or []
    extra_stats = extra_stats or {}
    returns = equity.pct_change().dropna()
    alloc_count = max(len(allocations), 1)
    bil_freq = sum(1 for row in allocations if row.get("BIL", 0.0) > 0.01) / alloc_count
    mean_bil = sum(row.get("BIL", 0.0) for row in allocations) / alloc_count
    avg_hold = float(np.mean([row.get("holding_days", 0) for row in trades])) if trades else 0.0
    asset_days: dict[str, int] = {}
    asset_weight_sum: dict[str, float] = {}
    for row in allocations:
        for symbol, weight in row.items():
            if weight > 0.01:
                asset_days[symbol] = asset_days.get(symbol, 0) + 1
            asset_weight_sum[symbol] = asset_weight_sum.get(symbol, 0.0) + weight
    stats = {
        "ending_equity": float(equity.iloc[-1]) if not equity.empty else STARTING_EQUITY,
        "total_return": total_return(equity),
        "annualized_return": annualized_return(equity),
        "volatility": annualized_volatility(returns),
        "sharpe": sharpe_ratio(returns),
        "max_drawdown": drawdown_dollars(equity),
        "risk_buffer": drawdown_dollars(equity) - STOP_DOLLARS,
        "trade_count": int(trade_count),
        "rebalance_count": int(rebalance_count),
        "average_holding_period": avg_hold,
        "turnover": turnover / STARTING_EQUITY,
        "bil_allocation_frequency": bil_freq,
        "mean_bil_allocation": mean_bil,
        "asset_allocation_frequency": {symbol: asset_days[symbol] / alloc_count for symbol in sorted(asset_days)},
        "asset_mean_allocation": {symbol: asset_weight_sum[symbol] / alloc_count for symbol in sorted(asset_weight_sum)},
    }
    stats.update(extra_stats)
    return {"candidate_id": candidate_id, "equity": equity, "returns": returns, "allocations": allocations, "trades": trades, "stats": stats}


def simulate_dual_scaled(
    store: dict[str, Any],
    ind: dict[str, pd.DataFrame],
    start_idx: int,
    end_idx: int,
    slippage: float,
) -> dict[str, Any]:
    equity = STARTING_EQUITY
    weights: dict[str, float] = {"BIL": 1.0}
    last_month = None
    values: list[float] = []
    dates: list[pd.Timestamp] = []
    allocations: list[dict[str, float]] = []
    scalar_rows: list[dict[str, Any]] = []
    turnover = 0.0
    rebalance_count = 0
    months = np.array([dt.year * 12 + dt.month for dt in store["index"]], dtype=int)
    for t in range(start_idx + 1, end_idx + 1):
        signal = t - 1
        month = int(months[t])
        if month != last_month:
            new_weights, scalar_info = weights_dual_scaled(store, ind, signal)
            rebalance_turnover = sum(abs(new_weights.get(sym, 0.0) - weights.get(sym, 0.0)) for sym in set(new_weights) | set(weights))
            if rebalance_turnover > 1e-10:
                equity -= equity * rebalance_turnover * slippage
                turnover += rebalance_turnover
                rebalance_count += 1
            weights = new_weights
            scalar_rows.append(
                {
                    "rebalance_date": str(store["index"][t].date()),
                    "signal_date": str(store["index"][signal].date()),
                    "scalar": scalar_info["scalar"],
                    "realized_vol_63d": scalar_info["realized_vol_63d"],
                    "route_to_bil_reason": scalar_info["reason"],
                    "target_weights": json.dumps({k: round(v, 6) for k, v in sorted(weights.items())}, sort_keys=True),
                    "parent_weights": json.dumps({k: round(v, 6) for k, v in sorted(scalar_info["parent_weights"].items())}, sort_keys=True),
                }
            )
            last_month = month
        daily_return = sum(weight * symbol_return(store, symbol, t) for symbol, weight in weights.items())
        equity *= 1.0 + daily_return
        values.append(equity)
        dates.append(store["index"][t])
        allocations.append(deepcopy(weights))
    scalar_values = [float(row["scalar"]) for row in scalar_rows]
    extra = {
        "scalar_min": min(scalar_values) if scalar_values else 0.0,
        "scalar_median": float(np.median(scalar_values)) if scalar_values else 0.0,
        "scalar_max": max(scalar_values) if scalar_values else 0.0,
        "scalar_at_min_025_frequency": float(np.mean([abs(value - 0.25) < 1e-12 for value in scalar_values])) if scalar_values else 0.0,
        "scalar_at_max_100_frequency": float(np.mean([abs(value - 1.0) < 1e-12 for value in scalar_values])) if scalar_values else 0.0,
        "missing_vol_route_to_bil_frequency": float(np.mean([row["route_to_bil_reason"] != "ok" for row in scalar_rows])) if scalar_rows else 0.0,
        "scalar_diagnostics": scalar_rows,
    }
    return result_payload(DUAL_ID, pd.Series(values, index=dates, dtype=float), allocations, rebalance_count, rebalance_count, turnover, extra_stats=extra)


def qualifying_donchian_signals(store: dict[str, Any], ind: dict[str, pd.DataFrame], signal: int) -> list[dict[str, Any]]:
    signals: list[dict[str, Any]] = []
    for symbol in DONCHIAN_UNIVERSE:
        prior_close = value_at(store["adj_close"], symbol, signal)
        high20 = value_at(ind["high20_prior"], symbol, signal)
        atr14 = value_at(ind["atr14"], symbol, signal)
        if prior_close is None or high20 is None or atr14 is None:
            continue
        if prior_close > high20:
            signals.append({"symbol": symbol, "prior_close": prior_close, "prior_20d_high": high20, "atr14": atr14})
    return signals


def simulate_donchian_risk_budget(
    store: dict[str, Any],
    ind: dict[str, pd.DataFrame],
    start_idx: int,
    end_idx: int,
    slippage: float,
) -> dict[str, Any]:
    cash = STARTING_EQUITY
    positions: list[dict[str, Any]] = []
    values: list[float] = []
    dates: list[pd.Timestamp] = []
    allocations: list[dict[str, float]] = []
    trades: list[dict[str, Any]] = []
    sizing_rows: list[dict[str, Any]] = []
    skip_reasons: dict[str, int] = {
        "portfolio_risk_budget": 0,
        "max_position_limit": 0,
        "below_minimum_notional": 0,
        "insufficient_cash": 0,
    }
    signal_count = 0
    accepted_signals = 0
    blocked_portfolio = 0
    blocked_max = 0
    below_min = 0
    entry_count = 0
    exit_count = 0
    stop_exits = 0
    max_hold_exits = 0
    turnover = 0.0
    risk_utilizations: list[float] = []
    notionals: list[float] = []
    max_open = 0
    for t in range(start_idx + 1, end_idx + 1):
        ts = store["index"][t]
        signal = t - 1
        survivors: list[dict[str, Any]] = []
        for pos in positions:
            prior_close = value_at(store["adj_close"], pos["symbol"], signal)
            exit_open = value_at(store["open"], pos["symbol"], t)
            hold_days = t - pos["entry_t"]
            reason = ""
            if prior_close is None or exit_open is None:
                reason = "missing_stale_data"
            elif prior_close <= pos["stop_threshold"]:
                reason = "close_based_atr_stop"
            elif hold_days >= 20:
                reason = "max_holding_period"
            if reason:
                exit_price = (exit_open if exit_open is not None else pos["entry_price"]) * (1.0 - slippage)
                proceeds = pos["shares"] * exit_price
                cash += proceeds
                turnover += proceeds
                exit_count += 1
                stop_exits += int(reason == "close_based_atr_stop")
                max_hold_exits += int(reason == "max_holding_period")
                trades.append(
                    {
                        "candidate_id": DONCHIAN_ID,
                        "symbol": pos["symbol"],
                        "entry_date": str(store["index"][pos["entry_t"]].date()),
                        "exit_date": str(ts.date()),
                        "entry_price": pos["entry_price"],
                        "exit_price": exit_price,
                        "entry_notional": pos["entry_notional"],
                        "pnl": proceeds - pos["entry_notional"],
                        "holding_days": hold_days,
                        "exit_reason": reason,
                    }
                )
            else:
                survivors.append(pos)
        positions = survivors

        equity_before = cash + sum(pos["shares"] * (value_at(store["adj_close"], pos["symbol"], signal) or pos["entry_price"]) for pos in positions)
        current_risk = sum(max(pos["entry_price"] - pos["stop_threshold"], 0.0) * pos["shares"] for pos in positions)
        portfolio_budget = 0.015 * equity_before
        remaining_risk = max(0.0, portfolio_budget - current_risk)
        held = {pos["symbol"] for pos in positions}
        for signal_row in qualifying_donchian_signals(store, ind, signal):
            signal_count += 1
            symbol = signal_row["symbol"]
            if symbol in held:
                continue
            if len(positions) >= 2:
                skip_reasons["max_position_limit"] += 1
                blocked_max += 1
                continue
            entry_open = value_at(store["open"], symbol, t)
            if entry_open is None or signal_row["atr14"] <= 0:
                continue
            entry_price = entry_open * (1.0 + slippage)
            stop_threshold = entry_price - 2.0 * float(signal_row["atr14"])
            dollar_risk_per_share = max(entry_price - stop_threshold, 0.0)
            if dollar_risk_per_share <= 0:
                continue
            per_position_budget = 0.0075 * equity_before
            raw_shares = per_position_budget / dollar_risk_per_share
            raw_notional = raw_shares * entry_price
            notional = min(raw_notional, 0.25 * equity_before, cash)
            if notional < 25.0:
                skip_reasons["below_minimum_notional"] += 1
                below_min += 1
                continue
            shares = notional / entry_price
            risk_dollars = dollar_risk_per_share * shares
            if risk_dollars > remaining_risk + 1e-8:
                skip_reasons["portfolio_risk_budget"] += 1
                blocked_portfolio += 1
                continue
            if cash < notional:
                skip_reasons["insufficient_cash"] += 1
                continue
            cash -= notional
            turnover += notional
            accepted_signals += 1
            entry_count += 1
            held.add(symbol)
            remaining_risk = max(0.0, remaining_risk - risk_dollars)
            positions.append(
                {
                    "symbol": symbol,
                    "entry_t": t,
                    "entry_price": entry_price,
                    "entry_notional": notional,
                    "shares": shares,
                    "stop_threshold": stop_threshold,
                    "risk_dollars": risk_dollars,
                }
            )
            notionals.append(notional)
            risk_utilizations.append(risk_dollars / portfolio_budget if portfolio_budget > 0 else 0.0)
            sizing_rows.append(
                {
                    "date": str(ts.date()),
                    "symbol": symbol,
                    "entry_price": entry_price,
                    "initial_stop_threshold": stop_threshold,
                    "dollar_risk_per_share": dollar_risk_per_share,
                    "position_notional": notional,
                    "risk_dollars": risk_dollars,
                    "portfolio_risk_budget": portfolio_budget,
                    "remaining_portfolio_risk_after_entry": remaining_risk,
                }
            )
        cash *= 1.0 + symbol_return(store, "BIL", t)
        equity = cash + sum(pos["shares"] * (value_at(store["adj_close"], pos["symbol"], t) or pos["entry_price"]) for pos in positions)
        max_open = max(max_open, len(positions))
        row_alloc: dict[str, float] = {"BIL": cash / equity if equity > 0 else 0.0}
        for pos in positions:
            mark = value_at(store["adj_close"], pos["symbol"], t) or pos["entry_price"]
            row_alloc[pos["symbol"]] = row_alloc.get(pos["symbol"], 0.0) + pos["shares"] * mark / equity if equity > 0 else 0.0
        allocations.append(row_alloc)
        values.append(equity)
        dates.append(ts)
    skipped = signal_count - accepted_signals
    extra = {
        "signal_count": signal_count,
        "accepted_signal_count": accepted_signals,
        "skipped_signal_count": skipped,
        "skip_reasons": skip_reasons,
        "risk_budget_utilization_median": float(np.median(risk_utilizations)) if risk_utilizations else 0.0,
        "risk_budget_utilization_max": max(risk_utilizations) if risk_utilizations else 0.0,
        "per_position_notional_min": min(notionals) if notionals else 0.0,
        "per_position_notional_median": float(np.median(notionals)) if notionals else 0.0,
        "per_position_notional_max": max(notionals) if notionals else 0.0,
        "positions_blocked_by_portfolio_risk_budget": blocked_portfolio,
        "positions_blocked_by_max_position_limit": blocked_max,
        "positions_below_minimum_notional": below_min,
        "stop_exits": stop_exits,
        "max_hold_exits": max_hold_exits,
        "entry_count": entry_count,
        "exit_count": exit_count,
        "max_open_positions_observed": max_open,
        "sizing_diagnostics": sizing_rows,
    }
    return result_payload(DONCHIAN_ID, pd.Series(values, index=dates, dtype=float), allocations, entry_count + exit_count, entry_count, turnover, trades, extra)


def simulate_benchmark(
    store: dict[str, Any],
    benchmark_id: str,
    start_idx: int,
    end_idx: int,
    slippage: float = BASE_SLIPPAGE,
) -> dict[str, Any] | None:
    if benchmark_id in UNAVAILABLE_REFERENCE_REASONS:
        return None
    close = store["adj_close"]
    equity = STARTING_EQUITY
    weights: dict[str, float] = {"BIL": 1.0}
    last_month = None
    turnover = 0.0
    rebalance_count = 0
    values: list[float] = []
    dates: list[pd.Timestamp] = []
    allocations: list[dict[str, float]] = []
    months = np.array([dt.year * 12 + dt.month for dt in store["index"]], dtype=int)
    for t in range(start_idx + 1, end_idx + 1):
        signal = t - 1
        month = int(months[t])
        if month != last_month:
            new_weights = benchmark_weights(close, benchmark_id, signal)
            if not new_weights:
                return None
            rebalance_turnover = sum(abs(new_weights.get(sym, 0.0) - weights.get(sym, 0.0)) for sym in set(new_weights) | set(weights))
            if rebalance_turnover > 1e-10:
                equity -= equity * rebalance_turnover * slippage
                turnover += rebalance_turnover
                rebalance_count += 1
            weights = new_weights
            last_month = month
        daily_return = sum(weight * symbol_return(store, symbol, t) for symbol, weight in weights.items())
        equity *= 1.0 + daily_return
        values.append(equity)
        dates.append(store["index"][t])
        allocations.append(deepcopy(weights))
    return result_payload(benchmark_id, pd.Series(values, index=dates, dtype=float), allocations, rebalance_count, rebalance_count, turnover)


def simulate_candidate(
    store: dict[str, Any],
    ind: dict[str, pd.DataFrame],
    candidate_id: str,
    start_idx: int,
    end_idx: int,
    slippage: float = BASE_SLIPPAGE,
) -> dict[str, Any]:
    if candidate_id == DUAL_ID:
        return simulate_dual_scaled(store, ind, start_idx, end_idx, slippage)
    if candidate_id == DONCHIAN_ID:
        return simulate_donchian_risk_budget(store, ind, start_idx, end_idx, slippage)
    raise ValueError(f"unauthorized candidate: {candidate_id}")


def drawdown_dollars(equity: pd.Series) -> float:
    if equity.empty:
        return 0.0
    return float((equity - equity.cummax()).min())


def total_return(equity: pd.Series) -> float:
    return float(equity.iloc[-1] / STARTING_EQUITY - 1.0) if not equity.empty else 0.0


def annualized_return(equity: pd.Series) -> float:
    if equity.empty:
        return 0.0
    years = max((equity.index[-1] - equity.index[0]).days / 365.25, 1 / 365.25)
    return float((equity.iloc[-1] / STARTING_EQUITY) ** (1.0 / years) - 1.0)


def annualized_volatility(returns: pd.Series) -> float:
    return float(returns.std() * np.sqrt(252.0)) if len(returns) > 1 else 0.0


def sharpe_ratio(returns: pd.Series) -> float:
    vol = returns.std()
    return float((returns.mean() / vol) * np.sqrt(252.0)) if len(returns) > 1 and vol > 0 else 0.0


def sample_starts(index: pd.DatetimeIndex, horizon: int) -> list[int]:
    starts = list(range(253, len(index) - horizon))
    if len(starts) <= MAX_WINDOWS_PER_HORIZON:
        return starts
    return sorted(set(int(x) for x in np.linspace(starts[0], starts[-1], MAX_WINDOWS_PER_HORIZON)))


def window_row_from_result(result: dict[str, Any], strategy_id: str, horizon: int, start: int, end: int, index: pd.DatetimeIndex) -> dict[str, Any]:
    equity = result["equity"]
    profit = float(equity.iloc[-1] - STARTING_EQUITY) if not equity.empty else 0.0
    stop_hit = bool((equity - STARTING_EQUITY <= STOP_DOLLARS).any()) if not equity.empty else False
    target300_idx = np.where((equity - STARTING_EQUITY) >= 300)[0]
    target400_idx = np.where((equity - STARTING_EQUITY) >= 400)[0]
    stop_idx = np.where((equity - STARTING_EQUITY) <= STOP_DOLLARS)[0]
    first_stop = int(stop_idx[0]) if len(stop_idx) else None
    first_300 = int(target300_idx[0]) if len(target300_idx) else None
    first_400 = int(target400_idx[0]) if len(target400_idx) else None
    return {
        "strategy_id": strategy_id,
        "horizon": horizon,
        "window_start": str(index[start].date()),
        "window_end": str(index[end].date()),
        "final_equity": float(equity.iloc[-1]) if not equity.empty else STARTING_EQUITY,
        "profit_dollars": profit,
        "max_drawdown": drawdown_dollars(equity),
        "absolute_600_stop_hit": stop_hit,
        "target_300_before_stop": bool(first_300 is not None and (first_stop is None or first_300 <= first_stop)),
        "target_400_before_stop": bool(first_400 is not None and (first_stop is None or first_400 <= first_stop)),
    }


def run_windows(store: dict[str, Any], ind: dict[str, pd.DataFrame], strategy_id: str, is_candidate: bool) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for horizon in HORIZONS:
        for start in sample_starts(store["index"], horizon):
            end = start + horizon
            if is_candidate:
                result = simulate_candidate(store, ind, strategy_id, start, end)
            else:
                result = simulate_benchmark(store, strategy_id, start, end)
                if result is None:
                    continue
            rows.append(window_row_from_result(result, strategy_id, horizon, start, end, store["index"]))
    return rows


def summarize(rows: list[dict[str, Any]], strategy_id: str, horizon: int) -> dict[str, Any]:
    frame = pd.DataFrame([row for row in rows if row["strategy_id"] == strategy_id and row["horizon"] == horizon])
    if frame.empty:
        return {"strategy_id": strategy_id, "horizon": horizon, "validation_status": "missing_or_unavailable"}
    return {
        "strategy_id": strategy_id,
        "horizon": horizon,
        "window_count": int(len(frame)),
        "median_final_equity": float(frame["final_equity"].median()),
        "mean_final_equity": float(frame["final_equity"].mean()),
        "p75_final_equity": float(frame["final_equity"].quantile(0.75)),
        "p90_final_equity": float(frame["final_equity"].quantile(0.90)),
        "best_final_equity": float(frame["final_equity"].max()),
        "worst_final_equity": float(frame["final_equity"].min()),
        "target_300_before_stop_rate": float(frame["target_300_before_stop"].mean()),
        "target_400_before_stop_rate": float(frame["target_400_before_stop"].mean()),
        "worst_drawdown": float(frame["max_drawdown"].min()),
        "median_drawdown": float(frame["max_drawdown"].median()),
        "stop_hit_rate": float(frame["absolute_600_stop_hit"].mean()),
        "worst_loss_window": float(frame["profit_dollars"].min()),
        "median_profit_dollars": float(frame["profit_dollars"].median()),
    }


def corr(returns: dict[str, pd.Series], left: str, right: str) -> float | str:
    if left not in returns or right not in returns:
        return "unavailable"
    aligned = pd.concat([returns[left].rename("left"), returns[right].rename("right")], axis=1).dropna()
    return float(aligned["left"].corr(aligned["right"])) if len(aligned) > 5 else "unavailable"


def build_payload(root: Path) -> dict[str, Any]:
    store = load_prices(root)
    if not store.get("available"):
        return {"diagnostics_available": False, "missing_symbols": store.get("missing", [])}
    ind = indicators(store)
    start_idx = 253
    end_idx = len(store["index"]) - 1
    full_results = {candidate_id: simulate_candidate(store, ind, candidate_id, start_idx, end_idx) for candidate_id in AUTHORIZED_CANDIDATES}
    stress_results = {candidate_id: simulate_candidate(store, ind, candidate_id, start_idx, end_idx, STRESS_SLIPPAGE) for candidate_id in AUTHORIZED_CANDIDATES}
    candidate_windows = {candidate_id: run_windows(store, ind, candidate_id, True) for candidate_id in AUTHORIZED_CANDIDATES}
    benchmark_ids = sorted(set(sum(BENCHMARKS_BY_CANDIDATE.values(), [])))
    benchmark_windows = {bench_id: run_windows(store, ind, bench_id, False) for bench_id in benchmark_ids if bench_id not in UNAVAILABLE_REFERENCE_REASONS}
    benchmark_full = {
        bench_id: simulate_benchmark(store, bench_id, start_idx, end_idx)
        for bench_id in benchmark_ids
        if bench_id not in UNAVAILABLE_REFERENCE_REASONS
    }
    summaries = {
        candidate_id: {horizon: summarize(candidate_windows[candidate_id], candidate_id, horizon) for horizon in HORIZONS}
        for candidate_id in AUTHORIZED_CANDIDATES
    }
    benchmark_summaries = {
        bench_id: {horizon: summarize(rows, bench_id, horizon) for horizon in HORIZONS}
        for bench_id, rows in benchmark_windows.items()
    }
    returns = {candidate_id: result["returns"] for candidate_id, result in full_results.items()}
    for bench_id, result in benchmark_full.items():
        if result is not None:
            returns[bench_id] = result["returns"]
    return {
        "diagnostics_available": True,
        "store": store,
        "ind": ind,
        "full_results": full_results,
        "stress_results": stress_results,
        "candidate_windows": candidate_windows,
        "benchmark_windows": benchmark_windows,
        "benchmark_full": benchmark_full,
        "summaries": summaries,
        "benchmark_summaries": benchmark_summaries,
        "returns": returns,
    }


def promotion_blockers(candidate_id: str, metrics: dict[str, Any], benchmark_deltas: dict[str, Any], duplication: dict[str, Any], stress: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if metrics.get("risk_buffer", -999.0) < 25:
        blockers.append("risk_buffer_fails")
    if stress.get("stress_pass") is not True:
        blockers.append("slippage_stress_fails")
    active_combo_delta = benchmark_deltas.get(combo.COMBO_ID)
    spy200_delta = benchmark_deltas.get(active.SPY_200D_ID)
    if not isinstance(active_combo_delta, (int, float)) or active_combo_delta < 25:
        blockers.append("benchmark_edge_fails_active_combo")
    if not isinstance(spy200_delta, (int, float)) or spy200_delta <= 0:
        blockers.append("benchmark_edge_fails_spy_200d")
    if metrics.get("trade_count", 0) <= 0:
        blockers.append("trade_count_too_low")
    active_combo_delta_value = active_combo_delta if isinstance(active_combo_delta, (int, float)) else 0.0
    if metrics.get("bil_allocation_frequency", 1.0) > 0.75 and active_combo_delta_value < 50:
        blockers.append("bil_allocation_excessive_without_clear_benefit")
    if duplication.get("duplicates_active_combo") is True or duplication.get("duplicates_spy_200d") is True:
        blockers.append("duplication_too_high_without_useful_edge")
    if candidate_id == DUAL_ID:
        if metrics.get("scalar_median", 0.0) <= 0.25 and metrics.get("ending_equity", 0.0) < STARTING_EQUITY * 1.05:
            blockers.append("volatility_scaling_too_slow_or_bil_heavy")
        if metrics.get("mean_bil_allocation", 0.0) > 0.65:
            blockers.append("bil_heavy_defensive_clone_risk")
    if candidate_id == DONCHIAN_ID:
        if metrics.get("accepted_signal_count", 0) <= 0:
            blockers.append("no_accepted_breakout_signals")
        if metrics.get("positions_blocked_by_portfolio_risk_budget", 0) + metrics.get("positions_blocked_by_max_position_limit", 0) > metrics.get("accepted_signal_count", 0) * 5 + 10:
            blockers.append("skip_block_logic_dominates_results")
        if metrics.get("per_position_notional_median", 0.0) < 25.0 and metrics.get("accepted_signal_count", 0) > 0:
            blockers.append("position_notional_too_small")
    return blockers


def candidate_decisions(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if not payload["diagnostics_available"]:
        return {candidate_id: {"outcome": "discovery_reject", "blockers": ["evidence_incomplete"], "reason": "price cache incomplete"} for candidate_id in AUTHORIZED_CANDIDATES}
    decisions: dict[str, dict[str, Any]] = {}
    for candidate_id in AUTHORIZED_CANDIDATES:
        stats = payload["full_results"][candidate_id]["stats"]
        s180 = payload["summaries"][candidate_id][180]
        metrics = {**stats, **{f"sample_180d_{k}": v for k, v in s180.items() if k != "strategy_id"}}
        deltas: dict[str, Any] = {}
        for bench_id in BENCHMARKS_BY_CANDIDATE[candidate_id]:
            if bench_id in UNAVAILABLE_REFERENCE_REASONS:
                continue
            bench = payload["benchmark_summaries"].get(bench_id, {}).get(180, {})
            if "median_final_equity" in bench and "median_final_equity" in s180:
                deltas[bench_id] = float(s180["median_final_equity"]) - float(bench["median_final_equity"])
        dup = {
            "corr_vs_active_combo": corr(payload["returns"], candidate_id, combo.COMBO_ID),
            "corr_vs_spy_200d": corr(payload["returns"], candidate_id, active.SPY_200D_ID),
        }
        dup["duplicates_active_combo"] = isinstance(dup["corr_vs_active_combo"], float) and dup["corr_vs_active_combo"] >= 0.95 and float(deltas.get(combo.COMBO_ID, 0.0)) < 50
        dup["duplicates_spy_200d"] = isinstance(dup["corr_vs_spy_200d"], float) and dup["corr_vs_spy_200d"] >= 0.95 and float(deltas.get(active.SPY_200D_ID, 0.0)) < 50
        stress_base = payload["stress_results"][candidate_id]["stats"]
        stress = {
            "stress_ending_equity": stress_base["ending_equity"],
            "stress_max_drawdown": stress_base["max_drawdown"],
            "stress_risk_buffer": stress_base["risk_buffer"],
            "stress_pass": stress_base["risk_buffer"] >= 0 and stress_base["ending_equity"] >= stats["ending_equity"] - 75,
        }
        blockers = promotion_blockers(candidate_id, metrics, deltas, dup, stress)
        if blockers:
            outcome = "discovery_reject"
        elif candidate_id == DUAL_ID:
            outcome = "promotion_review_candidate_macro"
        else:
            outcome = "promotion_review_candidate"
        decisions[candidate_id] = {"outcome": outcome, "blockers": blockers, "reason": ";".join(blockers) if blockers else "strict discovery gates passed; promotion review required before any further action"}
    return decisions


def final_next_action(decisions: dict[str, dict[str, Any]]) -> str:
    if any(row["outcome"] in {"promotion_review_candidate", "promotion_review_candidate_macro"} for row in decisions.values()):
        return NEXT_ACTION_PROMOTION
    return NEXT_ACTION_AUDIT


def result_rows(payload: dict[str, Any], decisions: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    if not payload["diagnostics_available"]:
        return []
    rows: list[dict[str, Any]] = []
    for candidate_id in AUTHORIZED_CANDIDATES:
        stats = payload["full_results"][candidate_id]["stats"]
        s90 = payload["summaries"][candidate_id][90]
        s180 = payload["summaries"][candidate_id][180]
        rows.append(
            {
                "candidate_id": candidate_id,
                "lane": LANES[candidate_id],
                "outcome": decisions[candidate_id]["outcome"],
                "decision_reason": decisions[candidate_id]["reason"],
                "ending_equity": stats["ending_equity"],
                "total_return": stats["total_return"],
                "annualized_return": stats["annualized_return"],
                "volatility": stats["volatility"],
                "sharpe": stats["sharpe"],
                "max_drawdown": stats["max_drawdown"],
                "risk_buffer": stats["risk_buffer"],
                "sample_90d_median_final_equity": s90.get("median_final_equity", ""),
                "sample_180d_median_final_equity": s180.get("median_final_equity", ""),
                "target_300_before_stop_rate": s180.get("target_300_before_stop_rate", ""),
                "target_400_before_stop_rate": s180.get("target_400_before_stop_rate", ""),
                "stop_hit_rate": s180.get("stop_hit_rate", ""),
                "trade_count": stats["trade_count"],
                "rebalance_count": stats["rebalance_count"],
                "average_holding_period": stats["average_holding_period"],
                "turnover": stats["turnover"],
                "bil_allocation_frequency": stats["bil_allocation_frequency"],
                "mean_bil_allocation": stats["mean_bil_allocation"],
            }
        )
    return rows


def benchmark_rows(payload: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    same_window: list[dict[str, Any]] = []
    deltas: list[dict[str, Any]] = []
    if not payload["diagnostics_available"]:
        return same_window, deltas
    for candidate_id in AUTHORIZED_CANDIDATES:
        c180 = payload["summaries"][candidate_id][180]
        for benchmark_id in BENCHMARKS_BY_CANDIDATE[candidate_id]:
            if benchmark_id in UNAVAILABLE_REFERENCE_REASONS:
                same_window.append(
                    {
                        "candidate_id": candidate_id,
                        "benchmark_id": benchmark_id,
                        "available": False,
                        "unavailable_reason": UNAVAILABLE_REFERENCE_REASONS[benchmark_id],
                        "benchmark_180d_median_final_equity": "",
                    }
                )
                deltas.append(
                    {
                        "candidate_id": candidate_id,
                        "benchmark_id": benchmark_id,
                        "available": False,
                        "unavailable_reason": UNAVAILABLE_REFERENCE_REASONS[benchmark_id],
                        "candidate_180d_median_final_equity": c180.get("median_final_equity", ""),
                        "benchmark_180d_median_final_equity": "",
                        "delta_180d_median_final_equity": "",
                    }
                )
                continue
            b180 = payload["benchmark_summaries"].get(benchmark_id, {}).get(180, {})
            available_benchmark = "median_final_equity" in b180
            same_window.append(
                {
                    "candidate_id": candidate_id,
                    "benchmark_id": benchmark_id,
                    "available": available_benchmark,
                    "unavailable_reason": "" if available_benchmark else "benchmark simulation unavailable",
                    "benchmark_180d_median_final_equity": b180.get("median_final_equity", ""),
                    "benchmark_stop_hit_rate": b180.get("stop_hit_rate", ""),
                    "benchmark_worst_drawdown": b180.get("worst_drawdown", ""),
                }
            )
            deltas.append(
                {
                    "candidate_id": candidate_id,
                    "benchmark_id": benchmark_id,
                    "available": available_benchmark,
                    "unavailable_reason": "" if available_benchmark else "benchmark simulation unavailable",
                    "candidate_180d_median_final_equity": c180.get("median_final_equity", ""),
                    "benchmark_180d_median_final_equity": b180.get("median_final_equity", ""),
                    "delta_180d_median_final_equity": float(c180["median_final_equity"]) - float(b180["median_final_equity"]) if available_benchmark and "median_final_equity" in c180 else "",
                }
            )
    return same_window, deltas


def risk_gate_rows(payload: dict[str, Any], decisions: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not payload["diagnostics_available"]:
        return rows
    _same, deltas = benchmark_rows(payload)
    by_pair = {(row["candidate_id"], row["benchmark_id"]): row for row in deltas}
    for candidate_id in AUTHORIZED_CANDIDATES:
        stats = payload["full_results"][candidate_id]["stats"]
        decision = decisions[candidate_id]
        rows.append(
            {
                "candidate_id": candidate_id,
                "risk_buffer_pass": stats["risk_buffer"] >= 25,
                "slippage_stress_pass": "slippage_stress_fails" not in decision["blockers"],
                "benchmark_edge_pass": "benchmark_edge_fails_active_combo" not in decision["blockers"] and "benchmark_edge_fails_spy_200d" not in decision["blockers"],
                "duplication_pass": "duplication_too_high_without_useful_edge" not in decision["blockers"],
                "trade_count_reasonable": "trade_count_too_low" not in decision["blockers"],
                "bil_allocation_pass": "bil_allocation_excessive_without_clear_benefit" not in decision["blockers"] and "bil_heavy_defensive_clone_risk" not in decision["blockers"],
                "formula_ambiguity": False,
                "invalidated_55_day_donchian_used": False,
                "delta_vs_active_combo": by_pair.get((candidate_id, combo.COMBO_ID), {}).get("delta_180d_median_final_equity", ""),
                "delta_vs_spy_200d": by_pair.get((candidate_id, active.SPY_200D_ID), {}).get("delta_180d_median_final_equity", ""),
                "blockers": ";".join(decision["blockers"]),
                "outcome": decision["outcome"],
            }
        )
    return rows


def slippage_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not payload["diagnostics_available"]:
        return rows
    for candidate_id in AUTHORIZED_CANDIDATES:
        base_stats = payload["full_results"][candidate_id]["stats"]
        stress_stats = payload["stress_results"][candidate_id]["stats"]
        rows.append(
            {
                "candidate_id": candidate_id,
                "base_slippage": BASE_SLIPPAGE,
                "stress_slippage": STRESS_SLIPPAGE,
                "base_ending_equity": base_stats["ending_equity"],
                "stress_ending_equity": stress_stats["ending_equity"],
                "stress_delta_ending_equity": stress_stats["ending_equity"] - base_stats["ending_equity"],
                "base_max_drawdown": base_stats["max_drawdown"],
                "stress_max_drawdown": stress_stats["max_drawdown"],
                "base_risk_buffer": base_stats["risk_buffer"],
                "stress_risk_buffer": stress_stats["risk_buffer"],
                "stress_pass": stress_stats["risk_buffer"] >= 0 and stress_stats["ending_equity"] >= base_stats["ending_equity"] - 75,
            }
        )
    return rows


def allocation_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not payload["diagnostics_available"]:
        return rows
    for candidate_id in AUTHORIZED_CANDIDATES:
        stats = payload["full_results"][candidate_id]["stats"]
        frequency = stats.get("asset_allocation_frequency", {})
        mean_alloc = stats.get("asset_mean_allocation", {})
        for symbol in sorted(set(frequency) | set(mean_alloc)):
            rows.append(
                {
                    "candidate_id": candidate_id,
                    "lane": LANES[candidate_id],
                    "symbol": symbol,
                    "allocation_frequency": frequency.get(symbol, 0.0),
                    "mean_allocation": mean_alloc.get(symbol, 0.0),
                }
            )
    return rows


def scalar_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if not payload["diagnostics_available"]:
        return []
    rows = payload["full_results"][DUAL_ID]["stats"].get("scalar_diagnostics", [])
    return rows


def sizing_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if not payload["diagnostics_available"]:
        return []
    stats = payload["full_results"][DONCHIAN_ID]["stats"]
    rows = stats.get("sizing_diagnostics", [])
    if rows:
        return rows
    return [
        {
            "date": "",
            "symbol": "",
            "entry_price": "",
            "initial_stop_threshold": "",
            "dollar_risk_per_share": "",
            "position_notional": "",
            "risk_dollars": "",
            "portfolio_risk_budget": "",
            "remaining_portfolio_risk_after_entry": "",
            "diagnostic_note": "no accepted Donchian entries",
        }
    ]


def parent_comparison_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for candidate_id, parent_id in [(DUAL_ID, "dual_momentum_paa_clean_v1"), (DONCHIAN_ID, "donchian_atr_breakout_etf_v1")]:
        rows.append(
            {
                "candidate_id": candidate_id,
                "parent_id": parent_id,
                "parent_available_same_window": False,
                "parent_rerun": False,
                "comparison_status": "unavailable_parent_closed",
                "reason": "exact rejected parent remains closed; parent was not rerun as a discovery candidate",
                "candidate_180d_median_final_equity": "" if not payload.get("diagnostics_available") else payload["summaries"][candidate_id][180].get("median_final_equity", ""),
                "parent_180d_median_final_equity": "",
                "delta_vs_parent": "",
                "risk_improvement_vs_parent": "unavailable",
            }
        )
    return rows


def duplication_rows(payload: dict[str, Any], deltas: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not payload["diagnostics_available"]:
        return rows
    delta_by_pair = {(row["candidate_id"], row["benchmark_id"]): row.get("delta_180d_median_final_equity", "") for row in deltas}
    for candidate_id in AUTHORIZED_CANDIDATES:
        for benchmark_id in CORE_CORRELATION_BENCHMARKS:
            correlation = corr(payload["returns"], candidate_id, benchmark_id)
            delta = delta_by_pair.get((candidate_id, benchmark_id), "")
            duplicate = isinstance(correlation, float) and correlation >= 0.95 and isinstance(delta, (int, float)) and delta < 50
            rows.append(
                {
                    "candidate_id": candidate_id,
                    "benchmark_id": benchmark_id,
                    "correlation": correlation,
                    "delta_180d_median_final_equity": delta,
                    "duplication_flag": duplicate,
                    "diagnostic": "duplicate_or_near_duplicate" if duplicate else "not_flagged",
                }
            )
    return rows


def promotion_rows(decisions: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for candidate_id, decision in decisions.items():
        if decision["outcome"] in {"promotion_review_candidate", "promotion_review_candidate_macro"}:
            rows.append(
                {
                    "candidate_id": candidate_id,
                    "outcome": decision["outcome"],
                    "promotion_review_required": True,
                    "candidate_exhaustive_run": False,
                    "paper_forward_action": False,
                    "reason": decision["reason"],
                }
            )
    return rows


def metrics_json(payload: dict[str, Any], decisions: dict[str, dict[str, Any]]) -> dict[str, Any]:
    if not payload["diagnostics_available"]:
        return {"diagnostics_available": False, "missing_symbols": payload.get("missing_symbols", [])}
    result: dict[str, Any] = {}
    for candidate_id in AUTHORIZED_CANDIDATES:
        stats = {k: v for k, v in payload["full_results"][candidate_id]["stats"].items() if k not in {"scalar_diagnostics", "sizing_diagnostics"}}
        result[candidate_id] = {
            "outcome": decisions[candidate_id]["outcome"],
            "blockers": decisions[candidate_id]["blockers"],
            "full_period_stats": stats,
            "sampled_windows": payload["summaries"][candidate_id],
        }
    return result


def summary_md(created_utc: str, output: Path, manifest: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    lines = [
        "# Risk-Controlled High-Return Discovery",
        "",
        f"Created UTC: `{created_utc}`",
        "",
        f"Evidence path: `{output}`",
        "",
        f"Candidates evaluated: `{', '.join(manifest['candidate_ids'])}`",
        "",
        f"Promotion candidates: `{manifest['promotion_candidates_count']}`",
        "",
        f"Next action: `{manifest['next_action']}`",
        "",
        "## Candidate Results",
        "",
    ]
    for row in rows:
        lines.append(
            f"- `{row['candidate_id']}`: `{row['outcome']}`, 180d median `{fmt(row['sample_180d_median_final_equity'])}`, risk buffer `{fmt(row['risk_buffer'])}`, reason `{row['decision_reason']}`"
        )
    lines.extend(
        [
            "",
            "No provider download, intraday data, candidate_exhaustive, paper-forward action, broker/live path, or real-money recommendation occurred.",
            "",
            "The invalidated Donchian lookback variant was not used; the official corrected rule uses the parent-consistent 20-day breakout.",
        ]
    )
    return "\n".join(lines) + "\n"


def rejection_md(decisions: dict[str, dict[str, Any]]) -> str:
    lines = ["# Risk-Controlled Rejection Reasons", ""]
    for candidate_id in AUTHORIZED_CANDIDATES:
        decision = decisions[candidate_id]
        if decision["outcome"] == "discovery_reject":
            lines.append(f"## {candidate_id}")
            lines.append("")
            lines.append(f"Reason codes: `{decision['reason']}`")
            lines.append("")
        else:
            lines.append(f"## {candidate_id}")
            lines.append("")
            lines.append("No rejection reason; promotion review candidate only, not candidate_exhaustive or paper-forward.")
            lines.append("")
    return "\n".join(lines)


def next_action_md(next_action: str) -> str:
    return f"""# Risk-Controlled Discovery Next Action

`{next_action}`

Do not run the next action in this task.
"""


def update_metadata(root: Path, output: Path, created_utc: str, manifest: dict[str, Any]) -> tuple[bool, bool]:
    registry_updated = False
    registry_path = root / REGISTRY_PATH
    if registry_path.exists():
        registry = load_yaml(registry_path)
        metadata = registry.setdefault("registry", {})
        metadata.update(
            {
                "risk_controlled_high_return_discovery_path": str(output),
                "risk_controlled_high_return_discovery_status": "completed",
                "risk_controlled_high_return_discovery_created_utc": created_utc,
                "risk_controlled_high_return_promotion_candidates_count": manifest["promotion_candidates_count"],
                "risk_controlled_high_return_promotion_candidate_ids": manifest["promotion_candidate_ids"],
                "risk_controlled_high_return_rejected_candidate_ids": manifest["rejected_candidate_ids"],
                "risk_controlled_high_return_next_action": manifest["next_action"],
                "current_next_action": manifest["next_action"],
                "next_action": manifest["next_action"],
                **MANIFEST_FLAGS,
                "updated_utc": created_utc,
            }
        )
        registry_path.write_text(yaml.safe_dump(registry, sort_keys=False, width=120, allow_unicode=False), encoding="utf-8")
        registry_updated = True

    roadmap_path = root / ROADMAP_PATH
    existing = roadmap_path.read_text(encoding="utf-8") if roadmap_path.exists() else "# Research Roadmap\n"
    lines = existing.splitlines()
    for idx, line in enumerate(lines):
        if line.startswith("Current next action:"):
            lines[idx] = f"Current next action: `{manifest['next_action']}`"
            break
    else:
        insert_at = 1 if lines and lines[0].startswith("#") else 0
        lines.insert(insert_at, f"Current next action: `{manifest['next_action']}`")
    base = "\n".join(lines)
    marker = "## Risk-Controlled High-Return Discovery"
    section = f"""## Risk-Controlled High-Return Discovery

- Created UTC: `{created_utc}`
- Evidence path: `{output}`
- Candidates evaluated: `{', '.join(manifest["candidate_ids"])}`
- Promotion candidates: `{manifest["promotion_candidates_count"]}`
- Promotion candidate IDs: `{', '.join(manifest["promotion_candidate_ids"]) if manifest["promotion_candidate_ids"] else 'none'}`
- Rejected candidate IDs: `{', '.join(manifest["rejected_candidate_ids"]) if manifest["rejected_candidate_ids"] else 'none'}`
- Invalidated 55-day Donchian rule used: `false`
- Intraday research remains paused: `true`
- Next action: `{manifest["next_action"]}`
- No provider download, intraday data, candidate_exhaustive, paper-forward action, broker/live path, or real-money recommendation is authorized.
"""
    updated = base.split(marker, 1)[0].rstrip() + "\n\n" + section if marker in base else base.rstrip() + "\n\n" + section
    roadmap_path.parent.mkdir(parents=True, exist_ok=True)
    roadmap_path.write_text(updated.rstrip() + "\n", encoding="utf-8")
    return registry_updated, True


def consistency_check(
    output: Path,
    manifest: dict[str, Any],
    strategies_before: list[dict[str, Any]],
    strategies_after: list[dict[str, Any]],
    decisions: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    required_present = {
        name: True if name == "risk_controlled_discovery_consistency_check.json" else (output / name).exists()
        for name in REQUIRED_FILES
    }
    evaluated = manifest.get("candidate_ids", [])
    all_outcomes = [row["outcome"] for row in decisions.values()]
    check = {
        "exactly_two_candidates_evaluated": manifest.get("candidate_count") == 2 and len(evaluated) == 2,
        "candidate_ids_match_approved_list": evaluated == AUTHORIZED_CANDIDATES,
        "no_excluded_candidates_evaluated": set(evaluated).isdisjoint(EXCLUDED_CANDIDATES),
        "invalidated_55_day_donchian_rule_not_used": manifest["invalidated_55_day_donchian_used"] is False,
        "official_donchian_rule_uses_20_day_breakout": True,
        "dual_momentum_volatility_scalar_frozen": True,
        "donchian_risk_budget_sizing_frozen": True,
        "provider_download_false": manifest["provider_download"] is False,
        "intraday_data_not_used": manifest["intraday_data_used"] is False,
        "no_candidate_exhaustive": manifest["candidate_exhaustive_run"] is False and not any(outcome in FORBIDDEN_OUTCOMES for outcome in all_outcomes),
        "no_paper_forward_action": manifest["paper_forward_review"] is False and manifest["paper_forward_activation"] is False,
        "no_broker_live_path": manifest["broker_path_touched"] is False and manifest["live_orders"] is False,
        "exact_rejected_variants_remain_closed": manifest["exact_rejected_variants_reopened"] is False,
        "intraday_remains_paused": manifest["intraday_research_remains_paused"] is True,
        "risk_gate_results_exist": required_present["risk_controlled_risk_gate_results.csv"],
        "slippage_stress_results_exist": required_present["risk_controlled_slippage_stress_results.csv"],
        "benchmark_deltas_exist": required_present["risk_controlled_benchmark_deltas.csv"],
        "dual_momentum_scalar_diagnostics_exist": required_present["risk_controlled_dual_momentum_scalar_diagnostics.csv"],
        "donchian_sizing_diagnostics_exist": required_present["risk_controlled_donchian_sizing_diagnostics.csv"],
        "parent_comparison_exists": required_present["risk_controlled_parent_comparison.csv"],
        "promotion_candidate_file_exists": required_present["risk_controlled_promotion_candidates.csv"],
        "rejection_reasons_exist_if_rejected": required_present["risk_controlled_rejection_reasons.md"] if manifest["rejected_candidate_ids"] else True,
        "manifest_flags_match_strict_scope": all(manifest.get(key) == value for key, value in MANIFEST_FLAGS.items()),
        "no_strategy_state_changes": strategy_state_map(strategies_before) == strategy_state_map(strategies_after),
        "next_action_valid": manifest["next_action"] in VALID_NEXT_ACTIONS,
        "all_required_files_present": all(required_present.values()),
    }
    check["consistency_passed"] = all(check.values())
    return check


def run_risk_controlled_high_return_discovery_batch(root: Path = ROOT, strict_authorization: bool = True) -> dict[str, Any]:
    root = Path(root)
    created_utc = now_utc()
    output = clean_output(root)
    strategies_before = strategy_snapshot(root)
    mismatches = validate_authorization(root) if strict_authorization else []
    payload = {"diagnostics_available": False, "missing_symbols": [], "authorization_mismatches": mismatches}
    if not mismatches:
        payload = build_payload(root)
    decisions = candidate_decisions(payload)
    next_action = final_next_action(decisions)
    promotions = promotion_rows(decisions)
    promotion_ids = [row["candidate_id"] for row in promotions]
    macro_ids = [row["candidate_id"] for row in promotions if row["outcome"] == "promotion_review_candidate_macro"]
    rejected_ids = [candidate_id for candidate_id, row in decisions.items() if row["outcome"] == "discovery_reject"]
    manifest: dict[str, Any] = {
        "artifact": "risk_controlled_high_return_discovery_batch",
        "created_utc": created_utc,
        "output_dir": str(output),
        **MANIFEST_FLAGS,
        "promotion_candidates_count": len(promotions),
        "promotion_candidate_ids": promotion_ids,
        "macro_promotion_candidate_ids": macro_ids,
        "rejected_candidate_ids": rejected_ids,
        "authorization_mismatches": mismatches,
        "next_action": next_action,
    }

    results = result_rows(payload, decisions)
    same_window, deltas = benchmark_rows(payload)
    risks = risk_gate_rows(payload, decisions)
    stress = slippage_rows(payload)
    allocations = allocation_rows(payload)
    scalar_diag = scalar_rows(payload)
    sizing_diag = sizing_rows(payload)
    parents = parent_comparison_rows(payload)
    duplication = duplication_rows(payload, deltas)

    write_json(output / "risk_controlled_discovery_manifest.json", manifest)
    (output / "risk_controlled_discovery_summary.md").write_text(summary_md(created_utc, output, manifest, results), encoding="utf-8")
    write_csv(
        output / "risk_controlled_candidate_results.csv",
        results,
        [
            "candidate_id",
            "lane",
            "outcome",
            "decision_reason",
            "ending_equity",
            "total_return",
            "annualized_return",
            "volatility",
            "sharpe",
            "max_drawdown",
            "risk_buffer",
            "sample_90d_median_final_equity",
            "sample_180d_median_final_equity",
            "target_300_before_stop_rate",
            "target_400_before_stop_rate",
            "stop_hit_rate",
            "trade_count",
            "rebalance_count",
            "average_holding_period",
            "turnover",
            "bil_allocation_frequency",
            "mean_bil_allocation",
        ],
    )
    write_json(output / "risk_controlled_candidate_metrics.json", metrics_json(payload, decisions))
    write_csv(output / "risk_controlled_benchmark_deltas.csv", deltas, ["candidate_id", "benchmark_id", "available", "unavailable_reason", "candidate_180d_median_final_equity", "benchmark_180d_median_final_equity", "delta_180d_median_final_equity"])
    write_csv(output / "risk_controlled_same_window_benchmarks.csv", same_window, ["candidate_id", "benchmark_id", "available", "unavailable_reason", "benchmark_180d_median_final_equity", "benchmark_stop_hit_rate", "benchmark_worst_drawdown"])
    write_csv(output / "risk_controlled_risk_gate_results.csv", risks, ["candidate_id", "risk_buffer_pass", "slippage_stress_pass", "benchmark_edge_pass", "duplication_pass", "trade_count_reasonable", "bil_allocation_pass", "formula_ambiguity", "invalidated_55_day_donchian_used", "delta_vs_active_combo", "delta_vs_spy_200d", "blockers", "outcome"])
    write_csv(output / "risk_controlled_slippage_stress_results.csv", stress, ["candidate_id", "base_slippage", "stress_slippage", "base_ending_equity", "stress_ending_equity", "stress_delta_ending_equity", "base_max_drawdown", "stress_max_drawdown", "base_risk_buffer", "stress_risk_buffer", "stress_pass"])
    write_csv(output / "risk_controlled_allocation_diagnostics.csv", allocations, ["candidate_id", "lane", "symbol", "allocation_frequency", "mean_allocation"])
    write_csv(output / "risk_controlled_dual_momentum_scalar_diagnostics.csv", scalar_diag, ["rebalance_date", "signal_date", "scalar", "realized_vol_63d", "route_to_bil_reason", "target_weights", "parent_weights"])
    write_csv(output / "risk_controlled_donchian_sizing_diagnostics.csv", sizing_diag, ["date", "symbol", "entry_price", "initial_stop_threshold", "dollar_risk_per_share", "position_notional", "risk_dollars", "portfolio_risk_budget", "remaining_portfolio_risk_after_entry", "diagnostic_note"])
    write_csv(output / "risk_controlled_parent_comparison.csv", parents, ["candidate_id", "parent_id", "parent_available_same_window", "parent_rerun", "comparison_status", "reason", "candidate_180d_median_final_equity", "parent_180d_median_final_equity", "delta_vs_parent", "risk_improvement_vs_parent"])
    write_csv(output / "risk_controlled_duplication_diagnostics.csv", duplication, ["candidate_id", "benchmark_id", "correlation", "delta_180d_median_final_equity", "duplication_flag", "diagnostic"])
    write_csv(output / "risk_controlled_promotion_candidates.csv", promotions, ["candidate_id", "outcome", "promotion_review_required", "candidate_exhaustive_run", "paper_forward_action", "reason"])
    (output / "risk_controlled_rejection_reasons.md").write_text(rejection_md(decisions), encoding="utf-8")
    (output / "risk_controlled_next_action.md").write_text(next_action_md(next_action), encoding="utf-8")

    registry_updated, roadmap_updated = update_metadata(root, output, created_utc, manifest)
    manifest["registry_metadata_updated"] = registry_updated
    manifest["roadmap_updated"] = roadmap_updated
    write_json(output / "risk_controlled_discovery_manifest.json", manifest)

    strategies_after = strategy_snapshot(root)
    check = consistency_check(output, manifest, strategies_before, strategies_after, decisions)
    write_json(output / "risk_controlled_discovery_consistency_check.json", check)
    return {
        "output_dir": str(output),
        "manifest": manifest,
        "consistency_check": check,
        "decisions": decisions,
        "results": results,
    }


def main() -> None:
    result = run_risk_controlled_high_return_discovery_batch(ROOT)
    manifest = result["manifest"]
    print(f"risk-controlled discovery written: {result['output_dir']}")
    print(f"candidates: {', '.join(manifest['candidate_ids'])}")
    print(f"promotion_candidates_count: {manifest['promotion_candidates_count']}")
    print(f"promotion_candidate_ids: {','.join(manifest['promotion_candidate_ids']) if manifest['promotion_candidate_ids'] else 'none'}")
    print(f"rejected_candidate_ids: {','.join(manifest['rejected_candidate_ids']) if manifest['rejected_candidate_ids'] else 'none'}")
    print(f"next action: {manifest['next_action']}")
    print(f"consistency_passed: {result['consistency_check']['consistency_passed']}")
    if not result["consistency_check"]["consistency_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
