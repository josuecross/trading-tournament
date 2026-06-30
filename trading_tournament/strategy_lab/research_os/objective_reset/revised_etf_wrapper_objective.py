from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import REGISTRY_PATH, ROADMAP_PATH, ROOT
from strategy_lab.research_os.objective_reset.objective_reset_review import (
    BATCH_AUDIT_DIR,
    BATCH_DIR,
    COMPACT_STATE_PATH,
    OUTPUT_DIR as OBJECTIVE_RESET_DIR,
    audit_hashes,
    batch_result_hashes,
    load_yaml,
    replace_or_append_section,
    strategy_snapshot,
    variant_status_hashes,
    write_json,
    write_text,
)


OUTPUT_DIR = Path("evidence") / "objective_reset" / "revised_etf_wrapper_objective" / "latest"

NEXT_ACTION_REVISED_SANDBOX = "pre_register_revised_objective_sandbox_batch"
NEXT_ACTION_CONTRIBUTION = "pre_register_portfolio_contribution_objective"
NEXT_ACTION_OBSERVE = "continue_paper_forward_observation_only"
NEXT_ACTION_PAUSE = "pause_expansion_and_wait_for_manual_direction"
NEXT_ACTION_MANUAL_REVIEW = "manual_review_required_after_revised_objective"
VALID_NEXT_ACTIONS = {
    NEXT_ACTION_REVISED_SANDBOX,
    NEXT_ACTION_CONTRIBUTION,
    NEXT_ACTION_OBSERVE,
    NEXT_ACTION_PAUSE,
    NEXT_ACTION_MANUAL_REVIEW,
}

REVISED_OBJECTIVE_PROFILE = "realistic_etf_wrapper_growth_objective"
REVISED_OBJECTIVE_STATEMENT = (
    "Find daily ETF/fund-wrapper strategies or sleeves that improve realistic risk-adjusted growth "
    "and/or portfolio contribution for a small paper/demo account, while preserving drawdown "
    "discipline and avoiding overfit promotion."
)

MANIFEST_FLAGS = {
    "objective_definition_only": True,
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
    "revised_etf_objective_manifest.json",
    "revised_etf_objective_summary.md",
    "revised_objective_statement.md",
    "objective_lanes.md",
    "target_tiers.md",
    "risk_policy.md",
    "benchmark_policy.md",
    "promotion_policy.md",
    "sandbox_role_under_revised_objective.md",
    "active_observation_policy.md",
    "forbidden_next_steps.md",
    "revised_etf_objective_next_action.md",
    "revised_etf_objective_consistency_check.json",
)


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def source_state(root: Path) -> dict[str, Any]:
    return {
        "objective_reset": read_json(root / OBJECTIVE_RESET_DIR / "objective_reset_review_manifest.json"),
        "batch_manifest": read_json(root / BATCH_DIR / "sandbox_batch_manifest.json"),
        "batch_audit": read_json(root / BATCH_AUDIT_DIR / "sandbox_batch_audit_manifest.json"),
    }


def revised_objective_statement_md() -> str:
    return f"""# Revised Objective Statement

Revised standard-lane objective:

`{REVISED_OBJECTIVE_STATEMENT}`

The project remains profit-oriented. It is still searching for strategies or sleeves that can improve a small paper/demo account, but the old $300-$400 short-horizon dollar target is no longer a hard pass/fail promotion gate.

$300 and $400 checkpoints remain stretch diagnostics. They are useful evidence when reached with controlled risk, robust behavior, and low overfit concern, but they do not override drawdown, benchmark, stress, duplicate, or governance gates.

A strategy can be research-useful if it improves realistic risk-adjusted growth, portfolio contribution, drawdown behavior, or diversification without unacceptable return drag. No strategy can be promoted without a separate promotion review.

Standard-lane constraints remain:

- daily ETF/fund wrappers only
- no leverage
- no shorting
- no derivatives
- no intraday
- no provider download without separate approval
- no parameter fishing
- no broker/live/real-money path
"""


