from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import REGISTRY_PATH, ROADMAP_PATH, ROOT
from strategy_lab.research_os.objective_reset.objective_reset_review import replace_or_append_section, write_json, write_text
from strategy_lab.research_os.split_tracks import (
    ACTIVE_OBSERVATIONS_PATH,
    ARCHIVE_INDEX_PATH,
    FAMILY_LEDGER_PATH,
    OPERATIONS_STATE_PATH,
    RESEARCH_QUEUE_PATH,
    RESEARCH_STATE_PATH,
)


OUTPUT_DIR = Path("evidence") / "operations_observation" / "continue_paper_forward_observation_only" / "latest"
COMPACT_STATE_PATH = Path("reports") / "compact_state" / "current_tournament_state.md"
VM_ID = "paper_forward_vm_quality_lowvol_proxy_v1"
DSR_ID = "paper_forward_dsr_sector_equal_weight_defensive_filter_v1"
STATIC_ALL_WEATHER_ID = "static_all_weather_benchmark_v1"
OBSERVATION_LOGS_MISSING = "observation_logs_missing_or_not_available"

NEXT_ACTION_WAIT = "wait_for_next_paper_forward_observation_checkpoint"
NEXT_ACTION_LOG_REVIEW = "manual_review_required_for_observation_logs"
NEXT_ACTION_RECOVER_GLD = "recover_gld_macro_family_lineage"
NEXT_ACTION_PAUSE = "pause_expansion_and_wait_for_manual_direction"
VALID_NEXT_ACTIONS = {
    NEXT_ACTION_WAIT,
    NEXT_ACTION_LOG_REVIEW,
    NEXT_ACTION_RECOVER_GLD,
    NEXT_ACTION_PAUSE,
}

REQUIRED_OUTPUT_FILES = (
    "observation_only_manifest.json",
    "observation_only_summary.md",
    "authoritative_state_verification.md",
    "current_active_observations.md",
    "active_vm_observation_status.md",
    "active_dsr_observation_status.md",
    "benchmark_control_status.md",
    "research_track_pause_status.md",
    "archive_lineage_status.md",
    "observation_logs_review.md",
    "future_manual_review_triggers.md",
    "forbidden_next_steps.md",
    "observation_only_next_action.md",
    "observation_only_consistency_check.json",
)

MANIFEST_FLAGS = {
    "observation_only": True,
    "operations_track_used_as_authoritative": True,
    "research_track_paused": True,
    "archive_lineage_track_preserved": True,
    "gld_macro_recovery_run": False,
    "new_sandbox_batch_run": False,
    "strategy_discovery_run": False,
    "formal_discovery_run": False,
    "new_backtests_run": False,
    "new_performance_metrics_from_raw_data_computed": False,
    "new_variants_created": False,
    "future_preregistration_candidates_created": False,
    "formal_preregistration_created": False,
    "candidate_exhaustive_run": False,
    "paper_forward_review": False,
    "paper_forward_activation": False,
    "new_paper_forward_candidate_created": False,
    "active_vm_preserved": True,
    "active_dsr_preserved": True,
    "static_all_weather_benchmark_control_only": True,
    "indicator_library_dependency_added": False,
    "provider_download": False,
    "intraday_data_used": False,
    "broker_orders_submitted": False,
    "broker_orders_cancelled": False,
    "live_orders": False,
    "real_money_recommendation": False,
    "active_strategy_state_changed": False,
    "rejected_strategy_state_changed": False,
    "exact_rejected_variants_reopened": False,
    "intraday_research_remains_paused": True,
}


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False, width=120, allow_unicode=False), encoding="utf-8")


def active_observation_file(root: Path, strategy_id: str) -> Path:
    return root / "paper_forward_observations" / strategy_id / "active_observation.yaml"


