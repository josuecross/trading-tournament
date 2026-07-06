from __future__ import annotations

import csv
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.objective_reset.objective_reset_review import write_json, write_text
from strategy_lab.research_os.research.profit_oriented_research_batch_v1 import write_csv


OUTPUT_DIR = Path("evidence") / "research_recovery" / "backtest_sample_adequacy_report" / "latest"
NEXT_ACTION = "review_backtest_sample_adequacy_before_stronger_interpretation"

RUN_SPECS: tuple[dict[str, Any], ...] = (
    {
        "run_id": "public_source_turn_of_month_bounded_bt_run",
        "path": Path("evidence") / "research_recovery" / "public_source_turn_of_month_bounded_bt_run" / "latest",
        "row_files": ("row_level_results.csv",),
        "strategy_type": "event_calendar",
        "expected": True,
    },
    {
        "run_id": "public_source_percent_b_money_flow_bounded_bt_run",
        "path": Path("evidence") / "research_recovery" / "public_source_percent_b_money_flow_bounded_bt_run" / "latest",
        "row_files": ("row_level_results.csv",),
        "strategy_type": "daily_signal",
        "expected": True,
    },
    {
        "run_id": "public_source_larry_connors_rsi2_bounded_bt_run",
        "path": Path("evidence") / "research_recovery" / "public_source_larry_connors_rsi2_bounded_bt_run" / "latest",
        "row_files": ("row_level_results.csv",),
        "strategy_type": "daily_signal",
        "expected": True,
    },
    {
        "run_id": "high_return_tactical_etf_equity_index_bounded_run",
        "path": Path("evidence") / "research_recovery" / "high_return_tactical_etf_equity_index_bounded_run" / "latest",
        "row_files": ("high_return_tactical_bounded_run_results.csv",),
        "strategy_type": "monthly_rotation",
        "expected": True,
    },
    {
        "run_id": "commodity_basket_etf_momentum_bounded_run",
        "path": Path("evidence") / "research_recovery" / "commodity_basket_etf_momentum_bounded_run" / "latest",
        "row_files": ("commodity_basket_bounded_row_results.csv",),
        "strategy_type": "monthly_rotation",
        "expected": True,
    },
    {
        "run_id": "global_multi_asset_etf_momentum_bounded_run",
        "path": Path("evidence") / "research_recovery" / "global_multi_asset_etf_momentum_bounded_run" / "latest",
        "row_files": ("global_multi_asset_bounded_row_results.csv",),
        "strategy_type": "monthly_rotation",
        "expected": True,
    },
    {
        "run_id": "regional_international_momentum_bounded_run",
        "path": Path("evidence") / "research_recovery" / "regional_international_momentum_bounded_run" / "latest",
        "row_files": ("regional_international_momentum_bounded_row_results.csv",),
        "strategy_type": "monthly_rotation",
        "expected": True,
    },
    {
        "run_id": "macro_gld_duration_risk_off_bounded_run",
        "path": Path("evidence") / "research_recovery" / "macro_gld_duration_risk_off_bounded_run" / "latest",
        "row_files": ("macro_gld_bounded_row_results.csv",),
        "strategy_type": "monthly_rotation",
        "expected": True,
    },
    {
        "run_id": "macro_gld_duration_risk_off_confirmation_report",
        "path": Path("evidence") / "research_recovery" / "macro_gld_duration_risk_off_confirmation_report" / "latest",
        "row_files": ("survivor_confirmation_rows.csv",),
        "strategy_type": "monthly_rotation",
        "expected": True,
    },
    {
        "run_id": "volatility_throttle_focused_research_followup_run",
        "path": Path("evidence") / "research_recovery" / "volatility_throttle_focused_research_followup_run" / "latest",
        "row_files": ("vol_throttle_followup_results.csv",),
        "strategy_type": "monthly_rotation",
        "expected": True,
    },
)

