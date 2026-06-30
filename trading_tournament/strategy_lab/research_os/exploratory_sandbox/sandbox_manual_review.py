from __future__ import annotations

import csv
import hashlib
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from .sandbox_batch_audit import OUTPUT_DIR as BATCH_AUDIT_DIR
from .sandbox_config import REGISTRY_PATH, ROADMAP_PATH, ROOT
from .sandbox_packet_fix import OUTPUT_DIR as PACKET_FIX_DIR


OUTPUT_DIR = Path("evidence") / "exploratory_sandbox" / "manual_review_after_packet_fix" / "latest"
COMPACT_STATE_PATH = Path("reports") / "compact_state" / "current_tournament_state.md"
BATCH_DIR = Path("evidence") / "exploratory_sandbox" / "batch_001" / "latest"

NEXT_ACTION_OBJECTIVE_RESET = "create_objective_reset_review"
NEXT_ACTION_BATCH_002 = "pre_register_exploratory_sandbox_batch_002"
NEXT_ACTION_FAMILY = "pre_register_one_family_from_sandbox_findings"
NEXT_ACTION_OBSERVE = "continue_paper_forward_observation_only"
NEXT_ACTION_PAUSE = "pause_expansion_and_wait_for_manual_direction"
VALID_NEXT_ACTIONS = {
    NEXT_ACTION_OBJECTIVE_RESET,
    NEXT_ACTION_BATCH_002,
    NEXT_ACTION_FAMILY,
    NEXT_ACTION_OBSERVE,
    NEXT_ACTION_PAUSE,
}

MANIFEST_FLAGS = {
    "manual_review_only": True,
    "new_sandbox_batch_run": False,
    "strategy_discovery_run": False,
    "formal_discovery_run": False,
    "new_backtests_run": False,
    "new_performance_metrics_computed": False,
    "sandbox_results_changed": False,
    "variant_statuses_changed": False,
    "family_audit_changed": False,
    "future_preregistration_candidates_created": False,
    "indicator_library_dependency_added": False,
    "provider_download": False,
    "intraday_data_used": False,
    "candidate_exhaustive_run": False,
    "paper_forward_review": False,
    "paper_forward_activation": False,
    "broker_orders_submitted": False,
    "broker_orders_cancelled": False,
    "live_orders": False,
    "real_money_recommendation": False,
    "active_strategy_state_changed": False,
    "rejected_strategy_state_changed": False,
    "exact_rejected_variants_reopened": False,
    "intraday_research_remains_paused": True,
    "sandbox_results_remain_non_promotable": True,
    "sandbox_can_create_paper_candidates": False,
}

REQUIRED_FILES = (
    "manual_review_after_packet_fix_manifest.json",
    "manual_review_after_packet_fix_summary.md",
    "packet_fix_acceptance_review.md",
    "batch_001_research_interpretation.md",
    "family_actionability_review.md",
    "batch_002_decision_review.md",
    "objective_mismatch_review.md",
    "active_observation_recommendation.md",
    "forbidden_next_steps.md",
    "manual_review_next_action.md",
    "manual_review_after_packet_fix_consistency_check.json",
)


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def batch_result_hashes(root: Path) -> dict[str, str]:
    batch = root / BATCH_DIR
    names = [
        "sandbox_variant_results.csv",
        "sandbox_family_summary.csv",
        "sandbox_benchmark_comparison_summary.csv",
        "sandbox_risk_summary.csv",
        "sandbox_diversification_summary.csv",
        "sandbox_practicality_summary.csv",
    ]
    return {name: sha256_file(batch / name) for name in names if (batch / name).exists()}


def audit_hashes(root: Path) -> dict[str, str]:
    audit_dir = root / BATCH_AUDIT_DIR
    names = ["sandbox_family_audit.csv", "sandbox_family_audit.md"]
    return {name: sha256_file(audit_dir / name) for name in names if (audit_dir / name).exists()}


def strategy_snapshot(root: Path) -> list[dict[str, Any]]:
    return deepcopy(load_yaml(root / REGISTRY_PATH).get("strategies", []))