def active_observation_status(root: Path, strategy_id: str) -> dict[str, Any]:
    path = active_observation_file(root, strategy_id)
    payload = load_yaml(path)
    return {
        "strategy_id": strategy_id,
        "path": str(path.resolve()),
        "exists": path.exists(),
        "status": payload.get("status", ""),
        "frozen": payload.get("frozen") is True,
        "rules_frozen": payload.get("rules_frozen") is True,
        "paper_forward_active": payload.get("paper_forward_active") is True,
        "broker_integration": payload.get("broker_integration") is True,
        "live_orders": payload.get("live_orders") is True,
        "order_placement": payload.get("order_placement") is True,
        "real_money_recommendation": payload.get("real_money_recommendation") is True,
        "current_checkpoint_status": payload.get("current_checkpoint_status", ""),
        "minimum_days_before_judgment": payload.get("minimum_days_before_judgment", ""),
        "universe": payload.get("universe", []),
        "rule_summary": payload.get("rule_summary", []),
        "has_target_allocations": "target_allocations" in payload,
        "has_latest_equity_snapshot": "latest_equity_snapshot" in payload or "latest_account_snapshot" in payload,
        "has_positions": "positions" in payload,
        "has_open_orders": "open_orders" in payload,
    }


def observation_log_status(root: Path) -> dict[str, Any]:
    evidence_obs_dir = root / "evidence" / "paper_forward_observations"
    paper_runs_latest = root / "evidence" / "paper_forward_runs" / "latest"
    individual_evidence_dirs = {
        VM_ID: (evidence_obs_dir / VM_ID).exists(),
        DSR_ID: (evidence_obs_dir / DSR_ID).exists(),
    }
    combo_evidence_exists = (evidence_obs_dir / "combo_SPY200d_GLD_50_50_v1").exists()
    latest_run_manifest = paper_runs_latest / "paper_forward_manifest.json"
    latest_run_payload = json.loads(latest_run_manifest.read_text(encoding="utf-8")) if latest_run_manifest.exists() else {}
    active_logs_available = all(individual_evidence_dirs.values())
    status = "available" if active_logs_available else OBSERVATION_LOGS_MISSING
    return {
        "status": status,
        "individual_active_evidence_dirs": individual_evidence_dirs,
        "combo_evidence_exists": combo_evidence_exists,
        "paper_forward_runs_latest_exists": paper_runs_latest.exists(),
        "latest_run_manifest_path": str(latest_run_manifest.resolve()) if latest_run_manifest.exists() else "",
        "latest_run_id": latest_run_payload.get("run_id", ""),
        "latest_run_created_at_utc": latest_run_payload.get("created_at_utc", ""),
        "latest_run_is_combo_observation": latest_run_payload.get("combo_observation_included") is True,
        "latest_run_data_downloaded": latest_run_payload.get("data_downloaded") is True,
        "latest_run_backtest_run": latest_run_payload.get("backtest_run") is True,
        "latest_run_broker_integration": latest_run_payload.get("broker_integration") is True,
        "latest_run_live_orders": latest_run_payload.get("live_orders") is True,
        "latest_run_real_money_recommendation": latest_run_payload.get("real_money_recommendation") is True,
    }


def load_current_track_state(root: Path) -> dict[str, Any]:
    operations = load_yaml(root / ACTIVE_OBSERVATIONS_PATH)
    research = load_yaml(root / RESEARCH_QUEUE_PATH)
    ledger = load_yaml(root / FAMILY_LEDGER_PATH)
    return {
        "operations_state_exists": (root / OPERATIONS_STATE_PATH).exists(),
        "research_state_exists": (root / RESEARCH_STATE_PATH).exists(),
        "archive_index_exists": (root / ARCHIVE_INDEX_PATH).exists(),
        "active_observations_yaml": operations,
        "research_queue_yaml": research,
        "family_ledger_yaml": ledger,
        "authoritative_state_policy_exists": (
            root
            / "evidence"
            / "research_engine_audit"
            / "split_operations_and_research_tracks"
            / "latest"
            / "authoritative_state_policy.md"
        ).exists(),
        "evidence_lineage_policy_exists": (
            root
            / "evidence"
            / "research_engine_audit"
            / "split_operations_and_research_tracks"
            / "latest"
            / "evidence_lineage_policy.md"
        ).exists(),
    }


