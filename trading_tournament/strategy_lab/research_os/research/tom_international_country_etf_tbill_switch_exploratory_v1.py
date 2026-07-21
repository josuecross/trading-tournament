from __future__ import annotations

import csv
import hashlib
import json
import math
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.data import NORMALIZED_COLUMNS, _download_yfinance, build_adjusted_ohlc
from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT


ARTIFACT_ID = "tom_international_country_etf_tbill_switch_exploratory_v1"
OUTPUT_DIR = Path("reports") / "strategy_research" / ARTIFACT_ID
DATA_CACHE_DIR = Path("data") / "cache"
PILOT_CACHE_DIR = Path("data") / "universe_expansion" / "pilot_etf_market_data_v1"

COUNTRY_ETFS: tuple[str, ...] = ("EWA", "EWZ", "EWC", "EWQ", "EWG", "EWH", "EWJ", "EWD", "EWU")
CASH_SYMBOL = "BIL"
FROZEN_SYMBOLS: tuple[str, ...] = (*COUNTRY_ETFS, CASH_SYMBOL)
COUNTRY_NAMES = {
    "EWA": "Australia",
    "EWZ": "Brazil",
    "EWC": "Canada",
    "EWQ": "France",
    "EWG": "Germany",
    "EWH": "Hong Kong",
    "EWJ": "Japan",
    "EWD": "Sweden",
    "EWU": "United Kingdom",
}
COST_LEVELS_BPS: tuple[int, ...] = (0, 5, 10)
START_NAV = 3000.0
TOL = 1e-10
EXPECTED_TRIAL_COUNT = 111

METHOD_TOM = "TOM_SOURCE"
METHOD_IDENTITY = "TOM_SOURCE_IDENTITY"
METHOD_BUY_HOLD = "COUNTRY_BUY_HOLD"
METHOD_EXPOSURE = "EXPOSURE_MATCHED_STATIC"
METHOD_BIL = "BIL_ONLY"
COUNTRY_METHODS: tuple[str, ...] = (METHOD_TOM, METHOD_IDENTITY, METHOD_BUY_HOLD, METHOD_EXPOSURE)
ALL_METHODS: tuple[str, ...] = (*COUNTRY_METHODS, METHOD_BIL)

TOM_DAY_MINUS_1 = "DAY_MINUS_1"
TOM_DAY_PLUS_1 = "DAY_PLUS_1"
TOM_DAY_PLUS_2 = "DAY_PLUS_2"
TOM_DAY_PLUS_3 = "DAY_PLUS_3"
NON_TOM = "NON_TOM"
TOM_LABELS = {TOM_DAY_MINUS_1, TOM_DAY_PLUS_1, TOM_DAY_PLUS_2, TOM_DAY_PLUS_3}

FAILURE_CODES = (
    "SOURCE_UNIVERSE_INCOMPLETE",
    "INSUFFICIENT_COMMON_HISTORY",
    "INVALID_TOM_CALENDAR_LABEL",
    "NEXT_OPEN_UNAVAILABLE",
    "IDENTITY_EQUIVALENCE_FAILED",
    "SYMBOL_SUBSTITUTION_ATTEMPTED",
    "DYNAMIC_UNIVERSE_CHANGE",
    "STALE_OR_FORWARDFILLED_RETURN",
    "ACCOUNTING_RECONCILIATION_FAILED",
    "INCONSISTENT_COST_APPLICATION",
)

CLASSIFICATIONS = (
    "WORTH_DEEPER_RESEARCH",
    "CONTROL_WEAK",
    "NO_MATERIAL_EDGE",
    "COST_DOMINATED",
    "BENCHMARK_DOMINATED",
    "CONCENTRATED",
    "DATA_OR_IMPLEMENTATION_INVALID",
)

RULE_PACKET = {
    "strategy_id": ARTIFACT_ID,
    "source_rule_completion": True,
    "source_symbols_in_order": list(COUNTRY_ETFS),
    "cash_translation": CASH_SYMBOL,
    "rule": {
        "per_country_independent_trial": True,
        "hold_country_etf_on_us_trading_days": [
            TOM_DAY_MINUS_1,
            TOM_DAY_PLUS_1,
            TOM_DAY_PLUS_2,
            TOM_DAY_PLUS_3,
        ],
        "hold_bil_all_other_days": True,
        "ranking": False,
        "lookback": False,
        "trend_filter": False,
        "volatility_filter": False,
        "leverage": False,
        "shorting": False,
        "optional_management_overlay_count": 0,
    },
    "execution": {
        "entry_intent": "created before DAY_MINUS_1 from known US trading calendar",
        "entry_fill": "next_valid_open_on_DAY_MINUS_1",
        "exit_intent": "created after DAY_PLUS_3_close",
        "exit_fill": "next_valid_open_on_DAY_PLUS_4",
        "same_close_execution": False,
        "retrospective_prior_close_fill": False,
    },
}


@dataclass(frozen=True)
class PriceData:
    open: pd.DataFrame
    close: pd.DataFrame
    coverage_rows: list[dict[str, Any]]
    common_start: pd.Timestamp
    common_end: pd.Timestamp
    calendar: pd.DatetimeIndex
    file_hashes: dict[str, str]
    acquisition_rows: list[dict[str, Any]]
    failures: list[dict[str, Any]]


@dataclass(frozen=True)
class TrialPath:
    trial_id: str
    method_id: str
    country_symbol: str
    cost_bps_per_side: int
    target_weights: pd.DataFrame
    end_weights: pd.DataFrame
    nav: pd.Series
    cash: pd.Series
    daily_returns: pd.Series
    orders: pd.DataFrame
    fills: pd.DataFrame
    daily_positions: pd.DataFrame
    component_returns: pd.DataFrame
    costs: pd.DataFrame
    state_hash: str
    economic_state_hash: str


def run(root: Path = ROOT) -> dict[str, Any]:
    output_dir = root / OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    prices = load_price_data(root)
    calendar_rows = classify_tom_calendar(prices.calendar)
    calendar_hash = stable_hash(calendar_rows)
    trials = registered_trials()
    source_hashes = source_and_worktree_hashes(root, prices.file_hashes)
    frozen_universe = frozen_universe_payload(prices, source_hashes)
    config = configuration_payload(prices, calendar_hash)
    prereg = pre_registered_manifest(source_hashes, frozen_universe, prices, config, trials)

    write_json(output_dir / "source_and_worktree_hashes.json", source_hashes)
    write_json(output_dir / "frozen_universe.json", frozen_universe)
    write_csv(output_dir / "data_coverage.csv", prices.coverage_rows, data_coverage_fields())
    write_csv(output_dir / "calendar_classification.csv", calendar_rows, calendar_fields())
    write_csv(output_dir / "trial_registry.csv", trials, trial_registry_fields())
    write_json(output_dir / "pre_registered_manifest.json", prereg)

    failure_rows = list(prices.failures)
    if failure_rows:
        failed_trials = completed_trial_registry(trials, {}, failure_rows)
        write_failure_only_artifacts(output_dir, prices, trials, failed_trials, failure_rows)
        return {
            "classification": "DATA_OR_IMPLEMENTATION_INVALID",
            "artifact_dir": str(output_dir),
            "trial_count": len(failed_trials),
            "completed_trial_count": 0,
            "failed_trial_count": len(failed_trials),
        }

    paths = run_registered_trials(prices, calendar_rows)
    identity_rows, identity_failures = identity_equivalence_rows(paths)
    failure_rows.extend(identity_failures)
    trial_registry_rows = completed_trial_registry(trials, paths, failure_rows)
    metrics_rows = metrics_for_all_paths(paths, prices, calendar_rows)
    subperiod_rows = subperiod_metrics(paths, prices)
    daily_rows = daily_positions_rows(paths, calendar_rows)
    turnover_rows = turnover_and_cost_rows(paths, calendar_rows)
    exposure_rows = exposure_matched_control_rows(prices.calendar)
    diagnostic_rows = close_to_close_source_diagnostic(prices, calendar_rows)
    episode_rows = tom_episode_attribution(paths, calendar_rows)
    country_rows = country_attribution(metrics_rows)
    month_rows = calendar_month_attribution(paths, calendar_rows)
    concentration_rows = concentration_diagnostics(paths, metrics_rows, subperiod_rows, month_rows, episode_rows)
    classification, comparison = classify_results(
        metrics_rows,
        subperiod_rows,
        concentration_rows,
        identity_rows,
        failure_rows,
    )

    manifest = manifest_payload(
        prices,
        config,
        trial_registry_rows,
        classification,
        identity_rows,
        failure_rows,
        source_hashes,
    )
    source_update = source_of_truth_update(classification, prices)

    write_csv(output_dir / "trial_registry.csv", trial_registry_rows, trial_registry_fields())
    write_csv(output_dir / "identity_equivalence.csv", identity_rows, identity_equivalence_fields())
    write_csv(output_dir / "metrics.csv", metrics_rows, metrics_fields())
    write_csv(output_dir / "subperiod_metrics.csv", subperiod_rows, subperiod_fields())
    write_csv(output_dir / "daily_positions.csv", daily_rows, daily_positions_fields())
    write_csv(output_dir / "tom_episode_attribution.csv", episode_rows, episode_fields())
    write_csv(output_dir / "country_attribution.csv", country_rows, country_attribution_fields())
    write_csv(output_dir / "calendar_month_attribution.csv", month_rows, calendar_month_fields())
    write_csv(output_dir / "exposure_matched_control.csv", exposure_rows, exposure_control_fields())
    write_csv(output_dir / "turnover_and_costs.csv", turnover_rows, turnover_fields())
    write_csv(output_dir / "close_to_close_source_diagnostic.csv", diagnostic_rows, diagnostic_fields())
    write_csv(output_dir / "concentration_diagnostics.csv", concentration_rows, concentration_fields())
    write_csv(output_dir / "failure_registry.csv", failure_rows, failure_fields())
    write_text(output_dir / "comparison.md", comparison)
    write_text(output_dir / "source_of_truth_update.md", source_update)
    write_text(
        output_dir / "test_results.txt",
        "PENDING - test command output is written by the external command harness after the bounded runner completes.\n",
    )
    write_json(output_dir / "manifest.json", manifest)

    return {
        "classification": classification,
        "artifact_dir": str(output_dir),
        "trial_count": len(trial_registry_rows),
        "completed_trial_count": sum(1 for row in trial_registry_rows if row["status"] == "COMPLETED"),
        "failed_trial_count": sum(1 for row in trial_registry_rows if row["status"] == "FAILED"),
    }


def load_price_data(root: Path) -> PriceData:
    frames: dict[str, pd.DataFrame] = {}
    coverage_rows: list[dict[str, Any]] = []
    acquisition_rows: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    for symbol in FROZEN_SYMBOLS:
        frame, coverage, acquisition = ensure_symbol_cache(root, symbol)
        coverage_rows.append(coverage)
        acquisition_rows.append(acquisition)
        if frame is None or frame.empty or coverage["qa_status"] != "passed":
            failures.append(
                failure_row(
                    trial_id="",
                    date="",
                    symbol=symbol,
                    failure_code="SOURCE_UNIVERSE_INCOMPLETE",
                    detail=coverage.get("failure_reason", "required source symbol unavailable"),
                )
            )
        else:
            frames[symbol] = frame

    if set(frames) != set(FROZEN_SYMBOLS):
        return PriceData(
            open=pd.DataFrame(),
            close=pd.DataFrame(),
            coverage_rows=coverage_rows,
            common_start=pd.NaT,
            common_end=pd.NaT,
            calendar=pd.DatetimeIndex([]),
            file_hashes={},
            acquisition_rows=acquisition_rows,
            failures=failures,
        )

    indexed = {symbol: indexed_frame(frame) for symbol, frame in frames.items()}
    common_start = max(frame.index.min() for frame in indexed.values())
    common_end = min(frame.index.max() for frame in indexed.values())
    if pd.isna(common_start) or pd.isna(common_end) or common_end <= common_start:
        failures.append(
            failure_row(
                trial_id="",
                date="",
                symbol=";".join(FROZEN_SYMBOLS),
                failure_code="INSUFFICIENT_COMMON_HISTORY",
                detail="No usable common adjusted-price period after all ten symbols are available.",
            )
        )
        return PriceData(
            open=pd.DataFrame(),
            close=pd.DataFrame(),
            coverage_rows=coverage_rows,
            common_start=common_start,
            common_end=common_end,
            calendar=pd.DatetimeIndex([]),
            file_hashes=file_hashes_for_symbols(root),
            acquisition_rows=acquisition_rows,
            failures=failures,
        )

    bil_calendar = pd.DatetimeIndex(
        indexed[CASH_SYMBOL].loc[(indexed[CASH_SYMBOL].index >= common_start) & (indexed[CASH_SYMBOL].index <= common_end)].index
    )
    if len(bil_calendar) < 252:
        failures.append(
            failure_row(
                trial_id="",
                date="",
                symbol=";".join(FROZEN_SYMBOLS),
                failure_code="INSUFFICIENT_COMMON_HISTORY",
                detail=f"Common BIL-calendar history has only {len(bil_calendar)} sessions.",
            )
        )

    missing_by_symbol: dict[str, int] = {}
    for symbol, frame in indexed.items():
        usable = frame.reindex(bil_calendar)
        missing = int(usable[["open", "close", "adj_close"]].isna().any(axis=1).sum())
        missing_by_symbol[symbol] = missing
        if missing:
            failures.append(
                failure_row(
                    trial_id="",
                    date="",
                    symbol=symbol,
                    failure_code="STALE_OR_FORWARDFILLED_RETURN",
                    detail=f"{missing} BIL-calendar sessions lack exact open/close/adj_close rows; no forward fill is allowed.",
                )
            )

    coverage_rows = [
        {**row, "missing_date_count_on_bil_calendar": missing_by_symbol.get(str(row["symbol"]), "")}
        for row in coverage_rows
    ]

    if failures:
        return PriceData(
            open=pd.DataFrame(),
            close=pd.DataFrame(),
            coverage_rows=coverage_rows,
            common_start=common_start,
            common_end=common_end,
            calendar=bil_calendar,
            file_hashes=file_hashes_for_symbols(root),
            acquisition_rows=acquisition_rows,
            failures=failures,
        )

    open_frame = pd.DataFrame({symbol: indexed[symbol].reindex(bil_calendar)["open"] for symbol in FROZEN_SYMBOLS})
    close_frame = pd.DataFrame({symbol: indexed[symbol].reindex(bil_calendar)["close"] for symbol in FROZEN_SYMBOLS})
    return PriceData(
        open=open_frame,
        close=close_frame,
        coverage_rows=coverage_rows,
        common_start=pd.Timestamp(bil_calendar[0]),
        common_end=pd.Timestamp(bil_calendar[-1]),
        calendar=bil_calendar,
        file_hashes=file_hashes_for_symbols(root),
        acquisition_rows=acquisition_rows,
        failures=failures,
    )


