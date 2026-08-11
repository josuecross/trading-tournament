from __future__ import annotations

import json
from pathlib import Path
import inspect
from typing import Any

from execution_lab.alpaca_micro_live_v1.handoff_import.calculator_registry import CalculatorRegistry
from execution_lab.alpaca_micro_live_v1.handoff_import.contract_models import HandoffPackage


def _numbers_match(actual: Any, expected: Any, tolerance: float) -> bool:
    if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
        return abs(float(actual) - float(expected)) <= tolerance
    return actual == expected


def _mapping_matches(actual: dict[str, Any], expected: dict[str, Any], tolerance: float) -> bool:
    if set(actual) != set(expected):
        return False
    return all(_numbers_match(actual[key], expected[key], tolerance) for key in expected)


def _targets_match(actual: dict[str, Any], expected: dict[str, Any], absolute_tolerance: float = 0.0) -> bool:
    if actual.get("status") != expected.get("status"):
        return False
    if actual.get("effective_timestamp") != expected.get("effective_timestamp"):
        return False
    actual_weights = actual.get("target_weights", {})
    expected_weights = expected.get("target_weights", {})
    if not _mapping_matches(actual_weights, expected_weights, absolute_tolerance):
        return False
    if not _mapping_matches(actual.get("intermediate_calculations", {}), expected.get("intermediate_calculations", {}), absolute_tolerance):
        return False
    return True


def _calculate(binding, inputs: dict[str, Any], prior_state: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    if len(inspect.signature(binding.calculate).parameters) >= 3:
        return binding.calculate(inputs, prior_state, contract)
    return binding.calculate(inputs, prior_state)


def run_conformance(package: HandoffPackage, registry: CalculatorRegistry | None = None, output_dir: Path | None = None) -> dict[str, Any]:
    registry = registry or CalculatorRegistry()
    fixtures = package.fixtures.get("fixtures") if isinstance(package.fixtures, dict) else None
    if not fixtures:
        status = "fixture_missing"
        report = {"package_id": package.package_id, "strategy_id": package.strategy_id, "status": status, "results": []}
    else:
        binding = registry.resolve(package.calculator_type, package.strategy_id)
        if binding is None:
            status = "calculator_missing"
            report = {"package_id": package.package_id, "strategy_id": package.strategy_id, "status": status, "results": []}
        elif binding.calculate is None:
            status = "manual_review_required" if "manual" in binding.status else "calculator_missing"
            report = {"package_id": package.package_id, "strategy_id": package.strategy_id, "status": status, "results": [], "calculator_status": binding.status}
        else:
            results = []
            for fixture in fixtures:
                expected = fixture.get("expected", {})
                actual = _calculate(binding, fixture.get("inputs", {}), fixture.get("prior_state", {}), package.contract)
                passed = _targets_match(actual, expected, float(fixture.get("absolute_tolerance", 0.0) or 0.0))
                results.append({"fixture_id": fixture.get("fixture_id", ""), "passed": passed, "expected": expected, "actual": actual})
            status = "fixture_passed" if all(row["passed"] for row in results) else "fixture_failed"
            report = {"package_id": package.package_id, "strategy_id": package.strategy_id, "status": status, "results": results}
    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / f"{package.package_id}_conformance.json"
        path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        report["report_path"] = str(path)
    return report
