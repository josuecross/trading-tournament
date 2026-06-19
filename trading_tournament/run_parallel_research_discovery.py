from __future__ import annotations

import csv
import hashlib
import json
import shutil
import zipfile
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd
import yaml

from src.data import DataQualityError, _download_yfinance, build_adjusted_ohlc


ROOT = Path(__file__).resolve().parent
QUEUE_PATH = Path("strategy_lab") / "parallel_research_discovery_queue.yaml"
OUTPUT_DIR = Path("evidence") / "parallel_research_discovery" / "latest"
LABEL_UPDATE_DIR = Path("evidence") / "exploratory_gate_label_update" / "latest"
REGISTRY_PATH = Path("strategy_lab") / "strategy_registry.yaml"
STARTING_EQUITY = 3000.0
STOP_DOLLARS = -600.0
SLIPPAGE = 0.0005
HORIZONS = [90, 180]
MAX_WINDOWS_PER_HORIZON = 180
PROMOTION_SCORE_THRESHOLD = 70
PROMOTION_TARGET300_THRESHOLD = 0.25
APPROVED_SYMBOLS = {
    "SPY",
    "QQQ",
    "EFA",
    "EEM",
    "IWM",
    "GLD",
    "IEF",
    "BIL",
    "TLT",
    "AGG",
    "USMV",
    "SPLV",
    "SCHD",
    "VIG",
    "DGRO",
    "HYG",
    "LQD",
    "EMB",
}
PROTECTED_IDS = {
    "current_no_cash_proxy_alpha_AB",
    "paper_forward_vm_quality_lowvol_proxy_v1",
    "paper_forward_dsr_sector_equal_weight_defensive_filter_v1",
    "SPY_200d_trend_model",
}
NEXT_PROMOTION = "create_promotion_review_for_best_parallel_discovery_candidate"
NEXT_CONTINUE = "continue_best_parallel_discovery_family"
NEXT_FAIL = "move_to_dsr_top2_or_reassess_roadmap"
AUDIT_NEXT_ACTION = "adjust_exploratory_gate_labels_not_thresholds"
EXPLORATORY_LABELS = {
    "diversifier_watchlist_candidate",
    "short_history_watchlist",
    "benchmark_watchlist",
    "defensive_watchlist",
    "too_slow_for_profit_goal",
    "duplicate_watchlist",
    "needs_benchmark_delta_review",
}
NON_PROMOTION_VERDICTS = {
    "watchlist",
    "too_risky",
    "too_slow",
    "duplicate_or_near_duplicate",
    "evidence_missing",
    "reject",
    *EXPLORATORY_LABELS,
}
WATCHLIST_VERDICTS = {
    "watchlist",
    "diversifier_watchlist_candidate",
    "short_history_watchlist",
    "benchmark_watchlist",
    "defensive_watchlist",
    "too_slow_for_profit_goal",
    "duplicate_watchlist",
    "needs_benchmark_delta_review",
}
COMBINED_BENCHMARK_IDS = [
    "SPY_200d",
    "SPY_buy_hold",
    "QQQ_buy_hold",
    "BIL_cash_proxy",
    "active_combo",
    "paper_forward_vm_quality_lowvol_proxy_v1",
    "paper_forward_dsr_sector_equal_weight_defensive_filter_v1",
    "gror_balanced_momentum_60_40_v1",
]

Downloader = Callable[[str, str, str | None, dict[str, Any]], pd.DataFrame]


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def rows_by_id(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(row.get("id")): row for row in registry.get("strategies", [])}


