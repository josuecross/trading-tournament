from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .sandbox_config import APPROVED_SYMBOL_MAP_PATH, DATA_CACHE_DIR


@dataclass(frozen=True)
class UniverseGroup:
    group_id: str
    display_name: str
    symbols: tuple[str, ...]
    eligible_for_sandbox: bool = True


UNIVERSE_GROUPS: dict[str, UniverseGroup] = {
    "core_equity": UniverseGroup("core_equity", "Core equity ETFs", ("SPY", "QQQ", "IWM", "DIA")),
    "sector": UniverseGroup(
        "sector",
        "Sector ETFs",
        ("XLK", "XLF", "XLV", "XLE", "XLI", "XLY", "XLP", "XLU", "XLB", "XLRE", "XLC"),
    ),
    "macro": UniverseGroup("macro", "Macro ETFs", ("GLD", "IEF", "TLT", "AGG", "BIL")),
    "factor_style": UniverseGroup(
        "factor_style",
        "Factor/style ETFs",
        ("VLUE", "QUAL", "MTUM", "SPLV", "USMV", "DGRO", "SCHD", "VIG", "VTV", "SCHG"),
    ),
    "managed_futures_wrappers": UniverseGroup(
        "managed_futures_wrappers",
        "Managed-futures wrapper ETFs",
        ("DBMF", "KMLM", "CTA", "FMF", "WTMF"),
    ),
    "international_regional": UniverseGroup(
        "international_regional",
        "International/regional ETFs",
        ("EFA", "EEM", "EWG", "EWJ", "EWU", "EWY", "INDA", "EEMV", "EFAV"),
    ),
    "credit_income": UniverseGroup("credit_income", "Credit/income ETFs", ("LQD", "HYG", "EMB")),
}


def load_approved_symbol_rows(root: Path) -> dict[str, dict[str, Any]]:
    path = root / APPROVED_SYMBOL_MAP_PATH
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    rows: dict[str, dict[str, Any]] = {}
    for row in data.get("symbols", []):
        symbol = str(row.get("symbol", "")).upper()
        if symbol:
            rows[symbol] = row
    return rows


def cache_symbol_files(root: Path) -> dict[str, Path]:
    cache_dir = root / DATA_CACHE_DIR
    if not cache_dir.exists():
        return {}
    return {path.stem.upper(): path for path in cache_dir.glob("*.csv")}


def is_symbol_approved(row: dict[str, Any] | None) -> bool:
    return bool(row and (row.get("allowed_for_strategy") or row.get("allowed_for_benchmark")))


def universe_registry_rows(root: Path) -> list[dict[str, object]]:
    approved = load_approved_symbol_rows(root)
    cached = cache_symbol_files(root)
    rows: list[dict[str, object]] = []
    for group in UNIVERSE_GROUPS.values():
        found = [symbol for symbol in group.symbols if symbol in cached and is_symbol_approved(approved.get(symbol))]
        blocked = []
        for symbol in group.symbols:
            reasons = []
            if symbol not in cached:
                reasons.append("missing_local_cache")
            if not is_symbol_approved(approved.get(symbol)):
                reasons.append("not_approved_for_strategy_or_benchmark")
            if reasons:
                blocked.append(f"{symbol}:{'+'.join(reasons)}")
        rows.append(
            {
                "group_id": group.group_id,
                "display_name": group.display_name,
                "symbols": list(group.symbols),
                "symbols_found": found,
                "blocked_symbols_and_reason": blocked,
                "eligible_for_sandbox": group.eligible_for_sandbox and len(found) >= min(2, len(group.symbols)),
            }
        )
    return rows
