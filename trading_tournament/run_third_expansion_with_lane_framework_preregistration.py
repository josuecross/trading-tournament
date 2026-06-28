from __future__ import annotations

import csv
import json
import shutil
from copy import deepcopy
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = Path("evidence") / "pre_registered_lanes" / "third_expansion_with_lane_framework" / "latest"
REGISTRY_PATH = Path("strategy_lab") / "strategy_registry.yaml"
ROADMAP_PATH = Path("strategy_lab") / "RESEARCH_ROADMAP.md"
SYMBOL_MAP_PATH = Path("strategy_lab") / "approved_etf_symbol_map.yaml"
LANE_FRAMEWORK_DIR = Path("evidence") / "tournament_lane_gate_framework" / "latest"
CACHE_DIR = Path("data") / "cache"

LANE_IDS = {
    "conservative_etf_allocation_lane",
    "moderate_tactical_etf_lane",
    "macro_gld_duration_risk_off_lane",
    "diversifier_contribution_lane",
    "intraday_research_only_lane",
}

NEXT_ACTION_DISCOVERY = "run_third_expansion_discovery_batch_with_lane_framework"
NEXT_ACTION_DATA = "authorize_data_availability_or_cache_refresh_for_third_expansion_batch"
NEXT_ACTION_MANUAL = "manual_review_required_for_third_expansion_batch"
VALID_NEXT_ACTIONS = {NEXT_ACTION_DISCOVERY, NEXT_ACTION_DATA, NEXT_ACTION_MANUAL}

DATA_STATUS_SUFFICIENT = "sufficient_for_third_expansion_discovery"
DATA_STATUS_MISSING = "missing_required_data"
DATA_STATUS_UNKNOWN = "unknown_requires_manual_review"
VALID_DATA_STATUSES = {DATA_STATUS_SUFFICIENT, DATA_STATUS_MISSING, DATA_STATUS_UNKNOWN}

STRATEGY_OUTCOMES = ["discovery_reject", "promotion_review_candidate"]
MACRO_OUTCOMES = ["discovery_reject", "promotion_review_candidate_macro"]
LIMITED_HISTORY_MACRO_OUTCOMES = ["discovery_reject", "promotion_review_candidate_macro_limited_history"]
CONTROL_OUTCOMES = ["benchmark_control_accepted", "benchmark_control_reject", "diagnostic_only"]
INTRADAY_AUDIT_OUTCOMES = ["intraday_research_ready", "intraday_research_not_ready"]
FORBIDDEN_OUTCOMES = ["candidate_exhaustive", "paper_forward", "paper_forward_active", "demo_active", "live_ready"]

REQUIRED_COLUMNS = ["date", "open", "high", "low", "close", "adj_close", "volume"]

EXACT_REJECTED_VARIANTS = {
    "dmr_liquid_etf_oversold_rebound_v1",
    "vm_spy_qqq_daily_vol_target_v1",
    "vol_compression_breakout_etf_v1",
    "rs_pair_rotation_spy_qqq_xlk_xlu_v1",
    "sector_rs_weekly_cash_filter_v1",
    "managed_futures_etf_trend_wrapper_v1",
    "gld_gror_balanced_momentum_clean_v1",
    "donchian_atr_breakout_etf_v1",
    "turn_of_month_spy_qqq_v1",
    "cash_pause_overlay_meta_v1",
    "gror_balanced_momentum_60_40_v1",
    "bsr_breadth_state_top_assets_v1",
    "bsr_breadth_state_defensive_shift_v1",
    "bsr_breadth_state_lowvol_overlay_v1",
}

EXPLICITLY_EXCLUDED_CANDIDATES = [
    "intraday_readiness_audit_v1",
    "weekly_tactical_tlt_ief_spy_bil_v1",
    "gtaa_faber_style_benchmark_lane",
    *sorted(EXACT_REJECTED_VARIANTS),
]

MANIFEST_FLAGS = {
    "pre_registration_only": True,
    "data_availability_audit_only": True,
    "lane_framework_used": True,
    "failure_lessons_applied": True,
    "candidate_count": 4,
    "backtests_run": False,
    "discovery_run": False,
    "performance_metrics_computed": False,
    "provider_download": False,
    "candidate_exhaustive_run": False,
    "paper_forward_review": False,
    "paper_forward_activation": False,
    "broker_path_touched": False,
    "live_orders": False,
    "real_money_recommendation": False,
    "accepted_strategy_state_changed": False,
    "rejected_strategy_state_changed": False,
    "old_gld_gror_state_resumed": False,
    "intraday_demo_candidate_included": False,
    "event_data_candidate_included": False,
}

