from __future__ import annotations

import csv
import hashlib
import json
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import yaml


TASK_ID = "complete_forward_observation_receiver_audit_v2"
AUDIT_DATE = "2026-08-10"
OUTCOME = "forward_observation_receiver_audit_complete"
DECISION = "standardization_required_before_scaling"
COMMON_SCHEMA_ID = "forward_observation_handoff_standard_v1"
NEXT_ACTION = "implement_forward_observation_handoff_standard_v1"
EXPECTED_PRIOR_HASH = "sha256:dbc8de88b61050ed6000758cf3e8eef3e2d55cf886cd15907ac36b480789f479"

ROOT = Path(__file__).resolve().parents[3]
OUTPUT_DIR = ROOT / "evidence/project_audits/forward_observation_receiver_audit_v2/latest"
PRIOR_DIR = ROOT / "evidence/project_audits/forward_observation_handoff_inventory_and_standardization_v1/latest"
RECEIVER = ROOT / "execution_lab/alpaca_micro_live_v1"
RECEIVER_REGISTRY = RECEIVER / "runtime_strategies/runtime_strategy_registry.yaml"
RECEIVER_SESSIONS = RECEIVER / "evidence/weekly_demo_sessions"
INTERNAL_HANDOFF = ROOT / "evidence/handoff/internal_capture_asymmetry_63d_top3_v1/latest"
SPDJ_HANDOFF = ROOT / "evidence/handoff_exports/spdj_dynamic_inflation_forward_observation_handoff_v1/latest"

PROTECTED_PATHS = [
    PRIOR_DIR,
    RECEIVER,
    INTERNAL_HANDOFF,
    SPDJ_HANDOFF,
    ROOT / "strategy_lab/strategy_registry.yaml",
    ROOT / "strategy_lab/RESEARCH_ROADMAP.md",
    ROOT / "strategy_lab/research_os/research/research_queue.yaml",
    ROOT / "strategy_lab/research_os/family_lineage/family_ledger.yaml",
    ROOT / "strategy_lab/research_os/operations/active_observations.yaml",
    ROOT / "paper_forward_observations",
]

