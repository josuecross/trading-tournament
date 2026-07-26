from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import os
import shutil
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
import yaml

from src.data import NORMALIZED_COLUMNS, RAW_COLUMNS, _download_yfinance, build_adjusted_ohlc, load_symbol_data
from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.research import (
    remediate_angl_observation_required_market_data_v1 as prior,
)


TASK_ID = "correct_observation_market_data_versioning_and_serialization_v1"
OUTPUT_DIR = ROOT / "evidence" / "correction" / TASK_ID / "latest"
STAGING_DIR = ROOT / "data" / "cache" / f".{TASK_ID}_staging"
BACKUP_DIR = ROOT / "data" / "cache" / f".{TASK_ID}_backup"
PRIOR_EVIDENCE_DIR = (
    ROOT
    / "evidence"
    / "data_capability"
    / "remediate_angl_observation_required_market_data_v1"
    / "latest"
)

REQUIRED_DATE = pd.Timestamp("2026-07-24")
END_EXCLUSIVE = "2026-07-25"
CORRECTION_TIMESTAMP = "2026-07-25T00:00:00+00:00"
PROVIDER_ID = "yfinance_existing_repo_supported_adjusted_daily_path"
ADAPTATION_LABEL = "methodology_correction"
STRATEGY_ID = prior.STRATEGY_ID
FAMILY_ID = prior.FAMILY_ID
OBSERVATION_ID = prior.OBSERVATION_ID
TARGET_SYMBOLS = prior.TARGET_SYMBOLS

OUTCOME_READY = "canonical_observation_data_version_ready"
OUTCOME_BLOCKED = "canonical_observation_data_version_blocked"
NEXT_READY = "rerun_initialize_angl_after_market_data_correction_v2"
NEXT_BLOCKED = "defer_angl_observation_data_lane_v1"
PROJECT_NEXT_ACTION = "refresh_strategy_source_library_v3"

SOURCE_FLOAT_DECIMALS = 12
HASH_FLOAT_DECIMALS = 12
CSV_FLOAT_FORMAT = "%.12f"
MISSING_SENTINEL = "<NA>"
NUMERIC_ABS_TOLERANCE = 1e-10
NUMERIC_REL_TOLERANCE = 1e-12
OHLC_ABS_TOLERANCE = 1e-10
OHLC_REL_TOLERANCE = 1e-12

INTEGER_COLUMNS = ("raw_volume", "volume")
FLOAT_COLUMNS = tuple(
    column
    for column in NORMALIZED_COLUMNS
    if column not in {"date", "symbol", *INTEGER_COLUMNS}
)
RAW_PRICE_COLUMNS = {"raw_open", "raw_high", "raw_low", "raw_close"}
RAW_VOLUME_COLUMNS = {"raw_volume", "volume"}
CORPORATE_ACTION_COLUMNS = {"dividends", "stock_splits"}
ADJUSTMENT_COLUMNS = {"raw_adj_close", "adjustment_factor"}
ADJUSTED_PRICE_COLUMNS = {"open", "high", "low", "close", "adj_close"}
DIFFERENCE_FIELDS = (
    "raw_open",
    "raw_high",
    "raw_low",
    "raw_close",
    "raw_adj_close",
    "raw_volume",
    "dividends",
    "stock_splits",
    "adjustment_factor",
    "open",
    "high",
    "low",
    "close",
    "adj_close",
    "volume",
)
ALLOWED_FAILURES = {"", "data_or_comparability_failure", "methodology_failure", "capability_missing"}

PROTECTED_STATE_PATHS = prior.PROTECTED_STATE_PATHS
OPERATIONAL_PATHS = prior.OPERATIONAL_PATHS
PRIOR_EVIDENCE_PATHS = tuple(
    path for path in sorted(PRIOR_EVIDENCE_DIR.glob("*")) if path.is_file()
)


def rel(path: str | Path) -> str:
    return prior.rel(path)


def file_hash(path: Path) -> str:
    return prior.file_hash(path)


def hash_map(paths: Iterable[Path]) -> dict[str, str]:
    return {rel(path): file_hash(path) for path in paths}


def cache_path(symbol: str) -> Path:
    return ROOT / "data" / "cache" / f"{symbol}.csv"


def metadata_path(symbol: str) -> Path:
    return ROOT / "data" / "cache" / f"{symbol}.acquisition.json"


def stage_cache_path(symbol: str) -> Path:
    return STAGING_DIR / f"{symbol}.csv"


def stage_metadata_path(symbol: str) -> Path:
    return STAGING_DIR / f"{symbol}.acquisition.json"


def backup_path(path: Path) -> Path:
    return BACKUP_DIR / path.name


def csv_value(value: Any) -> str:
    return prior.csv_value(value)


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    prior.write_csv(path, rows, fields)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    prior.write_json(path, payload)


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    prior.write_yaml(path, payload)


def write_text(path: Path, text: str) -> None:
    prior.write_text(path, text)


def read_csv(path: Path) -> list[dict[str, str]]:
    return prior.read_csv(path)


def clean_output_and_staging() -> None:
    if OUTPUT_DIR.exists():
        resolved = OUTPUT_DIR.resolve()
        expected_parent = (ROOT / "evidence" / "correction" / TASK_ID).resolve()
        if expected_parent not in resolved.parents:
            raise RuntimeError(f"Refusing to remove unexpected evidence directory: {resolved}")
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    cache_root = (ROOT / "data" / "cache").resolve()
    for path in (STAGING_DIR, BACKUP_DIR):
        if path.exists():
            if path.resolve().parent != cache_root:
                raise RuntimeError(f"Refusing to remove unexpected transaction directory: {path}")
            shutil.rmtree(path)
        path.mkdir(parents=True, exist_ok=True)


def sanitize_error(exc: BaseException) -> str:
    return prior.sanitize_error(exc)


def normalized_dates(values: pd.Series) -> pd.Series:
    dates = pd.to_datetime(values, errors="coerce", utc=True)
    return dates.dt.tz_convert(None).dt.normalize()


def canonicalize_frame(frame: pd.DataFrame, symbol: str) -> pd.DataFrame:
    """Normalize source fields, then deterministically rebuild every derived column."""
    built = build_adjusted_ohlc(frame, symbol)
    dates = normalized_dates(built["date"])
    if dates.isna().any():
        raise ValueError(f"{symbol}: unparseable date in canonical frame")
    source = built[["date", *RAW_COLUMNS]].copy()
    source["date"] = dates
    for column in RAW_COLUMNS:
        values = pd.to_numeric(source[column], errors="coerce")
        if values.isna().any() or not np.isfinite(values.to_numpy(dtype=float)).all():
            raise ValueError(f"{symbol}: non-finite source column {column}")
        if column == "raw_volume":
            rounded = np.rint(values.to_numpy(dtype=float))
            if not np.allclose(values.to_numpy(dtype=float), rounded, rtol=0.0, atol=1e-6):
                raise ValueError(f"{symbol}: raw volume is not integer-valued")
            source[column] = rounded.astype("int64")
        else:
            normalized = np.round(values.to_numpy(dtype="float64"), SOURCE_FLOAT_DECIMALS)
            normalized[normalized == 0.0] = 0.0
            source[column] = normalized.astype("float64")
    rebuilt = build_adjusted_ohlc(source, symbol)
    rebuilt["date"] = normalized_dates(rebuilt["date"]).dt.strftime("%Y-%m-%d")
    rebuilt["symbol"] = rebuilt["symbol"].astype("string").fillna("").astype(str)
    rebuilt["raw_volume"] = np.rint(pd.to_numeric(rebuilt["raw_volume"])).astype("int64")
    rebuilt["volume"] = np.rint(pd.to_numeric(rebuilt["volume"])).astype("int64")
    for column in FLOAT_COLUMNS:
        values = pd.to_numeric(rebuilt[column], errors="coerce").to_numpy(
            dtype="float64", copy=True
        )
        values[values == 0.0] = 0.0
        rebuilt[column] = values
    rebuilt = rebuilt.sort_values("date", kind="mergesort").reset_index(drop=True)
    return rebuilt[list(NORMALIZED_COLUMNS)]


def canonical_cell(column: str, value: Any) -> str:
    if pd.isna(value):
        return MISSING_SENTINEL
    if column in INTEGER_COLUMNS:
        return str(int(value))
    if column in FLOAT_COLUMNS:
        number = float(value)
        if number == 0.0:
            number = 0.0
        return f"{number:.{HASH_FLOAT_DECIMALS}f}"
    return str(value)


