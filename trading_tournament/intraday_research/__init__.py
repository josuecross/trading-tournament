"""Research-only intraday infrastructure contracts.

This package contains offline validation and simulation primitives only. It
does not fetch provider data, call brokers, submit orders, or run strategies.
"""

from intraday_research.candidate_readiness import (
    CANDIDATE_IDS,
    InfrastructureStatus,
    evaluate_candidate_readiness,
)
from intraday_research.cache_contract import IntradayCacheContract
from intraday_research.data_schema import ALLOWED_TIMEFRAMES, validate_intraday_bars
from intraday_research.event_logging import IntradayResearchEvent, validate_research_event
from intraday_research.fill_model import FillRequest, simulate_market_fill
from intraday_research.kill_switch import KillSwitchRecorder
from intraday_research.risk_engine import IntradayRiskLimits, IntradayRiskState, evaluate_risk_state
from intraday_research.session_timing import MarketSession, build_signal_timing, regular_session

__all__ = [
    "ALLOWED_TIMEFRAMES",
    "CANDIDATE_IDS",
    "FillRequest",
    "InfrastructureStatus",
    "IntradayCacheContract",
    "IntradayResearchEvent",
    "IntradayRiskLimits",
    "IntradayRiskState",
    "KillSwitchRecorder",
    "MarketSession",
    "build_signal_timing",
    "evaluate_candidate_readiness",
    "evaluate_risk_state",
    "regular_session",
    "simulate_market_fill",
    "validate_intraday_bars",
    "validate_research_event",
]
