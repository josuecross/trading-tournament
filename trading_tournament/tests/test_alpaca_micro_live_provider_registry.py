from __future__ import annotations

import pytest

from execution_lab.alpaca_micro_live_v1.handoff_import.provider_registry import ProviderRegistry

pytestmark = pytest.mark.alpaca_micro_live


def test_provider_registry_classifies_alpaca_supported_etf_data() -> None:
    result = ProviderRegistry().classify(["SPY", "BIL"], ["alpaca"], ["adjusted_close"])
    assert result.status == "provider_binding_present"
    assert "alpaca_daily_equity_etf_bars" in result.supported


def test_provider_registry_classifies_vix_adapter_required() -> None:
    result = ProviderRegistry().classify(["SPY", "IEF", "VIX", "VIX3M"], ["vix", "vix3m"], ["close"])
    assert result.status == "provider_adapter_missing"
    assert "provider_adapter_required:vix_vix3m" in result.missing


def test_provider_registry_classifies_usci_commodity_adapter_required() -> None:
    result = ProviderRegistry().classify(["USCI"], ["commodity"], ["curve"])
    assert result.status == "unsupported_asset_class"
    assert "provider_adapter_required:commodity_curve_usci" in result.missing
