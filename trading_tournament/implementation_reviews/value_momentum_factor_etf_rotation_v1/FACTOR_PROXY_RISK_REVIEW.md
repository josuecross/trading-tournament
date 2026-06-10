# Factor Proxy Risk Review

ETF factor proxies are not the same as academic long-short or stock-level factor portfolios. They may carry broad equity beta, sector constraints, fund-specific index methodology, rebalance timing, turnover, expense ratios, liquidity effects, and construction choices that distort the intended value, momentum, quality, or low-volatility exposure.

## Review Answers

1. Do these ETFs cleanly represent value/momentum/quality/low-vol factors? Not perfectly. MTUM, VTV/VLUE, QUAL, and USMV/SPLV are investable ETF proxies, not pure factor portfolios.
2. Is ETF factor rotation likely to be mostly U.S. equity beta? That is a major risk. All risky proxies are U.S. equity ETFs, so any target-rate improvement may be driven by equity beta rather than distinct factor timing.
3. Does factor rotation add real diversification beyond SPY_200d, combo, and top2? Possibly, but this remains uncertain. The best case is a smoother equity-factor mix with improved stop-aware profit/risk. The failure case is a near-duplicate equity momentum strategy.
4. What concentration diagnostics must future implementation report? Allocation frequency by ETF, maximum single-ETF allocation, MTUM allocation share, VTV/VLUE allocation share, QUAL allocation share, USMV/SPLV allocation share, SPY allocation share, BIL fallback frequency, equity allocation share, and concentration warnings.
5. What correlation diagnostics must future implementation report? Daily return correlation versus combo_SPY200d_GLD_50_50_v1, asset_class_tsmom_top2_v1, SPY_200d_trend_model, qqq_spy_gld_ief_dual_momentum_v1, SPY_buy_hold, GLD_buy_hold, and BIL_cash_proxy.
6. What would prove the factor strategy is not useful? It should be rejected or demoted if target rates improve only through higher drawdown, if stress degradation is worse than combo/top2, if stop-hit rate rises materially, if it is highly correlated with SPY/top2/QQQ, or if one ETF dominates allocations.

## Remaining Proxy Risks

- The common overlap starts in 2013, so evidence will be shorter than SPY/BIL and may miss important stress regimes.
- ETF methodologies can change and may not map cleanly to academic factors.
- Value and momentum proxies can behave like cyclical equity exposure.
- Quality and low-volatility proxies can reduce volatility but may also make the strategy too slow for +300/+400 thresholds.

No real-money recommendation is made.
