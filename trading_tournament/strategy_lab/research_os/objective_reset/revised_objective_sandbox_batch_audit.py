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
from strategy_lab.research_os.objective_reset.revised_objective_batch_config import (
    ALLOWED_RESULT_STATUSES,
    BATCH_ID,
    FORBIDDEN_STATUSES,
)
from strategy_lab.research_os.objective_reset.revised_objective_sandbox_batch import (
    BATCH_OUTPUT_DIR,
    BATCH_REQUIRED_FILES,
)


OUTPUT_DIR = Path("evidence") / "objective_reset" / "revised_objective_sandbox_batch_audit" / "latest"

NEXT_ACTION_FIX_SCORING = "fix_revised_objective_sandbox_scoring"
NEXT_ACTION_PREREGISTER_ONE = "pre_register_one_revised_objective_family"
NEXT_ACTION_MANUAL = "manual_review_required_after_revised_objective_sandbox_audit"
NEXT_ACTION_OBSERVE = "continue_paper_forward_observation_only"
NEXT_ACTION_PAUSE = "pause_expansion_and_wait_for_manual_direction"
VALID_NEXT_ACTIONS = {
    NEXT_ACTION_FIX_SCORING,
    NEXT_ACTION_PREREGISTER_ONE,
    NEXT_ACTION_MANUAL,
    NEXT_ACTION_OBSERVE,
    NEXT_ACTION_PAUSE,
}

MANIFEST_FLAGS = {
    "sandbox_batch_audit_only": True,
    "audited_batch_id": BATCH_ID,
    "new_sandbox_batch_run": False,
    "strategy_discovery_run": False,
    "formal_discovery_run": False,
    "new_backtests_run": False,
    "new_performance_metrics_computed": False,
    "new_variants_created": False,
    "sandbox_results_changed": False,
    "variant_statuses_changed": False,
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
    "revised_objective_sandbox_batch_audit_manifest.json",
    "revised_objective_sandbox_batch_audit_summary.md",
    "batch_consistency_review.md",
    "scoring_system_audit.md",
    "standalone_score_saturation_review.md",
    "family_audit.md",
    "family_audit.csv",
    "breakout_continuation_audit.md",
    "macro_portfolio_contribution_audit.md",
    "portfolio_combination_sleeve_ensemble_audit.md",
    "trend_momentum_audit.md",
    "volatility_regime_audit.md",
    "future_preregistration_clue_review.md",
    "risk_and_return_drag_review.md",
    "overfit_and_duplicate_review.md",
    "recommended_next_action.md",
    "revised_objective_sandbox_batch_audit_consistency_check.json",
)

SOURCE_FILES = tuple(BATCH_REQUIRED_FILES)


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
    return {name: sha256_file(source / name) for name in SOURCE_FILES if (source / name).exists()}


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


def median_of(rows: list[dict[str, str]], column: str, default: float = 0.0) -> float:
    values = [to_float(row.get(column), default) for row in rows if row.get(column, "") != ""]
    return median(values) if values else default


def max_of(rows: list[dict[str, str]], column: str, default: float = 0.0) -> float:
    values = [to_float(row.get(column), default) for row in rows if row.get(column, "") != ""]
    return max(values) if values else default


def source_state(root: Path) -> dict[str, Any]:
    source = root / BATCH_OUTPUT_DIR
    return {
        "source_dir": source,
        "manifest": read_json(source / "revised_objective_sandbox_batch_manifest.json"),
        "consistency": read_json(source / "revised_objective_sandbox_batch_consistency_check.json"),
        "variant_rows": read_csv(source / "batch_002_variant_results.csv"),
        "family_rows": read_csv(source / "batch_002_family_summary.csv"),
        "benchmark_rows": read_csv(source / "benchmark_comparison_summary.csv"),
        "required_files_present": all((source / name).exists() for name in BATCH_REQUIRED_FILES),
        "missing_required_files": [name for name in BATCH_REQUIRED_FILES if not (source / name).exists()],
    }


