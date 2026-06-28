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
OUTPUT_DIR = Path("evidence") / "pre_registered_lanes" / "second_expansion_with_lane_framework" / "latest"
REGISTRY_PATH = Path("strategy_lab") / "strategy_registry.yaml"
ROADMAP_PATH = Path("strategy_lab") / "RESEARCH_ROADMAP.md"
SYMBOL_MAP_PATH = Path("strategy_lab") / "approved_etf_symbol_map.yaml"
LANE_FRAMEWORK_DIR = Path("evidence") / "tournament_lane_gate_framework" / "latest"
SECTOR_RS_PREREG_DIR = Path("evidence") / "pre_registered_lanes" / "sector_rs_limited_history" / "latest"
CACHE_DIR = Path("data") / "cache"

LANE_IDS = {
    "conservative_etf_allocation_lane",
    "moderate_tactical_etf_lane",
    "macro_gld_duration_risk_off_lane",
    "diversifier_contribution_lane",
    "intraday_research_only_lane",
}

NEXT_ACTION_DISCOVERY = "run_second_expansion_discovery_batch_with_lane_framework"
NEXT_ACTION_DATA = "authorize_data_availability_or_cache_refresh_for_second_expansion_batch"
NEXT_ACTION_MANUAL = "manual_data_review_required_for_second_expansion_batch"
VALID_NEXT_ACTIONS = {NEXT_ACTION_DISCOVERY, NEXT_ACTION_DATA, NEXT_ACTION_MANUAL}

NORMAL_OUTCOMES = ["discovery_reject", "promotion_review_candidate"]
MACRO_OUTCOMES = ["discovery_reject", "promotion_review_candidate_macro"]
OVERLAY_OUTCOMES = ["diagnostic_reject", "risk_overlay_watchlist_candidate"]
FORBIDDEN_OUTCOMES = ["candidate_exhaustive", "paper_forward", "paper_forward_active", "demo_active", "live_ready"]

REQUIRED_COLUMNS = ["date", "open", "high", "low", "close", "adj_close", "volume"]
REQUIRED_SYMBOLS = [
    "SPY",
    "QQQ",
    "GLD",
    "IEF",
    "BIL",
    "DBMF",
    "KMLM",
    "CTA",
    "IWM",
    "DIA",
    "XLK",
    "XLF",
    "XLV",
    "XLE",
    "XLI",
    "XLY",
    "XLP",
    "XLU",
    "XLB",
    "XLRE",
]

EXCLUDED_CANDIDATES = [
    "sector_rs_weekly_cash_filter_v1",
    "dmr_liquid_etf_oversold_rebound_v1",
    "vm_spy_qqq_daily_vol_target_v1",
    "vol_compression_breakout_etf_v1",
    "rs_pair_rotation_spy_qqq_xlk_xlu_v1",
    "orb_spy_qqq_30m_research_v1",
    "gap_down_fade_spy_qqq_research_v1",
    "vwap_deviation_research_v1",
    "vwap_deviation_reversion_research_v1",
    "post_earnings_drift_large_cap_later_v1",
    "gror_balanced_momentum_60_40_v1",
]

MANIFEST_FLAGS = {
    "pre_registration_only": True,
    "data_availability_audit_only": True,
    "lane_framework_used": True,
    "candidate_count": 5,
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
    "sector_rs_discovery_run": False,
    "intraday_candidates_included": False,
    "event_data_candidates_included": False,
}


