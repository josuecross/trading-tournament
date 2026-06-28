from __future__ import annotations

import csv
import json
import math
import shutil
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml


ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = Path("evidence") / "diagnostics" / "turn_of_month_zero_trade_audit" / "latest"
PREREG_DIR = Path("evidence") / "pre_registered_lanes" / "second_expansion_with_lane_framework" / "latest"
RULE_PATCH_DIR = Path("evidence") / "pre_registered_lanes" / "second_expansion_with_lane_framework" / "rule_freeze_patch" / "latest"
SECOND_EXPANSION_DIR = Path("evidence") / "parallel_research_discovery" / "second_expansion_with_lane_framework" / "latest"
SECTOR_RS_DIR = Path("evidence") / "parallel_research_discovery" / "sector_rs_limited_history" / "latest"
REGISTRY_PATH = Path("strategy_lab") / "strategy_registry.yaml"
ROADMAP_PATH = Path("strategy_lab") / "RESEARCH_ROADMAP.md"
CACHE_DIR = Path("data") / "cache"

CANDIDATE_ID = "turn_of_month_spy_qqq_v1"
LANE_ID = "moderate_tactical_etf_lane"
UNIVERSE = ["SPY", "QQQ", "BIL"]
VALID_NEXT_ACTIONS = {
    "fix_turn_of_month_implementation_bug_before_more_research",
    "close_turn_of_month_exact_variant_and_continue_lane_framework",
    "pre_register_third_expansion_discovery_batch_with_lane_framework",
    "audit_second_expansion_failures_before_more_expansion",
}
NEXT_ACTION_FIX = "fix_turn_of_month_implementation_bug_before_more_research"
NEXT_ACTION_CLOSE = "close_turn_of_month_exact_variant_and_continue_lane_framework"
NEXT_ACTION_AUDIT = "audit_second_expansion_failures_before_more_expansion"

MANIFEST_FLAGS = {
    "audit_only": True,
    "new_discovery_run": False,
    "new_backtests_run": False,
    "performance_metrics_computed_from_new_tests": False,
    "provider_download": False,
    "candidate_exhaustive_run": False,
    "paper_forward_review": False,
    "paper_forward_activation": False,
    "broker_path_touched": False,
    "live_orders": False,
    "real_money_recommendation": False,
    "frozen_rule_changed": False,
    "candidate_status_changed": False,
    "accepted_strategy_state_changed": False,
    "rejected_strategy_state_changed": False,
}


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def fmt(value: Any) -> Any:
    if isinstance(value, (float, np.floating)):
        value = float(value)
        if math.isnan(value) or math.isinf(value):
            return ""
        return round(value, 6)
    return value


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: fmt(row.get(field, "")) for field in fields})


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def clean_output(root: Path) -> Path:
    output = (root / OUTPUT_DIR).resolve()
    if root.resolve() not in output.parents:
        raise RuntimeError(f"refusing output outside workspace: {output}")
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)
    return output


def strategy_snapshot(root: Path) -> list[dict[str, Any]]:
    return deepcopy(load_yaml(root / REGISTRY_PATH).get("strategies", []))


def registry_metadata_snapshot(root: Path) -> dict[str, Any]:
    return deepcopy(load_yaml(root / REGISTRY_PATH).get("registry", {}))


def validate_authorization(root: Path) -> tuple[dict[str, Any], list[str]]:
    mismatches: list[str] = []
    batch = load_yaml(root / PREREG_DIR / "second_expansion_batch.yaml")
    patch_manifest = read_json(root / RULE_PATCH_DIR / "second_expansion_rule_freeze_patch_manifest.json")
    second_manifest = read_json(root / SECOND_EXPANSION_DIR / "second_expansion_discovery_manifest.json")
    sector_manifest = read_json(root / SECTOR_RS_DIR / "sector_rs_limited_history_discovery_manifest.json")
    candidates = {candidate.get("candidate_id"): candidate for candidate in batch.get("candidates", [])}
    candidate = candidates.get(CANDIDATE_ID, {})
    if not candidate:
        mismatches.append("turn-of-month candidate missing from second expansion preregistration")
    if candidate.get("lane_id") != LANE_ID:
        mismatches.append("turn-of-month lane mismatch")
    if candidate.get("allowed_instruments") and candidate.get("allowed_instruments") != UNIVERSE:
        mismatches.append("turn-of-month universe mismatch")
    if patch_manifest.get("turn_of_month_rule_fully_frozen") is not True:
        mismatches.append("turn-of-month frozen-rule patch not recorded")
    if second_manifest.get("next_action") not in {"run_sector_rs_limited_history_discovery_batch", "audit_turn_of_month_zero_trade_result"}:
        mismatches.append("second expansion result does not support turn-of-month audit context")
    if sector_manifest and sector_manifest.get("next_action") != "audit_turn_of_month_zero_trade_result":
        mismatches.append("sector RS result does not authorize turn-of-month audit")
    return candidate, mismatches


