# Duplicate And Correlation Risk Review

The candidate must be compared against existing project finalists and benchmarks after any future research_sample implementation. This review does not run that implementation.

## Comparator Set

- SPY_200d_trend_model
- combo_SPY200d_GLD_50_50_v1
- asset_class_tsmom_top2_v1
- qqq_spy_gld_ief_dual_momentum_v1
- SPY_buy_hold
- GLD_buy_hold
- BIL_cash_proxy

## Duplicate-Risk Assessment

Factor ETF rotation could be a different return driver if value, quality, and low-volatility exposures materially change drawdown and target behavior versus SPY_200d, combo, top2, and QQQ dual momentum. It could also be mostly another U.S. equity momentum/beta variant if allocations concentrate in equity factor ETFs and track SPY/QQQ behavior.

The data gate now passes, so duplicate risk should be measured in the future research_sample implementation. It is not resolved by this review.

## Required Future Correlation Metrics

- Daily return correlation versus combo_SPY200d_GLD_50_50_v1.
- Daily return correlation versus asset_class_tsmom_top2_v1.
- Daily return correlation versus SPY_200d_trend_model.
- Daily return correlation versus qqq_spy_gld_ief_dual_momentum_v1.
- Daily return correlation versus SPY_buy_hold, GLD_buy_hold, and BIL_cash_proxy.
- SPY-like and QQQ-like beta diagnostics, if the existing reporting layer supports them.

## Required Future Allocation Metrics

- Selection/allocation frequency by MTUM, VTV, QUAL, USMV, SPY, and BIL.
- BIL fallback frequency.
- Maximum single-ETF allocation.
- Equity-factor allocation share.
- Cash/Treasury allocation share.
- Concentration warning if one ETF dominates.
- Equity-beta duplicate warning if MTUM/SPY or other equity ETFs explain most outcomes.

## Duplicate Or Near-Duplicate Conditions

Mark the candidate `duplicate_or_near_duplicate` if it has high correlation to SPY/QQQ/top2, if one equity factor ETF dominates allocations, or if target improvement is explained by higher equity beta and worse drawdown rather than a distinct stop-aware profit/risk improvement.