CANDIDATES: list[dict[str, Any]] = [
    {
        "candidate_id": "managed_futures_etf_trend_wrapper_v1",
        "lane_id": "macro_gld_duration_risk_off_lane",
        "status": "registered_not_tested",
        "family": "managed_futures_etf_trend_wrapper",
        "timeframe": "weekly",
        "purpose": "Test whether ETF/fund-wrapper managed-futures-style trend exposure can add a return stream less correlated with SPY/QQQ/sector equity wrappers.",
        "allowed_instruments": ["DBMF", "KMLM", "CTA", "BIL", "SPY"],
        "frozen_rule": [
            "Weekly rebalance.",
            "Use prior completed data only.",
            "Rank available approved managed-futures ETF proxies by fixed 13-week momentum.",
            "Hold the top approved proxy only if it has positive 13-week momentum and sufficient data.",
            "Otherwise hold BIL.",
            "No leverage, no margin, no shorting, and no direct futures.",
        ],
        "benchmark_plan": [
            "same-window SPY_200d",
            "active combo",
            "active VM",
            "active DSR",
            "BIL",
            "SPY",
            "managed-futures proxy buy-and-hold if available",
        ],
        "valid_future_outcomes": MACRO_OUTCOMES,
        "limited_history_symbols": ["DBMF", "KMLM", "CTA"],
    },
    {
        "candidate_id": "gld_gror_balanced_momentum_clean_v1",
        "lane_id": "macro_gld_duration_risk_off_lane",
        "status": "registered_not_tested",
        "family": "macro_gld_gror_balanced_momentum",
        "timeframe": "weekly",
        "purpose": "Cleanly retest the macro / GLD / global risk-on-risk-off idea without resuming stale old GROR candidate-exhaustive state.",
        "allowed_instruments": ["SPY", "QQQ", "GLD", "IEF", "BIL"],
        "frozen_rule": [
            "Weekly rebalance.",
            "Use prior completed data only.",
            "Rank SPY, QQQ, GLD, and IEF by fixed 13-week momentum.",
            "Eligible risk/macro assets must be above their 200-day SMA.",
            "Allocate 60% to the highest-ranked eligible risk/macro asset.",
            "Allocate 40% to the highest-ranked defensive asset among GLD, IEF, and BIL.",
            "If no eligible risk/macro asset qualifies, failed sleeve goes to BIL.",
            "No leverage and no shorting.",
            "Do not resume old gror_balanced_momentum_60_40_v1 state.",
        ],
        "benchmark_plan": [
            "same-window active VM",
            "same-window active DSR",
            "same-window active combo",
            "same-window SPY_200d",
            "SPY",
            "QQQ",
            "GLD",
            "IEF",
            "BIL",
            "profit_combo_SPY200d_GLD_50_50_v1 if available as accepted/reference",
        ],
        "valid_future_outcomes": MACRO_OUTCOMES,
    },
    {
        "candidate_id": "donchian_atr_breakout_etf_v1",
        "lane_id": "moderate_tactical_etf_lane",
        "status": "registered_not_tested",
        "family": "donchian_atr_breakout_etf",
        "timeframe": "daily",
        "purpose": "Test a controlled daily breakout strategy that is structurally different from defensive ETF wrappers and sector allocation.",
        "allowed_instruments": ["SPY", "QQQ", "IWM", "DIA", "XLK", "XLF", "XLV", "XLE", "XLI", "XLY", "XLP", "XLU", "XLB", "XLRE", "BIL"],
        "frozen_rule": [
            "Daily signal.",
            "Use prior completed daily data only.",
            "Enter long at next valid open when prior close breaks above fixed 20-day high.",
            "Use ATR-based stop.",
            "Max 2 open positions.",
            "Max holding period: 20 trading days.",
            "Max weekly trade count uses the moderate tactical ETF lane gate.",
            "No intraday confirmation, no leverage, and no shorting.",
        ],
        "benchmark_plan": [
            "SPY",
            "QQQ",
            "SPY_200d",
            "active VM",
            "active combo",
            "BIL",
            "simple buy-and-hold benchmark per selected symbol group if available",
        ],
        "valid_future_outcomes": NORMAL_OUTCOMES,
    },
    {
        "candidate_id": "turn_of_month_spy_qqq_v1",
        "lane_id": "moderate_tactical_etf_lane",
        "status": "registered_not_tested",
        "family": "turn_of_month_spy_qqq",
        "timeframe": "daily_calendar_window",
        "purpose": "Test a simple fixed calendar anomaly without overfitting many calendar windows.",
        "allowed_instruments": ["SPY", "QQQ", "BIL"],
        "frozen_rule": [
            "Use one fixed turn-of-month window only.",
            "Do not optimize or test multiple calendar windows.",
            "Hold selected risk asset only during the fixed pre-registered turn-of-month window.",
            "Use a fixed selection rule between SPY and QQQ based on prior completed data; future preregistration may freeze SPY-only if required.",
            "Hold BIL outside the window.",
            "No leverage and no shorting.",
        ],
        "benchmark_plan": [
            "SPY",
            "QQQ",
            "SPY_200d",
            "active VM",
            "active combo",
            "BIL",
            "calendar no-signal baseline if project supports it",
        ],
        "valid_future_outcomes": NORMAL_OUTCOMES,
    },
    {
        "candidate_id": "cash_pause_overlay_meta_v1",
        "lane_id": "diversifier_contribution_lane",
        "status": "shared_risk_overlay",
        "family": "cash_pause_overlay_meta",
        "timeframe": "overlay_meta_rule",
        "purpose": "Evaluate whether a shared pause/kill-switch overlay can improve portfolio risk behavior. This is not standalone alpha and cannot become a normal strategy candidate by itself.",
        "allowed_instruments": [],
        "allowed_application": [
            "Apply only as a diagnostic overlay to already-defined research candidates or active benchmark references according to existing project conventions.",
            "Do not alter accepted active strategy state.",
            "Do not activate paper-forward.",
        ],
        "frozen_rule": [
            "Pause new entries after abnormal drawdown, weekly loss breach, stale data, broker/reconciliation issue, or strategy-specific kill switch condition.",
            "Existing positions follow frozen exit policy.",
            "This overlay cannot be used to rescue rejected strategies unless a separate pre-registration says so.",
        ],
        "benchmark_plan": [
            "base strategy without overlay",
            "base strategy with overlay",
            "active combo without overlay",
            "active combo with overlay if project convention permits diagnostic comparison",
            "portfolio contribution report",
        ],
        "valid_future_outcomes": OVERLAY_OUTCOMES,
        "standalone_demo_eligible": False,
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
    supports_window = approved and cache_present and required_present and adjusted_close_available and null_count == 0 and duplicate_dates == 0 and stale_flag is not True
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
    elif null_count:
        issue = "nulls_in_required_columns"
    elif duplicate_dates:
        issue = "duplicate_dates"
    elif stale_flag is True:
        issue = "stale_cache"
    elif stale_flag == "unknown":
        issue = "unknown_stale_status"
    return {
        "symbol": symbol,
        "approved_symbol_status": status,
        "cache_path": str(cache_path.relative_to(root)) if cache_path.exists() else "",
        "first_available_date": first_date,
        "last_available_date": last_date,
        "row_count": len(rows),
        "required_ohlcv_columns": ";".join(REQUIRED_COLUMNS),
        "required_columns_present": required_present,
        "adjusted_close_available": adjusted_close_available,
        "null_count": null_count,
        "duplicate_date_count": duplicate_dates,
        "stale_data_flag": stale_flag,
        "supports_proposed_discovery_window": supports_window,
        "issue": issue,
    }


def audit_data(root: Path) -> list[dict[str, Any]]:
    return [audit_symbol(root, symbol) for symbol in REQUIRED_SYMBOLS]


def data_status(symbol_rows: list[dict[str, Any]]) -> str:
    if any(row["issue"] in {"not_approved", "missing_cache", "missing_required_columns"} for row in symbol_rows):
        return "missing_required_data"
    if any(row["issue"] for row in symbol_rows):
        return "unknown_requires_manual_review"
    return "sufficient_for_second_expansion_discovery"


def next_action_for_status(status: str) -> str:
    if status == "sufficient_for_second_expansion_discovery":
        return NEXT_ACTION_DISCOVERY
    if status == "missing_required_data":
        return NEXT_ACTION_DATA
    return NEXT_ACTION_MANUAL


def candidate_data_status(candidate: dict[str, Any], symbol_rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_symbol = {row["symbol"]: row for row in symbol_rows}
    symbols = candidate.get("allowed_instruments", [])
    issues = [f"{symbol}:{by_symbol[symbol]['issue']}" for symbol in symbols if symbol in by_symbol and by_symbol[symbol]["issue"]]
    missing_rows = [symbol for symbol in symbols if symbol not in by_symbol]
    if missing_rows:
        issues.extend(f"{symbol}:not_audited" for symbol in missing_rows)
    if candidate["candidate_id"] == "cash_pause_overlay_meta_v1":
        status = "diagnostic_overlay_no_symbol_data_required"
    elif issues:
        status = "data_blocked_or_manual_review_required"
    elif any(symbol in candidate.get("limited_history_symbols", []) for symbol in symbols):
        status = "available_limited_history_same_window_required"
    else:
        status = "available_for_preregistered_discovery"
    return {
        "candidate_id": candidate["candidate_id"],
        "lane_id": candidate["lane_id"],
        "candidate_data_status": status,
        "data_issues": ";".join(issues),
        "symbols_audited": ";".join(symbols),
    }


def lane_assignment_rows() -> list[dict[str, Any]]:
    return [
        {
            "candidate_id": candidate["candidate_id"],
            "lane_id": candidate["lane_id"],
            "status": candidate["status"],
            "family": candidate["family"],
            "timeframe": candidate["timeframe"],
            "valid_future_outcomes": ";".join(candidate["valid_future_outcomes"]),
        }
        for candidate in CANDIDATES
    ]


def batch_yaml(data_status_value: str, next_action: str, candidate_status_rows: list[dict[str, Any]]) -> dict[str, Any]:
    status_lookup = {row["candidate_id"]: row for row in candidate_status_rows}
    return {
        "metadata": {
            "batch_id": "second_expansion_with_lane_framework",
            "pre_registration_only": True,
            "lane_framework_used": True,
            "candidate_count": len(CANDIDATES),
            "data_availability_status": data_status_value,
            "valid_next_action": next_action,
            "forbidden_future_outcomes": FORBIDDEN_OUTCOMES,
            "excluded_candidates": EXCLUDED_CANDIDATES,
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
    lines = ["# Second Expansion Candidate Specs", ""]
    for candidate in CANDIDATES:
        lines.extend(
            [
                f"## {candidate['candidate_id']}",
                "",
                f"- Lane: `{candidate['lane_id']}`",
                f"- Status: `{candidate['status']}`",
                f"- Family: `{candidate['family']}`",
                f"- Timeframe: `{candidate['timeframe']}`",
                f"- Purpose: {candidate['purpose']}",
                f"- Allowed instruments: `{';'.join(candidate.get('allowed_instruments', [])) or 'not_applicable_overlay'}`",
                f"- Data status: `{status_lookup[candidate['candidate_id']]['candidate_data_status']}`",
                f"- Valid future outcomes: `{';'.join(candidate['valid_future_outcomes'])}`",
                "",
                "Frozen v1 rule:",
                "",
            ]
        )
        lines.extend(f"- {rule}" for rule in candidate["frozen_rule"])
        if candidate.get("allowed_application"):
            lines.extend(["", "Allowed application:", ""])
            lines.extend(f"- {item}" for item in candidate["allowed_application"])
        lines.append("")
    return "\n".join(lines)


def data_report_md(symbol_rows: list[dict[str, Any]], status: str) -> str:
    lines = [
        "# Second Expansion Data Availability Report",
        "",
        f"Data availability status: `{status}`",
        "",
        "No provider download was run. This report reads approved-symbol metadata and local cached CSV files only.",
        "",
        "| Symbol | Approved status | Cache path | First date | Last date | Rows | Columns present | Adj close | Nulls | Duplicate dates | Stale flag | Supports window | Issue |",
        "|---|---|---|---|---|---:|---|---|---:|---:|---|---|---|",
    ]
    for row in symbol_rows:
        lines.append(
            f"| {row['symbol']} | {row['approved_symbol_status']} | {row['cache_path']} | {row['first_available_date']} | {row['last_available_date']} | {row['row_count']} | {row['required_columns_present']} | {row['adjusted_close_available']} | {row['null_count']} | {row['duplicate_date_count']} | {row['stale_data_flag']} | {row['supports_proposed_discovery_window']} | {row['issue']} |"
        )
    return "\n".join(lines) + "\n"


def missing_data_report_md(symbol_rows: list[dict[str, Any]]) -> str:
    missing = [row for row in symbol_rows if row["issue"]]
    lines = ["# Second Expansion Missing Data Report", ""]
    if not missing:
        lines.append("No missing or uncertain required data was found by the local cache audit. Managed-futures ETF proxies remain limited-history and require same-window treatment.")
    else:
        lines.append("| Symbol | Issue | Required action |")
        lines.append("|---|---|---|")
        for row in missing:
            action = "authorize cache refresh or manual review before discovery" if row["issue"] in {"missing_cache", "not_approved", "missing_required_columns"} else "manual data review before discovery"
            lines.append(f"| {row['symbol']} | {row['issue']} | {action} |")
    return "\n".join(lines) + "\n"


def benchmark_plan_md() -> str:
    by_lane: dict[str, list[str]] = {}
    for candidate in CANDIDATES:
        by_lane.setdefault(candidate["lane_id"], [])
        for benchmark in candidate["benchmark_plan"]:
            if benchmark not in by_lane[candidate["lane_id"]]:
                by_lane[candidate["lane_id"]].append(benchmark)
    lines = ["# Second Expansion Benchmark Plan", ""]
    for lane_id, benchmarks in by_lane.items():
        lines.extend([f"## {lane_id}", ""])
        lines.extend(f"- {benchmark}" for benchmark in benchmarks)
        if lane_id == "macro_gld_duration_risk_off_lane":
            lines.append("- Same-window benchmark recomputation is required; no full-history benchmark values against shorter macro samples.")
        if lane_id == "diversifier_contribution_lane":
            lines.append("- Portfolio/base strategy with and without overlay must be compared over the same window.")
        lines.append("")
    return "\n".join(lines)


def risk_policy_md() -> str:
    return """# Second Expansion Risk Policy

- Use the lane-specific gate framework.
- No candidate may move directly to candidate_exhaustive, paper-forward, demo_active, live_ready, broker integration, or real-money use.
- Macro candidates require same-window comparisons and crisis/diversification diagnostics.
- Moderate tactical candidates must survive slippage/spread, drawdown, risk-buffer, and trade-frequency gates.
- The overlay candidate is not standalone alpha and is not standalone paper/demo eligible.
- No direct futures, options, margin, leverage, shorting, intraday confirmation, provider download, or broker/live path is authorized.
"""


def acceptance_gates_md() -> str:
    return """# Second Expansion Acceptance Gates

## Macro / GLD / Duration / Risk-Off Lane

- Valid outcomes: `discovery_reject` or `promotion_review_candidate_macro`.
- Same-window active VM, active DSR, active combo, SPY_200d, and relevant asset benchmarks are required.
- Managed-futures-style exposure must be ETF/fund-wrapper only.
- Crisis/risk-off or diversification benefit must be visible in future evidence.

## Moderate Tactical ETF Lane

- Valid outcomes: `discovery_reject` or `promotion_review_candidate`.
- Must survive strict slippage/spread, drawdown, risk-buffer, turnover, and trade-count gates.
- Must not duplicate SPY/QQQ/active combo without useful edge.

## Diversifier Contribution Lane

- Valid outcomes: `diagnostic_reject` or `risk_overlay_watchlist_candidate`.
- Must be judged by marginal contribution to a base strategy or portfolio, not standalone return.
"""


def rejection_gates_md() -> str:
    return """# Second Expansion Rejection Gates

## Macro Candidates

- Reject if same-window benchmarks cannot be computed.
- Reject if GLD buy-and-hold explains the result.
- Reject if data comparability is incomplete.
- Reject if the row is simply an equity wrapper with GLD decoration.
- Reject if drawdown, risk-buffer, or slippage gates fail.
- Reject if there is no crisis or diversification benefit.

## Moderate Tactical Candidates

- Reject if slippage erases edge.
- Reject if drawdown or risk buffer fails.
- Reject if trade count is too thin for confidence or too high for ETF execution.
- Reject if the row duplicates SPY, QQQ, or active combo without useful edge.

## Overlay Candidate

- Reject if it simply dilutes exposure.
- Reject if it improves drawdown only by destroying target probability.
- Reject if portfolio contribution is weak.
- Reject if it attempts to rescue rejected strategies without new pre-registration.
"""


def do_not_run_md() -> str:
    return """# Do Not Run Now

This packet is pre-registration and data-availability audit only.

Do not run discovery, backtests, performance metrics, candidate_exhaustive, paper-forward review, paper-forward activation, provider download, broker/live-order code, or real-money recommendations from this task.
"""


def update_metadata(root: Path, output: Path, created_utc: str, data_status_value: str, next_action: str) -> tuple[bool, bool]:
    registry_updated = False
    registry_path = root / REGISTRY_PATH
    if registry_path.exists():
        registry = load_yaml(registry_path)
        metadata = registry.setdefault("registry", {})
        metadata.update(
            {
                "second_expansion_lane_framework_preregistration_path": str(output),
                "second_expansion_lane_framework_preregistration_status": "pre_registered",
                "second_expansion_candidate_count": len(CANDIDATES),
                "second_expansion_data_availability_status": data_status_value,
                "second_expansion_next_action": next_action,
                "current_next_action": next_action,
                "next_action": next_action,
                "pre_registration_only": True,
                "data_availability_audit_only": True,
                "lane_framework_used": True,
                "backtests_run": False,
                "discovery_run": False,
                "performance_metrics_computed": False,
                "provider_download": False,
                "candidate_exhaustive_run": False,
                "paper_forward_active": False,
                "real_money_recommendation": False,
                "updated_utc": created_utc,
            }
        )
        registry_path.write_text(yaml.safe_dump(registry, sort_keys=False, width=120, allow_unicode=False), encoding="utf-8")
        registry_updated = True

    roadmap_updated = False
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
    marker = "## Second Expansion With Lane Framework Pre-Registration"
    section = f"""## Second Expansion With Lane Framework Pre-Registration

- Created UTC: `{created_utc}`
- Evidence path: `{output}`
- Candidate count: `{len(CANDIDATES)}`
- Lanes used: `macro_gld_duration_risk_off_lane, moderate_tactical_etf_lane, diversifier_contribution_lane`
- Data availability status: `{data_status_value}`
- Next action: `{next_action}`
- No backtest, discovery, performance metric, candidate_exhaustive, paper-forward action, provider download, broker/live-order path, accepted/rejected strategy state change, old GLD/GROR state resumption, sector RS discovery, intraday/event candidate, or real-money recommendation is authorized by this pre-registration.
"""
    updated = base.split(marker, 1)[0].rstrip() + "\n\n" + section if marker in base else base.rstrip() + "\n\n" + section
    roadmap_path.parent.mkdir(parents=True, exist_ok=True)
    roadmap_path.write_text(updated.rstrip() + "\n", encoding="utf-8")
    roadmap_updated = True
    return registry_updated, roadmap_updated


def consistency_check(
    manifest: dict[str, Any],
    output: Path,
    strategies_before: list[dict[str, Any]],
    strategies_after: list[dict[str, Any]],
) -> dict[str, Any]:
    candidate_ids = [candidate["candidate_id"] for candidate in CANDIDATES]
    included_excluded = sorted(set(candidate_ids) & set(EXCLUDED_CANDIDATES))
    all_outcomes = {outcome for candidate in CANDIDATES for outcome in candidate["valid_future_outcomes"]}
    required_files = [
        "second_expansion_lane_framework_manifest.json",
        "second_expansion_batch.yaml",
        "second_expansion_candidate_specs.md",
        "second_expansion_lane_assignment.csv",
        "second_expansion_data_availability_report.md",
        "second_expansion_missing_data_report.md",
        "second_expansion_benchmark_plan.md",
        "second_expansion_risk_policy.md",
        "second_expansion_acceptance_gates.md",
        "second_expansion_rejection_gates.md",
        "second_expansion_do_not_run_now.md",
        "second_expansion_next_action.md",
    ]
    sector_rs_next = output.parents[2] / "sector_rs_limited_history" / "latest" / "sector_rs_limited_history_next_action.md"
    if not sector_rs_next.exists():
        sector_rs_next = ROOT / SECTOR_RS_PREREG_DIR / "sector_rs_limited_history_next_action.md"
    sector_rs_text = sector_rs_next.read_text(encoding="utf-8") if sector_rs_next.exists() else ""
    check = {
        "exactly_five_candidates_included": len(CANDIDATES) == 5,
        "every_candidate_has_exactly_one_lane": all(candidate.get("lane_id") in LANE_IDS and isinstance(candidate.get("lane_id"), str) for candidate in CANDIDATES),
        "lane_framework_used": manifest["lane_framework_used"],
        "no_first_expansion_rejected_row_reopened": not included_excluded,
        "included_excluded_candidates": included_excluded,
        "sector_rs_discovery_not_run": not manifest["sector_rs_discovery_run"],
        "sector_rs_remains_separately_queued": "run_sector_rs_limited_history_discovery_batch" in sector_rs_text or "sector_rs_weekly_cash_filter_v1" not in candidate_ids,
        "old_gld_gror_candidate_exhaustive_not_resumed": not manifest["old_gld_gror_state_resumed"] and "gror_balanced_momentum_60_40_v1" not in candidate_ids,
        "no_intraday_candidate_included": not manifest["intraday_candidates_included"],
        "no_event_data_candidate_included": not manifest["event_data_candidates_included"],
        "no_provider_download": not manifest["provider_download"],
        "no_strategy_results_computed": not manifest["performance_metrics_computed"] and not manifest["backtests_run"] and not manifest["discovery_run"],
        "no_accepted_rejected_strategy_state_changes": strategies_before == strategies_after and not manifest["accepted_strategy_state_changed"] and not manifest["rejected_strategy_state_changed"],
        "no_broker_live_path": not manifest["broker_path_touched"] and not manifest["live_orders"],
        "no_paper_forward_action": not manifest["paper_forward_review"] and not manifest["paper_forward_activation"],
        "valid_future_outcomes_lane_specific_safe": not bool(all_outcomes & set(FORBIDDEN_OUTCOMES)),
        "required_files_created": all((output / name).exists() for name in required_files),
        "manifest_flags_match_scope": all(manifest[key] == value for key, value in MANIFEST_FLAGS.items()),
        "next_action_valid": manifest["next_action"] in VALID_NEXT_ACTIONS,
    }
    check["consistency_passed"] = all(bool(value) for value in check.values() if not isinstance(value, list))
    return check


def run_second_expansion_with_lane_framework_preregistration(root: Path = ROOT) -> dict[str, Any]:
    output = clean_output(root)
    created_utc = now_utc()
    strategies_before = strategy_state_snapshot(root)
    symbol_rows = audit_data(root)
    availability_status = data_status(symbol_rows)
    next_action = next_action_for_status(availability_status)
    candidate_status_rows = [candidate_data_status(candidate, symbol_rows) for candidate in CANDIDATES]
    registry_updated, roadmap_updated = update_metadata(root, output, created_utc, availability_status, next_action)
    strategies_after = strategy_state_snapshot(root)
    manifest = {
        "artifact": "second_expansion_with_lane_framework_preregistration",
        "created_utc": created_utc,
        "output_dir": str(output),
        "lane_framework_path": str(root / LANE_FRAMEWORK_DIR),
        "included_candidate_ids": [candidate["candidate_id"] for candidate in CANDIDATES],
        "excluded_candidate_ids": EXCLUDED_CANDIDATES,
        "required_symbols": REQUIRED_SYMBOLS,
        "data_availability_status": availability_status,
        "next_action": next_action,
        "registry_metadata_updated": registry_updated,
        "roadmap_updated": roadmap_updated,
        **MANIFEST_FLAGS,
    }

    write_json(output / "second_expansion_lane_framework_manifest.json", manifest)
    (output / "second_expansion_batch.yaml").write_text(yaml.safe_dump(batch_yaml(availability_status, next_action, candidate_status_rows), sort_keys=False, width=120, allow_unicode=False), encoding="utf-8")
    (output / "second_expansion_candidate_specs.md").write_text(candidate_specs_md(candidate_status_rows), encoding="utf-8")
    write_csv(output / "second_expansion_lane_assignment.csv", lane_assignment_rows(), ["candidate_id", "lane_id", "status", "family", "timeframe", "valid_future_outcomes"])
    write_csv(output / "second_expansion_symbol_data_availability.csv", symbol_rows, ["symbol", "approved_symbol_status", "cache_path", "first_available_date", "last_available_date", "row_count", "required_ohlcv_columns", "required_columns_present", "adjusted_close_available", "null_count", "duplicate_date_count", "stale_data_flag", "supports_proposed_discovery_window", "issue"])
    write_csv(output / "second_expansion_candidate_data_status.csv", candidate_status_rows, ["candidate_id", "lane_id", "candidate_data_status", "data_issues", "symbols_audited"])
    (output / "second_expansion_data_availability_report.md").write_text(data_report_md(symbol_rows, availability_status), encoding="utf-8")
    (output / "second_expansion_missing_data_report.md").write_text(missing_data_report_md(symbol_rows), encoding="utf-8")
    (output / "second_expansion_benchmark_plan.md").write_text(benchmark_plan_md(), encoding="utf-8")
    (output / "second_expansion_risk_policy.md").write_text(risk_policy_md(), encoding="utf-8")
    (output / "second_expansion_acceptance_gates.md").write_text(acceptance_gates_md(), encoding="utf-8")
    (output / "second_expansion_rejection_gates.md").write_text(rejection_gates_md(), encoding="utf-8")
    (output / "second_expansion_do_not_run_now.md").write_text(do_not_run_md(), encoding="utf-8")
    (output / "second_expansion_next_action.md").write_text(f"# Second Expansion Next Action\n\n`{next_action}`\n\nDo not run this next action from the pre-registration task.\n", encoding="utf-8")
    consistency = consistency_check(manifest, output, strategies_before, strategies_after)
    write_json(output / "second_expansion_consistency_check.json", consistency)
    return {
        "output_dir": str(output),
        "candidate_count": len(CANDIDATES),
        "candidate_ids": [candidate["candidate_id"] for candidate in CANDIDATES],
        "data_availability_status": availability_status,
        "next_action": next_action,
        "consistency": consistency,
    }


def main() -> None:
    print(json.dumps(run_second_expansion_with_lane_framework_preregistration(ROOT), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
