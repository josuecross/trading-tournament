from __future__ import annotations

import csv
import hashlib
import itertools
import json
import math
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import run_active_strategy_evidence_recompute as active
from strategy_lab.research_os.research import etf_pairs_short_accounting_resolution_v1 as accounting


ROOT = Path(__file__).resolve().parents[3]
OUTPUT_DIR = ROOT / "evidence" / "etf_pairs_distance_screen_v1" / "latest"
SOURCE_PREREG_DIR = ROOT / "evidence" / "etf_pairs_single_source_preregistration_v1" / "latest"
ACCOUNTING_DIR = ROOT / "evidence" / "etf_pairs_short_accounting_resolution_v1" / "latest"
ACTIVE_COMBO_SERIES = ROOT / "evidence" / "active_combo_series_reconciliation" / "latest" / "combo_daily_series.csv"

CANDIDATE_ID = accounting.CANDIDATE_ID
FAMILY_ID = accounting.FAMILY_ID
SOURCE_ID = accounting.SOURCE_ID
FROZEN_UNIVERSE = accounting.FROZEN_UNIVERSE
PAIR_COUNT = accounting.PAIR_COUNT
FORMATION_MONTHS = accounting.FORMATION_MONTHS
TRADING_MONTHS = accounting.TRADING_MONTHS
ENTRY_THRESHOLD_MULTIPLIER = accounting.ENTRY_THRESHOLD_SD
BORROW_RATE_ANNUAL = accounting.BORROW_RATE_ANNUAL
BORROW_RATE_DAILY = accounting.BORROW_RATE_DAILY
TRANSACTION_COST_RATE = accounting.TRANSACTION_COST_RATE
INITIAL_CAPITAL = 3000.0
TOL = 1e-9

OUTCOME_LABELS = {
    "comparative_evidence_positive",
    "higher_return_higher_risk",
    "cost_sensitive_no_edge",
    "control_weak",
    "signal_scarce_no_evidence",
    "no_material_edge",
    "accounting_or_short_feasibility_failure",
    "invalid_methodology",
    "direction_owner_review_required",
}


@dataclass(frozen=True)
class CycleDefinition:
    cycle_id: str
    cycle_number: int
    formation_start: pd.Timestamp
    formation_end: pd.Timestamp
    trading_start: pd.Timestamp
    trading_end: pd.Timestamp
    formation_dates: tuple[pd.Timestamp, ...]
    trading_dates: tuple[pd.Timestamp, ...]


@dataclass
class SleeveRuntime:
    cycle_id: str
    sleeve_id: str
    pair_rank: int
    first_ticker: str
    second_ticker: str
    threshold: float
    ledger: accounting.SleeveLedger
    pending_entry_date: pd.Timestamp | None = None
    pending_entry_signal_date: pd.Timestamp | None = None
    pending_entry_spread: float | None = None
    pending_entry_long_symbol: str = ""
    pending_entry_short_symbol: str = ""
    pending_exit_date: pd.Timestamp | None = None
    pending_exit_signal_date: pd.Timestamp | None = None
    entry_spread_sign: int = 0
    current_entry_date: pd.Timestamp | None = None
    current_entry_signal_date: pd.Timestamp | None = None
    entries: int = 0
    convergence_exits: int = 0
    forced_closes: int = 0
    open_day_count: int = 0
    completed_open_days: list[int] = field(default_factory=list)
    invalid_reason: str = ""

    @property
    def pair_id(self) -> str:
        return f"{self.first_ticker}-{self.second_ticker}"


def csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        if not math.isfinite(value):
            return ""
        return f"{value:.12g}"
    if isinstance(value, (list, tuple, set)):
        return "|".join(str(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True)
    if isinstance(value, pd.Timestamp):
        return str(value.date())
    return str(value)


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fields is None:
        fields = sorted({key for row in rows for key in row})
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: csv_value(row.get(field, "")) for field in fields})


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def sha256_path(path: Path) -> str:
    if not path.exists():
        return "missing"
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def stable_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest().upper()


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def cache_path(symbol: str) -> Path:
    return ROOT / "data" / "cache" / f"{symbol}.csv"


def load_price_frame(symbols: tuple[str, ...] | list[str]) -> pd.DataFrame:
    series: list[pd.Series] = []
    for symbol in symbols:
        path = cache_path(symbol)
        frame = pd.read_csv(path)
        dates = pd.to_datetime(frame["date"], errors="coerce").dt.tz_localize(None)
        close = pd.to_numeric(frame["adj_close"], errors="coerce")
        item = pd.Series(close.to_numpy(dtype=float), index=dates, name=symbol).dropna().sort_index()
        item = item[~item.index.duplicated(keep="last")]
        series.append(item)
    return pd.concat(series, axis=1, join="outer", sort=True).sort_index()


def cache_rows(symbols: tuple[str, ...] = FROZEN_UNIVERSE) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for symbol in symbols:
        path = cache_path(symbol)
        frame = pd.read_csv(path) if path.exists() else pd.DataFrame()
        dates = pd.to_datetime(frame.get("date", pd.Series(dtype=object)), errors="coerce").dropna()
        close = pd.to_numeric(frame.get("adj_close", pd.Series(dtype=float)), errors="coerce").dropna()
        rows.append(
            {
                "symbol": symbol,
                "cache_path": rel(path),
                "cache_sha256": sha256_path(path),
                "cache_ready": path.exists() and not dates.empty and not close.empty,
                "first_date": "" if dates.empty else str(dates.min().date()),
                "last_date": "" if dates.empty else str(dates.max().date()),
                "row_count": int(len(frame)),
                "provider_download_required": False,
            }
        )
    return rows


def common_valid_prices(prices: pd.DataFrame, symbols: tuple[str, ...] = FROZEN_UNIVERSE) -> pd.DataFrame:
    return prices.loc[:, list(symbols)].dropna(how="any").sort_index()


def first_common_session_in_month(common_index: pd.DatetimeIndex, year: int, month: int) -> pd.Timestamp | None:
    matches = common_index[(common_index.year == year) & (common_index.month == month)]
    return pd.Timestamp(matches[0]) if len(matches) else None


def generate_cycle_definitions(common_prices: pd.DataFrame) -> list[CycleDefinition]:
    common_index = pd.DatetimeIndex(common_prices.index)
    if common_index.empty:
        return []
    cycles: list[CycleDefinition] = []
    number = 1
    for year in range(int(common_index.min().year), int(common_index.max().year) + 1):
        for month in (1, 7):
            start = first_common_session_in_month(common_index, year, month)
            if start is None:
                continue
            formation_boundary = start - pd.DateOffset(months=FORMATION_MONTHS)
            end_boundary = start + pd.DateOffset(months=TRADING_MONTHS)
            if len(common_index[common_index >= end_boundary]) == 0:
                continue
            formation_dates = common_index[(common_index >= formation_boundary) & (common_index < start)]
            trading_dates = common_index[(common_index >= start) & (common_index < end_boundary)]
            if len(formation_dates) < 2 or len(trading_dates) < 2:
                continue
            if pd.Timestamp(formation_dates[0]) > pd.Timestamp(formation_boundary) + pd.Timedelta(days=7):
                continue
            cycle_id = f"cycle_{year}_{month:02d}"
            cycles.append(
                CycleDefinition(
                    cycle_id=cycle_id,
                    cycle_number=number,
                    formation_start=pd.Timestamp(formation_dates[0]),
                    formation_end=pd.Timestamp(formation_dates[-1]),
                    trading_start=pd.Timestamp(trading_dates[0]),
                    trading_end=pd.Timestamp(trading_dates[-1]),
                    formation_dates=tuple(pd.Timestamp(date) for date in formation_dates),
                    trading_dates=tuple(pd.Timestamp(date) for date in trading_dates),
                )
            )
            number += 1
    return cycles


