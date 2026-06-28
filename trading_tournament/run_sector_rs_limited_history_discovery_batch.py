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
import run_sector_rs_limited_history_preregistration as prereg


ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = Path("evidence") / "parallel_research_discovery" / "sector_rs_limited_history" / "latest"
PREREG_DIR = Path("evidence") / "pre_registered_lanes" / "sector_rs_limited_history" / "latest"
SECOND_EXPANSION_DIR = Path("evidence") / "parallel_research_discovery" / "second_expansion_with_lane_framework" / "latest"
REGISTRY_PATH = Path("strategy_lab") / "strategy_registry.yaml"
RESEARCH_ROADMAP_PATH = Path("strategy_lab") / "RESEARCH_ROADMAP.md"
EXPANSION_ROADMAP_PATH = Path("strategy_lab") / "STRATEGY_EXPANSION_ROADMAP.md"
CACHE_DIR = Path("data") / "cache"

CANDIDATE_ID = prereg.CANDIDATE_ID
LIMITED_HISTORY_LABEL = prereg.LIMITED_HISTORY_LABEL
METHODOLOGY = prereg.METHODOLOGY
VALID_OUTCOMES = {"discovery_reject", "promotion_review_candidate_limited_history"}
FORBIDDEN_OUTCOMES = {"candidate_exhaustive", "paper_forward", "paper_forward_active", "demo_active", "live_ready"}
NEXT_ACTION_PROMOTION = "promotion_review_for_sector_rs_limited_history"
NEXT_ACTION_TOM_AUDIT = "audit_turn_of_month_zero_trade_result"
NEXT_ACTION_FAILURE_AUDIT = "audit_second_expansion_failures_before_more_expansion"
NEXT_ACTION_THIRD = "pre_register_third_expansion_discovery_batch_with_lane_framework"
VALID_NEXT_ACTIONS = {NEXT_ACTION_PROMOTION, NEXT_ACTION_TOM_AUDIT, NEXT_ACTION_FAILURE_AUDIT, NEXT_ACTION_THIRD}

SECTOR_SYMBOLS = ["XLK", "XLF", "XLV", "XLE", "XLI", "XLY", "XLP", "XLU", "XLB", "XLRE"]
UNIVERSE = [*SECTOR_SYMBOLS, "BIL"]
RISK_SYMBOL = "SPY"
SECOND_EXPANSION_REJECT_IDS = [
    "managed_futures_etf_trend_wrapper_v1",
    "gld_gror_balanced_momentum_clean_v1",
    "donchian_atr_breakout_etf_v1",
    "turn_of_month_spy_qqq_v1",
    "cash_pause_overlay_meta_v1",
]
EXCLUDED_IDS = [
    *SECOND_EXPANSION_REJECT_IDS,
    "dmr_liquid_etf_oversold_rebound_v1",
    "vm_spy_qqq_daily_vol_target_v1",
    "vol_compression_breakout_etf_v1",
    "rs_pair_rotation_spy_qqq_xlk_xlu_v1",
    "orb_spy_qqq_30m_research_v1",
    "gap_down_fade_spy_qqq_research_v1",
    "vwap_deviation_reversion_research_v1",
    "post_earnings_drift_large_cap_later_v1",
    "gror_balanced_momentum_60_40_v1",
]
LOAD_SYMBOLS = sorted(set([*UNIVERSE, RISK_SYMBOL, "QQQ", *active.REQUIRED_CACHE_SYMBOLS]))
REFERENCE_IDS = [
    active.DSR_ID,
    combo.COMBO_ID,
    active.VM_ID,
    active.SPY_200D_ID,
    "SPY_buy_hold",
    "QQQ_buy_hold",
    "BIL_cash_proxy",
    "equal_weight_sector_baseline",
]

STARTING_EQUITY = active.STARTING_EQUITY
STOP_DOLLARS = active.STOP_DOLLARS
BASE_SLIPPAGE = active.SLIPPAGE
STRESS_SLIPPAGE = 0.0010
HORIZONS = active.HORIZONS
MAX_WINDOWS_PER_HORIZON = active.MAX_WINDOWS_PER_HORIZON

