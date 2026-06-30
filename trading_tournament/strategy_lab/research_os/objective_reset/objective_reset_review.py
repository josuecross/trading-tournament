from __future__ import annotations

import csv
import hashlib
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from strategy_lab.research_os.exploratory_sandbox.sandbox_batch_audit import OUTPUT_DIR as BATCH_AUDIT_DIR
from strategy_lab.research_os.exploratory_sandbox.sandbox_config import REGISTRY_PATH, ROADMAP_PATH, ROOT
from strategy_lab.research_os.exploratory_sandbox.sandbox_manual_review import (
    BATCH_DIR,
    OUTPUT_DIR as MANUAL_REVIEW_DIR,
)


OUTPUT_DIR = Path("evidence") / "objective_reset" / "objective_reset_review" / "latest"
COMPACT_STATE_PATH = Path("reports") / "compact_state" / "current_tournament_state.md"

NEXT_ACTION_OBSERVE = "continue_paper_forward_observation_only"
NEXT_ACTION_REVISED_ETF = "define_revised_etf_wrapper_objective"
NEXT_ACTION_PORTFOLIO_CONTRIBUTION = "pre_register_portfolio_contribution_objective"
NEXT_ACTION_AGGRESSIVE_REVIEW = "manual_review_required_for_aggressive_research_objective"
NEXT_ACTION_PAUSE = "pause_expansion_and_wait_for_manual_direction"
VALID_NEXT_ACTIONS = {
    NEXT_ACTION_OBSERVE,
    NEXT_ACTION_REVISED_ETF,
    NEXT_ACTION_PORTFOLIO_CONTRIBUTION,
    NEXT_ACTION_AGGRESSIVE_REVIEW,
    NEXT_ACTION_PAUSE,
}

RECOMMENDED_OBJECTIVE_PROFILE = "realistic_etf_wrapper_growth_objective"
RECOMMENDED_OBJECTIVE_LABEL = "Profile B: Realistic ETF-wrapper growth objective"

MANIFEST_FLAGS = {
    "objective_review_only": True,
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
}

REQUIRED_FILES = (
    "objective_reset_review_manifest.json",
    "objective_reset_review_summary.md",
    "current_objective_diagnosis.md",
    "constraint_conflict_map.csv",
    "evidence_summary.md",
    "objective_profiles_review.md",
    "recommended_objective.md",
    "active_observation_policy.md",
    "forbidden_next_steps.md",
    "objective_reset_next_action.md",
    "objective_reset_consistency_check.json",
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


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}


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


def variant_status_hashes(root: Path) -> dict[str, str]:
    path = root / BATCH_DIR / "sandbox_variant_results.csv"
    return {"sandbox_variant_results.csv": sha256_file(path)} if path.exists() else {}


def audit_hashes(root: Path) -> dict[str, str]:
    audit_dir = root / BATCH_AUDIT_DIR
    names = ["sandbox_family_audit.csv", "sandbox_family_audit.md"]
    return {name: sha256_file(audit_dir / name) for name in names if (audit_dir / name).exists()}


def strategy_snapshot(root: Path) -> list[dict[str, Any]]:
    return deepcopy(load_yaml(root / REGISTRY_PATH).get("strategies", []))


def source_state(root: Path) -> dict[str, Any]:
    return {
        "manual_review": read_json(root / MANUAL_REVIEW_DIR / "manual_review_after_packet_fix_manifest.json"),
        "batch_audit": read_json(root / BATCH_AUDIT_DIR / "sandbox_batch_audit_manifest.json"),
        "batch_manifest": read_json(root / BATCH_DIR / "sandbox_batch_manifest.json"),
        "family_audit": read_csv(root / BATCH_AUDIT_DIR / "sandbox_family_audit.csv"),
    }