def source_state(root: Path) -> dict[str, Any]:
    packet_fix = read_json(root / PACKET_FIX_DIR / "sandbox_packet_fix_manifest.json")
    batch_audit = read_json(root / BATCH_AUDIT_DIR / "sandbox_batch_audit_manifest.json")
    batch_manifest = read_json(root / BATCH_DIR / "sandbox_batch_manifest.json")
    family_audit = read_csv(root / BATCH_AUDIT_DIR / "sandbox_family_audit.csv")
    return {
        "packet_fix": packet_fix,
        "batch_audit": batch_audit,
        "batch_manifest": batch_manifest,
        "family_audit": family_audit,
    }


def family_lists(family_rows: list[dict[str, str]]) -> dict[str, list[str]]:
    interesting = [row["family_id"] for row in family_rows if row.get("source_status") == "sandbox_family_interesting"]
    actionable = [row["family_id"] for row in family_rows if row.get("actionable_now") == "True"]
    weak = [row["family_id"] for row in family_rows if row.get("source_status") != "sandbox_family_interesting"]
    return {"interesting": interesting, "actionable": actionable, "weak": weak}


def decide_next_action(state: dict[str, Any]) -> str:
    packet_fix = state["packet_fix"]
    family_info = family_lists(state["family_audit"])
    if not packet_fix.get("repaired_packet_consistency_passed") or not packet_fix.get("packet_required_files_exist_after_fix"):
        return NEXT_ACTION_PAUSE
    if len(family_info["actionable"]) == 1:
        return NEXT_ACTION_FAMILY
    if len(family_info["actionable"]) > 1:
        return NEXT_ACTION_PAUSE
    return NEXT_ACTION_OBJECTIVE_RESET


def packet_fix_acceptance_md(state: dict[str, Any]) -> str:
    packet = state["packet_fix"]
    return f"""# Packet Fix Acceptance Review

1. Is the repaired batch packet now accepted?

Yes. The repaired packet has `repaired_packet_consistency_passed: {packet.get('repaired_packet_consistency_passed')}` and `packet_required_files_exist_after_fix: {packet.get('packet_required_files_exist_after_fix')}`.

- Original packet consistency passed: `{packet.get('original_packet_consistency_passed')}`
- Repaired packet consistency passed: `{packet.get('repaired_packet_consistency_passed')}`
- Required files after repair: `{packet.get('packet_required_files_exist_after_fix')}`
- Repaired packet path: `{packet.get('repaired_packet_path')}`

The packet fix changed no sandbox results, variant statuses, or family audit conclusions.
"""


def research_interpretation_md(state: dict[str, Any]) -> str:
    batch = state["batch_manifest"]
    audit = state["batch_audit"]
    return f"""# Batch 001 Research Interpretation

2. Is batch 001 valid as non-promotable exploration?

Yes. Batch 001 is accepted as non-promotable exploration only.

- Planned variants: `{batch.get('variant_count_planned')}`
- Evaluated variants: `{batch.get('variant_count_evaluated')}`
- Families evaluated: `{batch.get('families_evaluated_count')}`
- Future preregistration candidates: `{batch.get('sandbox_future_preregistration_candidate_count')}`
- Audit promotable-true count: `{audit.get('promotable_true_count')}`
- Audit paper-candidate-allowed true count: `{audit.get('paper_candidate_allowed_true_count')}`
- Forbidden statuses absent: `{audit.get('forbidden_statuses_absent')}`

3. Did batch 001 identify any directly actionable family?

No. The audit found `families_actionable_count: {audit.get('families_actionable_count')}`.

4. Did batch 001 identify useful research clues?

Yes. It identified two useful but not actionable clues: `breakout_continuation` as a possible low-correlation diversifier clue, and `portfolio_combination_sleeve_ensemble` as a warning that combo overlays are likely too close to active combo behavior.
"""


