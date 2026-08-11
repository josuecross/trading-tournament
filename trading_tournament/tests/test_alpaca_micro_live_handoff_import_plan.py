from __future__ import annotations

import pytest

from execution_lab.alpaca_micro_live_v1.handoff_import.calculator_registry import CalculatorRegistry
from execution_lab.alpaca_micro_live_v1.handoff_import.import_pipeline import load_packages, plan_rows
from execution_lab.alpaca_micro_live_v1.handoff_import.provider_registry import ProviderRegistry
from tests.alpaca_handoff_fake import write_fake_handoff_package

pytestmark = pytest.mark.alpaca_micro_live


def test_inventory_classifies_package_ids(tmp_path) -> None:
    write_fake_handoff_package(tmp_path, package_id="pkg_a", strategy_id="strategy_a")
    write_fake_handoff_package(tmp_path, package_id="pkg_b", strategy_id="strategy_b")
    packages = load_packages(tmp_path)
    assert {package.package_id for package in packages} == {"pkg_a", "pkg_b"}


def test_import_plan_reports_calculator_and_provider_gaps(tmp_path) -> None:
    write_fake_handoff_package(tmp_path, package_id="vix_pkg", instruments=["SPY", "VIX", "VIX3M"])
    packages = load_packages(tmp_path)
    rows = plan_rows(packages, CalculatorRegistry(), ProviderRegistry())
    assert rows[0]["calculator_status"] == "calculator_binding_missing"
    assert rows[0]["provider_status"] == "provider_adapter_missing"
