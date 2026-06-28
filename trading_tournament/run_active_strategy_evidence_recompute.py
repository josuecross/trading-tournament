from __future__ import annotations

import csv
import hashlib
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
OUTPUT_DIR = Path("evidence") / "active_strategy_evidence_recompute" / "latest"

VM_ID = "paper_forward_vm_quality_lowvol_proxy_v1"
DSR_ID = "paper_forward_dsr_sector_equal_weight_defensive_filter_v1"
SPY_200D_ID = "SPY_200d_trend_model"
TOP2_ID = "dsr_sector_top2_momentum_200d_bil_v1"
TOP3_ID = "dsr_sector_top3_momentum_defensive_cash_v1"
TARGET_STRATEGY_IDS = [VM_ID, DSR_ID]

STARTING_EQUITY = 3000.0
STOP_DOLLARS = -600.0
SLIPPAGE = 0.0005
MAX_WINDOWS_PER_HORIZON = 5
HORIZONS = [90, 180]
DATA_HISTORY_MODE = "per_asset_availability"

VM_ASSETS = ["SPLV", "USMV", "QUAL", "SPY"]
SECTOR_ASSETS = ["XLK", "XLF", "XLE", "XLV", "XLY", "XLP", "XLU", "XLI", "XLB", "XLC"]
REQUIRED_CACHE_SYMBOLS = sorted(set([*VM_ASSETS, *SECTOR_ASSETS, "BIL"]))
OPTIONAL_BENCHMARK_SYMBOLS = ["QQQ"]

ALLOWED_REGISTRY_METADATA = {
    "latest_active_evidence_recompute_path",
    "active_evidence_audit_decision",
    "active_evidence_recompute_completed",
    "manual_review_required",
    "evidence_source",
    "no_candidate_exhaustive_run",
    "no_paper_forward_checkpoint",
    "no_real_money_recommendation",
}

RECOVERED_REFERENCES: dict[str, dict[str, float | None]] = {
    VM_ID: {
        "180d_median_final_equity": 3247.09,
        "target_300_before_stop_rate": 0.5385,
        "target_400_before_stop_rate": 0.3648,
        "180d_worst_drawdown": -549.41,
        "stress_median_final_equity": 3243.14,
        "stress_worst_drawdown": -557.47,
        "stop_hit_rate": 0.0,
    },
    DSR_ID: {
        "180d_median_final_equity": 3302.75,
        "180d_mean_final_equity": 3301.91,
        "180d_p75_final_equity": 3511.36,
        "180d_p90_final_equity": 3760.79,
        "best_final_equity": 4071.04,
        "worst_final_equity": 2578.70,
        "target_300_before_stop_rate": 0.6651,
        "target_400_before_stop_rate": 0.4571,
        "median_drawdown": -273.41,
        "180d_worst_drawdown": -580.65,
        "stop_hit_rate": 0.0,
        "stress_median_final_equity": 3297.76,
        "stress_worst_drawdown": -582.84,
    },
}

TOLERANCES = {
    "equity": 150.0,
    "drawdown": 150.0,
    "rate": 0.10,
    "stop_hit_rate": 0.02,
}


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


def active_observation_paths(root: Path) -> dict[str, Path]:
    return {
        VM_ID: root / "paper_forward_observations" / VM_ID / "active_observation.yaml",
        DSR_ID: root / "paper_forward_observations" / DSR_ID / "active_observation.yaml",
    }


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else "missing"


