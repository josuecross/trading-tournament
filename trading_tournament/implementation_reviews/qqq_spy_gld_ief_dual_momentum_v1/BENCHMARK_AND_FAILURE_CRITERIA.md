# Benchmark And Failure Criteria

## Primary Benchmark

`asset_class_tsmom_top2_v1`

## Secondary Benchmarks

- `combo_SPY200d_GLD_50_50_v1`
- `SPY_200d_trend_model`
- `SPY_buy_hold`
- `GLD_buy_hold`
- `BIL_cash_proxy`

## Failure Criteria

Reject or defer the candidate if any of these occur:

- does not beat top2 on stop-aware profit/risk
- higher target rate comes only with worse drawdown
- stress degradation is worse than top2 or combo
- stop-hit rate is materially higher than top2 or combo
- worst drawdown consumes too much of the -$600 budget
- QQQ dominates allocation and creates an equity-beta duplicate
- QQQ data history becomes insufficient under no-network constraints

## Required Result Interpretation

The candidate must be ranked by stop-aware profit/risk, not by target-hit rate alone. It cannot become paper-forward active from a research_sample run.

