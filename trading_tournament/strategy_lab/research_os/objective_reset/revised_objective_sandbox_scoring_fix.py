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
from strategy_lab.research_os.objective_reset.revised_objective_scoring_v2 import (
    SATURATION_FAIL_RATIO,
    SATURATION_SCORE_THRESHOLD,
    SATURATION_WARNING_RATIO,
    saturation_report,
    score_rows_v2,
)
from strategy_lab.research_os.objective_reset.revised_objective_sandbox_batch import BATCH_OUTPUT_DIR
from strategy_lab.research_os.objective_reset.revised_objective_sandbox_batch_audit import (
    OUTPUT_DIR as BATCH_AUDIT_DIR,
)


OUTPUT_DIR = Path("evidence") / "objective_reset" / "revised_objective_sandbox_scoring_fix" / "latest"
NEXT_ACTION_AUDIT = "audit_scoring_fix_before_more_research"
NEXT_ACTION_RERUN = "rerun_revised_objective_sandbox_batch_with_fixed_scoring"
NEXT_ACTION_MANUAL = "manual_review_required_after_scoring_fix"
NEXT_ACTION_OBSERVE = "continue_paper_forward_observation_only"
NEXT_ACTION_PAUSE = "pause_expansion_and_wait_for_manual_direction"
VALID_NEXT_ACTIONS = {
    NEXT_ACTION_AUDIT,
    NEXT_ACTION_RERUN,
    NEXT_ACTION_MANUAL,
    NEXT_ACTION_OBSERVE,
    NEXT_ACTION_PAUSE,
}

MANIFEST_FLAGS = {
    "scoring_fix_only": True,
    "new_sandbox_batch_run": False,
    "strategy_discovery_run": False,
    "formal_discovery_run": False,
    "new_backtests_run": False,
    "new_performance_metrics_from_raw_data_computed": False,
    "batch_002_raw_outputs_changed": False,
    "new_variants_created": False,
    "variant_statuses_changed": False,
    "family_audit_changed": False,
    "future_preregistration_candidates_created": False,
    "formal_preregistration_recommended": False,
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
    "scoring_fix_manifest.json",
    "scoring_fix_summary.md",
    "standalone_score_defect_review.md",
    "scoring_formula_v2.md",
    "score_penalty_design.md",
    "lane_aware_scoring_policy.md",
    "saturation_prevention_tests.md",
    "batch_002_diagnostic_rescore_policy.md",
    "batch_002_diagnostic_rescore.csv",
    "batch_002_diagnostic_rescore_summary.md",
    "scoring_fix_do_not_promote.md",
    "scoring_fix_next_action.md",
    "scoring_fix_consistency_check.json",
)

V2_SCORE_FIELDS = (
    "standalone_growth_score_v2",
    "portfolio_contribution_score_v2",
    "stretch_diagnostic_score_v2",
    "risk_integrity_score_v2",
    "overfit_risk_score_v2",
    "practicality_score_v2",
    "cash_allocation_penalty",
    "underinvestment_penalty",
    "benchmark_lag_penalty",
    "return_drag_penalty_v2",
    "duplicate_penalty_v2",
    "score_saturation_flag",
    "score_interpretation_status",
)