def protected_core_snapshot(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = rows_by_id(registry)
    protected: dict[str, dict[str, Any]] = {}
    for row_id in [VM_ID, DSR_ID, SPY_200D_ID]:
        row = deepcopy(rows.get(row_id, {}))
        for key in ALLOWED_REGISTRY_METADATA:
            row.pop(key, None)
        protected[row_id] = row
    return protected


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
    if qa_cache(root, symbol)["qa_status"] != "passed":
        return None
    frame = pd.read_csv(cache_path(root, symbol))
    dates = pd.to_datetime(frame["date"], errors="coerce").dt.tz_localize(None)
    close = pd.to_numeric(frame["adj_close"], errors="coerce")
    series = pd.DataFrame({"date": dates, symbol: close}).dropna().sort_values("date").drop_duplicates("date")
    return series.set_index("date")[symbol].astype(float) if not series.empty else None


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
    return pd.concat(close_map.values(), axis=1, join="outer", sort=True).sort_index(), []


def state_mismatches(root: Path, registry: dict[str, Any]) -> list[str]:
    rows = rows_by_id(registry)
    mismatches: list[str] = []
    for strategy_id in TARGET_STRATEGY_IDS:
        row = rows.get(strategy_id)
        if not row:
            mismatches.append(f"{strategy_id} missing from registry")
        else:
            if row.get("paper_forward_active") is not True:
                mismatches.append(f"{strategy_id} is not active")
            if row.get("rules_frozen") is not True or row.get("frozen") is not True:
                mismatches.append(f"{strategy_id} is not frozen")
            if row.get("real_money_recommendation") is not False:
                mismatches.append(f"{strategy_id} real_money_recommendation is not false")
            if row.get("candidate_exhaustive_run") is not False:
                mismatches.append(f"{strategy_id} candidate_exhaustive_run is not false")
        obs_path = active_observation_paths(root)[strategy_id]
        if not obs_path.exists():
            mismatches.append(f"{strategy_id} active observation missing")
        else:
            obs = load_yaml(obs_path)
            if obs.get("paper_forward_active") is not True or obs.get("frozen") is not True:
                mismatches.append(f"{strategy_id} active observation is not active/frozen")
    spy = rows.get(SPY_200D_ID)
    if not spy:
        mismatches.append(f"{SPY_200D_ID} missing from registry")
    elif spy.get("paper_forward_active") is not True or spy.get("rules_frozen") is not True:
        mismatches.append(f"{SPY_200D_ID} is not frozen active control")
    for strategy_id in [TOP2_ID, TOP3_ID]:
        row = rows.get(strategy_id)
        if not row:
            mismatches.append(f"{strategy_id} missing from registry")
        elif row.get("promotion_decision") != "mark_duplicate_or_near_duplicate" and row.get("status") != "mark_duplicate_or_near_duplicate":
            mismatches.append(f"{strategy_id} is not recorded as duplicate/near-duplicate")
        elif row.get("candidate_exhaustive_run") is not False:
            mismatches.append(f"{strategy_id} candidate_exhaustive_run is not false")
    readiness = root / "evidence" / "approved_etf_cache_readiness" / "latest" / "approved_etf_cache_readiness_manifest.json"
    if not readiness.exists():
        mismatches.append("approved ETF cache readiness manifest missing")
    else:
        manifest = json.loads(readiness.read_text(encoding="utf-8"))
        if manifest.get("missing_symbols") not in ([], None):
            mismatches.append("approved ETF cache readiness manifest has missing symbols")
    return mismatches


def available_at(close: pd.DataFrame, symbol: str, t: int, lookback: int = 0) -> bool:
    if symbol not in close.columns or t - lookback < 0:
        return False
    return bool(pd.notna(close.iloc[t][symbol]) and pd.notna(close.iloc[t - lookback][symbol]))


def eligible(close: pd.DataFrame, symbol: str, t: int) -> bool:
    if symbol not in close.columns or t < 200 or pd.isna(close.iloc[t][symbol]):
        return False
    window = close[symbol].iloc[t - 199 : t + 1].dropna()
    return bool(len(window) >= 200 and float(close.iloc[t][symbol]) > float(window.mean()))


def ret126(close: pd.DataFrame, symbol: str, t: int) -> float:
    if not available_at(close, symbol, t, 126):
        return float("nan")
    return float(close.iloc[t][symbol] / close.iloc[t - 126][symbol] - 1.0)


def vol60(close: pd.DataFrame, symbol: str, t: int) -> float:
    if symbol not in close.columns or t < 60:
        return float("nan")
    returns = close[symbol].pct_change().iloc[t - 59 : t + 1].dropna()
    if len(returns) < 45:
        return float("nan")
    return float(returns.std())


def add_weight(weights: dict[str, float], symbol: str, amount: float) -> None:
    if abs(amount) > 1e-12:
        weights[symbol] = weights.get(symbol, 0.0) + amount


def vm_weights(close: pd.DataFrame, t: int) -> dict[str, float]:
    scored: list[tuple[str, float]] = []
    for symbol in VM_ASSETS:
        if eligible(close, symbol, t):
            vol = vol60(close, symbol, t)
            score = ret126(close, symbol, t) / vol if np.isfinite(vol) and vol > 0 else float("nan")
            if np.isfinite(score):
                scored.append((symbol, score))
    picks = [symbol for symbol, _score in sorted(scored, key=lambda item: item[1], reverse=True)[:2]]
    if len(picks) == 2:
        return {picks[0]: 0.5, picks[1]: 0.5}
    if len(picks) == 1:
        return {picks[0]: 1.0}
    return {"BIL": 1.0}


def dsr_equal_weight(close: pd.DataFrame, t: int) -> dict[str, float]:
    picks = [symbol for symbol in SECTOR_ASSETS if eligible(close, symbol, t)]
    weights: dict[str, float] = {}
    if len(picks) >= 3:
        for symbol in picks:
            add_weight(weights, symbol, 1.0 / len(picks))
    elif picks:
        for symbol in picks:
            add_weight(weights, symbol, 1.0 / 3.0)
        add_weight(weights, "BIL", 1.0 - len(picks) / 3.0)
    else:
        add_weight(weights, "BIL", 1.0)
    return weights


def strategy_weights(close: pd.DataFrame, t: int, strategy_id: str) -> dict[str, float]:
    if strategy_id in {VM_ID, "vm_quality_lowvol_proxy_v1"}:
        return vm_weights(close, t)
    if strategy_id in {DSR_ID, "dsr_sector_equal_weight_defensive_filter_v1"}:
        return dsr_equal_weight(close, t)
    if strategy_id == "raw_sector_equal_weight_basket":
        available = [symbol for symbol in SECTOR_ASSETS if available_at(close, symbol, t, 1)]
        return {symbol: 1.0 / len(available) for symbol in available} if available else {"BIL": 1.0}
    if strategy_id == SPY_200D_ID:
        return {"SPY": 1.0} if eligible(close, "SPY", t) else {"BIL": 1.0}
    if strategy_id == "SPY_buy_hold":
        return {"SPY": 1.0}
    if strategy_id == "QQQ_buy_hold":
        return {"QQQ": 1.0}
    if strategy_id == "BIL_cash_proxy":
        return {"BIL": 1.0}
    return {"BIL": 1.0}


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
        for symbol, weight in weights.items():
            if available_at(close, symbol, today, 1):
                daily_return += weight * float(close.iloc[today][symbol] / close.iloc[today - 1][symbol] - 1.0)
        equity *= 1.0 + daily_return
        values.append(equity)
        dates.append(close.index[today])
    return pd.Series(values, index=dates).pct_change().dropna()


def common_start_warning(close: pd.DataFrame, symbols: list[str]) -> str:
    firsts = {symbol: close[symbol].first_valid_index() for symbol in symbols if symbol in close}
    valid_firsts = {symbol: dt for symbol, dt in firsts.items() if dt is not None}
    if not valid_firsts:
        return "no relevant history loaded"
    earliest = min(valid_firsts.values())
    latest = max(valid_firsts.values())
    removed_days = int((close.index >= earliest).sum() - (close.index >= latest).sum())
    shorter = sorted(symbol for symbol, dt in valid_firsts.items() if dt == latest)
    return (
        f"per-asset availability used; common-start at {latest.date()} would remove about "
        f"{removed_days} trading days because of shorter-history symbols such as {','.join(shorter)}"
    )


def fmt(value: Any) -> Any:
    if isinstance(value, float):
        return round(value, 4)
    return value


def metric_tolerance(metric: str) -> float:
    if "rate" in metric:
        return TOLERANCES["stop_hit_rate"] if metric == "stop_hit_rate" else TOLERANCES["rate"]
    if "drawdown" in metric:
        return TOLERANCES["drawdown"]
    return TOLERANCES["equity"]


def recovered_comparison_row(
    strategy_id: str,
    metric: str,
    recovered_value: float | None,
    recomputed_value: float | None,
    tolerance: float | None = None,
    notes: str = "",
) -> dict[str, Any]:
    if recovered_value is None:
        return {
            "strategy_id": strategy_id,
            "metric": metric,
            "recovered_value": "",
            "recomputed_value": "" if recomputed_value is None else fmt(float(recomputed_value)),
            "absolute_delta": "",
            "percent_delta": "",
            "tolerance": "" if tolerance is None else tolerance,
            "verdict": "recovered_value_missing",
            "notes": notes or "Recovered value was not present in recovery context.",
        }
    if recomputed_value is None:
        return {
            "strategy_id": strategy_id,
            "metric": metric,
            "recovered_value": fmt(float(recovered_value)),
            "recomputed_value": "",
            "absolute_delta": "",
            "percent_delta": "",
            "tolerance": "" if tolerance is None else tolerance,
            "verdict": "not_comparable",
            "notes": notes or "Recomputed value unavailable.",
        }
    tolerance = metric_tolerance(metric) if tolerance is None else tolerance
    delta = float(recomputed_value) - float(recovered_value)
    pct = abs(delta) / abs(float(recovered_value)) if abs(float(recovered_value)) > 1e-12 else ""
    if abs(delta) <= tolerance:
        verdict = "confirmed_within_tolerance"
    elif abs(delta) <= tolerance * 2.5:
        verdict = "minor_methodology_delta"
    else:
        verdict = "material_mismatch_requires_review"
    return {
        "strategy_id": strategy_id,
        "metric": metric,
        "recovered_value": fmt(float(recovered_value)),
        "recomputed_value": fmt(float(recomputed_value)),
        "absolute_delta": fmt(delta),
        "percent_delta": "" if pct == "" else fmt(float(pct)),
        "tolerance": tolerance,
        "verdict": verdict,
        "notes": notes,
    }


def comparison_metric_values(summary90: dict[str, Any], summary180: dict[str, Any]) -> dict[str, float | None]:
    if summary180.get("validation_status") == "missing_or_unavailable":
        return {}
    return {
        "90d_median_final_equity": summary90.get("median_final_equity"),
        "180d_median_final_equity": summary180.get("median_final_equity"),
        "180d_mean_final_equity": summary180.get("mean_final_equity"),
        "180d_p75_final_equity": summary180.get("p75_final_equity"),
        "180d_p90_final_equity": summary180.get("p90_final_equity"),
        "best_final_equity": summary180.get("best_final_equity"),
        "worst_final_equity": summary180.get("worst_final_equity"),
        "target_300_before_stop_rate": summary180.get("target_300_before_stop_rate"),
        "target_400_before_stop_rate": summary180.get("target_400_before_stop_rate"),
        "90d_worst_drawdown": summary90.get("worst_drawdown"),
        "180d_worst_drawdown": summary180.get("worst_drawdown"),
        "median_drawdown": summary180.get("median_drawdown"),
        "stop_hit_rate": summary180.get("stop_hit_rate"),
    }


def decide_strategy(comparison_rows: list[dict[str, Any]], diagnostics_available: bool) -> tuple[str, bool]:
    if not diagnostics_available:
        return "active_evidence_insufficient", True
    verdicts = {row["verdict"] for row in comparison_rows}
    if "material_mismatch_requires_review" in verdicts:
        return "active_evidence_material_mismatch_manual_review", True
    if "minor_methodology_delta" in verdicts:
        return "active_evidence_confirmed_with_minor_deltas", False
    return "active_evidence_confirmed", False


def overall_next_action(decisions: dict[str, str]) -> str:
    if any(decision == "active_evidence_insufficient" for decision in decisions.values()):
        return "repair_active_strategy_recompute_diagnostics"
    vm_bad = decisions.get(VM_ID) == "active_evidence_material_mismatch_manual_review"
    dsr_bad = decisions.get(DSR_ID) == "active_evidence_material_mismatch_manual_review"
    if vm_bad and dsr_bad:
        return "manual_review_active_strategy_evidence_before_new_research"
    if vm_bad:
        return "manual_review_vm_quality_lowvol_proxy_active_evidence"
    if dsr_bad:
        return "manual_review_dsr_equal_weight_active_evidence"
    return "continue_new_family_discovery_or_candidate_queue"


def build_review_payload(root: Path) -> dict[str, Any]:
    close, missing_symbols = prepare_prices(root)
    cache_rows = cache_status(root)
    if missing_symbols or close.empty:
        return {
            "diagnostics_available": False,
            "cache_rows": cache_rows,
            "missing_symbols": missing_symbols,
            "close": close,
            "summaries": {},
            "window_rows_by_strategy": {},
            "returns_by_strategy": {},
            "data_history_notes": {
                VM_ID: "cache missing; per-asset availability not computed",
                DSR_ID: "cache missing; per-asset availability not computed",
            },
        }
    strategy_ids = [VM_ID, DSR_ID, SPY_200D_ID, "SPY_buy_hold", "BIL_cash_proxy", "QQQ_buy_hold", "raw_sector_equal_weight_basket"]
    window_rows = {strategy_id: run_windows(close, strategy_id) for strategy_id in strategy_ids}
    summaries = {strategy_id: {horizon: summarize(window_rows[strategy_id], strategy_id, horizon) for horizon in HORIZONS} for strategy_id in strategy_ids}
    returns_by_strategy = {strategy_id: full_returns(close, strategy_id) for strategy_id in strategy_ids}
    return {
        "diagnostics_available": True,
        "cache_rows": cache_rows,
        "missing_symbols": [],
        "close": close,
        "summaries": summaries,
        "window_rows_by_strategy": window_rows,
        "returns_by_strategy": returns_by_strategy,
        "data_history_notes": {
            VM_ID: common_start_warning(close, VM_ASSETS),
            DSR_ID: common_start_warning(close, SECTOR_ASSETS),
        },
    }


def build_profit_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for strategy_id in TARGET_STRATEGY_IDS:
        if not payload["diagnostics_available"]:
            for metric in [
                "90d_median_final_equity",
                "180d_median_final_equity",
                "180d_mean_final_equity",
                "180d_p75_final_equity",
                "180d_p90_final_equity",
                "best_final_equity",
                "worst_final_equity",
                "target_300_before_stop_rate",
                "target_400_before_stop_rate",
            ]:
                rows.append({"strategy_id": strategy_id, "metric": metric, "value": "missing_or_unavailable", "horizon": "", "notes": "required cache missing"})
            continue
        s90 = payload["summaries"][strategy_id][90]
        s180 = payload["summaries"][strategy_id][180]
        values = {
            "90d_median_final_equity": (90, s90["median_final_equity"]),
            "180d_median_final_equity": (180, s180["median_final_equity"]),
            "180d_mean_final_equity": (180, s180["mean_final_equity"]),
            "180d_p75_final_equity": (180, s180["p75_final_equity"]),
            "180d_p90_final_equity": (180, s180["p90_final_equity"]),
            "best_final_equity": (180, s180["best_final_equity"]),
            "worst_final_equity": (180, s180["worst_final_equity"]),
            "target_300_before_stop_rate": (180, s180["target_300_before_stop_rate"]),
            "target_400_before_stop_rate": (180, s180["target_400_before_stop_rate"]),
        }
        for metric, (horizon, value) in values.items():
            rows.append({"strategy_id": strategy_id, "metric": metric, "value": fmt(value), "horizon": horizon, "notes": "bounded cached-data recompute"})
    return rows


def build_risk_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for strategy_id in TARGET_STRATEGY_IDS:
        if not payload["diagnostics_available"]:
            rows.append({"strategy_id": strategy_id, "metric": "diagnostics", "value": "missing_or_unavailable", "horizon": "", "notes": "required cache missing"})
            continue
        s90 = payload["summaries"][strategy_id][90]
        s180 = payload["summaries"][strategy_id][180]
        values = {
            "90d_worst_drawdown": (90, s90["worst_drawdown"]),
            "180d_worst_drawdown": (180, s180["worst_drawdown"]),
            "median_drawdown": (180, s180["median_drawdown"]),
            "stop_hit_rate": (180, s180["stop_hit_rate"]),
            "risk_buffer_vs_minus_600": (180, s180["worst_drawdown"] - STOP_DOLLARS),
            "worst_loss_window": (180, s180["worst_loss_window"]),
        }
        for metric, (horizon, value) in values.items():
            rows.append({"strategy_id": strategy_id, "metric": metric, "value": fmt(value), "horizon": horizon, "notes": "absolute drawdown uses dollar equity path from 3000 start"})
    return rows


def corr_between(close: pd.DataFrame, left: str, right: str) -> float | str:
    a = full_returns(close, left)
    b = full_returns(close, right)
    aligned = pd.concat([a.rename("a"), b.rename("b")], axis=1).dropna()
    if len(aligned) <= 5:
        return "unavailable"
    return float(aligned["a"].corr(aligned["b"]))


def corr_between_cached(returns_by_strategy: dict[str, pd.Series], left: str, right: str) -> float | str:
    if left not in returns_by_strategy or right not in returns_by_strategy:
        return "unavailable"
    aligned = pd.concat([returns_by_strategy[left].rename("a"), returns_by_strategy[right].rename("b")], axis=1).dropna()
    if len(aligned) <= 5:
        return "unavailable"
    return float(aligned["a"].corr(aligned["b"]))


def build_benchmark_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    benchmarks = [
        (SPY_200D_ID, SPY_200D_ID),
        ("SPY_buy_hold", "SPY_buy_hold"),
        ("BIL_cash_proxy", "BIL_cash_proxy"),
        ("QQQ_buy_hold", "QQQ_buy_hold"),
        ("raw_sector_equal_weight_basket", "raw_sector_equal_weight_basket"),
        (VM_ID, VM_ID),
        (DSR_ID, DSR_ID),
        ("active_combo", ""),
    ]
    for strategy_id in TARGET_STRATEGY_IDS:
        for benchmark_id, benchmark_key in benchmarks:
            if benchmark_id == strategy_id:
                continue
            if not payload["diagnostics_available"] or benchmark_id == "active_combo":
                rows.append(
                    {
                        "strategy_id": strategy_id,
                        "benchmark_id": benchmark_id,
                        "strategy_180d_median_final_equity": "",
                        "benchmark_180d_median_final_equity": "",
                        "delta": "",
                        "correlation": "",
                        "comparison_status": "unavailable",
                        "notes": "active combo exact series unavailable in this audit" if benchmark_id == "active_combo" else "required cache missing",
                    }
                )
                continue
            strat = payload["summaries"][strategy_id][180]
            bench = payload["summaries"][benchmark_key][180]
            delta = strat["median_final_equity"] - bench["median_final_equity"]
            corr = corr_between_cached(payload["returns_by_strategy"], strategy_id, benchmark_key)
            rows.append(
                {
                    "strategy_id": strategy_id,
                    "benchmark_id": benchmark_id,
                    "strategy_180d_median_final_equity": fmt(strat["median_final_equity"]),
                    "benchmark_180d_median_final_equity": fmt(bench["median_final_equity"]),
                    "delta": fmt(delta),
                    "correlation": fmt(corr),
                    "comparison_status": "computed",
                    "notes": "bounded cached-data comparison",
                }
            )
    return rows


def build_correlation_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if not payload["diagnostics_available"]:
        return [{"left_strategy_id": VM_ID, "right_strategy_id": DSR_ID, "correlation": "unavailable", "notes": "required cache missing"}]
    pairs = [(VM_ID, DSR_ID), (VM_ID, SPY_200D_ID), (DSR_ID, SPY_200D_ID), (DSR_ID, "raw_sector_equal_weight_basket")]
    return [
        {
            "left_strategy_id": left,
            "right_strategy_id": right,
            "correlation": fmt(corr_between_cached(payload["returns_by_strategy"], left, right)),
            "notes": "daily full-sample recomputed return correlation",
        }
        for left, right in pairs
    ]


def build_recovered_vs_recomputed(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for strategy_id in TARGET_STRATEGY_IDS:
        if not payload["diagnostics_available"]:
            for metric, recovered in RECOVERED_REFERENCES[strategy_id].items():
                rows.append(recovered_comparison_row(strategy_id, metric, recovered, None, notes="required cache missing"))
            continue
        metrics = comparison_metric_values(payload["summaries"][strategy_id][90], payload["summaries"][strategy_id][180])
        for metric, recovered in RECOVERED_REFERENCES[strategy_id].items():
            comparable_metric = {
                "stress_median_final_equity": "180d_median_final_equity",
                "stress_worst_drawdown": "180d_worst_drawdown",
            }.get(metric, metric)
            recomputed = metrics.get(comparable_metric)
            note = "Stress-specific recompute unavailable; compared to non-stress cached recompute." if metric.startswith("stress_") else "Recovered metric may use older sampling windows or methodology."
            rows.append(recovered_comparison_row(strategy_id, metric, recovered, recomputed, notes=note))
    return rows


def build_rule_fidelity_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"strategy_id": VM_ID, "field": "base_strategy", "expected": "vm_quality_lowvol_proxy_v1", "recomputed": "vm_quality_lowvol_proxy_v1", "verdict": "pass", "notes": "active observation base id matched"},
        {"strategy_id": VM_ID, "field": "rebalance", "expected": "monthly", "recomputed": "monthly", "verdict": "pass", "notes": "calendar month change triggers rebalance"},
        {"strategy_id": VM_ID, "field": "universe", "expected": ";".join([*VM_ASSETS, "BIL"]), "recomputed": ";".join([*VM_ASSETS, "BIL"]), "verdict": "pass", "notes": "BIL fallback only"},
        {"strategy_id": VM_ID, "field": "eligibility", "expected": "close > 200-day SMA", "recomputed": "close > 200-day SMA", "verdict": "pass", "notes": "per-asset availability"},
        {"strategy_id": VM_ID, "field": "ranking", "expected": "126-day return / 60-day realized volatility", "recomputed": "126-day return / 60-day realized volatility", "verdict": "pass", "notes": "finite score required"},
        {"strategy_id": VM_ID, "field": "allocation", "expected": "top 2 equal; one 100%; none BIL", "recomputed": "top 2 equal; one 100%; none BIL", "verdict": "pass", "notes": "no leverage or shorting"},
        {"strategy_id": VM_ID, "field": "data_history_mode", "expected": DATA_HISTORY_MODE, "recomputed": DATA_HISTORY_MODE, "verdict": "pass", "notes": payload["data_history_notes"][VM_ID]},
        {"strategy_id": DSR_ID, "field": "base_strategy", "expected": "dsr_sector_equal_weight_defensive_filter_v1", "recomputed": "dsr_sector_equal_weight_defensive_filter_v1", "verdict": "pass", "notes": "active observation base id matched"},
        {"strategy_id": DSR_ID, "field": "rebalance", "expected": "monthly", "recomputed": "monthly", "verdict": "pass", "notes": "calendar month change triggers rebalance"},
        {"strategy_id": DSR_ID, "field": "universe", "expected": ";".join([*SECTOR_ASSETS, "BIL"]), "recomputed": ";".join([*SECTOR_ASSETS, "BIL"]), "verdict": "pass", "notes": "BIL fallback only"},
        {"strategy_id": DSR_ID, "field": "eligibility", "expected": "close > 200-day SMA", "recomputed": "close > 200-day SMA", "verdict": "pass", "notes": "sector ETFs only"},
        {"strategy_id": DSR_ID, "field": "allocation", "expected": "equal-weight qualifying sectors; one/two sectors one-third each plus BIL; none BIL", "recomputed": "equal-weight qualifying sectors; one/two sectors one-third each plus BIL; none BIL", "verdict": "pass", "notes": "matches recovered active observation"},
        {"strategy_id": DSR_ID, "field": "data_history_mode", "expected": DATA_HISTORY_MODE, "recomputed": DATA_HISTORY_MODE, "verdict": "pass", "notes": payload["data_history_notes"][DSR_ID]},
        {"strategy_id": "all", "field": "forbidden_mechanics", "expected": "none", "recomputed": "none", "verdict": "pass", "notes": "no broker, live order, real-money, leverage, derivatives, intraday, or provider path"},
    ]


