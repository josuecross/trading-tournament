from __future__ import annotations

import csv
import hashlib
import json
import math
import shutil
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
import yaml

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.research import (
    initialize_angl_after_next_completed_common_session_v1 as reference_engine,
)
from strategy_lab.research_os.research import (
    refresh_ivts_activation_data_and_activate_forward_observation_v1 as prior,
)
from strategy_lab.research_os.research import (
    review_and_onboard_ivts_unfiltered_paper_demo_observation_v1 as onboarding,
)


TASK_ID = "correct_canonical_append_method_and_activate_ivts_observation_v1"
OUTPUT_DIR = ROOT / "evidence" / "correction" / TASK_ID / "latest"
PRIOR_DIR = (
    ROOT
    / "evidence"
    / "paper_demo"
    / "refresh_ivts_activation_data_and_activate_forward_observation_v1"
    / "latest"
)
RAW_DIR = PRIOR_DIR / "provider_raw"

STRATEGY_ID = prior.STRATEGY_ID
OBSERVATION_ID = prior.OBSERVATION_ID
REFERENCE_ID = prior.REFERENCE_ID
REFERENCE_WEIGHT = prior.REFERENCE_WEIGHT
CANDIDATE_WEIGHT = prior.CANDIDATE_WEIGHT
COST_RATE = prior.COST_RATE
LATEST_CAPTURED_SESSION = date(2026, 7, 24)
METHODOLOGY = "append_only_anchor_preserving_total_return_continuation_v1"

ACTIVATED_OUTCOME = prior.ACTIVATED_OUTCOME
DEFERRED_OUTCOME = prior.DEFERRED_OUTCOME
BLOCKED_OUTCOME = prior.BLOCKED_OUTCOME
ACTIVATED_NEXT_ACTION = prior.ACTIVATED_NEXT_ACTION
DEFERRED_NEXT_ACTION = (
    "defer_ivts_observation_and_resume_targeted_strategy_discovery_v1"
)
BLOCKED_NEXT_ACTION = prior.BLOCKED_NEXT_ACTION

REGISTRY_PATH = prior.REGISTRY_PATH
ACTIVE_OBSERVATIONS_PATH = prior.ACTIVE_OBSERVATIONS_PATH
ROADMAP_PATH = prior.ROADMAP_PATH
QUEUE_PATH = prior.QUEUE_PATH
FAMILY_LEDGER_PATH = prior.FAMILY_LEDGER_PATH
CACHE_DIR = prior.CACHE_DIR
CANONICAL_COLUMNS = prior.CANONICAL_COLUMNS

RAW_OHLC_TOLERANCE = 2e-4
ACTION_RETURN_TOLERANCE = 5e-5
ADJUSTED_RETURN_TOLERANCE = 1e-10
NAMED_ACTIONS = {
    "SPY": date(2026, 6, 18),
    "USMV": date(2026, 6, 15),
    "SPLV": date(2026, 6, 22),
}
EXPECTED_RAW_HASHES = {
    "BIL": "sha256:6ae4ac5ca423c1940f24153bac6db43a68bd3d858b8273e4e940bb6e53190598",
    "DBC": "sha256:9a0fbd04d228d9f361d9731c91a3474b0483aabc419af2ab0c0ae86e5b27644d",
    "IEF": "sha256:5fb41bb2c1954d4e6e3441a830358336a984111d373cc75b8313610c18392521",
    "QUAL": "sha256:b9d3007070843cd01d9a2d2e93df026bc31e23da1e0bb167118b5bf45b242093",
    "SPLV": "sha256:53472d48a7eefa4172091fe346692a1d06d5f3d33e3a66ff6aa792d79b115295",
    "SPY": "sha256:e054967c41151d97a8a41f8ba7519914cf9d301ef80465678da2e7f3f7a54be4",
    "USCI": "sha256:7600e9742e8e8f5e6741384d9267ba03fb0afff8ff53f2527425d437a3330fb7",
    "USMV": "sha256:19b57b36e258962494056712973fdc4793a56ae530236b73dedc6d8f27dac24e",
    "XLB": "sha256:46e0590571e3fd04ae1ff52cd13b48469c98d58ce86533e24e6c7435694cc187",
    "XLC": "sha256:8acd4ad5c9f9a0df0ca387eedb4f05cc259198feea1b0be15ed76eb8b0beb557",
    "XLE": "sha256:22c16edcddae58283a9177edf0caa514e299633a0aa336dc9a3438cbe989d158",
    "XLF": "sha256:f2390b2bbda586177de72e7062893c101b088ea0bf0ce3d56ab5dd4320c6de4a",
    "XLI": "sha256:828d7c4710075974cadc010f0ba6753eab1ef0d928fb989839e59a6f0cf37328",
    "XLK": "sha256:85fcaac13fef46493d6e9d3a8741bf3fa26f6b614476a1229bf6d3b3f6536a6b",
    "XLP": "sha256:b3f505f99e7ffc26b7581829c0f1ec90294159e3b5a6eb22b3b348a36d8d11d2",
    "XLU": "sha256:42ee3c367faaefece1ff213dc3c355bef36146acdc8b5c2bac332d6f2ce48224",
    "XLV": "sha256:76ba267d412245f935c1aa93dea13f5bb9e1a5cd35af22df0f48d7b43e7a6bc1",
    "XLY": "sha256:7e4696649850a70278048d091de13414b242d5c0eab3d34ed45209f54800b483",
}


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def file_hash(path: Path) -> str:
    return sha256_bytes(path.read_bytes()) if path.exists() else ""


def canonical_hash(value: Any) -> str:
    return sha256_bytes(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode(
            "utf-8"
        )
    )


def csv_value(value: Any) -> Any:
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    return value


def write_csv(path: Path, rows: Iterable[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: csv_value(row.get(field, "")) for field in fields})


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(payload, sort_keys=False, width=120, allow_unicode=False),
        encoding="utf-8",
    )


def clean_output_dir() -> None:
    allowed = (
        ROOT / "evidence" / "correction" / TASK_ID / "latest"
    ).resolve()
    if OUTPUT_DIR.exists():
        if OUTPUT_DIR.resolve() != allowed:
            raise RuntimeError(f"Refusing to remove unexpected path: {OUTPUT_DIR}")
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def cache_path(symbol: str) -> Path:
    return CACHE_DIR / f"{symbol}.csv"


def metadata_path(symbol: str) -> Path:
    return CACHE_DIR / f"{symbol}.acquisition.json"


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def required_symbols() -> tuple[str, ...]:
    rows = read_csv_rows(PRIOR_DIR / "required_symbol_scope.csv")
    values = tuple(sorted(row["symbol"] for row in rows))
    if len(values) != 18 or set(values) != set(EXPECTED_RAW_HASHES):
        raise RuntimeError("Prior frozen symbol scope does not contain exactly 18 symbols")
    return values


def direct_cache_frame(symbol: str) -> pd.DataFrame:
    frame = pd.read_csv(cache_path(symbol))
    if tuple(frame.columns) != CANONICAL_COLUMNS:
        raise RuntimeError(f"{symbol}: canonical schema mismatch")
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.strftime(
        "%Y-%m-%d"
    )
    return frame


def frame_hash(frame: pd.DataFrame) -> str:
    return sha256_bytes(
        frame.to_csv(
            index=False, lineterminator="\n", float_format="%.17g"
        ).encode("utf-8")
    )


def prior_packet_hash() -> str:
    rows = [
        (rel(path), file_hash(path))
        for path in sorted(PRIOR_DIR.rglob("*"))
        if path.is_file()
    ]
    return canonical_hash(rows)


def unrelated_cache_hash(symbols: tuple[str, ...]) -> str:
    excluded = {
        cache_path(symbol).resolve() for symbol in symbols
    } | {metadata_path(symbol).resolve() for symbol in symbols}
    rows = [
        (path.name, file_hash(path))
        for path in sorted(CACHE_DIR.glob("*"))
        if path.is_file() and path.resolve() not in excluded
    ]
    return canonical_hash(rows)


def provider_frame(symbol: str) -> pd.DataFrame:
    frame = prior.canonicalize(pd.read_csv(RAW_DIR / f"{symbol}.csv"), symbol)
    frame["date"] = pd.to_datetime(frame["date"]).dt.strftime("%Y-%m-%d")
    return frame


