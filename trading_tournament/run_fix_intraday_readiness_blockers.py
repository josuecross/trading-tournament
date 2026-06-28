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

from intraday_research import (
    CANDIDATE_IDS,
    InfrastructureStatus,
    IntradayCacheContract,
    evaluate_candidate_readiness,
)


ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = Path("evidence") / "intraday_readiness" / "fix_intraday_readiness_blockers" / "latest"
PREVIOUS_AUDIT_DIR = Path("evidence") / "intraday_readiness" / "intraday_research_readiness_audit" / "latest"
REGISTRY_PATH = Path("strategy_lab") / "strategy_registry.yaml"
ROADMAP_PATH = Path("strategy_lab") / "RESEARCH_ROADMAP.md"

READINESS_VERDICT_AFTER_FIX = "manual_intraday_data_source_review_required"
NEXT_ACTION = "manual_intraday_data_source_review_required"
VALID_READINESS_VERDICTS = {
    "intraday_research_not_ready",
    "intraday_research_ready_with_blockers",
    "manual_intraday_data_source_review_required",
    "pre_register_intraday_research_harness",
}
VALID_NEXT_ACTIONS = {
    "manual_intraday_data_source_review_required",
    "pre_register_intraday_research_harness",
    "fix_intraday_readiness_blockers",
}

MANIFEST_FLAGS = {
    "blocker_fix_only": True,
    "intraday_strategy_backtests_run": False,
    "new_discovery_run": False,
    "new_performance_metrics_computed": False,
    "provider_download": False,
    "intraday_data_downloaded": False,
    "candidate_exhaustive_run": False,
    "paper_forward_review": False,
    "paper_forward_activation": False,
    "broker_orders_submitted": False,
    "broker_orders_cancelled": False,
    "live_orders": False,
    "broker_path_touched_execution": False,
    "real_money_recommendation": False,
    "strategy_rules_changed": False,
    "accepted_strategy_state_changed": False,
    "rejected_strategy_state_changed": False,
    "intraday_candidates_demo_eligible": False,
}

REQUIRED_FILES = [
    "intraday_blocker_fix_manifest.json",
    "intraday_blocker_fix_summary.md",
    "intraday_data_schema_contract.md",
    "intraday_cache_contract.md",
    "intraday_session_timing_contract.md",
    "intraday_fill_model_contract.md",
    "intraday_risk_engine_contract.md",
    "intraday_kill_switch_contract.md",
    "intraday_event_logging_contract.md",
    "intraday_candidate_readiness_gates.md",
    "intraday_blocker_resolution_table.csv",
    "intraday_remaining_blockers.csv",
    "intraday_next_action.md",
    "intraday_blocker_fix_consistency_check.json",
]


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


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


def previous_audit_summary(root: Path) -> dict[str, Any]:
    manifest = root / PREVIOUS_AUDIT_DIR / "intraday_readiness_manifest.json"
    if not manifest.exists():
        return {"previous_audit_found": False}
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    return {
        "previous_audit_found": True,
        "previous_readiness_verdict": payload.get("readiness_verdict"),
        "previous_next_action": payload.get("next_action"),
        "previous_blocker_count": payload.get("blocker_count"),
        "previous_critical_blocker_count": payload.get("critical_blocker_count"),
    }


def build_infrastructure_status(root: Path) -> tuple[InfrastructureStatus, dict[str, Any]]:
    contract = IntradayCacheContract(root=root / "data" / "intraday")
    cache_inspection = contract.inspect("SPY", "1Min")
    status = InfrastructureStatus(
        data_schema_contract=True,
        cache_contract=True,
        session_timing_contract=True,
        fill_model_contract=True,
        risk_engine_contract=True,
        kill_switch_contract=True,
        event_logging_contract=True,
        intraday_data_present=cache_inspection.data_present,
        intraday_data_source_approved=False,
    )
    return status, {
        "cache_status": cache_inspection.status,
        "intraday_data_present": cache_inspection.data_present,
        "metadata_present": cache_inspection.metadata_present,
        "row_count": cache_inspection.row_count,
        "first_timestamp": cache_inspection.first_timestamp,
        "last_timestamp": cache_inspection.last_timestamp,
        "stale": cache_inspection.stale,
        "missing_bar_count": cache_inspection.missing_bar_count,
        "allowed_timeframes": list(contract.allowed_timeframes),
        "cache_root": str(contract.root),
        "filename_convention": "{symbol}_{timeframe}.csv under data/intraday/{timeframe}/",
        "metadata_convention": "{symbol}_{timeframe}.metadata.json beside the cache file",
    }