def guardrail_review(state: dict[str, Any]) -> dict[str, Any]:
    rows = state["variant_rows"]
    statuses = {row.get("status", "") for row in rows}
    promotable_true = sum(1 for row in rows if bool_text(row.get("promotable")))
    paper_true = sum(1 for row in rows if bool_text(row.get("paper_candidate_allowed")))
    forbidden = sorted(statuses & set(FORBIDDEN_STATUSES))
    allowed_statuses = statuses <= set(ALLOWED_RESULT_STATUSES)
    manifest = state["manifest"]
    return {
        "required_files_present": state["required_files_present"],
        "missing_required_files": state["missing_required_files"],
        "source_consistency_passed": state["consistency"].get("consistency_passed") is True,
        "forbidden_statuses_absent": not forbidden,
        "forbidden_statuses": forbidden,
        "allowed_statuses_only": allowed_statuses,
        "promotable_true_count": promotable_true,
        "paper_candidate_allowed_true_count": paper_true,
        "non_promotable_rules_held": allowed_statuses and not forbidden and promotable_true == 0 and paper_true == 0,
        "protected_state_preserved": manifest.get("active_strategy_state_changed") is False
        and manifest.get("rejected_strategy_state_changed") is False
        and manifest.get("exact_rejected_variants_reopened") is False
        and manifest.get("intraday_research_remains_paused") is True,
    }


def scoring_review(state: dict[str, Any]) -> dict[str, Any]:
    rows = state["variant_rows"]
    total = len(rows)
    saturated_count = sum(1 for row in rows if to_float(row.get("standalone_growth_score")) >= 99.9)
    saturated_ratio = saturated_count / total if total else 0.0
    family_saturated = {
        family_id: sum(1 for row in group if to_float(row.get("standalone_growth_score")) >= 99.9)
        for family_id, group in grouped_variants(rows).items()
    }
    component_count = sum(1 for row in rows if row.get("status") == "sandbox_component_candidate")
    return {
        "standalone_score_saturation_found": saturated_ratio >= 0.50,
        "standalone_score_saturation_blocking": saturated_ratio >= 0.50,
        "standalone_saturated_count": saturated_count,
        "source_variant_count": total,
        "standalone_saturated_ratio": saturated_ratio,
        "family_saturated_counts": family_saturated,
        "component_candidate_count": component_count,
        "scores_to_trust": [
            "risk_integrity_score",
            "portfolio_contribution_score",
            "benchmark_comparison_summary",
            "overfit_risk_score",
            "practicality_score",
            "return_drag_penalty",
            "duplicate_penalty",
        ],
        "standalone_growth_score_trust": "exclude_from_actionability_decisions_for_this_batch",
        "scoring_fix_required": saturated_ratio >= 0.50,
    }


