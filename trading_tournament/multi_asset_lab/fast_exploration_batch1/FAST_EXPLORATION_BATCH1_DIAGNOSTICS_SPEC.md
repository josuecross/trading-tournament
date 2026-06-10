# Fast Exploration Batch 1 Diagnostics Spec

Profit Exploration must report target rates for +300, +400, +600, +900, and +1200 across 30/60/90/180 day windows, stop-hit rates, worst drawdown, risk-budget usage, median and p95 stop-enforced equity, stress degradation, BIL allocation share, max asset or sleeve concentration, and asset allocation frequencies.

Comparisons should include combo_SPY200d_GLD_50_50_v1, asset_class_tsmom_top2_v1, SPY_200d_trend_model, GLD_buy_hold, commodity_basket_tsmom_top2_v1, combo_plus_commodity_basket_80_20_v1 if available, and combo_plus_crypto_spot_tsmom_90_10_v1 if available.

Correlation and co-movement diagnostics should be treated as preliminary unless exact target-window IDs and drawdown overlap windows are separately exported in a later diagnostics prompt.

Candidate_exhaustive is not run in this batch. Any future recommendation must remain a separate prompt and must preserve exploratory ETF/fund-wrapper labels.
