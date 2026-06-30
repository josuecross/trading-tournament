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
from strategy_lab.research_os.objective_reset.revised_objective_scoring_v3 import (
    FLOOR_SCORE_THRESHOLD,
    RISK_FLOOR_WARNING_RATIO,
    SATURATION_SCORE_THRESHOLD,
    STANDALONE_FLOOR_FAIL_RATIO,
    STANDALONE_SATURATION_FAIL_RATIO,
    calibration_report_v3,
    score_rows_v3,
)
from strategy_lab.research_os.objective_reset.revised_objective_sandbox_batch import BATCH_OUTPUT_DIR
from strategy_lab.research_os.objective_reset.revised_objective_sandbox_batch_audit import (
    OUTPUT_DIR as BATCH_AUDIT_DIR,
)
from strategy_lab.research_os.objective_reset.revised_objective_sandbox_scoring_fix_audit import (
    OUTPUT_DIR as SCORING_FIX_AUDIT_DIR,
)


OUTPUT_DIR = Path("evidence") / "objective_reset" / "revised_objective_sandbox_scoring_fix_v3" / "latest"

NEXT_ACTION_AUDIT = "audit_scoring_fix_v3_before_more_research"
NEXT_ACTION_RERUN = "rerun_revised_objective_sandbox_batch_with_fixed_scoring"
NEXT_ACTION_MANUAL = "manual_review_required_after_scoring_fix_v3"
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
    "scoring_version": "v3",
    "new_sandbox_batch_run": False,
    "rerun_batch_002": False,
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
    "candidate_creation_allowed_from_rescore": False,
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
    "scoring_fix_v3_manifest.json",
    "scoring_fix_v3_summary.md",
    "v2_overcorrection_review.md",
    "scoring_formula_v3.md",
    "score_penalty_design_v3.md",
    "risk_gate_design_v3.md",
    "lane_aware_scoring_policy_v3.md",
    "calibration_thresholds_v3.md",
    "saturation_and_floor_collapse_tests_v3.md",
    "batch_002_diagnostic_rescore_v3_policy.md",
    "batch_002_diagnostic_rescore_v3.csv",
    "batch_002_diagnostic_rescore_v3_summary.md",
    "scoring_fix_v3_do_not_promote.md",
    "scoring_fix_v3_next_action.md",
    "scoring_fix_v3_consistency_check.json",
)

