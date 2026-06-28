from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal


@dataclass(frozen=True)
class IntradayRiskLimits:
    max_trades_per_day: int = 3
    max_daily_loss: Decimal = Decimal("90")
    max_weekly_loss: Decimal = Decimal("180")
    max_open_positions: int = 1
    max_notional_exposure: Decimal = Decimal("1200")
    force_flat_time_utc: time = time(20, 55)
    no_overnight: bool = True
    stale_bar_minutes: int = 10
    abnormal_loss: Decimal = Decimal("120")
    excessive_order_count: int = 6


@dataclass(frozen=True)
class IntradayRiskState:
    timestamp_utc: datetime
    trades_today: int = 0
    orders_today: int = 0
    daily_realized_pnl: Decimal = Decimal("0")
    weekly_realized_pnl: Decimal = Decimal("0")
    open_positions: dict[str, Decimal] = field(default_factory=dict)
    notional_exposure: Decimal = Decimal("0")
    latest_bar_timestamp_utc: datetime | None = None
    logging_ok: bool = True


@dataclass(frozen=True)
class RiskDecision:
    allowed: bool
    force_flat_required: bool
    halt_required: bool
    reasons: tuple[str, ...]


def _to_utc(timestamp: datetime) -> datetime:
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return timestamp.astimezone(timezone.utc)


def evaluate_risk_state(state: IntradayRiskState, limits: IntradayRiskLimits) -> RiskDecision:
    now = _to_utc(state.timestamp_utc)
    reasons: list[str] = []
    if state.trades_today >= limits.max_trades_per_day:
        reasons.append("max_trades_per_day")
    if state.orders_today >= limits.excessive_order_count:
        reasons.append("excessive_order_count")
    if -state.daily_realized_pnl >= limits.max_daily_loss:
        reasons.append("max_daily_loss")
    if -state.weekly_realized_pnl >= limits.max_weekly_loss:
        reasons.append("max_weekly_loss")
    if -state.daily_realized_pnl >= limits.abnormal_loss:
        reasons.append("abnormal_loss")
    if len(state.open_positions) > limits.max_open_positions:
        reasons.append("max_open_positions")
    if state.notional_exposure > limits.max_notional_exposure:
        reasons.append("max_notional_exposure")
    if state.latest_bar_timestamp_utc is None:
        reasons.append("missing_latest_bar")
    else:
        latest = _to_utc(state.latest_bar_timestamp_utc)
        if now - latest > timedelta(minutes=limits.stale_bar_minutes):
            reasons.append("stale_or_missing_data")
    if not state.logging_ok:
        reasons.append("logging_failure")
    force_flat = limits.no_overnight and now.time() >= limits.force_flat_time_utc and bool(state.open_positions)
    if force_flat:
        reasons.append("force_flat_no_overnight")
    halt_reasons = {
        "max_daily_loss",
        "max_weekly_loss",
        "abnormal_loss",
        "stale_or_missing_data",
        "missing_latest_bar",
        "excessive_order_count",
        "logging_failure",
    }
    halt_required = any(reason in halt_reasons for reason in reasons)
    return RiskDecision(
        allowed=not reasons,
        force_flat_required=force_flat,
        halt_required=halt_required,
        reasons=tuple(reasons),
    )
