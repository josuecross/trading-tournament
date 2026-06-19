from __future__ import annotations

import argparse
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
POLICY_PATH = Path("strategy_lab") / "APPROVED_ETF_CACHE_POLICY.md"
SYMBOL_MAP_PATH = Path("strategy_lab") / "approved_etf_symbol_map.yaml"
OUTPUT_DIR = Path("evidence") / "approved_etf_cache_readiness" / "latest"
REQUIRED_WARMUP_ROWS = 252
Downloader = Callable[[str, str, str | None, dict[str, Any]], pd.DataFrame]

FORBIDDEN_SYMBOLS = {"AAPL", "MSFT", "BTC-USD", "ETH-USD", "ES=F", "NQ=F", "EURUSD=X", "SPXL", "SQQQ", "TQQQ"}
FAMILIES: dict[str, dict[str, Any]] = {
    "volatility_managed_equity_etf": {"required": ["SPY", "SPLV", "USMV", "QUAL", "BIL"], "optional": []},
    "defensive_sector_rotation_etf": {"required": ["XLK", "XLF", "XLE", "XLV", "XLY", "XLP", "XLU", "XLI", "XLB", "XLC", "BIL"], "optional": ["SPY"]},
    "global_risk_on_risk_off_etf": {"required": ["SPY", "QQQ", "GLD", "IEF", "BIL"], "optional": []},
    "quality_momentum_etf_proxy": {"required": ["MTUM", "VLUE", "VTV", "QUAL", "USMV", "SPLV", "SPY", "BIL"], "optional": []},
    "quality_momentum_etf_proxy_risk_control_batch_1": {"required": ["MTUM", "VLUE", "VTV", "QUAL", "USMV", "SPLV", "SPY", "BIL"], "optional": []},
    "managed_futures_etf_wrapper": {"required": ["DBMF", "KMLM", "CTA", "FMF", "WTMF", "SPY", "BIL"], "optional": []},
    "dual_momentum_paa_etf_wrapper": {"required": ["SPY", "QQQ", "EFA", "EEM", "IWM", "GLD", "IEF", "BIL"], "optional": []},
    "gtaa_faber_style_benchmark_lane": {"required": ["SPY", "QQQ", "EFA", "EEM", "IWM", "GLD", "IEF", "BIL"], "optional": []},
    "static_all_weather_or_permanent_portfolio_benchmark": {"required": ["SPY", "GLD", "IEF", "BIL"], "optional": []},
    "low_beta_defensive_equity_etf": {"required": ["USMV", "SPLV", "SPY", "BIL"], "optional": []},
    "dividend_quality_yield_etf": {"required": ["SCHD", "VIG", "DGRO", "SPY", "BIL"], "optional": []},
    "carry_yield_etf_proxy": {"required": ["HYG", "LQD", "EMB", "IEF", "BIL", "SPY"], "optional": []},
}
PRIOR_RESULTS: dict[str, dict[str, Any]] = {
    "gror_balanced_momentum_60_40_v1_candidate_exhaustive": {"family": "global_risk_on_risk_off_etf", "prior_status": "watchlist"},
    "managed_futures_etf_wrapper_research_sample": {"family": "managed_futures_etf_wrapper", "prior_status": "watchlist"},
    "dual_momentum_paa_etf_wrapper_research_sample": {"family": "dual_momentum_paa_etf_wrapper", "prior_status": "watchlist"},
    "parallel_research_discovery": {"family": "parallel_batch", "families": ["gtaa_faber_style_benchmark_lane", "static_all_weather_or_permanent_portfolio_benchmark", "low_beta_defensive_equity_etf", "dividend_quality_yield_etf", "carry_yield_etf_proxy"], "prior_status": "zero_promotions"},
    "dsr_sector_top2_momentum_200d_bil_v1_promotion_review": {"family": "defensive_sector_rotation_etf", "prior_status": "evidence_missing"},
    "quality_momentum_etf_proxy_research_sample": {"family": "quality_momentum_etf_proxy", "prior_status": "watchlist"},
    "quality_momentum_etf_proxy_risk_control_batch_1": {"family": "quality_momentum_etf_proxy_risk_control_batch_1", "prior_status": "watchlist"},
    "defensive_sector_rotation_etf_research_sample": {"family": "defensive_sector_rotation_etf", "prior_status": "conversation_recovered"},
    "volatility_managed_equity_etf_research_sample": {"family": "volatility_managed_equity_etf", "prior_status": "conversation_recovered"},
}


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def load_symbol_map(root: Path = ROOT) -> dict[str, Any]:
    data = load_yaml(root / SYMBOL_MAP_PATH)
    seen: set[str] = set()
    for row in data.get("symbols", []):
        symbol = str(row.get("symbol", "")).upper()
        if not symbol:
            raise ValueError("approved symbol map contains an empty symbol")
        if symbol in seen:
            raise ValueError(f"duplicate approved symbol: {symbol}")
        seen.add(symbol)
        if symbol in FORBIDDEN_SYMBOLS:
            raise ValueError(f"forbidden symbol cannot be approved: {symbol}")
    return data


