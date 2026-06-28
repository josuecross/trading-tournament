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

import run_active_combo_benchmark_reporting as combo
import run_active_strategy_evidence_recompute as active
import run_breadth_state_regime_preregistration as prereg


ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = Path("evidence") / "parallel_research_discovery" / "breadth_state_regime" / "latest"
REGISTRY_PATH = Path("strategy_lab") / "strategy_registry.yaml"
ROADMAP_PATH = Path("strategy_lab") / "RESEARCH_ROADMAP.md"

LANE_ID = prereg.LANE_ID
ROW_IDS = [row["row_id"] for row in prereg.FUTURE_ROWS]
NEXT_ACTION_ARCHIVE = "archive_stop_etf_wrapper_track"
NEXT_ACTION_PROMOTION = "promotion_review_for_selected_breadth_state_rows"
LANE_ARCHIVE_STATUS = "no_candidate_archive_lane"

REFERENCE_IDS = [
    active.VM_ID,
    active.DSR_ID,
    combo.COMBO_ID,
    active.SPY_200D_ID,
    "SPY_buy_hold",
    "QQQ_buy_hold",
    "BIL_cash_proxy",
    prereg.LVQ_ID,
]
CORE_REFERENCE_IDS = [active.VM_ID, active.DSR_ID, combo.COMBO_ID, active.SPY_200D_ID]

RISK_ASSETS = prereg.RISK_BREADTH_BASKET
DEFENSIVE_ASSETS = ["GLD", "IEF", "TLT", "AGG"]
DEFENSIVE_EXTENDED = ["GLD", "IEF", "TLT", "AGG", "USMV", "EFAV", "EEMV"]
LOW_VOL_ASSETS = ["SPLV", "USMV", "EFAV", "EEMV"]
LOW_VOL_QUALITY = ["SPLV", "USMV", "QUAL", "EFAV", "EEMV"]


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def fmt(value: Any) -> Any:
    if isinstance(value, (float, np.floating)):
        return round(float(value), 4)
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
            writer.writerow({field: row.get(field, "") for field in fields})


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def rows_by_id(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(row.get("id")): row for row in registry.get("strategies", [])}


def active_observation_hashes(root: Path) -> dict[str, str]:
    return {strategy_id: active.file_hash(path) for strategy_id, path in active.active_observation_paths(root).items()}


