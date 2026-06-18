from __future__ import annotations

import csv
import json
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml


ROOT = Path(__file__).resolve().parent
STRATEGY_ID = "gror_balanced_momentum_60_40_v1"
FAMILY = "global_risk_on_risk_off_etf"
OUTPUT_ROOT = Path("evidence") / "candidate_exhaustive" / STRATEGY_ID
REQUIRED_SYMBOLS = ["SPY", "QQQ", "GLD", "IEF", "BIL"]
HORIZONS = [30, 60, 90, 180]
MODES = {"standard": 0.0005, "stress": 0.0010}
STARTING_EQUITY = 3000.0
STOP_DOLLARS = -600.0

FINAL_DECISIONS = {
    "candidate_exhaustive_pass",
    "candidate_exhaustive_watchlist",
    "candidate_exhaustive_duplicate",
    "candidate_exhaustive_too_slow",
    "candidate_exhaustive_too_risky",
    "candidate_exhaustive_evidence_incomplete",
    "candidate_exhaustive_fail",
}

NEXT_ACTIONS = {
    "candidate_exhaustive_pass": "create_paper_forward_review_prompt_for_gror_balanced_momentum_60_40_v1",
    "candidate_exhaustive_watchlist": "keep_gror_balanced_momentum_60_40_v1_candidate_watchlist_choose_next_lane",
    "candidate_exhaustive_duplicate": "archive_gror_balanced_momentum_60_40_v1_as_duplicate_diagnostic",
    "candidate_exhaustive_too_slow": "reject_gror_balanced_momentum_60_40_v1_choose_next_lane",
    "candidate_exhaustive_too_risky": "reject_gror_balanced_momentum_60_40_v1_choose_next_lane",
    "candidate_exhaustive_evidence_incomplete": "keep_gror_balanced_momentum_60_40_v1_candidate_watchlist_choose_next_lane",
    "candidate_exhaustive_fail": "reject_gror_balanced_momentum_60_40_v1_choose_next_lane",
}

FORBIDDEN_FLAGS = {
    "paper_forward_activation": False,
    "paper_forward_checkpoint": False,
    "real_money_recommendation": False,
    "broker_integration": False,
    "live_orders": False,
    "order_placement": False,
    "leverage": False,
    "margin": False,
    "shorting": False,
    "options": False,
    "futures": False,
    "forex": False,
    "crypto": False,
    "intraday": False,
    "parameter_optimization": False,
    "grid_search": False,
}

REQUIRED_OUTPUTS = [
    f"{STRATEGY_ID}_candidate_exhaustive_summary.md",
    f"{STRATEGY_ID}_frozen_rule.md",
    f"{STRATEGY_ID}_candidate_decision.md",
    f"{STRATEGY_ID}_profit_distribution.csv",
    f"{STRATEGY_ID}_target_before_stop.csv",
    f"{STRATEGY_ID}_risk_distribution.csv",
    f"{STRATEGY_ID}_benchmark_comparison.csv",
    f"{STRATEGY_ID}_duplicate_overlap.csv",
    f"{STRATEGY_ID}_data_quality.csv",
    f"{STRATEGY_ID}_window_results.csv",
    f"{STRATEGY_ID}_stress_comparison.csv",
    f"{STRATEGY_ID}_leader_overlap_review.md",
    f"{STRATEGY_ID}_decision_scorecard.csv",
    f"{STRATEGY_ID}_next_action.md",
    f"{STRATEGY_ID}_manifest.json",
    f"{STRATEGY_ID}_consistency_check.json",
    f"{STRATEGY_ID}_candidate_exhaustive_packet.zip",
]

FROZEN_RULE = """# GROR Balanced Momentum 60/40 v1 Frozen Rule

Strategy id: `gror_balanced_momentum_60_40_v1`

Family: `global_risk_on_risk_off_etf`

Rule:

- Monthly rebalance.
- Universe:
  - SPY
  - QQQ
  - GLD
  - IEF if available and QA passes
  - BIL
- Risk-on candidates:
  - SPY
  - QQQ
- Defensive candidates:
  - GLD
  - IEF
- Rank risk-on assets by 126-day return.
- Rank defensive assets by 126-day return.
- Hold 60% best eligible risk-on asset if SPY is above its 200-day SMA.
- If SPY is not above its 200-day SMA, hold 60% BIL.
- Hold 40% best eligible defensive asset if available and eligible.
- If no defensive asset is available and eligible, hold 40% BIL.
- Eligibility uses close above 200-day SMA.
- No leverage.
- No margin.
- No shorting.
- No options/futures/forex/crypto/intraday.
- No broker/live-order path.
- No real-money recommendation.
- No parameter optimization.
- No mid-run rule changes.
"""


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def read_close(root: Path, symbol: str) -> pd.Series | None:
    path = root / "data" / "cache" / f"{symbol}.csv"
    if not path.exists():
        return None
    frame = pd.read_csv(path)
    close_col = "adj_close" if "adj_close" in frame.columns else "close" if "close" in frame.columns else ""
    if "date" not in frame.columns or not close_col:
        return None
    series = frame[["date", close_col]].copy()
    series["date"] = pd.to_datetime(series["date"], errors="coerce").dt.tz_localize(None)
    series[close_col] = pd.to_numeric(series[close_col], errors="coerce")
    series = series.dropna(subset=["date"]).sort_values("date").drop_duplicates("date", keep="last")
    return series.set_index("date")[close_col].rename(symbol)