def approved_rows(symbol_map: dict[str, Any]) -> list[dict[str, Any]]:
    return [{**row, "symbol": str(row["symbol"]).upper()} for row in symbol_map.get("symbols", [])]


def approved_symbols(symbol_map: dict[str, Any], include_explicit_only: bool = False) -> set[str]:
    symbols: set[str] = set()
    for row in approved_rows(symbol_map):
        default_enabled = row.get("enabled_by_default", True) is not False
        if not default_enabled and not include_explicit_only:
            continue
        if row.get("allowed_for_strategy") is True or row.get("allowed_for_benchmark") is True:
            symbols.add(row["symbol"])
    return symbols


def bootstrap_allowed_symbols(symbol_map: dict[str, Any]) -> set[str]:
    symbols: set[str] = set()
    for row in approved_rows(symbol_map):
        if row.get("enabled_by_default", True) is False:
            continue
        if row.get("allowed_for_strategy") is True:
            symbols.add(row["symbol"])
    return symbols


def cache_path(root: Path, symbol: str) -> Path:
    return root / "data" / "cache" / f"{symbol}.csv"


def load_config(root: Path) -> dict[str, Any]:
    path = root / "config.yaml"
    if not path.exists():
        return {"data": {"start_date": "2007-01-01", "end_date": None, "yfinance": {}}}
    return load_yaml(path)


def qa_cache_file(root: Path, symbol: str) -> dict[str, Any]:
    path = cache_path(root, symbol)
    row = {
        "symbol": symbol,
        "cache_available": path.exists(),
        "qa_status": "missing",
        "first_date": "",
        "last_date": "",
        "row_count": 0,
        "adjusted_close_exists": False,
        "adjusted_close_not_fully_empty": False,
        "duplicate_dates": "",
        "warmup_sufficiency": False,
        "missing_reason": "cache missing",
    }
    if not path.exists():
        return row
    try:
        frame = pd.read_csv(path)
    except Exception as exc:
        row["qa_status"] = "failed"
        row["missing_reason"] = f"cache read failed: {exc}"
        return row
    if "date" not in frame.columns or "adj_close" not in frame.columns:
        row["qa_status"] = "failed"
        row["missing_reason"] = "date or adj_close missing"
        return row
    dates = pd.to_datetime(frame["date"], errors="coerce").dt.tz_localize(None)
    close = pd.to_numeric(frame["adj_close"], errors="coerce")
    duplicate_dates = int(dates.dropna().duplicated().sum())
    valid_dates = dates.dropna()
    row.update(
        {
            "first_date": "" if valid_dates.empty else str(valid_dates.min().date()),
            "last_date": "" if valid_dates.empty else str(valid_dates.max().date()),
            "row_count": int(len(frame)),
            "adjusted_close_exists": True,
            "adjusted_close_not_fully_empty": bool(close.notna().any()),
            "duplicate_dates": duplicate_dates,
            "warmup_sufficiency": int(close.notna().sum()) >= REQUIRED_WARMUP_ROWS,
        }
    )
    passed = row["adjusted_close_not_fully_empty"] and duplicate_dates == 0 and row["warmup_sufficiency"]
    row["qa_status"] = "passed" if passed else "failed"
    row["missing_reason"] = "" if passed else "insufficient rows, duplicate dates, or empty adjusted close"
    return row


