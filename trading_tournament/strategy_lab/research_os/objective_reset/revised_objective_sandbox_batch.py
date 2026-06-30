from __future__ import annotations

import csv
import json
import math
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import REGISTRY_PATH, ROADMAP_PATH, ROOT
from strategy_lab.research_os.exploratory_sandbox.sandbox_batch import (
    STARTING_EQUITY,
    aligned_metric_delta,
    metrics_for_returns,
    price_frame,
    reference_returns,
    safe_float,
    score_frame,
    weights_from_score,
)
from strategy_lab.research_os.exploratory_sandbox.sandbox_data_preflight import (
    preflight_report,
    preflight_universe_availability,
)
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
from strategy_lab.research_os.objective_reset.revised_objective_batch_config import (
    BATCH_ID,
    EXCLUDED_FAMILIES,
    EXCLUDED_FAMILY_REASONS,
    FAMILY_DEFINITIONS,
    FORBIDDEN_STATUSES,
    INCLUDED_FAMILIES,
    INITIAL_STATUS,
    MAX_FAMILIES,
    MAX_PARAMETER_CHOICES_PER_INDICATOR,
    MAX_PORTFOLIO_COMBINATION_VARIANTS,
    MAX_TOTAL_VARIANTS,
    MAX_VARIANTS_PER_FAMILY,
    OLD_DOLLAR_TARGET_IS_HARD_GATE,
    PAPER_CANDIDATES_CAN_BE_CREATED,
    REVISED_OBJECTIVE_PROFILE,
    SANDBOX_RESULTS_CAN_PROMOTE,
    STRETCH_DIAGNOSTICS_ARE_PROMOTION_GATES,
    ALLOWED_RESULT_STATUSES,
    assert_status_allowed,
    forbidden_statuses_blocked,
)
from strategy_lab.research_os.objective_reset.revised_objective_contribution_schema import (
    portfolio_contribution_schema_report,
    stretch_diagnostic_schema_report,
)
from strategy_lab.research_os.objective_reset.revised_objective_scoring_schema import (
    schema_markdown,
    revised_scoring_schema_report,
)
from strategy_lab.research_os.objective_reset.revised_objective_sandbox_preregistration import (
    OUTPUT_DIR as PREREGISTRATION_DIR,
)
from strategy_lab.research_os.objective_reset.revised_objective_scoring_v3 import score_row_v3
from strategy_lab.research_os.objective_reset.revised_objective_target_tiers import (
    target_tier_mapping_report,
)
from strategy_lab.research_os.objective_reset.revised_objective_variant_plan import (
    fieldnames as variant_fieldnames,
    generate_dry_run_variant_plan,
    validate_variant_plan,
)


OUTPUT_DIR = Path("evidence") / "objective_reset" / "revised_objective_sandbox_implementation" / "latest"
BATCH_OUTPUT_DIR = Path("evidence") / "objective_reset" / "revised_objective_sandbox_batch" / "latest"
NEXT_ACTION_RUN_BATCH = "run_revised_objective_sandbox_batch"
NEXT_ACTION_MANUAL_REVIEW = "manual_review_required_after_revised_objective_sandbox_implementation"
NEXT_ACTION_OBSERVE = "continue_paper_forward_observation_only"
NEXT_ACTION_PAUSE = "pause_expansion_and_wait_for_manual_direction"
VALID_NEXT_ACTIONS = {
    NEXT_ACTION_RUN_BATCH,
    NEXT_ACTION_MANUAL_REVIEW,
    NEXT_ACTION_OBSERVE,
    NEXT_ACTION_PAUSE,
}

BATCH_NEXT_ACTION_AUDIT = "audit_revised_objective_sandbox_batch_results"
BATCH_NEXT_ACTION_FAMILY = "pre_register_one_revised_objective_family"
BATCH_NEXT_ACTION_MANUAL = "manual_review_required_after_revised_objective_sandbox_batch"
BATCH_NEXT_ACTION_OBSERVE = "continue_paper_forward_observation_only"
BATCH_NEXT_ACTION_PAUSE = "pause_expansion_and_wait_for_manual_direction"
BATCH_VALID_NEXT_ACTIONS = {
    BATCH_NEXT_ACTION_AUDIT,
    BATCH_NEXT_ACTION_FAMILY,
    BATCH_NEXT_ACTION_MANUAL,
    BATCH_NEXT_ACTION_OBSERVE,
    BATCH_NEXT_ACTION_PAUSE,
}

MANIFEST_FLAGS = {
    "sandbox_implementation_only": True,
    "batch_id": BATCH_ID,
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
    "revised_objective_sandbox_implementation_manifest.json",
    "revised_objective_sandbox_implementation_summary.md",
    "batch_002_dry_run_variant_plan.csv",
    "batch_002_family_plan.md",
    "batch_002_excluded_families.md",
    "revised_scoring_schema.md",
    "target_tier_mapping.md",
    "portfolio_contribution_schema.md",
    "stretch_diagnostic_schema.md",
    "risk_integrity_schema.md",
    "overfit_risk_schema.md",
    "practicality_schema.md",
    "status_taxonomy_validation.md",
    "data_preflight_report.md",
    "do_not_run_batch_now.md",
    "revised_objective_sandbox_implementation_next_action.md",
    "revised_objective_sandbox_implementation_consistency_check.json",
)

BATCH_MANIFEST_FLAGS = {
    "sandbox_batch_run": True,
    "batch_id": BATCH_ID,
    "sandbox_results_non_promotable": True,
    "sandbox_can_create_paper_candidates": False,
    "formal_discovery_run": False,
    "strategy_discovery_run": False,
    "candidate_exhaustive_run": False,
    "paper_forward_review": False,
    "paper_forward_activation": False,
    "indicator_library_dependency_added": False,
    "provider_download": False,
    "intraday_data_used": False,
    "broker_orders_submitted": False,
    "broker_orders_cancelled": False,
    "live_orders": False,
    "real_money_recommendation": False,
    "active_strategy_state_changed": False,
    "rejected_strategy_state_changed": False,
    "exact_rejected_variants_reopened": False,
    "intraday_research_remains_paused": True,
    "old_dollar_target_is_hard_gate": False,
    "stretch_diagnostics_are_promotion_gates": False,
    "best_single_variant_promoted": False,
}

BATCH_REQUIRED_FILES = (
    "revised_objective_sandbox_batch_manifest.json",
    "revised_objective_sandbox_batch_summary.md",
    "batch_preflight_report.md",
    "batch_002_variant_results.csv",
    "batch_002_family_summary.csv",
    "batch_002_family_summary.md",
    "standalone_growth_score_summary.csv",
    "portfolio_contribution_score_summary.csv",
    "stretch_diagnostic_summary.csv",
    "risk_integrity_summary.csv",
    "overfit_risk_summary.csv",
    "practicality_summary.csv",
    "benchmark_comparison_summary.csv",
    "family_actionability_review.md",
    "future_preregistration_candidates.md",
    "do_not_promote.md",
    "revised_objective_sandbox_batch_next_action.md",
    "revised_objective_sandbox_batch_consistency_check.json",
)

PARAMETER_CHOICES_BY_INDICATOR: dict[str, tuple[dict[str, Any], ...]] = {
    "sma": ({"lookback": 40}, {"lookback": 80}, {"lookback": 120}, {"lookback": 180}),
    "ema": ({"lookback": 34}, {"lookback": 55}, {"lookback": 89}, {"lookback": 144}),
    "atr": ({"lookback": 14}, {"lookback": 21}, {"lookback": 42}, {"lookback": 63}),
    "rsi": ({"lookback": 7}, {"lookback": 14}, {"lookback": 21}, {"lookback": 28}),
    "bollinger_bands": (
        {"lookback": 20, "band_width": 2.0},
        {"lookback": 30, "band_width": 2.0},
        {"lookback": 40, "band_width": 2.0},
        {"lookback": 60, "band_width": 2.0},
    ),
    "realized_volatility": ({"lookback": 20}, {"lookback": 42}, {"lookback": 63}, {"lookback": 126}),
    "roc_rolling_return": ({"lookback": 21}, {"lookback": 63}, {"lookback": 126}, {"lookback": 189}),
    "donchian_prior_high": ({"lookback": 40}, {"lookback": 55}, {"lookback": 100}, {"lookback": 150}),
    "volume_sma_filter_alignment": ({"lookback": 20}, {"lookback": 50}, {"lookback": 100}, {"lookback": 150}),
    "rolling_percentile_rank": ({"lookback": 42}, {"lookback": 63}, {"lookback": 126}, {"lookback": 189}),
    "moving_average_regime": (
        {"fast": 40, "slow": 160},
        {"fast": 50, "slow": 200},
        {"fast": 80, "slow": 200},
        {"fast": 100, "slow": 240},
    ),
    "spy_regime_features": ({"lookback": 42}, {"lookback": 63}, {"lookback": 126}, {"lookback": 189}),
}


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
        "preregistration": read_json(
            root / PREREGISTRATION_DIR / "revised_objective_sandbox_preregistration_manifest.json"
        ),
        "batch_manifest": read_json(root / BATCH_DIR / "sandbox_batch_manifest.json"),
        "batch_audit": read_json(root / BATCH_AUDIT_DIR / "sandbox_batch_audit_manifest.json"),
    }


def family_plan_md() -> str:
    lines = [
        "# Batch 002 Family Plan",
        "",
        f"Included family count: `{len(INCLUDED_FAMILIES)}`",
        "",
        "Every family is implemented as revised-objective, exploratory, sandbox-only, and non-promotable.",
        "",
    ]
    for family_id in INCLUDED_FAMILIES:
        family = FAMILY_DEFINITIONS[family_id]
        lines.extend(
            [
                f"## `{family_id}`",
                f"- Objective lane: `{family.objective_lane}`",
                f"- Planned variant cap: `{family.planned_variant_cap}`",
                f"- Purpose: {family.purpose}",
                f"- Batch 001 lesson: {family.batch_001_lesson}",
                f"- Implementation requirement: {family.implementation_requirement}",
                f"- Universe groups: `{', '.join(family.universe_groups)}`",
                f"- Indicator concepts: `{', '.join(family.indicator_concepts)}`",
                "",
            ]
        )
    return "\n".join(lines)