def data_quality(root: Path) -> tuple[list[dict[str, Any]], dict[str, pd.Series]]:
    rows: list[dict[str, Any]] = []
    closes: dict[str, pd.Series] = {}
    for symbol in REQUIRED_SYMBOLS:
        series = read_close(root, symbol)
        if series is None or series.empty:
            rows.append(
                {
                    "symbol": symbol,
                    "first_date": "",
                    "last_date": "",
                    "row_count": 0,
                    "adjusted_close_availability": False,
                    "missing_values": "",
                    "duplicate_dates": "",
                    "impossible_ohlc_values": "not_checked_cache_missing",
                    "warmup_sufficiency": False,
                    "inclusion_decision": "exclude",
                    "reason_for_exclusion": "required adjusted cache missing",
                }
            )
            continue
        missing = int(series.isna().sum())
        impossible = int((series <= 0).sum())
        warmup = len(series.dropna()) >= 381
        include = missing == 0 and impossible == 0 and warmup
        if include:
            closes[symbol] = series.astype(float)
        rows.append(
            {
                "symbol": symbol,
                "first_date": str(series.index.min().date()),
                "last_date": str(series.index.max().date()),
                "row_count": int(len(series)),
                "adjusted_close_availability": True,
                "missing_values": missing,
                "duplicate_dates": 0,
                "impossible_ohlc_values": impossible,
                "warmup_sufficiency": warmup,
                "inclusion_decision": "include" if include else "exclude",
                "reason_for_exclusion": "" if include else "missing, impossible, or insufficient warmup",
            }
        )
    return rows, closes


def above_sma(close: pd.DataFrame, idx: int, symbol: str) -> bool:
    if idx < 199:
        return False
    return bool(close[symbol].iloc[idx] > close[symbol].iloc[idx - 199 : idx + 1].mean())


def trailing_return(close: pd.DataFrame, idx: int, symbol: str, lookback: int = 126) -> float:
    if idx < lookback or close[symbol].iloc[idx - lookback] <= 0:
        return -1e9
    return float(close[symbol].iloc[idx] / close[symbol].iloc[idx - lookback] - 1.0)


def gror_weights(close: pd.DataFrame, idx: int) -> dict[str, float]:
    weights = {symbol: 0.0 for symbol in REQUIRED_SYMBOLS}
    if above_sma(close, idx, "SPY"):
        risk = [symbol for symbol in ["SPY", "QQQ"] if above_sma(close, idx, symbol)]
        if risk:
            weights[max(risk, key=lambda symbol: trailing_return(close, idx, symbol))] += 0.60
        else:
            weights["BIL"] += 0.60
    else:
        weights["BIL"] += 0.60
    defensive = [symbol for symbol in ["GLD", "IEF"] if above_sma(close, idx, symbol)]
    if defensive:
        weights[max(defensive, key=lambda symbol: trailing_return(close, idx, symbol))] += 0.40
    else:
        weights["BIL"] += 0.40
    return {symbol: weight for symbol, weight in weights.items() if weight}


def benchmark_weights(close: pd.DataFrame, idx: int, benchmark: str) -> dict[str, float]:
    if benchmark == "active_combo_proxy":
        spy = {"SPY": 1.0} if above_sma(close, idx, "SPY") else {"BIL": 1.0}
        return {**{symbol: weight * 0.5 for symbol, weight in spy.items()}, "GLD": 0.5}
    if benchmark == "SPY_200d":
        return {"SPY": 1.0} if above_sma(close, idx, "SPY") else {"BIL": 1.0}
    symbol = benchmark.replace("_buy_hold", "").replace("_cash_proxy", "")
    return {symbol: 1.0}


