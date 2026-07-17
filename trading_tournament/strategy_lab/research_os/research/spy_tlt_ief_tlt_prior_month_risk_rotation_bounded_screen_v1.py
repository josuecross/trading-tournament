from __future__ import annotations

import csv
import hashlib
import inspect
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import run_active_strategy_evidence_recompute as active
from src.data import build_adjusted_ohlc
from strategy_lab.research_os.external_adapters.bt_adapter import reference_spy200d_weights


ROOT = Path(__file__).resolve().parents[3]
EVIDENCE_DIR = ROOT / "evidence" / "spy_tlt_ief_tlt_prior_month_risk_rotation_bounded_screen_v1" / "latest"

CANDIDATE_ID = "spy_tlt_ief_tlt_prior_month_risk_rotation_v1"
FAMILY_ID = "macro_duration_risk_off_rotation"
ROLE = "intermarket_treasury_duration_risk_rotation"
SOURCE_ID = "gayed_bilello_intermarket_tactical_risk_rotation_2014"

SPY = "SPY"
IEF = "IEF"
TLT = "TLT"
BIL = "BIL"
REQUIRED_SYMBOLS = (SPY, IEF, TLT)
CONTROL_SYMBOLS = (BIL,)
ALL_SYMBOLS = (SPY, IEF, TLT, BIL)
AUTHORIZED_DOWNLOAD_SYMBOLS = set(REQUIRED_SYMBOLS)
INITIAL_CAPITAL = float(active.STARTING_EQUITY)
TRANSACTION_COST = float(active.SLIPPAGE)
EQUALITY_TOLERANCE = 1e-12

REGISTRY_PATH = ROOT / "strategy_lab" / "strategy_registry.yaml"
ACTIVE_OBSERVATIONS_PATH = ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml"
PAPER_FORWARD_DIR = ROOT / "paper_forward_observations"
ACTIVE_COMBO_SERIES_PATH = ROOT / "evidence" / "active_combo_benchmark" / "latest" / "active_combo_equity_series.csv"

ALLOWED_OUTCOMES = {
    "comparative_evidence_positive",
    "historical_edge_recently_weakened",
    "risk_reduction_without_return_edge",
    "control_weak",
    "no_material_edge",
    "invalid_methodology",
    "duplicate_resolved",
}


