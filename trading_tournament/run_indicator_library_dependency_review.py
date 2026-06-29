from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = Path("evidence") / "governance" / "indicator_library_dependency_review" / "latest"
REGISTRY_PATH = Path("strategy_lab") / "strategy_registry.yaml"
ROADMAP_PATH = Path("strategy_lab") / "RESEARCH_ROADMAP.md"
REQUIREMENTS_PATH = Path("requirements.txt")
VALIDATION_IMPL_DIR = Path("evidence") / "governance" / "indicator_validation_harness_implementation" / "latest"
INTEGRATION_AUDIT_DIR = Path("evidence") / "governance" / "indicator_library_integration_audit" / "latest"

DEPENDENCY_DECISION = "stay_custom_indicators_only"
SELECTED_DEPENDENCY_CANDIDATE = "current_custom_indicators_only"
NEXT_ACTION = "pre_register_next_family_after_indicator_validation"

VALID_DEPENDENCY_DECISIONS = {
    "stay_custom_indicators_only",
    "approve_ta_for_future_controlled_install",
    "approve_pandas_ta_classic_for_future_controlled_install",
    "manual_dependency_review_required",
    "reject_external_indicator_libraries_for_now",
}
VALID_NEXT_ACTIONS = {
    "pre_register_external_indicator_parity_harness",
    "pre_register_next_family_after_indicator_validation",
    "pause_expansion_and_wait_for_manual_direction",
    "manual_review_required_for_indicator_dependency",
}

MANIFEST_FLAGS = {
    "dependency_review_only": True,
    "dependency_installed": False,
    "dependency_files_changed": False,
    "strategy_discovery_run": False,
    "backtests_run": False,
    "new_performance_metrics_computed": False,
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
    "expansion_remains_paused": True,
    "intraday_research_remains_paused": True,
}

CANDIDATE_REVIEWS = [
    {
        "candidate": "current_custom_indicators_only",
        "classification": "selected",
        "install_complexity": "none",
        "maintenance_risk": "low_local_surface_area",
        "native_dependency_risk": "none",
        "reproducibility_risk": "lowest",
        "pandas_compatibility": "already_validated",
        "parity_testing": "current_reference",
        "allowlist_support": "direct",
        "indicator_mining_risk": "lowest",
        "near_term_help": "sufficient_after_clean_validation",
        "intraday_effect": "none_intraday_remains_paused",
        "gate_risk": "does_not_weaken_gates_or_reopen_rejects",
        "decision_note": "Stay with custom indicators; adding a catalog library does not solve the current bottleneck.",
    },
    {
        "candidate": "ta",
        "classification": "defer",
        "install_complexity": "likely_lightweight_python_package",
        "maintenance_risk": "external_package_lifecycle",
        "native_dependency_risk": "low",
        "reproducibility_risk": "moderate_until_pinned",
        "pandas_compatibility": "likely_good_but_needs_local_parity_tests",
        "parity_testing": "feasible_against_current_harness",
        "allowlist_support": "yes_if_wrapped",
        "indicator_mining_risk": "moderate_catalog_risk",
        "near_term_help": "not_needed_after_custom_validation",
        "intraday_effect": "no_intraday_use_while_paused",
        "gate_risk": "must_not_weaken_gates_or_rescue_rejects",
        "decision_note": "Could be reconsidered later, but no install or dependency patch is justified now.",
    },
    {
        "candidate": "pandas-ta-classic",
        "classification": "defer",
        "install_complexity": "moderate",
        "maintenance_risk": "external_package_lifecycle_and_broad_catalog",
        "native_dependency_risk": "low_to_moderate",
        "reproducibility_risk": "moderate_until_pinned",
        "pandas_compatibility": "likely_good_but_broad_surface",
        "parity_testing": "feasible_but_broader_than_needed",
        "allowlist_support": "yes_if_strictly_wrapped",
        "indicator_mining_risk": "high_catalog_mining_risk",
        "near_term_help": "not_needed_for_validated_current_indicators",
        "intraday_effect": "no_intraday_use_while_paused",
        "gate_risk": "strict_allowlist_required",
        "decision_note": "Broader catalog is not justified now because it increases mining risk.",
    },
    {
        "candidate": "TA-Lib",
        "classification": "manual_review_required_if_reconsidered",
        "install_complexity": "high_native_library_wrapper",
        "maintenance_risk": "native_binary_and_platform_risk",
        "native_dependency_risk": "high",
        "reproducibility_risk": "high_without_lock_and_platform_plan",
        "pandas_compatibility": "adapter_required",
        "parity_testing": "possible_but_setup_heavy",
        "allowlist_support": "yes_but_costly",
        "indicator_mining_risk": "moderate_catalog_risk",
        "near_term_help": "not_needed",
        "intraday_effect": "no_intraday_use_while_paused",
        "gate_risk": "manual_review_required_before_any_use",
        "decision_note": "Do not add without human dependency/platform review.",
    },
    {
        "candidate": "vectorbt_indicator_layer_only",
        "classification": "reject_for_now",
        "install_complexity": "high_framework_surface_area",
        "maintenance_risk": "framework_migration_risk",
        "native_dependency_risk": "moderate_transitive_surface",
        "reproducibility_risk": "high_due_to_large_stack",
        "pandas_compatibility": "strong_but_framework_oriented",
        "parity_testing": "possible_but_overpowered_for_need",
        "allowlist_support": "harder_due_to_framework_breadth",
        "indicator_mining_risk": "high_fast_scan_risk",
        "near_term_help": "not_needed_and_distracting",
        "intraday_effect": "must_remain_blocked",
        "gate_risk": "could_encourage_framework_migration_and_indicator_mining",
        "decision_note": "Reject for now; too much surface area for a paused governance track.",
    },
]