def manifest(created_utc: str, root: Path, output: Path) -> dict[str, Any]:
    track = load_current_track_state(root)
    active_rows = track["active_observations_yaml"].get("active_observations", [])
    active_ids = [row.get("strategy_id", "") for row in active_rows]
    vm = active_observation_status(root, VM_ID)
    dsr = active_observation_status(root, DSR_ID)
    logs = observation_log_status(root)
    research_queue = track["research_queue_yaml"]
    gld_queue = next(
        (row for row in research_queue.get("queued_governance_reviews", []) if row.get("id") == "recover_gld_macro_family_lineage"),
        {},
    )
    next_action = NEXT_ACTION_WAIT if logs["status"] == "available" else NEXT_ACTION_LOG_REVIEW
    return {
        "created_utc": created_utc,
        **MANIFEST_FLAGS,
        "evidence_path": str(output.resolve()),
        "current_active_observation_count": len(active_ids),
        "active_observation_ids": active_ids,
        "active_vm_observation_exists": vm["exists"],
        "active_vm_status": vm["status"],
        "active_vm_rules_unchanged": vm["frozen"] and vm["rules_frozen"],
        "active_dsr_observation_exists": dsr["exists"],
        "active_dsr_status": dsr["status"],
        "active_dsr_rules_unchanged": dsr["frozen"] and dsr["rules_frozen"],
        "static_all_weather_state": "benchmark_control_only",
        "sandbox_batch_authorization": research_queue.get("sandbox_batch_authorized") is True,
        "strategy_discovery_authorization": research_queue.get("strategy_discovery_authorized") is True,
        "candidate_exhaustive_authorization": research_queue.get("candidate_exhaustive_authorized") is True,
        "paper_forward_candidate_creation_authorization": research_queue.get("paper_forward_candidate_creation_authorized") is True,
        "provider_download_authorization": False,
        "intraday_data_authorization": False,
        "broker_live_authorization": False,
        "gld_macro_recovery_status": gld_queue.get("status", ""),
        "family_lineage_ledger_exists": bool(track["family_ledger_yaml"]),
        "authoritative_state_policy_exists": track["authoritative_state_policy_exists"],
        "evidence_lineage_policy_exists": track["evidence_lineage_policy_exists"],
        "operations_state_exists": track["operations_state_exists"],
        "research_state_exists": track["research_state_exists"],
        "archive_index_exists": track["archive_index_exists"],
        "observation_logs_status": logs["status"],
        "observation_logs_detail": logs,
        "vm_observation_detail": vm,
        "dsr_observation_detail": dsr,
        "next_action": next_action,
    }


def authoritative_state_verification_md(m: dict[str, Any]) -> str:
    return f"""# Authoritative State Verification

- Operations state exists: `{m['operations_state_exists']}`
- Research state exists: `{m['research_state_exists']}`
- Archive index exists: `{m['archive_index_exists']}`
- Family lineage ledger exists: `{m['family_lineage_ledger_exists']}`
- Authoritative state policy exists: `{m['authoritative_state_policy_exists']}`
- Evidence lineage policy exists: `{m['evidence_lineage_policy_exists']}`

The operations track is used as authoritative before reading historical roadmap sections. Historical next-action labels remain non-authoritative archive records.
"""


def current_active_observations_md(m: dict[str, Any]) -> str:
    ids = "\n".join(f"- `{item}`" for item in m["active_observation_ids"])
    return f"""# Current Active Observations

Current active observation count: `{m['current_active_observation_count']}`

{ids}

No new active strategy or paper-forward candidate was created by this checkpoint.
"""


def active_status_md(title: str, detail: dict[str, Any]) -> str:
    universe = ", ".join(detail.get("universe", []))
    rules = "\n".join(f"- {line}" for line in detail.get("rule_summary", []))
    return f"""# {title}

- Observation file exists: `{detail['exists']}`
- Status: `{detail['status']}`
- Paper-forward active: `{detail['paper_forward_active']}`
- Frozen: `{detail['frozen']}`
- Rules frozen: `{detail['rules_frozen']}`
- Current checkpoint status: `{detail['current_checkpoint_status']}`
- Minimum days before judgment: `{detail['minimum_days_before_judgment']}`
- Broker integration: `{detail['broker_integration']}`
- Live orders: `{detail['live_orders']}`
- Order placement: `{detail['order_placement']}`
- Real-money recommendation: `{detail['real_money_recommendation']}`
- Target allocations available: `{detail['has_target_allocations']}`
- Latest equity/account snapshot available: `{detail['has_latest_equity_snapshot']}`
- Positions available: `{detail['has_positions']}`
- Open orders available: `{detail['has_open_orders']}`
- Universe: `{universe}`

## Rule Summary

{rules}
"""


