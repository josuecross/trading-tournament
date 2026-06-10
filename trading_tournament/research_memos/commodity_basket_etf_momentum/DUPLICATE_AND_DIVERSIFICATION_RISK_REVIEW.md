# Duplicate And Diversification Risk Review

## Benchmark Comparisons

Future commodity basket ETF momentum must compare against:

- GLD_buy_hold,
- combo_SPY200d_GLD_50_50_v1,
- asset_class_tsmom_top2_v1,
- SPY_200d_trend_model,
- managed_futures_proxy_etf_trend_v1,
- BIL_cash_proxy.

## Questions

1. Could commodity basket products add real diversification beyond GLD?

   Possibly. Broad commodity wrappers may add energy, industrial metals, agriculture, and commodity-roll exposure beyond gold. This is not proven until correlation, drawdown co-incidence, and target-window diagnostics are computed.

2. Could they simply duplicate existing top2 commodity/GLD exposure?

   Yes. If future returns mostly track GLD or the existing top2 commodity sleeve, the family should be marked duplicate_or_near_duplicate.

3. Could they improve inflation/commodity-regime exposure?

   Possibly, especially in commodity/inflation regimes. This must be tested with stress-period and regime diagnostics rather than assumed from labels.

4. Could roll decay make them too slow or risky?

   Yes. Futures-linked products can lose value through roll decay and product costs even when spot commodities appear diversified.

5. What correlation and target-window diagnostics must future implementation report?

   Required diagnostics include daily return correlation versus combo/top2/SPY_200d/GLD/BIL, rolling 60/90-day correlation, stress-period correlation, target-window co-movement, drawdown co-incidence, component contribution, and incremental target-hit windows.

6. What would make this family reject-worthy?

   Reject if product structure is too opaque, data history is too short, target rates are weak, drawdowns are worse than combo/top2, returns duplicate GLD/top2, liquidity/spreads are unrealistic, or exact fresh-window streams cannot be produced.
