from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover - Windows fallback guard
    ZoneInfo = None  # type: ignore[assignment]


def _eastern_tz():
    if ZoneInfo is not None:
        try:
            return ZoneInfo("America/New_York")
        except Exception:
            pass
    return timezone(timedelta(hours=-5), name="America/New_York")


EASTERN = _eastern_tz()
REGULAR_OPEN = time(9, 30)
REGULAR_CLOSE = time(16, 0)


@dataclass(frozen=True)
class MarketSession:
    session_date: date
    open_utc: datetime
    close_utc: datetime
    early_close: bool = False
    holiday: bool = False

    def contains(self, timestamp: datetime) -> bool:
        ts = _to_utc(timestamp)
        return self.open_utc <= ts <= self.close_utc


@dataclass(frozen=True)
class SignalTimingPlan:
    signal_bar_end_utc: datetime
    entry_not_before_utc: datetime
    exit_deadline_utc: datetime
    completed_bar_only: bool
    no_lookahead_enforced: bool


def _to_utc(timestamp: datetime) -> datetime:
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return timestamp.astimezone(timezone.utc)


def regular_session(
    session_date: date,
    early_close_time: time | None = None,
    holiday: bool = False,
) -> MarketSession | None:
    if holiday or session_date.weekday() >= 5:
        return None
    close_time = early_close_time or REGULAR_CLOSE
    open_local = datetime.combine(session_date, REGULAR_OPEN, tzinfo=EASTERN)
    close_local = datetime.combine(session_date, close_time, tzinfo=EASTERN)
    if close_local <= open_local:
        raise ValueError("session close must be after session open")
    return MarketSession(
        session_date=session_date,
        open_utc=open_local.astimezone(timezone.utc),
        close_utc=close_local.astimezone(timezone.utc),
        early_close=early_close_time is not None,
        holiday=False,
    )


def build_signal_timing(signal_bar_end: datetime, timeframe_minutes: int, session: MarketSession) -> SignalTimingPlan:
    signal_end = _to_utc(signal_bar_end)
    if timeframe_minutes <= 0:
        raise ValueError("timeframe_minutes must be positive")
    if not session.contains(signal_end):
        raise ValueError("signal bar must end inside the market session")
    entry_not_before = signal_end + timedelta(minutes=timeframe_minutes)
    if entry_not_before > session.close_utc:
        raise ValueError("entry would occur after the session close")
    if entry_not_before <= signal_end:
        raise ValueError("entry must be after the signal bar")
    return SignalTimingPlan(
        signal_bar_end_utc=signal_end,
        entry_not_before_utc=entry_not_before,
        exit_deadline_utc=session.close_utc,
        completed_bar_only=True,
        no_lookahead_enforced=True,
    )