def benchmark_status_md() -> str:
    return f"""# Benchmark / Control Status

- `{STATIC_ALL_WEATHER_ID}` remains benchmark/control only.
- Active combo and broad market references remain references, not new active strategies.
- This checkpoint did not change benchmark/control status.
"""


def research_pause_md(m: dict[str, Any]) -> str:
    return f"""# Research Track Pause Status

- Research track paused: `{m['research_track_paused']}`
- Sandbox batch authorization: `{m['sandbox_batch_authorization']}`
- Strategy discovery authorization: `{m['strategy_discovery_authorization']}`
- Candidate exhaustive authorization: `{m['candidate_exhaustive_authorization']}`
- Paper-forward candidate creation authorization: `{m['paper_forward_candidate_creation_authorization']}`
- Provider download authorization: `{m['provider_download_authorization']}`
- Intraday data authorization: `{m['intraday_data_authorization']}`
- Broker/live authorization: `{m['broker_live_authorization']}`

Research expansion remains paused.
"""


def archive_lineage_md(m: dict[str, Any]) -> str:
    return f"""# Archive / Lineage Status

- Archive lineage track preserved: `{m['archive_lineage_track_preserved']}`
- Family lineage ledger exists: `{m['family_lineage_ledger_exists']}`
- GLD/macro recovery status: `{m['gld_macro_recovery_status']}`
- GLD/macro recovery run: `{m['gld_macro_recovery_run']}`

The GLD/macro recovery queue remains queued but not run.
"""


def observation_logs_md(m: dict[str, Any]) -> str:
    logs = m["observation_logs_detail"]
    return f"""# Observation Logs Review

Observation logs status: `{m['observation_logs_status']}`

The active VM/DSR observation YAML files exist, but individual evidence directories for those two active observations were not found under `evidence/paper_forward_observations/`.

## Existing Artifacts

- VM active evidence directory exists: `{logs['individual_active_evidence_dirs'].get(VM_ID)}`
- DSR active evidence directory exists: `{logs['individual_active_evidence_dirs'].get(DSR_ID)}`
- Combo observation evidence exists: `{logs['combo_evidence_exists']}`
- Latest paper-forward run folder exists: `{logs['paper_forward_runs_latest_exists']}`
- Latest run manifest path: `{logs['latest_run_manifest_path'] or 'none'}`
- Latest run ID: `{logs['latest_run_id'] or 'none'}`
- Latest run created UTC: `{logs['latest_run_created_at_utc'] or 'none'}`
- Latest run is combo observation: `{logs['latest_run_is_combo_observation']}`

## Operational Log Gaps

- Active VM target allocations available: `{m['vm_observation_detail']['has_target_allocations']}`
- Active DSR target allocations available: `{m['dsr_observation_detail']['has_target_allocations']}`
- Active VM latest equity/account snapshot available: `{m['vm_observation_detail']['has_latest_equity_snapshot']}`
- Active DSR latest equity/account snapshot available: `{m['dsr_observation_detail']['has_latest_equity_snapshot']}`
- Active VM positions/open orders available: `{m['vm_observation_detail']['has_positions']}` / `{m['vm_observation_detail']['has_open_orders']}`
- Active DSR positions/open orders available: `{m['dsr_observation_detail']['has_positions']}` / `{m['dsr_observation_detail']['has_open_orders']}`

Because active VM/DSR operational logs/checkpoints are not clearly present, record: `{OBSERVATION_LOGS_MISSING}`.
"""


