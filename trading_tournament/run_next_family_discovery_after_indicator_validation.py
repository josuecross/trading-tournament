from __future__ import annotations

import csv
import json
import math
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd
import yaml

import run_active_combo_benchmark_reporting as combo
import run_active_strategy_evidence_recompute as active


ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = Path("evidence") / "parallel_research_discovery" / "next_family_after_indicator_validation" / "latest"
PREREG_DIR = Path("evidence") / "pre_registered_lanes" / "next_family_after_indicator_validation" / "latest"
REGISTRY_PATH = Path("strategy_lab") / "strategy_registry.yaml"
ROADMAP_PATH = Path("strategy_lab") / "RESEARCH_ROADMAP.md"
COMPACT_STATE_PATH = Path("reports") / "compact_state" / "current_tournament_state.md"
DATA_CACHE_DIR = Path("data") / "cache"
MF_SAMPLE_DIR = Path("evidence") / "research_samples" / "managed_futures_etf_wrapper" / "latest"

CANDIDATE_ID = "mfv_equal_weight_trend_filter_v1"
SELECTED_FAMILY = "managed_futures_etf_wrapper"
LANE = "diversifier_contribution_lane"
NEXT_ACTION_AUDIT = "audit_next_family_discovery_result"
NEXT_ACTION_PROMOTION = "promotion_review_for_mfv_equal_weight_trend_filter_v1"
NEXT_ACTION_PAUSE = "pause_expansion_and_wait_for_manual_direction"
NEXT_ACTION_MANUAL = "manual_review_required_before_next_family_discovery"

VALID_NEXT_ACTIONS = {
    NEXT_ACTION_AUDIT,
    NEXT_ACTION_PROMOTION,
    NEXT_ACTION_PAUSE,
    NEXT_ACTION_MANUAL,
}
VALID_OUTCOMES = {
    "discovery_reject",
    "promotion_review_candidate",
    "promotion_review_candidate_macro",
    "promotion_review_candidate_macro_limited_history",
}
WRAPPERS = ["DBMF", "KMLM", "CTA", "FMF", "WTMF"]
REQUIRED_SYMBOLS = ["DBMF", "KMLM", "CTA", "FMF", "WTMF", "BIL", "SPY", "QQQ", "GLD", "TLT", "AGG"]
STATIC_ALL_WEATHER_WEIGHTS = {"SPY": 0.30, "IEF": 0.40, "GLD": 0.20, "BIL": 0.10}
LOAD_SYMBOLS = sorted(set(REQUIRED_SYMBOLS + ["IEF"] + active.REQUIRED_CACHE_SYMBOLS + active.OPTIONAL_BENCHMARK_SYMBOLS))
REFERENCE_IDS = [
    active.VM_ID,
    active.DSR_ID,
    combo.COMBO_ID,
    active.SPY_200D_ID,
    "SPY_buy_hold",
    "QQQ_buy_hold",
    "BIL_cash_proxy",
    "GLD_buy_hold",
    "TLT_buy_hold",
    "AGG_buy_hold",
    "static_all_weather_benchmark_v1",
    "managed_futures_wrapper_equal_weight_unfiltered_reference",
]
SAME_WINDOW_IDS = [CANDIDATE_ID] + REFERENCE_IDS
OLD_MANAGED_FUTURES_ROWS = {
    "managed_futures_etf_trend_wrapper_v1",
    "managed_futures_proxy_etf_trend_v1",
    "mf_wrapper_top1_trend_v1",
    "mf_wrapper_top2_risk_adjusted_v1",
    "mf_wrapper_plus_spy_70_30_v1",
    "mf_wrapper_defensive_cash_switch_v1",
    "mf_wrapper_plus_dsr_vm_combo_proxy_v1",
}

MANIFEST_FLAGS = {
    "next_family_discovery_only": True,
    "preflight_state_reconciled": True,
    "candidate_id": CANDIDATE_ID,
    "selected_family": SELECTED_FAMILY,
    "strategy_discovery_run": True,
    "backtests_run": True,
    "new_performance_metrics_computed": True,
    "indicator_library_dependency_added": False,
    "provider_download": False,
    "intraday_data_used": False,
    "candidate_exhaustive_run": False,
    "paper_forward_review": False,
    "paper_forward_activation": False,
    "broker_orders_submitted": False,
    "broker_orders_cancelled": False,
    "live_orders": False,
    "real_money_recommendation": False,
    "active_strategy_state_changed": False,
    "rejected_strategy_state_changed": False,
    "exact_rejected_variants_reopened": False,
    "intraday_research_remains_paused": True,
}


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: fmt(row.get(field, "")) for field in fields})


def fmt(value: Any) -> Any:
    if isinstance(value, (float, np.floating)):
        value = float(value)
        if math.isnan(value) or math.isinf(value):
            return ""
        return round(value, 6)
    return value


def strategy_snapshot(root: Path) -> list[dict[str, Any]]:
    return deepcopy(load_yaml(root / REGISTRY_PATH).get("strategies", []))


def approved_symbols(root: Path) -> set[str]:
    manifest = load_json(root / MF_SAMPLE_DIR / "managed_futures_etf_wrapper_manifest.json")
    approved = manifest.get("approved_symbols", [])
    return set(approved if isinstance(approved, list) else [])


def symbol_cache_report(root: Path, symbol: str, approved: set[str], created_utc: str) -> dict[str, Any]:
    path = root / DATA_CACHE_DIR / f"{symbol}.csv"
    row: dict[str, Any] = {
        "symbol": symbol,
        "approved_status": symbol in approved,
        "cache_present": path.exists(),
        "first_date": "",
        "last_date": "",
        "row_count": 0,
        "adjusted_close_availability": False,
        "null_count": "",
        "duplicate_date_count": "",
        "stale_flag": True,
        "supports_candidate_window": False,
    }
    if not path.exists():
        return row
    frame = pd.read_csv(path)
    dates = pd.to_datetime(frame["date"], errors="coerce") if "date" in frame else pd.Series(dtype="datetime64[ns]")
    valid_dates = dates.dropna()
    row["first_date"] = str(valid_dates.min().date()) if not valid_dates.empty else ""
    row["last_date"] = str(valid_dates.max().date()) if not valid_dates.empty else ""
    row["row_count"] = int(len(frame))
    adjusted_col = "adj_close" if "adj_close" in frame.columns else "raw_adj_close" if "raw_adj_close" in frame.columns else ""
    row["adjusted_close_availability"] = bool(adjusted_col and pd.to_numeric(frame[adjusted_col], errors="coerce").notna().any())
    quality_columns = [column for column in ["date", "open", "high", "low", "close", "adj_close", "volume"] if column in frame]
    row["null_count"] = int(frame[quality_columns].isna().sum().sum()) if quality_columns else int(frame.isna().sum().sum())
    row["duplicate_date_count"] = int(frame["date"].duplicated().sum()) if "date" in frame else ""
    created_date = datetime.fromisoformat(created_utc).date()
    last_date = valid_dates.max().date() if not valid_dates.empty else None
    row["stale_flag"] = bool(last_date is None or (created_date - last_date).days > 45)
    row["supports_candidate_window"] = bool(
        row["approved_status"]
        and row["cache_present"]
        and int(row["row_count"]) >= 252 + 126
        and row["adjusted_close_availability"]
        and row["duplicate_date_count"] == 0
        and not row["stale_flag"]
    )
    return row


