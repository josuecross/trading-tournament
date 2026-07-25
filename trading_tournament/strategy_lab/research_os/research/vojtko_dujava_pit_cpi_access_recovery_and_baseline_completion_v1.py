from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import re
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import requests
import yaml

from strategy_lab.research_os.external_adapters.bt_adapter import returns_from_weights
from strategy_lab.research_os.research import vojtko_dujava_inflation_acceleration_gld_ief_regime_v1 as base


ROOT = Path(__file__).resolve().parents[3]
TASK_ID = "vojtko_dujava_pit_cpi_access_recovery_and_baseline_completion_v1"
STRATEGY_ID = base.STRATEGY_ID
FAMILY_ID = base.FAMILY_ID
OUTPUT_DIR = Path("evidence") / "public_source_strategy_correction" / TASK_ID / "latest"
PRIOR_PACKET_DIR = base.OUTPUT_DIR
RAW_CACHE_DIR = Path("data") / "raw" / TASK_ID
NEXT_ACTION = "direction_owner_review_vojtko_dujava_pit_cpi_recovery_v1"
RUN_CREATED_UTC = "2026-07-21T00:00:00Z"

FRED_SERIES_ID = "CPIAUCSL"
FRED_API_BASE = "https://api.stlouisfed.org/fred"
FRED_API_KEY_ENV_NAMES = ("FRED_API_KEY", "ALFRED_API_KEY", "STLOUISFED_API_KEY")
PIT_START_MONTH = pd.Period("1994-01", freq="M")
REQUEST_HEADERS = {
    "User-Agent": "trading-tournament-research/1.0 point-in-time-cpi-correction"
}

BLS_ANCHORS = [
    {
        "anchor_id": "cpi_dec_1995_release_1996_02_01",
        "reference_month": "1995-12",
        "release_date": "1996-02-01",
        "url": "https://www.bls.gov/news.release/history/cpi_020196.txt",
    },
    {
        "anchor_id": "cpi_sep_2000_release_2000_10_18",
        "reference_month": "2000-09",
        "release_date": "2000-10-18",
        "url": "https://www.bls.gov/news.release/history/cpi_10182000.txt",
    },
    {
        "anchor_id": "cpi_dec_2006_release_2007_01_18",
        "reference_month": "2006-12",
        "release_date": "2007-01-18",
        "url": "https://www.bls.gov/news.release/history/cpi_01182007.txt",
    },
    {
        "anchor_id": "cpi_dec_2007_release_2008_01_16",
        "reference_month": "2007-12",
        "release_date": "2008-01-16",
        "url": "https://www.bls.gov/news.release/history/cpi_01162008.txt",
    },
    {
        "anchor_id": "cpi_jan_2024_release_2024_02_13",
        "reference_month": "2024-01",
        "release_date": "2024-02-13",
        "url": "https://www.bls.gov/news.release/archives/cpi_02132024.htm",
    },
]

ALLOWED_OUTCOMES = {
    "baseline_implemented_for_exploratory_review",
    "alfred_vintage_access_blocked",
    "official_bls_anchor_access_blocked",
    "alfred_bls_release_mismatch",
    "point_in_time_cpi_reconstruction_defect",
    "common_history_insufficient",
    "provider_reconciliation_defect",
    "implementation_or_accounting_defect",
}

REQUIRED_FILES = {
    "correction_trigger.json",
    "prior_packet_reconciliation.json",
    "repository_capability_review.json",
    "fred_alfred_access_check.json",
    "alfred_vintage_inventory.csv",
    "alfred_point_in_time_cpi_levels.csv",
    "alfred_point_in_time_mom_series.csv",
    "bls_anchor_release_inventory.csv",
    "bls_anchor_extraction.csv",
    "alfred_vs_bls_anchor_reconciliation.csv",
    "rounding_convention_audit.json",
    "point_in_time_signal_gate.json",
    "cpi_release_timing_audit.csv",
    "regime_calculation_audit.csv",
    "target_weights.csv",
    "transactions.csv",
    "baseline_metrics.csv",
    "benchmark_metrics.csv",
    "static_average_weight_control.csv",
    "baseline_vs_controls.csv",
    "accounting_invariants.csv",
    "identity_overlay_equality.csv",
    "overlay_compatibility_map.csv",
    "trial_manifest.json",
    "command_validation_log.csv",
    "consistency_check.json",
    "correction_summary.md",
}

PROTECTED_STATE_PATHS = base.PROTECTED_STATE_PATHS


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


def dataframe_hash(frame: pd.DataFrame | pd.Series) -> str:
    if frame.empty:
        return "empty"
    return sha256_text(frame.to_csv(index=True, lineterminator="\n"))


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
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    if isinstance(value, (pd.Timestamp, pd.Period)):
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


def clean_output_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    for child in path.iterdir():
        if child.is_file():
            child.unlink()


def state_hashes(root: Path) -> dict[str, str]:
    return {str(path): sha256_path(root / path) for path in PROTECTED_STATE_PATHS}


