from __future__ import annotations

from datetime import datetime

from .calendar import StaticExchangeCalendar
from .errors import StandardContractError
from .models import CalculationEvent, TimingContract


def resolve_effective_timestamp(
    contract: TimingContract,
    *,
    event: CalculationEvent,
    calendar: StaticExchangeCalendar | None,
) -> str:
    rule = contract.effective_rule
    kind = rule["kind"]
    boundary = rule.get("boundary", "after_close")
    if kind == "explicit_timestamp":
        value = rule.get("timestamp")
        if not value:
            raise StandardContractError("timing_contract_not_supported", "Explicit timing needs a timestamp")
        datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return str(value)
    if calendar is None or calendar.calendar_id != contract.calendar_id:
        raise StandardContractError("calendar_binding_missing", "Matching exchange calendar is required")
    if kind == "same_session":
        session = calendar.session_on(event.available_timestamp)
        if session is None:
            raise StandardContractError("calendar_binding_missing", "Event date is not a market session")
    elif kind == "next_valid_session":
        session = calendar.next_session_after(event.available_timestamp)
    elif kind == "session_offset":
        session = calendar.offset_session(event.available_timestamp, int(rule.get("offset", 0)))
    else:  # guarded by TimingContract validation
        raise StandardContractError("timing_contract_not_supported", f"Unsupported rule: {kind}")
    if boundary == "open":
        return session.open_timestamp
    if boundary in {"close", "after_close"}:
        return session.close_timestamp
    raise StandardContractError("timing_contract_not_supported", f"Unsupported session boundary: {boundary}")
