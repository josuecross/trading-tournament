# Duplicate And Correlation Risk Review

Compared against: `A_ETF_sector_momentum`, `SPY_200d_trend_model`, `combo_SPY200d_GLD_50_50_v1`, `asset_class_tsmom_top2_v1`, `SPY_buy_hold`, `GLD_buy_hold`, `BIL_cash_proxy`, `qqq_spy_gld_ief_dual_momentum_v1`, and `value_momentum_factor_etf_rotation_v1`.

## Findings

1. Is sector_top2 mostly equity beta?
   It may be. Sector ETFs are U.S. equity sleeves, so a top-2 sector rule can improve target probability through dispersion while still being dominated by equity beta and market-regime timing.

2. Is it a near-duplicate of `A_ETF_sector_momentum`?
   It is conceptually close. It should be treated as duplicate-risk until a future implementation proves it is a clean minimal rule with independent streams and diagnostics.

3. Could it add target probability through sector dispersion?
   Yes. Concentrating into stronger sectors could increase +300/+400 target rates versus broad SPY exposure, but this may also increase drawdown and stop-hit risk in equity bear markets.

4. Could it increase drawdown during equity bear markets?
   Yes. If the cash/trend filter lags or sector leadership rotates quickly, top sectors can still fall with the market and consume the -$600 drawdown budget.

5. What concentration metrics must future implementation report?
   Sector selection frequency, sector allocation share, maximum single-sector allocation, top-sector dominance, BIL/cash allocation frequency, equity exposure share, and sector turnover.

6. What correlation metrics must future implementation report?
   Correlation of daily/window returns and stop-enforced equity paths versus SPY, `SPY_200d_trend_model`, `combo_SPY200d_GLD_50_50_v1`, `asset_class_tsmom_top2_v1`, `qqq_spy_gld_ief_dual_momentum_v1`, and `value_momentum_factor_etf_rotation_v1`.

## Duplicate Risk Result

Duplicate risk status: `conditional`.

The candidate may be useful if sector dispersion improves stop-aware target rates without worse drawdown, but it may simply repackage equity beta or duplicate A-sector logic. A future research_sample prompt must include duplicate and concentration diagnostics.