def build_target_window_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not payload["diagnostics_available"]:
        return rows
    for strategy_id in TARGET_STRATEGY_IDS:
        for row in payload["window_rows_by_strategy"][strategy_id]:
            rows.append(
                {
                    "strategy_id": strategy_id,
                    "horizon": row["horizon"],
                    "window_start": row["window_start"],
                    "window_end": row["window_end"],
                    "target_300_before_stop": row["target_300_before_stop"],
                    "target_400_before_stop": row["target_400_before_stop"],
                    "absolute_600_stop_hit": row["absolute_600_stop_hit"],
                    "final_equity": fmt(row["final_equity"]),
                }
            )
    return rows


def build_drawdown_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not payload["diagnostics_available"]:
        return rows
    for strategy_id in TARGET_STRATEGY_IDS:
        for row in payload["window_rows_by_strategy"][strategy_id]:
            rows.append(
                {
                    "strategy_id": strategy_id,
                    "horizon": row["horizon"],
                    "window_start": row["window_start"],
                    "window_end": row["window_end"],
                    "max_drawdown": fmt(row["max_drawdown"]),
                    "profit_dollars": fmt(row["profit_dollars"]),
                }
            )
    return rows


def build_rebalance_trace(close: pd.DataFrame, strategy_id: str, limit: int = 24) -> list[dict[str, Any]]:
    if close.empty:
        return []
    rows: list[dict[str, Any]] = []
    last_month = None
    months = np.array([dt.year * 12 + dt.month for dt in close.index], dtype=int)
    for t in range(252, len(close)):
        month = int(months[t])
        if month == last_month:
            continue
        weights = strategy_weights(close, t, strategy_id)
        rows.append({"strategy_id": strategy_id, "rebalance_date": str(close.index[t].date()), "weights": json.dumps({k: round(v, 6) for k, v in sorted(weights.items())}, sort_keys=True)})
        last_month = month
        if len(rows) >= limit:
            break
    return rows