def family_actionability_md(state: dict[str, Any]) -> str:
    rows = state["family_audit"]
    lines = ["# Family Actionability Review", "", "No family is actionable for direct preregistration.", ""]
    direct_answers = {
        "breakout_continuation": "Worth a separate future sleeve/diversifier audit only if framed as contribution diagnostics, not as a candidate. It is not actionable now.",
        "portfolio_combination_sleeve_ensemble": "Too correlated with active combo to pursue now; it risks repackaging the active pair.",
        "volatility_regime": "Repeats the high-upside/high-risk risk-buffer failure pattern; no immediate risk-control study is authorized by this review.",
        "mean_reversion": "Likely needs intraday or shorter-horizon data to be credible, and those remain blocked.",
        "factor_style_rotation": "Mostly repackages equity beta under current objective/risk constraints.",
        "macro_portfolio_contribution": "Useful only as benchmark/control/contribution context, not as an actionable family.",
    }
    for row in rows:
        family_id = row["family_id"]
        lines.append(f"## `{family_id}`")
        lines.append(f"- Source status: `{row.get('source_status')}`")
        lines.append(f"- Actionable now: `{row.get('actionable_now')}`")
        lines.append(f"- Audit conclusion: {row.get('audit_conclusion')}")
        lines.append(f"- Manual-review conclusion: {direct_answers.get(family_id, 'Not actionable now.')}")
        lines.append("")
    return "\n".join(lines)


def batch_002_decision_md(next_action: str) -> str:
    return f"""# Batch 002 Decision Review

11. Should batch 002 be run immediately?

No.

12. If batch 002 is justified, what must change so it is not random search?

It would need a clearly different preregistered purpose, such as objective-reset diagnostics, materially different family templates, or better portfolio-contribution diagnostics. Batch 002 is not justified merely because batch 001 found no candidate.

Decision: do not run or preregister batch 002 in this review.

Selected next action: `{next_action}`
"""


def objective_mismatch_md() -> str:
    return """# Objective Mismatch Review

13. Should the project instead run an objective reset review?

Yes. The repeated pattern is not missing packet evidence or one family needing promotion. The blocker is objective/risk/universe mismatch:

- Higher-upside families tend to fail drawdown and risk-buffer screens.
- Safer or lower-correlation families tend to lag active references.
- Portfolio-combination families tend to duplicate active combo behavior.
- Mean-reversion likely needs shorter-horizon data that remains blocked.

The next review should ask whether the current small-account profit objective, risk limits, ETF-only universe, and daily-data constraint are internally compatible.
"""


def active_observation_md() -> str:
    return """# Active Observation Recommendation

14. Should active VM and active DSR remain the only active/frozen observations?

Yes. Active VM and active DSR remain the only supported active/frozen observations.

No new paper-forward candidate, active strategy, benchmark-control change, or live/real-money path is authorized.
"""


def forbidden_next_steps_md() -> str:
    return """# Forbidden Next Steps

Do not run:

- exploratory sandbox batch 002 directly
- strategy discovery
- backtests
- candidate_exhaustive
- paper-forward review or activation
- provider downloads
- intraday research
- broker/live-order paths
- real-money recommendations

Do not:

- promote the best row
- promote the best family
- loosen gates after results
- add variants to rescue weak families
- create paper-forward candidates from sandbox outputs
"""


def next_action_md(next_action: str) -> str:
    return f"""# Manual Review Next Action

15. What is the single safest next action?

`{next_action}`

Do not run the next action in this manual review task.
"""


def summary_md(manifest: dict[str, Any], family_info: dict[str, list[str]]) -> str:
    return f"""# Manual Review After Sandbox Packet Fix

Manual-review-only: `{manifest['manual_review_only']}`

Packet fix accepted: `{manifest['packet_fix_accepted']}`

Batch 001 accepted as non-promotable exploration: `{manifest['batch_001_accepted_as_non_promotable_exploration']}`

Families actionable count: `{manifest['families_actionable_count']}`

Future preregistration candidate count: `{manifest['future_preregistration_candidate_count']}`

Useful but not actionable clues: `{', '.join(family_info['interesting']) or 'none'}`

Weak/noisy families: `{', '.join(family_info['weak']) or 'none'}`

Objective reset needed: `true`

Next action: `{manifest['next_action']}`

No new sandbox batch, discovery, backtest, provider download, intraday data, candidate_exhaustive, paper-forward action, broker/live path, or real-money recommendation occurred.
"""


