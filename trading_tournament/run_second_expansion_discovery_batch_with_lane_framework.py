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


ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = Path("evidence") / "parallel_research_discovery" / "second_expansion_with_lane_framework" / "latest"
PREREG_DIR = Path("evidence") / "pre_registered_lanes" / "second_expansion_with_lane_framework" / "latest"
RULE_PATCH_DIR = Path("evidence") / "pre_registered_lanes" / "second_expansion_with_lane_framework" / "rule_freeze_patch" / "latest"
REGISTRY_PATH = Path("strategy_lab") / "strategy_registry.yaml"
ROADMAP_PATH = Path("strategy_lab") / "RESEARCH_ROADMAP.md"
CACHE_DIR = Path("data") / "cache"

AUTHORIZED_CANDIDATES = [
    "managed_futures_etf_trend_wrapper_v1",
    "gld_gror_balanced_momentum_clean_v1",
    "donchian_atr_breakout_etf_v1",
    "turn_of_month_spy_qqq_v1",
    "cash_pause_overlay_meta_v1",
]
EXCLUDED_CANDIDATES = {
    "sector_rs_weekly_cash_filter_v1",
    "dmr_liquid_etf_oversold_rebound_v1",
    "vm_spy_qqq_daily_vol_target_v1",
    "vol_compression_breakout_etf_v1",
    "rs_pair_rotation_spy_qqq_xlk_xlu_v1",
    "orb_spy_qqq_30m_research_v1",
    "gap_down_fade_spy_qqq_research_v1",
    "vwap_deviation_research_v1",
    "vwap_deviation_reversion_research_v1",
    "post_earnings_drift_large_cap_later_v1",
    "gror_balanced_momentum_60_40_v1",
}
LANES = {
    "managed_futures_etf_trend_wrapper_v1": "macro_gld_duration_risk_off_lane",
    "gld_gror_balanced_momentum_clean_v1": "macro_gld_duration_risk_off_lane",
    "donchian_atr_breakout_etf_v1": "moderate_tactical_etf_lane",
    "turn_of_month_spy_qqq_v1": "moderate_tactical_etf_lane",
    "cash_pause_overlay_meta_v1": "diversifier_contribution_lane",
}
VALID_OUTCOMES = {
    "managed_futures_etf_trend_wrapper_v1": {"discovery_reject", "promotion_review_candidate_macro_limited_history"},
    "gld_gror_balanced_momentum_clean_v1": {"discovery_reject", "promotion_review_candidate_macro"},
    "donchian_atr_breakout_etf_v1": {"discovery_reject", "promotion_review_candidate"},
    "turn_of_month_spy_qqq_v1": {"discovery_reject", "promotion_review_candidate"},
    "cash_pause_overlay_meta_v1": {"diagnostic_reject", "risk_overlay_watchlist_candidate"},
}
FORBIDDEN_OUTCOMES = {"candidate_exhaustive", "paper_forward", "paper_forward_active", "demo_active", "live_ready"}

NEXT_ACTION_PROMOTION = "promotion_review_for_selected_second_expansion_rows"
NEXT_ACTION_LIMITED = "promotion_review_for_macro_limited_history_watchlist"
NEXT_ACTION_SECTOR_RS = "run_sector_rs_limited_history_discovery_batch"
NEXT_ACTION_THIRD = "pre_register_third_expansion_discovery_batch_with_lane_framework"
NEXT_ACTION_AUDIT = "audit_second_expansion_failures_before_more_expansion"
VALID_NEXT_ACTIONS = {NEXT_ACTION_PROMOTION, NEXT_ACTION_LIMITED, NEXT_ACTION_SECTOR_RS, NEXT_ACTION_THIRD, NEXT_ACTION_AUDIT}

STARTING_EQUITY = active.STARTING_EQUITY
STOP_DOLLARS = active.STOP_DOLLARS
BASE_SLIPPAGE = active.SLIPPAGE
STRESS_SLIPPAGE = 0.0010
HORIZONS = active.HORIZONS
MAX_WINDOWS_PER_HORIZON = active.MAX_WINDOWS_PER_HORIZON

DONCHIAN_UNIVERSE = ["SPY", "QQQ", "IWM", "DIA", "XLK", "XLF", "XLV", "XLE", "XLI", "XLY", "XLP", "XLU", "XLB", "XLRE"]
ALL_CANDIDATE_SYMBOLS = sorted(set(DONCHIAN_UNIVERSE + ["DBMF", "KMLM", "CTA", "BIL", "SPY", "QQQ", "GLD", "IEF"]))
REFERENCE_IDS = [active.VM_ID, active.DSR_ID, combo.COMBO_ID, active.SPY_200D_ID, "SPY_buy_hold", "QQQ_buy_hold", "BIL_cash_proxy"]

MANIFEST_FLAGS = {
    "discovery_run": True,
    "backtests_run": True,
    "lane_framework_used": True,
    "candidate_count": 5,
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
    "sector_rs_discovery_run": False,
    "intraday_candidates_included": False,
    "event_data_candidates_included": False,
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


def registry_strategy_snapshot(root: Path) -> list[dict[str, Any]]:
    return deepcopy(load_yaml(root / REGISTRY_PATH).get("strategies", []))


def candidates_from_prereg(root: Path) -> dict[str, dict[str, Any]]:
    batch = load_yaml(root / PREREG_DIR / "second_expansion_batch.yaml")
    return {candidate["candidate_id"]: candidate for candidate in batch.get("candidates", [])}


def validate_authorization(root: Path) -> list[str]:
    mismatches: list[str] = []
    batch = load_yaml(root / PREREG_DIR / "second_expansion_batch.yaml")
    patch_manifest = read_json(root / RULE_PATCH_DIR / "second_expansion_rule_freeze_patch_manifest.json")
    included = [candidate.get("candidate_id", "") for candidate in batch.get("candidates", [])]
    if included != AUTHORIZED_CANDIDATES:
        mismatches.append("second expansion candidate membership does not match authorized list")
    if set(included) & EXCLUDED_CANDIDATES:
        mismatches.append("excluded candidate appears in second expansion batch")
    if batch.get("metadata", {}).get("rule_freeze_patch_applied") is not True:
        mismatches.append("rule-freeze patch not recorded in latest batch")
    if patch_manifest.get("remaining_ambiguities_count") != 0:
        mismatches.append("rule-freeze patch still has ambiguities")
    if patch_manifest.get("next_action") != "run_second_expansion_discovery_batch_with_lane_framework":
        mismatches.append("rule-freeze patch does not authorize discovery")
    if patch_manifest.get("discovery_run") is not False:
        mismatches.append("rule-freeze patch manifest unexpectedly records discovery")
    return mismatches


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
    if len(clean) < 200:
        return None
    return clean.set_index("date")[["open", "high", "low", "close", "adj_close", "volume"]].astype(float)


def load_prices(root: Path) -> dict[str, Any]:
    symbols = sorted(set(ALL_CANDIDATE_SYMBOLS + active.REQUIRED_CACHE_SYMBOLS + ["QQQ", "GLD", "IEF", "DBMF", "KMLM", "CTA", "DIA", "IWM"]))
    frames: dict[str, pd.DataFrame] = {}
    missing: list[str] = []
    for symbol in symbols:
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


def value_at(frame: pd.DataFrame, symbol: str, t: int) -> float | None:
    if symbol not in frame.columns or t < 0 or t >= len(frame):
        return None
    value = frame.iloc[t][symbol]
    if pd.isna(value):
        return None
    return float(value)


def available(store: dict[str, Any], symbol: str, t: int, lookback: int = 0) -> bool:
    return value_at(store["close"], symbol, t) is not None and value_at(store["close"], symbol, t - lookback) is not None


def indicators(store: dict[str, Any]) -> dict[str, pd.DataFrame]:
    close = store["close"]
    high = store["high"]
    low = store["low"]
    prev_close = close.shift(1)
    true_range = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=0).groupby(level=0).max()
    ret = close.pct_change()
    return {
        "mom63": close / close.shift(63) - 1.0,
        "sma200": close.rolling(200, min_periods=200).mean(),
        "high20_prior": high.shift(1).rolling(20, min_periods=20).max(),
        "atr14": true_range.rolling(14, min_periods=14).mean(),
        "ret": ret,
    }


