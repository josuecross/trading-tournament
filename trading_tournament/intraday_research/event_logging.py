from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


EVENT_TYPES = {
    "signal_generated",
    "order_intent_created",
    "simulated_order_submitted",
    "simulated_fill",
    "simulated_no_fill",
    "simulated_partial_fill",
    "position_updated",
    "risk_gate_block",
    "kill_switch_triggered",
    "forced_flat",
    "session_closed",
}


@dataclass(frozen=True)
class IntradayResearchEvent:
    event_type: str
    timestamp_utc: datetime
    strategy_id: str
    symbol: str
    payload: dict[str, Any] = field(default_factory=dict)

    def to_json_line(self) -> str:
        event = validate_research_event(self)
        return json.dumps(
            {
                "event_type": event.event_type,
                "timestamp_utc": event.timestamp_utc.isoformat(),
                "strategy_id": event.strategy_id,
                "symbol": event.symbol,
                "payload": event.payload,
            },
            sort_keys=True,
        )


def validate_research_event(event: IntradayResearchEvent) -> IntradayResearchEvent:
    if event.event_type not in EVENT_TYPES:
        raise ValueError(f"unsupported intraday research event: {event.event_type}")
    if event.timestamp_utc.tzinfo is None or event.timestamp_utc.utcoffset() is None:
        raise ValueError("event timestamp must be timezone-aware")
    if not event.strategy_id:
        raise ValueError("strategy_id is required")
    if not event.symbol:
        raise ValueError("symbol is required")
    return IntradayResearchEvent(
        event_type=event.event_type,
        timestamp_utc=event.timestamp_utc.astimezone(timezone.utc),
        strategy_id=event.strategy_id,
        symbol=event.symbol.upper(),
        payload=dict(event.payload),
    )