def excluded_families_md() -> str:
    lines = ["# Batch 002 Excluded Families", ""]
    for family_id in EXCLUDED_FAMILIES:
        lines.append(f"- `{family_id}`: {EXCLUDED_FAMILY_REASONS[family_id]}.")
    lines.append("")
    lines.append("Excluded families are not generated in the dry-run variant plan.")
    return "\n".join(lines)


def status_taxonomy_validation_md() -> str:
    allowed = "\n".join(f"- `{status}`" for status in (INITIAL_STATUS, *()))
    future_allowed = "\n".join(
        f"- `{status}`"
        for status in (
            "sandbox_discard",
            "sandbox_family_weak",
            "sandbox_family_interesting",
            "sandbox_component_candidate",
            "sandbox_portfolio_sleeve_candidate",
            "sandbox_needs_objective_reset",
            "sandbox_data_blocked",
            "sandbox_future_preregistration_candidate",
        )
    )
    forbidden = "\n".join(f"- `{status}`" for status in FORBIDDEN_STATUSES)
    return f"""# Status Taxonomy Validation

Initial dry-run variant status:

{allowed}

Allowed future sandbox statuses:

{future_allowed}

Forbidden statuses:

{forbidden}

Forbidden statuses blocked by implementation: `{forbidden_statuses_blocked()}`

All dry-run variants are emitted as `{INITIAL_STATUS}`.
"""


def do_not_run_md() -> str:
    return """# Do Not Run Batch Now

This implementation prepares a future revised-objective sandbox batch but does not execute it.

Do not run:

- batch 002 execution
- strategy discovery
- backtests
- new performance metrics
- provider downloads or provider APIs
- intraday research
- candidate_exhaustive
- paper-forward review or activation
- broker/live paths
- real-money recommendations

Do not create promotable candidates or paper-forward candidates from this implementation.
"""


def next_action_md(next_action: str) -> str:
    return f"""# Revised Objective Sandbox Implementation Next Action

The dry-run variant plan and revised scoring schemas are implemented without running the sandbox.

Exact next action: `{next_action}`

Do not run the next action in this implementation task.
"""


def summary_md(manifest: dict[str, Any]) -> str:
    return f"""# Revised Objective Sandbox Implementation

Sandbox-implementation-only: `{manifest['sandbox_implementation_only']}`

Batch ID: `{manifest['batch_id']}`

Planned variant count: `{manifest['planned_variant_count']}`

Planned family count: `{manifest['planned_family_count']}`

Planned max variants: `{manifest['planned_max_variants']}`

Old dollar target is hard gate: `{manifest['old_dollar_target_is_hard_gate']}`

Stretch diagnostics are promotion gates: `{manifest['stretch_diagnostics_are_promotion_gates']}`

Sandbox results can promote: `{manifest['sandbox_results_can_promote']}`

Paper candidates can be created: `{manifest['paper_candidates_can_be_created']}`

Forbidden statuses blocked: `{manifest['forbidden_statuses_blocked']}`

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
            "revised_objective_sandbox_implementation_path": str(output.resolve()),
            "revised_objective_sandbox_implementation_status": "implemented_not_run",
            "revised_objective_sandbox_implementation_created_utc": created_utc,
            "current_research_mode": "revised_objective_sandbox_implemented_not_run",
            "current_next_action": manifest["next_action"],
            "official_current_next_action": manifest["next_action"],
            "next_action": manifest["next_action"],
            "revised_objective_sandbox_implementation_only": True,
            "revised_objective_sandbox_implementation_batch_id": manifest["batch_id"],
            "revised_objective_sandbox_implementation_planned_variant_count": manifest["planned_variant_count"],
            "revised_objective_sandbox_implementation_planned_family_count": manifest["planned_family_count"],
            "revised_objective_sandbox_implementation_no_new_batch_run": True,
            "revised_objective_sandbox_implementation_no_strategy_discovery": True,
            "revised_objective_sandbox_implementation_no_backtests": True,
            "revised_objective_sandbox_implementation_no_performance_metrics": True,
            "revised_objective_sandbox_implementation_no_provider_download": True,
            "revised_objective_sandbox_implementation_no_intraday_data": True,
            "revised_objective_sandbox_implementation_no_candidate_exhaustive": True,
            "revised_objective_sandbox_implementation_no_paper_forward_action": True,
            "revised_objective_sandbox_implementation_no_real_money_recommendation": True,
        }
    )
    registry_path.write_text(yaml.safe_dump(registry, sort_keys=False, width=120, allow_unicode=False), encoding="utf-8")

    roadmap_path = root / ROADMAP_PATH
    before_roadmap = roadmap_path.read_text(encoding="utf-8") if roadmap_path.exists() else "# Research Roadmap\n"
    compact_section = f"""## Compact Current State

- Updated UTC: `{created_utc}`
- Current research mode: `revised_objective_sandbox_implemented_not_run`
- Official current next action: `{manifest['next_action']}`
- Revised-objective sandbox implementation evidence: `{output.resolve()}`
- Batch ID: `{manifest['batch_id']}`
- Planned variant count: `{manifest['planned_variant_count']}`
- Planned family count: `{manifest['planned_family_count']}`
- Old $300-$400 target is hard gate: `{manifest['old_dollar_target_is_hard_gate']}`
- Stretch diagnostics are promotion gates: `{manifest['stretch_diagnostics_are_promotion_gates']}`
- Sandbox results can promote: `{manifest['sandbox_results_can_promote']}`
- Batch 002 was not run.
- Active VM and active DSR remain the only supported active/frozen observations.
- `static_all_weather_benchmark_v1` remains benchmark/control only.
- Exact rejected variants remain closed.
- Intraday remains paused: `true`
- This implementation did not run a sandbox batch, discovery, backtest, new metric, provider download, intraday data, candidate_exhaustive, paper-forward action, broker/live path, or real-money recommendation.
"""
    section = f"""## Revised Objective Sandbox Implementation

- Created UTC: `{created_utc}`
- Evidence path: `{output.resolve()}`
- Batch ID: `{manifest['batch_id']}`
- Planned variant count: `{manifest['planned_variant_count']}`
- Planned family count: `{manifest['planned_family_count']}`
- Revised scoring schemas created: `true`
- Target-tier mapping created: `true`
- Portfolio-contribution schema created: `true`
- Stretch diagnostics are promotion gates: `{manifest['stretch_diagnostics_are_promotion_gates']}`
- Forbidden statuses blocked: `{manifest['forbidden_statuses_blocked']}`
- Next action: `{manifest['next_action']}`
- Do not run the next action in this implementation task.
"""
    after_roadmap = replace_or_append_section(before_roadmap, "## Compact Current State", compact_section)
    after_roadmap = replace_or_append_section(after_roadmap, "## Revised Objective Sandbox Implementation", section)
    write_text(roadmap_path, after_roadmap)

    compact_path = root / COMPACT_STATE_PATH
    before_compact = compact_path.read_text(encoding="utf-8") if compact_path.exists() else ""
    after_compact = f"""# Current Tournament State

Created UTC: `{created_utc}`

Current research mode: `revised_objective_sandbox_implemented_not_run`

Current next action: `{manifest['next_action']}`

Revised-objective sandbox implementation evidence: `{output.resolve()}`

## Decision

- Batch ID: `{manifest['batch_id']}`
- Planned variant count: `{manifest['planned_variant_count']}`
- Planned family count: `{manifest['planned_family_count']}`
- Batch 002 was not run.
- Sandbox results can promote: `{manifest['sandbox_results_can_promote']}`
- Paper candidates can be created: `{manifest['paper_candidates_can_be_created']}`
- Single safest next action: `{manifest['next_action']}`

## Protected State

- `paper_forward_vm_quality_lowvol_proxy_v1` remains active/accepted/frozen.
- `paper_forward_dsr_sector_equal_weight_defensive_filter_v1` remains active/accepted/frozen.
- `static_all_weather_benchmark_v1` remains benchmark/control only.
- Exact rejected variants remain closed.
- Intraday research remains paused.

## Forbidden Actions

- No new sandbox batch was run by this implementation.
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
        "sandbox_implementation_only": manifest["sandbox_implementation_only"] is True,
        "batch_id_correct": manifest["batch_id"] == BATCH_ID,
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
        "dry_run_variant_plan_exists": (output / "batch_002_dry_run_variant_plan.csv").exists(),
        "planned_variant_count_within_limit": manifest["planned_variant_count"] <= MAX_TOTAL_VARIANTS,
        "planned_family_count_within_limit": manifest["planned_family_count"] <= MAX_FAMILIES,
        "forbidden_statuses_blocked": manifest["forbidden_statuses_blocked"] is True,
        "revised_scoring_schema_exists": (output / "revised_scoring_schema.md").exists(),
        "target_tier_mapping_exists": (output / "target_tier_mapping.md").exists(),
        "portfolio_contribution_schema_exists": (output / "portfolio_contribution_schema.md").exists(),
        "stretch_diagnostic_schema_exists": (output / "stretch_diagnostic_schema.md").exists(),
        "old_dollar_target_is_hard_gate_false": manifest["old_dollar_target_is_hard_gate"] is False,
        "stretch_diagnostics_are_promotion_gates_false": manifest["stretch_diagnostics_are_promotion_gates"] is False,
        "do_not_run_file_exists": (output / "do_not_run_batch_now.md").exists(),
        "next_action_valid": manifest["next_action"] in VALID_NEXT_ACTIONS,
        "manifest_flags_match_strict_scope": all(manifest.get(key) == value for key, value in MANIFEST_FLAGS.items()),
        "required_files_exist": all((output / name).exists() for name in REQUIRED_FILES),
    }
    check["consistency_passed"] = all(check.values())
    return check


