# Next Action Plan

## Next Prompt Direction

Create an implementation/data review only for:

`commodity_basket_etf_momentum_v1`

## Candidate Symbols To Review

Illustrative symbols for review only:

- DBC
- PDBC
- COMT
- GSG
- USCI

These are not approved symbols yet.

## Required Review Topics

- ETF versus ETN/product wrapper structure,
- commodity futures roll yield exposure,
- inception history and common overlap,
- expense ratio and product fees,
- K-1/tax/product risks where applicable,
- issuer/fund closure/liquidity risk,
- tracking methodology and collateral mechanics,
- whether product behavior duplicates GLD or existing top2 commodity sleeves,
- whether target potential is realistic for +300/+400 hurdles,
- whether drawdown/roll decay can breach the -600 budget.

## Forbidden In Next Prompt Unless Explicitly Approved

- no data download until product/data review passes,
- no strategy implementation,
- no implementation,
- no backtest,
- no Profit Exploration,
- no candidate_exhaustive,
- no paper-forward observation,
- no futures contract logic,
- no leverage, margin, or shorting,
- no real-money recommendation.

## Fallback Plan

If commodity product risks are too high, move to `treasury_duration_trend_rotation_v1` target-potential review rather than returning to blocked stock-provider loops.