def blocker_resolution_rows() -> list[dict[str, str]]:
    return [
        {
            "blocker_id": "local_intraday_bar_cache_missing",
            "severity": "critical",
            "resolution_status": "remaining",
            "fix_added": "Local cache contract and schema exist, but no minute data was downloaded or created.",
            "remaining_gap": "Approved local 1Min/5Min data cache remains absent.",
        },
        {
            "blocker_id": "intraday_capable_provider_cache_path_missing",
            "severity": "critical",
            "resolution_status": "partially_fixed",
            "fix_added": "Research-only cache convention, filename convention, metadata template, stale-data check, and missing-bar reporting were added.",
            "remaining_gap": "No provider source is approved and no provider download path was added.",
        },
        {
            "blocker_id": "session_calendar_timestamp_alignment_missing",
            "severity": "critical",
            "resolution_status": "fixed",
            "fix_added": "Regular-session utility, early-close/holiday placeholders, completed-bar timing, signal/entry separation, and no-lookahead plan were added.",
            "remaining_gap": "Needs manual calendar-source approval before production-grade research.",
        },
        {
            "blocker_id": "fill_slippage_no_fill_model_missing",
            "severity": "critical",
            "resolution_status": "fixed",
            "fix_added": "Conservative market-fill approximation, spread/slippage costs, stress mode, bar-extreme avoidance, no-fill, and partial-fill placeholders were added.",
            "remaining_gap": "Future harness must pre-register concrete cost assumptions before any strategy test.",
        },
        {
            "blocker_id": "intraday_risk_engine_missing",
            "severity": "critical",
            "resolution_status": "fixed",
            "fix_added": "Research-only risk engine supports max trades, daily/weekly loss, open positions, notional exposure, stale/missing data, abnormal loss, excessive orders, and no-overnight force-flat.",
            "remaining_gap": "Future harness must wire these rules into replay before candidate research.",
        },
        {
            "blocker_id": "candidate_suitability_missing",
            "severity": "critical",
            "resolution_status": "partially_fixed",
            "fix_added": "Candidate readiness gate was added for ORB, gap fade, and VWAP research concepts.",
            "remaining_gap": "All candidates remain research_concept_not_ready until data/source approval and harness pre-registration.",
        },
        {
            "blocker_id": "logging_reconciliation_not_intraday_specific",
            "severity": "non_critical",
            "resolution_status": "fixed",
            "fix_added": "Research-only event logging contract defines signal, simulated order, simulated fill/no-fill/partial-fill, risk, kill-switch, forced-flat, and session events.",
            "remaining_gap": "Future replay can extend this with reconciliation outputs.",
        },
        {
            "blocker_id": "pdt_small_account_constraints_not_formalized",
            "severity": "non_critical",
            "resolution_status": "fixed",
            "fix_added": "Risk limits include max trades per day, excessive-order halt, max notional exposure, and no-overnight force-flat for small-account realism.",
            "remaining_gap": "Manual policy review still needed before demo eligibility.",
        },
        {
            "blocker_id": "intraday_kill_switch_rules_missing",
            "severity": "non_critical",
            "resolution_status": "fixed",
            "fix_added": "Kill-switch reasons now cover data error, timestamp/session error, fill-model error, risk breach, excessive orders, reconciliation mismatch, and logging failure.",
            "remaining_gap": "Future harness must persist and replay these events.",
        },
    ]