def canonical_frame_payload(frame: pd.DataFrame, symbol: str) -> bytes:
    normalized = canonicalize_frame(frame, symbol)
    handle = io.StringIO(newline="")
    writer = csv.writer(handle, lineterminator="\n")
    writer.writerow(NORMALIZED_COLUMNS)
    for row in normalized.itertuples(index=False, name=None):
        writer.writerow(
            canonical_cell(column, value)
            for column, value in zip(NORMALIZED_COLUMNS, row, strict=True)
        )
    return handle.getvalue().encode("utf-8")


def canonical_frame_hash(frame: pd.DataFrame, symbol: str) -> str:
    return "sha256:" + hashlib.sha256(canonical_frame_payload(frame, symbol)).hexdigest()


def write_canonical_csv(path: Path, frame: pd.DataFrame, symbol: str) -> pd.DataFrame:
    normalized = canonicalize_frame(frame, symbol)
    normalized.to_csv(
        path,
        index=False,
        lineterminator="\n",
        float_format=CSV_FLOAT_FORMAT,
        na_rep=MISSING_SENTINEL,
    )
    return normalized


def load_existing_cache(symbol: str) -> pd.DataFrame:
    path = cache_path(symbol)
    if not path.exists():
        return pd.DataFrame(columns=NORMALIZED_COLUMNS)
    return canonicalize_frame(pd.read_csv(path), symbol)


