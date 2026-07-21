from __future__ import annotations

import csv
import hashlib
import json
import math
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import pandas as pd
import requests

from execution_lab.alpaca_micro_live_v1.adapters.credentials import (
    LIVE_KEY,
    LIVE_SECRET,
    PAPER_KEY,
    PAPER_SECRET,
    load_alpaca_credentials,
)


ROOT = Path(__file__).resolve().parents[3]
TASK_ID = "currency_momentum_alpaca_data_and_overlay_readiness_v1"
SOURCE_EXACT_ID = "deutsche_bank_g10_currency_momentum_top3_bottom3_12m_forward_v1"
SPOT_PROXY_ID = "currency_momentum_g10_top3_bottom3_12m_alpaca_spot_proxy_v1"
ADAPTATION_LABEL = "data_feasibility_adjustment"
OUTPUT_DIR = (
    Path("evidence")
    / "public_source_strategy_intake"
    / "currency_momentum_factor"
    / "alpaca_data_and_overlay_readiness_v1"
    / "latest"
)
RAW_CACHE_DIR = Path("data") / "raw" / "alpaca_forex_rates" / TASK_ID
REQUEST_START_DATE = "1970-01-01"
REQUEST_END_DATE = "2026-07-21"
ALPACA_FOREX_RATES_ENDPOINT = "https://data.alpaca.markets/v1beta1/forex/rates"
NEXT_ACTION = "direction_owner_review_currency_momentum_alpaca_data_and_overlay_readiness_v1"

REQUIRED_CURRENCIES = ["USD", "EUR", "JPY", "GBP", "CHF", "AUD", "NZD", "CAD", "NOK", "SEK"]
PAIR_DEFINITIONS: list[dict[str, Any]] = [
    {"currency": "EUR", "pair": "EURUSD", "quote_direction": "direct", "normalized_description": "EURUSD is USD per EUR."},
    {"currency": "GBP", "pair": "GBPUSD", "quote_direction": "direct", "normalized_description": "GBPUSD is USD per GBP."},
    {"currency": "AUD", "pair": "AUDUSD", "quote_direction": "direct", "normalized_description": "AUDUSD is USD per AUD."},
    {"currency": "NZD", "pair": "NZDUSD", "quote_direction": "direct", "normalized_description": "NZDUSD is USD per NZD."},
    {"currency": "JPY", "pair": "USDJPY", "quote_direction": "inverse", "normalized_description": "USDJPY is inverted to USD per JPY."},
    {"currency": "CHF", "pair": "USDCHF", "quote_direction": "inverse", "normalized_description": "USDCHF is inverted to USD per CHF."},
    {"currency": "CAD", "pair": "USDCAD", "quote_direction": "inverse", "normalized_description": "USDCAD is inverted to USD per CAD."},
    {"currency": "NOK", "pair": "USDNOK", "quote_direction": "inverse", "normalized_description": "USDNOK is inverted to USD per NOK."},
    {"currency": "SEK", "pair": "USDSEK", "quote_direction": "inverse", "normalized_description": "USDSEK is inverted to USD per SEK."},
]
PAIR_BY_ID = {row["pair"]: row for row in PAIR_DEFINITIONS}

PROTECTED_STATE_PATHS = [
    Path("strategy_lab") / "strategy_registry.yaml",
    Path("strategy_lab") / "research_os" / "research" / "research_queue.yaml",
    Path("strategy_lab") / "research_os" / "family_lineage" / "family_ledger.yaml",
    Path("strategy_lab") / "research_os" / "operations" / "active_observations.yaml",
]

OFFICIAL_FED_COUNTRIES = {
    "EUR": "Euro Area",
    "GBP": "United Kingdom",
    "AUD": "Australia",
    "NZD": "New Zealand",
    "JPY": "Japan",
    "CHF": "Switzerland",
    "CAD": "Canada",
    "NOK": "Norway",
    "SEK": "Sweden",
}
FED_DIRECT_CURRENCIES = {"EUR", "GBP", "AUD", "NZD"}


@dataclass(frozen=True)
class PairHistory:
    requested_pair: str
    returned_pair_identifier: str
    records: list[dict[str, Any]]
    pages: int
    status: str
    error: str
    loaded_from_cache: bool
    cache_path: Path
    cache_hash: str
    request_metadata: dict[str, Any]


def abs_path(root: Path, path: Path) -> Path:
    return path if path.is_absolute() else root / path


def clean_output_dir(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    for path in output.iterdir():
        if path.is_file():
            path.unlink()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def sha256_path(path: Path) -> str:
    if not path.exists():
        return "missing"
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def stable_payload_hash(payload: Any) -> str:
    return sha256_text(stable_json(payload))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, tuple, set)):
        return "|".join(str(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True, default=str)
    if isinstance(value, float):
        if math.isnan(value):
            return ""
        return repr(value)
    return str(value)


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: csv_value(row.get(field, "")) for field in fieldnames})


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def normalize_pair_rate(pair: str, raw_rate: float) -> float:
    pair_info = PAIR_BY_ID[pair]
    if raw_rate <= 0 or not math.isfinite(raw_rate):
        raise ValueError(f"{pair} raw rate must be positive and finite")
    if pair_info["quote_direction"] == "direct":
        return float(raw_rate)
    return float(1.0 / raw_rate)


def usd_momentum_signal() -> float:
    return 0.0


def pair_map_rows() -> list[dict[str, Any]]:
    rows = [
        {
            "currency": "USD",
            "alpaca_pair": "not_applicable",
            "source_role": "eligible_currency_member",
            "required": True,
            "quote_direction": "base_currency",
            "normalization_rule": "constant USD member; momentum signal fixed at 0.0",
            "included_in_rank": True,
        }
    ]
    for row in PAIR_DEFINITIONS:
        rows.append(
            {
                "currency": row["currency"],
                "alpaca_pair": row["pair"],
                "source_role": "non_usd_currency_pair",
                "required": True,
                "quote_direction": row["quote_direction"],
                "normalization_rule": row["normalized_description"],
                "included_in_rank": True,
            }
        )
    return rows


def quote_normalization_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in PAIR_DEFINITIONS:
        formula = "normalized_rate = raw_rate" if row["quote_direction"] == "direct" else "normalized_rate = 1 / raw_rate"
        rows.append(
            {
                "currency": row["currency"],
                "alpaca_pair": row["pair"],
                "raw_quote_convention": row["quote_direction"],
                "canonical_normalized_series": "USD per 1 unit of foreign currency",
                "normalization_formula": formula,
                "example": row["normalized_description"],
                "deterministic": True,
            }
        )
    rows.append(
        {
            "currency": "USD",
            "alpaca_pair": "not_applicable",
            "raw_quote_convention": "base_currency",
            "canonical_normalized_series": "USD member of ten-currency universe",
            "normalization_formula": "USD momentum = 0.0; no exchange-rate series is constructed",
            "example": "USD remains eligible for top-three or bottom-three ranking.",
            "deterministic": True,
        }
    )
    return rows


