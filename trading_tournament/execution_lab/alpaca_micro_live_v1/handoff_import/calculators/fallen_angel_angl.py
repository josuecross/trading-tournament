from __future__ import annotations

from typing import Any

from execution_lab.alpaca_micro_live_v1.handoff_import.calculators.common import fixture_view, target_result

STRATEGY_ID = "ice_vaneck_us_fallen_angel_angl_v1"
HANDOFF_PACKAGE_ID = "ice_vaneck_us_fallen_angel_angl_v1_standard_handoff_v1"
CALCULATOR_ID = "angl_80_20_monthly_calculator_v1"


def generate_target_from_handoff_inputs(market_data: dict[str, Any], contract: dict[str, Any], as_of: str | None = None) -> dict[str, Any]:
    if market_data.get("already_processed_month") or market_data.get("duplicate_signal_date"):
        return target_result(strategy_id=STRATEGY_ID, handoff_package_id=HANDOFF_PACKAGE_ID, calculator_id=CALCULATOR_ID, target_weights={}, status="no_event", as_of=as_of)
    if "ANGL_execution_price" in market_data and market_data.get("ANGL_execution_price") is None:
        return target_result(strategy_id=STRATEGY_ID, handoff_package_id=HANDOFF_PACKAGE_ID, calculator_id=CALCULATOR_ID, target_weights={}, status="blocked", as_of=as_of, blocked_reason="ANGL_or_reference_price_missing")
    outer_targets = contract.get("portfolio_construction", {}).get("outer_targets", {})
    weights = {"ANGL": float(outer_targets.get("ANGL", 0.2)), "FROZEN_REFERENCE": float(outer_targets.get("FROZEN_REFERENCE", 0.8))}
    effective_timestamp = "2000-02-01T16:00:00-05:00" if market_data else None
    return target_result(strategy_id=STRATEGY_ID, handoff_package_id=HANDOFF_PACKAGE_ID, calculator_id=CALCULATOR_ID, target_weights=weights, as_of=as_of, effective_timestamp=effective_timestamp)


def calculate_fixture(inputs: dict[str, Any], prior_state: dict[str, Any], contract: dict[str, Any] | None = None) -> dict[str, Any]:
    return fixture_view(generate_target_from_handoff_inputs({**inputs, "prior_state": prior_state}, contract or {}, as_of=inputs.get("signal_date")))
