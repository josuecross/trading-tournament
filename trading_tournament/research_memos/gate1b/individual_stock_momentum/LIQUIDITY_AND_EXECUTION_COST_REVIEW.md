# Liquidity And Execution Cost Review

Individual stock momentum can produce attractive historical ranks by selecting small or illiquid names. A $3,000 paper/demo account needs realistic constraints.

## Required Constraints

- minimum price filter to avoid penny-stock artifacts,
- minimum dollar volume filter,
- maximum position concentration,
- explicit spread/slippage model,
- turnover-cost model,
- fixed rebalance frequency,
- no shorting,
- no borrow assumptions,
- no margin,
- no leverage,
- fractional-share assumption stated explicitly,
- execution limits consistent with a small paper/demo account.

## Target Fit

It is uncertain whether individual stock momentum can realistically target +$300/+400 without using tiny or illiquid names. A future implementation review must require liquidity screens and cost sensitivity before any target-rate interpretation.

Conclusion: execution cost and liquidity review is a blocker for credible implementation.