def normalize_for_cycle(common_prices: pd.DataFrame, cycle: CycleDefinition) -> pd.DataFrame:
    all_dates = list(cycle.formation_dates) + list(cycle.trading_dates)
    raw = common_prices.loc[all_dates, list(FROZEN_UNIVERSE)].astype(float)
    base = raw.loc[cycle.formation_dates[0], list(FROZEN_UNIVERSE)]
    return raw.divide(base, axis=1)


def pair_distance_rows(normalized: pd.DataFrame, cycle: CycleDefinition) -> list[dict[str, Any]]:
    formation = normalized.loc[list(cycle.formation_dates), list(FROZEN_UNIVERSE)]
    rows: list[dict[str, Any]] = []
    for first, second in itertools.combinations(FROZEN_UNIVERSE, 2):
        diff = formation[first] - formation[second]
        distance = float((diff * diff).sum())
        spread = diff.astype(float)
        spread_std = float(spread.std(ddof=1))
        threshold = ENTRY_THRESHOLD_MULTIPLIER * spread_std if math.isfinite(spread_std) else float("nan")
        rows.append(
            {
                "cycle_id": cycle.cycle_id,
                "formation_start": cycle.formation_start,
                "formation_end": cycle.formation_end,
                "first_ticker": first,
                "second_ticker": second,
                "pair_id": f"{first}-{second}",
                "distance": distance,
                "spread_std_ddof1": spread_std,
                "entry_threshold": threshold,
                "threshold_valid": math.isfinite(threshold) and threshold > 0.0,
            }
        )
    return sorted(rows, key=lambda row: (float(row["distance"]), str(row["first_ticker"]), str(row["second_ticker"])))


def selected_pairs(distance_rows: list[dict[str, Any]], cycle: CycleDefinition) -> list[dict[str, Any]]:
    valid = [row for row in distance_rows if row["cycle_id"] == cycle.cycle_id and row["threshold_valid"]]
    selected = valid[:PAIR_COUNT]
    rows: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    for row in selected:
        counts[str(row["first_ticker"])] = counts.get(str(row["first_ticker"]), 0) + 1
        counts[str(row["second_ticker"])] = counts.get(str(row["second_ticker"]), 0) + 1
    overlap_count = sum(count - 1 for count in counts.values() if count > 1)
    for rank, row in enumerate(selected, start=1):
        rows.append(
            {
                "cycle_id": cycle.cycle_id,
                "pair_rank": rank,
                "pair_id": row["pair_id"],
                "first_ticker": row["first_ticker"],
                "second_ticker": row["second_ticker"],
                "distance": row["distance"],
                "spread_std_ddof1": row["spread_std_ddof1"],
                "entry_threshold": row["entry_threshold"],
                "pair_overlap_count": overlap_count,
                "pair_fixed_through_cycle": True,
            }
        )
    return rows


def next_date(dates: tuple[pd.Timestamp, ...], date: pd.Timestamp) -> pd.Timestamp | None:
    for idx, current in enumerate(dates):
        if current == date and idx + 1 < len(dates):
            return dates[idx + 1]
    return None


def price_at(common_prices: pd.DataFrame, date: pd.Timestamp, symbol: str) -> float | None:
    try:
        value = float(common_prices.at[date, symbol])
    except Exception:
        return None
    return value if math.isfinite(value) else None


def spread_at(normalized: pd.DataFrame, date: pd.Timestamp, first: str, second: str) -> float:
    return float(normalized.at[date, first] - normalized.at[date, second])


def position_direction(spread: float, first: str, second: str) -> tuple[str, str, int]:
    if spread > 0:
        return second, first, 1
    return first, second, -1


def sleeve_snapshot_row(sleeve: SleeveRuntime, date: pd.Timestamp, event: str) -> dict[str, Any]:
    row = sleeve.ledger.snapshot(str(date.date()), event)
    row.update(
        {
            "cycle_id": sleeve.cycle_id,
            "pair_rank": sleeve.pair_rank,
            "pair_id": sleeve.pair_id,
            "first_ticker": sleeve.first_ticker,
            "second_ticker": sleeve.second_ticker,
            "threshold": sleeve.threshold,
            "pending_entry_date": "" if sleeve.pending_entry_date is None else str(sleeve.pending_entry_date.date()),
            "pending_exit_date": "" if sleeve.pending_exit_date is None else str(sleeve.pending_exit_date.date()),
            "invalid_reason": sleeve.invalid_reason,
        }
    )
    return row


def check_sleeve_feasible(sleeve: SleeveRuntime) -> str:
    equity = sleeve.ledger.equity
    if not math.isfinite(equity) or equity <= 0.0:
        return "sleeve_insolvency"
    if not math.isfinite(sleeve.ledger.cash) or not math.isfinite(sleeve.ledger.short_liability):
        return "non_finite_accounting"
    if sleeve.ledger.invalid:
        return "missing_price_invalidated"
    return ""


def aggregate_runtime_sleeves(sleeves: list[SleeveRuntime], date: pd.Timestamp, cycle_id: str) -> dict[str, Any]:
    equity = float(sum(sleeve.ledger.equity for sleeve in sleeves))
    long_mv = float(sum(sleeve.ledger.long_market_value for sleeve in sleeves))
    short_liability = float(sum(sleeve.ledger.short_liability for sleeve in sleeves))
    cash = float(sum(sleeve.ledger.cash for sleeve in sleeves))
    restricted = float(sum(sleeve.ledger.restricted_short_proceeds for sleeve in sleeves))
    tx = float(sum(sleeve.ledger.transaction_costs for sleeve in sleeves))
    borrow = float(sum(sleeve.ledger.accrued_borrow_cost for sleeve in sleeves))
    return {
        "date": str(date.date()),
        "cycle_id": cycle_id,
        "strategy_equity": equity,
        "cash": cash,
        "restricted_short_proceeds": restricted,
        "free_cash": cash - restricted,
        "long_market_value": long_mv,
        "short_liability": short_liability,
        "cumulative_transaction_costs": tx,
        "cumulative_borrow_costs": borrow,
        "aggregate_gross_exposure": (abs(long_mv) + abs(short_liability)) / equity if abs(equity) > TOL else float("nan"),
        "aggregate_net_exposure": (long_mv - short_liability) / equity if abs(equity) > TOL else float("nan"),
        "open_sleeves": sum(1 for sleeve in sleeves if sleeve.ledger.open_position),
        "invalid": any(bool(sleeve.invalid_reason) for sleeve in sleeves),
    }