def ensure_symbol_cache(root: Path, symbol: str) -> tuple[pd.DataFrame | None, dict[str, Any], dict[str, Any]]:
    cache = root / DATA_CACHE_DIR / f"{symbol}.csv"
    pilot = root / PILOT_CACHE_DIR / f"{symbol}.csv"
    checked_sources: list[str] = []

    if cache.exists():
        checked_sources.append(str(cache))
        frame, coverage = qa_symbol_file(cache, symbol, source_action="existing_cache")
        if frame is not None and coverage["qa_status"] == "passed":
            coverage.update({"provider_api_called": False, "download_attempted": False})
            return frame, coverage, acquisition_row(symbol, "existing_cache", False, False, "not_needed_cache_passed", "")

    if pilot.exists():
        checked_sources.append(str(pilot))
        frame, pilot_coverage = qa_symbol_file(pilot, symbol, source_action="pilot_cache_copy")
        if frame is not None and pilot_coverage["qa_status"] == "passed":
            cache.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(pilot, cache)
            frame, coverage = qa_symbol_file(cache, symbol, source_action="pilot_cache_copy")
            coverage.update({"provider_api_called": False, "download_attempted": False})
            return frame, coverage, acquisition_row(symbol, "pilot_cache_copy", False, False, "copied_from_local_pilot_cache", "")

    try:
        raw = _download_yfinance(
            symbol,
            "2007-01-01",
            None,
            {"auto_adjust": False, "actions": True, "progress": False, "multi_level_index": False, "timeout": 10},
        )
        if raw is None or raw.empty:
            raise ValueError("provider returned no rows")
        normalized = build_adjusted_ohlc(raw, symbol)
        cache.parent.mkdir(parents=True, exist_ok=True)
        normalized.to_csv(cache, index=False)
        frame, coverage = qa_symbol_file(cache, symbol, source_action="yfinance_compatible_download")
        if frame is None or coverage["qa_status"] != "passed":
            coverage.update({"provider_api_called": True, "download_attempted": True})
            return (
                None,
                coverage,
                acquisition_row(symbol, "yfinance_compatible_download", True, True, "downloaded_failed_qa", coverage["failure_reason"]),
            )
        coverage.update({"provider_api_called": True, "download_attempted": True})
        return (
            frame,
            coverage,
            acquisition_row(symbol, "yfinance_compatible_download", True, True, "downloaded_and_cached", ""),
        )
    except Exception as exc:
        coverage = base_coverage_row(symbol, cache)
        coverage.update(
            {
                "cache_status": "missing_or_failed",
                "qa_status": "failed",
                "source_action": "unavailable_after_existing_authorized_paths",
                "provider_api_called": True,
                "download_attempted": True,
                "failure_code": "SOURCE_UNIVERSE_INCOMPLETE",
                "failure_reason": f"{exc}; checked_sources={checked_sources}",
            }
        )
        return (
            None,
            coverage,
            acquisition_row(symbol, "yfinance_compatible_download", True, True, "download_failed", str(exc)),
        )


def qa_symbol_file(path: Path, symbol: str, *, source_action: str) -> tuple[pd.DataFrame | None, dict[str, Any]]:
    row = base_coverage_row(symbol, path)
    try:
        raw = pd.read_csv(path)
        normalized = build_adjusted_ohlc(raw, symbol)
    except Exception as exc:
        row.update(
            {
                "cache_available": path.exists(),
                "cache_status": "present_failed",
                "qa_status": "failed",
                "source_action": source_action,
                "failure_code": "SOURCE_UNIVERSE_INCOMPLETE",
                "failure_reason": str(exc),
            }
        )
        return None, row

    dates = pd.to_datetime(normalized["date"], errors="coerce").dt.tz_localize(None)
    duplicate_dates = int(dates.dropna().duplicated().sum())
    numeric = normalized[["open", "high", "low", "close", "adj_close"]].apply(pd.to_numeric, errors="coerce")
    null_count = int(dates.isna().sum() + numeric.isna().sum().sum())
    non_positive = int((numeric <= 0).any(axis=1).sum())
    schema_matches = list(normalized.columns) == NORMALIZED_COLUMNS
    passed = bool(
        schema_matches
        and not normalized.empty
        and duplicate_dates == 0
        and null_count == 0
        and non_positive == 0
        and len(normalized) >= 252
    )
    row.update(
        {
            "cache_available": path.exists(),
            "cache_status": "present_pass" if passed else "present_failed",
            "qa_status": "passed" if passed else "failed",
            "source_action": source_action,
            "first_date": dates.min().date().isoformat() if not dates.dropna().empty else "",
            "last_date": dates.max().date().isoformat() if not dates.dropna().empty else "",
            "row_count": int(len(normalized)),
            "valid_open_close_rows": int(numeric[["open", "close"]].notna().all(axis=1).sum()),
            "duplicate_dates": duplicate_dates,
            "non_positive_adjusted_price_count": non_positive,
            "schema_matches_normalized_daily_etf_data": schema_matches,
            "file_sha256": sha256_file(path) if path.exists() else "",
            "failure_code": "" if passed else "SOURCE_UNIVERSE_INCOMPLETE",
            "failure_reason": ""
            if passed
            else "schema, minimum rows, duplicate date, null price, or non-positive price QA failed",
        }
    )
    normalized["date"] = dates
    normalized = normalized.sort_values("date").drop_duplicates("date", keep="last")
    return normalized, row


def base_coverage_row(symbol: str, path: Path) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "country": COUNTRY_NAMES.get(symbol, "Project T-bill translation"),
        "role": "cash_translation" if symbol == CASH_SYMBOL else "source_country_etf",
        "required": True,
        "cache_path": str(path.resolve()),
        "cache_available": path.exists(),
        "cache_status": "missing",
        "qa_status": "failed",
        "source_action": "",
        "provider_api_called": False,
        "download_attempted": False,
        "first_date": "",
        "last_date": "",
        "row_count": 0,
        "valid_open_close_rows": 0,
        "missing_date_count_on_bil_calendar": "",
        "duplicate_dates": 0,
        "non_positive_adjusted_price_count": 0,
        "schema_matches_normalized_daily_etf_data": False,
        "file_sha256": "",
        "failure_code": "SOURCE_UNIVERSE_INCOMPLETE",
        "failure_reason": "cache file missing",
    }


