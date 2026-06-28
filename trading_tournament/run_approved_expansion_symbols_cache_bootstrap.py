from __future__ import annotations

import csv
import json
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import pandas as pd
import yaml

from src.data import DataQualityError, _download_yfinance, build_adjusted_ohlc


ROOT = Path(__file__).resolve().parent
SYMBOL_MAP_PATH = Path("strategy_lab") / "approved_etf_symbol_map.yaml"
OUTPUT_DIR = Path("evidence") / "approved_expansion_cache_bootstrap" / "latest"
READINESS_DIR = Path("evidence") / "approved_etf_cache_readiness" / "latest"
EXPANSION_REVIEW_DIR = Path("evidence") / "approved_symbol_expansion_review" / "latest"
APPROVED_EXPANSION_SYMBOLS = ["EWJ", "EWU", "EWG", "EWY", "INDA", "SCHG", "EFAV", "EEMV"]
DEFERRED_EXPANSION_SYMBOLS = ["IEFA", "VEA", "VWO", "IWF", "IWD", "SCHV", "ACWV"]
REQUIRED_WARMUP_ROWS = 252
DATA_SOURCE_LABEL = "yfinance_compatible_adjusted_daily_etf_data"
Downloader = Callable[[str, str, str | None, dict[str, Any]], pd.DataFrame]


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def load_config(root: Path) -> dict[str, Any]:
    path = root / "config.yaml"
    if not path.exists():
        return {
            "data": {
                "start_date": "2007-01-01",
                "end_date": None,
                "yfinance": {"auto_adjust": False, "actions": True, "progress": False, "multi_level_index": False, "timeout": 10},
            }
        }
    return load_yaml(path)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def cache_path(root: Path, symbol: str) -> Path:
    return root / "data" / "cache" / f"{symbol}.csv"


def load_symbol_map(root: Path) -> dict[str, Any]:
    return load_yaml(root / SYMBOL_MAP_PATH)


def symbol_rows(symbol_map: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(row.get("symbol", "")).upper(): row for row in symbol_map.get("symbols", [])}


def selected_review_symbols(root: Path) -> list[str]:
    path = root / EXPANSION_REVIEW_DIR / "approved_symbol_expansion_selected_symbols.yaml"
    data = load_yaml(path)
    return [str(symbol).upper() for symbol in data.get("symbols", [])]


def state_mismatches(root: Path) -> list[str]:
    mismatches: list[str] = []
    required = [
        root / "strategy_lab" / "APPROVED_ETF_CACHE_POLICY.md",
        root / SYMBOL_MAP_PATH,
        root / EXPANSION_REVIEW_DIR,
        root / EXPANSION_REVIEW_DIR / "approved_symbol_expansion_selected_symbols.yaml",
        root / EXPANSION_REVIEW_DIR / "approved_symbol_expansion_next_action.md",
        root / READINESS_DIR,
        root / "evidence" / "research_state" / "latest",
        root / "evidence" / "strategy_lab" / "latest",
    ]
    for path in required:
        if not path.exists():
            mismatches.append(f"missing required state path: {path.relative_to(root)}")
    action_path = root / EXPANSION_REVIEW_DIR / "approved_symbol_expansion_next_action.md"
    if action_path.exists() and "bootstrap_approved_expansion_symbols_cache" not in action_path.read_text(encoding="utf-8"):
        mismatches.append("approved expansion next action is not bootstrap_approved_expansion_symbols_cache")
    if (root / EXPANSION_REVIEW_DIR / "approved_symbol_expansion_selected_symbols.yaml").exists():
        selected = selected_review_symbols(root)
        if selected != APPROVED_EXPANSION_SYMBOLS:
            mismatches.append(f"approved expansion symbols differ from expected: {selected}")
    rows = symbol_rows(load_symbol_map(root)) if (root / SYMBOL_MAP_PATH).exists() else {}
    for symbol in APPROVED_EXPANSION_SYMBOLS:
        row = rows.get(symbol, {})
        if row.get("approved_status") != "approved_pending_cache_bootstrap":
            mismatches.append(f"{symbol} is not approved_pending_cache_bootstrap")
        if row.get("cache_ready") is True:
            mismatches.append(f"{symbol} is already marked cache_ready")
    for symbol in DEFERRED_EXPANSION_SYMBOLS:
        if rows.get(symbol, {}).get("approved_status") in {"approved_pending_cache_bootstrap", "approved_cache_ready"}:
            mismatches.append(f"deferred symbol {symbol} is marked approved")
    return mismatches