def update_metadata(root: Path, output: Path, created_utc: str, manifest: dict[str, Any]) -> tuple[bool, bool, bool]:
    registry_path = root / REGISTRY_PATH
    registry = load_yaml(registry_path)
    metadata = registry.setdefault("registry", {})
    before = deepcopy(metadata)
    metadata.update(
        {
            "manual_review_after_sandbox_packet_fix_path": str(output.resolve()),
            "manual_review_after_sandbox_packet_fix_status": "completed_objective_reset_recommended",
            "manual_review_after_sandbox_packet_fix_created_utc": created_utc,
            "current_research_mode": "manual_review_after_sandbox_packet_fix_completed",
            "current_next_action": manifest["next_action"],
            "official_current_next_action": manifest["next_action"],
            "next_action": manifest["next_action"],
            "manual_review_only": True,
            "sandbox_packet_fix_accepted": manifest["packet_fix_accepted"],
            "batch_001_accepted_as_non_promotable_exploration": manifest["batch_001_accepted_as_non_promotable_exploration"],
            "sandbox_manual_review_families_actionable_count": manifest["families_actionable_count"],
            "sandbox_manual_review_future_preregistration_candidate_count": manifest["future_preregistration_candidate_count"],
            "sandbox_manual_review_no_new_batch_run": True,
            "sandbox_manual_review_no_backtests": True,
            "sandbox_manual_review_no_provider_download": True,
            "sandbox_manual_review_no_intraday_data": True,
            "sandbox_manual_review_no_candidate_exhaustive": True,
            "sandbox_manual_review_no_paper_forward_action": True,
            "sandbox_manual_review_no_real_money_recommendation": True,
        }
    )
    registry_path.write_text(yaml.safe_dump(registry, sort_keys=False, width=120, allow_unicode=False), encoding="utf-8")

    roadmap_path = root / ROADMAP_PATH
    before_roadmap = roadmap_path.read_text(encoding="utf-8") if roadmap_path.exists() else "# Research Roadmap\n"
    compact = f"""## Compact Current State

- Updated UTC: `{created_utc}`
- Current research mode: `manual_review_after_sandbox_packet_fix_completed`
- Official current next action: `{manifest['next_action']}`
- Manual review evidence: `{output.resolve()}`
- Packet fix accepted: `{manifest['packet_fix_accepted']}`
- Batch 001 accepted as non-promotable exploration: `{manifest['batch_001_accepted_as_non_promotable_exploration']}`
- Families actionable count: `{manifest['families_actionable_count']}`
- Future preregistration candidate count: `{manifest['future_preregistration_candidate_count']}`
- Objective reset review needed: `true`
- Active VM and active DSR remain the only active/frozen observations.
- `static_all_weather_benchmark_v1` remains benchmark/control only.
- Exact rejected variants remain closed.
- Intraday remains paused: `true`
- This manual review did not run a new sandbox batch, discovery, backtest, new metric, provider download, intraday data, candidate_exhaustive, paper-forward action, broker/live path, or real-money recommendation.
"""
    section = f"""## Manual Review After Sandbox Packet Fix

- Created UTC: `{created_utc}`
- Evidence path: `{output.resolve()}`
- Packet fix accepted: `{manifest['packet_fix_accepted']}`
- Batch 001 accepted as non-promotable exploration: `{manifest['batch_001_accepted_as_non_promotable_exploration']}`
- Families actionable count: `{manifest['families_actionable_count']}`
- Future preregistration candidate count: `{manifest['future_preregistration_candidate_count']}`
- Decision: current blocker is objective/risk/universe mismatch rather than one actionable family.
- Next action: `{manifest['next_action']}`
- Do not run the next action in this manual review task.
"""
    after_roadmap = replace_or_append_section(before_roadmap, "## Compact Current State", compact)
    after_roadmap = replace_or_append_section(after_roadmap, "## Manual Review After Sandbox Packet Fix", section)
    write_text(roadmap_path, after_roadmap)

    compact_path = root / COMPACT_STATE_PATH
    before_compact = compact_path.read_text(encoding="utf-8") if compact_path.exists() else ""
    after_compact = f"""# Current Tournament State

Created UTC: `{created_utc}`

Current research mode: `manual_review_after_sandbox_packet_fix_completed`

Current next action: `{manifest['next_action']}`

Manual review evidence: `{output.resolve()}`

## Decision

- Packet fix accepted: `{manifest['packet_fix_accepted']}`
- Batch 001 accepted as non-promotable exploration: `{manifest['batch_001_accepted_as_non_promotable_exploration']}`
- Families actionable count: `{manifest['families_actionable_count']}`
- Future preregistration candidate count: `{manifest['future_preregistration_candidate_count']}`
- Single safest next action: `{manifest['next_action']}`

## Protected State

- `paper_forward_vm_quality_lowvol_proxy_v1` remains active/accepted/frozen.
- `paper_forward_dsr_sector_equal_weight_defensive_filter_v1` remains active/accepted/frozen.
- `static_all_weather_benchmark_v1` remains benchmark/control only.
- Exact rejected variants remain closed.
- Intraday research remains paused.

## Forbidden Actions

- No new sandbox batch was run by this review.
- No strategy discovery, new backtest, or new performance metric computation.
- No candidate_exhaustive.
- No paper-forward review or activation.
- No provider download.
- No intraday data use.
- No indicator library dependency.
- No broker/live-order path or order action.
- No real-money recommendation.
"""
    write_text(compact_path, after_compact)
    return before != metadata, before_roadmap != after_roadmap, before_compact != after_compact


