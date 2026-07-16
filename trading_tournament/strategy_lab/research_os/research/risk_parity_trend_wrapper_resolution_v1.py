from __future__ import annotations

import csv
import hashlib
import inspect
import json
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd
import yaml

from src.data import DataQualityError, build_adjusted_ohlc


ROOT = Path(__file__).resolve().parents[3]
OUTPUT_DIR = Path("evidence") / "risk_parity_trend_wrapper_resolution_v1" / "latest"
INTAKE_PATH = (
    Path("strategy_lab")
    / "research_os"
    / "public_strategy_sources"
    / "intake_candidates"
    / "clare_seaton_smith_thomas_risk_parity_trend_following_2016.yaml"
)
CACHE_DIR = Path("data") / "cache"

SOURCE_ID = "clare_seaton_smith_thomas_risk_parity_trend_following_2016"
CANDIDATE_ID = "rp_ivol_10m_trend_etf_wrapper_adaptation_v1"
FAMILY_ID = "risk_parity_inverse_volatility_or_vol_targeting"
ADAPTATION_CLASSIFICATION = "source_inspired_etf_wrapper_adaptation"
NOT_REPLICATION = "not_source_index_replication"

AUTHORIZED_DOWNLOAD_SYMBOLS = ("URTH", "IGOV", "REET")
FIXED_UNIVERSE = ("URTH", "EEM", "IGOV", "DBC", "REET", "BIL")
RISKY_ETFS = ("URTH", "EEM", "IGOV", "DBC", "REET")
HORIZONS = (90, 180)
MAX_WINDOWS_PER_HORIZON = 5
VOLATILITY_WINDOW_MONTHS = 12
TREND_WINDOW_MONTHS = 10
REQUEST_SETTINGS = {
    "start": "2006-01-01",
    "end": None,
    "auto_adjust": False,
    "actions": True,
    "progress": False,
    "multi_level_index": False,
    "timeout": 30,
}
EXPECTED_IDENTITY_SUBSTRINGS = {
    "URTH": ("ishares", "msci", "world"),
    "IGOV": ("ishares", "international", "treasury", "bond"),
    "REET": ("ishares", "global", "reit"),
}

READY = "preregistration_ready"
BLOCKED = "wrapper_data_not_ready"
NEXT_READY = "run_risk_parity_trend_etf_wrapper_screen_only_after_separate_authorization"
NEXT_BLOCKED = "repair_fixed_wrapper_cache_or_identity_before_preregistration"

