from __future__ import annotations

import csv
import hashlib
import json
import math
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from src.data import NORMALIZED_COLUMNS, _download_yfinance, build_adjusted_ohlc, load_symbol_data
from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT


TASK_ID = "remediate_angl_observation_required_market_data_v1"
OUTPUT_DIR = ROOT / "evidence" / "data_capability" / TASK_ID / "latest"
STAGING_DIR = ROOT / "data" / "cache" / f".{TASK_ID}_staging"
REQUIRED_DATE = pd.Timestamp("2026-07-24")
END_EXCLUSIVE = "2026-07-25"
ACQUISITION_TIMESTAMP = "2026-07-25T00:00:00+00:00"

STRATEGY_ID = "ice_vaneck_us_fallen_angel_angl_v1"
FAMILY_ID = "fallen_angel_credit_anomaly"
OBSERVATION_ID = "paper_forward_angl_20pct_diversifier_v1"
PARENT_TRIAL_ID = "correction_angl__ice_vaneck_us_fallen_angel_angl_v1__methodology_correction_child"
ADAPTATION_LABEL = "data_feasibility_adjustment"
PROVIDER_ID = "yfinance_existing_repo_supported_adjusted_daily_path"
OUTCOME_READY = "all_required_observation_data_feasible"
OUTCOME_BLOCKED = "partial_or_failed_observation_data_remediation"
NEXT_READY = "rerun_initialize_angl_after_market_data_remediation_v1"
NEXT_BLOCKED = "direction_owner_review_remaining_angl_data_block_v1"
PROJECT_NEXT_ACTION = "refresh_strategy_source_library_v3"

TARGET_SYMBOLS = (
    "ANGL",
    "BIL",
    "DBC",
    "HYG",
    "JNK",
    "QUAL",
    "SPLV",
    "SPY",
    "USCI",
    "USMV",
    "XLB",
    "XLC",
    "XLE",
    "XLF",
    "XLI",
    "XLK",
    "XLP",
    "XLU",
    "XLV",
    "XLY",
)
VM_SYMBOLS = ("SPLV", "USMV", "QUAL", "SPY", "BIL")
DSR_SYMBOLS = ("XLK", "XLF", "XLE", "XLV", "XLY", "XLP", "XLU", "XLI", "XLB", "XLC", "BIL")
USCI_SYMBOLS = ("USCI", "DBC", "BIL", "SPY")
REFERENCE_SYMBOLS = tuple(sorted(set(VM_SYMBOLS + DSR_SYMBOLS + USCI_SYMBOLS)))

REGISTRY_PATH = ROOT / "strategy_lab" / "strategy_registry.yaml"
ROADMAP_PATH = ROOT / "strategy_lab" / "RESEARCH_ROADMAP.md"
QUEUE_PATH = ROOT / "strategy_lab" / "research_os" / "research" / "research_queue.yaml"
FAMILY_LEDGER_PATH = ROOT / "strategy_lab" / "research_os" / "family_lineage" / "family_ledger.yaml"
ACTIVE_OBSERVATIONS_PATH = ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml"
PROTECTED_STATE_PATHS = (
    REGISTRY_PATH,
    ROADMAP_PATH,
    QUEUE_PATH,
    FAMILY_LEDGER_PATH,
    ACTIVE_OBSERVATIONS_PATH,
)

PRIOR_INITIALIZATION_DIR = ROOT / "evidence" / "paper_demo" / "initialize_angl_after_next_completed_common_session_v1" / "latest"
PRIOR_EVIDENCE_PATHS = tuple(path for path in sorted(PRIOR_INITIALIZATION_DIR.glob("*")) if path.is_file())
OPERATIONAL_PATHS = (
    ROOT / "paper_forward_observations" / OBSERVATION_ID / "active_observation.yaml",
    ROOT / "paper_forward_observations" / OBSERVATION_ID / "forward_observation_ledger.csv",
    ROOT / "paper_forward_observations" / OBSERVATION_ID / "virtual_positions.csv",
    ROOT / "paper_forward_observations" / OBSERVATION_ID / "virtual_trades.csv",
)
ALLOWED_FAILURES = {
    "",
    "data_unavailable",
    "capability_missing",
    "data_or_comparability_failure",
    "methodology_failure",
}


def rel(path: str | Path) -> str:
    value = Path(path)
    try:
        return value.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return value.as_posix()


def csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return "" if not math.isfinite(value) else f"{value:.12g}"
    if isinstance(value, (dict, list, tuple, set)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    return str(value)


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: csv_value(row.get(field, "")) for field in fields})


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False, width=120, allow_unicode=False), encoding="utf-8")


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value.rstrip() + "\n", encoding="utf-8")


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def file_hash(path: Path) -> str:
    if not path.exists():
        return "missing"
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def frame_hash(frame: pd.DataFrame) -> str:
    normalized = frame.copy()
    normalized["date"] = pd.to_datetime(normalized["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    normalized = normalized.sort_values("date")
    payload = normalized.to_csv(index=False, lineterminator="\n").encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def hash_map(paths: tuple[Path, ...] | list[Path]) -> dict[str, str]:
    return {rel(path): file_hash(path) for path in paths}


def clean_paths() -> None:
    if OUTPUT_DIR.exists():
        resolved = OUTPUT_DIR.resolve()
        expected = (ROOT / "evidence" / "data_capability" / TASK_ID).resolve()
        if expected not in resolved.parents:
            raise RuntimeError(f"Refusing to remove unexpected output directory: {resolved}")
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if STAGING_DIR.exists():
        resolved = STAGING_DIR.resolve()
        expected = (ROOT / "data" / "cache").resolve()
        if resolved.parent != expected:
            raise RuntimeError(f"Refusing to remove unexpected staging directory: {resolved}")
        shutil.rmtree(STAGING_DIR)
    STAGING_DIR.mkdir(parents=True, exist_ok=True)


def cache_path(symbol: str) -> Path:
    return ROOT / "data" / "cache" / f"{symbol}.csv"


def metadata_path(symbol: str) -> Path:
    return ROOT / "data" / "cache" / f"{symbol}.acquisition.json"


def load_cache(symbol: str) -> pd.DataFrame:
    path = cache_path(symbol)
    if not path.exists():
        return pd.DataFrame(columns=NORMALIZED_COLUMNS)
    frame = build_adjusted_ohlc(pd.read_csv(path), symbol)
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    return frame[NORMALIZED_COLUMNS]


def sanitize_error(exc: BaseException) -> str:
    text = str(exc).replace("\r", " ").replace("\n", " ")
    for token in ("APCA-API-KEY-ID", "APCA-API-SECRET-KEY", "ALPACA_PAPER_API_KEY", "ALPACA_PAPER_SECRET_KEY"):
        text = text.replace(token, f"{token}_REDACTED")
    return text[:500]


def integrity_rows(symbol: str, frame: pd.DataFrame, old: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    def add(check: str, passed: bool, details: str = "", violations: int | str = "") -> None:
        rows.append(
            {
                "symbol": symbol,
                "check_name": check,
                "status": "pass" if passed else "fail",
                "violation_count": violations,
                "details": details,
            }
        )

    if frame.empty:
        add("non_empty_frame", False, "no staged rows", 1)
        return rows
    dates = pd.to_datetime(frame["date"], errors="coerce")
    add("correct_instrument_identity", bool(frame["symbol"].astype(str).eq(symbol).all()), "", int((frame["symbol"] != symbol).sum()))
    add("canonical_schema", list(frame.columns) == list(NORMALIZED_COLUMNS), "|".join(frame.columns), "")
    add("dates_parse", bool(dates.notna().all()), "", int(dates.isna().sum()))
    add("dates_strictly_increasing", bool(dates.is_monotonic_increasing), "", "")
    add("dates_unique", bool(not dates.duplicated().any()), "", int(dates.duplicated().sum()))
    add("no_duplicate_rows", bool(not frame.duplicated().any()), "", int(frame.duplicated().sum()))
    add(
        "no_impossible_timestamps",
        bool(dates.notna().all() and (dates.dt.weekday < 5).all() and (dates >= pd.Timestamp("1900-01-01")).all()),
        "",
        int((dates.dt.weekday >= 5).sum()),
    )
    add(
        "no_future_rows_beyond_completed_session",
        bool(dates.max() <= REQUIRED_DATE),
        f"last={dates.max().date().isoformat()};limit={REQUIRED_DATE.date().isoformat()}",
        int((dates > REQUIRED_DATE).sum()),
    )
    add(
        "required_2026_07_24_present",
        bool((dates == REQUIRED_DATE).any()),
        f"last={dates.max().date().isoformat()}",
        0 if (dates == REQUIRED_DATE).any() else 1,
    )
    adjusted = frame[["open", "high", "low", "close", "adj_close"]].apply(pd.to_numeric, errors="coerce")
    finite = np.isfinite(adjusted.to_numpy(dtype=float))
    add("adjusted_prices_finite", bool(finite.all()), "", int((~finite).sum()))
    add("adjusted_prices_positive", bool((adjusted > 0).all().all()), "", int((adjusted <= 0).sum().sum()))
    volume = pd.to_numeric(frame["volume"], errors="coerce")
    add(
        "adjusted_volume_nonnegative_finite",
        bool(volume.notna().all() and np.isfinite(volume.to_numpy(dtype=float)).all() and (volume >= 0).all()),
        "",
        int(volume.isna().sum() + (volume < 0).sum()),
    )
    high_ok = frame["high"] + 1e-9 >= frame[["open", "low", "close"]].max(axis=1)
    low_ok = frame["low"] <= frame[["open", "high", "close"]].min(axis=1) + 1e-9
    add("adjusted_ohlc_relationships", bool(high_ok.all() and low_ok.all()), "", int((~high_ok).sum() + (~low_ok).sum()))
    factor = pd.to_numeric(frame["adjustment_factor"], errors="coerce")
    factor_ok = factor.notna() & np.isfinite(factor.to_numpy(dtype=float)) & (factor > 0)
    add("adjustment_factor_positive_finite", bool(factor_ok.all()), "", int((~factor_ok).sum()))
    factor_math = np.isclose(
        pd.to_numeric(frame["raw_close"], errors="coerce") * factor,
        pd.to_numeric(frame["raw_adj_close"], errors="coerce"),
        rtol=1e-10,
        atol=1e-8,
    )
    add("adjustment_factor_matches_raw_adjusted_close", bool(factor_math.all()), "", int((~factor_math).sum()))
    if old.empty:
        add("existing_history_not_truncated", True, "no prior cache", 0)
    else:
        old_dates = set(pd.to_datetime(old["date"]).dt.strftime("%Y-%m-%d"))
        new_dates = set(dates.dt.strftime("%Y-%m-%d"))
        missing_old = sorted(old_dates - new_dates)
        add(
            "existing_history_not_truncated",
            not missing_old and dates.min() <= pd.to_datetime(old["date"]).min(),
            "missing_prior_dates=" + "|".join(missing_old[:20]),
            len(missing_old),
        )
    return rows


def overlap_reconciliation(symbol: str, old: pd.DataFrame, candidate: pd.DataFrame) -> dict[str, Any]:
    if old.empty:
        return {
            "symbol": symbol,
            "overlap_start": "",
            "overlap_end": "",
            "overlap_rows": 0,
            "missing_prior_dates": 0,
            "raw_rows_changed": 0,
            "corporate_action_rows_changed": 0,
            "adjusted_rows_changed": 0,
            "maximum_raw_absolute_difference": 0.0,
            "maximum_corporate_action_absolute_difference": 0.0,
            "maximum_adjusted_absolute_difference": 0.0,
            "adjustment_ratio_dispersion": 0.0,
            "reconciliation_classification": "new_cache_no_prior_overlap",
            "explicit_acceptance_basis": "no prior canonical history existed",
            "acceptable": True,
        }
    old_indexed = old.copy()
    new_indexed = candidate.copy()
    old_indexed.index = pd.to_datetime(old_indexed["date"])
    new_indexed.index = pd.to_datetime(new_indexed["date"])
    common = old_indexed.index.intersection(new_indexed.index)
    missing = old_indexed.index.difference(new_indexed.index)
    raw_columns = ["raw_open", "raw_high", "raw_low", "raw_close", "raw_volume"]
    corporate_action_columns = ["dividends", "stock_splits"]
    adjusted_columns = ["open", "high", "low", "close", "adj_close", "volume"]
    old_raw = old_indexed.loc[common, raw_columns].astype(float)
    new_raw = new_indexed.loc[common, raw_columns].astype(float)
    old_actions = old_indexed.loc[common, corporate_action_columns].astype(float)
    new_actions = new_indexed.loc[common, corporate_action_columns].astype(float)
    old_adjusted = old_indexed.loc[common, adjusted_columns].astype(float)
    new_adjusted = new_indexed.loc[common, adjusted_columns].astype(float)
    raw_delta = (old_raw - new_raw).abs()
    action_delta = (old_actions - new_actions).abs()
    adjusted_delta = (old_adjusted - new_adjusted).abs()
    raw_changed = ~np.isclose(old_raw, new_raw, rtol=1e-10, atol=1e-8)
    action_changed = ~np.isclose(old_actions, new_actions, rtol=1e-10, atol=1e-8)
    adjusted_changed = ~np.isclose(old_adjusted, new_adjusted, rtol=1e-10, atol=1e-8)
    raw_changed_rows = int(raw_changed.any(axis=1).sum())
    action_changed_rows = int(action_changed.any(axis=1).sum())
    adjusted_changed_rows = int(adjusted_changed.any(axis=1).sum())
    old_adj = old_indexed.loc[common, "adj_close"].astype(float)
    new_adj = new_indexed.loc[common, "adj_close"].astype(float)
    ratio = (new_adj / old_adj).replace([np.inf, -np.inf], np.nan).dropna()
    ratio_dispersion = float(ratio.max() - ratio.min()) if len(ratio) else float("nan")
    if len(missing):
        classification = "incompatible_history_truncation"
        acceptable = False
        basis = "candidate omitted dates present in the prior canonical cache"
    elif raw_changed_rows == 0 and action_changed_rows == 0 and adjusted_changed_rows == 0:
        classification = "overlap_identical"
        acceptable = True
        basis = "all raw and adjusted overlap values match within strict tolerance"
    elif raw_changed_rows == 0:
        classification = "legitimate_adjustment_history_rebuild"
        acceptable = True
        basis = (
            "raw OHLCV is unchanged; adjusted prices and any corporate-action revisions "
            "are explicitly recorded as a canonical provider adjustment-history rebuild"
        )
    else:
        classification = "provider_history_revision_requires_rejection"
        acceptable = False
        basis = "one or more overlapping raw OHLCV rows changed"
    return {
        "symbol": symbol,
        "overlap_start": "" if not len(common) else common.min().date().isoformat(),
        "overlap_end": "" if not len(common) else common.max().date().isoformat(),
        "overlap_rows": len(common),
        "missing_prior_dates": len(missing),
        "raw_rows_changed": raw_changed_rows,
        "corporate_action_rows_changed": action_changed_rows,
        "adjusted_rows_changed": adjusted_changed_rows,
        "maximum_raw_absolute_difference": float(raw_delta.max().max()) if not raw_delta.empty else 0.0,
        "maximum_corporate_action_absolute_difference": (
            float(action_delta.max().max()) if not action_delta.empty else 0.0
        ),
        "maximum_adjusted_absolute_difference": float(adjusted_delta.max().max()) if not adjusted_delta.empty else 0.0,
        "adjustment_ratio_dispersion": ratio_dispersion,
        "reconciliation_classification": classification,
        "explicit_acceptance_basis": basis,
        "acceptable": acceptable,
    }


def reload_via_normal_interface(symbol: str, expected: pd.DataFrame) -> dict[str, Any]:
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
    loaded_hash = frame_hash(loaded) if loaded is not None and not loaded.empty else ""
    expected_hash = frame_hash(expected)
    passed = bool(
        loaded is not None
        and not loaded.empty
        and len(loaded) == len(expected)
        and loaded_hash == expected_hash
        and coverage.get("status") == "valid"
        and source == "cache"
    )
    return {
        "symbol": symbol,
        "normal_data_interface": "src.data.load_symbol_data",
        "load_source": source,
        "load_status": coverage.get("status", ""),
        "staged_row_count": len(expected),
        "reloaded_row_count": 0 if loaded is None else len(loaded),
        "staged_frame_hash": expected_hash,
        "reloaded_frame_hash": loaded_hash,
        "staged_and_reloaded_hashes_match": passed,
        "reload_pass": passed,
    }


def download_one(symbol: str, start: str) -> pd.DataFrame:
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
    frame = build_adjusted_ohlc(raw, symbol)
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    frame = frame[pd.to_datetime(frame["date"]) <= REQUIRED_DATE].copy()
    return frame[NORMALIZED_COLUMNS]


def remediate_symbol(symbol: str) -> dict[str, Any]:
    target = cache_path(symbol)
    metadata = metadata_path(symbol)
    old_cache_bytes = target.read_bytes() if target.exists() else None
    old_metadata_bytes = metadata.read_bytes() if metadata.exists() else None
    old = load_cache(symbol)
    cache_before_hash = file_hash(target)
    metadata_before_hash = file_hash(metadata)
    first_date = (
        pd.to_datetime(old["date"]).min().date().isoformat()
        if not old.empty
        else "1990-01-01"
    )
    integrity: list[dict[str, Any]] = []
    overlap = overlap_reconciliation(symbol, old, pd.DataFrame(columns=NORMALIZED_COLUMNS))
    reload = {
        "symbol": symbol,
        "normal_data_interface": "src.data.load_symbol_data",
        "load_source": "",
        "load_status": "",
        "staged_row_count": 0,
        "reloaded_row_count": 0,
        "staged_frame_hash": "",
        "reloaded_frame_hash": "",
        "staged_and_reloaded_hashes_match": False,
        "reload_pass": False,
    }
    provider_status = ""
    acquisition_result = ""
    validation_result = ""
    failure_reason = ""
    failure_detail = ""
    candidate = pd.DataFrame(columns=NORMALIZED_COLUMNS)
    staged_cache = STAGING_DIR / f"{symbol}.csv"
    staged_metadata = STAGING_DIR / f"{symbol}.acquisition.json"
    cache_replaced = False
    try:
        candidate = download_one(symbol, first_date)
        provider_status = "returned_single_symbol_daily_history"
        integrity = integrity_rows(symbol, candidate, old)
        overlap = overlap_reconciliation(symbol, old, candidate)
        mandatory_pass = all(row["status"] == "pass" for row in integrity) and bool(overlap["acceptable"])
        if not mandatory_pass:
            validation_result = "staged_validation_failed"
            failure_reason = "data_or_comparability_failure"
            failed_checks = [row["check_name"] for row in integrity if row["status"] == "fail"]
            failure_detail = "|".join(failed_checks + [str(overlap["reconciliation_classification"])])
            acquisition_result = "prior_cache_preserved"
            raise RuntimeError(failure_detail)
        candidate.to_csv(staged_cache, index=False, lineterminator="\n")
        stage_reloaded = build_adjusted_ohlc(pd.read_csv(staged_cache), symbol)
        stage_reloaded["date"] = pd.to_datetime(stage_reloaded["date"]).dt.strftime("%Y-%m-%d")
        stage_reloaded = stage_reloaded[NORMALIZED_COLUMNS]
        if frame_hash(stage_reloaded) != frame_hash(candidate):
            validation_result = "staged_serialization_hash_mismatch"
            failure_reason = "methodology_failure"
            failure_detail = "staged and in-memory canonical frame hashes differ"
            acquisition_result = "prior_cache_preserved"
            raise RuntimeError(failure_detail)
        provenance = {
            "symbol": symbol,
            "task_id": TASK_ID,
            "provider": PROVIDER_ID,
            "provider_identity": "Yahoo Finance through existing src.data._download_yfinance path",
            "provider_role": "single_existing_repository_supported_adjusted_daily_path",
            "acquisition_timestamp": ACQUISITION_TIMESTAMP,
            "request_start": first_date,
            "request_end_exclusive": END_EXCLUSIVE,
            "request_settings": {
                "auto_adjust": False,
                "actions": True,
                "progress": False,
                "multi_level_index": False,
                "timeout": 30,
            },
            "adjustment_method": "raw_adj_close_divided_by_raw_close_then_applied_to_raw_ohlc",
            "canonical_schema": list(NORMALIZED_COLUMNS),
            "staged_frame_hash": frame_hash(candidate),
            "overlap_reconciliation": overlap,
            "alpaca_attempted": False,
            "account_position_or_order_endpoint_called": False,
            "strategy_or_observation_execution": False,
        }
        staged_metadata.write_text(json.dumps(provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        staged_cache.replace(target)
        staged_metadata.replace(metadata)
        cache_replaced = True
        reload = reload_via_normal_interface(symbol, candidate)
        if not reload["reload_pass"]:
            validation_result = "normal_interface_reload_failed"
            failure_reason = "methodology_failure"
            failure_detail = "src.data.load_symbol_data did not reproduce the staged canonical frame"
            acquisition_result = "replacement_rolled_back"
            raise RuntimeError(failure_detail)
        final_metadata = json.loads(metadata.read_text(encoding="utf-8"))
        final_metadata.update(
            {
                "cache_path": rel(target),
                "cache_file_hash": file_hash(target),
                "canonical_frame_hash": frame_hash(candidate),
                "metadata_path": rel(metadata),
                "admitted_to_canonical_cache": True,
                "first_valid_date": str(candidate.iloc[0]["date"]),
                "last_valid_date": str(candidate.iloc[-1]["date"]),
                "row_count": len(candidate),
                "normal_interface_reload_pass": True,
            }
        )
        metadata.write_text(json.dumps(final_metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        validation_result = "all_mandatory_checks_passed"
        acquisition_result = "canonical_cache_atomically_replaced"
    except BaseException as exc:  # noqa: BLE001 - every symbol must produce an auditable result and continue.
        if not failure_reason:
            provider_status = provider_status or "provider_call_failed"
            failure_reason = "data_unavailable"
            failure_detail = sanitize_error(exc)
            validation_result = "not_validated"
            acquisition_result = "prior_cache_preserved"
        if cache_replaced:
            if old_cache_bytes is None:
                target.unlink(missing_ok=True)
            else:
                target.write_bytes(old_cache_bytes)
            if old_metadata_bytes is None:
                metadata.unlink(missing_ok=True)
            else:
                metadata.write_bytes(old_metadata_bytes)
        staged_cache.unlink(missing_ok=True)
        staged_metadata.unlink(missing_ok=True)
    final = load_cache(symbol)
    final_valid = (
        not final.empty
        and pd.to_datetime(final["date"]).max() >= REQUIRED_DATE
        and (pd.to_datetime(final["date"]) == REQUIRED_DATE).any()
    )
    stage = "feasible" if validation_result == "all_mandatory_checks_passed" and final_valid else "blocked"
    if stage == "feasible":
        failure_reason = ""
        failure_detail = ""
    elif not failure_reason:
        failure_reason = "data_unavailable"
        failure_detail = "canonical cache does not contain 2026-07-24"
    return {
        "symbol": symbol,
        "stage": stage,
        "provider_attempted": PROVIDER_ID,
        "provider_status": provider_status,
        "acquisition_result": acquisition_result,
        "validation_result": validation_result,
        "failure_reason": failure_reason,
        "failure_detail": failure_detail,
        "attempt_count": 1,
        "alpaca_attempted": False,
        "cache_replaced": cache_before_hash != file_hash(target),
        "cache_before_hash": cache_before_hash,
        "cache_after_hash": file_hash(target),
        "metadata_before_hash": metadata_before_hash,
        "metadata_after_hash": file_hash(metadata),
        "cache_state_before": (
            "missing"
            if old.empty
            else f"{old.iloc[0]['date']}..{old.iloc[-1]['date']} rows={len(old)}"
        ),
        "cache_state_after": (
            "missing"
            if final.empty
            else f"{final.iloc[0]['date']}..{final.iloc[-1]['date']} rows={len(final)}"
        ),
        "candidate_frame": candidate,
        "final_frame": final,
        "integrity_rows": integrity,
        "overlap_row": overlap,
        "reload_row": reload,
        "request_start": first_date,
        "request_end_exclusive": END_EXCLUSIVE,
        "staging_cache_path": rel(STAGING_DIR / f"{symbol}.csv"),
        "canonical_cache_path": rel(target),
        "metadata_path": rel(metadata),
        "next_action": "" if stage == "feasible" else NEXT_BLOCKED,
        "broker_account_position_order_endpoint_called": False,
    }


def trial_rows() -> list[dict[str, Any]]:
    sources = (
        ROOT / "evidence" / "research_recovery" / "rerun_fast_source_library_blocked_candidates_v3" / "latest" / "trial_ledger.csv",
        ROOT / "evidence" / "validation" / "angl_fallen_angel_diversifier_validation_v1" / "latest" / "trial_ledger.csv",
        ROOT / "evidence" / "correction" / "angl_80_20_portfolio_construction_methodology_correction_v1" / "latest" / "trial_ledger.csv",
    )
    carried: dict[str, dict[str, Any]] = {}
    for source in sources:
        for row in read_csv(source):
            if row.get("strategy_id") != STRATEGY_ID or not row.get("trial_id"):
                continue
            carried[row["trial_id"]] = {
                "trial_id": row["trial_id"],
                "parent_trial_id": row.get("parent_trial_id", ""),
                "strategy_id": STRATEGY_ID,
                "entity_type": "experiment_trial",
                "stage": row.get("stage", ""),
                "adaptation_label": row.get("adaptation_label", ""),
                "outcome": row.get("outcome", ""),
                "read_only": True,
                "source_path": rel(source),
                "new_trial_created": False,
            }
    return [carried[key] for key in sorted(carried)]


def sufficiency_rows(results: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    groups = [
        ("VM_observation_inputs", VM_SYMBOLS),
        ("DSR_observation_inputs", DSR_SYMBOLS),
        ("USCI_observation_inputs", USCI_SYMBOLS),
        ("frozen_current_active_vm_dsr_usci_combo", REFERENCE_SYMBOLS),
        ("ANGL_candidate_input", ("ANGL",)),
        ("HYG_control_input", ("HYG",)),
        ("JNK_control_input", ("JNK",)),
    ]
    rows: list[dict[str, Any]] = []
    for item_id, symbols in groups:
        missing = [symbol for symbol in symbols if results[symbol]["stage"] != "feasible"]
        frames = [results[symbol]["final_frame"] for symbol in symbols if not results[symbol]["final_frame"].empty]
        common_dates = (
            set(pd.to_datetime(frames[0]["date"]).dt.strftime("%Y-%m-%d"))
            if frames
            else set()
        )
        for frame in frames[1:]:
            common_dates &= set(pd.to_datetime(frame["date"]).dt.strftime("%Y-%m-%d"))
        warmup_rows = min((len(frame) for frame in frames), default=0)
        warmup_required = 200 if item_id in {"VM_observation_inputs", "DSR_observation_inputs", "frozen_current_active_vm_dsr_usci_combo"} else 1
        rows.append(
            {
                "reference_or_input_id": item_id,
                "required_symbols": symbols,
                "blocked_symbols": missing,
                "required_session": REQUIRED_DATE.date().isoformat(),
                "required_session_common": REQUIRED_DATE.date().isoformat() in common_dates and not missing,
                "common_start": min(common_dates) if common_dates else "",
                "common_end": max(common_dates) if common_dates else "",
                "common_session_count": len(common_dates),
                "minimum_history_rows": warmup_rows,
                "warmup_rows_required": warmup_required,
                "warmup_sufficient": warmup_rows >= warmup_required,
                "data_only_reproducibility": "feasible" if not missing and REQUIRED_DATE.date().isoformat() in common_dates and warmup_rows >= warmup_required else "blocked",
                "strategy_performance_calculated": False,
                "virtual_position_trade_or_nav_created": False,
            }
        )
    return rows


def run() -> dict[str, Any]:
    clean_paths()
    protected_before = hash_map(list(PROTECTED_STATE_PATHS) + list(OPERATIONAL_PATHS))
    prior_before = hash_map(list(PRIOR_EVIDENCE_PATHS))
    target_paths = [path for symbol in TARGET_SYMBOLS for path in (cache_path(symbol), metadata_path(symbol))]
    target_before = hash_map(target_paths)
    unrelated_cache_paths = [
        path
        for path in sorted((ROOT / "data" / "cache").glob("*"))
        if path.is_file() and path not in target_paths and not path.name.startswith(".")
    ]
    unrelated_before = hash_map(unrelated_cache_paths)

    results: dict[str, dict[str, Any]] = {}
    for symbol in TARGET_SYMBOLS:
        results[symbol] = remediate_symbol(symbol)

    STAGING_DIR.rmdir()
    protected_after = hash_map(list(PROTECTED_STATE_PATHS) + list(OPERATIONAL_PATHS))
    prior_after = hash_map(list(PRIOR_EVIDENCE_PATHS))
    target_after = hash_map(target_paths)
    unrelated_after = hash_map(unrelated_cache_paths)

    tasks: list[dict[str, Any]] = []
    refresh_rows: list[dict[str, Any]] = []
    source_rows: list[dict[str, Any]] = []
    coverage_rows: list[dict[str, Any]] = []
    integrity: list[dict[str, Any]] = []
    overlap_rows: list[dict[str, Any]] = []
    reload_rows: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for symbol in TARGET_SYMBOLS:
        result = results[symbol]
        frame = result["final_frame"]
        tasks.append(
            {
                "task_id": f"{TASK_ID}__{symbol}",
                "symbol": symbol,
                "entity_type": "data_capability_task",
                "stage": result["stage"],
                "adaptation_label": ADAPTATION_LABEL,
                "cache_state_before": result["cache_state_before"],
                "provider_attempted": PROVIDER_ID,
                "acquisition_result": result["acquisition_result"],
                "validation_result": result["validation_result"],
                "cache_state_after": result["cache_state_after"],
                "failure_reason": result["failure_reason"],
                "next_action": result["next_action"],
                "counted_as_strategy_trial_or_observation": False,
            }
        )
        refresh_rows.append(
            {
                key: result[key]
                for key in [
                    "symbol",
                    "stage",
                    "attempt_count",
                    "provider_attempted",
                    "provider_status",
                    "request_start",
                    "request_end_exclusive",
                    "acquisition_result",
                    "validation_result",
                    "failure_reason",
                    "failure_detail",
                    "alpaca_attempted",
                    "cache_replaced",
                    "cache_before_hash",
                    "cache_after_hash",
                    "metadata_before_hash",
                    "metadata_after_hash",
                    "staging_cache_path",
                    "canonical_cache_path",
                    "metadata_path",
                    "broker_account_position_order_endpoint_called",
                ]
            }
        )
        source_rows.append(
            {
                "symbol": symbol,
                "provider_identifier": PROVIDER_ID,
                "provider_path": "src.data._download_yfinance",
                "canonical_builder": "src.data.build_adjusted_ohlc",
                "normal_reload_interface": "src.data.load_symbol_data",
                "acquisition_timestamp": ACQUISITION_TIMESTAMP,
                "request_start": result["request_start"],
                "request_end_exclusive": result["request_end_exclusive"],
                "adjustment_convention": "raw_adj_close/raw_close factor applied to raw OHLC; volume unadjusted",
                "cache_path": result["canonical_cache_path"],
                "metadata_path": result["metadata_path"],
                "cache_hash": result["cache_after_hash"],
                "metadata_hash": result["metadata_after_hash"],
                "admitted": result["stage"] == "feasible",
                "alpaca_attempted": False,
                "provider_attempt_count": 1,
            }
        )
        coverage_rows.append(
            {
                "symbol": symbol,
                "status": result["stage"],
                "first_date": "" if frame.empty else str(frame.iloc[0]["date"]),
                "last_date": "" if frame.empty else str(frame.iloc[-1]["date"]),
                "row_count": len(frame),
                "required_date": REQUIRED_DATE.date().isoformat(),
                "required_date_present": (
                    not frame.empty and (pd.to_datetime(frame["date"]) == REQUIRED_DATE).any()
                ),
                "canonical_schema": list(frame.columns) == list(NORMALIZED_COLUMNS) if not frame.empty else False,
                "cache_hash": result["cache_after_hash"],
            }
        )
        integrity.extend(result["integrity_rows"])
        overlap_rows.append(result["overlap_row"])
        reload_rows.append(result["reload_row"])
        if result["failure_reason"]:
            failures.append(
                {
                    "symbol": symbol,
                    "primary_failure_reason": result["failure_reason"],
                    "failure_detail": result["failure_detail"],
                    "prior_cache_preserved": result["cache_before_hash"] == result["cache_after_hash"],
                    "next_action": NEXT_BLOCKED,
                }
            )

    sufficiency = sufficiency_rows(results)
    feasible = [symbol for symbol in TARGET_SYMBOLS if results[symbol]["stage"] == "feasible"]
    blocked = [symbol for symbol in TARGET_SYMBOLS if results[symbol]["stage"] == "blocked"]
    all_ready = len(feasible) == len(TARGET_SYMBOLS) and all(
        row["data_only_reproducibility"] == "feasible" for row in sufficiency
    )
    outcome = OUTCOME_READY if all_ready else OUTCOME_BLOCKED
    observation_next = NEXT_READY if all_ready else NEXT_BLOCKED

    state_rows: list[dict[str, Any]] = []
    for path_text, before in protected_before.items():
        state_rows.append(
            {
                "path": path_text,
                "path_type": "protected_state_or_operational_observation",
                "hash_before": before,
                "hash_after": protected_after[path_text],
                "changed": before != protected_after[path_text],
                "change_permitted": False,
                "change_description": "must remain byte-identical",
            }
        )
    for path_text, before in target_before.items():
        symbol = Path(path_text).name.split(".")[0]
        permitted = symbol in feasible
        state_rows.append(
            {
                "path": path_text,
                "path_type": "authorized_target_cache_or_metadata",
                "hash_before": before,
                "hash_after": target_after[path_text],
                "changed": before != target_after[path_text],
                "change_permitted": permitted or before == target_after[path_text],
                "change_description": "validated per-symbol atomic replacement" if permitted else "prior file preserved",
            }
        )
    unexpected = [row["path"] for row in state_rows if row["changed"] and not row["change_permitted"]]

    prior_root_rows = [
        {
            "root_cause_id": "prior_batch_all_or_nothing_failure",
            "source_path": rel(PRIOR_INITIALIZATION_DIR / "market_data_refresh_manifest.csv"),
            "prior_provider": "yfinance_existing_repo_supported_fallback",
            "prior_call_shape": "one_20_symbol_batch",
            "prior_result": "provider_call_failed_before_any_canonical_symbol_frame_admitted",
            "root_cause_classification": "batch_level_exception_boundary_obscured_per_symbol_failure",
            "remediation": "one existing-provider request and isolated staged transaction per symbol",
            "alpaca_retried": False,
            "provider_architecture_changed": False,
        }
    ]
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
        "activated_in_this_task": False,
        "forward_record_created": False,
    }
    process_row = {
        "task_id": TASK_ID,
        "entity_type": "process_task",
        "stage": "feasibility",
        "data_capability_tasks": 20,
        "strategy_configurations_created": 0,
        "experiment_trials_created": 0,
        "observations_created": 0,
        "observations_activated": 0,
    }
    common_row = {
        "required_session": REQUIRED_DATE.date().isoformat(),
        "authorized_symbol_count": len(TARGET_SYMBOLS),
        "symbols_feasible_through_required_session": len(feasible),
        "symbols_blocked": len(blocked),
        "blocked_symbols": blocked,
        "all_required_symbols_same_session_ready": all_ready,
        "frozen_reference_inputs_ready": next(
            row["data_only_reproducibility"]
            for row in sufficiency
            if row["reference_or_input_id"] == "frozen_current_active_vm_dsr_usci_combo"
        )
        == "feasible",
        "strategy_performance_calculated": False,
        "virtual_position_trade_or_nav_created": False,
    }
    outcome_row = {
        "task_id": TASK_ID,
        "data_outcome": outcome,
        "symbols_attempted": len(TARGET_SYMBOLS),
        "symbols_feasible": len(feasible),
        "symbols_blocked": len(blocked),
        "cache_symbols_updated": sum(results[symbol]["cache_replaced"] for symbol in TARGET_SYMBOLS),
        "strategy_configurations_created": 0,
        "experiment_trials_created": 0,
        "observations_created": 0,
        "observations_activated": 0,
        "data_capability_tasks": 20,
        "process_tasks": 1,
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
    consistency = {
        "consistency_passed": bool(
            len(tasks) == 20
            and all(result["attempt_count"] == 1 for result in results.values())
            and all(result["failure_reason"] in ALLOWED_FAILURES for result in results.values())
            and protected_before == protected_after
            and prior_before == prior_after
            and unrelated_before == unrelated_after
            and not unexpected
            and all(
                result["stage"] == "blocked"
                or (
                    all(row["status"] == "pass" for row in result["integrity_rows"])
                    and result["overlap_row"]["acceptable"]
                    and result["reload_row"]["reload_pass"]
                )
                for result in results.values()
            )
        ),
        "exact_authorized_symbols": list(TARGET_SYMBOLS),
        "exactly_20_symbols_processed": len(tasks) == 20,
        "one_attempt_per_symbol": all(result["attempt_count"] == 1 for result in results.values()),
        "provider_paths_used": [PROVIDER_ID],
        "exactly_one_existing_provider_path_used": True,
        "alpaca_retried": False,
        "independent_symbol_processing": True,
        "failed_symbol_did_not_cancel_later_symbols": len(tasks) == 20,
        "validated_cache_replacement_only": not unexpected,
        "blocked_symbol_prior_cache_preserved": all(
            result["stage"] != "blocked" or result["cache_before_hash"] == result["cache_after_hash"]
            for result in results.values()
        ),
        "normal_interface_reload_pass_for_feasible": all(
            result["stage"] != "feasible" or result["reload_row"]["reload_pass"]
            for result in results.values()
        ),
        "protected_state_hashes_unchanged": protected_before == protected_after,
        "prior_evidence_hashes_unchanged": prior_before == prior_after,
        "unrelated_cache_hashes_unchanged": unrelated_before == unrelated_after,
        "unexpected_changes": unexpected,
        "strategy_configurations_created": 0,
        "experiment_trials_created": 0,
        "observations_created": 0,
        "observations_activated": 0,
        "forward_records_created": 0,
        "virtual_positions_trades_or_nav_created": False,
        "strategy_performance_calculated": False,
        "broker_account_position_order_endpoint_called": False,
        "paper_or_live_order_submitted": False,
        "real_money_action": False,
        "data_outcome": outcome,
        "observation_next_action": observation_next,
        "project_discovery_next_action": PROJECT_NEXT_ACTION,
    }

    write_yaml(
        OUTPUT_DIR / "remediation_manifest.yaml",
        {
            "task_id": TASK_ID,
            "mode": "data-capability",
            "stage": "feasibility",
            "adaptation_label": ADAPTATION_LABEL,
            "strategy_id": STRATEGY_ID,
            "observation_id": OBSERVATION_ID,
            "required_session": REQUIRED_DATE.date().isoformat(),
            "authorized_symbols": list(TARGET_SYMBOLS),
            "provider_path": PROVIDER_ID,
            "provider_attempts": 20,
            "alpaca_attempts": 0,
            "data_outcome": outcome,
            "strategy_configurations_created": 0,
            "experiment_trials_created": 0,
            "observations_created": 0,
            "observations_activated": 0,
            "data_capability_tasks": 20,
            "process_tasks": 1,
            "cache_symbols_updated": outcome_row["cache_symbols_updated"],
            "symbols_feasible_through_2026_07_24": len(feasible),
            "observation_next_action": observation_next,
            "project_discovery_next_action": PROJECT_NEXT_ACTION,
        },
    )
    write_csv(OUTPUT_DIR / "strategy_cards.csv", [strategy_row], list(strategy_row))
    trials = trial_rows()
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
    write_csv(OUTPUT_DIR / "paper_demo_observations.csv", [observation_row], list(observation_row))
    write_csv(OUTPUT_DIR / "data_capability_task_log.csv", tasks, list(tasks[0]))
    write_csv(OUTPUT_DIR / "process_task_log.csv", [process_row], list(process_row))
    write_csv(OUTPUT_DIR / "provider_failure_root_cause.csv", prior_root_rows, list(prior_root_rows[0]))
    write_csv(OUTPUT_DIR / "per_symbol_refresh_results.csv", refresh_rows, list(refresh_rows[0]))
    write_csv(OUTPUT_DIR / "data_source_manifest.csv", source_rows, list(source_rows[0]))
    write_csv(OUTPUT_DIR / "data_coverage.csv", coverage_rows, list(coverage_rows[0]))
    write_csv(
        OUTPUT_DIR / "data_integrity_checks.csv",
        integrity,
        ["symbol", "check_name", "status", "violation_count", "details"],
    )
    write_csv(OUTPUT_DIR / "overlap_history_reconciliation.csv", overlap_rows, list(overlap_rows[0]))
    write_csv(OUTPUT_DIR / "cache_reload_reconciliation.csv", reload_rows, list(reload_rows[0]))
    write_csv(OUTPUT_DIR / "reference_input_sufficiency.csv", sufficiency, list(sufficiency[0]))
    write_csv(OUTPUT_DIR / "common_session_sufficiency.csv", [common_row], list(common_row))
    write_csv(OUTPUT_DIR / "state_change_manifest.csv", state_rows, list(state_rows[0]))
    write_csv(OUTPUT_DIR / "outcome_summary.csv", [outcome_row], list(outcome_row))
    write_csv(
        OUTPUT_DIR / "failure_reasons.csv",
        failures,
        ["symbol", "primary_failure_reason", "failure_detail", "prior_cache_preserved", "next_action"],
    )
    write_csv(OUTPUT_DIR / "next_actions.csv", next_rows, list(next_rows[0]))
    write_json(OUTPUT_DIR / "consistency_check.json", consistency)
    write_text(
        OUTPUT_DIR / "remediation_report.md",
        f"""# ANGL Observation Market-Data Remediation v1

Exactly 20 authorized symbols were processed sequentially with one attempt each through the existing `{PROVIDER_ID}` path. Alpaca was not retried, no provider architecture changed, and no lifecycle or observation state was modified.

## Outcome

- Data outcome: `{outcome}`
- Symbols feasible through July 24, 2026: `{len(feasible)} / 20`
- Symbols blocked: `{'|'.join(blocked)}`
- Canonical cache symbols updated: `{outcome_row['cache_symbols_updated']}`
- Frozen reference input sufficiency: `{'feasible' if common_row['frozen_reference_inputs_ready'] else 'blocked'}`
- Observation remains blocked and uninitialized: `true`
- Strategy/trials/observations created: `0 / 0 / 0`
- Observation activations: `0`
- Broker/account/position/order calls: `0`

The task calculated no strategy performance, virtual positions, virtual trades, or forward NAV.

## Next Actions

- ANGL observation: `{observation_next}` (not executed)
- Separate project discovery: `{PROJECT_NEXT_ACTION}` (not executed)
""",
    )
    return {
        "task_id": TASK_ID,
        "output_dir": rel(OUTPUT_DIR),
        "data_outcome": outcome,
        "symbols_attempted": len(TARGET_SYMBOLS),
        "symbols_feasible": len(feasible),
        "symbols_blocked": blocked,
        "cache_symbols_updated": outcome_row["cache_symbols_updated"],
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
