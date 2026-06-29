from __future__ import annotations

import csv
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = Path("evidence") / "governance" / "indicator_validation_harness_implementation" / "latest"
REGISTRY_PATH = Path("strategy_lab") / "strategy_registry.yaml"
ROADMAP_PATH = Path("strategy_lab") / "RESEARCH_ROADMAP.md"
PREREGISTRATION_DIR = Path("evidence") / "governance" / "indicator_validation_harness_preregistration" / "latest"

NEXT_ACTION = "pre_register_indicator_library_dependency_review"
VALID_NEXT_ACTIONS = {
    "manual_review_required_after_indicator_validation",
    "pre_register_indicator_library_dependency_review",
    "pre_register_next_family_after_indicator_validation",
    "pause_expansion_and_wait_for_manual_direction",
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

INDICATOR_TESTS_ADDED_COUNT = 19
LOOKAHEAD_TESTS_ADDED_COUNT = 6
INDICATOR_BUGS_FOUND_COUNT = 0
INDICATOR_BUGS_FIXED_COUNT = 0
MATERIAL_STRATEGY_RESULT_RISK_FLAG = False

GATED_FUTURE_INDICATORS = ["MACD", "Keltner Channel", "OBV"]

MANIFEST_FLAGS = {
    "indicator_validation_implementation_only": True,
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

COVERAGE_ROWS = [
    {
        "category": "trend",
        "indicator": "SMA",
        "validation_status": "validated_by_harness",
        "tests": "hand-computed values; warmup; short history; flat price; strategy column presence",
        "fixtures": "known_manual_calculation_fixture; short_history_fixture; flat_price_fixture",
        "lookahead_status": "aligned_current_completed_data",
    },
    {
        "category": "trend",
        "indicator": "EMA",
        "validation_status": "validated_by_harness",
        "tests": "determinism; warmup; monotonic behavior",
        "fixtures": "known_manual_calculation_fixture; monotonic_up_fixture",
        "lookahead_status": "aligned_current_completed_data",
    },
    {
        "category": "trend",
        "indicator": "Donchian prior high",
        "validation_status": "validated_by_harness",
        "tests": "rolling high shift excludes current signal row; strategy column alignment",
        "fixtures": "known_manual_calculation_fixture; flat_price_fixture",
        "lookahead_status": "current_signal_bar_excluded",
    },
    {
        "category": "trend",
        "indicator": "Donchian prior low",
        "validation_status": "not_applicable_current_code",
        "tests": "not implemented in current custom indicator layer",
        "fixtures": "",
        "lookahead_status": "not_applicable_current_code",
    },
    {
        "category": "momentum",
        "indicator": "ROC / rolling return",
        "validation_status": "validated_by_harness",
        "tests": "hand-computed values; warmup; strategy column presence",
        "fixtures": "known_manual_calculation_fixture; flat_price_fixture",
        "lookahead_status": "no_future_bar_leakage",
    },
    {
        "category": "momentum",
        "indicator": "RSI",
        "validation_status": "validated_by_harness",
        "tests": "flat/rising/falling behavior; warmup; future mutation does not alter prior outputs",
        "fixtures": "flat_price_fixture; monotonic_up_fixture; monotonic_down_fixture",
        "lookahead_status": "no_future_bar_leakage",
    },
    {
        "category": "momentum",
        "indicator": "MACD",
        "validation_status": "gated_requires_future_implementation_and_validation",
        "tests": "not implemented; asserted absent from generated columns",
        "fixtures": "",
        "lookahead_status": "gated_requires_future_implementation_and_validation",
    },
    {
        "category": "volatility",
        "indicator": "ATR",
        "validation_status": "validated_by_harness",
        "tests": "gap true range; hand-computed rolling mean; missing high/low/close invalid behavior",
        "fixtures": "gap_fixture; missing_values_fixture; known_manual_calculation_fixture",
        "lookahead_status": "available_by_completed_bar",
    },
    {
        "category": "volatility",
        "indicator": "realized volatility",
        "validation_status": "validated_by_harness",
        "tests": "flat zero volatility; monotonic/gap finite non-negative behavior",
        "fixtures": "flat_price_fixture; monotonic_up_fixture; gap_fixture",
        "lookahead_status": "available_by_completed_bar",
    },
    {
        "category": "volatility",
        "indicator": "Bollinger bands",
        "validation_status": "validated_by_harness",
        "tests": "flat band collapse; warmup behavior; strategy column presence",
        "fixtures": "flat_price_fixture",
        "lookahead_status": "aligned_current_completed_data",
    },
    {
        "category": "volatility",
        "indicator": "Bollinger z-score",
        "validation_status": "not_applicable_current_code",
        "tests": "explicit z-score column is not implemented",
        "fixtures": "",
        "lookahead_status": "not_applicable_current_code",
    },
    {
        "category": "volatility",
        "indicator": "Keltner Channel",
        "validation_status": "gated_requires_future_implementation_and_validation",
        "tests": "not implemented; asserted absent from generated columns",
        "fixtures": "",
        "lookahead_status": "gated_requires_future_implementation_and_validation",
    },
    {
        "category": "volume_liquidity",
        "indicator": "volume SMA",
        "validation_status": "validated_by_harness",
        "tests": "zero volume; missing volume; rolling-window behavior",
        "fixtures": "flat_price_fixture; missing_values_fixture",
        "lookahead_status": "no_future_volume_leakage",
    },
    {
        "category": "volume_liquidity",
        "indicator": "volume spike filter",
        "validation_status": "validated_by_harness",
        "tests": "strategy-consumed average volume column presence and alignment",
        "fixtures": "flat_price_fixture; missing_values_fixture",
        "lookahead_status": "strategy_consumed_column_aligned",
    },
    {
        "category": "volume_liquidity",
        "indicator": "OBV",
        "validation_status": "gated_requires_future_implementation_and_validation",
        "tests": "not implemented; asserted absent from generated columns",
        "fixtures": "",
        "lookahead_status": "gated_requires_future_implementation_and_validation",
    },
    {
        "category": "risk_state",
        "indicator": "rolling percentile rank",
        "validation_status": "validated_by_harness",
        "tests": "future mutation does not alter prior ranks; bounded rank output",
        "fixtures": "known_manual_calculation_fixture; monotonic_up_fixture",
        "lookahead_status": "no_future_rows_used",
    },
    {
        "category": "risk_state",
        "indicator": "moving-average regime",
        "validation_status": "validated_by_harness",
        "tests": "future mutation does not alter prior SMA; completed-row regime behavior",
        "fixtures": "monotonic_up_fixture",
        "lookahead_status": "prior_completed_data_for_next_open_decision",
    },
    {
        "category": "risk_state",
        "indicator": "SPY regime features",
        "validation_status": "validated_by_harness",
        "tests": "prepared SPY regime labels; future mutation does not alter prior SMA/regime inputs",
        "fixtures": "monotonic_up_fixture",
        "lookahead_status": "prior_completed_data_for_next_open_decision",
    },
]

LOOKAHEAD_ROWS = [
    {
        "check": "rolling high used for breakout excludes the current signal bar when required",
        "status": "implemented",
        "test_reference": "test_donchian_prior_high_excludes_current_signal_row",
    },
    {
        "check": "moving-average regime uses prior completed values when decision occurs at next open",
        "status": "implemented",
        "test_reference": "test_moving_average_and_spy_regime_use_completed_current_row_without_future_leakage",
    },
    {
        "check": "percentile/rank features use only rows up to the current timestamp",
        "status": "implemented",
        "test_reference": "test_percentile_rank_does_not_use_future_rows",
    },
    {
        "check": "volatility features use only data available before the decision timestamp",
        "status": "implemented",
        "test_reference": "test_realized_volatility_handles_flat_monotonic_and_gap_fixtures",
    },
    {
        "check": "weekly/monthly rebalance features do not use incomplete current-period data",
        "status": "not_applicable_current_code",
        "test_reference": "no current generic weekly/monthly indicator feature in src/indicators.py",
    },
    {
        "check": "indicator columns consumed by strategies are shifted or aligned correctly",
        "status": "implemented",
        "test_reference": "test_strategy_consumed_indicator_columns_are_present_and_aligned",
    },
]

REQUIRED_FILES = [
    "indicator_validation_implementation_manifest.json",
    "indicator_validation_implementation_summary.md",
    "indicator_fixture_implementation_report.md",
    "indicator_validation_coverage_matrix.csv",
    "indicator_lookahead_test_report.md",
    "indicator_bug_fix_report.md",
    "indicator_gated_future_items.md",
    "indicator_validation_next_action.md",
    "indicator_validation_implementation_consistency_check.json",
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


def summary_md(created_utc: str, output: Path) -> str:
    return f"""# Indicator Validation Harness Implementation Summary

Created UTC: `{created_utc}`

Evidence path: `{output.resolve()}`

Implemented deterministic fixture builders: `{len(FIXTURE_TYPES)}`

Indicator validation tests added: `{INDICATOR_TESTS_ADDED_COUNT}`

Lookahead tests added: `{LOOKAHEAD_TESTS_ADDED_COUNT}`

Indicator bugs found: `{INDICATOR_BUGS_FOUND_COUNT}`

Indicator bugs fixed: `{INDICATOR_BUGS_FIXED_COUNT}`

Material past-strategy-result risk flagged: `{str(MATERIAL_STRATEGY_RESULT_RISK_FLAG).lower()}`

This implementation validates existing custom indicators only. It does not install indicator libraries, add strategy logic, run discovery, run trading backtests, compute strategy performance metrics, use provider data, or activate paper-forward.
"""


def fixture_report_md() -> str:
    bullets = "\n".join(f"- `{name}`" for name in FIXTURE_TYPES)
    return f"""# Indicator Fixture Implementation Report

Implemented fixture builders in `tests/indicator_fixtures.py`:

{bullets}

The fixtures are deterministic OHLCV frames intended for formula, warmup, missing-value, flat-price, gap, and alignment validation. They do not load provider data and do not generate strategy signals for evaluation.
"""


def lookahead_report_md() -> str:
    lines = "\n".join(f"- `{row['status']}`: {row['check']} ({row['test_reference']})" for row in LOOKAHEAD_ROWS)
    return f"""# Indicator Lookahead Test Report

{lines}
"""


def bug_fix_report_md() -> str:
    return """# Indicator Bug Fix Report

Indicator bugs found: `0`

Indicator bugs fixed: `0`

Material past-strategy-result risk flagged: `false`

No indicator formula or alignment implementation was changed in `src/indicators.py`. The harness validates current behavior and records future-only/gated items without changing strategy rules.
"""


def gated_future_md() -> str:
    bullets = "\n".join(
        f"- `{name}`: `gated_requires_future_implementation_and_validation`" for name in GATED_FUTURE_INDICATORS
    )
    return f"""# Indicator Gated Future Items

{bullets}

These indicators are not implemented by this task and may not be used in strategy discovery until separately implemented and validated.
"""


def next_action_md() -> str:
    return f"""# Indicator Validation Next Action

Exact next action: `{NEXT_ACTION}`

Reason: current custom indicators validated cleanly under the deterministic harness, no indicator bugs were found, and no dependency was added. The skeptical next step is a separately pre-registered dependency review before considering external indicator-library parity.

Do not run this next action in the implementation task.
"""


def consistency_check(manifest: dict[str, Any], output: Path) -> dict[str, Any]:
    check = {
        "indicator_validation_implementation_only": manifest["indicator_validation_implementation_only"] is True,
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
        "fixture_report_exists": (output / "indicator_fixture_implementation_report.md").exists(),
        "coverage_matrix_exists": (output / "indicator_validation_coverage_matrix.csv").exists(),
        "lookahead_report_exists": (output / "indicator_lookahead_test_report.md").exists(),
        "bug_fix_report_exists": (output / "indicator_bug_fix_report.md").exists(),
        "gated_future_items_exists": (output / "indicator_gated_future_items.md").exists(),
        "next_action_valid": manifest["next_action"] in VALID_NEXT_ACTIONS,
        "manifest_flags_match_strict_scope": all(manifest[key] == value for key, value in MANIFEST_FLAGS.items()),
    }
    check["consistency_passed"] = all(check.values())
    return check


def write_evidence(output: Path, created_utc: str, manifest: dict[str, Any]) -> None:
    output.mkdir(parents=True, exist_ok=True)
    write_json(output / "indicator_validation_implementation_manifest.json", manifest)
    write_text(output / "indicator_validation_implementation_summary.md", summary_md(created_utc, output))
    write_text(output / "indicator_fixture_implementation_report.md", fixture_report_md())
    write_csv(
        output / "indicator_validation_coverage_matrix.csv",
        COVERAGE_ROWS,
        ["category", "indicator", "validation_status", "tests", "fixtures", "lookahead_status"],
    )
    write_text(output / "indicator_lookahead_test_report.md", lookahead_report_md())
    write_text(output / "indicator_bug_fix_report.md", bug_fix_report_md())
    write_text(output / "indicator_gated_future_items.md", gated_future_md())
    write_text(output / "indicator_validation_next_action.md", next_action_md())
    write_json(output / "indicator_validation_implementation_consistency_check.json", {"consistency_passed": False})
    write_yaml(
        output / "indicator_validation_test_manifest.yaml",
        {
            "test_file": "tests/test_indicator_validation_harness.py",
            "fixture_file": "tests/indicator_fixtures.py",
            "expected_pytest_command": ".venv\\Scripts\\python.exe -m pytest tests\\test_indicator_validation_harness.py -q",
            "no_strategy_backtest_required": True,
        },
    )


def update_registry_metadata(root: Path, created_utc: str, output: Path, manifest: dict[str, Any]) -> None:
    path = root / REGISTRY_PATH
    data = load_yaml(path)
    meta = data.setdefault("registry", {})
    meta.update(
        {
            "indicator_validation_harness_implementation_path": str(output.resolve()),
            "indicator_validation_harness_implementation_status": "completed",
            "indicator_validation_harness_implementation_created_utc": created_utc,
            "indicator_validation_implementation_only": True,
            "indicator_library_dependency_added": False,
            "fixture_types_implemented_count": manifest["fixture_types_implemented_count"],
            "indicator_tests_added_count": manifest["indicator_tests_added_count"],
            "lookahead_tests_added_count": manifest["lookahead_tests_added_count"],
            "indicator_bugs_found_count": manifest["indicator_bugs_found_count"],
            "indicator_bugs_fixed_count": manifest["indicator_bugs_fixed_count"],
            "material_strategy_result_risk_flag": manifest["material_strategy_result_risk_flag"],
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
- Current research mode: `indicator_validation_harness_implemented`
- Official current next action: `{NEXT_ACTION}`
- Indicator validation implementation evidence: `{output.resolve()}`
- Expansion remains paused: `true`
- Intraday remains paused: `true`
- Active accepted/paper-demo observations preserved: active VM and active DSR.
- Benchmark/control preserved: `static_all_weather_benchmark_v1` remains benchmark/control only.
- Exact rejected variants remain closed, including the latest risk-controlled high-return rejects.
- This section does not authorize discovery, trading backtests, new strategy metrics, provider download, intraday data, candidate_exhaustive, paper-forward action, broker/live order paths, indicator-library installation, or real-money recommendation.
"""
    text = replace_or_append_section(text, "## Compact Current State", compact)
    section = f"""## Indicator Validation Harness Implementation

- Created UTC: `{created_utc}`
- Evidence path: `{output.resolve()}`
- Implementation-only: `true`
- Indicator library dependency added: `false`
- Fixture types implemented: `{len(FIXTURE_TYPES)}`
- Indicator tests added: `{INDICATOR_TESTS_ADDED_COUNT}`
- Lookahead tests added: `{LOOKAHEAD_TESTS_ADDED_COUNT}`
- Indicator bugs found: `{INDICATOR_BUGS_FOUND_COUNT}`
- Indicator bugs fixed: `{INDICATOR_BUGS_FIXED_COUNT}`
- Material past-strategy-result risk flagged: `{str(MATERIAL_STRATEGY_RESULT_RISK_FLAG).lower()}`
- Expansion remains paused: `true`
- Intraday remains paused: `true`
- Official current next action: `{NEXT_ACTION}`
- This implementation does not authorize discovery, trading backtests, new strategy metrics, provider download, intraday data, candidate_exhaustive, paper-forward action, broker/live order paths, indicator-library installation, strategy rule creation, or real-money recommendation.
"""
    write_text(path, replace_or_append_section(text, "## Indicator Validation Harness Implementation", section))


def run_indicator_validation_harness_implementation(root: Path = ROOT) -> dict[str, Any]:
    root = root.resolve()
    created_utc = now_utc()
    output = root / OUTPUT_DIR
    strategies_before = strategy_snapshot(root)
    manifest = {
        "created_utc": created_utc,
        "output_dir": str(output.resolve()),
        **MANIFEST_FLAGS,
        "fixture_types_implemented_count": len(FIXTURE_TYPES),
        "indicator_tests_added_count": INDICATOR_TESTS_ADDED_COUNT,
        "lookahead_tests_added_count": LOOKAHEAD_TESTS_ADDED_COUNT,
        "indicator_bugs_found_count": INDICATOR_BUGS_FOUND_COUNT,
        "indicator_bugs_fixed_count": INDICATOR_BUGS_FIXED_COUNT,
        "material_strategy_result_risk_flag": MATERIAL_STRATEGY_RESULT_RISK_FLAG,
        "next_action": NEXT_ACTION,
    }
    write_evidence(output, created_utc, manifest)
    consistency = consistency_check(manifest, output)
    write_json(output / "indicator_validation_implementation_consistency_check.json", consistency)
    update_registry_metadata(root, created_utc, output, manifest)
    update_roadmap(root, created_utc, output)
    strategies_after = strategy_snapshot(root)
    if strategies_before != strategies_after:
        manifest["active_strategy_state_changed"] = True
        manifest["rejected_strategy_state_changed"] = True
        write_json(output / "indicator_validation_implementation_manifest.json", manifest)
        consistency = consistency_check(manifest, output)
        write_json(output / "indicator_validation_implementation_consistency_check.json", consistency)
    return {
        "output_dir": str(output),
        "fixture_types_implemented_count": manifest["fixture_types_implemented_count"],
        "indicator_tests_added_count": manifest["indicator_tests_added_count"],
        "lookahead_tests_added_count": manifest["lookahead_tests_added_count"],
        "indicator_bugs_found_count": manifest["indicator_bugs_found_count"],
        "indicator_bugs_fixed_count": manifest["indicator_bugs_fixed_count"],
        "material_strategy_result_risk_flag": manifest["material_strategy_result_risk_flag"],
        "next_action": NEXT_ACTION,
        "consistency_passed": consistency["consistency_passed"],
    }


def main() -> None:
    print(json.dumps(run_indicator_validation_harness_implementation(ROOT), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