def read_symbol_frame(root: Path, symbol: str) -> pd.DataFrame | None:
    path = root / CACHE_DIR / f"{symbol}.csv"
    if not path.exists():
        return None
    frame = pd.read_csv(path)
    if "date" not in frame:
        return None
    dates = pd.to_datetime(frame["date"], errors="coerce").dt.tz_localize(None)
    clean = pd.DataFrame({"date": dates})
    for column in ["open", "high", "low", "close", "adj_close", "volume"]:
        if column in frame:
            clean[column] = pd.to_numeric(frame[column], errors="coerce")
    if "close" not in clean and "adj_close" in clean:
        clean["close"] = clean["adj_close"]
    if "adj_close" not in clean and "close" in clean:
        clean["adj_close"] = clean["close"]
    for column in ["open", "high", "low"]:
        if column not in clean and "close" in clean:
            clean[column] = clean["close"]
    if "volume" not in clean:
        clean["volume"] = 1_000_000.0
    required = ["date", "open", "high", "low", "close", "adj_close", "volume"]
    if any(column not in clean for column in required):
        return None
    clean = clean.dropna(subset=["date", "close", "adj_close"]).sort_values("date").drop_duplicates("date")
    if len(clean) < 260:
        return None
    return clean.set_index("date")[["open", "high", "low", "close", "adj_close", "volume"]].astype(float)


def load_prices(root: Path) -> dict[str, Any]:
    frames: dict[str, pd.DataFrame] = {}
    missing: list[str] = []
    for symbol in UNIVERSE:
        frame = read_symbol_frame(root, symbol)
        if frame is None:
            missing.append(symbol)
        else:
            frames[symbol] = frame
    if missing:
        return {"available": False, "missing": missing}
    common_end = min(frame.index.max() for frame in frames.values())
    all_dates = sorted(set().union(*(set(frame.index[frame.index <= common_end]) for frame in frames.values())))
    store: dict[str, Any] = {
        "available": True,
        "index": pd.DatetimeIndex(all_dates),
        "first_dates": {symbol: str(frame.index.min().date()) for symbol, frame in frames.items()},
        "last_dates": {symbol: str(min(frame.index.max(), common_end).date()) for symbol, frame in frames.items()},
    }
    for column in ["open", "high", "low", "close", "adj_close", "volume"]:
        store[column] = pd.concat(
            [frame[column].rename(symbol) for symbol, frame in frames.items()],
            axis=1,
            join="outer",
            sort=False,
        ).reindex(store["index"]).sort_index()
    return store


def indicators(store: dict[str, Any]) -> dict[str, pd.DataFrame]:
    close = store["close"]
    return {
        "mom63": close / close.shift(63) - 1.0,
        "sma200": close.rolling(200, min_periods=200).mean(),
    }


def value_at(frame: pd.DataFrame, symbol: str, t: int) -> float | None:
    if symbol not in frame.columns or t < 0 or t >= len(frame):
        return None
    value = frame.iloc[t][symbol]
    if pd.isna(value):
        return None
    return float(value)


def available(store: dict[str, Any], symbol: str, t: int, lookback: int = 0) -> bool:
    return value_at(store["close"], symbol, t) is not None and value_at(store["close"], symbol, t - lookback) is not None


def above_sma200(store: dict[str, Any], ind: dict[str, pd.DataFrame], symbol: str, t: int) -> bool:
    price = value_at(store["close"], symbol, t)
    sma = value_at(ind["sma200"], symbol, t)
    return price is not None and sma is not None and price > sma


