from __future__ import annotations

import csv
import json
import shutil
import zipfile
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml


ROOT = Path(__file__).resolve().parent
TARGET_ID = "dsr_sector_top2_momentum_200d_bil_v1"
FAMILY = "defensive_sector_rotation_etf"
ACTIVE_DSR_ID = "paper_forward_dsr_sector_equal_weight_defensive_filter_v1"
VM_QUALITY_ID = "paper_forward_vm_quality_lowvol_proxy_v1"
SPY_200D_ID = "SPY_200d_trend_model"
TOP3_ID = "dsr_sector_top3_momentum_defensive_cash_v1"
REGISTRY_PATH = Path("strategy_lab") / "strategy_registry.yaml"
OUTPUT_DIR = Path("evidence") / "promotion_reviews" / TARGET_ID / "latest"
STARTING_EQUITY = 3000.0
STOP_DOLLARS = -600.0
SLIPPAGE = 0.0005
MAX_WINDOWS_PER_HORIZON = 5
HORIZONS = [90, 180]
REQUIRED_HORIZONS = [90, 180]
SECTOR_SYMBOLS = ["XLK", "XLF", "XLE", "XLV", "XLY", "XLP", "XLU", "XLI", "XLB", "XLC"]
REQUIRED_CACHE_SYMBOLS = [*SECTOR_SYMBOLS, "BIL"]
OPTIONAL_BENCHMARK_SYMBOLS = ["SPY"]
DATA_HISTORY_MODE = "per_asset_availability"
ALLOWED_DECISIONS = {
    "promote_to_candidate_exhaustive_queue",
    "promotion_review_required",
    "keep_watchlist",
    "mark_duplicate_or_near_duplicate",
    "mark_too_risky",
    "mark_too_slow",
    "evidence_missing",
    "reject",
}
NEXT_ACTIONS = {
    "promote_to_candidate_exhaustive_queue": "create_candidate_exhaustive_prompt_for_dsr_sector_top2_momentum_200d_bil_v1",
    "evidence_missing": "repair_dsr_top2_promotion_review_diagnostics",
    "keep_watchlist": "keep_dsr_sector_top2_momentum_200d_bil_v1_on_watchlist",
    "mark_duplicate_or_near_duplicate": "archive_dsr_sector_top2_momentum_200d_bil_v1_as_dsr_duplicate_diagnostic",
    "mark_too_risky": "mark_dsr_sector_top2_momentum_200d_bil_v1_too_risky",
    "reject": "reject_dsr_sector_top2_momentum_200d_bil_v1",
}
FORBIDDEN_NEXT_ACTIONS = [
    "broker_integration",
    "call_provider_api",
    "download_data",
    "grid_search",
    "live_orders",
    "order_placement",
    "paper_forward_activation",
    "paper_forward_checkpoint",
    "paper_forward_review",
    "place_live_orders",
    "promote_to_real_money",
    "real_money_recommendation",
    "run_candidate_exhaustive",
    "run_profit_exploration",
    "run_research_sample",
    "skip_gates",
    "tune_parameters",
    "use_crypto",
    "use_forex",
    "use_futures_contract_logic",
    "use_individual_stock_logic",
    "use_intraday_logic",
    "use_leverage",
    "use_margin",
    "use_options",
    "use_shorting",
]


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
        if row_id in {ACTIVE_DSR_ID, VM_QUALITY_ID, SPY_200D_ID, "current_no_cash_proxy_alpha_AB"} or row.get("paper_forward_active") is True
    }


def cache_path(root: Path, symbol: str) -> Path:
    return root / "data" / "cache" / f"{symbol}.csv"


def qa_cache(root: Path, symbol: str) -> dict[str, Any]:
    path = cache_path(root, symbol)
    row = {
        "symbol": symbol,
        "required": symbol in REQUIRED_CACHE_SYMBOLS,
        "cache_available": path.exists(),
        "cache_path": str(path),
        "qa_status": "missing",
        "first_date": "",
        "last_date": "",
        "row_count": 0,
        "warmup_sufficiency": False,
        "missing_reason": "cache missing",
    }
    if not path.exists():
        return row
    try:
        frame = pd.read_csv(path)
    except Exception as exc:
        row["qa_status"] = "failed"
        row["missing_reason"] = f"cache read failed: {exc}"
        return row
    if "date" not in frame or "adj_close" not in frame:
        row["qa_status"] = "failed"
        row["missing_reason"] = "date or adj_close missing"
        return row
    dates = pd.to_datetime(frame["date"], errors="coerce").dt.tz_localize(None)
    close = pd.to_numeric(frame["adj_close"], errors="coerce")
    valid = pd.DataFrame({"date": dates, "adj_close": close}).dropna().sort_values("date").drop_duplicates("date")
    duplicate_dates = int(dates.dropna().duplicated().sum())
    row.update(
        {
            "first_date": "" if valid.empty else str(valid["date"].min().date()),
            "last_date": "" if valid.empty else str(valid["date"].max().date()),
            "row_count": int(len(valid)),
            "warmup_sufficiency": int(len(valid)) >= 252,
        }
    )
    passed = bool(len(valid) >= 252 and duplicate_dates == 0 and valid["adj_close"].notna().any())
    row["qa_status"] = "passed" if passed else "failed"
    row["missing_reason"] = "" if passed else "insufficient rows, duplicate dates, or empty adjusted close"
    return row


def cache_status(root: Path) -> list[dict[str, Any]]:
    return [qa_cache(root, symbol) for symbol in REQUIRED_CACHE_SYMBOLS + OPTIONAL_BENCHMARK_SYMBOLS]


def read_close(root: Path, symbol: str) -> pd.Series | None:
    qa = qa_cache(root, symbol)
    if qa["qa_status"] != "passed":
        return None
    frame = pd.read_csv(cache_path(root, symbol))
    dates = pd.to_datetime(frame["date"], errors="coerce").dt.tz_localize(None)
    close = pd.to_numeric(frame["adj_close"], errors="coerce")
    series = pd.DataFrame({"date": dates, symbol: close}).dropna().sort_values("date").drop_duplicates("date")
    return series.set_index("date")[symbol].astype(float) if not series.empty else None


