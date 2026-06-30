from __future__ import annotations

import csv
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import REGISTRY_PATH, ROADMAP_PATH, ROOT
from strategy_lab.research_os.objective_reset.objective_reset_review import (
    BATCH_AUDIT_DIR,
    BATCH_DIR,
    COMPACT_STATE_PATH,
    audit_hashes,
    batch_result_hashes,
    load_yaml,
    replace_or_append_section,
    strategy_snapshot,
    variant_status_hashes,
    write_json,
    write_text,
)
from strategy_lab.research_os.objective_reset.revised_etf_wrapper_objective import (
    OUTPUT_DIR as REVISED_OBJECTIVE_DIR,
    REVISED_OBJECTIVE_PROFILE,
)


OUTPUT_DIR = Path("evidence") / "objective_reset" / "revised_objective_sandbox_preregistration" / "latest"

PLANNED_BATCH_ID = "batch_002_revised_objective"
PLANNED_MAX_VARIANTS = 100
PLANNED_FAMILY_COUNT = 5
MAX_VARIANTS_PER_FAMILY = 20
MAX_PARAMETER_CHOICES_PER_INDICATOR = 4
MAX_PORTFOLIO_COMBINATION_VARIANTS = 30

NEXT_ACTION_IMPLEMENT = "implement_revised_objective_sandbox_batch"
NEXT_ACTION_MANUAL_REVIEW = "manual_review_required_after_revised_objective_sandbox_preregistration"
NEXT_ACTION_OBSERVE = "continue_paper_forward_observation_only"
NEXT_ACTION_PAUSE = "pause_expansion_and_wait_for_manual_direction"
VALID_NEXT_ACTIONS = {
    NEXT_ACTION_IMPLEMENT,
    NEXT_ACTION_MANUAL_REVIEW,
    NEXT_ACTION_OBSERVE,
    NEXT_ACTION_PAUSE,
}

MANIFEST_FLAGS = {
    "sandbox_preregistration_only": True,
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
    "revised_objective_sandbox_preregistration_manifest.json",
    "revised_objective_sandbox_preregistration_summary.md",
    "batch_002_purpose.md",
    "batch_001_lessons_applied.md",
    "revised_batch_family_selection.md",
    "revised_batch_universe_plan.md",
    "revised_batch_indicator_plan.md",
    "revised_batch_variant_limits.md",
    "revised_scoring_framework.md",
    "target_tier_application.md",
    "portfolio_contribution_scoring_plan.md",
    "stretch_diagnostic_policy.md",
    "do_not_run_batch_now.md",
    "revised_objective_sandbox_next_action.md",
    "revised_objective_sandbox_consistency_check.json",
)

OPTIONAL_FILES = ("planned_family_variant_plan.csv",)


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def source_state(root: Path) -> dict[str, Any]:
    return {
        "revised_objective": read_json(root / REVISED_OBJECTIVE_DIR / "revised_etf_objective_manifest.json"),
        "batch_manifest": read_json(root / BATCH_DIR / "sandbox_batch_manifest.json"),
        "batch_audit": read_json(root / BATCH_AUDIT_DIR / "sandbox_batch_audit_manifest.json"),
    }


