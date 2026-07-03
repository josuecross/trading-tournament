from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import REGISTRY_PATH, ROADMAP_PATH, ROOT
from strategy_lab.research_os.objective_reset.objective_reset_review import replace_or_append_section, write_json, write_text


OUTPUT_DIR = Path("evidence") / "research_engine_audit" / "split_operations_and_research_tracks" / "latest"
COMPACT_STATE_PATH = Path("reports") / "compact_state" / "current_tournament_state.md"
OPERATIONS_STATE_PATH = Path("reports") / "operations_state" / "current_operations_state.md"
RESEARCH_STATE_PATH = Path("reports") / "research_state" / "current_research_state.md"
ARCHIVE_INDEX_PATH = Path("reports") / "archive_state" / "archive_index.md"
ACTIVE_OBSERVATIONS_PATH = Path("strategy_lab") / "research_os" / "operations" / "active_observations.yaml"
OBSERVATION_POLICY_PATH = Path("strategy_lab") / "research_os" / "operations" / "observation_policy.md"
RESEARCH_POLICY_PATH = Path("strategy_lab") / "research_os" / "research" / "research_policy.md"
RESEARCH_QUEUE_PATH = Path("strategy_lab") / "research_os" / "research" / "research_queue.yaml"
ARCHIVE_POLICY_PATH = Path("strategy_lab") / "research_os" / "archive" / "archive_policy.md"
FAMILY_LEDGER_PATH = Path("strategy_lab") / "research_os" / "family_lineage" / "family_ledger.yaml"

NEXT_ACTION_OBSERVE = "continue_paper_forward_observation_only"
NEXT_ACTION_RECOVER_GLD = "recover_gld_macro_family_lineage"
NEXT_ACTION_MANUAL = "manual_review_required_after_track_split"
NEXT_ACTION_PAUSE = "pause_expansion_and_wait_for_manual_direction"
VALID_NEXT_ACTIONS = {
    NEXT_ACTION_OBSERVE,
    NEXT_ACTION_RECOVER_GLD,
    NEXT_ACTION_MANUAL,
    NEXT_ACTION_PAUSE,
}

REQUIRED_OUTPUT_FILES = (
    "split_tracks_manifest.json",
    "split_tracks_summary.md",
    "operations_track_policy.md",
    "research_track_policy.md",
    "archive_track_policy.md",
    "current_operations_state.md",
    "current_research_state.md",
    "archive_index.md",
    "family_lineage_ledger.yaml",
    "gld_macro_lineage_recovery_queue.md",
    "authoritative_state_policy.md",
    "evidence_lineage_policy.md",
    "forbidden_next_steps.md",
    "split_tracks_next_action.md",
    "split_tracks_consistency_check.json",
)

MANIFEST_FLAGS = {
    "split_tracks_only": True,
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


def audit_source(root: Path) -> dict[str, Any]:
    audit_path = root / "evidence" / "research_engine_audit" / "independent_research_engine_audit" / "latest"
    manifest = {}
    manifest_path = audit_path / "research_engine_audit_manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return {
        "audit_path": str(audit_path),
        "audit_exists": audit_path.exists(),
        "audit_recommendation": manifest.get("final_recommendation", "split_operations_and_research_tracks"),
        "audit_blocking_issue_found": manifest.get("blocking_issue_found", False),
        "audit_gld_macro_lineage_needs_recovery": manifest.get("gld_macro_lineage_needs_recovery", True),
    }


def operations_payload(created_utc: str) -> dict[str, Any]:
    return {
        "created_utc": created_utc,
        "track": "operations_observation",
        "source_of_truth": True,
        "research_mutation_allowed": False,
        "paper_forward_activation_allowed": False,
        "broker_live_action_allowed": False,
        "real_money_recommendation_allowed": False,
        "active_observations": [
            {
                "strategy_id": "paper_forward_vm_quality_lowvol_proxy_v1",
                "state": "active_accepted_frozen_observation",
                "paper_forward_active": True,
                "protected": True,
            },
            {
                "strategy_id": "paper_forward_dsr_sector_equal_weight_defensive_filter_v1",
                "state": "active_accepted_frozen_observation",
                "paper_forward_active": True,
                "protected": True,
            },
        ],
        "benchmark_controls": [
            {
                "strategy_id": "static_all_weather_benchmark_v1",
                "state": "benchmark_control_only",
                "paper_forward_active": False,
                "protected": True,
            }
        ],
        "references": ["SPY", "QQQ", "BIL", "active_vm", "active_dsr", "active_combo", "static_all_weather"],
        "forbidden": [
            "new_paper_forward_candidate",
            "paper_forward_activation",
            "broker_live_action",
            "real_money_recommendation",
            "research_mutation",
        ],
    }


