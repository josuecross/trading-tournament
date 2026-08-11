from __future__ import annotations

from datetime import date
from typing import Any


def target_result(
    *,
    strategy_id: str,
    handoff_package_id: str,
    calculator_id: str,
    target_weights: dict[str, float],
    status: str = "target_calculated",
    as_of: str | None = None,
    intermediate_calculations: dict[str, Any] | None = None,
    blocked_reason: str | None = None,
    effective_timestamp: str | None = None,
    signals: dict[str, Any] | None = None,
) -> dict[str, Any]:
    selected_holdings = [symbol for symbol, weight in target_weights.items() if float(weight) > 0]
    return {
        "strategy_id": strategy_id,
        "as_of": as_of or date.today().isoformat(),
        "target_source": "standard_v1_handoff_calculator",
        "target_weights": {symbol: float(weight) for symbol, weight in target_weights.items()},
        "cash_weight": 0.0,
        "metadata": {
            "handoff_package_id": handoff_package_id,
            "calculator_id": calculator_id,
            "strategy_logic_modified": False,
            "selected_holdings": selected_holdings,
            "signals": signals or {},
            "blocked_reason": blocked_reason,
            "status": status,
            "effective_timestamp": effective_timestamp,
            "intermediate_calculations": intermediate_calculations or {},
        },
    }


def fixture_view(result: dict[str, Any]) -> dict[str, Any]:
    metadata = result.get("metadata", {})
    return {
        "effective_timestamp": metadata.get("effective_timestamp"),
        "intermediate_calculations": metadata.get("intermediate_calculations", {}),
        "status": metadata.get("status", "target_calculated"),
        "target_weights": result.get("target_weights", {}),
    }


def positive_target(symbol: str, *, frozen_reference: bool = False) -> dict[str, float]:
    if frozen_reference:
        weights = {"BIL": 0.0, "FROZEN_REFERENCE": 0.8, "SPY": 0.0}
        weights[symbol] = 0.2
        return weights
    return {"BIL": 0.0 if symbol != "BIL" else 1.0, "SPY": 0.0 if symbol != "SPY" else 1.0}


def prior_symbol(prior_state: dict[str, Any], default: str = "BIL") -> str:
    return str(prior_state.get("target") or prior_state.get("current_target") or prior_state.get("persisted_inner_target") or default)