def sanitized_credential_review(root: Path) -> dict[str, Any]:
    credentials = load_alpaca_credentials("paper")
    source_kind = "none"
    if credentials.source == "environment":
        source_kind = "environment"
    elif credentials.source != "none":
        source_kind = "local_env_file"
    return {
        "paper_credentials_present": credentials.present,
        "credential_source_kind": source_kind,
        "credential_env_vars": [PAPER_KEY, PAPER_SECRET],
        "live_credential_env_vars_checked": [LIVE_KEY, LIVE_SECRET],
        "live_credentials_detected": credentials.live_credentials_detected,
        "api_secrets_persisted": False,
        "masked_credentials_written": False,
        "raw_credential_source_path_written": False,
    }


def repository_capability_review(root: Path) -> dict[str, Any]:
    files = {
        "credentials_helper": "execution_lab/alpaca_micro_live_v1/adapters/credentials.py",
        "alpaca_client": "execution_lab/alpaca_micro_live_v1/adapters/alpaca_client.py",
        "stock_bar_fetcher": "execution_lab/alpaca_micro_live_v1/data/alpaca_historical_bars.py",
        "runtime_cache": "execution_lab/alpaca_micro_live_v1/data/alpaca_runtime_cache.py",
        "overlay_module": "src/overlays.py",
        "trade_management_policy": "docs/trade_management_research_policy.md",
        "overlay_architecture": "docs/trade_management_overlay_architecture.md",
    }
    return {
        "task_id": TASK_ID,
        "alpaca_preferred_primary_data_source": True,
        "read_only_auth_helper_reused": True,
        "provider_adapter_files_inspected": files,
        "existing_stock_bar_support": (root / files["stock_bar_fetcher"]).exists(),
        "existing_forex_rate_endpoint_support": False,
        "new_capability_added_by_this_task": "minimal_read_only_historical_forex_rates_fetch_for_feasibility",
        "paper_credentials_integration": sanitized_credential_review(root),
        "provider_cache_convention": {
            "raw_cache_dir": str(abs_path(root, RAW_CACHE_DIR)),
            "cache_contains_raw_alpaca_response_pages": True,
            "cache_replay_supported": True,
        },
        "missing_capabilities_before_task": [
            "historical forex rates request helper",
            "forex-rate pagination capture",
            "G10 quote normalization inventory",
            "monthly common FX calendar validation",
            "official public-source reconciliation packet",
        ],
        "broker_order_paths_touched": False,
        "paper_or_live_order_capability_added": False,
    }


def endpoint_schema_review() -> dict[str, Any]:
    return {
        "official_provider": "Alpaca",
        "official_documentation_url": "https://docs.alpaca.markets/us/reference/rates-1",
        "endpoint": ALPACA_FOREX_RATES_ENDPOINT,
        "http_method": "GET",
        "path": "/v1beta1/forex/rates",
        "required_parameters": ["currency_pairs"],
        "supported_timeframes_documented": ["5Sec", "1Min", "1Day"],
        "task_timeframe": "1Day",
        "date_parameters": ["start", "end"],
        "pagination_parameter": "page_token",
        "pagination_response_field": "next_page_token",
        "documented_limit_range": "1 to 10000",
        "auth_required": True,
        "known_response_fields": {
            "timestamp": "t or timestamp/time field from provider payload",
            "rate": "r or rate field from provider payload",
        },
        "rate_definition_limit": (
            "Repository-inspected Alpaca endpoint documentation identifies historical forex rates, "
            "but does not make bid/ask/midpoint/executable-status explicit enough to treat the series as executable FX prices."
        ),
        "task_interpretation": "spot proxy data feasibility only; not a source-exact forward-index replication",
    }


def extract_rate_records(payload: dict[str, Any], requested_pair: str) -> tuple[str, list[dict[str, Any]], list[str]]:
    records_container: Any = payload.get("rates", payload.get("data", payload))
    returned_pair = requested_pair
    if isinstance(records_container, dict):
        for key in [requested_pair, requested_pair.replace("/", ""), f"{requested_pair[:3]}/{requested_pair[3:]}"]:
            if key in records_container:
                returned_pair = key
                records_container = records_container[key]
                break
    if not isinstance(records_container, list):
        return returned_pair, [], []

    extracted: list[dict[str, Any]] = []
    fieldnames: set[str] = set()
    for item in records_container:
        if not isinstance(item, dict):
            continue
        fieldnames.update(str(key) for key in item.keys())
        timestamp = item.get("t") or item.get("timestamp") or item.get("time")
        raw_rate = item.get("r")
        if raw_rate is None:
            raw_rate = item.get("rate")
        if raw_rate is None:
            raw_rate = item.get("c")
        if timestamp is None or raw_rate is None:
            continue
        try:
            rate = float(raw_rate)
        except (TypeError, ValueError):
            continue
        extracted.append({"timestamp": str(timestamp), "raw_rate": rate, "provider_fields": sorted(item.keys())})
    return returned_pair, extracted, sorted(fieldnames)


def cache_path_for_pair(root: Path, pair: str) -> Path:
    return abs_path(root, RAW_CACHE_DIR) / f"{pair}.json"