def create_packet(directory: Path, name: str) -> Path:
    packet = directory / name
    if packet.exists():
        packet.unlink()
    with zipfile.ZipFile(packet, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(directory.iterdir()):
            if path.is_file() and path.name != packet.name:
                zf.write(path, path.name)
    return packet


def state_mismatches(root: Path, registry: dict[str, Any]) -> list[str]:
    rows = rows_by_id(registry)
    mismatches: list[str] = []
    target = rows.get(TARGET_ID)
    active_dsr = rows.get(ACTIVE_DSR_ID)
    if not target:
        mismatches.append(f"{TARGET_ID} missing from registry")
    else:
        if target.get("paper_forward_active") is not False:
            mismatches.append(f"{TARGET_ID} paper_forward_active is not false")
        if target.get("real_money_recommendation") is not False:
            mismatches.append(f"{TARGET_ID} real_money_recommendation is not false")
        if target.get("candidate_exhaustive_run") is not False:
            mismatches.append(f"{TARGET_ID} candidate_exhaustive_run is not false")
    if not active_dsr:
        mismatches.append(f"{ACTIVE_DSR_ID} missing from registry")
    else:
        if active_dsr.get("paper_forward_active") is not True:
            mismatches.append(f"{ACTIVE_DSR_ID} is not active")
        if active_dsr.get("rules_frozen") is not True:
            mismatches.append(f"{ACTIVE_DSR_ID} rules_frozen is not true")
        if active_dsr.get("real_money_recommendation") is not False:
            mismatches.append(f"{ACTIVE_DSR_ID} real_money_recommendation is not false")
    readiness = root / "evidence" / "approved_etf_cache_readiness" / "latest" / "prior_result_data_readiness_audit.csv"
    if readiness.exists():
        rows_by_result = {row["result_id"]: row for row in csv.DictReader(readiness.open(encoding="utf-8"))}
        if rows_by_result.get(f"{TARGET_ID}_promotion_review", {}).get("classification") != "needs_rerun_after_cache_bootstrap":
            mismatches.append("cache-readiness audit does not recommend DSR Top2 rerun")
    return mismatches


def target_rule_rows(common_start_warning: str) -> list[dict[str, Any]]:
    return [
        {"field": "strategy_id", "value": TARGET_ID, "source": "registry/prompt", "notes": "target row"},
        {"field": "family", "value": FAMILY, "source": "registry/prompt", "notes": "same family as active DSR equal-weight observation"},
        {"field": "rebalance", "value": "monthly", "source": "promotion_review_implementation", "notes": "fixed monthly rebalance"},
        {"field": "universe", "value": ";".join(REQUIRED_CACHE_SYMBOLS), "source": "prompt/cache", "notes": "sector ETFs plus BIL fallback"},
        {"field": "candidate_assets", "value": ";".join(SECTOR_SYMBOLS), "source": "prompt/cache", "notes": "BIL is fallback only"},
        {"field": "eligibility", "value": "sector ETF close > 200-day SMA", "source": "promotion_review_implementation", "notes": "per-asset availability"},
        {"field": "ranking", "value": "rank eligible sectors by 126-day return", "source": "promotion_review_implementation", "notes": "no recovered 126d/60d-vol implementation discrepancy found"},
        {"field": "allocation", "value": "top two eligible sectors at 50% each; one sector 50% sector/50% BIL; none 100% BIL", "source": "promotion_review_implementation", "notes": "fixed fallback"},
        {"field": "data_history_mode", "value": DATA_HISTORY_MODE, "source": "promotion_review_implementation", "notes": common_start_warning},
        {"field": "forbidden_mechanics", "value": "no leverage, margin, shorting, options, futures, forex, crypto, intraday, broker/live-order path", "source": "policy", "notes": "compliant by review design"},
    ]


def prepare_prices(root: Path) -> tuple[pd.DataFrame, list[str]]:
    close_map: dict[str, pd.Series] = {}
    missing: list[str] = []
    for symbol in REQUIRED_CACHE_SYMBOLS + OPTIONAL_BENCHMARK_SYMBOLS:
        series = read_close(root, symbol)
        if series is None:
            if symbol in REQUIRED_CACHE_SYMBOLS:
                missing.append(symbol)
            continue
        close_map[symbol] = series
    if missing:
        return pd.DataFrame(), missing
    close = pd.concat(close_map.values(), axis=1, join="outer").sort_index()
    return close, missing


def available_at(close: pd.DataFrame, symbol: str, t: int, lookback: int = 0) -> bool:
    if symbol not in close.columns or t - lookback < 0:
        return False
    return bool(pd.notna(close.iloc[t][symbol]) and pd.notna(close.iloc[t - lookback][symbol]))


def eligible(close: pd.DataFrame, symbol: str, t: int) -> bool:
    if symbol not in close.columns or t < 200:
        return False
    window = close[symbol].iloc[t - 199 : t + 1].dropna()
    if len(window) < 200 or pd.isna(close.iloc[t][symbol]):
        return False
    return bool(float(close.iloc[t][symbol]) > float(window.mean()))


def ret126(close: pd.DataFrame, symbol: str, t: int) -> float:
    if not available_at(close, symbol, t, 126):
        return float("nan")
    return float(close.iloc[t][symbol] / close.iloc[t - 126][symbol] - 1.0)


def add(weights: dict[str, float], symbol: str, amount: float) -> None:
    weights[symbol] = weights.get(symbol, 0.0) + amount


def strategy_weights(close: pd.DataFrame, t: int, strategy_id: str) -> dict[str, float]:
    eligible_sectors = [sym for sym in SECTOR_SYMBOLS if eligible(close, sym, t) and np.isfinite(ret126(close, sym, t))]
    ranked = sorted(eligible_sectors, key=lambda sym: ret126(close, sym, t), reverse=True)
    weights: dict[str, float] = {}
    if strategy_id == TARGET_ID:
        picks = ranked[:2]
        if len(picks) == 2:
            for pick in picks:
                add(weights, pick, 0.5)
        elif len(picks) == 1:
            add(weights, picks[0], 0.5)
            add(weights, "BIL", 0.5)
        else:
            add(weights, "BIL", 1.0)
    elif strategy_id == "dsr_sector_equal_weight_defensive_filter_v1":
        picks = ranked
        if len(picks) >= 3:
            for pick in picks:
                add(weights, pick, 1.0 / len(picks))
        elif picks:
            for pick in picks:
                add(weights, pick, 1.0 / 3.0)
            add(weights, "BIL", 1.0 - len(picks) / 3.0)
        else:
            add(weights, "BIL", 1.0)
    elif strategy_id == TOP3_ID:
        picks = ranked[:3]
        if picks:
            for pick in picks:
                add(weights, pick, 1.0 / 3.0)
            add(weights, "BIL", max(0.0, 1.0 - len(picks) / 3.0))
        else:
            add(weights, "BIL", 1.0)
    elif strategy_id == "raw_sector_equal_weight_basket":
        available = [sym for sym in SECTOR_SYMBOLS if available_at(close, sym, t, 1)]
        if available:
            for sym in available:
                add(weights, sym, 1.0 / len(available))
        else:
            add(weights, "BIL", 1.0)
    elif strategy_id == SPY_200D_ID:
        if "SPY" in close.columns and eligible(close, "SPY", t):
            add(weights, "SPY", 1.0)
        else:
            add(weights, "BIL", 1.0)
    elif strategy_id == "SPY_buy_hold":
        add(weights, "SPY", 1.0)
    elif strategy_id == "BIL_cash_proxy":
        add(weights, "BIL", 1.0)
    else:
        add(weights, "BIL", 1.0)
    return weights


def simulate(close: pd.DataFrame, start: int, horizon: int, strategy_id: str) -> dict[str, Any]:
    equity = STARTING_EQUITY
    peak = equity
    max_drawdown = 0.0
    weights: dict[str, float] = {}
    last_month = None
    stop = None
    target300 = None
    target400 = None
    months = np.array([dt.year * 12 + dt.month for dt in close.index], dtype=int)
    for offset in range(1, horizon + 1):
        today = start + offset
        signal = today - 1
        month = int(months[today])
        if month != last_month:
            new_weights = strategy_weights(close, signal, strategy_id)
            turnover = sum(abs(new_weights.get(sym, 0.0) - weights.get(sym, 0.0)) for sym in set(new_weights) | set(weights))
            equity -= equity * turnover * SLIPPAGE
            weights = new_weights
            last_month = month
        daily_return = 0.0
        for sym, weight in weights.items():
            if sym in close.columns and available_at(close, sym, today, 1):
                daily_return += weight * float(close.iloc[today][sym] / close.iloc[today - 1][sym] - 1.0)
        equity *= 1.0 + daily_return
        peak = max(peak, equity)
        max_drawdown = min(max_drawdown, equity - peak)
        profit = equity - STARTING_EQUITY
        if stop is None and profit <= STOP_DOLLARS:
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
        "profit_dollars": equity - STARTING_EQUITY,
        "max_drawdown": max_drawdown,
        "absolute_600_stop_hit": stop is not None,
        "target_300_before_stop": bool(target300 is not None and (stop is None or target300 <= stop)),
        "target_400_before_stop": bool(target400 is not None and (stop is None or target400 <= stop)),
    }


