from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class CalculatorBinding:
    calculator_type: str
    strategy_id: str
    module_path: str
    status: str
    calculate: Callable[..., dict[str, Any]] | None = None
    note: str = ""


class CalculatorRegistry:
    def __init__(self) -> None:
        self._bindings: dict[str, CalculatorBinding] = {}
        self.register(
            "vm_quality_lowvol_proxy_v1",
            "vm_quality_lowvol_proxy_v1",
            "execution_lab.alpaca_micro_live_v1.runtime_strategies.vm_quality_lowvol_proxy_v1",
            status="calculator_binding_present_manual_adapter_required",
        )
        self.register(
            "dsr_sector_equal_weight_defensive_filter_v1",
            "dsr_sector_equal_weight_defensive_filter_v1",
            "execution_lab.alpaca_micro_live_v1.runtime_strategies.dsr_sector_equal_weight_defensive_filter_v1",
            status="calculator_binding_present_manual_adapter_required",
        )
        self.register(
            "spdj_dynamic_inflation_calculator_v1",
            "spdj_multi_asset_dynamic_inflation_etf_portability_v1",
            "execution_lab.alpaca_micro_live_v1.standard_handoff.spdj_calculator",
            status="manual_review_required",
            note="SPDJ pilot calculator exists, but runtime provider/timing acceptance is not automatic.",
        )
        self.register(
            "angl_80_20_monthly_calculator_v1",
            "ice_vaneck_us_fallen_angel_angl_v1",
            "execution_lab.alpaca_micro_live_v1.handoff_import.calculators.fallen_angel_angl",
            status="calculator_binding_present_fixture_pending",
            calculate=_load_calculator("execution_lab.alpaca_micro_live_v1.handoff_import.calculators.fallen_angel_angl"),
        )
        self.register(
            "hyg_ema100_spy_bil_calculator_v1",
            "schwoerer_hyg_ema100_spy_bil_v1",
            "execution_lab.alpaca_micro_live_v1.handoff_import.calculators.hyg_ema100_spy_bil",
            status="calculator_binding_present_fixture_pending",
            calculate=_load_calculator("execution_lab.alpaca_micro_live_v1.handoff_import.calculators.hyg_ema100_spy_bil"),
        )
        self.register(
            "decelerated_psar_calculator_v1",
            "barbara_decelerated_psar_spy_bil_v1",
            "execution_lab.alpaca_micro_live_v1.handoff_import.calculators.decelerated_psar_spy_bil",
            status="calculator_binding_present_fixture_pending",
            calculate=_load_calculator("execution_lab.alpaca_micro_live_v1.handoff_import.calculators.decelerated_psar_spy_bil"),
        )
        self.register(
            "factory_d1_trend_quality_calculator_v1",
            "factory_v1_spy_trend_quality_state_d1",
            "execution_lab.alpaca_micro_live_v1.handoff_import.calculators.spy_trend_quality_state_d1",
            status="calculator_binding_present_fixture_pending",
            calculate=_load_calculator("execution_lab.alpaca_micro_live_v1.handoff_import.calculators.spy_trend_quality_state_d1"),
        )

    def register(
        self,
        calculator_type: str,
        strategy_id: str,
        module_path: str,
        *,
        status: str = "calculator_binding_present_fixture_not_run",
        calculate: Callable[..., dict[str, Any]] | None = None,
        note: str = "",
    ) -> None:
        self._bindings[calculator_type.lower()] = CalculatorBinding(calculator_type, strategy_id, module_path, status, calculate, note)

    def resolve(self, calculator_type: str, strategy_id: str = "") -> CalculatorBinding | None:
        key = (calculator_type or "").lower()
        if key in self._bindings:
            return self._bindings[key]
        if strategy_id and strategy_id.lower() in self._bindings:
            return self._bindings[strategy_id.lower()]
        return None

    def classify(self, calculator_type: str, strategy_id: str = "") -> str:
        binding = self.resolve(calculator_type, strategy_id)
        if not calculator_type:
            return "calculator_module_required"
        if binding is None:
            return "calculator_binding_missing"
        return binding.status

    def rows(self) -> list[dict[str, str]]:
        return [
            {
                "calculator_type": binding.calculator_type,
                "strategy_id": binding.strategy_id,
                "module_path": binding.module_path,
                "status": binding.status,
                "note": binding.note,
            }
            for binding in sorted(self._bindings.values(), key=lambda b: b.calculator_type)
        ]


def _load_calculator(module_path: str) -> Callable[..., dict[str, Any]]:
    from importlib import import_module

    module = import_module(module_path)
    return module.calculate_fixture