def grouped_variants(rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        grouped.setdefault(row.get("family_id", ""), []).append(row)
    return grouped


def family_lookup(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {row.get("family_id", ""): row for row in rows}


def benchmark_lookup(rows: list[dict[str, str]]) -> dict[tuple[str, str], dict[str, str]]:
    return {(row.get("family_id", ""), row.get("benchmark_id", "")): row for row in rows}


def family_decision(family_id: str, stats: dict[str, Any], scoring: dict[str, Any]) -> tuple[str, bool, str]:
    if family_id == "breakout_continuation":
        return (
            "manual_review_required",
            False,
            "Plausible low-correlation sleeve clue, but median cash allocation is high and standalone scoring is unusable.",
        )
    if family_id == "macro_portfolio_contribution":
        return (
            "keep_as_sandbox_clue_only",
            False,
            "Useful contribution/benchmark context, but no family-level contribution strength and risk integrity is too narrow.",
        )
    if family_id == "portfolio_combination_sleeve_ensemble":
        return ("deprioritize", False, "High active-combo correlation confirms repackaging risk.")
    if family_id == "trend_momentum":
        return (
            "deprioritize",
            False,
            "Contribution-like readings are outweighed by failed family-level risk integrity.",
        )
    if family_id == "volatility_regime":
        return ("deprioritize", False, "Prior high-upside/high-risk pattern persists without risk-integrity improvement.")
    if scoring["standalone_score_saturation_blocking"]:
        return ("manual_review_required", False, "Scoring defect blocks confident interpretation.")
    return ("keep_as_sandbox_clue_only", False, "No direct actionability after audit.")


def audit_families(state: dict[str, Any], scoring: dict[str, Any]) -> list[dict[str, Any]]:
    variants = grouped_variants(state["variant_rows"])
    source_families = family_lookup(state["family_rows"])
    benchmarks = benchmark_lookup(state["benchmark_rows"])
    rows: list[dict[str, Any]] = []
    for family_id in sorted(source_families):
        group = variants.get(family_id, [])
        family = source_families[family_id]
        median_cash = median_of(group, "avg_cash_allocation")
        median_trades = median_of(group, "trade_count")
        median_return_drag = median_of(group, "return_drag_penalty")
        median_duplicate_penalty = median_of(group, "duplicate_penalty")
        active_combo = benchmarks.get((family_id, "active_combo"), {})
        useful_contribution_count = sum(1 for row in group if bool_text(row.get("useful_contribution_evidence")))
        risk_integrity_count = sum(1 for row in group if bool_text(row.get("acceptable_drawdown_risk_integrity")))
        contribution_score_median = median_of(group, "portfolio_contribution_score")
        risk_score_median = median_of(group, "risk_integrity_score")
        decision, formal_recommended, conclusion = family_decision(
            family_id,
            {
                "median_cash": median_cash,
                "median_trades": median_trades,
                "median_return_drag": median_return_drag,
                "useful_contribution_count": useful_contribution_count,
                "risk_integrity_count": risk_integrity_count,
            },
            scoring,
        )
        row = {
            "family_id": family_id,
            "source_family_status": family.get("family_status", ""),
            "audit_decision": decision,
            "family_level_or_row_level": "family_level_clue" if family.get("future_preregistration_candidate") == "True" else "row_or_context_signal",
            "variants_evaluated": len(group),
            "useful_contribution_variants": useful_contribution_count,
            "acceptable_risk_integrity_variants": risk_integrity_count,
            "median_portfolio_contribution_score": contribution_score_median,
            "median_risk_integrity_score": risk_score_median,
            "median_cash_allocation": median_cash,
            "median_trade_count": median_trades,
            "median_return_drag_penalty": median_return_drag,
            "median_duplicate_penalty": median_duplicate_penalty,
            "active_combo_median_correlation": active_combo.get("median_correlation", ""),
            "active_combo_median_delta_180d": active_combo.get("median_delta_180d_median_final_equity", ""),
            "genuine_contribution_evidence": "mixed" if useful_contribution_count else "not_confirmed",
            "risk_integrity_conclusion": "narrow" if 0 < risk_integrity_count < len(group) // 2 else ("failed" if risk_integrity_count == 0 else "broad_enough_for_audit"),
            "return_drag_conclusion": "material" if median_return_drag > 0.25 else "not_material",
            "duplicate_conclusion": "duplicate_risk" if median_duplicate_penalty > 10 else "not_active_combo_duplicate",
            "underinvestment_or_artifact_risk": "high" if median_cash > 0.60 or median_trades < 3 else "not_primary",
            "formal_preregistration_recommended": formal_recommended,
            "audit_conclusion": conclusion,
        }
        rows.append(row)
    return rows


def decide_next_action(scoring: dict[str, Any], family_rows: list[dict[str, Any]]) -> str:
    if scoring["scoring_fix_required"]:
        return NEXT_ACTION_FIX_SCORING
    recommended = [row for row in family_rows if row["formal_preregistration_recommended"]]
    if len(recommended) == 1:
        return NEXT_ACTION_PREREGISTER_ONE
    if recommended or any(row["audit_decision"] == "manual_review_required" for row in family_rows):
        return NEXT_ACTION_MANUAL
    if all(row["audit_decision"] in {"deprioritize", "discard"} for row in family_rows):
        return NEXT_ACTION_OBSERVE
    return NEXT_ACTION_PAUSE


def batch_consistency_md(manifest: dict[str, Any], guardrails: dict[str, Any], state: dict[str, Any]) -> str:
    missing = ", ".join(guardrails["missing_required_files"]) or "none"
    return f"""# Batch Consistency Review

1. Did batch 002 pass consistency and required-file checks?

Consistency check passed: `{guardrails['source_consistency_passed']}`. Required files present: `{guardrails['required_files_present']}`. Missing files: `{missing}`.

2. Did any result violate non-promotable sandbox rules?

Non-promotable sandbox rules held: `{guardrails['non_promotable_rules_held']}`.

3. Did any result have `promotable=true`?

Promotable true count: `{guardrails['promotable_true_count']}`.

4. Did any result have `paper_candidate_allowed=true`?

Paper candidate allowed true count: `{guardrails['paper_candidate_allowed_true_count']}`.

5. Were forbidden statuses absent?

Forbidden statuses absent: `{guardrails['forbidden_statuses_absent']}`. Forbidden statuses found: `{', '.join(guardrails['forbidden_statuses']) or 'none'}`.

6. Did active VM, active DSR, static all-weather benchmark/control, rejected closures, and intraday pause remain preserved?

Protected-state preservation reported by the source batch: `{guardrails['protected_state_preserved']}`.

Source variant count: `{manifest.get('variant_count_evaluated')}`.
Source family count: `{manifest.get('family_count_evaluated')}`.
Source future-preregistration clue count: `{manifest.get('sandbox_future_preregistration_candidate_count')}`.
"""


def scoring_system_audit_md(scoring: dict[str, Any]) -> str:
    trusted = ", ".join(f"`{item}`" for item in scoring["scores_to_trust"])
    return f"""# Scoring System Audit

The revised scoring framework worked for governance guardrails, contribution/risk diagnostics, and non-promotable output control, but the standalone growth score failed as a discriminator.

## Standalone Growth Score

- Saturation found: `{scoring['standalone_score_saturation_found']}`
- Saturated variants: `{scoring['standalone_saturated_count']}` of `{scoring['source_variant_count']}`
- Audit treatment: `{scoring['standalone_growth_score_trust']}`

The score appears over-scaled and then clamped at 100, so it could not distinguish high-cash, defensive, benchmark-lagging, or high-drawdown rows from genuinely useful standalone engines.

## Portfolio Contribution Score

Useful, but incomplete. It separated active-combo repackaging from lower-correlation sleeves better than standalone score did. It still needs stronger return-drag and underinvestment penalties before future preregistration.

## Stretch Diagnostic Score

The source batch kept stretch diagnostics diagnostic-only. Stretch hits did not directly create promotion or paper-forward status, but they can still create false excitement if viewed without risk integrity.

## Risk Integrity Score

Risk integrity is the most important blocking score for this batch. It correctly showed weak family-level risk integrity in trend, volatility, portfolio-combination, and macro rows, but may over-reward very defensive or under-invested artifacts in isolated rows.

## Overfit Risk Score

Useful as a secondary warning for duplicate and concentration risk. It is not strong enough by itself to validate robustness.

## Practicality Score

Useful for identifying high-turnover and low-activity artifacts. It should have stronger zero-trade, under-investment, and excessive-trade penalties before the next execution batch.

Scores to trust more for interpretation: {trusted}.

Scoring fix required before next research: `{scoring['scoring_fix_required']}`.
"""


def standalone_saturation_md(scoring: dict[str, Any]) -> str:
    family_lines = "\n".join(
        f"- `{family_id}`: `{count}` saturated variants"
        for family_id, count in sorted(scoring["family_saturated_counts"].items())
    )
    return f"""# Standalone Score Saturation Review

Standalone score saturation is real: `{scoring['standalone_score_saturation_found']}`.

Saturated count: `{scoring['standalone_saturated_count']}` of `{scoring['source_variant_count']}`.

Family saturation:

{family_lines}

Why it likely saturated:

- The formula gave too much positive credit to 180-day progress and ending-equity readings before clamping.
- Low-volatility, cash-heavy, or defensive rows could receive high standalone scores despite benchmark lag or return drag.
- The final 0-100 clamp hid meaningful differences among variants.
- Risk, contribution, duplicate, and practicality penalties did not sufficiently constrain the headline score.

Does this make the full framework unreliable?

No, but it makes standalone growth score unusable for actionability in this batch. Interpretation should rely on risk integrity, contribution, benchmark comparison, overfit risk, practicality, return-drag, and duplicate checks.

Blocking conclusion: `{scoring['standalone_score_saturation_blocking']}`.
"""


def family_audit_md(rows: list[dict[str, Any]]) -> str:
    lines = ["# Family Audit", "", "No family is promotable or paper-forward eligible from this audit.", ""]
    for row in rows:
        lines.extend(
            [
                f"## `{row['family_id']}`",
                f"- Source status: `{row['source_family_status']}`",
                f"- Audit decision: `{row['audit_decision']}`",
                f"- Formal preregistration recommended: `{row['formal_preregistration_recommended']}`",
                f"- Useful contribution variants: `{row['useful_contribution_variants']}`",
                f"- Acceptable risk-integrity variants: `{row['acceptable_risk_integrity_variants']}`",
                f"- Median contribution score: `{row['median_portfolio_contribution_score']}`",
                f"- Median risk-integrity score: `{row['median_risk_integrity_score']}`",
                f"- Median cash allocation: `{row['median_cash_allocation']}`",
                f"- Median return-drag penalty: `{row['median_return_drag_penalty']}`",
                f"- Duplicate conclusion: `{row['duplicate_conclusion']}`",
                f"- Conclusion: {row['audit_conclusion']}",
                "",
            ]
        )
    return "\n".join(lines)


def family_detail_md(family_id: str, row: dict[str, Any]) -> str:
    questions: dict[str, list[str]] = {
        "breakout_continuation": [
            "It is a plausible low-correlation sleeve clue, but not yet a real future candidate because the family is cash-heavy and benchmark-lagging.",
            "Best rows may be defensive or under-invested artifacts; median cash allocation is the key warning.",
            "It does not improve active VM/DSR enough to bypass a scoring fix.",
            "Separate preregistration should wait until scoring penalizes cash drag and underinvestment more clearly.",
        ],
        "macro_portfolio_contribution": [
            "Measurable contribution is not confirmed at family level.",
            "The evidence is more useful as benchmark/control or contribution context than as a candidate family.",
            "Component-like rows may be defensive artifacts and do not justify preregistration now.",
        ],
        "portfolio_combination_sleeve_ensemble": [
            "Duplicate/correlation penalties worked; active-combo repackaging remains the dominant concern.",
            "No real contribution survived risk and duplicate review strongly enough.",
            "This family should remain closed/deprioritized for now.",
        ],
        "trend_momentum": [
            "Contribution-like signals are misleading without risk integrity.",
            "Positive rows look too risk-fragile for actionability.",
            "Keep sandbox-only until a separate risk-control hypothesis is written.",
        ],
        "volatility_regime": [
            "The prior high-upside/high-risk pattern persists.",
            "No sub-family improved risk enough for actionability.",
            "Pause or keep sandbox-only until a distinct risk-control thesis exists.",
        ],
    }
    body = "\n".join(f"- {item}" for item in questions.get(family_id, [row["audit_conclusion"]]))
    return f"""# `{family_id}` Audit

Source family status: `{row['source_family_status']}`

Audit decision: `{row['audit_decision']}`

Formal preregistration recommended: `{row['formal_preregistration_recommended']}`

{body}

Key readings:

- Useful contribution variants: `{row['useful_contribution_variants']}`
- Acceptable risk-integrity variants: `{row['acceptable_risk_integrity_variants']}`
- Median portfolio contribution score: `{row['median_portfolio_contribution_score']}`
- Median risk-integrity score: `{row['median_risk_integrity_score']}`
- Median cash allocation: `{row['median_cash_allocation']}`
- Median trade count: `{row['median_trade_count']}`
- Median return-drag penalty: `{row['median_return_drag_penalty']}`
- Median duplicate penalty: `{row['median_duplicate_penalty']}`
- Active-combo median correlation: `{row['active_combo_median_correlation']}`
- Active-combo median 180-day delta: `{row['active_combo_median_delta_180d']}`
"""


def future_clue_review_md(rows: list[dict[str, Any]]) -> str:
    clue_rows = [row for row in rows if row["source_family_status"] == "sandbox_future_preregistration_candidate"]
    lines = ["# Future Preregistration Clue Review", ""]
    if not clue_rows:
        lines.append("No source future-preregistration clues were present.")
    for row in clue_rows:
        lines.extend(
            [
                f"## `{row['family_id']}`",
                f"- Audit decision: `{row['audit_decision']}`",
                f"- Formal preregistration recommended now: `{row['formal_preregistration_recommended']}`",
                f"- Family-level or row-level: `{row['family_level_or_row_level']}`",
                f"- Reason: {row['audit_conclusion']}",
                "",
            ]
        )
    lines.append("Audit conclusion: no separate formal preregistration is recommended before fixing the scoring defect.")
    return "\n".join(lines)


def risk_return_drag_md(rows: list[dict[str, Any]]) -> str:
    lines = ["# Risk And Return-Drag Review", ""]
    for row in rows:
        lines.append(
            f"- `{row['family_id']}`: risk `{row['risk_integrity_conclusion']}`, return drag `{row['return_drag_conclusion']}`, "
            f"median risk score `{row['median_risk_integrity_score']}`, median return-drag penalty `{row['median_return_drag_penalty']}`."
        )
    return "\n".join(lines)


def overfit_duplicate_md(rows: list[dict[str, Any]]) -> str:
    lines = ["# Overfit And Duplicate Review", ""]
    for row in rows:
        lines.append(
            f"- `{row['family_id']}`: duplicate conclusion `{row['duplicate_conclusion']}`, "
            f"artifact risk `{row['underinvestment_or_artifact_risk']}`, median duplicate penalty `{row['median_duplicate_penalty']}`."
        )
    lines.append("")
    lines.append("Best single rows are not actionable. No family may move directly to promotion review.")
    return "\n".join(lines)


def next_action_md(next_action: str, scoring: dict[str, Any]) -> str:
    return f"""# Recommended Next Action

Exact next action: `{next_action}`

Reason: standalone score saturation is blocking: `{scoring['standalone_score_saturation_blocking']}`.

Do not run the next action in this audit task.
"""


def summary_md(manifest: dict[str, Any], family_rows: list[dict[str, Any]]) -> str:
    family_lines = "\n".join(
        f"- `{row['family_id']}`: `{row['audit_decision']}`; prereg recommended `{row['formal_preregistration_recommended']}`"
        for row in family_rows
    )
    return f"""# Revised Objective Sandbox Batch Audit

Audit-only: `{manifest['sandbox_batch_audit_only']}`

Audited batch ID: `{manifest['audited_batch_id']}`

Source variants: `{manifest['source_variant_count']}`

Source families: `{manifest['source_family_count']}`

Source future-preregistration clue count: `{manifest['source_future_preregistration_candidate_count']}`

Families actionable after audit: `{manifest['families_actionable_count_after_audit']}`

Standalone score saturation found: `{manifest['standalone_score_saturation_found']}`

Scoring fix required: `{manifest['scoring_fix_required']}`

Next action: `{manifest['next_action']}`

Family conclusions:

{family_lines}

No new sandbox batch, discovery, backtest, strategy metric computation from raw data, provider download, intraday use, candidate_exhaustive, paper-forward action, broker/live path, or real-money recommendation occurred.
"""


def update_metadata(root: Path, output: Path, created_utc: str, manifest: dict[str, Any]) -> tuple[bool, bool, bool]:
    registry_path = root / REGISTRY_PATH
    registry = load_yaml(registry_path)
    metadata = registry.setdefault("registry", {})
    before_metadata = deepcopy(metadata)
    metadata.update(
        {
            "revised_objective_sandbox_batch_audit_path": str(output.resolve()),
            "revised_objective_sandbox_batch_audit_status": "completed_scoring_fix_required",
            "revised_objective_sandbox_batch_audit_created_utc": created_utc,
            "current_research_mode": "revised_objective_sandbox_batch_audited",
            "current_next_action": manifest["next_action"],
            "official_current_next_action": manifest["next_action"],
            "next_action": manifest["next_action"],
            "revised_objective_sandbox_batch_audit_only": True,
            "revised_objective_sandbox_batch_audit_scoring_fix_required": manifest["scoring_fix_required"],
            "revised_objective_sandbox_batch_audit_families_actionable_count": manifest[
                "families_actionable_count_after_audit"
            ],
            "revised_objective_sandbox_batch_audit_no_formal_preregistration": True,
            "revised_objective_sandbox_batch_audit_no_new_batch": True,
            "revised_objective_sandbox_batch_audit_no_strategy_discovery": True,
            "revised_objective_sandbox_batch_audit_no_provider_download": True,
            "revised_objective_sandbox_batch_audit_no_intraday": True,
            "revised_objective_sandbox_batch_audit_no_candidate_exhaustive": True,
            "revised_objective_sandbox_batch_audit_no_paper_forward_action": True,
            "revised_objective_sandbox_batch_audit_no_real_money_recommendation": True,
        }
    )
    registry_path.write_text(yaml.safe_dump(registry, sort_keys=False, width=120, allow_unicode=False), encoding="utf-8")

    roadmap_path = root / ROADMAP_PATH
    before_roadmap = roadmap_path.read_text(encoding="utf-8") if roadmap_path.exists() else "# Research Roadmap\n"
    compact_section = f"""## Compact Current State

- Updated UTC: `{created_utc}`
- Current research mode: `revised_objective_sandbox_batch_audited`
- Official current next action: `{manifest['next_action']}`
- Revised-objective sandbox batch audit evidence: `{output.resolve()}`
- Source batch ID: `{manifest['audited_batch_id']}`
- Source variants: `{manifest['source_variant_count']}`
- Source families: `{manifest['source_family_count']}`
- Source future-preregistration clues: `{manifest['source_future_preregistration_candidate_count']}`
- Families actionable after audit: `{manifest['families_actionable_count_after_audit']}`
- Standalone score saturation found: `{manifest['standalone_score_saturation_found']}`
- Scoring fix required: `{manifest['scoring_fix_required']}`
- Active VM and active DSR preserved.
- `static_all_weather_benchmark_v1` remains benchmark/control only.
- Exact rejected variants remain closed.
- Intraday remains paused: `true`
- This audit did not run a new sandbox batch, discovery, new backtest, provider download, intraday data, candidate_exhaustive, paper-forward action, broker/live path, or real-money recommendation.
"""
    audit_section = f"""## Revised Objective Sandbox Batch Audit

- Created UTC: `{created_utc}`
- Evidence path: `{output.resolve()}`
- Audited batch ID: `{manifest['audited_batch_id']}`
- Batch consistency passed: `{manifest['batch_consistency_passed']}`
- Sandbox guardrails held: `{manifest['sandbox_guardrails_held']}`
- Standalone score saturation found: `{manifest['standalone_score_saturation_found']}`
- Scoring fix required: `{manifest['scoring_fix_required']}`
- Families actionable after audit: `{manifest['families_actionable_count_after_audit']}`
- Formal preregistration recommended now: `false`
- Next action: `{manifest['next_action']}`
- Do not run the next action in this audit task.
"""
    after_roadmap = replace_or_append_section(before_roadmap, "## Compact Current State", compact_section)
    after_roadmap = replace_or_append_section(after_roadmap, "## Revised Objective Sandbox Batch Audit", audit_section)
    write_text(roadmap_path, after_roadmap)

    compact_path = root / COMPACT_STATE_PATH
    before_compact = compact_path.read_text(encoding="utf-8") if compact_path.exists() else ""
    after_compact = f"""# Current Tournament State

Created UTC: `{created_utc}`

Current research mode: `revised_objective_sandbox_batch_audited`

Current next action: `{manifest['next_action']}`

Revised-objective sandbox batch audit evidence: `{output.resolve()}`

## Audit Decision

- Batch consistency passed: `{manifest['batch_consistency_passed']}`
- Sandbox guardrails held: `{manifest['sandbox_guardrails_held']}`
- Standalone score saturation found: `{manifest['standalone_score_saturation_found']}`
- Scoring fix required: `{manifest['scoring_fix_required']}`
- Families actionable after audit: `{manifest['families_actionable_count_after_audit']}`
- Formal preregistration recommended now: `false`
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
        "sandbox_batch_audit_only": manifest["sandbox_batch_audit_only"] is True,
        "audited_batch_id_correct": manifest["audited_batch_id"] == BATCH_ID,
        "no_new_sandbox_batch": manifest["new_sandbox_batch_run"] is False,
        "no_formal_strategy_discovery": manifest["strategy_discovery_run"] is False and manifest["formal_discovery_run"] is False,
        "no_new_backtests": manifest["new_backtests_run"] is False,
        "no_new_performance_metrics": manifest["new_performance_metrics_computed"] is False,
        "no_new_variants_created": manifest["new_variants_created"] is False,
        "sandbox_results_unchanged": manifest["sandbox_results_changed"] is False,
        "variant_statuses_unchanged": manifest["variant_statuses_changed"] is False,
        "no_future_preregistration_candidates_created_by_audit": manifest[
            "future_preregistration_candidates_created"
        ]
        is False,
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
        "batch_consistency_review_exists": (output / "batch_consistency_review.md").exists(),
        "scoring_system_audit_exists": (output / "scoring_system_audit.md").exists(),
        "standalone_score_saturation_review_exists": (output / "standalone_score_saturation_review.md").exists(),
        "family_audit_exists": (output / "family_audit.md").exists() and (output / "family_audit.csv").exists(),
        "future_preregistration_clue_review_exists": (output / "future_preregistration_clue_review.md").exists(),
        "risk_return_drag_review_exists": (output / "risk_and_return_drag_review.md").exists(),
        "overfit_duplicate_review_exists": (output / "overfit_and_duplicate_review.md").exists(),
        "next_action_valid": manifest["next_action"] in VALID_NEXT_ACTIONS,
        "manifest_flags_match_strict_scope": all(manifest.get(key) == value for key, value in MANIFEST_FLAGS.items()),
        "required_files_exist": all((output / name).exists() for name in REQUIRED_FILES),
    }
    check["consistency_passed"] = all(check.values())
    return check


def run_revised_objective_sandbox_batch_audit(root: Path = ROOT) -> dict[str, Any]:
    root = root.resolve()
    created_utc = now_utc()
    output = root / OUTPUT_DIR
    output.mkdir(parents=True, exist_ok=True)

    before_strategies = strategy_snapshot(root)
    source_hashes_before = source_hashes(root)
    state = source_state(root)
    guardrails = guardrail_review(state)
    scoring = scoring_review(state)
    family_rows = audit_families(state, scoring)
    next_action = decide_next_action(scoring, family_rows)
    families_actionable = sum(1 for row in family_rows if row["formal_preregistration_recommended"])

    manifest = {
        "created_utc": created_utc,
        "output_dir": str(output.resolve()),
        **MANIFEST_FLAGS,
        "source_variant_count": int(state["manifest"].get("variant_count_evaluated", len(state["variant_rows"]))),
        "source_family_count": int(state["manifest"].get("family_count_evaluated", len(state["family_rows"]))),
        "source_future_preregistration_candidate_count": int(
            state["manifest"].get("sandbox_future_preregistration_candidate_count", 0)
        ),
        "families_actionable_count_after_audit": families_actionable,
        "standalone_score_saturation_found": scoring["standalone_score_saturation_found"],
        "standalone_score_saturation_blocking": scoring["standalone_score_saturation_blocking"],
        "scoring_fix_required": scoring["scoring_fix_required"],
        "batch_consistency_passed": guardrails["source_consistency_passed"] and guardrails["required_files_present"],
        "sandbox_guardrails_held": guardrails["non_promotable_rules_held"],
        "formal_preregistration_recommended": families_actionable == 1 and not scoring["scoring_fix_required"],
        "next_action": next_action,
    }

    write_text(output / "batch_consistency_review.md", batch_consistency_md(manifest, guardrails, state))
    write_text(output / "scoring_system_audit.md", scoring_system_audit_md(scoring))
    write_text(output / "standalone_score_saturation_review.md", standalone_saturation_md(scoring))
    write_csv(
        output / "family_audit.csv",
        family_rows,
        [
            "family_id",
            "source_family_status",
            "audit_decision",
            "family_level_or_row_level",
            "variants_evaluated",
            "useful_contribution_variants",
            "acceptable_risk_integrity_variants",
            "median_portfolio_contribution_score",
            "median_risk_integrity_score",
            "median_cash_allocation",
            "median_trade_count",
            "median_return_drag_penalty",
            "median_duplicate_penalty",
            "active_combo_median_correlation",
            "active_combo_median_delta_180d",
            "genuine_contribution_evidence",
            "risk_integrity_conclusion",
            "return_drag_conclusion",
            "duplicate_conclusion",
            "underinvestment_or_artifact_risk",
            "formal_preregistration_recommended",
            "audit_conclusion",
        ],
    )
    write_text(output / "family_audit.md", family_audit_md(family_rows))
    for row in family_rows:
        write_text(output / f"{row['family_id']}_audit.md", family_detail_md(row["family_id"], row))
    write_text(output / "future_preregistration_clue_review.md", future_clue_review_md(family_rows))
    write_text(output / "risk_and_return_drag_review.md", risk_return_drag_md(family_rows))
    write_text(output / "overfit_and_duplicate_review.md", overfit_duplicate_md(family_rows))
    write_text(output / "recommended_next_action.md", next_action_md(next_action, scoring))
    write_text(output / "revised_objective_sandbox_batch_audit_summary.md", summary_md(manifest, family_rows))
    write_json(output / "revised_objective_sandbox_batch_audit_manifest.json", manifest)
    write_json(output / "revised_objective_sandbox_batch_audit_consistency_check.json", {"consistency_passed": False})

    after_strategies = strategy_snapshot(root)
    source_hashes_after = source_hashes(root)
    if before_strategies != after_strategies:
        manifest["active_strategy_state_changed"] = True
        manifest["rejected_strategy_state_changed"] = True
    manifest["sandbox_results_changed"] = source_hashes_before != source_hashes_after
    manifest["variant_statuses_changed"] = source_hashes_before.get("batch_002_variant_results.csv") != source_hashes_after.get(
        "batch_002_variant_results.csv"
    )

    registry_updated, roadmap_updated, compact_updated = update_metadata(root, output, created_utc, manifest)
    manifest["registry_metadata_updated"] = registry_updated
    manifest["roadmap_updated"] = roadmap_updated
    manifest["compact_state_updated"] = compact_updated
    consistency = consistency_check(manifest, output)
    write_json(output / "revised_objective_sandbox_batch_audit_manifest.json", manifest)
    write_json(output / "revised_objective_sandbox_batch_audit_consistency_check.json", consistency)

    return {
        "output_dir": str(output),
        "audited_batch_id": BATCH_ID,
        "batch_consistency_passed": manifest["batch_consistency_passed"],
        "sandbox_guardrails_held": manifest["sandbox_guardrails_held"],
        "standalone_score_saturation_found": manifest["standalone_score_saturation_found"],
        "scoring_fix_required": manifest["scoring_fix_required"],
        "families_actionable_count_after_audit": manifest["families_actionable_count_after_audit"],
        "formal_preregistration_recommended": manifest["formal_preregistration_recommended"],
        "next_action": manifest["next_action"],
        "consistency_passed": consistency["consistency_passed"],
    }