def download_once(symbol: str, start: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    raw = _download_yfinance(
        symbol,
        start,
        END_EXCLUSIVE,
        {
            "auto_adjust": False,
            "actions": True,
            "progress": False,
            "multi_level_index": False,
            "timeout": 30,
        },
    )
    if raw.empty:
        raise RuntimeError(f"{symbol}: provider returned no rows")
    unrounded = build_adjusted_ohlc(raw, symbol)
    unrounded["date"] = normalized_dates(unrounded["date"])
    unrounded = unrounded[unrounded["date"] <= REQUIRED_DATE].copy()
    if unrounded.empty:
        raise RuntimeError(f"{symbol}: no provider rows through required date")
    canonical = canonicalize_frame(unrounded, symbol)
    return unrounded[list(NORMALIZED_COLUMNS)], canonical


def field_category(field: str) -> str:
    if field in RAW_PRICE_COLUMNS:
        return "raw_price"
    if field in RAW_VOLUME_COLUMNS:
        return "raw_volume"
    if field == "dividends":
        return "dividend"
    if field == "stock_splits":
        return "split"
    if field in ADJUSTMENT_COLUMNS:
        return "adjustment_factor"
    if field in ADJUSTED_PRICE_COLUMNS:
        return "adjusted_price"
    raise ValueError(f"Unclassified field: {field}")


def exact_numeric_difference(prior_value: float, candidate_value: float) -> bool:
    return not math.isclose(
        float(prior_value),
        float(candidate_value),
        rel_tol=0.0,
        abs_tol=0.5 * (10 ** -SOURCE_FLOAT_DECIMALS),
    )


def overlap_differences(
    symbol: str,
    old: pd.DataFrame,
    candidate: pd.DataFrame,
    verification: pd.DataFrame,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if old.empty:
        return [], {
            "symbol": symbol,
            "prior_rows": 0,
            "candidate_rows": len(candidate),
            "overlap_rows": 0,
            "missing_prior_dates": 0,
            "changed_rows": 0,
            "changed_fields": 0,
            "raw_price_rows_changed": 0,
            "raw_volume_rows_changed": 0,
            "corporate_action_rows_changed": 0,
            "adjustment_rows_changed": 0,
            "adjusted_price_rows_changed": 0,
            "raw_overlap_revision_classification": "new_cache_no_prior_history",
            "history_revision_classification": "new_cache_no_prior_history",
            "revision_explained": True,
            "acceptance_basis": "no prior canonical history",
        }
    indexed_old = old.set_index("date", drop=False)
    indexed_candidate = candidate.set_index("date", drop=False)
    indexed_verification = verification.set_index("date", drop=False)
    common = indexed_old.index.intersection(indexed_candidate.index)
    missing_prior = indexed_old.index.difference(indexed_candidate.index)
    rows: list[dict[str, Any]] = []
    changed_dates_by_category: dict[str, set[str]] = {
        "raw_price": set(),
        "raw_volume": set(),
        "dividend": set(),
        "split": set(),
        "adjustment_factor": set(),
        "adjusted_price": set(),
    }
    changed_fields: set[str] = set()
    for field in DIFFERENCE_FIELDS:
        category = field_category(field)
        prior_values = pd.to_numeric(indexed_old.loc[common, field], errors="coerce")
        candidate_values = pd.to_numeric(indexed_candidate.loc[common, field], errors="coerce")
        verification_values = pd.to_numeric(
            indexed_verification.reindex(common)[field], errors="coerce"
        )
        differences = [
            exact_numeric_difference(prior_value, candidate_value)
            for prior_value, candidate_value in zip(
                prior_values.to_numpy(dtype=float),
                candidate_values.to_numpy(dtype=float),
                strict=True,
            )
        ]
        for position in np.flatnonzero(np.asarray(differences, dtype=bool)):
            date = str(common[position])
            prior_value = float(prior_values.iloc[position])
            candidate_value = float(candidate_values.iloc[position])
            verification_value = float(verification_values.iloc[position])
            absolute = abs(candidate_value - prior_value)
            relative = absolute / max(abs(prior_value), 1e-30)
            rows.append(
                {
                    "symbol": symbol,
                    "date": date,
                    "field": field,
                    "field_category": category,
                    "prior_value": prior_value,
                    "candidate_value": candidate_value,
                    "verification_fetch_value": verification_value,
                    "absolute_difference": absolute,
                    "relative_difference": relative,
                    "candidate_matches_verification": not exact_numeric_difference(
                        candidate_value, verification_value
                    ),
                }
            )
            changed_fields.add(field)
            changed_dates_by_category[category].add(date)
    raw_price_dates = changed_dates_by_category["raw_price"]
    raw_volume_dates = changed_dates_by_category["raw_volume"]
    action_dates = changed_dates_by_category["dividend"] | changed_dates_by_category["split"]
    adjustment_dates = changed_dates_by_category["adjustment_factor"]
    adjusted_dates = changed_dates_by_category["adjusted_price"]
    if raw_price_dates:
        last_prior_dates = set(indexed_old.index[-10:])
        if raw_price_dates.issubset(last_prior_dates):
            raw_classification = "recent_session_price_correction"
            explained = True
        else:
            raw_classification = "material_unexplained_history_change"
            explained = False
    elif raw_volume_dates and not action_dates:
        raw_classification = "raw_volume_revision_only"
        explained = True
    elif action_dates:
        raw_classification = "corporate_action_restatement"
        explained = True
    elif not changed_fields:
        raw_classification = "overlap_identical"
        explained = True
    else:
        raw_classification = "adjustment_history_rebuild_only"
        explained = True
    if raw_classification == "raw_volume_revision_only" and (adjustment_dates or adjusted_dates):
        classification = "raw_volume_revision_with_adjustment_history_rebuild"
    elif raw_classification == "corporate_action_restatement" and raw_volume_dates:
        classification = "raw_volume_and_corporate_action_restatement"
    elif raw_classification == "overlap_identical" and (adjustment_dates or adjusted_dates):
        classification = "adjustment_history_rebuild_only"
    else:
        classification = raw_classification
    basis = {
        "overlap_identical": "all normalized overlap fields are identical",
        "raw_volume_revision_with_adjustment_history_rebuild": (
            "raw price fields are unchanged; deterministic provider volume restatement and "
            "adjustment-history rebuild are recorded field by field"
        ),
        "raw_volume_revision_only": (
            "raw price fields are unchanged and the only raw overlap revision is volume"
        ),
        "corporate_action_restatement": (
            "raw price fields are unchanged and deterministic corporate-action/adjustment "
            "history changes are recorded field by field"
        ),
        "raw_volume_and_corporate_action_restatement": (
            "raw price fields are unchanged; deterministic volume and corporate-action "
            "restatements are recorded field by field"
        ),
        "adjustment_history_rebuild_only": (
            "raw OHLCV fields are unchanged and deterministic adjusted-history changes are recorded"
        ),
        "recent_session_price_correction": (
            "deterministic raw-price changes are confined to the final ten prior sessions"
        ),
        "material_unexplained_history_change": (
            "raw-price history changed outside the recent-session correction boundary"
        ),
    }.get(classification, "classification recorded from normalized field-level differences")
    changed_dates = {row["date"] for row in rows}
    return rows, {
        "symbol": symbol,
        "prior_rows": len(old),
        "candidate_rows": len(candidate),
        "overlap_rows": len(common),
        "missing_prior_dates": len(missing_prior),
        "changed_rows": len(changed_dates),
        "changed_fields": len(rows),
        "raw_price_rows_changed": len(raw_price_dates),
        "raw_volume_rows_changed": len(raw_volume_dates),
        "corporate_action_rows_changed": len(action_dates),
        "adjustment_rows_changed": len(adjustment_dates),
        "adjusted_price_rows_changed": len(adjusted_dates),
        "raw_overlap_revision_classification": raw_classification,
        "history_revision_classification": classification,
        "revision_explained": explained,
        "acceptance_basis": basis,
    }


def relationship_violations(
    frame: pd.DataFrame,
    prefix: str,
    use_tolerance: bool,
) -> list[dict[str, Any]]:
    high = pd.to_numeric(frame[f"{prefix}high"], errors="coerce").to_numpy(dtype=float)
    low = pd.to_numeric(frame[f"{prefix}low"], errors="coerce").to_numpy(dtype=float)
    open_values = pd.to_numeric(frame[f"{prefix}open"], errors="coerce").to_numpy(dtype=float)
    close = pd.to_numeric(frame[f"{prefix}close"], errors="coerce").to_numpy(dtype=float)
    max_component = np.maximum.reduce([open_values, low, close])
    min_component = np.minimum.reduce([open_values, high, close])
    high_gap = max_component - high
    low_gap = low - min_component
    scale = np.maximum.reduce(
        [
            np.abs(high),
            np.abs(low),
            np.abs(open_values),
            np.abs(close),
            np.ones(len(frame)),
        ]
    )
    tolerance = OHLC_ABS_TOLERANCE + OHLC_REL_TOLERANCE * scale
    threshold = tolerance if use_tolerance else np.zeros(len(frame))
    rows: list[dict[str, Any]] = []
    for index in np.flatnonzero((high_gap > threshold) | (low_gap > threshold)):
        side = "high_below_component" if high_gap[index] > threshold[index] else "low_above_component"
        magnitude = max(float(high_gap[index]), float(low_gap[index]), 0.0)
        rows.append(
            {
                "date": pd.to_datetime(frame.iloc[index]["date"]).date().isoformat(),
                "violation_side": side,
                "open": open_values[index],
                "high": high[index],
                "low": low[index],
                "close": close[index],
                "maximum_component": max_component[index],
                "minimum_component": min_component[index],
                "violation_magnitude": magnitude,
                "relative_violation": magnitude / scale[index],
                "strict_tolerance": tolerance[index],
                "within_strict_tolerance": magnitude <= tolerance[index],
            }
        )
    return rows


def xlc_violation_analysis(
    candidate_unrounded: pd.DataFrame | None,
    verification_unrounded: pd.DataFrame | None,
) -> list[dict[str, Any]]:
    if candidate_unrounded is None or verification_unrounded is None:
        return [
            {
                "symbol": "XLC",
                "date": "",
                "analysis_status": "provider_fetch_unavailable",
                "violation_side": "",
                "raw_open": "",
                "raw_high": "",
                "raw_low": "",
                "raw_close": "",
                "adjusted_open": "",
                "adjusted_high": "",
                "adjusted_low": "",
                "adjusted_close": "",
                "violation_magnitude": "",
                "relative_violation": "",
                "strict_tolerance": "",
                "raw_ohlc_relationship_valid": False,
                "verification_fetch_same_values": False,
                "numerically_immaterial": False,
                "row_deleted_or_clipped": False,
            }
        ]
    violations = relationship_violations(candidate_unrounded, "", use_tolerance=False)
    if not violations:
        return [
            {
                "symbol": "XLC",
                "date": "",
                "analysis_status": "no_exact_adjusted_relationship_violation_in_current_fetch",
                "violation_side": "",
                "raw_open": "",
                "raw_high": "",
                "raw_low": "",
                "raw_close": "",
                "adjusted_open": "",
                "adjusted_high": "",
                "adjusted_low": "",
                "adjusted_close": "",
                "violation_magnitude": 0.0,
                "relative_violation": 0.0,
                "strict_tolerance": OHLC_ABS_TOLERANCE,
                "raw_ohlc_relationship_valid": not relationship_violations(
                    candidate_unrounded, "raw_", use_tolerance=True
                ),
                "verification_fetch_same_values": canonical_frame_hash(
                    candidate_unrounded, "XLC"
                )
                == canonical_frame_hash(verification_unrounded, "XLC"),
                "numerically_immaterial": True,
                "row_deleted_or_clipped": False,
            }
        ]
    verification_indexed = verification_unrounded.copy()
    verification_indexed["date"] = normalized_dates(verification_indexed["date"]).dt.strftime(
        "%Y-%m-%d"
    )
    verification_indexed = verification_indexed.set_index("date")
    candidate_indexed = candidate_unrounded.copy()
    candidate_indexed["date"] = normalized_dates(candidate_indexed["date"]).dt.strftime("%Y-%m-%d")
    candidate_indexed = candidate_indexed.set_index("date")
    raw_invalid_dates = {
        row["date"]
        for row in relationship_violations(candidate_unrounded, "raw_", use_tolerance=True)
    }
    output: list[dict[str, Any]] = []
    for violation in violations:
        date = violation["date"]
        candidate_row = candidate_indexed.loc[date]
        verification_row = verification_indexed.loc[date] if date in verification_indexed.index else None
        compared_fields = ["raw_open", "raw_high", "raw_low", "raw_close", "open", "high", "low", "close"]
        verification_same = verification_row is not None and all(
            math.isclose(
                float(candidate_row[field]),
                float(verification_row[field]),
                rel_tol=NUMERIC_REL_TOLERANCE,
                abs_tol=NUMERIC_ABS_TOLERANCE,
            )
            for field in compared_fields
        )
        output.append(
            {
                "symbol": "XLC",
                "date": date,
                "analysis_status": "exact_violation_measured",
                "violation_side": violation["violation_side"],
                "raw_open": candidate_row["raw_open"],
                "raw_high": candidate_row["raw_high"],
                "raw_low": candidate_row["raw_low"],
                "raw_close": candidate_row["raw_close"],
                "adjusted_open": violation["open"],
                "adjusted_high": violation["high"],
                "adjusted_low": violation["low"],
                "adjusted_close": violation["close"],
                "violation_magnitude": violation["violation_magnitude"],
                "relative_violation": violation["relative_violation"],
                "strict_tolerance": violation["strict_tolerance"],
                "raw_ohlc_relationship_valid": date not in raw_invalid_dates,
                "verification_fetch_same_values": verification_same,
                "numerically_immaterial": (
                    bool(violation["within_strict_tolerance"])
                    and date not in raw_invalid_dates
                    and verification_same
                ),
                "row_deleted_or_clipped": False,
            }
        )
    return output


def integrity_checks(
    symbol: str,
    frame: pd.DataFrame,
    old: pd.DataFrame,
    provider_reproducible: bool,
    staged_hash_match: bool,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    def add(name: str, passed: bool, details: str = "", violations: int | str = "") -> None:
        rows.append(
            {
                "symbol": symbol,
                "check_name": name,
                "status": "pass" if passed else "fail",
                "violation_count": violations,
                "details": details,
            }
        )

    if frame.empty:
        add("non_empty_frame", False, "no canonical candidate rows", 1)
        return rows
    dates = normalized_dates(frame["date"])
    add("canonical_schema", list(frame.columns) == list(NORMALIZED_COLUMNS), "|".join(frame.columns))
    add("correct_instrument_identity", frame["symbol"].astype(str).eq(symbol).all())
    add("ordered_dates", dates.is_monotonic_increasing)
    add("unique_dates", not dates.duplicated().any(), violations=int(dates.duplicated().sum()))
    add("no_duplicate_rows", not frame.duplicated().any(), violations=int(frame.duplicated().sum()))
    add(
        "valid_weekday_dates",
        bool((dates.dt.weekday < 5).all()),
        violations=int((dates.dt.weekday >= 5).sum()),
    )
    add("no_future_dates", dates.max() <= REQUIRED_DATE, f"last={dates.max().date().isoformat()}")
    add("required_date_present", bool((dates == REQUIRED_DATE).any()))
    old_dates = set(normalized_dates(old["date"]).dt.strftime("%Y-%m-%d")) if not old.empty else set()
    new_dates = set(dates.dt.strftime("%Y-%m-%d"))
    missing_prior = sorted(old_dates - new_dates)
    add(
        "no_missing_prior_dates",
        not missing_prior,
        "missing=" + "|".join(missing_prior[:20]),
        len(missing_prior),
    )
    price_columns = [
        "raw_open",
        "raw_high",
        "raw_low",
        "raw_close",
        "raw_adj_close",
        "open",
        "high",
        "low",
        "close",
        "adj_close",
    ]
    prices = frame[price_columns].apply(pd.to_numeric, errors="coerce")
    finite_prices = np.isfinite(prices.to_numpy(dtype=float))
    add("positive_finite_raw_and_adjusted_prices", finite_prices.all() and (prices > 0).all().all())
    volume = frame[["raw_volume", "volume"]].apply(pd.to_numeric, errors="coerce")
    add(
        "nonnegative_finite_volume",
        np.isfinite(volume.to_numpy(dtype=float)).all() and (volume >= 0).all().all(),
    )
    raw_violations = relationship_violations(frame, "raw_", use_tolerance=True)
    adjusted_violations = relationship_violations(frame, "", use_tolerance=True)
    add("valid_raw_ohlc_relationships", not raw_violations, violations=len(raw_violations))
    add(
        "valid_adjusted_ohlc_relationships",
        not adjusted_violations,
        violations=len(adjusted_violations),
    )
    factor = pd.to_numeric(frame["adjustment_factor"], errors="coerce").to_numpy(dtype=float)
    raw_close = pd.to_numeric(frame["raw_close"], errors="coerce").to_numpy(dtype=float)
    raw_adj = pd.to_numeric(frame["raw_adj_close"], errors="coerce").to_numpy(dtype=float)
    factor_valid = np.isfinite(factor).all() and (factor > 0).all()
    factor_matches = np.isclose(
        raw_close * factor,
        raw_adj,
        rtol=NUMERIC_REL_TOLERANCE,
        atol=NUMERIC_ABS_TOLERANCE,
    ).all()
    add("valid_adjustment_factors", factor_valid and factor_matches)
    adjusted_close = pd.to_numeric(frame["adj_close"], errors="coerce").to_numpy(dtype=float)
    add(
        "adjusted_close_reconciliation",
        np.isclose(
            adjusted_close,
            raw_adj,
            rtol=NUMERIC_REL_TOLERANCE,
            atol=NUMERIC_ABS_TOLERANCE,
        ).all(),
    )
    add("deterministic_provider_fetch", provider_reproducible)
    add("staged_reloaded_canonical_hash_equality", staged_hash_match)
    return rows


def legacy_serialization_diagnosis(
    symbol: str,
    candidate: pd.DataFrame,
    prior_failed: bool,
) -> dict[str, Any]:
    legacy_before = prior.frame_hash(candidate)
    buffer = io.StringIO()
    candidate.to_csv(buffer, index=False, lineterminator="\n")
    buffer.seek(0)
    legacy_reloaded = build_adjusted_ohlc(pd.read_csv(buffer), symbol)
    legacy_reloaded["date"] = normalized_dates(legacy_reloaded["date"]).dt.strftime("%Y-%m-%d")
    legacy_reloaded = legacy_reloaded[list(NORMALIZED_COLUMNS)]
    legacy_after = prior.frame_hash(legacy_reloaded)
    before_numeric = candidate[list(FLOAT_COLUMNS)].to_numpy(dtype=float)
    after_numeric = legacy_reloaded[list(FLOAT_COLUMNS)].to_numpy(dtype=float)
    maximum_delta = float(np.max(np.abs(before_numeric - after_numeric)))
    return {
        "symbol": symbol,
        "prior_serialization_failure_reported": prior_failed,
        "legacy_in_memory_hash": legacy_before,
        "legacy_reloaded_hash": legacy_after,
        "legacy_hashes_match": legacy_before == legacy_after,
        "maximum_float_round_trip_difference": maximum_delta,
        "root_cause": (
            "legacy hashing serialized derived binary floats, then reload rebuilt derived fields "
            "from decimal raw columns; sub-precision float drift changed the unnormalized payload hash"
        ),
        "correction": (
            f"raw source fields quantized to {SOURCE_FLOAT_DECIMALS} decimals; derived fields rebuilt; "
            f"all columns hashed at {HASH_FLOAT_DECIMALS} decimals with fixed dtypes and missing sentinel"
        ),
        "columns_omitted_from_corrected_hash": "",
        "hash_comparison_weakened": False,
    }


def normal_cache_reload(symbol: str, expected: pd.DataFrame) -> dict[str, Any]:
    config = {
        "data": {
            "cache_dir": "data/cache",
            "raw_dir": "data/raw",
            "use_cache": True,
            "refresh_cache": False,
            "start_date": str(expected.iloc[0]["date"]),
            "end_date": END_EXCLUSIVE,
            "yfinance": {},
        }
    }
    loaded, coverage, source = load_symbol_data(symbol, config, ROOT)
    expected_hash = canonical_frame_hash(expected, symbol)
    loaded_hash = (
        canonical_frame_hash(loaded, symbol)
        if loaded is not None and not loaded.empty
        else ""
    )
    passed = bool(
        loaded is not None
        and not loaded.empty
        and len(loaded) == len(expected)
        and source == "cache"
        and coverage.get("status") == "valid"
        and expected_hash == loaded_hash
    )
    return {
        "symbol": symbol,
        "normal_data_interface": "src.data.load_symbol_data",
        "load_source": source,
        "load_status": coverage.get("status", ""),
        "expected_rows": len(expected),
        "reloaded_rows": 0 if loaded is None else len(loaded),
        "expected_canonical_hash": expected_hash,
        "reloaded_canonical_hash": loaded_hash,
        "reload_hash_match": expected_hash == loaded_hash,
        "reload_pass": passed,
    }


def restore_transaction(target_paths: list[Path], existed_before: dict[str, bool]) -> None:
    for target in target_paths:
        backup = backup_path(target)
        if existed_before[rel(target)]:
            if not backup.exists():
                raise RuntimeError(f"Missing transaction backup for {target}")
            shutil.copy2(backup, target)
        else:
            target.unlink(missing_ok=True)


def cohort_commit(
    frames: dict[str, pd.DataFrame],
    metadata_payloads: dict[str, dict[str, Any]],
) -> tuple[bool, str, list[dict[str, Any]]]:
    target_paths = [
        path
        for symbol in TARGET_SYMBOLS
        for path in (cache_path(symbol), metadata_path(symbol))
    ]
    existed_before = {rel(path): path.exists() for path in target_paths}
    try:
        for path in target_paths:
            if path.exists():
                shutil.copy2(path, backup_path(path))
        for symbol in TARGET_SYMBOLS:
            write_canonical_csv(stage_cache_path(symbol), frames[symbol], symbol)
            metadata_payloads[symbol].update(
                {
                    "cache_path": rel(cache_path(symbol)),
                    "metadata_path": rel(metadata_path(symbol)),
                    "cache_file_hash": file_hash(stage_cache_path(symbol)),
                    "canonical_frame_hash": canonical_frame_hash(
                        frames[symbol], symbol
                    ),
                    "admitted_to_canonical_cache": True,
                }
            )
            stage_metadata_path(symbol).write_text(
                json.dumps(metadata_payloads[symbol], indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        for symbol in TARGET_SYMBOLS:
            os.replace(stage_cache_path(symbol), cache_path(symbol))
            os.replace(stage_metadata_path(symbol), metadata_path(symbol))
        reload_rows = [normal_cache_reload(symbol, frames[symbol]) for symbol in TARGET_SYMBOLS]
        if not all(row["reload_pass"] for row in reload_rows):
            restore_transaction(target_paths, existed_before)
            return False, "post_commit_normal_interface_reload_failed_and_cohort_rolled_back", reload_rows
        return True, "all_20_cache_and_metadata_files_committed_as_one_transaction", reload_rows
    except BaseException as exc:  # noqa: BLE001 - transaction must roll back every target.
        restore_transaction(target_paths, existed_before)
        return False, "cohort_transaction_failed_and_rolled_back:" + sanitize_error(exc), []


def sufficiency_rows(final_frames: dict[str, pd.DataFrame], committed: bool) -> list[dict[str, Any]]:
    groups = [
        ("VM_observation_inputs", prior.VM_SYMBOLS),
        ("DSR_observation_inputs", prior.DSR_SYMBOLS),
        ("USCI_observation_inputs", prior.USCI_SYMBOLS),
        ("frozen_current_active_vm_dsr_usci_combo", prior.REFERENCE_SYMBOLS),
        ("ANGL_candidate_input", ("ANGL",)),
        ("HYG_control_input", ("HYG",)),
        ("JNK_control_input", ("JNK",)),
    ]
    rows: list[dict[str, Any]] = []
    for item_id, symbols in groups:
        frames = [final_frames[symbol] for symbol in symbols if not final_frames[symbol].empty]
        common_dates = (
            set(normalized_dates(frames[0]["date"]).dt.strftime("%Y-%m-%d"))
            if frames
            else set()
        )
        for frame in frames[1:]:
            common_dates &= set(normalized_dates(frame["date"]).dt.strftime("%Y-%m-%d"))
        minimum_rows = min((len(frame) for frame in frames), default=0)
        warmup_required = (
            200
            if item_id
            in {
                "VM_observation_inputs",
                "DSR_observation_inputs",
                "frozen_current_active_vm_dsr_usci_combo",
            }
            else 1
        )
        ready = bool(
            committed
            and len(frames) == len(symbols)
            and REQUIRED_DATE.date().isoformat() in common_dates
            and minimum_rows >= warmup_required
        )
        rows.append(
            {
                "reference_or_input_id": item_id,
                "required_symbols": symbols,
                "required_session": REQUIRED_DATE.date().isoformat(),
                "required_session_common": REQUIRED_DATE.date().isoformat() in common_dates,
                "common_start": min(common_dates) if common_dates else "",
                "common_end": max(common_dates) if common_dates else "",
                "common_session_count": len(common_dates),
                "minimum_history_rows": minimum_rows,
                "warmup_rows_required": warmup_required,
                "warmup_sufficient": minimum_rows >= warmup_required,
                "data_only_reproducibility": "feasible" if ready else "blocked",
                "strategy_performance_calculated": False,
                "virtual_position_trade_or_nav_created": False,
            }
        )
    return rows


def run() -> dict[str, Any]:
    clean_output_and_staging()
    target_paths = [
        path
        for symbol in TARGET_SYMBOLS
        for path in (cache_path(symbol), metadata_path(symbol))
    ]
    protected_paths = list(PROTECTED_STATE_PATHS) + list(OPERATIONAL_PATHS) + list(PRIOR_EVIDENCE_PATHS)
    protected_before = hash_map(protected_paths)
    target_before = hash_map(target_paths)
    unrelated_cache_paths = [
        path
        for path in sorted((ROOT / "data" / "cache").glob("*"))
        if path.is_file() and path not in target_paths
    ]
    unrelated_before = hash_map(unrelated_cache_paths)

    existing_frames = {symbol: load_existing_cache(symbol) for symbol in TARGET_SYMBOLS}
    results: dict[str, dict[str, Any]] = {}
    difference_fields = [
        "symbol",
        "date",
        "field",
        "field_category",
        "prior_value",
        "candidate_value",
        "verification_fetch_value",
        "absolute_difference",
        "relative_difference",
        "candidate_matches_verification",
    ]
    difference_handle = (OUTPUT_DIR / "exact_overlap_field_differences.csv").open(
        "w", newline="", encoding="utf-8"
    )
    difference_writer = csv.DictWriter(
        difference_handle,
        fieldnames=difference_fields,
        extrasaction="ignore",
        lineterminator="\n",
    )
    difference_writer.writeheader()
    revision_rows: list[dict[str, Any]] = []
    reproducibility_rows: list[dict[str, Any]] = []
    serialization_root_rows: list[dict[str, Any]] = []
    serialization_hash_rows: list[dict[str, Any]] = []
    staged_integrity_rows: list[dict[str, Any]] = []

    prior_hash_failures = {"JNK", "QUAL", "XLP", "XLY"}
    for symbol in TARGET_SYMBOLS:
        old = existing_frames[symbol]
        start = (
            normalized_dates(old["date"]).min().date().isoformat()
            if not old.empty
            else "1990-01-01"
        )
        candidate_unrounded: pd.DataFrame | None = None
        verification_unrounded: pd.DataFrame | None = None
        candidate = pd.DataFrame(columns=NORMALIZED_COLUMNS)
        verification = pd.DataFrame(columns=NORMALIZED_COLUMNS)
        candidate_error = ""
        verification_error = ""
        try:
            candidate_unrounded, candidate = download_once(symbol, start)
        except BaseException as exc:  # noqa: BLE001 - verification fetch still must be attempted.
            candidate_error = sanitize_error(exc)
        try:
            verification_unrounded, verification = download_once(symbol, start)
        except BaseException as exc:  # noqa: BLE001 - every symbol receives a second bounded fetch.
            verification_error = sanitize_error(exc)
        candidate_hash = canonical_frame_hash(candidate, symbol) if not candidate.empty else ""
        verification_hash = (
            canonical_frame_hash(verification, symbol) if not verification.empty else ""
        )
        reproducible = bool(
            not candidate.empty
            and not verification.empty
            and candidate_hash == verification_hash
            and len(candidate) == len(verification)
        )
        reproducibility_rows.append(
            {
                "symbol": symbol,
                "provider": PROVIDER_ID,
                "candidate_fetch_attempts": 1,
                "verification_fetch_attempts": 1,
                "candidate_status": "returned" if not candidate.empty else "failed",
                "verification_status": "returned" if not verification.empty else "failed",
                "candidate_error": candidate_error,
                "verification_error": verification_error,
                "candidate_rows": len(candidate),
                "verification_rows": len(verification),
                "candidate_first_date": "" if candidate.empty else candidate.iloc[0]["date"],
                "candidate_last_date": "" if candidate.empty else candidate.iloc[-1]["date"],
                "verification_first_date": "" if verification.empty else verification.iloc[0]["date"],
                "verification_last_date": "" if verification.empty else verification.iloc[-1]["date"],
                "candidate_canonical_hash": candidate_hash,
                "verification_canonical_hash": verification_hash,
                "normalized_provider_frames_identical": reproducible,
                "alpaca_attempted": False,
            }
        )
        if not candidate.empty and not verification.empty:
            differences, revision = overlap_differences(symbol, old, candidate, verification)
        else:
            differences = []
            revision = {
                "symbol": symbol,
                "prior_rows": len(old),
                "candidate_rows": len(candidate),
                "overlap_rows": 0,
                "missing_prior_dates": len(old),
                "changed_rows": 0,
                "changed_fields": 0,
                "raw_price_rows_changed": 0,
                "raw_volume_rows_changed": 0,
                "corporate_action_rows_changed": 0,
                "adjustment_rows_changed": 0,
                "adjusted_price_rows_changed": 0,
                "raw_overlap_revision_classification": "provider_fetch_incomplete",
                "history_revision_classification": "provider_fetch_incomplete",
                "revision_explained": False,
                "acceptance_basis": "both required provider fetches were not available",
            }
        for difference in differences:
            difference_writer.writerow(
                {key: csv_value(value) for key, value in difference.items()}
            )
        revision_rows.append(revision)

        staged_hash = ""
        reloaded_hash = ""
        staged_hash_match = False
        serialization_error = ""
        if not candidate.empty:
            try:
                normalized_candidate = write_canonical_csv(
                    stage_cache_path(symbol), candidate, symbol
                )
                staged_hash = canonical_frame_hash(normalized_candidate, symbol)
                staged_reload = canonicalize_frame(pd.read_csv(stage_cache_path(symbol)), symbol)
                reloaded_hash = canonical_frame_hash(staged_reload, symbol)
                staged_hash_match = staged_hash == reloaded_hash
            except BaseException as exc:  # noqa: BLE001
                serialization_error = sanitize_error(exc)
        serialization_hash_rows.append(
            {
                "symbol": symbol,
                "canonical_columns_hashed": list(NORMALIZED_COLUMNS),
                "source_float_decimals": SOURCE_FLOAT_DECIMALS,
                "hash_float_decimals": HASH_FLOAT_DECIMALS,
                "csv_float_format": CSV_FLOAT_FORMAT,
                "missing_value_representation": MISSING_SENTINEL,
                "in_memory_canonical_hash": staged_hash,
                "staged_reloaded_canonical_hash": reloaded_hash,
                "hashes_match": staged_hash_match,
                "serialization_error": serialization_error,
            }
        )
        if not candidate.empty:
            serialization_root_rows.append(
                legacy_serialization_diagnosis(
                    symbol,
                    candidate,
                    symbol in prior_hash_failures,
                )
            )
        else:
            serialization_root_rows.append(
                {
                    "symbol": symbol,
                    "prior_serialization_failure_reported": symbol in prior_hash_failures,
                    "legacy_in_memory_hash": "",
                    "legacy_reloaded_hash": "",
                    "legacy_hashes_match": False,
                    "maximum_float_round_trip_difference": "",
                    "root_cause": "provider candidate unavailable for serialization diagnosis",
                    "correction": "canonical normalization specified but not executable",
                    "columns_omitted_from_corrected_hash": "",
                    "hash_comparison_weakened": False,
                }
            )
        checks = integrity_checks(
            symbol,
            candidate,
            old,
            reproducible,
            staged_hash_match,
        )
        staged_integrity_rows.extend(checks)
        integrity_pass = bool(checks and all(row["status"] == "pass" for row in checks))
        individual_pass = bool(
            reproducible
            and staged_hash_match
            and integrity_pass
            and revision["missing_prior_dates"] == 0
            and revision["revision_explained"]
        )
        failure_reason = ""
        failure_detail = ""
        if not candidate.empty and not verification.empty and not reproducible:
            failure_reason = "data_or_comparability_failure"
            failure_detail = "candidate and verification provider frames differ"
        elif candidate.empty or verification.empty:
            failure_reason = "capability_missing"
            failure_detail = candidate_error or verification_error or "provider fetch incomplete"
        elif not staged_hash_match:
            failure_reason = "methodology_failure"
            failure_detail = serialization_error or "canonical staged/reloaded hash mismatch"
        elif not integrity_pass:
            failure_reason = "methodology_failure"
            failure_detail = "|".join(
                row["check_name"] for row in checks if row["status"] == "fail"
            )
        elif not revision["revision_explained"] or revision["missing_prior_dates"]:
            failure_reason = "data_or_comparability_failure"
            failure_detail = revision["history_revision_classification"]
        results[symbol] = {
            "old": old,
            "candidate": candidate,
            "verification": verification,
            "candidate_unrounded": candidate_unrounded,
            "verification_unrounded": verification_unrounded,
            "candidate_hash": candidate_hash,
            "verification_hash": verification_hash,
            "staged_hash": staged_hash,
            "reloaded_hash": reloaded_hash,
            "provider_reproducible": reproducible,
            "serialization_pass": staged_hash_match,
            "integrity_pass": integrity_pass,
            "revision": revision,
            "individual_pass": individual_pass,
            "failure_reason": failure_reason,
            "failure_detail": failure_detail,
            "start": start,
        }

    difference_handle.close()
    xlc_rows = xlc_violation_analysis(
        results["XLC"]["candidate_unrounded"],
        results["XLC"]["verification_unrounded"],
    )
    xlc_pass = all(row["numerically_immaterial"] for row in xlc_rows)
    if not xlc_pass:
        results["XLC"]["individual_pass"] = False
        results["XLC"]["failure_reason"] = "methodology_failure"
        results["XLC"]["failure_detail"] = "material_or_unexplained_adjusted_ohlc_violation"

    all_individual_pass = all(results[symbol]["individual_pass"] for symbol in TARGET_SYMBOLS)
    version_seed = "\n".join(
        f"{symbol}|{results[symbol]['candidate_hash']}" for symbol in TARGET_SYMBOLS
    ).encode("utf-8")
    aggregate_hash = "sha256:" + hashlib.sha256(version_seed).hexdigest()
    data_version_id = (
        f"angl_observation_market_data_20260724_{aggregate_hash.split(':', 1)[1][:16]}"
        if all_individual_pass
        else ""
    )
    metadata_payloads: dict[str, dict[str, Any]] = {}
    for symbol in TARGET_SYMBOLS:
        result = results[symbol]
        metadata_payloads[symbol] = {
            "symbol": symbol,
            "task_id": TASK_ID,
            "data_version_id": data_version_id,
            "provider": PROVIDER_ID,
            "provider_path": "src.data._download_yfinance",
            "canonical_builder": "src.data.build_adjusted_ohlc",
            "acquisition_timestamp": CORRECTION_TIMESTAMP,
            "candidate_fetch_attempts": 1,
            "verification_fetch_attempts": 1,
            "request_start": result["start"],
            "request_end_exclusive": END_EXCLUSIVE,
            "required_session": REQUIRED_DATE.date().isoformat(),
            "canonical_normalization_spec": f"{TASK_ID}_canonical_normalization_v1",
            "canonical_schema": list(NORMALIZED_COLUMNS),
            "prior_cache_hash": target_before[rel(cache_path(symbol))],
            "prior_metadata_hash": target_before[rel(metadata_path(symbol))],
            "candidate_canonical_hash": result["candidate_hash"],
            "verification_canonical_hash": result["verification_hash"],
            "history_revision_classification": result["revision"][
                "history_revision_classification"
            ],
            "changed_overlap_rows": result["revision"]["changed_rows"],
            "changed_overlap_fields": result["revision"]["changed_fields"],
            "provider_history_revision": result["revision"][
                "history_revision_classification"
            ]
            not in {"overlap_identical", "new_cache_no_prior_history"},
            "normalized_provider_frames_identical": result["provider_reproducible"],
            "staged_reload_hash_match": result["serialization_pass"],
            "individual_integrity_pass": result["integrity_pass"],
            "cohort_commit_required": True,
            "alpaca_attempted": False,
            "broker_account_position_order_endpoint_called": False,
            "strategy_or_observation_execution": False,
        }

    committed = False
    commit_detail = "cohort_not_committed_due_individual_validation_failure"
    reload_rows: list[dict[str, Any]] = []
    if all_individual_pass:
        committed, commit_detail, reload_rows = cohort_commit(
            {symbol: results[symbol]["candidate"] for symbol in TARGET_SYMBOLS},
            metadata_payloads,
        )
    if not committed:
        reload_rows = [
            {
                "symbol": symbol,
                "normal_data_interface": "src.data.load_symbol_data",
                "load_source": "not_attempted_after_cohort_decision",
                "load_status": "blocked",
                "expected_rows": len(results[symbol]["candidate"]),
                "reloaded_rows": len(results[symbol]["old"]),
                "expected_canonical_hash": results[symbol]["candidate_hash"],
                "reloaded_canonical_hash": canonical_frame_hash(
                    results[symbol]["old"], symbol
                )
                if not results[symbol]["old"].empty
                else "",
                "reload_hash_match": False,
                "reload_pass": False,
            }
            for symbol in TARGET_SYMBOLS
        ]

    final_frames = {symbol: load_existing_cache(symbol) for symbol in TARGET_SYMBOLS}
    protected_after = hash_map(protected_paths)
    target_after = hash_map(target_paths)
    unrelated_after = hash_map(unrelated_cache_paths)
    outcome = OUTCOME_READY if committed else OUTCOME_BLOCKED
    observation_next = NEXT_READY if committed else NEXT_BLOCKED

    task_rows: list[dict[str, Any]] = []
    failure_rows: list[dict[str, Any]] = []
    for symbol in TARGET_SYMBOLS:
        result = results[symbol]
        stage = "feasible" if committed else "blocked"
        failure_reason = "" if committed else (
            result["failure_reason"] or "data_or_comparability_failure"
        )
        failure_detail = "" if committed else (
            result["failure_detail"]
            or "20-symbol cohort withheld because at least one symbol did not pass"
        )
        task_rows.append(
            {
                "task_id": f"{TASK_ID}__{symbol}",
                "symbol": symbol,
                "entity_type": "data_capability_task",
                "stage": stage,
                "adaptation_label": ADAPTATION_LABEL,
                "revision_classification": result["revision"][
                    "history_revision_classification"
                ],
                "serialization_result": (
                    "pass" if result["serialization_pass"] else "fail"
                ),
                "integrity_result": "pass" if result["integrity_pass"] else "fail",
                "provider_reproducibility": (
                    "pass" if result["provider_reproducible"] else "fail"
                ),
                "individual_validation_result": (
                    "pass" if result["individual_pass"] else "fail"
                ),
                "cache_decision": (
                    "committed_shared_data_version"
                    if committed
                    else "prior_cache_preserved_no_partial_cohort"
                ),
                "failure_reason": failure_reason,
                "next_action": "" if committed else NEXT_BLOCKED,
                "counted_as_strategy_or_trial": False,
            }
        )
        if failure_reason:
            failure_rows.append(
                {
                    "symbol": symbol,
                    "primary_failure_reason": failure_reason,
                    "failure_detail": failure_detail,
                    "individual_validation_pass": result["individual_pass"],
                    "cohort_committed": committed,
                    "prior_cache_preserved": (
                        target_before[rel(cache_path(symbol))]
                        == target_after[rel(cache_path(symbol))]
                    ),
                    "next_action": NEXT_BLOCKED,
                }
            )

    data_version_rows = []
    cache_rows = []
    for symbol in TARGET_SYMBOLS:
        result = results[symbol]
        data_version_rows.append(
            {
                "data_version_id": data_version_id,
                "symbol": symbol,
                "provider": PROVIDER_ID,
                "prior_cache_hash": target_before[rel(cache_path(symbol))],
                "prior_metadata_hash": target_before[rel(metadata_path(symbol))],
                "candidate_canonical_hash": result["candidate_hash"],
                "verification_canonical_hash": result["verification_hash"],
                "candidate_rows": len(result["candidate"]),
                "candidate_first_date": (
                    "" if result["candidate"].empty else result["candidate"].iloc[0]["date"]
                ),
                "candidate_last_date": (
                    "" if result["candidate"].empty else result["candidate"].iloc[-1]["date"]
                ),
                "history_revision_classification": result["revision"][
                    "history_revision_classification"
                ],
                "admitted_to_canonical_cache": committed,
                "cohort_atomicity": "all_20_or_none",
            }
        )
        for path in (cache_path(symbol), metadata_path(symbol)):
            path_text = rel(path)
            cache_rows.append(
                {
                    "symbol": symbol,
                    "path": path_text,
                    "file_role": "canonical_cache" if path.suffix == ".csv" else "acquisition_metadata",
                    "hash_before": target_before[path_text],
                    "hash_after": target_after[path_text],
                    "changed": target_before[path_text] != target_after[path_text],
                    "cohort_committed": committed,
                    "change_permitted": committed,
                }
            )

    sufficiency = sufficiency_rows(final_frames, committed)
    common_row = {
        "required_session": REQUIRED_DATE.date().isoformat(),
        "symbol_count": len(TARGET_SYMBOLS),
        "cohort_committed": committed,
        "symbols_with_required_session": sum(
            (normalized_dates(final_frames[symbol]["date"]) == REQUIRED_DATE).any()
            if not final_frames[symbol].empty
            else False
            for symbol in TARGET_SYMBOLS
        ),
        "all_required_symbols_same_session_ready": bool(
            committed
            and all(
                (normalized_dates(final_frames[symbol]["date"]) == REQUIRED_DATE).any()
                for symbol in TARGET_SYMBOLS
            )
        ),
        "frozen_reference_inputs_ready": next(
            row["data_only_reproducibility"]
            for row in sufficiency
            if row["reference_or_input_id"] == "frozen_current_active_vm_dsr_usci_combo"
        )
        == "feasible",
        "strategy_performance_calculated": False,
        "virtual_position_trade_or_nav_created": False,
    }

    state_rows: list[dict[str, Any]] = []
    protected_state_set = {rel(path) for path in PROTECTED_STATE_PATHS}
    operational_set = {rel(path) for path in OPERATIONAL_PATHS}
    prior_evidence_set = {rel(path) for path in PRIOR_EVIDENCE_PATHS}
    for path_text, before in protected_before.items():
        if path_text in protected_state_set:
            path_type = "protected_source_of_truth"
        elif path_text in operational_set:
            path_type = "protected_operational_forward_state"
        elif path_text in prior_evidence_set:
            path_type = "protected_prior_evidence"
        else:
            path_type = "protected_other"
        state_rows.append(
            {
                "path": path_text,
                "path_type": path_type,
                "hash_before": before,
                "hash_after": protected_after[path_text],
                "changed": before != protected_after[path_text],
                "change_permitted": False,
            }
        )
    for path_text, before in target_before.items():
        state_rows.append(
            {
                "path": path_text,
                "path_type": "authorized_20_symbol_cohort_cache_or_metadata",
                "hash_before": before,
                "hash_after": target_after[path_text],
                "changed": before != target_after[path_text],
                "change_permitted": committed,
            }
        )
    for path_text, before in unrelated_before.items():
        state_rows.append(
            {
                "path": path_text,
                "path_type": "protected_unrelated_cache",
                "hash_before": before,
                "hash_after": unrelated_after[path_text],
                "changed": before != unrelated_after[path_text],
                "change_permitted": False,
            }
        )
    unexpected_changes = [
        row["path"] for row in state_rows if row["changed"] and not row["change_permitted"]
    ]
    target_change_count = sum(row["changed"] for row in cache_rows)
    all_or_none_change = target_change_count in {0, 40}
    blocked_prior_preserved = committed or target_before == target_after
    all_fetches_two = all(
        row["candidate_fetch_attempts"] == 1 and row["verification_fetch_attempts"] == 1
        for row in reproducibility_rows
    )
    consistency = {
        "consistency_passed": bool(
            len(task_rows) == 20
            and all_fetches_two
            and all_or_none_change
            and blocked_prior_preserved
            and protected_before == protected_after
            and unrelated_before == unrelated_after
            and not unexpected_changes
            and all(row["failure_reason"] in ALLOWED_FAILURES for row in task_rows)
            and ((committed and target_change_count == 40) or (not committed and target_change_count == 0))
        ),
        "exact_symbols": list(TARGET_SYMBOLS),
        "exactly_20_data_tasks": len(task_rows) == 20,
        "candidate_and_verification_fetch_per_symbol": all_fetches_two,
        "total_provider_fetches": 40,
        "provider_paths_used": [PROVIDER_ID],
        "alpaca_retried": False,
        "all_normalized_provider_pairs_identical": all(
            result["provider_reproducible"] for result in results.values()
        ),
        "all_staged_reload_hashes_match": all(
            result["serialization_pass"] for result in results.values()
        ),
        "all_integrity_checks_pass": all(
            result["integrity_pass"] for result in results.values()
        ),
        "xlc_numerically_immaterial_only": xlc_pass,
        "cohort_commit_all_or_none": all_or_none_change,
        "cohort_committed": committed,
        "target_files_changed": target_change_count,
        "blocked_cohort_prior_cache_preserved": blocked_prior_preserved,
        "protected_state_and_prior_evidence_unchanged": protected_before == protected_after,
        "unrelated_cache_hashes_unchanged": unrelated_before == unrelated_after,
        "unexpected_changes": unexpected_changes,
        "strategy_configurations_created": 0,
        "experiment_trials_created": 0,
        "observations_created": 0,
        "observations_activated": 0,
        "forward_records_created": 0,
        "strategy_performance_calculated": False,
        "virtual_positions_trades_or_nav_created": False,
        "broker_account_position_order_endpoint_called": False,
        "paper_or_live_order_submitted": False,
        "real_money_action": False,
        "outcome": outcome,
        "observation_next_action": observation_next,
        "project_discovery_next_action": PROJECT_NEXT_ACTION,
    }

    strategy_row = {
        "strategy_id": STRATEGY_ID,
        "family_id": FAMILY_ID,
        "entity_type": "strategy_configuration",
        "stage": "paper_demo_eligible",
        "outcome": "paper_demo_eligible",
        "route": "diversifier_only",
        "read_only": True,
        "created_in_this_task": False,
        "rules_changed": False,
    }
    observation_row = {
        "observation_id": OBSERVATION_ID,
        "entity_type": "paper_demo_observation",
        "stage": "blocked",
        "outcome": "observation_invalid_or_incomplete",
        "failure_reason": "data_unavailable",
        "first_forward_observation_date": "",
        "read_only": True,
        "created_in_this_task": False,
        "activated_in_this_task": False,
        "forward_record_created": False,
    }
    process_row = {
        "task_id": TASK_ID,
        "entity_type": "process_task",
        "stage": "correction",
        "adaptation_label": ADAPTATION_LABEL,
        "counted_as_strategy_or_trial": False,
        "provider_fetches": 40,
        "strategy_performance_calculated": False,
    }
    commit_row = {
        "task_id": TASK_ID,
        "data_version_id": data_version_id,
        "all_20_individual_validations_passed": all_individual_pass,
        "xlc_gate_passed": xlc_pass,
        "cohort_committed": committed,
        "commit_policy": "all_20_cache_and_metadata_files_or_none",
        "commit_detail": commit_detail,
        "target_files_changed": target_change_count,
        "mixed_observation_data_version_created": False,
    }
    outcome_row = {
        "task_id": TASK_ID,
        "outcome": outcome,
        "data_version_id": data_version_id,
        "symbols_processed": 20,
        "symbols_individually_passed": sum(
            result["individual_pass"] for result in results.values()
        ),
        "symbols_blocked": sum(
            not result["individual_pass"] for result in results.values()
        ),
        "cohort_committed": committed,
        "cache_files_updated": 20 if committed else 0,
        "metadata_files_updated": 20 if committed else 0,
        "strategy_configurations_created": 0,
        "experiment_trials_created": 0,
        "observations_created": 0,
        "observations_activated": 0,
        "forward_records_created": 0,
        "observation_next_action": observation_next,
        "project_discovery_next_action": PROJECT_NEXT_ACTION,
    }
    next_rows = [
        {
            "action_scope": "ANGL_observation",
            "exact_next_action": observation_next,
            "execute_in_this_task": False,
        },
        {
            "action_scope": "separate_project_discovery",
            "exact_next_action": PROJECT_NEXT_ACTION,
            "execute_in_this_task": False,
        },
    ]

    write_yaml(
        OUTPUT_DIR / "correction_manifest.yaml",
        {
            "task_id": TASK_ID,
            "mode": "correction",
            "stage": "correction",
            "adaptation_label": ADAPTATION_LABEL,
            "strategy_id": STRATEGY_ID,
            "observation_id": OBSERVATION_ID,
            "required_session": REQUIRED_DATE.date().isoformat(),
            "symbols": list(TARGET_SYMBOLS),
            "provider": PROVIDER_ID,
            "fetches_per_symbol": 2,
            "data_version_id": data_version_id,
            "outcome": outcome,
            "cohort_committed": committed,
            "strategy_configurations_created": 0,
            "experiment_trials_created": 0,
            "observations_created": 0,
            "observations_activated": 0,
            "forward_records_created": 0,
            "data_capability_tasks": 20,
            "process_tasks": 1,
            "observation_next_action": observation_next,
            "project_discovery_next_action": PROJECT_NEXT_ACTION,
        },
    )
    write_csv(OUTPUT_DIR / "strategy_cards.csv", [strategy_row], list(strategy_row))
    trials = prior.trial_rows()
    write_csv(
        OUTPUT_DIR / "trial_ledger.csv",
        trials,
        [
            "trial_id",
            "parent_trial_id",
            "strategy_id",
            "entity_type",
            "stage",
            "adaptation_label",
            "outcome",
            "read_only",
            "source_path",
            "new_trial_created",
        ],
    )
    write_csv(
        OUTPUT_DIR / "paper_demo_observations.csv",
        [observation_row],
        list(observation_row),
    )
    write_csv(OUTPUT_DIR / "data_capability_task_log.csv", task_rows, list(task_rows[0]))
    write_csv(OUTPUT_DIR / "process_task_log.csv", [process_row], list(process_row))
    write_csv(
        OUTPUT_DIR / "provider_fetch_reproducibility.csv",
        reproducibility_rows,
        list(reproducibility_rows[0]),
    )
    write_csv(
        OUTPUT_DIR / "history_revision_classification.csv",
        revision_rows,
        list(revision_rows[0]),
    )
    write_yaml(
        OUTPUT_DIR / "canonical_normalization_spec.yaml",
        {
            "spec_id": f"{TASK_ID}_canonical_normalization_v1",
            "column_order": list(NORMALIZED_COLUMNS),
            "date_type": "UTC-normalized timezone-naive calendar date serialized YYYY-MM-DD",
            "row_order": "ascending date stable mergesort",
            "ticker_type": "non-null string",
            "integer_columns": list(INTEGER_COLUMNS),
            "integer_rule": "finite integer-valued volume rounded only after <=1e-6 integer check",
            "float_columns": list(FLOAT_COLUMNS),
            "float_dtype": "float64",
            "source_float_decimals": SOURCE_FLOAT_DECIMALS,
            "negative_zero": "normalized to positive zero",
            "missing_value_representation": MISSING_SENTINEL,
            "csv_float_format": CSV_FLOAT_FORMAT,
            "hash_float_decimals": HASH_FLOAT_DECIMALS,
            "hash_columns_omitted": [],
            "derived_field_rule": "rebuild all adjusted fields from normalized raw source columns",
            "hash_algorithm": "sha256 over normalized header and every normalized cell",
        },
    )
    write_csv(
        OUTPUT_DIR / "serialization_root_causes.csv",
        serialization_root_rows,
        list(serialization_root_rows[0]),
    )
    write_csv(
        OUTPUT_DIR / "serialization_hash_reconciliation.csv",
        serialization_hash_rows,
        list(serialization_hash_rows[0]),
    )
    write_csv(
        OUTPUT_DIR / "xlc_ohlc_violation_analysis.csv",
        xlc_rows,
        list(xlc_rows[0]),
    )
    write_csv(
        OUTPUT_DIR / "staged_data_integrity_checks.csv",
        staged_integrity_rows,
        ["symbol", "check_name", "status", "violation_count", "details"],
    )
    write_csv(
        OUTPUT_DIR / "data_version_manifest.csv",
        data_version_rows,
        list(data_version_rows[0]),
    )
    write_csv(
        OUTPUT_DIR / "cohort_commit_decision.csv",
        [commit_row],
        list(commit_row),
    )
    write_csv(OUTPUT_DIR / "cache_before_after.csv", cache_rows, list(cache_rows[0]))
    write_csv(
        OUTPUT_DIR / "cache_reload_reconciliation.csv",
        reload_rows,
        list(reload_rows[0]),
    )
    write_csv(
        OUTPUT_DIR / "reference_input_sufficiency.csv",
        sufficiency,
        list(sufficiency[0]),
    )
    write_csv(
        OUTPUT_DIR / "common_session_sufficiency.csv",
        [common_row],
        list(common_row),
    )
    write_csv(OUTPUT_DIR / "state_change_manifest.csv", state_rows, list(state_rows[0]))
    write_csv(OUTPUT_DIR / "outcome_summary.csv", [outcome_row], list(outcome_row))
    write_csv(
        OUTPUT_DIR / "failure_reasons.csv",
        failure_rows,
        [
            "symbol",
            "primary_failure_reason",
            "failure_detail",
            "individual_validation_pass",
            "cohort_committed",
            "prior_cache_preserved",
            "next_action",
        ],
    )
    write_csv(OUTPUT_DIR / "next_actions.csv", next_rows, list(next_rows[0]))
    write_json(OUTPUT_DIR / "consistency_check.json", consistency)
    revision_counts = (
        pd.DataFrame(revision_rows)["history_revision_classification"].value_counts().to_dict()
    )
    write_text(
        OUTPUT_DIR / "correction_report.md",
        f"""# Observation Market-Data Versioning and Serialization Correction v1

## Outcome

- Outcome: `{outcome}`
- Shared data version: `{data_version_id}`
- Symbols processed: `20`
- Provider fetches: `40` (candidate plus verification for each symbol)
- Individual validations passed: `{outcome_row['symbols_individually_passed']} / 20`
- Cohort committed: `{str(committed).lower()}`
- Target cache/metadata files changed: `{target_change_count}`
- Revision classifications: `{json.dumps(revision_counts, sort_keys=True)}`

The corrected hash includes every canonical column after fixed date, dtype, row-order,
missing-value, negative-zero, and float-precision normalization. XLC prices were not
clipped, rewritten, or deleted. The cache transaction was all-or-none.

No strategy return, performance metric, forward NAV, virtual position, virtual trade,
strategy configuration, experiment trial, observation, activation, broker call, or order
was created.

## Next Actions

- Observation: `{observation_next}` (not executed)
- Separate project discovery: `{PROJECT_NEXT_ACTION}` (not executed)
""",
    )

    for path in (STAGING_DIR, BACKUP_DIR):
        if path.exists():
            shutil.rmtree(path)
    return {
        "task_id": TASK_ID,
        "output_dir": rel(OUTPUT_DIR),
        "outcome": outcome,
        "data_version_id": data_version_id,
        "symbols_processed": 20,
        "symbols_individually_passed": outcome_row["symbols_individually_passed"],
        "cohort_committed": committed,
        "target_files_changed": target_change_count,
        "observation_next_action": observation_next,
        "project_discovery_next_action": PROJECT_NEXT_ACTION,
        "consistency_passed": consistency["consistency_passed"],
    }


def main() -> int:
    result = run()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["consistency_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
