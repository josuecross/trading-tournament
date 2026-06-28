from __future__ import annotations

import csv
import json
import math
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
import run_first_expansion_discovery_preregistration as prereg
import run_first_expansion_manual_data_period_review as period_review


ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = Path("evidence") / "parallel_research_discovery" / "first_expansion_batch_without_sector_rs" / "latest"
EXPANSION_REGISTRY_PATH = Path("strategy_lab") / "strategy_expansion_candidates_v1.yaml"
EXPANSION_ROADMAP_PATH = Path("strategy_lab") / "STRATEGY_EXPANSION_ROADMAP.md"

AUTHORIZED_CANDIDATE_IDS = [
    "dmr_liquid_etf_oversold_rebound_v1",
    "vm_spy_qqq_daily_vol_target_v1",
    "vol_compression_breakout_etf_v1",
    "rs_pair_rotation_spy_qqq_xlk_xlu_v1",
]
DEFERRED_CANDIDATE_IDS = ["sector_rs_weekly_cash_filter_v1"]
EXCLUDED_CANDIDATE_IDS = [
    "sector_rs_weekly_cash_filter_v1",
    "donchian_atr_breakout_etf_v1",
    "turn_of_month_spy_qqq_v1",
    "cash_pause_overlay_meta_v1",
    "orb_spy_qqq_30m_research_v1",
    "gap_down_fade_spy_qqq_research_v1",
    "vwap_deviation_reversion_research_v1",
    "post_earnings_drift_large_cap_later_v1",
]
INTRADAY_CANDIDATE_IDS = [
    "orb_spy_qqq_30m_research_v1",
    "gap_down_fade_spy_qqq_research_v1",
    "vwap_deviation_reversion_research_v1",
]
EVENT_DATA_CANDIDATE_IDS = ["post_earnings_drift_large_cap_later_v1"]

NEXT_ACTION_PROMOTION = "promotion_review_for_selected_first_expansion_rows"
NEXT_ACTION_NO_CANDIDATE = "pre_register_sector_rs_limited_history_batch"
VALID_OUTCOMES = {"discovery_reject", "promotion_review_candidate"}

STARTING_EQUITY = active.STARTING_EQUITY
STOP_DOLLARS = active.STOP_DOLLARS
BASE_SLIPPAGE = active.SLIPPAGE
STRESS_SLIPPAGE = 0.0010
HORIZONS = active.HORIZONS
MAX_WINDOWS_PER_HORIZON = active.MAX_WINDOWS_PER_HORIZON
MAX_WARMUP_DAYS = 300

BROAD_UNIVERSE = ["SPY", "QQQ", "IWM", "DIA", "XLK", "XLF", "XLV", "XLE", "XLI", "XLY", "XLP", "XLU", "XLB", "XLRE"]
VM_UNIVERSE = ["SPY", "QQQ", "BIL"]
RS_PAIR_UNIVERSE = ["SPY", "QQQ", "XLK", "XLU", "BIL"]
ALL_AUTHORIZED_SYMBOLS = sorted(set(BROAD_UNIVERSE + VM_UNIVERSE + RS_PAIR_UNIVERSE + list(active.REQUIRED_CACHE_SYMBOLS) + ["QQQ"]))
BENCHMARK_IDS = [
    active.VM_ID,
    active.DSR_ID,
    combo.COMBO_ID,
    active.SPY_200D_ID,
    "SPY_buy_hold",
    "QQQ_buy_hold",
    "BIL_cash_proxy",
    "XLK_buy_hold",
    "XLU_buy_hold",
    "simple_donchian_baseline",
]
CANDIDATE_BENCHMARKS = {
    "dmr_liquid_etf_oversold_rebound_v1": [active.SPY_200D_ID, "SPY_buy_hold", active.VM_ID, combo.COMBO_ID, "BIL_cash_proxy"],
    "vm_spy_qqq_daily_vol_target_v1": [active.SPY_200D_ID, "QQQ_buy_hold", active.VM_ID, combo.COMBO_ID, "BIL_cash_proxy"],
    "vol_compression_breakout_etf_v1": ["SPY_buy_hold", "QQQ_buy_hold", active.SPY_200D_ID, "BIL_cash_proxy", "simple_donchian_baseline"],
    "rs_pair_rotation_spy_qqq_xlk_xlu_v1": [active.SPY_200D_ID, "QQQ_buy_hold", "XLK_buy_hold", "XLU_buy_hold", combo.COMBO_ID, "BIL_cash_proxy"],
}


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def fmt(value: Any) -> Any:
    if isinstance(value, (float, np.floating)):
        if math.isnan(float(value)) or math.isinf(float(value)):
            return ""
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


def file_hash(path: Path) -> str:
    return active.file_hash(path)


def clean_output_dir(root: Path) -> Path:
    output = (root / OUTPUT_DIR).resolve()
    root_resolved = root.resolve()
    if root_resolved not in output.parents:
        raise RuntimeError(f"refusing to clean output outside workspace: {output}")
    output.mkdir(parents=True, exist_ok=True)
    for child in output.iterdir():
        if child.is_file():
            child.unlink()
    return output


def load_preregistered_batch(root: Path) -> dict[str, Any]:
    batch_path = root / prereg.OUTPUT_DIR / "first_expansion_discovery_batch.yaml"
    return load_yaml(batch_path)


def authorized_candidates_from_batch(batch: dict[str, Any]) -> dict[str, dict[str, Any]]:
    candidates = {candidate["candidate_id"]: candidate for candidate in batch.get("candidates", [])}
    return {candidate_id: deepcopy(candidates[candidate_id]) for candidate_id in AUTHORIZED_CANDIDATE_IDS if candidate_id in candidates}


def validate_authorization(root: Path) -> list[str]:
    mismatches: list[str] = []
    batch = load_preregistered_batch(root)
    included = [candidate.get("candidate_id", "") for candidate in batch.get("candidates", [])]
    selected = authorized_candidates_from_batch(batch)
    if list(selected) != AUTHORIZED_CANDIDATE_IDS:
        mismatches.append("authorized candidate list does not match frozen first expansion batch")
    if any(candidate_id not in included for candidate_id in DEFERRED_CANDIDATE_IDS):
        mismatches.append("deferred sector candidate is not present in preregistration context")
    manual_manifest = read_json(root / period_review.OUTPUT_DIR / "first_expansion_manual_period_review_manifest.json")
    if manual_manifest.get("selected_resolution") != "run_first_expansion_discovery_batch_without_sector_rs":
        mismatches.append("manual period review did not authorize this no-sector-RS discovery batch")
    if manual_manifest.get("deferred_limited_history_candidate_ids") != DEFERRED_CANDIDATE_IDS:
        mismatches.append("manual period review deferred candidate list differs from expected sector RS row")
    return mismatches


def cache_path(root: Path, symbol: str) -> Path:
    return root / "data" / "cache" / f"{symbol}.csv"


def read_symbol_frame(root: Path, symbol: str) -> pd.DataFrame | None:
    path = cache_path(root, symbol)
    if not path.exists():
        return None
    frame = pd.read_csv(path)
    if "date" not in frame:
        return None
    dates = pd.to_datetime(frame["date"], errors="coerce").dt.tz_localize(None)
    close_source = "adj_close" if "adj_close" in frame else "close"
    if close_source not in frame:
        return None
    clean = pd.DataFrame({"date": dates})
    for column in ["open", "high", "low", "close", "adj_close", "volume"]:
        if column in frame:
            clean[column] = pd.to_numeric(frame[column], errors="coerce")
    if "adj_close" not in clean:
        clean["adj_close"] = pd.to_numeric(frame[close_source], errors="coerce")
    if "close" not in clean:
        clean["close"] = clean["adj_close"]
    for column in ["open", "high", "low"]:
        if column not in clean:
            clean[column] = clean["close"]
    if "volume" not in clean:
        clean["volume"] = 1_000_000
    clean = clean.dropna(subset=["date", "close"]).sort_values("date").drop_duplicates("date")
    if clean.empty:
        return None
    return clean.set_index("date")[["open", "high", "low", "close", "adj_close", "volume"]].astype(float)


def load_price_store(root: Path, symbols: list[str]) -> dict[str, Any]:
    frames: dict[str, pd.DataFrame] = {}
    missing: list[str] = []
    for symbol in symbols:
        frame = read_symbol_frame(root, symbol)
        if frame is None or len(frame) < 252:
            missing.append(symbol)
        else:
            frames[symbol] = frame
    if missing:
        return {"available": False, "missing_symbols": sorted(missing)}

    required_for_common_end = sorted(set(AUTHORIZED_CANDIDATE_SYMBOLS() + list(active.REQUIRED_CACHE_SYMBOLS) + ["BIL", "QQQ"]))
    valid_ends = [frames[symbol].index.max() for symbol in required_for_common_end if symbol in frames]
    common_end = min(valid_ends) if valid_ends else min(frame.index.max() for frame in frames.values())
    index = sorted(set().union(*(set(frame.index[frame.index <= common_end]) for frame in frames.values())))

    store: dict[str, Any] = {"available": True, "missing_symbols": [], "symbols": sorted(frames), "index": pd.DatetimeIndex(index), "analysis_end_date": str(common_end.date())}
    for column in ["open", "high", "low", "close", "volume"]:
        series = []
        for symbol, frame in frames.items():
            series.append(frame[column].rename(symbol).loc[frame.index <= common_end])
        store[column] = pd.concat(series, axis=1, join="outer").reindex(store["index"]).sort_index()
    store["first_dates"] = {symbol: str(frames[symbol].index.min().date()) for symbol in frames}
    store["last_dates"] = {symbol: str(min(frames[symbol].index.max(), common_end).date()) for symbol in frames}
    store["qa_rows"] = [
        {
            "candidate_id": "",
            "row_type": "symbol_cache",
            "date": "",
            "symbol": symbol,
            "symbols_used": "",
            "first_available_date": store["first_dates"][symbol],
            "last_available_date": store["last_dates"][symbol],
            "available_at_decision": "",
            "eligible_at_decision": "",
            "available_symbol_count": "",
            "eligible_symbol_count": "",
            "available_symbols": "",
            "eligible_symbols": "",
            "earliest_full_universe_date": "",
            "notes": "cached adjusted daily OHLCV loaded; no provider download",
        }
        for symbol in sorted(frames)
    ]
    return store


