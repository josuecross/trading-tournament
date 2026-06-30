from __future__ import annotations

import csv
import json
import zipfile
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from .sandbox_anti_overfit import ANTI_OVERFITTING_CONTROLS, anti_overfitting_report, assert_plan_non_promotable
from .sandbox_config import (
    MANIFEST_FLAGS,
    MAX_FAMILIES_PER_RUN,
    MAX_PARAMETER_CHOICES_PER_INDICATOR,
    MAX_PORTFOLIO_COMBINATION_VARIANTS,
    MAX_TOTAL_FUTURE_VARIANTS,
    MAX_UNIVERSE_GROUPS_PER_RUN,
    MAX_VARIANTS_PER_FAMILY,
    NEXT_ACTION_MANUAL_REVIEW,
    NEXT_ACTION_RUN_BATCH,
    OUTPUT_DIR,
    REGISTRY_PATH,
    REQUIRED_OUTPUT_FILES,
    ROADMAP_PATH,
    ROOT,
    SANDBOX_PRINCIPLE,
    VALID_NEXT_ACTIONS,
)
from .sandbox_data_preflight import preflight_report, preflight_universe_availability, universe_availability_report
from .sandbox_families import ALLOWED_FAMILIES, family_registry_report
from .sandbox_indicators import ALLOWED_INDICATORS, indicator_registry_report
from .sandbox_leverage_policy import leverage_policy_report
from .sandbox_schema import variant_schema_report
from .sandbox_scoring import SCORING_CATEGORIES, scoring_framework_report
from .sandbox_status_taxonomy import forbidden_statuses_blocked, status_taxonomy_report
from .sandbox_universes import UNIVERSE_GROUPS
from .sandbox_variant_generator import generate_variant_plan, validate_plan_limits


MODULE_PURPOSES = {
    "__init__.py": "Package export for dry-run planning and implementation evidence.",
    "sandbox_config.py": "Shared limits, flags, paths, and next-action labels.",
    "sandbox_schema.py": "Non-promotable variant specification schema and validation.",
    "sandbox_universes.py": "Allowed universe registry using local approved/cache-present symbols.",
    "sandbox_families.py": "Allowed sandbox family registry.",
    "sandbox_indicators.py": "Allowed custom-indicator registry and forbidden-indicator gates.",
    "sandbox_variant_generator.py": "Dry-run variant-plan generator with hard limit enforcement.",
    "sandbox_status_taxonomy.py": "Allowed and forbidden sandbox status taxonomy.",
    "sandbox_scoring.py": "Future scoring framework structure only; no score computation.",
    "sandbox_anti_overfit.py": "Anti-overfitting controls and non-promotable plan checks.",
    "sandbox_data_preflight.py": "Local cache metadata preflight only; no downloads.",
    "sandbox_leverage_policy.py": "Research-only leverage sensitivity metadata.",
    "sandbox_evidence.py": "Evidence, manifest, consistency check, and metadata update writer.",
}


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def strategy_snapshot(root: Path) -> list[dict[str, Any]]:
    return deepcopy(load_yaml(root / REGISTRY_PATH).get("strategies", []))


def replace_or_append_section(text: str, header: str, section: str) -> str:
    if header not in text:
        return text.rstrip() + "\n\n" + section.rstrip() + "\n"
    start = text.index(header)
    next_start = text.find("\n## ", start + len(header))
    if next_start == -1:
        return text[:start].rstrip() + "\n\n" + section.rstrip() + "\n"
    return text[:start].rstrip() + "\n\n" + section.rstrip() + "\n\n" + text[next_start + 1 :].lstrip()


def decide_next_action(plan_rows: int, implementation_safe: bool) -> str:
    if implementation_safe and plan_rows > 0:
        return NEXT_ACTION_RUN_BATCH
    return NEXT_ACTION_MANUAL_REVIEW


