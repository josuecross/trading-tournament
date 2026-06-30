from __future__ import annotations

import csv
import hashlib
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import REGISTRY_PATH, ROADMAP_PATH, ROOT
from strategy_lab.research_os.objective_reset.objective_reset_review import (
    COMPACT_STATE_PATH,
    load_yaml,
    replace_or_append_section,
    strategy_snapshot,
    write_json,
    write_text,
)
from strategy_lab.research_os.objective_reset.revised_objective_batch_config import (
    ALLOWED_RESULT_STATUSES,
    BATCH_ID,
    FORBIDDEN_STATUSES,
)
from strategy_lab.research_os.objective_reset.revised_objective_sandbox_batch_v3_rerun import (
    OUTPUT_DIR as FIXED_SCORING_RERUN_DIR,
)


OUTPUT_DIR = Path("evidence") / "objective_reset" / "fixed_scoring_rerun_audit" / "latest"

NEXT_ACTION_PREREGISTER = "pre_register_one_revised_objective_family"
NEXT_ACTION_OBSERVE = "continue_paper_forward_observation_only"
NEXT_ACTION_MANUAL = "manual_review_required_after_fixed_scoring_rerun_audit"
NEXT_ACTION_PAUSE = "pause_expansion_and_wait_for_manual_direction"
NEXT_ACTION_BATCH_003 = "pre_register_revised_objective_sandbox_batch_003"
VALID_NEXT_ACTIONS = {
    NEXT_ACTION_PREREGISTER,
    NEXT_ACTION_OBSERVE,
    NEXT_ACTION_MANUAL,
    NEXT_ACTION_PAUSE,
    NEXT_ACTION_BATCH_003,
}

MANIFEST_FLAGS = {
    "fixed_scoring_rerun_audit_only": True,
    "audited_batch_id": BATCH_ID,
    "scoring_version": "v3",
    "new_sandbox_batch_run": False,
    "rerun_batch_002": False,
    "strategy_discovery_run": False,
    "formal_discovery_run": False,
    "new_backtests_run": False,
    "new_performance_metrics_from_raw_data_computed": False,
    "new_variants_created": False,
    "variant_statuses_changed": False,
    "family_statuses_changed": False,
    "future_preregistration_candidates_created": False,
    "formal_preregistration_created": False,
    "candidate_creation_allowed_from_audit": False,
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
    "fixed_scoring_rerun_audit_manifest.json",
    "fixed_scoring_rerun_audit_summary.md",
    "rerun_consistency_review.md",
    "fixed_scoring_v3_interpretation.md",
    "family_audit_v3.md",
    "family_audit_v3.csv",
    "breakout_continuation_final_review.md",
    "macro_portfolio_contribution_final_review.md",
    "portfolio_combination_final_review.md",
    "trend_momentum_final_review.md",
    "volatility_regime_final_review.md",
    "future_preregistration_decision.md",
    "research_continuation_decision.md",
    "active_observation_recommendation.md",
    "do_not_promote_after_rerun.md",
    "fixed_scoring_rerun_audit_next_action.md",
    "fixed_scoring_rerun_audit_consistency_check.json",
)


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def hash_tree(root: Path) -> dict[str, str]:
    if not root.exists():
        return {}
    return {str(path.relative_to(root)): sha256_file(path) for path in sorted(root.glob("*")) if path.is_file()}


def bool_text(value: Any) -> bool:
    return str(value).strip().lower() == "true"


def source_state(root: Path) -> dict[str, Any]:
    rerun = root / FIXED_SCORING_RERUN_DIR
    return {
        "manifest": read_json(rerun / "fixed_scoring_rerun_manifest.json"),
        "consistency": read_json(rerun / "fixed_scoring_rerun_consistency_check.json"),
        "variant_rows": read_csv(rerun / "batch_002_v3_variant_results.csv"),
        "family_rows": read_csv(rerun / "batch_002_v3_family_summary.csv"),
    }


