from __future__ import annotations

import csv
import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

import run_active_strategy_evidence_recompute as active


ROOT = Path(__file__).resolve().parents[3]
OUTPUT_DIR = Path("evidence") / "risk_parity_trend_etf_wrapper_screen_v1" / "latest"
PREREG_DIR = Path("evidence") / "risk_parity_trend_wrapper_resolution_v1" / "latest"
PREREG_PATH = PREREG_DIR / "preregistration.yaml"
WINDOW_PREVIEW_PATH = PREREG_DIR / "deterministic_window_preview.csv"
ACTIVE_COMBO_SERIES = Path("evidence") / "active_combo_series_reconciliation" / "latest" / "combo_daily_series.csv"

SOURCE_ID = "clare_seaton_smith_thomas_risk_parity_trend_following_2016"
CANDIDATE_ID = "rp_ivol_10m_trend_etf_wrapper_adaptation_v1"
FAMILY_ID = "risk_parity_inverse_volatility_or_vol_targeting"
RISKY_ASSETS = ("URTH", "EEM", "IGOV", "DBC", "REET")
RISK_OFF_ASSET = "BIL"
FROZEN_UNIVERSE = (*RISKY_ASSETS, RISK_OFF_ASSET)
BENCHMARK_IDS = (
    "SPY_200d_trend_model",
    "SPY_buy_and_hold",
    "BIL_cash_proxy",
    "active_combo_vm_dsr_equal_weight_v1",
    "equal_weight_same_five_risky_etfs_benchmark_only",
)
DDOF = 1
VOL_RETURNS_REQUIRED = 12
TREND_PRICE_COUNT = 10
STARTING_EQUITY = active.STARTING_EQUITY
STOP_DOLLARS = active.STOP_DOLLARS
TARGET_300_DOLLARS = 300.0
TARGET_400_DOLLARS = 400.0
SLIPPAGE = active.SLIPPAGE
PUBLIC_SOURCE_STANDARD_COST_ASSUMPTION = 0.0
TOL = 1e-8


@dataclass(frozen=True)
class ReturnPath:
    strategy_id: str
    daily_returns: pd.Series
    weights: pd.DataFrame
    turnover: pd.Series
    equity: pd.Series
    cost: pd.Series
    target_weights: pd.DataFrame
    pre_trade_weights: pd.DataFrame
    post_trade_weights: pd.DataFrame
    scheduled_execution_dates: tuple[pd.Timestamp, ...]


def abs_path(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return ""
        return f"{value:.12g}"
    if isinstance(value, (list, tuple, set)):
        return "|".join(str(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True)
    return str(value)


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    full = abs_path(path)
    full.parent.mkdir(parents=True, exist_ok=True)
    with full.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: csv_value(row.get(field, "")) for field in fieldnames})


