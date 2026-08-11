from __future__ import annotations

from typing import Any

from execution_lab.alpaca_micro_live_v1.handoff_import.calculators.common import fixture_view, target_result

STRATEGY_ID = "factory_v1_spy_trend_quality_state_d1"
HANDOFF_PACKAGE_ID = "factory_v1_spy_trend_quality_state_d1_standard_handoff_v1"
CALCULATOR_ID = "factory_d1_trend_quality_calculator_v1"


def _outer(inner: str) -> dict[str, float]:
    return {"BIL": 0.2 if inner == "BIL" else 0.0, "FROZEN_REFERENCE": 0.8, "SPY": 0.2 if inner == "SPY" else 0.0}


def generate_target_from_handoff_inputs(market_data: dict[str, Any], contract: dict[str, Any], as_of: str | None = None) -> dict[str, Any]:
    if market_data.get("duplicate_signal_date"):
        return target_result(strategy_id=STRATEGY_ID, handoff_package_id=HANDOFF_PACKAGE_ID, calculator_id=CALCULATOR_ID, target_weights={}, status="no_event", as_of=as_of)
    if int(market_data.get("valid_SPY_closes", 60)) < 60:
        inner = "BIL"
    elif market_data.get("SST") == 0.0:
        inner = "BIL"
    elif "annualized_slope" in market_data and "r_squared" in market_data:
        inner = "SPY" if float(market_data["annualized_slope"]) > 0 and float(market_data["r_squared"]) >= 0.25 else "BIL"
    elif market_data.get("signal_after_close") and market_data.get("execution") == "next_valid_session_close":
        inner = "SPY"
    elif market_data.get("r_squared") is None and "r_squared" in market_data:
        inner = "BIL"
    else:
        inner = str(market_data.get("persisted_inner_target", "BIL"))
    return target_result(strategy_id=STRATEGY_ID, handoff_package_id=HANDOFF_PACKAGE_ID, calculator_id=CALCULATOR_ID, target_weights=_outer(inner), as_of=as_of, effective_timestamp="2000-02-01T16:00:00-05:00")


def calculate_fixture(inputs: dict[str, Any], prior_state: dict[str, Any], contract: dict[str, Any] | None = None) -> dict[str, Any]:
    return fixture_view(generate_target_from_handoff_inputs({**inputs, "prior_state": prior_state}, contract or {}, as_of=inputs.get("signal_date")))