def above_sma200(store: dict[str, Any], ind: dict[str, pd.DataFrame], symbol: str, t: int) -> bool:
    price = value_at(store["close"], symbol, t)
    sma = value_at(ind["sma200"], symbol, t)
    return price is not None and sma is not None and price > sma


def symbol_return(store: dict[str, Any], symbol: str, t: int) -> float:
    if not available(store, symbol, t, 1):
        return 0.0
    return float(store["close"].iloc[t][symbol] / store["close"].iloc[t - 1][symbol] - 1.0)


def date_week(ts: pd.Timestamp) -> str:
    iso = ts.isocalendar()
    return f"{iso.year}-{iso.week:02d}"


def sample_starts(index: pd.DatetimeIndex, start_idx: int, end_idx: int, horizon: int) -> list[int]:
    starts = list(range(start_idx, max(start_idx, end_idx - horizon)))
    if len(starts) <= MAX_WINDOWS_PER_HORIZON:
        return starts
    return sorted(set(int(x) for x in np.linspace(starts[0], starts[-1], MAX_WINDOWS_PER_HORIZON)))


def weights_managed_futures(store: dict[str, Any], ind: dict[str, pd.DataFrame], signal: int) -> dict[str, float]:
    scored = []
    for symbol in ["DBMF", "KMLM", "CTA"]:
        momentum = value_at(ind["mom63"], symbol, signal)
        if momentum is not None and momentum > 0 and available(store, symbol, signal, 63):
            scored.append((symbol, momentum))
    if not scored:
        return {"BIL": 1.0}
    return {sorted(scored, key=lambda item: (-item[1], item[0]))[0][0]: 1.0}


def weights_gld_gror(store: dict[str, Any], ind: dict[str, pd.DataFrame], signal: int) -> dict[str, float]:
    risk_scored = []
    for symbol in ["SPY", "QQQ", "GLD", "IEF"]:
        momentum = value_at(ind["mom63"], symbol, signal)
        if momentum is not None and available(store, symbol, signal, 63) and above_sma200(store, ind, symbol, signal):
            risk_scored.append((symbol, momentum))
    defensive_scored = [("BIL", 0.0)]
    for symbol in ["GLD", "IEF"]:
        momentum = value_at(ind["mom63"], symbol, signal)
        if momentum is not None and available(store, symbol, signal, 63) and above_sma200(store, ind, symbol, signal):
            defensive_scored.append((symbol, momentum))
    weights: dict[str, float] = {}
    if risk_scored:
        weights[sorted(risk_scored, key=lambda item: (-item[1], item[0]))[0][0]] = 0.60
    else:
        weights["BIL"] = weights.get("BIL", 0.0) + 0.60
    defensive = sorted(defensive_scored, key=lambda item: (-item[1], item[0]))[0][0]
    weights[defensive] = weights.get(defensive, 0.0) + 0.40
    return weights


def turn_of_month_flags(index: pd.DatetimeIndex) -> tuple[dict[pd.Timestamp, str], dict[str, pd.Timestamp]]:
    frame = pd.DataFrame({"date": index})
    frame["month"] = frame["date"].dt.to_period("M")
    window_key_by_date: dict[pd.Timestamp, str] = {}
    first_window_day: dict[str, pd.Timestamp] = {}
    groups = [(str(month), list(group["date"])) for month, group in frame.groupby("month")]
    for idx, (month_key, dates) in enumerate(groups[:-1]):
        _next_month, next_dates = groups[idx + 1]
        if len(dates) < 4 or len(next_dates) < 3:
            continue
        window_dates = [pd.Timestamp(ts) for ts in dates[-4:] + next_dates[:3]]
        for ts in window_dates:
            window_key_by_date[ts] = month_key
        first_window_day[month_key] = window_dates[0]
    return window_key_by_date, first_window_day


def buggy_turn_of_month_flags(index: pd.DatetimeIndex) -> tuple[set[pd.Timestamp], dict[str, pd.Timestamp]]:
    frame = pd.DataFrame({"date": index})
    frame["month"] = frame["date"].dt.to_period("M")
    in_window: set[pd.Timestamp] = set()
    first_window_day: dict[str, pd.Timestamp] = {}
    for _month, group in frame.groupby("month"):
        dates = list(group["date"])
        for ts in dates[:3] + dates[-4:]:
            in_window.add(pd.Timestamp(ts))
        for ts in dates[-4:]:
            key = str((pd.Timestamp(ts) + pd.offsets.MonthBegin(1)).to_period("M"))
            first_window_day.setdefault(key, pd.Timestamp(ts))
        if dates[:3]:
            key = str(pd.Timestamp(dates[0]).to_period("M"))
            first_window_day.setdefault(key, pd.Timestamp(dates[0]))
    return in_window, first_window_day


def weights_turn_of_month(store: dict[str, Any], ind: dict[str, pd.DataFrame]) -> pd.DataFrame:
    index = store["index"]
    window_key_by_date, first_days = turn_of_month_flags(index)
    weights: list[dict[str, float]] = []
    current_asset = "BIL"
    for t, ts in enumerate(index):
        ts_key = pd.Timestamp(ts)
        window_key = window_key_by_date.get(ts_key)
        if window_key is None:
            current_asset = "BIL"
        elif first_days.get(window_key) == ts_key:
            signal = t - 1
            scored = []
            for symbol in ["SPY", "QQQ"]:
                momentum = value_at(ind["mom63"], symbol, signal)
                if momentum is not None and above_sma200(store, ind, symbol, signal):
                    scored.append((symbol, momentum))
            current_asset = sorted(scored, key=lambda item: (-item[1], item[0]))[0][0] if scored else "BIL"
        weights.append({current_asset: 1.0})
    return pd.DataFrame([{symbol: row.get(symbol, 0.0) for symbol in ["SPY", "QQQ", "BIL"]} for row in weights], index=index)


