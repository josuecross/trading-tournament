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
REGISTRY_PATH = Path("strategy_lab") / "strategy_registry.yaml"
SYMBOL_MAP_PATH = Path("strategy_lab") / "approved_etf_symbol_map.yaml"
OUTPUT_DIR = Path("evidence") / "parallel_research_discovery" / "new_batch_approved_cache" / "latest"

VM_ID = "paper_forward_vm_quality_lowvol_proxy_v1"
DSR_ID = "paper_forward_dsr_sector_equal_weight_defensive_filter_v1"
SPY_200D_ID = "SPY_200d_trend_model"
TOP2_ID = "dsr_sector_top2_momentum_200d_bil_v1"
TOP3_ID = "dsr_sector_top3_momentum_defensive_cash_v1"

STARTING_EQUITY = 3000.0
STOP_DOLLARS = -600.0
SLIPPAGE = 0.0005
MAX_WINDOWS_PER_HORIZON = 5
HORIZONS = [90, 180]
DATA_HISTORY_MODE = "per_asset_availability"

FORBIDDEN_SYMBOLS = {"DBC"}
BENCHMARK_IDS = [VM_ID, DSR_ID, SPY_200D_ID, "SPY_buy_hold", "QQQ_buy_hold", "BIL_cash_proxy"]
NEXT_ACTIONS = {
    "promotion": "create_promotion_review_for_best_approved_cache_discovery_candidate",
    "diversifier": "review_best_diversifier_watchlist_candidate_or_continue_discovery",
    "none": "continue_next_approved_family_discovery_batch",
    "data_issue": "repair_approved_cache_discovery_data_issue",
}


def candidate_specs() -> list[dict[str, Any]]:
    return [
        {"strategy_id": "qvm_quality_value_momentum_top2_v1", "family_group": "quality_value_momentum_blend", "symbols": ["QUAL", "MTUM", "VLUE", "VTV", "SPY", "QQQ", "BIL"], "rule": "top_n_return", "n": 2},
        {"strategy_id": "qvm_quality_value_momentum_risk_adjusted_top2_v1", "family_group": "quality_value_momentum_blend", "symbols": ["QUAL", "MTUM", "VLUE", "VTV", "SPY", "QQQ", "BIL"], "rule": "top_n_risk_adjusted", "n": 2},
        {"strategy_id": "qvm_quality_momentum_lowvol_blend_v1", "family_group": "quality_value_momentum_blend", "symbols": ["QUAL", "MTUM", "SPLV", "USMV", "SPY", "BIL"], "rule": "equal_weight_filter"},
        {"strategy_id": "qvm_defensive_quality_rotation_bil_v1", "family_group": "quality_value_momentum_blend", "symbols": ["QUAL", "USMV", "VTV", "SPY", "BIL"], "rule": "top_n_risk_adjusted", "n": 1},
        {"strategy_id": "ma_offensive_defensive_top3_trend_v1", "family_group": "multi_asset_offensive_defensive", "symbols": ["SPY", "QQQ", "IWM", "EFA", "EEM", "GLD", "IEF", "TLT", "AGG", "BIL"], "rule": "top_n_return", "n": 3},
        {"strategy_id": "ma_global_assets_risk_adjusted_top3_v1", "family_group": "multi_asset_offensive_defensive", "symbols": ["SPY", "QQQ", "IWM", "EFA", "EEM", "GLD", "IEF", "TLT", "AGG", "BIL"], "rule": "top_n_risk_adjusted", "n": 3},
        {"strategy_id": "ma_equity_bond_gold_regime_v1", "family_group": "multi_asset_offensive_defensive", "symbols": ["SPY", "IEF", "GLD", "BIL"], "rule": "equity_bond_gold_regime"},
        {"strategy_id": "ma_aggressive_growth_with_bil_filter_v1", "family_group": "multi_asset_offensive_defensive", "symbols": ["QQQ", "SPY", "IWM", "BIL"], "rule": "growth_top2_spy_regime"},
        {"strategy_id": "lvq_lowvol_quality_top2_v1", "family_group": "lowvol_quality_hybrid", "symbols": ["SPLV", "USMV", "QUAL", "VTV", "SPY", "BIL"], "rule": "top_n_risk_adjusted", "n": 2},
        {"strategy_id": "lvq_lowvol_quality_spy_regime_v1", "family_group": "lowvol_quality_hybrid", "symbols": ["SPLV", "USMV", "QUAL", "SPY", "BIL"], "rule": "spy_regime_equal_weight"},
        {"strategy_id": "lvq_lowvol_quality_equal_weight_filter_v1", "family_group": "lowvol_quality_hybrid", "symbols": ["SPLV", "USMV", "QUAL", "VTV", "SPY", "BIL"], "rule": "equal_weight_filter"},
        {"strategy_id": "yield_credit_trend_filter_v1", "family_group": "yield_credit_defensive_recheck", "symbols": ["HYG", "LQD", "EMB", "AGG", "IEF", "BIL", "SPY"], "rule": "equal_weight_filter"},
        {"strategy_id": "yield_credit_risk_off_rotation_v1", "family_group": "yield_credit_defensive_recheck", "symbols": ["HYG", "LQD", "EMB", "AGG", "IEF", "BIL", "SPY"], "rule": "yield_risk_off_rotation"},
    ]


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def rows_by_id(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(row.get("id")): row for row in registry.get("strategies", [])}


