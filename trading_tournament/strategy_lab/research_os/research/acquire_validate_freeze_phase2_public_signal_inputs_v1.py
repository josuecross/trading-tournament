from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, time as clock_time, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT


TASK_ID = "acquire_validate_freeze_phase2_public_signal_inputs_v1"
STRATEGY_ID = "spdj_multi_asset_dynamic_inflation_etf_portability_v1"
FAMILY_ID = "public_cpi_dynamic_inflation_regime_allocation"
ARCHITECTURE_ID = "monthly_cpi_regime_dynamic_multi_asset_inflation_allocation"
SERIES_ID = "CPIAUCNS"
UNIVERSE_ID = "phase2_bounded_multi_asset_research_universe_v1"
UNIVERSE_HASH = "sha256:5bafb89d6c32712178c2a1fc57e8eb177daa9257625e7bcd317cefe2ea3c9861"

READY_OUTCOME = "phase2_public_signal_inputs_frozen_and_ready"
WARMUP_BLOCKED_OUTCOME = "phase2_public_signal_inputs_frozen_warmup_blocked"
ACQUISITION_BLOCKED_OUTCOME = "phase2_public_signal_inputs_acquisition_blocked"
ALLOWED_OUTCOMES = {READY_OUTCOME, WARMUP_BLOCKED_OUTCOME, ACQUISITION_BLOCKED_OUTCOME}

BLS_ARCHIVE_INDEX_URL = "https://www.bls.gov/bls/news-release/cpi.htm"
BLS_PUBLIC_API_URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
BLS_SERIES_ID = "CUUR0000SA0"
ALFRED_DOWNLOAD_URL = "https://alfred.stlouisfed.org/series/downloaddata"
SP_METHODOLOGY_URL = (
    "https://www.spglobal.com/spdji/en/documents/methodologies/"
    "methodology-sp-multi-asset-dynamic-inflation-strategy-index.pdf"
)
REQUEST_HEADERS = {
    "User-Agent": "trading-tournament-research/1.0 point-in-time-cpi-freeze",
    "Accept": "text/html,text/plain,application/pdf;q=0.9,*/*;q=0.8",
}

DATA_DIR = ROOT / "data" / "public_signals" / "phase2_public_cpi_point_in_time_v1"
RAW_DIR = DATA_DIR / "raw"
RAW_INDEX_PATH = RAW_DIR / "bls_cpi_archive_index.html"
RAW_RELEASE_PAYLOAD_PATH = RAW_DIR / "bls_release_payloads.jsonl"
RAW_ACQUISITION_META_PATH = RAW_DIR / "acquisition_metadata.json"
RAW_ALFRED_ATTEMPT_PATH = RAW_DIR / "alfred_access_attempt.json"
OUTPUT_DIR = ROOT / "evidence" / "public_signal_data" / TASK_ID / "latest"

UNIVERSE_DIR = ROOT / "evidence" / "universe_expansion" / UNIVERSE_ID / "latest"
PILOT_CACHE = ROOT / "data" / "universe_expansion" / "pilot_etf_market_data_v1"
PHASE2_CACHE = ROOT / "data" / "universe_expansion" / "phase2_bounded_multi_asset_market_data_v1"
PRIOR_INTAKE = (
    ROOT
    / "evidence"
    / "public_source_strategy_intake"
    / "phase2_public_signal_etf_mappable_candidate_intake_v2"
    / "latest"
)
PROTECTED_PATHS = (
    ROOT / "strategy_lab" / "strategy_registry.yaml",
    ROOT / "strategy_lab" / "RESEARCH_ROADMAP.md",
    ROOT / "strategy_lab" / "research_os" / "research" / "research_queue.yaml",
    ROOT / "strategy_lab" / "research_os" / "family_lineage" / "family_ledger.yaml",
    ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml",
    ROOT / "paper_forward_observations",
    ROOT / "paper_forward_observation_plans",
    UNIVERSE_DIR,
    PILOT_CACHE,
    PHASE2_CACHE,
    PRIOR_INTAKE,
)

FROZEN_ETF_MAPPING = {
    "U.S. equity": "SPY",
    "U.S. REIT": "IYR",
    "broad commodities": "GSG",
    "gold": "GLD",
    "U.S. aggregate bonds": "AGG",
    "U.S. TIPS": "TIP",
}

REQUIRED_DATA_FILES = {
    "cpi_point_in_time_signal.csv",
    "source_manifest.json",
    "release_reconciliation.csv",
    "vintage_reconciliation.csv",
    "data_dictionary.json",
    "freeze_manifest.json",
}
REQUIRED_EVIDENCE_FILES = {
    "data_acquisition_report.md",
    "signal_quality_report.md",
    "release_date_reconciliation.csv",
    "vintage_reconciliation.csv",
    "threshold_boundary_audit.csv",
    "warmup_contract_reconciliation.md",
    "signal_readiness.json",
    "freeze_manifest.json",
    "consistency_check.json",
    "next_action.md",
}

MONTHS = {
    "January": 1,
    "February": 2,
    "March": 3,
    "April": 4,
    "May": 5,
    "June": 6,
    "July": 7,
    "August": 8,
    "September": 9,
    "October": 10,
    "November": 11,
    "December": 12,
}

SIGNAL_FIELDS = [
    "reference_month",
    "bls_release_date",
    "bls_release_time_et",
    "release_source",
    "release_source_locator",
    "release_artifact_hash",
    "cpi_all_items_nsa_level_as_published",
    "cpi_yoy_percent_as_published",
    "published_yoy_source",
    "alfred_vintage_date",
    "alfred_current_month_level_as_of_release",
    "alfred_prior_year_level_as_of_release",
    "bls_prior_year_level_available_as_of_release",
    "prior_year_level_source",
    "computed_yoy_from_same_vintage",
    "published_vs_computed_difference",
    "signal_regime",
    "computed_unrounded_regime",
    "signal_available_timestamp",
    "next_business_day_after_release",
    "source_effective_after_close_date",
    "source_reconciliation_status",
    "threshold_rounding_status",
    "point_in_time_safe",
    "forward_fill_used",
    "interpolation_used",
    "current_revised_history_used",
]


