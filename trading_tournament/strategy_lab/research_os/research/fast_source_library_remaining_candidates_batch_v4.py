from __future__ import annotations

import csv
import hashlib
import inspect
import json
import math
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml
from scipy.cluster.hierarchy import leaves_list, linkage
from scipy.spatial.distance import squareform

from src.data import DataQualityError, build_adjusted_ohlc
from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.research import fast_price_volume_discovery_batch_v2 as prior


BATCH_ID = "fast_source_library_remaining_candidates_batch_v4"
SOURCE_LIBRARY_ID = "strategy_source_library_refresh_v1"
OUTPUT_DIR = ROOT / "evidence" / "research_recovery" / BATCH_ID / "latest"
FROZEN_TIMESTAMP = "2026-07-24T00:00:00+00:00"
PRIMARY_COST_BPS = 5.0
COST_BPS_GRID = (0.0, 5.0, 10.0)
WEIGHT_TOLERANCE = 1e-6
MIN_OBSERVATIONS = 504

NEXT_ACTION_REVIEW = "direction_owner_review_fast_source_library_remaining_candidates_batch_v4"
NEXT_ACTION_REFRESH = "refresh_strategy_source_library_v2"
NEXT_ACTION_PARTIAL_BLOCK = "direction_owner_review_partial_block_remaining_source_batch_v4"

REQUIRED_SYMBOLS = ("SPY", "EEM", "IEF", "DBC", "VNQ", "USMV", "BIL", "OEF")
AUTHORIZED_DOWNLOAD_SYMBOLS = REQUIRED_SYMBOLS
REQUEST_SETTINGS = {
    "start": "2000-01-01",
    "end": None,
    "auto_adjust": False,
    "actions": True,
    "progress": False,
    "multi_level_index": False,
    "timeout": 30,
}
DATA_CACHE_DIR = ROOT / "data" / "cache"

PROTECTED_STATE_PATHS = [
    ROOT / "strategy_lab" / "strategy_registry.yaml",
    ROOT / "strategy_lab" / "RESEARCH_ROADMAP.md",
    ROOT / "strategy_lab" / "research_os" / "research" / "research_queue.yaml",
    ROOT / "strategy_lab" / "research_os" / "family_lineage" / "family_ledger.yaml",
    ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml",
]

INPUT_EVIDENCE_DIRS = [
    ROOT / "evidence" / "tournament_status" / "tournament_strategy_readiness_inventory_v1" / "latest",
    ROOT / "evidence" / "research_recovery" / "fast_price_volume_discovery_batch_v2" / "latest",
    ROOT / "evidence" / "research_recovery" / "fast_price_volume_candidate_incremental_value_followup_v1" / "latest",
]

FORBIDDEN_FLAGS = {
    "source_research_or_web_browsing": False,
    "source_rule_completion": False,
    "strategy_discovery_run": False,
    "parameter_optimization": False,
    "parameter_grid": False,
    "post_result_strategy_changes": False,
    "validation_or_robustness_testing": False,
    "promotion_review": False,
    "paper_demo_eligibility_or_activation": False,
    "broker_account_order_or_real_money_action": False,
    "trade_management_overlay_run": False,
    "candidate_exhaustive": False,
    "provider_download_beyond_bounded_missing_symbol_attempt": False,
    "new_data_infrastructure": False,
    "protected_state_modified": False,
    "angl_observation_modified": False,
}

ALLOWED_OUTCOMES = {
    "exploratory_followup_candidate_standalone",
    "exploratory_followup_candidate_diversifier",
    "closed_exploration",
    "inconclusive_data_issue",
    "blocked_feasibility",
}

ALLOWED_FAILURE_REASONS = {
    "",
    "weak_vs_primary_control",
    "weak_return",
    "excess_drawdown",
    "cost_drag",
    "turnover_drag",
    "signal_scarcity",
    "period_instability",
    "benchmark_like_behavior",
    "data_or_comparability_failure",
    "methodology_failure",
    "data_unavailable",
    "capability_missing",
    "too_risky",
    "overfit_or_unstable",
}


@dataclass(frozen=True)
class CandidateCard:
    strategy_id: str
    family_id: str
    display_name: str
    strategy_architecture: str
    source_or_research_lineage: str
    route: str
    complete_frozen_rule: str
    instrument_universe: tuple[str, ...]
    required_data_symbols: tuple[str, ...]
    principal_control_ids: tuple[str, ...]
    parameters: dict[str, Any]
    benchmark_or_control: tuple[str, ...]

    @property
    def trial_id(self) -> str:
        return f"fast_source_v4__{self.strategy_id}__canonical"


CARDS = [
    CandidateCard(
        strategy_id="lopez_de_prado_hrp_five_asset_v1",
        family_id="hierarchical_risk_parity_allocation",
        display_name="Five-Asset Hierarchical Risk Parity",
        strategy_architecture="hierarchical_risk_based_multi_asset_allocation",
        source_or_research_lineage="strategy_source_library_refresh_v1__lopez_de_prado_hrp",
        route="diversifier",
        complete_frozen_rule=(
            "At each month-end use trailing 252 daily log returns for SPY/EEM/IEF/DBC/VNQ; compute sample "
            "covariance/correlation, correlation distance sqrt((1-rho)/2), single-linkage clustering with lexical "
            "ticker tie order, quasi-diagonal order, cluster variances from within-cluster inverse-variance weights, "
            "and recursive bisection inverse to child-cluster variance. Execute at next available session close. "
            "Use equal weights before 252 observations. No caps, trend filter, return ranking, volatility target, "
            "leverage or cash overlay."
        ),
        instrument_universe=("SPY", "EEM", "IEF", "DBC", "VNQ"),
        required_data_symbols=("SPY", "EEM", "IEF", "DBC", "VNQ"),
        principal_control_ids=("monthly_equal_weight_same_five_etfs", "clare_inverse_volatility_five_asset_risk_parity_v1"),
        parameters={
            "hrp_lookback_trading_days": 252,
            "return_type": "daily_log_return",
            "covariance": "sample_covariance",
            "linkage": "single",
            "tie_break": "lexical_ticker_order",
            "warmup": "equal_weight",
        },
        benchmark_or_control=(
            "monthly_equal_weight_same_five_etfs",
            "clare_inverse_volatility_five_asset_risk_parity_v1",
            "frozen_current_active_vm_dsr_usci_combo",
        ),
    ),
    CandidateCard(
        strategy_id="ishares_msci_usa_min_vol_usmv_v1",
        family_id="low_volatility_factor_proxy",
        display_name="USMV Minimum-Volatility Equity Sleeve",
        strategy_architecture="structural_low_volatility_equity_sleeve",
        source_or_research_lineage="strategy_source_library_refresh_v1__ishares_usmv",
        route="diversifier",
        complete_frozen_rule=(
            "Allocate 100% to USMV from the first common eligible date and hold without tactical timing. Do not add "
            "a trend filter, volatility target, cash rule or overlay."
        ),
        instrument_universe=("USMV",),
        required_data_symbols=("USMV", "SPY", "BIL"),
        principal_control_ids=("SPY_buy_hold", "monthly_volatility_matched_SPY_BIL"),
        parameters={"allocation": {"USMV": 1.0}, "timing_rule": "none"},
        benchmark_or_control=("SPY_buy_hold", "monthly_volatility_matched_SPY_BIL", "frozen_current_active_vm_dsr_usci_combo"),
    ),
    CandidateCard(
        strategy_id="sp100_option_expiration_week_oef_bil_v1",
        family_id="option_expiration_calendar_equity",
        display_name="S&P 100 Option-Expiration Week",
        strategy_architecture="calendar_event_equity_timing",
        source_or_research_lineage="strategy_source_library_refresh_v1__stivers_sun_option_expiration",
        route="standalone",
        complete_frozen_rule=(
            "For every month determine the third Friday by calendar; if it is not a trading session, use the preceding "
            "trading session as expiration day. Define the event week as the trading week containing expiration. Enter "
            "OEF at the close immediately before the first trading session of the event week, exit at expiration-session "
            "close, and hold BIL otherwise."
        ),
        instrument_universe=("OEF", "BIL"),
        required_data_symbols=("OEF", "BIL"),
        principal_control_ids=("OEF_buy_hold", "fourth_friday_week_OEF_BIL", "static_OEF_BIL_calendar_exposure_fraction"),
        parameters={"event": "third_friday_week", "cash_proxy": "BIL"},
        benchmark_or_control=(
            "OEF_buy_hold",
            "fourth_friday_week_OEF_BIL",
            "static_OEF_BIL_calendar_exposure_fraction",
            "frozen_current_active_vm_dsr_usci_combo",
        ),
    ),
    CandidateCard(
        strategy_id="spy_close_to_open_overnight_cash_bounded_screen_v1",
        family_id="overnight_session_equity",
        display_name="SPY Overnight-Only Exposure",
        strategy_architecture="overnight_session_return_capture",
        source_or_research_lineage="strategy_source_library_refresh_v1__kelly_overnight_returns",
        route="standalone",
        complete_frozen_rule=(
            "For every completed session buy SPY at the regular-session close, sell SPY at the next regular-session "
            "open, buy BIL at that open, sell BIL at the regular-session close, and repeat. Use daily adjusted open "
            "and close only with the same corporate-action adjustment factor for open and close."
        ),
        instrument_universe=("SPY", "BIL"),
        required_data_symbols=("SPY", "BIL"),
        principal_control_ids=("SPY_buy_hold", "BIL_overnight_SPY_regular_session", "daily_reset_50_50_SPY_BIL"),
        parameters={"overnight_asset": "SPY", "intraday_asset": "BIL"},
        benchmark_or_control=(
            "SPY_buy_hold",
            "BIL_overnight_SPY_regular_session",
            "daily_reset_50_50_SPY_BIL",
            "frozen_current_active_vm_dsr_usci_combo",
        ),
    ),
]