def research_queue_payload(created_utc: str) -> dict[str, Any]:
    return {
        "created_utc": created_utc,
        "track": "research_discovery",
        "current_expansion_status": "paused",
        "sandbox_batch_authorized": False,
        "strategy_discovery_authorized": False,
        "candidate_exhaustive_authorized": False,
        "paper_forward_candidate_creation_authorized": False,
        "future_research_requirements": [
            "specific_objective",
            "specific_lane",
            "specific_hypothesis",
            "separate_preregistration_before_formal_discovery",
            "sandbox_outputs_non_promotable",
        ],
        "queued_governance_reviews": [
            {
                "id": "recover_gld_macro_family_lineage",
                "purpose": "Recover GLD/gold/macro/risk-on-risk-off decisions into a compact ledger before any new macro/diversifier research.",
                "status": "queued_not_run",
                "authorizes_backtests": False,
                "authorizes_discovery": False,
                "authorizes_rejected_row_reopening": False,
                "authorizes_provider_download": False,
                "authorizes_paper_forward": False,
            }
        ],
    }


def family_ledger_payload(created_utc: str) -> dict[str, Any]:
    entries = [
        {
            "family_id": "gld_macro_risk_off",
            "current_status": "lineage_recovery_needed",
            "latest_decision": "context_only_until_recovered",
            "authoritative_evidence_path": "strategy_lab/RESEARCH_ROADMAP.md and historical evidence packets",
            "active_rejected_context_status": "context_only",
            "lineage_recovery_needed": True,
            "future_research_allowed": False,
            "required_next_review_before_reopening": "recover_gld_macro_family_lineage",
            "notes": "Recover GLD/gold/macro/risk-on-risk-off decisions before any new macro/diversifier research.",
        },
        {
            "family_id": "managed_futures_etf_wrapper",
            "current_status": "closed_under_current_mechanics",
            "latest_decision": "mfv_equal_weight_trend_filter_v1 rejected as weaker than active references",
            "authoritative_evidence_path": "evidence/parallel_research_discovery/next_family_after_indicator_validation/latest",
            "active_rejected_context_status": "rejected",
            "lineage_recovery_needed": False,
            "future_research_allowed": False,
            "required_next_review_before_reopening": "new_objective_or_data_class_review",
            "notes": "ETF-wrapper managed-futures ideas remain historical context, not direct futures trading.",
        },
        {
            "family_id": "quality_momentum_etf_proxy",
            "current_status": "context_watchlist",
            "latest_decision": "upside rows had insufficient risk buffer",
            "authoritative_evidence_path": "evidence/promotion_reviews/qvm_quality_value_momentum_risk_adjusted_top2_v1/latest",
            "active_rejected_context_status": "context_only",
            "lineage_recovery_needed": False,
            "future_research_allowed": False,
            "required_next_review_before_reopening": "separate_family_lineage_review",
            "notes": "Do not reopen exact variants without a new frozen thesis.",
        },
        {
            "family_id": "defensive_sector_rotation",
            "current_status": "active_dsr_preserved",
            "latest_decision": "paper_forward_dsr_sector_equal_weight_defensive_filter_v1 active/frozen",
            "authoritative_evidence_path": "strategy_lab/strategy_registry.yaml",
            "active_rejected_context_status": "active_frozen_observation",
            "lineage_recovery_needed": False,
            "future_research_allowed": False,
            "required_next_review_before_reopening": "operations_track_observation_review_only",
            "notes": "Active DSR remains protected and not research-mutated.",
        },
        {
            "family_id": "volatility_managed_quality_lowvol",
            "current_status": "active_vm_preserved",
            "latest_decision": "paper_forward_vm_quality_lowvol_proxy_v1 active/frozen",
            "authoritative_evidence_path": "strategy_lab/strategy_registry.yaml",
            "active_rejected_context_status": "active_frozen_observation",
            "lineage_recovery_needed": False,
            "future_research_allowed": False,
            "required_next_review_before_reopening": "operations_track_observation_review_only",
            "notes": "Active VM remains protected and not research-mutated.",
        },
        {
            "family_id": "breakout_continuation",
            "current_status": "sandbox_clue_only",
            "latest_decision": "interesting but not actionable after fixed-scoring rerun audit",
            "authoritative_evidence_path": "evidence/objective_reset/fixed_scoring_rerun_audit/latest",
            "active_rejected_context_status": "context_only",
            "lineage_recovery_needed": False,
            "future_research_allowed": False,
            "required_next_review_before_reopening": "manual_family_lineage_review",
            "notes": "Contribution score was not enough; useful contribution evidence variants remained zero.",
        },
        {
            "family_id": "macro_portfolio_contribution",
            "current_status": "sandbox_context_only",
            "latest_decision": "weak/contextual after v3 rerun audit",
            "authoritative_evidence_path": "evidence/objective_reset/fixed_scoring_rerun_audit/latest",
            "active_rejected_context_status": "context_only",
            "lineage_recovery_needed": True,
            "future_research_allowed": False,
            "required_next_review_before_reopening": "recover_gld_macro_family_lineage",
            "notes": "Treat as benchmark/contribution context until macro lineage is compacted.",
        },
        {
            "family_id": "trend_momentum",
            "current_status": "deprioritized",
            "latest_decision": "weak after v3 rerun audit; risk integrity blocked",
            "authoritative_evidence_path": "evidence/objective_reset/fixed_scoring_rerun_audit/latest",
            "active_rejected_context_status": "sandbox_weak",
            "lineage_recovery_needed": False,
            "future_research_allowed": False,
            "required_next_review_before_reopening": "new_risk_control_hypothesis_preregistration",
            "notes": "Do not rely on standalone score when risk integrity fails.",
        },
        {
            "family_id": "volatility_regime",
            "current_status": "deprioritized",
            "latest_decision": "high-upside/high-risk pattern persisted",
            "authoritative_evidence_path": "evidence/objective_reset/fixed_scoring_rerun_audit/latest",
            "active_rejected_context_status": "sandbox_weak",
            "lineage_recovery_needed": False,
            "future_research_allowed": False,
            "required_next_review_before_reopening": "new_risk_control_hypothesis_preregistration",
            "notes": "No new volatility-regime research without a distinct risk-control thesis.",
        },
        {
            "family_id": "portfolio_combination_sleeve_ensemble",
            "current_status": "deprioritized",
            "latest_decision": "active-combo repackaging concern remains",
            "authoritative_evidence_path": "evidence/objective_reset/fixed_scoring_rerun_audit/latest",
            "active_rejected_context_status": "sandbox_weak",
            "lineage_recovery_needed": False,
            "future_research_allowed": False,
            "required_next_review_before_reopening": "duplicate_behavior_review",
            "notes": "Do not reopen without a non-duplicate portfolio-contribution thesis.",
        },
    ]
    return {
        "created_utc": created_utc,
        "track": "archive_lineage",
        "ledger_status": "scaffold_created_recovery_not_run",
        "full_lineage_recovery_performed": False,
        "entries": entries,
    }


