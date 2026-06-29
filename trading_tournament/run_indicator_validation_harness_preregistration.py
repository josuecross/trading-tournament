from __future__ import annotations

import csv
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = Path("evidence") / "governance" / "indicator_validation_harness_preregistration" / "latest"
REGISTRY_PATH = Path("strategy_lab") / "strategy_registry.yaml"
ROADMAP_PATH = Path("strategy_lab") / "RESEARCH_ROADMAP.md"
PRIOR_AUDIT_DIR = Path("evidence") / "governance" / "indicator_library_integration_audit" / "latest"
INDICATOR_CODE_PATH = Path("src") / "indicators.py"
STRATEGY_CODE_PATH = Path("src") / "strategies.py"
BACKTESTER_CODE_PATH = Path("src") / "backtester.py"
APPROVED_INDICATORS_PATH = Path("indicator_layer") / "approved_indicators.yaml"
INDICATOR_POLICY_PATH = Path("indicator_layer") / "indicator_policy.md"

NEXT_ACTION = "implement_indicator_validation_harness"
VALID_NEXT_ACTIONS = {
    "implement_indicator_validation_harness",
    "manual_review_required_for_indicator_validation_harness",
    "pause_expansion_and_wait_for_manual_direction",
}

MANIFEST_FLAGS = {
    "indicator_validation_preregistration_only": True,
    "indicator_library_dependency_added": False,
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

INDICATOR_CATEGORIES = {
    "trend": ["SMA", "EMA", "Donchian prior high / prior low"],
    "momentum": ["ROC / rolling return", "RSI", "MACD"],
    "volatility": ["ATR", "realized volatility", "Bollinger band / Bollinger z-score", "Keltner Channel"],
    "volume_liquidity": ["volume SMA", "volume spike filter", "OBV"],
    "risk_state": ["drawdown state", "volatility percentile", "moving-average regime", "SPY regime features"],
}

FIXTURE_TYPES = [
    "flat_price_fixture",
    "monotonic_up_fixture",
    "monotonic_down_fixture",
    "gap_fixture",
    "missing_values_fixture",
    "short_history_fixture",
    "known_manual_calculation_fixture",
]

LOOKAHEAD_CHECKS = [
    "rolling high used for breakout excludes the current signal bar when required",
    "moving-average regime uses prior completed data when strategy decision happens at next open",
    "percentile features do not include future rows",
    "volatility features use only data available before decision timestamp",
    "weekly/monthly rebalance features do not use incomplete current period data",
    "indicator columns consumed by strategy code are shifted or aligned correctly",
]

STATUS_ROWS = [
    {
        "category": "trend",
        "indicator": "SMA",
        "current_code_reference": "src/indicators.py:sma; add_indicators sma_5/sma_20/sma_50/sma_100/sma_200",
        "validation_status": "validation_planned",
        "fixture_types": "flat_price_fixture; monotonic_up_fixture; short_history_fixture; missing_values_fixture",
        "required_checks": "warmup; minimum-period; missing values; flat price; moving-average regime alignment",
        "notes": "Existing tests cover partial warmup behavior; full harness still planned.",
    },
    {
        "category": "trend",
        "indicator": "EMA",
        "current_code_reference": "src/indicators.py:ema; add_indicators ema_10",
        "validation_status": "validation_planned",
        "fixture_types": "flat_price_fixture; monotonic_up_fixture; short_history_fixture; missing_values_fixture",
        "required_checks": "warmup; minimum-period; monotonic behavior; missing values",
        "notes": "Existing tests cover partial warmup behavior; full harness still planned.",
    },
    {
        "category": "trend",
        "indicator": "Donchian prior high / prior low",
        "current_code_reference": "src/indicators.py:rolling_high; add_indicators high_20",
        "validation_status": "validation_planned",
        "fixture_types": "monotonic_up_fixture; known_manual_calculation_fixture; short_history_fixture",
        "required_checks": "shifted prior high; prior low future extension; no current-bar leakage",
        "notes": "Prior high exists; prior low is planned if future lane needs it.",
    },
    {
        "category": "momentum",
        "indicator": "ROC / rolling return",
        "current_code_reference": "src/indicators.py:rolling_return; add_indicators ret_63/ret_126/ret_252",
        "validation_status": "validation_planned",
        "fixture_types": "known_manual_calculation_fixture; flat_price_fixture; monotonic_up_fixture; missing_values_fixture",
        "required_checks": "hand-computed output; warmup; flat price; monotonic price; no future-bar leakage",
        "notes": "Used by ranking strategies; validation must lock shift/alignment.",
    },
    {
        "category": "momentum",
        "indicator": "RSI",
        "current_code_reference": "src/indicators.py:rsi; add_indicators rsi_2",
        "validation_status": "validation_planned",
        "fixture_types": "flat_price_fixture; monotonic_up_fixture; monotonic_down_fixture; missing_values_fixture",
        "required_checks": "known fixture; warmup; flat price; monotonic behavior; missing values",
        "notes": "Existing tests cover partial warmup behavior; neutral/edge behavior needs preregistered fixtures.",
    },
    {
        "category": "momentum",
        "indicator": "MACD",
        "current_code_reference": "not currently implemented",
        "validation_status": "gated_requires_validation",
        "fixture_types": "known_manual_calculation_fixture; short_history_fixture",
        "required_checks": "EMA parity; warmup; no future-bar leakage",
        "notes": "Future-only gated indicator; not allowed in discovery before validation.",
    },
    {
        "category": "volatility",
        "indicator": "ATR",
        "current_code_reference": "src/indicators.py:atr; add_indicators atr_10/atr_20",
        "validation_status": "validation_planned",
        "fixture_types": "gap_fixture; known_manual_calculation_fixture; short_history_fixture; missing_values_fixture",
        "required_checks": "hand-computed true range; gap behavior; missing high/low/close; min-period behavior",
        "notes": "Existing tests cover partial warmup behavior; gap and missing-value behavior still planned.",
    },
    {
        "category": "volatility",
        "indicator": "realized volatility",
        "current_code_reference": "src/indicators.py:realized_volatility; add_indicators rv_20/rv_60",
        "validation_status": "validation_planned",
        "fixture_types": "flat_price_fixture; gap_fixture; known_manual_calculation_fixture; short_history_fixture",
        "required_checks": "zero volatility; hand-computed returns; min-period; timing alignment",
        "notes": "Used for score/risk-state logic; future harness must pin annualization.",
    },
    {
        "category": "volatility",
        "indicator": "Bollinger band / Bollinger z-score",
        "current_code_reference": "src/indicators.py:bollinger_bands; add_indicators bb_mid/bb_upper/bb_lower",
        "validation_status": "validation_planned",
        "fixture_types": "flat_price_fixture; known_manual_calculation_fixture; short_history_fixture",
        "required_checks": "zero-volatility band collapse; min-period; missing close behavior",
        "notes": "Bands exist; z-score output is a future planned validation target.",
    },
    {
        "category": "volatility",
        "indicator": "Keltner Channel",
        "current_code_reference": "not currently implemented",
        "validation_status": "gated_requires_validation",
        "fixture_types": "gap_fixture; known_manual_calculation_fixture",
        "required_checks": "ATR dependency parity; warmup; missing high/low/close behavior",
        "notes": "Future-only gated indicator; not allowed in discovery before validation.",
    },
    {
        "category": "volume_liquidity",
        "indicator": "volume SMA",
        "current_code_reference": "src/indicators.py:add_indicators avg_volume_20",
        "validation_status": "validation_planned",
        "fixture_types": "flat_price_fixture; missing_values_fixture; short_history_fixture",
        "required_checks": "zero volume; missing volume; rolling-window behavior; no future volume leakage",
        "notes": "Consumed by breakout/volume filter logic.",
    },
    {
        "category": "volume_liquidity",
        "indicator": "volume spike filter",
        "current_code_reference": "src/strategies.py volume > multiple * avg_volume_20",
        "validation_status": "validation_planned",
        "fixture_types": "flat_price_fixture; missing_values_fixture; known_manual_calculation_fixture",
        "required_checks": "zero volume; missing volume; threshold behavior; alignment to signal date",
        "notes": "Filter logic is strategy consumption of avg_volume_20; no new strategy rule is added here.",
    },
    {
        "category": "volume_liquidity",
        "indicator": "OBV",
        "current_code_reference": "not currently implemented",
        "validation_status": "gated_requires_validation",
        "fixture_types": "known_manual_calculation_fixture; missing_values_fixture",
        "required_checks": "directional volume accumulation; missing volume; flat close behavior",
        "notes": "Future-only gated indicator; not allowed in discovery before validation.",
    },
    {
        "category": "risk_state",
        "indicator": "drawdown state",
        "current_code_reference": "src/metrics.py and src/backtester.py drawdown calculations",
        "validation_status": "validation_planned",
        "fixture_types": "monotonic_down_fixture; monotonic_up_fixture; known_manual_calculation_fixture",
        "required_checks": "drawdown reset behavior; peak tracking; missing equity/price behavior",
        "notes": "Risk-state diagnostic target; not a new strategy feature.",
    },
    {
        "category": "risk_state",
        "indicator": "volatility percentile",
        "current_code_reference": "src/indicators.py:rolling_percentile_rank; add_indicators atr_10_percentile",
        "validation_status": "validation_planned",
        "fixture_types": "flat_price_fixture; gap_fixture; short_history_fixture; missing_values_fixture",
        "required_checks": "percentile warmup; no future rows; missing values; rank tie behavior",
        "notes": "Must pin pandas-version behavior where rolling rank availability differs.",
    },
    {
        "category": "risk_state",
        "indicator": "moving-average regime",
        "current_code_reference": "src/strategies.py close > sma_200 checks; src/indicators.py _spy_regime",
        "validation_status": "validation_planned",
        "fixture_types": "monotonic_up_fixture; monotonic_down_fixture; short_history_fixture",
        "required_checks": "regime threshold behavior; prior-completed-data timing; missing benchmark behavior",
        "notes": "Harness must verify decision-time alignment for next-open assumptions.",
    },
    {
        "category": "risk_state",
        "indicator": "SPY regime features",
        "current_code_reference": "src/indicators.py:_spy_regime; prepare_indicators",
        "validation_status": "validation_planned",
        "fixture_types": "flat_price_fixture; monotonic_down_fixture; missing_values_fixture; short_history_fixture",
        "required_checks": "regime labels; volatility quantile warmup; missing SPY behavior; prior-completed-data timing",
        "notes": "SPY rv threshold currently shifts q75 output; full regime label timing still needs harness coverage.",
    },
]

REQUIRED_FILES = [
    "indicator_validation_harness_manifest.json",
    "indicator_validation_harness_summary.md",
    "indicator_validation_scope.md",
    "indicator_fixture_plan.md",
    "indicator_lookahead_prevention_plan.md",
    "indicator_validation_status_matrix.csv",
    "indicator_parity_test_policy.md",
    "indicator_validation_do_not_run_now.md",
    "indicator_validation_next_action.md",
    "indicator_validation_harness_consistency_check.json",
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


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


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


def summary_md(created_utc: str, output: Path, prior: dict[str, Any]) -> str:
    prior_decision = prior.get("dependency_decision", "unknown")
    prior_library = prior.get("selected_library", "unknown")
    return f"""# Indicator Validation Harness Preregistration Summary

Created UTC: `{created_utc}`

Evidence path: `{output.resolve()}`

Prior indicator-library audit decision: `{prior_decision}`

Selected indicator path: `{prior_library}`

This packet pre-registers a deterministic validation harness for current custom indicators. It defines fixture types, lookahead checks, warmup/minimum-period checks, missing-value checks, and future parity-test requirements.

No indicator library is installed, no strategy logic is added, and no discovery or backtest is run.
"""


def scope_md() -> str:
    categories = "\n".join(
        f"- `{category}`: " + ", ".join(f"`{indicator}`" for indicator in indicators)
        for category, indicators in INDICATOR_CATEGORIES.items()
    )
    return f"""# Indicator Validation Scope

Covered indicator categories:

{categories}

Strategy consumption points to cover in the future harness:

- `src/indicators.py`: formula generation and indicator-column preparation.
- `src/strategies.py`: `indicators_ready` checks, ranking inputs, breakout thresholds, volume filters, exits, stops, and regime filters.
- `src/backtester.py`: signal metadata export and indicator-column mapping.

This preregistration does not implement strategy rules, generate trading signals for evaluation, or compute performance metrics.
"""


def fixture_plan_md() -> str:
    return """# Indicator Fixture Plan

- `flat_price_fixture`: constant OHLCV; tests zero momentum, zero/near-zero volatility, stable bands, zero-volume variants, and edge RSI behavior.
- `monotonic_up_fixture`: steadily rising close; tests ROC, SMA/EMA ordering, RSI, prior high, breakout timing, and moving-average regime.
- `monotonic_down_fixture`: steadily falling close; tests drawdown, RSI, trend/regime transitions, and moving-average regime.
- `gap_fixture`: open/high/low/close gaps; tests ATR true range, realized volatility response, and gap-sensitive missing behavior.
- `missing_values_fixture`: controlled missing OHLCV values; tests null handling and forced invalid indicator outputs.
- `short_history_fixture`: fewer rows than required lookback; tests warmup/minimum-period behavior.
- `known_manual_calculation_fixture`: small hand-computed fixture; tests exact SMA, ROC, ATR, realized volatility, and Donchian prior high.
"""


def lookahead_plan_md() -> str:
    checks = "\n".join(f"- {check}" for check in LOOKAHEAD_CHECKS)
    return f"""# Indicator Lookahead Prevention Plan

The future validation harness must explicitly test:

{checks}

Any future strategy using indicator columns must document whether its decision occurs on the close, at next open, weekly rebalance, or monthly rebalance, and the harness must assert the indicator value was knowable at that decision time.
"""


def parity_policy_md() -> str:
    return """# Indicator Parity Test Policy

No new indicator library is installed in this preregistration.

If a library is later approved, every library indicator used must be parity-tested against:

- the current custom implementation, or
- a hand-computed fixture, or
- both when the indicator already exists in `src/indicators.py`.

Library indicators may not be used in strategy discovery until parity tests pass. Parity tests must pin warmup behavior, missing-value behavior, parameter names/defaults, output alignment, and lookahead-sensitive shifts.
"""


def do_not_run_md() -> str:
    return """# Indicator Validation Do Not Run Now

This preregistration does not authorize:

- installing `ta`, `pandas-ta-classic`, `TA-Lib`, `vectorbt`, or any new library
- strategy discovery
- backtests
- strategy performance metrics
- new strategy candidates
- indicator strategy rules
- parameter grids
- trading-signal generation for strategy evaluation
- provider downloads
- intraday data use
- paper-forward review or activation
- broker/live-order code changes
- real-money recommendations
"""


def next_action_md() -> str:
    return f"""# Indicator Validation Next Action

Exact next action: `{NEXT_ACTION}`

Reason: the harness scope is clear, bounded, and testable with synthetic fixtures. Implementation should add deterministic unit tests for current custom indicators before any dependency replacement or indicator-based strategy work.

Do not run this next action in the preregistration task.
"""


def update_registry_metadata(root: Path, created_utc: str, output: Path, manifest: dict[str, Any]) -> None:
    path = root / REGISTRY_PATH
    data = load_yaml(path)
    meta = data.setdefault("registry", {})
    meta.update(
        {
            "indicator_validation_harness_preregistration_path": str(output.resolve()),
            "indicator_validation_harness_preregistration_status": "pre_registered",
            "indicator_validation_harness_preregistration_created_utc": created_utc,
            "indicator_validation_preregistration_only": True,
            "indicator_library_dependency_added": False,
            "fixture_types_count": manifest["fixture_types_count"],
            "indicator_categories_count": manifest["indicator_categories_count"],
            "lookahead_checks_defined": manifest["lookahead_checks_defined"],
            "parity_policy_defined": True,
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
- Current research mode: `indicator_validation_harness_preregistered`
- Official current next action: `{NEXT_ACTION}`
- Indicator validation preregistration evidence: `{output.resolve()}`
- Expansion remains paused: `true`
- Intraday remains paused: `true`
- Active accepted/paper-demo observations preserved: active VM and active DSR.
- Benchmark/control preserved: `static_all_weather_benchmark_v1` remains benchmark/control only.
- Exact rejected variants remain closed, including the latest risk-controlled high-return rejects.
- This section does not authorize discovery, backtests, new metrics, provider download, intraday data, candidate_exhaustive, paper-forward action, broker/live order paths, indicator-library installation, or real-money recommendation.
"""
    text = replace_or_append_section(text, "## Compact Current State", compact)
    section = f"""## Indicator Validation Harness Preregistration

- Created UTC: `{created_utc}`
- Evidence path: `{output.resolve()}`
- Preregistration-only: `true`
- Indicator library dependency added: `false`
- Fixture types defined: `{len(FIXTURE_TYPES)}`
- Indicator categories covered: `{len(INDICATOR_CATEGORIES)}`
- Lookahead checks defined: `{len(LOOKAHEAD_CHECKS)}`
- Parity-test policy defined: `true`
- Expansion remains paused: `true`
- Intraday remains paused: `true`
- Official current next action: `{NEXT_ACTION}`
- This preregistration does not authorize discovery, backtests, new metrics, provider download, intraday data, candidate_exhaustive, paper-forward action, broker/live order paths, indicator-library installation, strategy rule creation, or real-money recommendation.
"""
    write_text(path, replace_or_append_section(text, "## Indicator Validation Harness Preregistration", section))


def consistency_check(manifest: dict[str, Any], output: Path) -> dict[str, Any]:
    check = {
        "indicator_validation_preregistration_only": manifest["indicator_validation_preregistration_only"] is True,
        "no_indicator_library_dependency_added": manifest["indicator_library_dependency_added"] is False,
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
        "fixture_plan_exists": (output / "indicator_fixture_plan.md").exists(),
        "lookahead_prevention_plan_exists": (output / "indicator_lookahead_prevention_plan.md").exists(),
        "indicator_validation_status_matrix_exists": (output / "indicator_validation_status_matrix.csv").exists(),
        "parity_test_policy_exists": (output / "indicator_parity_test_policy.md").exists(),
        "do_not_run_now_file_exists": (output / "indicator_validation_do_not_run_now.md").exists(),
        "next_action_valid": manifest["next_action"] in VALID_NEXT_ACTIONS,
        "manifest_flags_match_strict_scope": all(manifest[key] == value for key, value in MANIFEST_FLAGS.items()),
    }
    check["consistency_passed"] = all(check.values())
    return check


def write_evidence(root: Path, output: Path, created_utc: str, manifest: dict[str, Any], prior: dict[str, Any]) -> None:
    output.mkdir(parents=True, exist_ok=True)
    write_json(output / "indicator_validation_harness_manifest.json", manifest)
    write_text(output / "indicator_validation_harness_summary.md", summary_md(created_utc, output, prior))
    write_text(output / "indicator_validation_scope.md", scope_md())
    write_text(output / "indicator_fixture_plan.md", fixture_plan_md())
    write_text(output / "indicator_lookahead_prevention_plan.md", lookahead_plan_md())
    write_csv(
        output / "indicator_validation_status_matrix.csv",
        STATUS_ROWS,
        ["category", "indicator", "current_code_reference", "validation_status", "fixture_types", "required_checks", "notes"],
    )
    write_text(output / "indicator_parity_test_policy.md", parity_policy_md())
    write_text(output / "indicator_validation_do_not_run_now.md", do_not_run_md())
    write_text(output / "indicator_validation_next_action.md", next_action_md())
    write_json(output / "indicator_validation_harness_consistency_check.json", {"consistency_passed": False})
    write_yaml(
        output / "indicator_validation_harness_preregistration_context.yaml",
        {
            "source_files_reviewed": [
                str(INDICATOR_CODE_PATH),
                str(STRATEGY_CODE_PATH),
                str(BACKTESTER_CODE_PATH),
                str(APPROVED_INDICATORS_PATH),
                str(INDICATOR_POLICY_PATH),
                str(PRIOR_AUDIT_DIR),
            ],
            "no_strategy_code_changed": True,
            "no_dependency_installed": True,
        },
    )


def run_indicator_validation_harness_preregistration(root: Path = ROOT) -> dict[str, Any]:
    root = root.resolve()
    created_utc = now_utc()
    output = root / OUTPUT_DIR
    strategies_before = strategy_snapshot(root)
    prior = load_json(root / PRIOR_AUDIT_DIR / "indicator_library_audit_manifest.json")
    manifest = {
        "created_utc": created_utc,
        "output_dir": str(output.resolve()),
        **MANIFEST_FLAGS,
        "fixture_types_count": len(FIXTURE_TYPES),
        "indicator_categories_count": len(INDICATOR_CATEGORIES),
        "lookahead_checks_defined": len(LOOKAHEAD_CHECKS),
        "parity_policy_defined": True,
        "next_action": NEXT_ACTION,
    }
    write_evidence(root, output, created_utc, manifest, prior)
    consistency = consistency_check(manifest, output)
    write_json(output / "indicator_validation_harness_consistency_check.json", consistency)
    update_registry_metadata(root, created_utc, output, manifest)
    update_roadmap(root, created_utc, output)
    strategies_after = strategy_snapshot(root)
    if strategies_before != strategies_after:
        manifest["active_strategy_state_changed"] = True
        manifest["rejected_strategy_state_changed"] = True
        write_json(output / "indicator_validation_harness_manifest.json", manifest)
        consistency = consistency_check(manifest, output)
        write_json(output / "indicator_validation_harness_consistency_check.json", consistency)
    return {
        "output_dir": str(output),
        "fixture_types_count": manifest["fixture_types_count"],
        "indicator_categories_count": manifest["indicator_categories_count"],
        "lookahead_checks_defined": manifest["lookahead_checks_defined"],
        "parity_policy_defined": manifest["parity_policy_defined"],
        "next_action": NEXT_ACTION,
        "consistency_passed": consistency["consistency_passed"],
    }


def main() -> None:
    print(json.dumps(run_indicator_validation_harness_preregistration(ROOT), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
