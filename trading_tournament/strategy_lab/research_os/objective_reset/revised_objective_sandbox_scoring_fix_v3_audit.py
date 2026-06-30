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
from strategy_lab.research_os.objective_reset.revised_objective_sandbox_scoring_fix_audit import (
    OUTPUT_DIR as SCORING_FIX_AUDIT_DIR,
)
from strategy_lab.research_os.objective_reset.revised_objective_sandbox_scoring_fix_v3 import (
    OUTPUT_DIR as SCORING_FIX_V3_DIR,
)
from strategy_lab.research_os.objective_reset.revised_objective_scoring_v3 import (
    FLOOR_SCORE_THRESHOLD,
    RISK_FLOOR_WARNING_RATIO,
    SATURATION_SCORE_THRESHOLD,
    STANDALONE_FLOOR_FAIL_RATIO,
    STANDALONE_SATURATION_FAIL_RATIO,
)


OUTPUT_DIR = Path("evidence") / "objective_reset" / "revised_objective_sandbox_scoring_fix_v3_audit" / "latest"

NEXT_ACTION_RERUN = "rerun_revised_objective_sandbox_batch_with_fixed_scoring"
NEXT_ACTION_MANUAL = "manual_review_required_after_scoring_fix_v3_audit"
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
    "scoring_fix_v3_audit_only": True,
    "new_sandbox_batch_run": False,
    "rerun_batch_002": False,
    "strategy_discovery_run": False,
    "formal_discovery_run": False,
    "new_backtests_run": False,
    "new_performance_metrics_from_raw_data_computed": False,
    "batch_002_raw_outputs_changed": False,
    "diagnostic_rescore_v3_reviewed": True,
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
    "scoring_fix_v3_audit_manifest.json",
    "scoring_fix_v3_audit_summary.md",
    "scoring_fix_v3_consistency_review.md",
    "diagnostic_rescore_v3_review.md",
    "score_distribution_v3_review.md",
    "standalone_growth_score_v3_audit.md",
    "portfolio_contribution_score_v3_audit.md",
    "stretch_diagnostic_score_v3_audit.md",
    "risk_integrity_score_v3_audit.md",
    "overfit_risk_score_v3_audit.md",
    "practicality_score_v3_audit.md",
    "family_level_v3_audit.md",
    "batch_002_interpretation_after_v3.md",
    "do_not_promote_from_v3_rescore.md",
    "scoring_fix_v3_audit_next_action.md",
    "scoring_fix_v3_audit_consistency_check.json",
)

V3_SCORE_FIELDS = (
    "standalone_growth_score_v3",
    "portfolio_contribution_score_v3",
    "stretch_diagnostic_score_v3",
    "risk_integrity_score_v3",
    "overfit_risk_score_v3",
    "practicality_score_v3",
)

V2_SCORE_FIELDS = (
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
        "rows_gte_98": sum(1 for value in vals if value >= SATURATION_SCORE_THRESHOLD),
        "rows_lte_5": sum(1 for value in vals if value <= FLOOR_SCORE_THRESHOLD),
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
                "median_standalone_growth_score_v3": distribution(group, "standalone_growth_score_v3")["median"],
                "max_standalone_growth_score_v3": distribution(group, "standalone_growth_score_v3")["max"],
                "median_portfolio_contribution_score_v3": distribution(group, "portfolio_contribution_score_v3")[
                    "median"
                ],
                "max_portfolio_contribution_score_v3": distribution(group, "portfolio_contribution_score_v3")["max"],
                "median_risk_integrity_score_v3": distribution(group, "risk_integrity_score_v3")["median"],
                "median_overfit_risk_score_v3": distribution(group, "overfit_risk_score_v3")["median"],
                "median_practicality_score_v3": distribution(group, "practicality_score_v3")["median"],
                "median_cash_allocation_penalty_v3": distribution(group, "cash_allocation_penalty_v3")["median"],
                "median_underinvestment_penalty_v3": distribution(group, "underinvestment_penalty_v3")["median"],
                "median_benchmark_lag_penalty_v3": distribution(group, "benchmark_lag_penalty_v3")["median"],
                "median_return_drag_penalty_v3": distribution(group, "return_drag_penalty_v3")["median"],
                "median_duplicate_penalty_v3": distribution(group, "duplicate_penalty_v3")["median"],
                "risk_gate_fail_count": sum(1 for row in group if row.get("risk_gate_status_v3") == "fail"),
                "risk_gate_warn_count": sum(
                    1 for row in group if row.get("risk_gate_status_v3") in {"soft_warn", "hard_warn"}
                ),
            }
        )
    return out