def operations_state_md(created_utc: str, output: Path) -> str:
    return f"""# Current Operations State

Created UTC: `{created_utc}`

Source-of-truth track: `operations_observation`

Evidence packet: `{output.resolve()}`

## Protected Active Observations

- `paper_forward_vm_quality_lowvol_proxy_v1`: active/accepted/frozen observation.
- `paper_forward_dsr_sector_equal_weight_defensive_filter_v1`: active/accepted/frozen observation.

## Benchmark / Control

- `static_all_weather_benchmark_v1`: benchmark/control only.
- Active combo, SPY, QQQ, BIL, and static all-weather remain references or controls, not new active strategies.

## Operations Rules

- No research mutation is allowed from the operations track.
- No new paper-forward candidate is created by this split.
- No broker/live-order or real-money path is authorized.
"""


def research_state_md(created_utc: str, output: Path) -> str:
    return f"""# Current Research State

Created UTC: `{created_utc}`

Source-of-truth track: `research_discovery`

Evidence packet: `{output.resolve()}`

Research expansion status: `paused`

## Authorization State

- Sandbox batch authorized: `false`
- Strategy discovery authorized: `false`
- Candidate exhaustive authorized: `false`
- Paper-forward candidate creation authorized: `false`
- Provider download authorized: `false`
- Intraday data use authorized: `false`

## Future Research Requirement

Any future research must reference a specific objective, lane, and hypothesis and must use a separate preregistration before formal discovery. Sandbox outputs remain non-promotable.
"""