def run_revised_objective_sandbox_dry_run(
    root: Path = ROOT,
    *,
    batch_id: str = BATCH_ID,
    max_variants: int = MAX_TOTAL_VARIANTS,
    update_project_metadata: bool = False,
) -> dict[str, Any]:
    root = root.resolve()
    created_utc = now_utc()
    output = root / OUTPUT_DIR
    output.mkdir(parents=True, exist_ok=True)

    before_strategies = strategy_snapshot(root)
    batch_hashes_before = batch_result_hashes(root)
    variant_hashes_before = variant_status_hashes(root)
    audit_hashes_before = audit_hashes(root)
    source_state(root)
    rows = generate_dry_run_variant_plan(batch_id=batch_id, max_variants=max_variants)
    validate_variant_plan(rows, batch_id=batch_id, max_variants=max_variants)
    family_ids = sorted({str(row["family_id"]) for row in rows})
    next_action = NEXT_ACTION_RUN_BATCH

    write_csv(output / "batch_002_dry_run_variant_plan.csv", rows, variant_fieldnames())
    write_text(output / "batch_002_family_plan.md", family_plan_md())
    write_text(output / "batch_002_excluded_families.md", excluded_families_md())
    write_text(output / "revised_scoring_schema.md", revised_scoring_schema_report())
    write_text(output / "target_tier_mapping.md", target_tier_mapping_report())
    write_text(output / "portfolio_contribution_schema.md", portfolio_contribution_schema_report())
    write_text(output / "stretch_diagnostic_schema.md", stretch_diagnostic_schema_report())
    write_text(output / "risk_integrity_schema.md", schema_markdown("risk_integrity_score"))
    write_text(output / "overfit_risk_schema.md", schema_markdown("overfit_risk_score"))
    write_text(output / "practicality_schema.md", schema_markdown("practicality_score"))
    write_text(output / "status_taxonomy_validation.md", status_taxonomy_validation_md())
    write_text(output / "data_preflight_report.md", preflight_report(preflight_universe_availability(root)))
    write_text(output / "do_not_run_batch_now.md", do_not_run_md())
    write_text(output / "revised_objective_sandbox_implementation_next_action.md", next_action_md(next_action))

    batch_hashes_after = batch_result_hashes(root)
    variant_hashes_after = variant_status_hashes(root)
    audit_hashes_after = audit_hashes(root)
    after_strategies = strategy_snapshot(root)
    manifest = {
        "created_utc": created_utc,
        "output_dir": str(output.resolve()),
        **MANIFEST_FLAGS,
        "planned_variant_count": len(rows),
        "planned_family_count": len(family_ids),
        "planned_max_variants": max_variants,
        "max_variants_per_family": MAX_VARIANTS_PER_FAMILY,
        "max_parameter_choices_per_indicator": MAX_PARAMETER_CHOICES_PER_INDICATOR,
        "max_portfolio_combination_variants": MAX_PORTFOLIO_COMBINATION_VARIANTS,
        "included_families": family_ids,
        "excluded_families": list(EXCLUDED_FAMILIES),
        "old_dollar_target_is_hard_gate": OLD_DOLLAR_TARGET_IS_HARD_GATE,
        "stretch_diagnostics_are_promotion_gates": STRETCH_DIAGNOSTICS_ARE_PROMOTION_GATES,
        "sandbox_results_can_promote": SANDBOX_RESULTS_CAN_PROMOTE,
        "paper_candidates_can_be_created": PAPER_CANDIDATES_CAN_BE_CREATED,
        "forbidden_statuses_blocked": forbidden_statuses_blocked(),
        "sandbox_results_changed": batch_hashes_before != batch_hashes_after,
        "variant_statuses_changed": variant_hashes_before != variant_hashes_after,
        "family_audit_changed": audit_hashes_before != audit_hashes_after,
        "next_action": next_action,
    }
    if before_strategies != after_strategies:
        manifest["active_strategy_state_changed"] = True
        manifest["rejected_strategy_state_changed"] = True

    manifest["registry_metadata_updated"] = False
    manifest["roadmap_updated"] = False
    manifest["compact_state_updated"] = False
    if update_project_metadata:
        registry_updated, roadmap_updated, compact_updated = update_metadata(root, output, created_utc, manifest)
        manifest["registry_metadata_updated"] = registry_updated
        manifest["roadmap_updated"] = roadmap_updated
        manifest["compact_state_updated"] = compact_updated

    write_text(output / "revised_objective_sandbox_implementation_summary.md", summary_md(manifest))
    write_json(output / "revised_objective_sandbox_implementation_manifest.json", manifest)
    write_json(output / "revised_objective_sandbox_implementation_consistency_check.json", {"consistency_passed": False})
    consistency = consistency_check(manifest, output)
    write_json(output / "revised_objective_sandbox_implementation_manifest.json", manifest)
    write_json(output / "revised_objective_sandbox_implementation_consistency_check.json", consistency)

    return {
        "output_dir": str(output),
        "batch_id": batch_id,
        "planned_variant_count": manifest["planned_variant_count"],
        "planned_family_count": manifest["planned_family_count"],
        "planned_max_variants": manifest["planned_max_variants"],
        "forbidden_statuses_blocked": manifest["forbidden_statuses_blocked"],
        "next_action": manifest["next_action"],
        "consistency_passed": consistency["consistency_passed"],
    }


def run_revised_objective_sandbox_implementation(root: Path = ROOT) -> dict[str, Any]:
    return run_revised_objective_sandbox_dry_run(
        root,
        batch_id=BATCH_ID,
        max_variants=MAX_TOTAL_VARIANTS,
        update_project_metadata=True,
    )


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def load_revised_dry_run_plan(root: Path) -> list[dict[str, str]]:
    return read_csv_rows(root / OUTPUT_DIR / "batch_002_dry_run_variant_plan.csv")


def coerce_float(value: Any, default: float = 0.0) -> float:
    number = safe_float(value)
    if math.isnan(number) or math.isinf(number):
        return default
    return number


def clamp_score(value: float, lower: float = 0.0, upper: float = 100.0) -> float:
    if math.isnan(value) or math.isinf(value):
        return lower
    return float(max(lower, min(upper, value)))


def bool_string(value: Any) -> bool:
    return str(value).strip().lower() == "true"


def symbols_by_universe_group(root: Path) -> dict[str, list[str]]:
    rows = preflight_universe_availability(root)
    return {str(row["universe_group"]): [str(symbol).upper() for symbol in row["symbols_found"]] for row in rows}


def parameter_profile_params(indicator: str, profile: str) -> dict[str, Any]:
    choices = PARAMETER_CHOICES_BY_INDICATOR.get(indicator)
    if not choices:
        raise ValueError(f"parameter choices missing for indicator: {indicator}")
    suffix = str(profile).rsplit("_", 1)[-1]
    try:
        index = int(suffix) - 1
    except ValueError as exc:
        raise ValueError(f"invalid parameter profile: {profile}") from exc
    if index < 0 or index >= len(choices):
        raise ValueError(f"parameter profile exceeds preregistered choices: {profile}")
    return dict(choices[index])


def revised_batch_preflight(root: Path, plan_rows: list[dict[str, str]], max_variants: int) -> dict[str, Any]:
    registry = load_yaml(root / REGISTRY_PATH)
    metadata = registry.get("registry", {})
    implementation_manifest = read_json(root / OUTPUT_DIR / "revised_objective_sandbox_implementation_manifest.json")
    universe_rows = preflight_universe_availability(root)
    universe_map = {str(row["universe_group"]): row for row in universe_rows}
    failures: list[str] = []
    warnings: list[str] = []

    expected_next = "run_revised_objective_sandbox_batch"
    if metadata.get("current_next_action") != expected_next or metadata.get("official_current_next_action") != expected_next:
        failures.append("registry current/official next action is not run_revised_objective_sandbox_batch")
    if implementation_manifest.get("next_action") != expected_next:
        failures.append("implementation manifest does not authorize revised-objective sandbox batch")
    if implementation_manifest.get("batch_id") != BATCH_ID:
        failures.append("implementation manifest batch id mismatch")
    if not plan_rows:
        failures.append("dry-run variant plan is missing")
    if len(plan_rows) != 80:
        failures.append(f"planned variant count expected 80, found {len(plan_rows)}")
    if len(plan_rows) > max_variants or len(plan_rows) > MAX_TOTAL_VARIANTS:
        failures.append("planned variant count exceeds authorized revised-objective limit")

    family_ids = sorted({str(row.get("family_id", "")) for row in plan_rows})
    if tuple(family_ids) != tuple(sorted(INCLUDED_FAMILIES)):
        failures.append("included families do not match preregistration")
    if len(family_ids) != MAX_FAMILIES:
        failures.append(f"planned family count expected {MAX_FAMILIES}, found {len(family_ids)}")
    excluded_seen = sorted(set(family_ids) & set(EXCLUDED_FAMILIES))
    if excluded_seen:
        failures.append(f"excluded families present in dry-run plan: {excluded_seen}")

    forbidden_seen = sorted({row.get("status", "") for row in plan_rows if row.get("status", "") in FORBIDDEN_STATUSES})
    if forbidden_seen:
        failures.append(f"forbidden statuses present in dry-run plan: {forbidden_seen}")
    for row in plan_rows:
        variant_id = row.get("variant_id", "<unknown>")
        if row.get("batch_id") != BATCH_ID:
            failures.append(f"variant has wrong batch id: {variant_id}")
        if row.get("promotable") != "false":
            failures.append(f"variant is promotable: {variant_id}")
        if row.get("paper_candidate_allowed") != "false":
            failures.append(f"variant can create paper candidate: {variant_id}")
        if row.get("status") != INITIAL_STATUS:
            failures.append(f"variant status is not non_promotable_exploration: {variant_id}")
        if row.get("old_dollar_target_is_hard_gate") != "false":
            failures.append(f"old dollar target encoded as hard gate: {variant_id}")
        if row.get("stretch_diagnostics_are_promotion_gates") != "false":
            failures.append(f"stretch diagnostics encoded as promotion gate: {variant_id}")
        group_id = str(row.get("universe_group", ""))
        universe = universe_map.get(group_id)
        if not universe or not universe.get("eligible_for_future_sandbox_run"):
            failures.append(f"local approved/cache-present daily data insufficient for universe group: {group_id}")
        elif int(universe.get("row_count", 0)) < 180:
            warnings.append(f"limited daily history for universe group: {group_id}")

    try:
        refs = reference_returns(root)
        for ref_id in ("SPY", "QQQ", "BIL", "active_vm", "active_dsr", "active_combo", "static_all_weather"):
            if ref_id not in refs or refs[ref_id].empty:
                failures.append(f"reference return series unavailable: {ref_id}")
    except Exception as exc:
        failures.append(f"reference return preflight failed: {exc}")

    if metadata.get("intraday_research_remains_paused") is not True:
        failures.append("intraday is not marked paused in registry")
    strategy_ids = {str(row.get("id", "")) for row in registry.get("strategies", [])}
    for strategy_id in (
        "paper_forward_vm_quality_lowvol_proxy_v1",
        "paper_forward_dsr_sector_equal_weight_defensive_filter_v1",
    ):
        if strategy_id not in strategy_ids:
            failures.append(f"active/frozen observation missing from registry: {strategy_id}")
    if "static_all_weather_benchmark_v1" not in strategy_ids and metadata.get("static_all_weather_benchmark_control_status") != "benchmark_control_accepted":
        warnings.append("static_all_weather_benchmark_v1 not explicitly listed as benchmark/control in registry")

    exact_rejected_reopened = [
        str(row.get("id", ""))
        for row in registry.get("strategies", [])
        if str(row.get("id", "")).startswith("mfv_")
        and (row.get("paper_forward_active") is True or str(row.get("status", "")).startswith("active"))
    ]
    if exact_rejected_reopened:
        failures.append(f"exact rejected managed-futures variants appear reopened: {exact_rejected_reopened}")

    return {
        "preflight_passed": not failures,
        "failures": sorted(set(failures)),
        "warnings": sorted(set(warnings)),
        "variant_count_planned": len(plan_rows),
        "family_count_planned": len(family_ids),
        "included_families": family_ids,
        "excluded_families": list(EXCLUDED_FAMILIES),
        "max_variants_requested": max_variants,
        "old_dollar_target_is_hard_gate": OLD_DOLLAR_TARGET_IS_HARD_GATE,
        "stretch_diagnostics_are_promotion_gates": STRETCH_DIAGNOSTICS_ARE_PROMOTION_GATES,
        "provider_download_required": False,
        "intraday_research_remains_paused": metadata.get("intraday_research_remains_paused") is True,
        "data_preflight_rows": universe_rows,
    }


