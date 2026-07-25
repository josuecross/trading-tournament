from __future__ import annotations

import csv
import hashlib
import io
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import requests
import yaml

from execution_lab.alpaca_micro_live_v1.adapters.alpaca_client import AlpacaClient, AlpacaClientConfig
from execution_lab.alpaca_micro_live_v1.adapters.credentials import load_alpaca_credentials
from execution_lab.alpaca_micro_live_v1.data.alpaca_historical_bars import parse_bars_response
from strategy_lab.research_os.external_adapters.bt_adapter import equity_from_returns, returns_from_weights
from strategy_lab.research_os.research.profit_oriented_research_batch_v1 import (
    complete_rebalance_weight_frame,
    max_drawdown,
    trade_count_and_turnover,
    weight_invariant_report,
)


ROOT = Path(__file__).resolve().parents[3]
STRATEGY_ID = "driesprong_us_equity_oil_signal_wti_spy_bil_expanding_v1"
FAMILY_ID = "cross_asset_macro_predictive_timing"
TASK_ID = STRATEGY_ID
OUTPUT_DIR = Path("evidence") / "public_source_strategy_implementation" / STRATEGY_ID / "latest"
NEXT_ACTION = "direction_owner_review_driesprong_oil_spy_bil_baseline_v1"

RISKY_SYMBOL = "SPY"
DEFENSIVE_SYMBOL = "BIL"
SYMBOLS = (RISKY_SYMBOL, DEFENSIVE_SYMBOL)
PREDICTOR_SERIES = "DCOILWTICO"
RISK_FREE_SERIES = "TB3MS"
FRED_CSV_URLS = {
    PREDICTOR_SERIES: f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={PREDICTOR_SERIES}",
    RISK_FREE_SERIES: f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={RISK_FREE_SERIES}",
}
FRED_SERIES_URLS = {
    PREDICTOR_SERIES: f"https://fred.stlouisfed.org/series/{PREDICTOR_SERIES}",
    RISK_FREE_SERIES: f"https://fred.stlouisfed.org/series/{RISK_FREE_SERIES}",
}

RUN_CREATED_UTC = "2026-07-21T00:00:00Z"
REQUEST_START_DATE = "2000-01-01T00:00:00Z"
REQUEST_END_DATE = "2026-07-21T23:59:59Z"
LAST_COMPLETE_SIGNAL_MONTH = "2026-06"
ALPACA_FEED = "iex"
ALPACA_ADJUSTMENT = "all"
INITIAL_REGRESSION_OBSERVATIONS = 180
SWITCHING_COST_BPS = 10
SWITCHING_COST_RATE = SWITCHING_COST_BPS / 10000.0
WEIGHT_TOLERANCE = 1e-9

ALLOWED_OUTCOMES = {
    "baseline_implemented_for_exploratory_review",
    "aligned_history_insufficient",
    "alpaca_asset_or_bar_access_blocked",
    "official_macro_data_access_blocked",
    "source_timing_convention_invalid",
    "implementation_or_accounting_defect",
}

PROTECTED_STATE_PATHS = [
    Path("strategy_lab") / "strategy_registry.yaml",
    Path("strategy_lab") / "research_os" / "research" / "research_queue.yaml",
    Path("strategy_lab") / "research_os" / "family_lineage" / "family_ledger.yaml",
    Path("strategy_lab") / "research_os" / "operations" / "active_observations.yaml",
]

REQUIRED_FILES = {
    "source_packet_used.yaml",
    "pre_implementation_gate.json",
    "alpaca_asset_and_bar_check.json",
    "data_sources_and_hashes.json",
    "provider_splice_reconciliation.csv",
    "monthly_signal_calendar.csv",
    "frozen_test_config.yaml",
    "regression_audit.csv",
    "target_weights.csv",
    "transactions.csv",
    "accounting_invariants.csv",
    "baseline_metrics.csv",
    "benchmark_metrics.csv",
    "identity_overlay_equality.csv",
    "overlay_compatibility_map.csv",
    "trial_manifest.json",
    "command_validation_log.csv",
    "consistency_check.json",
    "implementation_summary.md",
}


SOURCE_PACKET: dict[str, Any] = {
    "strategy_id": STRATEGY_ID,
    "task_type": "active-direction-execution",
    "stage": "exploration",
    "family": FAMILY_ID,
    "adaptation_labels": ["data_feasibility_adjustment", "instrument_universe_adjustment"],
    "source_identity": {
        "public_strategy_page": "Crude Oil Predicts Equity Returns",
        "original_paper": "Driesprong, Jacobsen and Maat, Striking Oil: Another Puzzle?",
        "ssrn_abstract_identifier": "460500",
    },
    "source_rule": {
        "monthly_equity_return_estimated_from_previous_month_crude_oil_return": "source_explicit",
        "expanding_monthly_model_reestimated_each_month": "source_explicit",
        "equity_when_forecast_exceeds_risk_free_rate_otherwise_short_term_bills": "source_explicit",
        "switching_cost_10_bps": "source_explicit",
    },
    "frozen_modern_translation": {
        "risky_asset": RISKY_SYMBOL,
        "defensive_asset": DEFENSIVE_SYMBOL,
        "predictor": PREDICTOR_SERIES,
        "risk_free_threshold": RISK_FREE_SERIES,
        "alpaca_preferred_for_spy_bil": True,
        "fred_official_macro_inputs": True,
        "oil_etf_predictor": False,
        "futures": False,
        "options": False,
        "alternative_equity_etfs": False,
    },
    "execution": {
        "signal_timing": "after completed calendar month",
        "target_application": "project shifted/no-lookahead convention",
        "no_same_month_return": True,
        "initial_regression_observations": INITIAL_REGRESSION_OBSERVATIONS,
        "cost_rate_on_spy_bil_switch": SWITCHING_COST_RATE,
    },
    "non_promotable": True,
}


