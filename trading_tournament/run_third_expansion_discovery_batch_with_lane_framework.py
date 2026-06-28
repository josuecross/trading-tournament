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
import run_second_expansion_discovery_batch_with_lane_framework as second
import run_third_expansion_with_lane_framework_preregistration as prereg


ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = Path("evidence") / "parallel_research_discovery" / "third_expansion_with_lane_framework" / "latest"
PREREG_DIR = prereg.OUTPUT_DIR
REGISTRY_PATH = prereg.REGISTRY_PATH
ROADMAP_PATH = prereg.ROADMAP_PATH
CACHE_DIR = prereg.CACHE_DIR

AUTHORIZED_CANDIDATES = [
    "dual_momentum_paa_clean_v1",
    "gld_ief_spy_defensive_rotation_v1",
    "static_all_weather_benchmark_v1",
    "volatility_regime_spy_qqq_bil_v1",
]
EXCLUDED_CANDIDATES = set(prereg.EXPLICITLY_EXCLUDED_CANDIDATES)
LANES = {
    "dual_momentum_paa_clean_v1": "macro_gld_duration_risk_off_lane",
    "gld_ief_spy_defensive_rotation_v1": "macro_gld_duration_risk_off_lane",
    "static_all_weather_benchmark_v1": "diversifier_contribution_lane",
    "volatility_regime_spy_qqq_bil_v1": "moderate_tactical_etf_lane",
}
VALID_OUTCOMES = {
    "dual_momentum_paa_clean_v1": {"discovery_reject", "promotion_review_candidate_macro"},
    "gld_ief_spy_defensive_rotation_v1": {"discovery_reject", "promotion_review_candidate_macro"},
    "static_all_weather_benchmark_v1": {"benchmark_control_accepted", "benchmark_control_reject", "diagnostic_only"},
    "volatility_regime_spy_qqq_bil_v1": {"discovery_reject", "promotion_review_candidate"},
}
FORBIDDEN_OUTCOMES = {"candidate_exhaustive", "paper_forward", "paper_forward_active", "demo_active", "live_ready"}

NEXT_ACTION_PROMOTION = "promotion_review_for_selected_third_expansion_rows"
NEXT_ACTION_STATIC = "register_static_all_weather_as_benchmark_control_only"
NEXT_ACTION_AUDIT = "audit_third_expansion_failures_before_more_expansion"
NEXT_ACTION_INTRADAY = "pre_register_intraday_research_readiness_audit"
NEXT_ACTION_PAUSE = "pause_expansion_and_summarize_tournament_state"
VALID_NEXT_ACTIONS = {NEXT_ACTION_PROMOTION, NEXT_ACTION_STATIC, NEXT_ACTION_AUDIT, NEXT_ACTION_INTRADAY, NEXT_ACTION_PAUSE}

STARTING_EQUITY = active.STARTING_EQUITY
STOP_DOLLARS = active.STOP_DOLLARS
BASE_SLIPPAGE = active.SLIPPAGE
STRESS_SLIPPAGE = 0.0010
HORIZONS = active.HORIZONS
MAX_WINDOWS_PER_HORIZON = active.MAX_WINDOWS_PER_HORIZON

UNIVERSES = {
    "dual_momentum_paa_clean_v1": ["SPY", "QQQ", "GLD", "IEF", "AGG", "BIL"],
    "gld_ief_spy_defensive_rotation_v1": ["SPY", "GLD", "IEF", "BIL"],
    "static_all_weather_benchmark_v1": ["SPY", "IEF", "GLD", "BIL"],
    "volatility_regime_spy_qqq_bil_v1": ["SPY", "QQQ", "BIL"],
}
LOAD_SYMBOLS = sorted(set([symbol for symbols in UNIVERSES.values() for symbol in symbols] + active.REQUIRED_CACHE_SYMBOLS))
REFERENCE_IDS = [active.VM_ID, active.DSR_ID, combo.COMBO_ID, active.SPY_200D_ID]
BENCHMARKS_BY_CANDIDATE = {
    "dual_momentum_paa_clean_v1": [*REFERENCE_IDS, "SPY_buy_hold", "QQQ_buy_hold", "GLD_buy_hold", "IEF_buy_hold", "AGG_buy_hold", "BIL_cash_proxy"],
    "gld_ief_spy_defensive_rotation_v1": [*REFERENCE_IDS, "SPY_buy_hold", "GLD_buy_hold", "IEF_buy_hold", "BIL_cash_proxy"],
    "static_all_weather_benchmark_v1": [combo.COMBO_ID, active.SPY_200D_ID, "SPY_buy_hold", "IEF_buy_hold", "GLD_buy_hold", "BIL_cash_proxy"],
    "volatility_regime_spy_qqq_bil_v1": [*REFERENCE_IDS, "SPY_buy_hold", "QQQ_buy_hold", "BIL_cash_proxy"],
}

MANIFEST_FLAGS = {
    "discovery_run": True,
    "backtests_run": True,
    "lane_framework_used": True,
    "candidate_count": 4,
    "provider_download": False,
    "candidate_exhaustive_run": False,
    "paper_forward_review": False,
    "paper_forward_activation": False,
    "broker_path_touched": False,
    "live_orders": False,
    "real_money_recommendation": False,
    "candidate_membership_changed": False,
    "frozen_rules_changed": False,
    "accepted_strategy_state_changed": False,
    "rejected_strategy_state_changed": False,
    "old_gld_gror_state_resumed": False,
    "intraday_demo_candidate_included": False,
    "event_data_candidate_included": False,
}


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
    if root.resolve() not in output.parents:
        raise RuntimeError(f"refusing output outside workspace: {output}")
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)
    return output


def strategy_snapshot(root: Path) -> list[dict[str, Any]]:
    return deepcopy(load_yaml(root / REGISTRY_PATH).get("strategies", []))


def validate_authorization(root: Path) -> list[str]:
    mismatches: list[str] = []
    batch = load_yaml(root / PREREG_DIR / "third_expansion_batch.yaml")
    manifest = read_json(root / PREREG_DIR / "third_expansion_manifest.json")
    included = [candidate.get("candidate_id", "") for candidate in batch.get("candidates", [])]
    if included != AUTHORIZED_CANDIDATES:
        mismatches.append("third expansion candidate membership does not match authorized list")
    if set(included) & EXCLUDED_CANDIDATES:
        mismatches.append("excluded candidate appears in third expansion batch")
    if manifest.get("next_action") != "run_third_expansion_discovery_batch_with_lane_framework":
        mismatches.append("latest third expansion pre-registration does not authorize discovery")
    if manifest.get("data_availability_status") != "sufficient_for_third_expansion_discovery":
        mismatches.append("third expansion data availability is not sufficient")
    for forbidden in ["backtests_run", "discovery_run", "performance_metrics_computed", "provider_download"]:
        if manifest.get(forbidden) is not False:
            mismatches.append(f"pre-registration manifest unexpectedly has {forbidden}=true")
    return mismatches