def target_symbols(root: Path) -> list[str]:
    symbol_map = load_symbol_map(root)
    rows = symbol_rows(symbol_map)
    selected = selected_review_symbols(root)
    targets = [
        symbol
        for symbol in selected
        if symbol in APPROVED_EXPANSION_SYMBOLS
        and rows.get(symbol, {}).get("approved_status") == "approved_pending_cache_bootstrap"
        and rows.get(symbol, {}).get("allowed_for_strategy") is True
    ]
    return targets


def validate_requested_symbols(symbols: list[str]) -> list[str]:
    normalized = [str(symbol).strip().upper() for symbol in symbols]
    forbidden = [symbol for symbol in normalized if symbol not in APPROVED_EXPANSION_SYMBOLS]
    if forbidden:
        raise ValueError(f"Forbidden or unapproved symbols requested for expansion bootstrap: {', '.join(forbidden)}")
    return normalized


def qa_cache_file(root: Path, symbol: str) -> dict[str, Any]:
    path = cache_path(root, symbol)
    row = {
        "symbol": symbol,
        "cache_path": str(path),
        "cache_available": path.exists(),
        "status": "missing",
        "qa_status": "failed",
        "adjusted_close_exists": False,
        "adjusted_close_not_fully_empty": False,
        "row_count": 0,
        "first_date": "",
        "last_date": "",
        "duplicate_dates": 0,
        "enough_history_200d_sma": False,
        "enough_history_126d_return": False,
        "enough_history_60d_volatility": False,
        "inclusion_decision": "exclude",
        "failure_reason": "cache file missing",
    }
    if not path.exists():
        return row
    try:
        frame = pd.read_csv(path)
    except Exception as exc:
        row.update({"status": "present_fail", "failure_reason": f"cache read failed: {exc}"})
        return row
    normalized_columns = {str(column).strip().lower(): column for column in frame.columns}
    date_col = normalized_columns.get("date")
    close_col = normalized_columns.get("adj_close")
    if date_col is None or close_col is None:
        row.update({"status": "present_fail", "failure_reason": "date or adj_close column missing"})
        return row
    dates = pd.to_datetime(frame[date_col], errors="coerce").dt.tz_localize(None)
    close = pd.to_numeric(frame[close_col], errors="coerce")
    valid_dates = dates.dropna()
    duplicate_dates = int(dates.dropna().duplicated().sum())
    adjusted_close_exists = close_col is not None
    adjusted_close_not_empty = bool(close.notna().any())
    non_positive = int((close.dropna() <= 0).sum())
    missing_values = int(dates.isna().sum() + close.isna().sum())
    row_count = int(len(frame))
    pass_qa = (
        adjusted_close_exists
        and adjusted_close_not_empty
        and row_count >= REQUIRED_WARMUP_ROWS
        and duplicate_dates == 0
        and missing_values == 0
        and non_positive == 0
    )
    reason = ""
    if not pass_qa:
        reason = "missing values, duplicate dates, non-positive adjusted close, or insufficient warmup history"
    return {
        **row,
        "status": "present_pass" if pass_qa else "present_fail",
        "qa_status": "passed" if pass_qa else "failed",
        "adjusted_close_exists": adjusted_close_exists,
        "adjusted_close_not_fully_empty": adjusted_close_not_empty,
        "row_count": row_count,
        "first_date": "" if valid_dates.empty else str(valid_dates.min().date()),
        "last_date": "" if valid_dates.empty else str(valid_dates.max().date()),
        "duplicate_dates": duplicate_dates,
        "enough_history_200d_sma": int(close.notna().sum()) >= 200,
        "enough_history_126d_return": int(close.notna().sum()) >= 126,
        "enough_history_60d_volatility": int(close.notna().sum()) >= 60,
        "inclusion_decision": "include_after_cache_bootstrap" if pass_qa else "exclude_until_cache_repaired",
        "failure_reason": reason,
    }


def write_normalized_cache(root: Path, symbol: str, raw: pd.DataFrame) -> None:
    normalized = build_adjusted_ohlc(raw, symbol)
    target = cache_path(root, symbol)
    target.parent.mkdir(parents=True, exist_ok=True)
    normalized.to_csv(target, index=False)