def remaining_blocker_rows() -> list[dict[str, str]]:
    return [
        {
            "blocker_id": "approved_intraday_data_source_missing",
            "severity": "critical",
            "status": "open",
            "why_remaining": "No data source or license/terms review was approved in this blocker-fix step.",
            "required_next_step": "manual_intraday_data_source_review_required",
        },
        {
            "blocker_id": "local_intraday_data_absent",
            "severity": "critical",
            "status": "open",
            "why_remaining": "The cache contract exists but no 1Min/5Min bars are present because provider download was forbidden.",
            "required_next_step": "approve data source before any future controlled cache bootstrap",
        },
        {
            "blocker_id": "intraday_research_harness_not_preregistered",
            "severity": "non_critical",
            "status": "open",
            "why_remaining": "Contracts exist, but no harness should be pre-registered until the data source question is resolved.",
            "required_next_step": "pre_register_intraday_research_harness only after data-source review",
        },
    ]


def summary_md(created_utc: str, output: Path, manifest: dict[str, Any]) -> str:
    return f"""# Fix Intraday Readiness Blockers

Created UTC: `{created_utc}`

Evidence path: `{output}`

Readiness verdict after fix: `{manifest["readiness_verdict_after_fix"]}`

Next action: `{manifest["next_action"]}`

## Scope

This was an infrastructure-only blocker-fix step. It created research-only intraday contracts for data validation, cache layout, session/timing alignment, fill/slippage/no-fill simulation, risk governance, kill switches, event logging, and candidate readiness gates.

No intraday strategy backtest, discovery, performance metric, provider download, candidate_exhaustive, paper-forward action, broker order, live order, strategy-state change, or real-money recommendation was performed.

## Result

- Blockers fixed: `{manifest["blockers_fixed_count"]}`
- Blockers partially fixed: `{manifest["blockers_partially_fixed_count"]}`
- Remaining blockers: `{manifest["blockers_remaining_count"]}`
- Critical blockers remaining: `{manifest["critical_blockers_remaining_count"]}`
- Intraday cache contract created: `{manifest["intraday_cache_contract_created"]}`
- Intraday data present: `{manifest["intraday_data_present"]}`
- Intraday data source approved: `{manifest["intraday_data_source_approved"]}`

The main remaining blocker is data-source approval plus a real local intraday cache. Because provider downloads were explicitly out of scope, the honest next step is manual intraday data-source review.
"""


def data_schema_contract_md() -> str:
    return """# Intraday Data Schema Contract

Required fields:

- `symbol`
- `timestamp`
- `open`
- `high`
- `low`
- `close`
- `volume`
- `timeframe`
- `source`
- `adjusted`

Rules:

- Timestamps must be timezone-aware and are normalized to UTC.
- Allowed research timeframes are `1Min` and `5Min`.
- Daily bars are rejected because `1Day` is not an allowed intraday timeframe.
- Duplicate `symbol` plus `timestamp` rows are rejected.
- Timestamps must be strictly monotonic per symbol.
- OHLCV fields must be present and non-null.
- OHLC prices must be positive; volume must be non-negative.
- High/low must contain open and close.
"""


def cache_contract_md(cache_scan: dict[str, Any]) -> str:
    return f"""# Intraday Cache Contract

Status: `{cache_scan["cache_status"]}`

Expected folder path: `{cache_scan["cache_root"]}`

Filename convention: `{cache_scan["filename_convention"]}`

Metadata convention: `{cache_scan["metadata_convention"]}`

Allowed timeframes: `{", ".join(cache_scan["allowed_timeframes"])}`

Required schema: `intraday_research_v1`

Metadata file fields:

- `symbol`
- `timeframe`
- `source`
- `timezone_policy`
- `schema`
- `first_timestamp`
- `last_timestamp`
- `row_count`
- `adjusted`
- `early_close_calendar`
- `holiday_calendar`
- `provider_download_performed_by_contract`

Reporting:

- Intraday data present: `{cache_scan["intraday_data_present"]}`
- First timestamp: `{cache_scan["first_timestamp"]}`
- Last timestamp: `{cache_scan["last_timestamp"]}`
- Stale-data flag: `{cache_scan["stale"]}`
- Missing-bar count: `{cache_scan["missing_bar_count"]}`

Evidence statement: `intraday_cache_contract_created_but_no_data_present`
"""


def session_timing_contract_md() -> str:
    return """# Intraday Session Timing Contract

The session utility defines regular-market boundaries with placeholders for early closes and holidays. It enforces:

- regular session open and close,
- holiday/no-session placeholder support,
- early-close placeholder support,
- completed-bar-only signal timing,
- signal bar versus entry bar separation,
- exit deadline before or at session close,
- no-lookahead enforcement by requiring entry time after the completed signal bar.

Future ORB, gap, and VWAP research can use this contract, but no strategy was run in this step.
"""