def approved_strategy_symbols(root: Path) -> set[str]:
    symbol_map = load_yaml(root / SYMBOL_MAP_PATH)
    return {row["symbol"] for row in symbol_map.get("symbols", []) if row.get("allowed_for_strategy") is True}


def validate_spec_symbols(spec: dict[str, Any], approved: set[str]) -> None:
    symbols = set(spec.get("symbols", []))
    forbidden = sorted((symbols - approved) | (symbols & FORBIDDEN_SYMBOLS))
    if forbidden:
        raise ValueError(f"{spec.get('strategy_id')} uses forbidden or unapproved symbols: {','.join(forbidden)}")


def required_symbols() -> list[str]:
    symbols: set[str] = {"SPY", "QQQ", "BIL"}
    for spec in candidate_specs():
        symbols.update(spec["symbols"])
    symbols.update(["SPLV", "USMV", "QUAL", "VTV", "XLK", "XLF", "XLE", "XLV", "XLY", "XLP", "XLU", "XLI", "XLB", "XLC"])
    return sorted(symbols)


def cache_path(root: Path, symbol: str) -> Path:
    return root / "data" / "cache" / f"{symbol}.csv"


def qa_cache(root: Path, symbol: str) -> dict[str, Any]:
    path = cache_path(root, symbol)
    row = {"symbol": symbol, "required": True, "cache_available": path.exists(), "cache_path": str(path), "qa_status": "missing", "first_date": "", "last_date": "", "row_count": 0, "warmup_sufficiency": False, "missing_reason": "cache missing"}
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
    row.update({"first_date": "" if valid.empty else str(valid["date"].min().date()), "last_date": "" if valid.empty else str(valid["date"].max().date()), "row_count": int(len(valid)), "warmup_sufficiency": int(len(valid)) >= 252})
    passed = bool(len(valid) >= 252 and int(dates.dropna().duplicated().sum()) == 0 and valid["adj_close"].notna().any())
    row["qa_status"] = "passed" if passed else "failed"
    row["missing_reason"] = "" if passed else "insufficient rows, duplicate dates, or empty adjusted close"
    return row


def read_close(root: Path, symbol: str) -> pd.Series | None:
    if qa_cache(root, symbol)["qa_status"] != "passed":
        return None
    frame = pd.read_csv(cache_path(root, symbol))
    dates = pd.to_datetime(frame["date"], errors="coerce").dt.tz_localize(None)
    close = pd.to_numeric(frame["adj_close"], errors="coerce")
    series = pd.DataFrame({"date": dates, symbol: close}).dropna().sort_values("date").drop_duplicates("date")
    return series.set_index("date")[symbol].astype(float) if not series.empty else None


def prepare_prices(root: Path) -> tuple[pd.DataFrame, list[str], list[dict[str, Any]]]:
    close_map: dict[str, pd.Series] = {}
    missing: list[str] = []
    cache_rows = [qa_cache(root, symbol) for symbol in required_symbols()]
    for row in cache_rows:
        symbol = row["symbol"]
        series = read_close(root, symbol)
        if series is None:
            missing.append(symbol)
        else:
            close_map[symbol] = series
    if missing:
        return pd.DataFrame(), missing, cache_rows
    return pd.concat(close_map.values(), axis=1, join="outer", sort=True).sort_index(), [], cache_rows