def bootstrap_symbol(root: Path, symbol: str, downloader: Downloader | None = None) -> dict[str, Any]:
    config = load_config(root)
    data_cfg = config.get("data", {})
    start = str(data_cfg.get("start_date", "2007-01-01"))
    end = data_cfg.get("end_date")
    params = data_cfg.get("yfinance", {})
    downloader = downloader or _download_yfinance
    timestamp = now_utc()
    log = {
        "symbol": symbol,
        "provider": "yfinance_compatible",
        "timestamp_utc": timestamp,
        "download_attempted": True,
        "download_status": "failed",
        "qa_status": "failed",
        "first_date": "",
        "last_date": "",
        "row_count": 0,
        "error": "",
    }
    try:
        raw = downloader(symbol, start, end, params)
        if raw is None or raw.empty:
            raise DataQualityError("provider returned no rows")
        normalized = build_adjusted_ohlc(raw, symbol)
        target = cache_path(root, symbol)
        target.parent.mkdir(parents=True, exist_ok=True)
        normalized.to_csv(target, index=False)
        qa = qa_cache_file(root, symbol)
        log.update(
            {
                "download_status": "downloaded",
                "qa_status": qa["qa_status"],
                "first_date": qa["first_date"],
                "last_date": qa["last_date"],
                "row_count": qa["row_count"],
                "error": qa["missing_reason"],
            }
        )
    except Exception as exc:
        log["error"] = str(exc)
    return log


