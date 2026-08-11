from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from .errors import StandardContractError


@dataclass(frozen=True)
class MarketSession:
    session_date: str
    open_timestamp: str
    close_timestamp: str

    def __post_init__(self) -> None:
        session_day = date.fromisoformat(self.session_date)
        opened = datetime.fromisoformat(self.open_timestamp.replace("Z", "+00:00"))
        closed = datetime.fromisoformat(self.close_timestamp.replace("Z", "+00:00"))
        if opened.date() != session_day or closed.date() != session_day or opened >= closed:
            raise StandardContractError("timing_contract_not_supported", "Invalid market session timestamps")


class StaticExchangeCalendar:
    """Offline authoritative session table supplied by the receiver."""

    def __init__(self, calendar_id: str, sessions: list[MarketSession]) -> None:
        if not calendar_id:
            raise StandardContractError("calendar_binding_missing", "calendar_id is required")
        ordered = sorted(sessions, key=lambda row: row.session_date)
        if not ordered or len({row.session_date for row in ordered}) != len(ordered):
            raise StandardContractError("calendar_binding_missing", "Calendar needs unique sessions")
        self.calendar_id = calendar_id
        self.sessions = ordered

    def session_on(self, value: str) -> MarketSession | None:
        day = value[:10]
        return next((row for row in self.sessions if row.session_date == day), None)

    def first_session_on_or_after(self, value: str) -> MarketSession:
        day = value[:10]
        row = next((item for item in self.sessions if item.session_date >= day), None)
        if row is None:
            raise StandardContractError("calendar_binding_missing", "No calendar session on or after timestamp")
        return row

    def next_session_after(self, value: str) -> MarketSession:
        day = value[:10]
        row = next((item for item in self.sessions if item.session_date > day), None)
        if row is None:
            raise StandardContractError("calendar_binding_missing", "No next calendar session")
        return row

    def offset_session(self, value: str, offset: int) -> MarketSession:
        base = self.first_session_on_or_after(value)
        index = self.sessions.index(base) + offset
        if index < 0 or index >= len(self.sessions):
            raise StandardContractError("calendar_binding_missing", "Session offset is outside calendar coverage")
        return self.sessions[index]