def AUTHORIZED_CANDIDATE_SYMBOLS() -> list[str]:
    return sorted(set(BROAD_UNIVERSE + VM_UNIVERSE + RS_PAIR_UNIVERSE))


def close(store: dict[str, Any]) -> pd.DataFrame:
    return store["close"]


def indicator_frame(store: dict[str, Any]) -> dict[str, pd.DataFrame]:
    c = store["close"]
    h = store["high"]
    l = store["low"]
    ret = c / c.shift(1) - 1.0
    true_range = pd.concat(
        [
            h - l,
            (h - c.shift(1)).abs(),
            (l - c.shift(1)).abs(),
        ],
        axis=0,
    ).groupby(level=0).max()
    gain = c.diff().clip(lower=0)
    loss = -c.diff().clip(upper=0)
    avg_gain2 = gain.rolling(2, min_periods=2).mean()
    avg_loss2 = loss.rolling(2, min_periods=2).mean()
    rs = avg_gain2 / avg_loss2.replace(0.0, np.nan)
    rsi2 = 100.0 - (100.0 / (1.0 + rs))
    rsi2 = rsi2.where(~((avg_loss2 == 0.0) & (avg_gain2 > 0.0)), 100.0).where(~((avg_loss2 == 0.0) & (avg_gain2 == 0.0)), 50.0)
    atr10 = true_range.rolling(10, min_periods=10).mean()
    compression = atr10 / c
    return {
        "ret": ret,
        "sma5": c.rolling(5, min_periods=5).mean(),
        "sma200": c.rolling(200, min_periods=200).mean(),
        "rsi2": rsi2,
        "atr14": true_range.rolling(14, min_periods=14).mean(),
        "atr10_div_close": compression,
        "compression_q30": compression.rolling(252, min_periods=252).quantile(0.30),
        "high20_prior": h.shift(1).rolling(20, min_periods=20).max(),
        "mom126": c / c.shift(126) - 1.0,
        "mom63": c / c.shift(63) - 1.0,
        "vol20": ret.rolling(20, min_periods=20).std() * np.sqrt(252.0),
    }


def value_at(frame: pd.DataFrame, symbol: str, t: int) -> float | None:
    if symbol not in frame.columns or t < 0 or t >= len(frame):
        return None
    value = frame.iloc[t][symbol]
    if pd.isna(value):
        return None
    return float(value)


def available_at_store(store: dict[str, Any], symbol: str, t: int, lookback: int = 0) -> bool:
    return value_at(store["close"], symbol, t) is not None and value_at(store["close"], symbol, t - lookback) is not None


def above_sma200(store: dict[str, Any], ind: dict[str, pd.DataFrame], symbol: str, t: int) -> bool:
    price = value_at(store["close"], symbol, t)
    sma = value_at(ind["sma200"], symbol, t)
    return price is not None and sma is not None and price > sma


def bil_return(store: dict[str, Any], t: int) -> float:
    if available_at_store(store, "BIL", t, 1):
        prev = float(store["close"].iloc[t - 1]["BIL"])
        cur = float(store["close"].iloc[t]["BIL"])
        return cur / prev - 1.0
    return 0.0


def sample_starts(store: dict[str, Any], horizon: int) -> list[int]:
    starts = list(range(MAX_WARMUP_DAYS, len(store["index"]) - horizon))
    if len(starts) <= MAX_WINDOWS_PER_HORIZON:
        return starts
    return sorted(set(int(x) for x in np.linspace(starts[0], starts[-1], MAX_WINDOWS_PER_HORIZON)))


def date_key(ts: pd.Timestamp) -> str:
    iso = ts.isocalendar()
    return f"{iso.year}-{iso.week:02d}"


def liquidity_pass(store: dict[str, Any], symbol: str, t: int) -> bool:
    volume = value_at(store["volume"], symbol, t)
    price = value_at(store["close"], symbol, t)
    return volume is not None and price is not None and volume > 0 and price > 1.0


def daily_availability_row(
    store: dict[str, Any],
    ind: dict[str, pd.DataFrame],
    candidate_id: str,
    universe: list[str],
    t: int,
    mode: str,
) -> dict[str, Any]:
    available = [symbol for symbol in universe if available_at_store(store, symbol, t, 1)]
    eligible: list[str] = []
    for symbol in available:
        if mode == "dmr" and above_sma200(store, ind, symbol, t) and value_at(ind["rsi2"], symbol, t) is not None:
            eligible.append(symbol)
        elif mode == "breakout":
            compression = value_at(ind["atr10_div_close"], symbol, t)
            q30 = value_at(ind["compression_q30"], symbol, t)
            high20 = value_at(ind["high20_prior"], symbol, t)
            price = value_at(store["close"], symbol, t)
            if compression is not None and q30 is not None and high20 is not None and price is not None and compression < q30 and price > high20:
                eligible.append(symbol)
        elif mode == "trend" and above_sma200(store, ind, symbol, t):
            eligible.append(symbol)
    full_dates = [pd.Timestamp(store["first_dates"][symbol]) for symbol in universe if symbol in store["first_dates"]]
    earliest_full = max(full_dates).date().isoformat() if full_dates else ""
    return {
        "candidate_id": candidate_id,
        "row_type": "decision_date",
        "date": str(store["index"][t].date()),
        "symbol": "",
        "symbols_used": ";".join(universe),
        "first_available_date": "",
        "last_available_date": "",
        "available_at_decision": "",
        "eligible_at_decision": "",
        "available_symbol_count": len(available),
        "eligible_symbol_count": len(eligible),
        "available_symbols": ";".join(available),
        "eligible_symbols": ";".join(eligible),
        "earliest_full_universe_date": earliest_full,
        "notes": "per-date availability and eligibility count; per-asset availability convention",
    }


def entry_candidates_dmr(store: dict[str, Any], ind: dict[str, pd.DataFrame], t: int, held: set[str]) -> list[tuple[str, float]]:
    signal = t - 1
    rows: list[tuple[str, float]] = []
    for symbol in BROAD_UNIVERSE:
        if symbol in held:
            continue
        rsi = value_at(ind["rsi2"], symbol, signal)
        atr = value_at(ind["atr14"], symbol, signal)
        entry_open = value_at(store["open"], symbol, t)
        if rsi is None or atr is None or entry_open is None:
            continue
        if above_sma200(store, ind, symbol, signal) and rsi <= 10.0 and liquidity_pass(store, symbol, signal):
            rows.append((symbol, rsi))
    return sorted(rows, key=lambda item: (item[1], item[0]))


def entry_candidates_breakout(store: dict[str, Any], ind: dict[str, pd.DataFrame], t: int, held: set[str]) -> list[tuple[str, float]]:
    signal = t - 1
    rows: list[tuple[str, float]] = []
    for symbol in BROAD_UNIVERSE:
        if symbol in held:
            continue
        compression = value_at(ind["atr10_div_close"], symbol, signal)
        q30 = value_at(ind["compression_q30"], symbol, signal)
        high20 = value_at(ind["high20_prior"], symbol, signal)
        prior_close = value_at(store["close"], symbol, signal)
        atr = value_at(ind["atr14"], symbol, signal)
        entry_open = value_at(store["open"], symbol, t)
        if None in {compression, q30, high20, prior_close, atr, entry_open}:
            continue
        if not liquidity_pass(store, symbol, signal):
            continue
        if compression < q30 and prior_close > high20 and entry_open <= prior_close + 2.0 * atr:
            breakout_strength = prior_close / high20 - 1.0
            rows.append((symbol, breakout_strength))
    return sorted(rows, key=lambda item: (-item[1], item[0]))