REQUIRED_RESCORING_FIELDS = (
    "variant_id",
    "family_id",
    "objective_lane",
    "180d_median_final_equity",
    "ending_equity",
    "total_return",
    "sharpe",
    "max_drawdown",
    "180d_worst_drawdown",
    "risk_buffer_vs_minus_600",
    "stop_hit_rate",
    "delta_vs_active_combo_180d_median",
    "return_drag_penalty",
    "duplicate_penalty",
    "corr_vs_active_combo",
    "trade_count",
    "avg_turnover",
    "avg_cash_allocation",
    "avg_symbols_held",
    "max_symbol_weight",
    "data_window_length",
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


def source_hashes(root: Path) -> dict[str, str]:
    source = root / BATCH_OUTPUT_DIR
    if not source.exists():
        return {}
    return {str(path.relative_to(source)): sha256_file(path) for path in sorted(source.glob("*")) if path.is_file()}


def audit_hashes(root: Path) -> dict[str, str]:
    source = root / BATCH_AUDIT_DIR
    if not source.exists():
        return {}
    return {str(path.relative_to(source)): sha256_file(path) for path in sorted(source.glob("*")) if path.is_file()}


def missing_rescore_fields(rows: list[dict[str, str]]) -> list[str]:
    if not rows:
        return list(REQUIRED_RESCORING_FIELDS)
    fields = set(rows[0])
    return [field for field in REQUIRED_RESCORING_FIELDS if field not in fields]


def diagnostic_rescore(rows: list[dict[str, str]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    missing = missing_rescore_fields(rows)
    if missing:
        return [], {
            "diagnostic_rescore_performed": False,
            "diagnostic_rescore_status": "not_performed_insufficient_saved_fields",
            "missing_fields": missing,
            "saturation": {},
        }
    rescored = score_rows_v2(rows, interpretation_status="diagnostic_only")
    saturation = saturation_report(rescored)
    return rescored, {
        "diagnostic_rescore_performed": True,
        "diagnostic_rescore_status": "performed_existing_saved_batch_002_fields_only",
        "missing_fields": [],
        "saturation": saturation,
    }


def standalone_defect_review_md() -> str:
    return """# Standalone Score Defect Review

Batch 002 saturated because the original standalone formula added large positive credits for ending equity, 180-day progress, Sharpe, risk buffer, and benchmark delta before applying a final 0-100 clamp. The clamp hid differences among rows.

The defect was material because cash-heavy, defensive, benchmark-lagging, or high-drawdown rows could still print `100`. The audit therefore treated standalone growth score as invalid for actionability.

The v2 design fixes this by:

- using bounded logistic normalization for growth and benchmark components
- applying penalties before final clamping
- capping standalone scores when risk integrity is weak
- penalizing cash-heavy and under-invested rows
- penalizing active-reference lag and return drag
- separating standalone-growth and contribution-sleeve scoring
"""


def scoring_formula_v2_md() -> str:
    return f"""# Scoring Formula V2

Required v2 outputs:

- `standalone_growth_score_v2`
- `portfolio_contribution_score_v2`
- `stretch_diagnostic_score_v2`
- `risk_integrity_score_v2`
- `overfit_risk_score_v2`
- `practicality_score_v2`
- `cash_allocation_penalty`
- `underinvestment_penalty`
- `benchmark_lag_penalty`
- `return_drag_penalty_v2`
- `duplicate_penalty_v2`
- `score_saturation_flag`
- `score_interpretation_status`

Standalone score v2 combines bounded evidence components:

- 180-day median progress
- total return
- Sharpe
- active-combo delta
- risk integrity
- practicality

Then it subtracts:

- cash allocation penalty
- underinvestment penalty
- benchmark lag penalty
- return-drag penalty
- duplicate penalty
- overfit-risk penalty

Risk-integrity gates cap the result when drawdown quality is weak. The saturation threshold is `{SATURATION_SCORE_THRESHOLD}`, warning ratio is `{SATURATION_WARNING_RATIO}`, and fail ratio is `{SATURATION_FAIL_RATIO}`.
"""


def penalty_design_md() -> str:
    return """# Score Penalty Design

Cash / underinvestment:

- high `avg_cash_allocation` creates `cash_allocation_penalty`
- low `avg_symbols_held`, near-zero trades, and all-cash behavior create `underinvestment_penalty`
- high-cash rows may remain contribution/context clues but cannot be standalone winners

Benchmark lag:

- negative active-combo delta creates `benchmark_lag_penalty`
- lag is evidence of opportunity cost, not an automatic rejection

Return drag:

- saved `return_drag_penalty` is converted into stronger `return_drag_penalty_v2`
- contribution score is reduced unless portfolio improvement offsets drag

Risk integrity:

- stop breach, poor risk buffer, and weak 180-day drawdown reduce `risk_integrity_score_v2`
- zero or very low risk integrity caps standalone score

Duplicate behavior:

- high active-combo correlation and explicit duplicate penalty create `duplicate_penalty_v2`
- contribution score is capped for active-combo repackaging without net improvement

Practicality:

- high turnover, excessive trades, zero-trade artifacts, limited history, and inactive defensive behavior reduce `practicality_score_v2`
"""


def lane_policy_md() -> str:
    return """# Lane-Aware Scoring Policy

Standalone growth lane:

- emphasizes realistic growth, risk integrity, benchmark relevance, and practicality
- penalizes high cash, underinvestment, benchmark lag, return drag, and high drawdown

Portfolio-contribution sleeve lane:

- emphasizes active VM/DSR or active-combo portfolio improvement net of drag
- penalizes duplicate active-combo behavior and high correlation
- may preserve low-correlation clues without treating them as standalone engines

Stretch diagnostics:

- remain diagnostic only
- cannot force high standalone or contribution score
- cannot create promotion, candidate_exhaustive, or paper-forward status

Benchmark/control context:

- remains non-promotable
- may inform future audits only after separate preregistration
"""


def saturation_tests_md(rescore: dict[str, Any]) -> str:
    saturation = rescore.get("saturation", {})
    return f"""# Saturation Prevention Tests

Rules:

- Fail if more than `{SATURATION_FAIL_RATIO:.0%}` of rows have standalone score >= `{SATURATION_SCORE_THRESHOLD}`
- Warn if more than `{SATURATION_WARNING_RATIO:.0%}` of rows have standalone score >= `{SATURATION_SCORE_THRESHOLD}`

Diagnostic rescore result:

- Rows: `{saturation.get('row_count', 0)}`
- Saturated count: `{saturation.get('saturated_count', 0)}`
- Saturated ratio: `{saturation.get('saturated_ratio', 0.0)}`
- Warning: `{saturation.get('saturation_warning', False)}`
- Failed: `{saturation.get('saturation_failed', False)}`

Synthetic unit tests also cover cash-heavy lagging rows, high-drawdown rows, duplicate active-combo rows, contribution-style rows, and stretch diagnostics.
"""


def rescore_policy_md(rescore: dict[str, Any]) -> str:
    return f"""# Batch 002 Diagnostic Rescore Policy

Diagnostic rescore performed: `{rescore['diagnostic_rescore_performed']}`

Diagnostic rescore status: `{rescore['diagnostic_rescore_status']}`

Rules:

- existing batch 002 CSV/JSON files only
- no strategy calculations
- no raw data reads for performance computation
- no signal recomputation
- no provider downloads
- no changes to original batch 002 outputs
- diagnostic-only interpretation
- no candidate creation
- no family audit conclusion changes
"""


def rescore_not_performed_md(rescore: dict[str, Any]) -> str:
    missing = "\n".join(f"- `{field}`" for field in rescore["missing_fields"]) or "- none"
    return f"""# Batch 002 Diagnostic Rescore Not Performed

Status: `{rescore['diagnostic_rescore_status']}`

Missing fields:

{missing}
"""


def rescore_summary_md(rescore: dict[str, Any], row_count: int) -> str:
    saturation = rescore["saturation"]
    return f"""# Batch 002 Diagnostic Rescore Summary

Rows rescored: `{row_count}`

Diagnostic-only: `true`

Saturation threshold: `{saturation['saturation_threshold']}`

Saturated count: `{saturation['saturated_count']}`

Saturated ratio: `{saturation['saturated_ratio']}`

Saturation failed: `{saturation['saturation_failed']}`

Corrected scores cannot create candidates or alter original batch 002 conclusions automatically.
"""


def do_not_promote_md() -> str:
    return """# Scoring Fix Do Not Promote

This scoring fix does not promote any row, family, or strategy.

Forbidden from this task:

- promotion-review candidates
- candidate_exhaustive candidates
- paper-forward candidates
- paper-forward activation
- future preregistration candidates
- broker/live-order paths
- real-money recommendations

Any future run or preregistration must be separately authorized.
"""


def next_action_md(next_action: str) -> str:
    return f"""# Scoring Fix Next Action

Exact next action: `{next_action}`

The fixed scoring formula and tests should be audited before any additional research run.

Do not run the next action in this scoring-fix task.
"""


def summary_md(manifest: dict[str, Any]) -> str:
    return f"""# Revised Objective Sandbox Scoring Fix

Scoring-fix-only: `{manifest['scoring_fix_only']}`

Standalone score saturation fixed in schema: `{manifest['standalone_score_saturation_fixed_in_schema']}`

Diagnostic rescore performed: `{manifest['diagnostic_rescore_performed']}`

Diagnostic rescore status: `{manifest['diagnostic_rescore_status']}`

Candidate creation allowed from rescore: `{manifest['candidate_creation_allowed_from_rescore']}`

Batch 002 raw outputs changed: `{manifest['batch_002_raw_outputs_changed']}`

Variant statuses changed: `{manifest['variant_statuses_changed']}`

Family audit changed: `{manifest['family_audit_changed']}`

Next action: `{manifest['next_action']}`

No new sandbox batch, discovery, new backtest, raw-data metric computation, provider download, intraday data, candidate_exhaustive, paper-forward action, broker/live path, or real-money recommendation occurred.
"""


def update_metadata(root: Path, output: Path, created_utc: str, manifest: dict[str, Any]) -> tuple[bool, bool, bool]:
    registry_path = root / REGISTRY_PATH
    registry = load_yaml(registry_path)
    metadata = registry.setdefault("registry", {})
    before_metadata = deepcopy(metadata)
    metadata.update(
        {
            "revised_objective_sandbox_scoring_fix_path": str(output.resolve()),
            "revised_objective_sandbox_scoring_fix_status": "completed_fixed_schema_diagnostic_rescore",
            "revised_objective_sandbox_scoring_fix_created_utc": created_utc,
            "current_research_mode": "revised_objective_sandbox_scoring_fixed",
            "current_next_action": manifest["next_action"],
            "official_current_next_action": manifest["next_action"],
            "next_action": manifest["next_action"],
            "revised_objective_sandbox_scoring_fix_only": True,
            "revised_objective_sandbox_scoring_fix_saturation_fixed_in_schema": manifest[
                "standalone_score_saturation_fixed_in_schema"
            ],
            "revised_objective_sandbox_scoring_fix_diagnostic_rescore_performed": manifest[
                "diagnostic_rescore_performed"
            ],
            "revised_objective_sandbox_scoring_fix_candidate_creation_allowed": False,
            "revised_objective_sandbox_scoring_fix_no_new_batch": True,
            "revised_objective_sandbox_scoring_fix_no_strategy_discovery": True,
            "revised_objective_sandbox_scoring_fix_no_raw_data_metrics": True,
            "revised_objective_sandbox_scoring_fix_no_provider_download": True,
            "revised_objective_sandbox_scoring_fix_no_intraday": True,
            "revised_objective_sandbox_scoring_fix_no_candidate_exhaustive": True,
            "revised_objective_sandbox_scoring_fix_no_paper_forward_action": True,
            "revised_objective_sandbox_scoring_fix_no_real_money_recommendation": True,
        }
    )
    registry_path.write_text(yaml.safe_dump(registry, sort_keys=False, width=120, allow_unicode=False), encoding="utf-8")

    roadmap_path = root / ROADMAP_PATH
    before_roadmap = roadmap_path.read_text(encoding="utf-8") if roadmap_path.exists() else "# Research Roadmap\n"
    compact_section = f"""## Compact Current State

- Updated UTC: `{created_utc}`
- Current research mode: `revised_objective_sandbox_scoring_fixed`
- Official current next action: `{manifest['next_action']}`
- Scoring fix evidence: `{output.resolve()}`
- Standalone score saturation fixed in schema: `{manifest['standalone_score_saturation_fixed_in_schema']}`
- Diagnostic rescore performed: `{manifest['diagnostic_rescore_performed']}`
- Diagnostic rescore status: `{manifest['diagnostic_rescore_status']}`
- Batch 002 raw outputs changed: `{manifest['batch_002_raw_outputs_changed']}`
- Candidate creation allowed from rescore: `false`
- Active VM and active DSR preserved.
- `static_all_weather_benchmark_v1` remains benchmark/control only.
- Exact rejected variants remain closed.
- Intraday remains paused: `true`
- This scoring fix did not run a new sandbox batch, discovery, new backtest, raw-data metric computation, provider download, intraday data, candidate_exhaustive, paper-forward action, broker/live path, or real-money recommendation.
"""
    section = f"""## Revised Objective Sandbox Scoring Fix

- Created UTC: `{created_utc}`
- Evidence path: `{output.resolve()}`
- V2 scoring fields created: `true`
- Diagnostic rescore performed: `{manifest['diagnostic_rescore_performed']}`
- Diagnostic rescore status: `{manifest['diagnostic_rescore_status']}`
- Standalone saturation fixed in schema: `{manifest['standalone_score_saturation_fixed_in_schema']}`
- Candidate creation allowed from rescore: `false`
- Next action: `{manifest['next_action']}`
- Do not run the next action in this scoring-fix task.
"""
    after_roadmap = replace_or_append_section(before_roadmap, "## Compact Current State", compact_section)
    after_roadmap = replace_or_append_section(after_roadmap, "## Revised Objective Sandbox Scoring Fix", section)
    write_text(roadmap_path, after_roadmap)

    compact_path = root / COMPACT_STATE_PATH
    before_compact = compact_path.read_text(encoding="utf-8") if compact_path.exists() else ""
    after_compact = f"""# Current Tournament State

Created UTC: `{created_utc}`

Current research mode: `revised_objective_sandbox_scoring_fixed`

Current next action: `{manifest['next_action']}`

Scoring fix evidence: `{output.resolve()}`

## Scoring Fix

- Standalone score saturation fixed in schema: `{manifest['standalone_score_saturation_fixed_in_schema']}`
- Diagnostic rescore performed: `{manifest['diagnostic_rescore_performed']}`
- Diagnostic rescore status: `{manifest['diagnostic_rescore_status']}`
- Candidate creation allowed from rescore: `false`
- Batch 002 raw outputs changed: `{manifest['batch_002_raw_outputs_changed']}`
- Single safest next action: `{manifest['next_action']}`

## Protected State

- `paper_forward_vm_quality_lowvol_proxy_v1` remains active/accepted/frozen.
- `paper_forward_dsr_sector_equal_weight_defensive_filter_v1` remains active/accepted/frozen.
- `static_all_weather_benchmark_v1` remains benchmark/control only.
- Exact rejected variants remain closed.
- Intraday research remains paused.

## Forbidden Actions

- No new sandbox batch.
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
        "scoring_fix_only": manifest["scoring_fix_only"] is True,
        "no_new_sandbox_batch": manifest["new_sandbox_batch_run"] is False,
        "no_formal_strategy_discovery": manifest["strategy_discovery_run"] is False and manifest["formal_discovery_run"] is False,
        "no_new_backtests": manifest["new_backtests_run"] is False,
        "no_new_raw_data_metrics": manifest["new_performance_metrics_from_raw_data_computed"] is False,
        "batch_002_raw_outputs_unchanged": manifest["batch_002_raw_outputs_changed"] is False,
        "no_new_variants_created": manifest["new_variants_created"] is False,
        "variant_statuses_unchanged": manifest["variant_statuses_changed"] is False,
        "family_audit_unchanged": manifest["family_audit_changed"] is False,
        "no_future_preregistration_candidates_created": manifest["future_preregistration_candidates_created"] is False,
        "no_formal_preregistration_recommended": manifest["formal_preregistration_recommended"] is False,
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
        "v2_schema_fields_present": all(field in manifest["v2_score_fields"] for field in V2_SCORE_FIELDS),
        "candidate_creation_blocked_from_rescore": manifest["candidate_creation_allowed_from_rescore"] is False,
        "next_action_valid": manifest["next_action"] in VALID_NEXT_ACTIONS,
        "manifest_flags_match_strict_scope": all(manifest.get(key) == value for key, value in MANIFEST_FLAGS.items()),
        "required_files_exist": all((output / name).exists() for name in REQUIRED_FILES),
    }
    check["consistency_passed"] = all(check.values())
    return check


def run_revised_objective_sandbox_scoring_fix(root: Path = ROOT) -> dict[str, Any]:
    root = root.resolve()
    created_utc = now_utc()
    output = root / OUTPUT_DIR
    output.mkdir(parents=True, exist_ok=True)
    before_strategies = strategy_snapshot(root)
    raw_hashes_before = source_hashes(root)
    audit_hashes_before = audit_hashes(root)
    rows = read_csv(root / BATCH_OUTPUT_DIR / "batch_002_variant_results.csv")
    rescored_rows, rescore = diagnostic_rescore(rows)
    next_action = NEXT_ACTION_AUDIT

    manifest = {
        "created_utc": created_utc,
        "output_dir": str(output.resolve()),
        **MANIFEST_FLAGS,
        "standalone_score_saturation_fixed_in_schema": True,
        "diagnostic_rescore_performed": rescore["diagnostic_rescore_performed"],
        "diagnostic_rescore_status": rescore["diagnostic_rescore_status"],
        "candidate_creation_allowed_from_rescore": False,
        "v2_score_fields": list(V2_SCORE_FIELDS),
        "source_batch_002_rows_read": len(rows),
        "diagnostic_rescore_rows_written": len(rescored_rows),
        "saturation_report": rescore["saturation"],
        "next_action": next_action,
    }

    write_text(output / "standalone_score_defect_review.md", standalone_defect_review_md())
    write_text(output / "scoring_formula_v2.md", scoring_formula_v2_md())
    write_text(output / "score_penalty_design.md", penalty_design_md())
    write_text(output / "lane_aware_scoring_policy.md", lane_policy_md())
    write_text(output / "saturation_prevention_tests.md", saturation_tests_md(rescore))
    write_text(output / "batch_002_diagnostic_rescore_policy.md", rescore_policy_md(rescore))
    if rescored_rows:
        fieldnames = list(dict.fromkeys([*rows[0].keys(), *V2_SCORE_FIELDS]))
        write_csv(output / "batch_002_diagnostic_rescore.csv", rescored_rows, fieldnames)
        write_text(output / "batch_002_diagnostic_rescore_summary.md", rescore_summary_md(rescore, len(rescored_rows)))
    else:
        write_text(output / "batch_002_diagnostic_rescore_not_performed.md", rescore_not_performed_md(rescore))
    write_text(output / "scoring_fix_do_not_promote.md", do_not_promote_md())
    write_text(output / "scoring_fix_next_action.md", next_action_md(next_action))
    write_text(output / "scoring_fix_summary.md", summary_md(manifest))
    write_json(output / "scoring_fix_manifest.json", manifest)
    write_json(output / "scoring_fix_consistency_check.json", {"consistency_passed": False})

    after_strategies = strategy_snapshot(root)
    raw_hashes_after = source_hashes(root)
    audit_hashes_after = audit_hashes(root)
    manifest["batch_002_raw_outputs_changed"] = raw_hashes_before != raw_hashes_after
    manifest["variant_statuses_changed"] = raw_hashes_before.get("batch_002_variant_results.csv") != raw_hashes_after.get(
        "batch_002_variant_results.csv"
    )
    manifest["family_audit_changed"] = audit_hashes_before != audit_hashes_after
    if before_strategies != after_strategies:
        manifest["active_strategy_state_changed"] = True
        manifest["rejected_strategy_state_changed"] = True

    registry_updated, roadmap_updated, compact_updated = update_metadata(root, output, created_utc, manifest)
    manifest["registry_metadata_updated"] = registry_updated
    manifest["roadmap_updated"] = roadmap_updated
    manifest["compact_state_updated"] = compact_updated
    consistency = consistency_check(manifest, output)
    write_json(output / "scoring_fix_manifest.json", manifest)
    write_json(output / "scoring_fix_consistency_check.json", consistency)

    return {
        "output_dir": str(output),
        "standalone_score_saturation_fixed_in_schema": manifest["standalone_score_saturation_fixed_in_schema"],
        "diagnostic_rescore_performed": manifest["diagnostic_rescore_performed"],
        "diagnostic_rescore_status": manifest["diagnostic_rescore_status"],
        "batch_002_raw_outputs_changed": manifest["batch_002_raw_outputs_changed"],
        "candidate_creation_allowed_from_rescore": manifest["candidate_creation_allowed_from_rescore"],
        "next_action": manifest["next_action"],
        "consistency_passed": consistency["consistency_passed"],
    }