def objective_lanes_md() -> str:
    return """# Objective Lanes

## 1. Standalone ETF-Wrapper Growth Lane

Purpose: identify strategies that can stand alone as profit engines under ETF-only daily-data constraints.

Evaluation dimensions:

- 180-day median final equity
- positive objective progress
- drawdown/risk buffer
- benchmark comparison
- active-reference comparison
- slippage/stress robustness
- duplicate/correlation check
- data-history quality
- simplicity and turnover

## 2. Portfolio-Contribution Sleeve Lane

Purpose: identify sleeves that improve the active VM/DSR portfolio at the portfolio level.

Evaluation dimensions:

- portfolio-level return/risk improvement
- drawdown reduction
- volatility reduction
- correlation reduction
- acceptable return drag
- improved risk-adjusted outcome
- contribution versus active combo
- contribution versus static all-weather control

## 3. Benchmark/Control Lane

Purpose: preserve useful controls without treating them as promotable strategies.

Examples:

- SPY
- QQQ
- BIL
- SPY_200d
- static all-weather
- active VM
- active DSR
- active combo

## 4. Exploratory Sandbox Lane

Purpose: map opportunity space without promotion.

All exploratory sandbox outputs remain `non_promotable_exploration`. Sandbox results can inform future preregistration only after manual review; they cannot become paper-forward candidates directly.
"""


def target_tiers_md() -> str:
    return """# Target Tiers

## Core Success Diagnostics

Core diagnostics define whether future research is worth promotion review consideration. They are not guarantees and do not authorize paper-forward action.

- positive 180-day median progress
- controlled max drawdown
- survives slippage/stress review
- not dominated by active references
- not a duplicate of active combo
- stable enough across neighboring parameters or related family concepts
- enough data-history quality to avoid limited-history false confidence
- simple enough rules and turnover for paper/demo practicality

## Realistic Expectation Bands

The revised ETF-wrapper objective should evaluate monthly and 180-day progress as bands, not fixed promises.

- Monthly diagnostics: evidence of positive expectancy or contribution over repeated windows, with drawdown and turnover still acceptable.
- 180-day diagnostics: median final equity above starting capital, meaningful risk-adjusted progress, and no unacceptable downside concentration.
- Benchmark diagnostics: relevant benchmark and active-reference comparisons are evidence weights, not a requirement to beat every benchmark in every metric.

## Stretch Diagnostics

Stretch diagnostics remain useful evidence but are not automatic promotion gates.

- reaches $300 before stop in a meaningful fraction of rolling windows
- reaches $400 before stop in a meaningful fraction of rolling windows
- beats active combo in same-window comparisons
- improves portfolio-level risk-adjusted return

Failure to hit $300-$400 alone does not invalidate a strategy if it has strong portfolio contribution. Hitting $300-$400 alone does not justify promotion if risk, overfit, benchmark, duplicate, or governance gates fail.
"""


def risk_policy_md() -> str:
    return """# Risk Policy

Drawdown discipline is preserved.

- A hard small-account drawdown guard remains required for standard-lane candidates.
- Risk-buffer review remains required before any promotion-review eligibility.
- Stress and slippage review remain required and must not be skipped because a row has attractive headline return.
- Drawdown interpretation is lane-specific and must be preregistered before future runs.
- Standalone growth rows must satisfy standalone drawdown/risk gates.
- Portfolio-contribution sleeves must be assessed at the portfolio level, including whether they reduce or worsen active VM/DSR portfolio drawdown.
- Benchmark/control rows are not promotable and do not become candidates because they look attractive in one comparison.
- No risk gate may be loosened after seeing results.

Leverage remains forbidden in the standard lane. Leverage sensitivity can only be a separate non-promotable diagnostic after manual approval.

No real-money recommendation, broker/live path, paper-forward review, or paper-forward activation is authorized by this objective-definition step.
"""


def benchmark_policy_md() -> str:
    return """# Benchmark Policy

Benchmarks remain evidence and controls, not automatic promotion blockers in every metric.

Benchmarks and references to use under the revised objective:

- SPY
- QQQ
- BIL
- SPY_200d
- active VM
- active DSR
- active combo
- static all-weather
- same-window benchmarks
- limited-history labeling

A candidate does not need to beat every benchmark in every metric to be research-useful. A standalone growth candidate must show enough edge versus relevant active references to justify further review. A contribution sleeve must improve portfolio-level behavior, not necessarily standalone return.

Benchmark/control rows are not promotable. They may be used to calibrate opportunity cost, drawdown, volatility, regime behavior, and duplicate risk.

Same-window benchmark comparisons must stay visible. Limited-history rows must be labeled clearly and cannot borrow credibility from longer-history references.
"""