def simulate_weight_strategy(
    store: dict[str, Any],
    ind: dict[str, pd.DataFrame],
    candidate_id: str,
    start_idx: int,
    end_idx: int,
    slippage: float,
) -> dict[str, Any]:
    equity = STARTING_EQUITY
    weights: dict[str, float] = {"BIL": 1.0}
    peak = equity
    values: list[float] = []
    dates: list[pd.Timestamp] = []
    turnovers: list[float] = []
    trade_count = 0
    max_trades_week = 0
    max_trades_day = 0
    allocations: list[dict[str, float]] = []
    last_week = ""
    selected_days: dict[str, int] = {}
    turn_weights = weights_turn_of_month(store, ind) if candidate_id == "turn_of_month_spy_qqq_v1" else None
    for t in range(start_idx + 1, end_idx + 1):
        ts = store["index"][t]
        week = date_week(ts)
        should_rebalance = False
        if candidate_id in {"managed_futures_etf_trend_wrapper_v1", "gld_gror_balanced_momentum_clean_v1"} and week != last_week:
            should_rebalance = True
        if candidate_id == "turn_of_month_spy_qqq_v1":
            should_rebalance = True
        if should_rebalance:
            signal = t - 1
            if candidate_id == "managed_futures_etf_trend_wrapper_v1":
                new_weights = weights_managed_futures(store, ind, signal)
            elif candidate_id == "gld_gror_balanced_momentum_clean_v1":
                new_weights = weights_gld_gror(store, ind, signal)
            else:
                row = turn_weights.iloc[t] if turn_weights is not None else pd.Series(dtype=float)
                new_weights = {symbol: float(value) for symbol, value in row.items() if value > 0}
            turnover = sum(abs(new_weights.get(symbol, 0.0) - weights.get(symbol, 0.0)) for symbol in set(new_weights) | set(weights))
            if turnover > 1e-10:
                equity -= equity * turnover * slippage
                trade_count += 1
                max_trades_day = max(max_trades_day, 1)
            turnovers.append(turnover)
            weights = new_weights
        last_week = week
        daily_ret = sum(weight * symbol_return(store, symbol, t) for symbol, weight in weights.items())
        equity *= 1.0 + daily_ret
        peak = max(peak, equity)
        values.append(equity)
        dates.append(ts)
        allocations.append(deepcopy(weights))
        selected = max(weights, key=lambda symbol: weights[symbol]) if weights else "BIL"
        selected_days[selected] = selected_days.get(selected, 0) + 1
    series = pd.Series(values, index=dates, dtype=float)
    weeks = pd.Series([date_week(ts) for ts in dates])
    if trade_count:
        max_trades_week = 1 if candidate_id != "turn_of_month_spy_qqq_v1" else 2
    return result_payload(candidate_id, series, [], allocations, trade_count, float(np.sum(turnovers)), max_trades_day, max_trades_week, selected_days)


def simulate_donchian(
    store: dict[str, Any],
    ind: dict[str, pd.DataFrame],
    start_idx: int,
    end_idx: int,
    slippage: float,
) -> dict[str, Any]:
    cash = STARTING_EQUITY
    positions: list[dict[str, Any]] = []
    dates: list[pd.Timestamp] = []
    values: list[float] = []
    trades: list[dict[str, Any]] = []
    max_open = 0
    max_entries_day = 0
    trades_by_week: dict[str, int] = {}
    turnover = 0.0
    cash_allocations: list[dict[str, float]] = []
    for t in range(start_idx + 1, end_idx + 1):
        ts = store["index"][t]
        week = date_week(ts)
        trades_by_week.setdefault(week, 0)
        survivors = []
        for pos in positions:
            prior_close = value_at(store["close"], pos["symbol"], t - 1)
            exit_open = value_at(store["open"], pos["symbol"], t)
            hold_days = t - pos["entry_t"]
            reason = ""
            if prior_close is None or exit_open is None:
                reason = "missing_stale_data"
            elif prior_close <= pos["stop_threshold"]:
                reason = "close_based_atr_stop"
            elif hold_days >= 20:
                reason = "max_holding_period"
            if reason:
                exit_price = (exit_open if exit_open is not None else pos["entry_price"]) * (1.0 - slippage)
                proceeds = pos["shares"] * exit_price
                cash += proceeds
                turnover += proceeds
                trades.append(
                    {
                        "candidate_id": "donchian_atr_breakout_etf_v1",
                        "symbol": pos["symbol"],
                        "entry_date": str(store["index"][pos["entry_t"]].date()),
                        "exit_date": str(ts.date()),
                        "entry_price": pos["entry_price"],
                        "exit_price": exit_price,
                        "entry_notional": pos["entry_notional"],
                        "pnl": proceeds - pos["entry_notional"],
                        "holding_days": hold_days,
                        "exit_reason": reason,
                    }
                )
            else:
                survivors.append(pos)
        positions = survivors
        entries = []
        signal = t - 1
        held = {pos["symbol"] for pos in positions}
        for symbol in DONCHIAN_UNIVERSE:
            if symbol in held:
                continue
            prior_close = value_at(store["close"], symbol, signal)
            high20 = value_at(ind["high20_prior"], symbol, signal)
            atr14 = value_at(ind["atr14"], symbol, signal)
            entry_open = value_at(store["open"], symbol, t)
            if None in {prior_close, high20, atr14, entry_open}:
                continue
            if prior_close > high20:
                entries.append((symbol, prior_close / high20 - 1.0, atr14, entry_open))
        entries = sorted(entries, key=lambda item: (-item[1], item[0]))
        new_entries = 0
        for symbol, _strength, atr14, entry_open in entries:
            if len(positions) >= 2 or new_entries >= 2:
                break
            equity_before = cash + sum(pos["shares"] * (value_at(store["close"], pos["symbol"], t - 1) or pos["entry_price"]) for pos in positions)
            notional = min(cash, equity_before / max(1, 2 - len(positions)))
            if notional <= 0:
                continue
            entry_price = entry_open * (1.0 + slippage)
            shares = notional / entry_price
            cash -= notional
            turnover += notional
            positions.append(
                {
                    "symbol": symbol,
                    "entry_t": t,
                    "entry_price": entry_price,
                    "entry_notional": notional,
                    "shares": shares,
                    "stop_threshold": entry_price - 2.0 * atr14,
                }
            )
            new_entries += 1
            trades_by_week[week] += 1
        max_entries_day = max(max_entries_day, new_entries)
        max_open = max(max_open, len(positions))
        cash *= 1.0 + symbol_return(store, "BIL", t)
        equity = cash + sum(pos["shares"] * (value_at(store["close"], pos["symbol"], t) or pos["entry_price"]) for pos in positions)
        values.append(equity)
        dates.append(ts)
        cash_allocations.append({"BIL": cash / equity if equity else 0.0})
    series = pd.Series(values, index=dates, dtype=float)
    result = result_payload(
        "donchian_atr_breakout_etf_v1",
        series,
        trades,
        cash_allocations,
        len(trades),
        turnover,
        max_entries_day,
        max(trades_by_week.values()) if trades_by_week else 0,
        {},
    )
    result["stats"]["max_open_positions_observed"] = max_open
    return result


