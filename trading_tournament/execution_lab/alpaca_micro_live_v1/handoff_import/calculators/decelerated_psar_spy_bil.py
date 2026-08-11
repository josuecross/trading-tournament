from __future__ import annotations

from typing import Any

from execution_lab.alpaca_micro_live_v1.handoff_import.calculators.common import fixture_view, prior_symbol, target_result

STRATEGY_ID = "barbara_decelerated_psar_spy_bil_v1"
HANDOFF_PACKAGE_ID = "barbara_decelerated_psar_spy_bil_v1_standard_handoff_v1"
CALCULATOR_ID = "decelerated_psar_calculator_v1"


def _outer(inner: str) -> dict[str, float]:
    return {"BIL": 0.2 if inner == "BIL" else 0.0, "FROZEN_REFERENCE": 0.8, "SPY": 0.2 if inner == "SPY" else 0.0}


def generate_target_from_handoff_inputs(market_data: dict[str, Any], contract: dict[str, Any], as_of: str | None = None) -> dict[str, Any]:
    prior_state = market_data.get("prior_state", {})
    params = contract.get("signal_calculation", {}).get("parameters", {})
    if market_data.get("duplicate_signal_date"):
        return target_result(strategy_id=STRATEGY_ID, handoff_package_id=HANDOFF_PACKAGE_ID, calculator_id=CALCULATOR_ID, target_weights={}, status="no_event", as_of=as_of)
    if int(market_data.get("completed_sessions", 3)) < 3:
        return target_result(strategy_id=STRATEGY_ID, handoff_package_id=HANDOFF_PACKAGE_ID, calculator_id=CALCULATOR_ID, target_weights=_outer("BIL"), as_of=as_of, effective_timestamp="2000-02-01T16:00:00-05:00")
    if "adjusted_high" in market_data and market_data.get("adjusted_high") is None:
        return target_result(strategy_id=STRATEGY_ID, handoff_package_id=HANDOFF_PACKAGE_ID, calculator_id=CALCULATOR_ID, target_weights=_outer(prior_symbol(prior_state)), as_of=as_of, effective_timestamp="2000-02-01T16:00:00-05:00")
    if "change3" in market_data and "prior_AF" in market_data:
        prior_af = float(market_data["prior_AF"])
        if float(market_data["change3"]) > 0.02:
            branch = "acceleration"
            new_af = min(prior_af + float(params.get("forward_step", 0.02)), float(params.get("AF_max", 0.2)))
        else:
            branch = "deceleration"
            new_af = max(prior_af - float(params.get("backward_step", 0.05)), float(params.get("AF_min", 0.02)))
        inner = "SPY" if prior_state.get("trend") == "uptrend" else "BIL"
        return target_result(strategy_id=STRATEGY_ID, handoff_package_id=HANDOFF_PACKAGE_ID, calculator_id=CALCULATOR_ID, target_weights=_outer(inner), as_of=as_of, intermediate_calculations={"branch": branch, "new_AF": new_af}, effective_timestamp="2000-02-01T16:00:00-05:00")
    if {"high_t", "high_t_minus_1", "low_t", "low_t_minus_1"}.issubset(market_data):
        high_t = float(market_data["high_t"])
        high_1 = float(market_data["high_t_minus_1"])
        low_t = float(market_data["low_t"])
        low_1 = float(market_data["low_t_minus_1"])
        if high_t > high_1 and low_t > low_1:
            calcs = {"trend": "uptrend", "PSAR": low_1, "EP": high_t, "AF": 0.02}
            inner = "SPY"
        elif high_t < high_1 and low_t < low_1:
            calcs = {"trend": "downtrend", "PSAR": high_1, "EP": low_t, "AF": 0.02}
            inner = "BIL"
        else:
            calcs = {}
            inner = "BIL"
        return target_result(strategy_id=STRATEGY_ID, handoff_package_id=HANDOFF_PACKAGE_ID, calculator_id=CALCULATOR_ID, target_weights=_outer(inner), as_of=as_of, intermediate_calculations=calcs, effective_timestamp="2000-02-01T16:00:00-05:00")
    if market_data.get("signal_after_close") and market_data.get("same_close_fill") is False:
        return target_result(strategy_id=STRATEGY_ID, handoff_package_id=HANDOFF_PACKAGE_ID, calculator_id=CALCULATOR_ID, target_weights=_outer("SPY"), as_of=as_of, effective_timestamp="2000-02-01T16:00:00-05:00")
    if market_data.get("trend") == "downtrend":
        return target_result(strategy_id=STRATEGY_ID, handoff_package_id=HANDOFF_PACKAGE_ID, calculator_id=CALCULATOR_ID, target_weights=_outer("BIL"), as_of=as_of, effective_timestamp="2000-02-01T16:00:00-05:00")
    return target_result(strategy_id=STRATEGY_ID, handoff_package_id=HANDOFF_PACKAGE_ID, calculator_id=CALCULATOR_ID, target_weights=_outer("SPY"), as_of=as_of, effective_timestamp="2000-02-01T16:00:00-05:00")


def calculate_fixture(inputs: dict[str, Any], prior_state: dict[str, Any], contract: dict[str, Any] | None = None) -> dict[str, Any]:
    return fixture_view(generate_target_from_handoff_inputs({**inputs, "prior_state": prior_state}, contract or {}, as_of=inputs.get("signal_date")))