def planned_family_rows() -> list[dict[str, str]]:
    return [
        {
            "family_id": "breakout_continuation",
            "planned_status": "included_redesigned",
            "objective_lane": "portfolio_contribution_sleeve",
            "planned_variant_cap": "18",
            "research_question": "Can breakout continuation provide low-correlation participation with controlled drawdown and less cash drag?",
            "batch_001_lesson": "Low correlation and gentler drawdown, but weak objective progress.",
        },
        {
            "family_id": "portfolio_combination_sleeve_ensemble",
            "planned_status": "included_redesigned",
            "objective_lane": "portfolio_contribution_sleeve",
            "planned_variant_cap": "18",
            "research_question": "Can simple sleeve combinations improve active VM/DSR portfolio behavior after penalizing active-combo duplication?",
            "batch_001_lesson": "Some interest, but too correlated with active combo.",
        },
        {
            "family_id": "volatility_regime",
            "planned_status": "included_high_risk_diagnostic",
            "objective_lane": "standalone_growth",
            "planned_variant_cap": "16",
            "research_question": "Do volatility-regime variants retain realistic growth after drawdown and risk-buffer penalties?",
            "batch_001_lesson": "High upside but drawdown failures.",
        },
        {
            "family_id": "trend_momentum",
            "planned_status": "included_risk_adjusted_redesign",
            "objective_lane": "standalone_growth",
            "planned_variant_cap": "16",
            "research_question": "Can trend momentum produce positive 180-day progress without relying on high-drawdown rows?",
            "batch_001_lesson": "Some active-combo beats but drawdown failures.",
        },
        {
            "family_id": "macro_portfolio_contribution",
            "planned_status": "included_contribution_context",
            "objective_lane": "portfolio_contribution_sleeve",
            "planned_variant_cap": "12",
            "research_question": "Can macro allocation context improve portfolio contribution diagnostics versus static all-weather control?",
            "batch_001_lesson": "Useful as contribution/benchmark context, weak as standalone.",
        },
        {
            "family_id": "mean_reversion",
            "planned_status": "deprioritized_not_in_batch_002",
            "objective_lane": "excluded",
            "planned_variant_cap": "0",
            "research_question": "No daily ETF mean-reversion research until intraday or shorter-horizon data is separately approved.",
            "batch_001_lesson": "Weak in daily ETF form; likely needs intraday/shorter horizon.",
        },
        {
            "family_id": "factor_style_rotation",
            "planned_status": "deprioritized_not_in_batch_002",
            "objective_lane": "excluded",
            "planned_variant_cap": "0",
            "research_question": "No new style-rotation research without a clear non-duplicate contribution thesis.",
            "batch_001_lesson": "Likely equity-beta heavy.",
        },
    ]


def batch_purpose_md() -> str:
    return f"""# Batch 002 Purpose

Planned batch ID: `{PLANNED_BATCH_ID}`

Purpose: preregister a revised-objective exploratory sandbox batch that maps ETF-wrapper opportunities under the realistic ETF-wrapper growth objective, not the old hard $300-$400 target.

The batch is designed to answer two separate questions:

1. Can any daily ETF/fund-wrapper family show realistic standalone growth with controlled drawdown, stress/slippage tolerance, and non-duplication versus active references?
2. Can any sleeve improve the active VM/DSR portfolio through contribution, drawdown or volatility reduction, lower correlation, or better risk-adjusted behavior without unacceptable return drag?

This is not random search and not batch-001 repetition because:

- families are selected from explicit batch-001 lessons;
- mean reversion and factor style rotation are excluded/deprioritized;
- standalone growth and portfolio contribution are scored separately;
- $300/$400 checkpoints are recorded only as stretch diagnostics;
- high active-combo correlation is penalized rather than treated as contribution;
- every future row remains non-promotable sandbox evidence.

No sandbox batch is run by this preregistration.
"""


def batch_001_lessons_md() -> str:
    return """# Batch 001 Lessons Applied

- `breakout_continuation`: retained only as a possible low-correlation sleeve or drawdown-controlled component. It is not treated as standalone alpha unless realistic objective progress improves.
- `portfolio_combination_sleeve_ensemble`: retained only with stronger contribution diagnostics and an explicit active-combo correlation penalty.
- `volatility_regime`: retained only as a high-upside/high-risk diagnostic. It cannot become actionable without drawdown improvement.
- `trend_momentum`: retained only under improved risk-adjusted scoring. It must not rely on high-drawdown variants.
- `macro_portfolio_contribution`: retained as contribution context unless portfolio-level improvement is measurable.
- `mean_reversion`: excluded/deprioritized because the daily ETF version was weak and likely needs intraday or shorter-horizon data, which remains blocked.
- `factor_style_rotation`: excluded/deprioritized because batch 001 suggested equity-beta duplication risk unless a clear non-duplicate contribution question is defined.

The revised batch tests objective-aligned questions rather than expanding the search because batch 001 found no candidate.
"""