def state_mismatches(root: Path, registry: dict[str, Any]) -> list[str]:
    rows = rows_by_id(registry)
    mismatches: list[str] = []
    readiness = root / "evidence" / "approved_etf_cache_readiness" / "latest" / "approved_etf_cache_readiness_manifest.json"
    if not readiness.exists() or json.loads(readiness.read_text(encoding="utf-8")).get("missing_symbols") not in ([], None):
        mismatches.append("approved ETF cache is not ready")
    active_recompute = root / "evidence" / "active_strategy_evidence_recompute" / "latest" / "active_strategy_recompute_manifest.json"
    if not active_recompute.exists():
        mismatches.append("active strategy recompute evidence missing")
    else:
        manifest = json.loads(active_recompute.read_text(encoding="utf-8"))
        if manifest.get("decisions", {}).get(VM_ID) not in {"active_evidence_confirmed", "active_evidence_confirmed_with_minor_deltas"}:
            mismatches.append("VM active evidence is not confirmed")
        if manifest.get("decisions", {}).get(DSR_ID) not in {"active_evidence_material_mismatch_manual_review", "active_evidence_confirmed_with_minor_deltas", "active_evidence_confirmed"}:
            mismatches.append("DSR active evidence is not accepted for continuity")
    for strategy_id in [TOP2_ID, TOP3_ID]:
        row = rows.get(strategy_id, {})
        if row.get("promotion_decision") != "mark_duplicate_or_near_duplicate" and row.get("status") != "mark_duplicate_or_near_duplicate":
            mismatches.append(f"{strategy_id} is not duplicate/near-duplicate")
    for strategy_id in [VM_ID, DSR_ID, SPY_200D_ID]:
        row = rows.get(strategy_id, {})
        if row.get("paper_forward_active") is not True or row.get("rules_frozen") is not True:
            mismatches.append(f"{strategy_id} is not active/frozen")
    return mismatches


def available_at(close: pd.DataFrame, symbol: str, t: int, lookback: int = 0) -> bool:
    return bool(symbol in close.columns and t - lookback >= 0 and pd.notna(close.iloc[t][symbol]) and pd.notna(close.iloc[t - lookback][symbol]))


def eligible(close: pd.DataFrame, symbol: str, t: int) -> bool:
    if symbol not in close.columns or t < 200 or pd.isna(close.iloc[t][symbol]):
        return False
    window = close[symbol].iloc[t - 199 : t + 1].dropna()
    return bool(len(window) >= 200 and float(close.iloc[t][symbol]) > float(window.mean()))


def ret126(close: pd.DataFrame, symbol: str, t: int) -> float:
    return float(close.iloc[t][symbol] / close.iloc[t - 126][symbol] - 1.0) if available_at(close, symbol, t, 126) else float("nan")


def vol60(close: pd.DataFrame, symbol: str, t: int) -> float:
    if symbol not in close.columns or t < 60:
        return float("nan")
    returns = close[symbol].pct_change().iloc[t - 59 : t + 1].dropna()
    return float(returns.std()) if len(returns) >= 45 else float("nan")


def ranked(close: pd.DataFrame, symbols: list[str], t: int, risk_adjusted: bool) -> list[str]:
    scored: list[tuple[str, float]] = []
    for symbol in symbols:
        if symbol == "BIL" or not eligible(close, symbol, t):
            continue
        score = ret126(close, symbol, t)
        if risk_adjusted:
            vol = vol60(close, symbol, t)
            score = score / vol if np.isfinite(vol) and vol > 0 else float("nan")
        if np.isfinite(score):
            scored.append((symbol, score))
    return [symbol for symbol, _score in sorted(scored, key=lambda item: item[1], reverse=True)]


def equal_weight(symbols: list[str]) -> dict[str, float]:
    return {symbol: 1.0 / len(symbols) for symbol in symbols} if symbols else {"BIL": 1.0}


def spec_weights(close: pd.DataFrame, spec: dict[str, Any], t: int) -> dict[str, float]:
    assets = [symbol for symbol in spec["symbols"] if symbol != "BIL"]
    rule = spec["rule"]
    if rule == "top_n_return":
        picks = ranked(close, assets, t, False)[: int(spec["n"])]
        return equal_weight(picks)
    if rule == "top_n_risk_adjusted":
        picks = ranked(close, assets, t, True)[: int(spec["n"])]
        return equal_weight(picks)
    if rule == "equal_weight_filter":
        return equal_weight([symbol for symbol in assets if eligible(close, symbol, t)])
    if rule == "spy_regime_equal_weight":
        return equal_weight([symbol for symbol in assets if symbol != "SPY" and eligible(close, symbol, t)]) if eligible(close, "SPY", t) else {"BIL": 1.0}
    if rule == "equity_bond_gold_regime":
        if eligible(close, "SPY", t):
            return {"SPY": 0.6, "IEF": 0.3, "GLD": 0.1}
        return {"IEF": 0.6, "GLD": 0.2, "BIL": 0.2}
    if rule == "growth_top2_spy_regime":
        return equal_weight(ranked(close, ["QQQ", "SPY", "IWM"], t, False)[:2]) if eligible(close, "SPY", t) else {"BIL": 1.0}
    if rule == "yield_risk_off_rotation":
        return equal_weight(ranked(close, ["HYG", "LQD", "EMB"], t, True)[:2]) if eligible(close, "SPY", t) else {"IEF": 0.5, "BIL": 0.5}
    return {"BIL": 1.0}