def constraint_rows() -> list[dict[str, str]]:
    return [
        {
            "constraint": "small account size",
            "effect_on_success_probability": "Makes ordinary ETF returns too small in dollar terms for the original target.",
            "classification": "revise",
            "review_conclusion": "Keep the account premise, but translate goals into realistic percentage and risk-adjusted objectives.",
        },
        {
            "constraint": "high dollar profit target",
            "effect_on_success_probability": "Creates the strongest conflict with strict drawdown limits, no leverage, and daily ETF wrappers.",
            "classification": "revise",
            "review_conclusion": "$300-$400 checkpoints should become diagnostic stretch markers, not pass/fail promotion gates.",
        },
        {
            "constraint": "strict drawdown budget",
            "effect_on_success_probability": "Correctly blocks fragile high-upside rows, but should be mapped to objective lane rather than relaxed after results.",
            "classification": "keep",
            "review_conclusion": "Keep hard drawdown discipline; define lane-specific evaluation before any future run.",
        },
        {
            "constraint": "daily ETF-only universe",
            "effect_on_success_probability": "Improves governance and implementation realism but limits short-horizon return capacity.",
            "classification": "keep",
            "review_conclusion": "Keep for the revised ETF-wrapper objective; non-ETF or shorter-horizon work needs separate approval.",
        },
        {
            "constraint": "no leverage",
            "effect_on_success_probability": "Materially caps upside, which is appropriate for promotable or paper-forward governance.",
            "classification": "relax_only_for_research",
            "review_conclusion": "Leverage sensitivity may be discussed only in a separate non-promotable diagnostic review; no current authorization.",
        },
        {
            "constraint": "no shorting",
            "effect_on_success_probability": "Reduces available hedging and relative-value designs, but avoids borrow/execution complexity.",
            "classification": "do_not_relax",
            "review_conclusion": "Do not relax under the current project class.",
        },
        {
            "constraint": "no derivatives",
            "effect_on_success_probability": "Limits convexity and downside hedging but protects against model and execution false confidence.",
            "classification": "do_not_relax",
            "review_conclusion": "Options and futures require a separate major governance decision and remain outside this objective.",
        },
        {
            "constraint": "no intraday",
            "effect_on_success_probability": "Blocks the likely natural horizon for mean-reversion and some breakout refinements.",
            "classification": "manual_decision_required",
            "review_conclusion": "Keep paused until data-source, slippage, and quality governance are explicitly approved.",
        },
        {
            "constraint": "no provider download",
            "effect_on_success_probability": "Keeps the review reproducible but blocks expanded data diagnostics.",
            "classification": "manual_decision_required",
            "review_conclusion": "Do not download data in this review; future data expansion needs explicit approval.",
        },
        {
            "constraint": "no individual stocks",
            "effect_on_success_probability": "Limits breadth and alpha search space but avoids survivorship and delisting bias.",
            "classification": "manual_decision_required",
            "review_conclusion": "Remain blocked unless survivorship-free data, delisting treatment, and governance are solved.",
        },
        {
            "constraint": "no overfit parameter selection",
            "effect_on_success_probability": "Reduces apparent opportunity count but protects against repeated-search false confidence.",
            "classification": "do_not_relax",
            "review_conclusion": "Do not relax; all future objectives need preregistered gates and no tuning after results.",
        },
        {
            "constraint": "same-window benchmark pressure",
            "effect_on_success_probability": "Can reject useful defensive or diversifying sleeves when judged only as standalone return engines.",
            "classification": "revise",
            "review_conclusion": "Retain benchmark transparency, but separate standalone growth and portfolio-contribution success criteria.",
        },
        {
            "constraint": "active combo benchmark pressure",
            "effect_on_success_probability": "Appropriately blocks duplicates, but can over-penalize low-correlation sleeves with modest standalone returns.",
            "classification": "revise",
            "review_conclusion": "Keep duplicate checks; add contribution-aware criteria only after a revised objective is defined.",
        },
    ]


def current_objective_diagnosis_md() -> str:
    return """# Current Objective Diagnosis

1. Is the current objective internally realistic?

No, not as a general strategy-discovery target under the current constraints. A small $3,000 account seeking roughly $300-$400 over monthly or short-to-mid horizons asks daily ETF wrappers to deliver unusually high dollar returns while also obeying strict drawdown, no leverage, no shorting, no derivatives, no intraday data, and no parameter fishing.

2. Which constraint is the main blocker?

The main blocker is the combined objective/risk/universe mismatch. The high dollar target is the sharpest conflict, but it becomes binding because the universe and risk controls deliberately remove the usual ways to seek higher upside.

3. Should the project remain ETF-only and daily-data-only?

Yes for the next standard objective. ETF-only and daily-data-only constraints should remain the default governance lane. Any intraday, individual-stock, derivatives, leverage, or new-provider path requires separate manual approval before research.

4. Should the return target be lowered?

Yes. The original $300-$400 checkpoint should be treated as diagnostic context, not the primary pass/fail target. The revised objective should focus on realistic risk-adjusted growth, drawdown containment, repeatable paper/demo tracking, and clearly defined portfolio contribution.

5. Should drawdown/risk gates be changed, kept, or made lane-specific?

Keep the core drawdown/risk discipline. Make the interpretation lane-specific before any future run: standalone growth rows must meet standalone risk gates, while future contribution sleeves must be evaluated by preregistered portfolio-level improvement and duplicate checks. Do not loosen gates after seeing results.

6. Should leverage be considered only as research-only sensitivity, or remain fully forbidden?

Leverage remains fully forbidden for candidates, paper-forward activation, or any actionable recommendation. A leverage sensitivity study could only exist later as a separate non-promotable diagnostic after manual approval; it is not authorized by this review.

7. Should the project shift from profit-first to portfolio-contribution-first?

Not as the immediate next step. The first move should define a revised ETF-wrapper objective that explicitly separates standalone growth from portfolio-contribution criteria. Portfolio contribution is promising, but it should not be launched before the objective language and gates are reset.
"""


