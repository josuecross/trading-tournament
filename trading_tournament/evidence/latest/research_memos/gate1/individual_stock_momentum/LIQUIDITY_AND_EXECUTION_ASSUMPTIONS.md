# Liquidity And Execution Assumptions

These preliminary assumptions must be fixed before testing.

## Preliminary Execution Assumptions

- Spread model: conservative spread estimate by price/liquidity bucket, not a flat ETF spread.
- Slippage model: base slippage plus spread component; stress slippage must be materially worse.
- Market open fills: next-open fills allowed only with gap-aware execution.
- Gap-through-stop logic: if the open gaps below the stop, fill at the open, not the stop.
- Same-bar stop/target rule: stop wins when both are touched on the same daily bar.
- Notional cap: max 20% to 25% of equity per single name, finalized before testing.
- Maximum position count: preliminary 5 to 10 positions.
- Maximum single-name exposure: capped at or below notional cap.
- Maximum sector exposure: preliminary 30% if sector data is available.
- Fractional shares: allowed for paper/demo accounting, flagged as simplification.
- No shorting.
- No margin.
- No low-float, penny-stock, or illiquid-stock focus.

## Requirement

These assumptions must be fixed before any Gate 2 test. They cannot be adjusted after seeing results.