def revised_variant_returns(
    root: Path,
    row: dict[str, str],
    refs: dict[str, pd.Series],
    universe_symbols: dict[str, list[str]],
) -> dict[str, Any]:
    group_id = str(row["universe_group"])
    symbols = universe_symbols.get(group_id, [])
    if len(symbols) < 2:
        raise ValueError(f"insufficient local symbols for universe group: {group_id}")
    symbols = symbols[: min(len(symbols), 8)]
    prices = price_frame(root, symbols)
    asset_returns = prices.pct_change().fillna(0.0)
    bil = refs["BIL"].reindex(asset_returns.index).fillna(0.0)
    indicator = str(row["indicator_concepts"])
    params = parameter_profile_params(indicator, str(row["parameter_profile"]))
    score = score_frame(str(row["family_id"]), indicator, params, prices)

    top_n = 1 if row.get("variant_role") in {"low_correlation_sleeve", "risk_buffer_probe"} else 2
    if row.get("family_id") == "macro_portfolio_contribution":
        top_n = 2
    weights = weights_from_score(score, str(row["family_id"]), top_n=top_n)
    cash_weight = (1.0 - weights.sum(axis=1)).clip(lower=0.0, upper=1.0)
    shifted_weights = weights.shift(1).fillna(0.0)
    shifted_cash = cash_weight.shift(1).fillna(1.0)
    sleeve_returns = ((shifted_weights * asset_returns).sum(axis=1) + shifted_cash * bil).rename("sleeve_returns")

    strategy_returns = sleeve_returns.rename(str(row["variant_id"]))
    if row.get("family_id") == "portfolio_combination_sleeve_ensemble":
        active_combo = refs["active_combo"].reindex(strategy_returns.index).fillna(0.0)
        aligned = pd.concat([sleeve_returns, active_combo], axis=1, join="inner").dropna()
        strategy_returns = (aligned.iloc[:, 0] * 0.35 + aligned.iloc[:, 1] * 0.65).rename(str(row["variant_id"]))

    turnover = weights.diff().abs().sum(axis=1).fillna(0.0)
    trade_count = int((turnover > 0.01).sum())
    avg_turnover = float(turnover.mean()) if len(turnover) else 0.0
    avg_cash = float(cash_weight.mean()) if len(cash_weight) else 1.0
    max_symbol_weight = float(weights.max(axis=1).max()) if not weights.empty else 0.0
    avg_symbols_held = float((weights > 0).sum(axis=1).mean()) if not weights.empty else 0.0
    return {
        "returns": strategy_returns.dropna(),
        "sleeve_returns": sleeve_returns.reindex(strategy_returns.index).fillna(0.0),
        "symbols": ",".join(symbols),
        "parameter_set": json.dumps(params, sort_keys=True),
        "trade_count": trade_count,
        "avg_turnover": avg_turnover,
        "avg_cash_allocation": avg_cash,
        "max_symbol_weight": max_symbol_weight,
        "avg_symbols_held": avg_symbols_held,
        "start_date": strategy_returns.index.min().date().isoformat(),
        "end_date": strategy_returns.index.max().date().isoformat(),
        "data_window_length": int(strategy_returns.shape[0]),
    }


def portfolio_contribution_metrics(variant_returns_series: pd.Series, refs: dict[str, pd.Series]) -> dict[str, float]:
    active_combo = refs["active_combo"]
    active_vm = refs["active_vm"]
    active_dsr = refs["active_dsr"]
    static_all_weather = refs["static_all_weather"]
    active_pair = pd.concat([active_vm, active_dsr], axis=1, join="inner").dropna().mean(axis=1).rename("active_pair")
    aligned = pd.concat([variant_returns_series, active_combo, active_pair, static_all_weather], axis=1, join="inner").dropna()
    if aligned.empty:
        return {
            "portfolio_return_risk_improvement": float("nan"),
            "active_combo_improvement": float("nan"),
            "correlation_reduction": float("nan"),
            "drawdown_contribution": float("nan"),
            "volatility_contribution": float("nan"),
            "return_drag_penalty": float("nan"),
            "contribution_vs_static_all_weather_control": float("nan"),
            "duplicate_penalty": float("nan"),
            "portfolio_level_risk_adjusted_improvement": float("nan"),
        }

    variant = aligned.iloc[:, 0]
    combo = aligned.iloc[:, 1]
    active_pair_returns = aligned.iloc[:, 2]
    static_returns = aligned.iloc[:, 3]
    blended = (combo * 0.80 + variant * 0.20).rename("active_combo_plus_sleeve")
    combo_metrics = metrics_for_returns(combo)
    blended_metrics = metrics_for_returns(blended)
    pair_metrics = metrics_for_returns(active_pair_returns)
    static_metrics = metrics_for_returns(static_returns)
    corr = float(variant.corr(combo)) if len(aligned) > 2 else float("nan")
    return {
        "portfolio_return_risk_improvement": coerce_float(blended_metrics["sharpe"] - combo_metrics["sharpe"]),
        "active_combo_improvement": coerce_float(
            blended_metrics["180d_median_final_equity"] - combo_metrics["180d_median_final_equity"]
        ),
        "active_vm_dsr_pair_improvement": coerce_float(
            blended_metrics["180d_median_final_equity"] - pair_metrics["180d_median_final_equity"]
        ),
        "correlation_reduction": coerce_float(1.0 - abs(corr), 0.0),
        "drawdown_contribution": coerce_float(blended_metrics["max_drawdown"] - combo_metrics["max_drawdown"]),
        "volatility_contribution": coerce_float(combo_metrics["volatility"] - blended_metrics["volatility"]),
        "return_drag_penalty": max(0.0, coerce_float(combo_metrics["total_return"] - blended_metrics["total_return"])),
        "contribution_vs_static_all_weather_control": coerce_float(
            blended_metrics["180d_median_final_equity"] - static_metrics["180d_median_final_equity"]
        ),
        "duplicate_penalty": coerce_float(max(0.0, abs(corr) - 0.80) * 100.0, 0.0),
        "portfolio_level_risk_adjusted_improvement": coerce_float(blended_metrics["sharpe"] - combo_metrics["sharpe"]),
    }


def standalone_growth_score(metrics: dict[str, Any], active_combo_delta: dict[str, float], duplicate_penalty: float) -> float:
    progress = (coerce_float(metrics.get("180d_median_final_equity"), STARTING_EQUITY) - STARTING_EQUITY) / 4.0
    ending = (coerce_float(metrics.get("ending_equity"), STARTING_EQUITY) - STARTING_EQUITY) / 12.0
    sharpe = 12.0 + coerce_float(metrics.get("sharpe")) * 8.0
    drawdown = coerce_float(metrics.get("risk_buffer_vs_minus_600")) / 12.0
    benchmark = coerce_float(active_combo_delta.get("delta_180d_median_final_equity")) / 8.0
    return clamp_score(35.0 + progress + ending + sharpe + drawdown + benchmark - duplicate_penalty * 0.20)


def portfolio_contribution_score(contrib: dict[str, float]) -> float:
    return clamp_score(
        45.0
        + coerce_float(contrib.get("active_combo_improvement")) / 5.0
        + coerce_float(contrib.get("active_vm_dsr_pair_improvement")) / 8.0
        + coerce_float(contrib.get("portfolio_return_risk_improvement")) * 12.0
        + coerce_float(contrib.get("correlation_reduction")) * 12.0
        + coerce_float(contrib.get("drawdown_contribution")) / 12.0
        + coerce_float(contrib.get("volatility_contribution")) * 120.0
        - coerce_float(contrib.get("return_drag_penalty")) * 50.0
        - coerce_float(contrib.get("duplicate_penalty")) * 0.30
    )


def stretch_diagnostic_score(metrics: dict[str, Any], active_combo_delta: dict[str, float], contrib: dict[str, float]) -> float:
    return clamp_score(
        coerce_float(metrics.get("target_300_before_stop_rate")) * 25.0
        + coerce_float(metrics.get("target_400_before_stop_rate")) * 25.0
        + (15.0 if coerce_float(active_combo_delta.get("delta_180d_median_final_equity")) > 0 else 0.0)
        + (20.0 if coerce_float(contrib.get("portfolio_level_risk_adjusted_improvement")) > 0 else 0.0)
    )


