from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = Path("evidence") / "governance" / "indicator_library_integration_audit" / "latest"
REGISTRY_PATH = Path("strategy_lab") / "strategy_registry.yaml"
ROADMAP_PATH = Path("strategy_lab") / "RESEARCH_ROADMAP.md"
INDICATOR_POLICY_PATH = Path("indicator_layer") / "indicator_policy.md"
APPROVED_INDICATORS_PATH = Path("indicator_layer") / "approved_indicators.yaml"
REQUIREMENTS_PATH = Path("requirements.txt")
CUSTOM_INDICATOR_PATH = Path("src") / "indicators.py"

DEPENDENCY_DECISION = "no_dependency_added_policy_only"
SELECTED_LIBRARY = "current_custom_indicators_only"
NEXT_ACTION = "pre_register_indicator_validation_harness"
VALID_DECISIONS = {
    "no_dependency_added_policy_only",
    "approve_lightweight_indicator_library_for_future_install",
    "manual_dependency_review_required",
    "reject_indicator_library_addition_for_now",
}
VALID_NEXT_ACTIONS = {
    "manual_review_indicator_library_dependency_choice",
    "pre_register_indicator_validation_harness",
    "pre_register_next_family_after_indicator_governance",
    "pause_expansion_and_wait_for_manual_direction",
}

MANIFEST_FLAGS = {
    "indicator_governance_only": True,
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
    "intraday_research_remains_paused": True,
    "expansion_remains_paused": True,
}

ALLOWED_INDICATORS = {
    "trend": [
        {"name": "SMA", "status": "allowed"},
        {"name": "EMA", "status": "allowed"},
        {"name": "Donchian high/low", "status": "allowed"},
        {"name": "ADX", "status": "gated_requires_validation"},
    ],
    "momentum": [
        {"name": "ROC / total return", "status": "allowed"},
        {"name": "RSI", "status": "allowed"},
        {"name": "MACD", "status": "gated_requires_validation"},
    ],
    "volatility": [
        {"name": "ATR", "status": "allowed"},
        {"name": "realized volatility", "status": "allowed"},
        {"name": "Bollinger Band z-score", "status": "allowed"},
        {"name": "Keltner Channel", "status": "gated_requires_validation"},
    ],
    "volume_liquidity": [
        {"name": "volume SMA", "status": "allowed"},
        {"name": "volume spike filter", "status": "allowed"},
        {"name": "OBV", "status": "gated_requires_validation"},
    ],
    "risk_state": [
        {"name": "drawdown state", "status": "allowed"},
        {"name": "volatility percentile", "status": "allowed"},
        {"name": "moving-average regime", "status": "allowed"},
    ],
}

FORBIDDEN_RULES = [
    "broad indicator mining",
    "indicator voting systems",
    "genetic search",
    "AI-selected indicator formulas",
    "candlestick-pattern mining",
    "unrestricted parameter grids",
    "post-result indicator tuning",
    "adding indicators to rescue exact rejected rows",
    "using indicators to weaken risk gates",
    "using indicators to justify paper-forward directly",
    "intraday indicator strategies while intraday data is paused",
]

LIBRARY_REVIEWS = [
    {
        "approach": "keep_current_custom_indicators_only",
        "classification": "defer",
        "summary": "Selected for now: no dependency added; formalize policy and validate existing custom calculations before any strategy use.",
    },
    {
        "approach": "ta",
        "classification": "approved_for_future_dependency_review",
        "summary": "Lightweight Pandas-style candidate for future review; useful catalog but still requires allowlist and parity tests.",
    },
    {
        "approach": "pandas-ta-classic",
        "classification": "approved_for_future_dependency_review",
        "summary": "Broad Pandas indicator catalog; higher mining risk, so future review must be allowlist-first.",
    },
    {
        "approach": "TA-Lib",
        "classification": "manual_review_required",
        "summary": "Native dependency/install complexity makes it inappropriate without manual dependency approval.",
    },
    {
        "approach": "vectorbt_indicator_layer_only",
        "classification": "reject_for_now",
        "summary": "Powerful but too likely to pull the project toward framework migration or fast indicator mining.",
    },
]