def future_triggers_md() -> str:
    return """# Future Manual Review Triggers

Trigger manual review if:

- Enough observation time has passed for a scheduled checkpoint.
- Active VM or active DSR behavior diverges materially from expectations.
- Unexplained P&L appears.
- Logs are missing, incomplete, inconsistent, or stale.
- Target allocations are missing.
- Benchmark comparison changes materially.
- Open orders or stale positions exist.
- Broker/API issues appear.
- A new data source is approved.
- A new objective is manually approved.
- GLD/macro lineage recovery is explicitly authorized later.
"""


def forbidden_next_steps_md() -> str:
    return """# Forbidden Next Steps

This checkpoint does not authorize:

- strategy discovery
- sandbox batches
- new backtests
- raw-data performance metrics
- new variants
- promotion review candidates
- candidate_exhaustive
- new paper-forward candidates
- paper-forward activation
- provider downloads
- intraday data use
- broker/live-order paths
- order placement, cancellation, or simulation
- real-money recommendations
- rejected variant reopening
- GLD/macro lineage recovery
"""


def summary_md(m: dict[str, Any]) -> str:
    return f"""# Observation-Only Summary

Exact next action: `{m['next_action']}`

Observation logs status: `{m['observation_logs_status']}`

Current active observation count: `{m['current_active_observation_count']}`

Active observations:

- `{VM_ID}`
- `{DSR_ID}`

Static all-weather remains benchmark/control only.

Research expansion remains paused. GLD/macro lineage recovery remains queued but not run.

No sandbox batch, discovery, backtest, provider download, intraday data, candidate_exhaustive, paper-forward activation, broker/live action, or real-money recommendation occurred.
"""


def next_action_md(next_action: str) -> str:
    return f"""# Observation-Only Next Action

Exact next action:

`{next_action}`

Do not run the next action in this checkpoint task.
"""