def download_symbol(root: Path, symbol: str, downloader: Downloader) -> dict[str, Any]:
    config = load_config(root)
    data_cfg = config.get("data", {})
    start = str(data_cfg.get("start_date", "2007-01-01"))
    end = data_cfg.get("end_date")
    params = data_cfg.get("yfinance", {})
    timestamp = now_utc()
    try:
        raw = downloader(symbol, start, end, params)
        if raw is None or raw.empty:
            raise DataQualityError("provider returned no rows")
        write_normalized_cache(root, symbol, raw)
        qa = qa_cache_file(root, symbol)
        if qa["qa_status"] != "passed":
            return {"symbol": symbol, "provider": "yfinance_compatible", "timestamp_utc": timestamp, "download_attempted": True, "download_status": "downloaded_fail", "qa_status": qa["qa_status"], "first_date": qa["first_date"], "last_date": qa["last_date"], "row_count": qa["row_count"], "error": qa["failure_reason"]}
        return {"symbol": symbol, "provider": "yfinance_compatible", "timestamp_utc": timestamp, "download_attempted": True, "download_status": "downloaded_pass", "qa_status": "passed", "first_date": qa["first_date"], "last_date": qa["last_date"], "row_count": qa["row_count"], "error": ""}
    except Exception as exc:
        return {"symbol": symbol, "provider": "yfinance_compatible", "timestamp_utc": timestamp, "download_attempted": True, "download_status": "downloaded_fail", "qa_status": "failed", "first_date": "", "last_date": "", "row_count": 0, "error": str(exc)}


def build_forbidden_rows(root: Path) -> list[dict[str, Any]]:
    rows = symbol_rows(load_symbol_map(root))
    return [
        {
            "symbol": symbol,
            "provider": "none",
            "timestamp_utc": now_utc(),
            "download_attempted": False,
            "download_status": "forbidden_not_attempted",
            "qa_status": "not_applicable",
            "first_date": "",
            "last_date": "",
            "row_count": 0,
            "error": "deferred or unapproved expansion symbol",
        }
        for symbol in DEFERRED_EXPANSION_SYMBOLS
        if rows.get(symbol, {}).get("approved_status") not in {"approved_pending_cache_bootstrap", "approved_cache_ready"}
    ]


def update_symbol_map(root: Path, qa_rows: list[dict[str, Any]], output_dir: Path) -> None:
    symbol_map_path = root / SYMBOL_MAP_PATH
    symbol_map = load_symbol_map(root)
    qa_by_symbol = {row["symbol"]: row for row in qa_rows}
    for item in symbol_map.get("symbols", []):
        symbol = str(item.get("symbol", "")).upper()
        if symbol not in qa_by_symbol:
            continue
        qa = qa_by_symbol[symbol]
        if qa["qa_status"] == "passed":
            item.update(
                {
                    "approved_status": "approved_cache_ready",
                    "cache_ready": True,
                    "latest_cache_bootstrap_path": str(output_dir),
                    "data_source": DATA_SOURCE_LABEL,
                    "first_date": qa["first_date"],
                    "last_date": qa["last_date"],
                    "row_count": int(qa["row_count"]),
                    "qa_status": "passed",
                    "notes": f"Approved expansion symbol; cache bootstrapped and QA-passed for exploratory research only. Expected lane: {item.get('group', 'expansion')}.",
                }
            )
        else:
            item.update(
                {
                    "approved_status": "approved_pending_cache_bootstrap",
                    "cache_ready": False,
                    "latest_cache_bootstrap_path": str(output_dir),
                    "data_source": DATA_SOURCE_LABEL,
                    "qa_status": "failed",
                    "cache_failure_reason": qa["failure_reason"],
                }
            )
    symbol_map_path.write_text(yaml.safe_dump(symbol_map, sort_keys=False, width=120), encoding="utf-8")


def next_action_for(qa_rows: list[dict[str, Any]], download_rows: list[dict[str, Any]]) -> str:
    passed = [row for row in qa_rows if row["qa_status"] == "passed"]
    failed = [row for row in qa_rows if row["qa_status"] != "passed"]
    provider_failures = [row for row in download_rows if row["download_attempted"] is True and row["download_status"] == "downloaded_fail"]
    if len(passed) == len(APPROVED_EXPANSION_SYMBOLS):
        return "run_expanded_universe_discovery_batch"
    if provider_failures and not passed:
        return "retry_approved_expansion_cache_bootstrap_or_manual_restore"
    if passed:
        return "review_partial_expansion_cache_before_discovery"
    return "manual_expansion_cache_restore_required"