def family_selection_md() -> str:
    lines = [
        "# Revised Batch Family Selection",
        "",
        f"Planned family count: `{PLANNED_FAMILY_COUNT}` included families, with two deprioritized exclusions.",
        "",
        "All planned variants remain `status: non_promotable_exploration`, `promotable: false`, and `paper_candidate_allowed: false`.",
        "",
    ]
    for row in planned_family_rows():
        lines.extend(
            [
                f"## `{row['family_id']}`",
                f"- Planned status: `{row['planned_status']}`",
                f"- Objective lane: `{row['objective_lane']}`",
                f"- Planned variant cap: `{row['planned_variant_cap']}`",
                f"- Research question: {row['research_question']}",
                f"- Batch 001 lesson: {row['batch_001_lesson']}",
                "",
            ]
        )
    return "\n".join(lines)


def universe_plan_md() -> str:
    return """# Revised Batch Universe Plan

Use local approved/cache-present daily ETF/fund-wrapper data only.

Included universe groups, only when cache-present:

- broad equity benchmarks and references: SPY, QQQ
- defensive and cash references: BIL and approved treasury/bond wrappers
- active-reference components needed to compare active VM, active DSR, and active combo behavior
- sector or style ETF wrappers already approved and present in cache
- low-volatility, quality, or defensive ETF wrappers already approved and present in cache
- static all-weather benchmark/control components already approved and present in cache

Excluded universe paths:

- provider downloads
- intraday data
- individual stocks
- crypto
- options, futures, forex, or derivatives
- leveraged or inverse products for the standard lane
- symbols missing from local approved/cache-present data

Data availability audit policy:

- implementation may check local approved symbol maps and cache presence;
- missing symbols must be marked `sandbox_data_blocked`;
- missing symbols must not trigger provider APIs or downloads;
- limited-history rows must be labeled and penalized for overfit risk.
"""


def indicator_plan_md() -> str:
    return """# Revised Batch Indicator Plan

Allowed validated custom indicators:

- SMA
- EMA
- ATR
- RSI
- Bollinger bands
- realized volatility
- ROC / rolling return
- Donchian prior high
- volume SMA / filter alignment
- rolling percentile rank
- moving-average regime
- SPY regime features

Forbidden indicators and methods:

- MACD
- Keltner Channel
- OBV
- external indicator libraries
- candlestick-pattern mining
- AI-generated formulas
- genetic search
- parameter optimization or tuning after results

Parameter choices are limited to at most four per indicator concept and must be fixed before any future implementation run.
"""


def variant_limits_md() -> str:
    return f"""# Revised Batch Variant Limits

- Max total future variants: `{PLANNED_MAX_VARIANTS}`
- Max families: `{PLANNED_FAMILY_COUNT}`
- Max variants per family: `{MAX_VARIANTS_PER_FAMILY}`
- Max parameter choices per indicator concept: `{MAX_PARAMETER_CHOICES_PER_INDICATOR}`
- Max portfolio-combination variants: `{MAX_PORTFOLIO_COMBINATION_VARIANTS}`

All future variants must remain:

- `promotable: false`
- `paper_candidate_allowed: false`
- `status: non_promotable_exploration`

No best row, best family, or stretch-diagnostic hit can become a promotion candidate directly.
"""