def vm_weights(close: pd.DataFrame, t: int) -> dict[str, float]:
    picks = ranked(close, ["SPLV", "USMV", "QUAL", "SPY"], t, True)[:2]
    return equal_weight(picks)


def dsr_weights(close: pd.DataFrame, t: int) -> dict[str, float]:
    sectors = ["XLK", "XLF", "XLE", "XLV", "XLY", "XLP", "XLU", "XLI", "XLB", "XLC"]
    picks = [symbol for symbol in sectors if eligible(close, symbol, t)]
    if len(picks) >= 3:
        return equal_weight(picks)
    if picks:
        weights = {symbol: 1.0 / 3.0 for symbol in picks}
        weights["BIL"] = 1.0 - len(picks) / 3.0
        return weights
    return {"BIL": 1.0}


def strategy_weights(close: pd.DataFrame, strategy_id: str, t: int, specs_by_id: dict[str, dict[str, Any]]) -> dict[str, float]:
    if strategy_id in specs_by_id:
        return spec_weights(close, specs_by_id[strategy_id], t)
    if strategy_id == VM_ID:
        return vm_weights(close, t)
    if strategy_id == DSR_ID:
        return dsr_weights(close, t)
    if strategy_id == SPY_200D_ID:
        return {"SPY": 1.0} if eligible(close, "SPY", t) else {"BIL": 1.0}
    if strategy_id == "SPY_buy_hold":
        return {"SPY": 1.0}
    if strategy_id == "QQQ_buy_hold":
        return {"QQQ": 1.0}
    return {"BIL": 1.0}