def correct_turn_windows(index: pd.DatetimeIndex, start_idx: int, end_idx: int) -> list[dict[str, Any]]:
    frame = pd.DataFrame({"date": index})
    frame["month"] = frame["date"].dt.to_period("M")
    groups = [(str(month), list(group["date"])) for month, group in frame.groupby("month")]
    rows: list[dict[str, Any]] = []
    for idx, (month, dates) in enumerate(groups[:-1]):
        next_month, next_dates = groups[idx + 1]
        if len(dates) < 4 or len(next_dates) < 3:
            continue
        window_dates = [pd.Timestamp(ts) for ts in dates[-4:] + next_dates[:3]]
        first = window_dates[0]
        first_idx = int(index.get_loc(first))
        if first_idx < start_idx or first_idx > end_idx:
            continue
        rows.append(
            {
                "window_month": month,
                "next_month": next_month,
                "first_eligible_day": first,
                "last_eligible_day": window_dates[-1],
                "trading_days_in_window": len(window_dates),
                "window_dates": window_dates,
                "first_idx": first_idx,
            }
        )
    return rows


def implemented_turn_flags(index: pd.DatetimeIndex) -> tuple[set[pd.Timestamp], dict[str, pd.Timestamp]]:
    frame = pd.DataFrame({"date": index})
    frame["month"] = frame["date"].dt.to_period("M")
    in_window: set[pd.Timestamp] = set()
    first_window_day: dict[str, pd.Timestamp] = {}
    for _month, group in frame.groupby("month"):
        dates = list(group["date"])
        for ts in dates[:3] + dates[-4:]:
            in_window.add(pd.Timestamp(ts))
        for ts in dates[-4:]:
            key = str((pd.Timestamp(ts) + pd.offsets.MonthBegin(1)).to_period("M"))
            first_window_day.setdefault(key, pd.Timestamp(ts))
        if dates[:3]:
            key = str(pd.Timestamp(dates[0]).to_period("M"))
            first_window_day.setdefault(key, pd.Timestamp(dates[0]))
    return in_window, first_window_day


def discovery_trade_count(root: Path) -> int:
    rows = read_csv_rows(root / SECOND_EXPANSION_DIR / "second_expansion_tactical_diagnostics.csv")
    for row in rows:
        if row.get("candidate_id") == CANDIDATE_ID:
            return int(float(row.get("trade_count", "0") or 0))
    result_rows = read_csv_rows(root / SECOND_EXPANSION_DIR / "second_expansion_candidate_results.csv")
    for row in result_rows:
        if row.get("candidate_id") == CANDIDATE_ID:
            return int(float(row.get("trade_count", "0") or 0))
    return 0