def sample_starts(close: pd.DataFrame, horizon: int) -> list[int]:
    starts = list(range(252, len(close) - horizon))
    if len(starts) <= MAX_WINDOWS_PER_HORIZON:
        return starts
    return sorted(set(int(x) for x in np.linspace(starts[0], starts[-1], MAX_WINDOWS_PER_HORIZON)))


def run_windows(close: pd.DataFrame, strategy_id: str, horizons: list[int] = HORIZONS) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for horizon in horizons:
        for start in sample_starts(close, horizon):
            rows.append(simulate(close, start, horizon, strategy_id))
    return rows


def summarize(rows: list[dict[str, Any]], strategy_id: str, horizon: int) -> dict[str, Any]:
    df = pd.DataFrame([row for row in rows if row["strategy_id"] == strategy_id and row["horizon"] == horizon])
    if df.empty:
        return {"strategy_id": strategy_id, "horizon": horizon, "validation_status": "missing_or_unavailable"}
    return {
        "strategy_id": strategy_id,
        "horizon": horizon,
        "window_count": int(len(df)),
        "median_final_equity": float(df["final_equity"].median()),
        "mean_final_equity": float(df["final_equity"].mean()),
        "p75_final_equity": float(df["final_equity"].quantile(0.75)),
        "p90_final_equity": float(df["final_equity"].quantile(0.90)),
        "best_final_equity": float(df["final_equity"].max()),
        "worst_final_equity": float(df["final_equity"].min()),
        "target_300_before_stop_rate": float(df["target_300_before_stop"].mean()),
        "target_400_before_stop_rate": float(df["target_400_before_stop"].mean()),
        "worst_drawdown": float(df["max_drawdown"].min()),
        "median_drawdown": float(df["max_drawdown"].median()),
        "stop_hit_rate": float(df["absolute_600_stop_hit"].mean()),
        "worst_loss_window": float(df["profit_dollars"].min()),
        "median_profit_dollars": float(df["profit_dollars"].median()),
    }


def full_returns(close: pd.DataFrame, strategy_id: str) -> pd.Series:
    equity = STARTING_EQUITY
    weights: dict[str, float] = {}
    last_month = None
    values: list[float] = []
    dates: list[pd.Timestamp] = []
    months = np.array([dt.year * 12 + dt.month for dt in close.index], dtype=int)
    for today in range(253, len(close)):
        signal = today - 1
        month = int(months[today])
        if month != last_month:
            weights = strategy_weights(close, signal, strategy_id)
            last_month = month
        daily_return = 0.0
        for sym, weight in weights.items():
            if sym in close.columns and available_at(close, sym, today, 1):
                daily_return += weight * float(close.iloc[today][sym] / close.iloc[today - 1][sym] - 1.0)
        equity *= 1.0 + daily_return
        values.append(equity)
        dates.append(close.index[today])
    return pd.Series(values, index=dates).pct_change().dropna()