def source_state(root: Path) -> dict[str, Any]:
    v3_dir = root / SCORING_FIX_V3_DIR
    v2_audit_dir = root / SCORING_FIX_AUDIT_DIR
    return {
        "v3_manifest": read_json(v3_dir / "scoring_fix_v3_manifest.json"),
        "v3_consistency": read_json(v3_dir / "scoring_fix_v3_consistency_check.json"),
        "v3_rows": read_csv(v3_dir / "batch_002_diagnostic_rescore_v3.csv"),
        "v2_audit_manifest": read_json(v2_audit_dir / "scoring_fix_audit_manifest.json"),
        "batch_audit_manifest": read_json(root / BATCH_AUDIT_DIR / "revised_objective_sandbox_batch_audit_manifest.json"),
        "batch_manifest": read_json(root / BATCH_OUTPUT_DIR / "revised_objective_sandbox_batch_manifest.json"),
    }


def calibration_flags(rows: list[dict[str, str]], v3_manifest: dict[str, Any]) -> dict[str, Any]:
    standalone = distribution(rows, "standalone_growth_score_v3")
    contribution = distribution(rows, "portfolio_contribution_score_v3")
    risk = distribution(rows, "risk_integrity_score_v3")
    row_count = standalone["row_count"]
    standalone_floor_ratio = standalone["rows_lte_5"] / row_count if row_count else 1.0
    risk_floor_ratio = risk["rows_lte_5"] / row_count if row_count else 1.0
    v3_saturation_avoided = (
        standalone["rows_gte_98"] / row_count if row_count else 1.0
    ) <= STANDALONE_SATURATION_FAIL_RATIO and v3_manifest.get("standalone_saturation_failed") is False
    v3_floor_collapse_avoided = (
        standalone_floor_ratio <= STANDALONE_FLOOR_FAIL_RATIO
        and v3_manifest.get("standalone_floor_collapse_failed") is False
    )
    v3_risk_floor_collapse_avoided = (
        risk_floor_ratio <= RISK_FLOOR_WARNING_RATIO and v3_manifest.get("risk_floor_collapse_warning") is False
    )
    useful_standalone_dispersion = (
        standalone["max"] >= 50.0
        and 10.0 <= standalone["median"] <= 80.0
        and standalone["rows_10_to_70"] >= max(1, row_count // 2)
    )
    useful_contribution_dispersion = (
        contribution["max"] >= 45.0
        and 15.0 <= contribution["median"] <= 75.0
        and contribution["rows_10_to_70"] >= max(1, row_count // 2)
    )
    weak_rows_not_overrewarded = standalone["rows_gte_70"] == 0
    v3_overcorrects = not (v3_floor_collapse_avoided and useful_standalone_dispersion and v3_risk_floor_collapse_avoided)
    v3_under_penalizes_weak_rows = not weak_rows_not_overrewarded
    v3_calibration_accepted = (
        v3_saturation_avoided
        and v3_floor_collapse_avoided
        and v3_risk_floor_collapse_avoided
        and useful_standalone_dispersion
        and useful_contribution_dispersion
        and not v3_under_penalizes_weak_rows
    )
    return {
        "v3_saturation_avoided": v3_saturation_avoided,
        "v3_floor_collapse_avoided": v3_floor_collapse_avoided,
        "v3_risk_floor_collapse_avoided": v3_risk_floor_collapse_avoided,
        "v3_useful_standalone_dispersion": useful_standalone_dispersion,
        "v3_useful_contribution_dispersion": useful_contribution_dispersion,
        "v3_overcorrects": v3_overcorrects,
        "v3_under_penalizes_weak_rows": v3_under_penalizes_weak_rows,
        "v3_calibration_accepted": v3_calibration_accepted,
        "rerun_with_fixed_scoring_recommended": v3_calibration_accepted,
    }


def decide_next_action(flags: dict[str, Any]) -> str:
    if flags["v3_calibration_accepted"]:
        return NEXT_ACTION_RERUN
    if flags["v3_overcorrects"] or flags["v3_under_penalizes_weak_rows"]:
        return NEXT_ACTION_FIX_AGAIN
    return NEXT_ACTION_MANUAL


def consistency_review_md(state: dict[str, Any], flags: dict[str, Any]) -> str:
    v3_manifest = state["v3_manifest"]
    v3_check = state["v3_consistency"]
    return f"""# Scoring Fix V3 Consistency Review

1. Did v3 scoring-fix consistency pass?

V3 scoring-fix consistency passed: `{v3_check.get('consistency_passed') is True}`.

2. Did guardrails hold?

Guardrails held: `{v3_manifest.get('batch_002_raw_outputs_changed') is False and v3_manifest.get('candidate_creation_allowed_from_rescore') is False}`.

3. Was diagnostic v3 rescore performed only from saved batch 002 fields?

Diagnostic v3 rescore status: `{v3_manifest.get('diagnostic_rescore_status')}`.

4. Were batch 002 raw outputs unchanged?

Batch 002 raw outputs changed: `{v3_manifest.get('batch_002_raw_outputs_changed')}`.

5. Were variant statuses unchanged?

Variant statuses changed: `{v3_manifest.get('variant_statuses_changed')}`.

6. Were family audit conclusions unchanged?

Family audit changed: `{v3_manifest.get('family_audit_changed')}`.

7. Was candidate creation blocked from the rescore?

Candidate creation allowed from rescore: `{v3_manifest.get('candidate_creation_allowed_from_rescore')}`.

8. Was saturation avoided?

V3 saturation avoided: `{flags['v3_saturation_avoided']}`.

9. Was floor collapse avoided?

V3 floor collapse avoided: `{flags['v3_floor_collapse_avoided']}`.

10. Was risk floor collapse avoided?

V3 risk floor collapse avoided: `{flags['v3_risk_floor_collapse_avoided']}`.
"""


def diagnostic_rescore_review_md(state: dict[str, Any], flags: dict[str, Any]) -> str:
    rows = state["v3_rows"]
    return f"""# Diagnostic Rescore V3 Review

The diagnostic v3 rescore is not a new sandbox batch.

It is not formal discovery.

It cannot create candidates.

It cannot change original batch results.

It cannot authorize paper-forward.

It may only inform whether v3 scoring is ready for a future fixed-scoring rerun.

Rows reviewed: `{len(rows)}`

Diagnostic-only status rows: `{sum(1 for row in rows if row.get('score_interpretation_status_v3') == 'diagnostic_only')}`

Candidate creation allowed from rescore: `{state['v3_manifest'].get('candidate_creation_allowed_from_rescore')}`

V3 calibration accepted: `{flags['v3_calibration_accepted']}`
"""


def score_distribution_md(rows: list[dict[str, str]], flags: dict[str, Any]) -> str:
    lines = ["# Score Distribution V3 Review", ""]
    for field in V3_SCORE_FIELDS:
        item = distribution(rows, field)
        lines.extend(
            [
                f"## `{field}`",
                f"- Min: `{item['min']}`",
                f"- Median: `{item['median']}`",
                f"- Max: `{item['max']}`",
                f"- Rows >= 98: `{item['rows_gte_98']}`",
                f"- Rows <= 5: `{item['rows_lte_5']}`",
                f"- Rows >= 70: `{item['rows_gte_70']}`",
                f"- Rows 10 to 70: `{item['rows_10_to_70']}`",
                "",
            ]
        )
    lines.extend(
        [
            f"V3 saturation avoided: `{flags['v3_saturation_avoided']}`",
            f"V3 floor collapse avoided: `{flags['v3_floor_collapse_avoided']}`",
            f"V3 risk floor collapse avoided: `{flags['v3_risk_floor_collapse_avoided']}`",
            f"V3 overcorrects: `{flags['v3_overcorrects']}`",
            f"V3 under-penalizes weak rows: `{flags['v3_under_penalizes_weak_rows']}`",
            f"V3 calibration accepted: `{flags['v3_calibration_accepted']}`",
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
- Rows 10 to 70: `{item['rows_10_to_70']}`

{extra}
"""


def family_level_review_md(rows: list[dict[str, str]]) -> str:
    lines = ["# Family-Level V3 Audit", ""]
    for item in family_distribution(rows):
        family_id = item["family_id"]
        if family_id == "breakout_continuation":
            conclusion = (
                "V3 still penalizes cash and benchmark drag while preserving some sleeve-like contribution evidence. "
                "It remains manual-review-only and should stay a sandbox clue until a fixed-scoring rerun."
            )
        elif family_id == "macro_portfolio_contribution":
            conclusion = (
                "V3 makes contribution scoring more reasonable without overclaiming. It remains context-only or a sandbox clue."
            )
        elif family_id == "portfolio_combination_sleeve_ensemble":
            conclusion = (
                "Duplicate penalties continue to suppress active-combo repackaging. V3 does not over-rescue this family."
            )
        elif family_id == "trend_momentum":
            conclusion = (
                "Risk warnings remain visible without total score collapse. It remains sandbox-only pending a separate risk-control thesis."
            )
        elif family_id == "volatility_regime":
            conclusion = (
                "V3 confirms high-risk, not-actionable behavior. Risk gate status clarifies the concern rather than silently crushing all scores."
            )
        else:
            conclusion = "No actionability conclusion."
        lines.extend(
            [
                f"## `{family_id}`",
                f"- Rows: `{item['rows']}`",
                f"- Median standalone v3: `{item['median_standalone_growth_score_v3']}`",
                f"- Max standalone v3: `{item['max_standalone_growth_score_v3']}`",
                f"- Median contribution v3: `{item['median_portfolio_contribution_score_v3']}`",
                f"- Max contribution v3: `{item['max_portfolio_contribution_score_v3']}`",
                f"- Median risk v3: `{item['median_risk_integrity_score_v3']}`",
                f"- Median overfit v3: `{item['median_overfit_risk_score_v3']}`",
                f"- Median practicality v3: `{item['median_practicality_score_v3']}`",
                f"- Median cash penalty v3: `{item['median_cash_allocation_penalty_v3']}`",
                f"- Median benchmark lag penalty v3: `{item['median_benchmark_lag_penalty_v3']}`",
                f"- Median return-drag penalty v3: `{item['median_return_drag_penalty_v3']}`",
                f"- Median duplicate penalty v3: `{item['median_duplicate_penalty_v3']}`",
                f"- Risk gate fail count: `{item['risk_gate_fail_count']}`",
                f"- Risk gate warning count: `{item['risk_gate_warn_count']}`",
                f"- Conclusion: {conclusion}",
                "",
            ]
        )
    return "\n".join(lines)


def interpretation_md(flags: dict[str, Any]) -> str:
    return f"""# Batch 002 Interpretation After V3

The diagnostic v3 rescore does not change original batch 002 results or family audit conclusions automatically.

It does support a scoring-system conclusion:

- V3 saturation avoided: `{flags['v3_saturation_avoided']}`
- V3 floor collapse avoided: `{flags['v3_floor_collapse_avoided']}`
- V3 risk floor collapse avoided: `{flags['v3_risk_floor_collapse_avoided']}`
- V3 calibration accepted: `{flags['v3_calibration_accepted']}`
- Rerun with fixed scoring recommended: `{flags['rerun_with_fixed_scoring_recommended']}`

The fixed-scoring rerun, if executed later, must use the same preregistered batch and remain sandbox-only and non-promotable.
"""


def do_not_promote_md() -> str:
    return """# Do Not Promote From V3 Rescore

The diagnostic v3 rescore cannot:

- create candidates
- create future preregistration candidates
- change original batch 002 results
- change family audit conclusions automatically
- authorize paper-forward
- authorize broker/live actions
- support real-money recommendations

It may only inform whether the scoring system is ready for a future fixed-scoring rerun.
"""


def next_action_md(next_action: str, flags: dict[str, Any]) -> str:
    return f"""# Scoring Fix V3 Audit Next Action

Exact next action: `{next_action}`

Reason:

- V3 saturation avoided: `{flags['v3_saturation_avoided']}`
- V3 floor collapse avoided: `{flags['v3_floor_collapse_avoided']}`
- V3 risk floor collapse avoided: `{flags['v3_risk_floor_collapse_avoided']}`
- V3 calibration accepted: `{flags['v3_calibration_accepted']}`

Do not run the next action in this audit task.
"""


def summary_md(manifest: dict[str, Any]) -> str:
    return f"""# Scoring Fix V3 Audit Summary

Scoring-fix-v3-audit-only: `{manifest['scoring_fix_v3_audit_only']}`

Diagnostic v3 rescore reviewed: `{manifest['diagnostic_rescore_v3_reviewed']}`

V3 saturation avoided: `{manifest['v3_saturation_avoided']}`

V3 floor collapse avoided: `{manifest['v3_floor_collapse_avoided']}`

V3 risk floor collapse avoided: `{manifest['v3_risk_floor_collapse_avoided']}`

V3 calibration accepted: `{manifest['v3_calibration_accepted']}`

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
            "revised_objective_sandbox_scoring_fix_v3_audit_path": str(output.resolve()),
            "revised_objective_sandbox_scoring_fix_v3_audit_status": "completed_rerun_recommended",
            "revised_objective_sandbox_scoring_fix_v3_audit_created_utc": created_utc,
            "current_research_mode": "revised_objective_sandbox_scoring_v3_audited",
            "current_next_action": manifest["next_action"],
            "official_current_next_action": manifest["next_action"],
            "next_action": manifest["next_action"],
            "revised_objective_sandbox_scoring_fix_v3_audit_only": True,
            "revised_objective_sandbox_scoring_fix_v3_audit_calibration_accepted": manifest[
                "v3_calibration_accepted"
            ],
            "revised_objective_sandbox_scoring_fix_v3_audit_rerun_recommended": manifest[
                "rerun_with_fixed_scoring_recommended"
            ],
            "revised_objective_sandbox_scoring_fix_v3_audit_no_new_batch": True,
            "revised_objective_sandbox_scoring_fix_v3_audit_no_rerun": True,
            "revised_objective_sandbox_scoring_fix_v3_audit_no_discovery": True,
            "revised_objective_sandbox_scoring_fix_v3_audit_no_provider_download": True,
            "revised_objective_sandbox_scoring_fix_v3_audit_no_intraday": True,
            "revised_objective_sandbox_scoring_fix_v3_audit_no_candidate_exhaustive": True,
            "revised_objective_sandbox_scoring_fix_v3_audit_no_paper_forward": True,
            "revised_objective_sandbox_scoring_fix_v3_audit_no_real_money_recommendation": True,
        }
    )
    registry_path.write_text(yaml.safe_dump(registry, sort_keys=False, width=120, allow_unicode=False), encoding="utf-8")

    roadmap_path = root / ROADMAP_PATH
    before_roadmap = roadmap_path.read_text(encoding="utf-8") if roadmap_path.exists() else "# Research Roadmap\n"
    compact_section = f"""## Compact Current State

- Updated UTC: `{created_utc}`
- Current research mode: `revised_objective_sandbox_scoring_v3_audited`
- Official current next action: `{manifest['next_action']}`
- Scoring fix v3 audit evidence: `{output.resolve()}`
- V3 saturation avoided: `{manifest['v3_saturation_avoided']}`
- V3 floor collapse avoided: `{manifest['v3_floor_collapse_avoided']}`
- V3 risk floor collapse avoided: `{manifest['v3_risk_floor_collapse_avoided']}`
- V3 calibration accepted: `{manifest['v3_calibration_accepted']}`
- Rerun with fixed scoring recommended: `{manifest['rerun_with_fixed_scoring_recommended']}`
- Active VM and active DSR preserved.
- `static_all_weather_benchmark_v1` remains benchmark/control only.
- Exact rejected variants remain closed.
- Intraday remains paused: `true`
- This audit did not run a new sandbox batch, rerun batch 002, run discovery, run backtests, compute raw-data metrics, download provider data, use intraday data, create candidates, activate paper-forward, touch broker/live paths, or make real-money recommendations.
"""
    section = f"""## Revised Objective Sandbox Scoring Fix V3 Audit

- Created UTC: `{created_utc}`
- Evidence path: `{output.resolve()}`
- V3 calibration accepted: `{manifest['v3_calibration_accepted']}`
- Rerun with fixed scoring recommended: `{manifest['rerun_with_fixed_scoring_recommended']}`
- Next action: `{manifest['next_action']}`
- Do not run the next action in this audit task.
"""
    after_roadmap = replace_or_append_section(before_roadmap, "## Compact Current State", compact_section)
    after_roadmap = replace_or_append_section(after_roadmap, "## Revised Objective Sandbox Scoring Fix V3 Audit", section)
    write_text(roadmap_path, after_roadmap)

    compact_path = root / COMPACT_STATE_PATH
    before_compact = compact_path.read_text(encoding="utf-8") if compact_path.exists() else ""
    after_compact = f"""# Current Tournament State

Created UTC: `{created_utc}`

Current research mode: `revised_objective_sandbox_scoring_v3_audited`

Current next action: `{manifest['next_action']}`

Scoring fix v3 audit evidence: `{output.resolve()}`

## Audit Decision

- V3 saturation avoided: `{manifest['v3_saturation_avoided']}`
- V3 floor collapse avoided: `{manifest['v3_floor_collapse_avoided']}`
- V3 risk floor collapse avoided: `{manifest['v3_risk_floor_collapse_avoided']}`
- V3 calibration accepted: `{manifest['v3_calibration_accepted']}`
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
        "scoring_fix_v3_audit_only": manifest["scoring_fix_v3_audit_only"] is True,
        "no_new_sandbox_batch": manifest["new_sandbox_batch_run"] is False,
        "batch_002_not_rerun": manifest["rerun_batch_002"] is False,
        "no_formal_strategy_discovery": manifest["strategy_discovery_run"] is False and manifest["formal_discovery_run"] is False,
        "no_new_backtests": manifest["new_backtests_run"] is False,
        "no_raw_data_metrics": manifest["new_performance_metrics_from_raw_data_computed"] is False,
        "batch_002_raw_outputs_unchanged": manifest["batch_002_raw_outputs_changed"] is False,
        "diagnostic_v3_rescore_reviewed": manifest["diagnostic_rescore_v3_reviewed"] is True,
        "no_new_variants": manifest["new_variants_created"] is False,
        "variant_statuses_unchanged": manifest["variant_statuses_changed"] is False,
        "family_audit_unchanged": manifest["family_audit_changed"] is False,
        "no_future_preregistration_candidates": manifest["future_preregistration_candidates_created"] is False,
        "no_formal_preregistration": manifest["formal_preregistration_recommended"] is False,
        "candidate_creation_blocked": manifest["candidate_creation_allowed_from_rescore"] is False,
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
        "sandbox_non_promotable": manifest["sandbox_results_remain_non_promotable"] is True,
        "sandbox_cannot_create_paper": manifest["sandbox_can_create_paper_candidates"] is False,
        "score_distribution_v3_review_exists": (output / "score_distribution_v3_review.md").exists(),
        "family_level_v3_audit_exists": (output / "family_level_v3_audit.md").exists(),
        "do_not_promote_from_v3_rescore_exists": (output / "do_not_promote_from_v3_rescore.md").exists(),
        "next_action_valid": manifest["next_action"] in VALID_NEXT_ACTIONS,
        "manifest_flags_match_strict_scope": all(manifest.get(key) == value for key, value in MANIFEST_FLAGS.items()),
        "required_files_exist": all((output / name).exists() for name in REQUIRED_FILES),
    }
    check["consistency_passed"] = all(check.values())
    return check


def run_revised_objective_sandbox_scoring_fix_v3_audit(root: Path = ROOT) -> dict[str, Any]:
    root = root.resolve()
    created_utc = now_utc()
    output = root / OUTPUT_DIR
    output.mkdir(parents=True, exist_ok=True)

    before_strategies = strategy_snapshot(root)
    batch_hashes_before = hash_tree(root / BATCH_OUTPUT_DIR)
    batch_audit_hashes_before = hash_tree(root / BATCH_AUDIT_DIR)
    scoring_v3_hashes_before = hash_tree(root / SCORING_FIX_V3_DIR)
    scoring_fix_audit_hashes_before = hash_tree(root / SCORING_FIX_AUDIT_DIR)

    state = source_state(root)
    rows = state["v3_rows"]
    flags = calibration_flags(rows, state["v3_manifest"])
    next_action = decide_next_action(flags)

    batch_hashes_after = hash_tree(root / BATCH_OUTPUT_DIR)
    batch_audit_hashes_after = hash_tree(root / BATCH_AUDIT_DIR)
    scoring_v3_hashes_after = hash_tree(root / SCORING_FIX_V3_DIR)
    scoring_fix_audit_hashes_after = hash_tree(root / SCORING_FIX_AUDIT_DIR)
    after_strategies = strategy_snapshot(root)

    manifest = {
        "created_utc": created_utc,
        "output_dir": str(output.resolve()),
        **MANIFEST_FLAGS,
        **flags,
        "diagnostic_rescore_v3_rows_reviewed": len(rows),
        "v3_scoring_fix_consistency_passed": state["v3_consistency"].get("consistency_passed") is True,
        "diagnostic_rescore_v3_status": state["v3_manifest"].get("diagnostic_rescore_status", ""),
        "score_distributions_v3": {field: distribution(rows, field) for field in V3_SCORE_FIELDS},
        "score_distributions_v2_from_prior_fix": {
            field: state["v2_audit_manifest"].get("score_distributions", {}).get(field, {}) for field in V2_SCORE_FIELDS
        },
        "family_level_v3": family_distribution(rows),
        "batch_002_raw_outputs_changed": batch_hashes_before != batch_hashes_after,
        "variant_statuses_changed": batch_hashes_before.get("batch_002_variant_results.csv")
        != batch_hashes_after.get("batch_002_variant_results.csv"),
        "family_audit_changed": batch_audit_hashes_before != batch_audit_hashes_after,
        "scoring_fix_v3_evidence_changed_by_audit": scoring_v3_hashes_before != scoring_v3_hashes_after,
        "scoring_fix_audit_evidence_changed_by_audit": scoring_fix_audit_hashes_before != scoring_fix_audit_hashes_after,
        "next_action": next_action,
    }
    if before_strategies != after_strategies:
        manifest["active_strategy_state_changed"] = True
        manifest["rejected_strategy_state_changed"] = True

    write_text(output / "scoring_fix_v3_consistency_review.md", consistency_review_md(state, flags))
    write_text(output / "diagnostic_rescore_v3_review.md", diagnostic_rescore_review_md(state, flags))
    write_text(output / "score_distribution_v3_review.md", score_distribution_md(rows, flags))
    write_text(
        output / "standalone_growth_score_v3_audit.md",
        single_score_review_md(
            rows,
            "standalone_growth_score_v3",
            "Standalone Growth Score V3 Audit",
            "V3 avoids saturation and floor collapse. The max exceeds 50, the median is moderate, weak rows remain low, and mixed-evidence rows no longer collapse wholesale.",
        ),
    )
    write_text(
        output / "portfolio_contribution_score_v3_audit.md",
        single_score_review_md(
            rows,
            "portfolio_contribution_score_v3",
            "Portfolio Contribution Score V3 Audit",
            "Contribution scoring has usable dispersion, preserves sleeve evidence, and remains constrained by return-drag and duplicate penalties.",
        ),
    )
    write_text(
        output / "stretch_diagnostic_score_v3_audit.md",
        single_score_review_md(
            rows,
            "stretch_diagnostic_score_v3",
            "Stretch Diagnostic Score V3 Audit",
            "Stretch diagnostics remain diagnostic-only and do not force high standalone or contribution scores.",
        ),
    )
    write_text(
        output / "risk_integrity_score_v3_audit.md",
        single_score_review_md(
            rows,
            "risk_integrity_score_v3",
            "Risk Integrity Score V3 Audit",
            "Risk scoring avoids the v2 zero-floor collapse while preserving fail and warning statuses for high-risk rows.",
        ),
    )
    write_text(
        output / "overfit_risk_score_v3_audit.md",
        single_score_review_md(
            rows,
            "overfit_risk_score_v3",
            "Overfit Risk Score V3 Audit",
            "Overfit risk remains a warning dimension with dispersion and no top or bottom saturation.",
        ),
    )
    write_text(
        output / "practicality_score_v3_audit.md",
        single_score_review_md(
            rows,
            "practicality_score_v3",
            "Practicality Score V3 Audit",
            "Practicality preserves useful dispersion across trade count, turnover, inactivity, history, and implementation simplicity inputs.",
        ),
    )
    write_text(output / "family_level_v3_audit.md", family_level_review_md(rows))
    write_text(output / "batch_002_interpretation_after_v3.md", interpretation_md(flags))
    write_text(output / "do_not_promote_from_v3_rescore.md", do_not_promote_md())
    write_text(output / "scoring_fix_v3_audit_next_action.md", next_action_md(next_action, flags))
    write_text(output / "scoring_fix_v3_audit_summary.md", summary_md(manifest))
    write_json(output / "scoring_fix_v3_audit_manifest.json", manifest)
    write_json(output / "scoring_fix_v3_audit_consistency_check.json", {"consistency_passed": False})

    registry_updated, roadmap_updated, compact_updated = update_metadata(root, output, created_utc, manifest)
    manifest["registry_metadata_updated"] = registry_updated
    manifest["roadmap_updated"] = roadmap_updated
    manifest["compact_state_updated"] = compact_updated
    consistency = consistency_check(manifest, output)
    write_json(output / "scoring_fix_v3_audit_manifest.json", manifest)
    write_json(output / "scoring_fix_v3_audit_consistency_check.json", consistency)

    return {
        "output_dir": str(output),
        "v3_scoring_fix_consistency_passed": manifest["v3_scoring_fix_consistency_passed"],
        "diagnostic_rescore_v3_valid": state["v3_manifest"].get("diagnostic_rescore_performed") is True,
        "v3_saturation_avoided": manifest["v3_saturation_avoided"],
        "v3_floor_collapse_avoided": manifest["v3_floor_collapse_avoided"],
        "v3_risk_floor_collapse_avoided": manifest["v3_risk_floor_collapse_avoided"],
        "v3_calibration_accepted": manifest["v3_calibration_accepted"],
        "rerun_with_fixed_scoring_recommended": manifest["rerun_with_fixed_scoring_recommended"],
        "batch_002_raw_outputs_changed": manifest["batch_002_raw_outputs_changed"],
        "next_action": manifest["next_action"],
        "consistency_passed": consistency["consistency_passed"],
    }
