from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Any


TERMINAL_STATUSES = {"completed", "failed", "stopped", "emergency_stopped"}


@dataclass(frozen=True)
class LivenessResult:
    persisted_status: str
    authoritative_current_liveness: str
    evaluated_at: str
    last_heartbeat: str | None
    planned_end: str | None
    ttl_seconds: int
    grace_seconds: int
    reasons: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _parse(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def reconcile_session_liveness(
    state: dict[str, Any],
    *,
    evaluated_at: str,
    heartbeat_ttl_seconds: int,
    planned_end_grace_seconds: int,
) -> LivenessResult:
    now = _parse(evaluated_at)
    status = str(state.get("status") or "unknown")
    heartbeat = _parse(state.get("last_heartbeat_utc"))
    planned_end = _parse(state.get("planned_end_at_utc"))
    reasons: list[str] = []
    if now is None:
        raise ValueError("evaluated_at must be ISO-8601")
    if status in TERMINAL_STATUSES:
        classification = "terminal"
        reasons.append(f"terminal_status:{status}")
    elif status not in {"running", "degraded_running"}:
        classification = "unknown"
        reasons.append("persisted_status_not_liveness_eligible")
    else:
        expired_heartbeat = heartbeat is None or now > heartbeat + timedelta(seconds=heartbeat_ttl_seconds)
        expired_end = planned_end is not None and now > planned_end + timedelta(seconds=planned_end_grace_seconds)
        if expired_heartbeat or expired_end:
            classification = "stale"
            if expired_heartbeat:
                reasons.append("heartbeat_ttl_expired")
            if expired_end:
                reasons.append("planned_end_grace_expired")
        else:
            classification = "active"
            reasons.append("running_with_fresh_heartbeat_and_unexpired_plan")
    return LivenessResult(
        persisted_status=status,
        authoritative_current_liveness=classification,
        evaluated_at=evaluated_at,
        last_heartbeat=state.get("last_heartbeat_utc"),
        planned_end=state.get("planned_end_at_utc"),
        ttl_seconds=heartbeat_ttl_seconds,
        grace_seconds=planned_end_grace_seconds,
        reasons=reasons,
    )