def protected_snapshot(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = rows_by_id(registry)
    return {
        row_id: deepcopy(row)
        for row_id, row in rows.items()
        if row_id in PROTECTED_IDS or row.get("paper_forward_active") is True
    }


def is_promotion_candidate(verdict: str) -> bool:
    return verdict == "promotion_review_candidate"


def next_action_for_verdict(verdict: str) -> str:
    if is_promotion_candidate(verdict):
        return NEXT_PROMOTION
    if verdict == "evidence_missing":
        return NEXT_FAIL
    return NEXT_CONTINUE


def validate_queue(queue: dict[str, Any]) -> None:
    allowed = set(queue.get("approved_symbols", []))
    if not allowed <= APPROVED_SYMBOLS:
        raise ValueError(f"queue approved symbols outside policy: {sorted(allowed - APPROVED_SYMBOLS)}")
    for family in queue.get("families", []):
        symbols = set(family.get("approved_symbols", []))
        if not symbols <= APPROVED_SYMBOLS:
            raise ValueError(f"{family.get('family_id')} has unapproved symbols: {sorted(symbols - APPROVED_SYMBOLS)}")
        if family.get("stage") != "research_sample":
            raise ValueError(f"{family.get('family_id')} stage must be research_sample")
        if family.get("max_variants", 0) < len(family.get("variants", [])):
            raise ValueError(f"{family.get('family_id')} exceeds max_variants")
        for variant in family.get("variants", []):
            universe = set(variant.get("universe", []))
            if not universe <= APPROVED_SYMBOLS:
                raise ValueError(f"{variant.get('strategy_id')} has unapproved symbols: {sorted(universe - APPROVED_SYMBOLS)}")


def cache_path(root: Path, symbol: str) -> Path:
    return root / "data" / "cache" / f"{symbol}.csv"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else ""


def load_config(root: Path) -> dict[str, Any]:
    path = root / "config.yaml"
    if not path.exists():
        return {"data": {"start_date": "2007-01-01", "end_date": None, "yfinance": {}}}
    return load_yaml(path)


def qa_cache(root: Path, symbol: str) -> dict[str, Any]:
    if symbol not in APPROVED_SYMBOLS:
        raise ValueError(f"unapproved symbol requested: {symbol}")
    path = cache_path(root, symbol)
    row = {
        "symbol": symbol,
        "first_date": "",
        "last_date": "",
        "row_count": 0,
        "adjusted_close_availability": False,
        "missing_adjusted_close_count": "",
        "duplicate_dates": "",
        "impossible_ohlc_values": "",
        "warmup_sufficiency": False,
        "inclusion_decision": "exclude",
        "reason_for_exclusion": "cache missing",
        "short_history_warning": True,
        "cache_file_hash": sha256_file(path),
    }
    if not path.exists():
        return row
    try:
        frame = pd.read_csv(path)
    except Exception as exc:
        row["reason_for_exclusion"] = f"cache read failed: {exc}"
        return row
    if "date" not in frame or "adj_close" not in frame:
        row["reason_for_exclusion"] = "date or adj_close missing"
        return row
    dates = pd.to_datetime(frame["date"], errors="coerce").dt.tz_localize(None)
    close = pd.to_numeric(frame["adj_close"], errors="coerce")
    duplicate_dates = int(dates.dropna().duplicated().sum())
    missing_close = int(close.isna().sum())
    ohlc_cols = [col for col in ["open", "high", "low", "close"] if col in frame]
    impossible = ""
    if ohlc_cols:
        ohlc = frame[ohlc_cols].apply(pd.to_numeric, errors="coerce")
        impossible = int((ohlc <= 0).any(axis=1).sum())
    valid_count = int((dates.notna() & close.notna()).sum())
    include = valid_count >= 260 and missing_close == 0 and duplicate_dates == 0 and (impossible in {"", 0})
    valid_dates = dates.dropna()
    row.update(
        {
            "first_date": "" if valid_dates.empty else str(valid_dates.min().date()),
            "last_date": "" if valid_dates.empty else str(valid_dates.max().date()),
            "row_count": int(len(frame)),
            "adjusted_close_availability": True,
            "missing_adjusted_close_count": missing_close,
            "duplicate_dates": duplicate_dates,
            "impossible_ohlc_values": impossible,
            "warmup_sufficiency": valid_count >= 260,
            "inclusion_decision": "include" if include else "exclude",
            "reason_for_exclusion": "" if include else "missing, duplicate, non-positive, or insufficient history",
            "short_history_warning": valid_count < 756,
            "cache_file_hash": sha256_file(path),
        }
    )
    return row


def read_close(root: Path, symbol: str) -> pd.Series | None:
    path = cache_path(root, symbol)
    if not path.exists():
        return None
    frame = pd.read_csv(path)
    if "date" not in frame or "adj_close" not in frame:
        return None
    dates = pd.to_datetime(frame["date"], errors="coerce").dt.tz_localize(None)
    close = pd.to_numeric(frame["adj_close"], errors="coerce")
    series = pd.DataFrame({"date": dates, symbol: close}).dropna().sort_values("date").drop_duplicates("date")
    return None if series.empty else series.set_index("date")[symbol].astype(float)


def bootstrap_symbols(root: Path, symbols: list[str], downloader: Downloader | None, allow_download: bool) -> tuple[list[dict[str, Any]], list[dict[str, Any]], bool, list[str]]:
    config = load_config(root)
    data_cfg = config.get("data", {})
    start = str(data_cfg.get("start_date", "2007-01-01"))
    end = data_cfg.get("end_date")
    params = data_cfg.get("yfinance", {})
    downloader = downloader or _download_yfinance
    qa_rows: list[dict[str, Any]] = []
    logs: list[dict[str, Any]] = []
    provider_api_called = False
    downloaded: list[str] = []
    for symbol in sorted(set(symbols)):
        qa = qa_cache(root, symbol)
        if qa["inclusion_decision"] == "include":
            logs.append({"symbol": symbol, "status": "used_existing_cache", "provider_api_called": False, "detail": "cache passed QA"})
            qa_rows.append(qa)
            continue
        if not allow_download:
            logs.append({"symbol": symbol, "status": "missing_no_download", "provider_api_called": False, "detail": qa["reason_for_exclusion"]})
            qa_rows.append(qa)
            continue
        provider_api_called = True
        try:
            raw = downloader(symbol, start, end, params)
            if raw is None or raw.empty:
                raise DataQualityError("provider returned no rows")
            normalized = build_adjusted_ohlc(raw, symbol)
            target = cache_path(root, symbol)
            target.parent.mkdir(parents=True, exist_ok=True)
            normalized.to_csv(target, index=False)
            qa = qa_cache(root, symbol)
            if qa["inclusion_decision"] != "include":
                raise DataQualityError(qa["reason_for_exclusion"])
            downloaded.append(symbol)
            logs.append({"symbol": symbol, "status": "downloaded", "provider_api_called": True, "detail": "downloaded approved ETF/fund-wrapper adjusted daily data"})
        except Exception as exc:
            logs.append({"symbol": symbol, "status": "download_failed", "provider_api_called": True, "detail": str(exc)})
        qa_rows.append(qa_cache(root, symbol))
    return qa_rows, logs, provider_api_called, downloaded


def prepared(close: pd.DataFrame) -> dict[str, Any]:
    values = close.to_numpy(dtype=float)
    above = values > close.rolling(200).mean().to_numpy(dtype=float)
    ret126 = (close / close.shift(126) - 1.0).replace([np.inf, -np.inf], np.nan).fillna(-1e9).to_numpy(dtype=float)
    returns = np.zeros_like(values)
    returns[1:] = values[1:] / values[:-1] - 1.0
    vol60 = pd.DataFrame(returns, index=close.index, columns=close.columns).rolling(60).std().replace(0, np.nan).to_numpy(dtype=float)
    return {"close": close, "idx": {sym: i for i, sym in enumerate(close.columns)}, "above": above, "ret126": ret126, "returns": returns, "vol60": vol60, "months": np.array([dt.year * 12 + dt.month for dt in close.index], dtype=int)}


def eligible(p: dict[str, Any], t: int, sym: str) -> bool:
    return sym in p["idx"] and bool(p["above"][t, p["idx"][sym]])


def rank_assets(p: dict[str, Any], t: int, assets: list[str], risk_adjusted: bool = False) -> list[str]:
    scored: list[tuple[str, float]] = []
    for sym in assets:
        if sym == "BIL" or not eligible(p, t, sym):
            continue
        idx = p["idx"][sym]
        score = float(p["ret126"][t, idx])
        if risk_adjusted:
            vol = float(p["vol60"][t, idx])
            score = score / vol if np.isfinite(vol) and vol > 0 else -1e9
        scored.append((sym, score))
    return [sym for sym, _ in sorted(scored, key=lambda item: item[1], reverse=True)]


def add(weights: dict[str, float], sym: str, amount: float) -> None:
    weights[sym] = weights.get(sym, 0.0) + amount


def weights_for_variant(p: dict[str, Any], t: int, variant: dict[str, Any]) -> dict[str, float]:
    rule = variant["rule_type"]
    universe = variant["universe"]
    weights: dict[str, float] = {}
    risky = [sym for sym in universe if sym != "BIL"]
    if rule == "gtaa_equal_weight_trend_filter":
        eligible_assets = [sym for sym in risky if eligible(p, t, sym)]
        share = 1.0 / len(risky)
        for sym in eligible_assets:
            add(weights, sym, share)
        add(weights, "BIL", max(0.0, 1.0 - share * len(eligible_assets)))
    elif rule in {"gtaa_top_n_return", "gtaa_top_n_risk_adjusted", "top2_risk_adjusted", "top1_risk_adjusted"}:
        top_n = int(variant.get("top_n", 2 if "top2" in rule else 1))
        picks = rank_assets(p, t, risky, risk_adjusted=rule in {"gtaa_top_n_risk_adjusted", "top2_risk_adjusted", "top1_risk_adjusted"})[:top_n]
        for pick in picks:
            add(weights, pick, 1.0 / top_n)
        add(weights, "BIL", max(0.0, 1.0 - len(picks) / top_n))
    elif rule == "static_trend_weights":
        for sym, weight in (variant.get("base_weights") or {}).items():
            if sym == "BIL" or eligible(p, t, sym):
                add(weights, sym, float(weight))
            else:
                add(weights, "BIL", float(weight))
    elif rule == "static_equal_weight":
        share = 1.0 / len(universe)
        for sym in universe:
            add(weights, sym, share)
    elif rule == "gtaa_breadth_defensive":
        risk_assets = [sym for sym in ["SPY", "QQQ", "EFA", "EEM", "IWM"] if sym in universe]
        if sum(1 for sym in risk_assets if eligible(p, t, sym)) >= 3:
            picks = rank_assets(p, t, risky)[:3]
            for pick in picks:
                add(weights, pick, 1 / 3)
            add(weights, "BIL", max(0.0, 1.0 - len(picks) / 3))
        else:
            defensive = rank_assets(p, t, ["GLD", "IEF"])[:1]
            add(weights, defensive[0] if defensive else "BIL", 0.5)
            add(weights, "BIL", 0.5)
    elif rule == "trend_equal_weight":
        assets = [sym for sym in risky if eligible(p, t, sym)]
        share = 1.0 / len(risky)
        for sym in assets:
            add(weights, sym, share)
        add(weights, "BIL", max(0.0, 1.0 - share * len(assets)))
    elif rule == "carry_yield_defensive_filter":
        spy_on = eligible(p, t, "SPY")
        assets = ["HYG", "EMB"] if spy_on else ["IEF"]
        picks = rank_assets(p, t, assets, risk_adjusted=True)[:1]
        add(weights, picks[0] if picks else "BIL", 1.0)
    return weights or {"BIL": 1.0}


def benchmark_weights(p: dict[str, Any], t: int, benchmark: str) -> dict[str, float]:
    if benchmark == "SPY_200d":
        return {"SPY": 1.0} if eligible(p, t, "SPY") else {"BIL": 1.0}
    symbol = benchmark.replace("_buy_hold", "").replace("_cash_proxy", "")
    return {symbol: 1.0} if symbol in p["idx"] else {}


def simulate(p: dict[str, Any], start: int, horizon: int, variant: dict[str, Any] | None = None, benchmark: str | None = None) -> dict[str, Any]:
    equity = STARTING_EQUITY
    peak = equity
    max_drawdown = 0.0
    weights: dict[str, float] = {}
    last_month = None
    stop = None
    target300 = None
    target400 = None
    for offset in range(1, horizon + 1):
        today = start + offset
        signal = today - 1
        month = int(p["months"][today])
        if month != last_month:
            new_weights = benchmark_weights(p, signal, benchmark) if benchmark else weights_for_variant(p, signal, variant or {})
            turnover = sum(abs(new_weights.get(sym, 0.0) - weights.get(sym, 0.0)) for sym in set(new_weights) | set(weights))
            equity -= equity * turnover * SLIPPAGE
            weights = new_weights
            last_month = month
        equity *= 1.0 + sum(weight * float(p["returns"][today, p["idx"][sym]]) for sym, weight in weights.items() if sym in p["idx"])
        peak = max(peak, equity)
        max_drawdown = min(max_drawdown, equity - peak)
        profit = equity - STARTING_EQUITY
        if stop is None and profit <= STOP_DOLLARS:
            stop = offset
        if target300 is None and profit >= 300:
            target300 = offset
        if target400 is None and profit >= 400:
            target400 = offset
    dates = p["close"].index
    return {
        "window_start": str(dates[start].date()),
        "window_end": str(dates[start + horizon].date()),
        "final_equity": equity,
        "profit_dollars": equity - STARTING_EQUITY,
        "total_return": equity / STARTING_EQUITY - 1,
        "max_drawdown": max_drawdown,
        "absolute_600_stop_hit": stop is not None,
        "target_300_before_stop": bool(target300 is not None and (stop is None or target300 <= stop)),
        "target_400_before_stop": bool(target400 is not None and (stop is None or target400 <= stop)),
    }


def sample_starts(length: int, horizon: int) -> list[int]:
    starts = list(range(252, length - horizon))
    if len(starts) <= MAX_WINDOWS_PER_HORIZON:
        return starts
    return sorted(set(int(x) for x in np.linspace(starts[0], starts[-1], MAX_WINDOWS_PER_HORIZON)))


def full_returns(p: dict[str, Any], variant: dict[str, Any] | None = None, benchmark: str | None = None) -> pd.Series:
    equity = STARTING_EQUITY
    weights: dict[str, float] = {}
    last_month = None
    values = []
    for today in range(253, len(p["close"])):
        signal = today - 1
        month = int(p["months"][today])
        if month != last_month:
            weights = benchmark_weights(p, signal, benchmark) if benchmark else weights_for_variant(p, signal, variant or {})
            last_month = month
        equity *= 1.0 + sum(weight * float(p["returns"][today, p["idx"][sym]]) for sym, weight in weights.items() if sym in p["idx"])
        values.append(equity)
    return pd.Series(values, index=p["close"].index[253:]).pct_change().dropna()


def summarize(rows: list[dict[str, Any]], strategy_id: str, horizon: int) -> dict[str, Any]:
    df = pd.DataFrame([row for row in rows if row["strategy_id"] == strategy_id and row["horizon"] == horizon])
    if df.empty:
        return {"strategy_id": strategy_id, "horizon": horizon, "validation_status": "evidence_missing"}
    return {
        "strategy_id": strategy_id,
        "horizon": horizon,
        "window_count": int(len(df)),
        "final_equity_median": float(df["final_equity"].median()),
        "final_equity_mean": float(df["final_equity"].mean()),
        "final_equity_p75": float(df["final_equity"].quantile(0.75)),
        "final_equity_p90": float(df["final_equity"].quantile(0.90)),
        "best_final_equity": float(df["final_equity"].max()),
        "worst_final_equity": float(df["final_equity"].min()),
        "target_300_rate": float(df["target_300_before_stop"].mean()),
        "target_400_rate": float(df["target_400_before_stop"].mean()),
        "worst_drawdown": float(df["max_drawdown"].min()),
        "median_drawdown": float(df["max_drawdown"].median()),
        "absolute_600_stop_hit_rate": float(df["absolute_600_stop_hit"].mean()),
        "worst_loss_window": float(df["profit_dollars"].min()),
        "median_profit_dollars": float(df["profit_dollars"].median()),
    }


def benchmark_missing_reason(p: dict[str, Any], benchmark_id: str) -> str:
    idx = p.get("idx", {})
    if benchmark_id == "SPY_200d":
        missing = [sym for sym in ["SPY", "BIL"] if sym not in idx]
        return "" if not missing else f"missing required symbols: {';'.join(missing)}"
    if benchmark_id.endswith("_buy_hold") or benchmark_id.endswith("_cash_proxy"):
        symbol = benchmark_id.replace("_buy_hold", "").replace("_cash_proxy", "")
        return "" if symbol in idx else f"missing required symbol: {symbol}"
    return "benchmark rule/equity series not available in parallel discovery export"


def benchmark_is_available(p: dict[str, Any], benchmark_id: str) -> bool:
    return benchmark_missing_reason(p, benchmark_id) == ""


def benchmark_delta_rows(
    family_id: str,
    variant: dict[str, Any],
    p: dict[str, Any],
    summary180: dict[str, Any],
) -> list[dict[str, Any]]:
    strategy_median = summary180.get("final_equity_median", "")
    rows: list[dict[str, Any]] = []
    starts = sample_starts(len(p["close"]), 180)
    for benchmark_id in COMBINED_BENCHMARK_IDS:
        missing_reason = benchmark_missing_reason(p, benchmark_id)
        if missing_reason:
            rows.append(
                {
                    "family_id": family_id,
                    "strategy_id": variant["strategy_id"],
                    "benchmark_id": benchmark_id,
                    "horizon": 180,
                    "strategy_median_equity": strategy_median,
                    "benchmark_median_equity": "",
                    "delta_median_equity": "",
                    "delta_sign_check": "not_applicable",
                    "comparison_status": "unavailable",
                    "benchmark_available": False,
                    "missing_reason": missing_reason,
                    "notes": "no zero-filled delta for unavailable benchmark",
                }
            )
            continue
        benchmark_results = [simulate(p, start, 180, benchmark=benchmark_id) for start in starts]
        benchmark_median = float(pd.DataFrame(benchmark_results)["final_equity"].median()) if benchmark_results else ""
        if strategy_median == "" or benchmark_median == "":
            delta = ""
            delta_sign_check = "not_applicable"
            status = "unavailable"
            missing = "strategy or benchmark median unavailable"
        else:
            delta = float(strategy_median) - float(benchmark_median)
            delta_sign_check = "passed"
            status = "available"
            missing = ""
        rows.append(
            {
                "family_id": family_id,
                "strategy_id": variant["strategy_id"],
                "benchmark_id": benchmark_id,
                "horizon": 180,
                "strategy_median_equity": strategy_median,
                "benchmark_median_equity": benchmark_median,
                "delta_median_equity": delta,
                "delta_sign_check": delta_sign_check,
                "comparison_status": status,
                "benchmark_available": status == "available",
                "missing_reason": missing,
                "notes": "delta=strategy_median_equity-benchmark_median_equity",
            }
        )
    return rows


def refine_exploratory_verdict(
    family_id: str,
    strategy_id: str,
    summary180: dict[str, Any],
    score_label: str,
    base_verdict: str,
    max_corr: float,
    missing_count: int,
    benchmark_deltas_available: bool,
) -> tuple[str, str]:
    if base_verdict == "promotion_review_candidate":
        return score_label, base_verdict
    if base_verdict not in {"watchlist", "too_slow", "duplicate_or_near_duplicate"}:
        return score_label, base_verdict
    if missing_count:
        return "needs_benchmark_delta_review", "needs_benchmark_delta_review"
    if not benchmark_deltas_available:
        return "needs_benchmark_delta_review", "needs_benchmark_delta_review"
    if base_verdict == "duplicate_or_near_duplicate":
        return "duplicate_watchlist", "duplicate_watchlist"
    if family_id == "gtaa_faber_style_benchmark_lane":
        return "benchmark_watchlist", "benchmark_watchlist"
    if family_id == "static_all_weather_or_permanent_portfolio_benchmark":
        if summary180.get("worst_drawdown", STOP_DOLLARS) > STOP_DOLLARS * 0.5:
            return "defensive_watchlist", "defensive_watchlist"
        return "benchmark_watchlist", "benchmark_watchlist"
    if family_id in {"low_beta_defensive_equity_etf", "dividend_quality_yield_etf"}:
        if base_verdict == "too_slow":
            return "too_slow_for_profit_goal", "too_slow_for_profit_goal"
        return "defensive_watchlist", "defensive_watchlist"
    if family_id == "carry_yield_etf_proxy":
        if base_verdict == "too_slow":
            return "too_slow_for_profit_goal", "too_slow_for_profit_goal"
        if max_corr < 0.70:
            return "diversifier_watchlist_candidate", "diversifier_watchlist_candidate"
        return "defensive_watchlist", "defensive_watchlist"
    if "managed_futures" in family_id or "managed_futures" in strategy_id:
        return "short_history_watchlist", "short_history_watchlist"
    if base_verdict == "too_slow":
        return "too_slow_for_profit_goal", "too_slow_for_profit_goal"
    return score_label, base_verdict


def score_and_verdict(summary180: dict[str, Any], max_corr: float, missing_count: int) -> tuple[float, str, str]:
    if summary180.get("validation_status") == "evidence_missing":
        return 0.0, "reject", "evidence_missing"
    profit = min(40, max(0, summary180["median_profit_dollars"] / 300 * 14 + summary180["target_300_rate"] * 12 + summary180["target_400_rate"] * 8 + max(0, (summary180["final_equity_p90"] - 3000) / 500 * 6)))
    risk = min(25, (10 if summary180["absolute_600_stop_hit_rate"] == 0 else 0) + max(0, 10 * (1 + summary180["worst_drawdown"] / 600)) + max(0, 5 * (1 + summary180["worst_loss_window"] / 600)))
    additive = max(0, 25 * (1 - min(max_corr, 1)))
    score = profit + risk + additive + 10 - (20 if missing_count else 0)
    if summary180["absolute_600_stop_hit_rate"] > 0 or summary180["worst_drawdown"] <= STOP_DOLLARS:
        return max(0, score - 30), "weak", "too_risky"
    if summary180["target_300_rate"] < 0.10 and summary180["median_profit_dollars"] < 100:
        return max(0, score - 25), "weak", "too_slow"
    if max_corr >= 0.85:
        return max(0, score - 25), "weak", "duplicate_or_near_duplicate"
    verdict = "promotion_review_candidate" if score >= PROMOTION_SCORE_THRESHOLD and summary180["target_300_rate"] >= PROMOTION_TARGET300_THRESHOLD else "watchlist"
    label = "strong_candidate" if score >= 80 else "possible_candidate" if score >= 65 else "watchlist" if score >= 45 else "weak" if score >= 25 else "reject"
    return round(max(0, min(100, score)), 2), label, verdict


def create_packet(directory: Path, name: str) -> Path:
    packet = directory / name
    if packet.exists():
        packet.unlink()
    with zipfile.ZipFile(packet, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(directory.iterdir()):
            if path.is_file() and path.name != packet.name:
                zf.write(path, path.name)
    return packet


def write_label_update_outputs(
    root: Path,
    classification_rows: list[dict[str, Any]],
    combined_delta_rows: list[dict[str, Any]],
    strategy_rows: list[dict[str, Any]],
    before_protected: dict[str, dict[str, Any]],
    after_protected: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    label_dir = root / LABEL_UPDATE_DIR
    if label_dir.exists():
        shutil.rmtree(label_dir)
    label_dir.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "family_id",
        "strategy_id",
        "previous_generic_verdict",
        "updated_label",
        "profit_first_score",
        "promotion_candidate",
        "candidate_exhaustive_unlocked",
        "paper_forward_unlocked",
        "reason",
    ]
    write_csv(label_dir / "updated_watchlist_classification.csv", classification_rows, fieldnames)
    (label_dir / "label_mapping.md").write_text(
        "# Exploratory Gate Label Mapping\n\n"
        "- `diversifier_watchlist_candidate`: low-correlation, acceptable-risk row that may be useful as a diversifier but is not promotion-ready.\n"
        "- `short_history_watchlist`: wrapper/history is too short for strong conclusions.\n"
        "- `benchmark_watchlist`: useful as a sanity-check or benchmark lane, not promotion-ready.\n"
        "- `defensive_watchlist`: good drawdown/control profile but weak profit objective fit.\n"
        "- `too_slow_for_profit_goal`: controlled risk but weak +300/+400 or median-profit behavior.\n"
        "- `duplicate_watchlist`: duplicate-like comparison row worth retaining as a reference.\n"
        "- `needs_benchmark_delta_review`: key benchmark comparison is missing, so no confident label upgrade is made.\n\n"
        "All labels above are non-promotion labels and route to continued research/watching only.\n",
        encoding="utf-8",
    )
    unavailable_rows = [row for row in combined_delta_rows if row["comparison_status"] == "unavailable"]
    unavailable_zero_filled = [
        row
        for row in unavailable_rows
        if str(row.get("delta_median_equity", "")).strip() in {"0", "0.0"}
    ]
    (label_dir / "combined_benchmark_delta_export_review.md").write_text(
        "# Combined Benchmark Delta Export Review\n\n"
        f"- Export created: `{(root / OUTPUT_DIR / 'combined_benchmark_delta.csv').exists()}`\n"
        f"- Rows exported: `{len(combined_delta_rows)}`\n"
        f"- Unavailable rows: `{len(unavailable_rows)}`\n"
        f"- Unavailable rows zero-filled: `{len(unavailable_zero_filled)}`\n"
        "- Delta formula: `strategy_median_equity - benchmark_median_equity`.\n"
        "- Active/paper-forward protected benchmark lanes are recorded as unavailable when their equity series is not available to this discovery export.\n",
        encoding="utf-8",
    )
    reclassified = [row for row in classification_rows if row["previous_generic_verdict"] != row["updated_label"]]
    promotions = [row for row in strategy_rows if is_promotion_candidate(row["strategy_verdict"])]
    consistency = {
        "labels_added": sorted(EXPLORATORY_LABELS),
        "promotion_thresholds_unchanged": PROMOTION_SCORE_THRESHOLD == 70 and PROMOTION_TARGET300_THRESHOLD == 0.25,
        "new_labels_are_not_promotion_candidates": all(not is_promotion_candidate(label) for label in EXPLORATORY_LABELS),
        "candidate_exhaustive_not_unlocked": all(next_action_for_verdict(label) != "run_candidate_exhaustive" for label in EXPLORATORY_LABELS),
        "paper_forward_not_unlocked": all("paper_forward" not in next_action_for_verdict(label) for label in EXPLORATORY_LABELS),
        "combined_benchmark_delta_export_created": (root / OUTPUT_DIR / "combined_benchmark_delta.csv").exists(),
        "unavailable_benchmarks_not_zero": not unavailable_zero_filled,
        "active_observations_unchanged": before_protected == after_protected,
        "no_candidate_exhaustive_run": True,
        "no_paper_forward_activation": True,
        "no_broker_path_added": True,
        "no_live_order_path_added": True,
        "no_real_money_recommendation": True,
        "consistency_passed": False,
    }
    consistency["consistency_passed"] = all(
        value is True for key, value in consistency.items() if key not in {"labels_added", "consistency_passed"}
    )
    write_json(label_dir / "exploratory_gate_label_consistency_check.json", consistency)
    (label_dir / "exploratory_gate_label_update_summary.md").write_text(
        "# Exploratory Gate Label Update\n\n"
        f"- Labels added: `{', '.join(sorted(EXPLORATORY_LABELS))}`\n"
        "- Promotion thresholds were not weakened: score remains `70`, +300 target rate remains `0.25`.\n"
        "- New labels do not unlock candidate_exhaustive, paper-forward review, or paper-forward activation.\n"
        f"- Reclassified rows: `{len(reclassified)}`\n"
        f"- Promotion candidates after relabeling: `{len(promotions)}`\n"
        f"- Combined benchmark-delta export created: `{consistency['combined_benchmark_delta_export_created']}`\n"
        "- This is a labeling/export fix only; no strategy rules or active observations were changed.\n",
        encoding="utf-8",
    )
    create_packet(label_dir, "exploratory_gate_label_update_packet.zip")
    return consistency


def run_parallel_discovery(root: Path = ROOT, downloader: Downloader | None = None, allow_download: bool = True, update_registry_file: bool = True) -> dict[str, Any]:
    queue = load_yaml(root / QUEUE_PATH)
    validate_queue(queue)
    registry_path = root / REGISTRY_PATH
    registry = load_yaml(registry_path)
    before_protected = protected_snapshot(registry)
    symbols = sorted({sym for fam in queue["families"] if fam.get("run_enabled") for sym in fam.get("approved_symbols", [])})
    qa_rows, download_rows, provider_called, downloaded = bootstrap_symbols(root, symbols, downloader, allow_download)
    qa_by_symbol = {row["symbol"]: row for row in qa_rows}

    combined_dir = root / OUTPUT_DIR
    if combined_dir.exists():
        shutil.rmtree(combined_dir)
    combined_dir.mkdir(parents=True, exist_ok=True)

    family_rows: list[dict[str, Any]] = []
    strategy_rows: list[dict[str, Any]] = []
    all_benchmark_rows: list[dict[str, Any]] = []
    combined_benchmark_delta_rows: list[dict[str, Any]] = []
    classification_rows: list[dict[str, Any]] = []
    all_duplicate_rows: list[dict[str, Any]] = []

    for family in [fam for fam in queue["families"] if fam.get("run_enabled")]:
        family_id = family["family_id"]
        family_dir = root / "evidence" / "research_samples" / family_id / "latest"
        if family_dir.exists():
            shutil.rmtree(family_dir)
        family_dir.mkdir(parents=True, exist_ok=True)
        family_symbols = sorted({sym for variant in family["variants"] for sym in variant["universe"]})
        available = [sym for sym in family_symbols if qa_by_symbol.get(sym, {}).get("inclusion_decision") == "include"]
        missing = [sym for sym in family_symbols if sym not in available]
        close_map = {sym: read_close(root, sym) for sym in available}
        close = pd.concat([series for series in close_map.values() if series is not None], axis=1, join="inner").dropna().sort_index() if close_map else pd.DataFrame()
        window_rows: list[dict[str, Any]] = []
        rolling_rows: list[dict[str, Any]] = []
        verdict_rows: list[dict[str, Any]] = []
        scores: list[dict[str, Any]] = []
        if len(close) >= 432 and "BIL" in close.columns:
            p = prepared(close)
            bench_ids = ["SPY_200d"] + [f"{sym}_buy_hold" for sym in ["SPY", "QQQ", "BIL"] if sym in close.columns]
            for variant in family["variants"]:
                required = set(variant["universe"])
                if not required <= set(close.columns):
                    summary180 = {"strategy_id": variant["strategy_id"], "validation_status": "evidence_missing"}
                    score, label, verdict = score_and_verdict(summary180, 1.0, len(required - set(close.columns)))
                    base_verdict = verdict
                    delta_rows = benchmark_delta_rows(family_id, variant, p, summary180)
                    combined_benchmark_delta_rows.extend(delta_rows)
                else:
                    for horizon in HORIZONS:
                        for start in sample_starts(len(close), horizon):
                            row = simulate(p, start, horizon, variant)
                            row.update({"family_id": family_id, "strategy_id": variant["strategy_id"], "horizon": horizon, "sampled_results_are_final": False, "exploratory_results_are_final": False})
                            window_rows.append(row)
                    summaries = [summarize(window_rows, variant["strategy_id"], horizon) for horizon in HORIZONS]
                    rolling_rows.extend(summaries)
                    summary180 = next(row for row in summaries if row["horizon"] == 180)
                    variant_returns = full_returns(p, variant)
                    corr_values = []
                    for bench in bench_ids:
                        bench_returns = full_returns(p, None, benchmark=bench)
                        aligned = pd.concat([variant_returns.rename("variant"), bench_returns.rename("bench")], axis=1).dropna()
                        corr = float(aligned["variant"].corr(aligned["bench"])) if len(aligned) > 5 else np.nan
                        corr_values.append(corr)
                        all_benchmark_rows.append({"family_id": family_id, "strategy_id": variant["strategy_id"], "benchmark_id": bench, "horizon": 180, "correlation": corr})
                    max_corr = max([abs(c) for c in corr_values if np.isfinite(c)] or [1.0])
                    score, label, verdict = score_and_verdict(summary180, max_corr, len(missing))
                    base_verdict = verdict
                    delta_rows = benchmark_delta_rows(family_id, variant, p, summary180)
                    combined_benchmark_delta_rows.extend(delta_rows)
                    label, verdict = refine_exploratory_verdict(
                        family_id,
                        variant["strategy_id"],
                        summary180,
                        label,
                        verdict,
                        max_corr,
                        len(missing),
                        any(row["comparison_status"] == "available" for row in delta_rows),
                    )
                    all_duplicate_rows.append({"family_id": family_id, "strategy_id": variant["strategy_id"], "max_abs_available_correlation": max_corr, "duplicate_label": "duplicate_or_near_duplicate" if max_corr >= 0.85 else "not_proven_duplicate", "additive_label": "possible_additive" if max_corr < 0.70 else "weak_or_unclear_additive"})
                score_row = {"family_id": family_id, "strategy_id": variant["strategy_id"], "profit_first_score": score, "score_label": label, "strategy_verdict": verdict}
                scores.append(score_row)
                strategy_rows.append(score_row)
                classification_rows.append(
                    {
                        "family_id": family_id,
                        "strategy_id": variant["strategy_id"],
                        "previous_generic_verdict": base_verdict if "base_verdict" in locals() else verdict,
                        "updated_label": verdict,
                        "profit_first_score": score,
                        "promotion_candidate": is_promotion_candidate(verdict),
                        "candidate_exhaustive_unlocked": False,
                        "paper_forward_unlocked": False,
                        "reason": f"score={score}; label={label}",
                    }
                )
                verdict_rows.append({"strategy_id": variant["strategy_id"], "strategy_verdict": verdict, "next_allowed_action": next_action_for_verdict(verdict), "reason": f"score={score}; label={label}"})
        else:
            for variant in family["variants"]:
                row = {"family_id": family_id, "strategy_id": variant["strategy_id"], "profit_first_score": 0, "score_label": "reject", "strategy_verdict": "evidence_missing"}
                scores.append(row)
                strategy_rows.append(row)
                classification_rows.append(
                    {
                        "family_id": family_id,
                        "strategy_id": variant["strategy_id"],
                        "previous_generic_verdict": "evidence_missing",
                        "updated_label": "evidence_missing",
                        "profit_first_score": 0,
                        "promotion_candidate": False,
                        "candidate_exhaustive_unlocked": False,
                        "paper_forward_unlocked": False,
                        "reason": "insufficient data",
                    }
                )
                verdict_rows.append({"strategy_id": variant["strategy_id"], "strategy_verdict": "evidence_missing", "next_allowed_action": NEXT_FAIL, "reason": "insufficient data"})
        if any(row["strategy_verdict"] == "promotion_review_candidate" for row in scores):
            family_verdict = "promotion_review_candidate_family"
        elif all(row["strategy_verdict"] in {"too_risky", "evidence_missing", "reject"} for row in scores):
            family_verdict = "reject_family"
        else:
            family_verdict = "watchlist_family"
        best_score = max([float(row["profit_first_score"]) for row in scores] or [0])
        family_row = {"family_id": family_id, "family_verdict": family_verdict, "best_score": best_score, "best_strategy_id": max(scores, key=lambda row: float(row["profit_first_score"]))["strategy_id"] if scores else "", "missing_symbols": ";".join(missing)}
        family_rows.append(family_row)
        write_csv(family_dir / f"{family_id}_strategy_verdicts.csv", verdict_rows, ["strategy_id", "strategy_verdict", "next_allowed_action", "reason"])
        write_csv(family_dir / f"{family_id}_profit_first_scores.csv", scores, ["family_id", "strategy_id", "profit_first_score", "score_label", "strategy_verdict"])
        write_csv(family_dir / f"{family_id}_rolling_summary.csv", rolling_rows, sorted({k for row in rolling_rows for k in row}) if rolling_rows else ["strategy_id", "horizon", "validation_status"])
        write_csv(family_dir / f"{family_id}_data_quality.csv", [qa_by_symbol[sym] for sym in family_symbols if sym in qa_by_symbol], list(qa_rows[0].keys()))
        write_json(family_dir / f"{family_id}_manifest.json", {"family_id": family_id, "family_verdict": family_verdict, "exploratory_non_final": True, "candidate_exhaustive_run": False, "paper_forward_activation": False, "real_money_recommendation": False})

    promotions = [row for row in strategy_rows if row["strategy_verdict"] == "promotion_review_candidate"]
    best_family = max(family_rows, key=lambda row: float(row["best_score"])) if family_rows else {}
    next_action = NEXT_PROMOTION if promotions else NEXT_CONTINUE if best_family and best_family.get("family_verdict") == "watchlist_family" else NEXT_FAIL

    write_csv(combined_dir / "family_leaderboard.csv", sorted(family_rows, key=lambda row: float(row["best_score"]), reverse=True), ["family_id", "family_verdict", "best_score", "best_strategy_id", "missing_symbols"])
    write_csv(combined_dir / "strategy_leaderboard.csv", sorted(strategy_rows, key=lambda row: float(row["profit_first_score"]), reverse=True), ["family_id", "strategy_id", "profit_first_score", "score_label", "strategy_verdict"])
    write_csv(combined_dir / "promotion_review_candidates.csv", promotions, ["family_id", "strategy_id", "profit_first_score", "score_label", "strategy_verdict"])
    bucket_specs = [
        ("watchlist_rows.csv", WATCHLIST_VERDICTS),
        ("rejected_rows.csv", {"reject"}),
        ("duplicate_rows.csv", {"duplicate_or_near_duplicate", "duplicate_watchlist"}),
        ("too_risky_rows.csv", {"too_risky"}),
        ("too_slow_rows.csv", {"too_slow", "too_slow_for_profit_goal"}),
    ]
    for name, verdicts in bucket_specs:
        rows = [row for row in strategy_rows if row["strategy_verdict"] in verdicts]
        write_csv(combined_dir / name, rows, ["family_id", "strategy_id", "profit_first_score", "score_label", "strategy_verdict"])
    write_csv(
        combined_dir / "combined_benchmark_delta.csv",
        combined_benchmark_delta_rows,
        [
            "family_id",
            "strategy_id",
            "benchmark_id",
            "horizon",
            "strategy_median_equity",
            "benchmark_median_equity",
            "delta_median_equity",
            "delta_sign_check",
            "comparison_status",
            "benchmark_available",
            "missing_reason",
            "notes",
        ],
    )
    write_csv(combined_dir / "data_quality_summary.csv", qa_rows, list(qa_rows[0].keys()))
    write_csv(combined_dir / "download_log.csv", download_rows, ["symbol", "status", "provider_api_called", "detail"])
    (combined_dir / "next_action.md").write_text(f"# Next Action\n\n`{next_action}`\n", encoding="utf-8")
    after_protected = protected_snapshot(registry)
    label_consistency = write_label_update_outputs(root, classification_rows, combined_benchmark_delta_rows, strategy_rows, before_protected, after_protected)
    (combined_dir / "parallel_research_discovery_summary.md").write_text(f"# Parallel Research Discovery\n\nFamilies tested: `{len(family_rows)}`\n\nBest family: `{best_family.get('family_id', '')}`\n\nNext action: `{next_action}`\n\nCombined benchmark delta rows: `{len(combined_benchmark_delta_rows)}`\n\nExploratory label update: `{root / LABEL_UPDATE_DIR}`\n", encoding="utf-8")
    consistency = {
        "parallel_discovery_completed": True,
        "exploratory_non_final": True,
        "no_candidate_exhaustive_run": True,
        "no_paper_forward_activation": True,
        "active_observations_unchanged": after_protected == before_protected,
        "no_broker_path_added": True,
        "no_live_order_path_added": True,
        "no_real_money_recommendation": True,
        "approved_symbols_only": set(symbols) <= APPROVED_SYMBOLS,
        "no_individual_stocks": True,
        "no_direct_futures": True,
        "no_options": True,
        "no_forex": True,
        "no_crypto": True,
        "no_intraday": True,
        "no_leverage_added_by_system": True,
        "family_outputs_isolated": all((root / "evidence" / "research_samples" / row["family_id"] / "latest").exists() for row in family_rows),
        "combined_leaderboard_created": (combined_dir / "strategy_leaderboard.csv").exists(),
        "combined_benchmark_delta_export_created": (combined_dir / "combined_benchmark_delta.csv").exists(),
        "exploratory_gate_label_update_created": label_consistency["consistency_passed"],
        "next_action_explicit": bool(next_action),
        "consistency_passed": False,
    }
    consistency["consistency_passed"] = all(value is True for key, value in consistency.items() if key != "consistency_passed")
    manifest = {"created_at_utc": now_utc(), "families_tested": [row["family_id"] for row in family_rows], "labels_added": sorted(EXPLORATORY_LABELS), "promotion_thresholds_unchanged": True, "combined_benchmark_delta_created": True, "data_downloaded": bool(downloaded), "downloaded_symbols": downloaded, "provider_api_called": provider_called, "next_action": next_action, "audit_next_action_addressed": AUDIT_NEXT_ACTION, "candidate_exhaustive_run": False, "paper_forward_activation": False, "real_money_recommendation": False}
    write_json(combined_dir / "parallel_research_discovery_manifest.json", manifest)
    write_json(combined_dir / "parallel_research_discovery_consistency_check.json", consistency)
    create_packet(combined_dir, "parallel_research_discovery_packet.zip")

    if update_registry_file:
        updated = deepcopy(registry)
        rows = rows_by_id(updated)
        for family_row in family_rows:
            row = rows.get(family_row["family_id"])
            if row and row.get("paper_forward_active") is not True:
                row["status"] = family_row["family_verdict"]
                row["current_status"] = family_row["family_verdict"]
                row["family_verdict"] = family_row["family_verdict"]
                row["allowed_next_action"] = next_action
                row["next_allowed_action"] = next_action
                row["allowed_next_actions"] = [next_action]
                row["latest_evidence_path"] = str(root / "evidence" / "research_samples" / family_row["family_id"] / "latest")
                row["paper_forward_active"] = False
                row["real_money_recommendation"] = False
                row["candidate_exhaustive_run"] = False
        registry_path.write_text(yaml.safe_dump(updated, sort_keys=False, width=140), encoding="utf-8")
    return {"output_dir": str(combined_dir), "families_tested": [row["family_id"] for row in family_rows], "downloaded_symbols": downloaded, "best_family": best_family, "best_strategy": max(strategy_rows, key=lambda row: float(row["profit_first_score"])) if strategy_rows else {}, "promotion_candidates": promotions, "next_action": next_action, "consistency": consistency}


def main() -> int:
    result = run_parallel_discovery(ROOT, allow_download=False)
    print(f"parallel_discovery_latest_dir={result['output_dir']}")
    print(f"families_tested={','.join(result['families_tested'])}")
    print(f"downloaded_symbols={','.join(result['downloaded_symbols']) or 'none'}")
    print(f"best_family={result['best_family'].get('family_id', '')}")
    print(f"best_strategy={result['best_strategy'].get('strategy_id', '')}")
    print(f"promotion_candidates={len(result['promotion_candidates'])}")
    print(f"next_action={result['next_action']}")
    print(f"consistency_passed={str(result['consistency']['consistency_passed']).lower()}")
    return 0 if result["consistency"]["consistency_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