CANDIDATES: list[dict[str, Any]] = [
    {
        "candidate_id": "dual_momentum_paa_clean_v1",
        "lane_id": "macro_gld_duration_risk_off_lane",
        "family": "dual_momentum_paa_etf_wrapper",
        "timeframe": "monthly",
        "purpose": "Test a protective allocation rule with fixed relative and absolute momentum across equity, gold, duration, aggregate bond, and cash sleeves.",
        "hypothesis": "A compact dual-momentum protective allocation can improve crisis behavior versus equity-heavy references without resuming old GROR state.",
        "universe": ["SPY", "QQQ", "GLD", "IEF", "AGG", "BIL"],
        "required_symbols": ["SPY", "QQQ", "GLD", "IEF", "AGG", "BIL"],
        "entry_allocation_rule": [
            "Rebalance on the first valid trading session of each calendar month using only prior completed daily adjusted close data.",
            "For SPY, QQQ, GLD, IEF, and AGG, compute fixed 252-trading-day total return and 200-trading-day simple moving average from the prior session.",
            "An asset is eligible only when its 252-trading-day total return is positive and its prior close is above its 200-trading-day simple moving average.",
            "Rank eligible assets by fixed 252-trading-day total return.",
            "Allocate 50% to each of the top two eligible assets.",
            "Unused 50% sleeves are allocated to BIL.",
        ],
        "exit_deallocation_rule": [
            "Hold monthly weights until the next scheduled monthly rebalance.",
            "A missing required price for any required symbol blocks the candidate for discovery rather than replacing the symbol.",
            "No intra-month stop, intraday confirmation, or post-result threshold change is authorized.",
        ],
        "sizing": "Two 50% sleeves; each sleeve holds one eligible asset or BIL; total gross exposure remains 100%.",
        "risk_controls": [
            "No leverage, no margin, no shorting, no derivatives.",
            "Same-window benchmark comparison is mandatory.",
            "Reject if correlation and allocation overlap show an active combo or SPY_200d duplicate without incremental macro protection.",
        ],
        "benchmark_group": ["active VM", "active DSR", "active combo", "SPY_200d", "SPY", "QQQ", "GLD", "IEF", "AGG", "BIL"],
        "valid_future_outcomes": MACRO_OUTCOMES,
        "acceptance_gates": [
            "Must survive drawdown, risk-buffer, turnover, and slippage/spread stress gates.",
            "Must show same-window benefit versus active combo or SPY_200d through drawdown reduction or risk-adjusted improvement.",
            "Must not be explained by GLD, IEF, AGG, SPY, or QQQ buy-and-hold exposure alone.",
        ],
        "rejection_gates": [
            "Reject if weaker than active references without risk benefit.",
            "Reject if it behaves as old GROR, active combo, or SPY_200d under a new name.",
            "Reject if any required symbol lacks approved cache support.",
        ],
        "data_requirements": "Approved local daily OHLCV plus adjusted close for SPY, QQQ, GLD, IEF, AGG, and BIL with at least 504 rows.",
        "start_window_methodology": "Start at the first date where every required non-cash asset has 252-day momentum and 200-day SMA history; benchmarks use the same start date.",
        "same_window_or_mixed_inception_treatment": "Same-window treatment is required for every benchmark and buy-and-hold reference.",
    },
    {
        "candidate_id": "gld_ief_spy_defensive_rotation_v1",
        "lane_id": "macro_gld_duration_risk_off_lane",
        "family": "gld_ief_spy_defensive_rotation",
        "timeframe": "weekly",
        "purpose": "Test a compact equity, gold, duration, and cash rotation that is simpler than GROR.",
        "hypothesis": "A one-asset weekly rotation among SPY, GLD, and IEF with BIL fallback can capture macro risk-off behavior with less complexity than prior GLD/GROR variants.",
        "universe": ["SPY", "GLD", "IEF", "BIL"],
        "required_symbols": ["SPY", "GLD", "IEF", "BIL"],
        "entry_allocation_rule": [
            "Rebalance on the first valid trading session after each completed week using prior completed daily adjusted close data.",
            "Compute fixed 63-trading-day total return and 200-trading-day simple moving average for SPY, GLD, and IEF from the prior session.",
            "An asset is eligible only when its 63-trading-day total return is positive and its prior close is above its 200-trading-day simple moving average.",
            "Allocate 100% to the eligible asset with the highest fixed 63-trading-day total return.",
            "Allocate 100% to BIL when no asset is eligible.",
        ],
        "exit_deallocation_rule": [
            "Hold the selected asset or BIL until the next scheduled weekly rebalance.",
            "A missing required price for any required symbol blocks the candidate for discovery.",
            "No alternate lookback, stop, or GLD-specific override is authorized.",
        ],
        "sizing": "One 100% sleeve in SPY, GLD, IEF, or BIL; total gross exposure remains 100%.",
        "risk_controls": [
            "No leverage, no margin, no shorting, no derivatives.",
            "Same-window macro benchmark comparison is mandatory.",
            "GLD buy-and-hold explanation check is mandatory.",
        ],
        "benchmark_group": ["active VM", "active DSR", "active combo", "SPY_200d", "SPY", "GLD", "IEF", "BIL"],
        "valid_future_outcomes": MACRO_OUTCOMES,
        "acceptance_gates": [
            "Must survive drawdown, risk-buffer, turnover, and slippage/spread stress gates.",
            "Must show same-window crisis or drawdown benefit versus active combo, SPY_200d, and GLD buy-and-hold.",
            "Must not be a GLD buy-and-hold wrapper with extra turnover.",
        ],
        "rejection_gates": [
            "Reject if GLD buy-and-hold explains the result.",
            "Reject if same-window benchmarks are unavailable.",
            "Reject if it duplicates the old GROR failure pattern.",
        ],
        "data_requirements": "Approved local daily OHLCV plus adjusted close for SPY, GLD, IEF, and BIL with at least 504 rows.",
        "start_window_methodology": "Start at the first date where SPY, GLD, and IEF have 63-day momentum and 200-day SMA history; benchmarks use the same start date.",
        "same_window_or_mixed_inception_treatment": "Same-window treatment is required for every benchmark and buy-and-hold reference.",
    },
    {
        "candidate_id": "static_all_weather_benchmark_v1",
        "lane_id": "diversifier_contribution_lane",
        "family": "static_all_weather_or_permanent_portfolio_benchmark",
        "timeframe": "monthly",
        "purpose": "Create a static diversification benchmark/control for drawdown and contribution review.",
        "hypothesis": "A fixed equity, duration, gold, and cash control can reveal whether new macro rows add value beyond simple diversification.",
        "universe": ["SPY", "IEF", "GLD", "BIL"],
        "required_symbols": ["SPY", "IEF", "GLD", "BIL"],
        "entry_allocation_rule": [
            "Rebalance on the first valid trading session of each calendar month using prior completed daily adjusted close data.",
            "Hold static target weights: 30% SPY, 40% IEF, 20% GLD, and 10% BIL.",
            "No signal ranking, no trend filter, no volatility filter, and no tactical override is authorized.",
        ],
        "exit_deallocation_rule": [
            "Maintain static weights between scheduled monthly rebalances.",
            "A missing required price for any required symbol blocks the benchmark/control from discovery.",
            "No replacement asset is authorized.",
        ],
        "sizing": "Static 30/40/20/10 allocation with total gross exposure of 100%.",
        "risk_controls": [
            "No leverage, no margin, no shorting, no derivatives.",
            "Control candidate only; promotion requires contribution evidence, not standalone return.",
            "Reject as a control if it worsens drawdown without improving interpretation of macro candidate evidence.",
        ],
        "benchmark_group": ["active combo", "SPY_200d", "SPY", "IEF", "GLD", "BIL", "portfolio-without-diversifier", "portfolio-with-diversifier"],
        "valid_future_outcomes": CONTROL_OUTCOMES,
        "acceptance_gates": [
            "Can be accepted only as a benchmark/control or diagnostic row.",
            "Must support same-window contribution analysis for macro and diversifier lanes.",
            "Must not be treated as a primary profit candidate without separate promotion-review evidence.",
        ],
        "rejection_gates": [
            "Reject as a control if data support is incomplete.",
            "Reject as a control if it duplicates BIL-heavy slowdown without explanatory value.",
            "Reject as a promotion candidate if standalone return is the only favorable property.",
        ],
        "data_requirements": "Approved local daily OHLCV plus adjusted close for SPY, IEF, GLD, and BIL with at least 504 rows.",
        "start_window_methodology": "Start at the first date where all four required symbols have valid adjusted close data; comparison rows use the same start date.",
        "same_window_or_mixed_inception_treatment": "Same-window treatment is required for every contribution and benchmark comparison.",
    },
    {
        "candidate_id": "volatility_regime_spy_qqq_bil_v1",
        "lane_id": "moderate_tactical_etf_lane",
        "family": "volatility_regime_spy_qqq_bil",
        "timeframe": "weekly",
        "purpose": "Test volatility-regime behavior with explicit anti-duplication checks versus active VM.",
        "hypothesis": "A fixed volatility regime rule can reduce exposure during unstable equity regimes without becoming a momentum/ranking clone.",
        "universe": ["SPY", "QQQ", "BIL"],
        "required_symbols": ["SPY", "QQQ", "BIL"],
        "entry_allocation_rule": [
            "Rebalance on the first valid trading session after each completed week using prior completed daily adjusted close data.",
            "Compute 20-trading-day annualized realized volatility and 200-trading-day simple moving average for SPY and QQQ from the prior session.",
            "An asset is eligible when its 20-trading-day annualized realized volatility is at or below 28% and its prior close is above its 200-trading-day simple moving average.",
            "If SPY and QQQ are both eligible, allocate 100% to the lower-volatility asset.",
            "If exactly one of SPY or QQQ is eligible, allocate 50% to that asset and 50% to BIL.",
            "If neither SPY nor QQQ is eligible, allocate 100% to BIL.",
        ],
        "exit_deallocation_rule": [
            "Hold weekly weights until the next scheduled weekly rebalance.",
            "A missing required price for any required symbol blocks the candidate for discovery.",
            "No momentum rank, daily vol target, or max-trades/week rescue from the rejected daily-vol row is authorized.",
        ],
        "sizing": "Either 100% one risk asset, 50% one risk asset plus 50% BIL, or 100% BIL; total gross exposure remains 100%.",
        "risk_controls": [
            "No leverage, no margin, no shorting, no derivatives.",
            "Strict turnover and max-trades/week diagnostics are required in future discovery.",
            "Anti-duplication checks versus active VM, active combo, SPY, and QQQ are mandatory.",
        ],
        "benchmark_group": ["active VM", "active DSR", "active combo", "SPY_200d", "SPY", "QQQ", "BIL"],
        "valid_future_outcomes": STRATEGY_OUTCOMES,
        "acceptance_gates": [
            "Must survive drawdown, risk-buffer, slippage/spread stress, turnover, and trade-frequency gates.",
            "Must beat or materially improve risk versus active VM, active combo, SPY_200d, SPY, and QQQ.",
            "Must not be explained by simple SPY or QQQ exposure.",
        ],
        "rejection_gates": [
            "Reject if it duplicates active VM or active combo behavior.",
            "Reject if slippage or turnover erases the edge.",
            "Reject if it behaves as the rejected daily-vol-target row with a weekly wrapper.",
        ],
        "data_requirements": "Approved local daily OHLCV plus adjusted close for SPY, QQQ, and BIL with at least 504 rows.",
        "start_window_methodology": "Start at the first date where SPY and QQQ have 20-day volatility and 200-day SMA history; benchmarks use the same start date.",
        "same_window_or_mixed_inception_treatment": "Same-window treatment is required for every benchmark and buy-and-hold reference.",
    },
]


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def clean_output(root: Path) -> Path:
    output = (root / OUTPUT_DIR).resolve()
    if root.resolve() not in output.parents:
        raise RuntimeError(f"refusing output outside workspace: {output}")
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)
    return output


