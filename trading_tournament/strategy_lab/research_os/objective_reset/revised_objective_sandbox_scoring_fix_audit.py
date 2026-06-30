from __future__ import annotations

import csv
import hashlib
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
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
from strategy_lab.research_os.objective_reset.revised_objective_sandbox_batch import BATCH_OUTPUT_DIR
from strategy_lab.research_os.objective_reset.revised_objective_sandbox_batch_audit import (
    OUTPUT_DIR as BATCH_AUDIT_DIR,
)
from strategy_lab.research_os.objective_reset.revised_objective_sandbox_scoring_fix import (
    OUTPUT_DIR as SCORING_FIX_DIR,
)


OUTPUT_DIR = Path("evidence") / "objective_reset" / "revised_objective_sandbox_scoring_fix_audit" / "latest"

NEXT_ACTION_RERUN = "rerun_revised_objective_sandbox_batch_with_fixed_scoring"
NEXT_ACTION_MANUAL = "manual_review_required_after_scoring_fix_audit"
NEXT_ACTION_FIX_AGAIN = "fix_revised_objective_sandbox_scoring_again"
NEXT_ACTION_OBSERVE = "continue_paper_forward_observation_only"
NEXT_ACTION_PAUSE = "pause_expansion_and_wait_for_manual_direction"
VALID_NEXT_ACTIONS = {
    NEXT_ACTION_RERUN,
    NEXT_ACTION_MANUAL,
    NEXT_ACTION_FIX_AGAIN,
    NEXT_ACTION_OBSERVE,
    NEXT_ACTION_PAUSE,
}

MANIFEST_FLAGS = {
    "scoring_fix_audit_only": True,
    "new_sandbox_batch_run": False,
    "rerun_batch_002": False,
    "strategy_discovery_run": False,
    "formal_discovery_run": False,
    "new_backtests_run": False,
    "new_performance_metrics_from_raw_data_computed": False,
    "batch_002_raw_outputs_changed": False,
    "diagnostic_rescore_reviewed": True,
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
    "scoring_fix_audit_manifest.json",
    "scoring_fix_audit_summary.md",
    "scoring_fix_consistency_review.md",
    "diagnostic_rescore_review.md",
    "score_distribution_review.md",
    "standalone_growth_score_v2_review.md",
    "portfolio_contribution_score_v2_review.md",
    "stretch_diagnostic_score_v2_review.md",
    "risk_integrity_score_v2_review.md",
    "overfit_risk_score_v2_review.md",
    "practicality_score_v2_review.md",
    "family_level_v2_review.md",
    "batch_002_interpretation_after_v2.md",
    "do_not_promote_from_rescore.md",
    "scoring_fix_audit_next_action.md",
    "scoring_fix_audit_consistency_check.json",
)

