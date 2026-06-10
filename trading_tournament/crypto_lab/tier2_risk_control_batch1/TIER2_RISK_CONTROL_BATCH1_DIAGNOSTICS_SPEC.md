# Diagnostics Spec

The evidence packet should report:

- rule summary
- data/cache status
- symbols used and failed
- +300/+400 rates for 30/60/90/180
- +600/+900/+1200 rates
- stop-hit rates
- worst drawdown
- risk-budget usage
- median and p95 stop-enforced equity
- stress degradation
- BIL/cash allocation share
- max crypto exposure
- BTC/ETH allocation frequencies
- comparison versus combo/top2/SPY_200d/GLD
- correlation/co-movement if available
- target-window incremental hits if available
- drawdown co-incidence if available
- verdict
- candidate_exhaustive recommendation
- no real-money recommendation

If target-window attribution or drawdown co-incidence is unavailable, the packet must mark it unavailable rather than infer independence from correlation.