ROBUSTNESS_SPECS: tuple[dict[str, Any], ...] = (
    {
        "path": Path("evidence") / "research_recovery" / "public_source_turn_of_month_bounded_bt_robustness" / "latest",
        "event_file": "calendar_event_stability_report.csv",
        "stress_file": "base_vs_cost_stress.csv",
        "subperiod_file": "subperiod_performance.csv",
        "rolling_file": "rolling_window_weakness.csv",
        "rolling_flag": "rolling_window_weakness",
    },
    {
        "path": Path("evidence") / "research_recovery" / "high_return_tactical_etf_equity_index_bounded_robustness" / "latest",
        "stress_file": "base_vs_stress_row_results.csv",
        "subperiod_file": "subperiod_performance.csv",
        "rolling_file": "rolling_window_weakness.csv",
        "rolling_flag": "unacceptable_rolling_weakness",
    },
    {
        "path": Path("evidence") / "research_recovery" / "macro_gld_duration_risk_off_bounded_robustness" / "latest",
        "stress_file": "base_vs_stress_row_results.csv",
        "subperiod_file": "subperiod_performance.csv",
        "rolling_file": "rolling_window_weakness.csv",
        "rolling_flag": "unacceptable_rolling_weakness",
    },
)

SUMMARY_FIELDS = (
    "run_id",
    "evidence_path",
    "lane_id",
    "family_id",
    "variant_id",
    "role",
    "strategy_type",
    "effective_start_date",
    "effective_end_date",
    "calendar_years_covered",
    "trading_days_covered",
    "limiting_symbols",
    "rebalance_count",
    "trade_signal_event_count",
    "event_count_source",
    "average_exposure",
    "turnover_proxy",
    "data_blocked_status",
    "invariant_status",
    "subperiod_coverage_status",
    "rolling_window_weakness_status",
    "cost_stress_status",
    "missing_evidence_items",
    "sample_adequacy_classification",
    "diagnostic_interpretation_allowed",
    "notes",
)
EFFECTIVE_HISTORY_FIELDS = (
    "run_id",
    "variant_id",
    "effective_start_date",
    "effective_end_date",
    "calendar_years_covered",
    "trading_days_covered",
    "symbol_count",
    "limiting_symbols",
    "data_blocked_status",
)
EVENT_FIELDS = (
    "run_id",
    "variant_id",
    "role",
    "strategy_type",
    "trade_count",
    "rebalance_count",
    "event_count",
    "entry_signal_count",
    "exit_signal_count",
    "event_count_source",
    "average_exposure",
    "sample_adequacy_classification",
)


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def boolish(value: Any) -> bool | None:
    text = str(value).strip().lower()
    if text in {"true", "1", "yes"}:
        return True
    if text in {"false", "0", "no"}:
        return False
    return None


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in {"", None}:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def as_int(value: Any, default: int = 0) -> int:
    try:
        if value in {"", None}:
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def date_value(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text[:10])
    except ValueError:
        return None


def years_between(start: str, end: str) -> float:
    left = date_value(start)
    right = date_value(end)
    if not left or not right or right < left:
        return 0.0
    return round((right - left).days / 365.25, 4)


def split_symbols(row: dict[str, str]) -> list[str]:
    raw = (
        row.get("symbols_used")
        or row.get("symbols")
        or row.get("universe")
        or row.get("comparator_references")
        or ""
    )
    symbols: list[str] = []
    for item in str(raw).replace(",", "|").split("|"):
        item = item.strip()
        if item and item.isupper() and len(item) <= 8 and item not in {"SPY_200D", "BIL_CASH"}:
            symbols.append(item)
    return sorted(set(symbols))


def load_cache_dates(root: Path) -> dict[str, list[str]]:
    cache_dir = root / "data" / "cache"
    dates: dict[str, list[str]] = {}
    for path in cache_dir.glob("*.csv"):
        symbol = path.stem.upper()
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            series = [row.get("date", "")[:10] for row in reader if row.get("date")]
        if series:
            dates[symbol] = sorted(set(series))
    return dates


def count_common_trading_days(cache_dates: dict[str, list[str]], symbols: list[str], start: str, end: str) -> tuple[int, str]:
    if not symbols:
        return 0, "unknown"
    available = {symbol: cache_dates.get(symbol, []) for symbol in symbols}
    present = {symbol: values for symbol, values in available.items() if values}
    if not present:
        return 0, "missing_symbol_date_cache"
    start_text = start[:10]
    end_text = end[:10]
    sets = []
    for values in present.values():
        sets.append({value for value in values if start_text <= value <= end_text})
    common = set.intersection(*sets) if sets else set()
    first_dates = {symbol: values[0] for symbol, values in present.items() if values}
    last_dates = {symbol: values[-1] for symbol, values in present.items() if values}
    latest_first = max(first_dates.values()) if first_dates else ""
    earliest_last = min(last_dates.values()) if last_dates else ""
    limiting = [
        symbol
        for symbol in present
        if first_dates.get(symbol) == latest_first or last_dates.get(symbol) == earliest_last
    ]
    missing = [symbol for symbol in symbols if symbol not in present]
    if missing:
        limiting.extend(f"{symbol}:missing" for symbol in missing)
    return len(common), "|".join(sorted(set(limiting))) if limiting else "none"


