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
FAMILY_ID = "dual_momentum_paa_etf_wrapper"
OUTPUT_DIR = Path("evidence") / "research_samples" / FAMILY_ID / "latest"
REGISTRY_PATH = Path("strategy_lab") / "strategy_registry.yaml"
STARTING_EQUITY = 3000.0
STOP_DOLLARS = -600.0
SLIPPAGE = 0.0005
HORIZONS = [30, 60, 90, 180]
MAX_WINDOWS_PER_HORIZON = 240
CORE_SYMBOLS = ["SPY", "QQQ", "EFA", "EEM", "IWM", "GLD", "IEF", "BIL"]
CONDITIONAL_BENCHMARKS = ["TLT", "AGG"]
APPROVED_SYMBOLS = CORE_SYMBOLS + CONDITIONAL_BENCHMARKS
NEXT_LANE_ACTION = "create_gtaa_faber_style_benchmark_lane_review_prompt"
PROMOTION_ACTION = "create_promotion_review_for_dual_momentum_paa_etf_wrapper"

PROTECTED_IDS = {
    "current_no_cash_proxy_alpha_AB",
    "paper_forward_vm_quality_lowvol_proxy_v1",
    "paper_forward_dsr_sector_equal_weight_defensive_filter_v1",
    "SPY_200d_trend_model",
}

VARIANT_IDS = [
    "dm_global_dual_momentum_top1_v1",
    "dm_multi_asset_top2_absolute_momentum_v1",
    "dm_protective_canary_bil_v1",
    "dm_balanced_offensive_defensive_v1",
    "dm_paa_breadth_protection_v1",
]

FORBIDDEN_FLAGS = {
    "direct_futures_contracts": False,
    "options": False,
    "forex": False,
    "crypto": False,
    "intraday_logic": False,
    "leverage_added_by_system": False,
    "margin": False,
    "shorting": False,
    "individual_stock_strategy_logic": False,
    "broker_integration": False,
    "live_orders": False,
    "order_placement": False,
    "real_money_recommendation": False,
    "paper_forward_activation": False,
    "paper_forward_checkpoint": False,
    "candidate_exhaustive_run": False,
    "parameter_optimization": False,
    "grid_search": False,
}

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


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else ""


def cache_path(root: Path, symbol: str) -> Path:
    return root / "data" / "cache" / f"{symbol}.csv"


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"registry": {"schema_version": 1, "project": "trading_tournament", "research_only": True}, "strategies": []}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def load_config(root: Path) -> dict[str, Any]:
    path = root / "config.yaml"
    if not path.exists():
        return {"data": {"start_date": "2007-01-01", "end_date": None, "yfinance": {}}}
    return load_yaml(path)


def rows_by_id(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(row.get("id")): row for row in registry.get("strategies", [])}