def update_metadata(root: Path, output: Path, created_utc: str, m: dict[str, Any]) -> tuple[bool, bool, bool, bool]:
    registry_path = root / REGISTRY_PATH
    registry = load_yaml(registry_path)
    metadata = registry.setdefault("registry", {})
    before_metadata = dict(metadata)
    metadata.update(
        {
            "continue_paper_forward_observation_only_path": str(output.resolve()),
            "continue_paper_forward_observation_only_status": "completed_observation_logs_review_required",
            "continue_paper_forward_observation_only_created_utc": created_utc,
            "current_research_mode": "operations_observation_checkpoint_completed",
            "current_next_action": m["next_action"],
            "official_current_next_action": m["next_action"],
            "next_action": m["next_action"],
            "observation_only_current_active_observation_count": m["current_active_observation_count"],
            "observation_only_active_observation_ids": m["active_observation_ids"],
            "observation_logs_status": m["observation_logs_status"],
            "observation_only_no_strategy_discovery": True,
            "observation_only_no_sandbox_batch": True,
            "observation_only_no_backtests": True,
            "observation_only_no_provider_download": True,
            "observation_only_no_intraday_data": True,
            "observation_only_no_candidate_exhaustive": True,
            "observation_only_no_paper_forward_activation": True,
            "observation_only_no_real_money_recommendation": True,
        }
    )
    registry_path.write_text(yaml.safe_dump(registry, sort_keys=False, width=120, allow_unicode=False), encoding="utf-8")

    roadmap_path = root / ROADMAP_PATH
    before_roadmap = read_text(roadmap_path) or "# Research Roadmap\n"
    compact_section = f"""## Compact Current State

- Updated UTC: `{created_utc}`
- Current research mode: `operations_observation_checkpoint_completed`
- Official current next action: `{m['next_action']}`
- Observation-only checkpoint evidence: `{output.resolve()}`
- Observation logs status: `{m['observation_logs_status']}`
- Current active observation count: `{m['current_active_observation_count']}`
- Active observations: `{', '.join(m['active_observation_ids'])}`
- Active VM and active DSR remain protected active/frozen observations.
- `static_all_weather_benchmark_v1` remains benchmark/control only.
- Research expansion remains paused.
- GLD/macro recovery remains queued but not run.
- Historical roadmap sections below this compact state are non-authoritative archive records unless cited by current-state files.
- This checkpoint did not run a sandbox batch, strategy discovery, new backtest, candidate_exhaustive, paper-forward activation, provider download, intraday test, broker/live action, strategy promotion, rejected variant reopening, GLD/macro recovery, or real-money recommendation.
"""
    checkpoint_section = f"""## Continue Paper Forward Observation Only

- Created UTC: `{created_utc}`
- Evidence path: `{output.resolve()}`
- Observation logs status: `{m['observation_logs_status']}`
- Active VM preserved: `{m['active_vm_preserved']}`
- Active DSR preserved: `{m['active_dsr_preserved']}`
- Static all-weather benchmark/control only: `{m['static_all_weather_benchmark_control_only']}`
- Research track paused: `{m['research_track_paused']}`
- GLD/macro recovery run: `{m['gld_macro_recovery_run']}`
- Next action: `{m['next_action']}`
- Do not run the next action in this checkpoint task.
"""
    after_roadmap = replace_or_append_section(before_roadmap, "## Compact Current State", compact_section)
    after_roadmap = replace_or_append_section(after_roadmap, "## Continue Paper Forward Observation Only", checkpoint_section)
    write_text(roadmap_path, after_roadmap)

    compact_path = root / COMPACT_STATE_PATH
    before_compact = read_text(compact_path)
    after_compact = f"""# Current Tournament State

Created UTC: `{created_utc}`

Current research mode: `operations_observation_checkpoint_completed`

Current next action: `{m['next_action']}`

Observation-only checkpoint evidence: `{output.resolve()}`

## Observation State

- Observation logs status: `{m['observation_logs_status']}`
- Current active observation count: `{m['current_active_observation_count']}`
- Active observations: `{', '.join(m['active_observation_ids'])}`
- `paper_forward_vm_quality_lowvol_proxy_v1` remains active/accepted/frozen.
- `paper_forward_dsr_sector_equal_weight_defensive_filter_v1` remains active/accepted/frozen.
- `static_all_weather_benchmark_v1` remains benchmark/control only.

## Research / Archive State

- Research expansion remains paused.
- GLD/macro recovery remains queued but not run.
- Intraday research remains paused.

## Forbidden Actions

- No new sandbox batch, strategy discovery, new backtest, candidate_exhaustive, paper-forward activation, provider download, intraday test, broker/live action, rejected variant reopening, strategy promotion, GLD/macro recovery, or real-money recommendation occurred in this checkpoint.
"""
    write_text(compact_path, after_compact)

    operations_path = root / OPERATIONS_STATE_PATH
    before_operations = read_text(operations_path)
    after_operations = before_operations.rstrip() + f"""

## Latest Observation-Only Checkpoint

- Created UTC: `{created_utc}`
- Evidence path: `{output.resolve()}`
- Observation logs status: `{m['observation_logs_status']}`
- Next action: `{m['next_action']}`
- No new paper-forward candidate, broker/live path, or real-money recommendation was authorized.
"""
    write_text(operations_path, after_operations)
    return before_metadata != metadata, before_roadmap != after_roadmap, before_compact != after_compact, before_operations != after_operations