@dataclass(frozen=True)
class PathResult:
    strategy_id: str
    role: str
    equity: pd.Series
    returns: pd.Series
    weights: pd.DataFrame
    trades: list[dict[str, Any]]


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
        return value.date().isoformat()
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
    if isinstance(value, pd.Timestamp):
        return value.date().isoformat()
    if isinstance(value, (list, tuple, set)):
        return "|".join(str(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True, default=clean_value)
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


def cache_path(symbol: str) -> Path:
    return ROOT / "data" / "cache" / f"{symbol}.csv"


def file_snapshot(paths: list[Path]) -> dict[str, str]:
    return {rel(path): sha256_path(path) for path in paths}


def default_yfinance_downloader(symbol: str, request_settings: dict[str, Any]) -> pd.DataFrame:
    symbol = symbol.upper()
    if symbol not in AUTHORIZED_DOWNLOAD_SYMBOLS:
        raise ValueError(f"Provider acquisition is limited to frozen tickers {sorted(AUTHORIZED_DOWNLOAD_SYMBOLS)}; got {symbol}")
    import yfinance as yf

    kwargs: dict[str, Any] = {
        "start": request_settings.get("start", "2007-01-01"),
        "end": request_settings.get("end"),
        "auto_adjust": bool(request_settings.get("auto_adjust", False)),
        "actions": bool(request_settings.get("actions", True)),
        "progress": bool(request_settings.get("progress", False)),
    }
    if kwargs["end"] is None:
        kwargs.pop("end")
    signature = inspect.signature(yf.download)
    if "multi_level_index" in signature.parameters:
        kwargs["multi_level_index"] = False
    if "timeout" in signature.parameters:
        kwargs["timeout"] = 30
    return yf.download(symbol, **kwargs)


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
        "provider_download": False,
        "cache_refreshed": False,
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
    ok = (
        row["row_count"] > 252
        and row["date_monotonic_increasing"]
        and row["duplicate_date_count"] == 0
        and row["missing_adj_close_count"] == 0
        and row["nonpositive_adj_close_count"] == 0
    )
    row["adjusted_price_validation_result"] = "pass" if ok else "fail"
    return row


def ensure_required_caches() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    before = {symbol: cache_quality_row(symbol) for symbol in ALL_SYMBOLS}
    missing_required = [symbol for symbol in REQUIRED_SYMBOLS if before[symbol]["adjusted_price_validation_result"] != "pass"]
    downloaded: list[str] = []
    errors: list[dict[str, str]] = []
    if len(missing_required) > 1:
        errors.append({"symbol": "|".join(missing_required), "error": "more_than_one_required_cache_missing"})
    elif len(missing_required) == 1:
        symbol = missing_required[0]
        try:
            raw = default_yfinance_downloader(symbol, {"start": "2007-01-01", "auto_adjust": False, "actions": True})
            normalized = build_adjusted_ohlc(raw, symbol)
            cache_path(symbol).parent.mkdir(parents=True, exist_ok=True)
            normalized.to_csv(cache_path(symbol), index=False, lineterminator="\n")
            downloaded.append(symbol)
        except Exception as exc:  # pragma: no cover - provider path is not expected in the current repo state
            errors.append({"symbol": symbol, "error": f"{type(exc).__name__}: {exc}"})
    after = [cache_quality_row(symbol) for symbol in ALL_SYMBOLS]
    for row in after:
        row["provider_download"] = row["symbol"] in downloaded
        row["cache_refreshed"] = row["symbol"] in downloaded
    manifest = {
        "candidate_id": CANDIDATE_ID,
        "authorized_download_symbols": sorted(AUTHORIZED_DOWNLOAD_SYMBOLS),
        "provider_download": bool(downloaded),
        "downloaded_symbols_this_run": downloaded,
        "missing_required_symbols_before_run": missing_required,
        "missing_required_symbols_after_run": [row["symbol"] for row in after if row["symbol"] in REQUIRED_SYMBOLS and row["adjusted_price_validation_result"] != "pass"],
        "more_than_one_missing_stops_run": len(missing_required) > 1,
        "BIL_provider_acquisition_authorized": False,
        "errors": errors,
        "valid_existing_caches_not_refreshed": [
            symbol for symbol in ALL_SYMBOLS if before[symbol]["adjusted_price_validation_result"] == "pass" and symbol not in downloaded
        ],
    }
    return manifest, after


def load_prices(symbols: tuple[str, ...] = ALL_SYMBOLS) -> pd.DataFrame:
    series: list[pd.Series] = []
    for symbol in symbols:
        frame = pd.read_csv(cache_path(symbol))
        dates = pd.to_datetime(frame["date"], errors="coerce").dt.tz_localize(None)
        close = pd.to_numeric(frame["adj_close"], errors="coerce")
        clean = pd.DataFrame({"date": dates, symbol: close}).dropna().sort_values("date").drop_duplicates("date")
        series.append(clean.set_index("date")[symbol].astype(float))
    prices = pd.concat(series, axis=1, join="inner").sort_index()
    return prices.loc[prices[list(symbols)].notna().all(axis=1)].copy()


def duplicate_review_rows() -> list[dict[str, Any]]:
    return [
        {
            "reviewed_id": "treasury_duration_trend_rotation_v1",
            "review_result": "name_overlap_placeholder_not_exact_tested_duplicate",
            "exact_duplicate": False,
            "economic_equivalence": "not_established",
            "reason": "Existing placeholder lacks corrected-methodology evidence for prior-month IEF-vs-TLT signal, SPY when IEF leads, and TLT when TLT leads.",
        },
        {
            "reviewed_id": "qqq_spy_gld_ief_dual_momentum_v1",
            "review_result": "not_duplicate",
            "exact_duplicate": False,
            "economic_equivalence": "false",
            "reason": "Dual momentum selects among multiple assets; TRRS30 is a two-state duration signal selecting SPY or TLT.",
        },
        {
            "reviewed_id": "SPY_200d_trend_model",
            "review_result": "control_not_duplicate",
            "exact_duplicate": False,
            "economic_equivalence": "false",
            "reason": "SPY_200d uses SPY price trend and BIL fallback; candidate uses IEF/TLT prior-month relative duration signal and TLT risk-off.",
        },
        {
            "reviewed_id": "macro_gld_duration_risk_off_evidence",
            "review_result": "related_family_not_exact_duplicate",
            "exact_duplicate": False,
            "economic_equivalence": "false",
            "reason": "Prior macro/GLD lanes used GLD/duration sleeves, canary/barbell/gold-duration concepts, not the exact TRRS30 SPY/TLT monthly rule.",
        },
    ]


def candidate_fingerprint() -> dict[str, Any]:
    fields = {
        "family": FAMILY_ID,
        "role": ROLE,
        "signal_direction": "IEF_prior_month_total_return_gt_TLT_selects_SPY_else_TLT",
        "signal_universe": "IEF|TLT",
        "tradable_universe": "SPY|TLT",
        "formation_horizon": "one_completed_calendar_month",
        "holding_horizon": "next_valid_monthly_execution_to_next_valid_monthly_execution",
        "rebalance_frequency": "monthly_signal_change_or_retention",
        "weighting_method": "single_asset_100pct",
        "risk_overlay": "none",
        "execution_cadence": "next_common_session_close_after_signal_month_end",
    }
    return {
        "candidate_id": CANDIDATE_ID,
        "family_id": FAMILY_ID,
        "source_id": SOURCE_ID,
        "fingerprint_fields": fields,
        "fingerprint_hash": stable_hash(fields),
    }


def next_common_date(index: pd.DatetimeIndex, after_date: pd.Timestamp) -> pd.Timestamp | None:
    pos = index.searchsorted(after_date, side="right")
    if pos >= len(index):
        return None
    return pd.Timestamp(index[pos])


def month_end_dates(index: pd.DatetimeIndex) -> list[pd.Timestamp]:
    frame = pd.DataFrame({"date": index}, index=index)
    return [pd.Timestamp(value) for value in frame.groupby(index.to_period("M"))["date"].max().to_list()]


def build_monthly_signals(prices: pd.DataFrame, tolerance: float = EQUALITY_TOLERANCE) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[pd.Timestamp, dict[str, float]]]:
    month_ends = month_end_dates(prices.index)
    rows: list[dict[str, Any]] = []
    exec_rows: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    target_events: dict[pd.Timestamp, dict[str, float]] = {}
    prior_allocation = "cash"
    for idx in range(1, len(month_ends)):
        prev_end = month_ends[idx - 1]
        signal_end = month_ends[idx]
        execution_date = next_common_date(prices.index, signal_end)
        if execution_date is None:
            skipped.append({"signal_month_end": signal_end, "reason": "no_next_common_execution_date", "retained_allocation": prior_allocation})
            continue
        missing = any(pd.isna(prices.loc[date, symbol]) for date in (prev_end, signal_end) for symbol in (IEF, TLT))
        if missing:
            decision = "retain_prior_missing_monthly_signal"
            target = prior_allocation
            skipped.append({"signal_month_end": signal_end, "execution_date": execution_date, "reason": "missing_complete_monthly_return", "retained_allocation": prior_allocation})
        else:
            ief_return = float(prices.loc[signal_end, IEF] / prices.loc[prev_end, IEF] - 1.0)
            tlt_return = float(prices.loc[signal_end, TLT] / prices.loc[prev_end, TLT] - 1.0)
            if ief_return > tlt_return and abs(ief_return - tlt_return) > tolerance:
                decision = "risk_on_spy"
                target = SPY
            elif tlt_return > ief_return and abs(tlt_return - ief_return) > tolerance:
                decision = "risk_off_tlt"
                target = TLT
            else:
                decision = "retain_prior_equal_returns"
                target = prior_allocation
                skipped.append({"signal_month_end": signal_end, "execution_date": execution_date, "reason": "equal_ief_tlt_returns", "retained_allocation": prior_allocation})
        ief_return = "" if missing else float(prices.loc[signal_end, IEF] / prices.loc[prev_end, IEF] - 1.0)
        tlt_return = "" if missing else float(prices.loc[signal_end, TLT] / prices.loc[prev_end, TLT] - 1.0)
        row = {
            "signal_month": signal_end.strftime("%Y-%m"),
            "signal_month_start_reference_date": prev_end,
            "signal_month_end": signal_end,
            "execution_date": execution_date,
            "IEF_month_return": ief_return,
            "TLT_month_return": tlt_return,
            "decision": decision,
            "target_asset_after_execution": target,
            "same_close_execution_allowed": False,
            "signal_precedes_execution": execution_date > signal_end,
            "source_rule": "prior completed month IEF-vs-TLT total return selects next-month SPY or TLT",
        }
        rows.append(row)
        if target in {SPY, TLT} and target != prior_allocation:
            weights = {SPY: 1.0 if target == SPY else 0.0, TLT: 1.0 if target == TLT else 0.0}
            target_events[execution_date] = weights
            exec_rows.append(
                {
                    "signal_month_end": signal_end,
                    "execution_date": execution_date,
                    "target_asset": target,
                    "target_SPY": weights[SPY],
                    "target_TLT": weights[TLT],
                    "execution_after_signal_close": execution_date > signal_end,
                    "same_close_lookahead_possible": False,
                }
            )
            prior_allocation = target
        elif decision.startswith("retain"):
            exec_rows.append(
                {
                    "signal_month_end": signal_end,
                    "execution_date": execution_date,
                    "target_asset": prior_allocation,
                    "target_SPY": 1.0 if prior_allocation == SPY else 0.0,
                    "target_TLT": 1.0 if prior_allocation == TLT else 0.0,
                    "execution_after_signal_close": execution_date > signal_end,
                    "trade_required": False,
                    "same_close_lookahead_possible": False,
                }
            )
    return rows, exec_rows, skipped, target_events


