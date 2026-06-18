from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RuntimeSignal:
    strategy_id: str
    as_of: str
    target_weights: dict[str, float]
    cash_weight: float
    metadata: dict[str, Any] = field(default_factory=dict)
    eligibility_table: list[dict[str, Any]] = field(default_factory=list)
    ranking_table: list[dict[str, Any]] = field(default_factory=list)
    selected_holdings: list[str] = field(default_factory=list)
    fallback_triggered: bool = False
    missing_data: list[str] = field(default_factory=list)
    approximations: list[str] = field(default_factory=list)


@dataclass
class ProposedOrder:
    symbol: str
    side: str
    notional: float
    reason: str
    qty: float | None = None
    client_order_id: str | None = None


@dataclass
class RiskGateResult:
    allowed: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
