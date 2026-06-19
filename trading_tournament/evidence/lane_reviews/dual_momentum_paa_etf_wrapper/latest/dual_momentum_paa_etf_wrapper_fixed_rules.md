# Dual Momentum PAA ETF Wrapper Fixed Rules

## `dm_global_dual_momentum_top1_v1`

Universe: `SPY;EFA;EEM;BIL`

Monthly rebalance; rank SPY, EFA, EEM by 126-day return; selected asset must have positive 126-day return and close > 200-day SMA; hold top 1 else BIL.

Purpose/profit driver: Minimal global dual momentum selects the strongest global equity wrapper while using BIL for failed absolute momentum.

No leverage. No direct futures contracts. No parameter optimization or grid search.

## `dm_multi_asset_top2_absolute_momentum_v1`

Universe: `SPY;QQQ;EFA;EEM;IWM;GLD;IEF;BIL`

Monthly rebalance; rank SPY, QQQ, EFA, EEM, IWM, GLD, IEF by 126-day return / 60-day realized volatility; hold top 2 eligible assets equally; unused allocation to BIL.

Purpose/profit driver: Multi-asset relative plus absolute momentum may diversify beyond equity-only trend.

No leverage. No direct futures contracts. No parameter optimization or grid search.

## `dm_protective_canary_bil_v1`

Universe: `SPY;QQQ;EFA;EEM;GLD;IEF;BIL`

Monthly rebalance; if EFA and EEM both have negative 126-day return or are below 200-day SMA hold BIL; otherwise rank SPY, QQQ, GLD, IEF by 126-day return / 60-day realized volatility and hold top 2 eligible assets.

Purpose/profit driver: Global canary may reduce crash exposure while still allowing offensive participation.

No leverage. No direct futures contracts. No parameter optimization or grid search.

## `dm_balanced_offensive_defensive_v1`

Universe: `SPY;QQQ;EFA;EEM;GLD;IEF;BIL`

Monthly rebalance; if SPY > 200-day SMA allocate 60% best eligible offensive asset and 40% best eligible defensive asset; if SPY <= 200-day SMA allocate 40% defensive and 60% BIL.

Purpose/profit driver: Balanced offensive/defensive sleeve may improve drawdown without fully abandoning target power.

No leverage. No direct futures contracts. No parameter optimization or grid search.

## `dm_paa_breadth_protection_v1`

Universe: `SPY;QQQ;EFA;EEM;IWM;GLD;IEF;BIL`

Monthly rebalance; if fewer than 2 risky assets are positive, hold 50% best eligible defensive asset and 50% BIL; otherwise rank all eligible assets by 126-day return / 60-day volatility and hold top 2.

Purpose/profit driver: Protective asset allocation breadth may avoid broad risk-off regimes while keeping multi-asset opportunity.

No leverage. No direct futures contracts. No parameter optimization or grid search.