def implementation_summary(created_utc: str, output: Path, manifest: dict[str, Any]) -> str:
    return f"""# Exploratory Strategy Search Sandbox Implementation

Created UTC: `{created_utc}`

Evidence path: `{output.resolve()}`

Design principle: `{SANDBOX_PRINCIPLE}`

Implementation-only: `{manifest['sandbox_implementation_only']}`

Dry-run variant plan generated: `{manifest['variant_plan_generated']}`

Variant plan rows: `{manifest['variant_plan_rows']}`

Next action: `{manifest['next_action']}`

This infrastructure step did not run sandbox search, strategy discovery, trading backtests, performance metrics, provider downloads, intraday data, candidate validation, paper-forward actions, broker/live paths, or real-money recommendations.
"""


def module_report() -> str:
    lines = ["# Sandbox Module Report", ""]
    for module, purpose in MODULE_PURPOSES.items():
        lines.append(f"- `{module}`: {purpose}")
    return "\n".join(lines)


def do_not_run_results_report() -> str:
    return """# Sandbox Do Not Run Results

This implementation creates a dry-run variant plan only. It does not create strategy results.

Not run:

- sandbox search
- strategy discovery
- trading backtests
- performance metric computation
- provider download
- intraday data
- candidate_exhaustive
- paper-forward review or activation
- broker/live order path
- real-money recommendation
"""


def next_action_report(next_action: str) -> str:
    return f"""# Sandbox Implementation Next Action

Exact next action: `{next_action}`

Do not run the next action in this implementation task.
"""