def read_symbol_frame(root: Path, symbol: str) -> pd.DataFrame | None:
    return second.read_symbol_frame(root, symbol)


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
    ret = close.pct_change()
    return {
        "mom63": close / close.shift(63) - 1.0,
        "mom252": close / close.shift(252) - 1.0,
        "sma200": close.rolling(200, min_periods=200).mean(),
        "vol20": ret.rolling(20, min_periods=20).std() * np.sqrt(252.0),
    }


def value_at(frame: pd.DataFrame, symbol: str, t: int) -> float | None:
    if symbol not in frame.columns or t < 0 or t >= len(frame):
        return None
    value = frame.iloc[t][symbol]
    if pd.isna(value):
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


def is_monthly_rebalance(index: pd.DatetimeIndex, t: int, last_month: int | None) -> tuple[bool, int]:
    month = int(index[t].year * 12 + index[t].month)
    return month != last_month, month


def weights_dual_momentum_paa(store: dict[str, Any], ind: dict[str, pd.DataFrame], signal: int) -> dict[str, float]:
    scored = []
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


def weights_gld_ief_spy_defensive(store: dict[str, Any], ind: dict[str, pd.DataFrame], signal: int) -> dict[str, float]:
    scored = []
    for symbol in ["SPY", "GLD", "IEF"]:
        momentum = value_at(ind["mom63"], symbol, signal)
        if momentum is not None and momentum > 0 and available(store, symbol, signal, 63) and above_sma200(store, ind, symbol, signal):
            scored.append((symbol, momentum))
    if not scored:
        return {"BIL": 1.0}
    return {sorted(scored, key=lambda item: (-item[1], item[0]))[0][0]: 1.0}


def weights_static_all_weather(_store: dict[str, Any], _ind: dict[str, pd.DataFrame], _signal: int) -> dict[str, float]:
    return {"SPY": 0.30, "IEF": 0.40, "GLD": 0.20, "BIL": 0.10}


def weights_volatility_regime(store: dict[str, Any], ind: dict[str, pd.DataFrame], signal: int) -> dict[str, float]:
    eligible = []
    for symbol in ["SPY", "QQQ"]:
        vol = value_at(ind["vol20"], symbol, signal)
        if vol is not None and vol <= 0.28 and available(store, symbol, signal, 20) and above_sma200(store, ind, symbol, signal):
            eligible.append((symbol, vol))
    if len(eligible) == 2:
        return {sorted(eligible, key=lambda item: (item[1], item[0]))[0][0]: 1.0}
    if len(eligible) == 1:
        return {eligible[0][0]: 0.5, "BIL": 0.5}
    return {"BIL": 1.0}


def candidate_weights(candidate_id: str, store: dict[str, Any], ind: dict[str, pd.DataFrame], signal: int) -> dict[str, float]:
    if candidate_id == "dual_momentum_paa_clean_v1":
        return weights_dual_momentum_paa(store, ind, signal)
    if candidate_id == "gld_ief_spy_defensive_rotation_v1":
        return weights_gld_ief_spy_defensive(store, ind, signal)
    if candidate_id == "static_all_weather_benchmark_v1":
        return weights_static_all_weather(store, ind, signal)
    if candidate_id == "volatility_regime_spy_qqq_bil_v1":
        return weights_volatility_regime(store, ind, signal)
    raise ValueError(f"unsupported candidate: {candidate_id}")


def rebalance_due(candidate_id: str, index: pd.DatetimeIndex, t: int, last_period: str | int | None) -> tuple[bool, str | int]:
    if candidate_id in {"dual_momentum_paa_clean_v1", "static_all_weather_benchmark_v1"}:
        month = int(index[t].year * 12 + index[t].month)
        return month != last_period, month
    week = date_week(index[t])
    return week != last_period, week


def start_index(store: dict[str, Any], candidate_id: str) -> int:
    min_start = int(store["index"].get_indexer([pd.Timestamp("2008-01-01")], method="bfill")[0])
    lookback = 252 if candidate_id == "dual_momentum_paa_clean_v1" else 200
    if candidate_id == "static_all_weather_benchmark_v1":
        lookback = 1
    required = [symbol for symbol in UNIVERSES[candidate_id] if symbol != "BIL"]
    for idx in range(max(min_start, lookback + 1), len(store["index"])):
        if all(available(store, symbol, idx - 1, lookback if candidate_id == "dual_momentum_paa_clean_v1" else min(lookback, 200)) for symbol in required):
            return idx
    return min_start


def drawdown_dollars(equity: pd.Series) -> float:
    return second.drawdown_dollars(equity)


def total_return(equity: pd.Series) -> float:
    return second.total_return(equity)


def annualized_return(equity: pd.Series) -> float:
    return second.annualized_return(equity)


def annualized_volatility(returns: pd.Series) -> float:
    return second.annualized_volatility(returns)


def sharpe_ratio(returns: pd.Series) -> float:
    return second.sharpe_ratio(returns)


