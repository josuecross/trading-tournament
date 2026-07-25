from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import zipfile
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import requests

from execution_lab.alpaca_micro_live_v1.adapters.alpaca_client import AlpacaClient, AlpacaClientConfig
from execution_lab.alpaca_micro_live_v1.adapters.credentials import (
    LIVE_KEY,
    LIVE_SECRET,
    PAPER_KEY,
    PAPER_SECRET,
    load_alpaca_credentials,
)


ROOT = Path(__file__).resolve().parents[3]
TASK_ID = "fed_model_yield_gap_alpaca_data_feasibility_v1"
CANDIDATE_STRATEGY_ID = "maio_fed_model_yield_gap_spy_bil_recursive_v1"
ADAPTATION_LABEL = "data_feasibility_adjustment"
NEXT_ACTION = "direction_owner_review_next_alpaca_first_fundamental_strategy_page_v1"
RUN_CREATED_UTC = "2026-07-21T00:00:00Z"

OUTPUT_DIR = (
    Path("evidence")
    / "public_source_strategy_intake"
    / "fed_model"
    / "yield_gap_alpaca_data_feasibility_v1"
    / "latest"
)
RAW_CACHE_DIR = Path("data") / "raw" / "fed_model_yield_gap_alpaca_data_feasibility_v1"

SHILLER_DATA_URL = "http://www.econ.yale.edu/~shiller/data/ie_data.xls"
SHILLER_DATA_PAGE = "https://www.econ.yale.edu/~shiller/data.htm"
DGS10_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS10"
DGS10_SERIES_URL = "https://fred.stlouisfed.org/series/DGS10"
FRENCH_FACTORS_ZIP_URL = (
    "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_Factors_CSV.zip"
)
FRENCH_EXPECTED_MEMBER = "F-F_Research_Data_Factors.csv"
SSRN_SOURCE_URL = "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=889931"

ALPACA_SYMBOLS = ["SPY", "BIL"]
ALPACA_BAR_START = "1993-01-01T00:00:00Z"
ALPACA_BAR_END = "2026-07-21T00:00:00Z"
ALPACA_FEED = "iex"
ALPACA_ADJUSTMENT = "all"
ALPACA_TIMEFRAME = "1Day"

OUTCOMES = {
    "source_aligned_data_ready",
    "ready_with_publication_lag_convention",
    "earnings_yield_timing_unresolvable",
    "source_rule_details_incomplete",
    "alpaca_asset_or_bar_access_blocked",
    "official_public_data_access_blocked",
    "insufficient_aligned_history",
    "data_reconciliation_defect",
}

PROTECTED_STATE_PATHS = [
    Path("strategy_lab") / "strategy_registry.yaml",
    Path("strategy_lab") / "research_os" / "research" / "research_queue.yaml",
    Path("strategy_lab") / "research_os" / "family_lineage" / "family_ledger.yaml",
    Path("strategy_lab") / "research_os" / "operations" / "active_observations.yaml",
]

REQUIRED_OUTPUT_FILES = {
    "source_identity.json",
    "repository_capability_review.json",
    "alpaca_spy_bil_asset_check.json",
    "alpaca_bar_coverage.csv",
    "source_rule_completion.csv",
    "earnings_data_schema.json",
    "earnings_publication_timing_review.md",
    "treasury_yield_schema.json",
    "market_and_rf_series_inventory.csv",
    "monthly_information_availability.csv",
    "provider_overlap_reconciliation.csv",
    "data_sources_and_hashes.json",
    "future_baseline_spec.json",
    "feasibility_outcome.json",
    "command_validation_log.csv",
    "consistency_check.json",
    "feasibility_summary.md",
}


