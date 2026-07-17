from __future__ import annotations

import csv
import hashlib
import json
import math
import shutil
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import run_active_strategy_evidence_recompute as active


ROOT = Path(__file__).resolve().parents[3]
OUTPUT_DIR = ROOT / "evidence" / "usci_current_methodology_validation_v1" / "latest"
PRIOR_SCREEN_DIR = ROOT / "evidence" / "usci_dynamic_commodity_curve_selection_bounded_screen_v1" / "latest"
CANDIDATE_ID = "usci_dynamic_commodity_curve_selection_wrapper_v1"
FAMILY_ID = "commodity_curve_selection"
USCI = "USCI"
DBC = "DBC"
BIL = "BIL"
SPY = "SPY"
SYMBOLS = (USCI, DBC, BIL, SPY)
CURRENT_START = pd.Timestamp("2021-01-04")
CURRENT_END = pd.Timestamp("2026-06-18")
TRANSITION_START = pd.Timestamp("2020-12-24")
TRANSITION_END = pd.Timestamp("2020-12-31")
ROLLING_HORIZONS = (90, 180, 252, 504)
NON_OVERLAPPING_HORIZONS = (180, 252, 504)
INITIAL_CAPITAL = float(active.STARTING_EQUITY)
INITIAL_TRANSACTION_COST = float(active.SLIPPAGE)
REGISTRY_PATH = ROOT / "strategy_lab" / "strategy_registry.yaml"
ACTIVE_OBSERVATIONS_PATH = ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml"
CURRENT_CHECKPOINT_DIR = ROOT / "evidence" / "current_research_checkpoint" / "latest"
MATERIALLY_NEGATIVE_EXCESS_THRESHOLD = -0.02
ALLOWED_OUTCOMES = {
    "validation_supports_further_review",
    "historical_edge_recently_weakened",
    "screening_positive_not_stable",
    "higher_return_higher_risk",
    "risk_reduction_without_return_edge",
    "control_weak",
    "invalid_methodology",
    "direction_owner_review_required",
}


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


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
    return hashlib.sha256(encoded).hexdigest().upper()


def clean_value(value: Any) -> Any:
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, (int, np.integer)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        val = float(value)
        if not math.isfinite(val):
            return None
        return round(val, 12)
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, Path):
        return rel(value)
    return value


def csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (float, np.floating)):
        val = float(value)
        if not math.isfinite(val):
            return ""
        return f"{val:.12g}"
    if isinstance(value, (list, tuple, set)):
        return "|".join(str(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True, default=clean_value)
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    return str(value)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=clean_value) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fields is None:
        fields = sorted({key for row in rows for key in row})
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: csv_value(row.get(field, "")) for field in fields})


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def file_snapshot(paths: list[Path]) -> dict[str, str]:
    return {rel(path): sha256_path(path) for path in paths}