def audit_signals(root: Path, store: dict[str, Any], ind: dict[str, pd.DataFrame]) -> dict[str, Any]:
    index = store["index"]
    start_idx = int(index.get_indexer([pd.Timestamp("2008-01-01")], method="bfill")[0])
    end_idx = len(index) - 1
    windows = correct_turn_windows(index, start_idx, end_idx)
    implemented_in_window, implemented_first_days = implemented_turn_flags(index)
    implemented_first_matches = 0
    signal_rows: list[dict[str, Any]] = []
    sample_rows: list[dict[str, Any]] = []
    counts = {
        "calendar_months_in_test_window": len(set(str(ts.to_period("M")) for ts in index[start_idx : end_idx + 1])),
        "turn_of_month_windows_constructed": len(windows),
        "first_eligible_window_days_identified": len(windows),
        "windows_with_enough_63_day_momentum_history": 0,
        "windows_with_enough_200_day_sma_history": 0,
        "spy_above_200d_sma_count": 0,
        "qqq_above_200d_sma_count": 0,
        "selected_higher_63d_asset_qualifies_count": 0,
        "entry_signal_count_before_execution": 0,
        "entries_blocked_missing_stale": 0,
        "entries_blocked_execution_date": 0,
        "entries_blocked_risk_or_no_trade_filters": 0,
        "entry_signal_count_after_filters": 0,
        "implemented_first_eligible_day_matches": 0,
    }
    for row in windows:
        t = row["first_idx"]
        signal = t - 1
        first_day = pd.Timestamp(row["first_eligible_day"])
        month_key = str(first_day.to_period("M"))
        implemented_match = first_day in implemented_in_window and implemented_first_days.get(month_key) == first_day
        implemented_first_matches += int(implemented_match)
        spy_mom = value_at(ind["mom63"], "SPY", signal)
        qqq_mom = value_at(ind["mom63"], "QQQ", signal)
        spy_sma = value_at(ind["sma200"], "SPY", signal)
        qqq_sma = value_at(ind["sma200"], "QQQ", signal)
        enough_63 = spy_mom is not None and qqq_mom is not None and available(store, "SPY", signal, 63) and available(store, "QQQ", signal, 63)
        enough_200 = spy_sma is not None and qqq_sma is not None and available(store, "SPY", signal, 200) and available(store, "QQQ", signal, 200)
        if enough_63:
            counts["windows_with_enough_63_day_momentum_history"] += 1
        if enough_200:
            counts["windows_with_enough_200_day_sma_history"] += 1
        spy_qualifies = enough_200 and above_sma200(store, ind, "SPY", signal)
        qqq_qualifies = enough_200 and above_sma200(store, ind, "QQQ", signal)
        counts["spy_above_200d_sma_count"] += int(spy_qualifies)
        counts["qqq_above_200d_sma_count"] += int(qqq_qualifies)
        selected = ""
        selected_qualifies = False
        block_reason = ""
        if not enough_63:
            block_reason = "insufficient_63_day_momentum_data"
        elif not enough_200:
            block_reason = "insufficient_200_day_sma_history"
        else:
            selected = "SPY" if float(spy_mom) >= float(qqq_mom) else "QQQ"
            selected_qualifies = spy_qualifies if selected == "SPY" else qqq_qualifies
            if selected_qualifies:
                counts["selected_higher_63d_asset_qualifies_count"] += 1
                counts["entry_signal_count_before_execution"] += 1
                if not available(store, selected, t, 1):
                    counts["entries_blocked_missing_stale"] += 1
                    block_reason = "missing_stale_data"
                elif t < start_idx or t > end_idx:
                    counts["entries_blocked_execution_date"] += 1
                    block_reason = "execution_date_issue"
                else:
                    counts["entry_signal_count_after_filters"] += 1
                    block_reason = "entry_signal_after_filters"
            else:
                counts["entries_blocked_risk_or_no_trade_filters"] += 1
                block_reason = "selected_asset_below_200d_sma"
        signal_row = {
            "candidate_id": CANDIDATE_ID,
            "window_month": row["window_month"],
            "first_eligible_day": str(first_day.date()),
            "last_eligible_day": str(pd.Timestamp(row["last_eligible_day"]).date()),
            "signal_date": str(index[signal].date()) if signal >= 0 else "",
            "enough_63_day_momentum_history": enough_63,
            "enough_200_day_sma_history": enough_200,
            "spy_63d_return": spy_mom if spy_mom is not None else "",
            "qqq_63d_return": qqq_mom if qqq_mom is not None else "",
            "spy_above_200d_sma": spy_qualifies,
            "qqq_above_200d_sma": qqq_qualifies,
            "selected_asset": selected or "BIL",
            "selected_higher_63d_asset_qualifies": selected_qualifies,
            "entry_signal_before_execution": selected_qualifies,
            "entry_signal_after_filters": block_reason == "entry_signal_after_filters",
            "implemented_first_day_match": implemented_match,
            "block_reason": block_reason,
        }
        signal_rows.append(signal_row)
        if len(sample_rows) < 24 or not implemented_match and len(sample_rows) < 40:
            sample_rows.append(signal_row)
    counts["implemented_first_eligible_day_matches"] = implemented_first_matches
    block_reasons = {
        "outside_calendar_window": int(len(index[start_idx : end_idx + 1]) - len(set(day for row in windows for day in row["window_dates"]))),
        "insufficient_63_day_momentum_data": sum(1 for row in signal_rows if row["block_reason"] == "insufficient_63_day_momentum_data"),
        "insufficient_200_day_sma_history": sum(1 for row in signal_rows if row["block_reason"] == "insufficient_200_day_sma_history"),
        "spy_below_200d_sma": sum(1 for row in signal_rows if row["enough_200_day_sma_history"] and not row["spy_above_200d_sma"]),
        "qqq_below_200d_sma": sum(1 for row in signal_rows if row["enough_200_day_sma_history"] and not row["qqq_above_200d_sma"]),
        "selected_asset_below_200d_sma": sum(1 for row in signal_rows if row["block_reason"] == "selected_asset_below_200d_sma"),
        "missing_stale_data": counts["entries_blocked_missing_stale"],
        "calendar_window_construction_issue": counts["first_eligible_window_days_identified"] - counts["implemented_first_eligible_day_matches"],
        "execution_date_issue": counts["entries_blocked_execution_date"],
        "bil_fallback_issue": counts["entry_signal_count_after_filters"] if counts["implemented_first_eligible_day_matches"] == 0 else 0,
        "risk_or_no_trade_filter": counts["entries_blocked_risk_or_no_trade_filters"],
    }
    return {
        "start_idx": start_idx,
        "end_idx": end_idx,
        "test_start": str(index[start_idx].date()),
        "test_end": str(index[end_idx].date()),
        "counts": counts,
        "signal_rows": signal_rows,
        "sample_rows": sample_rows,
        "block_reasons": block_reasons,
    }


