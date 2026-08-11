from __future__ import annotations

import pytest
import yaml

from execution_lab.alpaca_micro_live_v1.execution.implement_first_batch_calculators import run_first_batch
from execution_lab.alpaca_micro_live_v1.handoff_import.calculator_registry import CalculatorRegistry
from tests.test_alpaca_micro_live_first_batch_conformance import _write_ice_fake

pytestmark = pytest.mark.alpaca_micro_live


def test_registry_binding_records_calculator_presence_without_enabling_runtime() -> None:
    binding = CalculatorRegistry().resolve("angl_80_20_monthly_calculator_v1", "ice_vaneck_us_fallen_angel_angl_v1")
    assert binding is not None
    assert binding.status == "calculator_binding_present_fixture_pending"
    assert "handoff_import.calculators" in binding.module_path


def test_first_batch_command_does_not_enable_generated_or_active_runtime(tmp_path) -> None:
    _write_ice_fake(tmp_path / "handoffs")
    run_first_batch(
        handoff_root=tmp_path / "handoffs",
        evidence_dir=tmp_path / "evidence",
        conformance_dir=tmp_path / "conformance",
        generated_spec_dir=tmp_path / "generated",
        dry_run=False,
        write_bindings=True,
        run_conformance_gate=True,
    )
    spec = yaml.safe_load((tmp_path / "generated" / "ice_vaneck_us_fallen_angel_angl_v1.yaml").read_text(encoding="utf-8"))
    safety = (tmp_path / "evidence" / "safety_check.json").read_text(encoding="utf-8")
    assert spec["enabled"] is False
    assert spec["runtime_ready"] is False
    assert spec["paper_trading_allowed"] is False
    assert spec["live_trading_allowed"] is False
    assert '"paper_orders_submitted": false' in safety
    assert '"live_orders_submitted": false' in safety
    assert '"broker_network_calls": false' in safety


def test_existing_vm_dsr_runtime_registry_behavior_unchanged() -> None:
    registry = yaml.safe_load(open("execution_lab/alpaca_micro_live_v1/runtime_strategies/runtime_strategy_registry.yaml", encoding="utf-8"))
    assert registry["strategies"]["vm_quality_lowvol_proxy_v1"]["enabled"] is True
    assert registry["strategies"]["vm_quality_lowvol_proxy_v1"]["runtime_ready"] is True
    assert registry["strategies"]["dsr_sector_equal_weight_defensive_filter_v1"]["enabled"] is True
    assert registry["strategies"]["dsr_sector_equal_weight_defensive_filter_v1"]["runtime_ready"] is True