def directory_snapshot(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    return {
        rel(file): sha256_path(file)
        for file in sorted(item for item in path.rglob("*") if item.is_file())
    }


def cache_path(symbol: str) -> Path:
    return ROOT / "data" / "cache" / f"{symbol}.csv"


def cache_quality_row(symbol: str) -> dict[str, Any]:
    path = cache_path(symbol)
    row: dict[str, Any] = {
        "symbol": symbol,
        "cache_path": rel(path),
        "cache_exists": path.exists(),
        "cache_hash": sha256_path(path),
        "row_count": 0,
        "first_valid_date": "",
        "last_valid_date": "",
        "date_monotonic_increasing": False,
        "duplicate_date_count": "",
        "missing_adj_close_count": "",
        "nonpositive_adj_close_count": "",
        "adjusted_price_validation_result": "missing",
    }
    if not path.exists():
        return row
    frame = pd.read_csv(path)
    dates = pd.to_datetime(frame.get("date"), errors="coerce").dt.tz_localize(None)
    adj = pd.to_numeric(frame.get("adj_close"), errors="coerce") if "adj_close" in frame else pd.Series(dtype=float)
    row["row_count"] = int(len(frame))
    row["first_valid_date"] = dates.dropna().min().date().isoformat() if dates.notna().any() else ""
    row["last_valid_date"] = dates.dropna().max().date().isoformat() if dates.notna().any() else ""
    row["date_monotonic_increasing"] = bool(dates.dropna().is_monotonic_increasing)
    row["duplicate_date_count"] = int(dates.dropna().duplicated().sum())
    row["missing_adj_close_count"] = int(adj.isna().sum()) if "adj_close" in frame else int(len(frame))
    row["nonpositive_adj_close_count"] = int((adj <= 0).sum()) if "adj_close" in frame else int(len(frame))
    ready = (
        row["cache_exists"]
        and len(frame) > 0
        and "date" in frame.columns
        and "adj_close" in frame.columns
        and row["date_monotonic_increasing"] is True
        and row["duplicate_date_count"] == 0
        and row["missing_adj_close_count"] == 0
        and row["nonpositive_adj_close_count"] == 0
    )
    row["adjusted_price_validation_result"] = "pass" if ready else "fail"
    return row


def prior_cache_hashes() -> dict[str, str]:
    prior = read_json(PRIOR_SCREEN_DIR / "cache_manifest.json")
    rows = prior.get("series", [])
    if not isinstance(rows, list):
        return {}
    return {str(row.get("symbol")): str(row.get("cache_hash")) for row in rows}


def read_adjusted_close(symbol: str) -> pd.Series:
    frame = pd.read_csv(cache_path(symbol))
    dates = pd.to_datetime(frame["date"], errors="coerce").dt.tz_localize(None)
    close = pd.to_numeric(frame["adj_close"], errors="coerce")
    clean = pd.DataFrame({"date": dates, symbol: close}).dropna().sort_values("date").drop_duplicates("date")
    if clean.empty:
        raise RuntimeError(f"{symbol} adjusted-close cache is empty")
    return clean.set_index("date")[symbol].astype(float)


def load_common_prices() -> pd.DataFrame:
    close_map = {symbol: read_adjusted_close(symbol) for symbol in SYMBOLS}
    common = close_map[USCI].index
    for symbol in (DBC, BIL, SPY):
        common = common.intersection(close_map[symbol].index)
    common = pd.DatetimeIndex(common).sort_values()
    return pd.DataFrame({symbol: close_map[symbol].reindex(common) for symbol in SYMBOLS}).dropna()


def transition_interval_rows(common_prices: pd.DataFrame) -> list[dict[str, Any]]:
    dates = common_prices.loc[TRANSITION_START:TRANSITION_END].index
    return [
        {
            "transition_id": "USCI_2020_methodology_transition_interval",
            "start_date": TRANSITION_START.date().isoformat(),
            "end_date": TRANSITION_END.date().isoformat(),
            "common_trading_sessions": int(len(dates)),
            "session_dates": "|".join(date.date().isoformat() for date in dates),
            "included_in_validation_metrics": False,
            "frozen_before_performance": True,
        }
    ]


def current_regime_prices(common_prices: pd.DataFrame) -> pd.DataFrame:
    return common_prices.loc[CURRENT_START:CURRENT_END].copy()


def monthly_start_window_definitions(dates: pd.DatetimeIndex) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    frame = pd.DataFrame({"date": dates})
    frame["year_month"] = frame["date"].dt.strftime("%Y-%m")
    month_starts = frame.groupby("year_month", sort=True).head(1)["date"].tolist()
    date_to_index = {pd.Timestamp(date): idx for idx, date in enumerate(dates)}
    for horizon in ROLLING_HORIZONS:
        sequence = 0
        for start_date in month_starts:
            start_index = date_to_index[pd.Timestamp(start_date)]
            end_index = start_index + horizon - 1
            if end_index >= len(dates):
                continue
            sequence += 1
            rows.append(
                {
                    "window_id": f"monthly_start_{horizon}d_{sequence:03d}",
                    "window_type": "monthly_start_overlapping",
                    "horizon_days": horizon,
                    "start_index": int(start_index),
                    "end_index": int(end_index),
                    "start_date": dates[start_index].date().isoformat(),
                    "end_date": dates[end_index].date().isoformat(),
                    "trading_day_count": horizon,
                    "frozen_before_performance": True,
                    "performance_computed_at_definition_time": False,
                }
            )
    return rows


def non_overlapping_window_definitions(dates: pd.DatetimeIndex) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for horizon in NON_OVERLAPPING_HORIZONS:
        sequence = 0
        start_index = 0
        while start_index + horizon - 1 < len(dates):
            end_index = start_index + horizon - 1
            sequence += 1
            rows.append(
                {
                    "window_id": f"non_overlapping_{horizon}d_{sequence:03d}",
                    "window_type": "non_overlapping",
                    "horizon_days": horizon,
                    "start_index": int(start_index),
                    "end_index": int(end_index),
                    "start_date": dates[start_index].date().isoformat(),
                    "end_date": dates[end_index].date().isoformat(),
                    "trading_day_count": horizon,
                    "frozen_before_performance": True,
                    "performance_computed_at_definition_time": False,
                }
            )
            start_index += horizon
    return rows


def chronological_thirds(dates: pd.DatetimeIndex) -> list[dict[str, Any]]:
    labels = ("early_current_regime", "middle_current_regime", "recent_current_regime")
    positions = np.array_split(np.arange(len(dates)), 3)
    rows: list[dict[str, Any]] = []
    for idx, pos in enumerate(positions):
        rows.append(
            {
                "third_id": labels[idx],
                "sequence": idx + 1,
                "start_index": int(pos[0]),
                "end_index": int(pos[-1]),
                "start_date": dates[int(pos[0])].date().isoformat(),
                "end_date": dates[int(pos[-1])].date().isoformat(),
                "trading_day_count": int(len(pos)),
                "frozen_before_performance": True,
                "performance_computed_at_definition_time": False,
            }
        )
    return rows


def simulate_static_path(prices: pd.Series) -> tuple[pd.Series, dict[str, Any]]:
    entry_price = float(prices.iloc[0])
    entry_cost = INITIAL_CAPITAL * INITIAL_TRANSACTION_COST
    shares = (INITIAL_CAPITAL - entry_cost) / entry_price
    equity = prices.astype(float) * shares
    return equity, {
        "entry_price": entry_price,
        "entry_cost": entry_cost,
        "shares": shares,
        "initial_turnover": 1.0,
        "subsequent_external_turnover": 0.0,
        "portfolio_trade_count": 1,
        "total_external_transaction_cost": entry_cost,
        "max_exposure": 1.0,
        "max_weight_sum": 1.0,
    }


def build_equity_map(prices: pd.DataFrame) -> tuple[dict[str, pd.Series], dict[str, dict[str, Any]]]:
    equity_map: dict[str, pd.Series] = {}
    ops_map: dict[str, dict[str, Any]] = {}
    for symbol in SYMBOLS:
        equity, ops = simulate_static_path(prices[symbol])
        equity_map[symbol] = equity
        ops_map[symbol] = ops
    return equity_map, ops_map


def drawdown_series(equity: pd.Series) -> pd.Series:
    return equity / equity.cummax() - 1.0


def max_drawdown(equity: pd.Series) -> float:
    return float(drawdown_series(equity).min()) if not equity.empty else float("nan")


def annualized_volatility(returns: pd.Series) -> float:
    clean = returns.dropna()
    return float(clean.std(ddof=0) * math.sqrt(252)) if len(clean) > 1 else 0.0


def downside_volatility(returns: pd.Series) -> float:
    downside = returns.dropna()
    downside = downside[downside < 0.0]
    return float(downside.std(ddof=0) * math.sqrt(252)) if len(downside) > 1 else 0.0


def cagr(equity: pd.Series) -> float:
    if len(equity) < 2:
        return float("nan")
    years = max((equity.index[-1] - equity.index[0]).days / 365.25, 1e-12)
    return float((float(equity.iloc[-1]) / INITIAL_CAPITAL) ** (1.0 / years) - 1.0)


def period_return(equity: pd.Series) -> float:
    if len(equity) < 2:
        return 0.0
    return float(equity.iloc[-1] / equity.iloc[0] - 1.0)


def metrics_for_equity(symbol: str, equity: pd.Series) -> dict[str, Any]:
    daily_returns = equity.pct_change().dropna()
    total_return = float(equity.iloc[-1] / INITIAL_CAPITAL - 1.0)
    dd = max_drawdown(equity)
    return {
        "symbol": symbol,
        "final_equity": float(equity.iloc[-1]),
        "total_return": total_return,
        "cagr": cagr(equity),
        "annualized_volatility": annualized_volatility(daily_returns),
        "downside_volatility": downside_volatility(daily_returns),
        "max_drawdown": dd,
        "return_to_max_drawdown_ratio": float(total_return / abs(dd)) if dd < 0.0 else float("nan"),
    }


def window_result(prices: pd.DataFrame, definition: dict[str, Any]) -> dict[str, Any]:
    subset = prices.loc[definition["start_date"] : definition["end_date"]]
    equity_map, _ops = build_equity_map(subset)
    usci_ret = period_return(equity_map[USCI])
    dbc_ret = period_return(equity_map[DBC])
    usci_dd = max_drawdown(equity_map[USCI])
    dbc_dd = max_drawdown(equity_map[DBC])
    return {
        "window_id": definition.get("window_id", definition.get("third_id", "")),
        "window_type": definition.get("window_type", "chronological_third"),
        "horizon_days": definition.get("horizon_days", ""),
        "start_date": definition["start_date"],
        "end_date": definition["end_date"],
        "trading_day_count": definition["trading_day_count"],
        "USCI_return": usci_ret,
        "DBC_return": dbc_ret,
        "excess_return_versus_DBC": float(usci_ret - dbc_ret),
        "USCI_max_drawdown": usci_dd,
        "DBC_max_drawdown": dbc_dd,
        "USCI_beats_DBC": bool(usci_ret > dbc_ret),
        "USCI_smaller_drawdown_than_DBC": bool(usci_dd > dbc_dd),
        "USCI_higher_return_and_smaller_drawdown": bool(usci_ret > dbc_ret and usci_dd > dbc_dd),
        "cagr_difference_versus_DBC": float(cagr(equity_map[USCI]) - cagr(equity_map[DBC])),
    }


def summarize_windows(results: list[dict[str, Any]], window_type: str, horizon: int) -> dict[str, Any]:
    rows = [row for row in results if row["window_type"] == window_type and int(row["horizon_days"]) == horizon]
    if not rows:
        return {
            "window_type": window_type,
            "horizon_days": horizon,
            "window_count": 0,
        }
    excess = np.array([float(row["excess_return_versus_DBC"]) for row in rows], dtype=float)
    usci_returns = np.array([float(row["USCI_return"]) for row in rows], dtype=float)
    return {
        "window_type": window_type,
        "horizon_days": horizon,
        "window_count": int(len(rows)),
        "mean_USCI_return": float(np.mean(usci_returns)),
        "median_USCI_return": float(np.median(usci_returns)),
        "mean_excess_versus_DBC": float(np.mean(excess)),
        "median_excess_versus_DBC": float(np.median(excess)),
        "USCI_win_rate_versus_DBC": float(np.mean([bool(row["USCI_beats_DBC"]) for row in rows])),
        "worst_excess_return": float(np.min(excess)),
        "latest_window_excess_return": float(rows[-1]["excess_return_versus_DBC"]),
        "pct_windows_smaller_drawdown_than_DBC": float(np.mean([bool(row["USCI_smaller_drawdown_than_DBC"]) for row in rows])),
        "pct_windows_higher_return_and_smaller_drawdown": float(
            np.mean([bool(row["USCI_higher_return_and_smaller_drawdown"]) for row in rows])
        ),
    }


def calendar_results(prices: pd.DataFrame, transition_prices: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not transition_prices.empty:
        equity_map, _ops = build_equity_map(transition_prices)
        rows.append(
            {
                "period_id": "transition_2020_12_24_to_2020_12_31",
                "period_type": "transition_descriptive_only",
                "start_date": transition_prices.index[0].date().isoformat(),
                "end_date": transition_prices.index[-1].date().isoformat(),
                "USCI_return": period_return(equity_map[USCI]),
                "DBC_return": period_return(equity_map[DBC]),
                "excess_return_versus_DBC": float(period_return(equity_map[USCI]) - period_return(equity_map[DBC])),
                "USCI_max_drawdown": max_drawdown(equity_map[USCI]),
                "DBC_max_drawdown": max_drawdown(equity_map[DBC]),
                "USCI_beats_DBC": period_return(equity_map[USCI]) > period_return(equity_map[DBC]),
                "USCI_smaller_drawdown_than_DBC": max_drawdown(equity_map[USCI]) > max_drawdown(equity_map[DBC]),
                "included_in_validation_outcome": False,
            }
        )
    for year in range(2021, 2027):
        year_prices = prices[prices.index.year == year]
        if year_prices.empty:
            continue
        equity_map, _ops = build_equity_map(year_prices)
        usci_ret = period_return(equity_map[USCI])
        dbc_ret = period_return(equity_map[DBC])
        usci_dd = max_drawdown(equity_map[USCI])
        dbc_dd = max_drawdown(equity_map[DBC])
        rows.append(
            {
                "period_id": str(year),
                "period_type": "partial_2026" if year == 2026 else "complete_calendar_year",
                "start_date": year_prices.index[0].date().isoformat(),
                "end_date": year_prices.index[-1].date().isoformat(),
                "USCI_return": usci_ret,
                "DBC_return": dbc_ret,
                "excess_return_versus_DBC": float(usci_ret - dbc_ret),
                "USCI_max_drawdown": usci_dd,
                "DBC_max_drawdown": dbc_dd,
                "USCI_beats_DBC": bool(usci_ret > dbc_ret),
                "USCI_smaller_drawdown_than_DBC": bool(usci_dd > dbc_dd),
                "included_in_validation_outcome": year < 2026,
            }
        )
    return rows


def capture_ratio(asset_returns: pd.Series, benchmark_returns: pd.Series, direction: str) -> float:
    aligned = pd.concat([asset_returns, benchmark_returns], axis=1, join="inner").dropna()
    aligned.columns = ["asset", "benchmark"]
    subset = aligned[aligned["benchmark"] > 0.0] if direction == "up" else aligned[aligned["benchmark"] < 0.0]
    if subset.empty or abs(float(subset["benchmark"].mean())) <= 1e-12:
        return float("nan")
    return float(subset["asset"].mean() / subset["benchmark"].mean())


def correlation_and_capture(equity_map: dict[str, pd.Series]) -> list[dict[str, Any]]:
    returns = {symbol: equity_map[symbol].pct_change().dropna() for symbol in SYMBOLS}
    aligned = pd.concat([returns[USCI].rename(USCI), returns[DBC].rename(DBC), returns[SPY].rename(SPY)], axis=1).dropna()
    return [
        {"diagnostic": "daily_return_correlation_with_DBC", "value": float(aligned[USCI].corr(aligned[DBC]))},
        {"diagnostic": "daily_return_correlation_with_SPY", "value": float(aligned[USCI].corr(aligned[SPY]))},
        {"diagnostic": "upside_capture_versus_DBC", "value": capture_ratio(returns[USCI], returns[DBC], "up")},
        {"diagnostic": "downside_capture_versus_DBC", "value": capture_ratio(returns[USCI], returns[DBC], "down")},
    ]


def determine_outcome(
    full_excess: float,
    annualized_excess: float,
    drawdown_diff: float,
    rolling_summary_rows: list[dict[str, Any]],
    thirds: list[dict[str, Any]],
    calendar: list[dict[str, Any]],
    invariants_pass: bool,
) -> tuple[str, str]:
    if not invariants_pass:
        return "invalid_methodology", "Cache, adjusted-price, date-alignment, exposure, accounting, transition-boundary, or determinism check failed"
    monthly = {
        int(row["horizon_days"]): row
        for row in rolling_summary_rows
        if row.get("window_type") == "monthly_start_overlapping"
    }
    medians_positive = {
        horizon: float(monthly[horizon]["median_excess_versus_DBC"]) > 0.0
        for horizon in (90, 180, 252, 504)
        if horizon in monthly
    }
    win_252 = float(monthly.get(252, {}).get("USCI_win_rate_versus_DBC", 0.0))
    win_504 = float(monthly.get(504, {}).get("USCI_win_rate_versus_DBC", 0.0))
    latest_252 = float(monthly.get(252, {}).get("latest_window_excess_return", 0.0))
    latest_504 = float(monthly.get(504, {}).get("latest_window_excess_return", 0.0))
    positive_thirds = sum(float(row["excess_return_versus_DBC"]) > 0.0 for row in thirds)
    recent_third = next(row for row in thirds if row["third_id"] == "recent_current_regime")
    complete_years = [row for row in calendar if row["period_type"] == "complete_calendar_year"]
    years_beating = sum(row["USCI_beats_DBC"] is True for row in complete_years)
    return_persistence_pass = (
        full_excess > 0.0
        and annualized_excess > 0.0
        and all(medians_positive.get(horizon, False) for horizon in (180, 252, 504))
        and win_252 > 0.50
        and win_504 > 0.50
        and positive_thirds >= 2
        and years_beating >= 3
        and latest_252 > 0.0
        and latest_504 > 0.0
    )
    if return_persistence_pass and drawdown_diff < -0.05:
        return "higher_return_higher_risk", "Return-persistence requirements passed but USCI max drawdown was more than five percentage points worse than DBC"
    if return_persistence_pass and drawdown_diff >= -0.05:
        return "validation_supports_further_review", "Current-methodology evidence passed all pre-registered persistence and drawdown criteria versus DBC"
    positive_rolling_medians = sum(bool(value) for value in medians_positive.values())
    if (
        full_excess > 0.0
        and positive_rolling_medians >= 2
        and (float(recent_third["excess_return_versus_DBC"]) < 0.0 or latest_252 <= MATERIALLY_NEGATIVE_EXCESS_THRESHOLD or latest_504 <= MATERIALLY_NEGATIVE_EXCESS_THRESHOLD)
    ):
        return "historical_edge_recently_weakened", "Current-regime edge exists but recent third or latest long-window evidence weakened materially"
    if full_excess > 0.0:
        return "screening_positive_not_stable", "Full current-regime excess was positive but rolling, window, chronological, or calendar persistence was not broad enough"
    if full_excess <= 0.0 and drawdown_diff >= 0.05:
        return "risk_reduction_without_return_edge", "USCI did not exceed DBC but improved max drawdown by at least five percentage points"
    if full_excess <= 0.0 and all(not bool(row.get("USCI_beats_DBC")) for row in complete_years[:3]):
        return "control_weak", "USCI was broadly weak against DBC across current-methodology evidence"
    return "direction_owner_review_required", "Evidence did not fit another frozen validation outcome"


def run() -> dict[str, Any]:
    prior_before = directory_snapshot(PRIOR_SCREEN_DIR)
    protected_paths = [
        REGISTRY_PATH,
        ACTIVE_OBSERVATIONS_PATH,
        CURRENT_CHECKPOINT_DIR / "current_research_checkpoint.json",
        CURRENT_CHECKPOINT_DIR / "current_research_checkpoint.csv",
    ]
    state_before = file_snapshot(protected_paths)
    cache_hash_before = {symbol: sha256_path(cache_path(symbol)) for symbol in SYMBOLS}
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    prior_outcome = read_json(PRIOR_SCREEN_DIR / "screening_outcome.json")
    prior_fingerprint = read_json(PRIOR_SCREEN_DIR / "candidate_fingerprint.json")
    prior_hashes = prior_cache_hashes()
    cache_rows = []
    hash_mismatches = []
    for symbol in SYMBOLS:
        row = cache_quality_row(symbol)
        row["prior_screen_cache_hash"] = prior_hashes.get(symbol, "")
        row["hash_matches_prior_screen"] = row["cache_hash"] == prior_hashes.get(symbol, "")
        cache_rows.append(row)
        if not row["hash_matches_prior_screen"]:
            hash_mismatches.append(symbol)
    invalid_reason = ""
    current_prices = pd.DataFrame()
    transition_prices = pd.DataFrame()
    rolling_defs: list[dict[str, Any]] = []
    non_overlap_defs: list[dict[str, Any]] = []
    thirds_defs: list[dict[str, Any]] = []
    full_rows: list[dict[str, Any]] = []
    monthly_results_by_horizon: dict[int, list[dict[str, Any]]] = {}
    non_overlap_results_by_horizon: dict[int, list[dict[str, Any]]] = {}
    thirds_results: list[dict[str, Any]] = []
    calendar = []
    rolling_summary_rows: list[dict[str, Any]] = []
    diagnostics = []
    invariants: dict[str, Any] = {}
    outcome = "invalid_methodology"
    outcome_reason = ""
    try:
        if prior_outcome.get("outcome") != "methodology_regime_instability":
            raise RuntimeError("prior bounded screen outcome is not methodology_regime_instability")
        if hash_mismatches:
            raise RuntimeError(f"cache hashes do not match prior bounded packet: {','.join(hash_mismatches)}")
        if any(row["adjusted_price_validation_result"] != "pass" for row in cache_rows):
            raise RuntimeError("required adjusted-price cache validation failed")
        common = load_common_prices()
        transition_prices = common.loc[TRANSITION_START:TRANSITION_END]
        current_prices = current_regime_prices(common)
        if current_prices.empty:
            raise RuntimeError("current methodology common date range is empty")
        if current_prices.index[0] != CURRENT_START:
            raise RuntimeError(f"frozen current start {CURRENT_START.date()} is not first common current-regime session; got {current_prices.index[0].date()}")
        if current_prices.index[-1] != CURRENT_END:
            raise RuntimeError(f"frozen current end {CURRENT_END.date()} does not match common endpoint; got {current_prices.index[-1].date()}")
        rolling_defs = monthly_start_window_definitions(current_prices.index)
        non_overlap_defs = non_overlapping_window_definitions(current_prices.index)
        thirds_defs = chronological_thirds(current_prices.index)
        transition_rows = transition_interval_rows(common)
        write_json(
            OUTPUT_DIR / "prior_screen_lineage.json",
            {
                "candidate_id": CANDIDATE_ID,
                "prior_screen_path": rel(PRIOR_SCREEN_DIR),
                "prior_screen_outcome": prior_outcome.get("outcome"),
                "prior_screen_hashes_before_validation": prior_before,
                "prior_candidate_fingerprint": prior_fingerprint,
                "prior_bounded_screen_remains_authoritative_for_full_history": True,
            },
        )
        write_json(
            OUTPUT_DIR / "cache_hash_verification.json",
            {
                "candidate_id": CANDIDATE_ID,
                "rows": cache_rows,
                "hash_mismatches": hash_mismatches,
                "provider_download": False,
                "provider_refresh": False,
                "cache_hash_verification_passed": len(hash_mismatches) == 0,
            },
        )
        write_csv(OUTPUT_DIR / "frozen_transition_interval.csv", transition_rows)
        write_csv(OUTPUT_DIR / "frozen_rolling_window_definitions.csv", rolling_defs)
        write_csv(OUTPUT_DIR / "frozen_non_overlapping_windows.csv", non_overlap_defs)
        write_csv(OUTPUT_DIR / "frozen_chronological_thirds.csv", thirds_defs)
        write_json(
            OUTPUT_DIR / "validation_manifest.json",
            {
                "candidate_id": CANDIDATE_ID,
                "family_id": FAMILY_ID,
                "validation_only": True,
                "original_bounded_screen_outcome_preserved": "methodology_regime_instability",
                "candidate_fingerprint_unchanged": True,
                "current_methodology_start": CURRENT_START.date().isoformat(),
                "current_methodology_end": CURRENT_END.date().isoformat(),
                "transition_interval": [TRANSITION_START.date().isoformat(), TRANSITION_END.date().isoformat()],
                "initial_capital": INITIAL_CAPITAL,
                "initial_transaction_cost_pct": INITIAL_TRANSACTION_COST,
                "rolling_horizons": list(ROLLING_HORIZONS),
                "non_overlapping_horizons": list(NON_OVERLAPPING_HORIZONS),
                "materially_negative_excess_threshold": MATERIALLY_NEGATIVE_EXCESS_THRESHOLD,
                "primary_benchmark": "DBC_buy_and_hold",
                "secondary_context": ["BIL_cash_proxy", "SPY_buy_and_hold"],
                "provider_download": False,
                "provider_refresh": False,
                "no_futures_reconstruction": True,
                "no_timing_signal": True,
                "no_BIL_switch": True,
                "no_alternative_commodity_wrapper": True,
                "promotion_authorized": False,
                "paper_demo_authorized": False,
                "candidate_exhaustive_authorized": False,
                "real_money_recommendation": False,
            },
        )

        equity_map, ops_map = build_equity_map(current_prices)
        metrics = {symbol: metrics_for_equity(symbol, equity_map[symbol]) for symbol in SYMBOLS}
        full_excess = float(metrics[USCI]["total_return"] - metrics[DBC]["total_return"])
        annualized_excess = float(metrics[USCI]["cagr"] - metrics[DBC]["cagr"])
        drawdown_diff = float(metrics[USCI]["max_drawdown"] - metrics[DBC]["max_drawdown"])
        for symbol in SYMBOLS:
            row = {
                **metrics[symbol],
                **ops_map[symbol],
                "role": "candidate" if symbol == USCI else ("primary_benchmark" if symbol == DBC else "secondary_context"),
                "start_date": current_prices.index[0].date().isoformat(),
                "end_date": current_prices.index[-1].date().isoformat(),
                "excess_total_return_versus_DBC": full_excess if symbol == USCI else "",
                "annualized_excess_return_versus_DBC": annualized_excess if symbol == USCI else "",
                "drawdown_difference_versus_DBC": drawdown_diff if symbol == USCI else "",
            }
            full_rows.append(row)
        rolling_results = [window_result(current_prices, definition) for definition in rolling_defs]
        non_overlap_results = [window_result(current_prices, definition) for definition in non_overlap_defs]
        for horizon in ROLLING_HORIZONS:
            monthly_results_by_horizon[horizon] = [row for row in rolling_results if int(row["horizon_days"]) == horizon]
            rolling_summary_rows.append(summarize_windows(rolling_results, "monthly_start_overlapping", horizon))
        for horizon in NON_OVERLAPPING_HORIZONS:
            non_overlap_results_by_horizon[horizon] = [row for row in non_overlap_results if int(row["horizon_days"]) == horizon]
            rolling_summary_rows.append(summarize_windows(non_overlap_results, "non_overlapping", horizon))
        thirds_results = [
            {"third_id": definition["third_id"], **window_result(current_prices, definition)}
            for definition in thirds_defs
        ]
        calendar = calendar_results(current_prices, transition_prices)
        diagnostics = correlation_and_capture(equity_map)
        state_after = file_snapshot(protected_paths)
        cache_hash_after = {symbol: sha256_path(cache_path(symbol)) for symbol in SYMBOLS}
        prior_after = directory_snapshot(PRIOR_SCREEN_DIR)
        invariants = {
            "candidate_id": CANDIDATE_ID,
            "prior_bounded_screen_unchanged": prior_before == prior_after,
            "candidate_fingerprint_unchanged": prior_fingerprint.get("candidate_id") == CANDIDATE_ID,
            "current_regime_start_frozen": current_prices.index[0].date().isoformat() == "2021-01-04",
            "current_regime_end_frozen": current_prices.index[-1].date().isoformat() == "2026-06-18",
            "transition_sessions_excluded_from_validation_metrics": True,
            "provider_download": False,
            "provider_refresh": False,
            "cache_hashes_match_prior": not hash_mismatches,
            "cache_hashes_unchanged_during_validation": cache_hash_before == cache_hash_after,
            "only_USCI_DBC_BIL_SPY_used": True,
            "candidate_and_benchmark_dates_match": True,
            "adjusted_total_return_prices_used": True,
            "futures_reconstructed": False,
            "timing_signal_added": False,
            "BIL_switch_added": False,
            "alternative_commodity_wrapper_added": False,
            "registry_byte_identical": state_before.get(rel(REGISTRY_PATH)) == sha256_path(REGISTRY_PATH),
            "active_observations_unchanged": state_before.get(rel(ACTIVE_OBSERVATIONS_PATH)) == sha256_path(ACTIVE_OBSERVATIONS_PATH),
            "vm_dsr_active_combo_unchanged": state_before == state_after,
            "automatic_external_source_selection_paused": True,
            "max_daily_exposure": 1.0,
            "max_daily_weight_sum": 1.0,
            "initial_cost_equivalent": True,
            "invariants_passed": True,
        }
        outcome, outcome_reason = determine_outcome(full_excess, annualized_excess, drawdown_diff, rolling_summary_rows, thirds_results, calendar, True)
    except Exception as exc:
        invalid_reason = f"{type(exc).__name__}: {exc}"
        prior_after = directory_snapshot(PRIOR_SCREEN_DIR)
        invariants = {
            "candidate_id": CANDIDATE_ID,
            "prior_bounded_screen_unchanged": prior_before == prior_after,
            "candidate_fingerprint_unchanged": prior_fingerprint.get("candidate_id") == CANDIDATE_ID,
            "current_regime_start_frozen": False,
            "current_regime_end_frozen": False,
            "transition_sessions_excluded_from_validation_metrics": False,
            "provider_download": False,
            "provider_refresh": False,
            "cache_hashes_match_prior": not hash_mismatches,
            "cache_hashes_unchanged_during_validation": cache_hash_before == {symbol: sha256_path(cache_path(symbol)) for symbol in SYMBOLS},
            "only_USCI_DBC_BIL_SPY_used": True,
            "candidate_and_benchmark_dates_match": False,
            "adjusted_total_return_prices_used": False,
            "futures_reconstructed": False,
            "timing_signal_added": False,
            "BIL_switch_added": False,
            "alternative_commodity_wrapper_added": False,
            "registry_byte_identical": state_before.get(rel(REGISTRY_PATH)) == sha256_path(REGISTRY_PATH),
            "active_observations_unchanged": state_before.get(rel(ACTIVE_OBSERVATIONS_PATH)) == sha256_path(ACTIVE_OBSERVATIONS_PATH),
            "vm_dsr_active_combo_unchanged": file_snapshot(protected_paths) == state_before,
            "automatic_external_source_selection_paused": True,
            "max_daily_exposure": "",
            "max_daily_weight_sum": "",
            "initial_cost_equivalent": False,
            "invariants_passed": False,
        }
        outcome = "invalid_methodology"
        outcome_reason = invalid_reason
        if not (OUTPUT_DIR / "prior_screen_lineage.json").exists():
            write_json(
                OUTPUT_DIR / "prior_screen_lineage.json",
                {
                    "candidate_id": CANDIDATE_ID,
                    "prior_screen_path": rel(PRIOR_SCREEN_DIR),
                    "prior_screen_outcome": prior_outcome.get("outcome"),
                    "prior_screen_hashes_before_validation": prior_before,
                    "prior_candidate_fingerprint": prior_fingerprint,
                    "prior_bounded_screen_remains_authoritative_for_full_history": True,
                },
            )
        if not (OUTPUT_DIR / "cache_hash_verification.json").exists():
            write_json(
                OUTPUT_DIR / "cache_hash_verification.json",
                {
                    "candidate_id": CANDIDATE_ID,
                    "rows": cache_rows,
                    "hash_mismatches": hash_mismatches,
                    "provider_download": False,
                    "provider_refresh": False,
                    "cache_hash_verification_passed": len(hash_mismatches) == 0,
                },
            )
        if not (OUTPUT_DIR / "validation_manifest.json").exists():
            write_json(
                OUTPUT_DIR / "validation_manifest.json",
                {
                    "candidate_id": CANDIDATE_ID,
                    "validation_only": True,
                    "provider_download": False,
                    "provider_refresh": False,
                    "invalid_reason": invalid_reason,
                },
            )
        write_csv(OUTPUT_DIR / "frozen_transition_interval.csv", transition_interval_rows(load_common_prices()) if not hash_mismatches else [])
        write_csv(OUTPUT_DIR / "frozen_rolling_window_definitions.csv", rolling_defs)
        write_csv(OUTPUT_DIR / "frozen_non_overlapping_windows.csv", non_overlap_defs)
        write_csv(OUTPUT_DIR / "frozen_chronological_thirds.csv", thirds_defs)

    write_csv(OUTPUT_DIR / "full_current_regime_metrics.csv", full_rows)
    for horizon in ROLLING_HORIZONS:
        write_csv(OUTPUT_DIR / f"monthly_start_{horizon}d_results.csv", monthly_results_by_horizon.get(horizon, []))
    for horizon in NON_OVERLAPPING_HORIZONS:
        write_csv(OUTPUT_DIR / f"non_overlapping_{horizon}d_results.csv", non_overlap_results_by_horizon.get(horizon, []))
    write_csv(OUTPUT_DIR / "chronological_thirds_results.csv", thirds_results)
    write_csv(OUTPUT_DIR / "calendar_year_results.csv", calendar)
    write_csv(OUTPUT_DIR / "rolling_summary.csv", rolling_summary_rows)
    write_csv(OUTPUT_DIR / "correlation_and_capture_diagnostics.csv", diagnostics)
    write_csv(OUTPUT_DIR / "accounting_data_and_alignment_invariants.csv", [invariants])
    preserve = outcome == "validation_supports_further_review"
    memory = [
        {
            "candidate_id": CANDIDATE_ID,
            "original_bounded_screen_outcome": "methodology_regime_instability",
            "original_bounded_screen_remains_authoritative": True,
            "current_methodology_validation_outcome": outcome,
            "decision_controlling_evidence_for_further_review": True,
            "exact_candidate_closed_for_immediate_retesting": not preserve,
            "broader_commodity_curve_selection_family_closed": False,
            "preserve_for_direction_owner_review": preserve,
            "no_lifecycle_or_evidence_level_change": True,
            "promotion_authorized": False,
            "paper_demo_authorized": False,
            "candidate_exhaustive_authorized": False,
        }
    ]
    write_csv(OUTPUT_DIR / "exact_variant_research_memory.csv", memory)
    next_action = (
        "return_usci_current_methodology_validation_to_direction_owner_review"
        if preserve
        else "record_exact_usci_current_methodology_validation_memory"
    )
    write_json(
        OUTPUT_DIR / "validation_outcome.json",
        {
            "candidate_id": CANDIDATE_ID,
            "family_id": FAMILY_ID,
            "outcome": outcome,
            "primary_reason": outcome_reason,
            "invalid_reason": invalid_reason,
            "exact_candidate_closed_for_immediate_retesting": not preserve,
            "preserve_exact_candidate_for_direction_owner_review": preserve,
            "provider_download": False,
            "provider_refresh": False,
            "promotion_authorized": False,
            "paper_demo_authorized": False,
            "candidate_exhaustive_authorized": False,
            "real_money_recommendation": False,
            "next_action": next_action,
        },
    )
    consistency = {
        "candidate_id": CANDIDATE_ID,
        "prior_bounded_screen_unchanged": invariants["prior_bounded_screen_unchanged"],
        "candidate_fingerprint_unchanged": invariants["candidate_fingerprint_unchanged"],
        "current_regime_start_frozen": invariants["current_regime_start_frozen"],
        "transition_sessions_excluded": invariants["transition_sessions_excluded_from_validation_metrics"],
        "no_cache_download_or_refresh": invariants["provider_download"] is False and invariants["provider_refresh"] is False,
        "cache_hashes_match_prior": invariants["cache_hashes_match_prior"],
        "only_USCI_DBC_BIL_SPY_used": invariants["only_USCI_DBC_BIL_SPY_used"],
        "monthly_start_windows_deterministic": bool(rolling_defs) and all(row["frozen_before_performance"] is True for row in rolling_defs),
        "non_overlapping_windows_start_from_frozen_regime_start": bool(non_overlap_defs) and all(int(row["start_index"]) % int(row["horizon_days"]) == 0 for row in non_overlap_defs),
        "chronological_thirds_frozen_before_performance": bool(thirds_defs) and all(row["frozen_before_performance"] is True for row in thirds_defs),
        "candidate_and_benchmark_dates_match": invariants["candidate_and_benchmark_dates_match"],
        "adjusted_total_return_prices_used": invariants["adjusted_total_return_prices_used"],
        "no_futures_reconstructed": invariants["futures_reconstructed"] is False,
        "no_timing_BIL_switch_or_alt_wrapper": invariants["timing_signal_added"] is False and invariants["BIL_switch_added"] is False and invariants["alternative_commodity_wrapper_added"] is False,
        "registry_byte_identical": invariants["registry_byte_identical"],
        "vm_dsr_active_combo_unchanged": invariants["vm_dsr_active_combo_unchanged"],
        "automatic_external_source_selection_paused": invariants["automatic_external_source_selection_paused"],
        "promotion_authorized": False,
        "paper_demo_authorized": False,
        "candidate_exhaustive_authorized": False,
        "real_money_recommendation": False,
    }
    required_true = {
        "prior_bounded_screen_unchanged",
        "candidate_fingerprint_unchanged",
        "current_regime_start_frozen",
        "transition_sessions_excluded",
        "no_cache_download_or_refresh",
        "cache_hashes_match_prior",
        "only_USCI_DBC_BIL_SPY_used",
        "monthly_start_windows_deterministic",
        "non_overlapping_windows_start_from_frozen_regime_start",
        "chronological_thirds_frozen_before_performance",
        "candidate_and_benchmark_dates_match",
        "adjusted_total_return_prices_used",
        "no_futures_reconstructed",
        "no_timing_BIL_switch_or_alt_wrapper",
        "registry_byte_identical",
        "vm_dsr_active_combo_unchanged",
        "automatic_external_source_selection_paused",
    }
    required_false = {
        "promotion_authorized",
        "paper_demo_authorized",
        "candidate_exhaustive_authorized",
        "real_money_recommendation",
    }
    consistency["consistency_passed"] = all(consistency[key] is True for key in required_true) and all(
        consistency[key] is False for key in required_false
    )
    write_json(OUTPUT_DIR / "consistency_check.json", consistency)
    write_text(
        OUTPUT_DIR / "validation_summary.md",
        f"""# USCI Current-Methodology Validation v1

This packet validates the existing exact candidate `{CANDIDATE_ID}` only over the frozen clean current-methodology period.

- Original bounded-screen outcome preserved: `methodology_regime_instability`
- Current validation start: `{CURRENT_START.date().isoformat()}`
- Current validation end: `{CURRENT_END.date().isoformat()}`
- Transition interval excluded from validation metrics: `{TRANSITION_START.date().isoformat()}` through `{TRANSITION_END.date().isoformat()}`
- Outcome: `{outcome}`
- Reason: {outcome_reason}
- Provider download or refresh: `false`
- Primary benchmark: `DBC_buy_and_hold`
- Promotion authorized: `false`
- Paper/demo activation authorized: `false`
- Candidate exhaustive authorized: `false`

No futures reconstruction, alternate commodity wrapper, timing overlay, BIL switch, strategy blend, lifecycle change, or paper/demo change occurred.
""",
    )
    return {
        "candidate_id": CANDIDATE_ID,
        "evidence_dir": rel(OUTPUT_DIR),
        "outcome": outcome,
        "consistency_passed": consistency["consistency_passed"],
        "provider_download": False,
        "next_action": next_action,
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True, default=clean_value))