def data_audit(root: Path, created_utc: str) -> list[dict[str, Any]]:
    approved = approved_symbols(root)
    return [symbol_cache_report(root, symbol, approved, created_utc) for symbol in REQUIRED_SYMBOLS]


def data_status(rows: list[dict[str, Any]]) -> str:
    return "sufficient_for_preregistered_discovery" if all(row["supports_candidate_window"] for row in rows) else "manual_review_required_data_incomplete"


def read_close_series(root: Path, symbol: str) -> pd.Series | None:
    path = root / DATA_CACHE_DIR / f"{symbol}.csv"
    if not path.exists():
        return None
    frame = pd.read_csv(path)
    if "date" not in frame:
        return None
    close_col = "adj_close" if "adj_close" in frame.columns else "raw_adj_close" if "raw_adj_close" in frame.columns else "close"
    if close_col not in frame.columns:
        return None
    clean = pd.DataFrame(
        {
            "date": pd.to_datetime(frame["date"], errors="coerce").dt.tz_localize(None),
            symbol: pd.to_numeric(frame[close_col], errors="coerce"),
        }
    )
    clean = clean.dropna().sort_values("date").drop_duplicates("date")
    if clean.empty:
        return None
    return clean.set_index("date")[symbol].astype(float)


def prepare_close(root: Path) -> tuple[pd.DataFrame, list[str]]:
    series: dict[str, pd.Series] = {}
    missing: list[str] = []
    for symbol in LOAD_SYMBOLS:
        close = read_close_series(root, symbol)
        if close is None:
            missing.append(symbol)
        else:
            series[symbol] = close
    if missing:
        return pd.DataFrame(), missing
    return pd.concat(series.values(), axis=1, join="outer", sort=True).sort_index(), []


def first_valid_signal_index(close: pd.DataFrame) -> int | None:
    sma200 = close[WRAPPERS].rolling(200, min_periods=200).mean()
    roc126 = close[WRAPPERS] / close[WRAPPERS].shift(126) - 1.0
    required_for_same_window = sorted(set(REQUIRED_SYMBOLS + ["IEF"] + active.REQUIRED_CACHE_SYMBOLS))
    for t in range(252, len(close) - 1):
        if close[required_for_same_window].iloc[t].isna().any():
            continue
        if close[required_for_same_window].iloc[t - 1].isna().any():
            continue
        if sma200.iloc[t].isna().any() or roc126.iloc[t].isna().any():
            continue
        return t
    return None


def sample_starts(close: pd.DataFrame, horizon: int, first_start: int) -> list[int]:
    starts = list(range(first_start, len(close) - horizon))
    if len(starts) <= active.MAX_WINDOWS_PER_HORIZON:
        return starts
    return sorted(set(int(x) for x in np.linspace(starts[0], starts[-1], active.MAX_WINDOWS_PER_HORIZON)))


def safe_return(close: pd.DataFrame, symbol: str, today: int) -> float:
    if symbol not in close.columns or today <= 0:
        return 0.0
    current = close.iloc[today][symbol]
    previous = close.iloc[today - 1][symbol]
    if pd.isna(current) or pd.isna(previous) or float(previous) == 0.0:
        return 0.0
    return float(current / previous - 1.0)


def candidate_weights(close: pd.DataFrame, signal: int) -> dict[str, float]:
    picks: list[str] = []
    for symbol in WRAPPERS:
        if signal < 199 or symbol not in close:
            continue
        current = close.iloc[signal][symbol]
        prior = close.iloc[signal - 126][symbol] if signal >= 126 else np.nan
        sma = close[symbol].iloc[signal - 199 : signal + 1].mean()
        if pd.isna(current) or pd.isna(prior) or pd.isna(sma) or float(prior) == 0.0:
            continue
        roc = float(current / prior - 1.0)
        if float(current) > float(sma) and roc > 0.0:
            picks.append(symbol)
    if not picks:
        return {"BIL": 1.0}
    weight = 1.0 / len(picks)
    return {symbol: weight for symbol in picks}


def mf_equal_weight_unfiltered_weights(_close: pd.DataFrame, _signal: int) -> dict[str, float]:
    return {symbol: 1.0 / len(WRAPPERS) for symbol in WRAPPERS}


def static_symbol_weights(symbol: str) -> Callable[[pd.DataFrame, int], dict[str, float]]:
    return lambda _close, _signal: {symbol: 1.0}


def static_all_weather_weights(_close: pd.DataFrame, _signal: int) -> dict[str, float]:
    return dict(STATIC_ALL_WEATHER_WEIGHTS)


def active_strategy_weight_func(strategy_id: str) -> Callable[[pd.DataFrame, int], dict[str, float]]:
    return lambda close, signal: active.strategy_weights(close, signal, strategy_id)


def weight_func(strategy_id: str) -> Callable[[pd.DataFrame, int], dict[str, float]]:
    if strategy_id == CANDIDATE_ID:
        return candidate_weights
    if strategy_id == "managed_futures_wrapper_equal_weight_unfiltered_reference":
        return mf_equal_weight_unfiltered_weights
    if strategy_id == "SPY_buy_hold":
        return static_symbol_weights("SPY")
    if strategy_id == "QQQ_buy_hold":
        return static_symbol_weights("QQQ")
    if strategy_id == "BIL_cash_proxy":
        return static_symbol_weights("BIL")
    if strategy_id == "GLD_buy_hold":
        return static_symbol_weights("GLD")
    if strategy_id == "TLT_buy_hold":
        return static_symbol_weights("TLT")
    if strategy_id == "AGG_buy_hold":
        return static_symbol_weights("AGG")
    if strategy_id == "static_all_weather_benchmark_v1":
        return static_all_weather_weights
    if strategy_id in {active.VM_ID, active.DSR_ID, active.SPY_200D_ID}:
        return active_strategy_weight_func(strategy_id)
    raise ValueError(f"unsupported weight strategy: {strategy_id}")