REQUIRED_FILES = [
    "indicator_dependency_review_manifest.json",
    "indicator_dependency_review_summary.md",
    "candidate_library_dependency_matrix.md",
    "dependency_risk_assessment.md",
    "dependency_decision.md",
    "proposed_dependency_patch_if_any.md",
    "indicator_library_parity_requirements.md",
    "indicator_dependency_do_not_install_now.md",
    "indicator_dependency_next_action.md",
    "indicator_dependency_review_consistency_check.json",
]


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_yaml(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=False), encoding="utf-8")


def strategy_snapshot(root: Path) -> list[dict[str, Any]]:
    return deepcopy(load_yaml(root / REGISTRY_PATH).get("strategies", []))


def requirements_snapshot(root: Path) -> str:
    path = root / REQUIREMENTS_PATH
    return path.read_text(encoding="utf-8") if path.exists() else ""


def replace_or_append_section(text: str, header: str, section: str) -> str:
    if header not in text:
        return text.rstrip() + "\n\n" + section.rstrip() + "\n"
    start = text.index(header)
    next_start = text.find("\n## ", start + len(header))
    if next_start == -1:
        return text[:start].rstrip() + "\n\n" + section.rstrip() + "\n"
    return text[:start].rstrip() + "\n\n" + section.rstrip() + "\n\n" + text[next_start + 1 :].lstrip()


def matrix_md() -> str:
    rows = "\n".join(
        "| `{candidate}` | `{classification}` | `{install_complexity}` | `{maintenance_risk}` | `{native_dependency_risk}` | `{reproducibility_risk}` | `{indicator_mining_risk}` | {decision_note} |".format(
            **item
        )
        for item in CANDIDATE_REVIEWS
    )
    return f"""# Candidate Library Dependency Matrix

| Candidate | Classification | Install complexity | Maintenance risk | Native dependency risk | Reproducibility risk | Indicator-mining risk | Decision note |
|---|---|---|---|---|---|---|---|
{rows}
"""


def risk_assessment_md(validation_manifest: dict[str, Any]) -> str:
    return f"""# Dependency Risk Assessment

Validation harness result:

- Fixture types implemented: `{validation_manifest.get('fixture_types_implemented_count', 'unknown')}`
- Indicator tests added: `{validation_manifest.get('indicator_tests_added_count', 'unknown')}`
- Lookahead tests added: `{validation_manifest.get('lookahead_tests_added_count', 'unknown')}`
- Indicator bugs found: `{validation_manifest.get('indicator_bugs_found_count', 'unknown')}`
- Material strategy-result risk flagged: `{str(validation_manifest.get('material_strategy_result_risk_flag', 'unknown')).lower()}`

Main dependency risks:

- External catalogs increase indicator-mining temptation.
- Pinning, package lifecycle, and transitive dependencies add reproducibility risk.
- `TA-Lib` adds native dependency/platform risk.
- `vectorbt` risks broad framework migration rather than a narrow indicator layer.
- Any library output must be parity-tested before use, so adding a library now does not accelerate safe research.
- Intraday indicator use remains blocked while intraday research is paused.

Conclusion: current custom indicators validate cleanly and are sufficient for the current governance state.
"""


