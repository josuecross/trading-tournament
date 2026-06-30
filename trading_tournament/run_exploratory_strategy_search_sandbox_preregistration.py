from __future__ import annotations

import csv
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = Path("evidence") / "governance" / "exploratory_strategy_search_sandbox_preregistration" / "latest"
REGISTRY_PATH = Path("strategy_lab") / "strategy_registry.yaml"
ROADMAP_PATH = Path("strategy_lab") / "RESEARCH_ROADMAP.md"
COMPACT_STATE_PATH = Path("reports") / "compact_state" / "current_tournament_state.md"
APPROVED_SYMBOL_MAP_PATH = Path("strategy_lab") / "approved_etf_symbol_map.yaml"
DATA_CACHE_DIR = Path("data") / "cache"

NEXT_ACTION_IMPLEMENT = "implement_exploratory_strategy_search_sandbox"
NEXT_ACTION_REVIEW = "manual_review_required_for_exploratory_sandbox"
NEXT_ACTION_PAUSE = "pause_expansion_and_wait_for_manual_direction"
VALID_NEXT_ACTIONS = {NEXT_ACTION_IMPLEMENT, NEXT_ACTION_REVIEW, NEXT_ACTION_PAUSE}

MAX_TOTAL_FUTURE_VARIANTS = 200
MAX_FAMILIES_PER_RUN = 7
MAX_VARIANTS_PER_FAMILY = 30
MAX_PARAMETER_CHOICES_PER_INDICATOR = 5
MAX_UNIVERSE_GROUPS_PER_RUN = 8
MAX_PORTFOLIO_COMBINATION_VARIANTS = 40

ALLOWED_INDICATORS = [
    "SMA",
    "EMA",
    "ATR",
    "RSI",
    "Bollinger bands",
    "realized volatility",
    "ROC / rolling return",
    "Donchian prior high",
    "volume SMA / filter alignment",
    "rolling percentile rank",
    "moving-average regime",
    "SPY regime features",
]

FORBIDDEN_INDICATORS = [
    "MACD",
    "Keltner Channel",
    "OBV",
    "external indicator-library outputs",
    "candlestick-pattern mining",
    "AI-selected formulas",
    "genetic search",
    "broad unconstrained indicator voting systems",
]

ALLOWED_FAMILIES = [
    {
        "family": "trend_momentum",
        "examples": ["time-series momentum", "dual momentum", "cross-sectional momentum", "sector/factor/macro momentum"],
    },
    {
        "family": "mean_reversion",
        "examples": ["RSI pullback", "Bollinger z-score reversion", "distance-from-moving-average reversion"],
    },
    {
        "family": "breakout_continuation",
        "examples": ["Donchian breakout", "volatility compression breakout", "trend continuation after consolidation"],
    },
    {
        "family": "volatility_regime",
        "examples": ["realized-vol filters", "volatility percentile state", "drawdown/SPY regime filters"],
    },
    {
        "family": "factor_style_rotation",
        "examples": ["value/quality/momentum/low-vol ETF rotation", "growth versus value", "quality/momentum/low-vol blend"],
    },
    {
        "family": "macro_portfolio_contribution",
        "examples": ["equity/bond/gold/cash contribution", "managed-futures sleeve contribution", "all-weather controls"],
    },
    {
        "family": "portfolio_combination_sleeve_ensemble",
        "examples": ["active VM + active DSR + BIL", "active VM + active DSR + macro/trend/mean-reversion/managed-futures sleeves"],
    },
]

UNIVERSE_GROUPS = {
    "core_equity_etfs": ["SPY", "QQQ", "IWM", "DIA"],
    "sector_etfs": ["XLK", "XLF", "XLV", "XLE", "XLI", "XLY", "XLP", "XLU", "XLB", "XLRE", "XLC"],
    "macro_etfs": ["GLD", "IEF", "TLT", "AGG", "BIL"],
    "factor_style_etfs": ["VLUE", "QUAL", "MTUM", "SPLV", "USMV", "DGRO", "SCHD", "VIG", "VTV", "SCHG"],
    "managed_futures_wrappers": ["DBMF", "KMLM", "CTA", "FMF", "WTMF"],
    "international_regional_etfs": ["EFA", "EEM", "EWG", "EWJ", "EWU", "EWY", "INDA", "EEMV", "EFAV"],
    "credit_income_etfs": ["LQD", "HYG", "EMB"],
}