def archive_index_md(created_utc: str, output: Path) -> str:
    return f"""# Archive Index

Created UTC: `{created_utc}`

Source-of-truth track: `archive_lineage`

Evidence packet: `{output.resolve()}`

Historical roadmap sections and stale next-action labels are non-authoritative. The compact current state, operations state, research state, and family ledger are the current authority surfaces.

## Queued Recovery

- `recover_gld_macro_family_lineage`: queued, not run.

## Ledger

- Family ledger scaffold: `strategy_lab/research_os/family_lineage/family_ledger.yaml`
"""


def operation_policy_md() -> str:
    return """# Operations Track Policy

The operations track preserves current active/frozen observations and benchmark controls.

Allowed:

- Observe active VM and active DSR.
- Maintain paper/demo observation status.
- Reference benchmark/control rows.

Forbidden:

- Research mutation.
- New candidate creation.
- Paper-forward activation for a new strategy.
- Broker/live-order action.
- Real-money recommendation.
"""


def research_policy_md() -> str:
    return """# Research Track Policy

The research track contains non-operational hypotheses, sandbox logic, scoring systems, preregistration work, and future discovery governance.

Current status: `paused`

No sandbox batch, strategy discovery, candidate_exhaustive, provider download, intraday test, paper-forward activation, or real-money action is authorized by this split.

Any future research must define a specific objective, lane, hypothesis, data policy, scoring policy, and separate preregistration before formal discovery.
"""


def archive_policy_md() -> str:
    return """# Archive Track Policy

The archive track stores historical evidence, stale roadmap sections, prior next-action labels, and family decisions.

Historical sections are non-authoritative unless cited by the compact current state, current operations state, current research state, or family ledger.

Do not delete historical evidence. Do not use a stale roadmap next action as authorization. Future promotion decisions must reference durable evidence packets or hashes, not only mutable `latest/` paths.
"""


def authoritative_state_policy_md() -> str:
    return """# Authoritative State Policy

Authoritative current-state order:

1. `reports/operations_state/current_operations_state.md`
2. `reports/research_state/current_research_state.md`
3. `reports/compact_state/current_tournament_state.md`
4. `strategy_lab/strategy_registry.yaml` current metadata fields
5. `strategy_lab/research_os/family_lineage/family_ledger.yaml`

Non-authoritative by default:

- Historical roadmap sections below the compact current state.
- Stale next-action labels in old evidence packets.
- Mutable `latest/` evidence directories unless supported by a manifest and current-state reference.

Agents must treat historical next actions as archive records, not authorization.
"""


def evidence_lineage_policy_md() -> str:
    return """# Evidence Lineage Policy

Evidence lineage rules:

- `latest/` directories are convenience pointers, not durable proof by themselves.
- Promotion or paper-forward decisions require durable packet paths, manifests, and consistency checks.
- Generated evidence can remain ignored by git, but source-of-truth metadata must be reflected in tracked registry, roadmap, compact state, and track files.
- Historical packets must not be deleted during lineage cleanup.
- Family decisions should be recoverable from the family ledger without reading dozens of packets.
"""


def gld_queue_md() -> str:
    return """# GLD / Macro Lineage Recovery Queue

Queue entry: `recover_gld_macro_family_lineage`

Status: `queued_not_run`

Purpose:

Recover all GLD/gold/macro/risk-on-risk-off decisions into a compact ledger before any new macro/diversifier research.

This queue entry does not authorize backtests, discovery, provider downloads, intraday data use, rejected-row reopening, candidate_exhaustive, paper-forward activation, broker/live action, or real-money recommendations.
"""


def forbidden_next_steps_md() -> str:
    return """# Forbidden Next Steps

This split does not authorize:

- strategy discovery
- sandbox batch 003
- batch 002 rerun
- new backtests
- raw-data performance metrics
- new variants
- strategy promotion
- rejected variant reopening
- new paper-forward candidates
- paper-forward activation
- provider downloads
- intraday data use
- broker/live-order paths
- real-money recommendations
"""


