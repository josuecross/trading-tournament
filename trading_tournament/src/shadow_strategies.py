from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ShadowStrategyStatus:
    name: str
    included_in_main_results: bool
    reason: str
    required_data: str


OPENING_RANGE_BREAKOUT = ShadowStrategyStatus(
    name="F_opening_range_breakout",
    included_in_main_results=False,
    reason="Opening range breakout requires intraday bars and live-session assumptions.",
    required_data="Clean intraday OHLCV CSV files under data/intraday/.",
)


EVENT_DRIVEN_MOMENTUM = ShadowStrategyStatus(
    name="G_event_driven_momentum",
    included_in_main_results=False,
    reason="Event/news momentum requires reliable timestamped event data.",
    required_data="Auditable earnings/news/event feed with release timestamps.",
)


SHADOW_STRATEGIES = [OPENING_RANGE_BREAKOUT, EVENT_DRIVEN_MOMENTUM]