def choose(row: dict[str, str], *names: str) -> str:
    for name in names:
        value = row.get(name)
        if value not in {"", None}:
            return str(value)
    return ""


def manifest_for(path: Path) -> dict[str, Any]:
    manifests = sorted(path.glob("*manifest.json"))
    if not manifests:
        return {}
    return read_json(manifests[0])


def row_file_for(path: Path, candidates: tuple[str, ...]) -> Path | None:
    for filename in candidates:
        candidate = path / filename
        if candidate.exists():
            return candidate
    return None


def event_counts_from_robustness(root: Path) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for spec in ROBUSTNESS_SPECS:
        event_name = spec.get("event_file")
        if not event_name:
            continue
        for row in read_csv_rows(root / spec["path"] / event_name):
            counts[row.get("variant_id", "")] += as_int(row.get("event_count"))
    return dict(counts)


def aux_status_by_variant(root: Path) -> dict[str, dict[str, str]]:
    aux: dict[str, dict[str, str]] = defaultdict(dict)
    for spec in ROBUSTNESS_SPECS:
        path = root / spec["path"]
        stress_file = spec.get("stress_file")
        if stress_file:
            for row in read_csv_rows(path / stress_file):
                variant = row.get("variant_id", "")
                if not variant:
                    continue
                pass10 = choose(row, "stress_10bps_numeric_criteria_pass")
                pass25 = choose(row, "stress_25bps_numeric_criteria_pass")
                if pass10 or pass25:
                    aux[variant]["cost_stress_status"] = f"10bps={pass10 or 'unknown'};25bps={pass25 or 'unknown'}"
                elif row.get("fails_only_due_to_cost_stress"):
                    aux[variant]["cost_stress_status"] = f"fails_only_due_to_cost_stress={row.get('fails_only_due_to_cost_stress')}"
        subperiod_file = spec.get("subperiod_file")
        if subperiod_file:
            by_variant: dict[str, list[bool | None]] = defaultdict(list)
            for row in read_csv_rows(path / subperiod_file):
                by_variant[row.get("variant_id", "")].append(boolish(row.get("subperiod_weakness_flag")))
            for variant, values in by_variant.items():
                if not variant:
                    continue
                valid = [value for value in values if value is not None]
                aux[variant]["subperiod_coverage_status"] = (
                    f"subperiods={len(values)};weak={sum(1 for value in valid if value)}"
                )
        rolling_file = spec.get("rolling_file")
        if rolling_file:
            flag_name = spec.get("rolling_flag", "rolling_window_weakness")
            for row in read_csv_rows(path / rolling_file):
                variant = row.get("variant_id", "")
                if not variant:
                    continue
                flag = row.get(flag_name, "")
                aux[variant]["rolling_window_weakness_status"] = f"{flag_name}={flag}"
    return dict(aux)


def infer_counts(row: dict[str, str], manifest: dict[str, Any], event_counts: dict[str, int]) -> tuple[int, int, int, str]:
    variant = row.get("variant_id", "")
    trade = as_int(choose(row, "trade_count"))
    rebalance = as_int(choose(row, "rebalance_count"))
    if not rebalance:
        rebalance = trade
    event_count = event_counts.get(variant, 0)
    source = "robustness_event_count" if event_count else ""
    if not event_count and trade:
        event_count = trade
        source = "row_trade_count"
    if not event_count and row.get("variant_role") == "source_primary":
        entry = as_int(manifest.get("entry_signal_count"))
        if entry:
            event_count = entry
            source = "manifest_entry_signal_count"
    return trade, rebalance, event_count, source or "missing"


