from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class FillRequest:
    side: str
    quantity: Decimal
    reference_price: Decimal
    bar_low: Decimal
    bar_high: Decimal
    spread_cents: Decimal = Decimal("0")
    slippage_bps: Decimal = Decimal("0")
    slippage_cents: Decimal = Decimal("0")
    stress_mode: bool = False
    force_no_fill_reason: str | None = None
    max_fill_quantity: Decimal | None = None
    allow_partial: bool = True


@dataclass(frozen=True)
class FillResult:
    status: str
    filled_quantity: Decimal
    fill_price: Decimal | None
    reason: str
    conservative_bar_extreme_check: bool
    partial_fill_placeholder: bool
    no_fill_placeholder: bool


def _as_decimal(value: Decimal | int | float | str) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


def simulate_market_fill(request: FillRequest) -> FillResult:
    side = request.side.lower()
    if side not in {"buy", "sell"}:
        raise ValueError("side must be buy or sell")
    if request.quantity <= 0:
        raise ValueError("quantity must be positive")
    if request.bar_low <= 0 or request.bar_high <= 0 or request.bar_high < request.bar_low:
        raise ValueError("bar extremes are invalid")
    if request.force_no_fill_reason:
        return FillResult(
            status="no_fill",
            filled_quantity=Decimal("0"),
            fill_price=None,
            reason=request.force_no_fill_reason,
            conservative_bar_extreme_check=True,
            partial_fill_placeholder=False,
            no_fill_placeholder=True,
        )
    multiplier = Decimal("2") if request.stress_mode else Decimal("1")
    half_spread = _as_decimal(request.spread_cents) / Decimal("200")
    slippage_from_bps = request.reference_price * (_as_decimal(request.slippage_bps) / Decimal("10000"))
    slippage_from_cents = _as_decimal(request.slippage_cents) / Decimal("100")
    total_cost = multiplier * (half_spread + slippage_from_bps + slippage_from_cents)
    fill_price = request.reference_price + total_cost if side == "buy" else request.reference_price - total_cost
    if fill_price > request.bar_high or fill_price < request.bar_low:
        return FillResult(
            status="no_fill",
            filled_quantity=Decimal("0"),
            fill_price=None,
            reason="modeled_fill_outside_bar_extremes",
            conservative_bar_extreme_check=True,
            partial_fill_placeholder=False,
            no_fill_placeholder=True,
        )
    filled = request.quantity
    partial = False
    if request.max_fill_quantity is not None and request.max_fill_quantity < request.quantity:
        if not request.allow_partial or request.max_fill_quantity <= 0:
            return FillResult(
                status="no_fill",
                filled_quantity=Decimal("0"),
                fill_price=None,
                reason="max_fill_quantity_prevents_fill",
                conservative_bar_extreme_check=True,
                partial_fill_placeholder=False,
                no_fill_placeholder=True,
            )
        filled = request.max_fill_quantity
        partial = True
    return FillResult(
        status="partial_fill" if partial else "filled",
        filled_quantity=filled,
        fill_price=fill_price,
        reason="conservative_market_approximation",
        conservative_bar_extreme_check=True,
        partial_fill_placeholder=partial,
        no_fill_placeholder=False,
    )