def window_overlap(rows_a: list[dict[str, Any]], rows_b: list[dict[str, Any]], horizon: int, field: str) -> float | str:
    a = pd.DataFrame([row for row in rows_a if row["horizon"] == horizon])
    b = pd.DataFrame([row for row in rows_b if row["horizon"] == horizon])
    if a.empty or b.empty:
        return "unavailable"
    merged = a[["window_start", field]].merge(b[["window_start", field]], on="window_start", suffixes=("_a", "_b"))
    if merged.empty:
        return "unavailable"
    if merged[f"{field}_a"].dtype == bool:
        both = (merged[f"{field}_a"] & merged[f"{field}_b"]).mean()
        return float(both)
    return float(merged[f"{field}_a"].corr(merged[f"{field}_b"]))


def common_start_warning(close: pd.DataFrame) -> str:
    firsts = {sym: close[sym].first_valid_index() for sym in SECTOR_SYMBOLS if sym in close}
    if not firsts:
        return "no sector history loaded"
    earliest = min(dt for dt in firsts.values() if dt is not None)
    latest = max(dt for dt in firsts.values() if dt is not None)
    removed_days = int((close.index >= earliest).sum() - (close.index >= latest).sum())
    shorter = sorted(sym for sym, dt in firsts.items() if dt == latest)
    if removed_days > 504:
        return f"per-asset availability used; common-start at {latest.date()} would remove about {removed_days} trading days because of shorter-history symbols such as {','.join(shorter)}"
    if latest > earliest:
        return f"per-asset availability used; common-start at {latest.date()} would remove about {removed_days} trading days because of shorter-history symbols such as {','.join(shorter)}"
    return "per-asset availability used; common-start history loss is not large"


def decide(summary180: dict[str, Any], delta_vs_dsr: float | str, corr_vs_dsr: float | str) -> tuple[str, str, bool]:
    if summary180.get("validation_status") == "missing_or_unavailable":
        return "evidence_missing", NEXT_ACTIONS["evidence_missing"], False
    if summary180["stop_hit_rate"] > 0 or summary180["worst_drawdown"] <= STOP_DOLLARS:
        return "mark_too_risky", NEXT_ACTIONS["mark_too_risky"], False
    if summary180["target_300_before_stop_rate"] < 0.10 and summary180["median_profit_dollars"] < 100:
        return "mark_too_slow", NEXT_ACTIONS["keep_watchlist"], False
    duplicate_like = isinstance(corr_vs_dsr, float) and corr_vs_dsr >= 0.85
    not_better = isinstance(delta_vs_dsr, float) and delta_vs_dsr <= 25
    if duplicate_like and not_better:
        return "mark_duplicate_or_near_duplicate", NEXT_ACTIONS["mark_duplicate_or_near_duplicate"], False
    profit_useful = summary180["target_300_before_stop_rate"] >= 0.25 and summary180["target_400_before_stop_rate"] >= 0.15 and summary180["median_final_equity"] >= 3300
    risk_ok = summary180["worst_drawdown"] > STOP_DOLLARS and summary180["stop_hit_rate"] == 0
    additive_ok = not duplicate_like or (isinstance(delta_vs_dsr, float) and delta_vs_dsr > 75)
    if profit_useful and risk_ok and additive_ok:
        return "promote_to_candidate_exhaustive_queue", NEXT_ACTIONS["promote_to_candidate_exhaustive_queue"], True
    return "keep_watchlist", NEXT_ACTIONS["keep_watchlist"], False


def fmt(value: Any) -> Any:
    if isinstance(value, float):
        return round(value, 4)
    return value


def build_review_payload(root: Path) -> dict[str, Any]:
    close, missing_symbols = prepare_prices(root)
    cache_rows = cache_status(root)
    if missing_symbols or close.empty:
        return {
            "cache_rows": cache_rows,
            "missing_symbols": missing_symbols,
            "diagnostics_available": False,
            "final_decision": "evidence_missing",
            "next_action": NEXT_ACTIONS["evidence_missing"],
            "candidate_exhaustive_recommended": False,
            "common_start_warning": "cache missing; per-asset availability not computed",
        }
    strategy_ids = [TARGET_ID, "dsr_sector_equal_weight_defensive_filter_v1", TOP3_ID, "raw_sector_equal_weight_basket", SPY_200D_ID, "SPY_buy_hold", "BIL_cash_proxy"]
    window_rows_by_strategy = {sid: run_windows(close, sid) for sid in strategy_ids}
    summaries = {sid: {h: summarize(window_rows_by_strategy[sid], sid, h) for h in HORIZONS} for sid in strategy_ids}
    summary180 = summaries[TARGET_ID][180]
    dsr_delta = summary180["median_final_equity"] - summaries["dsr_sector_equal_weight_defensive_filter_v1"][180]["median_final_equity"]
    returns_target = full_returns(close, TARGET_ID)
    returns_dsr = full_returns(close, "dsr_sector_equal_weight_defensive_filter_v1")
    aligned = pd.concat([returns_target.rename("target"), returns_dsr.rename("dsr")], axis=1).dropna()
    corr_vs_dsr = float(aligned["target"].corr(aligned["dsr"])) if len(aligned) > 5 else "unavailable"
    final_decision, next_action, candidate_recommended = decide(summary180, dsr_delta, corr_vs_dsr)
    return {
        "cache_rows": cache_rows,
        "missing_symbols": [],
        "diagnostics_available": True,
        "close": close,
        "window_rows_by_strategy": window_rows_by_strategy,
        "summaries": summaries,
        "final_decision": final_decision,
        "next_action": next_action,
        "candidate_exhaustive_recommended": candidate_recommended,
        "common_start_warning": common_start_warning(close),
        "corr_vs_dsr": corr_vs_dsr,
        "delta_vs_dsr": dsr_delta,
    }