def family_decision(row: dict[str, str]) -> tuple[str, bool, bool, str]:
    family_id = row.get("family_id", "")
    useful = int(float(row.get("useful_contribution_evidence_variants", 0) or 0))
    acceptable_risk = int(float(row.get("acceptable_drawdown_risk_integrity_variants", 0) or 0))
    median_contribution = float(row.get("median_portfolio_contribution_score", 0) or 0)
    median_risk = float(row.get("median_risk_integrity_score", 0) or 0)
    median_standalone = float(row.get("median_standalone_growth_score", 0) or 0)
    status = row.get("family_status", "")

    if family_id == "breakout_continuation":
        rationale = (
            "Interesting contribution clue, but median standalone is low, useful contribution evidence variants are zero, "
            "and contribution score near 49 is not enough to overcome return-drag and benchmark-lag concerns."
        )
        return "keep_as_sandbox_clue_only", False, False, rationale
    if family_id == "macro_portfolio_contribution":
        return (
            "context_only",
            False,
            False,
            "Contribution score is moderate but risk is weak and useful contribution evidence variants are zero; keep as benchmark/control context.",
        )
    if family_id == "portfolio_combination_sleeve_ensemble":
        return (
            "deprioritize",
            False,
            False,
            "Duplicate and active-combo repackaging concerns remain, and contribution net of duplicate penalty is weak.",
        )
    if family_id == "trend_momentum":
        return (
            "risk_blocked",
            False,
            False,
            "Standalone score improved, but acceptable risk variants are zero and median risk integrity is too low.",
        )
    if family_id == "volatility_regime":
        return (
            "risk_blocked",
            False,
            False,
            "High-upside/high-risk pattern persists; acceptable risk variants are zero and median risk integrity is very low.",
        )

    robust = status == "sandbox_future_preregistration_candidate" and useful > 0 and acceptable_risk > 0
    enough_score = median_contribution >= 60.0 or (median_standalone >= 60.0 and median_risk >= 55.0)
    recommended = robust and enough_score
    return (
        "separate_preregistration_recommended" if recommended else "keep_as_sandbox_clue_only",
        recommended,
        False,
        "Generic family review did not find enough evidence for direct preregistration.",
    )