def summary_md(m: dict[str, Any]) -> str:
    return f"""# Split Operations And Research Tracks Summary

Exact next action: `{m['next_action']}`

Operations track created: `{m['operations_track_created']}`

Research track created: `{m['research_track_created']}`

Archive track created: `{m['archive_track_created']}`

Family lineage ledger created: `{m['family_lineage_ledger_created']}`

GLD/macro recovery queued: `{m['gld_macro_recovery_queued']}`

## Decision

The split is clean enough to resume observation-only operations while keeping research expansion paused. GLD/macro lineage recovery is queued as a governance-only task, not run here.

## Protected State

- Active VM remains active/frozen.
- Active DSR remains active/frozen.
- Static all-weather remains benchmark/control only.
- Exact rejected variants remain closed.
- Intraday research remains paused.

No sandbox batch, discovery, backtest, provider download, intraday data, candidate_exhaustive, paper-forward activation, broker/live action, or real-money recommendation occurred.
"""


def next_action_md(next_action: str) -> str:
    return f"""# Split Tracks Next Action

Exact next action:

`{next_action}`

This is observation-only. Do not run strategy discovery, sandbox batches, backtests, provider downloads, intraday tests, candidate_exhaustive, paper-forward activation, broker/live actions, or real-money recommendations.
"""


def manifest(created_utc: str, root: Path, output: Path) -> dict[str, Any]:
    source = audit_source(root)
    return {
        "created_utc": created_utc,
        **MANIFEST_FLAGS,
        "source_audit_path": source["audit_path"],
        "source_audit_recommendation": source["audit_recommendation"],
        "source_audit_blocking_issue_found": source["audit_blocking_issue_found"],
        "operations_track_created": True,
        "research_track_created": True,
        "archive_track_created": True,
        "family_lineage_ledger_created": True,
        "gld_macro_recovery_queued": True,
        "full_lineage_recovery_run": False,
        "current_operations_state_path": str((root / OPERATIONS_STATE_PATH).resolve()),
        "current_research_state_path": str((root / RESEARCH_STATE_PATH).resolve()),
        "archive_index_path": str((root / ARCHIVE_INDEX_PATH).resolve()),
        "family_lineage_ledger_path": str((root / FAMILY_LEDGER_PATH).resolve()),
        "evidence_path": str(output.resolve()),
        "next_action": NEXT_ACTION_OBSERVE,
    }