def promotion_policy_md() -> str:
    return """# Promotion Policy

No step can be skipped.

Required staged path:

1. Sandbox result
2. Future preregistration candidate
3. Frozen formal discovery candidate
4. Promotion review candidate
5. Candidate exhaustive
6. Paper/demo observation

No sandbox output can become paper-forward directly. No best row can be promoted. No rejected row can be rescued without a new hypothesis and manual review.

Promotion-review eligibility language:

- Standalone growth candidates must show realistic risk-adjusted growth, drawdown control, stress/slippage tolerance, active-reference relevance, duplicate avoidance, and data-quality sufficiency.
- Portfolio-contribution sleeves must show preregistered portfolio-level improvement with acceptable return drag and clear non-duplication.
- Benchmark/control rows remain controls only.
- Non-promotable sandbox results remain evidence for future objective design, not candidates.
"""


def sandbox_role_md() -> str:
    return """# Sandbox Role Under Revised Objective

The exploratory sandbox remains an opportunity-map tool. It may test preregistered research maps after a revised-objective sandbox batch is separately preregistered.

All sandbox outputs remain `non_promotable_exploration`.

The sandbox may:

- map families against revised target tiers
- compare standalone-growth and contribution clues
- flag possible future preregistration candidates
- identify duplicate, weak, risky, or low-contribution areas

The sandbox may not:

- promote rows
- create paper-forward candidates
- rescue rejected variants
- loosen gates after results
- become candidate_exhaustive
- trigger provider downloads, intraday research, broker paths, or real-money recommendations
"""


def active_observation_policy_md() -> str:
    return """# Active Observation Policy

- `paper_forward_vm_quality_lowvol_proxy_v1` remains active/frozen.
- `paper_forward_dsr_sector_equal_weight_defensive_filter_v1` remains active/frozen.
- `static_all_weather_benchmark_v1` remains benchmark/control only.
- Exact rejected variants remain closed.
- Intraday remains paused.
- No new active strategy is created by this objective-definition step.
- No paper-forward review or activation is authorized.
- No broker/live/real-money action is authorized.
"""


def forbidden_next_steps_md() -> str:
    return """# Forbidden Next Steps

Explicitly forbidden:

- sandbox batch 002 directly before revised objective is committed
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
    return f"""# Revised ETF Objective Next Action

The revised objective is clear enough to preregister a future sandbox batch with updated scoring and target tiers.

Exact next action: `{next_action}`

This is a preregistration action only. Do not run a sandbox batch, discovery, backtest, provider download, candidate_exhaustive, paper-forward action, broker/live path, or real-money action in this objective-definition step.
"""


def summary_md(manifest: dict[str, Any]) -> str:
    return f"""# Revised ETF Wrapper Objective

Objective-definition-only: `{manifest['objective_definition_only']}`

Revised objective profile: `{manifest['revised_objective_profile']}`

Old $300-$400 target reclassified as stretch diagnostic: `{manifest['old_dollar_target_reclassified_as_stretch_diagnostic']}`

Standard-lane leverage allowed: `{manifest['standard_lane_leverage_allowed']}`

Batch 002 directly authorized: `{manifest['batch_002_directly_authorized']}`

Next action: `{manifest['next_action']}`

Revised objective statement:

`{REVISED_OBJECTIVE_STATEMENT}`