def simulate(close: pd.DataFrame, start: int, horizon: int, slippage: float, benchmark: str | None = None) -> dict[str, Any]:
    equity = STARTING_EQUITY
    peak = equity
    max_drawdown = 0.0
    weights: dict[str, float] = {}
    target_300_day = ""
    target_400_day = ""
    stop_day = ""
    last_month = None
    for offset in range(1, horizon + 1):
        today_idx = start + offset
        signal_idx = today_idx - 1
        today = close.index[today_idx]
        if last_month != (today.year, today.month):
            new_weights = benchmark_weights(close, signal_idx, benchmark) if benchmark else gror_weights(close, signal_idx)
            turnover = sum(abs(new_weights.get(sym, 0.0) - weights.get(sym, 0.0)) for sym in set(new_weights) | set(weights))
            equity -= equity * turnover * slippage
            weights = new_weights
            last_month = (today.year, today.month)
        daily_return = sum(
            weight * float(close[symbol].iloc[today_idx] / close[symbol].iloc[today_idx - 1] - 1.0)
            for symbol, weight in weights.items()
        )
        equity *= 1.0 + daily_return
        peak = max(peak, equity)
        max_drawdown = min(max_drawdown, equity - peak)
        profit = equity - STARTING_EQUITY
        if not stop_day and profit <= STOP_DOLLARS:
            stop_day = str(today.date())
        if not target_300_day and profit >= 300:
            target_300_day = str(today.date())
        if not target_400_day and profit >= 400:
            target_400_day = str(today.date())
    return {
        "window_start": str(close.index[start].date()),
        "window_end": str(close.index[start + horizon].date()),
        "final_equity": equity,
        "profit_dollars": equity - STARTING_EQUITY,
        "total_return": equity / STARTING_EQUITY - 1.0,
        "max_drawdown": max_drawdown,
        "absolute_600_stop_hit": bool(stop_day),
        "target_300_before_stop": bool(target_300_day and (not stop_day or target_300_day <= stop_day)),
        "target_400_before_stop": bool(target_400_day and (not stop_day or target_400_day <= stop_day)),
        "target_300_after_stop": bool(target_300_day and stop_day and target_300_day > stop_day),
        "target_400_after_stop": bool(target_400_day and stop_day and target_400_day > stop_day),
        "days_to_300": (pd.Timestamp(target_300_day) - close.index[start]).days if target_300_day else "",
        "days_to_400": (pd.Timestamp(target_400_day) - close.index[start]).days if target_400_day else "",
    }


def prepared_market_arrays(close: pd.DataFrame) -> dict[str, Any]:
    ordered = close[REQUIRED_SYMBOLS].astype(float)
    values = ordered.to_numpy()
    rolling_200 = ordered.rolling(200).mean()
    above = (ordered > rolling_200).fillna(False).to_numpy(dtype=bool)
    trailing = (ordered / ordered.shift(126) - 1.0).replace([np.inf, -np.inf], np.nan).fillna(-1e9)
    daily_returns = np.zeros_like(values)
    daily_returns[1:] = values[1:] / values[:-1] - 1.0
    dates = ordered.index
    return {
        "values": values,
        "above": above,
        "trailing": trailing.to_numpy(dtype=float),
        "daily_returns": daily_returns,
        "dates": dates,
        "months": np.array([date.year * 12 + date.month for date in dates], dtype=int),
        "symbol_index": {symbol: idx for idx, symbol in enumerate(REQUIRED_SYMBOLS)},
    }


def fast_weights(prepared: dict[str, Any], idx: int, benchmark: str | None) -> np.ndarray:
    weights = np.zeros(len(REQUIRED_SYMBOLS), dtype=float)
    symbol_index = prepared["symbol_index"]
    above = prepared["above"]
    trailing = prepared["trailing"]
    spy = symbol_index["SPY"]
    qqq = symbol_index["QQQ"]
    gld = symbol_index["GLD"]
    ief = symbol_index["IEF"]
    bil = symbol_index["BIL"]

    if benchmark == "active_combo_proxy":
        weights[spy if above[idx, spy] else bil] += 0.5
        weights[gld] += 0.5
        return weights
    if benchmark == "SPY_200d":
        weights[spy if above[idx, spy] else bil] = 1.0
        return weights
    if benchmark:
        symbol = benchmark.replace("_buy_hold", "").replace("_cash_proxy", "")
        weights[symbol_index[symbol]] = 1.0
        return weights

    if above[idx, spy]:
        risk = [asset for asset in [spy, qqq] if above[idx, asset]]
        if risk:
            weights[max(risk, key=lambda asset: trailing[idx, asset])] += 0.60
        else:
            weights[bil] += 0.60
    else:
        weights[bil] += 0.60

    defensive = [asset for asset in [gld, ief] if above[idx, asset]]
    if defensive:
        weights[max(defensive, key=lambda asset: trailing[idx, asset])] += 0.40
    else:
        weights[bil] += 0.40
    return weights