def acquisition_row(
    symbol: str,
    source_action: str,
    provider_api_called: bool,
    download_attempted: bool,
    status: str,
    error: str,
) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "source_action": source_action,
        "provider_api_called": provider_api_called,
        "download_attempted": download_attempted,
        "status": status,
        "error": error,
        "timestamp_utc": now_utc(),
    }


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def indexed_frame(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out["date"] = pd.to_datetime(out["date"], errors="coerce").dt.tz_localize(None)
    out = out.dropna(subset=["date"]).sort_values("date").drop_duplicates("date", keep="last")
    return out.set_index("date", drop=False)


def classify_tom_calendar(dates: pd.DatetimeIndex | list[pd.Timestamp]) -> list[dict[str, Any]]:
    idx = pd.DatetimeIndex(pd.to_datetime(list(dates))).sort_values()
    groups: dict[pd.Period, list[pd.Timestamp]] = {}
    for date in idx:
        groups.setdefault(pd.Timestamp(date).to_period("M"), []).append(pd.Timestamp(date))

    rows: list[dict[str, Any]] = []
    for period in sorted(groups):
        month_dates = groups[period]
        month_len = len(month_dates)
        for offset, date in enumerate(month_dates):
            from_start = offset + 1
            from_end = month_len - offset
            if from_end == 1:
                label = TOM_DAY_MINUS_1
            elif from_start == 1:
                label = TOM_DAY_PLUS_1
            elif from_start == 2:
                label = TOM_DAY_PLUS_2
            elif from_start == 3:
                label = TOM_DAY_PLUS_3
            else:
                label = NON_TOM
            rows.append(
                {
                    "date": date.date().isoformat(),
                    "calendar_month": str(period),
                    "trading_day_number_from_start": from_start,
                    "trading_day_number_from_end": from_end,
                    "tom_status": label != NON_TOM,
                    "tom_day_label": label,
                }
            )
    return rows


def calendar_frame(calendar_rows: list[dict[str, Any]]) -> pd.DataFrame:
    frame = pd.DataFrame(calendar_rows)
    frame["date"] = pd.to_datetime(frame["date"])
    return frame.set_index("date", drop=False)


def registered_trials() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for cost in COST_LEVELS_BPS:
        for country in COUNTRY_ETFS:
            for method in COUNTRY_METHODS:
                rows.append(
                    {
                        "trial_id": trial_id(method, country, cost),
                        "method_id": method,
                        "country_symbol": country,
                        "country": COUNTRY_NAMES[country],
                        "cash_symbol": CASH_SYMBOL,
                        "cost_bps_per_side": cost,
                        "registered_before_performance": True,
                        "optional_management_overlay_count": 0,
                        "validation_or_promotion_status": "not_applicable_research_only",
                        "status": "REGISTERED",
                        "failure_code": "",
                        "failure_reason": "",
                    }
                )
        rows.append(
            {
                "trial_id": trial_id(METHOD_BIL, CASH_SYMBOL, cost),
                "method_id": METHOD_BIL,
                "country_symbol": "",
                "country": "Project T-bill translation",
                "cash_symbol": CASH_SYMBOL,
                "cost_bps_per_side": cost,
                "registered_before_performance": True,
                "optional_management_overlay_count": 0,
                "validation_or_promotion_status": "not_applicable_research_only",
                "status": "REGISTERED",
                "failure_code": "",
                "failure_reason": "",
            }
        )
    if len(rows) != EXPECTED_TRIAL_COUNT:
        raise AssertionError(f"registered trial count changed: {len(rows)}")
    return rows


def run_registered_trials(prices: PriceData, calendar_rows: list[dict[str, Any]]) -> dict[str, TrialPath]:
    paths: dict[str, TrialPath] = {}
    for cost in COST_LEVELS_BPS:
        for country in COUNTRY_ETFS:
            for method in COUNTRY_METHODS:
                tid = trial_id(method, country, cost)
                targets = target_weights_for_method(method, country, prices.calendar, calendar_rows)
                paths[tid] = simulate_trial(tid, method, country, cost, targets, prices, calendar_rows)
        tid = trial_id(METHOD_BIL, CASH_SYMBOL, cost)
        targets = target_weights_for_method(METHOD_BIL, CASH_SYMBOL, prices.calendar, calendar_rows)
        paths[tid] = simulate_trial(tid, METHOD_BIL, "", cost, targets, prices, calendar_rows)
    return paths


def target_weights_for_method(
    method_id: str,
    country_symbol: str,
    dates: pd.DatetimeIndex,
    calendar_rows: list[dict[str, Any]],
) -> pd.DataFrame:
    columns = trial_symbols(country_symbol)
    weights = pd.DataFrame(0.0, index=dates, columns=columns, dtype=float)
    cal = calendar_frame(calendar_rows)
    if method_id in {METHOD_TOM, METHOD_IDENTITY}:
        for date in dates:
            label = str(cal.loc[date, "tom_day_label"])
            if label in TOM_LABELS:
                weights.loc[date, country_symbol] = 1.0
            else:
                weights.loc[date, CASH_SYMBOL] = 1.0
        return weights
    if method_id == METHOD_BUY_HOLD:
        weights[country_symbol] = 1.0
        return weights
    if method_id == METHOD_EXPOSURE:
        for period, month_dates in month_groups(dates).items():
            equity_weight = 4.0 / float(len(month_dates))
            for date in month_dates:
                weights.loc[date, country_symbol] = equity_weight
                weights.loc[date, CASH_SYMBOL] = 1.0 - equity_weight
        return weights
    if method_id == METHOD_BIL:
        weights[CASH_SYMBOL] = 1.0
        return weights
    raise ValueError(f"unknown method_id: {method_id}")


def simulate_trial(
    trial_id_value: str,
    method_id: str,
    country_symbol: str,
    cost_bps_per_side: int,
    target_weights: pd.DataFrame,
    prices: PriceData,
    calendar_rows: list[dict[str, Any]],
) -> TrialPath:
    return simulate_trial_numpy(trial_id_value, method_id, country_symbol, cost_bps_per_side, target_weights, prices, calendar_rows)


def simulate_trial_numpy(
    trial_id_value: str,
    method_id: str,
    country_symbol: str,
    cost_bps_per_side: int,
    target_weights: pd.DataFrame,
    prices: PriceData,
    calendar_rows: list[dict[str, Any]],
) -> TrialPath:
    symbols = list(target_weights.columns)
    date_index = pd.DatetimeIndex(target_weights.index)
    date_iso = [pd.Timestamp(date).date().isoformat() for date in date_index]
    calendar_by_date = {row["date"]: row for row in calendar_rows}
    labels = [str(calendar_by_date[date]["tom_day_label"]) for date in date_iso]
    months = [str(pd.Timestamp(date).to_period("M")) for date in date_index]
    open_np = prices.open.loc[date_index, symbols].to_numpy(dtype=float)
    close_np = prices.close.loc[date_index, symbols].to_numpy(dtype=float)
    target_np = target_weights.to_numpy(dtype=float)
    cost_rate = float(cost_bps_per_side) / 10000.0

    shares = np.zeros(len(symbols), dtype=float)
    cash = START_NAV
    prior_close_prices: np.ndarray | None = None
    prior_close_nav = START_NAV
    previous_target = np.zeros(len(symbols), dtype=float)

    daily_rows: list[dict[str, Any]] = []
    order_rows: list[dict[str, Any]] = []
    fill_rows: list[dict[str, Any]] = []
    cost_rows: list[dict[str, Any]] = []
    component_rows: list[dict[str, Any]] = []

    for idx, date in enumerate(date_index):
        open_row = open_np[idx]
        close_row = close_np[idx]
        if np.isnan(open_row).any() or np.isnan(close_row).any():
            raise ValueError(f"{trial_id_value}: missing open/close on {date.date()}")

        previous_position_symbol = dominant_symbol_from_arrays(symbols, shares, prior_close_prices)
        overnight_pnl = float(np.dot(shares, open_row - prior_close_prices)) if prior_close_prices is not None else 0.0
        open_nav_before_trade = float(cash + np.dot(shares, open_row))
        if open_nav_before_trade <= 0 or not math.isfinite(open_nav_before_trade):
            raise ValueError(f"{trial_id_value}: invalid open NAV on {date.date()}")

        pre_trade_values = shares * open_row
        pre_trade_weights = pre_trade_values / open_nav_before_trade
        current_target = target_np[idx]
        target_changed = bool(idx == 0 or not np.allclose(current_target, previous_target, atol=TOL, rtol=0.0))
        gross_traded_notional = 0.0
        transaction_cost = 0.0
        orders_count = 0
        fills_count = 0
        signal_date = "PRE_EVALUATION_START" if idx == 0 else date_index[idx - 1].date().isoformat()
        signal_type = signal_type_for_target_change_arrays(method_id, symbols, previous_target, current_target, country_symbol)

        if target_changed:
            gross_traded_notional = float(open_nav_before_trade * np.abs(current_target - pre_trade_weights).sum())
            transaction_cost = gross_traded_notional * cost_rate
            nav_after_cost = open_nav_before_trade - transaction_cost
            if nav_after_cost <= 0:
                raise ValueError(f"{trial_id_value}: costs exhausted NAV on {date.date()}")
            desired_values = current_target * nav_after_cost
            deltas = desired_values - pre_trade_values
            for col, symbol in enumerate(symbols):
                delta_notional = float(deltas[col])
                if abs(delta_notional) <= 1e-8:
                    continue
                orders_count += 1
                fills_count += 1
                side = "BUY" if delta_notional > 0 else "SELL"
                shares_delta = delta_notional / float(open_row[col])
                order_rows.append(
                    {
                        "trial_id": trial_id_value,
                        "method_id": method_id,
                        "country_symbol": country_symbol,
                        "cost_bps_per_side": cost_bps_per_side,
                        "signal_date": signal_date,
                        "fill_date": date_iso[idx],
                        "symbol": symbol,
                        "side": side,
                        "target_weight": float(current_target[col]),
                        "pre_trade_weight": float(pre_trade_weights[col]),
                        "delta_notional": delta_notional,
                        "price_source": "next_open",
                        "signal_type": signal_type,
                    }
                )
                fill_rows.append(
                    {
                        "trial_id": trial_id_value,
                        "method_id": method_id,
                        "country_symbol": country_symbol,
                        "cost_bps_per_side": cost_bps_per_side,
                        "signal_date": signal_date,
                        "fill_date": date_iso[idx],
                        "symbol": symbol,
                        "side": side,
                        "shares_delta": float(shares_delta),
                        "fill_price": float(open_row[col]),
                        "price_source": "next_open",
                        "signal_type": signal_type,
                    }
                )
            shares = desired_values / open_row
            cash = float(nav_after_cost - desired_values.sum())
            if abs(cash) <= 1e-8:
                cash = 0.0

        intraday_pnl = float(np.dot(shares, close_row - open_row))
        close_values = shares * close_row
        close_nav = float(cash + close_values.sum())
        if close_nav <= 0 or not math.isfinite(close_nav):
            raise ValueError(f"{trial_id_value}: invalid close NAV on {date.date()}")
        daily_return = close_nav / prior_close_nav - 1.0
        label = labels[idx]
        current_position_symbol = dominant_symbol_from_arrays(symbols, shares, close_row)
        source_component = source_component_flag(method_id, label, previous_position_symbol, current_position_symbol)
        overnight_contribution = overnight_pnl / prior_close_nav if prior_close_nav else 0.0
        open_to_close_contribution = intraday_pnl / prior_close_nav if prior_close_nav else 0.0
        cost_contribution = -transaction_cost / prior_close_nav if prior_close_nav else 0.0
        total_component = overnight_contribution + open_to_close_contribution + cost_contribution
        end_weights = close_values / close_nav
        country_idx = symbols.index(country_symbol) if country_symbol in symbols else -1
        bil_idx = symbols.index(CASH_SYMBOL) if CASH_SYMBOL in symbols else -1
        country_weight = float(end_weights[country_idx]) if country_idx >= 0 else 0.0
        bil_weight = float(end_weights[bil_idx]) if bil_idx >= 0 else 0.0
        target_country = float(current_target[country_idx]) if country_idx >= 0 else 0.0
        target_bil = float(current_target[bil_idx]) if bil_idx >= 0 else 0.0
        shares_country = float(shares[country_idx]) if country_idx >= 0 else 0.0
        shares_bil = float(shares[bil_idx]) if bil_idx >= 0 else 0.0
        gross_pct = gross_traded_notional / open_nav_before_trade if open_nav_before_trade else 0.0
        cost_ret = transaction_cost / prior_close_nav if prior_close_nav else 0.0

        daily_rows.append(
            {
                "trial_id": trial_id_value,
                "method_id": method_id,
                "country_symbol": country_symbol,
                "country": COUNTRY_NAMES.get(country_symbol, ""),
                "cost_bps_per_side": cost_bps_per_side,
                "date": date_iso[idx],
                "calendar_month": months[idx],
                "tom_day_label": label,
                "tom_status": label in TOM_LABELS,
                "target_country_weight": target_country,
                "target_bil_weight": target_bil,
                "country_weight": country_weight,
                "bil_weight": bil_weight,
                "cash_weight": float(cash / close_nav),
                "shares_country": shares_country,
                "shares_bil": shares_bil,
                "nav": close_nav,
                "daily_return": float(daily_return),
                "orders_count": orders_count,
                "fills_count": fills_count,
                "target_changed_at_open": target_changed,
                "gross_traded_notional": gross_traded_notional,
                "gross_traded_notional_pct": gross_pct,
                "one_way_turnover": 0.5 * gross_pct,
                "modeled_cost_dollars": transaction_cost,
                "transaction_cost_return": cost_ret,
                "overnight_contribution": overnight_contribution,
                "entry_overnight_contribution": overnight_contribution if signal_type == "entry" else 0.0,
                "open_to_close_contribution": open_to_close_contribution,
                "source_window_component_return": total_component if source_component else 0.0,
                "non_tom_component_return": 0.0 if source_component else total_component,
                "delayed_entry": False,
                "failed_entry": False,
                "delayed_exit": False,
                "failed_exit": False,
            }
        )
        cost_rows.append(
            {
                "trial_id": trial_id_value,
                "method_id": method_id,
                "country_symbol": country_symbol,
                "cost_bps_per_side": cost_bps_per_side,
                "date": date_iso[idx],
                "is_execution_date": target_changed,
                "gross_traded_notional": gross_traded_notional,
                "gross_traded_notional_pct": gross_pct,
                "one_way_turnover": 0.5 * gross_pct,
                "transaction_cost_return": cost_ret,
                "modeled_cost_dollars": transaction_cost,
                "orders_count": orders_count,
                "fills_count": fills_count,
                "expected_transaction_cost_return": (gross_traded_notional / prior_close_nav) * cost_rate
                if prior_close_nav
                else 0.0,
            }
        )
        component_rows.append(
            {
                "trial_id": trial_id_value,
                "method_id": method_id,
                "country_symbol": country_symbol,
                "cost_bps_per_side": cost_bps_per_side,
                "date": date_iso[idx],
                "calendar_month": months[idx],
                "tom_day_label": label,
                "source_component": source_component,
                "previous_position_symbol": previous_position_symbol,
                "current_position_symbol": current_position_symbol,
                "overnight_contribution": overnight_contribution,
                "entry_overnight_contribution": overnight_contribution if signal_type == "entry" else 0.0,
                "open_to_close_contribution": open_to_close_contribution,
                "cost_contribution": cost_contribution,
                "total_component_return": total_component,
                "daily_return": float(daily_return),
            }
        )

        prior_close_prices = close_row
        prior_close_nav = close_nav
        previous_target = current_target.copy()

    daily_frame = pd.DataFrame(daily_rows)
    orders_frame = pd.DataFrame(order_rows)
    fills_frame = pd.DataFrame(fill_rows)
    costs_frame = pd.DataFrame(cost_rows)
    components_frame = pd.DataFrame(component_rows)
    end_weights = daily_frame.set_index(pd.to_datetime(daily_frame["date"]))[
        ["country_weight", "bil_weight", "cash_weight"]
    ].copy()
    end_weights.columns = [country_symbol or "country_weight", CASH_SYMBOL, "cash"]
    nav = pd.Series(daily_frame["nav"].to_numpy(dtype=float), index=pd.to_datetime(daily_frame["date"]), name="nav")
    cash_series = pd.Series(daily_frame["cash_weight"].to_numpy(dtype=float) * nav.to_numpy(), index=nav.index, name="cash")
    daily_returns = pd.Series(
        daily_frame["daily_return"].to_numpy(dtype=float),
        index=pd.to_datetime(daily_frame["date"]),
        name="daily_return",
    )
    state = fast_state_hash(
        target_weights,
        end_weights,
        nav,
        cash_series,
        economic_cost_frame(costs_frame),
    )
    economic_state = fast_state_hash(
        target_weights,
        end_weights,
        nav,
        cash_series,
        economic_order_frame(orders_frame),
        economic_fill_frame(fills_frame),
        economic_cost_frame(costs_frame),
    )
    return TrialPath(
        trial_id=trial_id_value,
        method_id=method_id,
        country_symbol=country_symbol,
        cost_bps_per_side=cost_bps_per_side,
        target_weights=target_weights.copy(),
        end_weights=end_weights,
        nav=nav,
        cash=cash_series,
        daily_returns=daily_returns,
        orders=orders_frame,
        fills=fills_frame,
        daily_positions=daily_frame,
        component_returns=components_frame,
        costs=costs_frame,
        state_hash=state,
        economic_state_hash=economic_state,
    )


def dominant_symbol_from_arrays(symbols: list[str], shares: np.ndarray, prices: np.ndarray | None) -> str:
    if prices is None:
        return ""
    values = np.abs(shares * prices)
    if values.size == 0 or float(values.max()) <= TOL:
        return ""
    return symbols[int(values.argmax())]


def signal_type_for_target_change_arrays(
    method_id: str,
    symbols: list[str],
    previous_target: np.ndarray,
    current_target: np.ndarray,
    country_symbol: str,
) -> str:
    if method_id not in {METHOD_TOM, METHOD_IDENTITY} or country_symbol not in symbols:
        return "rebalance"
    idx = symbols.index(country_symbol)
    if float(current_target[idx]) > float(previous_target[idx]):
        return "entry"
    if float(current_target[idx]) < float(previous_target[idx]):
        return "exit"
    return "rebalance"


def fast_state_hash(*parts: Any) -> str:
    digest = hashlib.sha256()
    for part in parts:
        if isinstance(part, pd.DataFrame):
            payload = part.copy()
            for column in payload.columns:
                if pd.api.types.is_numeric_dtype(payload[column]):
                    payload[column] = payload[column].astype(float).round(12)
            digest.update(payload.to_csv(index=True, lineterminator="\n").encode("utf-8"))
        elif isinstance(part, pd.Series):
            payload = part.astype(float).round(12).to_frame("value")
            digest.update(payload.to_csv(index=True, lineterminator="\n").encode("utf-8"))
        else:
            digest.update(json.dumps(jsonable(part), sort_keys=True).encode("utf-8"))
        digest.update(b"\n--part--\n")
    return "sha256:" + digest.hexdigest()


def simulate_trial_pandas_reference(
    trial_id_value: str,
    method_id: str,
    country_symbol: str,
    cost_bps_per_side: int,
    target_weights: pd.DataFrame,
    prices: PriceData,
    calendar_rows: list[dict[str, Any]],
) -> TrialPath:
    symbols = list(target_weights.columns)
    open_prices = prices.open[symbols]
    close_prices = prices.close[symbols]
    cost_rate = float(cost_bps_per_side) / 10000.0
    cal = calendar_frame(calendar_rows)

    shares = pd.Series(0.0, index=symbols, dtype=float)
    cash = START_NAV
    prior_close_prices: pd.Series | None = None
    prior_close_nav = START_NAV
    previous_target = pd.Series(0.0, index=symbols, dtype=float)

    daily_rows: list[dict[str, Any]] = []
    order_rows: list[dict[str, Any]] = []
    fill_rows: list[dict[str, Any]] = []
    cost_rows: list[dict[str, Any]] = []
    component_rows: list[dict[str, Any]] = []

    date_list = list(pd.DatetimeIndex(target_weights.index))
    for idx, date in enumerate(date_list):
        open_row = open_prices.loc[date].astype(float)
        close_row = close_prices.loc[date].astype(float)
        if open_row.isna().any() or close_row.isna().any():
            raise ValueError(f"{trial_id_value}: missing open/close on {date.date()}")

        previous_position_symbol = dominant_symbol(shares, prior_close_prices) if prior_close_prices is not None else ""
        overnight_pnl = 0.0
        if prior_close_prices is not None:
            overnight_pnl = float((shares * (open_row - prior_close_prices)).sum())
        open_nav_before_trade = float(cash + (shares * open_row).sum())
        if open_nav_before_trade <= 0 or not math.isfinite(open_nav_before_trade):
            raise ValueError(f"{trial_id_value}: invalid open NAV on {date.date()}")

        pre_trade_values = shares * open_row
        pre_trade_weights = pre_trade_values / open_nav_before_trade
        current_target = target_weights.loc[date].astype(float)
        target_changed = bool(idx == 0 or not np.allclose(current_target.to_numpy(), previous_target.to_numpy(), atol=TOL, rtol=0.0))
        gross_traded_notional = 0.0
        transaction_cost = 0.0
        orders_count = 0
        fills_count = 0
        signal_date = signal_date_for_execution(date, idx, date_list, method_id, cal)
        signal_type = signal_type_for_target_change(method_id, previous_target, current_target, country_symbol)

        if target_changed:
            gross_traded_notional = float(open_nav_before_trade * np.abs(current_target - pre_trade_weights).sum())
            transaction_cost = gross_traded_notional * cost_rate
            nav_after_cost = open_nav_before_trade - transaction_cost
            if nav_after_cost <= 0:
                raise ValueError(f"{trial_id_value}: costs exhausted NAV on {date.date()}")
            desired_values = current_target * nav_after_cost
            deltas = desired_values - pre_trade_values
            for symbol in symbols:
                delta_notional = float(deltas[symbol])
                if abs(delta_notional) <= 1e-8:
                    continue
                orders_count += 1
                side = "BUY" if delta_notional > 0 else "SELL"
                quantity = delta_notional / float(open_row[symbol])
                order_rows.append(
                    {
                        "trial_id": trial_id_value,
                        "method_id": method_id,
                        "country_symbol": country_symbol,
                        "cost_bps_per_side": cost_bps_per_side,
                        "signal_date": signal_date,
                        "fill_date": date.date().isoformat(),
                        "symbol": symbol,
                        "side": side,
                        "target_weight": float(current_target[symbol]),
                        "pre_trade_weight": float(pre_trade_weights[symbol]),
                        "delta_notional": delta_notional,
                        "price_source": "next_open",
                        "signal_type": signal_type,
                    }
                )
                fill_rows.append(
                    {
                        "trial_id": trial_id_value,
                        "method_id": method_id,
                        "country_symbol": country_symbol,
                        "cost_bps_per_side": cost_bps_per_side,
                        "signal_date": signal_date,
                        "fill_date": date.date().isoformat(),
                        "symbol": symbol,
                        "side": side,
                        "shares_delta": float(quantity),
                        "fill_price": float(open_row[symbol]),
                        "price_source": "next_open",
                        "signal_type": signal_type,
                    }
                )
                fills_count += 1
            shares = desired_values / open_row
            cash = float(nav_after_cost - desired_values.sum())
            if abs(cash) <= 1e-8:
                cash = 0.0

        intraday_pnl = float((shares * (close_row - open_row)).sum())
        close_values = shares * close_row
        close_nav = float(cash + close_values.sum())
        if close_nav <= 0 or not math.isfinite(close_nav):
            raise ValueError(f"{trial_id_value}: invalid close NAV on {date.date()}")
        daily_return = close_nav / prior_close_nav - 1.0
        label = str(cal.loc[date, "tom_day_label"])
        current_position_symbol = dominant_symbol(shares, close_row)
        source_component = source_component_flag(method_id, label, previous_position_symbol, current_position_symbol)
        overnight_contribution = overnight_pnl / prior_close_nav if prior_close_nav else 0.0
        open_to_close_contribution = intraday_pnl / prior_close_nav if prior_close_nav else 0.0
        cost_contribution = -transaction_cost / prior_close_nav if prior_close_nav else 0.0
        total_component = overnight_contribution + open_to_close_contribution + cost_contribution

        end_weights = close_values / close_nav
        daily_payload = {
            "trial_id": trial_id_value,
            "method_id": method_id,
            "country_symbol": country_symbol,
            "country": COUNTRY_NAMES.get(country_symbol, ""),
            "cost_bps_per_side": cost_bps_per_side,
            "date": date.date().isoformat(),
            "calendar_month": str(pd.Timestamp(date).to_period("M")),
            "tom_day_label": label,
            "tom_status": label in TOM_LABELS,
            "target_country_weight": float(current_target.get(country_symbol, 0.0)) if country_symbol else 0.0,
            "target_bil_weight": float(current_target.get(CASH_SYMBOL, 0.0)),
            "country_weight": float(end_weights.get(country_symbol, 0.0)) if country_symbol else 0.0,
            "bil_weight": float(end_weights.get(CASH_SYMBOL, 0.0)),
            "cash_weight": float(cash / close_nav),
            "shares_country": float(shares.get(country_symbol, 0.0)) if country_symbol else 0.0,
            "shares_bil": float(shares.get(CASH_SYMBOL, 0.0)),
            "nav": close_nav,
            "daily_return": float(daily_return),
            "orders_count": orders_count,
            "fills_count": fills_count,
            "target_changed_at_open": target_changed,
            "gross_traded_notional": gross_traded_notional,
            "gross_traded_notional_pct": gross_traded_notional / open_nav_before_trade if open_nav_before_trade else 0.0,
            "one_way_turnover": 0.5 * gross_traded_notional / open_nav_before_trade if open_nav_before_trade else 0.0,
            "modeled_cost_dollars": transaction_cost,
            "transaction_cost_return": transaction_cost / prior_close_nav if prior_close_nav else 0.0,
            "overnight_contribution": overnight_contribution,
            "entry_overnight_contribution": overnight_contribution if signal_type == "entry" else 0.0,
            "open_to_close_contribution": open_to_close_contribution,
            "source_window_component_return": total_component if source_component else 0.0,
            "non_tom_component_return": 0.0 if source_component else total_component,
            "delayed_entry": False,
            "failed_entry": False,
            "delayed_exit": False,
            "failed_exit": False,
        }
        daily_rows.append(daily_payload)
        cost_rows.append(
            {
                "trial_id": trial_id_value,
                "method_id": method_id,
                "country_symbol": country_symbol,
                "cost_bps_per_side": cost_bps_per_side,
                "date": date.date().isoformat(),
                "is_execution_date": target_changed,
                "gross_traded_notional": gross_traded_notional,
                "gross_traded_notional_pct": gross_traded_notional / open_nav_before_trade if open_nav_before_trade else 0.0,
                "one_way_turnover": 0.5 * gross_traded_notional / open_nav_before_trade if open_nav_before_trade else 0.0,
                "transaction_cost_return": transaction_cost / prior_close_nav if prior_close_nav else 0.0,
                "modeled_cost_dollars": transaction_cost,
                "orders_count": orders_count,
                "fills_count": fills_count,
                "expected_transaction_cost_return": (gross_traded_notional / prior_close_nav) * cost_rate
                if prior_close_nav
                else 0.0,
            }
        )
        component_rows.append(
            {
                "trial_id": trial_id_value,
                "method_id": method_id,
                "country_symbol": country_symbol,
                "cost_bps_per_side": cost_bps_per_side,
                "date": date.date().isoformat(),
                "calendar_month": str(pd.Timestamp(date).to_period("M")),
                "tom_day_label": label,
                "source_component": source_component,
                "previous_position_symbol": previous_position_symbol,
                "current_position_symbol": current_position_symbol,
                "overnight_contribution": overnight_contribution,
                "entry_overnight_contribution": overnight_contribution if signal_type == "entry" else 0.0,
                "open_to_close_contribution": open_to_close_contribution,
                "cost_contribution": cost_contribution,
                "total_component_return": total_component,
                "daily_return": float(daily_return),
            }
        )

        prior_close_prices = close_row
        prior_close_nav = close_nav
        previous_target = current_target

    daily_frame = pd.DataFrame(daily_rows)
    orders_frame = pd.DataFrame(order_rows)
    fills_frame = pd.DataFrame(fill_rows)
    costs_frame = pd.DataFrame(cost_rows)
    components_frame = pd.DataFrame(component_rows)
    end_weights = daily_frame.set_index(pd.to_datetime(daily_frame["date"]))[
        ["country_weight", "bil_weight", "cash_weight"]
    ].copy()
    end_weights.columns = [country_symbol or "country_weight", CASH_SYMBOL, "cash"]
    nav = pd.Series(daily_frame["nav"].to_numpy(dtype=float), index=pd.to_datetime(daily_frame["date"]), name="nav")
    cash_series = pd.Series(daily_frame["cash_weight"].to_numpy(dtype=float) * nav.to_numpy(), index=nav.index, name="cash")
    daily_returns = pd.Series(
        daily_frame["daily_return"].to_numpy(dtype=float),
        index=pd.to_datetime(daily_frame["date"]),
        name="daily_return",
    )
    target = target_weights.copy()
    state = state_hash_payload(
        target_weights=target,
        end_weights=end_weights,
        nav=nav,
        cash=cash_series,
        costs=costs_frame[["date", "gross_traded_notional_pct", "transaction_cost_return", "orders_count", "fills_count"]],
    )
    economic_state = state_hash_payload(
        target_weights=target,
        end_weights=end_weights,
        nav=nav,
        cash=cash_series,
        orders=economic_order_frame(orders_frame),
        fills=economic_fill_frame(fills_frame),
        costs=costs_frame[["date", "gross_traded_notional_pct", "transaction_cost_return", "orders_count", "fills_count"]],
    )
    return TrialPath(
        trial_id=trial_id_value,
        method_id=method_id,
        country_symbol=country_symbol,
        cost_bps_per_side=cost_bps_per_side,
        target_weights=target,
        end_weights=end_weights,
        nav=nav,
        cash=cash_series,
        daily_returns=daily_returns,
        orders=orders_frame,
        fills=fills_frame,
        daily_positions=daily_frame,
        component_returns=components_frame,
        costs=costs_frame,
        state_hash=state,
        economic_state_hash=economic_state,
    )


def signal_date_for_execution(
    date: pd.Timestamp,
    idx: int,
    dates: list[pd.Timestamp],
    method_id: str,
    cal: pd.DataFrame,
) -> str:
    if idx == 0:
        return "PRE_EVALUATION_START"
    previous = dates[idx - 1]
    if method_id in {METHOD_TOM, METHOD_IDENTITY} and str(cal.loc[date, "tom_day_label"]) == TOM_DAY_MINUS_1:
        return previous.date().isoformat()
    return previous.date().isoformat()


def signal_type_for_target_change(
    method_id: str,
    previous_target: pd.Series,
    current_target: pd.Series,
    country_symbol: str,
) -> str:
    if method_id not in {METHOD_TOM, METHOD_IDENTITY} or not country_symbol:
        return "rebalance"
    previous_country = float(previous_target.get(country_symbol, 0.0))
    current_country = float(current_target.get(country_symbol, 0.0))
    if current_country > previous_country:
        return "entry"
    if current_country < previous_country:
        return "exit"
    return "rebalance"


def source_component_flag(
    method_id: str,
    tom_label: str,
    previous_position_symbol: str,
    current_position_symbol: str,
) -> bool:
    if method_id not in {METHOD_TOM, METHOD_IDENTITY}:
        return tom_label in TOM_LABELS
    if tom_label in TOM_LABELS and current_position_symbol != CASH_SYMBOL:
        return True
    # The source position is held overnight after DAY_PLUS_3 and exits at DAY_PLUS_4 open.
    return tom_label == NON_TOM and previous_position_symbol not in {"", CASH_SYMBOL} and current_position_symbol == CASH_SYMBOL


def dominant_symbol(shares: pd.Series, prices: pd.Series | None) -> str:
    if prices is None:
        return ""
    values = (shares * prices).abs()
    if values.empty or float(values.max()) <= TOL:
        return ""
    return str(values.idxmax())


def trial_symbols(country_symbol: str) -> list[str]:
    if country_symbol == CASH_SYMBOL:
        return [CASH_SYMBOL]
    return [country_symbol, CASH_SYMBOL]


def trial_id(method_id: str, country_symbol: str, cost_bps: int) -> str:
    if method_id == METHOD_BIL:
        return f"{ARTIFACT_ID}__{METHOD_BIL}__cost{cost_bps:02d}bps"
    return f"{ARTIFACT_ID}__{country_symbol}__{method_id}__cost{cost_bps:02d}bps"


def month_groups(dates: pd.DatetimeIndex) -> dict[pd.Period, list[pd.Timestamp]]:
    groups: dict[pd.Period, list[pd.Timestamp]] = {}
    for date in dates:
        groups.setdefault(pd.Timestamp(date).to_period("M"), []).append(pd.Timestamp(date))
    return groups


def identity_equivalence_rows(paths: dict[str, TrialPath]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for cost in COST_LEVELS_BPS:
        for country in COUNTRY_ETFS:
            source = paths[trial_id(METHOD_TOM, country, cost)]
            identity = paths[trial_id(METHOD_IDENTITY, country, cost)]
            checks = {
                "signals_equal": economic_order_frame(source.orders).equals(economic_order_frame(identity.orders)),
                "tom_labels_equal": list(source.daily_positions["tom_day_label"]) == list(identity.daily_positions["tom_day_label"]),
                "target_weights_equal": frame_equal(source.target_weights, identity.target_weights),
                "orders_equal": economic_order_frame(source.orders).equals(economic_order_frame(identity.orders)),
                "fills_equal": economic_fill_frame(source.fills).equals(economic_fill_frame(identity.fills)),
                "daily_positions_equal": frame_equal(source.end_weights, identity.end_weights),
                "daily_cash_equal": series_equal(source.cash, identity.cash),
                "daily_nav_equal": series_equal(source.nav, identity.nav),
                "costs_equal": economic_cost_frame(source.costs).equals(economic_cost_frame(identity.costs)),
                "complete_state_hash_equal": source.economic_state_hash == identity.economic_state_hash,
                "final_metrics_equal": abs(float(source.nav.iloc[-1]) - float(identity.nav.iloc[-1])) <= TOL,
            }
            passed = all(checks.values())
            row = {
                "country_symbol": country,
                "country": COUNTRY_NAMES[country],
                "cost_bps_per_side": cost,
                **checks,
                "tom_state_hash": source.economic_state_hash,
                "identity_state_hash": identity.economic_state_hash,
                "equivalence_status": "PASS" if passed else "FAIL",
            }
            rows.append(row)
            if not passed:
                failures.append(
                    failure_row(
                        trial_id=identity.trial_id,
                        date="",
                        symbol=country,
                        failure_code="IDENTITY_EQUIVALENCE_FAILED",
                        detail=json.dumps(checks, sort_keys=True),
                    )
                )
    return rows, failures


def economic_order_frame(frame: pd.DataFrame) -> pd.DataFrame:
    fields = [
        "signal_date",
        "fill_date",
        "symbol",
        "side",
        "target_weight",
        "pre_trade_weight",
        "delta_notional",
        "price_source",
        "signal_type",
    ]
    return comparable_frame(frame, fields)


def economic_fill_frame(frame: pd.DataFrame) -> pd.DataFrame:
    fields = ["signal_date", "fill_date", "symbol", "side", "shares_delta", "fill_price", "price_source", "signal_type"]
    return comparable_frame(frame, fields)


def economic_cost_frame(frame: pd.DataFrame) -> pd.DataFrame:
    fields = ["date", "gross_traded_notional_pct", "transaction_cost_return", "orders_count", "fills_count"]
    return comparable_frame(frame, fields)


def comparable_frame(frame: pd.DataFrame, fields: list[str]) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=fields)
    out = frame[fields].copy()
    for column in out.columns:
        if pd.api.types.is_numeric_dtype(out[column]):
            out[column] = out[column].astype(float).round(12)
    return out.reset_index(drop=True)


def metrics_for_all_paths(
    paths: dict[str, TrialPath],
    prices: PriceData,
    calendar_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in paths.values():
        rows.append(metric_row(path, row_type="trial", aggregate_component_count=1))
    rows.extend(aggregate_metric_rows(paths, prices))
    add_control_deltas(rows)
    return rows


def metric_row(path: TrialPath, *, row_type: str, aggregate_component_count: int) -> dict[str, Any]:
    returns = path.daily_returns.astype(float)
    nav = path.nav.astype(float)
    years = max((nav.index[-1] - nav.index[0]).days / 365.25, 1e-9)
    total_return = float(nav.iloc[-1] / START_NAV - 1.0)
    annualized_return = float((nav.iloc[-1] / START_NAV) ** (1.0 / years) - 1.0)
    annualized_volatility = float(returns.std(ddof=1) * math.sqrt(252.0)) if len(returns) > 1 else float("nan")
    max_dd, dd_duration = max_drawdown_and_duration(nav)
    sharpe = float(math.sqrt(252.0) * returns.mean() / returns.std(ddof=1)) if returns.std(ddof=1) > 0 else float("nan")
    downside = returns[returns < 0]
    sortino = float(math.sqrt(252.0) * returns.mean() / downside.std(ddof=1)) if len(downside) > 1 and downside.std(ddof=1) > 0 else float("nan")
    costs = path.costs
    positions = path.daily_positions
    components = path.component_returns
    return {
        "row_type": row_type,
        "trial_id": path.trial_id,
        "method_id": path.method_id,
        "country_symbol": path.country_symbol,
        "country": COUNTRY_NAMES.get(path.country_symbol, ""),
        "cost_bps_per_side": path.cost_bps_per_side,
        "initial_nav": START_NAV,
        "terminal_nav": float(nav.iloc[-1]),
        "total_return": total_return,
        "annualized_return": annualized_return,
        "annualized_volatility": annualized_volatility,
        "maximum_drawdown": max_dd,
        "drawdown_duration_days": dd_duration,
        "sharpe": sharpe,
        "sortino": sortino,
        "return_to_drawdown": annualized_return / abs(max_dd) if max_dd < 0 else float("nan"),
        "worst_daily_return": float(returns.min()),
        "expected_shortfall_95": expected_shortfall(returns, 0.95),
        "average_equity_exposure": float(positions["country_weight"].mean()) if "country_weight" in positions else 0.0,
        "average_bil_exposure": float(positions["bil_weight"].mean()) if "bil_weight" in positions else 0.0,
        "turnover": float(costs["one_way_turnover"].sum()) if not costs.empty else 0.0,
        "gross_traded_notional": float(costs["gross_traded_notional_pct"].sum()) if not costs.empty else 0.0,
        "orders": int(costs["orders_count"].sum()) if not costs.empty else 0,
        "fills": int(costs["fills_count"].sum()) if not costs.empty else 0,
        "modeled_costs": float(costs["modeled_cost_dollars"].sum()) if not costs.empty else 0.0,
        "tom_return": float(components["total_component_return"].where(components["source_component"], 0.0).sum())
        if not components.empty
        else 0.0,
        "non_tom_return": float(components["total_component_return"].where(~components["source_component"], 0.0).sum())
        if not components.empty
        else 0.0,
        "entry_overnight_contribution": float(components["entry_overnight_contribution"].sum()) if not components.empty else 0.0,
        "open_to_close_contribution": float(components["open_to_close_contribution"].sum()) if not components.empty else 0.0,
        "completed_tom_episodes": completed_episode_count(path.daily_positions),
        "delayed_entries": int(positions["delayed_entry"].sum()) if "delayed_entry" in positions else 0,
        "failed_entries": int(positions["failed_entry"].sum()) if "failed_entry" in positions else 0,
        "delayed_exits": int(positions["delayed_exit"].sum()) if "delayed_exit" in positions else 0,
        "failed_exits": int(positions["failed_exit"].sum()) if "failed_exit" in positions else 0,
        "state_hash": path.economic_state_hash,
        "aggregate_component_count": aggregate_component_count,
        "validation_status": "not_validation",
        "promotion_status": "not_promoted",
        "paper_demo_live_status": "not_invoked",
    }


def aggregate_metric_rows(paths: dict[str, TrialPath], prices: PriceData) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for cost in COST_LEVELS_BPS:
        for method in (METHOD_TOM, METHOD_EXPOSURE):
            selected = [paths[trial_id(method, country, cost)] for country in COUNTRY_ETFS]
            returns = pd.concat([path.daily_returns.rename(path.country_symbol) for path in selected], axis=1).mean(axis=1)
            nav = START_NAV * (1.0 + returns).cumprod()
            components = pd.concat([path.component_returns for path in selected], ignore_index=True)
            avg_positions = pd.concat([path.daily_positions for path in selected], ignore_index=True)
            costs = pd.concat([path.costs for path in selected], ignore_index=True)
            aggregate_path = TrialPath(
                trial_id=f"{ARTIFACT_ID}__AGGREGATE_EQUAL_WEIGHT_9_COUNTRIES__{method}__cost{cost:02d}bps",
                method_id=f"AGGREGATE_EQUAL_WEIGHT_9_COUNTRIES_{method}",
                country_symbol="",
                cost_bps_per_side=cost,
                target_weights=pd.DataFrame(index=prices.calendar),
                end_weights=pd.DataFrame(index=prices.calendar),
                nav=nav,
                cash=pd.Series(dtype=float),
                daily_returns=returns,
                orders=pd.DataFrame(),
                fills=pd.DataFrame(),
                daily_positions=pd.DataFrame(
                    {
                        "country_weight": avg_positions.groupby("date")["country_weight"].mean().to_numpy(),
                        "bil_weight": avg_positions.groupby("date")["bil_weight"].mean().to_numpy(),
                    },
                    index=pd.to_datetime(sorted(avg_positions["date"].unique())),
                ),
                component_returns=components,
                costs=costs,
                state_hash=stable_hash(series_payload(nav)),
                economic_state_hash=stable_hash(series_payload(nav)),
            )
            rows.append(metric_row(aggregate_path, row_type="aggregate_reporting", aggregate_component_count=9))
    return rows


def add_control_deltas(rows: list[dict[str, Any]]) -> None:
    lookup = {(row["method_id"], row["country_symbol"], int(row["cost_bps_per_side"])): row for row in rows}
    for row in rows:
        row["total_return_delta_vs_exposure_matched_control"] = ""
        row["annualized_return_delta_vs_exposure_matched_control"] = ""
        row["sharpe_delta_vs_exposure_matched_control"] = ""
        row["return_to_drawdown_delta_vs_exposure_matched_control"] = ""
        if row["method_id"] == METHOD_TOM:
            control = lookup.get((METHOD_EXPOSURE, row["country_symbol"], int(row["cost_bps_per_side"])))
        elif str(row["method_id"]).startswith("AGGREGATE_EQUAL_WEIGHT_9_COUNTRIES_TOM_SOURCE"):
            control = lookup.get((f"AGGREGATE_EQUAL_WEIGHT_9_COUNTRIES_{METHOD_EXPOSURE}", "", int(row["cost_bps_per_side"])))
        else:
            control = None
        if control is None:
            continue
        for metric_name, field_name in (
            ("total_return", "total_return_delta_vs_exposure_matched_control"),
            ("annualized_return", "annualized_return_delta_vs_exposure_matched_control"),
            ("sharpe", "sharpe_delta_vs_exposure_matched_control"),
            ("return_to_drawdown", "return_to_drawdown_delta_vs_exposure_matched_control"),
        ):
            row[field_name] = safe_float(row[metric_name]) - safe_float(control[metric_name])


def subperiod_metrics(paths: dict[str, TrialPath], prices: PriceData) -> list[dict[str, Any]]:
    blocks = five_year_blocks(prices.common_start, prices.common_end)
    rows: list[dict[str, Any]] = []
    aggregate_returns = aggregate_returns_by_method(paths)
    for block_id, block in enumerate(blocks, start=1):
        start = pd.Timestamp(block["start_date"])
        end = pd.Timestamp(block["end_date"])
        for path in paths.values():
            rows.append(subperiod_metric_row(path.trial_id, path.method_id, path.country_symbol, path.cost_bps_per_side, path.daily_returns, start, end, block_id))
        for key, returns in aggregate_returns.items():
            method, cost = key
            rows.append(subperiod_metric_row(
                f"{ARTIFACT_ID}__AGGREGATE_EQUAL_WEIGHT_9_COUNTRIES__{method}__cost{cost:02d}bps",
                f"AGGREGATE_EQUAL_WEIGHT_9_COUNTRIES_{method}",
                "",
                cost,
                returns,
                start,
                end,
                block_id,
            ))
    add_subperiod_control_deltas(rows)
    return rows


def subperiod_metric_row(
    trial_id_value: str,
    method_id: str,
    country_symbol: str,
    cost: int,
    returns: pd.Series,
    start: pd.Timestamp,
    end: pd.Timestamp,
    block_id: int,
) -> dict[str, Any]:
    subset = returns.loc[(returns.index >= start) & (returns.index <= end)].copy()
    if subset.empty:
        return {
            "block_id": block_id,
            "block_start": start.date().isoformat(),
            "block_end": end.date().isoformat(),
            "trial_id": trial_id_value,
            "method_id": method_id,
            "country_symbol": country_symbol,
            "cost_bps_per_side": cost,
            "date_count": 0,
            "total_return": "",
            "annualized_return": "",
            "annualized_volatility": "",
            "maximum_drawdown": "",
            "sharpe": "",
            "delta_vs_exposure_matched_control": "",
        }
    nav = START_NAV * (1.0 + subset).cumprod()
    years = max((subset.index[-1] - subset.index[0]).days / 365.25, 1e-9)
    total_return = float(nav.iloc[-1] / START_NAV - 1.0)
    ann = float((nav.iloc[-1] / START_NAV) ** (1.0 / years) - 1.0)
    vol = float(subset.std(ddof=1) * math.sqrt(252.0)) if len(subset) > 1 else float("nan")
    max_dd, _ = max_drawdown_and_duration(nav)
    sharpe = float(math.sqrt(252.0) * subset.mean() / subset.std(ddof=1)) if subset.std(ddof=1) > 0 else float("nan")
    return {
        "block_id": block_id,
        "block_start": start.date().isoformat(),
        "block_end": end.date().isoformat(),
        "trial_id": trial_id_value,
        "method_id": method_id,
        "country_symbol": country_symbol,
        "cost_bps_per_side": cost,
        "date_count": int(len(subset)),
        "total_return": total_return,
        "annualized_return": ann,
        "annualized_volatility": vol,
        "maximum_drawdown": max_dd,
        "sharpe": sharpe,
        "delta_vs_exposure_matched_control": "",
    }


def add_subperiod_control_deltas(rows: list[dict[str, Any]]) -> None:
    lookup = {
        (row["block_id"], row["method_id"], row["country_symbol"], int(row["cost_bps_per_side"])): row
        for row in rows
    }
    for row in rows:
        if row["method_id"] == METHOD_TOM:
            control = lookup.get((row["block_id"], METHOD_EXPOSURE, row["country_symbol"], int(row["cost_bps_per_side"])))
        elif str(row["method_id"]).startswith("AGGREGATE_EQUAL_WEIGHT_9_COUNTRIES_TOM_SOURCE"):
            control = lookup.get(
                (
                    row["block_id"],
                    f"AGGREGATE_EQUAL_WEIGHT_9_COUNTRIES_{METHOD_EXPOSURE}",
                    "",
                    int(row["cost_bps_per_side"]),
                )
            )
        else:
            control = None
        if control is not None and row["annualized_return"] != "" and control["annualized_return"] != "":
            row["delta_vs_exposure_matched_control"] = safe_float(row["annualized_return"]) - safe_float(control["annualized_return"])


def aggregate_returns_by_method(paths: dict[str, TrialPath]) -> dict[tuple[str, int], pd.Series]:
    out: dict[tuple[str, int], pd.Series] = {}
    for cost in COST_LEVELS_BPS:
        for method in (METHOD_TOM, METHOD_EXPOSURE):
            selected = [paths[trial_id(method, country, cost)].daily_returns.rename(country) for country in COUNTRY_ETFS]
            out[(method, cost)] = pd.concat(selected, axis=1).mean(axis=1)
    return out


def daily_positions_rows(paths: dict[str, TrialPath], calendar_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in paths.values():
        rows.extend(path.daily_positions.to_dict("records"))
    return rows


def turnover_and_cost_rows(paths: dict[str, TrialPath], calendar_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in paths.values():
        rows.extend(path.costs.to_dict("records"))
    return rows


def exposure_matched_control_rows(dates: pd.DatetimeIndex) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for period, month_dates in month_groups(dates).items():
        equity_weight = 4.0 / float(len(month_dates))
        for country in COUNTRY_ETFS:
            rows.append(
                {
                    "country_symbol": country,
                    "country": COUNTRY_NAMES[country],
                    "calendar_month": str(period),
                    "trading_days_in_month": len(month_dates),
                    "equity_weight": equity_weight,
                    "bil_weight": 1.0 - equity_weight,
                    "first_trading_date": month_dates[0].date().isoformat(),
                    "last_trading_date": month_dates[-1].date().isoformat(),
                    "control_definition": "equity_weight = 4 / number_of_US_trading_days_in_month; BIL is residual",
                }
            )
    return rows


def close_to_close_source_diagnostic(prices: PriceData, calendar_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cal = calendar_frame(calendar_rows)
    rows: list[dict[str, Any]] = []
    for country in COUNTRY_ETFS:
        returns = prices.close[country].pct_change(fill_method=None)
        frame = pd.DataFrame({"return": returns, "label": cal["tom_day_label"]}).dropna()
        for label in [TOM_DAY_MINUS_1, TOM_DAY_PLUS_1, TOM_DAY_PLUS_2, TOM_DAY_PLUS_3, NON_TOM]:
            subset = frame.loc[frame["label"] == label, "return"]
            rows.append(
                {
                    "country_symbol": country,
                    "country": COUNTRY_NAMES[country],
                    "tom_day_label": label,
                    "diagnostic_only": True,
                    "used_as_executable_fill": False,
                    "observation_count": int(len(subset)),
                    "mean_close_to_close_return": float(subset.mean()) if not subset.empty else "",
                    "median_close_to_close_return": float(subset.median()) if not subset.empty else "",
                    "hit_rate": float((subset > 0).mean()) if not subset.empty else "",
                    "total_compounded_close_to_close_return": float((1.0 + subset).prod() - 1.0) if not subset.empty else "",
                }
            )
    return rows


def tom_episode_attribution(paths: dict[str, TrialPath], calendar_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cal = calendar_frame(calendar_rows)
    rows: list[dict[str, Any]] = []
    for cost in COST_LEVELS_BPS:
        for country in COUNTRY_ETFS:
            path = paths[trial_id(METHOD_TOM, country, cost)]
            components = path.component_returns.copy()
            components["date_ts"] = pd.to_datetime(components["date"])
            for entry_date in cal.loc[cal["tom_day_label"] == TOM_DAY_MINUS_1, "date"]:
                entry_ts = pd.Timestamp(entry_date)
                month = str(entry_ts.to_period("M"))
                next_idx = list(cal.index).index(entry_ts) if entry_ts in cal.index else -1
                if next_idx < 0:
                    continue
                dates = list(cal.index)
                episode_dates = [entry_ts]
                cursor = next_idx + 1
                plus_seen = 0
                while cursor < len(dates) and plus_seen < 3:
                    label = str(cal.loc[dates[cursor], "tom_day_label"])
                    if label in {TOM_DAY_PLUS_1, TOM_DAY_PLUS_2, TOM_DAY_PLUS_3}:
                        episode_dates.append(pd.Timestamp(dates[cursor]))
                        plus_seen += 1
                    cursor += 1
                exit_date = dates[cursor] if cursor < len(dates) else pd.NaT
                subset_dates = set(pd.Timestamp(d).date().isoformat() for d in episode_dates)
                if pd.notna(exit_date):
                    subset_dates.add(pd.Timestamp(exit_date).date().isoformat())
                subset = components[components["date"].isin(subset_dates)]
                source_return = float(subset.loc[subset["source_component"], "total_component_return"].sum()) if not subset.empty else 0.0
                rows.append(
                    {
                        "country_symbol": country,
                        "country": COUNTRY_NAMES[country],
                        "cost_bps_per_side": cost,
                        "episode_month": month,
                        "entry_date": entry_ts.date().isoformat(),
                        "exit_date": "" if pd.isna(exit_date) else pd.Timestamp(exit_date).date().isoformat(),
                        "completed_episode": bool(pd.notna(exit_date) and plus_seen == 3),
                        "source_window_component_return": source_return,
                        "entry_overnight_contribution": float(subset["entry_overnight_contribution"].sum()) if not subset.empty else 0.0,
                        "open_to_close_contribution": float(subset["open_to_close_contribution"].sum()) if not subset.empty else 0.0,
                        "modeled_cost_component": float(subset["cost_contribution"].sum()) if not subset.empty else 0.0,
                        "dominant_single_day_component": float(subset["total_component_return"].abs().max()) if not subset.empty else 0.0,
                    }
                )
    return rows


def country_attribution(metrics_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    lookup = {(row["method_id"], row["country_symbol"], int(row["cost_bps_per_side"])): row for row in metrics_rows if row["row_type"] == "trial"}
    for cost in COST_LEVELS_BPS:
        for country in COUNTRY_ETFS:
            tom = lookup[(METHOD_TOM, country, cost)]
            exposure = lookup[(METHOD_EXPOSURE, country, cost)]
            buy_hold = lookup[(METHOD_BUY_HOLD, country, cost)]
            rows.append(
                {
                    "country_symbol": country,
                    "country": COUNTRY_NAMES[country],
                    "cost_bps_per_side": cost,
                    "tom_total_return": tom["total_return"],
                    "exposure_matched_total_return": exposure["total_return"],
                    "buy_hold_total_return": buy_hold["total_return"],
                    "tom_minus_exposure_matched_total_return": safe_float(tom["total_return"]) - safe_float(exposure["total_return"]),
                    "tom_minus_exposure_matched_annualized_return": safe_float(tom["annualized_return"]) - safe_float(exposure["annualized_return"]),
                    "tom_minus_buy_hold_total_return": safe_float(tom["total_return"]) - safe_float(buy_hold["total_return"]),
                    "tom_average_equity_exposure": tom["average_equity_exposure"],
                    "exposure_control_average_equity_exposure": exposure["average_equity_exposure"],
                }
            )
    return rows


def calendar_month_attribution(paths: dict[str, TrialPath], calendar_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for cost in COST_LEVELS_BPS:
        for country in COUNTRY_ETFS:
            for method in (METHOD_TOM, METHOD_EXPOSURE):
                path = paths[trial_id(method, country, cost)]
                frame = path.daily_positions.copy()
                frame["calendar_month_number"] = pd.to_datetime(frame["date"]).dt.month
                grouped = frame.groupby("calendar_month_number", dropna=False)
                for month_num, subset in grouped:
                    rows.append(
                        {
                            "country_symbol": country,
                            "country": COUNTRY_NAMES[country],
                            "method_id": method,
                            "cost_bps_per_side": cost,
                            "calendar_month_number": int(month_num),
                            "observation_count": int(len(subset)),
                            "component_return_sum": float(subset["daily_return"].sum()),
                            "compounded_return": float((1.0 + subset["daily_return"]).prod() - 1.0),
                            "source_window_component_return": float(subset["source_window_component_return"].sum()),
                            "non_tom_component_return": float(subset["non_tom_component_return"].sum()),
                        }
                    )
    return rows


def concentration_diagnostics(
    paths: dict[str, TrialPath],
    metrics_rows: list[dict[str, Any]],
    subperiod_rows: list[dict[str, Any]],
    month_rows: list[dict[str, Any]],
    episode_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for cost in COST_LEVELS_BPS:
        improvements = [
            row
            for row in country_attribution(metrics_rows)
            if int(row["cost_bps_per_side"]) == cost and safe_float(row["tom_minus_exposure_matched_total_return"]) > 0
        ]
        total_positive = sum(safe_float(row["tom_minus_exposure_matched_total_return"]) for row in improvements)
        max_country_share = (
            max(safe_float(row["tom_minus_exposure_matched_total_return"]) for row in improvements) / total_positive
            if total_positive > 0
            else 0.0
        )
        episode_subset = [row for row in episode_rows if int(row["cost_bps_per_side"]) == cost]
        positive_episode = [safe_float(row["source_window_component_return"]) for row in episode_subset if safe_float(row["source_window_component_return"]) > 0]
        episode_total = sum(positive_episode)
        max_episode_share = max(positive_episode) / episode_total if episode_total > 0 else 0.0
        monthly = [row for row in month_rows if int(row["cost_bps_per_side"]) == cost and row["method_id"] == METHOD_TOM]
        positive_month = [safe_float(row["source_window_component_return"]) for row in monthly if safe_float(row["source_window_component_return"]) > 0]
        month_total = sum(positive_month)
        max_month_share = max(positive_month) / month_total if month_total > 0 else 0.0
        block_rows = [
            row
            for row in subperiod_rows
            if row["method_id"] == f"AGGREGATE_EQUAL_WEIGHT_9_COUNTRIES_{METHOD_TOM}" and int(row["cost_bps_per_side"]) == cost
        ]
        positive_blocks = sum(1 for row in block_rows if safe_float(row.get("delta_vs_exposure_matched_control")) > 0)
        rows.append(
            {
                "cost_bps_per_side": cost,
                "positive_country_count_vs_exposure_control": len(improvements),
                "max_positive_country_share": max_country_share,
                "max_positive_episode_share": max_episode_share,
                "max_positive_calendar_month_share": max_month_share,
                "positive_chronological_block_count_vs_exposure_control": positive_blocks,
                "country_concentration_flag": max_country_share > 0.50,
                "episode_concentration_flag": max_episode_share > 0.50,
                "calendar_month_concentration_flag": max_month_share > 0.50,
                "short_episode_sequence_concentration_flag": max_episode_share > 0.50,
                "chronological_evidence_more_than_one_block": positive_blocks > 1,
            }
        )
    return rows


def classify_results(
    metrics_rows: list[dict[str, Any]],
    subperiod_rows: list[dict[str, Any]],
    concentration_rows: list[dict[str, Any]],
    identity_rows: list[dict[str, Any]],
    failure_rows: list[dict[str, Any]],
) -> tuple[str, str]:
    if failure_rows or any(row["equivalence_status"] != "PASS" for row in identity_rows):
        return "DATA_OR_IMPLEMENTATION_INVALID", comparison_md(
            "DATA_OR_IMPLEMENTATION_INVALID", metrics_rows, concentration_rows, "Failure or identity mismatch detected."
        )
    trial_lookup = {(row["method_id"], row["country_symbol"], int(row["cost_bps_per_side"])): row for row in metrics_rows}

    def country_deltas(cost: int) -> list[float]:
        return [
            safe_float(trial_lookup[(METHOD_TOM, country, cost)]["annualized_return"])
            - safe_float(trial_lookup[(METHOD_EXPOSURE, country, cost)]["annualized_return"])
            for country in COUNTRY_ETFS
        ]

    def aggregate_delta(cost: int) -> float:
        tom = trial_lookup[(f"AGGREGATE_EQUAL_WEIGHT_9_COUNTRIES_{METHOD_TOM}", "", cost)]
        exposure = trial_lookup[(f"AGGREGATE_EQUAL_WEIGHT_9_COUNTRIES_{METHOD_EXPOSURE}", "", cost)]
        return safe_float(tom["annualized_return"]) - safe_float(exposure["annualized_return"])

    pass_by_cost = {}
    for cost in (5, 10):
        deltas = country_deltas(cost)
        concentration = next(row for row in concentration_rows if int(row["cost_bps_per_side"]) == cost)
        pass_by_cost[cost] = {
            "median_improvement": float(np.median(deltas)) > 0,
            "country_count": sum(1 for value in deltas if value > 0) >= 5,
            "aggregate": aggregate_delta(cost) > 0,
            "blocks": bool(concentration["chronological_evidence_more_than_one_block"]),
            "not_concentrated": not any(
                bool(concentration[field])
                for field in (
                    "country_concentration_flag",
                    "episode_concentration_flag",
                    "calendar_month_concentration_flag",
                    "short_episode_sequence_concentration_flag",
                )
            ),
        }

    concentrated = any(not pass_by_cost[cost]["not_concentrated"] for cost in (5, 10))
    zero_edge = aggregate_delta(0) > 0
    cost_edge = pass_by_cost[5]["aggregate"] and pass_by_cost[10]["aggregate"]
    if all(all(flags.values()) for flags in pass_by_cost.values()):
        classification = "WORTH_DEEPER_RESEARCH"
    elif zero_edge and not cost_edge:
        classification = "COST_DOMINATED"
    else:
        bh_better_count = 0
        exposure_better_count = 0
        for country in COUNTRY_ETFS:
            tom = trial_lookup[(METHOD_TOM, country, 10)]
            buy_hold = trial_lookup[(METHOD_BUY_HOLD, country, 10)]
            exposure = trial_lookup[(METHOD_EXPOSURE, country, 10)]
            if safe_float(tom["maximum_drawdown"]) > safe_float(buy_hold["maximum_drawdown"]):
                bh_better_count += 1
            if safe_float(tom["annualized_return"]) > safe_float(exposure["annualized_return"]):
                exposure_better_count += 1
        if bh_better_count >= 5 and exposure_better_count < 5:
            classification = "CONTROL_WEAK"
        elif aggregate_delta(5) < 0 and aggregate_delta(10) < 0:
            classification = "BENCHMARK_DOMINATED"
        else:
            classification = "NO_MATERIAL_EDGE"
    if classification == "WORTH_DEEPER_RESEARCH" and concentrated:
        classification = "CONCENTRATED"
    return classification, comparison_md(classification, metrics_rows, concentration_rows, "")


def comparison_md(
    classification: str,
    metrics_rows: list[dict[str, Any]],
    concentration_rows: list[dict[str, Any]],
    note: str,
) -> str:
    aggregate_rows = [
        row
        for row in metrics_rows
        if row.get("row_type") == "aggregate_reporting"
        and str(row["method_id"]).startswith("AGGREGATE_EQUAL_WEIGHT_9_COUNTRIES")
    ]
    lines = [
        f"# {ARTIFACT_ID}",
        "",
        f"Final exploratory classification: `{classification}`.",
        "",
        "This is a bounded research-only source-rule completion run. It is not validation, optimization, promotion, paper/demo eligibility, or real-money advice.",
        "",
        "## Registered Design",
        "",
        f"- Frozen source country ETFs: `{', '.join(COUNTRY_ETFS)}`.",
        f"- Project T-bill translation: `{CASH_SYMBOL}`.",
        "- Executable timing: target-change intents are known before the opening fill, entries fill at the next valid Day -1 open, and exits fill at the next valid Day +4 open.",
        "- Close-to-close source-window calculations are diagnostic only and are not used for executable fills.",
        "- Optional management overlay count: `0`.",
        "",
    ]
    if note:
        lines.extend(["## Failure Note", "", note, ""])
    lines.extend(["## Aggregate Reporting Rows", "", "| method | bps | total return | annualized return | max drawdown | Sharpe | avg equity exposure | turnover | costs |", "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"])
    for row in aggregate_rows:
        lines.append(
            f"| {row['method_id']} | {row['cost_bps_per_side']} | {fmt(row['total_return'])} | {fmt(row['annualized_return'])} | {fmt(row['maximum_drawdown'])} | {fmt(row['sharpe'])} | {fmt(row['average_equity_exposure'])} | {fmt(row['turnover'])} | {fmt(row['modeled_costs'])} |"
        )
    lines.extend(["", "## Concentration Diagnostics", "", "| bps | positive countries | max country share | max episode share | max month share | positive blocks |", "| ---: | ---: | ---: | ---: | ---: | ---: |"])
    for row in concentration_rows:
        lines.append(
            f"| {row['cost_bps_per_side']} | {row['positive_country_count_vs_exposure_control']} | {fmt(row['max_positive_country_share'])} | {fmt(row['max_positive_episode_share'])} | {fmt(row['max_positive_calendar_month_share'])} | {row['positive_chronological_block_count_vs_exposure_control']} |"
        )
    lines.extend(
        [
            "",
            "## Boundary Confirmation",
            "",
            "No tuning, symbol replacement, optional management overlay, validation, promotion, paper/demo/live action, or broker invocation occurred.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_failure_only_artifacts(
    output_dir: Path,
    prices: PriceData,
    trials: list[dict[str, Any]],
    failed_trials: list[dict[str, Any]],
    failure_rows: list[dict[str, Any]],
) -> None:
    write_csv(output_dir / "trial_registry.csv", failed_trials, trial_registry_fields())
    empty_files = {
        "identity_equivalence.csv": identity_equivalence_fields(),
        "metrics.csv": metrics_fields(),
        "subperiod_metrics.csv": subperiod_fields(),
        "daily_positions.csv": daily_positions_fields(),
        "tom_episode_attribution.csv": episode_fields(),
        "country_attribution.csv": country_attribution_fields(),
        "calendar_month_attribution.csv": calendar_month_fields(),
        "exposure_matched_control.csv": exposure_control_fields(),
        "turnover_and_costs.csv": turnover_fields(),
        "close_to_close_source_diagnostic.csv": diagnostic_fields(),
        "concentration_diagnostics.csv": concentration_fields(),
    }
    for filename, fields in empty_files.items():
        write_csv(output_dir / filename, [], fields)
    write_csv(output_dir / "failure_registry.csv", failure_rows, failure_fields())
    classification = "DATA_OR_IMPLEMENTATION_INVALID"
    write_text(output_dir / "comparison.md", comparison_md(classification, [], [], "Exact source universe incomplete; performance run stopped."))
    write_text(output_dir / "source_of_truth_update.md", source_of_truth_update(classification, prices))
    write_text(output_dir / "test_results.txt", "PENDING - run stopped before performance because the exact source universe was incomplete.\n")
    write_json(
        output_dir / "manifest.json",
        {
            "artifact_id": ARTIFACT_ID,
            "classification": classification,
            "registered_trial_count": len(trials),
            "completed_trial_count": 0,
            "failed_trial_count": len(failed_trials),
            "failure_codes": sorted({row["failure_code"] for row in failure_rows}),
            "optional_management_overlay_count": 0,
            "paper_demo_live_action": False,
            "broker_action": False,
        },
    )


def completed_trial_registry(
    trials: list[dict[str, Any]],
    paths: dict[str, TrialPath],
    failures: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not paths:
        reason = ";".join(sorted({row.get("failure_code", "") for row in failures if row.get("failure_code")}))
        return [
            {**trial, "status": "FAILED", "failure_code": reason or "SOURCE_UNIVERSE_INCOMPLETE", "failure_reason": "performance stopped before execution"}
            for trial in trials
        ]
    failure_by_trial = {row["trial_id"]: row for row in failures if row.get("trial_id")}
    rows = []
    for trial in trials:
        row = dict(trial)
        if row["trial_id"] in failure_by_trial:
            row["status"] = "FAILED"
            row["failure_code"] = failure_by_trial[row["trial_id"]]["failure_code"]
            row["failure_reason"] = failure_by_trial[row["trial_id"]]["detail"]
        elif row["trial_id"] in paths:
            row["status"] = "COMPLETED"
        else:
            row["status"] = "FAILED"
            row["failure_code"] = "ACCOUNTING_RECONCILIATION_FAILED"
            row["failure_reason"] = "registered trial missing from completed paths"
        rows.append(row)
    return rows


def max_drawdown_and_duration(nav: pd.Series) -> tuple[float, int]:
    if nav.empty:
        return 0.0, 0
    running = nav.cummax()
    dd = nav / running - 1.0
    current = 0
    longest = 0
    for value in dd:
        if value >= -TOL:
            current = 0
        else:
            current += 1
            longest = max(longest, current)
    return float(dd.min()), int(longest)


def expected_shortfall(returns: pd.Series, confidence: float) -> float:
    clean = returns.dropna()
    if clean.empty:
        return float("nan")
    cutoff_count = max(1, int(math.ceil((1.0 - confidence) * len(clean.index))))
    return float(clean.sort_values().iloc[:cutoff_count].mean())


def completed_episode_count(daily_positions: pd.DataFrame) -> int:
    if daily_positions.empty or "tom_day_label" not in daily_positions:
        return 0
    return int((daily_positions["tom_day_label"] == TOM_DAY_MINUS_1).sum())


def five_year_blocks(start: pd.Timestamp, end: pd.Timestamp) -> list[dict[str, str]]:
    blocks: list[dict[str, str]] = []
    cursor = pd.Timestamp(start)
    block_id = 1
    while cursor <= end:
        block_end = min(cursor + pd.DateOffset(years=5) - pd.Timedelta(days=1), pd.Timestamp(end))
        blocks.append({"block_id": block_id, "start_date": cursor.date().isoformat(), "end_date": block_end.date().isoformat()})
        cursor = cursor + pd.DateOffset(years=5)
        block_id += 1
    return blocks


def source_and_worktree_hashes(root: Path, data_hashes: dict[str, str]) -> dict[str, Any]:
    module_path = Path(__file__).resolve()
    runner_path = root / f"run_{ARTIFACT_ID}.py"
    return {
        "created_at_utc": now_utc(),
        "repository_head": git_output(root, ["rev-parse", "HEAD"]),
        "git_status_short": git_output(root, ["status", "--short"]),
        "dirty_worktree": bool(git_output(root, ["status", "--short"]).strip()),
        "tracked_diff_hash": "sha256:" + hashlib.sha256(git_output(root, ["diff", "--no-ext-diff", "--binary"]).encode("utf-8")).hexdigest(),
        "git_status_short_hash": "sha256:" + hashlib.sha256(git_output(root, ["status", "--short"]).encode("utf-8")).hexdigest(),
        "untracked_file_list_hash": "sha256:"
        + hashlib.sha256(git_output(root, ["ls-files", "--others", "--exclude-standard"]).encode("utf-8")).hexdigest(),
        "source_module_path": str(module_path),
        "source_module_hash": sha256_file(module_path),
        "runner_path": str(runner_path.resolve()),
        "runner_hash": sha256_file(runner_path) if runner_path.exists() else "",
        "strategy_rule_hash": stable_hash(RULE_PACKET),
        "data_file_hashes": data_hashes,
    }


def git_output(root: Path, args: list[str]) -> str:
    try:
        return subprocess.run(["git", *args], cwd=root, check=False, capture_output=True, text=True).stdout
    except Exception:
        return ""


def file_hashes_for_symbols(root: Path) -> dict[str, str]:
    return {
        symbol: sha256_file(root / DATA_CACHE_DIR / f"{symbol}.csv")
        for symbol in FROZEN_SYMBOLS
        if (root / DATA_CACHE_DIR / f"{symbol}.csv").exists()
    }


def frozen_universe_payload(prices: PriceData, hashes: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "artifact_id": ARTIFACT_ID,
        "symbols": list(FROZEN_SYMBOLS),
        "country_etfs": [{"symbol": symbol, "country": COUNTRY_NAMES[symbol]} for symbol in COUNTRY_ETFS],
        "cash_symbol": CASH_SYMBOL,
        "symbol_replacement_allowed": False,
        "dynamic_universe_changes_allowed": False,
        "optional_management_overlay_count": 0,
        "common_start": "" if pd.isna(prices.common_start) else prices.common_start.date().isoformat(),
        "common_end": "" if pd.isna(prices.common_end) else prices.common_end.date().isoformat(),
        "data_file_hashes": prices.file_hashes,
        "source_rule_hash": hashes.get("strategy_rule_hash", ""),
    }
    payload["frozen_universe_hash"] = stable_hash(payload)
    return payload


def configuration_payload(prices: PriceData, calendar_hash: str) -> dict[str, Any]:
    return {
        "evaluation_dates": {
            "start": "" if pd.isna(prices.common_start) else prices.common_start.date().isoformat(),
            "end": "" if pd.isna(prices.common_end) else prices.common_end.date().isoformat(),
            "date_count": len(prices.calendar),
        },
        "us_trading_calendar_source": "BIL calendar restricted to exact ten-symbol common open/close availability",
        "us_trading_calendar_hash": calendar_hash,
        "tom_day_definition": {
            TOM_DAY_MINUS_1: "last US trading day of the current month",
            TOM_DAY_PLUS_1: "first US trading day of the next/current calendar month",
            TOM_DAY_PLUS_2: "second US trading day of the month",
            TOM_DAY_PLUS_3: "third US trading day of the month",
            NON_TOM: "all other US trading days",
        },
        "execution_convention": RULE_PACKET["execution"],
        "cost_bps_per_side": list(COST_LEVELS_BPS),
        "control_definitions": {
            METHOD_IDENTITY: "mechanical identity of TOM source strategy; must match complete state",
            METHOD_BUY_HOLD: "100% country ETF buy-and-hold from first evaluation open",
            METHOD_EXPOSURE: "monthly static country/BIL control with country target 4 / US trading days in month",
            METHOD_BIL: "100% BIL contextual benchmark run once per cost level",
        },
        "classification_rules": classification_rules_payload(),
        "trial_count": EXPECTED_TRIAL_COUNT,
    }


def pre_registered_manifest(
    hashes: dict[str, Any],
    frozen_universe: dict[str, Any],
    prices: PriceData,
    config: dict[str, Any],
    trials: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "artifact_id": ARTIFACT_ID,
        "created_before_performance": True,
        "source_rule_completion": True,
        "research_only_exploration": True,
        "validation": False,
        "optimization": False,
        "promotion": False,
        "paper_demo_eligibility": False,
        "paper_forward_activation": False,
        "broker_or_live_action": False,
        "source_and_worktree_hashes": hashes,
        "frozen_universe": frozen_universe,
        "source_rule_packet": RULE_PACKET,
        "exact_ticker_order": list(FROZEN_SYMBOLS),
        "exact_bil_mapping": {"project_tbill_translation": CASH_SYMBOL},
        "data_hashes_and_coverage": prices.file_hashes,
        "data_acquisition_log": prices.acquisition_rows,
        "evaluation_dates": config["evaluation_dates"],
        "us_trading_calendar": config["us_trading_calendar_source"],
        "us_trading_calendar_hash": config["us_trading_calendar_hash"],
        "day_definition": config["tom_day_definition"],
        "execution_convention": config["execution_convention"],
        "cost_assumptions": {"bps_per_side": list(COST_LEVELS_BPS), "cost_model": "gross traded notional times bps per side at open fill"},
        "control_definitions": config["control_definitions"],
        "trial_count": len(trials),
        "trial_count_expected": EXPECTED_TRIAL_COUNT,
        "trial_registry_hash": stable_hash(trials),
        "classification_rules": config["classification_rules"],
        "period_selection_rule": "maximum common adjusted open/close period after BIL and all nine country ETFs are available; not selected from performance",
        "sealed_holdout": False,
    }


def manifest_payload(
    prices: PriceData,
    config: dict[str, Any],
    trial_registry_rows: list[dict[str, Any]],
    classification: str,
    identity_rows: list[dict[str, Any]],
    failure_rows: list[dict[str, Any]],
    hashes: dict[str, Any],
) -> dict[str, Any]:
    return {
        "artifact_id": ARTIFACT_ID,
        "created_at_utc": now_utc(),
        "source_rule_completion": True,
        "research_only_exploration": True,
        "classification": classification,
        "classification_allowed": classification in CLASSIFICATIONS,
        "evaluation_start": prices.common_start.date().isoformat(),
        "evaluation_end": prices.common_end.date().isoformat(),
        "evaluation_date_count": len(prices.calendar),
        "registered_trial_count": len(trial_registry_rows),
        "expected_trial_count": EXPECTED_TRIAL_COUNT,
        "completed_trial_count": sum(1 for row in trial_registry_rows if row["status"] == "COMPLETED"),
        "failed_trial_count": sum(1 for row in trial_registry_rows if row["status"] == "FAILED"),
        "identity_rows": len(identity_rows),
        "identity_all_passed": all(row["equivalence_status"] == "PASS" for row in identity_rows),
        "failure_count": len(failure_rows),
        "failure_codes": sorted({row["failure_code"] for row in failure_rows}),
        "source_symbols_frozen": list(FROZEN_SYMBOLS),
        "symbol_replacement": False,
        "dynamic_universe_dropping": False,
        "optional_management_overlay_used": False,
        "optional_management_overlay_count": 0,
        "tuning_or_parameter_search": False,
        "validation_run": False,
        "promotion_created": False,
        "paper_demo_eligibility_review": False,
        "paper_forward_activation": False,
        "broker_or_live_action": False,
        "historical_performance_matrix": False,
        "close_to_close_diagnostic_only": True,
        "next_open_execution": True,
        "source_and_worktree_hashes": hashes,
        "configuration": config,
        "data_acquisition_log": prices.acquisition_rows,
    }


def classification_rules_payload() -> dict[str, Any]:
    return {
        "WORTH_DEEPER_RESEARCH": [
            "at 5 and 10 bps, median country annualized-return improvement versus exposure-matched control is positive",
            "at 5 and 10 bps, at least five of nine countries improve versus exposure-matched control",
            "at 5 and 10 bps, equal-weight reporting aggregate improves versus exposure-matched aggregate",
            "aggregate evidence is positive in more than one consecutive chronological block",
            "benefit is not mostly explained by one country, month, or short episode sequence",
            "benefit is not mainly BIL performance",
        ],
        "CONTROL_WEAK": "strategy appears better than buy-and-hold primarily through lower equity exposure but fails exposure-matched control",
        "COST_DOMINATED": "zero-cost aggregate improvement does not survive 5 and 10 bps",
        "BENCHMARK_DOMINATED": "aggregate underperforms exposure-matched control after costs",
        "NO_MATERIAL_EDGE": "valid implementation with no qualifying edge pattern",
        "CONCENTRATED": "otherwise promising improvement is concentrated in one country, month, or episode sequence",
        "DATA_OR_IMPLEMENTATION_INVALID": "data, calendar, identity, timing, or accounting failure",
    }


def source_of_truth_update(classification: str, prices: PriceData) -> str:
    start = "" if pd.isna(prices.common_start) else prices.common_start.date().isoformat()
    end = "" if pd.isna(prices.common_end) else prices.common_end.date().isoformat()
    return f"""# Source Of Truth Update

`{ARTIFACT_ID}` completed the requested bounded source-rule completion run.

- Frozen symbols: `{", ".join(FROZEN_SYMBOLS)}`.
- Frozen range: `{start}` to `{end}`.
- Registered runs: `{EXPECTED_TRIAL_COUNT}`.
- Final exploratory classification: `{classification}`.
- Research stage: `research_only_exploration`.
- The equal-weight nine-country aggregate is reporting-only and is not an optimized portfolio trial.
- No tuning, symbol replacement, optional management overlay, validation, promotion, paper/demo/live action, or broker invocation occurred.
"""


def failure_row(trial_id: str, date: str, symbol: str, failure_code: str, detail: str) -> dict[str, Any]:
    if failure_code not in FAILURE_CODES:
        raise ValueError(f"unknown failure code: {failure_code}")
    return {
        "trial_id": trial_id,
        "date": date,
        "symbol": symbol,
        "failure_code": failure_code,
        "detail": detail,
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(jsonable(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: csv_value(row.get(field, "")) for field in fieldnames})


def csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (np.integer,)):
        return str(int(value))
    if isinstance(value, (np.floating, float)):
        numeric = float(value)
        return "" if not math.isfinite(numeric) else repr(numeric)
    if isinstance(value, (np.bool_, bool)):
        return "True" if bool(value) else "False"
    if isinstance(value, (list, tuple)):
        return "|".join(str(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(jsonable(value), sort_keys=True)
    return str(value)


def jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [jsonable(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        numeric = float(value)
        return None if not math.isfinite(numeric) else numeric
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, float):
        return None if not math.isfinite(value) else value
    if isinstance(value, pd.Timestamp):
        return value.date().isoformat()
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_hash(value: Any) -> str:
    text = json.dumps(jsonable(value), sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def state_hash_payload(**frames: Any) -> str:
    payload: dict[str, Any] = {}
    for name, value in frames.items():
        if isinstance(value, pd.DataFrame):
            payload[name] = frame_payload(value)
        elif isinstance(value, pd.Series):
            payload[name] = series_payload(value)
        else:
            payload[name] = value
    return stable_hash(payload)


def frame_payload(frame: pd.DataFrame) -> dict[str, Any]:
    return {
        "index": [str(pd.Timestamp(idx).date()) if isinstance(idx, pd.Timestamp) else str(idx) for idx in frame.index],
        "columns": [str(column) for column in frame.columns],
        "values": [[payload_cell(value) for value in row] for row in frame.to_numpy()],
    }


def series_payload(series: pd.Series) -> dict[str, float]:
    return {str(pd.Timestamp(idx).date()) if isinstance(idx, pd.Timestamp) else str(idx): round(float(value), 12) for idx, value in series.fillna(0.0).items()}


def payload_cell(value: Any) -> Any:
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float, int)):
        numeric = float(value)
        return None if not math.isfinite(numeric) else round(numeric, 12)
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    return str(value)


def frame_equal(left: pd.DataFrame, right: pd.DataFrame) -> bool:
    return (
        left.shape == right.shape
        and list(left.index) == list(right.index)
        and list(left.columns) == list(right.columns)
        and np.allclose(left.to_numpy(dtype=float), right.to_numpy(dtype=float), atol=1e-12, rtol=0.0)
    )


def series_equal(left: pd.Series, right: pd.Series) -> bool:
    return left.shape == right.shape and list(left.index) == list(right.index) and np.allclose(left.to_numpy(dtype=float), right.to_numpy(dtype=float), atol=1e-12, rtol=0.0)


def safe_float(value: Any) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return float("nan")
    return parsed if math.isfinite(parsed) else float("nan")


def fmt(value: Any) -> str:
    numeric = safe_float(value)
    if math.isnan(numeric):
        return ""
    return f"{numeric:.4f}"


def data_coverage_fields() -> list[str]:
    return [
        "symbol",
        "country",
        "role",
        "required",
        "cache_path",
        "cache_available",
        "cache_status",
        "qa_status",
        "source_action",
        "provider_api_called",
        "download_attempted",
        "first_date",
        "last_date",
        "row_count",
        "valid_open_close_rows",
        "missing_date_count_on_bil_calendar",
        "duplicate_dates",
        "non_positive_adjusted_price_count",
        "schema_matches_normalized_daily_etf_data",
        "file_sha256",
        "failure_code",
        "failure_reason",
    ]


def calendar_fields() -> list[str]:
    return [
        "date",
        "calendar_month",
        "trading_day_number_from_start",
        "trading_day_number_from_end",
        "tom_status",
        "tom_day_label",
    ]


def trial_registry_fields() -> list[str]:
    return [
        "trial_id",
        "method_id",
        "country_symbol",
        "country",
        "cash_symbol",
        "cost_bps_per_side",
        "registered_before_performance",
        "optional_management_overlay_count",
        "validation_or_promotion_status",
        "status",
        "failure_code",
        "failure_reason",
    ]


def identity_equivalence_fields() -> list[str]:
    return [
        "country_symbol",
        "country",
        "cost_bps_per_side",
        "signals_equal",
        "tom_labels_equal",
        "target_weights_equal",
        "orders_equal",
        "fills_equal",
        "daily_positions_equal",
        "daily_cash_equal",
        "daily_nav_equal",
        "costs_equal",
        "complete_state_hash_equal",
        "final_metrics_equal",
        "tom_state_hash",
        "identity_state_hash",
        "equivalence_status",
    ]


def metrics_fields() -> list[str]:
    return [
        "row_type",
        "trial_id",
        "method_id",
        "country_symbol",
        "country",
        "cost_bps_per_side",
        "initial_nav",
        "terminal_nav",
        "total_return",
        "annualized_return",
        "annualized_volatility",
        "maximum_drawdown",
        "drawdown_duration_days",
        "sharpe",
        "sortino",
        "return_to_drawdown",
        "worst_daily_return",
        "expected_shortfall_95",
        "average_equity_exposure",
        "average_bil_exposure",
        "turnover",
        "gross_traded_notional",
        "orders",
        "fills",
        "modeled_costs",
        "tom_return",
        "non_tom_return",
        "entry_overnight_contribution",
        "open_to_close_contribution",
        "completed_tom_episodes",
        "delayed_entries",
        "failed_entries",
        "delayed_exits",
        "failed_exits",
        "total_return_delta_vs_exposure_matched_control",
        "annualized_return_delta_vs_exposure_matched_control",
        "sharpe_delta_vs_exposure_matched_control",
        "return_to_drawdown_delta_vs_exposure_matched_control",
        "state_hash",
        "aggregate_component_count",
        "validation_status",
        "promotion_status",
        "paper_demo_live_status",
    ]


def subperiod_fields() -> list[str]:
    return [
        "block_id",
        "block_start",
        "block_end",
        "trial_id",
        "method_id",
        "country_symbol",
        "cost_bps_per_side",
        "date_count",
        "total_return",
        "annualized_return",
        "annualized_volatility",
        "maximum_drawdown",
        "sharpe",
        "delta_vs_exposure_matched_control",
    ]


def daily_positions_fields() -> list[str]:
    return [
        "trial_id",
        "method_id",
        "country_symbol",
        "country",
        "cost_bps_per_side",
        "date",
        "calendar_month",
        "tom_day_label",
        "tom_status",
        "target_country_weight",
        "target_bil_weight",
        "country_weight",
        "bil_weight",
        "cash_weight",
        "shares_country",
        "shares_bil",
        "nav",
        "daily_return",
        "orders_count",
        "fills_count",
        "target_changed_at_open",
        "gross_traded_notional",
        "gross_traded_notional_pct",
        "one_way_turnover",
        "modeled_cost_dollars",
        "transaction_cost_return",
        "overnight_contribution",
        "entry_overnight_contribution",
        "open_to_close_contribution",
        "source_window_component_return",
        "non_tom_component_return",
        "delayed_entry",
        "failed_entry",
        "delayed_exit",
        "failed_exit",
    ]


def episode_fields() -> list[str]:
    return [
        "country_symbol",
        "country",
        "cost_bps_per_side",
        "episode_month",
        "entry_date",
        "exit_date",
        "completed_episode",
        "source_window_component_return",
        "entry_overnight_contribution",
        "open_to_close_contribution",
        "modeled_cost_component",
        "dominant_single_day_component",
    ]


def country_attribution_fields() -> list[str]:
    return [
        "country_symbol",
        "country",
        "cost_bps_per_side",
        "tom_total_return",
        "exposure_matched_total_return",
        "buy_hold_total_return",
        "tom_minus_exposure_matched_total_return",
        "tom_minus_exposure_matched_annualized_return",
        "tom_minus_buy_hold_total_return",
        "tom_average_equity_exposure",
        "exposure_control_average_equity_exposure",
    ]


def calendar_month_fields() -> list[str]:
    return [
        "country_symbol",
        "country",
        "method_id",
        "cost_bps_per_side",
        "calendar_month_number",
        "observation_count",
        "component_return_sum",
        "compounded_return",
        "source_window_component_return",
        "non_tom_component_return",
    ]


def exposure_control_fields() -> list[str]:
    return [
        "country_symbol",
        "country",
        "calendar_month",
        "trading_days_in_month",
        "equity_weight",
        "bil_weight",
        "first_trading_date",
        "last_trading_date",
        "control_definition",
    ]


def turnover_fields() -> list[str]:
    return [
        "trial_id",
        "method_id",
        "country_symbol",
        "cost_bps_per_side",
        "date",
        "is_execution_date",
        "gross_traded_notional",
        "gross_traded_notional_pct",
        "one_way_turnover",
        "transaction_cost_return",
        "modeled_cost_dollars",
        "orders_count",
        "fills_count",
        "expected_transaction_cost_return",
    ]


def diagnostic_fields() -> list[str]:
    return [
        "country_symbol",
        "country",
        "tom_day_label",
        "diagnostic_only",
        "used_as_executable_fill",
        "observation_count",
        "mean_close_to_close_return",
        "median_close_to_close_return",
        "hit_rate",
        "total_compounded_close_to_close_return",
    ]


def concentration_fields() -> list[str]:
    return [
        "cost_bps_per_side",
        "positive_country_count_vs_exposure_control",
        "max_positive_country_share",
        "max_positive_episode_share",
        "max_positive_calendar_month_share",
        "positive_chronological_block_count_vs_exposure_control",
        "country_concentration_flag",
        "episode_concentration_flag",
        "calendar_month_concentration_flag",
        "short_episode_sequence_concentration_flag",
        "chronological_evidence_more_than_one_block",
    ]


def failure_fields() -> list[str]:
    return ["trial_id", "date", "symbol", "failure_code", "detail"]


if __name__ == "__main__":
    result = run(ROOT)
    print(f"classification={result['classification']}")
    print(f"artifact_dir={result['artifact_dir']}")