def evidence_gaps(
    *,
    row: dict[str, str],
    strategy_type: str,
    event_source: str,
    aux: dict[str, str],
    start: str,
    end: str,
) -> list[str]:
    gaps: list[str] = []
    if not start or not end:
        gaps.append("missing_effective_date_window")
    if event_source == "missing" and strategy_type in {"event_calendar", "daily_signal"}:
        gaps.append("missing_event_or_signal_count")
    if "subperiod_coverage_status" not in aux:
        gaps.append("missing_subperiod_report")
    if "rolling_window_weakness_status" not in aux:
        gaps.append("missing_rolling_window_report")
    if "cost_stress_status" not in aux:
        gaps.append("missing_cost_stress_report")
    if not split_symbols(row):
        gaps.append("missing_symbol_coverage_fields")
    return gaps


def classify_sample(
    *,
    strategy_type: str,
    calendar_years: float,
    trading_days: int,
    event_count: int,
    data_blocked: bool,
    invariant_pass: bool,
    gaps: list[str],
) -> str:
    if data_blocked or not invariant_pass:
        return "missing_required_evidence"
    if "missing_effective_date_window" in gaps:
        return "missing_required_evidence"
    if calendar_years < 3.0 or (trading_days and trading_days < 756):
        return "too_short_or_too_sparse"
    if strategy_type in {"event_calendar", "daily_signal"}:
        if event_count == 0:
            return "missing_required_evidence"
        if event_count < 30:
            return "insufficient_event_count"
    if strategy_type == "monthly_rotation":
        if calendar_years < 10.0:
            return "marginal_sample"
        if event_count and event_count < 30:
            return "insufficient_event_count"
    if calendar_years >= 10.0 and (trading_days == 0 or trading_days >= 2520):
        return "adequate_diagnostic_sample"
    return "marginal_sample"


def normalize_row(
    *,
    root: Path,
    spec: dict[str, Any],
    row: dict[str, str],
    manifest: dict[str, Any],
    cache_dates: dict[str, list[str]],
    event_counts: dict[str, int],
    aux_by_variant: dict[str, dict[str, str]],
) -> dict[str, Any]:
    variant = row.get("variant_id", "")
    role = choose(row, "variant_role", "role")
    start = choose(row, "effective_start_date", "start_date")
    end = choose(row, "effective_end_date", "end_date")
    symbols = split_symbols(row)
    trading_days, limiting = count_common_trading_days(cache_dates, symbols, start, end)
    years = years_between(start, end)
    trade, rebalance, event_count, event_source = infer_counts(row, manifest, event_counts)
    average_exposure = choose(row, "average_exposure", "average_spy_exposure_share")
    turnover = choose(row, "turnover_proxy", "turnover")
    data_status = choose(row, "data_availability_status") or ("data_blocked" if manifest.get("data_blocked_row_count") else "cache_ready")
    invariant_value = boolish(choose(row, "exposure_invariant_pass"))
    if invariant_value is None:
        invariant_value = manifest.get("exposure_invariant_passed") is True
    aux = aux_by_variant.get(variant, {})
    gaps = evidence_gaps(row=row, strategy_type=spec["strategy_type"], event_source=event_source, aux=aux, start=start, end=end)
    classification = classify_sample(
        strategy_type=spec["strategy_type"],
        calendar_years=years,
        trading_days=trading_days,
        event_count=event_count,
        data_blocked="blocked" in data_status.lower() or data_status.lower() == "data_blocked",
        invariant_pass=invariant_value is True,
        gaps=gaps,
    )
    return {
        "run_id": spec["run_id"],
        "evidence_path": str((root / spec["path"]).resolve()),
        "lane_id": choose(row, "lane_id") or manifest.get("lane_id", ""),
        "family_id": choose(row, "family_id") or manifest.get("family_id", ""),
        "variant_id": variant,
        "role": role,
        "strategy_type": spec["strategy_type"],
        "effective_start_date": start,
        "effective_end_date": end,
        "calendar_years_covered": years,
        "trading_days_covered": trading_days,
        "limiting_symbols": limiting,
        "rebalance_count": rebalance,
        "trade_count": trade,
        "trade_signal_event_count": event_count,
        "event_count": event_count,
        "entry_signal_count": manifest.get("entry_signal_count", ""),
        "exit_signal_count": manifest.get("exit_signal_count", ""),
        "event_count_source": event_source,
        "average_exposure": average_exposure,
        "turnover_proxy": turnover,
        "data_blocked_status": data_status,
        "invariant_status": "pass" if invariant_value is True else "fail_or_unknown",
        "subperiod_coverage_status": aux.get("subperiod_coverage_status", "missing"),
        "rolling_window_weakness_status": aux.get("rolling_window_weakness_status", "missing"),
        "cost_stress_status": aux.get("cost_stress_status", "missing"),
        "missing_evidence_items": "|".join(gaps) if gaps else "none",
        "sample_adequacy_classification": classification,
        "diagnostic_interpretation_allowed": classification in {"adequate_diagnostic_sample", "marginal_sample"},
        "notes": "sample adequacy only; not a strategy approval or rejection",
    }