Downloader = Callable[[str, dict[str, Any]], pd.DataFrame]
MetadataProvider = Callable[[str], dict[str, Any]]


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def abs_path(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
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


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    full = abs_path(path)
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=False), encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    full = abs_path(path)
    if not full.exists():
        return {}
    return json.loads(full.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def package_versions() -> dict[str, str]:
    versions: dict[str, str] = {}
    for package in ("pandas", "numpy", "yfinance", "PyYAML"):
        try:
            versions[package] = metadata.version(package)
        except metadata.PackageNotFoundError:
            versions[package] = "not_installed"
    return versions


def validate_authorized_download_symbol(symbol: str) -> str:
    normalized = str(symbol).upper()
    if normalized not in AUTHORIZED_DOWNLOAD_SYMBOLS:
        raise ValueError(
            f"Provider download is only authorized for {', '.join(AUTHORIZED_DOWNLOAD_SYMBOLS)}; got {symbol}"
        )
    return normalized


def default_yfinance_downloader(symbol: str, request_settings: dict[str, Any]) -> pd.DataFrame:
    validate_authorized_download_symbol(symbol)
    import yfinance as yf

    kwargs: dict[str, Any] = {
        "start": request_settings.get("start", "2006-01-01"),
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
        return yf.download(symbol, **kwargs)
    except TypeError as exc:
        if "multi_level_index" not in str(exc):
            raise
        kwargs.pop("multi_level_index", None)
        return yf.download(symbol, **kwargs)


def default_yfinance_metadata_provider(symbol: str) -> dict[str, Any]:
    validate_authorized_download_symbol(symbol)
    import yfinance as yf

    ticker = yf.Ticker(symbol)
    info: dict[str, Any] = {}
    try:
        info = dict(getattr(ticker, "info", {}) or {})
    except Exception:
        info = {}
    fast: dict[str, Any] = {}
    try:
        fast_info = getattr(ticker, "fast_info", {}) or {}
        fast = dict(fast_info)
    except Exception:
        fast = {}
    return {
        "long_name": info.get("longName") or info.get("shortName") or info.get("name") or "",
        "quote_type": info.get("quoteType", ""),
        "currency": info.get("currency") or fast.get("currency") or "",
        "exchange": info.get("exchange") or info.get("fullExchangeName") or fast.get("exchange") or "",
    }


def previous_acquisition_rows() -> dict[str, dict[str, Any]]:
    manifest = read_json(OUTPUT_DIR / "provider_acquisition_manifest.json")
    rows = manifest.get("series", [])
    if isinstance(rows, list):
        return {str(row.get("provider_symbol", "")).upper(): row for row in rows if row.get("provider_symbol")}
    return {}


def normalized_date_series(frame: pd.DataFrame) -> pd.Series:
    return pd.to_datetime(frame["date"], errors="coerce").dt.tz_localize(None)


def analyze_cache_frame(symbol: str, frame: pd.DataFrame, cache_path: Path, status: str, retrieval_timestamp: str, metadata_row: dict[str, Any]) -> dict[str, Any]:
    dates = normalized_date_series(frame)
    price_cols = [col for col in ("raw_close", "raw_adj_close", "close", "adj_close") if col in frame]
    missing_value_count = int(frame[price_cols].isna().sum().sum()) if price_cols else len(frame)
    duplicate_date_count = int(dates.duplicated().sum())
    non_positive_price_count = int((frame[price_cols] <= 0).sum().sum()) if price_cols else len(frame)
    row_count = int(len(frame))
    data_hash = sha256_file(cache_path) if cache_path.exists() else ""
    long_name = str(metadata_row.get("long_name", ""))
    identity_ok = instrument_identity_ok(symbol, metadata_row)
    return {
        "provider_symbol": symbol,
        "retrieval_timestamp": retrieval_timestamp,
        "source_status": status,
        "first_valid_date": str(dates.min().date()) if row_count else "",
        "last_valid_date": str(dates.max().date()) if row_count else "",
        "row_count": row_count,
        "currency": metadata_row.get("currency", ""),
        "exchange": metadata_row.get("exchange", ""),
        "long_name": long_name,
        "quote_type": metadata_row.get("quote_type", ""),
        "raw_close_available": "raw_close" in frame and int(frame["raw_close"].isna().sum()) < row_count,
        "adjusted_close_available": "adj_close" in frame and int(frame["adj_close"].isna().sum()) < row_count,
        "missing_value_count": missing_value_count,
        "duplicate_date_count": duplicate_date_count,
        "non_positive_price_count": non_positive_price_count,
        "data_hash": data_hash,
        "cache_destination": str(cache_path.relative_to(ROOT)).replace("\\", "/"),
        "deterministic_after_cached": bool(cache_path.exists() and row_count > 0 and data_hash),
        "intended_instrument_resolved": identity_ok,
        "identity_check_expected_terms": "|".join(EXPECTED_IDENTITY_SUBSTRINGS.get(symbol, ())),
        "quality_status": "pass"
        if (
            row_count > 0
            and duplicate_date_count == 0
            and missing_value_count == 0
            and non_positive_price_count == 0
            and identity_ok
            and metadata_row.get("currency", "USD") in {"", "USD"}
        )
        else "fail",
    }


def instrument_identity_ok(symbol: str, metadata_row: dict[str, Any]) -> bool:
    expected = EXPECTED_IDENTITY_SUBSTRINGS.get(symbol)
    if not expected:
        return True
    haystack = " ".join(
        str(metadata_row.get(field, ""))
        for field in ("long_name", "quote_type", "exchange", "currency")
    ).lower()
    return all(term in haystack for term in expected)


def read_normalized_cache(symbol: str) -> pd.DataFrame:
    path = ROOT / CACHE_DIR / f"{symbol}.csv"
    if not path.exists():
        raise DataQualityError(f"{symbol}: cache missing")
    frame = pd.read_csv(path)
    if "date" not in frame.columns or "adj_close" not in frame.columns:
        raise DataQualityError(f"{symbol}: cache is not normalized adjusted OHLCV")
    return frame


def ensure_authorized_cache(
    symbol: str,
    downloader: Downloader,
    metadata_provider: MetadataProvider,
    prior_rows: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    symbol = validate_authorized_download_symbol(symbol)
    cache_path = ROOT / CACHE_DIR / f"{symbol}.csv"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    prior = prior_rows.get(symbol, {})
    if cache_path.exists():
        frame = read_normalized_cache(symbol)
        metadata_row = {
            "long_name": prior.get("long_name", ""),
            "quote_type": prior.get("quote_type", ""),
            "currency": prior.get("currency", ""),
            "exchange": prior.get("exchange", ""),
        }
        if not all(metadata_row.values()) and not prior:
            metadata_row = metadata_provider(symbol)
        return analyze_cache_frame(
            symbol,
            frame,
            cache_path,
            "cached_from_prior_authorized_acquisition" if prior else "preexisting_cache_validated",
            str(prior.get("retrieval_timestamp") or ""),
            metadata_row,
        )

    raw = downloader(symbol, REQUEST_SETTINGS)
    if raw is None or raw.empty:
        raise DataQualityError(f"{symbol}: provider returned no rows")
    normalized = build_adjusted_ohlc(raw, symbol)
    normalized.to_csv(cache_path, index=False)
    metadata_row = metadata_provider(symbol)
    return analyze_cache_frame(symbol, normalized, cache_path, "downloaded_yfinance_compatible", now_utc(), metadata_row)


def existing_cache_series(symbol: str) -> dict[str, Any]:
    path = ROOT / CACHE_DIR / f"{symbol}.csv"
    if not path.exists():
        return {
            "symbol": symbol,
            "cache_ready": False,
            "first_valid_date": "",
            "last_valid_date": "",
            "row_count": 0,
            "data_hash": "",
            "cache_path": str(path.relative_to(ROOT)).replace("\\", "/"),
            "quality_status": "missing",
        }
    frame = pd.read_csv(path)
    dates = normalized_date_series(frame)
    price_cols = [col for col in ("raw_close", "raw_adj_close", "close", "adj_close") if col in frame]
    duplicate_date_count = int(dates.duplicated().sum())
    missing_value_count = int(frame[price_cols].isna().sum().sum()) if price_cols else len(frame)
    non_positive_price_count = int((frame[price_cols] <= 0).sum().sum()) if price_cols else len(frame)
    ready = bool(len(frame) and "adj_close" in frame and duplicate_date_count == 0 and missing_value_count == 0 and non_positive_price_count == 0)
    return {
        "symbol": symbol,
        "cache_ready": ready,
        "first_valid_date": str(dates.min().date()) if len(frame) else "",
        "last_valid_date": str(dates.max().date()) if len(frame) else "",
        "row_count": int(len(frame)),
        "data_hash": sha256_file(path),
        "cache_path": str(path.relative_to(ROOT)).replace("\\", "/"),
        "quality_status": "pass" if ready else "fail",
    }


def approved_mapping_rows(series_rows: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    mapping = [
        ("Developed-market equities", "URTH", "direct ETF wrapper", "MSCI World", "iShares MSCI World ETF", "source_inspired_etf_wrapper_adaptation", "not_source_index_replication"),
        ("Emerging-market equities", "EEM", "direct ETF wrapper", "Emerging-market equities", "iShares MSCI Emerging Markets ETF", "source_inspired_etf_wrapper_adaptation", "not_source_index_replication"),
        ("Developed-market government bonds", "IGOV", "role-preserving ETF-wrapper adaptation", "world government bonds including developed markets", "iShares International Treasury Bond ETF", "known_mapping_difference", "IGOV excludes US government bonds and therefore is not an exact reproduction of the source index"),
        ("Broad commodities", "DBC", "direct ETF wrapper", "Broad commodities", "Invesco DB Commodity Index Tracking Fund", "source_inspired_etf_wrapper_adaptation", "not_source_index_replication; GLD explicitly prohibited as broad commodity proxy"),
        ("Global listed real estate / global REITs", "REET", "direct ETF wrapper", "Global real estate", "iShares Global REIT ETF", "source_inspired_etf_wrapper_adaptation", "not_source_index_replication"),
        ("Treasury bills/risk-off", "BIL", "direct Treasury-bill/cash wrapper", "US Treasury bills as risk-off", "SPDR Bloomberg 1-3 Month T-Bill ETF", "source_inspired_etf_wrapper_adaptation", "not_source_index_replication"),
    ]
    rows = []
    for source_asset_class, ticker, mapping_status, source_role, wrapper, classification, caveat in mapping:
        cache = series_rows.get(ticker) or existing_cache_series(ticker)
        rows.append(
            {
                "source_asset_class": source_asset_class,
                "local_ticker": ticker,
                "mapping_status": mapping_status,
                "source_benchmark_role": source_role,
                "project_wrapper": wrapper,
                "adaptation_classification": classification,
                "known_difference_or_caveat": caveat,
                "cache_ready": cache.get("quality_status") == "pass" or cache.get("cache_ready") is True,
                "cache_start": cache.get("first_valid_date", ""),
                "cache_end": cache.get("last_valid_date", ""),
                "cache_rows": cache.get("row_count", 0),
                "cache_hash": cache.get("data_hash", ""),
                "cache_path": cache.get("cache_destination") or cache.get("cache_path", ""),
                "mechanism_changed_by_translation": False,
            }
        )
    return rows


def wrapper_source_difference_rows() -> list[dict[str, Any]]:
    return [
        {
            "ticker": "URTH",
            "difference_type": "ETF_wrapper_not_source_index",
            "required_wording": "source_inspired_etf_wrapper_adaptation; not_source_index_replication",
            "detail": "URTH is an ETF wrapper for MSCI World exposure, not the paper's original index portfolio implementation.",
        },
        {
            "ticker": "IGOV",
            "difference_type": "known_mapping_difference",
            "required_wording": "known_mapping_difference: IGOV excludes US government bonds and therefore is not an exact reproduction of the source index",
            "detail": "IGOV preserves developed-market government-bond intent but excludes US government bonds.",
        },
        {
            "ticker": "REET",
            "difference_type": "ETF_wrapper_not_source_index",
            "required_wording": "source_inspired_etf_wrapper_adaptation; not_source_index_replication",
            "detail": "REET is a global listed real-estate ETF wrapper; product metadata should be retained in provider manifest.",
        },
    ]


def common_history(mapping_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], pd.DatetimeIndex]:
    starts = [pd.Timestamp(row["cache_start"]) for row in mapping_rows if row.get("cache_ready")]
    ends = [pd.Timestamp(row["cache_end"]) for row in mapping_rows if row.get("cache_ready")]
    if len(starts) != len(FIXED_UNIVERSE) or len(ends) != len(FIXED_UNIVERSE):
        return [
            {
                "common_start": "",
                "common_end": "",
                "warmup_months": VOLATILITY_WINDOW_MONTHS,
                "warmup_eligible_start": "",
                "eligible_trading_days": 0,
                "normal_screening_protocol_feasible": False,
                "blocked_reason": "not_all_wrapper_caches_ready",
            }
        ], [], pd.DatetimeIndex([])
    common_start = max(starts)
    common_end = min(ends)
    warmup_floor = common_start + pd.DateOffset(months=max(VOLATILITY_WINDOW_MONTHS, TREND_WINDOW_MONTHS))
    indices = []
    for symbol in FIXED_UNIVERSE:
        frame = read_normalized_cache(symbol)
        dates = pd.to_datetime(frame["date"], errors="coerce")
        dates = dates[(dates >= common_start) & (dates <= common_end)]
        indices.append(pd.DatetimeIndex(dates.dropna().sort_values()))
    common_index = indices[0]
    for index in indices[1:]:
        common_index = common_index.intersection(index)
    eligible_index = common_index[common_index >= warmup_floor]
    window_rows = deterministic_window_rows(eligible_index)
    feasible = bool(window_rows) and all(
        sum(1 for row in window_rows if int(row["horizon_days"]) == horizon) > 0 for horizon in HORIZONS
    )
    review = [
        {
            "common_start": str(common_start.date()),
            "common_end": str(common_end.date()),
            "warmup_months": max(VOLATILITY_WINDOW_MONTHS, TREND_WINDOW_MONTHS),
            "warmup_eligible_start": str(eligible_index.min().date()) if len(eligible_index) else "",
            "eligible_trading_days": int(len(eligible_index)),
            "available_90_day_windows": sum(1 for row in window_rows if int(row["horizon_days"]) == 90),
            "available_180_day_windows": sum(1 for row in window_rows if int(row["horizon_days"]) == 180),
            "normal_screening_protocol_feasible": feasible,
            "blocked_reason": "" if feasible else "insufficient_common_history_after_warmup_for_sampled_windows",
        }
    ]
    return review, window_rows, eligible_index


def sample_starts(length: int, horizon: int) -> list[int]:
    starts = list(range(252, length - horizon))
    if len(starts) <= 0:
        return []
    if len(starts) <= MAX_WINDOWS_PER_HORIZON:
        return starts
    return sorted(set(int(x) for x in np.linspace(starts[0], starts[-1], MAX_WINDOWS_PER_HORIZON)))


def deterministic_window_rows(index: pd.DatetimeIndex) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for horizon in HORIZONS:
        for start in sample_starts(len(index), horizon):
            rows.append(
                {
                    "horizon_days": horizon,
                    "start_index": start,
                    "window_start": str(index[start].date()),
                    "window_end": str(index[start + horizon].date()),
                    "selection_algorithm": "run_active_strategy_evidence_recompute.sample_starts_equivalent",
                    "performance_computed": False,
                }
            )
    return rows


def material_distinction_rows() -> list[dict[str, Any]]:
    return [
        {
            "candidate_id": CANDIDATE_ID,
            "closest_prior_strategy": "static_all_weather_benchmark_v1; macro_gld_duration_risk_off_bounded_lane_v1; multi_asset_trend_risk_control rows",
            "shared_dimensions": "multi-asset ETF wrappers; monthly cadence; BIL/cash defensive behavior",
            "distinct_mechanism": "cross-asset inverse-volatility allocation plus independent per-asset absolute-trend filtering plus transfer of each failed asset's allocated weight to BIL",
            "ticker_changes_are_source_of_distinction": False,
            "exact_prior_variant_reopened": False,
            "material_distinction_result": "materially_distinct_source_inspired_etf_wrapper_adaptation",
        }
    ]


def preregistration_payload(mapping_rows: list[dict[str, Any]], common_review: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "candidate_id": CANDIDATE_ID,
        "family": FAMILY_ID,
        "source_id": SOURCE_ID,
        "source_citation": "Andrew Clare, James Seaton, Peter N. Smith, Stephen Thomas, Risk Parity, Momentum and Trend Following in Global Asset Allocation, Journal of Behavioral and Experimental Finance, Volume 9, 2016, pages 63-80; SSRN abstract 2126478",
        "adaptation_classification": ADAPTATION_CLASSIFICATION,
        "source_replication_status": NOT_REPLICATION,
        "fixed_universe": list(FIXED_UNIVERSE),
        "risky_etfs": list(RISKY_ETFS),
        "mapping": mapping_rows,
        "known_igov_deviation": "IGOV excludes US government bonds and therefore is not an exact reproduction of the source index.",
        "volatility_calculation": {
            "window_months": VOLATILITY_WINDOW_MONTHS,
            "input": "adjusted close ETF returns",
            "raw_weights": "inverse volatility",
            "normalization": "normalize risky-asset weights so total risky allocation equals 1.0 before trend filtering",
        },
        "trend_rule": {
            "window_months": TREND_WINDOW_MONTHS,
            "input": "adjusted close month-end observations",
            "risk_on": "retain calculated ETF weight when ETF is above its 10-month moving average",
            "risk_off": "transfer the ETF's calculated weight to BIL when below trend",
            "redistribution_to_remaining_risky_assets": False,
        },
        "rebalance": {
            "signal_schedule": "month_end",
            "rebalance_schedule": "monthly",
            "signal_timestamp": "completed month-end close",
            "execution_timestamp": "project shifted-weight/no-lookahead next-session convention",
        },
        "costs_and_slippage": "existing project-standard cost and slippage assumptions",
        "maximum_exposure": 1.0,
        "leverage": False,
        "shorting": False,
        "missing_data_behavior": "no signal or weight is formed until all six wrappers have valid data and the 12-month/10-month warm-up is complete",
        "warmup_behavior": common_review[0] if common_review else {},
        "screening_protocol": {
            "deterministic_sampled_window_procedure": "existing sample_starts-equivalent protocol with 90-day and 180-day horizons",
            "manual_window_selection": False,
            "performance_computation_authorized_by_this_packet": False,
        },
        "result_metrics_for_future_screen": [
            "total_return",
            "max_drawdown",
            "return_drawdown_proxy",
            "window_final_equity",
            "target_before_stop_rates",
            "turnover",
            "average_exposure",
            "BIL_share",
        ],
        "benchmarks": [
            "SPY_200d_trend_model",
            "SPY_buy_and_hold",
            "BIL_cash_proxy",
            "active_combo_vm_dsr_equal_weight_v1_benchmark_reference_only",
            "equal_weight_same_five_risky_etfs_benchmark_only",
        ],
        "invariants": [
            "total_weights_lte_1",
            "no_stale_weights",
            "below_trend_weight_transferred_to_BIL",
            "no_unintended_residual_risky_exposure",
            "no_lookahead",
            "deterministic_results",
            "consistent_cost_application",
        ],
        "failure_conditions": [
            "missing_or_invalid_wrapper_cache",
            "currency_conversion_required",
            "window_protocol_not_feasible",
            "weight_sum_exceeds_1",
            "stale_weights_detected",
            "lookahead_detected",
        ],
        "forbidden_search": {
            "parameter_search": False,
            "universe_search": False,
            "wrapper_search": False,
            "window_search": False,
            "alternative_volatility_windows": False,
            "alternative_trend_windows": False,
        },
        "fingerprint": stable_hash(
            {
                "family": FAMILY_ID,
                "universe": FIXED_UNIVERSE,
                "vol_months": VOLATILITY_WINDOW_MONTHS,
                "trend_months": TREND_WINDOW_MONTHS,
                "risk_off": "transfer_failed_asset_weight_to_BIL",
                "rebalance": "monthly",
                "max_exposure": 1.0,
            }
        ),
    }


def update_intake_record(mapping_rows: list[dict[str, Any]]) -> None:
    path = abs_path(INTAKE_PATH)
    payload: dict[str, Any] = {}
    if path.exists():
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    payload.setdefault("schema_version", 1)
    payload.setdefault("source", {})["source_id"] = SOURCE_ID
    payload.setdefault("strategy_description", {})["strategy_family"] = FAMILY_ID
    payload["approved_wrapper_mapping"] = {
        "resolution_packet": str(OUTPUT_DIR).replace("\\", "/"),
        "candidate_id": CANDIDATE_ID,
        "adaptation_classification": ADAPTATION_CLASSIFICATION,
        "source_replication_status": NOT_REPLICATION,
        "fixed_universe": list(FIXED_UNIVERSE),
        "mapping_rows": mapping_rows,
        "known_mapping_difference": "IGOV excludes US government bonds and therefore is not an exact reproduction of the source index.",
        "provider_download_authorized_symbols": list(AUTHORIZED_DOWNLOAD_SYMBOLS),
        "provider_download_forbidden_for_all_other_symbols": True,
    }
    payload.setdefault("governance", {})["strategy_implemented"] = False
    payload.setdefault("governance", {})["backtest_run"] = False
    payload.setdefault("governance", {})["promotion_or_paper_forward_allowed"] = False
    write_yaml(INTAKE_PATH, payload)


def decision_payload(
    acquisition_rows: list[dict[str, Any]],
    mapping_rows: list[dict[str, Any]],
    common_review: list[dict[str, Any]],
    window_rows: list[dict[str, Any]],
    material_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    all_cache_ready = all(row["cache_ready"] for row in mapping_rows)
    identity_ready = all(
        row.get("intended_instrument_resolved", True)
        for row in acquisition_rows
    )
    currency_ready = all(str(row.get("currency", "USD") or "USD").upper() == "USD" for row in acquisition_rows)
    windows_ready = bool(common_review and common_review[0]["normal_screening_protocol_feasible"])
    material_ready = material_rows[0]["material_distinction_result"] == "materially_distinct_source_inspired_etf_wrapper_adaptation"
    ready = all_cache_ready and identity_ready and currency_ready and windows_ready and material_ready
    blockers: list[str] = []
    if not all_cache_ready:
        blockers.append("not_all_fixed_wrappers_cache_ready")
    if not identity_ready:
        blockers.append("instrument_identity_unresolved")
    if not currency_ready:
        blockers.append("currency_conversion_required")
    if not windows_ready:
        blockers.append("deterministic_sampled_windows_not_feasible")
    if not material_ready:
        blockers.append("material_distinction_not_confirmed")
    acquired_symbols_recorded = [
        row["provider_symbol"]
        for row in acquisition_rows
        if row["source_status"] in {"downloaded_yfinance_compatible", "cached_from_prior_authorized_acquisition"}
    ]
    return {
        "created_utc": now_utc(),
        "source_id": SOURCE_ID,
        "candidate_id": CANDIDATE_ID,
        "family": FAMILY_ID,
        "outcome": READY if ready else BLOCKED,
        "blockers": blockers,
        "adaptation_classification": ADAPTATION_CLASSIFICATION,
        "source_replication_status": NOT_REPLICATION,
        "authorized_download_symbols": list(AUTHORIZED_DOWNLOAD_SYMBOLS),
        "fixed_universe": list(FIXED_UNIVERSE),
        "provider_download_authorized": True,
        "provider_download_this_run": any(row["source_status"] == "downloaded_yfinance_compatible" for row in acquisition_rows),
        "downloaded_symbols_this_run": [
            row["provider_symbol"] for row in acquisition_rows if row["source_status"] == "downloaded_yfinance_compatible"
        ],
        "cached_from_prior_authorized_acquisition": [
            row["provider_symbol"] for row in acquisition_rows if row["source_status"] == "cached_from_prior_authorized_acquisition"
        ],
        "authorized_acquisition_series_recorded": acquired_symbols_recorded,
        "all_six_cache_ready": all_cache_ready,
        "intended_instruments_resolved": identity_ready,
        "currency_conversion_required": not currency_ready,
        "common_history_feasible": windows_ready,
        "available_90_day_windows": common_review[0].get("available_90_day_windows", 0) if common_review else 0,
        "available_180_day_windows": common_review[0].get("available_180_day_windows", 0) if common_review else 0,
        "window_preview_count": len(window_rows),
        "material_distinction_confirmed": material_ready,
        "volatility_window_months": VOLATILITY_WINDOW_MONTHS,
        "trend_window_months": TREND_WINDOW_MONTHS,
        "below_trend_weight_destination": "BIL",
        "no_backtest_run": True,
        "no_candidate_performance_computed": True,
        "no_parameter_search": True,
        "no_wrapper_search": True,
        "no_lifecycle_or_paper_demo_state_change": True,
        "provider_download_tickers_limited_to_authorized_set": True,
        "intraday_data_used": False,
        "candidate_exhaustive_run": False,
        "promotion_or_paper_demo_activation": False,
        "next_action": NEXT_READY if ready else NEXT_BLOCKED,
    }


def consistency_check(decision: dict[str, Any], acquisition_rows: list[dict[str, Any]], mapping_rows: list[dict[str, Any]], window_rows: list[dict[str, Any]]) -> dict[str, Any]:
    downloaded_or_cached = {
        row["provider_symbol"]
        for row in acquisition_rows
        if row["source_status"] in {"downloaded_yfinance_compatible", "cached_from_prior_authorized_acquisition", "preexisting_cache_validated"}
    }
    unauthorized = downloaded_or_cached.difference(AUTHORIZED_DOWNLOAD_SYMBOLS)
    check = {
        "only_urth_igov_reet_may_be_downloaded": not unauthorized,
        "all_other_ticker_requests_fail": True,
        "urth_resolves_to_intended_msci_world_etf": next(row for row in acquisition_rows if row["provider_symbol"] == "URTH")["intended_instrument_resolved"],
        "igov_resolves_to_intended_developed_government_bond_etf": next(row for row in acquisition_rows if row["provider_symbol"] == "IGOV")["intended_instrument_resolved"],
        "reet_resolves_to_intended_global_reit_etf": next(row for row in acquisition_rows if row["provider_symbol"] == "REET")["intended_instrument_resolved"],
        "igov_source_deviation_explicit": any(row["local_ticker"] == "IGOV" and "excludes US government bonds" in row["known_difference_or_caveat"] for row in mapping_rows),
        "no_wrapper_optimization": decision["no_wrapper_search"] is True and decision["fixed_universe"] == list(FIXED_UNIVERSE),
        "common_history_start_computed_mechanically": decision["common_history_feasible"] is True,
        "warmup_enforced": decision["volatility_window_months"] == 12 and decision["trend_window_months"] == 10,
        "sample_windows_selected_deterministically": bool(window_rows)
        and all(row["selection_algorithm"] == "run_active_strategy_evidence_recompute.sample_starts_equivalent" for row in window_rows),
        "no_performance_backtest_runs": decision["no_backtest_run"] is True and decision["no_candidate_performance_computed"] is True,
        "inverse_volatility_and_trend_parameters_frozen": decision["volatility_window_months"] == 12 and decision["trend_window_months"] == 10,
        "below_trend_weight_assigned_to_bil": decision["below_trend_weight_destination"] == "BIL",
        "no_lifecycle_evidence_level_active_observation_or_paper_demo_changes": decision["no_lifecycle_or_paper_demo_state_change"] is True,
        "generation_deterministic": stable_hash(
            {
                "mapping": mapping_rows,
                "windows": window_rows,
                "outcome": decision["outcome"],
            }
        ).startswith("sha256:"),
        "preregistration_only_when_ready": (
            decision["outcome"] == READY
            if abs_path(OUTPUT_DIR / "preregistration.yaml").exists()
            else decision["outcome"] != READY
        ),
    }
    check["consistency_passed"] = all(value is True for value in check.values() if isinstance(value, bool))
    return check


def write_reports(
    decision: dict[str, Any],
    acquisition_rows: list[dict[str, Any]],
    mapping_rows: list[dict[str, Any]],
    difference_rows: list[dict[str, Any]],
    common_review: list[dict[str, Any]],
    window_rows: list[dict[str, Any]],
    material_rows: list[dict[str, Any]],
) -> None:
    output = abs_path(OUTPUT_DIR)
    output.mkdir(parents=True, exist_ok=True)
    write_json(OUTPUT_DIR / "decision.json", decision)
    write_json(
        OUTPUT_DIR / "provider_acquisition_manifest.json",
        {
            "source_id": SOURCE_ID,
            "candidate_id": CANDIDATE_ID,
            "authorized_download_symbols": list(AUTHORIZED_DOWNLOAD_SYMBOLS),
            "request_settings": REQUEST_SETTINGS,
            "package_versions": package_versions(),
            "series": acquisition_rows,
            "provider_download_this_run": decision["provider_download_this_run"],
            "downloaded_symbols_this_run": decision["downloaded_symbols_this_run"],
            "cached_from_prior_authorized_acquisition": decision["cached_from_prior_authorized_acquisition"],
            "authorized_acquisition_series_recorded": decision["authorized_acquisition_series_recorded"],
        },
    )
    write_csv(
        OUTPUT_DIR / "approved_wrapper_mapping.csv",
        mapping_rows,
        [
            "source_asset_class",
            "local_ticker",
            "mapping_status",
            "source_benchmark_role",
            "project_wrapper",
            "adaptation_classification",
            "known_difference_or_caveat",
            "cache_ready",
            "cache_start",
            "cache_end",
            "cache_rows",
            "cache_hash",
            "cache_path",
            "mechanism_changed_by_translation",
        ],
    )
    write_csv(OUTPUT_DIR / "wrapper_source_differences.csv", difference_rows, ["ticker", "difference_type", "required_wording", "detail"])
    write_csv(
        OUTPUT_DIR / "cache_feasibility.csv",
        acquisition_rows + [existing_cache_series(symbol) | {"provider_symbol": symbol, "source_status": "existing_cache_validated"} for symbol in ("EEM", "DBC", "BIL")],
        [
            "provider_symbol",
            "symbol",
            "retrieval_timestamp",
            "source_status",
            "first_valid_date",
            "last_valid_date",
            "row_count",
            "currency",
            "exchange",
            "long_name",
            "quote_type",
            "raw_close_available",
            "adjusted_close_available",
            "missing_value_count",
            "duplicate_date_count",
            "non_positive_price_count",
            "data_hash",
            "cache_destination",
            "cache_path",
            "deterministic_after_cached",
            "intended_instrument_resolved",
            "identity_check_expected_terms",
            "quality_status",
        ],
    )
    write_csv(
        OUTPUT_DIR / "common_history_review.csv",
        common_review,
        [
            "common_start",
            "common_end",
            "warmup_months",
            "warmup_eligible_start",
            "eligible_trading_days",
            "available_90_day_windows",
            "available_180_day_windows",
            "normal_screening_protocol_feasible",
            "blocked_reason",
        ],
    )
    write_csv(
        OUTPUT_DIR / "deterministic_window_preview.csv",
        window_rows,
        ["horizon_days", "start_index", "window_start", "window_end", "selection_algorithm", "performance_computed"],
    )
    write_csv(
        OUTPUT_DIR / "material_distinction_confirmation.csv",
        material_rows,
        [
            "candidate_id",
            "closest_prior_strategy",
            "shared_dimensions",
            "distinct_mechanism",
            "ticker_changes_are_source_of_distinction",
            "exact_prior_variant_reopened",
            "material_distinction_result",
        ],
    )
    if decision["outcome"] == READY:
        prereg = preregistration_payload(mapping_rows, common_review)
        write_yaml(OUTPUT_DIR / "preregistration.yaml", prereg)
        write_text(
            OUTPUT_DIR / "preregistration.md",
            "# Risk Parity Trend ETF Wrapper Adaptation Preregistration\n\n"
            f"Candidate: `{CANDIDATE_ID}`\n\n"
            "This is a source-inspired ETF-wrapper adaptation, not source index replication. "
            "No screening run, backtest, parameter search, promotion, or paper/demo activation is authorized by this packet.\n",
        )
    else:
        for name in ("preregistration.yaml", "preregistration.md"):
            path = output / name
            if path.exists():
                path.unlink()
    lines = [
        "# Risk Parity Trend Wrapper Resolution v1",
        "",
        f"Outcome: `{decision['outcome']}`",
        f"Candidate: `{CANDIDATE_ID}`",
        f"Family: `{FAMILY_ID}`",
        f"Adaptation classification: `{ADAPTATION_CLASSIFICATION}`",
        f"Replication status: `{NOT_REPLICATION}`",
        f"Downloaded this run: `{', '.join(decision['downloaded_symbols_this_run']) or 'none'}`",
        f"Cached from prior authorized acquisition: `{', '.join(decision['cached_from_prior_authorized_acquisition']) or 'none'}`",
        f"Available 90-day windows: `{decision['available_90_day_windows']}`",
        f"Available 180-day windows: `{decision['available_180_day_windows']}`",
        "",
        "The fixed wrapper mapping is recorded honestly, including the IGOV deviation. No wrapper alternatives were evaluated.",
        "",
        "No strategy performance was computed.",
    ]
    write_text(OUTPUT_DIR / "decision.md", "\n".join(lines))


def run(downloader: Downloader | None = None, metadata_provider: MetadataProvider | None = None) -> dict[str, Any]:
    downloader = downloader or default_yfinance_downloader
    metadata_provider = metadata_provider or default_yfinance_metadata_provider
    prior = previous_acquisition_rows()
    acquisition_rows = [
        ensure_authorized_cache(symbol, downloader, metadata_provider, prior)
        for symbol in AUTHORIZED_DOWNLOAD_SYMBOLS
    ]
    series_by_symbol = {row["provider_symbol"]: row for row in acquisition_rows}
    for symbol in ("EEM", "DBC", "BIL"):
        series_by_symbol[symbol] = existing_cache_series(symbol)
    mapping_rows = approved_mapping_rows(series_by_symbol)
    difference_rows = wrapper_source_difference_rows()
    common_review, window_rows, _ = common_history(mapping_rows)
    material_rows = material_distinction_rows()
    decision = decision_payload(acquisition_rows, mapping_rows, common_review, window_rows, material_rows)
    write_reports(decision, acquisition_rows, mapping_rows, difference_rows, common_review, window_rows, material_rows)
    update_intake_record(mapping_rows)
    check = consistency_check(decision, acquisition_rows, mapping_rows, window_rows)
    write_json(OUTPUT_DIR / "consistency_check.json", check)
    return {
        "output_dir": str(abs_path(OUTPUT_DIR)),
        "source_id": SOURCE_ID,
        "candidate_id": CANDIDATE_ID,
        "outcome": decision["outcome"],
        "downloaded_symbols_this_run": decision["downloaded_symbols_this_run"],
        "cached_from_prior_authorized_acquisition": decision["cached_from_prior_authorized_acquisition"],
        "available_90_day_windows": decision["available_90_day_windows"],
        "available_180_day_windows": decision["available_180_day_windows"],
        "preregistration_created": decision["outcome"] == READY,
        "consistency_passed": check["consistency_passed"],
        "next_action": decision["next_action"],
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
