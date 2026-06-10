# Benchmark And Failure Criteria

## Primary Benchmark

- `combo_SPY200d_GLD_50_50_v1`

## Secondary Benchmarks

- `asset_class_tsmom_top2_v1`
- `SPY_200d_trend_model`
- `SPY_buy_hold`
- `BIL_cash_proxy`
- `A_ETF_sector_momentum`, if an exact stream becomes available
- `qqq_spy_gld_ief_dual_momentum_v1`, as a high-upside/high-risk comparator
- `value_momentum_factor_etf_rotation_v1`, as a duplicate/near-duplicate comparator

## Failure Criteria

Reject, defer, or keep as watchlist if any of the following occur in a future research_sample:

- It does not beat combo/top2 on stop-aware profit/risk.
- Higher target rate comes only with worse drawdown.
- Stress degradation is worse than combo/top2.
- Stop-hit rate is materially higher than combo or `SPY_200d_trend_model`.
- Sector concentration dominates results.
- Performance comes from only one sector or one regime.
- Exact fresh-window stream cannot be produced.
- Late-inception sector handling creates bias.
- Result mostly duplicates equity beta.

## Candidate Evidence Standard

A future research_sample result is not candidate-exhaustive validation and cannot activate paper-forward observation. If it looks promising, the next evidence step would be a separate candidate_exhaustive review, not promotion.

