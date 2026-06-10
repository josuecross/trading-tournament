# Strategy Candidate Queue Summary

This candidate queue was created because the project should continue disciplined research after finding a paper-forward candidate, but should not randomly add strategies or tune variants. The queue separates implementation-review candidates, research-only candidates, data-gated ideas, execution-gated ideas, complexity-gated ideas, near-duplicates, deferred items, and rejected items.

New candidates are not added to tonight's validation because the current Profit Exploration finalists already need full 30/60/90/180 candidate-exhaustive validation. Adding fresh candidates now would contaminate that validation queue and blur evidence finality.

## Highest Priority Candidates

1. `qqq_spy_gld_ief_dual_momentum_v1`: highest priority ETF implementation-review candidate after current finalist validation, if QQQ cached data is available and the rule is confirmed not to duplicate existing top2 behavior.
2. `value_momentum_factor_etf_rotation_v1`: strongest factor-research queue item, but it first needs ETF proxy, inception-date, and benchmark review.
3. `sector_top2_momentum_simple_v1`: promising if an exact fresh-window stream can be exposed or a clean minimal implementation can be approved without modifying `A_ETF_sector_momentum`.

## Data-Gated Candidates

- `managed_futures_proxy_etf_trend_v1`: potentially diversifying, but ETF/fund proxy history and methodology are uncertain.
- `commodity_basket_etf_momentum_v1`: potentially diversifying, but commodity ETF structure and roll-yield effects require review.
- `crypto_spot_tsmom_tier2_review_v1`: high target potential, but Tier 2 exchange-specific data, fees, spreads, and 24/7 handling are unresolved.
- `individual_stock_momentum_gate1b_v1`: requires survivorship-free data, delisting treatment, point-in-time universe, execution model, and cost/runtime review.

## Execution-Gated Candidates

The high-complexity blocked reference covers options, futures, forex, intraday, volatility products, and crypto leverage/perps. These are not ignored; they are blocked because execution, margin, spread, chain, roll, timestamp, or product-mechanics models are missing.

## Rejected For Now

- Options premium
- Intraday/day trading
- Volatility products
- Crypto leverage/perps
- AI trading gate

These are rejected for now because the project lacks the required execution, risk, and data framework, or because they conflict with project boundaries.

## Most Likely To Improve Profit Potential

- `qqq_spy_gld_ief_dual_momentum_v1`
- `sector_top2_momentum_simple_v1`
- `crypto_spot_tsmom_tier2_review_v1`, research-only and data/execution-gated
- `individual_stock_momentum_gate1b_v1`, research-only and data-gated

## Most Likely To Reduce Drawdown

- `low_vol_quality_defensive_rotation_v1`
- `treasury_duration_trend_rotation_v1`
- `managed_futures_proxy_etf_trend_v1`, if proxy data is usable

## Likely Duplicates Or Near-Duplicates

- `qqq_spy_gld_ief_dual_momentum_v1` may duplicate equity momentum risk if QQQ dominates.
- `sector_top2_momentum_simple_v1` may duplicate existing `A_ETF_sector_momentum` intent unless the exact stream issue is resolved.
- Treasury and defensive factor candidates may duplicate BIL/IEF defensive behavior and become too slow.

## After Current Full Validation

After the full 30/60/90/180 validation of the current finalists, the next implementation-review decision should compare:

- `qqq_spy_gld_ief_dual_momentum_v1`
- `value_momentum_factor_etf_rotation_v1`
- `sector_top2_momentum_simple_v1`

The next research-only memo should focus on `individual_stock_momentum_gate1b_v1`, because the return prior is meaningful but the project gate remains blocked.

No candidate is implemented here. No paper-forward row changes. No real-money recommendation is made.