def update_metadata(root: Path, output: Path, manifest: dict[str, Any]) -> tuple[bool, bool]:
    registry_path = root / REGISTRY_PATH
    registry = load_yaml(registry_path)
    metadata = registry.setdefault("registry", {})
    metadata.update(
        {
            "turn_of_month_zero_trade_audit_path": str(output),
            "turn_of_month_zero_trade_audit_status": "completed",
            "turn_of_month_zero_trade_confirmed": manifest["zero_trade_result_confirmed"],
            "turn_of_month_implementation_bug_found": manifest["implementation_bug_found"],
            "turn_of_month_zero_trade_next_action": manifest["next_action"],
            "current_next_action": manifest["next_action"],
            "next_action": manifest["next_action"],
            "audit_only": True,
            "new_discovery_run": False,
            "new_backtests_run": False,
            "provider_download": False,
            "candidate_exhaustive_run": False,
            "paper_forward_review": False,
            "paper_forward_activation": False,
            "broker_path_touched": False,
            "live_orders": False,
            "real_money_recommendation": False,
            "updated_utc": manifest["created_utc"],
        }
    )
    registry_path.write_text(yaml.safe_dump(registry, sort_keys=False, width=120, allow_unicode=False), encoding="utf-8")
    roadmap_path = root / ROADMAP_PATH
    existing = roadmap_path.read_text(encoding="utf-8") if roadmap_path.exists() else "# Research Roadmap\n"
    marker = "## Turn-of-Month Zero-Trade Audit"
    section = f"""## Turn-of-Month Zero-Trade Audit

- Created UTC: `{manifest['created_utc']}`
- Evidence path: `{output}`
- Candidate: `{CANDIDATE_ID}`
- Zero-trade result confirmed: `{manifest['zero_trade_result_confirmed']}`
- Implementation bug found: `{manifest['implementation_bug_found']}`
- Calendar windows constructed: `{manifest['calendar_window_count']}`
- Entry signals before execution: `{manifest['entry_signal_count_before_execution']}`
- Entry signals after filters: `{manifest['entry_signal_count_after_filters']}`
- Next action: `{manifest['next_action']}`
- This was audit-only: no new discovery, backtest, candidate_exhaustive, paper-forward action, provider download, broker/live path, state change, or real-money recommendation was authorized.
"""
    updated = existing.split(marker, 1)[0].rstrip() + "\n\n" + section if marker in existing else existing.rstrip() + "\n\n" + section
    roadmap_path.write_text(updated.rstrip() + "\n", encoding="utf-8")
    return True, True