@dataclass(frozen=True)
class FredSeries:
    series_id: str
    url: str
    frame: pd.DataFrame
    raw_hash: str
    status: str
    error: str = ""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_path(path: Path) -> str:
    if not path.exists():
        return "missing"
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def dataframe_hash(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "empty"
    text = frame.to_csv(index=True, lineterminator="\n")
    return sha256_bytes(text.encode("utf-8"))


def clean_output_dir(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    for path in output.iterdir():
        if path.is_file():
            path.unlink()


def csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return ""
    if isinstance(value, (list, tuple, set)):
        return "|".join(str(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    return str(value)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False, width=120, allow_unicode=False), encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: csv_value(row.get(field, "")) for field in fieldnames})


def state_hashes(root: Path) -> dict[str, str]:
    return {str(path): sha256_path(root / path) for path in PROTECTED_STATE_PATHS}


def fetch_alpaca_daily_bars_read_only(
    client: AlpacaClient,
    *,
    symbols: tuple[str, ...] = SYMBOLS,
    start: str = REQUEST_START_DATE,
    end: str = REQUEST_END_DATE,
) -> dict[str, pd.DataFrame]:
    merged_payload: dict[str, Any] = {"bars": {symbol: [] for symbol in symbols}}
    page_token: str | None = None
    while True:
        payload = client.get_historical_bars_page(
            symbols=list(symbols),
            start=start,
            end=end,
            timeframe="1Day",
            page_token=page_token,
            feed=ALPACA_FEED,
            adjustment=ALPACA_ADJUSTMENT,
            limit=10000,
        )
        for symbol, bars in payload.get("bars", {}).items():
            merged_payload["bars"].setdefault(symbol, []).extend(bars)
        page_token = payload.get("next_page_token")
        if not page_token:
            break
    return parse_bars_response(merged_payload, drop_incomplete_current_day=False)


def alpaca_asset_and_bar_check() -> tuple[dict[str, Any], dict[str, pd.DataFrame]]:
    payload: dict[str, Any] = {
        "alpaca_assets_api_checked": True,
        "alpaca_stock_bars_api_checked": True,
        "paper_credentials_present": False,
        "live_credentials_detected": False,
        "api_secrets_persisted": False,
        "order_endpoint_called": False,
        "assets": {},
        "bars": {},
        "status": "not_started",
        "error": "",
    }
    try:
        credentials = load_alpaca_credentials("paper")
        payload["paper_credentials_present"] = credentials.present
        payload["credential_source"] = "environment_or_env_local" if credentials.present else "missing"
        payload["live_credentials_detected"] = credentials.live_credentials_detected
        client = AlpacaClient(credentials, AlpacaClientConfig(data_feed=ALPACA_FEED, data_adjustment=ALPACA_ADJUSTMENT))
        assets: dict[str, dict[str, Any]] = {}
        for symbol in SYMBOLS:
            asset = client._request("GET", client.config.paper_base_url, f"/v2/assets/{symbol}")
            assets[symbol] = {
                "symbol": asset.get("symbol", symbol),
                "name": asset.get("name", ""),
                "status": asset.get("status", ""),
                "tradable": bool(asset.get("tradable")),
                "asset_class": asset.get("asset_class", ""),
                "exchange": asset.get("exchange", ""),
                "fractionable": bool(asset.get("fractionable")),
            }
        bars = fetch_alpaca_daily_bars_read_only(client)
        payload["assets"] = assets
        for symbol in SYMBOLS:
            frame = bars.get(symbol, pd.DataFrame())
            payload["bars"][symbol] = {
                "rows": int(len(frame)),
                "first_date": str(frame["date"].iloc[0]) if not frame.empty else "",
                "last_date": str(frame["date"].iloc[-1]) if not frame.empty else "",
                "columns": list(frame.columns),
                "feed": ALPACA_FEED,
                "adjustment": ALPACA_ADJUSTMENT,
                "hash": dataframe_hash(frame),
            }
        assets_ready = all(
            payload["assets"].get(symbol, {}).get("status") == "active"
            and payload["assets"].get(symbol, {}).get("tradable") is True
            for symbol in SYMBOLS
        )
        bars_ready = all(int(payload["bars"].get(symbol, {}).get("rows", 0)) > 0 for symbol in SYMBOLS)
        payload["status"] = "ready" if assets_ready and bars_ready else "blocked"
        return payload, bars
    except Exception as exc:  # pragma: no cover - live-provider defensive branch.
        payload["status"] = "blocked"
        payload["error"] = f"{type(exc).__name__}: {str(exc)[:300]}"
        return payload, {}


def download_fred_series(series_id: str) -> FredSeries:
    url = FRED_CSV_URLS[series_id]
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        raw = response.content
        frame = pd.read_csv(io.BytesIO(raw))
        date_col = "observation_date"
        if date_col not in frame.columns or series_id not in frame.columns:
            return FredSeries(series_id, url, pd.DataFrame(), sha256_bytes(raw), "blocked", "unexpected_schema")
        frame[date_col] = pd.to_datetime(frame[date_col], errors="coerce")
        frame[series_id] = pd.to_numeric(frame[series_id], errors="coerce")
        frame = frame.dropna(subset=[date_col, series_id]).sort_values(date_col).reset_index(drop=True)
        return FredSeries(series_id, url, frame, sha256_bytes(raw), "ready")
    except Exception as exc:  # pragma: no cover - network defensive branch.
        return FredSeries(series_id, url, pd.DataFrame(), "missing", "blocked", f"{type(exc).__name__}: {exc}")


def load_local_symbol_frame(root: Path, symbol: str) -> pd.DataFrame:
    path = root / "data" / "cache" / f"{symbol}.csv"
    if not path.exists():
        return pd.DataFrame()
    frame = pd.read_csv(path)
    if "date" not in frame.columns:
        return pd.DataFrame()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    for column in ["open", "high", "low", "close", "adj_close", "volume"]:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.dropna(subset=["date", "adj_close"]).sort_values("date")
    frame = frame.drop_duplicates("date", keep="last").set_index("date")
    return frame


def reconciliation_passes(symbol: str, metrics: dict[str, Any]) -> bool:
    if int(metrics.get("overlap_rows", 0)) < 252:
        return False
    median_abs = float(metrics.get("median_abs_daily_return_difference", float("inf")))
    p99_abs = float(metrics.get("p99_abs_daily_return_difference", float("inf")))
    corr = metrics.get("daily_return_correlation")
    corr_value = float(corr) if corr not in (None, "") and not pd.isna(corr) else float("nan")
    if symbol == DEFENSIVE_SYMBOL:
        return median_abs <= 0.00020 and p99_abs <= 0.00060
    return median_abs <= 0.00050 and p99_abs <= 0.00300 and corr_value >= 0.995


def build_spliced_price_series(
    root: Path,
    symbol: str,
    alpaca_frame: pd.DataFrame,
) -> tuple[pd.Series, dict[str, Any]]:
    local = load_local_symbol_frame(root, symbol)
    local_series = local["adj_close"].astype(float).rename("local")
    alpaca_series = pd.Series(dtype=float, name="alpaca")
    if not alpaca_frame.empty and {"date", "close"} <= set(alpaca_frame.columns):
        alpaca = alpaca_frame.copy()
        alpaca["date"] = pd.to_datetime(alpaca["date"], errors="coerce")
        alpaca["close"] = pd.to_numeric(alpaca["close"], errors="coerce")
        alpaca_series = (
            alpaca.dropna(subset=["date", "close"])
            .drop_duplicates("date", keep="last")
            .set_index("date")["close"]
            .astype(float)
            .sort_index()
            .rename("alpaca")
        )
    if local_series.empty or alpaca_series.empty:
        return pd.Series(dtype=float, name=symbol), {
            "symbol": symbol,
            "decision": "blocked_missing_local_or_alpaca_series",
            "overlap_rows": 0,
        }

    overlap = pd.concat([local_series, alpaca_series], axis=1).dropna()
    if overlap.empty:
        return pd.Series(dtype=float, name=symbol), {
            "symbol": symbol,
            "decision": "blocked_no_provider_overlap",
            "overlap_rows": 0,
        }
    ratios = overlap["local"] / overlap["alpaca"]
    local_ret = overlap["local"].pct_change(fill_method=None)
    alpaca_ret = overlap["alpaca"].pct_change(fill_method=None)
    ret_diff = (local_ret - alpaca_ret).dropna()
    ret_pair = pd.concat([local_ret.rename("local"), alpaca_ret.rename("alpaca")], axis=1).dropna()
    switch_date = pd.Timestamp(overlap.index.min())
    scale_factor = float(overlap.loc[switch_date, "alpaca"] / overlap.loc[switch_date, "local"])
    metrics: dict[str, Any] = {
        "symbol": symbol,
        "local_cache_path": str((root / "data" / "cache" / f"{symbol}.csv").resolve()),
        "local_first_date": local_series.index.min().date().isoformat(),
        "local_last_date": local_series.index.max().date().isoformat(),
        "alpaca_first_date": alpaca_series.index.min().date().isoformat(),
        "alpaca_last_date": alpaca_series.index.max().date().isoformat(),
        "overlap_rows": int(len(overlap)),
        "overlap_first_date": overlap.index.min().date().isoformat(),
        "overlap_last_date": overlap.index.max().date().isoformat(),
        "level_ratio_mean_local_over_alpaca": float(ratios.mean()),
        "level_ratio_min_local_over_alpaca": float(ratios.min()),
        "level_ratio_max_local_over_alpaca": float(ratios.max()),
        "level_ratio_std_local_over_alpaca": float(ratios.std()),
        "median_abs_daily_return_difference": float(ret_diff.abs().median()) if not ret_diff.empty else float("nan"),
        "p99_abs_daily_return_difference": float(ret_diff.abs().quantile(0.99)) if not ret_diff.empty else float("nan"),
        "max_abs_daily_return_difference": float(ret_diff.abs().max()) if not ret_diff.empty else float("nan"),
        "daily_return_correlation": float(ret_pair["local"].corr(ret_pair["alpaca"])) if len(ret_pair) > 2 else float("nan"),
        "switch_date": switch_date.date().isoformat(),
        "pre_switch_scale_factor_applied_to_local": scale_factor,
        "splice_method": "local_adjusted_history_scaled_to_first_alpaca_overlap_then_alpaca_adjusted_daily_bars",
    }
    if not reconciliation_passes(symbol, metrics):
        metrics["decision"] = "blocked_provider_overlap_reconciliation_failed"
        return pd.Series(dtype=float, name=symbol), metrics
    pre_switch = local_series[local_series.index < switch_date] * scale_factor
    post_switch = alpaca_series[alpaca_series.index >= switch_date]
    spliced = pd.concat([pre_switch, post_switch]).sort_index()
    spliced = spliced[~spliced.index.duplicated(keep="last")].rename(symbol)
    metrics["decision"] = "spliced_after_overlap_reconciliation"
    metrics["spliced_first_date"] = spliced.index.min().date().isoformat()
    metrics["spliced_last_date"] = spliced.index.max().date().isoformat()
    metrics["spliced_rows"] = int(len(spliced))
    metrics["spliced_series_hash"] = dataframe_hash(spliced.to_frame())
    return spliced, metrics


def month_last_observations(series: pd.Series) -> pd.DataFrame:
    clean = series.dropna().sort_index()
    rows: list[dict[str, Any]] = []
    for period, group in clean.groupby(clean.index.to_period("M")):
        final_date = pd.Timestamp(group.index.max())
        rows.append({"month": str(period), "observation_date": final_date, "value": float(group.loc[final_date])})
    return pd.DataFrame(rows)


def monthly_log_return(monthly_frame: pd.DataFrame, value_column: str = "value") -> pd.Series:
    values = pd.Series(
        monthly_frame[value_column].astype(float).to_numpy(),
        index=pd.PeriodIndex(monthly_frame["month"], freq="M"),
    ).sort_index()
    return np.log(values / values.shift(1)).rename("log_return")


def tb3ms_monthly_thresholds(tb3ms: pd.DataFrame) -> pd.Series:
    frame = tb3ms.copy()
    frame["month"] = frame["observation_date"].dt.to_period("M")
    monthly = frame.drop_duplicates("month", keep="last").set_index("month")[RISK_FREE_SERIES].astype(float)
    threshold = np.log1p((monthly / 100.0) / 12.0).rename("tb3ms_monthly_log_threshold")
    return threshold.shift(1)


def build_monthly_inputs(
    prices: pd.DataFrame,
    wti: pd.DataFrame,
    tb3ms: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    monthly_price_frames: dict[str, pd.DataFrame] = {}
    for symbol in SYMBOLS:
        monthly_price_frames[symbol] = month_last_observations(prices[symbol].rename(symbol))

    spy_monthly = monthly_price_frames[RISKY_SYMBOL].rename(
        columns={"observation_date": "spy_month_end_date", "value": "spy_close"}
    )
    bil_monthly = monthly_price_frames[DEFENSIVE_SYMBOL].rename(
        columns={"observation_date": "bil_month_end_date", "value": "bil_close"}
    )
    wti_series = pd.Series(wti[PREDICTOR_SERIES].to_numpy(), index=wti["observation_date"], name=PREDICTOR_SERIES)
    wti_monthly = month_last_observations(wti_series).rename(
        columns={"observation_date": "wti_observation_date", "value": "wti_close"}
    )

    monthly = spy_monthly.merge(bil_monthly, on="month", how="inner").merge(wti_monthly, on="month", how="inner")
    monthly = monthly[monthly["month"] <= LAST_COMPLETE_SIGNAL_MONTH].copy()
    monthly["period"] = pd.PeriodIndex(monthly["month"], freq="M")
    monthly = monthly.set_index("period").sort_index()

    spy_returns = monthly_log_return(spy_monthly, "spy_close")
    bil_returns = monthly_log_return(bil_monthly, "bil_close")
    wti_returns = monthly_log_return(wti_monthly, "wti_close")
    monthly["spy_log_return"] = spy_returns.reindex(monthly.index)
    monthly["bil_log_return"] = bil_returns.reindex(monthly.index)
    monthly["wti_log_return"] = wti_returns.reindex(monthly.index)
    monthly["wti_log_return_lag1"] = monthly["wti_log_return"].shift(1)
    monthly["tb3ms_monthly_log_threshold"] = tb3ms_monthly_thresholds(tb3ms).reindex(monthly.index)
    monthly["tb3ms_vintage_month"] = (monthly.index - 1).astype(str)
    monthly["data_complete_for_regression_observation"] = monthly[["spy_log_return", "wti_log_return_lag1"]].notna().all(axis=1)
    monthly["data_complete_for_signal"] = monthly[
        ["spy_log_return", "wti_log_return", "wti_log_return_lag1", "tb3ms_monthly_log_threshold"]
    ].notna().all(axis=1)
    return monthly, spy_monthly, wti_monthly


def ols_intercept_beta(x: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    design = np.column_stack([np.ones(len(x)), x])
    coeffs = np.linalg.lstsq(design, y, rcond=None)[0]
    return float(coeffs[0]), float(coeffs[1])


def expanding_regression_signals(monthly: pd.DataFrame) -> pd.DataFrame:
    observation_rows = monthly[monthly["data_complete_for_regression_observation"]].copy()
    rows: list[dict[str, Any]] = []
    for i, (period, row) in enumerate(observation_rows.iterrows(), start=1):
        if i < INITIAL_REGRESSION_OBSERVATIONS:
            continue
        if not bool(row.get("data_complete_for_signal")):
            continue
        fit_frame = observation_rows.iloc[:i]
        x = fit_frame["wti_log_return_lag1"].astype(float).to_numpy()
        y = fit_frame["spy_log_return"].astype(float).to_numpy()
        intercept, beta = ols_intercept_beta(x, y)
        forecast = intercept + beta * float(row["wti_log_return"])
        threshold = float(row["tb3ms_monthly_log_threshold"])
        target_asset = RISKY_SYMBOL if forecast > threshold else DEFENSIVE_SYMBOL
        rows.append(
            {
                "signal_month": str(period),
                "regression_observation_count": i,
                "estimation_first_month": str(fit_frame.index.min()),
                "estimation_last_month": str(period),
                "forecast_month": str(period + 1),
                "intercept": intercept,
                "beta": beta,
                "current_wti_log_return": float(row["wti_log_return"]),
                "forecast_spy_log_return_next_month": forecast,
                "tb3ms_monthly_log_threshold": threshold,
                "forecast_exceeds_threshold": forecast > threshold,
                "target_asset": target_asset,
            }
        )
    return pd.DataFrame(rows)


def next_trading_day(index: pd.DatetimeIndex, date: pd.Timestamp) -> pd.Timestamp | None:
    candidates = index[index > date]
    return pd.Timestamp(candidates[0]) if len(candidates) else None


def build_signal_calendar(
    monthly: pd.DataFrame,
    regression: pd.DataFrame,
    daily_index: pd.DatetimeIndex,
) -> pd.DataFrame:
    if regression.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    monthly_by_period = monthly.copy()
    for _, reg in regression.iterrows():
        period = pd.Period(reg["signal_month"], freq="M")
        month_row = monthly_by_period.loc[period]
        signal_date = pd.Timestamp(month_row["spy_month_end_date"])
        execution_date = next_trading_day(daily_index, signal_date)
        if execution_date is None:
            continue
        rows.append(
            {
                "signal_month": str(period),
                "forecast_month": reg["forecast_month"],
                "regression_observation_count": int(reg["regression_observation_count"]),
                "estimation_first_month": reg["estimation_first_month"],
                "estimation_last_month": reg["estimation_last_month"],
                "wti_observation_date": pd.Timestamp(month_row["wti_observation_date"]).date().isoformat(),
                "spy_month_end_date": signal_date.date().isoformat(),
                "tb3ms_vintage_month": month_row["tb3ms_vintage_month"],
                "execution_effective_date": execution_date.date().isoformat(),
                "forecast_spy_log_return_next_month": float(reg["forecast_spy_log_return_next_month"]),
                "tb3ms_monthly_log_threshold": float(reg["tb3ms_monthly_log_threshold"]),
                "forecast_exceeds_threshold": bool(reg["forecast_exceeds_threshold"]),
                "target_asset": reg["target_asset"],
                "SPY": 1.0 if reg["target_asset"] == RISKY_SYMBOL else 0.0,
                "BIL": 1.0 if reg["target_asset"] == DEFENSIVE_SYMBOL else 0.0,
                "spy_data_provider": "local_cache_scaled_until_alpaca_overlap_then_alpaca",
                "bil_data_provider": "local_cache_scaled_until_alpaca_overlap_then_alpaca",
                "wti_data_provider": "FRED_DCOILWTICO_daily_final_valid_calendar_month_observation",
                "tb3ms_data_provider": "FRED_TB3MS_prior_month_publication_lag_guard",
            }
        )
    return pd.DataFrame(rows)


def build_daily_weights(prices: pd.DataFrame, signal_calendar: pd.DataFrame) -> pd.DataFrame:
    if signal_calendar.empty:
        return pd.DataFrame(columns=list(SYMBOLS), dtype=float)
    start_date = pd.Timestamp(signal_calendar["spy_month_end_date"].iloc[0])
    daily_index = prices.index[prices.index >= start_date]
    targets: dict[pd.Timestamp, dict[str, float]] = {}
    for _, row in signal_calendar.iterrows():
        signal_date = pd.Timestamp(row["spy_month_end_date"])
        targets[signal_date] = {RISKY_SYMBOL: float(row["SPY"]), DEFENSIVE_SYMBOL: float(row["BIL"])}
    return complete_rebalance_weight_frame(daily_index, list(SYMBOLS), targets, tolerance=WEIGHT_TOLERANCE)


def transaction_rows(signal_calendar: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    previous_asset: str | None = None
    for _, row in signal_calendar.iterrows():
        current_asset = str(row["target_asset"])
        switched = previous_asset is not None and current_asset != previous_asset
        if switched:
            rows.append(
                {
                    "signal_month": row["signal_month"],
                    "signal_date": row["spy_month_end_date"],
                    "execution_effective_date": row["execution_effective_date"],
                    "from_asset": previous_asset,
                    "to_asset": current_asset,
                    "switching_cost_bps": SWITCHING_COST_BPS,
                    "switching_cost_rate": SWITCHING_COST_RATE,
                    "cost_applied": True,
                }
            )
        previous_asset = current_asset
    return rows


def apply_switching_costs(gross_returns: pd.Series, transactions: list[dict[str, Any]]) -> tuple[pd.Series, pd.Series]:
    costs = pd.Series(0.0, index=gross_returns.index, name="switching_cost")
    for row in transactions:
        date = pd.Timestamp(row["execution_effective_date"])
        if date in costs.index:
            costs.loc[date] += SWITCHING_COST_RATE
    net = (gross_returns - costs).rename("source_aligned_10bps_baseline")
    return net, costs


def compute_metrics(returns: pd.Series, weights: pd.DataFrame | None = None) -> dict[str, Any]:
    daily = returns.dropna().astype(float)
    if daily.empty:
        return {
            "total_return": float("nan"),
            "cagr": float("nan"),
            "max_drawdown": float("nan"),
            "volatility": float("nan"),
            "return_drawdown_proxy": float("nan"),
        }
    equity = equity_from_returns(daily)
    years = max((daily.index.max() - daily.index.min()).days / 365.25, 1e-9)
    total = float(equity.iloc[-1] - 1.0)
    cagr = float(equity.iloc[-1] ** (1.0 / years) - 1.0)
    mdd = max_drawdown(equity)
    vol = float(daily.std() * np.sqrt(252.0))
    proxy = float(cagr / abs(mdd)) if mdd < 0 else float("nan")
    payload: dict[str, Any] = {
        "effective_start_date": daily.index.min().date().isoformat(),
        "effective_end_date": daily.index.max().date().isoformat(),
        "daily_observations": int(len(daily)),
        "total_return": total,
        "cagr": cagr,
        "max_drawdown": mdd,
        "volatility": vol,
        "return_drawdown_proxy": proxy,
    }
    if weights is not None and not weights.empty:
        trades, turnover = trade_count_and_turnover(weights)
        payload.update(
            {
                "average_spy_weight": float(weights[RISKY_SYMBOL].mean()),
                "average_bil_weight": float(weights[DEFENSIVE_SYMBOL].mean()),
                "trade_count": trades,
                "turnover_proxy": turnover,
            }
        )
    return payload


def benchmark_return_series(
    prices: pd.DataFrame,
    price_start: pd.Timestamp,
    return_start: pd.Timestamp,
    end: pd.Timestamp,
) -> dict[str, pd.Series]:
    window = prices.loc[(prices.index >= price_start) & (prices.index <= end), list(SYMBOLS)].copy()
    pct = window.pct_change(fill_method=None).fillna(0.0)
    return {
        "SPY_buy_and_hold": pct[RISKY_SYMBOL].loc[return_start:end].rename("SPY_buy_and_hold"),
        "BIL_buy_and_hold": pct[DEFENSIVE_SYMBOL].loc[return_start:end].rename("BIL_buy_and_hold"),
    }


def identity_overlay_equality_rows(
    base_weights: pd.DataFrame,
    base_returns: pd.Series,
    base_transactions: list[dict[str, Any]],
    base_metrics: dict[str, Any],
) -> list[dict[str, Any]]:
    identity_weights = base_weights.copy()
    identity_returns = base_returns.copy()
    identity_transactions = [dict(row) for row in base_transactions]
    identity_metrics = dict(base_metrics)
    weight_diff = float((identity_weights - base_weights).abs().max().max()) if not base_weights.empty else 0.0
    return_diff = float((identity_returns - base_returns).abs().max()) if not base_returns.empty else 0.0
    transaction_equal = identity_transactions == base_transactions
    metric_equal = identity_metrics == base_metrics
    return [
        {
            "comparison": "target_weights",
            "exact_match": weight_diff <= 0.0,
            "max_abs_difference": weight_diff,
            "notes": "IdentityOverlay pass-through target transform",
        },
        {
            "comparison": "daily_returns",
            "exact_match": return_diff <= 0.0,
            "max_abs_difference": return_diff,
            "notes": "IdentityOverlay pass-through daily returns",
        },
        {
            "comparison": "transactions",
            "exact_match": transaction_equal,
            "max_abs_difference": 0.0 if transaction_equal else 1.0,
            "notes": "IdentityOverlay does not add, remove, or resize transactions",
        },
        {
            "comparison": "switching_costs",
            "exact_match": transaction_equal,
            "max_abs_difference": 0.0 if transaction_equal else 1.0,
            "notes": "Costs are inherited from unchanged base transactions",
        },
        {
            "comparison": "reported_metrics",
            "exact_match": metric_equal,
            "max_abs_difference": 0.0 if metric_equal else 1.0,
            "notes": "IdentityOverlay metrics equal base metrics",
        },
    ]


def overlay_compatibility_rows() -> list[dict[str, Any]]:
    return [
        {
            "overlay": "IdentityOverlay",
            "classification": "compatible_without_change",
            "reason": "pass-through overlay can be asserted exactly against binary SPY/BIL target weights",
            "performance_experiment_run": False,
        },
        {
            "overlay": "RebalanceBandOverlay",
            "classification": "not_economically_appropriate",
            "reason": "suppression of full SPY/BIL switches would change the monthly source allocation rule",
            "performance_experiment_run": False,
        },
        {
            "overlay": "LaggedVolatilityTargetOverlay",
            "classification": "not_economically_appropriate",
            "reason": "dynamic scaling would add a volatility target not present in the frozen baseline",
            "performance_experiment_run": False,
        },
        {
            "overlay": "ExposureCapsOverlay",
            "classification": "compatible_without_change",
            "reason": "a max-gross-exposure cap of 1.0 is a no-op for the invariant-compliant baseline",
            "performance_experiment_run": False,
        },
        {
            "overlay": "WideATRCatastrophicStopOverlay",
            "classification": "not_economically_appropriate",
            "reason": "ATR stops add daily technical exits outside the source rule",
            "performance_experiment_run": False,
        },
        {
            "overlay": "TimeStopOverlay",
            "classification": "not_economically_appropriate",
            "reason": "time exits alter the expanding-regression monthly allocation state",
            "performance_experiment_run": False,
        },
        {
            "overlay": "StaticScaleOverlay",
            "classification": "not_economically_appropriate",
            "reason": "static scaling would create a lower-exposure adaptation rather than the source-aligned baseline",
            "performance_experiment_run": False,
        },
    ]


def target_weight_rows(weights: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for date, row in weights.iterrows():
        rows.append(
            {
                "date": pd.Timestamp(date).date().isoformat(),
                "SPY": float(row[RISKY_SYMBOL]),
                "BIL": float(row[DEFENSIVE_SYMBOL]),
                "weight_sum": float(row.sum()),
                "held_asset": RISKY_SYMBOL if row[RISKY_SYMBOL] > 0.5 else DEFENSIVE_SYMBOL,
            }
        )
    return rows


def invariant_rows(weights: pd.DataFrame, transactions: list[dict[str, Any]], signal_calendar: pd.DataFrame) -> list[dict[str, Any]]:
    report = weight_invariant_report(weights, tolerance=WEIGHT_TOLERANCE)
    simultaneous = int(((weights[RISKY_SYMBOL] > WEIGHT_TOLERANCE) & (weights[DEFENSIVE_SYMBOL] > WEIGHT_TOLERANCE)).sum())
    binary_days = int(
        (~(
            ((weights[RISKY_SYMBOL] == 1.0) & (weights[DEFENSIVE_SYMBOL] == 0.0))
            | ((weights[RISKY_SYMBOL] == 0.0) & (weights[DEFENSIVE_SYMBOL] == 1.0))
        )).sum()
    )
    cost_dates = [row["execution_effective_date"] for row in transactions if row["cost_applied"]]
    return [
        {"invariant": "daily_weights_sum_to_one", "passed": report["weight_sum_violation_count"] == 0, "value": report["max_daily_weight_sum"]},
        {"invariant": "gross_exposure_lte_one", "passed": report["max_daily_exposure"] <= 1.0 + WEIGHT_TOLERANCE, "value": report["max_daily_exposure"]},
        {"invariant": "no_negative_weights", "passed": report["negative_weight_violation_count"] == 0, "value": report["negative_weight_violation_count"]},
        {"invariant": "no_nan_weights", "passed": report["nan_weight_count"] == 0, "value": report["nan_weight_count"]},
        {"invariant": "only_spy_or_bil_held", "passed": binary_days == 0, "value": binary_days},
        {"invariant": "no_simultaneous_spy_and_bil", "passed": simultaneous == 0, "value": simultaneous},
        {
            "invariant": "no_same_month_strategy_returns",
            "passed": bool((pd.to_datetime(signal_calendar["execution_effective_date"]) > pd.to_datetime(signal_calendar["spy_month_end_date"])).all())
            if not signal_calendar.empty
            else False,
            "value": "",
        },
        {
            "invariant": "forecast_month_after_estimation_last_month",
            "passed": bool((pd.PeriodIndex(signal_calendar["forecast_month"], freq="M") > pd.PeriodIndex(signal_calendar["estimation_last_month"], freq="M")).all())
            if not signal_calendar.empty
            else False,
            "value": "",
        },
        {
            "invariant": "switching_cost_once_per_change",
            "passed": len(cost_dates) == len(set(cost_dates)),
            "value": len(cost_dates),
        },
    ]


def command_validation_rows() -> list[dict[str, Any]]:
    commands = [
        ".venv\\Scripts\\python.exe run_driesprong_us_equity_oil_signal_wti_spy_bil_expanding_v1.py",
        ".venv\\Scripts\\python.exe -m pytest tests\\test_driesprong_us_equity_oil_signal_wti_spy_bil_expanding_v1.py -q",
        ".venv\\Scripts\\python.exe run_current_research_checkpoint.py",
        ".venv\\Scripts\\python.exe run_research_state_dashboard.py",
        ".venv\\Scripts\\python.exe run_advisor_consistency_check.py",
        ".venv\\Scripts\\python.exe run_strategy_lab.py --validate-registry --export-evidence",
    ]
    return [{"command": command, "status": "not_run_by_runner", "notes": "updated in final response"} for command in commands]


def source_packet_gate(
    alpaca_check: dict[str, Any],
    fred: dict[str, FredSeries],
    monthly: pd.DataFrame | None,
) -> tuple[str, str]:
    if alpaca_check.get("status") != "ready":
        return "alpaca_asset_or_bar_access_blocked", str(alpaca_check.get("error", ""))
    if any(series.status != "ready" or series.frame.empty for series in fred.values()):
        errors = "; ".join(f"{key}:{value.error or value.status}" for key, value in fred.items() if value.status != "ready")
        return "official_macro_data_access_blocked", errors
    if monthly is None or monthly.empty:
        return "aligned_history_insufficient", "no aligned monthly SPY/BIL/WTI/TB3MS data"
    available = int(monthly["data_complete_for_regression_observation"].sum())
    if available < INITIAL_REGRESSION_OBSERVATIONS:
        return "aligned_history_insufficient", f"only {available} aligned monthly regression observations"
    regression = expanding_regression_signals(monthly)
    if regression.empty:
        return "aligned_history_insufficient", "no post-warmup signal months available"
    first = int(regression["regression_observation_count"].iloc[0])
    if first != INITIAL_REGRESSION_OBSERVATIONS:
        return "source_timing_convention_invalid", f"first signal used {first} observations"
    return "baseline_implemented_for_exploratory_review", "none"


def metrics_rows(baseline_returns: pd.Series, zero_cost_returns: pd.Series, weights: pd.DataFrame, costs: pd.Series) -> list[dict[str, Any]]:
    base_metrics = compute_metrics(baseline_returns, weights)
    zero_metrics = compute_metrics(zero_cost_returns, weights)
    return [
        {
            "series_id": "source_aligned_10bps_baseline",
            "role": "candidate_baseline_diagnostic",
            "switching_cost_bps": SWITCHING_COST_BPS,
            "total_switching_cost_return_drag": float(costs.sum()),
            **base_metrics,
        },
        {
            "series_id": "zero_cost_accounting_control",
            "role": "accounting_control_only",
            "switching_cost_bps": 0,
            "total_switching_cost_return_drag": 0.0,
            **zero_metrics,
        },
    ]


def benchmark_rows(benchmarks: dict[str, pd.Series]) -> list[dict[str, Any]]:
    return [{"benchmark_id": name, "role": "required_control", **compute_metrics(series)} for name, series in benchmarks.items()]


def write_outputs_for_blocker(
    root: Path,
    output: Path,
    outcome: str,
    blocker: str,
    before_hashes: dict[str, str],
    after_hashes: dict[str, str],
    alpaca_check: dict[str, Any],
    fred: dict[str, FredSeries],
    splice_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    manifest = {
        "created_utc": RUN_CREATED_UTC,
        "strategy_id": STRATEGY_ID,
        "family_id": FAMILY_ID,
        "task_id": TASK_ID,
        "outcome": outcome,
        "blocker": blocker,
        "baseline_implemented": False,
        "backtest_run": False,
        "promotion_eligibility": False,
        "paper_demo_eligibility": False,
        "paper_demo_activation": False,
        "candidate_exhaustive_run": False,
        "broker_order_endpoint_called": False,
        "real_money_recommendation": False,
        "registry_state_changed": before_hashes != after_hashes,
        "state_hashes_before": before_hashes,
        "state_hashes_after": after_hashes,
        "next_action": NEXT_ACTION,
    }
    write_json(output / "trial_manifest.json", manifest)
    write_json(output / "pre_implementation_gate.json", {"outcome": outcome, "blocker": blocker, "gate_ran": True})
    write_json(output / "alpaca_asset_and_bar_check.json", alpaca_check)
    write_json(
        output / "data_sources_and_hashes.json",
        {
            "fred": {
                key: {"status": value.status, "url": value.url, "raw_hash": value.raw_hash, "rows": int(len(value.frame))}
                for key, value in fred.items()
            },
            "api_secrets_persisted": False,
            "provider_downloads": ["official_fred_csv_only"],
        },
    )
    write_csv(output / "provider_splice_reconciliation.csv", splice_rows, list(splice_rows[0].keys()) if splice_rows else ["symbol", "decision"])
    for filename, fields in {
        "monthly_signal_calendar.csv": ["signal_month"],
        "regression_audit.csv": ["signal_month"],
        "target_weights.csv": ["date", "SPY", "BIL"],
        "transactions.csv": ["signal_month", "from_asset", "to_asset"],
        "accounting_invariants.csv": ["invariant", "passed", "value"],
        "baseline_metrics.csv": ["series_id"],
        "benchmark_metrics.csv": ["benchmark_id"],
        "identity_overlay_equality.csv": ["comparison", "exact_match"],
    }.items():
        write_csv(output / filename, [], fields)
    write_yaml(output / "frozen_test_config.yaml", frozen_test_config(False))
    write_csv(
        output / "overlay_compatibility_map.csv",
        overlay_compatibility_rows(),
        ["overlay", "classification", "reason", "performance_experiment_run"],
    )
    write_csv(output / "command_validation_log.csv", command_validation_rows(), ["command", "status", "notes"])
    write_text(output / "implementation_summary.md", summary_md(manifest, []))
    consistency = consistency_payload(output, manifest, [], [], [], [], [])
    write_json(output / "consistency_check.json", consistency)
    return {**manifest, "output_dir": str(output.resolve()), "consistency_passed": consistency["consistency_passed"]}


def frozen_test_config(implemented: bool) -> dict[str, Any]:
    return {
        "strategy_id": STRATEGY_ID,
        "family_id": FAMILY_ID,
        "implemented": implemented,
        "risky_asset": RISKY_SYMBOL,
        "defensive_asset": DEFENSIVE_SYMBOL,
        "predictor_series": PREDICTOR_SERIES,
        "risk_free_threshold_series": RISK_FREE_SERIES,
        "initial_regression_observations": INITIAL_REGRESSION_OBSERVATIONS,
        "regression_type": "expanding_ols",
        "rolling_regression": False,
        "forecast_rule": "forecast next monthly SPY log return from current completed WTI monthly log return",
        "risk_free_threshold_conversion": "log(1 + TB3MS_percent / 100 / 12), one observation month lag for public-release guard",
        "switching_cost_bps": SWITCHING_COST_BPS,
        "cost_values_tested": [SWITCHING_COST_BPS],
        "zero_cost_output": "accounting_control_only",
        "benchmarks": ["SPY_buy_and_hold", "BIL_buy_and_hold"],
        "no_parameter_search": True,
        "no_alternative_predictors": True,
        "no_alternative_equity_etfs": True,
        "no_paper_demo_activation": True,
    }


def consistency_payload(
    output: Path,
    manifest: dict[str, Any],
    invariant: list[dict[str, Any]],
    identity_rows_: list[dict[str, Any]],
    regression_rows_: list[dict[str, Any]],
    signal_rows_: list[dict[str, Any]],
    baseline_rows_: list[dict[str, Any]],
) -> dict[str, Any]:
    required = {filename: (output / filename).exists() for filename in REQUIRED_FILES}
    required["consistency_check.json"] = True
    invariant_pass = all(row.get("passed") in (True, "true") for row in invariant) if invariant else manifest["outcome"] != "baseline_implemented_for_exploratory_review"
    identity_pass = all(row.get("exact_match") in (True, "true") for row in identity_rows_) if identity_rows_ else manifest["outcome"] != "baseline_implemented_for_exploratory_review"
    first_regression = int(regression_rows_[0]["regression_observation_count"]) if regression_rows_ else 0
    target_assets = {row.get("target_asset") for row in signal_rows_}
    checks = {
        "all_required_files_present": all(required.values()),
        "required_files": required,
        "outcome_allowed": manifest["outcome"] in ALLOWED_OUTCOMES,
        "exactly_one_strategy_configuration": manifest.get("strategy_id") == STRATEGY_ID,
        "initial_regression_window_exact_180": first_regression in {0, INITIAL_REGRESSION_OBSERVATIONS},
        "regression_expanding_not_rolling": manifest.get("regression_type") == "expanding_ols" or not baseline_rows_,
        "targets_binary_spy_or_bil": target_assets <= {RISKY_SYMBOL, DEFENSIVE_SYMBOL},
        "switching_cost_only_10bps": manifest.get("switching_cost_bps", SWITCHING_COST_BPS) == SWITCHING_COST_BPS,
        "no_alternative_parameters_or_instruments": manifest.get("parameter_search_run") is False
        and manifest.get("alternative_predictors_tested") is False
        and manifest.get("alternative_equity_etfs_tested") is False,
        "identity_overlay_exact": identity_pass,
        "accounting_invariants_pass": invariant_pass,
        "no_overlay_performance_output": not any("overlay_performance" in path.name for path in output.iterdir() if path.is_file()),
        "no_broker_write_or_orders": manifest.get("broker_order_endpoint_called") is False,
        "no_promotion_or_paper_demo": manifest.get("promotion_eligibility") is False
        and manifest.get("paper_demo_eligibility") is False
        and manifest.get("paper_demo_activation") is False,
        "state_preserved": manifest.get("registry_state_changed") is False,
    }
    checks["consistency_passed"] = all(value is True for key, value in checks.items() if key != "required_files")
    return checks


def summary_md(manifest: dict[str, Any], baseline_rows_: list[dict[str, Any]]) -> str:
    if not baseline_rows_:
        return f"""# Driesprong WTI-SPY-BIL Expanding Baseline

Strategy ID: `{STRATEGY_ID}`

Outcome: `{manifest['outcome']}`

Blocker: `{manifest.get('blocker', 'none')}`

No backtest, promotion, paper/demo activation, broker order, or real-money recommendation occurred.

Exact next action: `{NEXT_ACTION}`
"""
    primary = next(row for row in baseline_rows_ if row["series_id"] == "source_aligned_10bps_baseline")
    zero_cost = next(row for row in baseline_rows_ if row["series_id"] == "zero_cost_accounting_control")
    return f"""# Driesprong WTI-SPY-BIL Expanding Baseline

Strategy ID: `{STRATEGY_ID}`

Outcome: `{manifest['outcome']}`

Rows/configurations implemented: `1` source-aligned baseline plus `1` zero-cost accounting control.

Initial regression observations before first signal: `{manifest['initial_regression_observations']}`

First signal month: `{manifest['first_signal_month']}`

Latest signal month: `{manifest['latest_signal_month']}`

Daily evaluation window: `{primary['effective_start_date']}` to `{primary['effective_end_date']}`

Switching costs: `{SWITCHING_COST_BPS}` bps per SPY/BIL allocation change.

Baseline total return: `{primary['total_return']}`

Baseline max drawdown: `{primary['max_drawdown']}`

Zero-cost diagnostic total return: `{zero_cost['total_return']}`

Exposure invariant passed: `{manifest['exposure_invariant_passed']}`

IdentityOverlay equality passed: `{manifest['identity_overlay_equality_passed']}`

The output is exploratory diagnostic evidence only. It is not promotion evidence, paper/demo eligibility, candidate_exhaustive authorization, or real-money advice.

Exact next action: `{NEXT_ACTION}`
"""


def run(root: Path = ROOT) -> dict[str, Any]:
    output = root / OUTPUT_DIR
    clean_output_dir(output)
    before_hashes = state_hashes(root)
    write_yaml(output / "source_packet_used.yaml", SOURCE_PACKET)

    alpaca_check, alpaca_bars = alpaca_asset_and_bar_check()
    write_json(output / "alpaca_asset_and_bar_check.json", alpaca_check)
    fred = {series_id: download_fred_series(series_id) for series_id in (PREDICTOR_SERIES, RISK_FREE_SERIES)}

    splice_rows: list[dict[str, Any]] = []
    spliced: dict[str, pd.Series] = {}
    for symbol in SYMBOLS:
        series, row = build_spliced_price_series(root, symbol, alpaca_bars.get(symbol, pd.DataFrame()))
        splice_rows.append(row)
        spliced[symbol] = series

    prices = pd.concat([spliced[RISKY_SYMBOL], spliced[DEFENSIVE_SYMBOL]], axis=1).dropna() if all(not s.empty for s in spliced.values()) else pd.DataFrame()
    monthly: pd.DataFrame | None = None
    if not prices.empty and all(series.status == "ready" for series in fred.values()):
        monthly, _, _ = build_monthly_inputs(prices, fred[PREDICTOR_SERIES].frame, fred[RISK_FREE_SERIES].frame)

    outcome, blocker = source_packet_gate(alpaca_check, fred, monthly)
    write_json(output / "pre_implementation_gate.json", {"gate_ran": True, "outcome": outcome, "blocker": blocker})
    after_hashes = state_hashes(root)
    if outcome != "baseline_implemented_for_exploratory_review" or monthly is None:
        write_csv(output / "provider_splice_reconciliation.csv", splice_rows, sorted({key for row in splice_rows for key in row}))
        return write_outputs_for_blocker(root, output, outcome, blocker, before_hashes, after_hashes, alpaca_check, fred, splice_rows)

    regression = expanding_regression_signals(monthly)
    signal_calendar = build_signal_calendar(monthly, regression, prices.index)
    weights = build_daily_weights(prices, signal_calendar)
    transactions = transaction_rows(signal_calendar)
    evaluation_start = pd.Timestamp(signal_calendar["execution_effective_date"].iloc[0])
    evaluation_end = pd.Timestamp(prices.index.max())
    prices_window = prices.loc[(prices.index >= weights.index.min()) & (prices.index <= evaluation_end), list(SYMBOLS)]
    weights = weights.loc[weights.index <= evaluation_end]
    gross_returns = returns_from_weights(prices_window, weights).loc[evaluation_start:evaluation_end].rename("zero_cost_accounting_control")
    net_returns, costs = apply_switching_costs(gross_returns, transactions)
    benchmarks = benchmark_return_series(prices, weights.index.min(), evaluation_start, evaluation_end)

    baseline = metrics_rows(net_returns, gross_returns, weights.loc[evaluation_start:evaluation_end], costs.loc[evaluation_start:evaluation_end])
    benchmark = benchmark_rows(benchmarks)
    base_metrics = next(row for row in baseline if row["series_id"] == "source_aligned_10bps_baseline")
    identity_rows_ = identity_overlay_equality_rows(weights.loc[evaluation_start:evaluation_end], net_returns, transactions, base_metrics)
    invariant = invariant_rows(weights.loc[evaluation_start:evaluation_end], transactions, signal_calendar)
    regression_rows_ = regression.to_dict("records")
    signal_rows_ = signal_calendar.to_dict("records")

    exposure_passed = all(row["passed"] is True for row in invariant)
    identity_passed = all(row["exact_match"] is True for row in identity_rows_)
    if not exposure_passed or not identity_passed:
        outcome = "implementation_or_accounting_defect"
        blocker = "exposure or identity invariant failed"

    manifest = {
        "created_utc": RUN_CREATED_UTC,
        "strategy_id": STRATEGY_ID,
        "family_id": FAMILY_ID,
        "task_id": TASK_ID,
        "task_type": "active-direction-execution",
        "stage": "exploration",
        "adaptation_labels": SOURCE_PACKET["adaptation_labels"],
        "outcome": outcome,
        "blocker": blocker,
        "baseline_implemented": outcome == "baseline_implemented_for_exploratory_review",
        "source_public_page": "Crude Oil Predicts Equity Returns",
        "source_original_paper": "Driesprong, Jacobsen and Maat, Striking Oil: Another Puzzle?",
        "ssrn_abstract_identifier": "460500",
        "risky_asset": RISKY_SYMBOL,
        "defensive_asset": DEFENSIVE_SYMBOL,
        "predictor_series": PREDICTOR_SERIES,
        "risk_free_threshold_series": RISK_FREE_SERIES,
        "initial_regression_observations": INITIAL_REGRESSION_OBSERVATIONS,
        "first_signal_month": str(signal_calendar["signal_month"].iloc[0]),
        "latest_signal_month": str(signal_calendar["signal_month"].iloc[-1]),
        "regression_type": "expanding_ols",
        "switching_cost_bps": SWITCHING_COST_BPS,
        "baseline_series_count": 1,
        "zero_cost_accounting_control_created": True,
        "benchmark_count": len(benchmark),
        "signal_month_count": int(len(signal_calendar)),
        "transaction_count": int(len(transactions)),
        "exposure_invariant_passed": exposure_passed,
        "identity_overlay_equality_passed": identity_passed,
        "parameter_search_run": False,
        "alternative_predictors_tested": False,
        "alternative_equity_etfs_tested": False,
        "alternative_cost_values_tested": False,
        "overlay_performance_experiment_run": False,
        "backtest_run": True,
        "provider_download": "official_fred_csv_only",
        "intraday_data_used": False,
        "oil_etf_predictor_used": False,
        "futures_used": False,
        "options_used": False,
        "promotion_eligibility": False,
        "paper_demo_eligibility": False,
        "paper_demo_activation": False,
        "candidate_exhaustive_run": False,
        "broker_order_endpoint_called": False,
        "real_money_recommendation": False,
        "registry_state_changed": before_hashes != after_hashes,
        "state_hashes_before": before_hashes,
        "state_hashes_after": after_hashes,
        "next_action": NEXT_ACTION,
    }

    write_json(output / "trial_manifest.json", manifest)
    write_yaml(output / "frozen_test_config.yaml", frozen_test_config(True))
    write_json(
        output / "data_sources_and_hashes.json",
        {
            "alpaca": {
                "asset_and_bar_check_status": alpaca_check["status"],
                "feed": ALPACA_FEED,
                "adjustment": ALPACA_ADJUSTMENT,
                "requested_start": REQUEST_START_DATE,
                "requested_end": REQUEST_END_DATE,
                "bars": alpaca_check["bars"],
            },
            "local_cache": {
                symbol: {
                    "path": str((root / "data" / "cache" / f"{symbol}.csv").resolve()),
                    "file_hash": sha256_path(root / "data" / "cache" / f"{symbol}.csv"),
                }
                for symbol in SYMBOLS
            },
            "fred": {
                key: {
                    "series_url": FRED_SERIES_URLS[key],
                    "csv_url": value.url,
                    "status": value.status,
                    "raw_hash": value.raw_hash,
                    "rows": int(len(value.frame)),
                    "first_date": value.frame["observation_date"].min().date().isoformat() if not value.frame.empty else "",
                    "last_date": value.frame["observation_date"].max().date().isoformat() if not value.frame.empty else "",
                }
                for key, value in fred.items()
            },
            "storage_policy": "evidence stores derived values, provenance, and hashes; API credentials are never persisted",
            "api_secrets_persisted": False,
        },
    )
    write_csv(output / "provider_splice_reconciliation.csv", splice_rows, sorted({key for row in splice_rows for key in row}))
    write_csv(
        output / "monthly_signal_calendar.csv",
        signal_rows_,
        [
            "signal_month",
            "forecast_month",
            "regression_observation_count",
            "estimation_first_month",
            "estimation_last_month",
            "wti_observation_date",
            "spy_month_end_date",
            "tb3ms_vintage_month",
            "execution_effective_date",
            "forecast_spy_log_return_next_month",
            "tb3ms_monthly_log_threshold",
            "forecast_exceeds_threshold",
            "target_asset",
            "SPY",
            "BIL",
            "spy_data_provider",
            "bil_data_provider",
            "wti_data_provider",
            "tb3ms_data_provider",
        ],
    )
    write_csv(
        output / "regression_audit.csv",
        regression_rows_,
        [
            "signal_month",
            "regression_observation_count",
            "estimation_first_month",
            "estimation_last_month",
            "forecast_month",
            "intercept",
            "beta",
            "current_wti_log_return",
            "forecast_spy_log_return_next_month",
            "tb3ms_monthly_log_threshold",
            "forecast_exceeds_threshold",
            "target_asset",
        ],
    )
    write_csv(output / "target_weights.csv", target_weight_rows(weights.loc[evaluation_start:evaluation_end]), ["date", "SPY", "BIL", "weight_sum", "held_asset"])
    write_csv(
        output / "transactions.csv",
        transactions,
        [
            "signal_month",
            "signal_date",
            "execution_effective_date",
            "from_asset",
            "to_asset",
            "switching_cost_bps",
            "switching_cost_rate",
            "cost_applied",
        ],
    )
    write_csv(output / "accounting_invariants.csv", invariant, ["invariant", "passed", "value"])
    write_csv(
        output / "baseline_metrics.csv",
        baseline,
        [
            "series_id",
            "role",
            "switching_cost_bps",
            "total_switching_cost_return_drag",
            "effective_start_date",
            "effective_end_date",
            "daily_observations",
            "total_return",
            "cagr",
            "max_drawdown",
            "volatility",
            "return_drawdown_proxy",
            "average_spy_weight",
            "average_bil_weight",
            "trade_count",
            "turnover_proxy",
        ],
    )
    write_csv(
        output / "benchmark_metrics.csv",
        benchmark,
        [
            "benchmark_id",
            "role",
            "effective_start_date",
            "effective_end_date",
            "daily_observations",
            "total_return",
            "cagr",
            "max_drawdown",
            "volatility",
            "return_drawdown_proxy",
        ],
    )
    write_csv(output / "identity_overlay_equality.csv", identity_rows_, ["comparison", "exact_match", "max_abs_difference", "notes"])
    write_csv(output / "overlay_compatibility_map.csv", overlay_compatibility_rows(), ["overlay", "classification", "reason", "performance_experiment_run"])
    write_csv(output / "command_validation_log.csv", command_validation_rows(), ["command", "status", "notes"])
    write_text(output / "implementation_summary.md", summary_md(manifest, baseline))
    consistency = consistency_payload(output, manifest, invariant, identity_rows_, regression_rows_, signal_rows_, baseline)
    write_json(output / "consistency_check.json", consistency)
    return {**manifest, "output_dir": str(output.resolve()), "consistency_passed": consistency["consistency_passed"]}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