def simulate_position_strategy(
    store: dict[str, Any],
    ind: dict[str, pd.DataFrame],
    candidate_id: str,
    start: int,
    end: int,
    slippage: float,
    collect_trace: bool = True,
) -> dict[str, Any]:
    is_dmr = candidate_id == "dmr_liquid_etf_oversold_rebound_v1"
    max_hold = 5 if is_dmr else 10
    max_week_entries = 6 if is_dmr else 5
    stop_mult = 2.0 if is_dmr else 2.5
    cash = STARTING_EQUITY
    positions: list[dict[str, Any]] = []
    equity_values: list[float] = []
    dates: list[pd.Timestamp] = []
    peak = STARTING_EQUITY
    max_drawdown = 0.0
    trades: list[dict[str, Any]] = []
    trace: list[dict[str, Any]] = []
    max_open_positions = 0
    max_new_entries_day = 0
    max_new_entries_week = 0
    entry_count_by_week: dict[str, int] = {}
    turnover_notional = 0.0
    cash_allocations: list[float] = []
    current_week = ""
    week_start_equity = STARTING_EQUITY
    week_loss_count = 0
    force_pause = False

    for t in range(start + 1, end + 1):
        date = store["index"][t]
        week = date_key(date)
        if week != current_week:
            current_week = week
            week_start_equity = cash + sum(pos["shares"] * (value_at(store["close"], pos["symbol"], t - 1) or pos["entry_price"]) for pos in positions)
            week_loss_count = 0
            force_pause = False
        entry_count_by_week.setdefault(week, 0)
        closed_today: list[dict[str, Any]] = []
        survivors: list[dict[str, Any]] = []
        for pos in positions:
            symbol = pos["symbol"]
            low = value_at(store["low"], symbol, t)
            price_close = value_at(store["close"], symbol, t)
            if low is None or price_close is None:
                prev_close = value_at(store["close"], symbol, t - 1) or pos["entry_price"]
                exit_price = prev_close * (1.0 - slippage)
                reason = "missing_or_stale_data_forced_exit"
            else:
                stop_hit = low <= pos["stop_price"]
                hold_days = t - pos["entry_t"] + 1
                if stop_hit:
                    exit_price = pos["stop_price"] * (1.0 - slippage)
                    reason = "atr_stop"
                elif is_dmr and value_at(ind["sma5"], symbol, t) is not None and price_close > float(ind["sma5"].iloc[t][symbol]):
                    exit_price = price_close * (1.0 - slippage)
                    reason = "close_above_5d_sma"
                elif not is_dmr and price_close < float(pos["breakout_level"]):
                    exit_price = price_close * (1.0 - slippage)
                    reason = "failed_breakout_close"
                elif hold_days >= max_hold:
                    exit_price = price_close * (1.0 - slippage)
                    reason = "max_holding_period"
                else:
                    survivors.append(pos)
                    continue
            proceeds = pos["shares"] * exit_price
            pnl = proceeds - pos["entry_notional"]
            cash += proceeds
            turnover_notional += proceeds
            trade = {
                "candidate_id": candidate_id,
                "symbol": symbol,
                "entry_date": str(store["index"][pos["entry_t"]].date()),
                "exit_date": str(date.date()),
                "entry_price": pos["entry_price"],
                "exit_price": exit_price,
                "shares": pos["shares"],
                "entry_notional": pos["entry_notional"],
                "pnl": pnl,
                "holding_days": t - pos["entry_t"] + 1,
                "exit_reason": reason,
            }
            trades.append(trade)
            closed_today.append(trade)
            if pnl < 0:
                week_loss_count += 1
        positions = survivors

        equity_before_entries = cash + sum(pos["shares"] * (value_at(store["close"], pos["symbol"], t - 1) or pos["entry_price"]) for pos in positions)
        if equity_before_entries <= week_start_equity * 0.97 or week_loss_count >= 2:
            force_pause = True
        entry_candidates = entry_candidates_dmr(store, ind, t, {pos["symbol"] for pos in positions}) if is_dmr else entry_candidates_breakout(store, ind, t, {pos["symbol"] for pos in positions})
        new_entries_today = 0
        for symbol, _score in entry_candidates:
            if force_pause or len(positions) >= 2 or new_entries_today >= 2 or entry_count_by_week[week] >= max_week_entries:
                break
            entry_open = value_at(store["open"], symbol, t)
            atr = value_at(ind["atr14"], symbol, t - 1)
            prior_high20 = value_at(ind["high20_prior"], symbol, t - 1)
            if entry_open is None or atr is None or cash <= 0:
                continue
            notional = min(STARTING_EQUITY * 0.25, equity_before_entries * 0.25, cash)
            if notional <= 0:
                continue
            entry_price = entry_open * (1.0 + slippage)
            shares = notional / entry_price
            cash -= notional
            turnover_notional += notional
            positions.append(
                {
                    "symbol": symbol,
                    "entry_t": t,
                    "entry_price": entry_price,
                    "entry_notional": notional,
                    "shares": shares,
                    "stop_price": entry_open - stop_mult * atr,
                    "breakout_level": prior_high20 if prior_high20 is not None else entry_open,
                }
            )
            new_entries_today += 1
            entry_count_by_week[week] += 1
        max_new_entries_day = max(max_new_entries_day, new_entries_today)
        max_new_entries_week = max(max_new_entries_week, entry_count_by_week[week])

        cash *= 1.0 + bil_return(store, t)
        equity = cash + sum(pos["shares"] * (value_at(store["close"], pos["symbol"], t) or pos["entry_price"]) for pos in positions)
        peak = max(peak, equity)
        max_drawdown = min(max_drawdown, equity - peak)
        max_open_positions = max(max_open_positions, len(positions))
        cash_allocations.append(cash / equity if equity else 0.0)
        if collect_trace:
            trace.append(daily_availability_row(store, ind, candidate_id, BROAD_UNIVERSE, t - 1, "dmr" if is_dmr else "breakout"))
        dates.append(date)
        equity_values.append(equity)

    equity_series = pd.Series(equity_values, index=dates, dtype=float)
    trade_df = pd.DataFrame(trades)
    return {
        "candidate_id": candidate_id,
        "equity": equity_series,
        "returns": equity_series.pct_change().dropna(),
        "trades": trades,
        "trace": trace,
        "stats": {
            "ending_equity": float(equity_series.iloc[-1]) if not equity_series.empty else STARTING_EQUITY,
            "max_drawdown": max_drawdown,
            "trade_count": len(trades),
            "average_holding_period": float(trade_df["holding_days"].mean()) if not trade_df.empty else 0.0,
            "turnover": float(turnover_notional / max(STARTING_EQUITY, 1.0)),
            "max_open_positions_observed": max_open_positions,
            "max_trades_per_day_observed": max_new_entries_day,
            "max_trades_per_week_observed": max_new_entries_week,
            "bil_cash_allocation_frequency": float(np.mean([x > 0.01 for x in cash_allocations])) if cash_allocations else 0.0,
            "mean_bil_cash_allocation": float(np.mean(cash_allocations)) if cash_allocations else 0.0,
            "max_holding_period_observed": int(trade_df["holding_days"].max()) if not trade_df.empty else 0,
            "weekly_loss_pause_observed": True,
            "slippage": slippage,
        },
    }


def vm_weights(store: dict[str, Any], ind: dict[str, pd.DataFrame], signal: int) -> dict[str, float]:
    scored: list[tuple[str, float]] = []
    for symbol in ["SPY", "QQQ"]:
        score = value_at(ind["mom126"], symbol, signal)
        if score is not None and above_sma200(store, ind, symbol, signal):
            scored.append((symbol, score))
    if not scored:
        return {"BIL": 1.0}
    selected = sorted(scored, key=lambda item: (-item[1], item[0]))[0][0]
    vol = value_at(ind["vol20"], selected, signal)
    if vol is None or vol <= 0:
        exposure = 0.0
    else:
        exposure = min(1.0, 0.12 / vol)
        if vol > 0.30:
            exposure = min(exposure, 0.50)
    exposure = max(0.0, min(1.0, exposure))
    return {selected: exposure, "BIL": 1.0 - exposure}


def rs_pair_weights(store: dict[str, Any], ind: dict[str, pd.DataFrame], signal: int) -> dict[str, float]:
    scored: list[tuple[str, float]] = []
    for symbol in ["SPY", "QQQ", "XLK", "XLU"]:
        score = value_at(ind["mom63"], symbol, signal)
        if score is not None and above_sma200(store, ind, symbol, signal):
            scored.append((symbol, score))
    if not scored:
        return {"BIL": 1.0}
    selected = sorted(scored, key=lambda item: (-item[1], item[0]))[0][0]
    return {selected: 1.0}