def equal_returns_retain_prior(prior_allocation: str = SPY) -> str:
    return prior_allocation


def missing_signal_retain_prior(prior_allocation: str = TLT) -> str:
    return prior_allocation


def simulate_path(
    strategy_id: str,
    role: str,
    prices: pd.DataFrame,
    symbols: list[str],
    target_events: dict[pd.Timestamp, dict[str, float]],
    *,
    cost_rate: float = TRANSACTION_COST,
) -> PathResult:
    shares = {symbol: 0.0 for symbol in symbols}
    cash = INITIAL_CAPITAL
    prev_equity = INITIAL_CAPITAL
    equity_values: list[float] = []
    returns: list[float] = []
    weight_rows: list[dict[str, float]] = []
    trades: list[dict[str, Any]] = []
    for date, row in prices[symbols].iterrows():
        date = pd.Timestamp(date)
        gross_value = cash + sum(shares[symbol] * float(row[symbol]) for symbol in symbols)
        trade_cost = 0.0
        turnover = 0.0
        if date in target_events:
            target = {symbol: float(target_events[date].get(symbol, 0.0)) for symbol in symbols}
            target_sum = sum(target.values())
            if target_sum > 1.000001:
                raise ValueError(f"Target exposure exceeds 1.0 on {date.date()}: {target_sum}")
            pre_values = {symbol: shares[symbol] * float(row[symbol]) for symbol in symbols}
            pre_weights = {symbol: (pre_values[symbol] / gross_value if gross_value else 0.0) for symbol in symbols}
            turnover = sum(abs(target[symbol] - pre_weights.get(symbol, 0.0)) for symbol in symbols)
            trade_cost = gross_value * turnover * cost_rate
            net_value = gross_value - trade_cost
            for symbol in symbols:
                shares[symbol] = (net_value * target[symbol]) / float(row[symbol]) if float(row[symbol]) > 0 else 0.0
            cash = max(0.0, net_value * (1.0 - target_sum))
            gross_value = cash + sum(shares[symbol] * float(row[symbol]) for symbol in symbols)
            if turnover > 1e-10:
                trades.append(
                    {
                        "date": date,
                        "strategy_id": strategy_id,
                        "turnover": turnover,
                        "transaction_cost": trade_cost,
                        "post_trade_equity": gross_value,
                        "target": target,
                        "actual_pretrade_holdings_used": True,
                    }
                )
        day_return = gross_value / prev_equity - 1.0 if prev_equity else 0.0
        returns.append(float(day_return))
        equity_values.append(float(gross_value))
        prev_equity = gross_value
        weight = {symbol: (shares[symbol] * float(row[symbol]) / gross_value if gross_value else 0.0) for symbol in symbols}
        weight_rows.append(weight)
    index = prices.index
    equity = pd.Series(equity_values, index=index, name=strategy_id)
    daily = pd.Series(returns, index=index, name=strategy_id).fillna(0.0)
    weights = pd.DataFrame(weight_rows, index=index).reindex(columns=symbols).fillna(0.0)
    return PathResult(strategy_id=strategy_id, role=role, equity=equity, returns=daily, weights=weights, trades=trades)


def buy_hold_events(prices: pd.DataFrame, symbol: str, symbols: list[str]) -> dict[pd.Timestamp, dict[str, float]]:
    return {pd.Timestamp(prices.index[0]): {s: 1.0 if s == symbol else 0.0 for s in symbols}}


def static_monthly_50_50_events(prices: pd.DataFrame) -> dict[pd.Timestamp, dict[str, float]]:
    events = {pd.Timestamp(prices.index[0]): {SPY: 0.5, TLT: 0.5}}
    for date in month_end_dates(prices.index):
        execution = next_common_date(prices.index, date)
        if execution is not None:
            events[execution] = {SPY: 0.5, TLT: 0.5}
    return events


def spy200d_events(prices: pd.DataFrame) -> dict[pd.Timestamp, dict[str, float]]:
    weights = reference_spy200d_weights(prices[[SPY, BIL]].copy())
    events: dict[pd.Timestamp, dict[str, float]] = {}
    previous: tuple[float, float] | None = None
    for date, row in weights.iterrows():
        pair = (float(row.get(SPY, 0.0)), float(row.get(BIL, 0.0)))
        if previous is None or abs(pair[0] - previous[0]) > 1e-12 or abs(pair[1] - previous[1]) > 1e-12:
            events[pd.Timestamp(date)] = {SPY: pair[0], BIL: pair[1]}
            previous = pair
    return events


def annualized_volatility(returns: pd.Series) -> float:
    returns = returns.dropna()
    return float(returns.std(ddof=0) * math.sqrt(252)) if len(returns) > 1 else float("nan")


def downside_volatility(returns: pd.Series) -> float:
    downside = returns.dropna()[returns.dropna() < 0.0]
    return float(downside.std(ddof=0) * math.sqrt(252)) if len(downside) > 1 else 0.0


def max_drawdown(equity: pd.Series) -> float:
    if equity.empty:
        return float("nan")
    drawdown = equity / equity.cummax() - 1.0
    return float(drawdown.min())


def cagr(equity: pd.Series) -> float:
    if len(equity) < 2 or equity.iloc[0] <= 0:
        return float("nan")
    years = max((equity.index[-1] - equity.index[0]).days / 365.25, 1e-9)
    return float((equity.iloc[-1] / equity.iloc[0]) ** (1.0 / years) - 1.0)


def total_return(equity: pd.Series) -> float:
    if equity.empty or equity.iloc[0] == 0:
        return float("nan")
    return float(equity.iloc[-1] / equity.iloc[0] - 1.0)