def replace_or_append_section(text: str, header: str, section: str) -> str:
    if header not in text:
        return text.rstrip() + "\n\n" + section.rstrip() + "\n"
    start = text.index(header)
    next_start = text.find("\n## ", start + len(header))
    if next_start == -1:
        return text[:start].rstrip() + "\n\n" + section.rstrip() + "\n"
    return text[:start].rstrip() + "\n\n" + section.rstrip() + "\n\n" + text[next_start + 1 :].lstrip()


def consistency_check(manifest: dict[str, Any], output: Path) -> dict[str, Any]:
    check = {
        "manual_review_only": manifest["manual_review_only"] is True,
        "no_new_sandbox_batch": manifest["new_sandbox_batch_run"] is False,
        "no_formal_strategy_discovery": manifest["strategy_discovery_run"] is False and manifest["formal_discovery_run"] is False,
        "no_new_backtests": manifest["new_backtests_run"] is False,
        "no_new_performance_metrics": manifest["new_performance_metrics_computed"] is False,
        "sandbox_results_unchanged": manifest["sandbox_results_changed"] is False,
        "variant_statuses_unchanged": manifest["variant_statuses_changed"] is False,
        "family_audit_unchanged": manifest["family_audit_changed"] is False,
        "no_future_preregistration_candidates_created": manifest["future_preregistration_candidates_created"] is False,
        "no_indicator_library_dependency_added": manifest["indicator_library_dependency_added"] is False,
        "no_provider_download": manifest["provider_download"] is False,
        "no_intraday_data_used": manifest["intraday_data_used"] is False,
        "no_candidate_exhaustive": manifest["candidate_exhaustive_run"] is False,
        "no_paper_forward_action": manifest["paper_forward_review"] is False and manifest["paper_forward_activation"] is False,
        "no_broker_live_action": manifest["broker_orders_submitted"] is False
        and manifest["broker_orders_cancelled"] is False
        and manifest["live_orders"] is False,
        "no_real_money_recommendation": manifest["real_money_recommendation"] is False,
        "active_strategy_state_preserved": manifest["active_strategy_state_changed"] is False,
        "rejected_strategy_state_preserved": manifest["rejected_strategy_state_changed"] is False,
        "exact_rejected_variants_not_reopened": manifest["exact_rejected_variants_reopened"] is False,
        "intraday_remains_paused": manifest["intraday_research_remains_paused"] is True,
        "sandbox_results_remain_non_promotable": manifest["sandbox_results_remain_non_promotable"] is True,
        "sandbox_cannot_create_paper_candidates": manifest["sandbox_can_create_paper_candidates"] is False,
        "packet_fix_accepted": manifest["packet_fix_accepted"] is True,
        "batch_001_accepted_as_non_promotable_exploration": manifest["batch_001_accepted_as_non_promotable_exploration"] is True,
        "next_action_valid": manifest["next_action"] in VALID_NEXT_ACTIONS,
        "manifest_flags_match_strict_scope": all(manifest.get(key) == value for key, value in MANIFEST_FLAGS.items()),
        "required_files_exist": all((output / name).exists() for name in REQUIRED_FILES),
    }
    check["consistency_passed"] = all(check.values())
    return check