def risk_integrity_score(metrics: dict[str, Any]) -> float:
    buffer_score = coerce_float(metrics.get("risk_buffer_vs_minus_600")) / 7.5
    max_dd_penalty = max(0.0, -coerce_float(metrics.get("max_drawdown")) - 300.0) / 10.0
    rolling_dd_penalty = max(0.0, -coerce_float(metrics.get("180d_worst_drawdown")) - 250.0) / 10.0
    stop_penalty = coerce_float(metrics.get("stop_hit_rate")) * 30.0
    breach_penalty = 20.0 if metrics.get("stop_risk_breach_flag") else 0.0
    return clamp_score(45.0 + buffer_score - max_dd_penalty - rolling_dd_penalty - stop_penalty - breach_penalty)


def overfit_risk_score(row: dict[str, str], payload: dict[str, Any], corr_vs_combo: float) -> float:
    single_symbol_risk = max(0.0, coerce_float(payload.get("max_symbol_weight")) - 0.60) * 60.0
    limited_history = 20.0 if int(payload.get("data_window_length", 0)) < 500 else 0.0
    duplicate_risk = max(0.0, abs(coerce_float(corr_vs_combo)) - 0.80) * 55.0
    family_risk = 8.0 if row.get("family_id") in {"volatility_regime", "trend_momentum"} else 4.0
    profile_risk = 8.0 if str(row.get("parameter_profile", "")).endswith("_profile_4") else 3.0
    return clamp_score(18.0 + single_symbol_risk + limited_history + duplicate_risk + family_risk + profile_risk)


def practicality_score(payload: dict[str, Any]) -> float:
    turnover_penalty = min(35.0, coerce_float(payload.get("avg_turnover")) * 120.0)
    trade_penalty = min(25.0, coerce_float(payload.get("trade_count")) / 10.0)
    concentration_penalty = max(0.0, coerce_float(payload.get("max_symbol_weight")) - 0.70) * 25.0
    cash_bonus = min(10.0, coerce_float(payload.get("avg_cash_allocation")) * 8.0)
    return clamp_score(78.0 - turnover_penalty - trade_penalty - concentration_penalty + cash_bonus)


def assign_revised_result_status(result: dict[str, Any]) -> str:
    if bool(result.get("data_blocked")):
        return "sandbox_data_blocked"
    standalone = coerce_float(result.get("standalone_growth_score"))
    contribution = coerce_float(result.get("portfolio_contribution_score"))
    risk = coerce_float(result.get("risk_integrity_score"))
    overfit = coerce_float(result.get("overfit_risk_score"))
    stretch = coerce_float(result.get("stretch_diagnostic_score"))
    duplicate_penalty = coerce_float(result.get("duplicate_penalty"))
    if contribution >= 68.0 and risk >= 55.0 and overfit <= 60.0 and duplicate_penalty < 15.0:
        return assert_status_allowed("sandbox_portfolio_sleeve_candidate")
    if standalone >= 68.0 and risk >= 55.0 and overfit <= 60.0:
        return assert_status_allowed("sandbox_component_candidate")
    if max(standalone, contribution) >= 56.0 and risk >= 42.0:
        return assert_status_allowed("sandbox_family_interesting")
    if risk < 30.0 and stretch >= 35.0:
        return assert_status_allowed("sandbox_needs_objective_reset")
    if max(standalone, contribution, stretch) >= 35.0:
        return assert_status_allowed("sandbox_family_weak")
    return assert_status_allowed("sandbox_discard")