def summary_md(created_utc: str, output: Path) -> str:
    return f"""# Indicator Library Dependency Review Summary

Created UTC: `{created_utc}`

Evidence path: `{output.resolve()}`

Dependency decision: `{DEPENDENCY_DECISION}`

Selected dependency candidate: `{SELECTED_DEPENDENCY_CANDIDATE}`

No dependency was installed. No dependency file was changed. No proposed dependency patch was created.

The custom indicator layer validated cleanly, so an external indicator library does not solve the current project bottleneck. The safer path is to proceed, if at all, through a separate next-family preregistration that continues to use validated custom indicators and strict anti-mining controls.
"""


def decision_md() -> str:
    return f"""# Dependency Decision

Decision: `{DEPENDENCY_DECISION}`

Selected dependency candidate: `{SELECTED_DEPENDENCY_CANDIDATE}`

Rationale:

- Current custom indicators validated cleanly.
- The allowed indicator set is already covered enough for daily/weekly ETF governance work.
- A library catalog would add mining and reproducibility risk before it adds clear research value.
- Future external-library parity work can be reconsidered later, but this task creates no install and no dependency patch.
"""


def proposed_patch_md() -> str:
    return """# Proposed Dependency Patch If Any

Proposed dependency patch created: `false`

No dependency file is changed by this review.

No package is installed or added to `requirements.txt`.
"""


def parity_md() -> str:
    return """# Indicator Library Parity Requirements

No indicator may be used for discovery without validation/parity tests.

If an external library is ever approved in a later governance step:

- dependency versions must be pinned or otherwise reproducibly constrained,
- every used indicator must be mapped to the existing allowlist,
- every used indicator must pass parity against the current custom implementation, a hand-computed fixture, or both,
- warmup, missing-value, flat-price, gap, and lookahead-sensitive behavior must be checked,
- no indicator grid may be promotion-eligible,
- exact rejected variants cannot be reopened with indicators,
- indicators cannot weaken risk gates or justify paper-forward directly,
- intraday indicator use remains blocked while intraday research is paused.
"""


def do_not_install_md() -> str:
    return """# Indicator Dependency Do Not Install Now

This review explicitly forbids the following in this task:

- installing `ta`
- installing `pandas-ta-classic`
- installing `TA-Lib`
- installing `vectorbt`
- changing dependency files
- generating indicator strategies
- running grid searches
- running strategy discovery or trading backtests
- downloading provider data
- using intraday data
- running candidate_exhaustive
- activating paper-forward
- touching broker/live-order paths
- making real-money recommendations
"""


def next_action_md() -> str:
    return f"""# Indicator Dependency Next Action

Exact next action: `{NEXT_ACTION}`

Reason: the dependency decision is to stay with validated custom indicators, so no external parity harness is needed before selecting a future family. Any next family must still be separately pre-registered and must not reopen exact rejected variants or weaken gates.

Do not run this next action in the dependency-review task.
"""


def update_registry_metadata(root: Path, created_utc: str, output: Path, manifest: dict[str, Any]) -> None:
    path = root / REGISTRY_PATH
    data = load_yaml(path)
    meta = data.setdefault("registry", {})
    meta.update(
        {
            "indicator_library_dependency_review_path": str(output.resolve()),
            "indicator_library_dependency_review_status": "completed",
            "indicator_library_dependency_review_created_utc": created_utc,
            "dependency_review_only": True,
            "dependency_installed": False,
            "dependency_files_changed": False,
            "indicator_dependency_review_decision": manifest["dependency_decision"],
            "selected_dependency_candidate": manifest["selected_dependency_candidate"],
            "proposed_dependency_patch_created": False,
            "expansion_paused": True,
            "intraday_research_remains_paused": True,
            "official_current_next_action": NEXT_ACTION,
            "current_next_action": NEXT_ACTION,
            "next_action": NEXT_ACTION,
            "strategy_discovery_run": False,
            "backtests_run": False,
            "new_performance_metrics_computed": False,
            "provider_download": False,
            "intraday_data_used": False,
            "candidate_exhaustive_run": False,
            "paper_forward_review": False,
            "paper_forward_activation": False,
            "broker_orders_submitted": False,
            "broker_orders_cancelled": False,
            "live_orders": False,
            "real_money_recommendation": False,
        }
    )
    write_yaml(path, data)