def evidence_summary_md(state: dict[str, Any]) -> str:
    manual = state["manual_review"]
    batch = state["batch_manifest"]
    audit = state["batch_audit"]
    lines = [
        "# Evidence Summary",
        "",
        "- Manual review next action entering this step: `" + str(manual.get("next_action")) + "`",
        "- Packet fix accepted: `" + str(manual.get("packet_fix_accepted")) + "`",
        "- Batch 001 accepted as non-promotable exploration: `"
        + str(manual.get("batch_001_accepted_as_non_promotable_exploration"))
        + "`",
        "- Planned/evaluated sandbox variants: `"
        + str(batch.get("variant_count_planned"))
        + "` / `"
        + str(batch.get("variant_count_evaluated"))
        + "`",
        "- Families evaluated: `" + str(batch.get("families_evaluated_count")) + "`",
        "- Actionable families: `" + str(audit.get("families_actionable_count")) + "`",
        "- Future preregistration candidates: `" + str(manual.get("future_preregistration_candidate_count")) + "`",
        "",
        "What is working:",
        "",
        "- Governance gates are catching overfit and risk-buffer failures.",
        "- Active VM and active DSR remain protected as the only supported active/frozen observations.",
        "- The sandbox produced useful negative evidence without creating false candidates.",
        "- Indicator-library availability is not the central bottleneck.",
        "",
        "What is not working:",
        "",
        "- Higher-upside families repeatedly fail drawdown or risk-buffer screens.",
        "- Safer or low-correlation rows tend to lag active references as standalone return engines.",
        "- Portfolio combinations risk duplicating active combo behavior.",
        "- Daily ETF mean-reversion likely lacks the horizon and data needed to be credible.",
        "",
        "Wrong assumptions corrected by the evidence:",
        "",
        "- More families alone will not solve an objective mismatch.",
        "- The best sandbox row or family is not automatically useful.",
        "- Low correlation is not enough if objective progress is too weak.",
        "- Active-combo outperformance alone is not enough if drawdown fails.",
    ]
    return "\n".join(lines)


def objective_profiles_review_md() -> str:
    return """# Objective Profiles Review

## Profile A: Conservative Observation-Only

This is the safest operational posture. It preserves active VM and active DSR, avoids new research churn, and lets the project collect clean paper/demo observations. Its weakness is that it does not resolve the objective mismatch or define what future ETF-wrapper research should optimize.

Likely next action if selected: `continue_paper_forward_observation_only`

## Profile B: Realistic ETF-Wrapper Growth Objective

This is the recommended profile. It keeps daily ETF-wrapper governance but lowers and clarifies the target. The project should define success around realistic 180-day and monthly diagnostic bands, risk-adjusted progress, drawdown containment, duplicate avoidance, and whether +$300/+400 checkpoints are stretch diagnostics rather than promotion gates.

Likely next action if selected: `define_revised_etf_wrapper_objective`

## Profile C: Portfolio-Contribution Objective

This is promising but premature as the immediate next action. It would stop requiring every sleeve to beat active combo standalone and instead require preregistered portfolio-level return/risk contribution, correlation reduction, drawdown behavior, and acceptable return drag. It should be designed after the revised ETF objective clarifies the scoring language.

Likely next action if selected: `pre_register_portfolio_contribution_objective`

## Profile D: Aggressive Research-Only Objective

This would pursue higher upside by changing major constraints, such as leverage sensitivity, wider universes, individual stocks, intraday data, options, or futures. It is not safe to authorize here. Every such path requires a separate manual governance decision and better data/execution infrastructure.

Likely next action if selected: `manual_review_required_for_aggressive_research_objective`

## Profile E: Stop/Pause Expansion

This is defensible if the human decision is to stop spending research cycles until new capital, data, objective, or hypotheses appear. It is safer than random search, but it leaves the objective mismatch unresolved.

Likely next action if selected: `pause_expansion_and_wait_for_manual_direction`
"""