def fill_model_contract_md() -> str:
    return """# Intraday Fill Model Contract

The research fill model supports:

- market order approximation,
- configurable spread cost,
- configurable slippage in basis points or cents,
- no-fill condition,
- partial-fill placeholder,
- bar-extreme avoidance,
- fill stress mode.

It is an offline simulation interface only. It does not call a broker, submit an order, or consume broker fills.
"""


def risk_engine_contract_md() -> str:
    return """# Intraday Risk Engine Contract

The research-only risk engine supports:

- max trades per day,
- max daily loss,
- max weekly loss,
- max open positions,
- max notional exposure,
- force-flat/no-overnight rule,
- stale/missing data halt,
- abnormal-loss halt,
- excessive-order halt,
- logging failure halt placeholder.

This is not wired to live execution and does not authorize paper-forward activity.
"""


def kill_switch_contract_md() -> str:
    return """# Intraday Kill Switch Contract

Kill-switch reasons:

- `data_error`
- `timestamp_session_error`
- `fill_model_error`
- `risk_breach`
- `excessive_order_count`
- `reconciliation_mismatch`
- `logging_failure`

The recorder stores research-only halt events. It does not touch broker order submission or cancellation.
"""


def event_logging_contract_md() -> str:
    return """# Intraday Event Logging Contract

Allowed research events:

- `signal_generated`
- `order_intent_created`
- `simulated_order_submitted`
- `simulated_fill`
- `simulated_no_fill`
- `simulated_partial_fill`
- `position_updated`
- `risk_gate_block`
- `kill_switch_triggered`
- `forced_flat`
- `session_closed`

Events are simulation/research events only. This contract deliberately avoids broker order submission, cancellation, and live-order paths.
"""


def candidate_readiness_gates_md(candidate_status: dict[str, str]) -> str:
    rows = "\n".join(f"- `{candidate_id}`: `{status}`" for candidate_id, status in candidate_status.items())
    return f"""# Intraday Candidate Readiness Gates

Each candidate remains `research_concept_not_ready` unless all required infrastructure exists, intraday data is present, and the intraday data source is approved.

{rows}

No candidate is demo eligible, paper-forward eligible, or ready for discovery from this blocker-fix step.
"""


def next_action_md() -> str:
    return f"""# Intraday Next Action

`{NEXT_ACTION}`

Do not run the next action inside this task. This next action does not authorize intraday strategy backtests, strategy discovery, provider downloads, candidate_exhaustive, paper-forward activation, broker orders, live orders, or real-money recommendations.
"""