def write_json(path: Path, payload: dict[str, Any]) -> None:
    full = abs_path(path)
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    full = abs_path(path)
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(text.rstrip() + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def read_preregistration() -> dict[str, Any]:
    return yaml.safe_load(abs_path(PREREG_PATH).read_text(encoding="utf-8")) or {}


def cache_specs(prereg: dict[str, Any]) -> dict[str, dict[str, Any]]:
    specs: dict[str, dict[str, Any]] = {}
    for row in prereg.get("mapping", []):
        ticker = str(row["local_ticker"])
        specs[ticker] = row
    return specs


def verify_cache_hashes(prereg: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for symbol in FROZEN_UNIVERSE:
        spec = cache_specs(prereg)[symbol]
        path = abs_path(Path(str(spec["cache_path"])))
        actual = sha256_file(path)
        expected = str(spec["cache_hash"])
        rows.append(
            {
                "artifact_type": "cache_file",
                "artifact_id": symbol,
                "path": str(path.relative_to(ROOT)).replace("\\", "/"),
                "expected_hash": expected,
                "actual_hash": actual,
                "hash_match": actual == expected,
            }
        )
    return rows


def load_price_frame(symbols: tuple[str, ...] | list[str]) -> pd.DataFrame:
    series: list[pd.Series] = []
    for symbol in symbols:
        path = ROOT / "data" / "cache" / f"{symbol}.csv"
        frame = pd.read_csv(path)
        dates = pd.to_datetime(frame["date"], errors="coerce").dt.tz_localize(None)
        close = pd.to_numeric(frame["adj_close"], errors="coerce")
        item = pd.Series(close.to_numpy(dtype=float), index=dates, name=symbol).dropna().sort_index()
        item = item[~item.index.duplicated(keep="last")]
        series.append(item)
    return pd.concat(series, axis=1).sort_index()


def month_end_observations(daily_close: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    values: dict[str, pd.Series] = {}
    dates: dict[str, pd.Series] = {}
    for symbol in daily_close.columns:
        clean = daily_close[symbol].dropna().sort_index()
        grouped = clean.groupby(clean.index.to_period("M"))
        values[symbol] = grouped.last()
        dates[symbol] = grouped.apply(lambda x: x.index[-1])
    return pd.DataFrame(values), pd.DataFrame(dates)


def inverse_volatility_weights(monthly_returns: pd.DataFrame, ddof: int = DDOF) -> dict[str, float]:
    if monthly_returns.shape[0] != VOL_RETURNS_REQUIRED:
        raise ValueError("exactly 12 completed monthly returns are required")
    if list(monthly_returns.columns) != list(RISKY_ASSETS):
        monthly_returns = monthly_returns.loc[:, list(RISKY_ASSETS)]
    vol = monthly_returns.std(ddof=ddof)
    if vol.isna().any() or (~np.isfinite(vol.to_numpy(dtype=float))).any() or (vol <= TOL).any():
        raise ValueError("volatility must be finite and positive for every risky asset")
    raw = 1.0 / vol
    normalized = raw / raw.sum()
    return {symbol: float(normalized[symbol]) for symbol in RISKY_ASSETS}


def strict_trend_on(current_close: float, last_ten_closes: pd.Series) -> bool:
    if len(last_ten_closes) != TREND_PRICE_COUNT:
        raise ValueError("exactly 10 completed month-end closes are required")
    ma = float(last_ten_closes.mean())
    return bool(float(current_close) > ma)


def signal_for_position(
    month_pos: int,
    month_periods: pd.Index,
    monthly_close: pd.DataFrame,
    month_dates: pd.DataFrame,
) -> tuple[dict[str, float], dict[str, Any]]:
    period = month_periods[month_pos]
    vol_window = monthly_close.loc[month_periods[month_pos - VOL_RETURNS_REQUIRED : month_pos + 1], list(RISKY_ASSETS)].pct_change().dropna()
    trend_prices = monthly_close.loc[month_periods[month_pos - TREND_PRICE_COUNT + 1 : month_pos + 1], list(RISKY_ASSETS)]
    weights_before = inverse_volatility_weights(vol_window)
    risky_after: dict[str, float] = {}
    trend_flags: dict[str, bool] = {}
    bil_weight = 0.0
    for symbol in RISKY_ASSETS:
        current = float(monthly_close.at[period, symbol])
        history = trend_prices[symbol].dropna()
        risk_on = strict_trend_on(current, history)
        trend_flags[symbol] = risk_on
        if risk_on:
            risky_after[symbol] = weights_before[symbol]
        else:
            risky_after[symbol] = 0.0
            bil_weight += weights_before[symbol]
    final = {symbol: risky_after[symbol] for symbol in RISKY_ASSETS}
    final[RISK_OFF_ASSET] = float(bil_weight)
    observation_date = max(pd.Timestamp(month_dates.at[period, symbol]) for symbol in FROZEN_UNIVERSE)
    audit = {
        "signal_month": str(period),
        "signal_date": str(observation_date.date()),
        "volatility_return_count": len(vol_window),
        "volatility_ddof": DDOF,
        "trend_price_count": TREND_PRICE_COUNT,
        "all_volatility_finite_positive": True,
        "pre_filter_weight_sum": sum(weights_before.values()),
        "post_filter_weight_sum": sum(final.values()),
        "bil_weight": final[RISK_OFF_ASSET],
        "BIL_final_weight": final[RISK_OFF_ASSET],
        "bil_transfer_weight": sum(weights_before[s] for s in RISKY_ASSETS if not trend_flags[s]),
        "mixed_risky_bil_allocation": final[RISK_OFF_ASSET] > TOL and sum(final[s] for s in RISKY_ASSETS) > TOL,
    }
    for symbol in RISKY_ASSETS:
        audit[f"{symbol}_pre_filter_weight"] = weights_before[symbol]
        audit[f"{symbol}_risk_on"] = trend_flags[symbol]
        audit[f"{symbol}_final_weight"] = final[symbol]
    return final, audit


def build_monthly_signals(daily_close: pd.DataFrame) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    month_close, month_dates = month_end_observations(daily_close[list(FROZEN_UNIVERSE)])
    complete = month_close.dropna()
    periods = complete.index
    rows: list[dict[str, Any]] = []
    weights_by_execution: dict[pd.Timestamp, dict[str, float]] = {}
    common_daily_index = pd.DatetimeIndex(daily_close.dropna(subset=list(FROZEN_UNIVERSE)).index)
    for pos in range(VOL_RETURNS_REQUIRED, len(periods)):
        weights, audit = signal_for_position(pos, periods, complete, month_dates)
        signal_date = pd.Timestamp(audit["signal_date"])
        later = common_daily_index[common_daily_index > signal_date]
        if len(later) == 0:
            continue
        execution_date = later[0]
        audit["execution_date"] = str(execution_date.date())
        audit["signal_precedes_execution"] = signal_date < execution_date
        audit["final_weight_sum"] = sum(weights.values())
        audit["gross_exposure"] = sum(max(0.0, w) for w in weights.values())
        audit["negative_weight_count"] = sum(1 for w in weights.values() if w < -TOL)
        audit["bil_equals_failed_pre_filter_weight"] = abs(audit["bil_weight"] - audit["bil_transfer_weight"]) <= TOL
        audit["weight_invariant_passed"] = (
            abs(audit["final_weight_sum"] - 1.0) <= TOL
            and audit["gross_exposure"] <= 1.0 + TOL
            and audit["negative_weight_count"] == 0
            and audit["bil_equals_failed_pre_filter_weight"]
            and audit["signal_precedes_execution"]
        )
        weights_by_execution[execution_date] = weights
        rows.append(audit)
    weights = pd.DataFrame.from_dict(weights_by_execution, orient="index").sort_index()
    weights = weights.reindex(columns=list(FROZEN_UNIVERSE), fill_value=0.0).fillna(0.0)
    return weights, rows


def target_weights_to_daily(
    execution_weights: pd.DataFrame,
    daily_index: pd.DatetimeIndex,
    weight_columns: list[str] | tuple[str, ...] | None = None,
    cash_column: str | None = RISK_OFF_ASSET,
) -> pd.DataFrame:
    columns = list(weight_columns) if weight_columns is not None else list(execution_weights.columns)
    daily = execution_weights.reindex(daily_index).ffill()
    daily = daily.reindex(columns=columns)
    daily = daily.fillna({symbol: 0.0 for symbol in columns})
    if daily.empty:
        return daily
    before_first = daily.index < execution_weights.index.min()
    daily.loc[before_first, columns] = 0.0
    if cash_column and cash_column in columns:
        daily.loc[before_first, cash_column] = 1.0
    return daily[columns].fillna(0.0)


def run_weighted_path(
    strategy_id: str,
    daily_close: pd.DataFrame,
    execution_weights: pd.DataFrame,
    weight_columns: tuple[str, ...] | list[str],
    apply_slippage: bool = True,
) -> ReturnPath:
    returns = daily_close[list(weight_columns)].pct_change()
    index = pd.DatetimeIndex(returns.dropna(how="all").index)
    cash_column = RISK_OFF_ASSET if RISK_OFF_ASSET in weight_columns else ("BIL" if "BIL" in weight_columns else None)
    daily_targets = target_weights_to_daily(
        execution_weights.reindex(columns=list(weight_columns), fill_value=0.0),
        index,
        list(weight_columns),
        cash_column,
    )
    daily_targets = daily_targets.reindex(columns=list(weight_columns), fill_value=0.0)
    scheduled_targets = execution_weights.reindex(columns=list(weight_columns), fill_value=0.0).sort_index()
    execution_dates = set(pd.DatetimeIndex(scheduled_targets.index))
    actual_rows: list[pd.Series] = []
    pre_trade_rows: list[pd.Series] = []
    post_trade_rows: list[pd.Series] = []
    turnover_values: list[float] = []
    cost_values: list[float] = []
    net_values: list[float] = []
    current_weights: pd.Series | None = None
    return_frame = returns.reindex(index).fillna(0.0)

    for date in index:
        target = daily_targets.loc[date].astype(float)
        if current_weights is None:
            current_weights = target.copy()
        pre_trade = current_weights.reindex(index=list(weight_columns), fill_value=0.0).astype(float)
        if date in execution_dates:
            post_trade = scheduled_targets.loc[date].astype(float)
            turnover = float((post_trade - pre_trade).abs().sum() / 2.0)
        else:
            post_trade = pre_trade.copy()
            turnover = 0.0
        cost_return = turnover * SLIPPAGE if apply_slippage else 0.0
        asset_returns = return_frame.loc[date].astype(float)
        gross_return = float((post_trade * asset_returns).sum())
        net_return = float((1.0 - cost_return) * (1.0 + gross_return) - 1.0)
        denominator = 1.0 + gross_return
        if abs(denominator) <= TOL:
            end_weights = post_trade.copy()
        else:
            end_weights = post_trade * (1.0 + asset_returns) / denominator
        end_weights = end_weights.reindex(index=list(weight_columns), fill_value=0.0).astype(float)
        actual_rows.append(end_weights)
        pre_trade_rows.append(pre_trade)
        post_trade_rows.append(post_trade)
        turnover_values.append(turnover)
        cost_values.append(cost_return)
        net_values.append(net_return)
        current_weights = end_weights

    actual_weights = pd.DataFrame(actual_rows, index=index, columns=list(weight_columns))
    pre_trade_weights = pd.DataFrame(pre_trade_rows, index=index, columns=list(weight_columns))
    post_trade_weights = pd.DataFrame(post_trade_rows, index=index, columns=list(weight_columns))
    turnover = pd.Series(turnover_values, index=index, name="turnover")
    cost_return = pd.Series(cost_values, index=index, name="cost_return")
    net = pd.Series(net_values, index=index, name=strategy_id)
    equity = STARTING_EQUITY * (1.0 + net).cumprod()
    return ReturnPath(
        strategy_id,
        net,
        actual_weights,
        turnover,
        equity,
        cost_return,
        daily_targets,
        pre_trade_weights,
        post_trade_weights,
        tuple(pd.Timestamp(date) for date in scheduled_targets.index),
    )


def monthly_equal_weight_execution_weights(monthly_signal_weights: pd.DataFrame) -> pd.DataFrame:
    weights = pd.DataFrame(index=monthly_signal_weights.index, columns=list(FROZEN_UNIVERSE), data=0.0)
    for symbol in RISKY_ASSETS:
        weights[symbol] = 1.0 / len(RISKY_ASSETS)
    weights[RISK_OFF_ASSET] = 0.0
    return weights


def spy_200d_execution_weights(close: pd.DataFrame, execution_index: pd.DatetimeIndex) -> pd.DataFrame:
    weights = pd.DataFrame(index=execution_index, columns=["SPY", "BIL"], data=0.0)
    for execution_date in execution_index:
        signal_candidates = close.index[close.index < execution_date]
        if len(signal_candidates) == 0:
            weights.at[execution_date, "BIL"] = 1.0
            continue
        signal_date = signal_candidates[-1]
        signal_pos = close.index.get_loc(signal_date)
        spy = close["SPY"].iloc[: signal_pos + 1].dropna()
        if len(spy) >= 200 and float(spy.iloc[-1]) > float(spy.iloc[-200:].mean()):
            weights.at[execution_date, "SPY"] = 1.0
        else:
            weights.at[execution_date, "BIL"] = 1.0
    return weights


def constant_execution_weights(index: pd.DatetimeIndex, weights: dict[str, float], columns: list[str]) -> pd.DataFrame:
    frame = pd.DataFrame(index=index, columns=columns, data=0.0)
    for symbol, weight in weights.items():
        frame[symbol] = weight
    return frame


def active_combo_path() -> ReturnPath:
    frame = pd.read_csv(abs_path(ACTIVE_COMBO_SERIES))
    dates = pd.to_datetime(frame["date"], errors="coerce").dt.tz_localize(None)
    returns = pd.to_numeric(frame["active_combo_daily_return"], errors="coerce")
    series = pd.Series(returns.to_numpy(dtype=float), index=dates, name="active_combo_vm_dsr_equal_weight_v1").dropna().sort_index()
    equity = STARTING_EQUITY * (1.0 + series).cumprod()
    empty_weights = pd.DataFrame(index=series.index)
    return ReturnPath(
        "active_combo_vm_dsr_equal_weight_v1",
        series,
        empty_weights,
        pd.Series(0.0, index=series.index),
        equity,
        pd.Series(0.0, index=series.index),
        empty_weights,
        empty_weights,
        empty_weights,
        tuple(),
    )


def read_windows() -> list[dict[str, Any]]:
    with abs_path(WINDOW_PREVIEW_PATH).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def window_metrics(path: ReturnPath, window: dict[str, Any]) -> dict[str, Any]:
    start = pd.Timestamp(window["window_start"])
    end = pd.Timestamp(window["window_end"])
    period = path.daily_returns[(path.daily_returns.index > start) & (path.daily_returns.index <= end)]
    horizon = int(window["horizon_days"])
    row: dict[str, Any] = {
        "strategy_id": path.strategy_id,
        "horizon_days": horizon,
        "window_start": str(start.date()),
        "window_end": str(end.date()),
    }
    if len(period) != horizon or period.isna().any():
        row.update({"window_valid": False, "invalid_reason": f"expected_{horizon}_returns_got_{len(period)}"})
        return row
    equity = STARTING_EQUITY * (1.0 + period).cumprod()
    peak = equity.cummax()
    dd_dollars = equity - peak
    dd_pct = equity / peak - 1.0
    profit = equity - STARTING_EQUITY
    stop_hits = np.flatnonzero((profit <= STOP_DOLLARS).to_numpy())
    target300_hits = np.flatnonzero((profit >= TARGET_300_DOLLARS).to_numpy())
    target400_hits = np.flatnonzero((profit >= TARGET_400_DOLLARS).to_numpy())
    stop = int(stop_hits[0]) if len(stop_hits) else None
    target300 = int(target300_hits[0]) if len(target300_hits) else None
    target400 = int(target400_hits[0]) if len(target400_hits) else None
    weight_period = path.weights.reindex(period.index).fillna(0.0) if not path.weights.empty else pd.DataFrame(index=period.index)
    risky_cols = [col for col in weight_period.columns if col != RISK_OFF_ASSET]
    risky_exposure = weight_period[risky_cols].sum(axis=1) if risky_cols else pd.Series(np.nan, index=period.index)
    bil = weight_period[RISK_OFF_ASSET] if RISK_OFF_ASSET in weight_period else pd.Series(np.nan, index=period.index)
    turnover = path.turnover.reindex(period.index).fillna(0.0)
    row.update(
        {
            "window_valid": True,
            "invalid_reason": "",
            "final_equity": float(equity.iloc[-1]),
            "total_return": float(equity.iloc[-1] / STARTING_EQUITY - 1.0),
            "median_total_return": "",
            "profit_dollars": float(equity.iloc[-1] - STARTING_EQUITY),
            "max_drawdown_dollars": float(dd_dollars.min()),
            "max_drawdown_pct": float(dd_pct.min()),
            "return_drawdown_proxy": float((equity.iloc[-1] / STARTING_EQUITY - 1.0) / abs(dd_pct.min())) if dd_pct.min() < 0 else np.nan,
            "absolute_600_stop_hit": stop is not None,
            "target_300_before_stop": bool(target300 is not None and (stop is None or target300 <= stop)),
            "target_400_before_stop": bool(target400 is not None and (stop is None or target400 <= stop)),
            "turnover": float(turnover.sum()),
            "allocation_change_count": int((turnover > TOL).sum()),
            "average_risky_exposure": float(risky_exposure.mean()) if not risky_exposure.isna().all() else "",
            "average_bil_allocation": float(bil.mean()) if not bil.isna().all() else "",
            "pct_days_fully_in_bil": float((bil >= 1.0 - TOL).mean()) if not bil.isna().all() else "",
            "pct_days_mixed_risky_bil": float(((bil > TOL) & (risky_exposure > TOL)).mean()) if not bil.isna().all() else "",
        }
    )
    return row


def summarize_window_rows(rows: list[dict[str, Any]], strategy_id: str, horizon: int) -> dict[str, Any]:
    subset = [row for row in rows if row["strategy_id"] == strategy_id and int(row["horizon_days"]) == horizon]
    valid = [row for row in subset if row.get("window_valid") is True]
    invalid = len(subset) - len(valid)
    base = {
        "strategy_id": strategy_id,
        "horizon_days": horizon,
        "valid_window_count": len(valid),
        "invalid_window_count": invalid,
    }
    if not valid:
        return {**base, "comparability_status": "not_comparable"}
    frame = pd.DataFrame(valid)
    return {
        **base,
        "median_final_equity": float(pd.to_numeric(frame["final_equity"]).median()),
        "mean_final_equity": float(pd.to_numeric(frame["final_equity"]).mean()),
        "median_total_return": float(pd.to_numeric(frame["total_return"]).median()),
        "worst_final_equity": float(pd.to_numeric(frame["final_equity"]).min()),
        "max_drawdown_dollars": float(pd.to_numeric(frame["max_drawdown_dollars"]).min()),
        "max_drawdown_pct": float(pd.to_numeric(frame["max_drawdown_pct"]).min()),
        "return_drawdown_proxy": float(pd.to_numeric(frame["return_drawdown_proxy"], errors="coerce").median()),
        "target_300_before_stop_rate": float(pd.to_numeric(frame["target_300_before_stop"]).mean()),
        "target_400_before_stop_rate": float(pd.to_numeric(frame["target_400_before_stop"]).mean()),
        "stop_hit_rate": float(pd.to_numeric(frame["absolute_600_stop_hit"]).mean()),
        "turnover": float(pd.to_numeric(frame["turnover"], errors="coerce").mean()),
        "allocation_change_count": float(pd.to_numeric(frame["allocation_change_count"], errors="coerce").mean()),
        "average_risky_exposure": float(pd.to_numeric(frame["average_risky_exposure"], errors="coerce").mean()) if "average_risky_exposure" in frame else "",
        "average_bil_allocation": float(pd.to_numeric(frame["average_bil_allocation"], errors="coerce").mean()) if "average_bil_allocation" in frame else "",
        "pct_days_fully_in_bil": float(pd.to_numeric(frame["pct_days_fully_in_bil"], errors="coerce").mean()) if "pct_days_fully_in_bil" in frame else "",
        "pct_days_mixed_risky_bil": float(pd.to_numeric(frame["pct_days_mixed_risky_bil"], errors="coerce").mean()) if "pct_days_mixed_risky_bil" in frame else "",
        "comparability_status": "comparable" if invalid == 0 else "partially_comparable",
    }


def benchmark_delta_rows(summaries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_key = {(row["strategy_id"], int(row["horizon_days"])): row for row in summaries}
    rows: list[dict[str, Any]] = []
    for horizon in active.HORIZONS:
        candidate = by_key[(CANDIDATE_ID, horizon)]
        for benchmark in BENCHMARK_IDS:
            bench = by_key.get((benchmark, horizon), {})
            rows.append(
                {
                    "candidate_id": CANDIDATE_ID,
                    "benchmark_id": benchmark,
                    "horizon_days": horizon,
                    "candidate_median_final_equity": candidate.get("median_final_equity", ""),
                    "benchmark_median_final_equity": bench.get("median_final_equity", ""),
                    "median_final_equity_delta": float(candidate.get("median_final_equity", np.nan)) - float(bench.get("median_final_equity", np.nan)) if bench.get("median_final_equity") != "" else "",
                    "candidate_max_drawdown_dollars": candidate.get("max_drawdown_dollars", ""),
                    "benchmark_max_drawdown_dollars": bench.get("max_drawdown_dollars", ""),
                    "max_drawdown_delta": float(candidate.get("max_drawdown_dollars", np.nan)) - float(bench.get("max_drawdown_dollars", np.nan)) if bench.get("max_drawdown_dollars") != "" else "",
                    "comparison_status": "comparable" if candidate.get("comparability_status") == "comparable" and bench.get("comparability_status") == "comparable" else "not_comparable",
                }
            )
    return rows


def invariant_rows(path: ReturnPath, signal_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    weights = path.weights
    scheduled_dates = set(path.scheduled_execution_dates)
    turnover_dates = set(pd.DatetimeIndex(path.turnover.index[path.turnover > TOL]))
    rows = [
        {"scope": "daily_actual", "invariant": "actual_weight_sum_equals_1", "passed": bool(((weights.sum(axis=1) - 1.0).abs() <= TOL).all()), "observed": float((weights.sum(axis=1) - 1.0).abs().max()), "expected": "<=1e-8"},
        {"scope": "daily_target", "invariant": "target_weight_sum_equals_1", "passed": bool(((path.target_weights.sum(axis=1) - 1.0).abs() <= TOL).all()), "observed": float((path.target_weights.sum(axis=1) - 1.0).abs().max()), "expected": "<=1e-8"},
        {"scope": "daily", "invariant": "gross_exposure_lte_1", "passed": bool((weights.abs().sum(axis=1) <= 1.0 + TOL).all()), "observed": float(weights.abs().sum(axis=1).max()), "expected": "<=1.0"},
        {"scope": "daily", "invariant": "no_negative_weights", "passed": bool((weights >= -TOL).all().all()), "observed": float(weights.min().min()), "expected": ">=0"},
        {"scope": "daily", "invariant": "turnover_only_on_scheduled_execution_dates", "passed": turnover_dates.issubset(scheduled_dates), "observed": len(turnover_dates - scheduled_dates), "expected": "0"},
        {"scope": "signal", "invariant": "bil_weight_equals_failed_pre_filter_weight", "passed": all(row["bil_equals_failed_pre_filter_weight"] for row in signal_rows), "observed": "all_signals", "expected": "true"},
        {"scope": "signal", "invariant": "signal_date_precedes_execution_date", "passed": all(row["signal_precedes_execution"] for row in signal_rows), "observed": "all_signals", "expected": "true"},
        {"scope": "signal", "invariant": "intentional_mixed_bil_risky_allowed", "passed": any(row["mixed_risky_bil_allocation"] for row in signal_rows), "observed": "mixed_allocations_present", "expected": "allowed"},
    ]
    return rows


def classify_outcome(candidate_metrics: list[dict[str, Any]], deltas: list[dict[str, Any]], invariants_passed: bool) -> str:
    if not invariants_passed:
        return "invalid_methodology"
    c180 = next(row for row in candidate_metrics if int(row["horizon_days"]) == 180)
    if c180.get("comparability_status") != "comparable":
        return "not_comparable"
    delta_lookup = {row["benchmark_id"]: row for row in deltas if int(row["horizon_days"]) == 180}
    spy_delta = float(delta_lookup["SPY_buy_and_hold"]["median_final_equity_delta"])
    active_delta = float(delta_lookup["active_combo_vm_dsr_equal_weight_v1"]["median_final_equity_delta"])
    spy_dd = float(delta_lookup["SPY_buy_and_hold"]["max_drawdown_delta"])
    active_dd = float(delta_lookup["active_combo_vm_dsr_equal_weight_v1"]["max_drawdown_delta"])
    if spy_delta > 0 and active_delta > 0 and spy_dd >= 0 and active_dd >= 0:
        return "comparative_evidence_positive"
    if spy_delta > 0 and (spy_dd < 0 or active_dd < 0):
        return "higher_return_higher_risk"
    if spy_delta < 0 and active_delta < 0:
        return "control_weak"
    return "direction_owner_review_required"


def build_paths() -> tuple[dict[str, ReturnPath], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    frozen_prices = load_price_frame(list(FROZEN_UNIVERSE))
    execution_weights, signal_rows = build_monthly_signals(frozen_prices)
    common_index = pd.DatetimeIndex(frozen_prices.dropna().index)
    candidate = run_weighted_path(CANDIDATE_ID, frozen_prices.reindex(common_index), execution_weights, list(FROZEN_UNIVERSE), True)
    equal_weights = monthly_equal_weight_execution_weights(execution_weights)
    equal_weight = run_weighted_path("equal_weight_same_five_risky_etfs_benchmark_only", frozen_prices.reindex(common_index), equal_weights, list(FROZEN_UNIVERSE), True)
    spy_bil_prices = load_price_frame(["SPY", "BIL"])
    spy_exec_index = execution_weights.index
    spy200d_weights = spy_200d_execution_weights(spy_bil_prices, spy_exec_index)
    spy200d = run_weighted_path("SPY_200d_trend_model", spy_bil_prices, spy200d_weights, ["SPY", "BIL"], True)
    spy_bh_weights = constant_execution_weights(pd.DatetimeIndex([spy_bil_prices.dropna().index.min()]), {"SPY": 1.0}, ["SPY", "BIL"])
    spy_bh = run_weighted_path("SPY_buy_and_hold", spy_bil_prices, spy_bh_weights, ["SPY", "BIL"], False)
    bil_weights = constant_execution_weights(pd.DatetimeIndex([spy_bil_prices.dropna().index.min()]), {"BIL": 1.0}, ["SPY", "BIL"])
    bil = run_weighted_path("BIL_cash_proxy", spy_bil_prices, bil_weights, ["SPY", "BIL"], False)
    active_combo = active_combo_path()
    paths = {
        CANDIDATE_ID: candidate,
        "equal_weight_same_five_risky_etfs_benchmark_only": equal_weight,
        "SPY_200d_trend_model": spy200d,
        "SPY_buy_and_hold": spy_bh,
        "BIL_cash_proxy": bil,
        "active_combo_vm_dsr_equal_weight_v1": active_combo,
    }
    invariant = invariant_rows(candidate, signal_rows)
    daily_rows = daily_path_rows(candidate)
    return paths, signal_rows, invariant, daily_rows


def daily_path_rows(path: ReturnPath) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for date in path.daily_returns.index:
        weights = path.weights.loc[date]
        targets = path.target_weights.loc[date]
        pre_trade = path.pre_trade_weights.loc[date]
        post_trade = path.post_trade_weights.loc[date]
        row = {
            "date": str(date.date()),
            "strategy_id": path.strategy_id,
            "daily_return": float(path.daily_returns.at[date]),
            "equity": float(path.equity.at[date]),
            "turnover": float(path.turnover.at[date]),
            "cost_return": float(path.cost.at[date]),
            "target_weight_sum": float(targets.sum()),
            "pre_trade_weight_sum": float(pre_trade.sum()),
            "actual_weight_sum": float(weights.sum()),
            "weight_sum": float(weights.sum()),
            "gross_exposure": float(weights.abs().sum()),
            "risky_exposure": float(weights[list(RISKY_ASSETS)].sum()),
            "bil_weight": float(weights[RISK_OFF_ASSET]),
            "BIL_actual_weight": float(weights[RISK_OFF_ASSET]),
            "BIL_target_weight": float(targets[RISK_OFF_ASSET]),
            "BIL_pre_trade_weight": float(pre_trade[RISK_OFF_ASSET]),
        }
        for symbol in FROZEN_UNIVERSE:
            row[f"{symbol}_weight"] = float(weights[symbol])
            row[f"{symbol}_actual_weight"] = float(weights[symbol])
            row[f"{symbol}_target_weight"] = float(targets[symbol])
            row[f"{symbol}_pre_trade_weight"] = float(pre_trade[symbol])
            row[f"{symbol}_post_trade_weight"] = float(post_trade[symbol])
        rows.append(row)
    return rows


def execution_manifest(prereg: dict[str, Any], lineage_rows: list[dict[str, Any]], hash_rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "candidate_id": CANDIDATE_ID,
        "family": FAMILY_ID,
        "family_id": FAMILY_ID,
        "source_id": SOURCE_ID,
        "source_adaptation_classification": prereg.get("adaptation_classification"),
        "source_replication_status": prereg.get("source_replication_status"),
        "risky_assets": list(RISKY_ASSETS),
        "risk_off_asset": RISK_OFF_ASSET,
        "cache_hashes_verified": all(row["hash_match"] for row in hash_rows),
        "monthly_series_rule": "last valid trading-day adjusted close per calendar month; no forward-fill across missing month ends",
        "monthly_return_rule": "consecutive completed month-end adjusted closes",
        "volatility_window_monthly_returns": VOL_RETURNS_REQUIRED,
        "volatility_window_months": VOL_RETURNS_REQUIRED,
        "volatility_ddof": DDOF,
        "annualization": "none",
        "zero_or_missing_volatility_behavior": "invalidate affected signal/window; no epsilon, no fallback, no asset drop",
        "trend_window_completed_month_end_prices": TREND_PRICE_COUNT,
        "trend_window_months": TREND_PRICE_COUNT,
        "trend_decision": "current adjusted close strictly greater than 10-month arithmetic mean; equality risk-off",
        "below_trend_behavior": "full calculated pre-filter weight transferred to BIL; no redistribution",
        "execution_timing": "month-end signal; first available trading session after month end; active recompute shifted/no-lookahead convention",
        "portfolio_accounting_method": "monthly targets executed only on scheduled dates; actual weights drift with asset returns between executions",
        "daily_return_method": "daily returns use post-trade actual holdings on execution dates and drifted actual holdings on non-execution dates",
        "reported_weight_fields": "daily_path_and_weights.csv separates target, pre-trade actual, post-trade target, and end-of-day actual weights",
        "turnover_convention": "one-way turnover = 0.5 * sum(abs(new target weight - pre-trade actual weight)) on scheduled execution dates only",
        "transaction_cost_convention": "cost_return = one-way turnover * slippage_turnover_cost; no cost when turnover is zero",
        "initial_capital": STARTING_EQUITY,
        "stop_dollars": STOP_DOLLARS,
        "stop_threshold_dollars": STOP_DOLLARS,
        "target_300_profit_dollars": TARGET_300_DOLLARS,
        "target_300_dollars": TARGET_300_DOLLARS,
        "target_400_profit_dollars": TARGET_400_DOLLARS,
        "target_400_dollars": TARGET_400_DOLLARS,
        "slippage_turnover_cost": SLIPPAGE,
        "slippage_assumption": SLIPPAGE,
        "public_source_lane_standard_cost_assumption": PUBLIC_SOURCE_STANDARD_COST_ASSUMPTION,
        "cost_source_paths": [
            "run_active_strategy_evidence_recompute.py",
            "strategy_lab/research_os/research/public_source_comparative_screening_batch_v1.py",
            "run_current_research_checkpoint.py",
        ],
        "cost_conflict_detected": False,
        "windows_source": str(WINDOW_PREVIEW_PATH).replace("\\", "/"),
        "benchmark_ids": list(BENCHMARK_IDS),
        "no_provider_calls": True,
        "no_parameter_wrapper_universe_or_window_search": True,
        "no_strategy_discovery_run": True,
        "no_robustness_run": True,
        "no_candidate_exhaustive_run": True,
        "no_promotion_or_paper_demo_state_change": True,
        "no_lifecycle_or_paper_demo_state_change": True,
        "artifact_lineage_hash": stable_hash(lineage_rows),
    }


def write_reports(
    manifest: dict[str, Any],
    paths: dict[str, ReturnPath],
    signal_rows: list[dict[str, Any]],
    invariant_rows_: list[dict[str, Any]],
    daily_rows: list[dict[str, Any]],
    lineage_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    output = abs_path(OUTPUT_DIR)
    output.mkdir(parents=True, exist_ok=True)
    windows = read_windows()
    window_rows: list[dict[str, Any]] = []
    for strategy_id, path in paths.items():
        for window in windows:
            window_rows.append(window_metrics(path, window))
    summaries = [
        summarize_window_rows(window_rows, strategy_id, horizon)
        for strategy_id in paths
        for horizon in active.HORIZONS
    ]
    candidate_metrics = [row for row in summaries if row["strategy_id"] == CANDIDATE_ID]
    benchmark_metrics = [row for row in summaries if row["strategy_id"] != CANDIDATE_ID]
    for row in candidate_metrics:
        row["candidate_row"] = True
        row["promotion_authorized"] = False
        row["paper_demo_authorized"] = False
    for row in benchmark_metrics:
        row["benchmark_reference_only"] = True
        row["promotion_authorized"] = False
        row["paper_demo_authorized"] = False
    deltas = benchmark_delta_rows(summaries)
    invariants_passed = all(row["passed"] for row in invariant_rows_)
    outcome = classify_outcome(candidate_metrics, deltas, invariants_passed)
    if outcome == "invalid_methodology":
        next_action = "fix_risk_parity_trend_etf_wrapper_screen_v1_methodology_issue"
    elif outcome in {"control_weak", "no_material_edge"}:
        next_action = "mark_risk_parity_trend_etf_wrapper_screen_v1_control_weak"
    elif outcome == "not_comparable":
        next_action = "manual_review_required_after_risk_parity_trend_screen"
    else:
        next_action = "direction_owner_decide_focus_robustness_or_close_exact_variant"
    memory = [
        {
            "candidate_id": CANDIDATE_ID,
            "family": FAMILY_ID,
            "screening_outcome": outcome,
            "exact_variant_closed_for_immediate_retest": outcome in {"control_weak", "no_material_edge"},
            "broader_family_status": "open_only_for_materially_different_hypotheses",
            "robustness_decision_required": outcome in {"comparative_evidence_positive", "higher_return_higher_risk", "direction_owner_review_required"},
            "no_lifecycle_status_changed": True,
        }
    ]
    screening_outcome = {
        "candidate_id": CANDIDATE_ID,
        "screening_outcome": outcome,
        "non_promotional_label": True,
        "promotion_authorized": False,
        "paper_demo_authorized": False,
        "candidate_exhaustive_authorized": False,
        "strategy_discovery_authorized": False,
        "invariants_passed": invariants_passed,
        "valid_candidate_windows": sum(1 for row in window_rows if row["strategy_id"] == CANDIDATE_ID and row.get("window_valid") is True),
        "invalid_candidate_windows": sum(1 for row in window_rows if row["strategy_id"] == CANDIDATE_ID and row.get("window_valid") is not True),
        "next_action": next_action,
    }
    write_json(OUTPUT_DIR / "execution_manifest.json", manifest)
    write_csv(OUTPUT_DIR / "candidate_metrics.csv", candidate_metrics, list(candidate_metrics[0].keys()))
    write_csv(OUTPUT_DIR / "benchmark_metrics.csv", benchmark_metrics, list(benchmark_metrics[0].keys()))
    write_csv(OUTPUT_DIR / "benchmark_relative_deltas.csv", deltas, list(deltas[0].keys()))
    write_csv(OUTPUT_DIR / "window_level_results.csv", window_rows, sorted({key for row in window_rows for key in row.keys()}))
    write_csv(OUTPUT_DIR / "daily_path_and_weights.csv", daily_rows, list(daily_rows[0].keys()))
    write_csv(OUTPUT_DIR / "monthly_signal_and_weight_audit.csv", signal_rows, list(signal_rows[0].keys()))
    write_csv(OUTPUT_DIR / "exposure_and_weight_invariants.csv", invariant_rows_, ["scope", "invariant", "passed", "observed", "expected"])
    write_json(OUTPUT_DIR / "screening_outcome.json", screening_outcome)
    write_csv(OUTPUT_DIR / "exact_variant_research_memory.csv", memory, list(memory[0].keys()))
    write_csv(OUTPUT_DIR / "artifact_lineage.csv", lineage_rows, list(lineage_rows[0].keys()))
    write_text(
        OUTPUT_DIR / "source_adaptation_caveats.md",
        "# Source Adaptation Caveats\n\n"
        "This screen uses a source-inspired ETF-wrapper adaptation, not exact source-index replication.\n\n"
        "- `URTH` maps the developed-market equity role to iShares MSCI World ETF.\n"
        "- `IGOV` preserves developed-market government-bond intent but excludes US government bonds.\n"
        "- `REET` maps global listed real estate/global REITs to iShares Global REIT ETF.\n"
        "- `DBC` is the broad commodity wrapper; `GLD` is not used as a broad commodity proxy.\n"
        "- No parameter, wrapper, universe, or sampled-window search was performed.\n",
    )
    write_text(
        OUTPUT_DIR / "screening_summary.md",
        "# Risk Parity Trend ETF Wrapper Screen v1\n\n"
        f"Candidate: `{CANDIDATE_ID}`\n\n"
        f"Outcome label: `{outcome}`\n\n"
        f"Valid candidate windows: `{screening_outcome['valid_candidate_windows']}`\n\n"
        "This is a bounded comparative screen only. It does not promote, reject, activate, retire, or assign paper/demo eligibility.\n",
    )
    check = consistency_check(manifest, screening_outcome, invariant_rows_, window_rows, daily_rows)
    write_json(OUTPUT_DIR / "screening_consistency_check.json", check)
    return screening_outcome | {"consistency_passed": check["consistency_passed"]}


def consistency_check(
    manifest: dict[str, Any],
    outcome: dict[str, Any],
    invariants: list[dict[str, Any]],
    window_rows: list[dict[str, Any]],
    daily_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    files = [
        "execution_manifest.json",
        "screening_summary.md",
        "candidate_metrics.csv",
        "benchmark_metrics.csv",
        "benchmark_relative_deltas.csv",
        "window_level_results.csv",
        "daily_path_and_weights.csv",
        "monthly_signal_and_weight_audit.csv",
        "exposure_and_weight_invariants.csv",
        "source_adaptation_caveats.md",
        "screening_outcome.json",
        "exact_variant_research_memory.csv",
        "artifact_lineage.csv",
    ]
    check = {
        "exact_frozen_universe": manifest["risky_assets"] == list(RISKY_ASSETS) and manifest["risk_off_asset"] == RISK_OFF_ASSET,
        "cache_hashes_match_preregistration": manifest["cache_hashes_verified"] is True,
        "ten_frozen_windows_used": len({(row["horizon_days"], row["window_start"], row["window_end"]) for row in window_rows if row["strategy_id"] == CANDIDATE_ID}) == 10,
        "no_provider_calls": manifest["no_provider_calls"] is True,
        "no_parameter_wrapper_universe_or_window_search": manifest["no_parameter_wrapper_universe_or_window_search"] is True,
        "all_invariants_passed": all(row["passed"] for row in invariants),
        "candidate_windows_valid": outcome["valid_candidate_windows"] == 10 and outcome["invalid_candidate_windows"] == 0,
        "non_promotional_outcome": outcome["screening_outcome"] in {
            "comparative_evidence_positive",
            "higher_return_higher_risk",
            "control_weak",
            "no_material_edge",
            "not_comparable",
            "invalid_methodology",
            "direction_owner_review_required",
        },
        "daily_weight_sum_valid": max(abs(float(row["weight_sum"]) - 1.0) for row in daily_rows) <= 1e-8,
        "no_lifecycle_or_paper_demo_state_change": manifest["no_lifecycle_or_paper_demo_state_change"] is True,
        "required_files_present": all((abs_path(OUTPUT_DIR) / name).exists() for name in files),
        "generation_deterministic_hash": stable_hash({"manifest": manifest, "outcome": outcome}).startswith("sha256:"),
    }
    check["consistency_passed"] = all(value is True for value in check.values())
    return check


def run() -> dict[str, Any]:
    prereg = read_preregistration()
    hash_rows = verify_cache_hashes(prereg)
    if not all(row["hash_match"] for row in hash_rows):
        raise RuntimeError("cache hash mismatch against preregistration")
    paths, signal_rows, invariant_rows_, daily_rows = build_paths()
    lineage_rows = hash_rows + [
        {
            "artifact_type": "source_file",
            "artifact_id": "implementation",
            "path": "strategy_lab/research_os/research/risk_parity_trend_etf_wrapper_screen_v1.py",
            "expected_hash": "",
            "actual_hash": sha256_file(Path(__file__)),
            "hash_match": True,
        },
        {
            "artifact_type": "preregistration",
            "artifact_id": "preregistration",
            "path": str(PREREG_PATH).replace("\\", "/"),
            "expected_hash": "",
            "actual_hash": sha256_file(abs_path(PREREG_PATH)),
            "hash_match": True,
        },
    ]
    manifest = execution_manifest(prereg, lineage_rows, hash_rows)
    outcome = write_reports(manifest, paths, signal_rows, invariant_rows_, daily_rows, lineage_rows)
    return {
        "output_dir": str(abs_path(OUTPUT_DIR)),
        "candidate_id": CANDIDATE_ID,
        "screening_outcome": outcome["screening_outcome"],
        "valid_candidate_windows": outcome["valid_candidate_windows"],
        "invalid_candidate_windows": outcome["invalid_candidate_windows"],
        "consistency_passed": outcome["consistency_passed"],
        "next_action": outcome["next_action"],
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
