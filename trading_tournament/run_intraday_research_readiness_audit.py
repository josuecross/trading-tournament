from __future__ import annotations

import csv
import json
import shutil
import zipfile
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = Path("evidence") / "intraday_readiness" / "intraday_research_readiness_audit" / "latest"
REGISTRY_PATH = Path("strategy_lab") / "strategy_registry.yaml"
ROADMAP_PATH = Path("strategy_lab") / "RESEARCH_ROADMAP.md"

ALPACA_ROOT = Path("execution_lab") / "alpaca_micro_live_v1"
HISTORICAL_BARS_PATH = ALPACA_ROOT / "data" / "alpaca_historical_bars.py"
RUNTIME_CACHE_PATH = ALPACA_ROOT / "data" / "alpaca_runtime_cache.py"
RUNTIME_ORCHESTRATOR_PATH = ALPACA_ROOT / "execution" / "runtime_orchestrator.py"
WEEKLY_RUNNER_PATH = ALPACA_ROOT / "execution" / "weekly_demo_runner.py"
RISK_GATE_PATH = ALPACA_ROOT / "execution" / "risk_gate.py"
ORDER_SIZING_PATH = ALPACA_ROOT / "execution" / "order_sizing.py"
RECONCILE_PATH = ALPACA_ROOT / "execution" / "reconcile_orders.py"
ALPACA_CLIENT_PATH = ALPACA_ROOT / "adapters" / "alpaca_client.py"
RISK_LIMITS_PATH = ALPACA_ROOT / "config" / "risk_limits.example.yaml"
PROJECT_CONFIG_PATH = Path("config.yaml")
THIRD_EXPANSION_FAILURE_AUDIT_DIR = Path("evidence") / "tournament_failure_synthesis" / "third_expansion_failure_audit" / "latest"

READINESS_VERDICT = "intraday_research_not_ready"
NEXT_ACTION = "fix_intraday_readiness_blockers"
VALID_READINESS_VERDICTS = {
    "intraday_research_ready",
    "intraday_research_not_ready",
    "intraday_research_ready_with_blockers",
    "manual_review_required",
}
VALID_NEXT_ACTIONS = {
    "fix_intraday_readiness_blockers",
    "pre_register_intraday_research_harness",
    "pause_expansion_and_summarize_tournament_state",
    "pre_register_risk_controlled_high_return_family_review",
}

MANIFEST_FLAGS = {
    "audit_only": True,
    "intraday_readiness_audit": True,
    "intraday_strategy_backtests_run": False,
    "new_discovery_run": False,
    "new_performance_metrics_computed": False,
    "provider_download": False,
    "intraday_data_downloaded": False,
    "candidate_exhaustive_run": False,
    "paper_forward_review": False,
    "paper_forward_activation": False,
    "broker_path_touched_read_only_if_any": True,
    "broker_orders_submitted": False,
    "broker_orders_cancelled": False,
    "live_orders": False,
    "real_money_recommendation": False,
    "strategy_rules_changed": False,
    "accepted_strategy_state_changed": False,
    "rejected_strategy_state_changed": False,
}

REQUIRED_FILES = [
    "intraday_readiness_manifest.json",
    "intraday_readiness_summary.md",
    "intraday_data_support_audit.md",
    "intraday_signal_timing_audit.md",
    "intraday_fill_slippage_audit.md",
    "intraday_order_logging_reconciliation_audit.md",
    "intraday_position_risk_audit.md",
    "intraday_kill_switch_audit.md",
    "intraday_small_account_operational_audit.md",
    "intraday_candidate_suitability.md",
    "intraday_blocker_list.csv",
    "intraday_readiness_scorecard.csv",
    "intraday_readiness_next_action.md",
    "intraday_readiness_consistency_check.json",
]


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_text(root: Path, path: Path) -> str:
    target = root / path
    if not target.exists():
        return ""
    return target.read_text(encoding="utf-8", errors="replace")


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


