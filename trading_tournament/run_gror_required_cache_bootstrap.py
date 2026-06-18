from __future__ import annotations

import csv
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import pandas as pd
import yaml

from src.data import DataQualityError, _download_yfinance, build_adjusted_ohlc


ROOT = Path(__file__).resolve().parent
APPROVED_SYMBOLS = ["SPY", "QQQ", "GLD", "IEF", "BIL"]
OUTPUT_ROOT = Path("evidence") / "data_cache_bootstrap" / "gror_required"
REQUIRED_WARMUP_ROWS = 381
DATA_SOURCE_LABEL = "yfinance_compatible_adjusted_daily_etf_data"

FORBIDDEN_FLAGS = {
    "paper_forward_activation": False,
    "paper_forward_checkpoint": False,
    "real_money_recommendation": False,
    "broker_integration": False,
    "live_orders": False,
    "order_placement": False,
    "leverage": False,
    "margin": False,
    "shorting": False,
    "options": False,
    "futures": False,
    "forex": False,
    "crypto": False,
    "intraday": False,
    "parameter_optimization": False,
    "grid_search": False,
    "strategy_validation_run": False,
}

REQUIRED_OUTPUTS = [
    "cache_bootstrap_summary.md",
    "cache_status.csv",
    "download_log.csv",
    "data_quality.csv",
    "cache_bootstrap_manifest.json",
    "cache_bootstrap_consistency_check.json",
]

Downloader = Callable[[str, str, str | None, dict[str, Any]], pd.DataFrame]


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def sha256_file(path: Path) -> str:
    if not path.exists():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cache_path(root: Path, symbol: str) -> Path:
    return root / "data" / "cache" / f"{symbol}.csv"


def validate_symbols(symbols: list[str]) -> list[str]:
    normalized = [str(symbol).upper().strip() for symbol in symbols]
    forbidden = [symbol for symbol in normalized if symbol not in APPROVED_SYMBOLS]
    if forbidden:
        raise ValueError(f"Forbidden symbols requested for GROR cache bootstrap: {', '.join(forbidden)}")
    return normalized


def load_config(root: Path) -> dict[str, Any]:
    path = root / "config.yaml"
    if not path.exists():
        return {
            "data": {
                "start_date": "2007-01-01",
                "end_date": None,
                "yfinance": {
                    "auto_adjust": False,
                    "actions": True,
                    "progress": False,
                    "multi_level_index": False,
                    "timeout": 10,
                },
            }
        }
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def qa_cache_file(root: Path, symbol: str) -> dict[str, Any]:
    path = cache_path(root, symbol)
    base = {
        "symbol": symbol,
        "cache_file": str(path),
        "cache_file_exists": path.exists(),
        "cache_file_hash": sha256_file(path),
        "first_date": "",
        "last_date": "",
        "row_count": 0,
        "adjusted_close_availability": False,
        "missing_values": "",
        "duplicate_dates": "",
        "impossible_ohlc_values": "",
        "warmup_sufficiency": False,
        "qa_passed": False,
        "reason_for_failure": "",
    }
    if not path.exists():
        base["reason_for_failure"] = "cache file missing"
        return base

    try:
        frame = pd.read_csv(path)
    except Exception as exc:
        base["reason_for_failure"] = f"cache read failed: {exc}"
        return base

    normalized_columns = {str(column).strip().lower(): column for column in frame.columns}
    date_col = normalized_columns.get("date")
    close_col = normalized_columns.get("adj_close")
    if date_col is None or close_col is None:
        base["reason_for_failure"] = "required date or adj_close column missing"
        return base

    dates = pd.to_datetime(frame[date_col], errors="coerce").dt.tz_localize(None)
    close = pd.to_numeric(frame[close_col], errors="coerce")
    duplicate_dates = int(dates.dropna().duplicated().sum())
    missing_values = int(dates.isna().sum() + close.isna().sum())
    impossible_values = int((close <= 0).sum())
    valid_dates = dates.dropna()
    row_count = int(len(frame))
    warmup = int(close.dropna().shape[0]) >= REQUIRED_WARMUP_ROWS
    qa_passed = (
        row_count >= REQUIRED_WARMUP_ROWS
        and missing_values == 0
        and duplicate_dates == 0
        and impossible_values == 0
        and warmup
    )
    reason = ""
    if not qa_passed:
        reason = "missing, duplicate, non-positive, or insufficient adjusted close history"

    return {
        **base,
        "first_date": "" if valid_dates.empty else str(valid_dates.min().date()),
        "last_date": "" if valid_dates.empty else str(valid_dates.max().date()),
        "row_count": row_count,
        "adjusted_close_availability": True,
        "missing_values": missing_values,
        "duplicate_dates": duplicate_dates,
        "impossible_ohlc_values": impossible_values,
        "warmup_sufficiency": warmup,
        "qa_passed": qa_passed,
        "reason_for_failure": reason,
    }


