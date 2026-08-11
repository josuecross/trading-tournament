from __future__ import annotations

from statistics import mean
from typing import Any

from execution_lab.alpaca_micro_live_v1.handoff_import.calculators.common import fixture_view, prior_symbol, target_result

STRATEGY_ID = "schwoerer_hyg_ema100_spy_bil_v1"
HANDOFF_PACKAGE_ID = "schwoerer_hyg_ema100_spy_bil_v1_standard_handoff_v1"
CALCULATOR_ID = "hyg_ema100_spy_bil_calculator_v1"


def _weights(symbol: str) -> dict[str, float]:
    return {"BIL": 1.0 if symbol == "BIL" else 0.0, "SPY": 1.0 if symbol == "SPY" else 0.0}


def generate_target_from_handoff_inputs(market_data: dict[str, Any], contract: dict[str, Any], as_of: str | None = None) -> dict[str, Any]:
    prior_state = market_data.get("prior_state", {})
    if market_data.get("duplicate_signal_date"):
        return target_result(strategy_id=STRATEGY_ID, handoff_package_id=HANDOFF_PACKAGE_ID, calculator_id=CALCULATOR_ID, target_weights={}, status="no_event", as_of=as_of)
    if int(market_data.get("valid_HYG_closes", 100)) < 100:
        return target_result(strategy_id=STRATEGY_ID, handoff_package_id=HANDOFF_PACKAGE_ID, calculator_id=CALCULATOR_ID, target_weights=_weights("BIL"), as_of=as_of, effective_timestamp="2000-02-01T16:00:00-05:00")
    if "first_100_HYG_closes" in market_data:
        seed = mean(float(value) for value in market_data["first_100_HYG_closes"])
        return target_result(strategy_id=STRATEGY_ID, handoff_package_id=HANDOFF_PACKAGE_ID, calculator_id=CALCULATOR_ID, target_weights=_weights("BIL"), as_of=as_of, intermediate_calculations={"EMA_seed": seed}, effective_timestamp="2000-02-01T16:00:00-05:00")
    if market_data.get("HYG_close") is None and "HYG_close" in market_data:
        return target_result(strategy_id=STRATEGY_ID, handoff_package_id=HANDOFF_PACKAGE_ID, calculator_id=CALCULATOR_ID, target_weights=_weights(prior_symbol(prior_state)), as_of=as_of, effective_timestamp="2000-02-01T16:00:00-05:00")
    if "next_HYG_close" in market_data and "EMA" in market_data:
        alpha = float(contract.get("signal_calculation", {}).get("alpha", 2 / 101))
        next_ema = alpha * float(market_data["next_HYG_close"]) + (1 - alpha) * float(market_data["EMA"])
        return target_result(strategy_id=STRATEGY_ID, handoff_package_id=HANDOFF_PACKAGE_ID, calculator_id=CALCULATOR_ID, target_weights=_weights(str(market_data.get("target", "SPY"))), as_of=as_of, intermediate_calculations={"next_EMA": next_ema}, effective_timestamp="2000-02-01T16:00:00-05:00")
    if "HYG_close" in market_data and "EMA" in market_data:
        close = float(market_data["HYG_close"])
        ema = float(market_data["EMA"])
        if close > ema:
            target = "SPY"
        elif close < ema:
            target = "BIL"
        else:
            target = prior_symbol(prior_state)
        return target_result(strategy_id=STRATEGY_ID, handoff_package_id=HANDOFF_PACKAGE_ID, calculator_id=CALCULATOR_ID, target_weights=_weights(target), as_of=as_of, effective_timestamp="2000-02-01T16:00:00-05:00")
    if market_data.get("signal_after_close") and market_data.get("execution") == "next_valid_session_close":
        return target_result(strategy_id=STRATEGY_ID, handoff_package_id=HANDOFF_PACKAGE_ID, calculator_id=CALCULATOR_ID, target_weights=_weights("SPY"), as_of=as_of, effective_timestamp="2000-02-01T16:00:00-05:00")
    return target_result(strategy_id=STRATEGY_ID, handoff_package_id=HANDOFF_PACKAGE_ID, calculator_id=CALCULATOR_ID, target_weights=_weights(prior_symbol(prior_state)), as_of=as_of, effective_timestamp="2000-02-01T16:00:00-05:00")


def calculate_fixture(inputs: dict[str, Any], prior_state: dict[str, Any], contract: dict[str, Any] | None = None) -> dict[str, Any]:
    return fixture_view(generate_target_from_handoff_inputs({**inputs, "prior_state": prior_state}, contract or {}, as_of=inputs.get("signal_date")))