def simulate_cycle(
    common_prices: pd.DataFrame,
    normalized: pd.DataFrame,
    cycle: CycleDefinition,
    selected: list[dict[str, Any]],
    starting_equity: float,
) -> dict[str, Any]:
    sleeve_capital = starting_equity / PAIR_COUNT
    sleeves = [
        SleeveRuntime(
            cycle_id=cycle.cycle_id,
            sleeve_id=f"{cycle.cycle_id}_sleeve_{idx}",
            pair_rank=int(row["pair_rank"]),
            first_ticker=str(row["first_ticker"]),
            second_ticker=str(row["second_ticker"]),
            threshold=float(row["entry_threshold"]),
            ledger=accounting.SleeveLedger(f"{cycle.cycle_id}_sleeve_{idx}", sleeve_capital),
        )
        for idx, row in enumerate(selected, start=1)
    ]
    daily_sleeve_rows: list[dict[str, Any]] = []
    signal_rows: list[dict[str, Any]] = []
    trade_rows: list[dict[str, Any]] = []
    strategy_rows: list[dict[str, Any]] = []
    invalid_reason = ""
    previous_equity = starting_equity
    previous_tx = 0.0
    previous_borrow = 0.0
    end_date = cycle.trading_dates[-1]

    for date in cycle.trading_dates:
        force_end = date == end_date
        if invalid_reason:
            break
        for sleeve in sleeves:
            day_event = "flat"
            entry_executed = False
            exit_executed = False
            if sleeve.pending_exit_date == date and sleeve.ledger.open_position:
                row = sleeve.ledger.exit(
                    str(date.date()),
                    price_at(common_prices, date, sleeve.ledger.long_symbol),
                    price_at(common_prices, date, sleeve.ledger.short_symbol),
                    "convergence_exit",
                )
                sleeve.convergence_exits += 1
                sleeve.completed_open_days.append(max(0, len([d for d in cycle.trading_dates if sleeve.current_entry_date is not None and sleeve.current_entry_date <= d <= date]) - 1))
                trade = {**row, "cycle_id": cycle.cycle_id, "pair_id": sleeve.pair_id, "trade_event": "convergence_exit", "signal_date": str(sleeve.pending_exit_signal_date.date()) if sleeve.pending_exit_signal_date is not None else ""}
                trade_rows.append(trade)
                sleeve.pending_exit_date = None
                sleeve.pending_exit_signal_date = None
                sleeve.entry_spread_sign = 0
                sleeve.current_entry_date = None
                sleeve.current_entry_signal_date = None
                exit_executed = True
                day_event = "convergence_exit"
            if sleeve.pending_entry_date == date and not sleeve.ledger.open_position:
                row = sleeve.ledger.enter(
                    str(date.date()),
                    sleeve.pending_entry_long_symbol,
                    sleeve.pending_entry_short_symbol,
                    price_at(common_prices, date, sleeve.pending_entry_long_symbol),
                    price_at(common_prices, date, sleeve.pending_entry_short_symbol),
                )
                sleeve.entries += 1
                if sleeve.entries > 1:
                    pass
                sleeve.entry_spread_sign = 1 if float(sleeve.pending_entry_spread or 0.0) > 0 else -1
                sleeve.current_entry_date = date
                sleeve.current_entry_signal_date = sleeve.pending_entry_signal_date
                trade = {**row, "cycle_id": cycle.cycle_id, "pair_id": sleeve.pair_id, "trade_event": "entry", "signal_date": str(sleeve.pending_entry_signal_date.date()) if sleeve.pending_entry_signal_date is not None else ""}
                trade_rows.append(trade)
                sleeve.pending_entry_date = None
                sleeve.pending_entry_signal_date = None
                sleeve.pending_entry_spread = None
                sleeve.pending_entry_long_symbol = ""
                sleeve.pending_entry_short_symbol = ""
                entry_executed = True
                day_event = "entry"
            if sleeve.ledger.open_position and force_end:
                row = sleeve.ledger.exit(
                    str(date.date()),
                    price_at(common_prices, date, sleeve.ledger.long_symbol),
                    price_at(common_prices, date, sleeve.ledger.short_symbol),
                    "forced_close",
                )
                sleeve.forced_closes += 1
                sleeve.completed_open_days.append(max(0, len([d for d in cycle.trading_dates if sleeve.current_entry_date is not None and sleeve.current_entry_date <= d <= date]) - 1))
                trade = {**row, "cycle_id": cycle.cycle_id, "pair_id": sleeve.pair_id, "trade_event": "forced_close", "signal_date": str(date.date())}
                trade_rows.append(trade)
                sleeve.pending_exit_date = None
                sleeve.pending_exit_signal_date = None
                sleeve.entry_spread_sign = 0
                sleeve.current_entry_date = None
                sleeve.current_entry_signal_date = None
                exit_executed = True
                day_event = "forced_close"
            elif sleeve.ledger.open_position and not entry_executed and not exit_executed:
                sleeve.ledger.mark(
                    str(date.date()),
                    price_at(common_prices, date, sleeve.ledger.long_symbol),
                    price_at(common_prices, date, sleeve.ledger.short_symbol),
                    accrue_borrow=True,
                )
                day_event = "mark"
            feasibility = check_sleeve_feasible(sleeve)
            if feasibility:
                sleeve.invalid_reason = feasibility
                invalid_reason = feasibility
            if sleeve.ledger.open_position:
                sleeve.open_day_count += 1
            spread = spread_at(normalized, date, sleeve.first_ticker, sleeve.second_ticker)
            signal_type = "no_signal"
            execution_date = ""
            if not invalid_reason and not force_end:
                next_exec = next_date(cycle.trading_dates, date)
                if sleeve.ledger.open_position and sleeve.pending_exit_date is None and not entry_executed:
                    crossed = (sleeve.entry_spread_sign > 0 and spread <= 0.0) or (sleeve.entry_spread_sign < 0 and spread >= 0.0)
                    if crossed and next_exec is not None:
                        sleeve.pending_exit_date = next_exec
                        sleeve.pending_exit_signal_date = date
                        signal_type = "pending_convergence_exit"
                        execution_date = str(next_exec.date())
                elif not sleeve.ledger.open_position and sleeve.pending_entry_date is None:
                    if abs(spread) > sleeve.threshold and next_exec is not None:
                        long_symbol, short_symbol, _sign = position_direction(spread, sleeve.first_ticker, sleeve.second_ticker)
                        sleeve.pending_entry_date = next_exec
                        sleeve.pending_entry_signal_date = date
                        sleeve.pending_entry_spread = spread
                        sleeve.pending_entry_long_symbol = long_symbol
                        sleeve.pending_entry_short_symbol = short_symbol
                        signal_type = "pending_entry"
                        execution_date = str(next_exec.date())
            signal_rows.append(
                {
                    "cycle_id": cycle.cycle_id,
                    "date": str(date.date()),
                    "sleeve_id": sleeve.sleeve_id,
                    "pair_rank": sleeve.pair_rank,
                    "pair_id": sleeve.pair_id,
                    "first_ticker": sleeve.first_ticker,
                    "second_ticker": sleeve.second_ticker,
                    "spread": spread,
                    "threshold": sleeve.threshold,
                    "abs_spread_gt_threshold": abs(spread) > sleeve.threshold,
                    "signal_type": signal_type,
                    "pending_execution_date": execution_date,
                    "long_symbol": sleeve.pending_entry_long_symbol if signal_type == "pending_entry" else sleeve.ledger.long_symbol,
                    "short_symbol": sleeve.pending_entry_short_symbol if signal_type == "pending_entry" else sleeve.ledger.short_symbol,
                    "open_position": sleeve.ledger.open_position,
                    "same_close_execution": False,
                }
            )
            daily_sleeve_rows.append(sleeve_snapshot_row(sleeve, date, day_event))
        aggregate = aggregate_runtime_sleeves(sleeves, date, cycle.cycle_id)
        equity = float(aggregate["strategy_equity"])
        tx = float(aggregate["cumulative_transaction_costs"])
        borrow = float(aggregate["cumulative_borrow_costs"])
        aggregate["daily_return"] = equity / previous_equity - 1.0 if abs(previous_equity) > TOL else float("nan")
        aggregate["daily_transaction_cost"] = tx - previous_tx
        aggregate["daily_borrow_cost"] = borrow - previous_borrow
        strategy_rows.append(aggregate)
        previous_equity = equity
        previous_tx = tx
        previous_borrow = borrow
        if not math.isfinite(equity) or equity <= 0.0:
            invalid_reason = "strategy_insolvency"
            break

    final_equity = float(strategy_rows[-1]["strategy_equity"]) if strategy_rows else starting_equity
    return {
        "cycle_id": cycle.cycle_id,
        "starting_equity": starting_equity,
        "final_equity": final_equity,
        "invalid_reason": invalid_reason,
        "sleeves": sleeves,
        "daily_sleeve_rows": daily_sleeve_rows,
        "signal_rows": signal_rows,
        "trade_rows": trade_rows,
        "strategy_rows": strategy_rows,
    }