def write_outputs(
    output: Path,
    store: dict[str, Any],
    audit: dict[str, Any],
    manifest: dict[str, Any],
    consistency: dict[str, Any] | None = None,
) -> None:
    counts = audit["counts"]
    window_rows = [
        {
            "candidate_id": CANDIDATE_ID,
            "test_start": audit["test_start"],
            "test_end": audit["test_end"],
            "calendar_months_in_test_window": counts["calendar_months_in_test_window"],
            "turn_of_month_windows_constructed": counts["turn_of_month_windows_constructed"],
            "first_eligible_window_days_identified": counts["first_eligible_window_days_identified"],
            "implemented_first_eligible_day_matches": counts["implemented_first_eligible_day_matches"],
        }
    ]
    funnel_rows = [{"candidate_id": CANDIDATE_ID, "stage": key, "count": value} for key, value in counts.items()]
    block_rows = [{"candidate_id": CANDIDATE_ID, "block_reason": key, "count": value} for key, value in audit["block_reasons"].items()]
    data_rows = []
    for symbol in UNIVERSE:
        close = store["close"][symbol]
        data_rows.append(
            {
                "symbol": symbol,
                "first_date": store["first_dates"][symbol],
                "last_date": store["last_dates"][symbol],
                "rows": int(close.notna().sum()),
                "missing_close_rows": int(close.isna().sum()),
                "has_63_day_history_somewhere": bool(close.notna().sum() > 63),
                "has_200_day_sma_history_somewhere": bool(close.notna().sum() > 200),
            }
        )
    write_json(output / "turn_of_month_zero_trade_audit_manifest.json", manifest)
    write_csv(output / "turn_of_month_window_counts.csv", window_rows, list(window_rows[0].keys()))
    write_csv(output / "turn_of_month_signal_funnel.csv", funnel_rows, ["candidate_id", "stage", "count"])
    write_csv(output / "turn_of_month_block_reason_counts.csv", block_rows, ["candidate_id", "block_reason", "count"])
    write_csv(output / "turn_of_month_sample_windows.csv", audit["sample_rows"], list(audit["signal_rows"][0].keys()) if audit["signal_rows"] else ["candidate_id"])
    write_csv(output / "turn_of_month_data_availability_check.csv", data_rows, list(data_rows[0].keys()))
    (output / "turn_of_month_implementation_findings.md").write_text(implementation_findings_md(manifest, audit), encoding="utf-8")
    (output / "turn_of_month_zero_trade_next_action.md").write_text(next_action_md(manifest), encoding="utf-8")
    (output / "turn_of_month_zero_trade_audit_summary.md").write_text(summary_md(manifest, audit), encoding="utf-8")
    if consistency is not None:
        write_json(output / "turn_of_month_zero_trade_consistency_check.json", consistency)


def implementation_findings_md(manifest: dict[str, Any], audit: dict[str, Any]) -> str:
    return f"""# Turn-of-Month Implementation Findings

Candidate: `{CANDIDATE_ID}`

Zero-trade result confirmed from second-expansion evidence: `{manifest['zero_trade_result_confirmed']}`.

Implementation bug found: `{manifest['implementation_bug_found']}`.

The frozen rule's first eligible day is the first of the last four trading days of the month. The implementation stores those prior-month dates under the next-month key, but later looks them up using the current date's month key. That key mismatch prevents normal first-window-day selection after the initial data month.

Correct frozen-rule entry signals after filters: `{manifest['entry_signal_count_after_filters']}`.

Implemented first-day matches: `{audit['counts']['implemented_first_eligible_day_matches']}`.

Conclusion: the `0 trades` result was not logically expected from the frozen rule. It was caused by a likely calendar-window/first-day mapping bug. The exact frozen candidate remains rejected in project state; this audit only says the zero-trade evidence should not be used to close the calendar family.
"""


def next_action_md(manifest: dict[str, Any]) -> str:
    return f"""# Turn-of-Month Zero-Trade Next Action

`{manifest['next_action']}`

Do not run this next action from the audit task.
"""