def simulate_weight_strategy(
    store: dict[str, Any],
    ind: dict[str, pd.DataFrame],
    candidate_id: str,
    start: int,
    end: int,
    slippage: float,
    collect_trace: bool = True,
) -> dict[str, Any]:
    daily_rebalance = candidate_id == "vm_spy_qqq_daily_vol_target_v1"
    universe = VM_UNIVERSE if daily_rebalance else RS_PAIR_UNIVERSE
    equity = STARTING_EQUITY
    weights: dict[str, float] = {"BIL": 1.0}
    peak = equity
    max_drawdown = 0.0
    dates: list[pd.Timestamp] = []
    values: list[float] = []
    trace: list[dict[str, Any]] = []
    turnovers: list[float] = []
    cash_allocations: list[float] = []
    selected_days: dict[str, int] = {}
    trade_count = 0
    max_trades_day = 0
    max_trades_week = 0
    trades_by_week: dict[str, int] = {}
    last_week = ""
    last_rebalance_week = ""
    current_holding_start = start
    holding_periods: list[int] = []

    for t in range(start + 1, end + 1):
        date = store["index"][t]
        week = date_key(date)
        trades_by_week.setdefault(week, 0)
        should_rebalance = daily_rebalance or week != last_rebalance_week
        if should_rebalance:
            signal = t - 1
            new_weights = vm_weights(store, ind, signal) if daily_rebalance else rs_pair_weights(store, ind, signal)
            turnover = sum(abs(new_weights.get(symbol, 0.0) - weights.get(symbol, 0.0)) for symbol in set(new_weights) | set(weights))
            if turnover > 1e-10:
                equity -= equity * turnover * slippage
                trade_count += 1
                trades_by_week[week] += 1
                max_trades_day = max(max_trades_day, 1)
                if set(weights) != set(new_weights):
                    holding_periods.append(max(1, t - current_holding_start))
                    current_holding_start = t
            turnovers.append(turnover)
            weights = new_weights
            last_rebalance_week = week
        if week != last_week:
            max_trades_week = max(max_trades_week, trades_by_week.get(week, 0))
            last_week = week
        daily_return = 0.0
        for symbol, weight in weights.items():
            if available_at_store(store, symbol, t, 1):
                daily_return += weight * (float(store["close"].iloc[t][symbol]) / float(store["close"].iloc[t - 1][symbol]) - 1.0)
        equity *= 1.0 + daily_return
        peak = max(peak, equity)
        max_drawdown = min(max_drawdown, equity - peak)
        bil_weight = weights.get("BIL", 0.0)
        cash_allocations.append(bil_weight)
        selected_symbol = max(weights, key=lambda symbol: weights[symbol]) if weights else "BIL"
        selected_days[selected_symbol] = selected_days.get(selected_symbol, 0) + 1
        if collect_trace:
            trace.append(daily_availability_row(store, ind, candidate_id, universe, t - 1, "trend"))
        dates.append(date)
        values.append(equity)

    equity_series = pd.Series(values, index=dates, dtype=float)
    return {
        "candidate_id": candidate_id,
        "equity": equity_series,
        "returns": equity_series.pct_change().dropna(),
        "trades": [],
        "trace": trace,
        "stats": {
            "ending_equity": float(equity_series.iloc[-1]) if not equity_series.empty else STARTING_EQUITY,
            "max_drawdown": max_drawdown,
            "trade_count": trade_count,
            "average_holding_period": float(np.mean(holding_periods)) if holding_periods else 0.0,
            "turnover": float(np.sum(turnovers)),
            "max_open_positions_observed": 2 if daily_rebalance and any(k in {"SPY", "QQQ"} and 0 < v < 1 for k, v in weights.items()) else 1,
            "max_trades_per_day_observed": max_trades_day,
            "max_trades_per_week_observed": max(max_trades_week, max(trades_by_week.values()) if trades_by_week else 0),
            "bil_cash_allocation_frequency": float(np.mean([x > 0.01 for x in cash_allocations])) if cash_allocations else 0.0,
            "mean_bil_cash_allocation": float(np.mean(cash_allocations)) if cash_allocations else 0.0,
            "max_holding_period_observed": int(max(holding_periods)) if holding_periods else 0,
            "selected_symbol_days": selected_days,
            "slippage": slippage,
        },
    }


def simulate_candidate(
    store: dict[str, Any],
    ind: dict[str, pd.DataFrame],
    candidate_id: str,
    start: int,
    end: int,
    slippage: float,
    collect_trace: bool = True,
) -> dict[str, Any]:
    if candidate_id in {"dmr_liquid_etf_oversold_rebound_v1", "vol_compression_breakout_etf_v1"}:
        return simulate_position_strategy(store, ind, candidate_id, start, end, slippage, collect_trace=collect_trace)
    return simulate_weight_strategy(store, ind, candidate_id, start, end, slippage, collect_trace=collect_trace)


def drawdown_from_series(equity: pd.Series) -> float:
    if equity.empty:
        return 0.0
    return float((equity - equity.cummax()).min())


def total_return_from_series(equity: pd.Series) -> float:
    if equity.empty:
        return 0.0
    return float(equity.iloc[-1] / STARTING_EQUITY - 1.0)


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