def fetch_pair_history(
    root: Path,
    pair: str,
    *,
    use_cache: bool = True,
    refresh: bool = False,
    session: requests.Session | None = None,
) -> PairHistory:
    cache_path = cache_path_for_pair(root, pair)
    request_metadata = {
        "endpoint": ALPACA_FOREX_RATES_ENDPOINT,
        "method": "GET",
        "currency_pairs": pair,
        "timeframe": "1Day",
        "start": REQUEST_START_DATE,
        "end": REQUEST_END_DATE,
        "limit": 10000,
        "sort": "asc",
    }
    if use_cache and cache_path.exists() and not refresh:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
        return PairHistory(
            requested_pair=pair,
            returned_pair_identifier=str(payload.get("returned_pair_identifier", pair)),
            records=list(payload.get("records", [])),
            pages=int(payload.get("pages", 0)),
            status=str(payload.get("status", "loaded_from_cache")),
            error=str(payload.get("error", "")),
            loaded_from_cache=True,
            cache_path=cache_path,
            cache_hash=sha256_path(cache_path),
            request_metadata=dict(payload.get("request_metadata", request_metadata)),
        )

    credentials = load_alpaca_credentials("paper")
    if not credentials.present:
        return PairHistory(
            requested_pair=pair,
            returned_pair_identifier=pair,
            records=[],
            pages=0,
            status="auth_blocked",
            error="Alpaca paper API credentials are missing.",
            loaded_from_cache=False,
            cache_path=cache_path,
            cache_hash="missing",
            request_metadata=request_metadata,
        )

    http = session or requests.Session()
    headers = {
        "APCA-API-KEY-ID": credentials.api_key or "",
        "APCA-API-SECRET-KEY": credentials.secret_key or "",
        "Accept": "application/json",
    }
    page_token: str | None = None
    all_records: list[dict[str, Any]] = []
    returned_pair = pair
    returned_fields: set[str] = set()
    raw_pages: list[dict[str, Any]] = []
    status = "ok"
    error = ""
    page_count = 0

    while True:
        params: dict[str, Any] = {
            "currency_pairs": pair,
            "timeframe": "1Day",
            "start": REQUEST_START_DATE,
            "end": REQUEST_END_DATE,
            "limit": 10000,
            "sort": "asc",
        }
        if page_token:
            params["page_token"] = page_token
        try:
            response = http.get(ALPACA_FOREX_RATES_ENDPOINT, params=params, headers=headers, timeout=30)
        except requests.RequestException as exc:
            status = "request_error"
            error = str(exc)
            break
        page_count += 1
        try:
            page_payload = response.json() if response.text else {}
        except ValueError:
            page_payload = {"raw_text": response.text[:200]}
        raw_pages.append({"status_code": response.status_code, "payload": page_payload})
        if response.status_code == 401 or response.status_code == 403:
            status = "auth_blocked"
            error = f"Alpaca endpoint returned HTTP {response.status_code}."
            break
        if response.status_code == 429:
            status = "rate_limited"
            error = "Alpaca endpoint returned HTTP 429 rate limit."
            break
        if not (200 <= response.status_code < 300):
            status = "provider_error"
            message = page_payload.get("message") if isinstance(page_payload, dict) else ""
            error = f"Alpaca endpoint returned HTTP {response.status_code}: {message}"
            break
        page_pair, records, fields = extract_rate_records(page_payload, pair)
        returned_pair = page_pair or returned_pair
        returned_fields.update(fields)
        all_records.extend(records)
        page_token = str(page_payload.get("next_page_token") or "") if isinstance(page_payload, dict) else ""
        if not page_token:
            break

    if not all_records and status == "ok":
        status = "no_records"
        error = "Alpaca returned no parseable historical forex-rate records."

    cache_payload = {
        "schema_version": 1,
        "provider": "alpaca",
        "task_id": TASK_ID,
        "requested_pair": pair,
        "returned_pair_identifier": returned_pair,
        "status": status,
        "error": error,
        "request_metadata": request_metadata,
        "pages": page_count,
        "returned_data_fields": sorted(returned_fields),
        "records": all_records,
        "raw_response_pages": raw_pages,
        "secrets_included": False,
    }
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(cache_payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")

    return PairHistory(
        requested_pair=pair,
        returned_pair_identifier=returned_pair,
        records=all_records,
        pages=page_count,
        status=status,
        error=error,
        loaded_from_cache=False,
        cache_path=cache_path,
        cache_hash=sha256_path(cache_path),
        request_metadata=request_metadata,
    )


def canonical_daily_records(history: PairHistory) -> list[dict[str, Any]]:
    pair = history.requested_pair
    canonical: list[dict[str, Any]] = []
    seen: set[str] = set()
    for record in history.records:
        timestamp = pd.Timestamp(record["timestamp"])
        if timestamp.tzinfo is None:
            timestamp = timestamp.tz_localize("UTC")
        else:
            timestamp = timestamp.tz_convert("UTC")
        timestamp_iso = timestamp.isoformat()
        raw_rate = float(record["raw_rate"])
        normalized = normalize_pair_rate(pair, raw_rate)
        duplicate = timestamp_iso in seen
        seen.add(timestamp_iso)
        canonical.append(
            {
                "pair": pair,
                "currency": PAIR_BY_ID[pair]["currency"],
                "timestamp": timestamp_iso,
                "date": timestamp.date().isoformat(),
                "raw_rate": raw_rate,
                "normalized_rate": normalized,
                "duplicate_timestamp": duplicate,
            }
        )
    canonical.sort(key=lambda row: row["timestamp"])
    return canonical


def canonical_series_hash(rows: list[dict[str, Any]]) -> str:
    canonical = [
        {
            "pair": row["pair"],
            "timestamp": row["timestamp"],
            "normalized_rate": round(float(row["normalized_rate"]), 12),
        }
        for row in rows
    ]
    return stable_payload_hash(canonical)


def coverage_row(history: PairHistory) -> dict[str, Any]:
    canonical = canonical_daily_records(history) if history.records else []
    timestamps = [row["timestamp"] for row in canonical]
    duplicates = sum(1 for row in canonical if row["duplicate_timestamp"])
    nulls = sum(1 for record in history.records if record.get("raw_rate") is None or record.get("timestamp") is None)
    provider_fields = sorted({field for record in history.records for field in record.get("provider_fields", [])})
    return {
        "requested_pair": history.requested_pair,
        "returned_pair_identifier": history.returned_pair_identifier,
        "earliest_available_timestamp": min(timestamps) if timestamps else "",
        "latest_available_timestamp": max(timestamps) if timestamps else "",
        "observation_frequency": "1Day",
        "number_of_observations": len(canonical),
        "returned_data_fields": provider_fields,
        "null_values": nulls,
        "duplicate_timestamps": duplicates,
        "time_zone": "UTC_normalized_from_provider_timestamp",
        "pagination_complete": history.status in {"ok", "loaded_from_cache"},
        "pagination_pages": history.pages,
        "rate_construction_description": "Alpaca official endpoint returns historical forex rates; bid/ask/midpoint/executable-status not explicit in inspected endpoint documentation.",
        "value_definition": "historical forex rate",
        "historical_values_revised_policy": "not established by this repository inspection",
        "provider_request_metadata": history.request_metadata,
        "cache_path": str(history.cache_path),
        "file_hash": history.cache_hash,
        "canonical_normalized_series_hash": canonical_series_hash(canonical) if canonical else "missing",
        "status": history.status,
        "error": history.error,
        "loaded_from_cache": history.loaded_from_cache,
    }


def monthly_common_calendar(canonical_by_pair: dict[str, list[dict[str, Any]]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    monthly_by_pair: dict[str, dict[str, dict[str, Any]]] = {}
    for pair, rows in canonical_by_pair.items():
        pair_months: dict[str, dict[str, Any]] = {}
        for row in rows:
            month = row["date"][:7]
            current = pair_months.get(month)
            if current is None or row["timestamp"] > current["timestamp"]:
                pair_months[month] = row
        monthly_by_pair[pair] = pair_months

    all_months = sorted({month for months in monthly_by_pair.values() for month in months})
    coverage_rows: list[dict[str, Any]] = []
    gap_rows: list[dict[str, Any]] = []
    required_pairs = [row["pair"] for row in PAIR_DEFINITIONS]
    for month in all_months:
        missing_pairs = [pair for pair in required_pairs if month not in monthly_by_pair.get(pair, {})]
        missing_currencies = [PAIR_BY_ID[pair]["currency"] for pair in missing_pairs]
        present_pairs = [pair for pair in required_pairs if month in monthly_by_pair.get(pair, {})]
        complete = not missing_pairs
        coverage_rows.append(
            {
                "month": month,
                "complete_nine_pair_coverage": complete,
                "present_pair_count": len(present_pairs),
                "missing_pair_count": len(missing_pairs),
                "missing_pairs": missing_pairs,
                "missing_currencies": missing_currencies,
                "month_end_selection_rule": "final available Alpaca observation inside calendar month",
                "forward_filled": False,
                "interpolated": False,
                "synthetic_history_created": False,
            }
        )
        if missing_pairs:
            gap_rows.append(
                {
                    "month": month,
                    "missing_pairs": missing_pairs,
                    "missing_currencies": missing_currencies,
                    "gap_handling": "reported_not_filled",
                }
            )

    complete_months = [row["month"] for row in coverage_rows if row["complete_nine_pair_coverage"]]
    summary = {
        "earliest_complete_month": complete_months[0] if complete_months else "",
        "latest_complete_month": complete_months[-1] if complete_months else "",
        "complete_month_count": len(complete_months),
        "incomplete_month_count": len(gap_rows),
        "has_at_least_13_complete_months": len(complete_months) >= 13,
        "meaningful_multi_year_12m_momentum_experiment_possible": len(complete_months) >= 60,
        "sample_includes_multiple_market_regimes": len(complete_months) >= 84,
        "no_forward_fill": True,
        "no_interpolation": True,
        "no_synthetic_history": True,
    }
    return coverage_rows, gap_rows, summary


def monthly_dates_strictly_increasing(rows: list[dict[str, Any]]) -> bool:
    months = [row["month"] for row in rows]
    return months == sorted(months) and len(months) == len(set(months))


def duplicate_dates_rejected(canonical_rows: list[dict[str, Any]]) -> bool:
    return not any(row.get("duplicate_timestamp") for row in canonical_rows)


def discover_fed_h10_country_urls(session: requests.Session | None = None) -> dict[str, str]:
    http = session or requests.Session()
    base = "https://www.federalreserve.gov/releases/h10/hist/"
    try:
        response = http.get(base, timeout=30)
    except requests.RequestException:
        return {}
    if not (200 <= response.status_code < 300):
        return {}
    text = response.text
    urls: dict[str, str] = {}
    for currency, country in OFFICIAL_FED_COUNTRIES.items():
        pattern = re.compile(r'href="([^"]+)">\s*' + re.escape(country) + r"\s*</a>", re.IGNORECASE)
        match = pattern.search(text)
        if match:
            urls[currency] = urljoin(base, match.group(1))
    return urls


def parse_fed_h10_rates(html: str, currency: str) -> dict[str, float]:
    rates: dict[str, float] = {}
    for match in re.finditer(r"(\d{4}-\d{2}-\d{2})\s+([0-9.]+|ND)", html):
        day, raw_value = match.groups()
        if raw_value == "ND":
            continue
        value = float(raw_value)
        normalized = value if currency in FED_DIRECT_CURRENCIES else 1.0 / value
        rates[day] = normalized
    return rates


def fetch_fed_h10_rates(session: requests.Session | None = None) -> dict[str, dict[str, float]]:
    http = session or requests.Session()
    urls = discover_fed_h10_country_urls(http)
    data: dict[str, dict[str, float]] = {}
    for currency, url in urls.items():
        try:
            response = http.get(url, timeout=30)
        except requests.RequestException:
            data[currency] = {}
            continue
        if 200 <= response.status_code < 300:
            data[currency] = parse_fed_h10_rates(response.text, currency)
        else:
            data[currency] = {}
    return data


def sample_complete_months(coverage_rows: list[dict[str, Any]], max_samples: int = 5) -> list[str]:
    complete = [row["month"] for row in coverage_rows if row.get("complete_nine_pair_coverage")]
    if not complete:
        return []
    if len(complete) <= max_samples:
        return complete
    indexes = [0, len(complete) // 4, len(complete) // 2, (3 * len(complete)) // 4, len(complete) - 1]
    months: list[str] = []
    for index in indexes:
        month = complete[index]
        if month not in months:
            months.append(month)
    return months


def monthly_last_obs_by_pair(canonical_by_pair: dict[str, list[dict[str, Any]]]) -> dict[str, dict[str, dict[str, Any]]]:
    output: dict[str, dict[str, dict[str, Any]]] = {}
    for pair, rows in canonical_by_pair.items():
        output[pair] = {}
        for row in rows:
            month = row["date"][:7]
            current = output[pair].get(month)
            if current is None or row["timestamp"] > current["timestamp"]:
                output[pair][month] = row
    return output


def previous_month(month: str) -> str:
    year, mon = [int(part) for part in month.split("-")]
    if mon == 1:
        return f"{year - 1:04d}-12"
    return f"{year:04d}-{mon - 1:02d}"


def official_rate_for_date(fed_rates: dict[str, float], target_date: str) -> tuple[str, float | None, str]:
    if target_date in fed_rates:
        return target_date, fed_rates[target_date], "same_date"
    target = pd.Timestamp(target_date)
    for lag in range(1, 8):
        prior = (target - pd.Timedelta(days=lag)).date().isoformat()
        if prior in fed_rates:
            return prior, fed_rates[prior], f"prior_official_date_lag_{lag}_calendar_days"
    return "", None, "official_date_missing_within_7_calendar_days"


def reconciliation_rows(
    canonical_by_pair: dict[str, list[dict[str, Any]]],
    coverage_rows: list[dict[str, Any]],
    *,
    session: requests.Session | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    monthly_by_pair = monthly_last_obs_by_pair(canonical_by_pair)
    fed_by_currency = fetch_fed_h10_rates(session)
    sample_months = sample_complete_months(coverage_rows)
    rows: list[dict[str, Any]] = []
    statuses: list[str] = []
    for pair_info in PAIR_DEFINITIONS:
        pair = pair_info["pair"]
        currency = pair_info["currency"]
        fed_rates = fed_by_currency.get(currency, {})
        for month in sample_months:
            alpaca_row = monthly_by_pair.get(pair, {}).get(month)
            if alpaca_row is None:
                status = "insufficient_overlap"
                rows.append(
                    {
                        "pair": pair,
                        "currency": currency,
                        "sample_month": month,
                        "alpaca_observation_date": "",
                        "official_observation_date": "",
                        "quote_direction_checked": pair_info["quote_direction"],
                        "alpaca_normalized_usd_per_foreign": "",
                        "official_normalized_usd_per_foreign": "",
                        "absolute_difference": "",
                        "percentage_difference": "",
                        "month_over_month_return_difference": "",
                        "missing_date_behavior": "alpaca_month_missing",
                        "reconciliation_status": status,
                    }
                )
                statuses.append(status)
                continue
            fed_date, fed_rate, missing_behavior = official_rate_for_date(fed_rates, alpaca_row["date"])
            if fed_rate is None:
                status = "insufficient_overlap"
                rows.append(
                    {
                        "pair": pair,
                        "currency": currency,
                        "sample_month": month,
                        "alpaca_observation_date": alpaca_row["date"],
                        "official_observation_date": fed_date,
                        "quote_direction_checked": pair_info["quote_direction"],
                        "alpaca_normalized_usd_per_foreign": alpaca_row["normalized_rate"],
                        "official_normalized_usd_per_foreign": "",
                        "absolute_difference": "",
                        "percentage_difference": "",
                        "month_over_month_return_difference": "",
                        "missing_date_behavior": missing_behavior,
                        "reconciliation_status": status,
                    }
                )
                statuses.append(status)
                continue
            abs_diff = float(alpaca_row["normalized_rate"]) - float(fed_rate)
            pct_diff = abs_diff / float(fed_rate) if fed_rate else math.nan
            prev = previous_month(month)
            alpaca_prev = monthly_by_pair.get(pair, {}).get(prev)
            fed_prev_date, fed_prev_rate, _ = official_rate_for_date(fed_rates, alpaca_prev["date"]) if alpaca_prev else ("", None, "")
            mom_diff = ""
            if alpaca_prev is not None and fed_prev_rate:
                alpaca_mom = float(alpaca_row["normalized_rate"]) / float(alpaca_prev["normalized_rate"]) - 1.0
                fed_mom = float(fed_rate) / float(fed_prev_rate) - 1.0
                mom_diff = alpaca_mom - fed_mom
            if abs(pct_diff) <= 0.005:
                status = "consistent_with_official_public_source"
            elif abs(pct_diff) <= 0.02:
                status = "consistent_with_documented_timing_differences"
            else:
                status = "materially_inconsistent"
            rows.append(
                {
                    "pair": pair,
                    "currency": currency,
                    "sample_month": month,
                    "alpaca_observation_date": alpaca_row["date"],
                    "official_observation_date": fed_date,
                    "quote_direction_checked": pair_info["quote_direction"],
                    "alpaca_normalized_usd_per_foreign": alpaca_row["normalized_rate"],
                    "official_normalized_usd_per_foreign": fed_rate,
                    "absolute_difference": abs_diff,
                    "percentage_difference": pct_diff,
                    "month_over_month_return_difference": mom_diff,
                    "missing_date_behavior": missing_behavior,
                    "reconciliation_status": status,
                    "official_prev_observation_date_for_mom": fed_prev_date,
                }
            )
            statuses.append(status)
    summary = {
        "official_source": "Federal Reserve H.10 bilateral exchange rates",
        "official_source_url": "https://www.federalreserve.gov/releases/h10/hist/",
        "sample_months": sample_months,
        "reconciliation_rows": len(rows),
        "status_counts": {status: statuses.count(status) for status in sorted(set(statuses))},
        "materially_inconsistent_rows": statuses.count("materially_inconsistent"),
        "insufficient_overlap_rows": statuses.count("insufficient_overlap"),
    }
    return rows, summary


def determine_outcome(
    histories: dict[str, PairHistory],
    monthly_summary: dict[str, Any],
    reconciliation_summary: dict[str, Any],
) -> str:
    statuses = [history.status for history in histories.values()]
    present_pairs = [pair for pair, history in histories.items() if history.records and history.status in {"ok", "loaded_from_cache"}]
    if not present_pairs and any(status == "auth_blocked" for status in statuses):
        return "alpaca_access_or_auth_blocked"
    if len(present_pairs) < len(PAIR_DEFINITIONS):
        return "alpaca_pair_coverage_incomplete"
    if not monthly_summary.get("has_at_least_13_complete_months", False):
        return "alpaca_history_too_short"
    if reconciliation_summary.get("materially_inconsistent_rows", 0):
        return "alpaca_data_materially_inconsistent"
    if reconciliation_summary.get("insufficient_overlap_rows", 0):
        return "alpaca_ready_with_public_reconciliation_limits"
    return "alpaca_ready_with_public_reconciliation_limits"


def source_identity_and_lineage() -> dict[str, Any]:
    return {
        "task_id": TASK_ID,
        "task_type": "data-acquisition-or-capability",
        "stage": "feasibility",
        "primary_adaptation_label": ADAPTATION_LABEL,
        "public_page": "https://quantpedia.com/strategies/currency-momentum-factor",
        "source_exact_target_identity": SOURCE_EXACT_ID,
        "alpaca_public_spot_proxy_identity": SPOT_PROXY_ID,
        "relationship": {
            "deutsche_bank_strategy": "source-exact forward implementation target",
            "alpaca_strategy": "exploratory public spot proxy",
            "not_a_forward_index_replication": True,
            "excludes_forward_carry": True,
            "excludes_historical_bid_ask_spreads": True,
            "excludes_collateral_return": True,
            "excludes_contract_rolls": True,
        },
        "source_defined_universe": REQUIRED_CURRENCIES,
        "non_usd_alpaca_pairs": [row["pair"] for row in PAIR_DEFINITIONS],
        "do_not_rename_proxy_as_deutsche_bank_strategy": True,
    }


def source_exact_vs_spot_proxy_rows() -> list[dict[str, Any]]:
    return [
        {
            "dimension": "identity",
            "source_exact_forward_strategy": SOURCE_EXACT_ID,
            "alpaca_spot_proxy": SPOT_PROXY_ID,
            "interpretation": "separate identities preserved",
        },
        {
            "dimension": "instrument",
            "source_exact_forward_strategy": "G10 currency forward index construction",
            "alpaca_spot_proxy": "Alpaca spot forex-rate histories",
            "interpretation": "spot proxy does not replicate forwards",
        },
        {
            "dimension": "carry_collateral_rolls",
            "source_exact_forward_strategy": "forward carry/collateral/roll effects may be embedded in source-exact implementation",
            "alpaca_spot_proxy": "no forward carry, no collateral return, no roll accounting",
            "interpretation": "family data feasibility adjustment only",
        },
        {
            "dimension": "execution",
            "source_exact_forward_strategy": "not built in this task",
            "alpaca_spot_proxy": "not backtested in this task",
            "interpretation": "feasibility only",
        },
    ]


def build_frozen_baseline_spec(outcome: str, monthly_summary: dict[str, Any]) -> dict[str, Any]:
    data_ready = outcome in {"alpaca_primary_data_ready_for_spot_proxy", "alpaca_ready_with_public_reconciliation_limits"}
    if not data_ready:
        return {
            "spec_created": False,
            "reason": outcome,
            "strategy_configurations": [],
            "performance_backtest_authorized": False,
        }
    return {
        "spec_created": True,
        "strategy_configurations": [
            {
                "strategy_id": SPOT_PROXY_ID,
                "parent_source_strategy": SOURCE_EXACT_ID,
                "adaptation_label": ADAPTATION_LABEL,
                "stage": "exploration",
                "universe": REQUIRED_CURRENCIES,
                "alpaca_pairs": [row["pair"] for row in PAIR_DEFINITIONS],
                "quote_convention": "USD per 1 unit of foreign currency",
                "usd_momentum_signal": usd_momentum_signal(),
                "signal": "trailing 12-month normalized spot return",
                "ranking": "rank all ten currencies monthly, including USD",
                "long_leg": "top three currencies, equal weight +1/3 each",
                "short_leg": "bottom three currencies, equal weight -1/3 each",
                "gross_exposure": "approximately 200 percent",
                "net_currency_exposure": "approximately zero",
                "signal_timestamp": "final common completed monthly observation",
                "return_window": "following month normalized spot-rate change only",
                "same_period_return_in_signal": False,
                "rebalance_frequency": "monthly",
                "collateral_return": "excluded",
                "overnight_cash_return": "excluded",
                "forward_carry": "excluded",
                "spread_or_transaction_cost_deduction": "not invented",
                "volatility_scaling": "none",
                "crash_filter": "none",
                "carry_filter": "none",
                "parameter_alternatives": "none",
                "available_month_window": {
                    "earliest_complete_month": monthly_summary.get("earliest_complete_month", ""),
                    "latest_complete_month": monthly_summary.get("latest_complete_month", ""),
                    "complete_month_count": monthly_summary.get("complete_month_count", 0),
                },
            }
        ],
        "required_baseline_controls": [
            "identity_no_position_control_where_appropriate",
            "zero_excess_return_reference",
            "equal_weight_long_short_neutrality_and_exposure_invariants",
            "gross_spot_return_interpretation",
        ],
        "performance_backtest_authorized": False,
        "paper_demo_activation_authorized": False,
    }


def overlay_compatibility_rows() -> list[dict[str, Any]]:
    return [
        {
            "overlay": "IdentityOverlay",
            "classification": "compatible_after_narrow_adapter",
            "negative_weights_supported": "requires_monthly_long_short_weight_path_adapter",
            "gross_200_percent_supported": "identity_can_preserve_if_adapter_accepts_weights",
            "net_zero_preserved": True,
            "usd_ranked_currency_handled": "base_strategy_responsibility",
            "assumes_long_only": False,
            "assumes_daily_ohlc": False,
            "requires_atr_or_instrument_prices": False,
            "changes_signal_selection": False,
            "can_evaluate_on_published_monthly_return_path": "only after baseline weight path is defined",
            "identity_equality_can_be_asserted": "yes_after_base_strategy_exists",
            "lower_exposure_control_possible_without_signal_change": "not_applicable",
        },
        {
            "overlay": "RebalanceBandOverlay",
            "classification": "compatible_after_narrow_adapter",
            "negative_weights_supported": "needs explicit support for signed monthly target weights",
            "gross_200_percent_supported": "possible if cap and accounting support signed gross exposure",
            "net_zero_preserved": "must be invariant-tested",
            "usd_ranked_currency_handled": "base_strategy_responsibility",
            "assumes_long_only": "not inherently, but current order-intent accounting must be checked",
            "assumes_daily_ohlc": False,
            "requires_atr_or_instrument_prices": False,
            "changes_signal_selection": False,
            "can_evaluate_on_published_monthly_return_path": "no, needs target-weight path and rebalancing intents",
            "identity_equality_can_be_asserted": "not an identity overlay",
            "lower_exposure_control_possible_without_signal_change": "not_directly",
        },
        {
            "overlay": "LaggedVolatilityTargetOverlay",
            "classification": "defer_until_base_strategy_verified",
            "negative_weights_supported": "unknown_for_signed_fx_weight_path",
            "gross_200_percent_supported": "would change gross exposure",
            "net_zero_preserved": "must be proven before testing",
            "usd_ranked_currency_handled": "base_strategy_responsibility",
            "assumes_long_only": "not source-compatible without a fixed signed scaling adapter",
            "assumes_daily_ohlc": False,
            "requires_atr_or_instrument_prices": "requires return history",
            "changes_signal_selection": False,
            "can_evaluate_on_published_monthly_return_path": "possible only as separate overlay trial after baseline verification",
            "identity_equality_can_be_asserted": "not an identity overlay",
            "lower_exposure_control_possible_without_signal_change": "yes_as_static_scale_control_before_dynamic_vol_target",
        },
        {
            "overlay": "ExposureCapsOverlay",
            "classification": "compatible_after_narrow_adapter",
            "negative_weights_supported": "needs signed exposure accounting",
            "gross_200_percent_supported": "cap must be configured not to silently break source gross exposure",
            "net_zero_preserved": "must be invariant-tested",
            "usd_ranked_currency_handled": "base_strategy_responsibility",
            "assumes_long_only": "possible current assumptions need audit",
            "assumes_daily_ohlc": False,
            "requires_atr_or_instrument_prices": False,
            "changes_signal_selection": False,
            "can_evaluate_on_published_monthly_return_path": "no, needs instrument-level signed weights",
            "identity_equality_can_be_asserted": "not an identity overlay",
            "lower_exposure_control_possible_without_signal_change": "yes_if_static_cap_config_is_frozen_pre_results",
        },
        {
            "overlay": "WideATRCatastrophicStopOverlay",
            "classification": "not_appropriate_for_monthly_long_short_fx",
            "negative_weights_supported": "unsupported_for_current_monthly_spot_proxy",
            "gross_200_percent_supported": "unsupported",
            "net_zero_preserved": "unlikely",
            "usd_ranked_currency_handled": "not applicable",
            "assumes_long_only": "position-lifecycle stop semantics are not a source-compatible monthly FX overlay by default",
            "assumes_daily_ohlc": True,
            "requires_atr_or_instrument_prices": True,
            "changes_signal_selection": "may force exits outside monthly source rule",
            "can_evaluate_on_published_monthly_return_path": False,
            "identity_equality_can_be_asserted": "not an identity overlay",
            "lower_exposure_control_possible_without_signal_change": "no",
        },
        {
            "overlay": "TimeStopOverlay",
            "classification": "not_appropriate_for_monthly_long_short_fx",
            "negative_weights_supported": "unsupported_for_current_monthly_spot_proxy",
            "gross_200_percent_supported": "unsupported",
            "net_zero_preserved": "could break monthly rank-hold rule",
            "usd_ranked_currency_handled": "not applicable",
            "assumes_long_only": "position-lifecycle trade stops are not the baseline mechanism",
            "assumes_daily_ohlc": False,
            "requires_atr_or_instrument_prices": False,
            "changes_signal_selection": True,
            "can_evaluate_on_published_monthly_return_path": False,
            "identity_equality_can_be_asserted": "not an identity overlay",
            "lower_exposure_control_possible_without_signal_change": "no",
        },
        {
            "overlay": "StaticScaleOverlay",
            "classification": "compatible_after_narrow_adapter",
            "negative_weights_supported": "needs signed weight scaling adapter",
            "gross_200_percent_supported": "intentionally creates lower-gross control when predeclared",
            "net_zero_preserved": "yes_if all signed weights are scaled symmetrically",
            "usd_ranked_currency_handled": "base_strategy_responsibility",
            "assumes_long_only": False,
            "assumes_daily_ohlc": False,
            "requires_atr_or_instrument_prices": False,
            "changes_signal_selection": False,
            "can_evaluate_on_published_monthly_return_path": "yes_if applied to frozen signed weight path",
            "identity_equality_can_be_asserted": "not an identity overlay",
            "lower_exposure_control_possible_without_signal_change": True,
        },
    ]


def concrete_blockers(outcome: str, coverage_rows: list[dict[str, Any]], monthly_summary: dict[str, Any], reconciliation_summary: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    if outcome == "alpaca_access_or_auth_blocked":
        blockers.append(
            {
                "blocker": "alpaca_access_or_auth_blocked",
                "detail": "No required pair had usable Alpaca records and at least one request was auth-blocked.",
                "specific_next_remediation": "authorize valid Alpaca paper market-data credentials or restore raw Alpaca forex cache",
            }
        )
    missing_pairs = sorted({row["requested_pair"] for row in coverage_rows if not row.get("number_of_observations")})
    if missing_pairs:
        blockers.append(
            {
                "blocker": "alpaca_pair_coverage_incomplete",
                "detail": f"Missing usable Alpaca observations for: {', '.join(missing_pairs)}",
                "specific_next_remediation": "verify Alpaca FX pair support or obtain direction-owner approval for a different official source",
            }
        )
    if outcome == "alpaca_history_too_short":
        blockers.append(
            {
                "blocker": "alpaca_history_too_short",
                "detail": f"Only {monthly_summary.get('complete_month_count', 0)} complete months were available.",
                "specific_next_remediation": "authorize a data source with enough G10 spot history for a 12-month signal",
            }
        )
    if outcome == "alpaca_data_materially_inconsistent":
        blockers.append(
            {
                "blocker": "alpaca_data_materially_inconsistent",
                "detail": f"{reconciliation_summary.get('materially_inconsistent_rows', 0)} reconciliation rows were materially inconsistent.",
                "specific_next_remediation": "manual review of Alpaca/Fed quote timing and field definitions",
            }
        )
    if outcome == "alpaca_ready_with_public_reconciliation_limits":
        blockers.append(
            {
                "blocker": "interpretation_limit_not_blocking",
                "detail": "Alpaca endpoint field definition and official-source timing differences must remain visible.",
                "specific_next_remediation": "direction-owner review before authorizing a spot-proxy baseline implementation",
            }
        )
    if not blockers:
        blockers.append(
            {
                "blocker": "none",
                "detail": "No concrete data blocker was identified by this feasibility packet.",
                "specific_next_remediation": NEXT_ACTION,
            }
        )
    return blockers


def state_hashes(root: Path) -> dict[str, str]:
    return {str(path): sha256_path(abs_path(root, path)) for path in PROTECTED_STATE_PATHS}


def no_secret_text_written(output: Path) -> bool:
    forbidden = [PAPER_KEY, PAPER_SECRET, LIVE_KEY, LIVE_SECRET]
    for path in output.iterdir():
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        # Environment variable names are allowed for auditability; actual values are not loaded here.
        for token in forbidden:
            text = text.replace(token, "")
        if "APCA-API-KEY-ID" in text or "APCA-API-SECRET-KEY" in text:
            return False
    return True


def build_summary_text(outcome: str, monthly_summary: dict[str, Any], reconciliation_summary: dict[str, Any]) -> str:
    spec_status = "created" if outcome in {"alpaca_primary_data_ready_for_spot_proxy", "alpaca_ready_with_public_reconciliation_limits"} else "not created"
    return f"""# Currency Momentum Alpaca Data And Overlay Readiness

Task: `{TASK_ID}`

This packet is a data-feasibility and overlay-onboarding readiness check only. It did not run the currency-momentum strategy, calculate strategy performance metrics, place orders, or modify paper/demo state.

## Outcome

Exact Alpaca feasibility outcome: `{outcome}`

Earliest complete nine-pair month: `{monthly_summary.get("earliest_complete_month", "")}`

Latest complete nine-pair month: `{monthly_summary.get("latest_complete_month", "")}`

Complete months: `{monthly_summary.get("complete_month_count", 0)}`

Incomplete months: `{monthly_summary.get("incomplete_month_count", 0)}`

At least 13 complete months: `{monthly_summary.get("has_at_least_13_complete_months", False)}`

Meaningful multi-year 12-month-momentum experiment possible: `{monthly_summary.get("meaningful_multi_year_12m_momentum_experiment_possible", False)}`

Reconciliation status counts: `{json.dumps(reconciliation_summary.get("status_counts", {}), sort_keys=True)}`

Frozen later baseline experiment specification: `{spec_status}`

## Interpretation Limits

The Alpaca proxy remains separate from `{SOURCE_EXACT_ID}`. It is a spot-rate proxy only and excludes forward carry, collateral return, historical bid-ask spreads, and contract-roll mechanics. USD remains a ranked universe member with a fixed zero momentum signal; if USD ranks in the top or bottom three in the later experiment, the corresponding leg represents selection of the base currency rather than an Alpaca pair.

## Trade-Management Sequence

The mandatory future order is base strategy first, then identity-overlay equality, then separately labeled compatible overlay trials. No overlay performance experiment was run here.

Exact next action: `{NEXT_ACTION}`
"""


def run(root: Path | None = None, *, refresh: bool = False, use_cache: bool = True) -> dict[str, Any]:
    root = root or ROOT
    output = abs_path(root, OUTPUT_DIR)
    clean_output_dir(output)
    before_hashes = state_hashes(root)

    histories: dict[str, PairHistory] = {}
    for pair_info in PAIR_DEFINITIONS:
        histories[pair_info["pair"]] = fetch_pair_history(root, pair_info["pair"], use_cache=use_cache, refresh=refresh)

    canonical_by_pair = {pair: canonical_daily_records(history) for pair, history in histories.items()}
    coverage_rows = [coverage_row(history) for history in histories.values()]
    monthly_rows, gap_rows, monthly_summary = monthly_common_calendar(canonical_by_pair)
    reconciliation, reconciliation_summary = reconciliation_rows(canonical_by_pair, monthly_rows)
    outcome = determine_outcome(histories, monthly_summary, reconciliation_summary)
    spec = build_frozen_baseline_spec(outcome, monthly_summary)
    blockers = concrete_blockers(outcome, coverage_rows, monthly_summary, reconciliation_summary)
    overlay_rows = overlay_compatibility_rows()

    source_identity = source_identity_and_lineage()
    repo_review = repository_capability_review(root)
    endpoint_review = endpoint_schema_review()
    after_hashes = state_hashes(root)

    data_hash_review = {
        "task_id": TASK_ID,
        "raw_cache_dir": str(abs_path(root, RAW_CACHE_DIR)),
        "provider": "Alpaca",
        "raw_cache_files": [
            {
                "pair": pair,
                "cache_path": str(history.cache_path),
                "cache_hash": history.cache_hash,
                "canonical_normalized_series_hash": row["canonical_normalized_series_hash"],
                "loaded_from_cache": history.loaded_from_cache,
            }
            for pair, history in histories.items()
            for row in coverage_rows
            if row["requested_pair"] == pair
        ],
        "api_secrets_included": False,
        "deterministic_cache_replay_supported": True,
    }

    feasibility_outcome = {
        "task_id": TASK_ID,
        "alpaca_data_feasibility_outcome": outcome,
        "outcome_options": [
            "alpaca_primary_data_ready_for_spot_proxy",
            "alpaca_ready_with_public_reconciliation_limits",
            "alpaca_history_too_short",
            "alpaca_pair_coverage_incomplete",
            "alpaca_rate_definition_inadequate",
            "alpaca_access_or_auth_blocked",
            "alpaca_data_materially_inconsistent",
        ],
        "decision_basis": {
            "all_required_pairs_present": all(int(row["number_of_observations"]) > 0 for row in coverage_rows),
            "quote_normalization_unambiguous": True,
            "complete_month_count": monthly_summary.get("complete_month_count", 0),
            "has_at_least_13_complete_months": monthly_summary.get("has_at_least_13_complete_months", False),
            "official_reconciliation_status_counts": reconciliation_summary.get("status_counts", {}),
            "rate_definition_limit_visible": True,
        },
        "selected_based_on_strategy_returns": False,
    }

    consistency = {
        "task_id": TASK_ID,
        "consistency_passed": True,
        "all_nine_non_usd_pair_mappings_present": len(PAIR_DEFINITIONS) == 9,
        "required_inverse_pairs_inverted": all(row["quote_direction"] == "inverse" for row in PAIR_DEFINITIONS if row["pair"].startswith("USD")),
        "direct_pairs_not_inverted": all(row["quote_direction"] == "direct" for row in PAIR_DEFINITIONS if row["pair"] in {"EURUSD", "GBPUSD", "AUDUSD", "NZDUSD"}),
        "usd_momentum_exactly_zero": usd_momentum_signal() == 0.0,
        "monthly_dates_strictly_increasing": monthly_dates_strictly_increasing(monthly_rows),
        "internal_gaps_reported_not_filled": all(row["gap_handling"] == "reported_not_filled" for row in gap_rows),
        "api_keys_logged_or_persisted": False,
        "strategy_return_cagr_sharpe_drawdown_calculated": False,
        "order_placement_or_broker_write_called": False,
        "bybit_or_crypto_source_used": False,
        "strategy_registry_changed": before_hashes.get(str(PROTECTED_STATE_PATHS[0])) != after_hashes.get(str(PROTECTED_STATE_PATHS[0])),
        "active_observations_changed": before_hashes.get(str(PROTECTED_STATE_PATHS[3])) != after_hashes.get(str(PROTECTED_STATE_PATHS[3])),
        "trade_management_performance_experiment_executed": False,
        "frozen_baseline_strategy_configuration_count": len(spec.get("strategy_configurations", [])),
        "next_action": NEXT_ACTION,
    }

    write_json(output / "source_identity_and_lineage.json", source_identity)
    write_json(output / "alpaca_repository_capability_review.json", repo_review)
    write_json(output / "alpaca_endpoint_and_schema_review.json", endpoint_review)
    write_csv(
        output / "required_currency_and_pair_map.csv",
        pair_map_rows(),
        ["currency", "alpaca_pair", "source_role", "required", "quote_direction", "normalization_rule", "included_in_rank"],
    )
    write_csv(
        output / "quote_normalization_map.csv",
        quote_normalization_rows(),
        ["currency", "alpaca_pair", "raw_quote_convention", "canonical_normalized_series", "normalization_formula", "example", "deterministic"],
    )
    write_csv(
        output / "alpaca_raw_coverage_inventory.csv",
        coverage_rows,
        [
            "requested_pair",
            "returned_pair_identifier",
            "earliest_available_timestamp",
            "latest_available_timestamp",
            "observation_frequency",
            "number_of_observations",
            "returned_data_fields",
            "null_values",
            "duplicate_timestamps",
            "time_zone",
            "pagination_complete",
            "pagination_pages",
            "rate_construction_description",
            "value_definition",
            "historical_values_revised_policy",
            "provider_request_metadata",
            "cache_path",
            "file_hash",
            "canonical_normalized_series_hash",
            "status",
            "error",
            "loaded_from_cache",
        ],
    )
    write_csv(
        output / "monthly_common_calendar_coverage.csv",
        monthly_rows,
        [
            "month",
            "complete_nine_pair_coverage",
            "present_pair_count",
            "missing_pair_count",
            "missing_pairs",
            "missing_currencies",
            "month_end_selection_rule",
            "forward_filled",
            "interpolated",
            "synthetic_history_created",
        ],
    )
    write_csv(output / "missing_months_and_currency_gaps.csv", gap_rows, ["month", "missing_pairs", "missing_currencies", "gap_handling"])
    write_csv(
        output / "public_source_reconciliation.csv",
        reconciliation,
        [
            "pair",
            "currency",
            "sample_month",
            "alpaca_observation_date",
            "official_observation_date",
            "quote_direction_checked",
            "alpaca_normalized_usd_per_foreign",
            "official_normalized_usd_per_foreign",
            "absolute_difference",
            "percentage_difference",
            "month_over_month_return_difference",
            "missing_date_behavior",
            "reconciliation_status",
            "official_prev_observation_date_for_mom",
        ],
    )
    write_json(output / "data_hash_and_provenance_review.json", data_hash_review)
    write_json(output / "alpaca_data_feasibility_outcome.json", feasibility_outcome)
    write_csv(
        output / "source_exact_vs_spot_proxy_map.csv",
        source_exact_vs_spot_proxy_rows(),
        ["dimension", "source_exact_forward_strategy", "alpaca_spot_proxy", "interpretation"],
    )
    write_json(output / "frozen_baseline_experiment_spec.json", spec)
    write_csv(
        output / "trade_management_overlay_compatibility.csv",
        overlay_rows,
        [
            "overlay",
            "classification",
            "negative_weights_supported",
            "gross_200_percent_supported",
            "net_zero_preserved",
            "usd_ranked_currency_handled",
            "assumes_long_only",
            "assumes_daily_ohlc",
            "requires_atr_or_instrument_prices",
            "changes_signal_selection",
            "can_evaluate_on_published_monthly_return_path",
            "identity_equality_can_be_asserted",
            "lower_exposure_control_possible_without_signal_change",
        ],
    )
    write_text(
        output / "trade_management_onboarding_requirements.md",
        """# Trade-Management Onboarding Requirements

Step 1: Implement and verify the frozen Alpaca spot-proxy baseline before any overlay trial.

Step 2: Prove `base strategy = IdentityOverlay` at every supported cost assumption and for every return observation.

Step 3: Test only compatibility-selected overlays. Each overlay must have its own variant ID, trial-ledger row, `exploratory_variant` adaptation label, fixed pre-results configuration, comparison against the unchanged baseline, and comparison against a static lower-exposure control where relevant.

Step 4: Interpret overlays only as trade-management adaptations. No overlay may silently repair or redefine the source/base strategy.

No overlay performance comparison was run in this task.
""",
    )
    write_csv(output / "concrete_blockers.csv", blockers, ["blocker", "detail", "specific_next_remediation"])
    write_json(output / "next_action.json", {"next_action": NEXT_ACTION, "do_not_execute_in_this_task": True})
    write_csv(
        output / "command_validation_log.csv",
        [
            {"command": ".venv\\Scripts\\python.exe run_currency_momentum_alpaca_data_and_overlay_readiness_v1.py", "required": True, "status": "recorded_by_final_response"},
            {"command": ".venv\\Scripts\\python.exe -m pytest tests\\test_currency_momentum_alpaca_data_and_overlay_readiness_v1.py -q", "required": True, "status": "recorded_by_final_response"},
            {"command": ".venv\\Scripts\\python.exe run_current_research_checkpoint.py", "required": True, "status": "recorded_by_final_response"},
            {"command": ".venv\\Scripts\\python.exe run_research_state_dashboard.py", "required": True, "status": "recorded_by_final_response"},
            {"command": ".venv\\Scripts\\python.exe run_advisor_consistency_check.py", "required": True, "status": "recorded_by_final_response"},
            {"command": ".venv\\Scripts\\python.exe run_strategy_lab.py --validate-registry --export-evidence", "required": True, "status": "recorded_by_final_response"},
        ],
        ["command", "required", "status"],
    )
    write_json(output / "consistency_check.json", consistency)
    write_text(output / "feasibility_summary.md", build_summary_text(outcome, monthly_summary, reconciliation_summary))

    # Check after writing allowed evidence; state files must remain unchanged.
    final_state_hashes = state_hashes(root)
    consistency["strategy_registry_changed"] = before_hashes.get(str(PROTECTED_STATE_PATHS[0])) != final_state_hashes.get(str(PROTECTED_STATE_PATHS[0]))
    consistency["active_observations_changed"] = before_hashes.get(str(PROTECTED_STATE_PATHS[3])) != final_state_hashes.get(str(PROTECTED_STATE_PATHS[3]))
    consistency["api_keys_logged_or_persisted"] = not no_secret_text_written(output)
    consistency["consistency_passed"] = not consistency["strategy_registry_changed"] and not consistency["active_observations_changed"] and not consistency["api_keys_logged_or_persisted"]
    write_json(output / "consistency_check.json", consistency)

    return {
        "task_id": TASK_ID,
        "evidence_path": str(output),
        "alpaca_data_feasibility_outcome": outcome,
        "complete_month_count": monthly_summary.get("complete_month_count", 0),
        "incomplete_month_count": monthly_summary.get("incomplete_month_count", 0),
        "spec_created": spec.get("spec_created", False),
        "next_action": NEXT_ACTION,
        "consistency_passed": consistency["consistency_passed"],
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