def update_metadata(root: Path, output: Path, created_utc: str, m: dict[str, Any]) -> tuple[bool, bool, bool]:
    registry_path = root / REGISTRY_PATH
    registry = load_yaml(registry_path)
    metadata = registry.setdefault("registry", {})
    before_metadata = dict(metadata)
    metadata.update(
        {
            "split_operations_and_research_tracks_path": str(output.resolve()),
            "split_operations_and_research_tracks_status": "completed",
            "split_operations_and_research_tracks_created_utc": created_utc,
            "current_research_mode": "operations_research_archive_tracks_split",
            "current_next_action": m["next_action"],
            "official_current_next_action": m["next_action"],
            "next_action": m["next_action"],
            "operations_track_created": True,
            "research_track_created": True,
            "archive_track_created": True,
            "family_lineage_ledger_created": True,
            "gld_macro_recovery_queued": True,
            "authoritative_operations_state_path": str((root / OPERATIONS_STATE_PATH).resolve()),
            "authoritative_research_state_path": str((root / RESEARCH_STATE_PATH).resolve()),
            "authoritative_archive_index_path": str((root / ARCHIVE_INDEX_PATH).resolve()),
            "authoritative_family_ledger_path": str((root / FAMILY_LEDGER_PATH).resolve()),
            "split_tracks_no_strategy_discovery": True,
            "split_tracks_no_sandbox_batch": True,
            "split_tracks_no_backtests": True,
            "split_tracks_no_provider_download": True,
            "split_tracks_no_intraday_data": True,
            "split_tracks_no_candidate_exhaustive": True,
            "split_tracks_no_paper_forward_activation": True,
            "split_tracks_no_real_money_recommendation": True,
        }
    )
    registry_path.write_text(yaml.safe_dump(registry, sort_keys=False, width=120, allow_unicode=False), encoding="utf-8")

    roadmap_path = root / ROADMAP_PATH
    before_roadmap = read_text(roadmap_path) or "# Research Roadmap\n"
    compact_section = f"""## Compact Current State

- Updated UTC: `{created_utc}`
- Current research mode: `operations_research_archive_tracks_split`
- Official current next action: `{m['next_action']}`
- Split-tracks evidence: `{output.resolve()}`
- Operations state: `{(root / OPERATIONS_STATE_PATH).resolve()}`
- Research state: `{(root / RESEARCH_STATE_PATH).resolve()}`
- Archive index: `{(root / ARCHIVE_INDEX_PATH).resolve()}`
- Family ledger: `{(root / FAMILY_LEDGER_PATH).resolve()}`
- Active VM and active DSR remain protected active/frozen observations.
- `static_all_weather_benchmark_v1` remains benchmark/control only.
- Exact rejected variants remain closed.
- Intraday remains paused: `true`
- Historical roadmap sections below this compact state are non-authoritative archive records unless cited by current-state files.
- This split did not run a sandbox batch, strategy discovery, new backtest, candidate_exhaustive, paper-forward activation, provider download, intraday test, broker/live action, strategy promotion, rejected variant reopening, or real-money recommendation.
"""
    split_section = f"""## Split Operations And Research Tracks

- Created UTC: `{created_utc}`
- Evidence path: `{output.resolve()}`
- Operations track created: `{m['operations_track_created']}`
- Research track created: `{m['research_track_created']}`
- Archive track created: `{m['archive_track_created']}`
- Family lineage ledger created: `{m['family_lineage_ledger_created']}`
- GLD/macro recovery queued: `{m['gld_macro_recovery_queued']}`
- Next action: `{m['next_action']}`
- Do not run the next action in this split task.
"""
    after_roadmap = replace_or_append_section(before_roadmap, "## Compact Current State", compact_section)
    after_roadmap = replace_or_append_section(after_roadmap, "## Split Operations And Research Tracks", split_section)
    write_text(roadmap_path, after_roadmap)

    compact_path = root / COMPACT_STATE_PATH
    before_compact = read_text(compact_path)
    after_compact = f"""# Current Tournament State

Created UTC: `{created_utc}`

Current research mode: `operations_research_archive_tracks_split`

Current next action: `{m['next_action']}`

Split-tracks evidence: `{output.resolve()}`

## Authority

- Operations state: `{(root / OPERATIONS_STATE_PATH).resolve()}`
- Research state: `{(root / RESEARCH_STATE_PATH).resolve()}`
- Archive index: `{(root / ARCHIVE_INDEX_PATH).resolve()}`
- Family ledger: `{(root / FAMILY_LEDGER_PATH).resolve()}`

## Protected State

- `paper_forward_vm_quality_lowvol_proxy_v1` remains active/accepted/frozen.
- `paper_forward_dsr_sector_equal_weight_defensive_filter_v1` remains active/accepted/frozen.
- `static_all_weather_benchmark_v1` remains benchmark/control only.
- Exact rejected variants remain closed.
- Intraday research remains paused.

## Forbidden Actions

- No new sandbox batch, strategy discovery, new backtest, candidate_exhaustive, paper-forward activation, provider download, intraday test, broker/live action, rejected variant reopening, strategy promotion, or real-money recommendation occurred in this split.
"""
    write_text(compact_path, after_compact)
    return before_metadata != metadata, before_roadmap != after_roadmap, before_compact != after_compact