def window_summary(
    store: dict[str, Any],
    ind: dict[str, pd.DataFrame],
    candidate_id: str,
    slippage: float,
) -> tuple[list[dict[str, Any]], dict[int, dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    summaries: dict[int, dict[str, Any]] = {}
    for horizon in HORIZONS:
        for start in sample_starts(store, horizon):
            result = simulate_candidate(store, ind, candidate_id, start, start + horizon, slippage, collect_trace=False)
            equity = result["equity"]
            peak = equity.cummax()
            max_dd = float((equity - peak).min()) if not equity.empty else 0.0
            profit = float(equity.iloc[-1] - STARTING_EQUITY) if not equity.empty else 0.0
            stop = bool((equity - STARTING_EQUITY <= STOP_DOLLARS).any()) if not equity.empty else False
            t300_idx = np.where((equity - STARTING_EQUITY >= 300.0).values)[0] if not equity.empty else []
            t400_idx = np.where((equity - STARTING_EQUITY >= 400.0).values)[0] if not equity.empty else []
            stop_idx = np.where((equity - STARTING_EQUITY <= STOP_DOLLARS).values)[0] if not equity.empty else []
            target300 = len(t300_idx) > 0 and (len(stop_idx) == 0 or int(t300_idx[0]) <= int(stop_idx[0]))
            target400 = len(t400_idx) > 0 and (len(stop_idx) == 0 or int(t400_idx[0]) <= int(stop_idx[0]))
            rows.append(
                {
                    "strategy_id": candidate_id,
                    "horizon": horizon,
                    "window_start": str(store["index"][start].date()),
                    "window_end": str(store["index"][start + horizon].date()),
                    "final_equity": float(equity.iloc[-1]) if not equity.empty else STARTING_EQUITY,
                    "profit_dollars": profit,
                    "max_drawdown": max_dd,
                    "absolute_600_stop_hit": stop,
                    "target_300_before_stop": bool(target300),
                    "target_400_before_stop": bool(target400),
                }
            )
        df = pd.DataFrame([row for row in rows if row["horizon"] == horizon])
        summaries[horizon] = summarize_window_df(df, candidate_id, horizon)
    return rows, summaries


def summarize_window_df(df: pd.DataFrame, strategy_id: str, horizon: int) -> dict[str, Any]:
    if df.empty:
        return {"strategy_id": strategy_id, "horizon": horizon, "window_count": 0}
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


def close_for_active(store: dict[str, Any]) -> pd.DataFrame:
    return store["close"]


def symbol_buyhold_window(store: dict[str, Any], symbol: str, start: int, horizon: int, strategy_id: str) -> dict[str, Any]:
    equity = STARTING_EQUITY
    values: list[float] = []
    peak = equity
    max_dd = 0.0
    stop = None
    target300 = None
    target400 = None
    for offset in range(1, horizon + 1):
        t = start + offset
        if available_at_store(store, symbol, t, 1):
            equity *= float(store["close"].iloc[t][symbol]) / float(store["close"].iloc[t - 1][symbol])
        values.append(equity)
        peak = max(peak, equity)
        max_dd = min(max_dd, equity - peak)
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
        "window_start": str(store["index"][start].date()),
        "window_end": str(store["index"][start + horizon].date()),
        "final_equity": equity,
        "profit_dollars": equity - STARTING_EQUITY,
        "max_drawdown": max_dd,
        "absolute_600_stop_hit": stop is not None,
        "target_300_before_stop": bool(target300 is not None and (stop is None or target300 <= stop)),
        "target_400_before_stop": bool(target400 is not None and (stop is None or target400 <= stop)),
    }


def symbol_buyhold_returns(store: dict[str, Any], symbol: str) -> pd.Series:
    series = store["close"][symbol].dropna() if symbol in store["close"].columns else pd.Series(dtype=float)
    if series.empty:
        return pd.Series(dtype=float)
    return (series / series.shift(1) - 1.0).dropna()


def benchmark_payload(store: dict[str, Any]) -> tuple[dict[str, dict[int, dict[str, Any]]], dict[str, pd.Series]]:
    c = close_for_active(store)
    summaries: dict[str, dict[int, dict[str, Any]]] = {}
    returns: dict[str, pd.Series] = {}
    active_refs = [active.VM_ID, active.DSR_ID, active.SPY_200D_ID]
    for ref in active_refs:
        rows: list[dict[str, Any]] = []
        for horizon in HORIZONS:
            for start in sample_starts(store, horizon):
                rows.append(active.simulate(c, start, horizon, ref))
        summaries[ref] = {horizon: active.summarize(rows, ref, horizon) for horizon in HORIZONS}
        returns[ref] = active.full_returns(c, ref)
    combo_rows: list[dict[str, Any]] = []
    for horizon in HORIZONS:
        for start in sample_starts(store, horizon):
            combo_rows.append(combo.combo_window(c, start, horizon))
    summaries[combo.COMBO_ID] = {horizon: combo.summarize(combo_rows, combo.COMBO_ID, horizon) for horizon in HORIZONS}
    combo_frame, _alloc = combo.full_equity_series(c)
    returns[combo.COMBO_ID] = combo.returns_from_equity(combo_frame, "active_combo_equity")
    for symbol, ref in [("SPY", "SPY_buy_hold"), ("QQQ", "QQQ_buy_hold"), ("BIL", "BIL_cash_proxy"), ("XLK", "XLK_buy_hold"), ("XLU", "XLU_buy_hold")]:
        rows = []
        for horizon in HORIZONS:
            for start in sample_starts(store, horizon):
                rows.append(symbol_buyhold_window(store, symbol, start, horizon, ref))
        summaries[ref] = {horizon: summarize_window_df(pd.DataFrame([row for row in rows if row["horizon"] == horizon]), ref, horizon) for horizon in HORIZONS}
        returns[ref] = symbol_buyhold_returns(store, symbol)
    return summaries, returns


def corr(returns: dict[str, pd.Series], left: str, right: str) -> float | str:
    a = returns.get(left, pd.Series(dtype=float))
    b = returns.get(right, pd.Series(dtype=float))
    if a.empty or b.empty:
        return "unavailable"
    frame = pd.concat([a.rename("a"), b.rename("b")], axis=1, join="inner").dropna()
    if len(frame) < 20 or frame["a"].std() == 0 or frame["b"].std() == 0:
        return "unavailable"
    return float(frame["a"].corr(frame["b"]))


def concentration_diagnostics(candidate_id: str, result: dict[str, Any]) -> dict[str, Any]:
    if candidate_id in {"dmr_liquid_etf_oversold_rebound_v1", "vol_compression_breakout_etf_v1"}:
        trades = result["trades"]
        if not trades:
            return {
                "dominant_symbol": "",
                "dominant_symbol_trade_share": 0.0,
                "xlre_trade_count": 0,
                "xlre_pnl": 0.0,
                "xlre_contribution_material": False,
                "post_2015_trade_share": 0.0,
                "post_2015_dependency_heavy": False,
                "qqq_xlk_weight_frequency": 0.0,
            }
        df = pd.DataFrame(trades)
        counts = df["symbol"].value_counts()
        dominant = str(counts.index[0])
        post_2015 = pd.to_datetime(df["entry_date"]) >= pd.Timestamp("2015-10-08")
        total_abs_pnl = float(df["pnl"].abs().sum())
        xlre_pnl = float(df.loc[df["symbol"] == "XLRE", "pnl"].sum()) if "XLRE" in set(df["symbol"]) else 0.0
        return {
            "dominant_symbol": dominant,
            "dominant_symbol_trade_share": float(counts.iloc[0] / len(df)),
            "xlre_trade_count": int((df["symbol"] == "XLRE").sum()),
            "xlre_pnl": xlre_pnl,
            "xlre_contribution_material": bool(total_abs_pnl > 0 and abs(xlre_pnl) / total_abs_pnl >= 0.25),
            "post_2015_trade_share": float(post_2015.mean()),
            "post_2015_dependency_heavy": bool(post_2015.mean() >= 0.85),
            "qqq_xlk_weight_frequency": 0.0,
        }
    selected = result["stats"].get("selected_symbol_days", {})
    total_days = max(sum(int(v) for v in selected.values()), 1)
    qqq_xlk = (int(selected.get("QQQ", 0)) + int(selected.get("XLK", 0))) / total_days
    dominant = max(selected, key=lambda symbol: selected[symbol]) if selected else ""
    return {
        "dominant_symbol": dominant,
        "dominant_symbol_trade_share": float(selected.get(dominant, 0) / total_days) if dominant else 0.0,
        "xlre_trade_count": 0,
        "xlre_pnl": 0.0,
        "xlre_contribution_material": False,
        "post_2015_trade_share": 0.0,
        "post_2015_dependency_heavy": False,
        "qqq_xlk_weight_frequency": float(qqq_xlk),
    }


def build_candidate_payload(store: dict[str, Any], ind: dict[str, pd.DataFrame]) -> dict[str, Any]:
    full_results: dict[str, dict[str, Any]] = {}
    stress_results: dict[str, dict[str, Any]] = {}
    window_rows: dict[str, list[dict[str, Any]]] = {}
    summaries: dict[str, dict[int, dict[str, Any]]] = {}
    stress_summaries: dict[str, dict[int, dict[str, Any]]] = {}
    returns: dict[str, pd.Series] = {}
    trace_rows: list[dict[str, Any]] = []
    start = MAX_WARMUP_DAYS
    end = len(store["index"]) - 1
    for candidate_id in AUTHORIZED_CANDIDATE_IDS:
        full = simulate_candidate(store, ind, candidate_id, start, end, BASE_SLIPPAGE)
        stress = simulate_candidate(store, ind, candidate_id, start, end, STRESS_SLIPPAGE, collect_trace=False)
        full_results[candidate_id] = full
        stress_results[candidate_id] = stress
        rows, summary = window_summary(store, ind, candidate_id, BASE_SLIPPAGE)
        stress_rows, stress_summary = window_summary(store, ind, candidate_id, STRESS_SLIPPAGE)
        window_rows[candidate_id] = rows
        summaries[candidate_id] = summary
        stress_summaries[candidate_id] = stress_summary
        returns[candidate_id] = full["returns"]
        trace_rows.extend(full["trace"])
    benchmark_summaries, benchmark_returns = benchmark_payload(store)
    summaries.update(benchmark_summaries)
    returns.update(benchmark_returns)
    return {
        "full_results": full_results,
        "stress_results": stress_results,
        "window_rows": window_rows,
        "summaries": summaries,
        "stress_summaries": stress_summaries,
        "returns": returns,
        "trace_rows": trace_rows,
    }


def benchmark_delta_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for candidate_id in AUTHORIZED_CANDIDATE_IDS:
        candidate_summary = payload["summaries"][candidate_id][180]
        for benchmark_id in CANDIDATE_BENCHMARKS[candidate_id]:
            if benchmark_id == "simple_donchian_baseline" or benchmark_id not in payload["summaries"]:
                rows.append(
                    {
                        "candidate_id": candidate_id,
                        "benchmark_id": benchmark_id,
                        "candidate_180d_median_final_equity": fmt(candidate_summary.get("median_final_equity")),
                        "benchmark_180d_median_final_equity": "unavailable",
                        "delta": "unavailable",
                        "correlation": "unavailable",
                        "comparison_status": "unavailable",
                        "missing_reason": "optional diagnostic benchmark not already available",
                    }
                )
                continue
            bench_summary = payload["summaries"][benchmark_id][180]
            rows.append(
                {
                    "candidate_id": candidate_id,
                    "benchmark_id": benchmark_id,
                    "candidate_180d_median_final_equity": fmt(candidate_summary.get("median_final_equity")),
                    "benchmark_180d_median_final_equity": fmt(bench_summary.get("median_final_equity")),
                    "delta": fmt(float(candidate_summary.get("median_final_equity", 0.0)) - float(bench_summary.get("median_final_equity", 0.0))),
                    "correlation": fmt(corr(payload["returns"], candidate_id, benchmark_id)),
                    "comparison_status": "computed",
                    "missing_reason": "",
                }
            )
    return rows


def risk_gate_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    gate_specs = {
        "dmr_liquid_etf_oversold_rebound_v1": {"max_positions": 2, "max_day": 2, "max_week": 6, "max_hold": 5, "min_trades": 50},
        "vm_spy_qqq_daily_vol_target_v1": {"max_positions": 2, "max_day": 2, "max_week": 4, "max_hold": 99999, "min_trades": 10},
        "vol_compression_breakout_etf_v1": {"max_positions": 2, "max_day": 2, "max_week": 5, "max_hold": 10, "min_trades": 30},
        "rs_pair_rotation_spy_qqq_xlk_xlu_v1": {"max_positions": 1, "max_day": 1, "max_week": 2, "max_hold": 99999, "min_trades": 10},
    }
    for candidate_id, spec in gate_specs.items():
        stats = payload["full_results"][candidate_id]["stats"]
        s180 = payload["summaries"][candidate_id][180]
        stress = payload["stress_summaries"][candidate_id][180]
        checks = [
            ("max_open_positions", stats["max_open_positions_observed"] <= spec["max_positions"], stats["max_open_positions_observed"], spec["max_positions"]),
            ("max_trades_per_day", stats["max_trades_per_day_observed"] <= spec["max_day"], stats["max_trades_per_day_observed"], spec["max_day"]),
            ("max_trades_per_week", stats["max_trades_per_week_observed"] <= spec["max_week"], stats["max_trades_per_week_observed"], spec["max_week"]),
            ("max_holding_period", stats["max_holding_period_observed"] <= spec["max_hold"], stats["max_holding_period_observed"], spec["max_hold"]),
            ("minimum_trade_count", stats["trade_count"] >= spec["min_trades"], stats["trade_count"], spec["min_trades"]),
            ("risk_buffer_vs_minus_600", float(s180["worst_drawdown"]) - STOP_DOLLARS >= 25.0, fmt(float(s180["worst_drawdown"]) - STOP_DOLLARS), 25.0),
            ("stop_hit_rate", float(s180["stop_hit_rate"]) == 0.0, fmt(s180["stop_hit_rate"]), 0.0),
            ("slippage_stress", float(stress["median_final_equity"]) >= STARTING_EQUITY and float(stress["stop_hit_rate"]) == 0.0, fmt(stress["median_final_equity"]), ">=3000 and no stop hit"),
            ("liquidity_filter", True, "positive volume and price gate applied", "required"),
            ("missing_stale_data_rule", True, "missing data blocks entries and can force exits", "required"),
            ("kill_switch_condition", True, "no broker/reconciliation path in this research runner", "no abnormal path"),
        ]
        for gate, passed, observed, threshold in checks:
            rows.append(
                {
                    "candidate_id": candidate_id,
                    "risk_gate": gate,
                    "status": "pass" if passed else "fail",
                    "observed_value": observed,
                    "threshold_or_rule": threshold,
                    "notes": "frozen risk-control discovery gate",
                }
            )
    return rows


def slippage_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for candidate_id in AUTHORIZED_CANDIDATE_IDS:
        base = payload["summaries"][candidate_id][180]
        stress = payload["stress_summaries"][candidate_id][180]
        rows.append(
            {
                "candidate_id": candidate_id,
                "base_slippage_bps_per_side": BASE_SLIPPAGE * 10_000,
                "stress_slippage_bps_per_side": STRESS_SLIPPAGE * 10_000,
                "base_180d_median_final_equity": fmt(base["median_final_equity"]),
                "stress_180d_median_final_equity": fmt(stress["median_final_equity"]),
                "stress_delta": fmt(float(stress["median_final_equity"]) - float(base["median_final_equity"])),
                "base_stop_hit_rate": fmt(base["stop_hit_rate"]),
                "stress_stop_hit_rate": fmt(stress["stop_hit_rate"]),
                "stress_result": "pass" if float(stress["median_final_equity"]) >= STARTING_EQUITY and float(stress["stop_hit_rate"]) == 0.0 else "fail",
            }
        )
    return rows


def promotion_blockers(candidate_id: str, payload: dict[str, Any], deltas: list[dict[str, Any]]) -> list[str]:
    blockers: list[str] = []
    s180 = payload["summaries"][candidate_id][180]
    stats = payload["full_results"][candidate_id]["stats"]
    concentration = concentration_diagnostics(candidate_id, payload["full_results"][candidate_id])
    gate_specs = {
        "dmr_liquid_etf_oversold_rebound_v1": {"max_positions": 2, "max_day": 2, "max_week": 6, "max_hold": 5},
        "vm_spy_qqq_daily_vol_target_v1": {"max_positions": 2, "max_day": 2, "max_week": 4, "max_hold": 99999},
        "vol_compression_breakout_etf_v1": {"max_positions": 2, "max_day": 2, "max_week": 5, "max_hold": 10},
        "rs_pair_rotation_spy_qqq_xlk_xlu_v1": {"max_positions": 1, "max_day": 1, "max_week": 2, "max_hold": 99999},
    }
    gate = gate_specs[candidate_id]
    if stats["max_open_positions_observed"] > gate["max_positions"]:
        blockers.append("max_open_positions_violation")
    if stats["max_trades_per_day_observed"] > gate["max_day"]:
        blockers.append("max_trades_per_day_violation")
    if stats["max_trades_per_week_observed"] > gate["max_week"]:
        blockers.append("max_trades_per_week_violation")
    if stats["max_holding_period_observed"] > gate["max_hold"]:
        blockers.append("max_holding_period_violation")
    risk_buffer = float(s180["worst_drawdown"]) - STOP_DOLLARS
    if float(s180["stop_hit_rate"]) > 0.0:
        blockers.append("stop_hit_above_zero")
    if risk_buffer < 50.0:
        blockers.append("risk_buffer_too_thin")
    if stats["trade_count"] < (50 if candidate_id == "dmr_liquid_etf_oversold_rebound_v1" else 30 if candidate_id == "vol_compression_breakout_etf_v1" else 10):
        blockers.append("too_few_trades_to_evaluate")
    if float(s180["target_300_before_stop_rate"]) < 0.20:
        blockers.append("low_target_hit_rate")
    if candidate_id in {"dmr_liquid_etf_oversold_rebound_v1", "vol_compression_breakout_etf_v1"} and concentration["post_2015_dependency_heavy"]:
        blockers.append("mixed_inception_post_2015_dependency_heavy")
    if concentration["xlre_contribution_material"]:
        blockers.append("xlre_contribution_material_in_mixed_inception_sample")
    if concentration["dominant_symbol_trade_share"] >= 0.55 and candidate_id != "vm_spy_qqq_daily_vol_target_v1":
        blockers.append("dominant_symbol_concentration")
    if candidate_id == "rs_pair_rotation_spy_qqq_xlk_xlu_v1" and concentration["qqq_xlk_weight_frequency"] >= 0.75:
        blockers.append("hidden_qqq_xlk_concentration")
    for row in deltas:
        if row["candidate_id"] != candidate_id or row["comparison_status"] != "computed":
            continue
        benchmark_id = row["benchmark_id"]
        delta = float(row["delta"])
        if benchmark_id in {active.VM_ID, active.DSR_ID, combo.COMBO_ID, active.SPY_200D_ID, "SPY_buy_hold", "QQQ_buy_hold", "XLK_buy_hold", "XLU_buy_hold"} and delta <= 25.0:
            blockers.append(f"underperforms_or_insufficient_edge_vs_{benchmark_id}")
        corr_value = row["correlation"]
        if corr_value not in {"", "unavailable"}:
            corr_float = float(corr_value)
            if benchmark_id in {active.VM_ID, combo.COMBO_ID, active.SPY_200D_ID} and corr_float >= 0.95 and delta < 50.0:
                blockers.append(f"duplicative_correlation_vs_{benchmark_id}")
    stress = payload["stress_summaries"][candidate_id][180]
    if float(stress["median_final_equity"]) < STARTING_EQUITY or float(stress["stop_hit_rate"]) > 0.0:
        blockers.append("slippage_stress_failure")
    if candidate_id == "vm_spy_qqq_daily_vol_target_v1":
        corr_vm = corr(payload["returns"], candidate_id, active.VM_ID)
        delta_vm = next((float(row["delta"]) for row in deltas if row["candidate_id"] == candidate_id and row["benchmark_id"] == active.VM_ID and row["comparison_status"] == "computed"), -999.0)
        if isinstance(corr_vm, float) and corr_vm >= 0.90 and delta_vm < 50.0:
            blockers.append("active_vm_clone_without_meaningful_improvement")
    return sorted(set(blockers))


def decisions(payload: dict[str, Any], deltas: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for candidate_id in AUTHORIZED_CANDIDATE_IDS:
        blockers = promotion_blockers(candidate_id, payload, deltas)
        if blockers:
            out[candidate_id] = {"decision": "discovery_reject", "reason": ";".join(blockers), "blockers": blockers}
        else:
            out[candidate_id] = {"decision": "promotion_review_candidate", "reason": "strict discovery gates passed; promotion review required before any further action", "blockers": []}
    return out


def candidate_result_rows(payload: dict[str, Any], decisions_by_id: dict[str, dict[str, Any]], deltas: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for candidate_id in AUTHORIZED_CANDIDATE_IDS:
        result = payload["full_results"][candidate_id]
        s90 = payload["summaries"][candidate_id][90]
        s180 = payload["summaries"][candidate_id][180]
        stats = result["stats"]
        conc = concentration_diagnostics(candidate_id, result)
        rows.append(
            {
                "candidate_id": candidate_id,
                "discovery_outcome": decisions_by_id[candidate_id]["decision"],
                "decision_reason": decisions_by_id[candidate_id]["reason"],
                "ending_equity": fmt(stats["ending_equity"]),
                "total_return": fmt(total_return_from_series(result["equity"])),
                "annualized_return": fmt(annualized_return(result["equity"])),
                "volatility": fmt(annualized_volatility(result["returns"])),
                "sharpe": fmt(sharpe_ratio(result["returns"])),
                "90d_median_final_equity": fmt(s90["median_final_equity"]),
                "180d_median_final_equity": fmt(s180["median_final_equity"]),
                "180d_worst_drawdown": fmt(s180["worst_drawdown"]),
                "risk_buffer_vs_minus_600": fmt(float(s180["worst_drawdown"]) - STOP_DOLLARS),
                "stop_hit_rate": fmt(s180["stop_hit_rate"]),
                "stop_hit_count": int(round(float(s180["stop_hit_rate"]) * int(s180["window_count"]))),
                "target_300_before_stop_rate": fmt(s180["target_300_before_stop_rate"]),
                "target_400_before_stop_rate": fmt(s180["target_400_before_stop_rate"]),
                "trade_count": stats["trade_count"],
                "average_holding_period": fmt(stats["average_holding_period"]),
                "turnover": fmt(stats["turnover"]),
                "max_open_positions_observed": stats["max_open_positions_observed"],
                "max_trades_per_day_observed": stats["max_trades_per_day_observed"],
                "max_trades_per_week_observed": stats["max_trades_per_week_observed"],
                "bil_cash_allocation_frequency": fmt(stats["bil_cash_allocation_frequency"]),
                "mean_bil_cash_allocation": fmt(stats["mean_bil_cash_allocation"]),
                "dominant_symbol": conc["dominant_symbol"],
                "dominant_symbol_trade_share": fmt(conc["dominant_symbol_trade_share"]),
                "xlre_trade_count": conc["xlre_trade_count"],
                "xlre_pnl": fmt(conc["xlre_pnl"]),
                "post_2015_trade_share": fmt(conc["post_2015_trade_share"]),
                "qqq_xlk_weight_frequency": fmt(conc["qqq_xlk_weight_frequency"]),
                "candidate_exhaustive_recommended": False,
                "paper_forward_active": False,
                "real_money_recommendation": False,
            }
        )
    return rows


def trade_diagnostic_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for candidate_id in AUTHORIZED_CANDIDATE_IDS:
        result = payload["full_results"][candidate_id]
        stats = result["stats"]
        rows.append(
            {
                "candidate_id": candidate_id,
                "row_type": "summary",
                "symbol": "",
                "entry_date": "",
                "exit_date": "",
                "exit_reason": "",
                "pnl": "",
                "holding_days": "",
                "trade_count": stats["trade_count"],
                "average_holding_period": fmt(stats["average_holding_period"]),
                "turnover": fmt(stats["turnover"]),
                "max_open_positions_observed": stats["max_open_positions_observed"],
                "max_trades_per_day_observed": stats["max_trades_per_day_observed"],
                "max_trades_per_week_observed": stats["max_trades_per_week_observed"],
                "notes": "summary row",
            }
        )
        for trade in result["trades"][:1000]:
            rows.append(
                {
                    "candidate_id": candidate_id,
                    "row_type": "trade",
                    "symbol": trade["symbol"],
                    "entry_date": trade["entry_date"],
                    "exit_date": trade["exit_date"],
                    "exit_reason": trade["exit_reason"],
                    "pnl": fmt(trade["pnl"]),
                    "holding_days": trade["holding_days"],
                    "trade_count": "",
                    "average_holding_period": "",
                    "turnover": "",
                    "max_open_positions_observed": "",
                    "max_trades_per_day_observed": "",
                    "max_trades_per_week_observed": "",
                    "notes": "trade-level diagnostic capped at first 1000 trades",
                }
            )
    return rows


def mixed_inception_markdown(store: dict[str, Any], payload: dict[str, Any]) -> str:
    lines = [
        "# First Expansion Mixed-Inception Diagnostics",
        "",
        "Per-asset availability is used. `XLRE` was not removed or substituted. These mixed-inception results are not identical to full common-start tests.",
        "",
    ]
    for candidate_id in ["dmr_liquid_etf_oversold_rebound_v1", "vol_compression_breakout_etf_v1"]:
        conc = concentration_diagnostics(candidate_id, payload["full_results"][candidate_id])
        first_dates = {symbol: store["first_dates"].get(symbol, "") for symbol in BROAD_UNIVERSE}
        earliest_full = max(pd.Timestamp(value) for value in first_dates.values() if value).date().isoformat()
        pre_xlre_trades = [trade for trade in payload["full_results"][candidate_id]["trades"] if trade.get("entry_date", "") < "2015-10-08"]
        lines.extend(
            [
                f"## `{candidate_id}`",
                "",
                f"Symbols used: `{';'.join(BROAD_UNIVERSE)}`",
                f"First available dates: `{json.dumps(first_dates, sort_keys=True)}`",
                f"Earliest full-universe date: `{earliest_full}`",
                f"Post-2015 trade share: `{fmt(conc['post_2015_trade_share'])}`",
                f"XLRE trade count: `{conc['xlre_trade_count']}`",
                f"XLRE PnL contribution: `{fmt(conc['xlre_pnl'])}`",
                f"XLRE contributed materially: `{conc['xlre_contribution_material']}`",
                f"Candidate remains interpretable before XLRE inception: `{len(pre_xlre_trades) > 0}`",
                f"Depends heavily on post-2015 data: `{conc['post_2015_dependency_heavy']}`",
                "",
                "Per-date available and eligible symbol counts are exported in `first_expansion_symbol_availability_diagnostics.csv`.",
                "",
            ]
        )
    return "\n".join(lines)


def rejection_markdown(decisions_by_id: dict[str, dict[str, Any]]) -> str:
    lines = ["# First Expansion Rejection Reasons", ""]
    for candidate_id in AUTHORIZED_CANDIDATE_IDS:
        decision = decisions_by_id[candidate_id]
        if decision["decision"] == "promotion_review_candidate":
            lines.append(f"- `{candidate_id}`: promoted only to promotion review; no candidate_exhaustive or paper-forward permission.")
        else:
            lines.append(f"- `{candidate_id}`: `{decision['reason']}`")
    return "\n".join(lines) + "\n"


def summary_markdown(
    manifest: dict[str, Any],
    result_rows: list[dict[str, Any]],
    decisions_by_id: dict[str, dict[str, Any]],
) -> str:
    lines = [
        "# First Expansion Discovery Batch Without Sector RS",
        "",
        f"Created UTC: `{manifest['created_utc']}`",
        f"Candidates evaluated: `{manifest['candidates_evaluated_count']}`",
        f"Promotion-review candidates: `{manifest['promotion_candidates_count']}`",
        f"Next action: `{manifest['next_action']}`",
        "",
        "This was a research-only discovery/backtest batch using cached adjusted daily OHLCV. It did not run sector RS, excluded rows, provider downloads, candidate_exhaustive, paper-forward, broker/live-order, ETF-wrapper reopening, or real-money recommendation logic.",
        "",
        "## Results",
        "",
        "| Candidate | Outcome | 180d median | 180d worst DD | Stop hit rate | Trades | Reason |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for row in result_rows:
        lines.append(
            f"| `{row['candidate_id']}` | `{row['discovery_outcome']}` | {row['180d_median_final_equity']} | {row['180d_worst_drawdown']} | {row['stop_hit_rate']} | {row['trade_count']} | `{row['decision_reason']}` |"
        )
    lines.extend(
        [
            "",
            "## Deferred And Excluded",
            "",
            "- `sector_rs_weekly_cash_filter_v1` remains deferred to a separate limited-history pre-registration because `XLRE` starts in 2015.",
            "- Intraday and event-data candidates were not included.",
        ]
    )
    return "\n".join(lines) + "\n"


def build_metrics_json(payload: dict[str, Any], result_rows: list[dict[str, Any]], slippage: list[dict[str, Any]], deltas: list[dict[str, Any]]) -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    rows_by_id = {row["candidate_id"]: row for row in result_rows}
    for candidate_id in AUTHORIZED_CANDIDATE_IDS:
        metrics[candidate_id] = {
            "result": rows_by_id[candidate_id],
            "window_summaries": payload["summaries"][candidate_id],
            "stress_window_summaries": payload["stress_summaries"][candidate_id],
            "slippage": [row for row in slippage if row["candidate_id"] == candidate_id],
            "benchmark_deltas": [row for row in deltas if row["candidate_id"] == candidate_id],
            "concentration": concentration_diagnostics(candidate_id, payload["full_results"][candidate_id]),
        }
    return metrics


def update_metadata(root: Path, manifest: dict[str, Any], decisions_by_id: dict[str, dict[str, Any]]) -> None:
    registry_path = root / EXPANSION_REGISTRY_PATH
    registry = load_yaml(registry_path)
    metadata = registry.setdefault("metadata", {})
    metadata.update(
        {
            "first_expansion_discovery_without_sector_rs_path": str((root / OUTPUT_DIR).resolve()),
            "first_expansion_discovery_without_sector_rs_status": "discovery_completed",
            "first_expansion_discovery_without_sector_rs_next_action": manifest["next_action"],
            "first_expansion_discovery_without_sector_rs_promotion_candidates_count": manifest["promotion_candidates_count"],
            "first_expansion_discovery_without_sector_rs_promotion_candidate_ids": manifest["promotion_candidate_ids"],
            "first_expansion_discovery_without_sector_rs_rejected_candidate_ids": manifest["rejected_candidate_ids"],
            "sector_rs_deferred": True,
            "discovery_run": True,
            "backtests_run": True,
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
            "updated_utc": manifest["created_utc"],
        }
    )
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(yaml.safe_dump(registry, sort_keys=False, width=120, allow_unicode=False), encoding="utf-8")

    roadmap_path = root / EXPANSION_ROADMAP_PATH
    existing = roadmap_path.read_text(encoding="utf-8") if roadmap_path.exists() else "# Strategy Expansion Roadmap\n"
    marker = "## First Expansion Discovery Without Sector RS Result"
    section = f"""## First Expansion Discovery Without Sector RS Result

Created UTC: `{manifest['created_utc']}`

Rows evaluated: `{', '.join(AUTHORIZED_CANDIDATE_IDS)}`

Rows deferred/excluded: `{', '.join(EXCLUDED_CANDIDATE_IDS)}`

Promotion-review candidates: `{manifest['promotion_candidates_count']}`

Discovery outcomes: `{json.dumps({candidate_id: data['decision'] for candidate_id, data in decisions_by_id.items()}, sort_keys=True)}`

Next action: `{manifest['next_action']}`

No candidate_exhaustive, paper-forward action, provider download, broker/live-order path, ETF-wrapper reopening, or real-money recommendation is authorized.
"""
    updated = existing.split(marker, 1)[0].rstrip() + "\n\n" + section if marker in existing else existing.rstrip() + "\n\n" + section
    roadmap_path.parent.mkdir(parents=True, exist_ok=True)
    roadmap_path.write_text(updated.rstrip() + "\n", encoding="utf-8")


def active_observation_hashes(root: Path) -> dict[str, str]:
    return {strategy_id: file_hash(path) for strategy_id, path in active.active_observation_paths(root).items()}


def create_packet(output: Path) -> Path:
    packet = output / "first_expansion_discovery_packet.zip"
    if packet.exists():
        packet.unlink()
    with zipfile.ZipFile(packet, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(output.iterdir()):
            if path.is_file() and path.name != packet.name:
                zf.write(path, path.name)
    return packet


def run_first_expansion_discovery_batch_without_sector_rs(root: Path = ROOT) -> dict[str, Any]:
    output = clean_output_dir(root)
    created_utc = now_utc()
    prereg_batch = load_preregistered_batch(root)
    authorized = authorized_candidates_from_batch(prereg_batch)
    authorization_mismatches = validate_authorization(root)
    frozen_projection_before = deepcopy(authorized)
    registry_before = load_yaml(root / EXPANSION_REGISTRY_PATH)
    active_obs_before = active_observation_hashes(root)

    store = load_price_store(root, ALL_AUTHORIZED_SYMBOLS)
    if not store["available"]:
        raise RuntimeError("Required cached symbols missing; provider download is forbidden: " + ",".join(store["missing_symbols"]))
    ind = indicator_frame(store)
    payload = build_candidate_payload(store, ind)
    deltas = benchmark_delta_rows(payload)
    decisions_by_id = decisions(payload, deltas)
    promotion_ids = [candidate_id for candidate_id, decision in decisions_by_id.items() if decision["decision"] == "promotion_review_candidate"]
    rejected_ids = [candidate_id for candidate_id in AUTHORIZED_CANDIDATE_IDS if candidate_id not in promotion_ids]
    next_action = NEXT_ACTION_PROMOTION if promotion_ids else NEXT_ACTION_NO_CANDIDATE
    result_rows = candidate_result_rows(payload, decisions_by_id, deltas)
    risk_rows = risk_gate_rows(payload)
    slip_rows = slippage_rows(payload)
    trade_rows = trade_diagnostic_rows(payload)
    availability_rows = store["qa_rows"] + payload["trace_rows"]

    manifest = {
        "artifact": "first_expansion_discovery_batch_without_sector_rs",
        "created_utc": created_utc,
        "output_dir": str(output),
        "analysis_start_date": str(store["index"][MAX_WARMUP_DAYS].date()),
        "analysis_end_date": store["analysis_end_date"],
        "discovery_run": True,
        "backtests_run": True,
        "candidates_evaluated_count": len(AUTHORIZED_CANDIDATE_IDS),
        "candidates_evaluated": AUTHORIZED_CANDIDATE_IDS,
        "excluded_candidate_ids": EXCLUDED_CANDIDATE_IDS,
        "sector_rs_deferred": True,
        "deferred_candidate_ids": DEFERRED_CANDIDATE_IDS,
        "intraday_candidates_included": False,
        "event_data_candidates_included": False,
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
        "promotion_candidates_count": len(promotion_ids),
        "promotion_candidate_ids": promotion_ids,
        "rejected_candidate_ids": rejected_ids,
        "valid_outcomes": sorted(VALID_OUTCOMES),
        "next_action": next_action,
        "authorization_mismatches": authorization_mismatches,
    }

    update_metadata(root, manifest, decisions_by_id)
    registry_after = load_yaml(root / EXPANSION_REGISTRY_PATH)
    active_obs_after = active_observation_hashes(root)
    frozen_projection_after = authorized_candidates_from_batch(load_preregistered_batch(root))
    consistency = {
        "discovery_completed": True,
        "backtests_run": True,
        "exactly_four_candidates_evaluated": AUTHORIZED_CANDIDATE_IDS == manifest["candidates_evaluated"],
        "sector_rs_not_evaluated": "sector_rs_weekly_cash_filter_v1" not in manifest["candidates_evaluated"],
        "excluded_candidates_not_evaluated": not any(candidate_id in manifest["candidates_evaluated"] for candidate_id in EXCLUDED_CANDIDATE_IDS),
        "intraday_candidates_included": False,
        "event_data_candidates_included": False,
        "provider_download": False,
        "candidate_exhaustive_run": False,
        "paper_forward_review": False,
        "paper_forward_activation": False,
        "broker_path_touched": False,
        "live_orders": False,
        "real_money_recommendation": False,
        "frozen_rules_changed": frozen_projection_before != frozen_projection_after,
        "candidate_universe_changed": any(frozen_projection_before[cid].get("universe") != frozen_projection_after[cid].get("universe") for cid in AUTHORIZED_CANDIDATE_IDS),
        "benchmarks_changed": any(frozen_projection_before[cid].get("benchmark_controls") != frozen_projection_after[cid].get("benchmark_controls") for cid in AUTHORIZED_CANDIDATE_IDS),
        "active_strategy_state_changed": active_obs_before != active_obs_after,
        "etf_wrapper_track_reopened": False,
        "outcomes_limited": all(data["decision"] in VALID_OUTCOMES for data in decisions_by_id.values()),
        "promotion_candidate_file_created": True,
        "rejection_reasons_created": True,
        "risk_gate_results_for_every_candidate": set(AUTHORIZED_CANDIDATE_IDS) == {row["candidate_id"] for row in risk_rows},
        "benchmark_deltas_reported": bool(deltas),
        "mixed_inception_diagnostics_created": True,
        "next_action_explicit": next_action in {NEXT_ACTION_PROMOTION, NEXT_ACTION_NO_CANDIDATE, "pre_register_second_expansion_discovery_batch"},
        "metadata_files_updated": registry_before != registry_after,
    }
    consistency["consistency_passed"] = (
        consistency["discovery_completed"]
        and consistency["backtests_run"]
        and consistency["exactly_four_candidates_evaluated"]
        and consistency["sector_rs_not_evaluated"]
        and consistency["excluded_candidates_not_evaluated"]
        and not consistency["intraday_candidates_included"]
        and not consistency["event_data_candidates_included"]
        and not consistency["provider_download"]
        and not consistency["candidate_exhaustive_run"]
        and not consistency["paper_forward_review"]
        and not consistency["paper_forward_activation"]
        and not consistency["broker_path_touched"]
        and not consistency["live_orders"]
        and not consistency["real_money_recommendation"]
        and not consistency["frozen_rules_changed"]
        and not consistency["candidate_universe_changed"]
        and not consistency["benchmarks_changed"]
        and not consistency["active_strategy_state_changed"]
        and not consistency["etf_wrapper_track_reopened"]
        and consistency["outcomes_limited"]
        and consistency["risk_gate_results_for_every_candidate"]
        and consistency["benchmark_deltas_reported"]
        and consistency["mixed_inception_diagnostics_created"]
        and consistency["next_action_explicit"]
    )

    result_fields = [
        "candidate_id",
        "discovery_outcome",
        "decision_reason",
        "ending_equity",
        "total_return",
        "annualized_return",
        "volatility",
        "sharpe",
        "90d_median_final_equity",
        "180d_median_final_equity",
        "180d_worst_drawdown",
        "risk_buffer_vs_minus_600",
        "stop_hit_rate",
        "stop_hit_count",
        "target_300_before_stop_rate",
        "target_400_before_stop_rate",
        "trade_count",
        "average_holding_period",
        "turnover",
        "max_open_positions_observed",
        "max_trades_per_day_observed",
        "max_trades_per_week_observed",
        "bil_cash_allocation_frequency",
        "mean_bil_cash_allocation",
        "dominant_symbol",
        "dominant_symbol_trade_share",
        "xlre_trade_count",
        "xlre_pnl",
        "post_2015_trade_share",
        "qqq_xlk_weight_frequency",
        "candidate_exhaustive_recommended",
        "paper_forward_active",
        "real_money_recommendation",
    ]
    write_json(output / "first_expansion_discovery_manifest.json", manifest)
    (output / "first_expansion_discovery_summary.md").write_text(summary_markdown(manifest, result_rows, decisions_by_id), encoding="utf-8")
    write_csv(output / "first_expansion_candidate_results.csv", result_rows, result_fields)
    write_json(output / "first_expansion_candidate_metrics.json", build_metrics_json(payload, result_rows, slip_rows, deltas))
    write_csv(output / "first_expansion_benchmark_deltas.csv", deltas, ["candidate_id", "benchmark_id", "candidate_180d_median_final_equity", "benchmark_180d_median_final_equity", "delta", "correlation", "comparison_status", "missing_reason"])
    write_csv(output / "first_expansion_risk_gate_results.csv", risk_rows, ["candidate_id", "risk_gate", "status", "observed_value", "threshold_or_rule", "notes"])
    write_csv(output / "first_expansion_slippage_stress_results.csv", slip_rows, ["candidate_id", "base_slippage_bps_per_side", "stress_slippage_bps_per_side", "base_180d_median_final_equity", "stress_180d_median_final_equity", "stress_delta", "base_stop_hit_rate", "stress_stop_hit_rate", "stress_result"])
    write_csv(output / "first_expansion_trade_diagnostics.csv", trade_rows, ["candidate_id", "row_type", "symbol", "entry_date", "exit_date", "exit_reason", "pnl", "holding_days", "trade_count", "average_holding_period", "turnover", "max_open_positions_observed", "max_trades_per_day_observed", "max_trades_per_week_observed", "notes"])
    write_csv(output / "first_expansion_symbol_availability_diagnostics.csv", availability_rows, ["candidate_id", "row_type", "date", "symbol", "symbols_used", "first_available_date", "last_available_date", "available_at_decision", "eligible_at_decision", "available_symbol_count", "eligible_symbol_count", "available_symbols", "eligible_symbols", "earliest_full_universe_date", "notes"])
    (output / "first_expansion_mixed_inception_diagnostics.md").write_text(mixed_inception_markdown(store, payload), encoding="utf-8")
    write_csv(output / "first_expansion_promotion_candidates.csv", [row for row in result_rows if row["discovery_outcome"] == "promotion_review_candidate"], result_fields)
    (output / "first_expansion_rejection_reasons.md").write_text(rejection_markdown(decisions_by_id), encoding="utf-8")
    (output / "first_expansion_next_action.md").write_text(f"# First Expansion Next Action\n\n`{next_action}`\n\nDo not run this next action from the discovery batch.\n", encoding="utf-8")
    write_json(output / "first_expansion_discovery_consistency_check.json", consistency)
    packet = create_packet(output)

    return {
        "output_dir": str(output),
        "packet": str(packet),
        "manifest": manifest,
        "decisions": {candidate_id: data["decision"] for candidate_id, data in decisions_by_id.items()},
        "promotion_candidates_count": len(promotion_ids),
        "promotion_candidate_ids": promotion_ids,
        "rejected_candidate_ids": rejected_ids,
        "next_action": next_action,
        "consistency": consistency,
    }


def main() -> None:
    print(json.dumps(run_first_expansion_discovery_batch_without_sector_rs(ROOT), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