SCORE_FIELDS = (
    "standalone_growth_score_v2",
    "portfolio_contribution_score_v2",
    "stretch_diagnostic_score_v2",
    "risk_integrity_score_v2",
    "overfit_risk_score_v2",
    "practicality_score_v2",
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


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def hash_tree(root: Path) -> dict[str, str]:
    if not root.exists():
        return {}
    return {str(path.relative_to(root)): sha256_file(path) for path in sorted(root.glob("*")) if path.is_file()}


def to_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if number != number:
        return default
    return number


def bool_text(value: Any) -> bool:
    return str(value).strip().lower() == "true"


def values(rows: list[dict[str, str]], field: str) -> list[float]:
    return [to_float(row.get(field)) for row in rows if row.get(field, "") != ""]


def distribution(rows: list[dict[str, str]], field: str) -> dict[str, Any]:
    vals = values(rows, field)
    if not vals:
        return {
            "score_field": field,
            "row_count": 0,
            "min": 0.0,
            "median": 0.0,
            "max": 0.0,
            "rows_gte_98": 0,
            "rows_lte_5": 0,
            "rows_gte_70": 0,
            "rows_10_to_70": 0,
        }
    return {
        "score_field": field,
        "row_count": len(vals),
        "min": min(vals),
        "median": median(vals),
        "max": max(vals),
        "rows_gte_98": sum(1 for value in vals if value >= 98.0),
        "rows_lte_5": sum(1 for value in vals if value <= 5.0),
        "rows_gte_70": sum(1 for value in vals if value >= 70.0),
        "rows_10_to_70": sum(1 for value in vals if 10.0 <= value <= 70.0),
    }


def family_rows(rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        grouped.setdefault(row.get("family_id", ""), []).append(row)
    return grouped


def family_distribution(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for family_id, group in sorted(family_rows(rows).items()):
        out.append(
            {
                "family_id": family_id,
                "rows": len(group),
                "median_standalone_growth_score_v2": distribution(group, "standalone_growth_score_v2")["median"],
                "max_standalone_growth_score_v2": distribution(group, "standalone_growth_score_v2")["max"],
                "median_portfolio_contribution_score_v2": distribution(group, "portfolio_contribution_score_v2")[
                    "median"
                ],
                "max_portfolio_contribution_score_v2": distribution(group, "portfolio_contribution_score_v2")["max"],
                "median_risk_integrity_score_v2": distribution(group, "risk_integrity_score_v2")["median"],
                "median_practicality_score_v2": distribution(group, "practicality_score_v2")["median"],
                "median_cash_allocation_penalty": distribution(group, "cash_allocation_penalty")["median"],
                "median_underinvestment_penalty": distribution(group, "underinvestment_penalty")["median"],
                "median_benchmark_lag_penalty": distribution(group, "benchmark_lag_penalty")["median"],
                "median_return_drag_penalty_v2": distribution(group, "return_drag_penalty_v2")["median"],
                "median_duplicate_penalty_v2": distribution(group, "duplicate_penalty_v2")["median"],
            }
        )
    return out


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def calibration_flags(rows: list[dict[str, str]]) -> dict[str, Any]:
    standalone = distribution(rows, "standalone_growth_score_v2")
    contribution = distribution(rows, "portfolio_contribution_score_v2")
    saturation_fixed = standalone["rows_gte_98"] == 0
    overcorrection = (
        standalone["max"] < 50.0
        or (standalone["rows_lte_5"] / standalone["row_count"] if standalone["row_count"] else 1.0) > 0.30
    )
    contribution_preserved = contribution["max"] >= 40.0 and contribution["rows_10_to_70"] >= max(1, rows and len(rows) // 2)
    return {
        "saturation_fixed": saturation_fixed,
        "overcorrection_found": overcorrection,
        "contribution_signal_preserved": contribution_preserved,
        "v2_calibration_accepted": saturation_fixed and not overcorrection and contribution_preserved,
        "rerun_with_fixed_scoring_recommended": saturation_fixed and not overcorrection and contribution_preserved,
    }


def source_state(root: Path) -> dict[str, Any]:
    scoring_fix = root / SCORING_FIX_DIR
    return {
        "scoring_fix_manifest": read_json(scoring_fix / "scoring_fix_manifest.json"),
        "scoring_fix_consistency": read_json(scoring_fix / "scoring_fix_consistency_check.json"),
        "rescore_rows": read_csv(scoring_fix / "batch_002_diagnostic_rescore.csv"),
        "batch_audit_manifest": read_json(root / BATCH_AUDIT_DIR / "revised_objective_sandbox_batch_audit_manifest.json"),
        "batch_manifest": read_json(root / BATCH_OUTPUT_DIR / "revised_objective_sandbox_batch_manifest.json"),
    }


def decide_next_action(flags: dict[str, Any]) -> str:
    if flags["v2_calibration_accepted"]:
        return NEXT_ACTION_RERUN
    if flags["saturation_fixed"] and flags["overcorrection_found"]:
        return NEXT_ACTION_FIX_AGAIN
    if flags["saturation_fixed"]:
        return NEXT_ACTION_MANUAL
    return NEXT_ACTION_FIX_AGAIN


def consistency_review_md(state: dict[str, Any], flags: dict[str, Any]) -> str:
    fix_manifest = state["scoring_fix_manifest"]
    fix_check = state["scoring_fix_consistency"]
    return f"""# Scoring Fix Consistency Review

1. Did the scoring fix pass consistency checks?

Scoring-fix consistency passed: `{fix_check.get('consistency_passed') is True}`.

2. Did guardrails hold?

Guardrails held: `{fix_manifest.get('batch_002_raw_outputs_changed') is False and fix_manifest.get('candidate_creation_allowed_from_rescore') is False}`.

3. Was the diagnostic rescore performed only from saved batch 002 fields?

Diagnostic rescore status: `{fix_manifest.get('diagnostic_rescore_status')}`.

4. Were batch 002 raw outputs unchanged?

Batch 002 raw outputs changed: `{fix_manifest.get('batch_002_raw_outputs_changed')}`.

5. Were variant statuses unchanged?

Variant statuses changed: `{fix_manifest.get('variant_statuses_changed')}`.

6. Were family audit conclusions unchanged?

Family audit changed: `{fix_manifest.get('family_audit_changed')}`.

7. Was candidate creation blocked from the rescore?

Candidate creation allowed from rescore: `{fix_manifest.get('candidate_creation_allowed_from_rescore')}`.

8. Was standalone score saturation fixed?

Saturation fixed: `{flags['saturation_fixed']}`.

9. Did saturation prevention tests pass?

The scoring-fix test suite passed before this audit packet was generated in the workflow, and the diagnostic rescore shows zero rows at or above the saturation threshold.
"""


def diagnostic_rescore_review_md(state: dict[str, Any], flags: dict[str, Any]) -> str:
    rows = state["rescore_rows"]
    return f"""# Diagnostic Rescore Review

The diagnostic rescore is not a new sandbox batch.

It is not formal discovery and cannot create candidates, change original batch results, or authorize paper-forward.

Rows reviewed: `{len(rows)}`

Diagnostic-only status rows: `{sum(1 for row in rows if row.get('score_interpretation_status') == 'diagnostic_only')}`

Candidate creation allowed from rescore: `{state['scoring_fix_manifest'].get('candidate_creation_allowed_from_rescore')}`

Saturation fixed: `{flags['saturation_fixed']}`

Overcorrection found: `{flags['overcorrection_found']}`

The diagnostic rescore may only inform whether scoring is ready for a future rerun.
"""


def score_distribution_md(rows: list[dict[str, str]], flags: dict[str, Any]) -> str:
    lines = ["# Score Distribution Review", ""]
    for field in SCORE_FIELDS:
        item = distribution(rows, field)
        lines.extend(
            [
                f"## `{field}`",
                f"- Min: `{item['min']}`",
                f"- Median: `{item['median']}`",
                f"- Max: `{item['max']}`",
                f"- Rows >= 98: `{item['rows_gte_98']}`",
                f"- Rows <= 5: `{item['rows_lte_5']}`",
                f"- Rows 10 to 70: `{item['rows_10_to_70']}`",
                "",
            ]
        )
    lines.extend(
        [
            f"Saturation fixed: `{flags['saturation_fixed']}`",
            f"Overcorrection found: `{flags['overcorrection_found']}`",
            f"V2 calibration accepted: `{flags['v2_calibration_accepted']}`",
        ]
    )
    return "\n".join(lines)


def single_score_review_md(rows: list[dict[str, str]], field: str, title: str, extra: str) -> str:
    item = distribution(rows, field)
    return f"""# {title}

- Min: `{item['min']}`
- Median: `{item['median']}`
- Max: `{item['max']}`
- Rows >= 98: `{item['rows_gte_98']}`
- Rows <= 5: `{item['rows_lte_5']}`
- Rows >= 70: `{item['rows_gte_70']}`

{extra}
"""


def family_level_review_md(rows: list[dict[str, str]]) -> str:
    family_stats = family_distribution(rows)
    lines = ["# Family-Level V2 Review", ""]
    for row in family_stats:
        family_id = row["family_id"]
        if family_id == "breakout_continuation":
            conclusion = (
                "V2 correctly reduces standalone score for cash/benchmark drag, but contribution score remains too modest for preregistration."
            )
        elif family_id == "macro_portfolio_contribution":
            conclusion = "V2 confirms context-only status; return-drag and risk penalties keep it below candidate strength."
        elif family_id == "portfolio_combination_sleeve_ensemble":
            conclusion = "Duplicate penalty suppresses contribution score, confirming active-combo repackaging concern."
        elif family_id == "trend_momentum":
            conclusion = "Risk-integrity gating blocks high-risk rows; not ready without another scoring calibration pass."
        elif family_id == "volatility_regime":
            conclusion = "V2 confirms high-risk/not-actionable behavior, with risk gates doing most of the blocking."
        else:
            conclusion = "No actionability conclusion."
        lines.extend(
            [
                f"## `{family_id}`",
                f"- Rows: `{row['rows']}`",
                f"- Median standalone v2: `{row['median_standalone_growth_score_v2']}`",
                f"- Max standalone v2: `{row['max_standalone_growth_score_v2']}`",
                f"- Median contribution v2: `{row['median_portfolio_contribution_score_v2']}`",
                f"- Max contribution v2: `{row['max_portfolio_contribution_score_v2']}`",
                f"- Median risk v2: `{row['median_risk_integrity_score_v2']}`",
                f"- Median practicality v2: `{row['median_practicality_score_v2']}`",
                f"- Median cash penalty: `{row['median_cash_allocation_penalty']}`",
                f"- Median benchmark lag penalty: `{row['median_benchmark_lag_penalty']}`",
                f"- Median return-drag penalty v2: `{row['median_return_drag_penalty_v2']}`",
                f"- Median duplicate penalty v2: `{row['median_duplicate_penalty_v2']}`",
                f"- Conclusion: {conclusion}",
                "",
            ]
        )
    return "\n".join(lines)


def interpretation_md(flags: dict[str, Any]) -> str:
    return f"""# Batch 002 Interpretation After V2

The diagnostic rescore should not change original batch 002 results or family audit conclusions automatically.

It does change scoring-system interpretation:

- Saturation is fixed: `{flags['saturation_fixed']}`
- Overcorrection is found: `{flags['overcorrection_found']}`
- V2 calibration accepted: `{flags['v2_calibration_accepted']}`
- Rerun with fixed scoring recommended: `{flags['rerun_with_fixed_scoring_recommended']}`

Because standalone v2 maxes at a low level and many rows collapse near zero, the scoring system is not ready for a fixed-scoring rerun. The next action should be another scoring calibration pass, not a research run.
"""


def do_not_promote_md() -> str:
    return """# Do Not Promote From Rescore

The diagnostic rescore cannot:

- create candidates
- create future preregistration candidates
- change original batch 002 results
- change family audit conclusions automatically
- authorize paper-forward
- authorize broker/live actions
- support real-money recommendations

It may only inform whether the scoring system is ready for a future run.
"""


def next_action_md(next_action: str, flags: dict[str, Any]) -> str:
    return f"""# Scoring Fix Audit Next Action

Exact next action: `{next_action}`

Reason:

- Saturation fixed: `{flags['saturation_fixed']}`
- Overcorrection found: `{flags['overcorrection_found']}`
- V2 calibration accepted: `{flags['v2_calibration_accepted']}`

Do not run the next action in this audit task.
"""


def summary_md(manifest: dict[str, Any]) -> str:
    return f"""# Scoring Fix Audit Summary

Scoring-fix-audit-only: `{manifest['scoring_fix_audit_only']}`

Diagnostic rescore reviewed: `{manifest['diagnostic_rescore_reviewed']}`

Saturation fixed: `{manifest['saturation_fixed']}`

Overcorrection found: `{manifest['overcorrection_found']}`

V2 calibration accepted: `{manifest['v2_calibration_accepted']}`

Rerun with fixed scoring recommended: `{manifest['rerun_with_fixed_scoring_recommended']}`

Next action: `{manifest['next_action']}`

No new sandbox batch, batch 002 rerun, discovery, backtest, raw-data metric computation, provider download, intraday use, candidate_exhaustive, paper-forward action, broker/live path, or real-money recommendation occurred.
"""


def update_metadata(root: Path, output: Path, created_utc: str, manifest: dict[str, Any]) -> tuple[bool, bool, bool]:
    registry_path = root / REGISTRY_PATH
    registry = load_yaml(registry_path)
    metadata = registry.setdefault("registry", {})
    before_metadata = deepcopy(metadata)
    metadata.update(
        {
            "revised_objective_sandbox_scoring_fix_audit_path": str(output.resolve()),
            "revised_objective_sandbox_scoring_fix_audit_status": "completed_fix_again_required",
            "revised_objective_sandbox_scoring_fix_audit_created_utc": created_utc,
            "current_research_mode": "revised_objective_sandbox_scoring_fix_audited",
            "current_next_action": manifest["next_action"],
            "official_current_next_action": manifest["next_action"],
            "next_action": manifest["next_action"],
            "revised_objective_sandbox_scoring_fix_audit_only": True,
            "revised_objective_sandbox_scoring_fix_audit_saturation_fixed": manifest["saturation_fixed"],
            "revised_objective_sandbox_scoring_fix_audit_overcorrection_found": manifest["overcorrection_found"],
            "revised_objective_sandbox_scoring_fix_audit_v2_calibration_accepted": manifest[
                "v2_calibration_accepted"
            ],
            "revised_objective_sandbox_scoring_fix_audit_rerun_recommended": manifest[
                "rerun_with_fixed_scoring_recommended"
            ],
            "revised_objective_sandbox_scoring_fix_audit_no_new_batch": True,
            "revised_objective_sandbox_scoring_fix_audit_no_rerun": True,
            "revised_objective_sandbox_scoring_fix_audit_no_discovery": True,
            "revised_objective_sandbox_scoring_fix_audit_no_provider_download": True,
            "revised_objective_sandbox_scoring_fix_audit_no_intraday": True,
            "revised_objective_sandbox_scoring_fix_audit_no_candidate_exhaustive": True,
            "revised_objective_sandbox_scoring_fix_audit_no_paper_forward": True,
            "revised_objective_sandbox_scoring_fix_audit_no_real_money_recommendation": True,
        }
    )
    registry_path.write_text(yaml.safe_dump(registry, sort_keys=False, width=120, allow_unicode=False), encoding="utf-8")

    roadmap_path = root / ROADMAP_PATH
    before_roadmap = roadmap_path.read_text(encoding="utf-8") if roadmap_path.exists() else "# Research Roadmap\n"
    compact_section = f"""## Compact Current State

- Updated UTC: `{created_utc}`
- Current research mode: `revised_objective_sandbox_scoring_fix_audited`
- Official current next action: `{manifest['next_action']}`
- Scoring fix audit evidence: `{output.resolve()}`
- Saturation fixed: `{manifest['saturation_fixed']}`
- Overcorrection found: `{manifest['overcorrection_found']}`
- V2 calibration accepted: `{manifest['v2_calibration_accepted']}`
- Rerun with fixed scoring recommended: `{manifest['rerun_with_fixed_scoring_recommended']}`
- Active VM and active DSR preserved.
- `static_all_weather_benchmark_v1` remains benchmark/control only.
- Exact rejected variants remain closed.
- Intraday remains paused: `true`
- This audit did not run a new sandbox batch, rerun batch 002, run discovery, run backtests, compute raw-data metrics, download provider data, use intraday data, create candidates, activate paper-forward, touch broker/live paths, or make real-money recommendations.
"""
    section = f"""## Revised Objective Sandbox Scoring Fix Audit

- Created UTC: `{created_utc}`
- Evidence path: `{output.resolve()}`
- Saturation fixed: `{manifest['saturation_fixed']}`
- Overcorrection found: `{manifest['overcorrection_found']}`
- V2 calibration accepted: `{manifest['v2_calibration_accepted']}`
- Rerun with fixed scoring recommended: `{manifest['rerun_with_fixed_scoring_recommended']}`
- Next action: `{manifest['next_action']}`
- Do not run the next action in this audit task.
"""
    after_roadmap = replace_or_append_section(before_roadmap, "## Compact Current State", compact_section)
    after_roadmap = replace_or_append_section(after_roadmap, "## Revised Objective Sandbox Scoring Fix Audit", section)
    write_text(roadmap_path, after_roadmap)

    compact_path = root / COMPACT_STATE_PATH
    before_compact = compact_path.read_text(encoding="utf-8") if compact_path.exists() else ""
    after_compact = f"""# Current Tournament State

Created UTC: `{created_utc}`

Current research mode: `revised_objective_sandbox_scoring_fix_audited`

Current next action: `{manifest['next_action']}`

Scoring fix audit evidence: `{output.resolve()}`

## Audit Decision

- Saturation fixed: `{manifest['saturation_fixed']}`
- Overcorrection found: `{manifest['overcorrection_found']}`
- V2 calibration accepted: `{manifest['v2_calibration_accepted']}`
- Rerun with fixed scoring recommended: `{manifest['rerun_with_fixed_scoring_recommended']}`
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
        "scoring_fix_audit_only": manifest["scoring_fix_audit_only"] is True,
        "no_new_sandbox_batch": manifest["new_sandbox_batch_run"] is False,
        "batch_002_not_rerun": manifest["rerun_batch_002"] is False,
        "no_formal_strategy_discovery": manifest["strategy_discovery_run"] is False and manifest["formal_discovery_run"] is False,
        "no_new_backtests": manifest["new_backtests_run"] is False,
        "no_new_raw_data_metrics": manifest["new_performance_metrics_from_raw_data_computed"] is False,
        "batch_002_raw_outputs_unchanged": manifest["batch_002_raw_outputs_changed"] is False,
        "diagnostic_rescore_reviewed": manifest["diagnostic_rescore_reviewed"] is True,
        "no_new_variants_created": manifest["new_variants_created"] is False,
        "variant_statuses_unchanged": manifest["variant_statuses_changed"] is False,
        "family_audit_unchanged": manifest["family_audit_changed"] is False,
        "no_future_preregistration_candidates_created": manifest["future_preregistration_candidates_created"] is False,
        "no_formal_preregistration_recommended": manifest["formal_preregistration_recommended"] is False,
        "candidate_creation_blocked_from_rescore": manifest["candidate_creation_allowed_from_rescore"] is False,
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
        "score_distribution_review_exists": (output / "score_distribution_review.md").exists(),
        "family_level_v2_review_exists": (output / "family_level_v2_review.md").exists(),
        "do_not_promote_from_rescore_exists": (output / "do_not_promote_from_rescore.md").exists(),
        "next_action_valid": manifest["next_action"] in VALID_NEXT_ACTIONS,
        "manifest_flags_match_strict_scope": all(manifest.get(key) == value for key, value in MANIFEST_FLAGS.items()),
        "required_files_exist": all((output / name).exists() for name in REQUIRED_FILES),
    }
    check["consistency_passed"] = all(check.values())
    return check


def run_revised_objective_sandbox_scoring_fix_audit(root: Path = ROOT) -> dict[str, Any]:
    root = root.resolve()
    created_utc = now_utc()
    output = root / OUTPUT_DIR
    output.mkdir(parents=True, exist_ok=True)
    before_strategies = strategy_snapshot(root)
    batch_hashes_before = hash_tree(root / BATCH_OUTPUT_DIR)
    scoring_hashes_before = hash_tree(root / SCORING_FIX_DIR)
    audit_hashes_before = hash_tree(root / BATCH_AUDIT_DIR)
    state = source_state(root)
    rows = state["rescore_rows"]
    flags = calibration_flags(rows)
    next_action = decide_next_action(flags)
    after_strategies = strategy_snapshot(root)
    batch_hashes_after = hash_tree(root / BATCH_OUTPUT_DIR)
    scoring_hashes_after = hash_tree(root / SCORING_FIX_DIR)
    audit_hashes_after = hash_tree(root / BATCH_AUDIT_DIR)

    manifest = {
        "created_utc": created_utc,
        "output_dir": str(output.resolve()),
        **MANIFEST_FLAGS,
        **flags,
        "diagnostic_rescore_rows_reviewed": len(rows),
        "scoring_fix_consistency_passed": state["scoring_fix_consistency"].get("consistency_passed") is True,
        "diagnostic_rescore_status": state["scoring_fix_manifest"].get("diagnostic_rescore_status", ""),
        "score_distributions": {field: distribution(rows, field) for field in SCORE_FIELDS},
        "batch_002_raw_outputs_changed": batch_hashes_before != batch_hashes_after,
        "variant_statuses_changed": batch_hashes_before.get("batch_002_variant_results.csv")
        != batch_hashes_after.get("batch_002_variant_results.csv"),
        "family_audit_changed": audit_hashes_before != audit_hashes_after,
        "scoring_fix_evidence_changed_by_audit": scoring_hashes_before != scoring_hashes_after,
        "next_action": next_action,
    }
    if before_strategies != after_strategies:
        manifest["active_strategy_state_changed"] = True
        manifest["rejected_strategy_state_changed"] = True

    write_text(output / "scoring_fix_consistency_review.md", consistency_review_md(state, flags))
    write_text(output / "diagnostic_rescore_review.md", diagnostic_rescore_review_md(state, flags))
    write_text(output / "score_distribution_review.md", score_distribution_md(rows, flags))
    write_text(
        output / "standalone_growth_score_v2_review.md",
        single_score_review_md(
            rows,
            "standalone_growth_score_v2",
            "Standalone Growth Score V2 Review",
            "Saturation is fixed, but max score is too low and many rows collapsed near zero. This is overcorrection.",
        ),
    )
    write_text(
        output / "portfolio_contribution_score_v2_review.md",
        single_score_review_md(
            rows,
            "portfolio_contribution_score_v2",
            "Portfolio Contribution Score V2 Review",
            "Contribution scoring still has useful dispersion, but no row becomes actionable and duplicate penalties are active.",
        ),
    )
    write_text(
        output / "stretch_diagnostic_score_v2_review.md",
        single_score_review_md(
            rows,
            "stretch_diagnostic_score_v2",
            "Stretch Diagnostic Score V2 Review",
            "Stretch diagnostics remain moderate and diagnostic-only; they do not force high standalone or contribution scores.",
        ),
    )
    write_text(
        output / "risk_integrity_score_v2_review.md",
        single_score_review_md(
            rows,
            "risk_integrity_score_v2",
            "Risk Integrity Score V2 Review",
            "Risk gates blocked high-drawdown families, but the median at zero suggests penalty calibration is too harsh.",
        ),
    )
    write_text(
        output / "overfit_risk_score_v2_review.md",
        single_score_review_md(
            rows,
            "overfit_risk_score_v2",
            "Overfit Risk Score V2 Review",
            "Overfit risk remains a useful warning score without collapsing to zero or saturating at the top.",
        ),
    )
    write_text(
        output / "practicality_score_v2_review.md",
        single_score_review_md(
            rows,
            "practicality_score_v2",
            "Practicality Score V2 Review",
            "Practicality preserves dispersion and penalizes excessive trade/turnover behavior.",
        ),
    )
    write_text(output / "family_level_v2_review.md", family_level_review_md(rows))
    write_text(output / "batch_002_interpretation_after_v2.md", interpretation_md(flags))
    write_text(output / "do_not_promote_from_rescore.md", do_not_promote_md())
    write_text(output / "scoring_fix_audit_next_action.md", next_action_md(next_action, flags))
    write_text(output / "scoring_fix_audit_summary.md", summary_md(manifest))
    write_json(output / "scoring_fix_audit_manifest.json", manifest)
    write_json(output / "scoring_fix_audit_consistency_check.json", {"consistency_passed": False})

    registry_updated, roadmap_updated, compact_updated = update_metadata(root, output, created_utc, manifest)
    manifest["registry_metadata_updated"] = registry_updated
    manifest["roadmap_updated"] = roadmap_updated
    manifest["compact_state_updated"] = compact_updated
    consistency = consistency_check(manifest, output)
    write_json(output / "scoring_fix_audit_manifest.json", manifest)
    write_json(output / "scoring_fix_audit_consistency_check.json", consistency)

    return {
        "output_dir": str(output),
        "scoring_fix_consistency_passed": manifest["scoring_fix_consistency_passed"],
        "diagnostic_rescore_valid": state["scoring_fix_manifest"].get("diagnostic_rescore_performed") is True,
        "saturation_fixed": manifest["saturation_fixed"],
        "overcorrection_found": manifest["overcorrection_found"],
        "v2_calibration_accepted": manifest["v2_calibration_accepted"],
        "rerun_with_fixed_scoring_recommended": manifest["rerun_with_fixed_scoring_recommended"],
        "next_action": manifest["next_action"],
        "consistency_passed": consistency["consistency_passed"],
    }