ALLOWED_SANDBOX_STATUSES = [
    "sandbox_discard",
    "sandbox_family_weak",
    "sandbox_family_interesting",
    "sandbox_component_candidate",
    "sandbox_portfolio_sleeve_candidate",
    "sandbox_needs_objective_reset",
    "sandbox_data_blocked",
    "sandbox_future_preregistration_candidate",
]

FORBIDDEN_STATUSES = [
    "promotion_review_candidate",
    "candidate_exhaustive",
    "paper_forward",
    "paper_forward_active",
    "demo_active",
    "live_ready",
]

MANIFEST_FLAGS = {
    "sandbox_preregistration_only": True,
    "strategy_discovery_run": False,
    "backtests_run": False,
    "new_performance_metrics_computed": False,
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
    "sandbox_results_non_promotable": True,
    "sandbox_can_create_paper_candidates": False,
}

REQUIRED_FILES = [
    "exploratory_sandbox_preregistration_manifest.json",
    "exploratory_sandbox_summary.md",
    "sandbox_scope.md",
    "sandbox_allowed_universes.md",
    "sandbox_allowed_families.md",
    "sandbox_allowed_indicators.md",
    "sandbox_variant_limits.md",
    "sandbox_scoring_framework.md",
    "sandbox_anti_overfitting_controls.md",
    "sandbox_status_taxonomy.md",
    "sandbox_future_graduation_rules.md",
    "sandbox_research_only_leverage_policy.md",
    "sandbox_data_availability_audit.md",
    "sandbox_do_not_run_now.md",
    "sandbox_next_action.md",
    "exploratory_sandbox_consistency_check.json",
]


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


def approved_symbols(root: Path) -> set[str]:
    data = load_yaml(root / APPROVED_SYMBOL_MAP_PATH)
    return {str(row.get("symbol")) for row in data.get("symbols", []) if row.get("allowed_for_strategy") or row.get("allowed_for_benchmark")}


def cache_symbols(root: Path) -> set[str]:
    path = root / DATA_CACHE_DIR
    if not path.exists():
        return set()
    return {item.stem for item in path.glob("*.csv")}