def scoring_framework_md() -> str:
    return """# Revised Scoring Framework

The revised batch must emit separate scoring dimensions instead of one old hard-dollar gate.

## `standalone_growth_score`

- realistic 180-day progress
- risk-adjusted growth
- benchmark relevance
- drawdown control
- active-reference comparison

## `portfolio_contribution_score`

- active VM/DSR portfolio improvement
- active combo improvement
- correlation reduction
- drawdown/volatility contribution
- return drag penalty
- contribution versus static all-weather control

## `stretch_diagnostic_score`

- $300 hit rate
- $400 hit rate
- active-combo beat rate
- portfolio-level risk-adjusted improvement

This score is diagnostic only and never a direct promotion gate.

## `risk_integrity_score`

- drawdown
- risk buffer
- stress/slippage
- tail concentration

## `overfit_risk_score`

- parameter sensitivity
- single-symbol dependence
- limited history
- family robustness

## `practicality_score`

- turnover
- trade count
- simplicity
- data quality

Future output statuses allowed:

- `sandbox_discard`
- `sandbox_family_weak`
- `sandbox_family_interesting`
- `sandbox_component_candidate`
- `sandbox_portfolio_sleeve_candidate`
- `sandbox_needs_objective_reset`
- `sandbox_data_blocked`
- `sandbox_future_preregistration_candidate`

Forbidden statuses:

- `promotion_review_candidate`
- `candidate_exhaustive`
- `paper_forward`
- `paper_forward_active`
- `demo_active`
- `live_ready`
"""


def target_tier_application_md() -> str:
    return """# Target Tier Application

Core success diagnostics are the main evidence:

- positive 180-day median progress
- controlled max drawdown
- survives slippage/stress review
- not dominated by active references
- not a duplicate of active combo
- stable enough across neighboring parameters or related family concepts
- sufficient data-history quality
- simple enough rules and turnover for paper/demo practicality

Realistic expectation bands:

- monthly diagnostics should look for repeated positive expectancy or contribution rather than guaranteed monthly profit;
- 180-day diagnostics should require median final equity above starting capital and meaningful risk-adjusted progress;
- downside concentration and limited-history risk must remain visible.

Stretch diagnostics:

- $300 and $400 hits are recorded;
- active-combo same-window beats are recorded;
- portfolio-level risk-adjusted improvements are recorded;
- none of these are hard promotion gates.

Failing $300-$400 alone does not invalidate a strategy. Hitting $300-$400 alone does not justify promotion.
"""


def portfolio_contribution_scoring_md() -> str:
    return """# Portfolio Contribution Scoring Plan

Portfolio-contribution sleeves are evaluated against the active VM/DSR portfolio, active combo, and static all-weather control.

Required contribution fields:

- portfolio final-equity impact versus active VM/DSR pair
- portfolio drawdown impact
- portfolio volatility impact
- correlation to active combo
- return drag versus active combo
- risk-adjusted outcome delta
- contribution versus static all-weather control
- duplicate penalty for high active-combo correlation

Contribution sleeve interpretation:

- A sleeve can be interesting with modest standalone return only if it improves portfolio-level behavior.
- Low correlation is not enough if the sleeve is mostly uninvested or creates unacceptable return drag.
- High active-combo correlation is penalized and cannot be used as diversification evidence.
- Portfolio contribution cannot bypass promotion-review, candidate_exhaustive, or paper-forward gates.
"""


def stretch_diagnostic_policy_md() -> str:
    return """# Stretch Diagnostic Policy

The old $300-$400 target is not a hard gate.

The revised batch should record:

- $300 hit rate before stop in rolling windows
- $400 hit rate before stop in rolling windows
- active-combo beat rate in same-window comparisons
- portfolio-level risk-adjusted return improvement

Stretch diagnostics are useful evidence only when accompanied by drawdown control, stress/slippage resilience, non-duplication, and anti-overfit robustness.

Stretch diagnostics are not:

- promotion gates
- paper-forward gates
- reasons to loosen drawdown rules
- reasons to rescue a weak family
- reasons to promote a best row or best family
"""


def do_not_run_md() -> str:
    return """# Do Not Run Batch Now

This packet preregisters the revised-objective sandbox design only.

Do not run:

- batch 002
- strategy discovery
- backtests
- new performance metrics
- provider downloads
- intraday research
- candidate_exhaustive
- paper-forward review or activation
- broker/live paths
- real-money recommendations

Do not create promotable candidates or paper-forward candidates from this preregistration.
"""