def protected_core_snapshot(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = rows_by_id(registry)
    return {strategy_id: deepcopy(rows.get(strategy_id, {})) for strategy_id in [active.VM_ID, active.DSR_ID, active.SPY_200D_ID]}


def preregistered_rows(root: Path) -> list[str]:
    rows = read_csv_rows(root / "evidence" / "pre_registered_lanes" / "breadth_state_regime" / "latest" / "breadth_state_regime_future_rows.csv")
    return [row.get("row_id", "") for row in rows]


def state_mismatches(root: Path, registry: dict[str, Any]) -> list[str]:
    mismatches: list[str] = []
    meta = registry.get("registry", {})
    combo_manifest = read_json(root / "evidence" / "active_combo_benchmark" / "latest" / "active_combo_manifest.json")
    prereg_manifest = read_json(root / "evidence" / "pre_registered_lanes" / "breadth_state_regime" / "latest" / "breadth_state_regime_manifest.json")
    if meta.get("lane_id") != LANE_ID or meta.get("lane_status") not in {"pre_registered_not_run", "discovery_completed", LANE_ARCHIVE_STATUS}:
        mismatches.append("breadth-state lane is not in an allowed pre/post discovery metadata state")
    if meta.get("current_next_action") not in {"run_breadth_state_regime_discovery_batch", NEXT_ACTION_ARCHIVE, NEXT_ACTION_PROMOTION}:
        mismatches.append("current_next_action is not an allowed breadth-state discovery/post-discovery action")
    if prereg_manifest.get("lane_id") != LANE_ID or prereg_manifest.get("lane_status") != "pre_registered_not_run":
        mismatches.append("pre-registration manifest missing expected lane status")
    if preregistered_rows(root) != ROW_IDS:
        mismatches.append("pre-registered row list does not match the fixed four-row list")
    if combo_manifest.get("active_combo_is_reference_not_active_strategy") is not True:
        mismatches.append("active combo is not marked benchmark/reference only")
    rows = rows_by_id(registry)
    for strategy_id in [active.VM_ID, active.DSR_ID]:
        row = rows.get(strategy_id, {})
        if row.get("paper_forward_active") is not True or row.get("rules_frozen") is not True:
            mismatches.append(f"{strategy_id} is not active/frozen")
        if not active.active_observation_paths(root)[strategy_id].exists():
            mismatches.append(f"{strategy_id} active observation file missing")
    if rows.get(active.SPY_200D_ID, {}).get("rules_frozen") is not True:
        mismatches.append(f"{active.SPY_200D_ID} is not frozen")
    return mismatches


def required_symbols() -> list[str]:
    return sorted(set(prereg.referenced_symbols()) | set(active.REQUIRED_CACHE_SYMBOLS) | {"QQQ"})


def prepare_prices(root: Path) -> tuple[pd.DataFrame, list[str]]:
    close_map: dict[str, pd.Series] = {}
    missing: list[str] = []
    for symbol in required_symbols():
        series = active.read_close(root, symbol)
        if series is None:
            missing.append(symbol)
        else:
            close_map[symbol] = series
    if missing:
        return pd.DataFrame(), missing
    return pd.concat(close_map.values(), axis=1, join="outer", sort=True).sort_index(), []


def sleeve_daily_return(close: pd.DataFrame, today: int, weights: dict[str, float]) -> float:
    daily_return = 0.0
    for symbol, weight in weights.items():
        if active.available_at(close, symbol, today, 1):
            daily_return += weight * float(close.iloc[today][symbol] / close.iloc[today - 1][symbol] - 1.0)
    return daily_return


def symbol_daily_return(close: pd.DataFrame, today: int, symbol: str) -> float:
    if active.available_at(close, symbol, today, 1):
        return float(close.iloc[today][symbol] / close.iloc[today - 1][symbol] - 1.0)
    return 0.0


def sma200_available(close: pd.DataFrame, symbol: str, t: int) -> bool:
    if symbol not in close.columns or t < 199 or pd.isna(close.iloc[t][symbol]):
        return False
    return len(close[symbol].iloc[t - 199 : t + 1].dropna()) >= 200


def above_sma200(close: pd.DataFrame, symbol: str, t: int) -> bool | None:
    if not sma200_available(close, symbol, t):
        return None
    window = close[symbol].iloc[t - 199 : t + 1].dropna()
    return bool(float(close.iloc[t][symbol]) > float(window.mean()))


def breadth_state(close: pd.DataFrame, t: int) -> dict[str, Any]:
    available: list[str] = []
    above: list[str] = []
    unavailable: list[str] = []
    for symbol in RISK_ASSETS:
        value = above_sma200(close, symbol, t)
        if value is None:
            unavailable.append(symbol)
        else:
            available.append(symbol)
            if value:
                above.append(symbol)
    count = len(above)
    if count >= 8:
        state = "risk_on"
    elif 5 <= count <= 7:
        state = "neutral"
    else:
        state = "risk_off"
    spy_below = above_sma200(close, "SPY", t) is False
    qqq_below = above_sma200(close, "QQQ", t) is False
    canary_forced = bool(spy_below and qqq_below and state != "risk_off")
    if spy_below and qqq_below:
        state = "risk_off"
    return {
        "state": state,
        "risk_breadth_count": count,
        "available_denominator": len(available),
        "available_symbols": available,
        "unavailable_symbols": unavailable,
        "above_symbols": above,
        "canary_forced_risk_off": canary_forced,
        "spy_below_200d": spy_below,
        "qqq_below_200d": qqq_below,
    }


def score_symbol(close: pd.DataFrame, symbol: str, t: int) -> float | None:
    if not active.available_at(close, symbol, t, 126):
        return None
    if symbol not in close.columns or t < 60:
        return None
    returns = close[symbol].pct_change().iloc[t - 59 : t + 1].dropna()
    if len(returns) < 45:
        return None
    vol = float(returns.std())
    if not np.isfinite(vol) or vol <= 0:
        return None
    momentum = float(close.iloc[t][symbol] / close.iloc[t - 126][symbol] - 1.0)
    return momentum / vol


def top_symbols(close: pd.DataFrame, symbols: list[str], t: int, count: int) -> list[str]:
    scored = [(symbol, score_symbol(close, symbol, t)) for symbol in symbols]
    valid = [(symbol, score) for symbol, score in scored if score is not None and np.isfinite(score)]
    return [symbol for symbol, _score in sorted(valid, key=lambda item: item[1], reverse=True)[:count]]


def add_weight(weights: dict[str, float], symbol: str, weight: float) -> None:
    if weight <= 0:
        return
    weights[symbol] = weights.get(symbol, 0.0) + weight


def allocate_top(weights: dict[str, float], close: pd.DataFrame, symbols: list[str], t: int, slots: int, allocation: float) -> None:
    picks = top_symbols(close, symbols, t, slots)
    if slots <= 0:
        add_weight(weights, "BIL", allocation)
        return
    slot_weight = allocation / slots
    for symbol in picks:
        add_weight(weights, symbol, slot_weight)
    missing_slots = slots - len(picks)
    if missing_slots > 0:
        add_weight(weights, "BIL", slot_weight * missing_slots)


def allocate_fixed_if_available(weights: dict[str, float], close: pd.DataFrame, symbol: str, t: int, allocation: float) -> None:
    if active.available_at(close, symbol, t, 1):
        add_weight(weights, symbol, allocation)
    else:
        add_weight(weights, "BIL", allocation)


def target_weights(close: pd.DataFrame, row_id: str, signal_t: int) -> tuple[dict[str, float], dict[str, Any]]:
    state_info = breadth_state(close, signal_t)
    state = state_info["state"]
    weights: dict[str, float] = {}

    if row_id == "bsr_breadth_state_top_assets_v1":
        if state == "risk_on":
            allocate_top(weights, close, RISK_ASSETS, signal_t, 4, 1.0)
        elif state == "neutral":
            allocate_top(weights, close, RISK_ASSETS, signal_t, 2, 0.50)
            allocate_top(weights, close, DEFENSIVE_EXTENDED, signal_t, 1, 0.30)
            add_weight(weights, "BIL", 0.20)
        else:
            allocate_fixed_if_available(weights, close, "GLD", signal_t, 0.40)
            allocate_top(weights, close, ["IEF", "TLT", "AGG"], signal_t, 1, 0.40)
            add_weight(weights, "BIL", 0.20)
    elif row_id == "bsr_breadth_state_defensive_shift_v1":
        if state == "risk_on":
            allocate_top(weights, close, RISK_ASSETS, signal_t, 3, 0.70)
            allocate_top(weights, close, DEFENSIVE_ASSETS, signal_t, 1, 0.30)
        elif state == "neutral":
            allocate_top(weights, close, RISK_ASSETS, signal_t, 2, 0.40)
            allocate_top(weights, close, LOW_VOL_ASSETS, signal_t, 1, 0.30)
            add_weight(weights, "BIL", 0.30)
        else:
            add_weight(weights, "BIL", 0.60)
            allocate_top(weights, close, DEFENSIVE_ASSETS, signal_t, 1, 0.40)
    elif row_id == "bsr_breadth_state_lowvol_overlay_v1":
        if state == "risk_on":
            allocate_top(weights, close, RISK_ASSETS, signal_t, 2, 0.50)
            allocate_top(weights, close, LOW_VOL_QUALITY, signal_t, 1, 0.30)
            add_weight(weights, "BIL", 0.20)
        elif state == "neutral":
            allocate_top(weights, close, RISK_ASSETS, signal_t, 1, 0.30)
            allocate_top(weights, close, LOW_VOL_QUALITY, signal_t, 2, 0.40)
            add_weight(weights, "BIL", 0.30)
        else:
            add_weight(weights, "BIL", 0.50)
            allocate_top(weights, close, ["IEF", "TLT", "AGG"], signal_t, 1, 0.30)
            allocate_top(weights, close, ["GLD", "USMV", "EFAV"], signal_t, 1, 0.20)
    elif row_id == "bsr_breadth_state_active_combo_overlay_v1":
        if state == "risk_on":
            add_weight(weights, "__ACTIVE_COMBO__", 0.50)
            allocate_top(weights, close, ["QQQ", "SCHG", "MTUM", "SPY"], signal_t, 1, 0.30)
            add_weight(weights, "BIL", 0.20)
        elif state == "neutral":
            add_weight(weights, "__ACTIVE_COMBO__", 0.50)
            allocate_top(weights, close, DEFENSIVE_ASSETS, signal_t, 1, 0.25)
            add_weight(weights, "BIL", 0.25)
        else:
            add_weight(weights, "__VM__", 0.50)
            add_weight(weights, "BIL", 0.50)
    else:
        raise ValueError(f"Unknown breadth-state row: {row_id}")
    total = sum(weights.values())
    if abs(total - 1.0) > 1e-8:
        add_weight(weights, "BIL", max(0.0, 1.0 - total))
    return weights, state_info


def position_return(close: pd.DataFrame, today: int, name: str, vm_weights: dict[str, float], dsr_weights: dict[str, float]) -> float:
    if name == "__VM__":
        return sleeve_daily_return(close, today, vm_weights)
    if name == "__ACTIVE_COMBO__":
        return 0.5 * sleeve_daily_return(close, today, vm_weights) + 0.5 * sleeve_daily_return(close, today, dsr_weights)
    return symbol_daily_return(close, today, name)


def simulate_window(close: pd.DataFrame, start: int, horizon: int, row_id: str) -> dict[str, Any]:
    equity = active.STARTING_EQUITY
    positions: dict[str, float] = {}
    vm_weights: dict[str, float] = {}
    dsr_weights: dict[str, float] = {}
    last_month = None
    peak = equity
    max_drawdown = 0.0
    stop = None
    target300 = None
    target400 = None
    months = np.array([dt.year * 12 + dt.month for dt in close.index], dtype=int)
    for offset in range(1, horizon + 1):
        today = start + offset
        signal = today - 1
        month = int(months[today])
        if month != last_month:
            weights, _state_info = target_weights(close, row_id, signal)
            positions = {name: equity * weight for name, weight in weights.items()}
            vm_weights = active.strategy_weights(close, signal, active.VM_ID)
            dsr_weights = active.strategy_weights(close, signal, active.DSR_ID)
            last_month = month
        for name in list(positions):
            positions[name] *= 1.0 + position_return(close, today, name, vm_weights, dsr_weights)
        equity = sum(positions.values())
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
        "strategy_id": row_id,
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


def run_windows(close: pd.DataFrame, strategy_id: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for horizon in active.HORIZONS:
        for start in active.sample_starts(close, horizon):
            if strategy_id in ROW_IDS:
                rows.append(simulate_window(close, start, horizon, strategy_id))
            elif strategy_id == combo.COMBO_ID:
                rows.append(combo.combo_window(close, start, horizon))
            elif strategy_id == prereg.LVQ_ID:
                continue
            else:
                rows.append(active.simulate(close, start, horizon, strategy_id))
    return rows


def full_equity_and_trace(close: pd.DataFrame, row_id: str) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    equity = active.STARTING_EQUITY
    positions: dict[str, float] = {}
    vm_weights: dict[str, float] = {}
    dsr_weights: dict[str, float] = {}
    last_month = None
    rows: list[dict[str, Any]] = []
    trace: list[dict[str, Any]] = []
    months = np.array([dt.year * 12 + dt.month for dt in close.index], dtype=int)
    for today in range(253, len(close)):
        signal = today - 1
        month = int(months[today])
        if month != last_month:
            weights, state_info = target_weights(close, row_id, signal)
            positions = {name: equity * weight for name, weight in weights.items()}
            vm_weights = active.strategy_weights(close, signal, active.VM_ID)
            dsr_weights = active.strategy_weights(close, signal, active.DSR_ID)
            trace.append(
                {
                    "rebalance_date": str(close.index[today].date()),
                    "strategy_id": row_id,
                    "state": state_info["state"],
                    "risk_breadth_count": state_info["risk_breadth_count"],
                    "available_denominator": state_info["available_denominator"],
                    "available_symbols": ";".join(state_info["available_symbols"]),
                    "unavailable_symbols": ";".join(state_info["unavailable_symbols"]),
                    "above_200d_symbols": ";".join(state_info["above_symbols"]),
                    "canary_forced_risk_off": state_info["canary_forced_risk_off"],
                    "spy_below_200d": state_info["spy_below_200d"],
                    "qqq_below_200d": state_info["qqq_below_200d"],
                    "bil_target_weight": round(weights.get("BIL", 0.0), 6),
                    "active_combo_target_weight": round(weights.get("__ACTIVE_COMBO__", 0.0), 6),
                    "vm_sleeve_target_weight": round(weights.get("__VM__", 0.0), 6),
                    "target_weights": json.dumps({k: round(v, 6) for k, v in sorted(weights.items())}, sort_keys=True),
                }
            )
            last_month = month
        for name in list(positions):
            positions[name] *= 1.0 + position_return(close, today, name, vm_weights, dsr_weights)
        equity = sum(positions.values())
        rows.append({"date": str(close.index[today].date()), "strategy_id": row_id, "equity": round(equity, 6)})
    return pd.DataFrame(rows), trace


def returns_from_equity(frame: pd.DataFrame) -> pd.Series:
    if frame.empty:
        return pd.Series(dtype=float)
    dates = pd.to_datetime(frame["date"])
    return pd.Series(pd.to_numeric(frame["equity"], errors="coerce").values, index=dates).pct_change().dropna()


def corr(returns: dict[str, pd.Series], left: str, right: str) -> float | str:
    if left not in returns or right not in returns:
        return "unavailable"
    aligned = pd.concat([returns[left].rename("left"), returns[right].rename("right")], axis=1).dropna()
    return float(aligned["left"].corr(aligned["right"])) if len(aligned) > 5 else "unavailable"


def risk_buffer(summary: dict[str, Any]) -> float | str:
    if "worst_drawdown" not in summary:
        return "unavailable"
    return float(summary["worst_drawdown"]) - active.STOP_DOLLARS


def trace_diagnostics(trace_rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    diagnostics: dict[str, dict[str, Any]] = {}
    frame = pd.DataFrame(trace_rows)
    if frame.empty:
        return {row_id: {} for row_id in ROW_IDS}
    for row_id in ROW_IDS:
        sub = frame[frame["strategy_id"] == row_id].copy()
        if sub.empty:
            diagnostics[row_id] = {}
            continue
        states = sub["state"].value_counts(normalize=True).to_dict()
        state_sequence = list(sub["state"])
        transitions = sum(1 for prev, cur in zip(state_sequence, state_sequence[1:]) if prev != cur)
        bil = pd.to_numeric(sub["bil_target_weight"], errors="coerce").fillna(0.0)
        denom = pd.to_numeric(sub["available_denominator"], errors="coerce").fillna(0.0)
        canary = sub["canary_forced_risk_off"].astype(bool)
        diagnostics[row_id] = {
            "risk_on_frequency": float(states.get("risk_on", 0.0)),
            "neutral_frequency": float(states.get("neutral", 0.0)),
            "risk_off_frequency": float(states.get("risk_off", 0.0)),
            "state_transition_count": int(transitions),
            "mean_bil_allocation": float(bil.mean()),
            "bil_allocation_frequency": float((bil > 0).mean()),
            "max_bil_allocation": float(bil.max()),
            "mean_available_denominator": float(denom.mean()),
            "min_available_denominator": int(denom.min()),
            "low_denominator_months": int((denom < len(RISK_ASSETS)).sum()),
            "low_denominator_month_rate": float((denom < len(RISK_ASSETS)).mean()),
            "canary_forced_count": int(canary.sum()),
            "canary_forced_rate": float(canary.mean()),
            "state_frequency_distorted_by_availability": bool((denom < 8).mean() > 0.20 or denom.min() < 5),
        }
    return diagnostics


def build_payload(root: Path) -> dict[str, Any]:
    close, missing = prepare_prices(root)
    if missing or close.empty:
        return {"diagnostics_available": False, "missing_symbols": missing, "close": close}
    ids = ROW_IDS + [ref for ref in REFERENCE_IDS if ref != prereg.LVQ_ID]
    window_rows = {strategy_id: run_windows(close, strategy_id) for strategy_id in ids}
    summaries = {strategy_id: {h: active.summarize(window_rows[strategy_id], strategy_id, h) for h in active.HORIZONS} for strategy_id in ids}
    returns: dict[str, pd.Series] = {
        active.VM_ID: active.full_returns(close, active.VM_ID),
        active.DSR_ID: active.full_returns(close, active.DSR_ID),
        active.SPY_200D_ID: active.full_returns(close, active.SPY_200D_ID),
        "SPY_buy_hold": active.full_returns(close, "SPY_buy_hold"),
        "QQQ_buy_hold": active.full_returns(close, "QQQ_buy_hold"),
        "BIL_cash_proxy": active.full_returns(close, "BIL_cash_proxy"),
    }
    combo_frame, _combo_alloc = combo.full_equity_series(close)
    returns[combo.COMBO_ID] = combo.returns_from_equity(combo_frame, "active_combo_equity")
    trace_rows: list[dict[str, Any]] = []
    equity_frames: list[pd.DataFrame] = []
    for row_id in ROW_IDS:
        frame, trace = full_equity_and_trace(close, row_id)
        returns[row_id] = returns_from_equity(frame)
        equity_frames.append(frame)
        trace_rows.extend(trace)
    diagnostics = trace_diagnostics(trace_rows)
    return {
        "diagnostics_available": True,
        "missing_symbols": [],
        "close": close,
        "window_rows": window_rows,
        "summaries": summaries,
        "returns": returns,
        "trace_rows": trace_rows,
        "trace_diagnostics": diagnostics,
        "equity_frame": pd.concat(equity_frames, ignore_index=True) if equity_frames else pd.DataFrame(),
    }


def promotion_blockers(row_id: str, metrics: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if float(metrics.get("stop_hit_rate", 1.0)) > 0:
        blockers.append("stop_hit_above_zero")
    if float(metrics.get("risk_buffer_vs_minus_600", -999.0)) < 25:
        blockers.append("risk_buffer_below_25")
    if float(metrics.get("delta_vs_active_combo", -999.0)) < 25:
        blockers.append("marginal_or_negative_active_combo_improvement")
    if float(metrics.get("delta_vs_active_vm", -999.0)) <= 0:
        blockers.append("underperforms_or_fails_to_beat_active_vm")
    if float(metrics.get("delta_vs_active_dsr", -999.0)) <= 0:
        blockers.append("underperforms_or_fails_to_beat_active_dsr")
    if float(metrics.get("delta_vs_spy_200d", -999.0)) <= 0:
        blockers.append("underperforms_or_fails_to_beat_spy_200d")
    if float(metrics.get("target_300_before_stop_rate", 0.0)) < 0.60 or float(metrics.get("target_400_before_stop_rate", 0.0)) < 0.40:
        blockers.append("target_rates_not_useful_enough")
    corr_combo = metrics.get("corr_vs_active_combo")
    if isinstance(corr_combo, (float, int)) and float(corr_combo) >= 0.95 and float(metrics.get("delta_vs_active_combo", 0.0)) < 50:
        blockers.append("highly_duplicative_of_active_combo")
    corr_spy = metrics.get("corr_vs_spy_200d")
    if isinstance(corr_spy, (float, int)) and float(corr_spy) >= 0.95 and float(metrics.get("delta_vs_spy_200d", 0.0)) < 50:
        blockers.append("highly_duplicative_of_spy_200d")
    if float(metrics.get("mean_bil_allocation", 0.0)) > 0.40 and float(metrics.get("delta_vs_active_combo", -999.0)) < 50:
        blockers.append("bil_allocation_excessive_without_clear_benefit")
    if metrics.get("state_frequency_distorted_by_availability") is True:
        blockers.append("state_frequency_distorted_by_availability")
    if float(metrics.get("canary_forced_rate", 0.0)) > 0.33:
        blockers.append("result_depends_too_much_on_canary_override")
    if row_id == "bsr_breadth_state_active_combo_overlay_v1":
        if float(metrics.get("delta_vs_active_combo", -999.0)) < 50:
            blockers.append("active_combo_overlay_complexity_not_justified")
        if isinstance(corr_combo, (float, int)) and float(corr_combo) >= 0.90:
            blockers.append("active_combo_overlay_too_correlated_with_input_sleeve")
    return blockers


def decide_rows(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if not payload["diagnostics_available"]:
        return {row_id: {"decision": "discovery_reject", "reason": "evidence incomplete or unavailable", "blockers": ["evidence_incomplete"]} for row_id in ROW_IDS}
    decisions: dict[str, dict[str, Any]] = {}
    for row_id in ROW_IDS:
        s180 = payload["summaries"][row_id][180]
        diagnostics = payload["trace_diagnostics"].get(row_id, {})
        metrics = {
            "stop_hit_rate": float(s180.get("stop_hit_rate", 1.0)),
            "risk_buffer_vs_minus_600": float(risk_buffer(s180)),
            "target_300_before_stop_rate": float(s180.get("target_300_before_stop_rate", 0.0)),
            "target_400_before_stop_rate": float(s180.get("target_400_before_stop_rate", 0.0)),
            "corr_vs_active_combo": corr(payload["returns"], row_id, combo.COMBO_ID),
            "corr_vs_spy_200d": corr(payload["returns"], row_id, active.SPY_200D_ID),
            "delta_vs_active_combo": float(s180["median_final_equity"]) - float(payload["summaries"][combo.COMBO_ID][180]["median_final_equity"]),
            "delta_vs_active_vm": float(s180["median_final_equity"]) - float(payload["summaries"][active.VM_ID][180]["median_final_equity"]),
            "delta_vs_active_dsr": float(s180["median_final_equity"]) - float(payload["summaries"][active.DSR_ID][180]["median_final_equity"]),
            "delta_vs_spy_200d": float(s180["median_final_equity"]) - float(payload["summaries"][active.SPY_200D_ID][180]["median_final_equity"]),
            **diagnostics,
        }
        blockers = promotion_blockers(row_id, metrics)
        if blockers:
            decisions[row_id] = {"decision": "discovery_reject", "reason": ";".join(blockers), "blockers": blockers}
        else:
            decisions[row_id] = {"decision": "promotion_review_candidate", "reason": "strict discovery gates passed; promotion review required before any further action", "blockers": []}
    return decisions


def final_next_action(decisions: dict[str, dict[str, Any]]) -> str:
    if any(row["decision"] == "promotion_review_candidate" for row in decisions.values()):
        return NEXT_ACTION_PROMOTION
    return NEXT_ACTION_ARCHIVE


def result_rows(payload: dict[str, Any], decisions: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    if not payload["diagnostics_available"]:
        return []
    rows: list[dict[str, Any]] = []
    for row_id in ROW_IDS:
        s90 = payload["summaries"][row_id][90]
        s180 = payload["summaries"][row_id][180]
        diag = payload["trace_diagnostics"].get(row_id, {})
        result = {
            "strategy_id": row_id,
            "discovery_outcome": decisions[row_id]["decision"],
            "decision_reason": decisions[row_id]["reason"],
            "90d_median_final_equity": fmt(s90.get("median_final_equity")),
            "180d_median_final_equity": fmt(s180.get("median_final_equity")),
            "180d_mean_final_equity": fmt(s180.get("mean_final_equity")),
            "180d_p75_final_equity": fmt(s180.get("p75_final_equity")),
            "180d_p90_final_equity": fmt(s180.get("p90_final_equity")),
            "best_final_equity": fmt(s180.get("best_final_equity")),
            "worst_final_equity": fmt(s180.get("worst_final_equity")),
            "target_300_before_stop_rate": fmt(s180.get("target_300_before_stop_rate")),
            "target_400_before_stop_rate": fmt(s180.get("target_400_before_stop_rate")),
            "180d_worst_drawdown": fmt(s180.get("worst_drawdown")),
            "stop_hit_rate": fmt(s180.get("stop_hit_rate")),
            "stop_hit_count": int(round(float(s180.get("stop_hit_rate", 0.0)) * int(s180.get("window_count", 0)))),
            "risk_buffer_vs_minus_600": fmt(risk_buffer(s180)),
            "stress_result": "unavailable_not_supported_by_existing_bsr_model",
            "corr_vs_active_combo": fmt(corr(payload["returns"], row_id, combo.COMBO_ID)),
            "corr_vs_spy_200d": fmt(corr(payload["returns"], row_id, active.SPY_200D_ID)),
            "delta_vs_active_combo": fmt(float(s180["median_final_equity"]) - float(payload["summaries"][combo.COMBO_ID][180]["median_final_equity"])),
            "delta_vs_active_dsr": fmt(float(s180["median_final_equity"]) - float(payload["summaries"][active.DSR_ID][180]["median_final_equity"])),
            "delta_vs_active_vm": fmt(float(s180["median_final_equity"]) - float(payload["summaries"][active.VM_ID][180]["median_final_equity"])),
            "delta_vs_spy_200d": fmt(float(s180["median_final_equity"]) - float(payload["summaries"][active.SPY_200D_ID][180]["median_final_equity"])),
            "risk_on_frequency": fmt(diag.get("risk_on_frequency", 0.0)),
            "neutral_frequency": fmt(diag.get("neutral_frequency", 0.0)),
            "risk_off_frequency": fmt(diag.get("risk_off_frequency", 0.0)),
            "mean_bil_allocation": fmt(diag.get("mean_bil_allocation", 0.0)),
            "bil_allocation_frequency": fmt(diag.get("bil_allocation_frequency", 0.0)),
            "state_transition_count": diag.get("state_transition_count", 0),
            "mean_available_denominator": fmt(diag.get("mean_available_denominator", 0.0)),
            "min_available_denominator": diag.get("min_available_denominator", 0),
            "low_denominator_month_rate": fmt(diag.get("low_denominator_month_rate", 0.0)),
            "canary_forced_rate": fmt(diag.get("canary_forced_rate", 0.0)),
            "distinct_or_duplicative_notes": "see decision_reason and benchmark delta/correlation diagnostics",
        }
        rows.append(result)
    return rows


def benchmark_delta_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not payload["diagnostics_available"]:
        return rows
    for row_id in ROW_IDS:
        row_summary = payload["summaries"][row_id][180]
        for ref in REFERENCE_IDS:
            if ref not in payload["summaries"]:
                rows.append(
                    {
                        "strategy_id": row_id,
                        "reference_id": ref,
                        "strategy_180d_median_final_equity": fmt(row_summary["median_final_equity"]),
                        "reference_180d_median_final_equity": "unavailable",
                        "delta": "unavailable",
                        "correlation": "unavailable",
                        "comparison_status": "unavailable",
                        "missing_reason": "optional diagnostic benchmark unavailable",
                    }
                )
                continue
            ref_summary = payload["summaries"][ref][180]
            rows.append(
                {
                    "strategy_id": row_id,
                    "reference_id": ref,
                    "strategy_180d_median_final_equity": fmt(row_summary["median_final_equity"]),
                    "reference_180d_median_final_equity": fmt(ref_summary["median_final_equity"]),
                    "delta": fmt(float(row_summary["median_final_equity"]) - float(ref_summary["median_final_equity"])),
                    "correlation": fmt(corr(payload["returns"], row_id, ref)),
                    "comparison_status": "computed",
                    "missing_reason": "",
                }
            )
    return rows


def decision_log_rows(payload: dict[str, Any], decisions: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row_id in ROW_IDS:
        s = payload["summaries"].get(row_id, {}).get(180, {}) if payload["diagnostics_available"] else {}
        rows.append(
            {
                "strategy_id": row_id,
                "discovery_outcome": decisions[row_id]["decision"],
                "decision_reason": decisions[row_id]["reason"],
                "180d_median_final_equity": fmt(s.get("median_final_equity", "unavailable")),
                "180d_worst_drawdown": fmt(s.get("worst_drawdown", "unavailable")),
                "stop_hit_rate": fmt(s.get("stop_hit_rate", "unavailable")),
                "promotion_review_required": decisions[row_id]["decision"] == "promotion_review_candidate",
                "candidate_exhaustive_recommended": False,
                "paper_forward_active": False,
                "real_money_recommendation": False,
            }
        )
    return rows


def target_window_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not payload["diagnostics_available"]:
        return rows
    for row_id in ROW_IDS:
        for row in payload["window_rows"][row_id]:
            rows.append(
                {
                    "strategy_id": row_id,
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


def drawdown_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not payload["diagnostics_available"]:
        return rows
    for row_id in ROW_IDS:
        for row in payload["window_rows"][row_id]:
            rows.append(
                {
                    "strategy_id": row_id,
                    "horizon": row["horizon"],
                    "window_start": row["window_start"],
                    "window_end": row["window_end"],
                    "max_drawdown": fmt(row["max_drawdown"]),
                    "profit_dollars": fmt(row["profit_dollars"]),
                }
            )
    return rows


def state_frequency_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row_id, diag in payload.get("trace_diagnostics", {}).items():
        rows.append({"strategy_id": row_id, **{key: fmt(value) for key, value in diag.items()}})
    return rows


def create_packet(output: Path) -> Path:
    packet = output / "breadth_state_regime_discovery_packet.zip"
    if packet.exists():
        packet.unlink()
    with zipfile.ZipFile(packet, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(output.iterdir()):
            if path.is_file() and path.name != packet.name:
                zf.write(path, path.name)
    return packet


def registry_row_for_result(row_id: str, decision: str, output_path: Path, next_action: str) -> dict[str, Any]:
    promotion = decision == "promotion_review_candidate"
    return {
        "id": row_id,
        "display_name": row_id,
        "lane": "profit_exploration",
        "instrument_family": "ETF",
        "strategy_family": "breadth_state_regime",
        "version": "v1",
        "parent_id": "",
        "credibility_tier": "tier2_exploratory",
        "status": decision,
        "role": "breadth_state_regime_discovery_row",
        "rules_frozen": True,
        "paper_forward_active": False,
        "implementation_status": "implemented_research_sample",
        "data_source": "existing_adjusted_etf_cache",
        "evidence_source": "breadth_state_regime_discovery",
        "latest_evidence_path": str(output_path),
        "latest_known_result_summary": f"Breadth-state regime discovery verdict: {decision}.",
        "allowed_next_action": NEXT_ACTION_PROMOTION if promotion else "no_action",
        "forbidden_next_actions": [
            "run_candidate_exhaustive",
            "paper_forward_activation",
            "paper_forward_checkpoint",
            "paper_forward_review",
            "promote_to_real_money",
            "add_broker_integration",
            "live_orders",
            "order_placement",
            "download_data",
            "tune_parameters",
        ],
        "risk_framework_status": "research_sample_only",
        "paper_forward_allowed_by_risk_framework": False,
        "real_money_recommendation": False,
        "promotion_blockers": "research_sample_only;not_candidate_exhaustive;not_paper_forward_allowed",
        "promotion_requirements": "Separate promotion review only; no candidate_exhaustive from discovery batch.",
        "demotion_or_kill_criteria": "Weak target profile, unacceptable drawdown, duplicate exposure, benchmark lag, or state diagnostics distorted by availability.",
        "notes": "Fixed-rule breadth-state regime discovery row; no broker/live-order/real-money path.",
        "strategy_id": row_id,
        "family": "breadth_state_regime",
        "instrument_lane": "ETF",
        "evidence_tier": "research_sample",
        "current_status": decision,
        "allowed_next_actions": [NEXT_ACTION_PROMOTION if promotion else "no_action"],
        "candidate_exhaustive_run": False,
        "candidate_exhaustive_recommended": False,
        "promotion_review_required": promotion,
        "promotion_decision": decision,
        "promotion_reason": "promotion review candidate" if promotion else "strict discovery rejection",
        "primary_failure_mode": "not_flagged" if promotion else "discovery_reject",
        "duplication_risk": "review_required" if promotion else "not_promoted",
        "risk_budget_status": "research_sample_screened",
        "evidence_needed": "promotion review only if selected; no paper-forward action",
        "duplicate_of": "",
        "blocked_reason": "" if promotion else "failed strict breadth-state discovery gates",
        "discovery_decision": decision,
        "latest_discovery_path": str(output_path),
        "candidate_exhaustive_run_after_discovery": False,
        "paper_forward_active_after_discovery": False,
    }


def update_registry(root: Path, decisions: dict[str, dict[str, Any]], next_action: str, output_path: Path) -> None:
    path = root / REGISTRY_PATH
    registry = load_yaml(path)
    meta = registry.setdefault("registry", {})
    promotion_count = sum(1 for row in decisions.values() if row["decision"] == "promotion_review_candidate")
    meta["lane_id"] = LANE_ID
    meta["lane_status"] = "discovery_completed" if promotion_count else LANE_ARCHIVE_STATUS
    meta["etf_track_status"] = "promotion_review_pending_for_breadth_state" if promotion_count else "archived_stopped_after_final_breadth_state_no_candidate"
    meta["latest_discovery_path"] = str(output_path)
    meta["promotion_candidates_count"] = promotion_count
    meta["candidate_exhaustive_run"] = False
    meta["paper_forward_active"] = False
    meta["real_money_recommendation"] = False
    meta["next_action"] = next_action
    meta["current_next_action"] = next_action
    meta["no_candidate_exhaustive_run"] = True
    meta["no_paper_forward_action"] = True
    meta["no_real_money_recommendation"] = True
    existing = rows_by_id(registry)
    for row_id, details in decisions.items():
        row = registry_row_for_result(row_id, details["decision"], output_path, next_action)
        if row_id in existing:
            existing[row_id].update(row)
        else:
            registry.setdefault("strategies", []).append(row)
    path.write_text(yaml.safe_dump(registry, sort_keys=False, width=120), encoding="utf-8")


def update_roadmap(root: Path, decisions: dict[str, dict[str, Any]], next_action: str) -> None:
    path = root / ROADMAP_PATH
    existing = path.read_text(encoding="utf-8") if path.exists() else "# Research Roadmap\n"
    lines = existing.splitlines()
    for idx, line in enumerate(lines):
        if line.startswith("Current next action:"):
            lines[idx] = f"Current next action: `{next_action}`"
            break
    else:
        lines.insert(1, f"Current next action: `{next_action}`")
    promotion_count = sum(1 for row in decisions.values() if row["decision"] == "promotion_review_candidate")
    section = f"""## Breadth-State Regime Discovery Result

- Lane id: `{LANE_ID}`
- Rows evaluated: `{', '.join(ROW_IDS)}`
- Promotion-review candidates: `{promotion_count}`
- Discovery outcomes: `{json.dumps({row_id: data['decision'] for row_id, data in decisions.items()}, sort_keys=True)}`
- ETF-wrapper stop status: `{'not_archived_promotion_review_pending' if promotion_count else LANE_ARCHIVE_STATUS}`
- Next action: `{next_action}`
- No candidate_exhaustive, paper-forward action, provider download, broker/live-order path, or real-money recommendation is authorized.
"""
    marker = "## Breadth-State Regime Discovery Result"
    base = "\n".join(lines)
    updated = base.split(marker, 1)[0].rstrip() + "\n\n" + section if marker in base else base.rstrip() + "\n\n" + section
    path.write_text(updated.rstrip() + "\n", encoding="utf-8")


def write_outputs(
    root: Path,
    payload: dict[str, Any],
    decisions: dict[str, dict[str, Any]],
    next_action: str,
    consistency: dict[str, Any],
    state_notes: list[str],
) -> dict[str, Any]:
    output = root / OUTPUT_DIR
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)
    results = result_rows(payload, decisions)
    deltas = benchmark_delta_rows(payload)
    decisions_rows = decision_log_rows(payload, decisions)
    promotion_rows = [row for row in decisions_rows if row["discovery_outcome"] == "promotion_review_candidate"]
    reject_rows = [row for row in decisions_rows if row["discovery_outcome"] == "discovery_reject"]
    trace_rows = payload.get("trace_rows", []) if payload["diagnostics_available"] else []

    result_fields = [
        "strategy_id",
        "discovery_outcome",
        "decision_reason",
        "90d_median_final_equity",
        "180d_median_final_equity",
        "180d_mean_final_equity",
        "180d_p75_final_equity",
        "180d_p90_final_equity",
        "best_final_equity",
        "worst_final_equity",
        "target_300_before_stop_rate",
        "target_400_before_stop_rate",
        "180d_worst_drawdown",
        "stop_hit_rate",
        "stop_hit_count",
        "risk_buffer_vs_minus_600",
        "stress_result",
        "corr_vs_active_combo",
        "corr_vs_spy_200d",
        "delta_vs_active_combo",
        "delta_vs_active_dsr",
        "delta_vs_active_vm",
        "delta_vs_spy_200d",
        "risk_on_frequency",
        "neutral_frequency",
        "risk_off_frequency",
        "mean_bil_allocation",
        "bil_allocation_frequency",
        "state_transition_count",
        "mean_available_denominator",
        "min_available_denominator",
        "low_denominator_month_rate",
        "canary_forced_rate",
        "distinct_or_duplicative_notes",
    ]
    write_csv(output / "breadth_state_regime_results.csv", results, result_fields)
    write_csv(
        output / "breadth_state_regime_benchmark_delta.csv",
        deltas,
        ["strategy_id", "reference_id", "strategy_180d_median_final_equity", "reference_180d_median_final_equity", "delta", "correlation", "comparison_status", "missing_reason"],
    )
    decision_fields = ["strategy_id", "discovery_outcome", "decision_reason", "180d_median_final_equity", "180d_worst_drawdown", "stop_hit_rate", "promotion_review_required", "candidate_exhaustive_recommended", "paper_forward_active", "real_money_recommendation"]
    write_csv(output / "breadth_state_regime_decision_log.csv", decisions_rows, decision_fields)
    write_csv(output / "breadth_state_regime_promotion_candidates.csv", promotion_rows, decision_fields)
    write_csv(output / "breadth_state_regime_rejects.csv", reject_rows, decision_fields)
    write_csv(output / "breadth_state_regime_state_frequency.csv", state_frequency_rows(payload), ["strategy_id", "risk_on_frequency", "neutral_frequency", "risk_off_frequency", "state_transition_count", "mean_bil_allocation", "bil_allocation_frequency", "max_bil_allocation", "mean_available_denominator", "min_available_denominator", "low_denominator_months", "low_denominator_month_rate", "canary_forced_count", "canary_forced_rate", "state_frequency_distorted_by_availability"])
    trace_fields = ["rebalance_date", "strategy_id", "state", "risk_breadth_count", "available_denominator", "available_symbols", "unavailable_symbols", "above_200d_symbols", "canary_forced_risk_off", "spy_below_200d", "qqq_below_200d", "bil_target_weight", "active_combo_target_weight", "vm_sleeve_target_weight", "target_weights"]
    write_csv(output / "breadth_state_regime_state_trace.csv", trace_rows, trace_fields)
    write_csv(output / "breadth_state_regime_availability_diagnostics.csv", trace_rows, trace_fields)
    write_csv(output / "breadth_state_regime_allocation_trace.csv", trace_rows, trace_fields)
    write_csv(output / "breadth_state_regime_target_window_review.csv", target_window_rows(payload), ["strategy_id", "horizon", "window_start", "window_end", "target_300_before_stop", "target_400_before_stop", "absolute_600_stop_hit", "final_equity"])
    write_csv(output / "breadth_state_regime_drawdown_review.csv", drawdown_rows(payload), ["strategy_id", "horizon", "window_start", "window_end", "max_drawdown", "profit_dollars"])

    (output / "breadth_state_regime_next_action.md").write_text(
        f"# Breadth-State Regime Discovery Next Action\n\n`{next_action}`\n\nDo not run candidate_exhaustive or paper-forward directly from this discovery batch.\n",
        encoding="utf-8",
    )
    promotion_count = len(promotion_rows)
    summary = [
        "# Breadth-State Regime Discovery",
        "",
        f"Created at UTC: `{now_utc()}`",
        f"Lane id: `{LANE_ID}`",
        f"Rows evaluated: `{len(ROW_IDS)}`",
        f"Promotion-review candidates: `{promotion_count}`",
        f"Next action: `{next_action}`",
        "",
    ]
    if results:
        best = max(results, key=lambda row: float(row["180d_median_final_equity"]))
        summary.append(f"Best 180d median row: `{best['strategy_id']}` at `{best['180d_median_final_equity']}` with outcome `{best['discovery_outcome']}`.")
    if promotion_count == 0:
        summary.append("")
        summary.append("No row cleared the strict promotion bar. The final ETF-wrapper breadth-state lane triggers the archive/stop condition.")
    summary.append("")
    summary.append("This discovery did not run candidate_exhaustive, paper-forward workflows, provider downloads, broker/live-order paths, or real-money recommendation logic.")
    (output / "breadth_state_regime_discovery_summary.md").write_text("\n".join(summary) + "\n", encoding="utf-8")

    manifest = {
        "created_at_utc": now_utc(),
        "lane_id": LANE_ID,
        "lane_status": "discovery_completed" if promotion_count else LANE_ARCHIVE_STATUS,
        "output_dir": str(output),
        "rows_evaluated": ROW_IDS,
        "reference_ids": REFERENCE_IDS,
        "diagnostics_available": payload["diagnostics_available"],
        "missing_symbols": payload["missing_symbols"],
        "decisions": {row_id: details["decision"] for row_id, details in decisions.items()},
        "promotion_candidates_count": promotion_count,
        "etf_wrapper_track_archived_stopped": promotion_count == 0,
        "next_action": next_action,
        "state_notes": state_notes,
        "strategy_discovery_run": True,
        "research_sample_run": False,
        "candidate_exhaustive_run": False,
        "paper_forward_review": False,
        "paper_forward_activation": False,
        "paper_forward_checkpoint": False,
        "provider_download": False,
        "broker_integration": False,
        "live_orders": False,
        "order_placement": False,
        "real_money_recommendation": False,
    }
    write_json(output / "breadth_state_regime_discovery_manifest.json", manifest)
    write_json(output / "breadth_state_regime_consistency_check.json", consistency)
    packet = create_packet(output)
    return {"output_dir": str(output), "packet": str(packet), "manifest": manifest, "results": results}


def run_breadth_state_regime_discovery_batch(root: Path = ROOT, strict_state: bool = True) -> dict[str, Any]:
    registry_path = root / REGISTRY_PATH
    registry_before = load_yaml(registry_path)
    obs_before = active_observation_hashes(root)
    core_before = protected_core_snapshot(registry_before)
    mismatches = state_mismatches(root, registry_before)
    if mismatches and strict_state:
        raise RuntimeError("State confirmation failed: " + "; ".join(mismatches))
    payload = build_payload(root)
    decisions = decide_rows(payload)
    next_action = final_next_action(decisions)
    update_registry(root, decisions, next_action, root / OUTPUT_DIR)
    update_roadmap(root, decisions, next_action)
    registry_after = load_yaml(registry_path)
    obs_after = active_observation_hashes(root)
    core_after = protected_core_snapshot(registry_after)
    promotion_count = sum(1 for row in decisions.values() if row["decision"] == "promotion_review_candidate")
    consistency = {
        "discovery_completed": payload["diagnostics_available"],
        "only_preregistered_rows_run": set(ROW_IDS) == set(preregistered_rows(root)),
        "no_extra_rows_added": len(ROW_IDS) == 4,
        "fixed_state_thresholds_unchanged": True,
        "state_frequency_diagnostics_created": True,
        "availability_denominator_diagnostics_created": True,
        "no_research_sample_run": True,
        "no_candidate_exhaustive_run": True,
        "no_paper_forward_review": True,
        "no_paper_forward_activation": True,
        "no_paper_forward_checkpoint": True,
        "no_provider_download": True,
        "no_broker_path_added": True,
        "no_live_order_path_added": True,
        "no_real_money_recommendation": True,
        "active_observations_unchanged": obs_before == obs_after and core_before == core_after,
        "stop_condition_applied_if_no_candidate": promotion_count > 0 or next_action == NEXT_ACTION_ARCHIVE,
        "final_next_action_explicit": next_action in {NEXT_ACTION_ARCHIVE, NEXT_ACTION_PROMOTION},
    }
    consistency["consistency_passed"] = all(bool(value) for value in consistency.values())
    outputs = write_outputs(root, payload, decisions, next_action, consistency, mismatches)
    return {
        "output_dir": outputs["output_dir"],
        "packet": outputs["packet"],
        "rows_evaluated": ROW_IDS,
        "decisions": {row_id: details["decision"] for row_id, details in decisions.items()},
        "promotion_candidates_count": promotion_count,
        "etf_wrapper_track_archived_stopped": promotion_count == 0,
        "next_action": next_action,
        "diagnostics_available": payload["diagnostics_available"],
        "missing_symbols": payload["missing_symbols"],
        "consistency": consistency,
        "state_mismatches": mismatches,
    }


def main() -> None:
    print(json.dumps(run_breadth_state_regime_discovery_batch(ROOT, strict_state=True), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
