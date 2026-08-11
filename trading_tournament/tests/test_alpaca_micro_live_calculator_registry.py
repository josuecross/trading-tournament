from __future__ import annotations

import pytest

from execution_lab.alpaca_micro_live_v1.handoff_import.calculator_registry import CalculatorRegistry
from tests.alpaca_handoff_fake import fake_calculator

pytestmark = pytest.mark.alpaca_micro_live


def test_calculator_registry_reports_missing_binding_instead_of_guessing() -> None:
    assert CalculatorRegistry().classify("unknown_calculator_v1", "unknown_strategy") == "calculator_binding_missing"


def test_calculator_registry_can_register_fake_local_binding() -> None:
    registry = CalculatorRegistry()
    registry.register("fake_static_calculator_v1", "fake_strategy_v1", "tests.fake", calculate=fake_calculator)
    binding = registry.resolve("fake_static_calculator_v1", "fake_strategy_v1")
    assert binding is not None
    assert binding.calculate is fake_calculator