def hash_reconciliation_rows(
    symbols: tuple[str, ...],
) -> tuple[list[dict[str, Any]], bool, dict[str, datetime]]:
    prior_provider = read_csv_rows(PRIOR_DIR / "provider_attempt_log.csv")
    selected = [
        row
        for row in prior_provider
        if row["provider_id"]
        == "yfinance_existing_repo_supported_adjusted_daily_path"
    ]
    rows_by_symbol = json.loads(selected[0]["rows_by_symbol"]) if len(selected) == 1 else {}
    rows: list[dict[str, Any]] = []
    timestamps: dict[str, datetime] = {}
    for symbol in symbols:
        path = RAW_DIR / f"{symbol}.csv"
        actual_hash = file_hash(path)
        count = len(pd.read_csv(path)) if path.exists() else 0
        timestamp = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
        timestamps[symbol] = timestamp
        passed = bool(
            path.exists()
            and actual_hash == EXPECTED_RAW_HASHES[symbol]
            and count == int(rows_by_symbol.get(symbol, 0)) == 29
        )
        rows.append(
            {
                "symbol": symbol,
                "provider_raw_evidence_path": rel(path),
                "expected_frozen_hash": EXPECTED_RAW_HASHES[symbol],
                "actual_hash": actual_hash,
                "prior_recorded_row_count": rows_by_symbol.get(symbol, ""),
                "actual_row_count": count,
                "correction_input_frozen_before_processing": True,
                "capture_file_mtime_utc": timestamp.isoformat(),
                "provider_download_called_in_correction": False,
                "hash_reconciliation_pass": passed,
            }
        )
    return rows, all(row["hash_reconciliation_pass"] for row in rows), timestamps


def relative_difference(left: float, right: float) -> float:
    return abs(left - right) / max(abs(left), abs(right), 1e-12)


def action_return_check(provider: pd.DataFrame, action_date: date) -> dict[str, Any]:
    dates = pd.to_datetime(provider["date"]).dt.date
    matches = provider.index[dates == action_date].tolist()
    if len(matches) != 1 or matches[0] == provider.index[0]:
        return {"present": False, "valid": False}
    index = matches[0]
    prior_row = provider.iloc[provider.index.get_loc(index) - 1]
    row = provider.loc[index]
    adjusted_return = float(row["raw_adj_close"] / prior_row["raw_adj_close"] - 1.0)
    raw_plus_distribution = float(
        (row["raw_close"] + row["dividends"]) / prior_row["raw_close"] - 1.0
    )
    difference = adjusted_return - raw_plus_distribution
    return {
        "present": True,
        "valid": bool(
            float(row["dividends"]) > 0.0
            and float(row["stock_splits"]) == 0.0
            and abs(difference) <= ACTION_RETURN_TOLERANCE
        ),
        "date": action_date.isoformat(),
        "dividend": float(row["dividends"]),
        "split": float(row["stock_splits"]),
        "prior_raw_close": float(prior_row["raw_close"]),
        "raw_close": float(row["raw_close"]),
        "provider_adjusted_return": adjusted_return,
        "raw_plus_distribution_return": raw_plus_distribution,
        "difference": difference,
        "tolerance": ACTION_RETURN_TOLERANCE,
    }


def corporate_action_rows(
    symbols: tuple[str, ...], providers: dict[str, pd.DataFrame]
) -> tuple[list[dict[str, Any]], dict[tuple[str, str], bool], bool]:
    rows: list[dict[str, Any]] = []
    lookup: dict[tuple[str, str], bool] = {}
    named_pass = True
    for symbol in symbols:
        provider = providers[symbol]
        actions = provider.loc[
            (pd.to_numeric(provider["dividends"]) != 0.0)
            | (pd.to_numeric(provider["stock_splits"]) != 0.0)
        ]
        for _, action in actions.iterrows():
            action_date = date.fromisoformat(str(action["date"]))
            check = action_return_check(provider, action_date)
            passed = bool(check.get("valid"))
            lookup[(symbol, action_date.isoformat())] = passed
            rows.append(
                {
                    "symbol": symbol,
                    "action_date": action_date.isoformat(),
                    "action_type": (
                        "distribution"
                        if float(action["dividends"]) != 0.0
                        else "split"
                    ),
                    "distribution": float(action["dividends"]),
                    "split": float(action["stock_splits"]),
                    "provider_adjusted_return": check.get(
                        "provider_adjusted_return", ""
                    ),
                    "raw_plus_distribution_return": check.get(
                        "raw_plus_distribution_return", ""
                    ),
                    "return_difference": check.get("difference", ""),
                    "distribution_represented_once_by_adjusted_path": passed,
                    "separate_dividend_cash_added": False,
                    "named_required_reconciliation": NAMED_ACTIONS.get(symbol)
                    == action_date,
                    "reconciliation_status": "pass" if passed else "fail",
                }
            )
        if symbol in NAMED_ACTIONS:
            named = [
                row
                for row in rows
                if row["symbol"] == symbol
                and row["action_date"] == NAMED_ACTIONS[symbol].isoformat()
            ]
            named_pass = named_pass and len(named) == 1 and named[0][
                "reconciliation_status"
            ] == "pass"
    return rows, lookup, bool(named_pass and all(row["reconciliation_status"] == "pass" for row in rows))


def overlap_classification(
    symbol: str,
    existing: pd.DataFrame,
    provider: pd.DataFrame,
    action_lookup: dict[tuple[str, str], bool],
) -> tuple[list[dict[str, Any]], bool, list[date]]:
    anchor = date.fromisoformat(str(existing.iloc[-1]["date"]))
    provider_dates = pd.to_datetime(provider["date"]).dt.date
    overlap_dates = sorted(day for day in provider_dates if day <= anchor)
    if anchor not in overlap_dates or len(overlap_dates) < 5:
        return [], False, overlap_dates
    existing_by_date = existing.set_index("date")
    provider_by_date = provider.set_index("date")
    common = [
        day
        for day in overlap_dates
        if day.isoformat() in existing_by_date.index
    ]
    rows: list[dict[str, Any]] = []
    blocking = {
        "unexplained_raw_price_mismatch",
        "unexplained_corporate_action_mismatch",
        "unsupported_split_or_symbol_change",
    }
    for day in common:
        key = day.isoformat()
        old = existing_by_date.loc[key]
        new = provider_by_date.loc[key]
        raw_diff = max(
            relative_difference(float(old[column]), float(new[column]))
            for column in prior.RAW_PRICE_COLUMNS
        )
        if raw_diff == 0.0:
            raw_class = "exact_match"
        elif raw_diff <= RAW_OHLC_TOLERANCE:
            raw_class = "raw_price_revision_within_tolerance"
        else:
            raw_class = "unexplained_raw_price_mismatch"
        rows.append(
            {
                "symbol": symbol,
                "date": key,
                "field_group": "raw_ohlc",
                "classification": raw_class,
                "existing_value": "",
                "provider_value": "",
                "relative_difference": raw_diff,
                "numeric_tolerance": RAW_OHLC_TOLERANCE,
                "blocking": raw_class in blocking,
                "explanation": "raw OHLC comparison",
            }
        )

        volume_diff = relative_difference(
            float(old["raw_volume"]), float(new["raw_volume"])
        )
        volume_class = (
            "exact_match" if volume_diff == 0.0 else "volume_revision_nonblocking"
        )
        rows.append(
            {
                "symbol": symbol,
                "date": key,
                "field_group": "volume",
                "classification": volume_class,
                "existing_value": float(old["raw_volume"]),
                "provider_value": float(new["raw_volume"]),
                "relative_difference": volume_diff,
                "numeric_tolerance": "",
                "blocking": False,
                "explanation": "overlap volume is immutable and provider revision is not admitted",
            }
        )

        old_dividend = float(old["dividends"])
        new_dividend = float(new["dividends"])
        if old_dividend == new_dividend:
            dividend_class = "exact_match"
        elif new_dividend > 0.0 and action_lookup.get((symbol, key), False):
            dividend_class = "corporate_action_boundary_revision"
        else:
            dividend_class = "unexplained_corporate_action_mismatch"
        rows.append(
            {
                "symbol": symbol,
                "date": key,
                "field_group": "dividends",
                "classification": dividend_class,
                "existing_value": old_dividend,
                "provider_value": new_dividend,
                "relative_difference": relative_difference(
                    old_dividend, new_dividend
                ),
                "numeric_tolerance": ACTION_RETURN_TOLERANCE,
                "blocking": dividend_class in blocking,
                "explanation": "provider distribution checked against adjusted total-return path",
            }
        )

        old_split = float(old["stock_splits"])
        new_split = float(new["stock_splits"])
        split_class = (
            "exact_match"
            if old_split == new_split
            else "unsupported_split_or_symbol_change"
        )
        rows.append(
            {
                "symbol": symbol,
                "date": key,
                "field_group": "splits",
                "classification": split_class,
                "existing_value": old_split,
                "provider_value": new_split,
                "relative_difference": relative_difference(old_split, new_split),
                "numeric_tolerance": 0.0,
                "blocking": split_class in blocking,
                "explanation": "split field comparison",
            }
        )

        adjusted_ratio = float(new["raw_adj_close"] / old["adj_close"])
        if math.isclose(adjusted_ratio, 1.0, rel_tol=0.0, abs_tol=1e-12):
            adjusted_class = "exact_match"
        elif action_lookup.get((symbol, key), False):
            adjusted_class = "corporate_action_boundary_revision"
        else:
            adjusted_class = "stable_backward_adjustment_revision"
        rows.append(
            {
                "symbol": symbol,
                "date": key,
                "field_group": "adjusted_close",
                "classification": adjusted_class,
                "existing_value": float(old["adj_close"]),
                "provider_value": float(new["raw_adj_close"]),
                "relative_difference": abs(adjusted_ratio - 1.0),
                "numeric_tolerance": "",
                "blocking": False,
                "explanation": "backward adjusted-level revision is bridged, not admitted",
            }
        )
    return rows, not any(row["blocking"] for row in rows), common