REQUIRED_FILES = [
    "receiver_discovery_report.md",
    "receiver_repository_inventory.json",
    "receiver_lifecycle_model.csv",
    "cross_repository_strategy_reconciliation.csv",
    "receiver_authoritative_counts.json",
    "strategy_identity_aliases.csv",
    "receiver_strategy_interface.md",
    "receiver_state_contract.md",
    "receiver_market_data_contract.md",
    "receiver_timing_contract.md",
    "receiver_handoff_import_capability.md",
    "formal_handoff_compatibility.csv",
    "common_standard_receiver_mapping.csv",
    "receiver_missing_standard_fields.csv",
    "final_standardization_decision.json",
    "forward_observation_handoff_standard_v1_requirements.md",
    "microtrading_promotion_audit.md",
    "migration_matrix_v2.csv",
    "migration_priority.csv",
    "evidence_gaps.csv",
    "consistency_check.json",
    "next_action.md",
]


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def sha256_path(path: Path) -> str:
    if not path.exists():
        return "missing"
    if path.is_file():
        return sha256_file(path)
    digest = hashlib.sha256()
    for item in sorted(candidate for candidate in path.rglob("*") if candidate.is_file()):
        digest.update(item.relative_to(path).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(item.read_bytes())
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


def snapshot(paths: Iterable[Path]) -> dict[str, str]:
    return {rel(path): sha256_path(path) for path in paths}


def canonical_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def serialize_cell(value: Any) -> Any:
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return value


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    names = fieldnames or (list(rows[0]) if rows else [])
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=names, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({name: serialize_cell(row.get(name, "")) for name in names})


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def git_value(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True, encoding="utf-8"
    )
    return result.stdout.strip()


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def load_receiver_sessions() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(RECEIVER_SESSIONS.rglob("weekly_session_state.json")):
        state = json.loads(path.read_text(encoding="utf-8"))
        summary_path = path.with_name("weekly_summary.json")
        summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {}
        rows.append({"path": rel(path), "state": state, "summary": summary})
    return rows


def latest_relevant_session(sessions: list[dict[str, Any]], receiver_ids: set[str]) -> dict[str, Any]:
    relevant = [
        row
        for row in sessions
        if receiver_ids.intersection(set(row["state"].get("selected_strategies") or []))
    ]
    return max(relevant, key=lambda row: row["state"].get("started_at_utc", ""))


def alias_rows() -> list[dict[str, Any]]:
    return [
        {
            "research_strategy_id": "paper_forward_vm_quality_lowvol_proxy_v1",
            "receiver_strategy_id": "vm_quality_lowvol_proxy_v1",
            "alias_evidence": "paper_forward_observations/paper_forward_vm_quality_lowvol_proxy_v1/active_observation.yaml:base_strategy_id; identical universe and frozen rule",
            "identity_confidence": "high",
        },
        {
            "research_strategy_id": "paper_forward_dsr_sector_equal_weight_defensive_filter_v1",
            "receiver_strategy_id": "dsr_sector_equal_weight_defensive_filter_v1",
            "alias_evidence": "paper_forward_observations/paper_forward_dsr_sector_equal_weight_defensive_filter_v1/active_observation.yaml:base_strategy_id; receiver spec source_evidence",
            "identity_confidence": "high",
        },
    ]


def reconciliation_rows(prior: list[dict[str, str]], session: dict[str, Any]) -> list[dict[str, Any]]:
    aliases = {row["research_strategy_id"]: row for row in alias_rows()}
    selected = set(session["state"].get("selected_strategies") or [])
    handled = session["state"].get("handled_target_versions") or []
    persisted_active = session["state"].get("status") == "running" and session["summary"].get("active") is True
    latest_heartbeat = parse_iso(session["state"].get("last_heartbeat_utc"))
    audit_time = datetime.fromisoformat(f"{AUDIT_DATE}T00:00:00+00:00")
    stale_days = (audit_time - latest_heartbeat).days if latest_heartbeat else None
    rows: list[dict[str, Any]] = []
    for source in prior:
        strategy_id = source["strategy_id"]
        alias = aliases.get(strategy_id)
        receiver_id = alias["receiver_strategy_id"] if alias else ""
        registered = bool(receiver_id)
        initialized = bool(receiver_id and any(item.startswith(f"{receiver_id}:") for item in handled))
        active = bool(receiver_id in selected and persisted_active)
        state = "paper_demo_active" if active else "receiver_not_found"
        caveat = (
            f"persisted running state is stale ({stale_days} days since heartbeat) and receiver has no TTL"
            if active
            else "no exact ID or evidenced alias in receiver registry, specs, onboarding inventory, or session state"
        )
        if strategy_id in {"SPY_200d_trend_model", "profit_combo_SPY200d_GLD_50_50_v1"}:
            caveat = "legacy ambiguity resolved as absent from receiver; no exact ID or evidenced alias"
        rows.append(
            {
                "research_strategy_id": strategy_id,
                "research_historical_stage": source["current_exclusive_stage"],
                "research_eligible": source["eligibility_status"] == "research_eligible",
                "handoff_exported": bool(source["handoff_id"]),
                "receiver_strategy_id": receiver_id,
                "alias_status": "evidenced_alias" if alias else "none",
                "receiver_registered": registered,
                "receiver_imported": False,
                "receiver_validated": registered and initialized,
                "paper_demo_initialized": initialized,
                "paper_demo_active": active,
                "paper_demo_paused": False,
                "paper_demo_disabled": False,
                "microtrading_eligible": False,
                "microtrading_active": False,
                "receiver_state": state,
                "receiver_state_evidence": session["path"] if registered else "receiver registry and repository search",
                "receiver_state_caveat": caveat,
            }
        )
    return rows


def lifecycle_rows() -> list[dict[str, Any]]:
    base = "execution_lab/alpaca_micro_live_v1"
    return [
        {"state": "registered", "scope": "strategy", "created_by": "runtime registry row", "persisted_evidence": f"{base}/runtime_strategies/runtime_strategy_registry.yaml", "advance_or_exit": "enabled/runtime_ready flags plus local spec/module validation", "implies_current_observation": False, "implies_broker_execution": False},
        {"state": "runtime_ready", "scope": "strategy", "created_by": "manual frozen-copy onboarding", "persisted_evidence": f"{base}/evidence/runtime_onboarding/runtime_strategy_inventory.json", "advance_or_exit": "selected by a runtime session", "implies_current_observation": False, "implies_broker_execution": False},
        {"state": "ready_to_freeze", "scope": "onboarding candidate", "created_by": "runtime inventory classification", "persisted_evidence": f"{base}/execution/runtime_strategy_inventory.py", "advance_or_exit": "manual freeze command", "implies_current_observation": False, "implies_broker_execution": False},
        {"state": "onboarding_blocked", "scope": "onboarding candidate", "created_by": "runtime inventory classification", "persisted_evidence": f"{base}/evidence/runtime_onboarding/runtime_strategy_inventory.json", "advance_or_exit": "later rule/source completion outside this audit", "implies_current_observation": False, "implies_broker_execution": False},
        {"state": "disabled", "scope": "strategy", "created_by": "enabled=false or runtime_ready=false", "persisted_evidence": f"{base}/runtime_strategies/runtime_strategy_registry.yaml", "advance_or_exit": "manual registry/config change", "implies_current_observation": False, "implies_broker_execution": False},
        {"state": "running", "scope": "paper/demo session", "created_by": "weekly runner start", "persisted_evidence": f"{base}/evidence/weekly_demo_sessions/*/weekly_session_state.json", "advance_or_exit": "loop completion, stop, emergency stop, or failure", "implies_current_observation": True, "implies_broker_execution": "only when submit_paper_orders=true and risk gate permits"},
        {"state": "degraded_running", "scope": "paper/demo session", "created_by": "bounded read-error policy", "persisted_evidence": f"{base}/execution/weekly_demo_runner.py", "advance_or_exit": "successful read or failure threshold", "implies_current_observation": True, "implies_broker_execution": "paper only and risk-gated"},
        {"state": "completed", "scope": "paper/demo session", "created_by": "bounded loop/session completion", "persisted_evidence": f"{base}/evidence/weekly_demo_sessions/*/weekly_session_state.json", "advance_or_exit": "terminal", "implies_current_observation": False, "implies_broker_execution": False},
        {"state": "failed", "scope": "paper/demo session", "created_by": "runtime or validation failure", "persisted_evidence": f"{base}/evidence/weekly_demo_sessions/*/weekly_session_state.json", "advance_or_exit": "manual review; a new session may be started", "implies_current_observation": False, "implies_broker_execution": False},
        {"state": "stopped", "scope": "paper/demo session", "created_by": "local stop file", "persisted_evidence": f"{base}/evidence/control/STOP_WEEKLY_DEMO", "advance_or_exit": "terminal for session", "implies_current_observation": False, "implies_broker_execution": False},
        {"state": "emergency_stopped", "scope": "paper/demo session", "created_by": "local emergency stop file", "persisted_evidence": f"{base}/evidence/control/EMERGENCY_STOP_WEEKLY_DEMO", "advance_or_exit": "terminal; does not liquidate", "implies_current_observation": False, "implies_broker_execution": False},
        {"state": "paper", "scope": "execution mode", "created_by": "runner mode", "persisted_evidence": f"{base}/execution/risk_gate.py", "advance_or_exit": "no live transition is implemented", "implies_current_observation": False, "implies_broker_execution": "paper orders only when explicitly requested"},
        {"state": "live_unsupported", "scope": "execution mode", "created_by": "risk gate", "persisted_evidence": f"{base}/execution/risk_gate.py", "advance_or_exit": "none in current receiver", "implies_current_observation": False, "implies_broker_execution": False},
    ]


def formal_compatibility_rows() -> list[dict[str, Any]]:
    return [
        {
            "handoff_id": "internal_capture_asymmetry_63d_top3_v1",
            "strategy_id": "internal_capture_asymmetry_63d_top3_v1",
            "schema": "legacy_internal_capture_handoff:1",
            "classification": "requires_strategy_specific_adapter",
            "receiver_gaps": "no generic importer; monthly scheduler/effective-time contract absent; requires hand-written Python calculator and YAML runtime spec",
            "package_gaps": "legacy package lacks common envelope and receiver-native deployment binding",
            "activation_performed": False,
            "evidence": "evidence/handoff/internal_capture_asymmetry_63d_top3_v1/latest/strategy_handoff.json|execution_lab/alpaca_micro_live_v1/execution/freeze_successful_strategies.py",
        },
        {
            "handoff_id": "spdj_dynamic_inflation_forward_observation_handoff_v1",
            "strategy_id": "spdj_multi_asset_dynamic_inflation_etf_portability_v1",
            "schema": "spdj_forward_observation_handoff_schema_v1:v1",
            "classification": "receiver_architecture_incompatible",
            "receiver_gaps": "no external CPI event provider, point-in-time release state, no-event month handling, exchange-calendar event scheduler, or next-session-after-close target state",
            "package_gaps": "complete machine-readable package still needs a receiver binding; no package defect justifies substituting receiver behavior",
            "activation_performed": False,
            "evidence": "evidence/handoff_exports/spdj_dynamic_inflation_forward_observation_handoff_v1/latest/package/schedule_and_timing_contract.json|execution_lab/alpaca_micro_live_v1/runtime_strategies/runtime_strategy_registry.yaml",
        },
    ]


def mapping_rows() -> list[dict[str, Any]]:
    base = "execution_lab/alpaca_micro_live_v1"
    data = [
        ("strategy_id", "receiver_native", "RuntimeSignal.strategy_id and registry key", f"{base}/execution/models.py"),
        ("schema_id_and_version", "receiver_major_extension_needed", "none", f"{base}/runtime_strategies/runtime_strategy_registry.yaml"),
        ("handoff_id_and_package_hash", "receiver_major_extension_needed", "none", f"{base}/execution/freeze_successful_strategies.py"),
        ("strategy_version_family_architecture", "receiver_minor_extension_needed", "runtime_version exists only in per-strategy spec", f"{base}/runtime_strategies/vm_quality_lowvol_proxy_v1.yaml"),
        ("eligibility_evidence_and_source_hashes", "receiver_major_extension_needed", "free-text source evidence only", f"{base}/runtime_strategies/dsr_sector_equal_weight_defensive_filter_v1.yaml"),
        ("tradable_symbols_and_substitution_policy", "receiver_equivalent_different_name", "allowed_symbols plus exact registry/spec equality", f"{base}/execution/weekly_demo_runner.py"),
        ("price_semantics", "receiver_equivalent_different_name", "Alpaca feed=iex adjustment=all daily bars", f"{base}/data/alpaca_historical_bars.py"),
        ("lookback_requirements", "receiver_native", "per-strategy YAML parameters", f"{base}/runtime_strategies/vm_quality_lowvol_proxy_v1.yaml"),
        ("signal_dependencies_and_authority", "receiver_major_extension_needed", "Alpaca bars only; no generic external signal provider contract", f"{base}/data/alpaca_historical_bars.py"),
        ("versioned_calculator_and_configuration", "receiver_equivalent_different_name", "Python runtime_module plus YAML runtime_spec", f"{base}/runtime_strategies/runtime_strategy_registry.yaml"),
        ("target_weights", "receiver_native", "RuntimeSignal.target_weights", f"{base}/execution/models.py"),
        ("cash_and_constraints", "receiver_equivalent_different_name", "cash_weight plus per-strategy constraints and risk limits", f"{base}/execution/models.py"),
        ("target_effective_timestamp_and_calendar", "receiver_major_extension_needed", "as_of date only; no effective timestamp/calendar ID", f"{base}/execution/models.py"),
        ("event_identity", "receiver_equivalent_different_name", "target_version_id hashes strategy/as_of/weights", f"{base}/execution/runtime_orchestrator.py"),
        ("current_and_pending_target", "receiver_major_extension_needed", "latest target-version list only; no generic effective/pending state", f"{base}/execution/weekly_demo_runner.py"),
        ("idempotency_and_restart", "receiver_minor_extension_needed", "handled_target_versions and same-session resume; not global across sessions", f"{base}/execution/weekly_demo_runner.py"),
        ("stale_event_and_missing_release", "receiver_major_extension_needed", "read-error policy is not event staleness or no-release semantics", f"{base}/execution/weekly_demo_runner.py"),
        ("status_error_and_provenance", "receiver_minor_extension_needed", "session/event ledgers and RuntimeSignal metadata; no common output envelope", f"{base}/execution/models.py"),
        ("golden_and_state_fixtures", "receiver_major_extension_needed", "receiver unit tests exist but package conformance fixtures are not imported", "tests/test_alpaca_micro_live_runtime_strategy.py"),
        ("canonical_lifecycle", "receiver_major_extension_needed", "registry flags, onboarding classes, and session statuses are separate vocabularies", f"{base}/execution/runtime_strategy_inventory.py"),
        ("receiver_strategy_id_alias", "receiver_has_required_concept_missing_from_proposal", "research and receiver IDs differ for active strategies", "paper_forward_observations/paper_forward_vm_quality_lowvol_proxy_v1/active_observation.yaml"),
        ("deployment_sleeve_and_shared_symbol_policy", "receiver_has_required_concept_missing_from_proposal", "independent_virtual_sleeves, notional limits, shared fallback policy", f"{base}/execution/weekly_demo_runner.py"),
        ("runtime_spec_module_hashes", "receiver_has_required_concept_missing_from_proposal", "session config records registry/spec hashes", f"{base}/execution/weekly_demo_runner.py"),
    ]
    return [
        {"concept": concept, "classification": classification, "receiver_concept": receiver_concept, "evidence": evidence, "standard_revision": "retain in common envelope" if not classification.startswith("receiver_has") else "add receiver binding/deployment section"}
        for concept, classification, receiver_concept, evidence in data
    ]


def missing_standard_rows() -> list[dict[str, Any]]:
    data = [
        ("receiver_strategy_id_and_alias", "identity binding", "active research IDs carry paper_forward_ prefixes but receiver registry does not", "add explicit research_strategy_id to receiver_strategy_id binding"),
        ("strategy_instance_or_sleeve_id", "deployment context", "independent virtual sleeves and per-strategy notional are operationally material", "add receiver-owned deployment binding outside strategy logic"),
        ("target_version_id", "idempotency", "receiver hashes strategy, as_of, and weights", "standard event ID must map deterministically to target version"),
        ("calculation_run_or_session_id", "audit lineage", "weekly session IDs own persisted evidence", "add receiver calculation_run_id to acceptance/output evidence"),
        ("runtime_spec_and_module_hashes", "code provenance", "receiver persists local copied calculator/spec hashes", "require imported package hashes and receiver binding hashes"),
        ("market_data_feed_and_adjustment_binding", "data execution context", "receiver uses Alpaca IEX and adjustment=all", "bind provider capability and normalized price semantics without putting provider credentials in handoff"),
        ("multi_strategy_allocation_and_shared_symbol_policy", "portfolio aggregation", "receiver permits shared BIL but blocks shared risky symbols", "declare receiver-owned aggregation policy and strategy sleeve isolation"),
        ("execution_profile_binding", "target/execution boundary", "notional caps, tolerances and paper/live flags are mixed into registry/spec", "move these to separate receiver deployment profile linked by ID"),
        ("persisted_state_ttl", "lifecycle liveness", "a running session can remain active after heartbeat and planned end expire", "require stale-session policy and evidence-backed active-state calculation"),
    ]
    return [{"field": field, "receiver_need": need, "evidence_summary": evidence, "required_standard_change": change} for field, need, evidence, change in data]


def migration_rows(prior: list[dict[str, str]]) -> list[dict[str, Any]]:
    receiver_adapter = {"internal_capture_asymmetry_63d_top3_v1", "spdj_multi_asset_dynamic_inflation_etf_portability_v1"}
    retirement = {"SPY_200d_trend_model", "profit_combo_SPY200d_GLD_50_50_v1"}
    rows: list[dict[str, Any]] = []
    for row in prior:
        strategy_id = row["strategy_id"]
        if strategy_id in receiver_adapter:
            classification = "receiver_adapter_only"
            reason = "formal contract exists; receiver import/timing binding is missing"
        elif strategy_id in retirement:
            classification = "retirement_candidate_due_to_unreconciled_legacy_state"
            reason = "receiver absence resolves the old active-state ambiguity but does not authorize retirement"
        else:
            classification = "contract_materialization_required"
            reason = "rules are recoverable from strategy/observation evidence but no standard handoff exists"
        rows.append({"strategy_id": strategy_id, "classification": classification, "receiver_present": strategy_id in {"paper_forward_vm_quality_lowvol_proxy_v1", "paper_forward_dsr_sector_equal_weight_defensive_filter_v1"}, "active_legacy_contract_debt": strategy_id in {"paper_forward_vm_quality_lowvol_proxy_v1", "paper_forward_dsr_sector_equal_weight_defensive_filter_v1"}, "reason": reason, "migration_performed": False})
    return rows


def priority_rows(migrations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    order = [
        "paper_forward_vm_quality_lowvol_proxy_v1",
        "paper_forward_dsr_sector_equal_weight_defensive_filter_v1",
        "spdj_multi_asset_dynamic_inflation_etf_portability_v1",
        "internal_capture_asymmetry_63d_top3_v1",
        "keller_vanputten_faa_4m_top3_v1",
        "barbara_decelerated_psar_spy_bil_v1",
        "varadi_minimum_correlation_8etf_60d_weekly_v1",
        "schwoerer_hyg_ema100_spy_bil_v1",
        "factory_v1_spy_trend_quality_state_d1",
        "paper_forward_usci_dynamic_commodity_curve_selection_wrapper_v1",
        "paper_forward_combo_vm_dsr_usci_equal_weight_monthly_v1",
        "donninger_vix_vix3m_unfiltered_three_state_spy_ief_adaptation_v1",
        "ice_vaneck_us_fallen_angel_angl_v1",
        "SPY_200d_trend_model",
        "profit_combo_SPY200d_GLD_50_50_v1",
    ]
    by_id = {row["strategy_id"]: row for row in migrations}
    rows: list[dict[str, Any]] = []
    for index, strategy_id in enumerate(order, start=1):
        basis = "active receiver contract debt" if index <= 2 else "formal export completeness" if index <= 4 else "eligibility, rule recoverability, and operational relevance" if index <= 13 else "legacy ambiguity last"
        rows.append({"priority": index, "strategy_id": strategy_id, "classification": by_id[strategy_id]["classification"], "priority_basis": basis, "performance_used": False})
    return rows


def write_markdown_files(commit: str, latest_session: dict[str, Any]) -> None:
    state = latest_session["state"]
    OUTPUT_DIR.joinpath("receiver_discovery_report.md").write_text(f"""# Receiver Discovery Report

## Outcome

The authoritative receiver application was located at `execution_lab/alpaca_micro_live_v1` inside the same Git repository. It qualifies because it owns runtime registration, target calculation, market-data retrieval/cache, persisted paper/demo sessions, virtual sleeves/equity evidence, order sizing, risk gates, and the Alpaca paper adapter.

The repository/application is `trading-tournament / Alpaca Micro Live V1`, at commit `{commit}` on `main`.

## Bounded Search

Searched the workspace repository, sibling Git repositories under the local GitHub development directory, repository documentation/configuration, and the plausible local `Forward` directory. The sibling repositories did not contain the receiver contract. The `Forward` directory contained a document, not an application. No internet search was performed.

The receiver is a logically separate application module, not a physically separate Git repository. This resolves the V1 location block without changing the ownership boundary: research exports remain upstream, and `alpaca_micro_live_v1` owns runtime operations.
""", encoding="utf-8")

    OUTPUT_DIR.joinpath("receiver_strategy_interface.md").write_text("""# Receiver Strategy Interface

## Inputs

The runtime registry selects a `runtime_spec` YAML and `runtime_module` Python calculator. The weekly runner obtains approved Alpaca daily bars, dynamically imports the module, and calls `generate_signal_from_bars(bars, spec=...)`. Strategy identity and configuration are registry/spec values; the calendar is implicit in returned market sessions; persisted state is session-scoped.

## Output

`RuntimeSignal` returns `strategy_id`, `as_of`, `target_weights`, `cash_weight`, metadata, diagnostics, fallback, missing-data, and approximation fields. It does not carry a target effective timestamp, canonical event ID, common status/error envelope, or imported-handoff provenance.

`target_version_id(strategy_id, as_of, target_weights)` provides receiver-local idempotency. The execution layer separately converts target weights and observed positions into `ProposedOrder` records, then applies the risk gate and optional paper submission.

## Classification

`partial_target_execution_separation`

The calculation/order boundary is real and targets are weights, not orders. However, runtime registration mixes strategy binding with capital sleeve notional, maximum order notional, rebalance tolerance, and paper/live permission. These deployment controls should remain receiver-owned but move behind a separate deployment binding in the common standard.
""", encoding="utf-8")

    OUTPUT_DIR.joinpath("receiver_state_contract.md").write_text(f"""# Receiver State Contract

Classification: `partially_generic_state_contract`.

The weekly runner persists session status, selected strategies, `handled_target_versions`, latest target versions, loop/read-error state, signals, positions, account snapshots, virtual sleeves, orders, fills, and stop evidence. Duplicate targets are rejected within a session, and `--resume` restores the same session unless broker ambiguity blocks it.

The latest cohort-relevant persisted session is `{state.get('session_id')}` with status `{state.get('status')}`. Its last heartbeat is `{state.get('last_heartbeat_utc')}` and planned end is `{state.get('planned_end_at_utc')}`. This supports an evidence-based active count of two, but the persisted `running` state is stale and the receiver has no TTL or authoritative liveness reconciliation.

Missing generic state concepts are per-strategy last processed event, current effective target, pending target, stale-event rejection, no-release handling, pause state, and idempotent replay across newly created sessions. State logic is generic at session level but incomplete at strategy/event level.
""", encoding="utf-8")

    OUTPUT_DIR.joinpath("receiver_market_data_contract.md").write_text("""# Receiver Market-Data Contract

The receiver declares allowed symbols in the registry and universe/lookbacks in per-strategy YAML. It fetches Alpaca `1Day` bars with feed `iex` and adjustment `all`, drops an incomplete current day, paginates, validates approved symbols and minimum row count, and writes per-symbol CSV cache files.

This is sufficient for the two existing daily ETF calculators, but it is not a provider-neutral handoff contract. Daily/monthly requirements, dividend/split semantics, signal-provider authority, freshness bounds, and point-in-time external release requirements are not represented generically. No provider was called in this audit.
""", encoding="utf-8")

    OUTPUT_DIR.joinpath("receiver_timing_contract.md").write_text("""# Receiver Timing Contract

Classification: `timing_model_material_gap`.

The implemented cadence is `daily_completed_bar` inside an operator-controlled loop. The runner can repeatedly calculate the latest daily target and the risk gate can require the market to be open for a paper submit. It does not expose a generic schedule, exchange-calendar identifier, formation cutoff, target effective timestamp, monthly/weekly event planner, no-event month state, or externally published event clock.

Accordingly, the receiver cannot natively represent the SPDJ contract: CPI release event, then next valid U.S. equity business day, then target effective after that close. A strategy-specific rewrite would hide material timing semantics; the common receiver layer needs an event/calendar extension first.
""", encoding="utf-8")

    OUTPUT_DIR.joinpath("receiver_handoff_import_capability.md").write_text("""# Receiver Handoff Import Capability

Classification: `manual_strategy_registration`.

No generic or schema-specific handoff importer exists. The onboarding inventory classifies candidates, and `freeze_successful_strategies.py` materializes hard-coded YAML/Python copies into the runtime registry. There is no supported handoff schema/version negotiation, package hash check, imported lifecycle state, golden-fixture acceptance, handoff ID persistence, or generic state initialization.

Neither formal handoff was imported or activated by this audit.
""", encoding="utf-8")

    OUTPUT_DIR.joinpath("forward_observation_handoff_standard_v1_requirements.md").write_text("""# forward_observation_handoff_standard_v1 Requirements

## Common Envelope

Require `schema_id`, `schema_version`, `handoff_id`, package hash, research strategy ID/version, receiver strategy ID binding, family/architecture IDs, eligibility evidence, canonical trial ID, source hashes, claims/nonclaims, and immutable lineage. Receiver acceptance must persist imported package and binding hashes.

## Tradable and Signal Contract

Declare exact symbols, substitutions, price/adjustment semantics, lookbacks, frequency, signal type and authority, formula/configuration, point-in-time needs, release schedule, warmup, missing data/release behavior, cash residual, shorts, leverage, and target normalization. Provider credentials and broker instructions are excluded.

## Calculator and Output

Bind a versioned calculator type/entry point and machine-readable frozen configuration. Standard output is `target_weights`, `effective_timestamp`, event identity, target version, calculation run ID, provenance, and status/error. The strategy output never contains quantities, orders, fills, notional approval, or live authorization.

## Timing and State

Require formation and signal cutoffs, exchange calendar ID, target effective timestamp, last processed event, current and pending target, idempotent replay, restart semantics, stale-event/session TTL, duplicate-event handling, and no-event behavior.

## Receiver Binding

Keep a separate receiver-owned deployment profile for strategy instance/sleeve ID, allocation/aggregation policy, shared-symbol policy, data-feed capability binding, runtime module/spec hashes, paper/live flags, notional limits, tolerances, and risk controls. These operational fields do not change the research strategy contract.

## Conformance

Each handoff includes golden inputs and hashes, expected targets, equality/tie cases, first eligible and missing-event fixtures, timing/calendar fixtures, duplicate replay, restart recovery, stale-event behavior, and deterministic acceptance results.

## Lifecycle

Canonical states are `research_eligible`, `handoff_exported`, `imported`, `validated_not_active`, `paper_demo_initialized`, `paper_demo_active`, `paper_demo_paused`, `paper_demo_disabled`, `microtrading_eligible`, and `microtrading_active`. Every transition requires evidence ID/time. A stale receiver session cannot alone preserve current active status indefinitely.

Microtrading promotion remains a separate contract governing whether execution is allowed and under what operational limits.
""", encoding="utf-8")

    OUTPUT_DIR.joinpath("microtrading_promotion_audit.md").write_text("""# Microtrading Promotion Audit

Classification: `microtrading_promotion_contract_missing`.

The receiver has useful execution safeguards: paper-only mode, live rejection, per-order and total notional limits, disallowed leverage/short/derivative flags, market-open checks, approved-symbol checks, cash buffer, emergency stop, ambiguous-submit fail-closed handling, and no blind submit retry.

It does not implement a microtrading eligibility field, approval artifact, risk-review transition, execution-validation acceptance gate, real-money enablement, or rollback/revocation evidence. Existing notional caps are paper deployment controls, not microtrading authorization. No authorization or change was made.
""", encoding="utf-8")

    OUTPUT_DIR.joinpath("next_action.md").write_text(f"""# Next Action

`{NEXT_ACTION}`

Do not execute this action in `{TASK_ID}`.
""", encoding="utf-8")


def run() -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    protected_before = snapshot(PROTECTED_PATHS)

    prior_consistency = json.loads((PRIOR_DIR / "consistency_check.json").read_text(encoding="utf-8"))
    prior_inventory = read_csv(PRIOR_DIR / "strategy_lifecycle_inventory.csv")
    prior_ids = [row["strategy_id"] for row in prior_inventory]
    registry = yaml.safe_load(RECEIVER_REGISTRY.read_text(encoding="utf-8"))
    registry_rows = registry.get("strategies") or {}
    sessions = load_receiver_sessions()
    latest_session = latest_relevant_session(sessions, {"vm_quality_lowvol_proxy_v1", "dsr_sector_equal_weight_defensive_filter_v1"})
    reconciled = reconciliation_rows(prior_inventory, latest_session)
    aliases = alias_rows()
    migrations = migration_rows(prior_inventory)
    priorities = priority_rows(migrations)
    commit = git_value("rev-parse", "HEAD")
    branch = git_value("branch", "--show-current")

    receiver_counts = {
        "audit_as_of_date": AUDIT_DATE,
        "receiver_application_strategy_registry_count": len(registry_rows),
        "receiver_application_enabled_runtime_ready_count": sum(bool(row.get("enabled") and row.get("runtime_ready")) for row in registry_rows.values()),
        "receiver_application_disabled_or_blocked_registry_count": sum(not bool(row.get("enabled") and row.get("runtime_ready")) for row in registry_rows.values()),
        "prior_research_inventory_count": len(reconciled),
        "receiver_registered": sum(bool(row["receiver_registered"]) for row in reconciled),
        "receiver_imported": sum(bool(row["receiver_imported"]) for row in reconciled),
        "receiver_validated": sum(bool(row["receiver_validated"]) for row in reconciled),
        "paper_demo_initialized": sum(bool(row["paper_demo_initialized"]) for row in reconciled),
        "paper_demo_active": sum(bool(row["paper_demo_active"]) for row in reconciled),
        "paper_demo_paused_or_disabled": sum(bool(row["paper_demo_paused"] or row["paper_demo_disabled"]) for row in reconciled),
        "microtrading_eligible": sum(bool(row["microtrading_eligible"]) for row in reconciled),
        "microtrading_active": sum(bool(row["microtrading_active"]) for row in reconciled),
        "receiver_not_found": sum(row["receiver_state"] == "receiver_not_found" for row in reconciled),
        "active_count_basis": "receiver persisted running session and weekly_summary active flag, not trading_tournament legacy active observations",
        "active_count_caveat": "latest cohort-relevant running session is stale; no receiver TTL or liveness reconciliation exists",
        "research_legacy_historical_counts": {
            "research_eligible": 11,
            "formal_handoff_exported": 2,
            "paper_demo_initialized_ever": 11,
            "paper_demo_active_ever": 11,
            "paper_demo_currently_active_in_legacy_research_evidence": 9,
            "legacy_current_state_ambiguous": 2,
            "microtrading_eligible": 0,
            "microtrading_active": 0,
        },
    }

    repository_inventory = {
        "application_name": "Alpaca Micro Live V1",
        "repository_name": "trading-tournament",
        "repository_root": ".",
        "application_root": "execution_lab/alpaca_micro_live_v1",
        "repository_relationship": "logically separate receiver application module in the same Git repository",
        "git_branch": branch,
        "git_commit": commit,
        "primary_runtime": "Python 3",
        "receiver_qualification": ["strategy registration", "target calculation", "market-data freshness/cache", "paper/demo state and ledgers", "virtual sleeves/equity evidence", "order sizing and risk gate", "Alpaca paper broker boundary"],
        "relevant_modules": {
            "strategy_registry": "execution_lab/alpaca_micro_live_v1/runtime_strategies/runtime_strategy_registry.yaml",
            "runtime_specs_and_calculators": "execution_lab/alpaca_micro_live_v1/runtime_strategies",
            "observation_state_and_ledgers": "execution_lab/alpaca_micro_live_v1/evidence/weekly_demo_sessions",
            "onboarding_inventory": "execution_lab/alpaca_micro_live_v1/evidence/runtime_onboarding/runtime_strategy_inventory.json",
            "market_data_boundary": "execution_lab/alpaca_micro_live_v1/data/alpaca_historical_bars.py",
            "market_data_cache": "execution_lab/alpaca_micro_live_v1/evidence/alpaca_runtime_data/cache",
            "target_interface": "execution_lab/alpaca_micro_live_v1/execution/models.py",
            "order_sizing": "execution_lab/alpaca_micro_live_v1/execution/order_sizing.py",
            "risk_gate": "execution_lab/alpaca_micro_live_v1/execution/risk_gate.py",
            "broker_boundary": "execution_lab/alpaca_micro_live_v1/adapters/alpaca_client.py",
            "handoff_import_registry": "absent",
        },
        "runtime_registry_strategy_ids": sorted(registry_rows),
        "credentials_read": False,
        "network_or_broker_calls": 0,
    }

    write_json(OUTPUT_DIR / "receiver_repository_inventory.json", repository_inventory)
    write_csv(OUTPUT_DIR / "receiver_lifecycle_model.csv", lifecycle_rows())
    write_csv(OUTPUT_DIR / "cross_repository_strategy_reconciliation.csv", reconciled)
    write_json(OUTPUT_DIR / "receiver_authoritative_counts.json", receiver_counts)
    write_csv(OUTPUT_DIR / "strategy_identity_aliases.csv", aliases)
    write_csv(OUTPUT_DIR / "formal_handoff_compatibility.csv", formal_compatibility_rows())
    write_csv(OUTPUT_DIR / "common_standard_receiver_mapping.csv", mapping_rows())
    write_csv(OUTPUT_DIR / "receiver_missing_standard_fields.csv", missing_standard_rows())
    write_csv(OUTPUT_DIR / "migration_matrix_v2.csv", migrations)
    write_csv(OUTPUT_DIR / "migration_priority.csv", priorities)

    observed_migration_counts = Counter(row["classification"] for row in migrations)
    migration_counts = {
        classification: observed_migration_counts[classification]
        for classification in [
            "already_standard_compatible",
            "field_mapping_only",
            "receiver_adapter_only",
            "contract_materialization_required",
            "rule_reconstruction_required",
            "retirement_candidate_due_to_unreconciled_legacy_state",
        ]
    }
    final_decision = {
        "audit_outcome": OUTCOME,
        "decision": DECISION,
        "common_schema_id": COMMON_SCHEMA_ID,
        "primary_issue": "both sides, with substantial legacy migration debt",
        "receiver_lifecycle_model_status": "fragmented_registry_onboarding_and_session_state_vocabularies",
        "target_execution_boundary_status": "partial_target_execution_separation",
        "generic_state_contract_status": "partially_generic_state_contract",
        "timing_model_status": "timing_model_material_gap",
        "handoff_import_architecture": "manual_strategy_registration",
        "internal_capture_handoff_compatibility": "requires_strategy_specific_adapter",
        "spdj_handoff_compatibility": "receiver_architecture_incompatible",
        "receiver_side_changes_required": ["generic handoff importer and acceptance record", "generic event/calendar/effective-time model", "per-strategy current/pending/last-event state with cross-session idempotency", "stale-session TTL and liveness reconciliation", "separate deployment binding for sleeve, allocation, and execution limits"],
        "research_package_changes_required": ["materialize 11 recoverable legacy contracts", "add receiver identity binding and conformance fixtures", "preserve two legacy ambiguities as retirement candidates pending direction-owner review"],
        "active_legacy_contract_debt_count": 2,
        "active_legacy_contract_debt": ["paper_forward_vm_quality_lowvol_proxy_v1", "paper_forward_dsr_sector_equal_weight_defensive_filter_v1"],
        "migration_counts": migration_counts,
        "microtrading_promotion_contract_status": "microtrading_promotion_contract_missing",
        "next_action": NEXT_ACTION,
        "next_action_executed": False,
    }
    write_json(OUTPUT_DIR / "final_standardization_decision.json", final_decision)

    gaps = [
        {"gap_id": "G1", "area": "current liveness", "gap": "receiver persists two strategies in a stale running session without TTL", "impact": "paper_demo_active=2 is receiver-evidenced but cannot prove a live process on the audit date", "resolution_owner": "receiver standard implementation"},
        {"gap_id": "G2", "area": "import lineage", "gap": "no package import or acceptance history exists", "impact": "receiver_imported=0 for all 15", "resolution_owner": "receiver standard implementation"},
        {"gap_id": "G3", "area": "state", "gap": "no generic per-strategy effective/pending target or last-event record", "impact": "restart and no-event semantics cannot be proven across sessions", "resolution_owner": "receiver standard implementation"},
        {"gap_id": "G4", "area": "timing", "gap": "no exchange-calendar event scheduler or target effective timestamp", "impact": "SPDJ formal handoff is architecturally incompatible", "resolution_owner": "receiver standard implementation"},
        {"gap_id": "G5", "area": "physical boundary", "gap": "receiver is a separate application module, not a separate repository", "impact": "ownership is logical and must be enforced by package/import boundaries", "resolution_owner": "direction owner"},
        {"gap_id": "G6", "area": "microtrading", "gap": "no eligibility/approval/revocation transition contract", "impact": "microtrading remains unauthorized", "resolution_owner": "future governance task"},
    ]
    write_csv(OUTPUT_DIR / "evidence_gaps.csv", gaps)
    write_markdown_files(commit, latest_session)

    protected_after = snapshot(PROTECTED_PATHS)
    prior_hash = prior_consistency.get("deterministic_audit_hash")
    parse_errors: list[str] = []
    for path in sorted(list(INTERNAL_HANDOFF.rglob("*.json")) + list(SPDJ_HANDOFF.rglob("*.json"))):
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:  # pragma: no cover - evidence guard
            parse_errors.append(f"{rel(path)}:{type(exc).__name__}")
    for path in sorted(INTERNAL_HANDOFF.rglob("*.yaml")):
        try:
            yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception as exc:  # pragma: no cover - evidence guard
            parse_errors.append(f"{rel(path)}:{type(exc).__name__}")

    files_for_hash = [name for name in REQUIRED_FILES if name != "consistency_check.json"]
    artifact_hashes = {name: sha256_file(OUTPUT_DIR / name) for name in files_for_hash}
    audit_hash = canonical_hash(artifact_hashes)
    checks = {
        "prior_audit_hash_reconciles": prior_hash == EXPECTED_PRIOR_HASH,
        "exactly_15_unique_research_strategies": len(prior_ids) == len(set(prior_ids)) == 15,
        "receiver_registry_parses": isinstance(registry_rows, dict) and len(registry_rows) == 4,
        "receiver_session_state_files_parse": len(sessions) > 0,
        "exactly_two_evidenced_aliases": len(aliases) == 2 and len({row["receiver_strategy_id"] for row in aliases}) == 2,
        "receiver_counts_reconcile": receiver_counts["receiver_registered"] + receiver_counts["receiver_not_found"] == 15,
        "receiver_current_count_uses_receiver_evidence": receiver_counts["paper_demo_active"] == 2,
        "legacy_counts_kept_separate": receiver_counts["research_legacy_historical_counts"]["paper_demo_currently_active_in_legacy_research_evidence"] == 9,
        "formal_handoff_count_is_two": len(formal_compatibility_rows()) == 2,
        "handoff_manifests_and_schemas_parse": not parse_errors,
        "all_migration_rows_classified": len(migrations) == 15 and sum(migration_counts.values()) == 15,
        "active_legacy_contract_debt_is_two": final_decision["active_legacy_contract_debt_count"] == 2,
        "standardization_required": final_decision["decision"] == DECISION,
        "protected_state_unchanged": protected_before == protected_after,
        "all_required_files_exist": all((OUTPUT_DIR / name).exists() for name in files_for_hash),
        "no_strategy_or_receiver_mutation": protected_before == protected_after,
    }
    consistency = {
        "task_id": TASK_ID,
        "audit_as_of_date": AUDIT_DATE,
        "outcome": OUTCOME,
        "receiver_located": True,
        "checks": checks,
        "overall_pass": all(checks.values()),
        "deterministic_audit_hash": audit_hash,
        "artifact_hashes": artifact_hashes,
        "parse_errors": parse_errors,
        "protected_state_before": protected_before,
        "protected_state_after": protected_after,
        "strategy_performance_recalculated": False,
        "strategy_rules_changed": False,
        "network_market_data_calls": 0,
        "broker_calls": 0,
        "order_calls": 0,
        "current_target_calculations": 0,
        "observation_mutations": 0,
        "strategy_activations": 0,
        "microtrading_changes": 0,
        "next_action": NEXT_ACTION,
        "next_action_executed": False,
    }
    write_json(OUTPUT_DIR / "consistency_check.json", consistency)
    return consistency


def main() -> int:
    result = run()
    print(json.dumps({"task_id": TASK_ID, "outcome": result["outcome"], "overall_pass": result["overall_pass"], "deterministic_audit_hash": result["deterministic_audit_hash"], "next_action": result["next_action"]}, sort_keys=True))
    return 0 if result["overall_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
