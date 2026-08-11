from __future__ import annotations

import argparse
import csv
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from execution_lab.alpaca_micro_live_v1 import MODULE_ROOT
from execution_lab.alpaca_micro_live_v1.handoff_import.reporting import write_csv

DEFAULT_OUTPUT_DIR = MODULE_ROOT / "evidence" / "handoff_imports" / "dry_run_blocker_fixes" / "latest"
DEFAULT_CACHE_DIR = MODULE_ROOT / "evidence" / "alpaca_runtime_data" / "cache"

REQUIRED_ROWS = [
    {
        "handoff_package_id": "schwoerer_hyg_ema100_spy_bil_v1_standard_handoff_v1",
        "strategy_id": "schwoerer_hyg_ema100_spy_bil_v1",
        "required_symbol": "HYG",
        "required_timeframe": "1Day",
        "required_minimum_bars": 100,
    }
]


def cached_bar_count(symbol: str, timeframe: str = "1Day", cache_dir: Path = DEFAULT_CACHE_DIR) -> int:
    path = cache_dir / f"{symbol}_{timeframe}.csv"
    if not path.exists():
        return 0
    with path.open(newline="", encoding="utf-8") as handle:
        return max(0, sum(1 for _ in csv.DictReader(handle)))


def run_preflight(
    *,
    first_batch: bool,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    cache_dir: Path = DEFAULT_CACHE_DIR,
    allow_readonly_alpaca_fetch: bool = False,
    write_cache: bool = False,
) -> dict[str, Any]:
    rows = []
    for req in (REQUIRED_ROWS if first_batch else []):
        count = cached_bar_count(str(req["required_symbol"]), str(req["required_timeframe"]), cache_dir)
        needed = count < int(req["required_minimum_bars"])
        rows.append(
            {
                **req,
                "cache_path": str(cache_dir / f"{req['required_symbol']}_{req['required_timeframe']}.csv"),
                "cache_present": str(count > 0).lower(),
                "current_cached_bar_count": count,
                "readonly_alpaca_bootstrap_needed": str(needed).lower(),
                "network_used": "false",
                "bootstrap_command": (
                    "python -m execution_lab.alpaca_micro_live_v1.execution.imported_strategy_data_preflight "
                    "--first-batch --allow-readonly-alpaca-fetch --write-cache"
                    if needed
                    else ""
                ),
                "status": "data_requirement_gap" if needed else "cache_sufficient",
            }
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(output_dir / "data_preflight_report.csv", rows)
    if allow_readonly_alpaca_fetch and write_cache:
        _readonly_bootstrap(rows, cache_dir)
    return {
        "rows": rows,
        "missing_or_insufficient": sum(1 for row in rows if row["status"] == "data_requirement_gap"),
        "network_used": False,
        "output_dir": str(output_dir),
    }


def _readonly_bootstrap(rows: list[dict[str, Any]], cache_dir: Path) -> None:
    from execution_lab.alpaca_micro_live_v1.adapters.alpaca_client import AlpacaClient, AlpacaClientConfig
    from execution_lab.alpaca_micro_live_v1.adapters.credentials import load_alpaca_credentials
    from execution_lab.alpaca_micro_live_v1.data.alpaca_historical_bars import fetch_daily_bars

    credentials = load_alpaca_credentials("paper")
    client = AlpacaClient(credentials, AlpacaClientConfig())
    symbols = [str(row["required_symbol"]) for row in rows if row["status"] == "data_requirement_gap"]
    if not symbols:
        return
    bars = fetch_daily_bars(client, symbols=symbols, approved_symbols=symbols, start=(date.today() - timedelta(days=420)).isoformat())
    cache_dir.mkdir(parents=True, exist_ok=True)
    for symbol, frame in bars.items():
        if frame is not None and not frame.empty:
            frame.to_csv(cache_dir / f"{symbol}_1Day.csv", index=False)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Preflight imported strategy dry-run data requirements.")
    parser.add_argument("--first-batch", action="store_true", required=True)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--allow-readonly-alpaca-fetch", action="store_true")
    parser.add_argument("--write-cache", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_preflight(
        first_batch=args.first_batch,
        output_dir=args.output_dir,
        cache_dir=args.cache_dir,
        allow_readonly_alpaca_fetch=args.allow_readonly_alpaca_fetch,
        write_cache=args.write_cache,
    )
    print(f"preflight_rows: {len(result['rows'])}")
    print(f"missing_or_insufficient: {result['missing_or_insufficient']}")
    print(f"output_dir: {result['output_dir']}")
    print("network_used: false")
    print("paper_orders_submitted: false")
    print("live_orders_submitted: false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
