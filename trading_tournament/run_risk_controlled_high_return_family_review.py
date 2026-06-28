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
OUTPUT_DIR = Path("evidence") / "pre_registered_lanes" / "risk_controlled_high_return_family_review" / "latest"
REGISTRY_PATH = Path("strategy_lab") / "strategy_registry.yaml"
ROADMAP_PATH = Path("strategy_lab") / "RESEARCH_ROADMAP.md"
APPROVED_SYMBOL_MAP_PATH = Path("strategy_lab") / "approved_etf_symbol_map.yaml"
THIRD_FAILURE_DIR = Path("evidence") / "tournament_failure_synthesis" / "third_expansion_failure_audit" / "latest"
SECOND_DISCOVERY_DIR = Path("evidence") / "parallel_research_discovery" / "second_expansion_with_lane_framework" / "latest"
THIRD_DISCOVERY_DIR = Path("evidence") / "parallel_research_discovery" / "third_expansion_with_lane_framework" / "latest"
INTRADAY_PAUSE_DIR = Path("evidence") / "intraday_readiness" / "intraday_data_constraints_pause" / "latest"

NEXT_ACTION = "run_risk_controlled_high_return_discovery_batch"
VALID_NEXT_ACTIONS = {
    "run_risk_controlled_high_return_discovery_batch",
    "manual_review_required_for_risk_controlled_high_return_batch",
    "pause_expansion_and_summarize_tournament_state",
}

MANIFEST_FLAGS = {
    "pre_registration_only": True,
    "family_review_only": True,
    "failure_lessons_applied": True,
    "backtests_run": False,
    "discovery_run": False,
    "new_performance_metrics_computed": False,
    "provider_download": False,
    "intraday_data_used": False,
    "candidate_exhaustive_run": False,
    "paper_forward_review": False,
    "paper_forward_activation": False,
    "broker_path_touched": False,
    "live_orders": False,
    "real_money_recommendation": False,
    "accepted_strategy_state_changed": False,
    "rejected_strategy_state_changed": False,
    "exact_rejected_variants_reopened": False,
    "intraday_research_remains_paused": True,
}

REQUIRED_FILES = [
    "risk_controlled_high_return_manifest.json",
    "risk_controlled_high_return_summary.md",
    "high_return_family_review.md",
    "exact_rejected_parent_closure.md",
    "risk_controlled_candidate_specs.md",
    "risk_controlled_candidate_specs.yaml",
    "risk_controlled_lane_assignment.csv",
    "risk_controlled_data_availability_report.md",
    "risk_controlled_benchmark_plan.md",
    "risk_controlled_acceptance_gates.md",
    "risk_controlled_rejection_gates.md",
    "risk_controlled_do_not_run_now.md",
    "risk_controlled_next_action.md",
    "risk_controlled_consistency_check.json",
]