V3_SCORE_FIELDS = (
    "standalone_growth_score_v3",
    "portfolio_contribution_score_v3",
    "stretch_diagnostic_score_v3",
    "risk_integrity_score_v3",
    "overfit_risk_score_v3",
    "practicality_score_v3",
    "cash_allocation_penalty_v3",
    "underinvestment_penalty_v3",
    "benchmark_lag_penalty_v3",
    "return_drag_penalty_v3",
    "duplicate_penalty_v3",
    "risk_gate_status_v3",
    "score_saturation_flag_v3",
    "score_floor_collapse_flag_v3",
    "score_interpretation_status_v3",
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


def hash_tree(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    return {str(item.relative_to(path)): sha256_file(item) for item in sorted(path.glob("*")) if item.is_file()}


def missing_rescore_fields(rows: list[dict[str, str]]) -> list[str]:
    if not rows:
        return list(REQUIRED_RESCORING_FIELDS)
    fields = set(rows[0])
    return [field for field in REQUIRED_RESCORING_FIELDS if field not in fields]


def diagnostic_rescore_v3(rows: list[dict[str, str]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    missing = missing_rescore_fields(rows)
    if missing:
        return [], {
            "diagnostic_rescore_performed": False,
            "diagnostic_rescore_status": "not_performed_insufficient_saved_fields",
            "missing_fields": missing,
            "calibration_report": {},
        }
    rescored = score_rows_v3(rows, interpretation_status="diagnostic_only")
    return rescored, {
        "diagnostic_rescore_performed": True,
        "diagnostic_rescore_status": "performed_existing_saved_batch_002_fields_only",
        "missing_fields": [],
        "calibration_report": calibration_report_v3(rescored),
    }


def v2_overcorrection_review_md() -> str:
    return """# V2 Overcorrection Review

V2 fixed the original high-saturation bug, but it overcorrected:

- standalone v2 maxed at `35`
- many standalone rows collapsed near zero
- risk integrity median collapsed to `0`
- penalty stacking and risk caps made mixed evidence hard to distinguish

V3 keeps the anti-saturation controls but softens the penalties, separates risk gate labels from score crushing, and preserves moderate scores for mixed evidence.
"""


def scoring_formula_v3_md() -> str:
    return """# Scoring Formula V3

V3 outputs:

- `standalone_growth_score_v3`
- `portfolio_contribution_score_v3`
- `stretch_diagnostic_score_v3`
- `risk_integrity_score_v3`
- `overfit_risk_score_v3`
- `practicality_score_v3`
- `cash_allocation_penalty_v3`
- `underinvestment_penalty_v3`
- `benchmark_lag_penalty_v3`
- `return_drag_penalty_v3`
- `duplicate_penalty_v3`
- `risk_gate_status_v3`
- `score_saturation_flag_v3`
- `score_floor_collapse_flag_v3`
- `score_interpretation_status_v3`

V3 uses bounded logistic evidence components and capped penalties. It applies hard caps only for explicit risk-gate failures, not for every weak risk reading.
"""


def penalty_design_v3_md() -> str:
    return """# Score Penalty Design V3

V3 reduces overcorrection by:

- lowering cash and underinvestment penalty caps
- reducing benchmark-lag dominance
- applying return-drag penalties less aggressively
- reducing duplicate penalties unless active-combo overlap is severe
- keeping practicality and overfit penalties visible but not score-crushing

Penalties reduce confidence; they do not automatically zero scores unless the risk gate is a true failure.
"""


def risk_gate_design_v3_md() -> str:
    return """# Risk Gate Design V3

Risk gate statuses:

- `pass`
- `soft_warn`
- `hard_warn`
- `fail`
- `insufficient_evidence`

Only `fail` strongly caps standalone score. `soft_warn` and `hard_warn` communicate risk quality without collapsing all mixed rows to zero.
"""


def lane_policy_v3_md() -> str:
    return """# Lane-Aware Scoring Policy V3

Standalone growth:

- penalizes cash, benchmark lag, drawdown, duplicate behavior, and impracticality
- allows moderate scores for mixed evidence

Portfolio contribution:

- emphasizes active-combo and VM/DSR improvement net of drag and duplicate risk
- can preserve sleeve evidence even when standalone growth is weak

Stretch diagnostics:

- remain diagnostic-only
- cannot force high standalone or contribution scores
"""


def calibration_thresholds_v3_md(report: dict[str, Any]) -> str:
    return f"""# Calibration Thresholds V3

Standalone saturation fail ratio: `{STANDALONE_SATURATION_FAIL_RATIO}`

Standalone floor-collapse fail ratio: `{STANDALONE_FLOOR_FAIL_RATIO}`

Risk floor warning ratio: `{RISK_FLOOR_WARNING_RATIO}`

Diagnostic report:

- Standalone saturation failed: `{report.get('standalone_saturation_failed')}`
- Standalone floor collapse failed: `{report.get('standalone_floor_collapse_failed')}`
- Risk floor collapse warning: `{report.get('risk_floor_collapse_warning')}`
- Standalone max: `{report.get('standalone_max')}`
- Standalone median: `{report.get('standalone_median')}`
- Risk median: `{report.get('risk_median')}`
"""


def saturation_tests_v3_md(report: dict[str, Any]) -> str:
    return f"""# Saturation And Floor-Collapse Tests V3

Saturation threshold: `{SATURATION_SCORE_THRESHOLD}`

Floor threshold: `{FLOOR_SCORE_THRESHOLD}`

Rows reviewed: `{report.get('row_count', 0)}`

Standalone saturated count: `{report.get('standalone_saturated_count', 0)}`

Standalone floor count: `{report.get('standalone_floor_count', 0)}`

Standalone saturation failed: `{report.get('standalone_saturation_failed')}`

Standalone floor collapse failed: `{report.get('standalone_floor_collapse_failed')}`

Risk floor warning: `{report.get('risk_floor_collapse_warning')}`
"""


def rescore_policy_md(rescore: dict[str, Any]) -> str:
    return f"""# Batch 002 Diagnostic Rescore V3 Policy

Diagnostic rescore performed: `{rescore['diagnostic_rescore_performed']}`

Diagnostic rescore status: `{rescore['diagnostic_rescore_status']}`

Rules:

- existing saved batch 002 CSV/JSON only
- no strategy calculations
- no raw data reads for performance computation
- no signal recomputation
- no provider downloads
- no original output mutation
- diagnostic-only interpretation
- no candidate creation
- no family audit conclusion changes
"""


def rescore_summary_md(rescore: dict[str, Any], row_count: int) -> str:
    report = rescore["calibration_report"]
    return f"""# Batch 002 Diagnostic Rescore V3 Summary

Rows rescored: `{row_count}`

Diagnostic-only: `true`

Standalone max: `{report.get('standalone_max')}`

Standalone median: `{report.get('standalone_median')}`

Standalone saturation failed: `{report.get('standalone_saturation_failed')}`

Standalone floor collapse failed: `{report.get('standalone_floor_collapse_failed')}`

Risk median: `{report.get('risk_median')}`

Risk floor warning: `{report.get('risk_floor_collapse_warning')}`

Corrected scores cannot create candidates or alter original batch 002 conclusions automatically.
"""


def rescore_not_performed_md(rescore: dict[str, Any]) -> str:
    missing = "\n".join(f"- `{field}`" for field in rescore["missing_fields"]) or "- none"
    return f"""# Batch 002 Diagnostic Rescore V3 Not Performed

Status: `{rescore['diagnostic_rescore_status']}`

Missing fields:

{missing}
"""


def do_not_promote_md() -> str:
    return """# Scoring Fix V3 Do Not Promote

This v3 scoring fix does not promote any row, family, or strategy.

It creates no future preregistration candidates, no promotion-review candidates, no paper-forward candidates, and no real-money recommendation.
"""


def next_action_md(next_action: str) -> str:
    return f"""# Scoring Fix V3 Next Action

Exact next action: `{next_action}`

Do not run the next action in this scoring-fix task.
"""


def summary_md(manifest: dict[str, Any]) -> str:
    report = manifest.get("calibration_report", {})
    return f"""# Revised Objective Sandbox Scoring Fix V3

Scoring-fix-only: `{manifest['scoring_fix_only']}`

Scoring version: `{manifest['scoring_version']}`

V2 overcorrection addressed in schema: `{manifest['v2_overcorrection_addressed_in_schema']}`

Diagnostic rescore performed: `{manifest['diagnostic_rescore_performed']}`

Diagnostic rescore status: `{manifest['diagnostic_rescore_status']}`

Standalone saturation failed: `{manifest['standalone_saturation_failed']}`

Standalone floor collapse failed: `{manifest['standalone_floor_collapse_failed']}`

Risk floor collapse warning: `{manifest['risk_floor_collapse_warning']}`

Standalone max: `{report.get('standalone_max')}`

Standalone median: `{report.get('standalone_median')}`

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
            "revised_objective_sandbox_scoring_fix_v3_path": str(output.resolve()),
            "revised_objective_sandbox_scoring_fix_v3_status": "completed_awaiting_audit",
            "revised_objective_sandbox_scoring_fix_v3_created_utc": created_utc,
            "current_research_mode": "revised_objective_sandbox_scoring_v3_fixed",
            "current_next_action": manifest["next_action"],
            "official_current_next_action": manifest["next_action"],
            "next_action": manifest["next_action"],
            "revised_objective_sandbox_scoring_fix_v3_only": True,
            "revised_objective_sandbox_scoring_fix_v3_rescore_performed": manifest["diagnostic_rescore_performed"],
            "revised_objective_sandbox_scoring_fix_v3_saturation_failed": manifest["standalone_saturation_failed"],
            "revised_objective_sandbox_scoring_fix_v3_floor_failed": manifest["standalone_floor_collapse_failed"],
            "revised_objective_sandbox_scoring_fix_v3_candidate_creation_allowed": False,
            "revised_objective_sandbox_scoring_fix_v3_no_new_batch": True,
            "revised_objective_sandbox_scoring_fix_v3_no_rerun": True,
            "revised_objective_sandbox_scoring_fix_v3_no_discovery": True,
            "revised_objective_sandbox_scoring_fix_v3_no_provider_download": True,
            "revised_objective_sandbox_scoring_fix_v3_no_intraday": True,
            "revised_objective_sandbox_scoring_fix_v3_no_candidate_exhaustive": True,
            "revised_objective_sandbox_scoring_fix_v3_no_paper_forward": True,
            "revised_objective_sandbox_scoring_fix_v3_no_real_money_recommendation": True,
        }
    )
    registry_path.write_text(yaml.safe_dump(registry, sort_keys=False, width=120, allow_unicode=False), encoding="utf-8")

    roadmap_path = root / ROADMAP_PATH
    before_roadmap = roadmap_path.read_text(encoding="utf-8") if roadmap_path.exists() else "# Research Roadmap\n"
    compact_section = f"""## Compact Current State

- Updated UTC: `{created_utc}`
- Current research mode: `revised_objective_sandbox_scoring_v3_fixed`
- Official current next action: `{manifest['next_action']}`
- Scoring fix v3 evidence: `{output.resolve()}`
- Diagnostic v3 rescore performed: `{manifest['diagnostic_rescore_performed']}`
- Standalone saturation failed: `{manifest['standalone_saturation_failed']}`
- Standalone floor collapse failed: `{manifest['standalone_floor_collapse_failed']}`
- Risk floor warning: `{manifest['risk_floor_collapse_warning']}`
- Candidate creation allowed from rescore: `false`
- Batch 002 raw outputs changed: `{manifest['batch_002_raw_outputs_changed']}`
- Active VM and active DSR preserved.
- `static_all_weather_benchmark_v1` remains benchmark/control only.
- Exact rejected variants remain closed.
- Intraday remains paused: `true`
- This scoring fix did not run a new sandbox batch, rerun batch 002, run discovery, run backtests, compute raw-data metrics, download provider data, use intraday data, create candidates, activate paper-forward, touch broker/live paths, or make real-money recommendations.
"""
    section = f"""## Revised Objective Sandbox Scoring Fix V3

- Created UTC: `{created_utc}`
- Evidence path: `{output.resolve()}`
- V2 overcorrection addressed in schema: `{manifest['v2_overcorrection_addressed_in_schema']}`
- Diagnostic rescore performed: `{manifest['diagnostic_rescore_performed']}`
- Standalone saturation failed: `{manifest['standalone_saturation_failed']}`
- Standalone floor collapse failed: `{manifest['standalone_floor_collapse_failed']}`
- Next action: `{manifest['next_action']}`
- Do not run the next action in this scoring-fix task.
"""
    after_roadmap = replace_or_append_section(before_roadmap, "## Compact Current State", compact_section)
    after_roadmap = replace_or_append_section(after_roadmap, "## Revised Objective Sandbox Scoring Fix V3", section)
    write_text(roadmap_path, after_roadmap)

    compact_path = root / COMPACT_STATE_PATH
    before_compact = compact_path.read_text(encoding="utf-8") if compact_path.exists() else ""
    after_compact = f"""# Current Tournament State

Created UTC: `{created_utc}`

Current research mode: `revised_objective_sandbox_scoring_v3_fixed`

Current next action: `{manifest['next_action']}`

Scoring fix v3 evidence: `{output.resolve()}`

## Scoring Fix V3

- Diagnostic v3 rescore performed: `{manifest['diagnostic_rescore_performed']}`
- Standalone saturation failed: `{manifest['standalone_saturation_failed']}`
- Standalone floor collapse failed: `{manifest['standalone_floor_collapse_failed']}`
- Risk floor warning: `{manifest['risk_floor_collapse_warning']}`
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
        "scoring_fix_only": manifest["scoring_fix_only"] is True,
        "scoring_version_v3": manifest["scoring_version"] == "v3",
        "no_new_sandbox_batch": manifest["new_sandbox_batch_run"] is False,
        "batch_002_not_rerun": manifest["rerun_batch_002"] is False,
        "no_formal_strategy_discovery": manifest["strategy_discovery_run"] is False and manifest["formal_discovery_run"] is False,
        "no_new_backtests": manifest["new_backtests_run"] is False,
        "no_raw_data_metrics": manifest["new_performance_metrics_from_raw_data_computed"] is False,
        "batch_002_raw_outputs_unchanged": manifest["batch_002_raw_outputs_changed"] is False,
        "no_new_variants": manifest["new_variants_created"] is False,
        "variant_statuses_unchanged": manifest["variant_statuses_changed"] is False,
        "family_audit_unchanged": manifest["family_audit_changed"] is False,
        "no_future_preregistration_candidates": manifest["future_preregistration_candidates_created"] is False,
        "no_formal_preregistration": manifest["formal_preregistration_recommended"] is False,
        "candidate_creation_blocked": manifest["candidate_creation_allowed_from_rescore"] is False,
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
        "sandbox_non_promotable": manifest["sandbox_results_remain_non_promotable"] is True,
        "sandbox_cannot_create_paper": manifest["sandbox_can_create_paper_candidates"] is False,
        "v3_standalone_exists": "standalone_growth_score_v3" in manifest["v3_score_fields"],
        "v3_contribution_exists": "portfolio_contribution_score_v3" in manifest["v3_score_fields"],
        "v3_risk_exists": "risk_integrity_score_v3" in manifest["v3_score_fields"],
        "v3_gate_exists": "risk_gate_status_v3" in manifest["v3_score_fields"],
        "v3_floor_flag_exists": "score_floor_collapse_flag_v3" in manifest["v3_score_fields"],
        "next_action_valid": manifest["next_action"] in VALID_NEXT_ACTIONS,
        "manifest_flags_match_strict_scope": all(manifest.get(key) == value for key, value in MANIFEST_FLAGS.items()),
        "required_files_exist": all((output / name).exists() for name in REQUIRED_FILES),
    }
    check["consistency_passed"] = all(check.values())
    return check


def run_revised_objective_sandbox_scoring_fix_v3(root: Path = ROOT) -> dict[str, Any]:
    root = root.resolve()
    created_utc = now_utc()
    output = root / OUTPUT_DIR
    output.mkdir(parents=True, exist_ok=True)

    before_strategies = strategy_snapshot(root)
    batch_hashes_before = hash_tree(root / BATCH_OUTPUT_DIR)
    audit_hashes_before = hash_tree(root / BATCH_AUDIT_DIR)
    rows = read_csv(root / BATCH_OUTPUT_DIR / "batch_002_variant_results.csv")
    rescored_rows, rescore = diagnostic_rescore_v3(rows)
    report = rescore["calibration_report"]
    next_action = NEXT_ACTION_AUDIT

    manifest = {
        "created_utc": created_utc,
        "output_dir": str(output.resolve()),
        **MANIFEST_FLAGS,
        "v2_overcorrection_addressed_in_schema": True,
        "diagnostic_rescore_performed": rescore["diagnostic_rescore_performed"],
        "diagnostic_rescore_status": rescore["diagnostic_rescore_status"],
        "standalone_saturation_failed": bool(report.get("standalone_saturation_failed", False)),
        "standalone_floor_collapse_failed": bool(report.get("standalone_floor_collapse_failed", False)),
        "risk_floor_collapse_warning": bool(report.get("risk_floor_collapse_warning", False)),
        "calibration_report": report,
        "v3_score_fields": list(V3_SCORE_FIELDS),
        "source_batch_002_rows_read": len(rows),
        "diagnostic_rescore_rows_written": len(rescored_rows),
        "next_action": next_action,
    }

    write_text(output / "v2_overcorrection_review.md", v2_overcorrection_review_md())
    write_text(output / "scoring_formula_v3.md", scoring_formula_v3_md())
    write_text(output / "score_penalty_design_v3.md", penalty_design_v3_md())
    write_text(output / "risk_gate_design_v3.md", risk_gate_design_v3_md())
    write_text(output / "lane_aware_scoring_policy_v3.md", lane_policy_v3_md())
    write_text(output / "calibration_thresholds_v3.md", calibration_thresholds_v3_md(report))
    write_text(output / "saturation_and_floor_collapse_tests_v3.md", saturation_tests_v3_md(report))
    write_text(output / "batch_002_diagnostic_rescore_v3_policy.md", rescore_policy_md(rescore))
    if rescored_rows:
        fieldnames = list(dict.fromkeys([*rows[0].keys(), *V3_SCORE_FIELDS]))
        write_csv(output / "batch_002_diagnostic_rescore_v3.csv", rescored_rows, fieldnames)
        write_text(output / "batch_002_diagnostic_rescore_v3_summary.md", rescore_summary_md(rescore, len(rescored_rows)))
    else:
        write_text(output / "batch_002_diagnostic_rescore_v3_not_performed.md", rescore_not_performed_md(rescore))
    write_text(output / "scoring_fix_v3_do_not_promote.md", do_not_promote_md())
    write_text(output / "scoring_fix_v3_next_action.md", next_action_md(next_action))
    write_text(output / "scoring_fix_v3_summary.md", summary_md(manifest))
    write_json(output / "scoring_fix_v3_manifest.json", manifest)
    write_json(output / "scoring_fix_v3_consistency_check.json", {"consistency_passed": False})

    after_strategies = strategy_snapshot(root)
    batch_hashes_after = hash_tree(root / BATCH_OUTPUT_DIR)
    audit_hashes_after = hash_tree(root / BATCH_AUDIT_DIR)
    manifest["batch_002_raw_outputs_changed"] = batch_hashes_before != batch_hashes_after
    manifest["variant_statuses_changed"] = batch_hashes_before.get("batch_002_variant_results.csv") != batch_hashes_after.get(
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
    write_json(output / "scoring_fix_v3_manifest.json", manifest)
    write_json(output / "scoring_fix_v3_consistency_check.json", consistency)

    return {
        "output_dir": str(output),
        "diagnostic_rescore_performed": manifest["diagnostic_rescore_performed"],
        "diagnostic_rescore_status": manifest["diagnostic_rescore_status"],
        "standalone_saturation_failed": manifest["standalone_saturation_failed"],
        "standalone_floor_collapse_failed": manifest["standalone_floor_collapse_failed"],
        "risk_floor_collapse_warning": manifest["risk_floor_collapse_warning"],
        "batch_002_raw_outputs_changed": manifest["batch_002_raw_outputs_changed"],
        "candidate_creation_allowed_from_rescore": manifest["candidate_creation_allowed_from_rescore"],
        "next_action": manifest["next_action"],
        "consistency_passed": consistency["consistency_passed"],
    }