No sandbox batch, discovery, backtest, new performance metric, provider download, intraday data, candidate_exhaustive, paper-forward action, broker/live path, or real-money recommendation occurred.
"""


def update_metadata(root: Path, output: Path, created_utc: str, manifest: dict[str, Any]) -> tuple[bool, bool, bool]:
    registry_path = root / REGISTRY_PATH
    registry = load_yaml(registry_path)
    metadata = registry.setdefault("registry", {})
    before_metadata = dict(metadata)
    metadata.update(
        {
            "revised_etf_wrapper_objective_path": str(output.resolve()),
            "revised_etf_wrapper_objective_status": "defined",
            "revised_etf_wrapper_objective_created_utc": created_utc,
            "current_research_mode": "revised_etf_wrapper_objective_defined",
            "current_next_action": manifest["next_action"],
            "official_current_next_action": manifest["next_action"],
            "next_action": manifest["next_action"],
            "objective_definition_only": True,
            "revised_objective_profile": manifest["revised_objective_profile"],
            "old_dollar_target_reclassified_as_stretch_diagnostic": True,
            "standard_lane_leverage_allowed": False,
            "revised_objective_batch_002_directly_authorized": False,
            "revised_objective_no_new_sandbox_batch_run": True,
            "revised_objective_no_strategy_discovery": True,
            "revised_objective_no_backtests": True,
            "revised_objective_no_provider_download": True,
            "revised_objective_no_intraday_data": True,
            "revised_objective_no_candidate_exhaustive": True,
            "revised_objective_no_paper_forward_action": True,
            "revised_objective_no_real_money_recommendation": True,
        }
    )
    registry_path.write_text(
        __import__("yaml").safe_dump(registry, sort_keys=False, width=120, allow_unicode=False),
        encoding="utf-8",
    )

    roadmap_path = root / ROADMAP_PATH
    before_roadmap = roadmap_path.read_text(encoding="utf-8") if roadmap_path.exists() else "# Research Roadmap\n"
    compact_section = f"""## Compact Current State

- Updated UTC: `{created_utc}`
- Current research mode: `revised_etf_wrapper_objective_defined`
- Official current next action: `{manifest['next_action']}`
- Revised ETF-wrapper objective evidence: `{output.resolve()}`
- Revised objective profile: `{manifest['revised_objective_profile']}`
- Old $300-$400 target is now a stretch diagnostic, not a hard gate.
- Standard-lane leverage allowed: `{manifest['standard_lane_leverage_allowed']}`
- Batch 002 directly authorized: `{manifest['batch_002_directly_authorized']}`
- Active VM and active DSR remain the only supported active/frozen observations.
- `static_all_weather_benchmark_v1` remains benchmark/control only.
- Exact rejected variants remain closed.
- Intraday remains paused: `true`
- This objective definition did not run a new sandbox batch, discovery, backtest, new metric, provider download, intraday data, candidate_exhaustive, paper-forward action, broker/live path, or real-money recommendation.
"""
    objective_section = f"""## Revised ETF Wrapper Objective

- Created UTC: `{created_utc}`
- Evidence path: `{output.resolve()}`
- Revised objective profile: `{manifest['revised_objective_profile']}`
- Objective statement: `{REVISED_OBJECTIVE_STATEMENT}`
- Old $300-$400 target reclassified as stretch diagnostic: `{manifest['old_dollar_target_reclassified_as_stretch_diagnostic']}`
- Standard-lane leverage allowed: `{manifest['standard_lane_leverage_allowed']}`
- Batch 002 directly authorized: `{manifest['batch_002_directly_authorized']}`
- Next action: `{manifest['next_action']}`
- Do not run the next action in this objective-definition task.
"""
    after_roadmap = replace_or_append_section(before_roadmap, "## Compact Current State", compact_section)
    after_roadmap = replace_or_append_section(after_roadmap, "## Revised ETF Wrapper Objective", objective_section)
    write_text(roadmap_path, after_roadmap)

    compact_path = root / COMPACT_STATE_PATH
    before_compact = compact_path.read_text(encoding="utf-8") if compact_path.exists() else ""
    after_compact = f"""# Current Tournament State

Created UTC: `{created_utc}`

Current research mode: `revised_etf_wrapper_objective_defined`

Current next action: `{manifest['next_action']}`

Revised ETF-wrapper objective evidence: `{output.resolve()}`

## Decision

- Revised objective profile: `{manifest['revised_objective_profile']}`
- Old $300-$400 target is a stretch diagnostic, not a hard gate.
- Standard-lane leverage allowed: `{manifest['standard_lane_leverage_allowed']}`
- Batch 002 directly authorized: `{manifest['batch_002_directly_authorized']}`
- Single safest next action: `{manifest['next_action']}`

## Protected State