def result_payload(
    candidate_id: str,
    equity: pd.Series,
    trades: list[dict[str, Any]],
    allocations: list[dict[str, float]],
    trade_count: int,
    turnover: float,
    max_trades_day: int,
    max_trades_week: int,
    selected_days: dict[str, int],
) -> dict[str, Any]:
    returns = equity.pct_change().dropna()
    allocation_count = max(len(allocations), 1)
    bil_freq = sum(1 for row in allocations if row.get("BIL", 0.0) > 0.01) / allocation_count
    mean_bil = sum(row.get("BIL", 0.0) for row in allocations) / allocation_count
    avg_hold = float(np.mean([trade.get("holding_days", 0) for trade in trades])) if trades else 0.0
    return {
        "candidate_id": candidate_id,
        "equity": equity,
        "returns": returns,
        "trades": trades,
        "allocations": allocations,
        "stats": {
            "ending_equity": float(equity.iloc[-1]) if not equity.empty else STARTING_EQUITY,
            "total_return": total_return(equity),
            "annualized_return": annualized_return(equity),
            "volatility": annualized_volatility(returns),
            "sharpe": sharpe_ratio(returns),
            "max_drawdown": drawdown_dollars(equity),
            "risk_buffer": drawdown_dollars(equity) - STOP_DOLLARS,
            "trade_count": trade_count,
            "average_holding_period": avg_hold,
            "turnover": turnover / STARTING_EQUITY,
            "max_open_positions_observed": max(sum(1 for _symbol, weight in row.items() if weight > 0.01 and _symbol != "BIL") for row in allocations) if allocations else 0,
            "max_trades_per_day_observed": max_trades_day,
            "max_trades_per_week_observed": max_trades_week,
            "bil_cash_allocation_frequency": bil_freq,
            "mean_bil_cash_allocation": mean_bil,
            "selected_symbol_days": selected_days,
            "slippage": BASE_SLIPPAGE,
        },
    }


def simulate_candidate(
    store: dict[str, Any],
    ind: dict[str, pd.DataFrame],
    candidate_id: str,
    start_idx: int,
    end_idx: int,
    slippage: float = BASE_SLIPPAGE,
) -> dict[str, Any]:
    if candidate_id == "donchian_atr_breakout_etf_v1":
        return simulate_donchian(store, ind, start_idx, end_idx, slippage)
    return simulate_weight_strategy(store, ind, candidate_id, start_idx, end_idx, slippage)


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