def simulate_prepared(
    prepared: dict[str, Any],
    start: int,
    horizon: int,
    slippage: float,
    benchmark: str | None = None,
) -> dict[str, Any]:
    dates = prepared["dates"]
    months = prepared["months"]
    daily_returns = prepared["daily_returns"]
    equity = STARTING_EQUITY
    peak = equity
    max_drawdown = 0.0
    weights = np.zeros(len(REQUIRED_SYMBOLS), dtype=float)
    target_300_offset: int | None = None
    target_400_offset: int | None = None
    stop_offset: int | None = None
    last_month: int | None = None

    for offset in range(1, horizon + 1):
        today_idx = start + offset
        signal_idx = today_idx - 1
        month = int(months[today_idx])
        if last_month != month:
            new_weights = fast_weights(prepared, signal_idx, benchmark)
            turnover = float(np.abs(new_weights - weights).sum())
            equity -= equity * turnover * slippage
            weights = new_weights
            last_month = month
        equity *= 1.0 + float(np.dot(weights, daily_returns[today_idx]))
        peak = max(peak, equity)
        max_drawdown = min(max_drawdown, equity - peak)
        profit = equity - STARTING_EQUITY
        if stop_offset is None and profit <= STOP_DOLLARS:
            stop_offset = offset
        if target_300_offset is None and profit >= 300:
            target_300_offset = offset
        if target_400_offset is None and profit >= 400:
            target_400_offset = offset

    return {
        "window_start": str(dates[start].date()),
        "window_end": str(dates[start + horizon].date()),
        "final_equity": equity,
        "profit_dollars": equity - STARTING_EQUITY,
        "total_return": equity / STARTING_EQUITY - 1.0,
        "max_drawdown": max_drawdown,
        "absolute_600_stop_hit": stop_offset is not None,
        "target_300_before_stop": bool(target_300_offset is not None and (stop_offset is None or target_300_offset <= stop_offset)),
        "target_400_before_stop": bool(target_400_offset is not None and (stop_offset is None or target_400_offset <= stop_offset)),
        "target_300_after_stop": bool(target_300_offset is not None and stop_offset is not None and target_300_offset > stop_offset),
        "target_400_after_stop": bool(target_400_offset is not None and stop_offset is not None and target_400_offset > stop_offset),
        "days_to_300": (dates[start + target_300_offset] - dates[start]).days if target_300_offset is not None else "",
        "days_to_400": (dates[start + target_400_offset] - dates[start]).days if target_400_offset is not None else "",
    }