def next_action_md(next_action: str) -> str:
    return f"""# Revised Objective Sandbox Next Action

The preregistration is strict and clear enough to implement the revised-objective sandbox batch in a later step.

Exact next action: `{next_action}`

This packet does not run the next action.
"""


def summary_md(manifest: dict[str, Any]) -> str:
    return f"""# Revised Objective Sandbox Preregistration

Sandbox-preregistration-only: `{manifest['sandbox_preregistration_only']}`

Planned batch ID: `{manifest['planned_batch_id']}`

Revised objective profile: `{manifest['revised_objective_profile']}`

Planned max variants: `{manifest['planned_max_variants']}`

Planned family count: `{manifest['planned_family_count']}`

Old dollar target is hard gate: `{manifest['old_dollar_target_is_hard_gate']}`

Sandbox results can promote: `{manifest['sandbox_results_can_promote']}`

Batch 002 directly run: `{manifest['batch_002_directly_run']}`

Next action: `{manifest['next_action']}`

No sandbox batch, discovery, backtest, new performance metric, provider download, intraday data, candidate_exhaustive, paper-forward action, broker/live path, or real-money recommendation occurred.
"""


def update_metadata(root: Path, output: Path, created_utc: str, manifest: dict[str, Any]) -> tuple[bool, bool, bool]:
    registry_path = root / REGISTRY_PATH
    registry = load_yaml(registry_path)
    metadata = registry.setdefault("registry", {})
    before_metadata = deepcopy(metadata)
    metadata.update(
        {
            "revised_objective_sandbox_preregistration_path": str(output.resolve()),
            "revised_objective_sandbox_preregistration_status": "preregistered_not_run",
            "revised_objective_sandbox_preregistration_created_utc": created_utc,
            "current_research_mode": "revised_objective_sandbox_preregistered",
            "current_next_action": manifest["next_action"],
            "official_current_next_action": manifest["next_action"],
            "next_action": manifest["next_action"],
            "sandbox_preregistration_only": True,
            "revised_objective_sandbox_planned_batch_id": manifest["planned_batch_id"],
            "revised_objective_sandbox_planned_max_variants": manifest["planned_max_variants"],
            "revised_objective_sandbox_planned_family_count": manifest["planned_family_count"],
            "revised_objective_sandbox_old_dollar_target_is_hard_gate": False,
            "revised_objective_sandbox_results_can_promote": False,
            "revised_objective_sandbox_batch_002_directly_run": False,
            "revised_objective_sandbox_no_new_batch_run": True,
            "revised_objective_sandbox_no_strategy_discovery": True,
            "revised_objective_sandbox_no_backtests": True,
            "revised_objective_sandbox_no_provider_download": True,
            "revised_objective_sandbox_no_intraday_data": True,
            "revised_objective_sandbox_no_candidate_exhaustive": True,
            "revised_objective_sandbox_no_paper_forward_action": True,
            "revised_objective_sandbox_no_real_money_recommendation": True,
        }
    )
    registry_path.write_text(yaml.safe_dump(registry, sort_keys=False, width=120, allow_unicode=False), encoding="utf-8")

    roadmap_path = root / ROADMAP_PATH
    before_roadmap = roadmap_path.read_text(encoding="utf-8") if roadmap_path.exists() else "# Research Roadmap\n"
    compact_section = f"""## Compact Current State

- Updated UTC: `{created_utc}`
- Current research mode: `revised_objective_sandbox_preregistered`
- Official current next action: `{manifest['next_action']}`
- Revised-objective sandbox preregistration evidence: `{output.resolve()}`
- Planned batch ID: `{manifest['planned_batch_id']}`
- Planned max variants: `{manifest['planned_max_variants']}`
- Planned family count: `{manifest['planned_family_count']}`
- Old $300-$400 target is a stretch diagnostic, not a hard gate.
- Sandbox results cannot promote: `true`
- Batch 002 directly run: `{manifest['batch_002_directly_run']}`
- Active VM and active DSR remain the only supported active/frozen observations.
- `static_all_weather_benchmark_v1` remains benchmark/control only.
- Exact rejected variants remain closed.
- Intraday remains paused: `true`
- This preregistration did not run a sandbox batch, discovery, backtest, new metric, provider download, intraday data, candidate_exhaustive, paper-forward action, broker/live path, or real-money recommendation.
"""
    prereg_section = f"""## Revised Objective Sandbox Preregistration

- Created UTC: `{created_utc}`
- Evidence path: `{output.resolve()}`
- Planned batch ID: `{manifest['planned_batch_id']}`
- Planned max variants: `{manifest['planned_max_variants']}`
- Planned family count: `{manifest['planned_family_count']}`
- Included families: `breakout_continuation`, `portfolio_combination_sleeve_ensemble`, `volatility_regime`, `trend_momentum`, `macro_portfolio_contribution`
- Deprioritized/not in batch 002: `mean_reversion`, `factor_style_rotation`
- Old dollar target is hard gate: `{manifest['old_dollar_target_is_hard_gate']}`
- Sandbox results can promote: `{manifest['sandbox_results_can_promote']}`
- Batch 002 directly run: `{manifest['batch_002_directly_run']}`
- Next action: `{manifest['next_action']}`
- Do not run the next action in this preregistration task.
"""
    after_roadmap = replace_or_append_section(before_roadmap, "## Compact Current State", compact_section)
    after_roadmap = replace_or_append_section(after_roadmap, "## Revised Objective Sandbox Preregistration", prereg_section)
    write_text(roadmap_path, after_roadmap)

    compact_path = root / COMPACT_STATE_PATH
    before_compact = compact_path.read_text(encoding="utf-8") if compact_path.exists() else ""
    after_compact = f"""# Current Tournament State

Created UTC: `{created_utc}`

Current research mode: `revised_objective_sandbox_preregistered`

Current next action: `{manifest['next_action']}`

Revised-objective sandbox preregistration evidence: `{output.resolve()}`

## Decision

- Planned batch ID: `{manifest['planned_batch_id']}`
- Planned max variants: `{manifest['planned_max_variants']}`
- Planned family count: `{manifest['planned_family_count']}`
- Old $300-$400 target is hard gate: `{manifest['old_dollar_target_is_hard_gate']}`
- Sandbox results can promote: `{manifest['sandbox_results_can_promote']}`
- Batch 002 directly run: `{manifest['batch_002_directly_run']}`
- Single safest next action: `{manifest['next_action']}`

## Protected State

- `paper_forward_vm_quality_lowvol_proxy_v1` remains active/accepted/frozen.
- `paper_forward_dsr_sector_equal_weight_defensive_filter_v1` remains active/accepted/frozen.
- `static_all_weather_benchmark_v1` remains benchmark/control only.
- Exact rejected variants remain closed.
- Intraday research remains paused.

## Forbidden Actions

- No new sandbox batch was run by this preregistration.
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
        "sandbox_preregistration_only": manifest["sandbox_preregistration_only"] is True,
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
        "batch_purpose_exists": (output / "batch_002_purpose.md").exists(),
        "batch_001_lessons_applied_exists": (output / "batch_001_lessons_applied.md").exists(),
        "family_selection_exists": (output / "revised_batch_family_selection.md").exists(),
        "revised_scoring_framework_exists": (output / "revised_scoring_framework.md").exists(),
        "target_tier_application_exists": (output / "target_tier_application.md").exists(),
        "portfolio_contribution_scoring_plan_exists": (output / "portfolio_contribution_scoring_plan.md").exists(),
        "stretch_diagnostic_policy_exists": (output / "stretch_diagnostic_policy.md").exists(),
        "do_not_run_file_exists": (output / "do_not_run_batch_now.md").exists(),
        "next_action_valid": manifest["next_action"] in VALID_NEXT_ACTIONS,
        "manifest_flags_match_strict_scope": all(manifest.get(key) == value for key, value in MANIFEST_FLAGS.items()),
        "required_files_exist": all((output / name).exists() for name in REQUIRED_FILES),
    }
    check["consistency_passed"] = all(check.values())
    return check


def run_revised_objective_sandbox_preregistration(root: Path = ROOT) -> dict[str, Any]:
    root = root.resolve()
    created_utc = now_utc()
    output = root / OUTPUT_DIR
    output.mkdir(parents=True, exist_ok=True)

    before_strategies = strategy_snapshot(root)
    batch_hashes_before = batch_result_hashes(root)
    variant_hashes_before = variant_status_hashes(root)
    audit_hashes_before = audit_hashes(root)
    state = source_state(root)
    next_action = NEXT_ACTION_IMPLEMENT

    manifest = {
        "created_utc": created_utc,
        "output_dir": str(output.resolve()),
        **MANIFEST_FLAGS,
        "revised_objective_profile": state["revised_objective"].get(
            "revised_objective_profile", REVISED_OBJECTIVE_PROFILE
        ),
        "planned_batch_id": PLANNED_BATCH_ID,
        "planned_max_variants": PLANNED_MAX_VARIANTS,
        "planned_family_count": PLANNED_FAMILY_COUNT,
        "max_variants_per_family": MAX_VARIANTS_PER_FAMILY,
        "max_parameter_choices_per_indicator": MAX_PARAMETER_CHOICES_PER_INDICATOR,
        "max_portfolio_combination_variants": MAX_PORTFOLIO_COMBINATION_VARIANTS,
        "old_dollar_target_is_hard_gate": False,
        "sandbox_results_can_promote": False,
        "batch_002_directly_run": False,
        "next_action": next_action,
    }

    write_json(output / "revised_objective_sandbox_preregistration_manifest.json", manifest)
    write_text(output / "batch_002_purpose.md", batch_purpose_md())
    write_text(output / "batch_001_lessons_applied.md", batch_001_lessons_md())
    write_text(output / "revised_batch_family_selection.md", family_selection_md())
    write_text(output / "revised_batch_universe_plan.md", universe_plan_md())
    write_text(output / "revised_batch_indicator_plan.md", indicator_plan_md())
    write_text(output / "revised_batch_variant_limits.md", variant_limits_md())
    write_text(output / "revised_scoring_framework.md", scoring_framework_md())
    write_text(output / "target_tier_application.md", target_tier_application_md())
    write_text(output / "portfolio_contribution_scoring_plan.md", portfolio_contribution_scoring_md())
    write_text(output / "stretch_diagnostic_policy.md", stretch_diagnostic_policy_md())
    write_text(output / "do_not_run_batch_now.md", do_not_run_md())
    write_text(output / "revised_objective_sandbox_next_action.md", next_action_md(next_action))
    write_text(output / "revised_objective_sandbox_preregistration_summary.md", summary_md(manifest))
    write_csv(
        output / "planned_family_variant_plan.csv",
        planned_family_rows(),
        ["family_id", "planned_status", "objective_lane", "planned_variant_cap", "research_question", "batch_001_lesson"],
    )
    write_json(output / "revised_objective_sandbox_consistency_check.json", {"consistency_passed": False})

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
    write_json(output / "revised_objective_sandbox_preregistration_manifest.json", manifest)
    write_json(output / "revised_objective_sandbox_consistency_check.json", consistency)

    return {
        "output_dir": str(output),
        "planned_batch_id": manifest["planned_batch_id"],
        "planned_max_variants": manifest["planned_max_variants"],
        "planned_family_count": manifest["planned_family_count"],
        "old_dollar_target_is_hard_gate": manifest["old_dollar_target_is_hard_gate"],
        "sandbox_results_can_promote": manifest["sandbox_results_can_promote"],
        "batch_002_directly_run": manifest["batch_002_directly_run"],
        "next_action": manifest["next_action"],
        "consistency_passed": consistency["consistency_passed"],
    }
