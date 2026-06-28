from __future__ import annotations

import csv
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd
import yaml

import run_first_expansion_discovery_preregistration as prereg
from src.data import DataQualityError, NORMALIZED_COLUMNS, _download_yfinance, build_adjusted_ohlc


ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = Path("evidence") / "data_availability" / "first_expansion_batch" / "latest"
SYMBOL_MAP_PATH = Path("strategy_lab") / "approved_etf_symbol_map.yaml"
DATA_CACHE_DIR = Path("data") / "cache"
CONFIG_PATH = Path("config.yaml")
AUTHORIZED_SYMBOLS = ["DIA", "XLRE"]
DATA_SOURCE_LABEL = "yfinance_compatible_adjusted_daily_etf_data"
DAILY_REQUIRED_COLUMNS = ["date", "open", "high", "low", "close", "adj_close", "volume", "symbol"]
Downloader = Callable[[str, str, str | None, dict[str, Any]], pd.DataFrame]


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [json_safe(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    return value


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(json_safe(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def cache_path(root: Path, symbol: str) -> Path:
    return root / DATA_CACHE_DIR / f"{symbol}.csv"


def validate_requested_symbols(symbols: list[str]) -> list[str]:
    normalized = [str(symbol).strip().upper() for symbol in symbols]
    forbidden = sorted(set(normalized) - set(AUTHORIZED_SYMBOLS))
    if forbidden:
        raise ValueError(f"Only DIA and XLRE are authorized for this refresh step. Forbidden: {', '.join(forbidden)}")
    return normalized


def load_config(root: Path) -> dict[str, Any]:
    config = load_yaml(root / CONFIG_PATH)
    if config:
        return config
    return {
        "data": {
            "start_date": "2007-01-01",
            "end_date": None,
            "yfinance": {"auto_adjust": False, "actions": True, "progress": False, "multi_level_index": False, "timeout": 10},
        }
    }


def ensure_symbol_map_authorization(root: Path, created_utc: str, output_dir: Path) -> None:
    path = root / SYMBOL_MAP_PATH
    symbol_map = load_yaml(path)
    rows = symbol_map.setdefault("symbols", [])
    rows_by_symbol = {str(row.get("symbol", "")).upper(): row for row in rows}
    definitions = {
        "DIA": {
            "group": "first_expansion_required_broad_etf",
            "notes": "Required frozen first-expansion candidate symbol; authorized only for daily adjusted ETF cache refresh and research availability.",
        },
        "XLRE": {
            "group": "first_expansion_required_sector_etf",
            "notes": "Required frozen first-expansion sector ETF symbol; authorized only for daily adjusted ETF cache refresh and research availability.",
        },
    }
    for symbol, extra in definitions.items():
        row = rows_by_symbol.get(symbol)
        if row is None:
            row = {"symbol": symbol}
            rows.append(row)
        row.update(
            {
                "group": extra["group"],
                "allowed_for_strategy": True,
                "allowed_for_benchmark": True,
                "requires_explicit_prompt": True,
                "approved_status": row.get("approved_status", "approved_pending_first_expansion_cache_refresh"),
                "approval_source": "first_expansion_data_availability_refresh",
                "cache_ready": bool(row.get("cache_ready", False)),
                "latest_cache_refresh_path": str(output_dir.resolve()),
                "data_source": DATA_SOURCE_LABEL,
                "notes": extra["notes"],
                "last_authorized_refresh_utc": created_utc,
            }
        )
    path.write_text(yaml.safe_dump(symbol_map, sort_keys=False, allow_unicode=False, width=120), encoding="utf-8")


def update_symbol_map_after_qa(root: Path, coverage_rows: list[dict[str, Any]], output_dir: Path) -> None:
    path = root / SYMBOL_MAP_PATH
    symbol_map = load_yaml(path)
    rows_by_symbol = {str(row.get("symbol", "")).upper(): row for row in symbol_map.get("symbols", [])}
    for coverage in coverage_rows:
        symbol = str(coverage["symbol"]).upper()
        if symbol not in AUTHORIZED_SYMBOLS:
            continue
        row = rows_by_symbol.get(symbol)
        if row is None:
            continue
        if coverage["qa_status"] == "passed":
            row.update(
                {
                    "approved_status": "approved_cache_ready",
                    "cache_ready": True,
                    "latest_cache_refresh_path": str(output_dir.resolve()),
                    "data_source": DATA_SOURCE_LABEL,
                    "first_date": coverage["first_available_date"],
                    "last_date": coverage["last_available_date"],
                    "row_count": int(coverage["row_count"]),
                    "qa_status": "passed",
                    "schema_matches_existing_daily_etf_data": bool(coverage["schema_matches_existing_daily_etf_data"]),
                }
            )
        else:
            row.update(
                {
                    "approved_status": "approved_pending_first_expansion_cache_refresh",
                    "cache_ready": False,
                    "latest_cache_refresh_path": str(output_dir.resolve()),
                    "data_source": DATA_SOURCE_LABEL,
                    "qa_status": coverage["qa_status"],
                    "cache_failure_reason": coverage["failure_reason"],
                }
            )
    path.write_text(yaml.safe_dump(symbol_map, sort_keys=False, allow_unicode=False, width=120), encoding="utf-8")


def null_count_by_required_column(frame: pd.DataFrame) -> dict[str, int]:
    return {column: int(frame[column].isna().sum()) if column in frame.columns else -1 for column in DAILY_REQUIRED_COLUMNS}


def parse_date(value: str) -> date | None:
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def min_period_support(first_date: str, last_date: str, years: int) -> bool:
    first = parse_date(first_date)
    last = parse_date(last_date)
    if first is None or last is None:
        return False
    return (last - first).days >= years * 365


def missing_business_day_count(dates: pd.Series) -> int:
    parsed = pd.to_datetime(dates, errors="coerce").dropna()
    if parsed.empty:
        return 0
    all_business_days = pd.bdate_range(parsed.min().date(), parsed.max().date())
    observed = pd.DatetimeIndex(parsed.dt.normalize().unique())
    return int(len(all_business_days.difference(observed)))


def qa_cache_file(root: Path, symbol: str, affected_minimum_years: int = 10) -> dict[str, Any]:
    path = cache_path(root, symbol)
    base = {
        "symbol": symbol,
        "data_source_provider_used": DATA_SOURCE_LABEL,
        "cache_path": str(path),
        "first_available_date": "",
        "last_available_date": "",
        "row_count": 0,
        "required_ohlcv_columns": ";".join(DAILY_REQUIRED_COLUMNS),
        "adjusted_close_available": False,
        "missing_date_count_if_detectable": "",
        "duplicate_date_count": 0,
        "null_count_by_required_column": "{}",
        "supports_minimum_backtest_period": False,
        "schema_matches_existing_daily_etf_data": False,
        "stale_data_status": "freshness_threshold_not_defined",
        "qa_status": "failed",
        "cache_status": "missing",
        "failure_reason": "cache file missing",
    }
    if not path.exists():
        return base
    try:
        frame = pd.read_csv(path)
    except Exception as exc:
        return {**base, "cache_status": "present_unreadable", "failure_reason": f"cache read failed: {exc}"}
    columns = {str(column) for column in frame.columns}
    required_columns_present = set(DAILY_REQUIRED_COLUMNS) <= columns
    schema_matches = list(frame.columns) == NORMALIZED_COLUMNS
    if "date" in frame.columns:
        dates = pd.to_datetime(frame["date"], errors="coerce")
        valid_dates = dates.dropna()
        first = "" if valid_dates.empty else str(valid_dates.min().date())
        last = "" if valid_dates.empty else str(valid_dates.max().date())
        duplicate_dates = int(valid_dates.duplicated().sum())
        missing_dates = missing_business_day_count(dates)
    else:
        first = ""
        last = ""
        duplicate_dates = 0
        missing_dates = ""
    null_counts = null_count_by_required_column(frame)
    adjusted_close_available = "adj_close" in frame.columns and pd.to_numeric(frame["adj_close"], errors="coerce").notna().any()
    has_required_no_nulls = required_columns_present and all(value == 0 for value in null_counts.values())
    supports_period = min_period_support(first, last, affected_minimum_years)
    pass_qa = bool(required_columns_present and adjusted_close_available and duplicate_dates == 0 and has_required_no_nulls and schema_matches)
    reason = ""
    if not pass_qa:
        reason = "required columns, adjusted close, duplicate dates, null checks, or schema validation failed"
    return {
        **base,
        "first_available_date": first,
        "last_available_date": last,
        "row_count": int(len(frame)),
        "adjusted_close_available": adjusted_close_available,
        "missing_date_count_if_detectable": missing_dates,
        "duplicate_date_count": duplicate_dates,
        "null_count_by_required_column": json.dumps(null_counts, sort_keys=True),
        "supports_minimum_backtest_period": supports_period,
        "schema_matches_existing_daily_etf_data": schema_matches,
        "qa_status": "passed" if pass_qa else "failed",
        "cache_status": "present_pass" if pass_qa else "present_fail",
        "failure_reason": reason,
    }


def write_normalized_cache(root: Path, symbol: str, raw: pd.DataFrame) -> None:
    normalized = build_adjusted_ohlc(raw, symbol)
    target = cache_path(root, symbol)
    target.parent.mkdir(parents=True, exist_ok=True)
    normalized.to_csv(target, index=False)


def refresh_symbol(root: Path, symbol: str, downloader: Downloader, allow_download: bool) -> dict[str, Any]:
    before = qa_cache_file(root, symbol)
    timestamp = now_utc()
    if before["qa_status"] == "passed":
        return {
            "symbol": symbol,
            "status": "already_found",
            "provider": "none",
            "provider_api_called": False,
            "download_attempted": False,
            "download_status": "not_needed_cache_passed",
            "timestamp_utc": timestamp,
            "error": "",
        }
    if not allow_download:
        return {
            "symbol": symbol,
            "status": "missing_not_refreshed",
            "provider": "none",
            "provider_api_called": False,
            "download_attempted": False,
            "download_status": "not_attempted",
            "timestamp_utc": timestamp,
            "error": before["failure_reason"],
        }
    config = load_config(root)
    data_cfg = config.get("data", {})
    start = str(data_cfg.get("start_date", "2007-01-01"))
    end = data_cfg.get("end_date")
    params = data_cfg.get("yfinance", {})
    try:
        raw = downloader(symbol, start, end, params)
        if raw is None or raw.empty:
            raise DataQualityError("provider returned no rows")
        write_normalized_cache(root, symbol, raw)
        after = qa_cache_file(root, symbol)
        if after["qa_status"] != "passed":
            return {
                "symbol": symbol,
                "status": "refreshed_failed_qa",
                "provider": DATA_SOURCE_LABEL,
                "provider_api_called": True,
                "download_attempted": True,
                "download_status": "downloaded_fail",
                "timestamp_utc": timestamp,
                "error": after["failure_reason"],
            }
        return {
            "symbol": symbol,
            "status": "refreshed",
            "provider": DATA_SOURCE_LABEL,
            "provider_api_called": True,
            "download_attempted": True,
            "download_status": "downloaded_pass",
            "timestamp_utc": timestamp,
            "error": "",
        }
    except Exception as exc:
        return {
            "symbol": symbol,
            "status": "refresh_failed",
            "provider": DATA_SOURCE_LABEL,
            "provider_api_called": True,
            "download_attempted": True,
            "download_status": "downloaded_fail",
            "timestamp_utc": timestamp,
            "error": str(exc),
        }


def required_symbols_from_preregistration(root: Path) -> list[str]:
    batch = load_yaml(root / prereg.OUTPUT_DIR / "first_expansion_discovery_batch.yaml")
    symbols = {symbol for candidate in batch.get("candidates", []) for symbol in candidate.get("universe", [])}
    if not symbols:
        symbols = {"SPY", "QQQ", "IWM", "DIA", "XLK", "XLF", "XLV", "XLE", "XLI", "XLY", "XLP", "XLU", "XLB", "XLRE", "BIL"}
    symbols |= {"SPY", "QQQ", "BIL"}
    return sorted(symbols)


def full_required_symbol_coverage(root: Path) -> list[dict[str, Any]]:
    symbol_map = load_yaml(root / SYMBOL_MAP_PATH)
    map_rows = {str(row.get("symbol", "")).upper(): row for row in symbol_map.get("symbols", [])}
    rows: list[dict[str, Any]] = []
    for symbol in required_symbols_from_preregistration(root):
        qa = qa_cache_file(root, symbol)
        map_row = map_rows.get(symbol, {})
        approved_for_strategy = map_row.get("allowed_for_strategy") is True
        approved_for_benchmark = map_row.get("allowed_for_benchmark") is True
        missing_reasons: list[str] = []
        if not map_row:
            missing_reasons.append("not_in_approved_symbol_map")
        if not approved_for_strategy:
            missing_reasons.append("not_approved_for_strategy")
        if qa["qa_status"] != "passed":
            missing_reasons.append(qa["failure_reason"] or qa["cache_status"])
        rows.append(
            {
                **qa,
                "approved_for_strategy": approved_for_strategy,
                "approved_for_benchmark": approved_for_benchmark,
                "approved_status": map_row.get("approved_status", ""),
                "cache_ready": map_row.get("cache_ready", ""),
                "missing_reasons": ";".join(reason for reason in missing_reasons if reason),
                "available_for_first_expansion_batch": not missing_reasons,
            }
        )
    return rows


def translate_status_for_refresh(prereg_status: str) -> str:
    if prereg_status == "sufficient_for_discovery":
        return "sufficient_for_discovery"
    if prereg_status == "missing_required_data":
        return "still_missing_required_data"
    return "unknown_requires_manual_review"


def next_action_for_refresh(status_after: str, prereg_next_action: str) -> str:
    if status_after == "sufficient_for_discovery":
        return "run_first_expansion_discovery_batch"
    if prereg_next_action == "manual_data_review_required_for_first_expansion_batch":
        return prereg_next_action
    return "authorize_data_availability_or_cache_refresh_for_first_expansion_batch"


def report_md(manifest: dict[str, Any], refresh_rows: list[dict[str, Any]], coverage_rows: list[dict[str, Any]]) -> str:
    lines = [
        "# First Expansion Data Refresh Report",
        "",
        "This step refreshed or verified only `DIA` and `XLRE` daily adjusted OHLCV cache data through the existing yfinance-compatible adjusted ETF data convention.",
        "",
        f"Data availability status after refresh: `{manifest['data_availability_status_after_refresh']}`",
        f"Next action: `{manifest['next_action']}`",
        "",
        "## Authorized Refresh Symbols",
        "",
        "| Symbol | Status | Provider | Download attempted | Error |",
        "|---|---|---|---:|---|",
    ]
    for row in refresh_rows:
        lines.append(f"| {row['symbol']} | {row['status']} | {row['provider']} | {row['download_attempted']} | {row['error']} |")
    lines.extend(
        [
            "",
            "## Required Symbol Coverage",
            "",
            "| Symbol | Available | QA | First date | Last date | Rows | Missing reasons |",
            "|---|---:|---|---|---|---:|---|",
        ]
    )
    for row in coverage_rows:
        lines.append(
            f"| {row['symbol']} | {row['available_for_first_expansion_batch']} | {row['qa_status']} | {row['first_available_date']} | {row['last_available_date']} | {row['row_count']} | {row['missing_reasons'] or 'none'} |"
        )
    lines.extend(
        [
            "",
            "No strategy backtest, discovery run, performance metric, candidate exhaustive validation, paper-forward action, broker/live path, or real-money recommendation occurred.",
        ]
    )
    return "\n".join(lines) + "\n"


def availability_after_refresh_md(manifest: dict[str, Any], coverage_rows: list[dict[str, Any]]) -> str:
    lines = [
        "# First Expansion Data Availability After Refresh",
        "",
        f"Status: `{manifest['data_availability_status_after_refresh']}`",
        f"Next action: `{manifest['next_action']}`",
        "",
        "| Symbol | Approved | Cache ready | QA | Supports 10y minimum | First date | Last date |",
        "|---|---:|---:|---|---:|---|---|",
    ]
    for row in coverage_rows:
        lines.append(
            f"| {row['symbol']} | {row['approved_for_strategy']} | {row['cache_ready']} | {row['qa_status']} | {row['supports_minimum_backtest_period']} | {row['first_available_date']} | {row['last_available_date']} |"
        )
    return "\n".join(lines) + "\n"


def missing_after_refresh_md(manifest: dict[str, Any], coverage_rows: list[dict[str, Any]]) -> str:
    missing = [row for row in coverage_rows if not row["available_for_first_expansion_batch"]]
    uncertain_candidates = manifest.get("remaining_uncertain_candidates", [])
    lines = ["# First Expansion Missing Data After Refresh", ""]
    if missing:
        lines.extend(["Required data is still missing or failed schema/approval checks.", "", "| Symbol | Missing reasons |", "|---|---|"])
        for row in missing:
            lines.append(f"| {row['symbol']} | {row['missing_reasons']} |")
    else:
        lines.append("No required symbol is missing from the approved local daily cache after refresh.")
    if uncertain_candidates:
        lines.extend(
            [
                "",
                "At least one frozen candidate still requires manual review because required history may not satisfy its frozen minimum backtest-period gate.",
                "",
                "| Candidate | Period support | Missing symbols | Reason |",
                "|---|---|---|---|",
            ]
        )
        for row in uncertain_candidates:
            lines.append(
                f"| `{row['candidate_id']}` | {row['minimum_backtest_period_support']} | {', '.join(row['missing_symbols']) or 'none'} | {row['reason']} |"
            )
    return "\n".join(lines) + "\n"


def blocked_candidate_notes(root: Path) -> list[dict[str, Any]]:
    data_manifest = json.loads((root / prereg.OUTPUT_DIR / "first_expansion_data_availability_manifest.json").read_text(encoding="utf-8"))
    notes: list[dict[str, Any]] = []
    for row in data_manifest.get("candidate_status", []):
        if row.get("blocked_by_missing_data") is True:
            notes.append(
                {
                    "candidate_id": row.get("candidate_id", ""),
                    "minimum_backtest_period_support": row.get("minimum_backtest_period_support", ""),
                    "missing_symbols": row.get("missing_symbols", []),
                    "reason": "minimum_backtest_period_or_manual_review_required"
                    if not row.get("missing_symbols")
                    else "missing_required_symbols",
                }
            )
    return notes


def consistency_check(
    manifest: dict[str, Any],
    refresh_rows: list[dict[str, Any]],
    before_batch: dict[str, Any],
    after_batch: dict[str, Any],
) -> dict[str, Any]:
    before_candidates = before_batch.get("candidates", [])
    after_candidates = after_batch.get("candidates", [])
    fields = ["candidate_id", "entry_rule", "exit_rule", "sizing_rule", "benchmark_controls", "risk_controls", "universe"]
    before_projection = [{field: candidate.get(field) for field in fields} for candidate in before_candidates]
    after_projection = [{field: candidate.get(field) for field in fields} for candidate in after_candidates]
    downloaded_symbols = sorted(row["symbol"] for row in refresh_rows if row["download_attempted"])
    consistency = {
        "data_refresh_only": manifest["data_refresh_only"],
        "authorized_symbols_only": sorted(manifest["authorized_symbols"]) == AUTHORIZED_SYMBOLS,
        "downloaded_symbols_subset_authorized": set(downloaded_symbols) <= set(AUTHORIZED_SYMBOLS),
        "unrelated_symbols_downloaded": manifest["unrelated_symbols_downloaded"],
        "intraday_data_downloaded": manifest["intraday_data_downloaded"],
        "event_data_downloaded": manifest["event_data_downloaded"],
        "backtests_run": manifest["backtests_run"],
        "discovery_run": manifest["discovery_run"],
        "performance_metrics_computed": manifest["performance_metrics_computed"],
        "candidate_exhaustive_run": manifest["candidate_exhaustive_run"],
        "paper_forward_review": manifest["paper_forward_review"],
        "paper_forward_activation": manifest["paper_forward_activation"],
        "broker_path_touched": manifest["broker_path_touched"],
        "live_orders": manifest["live_orders"],
        "real_money_recommendation": manifest["real_money_recommendation"],
        "frozen_rules_changed": before_projection != after_projection,
        "candidate_universe_changed": [row["candidate_id"] for row in before_projection] != [row["candidate_id"] for row in after_projection],
        "benchmarks_changed": any(before.get("benchmark_controls") != after.get("benchmark_controls") for before, after in zip(before_projection, after_projection)),
        "active_strategy_state_changed": manifest["active_strategy_state_changed"],
        "etf_wrapper_track_reopened": manifest["etf_wrapper_track_reopened"],
        "five_included_candidates_unchanged": [candidate.get("candidate_id") for candidate in after_candidates] == prereg.AUTHORIZED_CANDIDATE_IDS,
        "excluded_candidates_remain_excluded": not (set(prereg.EXCLUDED_CANDIDATE_IDS) & {candidate.get("candidate_id") for candidate in after_candidates}),
        "intraday_candidates_remain_excluded": all(candidate.get("timeframe") != "intraday" for candidate in after_candidates),
        "event_data_candidate_remains_excluded": "post_earnings_drift_large_cap_later_v1" not in {candidate.get("candidate_id") for candidate in after_candidates},
    }
    consistency["consistency_passed"] = (
        consistency["data_refresh_only"]
        and consistency["authorized_symbols_only"]
        and consistency["downloaded_symbols_subset_authorized"]
        and not consistency["unrelated_symbols_downloaded"]
        and not consistency["intraday_data_downloaded"]
        and not consistency["event_data_downloaded"]
        and not consistency["backtests_run"]
        and not consistency["discovery_run"]
        and not consistency["performance_metrics_computed"]
        and not consistency["candidate_exhaustive_run"]
        and not consistency["paper_forward_review"]
        and not consistency["paper_forward_activation"]
        and not consistency["broker_path_touched"]
        and not consistency["live_orders"]
        and not consistency["real_money_recommendation"]
        and not consistency["frozen_rules_changed"]
        and not consistency["candidate_universe_changed"]
        and not consistency["benchmarks_changed"]
        and not consistency["active_strategy_state_changed"]
        and not consistency["etf_wrapper_track_reopened"]
        and consistency["five_included_candidates_unchanged"]
        and consistency["excluded_candidates_remain_excluded"]
        and consistency["intraday_candidates_remain_excluded"]
        and consistency["event_data_candidate_remains_excluded"]
    )
    return consistency


def run_first_expansion_data_availability_refresh(
    root: Path = ROOT,
    symbols: list[str] | None = None,
    downloader: Downloader | None = None,
    allow_download: bool = True,
) -> dict[str, Any]:
    created_utc = now_utc()
    output_dir = root / OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    symbols = validate_requested_symbols(symbols or AUTHORIZED_SYMBOLS)
    downloader = downloader or _download_yfinance

    before_batch = load_yaml(root / prereg.OUTPUT_DIR / "first_expansion_discovery_batch.yaml")
    ensure_symbol_map_authorization(root, created_utc, output_dir)

    refresh_rows = [refresh_symbol(root, symbol, downloader, allow_download=allow_download) for symbol in symbols]
    refreshed_symbol_coverage = [qa_cache_file(root, symbol) for symbol in symbols]
    update_symbol_map_after_qa(root, refreshed_symbol_coverage, output_dir)

    prereg_result = prereg.run_first_expansion_discovery_preregistration(root)
    after_batch = load_yaml(root / prereg.OUTPUT_DIR / "first_expansion_discovery_batch.yaml")
    prereg_status = str(prereg_result["data_availability_status"])
    status_after = translate_status_for_refresh(prereg_status)
    next_action = next_action_for_refresh(status_after, str(prereg_result["next_action"]))
    coverage_rows = full_required_symbol_coverage(root)
    blocked_candidates = blocked_candidate_notes(root)
    downloaded_symbols = sorted(row["symbol"] for row in refresh_rows if row["download_attempted"])

    manifest = {
        "artifact": "first_expansion_data_availability_refresh",
        "created_utc": created_utc,
        "output_dir": str(output_dir.resolve()),
        "data_refresh_only": True,
        "authorized_symbols": AUTHORIZED_SYMBOLS,
        "requested_symbols": symbols,
        "daily_adjusted_ohlcv_only": True,
        "provider_cache_mechanism": DATA_SOURCE_LABEL,
        "provider_api_called": any(bool(row["provider_api_called"]) for row in refresh_rows),
        "symbols_refreshed": [row["symbol"] for row in refresh_rows if row["status"] == "refreshed"],
        "symbols_already_found": [row["symbol"] for row in refresh_rows if row["status"] == "already_found"],
        "symbols_failed": [row["symbol"] for row in refresh_rows if row["status"] not in {"refreshed", "already_found"}],
        "downloaded_symbols": downloaded_symbols,
        "intraday_data_downloaded": False,
        "event_data_downloaded": False,
        "unrelated_symbols_downloaded": bool(set(downloaded_symbols) - set(AUTHORIZED_SYMBOLS)),
        "backtests_run": False,
        "discovery_run": False,
        "performance_metrics_computed": False,
        "candidate_exhaustive_run": False,
        "paper_forward_review": False,
        "paper_forward_activation": False,
        "broker_path_touched": False,
        "live_orders": False,
        "real_money_recommendation": False,
        "frozen_rules_changed": False,
        "candidate_universe_changed": False,
        "benchmarks_changed": False,
        "active_strategy_state_changed": False,
        "etf_wrapper_track_reopened": False,
        "data_availability_status_after_refresh": status_after,
        "pre_registration_data_availability_status": prereg_status,
        "remaining_missing_or_uncertain_data": [row["symbol"] for row in coverage_rows if not row["available_for_first_expansion_batch"]],
        "remaining_uncertain_candidates": blocked_candidates,
        "next_action": next_action,
    }
    consistency = consistency_check(manifest, refresh_rows, before_batch, after_batch)

    write_csv(
        output_dir / "first_expansion_symbol_coverage.csv",
        coverage_rows,
        [
            "symbol",
            "data_source_provider_used",
            "cache_path",
            "first_available_date",
            "last_available_date",
            "row_count",
            "required_ohlcv_columns",
            "adjusted_close_available",
            "missing_date_count_if_detectable",
            "duplicate_date_count",
            "null_count_by_required_column",
            "supports_minimum_backtest_period",
            "schema_matches_existing_daily_etf_data",
            "stale_data_status",
            "qa_status",
            "approved_for_strategy",
            "approved_for_benchmark",
            "approved_status",
            "cache_ready",
            "missing_reasons",
            "available_for_first_expansion_batch",
        ],
    )
    write_json(output_dir / "first_expansion_data_refresh_manifest.json", manifest)
    write_json(
        output_dir / "first_expansion_schema_validation.json",
        {
            "created_utc": created_utc,
            "expected_schema": NORMALIZED_COLUMNS,
            "authorized_symbol_validation": refreshed_symbol_coverage,
            "full_required_symbol_count": len(coverage_rows),
            "full_required_symbols": [row["symbol"] for row in coverage_rows],
        },
    )
    write_json(output_dir / "first_expansion_data_refresh_consistency_check.json", consistency)
    (output_dir / "first_expansion_data_refresh_report.md").write_text(report_md(manifest, refresh_rows, coverage_rows), encoding="utf-8")
    (output_dir / "first_expansion_data_availability_after_refresh.md").write_text(availability_after_refresh_md(manifest, coverage_rows), encoding="utf-8")
    (output_dir / "first_expansion_missing_data_after_refresh.md").write_text(missing_after_refresh_md(manifest, coverage_rows), encoding="utf-8")
    (output_dir / "first_expansion_next_action.md").write_text(f"# First Expansion Next Action\n\n`{next_action}`\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    result = run_first_expansion_data_availability_refresh(ROOT)
    print(
        json.dumps(
            {
                "output_dir": result["output_dir"],
                "symbols_refreshed": result["symbols_refreshed"],
                "symbols_already_found": result["symbols_already_found"],
                "symbols_failed": result["symbols_failed"],
                "data_availability_status_after_refresh": result["data_availability_status_after_refresh"],
                "remaining_missing_or_uncertain_data": result["remaining_missing_or_uncertain_data"],
                "next_action": result["next_action"],
            },
            indent=2,
        )
    )
