# Tier 2 Risk-Control Batch 1 Review

This batch tests whether simple BTC/ETH spot-only risk-control rules can preserve target potential while reducing the extreme stop/drawdown behavior seen in earlier exploratory crypto rows.

The batch remains separate from ETF/fund core evidence. It is not paper-forward eligible and cannot create a real-money recommendation.

Candidates:

- `crypto_spot_tsmom_top1_cash_filter_v1`
- `crypto_spot_equal_weight_200d_filter_v1`
- `combo_plus_crypto_spot_tsmom_90_10_v1`

Research controls:

- BTC/ETH only.
- BIL fallback or cash sleeve.
- Monthly rebalance.
- 126-trading-day return signal.
- 200-day SMA filter.
- No leverage, margin, shorting, futures, perpetuals, options, or exchange execution.
- No parameter tuning or grid search.
- No candidate_exhaustive in this task.

The active `combo_SPY200d_GLD_50_50_v1` paper/demo observation remains unchanged. `SPY_200d_trend_model` remains the frozen control.