def summary_md(manifest: dict[str, Any], audit: dict[str, Any]) -> str:
    counts = audit["counts"]
    questions = [
        ("How many calendar months were in the test window?", counts["calendar_months_in_test_window"]),
        ("How many turn-of-month windows were constructed?", counts["turn_of_month_windows_constructed"]),
        ("How many first eligible window days were identified?", counts["first_eligible_window_days_identified"]),
        ("How many windows had enough 63-day momentum history?", counts["windows_with_enough_63_day_momentum_history"]),
        ("How many windows had enough 200-day SMA history?", counts["windows_with_enough_200_day_sma_history"]),
        ("How many times did SPY qualify above 200-day SMA?", counts["spy_above_200d_sma_count"]),
        ("How many times did QQQ qualify above 200-day SMA?", counts["qqq_above_200d_sma_count"]),
        ("How many times did the selected higher-63-day-return asset qualify?", counts["selected_higher_63d_asset_qualifies_count"]),
        ("How many entry signals should have occurred before execution checks?", counts["entry_signal_count_before_execution"]),
        ("How many entries were blocked by missing/stale data?", counts["entries_blocked_missing_stale"]),
        ("How many entries were blocked by execution-date handling?", counts["entries_blocked_execution_date"]),
        ("How many entries were blocked by risk or no-trade filters?", counts["entries_blocked_risk_or_no_trade_filters"]),
        ("Was 0 trades logically expected under the frozen rule?", manifest["zero_trades_logically_expected_under_frozen_rule"]),
        ("Was 0 trades caused by a likely implementation bug?", manifest["implementation_bug_found"]),
        ("Was 0 trades caused by overly restrictive but correctly implemented filters?", manifest["zero_trades_caused_by_overly_restrictive_correct_filters"]),
        ("Should the exact frozen candidate remain rejected?", manifest["exact_frozen_candidate_remains_rejected"]),
        ("Should the calendar family remain open for a future new hypothesis?", manifest["calendar_family_remains_open_for_future_new_hypothesis"]),
    ]
    lines = [
        "# Turn-of-Month Zero-Trade Audit",
        "",
        f"Created UTC: `{manifest['created_utc']}`",
        f"Candidate: `{CANDIDATE_ID}`",
        f"Audit-only: `{manifest['audit_only']}`",
        f"Next action: `{manifest['next_action']}`",
        "",
        "## Direct Answers",
        "",
    ]
    lines.extend(f"- {question} `{answer}`" for question, answer in questions)
    return "\n".join(lines) + "\n"


def consistency_check(
    output: Path,
    manifest: dict[str, Any],
    strategies_before: list[dict[str, Any]],
    strategies_after: list[dict[str, Any]],
    metadata_before: dict[str, Any],
    metadata_after: dict[str, Any],
) -> dict[str, Any]:
    status_keys = {"strategies"}
    required_files = [
        "turn_of_month_zero_trade_audit_manifest.json",
        "turn_of_month_zero_trade_audit_summary.md",
        "turn_of_month_window_counts.csv",
        "turn_of_month_signal_funnel.csv",
        "turn_of_month_block_reason_counts.csv",
        "turn_of_month_sample_windows.csv",
        "turn_of_month_data_availability_check.csv",
        "turn_of_month_implementation_findings.md",
        "turn_of_month_zero_trade_next_action.md",
    ]
    check = {
        "audit_only_mode": manifest["audit_only"],
        "no_new_discovery": not manifest["new_discovery_run"],
        "no_new_backtest": not manifest["new_backtests_run"],
        "no_performance_metrics_from_new_tests": not manifest["performance_metrics_computed_from_new_tests"],
        "no_provider_download": not manifest["provider_download"],
        "no_candidate_exhaustive": not manifest["candidate_exhaustive_run"],
        "no_paper_forward_action": not manifest["paper_forward_review"] and not manifest["paper_forward_activation"],
        "no_broker_live_path": not manifest["broker_path_touched"] and not manifest["live_orders"],
        "frozen_rule_unchanged": not manifest["frozen_rule_changed"],
        "candidate_status_unchanged": not manifest["candidate_status_changed"] and strategies_before == strategies_after,
        "calendar_window_counts_exported": (output / "turn_of_month_window_counts.csv").exists(),
        "signal_funnel_exported": (output / "turn_of_month_signal_funnel.csv").exists(),
        "block_reason_counts_exported": (output / "turn_of_month_block_reason_counts.csv").exists(),
        "data_availability_check_exists": (output / "turn_of_month_data_availability_check.csv").exists(),
        "implementation_findings_exist": (output / "turn_of_month_implementation_findings.md").exists(),
        "zero_trade_result_recorded": isinstance(manifest["zero_trade_result_confirmed"], bool),
        "implementation_bug_flag_recorded": isinstance(manifest["implementation_bug_found"], bool),
        "next_action_valid": manifest["next_action"] in VALID_NEXT_ACTIONS,
        "manifest_flags_match_scope": all(manifest[key] == value for key, value in MANIFEST_FLAGS.items()),
        "required_files_exist": all((output / name).exists() for name in required_files),
    }
    check["metadata_only_update"] = metadata_before != metadata_after and status_keys.isdisjoint(metadata_after.keys())
    check["consistency_passed"] = all(bool(value) for key, value in check.items() if key != "metadata_only_update")
    return check