- `paper_forward_vm_quality_lowvol_proxy_v1` remains active/accepted/frozen.
- `paper_forward_dsr_sector_equal_weight_defensive_filter_v1` remains active/accepted/frozen.
- `static_all_weather_benchmark_v1` remains benchmark/control only.
- Exact rejected variants remain closed.
- Intraday research remains paused.

## Forbidden Actions

- No new sandbox batch was run by this objective definition.
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
        "objective_definition_only": manifest["objective_definition_only"] is True,
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
        "revised_objective_statement_exists": (output / "revised_objective_statement.md").exists(),
        "objective_lanes_exist": (output / "objective_lanes.md").exists(),
        "target_tiers_exist": (output / "target_tiers.md").exists(),
        "risk_policy_exists": (output / "risk_policy.md").exists(),
        "benchmark_policy_exists": (output / "benchmark_policy.md").exists(),
        "promotion_policy_exists": (output / "promotion_policy.md").exists(),
        "sandbox_role_exists": (output / "sandbox_role_under_revised_objective.md").exists(),
        "forbidden_next_steps_exists": (output / "forbidden_next_steps.md").exists(),
        "next_action_valid": manifest["next_action"] in VALID_NEXT_ACTIONS,
        "manifest_flags_match_strict_scope": all(manifest.get(key) == value for key, value in MANIFEST_FLAGS.items()),
        "required_files_exist": all((output / name).exists() for name in REQUIRED_FILES),
    }
    check["consistency_passed"] = all(check.values())
    return check


def run_revised_etf_wrapper_objective(root: Path = ROOT) -> dict[str, Any]:
    root = root.resolve()
    created_utc = now_utc()
    output = root / OUTPUT_DIR
    output.mkdir(parents=True, exist_ok=True)

    before_strategies = strategy_snapshot(root)
    batch_hashes_before = batch_result_hashes(root)
    variant_hashes_before = variant_status_hashes(root)
    audit_hashes_before = audit_hashes(root)
    state = source_state(root)
    next_action = NEXT_ACTION_REVISED_SANDBOX

    manifest = {
        "created_utc": created_utc,
        "output_dir": str(output.resolve()),
        **MANIFEST_FLAGS,
        "revised_objective_profile": REVISED_OBJECTIVE_PROFILE,
        "revised_objective_statement": REVISED_OBJECTIVE_STATEMENT,
        "old_dollar_target_reclassified_as_stretch_diagnostic": True,
        "standard_lane_leverage_allowed": False,
        "batch_002_directly_authorized": False,
        "objective_reset_source_next_action": state["objective_reset"].get("next_action"),
        "next_action": next_action,
    }

    write_json(output / "revised_etf_objective_manifest.json", manifest)
    write_text(output / "revised_objective_statement.md", revised_objective_statement_md())
    write_text(output / "objective_lanes.md", objective_lanes_md())
    write_text(output / "target_tiers.md", target_tiers_md())
    write_text(output / "risk_policy.md", risk_policy_md())
    write_text(output / "benchmark_policy.md", benchmark_policy_md())
    write_text(output / "promotion_policy.md", promotion_policy_md())
    write_text(output / "sandbox_role_under_revised_objective.md", sandbox_role_md())
    write_text(output / "active_observation_policy.md", active_observation_policy_md())
    write_text(output / "forbidden_next_steps.md", forbidden_next_steps_md())
    write_text(output / "revised_etf_objective_next_action.md", next_action_md(next_action))
    write_text(output / "revised_etf_objective_summary.md", summary_md(manifest))
    write_json(output / "revised_etf_objective_consistency_check.json", {"consistency_passed": False})

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
    write_json(output / "revised_etf_objective_manifest.json", manifest)
    write_json(output / "revised_etf_objective_consistency_check.json", consistency)

    return {
        "output_dir": str(output),
        "revised_objective_profile": manifest["revised_objective_profile"],
        "old_dollar_target_reclassified_as_stretch_diagnostic": manifest[
            "old_dollar_target_reclassified_as_stretch_diagnostic"
        ],
        "standard_lane_leverage_allowed": manifest["standard_lane_leverage_allowed"],
        "batch_002_directly_authorized": manifest["batch_002_directly_authorized"],
        "next_action": manifest["next_action"],
        "consistency_passed": consistency["consistency_passed"],
    }