def validate_authorization(root: Path) -> list[str]:
    mismatches: list[str] = []
    registry_next = load_yaml(root / REGISTRY_PATH).get("registry", {}).get("current_next_action")
    if registry_next and registry_next not in {"pre_register_intraday_research_readiness_audit", NEXT_ACTION}:
        mismatches.append(f"registry current_next_action is {registry_next}")
    previous_manifest = root / THIRD_EXPANSION_FAILURE_AUDIT_DIR / "third_expansion_failure_audit_manifest.json"
    if previous_manifest.exists():
        payload = json.loads(previous_manifest.read_text(encoding="utf-8"))
        previous_next = payload.get("next_action")
        if previous_next not in {"pre_register_intraday_research_readiness_audit", NEXT_ACTION}:
            mismatches.append(f"third expansion failure audit next_action is {previous_next}")
    return mismatches


def inspect_repository(root: Path) -> dict[str, Any]:
    historical = read_text(root, HISTORICAL_BARS_PATH)
    runtime_cache = read_text(root, RUNTIME_CACHE_PATH)
    orchestrator = read_text(root, RUNTIME_ORCHESTRATOR_PATH)
    weekly = read_text(root, WEEKLY_RUNNER_PATH)
    risk_gate = read_text(root, RISK_GATE_PATH)
    order_sizing = read_text(root, ORDER_SIZING_PATH)
    reconcile = read_text(root, RECONCILE_PATH)
    client = read_text(root, ALPACA_CLIENT_PATH)
    risk_limits = read_text(root, RISK_LIMITS_PATH)
    project_config = read_text(root, PROJECT_CONFIG_PATH)
    intraday_dir = root / "data" / "intraday"
    return {
        "daily_bars_fetcher_exists": bool(historical),
        "daily_timeframe_requested": 'timeframe="1Day"' in historical or "timeframe='1Day'" in historical,
        "minute_timeframe_requested": any(token in historical for token in ['timeframe="1Min"', 'timeframe="5Min"', "1Min", "5Min"]),
        "runtime_cache_daily_only": "_1Day.csv" in runtime_cache,
        "project_config_intraday_dir_declared": "intraday_dir" in project_config,
        "local_intraday_cache_exists": intraday_dir.exists() and any(intraday_dir.rglob("*")),
        "timestamp_utc_parse_present": "utc=True" in historical or "timezone.utc" in historical,
        "market_clock_read_present": "get_market_clock" in client and "get_market_clock" in orchestrator,
        "order_submit_present": "submit_order" in client,
        "paper_only_guard_present": "Only Alpaca paper mode is supported" in client and "Live mode is out of scope" in orchestrator,
        "order_logging_present": "orders.jsonl" in orchestrator or "submitted_orders.jsonl" in weekly,
        "weekly_event_files_present": "EVENT_FILES" in weekly and "order_statuses.jsonl" in weekly,
        "order_reconciliation_present": "get_order_by_id" in reconcile or "reconcile_order_statuses" in weekly,
        "open_order_tracking_present": "list_open_orders" in client and "open_orders.jsonl" in weekly,
        "idempotency_present": "target_version_already_handled" in risk_gate and "handled_target_versions" in weekly,
        "emergency_stop_present": "EMERGENCY_STOP_FILE" in weekly or "emergency_stop" in risk_gate,
        "risk_gate_present": "evaluate_risk_gate" in risk_gate,
        "max_daily_loss_present": "max_daily_loss" in risk_limits,
        "max_weekly_loss_present": "max_weekly_loss" in risk_limits,
        "notional_caps_present": "max_order_notional" in risk_limits and "max_total_notional_per_run" in risk_limits,
        "fractional_or_notional_order_support": "notional" in order_sizing and "fractionable" in risk_gate,
        "fill_model_present": "filled_avg_price" in weekly or "fills.jsonl" in weekly,
        "spread_model_present": "spread" in historical.lower() or "bid" in historical.lower() or "ask" in historical.lower(),
        "partial_fill_model_present": "partial" in weekly.lower() or "partially_filled" in weekly.lower(),
        "no_fill_model_present": "no_fill" in weekly.lower() or "partial" in weekly.lower(),
        "intraday_strategy_candidates_implemented": any(
            token in "\n".join([historical, orchestrator, weekly, project_config]).lower()
            for token in ["orb_spy_qqq_30m_research_v1", "gap_down_fade_spy_qqq_research_v1", "vwap_deviation_reversion_research_v1"]
        ),
    }


