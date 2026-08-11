from __future__ import annotations

import pytest

from execution_lab.alpaca_micro_live_v1.handoff_import.calculator_registry import CalculatorRegistry
from execution_lab.alpaca_micro_live_v1.handoff_import.conformance import run_conformance
from execution_lab.alpaca_micro_live_v1.handoff_import.manifest_loader import load_handoff_package
from tests.alpaca_handoff_fake import fake_calculator, write_fake_handoff_package

pytestmark = pytest.mark.alpaca_micro_live


def _registry(calculate=fake_calculator) -> CalculatorRegistry:
    registry = CalculatorRegistry()
    registry.register("fake_static_calculator_v1", "fake_strategy_v1", "tests.fake", calculate=calculate)
    return registry


def test_conformance_fixture_passes_when_fake_calculator_matches_expected(tmp_path) -> None:
    package = load_handoff_package(write_fake_handoff_package(tmp_path))
    result = run_conformance(package, _registry(), tmp_path / "reports")
    assert result["status"] == "fixture_passed"


def test_conformance_fixture_fails_on_mismatch(tmp_path) -> None:
    package = load_handoff_package(write_fake_handoff_package(tmp_path))
    result = run_conformance(package, _registry(lambda _inputs, _state: {"status": "target_calculated", "target_weights": {"BIL": 1.0}}))
    assert result["status"] == "fixture_failed"


def test_conformance_blocks_when_fixture_missing(tmp_path) -> None:
    package = load_handoff_package(write_fake_handoff_package(tmp_path, include_fixture=False))
    result = run_conformance(package, _registry())
    assert result["status"] == "fixture_missing"