def update_roadmap(root: Path, created_utc: str, output: Path) -> None:
    path = root / ROADMAP_PATH
    text = path.read_text(encoding="utf-8") if path.exists() else "# Research Roadmap\n"
    compact = f"""## Compact Current State

- Updated UTC: `{created_utc}`
- Current research mode: `indicator_library_dependency_review_completed`
- Official current next action: `{NEXT_ACTION}`
- Indicator dependency review evidence: `{output.resolve()}`
- Dependency decision: `{DEPENDENCY_DECISION}`
- Selected dependency candidate: `{SELECTED_DEPENDENCY_CANDIDATE}`
- Expansion remains paused: `true`
- Intraday remains paused: `true`
- Active accepted/paper-demo observations preserved: active VM and active DSR.
- Benchmark/control preserved: `static_all_weather_benchmark_v1` remains benchmark/control only.
- Exact rejected variants remain closed, including the latest risk-controlled high-return rejects.
- This section does not authorize dependency installation, discovery, trading backtests, new strategy metrics, provider download, intraday data, candidate_exhaustive, paper-forward action, broker/live order paths, or real-money recommendation.
"""
    text = replace_or_append_section(text, "## Compact Current State", compact)
    section = f"""## Indicator Library Dependency Review

- Created UTC: `{created_utc}`
- Evidence path: `{output.resolve()}`
- Dependency-review-only: `true`
- Dependency installed: `false`
- Dependency files changed: `false`
- Dependency decision: `{DEPENDENCY_DECISION}`
- Selected dependency candidate: `{SELECTED_DEPENDENCY_CANDIDATE}`
- Proposed dependency patch created: `false`
- Expansion remains paused: `true`
- Intraday remains paused: `true`
- Official current next action: `{NEXT_ACTION}`
- This review does not authorize dependency installation, strategy discovery, trading backtests, new strategy metrics, provider download, intraday data, candidate_exhaustive, paper-forward action, broker/live order paths, indicator strategy creation, grid search, or real-money recommendation.
"""
    write_text(path, replace_or_append_section(text, "## Indicator Library Dependency Review", section))


def consistency_check(manifest: dict[str, Any], output: Path) -> dict[str, Any]:
    check = {
        "dependency_review_only": manifest["dependency_review_only"] is True,
        "no_dependency_installed": manifest["dependency_installed"] is False,
        "dependency_files_unchanged": manifest["dependency_files_changed"] is False,
        "no_strategy_discovery": manifest["strategy_discovery_run"] is False,
        "no_backtests": manifest["backtests_run"] is False,
        "no_new_performance_metrics": manifest["new_performance_metrics_computed"] is False,
        "no_provider_download": manifest["provider_download"] is False,
        "no_intraday_data_used": manifest["intraday_data_used"] is False,
        "no_candidate_exhaustive": manifest["candidate_exhaustive_run"] is False,
        "no_paper_forward_action": manifest["paper_forward_review"] is False and manifest["paper_forward_activation"] is False,
        "no_broker_orders_submitted": manifest["broker_orders_submitted"] is False,
        "no_broker_orders_cancelled": manifest["broker_orders_cancelled"] is False,
        "no_live_orders": manifest["live_orders"] is False,
        "no_real_money_recommendation": manifest["real_money_recommendation"] is False,
        "active_strategy_state_preserved": manifest["active_strategy_state_changed"] is False,
        "rejected_strategy_state_preserved": manifest["rejected_strategy_state_changed"] is False,
        "exact_rejected_variants_not_reopened": manifest["exact_rejected_variants_reopened"] is False,
        "expansion_remains_paused": manifest["expansion_remains_paused"] is True,
        "intraday_remains_paused": manifest["intraday_research_remains_paused"] is True,
        "candidate_library_matrix_exists": (output / "candidate_library_dependency_matrix.md").exists(),
        "dependency_risk_assessment_exists": (output / "dependency_risk_assessment.md").exists(),
        "dependency_decision_valid": manifest["dependency_decision"] in VALID_DEPENDENCY_DECISIONS,
        "do_not_install_now_file_exists": (output / "indicator_dependency_do_not_install_now.md").exists(),
        "next_action_valid": manifest["next_action"] in VALID_NEXT_ACTIONS,
        "manifest_flags_match_strict_scope": all(manifest[key] == value for key, value in MANIFEST_FLAGS.items()),
    }
    check["consistency_passed"] = all(check.values())
    return check