def blocker_rows(scan: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [
        {
            "blocker_id": "intraday_data_source_and_cache_missing",
            "severity": "critical",
            "area": "intraday_data_support",
            "status": "open",
            "evidence": "Existing Alpaca runtime fetcher/cache is daily 1Day oriented; no approved 1-minute/5-minute local cache was found.",
            "required_fix": "Define approved intraday data source, cache layout, timezone policy, and vendor/license terms before any intraday research run.",
        },
        {
            "blocker_id": "timestamp_session_calendar_unproven",
            "severity": "critical",
            "area": "intraday_data_support",
            "status": "open",
            "evidence": "Daily bars parse UTC timestamps and market clock exists, but no intraday session calendar, early-close, holiday, partial-day, or missing-bar audit was found.",
            "required_fix": "Add intraday session/calendar validation and missing/partial bar handling tests.",
        },
        {
            "blocker_id": "signal_bar_entry_exit_contract_missing",
            "severity": "critical",
            "area": "signal_timing",
            "status": "open",
            "evidence": "Daily signal generation uses completed daily bars; no intraday completed-bar contract distinguishes signal bar, entry bar, and exit bar.",
            "required_fix": "Pre-register and test completed-bar-only signal timing for ORB, gap, and VWAP families.",
        },
        {
            "blocker_id": "intraday_fill_slippage_model_missing",
            "severity": "critical",
            "area": "fill_slippage",
            "status": "open",
            "evidence": "No intraday spread, market/limit, no-fill, partial-fill, or bar-extreme avoidance model is documented for research.",
            "required_fix": "Create fill/slippage/no-fill model and stress assumptions before strategy research.",
        },
        {
            "blocker_id": "intraday_risk_engine_missing",
            "severity": "critical",
            "area": "position_risk",
            "status": "open",
            "evidence": "Paper runtime has notional/order gates, but no intraday max daily loss, max weekly loss, no-overnight flattening, or stale-bar stop engine was found.",
            "required_fix": "Add offline intraday risk-state tracker and kill conditions before research harness pre-registration.",
        },
        {
            "blocker_id": "intraday_kill_switch_not_tested",
            "severity": "critical",
            "area": "kill_switch",
            "status": "open",
            "evidence": "Weekly demo stop files exist, but intraday-specific data-error, logging-failure, excessive-order, abnormal-loss, and reconciliation kill switches are not test-covered.",
            "required_fix": "Define and test intraday kill switches for offline research and any future paper runtime.",
        },
        {
            "blocker_id": "pdt_small_account_constraints_not_intraday_modeled",
            "severity": "non_critical",
            "area": "small_account_operational",
            "status": "open",
            "evidence": "Small notional caps and paper-only mode exist, but day-trade/PDT-style operational constraints are not modeled for intraday frequency.",
            "required_fix": "Add small-account/PDT-style research constraints and trade-count ceilings before classifying any intraday strategy as research-ready.",
        },
        {
            "blocker_id": "candidate_families_not_implemented_or_pre_registered",
            "severity": "non_critical",
            "area": "candidate_suitability",
            "status": "open",
            "evidence": "ORB, gap-down fade, and VWAP deviation families are suitable only as future research concepts and are not ready for tests.",
            "required_fix": "After blockers are fixed, pre-register an intraday research harness before any candidate-specific discovery.",
        },
    ]
    if scan.get("order_logging_present") and scan.get("order_reconciliation_present"):
        rows.append(
            {
                "blocker_id": "order_logging_reconciliation_not_intraday_specific",
                "severity": "non_critical",
                "area": "order_logging_reconciliation",
                "status": "open",
                "evidence": "Weekly paper runtime logs order statuses, fills, open orders, and derived fills, but this is not an intraday research replay/reconciliation model.",
                "required_fix": "Reuse the logging schema where useful, but add intraday event and replay semantics.",
            }
        )
    return rows


def scorecard_rows() -> list[dict[str, Any]]:
    return [
        {
            "area": "intraday_data_support",
            "readiness": "not_ready",
            "critical_blockers": 2,
            "main_finding": "No approved 1-minute/5-minute data source, local intraday cache, or session calendar QA is present.",
        },
        {
            "area": "signal_timing_and_bar_alignment",
            "readiness": "not_ready",
            "critical_blockers": 1,
            "main_finding": "No tested intraday signal bar / entry bar / exit bar contract exists.",
        },
        {
            "area": "fill_and_slippage_model",
            "readiness": "not_ready",
            "critical_blockers": 1,
            "main_finding": "No credible intraday fill, spread, partial/no-fill, or stress model is documented.",
        },
        {
            "area": "order_logging_and_reconciliation",
            "readiness": "partial",
            "critical_blockers": 0,
            "main_finding": "Paper runtime logging/reconciliation exists for daily/weekly operation but is not an intraday research replay model.",
        },
        {
            "area": "position_and_risk_tracking",
            "readiness": "not_ready",
            "critical_blockers": 1,
            "main_finding": "Intraday risk-state tracking, daily/weekly loss enforcement, stale-bar stops, and no-overnight flattening are missing.",
        },
        {
            "area": "kill_switch_readiness",
            "readiness": "not_ready",
            "critical_blockers": 1,
            "main_finding": "Weekly stop files exist, but intraday kill-switch behavior is not defined or tested.",
        },
        {
            "area": "small_account_operational_realism",
            "readiness": "partial",
            "critical_blockers": 0,
            "main_finding": "Small notional safeguards exist, but intraday PDT/trade-frequency realism is not modeled.",
        },
        {
            "area": "candidate_suitability",
            "readiness": "research_concepts_only",
            "critical_blockers": 0,
            "main_finding": "ORB, gap fade, and VWAP variants are suitable only after readiness blockers and harness pre-registration.",
        },
    ]


def summary_md(created_utc: str, output: Path, manifest: dict[str, Any]) -> str:
    return f"""# Intraday Research Readiness Audit

Created UTC: `{created_utc}`

Evidence path: `{output}`

Readiness verdict: `{manifest["readiness_verdict"]}`

Next action: `{manifest["next_action"]}`

## Decision

The project is not ready to research intraday strategies offline. The existing execution lab has useful paper-runtime safeguards and logs, but current evidence is daily/weekly oriented. Intraday research needs approved minute-level data, session/calendar validation, completed-bar signal timing, a credible fill/slippage/no-fill model, intraday risk-state tracking, and tested kill-switch behavior before any ORB, gap, or VWAP candidate can be researched.

This audit does not authorize intraday demo trading, paper-forward activation, broker orders, provider downloads, candidate_exhaustive, or intraday strategy discovery.

## Critical Blockers

- Approved 1-minute/5-minute intraday data source and cache are missing.
- Intraday timestamp/session/holiday/early-close handling is unproven.
- Signal bar / entry bar / exit bar alignment contract is missing.
- Intraday fill/slippage/no-fill model is missing.
- Intraday risk-state engine is missing.
- Intraday kill-switch behavior is not defined or test-covered.
"""


def data_support_md(scan: dict[str, Any]) -> str:
    return f"""# Intraday Data Support Audit

Verdict: `not_ready`

Findings:

- Daily Alpaca bar support exists: `{scan["daily_bars_fetcher_exists"]}`.
- Existing fetcher requests daily bars: `{scan["daily_timeframe_requested"]}`.
- Existing runtime cache is daily-only (`*_1Day.csv`): `{scan["runtime_cache_daily_only"]}`.
- Project config declares `data/intraday`: `{scan["project_config_intraday_dir_declared"]}`.
- Local intraday cache with data found: `{scan["local_intraday_cache_exists"]}`.
- Approved 1-minute/5-minute source found: `false`.
- Bid/ask/spread fields found in intraday data model: `{scan["spread_model_present"]}`.

Conclusion: the repository is not intraday-data-ready. A directory setting is not enough; the project needs a vetted data source, cache schema, timezone/session policy, missing-bar handling, early-close handling, and terms/licensing review.
"""


def signal_timing_md() -> str:
    return """# Intraday Signal Timing Audit

Verdict: `not_ready`

The current runtime generates daily signals from completed daily bars. That is useful for paper/demo daily allocation, but it does not establish intraday timing safety.

Missing for intraday research:

- completed intraday bar contract,
- signal bar versus entry bar separation,
- entry bar versus exit bar separation,
- open-range window handling,
- VWAP calculation that cannot include future bars,
- gap-open logic using prior close and current open,
- timestamp/session tests for early closes and partial sessions.

No ORB, gap, or VWAP strategy should be tested before this contract exists.
"""


def fill_slippage_md() -> str:
    return """# Intraday Fill And Slippage Audit

Verdict: `not_ready`

The project has daily/weekly slippage assumptions and paper runtime order records, but no credible intraday research fill model.

Missing:

- spread model,
- market versus limit assumptions,
- no-fill and partial-fill handling,
- bar-extreme avoidance,
- intraday stress fills,
- queue/latency approximation,
- documented conversion from signal to executable entry.

This is a critical blocker because intraday strategy results can be dominated by fill assumptions.
"""


def order_logging_md() -> str:
    return """# Intraday Order Logging And Reconciliation Audit

Verdict: `partial`

The Alpaca micro paper runtime has useful logging foundations: proposed orders, submitted orders, open orders, broker errors, order statuses, fills, derived fills, risk-gate decisions, allocation drift, and execution-quality logs. It also tracks client order IDs and target-version idempotency.

Limitations:

- the logging is for daily/weekly paper runtime, not offline intraday research replay,
- partial-fill and no-fill research semantics are not fully modeled,
- intraday target versus actual position reconciliation is not defined,
- replay of signal/entry/exit events is not available.

Conclusion: reuse the schema ideas, but do not classify intraday research as ready from order logging alone.
"""


def position_risk_md() -> str:
    return """# Intraday Position And Risk Audit

Verdict: `not_ready`

Existing safeguards include small notional caps, max total notional per run, symbol approval, open-order conflicts, paper-only mode, no margin, no shorting, and no live trading support.

Missing for intraday:

- intraday position-state engine,
- max trades per day enforcement,
- max daily loss and max weekly loss enforcement,
- no-overnight/force-flat rules,
- stale or missing intraday bar halt behavior,
- position drift handling at intraday cadence,
- research replay of position changes.

These are critical before any intraday research run.
"""


def kill_switch_md() -> str:
    return """# Intraday Kill Switch Audit

Verdict: `not_ready`

Weekly demo stop and emergency-stop files exist. The risk gate can block when an emergency-stop flag is active.

Missing for intraday:

- data-error kill switch,
- broker/API-error kill switch for intraday loops,
- reconciliation-mismatch kill switch,
- abnormal-loss kill switch,
- excessive-order kill switch,
- logging-failure kill switch,
- test coverage for all of the above in intraday context.

Stop files alone do not make intraday research ready.
"""


def small_account_md() -> str:
    return """# Small Account / PDT / Operational Audit

Verdict: `partial`

The project has a $3,000 small-account framework, strict loss budget culture, small notional paper-runtime caps, no margin, no shorting, and fractional/notional order support in the paper runtime.

Missing for intraday:

- day-trade/PDT-style frequency constraints,
- realistic trade-count ceilings by strategy family,
- intraday commission/spread/slippage policy,
- fractional/notional handling rules for intraday research fills,
- explicit policy that research-only intraday results cannot imply demo or real-money suitability.

These are fixable, but not currently ready.
"""


def candidate_suitability_md() -> str:
    return """# Intraday Candidate Suitability

No candidate was backtested.

`orb_spy_qqq_30m_research_v1`: suitable only as a future research concept after intraday data/session/timing/fill blockers are fixed. It especially needs open-range window semantics, completed-bar entry rules, and no-lookahead handling.

`gap_down_fade_spy_qqq_research_v1`: suitable only as a future research concept after prior-close/current-open gap logic, open auction assumptions, spread/slippage, and no-fill rules are defined.

`vwap_deviation_reversion_research_v1`: suitable only as a future research concept after VWAP calculation is proven to use only elapsed bars and after fill/slippage assumptions are stress-tested.

Candidate summary: all three are research-only concepts, not ready for discovery, not demo eligible, not paper-forward eligible, and not real-money recommendations.
"""


def next_action_md() -> str:
    return f"""# Intraday Readiness Next Action

`{NEXT_ACTION}`

Fix readiness blockers before any intraday research harness or candidate test. This next action does not authorize intraday backtests, discovery, provider downloads, candidate_exhaustive, paper-forward activation, broker orders, live orders, or real-money recommendations.
"""


def update_metadata(root: Path, output: Path, created_utc: str) -> tuple[bool, bool]:
    registry_updated = False
    registry_path = root / REGISTRY_PATH
    if registry_path.exists():
        registry = load_yaml(registry_path)
        metadata = registry.setdefault("registry", {})
        metadata.update(
            {
                "intraday_research_readiness_audit_path": str(output),
                "intraday_research_readiness_audit_status": "completed",
                "intraday_research_readiness_audit_created_utc": created_utc,
                "intraday_research_readiness_verdict": READINESS_VERDICT,
                "intraday_research_readiness_next_action": NEXT_ACTION,
                "current_next_action": NEXT_ACTION,
                "next_action": NEXT_ACTION,
                "intraday_strategy_discovery_authorized": False,
                "intraday_backtest_authorized": False,
                "intraday_data_downloaded": False,
                "audit_only": True,
                "intraday_readiness_audit": True,
                "new_backtests_run": False,
                "intraday_strategy_backtests_run": False,
                "new_discovery_run": False,
                "new_performance_metrics_computed": False,
                "provider_download": False,
                "candidate_exhaustive_run": False,
                "paper_forward_review": False,
                "paper_forward_activation": False,
                "broker_orders_submitted": False,
                "broker_orders_cancelled": False,
                "live_orders": False,
                "real_money_recommendation": False,
                "strategy_rules_changed": False,
                "accepted_strategy_state_changed": False,
                "rejected_strategy_state_changed": False,
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
            lines[idx] = f"Current next action: `{NEXT_ACTION}`"
            break
    else:
        insert_at = 1 if lines and lines[0].startswith("#") else 0
        lines.insert(insert_at, f"Current next action: `{NEXT_ACTION}`")
    base = "\n".join(lines)
    marker = "## Intraday Research Readiness Audit"
    section = f"""## Intraday Research Readiness Audit

- Created UTC: `{created_utc}`
- Evidence path: `{output}`
- Readiness verdict: `{READINESS_VERDICT}`
- Critical blockers: approved intraday data/cache, session calendar QA, signal/entry/exit bar contract, fill/slippage/no-fill model, intraday risk engine, and intraday kill-switch tests.
- Candidate suitability: ORB, gap-down fade, and VWAP deviation remain research-only concepts and are not authorized for discovery.
- Final next action: `{NEXT_ACTION}`
- No intraday backtest, strategy discovery, new performance metric, provider download, candidate_exhaustive, paper-forward action, broker order, live order, strategy-rule change, strategy-state change, or real-money recommendation is authorized by this audit.
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
        name: True if name == "intraday_readiness_consistency_check.json" else (output / name).exists()
        for name in REQUIRED_FILES
    }
    before_state = strategy_state_map(strategies_before)
    after_state = strategy_state_map(strategies_after)
    flags_match = all(manifest.get(key) == value for key, value in MANIFEST_FLAGS.items())
    check = {
        "audit_only_mode": manifest["audit_only"] is True,
        "no_intraday_strategy_backtests": manifest["intraday_strategy_backtests_run"] is False,
        "no_new_discovery": manifest["new_discovery_run"] is False,
        "no_new_performance_metrics": manifest["new_performance_metrics_computed"] is False,
        "no_provider_download": manifest["provider_download"] is False,
        "no_intraday_data_download": manifest["intraday_data_downloaded"] is False,
        "no_candidate_exhaustive": manifest["candidate_exhaustive_run"] is False,
        "no_paper_forward_action": manifest["paper_forward_review"] is False and manifest["paper_forward_activation"] is False,
        "no_broker_orders_submitted": manifest["broker_orders_submitted"] is False,
        "no_broker_orders_cancelled": manifest["broker_orders_cancelled"] is False,
        "no_live_orders": manifest["live_orders"] is False,
        "strategy_states_unchanged": before_state == after_state,
        "data_support_audit_exists": required_present["intraday_data_support_audit.md"],
        "signal_timing_audit_exists": required_present["intraday_signal_timing_audit.md"],
        "fill_slippage_audit_exists": required_present["intraday_fill_slippage_audit.md"],
        "order_logging_reconciliation_audit_exists": required_present["intraday_order_logging_reconciliation_audit.md"],
        "position_risk_audit_exists": required_present["intraday_position_risk_audit.md"],
        "kill_switch_audit_exists": required_present["intraday_kill_switch_audit.md"],
        "small_account_operational_audit_exists": required_present["intraday_small_account_operational_audit.md"],
        "candidate_suitability_file_exists": required_present["intraday_candidate_suitability.md"],
        "blocker_list_exists": required_present["intraday_blocker_list.csv"],
        "readiness_verdict_valid": manifest["readiness_verdict"] in VALID_READINESS_VERDICTS,
        "next_action_valid": manifest["next_action"] in VALID_NEXT_ACTIONS,
        "manifest_flags_match_strict_scope": flags_match,
        "all_required_files_present": all(required_present.values()),
    }
    check["consistency_passed"] = all(check.values())
    return check


def create_packet_zip(output: Path) -> Path:
    zip_path = output / "intraday_readiness_packet.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as packet:
        for name in REQUIRED_FILES:
            path = output / name
            if path.exists():
                packet.write(path, arcname=name)
    return zip_path


def run_intraday_research_readiness_audit(root: Path = ROOT) -> dict[str, Any]:
    root = Path(root)
    created_utc = now_utc()
    output = clean_output(root)
    strategies_before = strategy_snapshot(root)
    authorization_mismatches = validate_authorization(root)
    scan = inspect_repository(root)
    blockers = blocker_rows(scan)
    scorecard = scorecard_rows()
    critical_count = sum(1 for row in blockers if row["severity"] == "critical")

    manifest: dict[str, Any] = {
        "artifact": "intraday_research_readiness_audit",
        "created_utc": created_utc,
        "output_dir": str(output),
        "authorization_mismatches": authorization_mismatches,
        "repository_scan": scan,
        **MANIFEST_FLAGS,
        "readiness_verdict": READINESS_VERDICT,
        "blocker_count": len(blockers),
        "critical_blocker_count": critical_count,
        "next_action": NEXT_ACTION,
    }

    write_json(output / "intraday_readiness_manifest.json", manifest)
    (output / "intraday_readiness_summary.md").write_text(summary_md(created_utc, output, manifest), encoding="utf-8")
    (output / "intraday_data_support_audit.md").write_text(data_support_md(scan), encoding="utf-8")
    (output / "intraday_signal_timing_audit.md").write_text(signal_timing_md(), encoding="utf-8")
    (output / "intraday_fill_slippage_audit.md").write_text(fill_slippage_md(), encoding="utf-8")
    (output / "intraday_order_logging_reconciliation_audit.md").write_text(order_logging_md(), encoding="utf-8")
    (output / "intraday_position_risk_audit.md").write_text(position_risk_md(), encoding="utf-8")
    (output / "intraday_kill_switch_audit.md").write_text(kill_switch_md(), encoding="utf-8")
    (output / "intraday_small_account_operational_audit.md").write_text(small_account_md(), encoding="utf-8")
    (output / "intraday_candidate_suitability.md").write_text(candidate_suitability_md(), encoding="utf-8")
    write_csv_rows(
        output / "intraday_blocker_list.csv",
        blockers,
        ["blocker_id", "severity", "area", "status", "evidence", "required_fix"],
    )
    write_csv_rows(
        output / "intraday_readiness_scorecard.csv",
        scorecard,
        ["area", "readiness", "critical_blockers", "main_finding"],
    )
    (output / "intraday_readiness_next_action.md").write_text(next_action_md(), encoding="utf-8")

    registry_updated, roadmap_updated = update_metadata(root, output, created_utc)
    manifest["registry_metadata_updated"] = registry_updated
    manifest["roadmap_updated"] = roadmap_updated
    write_json(output / "intraday_readiness_manifest.json", manifest)

    strategies_after = strategy_snapshot(root)
    check = consistency_check(output, manifest, strategies_before, strategies_after)
    write_json(output / "intraday_readiness_consistency_check.json", check)
    packet_zip = create_packet_zip(output)
    return {
        "output_dir": str(output),
        "packet_zip": str(packet_zip),
        "manifest": manifest,
        "consistency_check": check,
    }


def main() -> None:
    result = run_intraday_research_readiness_audit(ROOT)
    check = result["consistency_check"]
    print(f"intraday readiness audit written: {result['output_dir']}")
    print(f"packet zip: {result['packet_zip']}")
    print(f"readiness verdict: {result['manifest']['readiness_verdict']}")
    print(f"next action: {result['manifest']['next_action']}")
    print(f"consistency_passed: {check['consistency_passed']}")
    if not check["consistency_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