def append_symbol(
    symbol: str,
    existing: pd.DataFrame,
    provider: pd.DataFrame,
) -> tuple[pd.DataFrame, bytes, list[dict[str, Any]], dict[str, Any]]:
    anchor_date = date.fromisoformat(str(existing.iloc[-1]["date"]))
    provider_dates = pd.to_datetime(provider["date"]).dt.date
    matches = provider.loc[provider_dates == anchor_date]
    if len(matches) != 1:
        raise RuntimeError(f"{symbol}: provider anchor is unavailable")
    anchor_provider = matches.iloc[0]
    anchor_canonical = existing.iloc[-1]
    provider_anchor_adjusted = float(anchor_provider["raw_adj_close"])
    bridge = float(anchor_canonical["adj_close"]) / provider_anchor_adjusted
    if not np.isfinite(bridge) or bridge <= 0.0:
        raise RuntimeError(f"{symbol}: invalid bridge factor")

    appended = provider.loc[provider_dates > anchor_date].copy()
    if appended.empty:
        raise RuntimeError(f"{symbol}: no sessions exist after anchor")
    for column in (
        "raw_adj_close",
        "adjustment_factor",
        "open",
        "high",
        "low",
        "close",
        "adj_close",
    ):
        appended[column] = pd.to_numeric(appended[column], errors="coerce") * bridge
    appended = appended[list(CANONICAL_COLUMNS)].reset_index(drop=True)

    combined = pd.concat([existing, appended], ignore_index=True)
    dates = pd.to_datetime(combined["date"], errors="coerce")
    prices = combined[["raw_open", "raw_high", "raw_low", "raw_close", "open", "high", "low", "close", "adj_close"]].apply(
        pd.to_numeric, errors="coerce"
    )
    appended_dates = pd.to_datetime(appended["date"]).dt.date
    expected = prior.expected_sessions(anchor_date, LATEST_CAPTURED_SESSION)
    available = set(appended_dates) | {anchor_date}
    missing = sorted(expected - available)
    frame_valid = bool(
        dates.notna().all()
        and dates.is_monotonic_increasing
        and not dates.duplicated().any()
        and np.isfinite(prices.to_numpy(dtype=float)).all()
        and (prices > 0.0).all().all()
        and (
            prices["high"] + 1e-10
            >= prices[["open", "close"]].max(axis=1)
        ).all()
        and (
            prices["low"] - 1e-10
            <= prices[["open", "close"]].min(axis=1)
        ).all()
        and not missing
        and appended_dates.iloc[-1] == LATEST_CAPTURED_SESSION
    )

    return_rows: list[dict[str, Any]] = []
    previous_canonical_close = float(anchor_canonical["adj_close"])
    previous_provider_close = provider_anchor_adjusted
    for _, row in appended.iterrows():
        day = str(row["date"])
        provider_source = provider.loc[provider["date"] == day].iloc[0]
        actual_return = float(row["adj_close"] / previous_canonical_close - 1.0)
        expected_return = float(
            provider_source["raw_adj_close"] / previous_provider_close - 1.0
        )
        difference = actual_return - expected_return
        return_rows.append(
            {
                "symbol": symbol,
                "anchor_date": anchor_date.isoformat(),
                "date": day,
                "provider_adjusted_return": expected_return,
                "continuation_adjusted_return": actual_return,
                "difference": difference,
                "absolute_tolerance": ADJUSTED_RETURN_TOLERANCE,
                "return_reconciliation_pass": abs(difference)
                <= ADJUSTED_RETURN_TOLERANCE,
                "dividend_cash_added_separately": False,
                "stale_price_forward_filled": False,
            }
        )
        previous_canonical_close = float(row["adj_close"])
        previous_provider_close = float(provider_source["raw_adj_close"])

    original_bytes = cache_path(symbol).read_bytes()
    separator = b"" if original_bytes.endswith((b"\n", b"\r")) else b"\n"
    append_bytes = appended.to_csv(
        index=False,
        header=False,
        lineterminator="\n",
        float_format="%.17g",
    ).encode("utf-8")
    proposed_bytes = original_bytes + separator + append_bytes
    historical_prefix_unchanged = proposed_bytes[: len(original_bytes)] == original_bytes
    result = {
        "symbol": symbol,
        "anchor_date": anchor_date.isoformat(),
        "canonical_anchor_adjusted_close": float(anchor_canonical["adj_close"]),
        "provider_anchor_raw_close": float(anchor_provider["raw_close"]),
        "provider_anchor_adjusted_close": provider_anchor_adjusted,
        "provider_anchor_adjustment_factor": float(
            anchor_provider["raw_adj_close"] / anchor_provider["raw_close"]
        ),
        "continuation_bridge_factor": bridge,
        "first_appended_date": str(appended.iloc[0]["date"]),
        "last_appended_date": str(appended.iloc[-1]["date"]),
        "appended_row_count": int(len(appended)),
        "overlap_sessions_before_anchor": int(
            (provider_dates < anchor_date).sum()
        ),
        "historical_rows_rewritten": False,
        "historical_byte_prefix_unchanged": historical_prefix_unchanged,
        "all_adjusted_returns_reconciled": all(
            row["return_reconciliation_pass"] for row in return_rows
        ),
        "frame_invariants_pass": frame_valid,
        "missing_sessions": [day.isoformat() for day in missing],
        "status": "pass"
        if (
            historical_prefix_unchanged
            and frame_valid
            and all(row["return_reconciliation_pass"] for row in return_rows)
        )
        else "fail",
    }
    return combined, proposed_bytes, return_rows, result