def simulate(close: pd.DataFrame, start: int, horizon: int, strategy_id: str, specs_by_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
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
            new_weights = strategy_weights(close, strategy_id, signal, specs_by_id)
            turnover = sum(abs(new_weights.get(sym, 0.0) - weights.get(sym, 0.0)) for sym in set(new_weights) | set(weights))
            equity -= equity * turnover * SLIPPAGE
            weights = new_weights
            last_month = month
        daily_return = 0.0
        for symbol, weight in weights.items():
            if available_at(close, symbol, today, 1):
                daily_return += weight * float(close.iloc[today][symbol] / close.iloc[today - 1][symbol] - 1.0)
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
    return {"strategy_id": strategy_id, "horizon": horizon, "window_start": str(close.index[start].date()), "window_end": str(close.index[start + horizon].date()), "final_equity": equity, "profit_dollars": equity - STARTING_EQUITY, "max_drawdown": max_drawdown, "absolute_600_stop_hit": stop is not None, "target_300_before_stop": bool(target300 is not None and (stop is None or target300 <= stop)), "target_400_before_stop": bool(target400 is not None and (stop is None or target400 <= stop))}


def sample_starts(close: pd.DataFrame, horizon: int) -> list[int]:
    starts = list(range(252, len(close) - horizon))
    if len(starts) <= MAX_WINDOWS_PER_HORIZON:
        return starts
    return sorted(set(int(x) for x in np.linspace(starts[0], starts[-1], MAX_WINDOWS_PER_HORIZON)))


def run_windows(close: pd.DataFrame, strategy_id: str, specs_by_id: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return [simulate(close, start, horizon, strategy_id, specs_by_id) for horizon in HORIZONS for start in sample_starts(close, horizon)]


def summarize(rows: list[dict[str, Any]], strategy_id: str, horizon: int) -> dict[str, Any]:
    df = pd.DataFrame([row for row in rows if row["strategy_id"] == strategy_id and row["horizon"] == horizon])
    if df.empty:
        return {"strategy_id": strategy_id, "horizon": horizon, "validation_status": "missing_or_unavailable"}
    return {"strategy_id": strategy_id, "horizon": horizon, "window_count": int(len(df)), "median_final_equity": float(df["final_equity"].median()), "mean_final_equity": float(df["final_equity"].mean()), "p75_final_equity": float(df["final_equity"].quantile(0.75)), "p90_final_equity": float(df["final_equity"].quantile(0.90)), "best_final_equity": float(df["final_equity"].max()), "worst_final_equity": float(df["final_equity"].min()), "target_300_before_stop_rate": float(df["target_300_before_stop"].mean()), "target_400_before_stop_rate": float(df["target_400_before_stop"].mean()), "worst_drawdown": float(df["max_drawdown"].min()), "stop_hit_rate": float(df["absolute_600_stop_hit"].mean()), "risk_buffer_vs_minus_600": float(df["max_drawdown"].min() - STOP_DOLLARS)}


def full_returns(close: pd.DataFrame, strategy_id: str, specs_by_id: dict[str, dict[str, Any]]) -> pd.Series:
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
            weights = strategy_weights(close, strategy_id, signal, specs_by_id)
            last_month = month
        daily_return = 0.0
        for symbol, weight in weights.items():
            if available_at(close, symbol, today, 1):
                daily_return += weight * float(close.iloc[today][symbol] / close.iloc[today - 1][symbol] - 1.0)
        equity *= 1.0 + daily_return
        values.append(equity)
        dates.append(close.index[today])
    return pd.Series(values, index=dates).pct_change().dropna()


def corr(returns: dict[str, pd.Series], left: str, right: str) -> float | str:
    if left not in returns or right not in returns:
        return "unavailable"
    aligned = pd.concat([returns[left].rename("left"), returns[right].rename("right")], axis=1).dropna()
    return float(aligned["left"].corr(aligned["right"])) if len(aligned) > 5 else "unavailable"


def fmt(value: Any) -> Any:
    return round(value, 4) if isinstance(value, float) else value


def classify(summary: dict[str, Any], deltas: dict[str, Any], correlations: dict[str, Any]) -> tuple[str, str]:
    if summary.get("validation_status") == "missing_or_unavailable":
        return "evidence_missing", "diagnostics unavailable"
    if summary["stop_hit_rate"] > 0 or summary["worst_drawdown"] <= STOP_DOLLARS:
        return "too_risky", "stop or drawdown breach"
    duplicate_like = any(isinstance(correlations.get(key), float) and correlations[key] >= 0.88 for key in ["corr_vs_active_vm", "corr_vs_active_dsr", "corr_vs_spy_200d"])
    benchmark_lag = any(isinstance(deltas.get(key), float) and deltas[key] < -75 for key in ["delta_vs_spy_200d", "delta_vs_spy_buy_hold", "delta_vs_bil"])
    useful_targets = summary["target_300_before_stop_rate"] >= 0.4 and summary["target_400_before_stop_rate"] >= 0.25 and summary["median_final_equity"] >= 3300
    if useful_targets and not duplicate_like and not benchmark_lag:
        return "promotion_review_candidate", "useful target profile, acceptable risk, not near-duplicate"
    if duplicate_like:
        return "duplicate_or_near_duplicate", "high correlation with active/control benchmark"
    if summary["median_final_equity"] < 3150 or summary["target_300_before_stop_rate"] < 0.2:
        return "too_slow_for_profit_goal", "target/profit profile too weak"
    if not benchmark_lag and max(v for v in correlations.values() if isinstance(v, float)) < 0.80:
        return "diversifier_watchlist_candidate", "different profile but not promotion-strong"
    if benchmark_lag:
        return "needs_benchmark_delta_review", "lags at least one core benchmark on median equity"
    return "diversifier_watchlist_candidate", "watchlist profile"


def build_payload(root: Path) -> dict[str, Any]:
    approved = approved_strategy_symbols(root)
    specs = candidate_specs()
    for spec in specs:
        validate_spec_symbols(spec, approved)
    close, missing, cache_rows = prepare_prices(root)
    if missing or close.empty:
        return {"diagnostics_available": False, "missing_symbols": missing, "cache_rows": cache_rows, "rows": [], "family_rows": [], "benchmark_rows": [], "decision_rows": [], "next_action": NEXT_ACTIONS["data_issue"], "best_row": ""}
    specs_by_id = {spec["strategy_id"]: spec for spec in specs}
    all_ids = [spec["strategy_id"] for spec in specs] + BENCHMARK_IDS
    windows = {strategy_id: run_windows(close, strategy_id, specs_by_id) for strategy_id in all_ids}
    summaries = {strategy_id: {h: summarize(windows[strategy_id], strategy_id, h) for h in HORIZONS} for strategy_id in all_ids}
    returns = {strategy_id: full_returns(close, strategy_id, specs_by_id) for strategy_id in all_ids}
    result_rows: list[dict[str, Any]] = []
    benchmark_rows: list[dict[str, Any]] = []
    decision_rows: list[dict[str, Any]] = []
    for spec in specs:
        sid = spec["strategy_id"]
        s90 = summaries[sid][90]
        s180 = summaries[sid][180]
        deltas = {
            "delta_vs_active_vm": s180["median_final_equity"] - summaries[VM_ID][180]["median_final_equity"],
            "delta_vs_active_dsr": s180["median_final_equity"] - summaries[DSR_ID][180]["median_final_equity"],
            "delta_vs_active_combo": "unavailable",
            "delta_vs_spy_200d": s180["median_final_equity"] - summaries[SPY_200D_ID][180]["median_final_equity"],
            "delta_vs_spy_buy_hold": s180["median_final_equity"] - summaries["SPY_buy_hold"][180]["median_final_equity"],
            "delta_vs_qqq_buy_hold": s180["median_final_equity"] - summaries["QQQ_buy_hold"][180]["median_final_equity"],
            "delta_vs_bil": s180["median_final_equity"] - summaries["BIL_cash_proxy"][180]["median_final_equity"],
        }
        correlations = {"corr_vs_active_vm": corr(returns, sid, VM_ID), "corr_vs_active_dsr": corr(returns, sid, DSR_ID), "corr_vs_spy_200d": corr(returns, sid, SPY_200D_ID)}
        verdict, reason = classify(s180, deltas, correlations)
        row = {"strategy_id": sid, "family_group": spec["family_group"], "rule": spec["rule"], "symbols": ";".join(spec["symbols"]), "data_history_mode": DATA_HISTORY_MODE, "90d_median_final_equity": fmt(s90["median_final_equity"]), "180d_median_final_equity": fmt(s180["median_final_equity"]), "180d_mean_final_equity": fmt(s180["mean_final_equity"]), "180d_p75_final_equity": fmt(s180["p75_final_equity"]), "180d_p90_final_equity": fmt(s180["p90_final_equity"]), "best_final_equity": fmt(s180["best_final_equity"]), "worst_final_equity": fmt(s180["worst_final_equity"]), "target_300_before_stop_rate": fmt(s180["target_300_before_stop_rate"]), "target_400_before_stop_rate": fmt(s180["target_400_before_stop_rate"]), "180d_worst_drawdown": fmt(s180["worst_drawdown"]), "stop_hit_rate": fmt(s180["stop_hit_rate"]), "risk_buffer_vs_minus_600": fmt(s180["risk_buffer_vs_minus_600"]), **{k: fmt(v) for k, v in correlations.items()}, **{k: fmt(v) for k, v in deltas.items()}, "decision": verdict, "decision_reason": reason, "candidate_exhaustive_run": False, "paper_forward_active": False, "real_money_recommendation": False}
        result_rows.append(row)
        decision_rows.append({"strategy_id": sid, "family_group": spec["family_group"], "decision": verdict, "decision_reason": reason, "next_allowed_step": "promotion_review_only" if verdict == "promotion_review_candidate" else "research_sample_review_or_archive"})
        for bench in BENCHMARK_IDS:
            if bench == sid:
                continue
            benchmark_rows.append({"strategy_id": sid, "benchmark_id": bench, "strategy_180d_median_final_equity": fmt(s180["median_final_equity"]), "benchmark_180d_median_final_equity": fmt(summaries[bench][180]["median_final_equity"]), "delta": fmt(s180["median_final_equity"] - summaries[bench][180]["median_final_equity"]), "correlation": fmt(corr(returns, sid, bench)), "comparison_status": "computed"})
        benchmark_rows.append({"strategy_id": sid, "benchmark_id": "active_combo", "strategy_180d_median_final_equity": fmt(s180["median_final_equity"]), "benchmark_180d_median_final_equity": "", "delta": "unavailable", "correlation": "unavailable", "comparison_status": "unavailable"})
    family_rows = []
    for family, frame in pd.DataFrame(result_rows).groupby("family_group"):
        best = frame.sort_values("180d_median_final_equity", ascending=False).iloc[0]
        family_rows.append({"family_group": family, "row_count": int(len(frame)), "best_strategy_id": best["strategy_id"], "best_180d_median_final_equity": best["180d_median_final_equity"], "promotion_candidates": int((frame["decision"] == "promotion_review_candidate").sum()), "watchlist_candidates": int(frame["decision"].astype(str).str.contains("watchlist").sum())})
    promotions = [row for row in result_rows if row["decision"] == "promotion_review_candidate"]
    diversifiers = [row for row in result_rows if row["decision"] == "diversifier_watchlist_candidate"]
    next_action = NEXT_ACTIONS["promotion"] if promotions else NEXT_ACTIONS["diversifier"] if diversifiers else NEXT_ACTIONS["none"]
    best_row = max(result_rows, key=lambda row: float(row["180d_median_final_equity"]))["strategy_id"] if result_rows else ""
    return {"diagnostics_available": True, "missing_symbols": [], "cache_rows": cache_rows, "rows": result_rows, "family_rows": family_rows, "benchmark_rows": benchmark_rows, "decision_rows": decision_rows, "next_action": next_action, "best_row": best_row}


def registry_row(spec: dict[str, Any], result: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    verdict = result["decision"]
    return {"id": spec["strategy_id"], "display_name": spec["strategy_id"].replace("_", " ").title(), "lane": "profit_exploration", "instrument_family": "ETF", "strategy_family": spec["family_group"], "version": "v1", "parent_id": "", "credibility_tier": "tier2_exploratory", "status": verdict, "role": "approved_cache_parallel_discovery_row", "rules_frozen": True, "paper_forward_active": False, "implementation_status": "implemented_research_sample", "data_source": "existing_adjusted_etf_cache", "evidence_source": "parallel_discovery_approved_cache_batch", "latest_evidence_path": str(output_dir), "latest_known_result_summary": f"Approved-cache discovery verdict: {verdict}; 180d median equity {result['180d_median_final_equity']}.", "allowed_next_action": "create_promotion_review_for_best_parallel_discovery_candidate" if verdict == "promotion_review_candidate" else "research_sample_review", "forbidden_next_actions": ["run_candidate_exhaustive", "paper_forward_activation", "paper_forward_checkpoint", "paper_forward_review", "promote_to_real_money", "add_broker_integration", "live_orders", "order_placement", "place_live_orders", "download_data", "tune_parameters"], "risk_framework_status": "research_sample_only", "paper_forward_allowed_by_risk_framework": False, "real_money_recommendation": False, "promotion_blockers": "research_sample_only;not_candidate_exhaustive;not_paper_forward_allowed", "promotion_requirements": "Separate promotion review only; no candidate_exhaustive from discovery batch.", "demotion_or_kill_criteria": "Weak target profile, unacceptable drawdown, duplicate exposure, or benchmark lag.", "notes": "Fixed-rule approved-cache discovery row; no broker/live-order/real-money path.", "strategy_id": spec["strategy_id"], "family": spec["family_group"], "instrument_lane": "ETF", "evidence_tier": "research_sample", "current_status": verdict, "allowed_next_actions": ["create_promotion_review_for_best_parallel_discovery_candidate"] if verdict == "promotion_review_candidate" else ["research_sample_review"], "candidate_exhaustive_run": False, "candidate_exhaustive_recommended": False, "promotion_review_required": verdict == "promotion_review_candidate", "promotion_decision": verdict, "promotion_reason": result["decision_reason"], "primary_failure_mode": "not_flagged" if verdict == "promotion_review_candidate" else verdict, "duplication_risk": "flagged" if "duplicate" in verdict else "not_flagged", "risk_budget_status": "research_sample_screened", "evidence_needed": "promotion review only if selected; no paper-forward action", "duplicate_of": "", "blocked_reason": ""}


def update_registry(root: Path, payload: dict[str, Any]) -> None:
    path = root / REGISTRY_PATH
    registry = load_yaml(path)
    results_by_id = {row["strategy_id"]: row for row in payload["rows"]}
    specs_by_id = {spec["strategy_id"]: spec for spec in candidate_specs()}
    existing = [row for row in registry.get("strategies", []) if row.get("id") not in specs_by_id]
    new_rows = [registry_row(specs_by_id[sid], results_by_id[sid], root / OUTPUT_DIR) for sid in specs_by_id if sid in results_by_id]
    registry["strategies"] = existing + new_rows
    path.write_text(yaml.safe_dump(registry, sort_keys=False, width=120), encoding="utf-8")


def create_packet(directory: Path) -> Path:
    packet = directory / "parallel_discovery_approved_cache_packet.zip"
    if packet.exists():
        packet.unlink()
    with zipfile.ZipFile(packet, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(directory.iterdir()):
            if path.is_file() and path.name != packet.name:
                zf.write(path, path.name)
    return packet


def write_outputs(root: Path, payload: dict[str, Any], consistency: dict[str, Any]) -> dict[str, Any]:
    output = root / OUTPUT_DIR
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)
    result_fields = ["strategy_id", "family_group", "rule", "symbols", "data_history_mode", "90d_median_final_equity", "180d_median_final_equity", "180d_mean_final_equity", "180d_p75_final_equity", "180d_p90_final_equity", "best_final_equity", "worst_final_equity", "target_300_before_stop_rate", "target_400_before_stop_rate", "180d_worst_drawdown", "stop_hit_rate", "risk_buffer_vs_minus_600", "corr_vs_active_vm", "corr_vs_active_dsr", "corr_vs_spy_200d", "delta_vs_active_vm", "delta_vs_active_dsr", "delta_vs_active_combo", "delta_vs_spy_200d", "delta_vs_spy_buy_hold", "delta_vs_qqq_buy_hold", "delta_vs_bil", "decision", "decision_reason", "candidate_exhaustive_run", "paper_forward_active", "real_money_recommendation"]
    write_csv(output / "parallel_discovery_approved_cache_results.csv", payload["rows"], result_fields)
    write_csv(output / "parallel_discovery_approved_cache_family_summary.csv", payload["family_rows"], ["family_group", "row_count", "best_strategy_id", "best_180d_median_final_equity", "promotion_candidates", "watchlist_candidates"])
    write_csv(output / "parallel_discovery_approved_cache_benchmark_delta.csv", payload["benchmark_rows"], ["strategy_id", "benchmark_id", "strategy_180d_median_final_equity", "benchmark_180d_median_final_equity", "delta", "correlation", "comparison_status"])
    write_csv(output / "parallel_discovery_approved_cache_decision_log.csv", payload["decision_rows"], ["strategy_id", "family_group", "decision", "decision_reason", "next_allowed_step"])
    write_csv(output / "parallel_discovery_approved_cache_watchlist.csv", [r for r in payload["rows"] if "watchlist" in r["decision"]], result_fields)
    write_csv(output / "parallel_discovery_approved_cache_promotion_candidates.csv", [r for r in payload["rows"] if r["decision"] == "promotion_review_candidate"], result_fields)
    write_csv(output / "parallel_discovery_approved_cache_rejects.csv", [r for r in payload["rows"] if r["decision"] in {"reject", "too_risky", "too_slow_for_profit_goal", "duplicate_or_near_duplicate", "evidence_missing", "needs_benchmark_delta_review"}], result_fields)
    (output / "parallel_discovery_approved_cache_next_action.md").write_text(f"# Next Action\n\n`{payload['next_action']}`\n\nDo not run candidate_exhaustive or any paper-forward/broker/real-money workflow directly from this discovery batch.\n", encoding="utf-8")
    summary = ["# Parallel Discovery Approved Cache Batch", "", f"Created at UTC: {now_utc()}", f"Rows tested: {len(payload['rows'])}", f"Best row overall: `{payload['best_row']}`", f"Promotion candidates: {sum(1 for r in payload['rows'] if r['decision'] == 'promotion_review_candidate')}", f"Diversifier watchlist candidates: {sum(1 for r in payload['rows'] if r['decision'] == 'diversifier_watchlist_candidate')}", f"Next action: `{payload['next_action']}`", "", "Discovery only; no candidate validation, paper-forward action, broker/live-order, provider download, or real-money recommendation."]
    (output / "parallel_discovery_approved_cache_summary.md").write_text("\n".join(summary) + "\n", encoding="utf-8")
    manifest = {"created_at_utc": now_utc(), "families_tested": sorted({spec["family_group"] for spec in candidate_specs()}), "rows_tested": [spec["strategy_id"] for spec in candidate_specs()], "best_row": payload["best_row"], "next_action": payload["next_action"], "diagnostics_available": payload["diagnostics_available"], "missing_symbols": payload["missing_symbols"], "candidate_exhaustive_run": False, "paper_forward_review": False, "paper_forward_activation": False, "paper_forward_checkpoint": False, "provider_api_called": False, "data_downloaded": False, "broker_integration": False, "live_orders": False, "order_placement": False, "real_money_recommendation": False, "data_history_mode": DATA_HISTORY_MODE}
    write_json(output / "parallel_discovery_approved_cache_manifest.json", manifest)
    write_json(output / "parallel_discovery_approved_cache_consistency_check.json", consistency)
    packet = create_packet(output)
    return {"output_dir": str(output), "packet": str(packet)}


def run_parallel_discovery(root: Path = ROOT, strict_state: bool = True) -> dict[str, Any]:
    registry = load_yaml(root / REGISTRY_PATH)
    mismatches = state_mismatches(root, registry)
    if mismatches and strict_state:
        raise RuntimeError("State confirmation failed: " + "; ".join(mismatches))
    payload = build_payload(root)
    update_registry(root, payload)
    consistency = {"approved_symbols_only": True, "forbidden_symbols_rejected": True, "parallel_discovery_completed": True, "cache_used": payload["diagnostics_available"] and not payload["missing_symbols"], "no_candidate_exhaustive_run": True, "no_paper_forward_review": True, "no_paper_forward_activation": True, "no_paper_forward_checkpoint": True, "no_active_observation_mutation": True, "no_broker_path_added": True, "no_live_order_path_added": True, "no_real_money_recommendation": True, "benchmark_unavailable_not_zero_filled": any(row["benchmark_id"] == "active_combo" and row["delta"] == "unavailable" for row in payload["benchmark_rows"]), "next_action_explicit": bool(payload["next_action"])}
    consistency["consistency_passed"] = all(bool(value) for value in consistency.values())
    outputs = write_outputs(root, payload, consistency)
    return {"output_dir": outputs["output_dir"], "packet": outputs["packet"], "best_row": payload["best_row"], "next_action": payload["next_action"], "promotion_candidates": [row["strategy_id"] for row in payload["rows"] if row["decision"] == "promotion_review_candidate"], "diversifier_watchlist_candidates": [row["strategy_id"] for row in payload["rows"] if row["decision"] == "diversifier_watchlist_candidate"], "consistency": consistency}


def main() -> None:
    print(json.dumps(run_parallel_discovery(ROOT, strict_state=True), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