def recommended_objective_md(next_action: str) -> str:
    return f"""# Recommended Objective

Recommended objective profile: `{RECOMMENDED_OBJECTIVE_PROFILE}`

Recommended label: `{RECOMMENDED_OBJECTIVE_LABEL}`

The project should keep ETF-only, daily-data-only, no-short, no-derivatives, no-intraday, and anti-overfit constraints for the standard lane, but revise the target away from short-horizon high-dollar profit as the primary success measure.

Revised objective direction:

- Treat $300-$400 checkpoints as diagnostic stretch markers, not promotion gates.
- Define realistic 180-day and monthly expectations before any future research run.
- Use risk-adjusted progress, drawdown containment, duplicate avoidance, and portfolio contribution as explicit evaluation dimensions.
- Keep active VM and active DSR as the only supported active/frozen observations.
- Require separate manual approval before any aggressive research-only constraint relaxation.

Exact next action: `{next_action}`

Do not run the next action in this objective-reset review.
"""


def active_observation_policy_md() -> str:
    return """# Active Observation Policy

8. Should active VM and active DSR remain the only active/frozen observations?

Yes.

- `paper_forward_vm_quality_lowvol_proxy_v1` remains active/frozen.
- `paper_forward_dsr_sector_equal_weight_defensive_filter_v1` remains active/frozen.
- `static_all_weather_benchmark_v1` remains benchmark/control only.
- No new active strategy is created by this review.
- No new paper-forward candidate is created by this review.
- No paper-forward review or activation is authorized.
- No broker/live/real-money action is authorized.
"""


def forbidden_next_steps_md() -> str:
    return """# Forbidden Next Steps

Explicitly forbidden next:

- sandbox batch 002 directly without a new objective
- strategy discovery
- backtests
- candidate_exhaustive
- paper-forward review or activation
- provider downloads
- intraday research
- broker/live paths
- real-money recommendations
- promoting best sandbox row
- promoting best sandbox family
- loosening gates after results
- adding variants to rescue weak families
- creating paper-forward candidates from sandbox outputs
"""


def next_action_md(next_action: str) -> str:
    return f"""# Objective Reset Next Action

9. Should future work be observation-only, new sandbox design, or objective-reset diagnostics?

Future work should first define a revised ETF-wrapper objective. Observation continues for active VM and active DSR, but new sandbox design is not authorized until the revised objective and gates are written.

10. What is the safest exact next action?

`{next_action}`

Do not run the next action in this objective-reset review.
"""


def summary_md(manifest: dict[str, Any]) -> str:
    return f"""# Objective Reset Review

Objective-review-only: `{manifest['objective_review_only']}`

Current objective internally realistic: `{manifest['current_objective_internally_realistic']}`

Main blocker: `{manifest['main_blocker']}`

Recommended objective profile: `{manifest['recommended_objective_profile']}`

Active VM/DSR observation recommended: `{manifest['active_vm_dsr_observation_recommended']}`

Batch 002 directly authorized: `{manifest['batch_002_directly_authorized']}`

Next action: `{manifest['next_action']}`

No sandbox batch, discovery, backtest, new performance metric, provider download, intraday data, candidate_exhaustive, paper-forward action, broker/live path, or real-money recommendation occurred.
"""


def replace_or_append_section(text: str, header: str, section: str) -> str:
    if header not in text:
        return text.rstrip() + "\n\n" + section.rstrip() + "\n"
    start = text.index(header)
    next_start = text.find("\n## ", start + len(header))
    if next_start == -1:
        return text[:start].rstrip() + "\n\n" + section.rstrip() + "\n"
    return text[:start].rstrip() + "\n\n" + section.rstrip() + "\n\n" + text[next_start + 1 :].lstrip()