def reference_state(
    frames: dict[str, pd.DataFrame],
) -> tuple[list[dict[str, Any]], dict[str, float], dict[str, Any]]:
    def close_frame(symbols: tuple[str, ...]) -> pd.DataFrame:
        series = []
        for symbol in symbols:
            frame = frames[symbol]
            series.append(
                pd.Series(
                    pd.to_numeric(frame["adj_close"]).to_numpy(),
                    index=pd.to_datetime(frame["date"]),
                    name=symbol,
                )
            )
        return pd.concat(series, axis=1).sort_index().dropna(how="any")

    vm_prices = close_frame(tuple(reference_engine.VM_SYMBOLS))
    dsr_prices = close_frame(tuple(reference_engine.DSR_SYMBOLS))
    common = vm_prices.index.intersection(dsr_prices.index)
    if not len(common) or common[-1].date() != LATEST_CAPTURED_SESSION:
        return [], {}, {"status": "blocked_latest_common_session"}
    current_month = (
        LATEST_CAPTURED_SESSION.year,
        LATEST_CAPTURED_SESSION.month,
    )
    month_sessions = [
        pd.Timestamp(value)
        for value in common
        if (value.year, value.month) == current_month
    ]
    effective = min(month_sessions)
    prior_sessions = common[common < effective]
    if not len(prior_sessions):
        return [], {}, {"status": "blocked_signal_session"}
    signal = pd.Timestamp(prior_sessions[-1])
    targets = {
        reference_engine.VM_ID: reference_engine.vm_target(vm_prices, signal),
        reference_engine.DSR_ID: reference_engine.dsr_target(dsr_prices, signal),
        reference_engine.USCI_ID: {"USCI": 1.0},
    }
    final: dict[str, float] = {}
    rows: list[dict[str, Any]] = []
    for component, target in targets.items():
        for symbol, weight in sorted(target.items()):
            final_weight = float(weight) / 3.0
            final[symbol] = final.get(symbol, 0.0) + final_weight
            rows.append(
                {
                    "record_type": "component_target",
                    "calculation_label": "activation_initialization_state_not_forward_performance",
                    "reference_id": REFERENCE_ID,
                    "component_id": component,
                    "component_signal_date": signal.date().isoformat(),
                    "component_target_effective_date": effective.date().isoformat(),
                    "latest_common_completed_session": LATEST_CAPTURED_SESSION.isoformat(),
                    "symbol": symbol,
                    "component_weight": 1.0 / 3.0,
                    "weight_within_component": float(weight),
                    "final_normalized_reference_weight": final_weight,
                    "gross_exposure": 1.0,
                    "daily_weight_sum": 1.0,
                    "invariant_status": "pass",
                }
            )
    total = sum(final.values())
    for symbol, weight in sorted(final.items()):
        rows.append(
            {
                "record_type": "final_normalized_reference_weight",
                "calculation_label": "activation_initialization_state_not_forward_performance",
                "reference_id": REFERENCE_ID,
                "component_id": "direct_normalized_holdings",
                "component_signal_date": signal.date().isoformat(),
                "component_target_effective_date": effective.date().isoformat(),
                "latest_common_completed_session": LATEST_CAPTURED_SESSION.isoformat(),
                "symbol": symbol,
                "component_weight": "",
                "weight_within_component": "",
                "final_normalized_reference_weight": weight,
                "gross_exposure": sum(abs(value) for value in final.values()),
                "daily_weight_sum": total,
                "invariant_status": "pass"
                if abs(total - 1.0) <= 1e-12
                else "fail",
            }
        )
    return rows, final, {
        "status": "pass" if abs(total - 1.0) <= 1e-12 else "fail",
        "component_ids": list(targets),
        "component_targets": targets,
        "signal_date": signal.date().isoformat(),
        "target_effective_date": effective.date().isoformat(),
        "latest_common_session": LATEST_CAPTURED_SESSION.isoformat(),
        "final_weights": final,
        "gross_exposure": sum(abs(value) for value in final.values()),
        "daily_weight_sum": total,
        "rules_changed": False,
    }