def simulate_weight_window(
    close: pd.DataFrame,
    start: int,
    horizon: int,
    strategy_id: str,
    weights_for_signal: Callable[[pd.DataFrame, int], dict[str, float]],
) -> dict[str, Any]:
    equity = active.STARTING_EQUITY
    peak = equity
    max_drawdown = 0.0
    last_month = None
    weights: dict[str, float] = {}
    stop = None
    target300 = None
    target400 = None
    months = np.array([dt.year * 12 + dt.month for dt in close.index], dtype=int)
    for offset in range(1, horizon + 1):
        today = start + offset
        signal = today - 1
        month = int(months[today])
        if month != last_month:
            new_weights = weights_for_signal(close, signal)
            turnover = sum(abs(new_weights.get(sym, 0.0) - weights.get(sym, 0.0)) for sym in set(new_weights) | set(weights))
            equity -= equity * turnover * active.SLIPPAGE
            weights = new_weights
            last_month = month
        daily_return = sum(weight * safe_return(close, symbol, today) for symbol, weight in weights.items())
        equity *= 1.0 + daily_return
        peak = max(peak, equity)
        max_drawdown = min(max_drawdown, equity - peak)
        profit = equity - active.STARTING_EQUITY
        if stop is None and profit <= active.STOP_DOLLARS:
            stop = offset
        if target300 is None and profit >= 300:
            target300 = offset
        if target400 is None and profit >= 400:
            target400 = offset
    return {
        "strategy_id": strategy_id,
        "horizon": horizon,
        "window_start": str(close.index[start].date()),
        "window_end": str(close.index[start + horizon].date()),
        "final_equity": equity,
        "profit_dollars": equity - active.STARTING_EQUITY,
        "max_drawdown": max_drawdown,
        "absolute_600_stop_hit": stop is not None,
        "target_300_before_stop": bool(target300 is not None and (stop is None or target300 <= stop)),
        "target_400_before_stop": bool(target400 is not None and (stop is None or target400 <= stop)),
    }


def simulate_active_combo_window(close: pd.DataFrame, start: int, horizon: int) -> dict[str, Any]:
    return combo.combo_window(close, start, horizon)