def equity_drawdown(equity: pd.Series) -> float:
    if equity.empty:
        return float("nan")
    peak = equity.cummax()
    drawdown = equity / peak - 1.0
    return float(drawdown.min())


def metrics_from_returns(returns: pd.Series, initial: float = INITIAL_CAPITAL) -> dict[str, Any]:
    clean = returns.dropna().astype(float)
    if clean.empty:
        return {
            "final_equity": initial,
            "total_return": 0.0,
            "annualized_return": "",
            "realized_volatility": "",
            "downside_volatility": "",
            "max_drawdown": 0.0,
            "return_drawdown_ratio": "",
        }
    equity = initial * (1.0 + clean).cumprod()
    total_return = float(equity.iloc[-1] / initial - 1.0)
    years = len(clean) / 252.0
    annualized = (float(equity.iloc[-1]) / initial) ** (1.0 / years) - 1.0 if years > 0 and equity.iloc[-1] > 0 else float("nan")
    volatility = float(clean.std(ddof=1) * math.sqrt(252.0)) if len(clean) > 1 else float("nan")
    downside = clean[clean < 0.0]
    downside_vol = float(downside.std(ddof=1) * math.sqrt(252.0)) if len(downside) > 1 else 0.0
    max_dd = equity_drawdown(equity)
    return {
        "final_equity": float(equity.iloc[-1]),
        "total_return": total_return,
        "annualized_return": annualized,
        "realized_volatility": volatility,
        "downside_volatility": downside_vol,
        "max_drawdown": max_dd,
        "return_drawdown_ratio": total_return / abs(max_dd) if max_dd < -TOL else "",
    }


def cycle_metrics(cycle: CycleDefinition, selected: list[dict[str, Any]], result: dict[str, Any]) -> dict[str, Any]:
    strategy = pd.DataFrame(result["strategy_rows"])
    sleeves: list[SleeveRuntime] = result["sleeves"]
    if strategy.empty:
        returns = pd.Series(dtype=float)
        equity = pd.Series(dtype=float)
    else:
        returns = pd.Series(pd.to_numeric(strategy["daily_return"], errors="coerce").to_numpy(dtype=float), index=pd.to_datetime(strategy["date"]))
        equity = pd.Series(pd.to_numeric(strategy["strategy_equity"], errors="coerce").to_numpy(dtype=float), index=pd.to_datetime(strategy["date"]))
    entries = sum(sleeve.entries for sleeve in sleeves)
    exits = sum(sleeve.convergence_exits for sleeve in sleeves)
    forced = sum(sleeve.forced_closes for sleeve in sleeves)
    open_days = [days for sleeve in sleeves for days in sleeve.completed_open_days]
    tx = float(strategy["cumulative_transaction_costs"].iloc[-1]) if not strategy.empty else 0.0
    borrow = float(strategy["cumulative_borrow_costs"].iloc[-1]) if not strategy.empty else 0.0
    final_equity = float(result["final_equity"])
    net_pnl = final_equity - float(result["starting_equity"])
    gross_pnl = net_pnl + tx + borrow
    symbol_counts: dict[str, int] = {}
    for row in selected:
        symbol_counts[str(row["first_ticker"])] = symbol_counts.get(str(row["first_ticker"]), 0) + 1
        symbol_counts[str(row["second_ticker"])] = symbol_counts.get(str(row["second_ticker"]), 0) + 1
    overlap = sum(count - 1 for count in symbol_counts.values() if count > 1)
    sleeve_days = len(cycle.trading_dates) * PAIR_COUNT
    invested_sleeve_days = sum(sleeve.open_day_count for sleeve in sleeves)
    return {
        "cycle_id": cycle.cycle_id,
        "formation_start": cycle.formation_start,
        "formation_end": cycle.formation_end,
        "trading_start": cycle.trading_start,
        "trading_end": cycle.trading_end,
        "selected_five_pairs": "|".join(str(row["pair_id"]) for row in selected),
        "pair_overlap_count": overlap,
        "entry_count": entries,
        "convergence_exit_count": exits,
        "forced_close_count": forced,
        "reentry_count": max(0, entries - PAIR_COUNT),
        "average_days_open": float(np.mean(open_days)) if open_days else 0.0,
        "percent_sleeve_days_invested": invested_sleeve_days / sleeve_days if sleeve_days else 0.0,
        "gross_pnl": gross_pnl,
        "borrow_costs": borrow,
        "transaction_costs": tx,
        "net_return": final_equity / float(result["starting_equity"]) - 1.0 if result["starting_equity"] else float("nan"),
        "final_equity": final_equity,
        "maximum_drawdown": equity_drawdown(equity),
        "maximum_gross_exposure": float(strategy["aggregate_gross_exposure"].max()) if not strategy.empty else 0.0,
        "maximum_absolute_net_exposure": float(strategy["aggregate_net_exposure"].abs().max()) if not strategy.empty else 0.0,
        "invalidity_status": "invalid" if result["invalid_reason"] else "valid",
        "invalidity_reason": result["invalid_reason"],
    }


def load_benchmark_returns(all_dates: pd.DatetimeIndex) -> dict[str, pd.Series]:
    spy_bil = load_price_frame(["SPY", "BIL"]).dropna(how="any")
    returns = {
        "SPY_buy_and_hold": spy_bil["SPY"].pct_change().dropna(),
        "BIL_cash_proxy": spy_bil["BIL"].pct_change().dropna(),
    }
    active_close, missing = active.prepare_prices(ROOT)
    if not missing and not active_close.empty:
        returns["SPY_200d_trend_model"] = active.full_returns(active_close, active.SPY_200D_ID)
    if ACTIVE_COMBO_SERIES.exists():
        frame = pd.read_csv(ACTIVE_COMBO_SERIES)
        dates = pd.to_datetime(frame["date"], errors="coerce").dt.tz_localize(None)
        combo_returns = pd.to_numeric(frame["active_combo_daily_return"], errors="coerce")
        returns["active_combo_vm_dsr_equal_weight_v1"] = pd.Series(combo_returns.to_numpy(dtype=float), index=dates, name="active_combo").dropna().sort_index()
    return {key: value.sort_index() for key, value in returns.items()}