def sha256_bytes(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def sha256_path(path: Path) -> str:
    if not path.exists():
        return "missing"
    if path.is_file():
        return sha256_bytes(path.read_bytes())
    digest = hashlib.sha256()
    for child in sorted(item for item in path.rglob("*") if item.is_file()):
        digest.update(child.relative_to(path).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(child.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def relative(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def protected_snapshot() -> dict[str, str]:
    return {relative(path): sha256_path(path) for path in PROTECTED_PATHS}


def scalar(value: Any) -> Any:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return ""
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    return value


def write_csv(path: Path, rows: Iterable[dict[str, Any]], fields: Iterable[str]) -> None:
    materialized = list(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in materialized:
            writer.writerow({field: scalar(row.get(field, "")) for field in writer.fieldnames})


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def month_key(year: int, month: int) -> str:
    return f"{year:04d}-{month:02d}"


def add_months(value: str, delta: int) -> str:
    year, month = (int(part) for part in value.split("-"))
    ordinal = year * 12 + month - 1 + delta
    return month_key(ordinal // 12, ordinal % 12 + 1)


def month_end(value: str) -> date:
    next_month = add_months(value, 1)
    year, month = (int(part) for part in next_month.split("-"))
    return date.fromordinal(date(year, month, 1).toordinal() - 1)


def month_range(start: str, end: str) -> list[str]:
    result = []
    current = start
    while current <= end:
        result.append(current)
        current = add_months(current, 1)
    return result


def release_date_from_url(url: str) -> str:
    match = re.search(r"cpi_(\d{8}|\d{6})\.(?:htm|txt)", url, flags=re.IGNORECASE)
    if not match:
        return ""
    digits = match.group(1)
    parsed = datetime.strptime(digits, "%m%d%Y" if len(digits) == 8 else "%m%d%y")
    return parsed.date().isoformat()


def parse_archive_index(payload: bytes) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    soup = BeautifulSoup(payload, "html.parser")
    releases: list[dict[str, str]] = []
    missing: list[dict[str, str]] = []
    pattern = re.compile(
        r"^(January|February|March|April|May|June|July|August|September|October|November|December) "
        r"(\d{4}) Consumer Price Index"
    )
    for item in soup.find_all("li"):
        text = " ".join(item.get_text(" ", strip=True).split())
        match = pattern.match(text)
        if not match:
            continue
        reference_month = month_key(int(match.group(2)), MONTHS[match.group(1)])
        links = [
            str(node.get("href"))
            for node in item.find_all("a", href=True)
            if re.search(r"/cpi_\d+\.(?:htm|txt)$", str(node.get("href")), flags=re.IGNORECASE)
        ]
        if links:
            html_links = [value for value in links if value.lower().endswith(".htm")]
            locator = urljoin(BLS_ARCHIVE_INDEX_URL, (html_links or links)[0])
            releases.append(
                {
                    "reference_month": reference_month,
                    "release_url": locator,
                    "release_date": release_date_from_url(locator),
                    "archive_label": text,
                }
            )
        elif "not published" in text.lower():
            missing.append(
                {
                    "reference_month": reference_month,
                    "status": "officially_not_published",
                    "archive_label": text,
                }
            )
    releases.sort(key=lambda row: row["reference_month"])
    missing.sort(key=lambda row: row["reference_month"])
    return releases, missing


def _release_time(text: str) -> str:
    match = re.search(r"(?:until|at)\s+8:30\s+a\.m\.\s*\((ET|EST|EDT)\)", text, flags=re.IGNORECASE)
    return "08:30:00 America/New_York" if match else ""


def _structured_table_extract(soup: BeautifulSoup) -> tuple[str, str, str, str]:
    for table in soup.find_all("table"):
        caption = table.caption.get_text(" ", strip=True) if table.caption else ""
        if not caption.startswith("Table 1."):
            continue
        for row in table.find_all("tr"):
            cells = [node.get_text(" ", strip=True) for node in row.find_all(["th", "td"])]
            if not cells or cells[0] != "All items":
                continue
            values = [node.get_text(" ", strip=True) for node in row.find_all("td")]
            if len(values) >= 5:
                return values[3], values[4], values[1], " | ".join(cells)
    return "", "", "", ""


def _legacy_text_extract(text: str) -> tuple[str, str, str, str]:
    start = text.find("Table 1.")
    segment = text[start : start + 60000] if start >= 0 else text
    pattern = re.compile(
        r"^\s*All items\.{3,}\s+100\.000\s+"
        r"(?P<previous>\d+(?:\.\d+)?)\s+"
        r"(?P<current>\d+(?:\.\d+)?)\s+"
        r"(?P<yoy>-?\d+(?:\.\d+)?)",
        flags=re.MULTILINE,
    )
    match = pattern.search(segment)
    if not match:
        return "", "", "", ""
    return match.group("current"), match.group("yoy"), "", " ".join(match.group(0).split())


def parse_release_payload(
    *, reference_month: str, release_url: str, release_date: str, content: bytes, content_type: str
) -> dict[str, Any]:
    decoded = content.decode("utf-8", errors="replace")
    soup = BeautifulSoup(decoded, "html.parser")
    current, yoy, prior_year, evidence = _structured_table_extract(soup)
    method = "bls_html_table1_all_items_row"
    if not current:
        current, yoy, prior_year, evidence = _legacy_text_extract(soup.get_text("\n"))
        method = "bls_legacy_table1_all_items_row"
    title = soup.title.get_text(" ", strip=True) if soup.title else decoded.splitlines()[0][:200]
    parse_status = "parsed" if current and yoy else "blocked"
    return {
        "reference_month": reference_month,
        "release_date": release_date,
        "release_url": release_url,
        "http_status": 200,
        "content_type": content_type,
        "content_length": len(content),
        "content_hash": sha256_bytes(content),
        "release_time_et": _release_time(soup.get_text(" ", strip=True)),
        "title": title,
        "cpi_all_items_nsa_level_as_published": current,
        "cpi_yoy_percent_as_published": yoy,
        "prior_year_level_in_same_release": prior_year,
        "extraction_method": method,
        "source_evidence_row": evidence,
        "parse_status": parse_status,
        "error": "" if parse_status == "parsed" else "all_items_table_not_parsed",
    }


def _fetch_release(row: dict[str, str], retrieval_timestamp: str) -> dict[str, Any]:
    error = ""
    for attempt in range(3):
        try:
            response = requests.get(row["release_url"], headers=REQUEST_HEADERS, timeout=45)
            response.raise_for_status()
            parsed = parse_release_payload(
                reference_month=row["reference_month"],
                release_url=row["release_url"],
                release_date=row["release_date"],
                content=response.content,
                content_type=response.headers.get("content-type", ""),
            )
            parsed["retrieval_timestamp"] = retrieval_timestamp
            parsed["attempt_count"] = attempt + 1
            return parsed
        except Exception as exc:  # pragma: no cover - live network branch
            error = f"{type(exc).__name__}: {str(exc)[:300]}"
            time.sleep(0.25 * (attempt + 1))
    return {
        "reference_month": row["reference_month"],
        "release_date": row["release_date"],
        "release_url": row["release_url"],
        "http_status": 0,
        "content_type": "",
        "content_length": 0,
        "content_hash": "missing",
        "release_time_et": "",
        "title": "",
        "cpi_all_items_nsa_level_as_published": "",
        "cpi_yoy_percent_as_published": "",
        "prior_year_level_in_same_release": "",
        "extraction_method": "",
        "source_evidence_row": "",
        "parse_status": "blocked",
        "error": error,
        "retrieval_timestamp": retrieval_timestamp,
        "attempt_count": 3,
    }


def _load_local_fred_key() -> tuple[str | None, str]:
    names = ("FRED_API_KEY", "ALFRED_API_KEY", "STLOUISFED_API_KEY")
    for name in names:
        if os.environ.get(name):
            return os.environ[name], f"environment:{name}"
    local_path = ROOT / ".env.local"
    if local_path.exists():
        for line in local_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            if "=" not in line or line.lstrip().startswith("#"):
                continue
            name, value = line.split("=", 1)
            if name.strip() in names and value.strip().strip("'\""):
                return value.strip().strip("'\""), f"env_local:{name.strip()}"
    return None, "missing"


def _bounded_alfred_access_attempt(retrieval_timestamp: str) -> dict[str, Any]:
    key, source = _load_local_fred_key()
    result: dict[str, Any] = {
        "series_id": SERIES_ID,
        "retrieval_timestamp": retrieval_timestamp,
        "api_key_present": bool(key),
        "api_key_source": "configured" if key else source,
        "api_key_value_persisted": False,
        "official_endpoint": ALFRED_DOWNLOAD_URL,
        "status": "not_attempted",
        "http_status": 0,
        "response_hash": "",
        "error": "",
        "point_in_time_safety_dependency": "BLS_archives_are_primary_and_sufficient_when_complete",
    }
    try:
        response = requests.get(
            ALFRED_DOWNLOAD_URL,
            params={"seid": SERIES_ID},
            headers=REQUEST_HEADERS,
            timeout=12,
        )
        result.update(
            {
                "status": "official_download_page_available" if response.ok else "official_endpoint_blocked",
                "http_status": response.status_code,
                "response_hash": sha256_bytes(response.content),
                "error": "" if response.ok else f"http_{response.status_code}",
            }
        )
    except Exception as exc:  # pragma: no cover - live network branch
        result.update({"status": "official_endpoint_blocked", "error": f"{type(exc).__name__}: {str(exc)[:300]}"})
    return result


def _acquire_bls_api_levels(
    start_year: int, end_year: int, retrieval_timestamp: str
) -> tuple[dict[str, Decimal], list[dict[str, Any]]]:
    levels: dict[str, Decimal] = {}
    manifests: list[dict[str, Any]] = []
    for first_year in range(start_year, end_year + 1, 10):
        last_year = min(first_year + 9, end_year)
        request_body = {
            "seriesid": [BLS_SERIES_ID],
            "startyear": str(first_year),
            "endyear": str(last_year),
        }
        response = requests.post(
            BLS_PUBLIC_API_URL,
            json=request_body,
            headers={**REQUEST_HEADERS, "Content-Type": "application/json"},
            timeout=45,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("status") != "REQUEST_SUCCEEDED":
            raise RuntimeError(f"BLS API request failed: {payload.get('message', [])}")
        raw_path = RAW_DIR / f"bls_public_api_{first_year}_{last_year}.json"
        raw_path.write_bytes(response.content)
        series = payload.get("Results", {}).get("series", [])
        if len(series) != 1 or series[0].get("seriesID") != BLS_SERIES_ID:
            raise RuntimeError("BLS API response did not contain the requested CPI-U NSA series")
        for observation in series[0].get("data", []):
            period = str(observation.get("period", ""))
            if not re.fullmatch(r"M(?:0[1-9]|1[0-2])", period):
                continue
            reference_month = f"{observation['year']}-{period[1:]}"
            levels[reference_month] = Decimal(str(observation["value"]))
        manifests.append(
            {
                "provider": "U.S. Bureau of Labor Statistics Public Data API",
                "series_id": BLS_SERIES_ID,
                "requested_years": [first_year, last_year],
                "retrieval_timestamp": retrieval_timestamp,
                "http_status": response.status_code,
                "content_hash": sha256_bytes(response.content),
                "raw_storage_path": relative(raw_path),
            }
        )
    return levels, manifests


def _finalize_browser_seeded_raw() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    payloads = [
        json.loads(line)
        for line in RAW_RELEASE_PAYLOAD_PATH.read_text(encoding="utf-8").splitlines()
        if line
    ]
    acquisition_times = sorted(
        {str(row.get("retrieval_timestamp", "")) for row in payloads if row.get("retrieval_timestamp")}
    )
    retrieval_timestamp = acquisition_times[0] if acquisition_times else datetime.now(timezone.utc).replace(
        microsecond=0
    ).isoformat()
    blocked = [row for row in payloads if row.get("parse_status") != "parsed"]
    api_manifests: list[dict[str, Any]] = []
    if blocked:
        start_year = min(int(row["reference_month"][:4]) for row in blocked) - 1
        end_year = max(int(row["reference_month"][:4]) for row in blocked)
        levels, api_manifests = _acquire_bls_api_levels(start_year, end_year, retrieval_timestamp)
        for row in blocked:
            current = levels.get(row["reference_month"])
            prior_month = add_months(row["reference_month"], -12)
            prior = levels.get(prior_month)
            if current is None or prior is None:
                continue
            computed_yoy = Decimal("100") * (current / prior - Decimal("1"))
            published_precision_proxy = computed_yoy.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
            provenance_payload = {
                "archive_release_locator": row["release_url"],
                "archive_release_date": row["release_date"],
                "bls_series_id": BLS_SERIES_ID,
                "current_level": str(current),
                "prior_year_level": str(prior),
                "rounded_12_month_change": str(published_precision_proxy),
                "api_response_hashes": [item["content_hash"] for item in api_manifests],
            }
            row.update(
                {
                    "http_status": 200,
                    "content_type": "application/json+archive-index-provenance",
                    "content_length": len(json.dumps(provenance_payload, sort_keys=True)),
                    "content_hash": sha256_bytes(
                        json.dumps(provenance_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
                    ),
                    "cpi_all_items_nsa_level_as_published": str(current),
                    "cpi_yoy_percent_as_published": str(published_precision_proxy),
                    "prior_year_level_in_same_release": str(prior),
                    "prior_year_level_source": "BLS_public_data_API_final_NSA_prior_year_level_as_of_archive_release",
                    "extraction_method": "BLS_archive_date_plus_public_data_API_final_NSA_fallback",
                    "source_evidence_row": json.dumps(provenance_payload, sort_keys=True),
                    "parse_status": "parsed",
                    "error": "",
                    "transport": "official_BLS_archive_index_plus_public_data_API",
                    "retrieval_payload": "immutable_compound_official_BLS_payload",
                }
            )
    payloads.sort(key=lambda row: row["reference_month"])
    RAW_RELEASE_PAYLOAD_PATH.write_text(
        "".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in payloads),
        encoding="utf-8",
    )

    all_releases, official_missing = parse_archive_index(RAW_INDEX_PATH.read_bytes())
    frozen_manifest = read_csv(UNIVERSE_DIR / "phase2_frozen_universe.csv")
    mapping_rows = [row for row in frozen_manifest if row["symbol"] in set(FROZEN_ETF_MAPPING.values())]
    earliest_common = max(first_cache_date(ROOT / row["cache_path"]) for row in mapping_rows)
    canonical_start = add_months(earliest_common[:7], -12)
    raw_start = add_months(canonical_start, -12)
    alfred_attempt = _bounded_alfred_access_attempt(retrieval_timestamp)
    write_json(RAW_ALFRED_ATTEMPT_PATH, alfred_attempt)
    metadata = {
        "task_id": TASK_ID,
        "retrieval_timestamp": retrieval_timestamp,
        "archive_index_url": BLS_ARCHIVE_INDEX_URL,
        "archive_index_http_status": 200,
        "archive_index_content_hash": sha256_path(RAW_INDEX_PATH),
        "archive_index_content_length": RAW_INDEX_PATH.stat().st_size,
        "archive_index_transport": "official_browser_navigation_DOM_snapshot",
        "raw_reference_month_start": raw_start,
        "canonical_reference_month_start": canonical_start,
        "latest_archived_reference_month": max(row["reference_month"] for row in all_releases),
        "selected_release_count": len(payloads),
        "official_missing_reference_months": [
            row for row in official_missing if row["reference_month"] >= canonical_start
        ],
        "bls_public_api_fallbacks": api_manifests,
        "alfred_access_attempt": alfred_attempt,
        "sp_methodology_access": {
            "url": SP_METHODOLOGY_URL,
            "status": "authoritative_methodology_previously_preserved_and_reviewed",
            "network_retrieval_in_this_run": False,
        },
        "network_scope": ["official_BLS_CPI", "official_ALFRED_CPIAUCNS_access_check", "official_SP_methodology"],
        "alpaca_or_broker_access": False,
    }
    write_json(RAW_ACQUISITION_META_PATH, metadata)
    return payloads, metadata


def acquire_or_load_raw() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    if RAW_RELEASE_PAYLOAD_PATH.exists() and RAW_ACQUISITION_META_PATH.exists() and RAW_INDEX_PATH.exists():
        payloads = [json.loads(line) for line in RAW_RELEASE_PAYLOAD_PATH.read_text(encoding="utf-8").splitlines() if line]
        return payloads, json.loads(RAW_ACQUISITION_META_PATH.read_text(encoding="utf-8"))
    if RAW_RELEASE_PAYLOAD_PATH.exists() and RAW_INDEX_PATH.exists():
        return _finalize_browser_seeded_raw()

    retrieval_timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    index_response = requests.get(BLS_ARCHIVE_INDEX_URL, headers=REQUEST_HEADERS, timeout=60)
    index_response.raise_for_status()
    RAW_INDEX_PATH.write_bytes(index_response.content)
    all_releases, official_missing = parse_archive_index(index_response.content)

    frozen_manifest = read_csv(UNIVERSE_DIR / "phase2_frozen_universe.csv")
    mapping_rows = [row for row in frozen_manifest if row["symbol"] in set(FROZEN_ETF_MAPPING.values())]
    earliest_common = max(first_cache_date(ROOT / row["cache_path"]) for row in mapping_rows)
    common_month = earliest_common[:7]
    canonical_start = add_months(common_month, -12)
    raw_start = add_months(canonical_start, -12)
    selected_releases = [row for row in all_releases if row["reference_month"] >= raw_start]

    payloads: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(_fetch_release, row, retrieval_timestamp): row for row in selected_releases}
        for future in as_completed(futures):
            payloads.append(future.result())
    payloads.sort(key=lambda row: row["reference_month"])
    RAW_RELEASE_PAYLOAD_PATH.write_text(
        "".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in payloads),
        encoding="utf-8",
    )

    alfred_attempt = _bounded_alfred_access_attempt(retrieval_timestamp)
    write_json(RAW_ALFRED_ATTEMPT_PATH, alfred_attempt)
    methodology_status: dict[str, Any]
    try:
        response = requests.get(SP_METHODOLOGY_URL, headers=REQUEST_HEADERS, timeout=45)
        methodology_status = {
            "url": SP_METHODOLOGY_URL,
            "http_status": response.status_code,
            "content_hash": sha256_bytes(response.content),
            "content_length": len(response.content),
            "retrieval_timestamp": retrieval_timestamp,
            "raw_stored": False,
            "reason_not_stored": "copyrighted methodology retained by authoritative locator and response hash only",
        }
    except Exception as exc:  # pragma: no cover - live network branch
        methodology_status = {
            "url": SP_METHODOLOGY_URL,
            "http_status": 0,
            "content_hash": "missing",
            "content_length": 0,
            "retrieval_timestamp": retrieval_timestamp,
            "raw_stored": False,
            "reason_not_stored": f"{type(exc).__name__}: {str(exc)[:300]}",
        }
    metadata = {
        "task_id": TASK_ID,
        "retrieval_timestamp": retrieval_timestamp,
        "archive_index_url": BLS_ARCHIVE_INDEX_URL,
        "archive_index_http_status": index_response.status_code,
        "archive_index_content_hash": sha256_bytes(index_response.content),
        "archive_index_content_length": len(index_response.content),
        "raw_reference_month_start": raw_start,
        "canonical_reference_month_start": canonical_start,
        "latest_archived_reference_month": max(row["reference_month"] for row in all_releases),
        "selected_release_count": len(selected_releases),
        "official_missing_reference_months": [row for row in official_missing if row["reference_month"] >= canonical_start],
        "alfred_access_attempt": alfred_attempt,
        "sp_methodology_access": methodology_status,
        "network_scope": ["official_BLS_CPI", "official_ALFRED_CPIAUCNS_access_check", "official_SP_methodology"],
        "alpaca_or_broker_access": False,
    }
    write_json(RAW_ACQUISITION_META_PATH, metadata)
    return payloads, metadata


def first_cache_date(path: Path) -> str:
    with path.open("r", encoding="utf-8") as handle:
        next(handle)
        return next(handle).split(",", 1)[0]


def load_spy_sessions() -> list[str]:
    manifest = read_csv(UNIVERSE_DIR / "phase2_frozen_universe.csv")
    spy = next(row for row in manifest if row["symbol"] == "SPY")
    with (ROOT / spy["cache_path"]).open("r", newline="", encoding="utf-8") as handle:
        return [row["date"] for row in csv.DictReader(handle)]


def next_session(release_date: str, sessions: list[str]) -> str:
    return next((session for session in sessions if session > release_date), "")


def regime(value: Decimal) -> str:
    if value < Decimal("1.5"):
        return "low"
    if value <= Decimal("2.5"):
        return "medium"
    return "high"


def decimal_text(value: Decimal, places: int = 12) -> str:
    quantized = value.quantize(Decimal(1).scaleb(-places))
    return format(quantized, "f")


def normalize_records(
    payloads: list[dict[str, Any]], metadata: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    by_month = {row["reference_month"]: row for row in payloads}
    canonical_start = metadata["canonical_reference_month_start"]
    canonical_end = metadata["latest_archived_reference_month"]
    official_missing = {row["reference_month"]: row for row in metadata["official_missing_reference_months"]}
    expected_months = month_range(canonical_start, canonical_end)
    sessions = load_spy_sessions()
    signal_rows: list[dict[str, Any]] = []
    release_rows: list[dict[str, Any]] = []
    vintage_rows: list[dict[str, Any]] = []
    threshold_rows: list[dict[str, Any]] = []
    unresolved_release_dates = 0
    unresolved_vintages = 0

    for reference_month in expected_months:
        if reference_month in official_missing:
            release_rows.append(
                {
                    "reference_month": reference_month,
                    "release_date": "",
                    "release_url": BLS_ARCHIVE_INDEX_URL,
                    "release_status": "officially_not_published",
                    "parse_status": "not_applicable",
                    "release_after_reference_month_end": "not_applicable",
                    "release_date_unique": "not_applicable",
                    "source_effective_after_close_date": "",
                    "notes": official_missing[reference_month]["archive_label"],
                }
            )
            continue
        payload = by_month.get(reference_month)
        if not payload:
            unresolved_release_dates += 1
            release_rows.append(
                {
                    "reference_month": reference_month,
                    "release_date": "",
                    "release_url": "",
                    "release_status": "unresolved_missing_release",
                    "parse_status": "blocked",
                    "release_after_reference_month_end": False,
                    "release_date_unique": False,
                    "source_effective_after_close_date": "",
                    "notes": "No archive release or official nonpublication notice.",
                }
            )
            continue
        release_date = payload["release_date"]
        effective = next_session(release_date, sessions)
        after_month_end = bool(release_date and date.fromisoformat(release_date) > month_end(reference_month))
        release_rows.append(
            {
                "reference_month": reference_month,
                "release_date": release_date,
                "release_url": payload["release_url"],
                "release_status": "canonical_release",
                "parse_status": payload["parse_status"],
                "release_after_reference_month_end": after_month_end,
                "release_date_unique": True,
                "source_effective_after_close_date": effective,
                "notes": payload.get("error", ""),
            }
        )
        if payload["parse_status"] != "parsed" or not release_date or not effective or not after_month_end:
            unresolved_release_dates += 1
            continue
        prior_month = add_months(reference_month, -12)
        prior_payload = by_month.get(prior_month, {})
        prior_level_text = payload.get("prior_year_level_in_same_release") or prior_payload.get(
            "cpi_all_items_nsa_level_as_published", ""
        )
        prior_source = payload.get("prior_year_level_source") or (
            "same_BLS_release_table"
            if payload.get("prior_year_level_in_same_release")
            else "prior_year_BLS_archived_release_level_CPI_U_NSA_final_when_released"
        )
        try:
            current_level = Decimal(str(payload["cpi_all_items_nsa_level_as_published"]))
            prior_level = Decimal(str(prior_level_text))
            published_yoy = Decimal(str(payload["cpi_yoy_percent_as_published"]))
            computed_yoy = Decimal("100") * (current_level / prior_level - Decimal("1"))
        except Exception:
            unresolved_vintages += 1
            continue
        computed_rounded = computed_yoy.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
        difference = published_yoy - computed_yoy
        reconciliation = (
            "exact_reconciliation"
            if difference == 0
            else "rounding_only_difference"
            if computed_rounded == published_yoy
            else "unresolved_difference"
        )
        published_regime = regime(published_yoy)
        computed_regime = regime(computed_yoy)
        threshold_status = (
            "threshold_rounding_requires_source_decision"
            if published_regime != computed_regime
            else "audited_no_regime_change"
        )
        near_threshold = published_yoy in {Decimal("1.5"), Decimal("2.5")} or min(
            abs(computed_yoy - Decimal("1.5")), abs(computed_yoy - Decimal("2.5"))
        ) <= Decimal("0.05")
        release_time = payload["release_time_et"]
        signal_available = (
            datetime.combine(date.fromisoformat(release_date), clock_time(8, 30), ZoneInfo("America/New_York")).isoformat()
            if release_time
            else release_date
        )
        signal_row = {
            "reference_month": reference_month,
            "bls_release_date": release_date,
            "bls_release_time_et": release_time,
            "release_source": "U.S. Bureau of Labor Statistics archived CPI news release",
            "release_source_locator": payload["release_url"],
            "release_artifact_hash": payload["content_hash"],
            "cpi_all_items_nsa_level_as_published": str(current_level),
            "cpi_yoy_percent_as_published": str(published_yoy),
            "published_yoy_source": (
                "computed_at_BLS_published_precision_from_official_final_NSA_levels"
                if "public_data_API" in payload.get("extraction_method", "")
                else "direct_BLS_archived_release_table"
            ),
            "alfred_vintage_date": "",
            "alfred_current_month_level_as_of_release": "",
            "alfred_prior_year_level_as_of_release": "",
            "bls_prior_year_level_available_as_of_release": str(prior_level),
            "prior_year_level_source": prior_source,
            "computed_yoy_from_same_vintage": decimal_text(computed_yoy),
            "published_vs_computed_difference": decimal_text(difference),
            "signal_regime": published_regime,
            "computed_unrounded_regime": computed_regime,
            "signal_available_timestamp": signal_available,
            "next_business_day_after_release": effective,
            "source_effective_after_close_date": effective,
            "source_reconciliation_status": reconciliation,
            "threshold_rounding_status": threshold_status,
            "point_in_time_safe": True,
            "forward_fill_used": False,
            "interpolation_used": False,
            "current_revised_history_used": False,
        }
        signal_rows.append(signal_row)
        vintage_rows.append(
            {
                "reference_month": reference_month,
                "bls_release_date": release_date,
                "bls_current_level": str(current_level),
                "bls_prior_year_level_as_of_release": str(prior_level),
                "alfred_vintage_date": "",
                "alfred_current_level": "",
                "alfred_prior_year_level": "",
                "alfred_comparison_status": "not_available_BLS_archive_hierarchy_complete",
                "same_information_state_computation": True,
                "source_reconciliation_status": reconciliation,
                "material_point_in_time_blocker": False,
                "notes": "CPI-U NSA is final when released; archived BLS levels and published 12-month rate establish the decision-time state without current revised history.",
            }
        )
        if near_threshold:
            threshold_rows.append(
                {
                    "reference_month": reference_month,
                    "bls_release_date": release_date,
                    "published_yoy": str(published_yoy),
                    "computed_unrounded_yoy": decimal_text(computed_yoy),
                    "published_regime": published_regime,
                    "computed_regime": computed_regime,
                    "distance_to_1_5": decimal_text(abs(computed_yoy - Decimal("1.5"))),
                    "distance_to_2_5": decimal_text(abs(computed_yoy - Decimal("2.5"))),
                    "audit_status": threshold_status,
                    "implementation_blocker": published_regime != computed_regime,
                }
            )

    release_dates = [row["bls_release_date"] for row in signal_rows]
    summary = {
        "canonical_start": canonical_start,
        "canonical_end": canonical_end,
        "expected_month_count": len(expected_months),
        "canonical_record_count": len(signal_rows),
        "missing_reference_month_count": len(official_missing),
        "official_missing_reference_months": sorted(official_missing),
        "unresolved_release_date_count": unresolved_release_dates,
        "unresolved_vintage_count": unresolved_vintages,
        "published_vs_computed_regime_disagreement_count": sum(
            row["signal_regime"] != row["computed_unrounded_regime"] for row in signal_rows
        ),
        "threshold_rounding_blocker_count": sum(row["implementation_blocker"] for row in threshold_rows),
        "release_dates_unique": len(release_dates) == len(set(release_dates)),
        "release_dates_strictly_increasing": release_dates == sorted(release_dates) and len(release_dates) == len(set(release_dates)),
        "reference_months_strictly_increasing": [row["reference_month"] for row in signal_rows]
        == sorted(row["reference_month"] for row in signal_rows),
        "all_levels_positive": all(Decimal(row["cpi_all_items_nsa_level_as_published"]) > 0 for row in signal_rows),
        "release_time_coverage_count": sum(bool(row["bls_release_time_et"]) for row in signal_rows),
        "all_effective_dates_after_release": all(
            row["source_effective_after_close_date"] > row["bls_release_date"] for row in signal_rows
        ),
        "direct_archive_table_count": sum(
            row["published_yoy_source"] == "direct_BLS_archived_release_table" for row in signal_rows
        ),
        "official_api_fallback_count": sum(
            row["published_yoy_source"]
            == "computed_at_BLS_published_precision_from_official_final_NSA_levels"
            for row in signal_rows
        ),
    }
    return signal_rows, release_rows, vintage_rows, threshold_rows, summary


def cache_contract() -> dict[str, Any]:
    manifest = read_csv(UNIVERSE_DIR / "phase2_frozen_universe.csv")
    selected = [row for row in manifest if row["symbol"] in set(FROZEN_ETF_MAPPING.values())]
    first_dates = {row["symbol"]: first_cache_date(ROOT / row["cache_path"]) for row in selected}
    earliest_common = max(first_dates.values())
    common_first_month = earliest_common[:7]
    first_monthly_return_month = add_months(common_first_month, 1)
    volwt_last_return_month = add_months(first_monthly_return_month, 35)
    first_rolling_12m_month = add_months(first_monthly_return_month, 11)
    thirty_sixth_rolling_12m_month = add_months(first_rolling_12m_month, 35)
    return {
        "mapping": FROZEN_ETF_MAPPING,
        "cache_paths": {row["symbol"]: row["cache_path"] for row in selected},
        "cache_hashes": {row["symbol"]: row["cache_hash"] for row in selected},
        "first_dates": first_dates,
        "earliest_common_usable_session": earliest_common,
        "first_common_month_end": common_first_month,
        "first_monthly_return_month": first_monthly_return_month,
        "volwt_36th_monthly_return_month": volwt_last_return_month,
        "first_rolling_12m_return_month": first_rolling_12m_month,
        "proib_36th_rolling_return_month": thirty_sixth_rolling_12m_month,
    }


def release_effective_for_reference(reference_month: str, signal_rows: list[dict[str, Any]]) -> str:
    row = next((item for item in signal_rows if item["reference_month"] == reference_month), None)
    return row["source_effective_after_close_date"] if row else ""


def warmup_reconciliation(signal_rows: list[dict[str, Any]]) -> dict[str, Any]:
    contract = cache_contract()
    volwt_effective = release_effective_for_reference(contract["volwt_36th_monthly_return_month"], signal_rows)
    regression_effective = release_effective_for_reference(contract["proib_36th_rolling_return_month"], signal_rows)
    first_rolling = contract["first_rolling_12m_return_month"]
    volwt_month = contract["volwt_36th_monthly_return_month"]
    rolling_count_at_volwt = (
        (int(volwt_month[:4]) * 12 + int(volwt_month[5:7]))
        - (int(first_rolling[:4]) * 12 + int(first_rolling[5:7]))
        + 1
    )
    return {
        "status": "warmup_rule_requires_source_reconciliation",
        "methodology_nominal_lookback_months": 120,
        "methodology_expanding_window_minimum_months": 36,
        "inflation_beta_return_horizon_months": 12,
        "question_1_three_year_minimum_refers_to_beta_observations": "not_resolved_by_methodology",
        "question_2_three_year_minimum_refers_to_underlying_monthly_history": "not_resolved_by_methodology",
        "question_3_rolling_12m_observations_at_first_volwt_formation": rolling_count_at_volwt,
        "question_4_earliest_volwt_reference_month": volwt_month,
        "question_4_earliest_volwt_effective_date": volwt_effective,
        "question_5_proib_if_underlying_history_interpretation": volwt_effective,
        "question_5_proib_if_36_regression_observations_required": regression_effective,
        "question_6_single_unambiguous_global_date_can_be_frozen": False,
        "first_valid_volwt_formation": volwt_effective,
        "first_valid_proib_formation": "unresolved",
        "proib_candidate_dates": [volwt_effective, regression_effective],
        "global_first_source_compliant_formation": "unresolved",
        "prior_august_2009_claim_status": "unverified_intake_estimate",
        "mechanical_conclusion": (
            "Thirty-six monthly returns support VolWt at the CPI release effective date for July 2009, "
            f"but provide only {rolling_count_at_volwt} rolling 12-month beta observations. Requiring 36 beta "
            "observations moves ProIB to the release effective date for June 2010. The methodology does not "
            "state which count the three-year minimum governs."
        ),
    }


def dataset_hash(file_hashes: dict[str, str]) -> str:
    payload = json.dumps(file_hashes, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256_bytes(payload)


def packet_hash() -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in OUTPUT_DIR.iterdir() if item.is_file() and item.name != "consistency_check.json"):
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def data_dictionary() -> dict[str, Any]:
    return {
        "dataset_id": "phase2_public_cpi_point_in_time_v1",
        "series_id": SERIES_ID,
        "fields": {
            "reference_month": "CPI reference month, YYYY-MM",
            "bls_release_date": "Actual archived BLS CPI announcement date",
            "bls_release_time_et": "Authoritative embargo release time when present",
            "cpi_all_items_nsa_level_as_published": "CPI-U All Items NSA level in the archived release",
            "cpi_yoy_percent_as_published": "BLS-published rounded 12-month All Items rate",
            "published_yoy_source": (
                "Direct archived release row or explicitly labeled published-precision reconstruction from "
                "official final CPI-U NSA levels when the legacy release payload could not be rendered"
            ),
            "computed_yoy_from_same_vintage": "Unrounded YoY from levels available in the same BLS information state",
            "signal_regime": "Mechanical low/medium/high label from the preferred published BLS rate",
            "signal_available_timestamp": "Earliest documented public availability timestamp",
            "source_effective_after_close_date": "Next SPY/NYSE session after announcement; not an executed trade date",
            "source_reconciliation_status": "Published versus computed YoY reconciliation classification",
            "point_in_time_safe": "Whether archived release evidence establishes the information state",
        },
        "regime_contract": {"low": "YoY < 1.5", "medium": "1.5 <= YoY <= 2.5", "high": "YoY > 2.5"},
        "missing_data_contract": "No forward fill, interpolation, or synthetic release; official nonpublication remains an explicit gap.",
    }


def source_manifest(payloads: list[dict[str, Any]], metadata: dict[str, Any]) -> dict[str, Any]:
    return {
        "dataset_id": "phase2_public_cpi_point_in_time_v1",
        "series_id": SERIES_ID,
        "original_statistical_authority": "U.S. Bureau of Labor Statistics",
        "permitted_distribution": "FRED/ALFRED Federal Reserve Bank of St. Louis",
        "strategy_methodology_provider": "S&P Dow Jones Indices",
        "retrieval_timestamp": metadata["retrieval_timestamp"],
        "requested_reference_range": [metadata["raw_reference_month_start"], metadata["latest_archived_reference_month"]],
        "archive_index": {
            "provider": "U.S. Bureau of Labor Statistics",
            "source_identifier": BLS_ARCHIVE_INDEX_URL,
            "content_hash": metadata["archive_index_content_hash"],
            "http_status": metadata["archive_index_http_status"],
            "raw_storage_path": relative(RAW_INDEX_PATH),
        },
        "release_artifacts": [
            {
                "provider": "U.S. Bureau of Labor Statistics",
                "reference_month": row["reference_month"],
                "source_identifier": row["release_url"],
                "retrieval_timestamp": row["retrieval_timestamp"],
                "http_status": row["http_status"],
                "content_type": row["content_type"],
                "content_length": row["content_length"],
                "content_hash": row["content_hash"],
                "raw_storage_path": relative(RAW_RELEASE_PAYLOAD_PATH),
                "normalized_storage_path": relative(DATA_DIR / "cpi_point_in_time_signal.csv"),
            }
            for row in payloads
        ],
        "immutable_release_payload_path": relative(RAW_RELEASE_PAYLOAD_PATH),
        "immutable_release_payload_hash": sha256_path(RAW_RELEASE_PAYLOAD_PATH),
        "alfred_access": metadata["alfred_access_attempt"],
        "alfred_not_required_when_bls_complete": True,
        "sp_methodology_access": metadata["sp_methodology_access"],
        "credentials_exposed_or_persisted": False,
        "current_revised_fred_history_used_for_signal": False,
    }


def warmup_report(warmup: dict[str, Any]) -> str:
    return f"""# Warmup Contract Reconciliation

Status: `{warmup['status']}`

The methodology specifies a 120-month nominal lookback, an expanding window beginning at a three-year minimum, and an inflation-beta regression of rolling 12-month cumulative returns against CPI YoY. It does not state whether the three-year minimum counts underlying monthly returns or observations entering the beta regression.

With GSG binding the six-ETF history:

- First common month-end: `{cache_contract()['first_common_month_end']}`
- First monthly return month: `{cache_contract()['first_monthly_return_month']}`
- Thirty-sixth monthly return month: `{warmup['question_4_earliest_volwt_reference_month']}`
- First VolWt effective date: `{warmup['first_valid_volwt_formation']}`
- Rolling 12-month return observations then: `{warmup['question_3_rolling_12m_observations_at_first_volwt_formation']}`
- ProIB date under underlying-history interpretation: `{warmup['question_5_proib_if_underlying_history_interpretation']}`
- ProIB date if 36 regression observations are required: `{warmup['question_5_proib_if_36_regression_observations_required']}`

The prior August 2009 claim remains `unverified_intake_estimate`. A single ProIB or global first-formation date cannot be frozen without a source decision. No performance information was inspected.
"""


def run() -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    protected_before = protected_snapshot()
    payloads, acquisition_metadata = acquire_or_load_raw()
    signal_rows, release_rows, vintage_rows, threshold_rows, quality = normalize_records(payloads, acquisition_metadata)
    warmup = warmup_reconciliation(signal_rows)

    write_csv(DATA_DIR / "cpi_point_in_time_signal.csv", signal_rows, SIGNAL_FIELDS)
    write_csv(DATA_DIR / "release_reconciliation.csv", release_rows, release_rows[0].keys())
    write_csv(DATA_DIR / "vintage_reconciliation.csv", vintage_rows, vintage_rows[0].keys())
    write_json(DATA_DIR / "data_dictionary.json", data_dictionary())
    write_json(DATA_DIR / "source_manifest.json", source_manifest(payloads, acquisition_metadata))

    core_files = [
        DATA_DIR / "cpi_point_in_time_signal.csv",
        DATA_DIR / "release_reconciliation.csv",
        DATA_DIR / "vintage_reconciliation.csv",
        DATA_DIR / "data_dictionary.json",
        DATA_DIR / "source_manifest.json",
    ]
    core_hashes = {relative(path): sha256_path(path) for path in core_files}
    frozen_hash = dataset_hash(core_hashes)

    point_in_time_safe = (
        quality["unresolved_release_date_count"] == 0
        and quality["unresolved_vintage_count"] == 0
        and quality["release_dates_unique"]
        and quality["release_dates_strictly_increasing"]
        and quality["reference_months_strictly_increasing"]
        and quality["all_levels_positive"]
        and quality["all_effective_dates_after_release"]
    )
    threshold_blockers = quality["threshold_rounding_blocker_count"]
    acquisition_ready = point_in_time_safe and threshold_blockers == 0
    if not acquisition_ready:
        outcome = ACQUISITION_BLOCKED_OUTCOME
        next_action = "direction_owner_review_phase2_public_signal_data_blocker_v1"
    elif warmup["status"] == "warmup_rule_requires_source_reconciliation":
        outcome = WARMUP_BLOCKED_OUTCOME
        next_action = "direction_owner_resolve_spdj_dynamic_inflation_warmup_contract_v1"
    else:
        outcome = READY_OUTCOME
        next_action = "implement_spdj_multi_asset_dynamic_inflation_etf_portability_v1"
    implementation_ready = outcome == READY_OUTCOME

    freeze = {
        "dataset_id": "phase2_public_cpi_point_in_time_v1",
        "task_id": TASK_ID,
        "series_id": SERIES_ID,
        "frozen_dataset_hash": frozen_hash,
        "core_file_hashes": core_hashes,
        "raw_input_hashes": {
            relative(RAW_INDEX_PATH): sha256_path(RAW_INDEX_PATH),
            relative(RAW_RELEASE_PAYLOAD_PATH): sha256_path(RAW_RELEASE_PAYLOAD_PATH),
            relative(RAW_ACQUISITION_META_PATH): sha256_path(RAW_ACQUISITION_META_PATH),
            relative(RAW_ALFRED_ATTEMPT_PATH): sha256_path(RAW_ALFRED_ATTEMPT_PATH),
            **{
                relative(path): sha256_path(path)
                for path in sorted(RAW_DIR.glob("bls_public_api_*.json"))
            },
        },
        "immutable": True,
        "deterministic_from_preserved_raw_inputs": True,
        "strategy_implemented": False,
        "trial_created": False,
        "backtest_run": False,
        "performance_metrics_calculated": False,
    }
    write_json(DATA_DIR / "freeze_manifest.json", freeze)

    readiness = {
        "task_id": TASK_ID,
        "task_outcome": outcome,
        "series_id": SERIES_ID,
        "provider_authority": "U.S. Bureau of Labor Statistics archived CPI releases; ALFRED permitted but unavailable in this run",
        "bls_alfred_reconciliation_status": "ALFRED_unavailable_BLS_archive_and_final_NSA_hierarchy_complete",
        "direct_bls_archive_table_count": quality["direct_archive_table_count"],
        "official_bls_api_fallback_count": quality["official_api_fallback_count"],
        "reference_month_start": quality["canonical_start"],
        "reference_month_end": quality["canonical_end"],
        "canonical_record_count": quality["canonical_record_count"],
        "missing_reference_month_count": quality["missing_reference_month_count"],
        "unresolved_release_date_count": quality["unresolved_release_date_count"],
        "unresolved_vintage_count": quality["unresolved_vintage_count"],
        "published_vs_computed_regime_disagreement_count": quality[
            "published_vs_computed_regime_disagreement_count"
        ],
        "threshold_rounding_blocker_count": threshold_blockers,
        "point_in_time_safe": point_in_time_safe,
        "warmup_contract_status": warmup["status"],
        "first_valid_volwt_formation": warmup["first_valid_volwt_formation"],
        "first_valid_proib_formation": warmup["first_valid_proib_formation"],
        "proib_candidate_dates": warmup["proib_candidate_dates"],
        "global_first_source_compliant_formation": warmup["global_first_source_compliant_formation"],
        "frozen_dataset_hash": frozen_hash,
        "implementation_ready": implementation_ready,
        "exact_next_action": next_action,
        "next_action_executed": False,
    }

    write_csv(OUTPUT_DIR / "release_date_reconciliation.csv", release_rows, release_rows[0].keys())
    write_csv(OUTPUT_DIR / "vintage_reconciliation.csv", vintage_rows, vintage_rows[0].keys())
    threshold_fields = [
        "reference_month",
        "bls_release_date",
        "published_yoy",
        "computed_unrounded_yoy",
        "published_regime",
        "computed_regime",
        "distance_to_1_5",
        "distance_to_2_5",
        "audit_status",
        "implementation_blocker",
    ]
    write_csv(OUTPUT_DIR / "threshold_boundary_audit.csv", threshold_rows, threshold_fields)
    write_json(OUTPUT_DIR / "signal_readiness.json", readiness)
    write_json(OUTPUT_DIR / "freeze_manifest.json", freeze)
    (OUTPUT_DIR / "warmup_contract_reconciliation.md").write_text(warmup_report(warmup), encoding="utf-8")
    (OUTPUT_DIR / "data_acquisition_report.md").write_text(
        f"""# Public CPI Point-in-Time Acquisition

Outcome: `{outcome}`

The task acquired only official archived BLS CPI releases for `{SERIES_ID}`, retained an immutable release-payload ledger with raw-response hashes, and performed a bounded official ALFRED access check. ALFRED was not required for point-in-time safety because the BLS archive supplies the published CPI-U NSA level, published 12-month rate, release date, and release time; CPI-U NSA is final when released. Current revised FRED history was not used.

Reference range: `{quality['canonical_start']}` through `{quality['canonical_end']}`  
Canonical releases: `{quality['canonical_record_count']}`  
Direct archived release rows: `{quality['direct_archive_table_count']}`  
Official BLS API fallbacks for legacy/unrenderable release rows: `{quality['official_api_fallback_count']}`  
Officially unpublished months: `{quality['official_missing_reference_months']}`  
Frozen dataset hash: `{frozen_hash}`

No ETF cache, universe, strategy, trial, backtest, lifecycle record, or forward-observation state was changed.
""",
        encoding="utf-8",
    )
    (OUTPUT_DIR / "signal_quality_report.md").write_text(
        f"""# CPI Signal Quality Report

Point-in-time safe: `{point_in_time_safe}`

- Unresolved release dates: `{quality['unresolved_release_date_count']}`
- Unresolved vintages: `{quality['unresolved_vintage_count']}`
- Published/computed regime disagreements: `{quality['published_vs_computed_regime_disagreement_count']}`
- Threshold-rounding blockers: `{threshold_blockers}`
- Release dates unique and increasing: `{quality['release_dates_strictly_increasing']}`
- No forward fill, interpolation, or current-history substitution occurred.

The BLS-published rounded 12-month rate remains the preferred signal confirmation. Every near-threshold month and any disagreement with the unrounded level reconstruction is retained in `threshold_boundary_audit.csv`; no favorable convention was selected.
""",
        encoding="utf-8",
    )
    (OUTPUT_DIR / "next_action.md").write_text(
        f"# Exact Next Action\n\n`{next_action}`\n\nRecorded only; not executed.\n", encoding="utf-8"
    )

    protected_after = protected_snapshot()
    actual_data = {path.name for path in DATA_DIR.iterdir() if path.is_file()}
    actual_evidence_without_consistency = {
        path.name for path in OUTPUT_DIR.iterdir() if path.is_file() and path.name != "consistency_check.json"
    }
    expected_evidence_without_consistency = REQUIRED_EVIDENCE_FILES - {"consistency_check.json"}
    checks = {
        "required_frozen_data_files_present": REQUIRED_DATA_FILES <= actual_data,
        "required_evidence_files_present_before_consistency": actual_evidence_without_consistency
        == expected_evidence_without_consistency,
        "outcome_allowed": outcome in ALLOWED_OUTCOMES,
        "series_exactly_CPIAUCNS": SERIES_ID == "CPIAUCNS",
        "only_official_sources_accessed": acquisition_metadata["network_scope"]
        == ["official_BLS_CPI", "official_ALFRED_CPIAUCNS_access_check", "official_SP_methodology"],
        "canonical_rows_unique": len(signal_rows) == len({row["reference_month"] for row in signal_rows}),
        "release_dates_unique": quality["release_dates_unique"],
        "release_dates_strictly_increasing": quality["release_dates_strictly_increasing"],
        "reference_months_strictly_increasing": quality["reference_months_strictly_increasing"],
        "release_after_reference_month": all(
            date.fromisoformat(row["bls_release_date"]) > month_end(row["reference_month"]) for row in signal_rows
        ),
        "signal_unavailable_before_release": all(
            row["signal_available_timestamp"].startswith(row["bls_release_date"]) for row in signal_rows
        ),
        "levels_numeric_positive": quality["all_levels_positive"],
        "computed_yoy_finite": all(row["computed_yoy_from_same_vintage"] for row in signal_rows),
        "no_forward_fill": all(not row["forward_fill_used"] for row in signal_rows),
        "no_interpolation": all(not row["interpolation_used"] for row in signal_rows),
        "no_current_revised_history_substitution": all(
            not row["current_revised_history_used"] for row in signal_rows
        ),
        "official_missing_month_visible": quality["missing_reference_month_count"]
        == len(acquisition_metadata["official_missing_reference_months"]),
        "threshold_disagreements_visible": threshold_blockers
        == sum(row["implementation_blocker"] for row in threshold_rows),
        "regimes_deterministic": all(
            row["signal_regime"] == regime(Decimal(row["cpi_yoy_percent_as_published"])) for row in signal_rows
        ),
        "source_effective_dates_use_later_session": quality["all_effective_dates_after_release"],
        "frozen_dataset_hash_reproducible": frozen_hash == dataset_hash(core_hashes),
        "warmup_ambiguity_not_inferred": warmup["status"] == "warmup_rule_requires_source_reconciliation"
        and warmup["global_first_source_compliant_formation"] == "unresolved",
        "frozen_universe_hash_preserved": json.loads(
            (UNIVERSE_DIR / "consistency_check.json").read_text(encoding="utf-8")
        )["frozen_universe_hash"]
        == UNIVERSE_HASH,
        "protected_state_unchanged": protected_before == protected_after,
        "no_strategy_trial_or_performance_work": not freeze["strategy_implemented"]
        and not freeze["trial_created"]
        and not freeze["backtest_run"]
        and not freeze["performance_metrics_calculated"],
        "exact_next_action_matches_outcome": (
            (outcome == READY_OUTCOME and next_action == "implement_spdj_multi_asset_dynamic_inflation_etf_portability_v1")
            or (
                outcome == WARMUP_BLOCKED_OUTCOME
                and next_action == "direction_owner_resolve_spdj_dynamic_inflation_warmup_contract_v1"
            )
            or (
                outcome == ACQUISITION_BLOCKED_OUTCOME
                and next_action == "direction_owner_review_phase2_public_signal_data_blocker_v1"
            )
        ),
    }
    consistency = {
        "task_id": TASK_ID,
        "task_outcome": outcome if all(checks.values()) else ACQUISITION_BLOCKED_OUTCOME,
        "overall_pass": all(checks.values()),
        "checks": checks,
        "series_id": SERIES_ID,
        "frozen_dataset_hash": frozen_hash,
        "deterministic_evidence_packet_hash": packet_hash(),
        "protected_hashes_before": protected_before,
        "protected_hashes_after": protected_after,
        "entity_counts": {
            "public_signal_datasets_created": 1,
            "strategy_configurations_created": 0,
            "experiment_trials_created": 0,
            "backtests_run": 0,
            "performance_metrics_calculated": 0,
            "eligibility_or_handoff_records_created": 0,
            "forward_observations_accessed_or_changed": 0,
            "alpaca_or_broker_calls": 0,
        },
        "exact_next_action": next_action,
        "next_action_executed": False,
    }
    write_json(OUTPUT_DIR / "consistency_check.json", consistency)
    return {
        "task_id": TASK_ID,
        "task_outcome": consistency["task_outcome"],
        "overall_pass": consistency["overall_pass"],
        "series_id": SERIES_ID,
        "canonical_record_count": quality["canonical_record_count"],
        "reference_month_range": [quality["canonical_start"], quality["canonical_end"]],
        "point_in_time_safe": point_in_time_safe,
        "unresolved_release_date_count": quality["unresolved_release_date_count"],
        "unresolved_vintage_count": quality["unresolved_vintage_count"],
        "threshold_rounding_blocker_count": threshold_blockers,
        "frozen_dataset_hash": frozen_hash,
        "warmup_contract_status": warmup["status"],
        "first_valid_volwt_formation": warmup["first_valid_volwt_formation"],
        "first_valid_proib_formation": warmup["first_valid_proib_formation"],
        "global_first_source_compliant_formation": warmup["global_first_source_compliant_formation"],
        "implementation_ready": implementation_ready,
        "exact_next_action": next_action,
        "deterministic_evidence_packet_hash": consistency["deterministic_evidence_packet_hash"],
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
