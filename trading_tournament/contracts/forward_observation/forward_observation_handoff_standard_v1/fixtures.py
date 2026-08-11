from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Callable

from .errors import StandardContractError
from .models import CalculationRequest, CalculationResult


FIXTURE_TYPES = {
    "signal_formula_fixture",
    "target_weight_fixture",
    "threshold_or_tie_fixture",
    "timing_fixture",
    "missing_event_fixture",
    "restart_fixture",
    "duplicate_event_fixture",
    "stale_event_fixture",
}


@dataclass(frozen=True)
class FixtureDefinition:
    fixture_id: str
    fixture_type: str
    calculator_type: str
    request: CalculationRequest
    expected_target_weights: dict[str, float] | None = None
    expected_effective_timestamp: str | None = None
    expected_status: str = "target_calculated"

    def __post_init__(self) -> None:
        if self.fixture_type not in FIXTURE_TYPES:
            raise StandardContractError("fixture_failure", f"Unsupported fixture type: {self.fixture_type}")


class CalculatorRegistry:
    def __init__(self) -> None:
        self._calculators: dict[str, Callable[[CalculationRequest], CalculationResult]] = {}

    def register(self, calculator_type: str, calculator: Callable[[CalculationRequest], CalculationResult]) -> None:
        self._calculators[calculator_type] = calculator

    def calculate(self, calculator_type: str, request: CalculationRequest) -> CalculationResult:
        calculator = self._calculators.get(calculator_type)
        if calculator is None:
            raise StandardContractError("calculator_not_supported", f"Calculator is not registered: {calculator_type}")
        return calculator(request)


def run_fixture(fixture: FixtureDefinition, registry: CalculatorRegistry) -> dict[str, Any]:
    try:
        result = registry.calculate(fixture.calculator_type, fixture.request)
        errors: list[str] = []
        if result.status != fixture.expected_status:
            errors.append(f"status:{result.status}!={fixture.expected_status}")
        if fixture.expected_target_weights is not None and result.target_weights != fixture.expected_target_weights:
            errors.append("target_weights_mismatch")
        if fixture.expected_effective_timestamp is not None and result.effective_timestamp != fixture.expected_effective_timestamp:
            errors.append("effective_timestamp_mismatch")
        return {"fixture_id": fixture.fixture_id, "fixture_type": fixture.fixture_type, "passed": not errors, "errors": errors, "result": result.to_dict()}
    except StandardContractError as exc:
        return {"fixture_id": fixture.fixture_id, "fixture_type": fixture.fixture_type, "passed": False, "errors": [exc.code], "result": None}


def fixture_to_dict(fixture: FixtureDefinition) -> dict[str, Any]:
    return asdict(fixture)