def evaluate_revised_variants(
    root: Path,
    plan_rows: list[dict[str, str]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    refs = reference_returns(root)
    universe_symbols = symbols_by_universe_group(root)
    variant_results: list[dict[str, Any]] = []
    benchmark_rows: list[dict[str, Any]] = []
    for row in plan_rows:
        try:
            payload = revised_variant_returns(root, row, refs, universe_symbols)
            returns = payload["returns"]
            metrics = metrics_for_returns(returns)
            active_combo_delta = aligned_metric_delta(returns, refs["active_combo"])
            contrib = portfolio_contribution_metrics(returns, refs)
            correlations = {name: aligned_metric_delta(returns, ref)["correlation"] for name, ref in refs.items()}
            result: dict[str, Any] = {
                **row,
                **{key: value for key, value in payload.items() if key not in {"returns", "sleeve_returns"}},
                **metrics,
                **contrib,
                "data_blocked": False,
                "block_reason": "",
                "promotable": "false",
                "paper_candidate_allowed": "false",
                "sandbox_results_can_promote": "false",
                "paper_candidates_can_be_created": "false",
                "delta_vs_active_combo_180d_median": active_combo_delta["delta_180d_median_final_equity"],
                "active_combo_180d_median_final_equity": active_combo_delta["ref_180d_median_final_equity"],
                "corr_vs_active_combo": correlations.get("active_combo"),
                "corr_vs_active_vm": correlations.get("active_vm"),
                "corr_vs_active_dsr": correlations.get("active_dsr"),
                "corr_vs_spy": correlations.get("SPY"),
                "corr_vs_qqq": correlations.get("QQQ"),
                "corr_vs_static_all_weather": correlations.get("static_all_weather"),
            }
            scores_v3 = score_row_v3(result, interpretation_status="usable_for_future_sandbox")
            result.update(scores_v3)
            result.update(
                {
                    "standalone_growth_score": scores_v3["standalone_growth_score_v3"],
                    "portfolio_contribution_score": scores_v3["portfolio_contribution_score_v3"],
                    "stretch_diagnostic_score": scores_v3["stretch_diagnostic_score_v3"],
                    "risk_integrity_score": scores_v3["risk_integrity_score_v3"],
                    "overfit_risk_score": scores_v3["overfit_risk_score_v3"],
                    "practicality_score": scores_v3["practicality_score_v3"],
                    "positive_180d_progress": coerce_float(metrics.get("180d_median_final_equity"), STARTING_EQUITY)
                    > STARTING_EQUITY,
                    "acceptable_drawdown_risk_integrity": scores_v3["risk_integrity_score_v3"] >= 55.0
                    and coerce_float(metrics.get("max_drawdown")) > -600.0
                    and coerce_float(metrics.get("180d_worst_drawdown")) > -600.0,
                    "useful_contribution_evidence": scores_v3["portfolio_contribution_score_v3"] >= 65.0
                    and scores_v3["duplicate_penalty_v3"] < 20.0,
                    "high_overfit_risk": scores_v3["overfit_risk_score_v3"] >= 65.0,
                    "stretch_diagnostic_hit": scores_v3["stretch_diagnostic_score_v3"] >= 35.0,
                }
            )
            result["status"] = assign_revised_result_status(result)
            variant_results.append(result)
            for benchmark_id, ref in refs.items():
                comparison = aligned_metric_delta(returns, ref)
                benchmark_rows.append(
                    {
                        "variant_id": row["variant_id"],
                        "family_id": row["family_id"],
                        "benchmark_id": benchmark_id,
                        "correlation": comparison["correlation"],
                        "delta_180d_median_final_equity": comparison["delta_180d_median_final_equity"],
                        "benchmark_180d_median_final_equity": comparison["ref_180d_median_final_equity"],
                    }
                )
        except Exception as exc:
            blocked = {
                **row,
                "data_blocked": True,
                "block_reason": str(exc),
                "status": "sandbox_data_blocked",
                "promotable": "false",
                "paper_candidate_allowed": "false",
                "sandbox_results_can_promote": "false",
                "paper_candidates_can_be_created": "false",
            }
            assert_status_allowed(blocked["status"])
            variant_results.append(blocked)
    return variant_results, benchmark_rows


def median_numeric(frame: pd.DataFrame, column: str) -> float:
    if column not in frame:
        return float("nan")
    return safe_float(pd.to_numeric(frame[column], errors="coerce").median())


def max_numeric(frame: pd.DataFrame, column: str) -> float:
    if column not in frame:
        return float("nan")
    return safe_float(pd.to_numeric(frame[column], errors="coerce").max())


def min_numeric(frame: pd.DataFrame, column: str) -> float:
    if column not in frame:
        return float("nan")
    return safe_float(pd.to_numeric(frame[column], errors="coerce").min())


def family_interpretation(family_id: str, row: dict[str, Any]) -> str:
    if row["family_status"] == "sandbox_data_blocked":
        return "Data availability blocked interpretation; do not infer opportunity."
    if family_id == "breakout_continuation":
        return "Contribution-aware review shows whether low-correlation behavior pays enough to overcome return drag."
    if family_id == "portfolio_combination_sleeve_ensemble":
        return "Review centers on active-combo duplication penalties and measurable portfolio-level improvement."
    if family_id == "volatility_regime":
        return "High-upside evidence remains diagnostic unless risk integrity improves across the family."
    if family_id == "trend_momentum":
        return "Positive rows must clear drawdown and overfit checks before any future preregistration is credible."
    if family_id == "macro_portfolio_contribution":
        return "Useful primarily as contribution or benchmark context unless portfolio improvement is measurable."
    return "Exploratory family interpretation requires audit."


def family_summaries_revised(variant_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    frame = pd.DataFrame(variant_results)
    rows: list[dict[str, Any]] = []
    if frame.empty:
        return rows
    for family_id, group in frame.groupby("family_id", sort=True):
        evaluated = group[group["status"] != "sandbox_data_blocked"].copy()
        if evaluated.empty:
            best_standalone = group.iloc[0]
            best_contribution = group.iloc[0]
        else:
            best_standalone = evaluated.sort_values("standalone_growth_score", ascending=False).iloc[0]
            best_contribution = evaluated.sort_values("portfolio_contribution_score", ascending=False).iloc[0]
        variant_count = int(len(group))
        data_blocked_count = int((group["status"] == "sandbox_data_blocked").sum())
        positive_count = int(group.get("positive_180d_progress", pd.Series(dtype=bool)).fillna(False).sum())
        risk_count = int(group.get("acceptable_drawdown_risk_integrity", pd.Series(dtype=bool)).fillna(False).sum())
        contribution_count = int(group.get("useful_contribution_evidence", pd.Series(dtype=bool)).fillna(False).sum())
        overfit_count = int(group.get("high_overfit_risk", pd.Series(dtype=bool)).fillna(False).sum())
        stretch_count = int(group.get("stretch_diagnostic_hit", pd.Series(dtype=bool)).fillna(False).sum())
        component_count = int((group["status"] == "sandbox_component_candidate").sum())
        sleeve_count = int((group["status"] == "sandbox_portfolio_sleeve_candidate").sum())

        family_status = "sandbox_family_weak"
        if data_blocked_count == variant_count:
            family_status = "sandbox_data_blocked"
        elif (component_count + sleeve_count) >= 3 and risk_count >= max(3, variant_count // 3) and overfit_count <= variant_count // 2:
            family_status = "sandbox_future_preregistration_candidate"
        elif sleeve_count:
            family_status = "sandbox_portfolio_sleeve_candidate"
        elif component_count:
            family_status = "sandbox_component_candidate"
        elif (
            median_numeric(evaluated, "standalone_growth_score") >= 48.0
            or median_numeric(evaluated, "portfolio_contribution_score") >= 48.0
        ) and risk_count > 0:
            family_status = "sandbox_family_interesting"

        row = {
            "family_id": family_id,
            "family_status": assert_status_allowed(family_status),
            "variants_evaluated": variant_count,
            "data_blocked_variants": data_blocked_count,
            "median_standalone_growth_score": median_numeric(evaluated, "standalone_growth_score"),
            "median_portfolio_contribution_score": median_numeric(evaluated, "portfolio_contribution_score"),
            "median_risk_integrity_score": median_numeric(evaluated, "risk_integrity_score"),
            "median_overfit_risk_score": median_numeric(evaluated, "overfit_risk_score"),
            "median_practicality_score": median_numeric(evaluated, "practicality_score"),
            "best_variant_by_standalone_growth_score": best_standalone.get("variant_id", ""),
            "best_standalone_growth_score": best_standalone.get("standalone_growth_score", ""),
            "best_variant_by_portfolio_contribution_score": best_contribution.get("variant_id", ""),
            "best_portfolio_contribution_score": best_contribution.get("portfolio_contribution_score", ""),
            "positive_180d_progress_variants": positive_count,
            "acceptable_drawdown_risk_integrity_variants": risk_count,
            "useful_contribution_evidence_variants": contribution_count,
            "high_overfit_risk_variants": overfit_count,
            "stretch_diagnostic_hits": stretch_count,
            "family_level_interpretation": "",
            "actionable_now": False,
            "future_preregistration_candidate": family_status == "sandbox_future_preregistration_candidate",
        }
        row["family_level_interpretation"] = family_interpretation(family_id, row)
        rows.append(row)
    return rows


def aggregate_score_summary(rows: list[dict[str, Any]], score_column: str) -> list[dict[str, Any]]:
    frame = pd.DataFrame(rows)
    out: list[dict[str, Any]] = []
    if frame.empty:
        return out
    for family_id, group in frame.groupby("family_id", sort=True):
        out.append(
            {
                "family_id": family_id,
                "variants": len(group),
                f"median_{score_column}": median_numeric(group, score_column),
                f"best_{score_column}": max_numeric(group, score_column),
                f"worst_{score_column}": min_numeric(group, score_column),
            }
        )
    return out


def benchmark_revised_summary(benchmark_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    frame = pd.DataFrame(benchmark_rows)
    out: list[dict[str, Any]] = []
    if frame.empty:
        return out
    for (family_id, benchmark_id), group in frame.groupby(["family_id", "benchmark_id"], sort=True):
        out.append(
            {
                "family_id": family_id,
                "benchmark_id": benchmark_id,
                "variant_count": len(group),
                "median_delta_180d_median_final_equity": median_numeric(group, "delta_180d_median_final_equity"),
                "best_delta_180d_median_final_equity": max_numeric(group, "delta_180d_median_final_equity"),
                "median_correlation": median_numeric(group, "correlation"),
            }
        )
    return out


def md_batch_preflight(pre: dict[str, Any]) -> str:
    failures = "\n".join(f"- {item}" for item in pre["failures"]) or "- none"
    warnings = "\n".join(f"- {item}" for item in pre["warnings"]) or "- none"
    return f"""# Revised Objective Sandbox Batch Preflight Report

Preflight passed: `{pre['preflight_passed']}`

Batch ID: `{BATCH_ID}`

Variant count planned: `{pre['variant_count_planned']}`

Family count planned: `{pre['family_count_planned']}`

Included families: `{', '.join(pre['included_families']) or 'none'}`

Excluded families: `{', '.join(pre['excluded_families']) or 'none'}`

Old $300-$400 target is hard gate: `{pre['old_dollar_target_is_hard_gate']}`

Stretch diagnostics are promotion gates: `{pre['stretch_diagnostics_are_promotion_gates']}`

Provider download required: `{pre['provider_download_required']}`

Intraday remains paused: `{pre['intraday_research_remains_paused']}`

Failures:

{failures}

Warnings:

{warnings}

Local approved/cache-present daily data was checked. No provider data was downloaded.
"""


def md_batch_family_summary(family_rows: list[dict[str, Any]]) -> str:
    lines = ["# Batch 002 Family Summary", "", "All findings are sandbox-only and non-promotable.", ""]
    for row in family_rows:
        lines.extend(
            [
                f"## `{row['family_id']}`",
                f"- Family status: `{row['family_status']}`",
                f"- Variants evaluated: `{row['variants_evaluated']}`",
                f"- Data-blocked variants: `{row['data_blocked_variants']}`",
                f"- Median standalone growth score: `{row['median_standalone_growth_score']}`",
                f"- Median portfolio contribution score: `{row['median_portfolio_contribution_score']}`",
                f"- Median risk integrity score: `{row['median_risk_integrity_score']}`",
                f"- Median overfit risk score: `{row['median_overfit_risk_score']}`",
                f"- Median practicality score: `{row['median_practicality_score']}`",
                f"- Positive 180-day progress variants: `{row['positive_180d_progress_variants']}`",
                f"- Acceptable drawdown/risk-integrity variants: `{row['acceptable_drawdown_risk_integrity_variants']}`",
                f"- Useful contribution evidence variants: `{row['useful_contribution_evidence_variants']}`",
                f"- High overfit-risk variants: `{row['high_overfit_risk_variants']}`",
                f"- Stretch diagnostic hits: `{row['stretch_diagnostic_hits']}`",
                f"- Interpretation: {row['family_level_interpretation']}",
                "",
            ]
        )
    return "\n".join(lines)


def md_family_actionability(family_rows: list[dict[str, Any]]) -> str:
    lookup = {row["family_id"]: row for row in family_rows}
    def status(family_id: str) -> str:
        row = lookup.get(family_id, {})
        return str(row.get("family_status", "not_evaluated"))

    return f"""# Family Actionability Review

No family is directly promotable from this sandbox batch.

## `breakout_continuation`

Question: Does this still only look like low-correlation/cash-heavy behavior, or does revised scoring reveal a credible sleeve?

Review status: `{status('breakout_continuation')}`. Contribution score, return drag, drawdown behavior, active-combo correlation, and portfolio-level effect are recorded for audit.

## `portfolio_combination_sleeve_ensemble`

Question: Does any combination improve active VM/DSR meaningfully, or is it still repackaging active combo?

Review status: `{status('portfolio_combination_sleeve_ensemble')}`. Active-combo duplicate penalties and correlation flags are explicit.

## `volatility_regime`

Question: Does it still show high-upside/high-risk behavior, or does a sub-family improve risk integrity enough to remain interesting?

Review status: `{status('volatility_regime')}`. Stretch diagnostics are recorded only as diagnostics and cannot make this actionable.

## `trend_momentum`

Question: Does risk-adjusted scoring identify robust trend behavior, or are positive rows still high-drawdown/parameter-sensitive variants?

Review status: `{status('trend_momentum')}`. Risk-integrity and overfit-risk fields are required before interpretation.

## `macro_portfolio_contribution`

Question: Does it provide measurable portfolio-level contribution, or is it only benchmark/control context?

Review status: `{status('macro_portfolio_contribution')}`. Contribution versus active VM/DSR, active combo, and static all-weather control is recorded.
"""


def md_future_preregistration_candidates(family_rows: list[dict[str, Any]]) -> str:
    candidates = [row for row in family_rows if row.get("future_preregistration_candidate")]
    lines = ["# Future Preregistration Candidates", ""]
    lines.append(f"Future preregistration candidate count: `{len(candidates)}`")
    lines.append("")
    if not candidates:
        lines.append("No family is ready to skip audit or move directly into formal discovery.")
    for row in candidates:
        lines.append(
            f"- `{row['family_id']}`: sandbox-only future-preregistration clue; separate preregistration is required before formal discovery."
        )
    lines.append("")
    lines.append("No promotion-review, candidate_exhaustive, paper-forward, demo-active, or live-ready status is created.")
    return "\n".join(lines)


def md_do_not_promote_revised() -> str:
    return """# Do Not Promote

All batch 002 outputs remain sandbox-only.

Forbidden from these results:

- promotion-review candidates
- candidate_exhaustive candidates
- paper-forward candidates
- paper-forward activation
- demo-active or live-ready labels
- broker/live-order paths
- real-money recommendations

Stretch diagnostics, best single rows, and high-return/high-drawdown rows cannot override risk, duplicate, overfit, benchmark, or governance failures.
"""


def md_batch_next_action(next_action: str) -> str:
    return f"""# Revised Objective Sandbox Batch Next Action

Exact next action: `{next_action}`

Do not run the next action in this batch execution task.
"""


def md_revised_batch_summary(manifest: dict[str, Any], family_rows: list[dict[str, Any]]) -> str:
    interesting = [
        row["family_id"]
        for row in family_rows
        if row["family_status"]
        in {"sandbox_family_interesting", "sandbox_component_candidate", "sandbox_portfolio_sleeve_candidate", "sandbox_future_preregistration_candidate"}
    ]
    weak = [row["family_id"] for row in family_rows if row["family_status"] in {"sandbox_family_weak", "sandbox_data_blocked"}]
    return f"""# Revised Objective Sandbox Batch 002 Summary

Sandbox batch run: `{manifest['sandbox_batch_run']}`

Batch ID: `{manifest['batch_id']}`

Variant count planned: `{manifest['variant_count_planned']}`

Variant count evaluated: `{manifest['variant_count_evaluated']}`

Families evaluated: `{manifest['family_count_evaluated']}`

Future preregistration candidate count: `{manifest['sandbox_future_preregistration_candidate_count']}`

Families interesting or candidate-like for audit: `{', '.join(interesting) or 'none'}`

Weak/data-blocked families: `{', '.join(weak) or 'none'}`

Families directly actionable now: `{manifest['families_actionable_count']}`

Next action: `{manifest['next_action']}`

All results remain non-promotable. No formal discovery, candidate_exhaustive, paper-forward action, provider download, intraday data, broker/live path, or real-money recommendation occurred.
"""


def decide_revised_batch_next_action(family_rows: list[dict[str, Any]], preflight_passed: bool) -> str:
    if not preflight_passed:
        return BATCH_NEXT_ACTION_MANUAL
    future_candidates = [row for row in family_rows if row.get("future_preregistration_candidate")]
    if len(future_candidates) == 1 and all(row.get("family_status") != "sandbox_family_interesting" for row in family_rows):
        return BATCH_NEXT_ACTION_FAMILY
    if family_rows and all(row["family_status"] in {"sandbox_family_weak", "sandbox_data_blocked"} for row in family_rows):
        return BATCH_NEXT_ACTION_OBSERVE
    return BATCH_NEXT_ACTION_AUDIT


def update_revised_batch_metadata(root: Path, output: Path, created_utc: str, manifest: dict[str, Any]) -> tuple[bool, bool, bool]:
    registry_path = root / REGISTRY_PATH
    registry = load_yaml(registry_path)
    metadata = registry.setdefault("registry", {})
    before_metadata = deepcopy(metadata)
    metadata.update(
        {
            "revised_objective_sandbox_batch_path": str(output.resolve()),
            "revised_objective_sandbox_batch_status": "completed_non_promotable_exploration",
            "revised_objective_sandbox_batch_created_utc": created_utc,
            "current_research_mode": "revised_objective_sandbox_batch_completed",
            "current_next_action": manifest["next_action"],
            "official_current_next_action": manifest["next_action"],
            "next_action": manifest["next_action"],
            "revised_objective_sandbox_batch_run": True,
            "revised_objective_sandbox_batch_id": manifest["batch_id"],
            "revised_objective_sandbox_variant_count_planned": manifest["variant_count_planned"],
            "revised_objective_sandbox_variant_count_evaluated": manifest["variant_count_evaluated"],
            "revised_objective_sandbox_family_count_evaluated": manifest["family_count_evaluated"],
            "revised_objective_sandbox_future_preregistration_candidate_count": manifest[
                "sandbox_future_preregistration_candidate_count"
            ],
            "revised_objective_sandbox_results_non_promotable": True,
            "revised_objective_sandbox_can_create_paper_candidates": False,
            "revised_objective_sandbox_formal_discovery_run": False,
            "revised_objective_sandbox_strategy_discovery_run": False,
            "revised_objective_sandbox_provider_download": False,
            "revised_objective_sandbox_intraday_data_used": False,
            "revised_objective_sandbox_candidate_exhaustive_run": False,
            "revised_objective_sandbox_paper_forward_action": False,
            "revised_objective_sandbox_real_money_recommendation": False,
            "intraday_research_remains_paused": True,
        }
    )
    registry_path.write_text(yaml.safe_dump(registry, sort_keys=False, width=120, allow_unicode=False), encoding="utf-8")

    roadmap_path = root / ROADMAP_PATH
    before_roadmap = roadmap_path.read_text(encoding="utf-8") if roadmap_path.exists() else "# Research Roadmap\n"
    compact_section = f"""## Compact Current State

- Updated UTC: `{created_utc}`
- Current research mode: `revised_objective_sandbox_batch_completed`
- Official current next action: `{manifest['next_action']}`
- Revised-objective sandbox batch evidence: `{output.resolve()}`
- Batch ID: `{manifest['batch_id']}`
- Variant count planned: `{manifest['variant_count_planned']}`
- Variant count evaluated: `{manifest['variant_count_evaluated']}`
- Families evaluated: `{manifest['family_count_evaluated']}`
- Future preregistration candidate count: `{manifest['sandbox_future_preregistration_candidate_count']}`
- Families actionable now: `{manifest['families_actionable_count']}`
- Old $300-$400 target is hard gate: `{manifest['old_dollar_target_is_hard_gate']}`
- Stretch diagnostics are promotion gates: `{manifest['stretch_diagnostics_are_promotion_gates']}`
- Sandbox results are non-promotable: `true`
- Sandbox cannot create paper candidates.
- Active VM and active DSR preserved.
- `static_all_weather_benchmark_v1` remains benchmark/control only.
- Exact rejected variants remain closed.
- Intraday remains paused: `true`
- This batch did not run formal discovery, candidate_exhaustive, paper-forward action, provider download, intraday data, broker/live path, or real-money recommendation.
"""
    section = f"""## Revised Objective Sandbox Batch 002

- Created UTC: `{created_utc}`
- Evidence path: `{output.resolve()}`
- Batch ID: `{manifest['batch_id']}`
- Sandbox batch run: `true`
- Variant count planned: `{manifest['variant_count_planned']}`
- Variant count evaluated: `{manifest['variant_count_evaluated']}`
- Families evaluated: `{manifest['family_count_evaluated']}`
- Future preregistration candidate count: `{manifest['sandbox_future_preregistration_candidate_count']}`
- Families directly actionable now: `{manifest['families_actionable_count']}`
- Best single variant promoted: `false`
- Next action: `{manifest['next_action']}`
- Do not run the next action in this batch task.
"""
    after_roadmap = replace_or_append_section(before_roadmap, "## Compact Current State", compact_section)
    after_roadmap = replace_or_append_section(after_roadmap, "## Revised Objective Sandbox Batch 002", section)
    write_text(roadmap_path, after_roadmap)

    compact_path = root / COMPACT_STATE_PATH
    before_compact = compact_path.read_text(encoding="utf-8") if compact_path.exists() else ""
    after_compact = f"""# Current Tournament State

Created UTC: `{created_utc}`

Current research mode: `revised_objective_sandbox_batch_completed`

Current next action: `{manifest['next_action']}`

Revised-objective sandbox batch evidence: `{output.resolve()}`

## Batch 002

- Batch ID: `{manifest['batch_id']}`
- Variant count planned: `{manifest['variant_count_planned']}`
- Variant count evaluated: `{manifest['variant_count_evaluated']}`
- Families evaluated: `{manifest['family_count_evaluated']}`
- Future preregistration candidate count: `{manifest['sandbox_future_preregistration_candidate_count']}`
- Families actionable now: `{manifest['families_actionable_count']}`
- Sandbox results are non-promotable.
- Sandbox cannot create paper candidates.
- Single safest next action: `{manifest['next_action']}`

## Protected State

- `paper_forward_vm_quality_lowvol_proxy_v1` remains active/accepted/frozen.
- `paper_forward_dsr_sector_equal_weight_defensive_filter_v1` remains active/accepted/frozen.
- `static_all_weather_benchmark_v1` remains benchmark/control only.
- Exact rejected variants remain closed.
- Intraday research remains paused.

## Forbidden Actions

- No formal strategy discovery.
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


def revised_batch_consistency_check(manifest: dict[str, Any], output: Path) -> dict[str, Any]:
    rows = read_csv_rows(output / "batch_002_variant_results.csv")
    statuses = {row.get("status", "") for row in rows}
    check = {
        "sandbox_batch_run_mode": manifest["sandbox_batch_run"] is True,
        "batch_id_correct": manifest["batch_id"] == BATCH_ID,
        "no_formal_strategy_discovery": manifest["strategy_discovery_run"] is False and manifest["formal_discovery_run"] is False,
        "no_candidate_exhaustive": manifest["candidate_exhaustive_run"] is False,
        "no_paper_forward_action": manifest["paper_forward_review"] is False and manifest["paper_forward_activation"] is False,
        "no_provider_download": manifest["provider_download"] is False,
        "no_intraday_data_used": manifest["intraday_data_used"] is False,
        "no_indicator_library_dependency_added": manifest["indicator_library_dependency_added"] is False,
        "no_broker_live_action": manifest["broker_orders_submitted"] is False
        and manifest["broker_orders_cancelled"] is False
        and manifest["live_orders"] is False,
        "no_real_money_recommendation": manifest["real_money_recommendation"] is False,
        "active_strategy_state_preserved": manifest["active_strategy_state_changed"] is False,
        "rejected_strategy_state_preserved": manifest["rejected_strategy_state_changed"] is False,
        "exact_rejected_variants_not_reopened": manifest["exact_rejected_variants_reopened"] is False,
        "intraday_remains_paused": manifest["intraday_research_remains_paused"] is True,
        "old_dollar_target_is_not_hard_gate": manifest["old_dollar_target_is_hard_gate"] is False,
        "stretch_diagnostics_are_not_promotion_gates": manifest["stretch_diagnostics_are_promotion_gates"] is False,
        "variant_count_planned_bounded": manifest["variant_count_planned"] <= MAX_TOTAL_VARIANTS,
        "variant_count_evaluated_bounded": manifest["variant_count_evaluated"] <= MAX_TOTAL_VARIANTS,
        "every_result_allowed_status": statuses <= set(ALLOWED_RESULT_STATUSES),
        "forbidden_statuses_absent": not (statuses & set(FORBIDDEN_STATUSES)),
        "no_result_promotable": all(row.get("promotable") == "false" for row in rows),
        "no_result_paper_candidate_allowed": all(row.get("paper_candidate_allowed") == "false" for row in rows),
        "standalone_growth_score_summary_exists": (output / "standalone_growth_score_summary.csv").exists(),
        "portfolio_contribution_score_summary_exists": (output / "portfolio_contribution_score_summary.csv").exists(),
        "stretch_diagnostic_summary_exists": (output / "stretch_diagnostic_summary.csv").exists(),
        "risk_integrity_summary_exists": (output / "risk_integrity_summary.csv").exists(),
        "overfit_risk_summary_exists": (output / "overfit_risk_summary.csv").exists(),
        "practicality_summary_exists": (output / "practicality_summary.csv").exists(),
        "family_summary_exists": (output / "batch_002_family_summary.csv").exists(),
        "future_preregistration_candidates_file_exists": (output / "future_preregistration_candidates.md").exists(),
        "do_not_promote_file_exists": (output / "do_not_promote.md").exists(),
        "next_action_valid": manifest["next_action"] in BATCH_VALID_NEXT_ACTIONS,
        "manifest_flags_match_strict_scope": all(manifest.get(key) == value for key, value in BATCH_MANIFEST_FLAGS.items()),
        "required_files_exist": all((output / name).exists() for name in BATCH_REQUIRED_FILES),
    }
    check["consistency_passed"] = all(check.values())
    return check


def run_revised_objective_sandbox_batch(
    root: Path = ROOT,
    *,
    batch_id: str = BATCH_ID,
    max_variants: int = MAX_TOTAL_VARIANTS,
    update_project_metadata: bool = True,
) -> dict[str, Any]:
    if batch_id != BATCH_ID:
        raise ValueError(f"unexpected revised-objective batch id: {batch_id}")
    root = root.resolve()
    created_utc = now_utc()
    output = root / BATCH_OUTPUT_DIR
    output.mkdir(parents=True, exist_ok=True)
    before_strategies = strategy_snapshot(root)
    plan_rows = load_revised_dry_run_plan(root)
    preflight = revised_batch_preflight(root, plan_rows, max_variants)
    variant_results: list[dict[str, Any]] = []
    benchmark_rows: list[dict[str, Any]] = []
    family_rows: list[dict[str, Any]] = []
    if preflight["preflight_passed"]:
        validate_variant_plan(plan_rows, batch_id=batch_id, max_variants=max_variants)
        variant_results, benchmark_rows = evaluate_revised_variants(root, plan_rows[:max_variants])
        family_rows = family_summaries_revised(variant_results)

    next_action = decide_revised_batch_next_action(family_rows, preflight["preflight_passed"])
    after_strategies = strategy_snapshot(root)
    future_count = sum(1 for row in family_rows if row.get("future_preregistration_candidate"))
    interesting_count = sum(
        1
        for row in family_rows
        if row.get("family_status")
        in {"sandbox_family_interesting", "sandbox_component_candidate", "sandbox_portfolio_sleeve_candidate", "sandbox_future_preregistration_candidate"}
    )
    actionable_count = 0
    manifest = {
        "created_utc": created_utc,
        "output_dir": str(output.resolve()),
        **BATCH_MANIFEST_FLAGS,
        "batch_id": batch_id,
        "variant_count_planned": preflight["variant_count_planned"],
        "variant_count_evaluated": len(variant_results),
        "family_count_evaluated": len({row.get("family_id") for row in variant_results}),
        "sandbox_future_preregistration_candidate_count": future_count,
        "families_interesting_count": interesting_count,
        "families_actionable_count": actionable_count,
        "preflight_passed": preflight["preflight_passed"],
        "preflight_failures": preflight["failures"],
        "preflight_warnings": preflight["warnings"],
        "included_families": list(INCLUDED_FAMILIES),
        "excluded_families": list(EXCLUDED_FAMILIES),
        "next_action": next_action,
    }
    if before_strategies != after_strategies:
        manifest["active_strategy_state_changed"] = True
        manifest["rejected_strategy_state_changed"] = True

    write_text(output / "batch_preflight_report.md", md_batch_preflight(preflight))

    result_fields = [
        "variant_id",
        "batch_id",
        "family_id",
        "objective_lane",
        "variant_role",
        "universe_group",
        "symbols",
        "indicator_concepts",
        "parameter_profile",
        "parameter_set",
        "status",
        "promotable",
        "paper_candidate_allowed",
        "sandbox_results_can_promote",
        "paper_candidates_can_be_created",
        "standalone_growth_score",
        "portfolio_contribution_score",
        "stretch_diagnostic_score",
        "risk_integrity_score",
        "overfit_risk_score",
        "practicality_score",
        "standalone_growth_score_v2",
        "portfolio_contribution_score_v2",
        "stretch_diagnostic_score_v2",
        "risk_integrity_score_v2",
        "overfit_risk_score_v2",
        "practicality_score_v2",
        "cash_allocation_penalty",
        "underinvestment_penalty",
        "exposure_quality_score",
        "active_combo_delta_penalty",
        "active_reference_lag_penalty",
        "benchmark_lag_penalty",
        "return_drag_penalty_v2",
        "contribution_net_of_drag_score",
        "risk_integrity_gate",
        "risk_adjusted_growth_score",
        "drawdown_quality_score",
        "duplicate_penalty_v2",
        "active_combo_duplicate_penalty",
        "correlation_adjusted_contribution_score",
        "turnover_penalty",
        "trade_count_penalty",
        "inactivity_penalty",
        "limited_history_penalty",
        "data_quality_score",
        "score_saturation_flag",
        "score_interpretation_status",
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
        "ending_equity",
        "total_return",
        "annualized_return",
        "volatility",
        "sharpe",
        "max_drawdown",
        "max_drawdown_pct",
        "risk_buffer_vs_minus_600",
        "stop_risk_breach_flag",
        "180d_median_final_equity",
        "180d_mean_final_equity",
        "180d_worst_final_equity",
        "180d_worst_drawdown",
        "target_300_before_stop_rate",
        "target_400_before_stop_rate",
        "stop_hit_rate",
        "delta_vs_active_combo_180d_median",
        "active_combo_180d_median_final_equity",
        "portfolio_return_risk_improvement",
        "active_combo_improvement",
        "active_vm_dsr_pair_improvement",
        "correlation_reduction",
        "drawdown_contribution",
        "volatility_contribution",
        "return_drag_penalty",
        "contribution_vs_static_all_weather_control",
        "duplicate_penalty",
        "portfolio_level_risk_adjusted_improvement",
        "corr_vs_active_combo",
        "corr_vs_active_vm",
        "corr_vs_active_dsr",
        "corr_vs_spy",
        "corr_vs_qqq",
        "corr_vs_static_all_weather",
        "trade_count",
        "avg_turnover",
        "avg_cash_allocation",
        "avg_symbols_held",
        "max_symbol_weight",
        "data_window_length",
        "start_date",
        "end_date",
        "positive_180d_progress",
        "acceptable_drawdown_risk_integrity",
        "useful_contribution_evidence",
        "high_overfit_risk",
        "stretch_diagnostic_hit",
        "data_blocked",
        "block_reason",
    ]
    write_csv(output / "batch_002_variant_results.csv", variant_results, result_fields)

    family_fields = [
        "family_id",
        "family_status",
        "variants_evaluated",
        "data_blocked_variants",
        "median_standalone_growth_score",
        "median_portfolio_contribution_score",
        "median_risk_integrity_score",
        "median_overfit_risk_score",
        "median_practicality_score",
        "best_variant_by_standalone_growth_score",
        "best_standalone_growth_score",
        "best_variant_by_portfolio_contribution_score",
        "best_portfolio_contribution_score",
        "positive_180d_progress_variants",
        "acceptable_drawdown_risk_integrity_variants",
        "useful_contribution_evidence_variants",
        "high_overfit_risk_variants",
        "stretch_diagnostic_hits",
        "family_level_interpretation",
        "actionable_now",
        "future_preregistration_candidate",
    ]
    write_csv(output / "batch_002_family_summary.csv", family_rows, family_fields)
    write_text(output / "batch_002_family_summary.md", md_batch_family_summary(family_rows))

    score_fields = ["family_id", "variants"]
    score_summary_files = {
        "standalone_growth_score": "standalone_growth_score_summary.csv",
        "portfolio_contribution_score": "portfolio_contribution_score_summary.csv",
        "stretch_diagnostic_score": "stretch_diagnostic_summary.csv",
        "risk_integrity_score": "risk_integrity_summary.csv",
        "overfit_risk_score": "overfit_risk_summary.csv",
        "practicality_score": "practicality_summary.csv",
    }
    for score_name, file_name in score_summary_files.items():
        rows = aggregate_score_summary(variant_results, score_name)
        write_csv(
            output / file_name,
            rows,
            score_fields + [f"median_{score_name}", f"best_{score_name}", f"worst_{score_name}"],
        )

    write_csv(
        output / "benchmark_comparison_summary.csv",
        benchmark_revised_summary(benchmark_rows),
        [
            "family_id",
            "benchmark_id",
            "variant_count",
            "median_delta_180d_median_final_equity",
            "best_delta_180d_median_final_equity",
            "median_correlation",
        ],
    )
    write_text(output / "family_actionability_review.md", md_family_actionability(family_rows))
    write_text(output / "future_preregistration_candidates.md", md_future_preregistration_candidates(family_rows))
    write_text(output / "do_not_promote.md", md_do_not_promote_revised())
    write_text(output / "revised_objective_sandbox_batch_next_action.md", md_batch_next_action(next_action))

    manifest["registry_metadata_updated"] = False
    manifest["roadmap_updated"] = False
    manifest["compact_state_updated"] = False
    if update_project_metadata:
        registry_updated, roadmap_updated, compact_updated = update_revised_batch_metadata(
            root, output, created_utc, manifest
        )
        manifest["registry_metadata_updated"] = registry_updated
        manifest["roadmap_updated"] = roadmap_updated
        manifest["compact_state_updated"] = compact_updated

    write_text(output / "revised_objective_sandbox_batch_summary.md", md_revised_batch_summary(manifest, family_rows))
    write_json(output / "revised_objective_sandbox_batch_manifest.json", manifest)
    write_json(output / "revised_objective_sandbox_batch_consistency_check.json", {"consistency_passed": False})
    consistency = revised_batch_consistency_check(manifest, output)
    write_json(output / "revised_objective_sandbox_batch_consistency_check.json", consistency)

    return {
        "output_dir": str(output),
        "batch_id": batch_id,
        "preflight_passed": preflight["preflight_passed"],
        "variant_count_planned": manifest["variant_count_planned"],
        "variant_count_evaluated": manifest["variant_count_evaluated"],
        "family_count_evaluated": manifest["family_count_evaluated"],
        "sandbox_future_preregistration_candidate_count": future_count,
        "families_actionable_count": actionable_count,
        "next_action": next_action,
        "consistency_passed": consistency["consistency_passed"],
    }
