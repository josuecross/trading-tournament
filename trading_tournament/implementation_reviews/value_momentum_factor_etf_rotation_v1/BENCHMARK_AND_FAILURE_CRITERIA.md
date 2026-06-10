# Benchmark And Failure Criteria

## Primary Benchmarks

- combo_SPY200d_GLD_50_50_v1
- asset_class_tsmom_top2_v1

## Secondary Benchmarks

- SPY_200d_trend_model
- SPY_buy_hold
- GLD_buy_hold
- BIL_cash_proxy
- qqq_spy_gld_ief_dual_momentum_v1 as a high-upside/high-risk comparator

## Failure Criteria

Reject, demote, or keep the candidate out of candidate_exhaustive if any future research_sample result shows:

- cannot beat combo or top2 on stop-aware profit/risk,
- higher target rates only through worse drawdown,
- stress degradation worse than combo/top2,
- stop-hit rate materially higher than combo/top2,
- worst drawdown consumes too much of the -600 risk budget,
- results mostly duplicate SPY/equity beta,
- one ETF dominates allocations,
- too slow for +300/+400,
- 2013-onward sample is too short for confidence,
- proxy risk is too high.

## Required Verdict Boundaries

A future research_sample implementation can be labeled only as research_sample, watchlist, candidate_exhaustive_queue, duplicate_or_near_duplicate, too_slow, too_risky, or incomplete_evidence. No paper-forward activation or real-money recommendation can follow from this review.