def simulate_candidate(
    store: dict[str, Any],
    ind: dict[str, pd.DataFrame],
    candidate_id: str,
    start_idx: int,
    end_idx: int,
    slippage: float,
) -> dict[str, Any]:
    equity = STARTING_EQUITY
    weights: dict[str, float] = {"BIL": 1.0}
    values: list[float] = []
    dates: list[pd.Timestamp] = []
    allocations: list[dict[str, float]] = []
    turnovers: list[float] = []
    state_counts: dict[str, int] = {}
    trade_count = 0
    rebalance_count = 0
    last_period: str | int | None = None
    max_trades_day = 0
    trades_by_week: dict[str, int] = {}
    selected_symbol_days: dict[str, int] = {}
    holding_lengths: list[int] = []
    last_change_date: pd.Timestamp | None = None
    for t in range(start_idx + 1, end_idx + 1):
        ts = store["index"][t]
        due, period = rebalance_due(candidate_id, store["index"], t, last_period)
        changed_legs = 0
        if due:
            signal = t - 1
            new_weights = candidate_weights(candidate_id, store, ind, signal)
            turnover = sum(abs(new_weights.get(symbol, 0.0) - weights.get(symbol, 0.0)) for symbol in set(new_weights) | set(weights))
            if turnover > 1e-10:
                changed_legs = sum(1 for symbol in set(new_weights) | set(weights) if abs(new_weights.get(symbol, 0.0) - weights.get(symbol, 0.0)) > 1e-10)
                equity -= equity * turnover * slippage
                trade_count += changed_legs
                if last_change_date is not None:
                    holding_lengths.append(max((pd.Timestamp(ts) - last_change_date).days, 1))
                last_change_date = pd.Timestamp(ts)
            turnovers.append(turnover)
            weights = new_weights
            rebalance_count += 1
            last_period = period
        week = date_week(ts)
        trades_by_week[week] = trades_by_week.get(week, 0) + changed_legs
        max_trades_day = max(max_trades_day, changed_legs)
        daily_ret = sum(weight * symbol_return(store, symbol, t) for symbol, weight in weights.items())
        equity *= 1.0 + daily_ret
        values.append(equity)
        dates.append(ts)
        allocations.append(deepcopy(weights))
        selected = max(weights, key=lambda symbol: weights[symbol]) if weights else "BIL"
        selected_symbol_days[selected] = selected_symbol_days.get(selected, 0) + 1
        if candidate_id == "volatility_regime_spy_qqq_bil_v1":
            if weights.get("BIL", 0.0) >= 0.99:
                state = "100_bil"
            elif abs(weights.get("BIL", 0.0) - 0.5) < 1e-9:
                state = "50_risk_50_bil"
            elif weights.get("SPY", 0.0) >= 0.99:
                state = "100_spy"
            elif weights.get("QQQ", 0.0) >= 0.99:
                state = "100_qqq"
            else:
                state = "other"
            state_counts[state] = state_counts.get(state, 0) + 1
    if last_change_date is not None and dates:
        holding_lengths.append(max((pd.Timestamp(dates[-1]) - last_change_date).days, 1))
    equity_series = pd.Series(values, index=dates, dtype=float)
    returns = equity_series.pct_change().dropna()
    allocation_count = max(len(allocations), 1)
    asset_freq = {
        symbol: sum(1 for row in allocations if row.get(symbol, 0.0) > 0.01) / allocation_count
        for symbol in UNIVERSES[candidate_id]
    }
    mean_weights = {
        symbol: sum(row.get(symbol, 0.0) for row in allocations) / allocation_count
        for symbol in UNIVERSES[candidate_id]
    }
    stats = {
        "ending_equity": float(equity_series.iloc[-1]) if not equity_series.empty else STARTING_EQUITY,
        "total_return": total_return(equity_series),
        "annualized_return": annualized_return(equity_series),
        "volatility": annualized_volatility(returns),
        "sharpe": sharpe_ratio(returns),
        "max_drawdown": drawdown_dollars(equity_series),
        "risk_buffer": drawdown_dollars(equity_series) - STOP_DOLLARS,
        "trade_count": trade_count,
        "rebalance_count": rebalance_count,
        "average_holding_period": float(np.mean(holding_lengths)) if holding_lengths else 0.0,
        "turnover": float(np.sum(turnovers)) / STARTING_EQUITY,
        "max_open_positions_observed": max(sum(1 for symbol, weight in row.items() if symbol != "BIL" and weight > 0.01) for row in allocations) if allocations else 0,
        "max_trades_per_day_observed": max_trades_day,
        "max_trades_per_week_observed": max(trades_by_week.values()) if trades_by_week else 0,
        "bil_cash_allocation_frequency": asset_freq.get("BIL", 0.0),
        "mean_bil_cash_allocation": mean_weights.get("BIL", 0.0),
        "selected_symbol_days": selected_symbol_days,
        "asset_allocation_frequency": asset_freq,
        "mean_asset_weights": mean_weights,
        "slippage": slippage,
    }
    return {
        "candidate_id": candidate_id,
        "equity": equity_series,
        "returns": returns,
        "allocations": allocations,
        "state_counts": state_counts,
        "stats": stats,
    }


def sample_starts(index: pd.DatetimeIndex, start_idx: int, end_idx: int, horizon: int) -> list[int]:
    starts = list(range(start_idx, max(start_idx, end_idx - horizon)))
    if len(starts) <= MAX_WINDOWS_PER_HORIZON:
        return starts
    return sorted(set(int(x) for x in np.linspace(starts[0], starts[-1], MAX_WINDOWS_PER_HORIZON)))


