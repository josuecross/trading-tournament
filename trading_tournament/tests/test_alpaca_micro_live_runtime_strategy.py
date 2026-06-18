from __future__ import annotations

import pytest

from execution_lab.alpaca_micro_live_v1.runtime_strategies.vm_quality_lowvol_proxy_v1 import (
    generate_signal_from_bars,
    load_strategy_spec,
)
from tests.alpaca_micro_live_fakes import make_bars_by_symbol

pytestmark = pytest.mark.alpaca_micro_live


def test_runtime_strategy_spec_loads() -> None:
    spec = load_strategy_spec()
    assert spec["strategy_id"] == "vm_quality_lowvol_proxy_v1"
    assert spec["portfolio"]["hold_top_n"] == 2
    assert spec["constraints"]["no_leverage"] is True


def test_signal_logic_selects_top_two_eligible_assets() -> None:
    signal = generate_signal_from_bars(make_bars_by_symbol(eligible=True))
    assert signal.fallback_triggered is False
    assert len(signal.selected_holdings) == 2
    assert set(signal.target_weights.values()) == {0.5}
    assert "BIL" not in signal.target_weights


def test_signal_logic_falls_back_to_bil_when_no_risk_assets_are_eligible() -> None:
    signal = generate_signal_from_bars(make_bars_by_symbol(eligible=False))
    assert signal.fallback_triggered is True
    assert signal.selected_holdings == ["BIL"]
    assert signal.target_weights == {"BIL": 1.0}