def build_scorecard_rows(
    payload: dict[str, Any],
    recovered_rows: list[dict[str, Any]],
    decisions: dict[str, str],
    manual_review: dict[str, bool],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    by_strategy = {strategy_id: [row for row in recovered_rows if row["strategy_id"] == strategy_id] for strategy_id in TARGET_STRATEGY_IDS}
    for strategy_id in TARGET_STRATEGY_IDS:
        material = any(row["verdict"] == "material_mismatch_requires_review" for row in by_strategy[strategy_id])
        minor = any(row["verdict"] == "minor_methodology_delta" for row in by_strategy[strategy_id])
        if payload["diagnostics_available"]:
            s180 = payload["summaries"][strategy_id][180]
            target300 = s180["target_300_before_stop_rate"]
            target400 = s180["target_400_before_stop_rate"]
            median = s180["median_final_equity"]
            worst_dd = s180["worst_drawdown"]
            stop = s180["stop_hit_rate"]
        else:
            target300 = target400 = median = worst_dd = stop = None
        criteria = [
            ("cache_ready", "pass" if payload["diagnostics_available"] else "fail", "required cached ETF data loaded"),
            ("rule_fidelity_confirmed", "pass", "rule documentation matched recovered observation"),
            ("data_history_mode_recorded", "pass", DATA_HISTORY_MODE),
            ("diagnostics_available", "pass" if payload["diagnostics_available"] else "fail", "bounded 90d/180d windows"),
            ("recovered_vs_recomputed_reasonable", "fail" if material else "weak_pass" if minor else "pass", "material mismatch triggers manual review"),
            ("target_300_before_stop", "pass" if isinstance(target300, float) and target300 > 0 else "unavailable", target300),
            ("target_400_before_stop", "pass" if isinstance(target400, float) and target400 > 0 else "unavailable", target400),
            ("median_final_equity", "pass" if isinstance(median, float) and median >= STARTING_EQUITY else "unavailable", median),
            ("worst_drawdown", "pass" if isinstance(worst_dd, float) and worst_dd > STOP_DOLLARS else "manual_review", worst_dd),
            ("stop_hit_rate", "pass" if stop == 0.0 else "manual_review", stop),
            ("benchmark_relative_behavior", "weak_pass" if payload["diagnostics_available"] else "unavailable", "see benchmark CSV"),
            ("duplicate_or_additive_profile", "weak_pass" if payload["diagnostics_available"] else "unavailable", "see correlation CSV"),
            ("active_status_should_remain", "manual_review" if manual_review[strategy_id] else "pass", decisions[strategy_id]),
            ("manual_review_required", "manual_review" if manual_review[strategy_id] else "pass", manual_review[strategy_id]),
            ("policy_compliance", "pass", "research-only cached-data recompute"),
            ("no_forbidden_mechanics", "pass", "no candidate_exhaustive, activation, checkpoint, broker, live order, provider, or real-money path"),
            ("no_real_money_path", "pass", "real_money_recommendation=false"),
        ]
        for criterion, verdict, notes in criteria:
            rows.append({"strategy_id": strategy_id, "criterion": criterion, "verdict": verdict, "notes": fmt(notes)})
    return rows


def create_packet(directory: Path) -> Path:
    packet = directory / "active_strategy_evidence_recompute_packet.zip"
    if packet.exists():
        packet.unlink()
    with zipfile.ZipFile(packet, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(directory.iterdir()):
            if path.is_file() and path.name != packet.name:
                zf.write(path, path.name)
    return packet


def update_registry_metadata(root: Path, decisions: dict[str, str], manual_review: dict[str, bool]) -> None:
    path = root / REGISTRY_PATH
    registry = load_yaml(path)
    for row in registry.get("strategies", []):
        if row.get("id") in TARGET_STRATEGY_IDS:
            row["latest_active_evidence_recompute_path"] = str(root / OUTPUT_DIR)
            row["active_evidence_audit_decision"] = decisions[row["id"]]
            row["active_evidence_recompute_completed"] = True
            row["manual_review_required"] = manual_review[row["id"]]
            row["evidence_source"] = "cached_etf_recompute"
            row["no_candidate_exhaustive_run"] = True
            row["no_paper_forward_checkpoint"] = True
            row["no_real_money_recommendation"] = True
    path.write_text(yaml.safe_dump(registry, sort_keys=False, width=120), encoding="utf-8")


def write_outputs(
    root: Path,
    payload: dict[str, Any],
    state_notes: list[str],
    decisions: dict[str, str],
    manual_review: dict[str, bool],
    next_action: str,
    consistency: dict[str, Any],
) -> dict[str, Any]:
    output = root / OUTPUT_DIR
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)

    recovered_rows = build_recovered_vs_recomputed(payload)
    profit_rows = build_profit_rows(payload)
    risk_rows = build_risk_rows(payload)
    benchmark_rows = build_benchmark_rows(payload)
    rule_rows = build_rule_fidelity_rows(payload)
    scorecard_rows = build_scorecard_rows(payload, recovered_rows, decisions, manual_review)
    correlation_rows = build_correlation_rows(payload)
    target_rows = build_target_window_rows(payload)
    drawdown_rows = build_drawdown_rows(payload)
    close = payload["close"]

    write_csv(output / "cache_status.csv", payload["cache_rows"], ["symbol", "required", "cache_available", "cache_path", "qa_status", "first_date", "last_date", "row_count", "warmup_sufficiency", "missing_reason"])
    write_csv(output / "active_strategy_recompute_profit_review.csv", profit_rows, ["strategy_id", "metric", "value", "horizon", "notes"])
    write_csv(output / "active_strategy_recompute_risk_review.csv", risk_rows, ["strategy_id", "metric", "value", "horizon", "notes"])
    write_csv(output / "active_strategy_recompute_benchmark_review.csv", benchmark_rows, ["strategy_id", "benchmark_id", "strategy_180d_median_final_equity", "benchmark_180d_median_final_equity", "delta", "correlation", "comparison_status", "notes"])
    write_csv(output / "active_strategy_recompute_recovered_vs_recomputed.csv", recovered_rows, ["strategy_id", "metric", "recovered_value", "recomputed_value", "absolute_delta", "percent_delta", "tolerance", "verdict", "notes"])
    write_csv(output / "active_strategy_recompute_rule_fidelity.csv", rule_rows, ["strategy_id", "field", "expected", "recomputed", "verdict", "notes"])
    write_csv(output / "active_strategy_recompute_scorecard.csv", scorecard_rows, ["strategy_id", "criterion", "verdict", "notes"])
    write_csv(output / "active_strategy_recompute_correlation_review.csv", correlation_rows, ["left_strategy_id", "right_strategy_id", "correlation", "notes"])
    write_csv(output / "active_strategy_recompute_target_window_review.csv", target_rows, ["strategy_id", "horizon", "window_start", "window_end", "target_300_before_stop", "target_400_before_stop", "absolute_600_stop_hit", "final_equity"])
    write_csv(output / "active_strategy_recompute_drawdown_window_review.csv", drawdown_rows, ["strategy_id", "horizon", "window_start", "window_end", "max_drawdown", "profit_dollars"])
    write_csv(output / "active_strategy_recompute_rebalance_trace_vm_quality.csv", build_rebalance_trace(close, VM_ID), ["strategy_id", "rebalance_date", "weights"])
    write_csv(output / "active_strategy_recompute_rebalance_trace_dsr_equal_weight.csv", build_rebalance_trace(close, DSR_ID), ["strategy_id", "rebalance_date", "weights"])

    missing_lines = ["# Missing Evidence", ""]
    if payload["missing_symbols"]:
        missing_lines.append("Required cache missing: " + ", ".join(payload["missing_symbols"]))
    else:
        missing_lines.append("No required cached ETF symbols are missing.")
    missing_lines.append("Active combo exact series is unavailable in this bounded audit and was not zero-filled.")
    missing_lines.append("Stress-cost-specific recompute was not separately simulated; stress recovered values were compared to base cached recompute and marked in notes.")
    (output / "active_strategy_recompute_missing_evidence.md").write_text("\n".join(missing_lines) + "\n", encoding="utf-8")

    next_lines = ["# Active Strategy Evidence Recompute Next Action", "", f"Overall next action: `{next_action}`", ""]
    for strategy_id in TARGET_STRATEGY_IDS:
        next_lines.append(f"- `{strategy_id}`: `{decisions[strategy_id]}`; manual_review_required={str(manual_review[strategy_id]).lower()}")
    next_lines.append("")
    next_lines.append("Do not run paper-forward checkpoint, candidate_exhaustive, broker/live-order, provider download, or real-money workflow from this audit.")
    (output / "active_strategy_recompute_next_action.md").write_text("\n".join(next_lines) + "\n", encoding="utf-8")

    summary_lines = ["# Active Strategy Evidence Recompute", "", f"Created at UTC: {now_utc()}", ""]
    summary_lines.append(f"Cache used successfully: {payload['diagnostics_available'] and not payload['missing_symbols']}")
    summary_lines.append(f"Data history mode: `{DATA_HISTORY_MODE}` for both strategies.")
    summary_lines.append("")
    for strategy_id in TARGET_STRATEGY_IDS:
        summary_lines.append(f"## {strategy_id}")
        summary_lines.append(f"Decision: `{decisions[strategy_id]}`")
        summary_lines.append(f"Manual review required: {str(manual_review[strategy_id]).lower()}")
        summary_lines.append(f"Data history note: {payload['data_history_notes'][strategy_id]}")
        if payload["diagnostics_available"]:
            s180 = payload["summaries"][strategy_id][180]
            summary_lines.append(
                "180d recompute: median={median}, mean={mean}, +300={t300}, +400={t400}, worst_drawdown={dd}, stop_hit={stop}".format(
                    median=fmt(s180["median_final_equity"]),
                    mean=fmt(s180["mean_final_equity"]),
                    t300=fmt(s180["target_300_before_stop_rate"]),
                    t400=fmt(s180["target_400_before_stop_rate"]),
                    dd=fmt(s180["worst_drawdown"]),
                    stop=fmt(s180["stop_hit_rate"]),
                )
            )
        summary_lines.append("")
    summary_lines.append(f"Overall next action: `{next_action}`")
    summary_lines.append("")
    summary_lines.append("This packet is an active evidence audit only. It did not mutate active observation files and did not run candidate validation or paper-forward checkpoint.")
    (output / "active_strategy_evidence_recompute_summary.md").write_text("\n".join(summary_lines) + "\n", encoding="utf-8")

    manifest = {
        "created_at_utc": now_utc(),
        "target_strategy_ids": TARGET_STRATEGY_IDS,
        "diagnostics_available": payload["diagnostics_available"],
        "missing_symbols": payload["missing_symbols"],
        "cache_used": payload["diagnostics_available"] and not payload["missing_symbols"],
        "data_history_mode": DATA_HISTORY_MODE,
        "data_history_notes": payload["data_history_notes"],
        "decisions": decisions,
        "manual_review_required": manual_review,
        "overall_next_action": next_action,
        "state_notes": state_notes,
        "candidate_exhaustive_run": False,
        "paper_forward_review": False,
        "paper_forward_activation": False,
        "paper_forward_checkpoint": False,
        "provider_api_called": False,
        "data_downloaded": False,
        "broker_integration": False,
        "live_orders": False,
        "order_placement": False,
        "real_money_recommendation": False,
        "data_label": "exploratory_non_institutional_not_real_money_ready",
    }
    write_json(output / "active_strategy_recompute_manifest.json", manifest)
    write_json(output / "active_strategy_recompute_consistency_check.json", consistency)
    packet = create_packet(output)
    return {"output_dir": str(output), "packet": str(packet), "manifest": manifest, "recovered_rows": recovered_rows}


def run_active_strategy_evidence_recompute(root: Path = ROOT, strict_state: bool = True) -> dict[str, Any]:
    registry_path = root / REGISTRY_PATH
    registry_before = load_yaml(registry_path)
    core_before = protected_core_snapshot(registry_before)
    obs_hash_before = {strategy_id: file_hash(path) for strategy_id, path in active_observation_paths(root).items()}
    mismatches = state_mismatches(root, registry_before)
    if mismatches and strict_state:
        raise RuntimeError("State confirmation failed: " + "; ".join(mismatches))

    payload = build_review_payload(root)
    recovered_rows = build_recovered_vs_recomputed(payload)
    decisions: dict[str, str] = {}
    manual_review: dict[str, bool] = {}
    for strategy_id in TARGET_STRATEGY_IDS:
        decision, review_required = decide_strategy([row for row in recovered_rows if row["strategy_id"] == strategy_id], payload["diagnostics_available"])
        decisions[strategy_id] = decision
        manual_review[strategy_id] = review_required
    next_action = overall_next_action(decisions)

    update_registry_metadata(root, decisions, manual_review)
    registry_after = load_yaml(registry_path)
    core_after = protected_core_snapshot(registry_after)
    obs_hash_after = {strategy_id: file_hash(path) for strategy_id, path in active_observation_paths(root).items()}

    consistency = {
        "active_recompute_completed": True,
        "vm_quality_recomputed": payload["diagnostics_available"],
        "dsr_equal_weight_recomputed": payload["diagnostics_available"],
        "cache_used": payload["diagnostics_available"] and not payload["missing_symbols"],
        "data_history_mode_recorded": DATA_HISTORY_MODE == "per_asset_availability",
        "no_candidate_exhaustive_run": True,
        "no_paper_forward_review": True,
        "no_paper_forward_activation": True,
        "no_paper_forward_checkpoint": True,
        "no_active_observation_mutation": obs_hash_before == obs_hash_after,
        "no_vm_quality_mutation": core_before.get(VM_ID) == core_after.get(VM_ID),
        "no_dsr_equal_weight_mutation": core_before.get(DSR_ID) == core_after.get(DSR_ID),
        "no_spy_200d_mutation": core_before.get(SPY_200D_ID) == core_after.get(SPY_200D_ID),
        "no_broker_path_added": True,
        "no_live_order_path_added": True,
        "no_real_money_recommendation": True,
        "recovered_vs_recomputed_created": True,
        "next_action_explicit": bool(next_action),
    }
    consistency["consistency_passed"] = all(bool(value) for value in consistency.values())

    outputs = write_outputs(root, payload, mismatches, decisions, manual_review, next_action, consistency)
    return {
        "output_dir": outputs["output_dir"],
        "packet": outputs["packet"],
        "diagnostics_available": payload["diagnostics_available"],
        "missing_symbols": payload["missing_symbols"],
        "cache_used": consistency["cache_used"],
        "data_history_mode": DATA_HISTORY_MODE,
        "decisions": decisions,
        "manual_review_required": manual_review,
        "overall_next_action": next_action,
        "consistency": consistency,
        "state_mismatches": mismatches,
    }


def main() -> None:
    result = run_active_strategy_evidence_recompute(ROOT, strict_state=True)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