def strategy_state_snapshot(root: Path) -> list[dict[str, Any]]:
    return deepcopy(load_yaml(root / REGISTRY_PATH).get("strategies", []))


def symbol_map_by_symbol(root: Path) -> dict[str, dict[str, Any]]:
    symbol_map = load_yaml(root / SYMBOL_MAP_PATH)
    return {str(row.get("symbol")): row for row in symbol_map.get("symbols", [])}


def read_cache_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        return [], []
    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def required_symbols() -> list[str]:
    symbols: set[str] = set()
    for candidate in CANDIDATES:
        symbols.update(candidate["required_symbols"])
    return sorted(symbols)


def audit_symbol(root: Path, symbol: str, today: date | None = None) -> dict[str, Any]:
    today = today or date.today()
    mapped = symbol_map_by_symbol(root).get(symbol, {})
    cache_path = root / CACHE_DIR / f"{symbol}.csv"
    fields, rows = read_cache_rows(cache_path)
    required_present = all(column in fields for column in REQUIRED_COLUMNS)
    dates = [row.get("date", "") for row in rows if row.get("date")]
    duplicate_dates = len(dates) - len(set(dates))
    null_count = 0
    for row in rows:
        null_count += sum(1 for column in REQUIRED_COLUMNS if row.get(column, "") in {"", "nan", "NaN", "None", "null"})
    first_date = min(dates) if dates else ""
    last_date = max(dates) if dates else ""
    stale_flag: str | bool = "unknown"
    if last_date:
        try:
            stale_flag = (today - datetime.strptime(last_date, "%Y-%m-%d").date()).days > 10
        except ValueError:
            stale_flag = "unknown"
    approved = mapped.get("allowed_for_strategy") is True
    cache_present = cache_path.exists() and bool(rows)
    adjusted_close_available = "adj_close" in fields
    supports_window = (
        approved
        and cache_present
        and required_present
        and adjusted_close_available
        and null_count == 0
        and duplicate_dates == 0
        and stale_flag is not True
        and len(rows) >= 504
    )
    if not mapped:
        status = "not_in_approved_symbol_map"
    elif approved:
        status = "approved_for_strategy"
    else:
        status = "not_approved_for_strategy"
    issue = ""
    if not approved:
        issue = "not_approved"
    elif not cache_present:
        issue = "missing_cache"
    elif not required_present:
        issue = "missing_required_columns"
    elif not adjusted_close_available:
        issue = "missing_adjusted_close"
    elif null_count:
        issue = "nulls_in_required_columns"
    elif duplicate_dates:
        issue = "duplicate_dates"
    elif stale_flag is True:
        issue = "stale_cache"
    elif stale_flag == "unknown":
        issue = "unknown_stale_status"
    elif len(rows) < 504:
        issue = "too_short_for_frozen_lookbacks"
    return {
        "symbol": symbol,
        "approved_status": status,
        "cache_path": str(cache_path.relative_to(root)) if cache_path.exists() else "",
        "first_date": first_date,
        "last_date": last_date,
        "row_count": len(rows),
        "adjusted_close_available": adjusted_close_available,
        "null_count": null_count,
        "duplicate_date_count": duplicate_dates,
        "stale_flag": stale_flag,
        "supports_candidate_window": supports_window,
        "issue": issue,
    }