MANIFEST_FLAGS = {
    "discovery_run": True,
    "backtests_run": True,
    "candidate_count": 1,
    "limited_history_due_to_xlre_inception": True,
    "methodology": METHODOLOGY,
    "not_2007_style_full_history_test": True,
    "same_window_benchmark_recompute_used": True,
    "provider_download": False,
    "candidate_exhaustive_run": False,
    "paper_forward_review": False,
    "paper_forward_activation": False,
    "broker_path_touched": False,
    "live_orders": False,
    "real_money_recommendation": False,
    "frozen_rules_changed": False,
    "candidate_universe_changed": False,
    "benchmarks_changed": False,
    "active_strategy_state_changed": False,
    "etf_wrapper_track_reopened": False,
    "second_expansion_rejects_remain_rejected": True,
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


def active_observation_hashes(root: Path) -> dict[str, str]:
    return prereg.active_observation_hashes(root)


def validate_authorization(root: Path) -> tuple[dict[str, Any], list[str]]:
    mismatches: list[str] = []
    batch = load_yaml(root / PREREG_DIR / "sector_rs_limited_history_batch.yaml")
    manifest = read_json(root / PREREG_DIR / "sector_rs_limited_history_manifest.json")
    metadata = batch.get("metadata", {})
    candidates = batch.get("candidates", [])
    candidate = candidates[0] if candidates else {}
    included = metadata.get("included_candidate_ids", [])
    if included != [CANDIDATE_ID] or len(candidates) != 1 or candidate.get("candidate_id") != CANDIDATE_ID:
        mismatches.append("sector RS preregistration does not authorize exactly one sector RS candidate")
    if metadata.get("next_action") != "run_sector_rs_limited_history_discovery_batch":
        mismatches.append("sector RS preregistration next action does not authorize discovery")
    if metadata.get("methodology") != METHODOLOGY or candidate.get("methodology") != METHODOLOGY:
        mismatches.append("sector RS methodology mismatch")
    if metadata.get("limited_history_due_to_xlre_inception") is not True or candidate.get("limited_history_label") != LIMITED_HISTORY_LABEL:
        mismatches.append("limited-history XLRE label missing")
    if candidate.get("universe") != UNIVERSE:
        mismatches.append("sector RS universe differs from frozen universe")
    if "XLRE" not in candidate.get("universe", []):
        mismatches.append("XLRE missing from frozen sector universe")
    if set(included) & set(EXCLUDED_IDS):
        mismatches.append("excluded candidate appears in sector RS batch")
    if manifest and manifest.get("discovery_run") is not False:
        mismatches.append("sector RS preregistration unexpectedly records discovery")
    if manifest and manifest.get("candidate_exhaustive_run") is not False:
        mismatches.append("sector RS preregistration unexpectedly permits candidate exhaustive")
    return batch, mismatches


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
    clean = clean.dropna(subset=["date", "close", "adj_close"]).sort_values("date").drop_duplicates("date")
    if len(clean) < 260:
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
    close = store["close"]
    volume = store["volume"]
    return {
        "mom63": close / close.shift(63) - 1.0,
        "sma200": close.rolling(200, min_periods=200).mean(),
        "volume20": volume.rolling(20, min_periods=20).mean(),
    }


def value_at(frame: pd.DataFrame, symbol: str, t: int) -> float | None:
    if symbol not in frame.columns or t < 0 or t >= len(frame):
        return None
    value = frame.iloc[t][symbol]
    if pd.isna(value):
        return None
    return float(value)


def available(store: dict[str, Any], symbol: str, t: int, lookback: int = 0) -> bool:
    return value_at(store["close"], symbol, t) is not None and value_at(store["close"], symbol, t - lookback) is not None


def symbol_return(store: dict[str, Any], symbol: str, t: int) -> float:
    if not available(store, symbol, t, 1):
        return 0.0
    return float(store["close"].iloc[t][symbol] / store["close"].iloc[t - 1][symbol] - 1.0)


def above_sma200(store: dict[str, Any], ind: dict[str, pd.DataFrame], symbol: str, t: int) -> bool:
    price = value_at(store["close"], symbol, t)
    sma = value_at(ind["sma200"], symbol, t)
    return price is not None and sma is not None and price > sma


def liquidity_ok(store: dict[str, Any], ind: dict[str, pd.DataFrame], symbol: str, t: int) -> bool:
    volume = value_at(store["volume"], symbol, t)
    avg_volume = value_at(ind["volume20"], symbol, t)
    return volume is not None and avg_volume is not None and volume > 0 and avg_volume > 0


def date_week(ts: pd.Timestamp) -> str:
    iso = ts.isocalendar()
    return f"{iso.year}-{iso.week:02d}"


def first_valid_signal_index(store: dict[str, Any], ind: dict[str, pd.DataFrame]) -> int:
    floor = pd.Timestamp("2016-01-01")
    start = int(store["index"].get_indexer([floor], method="bfill")[0])
    required = [*SECTOR_SYMBOLS, "BIL", RISK_SYMBOL]
    for t in range(max(start, 200), len(store["index"])):
        if all(available(store, symbol, t, 200) for symbol in required) and above_sma200(store, ind, RISK_SYMBOL, t):
            if all(value_at(ind["mom63"], symbol, t) is not None and value_at(ind["sma200"], symbol, t) is not None for symbol in SECTOR_SYMBOLS):
                return t
    raise RuntimeError("No common sector RS limited-history start after XLRE SMA warmup")


def sector_rs_weights(store: dict[str, Any], ind: dict[str, pd.DataFrame], signal: int) -> tuple[dict[str, float], str]:
    if not above_sma200(store, ind, RISK_SYMBOL, signal):
        return {"BIL": 1.0}, "spy_below_200d_sma"
    scored: list[tuple[str, float]] = []
    for symbol in SECTOR_SYMBOLS:
        momentum = value_at(ind["mom63"], symbol, signal)
        if momentum is not None and available(store, symbol, signal, 63) and liquidity_ok(store, ind, symbol, signal):
            scored.append((symbol, momentum))
    ranked = [symbol for symbol, _score in sorted(scored, key=lambda item: (-item[1], item[0]))[:2]]
    weights: dict[str, float] = {}
    for symbol in ranked:
        if above_sma200(store, ind, symbol, signal):
            weights[symbol] = weights.get(symbol, 0.0) + 0.5
        else:
            weights["BIL"] = weights.get("BIL", 0.0) + 0.5
    while sum(weights.values()) < 0.999:
        weights["BIL"] = weights.get("BIL", 0.0) + 0.5
    return weights, "weekly_top2_sector_rs"


def apply_turnover_cost(equity: float, old_weights: dict[str, float], new_weights: dict[str, float], slippage: float) -> tuple[float, float]:
    turnover = sum(abs(new_weights.get(symbol, 0.0) - old_weights.get(symbol, 0.0)) for symbol in set(new_weights) | set(old_weights))
    return equity - equity * turnover * slippage, turnover


def simulate_sector_rs(store: dict[str, Any], ind: dict[str, pd.DataFrame], start_idx: int, end_idx: int, slippage: float) -> dict[str, Any]:
    equity = STARTING_EQUITY
    peak = equity
    weights: dict[str, float] = {"BIL": 1.0}
    values: list[float] = []
    dates: list[pd.Timestamp] = []
    allocations: list[dict[str, float]] = []
    rebalance_rows: list[dict[str, Any]] = []
    rebalance_counts: dict[str, int] = {}
    selected_days = {symbol: 0 for symbol in UNIVERSE}
    turnover_total = 0.0
    trade_count = 0
    position_start: dict[str, pd.Timestamp] = {}
    holding_periods: list[int] = []
    last_week = ""
    week_start_equity = equity
    prior_week_return = 0.0
    risk_event_count = 0
    for t in range(start_idx + 1, end_idx + 1):
        ts = store["index"][t]
        week = date_week(ts)
        if week != last_week:
            if last_week:
                prior_week_return = equity / week_start_equity - 1.0 if week_start_equity else 0.0
            week_start_equity = equity
            drawdown_pct = equity / peak - 1.0 if peak else 0.0
            if drawdown_pct <= -0.06:
                new_weights, reason = {"BIL": 1.0}, "drawdown_pause_after_6pct"
                risk_event_count += 1
            elif prior_week_return <= -0.03:
                new_weights, reason = {"BIL": 1.0}, "weekly_loss_pause_after_3pct"
                risk_event_count += 1
            else:
                new_weights, reason = sector_rs_weights(store, ind, t - 1)
            before = deepcopy(weights)
            equity, turnover = apply_turnover_cost(equity, weights, new_weights, slippage)
            if turnover > 1e-10:
                changed = {symbol for symbol in set(weights) | set(new_weights) if abs(weights.get(symbol, 0.0) - new_weights.get(symbol, 0.0)) > 1e-10}
                trade_count += len([symbol for symbol in changed if symbol != "BIL"])
                for symbol in SECTOR_SYMBOLS:
                    old_weight = weights.get(symbol, 0.0)
                    new_weight = new_weights.get(symbol, 0.0)
                    if old_weight <= 0.01 and new_weight > 0.01:
                        position_start[symbol] = ts
                    if old_weight > 0.01 and new_weight <= 0.01 and symbol in position_start:
                        holding_periods.append(max((ts - position_start.pop(symbol)).days, 1))
            turnover_total += turnover
            weights = new_weights
            rebalance_counts[week] = rebalance_counts.get(week, 0) + 1
            rebalance_rows.append(
                {
                    "candidate_id": CANDIDATE_ID,
                    "date": str(ts.date()),
                    "rebalance_reason": reason,
                    "scheduled_weekly_rebalance": True,
                    "turnover": turnover,
                    "previous_weights": json.dumps({k: round(v, 6) for k, v in sorted(before.items())}, sort_keys=True),
                    "new_weights": json.dumps({k: round(v, 6) for k, v in sorted(weights.items())}, sort_keys=True),
                }
            )
            last_week = week
        daily_ret = sum(weight * symbol_return(store, symbol, t) for symbol, weight in weights.items())
        equity *= 1.0 + daily_ret
        peak = max(peak, equity)
        values.append(equity)
        dates.append(ts)
        allocations.append(deepcopy(weights))
        for symbol, weight in weights.items():
            if weight > 0.01:
                selected_days[symbol] = selected_days.get(symbol, 0) + 1
    final_date = store["index"][end_idx]
    for symbol, start in position_start.items():
        holding_periods.append(max((final_date - start).days, 1))
    equity_series = pd.Series(values, index=dates, dtype=float)
    allocation_frame = pd.DataFrame([{symbol: row.get(symbol, 0.0) for symbol in UNIVERSE} for row in allocations], index=dates).fillna(0.0)
    returns = equity_series.pct_change().dropna()
    allocation_count = max(len(allocations), 1)
    bil_freq = sum(1 for row in allocations if row.get("BIL", 0.0) > 0.01) / allocation_count
    mean_bil = sum(row.get("BIL", 0.0) for row in allocations) / allocation_count
    return {
        "candidate_id": CANDIDATE_ID,
        "equity": equity_series,
        "returns": returns,
        "allocations": allocations,
        "allocation_frame": allocation_frame,
        "trades": rebalance_rows,
        "stats": {
            "ending_equity": float(equity_series.iloc[-1]) if not equity_series.empty else STARTING_EQUITY,
            "total_return": total_return(equity_series),
            "annualized_return": annualized_return(equity_series),
            "volatility": annualized_volatility(returns),
            "sharpe": sharpe_ratio(returns),
            "max_drawdown": drawdown_dollars(equity_series),
            "worst_drawdown": drawdown_dollars(equity_series),
            "risk_buffer": drawdown_dollars(equity_series) - STOP_DOLLARS,
            "trade_count": trade_count,
            "average_holding_period": float(np.mean(holding_periods)) if holding_periods else 0.0,
            "turnover": turnover_total / STARTING_EQUITY,
            "max_sectors_held": int(max((sum(1 for symbol in SECTOR_SYMBOLS if row.get(symbol, 0.0) > 0.01) for row in allocations), default=0)),
            "max_weekly_rebalance_count_observed": int(max(rebalance_counts.values()) if rebalance_counts else 0),
            "bil_allocation_frequency": bil_freq,
            "mean_bil_allocation": mean_bil,
            "selected_symbol_days": selected_days,
            "risk_event_count": risk_event_count,
            "slippage": slippage,
        },
    }


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


def sample_starts(index: pd.DatetimeIndex, start_idx: int, end_idx: int, horizon: int) -> list[int]:
    starts = list(range(start_idx, max(start_idx, end_idx - horizon)))
    if len(starts) <= MAX_WINDOWS_PER_HORIZON:
        return starts
    return sorted(set(int(x) for x in np.linspace(starts[0], starts[-1], MAX_WINDOWS_PER_HORIZON)))


def window_rows(store: dict[str, Any], ind: dict[str, pd.DataFrame], start_idx: int, end_idx: int) -> tuple[list[dict[str, Any]], dict[int, dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    summaries: dict[int, dict[str, Any]] = {}
    for horizon in HORIZONS:
        for start in sample_starts(store["index"], start_idx, end_idx, horizon):
            result = simulate_sector_rs(store, ind, start, start + horizon, BASE_SLIPPAGE)
            equity = result["equity"]
            stop_hits = (equity - STARTING_EQUITY <= STOP_DOLLARS) if not equity.empty else pd.Series(dtype=bool)
            target300 = (equity - STARTING_EQUITY >= 300.0) if not equity.empty else pd.Series(dtype=bool)
            target400 = (equity - STARTING_EQUITY >= 400.0) if not equity.empty else pd.Series(dtype=bool)
            stop_first = int(np.where(stop_hits.values)[0][0]) if stop_hits.any() else None
            t300_first = int(np.where(target300.values)[0][0]) if target300.any() else None
            t400_first = int(np.where(target400.values)[0][0]) if target400.any() else None
            rows.append(
                {
                    "candidate_id": CANDIDATE_ID,
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
        summaries[horizon] = summarize_window_rows([row for row in rows if row["horizon"] == horizon], horizon)
    return rows, summaries


def summarize_window_rows(rows: list[dict[str, Any]], horizon: int) -> dict[str, Any]:
    if not rows:
        return {"candidate_id": CANDIDATE_ID, "horizon": horizon, "window_count": 0}
    df = pd.DataFrame(rows)
    return {
        "candidate_id": CANDIDATE_ID,
        "horizon": horizon,
        "window_count": int(len(df)),
        "median_final_equity": float(df["final_equity"].median()),
        "mean_final_equity": float(df["final_equity"].mean()),
        "target_300_before_stop_rate": float(df["target_300_before_stop"].mean()),
        "target_400_before_stop_rate": float(df["target_400_before_stop"].mean()),
        "worst_drawdown": float(df["max_drawdown"].min()),
        "stop_hit_rate": float(df["absolute_600_stop_hit"].mean()),
        "worst_loss_window": float(df["profit_dollars"].min()),
    }


def daily_return_for_weights(close: pd.DataFrame, today: int, weights: dict[str, float]) -> float:
    daily = 0.0
    for symbol, weight in weights.items():
        if active.available_at(close, symbol, today, 1):
            daily += weight * float(close.iloc[today][symbol] / close.iloc[today - 1][symbol] - 1.0)
    return daily


def active_reference_equity(close: pd.DataFrame, strategy_id: str, start_idx: int, end_idx: int) -> pd.Series:
    equity = STARTING_EQUITY
    values: list[float] = []
    dates = close.index[start_idx + 1 : end_idx + 1]
    months = np.array([dt.year * 12 + dt.month for dt in close.index], dtype=int)
    last_month = None
    weights: dict[str, float] = {}
    for t in range(start_idx + 1, end_idx + 1):
        month = int(months[t])
        if month != last_month:
            weights = active.strategy_weights(close, t - 1, strategy_id)
            last_month = month
        equity *= 1.0 + daily_return_for_weights(close, t, weights)
        values.append(equity)
    return pd.Series(values, index=dates, dtype=float)


def active_combo_equity(close: pd.DataFrame, start_idx: int, end_idx: int) -> pd.Series:
    vm_value = STARTING_EQUITY * 0.5
    dsr_value = STARTING_EQUITY * 0.5
    values: list[float] = []
    dates = close.index[start_idx + 1 : end_idx + 1]
    months = np.array([dt.year * 12 + dt.month for dt in close.index], dtype=int)
    last_month = None
    vm_weights: dict[str, float] = {}
    dsr_weights: dict[str, float] = {}
    for t in range(start_idx + 1, end_idx + 1):
        month = int(months[t])
        if month != last_month:
            total = vm_value + dsr_value
            vm_value = total * 0.5
            dsr_value = total * 0.5
            vm_weights = active.strategy_weights(close, t - 1, active.VM_ID)
            dsr_weights = active.strategy_weights(close, t - 1, active.DSR_ID)
            last_month = month
        vm_value *= 1.0 + daily_return_for_weights(close, t, vm_weights)
        dsr_value *= 1.0 + daily_return_for_weights(close, t, dsr_weights)
        values.append(vm_value + dsr_value)
    return pd.Series(values, index=dates, dtype=float)


def buyhold_equity(store: dict[str, Any], symbol: str, start_idx: int, end_idx: int) -> pd.Series:
    equity = STARTING_EQUITY
    values: list[float] = []
    dates: list[pd.Timestamp] = []
    for t in range(start_idx + 1, end_idx + 1):
        equity *= 1.0 + symbol_return(store, symbol, t)
        values.append(equity)
        dates.append(store["index"][t])
    return pd.Series(values, index=dates, dtype=float)


def equal_weight_sector_equity(store: dict[str, Any], start_idx: int, end_idx: int) -> pd.Series:
    equity = STARTING_EQUITY
    values: list[float] = []
    dates: list[pd.Timestamp] = []
    for t in range(start_idx + 1, end_idx + 1):
        available_sectors = [symbol for symbol in SECTOR_SYMBOLS if available(store, symbol, t, 1)]
        daily = sum(symbol_return(store, symbol, t) for symbol in available_sectors) / len(available_sectors) if available_sectors else symbol_return(store, "BIL", t)
        equity *= 1.0 + daily
        values.append(equity)
        dates.append(store["index"][t])
    return pd.Series(values, index=dates, dtype=float)


def benchmark_equities(store: dict[str, Any], start_idx: int, end_idx: int) -> dict[str, pd.Series]:
    close = store["close"]
    return {
        active.DSR_ID: active_reference_equity(close, active.DSR_ID, start_idx, end_idx),
        combo.COMBO_ID: active_combo_equity(close, start_idx, end_idx),
        active.VM_ID: active_reference_equity(close, active.VM_ID, start_idx, end_idx),
        active.SPY_200D_ID: active_reference_equity(close, active.SPY_200D_ID, start_idx, end_idx),
        "SPY_buy_hold": buyhold_equity(store, "SPY", start_idx, end_idx),
        "QQQ_buy_hold": buyhold_equity(store, "QQQ", start_idx, end_idx),
        "BIL_cash_proxy": buyhold_equity(store, "BIL", start_idx, end_idx),
        "equal_weight_sector_baseline": equal_weight_sector_equity(store, start_idx, end_idx),
    }


def series_metrics(series: pd.Series) -> dict[str, Any]:
    returns = series.pct_change().dropna()
    return {
        "ending_equity": float(series.iloc[-1]) if not series.empty else STARTING_EQUITY,
        "total_return": total_return(series),
        "annualized_return": annualized_return(series),
        "volatility": annualized_volatility(returns),
        "sharpe": sharpe_ratio(returns),
        "max_drawdown": drawdown_dollars(series),
        "risk_buffer": drawdown_dollars(series) - STOP_DOLLARS,
    }


def corr(left: pd.Series, right: pd.Series) -> float | str:
    frame = pd.concat([left.pct_change().rename("l"), right.pct_change().rename("r")], axis=1, join="inner").dropna()
    if len(frame) < 20 or frame["l"].std() == 0 or frame["r"].std() == 0:
        return "unavailable"
    return float(frame["l"].corr(frame["r"]))


def active_dsr_overlap(store: dict[str, Any], allocation_frame: pd.DataFrame, start_idx: int, end_idx: int) -> float:
    close = store["close"]
    overlaps: list[float] = []
    months = np.array([dt.year * 12 + dt.month for dt in close.index], dtype=int)
    last_month = None
    dsr_weights: dict[str, float] = {}
    for t in range(start_idx + 1, end_idx + 1):
        ts = store["index"][t]
        month = int(months[t])
        if month != last_month:
            dsr_weights = active.strategy_weights(close, t - 1, active.DSR_ID)
            last_month = month
        if ts not in allocation_frame.index:
            continue
        candidate_weights = allocation_frame.loc[ts].to_dict()
        overlaps.append(sum(min(float(candidate_weights.get(symbol, 0.0)), float(dsr_weights.get(symbol, 0.0))) for symbol in set(candidate_weights) | set(dsr_weights)))
    return float(np.mean(overlaps)) if overlaps else 0.0


def sector_concentration_rows(result: dict[str, Any]) -> list[dict[str, Any]]:
    frame = result["allocation_frame"]
    rows: list[dict[str, Any]] = []
    for symbol in UNIVERSE:
        series = frame[symbol] if symbol in frame else pd.Series(dtype=float)
        rows.append(
            {
                "candidate_id": CANDIDATE_ID,
                "symbol": symbol,
                "holding_frequency": float((series > 0.01).mean()) if len(series) else 0.0,
                "mean_allocation": float(series.mean()) if len(series) else 0.0,
                "max_allocation": float(series.max()) if len(series) else 0.0,
                "limited_history_label": LIMITED_HISTORY_LABEL,
            }
        )
    return rows


def bil_allocation_row(result: dict[str, Any], metrics: dict[str, Any]) -> dict[str, Any]:
    return {
        "candidate_id": CANDIDATE_ID,
        "bil_allocation_frequency": metrics["bil_allocation_frequency"],
        "mean_bil_allocation": metrics["mean_bil_allocation"],
        "ending_equity": metrics["ending_equity"],
        "max_drawdown": metrics["max_drawdown"],
        "excessive_bil_without_benefit": bool(metrics["mean_bil_allocation"] > 0.65 and metrics["ending_equity"] <= STARTING_EQUITY * 1.10),
        "limited_history_label": LIMITED_HISTORY_LABEL,
    }


def evaluate(store: dict[str, Any], ind: dict[str, pd.DataFrame], start_idx: int, end_idx: int) -> dict[str, Any]:
    result = simulate_sector_rs(store, ind, start_idx, end_idx, BASE_SLIPPAGE)
    stress = simulate_sector_rs(store, ind, start_idx, end_idx, STRESS_SLIPPAGE)
    windows, summaries = window_rows(store, ind, start_idx, end_idx)
    benchmarks = benchmark_equities(store, start_idx, end_idx)
    bench_metrics = {bid: series_metrics(series) for bid, series in benchmarks.items()}
    metrics = {**result["stats"]}
    metrics["stress_ending_equity"] = stress["stats"]["ending_equity"]
    metrics["stress_max_drawdown"] = stress["stats"]["max_drawdown"]
    metrics["window_180d_median_final_equity"] = summaries.get(180, {}).get("median_final_equity", "")
    metrics["window_180d_worst_drawdown"] = summaries.get(180, {}).get("worst_drawdown", "")
    metrics["window_180d_stop_hit_rate"] = summaries.get(180, {}).get("stop_hit_rate", "")
    metrics["target_300_before_stop_rate_180d"] = summaries.get(180, {}).get("target_300_before_stop_rate", "")
    deltas = {bid: metrics["ending_equity"] - data["ending_equity"] for bid, data in bench_metrics.items()}
    correlations = {bid: corr(result["equity"], series) for bid, series in benchmarks.items() if bid in {active.DSR_ID, combo.COMBO_ID, active.VM_ID, active.SPY_200D_ID}}
    overlap = active_dsr_overlap(store, result["allocation_frame"], start_idx, end_idx)
    duplication_rows = [
        {
            "candidate_id": CANDIDATE_ID,
            "reference_id": active.DSR_ID,
            "return_correlation": correlations.get(active.DSR_ID, "unavailable"),
            "mean_weight_overlap": overlap,
            "duplicate_or_clone": bool((isinstance(correlations.get(active.DSR_ID), float) and correlations[active.DSR_ID] >= 0.90) or overlap >= 0.80),
            "diagnostic": "active_dsr_overlap_and_correlation",
        },
        {
            "candidate_id": CANDIDATE_ID,
            "reference_id": combo.COMBO_ID,
            "return_correlation": correlations.get(combo.COMBO_ID, "unavailable"),
            "mean_weight_overlap": "unavailable",
            "duplicate_or_clone": bool(isinstance(correlations.get(combo.COMBO_ID), float) and correlations[combo.COMBO_ID] >= 0.92),
            "diagnostic": "active_combo_return_correlation",
        },
    ]
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
        "duplication_rows": duplication_rows,
        "sector_rows": sector_concentration_rows(result),
        "bil_row": bil_allocation_row(result, metrics),
    }


def risk_improved(candidate: dict[str, Any], benchmark: dict[str, Any]) -> bool:
    return candidate["ending_equity"] > STARTING_EQUITY and candidate["max_drawdown"] - benchmark["max_drawdown"] > 150.0


def decision(payload: dict[str, Any]) -> tuple[str, str, dict[str, bool]]:
    metrics = payload["metrics"]
    bench = payload["bench_metrics"]
    sector_rows = [row for row in payload["sector_rows"] if row["symbol"] != "BIL"]
    top_mean_allocation = max((row["mean_allocation"] for row in sector_rows), default=0.0)
    top_holding_frequency = max((row["holding_frequency"] for row in sector_rows), default=0.0)
    duplicate = any(row["duplicate_or_clone"] is True for row in payload["duplication_rows"])
    dsr_ok = payload["deltas"][active.DSR_ID] > 0 or risk_improved(metrics, bench[active.DSR_ID])
    combo_ok = payload["deltas"][combo.COMBO_ID] > 0 or risk_improved(metrics, bench[combo.COMBO_ID])
    spy200_ok = payload["deltas"][active.SPY_200D_ID] > 0 or risk_improved(metrics, bench[active.SPY_200D_ID])
    gates = {
        "active_dsr_gate": bool(dsr_ok),
        "active_combo_gate": bool(combo_ok),
        "spy200_gate": bool(spy200_ok),
        "risk_buffer_gate": bool(metrics["risk_buffer"] > 25 and metrics["stress_max_drawdown"] > STOP_DOLLARS and metrics.get("window_180d_stop_hit_rate", 1.0) == 0.0),
        "slippage_stress_gate": bool(metrics["stress_ending_equity"] >= metrics["ending_equity"] - 150 and metrics["stress_max_drawdown"] > STOP_DOLLARS),
        "turnover_gate": bool(metrics["max_weekly_rebalance_count_observed"] <= 1 and metrics["turnover"] <= 30.0),
        "concentration_gate": bool(top_mean_allocation <= 0.35 and top_holding_frequency <= 0.70),
        "bil_allocation_gate": bool(metrics["mean_bil_allocation"] <= 0.65 or metrics["ending_equity"] > STARTING_EQUITY * 1.10),
        "duplication_gate": not duplicate,
        "limited_history_strength_gate": bool(metrics["ending_equity"] > STARTING_EQUITY and metrics["window_180d_median_final_equity"] > STARTING_EQUITY),
    }
    if all(gates.values()):
        return "promotion_review_candidate_limited_history", "limited_history_sector_rs_all_gates_passed", gates
    if not gates["risk_buffer_gate"]:
        return "discovery_reject", "limited_history_sector_rs_failed_risk_gate", gates
    if not gates["active_dsr_gate"] or not gates["active_combo_gate"] or not gates["spy200_gate"]:
        return "discovery_reject", "limited_history_sector_rs_failed_same_window_benchmark_gate", gates
    if not gates["slippage_stress_gate"]:
        return "discovery_reject", "limited_history_sector_rs_failed_slippage_stress_gate", gates
    if not gates["concentration_gate"] or not gates["bil_allocation_gate"]:
        return "discovery_reject", "limited_history_sector_rs_concentration_or_bil_gate_failed", gates
    if not gates["duplication_gate"]:
        return "discovery_reject", "limited_history_sector_rs_duplicate_or_near_clone", gates
    return "discovery_reject", "limited_history_sector_rs_evidence_not_strong_enough", gates


def update_metadata(root: Path, output: Path, manifest: dict[str, Any]) -> tuple[bool, bool, bool]:
    registry_updated = False
    registry_path = root / REGISTRY_PATH
    registry = load_yaml(registry_path)
    meta = registry.setdefault("registry", {})
    meta.update(
        {
            "sector_rs_limited_history_discovery_path": str(output),
            "sector_rs_limited_history_discovery_status": "completed",
            "sector_rs_limited_history_discovery_outcome": manifest["discovery_outcome"],
            "sector_rs_limited_history_promotion_candidates_count": manifest["promotion_candidates_count"],
            "sector_rs_limited_history_promotion_candidate_ids": manifest["promotion_candidate_ids"],
            "sector_rs_limited_history_next_action": manifest["next_action"],
            "current_next_action": manifest["next_action"],
            "next_action": manifest["next_action"],
            "candidate_exhaustive_run": False,
            "paper_forward_review": False,
            "paper_forward_activation": False,
            "provider_download": False,
            "broker_path_touched": False,
            "live_orders": False,
            "real_money_recommendation": False,
            "etf_wrapper_track_reopened": False,
            "updated_utc": manifest["created_utc"],
        }
    )
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(yaml.safe_dump(registry, sort_keys=False, width=120, allow_unicode=False), encoding="utf-8")
    registry_updated = True

    research_updated = write_roadmap_section(
        root / RESEARCH_ROADMAP_PATH,
        "## Sector RS Limited-History Discovery Result",
        roadmap_section(manifest, output),
    )
    expansion_updated = write_roadmap_section(
        root / EXPANSION_ROADMAP_PATH,
        "## Sector RS Limited-History Discovery Result",
        roadmap_section(manifest, output),
    )
    return registry_updated, research_updated, expansion_updated


def write_roadmap_section(path: Path, marker: str, section: str) -> bool:
    existing = path.read_text(encoding="utf-8") if path.exists() else "# Research Roadmap\n"
    updated = existing.split(marker, 1)[0].rstrip() + "\n\n" + section if marker in existing else existing.rstrip() + "\n\n" + section
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(updated.rstrip() + "\n", encoding="utf-8")
    return True


def roadmap_section(manifest: dict[str, Any], output: Path) -> str:
    return f"""## Sector RS Limited-History Discovery Result

- Created UTC: `{manifest['created_utc']}`
- Evidence path: `{output}`
- Candidate evaluated: `{CANDIDATE_ID}`
- Limited-history label: `{LIMITED_HISTORY_LABEL}`
- Methodology: `{METHODOLOGY}`
- Discovery outcome: `{manifest['discovery_outcome']}`
- Promotion candidates: `{manifest['promotion_candidates_count']}`
- Rejected candidates: `{', '.join(manifest['rejected_candidate_ids']) or 'none'}`
- Next action: `{manifest['next_action']}`
- This is not a 2007-style full-history test. Same-window benchmarks were recomputed. No candidate_exhaustive, paper-forward activation, provider download, broker/live path, ETF-wrapper reopening, second-expansion rejected-row reopening, or real-money recommendation is authorized by this result.
"""


def write_outputs(output: Path, store: dict[str, Any], payload: dict[str, Any], outcome: str, reason: str, gates: dict[str, bool], manifest: dict[str, Any]) -> None:
    metrics = payload["metrics"]
    result = payload["result"]
    result_row = {
        "candidate_id": CANDIDATE_ID,
        "lane_id": manifest["lane_id"],
        "outcome": outcome,
        "reason_code": reason,
        "limited_history_label": LIMITED_HISTORY_LABEL,
        "methodology": METHODOLOGY,
        "not_2007_style_full_history_test": True,
        **metrics,
    }
    write_json(output / "sector_rs_limited_history_discovery_manifest.json", manifest)
    write_csv(output / "sector_rs_limited_history_candidate_results.csv", [result_row], list(result_row.keys()))
    write_json(
        output / "sector_rs_limited_history_candidate_metrics.json",
        {
            CANDIDATE_ID: {
                **metrics,
                "window_summaries": payload["summaries"],
                "correlations": payload["correlations"],
                "gate_results": gates,
                "limited_history_label": LIMITED_HISTORY_LABEL,
                "methodology": METHODOLOGY,
            }
        },
    )
    delta_rows = [{"candidate_id": CANDIDATE_ID, "benchmark_id": bid, "ending_equity_delta": delta, "limited_history_label": LIMITED_HISTORY_LABEL} for bid, delta in payload["deltas"].items()]
    write_csv(output / "sector_rs_limited_history_benchmark_deltas.csv", delta_rows, ["candidate_id", "benchmark_id", "ending_equity_delta", "limited_history_label"])
    same_rows = [{"candidate_id": CANDIDATE_ID, "benchmark_id": bid, "same_window_start": str(result["equity"].index[0].date()), "same_window_end": str(result["equity"].index[-1].date()), "benchmark_available": True, **data} for bid, data in payload["bench_metrics"].items()]
    write_csv(output / "sector_rs_limited_history_same_window_benchmarks.csv", same_rows, sorted({key for row in same_rows for key in row}))
    write_csv(
        output / "sector_rs_limited_history_risk_gate_results.csv",
        [
            {
                "candidate_id": CANDIDATE_ID,
                "risk_buffer": metrics["risk_buffer"],
                "max_drawdown": metrics["max_drawdown"],
                "worst_drawdown": metrics["worst_drawdown"],
                "stress_max_drawdown": metrics["stress_max_drawdown"],
                "stop_hit_rate_180d": metrics.get("window_180d_stop_hit_rate", ""),
                "risk_gate_pass": gates["risk_buffer_gate"],
            }
        ],
        ["candidate_id", "risk_buffer", "max_drawdown", "worst_drawdown", "stress_max_drawdown", "stop_hit_rate_180d", "risk_gate_pass"],
    )
    write_csv(
        output / "sector_rs_limited_history_slippage_stress_results.csv",
        [
            {
                "candidate_id": CANDIDATE_ID,
                "base_ending_equity": metrics["ending_equity"],
                "stress_ending_equity": metrics["stress_ending_equity"],
                "base_max_drawdown": metrics["max_drawdown"],
                "stress_max_drawdown": metrics["stress_max_drawdown"],
                "stress_pass": gates["slippage_stress_gate"],
            }
        ],
        ["candidate_id", "base_ending_equity", "stress_ending_equity", "base_max_drawdown", "stress_max_drawdown", "stress_pass"],
    )
    write_csv(output / "sector_rs_limited_history_trade_diagnostics.csv", result["trades"], ["candidate_id", "date", "rebalance_reason", "scheduled_weekly_rebalance", "turnover", "previous_weights", "new_weights"])
    write_csv(output / "sector_rs_limited_history_sector_concentration.csv", payload["sector_rows"], ["candidate_id", "symbol", "holding_frequency", "mean_allocation", "max_allocation", "limited_history_label"])
    write_csv(output / "sector_rs_limited_history_bil_allocation_diagnostics.csv", [payload["bil_row"]], ["candidate_id", "bil_allocation_frequency", "mean_bil_allocation", "ending_equity", "max_drawdown", "excessive_bil_without_benefit", "limited_history_label"])
    write_csv(output / "sector_rs_limited_history_duplication_diagnostics.csv", payload["duplication_rows"], ["candidate_id", "reference_id", "return_correlation", "mean_weight_overlap", "duplicate_or_clone", "diagnostic"])
    promotion_rows = [{"candidate_id": CANDIDATE_ID, "lane_id": manifest["lane_id"], "outcome": outcome, "reason_code": reason}] if outcome == "promotion_review_candidate_limited_history" else []
    write_csv(output / "sector_rs_limited_history_promotion_candidates.csv", promotion_rows, ["candidate_id", "lane_id", "outcome", "reason_code"])
    (output / "sector_rs_limited_history_rejection_reasons.md").write_text(rejection_md(outcome, reason, gates), encoding="utf-8")
    (output / "sector_rs_limited_history_next_action.md").write_text(next_action_md(manifest), encoding="utf-8")
    (output / "sector_rs_limited_history_discovery_summary.md").write_text(summary_md(result_row, payload, manifest), encoding="utf-8")


def rejection_md(outcome: str, reason: str, gates: dict[str, bool]) -> str:
    if outcome != "discovery_reject":
        return "# Sector RS Limited-History Rejection Reasons\n\nNo rejected candidate.\n"
    failed = [name for name, passed in gates.items() if not passed]
    return "# Sector RS Limited-History Rejection Reasons\n\n" + f"- `{CANDIDATE_ID}`: `{outcome}` because `{reason}`.\n- Failed gates: `{', '.join(failed)}`.\n"


def next_action_md(manifest: dict[str, Any]) -> str:
    return f"""# Sector RS Limited-History Next Action

`{manifest['next_action']}`

Limited-history status: `{LIMITED_HISTORY_LABEL}`.

Do not run this next action from the sector RS discovery task.
"""


def summary_md(result_row: dict[str, Any], payload: dict[str, Any], manifest: dict[str, Any]) -> str:
    metrics = payload["metrics"]
    active_combo_delta = payload["deltas"].get(combo.COMBO_ID, "")
    active_dsr_delta = payload["deltas"].get(active.DSR_ID, "")
    return f"""# Sector RS Limited-History Discovery Summary

Created UTC: `{manifest['created_utc']}`

Candidate: `{CANDIDATE_ID}`

Lane: `{manifest['lane_id']}`

Outcome: `{result_row['outcome']}`

Reason: `{result_row['reason_code']}`

Limited-history label: `{LIMITED_HISTORY_LABEL}`

Methodology: `{METHODOLOGY}`

This is not a 2007-style full-history test. All listed benchmarks were recomputed over the same limited-history window.

## Key Metrics

- Ending equity: `{fmt(metrics['ending_equity'])}`
- Max drawdown: `{fmt(metrics['max_drawdown'])}`
- Risk buffer: `{fmt(metrics['risk_buffer'])}`
- 180d median final equity: `{fmt(metrics.get('window_180d_median_final_equity', ''))}`
- BIL allocation frequency: `{fmt(metrics['bil_allocation_frequency'])}`
- Mean BIL allocation: `{fmt(metrics['mean_bil_allocation'])}`
- Active DSR delta: `{fmt(active_dsr_delta)}`
- Active combo delta: `{fmt(active_combo_delta)}`

Next action: `{manifest['next_action']}`
"""


def consistency_check(
    output: Path,
    manifest: dict[str, Any],
    outcome: str,
    strategies_before: list[dict[str, Any]],
    strategies_after: list[dict[str, Any]],
    active_before: dict[str, str],
    active_after: dict[str, str],
) -> dict[str, Any]:
    required_files = [
        "sector_rs_limited_history_discovery_manifest.json",
        "sector_rs_limited_history_discovery_summary.md",
        "sector_rs_limited_history_candidate_results.csv",
        "sector_rs_limited_history_candidate_metrics.json",
        "sector_rs_limited_history_benchmark_deltas.csv",
        "sector_rs_limited_history_same_window_benchmarks.csv",
        "sector_rs_limited_history_risk_gate_results.csv",
        "sector_rs_limited_history_slippage_stress_results.csv",
        "sector_rs_limited_history_trade_diagnostics.csv",
        "sector_rs_limited_history_sector_concentration.csv",
        "sector_rs_limited_history_bil_allocation_diagnostics.csv",
        "sector_rs_limited_history_duplication_diagnostics.csv",
        "sector_rs_limited_history_promotion_candidates.csv",
        "sector_rs_limited_history_rejection_reasons.md",
        "sector_rs_limited_history_next_action.md",
    ]
    check = {
        "exactly_one_candidate_evaluated": manifest["candidate_count"] == 1 and manifest["candidate_id"] == CANDIDATE_ID,
        "candidate_id_is_sector_rs": manifest["candidate_id"] == CANDIDATE_ID,
        "no_other_expansion_candidates_evaluated": manifest["evaluated_candidate_ids"] == [CANDIDATE_ID] and not bool(set(manifest["evaluated_candidate_ids"]) & set(EXCLUDED_IDS)),
        "second_expansion_rejects_remain_rejected": manifest["second_expansion_rejects_remain_rejected"],
        "no_intraday_candidate_included": not manifest["intraday_candidates_included"],
        "no_event_data_candidate_included": not manifest["event_data_candidates_included"],
        "frozen_rules_unchanged": not manifest["frozen_rules_changed"],
        "universe_unchanged": not manifest["candidate_universe_changed"] and manifest["candidate_universe"] == UNIVERSE,
        "xlre_remains_in_universe": "XLRE" in manifest["candidate_universe"],
        "limited_history_label_present": manifest["limited_history_due_to_xlre_inception"] and manifest["limited_history_label"] == LIMITED_HISTORY_LABEL,
        "methodology_is_common_start_2016_after_xlre_sma_warmup": manifest["methodology"] == METHODOLOGY,
        "same_window_benchmark_recompute_used": manifest["same_window_benchmark_recompute_used"],
        "full_history_benchmarks_not_used": manifest["not_2007_style_full_history_test"],
        "provider_download_false": not manifest["provider_download"],
        "candidate_outcome_valid": outcome in VALID_OUTCOMES,
        "no_candidate_exhaustive": not manifest["candidate_exhaustive_run"] and outcome not in FORBIDDEN_OUTCOMES,
        "no_paper_forward": not manifest["paper_forward_review"] and not manifest["paper_forward_activation"] and outcome not in {"paper_forward", "paper_forward_active"},
        "no_broker_live_path": not manifest["broker_path_touched"] and not manifest["live_orders"],
        "risk_gate_results_exist": (output / "sector_rs_limited_history_risk_gate_results.csv").exists(),
        "slippage_stress_results_exist": (output / "sector_rs_limited_history_slippage_stress_results.csv").exists(),
        "benchmark_deltas_exist": (output / "sector_rs_limited_history_benchmark_deltas.csv").exists(),
        "sector_concentration_diagnostics_exist": (output / "sector_rs_limited_history_sector_concentration.csv").exists(),
        "bil_allocation_diagnostics_exist": (output / "sector_rs_limited_history_bil_allocation_diagnostics.csv").exists(),
        "promotion_candidate_file_exists": (output / "sector_rs_limited_history_promotion_candidates.csv").exists(),
        "rejection_reasons_exist_if_rejected": outcome != "discovery_reject" or (output / "sector_rs_limited_history_rejection_reasons.md").exists(),
        "manifest_flags_match_scope": all(manifest[key] == value for key, value in MANIFEST_FLAGS.items()),
        "active_strategy_state_unchanged": strategies_before == strategies_after and active_before == active_after,
        "required_files_exist": all((output / name).exists() for name in required_files),
        "next_action_valid_and_explicit": manifest["next_action"] in VALID_NEXT_ACTIONS,
    }
    check["consistency_passed"] = all(bool(value) for value in check.values())
    return check


def run_sector_rs_limited_history_discovery_batch(root: Path = ROOT) -> dict[str, Any]:
    output = clean_output(root)
    created_utc = now_utc()
    batch, mismatches = validate_authorization(root)
    if mismatches:
        raise RuntimeError("Authorization failed: " + "; ".join(mismatches))
    strategies_before = strategy_snapshot(root)
    active_before = active_observation_hashes(root)
    store = load_prices(root)
    if not store.get("available"):
        raise RuntimeError("Missing cached symbols: " + ",".join(store.get("missing", [])))
    ind = indicators(store)
    start_idx = first_valid_signal_index(store, ind)
    end_idx = len(store["index"]) - 1
    payload = evaluate(store, ind, start_idx, end_idx)
    outcome, reason, gates = decision(payload)
    if outcome not in VALID_OUTCOMES:
        raise RuntimeError(f"invalid sector RS discovery outcome: {outcome}")
    promotion_ids = [CANDIDATE_ID] if outcome == "promotion_review_candidate_limited_history" else []
    rejected_ids = [CANDIDATE_ID] if outcome == "discovery_reject" else []
    next_action = NEXT_ACTION_PROMOTION if promotion_ids else NEXT_ACTION_TOM_AUDIT
    lane_id = batch.get("metadata", {}).get("lane_id") or batch.get("candidates", [{}])[0].get("lane_id", "sector_rs_limited_history")
    manifest = {
        "artifact": "sector_rs_limited_history_discovery_batch",
        "created_utc": created_utc,
        "output_dir": str(output),
        "candidate_id": CANDIDATE_ID,
        "evaluated_candidate_ids": [CANDIDATE_ID],
        "candidate_universe": UNIVERSE,
        "risk_filter_symbol": RISK_SYMBOL,
        "limited_history_label": LIMITED_HISTORY_LABEL,
        "lane_id": lane_id,
        "same_window_start": str(store["index"][start_idx + 1].date()),
        "same_window_signal_start": str(store["index"][start_idx].date()),
        "same_window_end": str(store["index"][end_idx].date()),
        "discovery_outcome": outcome,
        "promotion_candidates_count": len(promotion_ids),
        "promotion_candidate_ids": promotion_ids,
        "rejected_candidate_ids": rejected_ids,
        "next_action": next_action,
        "intraday_candidates_included": False,
        "event_data_candidates_included": False,
        **MANIFEST_FLAGS,
    }
    registry_updated, research_roadmap_updated, expansion_roadmap_updated = update_metadata(root, output, manifest)
    manifest["registry_metadata_updated"] = registry_updated
    manifest["research_roadmap_updated"] = research_roadmap_updated
    manifest["expansion_roadmap_updated"] = expansion_roadmap_updated
    write_outputs(output, store, payload, outcome, reason, gates, manifest)
    strategies_after = strategy_snapshot(root)
    active_after = active_observation_hashes(root)
    consistency = consistency_check(output, manifest, outcome, strategies_before, strategies_after, active_before, active_after)
    write_json(output / "sector_rs_limited_history_discovery_consistency_check.json", consistency)
    return {
        "output_dir": str(output),
        "candidate_id": CANDIDATE_ID,
        "discovery_outcome": outcome,
        "next_action": next_action,
        "consistency": consistency,
    }


def main() -> None:
    print(json.dumps(run_sector_rs_limited_history_discovery_batch(ROOT), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
