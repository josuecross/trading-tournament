from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderClassification:
    status: str
    supported: list[str]
    missing: list[str]
    unsupported: list[str]


ETF_SYMBOLS = {
    "SPY", "BIL", "IEF", "TLT", "SHY", "AGG", "GLD", "GSG", "IYR", "TIP", "ANGL", "HYG",
    "SPLV", "USMV", "QUAL", "XLK", "XLF", "XLE", "XLV", "XLY", "XLP", "XLU", "XLI", "XLB", "XLC",
}


class ProviderRegistry:
    def classify(self, instruments: list[str], provider_requirements: list[str], data_fields: list[str] | None = None) -> ProviderClassification:
        supported: list[str] = []
        missing: list[str] = []
        unsupported: list[str] = []
        tokens = " ".join(instruments + provider_requirements + (data_fields or [])).lower()
        tokens = tokens.replace("frozen_current_active_vm_dsr_usci_combo", "frozen_reference_virtual_sleeve")
        if any(symbol in ETF_SYMBOLS for symbol in instruments) or "alpaca" in tokens or "close" in tokens:
            supported.append("alpaca_daily_equity_etf_bars")
        if any(token in tokens for token in ("vix", "vix3m")):
            missing.append("provider_adapter_required:vix_vix3m")
        if any(token in tokens for token in ("commodity", "usci")):
            missing.append("provider_adapter_required:commodity_curve_usci")
            unsupported.append("unsupported_asset_class:commodity_curve")
        if any(token in tokens for token in ("cpi", "inflation")):
            missing.append("provider_adapter_required:event_inflation")
        if "frozen_reference" in tokens:
            missing.append("provider_adapter_required:frozen_reference_virtual_sleeve")
        if unsupported:
            status = "unsupported_asset_class"
        elif missing:
            status = "provider_adapter_missing"
        else:
            status = "provider_binding_present"
        return ProviderClassification(status=status, supported=supported or ["alpaca_account_position_order_data"], missing=missing, unsupported=unsupported)

    def rows(self) -> list[dict[str, str]]:
        return [
            {"provider": "alpaca_daily_equity_etf_bars", "status": "supported", "note": "App-local Alpaca bar provider boundary exists."},
            {"provider": "alpaca_account_position_order_data", "status": "supported", "note": "Existing broker adapter supports account/position/order reads with safety gates elsewhere."},
            {"provider": "vix_vix3m", "status": "provider_adapter_required", "note": "No downloads implemented in this import task."},
            {"provider": "commodity_curve_usci", "status": "provider_adapter_required", "note": "No downloads implemented in this import task."},
            {"provider": "event_inflation", "status": "provider_adapter_required", "note": "SPDJ-style provider boundary requires owner review."},
        ]