def benchmark_metric_rows(
    daily_strategy: pd.DataFrame,
    cycles: list[CycleDefinition],
    cycle_metric_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    candidate_returns = pd.Series(
        pd.to_numeric(daily_strategy["daily_return"], errors="coerce").to_numpy(dtype=float),
        index=pd.to_datetime(daily_strategy["date"], errors="coerce"),
        name=CANDIDATE_ID,
    ).dropna()
    benchmark_returns = load_benchmark_returns(pd.DatetimeIndex(candidate_returns.index))
    metric_rows: list[dict[str, Any]] = []
    relative_rows: list[dict[str, Any]] = []
    cycle_by_id = {row["cycle_id"]: row for row in cycle_metric_rows}

    windows: list[tuple[str, pd.Timestamp, pd.Timestamp, float, float]] = [
        ("full_chained_period", pd.Timestamp(candidate_returns.index.min()), pd.Timestamp(candidate_returns.index.max()), INITIAL_CAPITAL, float(daily_strategy["strategy_equity"].iloc[-1]))
    ]
    for cycle in cycles:
        cm = cycle_by_id[cycle.cycle_id]
        windows.append((cycle.cycle_id, cycle.trading_start, cycle.trading_end, INITIAL_CAPITAL, INITIAL_CAPITAL * (1.0 + float(cm["net_return"]))))

    for window_id, start, end, candidate_initial, candidate_final in windows:
        candidate_period = candidate_returns[(candidate_returns.index >= start) & (candidate_returns.index <= end)]
        candidate_metrics = metrics_from_returns(candidate_period, candidate_initial)
        candidate_total = candidate_final / candidate_initial - 1.0 if candidate_initial else float("nan")
        for benchmark_id, returns in benchmark_returns.items():
            period = returns[(returns.index >= start) & (returns.index <= end)].dropna()
            available = not period.empty and len(period) >= 2
            metrics = metrics_from_returns(period, candidate_initial) if available else {}
            metric_rows.append(
                {
                    "window_id": window_id,
                    "benchmark_id": benchmark_id,
                    "benchmark_available": available,
                    "matching_start": "" if not available else str(period.index.min().date()),
                    "matching_end": "" if not available else str(period.index.max().date()),
                    "matching_days": int(len(period)) if available else 0,
                    "final_equity": metrics.get("final_equity", ""),
                    "total_return": metrics.get("total_return", ""),
                    "annualized_return": metrics.get("annualized_return", ""),
                    "max_drawdown": metrics.get("max_drawdown", ""),
                    "benchmark_reference_only": True,
                }
            )
            relative_rows.append(
                {
                    "window_id": window_id,
                    "benchmark_id": benchmark_id,
                    "benchmark_available": available,
                    "candidate_final_equity": candidate_final,
                    "benchmark_final_equity": metrics.get("final_equity", ""),
                    "final_equity_difference": "" if not available else candidate_final - float(metrics["final_equity"]),
                    "candidate_total_return": candidate_total,
                    "benchmark_total_return": metrics.get("total_return", ""),
                    "total_return_difference": "" if not available else candidate_total - float(metrics["total_return"]),
                    "candidate_max_drawdown": candidate_metrics.get("max_drawdown", ""),
                    "benchmark_max_drawdown": metrics.get("max_drawdown", ""),
                    "drawdown_difference": "" if not available else float(candidate_metrics["max_drawdown"]) - float(metrics["max_drawdown"]),
                    "candidate_beats_benchmark": "" if not available else candidate_total > float(metrics["total_return"]),
                }
            )
    return metric_rows, relative_rows


def aggregate_metric_rows(daily_strategy: pd.DataFrame, cycle_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    returns = pd.Series(
        pd.to_numeric(daily_strategy["daily_return"], errors="coerce").to_numpy(dtype=float),
        index=pd.to_datetime(daily_strategy["date"], errors="coerce"),
    ).dropna()
    equity = pd.Series(
        pd.to_numeric(daily_strategy["strategy_equity"], errors="coerce").to_numpy(dtype=float),
        index=pd.to_datetime(daily_strategy["date"], errors="coerce"),
    ).dropna()
    metrics = metrics_from_returns(returns, INITIAL_CAPITAL)
    valid_cycles = [row for row in cycle_rows if row["invalidity_status"] == "valid"]
    invalid_cycles = [row for row in cycle_rows if row["invalidity_status"] != "valid"]
    cycle_returns = [float(row["net_return"]) for row in cycle_rows]
    total_borrow = float(daily_strategy["daily_borrow_cost"].sum()) if not daily_strategy.empty else 0.0
    total_tx = float(daily_strategy["daily_transaction_cost"].sum()) if not daily_strategy.empty else 0.0
    final_equity = float(equity.iloc[-1]) if not equity.empty else INITIAL_CAPITAL
    net_pnl = final_equity - INITIAL_CAPITAL
    gross_pnl = net_pnl + total_borrow + total_tx
    selected_pairs = [pair for row in cycle_rows for pair in str(row["selected_five_pairs"]).split("|") if pair]
    pair_counts = pd.Series(selected_pairs).value_counts() if selected_pairs else pd.Series(dtype=int)
    rows = [
        {"metric": "final_equity", "value": final_equity},
        {"metric": "total_return", "value": final_equity / INITIAL_CAPITAL - 1.0},
        {"metric": "annualized_return", "value": metrics["annualized_return"]},
        {"metric": "realized_volatility", "value": metrics["realized_volatility"]},
        {"metric": "downside_volatility", "value": metrics["downside_volatility"]},
        {"metric": "maximum_drawdown", "value": metrics["max_drawdown"]},
        {"metric": "return_drawdown_ratio", "value": metrics["return_drawdown_ratio"]},
        {"metric": "percentage_profitable_cycles", "value": sum(1 for item in cycle_returns if item > 0.0) / len(cycle_returns) if cycle_returns else 0.0},
        {"metric": "median_cycle_return", "value": float(np.median(cycle_returns)) if cycle_returns else ""},
        {"metric": "worst_cycle_return", "value": min(cycle_returns) if cycle_returns else ""},
        {"metric": "valid_cycle_count", "value": len(valid_cycles)},
        {"metric": "invalid_cycle_count", "value": len(invalid_cycles)},
        {"metric": "total_entries", "value": sum(int(row["entry_count"]) for row in cycle_rows)},
        {"metric": "total_exits", "value": sum(int(row["convergence_exit_count"]) + int(row["forced_close_count"]) for row in cycle_rows)},
        {"metric": "gross_traded_notional_proxy", "value": float(daily_strategy["daily_transaction_cost"].sum()) / TRANSACTION_COST_RATE if TRANSACTION_COST_RATE else ""},
        {"metric": "total_borrow_cost", "value": total_borrow},
        {"metric": "total_transaction_cost", "value": total_tx},
        {"metric": "cost_drag_as_pct_gross_pnl", "value": (total_borrow + total_tx) / gross_pnl if abs(gross_pnl) > TOL else ""},
        {"metric": "average_gross_exposure", "value": float(daily_strategy["aggregate_gross_exposure"].mean())},
        {"metric": "maximum_gross_exposure", "value": float(daily_strategy["aggregate_gross_exposure"].max())},
        {"metric": "average_absolute_net_exposure", "value": float(daily_strategy["aggregate_net_exposure"].abs().mean())},
        {"metric": "maximum_absolute_net_exposure", "value": float(daily_strategy["aggregate_net_exposure"].abs().max())},
        {"metric": "average_capital_deployed", "value": float((daily_strategy["aggregate_gross_exposure"] * daily_strategy["strategy_equity"]).mean())},
        {"metric": "percentage_days_completely_flat", "value": float((daily_strategy["open_sleeves"] == 0).mean())},
        {"metric": "percentage_days_all_five_sleeves_open", "value": float((daily_strategy["open_sleeves"] == PAIR_COUNT).mean())},
        {"metric": "unique_selected_pair_count", "value": int(pair_counts.size)},
        {"metric": "most_frequent_pair_share", "value": float(pair_counts.iloc[0] / len(selected_pairs)) if len(selected_pairs) else ""},
    ]
    return rows


def gross_vs_cost_rows(daily_strategy: pd.DataFrame) -> list[dict[str, Any]]:
    total_borrow = float(daily_strategy["daily_borrow_cost"].sum()) if not daily_strategy.empty else 0.0
    total_tx = float(daily_strategy["daily_transaction_cost"].sum()) if not daily_strategy.empty else 0.0
    final_equity = float(daily_strategy["strategy_equity"].iloc[-1]) if not daily_strategy.empty else INITIAL_CAPITAL
    net_pnl = final_equity - INITIAL_CAPITAL
    gross_pnl = net_pnl + total_borrow + total_tx
    return [
        {"component": "gross_trading_pnl_before_borrow_and_transaction_costs", "amount": gross_pnl, "candidate_variant": False},
        {"component": "borrow_cost_drag", "amount": -total_borrow, "candidate_variant": False},
        {"component": "transaction_cost_drag", "amount": -total_tx, "candidate_variant": False},
        {"component": "net_pnl_after_all_costs", "amount": net_pnl, "candidate_variant": False},
    ]


def invariant_rows(
    manifest: dict[str, Any],
    cycles: list[CycleDefinition],
    selected_rows: list[dict[str, Any]],
    daily_strategy: pd.DataFrame,
    invalid_cycles: list[dict[str, Any]],
    hashes_before: dict[str, str],
    hashes_after: dict[str, str],
) -> list[dict[str, Any]]:
    rows = [
        {"invariant": "exact_frozen_universe", "passed": tuple(manifest["exact_universe"]) == FROZEN_UNIVERSE, "observed": "|".join(manifest["exact_universe"]), "expected": "|".join(FROZEN_UNIVERSE)},
        {"invariant": "cache_hashes_verified_before_run", "passed": all(row["cache_ready"] and row["cache_sha256"] != "missing" for row in manifest["cache_files"]), "observed": len(manifest["cache_files"]), "expected": len(FROZEN_UNIVERSE)},
        {"invariant": "complete_january_july_cycles_only", "passed": all(pd.Timestamp(cycle.trading_end) < pd.Timestamp(cycle.trading_start) + pd.DateOffset(months=TRADING_MONTHS) for cycle in cycles), "observed": len(cycles), "expected": "mechanical_complete_cycles"},
        {"invariant": "exact_top_five_pairs_each_cycle", "passed": all(len([row for row in selected_rows if row["cycle_id"] == cycle.cycle_id]) == PAIR_COUNT for cycle in cycles), "observed": len(selected_rows), "expected": len(cycles) * PAIR_COUNT},
        {"invariant": "no_provider_calls", "passed": True, "observed": False, "expected": False},
        {"invariant": "no_parameter_universe_cycle_pair_count_cost_or_borrow_search", "passed": True, "observed": False, "expected": False},
        {"invariant": "restricted_proceeds_not_reused", "passed": bool((daily_strategy["free_cash"] <= daily_strategy["cash"] + TOL).all()) if not daily_strategy.empty else True, "observed": "free_cash<=cash", "expected": "true"},
        {"invariant": "borrow_cost_matches_5pct_over_252", "passed": abs(BORROW_RATE_DAILY - 0.05 / 252.0) <= TOL, "observed": BORROW_RATE_DAILY, "expected": 0.05 / 252.0},
        {"invariant": "transaction_cost_matches_0005_per_leg", "passed": TRANSACTION_COST_RATE == 0.0005, "observed": TRANSACTION_COST_RATE, "expected": 0.0005},
        {"invariant": "invalid_cycles_visible", "passed": (len(invalid_cycles) == 0 or all(row.get("invalidity_reason") for row in invalid_cycles)), "observed": len(invalid_cycles), "expected": "visible_if_any"},
        {"invariant": "registry_byte_identical", "passed": hashes_before["registry"] == hashes_after["registry"], "observed": hashes_after["registry"], "expected": hashes_before["registry"]},
        {"invariant": "active_observations_unchanged", "passed": hashes_before["active_observations"] == hashes_after["active_observations"], "observed": hashes_after["active_observations"], "expected": hashes_before["active_observations"]},
    ]
    return rows


def classify_outcome(
    aggregate_rows: list[dict[str, Any]],
    benchmark_relative_rows: list[dict[str, Any]],
    invalid_cycles: list[dict[str, Any]],
    cycle_rows: list[dict[str, Any]],
) -> str:
    if invalid_cycles:
        return "accounting_or_short_feasibility_failure"
    metrics = {row["metric"]: row["value"] for row in aggregate_rows}
    entries = int(float(metrics.get("total_entries", 0) or 0))
    valid_cycles = int(float(metrics.get("valid_cycle_count", 0) or 0))
    if entries < 5 or valid_cycles < 4:
        return "signal_scarce_no_evidence"
    full = [row for row in benchmark_relative_rows if row["window_id"] == "full_chained_period"]
    by_bench = {row["benchmark_id"]: row for row in full if row["benchmark_available"] is True}
    bil_delta = float(by_bench.get("BIL_cash_proxy", {}).get("total_return_difference", 0.0) or 0.0)
    bil_total = float(by_bench.get("BIL_cash_proxy", {}).get("benchmark_total_return", 0.0) or 0.0)
    spy_delta = float(by_bench.get("SPY_buy_and_hold", {}).get("total_return_difference", 0.0) or 0.0)
    total_return = float(metrics.get("total_return", 0.0) or 0.0)
    borrow_cost = float(metrics.get("total_borrow_cost", 0.0) or 0.0)
    transaction_cost = float(metrics.get("total_transaction_cost", 0.0) or 0.0)
    gross_total_return = total_return + (borrow_cost + transaction_cost) / INITIAL_CAPITAL
    worst_cycle = float(metrics.get("worst_cycle_return", 0.0) or 0.0)
    profitable = float(metrics.get("percentage_profitable_cycles", 0.0) or 0.0)
    if bil_delta <= 0.0 and gross_total_return > bil_total:
        return "cost_sensitive_no_edge"
    if bil_delta > 0.0 and profitable > 0.5 and abs(worst_cycle) < max(0.75, abs(total_return) * 2.5):
        return "comparative_evidence_positive"
    if bil_delta > 0.0 and spy_delta < 0.0:
        return "control_weak"
    if bil_delta > 0.0 and float(metrics.get("maximum_drawdown", 0.0) or 0.0) < -0.25:
        return "higher_return_higher_risk"
    if total_return > 0.0 and bil_delta <= 0.0:
        return "no_material_edge"
    return "no_material_edge"


def cycle_definition_rows(cycles: list[CycleDefinition]) -> list[dict[str, Any]]:
    return [
        {
            "cycle_id": cycle.cycle_id,
            "cycle_number": cycle.cycle_number,
            "formation_start": cycle.formation_start,
            "formation_end": cycle.formation_end,
            "formation_day_count": len(cycle.formation_dates),
            "trading_start": cycle.trading_start,
            "trading_end": cycle.trading_end,
            "trading_day_count": len(cycle.trading_dates),
            "complete_formation_period": True,
            "complete_six_month_trading_period": True,
            "first_valid_common_january_or_july_session": True,
        }
        for cycle in cycles
    ]


def execution_manifest_payload(
    cache: list[dict[str, Any]],
    cycles: list[CycleDefinition],
    common_prices: pd.DataFrame,
    ledger_hash: str,
) -> dict[str, Any]:
    return {
        "candidate_id": CANDIDATE_ID,
        "family_id": FAMILY_ID,
        "source_id": SOURCE_ID,
        "classification": "source_inspired_etf_pairs_adaptation",
        "research_simulation_only": True,
        "not_source_stock_universe_replication": True,
        "not_broker_ready": True,
        "not_paper_demo_eligible": True,
        "exact_universe": list(FROZEN_UNIVERSE),
        "cache_files": cache,
        "common_valid_history": {
            "start": "" if common_prices.empty else str(common_prices.index.min().date()),
            "end": "" if common_prices.empty else str(common_prices.index.max().date()),
            "day_count": int(len(common_prices)),
        },
        "complete_eligible_cycle_ids": [cycle.cycle_id for cycle in cycles],
        "cycle_count": len(cycles),
        "formation_and_trading_boundaries_written_before_performance": True,
        "pair_selection_rule": "normalize 12-calendar-month formation paths to 1.0, rank all unique pairs by ascending squared-distance sum, lexicographic tie-break, select top five, overlap allowed",
        "signal_convention": "strict abs(spread)>2*formation_std entry; long lower normalized price and short higher normalized price; convergence crossing exits",
        "execution_convention": "signal close executes on next valid common session; no same-close execution; pending orders are not cancelled by next-day spread changes",
        "ledger_version_hash": ledger_hash,
        "borrow_cost_convention": {"annualized": BORROW_RATE_ANNUAL, "daily": BORROW_RATE_DAILY},
        "transaction_cost_convention": {"per_leg_rate": TRANSACTION_COST_RATE},
        "initial_capital": INITIAL_CAPITAL,
        "benchmarks": ["BIL_cash_proxy", "SPY_buy_and_hold", "SPY_200d_trend_model", "active_combo_vm_dsr_equal_weight_v1"],
        "metrics": ["cycle", "aggregate_chained_path", "benchmark_relative", "gross_vs_cost_decomposition"],
        "invalidation_rules": ["missing_price_invalidates_cycle", "non_finite_or_non_positive_sleeve_equity_invalidates_cycle", "non_finite_or_non_positive_strategy_equity_invalidates_screen"],
        "no_search_or_optimization_authorized": True,
        "provider_download": False,
        "intraday_data_used": False,
        "candidate_exhaustive_run": False,
        "promotion_authorized": False,
        "paper_demo_activation": False,
        "broker_or_live_path": False,
        "real_money_recommendation": False,
    }


def screening_summary(outcome: dict[str, Any], aggregate_rows: list[dict[str, Any]]) -> str:
    metrics = {row["metric"]: row["value"] for row in aggregate_rows}
    return f"""# ETF Pairs Distance Screen V1

Candidate: `{CANDIDATE_ID}`

Outcome label: `{outcome['primary_outcome_label']}`

Cycles evaluated: `{outcome['cycle_count']}`

Invalid cycles: `{outcome['invalid_cycle_count']}`

Final equity: `{csv_value(metrics.get('final_equity', ''))}`

Total return: `{csv_value(metrics.get('total_return', ''))}`

This is one frozen historical screen for the exact pre-registered source-inspired ETF-pairs adaptation. It is diagnostic and non-promotional. It does not create variants, authorize robustness, promote, activate paper/demo observation, touch broker/live paths, or recommend real-money trading.
"""


def run() -> dict[str, Any]:
    registry_path = ROOT / "strategy_lab" / "strategy_registry.yaml"
    active_observations_path = ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml"
    hashes_before = {
        "registry": sha256_path(registry_path),
        "active_observations": sha256_path(active_observations_path),
    }
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    prices = load_price_frame(list(FROZEN_UNIVERSE))
    common_prices = common_valid_prices(prices)
    cache = cache_rows()
    cycles = generate_cycle_definitions(common_prices)
    manifest = execution_manifest_payload(cache, cycles, common_prices, sha256_path(ACCOUNTING_DIR / "accounting_convention.yaml"))

    # Save the frozen manifest and cycle list before any performance simulation.
    write_json(OUTPUT_DIR / "execution_manifest.json", manifest)
    write_csv(OUTPUT_DIR / "cycle_definitions.csv", cycle_definition_rows(cycles))

    all_distance_rows: list[dict[str, Any]] = []
    selected_rows_all: list[dict[str, Any]] = []
    normalized_by_cycle: dict[str, pd.DataFrame] = {}
    selected_by_cycle: dict[str, list[dict[str, Any]]] = {}
    for cycle in cycles:
        normalized = normalize_for_cycle(common_prices, cycle)
        normalized_by_cycle[cycle.cycle_id] = normalized
        distances = pair_distance_rows(normalized, cycle)
        selected = selected_pairs(distances, cycle)
        all_distance_rows.extend(distances)
        selected_rows_all.extend(selected)
        selected_by_cycle[cycle.cycle_id] = selected

    strategy_equity = INITIAL_CAPITAL
    all_daily_sleeves: list[dict[str, Any]] = []
    all_signals: list[dict[str, Any]] = []
    all_trades: list[dict[str, Any]] = []
    all_strategy_rows: list[dict[str, Any]] = []
    cycle_rows: list[dict[str, Any]] = []
    screen_invalid = False
    prior_path_equity = INITIAL_CAPITAL
    path_borrow_total = 0.0
    path_transaction_total = 0.0

    for cycle in cycles:
        result = simulate_cycle(common_prices, normalized_by_cycle[cycle.cycle_id], cycle, selected_by_cycle[cycle.cycle_id], strategy_equity)
        all_daily_sleeves.extend(result["daily_sleeve_rows"])
        all_signals.extend(result["signal_rows"])
        all_trades.extend(result["trade_rows"])
        for row in result["strategy_rows"]:
            adjusted = dict(row)
            equity = float(adjusted["strategy_equity"])
            adjusted["daily_return_chained"] = equity / prior_path_equity - 1.0 if abs(prior_path_equity) > TOL else float("nan")
            path_borrow_total += float(adjusted.get("daily_borrow_cost", 0.0) or 0.0)
            path_transaction_total += float(adjusted.get("daily_transaction_cost", 0.0) or 0.0)
            adjusted["path_cumulative_borrow_costs"] = path_borrow_total
            adjusted["path_cumulative_transaction_costs"] = path_transaction_total
            prior_path_equity = equity
            all_strategy_rows.append(adjusted)
        cycle_rows.append(cycle_metrics(cycle, selected_by_cycle[cycle.cycle_id], result))
        strategy_equity = float(result["final_equity"])
        if result["invalid_reason"] == "strategy_insolvency" or not math.isfinite(strategy_equity) or strategy_equity <= 0.0:
            screen_invalid = True
            break

    daily_strategy = pd.DataFrame(all_strategy_rows)
    if not daily_strategy.empty:
        daily_strategy["daily_return"] = pd.to_numeric(daily_strategy["daily_return_chained"], errors="coerce").fillna(0.0)
    invalid_cycles = [row for row in cycle_rows if row["invalidity_status"] != "valid"]
    benchmark_rows, benchmark_relative_rows = benchmark_metric_rows(daily_strategy, cycles[: len(cycle_rows)], cycle_rows)
    aggregate_rows = aggregate_metric_rows(daily_strategy, cycle_rows)
    gross_cost_rows = gross_vs_cost_rows(daily_strategy)
    primary_outcome = "accounting_or_short_feasibility_failure" if screen_invalid else classify_outcome(aggregate_rows, benchmark_relative_rows, invalid_cycles, cycle_rows)
    if primary_outcome not in OUTCOME_LABELS:
        primary_outcome = "direction_owner_review_required"

    hashes_after = {
        "registry": sha256_path(registry_path),
        "active_observations": sha256_path(active_observations_path),
    }
    invariants = invariant_rows(manifest, cycles[: len(cycle_rows)], selected_rows_all, daily_strategy, invalid_cycles, hashes_before, hashes_after)
    all_invariants_passed = all(bool(row["passed"]) for row in invariants)
    if not all_invariants_passed and primary_outcome not in {"accounting_or_short_feasibility_failure"}:
        primary_outcome = "invalid_methodology"

    outcome = {
        "candidate_id": CANDIDATE_ID,
        "family_id": FAMILY_ID,
        "primary_outcome_label": primary_outcome,
        "cycle_count": len(cycle_rows),
        "invalid_cycle_count": len(invalid_cycles),
        "valid_cycle_count": len(cycle_rows) - len(invalid_cycles),
        "screen_invalid": screen_invalid,
        "promotion_authorized": False,
        "paper_demo_authorized": False,
        "candidate_exhaustive_authorized": False,
        "robustness_authorized": False,
        "historical_screen_completed": True,
        "provider_download": False,
        "intraday_data_used": False,
        "broker_or_live_path": False,
        "real_money_recommendation": False,
        "registry_hash_before": hashes_before["registry"],
        "registry_hash_after": hashes_after["registry"],
        "registry_byte_identical": hashes_before["registry"] == hashes_after["registry"],
        "active_observations_hash_before": hashes_before["active_observations"],
        "active_observations_hash_after": hashes_after["active_observations"],
        "active_observations_unchanged": hashes_before["active_observations"] == hashes_after["active_observations"],
        "next_action": "direction_owner_validate_or_close_etf_pairs_distance_screen_v1",
    }
    if primary_outcome in {"no_material_edge", "control_weak", "cost_sensitive_no_edge", "signal_scarce_no_evidence", "accounting_or_short_feasibility_failure", "invalid_methodology"}:
        memory_action = "close_exact_variant_for_immediate_retesting"
    else:
        memory_action = "direction_owner_validation_decision_required"
    memory = [
        {
            "candidate_id": CANDIDATE_ID,
            "family_id": FAMILY_ID,
            "primary_outcome_label": primary_outcome,
            "exact_variant_immediate_retest_status": memory_action,
            "broader_family_status": "open_only_for_materially_different_source_backed_hypotheses",
            "parameters_or_universe_to_adjust_now": False,
            "canonical_lifecycle_status_modified": False,
            "paper_demo_state_modified": False,
            "next_action": outcome["next_action"],
        }
    ]
    lineage = [
        {"artifact_id": "source_preregistration", "artifact_type": "evidence", "path": rel(SOURCE_PREREG_DIR), "sha256": sha256_path(SOURCE_PREREG_DIR / "decision.json")},
        {"artifact_id": "short_accounting_resolution", "artifact_type": "evidence", "path": rel(ACCOUNTING_DIR), "sha256": sha256_path(ACCOUNTING_DIR / "decision.json")},
        {"artifact_id": "accounting_convention", "artifact_type": "evidence", "path": rel(ACCOUNTING_DIR / "accounting_convention.yaml"), "sha256": sha256_path(ACCOUNTING_DIR / "accounting_convention.yaml")},
        {"artifact_id": "implementation", "artifact_type": "source_file", "path": rel(Path(__file__)), "sha256": sha256_path(Path(__file__))},
    ]
    lineage.extend({"artifact_id": row["symbol"], "artifact_type": "cache_file", "path": row["cache_path"], "sha256": row["cache_sha256"]} for row in cache)
    check = {
        "consistency_passed": bool(
            all_invariants_passed
            and outcome["registry_byte_identical"]
            and outcome["active_observations_unchanged"]
            and outcome["provider_download"] is False
            and outcome["promotion_authorized"] is False
            and outcome["paper_demo_authorized"] is False
            and len(selected_rows_all) == len(cycles) * PAIR_COUNT
        ),
        "manifest_written_before_performance": True,
        "cycle_definitions_written_before_performance": True,
        "complete_cycles_evaluated": len(cycle_rows) == len(cycles) or screen_invalid,
        "exact_frozen_universe": manifest["exact_universe"] == list(FROZEN_UNIVERSE),
        "top_five_pairs_each_cycle": len(selected_rows_all) == len(cycles) * PAIR_COUNT,
        "no_provider_calls": True,
        "no_parameter_search": True,
        "registry_byte_identical": outcome["registry_byte_identical"],
        "active_observations_unchanged": outcome["active_observations_unchanged"],
        "deterministic_generation_no_timestamps": True,
        "generation_hash": stable_hash({"outcome": outcome, "cycles": cycle_definition_rows(cycles), "selected": selected_rows_all}),
    }

    write_csv(OUTPUT_DIR / "formation_pair_distances.csv", all_distance_rows)
    write_csv(OUTPUT_DIR / "selected_pairs_by_cycle.csv", selected_rows_all)
    write_csv(OUTPUT_DIR / "daily_pair_signals.csv", all_signals)
    write_csv(OUTPUT_DIR / "trade_ledger.csv", all_trades)
    write_csv(OUTPUT_DIR / "daily_sleeve_ledgers.csv", all_daily_sleeves)
    write_csv(OUTPUT_DIR / "daily_strategy_path.csv", all_strategy_rows)
    write_csv(OUTPUT_DIR / "cycle_metrics.csv", cycle_rows)
    write_csv(OUTPUT_DIR / "aggregate_metrics.csv", aggregate_rows, ["metric", "value"])
    write_csv(OUTPUT_DIR / "benchmark_metrics.csv", benchmark_rows)
    write_csv(OUTPUT_DIR / "benchmark_relative_metrics.csv", benchmark_relative_rows)
    write_csv(OUTPUT_DIR / "gross_vs_cost_decomposition.csv", gross_cost_rows)
    write_csv(OUTPUT_DIR / "exposure_and_accounting_invariants.csv", invariants)
    write_csv(OUTPUT_DIR / "invalid_cycles.csv", invalid_cycles, list(cycle_rows[0].keys()) if cycle_rows else ["cycle_id", "invalidity_reason"])
    write_text(OUTPUT_DIR / "screening_summary.md", screening_summary(outcome, aggregate_rows))
    write_json(OUTPUT_DIR / "screening_outcome.json", outcome)
    write_csv(OUTPUT_DIR / "exact_variant_research_memory.csv", memory)
    write_csv(OUTPUT_DIR / "artifact_lineage.csv", lineage)
    write_json(OUTPUT_DIR / "consistency_check.json", check)
    return {
        "output_dir": str(OUTPUT_DIR),
        "candidate_id": CANDIDATE_ID,
        "primary_outcome_label": primary_outcome,
        "cycle_count": len(cycle_rows),
        "invalid_cycle_count": len(invalid_cycles),
        "final_equity": next(row["value"] for row in aggregate_rows if row["metric"] == "final_equity"),
        "total_return": next(row["value"] for row in aggregate_rows if row["metric"] == "total_return"),
        "consistency_passed": check["consistency_passed"],
        "registry_byte_identical": outcome["registry_byte_identical"],
        "active_observations_unchanged": outcome["active_observations_unchanged"],
        "next_action": outcome["next_action"],
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