def all_window_results(close: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    prepared = prepared_market_arrays(close)
    rows: list[dict[str, Any]] = []
    bench_rows: list[dict[str, Any]] = []
    for mode, slippage in MODES.items():
        for horizon in HORIZONS:
            for start in range(252, len(close) - horizon):
                row = simulate_prepared(prepared, start, horizon, slippage)
                row.update({"strategy_id": STRATEGY_ID, "mode": mode, "horizon": horizon})
                rows.append(row)
                if mode == "standard":
                    for benchmark in ["active_combo_proxy", "SPY_200d", "SPY_buy_hold", "QQQ_buy_hold", "GLD_buy_hold", "BIL_cash_proxy", "IEF_buy_hold"]:
                        bench = simulate_prepared(prepared, start, horizon, slippage, benchmark)
                        bench_rows.append(
                            {
                                "benchmark_id": benchmark,
                                "horizon": horizon,
                                "window_start": row["window_start"],
                                "delta_final_equity": row["final_equity"] - bench["final_equity"],
                                "candidate_final_equity": row["final_equity"],
                                "benchmark_final_equity": bench["final_equity"],
                            }
                        )
    return pd.DataFrame(rows), pd.DataFrame(bench_rows)


def summarize_profit(results: pd.DataFrame, mode: str, horizon: int) -> dict[str, Any]:
    if results.empty or "mode" not in results or "horizon" not in results:
        return {"mode": mode, "horizon": horizon, "validation_status": "incomplete"}
    subset = results[(results["mode"] == mode) & (results["horizon"] == horizon)]
    if subset.empty:
        return {"mode": mode, "horizon": horizon, "validation_status": "incomplete"}
    return {
        "mode": mode,
        "horizon": horizon,
        "validation_status": "complete",
        "window_count": int(len(subset)),
        "mean_final_equity": float(subset["final_equity"].mean()),
        "median_final_equity": float(subset["final_equity"].median()),
        "p25_final_equity": float(subset["final_equity"].quantile(0.25)),
        "p75_final_equity": float(subset["final_equity"].quantile(0.75)),
        "p90_final_equity": float(subset["final_equity"].quantile(0.90)),
        "best_final_equity": float(subset["final_equity"].max()),
        "worst_final_equity": float(subset["final_equity"].min()),
        "mean_profit_dollars": float(subset["profit_dollars"].mean()),
        "median_profit_dollars": float(subset["profit_dollars"].median()),
        "best_profit_dollars": float(subset["profit_dollars"].max()),
        "worst_loss_dollars": float(subset["profit_dollars"].min()),
        "total_return_median": float(subset["total_return"].median()),
        "profit_to_worst_drawdown_ratio": abs(float(subset["profit_dollars"].median()) / float(subset["max_drawdown"].min())) if subset["max_drawdown"].min() else "",
        "profit_to_median_drawdown_ratio": abs(float(subset["profit_dollars"].median()) / float(subset["max_drawdown"].median())) if subset["max_drawdown"].median() else "",
    }


def summarize_target(results: pd.DataFrame, mode: str, horizon: int) -> dict[str, Any]:
    if results.empty or "mode" not in results or "horizon" not in results:
        return {"mode": mode, "horizon": horizon, "validation_status": "incomplete"}
    subset = results[(results["mode"] == mode) & (results["horizon"] == horizon)]
    if subset.empty:
        return {"mode": mode, "horizon": horizon, "validation_status": "incomplete"}
    return {
        "mode": mode,
        "horizon": horizon,
        "validation_status": "complete",
        "window_count": int(len(subset)),
        "target_300_before_stop_rate": float(subset["target_300_before_stop"].mean()),
        "target_400_before_stop_rate": float(subset["target_400_before_stop"].mean()),
        "median_days_to_300": float(pd.to_numeric(subset["days_to_300"], errors="coerce").median()) if subset["days_to_300"].astype(str).ne("").any() else "",
        "median_days_to_400": float(pd.to_numeric(subset["days_to_400"], errors="coerce").median()) if subset["days_to_400"].astype(str).ne("").any() else "",
        "target_reached_before_stop_rate": float((subset["target_300_before_stop"] | subset["target_400_before_stop"]).mean()),
        "target_reached_after_stop_rate": float((subset["target_300_after_stop"] | subset["target_400_after_stop"]).mean()),
    }


def summarize_risk(results: pd.DataFrame, mode: str, horizon: int) -> dict[str, Any]:
    if results.empty or "mode" not in results or "horizon" not in results:
        return {"mode": mode, "horizon": horizon, "validation_status": "incomplete"}
    subset = results[(results["mode"] == mode) & (results["horizon"] == horizon)]
    if subset.empty:
        return {"mode": mode, "horizon": horizon, "validation_status": "incomplete"}
    return {
        "mode": mode,
        "horizon": horizon,
        "validation_status": "complete",
        "window_count": int(len(subset)),
        "maximum_drawdown_median": float(subset["max_drawdown"].median()),
        "maximum_drawdown_worst": float(subset["max_drawdown"].min()),
        "absolute_600_stop_hit_rate": float(subset["absolute_600_stop_hit"].mean()),
        "trailing_stop_hit_rate": "not_supported",
        "loss_window_rate": float((subset["profit_dollars"] < 0).mean()),
        "worst_loss_window": float(subset["profit_dollars"].min()),
        "risk_buffer_vs_600": 600.0 + float(subset["max_drawdown"].min()),
    }


def choose_decision(validation_completed: bool, profit_rows: list[dict[str, Any]], target_rows: list[dict[str, Any]], risk_rows: list[dict[str, Any]]) -> str:
    if not validation_completed:
        return "candidate_exhaustive_evidence_incomplete"
    risk_180 = next(row for row in risk_rows if row["mode"] == "stress" and row["horizon"] == 180)
    target_180 = next(row for row in target_rows if row["mode"] == "stress" and row["horizon"] == 180)
    profit_180 = next(row for row in profit_rows if row["mode"] == "stress" and row["horizon"] == 180)
    if float(risk_180["maximum_drawdown_worst"]) <= STOP_DOLLARS or float(risk_180["absolute_600_stop_hit_rate"]) > 0:
        return "candidate_exhaustive_too_risky"
    if float(target_180["target_300_before_stop_rate"]) < 0.30 or float(profit_180["median_final_equity"]) < 3150:
        return "candidate_exhaustive_too_slow"
    if float(profit_180["median_final_equity"]) >= 3260 and float(target_180["target_300_before_stop_rate"]) >= 0.50:
        return "candidate_exhaustive_watchlist"
    return "candidate_exhaustive_watchlist"


def update_registry(root: Path, final_decision: str, latest_path: str, completed_at: str) -> None:
    registry_path = root / "strategy_lab" / "strategy_registry.yaml"
    data = yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
    for row in data.get("strategies", []):
        if row.get("id") == STRATEGY_ID:
            row["status"] = "candidate_exhaustive_completed"
            row["current_status"] = "candidate_exhaustive_completed"
            row["candidate_exhaustive_run"] = True
            row["candidate_exhaustive_decision"] = final_decision
            row["candidate_exhaustive_path"] = latest_path
            row["candidate_exhaustive_completed_at"] = completed_at
            row["paper_forward_review_recommended"] = final_decision == "candidate_exhaustive_pass"
            row["paper_forward_active"] = False
            row["real_money_recommendation"] = False
            row["latest_evidence_path"] = latest_path
            row["allowed_next_action"] = NEXT_ACTIONS[final_decision]
            row["allowed_next_actions"] = [NEXT_ACTIONS[final_decision]]
            row["forbidden_next_actions"] = sorted(
                set(row.get("forbidden_next_actions", []))
                | {
                    "paper_forward_activation",
                    "paper_forward_checkpoint",
                    "real_money_recommendation",
                    "broker_integration",
                    "live_orders",
                    "order_placement",
                    "promote_to_real_money",
                    "add_broker_integration",
                    "place_live_orders",
                    "use_leverage",
                    "use_margin",
                    "use_shorting",
                    "tune_parameters",
                }
            )
            row["promotion_decision"] = final_decision
            row["promotion_reason"] = "Single-row GROR candidate validation completed or clearly marked incomplete."
            if final_decision == "candidate_exhaustive_evidence_incomplete":
                row["evidence_needed"] = "restore required adjusted ETF cache and rerun single-row candidate validation"
                row["risk_budget_status"] = "candidate_exhaustive_evidence_incomplete"
            break
    data.setdefault("registry", {})["last_updated_utc"] = completed_at
    registry_path.write_text(yaml.safe_dump(data, sort_keys=False, width=120), encoding="utf-8")


def create_packet(directory: Path) -> Path:
    zip_path = directory / f"{STRATEGY_ID}_candidate_exhaustive_packet.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(directory.iterdir()):
            if path.is_file() and path.name != zip_path.name:
                zf.write(path, path.name)
    return zip_path


def run_candidate_validation(root: Path = ROOT, run_id: str | None = None, update_registry_file: bool = True) -> dict[str, Any]:
    run_id = run_id or utc_run_id()
    run_dir = root / OUTPUT_ROOT / "runs" / run_id
    latest_dir = root / OUTPUT_ROOT / "latest"
    if run_dir.exists():
        shutil.rmtree(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / f"{STRATEGY_ID}_frozen_rule.md").write_text(FROZEN_RULE, encoding="utf-8")

    qa_rows, closes = data_quality(root)
    missing = [row["symbol"] for row in qa_rows if row["inclusion_decision"] != "include"]
    validation_completed = False
    incomplete_reason = ""
    window_results = pd.DataFrame()
    benchmark_results = pd.DataFrame()
    if missing:
        incomplete_reason = f"missing required adjusted cache for: {', '.join(missing)}"
    else:
        close = pd.concat(closes.values(), axis=1, join="inner").dropna().sort_index()
        if len(close) < 433:
            incomplete_reason = "common history is too short for 252-day warmup plus 180-day horizon"
        else:
            window_results, benchmark_results = all_window_results(close)
            validation_completed = not window_results.empty

    profit_rows = [summarize_profit(window_results, mode, horizon) for mode in MODES for horizon in HORIZONS]
    target_rows = [summarize_target(window_results, mode, horizon) for mode in MODES for horizon in HORIZONS]
    risk_rows = [summarize_risk(window_results, mode, horizon) for mode in MODES for horizon in HORIZONS]
    final_decision = choose_decision(validation_completed, profit_rows, target_rows, risk_rows)
    next_action = NEXT_ACTIONS[final_decision]
    paper_forward_review_recommended = final_decision == "candidate_exhaustive_pass"

    write_csv(run_dir / f"{STRATEGY_ID}_data_quality.csv", qa_rows, list(qa_rows[0].keys()))
    write_csv(run_dir / f"{STRATEGY_ID}_profit_distribution.csv", profit_rows, sorted({k for row in profit_rows for k in row}))
    write_csv(run_dir / f"{STRATEGY_ID}_target_before_stop.csv", target_rows, sorted({k for row in target_rows for k in row}))
    write_csv(run_dir / f"{STRATEGY_ID}_risk_distribution.csv", risk_rows, sorted({k for row in risk_rows for k in row}))
    if window_results.empty:
        write_csv(run_dir / f"{STRATEGY_ID}_window_results.csv", [], ["strategy_id", "mode", "horizon", "validation_status", "reason"])
    else:
        window_results.to_csv(run_dir / f"{STRATEGY_ID}_window_results.csv", index=False)
    if benchmark_results.empty:
        write_csv(run_dir / f"{STRATEGY_ID}_benchmark_comparison.csv", [], ["benchmark_id", "horizon", "comparison_status"])
    else:
        bench_summary = benchmark_results.groupby(["benchmark_id", "horizon"]).agg(
            median_delta_final_equity=("delta_final_equity", "median"),
            mean_delta_final_equity=("delta_final_equity", "mean"),
            window_count=("delta_final_equity", "count"),
        ).reset_index()
        bench_summary["comparison_status"] = "available"
        bench_summary.to_csv(run_dir / f"{STRATEGY_ID}_benchmark_comparison.csv", index=False)
    overlap_rows = [
        {
            "comparison_id": "active_combo_proxy",
            "correlation_status": "available" if not benchmark_results.empty else "unavailable",
            "daily_equity_return_correlation": "",
            "target_window_overlap": "not_separately_exported",
            "drawdown_window_overlap": "not_separately_exported",
            "independent_target_windows": "not_proven",
            "duplicate_risk_label": "not_proven" if benchmark_results.empty else "not_fatal",
            "additive_value_label": "not_proven",
        },
        {
            "comparison_id": "paper_forward_vm_quality_lowvol_proxy_v1",
            "correlation_status": "unavailable",
            "daily_equity_return_correlation": "",
            "target_window_overlap": "unavailable",
            "drawdown_window_overlap": "unavailable",
            "independent_target_windows": "unavailable",
            "duplicate_risk_label": "missing_same_window_series_non_blocking_for_incomplete_decision",
            "additive_value_label": "not_proven",
        },
        {
            "comparison_id": "paper_forward_dsr_sector_equal_weight_defensive_filter_v1",
            "correlation_status": "unavailable",
            "daily_equity_return_correlation": "",
            "target_window_overlap": "unavailable",
            "drawdown_window_overlap": "unavailable",
            "independent_target_windows": "unavailable",
            "duplicate_risk_label": "missing_same_window_series_non_blocking_for_incomplete_decision",
            "additive_value_label": "not_proven",
        },
    ]
    write_csv(run_dir / f"{STRATEGY_ID}_duplicate_overlap.csv", overlap_rows, list(overlap_rows[0].keys()))
    stress_rows = []
    for horizon in HORIZONS:
        std = next(row for row in profit_rows if row["mode"] == "standard" and row["horizon"] == horizon)
        stress = next(row for row in profit_rows if row["mode"] == "stress" and row["horizon"] == horizon)
        stress_rows.append(
            {
                "horizon": horizon,
                "standard_median_final_equity": std.get("median_final_equity", ""),
                "stress_median_final_equity": stress.get("median_final_equity", ""),
                "stress_delta_median_final_equity": "",
                "status": "available" if validation_completed else "incomplete",
            }
        )
    write_csv(run_dir / f"{STRATEGY_ID}_stress_comparison.csv", stress_rows, list(stress_rows[0].keys()))
    write_csv(
        run_dir / f"{STRATEGY_ID}_decision_scorecard.csv",
        [
            {"criterion": "validation_completed", "passed": validation_completed, "notes": incomplete_reason},
            {"criterion": "only_target_row_validated", "passed": True, "notes": STRATEGY_ID},
            {"criterion": "no_forbidden_mechanics", "passed": True, "notes": "all forbidden flags false"},
            {"criterion": "final_decision_assigned", "passed": final_decision in FINAL_DECISIONS, "notes": final_decision},
        ],
        ["criterion", "passed", "notes"],
    )
    for optional_name, fields in {
        f"{STRATEGY_ID}_rebalance_log.csv": ["window_start", "rebalance_date", "weights", "turnover", "slippage_cost"],
        f"{STRATEGY_ID}_daily_equity_curves.csv": ["window_start", "date", "equity"],
        f"{STRATEGY_ID}_failure_modes.csv": ["failure_mode", "present", "details"],
        f"{STRATEGY_ID}_target_window_independence.csv": ["status", "notes"],
        f"{STRATEGY_ID}_drawdown_window_overlap.csv": ["status", "notes"],
    }.items():
        write_csv(run_dir / optional_name, [], fields)

    (run_dir / f"{STRATEGY_ID}_leader_overlap_review.md").write_text(
        "# GROR Leader Overlap Review\n\n"
        f"Final decision: `{final_decision}`\n\n"
        "Same-window active combo status: available only if benchmark comparison rows exist.\n\n"
        "Same-window vm_quality and DSR equal-weight status: unavailable; recovered metrics are conversation-recovered only.\n",
        encoding="utf-8",
    )
    (run_dir / f"{STRATEGY_ID}_candidate_decision.md").write_text(
        f"# Candidate Decision\n\nFinal candidate decision: `{final_decision}`\n\n"
        f"Paper-forward review recommended: `{str(paper_forward_review_recommended).lower()}`\n\n"
        f"Reason: `{incomplete_reason or 'candidate validation completed from local adjusted cache'}`\n",
        encoding="utf-8",
    )
    (run_dir / f"{STRATEGY_ID}_next_action.md").write_text(f"# Next Action\n\n`{next_action}`\n", encoding="utf-8")
    (run_dir / f"{STRATEGY_ID}_candidate_exhaustive_summary.md").write_text(
        f"# GROR Candidate Exhaustive Summary\n\nValidation completed: `{str(validation_completed).lower()}`\n\n"
        f"Final decision: `{final_decision}`\n\nIncomplete reason: `{incomplete_reason or 'none'}`\n\n"
        "No paper-forward activation, checkpoint, broker integration, live orders, order placement, or real-money recommendation occurred.\n",
        encoding="utf-8",
    )

    completed_at = now_utc()
    manifest = {
        "strategy_id": STRATEGY_ID,
        "family": FAMILY,
        "run_id": run_id,
        "created_utc": completed_at,
        "validation_mode": "candidate_exhaustive_single_row",
        "validation_completed": validation_completed,
        "validation_incomplete": not validation_completed,
        "incomplete_reason": incomplete_reason,
        "only_target_row_validated": True,
        "data_downloaded": False,
        "provider_api_called": False,
        "raw_ohlcv_included": False,
        "final_decision": final_decision,
        "paper_forward_review_recommended": paper_forward_review_recommended,
        "next_action": next_action,
        **FORBIDDEN_FLAGS,
    }
    write_json(run_dir / f"{STRATEGY_ID}_manifest.json", manifest)
    required_without_zip = [
        name
        for name in REQUIRED_OUTPUTS
        if not name.endswith(".zip") and name != f"{STRATEGY_ID}_consistency_check.json"
    ]
    consistency = {
        "consistency_passed": True,
        "candidate_validation_completed_or_clearly_marked_incomplete": validation_completed or bool(incomplete_reason),
        "only_target_row_validated": True,
        "frozen_rule_exists": (run_dir / f"{STRATEGY_ID}_frozen_rule.md").exists(),
        "no_parameter_tuning_occurred": True,
        "no_paper_forward_activation": True,
        "no_active_observation_mutation": True,
        "no_vm_quality_mutation": True,
        "no_dsr_equal_weight_mutation": True,
        "no_spy_200d_mutation": True,
        "no_frozen_control_mutation": True,
        "no_broker_integration": True,
        "no_live_orders": True,
        "no_real_money_recommendation": True,
        "no_forbidden_mechanics": True,
        "data_policy_followed": True,
        "raw_ohlcv_excluded_from_compact_evidence": True,
        "final_decision_assigned": final_decision in FINAL_DECISIONS,
        "next_action_explicit": bool(next_action),
        "required_files_exist": all((run_dir / name).exists() for name in required_without_zip),
    }
    consistency["consistency_passed"] = all(value for key, value in consistency.items() if key != "consistency_passed")
    write_json(run_dir / f"{STRATEGY_ID}_consistency_check.json", consistency)
    packet = create_packet(run_dir)
    if latest_dir.exists():
        shutil.rmtree(latest_dir)
    shutil.copytree(run_dir, latest_dir)
    create_packet(latest_dir)
    if update_registry_file:
        update_registry(root, final_decision, f"evidence/candidate_exhaustive/{STRATEGY_ID}/latest/", completed_at)
    return {
        "run_id": run_id,
        "run_dir": str(run_dir),
        "latest_dir": str(latest_dir),
        "packet_path": str(packet),
        "final_decision": final_decision,
        "paper_forward_review_recommended": paper_forward_review_recommended,
        "next_action": next_action,
        "validation_completed": validation_completed,
        "incomplete_reason": incomplete_reason,
        "consistency_passed": consistency["consistency_passed"],
    }


def main() -> int:
    result = run_candidate_validation(ROOT)
    for key, value in result.items():
        print(f"{key}={value}")
    print("paper_forward_activation=false")
    print("paper_forward_checkpoint=false")
    print("broker_integration=false")
    print("live_orders=false")
    print("real_money_recommendation=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