def update_metadata(root: Path, output: Path, created_utc: str, manifest: dict[str, Any]) -> tuple[bool, bool, bool]:
    registry_path = root / REGISTRY_PATH
    registry = load_yaml(registry_path)
    metadata = registry.setdefault("registry", {})
    before_metadata = deepcopy(metadata)
    metadata.update(
        {
            "objective_reset_review_path": str(output.resolve()),
            "objective_reset_review_status": "completed_revised_etf_wrapper_objective_recommended",
            "objective_reset_review_created_utc": created_utc,
            "current_research_mode": "objective_reset_review_completed",
            "current_next_action": manifest["next_action"],
            "official_current_next_action": manifest["next_action"],
            "next_action": manifest["next_action"],
            "objective_review_only": True,
            "objective_reset_recommended_objective_profile": manifest["recommended_objective_profile"],
            "objective_reset_active_vm_dsr_observation_recommended": manifest["active_vm_dsr_observation_recommended"],
            "objective_reset_batch_002_directly_authorized": manifest["batch_002_directly_authorized"],
            "objective_reset_no_new_sandbox_batch_run": True,
            "objective_reset_no_strategy_discovery": True,
            "objective_reset_no_backtests": True,
            "objective_reset_no_provider_download": True,
            "objective_reset_no_intraday_data": True,
            "objective_reset_no_candidate_exhaustive": True,
            "objective_reset_no_paper_forward_action": True,
            "objective_reset_no_real_money_recommendation": True,
        }
    )
    registry_path.write_text(yaml.safe_dump(registry, sort_keys=False, width=120, allow_unicode=False), encoding="utf-8")

    roadmap_path = root / ROADMAP_PATH
    before_roadmap = roadmap_path.read_text(encoding="utf-8") if roadmap_path.exists() else "# Research Roadmap\n"
    compact_section = f"""## Compact Current State

- Updated UTC: `{created_utc}`
- Current research mode: `objective_reset_review_completed`
- Official current next action: `{manifest['next_action']}`
- Objective reset evidence: `{output.resolve()}`
- Recommended objective profile: `{manifest['recommended_objective_profile']}`
- Current objective internally realistic: `{manifest['current_objective_internally_realistic']}`
- Main blocker: `{manifest['main_blocker']}`
- Batch 002 directly authorized: `{manifest['batch_002_directly_authorized']}`
- Active VM and active DSR remain the only supported active/frozen observations.
- `static_all_weather_benchmark_v1` remains benchmark/control only.
- Exact rejected variants remain closed.
- Intraday remains paused: `true`
- This objective review did not run a new sandbox batch, discovery, backtest, new metric, provider download, intraday data, candidate_exhaustive, paper-forward action, broker/live path, or real-money recommendation.
"""
    review_section = f"""## Objective Reset Review

- Created UTC: `{created_utc}`
- Evidence path: `{output.resolve()}`
- Current objective diagnosis: original high-dollar short-horizon target is not internally realistic under current ETF-only, daily-data, no-leverage, strict-risk constraints.
- Recommended objective profile: `{manifest['recommended_objective_profile']}`
- Batch 002 directly authorized: `{manifest['batch_002_directly_authorized']}`
- Active VM/DSR observation recommended: `{manifest['active_vm_dsr_observation_recommended']}`
- Next action: `{manifest['next_action']}`
- Do not run the next action in this objective-reset review.
"""
    after_roadmap = replace_or_append_section(before_roadmap, "## Compact Current State", compact_section)
    after_roadmap = replace_or_append_section(after_roadmap, "## Objective Reset Review", review_section)
    write_text(roadmap_path, after_roadmap)

    compact_path = root / COMPACT_STATE_PATH
    before_compact = compact_path.read_text(encoding="utf-8") if compact_path.exists() else ""
    after_compact = f"""# Current Tournament State

Created UTC: `{created_utc}`

Current research mode: `objective_reset_review_completed`

Current next action: `{manifest['next_action']}`

Objective reset evidence: `{output.resolve()}`

## Decision

- Current objective internally realistic: `{manifest['current_objective_internally_realistic']}`
- Main blocker: `{manifest['main_blocker']}`
- Recommended objective profile: `{manifest['recommended_objective_profile']}`
- Batch 002 directly authorized: `{manifest['batch_002_directly_authorized']}`
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
    return before_metadata != metadata, before_roadmap != after_roadmap, before_compact != after_compact


def consistency_check(manifest: dict[str, Any], output: Path) -> dict[str, Any]:
    check = {
        "objective_review_only": manifest["objective_review_only"] is True,
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
        "objective_diagnosis_exists": (output / "current_objective_diagnosis.md").exists(),
        "constraint_conflict_map_exists": (output / "constraint_conflict_map.csv").exists(),
        "objective_profiles_review_exists": (output / "objective_profiles_review.md").exists(),
        "recommended_objective_exists": (output / "recommended_objective.md").exists(),
        "active_observation_policy_exists": (output / "active_observation_policy.md").exists(),
        "forbidden_next_steps_exists": (output / "forbidden_next_steps.md").exists(),
        "next_action_valid": manifest["next_action"] in VALID_NEXT_ACTIONS,
        "manifest_flags_match_strict_scope": all(manifest.get(key) == value for key, value in MANIFEST_FLAGS.items()),
        "required_files_exist": all((output / name).exists() for name in REQUIRED_FILES),
    }
    check["consistency_passed"] = all(check.values())
    return check


def run_objective_reset_review(root: Path = ROOT) -> dict[str, Any]:
    root = root.resolve()
    created_utc = now_utc()
    output = root / OUTPUT_DIR
    output.mkdir(parents=True, exist_ok=True)

    before_strategies = strategy_snapshot(root)
    batch_hashes_before = batch_result_hashes(root)
    variant_hashes_before = variant_status_hashes(root)
    audit_hashes_before = audit_hashes(root)
    state = source_state(root)
    next_action = NEXT_ACTION_REVISED_ETF

    manifest = {
        "created_utc": created_utc,
        "output_dir": str(output.resolve()),
        **MANIFEST_FLAGS,
        "current_objective_internally_realistic": False,
        "main_blocker": "objective_risk_universe_mismatch",
        "recommended_objective_profile": RECOMMENDED_OBJECTIVE_PROFILE,
        "recommended_objective_label": RECOMMENDED_OBJECTIVE_LABEL,
        "active_vm_dsr_observation_recommended": True,
        "batch_002_directly_authorized": False,
        "next_action": next_action,
    }

    write_json(output / "objective_reset_review_manifest.json", manifest)
    write_text(output / "current_objective_diagnosis.md", current_objective_diagnosis_md())
    write_csv(
        output / "constraint_conflict_map.csv",
        constraint_rows(),
        ["constraint", "effect_on_success_probability", "classification", "review_conclusion"],
    )
    write_text(output / "evidence_summary.md", evidence_summary_md(state))
    write_text(output / "objective_profiles_review.md", objective_profiles_review_md())
    write_text(output / "recommended_objective.md", recommended_objective_md(next_action))
    write_text(output / "active_observation_policy.md", active_observation_policy_md())
    write_text(output / "forbidden_next_steps.md", forbidden_next_steps_md())
    write_text(output / "objective_reset_next_action.md", next_action_md(next_action))
    write_text(output / "objective_reset_review_summary.md", summary_md(manifest))
    write_json(output / "objective_reset_consistency_check.json", {"consistency_passed": False})

    batch_hashes_after = batch_result_hashes(root)
    variant_hashes_after = variant_status_hashes(root)
    audit_hashes_after = audit_hashes(root)
    after_strategies = strategy_snapshot(root)
    manifest["sandbox_results_changed"] = batch_hashes_before != batch_hashes_after
    manifest["variant_statuses_changed"] = variant_hashes_before != variant_hashes_after
    manifest["family_audit_changed"] = audit_hashes_before != audit_hashes_after
    if before_strategies != after_strategies:
        manifest["active_strategy_state_changed"] = True
        manifest["rejected_strategy_state_changed"] = True

    registry_updated, roadmap_updated, compact_updated = update_metadata(root, output, created_utc, manifest)
    manifest["registry_metadata_updated"] = registry_updated
    manifest["roadmap_updated"] = roadmap_updated
    manifest["compact_state_updated"] = compact_updated
    consistency = consistency_check(manifest, output)
    write_json(output / "objective_reset_review_manifest.json", manifest)
    write_json(output / "objective_reset_consistency_check.json", consistency)

    return {
        "output_dir": str(output),
        "current_objective_internally_realistic": manifest["current_objective_internally_realistic"],
        "main_blocker": manifest["main_blocker"],
        "recommended_objective_profile": manifest["recommended_objective_profile"],
        "active_vm_dsr_observation_recommended": manifest["active_vm_dsr_observation_recommended"],
        "batch_002_directly_authorized": manifest["batch_002_directly_authorized"],
        "next_action": manifest["next_action"],
        "consistency_passed": consistency["consistency_passed"],
    }