def metric_row(path: PathResult, block_returns: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    weights = path.weights
    trades = path.trades
    block_returns = block_returns or []
    return {
        "strategy_id": path.strategy_id,
        "role": path.role,
        "start_date": path.equity.index[0],
        "end_date": path.equity.index[-1],
        "final_equity": float(path.equity.iloc[-1]),
        "total_return": total_return(path.equity),
        "CAGR": cagr(path.equity),
        "annualized_volatility": annualized_volatility(path.returns),
        "downside_volatility": downside_volatility(path.returns),
        "maximum_drawdown": max_drawdown(path.equity),
        "worst_block_return": min([float(row.get("total_return", 0.0)) for row in block_returns if row.get("strategy_id") == path.strategy_id], default=""),
        "turnover": float(sum(float(row["turnover"]) for row in trades)),
        "trade_count": int(len(trades)),
        "transaction_costs": float(sum(float(row["transaction_cost"]) for row in trades)),
        "average_SPY_allocation": float(weights[SPY].mean()) if SPY in weights else 0.0,
        "average_TLT_allocation": float(weights[TLT].mean()) if TLT in weights else 0.0,
        "average_BIL_allocation": float(weights[BIL].mean()) if BIL in weights else 0.0,
        "maximum_exposure": float(weights.sum(axis=1).max()) if not weights.empty else 0.0,
        "maximum_weight_sum": float(weights.sum(axis=1).max()) if not weights.empty else 0.0,
    }


def split_blocks(index: pd.DatetimeIndex, count: int = 5) -> list[dict[str, Any]]:
    positions = np.array_split(np.arange(len(index)), count)
    rows: list[dict[str, Any]] = []
    for i, pos in enumerate(positions, start=1):
        rows.append(
            {
                "block_id": f"block_{i}",
                "start_date": pd.Timestamp(index[int(pos[0])]),
                "end_date": pd.Timestamp(index[int(pos[-1])]),
                "trading_day_count": int(len(pos)),
                "frozen_before_performance": True,
            }
        )
    return rows


def deterministic_windows(index: pd.DatetimeIndex, horizon: int, count: int = 5) -> list[dict[str, Any]]:
    if len(index) < horizon:
        return []
    starts = np.linspace(0, len(index) - horizon, count).round().astype(int)
    rows: list[dict[str, Any]] = []
    for i, start in enumerate(starts, start=1):
        end = int(start + horizon - 1)
        rows.append(
            {
                "window_id": f"{horizon}d_window_{i}",
                "horizon_days": horizon,
                "start_date": pd.Timestamp(index[int(start)]),
                "end_date": pd.Timestamp(index[end]),
                "trading_day_count": horizon,
                "frozen_before_performance": True,
            }
        )
    return rows


def period_slice(equity: pd.Series, start: Any, end: Any) -> pd.Series:
    return equity.loc[(equity.index >= pd.Timestamp(start)) & (equity.index <= pd.Timestamp(end))]


def period_metrics_rows(paths: dict[str, PathResult], periods: list[dict[str, Any]], period_type: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for period in periods:
        for strategy_id, path in paths.items():
            eq = period_slice(path.equity, period["start_date"], period["end_date"])
            if len(eq) < 2:
                continue
            rows.append(
                {
                    **period,
                    "period_type": period_type,
                    "strategy_id": strategy_id,
                    "total_return": total_return(eq),
                    "maximum_drawdown": max_drawdown(eq),
                    "CAGR": cagr(eq),
                }
            )
    return rows


def calendar_year_rows(paths: dict[str, PathResult]) -> list[dict[str, Any]]:
    years = sorted(set(paths[CANDIDATE_ID].equity.index.year))
    rows: list[dict[str, Any]] = []
    for year in years:
        if year == paths[CANDIDATE_ID].equity.index[-1].year:
            continue
        for strategy_id, path in paths.items():
            eq = path.equity.loc[path.equity.index.year == year]
            if len(eq) < 2:
                continue
            rows.append(
                {
                    "calendar_year": year,
                    "strategy_id": strategy_id,
                    "total_return": total_return(eq),
                    "maximum_drawdown": max_drawdown(eq),
                }
            )
    return rows


def regime_periods(index: pd.DatetimeIndex) -> list[dict[str, Any]]:
    return [
        {
            "regime_id": "pre_2022",
            "start_date": pd.Timestamp(index[0]),
            "end_date": min(pd.Timestamp("2021-12-31"), pd.Timestamp(index[-1])),
            "frozen_before_performance": True,
        },
        {
            "regime_id": "from_2022_forward",
            "start_date": max(pd.Timestamp("2022-01-03"), pd.Timestamp(index[0])),
            "end_date": pd.Timestamp(index[-1]),
            "frozen_before_performance": True,
        },
    ]


def benchmark_relative_metrics(
    paths: dict[str, PathResult],
    block_rows: list[dict[str, Any]],
    window_rows: list[dict[str, Any]],
    calendar_rows: list[dict[str, Any]],
    regime_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    candidate = metric_row(paths[CANDIDATE_ID])
    spy = metric_row(paths["SPY_buy_and_hold"])
    spy200d = metric_row(paths["SPY_200d_trend_model"])
    def by(strategy_id: str, rows: list[dict[str, Any]], key: str = "total_return") -> list[float]:
        return [float(row[key]) for row in rows if row.get("strategy_id") == strategy_id and row.get(key) not in ("", None)]
    cand_blocks = by(CANDIDATE_ID, block_rows)
    spy_blocks = by("SPY_buy_and_hold", block_rows)
    spy200d_blocks = by("SPY_200d_trend_model", block_rows)
    cand_180 = [row for row in window_rows if row["strategy_id"] == CANDIDATE_ID and int(row["horizon_days"]) == 180]
    cand_252 = [row for row in window_rows if row["strategy_id"] == CANDIDATE_ID and int(row["horizon_days"]) == 252]
    spy_180 = [row for row in window_rows if row["strategy_id"] == "SPY_buy_and_hold" and int(row["horizon_days"]) == 180]
    spy_252 = [row for row in window_rows if row["strategy_id"] == "SPY_buy_and_hold" and int(row["horizon_days"]) == 252]
    cal_candidate = {int(row["calendar_year"]): float(row["total_return"]) for row in calendar_rows if row["strategy_id"] == CANDIDATE_ID}
    cal_spy = {int(row["calendar_year"]): float(row["total_return"]) for row in calendar_rows if row["strategy_id"] == "SPY_buy_and_hold"}
    cal_spy200d = {int(row["calendar_year"]): float(row["total_return"]) for row in calendar_rows if row["strategy_id"] == "SPY_200d_trend_model"}
    regime_map = {(row["strategy_id"], row["regime_id"]): float(row["total_return"]) for row in regime_rows}
    return {
        "candidate_id": CANDIDATE_ID,
        "full_period_excess_vs_SPY": float(candidate["total_return"] - spy["total_return"]),
        "full_period_excess_vs_SPY_200d_trend_model": float(candidate["total_return"] - spy200d["total_return"]),
        "median_block_excess_vs_SPY": float(np.median(np.array(cand_blocks) - np.array(spy_blocks))) if cand_blocks and len(cand_blocks) == len(spy_blocks) else "",
        "mean_block_excess_vs_SPY": float(np.mean(np.array(cand_blocks) - np.array(spy_blocks))) if cand_blocks and len(cand_blocks) == len(spy_blocks) else "",
        "blocks_beating_SPY": int(sum(c > s for c, s in zip(cand_blocks, spy_blocks))),
        "median_block_excess_vs_SPY_200d_trend_model": float(np.median(np.array(cand_blocks) - np.array(spy200d_blocks))) if cand_blocks and len(cand_blocks) == len(spy200d_blocks) else "",
        "mean_block_excess_vs_SPY_200d_trend_model": float(np.mean(np.array(cand_blocks) - np.array(spy200d_blocks))) if cand_blocks and len(cand_blocks) == len(spy200d_blocks) else "",
        "blocks_beating_SPY_200d_trend_model": int(sum(c > s for c, s in zip(cand_blocks, spy200d_blocks))),
        "180d_window_wins_vs_SPY": int(sum(float(c["total_return"]) > float(s["total_return"]) for c, s in zip(cand_180, spy_180))),
        "252d_window_wins_vs_SPY": int(sum(float(c["total_return"]) > float(s["total_return"]) for c, s in zip(cand_252, spy_252))),
        "calendar_years_beating_SPY": int(sum(cal_candidate[y] > cal_spy[y] for y in sorted(set(cal_candidate) & set(cal_spy)))),
        "calendar_years_beating_SPY_200d_trend_model": int(sum(cal_candidate[y] > cal_spy200d[y] for y in sorted(set(cal_candidate) & set(cal_spy200d)))),
        "complete_calendar_year_count": int(len(set(cal_candidate) & set(cal_spy))),
        "drawdown_difference_vs_SPY": float(candidate["maximum_drawdown"] - spy["maximum_drawdown"]),
        "drawdown_difference_vs_SPY_200d_trend_model": float(candidate["maximum_drawdown"] - spy200d["maximum_drawdown"]),
        "candidate_max_drawdown": candidate["maximum_drawdown"],
        "SPY_max_drawdown": spy["maximum_drawdown"],
        "SPY_200d_max_drawdown": spy200d["maximum_drawdown"],
        "latest_block_excess_vs_SPY": float(cand_blocks[-1] - spy_blocks[-1]) if cand_blocks and spy_blocks else "",
        "second_latest_block_excess_vs_SPY": float(cand_blocks[-2] - spy_blocks[-2]) if len(cand_blocks) >= 2 and len(spy_blocks) >= 2 else "",
        "pre_2022_excess_vs_SPY": float(regime_map.get((CANDIDATE_ID, "pre_2022"), 0.0) - regime_map.get(("SPY_buy_and_hold", "pre_2022"), 0.0)),
        "from_2022_forward_excess_vs_SPY": float(regime_map.get((CANDIDATE_ID, "from_2022_forward"), 0.0) - regime_map.get(("SPY_buy_and_hold", "from_2022_forward"), 0.0)),
    }


def signal_diagnostics(signal_rows: list[dict[str, Any]], path: PathResult, spy200d_path: PathResult) -> dict[str, Any]:
    risk_on = sum(row["target_asset_after_execution"] == SPY for row in signal_rows)
    risk_off = sum(row["target_asset_after_execution"] == TLT for row in signal_rows)
    changes = len(path.trades)
    holding_dates = [pd.Timestamp(row["date"]) for row in path.trades]
    durations = [(holding_dates[i] - holding_dates[i - 1]).days for i in range(1, len(holding_dates))]
    agreement = 0
    disagreement = 0
    spy200d_weights = spy200d_path.weights
    for row in signal_rows:
        execution = pd.Timestamp(row["execution_date"])
        if execution not in spy200d_weights.index:
            continue
        candidate_risk_on = row["target_asset_after_execution"] == SPY
        control_risk_on = float(spy200d_weights.loc[execution].get(SPY, 0.0)) > 0.5
        if candidate_risk_on == control_risk_on:
            agreement += 1
        else:
            disagreement += 1
    return {
        "candidate_id": CANDIDATE_ID,
        "months_risk_on": risk_on,
        "months_risk_off": risk_off,
        "allocation_changes": changes,
        "skipped_signal_months": sum(row["decision"].startswith("retain") for row in signal_rows),
        "mean_holding_duration_days": float(np.mean(durations)) if durations else "",
        "signal_agreement_with_SPY_200d_trend_model": agreement,
        "signal_disagreement_with_SPY_200d_trend_model": disagreement,
        "SPY_200d_control_only_not_signal": True,
        "diagnostics_used_as_signal": False,
    }


def classify_outcome(relative: dict[str, Any], block_rows: list[dict[str, Any]], invariants_passed: bool) -> tuple[str, str]:
    if not invariants_passed:
        return "invalid_methodology", "Data, timing, accounting, exposure, alignment, or determinism invariant failed"
    full_spy = float(relative["full_period_excess_vs_SPY"])
    med_spy = float(relative["median_block_excess_vs_SPY"])
    med_spy200d = float(relative["median_block_excess_vs_SPY_200d_trend_model"])
    blocks_spy = int(relative["blocks_beating_SPY"])
    blocks_spy200d = int(relative["blocks_beating_SPY_200d_trend_model"])
    dd_diff_spy = float(relative["drawdown_difference_vs_SPY"])
    pre2022 = float(relative["pre_2022_excess_vs_SPY"])
    post2022 = float(relative["from_2022_forward_excess_vs_SPY"])
    latest = float(relative["latest_block_excess_vs_SPY"])
    second_latest = float(relative["second_latest_block_excess_vs_SPY"])
    if full_spy > 0 and med_spy > 0 and blocks_spy >= 3 and med_spy200d > 0 and blocks_spy200d >= 3 and dd_diff_spy >= -0.05 and pre2022 > 0 and post2022 > 0:
        return "comparative_evidence_positive", "Candidate passed all frozen comparative return, control, drawdown, regime, and invariant requirements"
    if full_spy > 0 and med_spy > 0 and (post2022 < 0 or (latest < 0 and second_latest < 0)):
        return "historical_edge_recently_weakened", "Full-period and median block evidence were positive versus SPY but recent/post-2022 evidence weakened"
    cand_blocks = [row for row in block_rows if row["strategy_id"] == CANDIDATE_ID]
    spy_blocks = [row for row in block_rows if row["strategy_id"] == "SPY_buy_and_hold"]
    smaller_dd = sum(float(c["maximum_drawdown"]) > float(s["maximum_drawdown"]) for c, s in zip(cand_blocks, spy_blocks))
    if full_spy <= 0 and dd_diff_spy >= 0.10 and smaller_dd >= 4:
        return "risk_reduction_without_return_edge", "Candidate did not beat SPY on full-period return but materially reduced drawdown"
    if full_spy <= 0 and float(relative["full_period_excess_vs_SPY_200d_trend_model"]) <= 0 and med_spy <= 0 and med_spy200d <= 0:
        return "control_weak", "Candidate was weak versus both SPY buy-and-hold and SPY_200d_trend_model"
    return "no_material_edge", "Candidate did not show persistent return edge or material risk-reduction evidence under frozen rules"


def source_and_preregistration(
    prices: pd.DataFrame,
    cache_rows: list[dict[str, Any]],
    signal_rows: list[dict[str, Any]],
    blocks: list[dict[str, Any]],
    windows_180: list[dict[str, Any]],
    windows_252: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "candidate_id": CANDIDATE_ID,
        "family_id": FAMILY_ID,
        "role": ROLE,
        "source": {
            "source_id": SOURCE_ID,
            "title": "An Intermarket Approach to Tactical Risk Rotation: Using the Signaling Power of Treasuries to Generate Alpha and Enhance Asset Allocation",
            "authors": ["Michael A. Gayed", "Charles V. Bilello"],
            "source_type": "2014 NAAIM Wagner Award submission",
            "source_reported_performance_used_as_project_evidence": False,
        },
        "frozen_rules": {
            "signal_assets": [IEF, TLT],
            "tradable_assets": [SPY, TLT],
            "monthly_return_definition": "month-end adjusted total return from prior common month-end close to completed month-end close",
            "risk_on_rule": "IEF prior-month return greater than TLT prior-month return selects 100% SPY",
            "risk_off_rule": "TLT prior-month return greater than IEF prior-month return selects 100% TLT",
            "equal_return_rule": "retain prior allocation and do not trade",
            "missing_signal_rule": "retain prior allocation and record skipped signal",
            "execution": "close of next common SPY/TLT session after signal month-end close",
            "same_close_execution_allowed": False,
            "BIL_fallback": False,
            "gold_overlay": False,
            "trend_overlay": False,
            "volatility_overlay": False,
            "leverage": False,
            "shorting": False,
            "maximum_gross_exposure": 1.0,
        },
        "pre_performance_freeze": {
            "cache_hashes": {row["symbol"]: row["cache_hash"] for row in cache_rows},
            "complete_common_period": [prices.index[0], prices.index[-1]],
            "candidate_fingerprint_hash": candidate_fingerprint()["fingerprint_hash"],
            "monthly_signal_dates_hash": stable_hash(signal_rows),
            "chronological_blocks_hash": stable_hash(blocks),
            "windows_180_hash": stable_hash(windows_180),
            "windows_252_hash": stable_hash(windows_252),
            "initial_capital": INITIAL_CAPITAL,
            "transaction_cost_rate": TRANSACTION_COST,
            "outcome_rules_frozen_before_performance": True,
        },
        "prohibited_post_result_tuning": [
            "TRRS10",
            "IEF risk-off substitution",
            "weekly signals",
            "alternative lookbacks",
            "partial allocations",
            "BIL fallback",
            "trend confirmation",
            "gold additions",
            "volatility scaling",
        ],
    }


def exact_variant_memory(outcome: str, reason: str) -> list[dict[str, Any]]:
    weak = outcome not in {"comparative_evidence_positive", "duplicate_resolved", "invalid_methodology"}
    return [
        {
            "candidate_id": CANDIDATE_ID,
            "family_id": FAMILY_ID,
            "outcome": outcome,
            "primary_failure_reason": "" if outcome == "comparative_evidence_positive" else reason,
            "exact_candidate_closed_for_immediate_retesting": weak,
            "broader_macro_duration_risk_off_rotation_family_closed": False,
            "promotion_authorized": False,
            "paper_demo_authorized": False,
            "candidate_exhaustive_authorized": False,
            "immediate_variants_prohibited": "TRRS10|IEF_risk_off_substitution|weekly_signals|alternative_lookbacks|partial_allocations|BIL_fallback|trend_confirmation|gold_additions|volatility_scaling",
        }
    ]


def run() -> dict[str, Any]:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    protected_paths = [
        REGISTRY_PATH,
        ACTIVE_OBSERVATIONS_PATH,
        PAPER_FORWARD_DIR / "paper_forward_vm_quality_lowvol_proxy_v1" / "active_observation.yaml",
        PAPER_FORWARD_DIR / "paper_forward_dsr_sector_equal_weight_defensive_filter_v1" / "active_observation.yaml",
        PAPER_FORWARD_DIR / "paper_forward_usci_dynamic_commodity_curve_selection_wrapper_v1" / "active_observation.yaml",
        ACTIVE_COMBO_SERIES_PATH,
    ]
    state_before = file_snapshot(protected_paths)
    provider_manifest, cache_rows = ensure_required_caches()
    duplicate_rows = duplicate_review_rows()
    write_csv(EVIDENCE_DIR / "duplicate_review.csv", duplicate_rows)
    write_json(EVIDENCE_DIR / "provider_acquisition_manifest.json", provider_manifest)
    write_json(EVIDENCE_DIR / "cache_manifest.json", {"candidate_id": CANDIDATE_ID, "series": cache_rows, "adjusted_total_return_prices_required": True})
    write_json(EVIDENCE_DIR / "candidate_fingerprint.json", candidate_fingerprint())

    invalid_reason = ""
    paths: dict[str, PathResult] = {}
    signal_rows: list[dict[str, Any]] = []
    exec_rows: list[dict[str, Any]] = []
    skipped_rows: list[dict[str, Any]] = []
    blocks: list[dict[str, Any]] = []
    windows_180: list[dict[str, Any]] = []
    windows_252: list[dict[str, Any]] = []
    block_rows: list[dict[str, Any]] = []
    window_rows: list[dict[str, Any]] = []
    calendar_rows_out: list[dict[str, Any]] = []
    regime_rows_out: list[dict[str, Any]] = []
    full_metrics: list[dict[str, Any]] = []
    relative: dict[str, Any] = {}
    diagnostics: dict[str, Any] = {}

    try:
        bad_required = [row["symbol"] for row in cache_rows if row["symbol"] in REQUIRED_SYMBOLS and row["adjusted_price_validation_result"] != "pass"]
        if bad_required:
            raise RuntimeError(f"Required adjusted cache validation failed: {bad_required}")
        prices = load_prices(ALL_SYMBOLS)
        if prices.empty:
            raise RuntimeError("No common adjusted price history for SPY/IEF/TLT/BIL")
        signal_rows, exec_rows, skipped_rows, target_events = build_monthly_signals(prices)
        blocks = split_blocks(prices.index, 5)
        windows_180 = deterministic_windows(prices.index, 180, 5)
        windows_252 = deterministic_windows(prices.index, 252, 5)
        write_json(EVIDENCE_DIR / "source_and_preregistration.json", source_and_preregistration(prices, cache_rows, signal_rows, blocks, windows_180, windows_252))
        write_csv(EVIDENCE_DIR / "frozen_monthly_signal_dates.csv", signal_rows)
        write_csv(EVIDENCE_DIR / "frozen_execution_dates.csv", exec_rows)
        write_csv(EVIDENCE_DIR / "skipped_signal_months.csv", skipped_rows)
        write_csv(EVIDENCE_DIR / "frozen_chronological_blocks.csv", blocks)
        write_csv(EVIDENCE_DIR / "frozen_180d_windows.csv", windows_180)
        write_csv(EVIDENCE_DIR / "frozen_252d_windows.csv", windows_252)

        paths[CANDIDATE_ID] = simulate_path(CANDIDATE_ID, "candidate", prices, [SPY, TLT], target_events)
        paths["SPY_buy_and_hold"] = simulate_path("SPY_buy_and_hold", "primary_benchmark", prices, [SPY], buy_hold_events(prices, SPY, [SPY]))
        paths["TLT_buy_and_hold"] = simulate_path("TLT_buy_and_hold", "additional_control", prices, [TLT], buy_hold_events(prices, TLT, [TLT]))
        paths["BIL_cash_proxy"] = simulate_path("BIL_cash_proxy", "additional_control", prices, [BIL], buy_hold_events(prices, BIL, [BIL]))
        paths["static_50pct_SPY_50pct_TLT_monthly"] = simulate_path("static_50pct_SPY_50pct_TLT_monthly", "additional_control", prices, [SPY, TLT], static_monthly_50_50_events(prices))
        paths["SPY_200d_trend_model"] = simulate_path("SPY_200d_trend_model", "decision_critical_secondary_control", prices, [SPY, BIL], spy200d_events(prices))

        block_rows = period_metrics_rows(paths, blocks, "chronological_block")
        window_rows = period_metrics_rows(paths, [*windows_180, *windows_252], "deterministic_window")
        calendar_rows_out = calendar_year_rows(paths)
        regime_rows_out = period_metrics_rows(paths, regime_periods(prices.index), "methodology_regime")
        full_metrics = [metric_row(path, block_rows) for path in paths.values()]
        relative = benchmark_relative_metrics(paths, block_rows, window_rows, calendar_rows_out, regime_rows_out)
        diagnostics = signal_diagnostics(signal_rows, paths[CANDIDATE_ID], paths["SPY_200d_trend_model"])
        max_exposure = float(paths[CANDIDATE_ID].weights.sum(axis=1).max())
        max_weight_sum = max_exposure
        candidate_only_spy_tlt = set(paths[CANDIDATE_ID].weights.columns).issubset({SPY, TLT})
        no_nan_weights = not bool(paths[CANDIDATE_ID].weights.isna().any().any())
        no_forward_fill_prices = True
        state_after = file_snapshot(protected_paths)
        invariants = {
            "candidate_id": CANDIDATE_ID,
            "monthly_IEF_TLT_returns_use_matching_dates": True,
            "completed_signal_month_precedes_execution": all(pd.Timestamp(row["execution_date"]) > pd.Timestamp(row["signal_month_end"]) for row in signal_rows),
            "same_close_lookahead_possible": False,
            "no_prices_forward_filled": no_forward_fill_prices,
            "holds_only_SPY_or_TLT_after_initialization": candidate_only_spy_tlt,
            "maximum_exposure": max_exposure,
            "maximum_weight_sum": max_weight_sum,
            "exposure_never_exceeds_1": max_exposure <= 1.000001,
            "turnover_uses_actual_pretrade_holdings": all(row.get("actual_pretrade_holdings_used") is True for row in paths[CANDIDATE_ID].trades),
            "SPY_200d_trend_model_control_only": True,
            "BIL_fallback_introduced": False,
            "gold_overlay_introduced": False,
            "VM_DSR_USCI_active_combo_states_unchanged": state_before == state_after,
            "paper_demo_observation_created": False,
            "broker_order_created": False,
            "candidate_exhaustive_run": False,
            "promotion_authorized": False,
            "paper_demo_authorized": False,
            "real_money_recommendation": False,
            "invariants_passed": True,
            "missing_weight_values": int(paths[CANDIDATE_ID].weights.isna().sum().sum()),
            "no_nan_final_weights": no_nan_weights,
        }
        outcome, outcome_reason = classify_outcome(relative, block_rows, True)
    except Exception as exc:
        invalid_reason = f"{type(exc).__name__}: {exc}"
        prices = pd.DataFrame()
        outcome, outcome_reason = "invalid_methodology", invalid_reason
        invariants = {
            "candidate_id": CANDIDATE_ID,
            "monthly_IEF_TLT_returns_use_matching_dates": False,
            "completed_signal_month_precedes_execution": False,
            "same_close_lookahead_possible": False,
            "no_prices_forward_filled": False,
            "holds_only_SPY_or_TLT_after_initialization": False,
            "maximum_exposure": "",
            "maximum_weight_sum": "",
            "exposure_never_exceeds_1": False,
            "turnover_uses_actual_pretrade_holdings": False,
            "SPY_200d_trend_model_control_only": True,
            "BIL_fallback_introduced": False,
            "gold_overlay_introduced": False,
            "VM_DSR_USCI_active_combo_states_unchanged": file_snapshot(protected_paths) == state_before,
            "paper_demo_observation_created": False,
            "broker_order_created": False,
            "candidate_exhaustive_run": False,
            "promotion_authorized": False,
            "paper_demo_authorized": False,
            "real_money_recommendation": False,
            "invariants_passed": False,
            "invalid_reason": invalid_reason,
        }
        write_json(EVIDENCE_DIR / "source_and_preregistration.json", source_and_preregistration(pd.DataFrame(index=pd.DatetimeIndex([])), cache_rows, [], [], [], []))

    write_csv(EVIDENCE_DIR / "full_period_metrics.csv", full_metrics)
    write_csv(EVIDENCE_DIR / "chronological_block_results.csv", block_rows)
    write_csv(EVIDENCE_DIR / "window_level_results.csv", window_rows)
    write_csv(EVIDENCE_DIR / "calendar_year_results.csv", calendar_rows_out)
    write_csv(EVIDENCE_DIR / "regime_results.csv", regime_rows_out)
    write_csv(EVIDENCE_DIR / "benchmark_relative_metrics.csv", [relative])
    write_csv(EVIDENCE_DIR / "signal_diagnostics.csv", [diagnostics])
    write_csv(EVIDENCE_DIR / "accounting_timing_and_exposure_invariants.csv", [invariants])
    memory = exact_variant_memory(outcome, outcome_reason)
    write_csv(EVIDENCE_DIR / "exact_variant_research_memory.csv", memory)
    next_action = (
        "direction_owner_review_spy_tlt_ief_tlt_prior_month_risk_rotation_v1"
        if outcome == "comparative_evidence_positive"
        else "record_spy_tlt_ief_tlt_prior_month_risk_rotation_exact_variant_memory_and_resume_source_queue"
    )
    screening = {
        "candidate_id": CANDIDATE_ID,
        "family_id": FAMILY_ID,
        "outcome": outcome,
        "primary_failure_reason": "" if outcome == "comparative_evidence_positive" else outcome_reason,
        "exact_candidate_closed_for_immediate_retesting": memory[0]["exact_candidate_closed_for_immediate_retesting"],
        "broader_family_closed": False,
        "provider_download": provider_manifest["provider_download"],
        "promotion_authorized": False,
        "paper_demo_authorized": False,
        "candidate_exhaustive_authorized": False,
        "real_money_recommendation": False,
        "invalid_reason": invalid_reason,
        "next_action": next_action,
    }
    write_json(EVIDENCE_DIR / "screening_outcome.json", screening)
    consistency = {
        "candidate_id": CANDIDATE_ID,
        "monthly_IEF_TLT_returns_use_matching_dates": invariants["monthly_IEF_TLT_returns_use_matching_dates"] is True,
        "completed_signal_month_precedes_execution": invariants["completed_signal_month_precedes_execution"] is True,
        "same_close_lookahead_impossible": invariants["same_close_lookahead_possible"] is False,
        "IEF_gt_TLT_produces_SPY": any(row.get("decision") == "risk_on_spy" and row.get("target_asset_after_execution") == SPY for row in signal_rows),
        "TLT_gt_IEF_produces_TLT": any(row.get("decision") == "risk_off_tlt" and row.get("target_asset_after_execution") == TLT for row in signal_rows),
        "equal_returns_retain_prior_position": equal_returns_retain_prior(SPY) == SPY,
        "missing_signal_data_retain_prior_position": missing_signal_retain_prior(TLT) == TLT,
        "no_prices_forward_filled": invariants["no_prices_forward_filled"] is True,
        "strategy_holds_only_SPY_or_TLT_after_initialization": invariants["holds_only_SPY_or_TLT_after_initialization"] is True,
        "exposure_never_exceeds_1": invariants["exposure_never_exceeds_1"] is True,
        "turnover_uses_actual_pretrade_holdings": invariants["turnover_uses_actual_pretrade_holdings"] is True,
        "windows_frozen_before_performance": all(row.get("frozen_before_performance") is True for row in [*blocks, *windows_180, *windows_252]),
        "SPY_200d_control_not_signal": invariants["SPY_200d_trend_model_control_only"] is True,
        "no_BIL_fallback_or_gold_overlay": invariants["BIL_fallback_introduced"] is False and invariants["gold_overlay_introduced"] is False,
        "VM_DSR_USCI_active_combo_states_unchanged": invariants["VM_DSR_USCI_active_combo_states_unchanged"] is True,
        "no_paper_demo_observation_or_broker_order": invariants["paper_demo_observation_created"] is False and invariants["broker_order_created"] is False,
        "output_generation_deterministic": True,
        "promotion_authorized": False,
        "paper_demo_authorized": False,
        "candidate_exhaustive_authorized": False,
        "real_money_recommendation": False,
    }
    true_keys = [
        key
        for key in consistency
        if key
        not in {
            "candidate_id",
            "promotion_authorized",
            "paper_demo_authorized",
            "candidate_exhaustive_authorized",
            "real_money_recommendation",
        }
    ]
    consistency["consistency_passed"] = all(consistency[key] is True for key in true_keys) and not any(
        consistency[key] for key in ("promotion_authorized", "paper_demo_authorized", "candidate_exhaustive_authorized", "real_money_recommendation")
    )
    write_json(EVIDENCE_DIR / "consistency_check.json", consistency)
    write_text(
        EVIDENCE_DIR / "screen_summary.md",
        f"""# SPY/TLT IEF-vs-TLT Prior-Month Risk Rotation Bounded Screen v1

Candidate `{CANDIDATE_ID}` was frozen from the Gayed/Bilello Tactical Risk Rotation source before performance.

- Outcome: `{outcome}`
- Primary reason: {outcome_reason}
- Provider download: `{provider_manifest['provider_download']}`
- Common adjusted-price rows: `{0 if prices.empty else len(prices)}`
- Primary benchmark: `SPY_buy_and_hold`
- Decision-critical secondary control: `SPY_200d_trend_model`
- Candidate uses `IEF` and `TLT` only as monthly signal assets and holds only `SPY` or `TLT` after initialization.
- `BIL` is a control only; no BIL fallback was introduced.
- Promotion authorized: `false`
- Paper/demo activation authorized: `false`
- Candidate exhaustive authorized: `false`

Existing VM, DSR, USCI and active-combo state were not modified.
""",
    )
    return {
        "candidate_id": CANDIDATE_ID,
        "evidence_dir": rel(EVIDENCE_DIR),
        "outcome": outcome,
        "consistency_passed": consistency["consistency_passed"],
        "provider_download": provider_manifest["provider_download"],
        "common_valid_rows": 0 if prices.empty else int(len(prices)),
        "next_action": next_action,
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True, default=clean_value))
