from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from trading_tournament.execution_lab.alpaca_micro_live_v1.runtime_strategies.vm_quality_lowvol_proxy_v1 import (
    generate_signal_from_bars,
    load_strategy_spec,
)
from trading_tournament.execution_lab.alpaca_micro_live_v1.signals.generate_alpaca_signal import signal_to_target_dict


pytestmark = pytest.mark.alpaca_micro_live


def make_frame(start_price: float, end_price: float, days: int = 230) -> pd.DataFrame:
    start = date(2025, 1, 1)
    prices = np.linspace(start_price, end_price, days)
    return pd.DataFrame(
        {
            "date": [(start + timedelta(days=i)).isoformat() for i in range(days)],
            "open": prices,
            "high": prices,
            "low": prices,
            "close": prices,
            "volume": 1000,
        }
    )


def test_runtime_strategy_spec_loads():
    spec = load_strategy_spec()
    assert spec["strategy_id"] == "vm_quality_lowvol_proxy_v1"
    assert spec["constraints"]["long_only"] is True


def test_signal_generation_selects_top_two_and_target_yaml_validates():
    bars = {
        "SPLV": make_frame(120, 104),
        "USMV": make_frame(120, 108),
        "QUAL": make_frame(100, 130),
        "SPY": make_frame(100, 120),
        "BIL": make_frame(100, 101),
    }
    signal = generate_signal_from_bars(bars)
    assert set(signal.target_weights) == {"QUAL", "SPY"}
    assert signal.target_weights["QUAL"] == pytest.approx(0.5)
    assert signal.target_weights["SPY"] == pytest.approx(0.5)
    assert signal.metadata["strategy_logic_modified"] is False
    target = signal_to_target_dict(signal)
    assert target["target_source"] == "alpaca_runtime"
    assert target["metadata"]["adjustment"] == "all"


def test_signal_generation_falls_back_to_bil_when_no_risk_asset_eligible():
    bars = {
        "SPLV": make_frame(120, 90),
        "USMV": make_frame(120, 91),
        "QUAL": make_frame(120, 92),
        "SPY": make_frame(120, 93),
        "BIL": make_frame(100, 101),
    }
    signal = generate_signal_from_bars(bars)
    assert signal.fallback_triggered is True
    assert signal.target_weights == {"BIL": 1.0}