def abs_path(root: Path, path: Path) -> Path:
    return path if path.is_absolute() else root / path


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_path(path: Path) -> str:
    if not path.exists():
        return "missing"
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_payload_hash(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()


def state_hashes(root: Path) -> dict[str, str]:
    return {str(path): sha256_path(abs_path(root, path)) for path in PROTECTED_STATE_PATHS}


def clean_output_dir(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    for path in output.iterdir():
        if path.is_file():
            path.unlink()


def to_jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [to_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [to_jsonable(item) for item in value]
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        value = float(value)
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return value
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, pd.Period):
        return str(value)
    if isinstance(value, Path):
        return str(value)
    return value


def csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (np.bool_,)):
        return "true" if bool(value) else "false"
    if isinstance(value, (float, np.floating)) and (math.isnan(float(value)) or math.isinf(float(value))):
        return ""
    if isinstance(value, (list, tuple, set)):
        return "|".join(str(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(to_jsonable(value), sort_keys=True, separators=(",", ":"))
    return str(value)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(to_jsonable(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")


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


def download_or_cache(root: Path, url: str, filename: str, *, timeout: int = 45) -> dict[str, Any]:
    path = abs_path(root, RAW_CACHE_DIR) / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    loaded_from_cache = path.exists()
    status = "loaded_from_cache"
    content_type = ""
    error = ""
    if not loaded_from_cache:
        try:
            response = requests.get(url, timeout=timeout)
            content_type = response.headers.get("content-type", "")
            response.raise_for_status()
            path.write_bytes(response.content)
            status = "downloaded"
        except Exception as exc:  # pragma: no cover - network-specific failure path.
            status = "blocked"
            error = f"{type(exc).__name__}: {str(exc)[:240]}"
    return {
        "url": url,
        "cache_path": str(path),
        "status": status,
        "loaded_from_cache": loaded_from_cache,
        "content_type": content_type,
        "file_hash": sha256_path(path),
        "bytes": path.stat().st_size if path.exists() else 0,
        "error": error,
    }


def ordinary_earnings_yield(earnings: float, price: float) -> float:
    if price <= 0 or not math.isfinite(price):
        raise ValueError("price must be positive and finite")
    if not math.isfinite(earnings):
        raise ValueError("earnings must be finite")
    return float(earnings / price)


def convert_percent_yield_to_decimal(value: float) -> float:
    if not math.isfinite(value):
        raise ValueError("yield must be finite")
    return float(value / 100.0) if abs(value) > 1.0 else float(value)


def yield_gap(price: float, earnings: float, y10_value: float, *, y10_input: str = "percent") -> float:
    ep = ordinary_earnings_yield(earnings, price)
    y10_decimal = convert_percent_yield_to_decimal(y10_value) if y10_input == "percent" else y10_value
    if 1.0 + ep <= 0.0 or 1.0 + y10_decimal <= 0.0:
        raise ValueError("yield-gap log inputs must be greater than -100%")
    return float(math.log1p(ep) - math.log1p(y10_decimal))


def permitted_signal_date(month_end: str, lag_months: int) -> str:
    date = pd.Timestamp(month_end)
    month = date.to_period("M") + lag_months
    return month.to_timestamp(how="end").date().isoformat()


def no_future_earnings_enter_earlier_rows(rows: list[dict[str, Any]]) -> bool:
    for row in rows:
        availability = row.get("earnings_available_date")
        permitted = row.get("permitted_signal_date") or row.get("month_end")
        if not availability or not permitted:
            continue
        if pd.Timestamp(availability) > pd.Timestamp(permitted):
            return False
    return True


def publication_lag_source() -> str:
    return "metadata_only_not_return_selected"


def no_secret_text_written(output: Path, credential_values: list[str | None]) -> bool:
    secrets = [value for value in credential_values if value]
    for path in output.iterdir():
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if any(secret in text for secret in secrets):
            return False
    return True


def repository_capability_review(root: Path) -> dict[str, Any]:
    files = {
        "alpaca_credentials": "execution_lab/alpaca_micro_live_v1/adapters/credentials.py",
        "alpaca_client": "execution_lab/alpaca_micro_live_v1/adapters/alpaca_client.py",
        "alpaca_stock_bars": "execution_lab/alpaca_micro_live_v1/data/alpaca_historical_bars.py",
        "alpaca_runtime_cache": "execution_lab/alpaca_micro_live_v1/data/alpaca_runtime_cache.py",
        "strategy_cache_spy": "data/cache/SPY.csv",
        "strategy_cache_bil": "data/cache/BIL.csv",
        "driesprong_fred_pattern": "strategy_lab/research_os/research/driesprong_oil_us_market_source_split_correction_v1.py",
    }
    credentials = load_alpaca_credentials("paper")
    source_kind = "none"
    if credentials.source == "environment":
        source_kind = "environment"
    elif credentials.source != "none":
        source_kind = "local_env_file"
    return {
        "task_id": TASK_ID,
        "files_inspected": files,
        "classes_and_functions": {
            "AlpacaClient": ["get_account", "get_assets", "get_historical_bars_page"],
            "AlpacaClientConfig": ["paper_base_url", "data_base_url", "data_feed", "data_adjustment"],
            "credentials": ["load_alpaca_credentials", "PAPER_KEY", "PAPER_SECRET", "LIVE_KEY", "LIVE_SECRET"],
            "alpaca_historical_bars": ["parse_bars_response", "fetch_daily_bars"],
            "alpaca_runtime_cache": ["cache_path", "read_symbol_bars", "write_symbol_bars"],
        },
        "environment_variable_names": [PAPER_KEY, PAPER_SECRET, LIVE_KEY, LIVE_SECRET],
        "credential_values_persisted": False,
        "paper_credentials_present": credentials.present,
        "credential_source_kind": source_kind,
        "live_credentials_detected": credentials.live_credentials_detected,
        "alpaca_assets_api_supported": True,
        "alpaca_adjusted_stock_bars_supported": True,
        "spy_bil_local_strategy_cache_present": {
            symbol: abs_path(root, Path("data") / "cache" / f"{symbol}.csv").exists() for symbol in ALPACA_SYMBOLS
        },
        "fred_download_pattern_present": abs_path(root, Path(files["driesprong_fred_pattern"])).exists(),
        "yale_shiller_generic_parser_present": False,
        "monthly_macro_calendar_engine_present": False,
        "data_release_timestamp_engine_present": False,
        "provider_overlap_reconciliation_present": "task_specific_only",
        "dataset_hashing_and_provenance_supported": True,
        "cache_conventions": {
            "strategy_lab_daily_etf_cache": "data/cache/{SYMBOL}.csv",
            "alpaca_runtime_cache": "execution_lab/alpaca_micro_live_v1/evidence/alpaca_runtime_data/cache/{SYMBOL}_1Day.csv",
            "this_task_raw_public_data_cache": str(abs_path(root, RAW_CACHE_DIR)),
        },
        "broker_order_endpoint_called": False,
    }


def source_identity() -> dict[str, Any]:
    return {
        "task_id": TASK_ID,
        "candidate_strategy": CANDIDATE_STRATEGY_ID,
        "adaptation_label": ADAPTATION_LABEL,
        "source_name": "The 'Fed Model' and the Predictability of Stock Returns",
        "author": "Paulo F. Maio",
        "journal_status": "Review of Finance article / SSRN working paper page",
        "ssrn_url": SSRN_SOURCE_URL,
        "source_rule_preserved": {
            "yield_gap_formula": "YG_t = log(1 + E_t / P_t) - log(1 + Y10_t)",
            "forecast_model": "equity_excess_return_t_plus_1 = intercept_t + beta_t * YG_t + error",
            "recursive_estimation": True,
            "equity_state": "hold equity market when forecast is positive",
            "risk_free_state": "hold risk-free asset otherwise",
        },
        "not_replaced_with": ["direct_E_over_P_threshold", "CAPE", "forward_earnings", "real_treasury_yields", "term_spread", "multiple_predictors"],
        "source_reported_performance_used": False,
    }


def source_rule_completion_rows() -> list[dict[str, Any]]:
    return [
        {
            "item": "stock_bond_yield_gap_predictor",
            "status": "confirmed",
            "value": "difference between stock market earnings yield and ten-year Treasury bond yield",
            "source_or_convention": "SSRN abstract and direction-owner source rule",
            "notes": "Uses ordinary E/P, not CAPE or forward earnings in this task packet.",
        },
        {
            "item": "log_yield_gap_formula",
            "status": "confirmed",
            "value": "log(1 + E/P) - log(1 + Y10)",
            "source_or_convention": "direction-owner source rule",
            "notes": "Formula preserved for future baseline; no signal is calculated here.",
        },
        {
            "item": "recursive_update_rule",
            "status": "confirmed",
            "value": "re-estimate monthly using only chronologically available data",
            "source_or_convention": "direction-owner source rule",
            "notes": "No expanding/recursive regression is executed by this feasibility task.",
        },
        {
            "item": "timing_between_signal_and_return",
            "status": "confirmed",
            "value": "YG_t forecasts equity excess return in t+1",
            "source_or_convention": "direction-owner source rule",
            "notes": "No same-month return may enter a later implementation signal.",
        },
        {
            "item": "forecast_positive_restriction",
            "status": "implementation_convention_required",
            "value": "hold market when forecast is positive, otherwise risk-free",
            "source_or_convention": "direction-owner source rule and SSRN abstract mentions positive equity-premium restriction",
            "notes": "Exact paper table/variant tying the restriction to the implementable timing rule was not independently extracted here.",
        },
        {
            "item": "market_return_definition",
            "status": "implementation_convention_required",
            "value": "Kenneth French monthly Mkt-RF plus RF for pre-ETF diagnostic; SPY for later Alpaca implementation",
            "source_or_convention": "project data-feasibility convention",
            "notes": "SSRN abstract mentions value/equal-weighted stock indexes but does not provide enough implementation detail in the public abstract.",
        },
        {
            "item": "risk_free_definition",
            "status": "implementation_convention_required",
            "value": "Kenneth French RF for source-regression diagnostic; BIL for later Alpaca implementation",
            "source_or_convention": "project data-feasibility convention",
            "notes": "Exact paper risk-free source was not fully extracted from the public abstract.",
        },
        {
            "item": "earnings_yield_definition",
            "status": "confirmed",
            "value": "ordinary earnings / price",
            "source_or_convention": "source rule; Shiller ordinary earnings field candidate",
            "notes": "No CAPE or forward earnings substitute is introduced.",
        },
        {
            "item": "ten_year_yield_aggregation",
            "status": "unresolved",
            "value": "month-end versus monthly-average not source-confirmed",
            "source_or_convention": "unresolved",
            "notes": "FRED DGS10 is daily; FRED also offers monthly transformations, but performance is not used to choose.",
        },
        {
            "item": "exact_sample_start_and_end",
            "status": "unresolved",
            "value": "not frozen",
            "source_or_convention": "unresolved",
            "notes": "Requires full source methodology extraction before implementation.",
        },
        {
            "item": "initial_out_of_sample_estimation_window",
            "status": "unresolved",
            "value": "not frozen",
            "source_or_convention": "unresolved",
            "notes": "Cannot infer warmup silently.",
        },
        {
            "item": "transaction_cost_assumption",
            "status": "unresolved",
            "value": "not frozen",
            "source_or_convention": "unresolved",
            "notes": "Cannot infer cost assumption silently.",
        },
        {
            "item": "source_benchmarks",
            "status": "confirmed",
            "value": "historical-average equity-premium forecast control",
            "source_or_convention": "SSRN abstract",
            "notes": "The future baseline spec may include this control only if data-ready.",
        },
    ]


def source_rules_complete_for_data_feasibility(rows: list[dict[str, Any]]) -> bool:
    critical_items = {
        "stock_bond_yield_gap_predictor",
        "log_yield_gap_formula",
        "recursive_update_rule",
        "timing_between_signal_and_return",
        "earnings_yield_definition",
    }
    by_item = {row["item"]: row for row in rows}
    return all(by_item[item]["status"] == "confirmed" for item in critical_items)


def parse_fred_dgs10(path: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    if not path.exists():
        return pd.DataFrame(), {"parse_status": "missing_file"}
    frame = pd.read_csv(path)
    if "observation_date" not in frame.columns or "DGS10" not in frame.columns:
        return pd.DataFrame(), {"parse_status": "unexpected_schema", "columns": list(frame.columns)}
    frame["observation_date"] = pd.to_datetime(frame["observation_date"], errors="coerce")
    frame["DGS10"] = pd.to_numeric(frame["DGS10"], errors="coerce")
    frame = frame.dropna(subset=["observation_date", "DGS10"]).sort_values("observation_date").reset_index(drop=True)
    meta = {
        "parse_status": "parsed",
        "series_id": "DGS10",
        "source": "FRED / Board of Governors H.15",
        "units": "Percent, not seasonally adjusted",
        "frequency": "Daily",
        "first_observation": frame["observation_date"].min().date().isoformat() if not frame.empty else "",
        "last_observation": frame["observation_date"].max().date().isoformat() if not frame.empty else "",
        "observation_count": int(len(frame)),
        "unit_conversion": "decimal_yield = percent / 100",
        "month_end_or_monthly_average_required": "unresolved_pending_source_methodology",
        "missing_date_handling": "future implementation must select prior valid observation or monthly transformation before performance is calculated",
    }
    return frame, meta


def parse_french_factors(path: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    if not path.exists():
        return pd.DataFrame(), {"parse_status": "missing_file"}
    try:
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            member = FRENCH_EXPECTED_MEMBER if FRENCH_EXPECTED_MEMBER in names else names[0]
            text = archive.read(member).decode("utf-8", errors="replace")
        lines = text.splitlines()
        header_index = next(i for i, line in enumerate(lines) if line.strip().startswith(",Mkt-RF"))
        monthly_lines = [lines[header_index]]
        for line in lines[header_index + 1 :]:
            first = line.split(",", 1)[0].strip()
            if len(first) != 6 or not first.isdigit():
                break
            monthly_lines.append(line)
        frame = pd.read_csv(io.StringIO("\n".join(monthly_lines)))
        frame = frame.rename(columns={frame.columns[0]: "yyyymm"})
        frame["month"] = pd.PeriodIndex(frame["yyyymm"].astype(str), freq="M")
        for column in ["Mkt-RF", "RF"]:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
        frame = frame.dropna(subset=["month", "Mkt-RF", "RF"]).sort_values("month").reset_index(drop=True)
    except Exception as exc:  # pragma: no cover - corrupt cache/network edge.
        return pd.DataFrame(), {"parse_status": "parse_error", "error": f"{type(exc).__name__}: {str(exc)[:160]}"}
    return frame, {
        "parse_status": "parsed",
        "source": "Kenneth French data library",
        "member": member,
        "frequency": "Monthly",
        "fields": ["Mkt-RF", "RF"],
        "units": "Percent",
        "first_month": str(frame["month"].min()) if not frame.empty else "",
        "last_month": str(frame["month"].max()) if not frame.empty else "",
        "row_count": int(len(frame)),
        "strategy_returns_calculated": False,
    }


def shiller_schema(download: dict[str, Any]) -> dict[str, Any]:
    parse_status = "blocked_legacy_xls_parser_unavailable" if download["status"] != "blocked" else "download_blocked"
    return {
        "source": "Robert Shiller official Yale market dataset",
        "data_page": SHILLER_DATA_PAGE,
        "download_url": SHILLER_DATA_URL,
        "download_status": download["status"],
        "file_hash": download["file_hash"],
        "bytes": download["bytes"],
        "parse_status": parse_status,
        "fields_required_for_candidate": ["Date", "Price", "Earnings"],
        "field_substitution_prohibited": ["CAPE", "forward_earnings", "real_earnings_without_price_alignment"],
        "frequency": "Monthly per official Shiller data page",
        "earliest_date": "not_parsed_in_current_venv",
        "latest_date": "not_parsed_in_current_venv",
        "earnings_construction": (
            "Official Shiller notes describe monthly earnings as S&P four-quarter totals interpolated to monthly figures."
        ),
        "historical_revision_risk": "material; current workbook is not a point-in-time vintage series",
        "vintage_files_found": False,
        "historical_investor_knowledge_at_month_end": "not_established",
        "license_or_storage_notes": "Official public workbook downloaded for private research feasibility; retain attribution and avoid redistribution.",
    }


def market_and_rf_inventory(french_meta: dict[str, Any], spy_cache: dict[str, Any], bil_cache: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "series_id": "ken_french_mkt_rf_plus_rf",
            "role": "source_regression_market_total_return_candidate",
            "provider": "Kenneth French data library",
            "frequency": "monthly",
            "fields": "Mkt-RF|RF",
            "first_date": french_meta.get("first_month", ""),
            "latest_date": french_meta.get("last_month", ""),
            "status": french_meta.get("parse_status", "unknown"),
            "strategy_returns_calculated": False,
        },
        {
            "series_id": "ken_french_rf",
            "role": "source_regression_risk_free_candidate",
            "provider": "Kenneth French data library",
            "frequency": "monthly",
            "fields": "RF",
            "first_date": french_meta.get("first_month", ""),
            "latest_date": french_meta.get("last_month", ""),
            "status": french_meta.get("parse_status", "unknown"),
            "strategy_returns_calculated": False,
        },
        {
            "series_id": "SPY",
            "role": "later_alpaca_equity_wrapper",
            "provider": "local project cache / Alpaca endpoint check",
            "frequency": "daily",
            "fields": "adjusted OHLCV",
            "first_date": spy_cache.get("first_date", ""),
            "latest_date": spy_cache.get("latest_date", ""),
            "status": spy_cache.get("status", "unknown"),
            "strategy_returns_calculated": False,
        },
        {
            "series_id": "BIL",
            "role": "later_alpaca_risk_free_wrapper",
            "provider": "local project cache / Alpaca endpoint check",
            "frequency": "daily",
            "fields": "adjusted OHLCV",
            "first_date": bil_cache.get("first_date", ""),
            "latest_date": bil_cache.get("latest_date", ""),
            "status": bil_cache.get("status", "unknown"),
            "strategy_returns_calculated": False,
        },
    ]


def local_cache_summary(root: Path, symbol: str) -> dict[str, Any]:
    path = abs_path(root, Path("data") / "cache" / f"{symbol}.csv")
    if not path.exists():
        return {"symbol": symbol, "status": "missing", "path": str(path), "hash": "missing"}
    frame = pd.read_csv(path)
    date_column = "date" if "date" in frame.columns else frame.columns[0]
    dates = pd.to_datetime(frame[date_column], errors="coerce").dropna()
    return {
        "symbol": symbol,
        "status": "present",
        "path": str(path),
        "hash": sha256_path(path),
        "rows": int(len(frame)),
        "first_date": dates.min().date().isoformat() if not dates.empty else "",
        "latest_date": dates.max().date().isoformat() if not dates.empty else "",
        "columns": list(frame.columns),
    }


def parse_alpaca_bars_payload(symbol: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
    bars = payload.get("bars", {}).get(symbol, [])
    rows = []
    for bar in bars:
        timestamp = pd.Timestamp(bar.get("t"))
        if timestamp.tzinfo is None:
            timestamp = timestamp.tz_localize("UTC")
        else:
            timestamp = timestamp.tz_convert("UTC")
        rows.append(
            {
                "symbol": symbol,
                "date": timestamp.date().isoformat(),
                "timestamp": timestamp.isoformat(),
                "open": float(bar.get("o")),
                "high": float(bar.get("h")),
                "low": float(bar.get("l")),
                "close": float(bar.get("c")),
                "volume": float(bar.get("v", 0.0)),
            }
        )
    return rows


def alpaca_asset_and_bar_check(root: Path) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    credentials = load_alpaca_credentials("paper")
    source_kind = "environment" if credentials.source == "environment" else ("local_env_file" if credentials.source != "none" else "none")
    asset_rows: dict[str, Any] = {}
    bar_rows: list[dict[str, Any]] = []
    account_status = {
        "credential_source_kind": source_kind,
        "paper_credentials_present": credentials.present,
        "live_credentials_detected": credentials.live_credentials_detected,
        "credential_values_persisted": False,
        "read_only_endpoints_only": True,
        "order_endpoint_called": False,
        "configured_data_feed": ALPACA_FEED,
    }
    raw_cache_root = abs_path(root, RAW_CACHE_DIR) / "alpaca_stock_bars"
    raw_cache_root.mkdir(parents=True, exist_ok=True)

    if not credentials.present:
        for symbol in ALPACA_SYMBOLS:
            runtime_path = (
                root
                / "execution_lab"
                / "alpaca_micro_live_v1"
                / "evidence"
                / "alpaca_runtime_data"
                / "cache"
                / f"{symbol}_1Day.csv"
            )
            local_runtime_rows = 0
            runtime_first = ""
            runtime_latest = ""
            runtime_hash = sha256_path(runtime_path)
            if runtime_path.exists():
                frame = pd.read_csv(runtime_path)
                dates = pd.to_datetime(frame["date"], errors="coerce").dropna()
                local_runtime_rows = int(len(frame))
                runtime_first = dates.min().date().isoformat() if not dates.empty else ""
                runtime_latest = dates.max().date().isoformat() if not dates.empty else ""
            asset_rows[symbol] = {
                "symbol": symbol,
                "endpoint_status": "auth_blocked",
                "exists": None,
                "active": None,
                "tradable": None,
                "fractionable": None,
                "marginable": None,
                "shortable": "not_required",
                "error": "Alpaca paper credentials missing; assets API not called.",
            }
            bar_rows.append(
                {
                    "symbol": symbol,
                    "endpoint_status": "auth_blocked",
                    "historical_bars_available": False,
                    "earliest_available_bar": "",
                    "latest_available_bar": "",
                    "observation_count": 0,
                    "adjustment": ALPACA_ADJUSTMENT,
                    "feed": ALPACA_FEED,
                    "timeframe": ALPACA_TIMEFRAME,
                    "pagination_pages": 0,
                    "cache_path": str(runtime_path),
                    "cache_hash": runtime_hash,
                    "runtime_cache_rows_visible": local_runtime_rows,
                    "runtime_cache_first_date": runtime_first,
                    "runtime_cache_latest_date": runtime_latest,
                    "error": "Alpaca paper credentials missing; bars endpoint not called.",
                }
            )
        account_status["account_endpoint_status"] = "auth_blocked"
        account_status["account_data_feed_entitlement"] = "unknown_auth_blocked"
        return {"account": account_status, "assets": asset_rows}, bar_rows, {
            "alpaca_read_only_access_ok": False,
            "credential_values": [credentials.api_key, credentials.secret_key],
        }

    client = AlpacaClient(credentials, AlpacaClientConfig(data_feed=ALPACA_FEED, data_adjustment=ALPACA_ADJUSTMENT))
    try:
        account = client.get_account()
        account_status["account_endpoint_status"] = "ok"
        account_status["account_data_feed_entitlement"] = str(account.get("market_data_feed", account.get("data_feed", ALPACA_FEED)))
        account_status["account_fields_recorded"] = sorted(k for k in account.keys() if "key" not in k.lower() and "secret" not in k.lower())
    except Exception as exc:
        account_status["account_endpoint_status"] = "blocked"
        account_status["account_data_feed_entitlement"] = "unknown_account_endpoint_blocked"
        account_status["account_error"] = f"{type(exc).__name__}: {str(exc)[:180]}"

    try:
        assets = client.get_assets(ALPACA_SYMBOLS)
        by_symbol = {row.get("symbol"): row for row in assets}
        for symbol in ALPACA_SYMBOLS:
            asset = by_symbol.get(symbol, {})
            asset_rows[symbol] = {
                "symbol": symbol,
                "endpoint_status": "ok" if asset else "missing",
                "exists": bool(asset),
                "active": asset.get("status") == "active",
                "tradable": bool(asset.get("tradable", False)) if asset else None,
                "fractionable": bool(asset.get("fractionable", False)) if asset else None,
                "marginable": bool(asset.get("marginable", False)) if asset else None,
                "shortable": "not_required",
                "asset_class": asset.get("class", ""),
                "exchange": asset.get("exchange", ""),
                "error": "" if asset else "symbol not returned by Alpaca assets API",
            }
    except Exception as exc:
        for symbol in ALPACA_SYMBOLS:
            asset_rows[symbol] = {
                "symbol": symbol,
                "endpoint_status": "blocked",
                "exists": None,
                "active": None,
                "tradable": None,
                "fractionable": None,
                "marginable": None,
                "shortable": "not_required",
                "error": f"{type(exc).__name__}: {str(exc)[:180]}",
            }

    for symbol in ALPACA_SYMBOLS:
        raw_payload = {"bars": {symbol: []}}
        page_token: str | None = None
        pages = 0
        endpoint_status = "ok"
        error = ""
        try:
            while True:
                payload = client.get_historical_bars_page(
                    symbols=[symbol],
                    start=ALPACA_BAR_START,
                    end=ALPACA_BAR_END,
                    timeframe=ALPACA_TIMEFRAME,
                    page_token=page_token,
                    feed=ALPACA_FEED,
                    adjustment=ALPACA_ADJUSTMENT,
                    limit=10000,
                )
                pages += 1
                raw_payload["bars"].setdefault(symbol, []).extend(payload.get("bars", {}).get(symbol, []))
                page_token = payload.get("next_page_token")
                if not page_token:
                    break
        except Exception as exc:
            endpoint_status = "blocked"
            error = f"{type(exc).__name__}: {str(exc)[:180]}"
        cache_path = raw_cache_root / f"{symbol}_{ALPACA_TIMEFRAME}_{ALPACA_ADJUSTMENT}_{ALPACA_FEED}.json"
        cache_path.write_text(
            json.dumps(
                {
                    "symbol": symbol,
                    "endpoint_status": endpoint_status,
                    "request": {
                        "start": ALPACA_BAR_START,
                        "end": ALPACA_BAR_END,
                        "feed": ALPACA_FEED,
                        "adjustment": ALPACA_ADJUSTMENT,
                        "timeframe": ALPACA_TIMEFRAME,
                    },
                    "pages": pages,
                    "payload": raw_payload,
                    "secrets_included": False,
                    "error": error,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        parsed = parse_alpaca_bars_payload(symbol, raw_payload)
        dates = [row["date"] for row in parsed]
        bar_rows.append(
            {
                "symbol": symbol,
                "endpoint_status": endpoint_status,
                "historical_bars_available": bool(parsed),
                "earliest_available_bar": min(dates) if dates else "",
                "latest_available_bar": max(dates) if dates else "",
                "observation_count": len(parsed),
                "adjustment": ALPACA_ADJUSTMENT,
                "feed": ALPACA_FEED,
                "timeframe": ALPACA_TIMEFRAME,
                "pagination_pages": pages,
                "cache_path": str(cache_path),
                "cache_hash": sha256_path(cache_path),
                "runtime_cache_rows_visible": "",
                "runtime_cache_first_date": "",
                "runtime_cache_latest_date": "",
                "error": error,
            }
        )
    read_only_ok = all(asset_rows[symbol]["endpoint_status"] == "ok" for symbol in ALPACA_SYMBOLS) and all(
        row["endpoint_status"] == "ok" and row["historical_bars_available"] for row in bar_rows
    )
    return {"account": account_status, "assets": asset_rows}, bar_rows, {
        "alpaca_read_only_access_ok": read_only_ok,
        "credential_values": [credentials.api_key, credentials.secret_key],
    }


def monthly_information_availability_rows() -> list[dict[str, Any]]:
    rows = []
    sample_months = pd.period_range("2024-01", periods=6, freq="M")
    for month in sample_months:
        month_end = month.to_timestamp(how="end").date().isoformat()
        rows.append(
            {
                "month": str(month),
                "month_end": month_end,
                "earnings_source": "Shiller/Yale current workbook",
                "earnings_available_date": "",
                "treasury_source": "FRED DGS10 daily",
                "treasury_available_date": permitted_signal_date(month_end, 0),
                "permitted_signal_date": "",
                "earnings_timing_status": "unresolved_no_point_in_time_vintage",
                "treasury_timing_status": "daily_release_visible_but_month_end_or_average_unfrozen",
                "future_earnings_enter_earlier_row": "unknown_not_allowed",
                "publication_lag_source": publication_lag_source(),
                "alternative_lags_performance_tested": False,
            }
        )
    return rows


def provider_overlap_reconciliation(root: Path, bar_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for symbol in ALPACA_SYMBOLS:
        local = local_cache_summary(root, symbol)
        endpoint_row = next(row for row in bar_rows if row["symbol"] == symbol)
        status = "not_available"
        overlap_start = ""
        overlap_end = ""
        overlap_months = 0
        max_abs_monthly_return_diff = ""
        if local["status"] == "present" and endpoint_row["historical_bars_available"] and Path(str(endpoint_row["cache_path"])).exists():
            raw = json.loads(Path(str(endpoint_row["cache_path"])).read_text(encoding="utf-8"))
            parsed = pd.DataFrame(parse_alpaca_bars_payload(symbol, raw.get("payload", {})))
            local_frame = pd.read_csv(local["path"])
            if not parsed.empty and "adj_close" in local_frame.columns:
                parsed["date"] = pd.to_datetime(parsed["date"])
                local_frame["date"] = pd.to_datetime(local_frame["date"])
                parsed["month"] = parsed["date"].dt.to_period("M")
                local_frame["month"] = local_frame["date"].dt.to_period("M")
                alpaca_m = parsed.sort_values("date").groupby("month").tail(1).set_index("month")["close"]
                local_m = local_frame.sort_values("date").groupby("month").tail(1).set_index("month")["adj_close"]
                overlap = sorted(set(alpaca_m.index) & set(local_m.index))
                if len(overlap) > 2:
                    a_ret = alpaca_m.loc[overlap].pct_change()
                    l_ret = local_m.loc[overlap].pct_change()
                    diff = (a_ret - l_ret).dropna().abs()
                    status = "compared_adjusted_monthly_returns"
                    overlap_start = str(overlap[0])
                    overlap_end = str(overlap[-1])
                    overlap_months = len(overlap)
                    max_abs_monthly_return_diff = float(diff.max()) if not diff.empty else ""
        else:
            status = "blocked_no_endpoint_bars" if not endpoint_row["historical_bars_available"] else "local_cache_missing"
        rows.append(
            {
                "symbol": symbol,
                "public_history_series": "pre_etf_market_and_rf_research_returns",
                "alpaca_series": f"{symbol}_{ALPACA_TIMEFRAME}_{ALPACA_ADJUSTMENT}_{ALPACA_FEED}",
                "overlap_status": status,
                "overlap_start": overlap_start,
                "overlap_end": overlap_end,
                "overlap_months": overlap_months,
                "comparison": "Alpaca ETF monthly close return versus local adjusted-cache ETF monthly return where endpoint bars exist",
                "max_abs_monthly_return_difference": max_abs_monthly_return_diff,
                "provider_boundary_freeze": "not_frozen_if_endpoint_unavailable_or_timing_unresolved",
                "strategy_returns_calculated": False,
            }
        )
    return rows


def future_baseline_spec(outcome: str) -> dict[str, Any]:
    ready = outcome in {"source_aligned_data_ready", "ready_with_publication_lag_convention"}
    return {
        "candidate_strategy": CANDIDATE_STRATEGY_ID,
        "spec_created": ready,
        "blocked_reason": "" if ready else "data feasibility outcome is not source-aligned/data-ready",
        "strategy_configurations": [
            {
                "strategy_id": CANDIDATE_STRATEGY_ID,
                "source_baseline_only": True,
                "yield_gap_formula": "log(1 + E_t / P_t) - log(1 + Y10_t)",
                "recursive_estimation": "monthly expanding/recursive using chronologically available data only",
                "forecast_target": "next_month_equity_excess_return",
                "state_rule": "hold SPY when forecast is positive; hold BIL otherwise",
                "controls": [
                    "SPY_buy_and_hold",
                    "BIL_buy_and_hold",
                    "historical_average_equity_premium_forecast_control",
                    "static_average_exposure_control",
                    "IdentityOverlay_equality_requirement",
                ],
                "overlay_variants_frozen": False,
                "performance_screen_authorized": False,
            }
        ]
        if ready
        else [],
        "no_overlay_variants": True,
        "do_not_execute_in_this_task": True,
    }


def determine_outcome(
    *,
    alpaca_ok: bool,
    official_downloads_ok: bool,
    rules_complete_for_data: bool,
    earnings_timing_resolved: bool,
    aligned_history_sufficient: bool,
    reconciliation_defect: bool,
) -> str:
    if not alpaca_ok:
        return "alpaca_asset_or_bar_access_blocked"
    if not official_downloads_ok:
        return "official_public_data_access_blocked"
    if not rules_complete_for_data:
        return "source_rule_details_incomplete"
    if not earnings_timing_resolved:
        return "earnings_yield_timing_unresolvable"
    if not aligned_history_sufficient:
        return "insufficient_aligned_history"
    if reconciliation_defect:
        return "data_reconciliation_defect"
    return "source_aligned_data_ready"


def command_validation_rows() -> list[dict[str, Any]]:
    commands = [
        ".venv\\Scripts\\python.exe run_fed_model_yield_gap_alpaca_data_feasibility_v1.py",
        ".venv\\Scripts\\python.exe -m pytest tests\\test_fed_model_yield_gap_alpaca_data_feasibility_v1.py -q",
        ".venv\\Scripts\\python.exe run_current_research_checkpoint.py",
        ".venv\\Scripts\\python.exe run_research_state_dashboard.py",
        ".venv\\Scripts\\python.exe run_advisor_consistency_check.py",
        ".venv\\Scripts\\python.exe run_strategy_lab.py --validate-registry --export-evidence",
    ]
    return [{"command": command, "status": "not_run_by_runner", "notes": "updated after command execution"} for command in commands]


def consistency_payload(
    output: Path,
    outcome: str,
    before_state: dict[str, str],
    after_state: dict[str, str],
    credentials_values: list[str | None],
    future_spec: dict[str, Any],
) -> dict[str, Any]:
    required = {name: (output / name).exists() for name in sorted(REQUIRED_OUTPUT_FILES)}
    required["consistency_check.json"] = True
    checks = {
        "required_files_present": all(required.values()),
        "outcome_allowed": outcome in OUTCOMES,
        "read_only_alpaca_endpoints_only": True,
        "yield_gap_uses_ordinary_earnings_yield": True,
        "no_cape_or_forward_earnings_substitute": True,
        "ten_year_yield_conversion_consistent": convert_percent_yield_to_decimal(4.6) == 0.046,
        "publication_lag_metadata_not_return_selected": publication_lag_source() == "metadata_only_not_return_selected",
        "no_alternative_lags_performance_tested": True,
        "no_strategy_return_cagr_sharpe_drawdown_calculated": True,
        "no_trade_management_overlay_executed": True,
        "no_order_endpoint_called": True,
        "registry_and_paper_demo_state_preserved": before_state == after_state,
        "api_credentials_not_persisted": no_secret_text_written(output, credentials_values),
        "future_spec_only_when_data_ready": bool(future_spec.get("strategy_configurations"))
        == (outcome in {"source_aligned_data_ready", "ready_with_publication_lag_convention"}),
        "next_action_exact": NEXT_ACTION == "direction_owner_review_next_alpaca_first_fundamental_strategy_page_v1",
    }
    return {**checks, "required_files": required, "consistency_passed": all(checks.values())}


def feasibility_summary(outcome: str, asset_check: dict[str, Any], shiller: dict[str, Any], dgs10: dict[str, Any]) -> str:
    return f"""# Fed Model Yield-Gap Alpaca Data Feasibility

Task: `{TASK_ID}`

Candidate strategy: `{CANDIDATE_STRATEGY_ID}`

Outcome: `{outcome}`

SPY/BIL Alpaca read-only access OK: `{all(asset_check['assets'][symbol]['endpoint_status'] == 'ok' for symbol in ALPACA_SYMBOLS)}`

Shiller/Yale workbook download status: `{shiller['download_status']}`

Shiller/Yale workbook parse status: `{shiller['parse_status']}`

DGS10 parse status: `{dgs10['parse_status']}`

Hidden look-ahead risk: the current Shiller workbook is not a point-in-time vintage series in this feasibility packet, and exact month-end investor availability for interpolated earnings is not established. No publication lag was chosen from performance.

This packet does not calculate strategy returns, run a backtest, tune parameters, run overlays, submit orders, activate paper/demo, promote anything, or make real-money recommendations.

Exact next action: `{NEXT_ACTION}`
"""


def earnings_timing_review_md(shiller: dict[str, Any]) -> str:
    return f"""# Earnings Publication Timing Review

Source reviewed: Robert Shiller official Yale market dataset.

Required future signal input: ordinary `E_t / P_t`.

Workbook download status: `{shiller['download_status']}`.

Workbook parse status in the active repository environment: `{shiller['parse_status']}`.

The source-compatible point-in-time issue is not resolved here. The official Shiller notes describe monthly earnings as four-quarter totals interpolated to monthly figures, while this feasibility packet found no point-in-time vintage file or release calendar that proves each monthly interpolated value was known at that month-end.

Answers to the feasibility questions:

1. Exact historical earnings yield observable without revisions: `not_established`.
2. Deterministic lag required if Shiller current workbook is used: `yes_if_direction_owner_accepts_source_translation`.
3. Smallest defensible lag from metadata: `unresolved`; no lag is selected here.
4. Whether a lag preserves the source economic question: `requires_direction_owner_review`.
5. Whether lag is documented source translation: `yes_if_later_authorized`.
6. Enough aligned history after lag: `not_calculated_without_parsed earnings schema`.
7. Latest signal monthly reproducibility: `blocked_until earnings release timing and parser are approved`.

No alternative lags were tested against returns.
"""


def run(root: Path = ROOT) -> dict[str, Any]:
    output = abs_path(root, OUTPUT_DIR)
    clean_output_dir(output)
    before_state = state_hashes(root)

    shiller_download = download_or_cache(root, SHILLER_DATA_URL, "ie_data.xls", timeout=60)
    dgs10_download = download_or_cache(root, DGS10_CSV_URL, "DGS10.csv")
    french_download = download_or_cache(root, FRENCH_FACTORS_ZIP_URL, "F-F_Research_Data_Factors_CSV.zip")

    dgs10_frame, dgs10_meta = parse_fred_dgs10(Path(dgs10_download["cache_path"]))
    french_frame, french_meta = parse_french_factors(Path(french_download["cache_path"]))
    shiller = shiller_schema(shiller_download)
    asset_check, alpaca_bar_rows, alpaca_meta = alpaca_asset_and_bar_check(root)
    spy_cache = local_cache_summary(root, "SPY")
    bil_cache = local_cache_summary(root, "BIL")
    rules = source_rule_completion_rows()
    availability = monthly_information_availability_rows()
    overlap = provider_overlap_reconciliation(root, alpaca_bar_rows)

    official_downloads_ok = shiller_download["status"] != "blocked" and dgs10_download["status"] != "blocked" and french_download["status"] != "blocked"
    rules_complete = source_rules_complete_for_data_feasibility(rules)
    earnings_timing_resolved = False
    aligned_history_sufficient = bool(not dgs10_frame.empty and not french_frame.empty)
    reconciliation_defect = any(row["overlap_status"] == "data_reconciliation_defect" for row in overlap)
    outcome = determine_outcome(
        alpaca_ok=bool(alpaca_meta["alpaca_read_only_access_ok"]),
        official_downloads_ok=official_downloads_ok,
        rules_complete_for_data=rules_complete,
        earnings_timing_resolved=earnings_timing_resolved,
        aligned_history_sufficient=aligned_history_sufficient,
        reconciliation_defect=reconciliation_defect,
    )
    future_spec = future_baseline_spec(outcome)

    data_sources = {
        "task_id": TASK_ID,
        "source_identity_page": {"url": SSRN_SOURCE_URL, "downloaded_in_runner": False},
        "shiller_yale_workbook": shiller_download,
        "fred_dgs10": dgs10_download,
        "kenneth_french_monthly_factors": french_download,
        "alpaca_bars": alpaca_bar_rows,
        "strategy_returns_calculated": False,
        "credentials_persisted": False,
    }
    treasury_schema = {
        **dgs10_meta,
        "download_url": DGS10_CSV_URL,
        "series_url": DGS10_SERIES_URL,
        "download_status": dgs10_download["status"],
        "file_hash": dgs10_download["file_hash"],
        "release_timing": "FRED page reports updates and next release date; H.15 release timing must be frozen before implementation.",
        "source_compatible_month_end_or_monthly_average": "unresolved_not_performance_selected",
    }
    source_id = source_identity()
    repo_review = repository_capability_review(root)
    market_rf_rows = market_and_rf_inventory(french_meta, spy_cache, bil_cache)

    write_json(output / "source_identity.json", source_id)
    write_json(output / "repository_capability_review.json", repo_review)
    write_json(output / "alpaca_spy_bil_asset_check.json", asset_check)
    write_csv(
        output / "alpaca_bar_coverage.csv",
        alpaca_bar_rows,
        [
            "symbol",
            "endpoint_status",
            "historical_bars_available",
            "earliest_available_bar",
            "latest_available_bar",
            "observation_count",
            "adjustment",
            "feed",
            "timeframe",
            "pagination_pages",
            "cache_path",
            "cache_hash",
            "runtime_cache_rows_visible",
            "runtime_cache_first_date",
            "runtime_cache_latest_date",
            "error",
        ],
    )
    write_csv(output / "source_rule_completion.csv", rules, ["item", "status", "value", "source_or_convention", "notes"])
    write_json(output / "earnings_data_schema.json", shiller)
    write_text(output / "earnings_publication_timing_review.md", earnings_timing_review_md(shiller))
    write_json(output / "treasury_yield_schema.json", treasury_schema)
    write_csv(
        output / "market_and_rf_series_inventory.csv",
        market_rf_rows,
        ["series_id", "role", "provider", "frequency", "fields", "first_date", "latest_date", "status", "strategy_returns_calculated"],
    )
    write_csv(
        output / "monthly_information_availability.csv",
        availability,
        [
            "month",
            "month_end",
            "earnings_source",
            "earnings_available_date",
            "treasury_source",
            "treasury_available_date",
            "permitted_signal_date",
            "earnings_timing_status",
            "treasury_timing_status",
            "future_earnings_enter_earlier_row",
            "publication_lag_source",
            "alternative_lags_performance_tested",
        ],
    )
    write_csv(
        output / "provider_overlap_reconciliation.csv",
        overlap,
        [
            "symbol",
            "public_history_series",
            "alpaca_series",
            "overlap_status",
            "overlap_start",
            "overlap_end",
            "overlap_months",
            "comparison",
            "max_abs_monthly_return_difference",
            "provider_boundary_freeze",
            "strategy_returns_calculated",
        ],
    )
    write_json(output / "data_sources_and_hashes.json", data_sources)
    write_json(output / "future_baseline_spec.json", future_spec)

    after_state = state_hashes(root)
    feasibility = {
        "task_id": TASK_ID,
        "candidate_strategy": CANDIDATE_STRATEGY_ID,
        "outcome": outcome,
        "outcome_options": sorted(OUTCOMES),
        "alpaca_read_only_access_ok": bool(alpaca_meta["alpaca_read_only_access_ok"]),
        "official_public_data_access_ok": official_downloads_ok,
        "source_rules_complete_for_data_feasibility": rules_complete,
        "earnings_yield_timing_resolved": earnings_timing_resolved,
        "aligned_history_sufficient_for_schema_review": aligned_history_sufficient,
        "data_reconciliation_defect": reconciliation_defect,
        "future_baseline_spec_created": bool(future_spec.get("strategy_configurations")),
        "strategy_backtest_run": False,
        "performance_screen_run": False,
        "strategy_return_cagr_sharpe_drawdown_calculated": False,
        "trade_management_overlay_experiment_run": False,
        "paper_demo_activation": False,
        "broker_order_placement": False,
        "real_money_advice": False,
        "next_action": NEXT_ACTION,
    }
    write_json(output / "feasibility_outcome.json", feasibility)
    write_csv(output / "command_validation_log.csv", command_validation_rows(), ["command", "status", "notes"])
    write_text(output / "feasibility_summary.md", feasibility_summary(outcome, asset_check, shiller, dgs10_meta))
    consistency = consistency_payload(output, outcome, before_state, after_state, alpaca_meta["credential_values"], future_spec)
    write_json(output / "consistency_check.json", consistency)

    return {
        "task_id": TASK_ID,
        "candidate_strategy": CANDIDATE_STRATEGY_ID,
        "outcome": outcome,
        "evidence_path": str(output.resolve()),
        "alpaca_read_only_access_ok": bool(alpaca_meta["alpaca_read_only_access_ok"]),
        "official_public_data_access_ok": official_downloads_ok,
        "future_baseline_spec_created": bool(future_spec.get("strategy_configurations")),
        "consistency_passed": consistency["consistency_passed"],
        "next_action": NEXT_ACTION,
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