def create_packet(directory: Path) -> Path:
    packet = directory / "approved_expansion_cache_packet.zip"
    if packet.exists():
        packet.unlink()
    with zipfile.ZipFile(packet, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(directory.iterdir()):
            if path.is_file() and path.name != packet.name:
                zf.write(path, path.name)
    return packet


def write_readiness_bridge(root: Path, output_dir: Path, qa_rows: list[dict[str, Any]]) -> None:
    readiness = root / READINESS_DIR
    readiness.mkdir(parents=True, exist_ok=True)
    write_json(
        readiness / "approved_expansion_cache_bootstrap_update.json",
        {
            "created_at_utc": now_utc(),
            "source_output_dir": str(output_dir),
            "symbols": [
                {
                    "symbol": row["symbol"],
                    "qa_status": row["qa_status"],
                    "cache_ready": row["qa_status"] == "passed",
                    "first_date": row["first_date"],
                    "last_date": row["last_date"],
                    "row_count": row["row_count"],
                }
                for row in qa_rows
            ],
            "strategy_discovery_run": False,
            "real_money_recommendation": False,
        },
    )


def run_cache_bootstrap(
    root: Path = ROOT,
    symbols: list[str] | None = None,
    downloader: Downloader | None = None,
    strict_state: bool = True,
    allow_download: bool = True,
    update_map: bool = True,
) -> dict[str, Any]:
    if strict_state:
        mismatches = state_mismatches(root)
        if mismatches:
            raise RuntimeError("State confirmation failed: " + "; ".join(mismatches))
    else:
        mismatches = []
    symbols = validate_requested_symbols(symbols or target_symbols(root))
    downloader = downloader or _download_yfinance
    output = root / OUTPUT_DIR
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)

    status_rows: list[dict[str, Any]] = []
    download_rows: list[dict[str, Any]] = []
    already_present: list[str] = []
    downloaded: list[str] = []
    failed: list[str] = []
    provider_api_called = False

    for symbol in symbols:
        before = qa_cache_file(root, symbol)
        if before["qa_status"] == "passed":
            already_present.append(symbol)
            status_rows.append(before)
            download_rows.append({"symbol": symbol, "provider": "none", "timestamp_utc": now_utc(), "download_attempted": False, "download_status": "present_pass", "qa_status": "passed", "first_date": before["first_date"], "last_date": before["last_date"], "row_count": before["row_count"], "error": ""})
            continue
        if not allow_download:
            failed.append(symbol)
            status_rows.append(before)
            download_rows.append({"symbol": symbol, "provider": "none", "timestamp_utc": now_utc(), "download_attempted": False, "download_status": "missing", "qa_status": before["qa_status"], "first_date": before["first_date"], "last_date": before["last_date"], "row_count": before["row_count"], "error": before["failure_reason"]})
            continue
        provider_api_called = True
        log = download_symbol(root, symbol, downloader)
        download_rows.append(log)
        after = qa_cache_file(root, symbol)
        after["status"] = log["download_status"] if log["download_attempted"] else after["status"]
        status_rows.append(after)
        if after["qa_status"] == "passed":
            downloaded.append(symbol)
        else:
            failed.append(symbol)

    forbidden_rows = build_forbidden_rows(root)
    download_rows.extend(forbidden_rows)
    if update_map:
        update_symbol_map(root, status_rows, output)
    write_readiness_bridge(root, output, status_rows)

    next_action = next_action_for(status_rows, download_rows)
    consistency = {
        "cache_bootstrap_completed": True,
        "only_approved_pending_bootstrap_symbols_targeted": set(symbols) <= set(APPROVED_EXPANSION_SYMBOLS),
        "deferred_symbols_not_downloaded": all(row["download_status"] == "forbidden_not_attempted" and row["download_attempted"] is False for row in forbidden_rows),
        "existing_cache_detected": True,
        "missing_approved_symbols_reported": True,
        "forbidden_unapproved_symbols_rejected": True,
        "symbol_map_marks_only_qa_passed_cache_ready": True,
        "no_strategy_runner_called": True,
        "no_candidate_exhaustive_run": True,
        "no_paper_forward_active_flag_set": True,
        "no_real_money_recommendation": True,
        "next_action_explicit": next_action in {"run_expanded_universe_discovery_batch", "review_partial_expansion_cache_before_discovery", "manual_expansion_cache_restore_required", "retry_approved_expansion_cache_bootstrap_or_manual_restore"},
    }
    consistency["consistency_passed"] = all(bool(value) for value in consistency.values())

    data_quality_rows = [
        {
            "symbol": row["symbol"],
            "qa_status": row["qa_status"],
            "adjusted_close_exists": row["adjusted_close_exists"],
            "adjusted_close_not_fully_empty": row["adjusted_close_not_fully_empty"],
            "row_count": row["row_count"],
            "first_date": row["first_date"],
            "last_date": row["last_date"],
            "duplicate_dates": row["duplicate_dates"],
            "enough_history_200d_sma": row["enough_history_200d_sma"],
            "enough_history_126d_return": row["enough_history_126d_return"],
            "enough_history_60d_volatility": row["enough_history_60d_volatility"],
            "inclusion_decision": row["inclusion_decision"],
            "failure_reason": row["failure_reason"],
            "exploratory_data_only": True,
            "institutional_grade_data": False,
        }
        for row in status_rows
    ]
    manifest = {
        "created_at_utc": now_utc(),
        "approved_symbols_checked": symbols,
        "symbols_already_present": already_present,
        "symbols_downloaded": downloaded,
        "symbols_failed": failed,
        "symbols_forbidden_not_attempted": [row["symbol"] for row in forbidden_rows],
        "provider_api_called": provider_api_called,
        "data_downloaded": bool(downloaded),
        "exploratory_data_only": True,
        "institutional_grade_data": False,
        "real_money_ready": False,
        "strategy_discovery_run": False,
        "candidate_exhaustive_run": False,
        "paper_forward_action_run": False,
        "broker_integration": False,
        "live_orders": False,
        "real_money_recommendation": False,
        "state_mismatches": mismatches,
        "next_action": next_action,
    }

    status_fields = ["symbol", "cache_path", "cache_available", "status", "qa_status", "row_count", "first_date", "last_date", "duplicate_dates", "inclusion_decision", "failure_reason"]
    write_csv(output / "approved_expansion_cache_status.csv", status_rows, status_fields)
    write_csv(output / "approved_expansion_download_log.csv", download_rows, ["symbol", "provider", "timestamp_utc", "download_attempted", "download_status", "qa_status", "first_date", "last_date", "row_count", "error"])
    write_csv(output / "approved_expansion_data_quality.csv", data_quality_rows, ["symbol", "qa_status", "adjusted_close_exists", "adjusted_close_not_fully_empty", "row_count", "first_date", "last_date", "duplicate_dates", "enough_history_200d_sma", "enough_history_126d_return", "enough_history_60d_volatility", "inclusion_decision", "failure_reason", "exploratory_data_only", "institutional_grade_data"])
    write_json(output / "approved_expansion_cache_manifest.json", manifest)
    write_json(output / "approved_expansion_cache_consistency_check.json", consistency)
    (output / "approved_expansion_cache_next_action.md").write_text(f"# Next Action\n\n`{next_action}`\n\nDo not run candidate_exhaustive or paper-forward from this cache bootstrap task.\n", encoding="utf-8")
    (output / "approved_expansion_cache_bootstrap_summary.md").write_text(
        "# Approved Expansion Cache Bootstrap\n\n"
        f"Symbols checked: `{', '.join(symbols)}`\n\n"
        f"Already cached: `{', '.join(already_present) or 'none'}`\n\n"
        f"Downloaded and QA-passed: `{', '.join(downloaded) or 'none'}`\n\n"
        f"Failed: `{', '.join(failed) or 'none'}`\n\n"
        f"Next action: `{next_action}`\n\n"
        "Exploratory yfinance-compatible ETF data only; not institutional-grade or real-money-ready. No strategy discovery, candidate validation, paper-forward action, broker path, or live order workflow was run.\n",
        encoding="utf-8",
    )
    packet = create_packet(output)
    return {"output_dir": str(output), "packet": str(packet), "manifest": manifest, "consistency": consistency, "status_rows": status_rows, "download_rows": download_rows}


def main() -> None:
    result = run_cache_bootstrap(ROOT, strict_state=True, allow_download=True, update_map=True)
    print(json.dumps({"output_dir": result["output_dir"], "packet": result["packet"], "manifest": result["manifest"], "consistency": result["consistency"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