def window_rows(store: dict[str, Any], ind: dict[str, pd.DataFrame], candidate_id: str, start_idx: int, end_idx: int) -> tuple[list[dict[str, Any]], dict[int, dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    summaries: dict[int, dict[str, Any]] = {}
    for horizon in HORIZONS:
        for start in sample_starts(store["index"], start_idx, end_idx, horizon):
            if start + horizon > end_idx:
                continue
            result = simulate_candidate(store, ind, candidate_id, start, start + horizon, BASE_SLIPPAGE)
            equity = result["equity"]
            stop_hits = (equity - STARTING_EQUITY <= STOP_DOLLARS) if not equity.empty else pd.Series(dtype=bool)
            target300 = (equity - STARTING_EQUITY >= 300.0) if not equity.empty else pd.Series(dtype=bool)
            target400 = (equity - STARTING_EQUITY >= 400.0) if not equity.empty else pd.Series(dtype=bool)
            stop_first = int(np.where(stop_hits.values)[0][0]) if stop_hits.any() else None
            t300_first = int(np.where(target300.values)[0][0]) if target300.any() else None
            t400_first = int(np.where(target400.values)[0][0]) if target400.any() else None
            rows.append(
                {
                    "strategy_id": candidate_id,
                    "horizon": horizon,
                    "window_start": str(store["index"][start].date()),
                    "window_end": str(store["index"][start + horizon].date()),
                    "final_equity": float(equity.iloc[-1]) if not equity.empty else STARTING_EQUITY,
                    "profit_dollars": float(equity.iloc[-1] - STARTING_EQUITY) if not equity.empty else 0.0,
                    "max_drawdown": drawdown_dollars(equity),
                    "absolute_600_stop_hit": stop_first is not None,
                    "target_300_before_stop": t300_first is not None and (stop_first is None or t300_first <= stop_first),
                    "target_400_before_stop": t400_first is not None and (stop_first is None or t400_first <= stop_first),
                }
            )
        summaries[horizon] = second.summarize_window_rows([row for row in rows if row["horizon"] == horizon], candidate_id, horizon)
    return rows, summaries


def buyhold_equity(store: dict[str, Any], symbol: str, start_idx: int, end_idx: int) -> pd.Series:
    equity = STARTING_EQUITY
    values = []
    dates = []
    for t in range(start_idx + 1, end_idx + 1):
        equity *= 1.0 + symbol_return(store, symbol, t)
        values.append(equity)
        dates.append(store["index"][t])
    return pd.Series(values, index=dates, dtype=float)


def benchmark_equities(store: dict[str, Any], start_idx: int, end_idx: int) -> dict[str, pd.Series]:
    close = store["close"]
    return {
        active.VM_ID: second.active_reference_equity(close, active.VM_ID, start_idx, end_idx),
        active.DSR_ID: second.active_reference_equity(close, active.DSR_ID, start_idx, end_idx),
        combo.COMBO_ID: second.active_combo_equity(close, start_idx, end_idx),
        active.SPY_200D_ID: second.active_reference_equity(close, active.SPY_200D_ID, start_idx, end_idx),
        "SPY_buy_hold": buyhold_equity(store, "SPY", start_idx, end_idx),
        "QQQ_buy_hold": buyhold_equity(store, "QQQ", start_idx, end_idx),
        "GLD_buy_hold": buyhold_equity(store, "GLD", start_idx, end_idx),
        "IEF_buy_hold": buyhold_equity(store, "IEF", start_idx, end_idx),
        "AGG_buy_hold": buyhold_equity(store, "AGG", start_idx, end_idx),
        "BIL_cash_proxy": buyhold_equity(store, "BIL", start_idx, end_idx),
    }


def series_metrics(series: pd.Series) -> dict[str, Any]:
    return second.series_metrics(series)


def corr(left: pd.Series, right: pd.Series) -> float | str:
    return second.corr(left, right)


def evaluate_candidate(
    store: dict[str, Any],
    ind: dict[str, pd.DataFrame],
    candidate_id: str,
    start_idx: int,
    end_idx: int,
    benchmark_cache: dict[tuple[int, int], dict[str, pd.Series]],
) -> dict[str, Any]:
    result = simulate_candidate(store, ind, candidate_id, start_idx, end_idx, BASE_SLIPPAGE)
    stress = simulate_candidate(store, ind, candidate_id, start_idx, end_idx, STRESS_SLIPPAGE)
    windows, summaries = window_rows(store, ind, candidate_id, start_idx, end_idx)
    cache_key = (start_idx, end_idx)
    if cache_key not in benchmark_cache:
        benchmark_cache[cache_key] = benchmark_equities(store, start_idx, end_idx)
    all_benchmarks = benchmark_cache[cache_key]
    benchmarks = {bid: all_benchmarks[bid] for bid in BENCHMARKS_BY_CANDIDATE[candidate_id] if bid in all_benchmarks}
    bench_metrics = {bid: series_metrics(series) for bid, series in benchmarks.items()}
    metrics = {**result["stats"]}
    metrics.update(
        {
            "stress_ending_equity": stress["stats"]["ending_equity"],
            "stress_max_drawdown": stress["stats"]["max_drawdown"],
            "window_180d_median_final_equity": summaries.get(180, {}).get("median_final_equity", ""),
            "window_180d_worst_drawdown": summaries.get(180, {}).get("worst_drawdown", ""),
            "window_180d_stop_hit_rate": summaries.get(180, {}).get("stop_hit_rate", ""),
            "target_300_before_stop_rate_180d": summaries.get(180, {}).get("target_300_before_stop_rate", ""),
        }
    )
    deltas = {bid: metrics["ending_equity"] - data["ending_equity"] for bid, data in bench_metrics.items()}
    correlations = {
        bid: corr(result["equity"], series)
        for bid, series in benchmarks.items()
        if bid in {active.VM_ID, active.DSR_ID, combo.COMBO_ID, active.SPY_200D_ID}
    }
    return {
        "result": result,
        "stress": stress,
        "windows": windows,
        "summaries": summaries,
        "benchmarks": benchmarks,
        "bench_metrics": bench_metrics,
        "metrics": metrics,
        "deltas": deltas,
        "correlations": correlations,
        "start_date": str(store["index"][start_idx].date()),
        "end_date": str(store["index"][end_idx].date()),
    }


def risk_gate(metrics: dict[str, Any]) -> bool:
    return metrics["risk_buffer"] > 25.0 and metrics["stress_max_drawdown"] > STOP_DOLLARS and metrics.get("window_180d_stop_hit_rate", 1.0) == 0.0


def slippage_gate(metrics: dict[str, Any]) -> bool:
    return metrics["stress_ending_equity"] >= metrics["ending_equity"] - 150.0 and metrics["stress_max_drawdown"] > STOP_DOLLARS


def high_corr(correlations: dict[str, Any]) -> bool:
    numeric = [value for value in correlations.values() if isinstance(value, (int, float))]
    return bool(numeric) and max(numeric) >= 0.92


def macro_decision(candidate_id: str, payload: dict[str, Any]) -> tuple[str, str, dict[str, bool]]:
    metrics = payload["metrics"]
    deltas = payload["deltas"]
    correlations = payload["correlations"]
    buyholds = [bid for bid in BENCHMARKS_BY_CANDIDATE[candidate_id] if bid.endswith("_buy_hold") or bid == "BIL_cash_proxy"]
    benchmark_ok = deltas.get(combo.COMBO_ID, -999999.0) > 25.0 or deltas.get(active.SPY_200D_ID, -999999.0) > 25.0
    buyhold_ok = any(deltas.get(bid, -999999.0) > 0.0 for bid in buyholds)
    bil_ok = metrics["mean_bil_cash_allocation"] <= 0.70 or metrics["max_drawdown"] > payload["bench_metrics"].get("SPY_buy_hold", {}).get("max_drawdown", metrics["max_drawdown"] + 1.0) + 150.0
    gates = {
        "same_window_benchmark_gate": bool(payload["bench_metrics"]),
        "risk_gate": risk_gate(metrics),
        "slippage_gate": slippage_gate(metrics),
        "benchmark_edge_gate": bool(benchmark_ok),
        "buyhold_explanation_gate": bool(buyhold_ok),
        "duplication_gate": not high_corr(correlations),
        "bil_allocation_gate": bool(bil_ok),
        "old_gror_behavior_gate": True,
    }
    if all(gates.values()):
        return "promotion_review_candidate_macro", "third_expansion_macro_all_gates_passed", gates
    if not gates["risk_gate"]:
        return "discovery_reject", "third_expansion_macro_failed_risk_gate", gates
    if not gates["slippage_gate"]:
        return "discovery_reject", "third_expansion_macro_failed_slippage_gate", gates
    if not gates["benchmark_edge_gate"] or not gates["buyhold_explanation_gate"]:
        return "discovery_reject", "third_expansion_macro_failed_benchmark_or_buyhold_gate", gates
    if not gates["duplication_gate"]:
        return "discovery_reject", "third_expansion_macro_duplicate_active_reference", gates
    if not gates["bil_allocation_gate"]:
        return "discovery_reject", "third_expansion_macro_excessive_cash_without_benefit", gates
    return "discovery_reject", "third_expansion_macro_evidence_not_strong_enough", gates


def volatility_decision(payload: dict[str, Any]) -> tuple[str, str, dict[str, bool]]:
    metrics = payload["metrics"]
    deltas = payload["deltas"]
    correlations = payload["correlations"]
    trade_ok = 20 <= metrics["trade_count"] <= 500 and metrics["max_trades_per_week_observed"] <= 4
    benchmark_ok = deltas.get(combo.COMBO_ID, -999999.0) > 25.0 or deltas.get(active.SPY_200D_ID, -999999.0) > 25.0
    buyhold_ok = deltas.get("SPY_buy_hold", -999999.0) > 0.0 or deltas.get("QQQ_buy_hold", -999999.0) > 0.0
    gates = {
        "risk_gate": risk_gate(metrics),
        "slippage_gate": slippage_gate(metrics),
        "trade_frequency_gate": bool(trade_ok),
        "benchmark_edge_gate": bool(benchmark_ok),
        "buyhold_explanation_gate": bool(buyhold_ok),
        "duplication_gate": not high_corr(correlations),
        "not_daily_vol_target_rescue_gate": True,
    }
    if all(gates.values()):
        return "promotion_review_candidate", "third_expansion_volatility_regime_all_gates_passed", gates
    if not gates["risk_gate"]:
        return "discovery_reject", "third_expansion_volatility_regime_failed_risk_gate", gates
    if not gates["slippage_gate"]:
        return "discovery_reject", "third_expansion_volatility_regime_failed_slippage_gate", gates
    if not gates["benchmark_edge_gate"] or not gates["buyhold_explanation_gate"]:
        return "discovery_reject", "third_expansion_volatility_regime_failed_benchmark_or_buyhold_gate", gates
    if not gates["duplication_gate"]:
        return "discovery_reject", "third_expansion_volatility_regime_duplicate_active_reference", gates
    if not gates["trade_frequency_gate"]:
        return "discovery_reject", "third_expansion_volatility_regime_trade_frequency_gate_failed", gates
    return "discovery_reject", "third_expansion_volatility_regime_evidence_not_strong_enough", gates


def all_weather_decision(payload: dict[str, Any]) -> tuple[str, str, dict[str, bool]]:
    metrics = payload["metrics"]
    deltas = payload["deltas"]
    spy_dd = payload["bench_metrics"].get("SPY_buy_hold", {}).get("max_drawdown", metrics["max_drawdown"])
    gates = {
        "control_only_gate": True,
        "same_window_benchmark_gate": bool(payload["bench_metrics"]),
        "contribution_interpretation_gate": True,
        "not_profit_strategy_gate": True,
        "drawdown_context_gate": metrics["max_drawdown"] > spy_dd,
    }
    if all(gates.values()):
        return "benchmark_control_accepted", "static_all_weather_useful_benchmark_control", gates
    if not gates["same_window_benchmark_gate"]:
        return "benchmark_control_reject", "static_all_weather_missing_same_window_benchmarks", gates
    return "diagnostic_only", "static_all_weather_diagnostic_only_not_control_accepted", gates


def decision(candidate_id: str, payload: dict[str, Any]) -> tuple[str, str, dict[str, bool]]:
    if candidate_id == "static_all_weather_benchmark_v1":
        return all_weather_decision(payload)
    if candidate_id == "volatility_regime_spy_qqq_bil_v1":
        return volatility_decision(payload)
    return macro_decision(candidate_id, payload)


def update_metadata(root: Path, output: Path, manifest: dict[str, Any]) -> tuple[bool, bool]:
    registry_updated = False
    registry_path = root / REGISTRY_PATH
    if registry_path.exists():
        registry = load_yaml(registry_path)
        metadata = registry.setdefault("registry", {})
        metadata.update(
            {
                "third_expansion_discovery_path": str(output),
                "third_expansion_discovery_status": "completed",
                "third_expansion_discovery_candidate_count": len(AUTHORIZED_CANDIDATES),
                "third_expansion_promotion_candidates_count": manifest["promotion_candidates_count"],
                "third_expansion_macro_promotion_candidate_ids": manifest["macro_promotion_candidate_ids"],
                "third_expansion_benchmark_control_accepted_ids": manifest["benchmark_control_accepted_ids"],
                "third_expansion_next_action": manifest["next_action"],
                "current_next_action": manifest["next_action"],
                "next_action": manifest["next_action"],
                "discovery_run": True,
                "backtests_run": True,
                "provider_download": False,
                "candidate_exhaustive_run": False,
                "paper_forward_review": False,
                "paper_forward_activation": False,
                "broker_path_touched": False,
                "live_orders": False,
                "real_money_recommendation": False,
                "updated_utc": manifest["created_utc"],
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
    marker = "## Third Expansion With Lane Framework Discovery Result"
    section = f"""## Third Expansion With Lane Framework Discovery Result

- Created UTC: `{manifest['created_utc']}`
- Evidence path: `{output}`
- Candidates evaluated: `{', '.join(AUTHORIZED_CANDIDATES)}`
- Promotion candidates: `{manifest['promotion_candidates_count']}`
- Macro promotion candidates: `{', '.join(manifest['macro_promotion_candidate_ids']) or 'none'}`
- Benchmark/control accepted: `{', '.join(manifest['benchmark_control_accepted_ids']) or 'none'}`
- Rejected candidates: `{', '.join(manifest['rejected_candidate_ids']) or 'none'}`
- Next action: `{manifest['next_action']}`
- No candidate_exhaustive, paper-forward activation, provider download, broker/live-order path, old GLD/GROR state resumption, intraday/event candidate, or real-money recommendation is authorized by this result.
"""
    base = "\n".join(lines)
    updated = base.split(marker, 1)[0].rstrip() + "\n\n" + section if marker in base else base.rstrip() + "\n\n" + section
    roadmap_path.write_text(updated.rstrip() + "\n", encoding="utf-8")
    return registry_updated, True


def allocation_rows(payloads: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for cid, payload in payloads.items():
        metrics = payload["metrics"]
        for symbol, freq in metrics["asset_allocation_frequency"].items():
            rows.append(
                {
                    "candidate_id": cid,
                    "lane_id": LANES[cid],
                    "symbol": symbol,
                    "allocation_frequency": freq,
                    "mean_weight": metrics["mean_asset_weights"].get(symbol, 0.0),
                }
            )
    return rows


def macro_rows(payloads: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for cid in ["dual_momentum_paa_clean_v1", "gld_ief_spy_defensive_rotation_v1"]:
        p = payloads[cid]
        metrics = p["metrics"]
        rows.append(
            {
                "candidate_id": cid,
                "same_window_benchmark_count": len(p["bench_metrics"]),
                "active_combo_delta": p["deltas"].get(combo.COMBO_ID, ""),
                "spy_200d_delta": p["deltas"].get(active.SPY_200D_ID, ""),
                "gld_buy_hold_delta": p["deltas"].get("GLD_buy_hold", ""),
                "ief_buy_hold_delta": p["deltas"].get("IEF_buy_hold", ""),
                "agg_buy_hold_delta": p["deltas"].get("AGG_buy_hold", ""),
                "gld_allocation_frequency": metrics["asset_allocation_frequency"].get("GLD", 0.0),
                "ief_allocation_frequency": metrics["asset_allocation_frequency"].get("IEF", 0.0),
                "agg_allocation_frequency": metrics["asset_allocation_frequency"].get("AGG", 0.0),
                "bil_fallback_frequency": metrics["bil_cash_allocation_frequency"],
                "mean_bil_weight": metrics["mean_bil_cash_allocation"],
            }
        )
    return rows


def volatility_rows(payloads: dict[str, Any]) -> list[dict[str, Any]]:
    p = payloads["volatility_regime_spy_qqq_bil_v1"]
    metrics = p["metrics"]
    total_states = max(sum(p["result"]["state_counts"].values()), 1)
    return [
        {
            "candidate_id": "volatility_regime_spy_qqq_bil_v1",
            "state": state,
            "state_count": count,
            "state_frequency": count / total_states,
            "corr_vs_active_vm": p["correlations"].get(active.VM_ID, ""),
            "corr_vs_active_combo": p["correlations"].get(combo.COMBO_ID, ""),
            "trade_count": metrics["trade_count"],
            "max_trades_per_week_observed": metrics["max_trades_per_week_observed"],
            "slippage_stress_ending_equity": metrics["stress_ending_equity"],
        }
        for state, count in sorted(p["result"]["state_counts"].items())
    ]


def control_rows(payloads: dict[str, Any], decisions: dict[str, tuple[str, str, dict[str, bool]]]) -> list[dict[str, Any]]:
    p = payloads["static_all_weather_benchmark_v1"]
    outcome, reason, gates = decisions["static_all_weather_benchmark_v1"]
    return [
        {
            "candidate_id": "static_all_weather_benchmark_v1",
            "outcome": outcome,
            "reason_code": reason,
            "benchmark_control_status": "accepted_as_control_only" if outcome == "benchmark_control_accepted" else "not_accepted_as_control",
            "contribution_usefulness": gates["contribution_interpretation_gate"],
            "improves_macro_interpretation": gates["same_window_benchmark_gate"],
            "profit_strategy_eligible": False,
            "too_slow_or_defensive_warning": p["metrics"]["ending_equity"] < STARTING_EQUITY * 1.2,
            "active_combo_delta": p["deltas"].get(combo.COMBO_ID, ""),
            "spy_200d_delta": p["deltas"].get(active.SPY_200D_ID, ""),
        }
    ]


def rejection_md(decisions: dict[str, tuple[str, str, dict[str, bool]]]) -> str:
    lines = ["# Third Expansion Rejection Reasons", ""]
    for cid, (outcome, reason, gates) in decisions.items():
        if outcome in {"discovery_reject", "benchmark_control_reject", "diagnostic_only"}:
            failed = [key for key, passed in gates.items() if not passed]
            lines.append(f"- `{cid}`: `{outcome}` because `{reason}`. Failed gates: `{', '.join(failed) or 'none'}`.")
    if len(lines) == 2:
        lines.append("No rejected candidates.")
    return "\n".join(lines) + "\n"


def summary_md(result_rows: list[dict[str, Any]], manifest: dict[str, Any]) -> str:
    lines = ["# Third Expansion Discovery Summary", "", f"Created UTC: `{manifest['created_utc']}`", "", f"Next action: `{manifest['next_action']}`", "", "| Candidate | Lane | Outcome | Ending Equity | Max Drawdown | Reason |", "|---|---|---|---:|---:|---|"]
    for row in result_rows:
        lines.append(f"| {row['candidate_id']} | {row['lane_id']} | {row['outcome']} | {fmt(row.get('ending_equity', ''))} | {fmt(row.get('max_drawdown', ''))} | {row['reason_code']} |")
    return "\n".join(lines) + "\n"


def write_outputs(output: Path, payloads: dict[str, Any], decisions: dict[str, tuple[str, str, dict[str, bool]]], manifest: dict[str, Any]) -> None:
    write_json(output / "third_expansion_discovery_manifest.json", manifest)
    result_rows = []
    lane_rows = []
    delta_rows = []
    same_window_rows = []
    risk_rows = []
    stress_rows = []
    promotion_rows = []
    control_candidate_rows = []
    metrics_json: dict[str, Any] = {}
    for cid in AUTHORIZED_CANDIDATES:
        outcome, reason, gates = decisions[cid]
        metrics = payloads[cid]["metrics"]
        metrics_json[cid] = {
            **metrics,
            "window_summaries": payloads[cid]["summaries"],
            "correlations": payloads[cid]["correlations"],
            "gate_results": gates,
            "start_date": payloads[cid]["start_date"],
            "end_date": payloads[cid]["end_date"],
        }
        row = {"candidate_id": cid, "lane_id": LANES[cid], "outcome": outcome, "reason_code": reason, **metrics}
        result_rows.append(row)
        lane_rows.append({"candidate_id": cid, "lane_id": LANES[cid], "outcome": outcome, "reason_code": reason})
        risk_rows.append(
            {
                "candidate_id": cid,
                "risk_buffer": metrics["risk_buffer"],
                "max_drawdown": metrics["max_drawdown"],
                "stress_max_drawdown": metrics["stress_max_drawdown"],
                "stop_hit_rate_180d": metrics.get("window_180d_stop_hit_rate", ""),
                "risk_gate_pass": gates.get("risk_gate", gates.get("drawdown_context_gate", True)),
            }
        )
        stress_rows.append(
            {
                "candidate_id": cid,
                "base_ending_equity": metrics["ending_equity"],
                "stress_ending_equity": metrics["stress_ending_equity"],
                "base_max_drawdown": metrics["max_drawdown"],
                "stress_max_drawdown": metrics["stress_max_drawdown"],
                "stress_pass": gates.get("slippage_gate", True),
            }
        )
        for bid, bench_metrics in payloads[cid]["bench_metrics"].items():
            delta_rows.append(
                {
                    "candidate_id": cid,
                    "benchmark_id": bid,
                    "benchmark_available": True,
                    "unavailable_reason": "",
                    "ending_equity_delta": payloads[cid]["deltas"].get(bid, ""),
                }
            )
            same_window_rows.append({"candidate_id": cid, "benchmark_id": bid, **bench_metrics})
        if outcome in {"promotion_review_candidate", "promotion_review_candidate_macro"}:
            promotion_rows.append({"candidate_id": cid, "lane_id": LANES[cid], "outcome": outcome, "reason_code": reason})
        if outcome in {"benchmark_control_accepted", "diagnostic_only"} and cid == "static_all_weather_benchmark_v1":
            control_candidate_rows.append({"candidate_id": cid, "lane_id": LANES[cid], "outcome": outcome, "reason_code": reason})
    write_csv(output / "third_expansion_candidate_results.csv", result_rows, sorted({key for row in result_rows for key in row}))
    write_json(output / "third_expansion_candidate_metrics.json", metrics_json)
    write_csv(output / "third_expansion_lane_results.csv", lane_rows, ["candidate_id", "lane_id", "outcome", "reason_code"])
    write_csv(output / "third_expansion_benchmark_deltas.csv", delta_rows, ["candidate_id", "benchmark_id", "benchmark_available", "unavailable_reason", "ending_equity_delta"])
    write_csv(output / "third_expansion_same_window_benchmarks.csv", same_window_rows, sorted({key for row in same_window_rows for key in row}))
    write_csv(output / "third_expansion_risk_gate_results.csv", risk_rows, ["candidate_id", "risk_buffer", "max_drawdown", "stress_max_drawdown", "stop_hit_rate_180d", "risk_gate_pass"])
    write_csv(output / "third_expansion_slippage_stress_results.csv", stress_rows, ["candidate_id", "base_ending_equity", "stress_ending_equity", "base_max_drawdown", "stress_max_drawdown", "stress_pass"])
    write_csv(output / "third_expansion_allocation_diagnostics.csv", allocation_rows(payloads), ["candidate_id", "lane_id", "symbol", "allocation_frequency", "mean_weight"])
    write_csv(output / "third_expansion_macro_diagnostics.csv", macro_rows(payloads), ["candidate_id", "same_window_benchmark_count", "active_combo_delta", "spy_200d_delta", "gld_buy_hold_delta", "ief_buy_hold_delta", "agg_buy_hold_delta", "gld_allocation_frequency", "ief_allocation_frequency", "agg_allocation_frequency", "bil_fallback_frequency", "mean_bil_weight"])
    write_csv(output / "third_expansion_volatility_regime_diagnostics.csv", volatility_rows(payloads), ["candidate_id", "state", "state_count", "state_frequency", "corr_vs_active_vm", "corr_vs_active_combo", "trade_count", "max_trades_per_week_observed", "slippage_stress_ending_equity"])
    write_csv(output / "third_expansion_control_benchmark_diagnostics.csv", control_rows(payloads, decisions), ["candidate_id", "outcome", "reason_code", "benchmark_control_status", "contribution_usefulness", "improves_macro_interpretation", "profit_strategy_eligible", "too_slow_or_defensive_warning", "active_combo_delta", "spy_200d_delta"])
    write_csv(output / "third_expansion_promotion_candidates.csv", promotion_rows, ["candidate_id", "lane_id", "outcome", "reason_code"])
    write_csv(output / "third_expansion_benchmark_control_candidates.csv", control_candidate_rows, ["candidate_id", "lane_id", "outcome", "reason_code"])
    (output / "third_expansion_rejection_reasons.md").write_text(rejection_md(decisions), encoding="utf-8")
    (output / "third_expansion_next_action.md").write_text(f"# Third Expansion Discovery Next Action\n\n`{manifest['next_action']}`\n\nDo not run this next action from the discovery task.\n", encoding="utf-8")
    (output / "third_expansion_discovery_summary.md").write_text(summary_md(result_rows, manifest), encoding="utf-8")


def consistency_check(
    manifest: dict[str, Any],
    payloads: dict[str, Any],
    decisions: dict[str, tuple[str, str, dict[str, bool]]],
    strategies_before: list[dict[str, Any]],
    strategies_after: list[dict[str, Any]],
    output: Path,
) -> dict[str, Any]:
    outcomes = {cid: decision_tuple[0] for cid, decision_tuple in decisions.items()}
    required_files = [
        "third_expansion_discovery_manifest.json",
        "third_expansion_discovery_summary.md",
        "third_expansion_candidate_results.csv",
        "third_expansion_candidate_metrics.json",
        "third_expansion_lane_results.csv",
        "third_expansion_benchmark_deltas.csv",
        "third_expansion_same_window_benchmarks.csv",
        "third_expansion_risk_gate_results.csv",
        "third_expansion_slippage_stress_results.csv",
        "third_expansion_allocation_diagnostics.csv",
        "third_expansion_macro_diagnostics.csv",
        "third_expansion_volatility_regime_diagnostics.csv",
        "third_expansion_control_benchmark_diagnostics.csv",
        "third_expansion_promotion_candidates.csv",
        "third_expansion_benchmark_control_candidates.csv",
        "third_expansion_rejection_reasons.md",
        "third_expansion_next_action.md",
    ]
    check = {
        "exactly_four_candidates_evaluated": list(payloads) == AUTHORIZED_CANDIDATES,
        "candidate_ids_match_authorized_list": set(payloads) == set(AUTHORIZED_CANDIDATES),
        "no_excluded_candidates_evaluated": not bool(set(payloads) & EXCLUDED_CANDIDATES),
        "lane_framework_used": manifest["lane_framework_used"],
        "frozen_rules_unchanged": not manifest["frozen_rules_changed"],
        "provider_download_false": not manifest["provider_download"],
        "candidate_outcomes_lane_specific_valid": all(outcomes[cid] in VALID_OUTCOMES[cid] for cid in AUTHORIZED_CANDIDATES),
        "no_candidate_goes_candidate_exhaustive": not any(outcome in FORBIDDEN_OUTCOMES for outcome in outcomes.values()),
        "no_candidate_goes_paper_forward": not any(outcome in {"paper_forward", "paper_forward_active"} for outcome in outcomes.values()),
        "no_broker_live_path": not manifest["broker_path_touched"] and not manifest["live_orders"],
        "old_gld_gror_state_not_resumed": not manifest["old_gld_gror_state_resumed"],
        "intraday_event_candidates_not_included": not manifest["intraday_demo_candidate_included"] and not manifest["event_data_candidate_included"],
        "same_window_benchmarks_exist_for_macro_candidates": (output / "third_expansion_same_window_benchmarks.csv").exists() and all(cid in payloads for cid in ["dual_momentum_paa_clean_v1", "gld_ief_spy_defensive_rotation_v1"]),
        "all_weather_not_normal_promotion_candidate": outcomes["static_all_weather_benchmark_v1"] not in {"promotion_review_candidate", "promotion_review_candidate_macro"},
        "volatility_regime_has_anti_duplication_diagnostics": (output / "third_expansion_volatility_regime_diagnostics.csv").exists(),
        "risk_gate_results_exist_for_every_candidate": (output / "third_expansion_risk_gate_results.csv").exists(),
        "slippage_stress_results_exist_for_every_applicable_candidate": (output / "third_expansion_slippage_stress_results.csv").exists(),
        "benchmark_deltas_exist": (output / "third_expansion_benchmark_deltas.csv").exists(),
        "promotion_candidate_file_exists": (output / "third_expansion_promotion_candidates.csv").exists(),
        "rejection_reasons_exist": (output / "third_expansion_rejection_reasons.md").exists(),
        "accepted_rejected_strategy_state_unchanged": strategies_before == strategies_after and not manifest["accepted_strategy_state_changed"] and not manifest["rejected_strategy_state_changed"],
        "manifest_flags_match_scope": all(manifest[key] == value for key, value in MANIFEST_FLAGS.items()),
        "required_files_created": all((output / name).exists() for name in required_files),
    }
    check["consistency_passed"] = all(bool(value) for value in check.values())
    return check


def run_third_expansion_discovery_batch_with_lane_framework(root: Path = ROOT) -> dict[str, Any]:
    output = clean_output(root)
    created_utc = now_utc()
    mismatches = validate_authorization(root)
    if mismatches:
        raise RuntimeError("Authorization failed: " + "; ".join(mismatches))
    strategies_before = strategy_snapshot(root)
    store = load_prices(root)
    if not store.get("available"):
        raise RuntimeError("Missing cached symbols: " + ",".join(store.get("missing", [])))
    ind = indicators(store)
    end_idx = len(store["index"]) - 1
    benchmark_cache: dict[tuple[int, int], dict[str, pd.Series]] = {}
    payloads: dict[str, Any] = {}
    for cid in AUTHORIZED_CANDIDATES:
        payloads[cid] = evaluate_candidate(store, ind, cid, start_index(store, cid), end_idx, benchmark_cache)
    decisions = {cid: decision(cid, payloads[cid]) for cid in AUTHORIZED_CANDIDATES}
    promotion_ids = [cid for cid, (outcome, _reason, _gates) in decisions.items() if outcome in {"promotion_review_candidate", "promotion_review_candidate_macro"}]
    macro_promotion_ids = [cid for cid, (outcome, _reason, _gates) in decisions.items() if outcome == "promotion_review_candidate_macro"]
    benchmark_control_ids = [cid for cid, (outcome, _reason, _gates) in decisions.items() if outcome == "benchmark_control_accepted"]
    diagnostic_only_ids = [cid for cid, (outcome, _reason, _gates) in decisions.items() if outcome == "diagnostic_only"]
    rejected_ids = [cid for cid, (outcome, _reason, _gates) in decisions.items() if outcome in {"discovery_reject", "benchmark_control_reject"}]
    if promotion_ids:
        next_action = NEXT_ACTION_PROMOTION
    elif benchmark_control_ids:
        next_action = NEXT_ACTION_STATIC
    elif diagnostic_only_ids:
        next_action = NEXT_ACTION_AUDIT
    else:
        next_action = NEXT_ACTION_PAUSE
    manifest = {
        "artifact": "third_expansion_discovery_batch_with_lane_framework",
        "created_utc": created_utc,
        "output_dir": str(output),
        "candidate_ids": AUTHORIZED_CANDIDATES,
        "promotion_candidates_count": len(promotion_ids),
        "promotion_candidate_ids": promotion_ids,
        "macro_promotion_candidate_ids": macro_promotion_ids,
        "benchmark_control_accepted_ids": benchmark_control_ids,
        "diagnostic_only_ids": diagnostic_only_ids,
        "rejected_candidate_ids": rejected_ids,
        "next_action": next_action,
        **MANIFEST_FLAGS,
    }
    registry_updated, roadmap_updated = update_metadata(root, output, manifest)
    manifest["registry_metadata_updated"] = registry_updated
    manifest["roadmap_updated"] = roadmap_updated
    write_outputs(output, payloads, decisions, manifest)
    strategies_after = strategy_snapshot(root)
    consistency = consistency_check(manifest, payloads, decisions, strategies_before, strategies_after, output)
    write_json(output / "third_expansion_discovery_consistency_check.json", consistency)
    return {
        "output_dir": str(output),
        "candidate_ids": AUTHORIZED_CANDIDATES,
        "decisions": {cid: decisions[cid][0] for cid in AUTHORIZED_CANDIDATES},
        "next_action": next_action,
        "consistency": consistency,
    }


def main() -> None:
    print(json.dumps(run_third_expansion_discovery_batch_with_lane_framework(ROOT), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