def run_windows(close: pd.DataFrame, strategy_id: str, first_start: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for horizon in active.HORIZONS:
        for start in sample_starts(close, horizon, first_start):
            if strategy_id == combo.COMBO_ID:
                rows.append(simulate_active_combo_window(close, start, horizon))
            else:
                rows.append(simulate_weight_window(close, start, horizon, strategy_id, weight_func(strategy_id)))
    return rows


def summarize_windows(rows: list[dict[str, Any]], strategy_id: str, horizon: int) -> dict[str, Any]:
    return active.summarize(rows, strategy_id, horizon)


def full_equity_series(
    close: pd.DataFrame,
    first_start: int,
    strategy_id: str,
    weights_for_signal: Callable[[pd.DataFrame, int], dict[str, float]],
) -> tuple[pd.Series, pd.DataFrame, list[dict[str, Any]]]:
    equity = active.STARTING_EQUITY
    weights: dict[str, float] = {}
    last_month = None
    values = [equity]
    dates = [close.index[first_start]]
    allocation_rows: list[dict[str, Any]] = []
    months = np.array([dt.year * 12 + dt.month for dt in close.index], dtype=int)
    for today in range(first_start + 1, len(close)):
        signal = today - 1
        month = int(months[today])
        if month != last_month:
            new_weights = weights_for_signal(close, signal)
            turnover = sum(abs(new_weights.get(sym, 0.0) - weights.get(sym, 0.0)) for sym in set(new_weights) | set(weights))
            equity -= equity * turnover * active.SLIPPAGE
            weights = new_weights
            allocation_rows.append(
                {
                    "rebalance_date": str(close.index[today].date()),
                    "strategy_id": strategy_id,
                    "weights": json.dumps({k: round(v, 6) for k, v in sorted(weights.items())}, sort_keys=True),
                    "turnover": turnover,
                    "equity_after_cost": equity,
                    "bil_weight": weights.get("BIL", 0.0),
                    "wrapper_count": len([symbol for symbol in WRAPPERS if weights.get(symbol, 0.0) > 0.0]),
                }
            )
            last_month = month
        daily_return = sum(weight * safe_return(close, symbol, today) for symbol, weight in weights.items())
        equity *= 1.0 + daily_return
        values.append(equity)
        dates.append(close.index[today])
    series = pd.Series(values, index=pd.DatetimeIndex(dates), name=strategy_id)
    frame = pd.DataFrame({"date": [str(dt.date()) for dt in series.index], "strategy_id": strategy_id, "equity": series.values})
    return series, frame, allocation_rows


def active_combo_full_equity(close: pd.DataFrame, first_start: int) -> pd.Series:
    vm_value = active.STARTING_EQUITY * 0.5
    dsr_value = active.STARTING_EQUITY * 0.5
    vm_weights: dict[str, float] = {}
    dsr_weights: dict[str, float] = {}
    last_month = None
    values = [active.STARTING_EQUITY]
    dates = [close.index[first_start]]
    months = np.array([dt.year * 12 + dt.month for dt in close.index], dtype=int)
    for today in range(first_start + 1, len(close)):
        signal = today - 1
        month = int(months[today])
        if month != last_month:
            total = vm_value + dsr_value
            vm_value = total * 0.5
            dsr_value = total * 0.5
            vm_weights = active.strategy_weights(close, signal, active.VM_ID)
            dsr_weights = active.strategy_weights(close, signal, active.DSR_ID)
            last_month = month
        vm_value *= 1.0 + sum(weight * safe_return(close, symbol, today) for symbol, weight in vm_weights.items())
        dsr_value *= 1.0 + sum(weight * safe_return(close, symbol, today) for symbol, weight in dsr_weights.items())
        values.append(vm_value + dsr_value)
        dates.append(close.index[today])
    return pd.Series(values, index=pd.DatetimeIndex(dates), name=combo.COMBO_ID)


def equity_metrics(equity: pd.Series) -> dict[str, Any]:
    returns = equity.pct_change().dropna()
    drawdowns = equity - equity.cummax()
    days = max(int(len(equity) - 1), 1)
    ending = float(equity.iloc[-1])
    total_return = ending / active.STARTING_EQUITY - 1.0
    vol = float(returns.std() * math.sqrt(252)) if len(returns) > 1 else 0.0
    sharpe = float(returns.mean() / returns.std() * math.sqrt(252)) if len(returns) > 1 and returns.std() > 0 else 0.0
    annualized = float((ending / active.STARTING_EQUITY) ** (252 / days) - 1.0) if ending > 0 else -1.0
    max_drawdown = float(drawdowns.min()) if not drawdowns.empty else 0.0
    return {
        "start_date": str(equity.index[0].date()),
        "end_date": str(equity.index[-1].date()),
        "trading_days": days,
        "ending_equity": ending,
        "total_return": total_return,
        "annualized_return": annualized,
        "volatility": vol,
        "sharpe": sharpe,
        "max_drawdown": max_drawdown,
        "risk_buffer": max_drawdown - active.STOP_DOLLARS,
    }


def corr(left: pd.Series, right: pd.Series) -> float | str:
    aligned = pd.concat([left.pct_change().rename("left"), right.pct_change().rename("right")], axis=1).dropna()
    return float(aligned["left"].corr(aligned["right"])) if len(aligned) > 5 else "unavailable"


def build_payload(root: Path) -> dict[str, Any]:
    close, missing = prepare_close(root)
    if missing or close.empty:
        return {"available": False, "missing": missing, "close": close}
    first_start = first_valid_signal_index(close)
    if first_start is None:
        return {"available": False, "missing": ["common_start_after_warmup"], "close": close}

    window_rows = {strategy_id: run_windows(close, strategy_id, first_start) for strategy_id in SAME_WINDOW_IDS}
    summaries = {
        strategy_id: {horizon: summarize_windows(window_rows[strategy_id], strategy_id, horizon) for horizon in active.HORIZONS}
        for strategy_id in SAME_WINDOW_IDS
    }
    equity_series: dict[str, pd.Series] = {}
    equity_frames: list[pd.DataFrame] = []
    allocation_rows: list[dict[str, Any]] = []
    for strategy_id in SAME_WINDOW_IDS:
        if strategy_id == combo.COMBO_ID:
            series = active_combo_full_equity(close, first_start)
            equity_series[strategy_id] = series
            equity_frames.append(pd.DataFrame({"date": [str(dt.date()) for dt in series.index], "strategy_id": strategy_id, "equity": series.values}))
            continue
        series, frame, allocations = full_equity_series(close, first_start, strategy_id, weight_func(strategy_id))
        equity_series[strategy_id] = series
        equity_frames.append(frame)
        if strategy_id in {CANDIDATE_ID, "managed_futures_wrapper_equal_weight_unfiltered_reference"}:
            allocation_rows.extend(allocations)

    first_dates = {symbol: str(close[symbol].first_valid_index().date()) for symbol in REQUIRED_SYMBOLS if symbol in close and close[symbol].first_valid_index() is not None}
    last_dates = {symbol: str(close[symbol].last_valid_index().date()) for symbol in REQUIRED_SYMBOLS if symbol in close and close[symbol].last_valid_index() is not None}
    common_days = int(len(close) - first_start)
    common_years = common_days / 252.0
    limited_label = "limited_history_common_window_short" if common_years < 5.0 else "sufficient_common_history"
    return {
        "available": True,
        "missing": [],
        "close": close,
        "first_start": first_start,
        "common_start_date": str(close.index[first_start].date()),
        "common_end_date": str(close.index[-1].date()),
        "common_days": common_days,
        "common_years": common_years,
        "limited_history_label": limited_label,
        "first_dates": first_dates,
        "last_dates": last_dates,
        "window_rows": window_rows,
        "summaries": summaries,
        "equity_series": equity_series,
        "equity_frame": pd.concat(equity_frames, ignore_index=True),
        "allocation_rows": allocation_rows,
    }


def same_window_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if not payload.get("available"):
        return []
    candidate = payload["equity_series"][CANDIDATE_ID]
    candidate_summary = payload["summaries"][CANDIDATE_ID][180]
    rows: list[dict[str, Any]] = []
    for strategy_id in SAME_WINDOW_IDS:
        metrics = equity_metrics(payload["equity_series"][strategy_id])
        summary = payload["summaries"][strategy_id][180]
        rows.append(
            {
                "benchmark_id": strategy_id,
                "candidate_id": CANDIDATE_ID,
                **metrics,
                "window_180d_median_final_equity": summary.get("median_final_equity", ""),
                "window_180d_target_300_before_stop_rate": summary.get("target_300_before_stop_rate", ""),
                "window_180d_target_400_before_stop_rate": summary.get("target_400_before_stop_rate", ""),
                "window_180d_worst_drawdown": summary.get("worst_drawdown", ""),
                "window_180d_stop_hit_rate": summary.get("stop_hit_rate", ""),
                "delta_180d_median_vs_candidate": float(summary["median_final_equity"]) - float(candidate_summary["median_final_equity"]),
                "correlation_vs_candidate": "self" if strategy_id == CANDIDATE_ID else corr(payload["equity_series"][strategy_id], candidate),
            }
        )
    return rows


def duplication_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if not payload.get("available"):
        return []
    candidate = payload["equity_series"][CANDIDATE_ID]
    rows: list[dict[str, Any]] = []
    for ref in REFERENCE_IDS:
        correlation = corr(candidate, payload["equity_series"][ref])
        status = "unavailable"
        if isinstance(correlation, float):
            status = "near_duplicate_risk" if abs(correlation) >= 0.90 else "not_flagged"
        rows.append({"reference_id": ref, "correlation_vs_candidate": correlation, "duplication_status": status})
    return rows


def allocation_diagnostics(payload: dict[str, Any]) -> dict[str, Any]:
    rows = [row for row in payload.get("allocation_rows", []) if row.get("strategy_id") == CANDIDATE_ID]
    if not rows:
        return {"rebalance_count": 0, "mean_bil_weight": 0.0, "max_bil_weight": 0.0, "mean_wrapper_count": 0.0}
    bil = [float(row.get("bil_weight", 0.0)) for row in rows]
    counts = [float(row.get("wrapper_count", 0.0)) for row in rows]
    return {
        "rebalance_count": len(rows),
        "mean_bil_weight": float(np.mean(bil)),
        "max_bil_weight": float(np.max(bil)),
        "mean_wrapper_count": float(np.mean(counts)),
    }


def decide_candidate(payload: dict[str, Any], data_availability_status: str) -> dict[str, Any]:
    if not payload.get("available") or data_availability_status != "sufficient_for_preregistered_discovery":
        return {
            "candidate_outcome": "discovery_reject",
            "promotion_candidates_count": 0,
            "next_action": NEXT_ACTION_MANUAL,
            "decision_label": "data_quality_or_cache_blocker",
            "gate_results": {"data_quality_gate": False},
            "rationale": "Preflight/data availability failed, so discovery should not be interpreted as actionable.",
        }
    summaries = payload["summaries"]
    s180 = summaries[CANDIDATE_ID][180]
    combo180 = summaries[combo.COMBO_ID][180]
    vm180 = summaries[active.VM_ID][180]
    dsr180 = summaries[active.DSR_ID][180]
    spy180 = summaries["SPY_buy_hold"][180]
    static180 = summaries["static_all_weather_benchmark_v1"][180]
    alloc = allocation_diagnostics(payload)
    duplicates = duplication_rows(payload)
    max_abs_corr = max((abs(row["correlation_vs_candidate"]) for row in duplicates if isinstance(row["correlation_vs_candidate"], float)), default=0.0)

    candidate_median = float(s180["median_final_equity"])
    active_reference_median = max(float(combo180["median_final_equity"]), float(vm180["median_final_equity"]), float(dsr180["median_final_equity"]))
    risk_buffer = float(s180["worst_drawdown"]) - active.STOP_DOLLARS
    target_rate = float(s180["target_300_before_stop_rate"])
    gate_results = {
        "data_quality_gate": True,
        "small_account_risk_gate": risk_buffer >= 0.0,
        "active_reference_edge_gate": candidate_median >= active_reference_median + 25.0,
        "profit_progress_gate": candidate_median >= 3300.0 and target_rate >= 0.40,
        "cash_behavior_gate": not (alloc["mean_bil_weight"] > 0.65 and candidate_median <= float(summaries["BIL_cash_proxy"][180]["median_final_equity"]) + 25.0),
        "duplication_gate": max_abs_corr < 0.90,
        "same_window_benchmark_gate": candidate_median >= min(float(spy180["median_final_equity"]), float(static180["median_final_equity"])),
        "limited_history_gate": payload["limited_history_label"] == "sufficient_common_history",
    }

    failures: list[str] = []
    if not gate_results["small_account_risk_gate"]:
        failures.append("risk_buffer_too_thin")
    if not gate_results["active_reference_edge_gate"]:
        failures.append("weaker_than_active_references")
    if not gate_results["profit_progress_gate"]:
        failures.append("too_slow_for_profit_goal")
    if not gate_results["cash_behavior_gate"]:
        failures.append("excessive_bil_cash_behavior_without_benefit")
    if not gate_results["duplication_gate"]:
        failures.append("duplicate_or_near_duplicate")
    if not gate_results["same_window_benchmark_gate"]:
        failures.append("no_clear_additive_contribution")

    strong_but_limited = (
        not failures
        and payload["limited_history_label"] != "sufficient_common_history"
        and candidate_median >= active_reference_median + 25.0
    )
    if strong_but_limited:
        return {
            "candidate_outcome": "promotion_review_candidate_macro_limited_history",
            "promotion_candidates_count": 1,
            "next_action": NEXT_ACTION_AUDIT,
            "decision_label": "promising_but_limited_history",
            "gate_results": gate_results,
            "rationale": "The row passed core discovery gates but common managed-futures wrapper history is short, so audit is required before promotion review.",
        }
    if not failures and payload["limited_history_label"] == "sufficient_common_history":
        return {
            "candidate_outcome": "promotion_review_candidate_macro",
            "promotion_candidates_count": 1,
            "next_action": NEXT_ACTION_PROMOTION,
            "decision_label": "clean_discovery_candidate",
            "gate_results": gate_results,
            "rationale": "The row passed discovery gates with sufficient common history.",
        }
    return {
        "candidate_outcome": "discovery_reject",
        "promotion_candidates_count": 0,
        "next_action": NEXT_ACTION_PAUSE,
        "decision_label": failures[0] if failures else "limited_history_not_actionable",
        "gate_results": gate_results,
        "rationale": "Rejected by discovery gates: " + ", ".join(failures or ["limited_history_not_actionable"]),
    }


def validate_preflight(root: Path) -> tuple[list[str], dict[str, Any], dict[str, Any]]:
    mismatches: list[str] = []
    prereg_manifest = load_json(root / PREREG_DIR / "next_family_preregistration_manifest.json")
    specs = load_yaml(root / PREREG_DIR / "candidate_specs.yaml")
    registry = load_yaml(root / REGISTRY_PATH)
    roadmap = (root / ROADMAP_PATH).read_text(encoding="utf-8") if (root / ROADMAP_PATH).exists() else ""
    compact = (root / COMPACT_STATE_PATH).read_text(encoding="utf-8") if (root / COMPACT_STATE_PATH).exists() else ""

    candidates = specs.get("candidates", [])
    candidate_ids = [candidate.get("candidate_id") for candidate in candidates]
    if prereg_manifest.get("candidate_ids") != [CANDIDATE_ID]:
        mismatches.append("preregistration manifest candidate_ids mismatch")
    if prereg_manifest.get("candidate_count") != 1:
        mismatches.append("preregistration manifest candidate_count is not 1")
    if prereg_manifest.get("selected_family") != SELECTED_FAMILY:
        mismatches.append("preregistration manifest selected_family mismatch")
    if prereg_manifest.get("data_availability_status") != "sufficient_for_preregistered_discovery":
        mismatches.append("preregistration manifest data availability is not sufficient")
    if prereg_manifest.get("indicator_library_dependency_added") is not False:
        mismatches.append("indicator library dependency is not false in preregistration manifest")
    if prereg_manifest.get("intraday_research_remains_paused") is not True:
        mismatches.append("intraday pause is not true in preregistration manifest")
    if candidate_ids != [CANDIDATE_ID]:
        mismatches.append("candidate_specs.yaml does not contain exactly the authorized candidate")
    candidate = candidates[0] if candidates else {}
    if candidate.get("candidate_id") in OLD_MANAGED_FUTURES_ROWS or CANDIDATE_ID in OLD_MANAGED_FUTURES_ROWS:
        mismatches.append("candidate id reopens an old managed-futures rejected row")
    if candidate.get("family") != SELECTED_FAMILY or candidate.get("lane") != LANE:
        mismatches.append("candidate family/lane mismatch")
    if candidate.get("rules_frozen") is not True:
        mismatches.append("candidate rules are not frozen")
    rule = candidate.get("rule", {})
    if "equal weight all wrappers" not in str(rule.get("allocation", "")):
        mismatches.append("candidate rule does not record equal-weight wrapper allocation")
    if "top1" in CANDIDATE_ID or "top2" in CANDIDATE_ID:
        mismatches.append("candidate id appears to replay top1/top2 row")
    meta = registry.get("registry", {})
    if meta.get("current_next_action") != "run_next_family_discovery_after_indicator_validation" and meta.get("official_current_next_action") != "run_next_family_discovery_after_indicator_validation":
        mismatches.append("registry does not authorize next-family discovery")
    if "run_next_family_discovery_after_indicator_validation" not in roadmap:
        mismatches.append("roadmap does not identify the current discovery next action")
    compact_stale = "run_next_family_discovery_after_indicator_validation" not in compact or CANDIDATE_ID not in compact
    return mismatches, {"prereg_manifest": prereg_manifest, "candidate": candidate, "compact_stale": compact_stale}, registry


def reconcile_compact_state(root: Path, created_utc: str, compact_stale: bool) -> dict[str, Any]:
    state = f"""# Current Tournament State

Created UTC: `{created_utc}`

Current research mode: `next_family_after_indicator_validation_preregistered`

Current next action before discovery: `run_next_family_discovery_after_indicator_validation`

Selected family: `{SELECTED_FAMILY}`

Authorized candidate ID: `{CANDIDATE_ID}`

## Active Accepted / Paper-Demo Observations

- `paper_forward_vm_quality_lowvol_proxy_v1` remains active/accepted/frozen.
- `paper_forward_dsr_sector_equal_weight_defensive_filter_v1` remains active/accepted/frozen.

## Benchmark Controls

- `static_all_weather_benchmark_v1` remains benchmark/control only.
- Active combo, active VM, active DSR, SPY, QQQ, BIL, GLD, TLT, AGG, and static all-weather are references/controls, not new promotions.

## Paused / Closed State

- Expansion remains paused until this discovery authorization.
- Intraday research remains paused.
- Exact rejected variants remain closed.
- Old managed-futures top1/top2 rows are historical context only and are not replayed.

## Forbidden Actions

- No additional strategy discovery beyond `{CANDIDATE_ID}`.
- No new candidates.
- No tuning.
- No candidate_exhaustive.
- No paper-forward review or activation.
- No provider download.
- No intraday data use.
- No indicator library dependency.
- No broker/live-order path activation or order action.
- No real-money recommendation.
"""
    write_text(root / COMPACT_STATE_PATH, state)
    return {
        "compact_state_was_stale": compact_stale,
        "compact_state_reconciled": True,
        "compact_state_path": str((root / COMPACT_STATE_PATH).resolve()),
    }


def update_roadmap_and_registry(root: Path, output: Path, created_utc: str, manifest: dict[str, Any]) -> None:
    registry_path = root / REGISTRY_PATH
    registry = load_yaml(registry_path)
    meta = registry.setdefault("registry", {})
    meta.update(
        {
            "next_family_discovery_after_indicator_validation_path": str(output.resolve()),
            "next_family_discovery_after_indicator_validation_status": "completed",
            "next_family_discovery_after_indicator_validation_created_utc": created_utc,
            "next_family_discovery_candidate_id": manifest["candidate_id"],
            "next_family_discovery_candidate_outcome": manifest["candidate_outcome"],
            "next_family_discovery_promotion_candidates_count": manifest["promotion_candidates_count"],
            "next_family_discovery_limited_history_label": manifest["limited_history_label"],
            "next_family_discovery_next_action": manifest["next_action"],
            "current_next_action": manifest["next_action"],
            "official_current_next_action": manifest["next_action"],
            "next_action": manifest["next_action"],
            "strategy_discovery_run": True,
            "backtests_run": True,
            "new_performance_metrics_computed": True,
            "indicator_library_dependency_added": False,
            "provider_download": False,
            "intraday_data_used": False,
            "candidate_exhaustive_run": False,
            "paper_forward_review": False,
            "paper_forward_activation": False,
            "broker_orders_submitted": False,
            "broker_orders_cancelled": False,
            "live_orders": False,
            "real_money_recommendation": False,
            "intraday_research_remains_paused": True,
        }
    )
    registry_path.write_text(yaml.safe_dump(registry, sort_keys=False, width=120, allow_unicode=False), encoding="utf-8")

    roadmap_path = root / ROADMAP_PATH
    roadmap = roadmap_path.read_text(encoding="utf-8") if roadmap_path.exists() else "# Research Roadmap\n"
    compact = f"""## Compact Current State

- Updated UTC: `{created_utc}`
- Current research mode: `next_family_discovery_after_indicator_validation_completed`
- Official current next action: `{manifest['next_action']}`
- Next-family discovery evidence: `{output.resolve()}`
- Selected family: `{SELECTED_FAMILY}`
- Candidate evaluated: `{CANDIDATE_ID}`
- Candidate outcome: `{manifest['candidate_outcome']}`
- Promotion candidates count: `{manifest['promotion_candidates_count']}`
- Limited-history label: `{manifest['limited_history_label']}`
- Data availability status: `{manifest['data_availability_status']}`
- Active VM and active DSR preserved.
- `static_all_weather_benchmark_v1` remains benchmark/control only.
- Exact rejected variants remain closed.
- Intraday remains paused: `true`
- No provider download, indicator dependency install, candidate_exhaustive, paper-forward action, broker/live path, or real-money recommendation was performed.
"""
    section = f"""## Next Family Discovery After Indicator Validation

- Created UTC: `{created_utc}`
- Evidence path: `{output.resolve()}`
- Discovery scope: `{CANDIDATE_ID}` only
- Selected family: `{SELECTED_FAMILY}`
- Candidate outcome: `{manifest['candidate_outcome']}`
- Decision label: `{manifest['decision_label']}`
- Promotion candidates count: `{manifest['promotion_candidates_count']}`
- Limited-history label: `{manifest['limited_history_label']}`
- Next action: `{manifest['next_action']}`
- Forbidden paths remained closed: candidate_exhaustive, paper-forward, provider download, intraday, broker/live order, and real-money recommendation.
"""
    roadmap = replace_or_append_section(roadmap, "## Compact Current State", compact)
    roadmap = replace_or_append_section(roadmap, "## Next Family Discovery After Indicator Validation", section)
    write_text(roadmap_path, roadmap)


def replace_or_append_section(text: str, header: str, section: str) -> str:
    if header not in text:
        return text.rstrip() + "\n\n" + section.rstrip() + "\n"
    start = text.index(header)
    next_start = text.find("\n## ", start + len(header))
    if next_start == -1:
        return text[:start].rstrip() + "\n\n" + section.rstrip() + "\n"
    return text[:start].rstrip() + "\n\n" + section.rstrip() + "\n\n" + text[next_start + 1 :].lstrip()


def summary_md(created_utc: str, output: Path, manifest: dict[str, Any], decision: dict[str, Any], metrics: dict[str, Any]) -> str:
    return f"""# Next Family Discovery After Indicator Validation

Created UTC: `{created_utc}`

Evidence path: `{output.resolve()}`

Candidate evaluated: `{CANDIDATE_ID}`

Selected family: `{SELECTED_FAMILY}`

Candidate outcome: `{manifest['candidate_outcome']}`

Decision label: `{decision['decision_label']}`

Promotion candidates count: `{manifest['promotion_candidates_count']}`

Limited-history label: `{manifest['limited_history_label']}`

Next action: `{manifest['next_action']}`

Key 180d rolling metrics:

- Median final equity: `{fmt(metrics.get('window_180d_median_final_equity'))}`
- Target +300 before stop rate: `{fmt(metrics.get('window_180d_target_300_before_stop_rate'))}`
- Worst drawdown: `{fmt(metrics.get('window_180d_worst_drawdown'))}`
- Stop hit rate: `{fmt(metrics.get('window_180d_stop_hit_rate'))}`

This packet ran only the pre-registered candidate. It did not run candidate_exhaustive, paper-forward review or activation, provider downloads, intraday data, indicator-library installation, broker/live paths, or real-money recommendation.
"""


def preflight_md(preflight: dict[str, Any], mismatches: list[str]) -> str:
    mismatch_lines = "\n".join(f"- {item}" for item in mismatches) if mismatches else "- none"
    return f"""# Preflight State Reconciliation

Compact state stale before reconciliation: `{preflight['compact_state_was_stale']}`

Compact state reconciled: `{preflight['compact_state_reconciled']}`

Authorized candidate: `{CANDIDATE_ID}`

Selected family: `{SELECTED_FAMILY}`

Mismatches:

{mismatch_lines}

Discovery was allowed only after roadmap, registry, preregistration, candidate specs, compact state, and local data checks were reconciled.
"""


def limited_history_md(payload: dict[str, Any]) -> str:
    if not payload.get("available"):
        return "# Candidate Window And Limited History Report\n\nPayload unavailable.\n"
    first_dates = "\n".join(f"- `{symbol}` first valid: `{date}`" for symbol, date in sorted(payload["first_dates"].items()))
    return f"""# Candidate Window And Limited History Report

Common usable start date: `{payload['common_start_date']}`

Common end date: `{payload['common_end_date']}`

Common usable trading days: `{payload['common_days']}`

Approximate common usable years: `{fmt(payload['common_years'])}`

Limited-history label: `{payload['limited_history_label']}`

Interpretation: managed-futures wrappers have staggered inception dates. Same-window benchmarks are used, and results must not be compared to full-history benchmark results without this label.

Required symbol first-valid dates:

{first_dates}
"""


def candidate_result_md(decision: dict[str, Any], metrics: dict[str, Any], allocation: dict[str, Any]) -> str:
    gates = "\n".join(f"- `{key}`: `{value}`" for key, value in decision["gate_results"].items())
    return f"""# Candidate Result: `{CANDIDATE_ID}`

Outcome: `{decision['candidate_outcome']}`

Decision label: `{decision['decision_label']}`

Rationale: {decision['rationale']}

Key metrics:

- Ending equity: `{fmt(metrics.get('ending_equity'))}`
- Annualized return: `{fmt(metrics.get('annualized_return'))}`
- Volatility: `{fmt(metrics.get('volatility'))}`
- Sharpe: `{fmt(metrics.get('sharpe'))}`
- Max drawdown: `{fmt(metrics.get('max_drawdown'))}`
- Risk buffer vs -600: `{fmt(metrics.get('risk_buffer'))}`
- 180d median final equity: `{fmt(metrics.get('window_180d_median_final_equity'))}`
- 180d target +300 before stop rate: `{fmt(metrics.get('window_180d_target_300_before_stop_rate'))}`

Allocation diagnostics:

- Rebalance count: `{allocation['rebalance_count']}`
- Mean BIL weight: `{fmt(allocation['mean_bil_weight'])}`
- Mean wrapper count: `{fmt(allocation['mean_wrapper_count'])}`

Gate results:

{gates}
"""


def duplication_review_md(rows: list[dict[str, Any]]) -> str:
    lines = ["# Duplication Review", "", "| reference | correlation vs candidate | status |", "|---|---:|---|"]
    for row in rows:
        lines.append(f"| `{row['reference_id']}` | `{fmt(row['correlation_vs_candidate'])}` | `{row['duplication_status']}` |")
    lines.append("")
    lines.append("Prior managed-futures top1/top2 rows are treated as historical context only and were not replayed.")
    return "\n".join(lines)


def risk_gate_review_md(decision: dict[str, Any], metrics: dict[str, Any]) -> str:
    gates = "\n".join(f"- `{key}`: `{value}`" for key, value in decision["gate_results"].items())
    return f"""# Risk Gate Review

Candidate outcome: `{decision['candidate_outcome']}`

180d worst drawdown: `{fmt(metrics.get('window_180d_worst_drawdown'))}`

Full-window max drawdown: `{fmt(metrics.get('max_drawdown'))}`

Full-window risk buffer vs -600: `{fmt(metrics.get('risk_buffer'))}`

Gate results:

{gates}

Drawdown improvement alone is not sufficient; the candidate also needed objective progress and additive behavior versus active references.
"""


def rationale_md(decision: dict[str, Any]) -> str:
    return f"""# Rejection Or Promotion Rationale

Candidate: `{CANDIDATE_ID}`

Outcome: `{decision['candidate_outcome']}`

Decision label: `{decision['decision_label']}`

Promotion candidates count: `{decision['promotion_candidates_count']}`

Rationale: {decision['rationale']}

No candidate may proceed directly to candidate_exhaustive, paper-forward, demo active, live ready, or real-money usage from this discovery packet.
"""


def next_action_md(manifest: dict[str, Any]) -> str:
    return f"""# Next Family Discovery Next Action

Exact next action: `{manifest['next_action']}`

Do not run the next action from this discovery task.
"""


def consistency_check(manifest: dict[str, Any], output: Path) -> dict[str, Any]:
    check = {
        "discovery_limited_to_authorized_candidate": manifest["candidate_id"] == CANDIDATE_ID,
        "candidate_count_evaluated_is_one": manifest["candidate_count_evaluated"] == 1,
        "preflight_state_reconciliation_exists": (output / "preflight_state_reconciliation.md").exists(),
        "no_indicator_library_dependency_added": manifest["indicator_library_dependency_added"] is False,
        "no_provider_download": manifest["provider_download"] is False,
        "no_intraday_data_used": manifest["intraday_data_used"] is False,
        "no_candidate_exhaustive": manifest["candidate_exhaustive_run"] is False,
        "no_paper_forward_action": manifest["paper_forward_review"] is False and manifest["paper_forward_activation"] is False,
        "no_broker_orders_submitted": manifest["broker_orders_submitted"] is False,
        "no_broker_orders_cancelled": manifest["broker_orders_cancelled"] is False,
        "no_live_orders": manifest["live_orders"] is False,
        "no_real_money_recommendation": manifest["real_money_recommendation"] is False,
        "active_strategy_state_preserved": manifest["active_strategy_state_changed"] is False,
        "rejected_strategy_state_preserved": manifest["rejected_strategy_state_changed"] is False,
        "exact_rejected_variants_not_reopened": manifest["exact_rejected_variants_reopened"] is False,
        "intraday_remains_paused": manifest["intraday_research_remains_paused"] is True,
        "same_window_benchmark_comparison_exists": (output / "same_window_benchmark_comparison.csv").exists(),
        "limited_history_report_exists": (output / "candidate_window_and_limited_history_report.md").exists(),
        "duplication_review_exists": (output / "duplication_review.md").exists(),
        "risk_gate_review_exists": (output / "risk_gate_review.md").exists(),
        "candidate_outcome_valid": manifest["candidate_outcome"] in VALID_OUTCOMES,
        "next_action_valid": manifest["next_action"] in VALID_NEXT_ACTIONS,
        "manifest_flags_match_strict_scope": all(manifest.get(key) == value for key, value in MANIFEST_FLAGS.items()),
    }
    check["consistency_passed"] = all(check.values())
    return check


def write_outputs(
    root: Path,
    output: Path,
    created_utc: str,
    manifest: dict[str, Any],
    preflight: dict[str, Any],
    mismatches: list[str],
    payload: dict[str, Any],
    decision: dict[str, Any],
    data_rows: list[dict[str, Any]],
) -> None:
    output.mkdir(parents=True, exist_ok=True)
    benchmark_rows = same_window_rows(payload)
    metrics_by_id = {row["benchmark_id"]: row for row in benchmark_rows}
    candidate_metrics = dict(metrics_by_id.get(CANDIDATE_ID, {}))
    candidate_metrics.update(
        {
            "candidate_id": CANDIDATE_ID,
            "window_summaries": payload.get("summaries", {}).get(CANDIDATE_ID, {}),
            "allocation_diagnostics": allocation_diagnostics(payload) if payload.get("available") else {},
            "decision": decision,
        }
    )
    duplication = duplication_rows(payload)

    write_json(output / "next_family_discovery_manifest.json", manifest)
    write_text(output / "next_family_discovery_summary.md", summary_md(created_utc, output, manifest, decision, candidate_metrics))
    write_text(output / "preflight_state_reconciliation.md", preflight_md(preflight, mismatches))
    write_text(output / f"candidate_result_{CANDIDATE_ID}.md", candidate_result_md(decision, candidate_metrics, candidate_metrics.get("allocation_diagnostics", {})))
    write_json(output / f"candidate_metrics_{CANDIDATE_ID}.json", candidate_metrics)
    write_text(output / "candidate_window_and_limited_history_report.md", limited_history_md(payload))
    write_csv(
        output / "same_window_benchmark_comparison.csv",
        benchmark_rows,
        [
            "benchmark_id",
            "candidate_id",
            "start_date",
            "end_date",
            "trading_days",
            "ending_equity",
            "total_return",
            "annualized_return",
            "volatility",
            "sharpe",
            "max_drawdown",
            "risk_buffer",
            "window_180d_median_final_equity",
            "window_180d_target_300_before_stop_rate",
            "window_180d_target_400_before_stop_rate",
            "window_180d_worst_drawdown",
            "window_180d_stop_hit_rate",
            "delta_180d_median_vs_candidate",
            "correlation_vs_candidate",
        ],
    )
    write_text(output / "duplication_review.md", duplication_review_md(duplication))
    write_text(output / "risk_gate_review.md", risk_gate_review_md(decision, candidate_metrics))
    write_text(output / "rejection_or_promotion_rationale.md", rationale_md(decision))
    write_text(output / "next_family_discovery_next_action.md", next_action_md(manifest))
    write_json(output / "next_family_discovery_consistency_check.json", {"consistency_passed": False})
    write_csv(
        output / "data_availability_audit.csv",
        data_rows,
        [
            "symbol",
            "approved_status",
            "cache_present",
            "first_date",
            "last_date",
            "row_count",
            "adjusted_close_availability",
            "null_count",
            "duplicate_date_count",
            "stale_flag",
            "supports_candidate_window",
        ],
    )
    if payload.get("available"):
        payload["equity_frame"].to_csv(output / "candidate_and_reference_equity_series.csv", index=False)
        write_csv(
            output / "candidate_allocation_trace.csv",
            [row for row in payload["allocation_rows"] if row.get("strategy_id") == CANDIDATE_ID],
            ["rebalance_date", "strategy_id", "weights", "turnover", "equity_after_cost", "bil_weight", "wrapper_count"],
        )


def run_next_family_discovery_after_indicator_validation(root: Path = ROOT) -> dict[str, Any]:
    root = root.resolve()
    created_utc = now_utc()
    output = root / OUTPUT_DIR
    strategies_before = strategy_snapshot(root)

    mismatches, prereg_context, _registry = validate_preflight(root)
    preflight = reconcile_compact_state(root, created_utc, prereg_context.get("compact_stale", True)) if not mismatches else {
        "compact_state_was_stale": prereg_context.get("compact_stale", True),
        "compact_state_reconciled": False,
        "compact_state_path": str((root / COMPACT_STATE_PATH).resolve()),
    }
    data_rows = data_audit(root, created_utc)
    availability = data_status(data_rows)
    if availability != "sufficient_for_preregistered_discovery":
        mismatches.append("data availability is not sufficient for preregistered discovery")

    payload = build_payload(root) if not mismatches else {"available": False, "missing": mismatches}
    decision = decide_candidate(payload, availability) if not mismatches else {
        "candidate_outcome": "discovery_reject",
        "promotion_candidates_count": 0,
        "next_action": NEXT_ACTION_MANUAL,
        "decision_label": "preflight_failed",
        "gate_results": {"preflight_gate": False},
        "rationale": "Preflight failed: " + "; ".join(mismatches),
    }
    limited_label = payload.get("limited_history_label", "not_applicable_preflight_failed")
    manifest = {
        "created_utc": created_utc,
        "output_dir": str(output.resolve()),
        **MANIFEST_FLAGS,
        "preflight_state_reconciled": bool(preflight["compact_state_reconciled"]),
        "strategy_discovery_run": not mismatches,
        "backtests_run": not mismatches,
        "new_performance_metrics_computed": not mismatches,
        "candidate_count_evaluated": 1 if not mismatches else 0,
        "promotion_candidates_count": decision["promotion_candidates_count"],
        "candidate_outcome": decision["candidate_outcome"],
        "decision_label": decision["decision_label"],
        "limited_history_label": limited_label,
        "data_availability_status": availability,
        "next_action": decision["next_action"],
    }
    if mismatches:
        manifest["preflight_state_reconciled"] = False

    write_outputs(root, output, created_utc, manifest, preflight, mismatches, payload, decision, data_rows)
    strategies_after = strategy_snapshot(root)
    if strategies_before != strategies_after:
        manifest["active_strategy_state_changed"] = True
        manifest["rejected_strategy_state_changed"] = True
    if not mismatches:
        update_roadmap_and_registry(root, output, created_utc, manifest)
        strategies_after_update = strategy_snapshot(root)
        if strategies_before != strategies_after_update:
            manifest["active_strategy_state_changed"] = True
            manifest["rejected_strategy_state_changed"] = True
    write_json(output / "next_family_discovery_manifest.json", manifest)
    consistency = consistency_check(manifest, output)
    write_json(output / "next_family_discovery_consistency_check.json", consistency)
    return {
        "output_dir": str(output),
        "preflight_state_reconciled": manifest["preflight_state_reconciled"],
        "candidate_id": CANDIDATE_ID,
        "candidate_outcome": manifest["candidate_outcome"],
        "promotion_candidates_count": manifest["promotion_candidates_count"],
        "limited_history_label": manifest["limited_history_label"],
        "data_availability_status": manifest["data_availability_status"],
        "next_action": manifest["next_action"],
        "consistency_passed": consistency["consistency_passed"],
    }


def main() -> None:
    print(json.dumps(run_next_family_discovery_after_indicator_validation(ROOT), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