def write_plan_csv(path: Path, plan: list[Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [item.to_row() for item in plan]
    fieldnames = [
        "variant_id",
        "family_id",
        "universe_group",
        "symbols",
        "indicator_concept",
        "parameter_set",
        "holding_period_type",
        "rebalance_frequency",
        "sandbox_status_initial",
        "status",
        "promotable",
        "paper_candidate_allowed",
        "leverage_policy",
        "notes",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_preflight_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "universe_group",
        "symbols_found",
        "symbols_missing",
        "local_cache_present",
        "approved_status",
        "earliest_date",
        "latest_date",
        "row_count",
        "limited_history_warning",
        "eligible_for_future_sandbox_run",
        "blocked_symbols_and_reason",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    **row,
                    "symbols_found": ",".join(row["symbols_found"]),
                    "symbols_missing": ",".join(row["symbols_missing"]),
                    "blocked_symbols_and_reason": ",".join(row["blocked_symbols_and_reason"]),
                }
            )


def update_registry_metadata(root: Path, output: Path, created_utc: str, manifest: dict[str, Any]) -> bool:
    path = root / REGISTRY_PATH
    registry = load_yaml(path)
    metadata = registry.setdefault("registry", {})
    before = deepcopy(metadata)
    metadata.update(
        {
            "exploratory_strategy_search_sandbox_implementation_path": str(output.resolve()),
            "exploratory_strategy_search_sandbox_implementation_status": "implemented_dry_run_ready",
            "exploratory_strategy_search_sandbox_implementation_created_utc": created_utc,
            "current_research_mode": "exploratory_strategy_search_sandbox_implemented",
            "current_next_action": manifest["next_action"],
            "official_current_next_action": manifest["next_action"],
            "next_action": manifest["next_action"],
            "sandbox_implementation_only": True,
            "sandbox_search_run": False,
            "sandbox_results_non_promotable": True,
            "sandbox_can_create_paper_candidates": False,
            "sandbox_variant_plan_generated": manifest["variant_plan_generated"],
            "sandbox_variant_plan_rows": manifest["variant_plan_rows"],
            "sandbox_max_total_future_variants": MAX_TOTAL_FUTURE_VARIANTS,
            "sandbox_allowed_family_count": len(ALLOWED_FAMILIES),
            "sandbox_allowed_universe_count": len(UNIVERSE_GROUPS),
            "sandbox_allowed_indicator_count": len(ALLOWED_INDICATORS),
            "sandbox_strategy_discovery_run": False,
            "sandbox_backtests_run": False,
            "sandbox_new_performance_metrics_computed": False,
            "sandbox_provider_download": False,
            "sandbox_intraday_data_used": False,
            "sandbox_candidate_exhaustive_run": False,
            "sandbox_paper_forward_review": False,
            "sandbox_paper_forward_activation": False,
            "sandbox_broker_orders_submitted": False,
            "sandbox_broker_orders_cancelled": False,
            "sandbox_live_orders": False,
            "sandbox_real_money_recommendation": False,
            "intraday_research_remains_paused": True,
        }
    )
    path.write_text(yaml.safe_dump(registry, sort_keys=False, width=120, allow_unicode=False), encoding="utf-8")
    return before != metadata


def update_roadmap(root: Path, output: Path, created_utc: str, manifest: dict[str, Any]) -> bool:
    path = root / ROADMAP_PATH
    before = path.read_text(encoding="utf-8") if path.exists() else "# Research Roadmap\n"
    compact = f"""## Compact Current State

- Updated UTC: `{created_utc}`
- Current research mode: `exploratory_strategy_search_sandbox_implemented`
- Official current next action: `{manifest['next_action']}`
- Exploratory sandbox implementation evidence: `{output.resolve()}`
- Design principle: `{SANDBOX_PRINCIPLE}`
- Sandbox implementation-only: `true`
- Sandbox search run: `false`
- Variant plan generated: `{manifest['variant_plan_generated']}`
- Variant plan rows: `{manifest['variant_plan_rows']}`
- Sandbox results are non-promotable: `true`
- Sandbox can create paper candidates: `false`
- Active VM and active DSR preserved.
- `static_all_weather_benchmark_v1` remains benchmark/control only.
- Exact rejected variants remain closed; old managed-futures top1/top2 rows remain historical context only.
- Intraday remains paused: `true`
- This implementation did not run discovery, trading backtests, new metrics, provider download, intraday data, candidate_exhaustive, paper-forward action, broker/live path, or real-money recommendation.
"""
    section = f"""## Exploratory Strategy Search Sandbox Implementation

- Created UTC: `{created_utc}`
- Evidence path: `{output.resolve()}`
- Sandbox-implementation-only: `true`
- Dry-run/plan-only mode created: `true`
- Variant plan generated: `{manifest['variant_plan_generated']}`
- Variant plan rows: `{manifest['variant_plan_rows']}`
- Max total future variants: `{MAX_TOTAL_FUTURE_VARIANTS}`
- Max families per future run: `{MAX_FAMILIES_PER_RUN}`
- Max variants per family: `{MAX_VARIANTS_PER_FAMILY}`
- Max parameter choices per indicator concept: `{MAX_PARAMETER_CHOICES_PER_INDICATOR}`
- Max universe groups per run: `{MAX_UNIVERSE_GROUPS_PER_RUN}`
- Max portfolio-combination variants: `{MAX_PORTFOLIO_COMBINATION_VARIANTS}`
- Forbidden statuses blocked by code: `{manifest['forbidden_statuses_blocked']}`
- Next action: `{manifest['next_action']}`
- Do not run the next action in this implementation task.
- No sandbox search, strategy discovery, trading backtest, performance metric computation, dependency install, provider download, intraday data, candidate_exhaustive, paper-forward action, broker/live path, or real-money recommendation occurred.
"""
    after = replace_or_append_section(before, "## Compact Current State", compact)
    after = replace_or_append_section(after, "## Exploratory Strategy Search Sandbox Implementation", section)
    write_text(path, after)
    return before != after


def consistency_check(manifest: dict[str, Any], output: Path, plan_rows: int) -> dict[str, Any]:
    plan_path = output / "sandbox_variant_plan_dry_run.csv"
    check = {
        "sandbox_implementation_only": manifest["sandbox_implementation_only"] is True,
        "sandbox_search_not_run": manifest["sandbox_search_run"] is False,
        "no_strategy_discovery": manifest["strategy_discovery_run"] is False,
        "no_backtests": manifest["backtests_run"] is False,
        "no_new_performance_metrics": manifest["new_performance_metrics_computed"] is False,
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
        "sandbox_results_non_promotable": manifest["sandbox_results_non_promotable"] is True,
        "sandbox_cannot_create_paper_candidates": manifest["sandbox_can_create_paper_candidates"] is False,
        "variant_plan_exists": plan_path.exists(),
        "variant_plan_rows_bounded": 0 < plan_rows <= MAX_TOTAL_FUTURE_VARIANTS,
        "hard_limits_enforced": manifest["hard_limits_enforced"] is True,
        "forbidden_statuses_blocked": manifest["forbidden_statuses_blocked"] is True,
        "allowed_family_count_is_7": manifest["allowed_family_count"] == 7,
        "allowed_universe_count_is_7": manifest["allowed_universe_count"] == 7,
        "allowed_indicator_count_is_12": manifest["allowed_indicator_count"] == 12,
        "scoring_framework_exists": (output / "sandbox_scoring_framework_report.md").exists()
        and len(SCORING_CATEGORIES) == 6,
        "anti_overfitting_controls_exist": (output / "sandbox_anti_overfitting_report.md").exists()
        and len(ANTI_OVERFITTING_CONTROLS) == 10,
        "research_only_leverage_policy_exists": (output / "sandbox_research_only_leverage_report.md").exists(),
        "data_preflight_report_exists": (output / "sandbox_data_preflight_report.md").exists(),
        "next_action_valid": manifest["next_action"] in VALID_NEXT_ACTIONS,
        "manifest_flags_match_strict_scope": all(manifest.get(key) == value for key, value in MANIFEST_FLAGS.items()),
        "required_files_exist": all((output / name).exists() for name in REQUIRED_OUTPUT_FILES),
    }
    check["consistency_passed"] = all(check.values())
    return check


def create_evidence_packet(output: Path) -> Path:
    packet = output / "exploratory_sandbox_implementation_packet.zip"
    with zipfile.ZipFile(packet, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(output.iterdir()):
            if path == packet or path.suffix == ".zip":
                continue
            archive.write(path, path.name)
    return packet


def write_outputs(
    output: Path,
    created_utc: str,
    manifest: dict[str, Any],
    plan: list[Any],
    preflight_rows: list[dict[str, Any]],
) -> None:
    output.mkdir(parents=True, exist_ok=True)
    write_json(output / "exploratory_sandbox_implementation_manifest.json", manifest)
    write_text(output / "exploratory_sandbox_implementation_summary.md", implementation_summary(created_utc, output, manifest))
    write_text(output / "sandbox_module_report.md", module_report())
    write_text(output / "sandbox_variant_schema.md", variant_schema_report())
    write_plan_csv(output / "sandbox_variant_plan_dry_run.csv", plan)
    write_text(output / "sandbox_universe_availability_report.md", universe_availability_report(preflight_rows))
    write_text(output / "sandbox_family_registry_report.md", family_registry_report())
    write_text(output / "sandbox_indicator_registry_report.md", indicator_registry_report())
    write_text(output / "sandbox_status_taxonomy_report.md", status_taxonomy_report())
    write_text(output / "sandbox_scoring_framework_report.md", scoring_framework_report())
    write_text(output / "sandbox_anti_overfitting_report.md", anti_overfitting_report())
    write_text(output / "sandbox_research_only_leverage_report.md", leverage_policy_report())
    write_text(output / "sandbox_data_preflight_report.md", preflight_report(preflight_rows))
    write_preflight_csv(output / "sandbox_data_preflight_report.csv", preflight_rows)
    write_text(output / "sandbox_do_not_run_results.md", do_not_run_results_report())
    write_text(output / "sandbox_implementation_next_action.md", next_action_report(manifest["next_action"]))
    write_json(output / "exploratory_sandbox_implementation_consistency_check.json", {"consistency_passed": False})


def run_sandbox_implementation(
    root: Path = ROOT,
    *,
    max_variants: int = MAX_TOTAL_FUTURE_VARIANTS,
    update_metadata: bool = True,
) -> dict[str, Any]:
    root = root.resolve()
    created_utc = now_utc()
    output = root / OUTPUT_DIR
    strategies_before = strategy_snapshot(root)
    preflight_rows = preflight_universe_availability(root)
    plan = generate_variant_plan(root, max_variants=max_variants, dry_run=True)
    hard_limits_enforced = validate_plan_limits(plan, max_variants=max_variants)
    non_promotable_plan = assert_plan_non_promotable(plan)
    statuses_blocked = forbidden_statuses_blocked()
    implementation_safe = hard_limits_enforced and non_promotable_plan and statuses_blocked
    next_action = decide_next_action(len(plan), implementation_safe)
    manifest = {
        "created_utc": created_utc,
        "output_dir": str(output.resolve()),
        **MANIFEST_FLAGS,
        "dry_run_mode": True,
        "variant_plan_generated": bool(plan),
        "variant_plan_rows": len(plan),
        "max_total_future_variants": MAX_TOTAL_FUTURE_VARIANTS,
        "max_families_per_run": MAX_FAMILIES_PER_RUN,
        "max_variants_per_family": MAX_VARIANTS_PER_FAMILY,
        "max_parameter_choices_per_indicator_concept": MAX_PARAMETER_CHOICES_PER_INDICATOR,
        "max_universe_groups_per_run": MAX_UNIVERSE_GROUPS_PER_RUN,
        "max_portfolio_combination_variants": MAX_PORTFOLIO_COMBINATION_VARIANTS,
        "allowed_family_count": len(ALLOWED_FAMILIES),
        "allowed_universe_count": len(UNIVERSE_GROUPS),
        "allowed_indicator_count": len(ALLOWED_INDICATORS),
        "forbidden_statuses_blocked": statuses_blocked,
        "hard_limits_enforced": hard_limits_enforced,
        "scoring_framework_defined": len(SCORING_CATEGORIES) == 6,
        "anti_overfitting_controls_defined": len(ANTI_OVERFITTING_CONTROLS) == 10,
        "data_preflight_completed": bool(preflight_rows),
        "evidence_packet_created": False,
        "next_action": next_action,
    }
    write_outputs(output, created_utc, manifest, plan, preflight_rows)
    if update_metadata:
        manifest["registry_metadata_updated"] = update_registry_metadata(root, output, created_utc, manifest)
        manifest["roadmap_updated"] = update_roadmap(root, output, created_utc, manifest)
    else:
        manifest["registry_metadata_updated"] = False
        manifest["roadmap_updated"] = False
    strategies_after = strategy_snapshot(root)
    if strategies_before != strategies_after:
        manifest["active_strategy_state_changed"] = True
        manifest["rejected_strategy_state_changed"] = True
    consistency = consistency_check(manifest, output, len(plan))
    write_json(output / "exploratory_sandbox_implementation_manifest.json", manifest)
    write_json(output / "exploratory_sandbox_implementation_consistency_check.json", consistency)
    packet = create_evidence_packet(output)
    manifest["evidence_packet_created"] = packet.exists()
    manifest["evidence_packet_path"] = str(packet.resolve())
    consistency = consistency_check(manifest, output, len(plan))
    write_json(output / "exploratory_sandbox_implementation_manifest.json", manifest)
    write_json(output / "exploratory_sandbox_implementation_consistency_check.json", consistency)
    return {
        "output_dir": str(output),
        "variant_plan_rows": len(plan),
        "allowed_family_count": len(ALLOWED_FAMILIES),
        "allowed_universe_count": len(UNIVERSE_GROUPS),
        "allowed_indicator_count": len(ALLOWED_INDICATORS),
        "next_action": manifest["next_action"],
        "consistency_passed": consistency["consistency_passed"],
        "evidence_packet_path": str(packet),
    }