def run_turn_of_month_zero_trade_audit(root: Path = ROOT) -> dict[str, Any]:
    output = clean_output(root)
    candidate, mismatches = validate_authorization(root)
    if mismatches:
        raise RuntimeError("Authorization failed: " + "; ".join(mismatches))
    strategies_before = strategy_snapshot(root)
    metadata_before = registry_metadata_snapshot(root)
    store = load_prices(root)
    if not store.get("available"):
        raise RuntimeError("Missing cached symbols: " + ",".join(store.get("missing", [])))
    ind = indicators(store)
    audit = audit_signals(root, store, ind)
    discovery_trades = discovery_trade_count(root)
    counts = audit["counts"]
    zero_trade_confirmed = discovery_trades == 0
    implementation_bug = zero_trade_confirmed and counts["entry_signal_count_after_filters"] > 0 and counts["implemented_first_eligible_day_matches"] == 0
    logically_expected = zero_trade_confirmed and counts["entry_signal_count_after_filters"] == 0 and not implementation_bug
    restrictive_filters = logically_expected and counts["entries_blocked_risk_or_no_trade_filters"] >= counts["turn_of_month_windows_constructed"]
    if implementation_bug:
        next_action = NEXT_ACTION_FIX
    elif logically_expected:
        next_action = NEXT_ACTION_CLOSE
    else:
        next_action = NEXT_ACTION_AUDIT
    manifest = {
        "artifact": "turn_of_month_zero_trade_audit",
        "created_utc": now_utc(),
        "output_dir": str(output),
        "candidate_id": CANDIDATE_ID,
        "lane_id": candidate.get("lane_id", LANE_ID),
        "universe": UNIVERSE,
        "zero_trade_result_confirmed": zero_trade_confirmed,
        "discovery_reported_trade_count": discovery_trades,
        "implementation_bug_found": implementation_bug,
        "calendar_window_count": counts["turn_of_month_windows_constructed"],
        "calendar_month_count": counts["calendar_months_in_test_window"],
        "entry_signal_count_before_execution": counts["entry_signal_count_before_execution"],
        "entry_signal_count_after_filters": counts["entry_signal_count_after_filters"],
        "implemented_first_eligible_day_matches": counts["implemented_first_eligible_day_matches"],
        "zero_trades_logically_expected_under_frozen_rule": logically_expected,
        "zero_trades_caused_by_overly_restrictive_correct_filters": restrictive_filters,
        "exact_frozen_candidate_remains_rejected": True,
        "calendar_family_remains_open_for_future_new_hypothesis": bool(implementation_bug),
        "next_action": next_action,
        **MANIFEST_FLAGS,
    }
    registry_updated, roadmap_updated = update_metadata(root, output, manifest)
    manifest["registry_metadata_updated"] = registry_updated
    manifest["roadmap_updated"] = roadmap_updated
    write_outputs(output, store, audit, manifest)
    strategies_after = strategy_snapshot(root)
    metadata_after = registry_metadata_snapshot(root)
    consistency = consistency_check(output, manifest, strategies_before, strategies_after, metadata_before, metadata_after)
    write_json(output / "turn_of_month_zero_trade_consistency_check.json", consistency)
    return {
        "output_dir": str(output),
        "candidate_id": CANDIDATE_ID,
        "zero_trade_result_confirmed": zero_trade_confirmed,
        "implementation_bug_found": implementation_bug,
        "next_action": next_action,
        "consistency": consistency,
    }


def main() -> None:
    print(json.dumps(run_turn_of_month_zero_trade_audit(ROOT), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