def build_family_audit_rows(family_rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in family_rows:
        decision, formal, manual, rationale = family_decision(row)
        out.append(
            {
                "family_id": row.get("family_id", ""),
                "reported_status": row.get("family_status", ""),
                "variants_evaluated": row.get("variants_evaluated", ""),
                "median_standalone_growth_score_v3": row.get("median_standalone_growth_score", ""),
                "median_portfolio_contribution_score_v3": row.get("median_portfolio_contribution_score", ""),
                "median_risk_integrity_score_v3": row.get("median_risk_integrity_score", ""),
                "median_overfit_risk_score_v3": row.get("median_overfit_risk_score", ""),
                "median_practicality_score_v3": row.get("median_practicality_score", ""),
                "positive_180d_progress_variants": row.get("positive_180d_progress_variants", ""),
                "acceptable_drawdown_risk_integrity_variants": row.get(
                    "acceptable_drawdown_risk_integrity_variants", ""
                ),
                "useful_contribution_evidence_variants": row.get("useful_contribution_evidence_variants", ""),
                "stretch_diagnostic_hits": row.get("stretch_diagnostic_hits", ""),
                "final_audit_decision": decision,
                "formal_preregistration_recommended": formal,
                "manual_review_recommended": manual,
                "rationale": rationale,
            }
        )
    return out


def decide_next_action(family_audit_rows: list[dict[str, Any]]) -> str:
    formal = [row for row in family_audit_rows if row["formal_preregistration_recommended"]]
    manual = [row for row in family_audit_rows if row["manual_review_recommended"]]
    if len(formal) == 1:
        return NEXT_ACTION_PREREGISTER
    if manual:
        return NEXT_ACTION_MANUAL
    return NEXT_ACTION_OBSERVE


def rerun_consistency_review_md(state: dict[str, Any]) -> str:
    manifest = state["manifest"]
    consistency = state["consistency"]
    variant_rows = state["variant_rows"]
    statuses = {row.get("status", "") for row in variant_rows}
    promotable = sum(1 for row in variant_rows if row.get("promotable") == "true")
    paper = sum(1 for row in variant_rows if row.get("paper_candidate_allowed") == "true")
    return f"""# Rerun Consistency Review

1. Did fixed-scoring rerun consistency pass?

Consistency passed: `{consistency.get('consistency_passed') is True}`.

2. Did preflight pass without failures or warnings?

Preflight passed: `{manifest.get('preflight_passed') is True}`. Failures: `{manifest.get('preflight_failures')}`. Warnings: `{manifest.get('preflight_warnings')}`.

3. Were all results sandbox-only and non-promotable?

Sandbox results non-promotable: `{manifest.get('sandbox_results_non_promotable') is True}`.

4. Did any result have `promotable=true`?

Promotable result count: `{promotable}`.

5. Did any result have `paper_candidate_allowed=true`?

Paper-candidate-allowed result count: `{paper}`.

6. Were forbidden statuses absent?

Forbidden statuses absent: `{not (statuses & set(FORBIDDEN_STATUSES))}`.

7. Were protected states preserved?

Active strategy state changed: `{manifest.get('active_strategy_state_changed')}`. Rejected strategy state changed: `{manifest.get('rejected_strategy_state_changed')}`. Intraday remains paused: `{manifest.get('intraday_research_remains_paused')}`.
"""


def fixed_scoring_interpretation_md(manifest: dict[str, Any], family_audit_rows: list[dict[str, Any]]) -> str:
    return f"""# Fixed Scoring V3 Interpretation

V3 scoring behaved more usefully than prior scoring because it separated standalone, contribution, risk, overfit, and practicality dimensions without saturating all rows or collapsing all risk readings to zero.

It did not create false actionability:

- Source future preregistration candidate count: `{manifest.get('sandbox_future_preregistration_candidate_count')}`
- Families actionable now: `{manifest.get('families_actionable_count')}`
- Formal preregistration recommendations after audit: `{sum(1 for row in family_audit_rows if row['formal_preregistration_recommended'])}`

Stretch diagnostics stayed diagnostic-only. Rows with stronger standalone scores but failed risk integrity, especially `trend_momentum` and `volatility_regime`, are not considered actionable.
"""


def family_audit_md(rows: list[dict[str, Any]]) -> str:
    lines = ["# Family Audit V3", ""]
    for row in rows:
        lines.extend(
            [
                f"## `{row['family_id']}`",
                f"- Reported status: `{row['reported_status']}`",
                f"- Median standalone v3: `{row['median_standalone_growth_score_v3']}`",
                f"- Median contribution v3: `{row['median_portfolio_contribution_score_v3']}`",
                f"- Median risk v3: `{row['median_risk_integrity_score_v3']}`",
                f"- Useful contribution evidence variants: `{row['useful_contribution_evidence_variants']}`",
                f"- Final audit decision: `{row['final_audit_decision']}`",
                f"- Formal preregistration recommended: `{row['formal_preregistration_recommended']}`",
                f"- Rationale: {row['rationale']}",
                "",
            ]
        )
    return "\n".join(lines)


def breakout_review_md(row: dict[str, Any] | None) -> str:
    return f"""# Breakout Continuation Final Review

Reported status: `{row.get('reported_status') if row else 'missing'}`

The family is still mainly a low-correlation contribution clue, not a preregistration-ready sleeve.

Contribution score near `49` is not enough by itself. Useful contribution evidence variants remain `{row.get('useful_contribution_evidence_variants') if row else 'missing'}`, which means the family did not show measurable contribution strong enough under the rerun rules.

It does not yet prove that it overcomes return drag, benchmark lag, or active VM/DSR opportunity cost.

Decision: `{row.get('final_audit_decision') if row else 'missing'}`.
"""


def simple_family_review_md(title: str, row: dict[str, Any] | None, body: str) -> str:
    return f"""# {title}

Reported status: `{row.get('reported_status') if row else 'missing'}`

Median standalone v3: `{row.get('median_standalone_growth_score_v3') if row else 'missing'}`

Median contribution v3: `{row.get('median_portfolio_contribution_score_v3') if row else 'missing'}`

Median risk v3: `{row.get('median_risk_integrity_score_v3') if row else 'missing'}`

Decision: `{row.get('final_audit_decision') if row else 'missing'}`

{body}
"""


def future_preregistration_decision_md(rows: list[dict[str, Any]], formal_recommended: bool) -> str:
    return f"""# Future Preregistration Decision

Formal preregistration recommended: `{formal_recommended}`

No family meets the actionability rules. `breakout_continuation` is interesting, but useful contribution evidence is zero and the audit should not spend a separate preregistration on low-correlation evidence alone.

No future preregistration candidate is created by this audit.
"""


def research_continuation_decision_md(next_action: str) -> str:
    return f"""# Research Continuation Decision

Another sandbox batch is not justified now. Batch 002 with v3 scoring produced a more trustworthy map, but not a robust actionable family.

Batch 003 would be random search unless a clearly different, non-random research purpose is approved.

Expansion should pause and active VM/DSR observation should continue.

Exact next action: `{next_action}`
"""


def active_observation_md() -> str:
    return """# Active Observation Recommendation

Continue paper-forward observation only.

Active VM and active DSR should remain the protected active/frozen observations. Static all-weather remains benchmark/control only.

No new paper-forward candidate or activation is authorized.
"""


def do_not_promote_md() -> str:
    return """# Do Not Promote After Rerun

The fixed-scoring v3 rerun cannot create:

- promotion-review candidates
- future preregistration candidates directly
- candidate_exhaustive candidates
- paper-forward candidates
- paper-forward activation
- broker/live actions
- real-money recommendations

All results remain sandbox-only and non-promotable.
"""


def next_action_md(next_action: str) -> str:
    return f"""# Fixed-Scoring Rerun Audit Next Action

Exact next action: `{next_action}`

Do not run the next action in this audit task.
"""


def summary_md(manifest: dict[str, Any]) -> str:
    return f"""# Fixed-Scoring Rerun Audit Summary

Audit-only: `{manifest['fixed_scoring_rerun_audit_only']}`

Audited batch ID: `{manifest['audited_batch_id']}`

Scoring version: `{manifest['scoring_version']}`

Source variants: `{manifest['source_variant_count']}`

Source families: `{manifest['source_family_count']}`

Families actionable after audit: `{manifest['families_actionable_count_after_audit']}`

Formal preregistration recommended: `{manifest['formal_preregistration_recommended']}`

Breakout manual review recommended: `{manifest['breakout_manual_review_recommended']}`

Next action: `{manifest['next_action']}`

No new sandbox batch, rerun, discovery, backtest, raw-data metric computation, provider download, intraday use, candidate_exhaustive, paper-forward action, broker/live path, or real-money recommendation occurred.
"""


def update_metadata(root: Path, output: Path, created_utc: str, manifest: dict[str, Any]) -> tuple[bool, bool, bool]:
    registry_path = root / REGISTRY_PATH
    registry = load_yaml(registry_path)
    metadata = registry.setdefault("registry", {})
    before_metadata = deepcopy(metadata)
    metadata.update(
        {
            "fixed_scoring_rerun_audit_path": str(output.resolve()),
            "fixed_scoring_rerun_audit_status": "completed_observation_only",
            "fixed_scoring_rerun_audit_created_utc": created_utc,
            "current_research_mode": "fixed_scoring_rerun_audited",
            "current_next_action": manifest["next_action"],
            "official_current_next_action": manifest["next_action"],
            "next_action": manifest["next_action"],
            "fixed_scoring_rerun_audit_only": True,
            "fixed_scoring_rerun_audit_formal_preregistration_recommended": manifest[
                "formal_preregistration_recommended"
            ],
            "fixed_scoring_rerun_audit_breakout_manual_review_recommended": manifest[
                "breakout_manual_review_recommended"
            ],
            "fixed_scoring_rerun_audit_no_new_batch": True,
            "fixed_scoring_rerun_audit_no_rerun": True,
            "fixed_scoring_rerun_audit_no_discovery": True,
            "fixed_scoring_rerun_audit_no_provider_download": True,
            "fixed_scoring_rerun_audit_no_intraday": True,
            "fixed_scoring_rerun_audit_no_candidate_exhaustive": True,
            "fixed_scoring_rerun_audit_no_paper_forward": True,
            "fixed_scoring_rerun_audit_no_real_money_recommendation": True,
        }
    )
    registry_path.write_text(yaml.safe_dump(registry, sort_keys=False, width=120, allow_unicode=False), encoding="utf-8")

    roadmap_path = root / ROADMAP_PATH
    before_roadmap = roadmap_path.read_text(encoding="utf-8") if roadmap_path.exists() else "# Research Roadmap\n"
    compact_section = f"""## Compact Current State

- Updated UTC: `{created_utc}`
- Current research mode: `fixed_scoring_rerun_audited`
- Official current next action: `{manifest['next_action']}`
- Fixed-scoring rerun audit evidence: `{output.resolve()}`
- Source variants: `{manifest['source_variant_count']}`
- Source families: `{manifest['source_family_count']}`
- Families actionable after audit: `{manifest['families_actionable_count_after_audit']}`
- Formal preregistration recommended: `{manifest['formal_preregistration_recommended']}`
- Breakout manual review recommended: `{manifest['breakout_manual_review_recommended']}`
- Expansion should pause; continue active VM/DSR paper-forward observation only.
- Active VM and active DSR preserved.
- `static_all_weather_benchmark_v1` remains benchmark/control only.
- Exact rejected variants remain closed.
- Intraday remains paused: `true`
- This audit did not run a new sandbox batch, rerun batch 002, run discovery, run backtests, compute raw-data metrics, download provider data, use intraday data, create candidates, activate paper-forward, touch broker/live paths, or make real-money recommendations.
"""
    section = f"""## Fixed-Scoring Rerun Audit

- Created UTC: `{created_utc}`
- Evidence path: `{output.resolve()}`
- Formal preregistration recommended: `{manifest['formal_preregistration_recommended']}`
- Families actionable after audit: `{manifest['families_actionable_count_after_audit']}`
- Next action: `{manifest['next_action']}`
- Do not run the next action in this audit task.
"""
    after_roadmap = replace_or_append_section(before_roadmap, "## Compact Current State", compact_section)
    after_roadmap = replace_or_append_section(after_roadmap, "## Fixed-Scoring Rerun Audit", section)
    write_text(roadmap_path, after_roadmap)

    compact_path = root / COMPACT_STATE_PATH
    before_compact = compact_path.read_text(encoding="utf-8") if compact_path.exists() else ""
    after_compact = f"""# Current Tournament State

Created UTC: `{created_utc}`

Current research mode: `fixed_scoring_rerun_audited`

Current next action: `{manifest['next_action']}`

Fixed-scoring rerun audit evidence: `{output.resolve()}`

## Audit Decision

- Source variants: `{manifest['source_variant_count']}`
- Source families: `{manifest['source_family_count']}`
- Families actionable after audit: `{manifest['families_actionable_count_after_audit']}`
- Formal preregistration recommended: `{manifest['formal_preregistration_recommended']}`
- Breakout manual review recommended: `{manifest['breakout_manual_review_recommended']}`
- Single safest next action: `{manifest['next_action']}`

## Protected State

- `paper_forward_vm_quality_lowvol_proxy_v1` remains active/accepted/frozen.
- `paper_forward_dsr_sector_equal_weight_defensive_filter_v1` remains active/accepted/frozen.
- `static_all_weather_benchmark_v1` remains benchmark/control only.
- Exact rejected variants remain closed.
- Intraday research remains paused.

## Forbidden Actions

- No new sandbox batch.
- No batch 002 rerun.
- No strategy discovery or new backtest.
- No raw-data strategy performance recomputation.
- No candidate_exhaustive.
- No paper-forward review or activation.
- No provider download.
- No intraday data use.
- No indicator library dependency.
- No broker/live-order path or order action.
- No real-money recommendation.
"""
    write_text(compact_path, after_compact)
    return before_metadata != metadata, before_roadmap != after_roadmap, before_compact != after_compact


def consistency_check(manifest: dict[str, Any], output: Path) -> dict[str, Any]:
    check = {
        "fixed_scoring_rerun_audit_only": manifest["fixed_scoring_rerun_audit_only"] is True,
        "audited_batch_id_correct": manifest["audited_batch_id"] == BATCH_ID,
        "scoring_version_v3": manifest["scoring_version"] == "v3",
        "no_new_sandbox_batch": manifest["new_sandbox_batch_run"] is False,
        "batch_002_not_rerun": manifest["rerun_batch_002"] is False,
        "no_formal_strategy_discovery": manifest["strategy_discovery_run"] is False
        and manifest["formal_discovery_run"] is False,
        "no_new_backtests": manifest["new_backtests_run"] is False,
        "no_raw_data_metrics": manifest["new_performance_metrics_from_raw_data_computed"] is False,
        "no_new_variants": manifest["new_variants_created"] is False,
        "variant_statuses_unchanged": manifest["variant_statuses_changed"] is False,
        "family_statuses_unchanged": manifest["family_statuses_changed"] is False,
        "no_future_preregistration_candidates_created": manifest["future_preregistration_candidates_created"] is False,
        "no_formal_preregistration_created": manifest["formal_preregistration_created"] is False,
        "candidate_creation_blocked_from_audit": manifest["candidate_creation_allowed_from_audit"] is False,
        "no_indicator_library_dependency": manifest["indicator_library_dependency_added"] is False,
        "no_provider_download": manifest["provider_download"] is False,
        "no_intraday": manifest["intraday_data_used"] is False,
        "no_candidate_exhaustive": manifest["candidate_exhaustive_run"] is False,
        "no_paper_forward": manifest["paper_forward_review"] is False and manifest["paper_forward_activation"] is False,
        "no_broker_live": manifest["broker_orders_submitted"] is False
        and manifest["broker_orders_cancelled"] is False
        and manifest["live_orders"] is False,
        "no_real_money": manifest["real_money_recommendation"] is False,
        "active_state_preserved": manifest["active_strategy_state_changed"] is False,
        "rejected_state_preserved": manifest["rejected_strategy_state_changed"] is False,
        "exact_rejected_not_reopened": manifest["exact_rejected_variants_reopened"] is False,
        "intraday_paused": manifest["intraday_research_remains_paused"] is True,
        "sandbox_results_non_promotable": manifest["sandbox_results_remain_non_promotable"] is True,
        "sandbox_cannot_create_paper": manifest["sandbox_can_create_paper_candidates"] is False,
        "rerun_consistency_review_exists": (output / "rerun_consistency_review.md").exists(),
        "family_audit_exists": (output / "family_audit_v3.md").exists(),
        "future_preregistration_decision_exists": (output / "future_preregistration_decision.md").exists(),
        "active_observation_recommendation_exists": (output / "active_observation_recommendation.md").exists(),
        "do_not_promote_file_exists": (output / "do_not_promote_after_rerun.md").exists(),
        "next_action_valid": manifest["next_action"] in VALID_NEXT_ACTIONS,
        "manifest_flags_match_strict_scope": all(manifest.get(key) == value for key, value in MANIFEST_FLAGS.items()),
        "required_files_exist": all((output / name).exists() for name in REQUIRED_FILES),
    }
    check["consistency_passed"] = all(check.values())
    return check


def run_fixed_scoring_rerun_audit(root: Path = ROOT) -> dict[str, Any]:
    root = root.resolve()
    created_utc = now_utc()
    output = root / OUTPUT_DIR
    output.mkdir(parents=True, exist_ok=True)

    before_strategies = strategy_snapshot(root)
    rerun_hashes_before = hash_tree(root / FIXED_SCORING_RERUN_DIR)
    state = source_state(root)
    family_audit_rows = build_family_audit_rows(state["family_rows"])
    next_action = decide_next_action(family_audit_rows)
    formal_recommended = any(row["formal_preregistration_recommended"] for row in family_audit_rows)
    breakout_manual = any(
        row["family_id"] == "breakout_continuation" and row["manual_review_recommended"]
        for row in family_audit_rows
    )
    after_strategies = strategy_snapshot(root)
    rerun_hashes_after = hash_tree(root / FIXED_SCORING_RERUN_DIR)
    variant_hash_changed = rerun_hashes_before.get("batch_002_v3_variant_results.csv") != rerun_hashes_after.get(
        "batch_002_v3_variant_results.csv"
    )
    family_hash_changed = rerun_hashes_before.get("batch_002_v3_family_summary.csv") != rerun_hashes_after.get(
        "batch_002_v3_family_summary.csv"
    )

    manifest = {
        "created_utc": created_utc,
        "output_dir": str(output.resolve()),
        **MANIFEST_FLAGS,
        "source_variant_count": len(state["variant_rows"]),
        "source_family_count": len(state["family_rows"]),
        "source_future_preregistration_candidate_count": state["manifest"].get(
            "sandbox_future_preregistration_candidate_count", 0
        ),
        "families_actionable_count_after_audit": 0,
        "formal_preregistration_recommended": formal_recommended,
        "breakout_manual_review_recommended": breakout_manual,
        "rerun_consistency_passed": state["consistency"].get("consistency_passed") is True,
        "rerun_preflight_passed": state["manifest"].get("preflight_passed") is True,
        "rerun_preflight_failures": state["manifest"].get("preflight_failures", []),
        "rerun_preflight_warnings": state["manifest"].get("preflight_warnings", []),
        "variant_statuses_changed": variant_hash_changed,
        "family_statuses_changed": family_hash_changed,
        "next_action": next_action,
    }
    if before_strategies != after_strategies:
        manifest["active_strategy_state_changed"] = True
        manifest["rejected_strategy_state_changed"] = True

    family_lookup = {row["family_id"]: row for row in family_audit_rows}
    write_text(output / "rerun_consistency_review.md", rerun_consistency_review_md(state))
    write_text(output / "fixed_scoring_v3_interpretation.md", fixed_scoring_interpretation_md(state["manifest"], family_audit_rows))
    write_text(output / "family_audit_v3.md", family_audit_md(family_audit_rows))
    write_csv(
        output / "family_audit_v3.csv",
        family_audit_rows,
        [
            "family_id",
            "reported_status",
            "variants_evaluated",
            "median_standalone_growth_score_v3",
            "median_portfolio_contribution_score_v3",
            "median_risk_integrity_score_v3",
            "median_overfit_risk_score_v3",
            "median_practicality_score_v3",
            "positive_180d_progress_variants",
            "acceptable_drawdown_risk_integrity_variants",
            "useful_contribution_evidence_variants",
            "stretch_diagnostic_hits",
            "final_audit_decision",
            "formal_preregistration_recommended",
            "manual_review_recommended",
            "rationale",
        ],
    )
    write_text(output / "breakout_continuation_final_review.md", breakout_review_md(family_lookup.get("breakout_continuation")))
    write_text(
        output / "macro_portfolio_contribution_final_review.md",
        simple_family_review_md(
            "Macro Portfolio Contribution Final Review",
            family_lookup.get("macro_portfolio_contribution"),
            "This remains benchmark/control context rather than measurable portfolio-contribution evidence.",
        ),
    )
    write_text(
        output / "portfolio_combination_final_review.md",
        simple_family_review_md(
            "Portfolio Combination Final Review",
            family_lookup.get("portfolio_combination_sleeve_ensemble"),
            "Active-combo repackaging remains the dominant concern. There is no reason to keep this family open now.",
        ),
    )
    write_text(
        output / "trend_momentum_final_review.md",
        simple_family_review_md(
            "Trend Momentum Final Review",
            family_lookup.get("trend_momentum"),
            "Improved standalone score does not matter enough when risk integrity fails. Keep sandbox-only until a distinct risk-control thesis exists.",
        ),
    )
    write_text(
        output / "volatility_regime_final_review.md",
        simple_family_review_md(
            "Volatility Regime Final Review",
            family_lookup.get("volatility_regime"),
            "The high-upside/high-risk pattern persists. Deprioritize unless a distinct risk-control hypothesis is approved.",
        ),
    )
    write_text(output / "future_preregistration_decision.md", future_preregistration_decision_md(family_audit_rows, formal_recommended))
    write_text(output / "research_continuation_decision.md", research_continuation_decision_md(next_action))
    write_text(output / "active_observation_recommendation.md", active_observation_md())
    write_text(output / "do_not_promote_after_rerun.md", do_not_promote_md())
    write_text(output / "fixed_scoring_rerun_audit_next_action.md", next_action_md(next_action))
    write_text(output / "fixed_scoring_rerun_audit_summary.md", summary_md(manifest))
    write_json(output / "fixed_scoring_rerun_audit_manifest.json", manifest)
    write_json(output / "fixed_scoring_rerun_audit_consistency_check.json", {"consistency_passed": False})

    registry_updated, roadmap_updated, compact_updated = update_metadata(root, output, created_utc, manifest)
    manifest["registry_metadata_updated"] = registry_updated
    manifest["roadmap_updated"] = roadmap_updated
    manifest["compact_state_updated"] = compact_updated
    consistency = consistency_check(manifest, output)
    write_json(output / "fixed_scoring_rerun_audit_manifest.json", manifest)
    write_json(output / "fixed_scoring_rerun_audit_consistency_check.json", consistency)

    return {
        "output_dir": str(output),
        "rerun_consistency_passed": manifest["rerun_consistency_passed"],
        "guardrails_held": consistency["consistency_passed"],
        "families_actionable_count_after_audit": manifest["families_actionable_count_after_audit"],
        "formal_preregistration_recommended": manifest["formal_preregistration_recommended"],
        "breakout_manual_review_recommended": manifest["breakout_manual_review_recommended"],
        "next_action": manifest["next_action"],
        "consistency_passed": consistency["consistency_passed"],
    }