def cached_row_count(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", newline="", encoding="utf-8") as handle:
        return max(sum(1 for _line in handle) - 1, 0)


def universe_audit(root: Path) -> list[dict[str, Any]]:
    approved = approved_symbols(root)
    cached = cache_symbols(root)
    rows: list[dict[str, Any]] = []
    for group, symbols in UNIVERSE_GROUPS.items():
        present = [symbol for symbol in symbols if symbol in cached]
        approved_present = [symbol for symbol in present if symbol in approved]
        missing = [symbol for symbol in symbols if symbol not in cached]
        min_rows = min((cached_row_count(root / DATA_CACHE_DIR / f"{symbol}.csv") for symbol in present), default=0)
        rows.append(
            {
                "universe_group": group,
                "symbol_count": len(symbols),
                "cache_present_count": len(present),
                "approved_and_cache_present_count": len(approved_present),
                "cache_missing_symbols": ", ".join(missing),
                "locally_usable_symbols": ", ".join(approved_present),
                "min_cached_rows": min_rows,
                "group_available_for_future_sandbox": len(approved_present) >= max(2, min(len(symbols), 3)),
            }
        )
    return rows


def available_universe_count(rows: list[dict[str, Any]]) -> int:
    return sum(1 for row in rows if row["group_available_for_future_sandbox"])


def decide_next_action(rows: list[dict[str, Any]]) -> str:
    if available_universe_count(rows) >= 4 and len(ALLOWED_FAMILIES) <= MAX_FAMILIES_PER_RUN:
        return NEXT_ACTION_IMPLEMENT
    if available_universe_count(rows) >= 2:
        return NEXT_ACTION_REVIEW
    return NEXT_ACTION_PAUSE


def update_registry_metadata(root: Path, output: Path, created_utc: str, manifest: dict[str, Any]) -> bool:
    path = root / REGISTRY_PATH
    registry = load_yaml(path)
    before = deepcopy(registry.get("registry", {}))
    metadata = registry.setdefault("registry", {})
    metadata.update(
        {
            "exploratory_strategy_search_sandbox_preregistration_path": str(output.resolve()),
            "exploratory_strategy_search_sandbox_preregistration_status": "pre_registered",
            "exploratory_strategy_search_sandbox_preregistration_created_utc": created_utc,
            "current_research_mode": "exploratory_strategy_search_sandbox_preregistered",
            "current_next_action": manifest["next_action"],
            "official_current_next_action": manifest["next_action"],
            "next_action": manifest["next_action"],
            "sandbox_preregistration_only": True,
            "sandbox_results_non_promotable": True,
            "sandbox_can_create_paper_candidates": False,
            "sandbox_max_total_future_variants": MAX_TOTAL_FUTURE_VARIANTS,
            "sandbox_allowed_family_count": len(ALLOWED_FAMILIES),
            "sandbox_allowed_universe_count": len(UNIVERSE_GROUPS),
            "sandbox_allowed_indicator_count": len(ALLOWED_INDICATORS),
            "sandbox_available_universe_count": manifest["available_universe_count"],
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


def replace_or_append_section(text: str, header: str, section: str) -> str:
    if header not in text:
        return text.rstrip() + "\n\n" + section.rstrip() + "\n"
    start = text.index(header)
    next_start = text.find("\n## ", start + len(header))
    if next_start == -1:
        return text[:start].rstrip() + "\n\n" + section.rstrip() + "\n"
    return text[:start].rstrip() + "\n\n" + section.rstrip() + "\n\n" + text[next_start + 1 :].lstrip()


def update_roadmap(root: Path, output: Path, created_utc: str, manifest: dict[str, Any]) -> bool:
    path = root / ROADMAP_PATH
    before = path.read_text(encoding="utf-8") if path.exists() else "# Research Roadmap\n"
    compact = f"""## Compact Current State

- Updated UTC: `{created_utc}`
- Current research mode: `exploratory_strategy_search_sandbox_preregistered`
- Official current next action: `{manifest['next_action']}`
- Exploratory sandbox preregistration evidence: `{output.resolve()}`
- Design principle: `explore broadly, promote narrowly`
- Sandbox results are non-promotable: `true`
- Sandbox can create paper candidates: `false`
- Max total future variants: `{MAX_TOTAL_FUTURE_VARIANTS}`
- Allowed families: `{len(ALLOWED_FAMILIES)}`
- Allowed universe groups: `{len(UNIVERSE_GROUPS)}`
- Allowed indicators: `{len(ALLOWED_INDICATORS)}`
- Active VM and active DSR preserved.
- `static_all_weather_benchmark_v1` remains benchmark/control only.
- Exact rejected variants remain closed; old managed-futures top1/top2 rows remain historical context only.
- Intraday remains paused: `true`
- This preregistration did not run discovery, backtests, new metrics, provider download, intraday data, candidate_exhaustive, paper-forward action, broker/live path, or real-money recommendation.
"""
    section = f"""## Exploratory Strategy Search Sandbox Preregistration

- Created UTC: `{created_utc}`
- Evidence path: `{output.resolve()}`
- Sandbox-preregistration-only: `true`
- Purpose: broad opportunity-map building only.
- All future sandbox outputs must remain `non_promotable_exploration`.
- Max total future variants: `{MAX_TOTAL_FUTURE_VARIANTS}`
- Max families per future run: `{MAX_FAMILIES_PER_RUN}`
- Max variants per family: `{MAX_VARIANTS_PER_FAMILY}`
- Max parameter choices per indicator concept: `{MAX_PARAMETER_CHOICES_PER_INDICATOR}`
- Max universe groups per run: `{MAX_UNIVERSE_GROUPS_PER_RUN}`
- Max portfolio-combination variants: `{MAX_PORTFOLIO_COMBINATION_VARIANTS}`
- Next action: `{manifest['next_action']}`
- No sandbox exploration, strategy discovery, backtest, new strategy metric, dependency install, provider download, intraday data, candidate_exhaustive, paper-forward action, broker/live path, or real-money recommendation is authorized by this preregistration.
"""
    after = replace_or_append_section(before, "## Compact Current State", compact)
    after = replace_or_append_section(after, "## Exploratory Strategy Search Sandbox Preregistration", section)
    write_text(path, after)
    return before != after


def summary_md(created_utc: str, output: Path, manifest: dict[str, Any]) -> str:
    return f"""# Exploratory Strategy Search Sandbox Preregistration

Created UTC: `{created_utc}`

Evidence path: `{output.resolve()}`

Design principle: `explore broadly, promote narrowly`

Purpose: build a non-promotable opportunity map across families, universes, indicators, and portfolio-sleeve combinations.

Next action: `{manifest['next_action']}`

This preregistration creates no candidates and runs no discovery or backtests.
"""


def scope_md() -> str:
    return """# Sandbox Scope

The sandbox is an exploration layer only. It may later map many fixed, bounded exploratory variants across families, symbols, indicators, and sleeve combinations, but every output remains `non_promotable_exploration`.

The qualification layer is separate. Only a robust family-level finding can later justify a new formal preregistration of one simple representative rule.

The sandbox must not answer what to trade live, what to paper-forward immediately, which optimized parameter is best, or which single best backtest should be promoted.
"""


def universes_md(rows: list[dict[str, Any]]) -> str:
    lines = ["# Sandbox Allowed Universes", "", "Use local approved/cache-present daily data only. Missing symbols must not be downloaded.", ""]
    for row in rows:
        lines.append(f"## `{row['universe_group']}`")
        lines.append(f"- Locally usable symbols: `{row['locally_usable_symbols'] or 'none'}`")
        lines.append(f"- Cache missing from preregistered group: `{row['cache_missing_symbols'] or 'none'}`")
        lines.append(f"- Available for future sandbox: `{row['group_available_for_future_sandbox']}`")
        lines.append("")
    return "\n".join(lines)


def families_md() -> str:
    lines = ["# Sandbox Allowed Families", ""]
    for item in ALLOWED_FAMILIES:
        lines.append(f"## `{item['family']}`")
        for example in item["examples"]:
            lines.append(f"- {example}")
        lines.append("")
    return "\n".join(lines)


def indicators_md() -> str:
    allowed = "\n".join(f"- `{item}`" for item in ALLOWED_INDICATORS)
    forbidden = "\n".join(f"- `{item}`" for item in FORBIDDEN_INDICATORS)
    return f"""# Sandbox Allowed Indicators

Allowed validated custom indicators:

{allowed}

Forbidden indicators and methods:

{forbidden}

No indicator library dependency may be added by this preregistration.
"""


def limits_md() -> str:
    return f"""# Sandbox Variant Limits

- Maximum total sandbox variants per future run: `{MAX_TOTAL_FUTURE_VARIANTS}`
- Maximum families per future run: `{MAX_FAMILIES_PER_RUN}`
- Maximum variants per family: `{MAX_VARIANTS_PER_FAMILY}`
- Maximum parameter choices per indicator concept: `{MAX_PARAMETER_CHOICES_PER_INDICATOR}`
- Maximum universe groups per run: `{MAX_UNIVERSE_GROUPS_PER_RUN}`
- Maximum portfolio-combination variants: `{MAX_PORTFOLIO_COMBINATION_VARIANTS}`

The future runner must enforce these limits before any sandbox execution.
"""


def scoring_md() -> str:
    return """# Sandbox Scoring Framework

Future sandbox scoring is non-promotable and family-level:

- Family robustness score: consistency across nearby parameters, symbols, universes, and no one-symbol outlier dependence.
- Risk score: max drawdown, stop/risk-buffer behavior, volatility, and slippage/stress sensitivity.
- Benchmark score: same-window comparison versus SPY, QQQ, BIL, active VM, active DSR, active combo, and static all-weather where relevant.
- Diversification score: correlation versus active VM, active DSR, active combo, and contribution when combined.
- Practicality score: turnover, trade frequency, BIL/cash usage, data length, symbol availability, and execution simplicity.
- Overfitting risk score: sensitivity to parameter choice, number of tested variants, regime concentration, and limited-history dependence.

The score may identify families for later preregistration, but it cannot promote variants.
"""


def anti_overfitting_md() -> str:
    controls = [
        "Every result is `non_promotable_exploration`.",
        "Best single variant cannot be promoted.",
        "Parameter-grid winners cannot be promoted.",
        "Only family-level robustness can graduate to future preregistration.",
        "Future preregistration must freeze one simple representative rule.",
        "Exact rejected variants cannot be reopened.",
        "Indicators cannot be added to rescue a failed row.",
        "Risk gates cannot be weakened because exploration finds weak returns.",
        "Same-window benchmarks are required for all future sandbox results.",
        "Costs/slippage stress must be included in future sandbox scoring.",
        "Family robustness must be measured across nearby parameters and symbols.",
        "Portfolio-combination results must distinguish contribution from standalone alpha.",
        "Research-only leverage sensitivity cannot authorize leverage use.",
    ]
    return "# Sandbox Anti-Overfitting Controls\n\n" + "\n".join(f"- {item}" for item in controls)


def taxonomy_md() -> str:
    allowed = "\n".join(f"- `{item}`" for item in ALLOWED_SANDBOX_STATUSES)
    forbidden = "\n".join(f"- `{item}`" for item in FORBIDDEN_STATUSES)
    return f"""# Sandbox Status Taxonomy

Allowed future sandbox statuses:

{allowed}

Forbidden statuses:

{forbidden}

No sandbox status is a promotion approval.
"""


def graduation_md() -> str:
    rules = [
        "Multiple nearby parameter variants are positive.",
        "Multiple symbols or related universes support the behavior.",
        "Same-window benchmark comparison is not obviously weak.",
        "Slippage/stress does not fully destroy the signal.",
        "The family is not just a duplicate of active VM, active DSR, or active combo.",
        "The idea can be simplified into one frozen representative rule.",
        "The future step is a separate formal preregistration, not promotion.",
    ]
    return "# Sandbox Future Graduation Rules\n\nA sandbox family can graduate only if:\n\n" + "\n".join(f"- {item}" for item in rules)


def leverage_md() -> str:
    return """# Sandbox Research-Only Leverage Policy

Leverage sensitivity is allowed only as a future diagnostic:

- Research-only.
- Simulation-only.
- No broker, margin, live, or real-money use.
- Allowed sensitivity levels only if implemented later: `1.0x`, `1.25x`, `1.5x`, `2.0x`.
- Must report drawdown amplification.
- Must report stop-risk breach sensitivity.
- Must never convert a weak strategy into a promotion candidate by leverage alone.
- Leveraged result must be labeled `research_only_leverage_sensitivity_non_promotable`.
"""


def data_audit_md(rows: list[dict[str, Any]]) -> str:
    header = "| universe group | symbols | cache present | approved+cache | min cached rows | available | missing | usable |"
    sep = "|---|---:|---:|---:|---:|---:|---|---|"
    body = "\n".join(
        f"| `{row['universe_group']}` | {row['symbol_count']} | {row['cache_present_count']} | {row['approved_and_cache_present_count']} | {row['min_cached_rows']} | `{row['group_available_for_future_sandbox']}` | {row['cache_missing_symbols'] or 'none'} | {row['locally_usable_symbols'] or 'none'} |"
        for row in rows
    )
    return f"""# Sandbox Data Availability Audit

Local approved/cache-present daily data only. No symbols were downloaded.

{header}
{sep}
{body}

Available universe groups for future sandbox implementation: `{available_universe_count(rows)}`
"""


def do_not_run_md() -> str:
    return """# Sandbox Do Not Run Now

This preregistration does not authorize:

- sandbox exploration
- strategy discovery
- backtests
- new strategy performance metrics
- provider downloads
- intraday data
- indicator library installation
- candidate_exhaustive
- paper-forward review or activation
- broker/live-order paths
- real-money recommendations
"""


def next_action_md(next_action: str) -> str:
    return f"""# Sandbox Next Action

Exact next action: `{next_action}`

Do not run the next action in this preregistration task.
"""


def consistency_check(manifest: dict[str, Any], output: Path) -> dict[str, Any]:
    check = {
        "sandbox_preregistration_only": manifest["sandbox_preregistration_only"] is True,
        "no_strategy_discovery": manifest["strategy_discovery_run"] is False,
        "no_backtests": manifest["backtests_run"] is False,
        "no_new_performance_metrics": manifest["new_performance_metrics_computed"] is False,
        "no_indicator_library_dependency_added": manifest["indicator_library_dependency_added"] is False,
        "no_provider_download": manifest["provider_download"] is False,
        "no_intraday_data_used": manifest["intraday_data_used"] is False,
        "no_candidate_exhaustive": manifest["candidate_exhaustive_run"] is False,
        "no_paper_forward_action": manifest["paper_forward_review"] is False and manifest["paper_forward_activation"] is False,
        "no_broker_live_action": manifest["broker_orders_submitted"] is False and manifest["broker_orders_cancelled"] is False and manifest["live_orders"] is False,
        "no_real_money_recommendation": manifest["real_money_recommendation"] is False,
        "active_strategy_state_preserved": manifest["active_strategy_state_changed"] is False,
        "rejected_strategy_state_preserved": manifest["rejected_strategy_state_changed"] is False,
        "exact_rejected_variants_not_reopened": manifest["exact_rejected_variants_reopened"] is False,
        "intraday_remains_paused": manifest["intraday_research_remains_paused"] is True,
        "sandbox_results_non_promotable": manifest["sandbox_results_non_promotable"] is True,
        "sandbox_cannot_create_paper_candidates": manifest["sandbox_can_create_paper_candidates"] is False,
        "variant_limit_present_and_bounded": 0 < manifest["max_total_future_variants"] <= 200,
        "allowed_families_file_exists": (output / "sandbox_allowed_families.md").exists(),
        "allowed_universes_file_exists": (output / "sandbox_allowed_universes.md").exists(),
        "allowed_indicators_file_exists": (output / "sandbox_allowed_indicators.md").exists(),
        "scoring_framework_exists": (output / "sandbox_scoring_framework.md").exists(),
        "anti_overfitting_controls_exists": (output / "sandbox_anti_overfitting_controls.md").exists(),
        "status_taxonomy_exists": (output / "sandbox_status_taxonomy.md").exists(),
        "future_graduation_rules_exists": (output / "sandbox_future_graduation_rules.md").exists(),
        "research_only_leverage_policy_exists": (output / "sandbox_research_only_leverage_policy.md").exists(),
        "do_not_run_now_file_exists": (output / "sandbox_do_not_run_now.md").exists(),
        "next_action_valid": manifest["next_action"] in VALID_NEXT_ACTIONS,
        "manifest_flags_match_strict_scope": all(manifest.get(key) == value for key, value in MANIFEST_FLAGS.items()),
        "required_files_exist": all((output / name).exists() for name in REQUIRED_FILES),
    }
    check["consistency_passed"] = all(check.values())
    return check


def write_outputs(output: Path, created_utc: str, manifest: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    output.mkdir(parents=True, exist_ok=True)
    write_json(output / "exploratory_sandbox_preregistration_manifest.json", manifest)
    write_text(output / "exploratory_sandbox_summary.md", summary_md(created_utc, output, manifest))
    write_text(output / "sandbox_scope.md", scope_md())
    write_text(output / "sandbox_allowed_universes.md", universes_md(rows))
    write_text(output / "sandbox_allowed_families.md", families_md())
    write_text(output / "sandbox_allowed_indicators.md", indicators_md())
    write_text(output / "sandbox_variant_limits.md", limits_md())
    write_text(output / "sandbox_scoring_framework.md", scoring_md())
    write_text(output / "sandbox_anti_overfitting_controls.md", anti_overfitting_md())
    write_text(output / "sandbox_status_taxonomy.md", taxonomy_md())
    write_text(output / "sandbox_future_graduation_rules.md", graduation_md())
    write_text(output / "sandbox_research_only_leverage_policy.md", leverage_md())
    write_text(output / "sandbox_data_availability_audit.md", data_audit_md(rows))
    write_text(output / "sandbox_do_not_run_now.md", do_not_run_md())
    write_text(output / "sandbox_next_action.md", next_action_md(manifest["next_action"]))
    write_json(output / "exploratory_sandbox_consistency_check.json", {"consistency_passed": False})
    csv_path = output / "sandbox_data_availability_audit.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        fields = [
            "universe_group",
            "symbol_count",
            "cache_present_count",
            "approved_and_cache_present_count",
            "cache_missing_symbols",
            "locally_usable_symbols",
            "min_cached_rows",
            "group_available_for_future_sandbox",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def run_exploratory_strategy_search_sandbox_preregistration(root: Path = ROOT) -> dict[str, Any]:
    root = root.resolve()
    created_utc = now_utc()
    output = root / OUTPUT_DIR
    strategies_before = strategy_snapshot(root)
    rows = universe_audit(root)
    next_action = decide_next_action(rows)
    manifest = {
        "created_utc": created_utc,
        "output_dir": str(output.resolve()),
        **MANIFEST_FLAGS,
        "max_total_future_variants": MAX_TOTAL_FUTURE_VARIANTS,
        "max_families_per_run": MAX_FAMILIES_PER_RUN,
        "max_variants_per_family": MAX_VARIANTS_PER_FAMILY,
        "max_parameter_choices_per_indicator_concept": MAX_PARAMETER_CHOICES_PER_INDICATOR,
        "max_universe_groups_per_run": MAX_UNIVERSE_GROUPS_PER_RUN,
        "max_portfolio_combination_variants": MAX_PORTFOLIO_COMBINATION_VARIANTS,
        "allowed_family_count": len(ALLOWED_FAMILIES),
        "allowed_universe_count": len(UNIVERSE_GROUPS),
        "allowed_indicator_count": len(ALLOWED_INDICATORS),
        "available_universe_count": available_universe_count(rows),
        "next_action": next_action,
    }
    write_outputs(output, created_utc, manifest, rows)
    registry_updated = update_registry_metadata(root, output, created_utc, manifest)
    roadmap_updated = update_roadmap(root, output, created_utc, manifest)
    strategies_after = strategy_snapshot(root)
    if strategies_before != strategies_after:
        manifest["active_strategy_state_changed"] = True
        manifest["rejected_strategy_state_changed"] = True
    manifest["registry_metadata_updated"] = registry_updated
    manifest["roadmap_updated"] = roadmap_updated
    write_json(output / "exploratory_sandbox_preregistration_manifest.json", manifest)
    consistency = consistency_check(manifest, output)
    write_json(output / "exploratory_sandbox_consistency_check.json", consistency)
    return {
        "output_dir": str(output),
        "next_action": manifest["next_action"],
        "allowed_family_count": manifest["allowed_family_count"],
        "allowed_universe_count": manifest["allowed_universe_count"],
        "allowed_indicator_count": manifest["allowed_indicator_count"],
        "available_universe_count": manifest["available_universe_count"],
        "consistency_passed": consistency["consistency_passed"],
    }


def main() -> None:
    print(json.dumps(run_exploratory_strategy_search_sandbox_preregistration(ROOT), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