def build_output_rows(payload: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    if not payload["diagnostics_available"]:
        missing_note = "Required sector ETF cache missing: " + ";".join(payload["missing_symbols"])
        missing = lambda metric: {"metric": metric, "value": "missing_or_unavailable", "evidence_source": "cache_missing_no_recompute", "notes": missing_note}
        return {
            "profit": [missing(metric) for metric in ["90d_median_final_equity", "180d_median_final_equity", "180d_mean_final_equity", "180d_p75_final_equity", "180d_p90_final_equity", "best_final_equity", "worst_final_equity", "target_300_before_stop_rate", "target_400_before_stop_rate", "delta_vs_dsr_equal_weight", "delta_vs_vm_quality", "delta_vs_active_combo", "delta_vs_SPY_200d", "delta_vs_SPY_buy_hold", "delta_vs_BIL"]],
            "risk": [missing(metric) for metric in ["90d_worst_drawdown", "180d_worst_drawdown", "median_drawdown", "stop_hit_rate", "risk_buffer_vs_minus_600", "worst_loss_window", "concentration_risk_notes", "drawdown_vs_dsr_equal_weight"]],
            "benchmark": [],
            "duplicate": [],
            "family": [],
            "scorecard": [],
            "target_window": [],
            "drawdown_window": [],
        }
    summaries = payload["summaries"]
    rows_by_strategy = payload["window_rows_by_strategy"]
    target90 = summaries[TARGET_ID][90]
    target180 = summaries[TARGET_ID][180]
    benchmark_specs = [
        ("active_combo", "", "unavailable_active_combo_series_not_in_scope"),
        (VM_QUALITY_ID, "", "unavailable_active_vm_rule_series_not_in_scope"),
        (ACTIVE_DSR_ID, "dsr_sector_equal_weight_defensive_filter_v1", "computed_proxy_from_cached_sector_etfs"),
        (SPY_200D_ID, SPY_200D_ID, "computed_from_cached_spy_bil"),
        ("SPY_buy_hold", "SPY_buy_hold", "computed_from_cached_spy"),
        ("BIL_cash_proxy", "BIL_cash_proxy", "computed_from_cached_bil"),
        ("raw_sector_equal_weight_basket", "raw_sector_equal_weight_basket", "computed_from_cached_sector_etfs"),
        ("dsr_sector_equal_weight_defensive_filter_v1", "dsr_sector_equal_weight_defensive_filter_v1", "computed_proxy_from_cached_sector_etfs"),
        (TOP3_ID, TOP3_ID, "computed_from_cached_sector_etfs"),
    ]
    benchmark_rows = []
    duplicate_rows = []
    returns_cache = {TARGET_ID: full_returns(payload["close"], TARGET_ID)}
    for bench, strategy_key, note in benchmark_specs:
        if bench in {"active_combo", VM_QUALITY_ID}:
            benchmark_rows.append({"benchmark_id": bench, "comparison_status": "unavailable", "strategy_metric": fmt(target180["median_final_equity"]), "benchmark_metric": "", "delta": "", "notes": note})
            duplicate_rows.append({"comparison_target": bench, "overlap_status": "unavailable", "duplicate_label": "unavailable", "correlation": "", "concentration_risk": "not_comparable", "target_window_overlap": "unavailable", "drawdown_window_overlap": "unavailable", "notes": note})
            continue
        bench_summary = summaries[strategy_key][180]
        delta = target180["median_final_equity"] - bench_summary["median_final_equity"]
        target_returns = returns_cache[TARGET_ID]
        if strategy_key not in returns_cache:
            returns_cache[strategy_key] = full_returns(payload["close"], strategy_key)
        bench_returns = returns_cache[strategy_key]
        aligned = pd.concat([target_returns.rename("target"), bench_returns.rename("bench")], axis=1).dropna()
        corr = float(aligned["target"].corr(aligned["bench"])) if len(aligned) > 5 else "unavailable"
        target_overlap = window_overlap(rows_by_strategy[TARGET_ID], rows_by_strategy[strategy_key], 180, "target_300_before_stop")
        drawdown_overlap = window_overlap(rows_by_strategy[TARGET_ID], rows_by_strategy[strategy_key], 180, "max_drawdown")
        duplicate_label = "near_duplicate" if isinstance(corr, float) and corr >= 0.85 else "not_proven_duplicate"
        benchmark_rows.append({"benchmark_id": bench, "comparison_status": "available", "strategy_metric": fmt(target180["median_final_equity"]), "benchmark_metric": fmt(bench_summary["median_final_equity"]), "delta": fmt(delta), "notes": note})
        duplicate_rows.append({"comparison_target": bench, "overlap_status": "available", "duplicate_label": duplicate_label, "correlation": fmt(corr), "concentration_risk": "top2_sector_concentration_vs_broader_dsr", "target_window_overlap": fmt(target_overlap), "drawdown_window_overlap": fmt(drawdown_overlap), "notes": note})
    family_rows = []
    for sid in ["dsr_sector_equal_weight_defensive_filter_v1", TARGET_ID, TOP3_ID, "dsr_defensive_sector_risk_off_rotation_v1", "dsr_sector_momentum_drawdown_guard_v1"]:
        if sid in summaries:
            s180 = summaries[sid][180]
            family_rows.append({"strategy_id": sid, "current_status": payload["final_decision"] if sid == TARGET_ID else "comparison_only", "evidence_source": "promotion_review_diagnostic_cached_etf_data", "180d_median_equity": fmt(s180["median_final_equity"]), "180d_target_300": fmt(s180["target_300_before_stop_rate"]), "180d_target_400": fmt(s180["target_400_before_stop_rate"]), "180d_worst_drawdown": fmt(s180["worst_drawdown"]), "stop_hit_rate": fmt(s180["stop_hit_rate"]), "duplicate_label": "same_family_comparison", "risk_label": "acceptable" if s180["worst_drawdown"] > STOP_DOLLARS and s180["stop_hit_rate"] == 0 else "risk_breach", "reason_for_status": "computed bounded promotion-review diagnostic", "next_action": payload["next_action"] if sid == TARGET_ID else ""})
        else:
            family_rows.append({"strategy_id": sid, "current_status": "missing_or_unavailable", "evidence_source": "not_found_in_current_cached_review", "180d_median_equity": "missing_or_unavailable", "180d_target_300": "missing_or_unavailable", "180d_target_400": "missing_or_unavailable", "180d_worst_drawdown": "missing_or_unavailable", "stop_hit_rate": "missing_or_unavailable", "duplicate_label": "not_assessed", "risk_label": "unavailable", "reason_for_status": "no implementation in bounded review", "next_action": ""})
    scorecard_rows = [
        {"criterion": "evidence_available", "value": True, "reference_or_threshold": "cached DSR sector ETFs QA-passed", "verdict": "pass", "notes": ""},
        {"criterion": "evidence_source", "value": "promotion_review_diagnostic_cached_etf_data", "reference_or_threshold": "labeled source", "verdict": "pass", "notes": "Bounded review only, not candidate_exhaustive."},
        {"criterion": "metrics_available", "value": True, "reference_or_threshold": "90d and 180d metrics", "verdict": "pass", "notes": ""},
        {"criterion": "target_300_before_stop", "value": fmt(target180["target_300_before_stop_rate"]), "reference_or_threshold": ">=0.25 for promotion consideration", "verdict": "pass" if target180["target_300_before_stop_rate"] >= 0.25 else "fail", "notes": ""},
        {"criterion": "target_400_before_stop", "value": fmt(target180["target_400_before_stop_rate"]), "reference_or_threshold": ">=0.15 for promotion consideration", "verdict": "pass" if target180["target_400_before_stop_rate"] >= 0.15 else "weak_pass", "notes": ""},
        {"criterion": "median_final_equity", "value": fmt(target180["median_final_equity"]), "reference_or_threshold": ">=3300 for promotion consideration", "verdict": "pass" if target180["median_final_equity"] >= 3300 else "weak_pass", "notes": ""},
        {"criterion": "worst_drawdown", "value": fmt(target180["worst_drawdown"]), "reference_or_threshold": "> -600", "verdict": "pass" if target180["worst_drawdown"] > STOP_DOLLARS else "fail", "notes": ""},
        {"criterion": "stop_hit_rate", "value": fmt(target180["stop_hit_rate"]), "reference_or_threshold": "0 preferred", "verdict": "pass" if target180["stop_hit_rate"] == 0 else "fail", "notes": ""},
        {"criterion": "drawdown_buffer", "value": fmt(target180["worst_drawdown"] - STOP_DOLLARS), "reference_or_threshold": "positive", "verdict": "pass" if target180["worst_drawdown"] > STOP_DOLLARS else "fail", "notes": ""},
        {"criterion": "delta_vs_dsr_equal_weight", "value": fmt(payload["delta_vs_dsr"]), "reference_or_threshold": "positive and material", "verdict": "pass" if payload["delta_vs_dsr"] > 75 else "weak_pass" if payload["delta_vs_dsr"] > 0 else "fail", "notes": ""},
        {"criterion": "duplicate_risk_vs_dsr_equal_weight", "value": fmt(payload["corr_vs_dsr"]), "reference_or_threshold": "<0.85 preferred", "verdict": "fail" if isinstance(payload["corr_vs_dsr"], float) and payload["corr_vs_dsr"] >= 0.85 else "pass", "notes": "Same-family overlap matters."},
        {"criterion": "concentration_risk", "value": "top2_sector_concentration", "reference_or_threshold": "must be offset by profit/additive value", "verdict": "weak_pass", "notes": "Top2 is more concentrated than equal-weight DSR."},
        {"criterion": "policy_compliance", "value": "research_only_review", "reference_or_threshold": "no forbidden path", "verdict": "pass", "notes": ""},
        {"criterion": "no_forbidden_mechanics", "value": True, "reference_or_threshold": "true", "verdict": "pass", "notes": ""},
        {"criterion": "no_real_money_path", "value": True, "reference_or_threshold": "true", "verdict": "pass", "notes": ""},
    ]
    return {
        "profit": [
            {"metric": "90d_median_final_equity", "value": fmt(target90["median_final_equity"]), "evidence_source": "promotion_review_diagnostic_cached_etf_data", "notes": ""},
            {"metric": "180d_median_final_equity", "value": fmt(target180["median_final_equity"]), "evidence_source": "promotion_review_diagnostic_cached_etf_data", "notes": ""},
            {"metric": "180d_mean_final_equity", "value": fmt(target180["mean_final_equity"]), "evidence_source": "promotion_review_diagnostic_cached_etf_data", "notes": ""},
            {"metric": "180d_p75_final_equity", "value": fmt(target180["p75_final_equity"]), "evidence_source": "promotion_review_diagnostic_cached_etf_data", "notes": ""},
            {"metric": "180d_p90_final_equity", "value": fmt(target180["p90_final_equity"]), "evidence_source": "promotion_review_diagnostic_cached_etf_data", "notes": ""},
            {"metric": "best_final_equity", "value": fmt(target180["best_final_equity"]), "evidence_source": "promotion_review_diagnostic_cached_etf_data", "notes": "180d"},
            {"metric": "worst_final_equity", "value": fmt(target180["worst_final_equity"]), "evidence_source": "promotion_review_diagnostic_cached_etf_data", "notes": "180d"},
            {"metric": "target_300_before_stop_rate", "value": fmt(target180["target_300_before_stop_rate"]), "evidence_source": "promotion_review_diagnostic_cached_etf_data", "notes": "180d"},
            {"metric": "target_400_before_stop_rate", "value": fmt(target180["target_400_before_stop_rate"]), "evidence_source": "promotion_review_diagnostic_cached_etf_data", "notes": "180d"},
            {"metric": "delta_vs_dsr_equal_weight", "value": fmt(payload["delta_vs_dsr"]), "evidence_source": "computed_proxy_from_cached_sector_etfs", "notes": "same-window median equity delta"},
            *[
                {"metric": f"delta_vs_{row['benchmark_id']}", "value": row["delta"], "evidence_source": row["comparison_status"], "notes": row["notes"]}
                for row in benchmark_rows
                if row["benchmark_id"] in {VM_QUALITY_ID, "active_combo", SPY_200D_ID, "SPY_buy_hold", "BIL_cash_proxy"}
            ],
        ],
        "risk": [
            {"metric": "90d_worst_drawdown", "value": fmt(summaries[TARGET_ID][90]["worst_drawdown"]), "evidence_source": "promotion_review_diagnostic_cached_etf_data", "notes": ""},
            {"metric": "180d_worst_drawdown", "value": fmt(target180["worst_drawdown"]), "evidence_source": "promotion_review_diagnostic_cached_etf_data", "notes": ""},
            {"metric": "median_drawdown", "value": fmt(target180["median_drawdown"]), "evidence_source": "promotion_review_diagnostic_cached_etf_data", "notes": "180d"},
            {"metric": "stop_hit_rate", "value": fmt(target180["stop_hit_rate"]), "evidence_source": "promotion_review_diagnostic_cached_etf_data", "notes": "180d"},
            {"metric": "risk_buffer_vs_minus_600", "value": fmt(target180["worst_drawdown"] - STOP_DOLLARS), "evidence_source": "promotion_review_diagnostic_cached_etf_data", "notes": "positive means above stop budget"},
            {"metric": "worst_loss_window", "value": fmt(target180["worst_loss_window"]), "evidence_source": "promotion_review_diagnostic_cached_etf_data", "notes": "180d"},
            {"metric": "concentration_risk_notes", "value": "top2_sector_concentration", "evidence_source": "promotion_review_diagnostic_cached_etf_data", "notes": "More concentrated than equal-weight DSR."},
            {"metric": "drawdown_vs_dsr_equal_weight", "value": fmt(target180["worst_drawdown"] - summaries["dsr_sector_equal_weight_defensive_filter_v1"][180]["worst_drawdown"]), "evidence_source": "computed_proxy_from_cached_sector_etfs", "notes": "positive means less severe worst drawdown than DSR equal-weight."},
        ],
        "benchmark": benchmark_rows,
        "duplicate": duplicate_rows,
        "family": family_rows,
        "scorecard": scorecard_rows,
        "target_window": [{"metric": "target_300_window_overlap_vs_dsr_equal_weight", "value": fmt(window_overlap(rows_by_strategy[TARGET_ID], rows_by_strategy["dsr_sector_equal_weight_defensive_filter_v1"], 180, "target_300_before_stop")), "evidence_source": "promotion_review_diagnostic_cached_etf_data", "notes": ""}],
        "drawdown_window": [{"metric": "drawdown_window_correlation_vs_dsr_equal_weight", "value": fmt(window_overlap(rows_by_strategy[TARGET_ID], rows_by_strategy["dsr_sector_equal_weight_defensive_filter_v1"], 180, "max_drawdown")), "evidence_source": "promotion_review_diagnostic_cached_etf_data", "notes": ""}],
    }


def update_registry(registry: dict[str, Any], output_dir: Path, payload: dict[str, Any]) -> dict[str, Any]:
    updated = deepcopy(registry)
    row = rows_by_id(updated).get(TARGET_ID)
    if not row:
        return updated
    final_decision = payload["final_decision"]
    row["status"] = final_decision
    row["current_status"] = final_decision
    row["promotion_review_completed"] = True
    row["promotion_decision"] = final_decision
    row["candidate_exhaustive_recommended"] = bool(payload["candidate_exhaustive_recommended"])
    row["candidate_exhaustive_run"] = False
    row["paper_forward_active"] = False
    row["paper_forward_allowed_by_risk_framework"] = False
    row["real_money_recommendation"] = False
    row["latest_promotion_review_path"] = str(output_dir)
    row["latest_evidence_path"] = str(output_dir)
    row["allowed_next_action"] = payload["next_action"]
    row["next_allowed_action"] = payload["next_action"]
    row["allowed_next_actions"] = [payload["next_action"]]
    row["forbidden_next_actions"] = sorted(set(row.get("forbidden_next_actions", [])) | set(FORBIDDEN_NEXT_ACTIONS))
    row["evidence_source"] = "dsr_top2_promotion_review_cached_etf_diagnostic"
    row["missing_evidence"] = "" if payload["diagnostics_available"] else "Required cached sector ETF data missing: " + ";".join(payload["missing_symbols"])
    row["evidence_needed"] = "candidate_exhaustive prompt only if promotion decision is accepted" if payload["candidate_exhaustive_recommended"] else "watchlist/duplicate/risk follow-up only; no candidate run"
    row["promotion_reason"] = f"Bounded promotion review decision: {final_decision}; next_action={payload['next_action']}"
    return updated


def run_promotion_review(root: Path = ROOT, update_registry_file: bool = True, strict_state: bool = True) -> dict[str, Any]:
    registry_path = root / REGISTRY_PATH
    registry = load_yaml(registry_path)
    mismatches = state_mismatches(root, registry)
    if mismatches and strict_state:
        raise RuntimeError("State mismatch before DSR Top2 promotion review: " + "; ".join(mismatches))
    before_protected = protected_snapshot(registry)
    output_dir = root / OUTPUT_DIR
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    payload = build_review_payload(root)
    rows = build_output_rows(payload)
    final_decision = payload["final_decision"]
    next_action = payload["next_action"]
    candidate_recommended = bool(payload["candidate_exhaustive_recommended"])
    write_csv(output_dir / f"{TARGET_ID}_evidence_scorecard.csv", rows["scorecard"], ["criterion", "value", "reference_or_threshold", "verdict", "notes"])
    write_csv(output_dir / f"{TARGET_ID}_profit_review.csv", rows["profit"], ["metric", "value", "evidence_source", "notes"])
    write_csv(output_dir / f"{TARGET_ID}_risk_review.csv", rows["risk"], ["metric", "value", "evidence_source", "notes"])
    write_csv(output_dir / f"{TARGET_ID}_benchmark_review.csv", rows["benchmark"], ["benchmark_id", "comparison_status", "strategy_metric", "benchmark_metric", "delta", "notes"])
    write_csv(output_dir / f"{TARGET_ID}_duplicate_review.csv", rows["duplicate"], ["comparison_target", "overlap_status", "duplicate_label", "correlation", "concentration_risk", "target_window_overlap", "drawdown_window_overlap", "notes"])
    write_csv(output_dir / f"{TARGET_ID}_family_comparison.csv", rows["family"], ["strategy_id", "current_status", "evidence_source", "180d_median_equity", "180d_target_300", "180d_target_400", "180d_worst_drawdown", "stop_hit_rate", "duplicate_label", "risk_label", "reason_for_status", "next_action"])
    write_csv(output_dir / f"{TARGET_ID}_target_window_review.csv", rows["target_window"], ["metric", "value", "evidence_source", "notes"])
    write_csv(output_dir / f"{TARGET_ID}_drawdown_window_review.csv", rows["drawdown_window"], ["metric", "value", "evidence_source", "notes"])
    write_csv(output_dir / f"{TARGET_ID}_rule_documentation.csv", target_rule_rows(payload["common_start_warning"]), ["field", "value", "source", "notes"])
    write_csv(output_dir / "cache_status.csv", payload["cache_rows"], ["symbol", "required", "cache_available", "cache_path", "qa_status", "first_date", "last_date", "row_count", "warmup_sufficiency", "missing_reason"])
    missing_text = "none" if payload["diagnostics_available"] else "; ".join(payload["missing_symbols"])
    (output_dir / f"{TARGET_ID}_missing_evidence.md").write_text(f"# Missing Evidence\n\nMissing evidence: `{missing_text}`.\n\nUnavailable comparisons, if any, are marked unavailable and not zero-filled.\n", encoding="utf-8")
    (output_dir / f"{TARGET_ID}_dsr_overlap_review.md").write_text(f"# DSR Overlap Review\n\nData-history mode: `{DATA_HISTORY_MODE}`.\n\n{payload['common_start_warning']}\n\nDSR Top2 is same-family as active/frozen DSR equal-weight; duplicate/additive diagnostics are in the duplicate review CSV.\n", encoding="utf-8")
    (output_dir / f"{TARGET_ID}_promotion_decision.md").write_text(f"# Promotion Decision\n\nFinal decision: `{final_decision}`\n\nCandidate exhaustive recommended: `{str(candidate_recommended).lower()}`\n\nNext action: `{next_action}`\n", encoding="utf-8")
    (output_dir / f"{TARGET_ID}_next_action.md").write_text(f"# Next Action\n\n`{next_action}`\n", encoding="utf-8")
    (output_dir / f"{TARGET_ID}_promotion_review_summary.md").write_text(
        f"# DSR Sector Top2 Promotion Review\n\nTarget: `{TARGET_ID}`\n\nData-history mode: `{DATA_HISTORY_MODE}`\n\n{payload['common_start_warning']}\n\nFinal decision: `{final_decision}`\n\nCandidate exhaustive recommended: `{str(candidate_recommended).lower()}`\n\nNext action: `{next_action}`\n\nNo candidate_exhaustive, paper-forward review, paper-forward activation, broker path, live orders, or real-money recommendation was run or added.\n",
        encoding="utf-8",
    )
    updated_registry = update_registry(registry, output_dir, payload)
    after_protected = protected_snapshot(updated_registry)
    consistency = {
        "promotion_review_completed": True,
        "cache_used_successfully": payload["diagnostics_available"],
        "data_history_mode": DATA_HISTORY_MODE,
        "no_candidate_exhaustive_run": True,
        "no_paper_forward_activation": True,
        "no_paper_forward_checkpoint": True,
        "no_active_observation_mutation": before_protected == after_protected,
        "no_vm_quality_mutation": before_protected.get(VM_QUALITY_ID) == after_protected.get(VM_QUALITY_ID),
        "no_dsr_equal_weight_mutation": before_protected.get(ACTIVE_DSR_ID) == after_protected.get(ACTIVE_DSR_ID),
        "no_spy_200d_mutation": before_protected.get(SPY_200D_ID) == after_protected.get(SPY_200D_ID),
        "no_broker_path_added": True,
        "no_live_order_path_added": True,
        "no_real_money_recommendation": True,
        "evidence_source_labeled": True,
        "final_decision_assigned": final_decision in ALLOWED_DECISIONS,
        "next_action_explicit": bool(next_action),
        "consistency_passed": False,
    }
    consistency["consistency_passed"] = all(value is True for key, value in consistency.items() if key not in {"cache_used_successfully", "data_history_mode", "consistency_passed"})
    manifest = {
        "created_at_utc": now_utc(),
        "target_strategy_id": TARGET_ID,
        "family": FAMILY,
        "final_decision": final_decision,
        "candidate_exhaustive_recommended": candidate_recommended,
        "candidate_exhaustive_run": False,
        "paper_forward_review": False,
        "paper_forward_activation": False,
        "paper_forward_checkpoint": False,
        "data_downloaded": False,
        "provider_api_called": False,
        "broker_integration": False,
        "live_orders": False,
        "order_placement": False,
        "real_money_recommendation": False,
        "missing_symbols": payload["missing_symbols"],
        "next_action": next_action,
        "data_history_mode": DATA_HISTORY_MODE,
        "diagnostics_available": payload["diagnostics_available"],
        "state_mismatches": mismatches,
    }
    write_json(output_dir / f"{TARGET_ID}_manifest.json", manifest)
    write_json(output_dir / f"{TARGET_ID}_consistency_check.json", consistency)
    create_packet(output_dir, f"{TARGET_ID}_promotion_review_packet.zip")
    if update_registry_file:
        registry_path.write_text(yaml.safe_dump(updated_registry, sort_keys=False, width=140), encoding="utf-8")
    return {
        "output_dir": str(output_dir),
        "final_decision": final_decision,
        "candidate_exhaustive_recommended": candidate_recommended,
        "next_action": next_action,
        "missing_symbols": payload["missing_symbols"],
        "data_history_mode": DATA_HISTORY_MODE,
        "diagnostics_available": payload["diagnostics_available"],
        "consistency": consistency,
        "manifest": manifest,
    }


def main() -> int:
    result = run_promotion_review(ROOT)
    print(f"promotion_review_latest_dir={result['output_dir']}")
    print(f"target_strategy_id={TARGET_ID}")
    print(f"cache_used_successfully={str(result['diagnostics_available']).lower()}")
    print(f"data_history_mode={result['data_history_mode']}")
    print(f"final_decision={result['final_decision']}")
    print(f"candidate_exhaustive_recommended={str(result['candidate_exhaustive_recommended']).lower()}")
    print(f"missing_symbols={';'.join(result['missing_symbols']) or 'none'}")
    print(f"next_action={result['next_action']}")
    print(f"consistency_passed={str(result['consistency']['consistency_passed']).lower()}")
    return 0 if result["consistency"]["consistency_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