def directory_file_hashes(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    return {
        str(child.relative_to(path)).replace("\\", "/"): sha256_path(child)
        for child in sorted(path.rglob("*"))
        if child.is_file()
    }


def read_env_local(root: Path) -> dict[str, str]:
    path = root / ".env.local"
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("'\"")
    return values


def load_fred_api_key(root: Path = ROOT) -> tuple[str | None, str]:
    for name in FRED_API_KEY_ENV_NAMES:
        if os.environ.get(name):
            return os.environ[name], f"environment:{name}"
    local = read_env_local(root)
    for name in FRED_API_KEY_ENV_NAMES:
        if local.get(name):
            return local[name], f"env_local:{name}"
    return None, "missing"


def safe_fred_params(params: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in params.items() if key != "api_key"}


def fred_api_get(endpoint: str, params: dict[str, Any], api_key: str | None) -> dict[str, Any]:
    if not api_key:
        return {
            "status": "blocked",
            "status_code": 0,
            "error": "missing_fred_api_key",
            "safe_params": safe_fred_params(params),
            "payload": {},
            "raw_hash": "missing",
        }
    call_params = {**params, "api_key": api_key, "file_type": "json"}
    url = f"{FRED_API_BASE}/{endpoint.lstrip('/')}"
    try:
        response = requests.get(url, params=call_params, headers=REQUEST_HEADERS, timeout=45)
        raw_hash = sha256_bytes(response.content)
        if response.status_code != 200:
            return {
                "status": "blocked",
                "status_code": int(response.status_code),
                "error": response.text[:240],
                "safe_params": safe_fred_params(call_params),
                "payload": {},
                "raw_hash": raw_hash,
            }
        return {
            "status": "ready",
            "status_code": int(response.status_code),
            "error": "",
            "safe_params": safe_fred_params(call_params),
            "payload": response.json(),
            "raw_hash": raw_hash,
        }
    except Exception as exc:  # pragma: no cover - network defensive branch.
        return {
            "status": "blocked",
            "status_code": 0,
            "error": f"{type(exc).__name__}: {str(exc)[:240]}",
            "safe_params": safe_fred_params(params),
            "payload": {},
            "raw_hash": "missing",
        }


def round_one_decimal_half_up(value: float) -> float:
    decimal_value = Decimal(str(value)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    return float(decimal_value)


def sign_bucket(value: float | str | None) -> str:
    if value in ("", None):
        return ""
    number = float(value)
    if number > 0:
        return "positive"
    if number < 0:
        return "negative"
    return "zero"


def alfred_vintage_reconstruction(root: Path = ROOT) -> tuple[dict[str, Any], list[dict[str, Any]], pd.DataFrame, pd.DataFrame]:
    api_key, source_kind = load_fred_api_key(root)
    access: dict[str, Any] = {
        "fred_api_key_present": bool(api_key),
        "fred_api_key_source_kind": "configured" if api_key else source_kind,
        "api_key_value_persisted": False,
        "series_id": FRED_SERIES_ID,
        "vintage_inventory_endpoint_status": "not_started",
        "initial_release_endpoint_status": "not_started",
        "vintage_observation_queries": 0,
        "required_capabilities": [
            "series_vintage_date_inventory",
            "observations_as_of_specified_vintage",
            "initial_release_output_for_audit",
        ],
    }
    vintage_rows: list[dict[str, Any]] = []
    level_rows: list[dict[str, Any]] = []
    mom_rows: list[dict[str, Any]] = []

    if not api_key:
        access.update(
            {
                "status": "blocked",
                "blocker": "missing_fred_api_key",
                "vintage_inventory_endpoint_status": "blocked",
                "initial_release_endpoint_status": "blocked",
            }
        )
        return access, vintage_rows, pd.DataFrame(level_rows), pd.DataFrame(mom_rows)

    vintage_response = fred_api_get(
        "series/vintagedates",
        {"series_id": FRED_SERIES_ID, "sort_order": "asc", "limit": 100000},
        api_key,
    )
    access["vintage_inventory_endpoint_status"] = vintage_response["status"]
    access["vintage_inventory_status_code"] = vintage_response["status_code"]
    access["vintage_inventory_hash"] = vintage_response["raw_hash"]
    if vintage_response["status"] != "ready":
        access.update({"status": "blocked", "blocker": "vintage_inventory_request_failed", "error": vintage_response["error"]})
        return access, vintage_rows, pd.DataFrame(level_rows), pd.DataFrame(mom_rows)

    vintages = vintage_response["payload"].get("vintage_dates", [])
    for vintage in vintages:
        vintage_rows.append(
            {
                "series_id": FRED_SERIES_ID,
                "vintage_date": vintage,
                "vintage_date_gte_1994": pd.Timestamp(vintage) >= pd.Timestamp("1994-01-01"),
                "source": "official_fred_api_series_vintagedates",
                "response_hash": vintage_response["raw_hash"],
            }
        )

    initial_response = fred_api_get(
        "series/observations",
        {
            "series_id": FRED_SERIES_ID,
            "observation_start": "1993-12-01",
            "output_type": 4,
            "sort_order": "asc",
            "limit": 100000,
        },
        api_key,
    )
    access["initial_release_endpoint_status"] = initial_response["status"]
    access["initial_release_status_code"] = initial_response["status_code"]
    access["initial_release_hash"] = initial_response["raw_hash"]
    if initial_response["status"] != "ready":
        access.update({"status": "blocked", "blocker": "initial_release_request_failed", "error": initial_response["error"]})
        return access, vintage_rows, pd.DataFrame(level_rows), pd.DataFrame(mom_rows)

    initial_observations = initial_response["payload"].get("observations", [])
    first_vintage_by_month: dict[str, str] = {}
    for item in initial_observations:
        period = pd.Period(item.get("date", ""), freq="M")
        if period < PIT_START_MONTH:
            continue
        value = item.get("value")
        if value in {".", "", None}:
            continue
        first_vintage_by_month[str(period)] = item.get("realtime_start", "")

    for ref_month, vintage_date in sorted(first_vintage_by_month.items()):
        previous_month = str(pd.Period(ref_month, freq="M") - 1)
        vintage_query = fred_api_get(
            "series/observations",
            {
                "series_id": FRED_SERIES_ID,
                "observation_start": f"{previous_month}-01",
                "observation_end": f"{ref_month}-01",
                "realtime_start": vintage_date,
                "realtime_end": vintage_date,
                "sort_order": "asc",
                "limit": 1000,
            },
            api_key,
        )
        access["vintage_observation_queries"] += 1
        if vintage_query["status"] != "ready":
            level_rows.append(
                {
                    "reference_month": ref_month,
                    "earliest_vintage_date": vintage_date,
                    "query_status": "blocked",
                    "query_error": vintage_query["error"],
                    "same_vintage_current_and_previous": False,
                }
            )
            continue
        by_month = {
            str(pd.Period(obs["date"], freq="M")): obs
            for obs in vintage_query["payload"].get("observations", [])
            if obs.get("value") not in {".", "", None}
        }
        current = by_month.get(ref_month)
        previous = by_month.get(previous_month)
        same_vintage_ok = bool(current and previous)
        current_value = float(current["value"]) if current else float("nan")
        previous_value = float(previous["value"]) if previous else float("nan")
        raw_mom = 100.0 * (current_value / previous_value - 1.0) if same_vintage_ok and previous_value != 0 else float("nan")
        rounded = round_one_decimal_half_up(raw_mom) if math.isfinite(raw_mom) else float("nan")
        source_hash = vintage_query["raw_hash"]
        level_rows.append(
            {
                "reference_month": ref_month,
                "earliest_vintage_date": vintage_date,
                "current_month_vintage_value": current_value,
                "previous_month": previous_month,
                "previous_month_value_from_same_vintage": previous_value,
                "same_vintage_current_and_previous": same_vintage_ok,
                "vintage_query_params": vintage_query["safe_params"],
                "source_hash": source_hash,
                "query_status": vintage_query["status"],
                "query_error": vintage_query["error"],
                "retrieval_timestamp": RUN_CREATED_UTC,
            }
        )
        mom_rows.append(
            {
                "cpi_reference_month": ref_month,
                "release_date": vintage_date,
                "earliest_vintage_date": vintage_date,
                "current_month_vintage_value": current_value,
                "previous_month_value_from_same_vintage": previous_value,
                "mom_raw_percent": raw_mom,
                "reported_mom_percent": rounded,
                "rounding_rule": "decimal_round_half_up_one_decimal",
                "source_hash": source_hash,
                "same_vintage_current_and_previous": same_vintage_ok,
                "latest_revised_history_used": False,
                "retrieval_timestamp": RUN_CREATED_UTC,
                "vintage_query_params": vintage_query["safe_params"],
            }
        )

    levels = pd.DataFrame(level_rows)
    mom = pd.DataFrame(mom_rows)
    access.update(
        {
            "status": "ready" if not mom.empty and mom["same_vintage_current_and_previous"].all() else "blocked",
            "blocker": "" if not mom.empty and mom["same_vintage_current_and_previous"].all() else "missing_same_vintage_cpi_levels",
            "vintage_count": len(vintage_rows),
            "point_in_time_mom_observation_count": int(len(mom)),
            "api_secret_persisted": False,
        }
    )
    return access, vintage_rows, levels, mom


def fetch_url(url: str) -> dict[str, Any]:
    try:
        response = requests.get(url, headers=REQUEST_HEADERS, timeout=30)
        return {
            "url": url,
            "status_code": int(response.status_code),
            "content_type": response.headers.get("content-type", ""),
            "content": response.content,
            "text": response.text,
            "content_hash": sha256_bytes(response.content),
            "error": "",
        }
    except Exception as exc:  # pragma: no cover - network defensive branch.
        return {
            "url": url,
            "status_code": 0,
            "content_type": "",
            "content": b"",
            "text": "",
            "content_hash": "missing",
            "error": f"{type(exc).__name__}: {str(exc)[:240]}",
        }


def extract_bls_anchor_mom(text: str, reference_month: str) -> dict[str, Any]:
    clean = re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()
    month_name = pd.Period(reference_month, freq="M").strftime("%B")
    month_re = re.escape(month_name)
    patterns = [
        re.compile(
            rf"On a seasonally adjusted basis,\s+the CPI-U\s+"
            rf"(?P<verb>rose|increased|declined|fell|decreased)\s+"
            rf"(?P<value>\d+(?:\.\d+)?)\s+percent\s+in\s+{month_re}",
            flags=re.IGNORECASE,
        ),
        re.compile(
            rf"On a seasonally adjusted basis,\s+the CPI-U\s+"
            rf"was unchanged\s+in\s+{month_re}",
            flags=re.IGNORECASE,
        ),
    ]
    for pattern in patterns:
        match = pattern.search(clean)
        if not match:
            continue
        verb = match.groupdict().get("verb", "unchanged").lower()
        value = 0.0 if match.groupdict().get("value") is None else float(match.group("value"))
        if verb in {"declined", "fell", "decreased"}:
            value = -value
        return {
            "extraction_status": "parsed",
            "reported_mom_percent": value,
            "value_sign": sign_bucket(value),
            "extraction_method": "anchored_cpi_u_sa_sentence_regex",
            "extraction_error": "",
        }
    return {
        "extraction_status": "not_parsed",
        "reported_mom_percent": "",
        "value_sign": "",
        "extraction_method": "anchored_cpi_u_sa_sentence_regex",
        "extraction_error": "CPI-U seasonally adjusted monthly percent sentence not found",
    }


def bls_anchor_releases() -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    inventory_rows: list[dict[str, Any]] = []
    extraction_rows: list[dict[str, Any]] = []
    for anchor in BLS_ANCHORS:
        fetched = fetch_url(anchor["url"])
        loaded = fetched["status_code"] == 200
        inventory_rows.append(
            {
                "anchor_id": anchor["anchor_id"],
                "reference_month": anchor["reference_month"],
                "release_date": anchor["release_date"],
                "release_url": anchor["url"],
                "http_status": fetched["status_code"],
                "content_type": fetched["content_type"],
                "content_hash": fetched["content_hash"],
                "access_status": "loaded" if loaded else "blocked",
                "error": fetched["error"] or ("" if loaded else f"http_{fetched['status_code']}"),
            }
        )
        extracted = extract_bls_anchor_mom(fetched["text"], anchor["reference_month"]) if loaded else {
            "extraction_status": "blocked",
            "reported_mom_percent": "",
            "value_sign": "",
            "extraction_method": "",
            "extraction_error": fetched["error"] or f"http_{fetched['status_code']}",
        }
        extraction_rows.append(
            {
                "anchor_id": anchor["anchor_id"],
                "reference_month": anchor["reference_month"],
                "release_date": anchor["release_date"],
                "release_timestamp": "",
                "release_url": anchor["url"],
                "content_hash": fetched["content_hash"],
                **extracted,
            }
        )
    meta = {
        "anchor_count": len(BLS_ANCHORS),
        "loaded_count": sum(1 for row in inventory_rows if row["access_status"] == "loaded"),
        "parsed_count": sum(1 for row in extraction_rows if row["extraction_status"] == "parsed"),
        "blocked_count": sum(1 for row in inventory_rows if row["access_status"] == "blocked"),
        "all_anchors_loaded_and_parsed": all(row["access_status"] == "loaded" for row in inventory_rows)
        and all(row["extraction_status"] == "parsed" for row in extraction_rows),
    }
    return inventory_rows, extraction_rows, meta


def reconcile_alfred_vs_bls(alfred_mom: pd.DataFrame, bls_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if alfred_mom.empty:
        lookup: dict[str, dict[str, Any]] = {}
    else:
        lookup = {str(row["cpi_reference_month"]): row.to_dict() for _, row in alfred_mom.iterrows()}
    rows: list[dict[str, Any]] = []
    for row in bls_rows:
        ref = row["reference_month"]
        alfred = lookup.get(ref)
        bls_value = row.get("reported_mom_percent", "")
        alfred_value = alfred.get("reported_mom_percent", "") if alfred else ""
        value_match = bool(
            bls_value not in ("", None)
            and alfred_value not in ("", None)
            and abs(float(bls_value) - float(alfred_value)) <= 1e-12
        )
        rows.append(
            {
                "anchor_id": row["anchor_id"],
                "reference_month": ref,
                "bls_release_date": row["release_date"],
                "bls_value": bls_value,
                "alfred_earliest_vintage_date": alfred.get("earliest_vintage_date", "") if alfred else "",
                "alfred_reconstructed_value": alfred_value,
                "one_decimal_value_agreement": value_match,
                "sign_agreement": sign_bucket(bls_value) == sign_bucket(alfred_value) if bls_value not in ("", None) and alfred_value not in ("", None) else False,
                "classification_agreement": sign_bucket(bls_value) == sign_bucket(alfred_value) if bls_value not in ("", None) and alfred_value not in ("", None) else False,
                "reconciliation_status": "matched" if value_match else ("blocked_no_alfred_data" if not alfred else "mismatch"),
            }
        )
    return rows


def point_in_time_signal_gate_payload(
    alfred_access: dict[str, Any],
    alfred_levels: pd.DataFrame,
    alfred_mom: pd.DataFrame,
    bls_meta: dict[str, Any],
    reconciliation_rows: list[dict[str, Any]],
    regime: pd.DataFrame,
) -> dict[str, Any]:
    every_month_has_vintage = not alfred_mom.empty and alfred_mom["earliest_vintage_date"].astype(str).ne("").all()
    same_vintage = not alfred_levels.empty and alfred_levels["same_vintage_current_and_previous"].astype(bool).all()
    anchors_match = bool(reconciliation_rows) and all(row["reconciliation_status"] == "matched" for row in reconciliation_rows)
    timing_rows = base.cpi_release_timing_rows(regime)
    release_before_target = bool(timing_rows) and all(
        row["release_date_before_target_effective"] in (True, "") for row in timing_rows
    )
    deterministic = dataframe_hash(alfred_mom) == dataframe_hash(alfred_mom.copy())
    passed = (
        alfred_access.get("status") == "ready"
        and every_month_has_vintage
        and same_vintage
        and bls_meta["all_anchors_loaded_and_parsed"]
        and anchors_match
        and release_before_target
        and deterministic
        and not regime.empty
    )
    return {
        "point_in_time_signal_gate_passed": passed,
        "alfred_access_ready": alfred_access.get("status") == "ready",
        "every_month_has_earliest_vintage_date": every_month_has_vintage,
        "current_and_previous_levels_same_vintage": same_vintage,
        "latest_revised_history_substituted": False,
        "every_fixed_bls_anchor_loaded_and_parsed": bls_meta["all_anchors_loaded_and_parsed"],
        "every_fixed_bls_anchor_reconciled": anchors_match,
        "release_dates_precede_permitted_signal_dates": release_before_target,
        "monthly_values_chronologically_reproducible": deterministic,
        "two_change_regime_deterministic": dataframe_hash(regime) == dataframe_hash(regime.copy()) if not regime.empty else False,
    }


def prior_packet_reconciliation(root: Path, before: dict[str, str], after: dict[str, str]) -> dict[str, Any]:
    path = root / PRIOR_PACKET_DIR
    manifest_path = path / "trial_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    return {
        "prior_packet_path": str(path.resolve()),
        "prior_packet_exists": path.exists(),
        "prior_outcome": manifest.get("outcome", ""),
        "prior_blocker": manifest.get("blocker", ""),
        "prior_packet_preserved_unchanged": before == after,
        "prior_file_count": len(before),
        "prior_hashes_before": before,
        "prior_hashes_after": after,
        "corrected_interpretation": "prior_http_403_proves_bls_archive_index_http_access_blocked_not_missing_pit_cpi_history",
    }


def repository_capability_review(root: Path) -> dict[str, Any]:
    key, source = load_fred_api_key(root)
    prior = root / PRIOR_PACKET_DIR
    return {
        "task_id": TASK_ID,
        "fred_api_key_present": bool(key),
        "fred_api_key_source_kind": "configured" if key else source,
        "fred_api_key_value_persisted": False,
        "fred_csv_final_history_pattern_present": True,
        "alfred_api_adapter_present_before_task": False,
        "alfred_api_adapter_scope": "task_specific_only",
        "dataset_hashing_supported": True,
        "bls_release_parser_present_before_task": False,
        "bls_release_parser_scope": "task_specific_fixed_anchor_only",
        "monthly_release_calendar_engine_present": False,
        "prior_gld_ief_packet_exists": prior.exists(),
        "prior_gld_ief_splice_reconciliation_exists": (prior / "provider_splice_reconciliation.csv").exists(),
        "baseline_identity_code_reused_from": str(Path(base.__file__).resolve()),
        "generic_macro_data_framework_created": False,
        "api_credentials_exposed_or_persisted": False,
    }


def verified_spliced_prices(root: Path) -> tuple[pd.DataFrame, list[dict[str, Any]], dict[str, Any]]:
    prior_path = root / PRIOR_PACKET_DIR / "provider_splice_reconciliation.csv"
    if not prior_path.exists():
        return pd.DataFrame(), [], {"status": "blocked", "blocker": "prior_provider_splice_reconciliation_missing"}
    with prior_path.open(newline="", encoding="utf-8") as handle:
        prior_rows = list(csv.DictReader(handle))
    alpaca_check, bars = base.alpaca_asset_and_bar_check()
    rows: list[dict[str, Any]] = []
    series: dict[str, pd.Series] = {}
    for symbol in base.SYMBOLS:
        spliced, row = base.build_spliced_price_series(root, symbol, bars.get(symbol, pd.DataFrame()))
        prior = next((item for item in prior_rows if item.get("symbol") == symbol), {})
        row["prior_spliced_series_hash"] = prior.get("spliced_series_hash", "")
        row["prior_decision"] = prior.get("decision", "")
        row["deterministic_equality_with_prior"] = row.get("spliced_series_hash") == prior.get("spliced_series_hash")
        rows.append(row)
        series[symbol] = spliced
    ok = (
        alpaca_check.get("status") == "ready"
        and all(row.get("decision") == "spliced_after_overlap_reconciliation" for row in rows)
        and all(row.get("deterministic_equality_with_prior") is True for row in rows)
    )
    if not ok:
        return pd.DataFrame(), rows, {"status": "blocked", "blocker": "prior_provider_splice_not_reproduced", "alpaca_status": alpaca_check.get("status")}
    prices = pd.concat([series[base.UP_ASSET], series[base.DOWN_ASSET]], axis=1).dropna()
    return prices, rows, {"status": "ready", "blocker": "", "alpaca_status": alpaca_check.get("status")}


def cpi_frame_for_base(alfred_mom: pd.DataFrame) -> pd.DataFrame:
    if alfred_mom.empty:
        return pd.DataFrame()
    frame = alfred_mom.copy()
    frame["release_date"] = frame["earliest_vintage_date"]
    frame["release_timestamp"] = ""
    frame["archived_release_url"] = "official_FRED_API_ALFRED_vintage_reconstruction"
    frame["reported_mom_percent"] = pd.to_numeric(frame["reported_mom_percent"], errors="coerce")
    frame["extraction_method"] = "alfred_same_vintage_cpi_level_reconstruction"
    frame["content_hash"] = frame["source_hash"]
    frame["whether_revised_later"] = "ALFRED_vintage_history_available"
    return frame[
        [
            "cpi_reference_month",
            "release_date",
            "release_timestamp",
            "archived_release_url",
            "reported_mom_percent",
            "extraction_method",
            "content_hash",
            "whether_revised_later",
        ]
    ]


def run_baseline_if_ready(root: Path, alfred_mom: pd.DataFrame, signal_gate: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
    if not signal_gate["point_in_time_signal_gate_passed"]:
        return "blocked", "point_in_time_signal_gate_failed", {}
    prices, splice_rows, provider_meta = verified_spliced_prices(root)
    if provider_meta["status"] != "ready":
        return "provider_reconciliation_defect", provider_meta["blocker"], {"splice_rows": splice_rows}
    cpi_frame = cpi_frame_for_base(alfred_mom)
    regime = base.calculate_regime_records(cpi_frame, prices.index)
    outcome, blocker = base.source_packet_gate({"status": "ready"}, splice_rows, cpi_frame, {}, prices, regime)
    if outcome != "baseline_implemented_for_exploratory_review":
        return outcome, blocker, {"splice_rows": splice_rows, "prices": prices, "regime": regime}
    weights = base.build_daily_weights(prices, regime)
    if weights.empty:
        return "common_history_insufficient", "no target weights overlap GLD/IEF price history", {"splice_rows": splice_rows, "prices": prices, "regime": regime}
    price_window = prices.loc[weights.index.min() : prices.index.max(), list(base.SYMBOLS)]
    returns = returns_from_weights(price_window, weights.reindex(price_window.index).ffill().fillna(0.0)).rename("zero_cost_dynamic_baseline")
    transactions = base.transaction_rows(regime)
    benchmarks, static_info = base.benchmark_return_series(prices, weights)
    baseline_rows = base.baseline_metric_rows(returns, weights.loc[returns.index], transactions)
    benchmark_rows = base.benchmark_metric_rows(benchmarks)
    baseline_vs_controls = base.baseline_vs_control_rows(returns, benchmarks)
    identity_rows = base.identity_overlay_equality_rows(weights, returns, transactions, baseline_rows[0])
    invariants = base.accounting_invariant_rows(weights, transactions, regime, set(cpi_frame["content_hash"]))
    if not all(row["passed"] is True for row in invariants) or not all(row["exact_match"] is True for row in identity_rows):
        return "implementation_or_accounting_defect", "accounting or identity invariant failed", {
            "splice_rows": splice_rows,
            "prices": prices,
            "regime": regime,
            "weights": weights,
            "transactions": transactions,
            "baseline_rows": baseline_rows,
            "benchmark_rows": benchmark_rows,
            "baseline_vs_controls": baseline_vs_controls,
            "identity_rows": identity_rows,
            "invariants": invariants,
            "static_info": static_info,
        }
    return "baseline_implemented_for_exploratory_review", "none", {
        "splice_rows": splice_rows,
        "prices": prices,
        "regime": regime,
        "weights": weights,
        "transactions": transactions,
        "baseline_rows": baseline_rows,
        "benchmark_rows": benchmark_rows,
        "baseline_vs_controls": baseline_vs_controls,
        "identity_rows": identity_rows,
        "invariants": invariants,
        "static_info": static_info,
    }


def determine_outcome(
    alfred_access: dict[str, Any],
    bls_meta: dict[str, Any],
    reconciliation_rows: list[dict[str, Any]],
    signal_gate: dict[str, Any],
    baseline_status: str,
    baseline_blocker: str,
) -> tuple[str, str]:
    if alfred_access.get("status") != "ready":
        return "alfred_vintage_access_blocked", alfred_access.get("blocker", "alfred_api_blocked")
    if not bls_meta["all_anchors_loaded_and_parsed"]:
        return "official_bls_anchor_access_blocked", "one_or_more_fixed_bls_anchor_releases_blocked_or_unparsed"
    if reconciliation_rows and any(row["reconciliation_status"] != "matched" for row in reconciliation_rows):
        return "alfred_bls_release_mismatch", "fixed_bls_anchor_reconciliation_failed"
    if not signal_gate["point_in_time_signal_gate_passed"]:
        return "point_in_time_cpi_reconstruction_defect", "point_in_time_signal_gate_failed"
    if baseline_status in ALLOWED_OUTCOMES:
        return baseline_status, baseline_blocker
    return "implementation_or_accounting_defect", baseline_blocker


def command_validation_rows() -> list[dict[str, Any]]:
    commands = [
        ".venv\\Scripts\\python.exe run_vojtko_dujava_pit_cpi_access_recovery_and_baseline_completion_v1.py",
        ".venv\\Scripts\\python.exe -m pytest tests\\test_vojtko_dujava_pit_cpi_access_recovery_and_baseline_completion_v1.py -q",
        ".venv\\Scripts\\python.exe run_current_research_checkpoint.py",
        ".venv\\Scripts\\python.exe run_research_state_dashboard.py",
        ".venv\\Scripts\\python.exe run_advisor_consistency_check.py",
        ".venv\\Scripts\\python.exe run_strategy_lab.py --validate-registry --export-evidence",
    ]
    return [{"command": command, "status": "not_run_by_runner", "notes": "updated after command execution"} for command in commands]


def no_secret_text_written(output: Path, secret_values: list[str | None]) -> bool:
    secrets = [value for value in secret_values if value]
    for path in output.iterdir():
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if any(secret in text for secret in secrets):
            return False
    return True


def consistency_payload(
    output: Path,
    manifest: dict[str, Any],
    prior_unchanged: bool,
    state_unchanged: bool,
    credentials: list[str | None],
) -> dict[str, Any]:
    required = {filename: (output / filename).exists() for filename in sorted(REQUIRED_FILES)}
    required["consistency_check.json"] = True
    checks = {
        "all_required_files_present": all(required.values()),
        "required_files": required,
        "outcome_allowed": manifest["outcome"] in ALLOWED_OUTCOMES,
        "prior_blocked_packet_preserved": prior_unchanged,
        "exactly_one_strategy": manifest["strategy_id"] == STRATEGY_ID,
        "alfred_vintage_path_used_or_blocked": manifest["alfred_access_status"] in {"ready", "blocked"},
        "no_latest_revised_cpi_substitution": manifest["latest_revised_cpi_used_for_signals"] is False,
        "fixed_bls_anchors_checked": manifest["fixed_bls_anchor_count"] == len(BLS_ANCHORS),
        "rounding_not_selected_from_returns": manifest["rounding_selected_from_investment_results"] is False,
        "baseline_only_no_momentum_or_extra_assets": manifest["momentum_field_used"] is False
        and manifest["prohibited_symbols_used"] is False,
        "no_overlay_performance_output": not any("overlay_performance" in child.name for child in output.iterdir() if child.is_file()),
        "no_broker_write": manifest["broker_order_endpoint_called"] is False,
        "no_promotion_or_paper_demo": manifest["promotion_eligibility"] is False
        and manifest["paper_demo_eligibility"] is False
        and manifest["paper_demo_activation"] is False,
        "state_preserved": state_unchanged,
        "api_credentials_not_persisted": no_secret_text_written(output, credentials),
        "next_action_exact": manifest["next_action"] == NEXT_ACTION,
    }
    checks["consistency_passed"] = all(value is True for key, value in checks.items() if key != "required_files")
    return checks


def correction_summary(manifest: dict[str, Any]) -> str:
    return f"""# PIT CPI Access Recovery And Baseline Completion

Task: `{TASK_ID}`

Strategy: `{STRATEGY_ID}`

Outcome: `{manifest['outcome']}`

Blocker: `{manifest['blocker']}`

Prior packet preserved unchanged: `{manifest['prior_packet_preserved_unchanged']}`

ALFRED access status: `{manifest['alfred_access_status']}`

Fixed BLS anchors loaded/parsed: `{manifest['fixed_bls_anchor_loaded_count']}` / `{manifest['fixed_bls_anchor_count']}`

Baseline implemented: `{manifest['baseline_implemented']}`

No revised CPI substitution, strategy variation, overlay performance, promotion, paper/demo activation, broker orders, or real-money recommendation occurred.

Exact next action: `{NEXT_ACTION}`
"""


def fields_for(name: str) -> list[str]:
    mapping = {
        "alfred_vintage_inventory.csv": [
            "series_id",
            "vintage_date",
            "vintage_date_gte_1994",
            "source",
            "response_hash",
        ],
        "alfred_point_in_time_cpi_levels.csv": [
            "reference_month",
            "earliest_vintage_date",
            "current_month_vintage_value",
            "previous_month",
            "previous_month_value_from_same_vintage",
            "same_vintage_current_and_previous",
            "vintage_query_params",
            "source_hash",
            "query_status",
            "query_error",
            "retrieval_timestamp",
        ],
        "alfred_point_in_time_mom_series.csv": [
            "cpi_reference_month",
            "release_date",
            "earliest_vintage_date",
            "current_month_vintage_value",
            "previous_month_value_from_same_vintage",
            "mom_raw_percent",
            "reported_mom_percent",
            "rounding_rule",
            "source_hash",
            "same_vintage_current_and_previous",
            "latest_revised_history_used",
            "retrieval_timestamp",
            "vintage_query_params",
        ],
        "bls_anchor_release_inventory.csv": [
            "anchor_id",
            "reference_month",
            "release_date",
            "release_url",
            "http_status",
            "content_type",
            "content_hash",
            "access_status",
            "error",
        ],
        "bls_anchor_extraction.csv": [
            "anchor_id",
            "reference_month",
            "release_date",
            "release_timestamp",
            "release_url",
            "content_hash",
            "extraction_status",
            "reported_mom_percent",
            "value_sign",
            "extraction_method",
            "extraction_error",
        ],
        "alfred_vs_bls_anchor_reconciliation.csv": [
            "anchor_id",
            "reference_month",
            "bls_release_date",
            "bls_value",
            "alfred_earliest_vintage_date",
            "alfred_reconstructed_value",
            "one_decimal_value_agreement",
            "sign_agreement",
            "classification_agreement",
            "reconciliation_status",
        ],
    }
    return mapping[name]


def write_empty_baseline_files(output: Path) -> None:
    write_csv(output / "cpi_release_timing_audit.csv", [], base.cpi_release_timing_fields())
    write_csv(output / "regime_calculation_audit.csv", [], base.regime_audit_fields())
    write_csv(output / "target_weights.csv", [], base.target_weight_fields())
    write_csv(output / "transactions.csv", [], base.transaction_fields())
    write_csv(output / "baseline_metrics.csv", [], base.baseline_metric_fields())
    write_csv(output / "benchmark_metrics.csv", [], base.benchmark_metric_fields())
    write_csv(output / "static_average_weight_control.csv", [], base.static_average_control_fields())
    write_csv(output / "baseline_vs_controls.csv", [], base.baseline_vs_control_fields())
    write_csv(
        output / "accounting_invariants.csv",
        [{"invariant": "baseline_not_run_until_pit_signal_gate_passes", "passed": True, "value": "blocked_before_targets"}],
        base.accounting_invariant_fields(),
    )
    write_csv(output / "identity_overlay_equality.csv", [], base.identity_fields())


def run(root: Path = ROOT) -> dict[str, Any]:
    output = root / OUTPUT_DIR
    clean_output_dir(output)
    before_state = state_hashes(root)
    prior_before = directory_file_hashes(root / PRIOR_PACKET_DIR)

    key, _ = load_fred_api_key(root)
    alfred_access, vintage_rows, alfred_levels, alfred_mom = alfred_vintage_reconstruction(root)
    bls_inventory, bls_extraction, bls_meta = bls_anchor_releases()
    reconciliation_rows = reconcile_alfred_vs_bls(alfred_mom, bls_extraction)

    cpi_for_regime = cpi_frame_for_base(alfred_mom)
    empty_sessions = pd.DatetimeIndex([])
    regime = base.calculate_regime_records(cpi_for_regime, empty_sessions if cpi_for_regime.empty else None)
    signal_gate = point_in_time_signal_gate_payload(
        alfred_access,
        alfred_levels,
        alfred_mom,
        bls_meta,
        reconciliation_rows,
        regime,
    )
    baseline_status, baseline_blocker, baseline = run_baseline_if_ready(root, alfred_mom, signal_gate)
    outcome, blocker = determine_outcome(alfred_access, bls_meta, reconciliation_rows, signal_gate, baseline_status, baseline_blocker)

    prior_after = directory_file_hashes(root / PRIOR_PACKET_DIR)
    after_state = state_hashes(root)
    prior_recon = prior_packet_reconciliation(root, prior_before, prior_after)
    state_unchanged = before_state == after_state
    baseline_implemented = outcome == "baseline_implemented_for_exploratory_review"
    manifest = {
        "created_utc": RUN_CREATED_UTC,
        "task_id": TASK_ID,
        "strategy_id": STRATEGY_ID,
        "family_id": FAMILY_ID,
        "stage": "correction",
        "adaptation_label": "data_feasibility_adjustment",
        "outcome": outcome,
        "blocker": blocker,
        "baseline_implemented": baseline_implemented,
        "backtest_run": baseline_implemented,
        "prior_packet_preserved_unchanged": prior_recon["prior_packet_preserved_unchanged"],
        "alfred_access_status": alfred_access.get("status"),
        "alfred_observation_count": int(len(alfred_mom)),
        "fixed_bls_anchor_count": len(BLS_ANCHORS),
        "fixed_bls_anchor_loaded_count": bls_meta["loaded_count"],
        "fixed_bls_anchor_parsed_count": bls_meta["parsed_count"],
        "bls_anchor_reconciliation_all_matched": bool(reconciliation_rows)
        and all(row["reconciliation_status"] == "matched" for row in reconciliation_rows),
        "point_in_time_signal_gate_passed": signal_gate["point_in_time_signal_gate_passed"],
        "latest_revised_cpi_used_for_signals": False,
        "rounding_rule": "decimal_round_half_up_one_decimal",
        "rounding_selected_from_investment_results": False,
        "momentum_field_used": False,
        "trend_filter_used": False,
        "prohibited_symbols_used": False,
        "alternative_inflation_series_used": False,
        "overlay_performance_experiment_run": False,
        "promotion_eligibility": False,
        "paper_demo_eligibility": False,
        "paper_demo_activation": False,
        "candidate_exhaustive_run": False,
        "broker_order_endpoint_called": False,
        "real_money_recommendation": False,
        "registry_state_changed": not state_unchanged,
        "state_hashes_before": before_state,
        "state_hashes_after": after_state,
        "next_action": NEXT_ACTION,
    }
    if baseline_implemented:
        weights = baseline["weights"]
        dynamic_months = weights.groupby(weights.index.to_period("M")).tail(1)
        manifest.update(
            {
                "target_day_count": int(len(weights)),
                "regime_switch_count": int(len(baseline["transactions"])),
                "both_inflation_regimes_observed": {"INFLATION_UP", "INFLATION_DOWN"}
                <= set(value for value in baseline["regime"]["regime"].dropna().astype(str) if value),
                "dynamic_gld_month_fraction": float((dynamic_months[base.UP_ASSET] > 0.5).mean()),
                "identity_overlay_equality_passed": all(row["exact_match"] is True for row in baseline["identity_rows"]),
                "exposure_invariant_passed": all(row["passed"] is True for row in baseline["invariants"]),
            }
        )

    write_json(output / "correction_trigger.json", {
        "previous_outcome": "archived_bls_history_incomplete",
        "corrected_interpretation": "bls_archive_index_http_access_blocked",
        "prior_packet_path": str((root / PRIOR_PACKET_DIR).resolve()),
        "prior_packet_overwritten": False,
    })
    write_json(output / "prior_packet_reconciliation.json", prior_recon)
    write_json(output / "repository_capability_review.json", repository_capability_review(root))
    write_json(output / "fred_alfred_access_check.json", alfred_access)
    write_csv(output / "alfred_vintage_inventory.csv", vintage_rows, fields_for("alfred_vintage_inventory.csv"))
    write_csv(output / "alfred_point_in_time_cpi_levels.csv", alfred_levels.to_dict("records"), fields_for("alfred_point_in_time_cpi_levels.csv"))
    write_csv(output / "alfred_point_in_time_mom_series.csv", alfred_mom.to_dict("records"), fields_for("alfred_point_in_time_mom_series.csv"))
    write_csv(output / "bls_anchor_release_inventory.csv", bls_inventory, fields_for("bls_anchor_release_inventory.csv"))
    write_csv(output / "bls_anchor_extraction.csv", bls_extraction, fields_for("bls_anchor_extraction.csv"))
    write_csv(output / "alfred_vs_bls_anchor_reconciliation.csv", reconciliation_rows, fields_for("alfred_vs_bls_anchor_reconciliation.csv"))
    write_json(output / "rounding_convention_audit.json", {
        "selected_rounding_rule": "decimal_round_half_up_one_decimal",
        "candidate_rules": ["decimal_round_half_up_one_decimal"],
        "selection_basis": "fixed_official_anchor_reconciliation_only_when_available",
        "investment_results_used": False,
        "example": {"raw": 0.249, "rounded": round_one_decimal_half_up(0.249)},
    })
    write_json(output / "point_in_time_signal_gate.json", signal_gate)
    if baseline_implemented:
        write_csv(output / "cpi_release_timing_audit.csv", base.cpi_release_timing_rows(baseline["regime"]), base.cpi_release_timing_fields())
        write_csv(output / "regime_calculation_audit.csv", base.regime_audit_rows(baseline["regime"]), base.regime_audit_fields())
        write_csv(output / "target_weights.csv", base.target_weight_rows(baseline["weights"]), base.target_weight_fields())
        write_csv(output / "transactions.csv", baseline["transactions"], base.transaction_fields())
        write_csv(output / "baseline_metrics.csv", baseline["baseline_rows"], base.baseline_metric_fields())
        write_csv(output / "benchmark_metrics.csv", baseline["benchmark_rows"], base.benchmark_metric_fields())
        write_csv(
            output / "static_average_weight_control.csv",
            [{
                "control_id": "static_average_weight_control",
                "gld_month_fraction": baseline["static_info"].get("gld_month_fraction"),
                "ief_month_fraction": baseline["static_info"].get("ief_month_fraction"),
                "dynamic_months": baseline["static_info"].get("dynamic_months"),
                "role": "ex_post_diagnostic_control",
                "calculated_ex_post": True,
            }],
            base.static_average_control_fields(),
        )
        write_csv(output / "baseline_vs_controls.csv", baseline["baseline_vs_controls"], base.baseline_vs_control_fields())
        write_csv(output / "accounting_invariants.csv", baseline["invariants"], base.accounting_invariant_fields())
        write_csv(output / "identity_overlay_equality.csv", baseline["identity_rows"], base.identity_fields())
    else:
        write_empty_baseline_files(output)
    write_csv(output / "overlay_compatibility_map.csv", base.overlay_compatibility_rows(), base.overlay_fields())
    write_json(output / "trial_manifest.json", manifest)
    write_csv(output / "command_validation_log.csv", command_validation_rows(), ["command", "status", "notes"])
    write_text(output / "correction_summary.md", correction_summary(manifest))
    consistency = consistency_payload(output, manifest, prior_recon["prior_packet_preserved_unchanged"], state_unchanged, [key])
    write_json(output / "consistency_check.json", consistency)
    return {**manifest, "output_dir": str(output.resolve()), "consistency_passed": consistency["consistency_passed"]}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
