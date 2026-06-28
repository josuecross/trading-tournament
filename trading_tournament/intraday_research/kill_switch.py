from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


KILL_SWITCH_REASONS = {
    "data_error",
    "timestamp_session_error",
    "fill_model_error",
    "risk_breach",
    "excessive_order_count",
    "reconciliation_mismatch",
    "logging_failure",
}


@dataclass(frozen=True)
class KillSwitchEvent:
    reason: str
    message: str
    timestamp_utc: datetime
    severity: str = "halt"


@dataclass
class KillSwitchRecorder:
    events: list[KillSwitchEvent] = field(default_factory=list)

    def trigger(self, reason: str, message: str, timestamp: datetime | None = None, severity: str = "halt") -> KillSwitchEvent:
        if reason not in KILL_SWITCH_REASONS:
            raise ValueError(f"unsupported kill-switch reason: {reason}")
        ts = timestamp or datetime.now(timezone.utc)
        if ts.tzinfo is None or ts.utcoffset() is None:
            raise ValueError("kill-switch timestamp must be timezone-aware")
        event = KillSwitchEvent(
            reason=reason,
            message=message,
            timestamp_utc=ts.astimezone(timezone.utc),
            severity=severity,
        )
        self.events.append(event)
        return event

    @property
    def active(self) -> bool:
        return any(event.severity == "halt" for event in self.events)


def triggers_from_inputs(
    *,
    data_error: bool = False,
    timestamp_session_error: bool = False,
    fill_model_error: bool = False,
    risk_breach: bool = False,
    excessive_order_count: bool = False,
    reconciliation_mismatch: bool = False,
    logging_failure: bool = False,
) -> tuple[str, ...]:
    flags = {
        "data_error": data_error,
        "timestamp_session_error": timestamp_session_error,
        "fill_model_error": fill_model_error,
        "risk_breach": risk_breach,
        "excessive_order_count": excessive_order_count,
        "reconciliation_mismatch": reconciliation_mismatch,
        "logging_failure": logging_failure,
    }
    return tuple(reason for reason, enabled in flags.items() if enabled)