def write_normalized_cache(root: Path, symbol: str, raw: pd.DataFrame) -> None:
    normalized = build_adjusted_ohlc(raw, symbol)
    target = cache_path(root, symbol)
    target.parent.mkdir(parents=True, exist_ok=True)
    normalized.to_csv(target, index=False)


def render_summary(
    manifest: dict[str, Any],
    quality_rows: list[dict[str, Any]],
    download_rows: list[dict[str, Any]],
) -> str:
    passed = [row["symbol"] for row in quality_rows if row["qa_passed"]]
    failed = [row["symbol"] for row in quality_rows if not row["qa_passed"]]
    provider = "yes" if manifest["provider_api_called"] else "no"
    return "\n".join(
        [
            "# GROR Required Cache Bootstrap",
            "",
            f"Run id: `{manifest['run_id']}`",
            f"Data source: `{manifest['data_source']}`",
            "",
            "Scope:",
            "",
            "- Research-only adjusted daily ETF/fund-wrapper cache bootstrap.",
            "- Exploratory data only; not institutional-grade data.",
            "- Not real-money ready and not a broker/live-order path.",
            f"- Provider API called: `{provider}`.",
            "",
            "Symbols:",
            "",
            f"- Checked: `{', '.join(manifest['symbols_checked'])}`",
            f"- Already present and QA-passing: `{', '.join(manifest['symbols_already_present']) or 'none'}`",
            f"- Downloaded: `{', '.join(manifest['symbols_downloaded']) or 'none'}`",
            f"- Failed: `{', '.join(manifest['symbols_failed']) or 'none'}`",
            "",
            "QA:",
            "",
            f"- Passed: `{', '.join(passed) or 'none'}`",
            f"- Failed: `{', '.join(failed) or 'none'}`",
            "",
            "Download Log:",
            "",
            *[
                f"- {row['symbol']}: {row['status']} ({row['detail']})"
                for row in download_rows
            ],
            "",
        ]
    )