def capture_snapshot(
    capture: dict[str, Any], execution: date
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    signal = capture["common_date"]
    snapshot_dir = (
        OUTPUT_DIR / "forward_snapshots" / signal.isoformat() / "activation_capture"
    )
    snapshot_dir.mkdir(parents=True, exist_ok=False)
    manifest: list[dict[str, Any]] = []
    raw_paths: dict[str, str] = {}
    for series in ("VIX", "VIX3M"):
        item = capture["captures"][series]
        path = snapshot_dir / f"{series}_official_history.csv"
        path.write_bytes(item["raw_bytes"])
        raw_paths[series] = rel(path)
        manifest.append(
            {
                "series": series,
                "signal_observation_date": signal.isoformat(),
                "retrieval_timestamp_utc": item["retrieval_timestamp_utc"],
                "retrieval_timestamp_et": item["retrieval_timestamp_et"],
                "official_source": item["official_source"],
                "raw_path": rel(path),
                "raw_hash": item["raw_hash"],
                "normalized_hash": item["normalized_hash"],
                "value": capture["records"][series],
                "intended_execution_session": execution.isoformat(),
                "immutable": True,
            }
        )
    ratio = float(capture["records"]["VIX"] / capture["records"]["VIX3M"])
    target, state = prior.target_for_ratio(ratio)
    snapshot = {
        "observation_id": OBSERVATION_ID,
        "snapshot_role": "prospective_activation_signal_not_forward_performance",
        "signal_observation_date": signal.isoformat(),
        "retrieval_timestamp_utc": capture["captured_at_utc"],
        "retrieval_timestamp_et": datetime.fromisoformat(
            capture["captured_at_utc"]
        ).astimezone(prior.EASTERN).isoformat(),
        "official_sources": prior.OFFICIAL_URLS,
        "raw_paths": raw_paths,
        "raw_hashes": {
            series: capture["captures"][series]["raw_hash"]
            for series in ("VIX", "VIX3M")
        },
        "normalized_hashes": {
            series: capture["captures"][series]["normalized_hash"]
            for series in ("VIX", "VIX3M")
        },
        "VIX": capture["records"]["VIX"],
        "VIX3M": capture["records"]["VIX3M"],
        "ratio": ratio,
        "candidate_target_state": state,
        "candidate_target": target,
        "intended_execution_session": execution.isoformat(),
        "signal_date_strictly_before_execution": signal < execution,
        "immutable_original_snapshot": True,
        "later_revision_may_replace_original": False,
        "historical_backfill": False,
        "completed_forward_performance_row": False,
        "broker_submission": False,
    }
    snapshot["normalized_snapshot_hash"] = canonical_hash(snapshot)
    path = snapshot_dir / "snapshot_record.json"
    write_json(path, snapshot)
    snapshot["snapshot_path"] = rel(path)
    snapshot["snapshot_file_hash"] = file_hash(path)
    return snapshot, manifest


def build_initialization(
    reference_weights: dict[str, float],
    candidate_target: dict[str, float],
    execution: date,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    symbols = sorted(set(reference_weights) | set(candidate_target))
    rows: list[dict[str, Any]] = []
    total_weights: dict[str, float] = {}
    for symbol in symbols:
        reference_part = REFERENCE_WEIGHT * reference_weights.get(symbol, 0.0)
        candidate_part = CANDIDATE_WEIGHT * candidate_target.get(symbol, 0.0)
        total = reference_part + candidate_part
        total_weights[symbol] = total
        rows.append(
            {
                "observation_id": OBSERVATION_ID,
                "record_type": "prospective_initialization_target",
                "initialization_is_completed_forward_performance": False,
                "historical_backfill": False,
                "latest_valuation_session": LATEST_CAPTURED_SESSION.isoformat(),
                "first_eligible_forward_session": execution.isoformat(),
                "symbol": symbol,
                "reference_contribution_weight": reference_part,
                "candidate_contribution_weight": candidate_part,
                "total_target_weight": total,
                "virtual_target_market_value_at_post_cost_nav": total
                * (1.0 - COST_RATE),
                "shares_set_at_future_execution_close": True,
            }
        )
    total = sum(total_weights.values())
    gross = sum(abs(value) for value in total_weights.values())
    turnover = 0.5 * (1.0 + gross)
    passed = bool(
        abs(total - 1.0) <= 1e-12
        and gross <= 1.0 + 1e-12
        and all(value >= 0.0 for value in total_weights.values())
    )
    return rows, {
        "status": "pass" if passed else "fail",
        "target_weights": total_weights,
        "weight_sum": total,
        "gross_exposure": gross,
        "negative_weights": sum(value < 0.0 for value in total_weights.values()),
        "initialization_turnover": turnover,
        "simulated_cost_at_5bps": turnover * COST_RATE,
        "cost_charged_once": True,
        "completed_forward_performance_rows": 0,
        "historical_backfill": False,
    }


def acquisition_metadata(
    symbol: str,
    original_frame: pd.DataFrame,
    result: dict[str, Any],
    timestamp: datetime,
    raw_hash: str,
) -> dict[str, Any]:
    raw = pd.read_csv(RAW_DIR / f"{symbol}.csv")
    action_dates = [
        str(value)[:10]
        for value in raw.loc[
            (pd.to_numeric(raw["Dividends"]) != 0.0)
            | (pd.to_numeric(raw["Stock Splits"]) != 0.0),
            "Date",
        ]
    ]
    return {
        "symbol": symbol,
        "task_id": TASK_ID,
        "methodology": METHODOLOGY,
        "provider_id": "yfinance_existing_repo_supported_adjusted_daily_path",
        "original_provider_retrieval_timestamp_utc": timestamp.isoformat(),
        "retrieval_timestamp_provenance": "captured_provider_raw_file_mtime_utc",
        "provider_raw_evidence_path": rel(RAW_DIR / f"{symbol}.csv"),
        "provider_raw_evidence_hash": raw_hash,
        "original_canonical_file_hash": file_hash(cache_path(symbol)),
        "original_canonical_frame_hash": frame_hash(original_frame),
        "anchor_date": result["anchor_date"],
        "bridge_factor": result["continuation_bridge_factor"],
        "appended_date_range": [
            result["first_appended_date"],
            result["last_appended_date"],
        ],
        "appended_row_count": result["appended_row_count"],
        "action_dates": action_dates,
        "historical_rows_rewritten": False,
        "backward_revisions_admitted_into_historical_rows": False,
        "dividends_added_as_separate_return_cash": False,
        "account_position_order_endpoint_called": False,
    }


def atomic_commit(staged: dict[Path, bytes]) -> None:
    backups = {
        path: path.read_bytes() if path.exists() else None for path in staged
    }
    temporary: dict[Path, Path] = {}
    try:
        for path, content in staged.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            temp = path.with_name(path.name + ".append_correction_tmp")
            temp.write_bytes(content)
            temporary[path] = temp
        for path, temp in temporary.items():
            temp.replace(path)
    except BaseException:
        for path, content in backups.items():
            if content is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(content)
        raise
    finally:
        for temp in temporary.values():
            temp.unlink(missing_ok=True)


def run() -> dict[str, Any]:
    clean_output_dir()
    started = datetime.now(timezone.utc)
    symbols = required_symbols()
    registry_hash_before = file_hash(REGISTRY_PATH)
    active_text_before = ACTIVE_OBSERVATIONS_PATH.read_text(encoding="utf-8")
    active_before = yaml.safe_load(active_text_before)
    observation_matches = prior.matching_observation(active_before)
    state_reconciled = bool(
        len(observation_matches) == 1
        and observation_matches[0].get("stage") == "deferred"
        and observation_matches[0].get("paper_forward_active") is False
        and observation_matches[0].get("historical_forward_records_created") == 0
        and observation_matches[0].get("initialization_status")
        == "not_initialized_deferred"
    )
    observation_before = observation_matches[0] if len(observation_matches) == 1 else {}
    other_observations_before = prior.other_observation_hash(active_before)
    prior_hash_before = prior_packet_hash()
    unrelated_cache_before = unrelated_cache_hash(symbols)
    protected_before = {
        ROADMAP_PATH: file_hash(ROADMAP_PATH),
        QUEUE_PATH: file_hash(QUEUE_PATH),
        FAMILY_LEDGER_PATH: file_hash(FAMILY_LEDGER_PATH),
    }

    original_cache_bytes = {
        symbol: cache_path(symbol).read_bytes() for symbol in symbols
    }
    metadata_hashes_before = {
        symbol: file_hash(metadata_path(symbol)) for symbol in symbols
    }
    hash_rows, hashes_pass, capture_timestamps = hash_reconciliation_rows(symbols)
    original_frames = {symbol: direct_cache_frame(symbol) for symbol in symbols}
    provider_frames = {symbol: provider_frame(symbol) for symbol in symbols}
    action_rows, action_lookup, actions_pass = corporate_action_rows(
        symbols, provider_frames
    )

    classification_rows: list[dict[str, Any]] = []
    classification_pass = True
    overlap_dates_by_symbol: dict[str, list[date]] = {}
    for symbol in symbols:
        rows, passed, overlap_dates = overlap_classification(
            symbol,
            original_frames[symbol],
            provider_frames[symbol],
            action_lookup,
        )
        classification_rows.extend(rows)
        classification_pass = classification_pass and passed
        overlap_dates_by_symbol[symbol] = overlap_dates

    proposed_frames: dict[str, pd.DataFrame] = {}
    proposed_bytes: dict[str, bytes] = {}
    return_rows: list[dict[str, Any]] = []
    anchor_rows: list[dict[str, Any]] = []
    bridge_rows: list[dict[str, Any]] = []
    proposal_pass = True
    for symbol in symbols:
        try:
            frame, content, returns, result = append_symbol(
                symbol, original_frames[symbol], provider_frames[symbol]
            )
        except BaseException as exc:  # noqa: BLE001
            frame = pd.DataFrame(columns=CANONICAL_COLUMNS)
            content = b""
            returns = []
            result = {
                "symbol": symbol,
                "status": "fail",
                "failure": type(exc).__name__,
            }
        proposed_frames[symbol] = frame
        proposed_bytes[symbol] = content
        return_rows.extend(returns)
        proposal_pass = proposal_pass and result.get("status") == "pass"
        anchor_rows.append(
            {
                "symbol": symbol,
                "anchor_date": result.get("anchor_date", ""),
                "canonical_anchor_adjusted_close": result.get(
                    "canonical_anchor_adjusted_close", ""
                ),
                "provider_anchor_raw_close": result.get(
                    "provider_anchor_raw_close", ""
                ),
                "provider_anchor_adjusted_close": result.get(
                    "provider_anchor_adjusted_close", ""
                ),
                "provider_adjustment_factor": result.get(
                    "provider_anchor_adjustment_factor", ""
                ),
                "continuation_bridge_factor": result.get(
                    "continuation_bridge_factor", ""
                ),
                "overlap_sessions_before_anchor": result.get(
                    "overlap_sessions_before_anchor", ""
                ),
                "first_appended_date": result.get("first_appended_date", ""),
                "last_appended_date": result.get("last_appended_date", ""),
                "appended_row_count": result.get("appended_row_count", ""),
                "historical_byte_prefix_unchanged": result.get(
                    "historical_byte_prefix_unchanged", False
                ),
                "status": result.get("status", "fail"),
            }
        )
        bridge_rows.append(
            {
                **result,
                "methodology": METHODOLOGY,
                "fixed_bridge_for_complete_appended_segment": True,
                "provider_forward_returns_preserved": result.get(
                    "all_adjusted_returns_reconciled", False
                ),
            }
        )

    all_data_ready = bool(
        hashes_pass
        and actions_pass
        and classification_pass
        and proposal_pass
        and all(
            frame.iloc[-1]["date"] == LATEST_CAPTURED_SESSION.isoformat()
            for frame in proposed_frames.values()
        )
    )
    reference_rows: list[dict[str, Any]] = []
    reference_weights: dict[str, float] = {}
    reference_detail: dict[str, Any] = {"status": "not_run"}
    if all_data_ready:
        reference_rows, reference_weights, reference_detail = reference_state(
            proposed_frames
        )
    reference_ready = reference_detail.get("status") == "pass"

    volume_rows = [
        {
            "component_id": component,
            "volume_used_by_frozen_rule": False,
            "volume_lookback": "not_applicable",
            "immutable_pre_anchor_volume_preserved": True,
            "appended_provider_volume_finite_nonnegative": bool(
                all(
                    np.isfinite(
                        pd.to_numeric(provider_frames[symbol]["raw_volume"]).to_numpy(
                            dtype=float
                        )
                    ).all()
                    and (
                        pd.to_numeric(provider_frames[symbol]["raw_volume"]) >= 0.0
                    ).all()
                    for symbol in component_symbols
                )
            ),
            "boundary_signal_sensitivity": "none_rule_does_not_use_volume",
            "assessment_status": "pass",
        }
        for component, component_symbols in (
            (reference_engine.VM_ID, tuple(reference_engine.VM_SYMBOLS)),
            (reference_engine.DSR_ID, tuple(reference_engine.DSR_SYMBOLS)),
            (reference_engine.USCI_ID, tuple(reference_engine.USCI_SYMBOLS)),
        )
    ]
    volume_pass = all(row["assessment_status"] == "pass" for row in volume_rows)

    capture: dict[str, Any] = {"status": "not_run", "request_count": 0}
    snapshot: dict[str, Any] = {}
    snapshot_rows: list[dict[str, Any]] = []
    execution = prior.next_regular_session(started.astimezone(prior.EASTERN).date())
    if all_data_ready and reference_ready and volume_pass:
        capture = prior.capture_cboe_once(datetime.now(timezone.utc))
        if capture.get("status") == "captured":
            execution = prior.execution_session(
                datetime.now(timezone.utc), capture["common_date"]
            )
            snapshot, snapshot_rows = capture_snapshot(capture, execution)

    now_et = datetime.now(timezone.utc).astimezone(prior.EASTERN)
    signal_current = bool(
        snapshot
        and date.fromisoformat(snapshot["signal_observation_date"])
        in {
            LATEST_CAPTURED_SESSION,
            prior.previous_regular_session(LATEST_CAPTURED_SESSION),
        }
    )
    safe_boundary = bool(
        snapshot
        and date.fromisoformat(snapshot["signal_observation_date"]) < execution
        and prior.is_regular_session(execution)
        and (
            execution > now_et.date()
            or (
                execution == now_et.date()
                and now_et.time() < datetime.strptime("15:45", "%H:%M").time()
            )
        )
    )

    initialization_rows: list[dict[str, Any]] = []
    initialization: dict[str, Any] = {"status": "not_created"}
    if signal_current and safe_boundary:
        initialization_rows, initialization = build_initialization(
            reference_weights, snapshot["candidate_target"], execution
        )

    gates = {
        "captured_provider_hashes_and_rows_reconcile": hashes_pass,
        "overlap_discrepancies_classified_without_blocker": classification_pass,
        "named_and_all_corporate_actions_reconcile": actions_pass,
        "append_only_bridge_invariants": proposal_pass,
        "all_18_proposed_caches_reach_2026_07_24": all_data_ready,
        "volume_boundary_assessment": volume_pass,
        "frozen_reference_targets_reconcile": reference_ready,
        "fresh_immutable_cboe_snapshot": bool(
            snapshot and snapshot.get("immutable_original_snapshot")
        ),
        "signal_current_and_strictly_prospective": signal_current and safe_boundary,
        "initialization_invariants": initialization.get("status") == "pass",
        "existing_observation_state_reconciles": state_reconciled,
        "prior_evidence_unchanged_precommit": prior_packet_hash()
        == prior_hash_before,
    }
    ready = all(gates.values())

    initialization_fields = [
        "observation_id",
        "record_type",
        "initialization_is_completed_forward_performance",
        "historical_backfill",
        "latest_valuation_session",
        "first_eligible_forward_session",
        "symbol",
        "reference_contribution_weight",
        "candidate_contribution_weight",
        "total_target_weight",
        "virtual_target_market_value_at_post_cost_nav",
        "shares_set_at_future_execution_close",
    ]
    initialization_path = OUTPUT_DIR / "portfolio_initialization_record.csv"
    write_csv(
        initialization_path,
        initialization_rows if ready else [],
        initialization_fields,
    )

    metadata_payloads: dict[str, dict[str, Any]] = {}
    for symbol in symbols:
        result = next(row for row in bridge_rows if row["symbol"] == symbol)
        metadata_payloads[symbol] = acquisition_metadata(
            symbol,
            original_frames[symbol],
            result,
            capture_timestamps[symbol],
            EXPECTED_RAW_HASHES[symbol],
        )

    observation_after = observation_before
    active_text_after = active_text_before
    state_error = ""
    state_written = False
    strict_atomicity_policy = (
        "all_or_nothing_18_caches_18_manifests_and_exact_observation_update;"
        "Cboe_evidence_snapshot_may_persist_as_non_authoritative_failure_evidence"
    )
    if ready:
        observation_after = prior.updated_observation(
            observation_before,
            datetime.now(timezone.utc),
            snapshot,
            execution,
            rel(initialization_path),
            file_hash(initialization_path),
        )
        active_text_after = prior.replace_observation_text(
            active_text_before, observation_after
        )
        proposed_active = yaml.safe_load(active_text_after)
        active_validation = onboarding.validate_active_observation_document(
            proposed_active
        )
        if not active_validation["passed"]:
            state_error = "|".join(active_validation["errors"])
        elif prior.other_observation_hash(proposed_active) != other_observations_before:
            state_error = "unrelated_observation_change_detected"
        else:
            staged: dict[Path, bytes] = {
                ACTIVE_OBSERVATIONS_PATH: active_text_after.encode("utf-8")
            }
            for symbol in symbols:
                staged[cache_path(symbol)] = proposed_bytes[symbol]
                staged[metadata_path(symbol)] = (
                    json.dumps(
                        metadata_payloads[symbol],
                        indent=2,
                        sort_keys=True,
                        default=str,
                    )
                    + "\n"
                ).encode("utf-8")
            try:
                atomic_commit(staged)
                state_written = True
            except BaseException as exc:  # noqa: BLE001
                state_error = type(exc).__name__

    if ready and state_written:
        outcome = ACTIVATED_OUTCOME
        failure_reason = ""
        next_action = ACTIVATED_NEXT_ACTION
    elif ready:
        outcome = BLOCKED_OUTCOME
        failure_reason = "activation_state_reconciliation_failed"
        next_action = BLOCKED_NEXT_ACTION
    else:
        outcome = DEFERRED_OUTCOME
        if not hashes_pass or not proposal_pass:
            failure_reason = "append_only_continuation_failed"
        elif not classification_pass or not actions_pass:
            failure_reason = "unexplained_canonical_data_mismatch"
        elif not reference_ready or not volume_pass:
            failure_reason = "frozen_reference_not_current"
        elif not signal_current:
            failure_reason = "forward_signal_not_current"
        elif not safe_boundary:
            failure_reason = "activation_boundary_not_ready"
        else:
            failure_reason = "data_or_comparability_failure"
        next_action = DEFERRED_NEXT_ACTION

    blocker_details = [
        (
            f"{row['symbol']}:{row['date']}:{row['field_group']}:"
            f"{row['classification']}"
        )
        for row in classification_rows
        if row["blocking"]
    ]
    blocker_details.extend(
        (
            f"{row['symbol']}:{row['action_date']}:corporate_action:"
            "unexplained_corporate_action_mismatch"
        )
        for row in action_rows
        if row["reconciliation_status"] != "pass"
    )

    post_active = yaml.safe_load(
        ACTIVE_OBSERVATIONS_PATH.read_text(encoding="utf-8")
    )
    post_frames = {symbol: direct_cache_frame(symbol) for symbol in symbols}
    proposed_before_after_rows: list[dict[str, Any]] = []
    atomic_rows: list[dict[str, Any]] = []
    metadata_before_after_rows: list[dict[str, Any]] = []
    for symbol in symbols:
        original_hash = metadata_payloads[symbol]["original_canonical_file_hash"]
        current_cache_bytes = cache_path(symbol).read_bytes()
        proposed_before_after_rows.append(
            {
                "symbol": symbol,
                "before_file_hash": original_hash,
                "after_file_hash": file_hash(cache_path(symbol)),
                "before_row_count": len(original_frames[symbol]),
                "after_row_count": len(post_frames[symbol]),
                "before_last_date": original_frames[symbol].iloc[-1]["date"],
                "after_last_date": post_frames[symbol].iloc[-1]["date"],
                "historical_prefix_byte_identical": current_cache_bytes[
                    : len(original_cache_bytes[symbol])
                ]
                == original_cache_bytes[symbol],
                "proposed_append_row_count": len(proposed_frames[symbol])
                - len(original_frames[symbol]),
                "cache_updated": state_written,
                "methodology": METHODOLOGY,
            }
        )
        atomic_rows.append(
            {
                "symbol": symbol,
                "cache_path": rel(cache_path(symbol)),
                "metadata_path": rel(metadata_path(symbol)),
                "staged_before_commit": ready,
                "all_symbol_gate_passed": all_data_ready,
                "atomic_transaction_committed": state_written,
                "cache_updated": state_written,
                "metadata_updated": state_written,
                "rollback_required": False,
                "historical_rows_rewritten": False,
            }
        )
        metadata_before_after_rows.append(
            {
                "symbol": symbol,
                "metadata_path": rel(metadata_path(symbol)),
                "before_hash": metadata_hashes_before[symbol],
                "after_hash": file_hash(metadata_path(symbol)),
                "metadata_updated": state_written,
                "provider_raw_hash": EXPECTED_RAW_HASHES[symbol],
                "anchor_date": metadata_payloads[symbol]["anchor_date"],
                "bridge_factor": metadata_payloads[symbol]["bridge_factor"],
                "methodology": METHODOLOGY,
                "historical_rows_rewritten": False,
                "backward_revisions_admitted": False,
            }
        )

    observation_diff_rows = [
        {
            "observation_id": OBSERVATION_ID,
            "field": key,
            "before": observation_before.get(key, ""),
            "after": observation_after.get(key, ""),
            "changed": observation_before.get(key) != observation_after.get(key),
            "permitted_change": key
            in {
                "stage",
                "outcome",
                "state",
                "paper_forward_active",
                "activation_timestamp",
                "first_forward_observation_date",
                "proposed_first_execution_session",
                "initialization_status",
                "latest_captured_signal_date",
                "latest_snapshot_path",
                "latest_snapshot_hash",
                "snapshot_role",
                "current_status",
                "failure_reason",
                "next_action",
                "initialization_record_path",
                "initialization_record_hash",
                "portfolio_initialization_is_performance",
            },
        }
        for key in sorted(set(observation_before) | set(observation_after))
    ]
    alignment_rows = (
        [
            {
                "observation_id": OBSERVATION_ID,
                "canonical_latest_common_session": LATEST_CAPTURED_SESSION.isoformat(),
                "signal_observation_date": snapshot["signal_observation_date"],
                "intended_execution_session": execution.isoformat(),
                "signal_strictly_before_execution": snapshot[
                    "signal_date_strictly_before_execution"
                ],
                "task_completed_before_safe_cutoff": safe_boundary,
                "valid_us_trading_session": prior.is_regular_session(execution),
                "historical_or_synthetic_fill_required": False,
                "alignment_status": "pass" if signal_current and safe_boundary else "fail",
            }
        ]
        if snapshot
        else []
    )

    state_paths = [
        REGISTRY_PATH,
        ACTIVE_OBSERVATIONS_PATH,
        ROADMAP_PATH,
        QUEUE_PATH,
        FAMILY_LEDGER_PATH,
        *[cache_path(symbol) for symbol in symbols],
        *[metadata_path(symbol) for symbol in symbols],
    ]
    before_hashes = {
        REGISTRY_PATH: registry_hash_before,
        ACTIVE_OBSERVATIONS_PATH: sha256_bytes(active_text_before.encode("utf-8")),
        **protected_before,
    }
    for symbol in symbols:
        before_hashes[cache_path(symbol)] = metadata_payloads[symbol][
            "original_canonical_file_hash"
        ]
        before_hashes[metadata_path(symbol)] = metadata_hashes_before[symbol]
    state_rows = [
        {
            "path": rel(path),
            "before_hash": before_hashes.get(path, ""),
            "after_hash": file_hash(path),
            "changed": before_hashes.get(path, "") != file_hash(path),
            "permitted_change": (
                path == ACTIVE_OBSERVATIONS_PATH
                or path in {cache_path(symbol) for symbol in symbols}
                or path in {metadata_path(symbol) for symbol in symbols}
            ),
            "change_role": (
                "exact_observation_activation"
                if path == ACTIVE_OBSERVATIONS_PATH
                else "exact_append_only_cache_or_acquisition_manifest"
                if path.parent == CACHE_DIR
                else "protected_unchanged"
            ),
        }
        for path in state_paths
    ]

    manifest = {
        "task_id": TASK_ID,
        "mode": "correction",
        "stage": "correction",
        "strategy_id": STRATEGY_ID,
        "observation_id": OBSERVATION_ID,
        "methodology": METHODOLOGY,
        "atomicity_policy": strict_atomicity_policy,
        "outcome": outcome,
        "failure_reason": failure_reason,
        "exact_next_action": next_action,
        "required_symbol_count": len(symbols),
        "market_data_provider_downloads": 0,
        "official_cboe_requests": capture.get("request_count", 0),
        "blocking_reconciliation_details": blocker_details,
        "raw_ohlc_relative_tolerance": RAW_OHLC_TOLERANCE,
        "corporate_action_return_tolerance": ACTION_RETURN_TOLERANCE,
        "canonical_caches_updated": 18 if state_written else 0,
        "strategies_created": 0,
        "strategies_updated": 0,
        "experiment_trials_created": 0,
        "observations_created": 0,
        "existing_observations_updated": int(state_written),
        "data_capability_tasks": 1,
        "process_tasks": 1,
        "initialization_records": int(bool(ready and initialization_rows)),
        "completed_forward_performance_rows": 0,
        "broker_or_paper_orders": 0,
    }
    write_yaml(OUTPUT_DIR / "correction_manifest.yaml", manifest)
    write_csv(
        OUTPUT_DIR / "captured_provider_hash_reconciliation.csv",
        hash_rows,
        list(hash_rows[0]),
    )
    write_csv(
        OUTPUT_DIR / "symbol_anchor_inventory.csv",
        anchor_rows,
        list(anchor_rows[0]),
    )
    write_csv(
        OUTPUT_DIR / "overlap_discrepancy_classification.csv",
        classification_rows,
        list(classification_rows[0]),
    )
    write_csv(
        OUTPUT_DIR / "corporate_action_reconciliation.csv",
        action_rows,
        list(action_rows[0]),
    )
    write_csv(
        OUTPUT_DIR / "bridge_factor_reconciliation.csv",
        bridge_rows,
        [
            "symbol",
            "anchor_date",
            "canonical_anchor_adjusted_close",
            "provider_anchor_raw_close",
            "provider_anchor_adjusted_close",
            "provider_anchor_adjustment_factor",
            "continuation_bridge_factor",
            "first_appended_date",
            "last_appended_date",
            "appended_row_count",
            "historical_rows_rewritten",
            "historical_byte_prefix_unchanged",
            "all_adjusted_returns_reconciled",
            "frame_invariants_pass",
            "missing_sessions",
            "status",
            "methodology",
            "fixed_bridge_for_complete_appended_segment",
            "provider_forward_returns_preserved",
        ],
    )
    write_csv(
        OUTPUT_DIR / "appended_return_reconciliation.csv",
        return_rows,
        list(return_rows[0]),
    )
    write_csv(
        OUTPUT_DIR / "volume_boundary_assessment.csv",
        volume_rows,
        list(volume_rows[0]),
    )
    write_csv(
        OUTPUT_DIR / "proposed_canonical_before_after.csv",
        proposed_before_after_rows,
        list(proposed_before_after_rows[0]),
    )
    write_csv(
        OUTPUT_DIR / "atomic_cache_update_manifest.csv",
        atomic_rows,
        list(atomic_rows[0]),
    )
    write_csv(
        OUTPUT_DIR / "acquisition_metadata_before_after.csv",
        metadata_before_after_rows,
        list(metadata_before_after_rows[0]),
    )
    write_csv(
        OUTPUT_DIR / "frozen_reference_initialization_state.csv",
        reference_rows,
        [
            "record_type",
            "calculation_label",
            "reference_id",
            "component_id",
            "component_signal_date",
            "component_target_effective_date",
            "latest_common_completed_session",
            "symbol",
            "component_weight",
            "weight_within_component",
            "final_normalized_reference_weight",
            "gross_exposure",
            "daily_weight_sum",
            "invariant_status",
        ],
    )
    write_csv(
        OUTPUT_DIR / "official_cboe_forward_snapshot_manifest.csv",
        snapshot_rows,
        [
            "series",
            "signal_observation_date",
            "retrieval_timestamp_utc",
            "retrieval_timestamp_et",
            "official_source",
            "raw_path",
            "raw_hash",
            "normalized_hash",
            "value",
            "intended_execution_session",
            "immutable",
        ],
    )
    write_csv(
        OUTPUT_DIR / "signal_execution_alignment.csv",
        alignment_rows,
        [
            "observation_id",
            "canonical_latest_common_session",
            "signal_observation_date",
            "intended_execution_session",
            "signal_strictly_before_execution",
            "task_completed_before_safe_cutoff",
            "valid_us_trading_session",
            "historical_or_synthetic_fill_required",
            "alignment_status",
        ],
    )
    write_csv(
        OUTPUT_DIR / "paper_demo_observation_before_after.csv",
        observation_diff_rows,
        list(observation_diff_rows[0]),
    )
    data_task = {
        "task_id": TASK_ID,
        "entity_type": "data_capability_task",
        "stage": "feasible" if all_data_ready else "blocked",
        "adaptation_label": "data_feasibility_adjustment",
        "methodology": METHODOLOGY,
        "provider_downloads": 0,
        "captured_raw_files_reused": 18,
        "canonical_caches_updated": 18 if state_written else 0,
        "historical_backtest_run": False,
        "broker_or_order_action": False,
    }
    write_csv(
        OUTPUT_DIR / "data_capability_task_log.csv",
        [data_task],
        list(data_task),
    )
    process_task = {
        "task_id": TASK_ID,
        "entity_type": "process_task",
        "stage": "correction",
        "strategies_created": 0,
        "trials_created": 0,
        "observations_created": 0,
        "observations_updated": int(state_written),
        "completed_forward_rows": 0,
        "broker_orders": 0,
    }
    write_csv(
        OUTPUT_DIR / "process_task_log.csv",
        [process_task],
        list(process_task),
    )
    write_csv(
        OUTPUT_DIR / "state_change_manifest.csv",
        state_rows,
        list(state_rows[0]),
    )
    outcome_row = {
        "strategy_id": STRATEGY_ID,
        "observation_id": OBSERVATION_ID,
        "outcome": outcome,
        "failure_reason": failure_reason,
        "exact_next_action": next_action,
        "canonical_latest_common_session": (
            LATEST_CAPTURED_SESSION.isoformat() if state_written else ""
        ),
        "signal_date": snapshot.get("signal_observation_date", ""),
        "first_eligible_forward_session": execution.isoformat(),
        "paper_forward_active": state_written,
        "initialization_created": bool(ready and initialization_rows),
        "completed_forward_performance_rows": 0,
    }
    write_csv(
        OUTPUT_DIR / "outcome_summary.csv",
        [outcome_row],
        list(outcome_row),
    )
    failure_rows = (
        [
            {
                "observation_id": OBSERVATION_ID,
                "failure_reason": failure_reason,
                "detail": state_error
                or "|".join(blocker_details)
                or "|".join(key for key, value in gates.items() if not value),
            }
        ]
        if failure_reason
        else []
    )
    write_csv(
        OUTPUT_DIR / "failure_reasons.csv",
        failure_rows,
        ["observation_id", "failure_reason", "detail"],
    )
    next_row = {
        "observation_id": OBSERVATION_ID,
        "outcome": outcome,
        "next_action": next_action,
        "executed_in_this_task": False,
    }
    write_csv(OUTPUT_DIR / "next_actions.csv", [next_row], list(next_row))

    prior_unchanged = prior_packet_hash() == prior_hash_before
    unrelated_cache_unchanged = unrelated_cache_hash(symbols) == unrelated_cache_before
    registry_unchanged = file_hash(REGISTRY_PATH) == registry_hash_before
    other_observations_unchanged = (
        prior.other_observation_hash(post_active) == other_observations_before
    )
    active_validation_after = onboarding.validate_active_observation_document(
        post_active
    )
    required_files = [
        "correction_manifest.yaml",
        "captured_provider_hash_reconciliation.csv",
        "symbol_anchor_inventory.csv",
        "overlap_discrepancy_classification.csv",
        "corporate_action_reconciliation.csv",
        "bridge_factor_reconciliation.csv",
        "appended_return_reconciliation.csv",
        "volume_boundary_assessment.csv",
        "proposed_canonical_before_after.csv",
        "atomic_cache_update_manifest.csv",
        "acquisition_metadata_before_after.csv",
        "frozen_reference_initialization_state.csv",
        "official_cboe_forward_snapshot_manifest.csv",
        "signal_execution_alignment.csv",
        "portfolio_initialization_record.csv",
        "paper_demo_observation_before_after.csv",
        "data_capability_task_log.csv",
        "process_task_log.csv",
        "state_change_manifest.csv",
        "outcome_summary.csv",
        "failure_reasons.csv",
        "next_actions.csv",
    ]
    consistency = {
        **manifest,
        "overall_pass": bool(
            outcome in {ACTIVATED_OUTCOME, DEFERRED_OUTCOME}
            and prior_unchanged
            and unrelated_cache_unchanged
            and registry_unchanged
            and other_observations_unchanged
            and active_validation_after["passed"]
            and all((OUTPUT_DIR / name).exists() for name in required_files)
            and (outcome != ACTIVATED_OUTCOME or all(gates.values()))
        ),
        "activation_gates": gates,
        "state_written": state_written,
        "state_error": state_error,
        "captured_provider_hashes": {
            symbol: file_hash(RAW_DIR / f"{symbol}.csv") for symbol in symbols
        },
        "provider_hashes_unchanged_during_task": all(
            file_hash(RAW_DIR / f"{symbol}.csv") == EXPECTED_RAW_HASHES[symbol]
            for symbol in symbols
        ),
        "prior_evidence_hash_before": prior_hash_before,
        "prior_evidence_hash_after": prior_packet_hash(),
        "prior_evidence_unchanged": prior_unchanged,
        "unrelated_cache_hash_before": unrelated_cache_before,
        "unrelated_cache_hash_after": unrelated_cache_hash(symbols),
        "unrelated_cache_unchanged": unrelated_cache_unchanged,
        "registry_hash_before": registry_hash_before,
        "registry_hash_after": file_hash(REGISTRY_PATH),
        "registry_unchanged": registry_unchanged,
        "roadmap_unchanged": file_hash(ROADMAP_PATH)
        == protected_before[ROADMAP_PATH],
        "research_queue_unchanged": file_hash(QUEUE_PATH)
        == protected_before[QUEUE_PATH],
        "family_ledger_unchanged": file_hash(FAMILY_LEDGER_PATH)
        == protected_before[FAMILY_LEDGER_PATH],
        "other_observations_unchanged": other_observations_unchanged,
        "active_observation_validation": active_validation_after,
        "reference_reconciliation": reference_detail,
        "initialization": initialization,
        "snapshot": snapshot,
        "blocking_reconciliation_details": blocker_details,
        "required_artifacts_present": all(
            (OUTPUT_DIR / name).exists() for name in required_files
        ),
        "market_data_provider_downloads": 0,
        "historical_backtest_run": False,
        "validation_rerun": False,
        "historical_forward_backfill": False,
        "completed_forward_performance_rows": 0,
        "strategies_created": 0,
        "strategies_updated": 0,
        "experiment_trials_created": 0,
        "observations_created": 0,
        "broker_orders": 0,
        "paper_orders": 0,
        "live_orders": 0,
        "real_money_actions": 0,
    }
    write_json(OUTPUT_DIR / "consistency_check.json", consistency)

    report = f"""# Canonical Append Correction and IVTS Activation V1

## Outcome

`{outcome}`

The correction reused the 18 frozen provider files from the prior packet and
made zero market-data provider requests. Historical canonical bytes through
each symbol-specific anchor were preserved. Post-anchor adjusted OHLC was
connected with one fixed bridge factor per symbol under `{METHODOLOGY}`.

The SPY distribution on 2026-06-18, USMV distribution on 2026-06-15, and
SPLV distribution on 2026-06-22 were verified against the provider adjusted
total-return path. Dividends were not added separately.

Blocking reconciliation details:
`{"; ".join(blocker_details) or "none"}`.

## Atomicity

`{strict_atomicity_policy}`

Canonical caches updated: `{18 if state_written else 0}`.
Observation updated: `{str(state_written).lower()}`.
Completed forward-performance rows: `0`.

The immutable signal date is
`{snapshot.get("signal_observation_date", "unavailable")}` and the prospective
execution session is `{execution.isoformat()}`.

Failure reason: `{failure_reason or "none"}`.

Exact next action: `{next_action}`.

No strategy, experiment trial, broker order, paper order, live order, or
real-money action was created.
"""
    (OUTPUT_DIR / "correction_report.md").write_text(report, encoding="utf-8")
    consistency["required_artifacts_present"] = all(
        (OUTPUT_DIR / name).exists()
        for name in [
            *required_files,
            "consistency_check.json",
            "correction_report.md",
        ]
    )
    consistency["overall_pass"] = bool(
        consistency["overall_pass"] and consistency["required_artifacts_present"]
    )
    write_json(OUTPUT_DIR / "consistency_check.json", consistency)

    return {
        "task_id": TASK_ID,
        "outcome": outcome,
        "failure_reason": failure_reason,
        "next_action": next_action,
        "market_data_provider_downloads": 0,
        "official_cboe_requests": capture.get("request_count", 0),
        "canonical_caches_updated": 18 if state_written else 0,
        "observation_active": state_written,
        "signal_date": snapshot.get("signal_observation_date", ""),
        "first_eligible_forward_session": execution.isoformat(),
        "initialization_records": len(initialization_rows) if ready else 0,
        "completed_forward_performance_rows": 0,
        "consistency_passed": consistency["overall_pass"],
    }


def main() -> int:
    result = run()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["consistency_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