def audit_data(root: Path) -> list[dict[str, Any]]:
    return [audit_symbol(root, symbol) for symbol in required_symbols()]


def candidate_data_rows(symbol_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_symbol = {row["symbol"]: row for row in symbol_rows}
    rows = []
    for candidate in CANDIDATES:
        issues = []
        for symbol in candidate["required_symbols"]:
            row = by_symbol.get(symbol)
            if row is None:
                issues.append(f"{symbol}:not_audited")
            elif row["issue"]:
                issues.append(f"{symbol}:{row['issue']}")
        if issues:
            status = "blocked_or_manual_review_required"
        else:
            status = "available_for_preregistered_discovery"
        rows.append(
            {
                "candidate_id": candidate["candidate_id"],
                "lane_id": candidate["lane_id"],
                "candidate_data_status": status,
                "data_issues": ";".join(issues),
                "symbols_audited": ";".join(candidate["required_symbols"]),
            }
        )
    return rows


def data_status(symbol_rows: list[dict[str, Any]]) -> str:
    missing_issues = {"not_approved", "missing_cache", "missing_required_columns", "missing_adjusted_close", "too_short_for_frozen_lookbacks"}
    if any(row["issue"] in missing_issues for row in symbol_rows):
        return DATA_STATUS_MISSING
    if any(row["issue"] for row in symbol_rows):
        return DATA_STATUS_UNKNOWN
    return DATA_STATUS_SUFFICIENT


def next_action_for_status(status: str) -> str:
    if status == DATA_STATUS_SUFFICIENT:
        return NEXT_ACTION_DISCOVERY
    if status == DATA_STATUS_MISSING:
        return NEXT_ACTION_DATA
    return NEXT_ACTION_MANUAL


def lane_assignment_rows() -> list[dict[str, Any]]:
    return [
        {
            "candidate_id": candidate["candidate_id"],
            "lane_id": candidate["lane_id"],
            "family": candidate["family"],
            "timeframe": candidate["timeframe"],
            "valid_future_outcomes": ";".join(candidate["valid_future_outcomes"]),
        }
        for candidate in CANDIDATES
    ]


def batch_yaml(availability_status: str, next_action: str, candidate_status_rows: list[dict[str, Any]]) -> dict[str, Any]:
    status_lookup = {row["candidate_id"]: row for row in candidate_status_rows}
    return {
        "metadata": {
            "batch_id": "third_expansion_with_lane_framework",
            "pre_registration_only": True,
            "data_availability_audit_only": True,
            "lane_framework_used": True,
            "failure_lessons_applied": True,
            "candidate_count": len(CANDIDATES),
            "data_availability_status": availability_status,
            "valid_next_action": next_action,
            "forbidden_future_outcomes": FORBIDDEN_OUTCOMES,
            "explicitly_excluded_candidates": EXPLICITLY_EXCLUDED_CANDIDATES,
        },
        "candidates": [
            {
                **candidate,
                "candidate_data_status": status_lookup[candidate["candidate_id"]]["candidate_data_status"],
                "data_issues": status_lookup[candidate["candidate_id"]]["data_issues"],
                "candidate_exhaustive_allowed_from_preregistration": False,
                "paper_forward_allowed_from_preregistration": False,
                "demo_active_allowed_from_preregistration": False,
                "live_ready_allowed": False,
                "real_money_recommendation": False,
            }
            for candidate in CANDIDATES
        ],
    }


def candidate_specs_md(candidate_status_rows: list[dict[str, Any]]) -> str:
    status_lookup = {row["candidate_id"]: row for row in candidate_status_rows}
    lines = ["# Third Expansion Candidate Specs", ""]
    for candidate in CANDIDATES:
        lines.extend(
            [
                f"## {candidate['candidate_id']}",
                "",
                f"- Lane: `{candidate['lane_id']}`",
                f"- Family: `{candidate['family']}`",
                f"- Timeframe: `{candidate['timeframe']}`",
                f"- Universe: `{';'.join(candidate['universe'])}`",
                f"- Hypothesis: {candidate['hypothesis']}",
                f"- Purpose: {candidate['purpose']}",
                f"- Data status: `{status_lookup[candidate['candidate_id']]['candidate_data_status']}`",
                f"- Valid future outcomes: `{';'.join(candidate['valid_future_outcomes'])}`",
                f"- Sizing: {candidate['sizing']}",
                f"- Data requirements: {candidate['data_requirements']}",
                f"- Start-window methodology: {candidate['start_window_methodology']}",
                f"- Same-window treatment: {candidate['same_window_or_mixed_inception_treatment']}",
                "",
                "Entry/allocation rule:",
                "",
            ]
        )
        lines.extend(f"- {item}" for item in candidate["entry_allocation_rule"])
        lines.extend(["", "Exit/deallocation rule:", ""])
        lines.extend(f"- {item}" for item in candidate["exit_deallocation_rule"])
        lines.extend(["", "Risk controls:", ""])
        lines.extend(f"- {item}" for item in candidate["risk_controls"])
        lines.extend(["", "Acceptance gates:", ""])
        lines.extend(f"- {item}" for item in candidate["acceptance_gates"])
        lines.extend(["", "Rejection gates:", ""])
        lines.extend(f"- {item}" for item in candidate["rejection_gates"])
        lines.append("")
    return "\n".join(lines)


def data_report_md(symbol_rows: list[dict[str, Any]], status: str) -> str:
    lines = [
        "# Third Expansion Data Availability Report",
        "",
        f"Data availability status: `{status}`",
        "",
        "No provider download was run. This report reads approved-symbol metadata and local cached CSV files only.",
        "",
        "| Symbol | Approved status | Cache path | First date | Last date | Rows | Adj close | Nulls | Duplicate dates | Stale flag | Supports window | Issue |",
        "|---|---|---|---|---|---:|---|---:|---:|---|---|---|",
    ]
    for row in symbol_rows:
        lines.append(
            f"| {row['symbol']} | {row['approved_status']} | {row['cache_path']} | {row['first_date']} | {row['last_date']} | {row['row_count']} | {row['adjusted_close_available']} | {row['null_count']} | {row['duplicate_date_count']} | {row['stale_flag']} | {row['supports_candidate_window']} | {row['issue']} |"
        )
    return "\n".join(lines) + "\n"


def missing_data_report_md(symbol_rows: list[dict[str, Any]]) -> str:
    missing = [row for row in symbol_rows if row["issue"]]
    lines = ["# Third Expansion Missing Data Report", ""]
    if not missing:
        lines.append("No missing or uncertain required data was found by the local cache audit.")
    else:
        lines.append("| Symbol | Issue | Required action |")
        lines.append("|---|---|---|")
        for row in missing:
            if row["issue"] in {"missing_cache", "not_approved", "missing_required_columns", "missing_adjusted_close", "too_short_for_frozen_lookbacks"}:
                action = "authorize data availability or cache refresh before discovery"
            else:
                action = "manual review before discovery"
            lines.append(f"| {row['symbol']} | {row['issue']} | {action} |")
    return "\n".join(lines) + "\n"


def benchmark_plan_md() -> str:
    lines = ["# Third Expansion Benchmark Plan", ""]
    by_lane: dict[str, list[str]] = {}
    for candidate in CANDIDATES:
        by_lane.setdefault(candidate["lane_id"], [])
        for benchmark in candidate["benchmark_group"]:
            if benchmark not in by_lane[candidate["lane_id"]]:
                by_lane[candidate["lane_id"]].append(benchmark)
    for lane_id, benchmarks in by_lane.items():
        lines.extend([f"## {lane_id}", ""])
        lines.extend(f"- {benchmark}" for benchmark in benchmarks)
        if lane_id == "macro_gld_duration_risk_off_lane":
            lines.append("- Same-window benchmark recomputation is required for active VM, active DSR, active combo, SPY_200d, buy-and-hold references, and BIL.")
        if lane_id == "moderate_tactical_etf_lane":
            lines.append("- Anti-duplication comparisons versus active VM, active combo, SPY, and QQQ are required.")
        if lane_id == "diversifier_contribution_lane":
            lines.append("- Portfolio contribution with and without the benchmark/control is required.")
        lines.append("")
    return "\n".join(lines)


def risk_policy_md() -> str:
    return """# Third Expansion Risk Policy

- Use the existing five-lane framework.
- No candidate may move directly to candidate_exhaustive, paper-forward, demo_active, live_ready, broker integration, or real-money use.
- Macro candidates require same-window comparisons, crisis diagnostics, drawdown gates, risk-buffer gates, and GLD/IEF/SPY buy-and-hold explanation checks.
- The moderate tactical volatility-regime row requires slippage/spread stress, turnover diagnostics, max-trades/week diagnostics, and anti-duplication review versus active VM and active combo.
- The static all-weather row is a benchmark/control row; it is not a primary profit candidate from this pre-registration.
- No direct futures, options, forex, crypto, margin, leverage, shorting, intraday logic, provider download, or broker/live path is authorized.
"""


def acceptance_gates_md() -> str:
    lines = ["# Third Expansion Acceptance Gates", ""]
    for candidate in CANDIDATES:
        lines.extend([f"## {candidate['candidate_id']}", ""])
        lines.extend(f"- {item}" for item in candidate["acceptance_gates"])
        lines.append(f"- Valid future outcomes: `{';'.join(candidate['valid_future_outcomes'])}`")
        lines.append("")
    return "\n".join(lines)


def rejection_gates_md() -> str:
    lines = ["# Third Expansion Rejection Gates", ""]
    for candidate in CANDIDATES:
        lines.extend([f"## {candidate['candidate_id']}", ""])
        lines.extend(f"- {item}" for item in candidate["rejection_gates"])
        lines.append("- Reject if future evidence uses alternate parameters or a changed universe from this pre-registration.")
        lines.append("")
    return "\n".join(lines)


def failure_lessons_md() -> str:
    return """# Third Expansion Failure Lessons Applied

## Lessons

- Breadth-state ETF wrappers, active-sleeve ensembles, and repeated ETF-wrapper variants did not produce promotion candidates.
- High-upside rows repeatedly failed drawdown, risk-buffer, or slippage stress gates.
- Safer rows often became too slow for the profit goal or weaker than active references.
- SPY/QQQ wrappers repeatedly risked duplicating active VM, active combo, SPY, or QQQ.
- Turn-of-month was fixed and rerun, then rejected on risk buffer, slippage stress, and benchmark edge.
- GLD/GROR state remains closed as an exact rejected variant; a simpler macro hypothesis requires a new candidate ID and same-window treatment.

## Applied Design Choices

- The batch is limited to four candidates.
- Exact rejected variants are excluded.
- No turn-of-month variant is included.
- No managed-futures wrapper is included because limited-history treatment already blocked full confidence.
- No intraday candidate is included as a demo candidate.
- No event-data candidate is included.
- BIL appears only as fallback or as a small static benchmark sleeve, not as a standalone return rescue.
- Macro rows must pass same-window benchmark checks and buy-and-hold explanation checks.
- The static all-weather row is explicitly benchmark/control, not a primary profit candidate.
- The volatility-regime row uses fixed volatility and SMA rules instead of changing the rejected daily-vol-target row.
"""


def do_not_run_md() -> str:
    return """# Do Not Run Now

This packet is pre-registration and data-availability audit only.

Do not run discovery, backtests, performance metrics, candidate_exhaustive, paper-forward review, paper-forward activation, provider download, broker/live-order code, or real-money recommendations from this task.
"""


def next_action_md(next_action: str) -> str:
    return f"# Third Expansion Next Action\n\n`{next_action}`\n\nDo not run this next action from the pre-registration task.\n"


def update_metadata(root: Path, output: Path, created_utc: str, availability_status: str, next_action: str) -> tuple[bool, bool]:
    registry_updated = False
    registry_path = root / REGISTRY_PATH
    if registry_path.exists():
        registry = load_yaml(registry_path)
        metadata = registry.setdefault("registry", {})
        metadata.update(
            {
                "third_expansion_lane_framework_preregistration_path": str(output),
                "third_expansion_lane_framework_preregistration_status": "pre_registered",
                "third_expansion_candidate_count": len(CANDIDATES),
                "third_expansion_data_availability_status": availability_status,
                "third_expansion_next_action": next_action,
                "current_next_action": next_action,
                "next_action": next_action,
                "pre_registration_only": True,
                "data_availability_audit_only": True,
                "lane_framework_used": True,
                "failure_lessons_applied": True,
                "backtests_run": False,
                "discovery_run": False,
                "performance_metrics_computed": False,
                "provider_download": False,
                "candidate_exhaustive_run": False,
                "paper_forward_review": False,
                "paper_forward_activation": False,
                "broker_path_touched": False,
                "live_orders": False,
                "real_money_recommendation": False,
                "updated_utc": created_utc,
            }
        )
        registry_path.write_text(yaml.safe_dump(registry, sort_keys=False, width=120, allow_unicode=False), encoding="utf-8")
        registry_updated = True

    roadmap_path = root / ROADMAP_PATH
    existing = roadmap_path.read_text(encoding="utf-8") if roadmap_path.exists() else "# Research Roadmap\n"
    lines = existing.splitlines()
    for index, line in enumerate(lines):
        if line.startswith("Current next action:"):
            lines[index] = f"Current next action: `{next_action}`"
            break
    else:
        lines.insert(1 if lines else 0, f"Current next action: `{next_action}`")
    base = "\n".join(lines)
    marker = "## Third Expansion With Lane Framework Pre-Registration"
    section = f"""## Third Expansion With Lane Framework Pre-Registration

- Created UTC: `{created_utc}`
- Evidence path: `{output}`
- Candidate count: `{len(CANDIDATES)}`
- Candidates: `{', '.join(candidate['candidate_id'] for candidate in CANDIDATES)}`
- Data availability status: `{availability_status}`
- Next action: `{next_action}`
- This was pre-registration and data-availability audit only. No backtest, discovery, performance metric, candidate_exhaustive, paper-forward action, provider download, broker/live-order path, accepted/rejected strategy state change, old GLD/GROR state resumption, intraday demo candidate, event-data candidate, or real-money recommendation is authorized.
"""
    updated = base.split(marker, 1)[0].rstrip() + "\n\n" + section if marker in base else base.rstrip() + "\n\n" + section
    roadmap_path.parent.mkdir(parents=True, exist_ok=True)
    roadmap_path.write_text(updated.rstrip() + "\n", encoding="utf-8")
    return registry_updated, True


def consistency_check(
    manifest: dict[str, Any],
    output: Path,
    strategies_before: list[dict[str, Any]],
    strategies_after: list[dict[str, Any]],
) -> dict[str, Any]:
    candidate_ids = [candidate["candidate_id"] for candidate in CANDIDATES]
    lane_ids = [candidate["lane_id"] for candidate in CANDIDATES]
    future_outcomes = {outcome for candidate in CANDIDATES for outcome in candidate["valid_future_outcomes"]}
    required_files = [
        "third_expansion_manifest.json",
        "third_expansion_batch.yaml",
        "third_expansion_candidate_specs.md",
        "third_expansion_lane_assignment.csv",
        "third_expansion_data_availability_report.md",
        "third_expansion_missing_data_report.md",
        "third_expansion_benchmark_plan.md",
        "third_expansion_risk_policy.md",
        "third_expansion_acceptance_gates.md",
        "third_expansion_rejection_gates.md",
        "third_expansion_failure_lessons_applied.md",
        "third_expansion_do_not_run_now.md",
        "third_expansion_next_action.md",
    ]
    check = {
        "candidate_count_between_3_and_5": 3 <= len(CANDIDATES) <= 5,
        "every_candidate_has_exactly_one_lane": all(isinstance(lane, str) and lane in LANE_IDS for lane in lane_ids),
        "unique_candidate_ids": len(candidate_ids) == len(set(candidate_ids)),
        "lane_framework_used": manifest["lane_framework_used"],
        "failure_lessons_explicitly_applied": manifest["failure_lessons_applied"] and (output / "third_expansion_failure_lessons_applied.md").exists(),
        "no_exact_rejected_variant_reopened": set(candidate_ids).isdisjoint(EXACT_REJECTED_VARIANTS),
        "no_old_gld_gror_state_resumed": not manifest["old_gld_gror_state_resumed"],
        "no_turn_of_month_variant_included": not any("turn_of_month" in candidate_id for candidate_id in candidate_ids),
        "no_intraday_demo_candidate_included": not manifest["intraday_demo_candidate_included"] and "intraday_readiness_audit_v1" not in candidate_ids,
        "no_event_data_candidate_included": not manifest["event_data_candidate_included"],
        "no_provider_download": not manifest["provider_download"],
        "no_strategy_results_computed": not manifest["performance_metrics_computed"] and not manifest["backtests_run"] and not manifest["discovery_run"],
        "no_accepted_rejected_strategy_state_changes": strategies_before == strategies_after and not manifest["accepted_strategy_state_changed"] and not manifest["rejected_strategy_state_changed"],
        "no_broker_live_path": not manifest["broker_path_touched"] and not manifest["live_orders"],
        "no_paper_forward_action": not manifest["paper_forward_review"] and not manifest["paper_forward_activation"],
        "valid_future_outcomes_lane_specific_safe": not bool(future_outcomes & set(FORBIDDEN_OUTCOMES)),
        "required_files_created": all((output / name).exists() for name in required_files),
        "manifest_flags_match_scope": all(manifest[key] == value for key, value in MANIFEST_FLAGS.items()),
        "data_availability_status_valid": manifest["data_availability_status"] in VALID_DATA_STATUSES,
        "next_action_valid": manifest["next_action"] in VALID_NEXT_ACTIONS,
    }
    check["consistency_passed"] = all(bool(value) for value in check.values())
    return check


def run_third_expansion_with_lane_framework_preregistration(root: Path = ROOT) -> dict[str, Any]:
    output = clean_output(root)
    created_utc = now_utc()
    strategies_before = strategy_state_snapshot(root)
    symbol_rows = audit_data(root)
    availability_status = data_status(symbol_rows)
    next_action = next_action_for_status(availability_status)
    candidate_status_rows = candidate_data_rows(symbol_rows)
    registry_updated, roadmap_updated = update_metadata(root, output, created_utc, availability_status, next_action)
    strategies_after = strategy_state_snapshot(root)
    manifest = {
        "artifact": "third_expansion_with_lane_framework_preregistration",
        "created_utc": created_utc,
        "output_dir": str(output),
        "lane_framework_path": str(root / LANE_FRAMEWORK_DIR),
        "included_candidate_ids": [candidate["candidate_id"] for candidate in CANDIDATES],
        "excluded_candidate_ids": EXPLICITLY_EXCLUDED_CANDIDATES,
        "required_symbols": required_symbols(),
        "data_availability_status": availability_status,
        "next_action": next_action,
        "registry_metadata_updated": registry_updated,
        "roadmap_updated": roadmap_updated,
        **MANIFEST_FLAGS,
    }

    write_json(output / "third_expansion_manifest.json", manifest)
    (output / "third_expansion_batch.yaml").write_text(
        yaml.safe_dump(batch_yaml(availability_status, next_action, candidate_status_rows), sort_keys=False, width=120, allow_unicode=False),
        encoding="utf-8",
    )
    (output / "third_expansion_candidate_specs.md").write_text(candidate_specs_md(candidate_status_rows), encoding="utf-8")
    write_csv(output / "third_expansion_lane_assignment.csv", lane_assignment_rows(), ["candidate_id", "lane_id", "family", "timeframe", "valid_future_outcomes"])
    write_csv(output / "third_expansion_symbol_data_availability.csv", symbol_rows, ["symbol", "approved_status", "cache_path", "first_date", "last_date", "row_count", "adjusted_close_available", "null_count", "duplicate_date_count", "stale_flag", "supports_candidate_window", "issue"])
    write_csv(output / "third_expansion_candidate_data_status.csv", candidate_status_rows, ["candidate_id", "lane_id", "candidate_data_status", "data_issues", "symbols_audited"])
    (output / "third_expansion_data_availability_report.md").write_text(data_report_md(symbol_rows, availability_status), encoding="utf-8")
    (output / "third_expansion_missing_data_report.md").write_text(missing_data_report_md(symbol_rows), encoding="utf-8")
    (output / "third_expansion_benchmark_plan.md").write_text(benchmark_plan_md(), encoding="utf-8")
    (output / "third_expansion_risk_policy.md").write_text(risk_policy_md(), encoding="utf-8")
    (output / "third_expansion_acceptance_gates.md").write_text(acceptance_gates_md(), encoding="utf-8")
    (output / "third_expansion_rejection_gates.md").write_text(rejection_gates_md(), encoding="utf-8")
    (output / "third_expansion_failure_lessons_applied.md").write_text(failure_lessons_md(), encoding="utf-8")
    (output / "third_expansion_do_not_run_now.md").write_text(do_not_run_md(), encoding="utf-8")
    (output / "third_expansion_next_action.md").write_text(next_action_md(next_action), encoding="utf-8")
    consistency = consistency_check(manifest, output, strategies_before, strategies_after)
    write_json(output / "third_expansion_consistency_check.json", consistency)
    return {
        "output_dir": str(output),
        "candidate_count": len(CANDIDATES),
        "candidate_ids": [candidate["candidate_id"] for candidate in CANDIDATES],
        "data_availability_status": availability_status,
        "next_action": next_action,
        "consistency": consistency,
    }


def main() -> None:
    print(json.dumps(run_third_expansion_with_lane_framework_preregistration(ROOT), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