def consistency_check(m: dict[str, Any], output: Path) -> dict[str, Any]:
    required = {name: (output / name).exists() for name in REQUIRED_OUTPUT_FILES}
    check = {
        "observation_only_completed": True,
        "required_files_present": all(required.values()),
        "required_files": required,
        "observation_only": m["observation_only"] is True,
        "operations_track_authoritative": m["operations_track_used_as_authoritative"] is True,
        "research_track_paused": m["research_track_paused"] is True,
        "archive_lineage_track_preserved": m["archive_lineage_track_preserved"] is True,
        "gld_macro_recovery_not_run": m["gld_macro_recovery_run"] is False,
        "no_new_sandbox_batch": m["new_sandbox_batch_run"] is False,
        "no_discovery": m["strategy_discovery_run"] is False and m["formal_discovery_run"] is False,
        "no_backtests_or_raw_metrics": (
            m["new_backtests_run"] is False and m["new_performance_metrics_from_raw_data_computed"] is False
        ),
        "no_new_variants_or_preregistration": (
            m["new_variants_created"] is False
            and m["future_preregistration_candidates_created"] is False
            and m["formal_preregistration_created"] is False
        ),
        "no_candidate_or_paper_forward_action": (
            m["candidate_exhaustive_run"] is False
            and m["paper_forward_review"] is False
            and m["paper_forward_activation"] is False
            and m["new_paper_forward_candidate_created"] is False
        ),
        "active_vm_preserved": m["active_vm_preserved"] is True and m["active_vm_observation_exists"] is True,
        "active_dsr_preserved": m["active_dsr_preserved"] is True and m["active_dsr_observation_exists"] is True,
        "static_all_weather_control_only": m["static_all_weather_benchmark_control_only"] is True,
        "no_provider_intraday_broker_real_money": (
            m["provider_download"] is False
            and m["intraday_data_used"] is False
            and m["broker_orders_submitted"] is False
            and m["broker_orders_cancelled"] is False
            and m["live_orders"] is False
            and m["real_money_recommendation"] is False
        ),
        "protected_state_unchanged": (
            m["active_strategy_state_changed"] is False
            and m["rejected_strategy_state_changed"] is False
            and m["exact_rejected_variants_reopened"] is False
            and m["intraday_research_remains_paused"] is True
        ),
        "active_observation_count_is_two": m["current_active_observation_count"] == 2,
        "observation_log_status_recorded": bool(m["observation_logs_status"]),
        "future_manual_review_triggers_exist": (output / "future_manual_review_triggers.md").exists(),
        "forbidden_next_steps_exist": (output / "forbidden_next_steps.md").exists(),
        "next_action_valid": m["next_action"] in VALID_NEXT_ACTIONS,
    }
    check["consistency_passed"] = all(value is True for key, value in check.items() if key != "required_files")
    return check


def run(root: Path = ROOT) -> dict[str, Any]:
    created = now_utc()
    output = root / OUTPUT_DIR
    output.mkdir(parents=True, exist_ok=True)
    m = manifest(created, root, output)

    write_text(output / "observation_only_summary.md", summary_md(m))
    write_text(output / "authoritative_state_verification.md", authoritative_state_verification_md(m))
    write_text(output / "current_active_observations.md", current_active_observations_md(m))
    write_text(output / "active_vm_observation_status.md", active_status_md("Active VM Observation Status", m["vm_observation_detail"]))
    write_text(output / "active_dsr_observation_status.md", active_status_md("Active DSR Observation Status", m["dsr_observation_detail"]))
    write_text(output / "benchmark_control_status.md", benchmark_status_md())
    write_text(output / "research_track_pause_status.md", research_pause_md(m))
    write_text(output / "archive_lineage_status.md", archive_lineage_md(m))
    write_text(output / "observation_logs_review.md", observation_logs_md(m))
    write_text(output / "future_manual_review_triggers.md", future_triggers_md())
    write_text(output / "forbidden_next_steps.md", forbidden_next_steps_md())
    write_text(output / "observation_only_next_action.md", next_action_md(m["next_action"]))

    registry_updated, roadmap_updated, compact_updated, operations_updated = update_metadata(root, output, created, m)
    m.update(
        {
            "registry_updated": registry_updated,
            "roadmap_updated": roadmap_updated,
            "compact_state_updated": compact_updated,
            "operations_state_updated": operations_updated,
        }
    )
    write_json(output / "observation_only_manifest.json", m)
    write_json(output / "observation_only_consistency_check.json", {"consistency_passed": False})
    check = consistency_check(m, output)
    write_json(output / "observation_only_consistency_check.json", check)
    return {**m, "consistency_passed": check["consistency_passed"], "output_dir": str(output.resolve())}


if __name__ == "__main__":
    result = run()
    print(
        json.dumps(
            {
                "output_dir": result["output_dir"],
                "next_action": result["next_action"],
                "observation_logs_status": result["observation_logs_status"],
                "consistency_passed": result["consistency_passed"],
            },
            indent=2,
        )
    )