def protected_snapshot(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = rows_by_id(registry)
    return {
        row_id: deepcopy(row)
        for row_id, row in rows.items()
        if row_id in PROTECTED_IDS or row.get("paper_forward_active") is True
    }


def state_is_ready(root: Path, registry: dict[str, Any]) -> tuple[bool, list[str]]:
    mismatches: list[str] = []
    review_manifest = root / "evidence" / "lane_reviews" / FAMILY_ID / "latest" / f"{FAMILY_ID}_manifest.json"
    if not review_manifest.exists():
        mismatches.append("dual momentum review manifest missing")
    else:
        payload = json.loads(review_manifest.read_text(encoding="utf-8"))
        if payload.get("lane_verdict") != "approve_future_research_sample_prompt":
            mismatches.append("dual momentum review did not approve future research_sample")
        if payload.get("next_action") != "create_dual_momentum_paa_etf_wrapper_research_sample_prompt":
            mismatches.append("dual momentum review next action is not research_sample prompt")
    rows = rows_by_id(registry)
    managed = rows.get("managed_futures_etf_wrapper", {})
    if managed.get("family_verdict") != "watchlist_family":
        mismatches.append("managed futures is not watchlist_family")
    dual = rows.get(FAMILY_ID, {})
    if dual.get("allowed_next_action") != "create_dual_momentum_paa_etf_wrapper_research_sample_prompt":
        mismatches.append("dual momentum registry next action is not research_sample prompt")
    for row_id in ["paper_forward_vm_quality_lowvol_proxy_v1", "paper_forward_dsr_sector_equal_weight_defensive_filter_v1", "SPY_200d_trend_model"]:
        row = rows.get(row_id, {})
        if row.get("paper_forward_active") is not True or row.get("rules_frozen") is not True:
            mismatches.append(f"{row_id} is not active/frozen")
    return not mismatches, mismatches


def validate_symbol(symbol: str) -> str:
    normalized = symbol.upper().strip()
    if normalized not in APPROVED_SYMBOLS:
        raise ValueError(f"unapproved symbol requested: {symbol}")
    return normalized


def qa_cache(root: Path, symbol: str) -> dict[str, Any]:
    symbol = validate_symbol(symbol)
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
        "warmup_sufficiency_200d_sma": False,
        "warmup_sufficiency_126d_return": False,
        "warmup_sufficiency_60d_volatility": False,
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
    columns = {str(col).strip().lower(): col for col in frame.columns}
    if "date" not in columns or "adj_close" not in columns:
        row["reason_for_exclusion"] = "date or adj_close missing"
        return row
    dates = pd.to_datetime(frame[columns["date"]], errors="coerce").dt.tz_localize(None)
    close = pd.to_numeric(frame[columns["adj_close"]], errors="coerce")
    duplicate_dates = int(dates.dropna().duplicated().sum())
    missing_close = int(close.isna().sum())
    ohlc_cols = [columns[col] for col in ["open", "high", "low", "close"] if col in columns]
    impossible_ohlc = ""
    if ohlc_cols:
        ohlc = frame[ohlc_cols].apply(pd.to_numeric, errors="coerce")
        impossible_ohlc = int((ohlc <= 0).any(axis=1).sum())
    valid_count = int((dates.notna() & close.notna()).sum())
    include = valid_count >= 260 and missing_close == 0 and duplicate_dates == 0 and (impossible_ohlc in {"", 0})
    valid_dates = dates.dropna()
    row.update(
        {
            "first_date": "" if valid_dates.empty else str(valid_dates.min().date()),
            "last_date": "" if valid_dates.empty else str(valid_dates.max().date()),
            "row_count": int(len(frame)),
            "adjusted_close_availability": True,
            "missing_adjusted_close_count": missing_close,
            "duplicate_dates": duplicate_dates,
            "impossible_ohlc_values": impossible_ohlc,
            "warmup_sufficiency_200d_sma": valid_count >= 200,
            "warmup_sufficiency_126d_return": valid_count >= 126,
            "warmup_sufficiency_60d_volatility": valid_count >= 60,
            "inclusion_decision": "include" if include else "exclude",
            "reason_for_exclusion": "" if include else "missing, duplicate, non-positive, or insufficient adjusted close history",
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


def ensure_symbol_data(
    root: Path,
    symbols: list[str],
    downloader: Downloader | None,
    allow_download: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], bool, list[str], list[str]]:
    config = load_config(root)
    data_cfg = config.get("data", {})
    start = str(data_cfg.get("start_date", "2007-01-01"))
    end = data_cfg.get("end_date")
    params = data_cfg.get("yfinance", {})
    downloader = downloader or _download_yfinance
    download_rows: list[dict[str, Any]] = []
    provider_api_called = False
    downloaded: list[str] = []
    failed: list[str] = []
    for symbol in [validate_symbol(symbol) for symbol in symbols]:
        qa = qa_cache(root, symbol)
        if qa["inclusion_decision"] == "include":
            download_rows.append({"symbol": symbol, "status": "used_existing_cache", "provider_api_called": False, "detail": "cache passed QA"})
            continue
        if not allow_download:
            failed.append(symbol)
            download_rows.append({"symbol": symbol, "status": "missing_no_download", "provider_api_called": False, "detail": qa["reason_for_exclusion"]})
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
            after = qa_cache(root, symbol)
            if after["inclusion_decision"] != "include":
                raise DataQualityError(after["reason_for_exclusion"])
            downloaded.append(symbol)
            download_rows.append({"symbol": symbol, "status": "downloaded", "provider_api_called": True, "detail": "downloaded normalized adjusted daily ETF/fund-wrapper data"})
        except Exception as exc:
            failed.append(symbol)
            download_rows.append({"symbol": symbol, "status": "download_failed", "provider_api_called": True, "detail": str(exc)})
    return [qa_cache(root, symbol) for symbol in symbols], download_rows, provider_api_called, downloaded, failed


def prepared(close: pd.DataFrame) -> dict[str, Any]:
    values = close.to_numpy(dtype=float)
    above = values > close.rolling(200).mean().to_numpy(dtype=float)
    ret126 = (close / close.shift(126) - 1.0).replace([np.inf, -np.inf], np.nan).fillna(-1e9).to_numpy(dtype=float)
    returns = np.zeros_like(values)
    returns[1:] = values[1:] / values[:-1] - 1.0
    vol60 = pd.DataFrame(returns, index=close.index, columns=close.columns).rolling(60).std().replace(0, np.nan).to_numpy(dtype=float)
    return {
        "close": close,
        "idx": {sym: i for i, sym in enumerate(close.columns)},
        "above": above,
        "ret126": ret126,
        "returns": returns,
        "vol60": vol60,
        "months": np.array([dt.year * 12 + dt.month for dt in close.index], dtype=int),
    }


def eligible(p: dict[str, Any], t: int, sym: str, require_positive_return: bool = True) -> bool:
    if sym not in p["idx"]:
        return False
    idx = p["idx"][sym]
    if not p["above"][t, idx]:
        return False
    return bool(p["ret126"][t, idx] > 0) if require_positive_return else True


def rank_assets(p: dict[str, Any], t: int, assets: list[str], risk_adjusted: bool = False, require_positive_return: bool = True) -> list[str]:
    scored: list[tuple[str, float]] = []
    for sym in assets:
        if not eligible(p, t, sym, require_positive_return=require_positive_return):
            continue
        idx = p["idx"][sym]
        score = float(p["ret126"][t, idx])
        if risk_adjusted:
            vol = float(p["vol60"][t, idx])
            score = score / vol if np.isfinite(vol) and vol > 0 else -1e9
        scored.append((sym, score))
    return [sym for sym, _ in sorted(scored, key=lambda item: item[1], reverse=True)]


def add_weight(weights: dict[str, float], sym: str, amount: float) -> None:
    weights[sym] = weights.get(sym, 0.0) + amount


def weights_for_variant(p: dict[str, Any], t: int, variant: str) -> dict[str, float]:
    weights: dict[str, float] = {}
    if variant == "dm_global_dual_momentum_top1_v1":
        picks = rank_assets(p, t, ["SPY", "EFA", "EEM"], require_positive_return=True)
        add_weight(weights, picks[0] if picks else "BIL", 1.0)
    elif variant == "dm_multi_asset_top2_absolute_momentum_v1":
        picks = rank_assets(p, t, ["SPY", "QQQ", "EFA", "EEM", "IWM", "GLD", "IEF"], risk_adjusted=True)[:2]
        for pick in picks:
            add_weight(weights, pick, 0.5)
        if len(picks) < 2:
            add_weight(weights, "BIL", (2 - len(picks)) * 0.5)
    elif variant == "dm_protective_canary_bil_v1":
        canary_bad = all((not eligible(p, t, sym, require_positive_return=True)) for sym in ["EFA", "EEM"])
        if canary_bad:
            add_weight(weights, "BIL", 1.0)
        else:
            picks = rank_assets(p, t, ["SPY", "QQQ", "GLD", "IEF"], risk_adjusted=True)[:2]
            for pick in picks:
                add_weight(weights, pick, 0.5)
            if len(picks) < 2:
                add_weight(weights, "BIL", (2 - len(picks)) * 0.5)
    elif variant == "dm_balanced_offensive_defensive_v1":
        defensive = rank_assets(p, t, ["GLD", "IEF"], require_positive_return=False)
        defensive_pick = defensive[0] if defensive else "BIL"
        spy_on = "SPY" in p["idx"] and p["above"][t, p["idx"]["SPY"]]
        if spy_on:
            offensive = rank_assets(p, t, ["SPY", "QQQ", "EFA", "EEM"], require_positive_return=False)
            add_weight(weights, offensive[0] if offensive else "BIL", 0.6)
            add_weight(weights, defensive_pick, 0.4)
        else:
            add_weight(weights, defensive_pick, 0.4)
            add_weight(weights, "BIL", 0.6)
    elif variant == "dm_paa_breadth_protection_v1":
        risky = ["SPY", "QQQ", "EFA", "EEM", "IWM"]
        positives = [sym for sym in risky if eligible(p, t, sym, require_positive_return=True)]
        if len(positives) < 2:
            defensive = rank_assets(p, t, ["GLD", "IEF"], require_positive_return=True)
            add_weight(weights, defensive[0] if defensive else "BIL", 0.5)
            add_weight(weights, "BIL", 0.5)
        else:
            picks = rank_assets(p, t, ["SPY", "QQQ", "EFA", "EEM", "IWM", "GLD", "IEF"], risk_adjusted=True)[:2]
            for pick in picks:
                add_weight(weights, pick, 0.5)
            if len(picks) < 2:
                add_weight(weights, "BIL", (2 - len(picks)) * 0.5)
    return weights


def benchmark_weights(p: dict[str, Any], t: int, benchmark: str) -> dict[str, float]:
    if benchmark == "SPY_200d":
        return {"SPY": 1.0} if p["above"][t, p["idx"]["SPY"]] else {"BIL": 1.0}
    if benchmark == "equal_weight_tactical_basket":
        assets = [sym for sym in ["SPY", "QQQ", "EFA", "EEM", "IWM", "GLD", "IEF"] if sym in p["idx"]]
        return {sym: 1.0 / len(assets) for sym in assets} if assets else {"BIL": 1.0}
    symbol = benchmark.replace("_buy_hold", "").replace("_cash_proxy", "")
    return {symbol: 1.0} if symbol in p["idx"] else {}


def simulate(p: dict[str, Any], start: int, horizon: int, variant: str | None, benchmark: str | None = None) -> dict[str, Any]:
    equity = STARTING_EQUITY
    peak = equity
    max_drawdown = 0.0
    weights: dict[str, float] = {}
    last_month = None
    stop_offset = None
    target300 = None
    target400 = None
    bil_weight_sum = 0.0
    bil_days = 0
    for offset in range(1, horizon + 1):
        today = start + offset
        signal = today - 1
        month = int(p["months"][today])
        if month != last_month:
            new_weights = benchmark_weights(p, signal, benchmark) if benchmark else weights_for_variant(p, signal, variant or "")
            turnover = sum(abs(new_weights.get(sym, 0.0) - weights.get(sym, 0.0)) for sym in set(new_weights) | set(weights))
            equity -= equity * turnover * SLIPPAGE
            weights = new_weights
            last_month = month
        bil_weight_sum += weights.get("BIL", 0.0)
        bil_days += 1
        daily_return = sum(weight * float(p["returns"][today, p["idx"][sym]]) for sym, weight in weights.items() if sym in p["idx"])
        equity *= 1.0 + daily_return
        peak = max(peak, equity)
        max_drawdown = min(max_drawdown, equity - peak)
        profit = equity - STARTING_EQUITY
        if stop_offset is None and profit <= STOP_DOLLARS:
            stop_offset = offset
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
        "total_return": equity / STARTING_EQUITY - 1.0,
        "max_drawdown": max_drawdown,
        "absolute_600_stop_hit": stop_offset is not None,
        "target_300_before_stop": bool(target300 is not None and (stop_offset is None or target300 <= stop_offset)),
        "target_400_before_stop": bool(target400 is not None and (stop_offset is None or target400 <= stop_offset)),
        "days_to_300": (dates[start + target300] - dates[start]).days if target300 is not None else "",
        "days_to_400": (dates[start + target400] - dates[start]).days if target400 is not None else "",
        "bil_weight_average": bil_weight_sum / bil_days if bil_days else 0.0,
    }


def sample_starts(length: int, horizon: int) -> list[int]:
    starts = list(range(252, length - horizon))
    if len(starts) <= MAX_WINDOWS_PER_HORIZON:
        return starts
    return sorted(set(int(x) for x in np.linspace(starts[0], starts[-1], MAX_WINDOWS_PER_HORIZON)))


def summarize(results: pd.DataFrame, variant: str, horizon: int) -> dict[str, Any]:
    subset = results[(results["strategy_id"] == variant) & (results["horizon"] == horizon)]
    if subset.empty:
        return {"strategy_id": variant, "horizon": horizon, "validation_status": "evidence_missing"}
    median_profit = float(subset["profit_dollars"].median())
    worst_drawdown = float(subset["max_drawdown"].min())
    median_drawdown = float(subset["max_drawdown"].median())
    return {
        "strategy_id": variant,
        "horizon": horizon,
        "validation_status": "complete",
        "window_count": int(len(subset)),
        "final_equity_mean": float(subset["final_equity"].mean()),
        "final_equity_median": float(subset["final_equity"].median()),
        "final_equity_75th_percentile": float(subset["final_equity"].quantile(0.75)),
        "final_equity_90th_percentile": float(subset["final_equity"].quantile(0.90)),
        "best_window_final_equity": float(subset["final_equity"].max()),
        "worst_window_final_equity": float(subset["final_equity"].min()),
        "average_profit_dollars": float(subset["profit_dollars"].mean()),
        "median_profit_dollars": median_profit,
        "total_return_median": float(subset["total_return"].median()),
        "target_300_before_stop_rate": float(subset["target_300_before_stop"].mean()),
        "target_400_before_stop_rate": float(subset["target_400_before_stop"].mean()),
        "days_to_300": float(pd.to_numeric(subset["days_to_300"], errors="coerce").median()) if subset["days_to_300"].astype(str).ne("").any() else "",
        "days_to_400": float(pd.to_numeric(subset["days_to_400"], errors="coerce").median()) if subset["days_to_400"].astype(str).ne("").any() else "",
        "max_drawdown_median": median_drawdown,
        "max_drawdown_worst": worst_drawdown,
        "absolute_600_stop_hit_rate": float(subset["absolute_600_stop_hit"].mean()),
        "trailing_drawdown_stop_hit_rate": "not_supported",
        "loss_window_rate": float((subset["profit_dollars"] < 0).mean()),
        "worst_loss_dollars": float(subset["profit_dollars"].min()),
        "profit_to_worst_drawdown_ratio": abs(median_profit / worst_drawdown) if worst_drawdown else "",
        "profit_to_median_drawdown_ratio": abs(median_profit / median_drawdown) if median_drawdown else "",
        "bil_weight_average": float(subset["bil_weight_average"].mean()),
    }


def full_period_returns(p: dict[str, Any], variant: str | None, benchmark: str | None = None) -> pd.Series:
    equity = STARTING_EQUITY
    weights: dict[str, float] = {}
    last_month = None
    values = []
    for today in range(253, len(p["close"])):
        signal = today - 1
        month = int(p["months"][today])
        if month != last_month:
            weights = benchmark_weights(p, signal, benchmark) if benchmark else weights_for_variant(p, signal, variant or "")
            last_month = month
        equity *= 1.0 + sum(weight * float(p["returns"][today, p["idx"][sym]]) for sym, weight in weights.items() if sym in p["idx"])
        values.append(equity)
    return pd.Series(values, index=p["close"].index[253:]).pct_change().dropna()


def score_and_verdict(summary: dict[str, Any], overlap: dict[str, Any], missing_count: int) -> tuple[float, str, str]:
    if summary.get("validation_status") != "complete":
        return 0.0, "reject", "evidence_missing"
    profit = min(40.0, max(0.0, float(summary["median_profit_dollars"]) / 300 * 14 + float(summary["target_300_before_stop_rate"]) * 12 + float(summary["target_400_before_stop_rate"]) * 8 + max(0.0, (float(summary["final_equity_90th_percentile"]) - 3000) / 500 * 6)))
    risk = min(25.0, (10 if float(summary["absolute_600_stop_hit_rate"]) == 0 else 0) + max(0.0, 10 * (1 + float(summary["max_drawdown_worst"]) / 600)) + max(0.0, 5 * (1 + float(summary["worst_loss_dollars"]) / 600)))
    max_corr = float(overlap.get("max_abs_available_correlation") or 1.0)
    additive = max(0.0, 25.0 * (1.0 - min(max_corr, 1.0)))
    bil_heavy = float(summary.get("bil_weight_average") or 0.0) >= 0.55 and float(summary["target_300_before_stop_rate"]) < 0.20
    score = max(0.0, profit + risk + additive + 10.0 - min(10.0, missing_count * 2.0))
    if missing_count:
        score -= 20
    if bil_heavy:
        score -= 25
    if float(summary["absolute_600_stop_hit_rate"]) > 0 or float(summary["max_drawdown_worst"]) <= STOP_DOLLARS:
        score -= 30
        return max(0.0, score), "weak", "too_risky"
    if float(summary["target_300_before_stop_rate"]) < 0.10 and float(summary["median_profit_dollars"]) < 100:
        score -= 25
        return max(0.0, score), "weak", "too_slow"
    if max_corr >= 0.85:
        score -= 25
        verdict = "duplicate_or_near_duplicate"
    elif score >= 70 and float(summary["target_300_before_stop_rate"]) >= 0.25 and not bil_heavy:
        verdict = "promotion_review_candidate"
    else:
        verdict = "watchlist"
    label = "strong_candidate" if score >= 80 else "possible_candidate" if score >= 65 else "watchlist" if score >= 45 else "weak" if score >= 25 else "reject"
    return max(0.0, min(100.0, score)), label, verdict


def update_registry(registry: dict[str, Any], verdicts: list[dict[str, Any]], family_verdict: str, next_action: str, output_dir: str) -> dict[str, Any]:
    updated = deepcopy(registry)
    updated.setdefault("strategies", [])
    rows = rows_by_id(updated)
    family_row = rows.get(FAMILY_ID)
    if family_row and family_row.get("paper_forward_active") is not True:
        family_row["status"] = family_verdict
        family_row["current_status"] = family_verdict
        family_row["family_verdict"] = family_verdict
        family_row["allowed_next_action"] = next_action
        family_row["next_allowed_action"] = next_action
        family_row["allowed_next_actions"] = [next_action]
        family_row["latest_evidence_path"] = output_dir
        family_row["paper_forward_active"] = False
        family_row["real_money_recommendation"] = False
        family_row["candidate_exhaustive_run"] = False
    for verdict in verdicts:
        row = rows.get(verdict["strategy_id"])
        if row is None:
            row = {
                "id": verdict["strategy_id"],
                "display_name": verdict["strategy_id"],
                "lane": "profit_exploration",
                "instrument_family": "ETF",
                "strategy_family": FAMILY_ID,
                "version": "v1",
                "parent_id": FAMILY_ID,
                "credibility_tier": "tier2_exploratory",
                "role": "dual_momentum_research_sample_row",
                "rules_frozen": True,
                "implementation_status": "implemented_research_sample",
                "data_source": "yfinance_compatible_adjusted_daily_etf_wrapper_data",
                "evidence_source": "dual_momentum_paa_etf_wrapper_research_sample",
                "promotion_requirements": "promotion review required before any candidate validation",
                "demotion_or_kill_criteria": "risk breach, duplicate exposure, too slow, or insufficient evidence",
                "notes": "Exploratory non-final research_sample only.",
                "strategy_id": verdict["strategy_id"],
                "family": FAMILY_ID,
                "instrument_lane": "ETF",
                "evidence_tier": "research_sample",
                "risk_framework_status": "research_only",
                "promotion_blockers": "exploratory_non_final;no_real_money_path",
                "evidence_needed": "promotion review if candidate",
                "duplicate_of": "",
                "blocked_reason": "",
            }
            updated["strategies"].append(row)
            rows[verdict["strategy_id"]] = row
        row["status"] = verdict["strategy_verdict"]
        row["current_status"] = verdict["strategy_verdict"]
        row["strategy_verdict"] = verdict["strategy_verdict"]
        row["family_verdict"] = family_verdict
        row["latest_known_result_summary"] = f"Fast exploratory dual momentum/PAA ETF-wrapper research_sample verdict: {verdict['strategy_verdict']}. Exploratory non-final evidence only."
        row["allowed_next_action"] = PROMOTION_ACTION if verdict["strategy_verdict"] == "promotion_review_candidate" else next_action
        row["next_allowed_action"] = row["allowed_next_action"]
        row["allowed_next_actions"] = [row["allowed_next_action"]]
        row["latest_evidence_path"] = output_dir
        row["paper_forward_active"] = False
        row["paper_forward_allowed_by_risk_framework"] = False
        row["real_money_recommendation"] = False
        row["candidate_exhaustive_run"] = False
        row["candidate_exhaustive_recommended"] = False
        row["promotion_review_required"] = verdict["strategy_verdict"] == "promotion_review_candidate"
        row["promotion_decision"] = verdict["strategy_verdict"]
        row["promotion_reason"] = verdict["reason"]
        row["primary_failure_mode"] = "duplicate_or_speed_or_bil_gate"
        row["duplication_risk"] = "requires_review" if verdict["strategy_verdict"] != "duplicate_or_near_duplicate" else "duplicate_or_near_duplicate"
        row["risk_budget_status"] = "research_sample_screened"
        row["forbidden_next_actions"] = sorted(set(row.get("forbidden_next_actions") or []) | {"paper_forward_activation", "real_money_recommendation", "broker_integration", "live_orders", "order_placement", "run_candidate_exhaustive_without_promotion_review"})
    updated.setdefault("registry", {})["last_updated_utc"] = now_utc()
    return updated


def create_packet(output_dir: Path) -> Path:
    packet = output_dir / f"{FAMILY_ID}_research_sample_packet.zip"
    if packet.exists():
        packet.unlink()
    with zipfile.ZipFile(packet, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(output_dir.iterdir()):
            if path.is_file() and path.name != packet.name:
                zf.write(path, path.name)
    return packet


def run_research_sample(root: Path = ROOT, downloader: Downloader | None = None, allow_download: bool = True, update_registry_file: bool = True) -> dict[str, Any]:
    registry_path = root / REGISTRY_PATH
    registry = load_yaml(registry_path)
    ready, mismatches = state_is_ready(root, registry)
    if not ready:
        raise RuntimeError("; ".join(mismatches))
    before_protected = protected_snapshot(registry)
    output_dir = root / OUTPUT_DIR
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    qa_rows, download_rows, provider_api_called, downloaded, failed = ensure_symbol_data(root, APPROVED_SYMBOLS, downloader, allow_download)
    included = [row["symbol"] for row in qa_rows if row["inclusion_decision"] == "include"]
    missing_symbols = [row["symbol"] for row in qa_rows if row["inclusion_decision"] != "include"]
    close_map = {symbol: read_close(root, symbol) for symbol in included}
    close = pd.concat([series for series in close_map.values() if series is not None], axis=1, join="inner").dropna().sort_index() if close_map else pd.DataFrame()
    window_rows: list[dict[str, Any]] = []
    rolling_summary: list[dict[str, Any]] = []
    benchmark_rows_out: list[dict[str, Any]] = []
    duplicate_rows: list[dict[str, Any]] = []
    score_rows: list[dict[str, Any]] = []
    verdict_rows: list[dict[str, Any]] = []
    variant_results: list[dict[str, Any]] = []

    required_core_available = all(symbol in close.columns for symbol in CORE_SYMBOLS)
    if close.empty or len(close) < 432 or not required_core_available:
        family_verdict = "needs_more_data"
        next_action = NEXT_LANE_ACTION
        for variant in VARIANT_IDS:
            verdict_rows.append({"strategy_id": variant, "strategy_verdict": "evidence_missing", "reason": "required symbols unavailable or insufficient common history", "next_allowed_action": next_action})
            score_rows.append({"strategy_id": variant, "profit_first_score": 0, "score_label": "reject", "strategy_verdict": "evidence_missing"})
    else:
        p = prepared(close)
        for variant in VARIANT_IDS:
            for horizon in HORIZONS:
                for start in sample_starts(len(close), horizon):
                    row = simulate(p, start, horizon, variant)
                    row.update({"strategy_id": variant, "horizon": horizon, "sampled_results_are_final": False, "exploratory_results_are_final": False})
                    window_rows.append(row)
        window_frame = pd.DataFrame(window_rows)
        for variant in VARIANT_IDS:
            for horizon in HORIZONS:
                rolling_summary.append(summarize(window_frame, variant, horizon))
        bench_ids = ["SPY_200d", "equal_weight_tactical_basket"] + [f"{symbol}_buy_hold" for symbol in ["SPY", "QQQ", "GLD", "BIL", "IEF", "TLT", "AGG"] if symbol in close.columns]
        for variant in VARIANT_IDS:
            variant_returns = full_period_returns(p, variant)
            corr_values: dict[str, float] = {}
            for benchmark in bench_ids:
                bench_returns = full_period_returns(p, None, benchmark=benchmark)
                aligned = pd.concat([variant_returns.rename("variant"), bench_returns.rename("benchmark")], axis=1).dropna()
                corr_values[benchmark] = float(aligned["variant"].corr(aligned["benchmark"])) if len(aligned) > 5 else np.nan
            max_corr = max([abs(value) for value in corr_values.values() if np.isfinite(value)] or [1.0])
            summary180 = next(row for row in rolling_summary if row["strategy_id"] == variant and row["horizon"] == 180)
            bil_heavy = float(summary180.get("bil_weight_average") or 0.0) >= 0.55
            duplicate_label = "duplicate_or_near_duplicate" if max_corr >= 0.85 else "not_proven_duplicate"
            additive_label = "possible_additive" if max_corr < 0.70 and not bil_heavy else "weak_or_unclear_additive"
            duplicate_rows.append(
                {
                    "strategy_id": variant,
                    "correlation_with_active_combo": "unavailable",
                    "correlation_with_vm_quality": "unavailable",
                    "correlation_with_dsr_equal_weight": "unavailable",
                    "correlation_with_gror": "unavailable",
                    "correlation_with_SPY_200d": corr_values.get("SPY_200d", ""),
                    "correlation_with_SPY": corr_values.get("SPY_buy_hold", ""),
                    "correlation_with_QQQ": corr_values.get("QQQ_buy_hold", ""),
                    "correlation_with_GLD": corr_values.get("GLD_buy_hold", ""),
                    "correlation_with_BIL": corr_values.get("BIL_buy_hold", ""),
                    "target_window_overlap": "not_computed_in_fast_sample",
                    "drawdown_window_overlap": "not_computed_in_fast_sample",
                    "duplicate_risk_label": duplicate_label,
                    "additive_value_label": additive_label,
                    "BIL_heavy_behavior_label": "bil_heavy" if bil_heavy else "not_bil_heavy",
                    "max_abs_available_correlation": max_corr,
                }
            )
            score, label, verdict = score_and_verdict(summary180, duplicate_rows[-1], len(missing_symbols))
            if bil_heavy and verdict == "watchlist":
                verdict = "too_slow"
            score_rows.append({"strategy_id": variant, "profit_first_score": round(score, 2), "score_label": label, "strategy_verdict": verdict})
            verdict_rows.append({"strategy_id": variant, "strategy_verdict": verdict, "reason": f"score={score:.2f}; duplicate={duplicate_label}; bil_heavy={bil_heavy}", "next_allowed_action": PROMOTION_ACTION if verdict == "promotion_review_candidate" else NEXT_LANE_ACTION})
            variant_results.append({**summary180, "profit_opportunity_score": round(score, 2), "strategy_verdict": verdict, "BIL_heavy_behavior_label": "bil_heavy" if bil_heavy else "not_bil_heavy"})
            for benchmark in bench_ids:
                bench_results = [simulate(p, start, 180, None, benchmark=benchmark) for start in sample_starts(len(close), 180)]
                bench_median = float(pd.Series([item["final_equity"] for item in bench_results]).median()) if bench_results else np.nan
                benchmark_rows_out.append({"strategy_id": variant, "benchmark_id": benchmark, "horizon": 180, "delta_median_final_equity": float(summary180["final_equity_median"]) - bench_median if np.isfinite(bench_median) else "", "comparison_status": "available" if np.isfinite(bench_median) else "unavailable"})
        if any(row["strategy_verdict"] == "promotion_review_candidate" for row in verdict_rows):
            family_verdict = "promotion_review_candidate_family"
            next_action = PROMOTION_ACTION
        elif all(row["strategy_verdict"] in {"too_slow", "duplicate_or_near_duplicate", "reject"} for row in verdict_rows):
            family_verdict = "reject_family"
            next_action = NEXT_LANE_ACTION
        else:
            family_verdict = "watchlist_family"
            next_action = NEXT_LANE_ACTION

    missing_rows = [{"symbol": row["symbol"], "reason": row["reason_for_exclusion"]} for row in qa_rows if row["inclusion_decision"] != "include"]
    updated_registry = update_registry(registry, verdict_rows, family_verdict, next_action, str(output_dir))
    active_unchanged = before_protected == protected_snapshot(updated_registry)
    if update_registry_file:
        registry_path.write_text(yaml.safe_dump(updated_registry, sort_keys=False, width=140), encoding="utf-8")

    consistency = {
        "research_sample_completed": True,
        "exploratory_non_final": True,
        "no_direct_futures": True,
        "no_options": True,
        "no_forex": True,
        "no_crypto": True,
        "no_intraday": True,
        "no_leverage_added_by_system": True,
        "no_shorting": True,
        "no_broker_path_added": True,
        "no_live_order_path_added": True,
        "no_real_money_recommendation": True,
        "no_candidate_exhaustive_run": True,
        "no_paper_forward_activation": True,
        "active_observations_unchanged": active_unchanged,
        "data_downloaded": bool(downloaded),
        "provider_api_called": provider_api_called,
        "downloaded_symbols": downloaded,
        "missing_symbols": missing_symbols,
        "family_verdict": family_verdict,
        "next_action": next_action,
        "consistency_passed": False,
    }
    consistency["consistency_passed"] = all(value is True for key, value in consistency.items() if key.startswith("no_")) and active_unchanged
    manifest = {
        "created_at_utc": now_utc(),
        "family_id": FAMILY_ID,
        "validation_mode": "fast_exploratory_research_sample",
        "sampled_results_are_final": False,
        "exploratory_results_are_final": False,
        "approved_symbols": APPROVED_SYMBOLS,
        "downloaded_symbols": downloaded,
        "provider_api_called": provider_api_called,
        "data_downloaded": bool(downloaded),
        "family_verdict": family_verdict,
        "next_action": next_action,
        **FORBIDDEN_FLAGS,
    }

    write_csv(output_dir / f"{FAMILY_ID}_data_quality.csv", qa_rows, list(qa_rows[0].keys()))
    write_csv(output_dir / f"{FAMILY_ID}_missing_symbols.csv", missing_rows, ["symbol", "reason"])
    write_csv(output_dir / f"{FAMILY_ID}_strategy_verdicts.csv", verdict_rows, ["strategy_id", "strategy_verdict", "reason", "next_allowed_action"])
    write_csv(output_dir / f"{FAMILY_ID}_variant_results.csv", variant_results, sorted({k for row in variant_results for k in row}) if variant_results else ["strategy_id", "validation_status"])
    write_csv(output_dir / f"{FAMILY_ID}_rolling_summary.csv", rolling_summary, sorted({k for row in rolling_summary for k in row}) if rolling_summary else ["strategy_id", "horizon", "validation_status"])
    write_csv(output_dir / f"{FAMILY_ID}_benchmark_comparison.csv", benchmark_rows_out, ["strategy_id", "benchmark_id", "horizon", "delta_median_final_equity", "comparison_status"])
    write_csv(output_dir / f"{FAMILY_ID}_profit_first_scores.csv", score_rows, ["strategy_id", "profit_first_score", "score_label", "strategy_verdict"])
    write_csv(output_dir / f"{FAMILY_ID}_duplicate_overlap.csv", duplicate_rows, sorted({k for row in duplicate_rows for k in row}) if duplicate_rows else ["strategy_id", "duplicate_risk_label"])
    if window_rows:
        pd.DataFrame(window_rows).to_csv(output_dir / f"{FAMILY_ID}_window_results.csv", index=False)
    write_csv(output_dir / f"{FAMILY_ID}_failure_modes.csv", [{"failure_mode": "bil_heavy_behavior", "observed": any(row.get("BIL_heavy_behavior_label") == "bil_heavy" for row in variant_results)}, {"failure_mode": "duplicate_or_near_duplicate", "observed": any(row["strategy_verdict"] == "duplicate_or_near_duplicate" for row in verdict_rows)}], ["failure_mode", "observed"])
    (output_dir / f"{FAMILY_ID}_bil_heavy_behavior_review.md").write_text("# BIL-Heavy Behavior Review\n\n" + "\n".join(f"- `{row.get('strategy_id')}`: `{row.get('BIL_heavy_behavior_label', '')}` avg BIL `{row.get('bil_weight_average', '')}`" for row in variant_results) + "\n", encoding="utf-8")
    (output_dir / f"{FAMILY_ID}_family_verdict.md").write_text(f"# Family Verdict\n\nFamily verdict: `{family_verdict}`\n\nNext action: `{next_action}`\n", encoding="utf-8")
    (output_dir / f"{FAMILY_ID}_decision.md").write_text(f"# Decision\n\nFast exploratory research_sample completed. Family verdict: `{family_verdict}`. Results are exploratory and non-final.\n", encoding="utf-8")
    (output_dir / f"{FAMILY_ID}_next_action.md").write_text(f"# Next Action\n\n`{next_action}`\n", encoding="utf-8")
    (output_dir / f"{FAMILY_ID}_research_sample_summary.md").write_text(f"# Dual Momentum PAA ETF Wrapper Research Sample\n\nExploratory non-final research_sample for ETF/fund wrappers only.\n\nFamily verdict: `{family_verdict}`\n\nNext action: `{next_action}`\n\nDownloaded symbols: `{', '.join(downloaded) or 'none'}`\n\nMissing symbols: `{', '.join(missing_symbols) or 'none'}`\n", encoding="utf-8")
    write_json(output_dir / f"{FAMILY_ID}_manifest.json", manifest)
    write_json(output_dir / f"{FAMILY_ID}_consistency_check.json", consistency)
    packet = create_packet(output_dir)
    return {
        "output_dir": str(output_dir),
        "packet": str(packet),
        "family_verdict": family_verdict,
        "next_action": next_action,
        "downloaded_symbols": downloaded,
        "missing_symbols": missing_symbols,
        "strategy_verdicts": verdict_rows,
        "scores": score_rows,
        "consistency": consistency,
    }


def main() -> int:
    result = run_research_sample(ROOT)
    print(f"dual_momentum_research_sample_latest_dir={result['output_dir']}")
    print(f"family_verdict={result['family_verdict']}")
    print(f"next_action={result['next_action']}")
    print(f"downloaded_symbols={','.join(result['downloaded_symbols']) or 'none'}")
    print(f"missing_symbols={','.join(result['missing_symbols']) or 'none'}")
    print(f"consistency_passed={str(result['consistency']['consistency_passed']).lower()}")
    return 0 if result["consistency"]["consistency_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