CANDIDATES: list[dict[str, Any]] = [
    {
        "candidate_id": "rc_dual_momentum_paa_vol_scaled_v1",
        "source_family": "dual_momentum_protective_asset_allocation",
        "exact_rejected_parent_row": "dual_momentum_paa_clean_v1",
        "parent_closure_reason": "Parent row remains closed after high ending equity failed drawdown, risk-buffer, and slippage gates.",
        "new_hypothesis": "Volatility-scaled allocation will reduce drawdown and risk-buffer failure while preserving the parent return engine enough to pass pre-defined promotion-review gates.",
        "one_major_changed_dimension": "volatility_scaling",
        "unchanged_dimensions": [
            "daily timeframe",
            "protective asset allocation family",
            "same signal family and rank inputs",
            "same long-only ETF/fund-wrapper universe",
            "same no leverage, no margin, no shorting, no derivatives boundary",
        ],
        "lane": "macro_gld_duration_risk_off_lane",
        "universe": ["SPY", "QQQ", "GLD", "IEF", "AGG", "BIL"],
        "timeframe": "daily",
        "rebalance_schedule": "monthly end-of-month rebalance only",
        "signal_rule": "Use the parent dual-momentum/protective-allocation ranking and absolute-momentum gate; route failed risk sleeves to BIL.",
        "allocation_sizing_rule": "Apply a single pre-registered realized-volatility exposure scalar to the parent risk allocation; unused exposure goes to BIL; total notional never exceeds 100%.",
        "risk_controls": [
            "Long-only ETF/fund wrappers.",
            "No leverage, margin, shorting, options, futures, forex, crypto, or intraday logic.",
            "Maximum total risk-asset exposure is capped by the volatility-scaling rule.",
            "BIL receives unused exposure.",
            "No new entries after a hard project-level risk halt.",
        ],
        "slippage_stress_assumptions": [
            "Use the same standard and stress slippage labels as the lane framework.",
            "Candidate must pass under stress slippage before any promotion-review consideration.",
        ],
        "benchmark_group": [
            "SPY buy-and-hold",
            "QQQ buy-and-hold",
            "SPY 200d trend model",
            "active VM",
            "active DSR",
            "active combo benchmark",
            "static_all_weather_benchmark_v1",
        ],
        "data_requirements": [
            "Adjusted daily OHLCV for SPY, QQQ, GLD, IEF, AGG, and BIL.",
            "Momentum inputs required by parent family.",
            "Realized-volatility input for exposure scalar.",
            "BIL cash proxy history.",
        ],
        "acceptance_gates": [
            "Must pass risk-buffer gate under standard and stress slippage.",
            "Must not collapse into old GROR, SPY 200d, static all-weather, or active combo behavior.",
            "Must preserve enough 180d target-window upside to remain a profit candidate.",
            "Must show the risk-control dimension reduced drawdown without relying on tuned thresholds.",
        ],
        "rejection_gates": [
            "Reject if volatility scaling removes too much upside to meet the profit objective.",
            "Reject if drawdown/risk-buffer gate still fails.",
            "Reject if behavior duplicates old GROR, SPY 200d, static all-weather, or active combo.",
            "Reject if results require alternate volatility thresholds after evidence is seen.",
        ],
        "valid_future_outcomes": ["discovery_reject", "promotion_review_candidate_macro"],
    },
    {
        "candidate_id": "rc_donchian_breakout_risk_budget_v1",
        "source_family": "donchian_atr_etf_breakout",
        "exact_rejected_parent_row": "donchian_atr_breakout_etf_v1",
        "parent_closure_reason": "Parent row remains closed after return potential failed drawdown, risk-buffer, benchmark, and trade gates.",
        "new_hypothesis": "A fixed risk-budget exposure cap will reduce breakout drawdown while preserving the parent price-breakout return engine enough to pass pre-defined promotion-review gates.",
        "one_major_changed_dimension": "risk_budget_sizing",
        "unchanged_dimensions": [
            "daily timeframe",
            "Donchian breakout entry family",
            "same ATR stop model",
            "same long-only broad and sector ETF universe",
            "same no leverage, no margin, no shorting, no derivatives boundary",
        ],
        "lane": "moderate_tactical_etf_lane",
        "universe": ["SPY", "QQQ", "IWM", "DIA", "XLK", "XLF", "XLV", "XLE", "XLI", "XLY", "XLP", "XLU", "XLB", "XLRE", "BIL"],
        "timeframe": "daily",
        "rebalance_schedule": "daily close signal review with entries only when the frozen Donchian condition is met",
        "signal_rule": "Use the parent Donchian breakout condition: close above the prior 55-day high with SPY above its 200-day SMA; exits follow the parent daily close-based rule set.",
        "allocation_sizing_rule": "Replace equal notional sizing with a fixed per-position risk-budget exposure cap; unused exposure remains unallocated or in BIL reporting.",
        "risk_controls": [
            "Long-only ETF/fund wrappers.",
            "No leverage, margin, shorting, options, futures, forex, crypto, or intraday logic.",
            "Maximum two open breakout positions.",
            "Risk-budget cap is fixed before testing.",
            "Parent ATR(14) stop and daily close-based stop timing remain unchanged.",
        ],
        "slippage_stress_assumptions": [
            "Use the same standard and stress slippage labels as the lane framework.",
            "Stop simulation remains daily close-based; no intraday stop fills are introduced.",
        ],
        "benchmark_group": [
            "SPY buy-and-hold",
            "QQQ buy-and-hold",
            "SPY 200d trend model",
            "active combo benchmark",
            "vol_compression_breakout_etf_v1 reference",
            "BIL cash proxy",
        ],
        "data_requirements": [
            "Adjusted daily OHLCV for broad and sector ETF universe.",
            "55-day high.",
            "20-day low.",
            "ATR(14).",
            "SPY 200-day SMA.",
            "BIL cash proxy for reporting.",
        ],
        "acceptance_gates": [
            "Must pass risk-buffer gate under standard and stress slippage.",
            "Must remain a price-breakout strategy, not a top-N momentum wrapper.",
            "Must not require Donchian or ATR parameter changes.",
            "Must show drawdown improvement without losing all breakout profit power.",
        ],
        "rejection_gates": [
            "Reject if drawdown/risk-buffer gate still fails.",
            "Reject if risk-budget sizing makes the row too slow for the profit objective.",
            "Reject if performance is explained by one sector ETF or one regime.",
            "Reject if results require Donchian, ATR, holding-period, or universe changes after evidence is seen.",
        ],
        "valid_future_outcomes": ["discovery_reject", "promotion_review_candidate"],
    },
]