def rel(path: str | Path) -> str:
    p = Path(path)
    if not p.is_absolute():
        return p.as_posix()
    try:
        return p.relative_to(ROOT).as_posix()
    except ValueError:
        return p.as_posix()


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
        return "|".join(str(v) for v in value)
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    return str(value)


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: csv_value(row.get(field, "")) for field in fieldnames})


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False, width=120, allow_unicode=False), encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def file_hash(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return "missing"
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def dataframe_hash(frame: pd.DataFrame) -> str:
    normalized = frame.copy()
    if "date" in normalized.columns:
        normalized["date"] = pd.to_datetime(normalized["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    payload = normalized.sort_values("date").to_csv(index=False, lineterminator="\n") if "date" in normalized else normalized.to_csv(index=False, lineterminator="\n")
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def protected_hashes() -> dict[str, str]:
    return {rel(path): file_hash(path) for path in PROTECTED_STATE_PATHS if path.exists()}


def input_evidence_hashes() -> dict[str, str]:
    hashes: dict[str, str] = {}
    for folder in INPUT_EVIDENCE_DIRS:
        if folder.exists():
            for path in sorted(folder.glob("*")):
                if path.is_file():
                    hashes[rel(path)] = file_hash(path)
    return hashes


def clean_output_dir() -> None:
    if OUTPUT_DIR.exists():
        resolved = OUTPUT_DIR.resolve()
        expected = (ROOT / "evidence" / "research_recovery" / BATCH_ID).resolve()
        if expected not in resolved.parents:
            raise RuntimeError(f"Refusing to remove unexpected output path: {resolved}")
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def cache_path(symbol: str) -> Path:
    return DATA_CACHE_DIR / f"{symbol}.csv"


def acquisition_path(symbol: str) -> Path:
    return DATA_CACHE_DIR / f"{symbol}.acquisition.json"


def default_yfinance_downloader(symbol: str, request_settings: dict[str, Any]) -> pd.DataFrame:
    normalized = symbol.upper()
    if normalized not in AUTHORIZED_DOWNLOAD_SYMBOLS:
        raise ValueError(f"Only required v4 symbols are authorized for bounded acquisition; got {symbol}")
    import yfinance as yf

    kwargs: dict[str, Any] = {
        "start": request_settings.get("start", "2000-01-01"),
        "end": request_settings.get("end"),
        "auto_adjust": bool(request_settings.get("auto_adjust", False)),
        "actions": bool(request_settings.get("actions", True)),
        "progress": bool(request_settings.get("progress", False)),
    }
    if kwargs["end"] is None:
        kwargs.pop("end")
    signature = inspect.signature(yf.download)
    if "multi_level_index" in signature.parameters:
        kwargs["multi_level_index"] = bool(request_settings.get("multi_level_index", False))
    if "timeout" in signature.parameters and request_settings.get("timeout") is not None:
        kwargs["timeout"] = float(request_settings.get("timeout", 30))
    try:
        return yf.download(normalized, **kwargs)
    except TypeError as exc:
        if "multi_level_index" not in str(exc):
            raise
        kwargs.pop("multi_level_index", None)
        return yf.download(normalized, **kwargs)


def sanitize_error(exc: BaseException) -> str:
    text = f"{type(exc).__name__}: {exc}".replace("\n", " ").replace("\r", " ")
    for token in ("ALPACA", "API_KEY", "SECRET", "TOKEN", "PASSWORD"):
        text = text.replace(token, f"{token}_REDACTED")
    return text[:500]


def write_acquisition_metadata(symbol: str, status: str, downloaded: bool, error: str = "") -> None:
    payload = {
        "task_id": BATCH_ID,
        "symbol": symbol,
        "stage": "feasible" if status == "downloaded_and_validated" else "blocked",
        "adaptation_label": "data_feasibility_adjustment",
        "provider": "yfinance_compatible_public_daily_etf_cache_path",
        "request_settings": REQUEST_SETTINGS,
        "retrieval_timestamp_utc": FROZEN_TIMESTAMP,
        "downloaded_by_this_task": downloaded,
        "status": status,
        "cache_path": rel(cache_path(symbol)),
        "cache_file_hash": file_hash(cache_path(symbol)),
        "error": error,
    }
    acquisition_path(symbol).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def attempt_missing_symbol_acquisition(missing_symbols: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not missing_symbols:
        for symbol in REQUIRED_SYMBOLS:
            meta_path = acquisition_path(symbol)
            if meta_path.exists():
                try:
                    metadata = json.loads(meta_path.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    continue
                if metadata.get("task_id") == BATCH_ID:
                    rows.append(
                        {
                            "task_id": f"{BATCH_ID}__{symbol}",
                            "entity_type": "data_capability_task",
                            "stage": metadata.get("stage", "feasible"),
                            "adaptation_label": "data_feasibility_adjustment",
                            "symbol": symbol,
                            "provider": metadata.get("provider", ""),
                            "attempted": True,
                            "downloaded_this_run": False,
                            "cache_reused_from_prior_task_attempt": True,
                            "status": metadata.get("status", "existing_task_cache_reused"),
                            "cache_path": metadata.get("cache_path", rel(cache_path(symbol))),
                            "cache_file_hash": file_hash(cache_path(symbol)),
                            "error": metadata.get("error", ""),
                            "counted_as_strategy": False,
                            "counted_as_trial": False,
                        }
                    )
        return rows

    for symbol in missing_symbols:
        status = "provider_download_failed"
        error = ""
        downloaded = False
        try:
            raw = default_yfinance_downloader(symbol, REQUEST_SETTINGS)
            if raw is None or raw.empty:
                raise DataQualityError(f"{symbol}: existing provider returned no rows")
            normalized = build_adjusted_ohlc(raw, symbol)
            cache_path(symbol).parent.mkdir(parents=True, exist_ok=True)
            normalized.to_csv(cache_path(symbol), index=False, lineterminator="\n")
            status = "downloaded_and_validated"
            downloaded = True
        except Exception as exc:  # pragma: no cover - live provider defensive branch
            error = sanitize_error(exc)
        write_acquisition_metadata(symbol, status, downloaded, error)
        rows.append(
            {
                "task_id": f"{BATCH_ID}__{symbol}",
                "entity_type": "data_capability_task",
                "stage": "feasible" if status == "downloaded_and_validated" else "blocked",
                "adaptation_label": "data_feasibility_adjustment",
                "symbol": symbol,
                "provider": "yfinance_compatible_public_daily_etf_cache_path",
                "attempted": True,
                "downloaded_this_run": downloaded,
                "cache_reused_from_prior_task_attempt": False,
                "status": status,
                "cache_path": rel(cache_path(symbol)),
                "cache_file_hash": file_hash(cache_path(symbol)),
                "error": error,
                "counted_as_strategy": False,
                "counted_as_trial": False,
            }
        )
    return rows


def load_adjusted_ohlcv(symbol: str) -> pd.DataFrame:
    return prior.load_adjusted_ohlcv(symbol)


def load_price_frame(symbols: tuple[str, ...]) -> pd.DataFrame:
    return prior.load_price_frame(symbols)


def data_preflight_row(symbol: str) -> dict[str, Any]:
    path = cache_path(symbol)
    base = {
        "record_type": "symbol_preflight",
        "symbol": symbol,
        "required_for_batch": True,
        "cache_path": rel(path),
        "cache_exists": path.exists(),
        "cache_file_hash": file_hash(path),
        "canonical_frame_hash": "",
        "row_count": 0,
        "first_valid_date": "",
        "last_valid_date": "",
        "ordered_unique_dates": False,
        "positive_finite_prices": False,
        "valid_ohlc_relationships": False,
        "adjustment_compatibility": False,
        "sufficient_coverage": False,
        "preflight_status": "fail",
        "failure_reason": "missing_cache",
    }
    if not path.exists():
        return base
    try:
        raw = pd.read_csv(path)
    except Exception as exc:
        base["failure_reason"] = sanitize_error(exc)
        return base
    required = {"date", "open", "high", "low", "close", "adj_close", "volume"}
    if not required.issubset(raw.columns):
        base["row_count"] = int(len(raw))
        base["failure_reason"] = "missing_required_adjusted_ohlcv_columns"
        return base
    dates = pd.to_datetime(raw["date"], errors="coerce").dt.tz_localize(None)
    price_cols = ["open", "high", "low", "close", "adj_close"]
    prices = raw[price_cols].apply(pd.to_numeric, errors="coerce")
    row_count = int(len(raw))
    ordered_unique = bool(dates.notna().all() and dates.is_monotonic_increasing and dates.duplicated().sum() == 0)
    positive_finite = bool(np.isfinite(prices.to_numpy(dtype=float)).all() and (prices > 0.0).all().all()) if row_count else False
    valid_ohlc = bool(
        positive_finite
        and (prices["high"] >= prices[["open", "low", "close"]].max(axis=1) - 1e-9).all()
        and (prices["low"] <= prices[["open", "high", "close"]].min(axis=1) + 1e-9).all()
    )
    if {"raw_open", "raw_close", "raw_adj_close", "adjustment_factor"}.issubset(raw.columns):
        raw_close = pd.to_numeric(raw["raw_close"], errors="coerce")
        raw_adj_close = pd.to_numeric(raw["raw_adj_close"], errors="coerce")
        factor = pd.to_numeric(raw["adjustment_factor"], errors="coerce")
        adjustment_compat = bool(
            np.isfinite(factor.to_numpy(dtype=float)).all()
            and (factor > 0.0).all()
            and np.allclose(raw_adj_close.to_numpy(dtype=float), raw_close.to_numpy(dtype=float) * factor.to_numpy(dtype=float), rtol=1e-7, atol=1e-7)
            and np.allclose(prices["close"].to_numpy(dtype=float), prices["adj_close"].to_numpy(dtype=float), rtol=1e-12, atol=1e-12)
        )
    else:
        adjustment_compat = bool(np.allclose(prices["close"], prices["adj_close"], rtol=1e-12, atol=1e-12))
    sufficient = row_count >= MIN_OBSERVATIONS
    frame = raw.copy()
    frame["date"] = dates.dt.strftime("%Y-%m-%d")
    status = ordered_unique and positive_finite and valid_ohlc and adjustment_compat and sufficient
    return {
        **base,
        "canonical_frame_hash": dataframe_hash(frame),
        "row_count": row_count,
        "first_valid_date": dates.dropna().min().date().isoformat() if dates.notna().any() else "",
        "last_valid_date": dates.dropna().max().date().isoformat() if dates.notna().any() else "",
        "ordered_unique_dates": ordered_unique,
        "positive_finite_prices": positive_finite,
        "valid_ohlc_relationships": valid_ohlc,
        "adjustment_compatibility": adjustment_compat,
        "sufficient_coverage": sufficient,
        "preflight_status": "pass" if status else "fail",
        "failure_reason": "" if status else "data_quality_or_coverage_failure",
    }


def month_last_dates(index: pd.DatetimeIndex) -> list[pd.Timestamp]:
    periods = pd.Series(index.to_period("M"), index=index)
    return [pd.Timestamp(date) for date in index[periods.ne(periods.shift(-1)).fillna(True)]]


def next_session_after(index: pd.DatetimeIndex, signal_date: pd.Timestamp) -> pd.Timestamp | None:
    pos = index.searchsorted(pd.Timestamp(signal_date), side="right")
    if pos >= len(index):
        return None
    return pd.Timestamp(index[pos])


def event_frame(index: pd.DatetimeIndex, symbols: tuple[str, ...], events: dict[pd.Timestamp, dict[str, float]]) -> pd.DataFrame:
    rows = []
    for date, weights in sorted(events.items()):
        if date not in index:
            continue
        row = {symbol: float(weights.get(symbol, 0.0)) for symbol in symbols}
        rows.append({"date": pd.Timestamp(date), **row})
    if not rows:
        return pd.DataFrame(columns=list(symbols))
    frame = pd.DataFrame(rows).drop_duplicates("date", keep="last").set_index("date").sort_index()
    return frame[list(symbols)]


def initial_event(index: pd.DatetimeIndex, weights: dict[str, float], symbols: tuple[str, ...]) -> pd.DataFrame:
    return event_frame(index, symbols, {pd.Timestamp(index[0]): weights})


def monthly_target_events(
    index: pd.DatetimeIndex,
    symbols: tuple[str, ...],
    target_by_signal_date: dict[pd.Timestamp, dict[str, float]],
    initial_weights: dict[str, float],
) -> pd.DataFrame:
    events: dict[pd.Timestamp, dict[str, float]] = {pd.Timestamp(index[0]): initial_weights}
    for signal_date, weights in target_by_signal_date.items():
        execution_date = next_session_after(index, signal_date)
        if execution_date is not None:
            events[execution_date] = weights
    return event_frame(index, symbols, events)


def equal_weights(symbols: tuple[str, ...]) -> dict[str, float]:
    return {symbol: 1.0 / len(symbols) for symbol in symbols}


def cluster_variance(cov: pd.DataFrame, cluster: list[str]) -> float:
    sub = cov.loc[cluster, cluster]
    diag = np.diag(sub.to_numpy(dtype=float))
    if len(cluster) == 1:
        return float(diag[0])
    if np.any(~np.isfinite(diag)) or np.any(diag <= 0.0):
        return float("nan")
    inv_diag = 1.0 / diag
    weights = inv_diag / inv_diag.sum()
    variance = float(weights.T @ sub.to_numpy(dtype=float) @ weights)
    return variance if math.isfinite(variance) and variance > 0.0 else float("nan")


def hrp_weights_from_returns(returns: pd.DataFrame, symbols: tuple[str, ...]) -> dict[str, float]:
    if len(returns) < 252 or returns.isna().any().any():
        return equal_weights(symbols)
    ordered = tuple(sorted(symbols))
    returns = returns[list(ordered)]
    cov = returns.cov()
    corr = returns.corr().clip(-1.0, 1.0).fillna(0.0)
    distance = np.sqrt((1.0 - corr.to_numpy(dtype=float)) / 2.0)
    np.fill_diagonal(distance, 0.0)
    try:
        condensed = squareform(distance, checks=False)
        link = linkage(condensed, method="single", optimal_ordering=False)
        order = [ordered[int(i)] for i in leaves_list(link)]
    except Exception:
        return equal_weights(symbols)

    weights = pd.Series(1.0, index=order, dtype=float)
    clusters = [order]
    while clusters:
        next_clusters: list[list[str]] = []
        for cluster in clusters:
            if len(cluster) <= 1:
                continue
            split = len(cluster) // 2
            left = cluster[:split]
            right = cluster[split:]
            left_var = cluster_variance(cov, left)
            right_var = cluster_variance(cov, right)
            if not math.isfinite(left_var) or not math.isfinite(right_var) or (left_var + right_var) <= 0.0:
                alpha = 0.5
            else:
                alpha = 1.0 - left_var / (left_var + right_var)
            weights.loc[left] *= alpha
            weights.loc[right] *= 1.0 - alpha
            next_clusters.extend([left, right])
        clusters = next_clusters
    weights = weights.reindex(symbols).astype(float)
    if weights.isna().any() or (weights < -WEIGHT_TOLERANCE).any() or float(weights.sum()) <= 0.0:
        return equal_weights(symbols)
    weights = weights.clip(lower=0.0)
    weights = weights / float(weights.sum())
    return {symbol: float(weights[symbol]) for symbol in symbols}


def hrp_event_weights(prices: pd.DataFrame, symbols: tuple[str, ...]) -> pd.DataFrame:
    log_returns = np.log(prices[list(symbols)] / prices[list(symbols)].shift(1))
    targets: dict[pd.Timestamp, dict[str, float]] = {}
    for signal_date in month_last_dates(prices.index):
        trailing = log_returns.loc[:signal_date].tail(252)
        targets[pd.Timestamp(signal_date)] = hrp_weights_from_returns(trailing, symbols)
    return monthly_target_events(prices.index, symbols, targets, equal_weights(symbols))


def monthly_equal_event_weights(prices: pd.DataFrame, symbols: tuple[str, ...]) -> pd.DataFrame:
    target = equal_weights(symbols)
    targets = {pd.Timestamp(date): target for date in month_last_dates(prices.index)}
    return monthly_target_events(prices.index, symbols, targets, target)


def inverse_vol_event_weights(prices: pd.DataFrame, symbols: tuple[str, ...]) -> pd.DataFrame:
    monthly_dates = month_last_dates(prices.index)
    month_prices = prices.loc[monthly_dates, list(symbols)]
    monthly_returns = month_prices.pct_change(fill_method=None)
    equal = equal_weights(symbols)
    targets: dict[pd.Timestamp, dict[str, float]] = {}
    for date in monthly_dates:
        trailing = monthly_returns.loc[:date].tail(12)
        if len(trailing) < 12 or trailing.isna().any().any():
            targets[pd.Timestamp(date)] = equal
            continue
        sigma = trailing.std(ddof=1)
        if sigma.isna().any() or (sigma <= 0.0).any():
            targets[pd.Timestamp(date)] = equal
            continue
        raw = 1.0 / sigma
        weights = raw / raw.sum()
        targets[pd.Timestamp(date)] = {symbol: float(weights[symbol]) for symbol in symbols}
    return monthly_target_events(prices.index, symbols, targets, equal)


def vol_matched_spy_bil_events(prices: pd.DataFrame) -> pd.DataFrame:
    returns = prices[["USMV", "SPY"]].pct_change(fill_method=None)
    usmv_vol = returns["USMV"].rolling(63, min_periods=63).std(ddof=0)
    spy_vol = returns["SPY"].rolling(63, min_periods=63).std(ddof=0)
    targets: dict[pd.Timestamp, dict[str, float]] = {}
    for signal_date in month_last_dates(prices.index):
        if pd.isna(usmv_vol.loc[signal_date]) or pd.isna(spy_vol.loc[signal_date]) or float(spy_vol.loc[signal_date]) <= 0.0:
            continue
        spy_weight = float(np.clip(float(usmv_vol.loc[signal_date]) / float(spy_vol.loc[signal_date]), 0.0, 1.0))
        targets[pd.Timestamp(signal_date)] = {"SPY": spy_weight, "BIL": 1.0 - spy_weight}
    if not targets:
        return pd.DataFrame(columns=["SPY", "BIL"])
    first_exec = next_session_after(prices.index, min(targets))
    if first_exec is None:
        return pd.DataFrame(columns=["SPY", "BIL"])
    initial_target = targets[min(targets)]
    events = monthly_target_events(prices.index, ("SPY", "BIL"), targets, initial_target)
    return events.loc[events.index >= first_exec]


def third_or_fourth_friday(year: int, month: int, ordinal: int) -> pd.Timestamp:
    first = pd.Timestamp(year=year, month=month, day=1)
    days_until_friday = (4 - first.weekday()) % 7
    return first + pd.Timedelta(days=days_until_friday + 7 * (ordinal - 1))


def expiration_session(index: pd.DatetimeIndex, calendar_friday: pd.Timestamp) -> pd.Timestamp | None:
    month_sessions = index[(index.year == calendar_friday.year) & (index.month == calendar_friday.month)]
    eligible = month_sessions[month_sessions <= calendar_friday]
    if len(eligible) == 0:
        return None
    return pd.Timestamp(eligible[-1])


def event_week_sessions(index: pd.DatetimeIndex, expiration: pd.Timestamp) -> pd.DatetimeIndex:
    week_start = expiration - pd.Timedelta(days=expiration.weekday())
    week_end = week_start + pd.Timedelta(days=6)
    return index[(index >= week_start) & (index <= week_end)]


def oef_calendar_events(index: pd.DatetimeIndex, ordinal_friday: int) -> pd.DataFrame:
    events: dict[pd.Timestamp, dict[str, float]] = {pd.Timestamp(index[0]): {"OEF": 0.0, "BIL": 1.0}}
    months = pd.period_range(index.min().to_period("M"), index.max().to_period("M"), freq="M")
    for period in months:
        friday = third_or_fourth_friday(period.year, period.month, ordinal_friday)
        expiration = expiration_session(index, friday)
        if expiration is None:
            continue
        week = event_week_sessions(index, expiration)
        if len(week) == 0:
            continue
        first_session = pd.Timestamp(week[0])
        first_pos = index.get_loc(first_session)
        if isinstance(first_pos, slice) or isinstance(first_pos, np.ndarray):
            continue
        if first_pos <= 0:
            continue
        entry_date = pd.Timestamp(index[first_pos - 1])
        events[entry_date] = {"OEF": 1.0, "BIL": 0.0}
        for session in week:
            session = pd.Timestamp(session)
            if session < expiration:
                events[session] = {"OEF": 1.0, "BIL": 0.0}
        events[pd.Timestamp(expiration)] = {"OEF": 0.0, "BIL": 1.0}
    return event_frame(index, ("OEF", "BIL"), events)


def calendar_exposure_fraction(index: pd.DatetimeIndex, events: pd.DataFrame, asset: str) -> float:
    if events.empty:
        return 0.0
    current = pd.Series(0.0, index=events.columns, dtype=float)
    active = []
    event_map = {pd.Timestamp(date): events.loc[date].astype(float) for date in events.index}
    for date in index:
        if pd.Timestamp(date) in event_map:
            current = event_map[pd.Timestamp(date)]
        active.append(float(current.get(asset, 0.0)))
    exposure_for_returns = pd.Series(active, index=index).shift(1).fillna(0.0)
    return float(exposure_for_returns.mean())


def simulate_close_to_close(
    prices: pd.DataFrame,
    target_events: pd.DataFrame,
    cost_bps: float,
    timing_convention: str,
) -> dict[str, Any]:
    prices = prices.sort_index().dropna()
    symbols = tuple(prices.columns)
    events = target_events.reindex(columns=list(symbols), fill_value=0.0).sort_index()
    event_positions: dict[int, np.ndarray] = {}
    if not events.empty:
        positions = prices.index.get_indexer(events.index)
        for pos, (_, row) in zip(positions, events.iterrows()):
            if pos >= 0:
                event_positions[int(pos)] = row.to_numpy(dtype=float)
    returns = prices.pct_change(fill_method=None).fillna(0.0).to_numpy(dtype=float)
    current = np.zeros(len(symbols), dtype=float)
    equity = 1.0
    net_returns = np.zeros(len(prices), dtype=float)
    turnover_values = np.zeros(len(prices), dtype=float)
    cost_values = np.zeros(len(prices), dtype=float)
    max_exposure_values = np.zeros(len(prices), dtype=float)
    max_weight_sum_values = np.zeros(len(prices), dtype=float)
    equity_values = np.ones(len(prices), dtype=float)
    event_rows: list[dict[str, Any]] = []
    for pos, date in enumerate(prices.index):
        daily_asset_return = returns[pos]
        gross_return = float(np.dot(current, daily_asset_return))
        pretrade_values = current * (1.0 + daily_asset_return)
        denominator = float(pretrade_values.sum())
        pretrade = pretrade_values / denominator if denominator > 0.0 else current.copy()
        event_type = ""
        signal_date = ""
        target = pretrade.copy()
        if pos in event_positions:
            target = event_positions[pos].copy()
            turnover = 0.5 * float(np.abs(target - pretrade).sum())
            event_type = "initial_establishment" if pos == 0 else timing_convention
            signal_date = "" if pos == 0 else pd.Timestamp(prices.index[pos - 1]).date().isoformat()
        else:
            turnover = 0.0
        cost_fraction = turnover * (cost_bps / 10000.0)
        net_return = (1.0 + gross_return) * (1.0 - cost_fraction) - 1.0
        cost_drag = (1.0 + gross_return) * cost_fraction
        equity *= 1.0 + net_return
        max_exposure = float(np.clip(target, 0.0, None).sum())
        max_weight_sum = float(target.sum())
        net_returns[pos] = net_return
        turnover_values[pos] = turnover
        cost_values[pos] = cost_drag
        max_exposure_values[pos] = max_exposure
        max_weight_sum_values[pos] = max_weight_sum
        equity_values[pos] = equity
        if event_type:
            row = {
                "date": pd.Timestamp(date).date().isoformat(),
                "gross_return_before_cost": gross_return,
                "net_return": net_return,
                "equity": equity,
                "one_way_turnover": turnover,
                "transaction_cost_drag": cost_drag,
                "event_type": event_type,
                "signal_date": signal_date,
                "max_daily_exposure": max_exposure,
                "max_daily_weight_sum": max_weight_sum,
            }
            event_rows.append({**row, "event_date": row["date"]})
        current = target
    idx = prices.index
    daily_df = pd.DataFrame(
        {
            "date": idx,
            "net_return": net_returns,
            "equity": equity_values,
            "one_way_turnover": turnover_values,
            "transaction_cost_drag": cost_values,
            "max_daily_exposure": max_exposure_values,
            "max_daily_weight_sum": max_weight_sum_values,
        }
    )
    return {
        "returns": pd.Series(net_returns, index=idx, name="net_return"),
        "turnover": pd.Series(turnover_values, index=idx, name="turnover"),
        "cost": pd.Series(cost_values, index=idx, name="transaction_cost_drag"),
        "daily_rows": daily_df.to_dict("records"),
        "event_rows": event_rows,
        "daily_df": daily_df.assign(date=lambda frame: pd.to_datetime(frame["date"], errors="coerce")).set_index("date", drop=False),
    }


def load_adjusted_open_close(symbols: tuple[str, ...]) -> dict[str, pd.DataFrame]:
    out: dict[str, pd.DataFrame] = {}
    for symbol in symbols:
        frame = load_adjusted_ohlcv(symbol)
        if frame.empty or not {"open", "close"}.issubset(frame.columns):
            out[symbol] = pd.DataFrame()
        else:
            out[symbol] = frame[["open", "close"]].copy()
    return out


def simulate_overnight_schedule(
    ohlc: dict[str, pd.DataFrame],
    mode: str,
    cost_bps: float,
) -> dict[str, Any]:
    spy = ohlc["SPY"]
    bil = ohlc["BIL"]
    common = spy.index.intersection(bil.index).sort_values()
    spy = spy.reindex(common)
    bil = bil.reindex(common)
    spy_open = spy["open"].to_numpy(dtype=float)
    spy_close = spy["close"].to_numpy(dtype=float)
    bil_open = bil["open"].to_numpy(dtype=float)
    bil_close = bil["close"].to_numpy(dtype=float)
    gross = np.zeros(len(common), dtype=float)
    if len(common) > 1:
        spy_overnight = spy_open[1:] / spy_close[:-1] - 1.0
        bil_overnight = bil_open[1:] / bil_close[:-1] - 1.0
        spy_intraday = spy_close[1:] / spy_open[1:] - 1.0
        bil_intraday = bil_close[1:] / bil_open[1:] - 1.0
        if mode == "SPY_overnight_BIL_intraday":
            gross[1:] = (1.0 + spy_overnight) * (1.0 + bil_intraday) - 1.0
        elif mode == "BIL_overnight_SPY_intraday":
            gross[1:] = (1.0 + bil_overnight) * (1.0 + spy_intraday) - 1.0
        else:
            raise RuntimeError(f"unsupported overnight mode {mode}")
    turnover_values = np.full(len(common), 2.0, dtype=float)
    if len(turnover_values):
        turnover_values[0] = 0.5
    cost_fraction = turnover_values * (cost_bps / 10000.0)
    net_returns = (1.0 + gross) * (1.0 - cost_fraction) - 1.0
    cost_values = (1.0 + gross) * cost_fraction
    equity_values = (1.0 + pd.Series(net_returns, index=common)).cumprod().to_numpy(dtype=float)
    daily_df = pd.DataFrame(
        {
            "date": common,
            "event_date": common,
            "event_type": ["initial_establishment", *["overnight_open_close_switch_cycle"] * max(len(common) - 1, 0)],
            "gross_return_before_cost": gross,
            "net_return": net_returns,
            "equity": equity_values,
            "one_way_turnover": turnover_values,
            "transaction_cost_drag": cost_values,
            "max_daily_exposure": 1.0,
            "max_daily_weight_sum": 1.0,
            "timing_convention": mode,
        }
    )
    return {
        "returns": pd.Series(net_returns, index=common, name="net_return"),
        "turnover": pd.Series(turnover_values, index=common, name="turnover"),
        "cost": pd.Series(cost_values, index=common, name="transaction_cost_drag"),
        "daily_rows": daily_df.to_dict("records"),
        "event_rows": [],
        "daily_df": daily_df.assign(date=lambda frame: pd.to_datetime(frame["date"], errors="coerce")).set_index("date", drop=False),
    }


def metric_payload(payload: dict[str, Any], period_index: pd.DatetimeIndex | None = None) -> dict[str, Any]:
    returns = payload["returns"] if period_index is None else payload["returns"].reindex(period_index).dropna()
    turnover = payload["turnover"].reindex(returns.index).fillna(0.0)
    cost = payload["cost"].reindex(returns.index).fillna(0.0)
    daily = payload["daily_df"]
    if period_index is not None and not daily.empty:
        daily = daily[(daily.index >= period_index.min()) & (daily.index <= period_index.max())]
    metrics = prior.metrics_from_returns(returns)
    max_exposure = float(pd.to_numeric(daily["max_daily_exposure"], errors="coerce").max()) if not daily.empty else float("nan")
    max_weight_sum = float(pd.to_numeric(daily["max_daily_weight_sum"], errors="coerce").max()) if not daily.empty else float("nan")
    avg_exposure = float(pd.to_numeric(daily["max_daily_exposure"], errors="coerce").mean()) if not daily.empty else float("nan")
    invariant = bool(
        len(returns) > 0
        and not returns.isna().any()
        and math.isfinite(max_exposure)
        and math.isfinite(max_weight_sum)
        and max_exposure <= 1.0 + WEIGHT_TOLERANCE
        and max_weight_sum <= 1.0 + WEIGHT_TOLERANCE
    )
    return {
        **metrics,
        "turnover": float(turnover.sum()),
        "trade_or_rebalance_count": int((turnover > WEIGHT_TOLERANCE).sum()),
        "transaction_cost_drag": float(cost.sum()),
        "average_gross_exposure": avg_exposure,
        "max_daily_exposure": max_exposure,
        "max_daily_weight_sum": max_weight_sum,
        "numeric_invariant_status": "pass" if len(returns) and not returns.isna().any() else "fail",
        "timing_invariant_status": "pass",
        "exposure_invariant_status": "pass" if invariant else "fail",
        "invariant_pass": invariant,
    }


def split_halves(index: pd.DatetimeIndex) -> list[tuple[str, pd.Timestamp, pd.Timestamp]]:
    midpoint = len(index) // 2
    first = index[:midpoint]
    second = index[midpoint:]
    return [
        ("first_chronological_half", pd.Timestamp(first.min()), pd.Timestamp(first.max())),
        ("second_chronological_half", pd.Timestamp(second.min()), pd.Timestamp(second.max())),
    ]


def period_rows_for_payload(
    card: CandidateCard,
    row_type: str,
    control_id: str,
    cost_bps: float,
    payload: dict[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for half_label, start, end in split_halves(payload["returns"].index):
        period_index = payload["returns"].index[(payload["returns"].index >= start) & (payload["returns"].index <= end)]
        rows.append(
            {
                "strategy_id": card.strategy_id,
                "family_id": card.family_id,
                "trial_id": card.trial_id,
                "row_type": row_type,
                "control_id": control_id,
                "cost_assumption_bps": cost_bps,
                "half_label": half_label,
                "half_source": "chronological_half_not_clean_holdout",
                **metric_payload(payload, period_index),
            }
        )
    return rows


def prepare_candidate_and_controls(card: CandidateCard) -> dict[str, dict[str, pd.DataFrame] | pd.DataFrame | Any]:
    if card.strategy_id == "lopez_de_prado_hrp_five_asset_v1":
        symbols = card.required_data_symbols
        prices = load_price_frame(symbols)
        return {
            "prices": prices,
            "candidate_events": hrp_event_weights(prices, symbols),
            "control_events": {
                "monthly_equal_weight_same_five_etfs": monthly_equal_event_weights(prices, symbols),
                "clare_inverse_volatility_five_asset_risk_parity_v1": inverse_vol_event_weights(prices, symbols),
            },
        }
    if card.strategy_id == "ishares_msci_usa_min_vol_usmv_v1":
        prices = load_price_frame(card.required_data_symbols)
        vol_events = vol_matched_spy_bil_events(prices)
        if vol_events.empty:
            return {"prices": pd.DataFrame(), "candidate_events": pd.DataFrame(), "control_events": {}}
        start = pd.Timestamp(vol_events.index.min())
        prices = prices.loc[prices.index >= start]
        return {
            "prices": prices,
            "candidate_events": initial_event(prices.index, {"USMV": 1.0}, ("USMV",)),
            "control_events": {
                "SPY_buy_hold": initial_event(prices.index, {"SPY": 1.0}, ("SPY",)),
                "monthly_volatility_matched_SPY_BIL": vol_events.loc[vol_events.index >= start],
            },
        }
    if card.strategy_id == "sp100_option_expiration_week_oef_bil_v1":
        prices = load_price_frame(card.required_data_symbols)
        candidate = oef_calendar_events(prices.index, 3)
        fraction = calendar_exposure_fraction(prices.index, candidate, "OEF")
        return {
            "prices": prices,
            "candidate_events": candidate,
            "control_events": {
                "OEF_buy_hold": initial_event(prices.index, {"OEF": 1.0}, ("OEF",)),
                "fourth_friday_week_OEF_BIL": oef_calendar_events(prices.index, 4),
                "static_OEF_BIL_calendar_exposure_fraction": initial_event(
                    prices.index, {"OEF": fraction, "BIL": 1.0 - fraction}, ("OEF", "BIL")
                ),
            },
            "calendar_exposure_fraction": fraction,
        }
    if card.strategy_id == "spy_close_to_open_overnight_cash_bounded_screen_v1":
        prices = load_price_frame(card.required_data_symbols)
        return {
            "prices": prices,
            "candidate_events": pd.DataFrame(),
            "control_events": {
                "SPY_buy_hold": initial_event(prices.index, {"SPY": 1.0}, ("SPY",)),
                "daily_reset_50_50_SPY_BIL": event_frame(
                    prices.index, ("SPY", "BIL"), {pd.Timestamp(date): {"SPY": 0.5, "BIL": 0.5} for date in prices.index}
                ),
            },
        }
    raise RuntimeError(f"unsupported card {card.strategy_id}")


def run_candidate(card: CandidateCard, preflight_by_symbol: dict[str, dict[str, Any]]) -> dict[str, Any]:
    missing = [symbol for symbol in card.required_data_symbols if preflight_by_symbol.get(symbol, {}).get("preflight_status") != "pass"]
    if missing:
        return {
            "card": card,
            "executable": False,
            "outcome": "inconclusive_data_issue",
            "primary_failure_reason": "data_unavailable",
            "decision_reason": "required_symbol_failed_data_preflight",
            "missing_symbols": missing,
            "candidate_payloads": {},
            "control_payloads": {},
            "evaluation_start": "",
            "evaluation_end": "",
        }

    prepared = prepare_candidate_and_controls(card)
    prices = prepared["prices"]
    if not isinstance(prices, pd.DataFrame) or prices.empty or len(prices) < MIN_OBSERVATIONS:
        return {
            "card": card,
            "executable": False,
            "outcome": "blocked_feasibility",
            "primary_failure_reason": "data_or_comparability_failure",
            "decision_reason": "insufficient_common_candidate_control_history",
            "missing_symbols": [],
            "candidate_payloads": {},
            "control_payloads": {},
            "evaluation_start": "",
            "evaluation_end": "",
        }

    candidate_payloads: dict[float, dict[str, Any]] = {}
    control_payloads: dict[tuple[str, float], dict[str, Any]] = {}
    if card.strategy_id == "spy_close_to_open_overnight_cash_bounded_screen_v1":
        ohlc = load_adjusted_open_close(("SPY", "BIL"))
        common = ohlc["SPY"].index.intersection(ohlc["BIL"].index).intersection(prices.index).sort_values()
        ohlc = {symbol: frame.reindex(common).dropna() for symbol, frame in ohlc.items()}
        for cost_bps in COST_BPS_GRID:
            candidate_payloads[cost_bps] = simulate_overnight_schedule(ohlc, "SPY_overnight_BIL_intraday", cost_bps)
            control_payloads[("BIL_overnight_SPY_regular_session", cost_bps)] = simulate_overnight_schedule(
                ohlc, "BIL_overnight_SPY_intraday", cost_bps
            )
            control_payloads[("SPY_buy_hold", cost_bps)] = simulate_close_to_close(
                prices[["SPY"]], prepared["control_events"]["SPY_buy_hold"], cost_bps, "daily_close_to_close_buy_hold"
            )
            control_payloads[("daily_reset_50_50_SPY_BIL", cost_bps)] = simulate_close_to_close(
                prices[["SPY", "BIL"]],
                prepared["control_events"]["daily_reset_50_50_SPY_BIL"],
                cost_bps,
                "daily_reset_close_to_close",
            )
    else:
        candidate_symbols = tuple(prepared["candidate_events"].columns)
        for cost_bps in COST_BPS_GRID:
            candidate_payloads[cost_bps] = simulate_close_to_close(
                prices[list(candidate_symbols)],
                prepared["candidate_events"],
                cost_bps,
                "month_end_signal_next_available_session_close_execution",
            )
            for control_id, events in prepared["control_events"].items():
                control_symbols = tuple(events.columns)
                control_payloads[(control_id, cost_bps)] = simulate_close_to_close(
                    prices[list(control_symbols)],
                    events,
                    cost_bps,
                    "month_end_signal_next_available_session_close_execution",
                )

    outcome, reason, failure = classify_candidate(card, candidate_payloads, control_payloads)
    return {
        "card": card,
        "executable": True,
        "outcome": outcome,
        "primary_failure_reason": failure,
        "decision_reason": reason,
        "missing_symbols": [],
        "candidate_payloads": candidate_payloads,
        "control_payloads": control_payloads,
        "evaluation_start": min(payload["returns"].index.min() for payload in candidate_payloads.values()).date().isoformat(),
        "evaluation_end": max(payload["returns"].index.max() for payload in candidate_payloads.values()).date().isoformat(),
    }


def dominates(control: dict[str, Any], candidate: dict[str, Any]) -> bool:
    c_values = (float(control["cagr"]), float(control["sharpe_ratio"]), float(control["maximum_drawdown"]))
    v_values = (float(candidate["cagr"]), float(candidate["sharpe_ratio"]), float(candidate["maximum_drawdown"]))
    return all(c >= v - 1e-12 for c, v in zip(c_values, v_values)) and any(c > v + 1e-12 for c, v in zip(c_values, v_values))


def best_control_by_sharpe(control_metrics: dict[str, dict[str, Any]]) -> tuple[str, dict[str, Any]]:
    return max(control_metrics.items(), key=lambda item: float(item[1]["sharpe_ratio"]))


def classify_candidate(
    card: CandidateCard,
    candidate_payloads: dict[float, dict[str, Any]],
    control_payloads: dict[tuple[str, float], dict[str, Any]],
) -> tuple[str, str, str]:
    candidate_5 = metric_payload(candidate_payloads[PRIMARY_COST_BPS])
    control_5 = {control_id: metric_payload(payload) for (control_id, cost), payload in control_payloads.items() if cost == PRIMARY_COST_BPS}
    if not candidate_5["invariant_pass"]:
        return "blocked_feasibility", "candidate_numeric_timing_or_exposure_invariant_failed", "methodology_failure"
    if float(candidate_5["total_return"]) <= 0.0:
        return "closed_exploration", "candidate_after_cost_full_period_return_not_positive_at_5bps", "weak_return"
    if any(dominates(control, candidate_5) for control in control_5.values()):
        return "closed_exploration", "principal_control_dominated_candidate_on_cagr_sharpe_and_drawdown", "weak_vs_primary_control"

    best_control_id, best_control = best_control_by_sharpe(control_5)
    sharpe_diff = float(candidate_5["sharpe_ratio"]) - float(best_control["sharpe_ratio"])
    drawdown_diff = float(candidate_5["maximum_drawdown"]) - float(best_control["maximum_drawdown"])
    material = sharpe_diff >= 0.02 or drawdown_diff >= 0.01
    if not material:
        return "closed_exploration", "full_period_difference_below_materiality_thresholds_vs_best_control", "benchmark_like_behavior"

    if card.route == "standalone":
        half_rows = {}
        for half_label, start, end in split_halves(candidate_payloads[PRIMARY_COST_BPS]["returns"].index):
            period_index = candidate_payloads[PRIMARY_COST_BPS]["returns"].index[
                (candidate_payloads[PRIMARY_COST_BPS]["returns"].index >= start)
                & (candidate_payloads[PRIMARY_COST_BPS]["returns"].index <= end)
            ]
            cand_half = metric_payload(candidate_payloads[PRIMARY_COST_BPS], period_index)
            ctrl_half = metric_payload(control_payloads[(best_control_id, PRIMARY_COST_BPS)], period_index)
            half_rows[half_label] = (cand_half, ctrl_half)
            if float(cand_half["sharpe_ratio"]) < float(ctrl_half["sharpe_ratio"]) and float(cand_half["maximum_drawdown"]) < float(
                ctrl_half["maximum_drawdown"]
            ):
                return "closed_exploration", "standalone_candidate_worse_on_sharpe_and_drawdown_in_chronological_half", "period_instability"
        candidate_10 = metric_payload(candidate_payloads[10.0])
        controls_10 = {
            control_id: metric_payload(payload) for (control_id, cost), payload in control_payloads.items() if cost == 10.0
        }
        best_10_id, best_10 = best_control_by_sharpe(controls_10)
        if (
            float(candidate_10["total_return"]) <= 0.0
            or (
                float(candidate_10["sharpe_ratio"]) - float(best_10["sharpe_ratio"]) < 0.02
                and float(candidate_10["maximum_drawdown"]) - float(best_10["maximum_drawdown"]) < 0.01
            )
        ):
            return "closed_exploration", f"effect_consumed_or_not_material_at_10bps_vs_{best_10_id}", "cost_drag"
        return "exploratory_followup_candidate_standalone", "standalone_candidate_passed_materiality_aware_exploration_gate", ""

    return "pending_diversifier_portfolio_gate", "requires_portfolio_contribution_gate", ""


def simulate_two_component_portfolio(
    reference: pd.Series,
    sleeve: pd.Series,
    portfolio_id: str,
    cost_bps: float,
) -> dict[str, Any]:
    returns = pd.concat([reference.rename("reference"), sleeve.rename("sleeve")], axis=1, join="inner").dropna()
    target = np.array([0.8, 0.2], dtype=float)
    weights = np.array([0.0, 0.0], dtype=float)
    trade_positions = {0}
    for pos in range(1, len(returns.index)):
        if returns.index[pos - 1].to_period("M") != returns.index[pos].to_period("M"):
            trade_positions.add(pos)
    values = returns[["reference", "sleeve"]].to_numpy(dtype=float)
    net_returns = np.zeros(len(returns), dtype=float)
    turnover_values = np.zeros(len(returns), dtype=float)
    cost_values = np.zeros(len(returns), dtype=float)
    max_exposure_values = np.zeros(len(returns), dtype=float)
    max_weight_sum_values = np.zeros(len(returns), dtype=float)
    equity_values = np.ones(len(returns), dtype=float)
    event_rows: list[dict[str, Any]] = []
    equity = 1.0
    for pos, date in enumerate(returns.index):
        daily_component_return = values[pos]
        gross_return = float(np.dot(weights, daily_component_return))
        pretrade_values = weights * (1.0 + daily_component_return)
        denominator = float(pretrade_values.sum())
        pretrade = pretrade_values / denominator if denominator > 0.0 else weights.copy()
        post_trade = pretrade.copy()
        event_type = ""
        signal_date = ""
        turnover = 0.0
        if pos in trade_positions:
            post_trade = target.copy()
            turnover = 0.5 * float(np.abs(post_trade - pretrade).sum())
            event_type = "initial_establishment" if pos == 0 else "monthly_rebalance_next_session_close"
            signal_date = "" if pos == 0 else pd.Timestamp(returns.index[pos - 1]).date().isoformat()
        cost_fraction = turnover * (cost_bps / 10000.0)
        net_return = (1.0 + gross_return) * (1.0 - cost_fraction) - 1.0
        cost_drag = (1.0 + gross_return) * cost_fraction
        equity *= 1.0 + net_return
        max_exposure = float(np.clip(post_trade, 0.0, None).sum())
        max_weight_sum = float(post_trade.sum())
        net_returns[pos] = net_return
        turnover_values[pos] = turnover
        cost_values[pos] = cost_drag
        equity_values[pos] = equity
        max_exposure_values[pos] = max_exposure
        max_weight_sum_values[pos] = max_weight_sum
        if event_type:
            row = {
                "date": pd.Timestamp(date).date().isoformat(),
                "portfolio_id": portfolio_id,
                "cost_assumption_bps": cost_bps,
                "event_type": event_type,
                "signal_date": signal_date,
                "gross_return_before_cost": gross_return,
                "net_return": net_return,
                "equity": equity,
                "pretrade_reference_weight": float(pretrade[0]),
                "pretrade_sleeve_weight": float(pretrade[1]),
                "post_trade_reference_weight": float(post_trade[0]),
                "post_trade_sleeve_weight": float(post_trade[1]),
                "one_way_turnover": turnover,
                "transaction_cost_drag": cost_drag,
                "max_daily_exposure": max_exposure,
                "max_daily_weight_sum": max_weight_sum,
            }
            event_rows.append({**row, "event_date": row["date"]})
        weights = post_trade
    daily_df = pd.DataFrame(
        {
            "date": returns.index,
            "net_return": net_returns,
            "equity": equity_values,
            "one_way_turnover": turnover_values,
            "transaction_cost_drag": cost_values,
            "max_daily_exposure": max_exposure_values,
            "max_daily_weight_sum": max_weight_sum_values,
        }
    )
    return {
        "returns": pd.Series(net_returns, index=returns.index, name=portfolio_id),
        "turnover": pd.Series(turnover_values, index=returns.index, name="turnover"),
        "cost": pd.Series(cost_values, index=returns.index, name="transaction_cost_drag"),
        "daily_rows": daily_df.to_dict("records"),
        "event_rows": event_rows,
        "daily_df": daily_df.assign(date=lambda frame: pd.to_datetime(frame["date"], errors="coerce")).set_index("date", drop=False),
    }


def reference_payload(reference: pd.Series, cost_bps: float) -> dict[str, Any]:
    rows = []
    equity = 1.0
    for date, value in reference.items():
        equity *= 1.0 + float(value)
        rows.append(
            {
                "date": pd.Timestamp(date).date().isoformat(),
                "portfolio_id": "frozen_reference_100pct",
                "cost_assumption_bps": cost_bps,
                "event_type": "",
                "signal_date": "",
                "gross_return_before_cost": float(value),
                "net_return": float(value),
                "equity": equity,
                "one_way_turnover": 0.0,
                "transaction_cost_drag": 0.0,
                "max_daily_exposure": 1.0,
                "max_daily_weight_sum": 1.0,
                "pretrade_reference_weight": 1.0,
                "pretrade_sleeve_weight": 0.0,
                "post_trade_reference_weight": 1.0,
                "post_trade_sleeve_weight": 0.0,
            }
        )
    return {
        "returns": reference.copy(),
        "turnover": pd.Series(0.0, index=reference.index),
        "cost": pd.Series(0.0, index=reference.index),
        "daily_rows": rows,
        "event_rows": [],
        "daily_df": pd.DataFrame(rows).assign(date=lambda frame: pd.to_datetime(frame["date"], errors="coerce")).set_index("date", drop=False),
    }


def portfolio_contribution_payloads(result: dict[str, Any], reference_returns: pd.Series) -> dict[tuple[str, float], dict[str, Any]]:
    card = result["card"]
    if not result["executable"]:
        return {}
    payloads: dict[tuple[str, float], dict[str, Any]] = {}
    for cost_bps in COST_BPS_GRID:
        candidate = result["candidate_payloads"][cost_bps]["returns"]
        common = candidate.index.intersection(reference_returns.dropna().index).sort_values()
        reference = reference_returns.reindex(common).dropna()
        candidate = candidate.reindex(reference.index).dropna()
        payloads[("frozen_reference_100pct", cost_bps)] = reference_payload(reference, cost_bps)
        payloads[(f"{card.strategy_id}_candidate_20pct", cost_bps)] = simulate_two_component_portfolio(
            reference, candidate, f"{card.strategy_id}_candidate_20pct", cost_bps
        )
        for control_id in card.principal_control_ids:
            control = result["control_payloads"][(control_id, cost_bps)]["returns"].reindex(reference.index).dropna()
            aligned_reference = reference.reindex(control.index).dropna()
            payloads[(f"{control_id}_20pct_control", cost_bps)] = simulate_two_component_portfolio(
                aligned_reference, control, f"{control_id}_20pct_control", cost_bps
            )
    return payloads


def finalize_diversifier_outcome(result: dict[str, Any], portfolio_payloads: dict[tuple[str, float], dict[str, Any]]) -> None:
    card = result["card"]
    if not result["executable"] or card.route != "diversifier":
        return
    candidate_5 = metric_payload(result["candidate_payloads"][PRIMARY_COST_BPS])
    if not candidate_5["invariant_pass"]:
        result.update(outcome="blocked_feasibility", decision_reason="candidate_numeric_timing_or_exposure_invariant_failed", primary_failure_reason="methodology_failure")
        return
    if float(candidate_5["total_return"]) <= 0.0:
        result.update(outcome="closed_exploration", decision_reason="candidate_after_cost_full_period_return_not_positive_at_5bps", primary_failure_reason="weak_return")
        return
    control_5 = {
        control_id: metric_payload(payload)
        for (control_id, cost), payload in result["control_payloads"].items()
        if cost == PRIMARY_COST_BPS
    }
    if any(dominates(control, candidate_5) for control in control_5.values()):
        result.update(
            outcome="closed_exploration",
            decision_reason="principal_control_dominated_candidate_on_cagr_sharpe_and_drawdown",
            primary_failure_reason="weak_vs_primary_control",
        )
        return
    ref = metric_payload(portfolio_payloads[("frozen_reference_100pct", PRIMARY_COST_BPS)])
    candidate_portfolio = metric_payload(portfolio_payloads[(f"{card.strategy_id}_candidate_20pct", PRIMARY_COST_BPS)])
    control_portfolios = {
        f"{control_id}_20pct_control": metric_payload(portfolio_payloads[(f"{control_id}_20pct_control", PRIMARY_COST_BPS)])
        for control_id in card.principal_control_ids
    }
    improves_sharpe = float(candidate_portfolio["sharpe_ratio"]) > float(ref["sharpe_ratio"])
    improves_drawdown = float(candidate_portfolio["maximum_drawdown"]) > float(ref["maximum_drawdown"])
    worsens_both = float(candidate_portfolio["sharpe_ratio"]) < float(ref["sharpe_ratio"]) and float(
        candidate_portfolio["maximum_drawdown"]
    ) < float(ref["maximum_drawdown"])
    if not ((improves_sharpe or improves_drawdown) and not worsens_both):
        result.update(
            outcome="closed_exploration",
            decision_reason="candidate_80_20_portfolio_did_not_improve_reference_without_worsening_both",
            primary_failure_reason="weak_vs_primary_control",
        )
        return
    if any(dominates(control, candidate_portfolio) for control in control_portfolios.values()):
        result.update(
            outcome="closed_exploration",
            decision_reason="best_80_20_control_dominated_candidate_80_20_portfolio",
            primary_failure_reason="weak_vs_primary_control",
        )
        return
    best_control_id, best_control = best_control_by_sharpe(control_portfolios)
    sharpe_diff = float(candidate_portfolio["sharpe_ratio"]) - float(best_control["sharpe_ratio"])
    drawdown_diff = float(candidate_portfolio["maximum_drawdown"]) - float(best_control["maximum_drawdown"])
    if sharpe_diff < 0.02 and drawdown_diff < 0.01:
        result.update(
            outcome="closed_exploration",
            decision_reason="80_20_difference_below_materiality_thresholds_vs_best_control",
            primary_failure_reason="benchmark_like_behavior",
        )
        return
    for half_label, start, end in split_halves(portfolio_payloads[(f"{card.strategy_id}_candidate_20pct", PRIMARY_COST_BPS)]["returns"].index):
        period_index = portfolio_payloads[(f"{card.strategy_id}_candidate_20pct", PRIMARY_COST_BPS)]["returns"].index[
            (portfolio_payloads[(f"{card.strategy_id}_candidate_20pct", PRIMARY_COST_BPS)]["returns"].index >= start)
            & (portfolio_payloads[(f"{card.strategy_id}_candidate_20pct", PRIMARY_COST_BPS)]["returns"].index <= end)
        ]
        cand_half = metric_payload(portfolio_payloads[(f"{card.strategy_id}_candidate_20pct", PRIMARY_COST_BPS)], period_index)
        ctrl_half = metric_payload(portfolio_payloads[(best_control_id, PRIMARY_COST_BPS)], period_index)
        if float(cand_half["sharpe_ratio"]) <= float(ctrl_half["sharpe_ratio"]) and float(cand_half["maximum_drawdown"]) <= float(
            ctrl_half["maximum_drawdown"]
        ):
            result.update(
                outcome="closed_exploration",
                decision_reason="candidate_80_20_not_favorable_vs_best_control_in_each_chronological_half",
                primary_failure_reason="period_instability",
            )
            return
    result.update(
        outcome="exploratory_followup_candidate_diversifier",
        decision_reason="diversifier_candidate_passed_materiality_aware_exploration_gate",
        primary_failure_reason="",
    )


def trial_result_rows(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in results:
        card = result["card"]
        if not result["executable"]:
            rows.append(
                {
                    "strategy_id": card.strategy_id,
                    "family_id": card.family_id,
                    "trial_id": "",
                    "entity_type": "strategy_configuration",
                    "stage": "blocked",
                    "route": card.route,
                    "cost_assumption_bps": PRIMARY_COST_BPS,
                    "outcome": result["outcome"],
                    "primary_failure_reason": result["primary_failure_reason"],
                    "decision_reason": result["decision_reason"],
                    "missing_symbols": result["missing_symbols"],
                }
            )
            continue
        for cost_bps, payload in result["candidate_payloads"].items():
            rows.append(
                {
                    "strategy_id": card.strategy_id,
                    "family_id": card.family_id,
                    "trial_id": card.trial_id,
                    "entity_type": "experiment_trial",
                    "stage": stage_for_outcome(result["outcome"], card.route),
                    "route": card.route,
                    "cost_assumption_bps": cost_bps,
                    "outcome": result["outcome"],
                    "primary_failure_reason": result["primary_failure_reason"],
                    "decision_reason": result["decision_reason"],
                    "missing_symbols": "",
                    **metric_payload(payload),
                }
            )
    return rows


def control_result_rows(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in results:
        card = result["card"]
        if not result["executable"]:
            for control_id in card.principal_control_ids:
                rows.append(
                    {
                        "strategy_id": card.strategy_id,
                        "family_id": card.family_id,
                        "trial_id": "",
                        "control_id": control_id,
                        "entity_type": "benchmark_reference",
                        "stage": "benchmark_reference_only",
                        "cost_assumption_bps": PRIMARY_COST_BPS,
                        "outcome": result["outcome"],
                        "data_issue": result["decision_reason"],
                        "missing_symbols": result["missing_symbols"],
                    }
                )
            continue
        for (control_id, cost_bps), payload in result["control_payloads"].items():
            rows.append(
                {
                    "strategy_id": card.strategy_id,
                    "family_id": card.family_id,
                    "trial_id": card.trial_id,
                    "control_id": control_id,
                    "entity_type": "benchmark_reference",
                    "stage": "benchmark_reference_only",
                    "cost_assumption_bps": cost_bps,
                    "outcome": "benchmark_reference_only",
                    "data_issue": "",
                    "missing_symbols": "",
                    **metric_payload(payload),
                }
            )
    return rows


def chronological_half_rows(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in results:
        card = result["card"]
        if not result["executable"]:
            continue
        for cost_bps, payload in result["candidate_payloads"].items():
            rows.extend(period_rows_for_payload(card, "candidate", "", cost_bps, payload))
        for (control_id, cost_bps), payload in result["control_payloads"].items():
            rows.extend(period_rows_for_payload(card, "control", control_id, cost_bps, payload))
    return rows


def portfolio_rows_and_events(results: list[dict[str, Any]], reference_returns: pd.Series) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    event_rows: list[dict[str, Any]] = []
    turnover_rows: list[dict[str, Any]] = []
    for result in results:
        if not result["executable"]:
            continue
        card = result["card"]
        payloads = portfolio_contribution_payloads(result, reference_returns)
        finalize_diversifier_outcome(result, payloads)
        for (portfolio_id, cost_bps), payload in payloads.items():
            for period_label, period_index in [("full_period", payload["returns"].index), *[
                (label, payload["returns"].index[(payload["returns"].index >= start) & (payload["returns"].index <= end)])
                for label, start, end in split_halves(payload["returns"].index)
            ]]:
                rows.append(
                    {
                        "strategy_id": card.strategy_id,
                        "family_id": card.family_id,
                        "trial_id": card.trial_id,
                        "route": card.route,
                        "portfolio_id": portfolio_id,
                        "portfolio_construction": "100pct_frozen_reference"
                        if portfolio_id == "frozen_reference_100pct"
                        else "monthly_rebalanced_80pct_reference_plus_20pct_candidate_or_control",
                        "period_label": period_label,
                        "half_source": "" if period_label == "full_period" else "chronological_half_not_clean_holdout",
                        "cost_assumption_bps": cost_bps,
                        **metric_payload(payload, period_index),
                    }
                )
            for event in payload["event_rows"]:
                event_rows.append(
                    {
                        "strategy_id": card.strategy_id,
                        "family_id": card.family_id,
                        "trial_id": card.trial_id,
                        "portfolio_id": portfolio_id,
                        "cost_assumption_bps": cost_bps,
                        **event,
                    }
                )
            metrics = metric_payload(payload)
            turnover_rows.append(
                {
                    "record_scope": "portfolio_contribution",
                    "strategy_id": card.strategy_id,
                    "portfolio_id": portfolio_id,
                    "cost_assumption_bps": cost_bps,
                    "total_one_way_turnover": metrics["turnover"],
                    "trade_or_rebalance_count": metrics["trade_or_rebalance_count"],
                    "transaction_cost_drag": metrics["transaction_cost_drag"],
                    "initial_establishment_charged": portfolio_id != "frozen_reference_100pct",
                    "rebalance_policy": "monthly_rebalanced_80_20_with_natural_drift"
                    if portfolio_id != "frozen_reference_100pct"
                    else "reference_only_no_task_turnover",
                }
            )
    return rows, event_rows, turnover_rows


def stage_for_outcome(outcome: str, route: str) -> str:
    if outcome == "exploratory_followup_candidate_standalone":
        return "exploratory_followup_standalone"
    if outcome == "exploratory_followup_candidate_diversifier":
        return "exploratory_followup_diversifier"
    if outcome == "closed_exploration":
        return "closed"
    if outcome in {"inconclusive_data_issue", "blocked_feasibility"}:
        return "blocked"
    return "exploration"


def strategy_card_rows(results: list[dict[str, Any]], next_action: str) -> list[dict[str, Any]]:
    rows = []
    for result in results:
        card = result["card"]
        rows.append(
            {
                "strategy_id": card.strategy_id,
                "family_id": card.family_id,
                "display_name": card.display_name,
                "entity_type": "strategy_configuration",
                "strategy_architecture": card.strategy_architecture,
                "source_or_research_lineage": card.source_or_research_lineage,
                "instrument_universe": card.instrument_universe,
                "parameters": card.parameters,
                "benchmark_or_control": card.benchmark_or_control,
                "stage": "exploration",
                "trial_id": card.trial_id,
                "parent_trial_id": "",
                "adaptation_label": "",
                "failure_reason": result["primary_failure_reason"],
                "next_action": next_action,
                "outcome": result["outcome"],
                "evaluation_start": result["evaluation_start"],
                "evaluation_end": result["evaluation_end"],
            }
        )
    return rows


def trial_ledger_rows(results: list[dict[str, Any]], next_action: str) -> list[dict[str, Any]]:
    rows = []
    for result in results:
        if not result["executable"]:
            continue
        card = result["card"]
        rows.append(
            {
                "strategy_id": card.strategy_id,
                "family_id": card.family_id,
                "display_name": card.display_name,
                "entity_type": "experiment_trial",
                "stage": "exploration",
                "trial_id": card.trial_id,
                "parent_trial_id": "",
                "source_library_id": SOURCE_LIBRARY_ID,
                "complete_frozen_rule": card.complete_frozen_rule,
                "instruments": card.instrument_universe,
                "evaluation_start": result["evaluation_start"],
                "evaluation_end": result["evaluation_end"],
                "benchmark_and_controls": card.benchmark_or_control,
                "route": card.route,
                "transaction_cost_assumptions": "5 bps primary; 0 and 10 bps fixed diagnostics",
                "execution_timing": "frozen_per_candidate_rule_no_result_driven_change",
                "changed_fields_from_parent": "canonical_configuration",
                "preregistration_timestamp": FROZEN_TIMESTAMP,
                "adaptation_label": "",
                "outcome": result["outcome"],
                "primary_failure_reason": result["primary_failure_reason"],
                "next_action": next_action,
                "strategy_definition_changed": False,
                "parameters_changed_after_results": False,
                "counted_as_trial": True,
            }
        )
    return rows


def source_library_rows() -> list[dict[str, Any]]:
    return [
        {
            "source_library_id": SOURCE_LIBRARY_ID,
            "strategy_id": card.strategy_id,
            "family_id": card.family_id,
            "source_or_research_lineage": card.source_or_research_lineage,
            "route": card.route,
            "frozen_candidate_from_refresh_v1": True,
            "source_research_performed": False,
            "source_rule_completion_performed": False,
            "complete_frozen_rule": card.complete_frozen_rule,
        }
        for card in CARDS
    ]


def benchmark_reference_rows(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in results:
        card = result["card"]
        rows.append(
            {
                "strategy_id": card.strategy_id,
                "family_id": card.family_id,
                "trial_id": card.trial_id if result["executable"] else "",
                "benchmark_or_control_id": "frozen_current_active_vm_dsr_usci_combo",
                "entity_type": "benchmark_reference",
                "stage": "benchmark_reference_only",
                "reference_role": "portfolio_contribution_reference_only",
                "counted_as_strategy": False,
                "counted_as_trial": False,
            }
        )
        for control_id in card.principal_control_ids:
            rows.append(
                {
                    "strategy_id": card.strategy_id,
                    "family_id": card.family_id,
                    "trial_id": card.trial_id if result["executable"] else "",
                    "benchmark_or_control_id": control_id,
                    "entity_type": "benchmark_reference",
                    "stage": "benchmark_reference_only",
                    "reference_role": "same_purpose_control",
                    "counted_as_strategy": False,
                    "counted_as_trial": False,
                }
            )
    return rows


def process_task_row(next_action: str, outcome: str) -> dict[str, Any]:
    return {
        "task_id": BATCH_ID,
        "entity_type": "process_task",
        "stage": "exploration",
        "outcome": outcome,
        "exact_next_action": next_action,
        "strategy_counted": False,
        "experiment_trial_counted": False,
        "execute_now": False,
    }


def next_action_for_results(results: list[dict[str, Any]]) -> str:
    followups = [r for r in results if r["outcome"].startswith("exploratory_followup_candidate")]
    blocked = [r for r in results if r["outcome"] in {"inconclusive_data_issue", "blocked_feasibility"}]
    if followups:
        return NEXT_ACTION_REVIEW
    if blocked:
        return NEXT_ACTION_PARTIAL_BLOCK
    return NEXT_ACTION_REFRESH


def outcome_summary_rows(results: list[dict[str, Any]], next_action: str) -> list[dict[str, Any]]:
    return [
        {
            "strategy_id": result["card"].strategy_id,
            "family_id": result["card"].family_id,
            "entity_type": "strategy_configuration",
            "stage": stage_for_outcome(result["outcome"], result["card"].route),
            "outcome": result["outcome"],
            "primary_failure_reason": result["primary_failure_reason"],
            "decision_reason": result["decision_reason"],
            "next_action": next_action,
            "counted_in_strategy_cohort": True,
        }
        for result in results
    ]


def failure_reason_rows(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "strategy_id": result["card"].strategy_id,
            "family_id": result["card"].family_id,
            "outcome": result["outcome"],
            "primary_failure_reason": result["primary_failure_reason"],
            "decision_reason": result["decision_reason"],
            "missing_symbols": result["missing_symbols"],
        }
        for result in results
        if result["primary_failure_reason"]
    ]


def next_action_rows(results: list[dict[str, Any]], next_action: str) -> list[dict[str, Any]]:
    rows = [
        {
            "scope": "strategy",
            "strategy_id": result["card"].strategy_id,
            "outcome": result["outcome"],
            "exact_next_action": next_action,
            "execute_now": False,
        }
        for result in results
    ]
    rows.append({"scope": "global", "strategy_id": "", "outcome": "batch_complete", "exact_next_action": next_action, "execute_now": False})
    return rows


def cohort_funnel_counts(
    results: list[dict[str, Any]],
    benchmark_rows: list[dict[str, Any]],
    data_task_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "source_library_record_count": len(CARDS),
        "strategy_configuration_count": len(results),
        "executable_experiment_trial_count": sum(1 for result in results if result["executable"]),
        "data_blocked_strategy_count": sum(1 for result in results if result["outcome"] == "inconclusive_data_issue"),
        "standalone_followup_candidate_count": sum(1 for result in results if result["outcome"] == "exploratory_followup_candidate_standalone"),
        "diversifier_followup_candidate_count": sum(1 for result in results if result["outcome"] == "exploratory_followup_candidate_diversifier"),
        "closed_strategy_count": sum(1 for result in results if result["outcome"] == "closed_exploration"),
        "blocked_feasibility_count": sum(1 for result in results if result["outcome"] == "blocked_feasibility"),
        "benchmark_reference_count": len(benchmark_rows),
        "data_capability_task_count": len(data_task_rows),
        "process_task_count": 1,
        "candidate_ids": [card.strategy_id for card in CARDS],
    }


def build_report(results: list[dict[str, Any]], funnel: dict[str, Any], next_action: str) -> str:
    lines = [
        "# Fast Source Library Remaining Candidates Batch V4",
        "",
        "This bounded exploratory batch considered exactly four frozen remaining candidates from "
        "`strategy_source_library_refresh_v1`. It did not perform source research, source-rule completion, "
        "strategy discovery, parameter optimization, validation, robustness, promotion review, paper/demo activation, "
        "broker/account/order work or real-money action.",
        "",
        "ANGL, NVI, inverse-volatility as a candidate, opportunistic rebalancing, and newly discovered strategies were excluded. "
        "Inverse volatility appears only as the frozen benchmark reference for HRP.",
        "",
        "## Funnel",
        "",
        f"- Source-library records: `{funnel['source_library_record_count']}`",
        f"- Strategy configurations considered: `{funnel['strategy_configuration_count']}`",
        f"- Executable experiment trials: `{funnel['executable_experiment_trial_count']}`",
        f"- Data-blocked strategies: `{funnel['data_blocked_strategy_count']}`",
        f"- Standalone follow-up candidates: `{funnel['standalone_followup_candidate_count']}`",
        f"- Diversifier follow-up candidates: `{funnel['diversifier_followup_candidate_count']}`",
        f"- Closed strategies: `{funnel['closed_strategy_count']}`",
        f"- Benchmark references: `{funnel['benchmark_reference_count']}`",
        f"- Data-capability tasks: `{funnel['data_capability_task_count']}`",
        f"- Process tasks: `{funnel['process_task_count']}`",
        "",
        "## Outcomes",
        "",
    ]
    for result in results:
        lines.append(f"- `{result['card'].strategy_id}`: `{result['outcome']}` - {result['decision_reason']}")
    lines.extend(["", f"Exact next action: `{next_action}`."])
    return "\n".join(lines)


def deterministic_core_hash() -> str:
    names = [
        "batch_manifest.yaml",
        "source_library_records.csv",
        "strategy_cards.csv",
        "trial_ledger.csv",
        "process_task_log.csv",
        "data_capability_task_log.csv",
        "benchmark_reference_log.csv",
        "data_preflight_reconciliation.csv",
        "all_trial_results.csv",
        "control_results.csv",
        "chronological_half_results.csv",
        "portfolio_contribution_results.csv",
        "portfolio_rebalance_events.csv",
        "turnover_cost_reconciliation.csv",
        "outcome_summary.csv",
        "failure_reasons.csv",
        "next_actions.csv",
        "cohort_funnel_counts.json",
        "batch_report.md",
    ]
    digest = hashlib.sha256()
    for name in names:
        path = OUTPUT_DIR / name
        digest.update(name.encode("utf-8"))
        digest.update(path.read_bytes() if path.exists() else b"missing")
    return "sha256:" + digest.hexdigest()


def write_artifacts(
    results: list[dict[str, Any]],
    data_task_rows: list[dict[str, Any]],
    data_preflight_rows: list[dict[str, Any]],
    portfolio_rows: list[dict[str, Any]],
    portfolio_events: list[dict[str, Any]],
    turnover_rows: list[dict[str, Any]],
    before_protected: dict[str, str],
    before_evidence: dict[str, str],
) -> dict[str, Any]:
    next_action = next_action_for_results(results)
    benchmark_rows = benchmark_reference_rows(results)
    funnel = cohort_funnel_counts(results, benchmark_rows, data_task_rows)
    process_rows = [process_task_row(next_action, "fast_source_library_remaining_candidates_batch_v4_complete")]

    write_yaml(
        OUTPUT_DIR / "batch_manifest.yaml",
        {
            "batch_id": BATCH_ID,
            "source_library_id": SOURCE_LIBRARY_ID,
            "mode": "fast-progress",
            "lane": "fast implementation",
            "stage": "exploration",
            "exact_candidate_ids": [card.strategy_id for card in CARDS],
            "exact_candidate_count": len(CARDS),
            "excluded_ids": [
                "ice_vaneck_us_fallen_angel_angl_v1",
                "fosback_nvi_255ema_spy_bil_v1",
                "clare_inverse_volatility_five_asset_risk_parity_v1_as_candidate",
                "daryanani_opportunistic_rebalance_20band_10day_v1",
            ],
            "required_symbols": list(REQUIRED_SYMBOLS),
            "cost_diagnostics_bps": list(COST_BPS_GRID),
            "primary_cost_bps": PRIMARY_COST_BPS,
            "exact_next_action": next_action,
            **FORBIDDEN_FLAGS,
        },
    )
    write_csv(OUTPUT_DIR / "source_library_records.csv", source_library_rows(), SOURCE_LIBRARY_FIELDS)
    write_csv(OUTPUT_DIR / "strategy_cards.csv", strategy_card_rows(results, next_action), STRATEGY_CARD_FIELDS)
    write_csv(OUTPUT_DIR / "trial_ledger.csv", trial_ledger_rows(results, next_action), TRIAL_LEDGER_FIELDS)
    write_csv(OUTPUT_DIR / "process_task_log.csv", process_rows, PROCESS_FIELDS)
    write_csv(OUTPUT_DIR / "data_capability_task_log.csv", data_task_rows, DATA_TASK_FIELDS)
    write_csv(OUTPUT_DIR / "benchmark_reference_log.csv", benchmark_rows, BENCHMARK_FIELDS)
    write_csv(OUTPUT_DIR / "data_preflight_reconciliation.csv", data_preflight_rows, PREFLIGHT_FIELDS)
    write_csv(OUTPUT_DIR / "all_trial_results.csv", trial_result_rows(results), TRIAL_RESULT_FIELDS)
    write_csv(OUTPUT_DIR / "control_results.csv", control_result_rows(results), CONTROL_RESULT_FIELDS)
    write_csv(OUTPUT_DIR / "chronological_half_results.csv", chronological_half_rows(results), HALF_FIELDS)
    write_csv(OUTPUT_DIR / "portfolio_contribution_results.csv", portfolio_rows, PORTFOLIO_FIELDS)
    write_csv(OUTPUT_DIR / "portfolio_rebalance_events.csv", portfolio_events, PORTFOLIO_EVENT_FIELDS)
    write_csv(OUTPUT_DIR / "turnover_cost_reconciliation.csv", turnover_rows, TURNOVER_FIELDS)
    write_csv(OUTPUT_DIR / "outcome_summary.csv", outcome_summary_rows(results, next_action), OUTCOME_FIELDS)
    write_csv(OUTPUT_DIR / "failure_reasons.csv", failure_reason_rows(results), FAILURE_FIELDS)
    write_csv(OUTPUT_DIR / "next_actions.csv", next_action_rows(results, next_action), NEXT_ACTION_FIELDS)
    write_json(OUTPUT_DIR / "cohort_funnel_counts.json", {**funnel, "exact_next_action": next_action})
    write_text(OUTPUT_DIR / "batch_report.md", build_report(results, funnel, next_action))

    after_protected = protected_hashes()
    after_evidence = input_evidence_hashes()
    consistency = {
        "batch_id": BATCH_ID,
        "exactly_four_frozen_candidates_considered": [card.strategy_id for card in CARDS]
        == [
            "lopez_de_prado_hrp_five_asset_v1",
            "ishares_msci_usa_min_vol_usmv_v1",
            "sp100_option_expiration_week_oef_bil_v1",
            "spy_close_to_open_overnight_cash_bounded_screen_v1",
        ],
        "no_excluded_candidates_in_strategy_cards": not any(
            row["strategy_id"]
            in {
                "ice_vaneck_us_fallen_angel_angl_v1",
                "fosback_nvi_255ema_spy_bil_v1",
                "clare_inverse_volatility_five_asset_risk_parity_v1",
                "daryanani_opportunistic_rebalance_20band_10day_v1",
            }
            for row in strategy_card_rows(results, next_action)
        ),
        "inverse_volatility_only_benchmark_reference": any(
            row["benchmark_or_control_id"] == "clare_inverse_volatility_five_asset_risk_parity_v1" for row in benchmark_rows
        )
        and not any(row["strategy_id"] == "clare_inverse_volatility_five_asset_risk_parity_v1" for row in strategy_card_rows(results, next_action)),
        "one_canonical_trial_per_executable_candidate": len(trial_ledger_rows(results, next_action))
        == sum(1 for result in results if result["executable"]),
        "all_strategy_metadata_non_unknown": all("unknown" not in json.dumps(row).lower() for row in strategy_card_rows(results, next_action)),
        "all_outcomes_allowed": all(result["outcome"] in ALLOWED_OUTCOMES for result in results),
        "all_failure_reasons_allowed": all(result["primary_failure_reason"] in ALLOWED_FAILURE_REASONS for result in results),
        "data_preflight_all_required_symbols_recorded": {row["symbol"] for row in data_preflight_rows} == set(REQUIRED_SYMBOLS),
        "benchmark_references_separate": all(row["entity_type"] == "benchmark_reference" and row["stage"] == "benchmark_reference_only" for row in benchmark_rows),
        "process_task_separate": process_rows[0]["strategy_counted"] is False and process_rows[0]["experiment_trial_counted"] is False,
        "cohort_counts_reconcile": (
            funnel["standalone_followup_candidate_count"]
            + funnel["diversifier_followup_candidate_count"]
            + funnel["closed_strategy_count"]
            + funnel["data_blocked_strategy_count"]
            + funnel["blocked_feasibility_count"]
            == funnel["strategy_configuration_count"]
        ),
        "portfolio_contribution_uses_monthly_rebalanced_80_20_not_fixed_return_blend": all(
            row["portfolio_construction"] in {"100pct_frozen_reference", "monthly_rebalanced_80pct_reference_plus_20pct_candidate_or_control"}
            for row in portfolio_rows
        ),
        "portfolio_exposure_lte_one": all(float(row.get("max_daily_exposure") or 0.0) <= 1.0 + WEIGHT_TOLERANCE for row in portfolio_rows),
        "portfolio_weight_sum_lte_one": all(float(row.get("max_daily_weight_sum") or 0.0) <= 1.0 + WEIGHT_TOLERANCE for row in portfolio_rows),
        "protected_state_hashes_unchanged": before_protected == after_protected,
        "input_evidence_hashes_unchanged": before_evidence == after_evidence,
        "exact_next_action": next_action,
        **FORBIDDEN_FLAGS,
    }
    consistency["consistency_passed"] = all(
        value is True for key, value in consistency.items() if key not in {"batch_id", "exact_next_action", *FORBIDDEN_FLAGS.keys()}
    ) and all(value is False for value in FORBIDDEN_FLAGS.values())
    write_json(OUTPUT_DIR / "consistency_check.json", {**consistency, "deterministic_core_hash": deterministic_core_hash()})
    return consistency


SOURCE_LIBRARY_FIELDS = [
    "source_library_id",
    "strategy_id",
    "family_id",
    "source_or_research_lineage",
    "route",
    "frozen_candidate_from_refresh_v1",
    "source_research_performed",
    "source_rule_completion_performed",
    "complete_frozen_rule",
]
STRATEGY_CARD_FIELDS = [
    "strategy_id",
    "family_id",
    "display_name",
    "entity_type",
    "strategy_architecture",
    "source_or_research_lineage",
    "instrument_universe",
    "parameters",
    "benchmark_or_control",
    "stage",
    "trial_id",
    "parent_trial_id",
    "adaptation_label",
    "failure_reason",
    "next_action",
    "outcome",
    "evaluation_start",
    "evaluation_end",
]
TRIAL_LEDGER_FIELDS = [
    "strategy_id",
    "family_id",
    "display_name",
    "entity_type",
    "stage",
    "trial_id",
    "parent_trial_id",
    "source_library_id",
    "complete_frozen_rule",
    "instruments",
    "evaluation_start",
    "evaluation_end",
    "benchmark_and_controls",
    "route",
    "transaction_cost_assumptions",
    "execution_timing",
    "changed_fields_from_parent",
    "preregistration_timestamp",
    "adaptation_label",
    "outcome",
    "primary_failure_reason",
    "next_action",
    "strategy_definition_changed",
    "parameters_changed_after_results",
    "counted_as_trial",
]
PROCESS_FIELDS = ["task_id", "entity_type", "stage", "outcome", "exact_next_action", "strategy_counted", "experiment_trial_counted", "execute_now"]
DATA_TASK_FIELDS = [
    "task_id",
    "entity_type",
    "stage",
    "adaptation_label",
    "symbol",
    "provider",
    "attempted",
    "downloaded_this_run",
    "cache_reused_from_prior_task_attempt",
    "status",
    "cache_path",
    "cache_file_hash",
    "error",
    "counted_as_strategy",
    "counted_as_trial",
]
BENCHMARK_FIELDS = [
    "strategy_id",
    "family_id",
    "trial_id",
    "benchmark_or_control_id",
    "entity_type",
    "stage",
    "reference_role",
    "counted_as_strategy",
    "counted_as_trial",
]
PREFLIGHT_FIELDS = [
    "record_type",
    "symbol",
    "required_for_batch",
    "cache_path",
    "cache_exists",
    "cache_file_hash",
    "canonical_frame_hash",
    "row_count",
    "first_valid_date",
    "last_valid_date",
    "ordered_unique_dates",
    "positive_finite_prices",
    "valid_ohlc_relationships",
    "adjustment_compatibility",
    "sufficient_coverage",
    "preflight_status",
    "failure_reason",
]
METRIC_FIELDS = [
    "evaluation_start",
    "evaluation_end",
    "trading_days",
    "total_return",
    "cagr",
    "annualized_volatility",
    "sharpe_ratio",
    "maximum_drawdown",
    "turnover",
    "trade_or_rebalance_count",
    "transaction_cost_drag",
    "average_gross_exposure",
    "max_daily_exposure",
    "max_daily_weight_sum",
    "numeric_invariant_status",
    "timing_invariant_status",
    "exposure_invariant_status",
    "invariant_pass",
]
TRIAL_RESULT_FIELDS = [
    "strategy_id",
    "family_id",
    "trial_id",
    "entity_type",
    "stage",
    "route",
    "cost_assumption_bps",
    "outcome",
    "primary_failure_reason",
    "decision_reason",
    "missing_symbols",
    *METRIC_FIELDS,
]
CONTROL_RESULT_FIELDS = [
    "strategy_id",
    "family_id",
    "trial_id",
    "control_id",
    "entity_type",
    "stage",
    "cost_assumption_bps",
    "outcome",
    "data_issue",
    "missing_symbols",
    *METRIC_FIELDS,
]
HALF_FIELDS = [
    "strategy_id",
    "family_id",
    "trial_id",
    "row_type",
    "control_id",
    "cost_assumption_bps",
    "half_label",
    "half_source",
    *METRIC_FIELDS,
]
PORTFOLIO_FIELDS = [
    "strategy_id",
    "family_id",
    "trial_id",
    "route",
    "portfolio_id",
    "portfolio_construction",
    "period_label",
    "half_source",
    "cost_assumption_bps",
    *METRIC_FIELDS,
]
PORTFOLIO_EVENT_FIELDS = [
    "strategy_id",
    "family_id",
    "trial_id",
    "portfolio_id",
    "cost_assumption_bps",
    "date",
    "event_date",
    "event_type",
    "signal_date",
    "gross_return_before_cost",
    "net_return",
    "equity",
    "pretrade_reference_weight",
    "pretrade_sleeve_weight",
    "post_trade_reference_weight",
    "post_trade_sleeve_weight",
    "one_way_turnover",
    "transaction_cost_drag",
    "max_daily_exposure",
    "max_daily_weight_sum",
]
TURNOVER_FIELDS = [
    "record_scope",
    "strategy_id",
    "portfolio_id",
    "cost_assumption_bps",
    "total_one_way_turnover",
    "trade_or_rebalance_count",
    "transaction_cost_drag",
    "initial_establishment_charged",
    "rebalance_policy",
]
OUTCOME_FIELDS = [
    "strategy_id",
    "family_id",
    "entity_type",
    "stage",
    "outcome",
    "primary_failure_reason",
    "decision_reason",
    "next_action",
    "counted_in_strategy_cohort",
]
FAILURE_FIELDS = ["strategy_id", "family_id", "outcome", "primary_failure_reason", "decision_reason", "missing_symbols"]
NEXT_ACTION_FIELDS = ["scope", "strategy_id", "outcome", "exact_next_action", "execute_now"]


def run() -> dict[str, Any]:
    before_protected = protected_hashes()
    before_evidence = input_evidence_hashes()
    missing_before = [symbol for symbol in REQUIRED_SYMBOLS if not cache_path(symbol).exists()]
    data_task_rows = attempt_missing_symbol_acquisition(missing_before)
    clean_output_dir()
    data_preflight_rows = [data_preflight_row(symbol) for symbol in REQUIRED_SYMBOLS]
    preflight_by_symbol = {row["symbol"]: row for row in data_preflight_rows}
    reference_returns = prior.active_vm_dsr_usci_reference_returns()
    results = [run_candidate(card, preflight_by_symbol) for card in CARDS]
    portfolio_rows, portfolio_events, turnover_rows = portfolio_rows_and_events(results, reference_returns)
    consistency = write_artifacts(
        results,
        data_task_rows,
        data_preflight_rows,
        portfolio_rows,
        portfolio_events,
        turnover_rows,
        before_protected,
        before_evidence,
    )
    return {
        "batch_id": BATCH_ID,
        "output_dir": rel(OUTPUT_DIR),
        "strategy_configurations_considered": len(results),
        "executable_experiment_trials": sum(1 for result in results if result["executable"]),
        "outcomes": {result["card"].strategy_id: result["outcome"] for result in results},
        "exact_next_action": consistency["exact_next_action"],
        "consistency_passed": consistency["consistency_passed"],
        "protected_state_hashes_unchanged": consistency["protected_state_hashes_unchanged"],
        "input_evidence_hashes_unchanged": consistency["input_evidence_hashes_unchanged"],
    }