def inspect_runs(root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    cache_dates = load_cache_dates(root)
    event_counts = event_counts_from_robustness(root)
    aux_by_variant = aux_status_by_variant(root)
    summary_rows: list[dict[str, Any]] = []
    missing_run_rows: list[dict[str, Any]] = []
    inspected_paths: list[dict[str, Any]] = []
    for spec in RUN_SPECS:
        evidence_path = root / spec["path"]
        manifest = manifest_for(evidence_path)
        row_path = row_file_for(evidence_path, spec["row_files"])
        inspected_paths.append(
            {
                "run_id": spec["run_id"],
                "evidence_path": str(evidence_path.resolve()),
                "exists": evidence_path.exists(),
                "row_file": str(row_path.name) if row_path else "",
                "manifest_exists": bool(manifest),
            }
        )
        if not evidence_path.exists() or not row_path:
            missing_run_rows.append(
                {
                    "run_id": spec["run_id"],
                    "evidence_path": str(evidence_path.resolve()),
                    "missing_evidence": "missing_run_directory_or_row_results",
                    "required_for_minimum_scope": spec.get("expected", False),
                }
            )
            continue
        for row in read_csv_rows(row_path):
            summary_rows.append(
                normalize_row(
                    root=root,
                    spec=spec,
                    row=row,
                    manifest=manifest,
                    cache_dates=cache_dates,
                    event_counts=event_counts,
                    aux_by_variant=aux_by_variant,
                )
            )
    return summary_rows, missing_run_rows, inspected_paths


def classification_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for row in rows:
        counts[row["sample_adequacy_classification"]] += 1
    return dict(sorted(counts.items()))


def missing_evidence_rows(rows: list[dict[str, Any]], missing_runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        if row["missing_evidence_items"] != "none":
            out.append(
                {
                    "run_id": row["run_id"],
                    "variant_id": row["variant_id"],
                    "sample_adequacy_classification": row["sample_adequacy_classification"],
                    "missing_evidence_items": row["missing_evidence_items"],
                    "notes": "Missing evidence should be filled before stronger interpretation.",
                }
            )
    for row in missing_runs:
        out.append(
            {
                "run_id": row["run_id"],
                "variant_id": "",
                "sample_adequacy_classification": "missing_required_evidence",
                "missing_evidence_items": row["missing_evidence"],
                "notes": "Expected evidence path or row file was not available.",
            }
        )
    return out


def manifest_payload(output: Path, rows: list[dict[str, Any]], missing_runs: list[dict[str, Any]], inspected: list[dict[str, Any]]) -> dict[str, Any]:
    counts = classification_counts(rows)
    return {
        "created_utc": now_utc(),
        "evidence_path": str(output.resolve()),
        "backtest_sample_adequacy_report_only": True,
        "new_backtests_run": False,
        "strategy_logic_changed": False,
        "new_variants_added": False,
        "parameters_tuned": False,
        "public_sources_scraped": False,
        "provider_download": False,
        "intraday_data_used": False,
        "candidate_exhaustive_run": False,
        "promotion_candidates_created": False,
        "paper_demo_observation_activated": False,
        "broker_live_paths_touched": False,
        "real_money_recommendation": False,
        "fast_runtime_treated_as_quality_proof": False,
        "fast_runtime_treated_as_insufficient_testing_proof": False,
        "run_evidence_paths_inspected_count": len(inspected),
        "included_row_count": len(rows),
        "missing_run_evidence_count": len(missing_runs),
        "classification_counts": counts,
        "adequate_diagnostic_sample_count": counts.get("adequate_diagnostic_sample", 0),
        "marginal_sample_count": counts.get("marginal_sample", 0),
        "too_short_or_too_sparse_count": counts.get("too_short_or_too_sparse", 0),
        "insufficient_event_count": counts.get("insufficient_event_count", 0),
        "missing_required_evidence_count": counts.get("missing_required_evidence", 0) + len(missing_runs),
        "fast_runtime_explained_by": [
            "local_cached_daily_data",
            "small_bounded_row_counts",
            "small_etf_universes",
            "vectorized_or_table_based_computation",
            "absence_of_provider_download",
            "absence_of_optimization_grid",
        ],
        "next_action": NEXT_ACTION,
    }


def md_table(rows: list[dict[str, Any]], columns: list[str], limit: int = 20) -> str:
    if not rows:
        return "_No rows._\n"
    shown = rows[:limit]
    lines = ["|" + "|".join(columns) + "|", "|" + "|".join("---" for _ in columns) + "|"]
    for row in shown:
        lines.append("|" + "|".join(str(row.get(col, "")).replace("|", "/") for col in columns) + "|")
    if len(rows) > limit:
        lines.append(f"\n_Showing {limit} of {len(rows)} rows._")
    return "\n".join(lines) + "\n"


def summary_md(manifest: dict[str, Any], rows: list[dict[str, Any]], missing: list[dict[str, Any]]) -> str:
    weakest = [row for row in rows if row["sample_adequacy_classification"] != "adequate_diagnostic_sample"]
    return f"""# Backtest Sample Adequacy Report

Rows inspected: `{manifest['included_row_count']}`

Evidence paths inspected: `{manifest['run_evidence_paths_inspected_count']}`

Missing run evidence count: `{manifest['missing_run_evidence_count']}`

Classification counts: `{manifest['classification_counts']}`

Fast runtime is explainable by local cached daily data, small bounded row counts, small ETF universes, vectorized/table-based computation, no provider download, and no optimization grid. It is not treated as proof of quality or proof of insufficient testing.

## Non-Adequate Or Evidence-Gap Rows

{md_table(weakest, ['run_id', 'variant_id', 'calendar_years_covered', 'trade_signal_event_count', 'sample_adequacy_classification', 'missing_evidence_items'], 25)}

## Missing Evidence Summary

{md_table(missing, ['run_id', 'variant_id', 'sample_adequacy_classification', 'missing_evidence_items'], 25)}

Exact next action: `{manifest['next_action']}`
"""


def missing_report_md(missing: list[dict[str, Any]]) -> str:
    return f"""# Missing Evidence Report

The audit does not rerun or repair any strategy. Missing evidence is recorded so later interpretation can stay appropriately cautious.

{md_table(missing, ['run_id', 'variant_id', 'sample_adequacy_classification', 'missing_evidence_items', 'notes'], 100)}
"""


def fast_runtime_md(manifest: dict[str, Any]) -> str:
    reasons = "\n".join(f"- `{item}`" for item in manifest["fast_runtime_explained_by"])
    return f"""# Fast Runtime Explanation

Fast bounded-run execution is plausible in this repository for these reasons, including local cached daily data:

{reasons}

The report explicitly records:

- Fast runtime is not proof of quality: `{manifest['fast_runtime_treated_as_quality_proof']}`
- Fast runtime is not proof of insufficient testing: `{manifest['fast_runtime_treated_as_insufficient_testing_proof']}`
- New backtests run by this audit: `{manifest['new_backtests_run']}`
- Provider download: `{manifest['provider_download']}`
- Optimization grid: `false`
"""


def next_action_md() -> str:
    return f"""# Backtest Sample Adequacy Report Next Action

Exact next action:

`{NEXT_ACTION}`

Do not execute the next action in this task.
"""


def consistency_check(manifest: dict[str, Any], output: Path, rows: list[dict[str, Any]]) -> dict[str, Any]:
    required = {
        "backtest_sample_adequacy_manifest.json": (output / "backtest_sample_adequacy_manifest.json").exists(),
        "sample_adequacy_table.csv": (output / "sample_adequacy_table.csv").exists(),
        "effective_history_table.csv": (output / "effective_history_table.csv").exists(),
        "event_signal_count_table.csv": (output / "event_signal_count_table.csv").exists(),
        "missing_evidence_report.md": (output / "missing_evidence_report.md").exists(),
        "fast_runtime_explanation.md": (output / "fast_runtime_explanation.md").exists(),
        "backtest_sample_adequacy_summary.md": (output / "backtest_sample_adequacy_summary.md").exists(),
        "backtest_sample_adequacy_next_action.md": (output / "backtest_sample_adequacy_next_action.md").exists(),
    }
    checks: dict[str, Any] = {
        "audit_only": manifest["backtest_sample_adequacy_report_only"] is True,
        "no_forbidden_actions": manifest["new_backtests_run"] is False
        and manifest["strategy_logic_changed"] is False
        and manifest["new_variants_added"] is False
        and manifest["parameters_tuned"] is False
        and manifest["public_sources_scraped"] is False
        and manifest["provider_download"] is False
        and manifest["intraday_data_used"] is False
        and manifest["candidate_exhaustive_run"] is False
        and manifest["promotion_candidates_created"] is False
        and manifest["paper_demo_observation_activated"] is False
        and manifest["broker_live_paths_touched"] is False
        and manifest["real_money_recommendation"] is False,
        "recent_public_source_runs_included": any(row["run_id"] == "public_source_turn_of_month_bounded_bt_run" for row in rows)
        and any(row["run_id"] == "public_source_percent_b_money_flow_bounded_bt_run" for row in rows)
        and any(row["run_id"] == "public_source_larry_connors_rsi2_bounded_bt_run" for row in rows),
        "recent_project_runs_included": any(row["run_id"] == "high_return_tactical_etf_equity_index_bounded_run" for row in rows)
        and any(row["run_id"] == "commodity_basket_etf_momentum_bounded_run" for row in rows)
        and any(row["run_id"] == "global_multi_asset_etf_momentum_bounded_run" for row in rows)
        and any(row["run_id"] == "regional_international_momentum_bounded_run" for row in rows)
        and any(row["run_id"] == "macro_gld_duration_risk_off_bounded_run" for row in rows)
        and any(row["run_id"] == "volatility_throttle_focused_research_followup_run" for row in rows),
        "classification_present_for_each_row": all(row["sample_adequacy_classification"] for row in rows),
        "fast_runtime_explanation_present": len(manifest["fast_runtime_explained_by"]) >= 5,
        "next_action_valid": manifest["next_action"] == NEXT_ACTION,
        "required_files_present": all(required.values()),
        "required_files": required,
    }
    checks["consistency_passed"] = all(value is True for key, value in checks.items() if key != "required_files")
    return checks


def run(root: Path = ROOT) -> dict[str, Any]:
    output = root / OUTPUT_DIR
    output.mkdir(parents=True, exist_ok=True)
    rows, missing_runs, inspected = inspect_runs(root)
    missing = missing_evidence_rows(rows, missing_runs)
    manifest = manifest_payload(output, rows, missing_runs, inspected)

    write_json(output / "backtest_sample_adequacy_manifest.json", manifest)
    write_csv(output / "sample_adequacy_table.csv", rows, list(SUMMARY_FIELDS))
    write_csv(output / "effective_history_table.csv", rows, list(EFFECTIVE_HISTORY_FIELDS))
    write_csv(output / "event_signal_count_table.csv", rows, list(EVENT_FIELDS))
    write_csv(output / "evidence_paths_inspected.csv", inspected, ["run_id", "evidence_path", "exists", "row_file", "manifest_exists"])
    write_csv(
        output / "missing_evidence_table.csv",
        missing,
        ["run_id", "variant_id", "sample_adequacy_classification", "missing_evidence_items", "notes"],
    )
    write_text(output / "missing_evidence_report.md", missing_report_md(missing))
    write_text(output / "fast_runtime_explanation.md", fast_runtime_md(manifest))
    write_text(output / "backtest_sample_adequacy_summary.md", summary_md(manifest, rows, missing))
    write_text(output / "backtest_sample_adequacy_next_action.md", next_action_md())
    check = consistency_check(manifest, output, rows)
    write_json(output / "backtest_sample_adequacy_consistency_check.json", check)
    return {**manifest, "output_dir": str(output.resolve()), "consistency_passed": check["consistency_passed"]}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
