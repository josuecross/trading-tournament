from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from .sandbox_universes import UNIVERSE_GROUPS, cache_symbol_files, is_symbol_approved, load_approved_symbol_rows


def cache_file_metadata(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"row_count": 0, "earliest_date": "", "latest_date": ""}
    row_count = 0
    earliest_date = ""
    latest_date = ""
    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            row_count += 1
            current = str(row.get("date", ""))
            if current and not earliest_date:
                earliest_date = current
            if current:
                latest_date = current
    return {"row_count": row_count, "earliest_date": earliest_date, "latest_date": latest_date}


def preflight_universe_availability(root: Path) -> list[dict[str, Any]]:
    approved = load_approved_symbol_rows(root)
    cached = cache_symbol_files(root)
    rows: list[dict[str, Any]] = []
    for group in UNIVERSE_GROUPS.values():
        symbols_found: list[str] = []
        symbols_missing: list[str] = []
        blocked: list[str] = []
        earliest_dates: list[str] = []
        latest_dates: list[str] = []
        row_counts: list[int] = []
        for symbol in group.symbols:
            approved_row = approved.get(symbol)
            cache_path = cached.get(symbol)
            approved_ok = is_symbol_approved(approved_row)
            if cache_path and approved_ok:
                symbols_found.append(symbol)
                meta = cache_file_metadata(cache_path)
                row_counts.append(int(meta["row_count"]))
                if meta["earliest_date"]:
                    earliest_dates.append(meta["earliest_date"])
                if meta["latest_date"]:
                    latest_dates.append(meta["latest_date"])
            else:
                reasons = []
                if not cache_path:
                    reasons.append("missing_local_cache")
                if not approved_ok:
                    reasons.append("not_approved")
                symbols_missing.append(symbol)
                blocked.append(f"{symbol}:{'+'.join(reasons)}")
        min_rows = min(row_counts, default=0)
        limited_history_warning = "limited_history" if 0 < min_rows < 500 else ""
        eligible = group.eligible_for_sandbox and len(symbols_found) >= min(2, len(group.symbols))
        rows.append(
            {
                "universe_group": group.group_id,
                "symbols_found": symbols_found,
                "symbols_missing": symbols_missing,
                "local_cache_present": bool(symbols_found),
                "approved_status": "approved_cache_present" if symbols_found else "no_approved_cache_present",
                "earliest_date": min(earliest_dates) if earliest_dates else "",
                "latest_date": max(latest_dates) if latest_dates else "",
                "row_count": min_rows,
                "limited_history_warning": limited_history_warning,
                "eligible_for_future_sandbox_run": eligible,
                "blocked_symbols_and_reason": blocked,
            }
        )
    return rows


def preflight_report(rows: list[dict[str, Any]]) -> str:
    header = (
        "| universe group | found | missing | earliest | latest | min rows | limited-history warning | eligible |"
    )
    sep = "|---|---:|---:|---|---|---:|---|---:|"
    body = "\n".join(
        f"| `{row['universe_group']}` | {len(row['symbols_found'])} | {len(row['symbols_missing'])} | "
        f"{row['earliest_date'] or 'n/a'} | {row['latest_date'] or 'n/a'} | {row['row_count']} | "
        f"{row['limited_history_warning'] or 'none'} | `{row['eligible_for_future_sandbox_run']}` |"
        for row in rows
    )
    return f"""# Sandbox Data Preflight Report

Local cache metadata only. No provider data was downloaded.

{header}
{sep}
{body}

Missing symbols are marked data-blocked for future sandbox execution rather than downloaded.
"""


def universe_availability_report(rows: list[dict[str, Any]]) -> str:
    lines = [
        "# Sandbox Universe Availability Report",
        "",
        "Universe groups use local approved/cache-present symbols only.",
        "",
    ]
    for row in rows:
        lines.append(f"## `{row['universe_group']}`")
        lines.append(f"- Symbols found: `{', '.join(row['symbols_found']) or 'none'}`")
        lines.append(f"- Symbols missing/data-blocked: `{', '.join(row['symbols_missing']) or 'none'}`")
        lines.append(f"- Blocked symbols and reason: `{', '.join(row['blocked_symbols_and_reason']) or 'none'}`")
        lines.append(f"- Earliest date: `{row['earliest_date'] or 'n/a'}`")
        lines.append(f"- Latest date: `{row['latest_date'] or 'n/a'}`")
        lines.append(f"- Minimum row count: `{row['row_count']}`")
        lines.append(f"- Eligible for future sandbox run: `{row['eligible_for_future_sandbox_run']}`")
        lines.append("")
    return "\n".join(lines)