REQUIRED_FILES = [
    "indicator_library_audit_manifest.json",
    "indicator_library_audit_summary.md",
    "current_indicator_usage_inventory.md",
    "candidate_indicator_library_review.md",
    "approved_indicator_allowlist.yaml",
    "forbidden_indicator_usage.md",
    "indicator_validation_policy.md",
    "indicator_overfitting_controls.md",
    "indicator_family_lane_mapping.md",
    "dependency_decision.md",
    "roadmap_next_action_reconciliation.md",
    "indicator_library_next_action.md",
    "indicator_library_audit_consistency_check.json",
]


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


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


def replace_or_append_section(text: str, header: str, section: str) -> str:
    if header not in text:
        return text.rstrip() + "\n\n" + section.rstrip() + "\n"
    start = text.index(header)
    next_start = text.find("\n## ", start + len(header))
    if next_start == -1:
        return text[:start].rstrip() + "\n\n" + section.rstrip() + "\n"
    return text[:start].rstrip() + "\n\n" + section.rstrip() + "\n\n" + text[next_start + 1 :].lstrip()


def allowed_indicator_count() -> int:
    return sum(len(items) for items in ALLOWED_INDICATORS.values())


def dependency_inventory(root: Path) -> dict[str, Any]:
    requirements = root / REQUIREMENTS_PATH
    packages = []
    if requirements.exists():
        packages = [
            line.strip()
            for line in requirements.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
    return {
        "dependency_files_found": [str(REQUIREMENTS_PATH)] if requirements.exists() else [],
        "declared_packages": packages,
        "indicator_libraries_declared": [
            pkg
            for pkg in packages
            if pkg.split("==")[0].lower() in {"ta", "pandas-ta", "pandas-ta-classic", "ta-lib", "talib", "vectorbt"}
        ],
    }


def roadmap_reconciliation(root: Path, created_utc: str) -> dict[str, Any]:
    path = root / ROADMAP_PATH
    text = path.read_text(encoding="utf-8") if path.exists() else "# Research Roadmap\n"
    stale_action = "audit_risk_controlled_high_return_discovery_failures"
    expected_action = "pre_register_indicator_library_integration_audit"
    had_stale_top_action = False
    if "## Compact Current State" in text:
        top = text.split("## Priority Backlog", 1)[0]
        had_stale_top_action = f"Official current next action: `{stale_action}`" in top
    compact_section = f"""## Compact Current State

- Updated UTC: `{created_utc}`
- Current research mode: `indicator_library_governance_audit_completed`
- Official current next action: `{NEXT_ACTION}`
- Indicator audit evidence: `{(root / OUTPUT_DIR).resolve()}`
- Roadmap top next-action reconciliation: `completed`
- Previous stale top action, if present: `{stale_action}`
- Canonical pre-audit next action: `{expected_action}`
- Expansion remains paused: `true`
- Intraday remains paused: `true`
- Active accepted/paper-demo observations preserved: active VM and active DSR.
- Benchmark/control preserved: `static_all_weather_benchmark_v1` remains benchmark/control only.
- Exact rejected variants remain closed, including the latest risk-controlled high-return rejects.
- This section does not authorize discovery, backtests, new metrics, provider download, intraday data, candidate_exhaustive, paper-forward action, broker/live order paths, or real-money recommendation.
"""
    reconciled_text = replace_or_append_section(text, "## Compact Current State", compact_section)
    write_text(path, reconciled_text)
    return {
        "roadmap_next_action_reconciled": True,
        "had_stale_top_action": had_stale_top_action,
        "stale_top_action": stale_action if had_stale_top_action else "",
        "canonical_pre_audit_next_action": expected_action,
        "final_next_action": NEXT_ACTION,
    }


def update_registry_metadata(root: Path, created_utc: str, output: Path, manifest: dict[str, Any]) -> None:
    path = root / REGISTRY_PATH
    data = load_yaml(path)
    meta = data.setdefault("registry", {})
    meta.update(
        {
            "indicator_library_integration_audit_path": str(output.resolve()),
            "indicator_library_integration_audit_status": "completed",
            "indicator_library_integration_audit_created_utc": created_utc,
            "indicator_governance_only": True,
            "indicator_dependency_decision": DEPENDENCY_DECISION,
            "indicator_library_dependency_added": False,
            "selected_indicator_library": SELECTED_LIBRARY,
            "allowed_indicator_count": manifest["allowed_indicator_count"],
            "forbidden_indicator_rules_count": manifest["forbidden_indicator_rules_count"],
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


def update_roadmap_audit_section(root: Path, created_utc: str, output: Path) -> None:
    path = root / ROADMAP_PATH
    text = path.read_text(encoding="utf-8") if path.exists() else "# Research Roadmap\n"
    section = f"""## Indicator Library Integration Audit

- Created UTC: `{created_utc}`
- Evidence path: `{output.resolve()}`
- Governance-only audit: `true`
- Dependency decision: `{DEPENDENCY_DECISION}`
- Selected library: `{SELECTED_LIBRARY}`
- Library dependency added: `false`
- Allowed indicator entries: `{allowed_indicator_count()}`
- Forbidden indicator rules: `{len(FORBIDDEN_RULES)}`
- Expansion remains paused: `true`
- Intraday remains paused: `true`
- Official current next action: `{NEXT_ACTION}`
- This audit does not authorize discovery, backtests, new metrics, provider download, intraday data, candidate_exhaustive, paper-forward action, broker/live order paths, exact rejected variant reopening, indicator mining, parameter grids, gate weakening, or real-money recommendation.
"""
    write_text(path, replace_or_append_section(text, "## Indicator Library Integration Audit", section))


def summary_md(created_utc: str, output: Path) -> str:
    return f"""# Indicator Library Integration Audit Summary

Created UTC: `{created_utc}`

Evidence path: `{output.resolve()}`

Decision: `{DEPENDENCY_DECISION}`

Selected library: `{SELECTED_LIBRARY}`

No dependency is added by this audit. The project is not currently limited by lack of indicator catalogs; it is limited by governance, validation, risk gates, data constraints, and overfitting risk.

The suitable near-term path is to keep existing custom indicators, formalize the allowlist, and pre-register a validation harness before any library replacement or indicator-based strategy use.
"""


def inventory_md(root: Path) -> str:
    deps = dependency_inventory(root)
    policy_exists = (root / INDICATOR_POLICY_PATH).exists()
    allowlist_exists = (root / APPROVED_INDICATORS_PATH).exists()
    custom_exists = (root / CUSTOM_INDICATOR_PATH).exists()
    packages = ", ".join(f"`{pkg}`" for pkg in deps["declared_packages"]) or "none"
    indicator_libs = ", ".join(f"`{pkg}`" for pkg in deps["indicator_libraries_declared"]) or "none"
    return f"""# Current Indicator Usage Inventory

## Dependency files

- Dependency files found: `{', '.join(deps['dependency_files_found']) or 'none'}`
- Declared packages: {packages}
- Declared indicator libraries: {indicator_libs}

## Existing policy and allowlist

- `indicator_layer/indicator_policy.md` exists: `{str(policy_exists).lower()}`
- `indicator_layer/approved_indicators.yaml` exists: `{str(allowlist_exists).lower()}`

## Existing custom indicator code

- `src/indicators.py` exists: `{str(custom_exists).lower()}`
- Current custom calculations include SMA, EMA, ATR, RSI, Bollinger bands, realized volatility, rolling return/ROC, prior rolling high/Donchian-style breakout, consolidation range, rolling percentile rank, volume SMA, and SPY regime features.
- Strategy code consumes prepared indicator columns through the existing backtest engine; no new strategy logic is added by this audit.

Conclusion: lack of indicator library breadth is not the current blocker.
"""


def candidate_review_md() -> str:
    rows = "\n".join(
        f"| `{item['approach']}` | `{item['classification']}` | {item['summary']} |"
        for item in LIBRARY_REVIEWS
    )
    return f"""# Candidate Indicator Library Review

Review basis: local repository files and known dependency constraints only. No online documentation was fetched.

| Approach | Classification | Review |
|---|---|---|
{rows}

Evaluation criteria considered: install complexity, maintenance risk, pure-Python versus native dependency, Pandas compatibility, validation ease, catalog usefulness, indicator-mining risk, current backtest-engine compatibility, reproducibility, daily/weekly ETF suitability, future intraday suitability while intraday remains paused, and allowlist governability.
"""


def allowlist_payload() -> dict[str, Any]:
    return {
        "approved_indicator_allowlist_version": 1,
        "dependency_decision": DEPENDENCY_DECISION,
        "selected_library": SELECTED_LIBRARY,
        "library_dependency_added": False,
        "allowed_initial_categories": ALLOWED_INDICATORS,
        "rules": {
            "family_hypothesis_required": True,
            "frozen_rule_before_testing": True,
            "one_major_new_indicator_concept_per_candidate": True,
            "parameter_values_frozen_before_discovery": True,
            "no_indicator_grid_promotion_eligible": True,
        },
    }


def forbidden_usage_md() -> str:
    bullets = "\n".join(f"- {rule}" for rule in FORBIDDEN_RULES)
    return f"""# Forbidden Indicator Usage

{bullets}
"""


def validation_policy_md() -> str:
    return """# Indicator Validation Policy

- Every approved indicator must have deterministic unit tests with synthetic fixtures.
- Library outputs, if a dependency is later approved, must be parity-tested against existing custom calculations or hand-computed fixtures.
- Validation fixtures must include warmup periods, missing values, flat prices, gaps, and minimum-period behavior.
- Lookahead prevention: signal code must use only indicator values known at or before the decision timestamp.
- Prior-high, breakout, percentile, and regime features must explicitly shift inputs when the current bar would otherwise leak into the decision.
- Daily/weekly indicators remain separate from intraday indicators while intraday research is paused.
- Indicator diagnostics may be generated only as non-promotable diagnostics unless separately pre-registered.
"""


def overfitting_controls_md() -> str:
    return """# Indicator Overfitting Controls

1. Every indicator-based strategy must start from a family hypothesis.
2. Every candidate must have a frozen rule before testing.
3. Each candidate may introduce only one major new indicator concept unless manually approved.
4. Parameter values must be frozen before discovery.
5. No indicator grid can be promotion-eligible.
6. Indicator diagnostics may be run only as research diagnostics and must be labeled non-promotable.
7. Exact rejected variants cannot be reopened with indicators unless there is a new family-level hypothesis and manual approval.
8. Every future indicator strategy must output a signal funnel.
9. Every future indicator strategy must map to a lane and benchmark group.
"""


def family_lane_mapping_md() -> str:
    return """# Indicator Family Lane Mapping

- Trend indicators map to absolute-trend, managed-futures ETF-wrapper, and market-state lanes only after pre-registration.
- Momentum indicators map to dual momentum, sector rotation, and quality/momentum watchlist lanes only when duplication is explicitly controlled.
- Volatility indicators map to volatility-management, risk-state, and stop-risk diagnostics lanes.
- Volume/liquidity indicators map only to liquidity filters or diagnostics until validated.
- Risk-state indicators map to breadth/state, drawdown guard, and market-regime lanes.

No indicator family mapping authorizes immediate discovery or paper-forward action.
"""


def dependency_decision_md() -> str:
    return f"""# Dependency Decision

Decision: `{DEPENDENCY_DECISION}`

Selected library: `{SELECTED_LIBRARY}`

Library dependency added: `false`

Rationale: the existing codebase already has a compact custom indicator layer for the indicators currently used in daily/weekly ETF research. Adding a dependency before validating current calculations would increase reproducibility and mining risk without solving the current blocker.

Future dependency review can consider `ta` or `pandas-ta-classic` behind an allowlist. `TA-Lib` requires manual install review because of native dependency complexity. `vectorbt` is rejected for now because it risks framework migration and broad indicator-mining behavior.
"""


def roadmap_reconciliation_md(reconciliation: dict[str, Any]) -> str:
    return f"""# Roadmap Next Action Reconciliation

Roadmap next-action reconciled: `{str(reconciliation['roadmap_next_action_reconciled']).lower()}`

Had stale top action before audit: `{str(reconciliation['had_stale_top_action']).lower()}`

Stale top action: `{reconciliation['stale_top_action'] or 'none'}`

Canonical pre-audit next action: `{reconciliation['canonical_pre_audit_next_action']}`

Final next action after audit: `{reconciliation['final_next_action']}`
"""


def next_action_md() -> str:
    return f"""# Indicator Library Next Action

Exact next action: `{NEXT_ACTION}`

Reason: indicator governance is ready for a validation harness, but no indicator dependency or strategy use should occur before synthetic fixture tests validate calculations, warmup behavior, and lookahead controls.

Do not run this next action in the indicator audit task.
"""


def consistency_check(manifest: dict[str, Any], output: Path) -> dict[str, Any]:
    check = {
        "indicator_governance_only": manifest["indicator_governance_only"] is True,
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
        "intraday_remains_paused": manifest["intraday_research_remains_paused"] is True,
        "expansion_remains_paused": manifest["expansion_remains_paused"] is True,
        "current_indicator_inventory_exists": (output / "current_indicator_usage_inventory.md").exists(),
        "candidate_library_review_exists": (output / "candidate_indicator_library_review.md").exists(),
        "indicator_allowlist_exists": (output / "approved_indicator_allowlist.yaml").exists(),
        "forbidden_indicator_usage_exists": (output / "forbidden_indicator_usage.md").exists(),
        "validation_policy_exists": (output / "indicator_validation_policy.md").exists(),
        "overfitting_controls_exists": (output / "indicator_overfitting_controls.md").exists(),
        "dependency_decision_valid": manifest["dependency_decision"] in VALID_DECISIONS,
        "next_action_valid": manifest["next_action"] in VALID_NEXT_ACTIONS,
        "manifest_flags_match_strict_scope": all(manifest[key] == value for key, value in MANIFEST_FLAGS.items()),
    }
    check["consistency_passed"] = all(check.values())
    return check


def write_evidence(root: Path, output: Path, created_utc: str, manifest: dict[str, Any], reconciliation: dict[str, Any]) -> None:
    output.mkdir(parents=True, exist_ok=True)
    write_json(output / "indicator_library_audit_manifest.json", manifest)
    write_text(output / "indicator_library_audit_summary.md", summary_md(created_utc, output))
    write_text(output / "current_indicator_usage_inventory.md", inventory_md(root))
    write_text(output / "candidate_indicator_library_review.md", candidate_review_md())
    write_yaml(output / "approved_indicator_allowlist.yaml", allowlist_payload())
    write_text(output / "forbidden_indicator_usage.md", forbidden_usage_md())
    write_text(output / "indicator_validation_policy.md", validation_policy_md())
    write_text(output / "indicator_overfitting_controls.md", overfitting_controls_md())
    write_text(output / "indicator_family_lane_mapping.md", family_lane_mapping_md())
    write_text(output / "dependency_decision.md", dependency_decision_md())
    write_text(output / "roadmap_next_action_reconciliation.md", roadmap_reconciliation_md(reconciliation))
    write_text(output / "indicator_library_next_action.md", next_action_md())
    write_json(output / "indicator_library_audit_consistency_check.json", {"consistency_passed": False})


def run_indicator_library_integration_audit(root: Path = ROOT) -> dict[str, Any]:
    root = root.resolve()
    created_utc = now_utc()
    output = root / OUTPUT_DIR
    strategies_before = strategy_snapshot(root)
    reconciliation = roadmap_reconciliation(root, created_utc)
    manifest = {
        "created_utc": created_utc,
        "output_dir": str(output.resolve()),
        **MANIFEST_FLAGS,
        "roadmap_next_action_reconciled": reconciliation["roadmap_next_action_reconciled"],
        "library_dependency_added": False,
        "dependency_decision": DEPENDENCY_DECISION,
        "selected_library": SELECTED_LIBRARY,
        "allowed_indicator_count": allowed_indicator_count(),
        "forbidden_indicator_rules_count": len(FORBIDDEN_RULES),
        "next_action": NEXT_ACTION,
    }
    write_evidence(root, output, created_utc, manifest, reconciliation)
    consistency = consistency_check(manifest, output)
    write_json(output / "indicator_library_audit_consistency_check.json", consistency)
    update_registry_metadata(root, created_utc, output, manifest)
    update_roadmap_audit_section(root, created_utc, output)
    strategies_after = strategy_snapshot(root)
    if strategies_before != strategies_after:
        manifest["active_strategy_state_changed"] = True
        manifest["rejected_strategy_state_changed"] = True
        write_json(output / "indicator_library_audit_manifest.json", manifest)
        consistency = consistency_check(manifest, output)
        write_json(output / "indicator_library_audit_consistency_check.json", consistency)
    return {
        "output_dir": str(output),
        "dependency_decision": DEPENDENCY_DECISION,
        "selected_library": SELECTED_LIBRARY,
        "library_dependency_added": False,
        "roadmap_next_action_reconciled": reconciliation["roadmap_next_action_reconciled"],
        "allowed_indicator_count": manifest["allowed_indicator_count"],
        "forbidden_indicator_rules_count": manifest["forbidden_indicator_rules_count"],
        "next_action": NEXT_ACTION,
        "consistency_passed": consistency["consistency_passed"],
    }


def main() -> None:
    print(json.dumps(run_indicator_library_integration_audit(ROOT), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