def consistency_check(m: dict[str, Any], output: Path, root: Path) -> dict[str, Any]:
    required = {name: (output / name).exists() for name in REQUIRED_OUTPUT_FILES}
    check = {
        "split_tracks_completed": True,
        "required_files_present": all(required.values()),
        "required_files": required,
        "split_tracks_only": m["split_tracks_only"] is True,
        "no_new_sandbox_batch": m["new_sandbox_batch_run"] is False,
        "no_discovery": m["strategy_discovery_run"] is False and m["formal_discovery_run"] is False,
        "no_backtests": m["new_backtests_run"] is False,
        "no_raw_data_metrics": m["new_performance_metrics_from_raw_data_computed"] is False,
        "no_new_variants": m["new_variants_created"] is False,
        "no_preregistration_or_candidates": (
            m["future_preregistration_candidates_created"] is False
            and m["formal_preregistration_created"] is False
            and m["candidate_exhaustive_run"] is False
        ),
        "no_paper_forward_action": (
            m["paper_forward_review"] is False
            and m["paper_forward_activation"] is False
            and m["new_paper_forward_candidate_created"] is False
        ),
        "active_vm_preserved": m["active_vm_preserved"] is True,
        "active_dsr_preserved": m["active_dsr_preserved"] is True,
        "static_all_weather_control_only": m["static_all_weather_benchmark_control_only"] is True,
        "no_provider_intraday_broker_real_money": (
            m["provider_download"] is False
            and m["intraday_data_used"] is False
            and m["broker_orders_submitted"] is False
            and m["broker_orders_cancelled"] is False
            and m["live_orders"] is False
            and m["real_money_recommendation"] is False
        ),
        "protected_strategy_state_unchanged": (
            m["active_strategy_state_changed"] is False
            and m["rejected_strategy_state_changed"] is False
            and m["exact_rejected_variants_reopened"] is False
        ),
        "operations_track_exists": (root / OPERATIONS_STATE_PATH).exists() and (root / ACTIVE_OBSERVATIONS_PATH).exists(),
        "research_track_exists": (root / RESEARCH_STATE_PATH).exists() and (root / RESEARCH_QUEUE_PATH).exists(),
        "archive_track_exists": (root / ARCHIVE_INDEX_PATH).exists() and (root / ARCHIVE_POLICY_PATH).exists(),
        "family_lineage_ledger_exists": (root / FAMILY_LEDGER_PATH).exists(),
        "gld_macro_recovery_queued": m["gld_macro_recovery_queued"] is True,
        "next_action_valid": m["next_action"] in VALID_NEXT_ACTIONS,
    }
    check["consistency_passed"] = all(value is True for key, value in check.items() if key not in {"required_files"})
    return check


def run(root: Path = ROOT) -> dict[str, Any]:
    created = now_utc()
    output = root / OUTPUT_DIR
    output.mkdir(parents=True, exist_ok=True)

    ops = operations_payload(created)
    research_queue = research_queue_payload(created)
    family_ledger = family_ledger_payload(created)

    write_yaml(root / ACTIVE_OBSERVATIONS_PATH, ops)
    write_text(root / OBSERVATION_POLICY_PATH, operation_policy_md())
    write_text(root / RESEARCH_POLICY_PATH, research_policy_md())
    write_yaml(root / RESEARCH_QUEUE_PATH, research_queue)
    write_text(root / ARCHIVE_POLICY_PATH, archive_policy_md())
    write_yaml(root / FAMILY_LEDGER_PATH, family_ledger)

    write_text(root / OPERATIONS_STATE_PATH, operations_state_md(created, output))
    write_text(root / RESEARCH_STATE_PATH, research_state_md(created, output))
    write_text(root / ARCHIVE_INDEX_PATH, archive_index_md(created, output))

    m = manifest(created, root, output)

    write_text(output / "operations_track_policy.md", operation_policy_md())
    write_text(output / "research_track_policy.md", research_policy_md())
    write_text(output / "archive_track_policy.md", archive_policy_md())
    write_text(output / "current_operations_state.md", operations_state_md(created, output))
    write_text(output / "current_research_state.md", research_state_md(created, output))
    write_text(output / "archive_index.md", archive_index_md(created, output))
    write_yaml(output / "family_lineage_ledger.yaml", family_ledger)
    write_text(output / "gld_macro_lineage_recovery_queue.md", gld_queue_md())
    write_text(output / "authoritative_state_policy.md", authoritative_state_policy_md())
    write_text(output / "evidence_lineage_policy.md", evidence_lineage_policy_md())
    write_text(output / "forbidden_next_steps.md", forbidden_next_steps_md())
    write_text(output / "split_tracks_next_action.md", next_action_md(m["next_action"]))
    write_text(output / "split_tracks_summary.md", summary_md(m))

    registry_updated, roadmap_updated, compact_updated = update_metadata(root, output, created, m)
    m.update({"registry_updated": registry_updated, "roadmap_updated": roadmap_updated, "compact_state_updated": compact_updated})

    write_json(output / "split_tracks_manifest.json", m)
    write_json(output / "split_tracks_consistency_check.json", {"consistency_passed": False})
    check = consistency_check(m, output, root)
    write_json(output / "split_tracks_consistency_check.json", check)
    return {**m, "consistency_passed": check["consistency_passed"], "output_dir": str(output.resolve())}


if __name__ == "__main__":
    result = run()
    print(
        json.dumps(
            {
                "output_dir": result["output_dir"],
                "next_action": result["next_action"],
                "consistency_passed": result["consistency_passed"],
            },
            indent=2,
        )
    )