def update_metadata(root: Path, output: Path, created_utc: str, manifest: dict[str, Any]) -> tuple[bool, bool]:
    registry_updated = False
    registry_path = root / REGISTRY_PATH
    if registry_path.exists():
        registry = load_yaml(registry_path)
        metadata = registry.setdefault("registry", {})
        metadata.update(
            {
                "intraday_blocker_fix_path": str(output),
                "intraday_blocker_fix_status": "completed",
                "intraday_blocker_fix_created_utc": created_utc,
                "intraday_readiness_verdict_after_fix": READINESS_VERDICT_AFTER_FIX,
                "intraday_readiness_next_action_after_fix": NEXT_ACTION,
                "current_next_action": NEXT_ACTION,
                "next_action": NEXT_ACTION,
                "intraday_cache_contract_created": manifest["intraday_cache_contract_created"],
                "intraday_data_present": manifest["intraday_data_present"],
                "intraday_data_source_approved": manifest["intraday_data_source_approved"],
                "intraday_candidates_demo_eligible": False,
                "blocker_fix_only": True,
                "intraday_strategy_backtests_run": False,
                "new_discovery_run": False,
                "new_performance_metrics_computed": False,
                "provider_download": False,
                "intraday_data_downloaded": False,
                "candidate_exhaustive_run": False,
                "paper_forward_review": False,
                "paper_forward_activation": False,
                "broker_orders_submitted": False,
                "broker_orders_cancelled": False,
                "live_orders": False,
                "broker_path_touched_execution": False,
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
    marker = "## Intraday Readiness Blocker Fix"
    section = f"""## Intraday Readiness Blocker Fix

- Created UTC: `{created_utc}`
- Evidence path: `{output}`
- Blocker-fix-only mode: `true`
- Contracts added: intraday data schema, cache, session timing, fill model, risk engine, kill switch, event logging, and candidate readiness gates.
- Blockers fixed: `{manifest["blockers_fixed_count"]}`
- Blockers partially fixed: `{manifest["blockers_partially_fixed_count"]}`
- Critical blockers remaining: `{manifest["critical_blockers_remaining_count"]}`
- Intraday cache contract created: `{manifest["intraday_cache_contract_created"]}`
- Intraday data present: `{manifest["intraday_data_present"]}`
- Intraday data source approved: `{manifest["intraday_data_source_approved"]}`
- Readiness verdict after fix: `{READINESS_VERDICT_AFTER_FIX}`
- Next action: `{NEXT_ACTION}`
- No intraday backtest, discovery, performance metric, provider download, candidate_exhaustive, paper-forward action, broker order, live order, strategy-rule change, strategy-state change, demo eligibility, or real-money recommendation is authorized.
"""
    updated = base.split(marker, 1)[0].rstrip() + "\n\n" + section if marker in base else base.rstrip() + "\n\n" + section
    roadmap_path.parent.mkdir(parents=True, exist_ok=True)
    roadmap_path.write_text(updated.rstrip() + "\n", encoding="utf-8")
    return registry_updated, True


def consistency_check(
    output: Path,
    manifest: dict[str, Any],
    candidate_status: dict[str, str],
    strategies_before: list[dict[str, Any]],
    strategies_after: list[dict[str, Any]],
) -> dict[str, Any]:
    required_present = {
        name: True if name == "intraday_blocker_fix_consistency_check.json" else (output / name).exists()
        for name in REQUIRED_FILES
    }
    flags_match = all(manifest.get(key) == value for key, value in MANIFEST_FLAGS.items())
    before_state = strategy_state_map(strategies_before)
    after_state = strategy_state_map(strategies_after)
    check = {
        "blocker_fix_only": manifest["blocker_fix_only"] is True,
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
        "no_strategy_state_changes": before_state == after_state,
        "data_schema_contract_exists": required_present["intraday_data_schema_contract.md"],
        "cache_contract_exists": required_present["intraday_cache_contract.md"],
        "session_timing_contract_exists": required_present["intraday_session_timing_contract.md"],
        "fill_model_contract_exists": required_present["intraday_fill_model_contract.md"],
        "risk_engine_contract_exists": required_present["intraday_risk_engine_contract.md"],
        "kill_switch_contract_exists": required_present["intraday_kill_switch_contract.md"],
        "event_logging_contract_exists": required_present["intraday_event_logging_contract.md"],
        "candidate_readiness_gates_exist": required_present["intraday_candidate_readiness_gates.md"],
        "remaining_blockers_table_exists": required_present["intraday_remaining_blockers.csv"],
        "readiness_verdict_after_fix_valid": manifest["readiness_verdict_after_fix"] in VALID_READINESS_VERDICTS,
        "next_action_valid": manifest["next_action"] in VALID_NEXT_ACTIONS,
        "manifest_flags_match_strict_scope": flags_match,
        "candidate_ids_present": tuple(candidate_status) == CANDIDATE_IDS,
        "candidate_statuses_not_demo_ready": all(status == "research_concept_not_ready" for status in candidate_status.values()),
        "all_required_files_present": all(required_present.values()),
    }
    check["consistency_passed"] = all(check.values())
    return check


def create_packet_zip(output: Path) -> Path:
    zip_path = output / "intraday_blocker_fix_packet.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as packet:
        for name in REQUIRED_FILES:
            path = output / name
            if path.exists():
                packet.write(path, arcname=name)
    return zip_path


def run_fix_intraday_readiness_blockers(root: Path = ROOT) -> dict[str, Any]:
    root = Path(root)
    created_utc = now_utc()
    output = clean_output(root)
    strategies_before = strategy_snapshot(root)
    previous = previous_audit_summary(root)
    infrastructure_status, cache_scan = build_infrastructure_status(root)
    candidate_status = evaluate_candidate_readiness(infrastructure_status)
    resolution_rows = blocker_resolution_rows()
    remaining_rows = remaining_blocker_rows()
    fixed_count = sum(1 for row in resolution_rows if row["resolution_status"] == "fixed")
    partially_fixed_count = sum(1 for row in resolution_rows if row["resolution_status"] == "partially_fixed")
    critical_remaining_count = sum(1 for row in remaining_rows if row["severity"] == "critical")

    manifest: dict[str, Any] = {
        "artifact": "fix_intraday_readiness_blockers",
        "created_utc": created_utc,
        "output_dir": str(output),
        "previous_audit": previous,
        **MANIFEST_FLAGS,
        "blockers_fixed_count": fixed_count,
        "blockers_partially_fixed_count": partially_fixed_count,
        "blockers_remaining_count": len(remaining_rows),
        "critical_blockers_remaining_count": critical_remaining_count,
        "intraday_cache_contract_created": True,
        "intraday_data_present": infrastructure_status.intraday_data_present,
        "intraday_data_source_approved": infrastructure_status.intraday_data_source_approved,
        "readiness_verdict_after_fix": READINESS_VERDICT_AFTER_FIX,
        "next_action": NEXT_ACTION,
        "cache_scan": cache_scan,
        "candidate_readiness": candidate_status,
    }

    write_json(output / "intraday_blocker_fix_manifest.json", manifest)
    (output / "intraday_blocker_fix_summary.md").write_text(summary_md(created_utc, output, manifest), encoding="utf-8")
    (output / "intraday_data_schema_contract.md").write_text(data_schema_contract_md(), encoding="utf-8")
    (output / "intraday_cache_contract.md").write_text(cache_contract_md(cache_scan), encoding="utf-8")
    (output / "intraday_session_timing_contract.md").write_text(session_timing_contract_md(), encoding="utf-8")
    (output / "intraday_fill_model_contract.md").write_text(fill_model_contract_md(), encoding="utf-8")
    (output / "intraday_risk_engine_contract.md").write_text(risk_engine_contract_md(), encoding="utf-8")
    (output / "intraday_kill_switch_contract.md").write_text(kill_switch_contract_md(), encoding="utf-8")
    (output / "intraday_event_logging_contract.md").write_text(event_logging_contract_md(), encoding="utf-8")
    (output / "intraday_candidate_readiness_gates.md").write_text(candidate_readiness_gates_md(candidate_status), encoding="utf-8")
    write_csv_rows(
        output / "intraday_blocker_resolution_table.csv",
        resolution_rows,
        ["blocker_id", "severity", "resolution_status", "fix_added", "remaining_gap"],
    )
    write_csv_rows(
        output / "intraday_remaining_blockers.csv",
        remaining_rows,
        ["blocker_id", "severity", "status", "why_remaining", "required_next_step"],
    )
    (output / "intraday_next_action.md").write_text(next_action_md(), encoding="utf-8")

    registry_updated, roadmap_updated = update_metadata(root, output, created_utc, manifest)
    manifest["registry_metadata_updated"] = registry_updated
    manifest["roadmap_updated"] = roadmap_updated
    write_json(output / "intraday_blocker_fix_manifest.json", manifest)

    strategies_after = strategy_snapshot(root)
    check = consistency_check(output, manifest, candidate_status, strategies_before, strategies_after)
    write_json(output / "intraday_blocker_fix_consistency_check.json", check)
    packet_zip = create_packet_zip(output)
    return {
        "output_dir": str(output),
        "packet_zip": str(packet_zip),
        "manifest": manifest,
        "consistency_check": check,
    }


def main() -> None:
    result = run_fix_intraday_readiness_blockers(ROOT)
    check = result["consistency_check"]
    manifest = result["manifest"]
    print(f"intraday blocker fix written: {result['output_dir']}")
    print(f"packet zip: {result['packet_zip']}")
    print(f"readiness verdict after fix: {manifest['readiness_verdict_after_fix']}")
    print(f"next action: {manifest['next_action']}")
    print(f"consistency_passed: {check['consistency_passed']}")
    if not check["consistency_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