def write_evidence(output: Path, created_utc: str, manifest: dict[str, Any], validation_manifest: dict[str, Any]) -> None:
    output.mkdir(parents=True, exist_ok=True)
    write_json(output / "indicator_dependency_review_manifest.json", manifest)
    write_text(output / "indicator_dependency_review_summary.md", summary_md(created_utc, output))
    write_text(output / "candidate_library_dependency_matrix.md", matrix_md())
    write_text(output / "dependency_risk_assessment.md", risk_assessment_md(validation_manifest))
    write_text(output / "dependency_decision.md", decision_md())
    write_text(output / "proposed_dependency_patch_if_any.md", proposed_patch_md())
    write_text(output / "indicator_library_parity_requirements.md", parity_md())
    write_text(output / "indicator_dependency_do_not_install_now.md", do_not_install_md())
    write_text(output / "indicator_dependency_next_action.md", next_action_md())
    write_json(output / "indicator_dependency_review_consistency_check.json", {"consistency_passed": False})
    write_yaml(
        output / "indicator_dependency_review_context.yaml",
        {
            "dependency_files_reviewed": [str(REQUIREMENTS_PATH)],
            "candidate_libraries_reviewed": [item["candidate"] for item in CANDIDATE_REVIEWS],
            "prior_validation_evidence": str(VALIDATION_IMPL_DIR),
            "prior_integration_audit_evidence": str(INTEGRATION_AUDIT_DIR),
            "no_dependency_installed": True,
            "no_dependency_file_changed": True,
        },
    )


def run_indicator_library_dependency_review(root: Path = ROOT) -> dict[str, Any]:
    root = root.resolve()
    created_utc = now_utc()
    output = root / OUTPUT_DIR
    strategies_before = strategy_snapshot(root)
    requirements_before = requirements_snapshot(root)
    validation_manifest = load_json(root / VALIDATION_IMPL_DIR / "indicator_validation_implementation_manifest.json")
    manifest = {
        "created_utc": created_utc,
        "output_dir": str(output.resolve()),
        **MANIFEST_FLAGS,
        "dependency_decision": DEPENDENCY_DECISION,
        "selected_dependency_candidate": SELECTED_DEPENDENCY_CANDIDATE,
        "proposed_dependency_patch_created": False,
        "next_action": NEXT_ACTION,
    }
    write_evidence(output, created_utc, manifest, validation_manifest)
    requirements_after_evidence = requirements_snapshot(root)
    if requirements_before != requirements_after_evidence:
        manifest["dependency_files_changed"] = True
        write_json(output / "indicator_dependency_review_manifest.json", manifest)
    consistency = consistency_check(manifest, output)
    write_json(output / "indicator_dependency_review_consistency_check.json", consistency)
    update_registry_metadata(root, created_utc, output, manifest)
    update_roadmap(root, created_utc, output)
    strategies_after = strategy_snapshot(root)
    requirements_after = requirements_snapshot(root)
    if strategies_before != strategies_after or requirements_before != requirements_after:
        if strategies_before != strategies_after:
            manifest["active_strategy_state_changed"] = True
            manifest["rejected_strategy_state_changed"] = True
        if requirements_before != requirements_after:
            manifest["dependency_files_changed"] = True
        write_json(output / "indicator_dependency_review_manifest.json", manifest)
        consistency = consistency_check(manifest, output)
        write_json(output / "indicator_dependency_review_consistency_check.json", consistency)
    return {
        "output_dir": str(output),
        "dependency_decision": manifest["dependency_decision"],
        "selected_dependency_candidate": manifest["selected_dependency_candidate"],
        "proposed_dependency_patch_created": manifest["proposed_dependency_patch_created"],
        "next_action": manifest["next_action"],
        "consistency_passed": consistency["consistency_passed"],
    }


def main() -> None:
    print(json.dumps(run_indicator_library_dependency_review(ROOT), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