def run_manual_review(root: Path = ROOT) -> dict[str, Any]:
    root = root.resolve()
    created_utc = now_utc()
    output = root / OUTPUT_DIR
    output.mkdir(parents=True, exist_ok=True)
    before_strategies = strategy_snapshot(root)
    batch_hashes_before = batch_result_hashes(root)
    audit_hashes_before = audit_hashes(root)
    state = source_state(root)
    family_info = family_lists(state["family_audit"])
    next_action = decide_next_action(state)
    manifest = {
        "created_utc": created_utc,
        "output_dir": str(output.resolve()),
        **MANIFEST_FLAGS,
        "packet_fix_accepted": bool(
            state["packet_fix"].get("repaired_packet_consistency_passed")
            and state["packet_fix"].get("packet_required_files_exist_after_fix")
        ),
        "batch_001_accepted_as_non_promotable_exploration": bool(
            state["batch_audit"].get("sandbox_results_remain_non_promotable")
            and state["batch_audit"].get("forbidden_statuses_absent")
            and state["batch_audit"].get("promotable_true_count") == 0
            and state["batch_audit"].get("paper_candidate_allowed_true_count") == 0
        ),
        "families_actionable_count": len(family_info["actionable"]),
        "future_preregistration_candidate_count": int(
            state["packet_fix"].get("source_future_preregistration_candidate_count")
            or state["batch_audit"].get("source_future_preregistration_candidate_count")
            or 0
        ),
        "batch_002_immediately_justified": False,
        "objective_reset_needed": True,
        "active_vm_dsr_observation_recommended": True,
        "next_action": next_action,
    }
    write_json(output / "manual_review_after_packet_fix_manifest.json", manifest)
    write_text(output / "packet_fix_acceptance_review.md", packet_fix_acceptance_md(state))
    write_text(output / "batch_001_research_interpretation.md", research_interpretation_md(state))
    write_text(output / "family_actionability_review.md", family_actionability_md(state))
    write_text(output / "batch_002_decision_review.md", batch_002_decision_md(next_action))
    write_text(output / "objective_mismatch_review.md", objective_mismatch_md())
    write_text(output / "active_observation_recommendation.md", active_observation_md())
    write_text(output / "forbidden_next_steps.md", forbidden_next_steps_md())
    write_text(output / "manual_review_next_action.md", next_action_md(next_action))
    write_text(output / "manual_review_after_packet_fix_summary.md", summary_md(manifest, family_info))
    write_json(output / "manual_review_after_packet_fix_consistency_check.json", {"consistency_passed": False})
    batch_hashes_after = batch_result_hashes(root)
    audit_hashes_after = audit_hashes(root)
    after_strategies = strategy_snapshot(root)
    manifest["sandbox_results_changed"] = batch_hashes_before != batch_hashes_after
    manifest["family_audit_changed"] = audit_hashes_before != audit_hashes_after
    if before_strategies != after_strategies:
        manifest["active_strategy_state_changed"] = True
        manifest["rejected_strategy_state_changed"] = True
    registry_updated, roadmap_updated, compact_updated = update_metadata(root, output, created_utc, manifest)
    manifest["registry_metadata_updated"] = registry_updated
    manifest["roadmap_updated"] = roadmap_updated
    manifest["compact_state_updated"] = compact_updated
    consistency = consistency_check(manifest, output)
    write_json(output / "manual_review_after_packet_fix_manifest.json", manifest)
    write_json(output / "manual_review_after_packet_fix_consistency_check.json", consistency)
    return {
        "output_dir": str(output),
        "packet_fix_accepted": manifest["packet_fix_accepted"],
        "batch_001_accepted_as_non_promotable_exploration": manifest["batch_001_accepted_as_non_promotable_exploration"],
        "families_actionable_count": manifest["families_actionable_count"],
        "future_preregistration_candidate_count": manifest["future_preregistration_candidate_count"],
        "objective_reset_needed": manifest["objective_reset_needed"],
        "next_action": manifest["next_action"],
        "consistency_passed": consistency["consistency_passed"],
    }