def symbol_status_rows(root: Path, symbol_map: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for item in approved_rows(symbol_map):
        qa = qa_cache_file(root, item["symbol"])
        rows.append(
            {
                "symbol": item["symbol"],
                "group": item.get("group", ""),
                "allowed_for_strategy": item.get("allowed_for_strategy", False),
                "allowed_for_benchmark": item.get("allowed_for_benchmark", False),
                "requires_explicit_prompt": item.get("requires_explicit_prompt", False),
                "enabled_by_default": item.get("enabled_by_default", True),
                "cache_available": qa["cache_available"],
                "qa_status": qa["qa_status"],
                "first_date": qa["first_date"],
                "last_date": qa["last_date"],
                "row_count": qa["row_count"],
                "warmup_sufficiency": qa["warmup_sufficiency"],
                "missing_reason": qa["missing_reason"],
                "notes": item.get("notes", ""),
            }
        )
    return rows


def family_cache_readiness_rows(status_by_symbol: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for family, spec in FAMILIES.items():
        required = spec["required"]
        optional = spec.get("optional", [])
        present = [sym for sym in required if status_by_symbol.get(sym, {}).get("qa_status") == "passed"]
        missing = [sym for sym in required if status_by_symbol.get(sym, {}).get("qa_status") != "passed"]
        optional_missing = [sym for sym in optional if status_by_symbol.get(sym, {}).get("qa_status") != "passed"]
        if missing:
            readiness = "missing_required_symbols"
        elif optional_missing:
            readiness = "partial_optional_missing"
        elif family in {"volatility_managed_equity_etf", "defensive_sector_rotation_etf"}:
            readiness = "conversation_recovered_only"
        else:
            readiness = "ready"
        rows.append(
            {
                "family": family,
                "required_symbols": ";".join(required),
                "present_symbols": ";".join(present),
                "missing_symbols": ";".join(missing),
                "optional_missing_symbols": ";".join(optional_missing),
                "readiness_status": readiness,
            }
        )
    return rows


def prior_result_rows(family_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    readiness = {row["family"]: row for row in family_rows}
    rows = []
    for result_id, spec in PRIOR_RESULTS.items():
        families = spec.get("families") or [spec["family"]]
        family_statuses = [readiness.get(fam, {}) for fam in families]
        missing = sorted({sym for fam in family_statuses for sym in str(fam.get("missing_symbols", "")).split(";") if sym})
        statuses = {fam.get("readiness_status") for fam in family_statuses}
        prior_status = spec["prior_status"]
        if missing:
            classification = "data_missing_incomplete"
            reason = "Required cache symbols missing: " + ";".join(missing)
        elif prior_status == "evidence_missing":
            classification = "needs_rerun_after_cache_bootstrap"
            reason = "Prior result was evidence_missing but cache is now ready enough to rerun the bounded review."
        elif "conversation_recovered_only" in statuses or prior_status == "conversation_recovered":
            classification = "conversation_recovered_only"
            reason = "Recovered/conversation evidence only; cache readiness is separate from metric recomputation."
        elif prior_status == "watchlist":
            classification = "watchlist_valid"
            reason = "Watchlist is not invalidated by data readiness audit."
        else:
            classification = "data_ready_valid_result"
            reason = "Required cache is ready; no data-missing issue detected."
        rows.append(
            {
                "result_id": result_id,
                "families": ";".join(families),
                "prior_status": prior_status,
                "classification": classification,
                "missing_symbols": ";".join(missing),
                "reason": reason,
            }
        )
    return rows


def rerun_recommendation_rows(prior_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for row in prior_rows:
        result_id = row["result_id"]
        classification = row["classification"]
        if result_id == "dsr_sector_top2_momentum_200d_bil_v1_promotion_review":
            if classification == "needs_rerun_after_cache_bootstrap":
                issue = "Prior review was evidence_missing; required cache is now ready."
                recommended = True
                action = "rerun_dsr_sector_top2_promotion_review"
                priority = "high"
            else:
                issue = row["reason"]
                recommended = False
                action = "bootstrap_dsr_sector_etf_cache_before_dsr_top2_promotion_review"
                priority = "high"
        elif classification == "data_missing_incomplete":
            issue = row["reason"]
            recommended = False
            action = "bootstrap_approved_missing_cache_first"
            priority = "medium"
        elif classification == "conversation_recovered_only":
            issue = "Metrics are conversation-recovered only."
            recommended = True
            action = f"rerun_bounded_review_for_{result_id}"
            priority = "medium"
        else:
            issue = "No data-readiness rerun required."
            recommended = False
            action = "none"
            priority = "low"
        rows.append(
            {
                "result_or_family": result_id,
                "issue": issue,
                "rerun_recommended": recommended,
                "recommended_next_action": action,
                "priority": priority,
                "reason": row["reason"],
            }
        )
    return rows


def create_packet(directory: Path, name: str) -> Path:
    packet = directory / name
    if packet.exists():
        packet.unlink()
    with zipfile.ZipFile(packet, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(directory.iterdir()):
            if path.is_file() and path.name != packet.name:
                zf.write(path, path.name)
    return packet


def run_cache_readiness_audit(
    root: Path = ROOT,
    bootstrap_approved_missing: bool = False,
    downloader: Downloader | None = None,
) -> dict[str, Any]:
    symbol_map = load_symbol_map(root)
    output_dir = root / OUTPUT_DIR
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    before_status = symbol_status_rows(root, symbol_map)
    default_bootstrap_symbols = bootstrap_allowed_symbols(symbol_map)
    missing_before = [
        row for row in before_status
        if row["enabled_by_default"] is not False and row["allowed_for_strategy"] is True and row["qa_status"] != "passed"
    ]
    download_logs: list[dict[str, Any]] = []
    if bootstrap_approved_missing:
        for row in missing_before:
            symbol = row["symbol"]
            if symbol not in default_bootstrap_symbols:
                download_logs.append({"symbol": symbol, "provider": "none", "timestamp_utc": now_utc(), "download_attempted": False, "download_status": "blocked", "qa_status": row["qa_status"], "first_date": "", "last_date": "", "row_count": 0, "error": "symbol not allowed for bootstrap"})
                continue
            download_logs.append(bootstrap_symbol(root, symbol, downloader))
    else:
        download_logs = [
            {"symbol": row["symbol"], "provider": "none", "timestamp_utc": now_utc(), "download_attempted": False, "download_status": "not_attempted_audit_only", "qa_status": row["qa_status"], "first_date": row["first_date"], "last_date": row["last_date"], "row_count": row["row_count"], "error": ""}
            for row in missing_before
        ]

    status_rows = symbol_status_rows(root, symbol_map)
    missing_rows = [
        row for row in status_rows
        if row["enabled_by_default"] is not False and row["allowed_for_strategy"] is True and row["qa_status"] != "passed"
    ]
    data_quality_rows = [
        {
            "symbol": row["symbol"],
            "qa_status": row["qa_status"],
            "first_date": row["first_date"],
            "last_date": row["last_date"],
            "row_count": row["row_count"],
            "warmup_sufficiency": row["warmup_sufficiency"],
            "exploratory_non_institutional_not_real_money_ready": True,
            "institutional_grade_data": False,
            "notes": row["missing_reason"] or "basic QA passed",
        }
        for row in status_rows
    ]
    status_by_symbol = {row["symbol"]: row for row in status_rows}
    family_rows = family_cache_readiness_rows(status_by_symbol)
    prior_rows = prior_result_rows(family_rows)
    rerun_rows = rerun_recommendation_rows(prior_rows)

    downloaded_symbols = [row["symbol"] for row in download_logs if row["download_status"] == "downloaded"]
    failed_symbols = [row["symbol"] for row in download_logs if row["download_attempted"] is True and row["download_status"] != "downloaded"]
    forbidden_blocked = not (FORBIDDEN_SYMBOLS & approved_symbols(symbol_map, include_explicit_only=True))
    downloaded_only_approved = set(downloaded_symbols) <= default_bootstrap_symbols
    consistency = {
        "audit_completed": True,
        "approved_symbol_map_created": (root / SYMBOL_MAP_PATH).exists(),
        "audit_only_mode_supported": True,
        "bootstrap_mode_supported": True,
        "audit_only_did_not_download": not bootstrap_approved_missing and not downloaded_symbols,
        "bootstrap_downloaded_only_approved_symbols": downloaded_only_approved,
        "forbidden_symbols_blocked": forbidden_blocked,
        "no_strategy_run": True,
        "no_candidate_exhaustive_run": True,
        "no_paper_forward_activation": True,
        "no_broker_path_added": True,
        "no_live_order_path_added": True,
        "no_real_money_recommendation": True,
        "data_labeled_exploratory": True,
        "institutional_grade_data_false": True,
        "family_readiness_created": True,
        "prior_result_audit_created": True,
        "rerun_recommendations_created": True,
        "consistency_passed": False,
    }
    if bootstrap_approved_missing:
        consistency["audit_only_did_not_download"] = True
    consistency["consistency_passed"] = all(value is True for key, value in consistency.items() if key != "consistency_passed")

    write_csv(output_dir / "approved_symbol_cache_status.csv", status_rows, ["symbol", "group", "allowed_for_strategy", "allowed_for_benchmark", "requires_explicit_prompt", "enabled_by_default", "cache_available", "qa_status", "first_date", "last_date", "row_count", "warmup_sufficiency", "missing_reason", "notes"])
    write_csv(output_dir / "missing_approved_symbols.csv", missing_rows, ["symbol", "group", "allowed_for_strategy", "allowed_for_benchmark", "requires_explicit_prompt", "enabled_by_default", "cache_available", "qa_status", "first_date", "last_date", "row_count", "warmup_sufficiency", "missing_reason", "notes"])
    write_csv(output_dir / "bootstrap_download_log.csv", download_logs, ["symbol", "provider", "timestamp_utc", "download_attempted", "download_status", "qa_status", "first_date", "last_date", "row_count", "error"])
    write_csv(output_dir / "data_quality_summary.csv", data_quality_rows, ["symbol", "qa_status", "first_date", "last_date", "row_count", "warmup_sufficiency", "exploratory_non_institutional_not_real_money_ready", "institutional_grade_data", "notes"])
    write_csv(output_dir / "family_cache_readiness.csv", family_rows, ["family", "required_symbols", "present_symbols", "missing_symbols", "optional_missing_symbols", "readiness_status"])
    write_csv(output_dir / "prior_result_data_readiness_audit.csv", prior_rows, ["result_id", "families", "prior_status", "classification", "missing_symbols", "reason"])
    write_csv(output_dir / "rerun_recommendations.csv", rerun_rows, ["result_or_family", "issue", "rerun_recommended", "recommended_next_action", "priority", "reason"])
    manifest = {
        "created_at_utc": now_utc(),
        "mode": "bootstrap_approved_missing" if bootstrap_approved_missing else "audit_only",
        "approved_symbol_count": len(status_rows),
        "cached_symbols": [row["symbol"] for row in status_rows if row["qa_status"] == "passed"],
        "missing_symbols": [row["symbol"] for row in missing_rows],
        "downloaded_symbols": downloaded_symbols,
        "failed_symbols": failed_symbols,
        "provider_api_called": bool(downloaded_symbols or failed_symbols),
        "data_downloaded": bool(downloaded_symbols),
        "strategy_run": False,
        "candidate_exhaustive_run": False,
        "paper_forward_activation": False,
        "paper_forward_checkpoint": False,
        "broker_integration": False,
        "live_orders": False,
        "order_placement": False,
        "real_money_recommendation": False,
        "data_label": "exploratory_non_institutional_not_real_money_ready",
        "institutional_grade_data": False,
    }
    write_json(output_dir / "approved_etf_cache_readiness_manifest.json", manifest)
    write_json(output_dir / "approved_etf_cache_readiness_consistency_check.json", consistency)
    (output_dir / "approved_etf_cache_readiness_summary.md").write_text(
        "# Approved ETF Cache Readiness\n\n"
        f"Mode: `{manifest['mode']}`\n\n"
        f"Approved symbols audited: `{len(status_rows)}`\n\n"
        f"Cached/QA-passed symbols: `{len(manifest['cached_symbols'])}`\n\n"
        f"Missing approved strategy symbols: `{len(manifest['missing_symbols'])}`\n\n"
        f"Downloaded symbols: `{'; '.join(downloaded_symbols) if downloaded_symbols else 'none'}`\n\n"
        "Data label: `exploratory_non_institutional_not_real_money_ready`.\n\n"
        "No strategies, candidate_exhaustive runs, paper-forward activations/checkpoints, broker paths, live orders, or real-money recommendations were run or added.\n",
        encoding="utf-8",
    )
    create_packet(output_dir, "approved_etf_cache_readiness_packet.zip")
    return {
        "output_dir": str(output_dir),
        "mode": manifest["mode"],
        "cached_symbols": manifest["cached_symbols"],
        "missing_symbols": manifest["missing_symbols"],
        "downloaded_symbols": downloaded_symbols,
        "failed_symbols": failed_symbols,
        "family_rows": family_rows,
        "prior_rows": prior_rows,
        "rerun_rows": rerun_rows,
        "consistency": consistency,
        "manifest": manifest,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--audit-only", action="store_true")
    mode.add_argument("--bootstrap-approved-missing", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = run_cache_readiness_audit(ROOT, bootstrap_approved_missing=args.bootstrap_approved_missing)
    print(f"approved_etf_cache_readiness_latest_dir={result['output_dir']}")
    print(f"mode={result['mode']}")
    print(f"cached_symbols={';'.join(result['cached_symbols']) or 'none'}")
    print(f"missing_symbols={';'.join(result['missing_symbols']) or 'none'}")
    print(f"downloaded_symbols={';'.join(result['downloaded_symbols']) or 'none'}")
    print(f"failed_symbols={';'.join(result['failed_symbols']) or 'none'}")
    print(f"consistency_passed={str(result['consistency']['consistency_passed']).lower()}")
    return 0 if result["consistency"]["consistency_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