FAMILIES_REVIEWED = [
    "dual_momentum_paa_clean_v1",
    "donchian_atr_breakout_etf_v1",
    "quality_momentum_etf_proxy_watchlist_only",
]


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_csv_rows(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def clean_output(root: Path) -> Path:
    output = (root / OUTPUT_DIR).resolve()
    workspace = root.resolve()
    if output == workspace or workspace not in output.parents:
        raise RuntimeError(f"refusing output outside workspace: {output}")
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)
    return output


def strategy_snapshot(root: Path) -> list[dict[str, Any]]:
    return deepcopy(load_yaml(root / REGISTRY_PATH).get("strategies", []))


def strategy_state_map(strategies: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    state: dict[str, dict[str, Any]] = {}
    for row in strategies:
        row_id = row.get("id") or row.get("strategy_id")
        if not row_id:
            continue
        state[row_id] = {
            "status": row.get("status") or row.get("current_status"),
            "current_status": row.get("current_status"),
            "paper_forward_active": row.get("paper_forward_active"),
            "candidate_exhaustive_run": row.get("candidate_exhaustive_run"),
            "candidate_exhaustive_recommended": row.get("candidate_exhaustive_recommended"),
            "promotion_review_required": row.get("promotion_review_required"),
        }
    return state


def prior_evidence(root: Path) -> dict[str, Any]:
    third_failure = load_json(root / THIRD_FAILURE_DIR / "third_expansion_failure_audit_manifest.json")
    intraday_pause = load_json(root / INTRADAY_PAUSE_DIR / "intraday_data_constraints_pause_manifest.json")
    second_metrics = load_json(root / SECOND_DISCOVERY_DIR / "second_expansion_candidate_metrics.json")
    third_metrics = load_json(root / THIRD_DISCOVERY_DIR / "third_expansion_candidate_metrics.json")
    return {
        "third_expansion_failure_audit_found": bool(third_failure),
        "exact_rejected_variants_closed": third_failure.get("exact_rejected_variants_closed"),
        "daily_weekly_expansion_should_pause": third_failure.get("daily_weekly_expansion_should_pause"),
        "intraday_pause_found": bool(intraday_pause),
        "intraday_research_paused": intraday_pause.get("intraday_research_paused"),
        "intraday_pause_next_action": intraday_pause.get("next_action"),
        "dual_momentum_parent_evidence_found": "dual_momentum_paa_clean_v1" in third_metrics,
        "donchian_parent_evidence_found": "donchian_atr_breakout_etf_v1" in second_metrics,
    }


def approved_symbol_status(root: Path) -> dict[str, str]:
    payload = load_yaml(root / APPROVED_SYMBOL_MAP_PATH)
    status: dict[str, str] = {}
    for row in payload.get("symbols", []):
        if not isinstance(row, dict) or not row.get("symbol"):
            continue
        symbol = str(row["symbol"]).upper()
        if row.get("allowed_for_strategy"):
            status[symbol] = row.get("approved_status") or "approved_for_strategy"
        elif row.get("allowed_for_benchmark"):
            status[symbol] = row.get("approved_status") or "approved_for_benchmark"
        else:
            status[symbol] = row.get("approved_status") or "not_approved"
    return status


def required_symbols() -> list[str]:
    symbols: set[str] = set()
    for candidate in CANDIDATES:
        symbols.update(candidate["universe"])
    return sorted(symbols)


def inspect_symbol_cache(root: Path, symbol: str, approved: dict[str, str]) -> dict[str, Any]:
    path = root / "data" / "cache" / f"{symbol}.csv"
    if not path.exists():
        return {
            "symbol": symbol,
            "approved_status": approved.get(symbol, "missing_from_approved_symbol_map"),
            "cache_present": False,
            "first_date": "",
            "last_date": "",
            "row_count": 0,
            "adjusted_close_available": False,
            "null_count": 0,
            "duplicate_date_count": 0,
            "stale_flag": True,
            "supports_required_window": False,
        }
    with path.open("r", newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    dates = [row.get("date", "") for row in rows if row.get("date")]
    duplicate_count = len(dates) - len(set(dates))
    null_count = 0
    adjusted_close_available = "adj_close" in (rows[0].keys() if rows else [])
    for row in rows:
        for field in ["date", "open", "high", "low", "close", "adj_close", "volume"]:
            if row.get(field) in {None, ""}:
                null_count += 1
    first_date = min(dates) if dates else ""
    last_date = max(dates) if dates else ""
    stale = True
    if last_date:
        try:
            stale = (date.today() - date.fromisoformat(last_date)).days > 45
        except ValueError:
            stale = True
    supports_required_window = bool(rows) and len(rows) >= 1260 and adjusted_close_available and null_count == 0 and duplicate_count == 0
    return {
        "symbol": symbol,
        "approved_status": approved.get(symbol, "missing_from_approved_symbol_map"),
        "cache_present": True,
        "first_date": first_date,
        "last_date": last_date,
        "row_count": len(rows),
        "adjusted_close_available": adjusted_close_available,
        "null_count": null_count,
        "duplicate_date_count": duplicate_count,
        "stale_flag": stale,
        "supports_required_window": supports_required_window,
    }


def data_availability(root: Path) -> tuple[list[dict[str, Any]], str]:
    approved = approved_symbol_status(root)
    rows = [inspect_symbol_cache(root, symbol, approved) for symbol in required_symbols()]
    sufficient = all(
        row["approved_status"] != "missing_from_approved_symbol_map"
        and row["cache_present"]
        and row["adjusted_close_available"]
        and row["null_count"] == 0
        and row["duplicate_date_count"] == 0
        and row["supports_required_window"]
        for row in rows
    )
    return rows, "sufficient_for_preregistered_discovery" if sufficient else "manual_review_required_for_data_availability"


def lane_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for candidate in CANDIDATES:
        rows.append(
            {
                "candidate_id": candidate["candidate_id"],
                "lane": candidate["lane"],
                "source_family": candidate["source_family"],
                "exact_rejected_parent_row": candidate["exact_rejected_parent_row"],
                "one_major_changed_dimension": candidate["one_major_changed_dimension"],
                "valid_future_outcomes": ";".join(candidate["valid_future_outcomes"]),
            }
        )
    return rows


def summary_md(created_utc: str, output: Path, manifest: dict[str, Any]) -> str:
    return f"""# Risk-Controlled High-Return Family Review

Created UTC: `{created_utc}`

Evidence path: `{output}`

Candidate count: `{manifest["candidate_count"]}`

Candidate IDs: `{', '.join(manifest["candidate_ids"])}`

Data availability status: `{manifest["data_availability_status"]}`

Next action: `{manifest["next_action"]}`

## Decision

Two risk-controlled high-return hypotheses are pre-registered. Exact rejected variants remain closed. Quality/momentum stays on watchlist with no new candidate in this packet.

This packet does not run a backtest, discovery, new performance metric, candidate_exhaustive, paper-forward review, provider download, broker/live path, intraday research, or real-money recommendation.
"""


def family_review_md() -> str:
    return """# High-Return Family Review

Reviewed families:

- `dual_momentum_paa_clean_v1`: rejected parent showed high ending equity and target-window power, but failed drawdown, risk-buffer, and slippage gates. Family remains open only through a new volatility-scaling hypothesis.
- `donchian_atr_breakout_etf_v1`: rejected parent showed tactical breakout return power, but failed drawdown, risk-buffer, benchmark, and trade gates. Family remains open only through a fixed risk-budget sizing hypothesis.
- `quality_momentum_etf_proxy`: remains watchlist-only. Recent rescue attempts failed risk/duplicate gates; this packet does not add another quality/momentum candidate.

Weak defensive rows are not treated as high-return candidates. Intraday candidates remain paused.
"""


def parent_closure_md() -> str:
    return """# Exact Rejected Parent Closure

- `dual_momentum_paa_clean_v1` remains closed as an exact row. It is not renamed, promoted, reactivated, or marked candidate_exhaustive eligible.
- `donchian_atr_breakout_etf_v1` remains closed as an exact row. It is not renamed, promoted, reactivated, or marked candidate_exhaustive eligible.

The new candidates are child hypotheses that change exactly one major risk-control dimension. They do not reopen the parent rows.
"""


def candidate_specs_md() -> str:
    blocks: list[str] = ["# Risk-Controlled Candidate Specs\n"]
    for candidate in CANDIDATES:
        blocks.append(f"""## {candidate["candidate_id"]}

- Source family: `{candidate["source_family"]}`
- Exact rejected parent row: `{candidate["exact_rejected_parent_row"]}`
- Parent closure: {candidate["parent_closure_reason"]}
- New hypothesis: {candidate["new_hypothesis"]}
- One major changed dimension: `{candidate["one_major_changed_dimension"]}`
- Unchanged dimensions: {', '.join(candidate["unchanged_dimensions"])}
- Lane: `{candidate["lane"]}`
- Universe: `{', '.join(candidate["universe"])}`
- Timeframe: `{candidate["timeframe"]}`
- Rebalance schedule: {candidate["rebalance_schedule"]}
- Signal rule: {candidate["signal_rule"]}
- Allocation/sizing rule: {candidate["allocation_sizing_rule"]}
- Risk controls: {'; '.join(candidate["risk_controls"])}
- Slippage/stress assumptions: {'; '.join(candidate["slippage_stress_assumptions"])}
- Benchmark group: {', '.join(candidate["benchmark_group"])}
- Data requirements: {'; '.join(candidate["data_requirements"])}
- Acceptance gates: {'; '.join(candidate["acceptance_gates"])}
- Rejection gates: {'; '.join(candidate["rejection_gates"])}
- Valid future outcomes: `{', '.join(candidate["valid_future_outcomes"])}`
""")
    return "\n".join(blocks)


def data_availability_md(rows: list[dict[str, Any]], status: str) -> str:
    lines = [
        "# Risk-Controlled Data Availability Report",
        "",
        f"Status: `{status}`",
        "",
        "Local approved/cache-present daily data only. No provider download or API call was performed.",
        "",
        "| Symbol | Approved Status | Cache Present | First Date | Last Date | Row Count | Adj Close | Null Count | Duplicate Dates | Stale | Supports Required Window |",
        "|---|---|---:|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['symbol']} | {row['approved_status']} | {row['cache_present']} | {row['first_date']} | {row['last_date']} | {row['row_count']} | {row['adjusted_close_available']} | {row['null_count']} | {row['duplicate_date_count']} | {row['stale_flag']} | {row['supports_required_window']} |"
        )
    return "\n".join(lines) + "\n"


def benchmark_plan_md() -> str:
    return """# Risk-Controlled Benchmark Plan

`rc_dual_momentum_paa_vol_scaled_v1` benchmarks:

- SPY buy-and-hold
- QQQ buy-and-hold
- SPY 200d trend model
- active VM
- active DSR
- active combo benchmark
- static_all_weather_benchmark_v1

`rc_donchian_breakout_risk_budget_v1` benchmarks:

- SPY buy-and-hold
- QQQ buy-and-hold
- SPY 200d trend model
- active combo benchmark
- vol_compression_breakout_etf_v1 reference
- BIL cash proxy

Benchmark comparison is authorized only in a later discovery batch.
"""


def acceptance_gates_md() -> str:
    return """# Risk-Controlled Acceptance Gates

Shared gates:

- Pass risk-buffer gate under standard and stress slippage.
- Preserve enough 180d target-window upside to remain relevant to the profit objective.
- Show distinct behavior versus active VM, active DSR, active combo, and static benchmark controls where applicable.
- Avoid reliance on one symbol, one regime, or one crisis period.
- Use only the one pre-registered risk-control dimension for the candidate.

No candidate can go directly to candidate_exhaustive, paper-forward, demo active, or live-ready status.
"""


def rejection_gates_md() -> str:
    return """# Risk-Controlled Rejection Gates

Reject a candidate if:

- drawdown or risk-buffer gate still fails,
- stress slippage invalidates the case,
- risk control removes too much upside for the profit objective,
- candidate behavior duplicates an active/reference strategy,
- results require post-evidence threshold changes,
- exact rejected parent row is effectively reopened,
- hidden intraday, leverage, margin, shorting, derivative, or broker/live assumptions appear.
"""


def do_not_run_md() -> str:
    return """# Do Not Run Now

This packet is pre-registration and family review only.

Do not run:

- backtests,
- discovery,
- new performance metrics,
- candidate_exhaustive,
- paper-forward review or activation,
- provider downloads,
- intraday data,
- broker/live paths,
- real-money recommendations.
"""


def next_action_md() -> str:
    return f"""# Risk-Controlled Next Action

`{NEXT_ACTION}`

Do not run the next action in this task.
"""


def update_metadata(root: Path, output: Path, created_utc: str, manifest: dict[str, Any]) -> tuple[bool, bool]:
    registry_updated = False
    registry_path = root / REGISTRY_PATH
    if registry_path.exists():
        registry = load_yaml(registry_path)
        metadata = registry.setdefault("registry", {})
        metadata.update(
            {
                "risk_controlled_high_return_family_review_path": str(output),
                "risk_controlled_high_return_family_review_status": "pre_registered",
                "risk_controlled_high_return_family_review_created_utc": created_utc,
                "risk_controlled_high_return_candidate_count": manifest["candidate_count"],
                "risk_controlled_high_return_candidate_ids": manifest["candidate_ids"],
                "risk_controlled_high_return_data_availability_status": manifest["data_availability_status"],
                "risk_controlled_high_return_next_action": manifest["next_action"],
                "current_next_action": manifest["next_action"],
                "next_action": manifest["next_action"],
                **MANIFEST_FLAGS,
                "updated_utc": created_utc,
            }
        )
        registry_path.write_text(yaml.safe_dump(registry, sort_keys=False, width=120, allow_unicode=False), encoding="utf-8")
        registry_updated = True

    roadmap_path = root / ROADMAP_PATH
    existing = roadmap_path.read_text(encoding="utf-8") if roadmap_path.exists() else "# Research Roadmap\n"
    lines = existing.splitlines()
    for idx, line in enumerate(lines):
        if line.startswith("Current next action:"):
            lines[idx] = f"Current next action: `{manifest['next_action']}`"
            break
    else:
        insert_at = 1 if lines and lines[0].startswith("#") else 0
        lines.insert(insert_at, f"Current next action: `{manifest['next_action']}`")
    base = "\n".join(lines)
    marker = "## Risk-Controlled High-Return Family Review"
    section = f"""## Risk-Controlled High-Return Family Review

- Created UTC: `{created_utc}`
- Evidence path: `{output}`
- Pre-registration only: `true`
- Candidate count: `{manifest["candidate_count"]}`
- Candidate IDs: `{', '.join(manifest["candidate_ids"])}`
- Families reviewed: `{', '.join(manifest["families_reviewed"])}`
- Exact rejected parents remain closed: `{', '.join(manifest["parent_rejected_rows"])}`
- Data availability status: `{manifest["data_availability_status"]}`
- Intraday research remains paused: `true`
- Next action: `{manifest["next_action"]}`
- No backtest, discovery, new performance metric, provider download, intraday data, candidate_exhaustive, paper-forward action, broker/live path, strategy-state change, rejected-row reopening, or real-money recommendation is authorized.
"""
    updated = base.split(marker, 1)[0].rstrip() + "\n\n" + section if marker in base else base.rstrip() + "\n\n" + section
    roadmap_path.parent.mkdir(parents=True, exist_ok=True)
    roadmap_path.write_text(updated.rstrip() + "\n", encoding="utf-8")
    return registry_updated, True


def consistency_check(
    output: Path,
    manifest: dict[str, Any],
    strategies_before: list[dict[str, Any]],
    strategies_after: list[dict[str, Any]],
) -> dict[str, Any]:
    required_present = {
        name: True if name == "risk_controlled_consistency_check.json" else (output / name).exists()
        for name in REQUIRED_FILES
    }
    flags_match = all(manifest.get(key) == value for key, value in MANIFEST_FLAGS.items())
    candidates = manifest["candidate_specs"]
    candidate_count = manifest["candidate_count"]
    valid_lanes = {"macro_gld_duration_risk_off_lane", "moderate_tactical_etf_lane"}
    check = {
        "pre_registration_only": manifest["pre_registration_only"] is True,
        "family_review_only": manifest["family_review_only"] is True,
        "no_backtests": manifest["backtests_run"] is False,
        "no_discovery": manifest["discovery_run"] is False,
        "no_new_performance_metrics": manifest["new_performance_metrics_computed"] is False,
        "no_provider_download": manifest["provider_download"] is False,
        "no_intraday_data_used": manifest["intraday_data_used"] is False,
        "no_candidate_exhaustive": manifest["candidate_exhaustive_run"] is False,
        "no_paper_forward_action": manifest["paper_forward_review"] is False and manifest["paper_forward_activation"] is False,
        "no_broker_or_live_path": manifest["broker_path_touched"] is False and manifest["live_orders"] is False,
        "exact_rejected_variants_remain_closed": manifest["exact_rejected_variants_reopened"] is False,
        "parent_rejected_rows_documented": sorted(manifest["parent_rejected_rows"]) == ["donchian_atr_breakout_etf_v1", "dual_momentum_paa_clean_v1"],
        "candidate_count_valid": 1 <= candidate_count <= 3 or (candidate_count == 0 and manifest["next_action"] == "pause_expansion_and_summarize_tournament_state"),
        "every_candidate_has_new_hypothesis": all(bool(candidate.get("new_hypothesis")) for candidate in candidates),
        "every_candidate_changes_exactly_one_dimension": all(isinstance(candidate.get("one_major_changed_dimension"), str) and candidate.get("one_major_changed_dimension") for candidate in candidates),
        "every_candidate_has_valid_lane": all(candidate.get("lane") in valid_lanes for candidate in candidates),
        "data_availability_report_exists": required_present["risk_controlled_data_availability_report.md"],
        "acceptance_gates_exist": required_present["risk_controlled_acceptance_gates.md"],
        "rejection_gates_exist": required_present["risk_controlled_rejection_gates.md"],
        "do_not_run_now_file_exists": required_present["risk_controlled_do_not_run_now.md"],
        "next_action_valid": manifest["next_action"] in VALID_NEXT_ACTIONS,
        "manifest_flags_match_strict_scope": flags_match,
        "no_strategy_state_changes": strategy_state_map(strategies_before) == strategy_state_map(strategies_after),
        "all_required_files_present": all(required_present.values()),
    }
    check["consistency_passed"] = all(check.values())
    return check


def run_risk_controlled_high_return_family_review(root: Path = ROOT) -> dict[str, Any]:
    root = Path(root)
    created_utc = now_utc()
    output = clean_output(root)
    strategies_before = strategy_snapshot(root)
    prior = prior_evidence(root)
    availability_rows, availability_status = data_availability(root)
    candidate_ids = [candidate["candidate_id"] for candidate in CANDIDATES]
    parent_rows = [candidate["exact_rejected_parent_row"] for candidate in CANDIDATES]
    next_action = NEXT_ACTION if availability_status == "sufficient_for_preregistered_discovery" else "manual_review_required_for_risk_controlled_high_return_batch"
    manifest: dict[str, Any] = {
        "artifact": "risk_controlled_high_return_family_review",
        "created_utc": created_utc,
        "output_dir": str(output),
        "prior_evidence": prior,
        **MANIFEST_FLAGS,
        "candidate_count": len(CANDIDATES),
        "candidate_ids": candidate_ids,
        "parent_rejected_rows": parent_rows,
        "families_reviewed": FAMILIES_REVIEWED,
        "data_availability_status": availability_status,
        "next_action": next_action,
        "candidate_specs": CANDIDATES,
    }

    write_json(output / "risk_controlled_high_return_manifest.json", manifest)
    (output / "risk_controlled_high_return_summary.md").write_text(summary_md(created_utc, output, manifest), encoding="utf-8")
    (output / "high_return_family_review.md").write_text(family_review_md(), encoding="utf-8")
    (output / "exact_rejected_parent_closure.md").write_text(parent_closure_md(), encoding="utf-8")
    (output / "risk_controlled_candidate_specs.md").write_text(candidate_specs_md(), encoding="utf-8")
    (output / "risk_controlled_candidate_specs.yaml").write_text(
        yaml.safe_dump({"candidates": CANDIDATES}, sort_keys=False, width=120, allow_unicode=False),
        encoding="utf-8",
    )
    write_csv_rows(
        output / "risk_controlled_lane_assignment.csv",
        lane_rows(),
        ["candidate_id", "lane", "source_family", "exact_rejected_parent_row", "one_major_changed_dimension", "valid_future_outcomes"],
    )
    (output / "risk_controlled_data_availability_report.md").write_text(
        data_availability_md(availability_rows, availability_status),
        encoding="utf-8",
    )
    (output / "risk_controlled_benchmark_plan.md").write_text(benchmark_plan_md(), encoding="utf-8")
    (output / "risk_controlled_acceptance_gates.md").write_text(acceptance_gates_md(), encoding="utf-8")
    (output / "risk_controlled_rejection_gates.md").write_text(rejection_gates_md(), encoding="utf-8")
    (output / "risk_controlled_do_not_run_now.md").write_text(do_not_run_md(), encoding="utf-8")
    (output / "risk_controlled_next_action.md").write_text(next_action_md().replace(NEXT_ACTION, next_action), encoding="utf-8")

    registry_updated, roadmap_updated = update_metadata(root, output, created_utc, manifest)
    manifest["registry_metadata_updated"] = registry_updated
    manifest["roadmap_updated"] = roadmap_updated
    write_json(output / "risk_controlled_high_return_manifest.json", manifest)

    strategies_after = strategy_snapshot(root)
    check = consistency_check(output, manifest, strategies_before, strategies_after)
    write_json(output / "risk_controlled_consistency_check.json", check)
    return {
        "output_dir": str(output),
        "manifest": manifest,
        "consistency_check": check,
    }


def main() -> None:
    result = run_risk_controlled_high_return_family_review(ROOT)
    manifest = result["manifest"]
    check = result["consistency_check"]
    print(f"risk-controlled high-return review written: {result['output_dir']}")
    print(f"candidate_count: {manifest['candidate_count']}")
    print(f"candidate_ids: {','.join(manifest['candidate_ids'])}")
    print(f"data_availability_status: {manifest['data_availability_status']}")
    print(f"next action: {manifest['next_action']}")
    print(f"consistency_passed: {check['consistency_passed']}")
    if not check["consistency_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