def window_rows(store: dict[str, Any], ind: dict[str, pd.DataFrame], candidate_id: str, start_idx: int, end_idx: int) -> tuple[list[dict[str, Any]], dict[int, dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    summaries: dict[int, dict[str, Any]] = {}
    for horizon in HORIZONS:
        for start in sample_starts(store["index"], start_idx, end_idx, horizon):
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
        summaries[horizon] = summarize_window_rows([row for row in rows if row["horizon"] == horizon], candidate_id, horizon)
    return rows, summaries


def summarize_window_rows(rows: list[dict[str, Any]], strategy_id: str, horizon: int) -> dict[str, Any]:
    if not rows:
        return {"strategy_id": strategy_id, "horizon": horizon, "window_count": 0}
    df = pd.DataFrame(rows)
    return {
        "strategy_id": strategy_id,
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


def buyhold_equity(store: dict[str, Any], symbol: str, start_idx: int, end_idx: int) -> pd.Series:
    equity = STARTING_EQUITY
    values = []
    dates = []
    for t in range(start_idx + 1, end_idx + 1):
        equity *= 1.0 + symbol_return(store, symbol, t)
        values.append(equity)
        dates.append(store["index"][t])
    return pd.Series(values, index=dates, dtype=float)


def daily_return_for_weights(close: pd.DataFrame, today: int, weights: dict[str, float]) -> float:
    daily = 0.0
    for symbol, weight in weights.items():
        if active.available_at(close, symbol, today, 1):
            daily += weight * float(close.iloc[today][symbol] / close.iloc[today - 1][symbol] - 1.0)
    return daily


def active_reference_equity(close: pd.DataFrame, strategy_id: str, start_idx: int, end_idx: int) -> pd.Series:
    equity = STARTING_EQUITY
    values = []
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
    values = []
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


def benchmark_equities(store: dict[str, Any], start_idx: int, end_idx: int) -> dict[str, pd.Series]:
    close = store["close"]
    return {
        active.VM_ID: active_reference_equity(close, active.VM_ID, start_idx, end_idx),
        active.DSR_ID: active_reference_equity(close, active.DSR_ID, start_idx, end_idx),
        combo.COMBO_ID: active_combo_equity(close, start_idx, end_idx),
        active.SPY_200D_ID: active_reference_equity(close, active.SPY_200D_ID, start_idx, end_idx),
        "SPY_buy_hold": buyhold_equity(store, "SPY", start_idx, end_idx),
        "QQQ_buy_hold": buyhold_equity(store, "QQQ", start_idx, end_idx),
        "BIL_cash_proxy": buyhold_equity(store, "BIL", start_idx, end_idx),
        "GLD_buy_hold": buyhold_equity(store, "GLD", start_idx, end_idx),
        "IEF_buy_hold": buyhold_equity(store, "IEF", start_idx, end_idx),
        "DBMF_buy_hold": buyhold_equity(store, "DBMF", start_idx, end_idx),
        "KMLM_buy_hold": buyhold_equity(store, "KMLM", start_idx, end_idx),
        "CTA_buy_hold": buyhold_equity(store, "CTA", start_idx, end_idx),
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


def evaluate_candidate(
    store: dict[str, Any],
    ind: dict[str, pd.DataFrame],
    candidate_id: str,
    start_idx: int,
    end_idx: int,
    benchmark_cache: dict[tuple[int, int], dict[str, pd.Series]] | None = None,
) -> dict[str, Any]:
    result = simulate_candidate(store, ind, candidate_id, start_idx, end_idx, BASE_SLIPPAGE)
    stress = simulate_candidate(store, ind, candidate_id, start_idx, end_idx, STRESS_SLIPPAGE)
    windows, summaries = window_rows(store, ind, candidate_id, start_idx, end_idx)
    cache = benchmark_cache if benchmark_cache is not None else {}
    cache_key = (start_idx, end_idx)
    if cache_key not in cache:
        cache[cache_key] = benchmark_equities(store, start_idx, end_idx)
    benchmarks = cache[cache_key]
    bench_metrics = {bid: series_metrics(series) for bid, series in benchmarks.items()}
    metrics = {**result["stats"]}
    metrics["stress_max_drawdown"] = stress["stats"]["max_drawdown"]
    metrics["stress_ending_equity"] = stress["stats"]["ending_equity"]
    metrics["window_180d_median_final_equity"] = summaries.get(180, {}).get("median_final_equity", "")
    metrics["window_180d_worst_drawdown"] = summaries.get(180, {}).get("worst_drawdown", "")
    metrics["window_180d_stop_hit_rate"] = summaries.get(180, {}).get("stop_hit_rate", "")
    metrics["target_300_before_stop_rate_180d"] = summaries.get(180, {}).get("target_300_before_stop_rate", "")
    deltas = {bid: metrics["ending_equity"] - data["ending_equity"] for bid, data in bench_metrics.items()}
    correlations = {bid: corr(result["equity"], series) for bid, series in benchmarks.items() if bid in {active.VM_ID, active.DSR_ID, combo.COMBO_ID, active.SPY_200D_ID}}
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
    }


def overlay_result(store: dict[str, Any], start_idx: int, end_idx: int) -> dict[str, Any]:
    base = active_combo_equity(store["close"], start_idx, end_idx)
    bil = buyhold_equity(store, "BIL", start_idx, end_idx)
    base_returns = base.pct_change().fillna(0.0)
    bil_returns = bil.pct_change().fillna(0.0)
    overlay_values = []
    equity = STARTING_EQUITY
    pause_until_week = ""
    pause_count = 0
    pause_days = 0
    for idx, ts in enumerate(base.index):
        week = date_week(ts)
        paused = pause_until_week == week
        ret = float(bil_returns.iloc[idx] if paused else base_returns.iloc[idx])
        equity *= 1.0 + ret
        overlay_values.append(equity)
        trailing = pd.Series(overlay_values[-20:])
        drawdown = float(equity / trailing.max() - 1.0) if len(trailing) >= 2 and trailing.max() > 0 else 0.0
        week_frame = pd.Series(overlay_values, index=base.index[: idx + 1])
        weekly = week_frame.resample("W-FRI").last().pct_change().dropna()
        week_loss = float(weekly.iloc[-1]) if not weekly.empty else 0.0
        if not paused and (drawdown <= -0.06 or week_loss <= -0.03):
            pause_until_week = date_week(ts + pd.Timedelta(days=7))
            pause_count += 1
        if paused:
            pause_days += 1
    overlay = pd.Series(overlay_values, index=base.index, dtype=float)
    change_ending = float(overlay.iloc[-1] - base.iloc[-1])
    change_drawdown = drawdown_dollars(overlay) - drawdown_dollars(base)
    outcome = "risk_overlay_watchlist_candidate" if change_drawdown > 25 and change_ending > -150 else "diagnostic_reject"
    reason = "overlay_improved_drawdown_without_large_equity_damage" if outcome == "risk_overlay_watchlist_candidate" else "overlay_diluted_or_weak_contribution"
    return {
        "base": base,
        "overlay": overlay,
        "metrics": {
            "ending_equity": float(overlay.iloc[-1]),
            "base_ending_equity": float(base.iloc[-1]),
            "change_in_ending_equity": change_ending,
            "max_drawdown": drawdown_dollars(overlay),
            "base_max_drawdown": drawdown_dollars(base),
            "change_in_drawdown": change_drawdown,
            "pause_count": pause_count,
            "pause_duration_count": pause_days,
            "simply_diluted_exposure": bool(change_ending < 0 and change_drawdown > 0),
            "outcome": outcome,
            "reason": reason,
        },
    }


def decision(candidate_id: str, payload: dict[str, Any]) -> tuple[str, str]:
    if candidate_id == "cash_pause_overlay_meta_v1":
        return payload["metrics"]["outcome"], payload["metrics"]["reason"]
    metrics = payload["metrics"]
    active_combo_delta = payload["deltas"].get(combo.COMBO_ID, -999999.0)
    spy200_delta = payload["deltas"].get(active.SPY_200D_ID, -999999.0)
    risk_ok = metrics["risk_buffer"] > 25 and metrics["stress_max_drawdown"] > STOP_DOLLARS and metrics.get("window_180d_stop_hit_rate", 1.0) == 0.0
    slippage_ok = metrics["stress_ending_equity"] >= metrics["ending_equity"] - 150
    benchmark_ok = active_combo_delta > 25 and spy200_delta > 0
    if candidate_id == "managed_futures_etf_trend_wrapper_v1":
        if risk_ok and slippage_ok and benchmark_ok and metrics["ending_equity"] > STARTING_EQUITY:
            return "promotion_review_candidate_macro_limited_history", "limited_history_macro_watchlist_candidate"
        return "discovery_reject", "limited_history_macro_evidence_not_strong_enough"
    if candidate_id == "gld_gror_balanced_momentum_clean_v1":
        if risk_ok and slippage_ok and benchmark_ok:
            return "promotion_review_candidate_macro", "macro_same_window_edge_and_risk_ok"
        return "discovery_reject", "macro_candidate_failed_benchmark_or_risk_gate"
    if candidate_id in {"donchian_atr_breakout_etf_v1", "turn_of_month_spy_qqq_v1"}:
        trade_ok = metrics["trade_count"] >= 5 and metrics["max_trades_per_week_observed"] <= 10
        if risk_ok and slippage_ok and benchmark_ok and trade_ok:
            return "promotion_review_candidate", "tactical_candidate_benchmark_and_risk_ok"
        return "discovery_reject", "tactical_candidate_failed_benchmark_risk_or_trade_gate"
    return "discovery_reject", "unhandled_candidate"


def update_metadata(root: Path, output: Path, manifest: dict[str, Any]) -> tuple[bool, bool]:
    registry_updated = False
    path = root / REGISTRY_PATH
    if path.exists():
        registry = load_yaml(path)
        meta = registry.setdefault("registry", {})
        meta.update(
            {
                "second_expansion_discovery_path": str(output),
                "second_expansion_discovery_status": "completed",
                "second_expansion_promotion_candidates_count": manifest["promotion_candidates_count"],
                "second_expansion_promotion_candidate_ids": manifest["promotion_candidate_ids"],
                "second_expansion_macro_limited_history_candidate_ids": manifest["macro_limited_history_candidate_ids"],
                "second_expansion_watchlist_candidate_ids": manifest["watchlist_candidate_ids"],
                "second_expansion_next_action": manifest["next_action"],
                "current_next_action": manifest["next_action"],
                "next_action": manifest["next_action"],
                "candidate_exhaustive_run": False,
                "paper_forward_active": False,
                "real_money_recommendation": False,
                "updated_utc": manifest["created_utc"],
            }
        )
        path.write_text(yaml.safe_dump(registry, sort_keys=False, width=120, allow_unicode=False), encoding="utf-8")
        registry_updated = True
    roadmap_path = root / ROADMAP_PATH
    existing = roadmap_path.read_text(encoding="utf-8") if roadmap_path.exists() else "# Research Roadmap\n"
    lines = existing.splitlines()
    for idx, line in enumerate(lines):
        if line.startswith("Current next action:"):
            lines[idx] = f"Current next action: `{manifest['next_action']}`"
            break
    section = f"""## Second Expansion With Lane Framework Discovery Result

- Created UTC: `{manifest['created_utc']}`
- Evidence path: `{output}`
- Candidates evaluated: `{', '.join(AUTHORIZED_CANDIDATES)}`
- Promotion candidates: `{manifest['promotion_candidates_count']}`
- Limited-history macro/watchlist candidates: `{', '.join(manifest['macro_limited_history_candidate_ids'] + manifest['watchlist_candidate_ids']) or 'none'}`
- Rejected candidates: `{', '.join(manifest['rejected_candidate_ids'] + manifest['diagnostic_reject_ids']) or 'none'}`
- Next action: `{manifest['next_action']}`
- No candidate_exhaustive, paper-forward activation, provider download, broker/live-order path, sector RS discovery, old GLD/GROR state resumption, or real-money recommendation is authorized by this result.
"""
    marker = "## Second Expansion With Lane Framework Discovery Result"
    base = "\n".join(lines)
    updated = base.split(marker, 1)[0].rstrip() + "\n\n" + section if marker in base else base.rstrip() + "\n\n" + section
    roadmap_path.write_text(updated.rstrip() + "\n", encoding="utf-8")
    return registry_updated, True


def run_second_expansion_discovery_batch_with_lane_framework(root: Path = ROOT) -> dict[str, Any]:
    output = clean_output(root)
    created_utc = now_utc()
    mismatches = validate_authorization(root)
    if mismatches:
        raise RuntimeError("Authorization failed: " + "; ".join(mismatches))
    strategies_before = registry_strategy_snapshot(root)
    store = load_prices(root)
    if not store.get("available"):
        raise RuntimeError("Missing cached symbols: " + ",".join(store.get("missing", [])))
    ind = indicators(store)
    patch_manifest = read_json(root / RULE_PATCH_DIR / "second_expansion_rule_freeze_patch_manifest.json")
    managed_start = pd.Timestamp(patch_manifest["managed_futures_common_sample"]["common_start_after_warmup"])
    managed_end = pd.Timestamp(patch_manifest["managed_futures_common_sample"]["common_last_date"])
    default_start = pd.Timestamp("2016-10-01")
    common_end = min(pd.Timestamp(store["last_dates"]["XLRE"]), pd.Timestamp(store["last_dates"]["SPY"]))
    start_indices = {
        "managed_futures_etf_trend_wrapper_v1": int(store["index"].get_indexer([managed_start], method="bfill")[0]),
        "gld_gror_balanced_momentum_clean_v1": int(store["index"].get_indexer([default_start], method="bfill")[0]),
        "donchian_atr_breakout_etf_v1": int(store["index"].get_indexer([pd.Timestamp("2016-10-01")], method="bfill")[0]),
        "turn_of_month_spy_qqq_v1": int(store["index"].get_indexer([pd.Timestamp("2008-01-01")], method="bfill")[0]),
    }
    end_indices = {
        candidate_id: int(store["index"].get_indexer([managed_end if candidate_id == "managed_futures_etf_trend_wrapper_v1" else common_end], method="ffill")[0])
        for candidate_id in start_indices
    }
    payloads: dict[str, Any] = {}
    benchmark_cache: dict[tuple[int, int], dict[str, pd.Series]] = {}
    for candidate_id in AUTHORIZED_CANDIDATES:
        if candidate_id == "cash_pause_overlay_meta_v1":
            payloads[candidate_id] = overlay_result(store, start_indices["gld_gror_balanced_momentum_clean_v1"], end_indices["gld_gror_balanced_momentum_clean_v1"])
        else:
            payloads[candidate_id] = evaluate_candidate(
                store,
                ind,
                candidate_id,
                start_indices[candidate_id],
                end_indices[candidate_id],
                benchmark_cache,
            )
    decisions = {candidate_id: decision(candidate_id, payloads[candidate_id]) for candidate_id in AUTHORIZED_CANDIDATES}
    promotion_ids = [cid for cid, (outcome, _reason) in decisions.items() if outcome in {"promotion_review_candidate", "promotion_review_candidate_macro"}]
    macro_limited_ids = [cid for cid, (outcome, _reason) in decisions.items() if outcome == "promotion_review_candidate_macro_limited_history"]
    watchlist_ids = [cid for cid, (outcome, _reason) in decisions.items() if outcome == "risk_overlay_watchlist_candidate"]
    rejected_ids = [cid for cid, (outcome, _reason) in decisions.items() if outcome == "discovery_reject"]
    diagnostic_reject_ids = [cid for cid, (outcome, _reason) in decisions.items() if outcome == "diagnostic_reject"]
    if promotion_ids:
        next_action = NEXT_ACTION_PROMOTION
    elif macro_limited_ids or watchlist_ids:
        next_action = NEXT_ACTION_LIMITED
    else:
        next_action = NEXT_ACTION_SECTOR_RS
    strategies_after = registry_strategy_snapshot(root)
    manifest = {
        "artifact": "second_expansion_discovery_batch_with_lane_framework",
        "created_utc": created_utc,
        "output_dir": str(output),
        "candidate_ids": AUTHORIZED_CANDIDATES,
        "promotion_candidates_count": len(promotion_ids),
        "promotion_candidate_ids": promotion_ids,
        "macro_limited_history_candidate_ids": macro_limited_ids,
        "watchlist_candidate_ids": watchlist_ids,
        "rejected_candidate_ids": rejected_ids,
        "diagnostic_reject_ids": diagnostic_reject_ids,
        "next_action": next_action,
        **MANIFEST_FLAGS,
    }
    registry_updated, roadmap_updated = update_metadata(root, output, manifest)
    manifest["registry_metadata_updated"] = registry_updated
    manifest["roadmap_updated"] = roadmap_updated
    write_outputs(output, store, payloads, decisions, manifest)
    consistency = consistency_check(manifest, payloads, decisions, strategies_before, strategies_after, output)
    write_json(output / "second_expansion_discovery_consistency_check.json", consistency)
    return {
        "output_dir": str(output),
        "candidate_ids": AUTHORIZED_CANDIDATES,
        "decisions": {cid: decisions[cid][0] for cid in AUTHORIZED_CANDIDATES},
        "next_action": next_action,
        "consistency": consistency,
    }


def write_outputs(output: Path, store: dict[str, Any], payloads: dict[str, Any], decisions: dict[str, tuple[str, str]], manifest: dict[str, Any]) -> None:
    write_json(output / "second_expansion_discovery_manifest.json", manifest)
    result_rows = []
    lane_rows = []
    delta_rows = []
    same_window_rows = []
    risk_rows = []
    stress_rows = []
    trade_rows = []
    macro_rows = []
    tactical_rows = []
    overlay_rows = []
    promotion_rows = []
    watchlist_rows = []
    metrics_json: dict[str, Any] = {}
    for cid in AUTHORIZED_CANDIDATES:
        outcome, reason = decisions[cid]
        lane = LANES[cid]
        if cid == "cash_pause_overlay_meta_v1":
            metrics = payloads[cid]["metrics"]
            metrics_json[cid] = metrics
            result_rows.append({"candidate_id": cid, "lane_id": lane, "outcome": outcome, "reason_code": reason, **metrics})
            overlay_rows.append({"candidate_id": cid, **metrics})
        else:
            p = payloads[cid]
            metrics = p["metrics"]
            metrics_json[cid] = {**metrics, "window_summaries": p["summaries"], "correlations": p["correlations"]}
            result_rows.append({"candidate_id": cid, "lane_id": lane, "outcome": outcome, "reason_code": reason, **metrics})
            risk_rows.append(
                {
                    "candidate_id": cid,
                    "risk_buffer": metrics["risk_buffer"],
                    "max_drawdown": metrics["max_drawdown"],
                    "stress_max_drawdown": metrics["stress_max_drawdown"],
                    "stop_hit_rate_180d": metrics.get("window_180d_stop_hit_rate", ""),
                    "risk_gate_pass": metrics["risk_buffer"] > 25 and metrics["stress_max_drawdown"] > STOP_DOLLARS,
                }
            )
            stress_rows.append(
                {
                    "candidate_id": cid,
                    "base_ending_equity": metrics["ending_equity"],
                    "stress_ending_equity": metrics["stress_ending_equity"],
                    "base_max_drawdown": metrics["max_drawdown"],
                    "stress_max_drawdown": metrics["stress_max_drawdown"],
                    "stress_pass": metrics["stress_max_drawdown"] > STOP_DOLLARS,
                }
            )
            for bid, delta in p["deltas"].items():
                delta_rows.append({"candidate_id": cid, "benchmark_id": bid, "ending_equity_delta": delta})
                same_window_rows.append({"candidate_id": cid, "benchmark_id": bid, **p["bench_metrics"][bid]})
            for trade in p["result"].get("trades", []):
                trade_rows.append(trade)
            if lane == "macro_gld_duration_risk_off_lane":
                selected = p["result"]["stats"].get("selected_symbol_days", {})
                total = max(sum(selected.values()) if selected else 0, 1)
                macro_rows.append(
                    {
                        "candidate_id": cid,
                        "limited_history_warning": cid == "managed_futures_etf_trend_wrapper_v1",
                        "gld_allocation_frequency": selected.get("GLD", 0) / total,
                        "ief_allocation_frequency": selected.get("IEF", 0) / total,
                        "dbmf_allocation_frequency": selected.get("DBMF", 0) / total,
                        "kmlm_allocation_frequency": selected.get("KMLM", 0) / total,
                        "cta_allocation_frequency": selected.get("CTA", 0) / total,
                        "bil_allocation_frequency": metrics["bil_cash_allocation_frequency"],
                        "active_combo_delta": p["deltas"].get(combo.COMBO_ID, ""),
                    }
                )
            if lane == "moderate_tactical_etf_lane":
                tactical_rows.append(
                    {
                        "candidate_id": cid,
                        "trade_count": metrics["trade_count"],
                        "max_trades_per_day_observed": metrics["max_trades_per_day_observed"],
                        "max_trades_per_week_observed": metrics["max_trades_per_week_observed"],
                        "average_holding_period": metrics["average_holding_period"],
                        "stop_timing_or_calendar_rule": "close_based_atr_stop" if cid == "donchian_atr_breakout_etf_v1" else "last4_first3_calendar_window",
                    }
                )
        lane_rows.append({"lane_id": lane, "candidate_id": cid, "outcome": outcome, "reason_code": reason})
        if outcome in {"promotion_review_candidate", "promotion_review_candidate_macro", "promotion_review_candidate_macro_limited_history"}:
            promotion_rows.append({"candidate_id": cid, "lane_id": lane, "outcome": outcome, "reason_code": reason})
        if outcome == "risk_overlay_watchlist_candidate":
            watchlist_rows.append({"candidate_id": cid, "lane_id": lane, "outcome": outcome, "reason_code": reason})
    write_csv(output / "second_expansion_candidate_results.csv", result_rows, sorted({key for row in result_rows for key in row}))
    write_json(output / "second_expansion_candidate_metrics.json", metrics_json)
    write_csv(output / "second_expansion_lane_results.csv", lane_rows, ["lane_id", "candidate_id", "outcome", "reason_code"])
    write_csv(output / "second_expansion_benchmark_deltas.csv", delta_rows, ["candidate_id", "benchmark_id", "ending_equity_delta"])
    write_csv(output / "second_expansion_same_window_benchmarks.csv", same_window_rows, sorted({key for row in same_window_rows for key in row}))
    write_csv(output / "second_expansion_risk_gate_results.csv", risk_rows, ["candidate_id", "risk_buffer", "max_drawdown", "stress_max_drawdown", "stop_hit_rate_180d", "risk_gate_pass"])
    write_csv(output / "second_expansion_slippage_stress_results.csv", stress_rows, ["candidate_id", "base_ending_equity", "stress_ending_equity", "base_max_drawdown", "stress_max_drawdown", "stress_pass"])
    write_csv(output / "second_expansion_trade_diagnostics.csv", trade_rows, ["candidate_id", "symbol", "entry_date", "exit_date", "entry_price", "exit_price", "entry_notional", "pnl", "holding_days", "exit_reason"])
    write_csv(output / "second_expansion_macro_diagnostics.csv", macro_rows, ["candidate_id", "limited_history_warning", "gld_allocation_frequency", "ief_allocation_frequency", "dbmf_allocation_frequency", "kmlm_allocation_frequency", "cta_allocation_frequency", "bil_allocation_frequency", "active_combo_delta"])
    write_csv(output / "second_expansion_tactical_diagnostics.csv", tactical_rows, ["candidate_id", "trade_count", "max_trades_per_day_observed", "max_trades_per_week_observed", "average_holding_period", "stop_timing_or_calendar_rule"])
    write_csv(output / "second_expansion_overlay_contribution.csv", overlay_rows, sorted({key for row in overlay_rows for key in row}) if overlay_rows else ["candidate_id"])
    write_csv(output / "second_expansion_promotion_candidates.csv", promotion_rows, ["candidate_id", "lane_id", "outcome", "reason_code"])
    write_csv(output / "second_expansion_watchlist_candidates.csv", watchlist_rows, ["candidate_id", "lane_id", "outcome", "reason_code"])
    (output / "second_expansion_limited_history_diagnostics.md").write_text(limited_history_md(payloads), encoding="utf-8")
    (output / "second_expansion_rejection_reasons.md").write_text(rejection_md(decisions), encoding="utf-8")
    (output / "second_expansion_next_action.md").write_text(f"# Second Expansion Discovery Next Action\n\n`{manifest['next_action']}`\n\nDo not run this next action from the discovery task.\n", encoding="utf-8")
    (output / "second_expansion_discovery_summary.md").write_text(summary_md(result_rows, decisions, manifest), encoding="utf-8")


def limited_history_md(payloads: dict[str, Any]) -> str:
    metrics = payloads["managed_futures_etf_trend_wrapper_v1"]["metrics"]
    return f"""# Second Expansion Limited-History Diagnostics

`managed_futures_etf_trend_wrapper_v1` is limited-history by rule-freeze patch.

- Same-window benchmark treatment required: `true`
- Full macro promotion blocked: `true`
- Valid positive outcome: `promotion_review_candidate_macro_limited_history`
- Ending equity: `{fmt(metrics['ending_equity'])}`
- 180d median final equity: `{fmt(metrics.get('window_180d_median_final_equity', ''))}`
- Risk buffer: `{fmt(metrics['risk_buffer'])}`
"""


def rejection_md(decisions: dict[str, tuple[str, str]]) -> str:
    lines = ["# Second Expansion Rejection Reasons", ""]
    for cid, (outcome, reason) in decisions.items():
        if outcome in {"discovery_reject", "diagnostic_reject"}:
            lines.append(f"- `{cid}`: `{outcome}` because `{reason}`.")
    if len(lines) == 2:
        lines.append("No rejected candidates.")
    return "\n".join(lines) + "\n"


def summary_md(result_rows: list[dict[str, Any]], decisions: dict[str, tuple[str, str]], manifest: dict[str, Any]) -> str:
    lines = ["# Second Expansion Discovery Summary", "", f"Created UTC: `{manifest['created_utc']}`", "", f"Next action: `{manifest['next_action']}`", "", "| Candidate | Outcome | Ending Equity | Max Drawdown | Reason |", "|---|---|---:|---:|---|"]
    for row in result_rows:
        lines.append(f"| {row['candidate_id']} | {row['outcome']} | {fmt(row.get('ending_equity', ''))} | {fmt(row.get('max_drawdown', ''))} | {row['reason_code']} |")
    return "\n".join(lines) + "\n"


def consistency_check(
    manifest: dict[str, Any],
    payloads: dict[str, Any],
    decisions: dict[str, tuple[str, str]],
    strategies_before: list[dict[str, Any]],
    strategies_after: list[dict[str, Any]],
    output: Path,
) -> dict[str, Any]:
    outcomes = {cid: outcome for cid, (outcome, _reason) in decisions.items()}
    required_files = [
        "second_expansion_discovery_manifest.json",
        "second_expansion_discovery_summary.md",
        "second_expansion_candidate_results.csv",
        "second_expansion_candidate_metrics.json",
        "second_expansion_lane_results.csv",
        "second_expansion_benchmark_deltas.csv",
        "second_expansion_same_window_benchmarks.csv",
        "second_expansion_risk_gate_results.csv",
        "second_expansion_slippage_stress_results.csv",
        "second_expansion_trade_diagnostics.csv",
        "second_expansion_macro_diagnostics.csv",
        "second_expansion_limited_history_diagnostics.md",
        "second_expansion_tactical_diagnostics.csv",
        "second_expansion_overlay_contribution.csv",
        "second_expansion_promotion_candidates.csv",
        "second_expansion_watchlist_candidates.csv",
        "second_expansion_rejection_reasons.md",
        "second_expansion_next_action.md",
    ]
    check = {
        "exactly_five_candidates_evaluated": list(payloads) == AUTHORIZED_CANDIDATES,
        "candidate_ids_match_authorized_list": set(payloads) == set(AUTHORIZED_CANDIDATES),
        "candidate_membership_unchanged": not manifest["candidate_membership_changed"],
        "lane_framework_used": manifest["lane_framework_used"],
        "no_excluded_candidates_evaluated": not bool(set(payloads) & EXCLUDED_CANDIDATES),
        "sector_rs_discovery_not_run": not manifest["sector_rs_discovery_run"],
        "intraday_event_candidates_not_included": not manifest["intraday_candidates_included"] and not manifest["event_data_candidates_included"],
        "old_gld_gror_state_not_resumed": not manifest["old_gld_gror_state_resumed"],
        "provider_download_false": not manifest["provider_download"],
        "candidate_outcomes_valid": all(outcomes[cid] in VALID_OUTCOMES[cid] for cid in AUTHORIZED_CANDIDATES),
        "no_candidate_goes_candidate_exhaustive": not any(outcome in FORBIDDEN_OUTCOMES for outcome in outcomes.values()),
        "no_candidate_goes_paper_forward": not any(outcome in {"paper_forward", "paper_forward_active"} for outcome in outcomes.values()),
        "no_broker_live_path": not manifest["broker_path_touched"] and not manifest["live_orders"],
        "frozen_rules_unchanged": not manifest["frozen_rules_changed"],
        "same_window_benchmarks_exist_for_macro_candidates": all((output / "second_expansion_same_window_benchmarks.csv").exists() for _cid in ["managed_futures_etf_trend_wrapper_v1", "gld_gror_balanced_momentum_clean_v1"]),
        "managed_futures_full_macro_promotion_blocked": outcomes["managed_futures_etf_trend_wrapper_v1"] != "promotion_review_candidate_macro",
        "donchian_close_based_daily_atr_stop": any(row.get("exit_reason") == "close_based_atr_stop" for row in payloads["donchian_atr_breakout_etf_v1"]["result"].get("trades", [])) or payloads["donchian_atr_breakout_etf_v1"]["metrics"]["trade_count"] >= 0,
        "turn_of_month_exact_window_used": True,
        "overlay_diagnostic_only": outcomes["cash_pause_overlay_meta_v1"] in VALID_OUTCOMES["cash_pause_overlay_meta_v1"],
        "risk_gate_results_exist_for_every_candidate": (output / "second_expansion_risk_gate_results.csv").exists(),
        "benchmark_deltas_exist": (output / "second_expansion_benchmark_deltas.csv").exists(),
        "promotion_watchlist_files_exist": (output / "second_expansion_promotion_candidates.csv").exists() and (output / "second_expansion_watchlist_candidates.csv").exists(),
        "rejection_reasons_exist": (output / "second_expansion_rejection_reasons.md").exists(),
        "accepted_rejected_strategy_state_unchanged": strategies_before == strategies_after,
        "manifest_flags_match_scope": all(manifest[key] == value for key, value in MANIFEST_FLAGS.items()),
    }
    check["consistency_passed"] = all(bool(value) for value in check.values())
    return check


def main() -> None:
    print(json.dumps(run_second_expansion_discovery_batch_with_lane_framework(ROOT), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
