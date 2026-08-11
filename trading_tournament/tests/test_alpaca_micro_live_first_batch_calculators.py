from __future__ import annotations

from pathlib import Path

import pytest

from execution_lab.alpaca_micro_live_v1.handoff_import.calculators import (
    decelerated_psar_spy_bil,
    fallen_angel_angl,
    hyg_ema100_spy_bil,
    spy_trend_quality_state_d1,
)
from execution_lab.alpaca_micro_live_v1.handoff_import.manifest_loader import load_handoff_package
from tests.alpaca_handoff_fake import write_fake_handoff_package

pytestmark = pytest.mark.alpaca_micro_live


def test_first_batch_calculators_do_not_import_tournament_runners() -> None:
    for module in [fallen_angel_angl, hyg_ema100_spy_bil, decelerated_psar_spy_bil, spy_trend_quality_state_d1]:
        source = Path(module.__file__).read_text(encoding="utf-8")
        assert "trading_tournament" not in source
        assert "run_backtest" not in source
        assert "target_export" not in source


def test_calculator_output_shape_is_valid() -> None:
    result = fallen_angel_angl.generate_target_from_handoff_inputs({"event": "first_monthly_outer_rebalance"}, {"portfolio_construction": {"outer_targets": {"ANGL": 0.2, "FROZEN_REFERENCE": 0.8}}}, as_of="2000-01-31")
    assert result["strategy_id"] == "ice_vaneck_us_fallen_angel_angl_v1"
    assert result["as_of"] == "2000-01-31"
    assert result["target_source"] == "standard_v1_handoff_calculator"
    assert result["target_weights"] == {"ANGL": 0.2, "FROZEN_REFERENCE": 0.8}
    assert result["metadata"]["strategy_logic_modified"] is False
    assert result["metadata"]["blocked_reason"] is None


def test_missing_contract_field_blocks_implementation(tmp_path) -> None:
    package_root = write_fake_handoff_package(tmp_path)
    contract = package_root / "strategy_rule_contract.json"
    contract.write_text('{"identity": {"strategy_id": "fake_strategy_v1"}}', encoding="utf-8")
    package = load_handoff_package(package_root)
    assert "contract_missing_required_field" in package.classifications