def run_cache_bootstrap(
    root: Path = ROOT,
    symbols: list[str] | None = None,
    run_id: str | None = None,
    downloader: Downloader | None = None,
    allow_download: bool = True,
) -> dict[str, Any]:
    symbols = validate_symbols(symbols or APPROVED_SYMBOLS)
    run_id = run_id or utc_run_id()
    config = load_config(root)
    data_cfg = config.get("data", {})
    start = str(data_cfg.get("start_date", "2007-01-01"))
    end = data_cfg.get("end_date")
    yfinance_params = data_cfg.get("yfinance", {})
    downloader = downloader or _download_yfinance

    run_dir = root / OUTPUT_ROOT / "runs" / run_id
    latest_dir = root / OUTPUT_ROOT / "latest"
    run_dir.mkdir(parents=True, exist_ok=True)

    symbols_already_present: list[str] = []
    symbols_downloaded: list[str] = []
    symbols_failed: list[str] = []
    provider_api_called = False
    download_rows: list[dict[str, Any]] = []

    for symbol in symbols:
        before = qa_cache_file(root, symbol)
        if before["qa_passed"]:
            symbols_already_present.append(symbol)
            download_rows.append(
                {
                    "symbol": symbol,
                    "status": "skipped_existing_cache",
                    "provider_api_called": False,
                    "detail": "existing adjusted cache passed QA",
                }
            )
            continue

        if not allow_download:
            symbols_failed.append(symbol)
            download_rows.append(
                {
                    "symbol": symbol,
                    "status": "failed_no_download",
                    "provider_api_called": False,
                    "detail": before["reason_for_failure"],
                }
            )
            continue

        provider_api_called = True
        try:
            raw = downloader(symbol, start, end, yfinance_params)
            if raw is None or raw.empty:
                raise DataQualityError("provider returned no rows")
            write_normalized_cache(root, symbol, raw)
            after = qa_cache_file(root, symbol)
            if not after["qa_passed"]:
                raise DataQualityError(str(after["reason_for_failure"]))
            symbols_downloaded.append(symbol)
            download_rows.append(
                {
                    "symbol": symbol,
                    "status": "downloaded",
                    "provider_api_called": True,
                    "detail": "downloaded and normalized adjusted cache passed QA",
                }
            )
        except Exception as exc:
            symbols_failed.append(symbol)
            download_rows.append(
                {
                    "symbol": symbol,
                    "status": "failed_download_or_qa",
                    "provider_api_called": True,
                    "detail": str(exc),
                }
            )

    quality_rows = [qa_cache_file(root, symbol) for symbol in symbols]
    all_required_symbols_passed_qa = all(row["qa_passed"] for row in quality_rows)
    output_files = [run_dir / name for name in REQUIRED_OUTPUTS]
    manifest = {
        "run_id": run_id,
        "created_at_utc": now_utc(),
        "data_source": DATA_SOURCE_LABEL,
        "symbols_checked": symbols,
        "symbols_already_present": symbols_already_present,
        "symbols_downloaded": symbols_downloaded,
        "symbols_failed": symbols_failed,
        "provider_api_called": provider_api_called,
        "exploratory_data_only": True,
        "institutional_grade_data": False,
        "real_money_ready": False,
        "all_required_symbols_passed_qa": all_required_symbols_passed_qa,
        "required_warmup_rows": REQUIRED_WARMUP_ROWS,
        "cache_dir": str(root / "data" / "cache"),
        "yfinance_params": yfinance_params,
        **FORBIDDEN_FLAGS,
    }
    consistency = {
        "run_id": run_id,
        "approved_symbols_only": symbols == APPROVED_SYMBOLS,
        "no_forbidden_symbols": all(symbol in APPROVED_SYMBOLS for symbol in symbols),
        "all_required_symbols_passed_qa": all_required_symbols_passed_qa,
        "no_paper_forward_activation": not manifest["paper_forward_activation"],
        "no_paper_forward_checkpoint": not manifest["paper_forward_checkpoint"],
        "no_real_money_recommendation": not manifest["real_money_recommendation"],
        "no_broker_or_live_order_path": not (
            manifest["broker_integration"] or manifest["live_orders"] or manifest["order_placement"]
        ),
        "no_forbidden_asset_classes_or_mechanics": not any(
            manifest[key]
            for key in [
                "leverage",
                "margin",
                "shorting",
                "options",
                "futures",
                "forex",
                "crypto",
                "intraday",
            ]
        ),
        "no_optimization_or_grid_search": not (manifest["parameter_optimization"] or manifest["grid_search"]),
        "strategy_validation_run": False,
        "consistency_passed": False,
    }
    consistency["required_outputs_exist"] = False
    consistency["consistency_passed"] = all(
        [
            consistency["approved_symbols_only"],
            consistency["no_forbidden_symbols"],
            consistency["all_required_symbols_passed_qa"],
            consistency["no_paper_forward_activation"],
            consistency["no_paper_forward_checkpoint"],
            consistency["no_real_money_recommendation"],
            consistency["no_broker_or_live_order_path"],
            consistency["no_forbidden_asset_classes_or_mechanics"],
            consistency["no_optimization_or_grid_search"],
            not consistency["strategy_validation_run"],
        ]
    )

    write_csv(
        run_dir / "cache_status.csv",
        [
            {
                "symbol": row["symbol"],
                "cache_file_exists": row["cache_file_exists"],
                "qa_passed": row["qa_passed"],
                "status": "ready" if row["qa_passed"] else "not_ready",
                "cache_file": row["cache_file"],
                "cache_file_hash": row["cache_file_hash"],
            }
            for row in quality_rows
        ],
        ["symbol", "cache_file_exists", "qa_passed", "status", "cache_file", "cache_file_hash"],
    )
    write_csv(
        run_dir / "download_log.csv",
        download_rows,
        ["symbol", "status", "provider_api_called", "detail"],
    )
    write_csv(
        run_dir / "data_quality.csv",
        quality_rows,
        [
            "symbol",
            "cache_file_exists",
            "first_date",
            "last_date",
            "row_count",
            "adjusted_close_availability",
            "missing_values",
            "duplicate_dates",
            "impossible_ohlc_values",
            "warmup_sufficiency",
            "qa_passed",
            "reason_for_failure",
            "cache_file",
            "cache_file_hash",
        ],
    )
    write_json(run_dir / "cache_bootstrap_manifest.json", manifest)
    write_json(run_dir / "cache_bootstrap_consistency_check.json", consistency)
    (run_dir / "cache_bootstrap_summary.md").write_text(
        render_summary(manifest, quality_rows, download_rows), encoding="utf-8"
    )

    consistency["required_outputs_exist"] = all(path.exists() for path in output_files)
    consistency["consistency_passed"] = consistency["consistency_passed"] and consistency["required_outputs_exist"]
    write_json(run_dir / "cache_bootstrap_consistency_check.json", consistency)

    if latest_dir.exists():
        shutil.rmtree(latest_dir)
    shutil.copytree(run_dir, latest_dir)

    return {
        "run_id": run_id,
        "run_dir": str(run_dir),
        "latest_dir": str(latest_dir),
        "manifest": manifest,
        "consistency": consistency,
        "quality_rows": quality_rows,
        "download_rows": download_rows,
    }


def main() -> int:
    result = run_cache_bootstrap(ROOT)
    manifest = result["manifest"]
    latest_dir = result["latest_dir"]
    if not manifest["all_required_symbols_passed_qa"]:
        failed = "_".join(APPROVED_SYMBOLS)
        print(f"manual_cache_restore_required_for_{failed}")
        print(f"latest_dir={latest_dir}")
        return 1
    print(f"gror_required_cache_bootstrap_passed latest_dir={latest_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
