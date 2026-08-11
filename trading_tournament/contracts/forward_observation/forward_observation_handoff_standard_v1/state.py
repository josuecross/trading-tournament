from __future__ import annotations

import json
import os
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from .errors import StandardContractError
from .models import CalculationResult, StrategyState


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class JsonStrategyStateStore:
    """Receiver-owned, session-independent strategy state."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def path_for(self, strategy_instance_id: str) -> Path:
        if not strategy_instance_id or any(token in strategy_instance_id for token in ("/", "\\", "..")):
            raise StandardContractError("state_contract_failure", "Unsafe strategy_instance_id")
        return self.root / f"{strategy_instance_id}.json"

    def load(self, strategy_instance_id: str) -> StrategyState | None:
        path = self.path_for(strategy_instance_id)
        if not path.exists():
            return None
        return StrategyState.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def save(self, state: StrategyState) -> Path:
        path = self.path_for(state.strategy_instance_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(state.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(temporary, path)
        return path


def apply_calculation_result(
    state: StrategyState,
    result: CalculationResult,
    *,
    now: str,
) -> StrategyState:
    if result.strategy_instance_id != state.strategy_instance_id:
        raise StandardContractError("state_contract_failure", "Result belongs to another strategy instance")
    if result.status == "no_event":
        return replace(state, state_updated_at=now)
    if result.status != "target_calculated" or not result.event_id:
        raise StandardContractError("state_contract_failure", "Only calculated targets or no_event can update state")
    if result.event_id in state.handled_event_ids:
        raise StandardContractError(
            "duplicate_event",
            f"Event {result.event_id} was already processed across a prior session",
            details={"event_id": result.event_id},
        )
    handled = [*state.handled_event_ids, result.event_id]
    common = {
        "last_processed_event_id": result.event_id,
        "last_processed_event_timestamp": result.calculation_reference_time,
        "handled_event_ids": handled,
        "last_successful_calculation_at": result.calculated_at,
        "state_updated_at": now,
    }
    if _dt(result.effective_timestamp or now) > _dt(now):
        return replace(
            state,
            pending_target_version=result.target_version_id,
            pending_target=result.target_weights,
            pending_cash_weight=result.cash_weight,
            pending_effective_timestamp=result.effective_timestamp,
            **common,
        )
    return replace(
        state,
        current_effective_target_version=result.target_version_id,
        current_effective_target=result.target_weights,
        current_effective_cash_weight=result.cash_weight,
        current_effective_timestamp=result.effective_timestamp,
        pending_target_version=None,
        pending_target={},
        pending_cash_weight=0.0,
        pending_effective_timestamp=None,
        **common,
    )


def promote_pending_target(state: StrategyState, *, now: str) -> StrategyState:
    if not state.pending_target_version or not state.pending_effective_timestamp:
        return state
    if _dt(state.pending_effective_timestamp) > _dt(now):
        return state
    return replace(
        state,
        current_effective_target_version=state.pending_target_version,
        current_effective_target=state.pending_target,
        current_effective_cash_weight=state.pending_cash_weight,
        current_effective_timestamp=state.pending_effective_timestamp,
        pending_target_version=None,
        pending_target={},
        pending_cash_weight=0.0,
        pending_effective_timestamp=None,
        state_updated_at=now,
    )
