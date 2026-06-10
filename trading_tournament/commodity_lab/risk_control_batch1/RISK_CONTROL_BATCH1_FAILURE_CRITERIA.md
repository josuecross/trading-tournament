# Risk-Control Batch 1 Failure Criteria

A candidate fails or remains watchlist-only if any of the following dominate:

- It does not improve stop-aware score versus the base commodity rule.
- It does not improve stop-aware score versus at least one primary benchmark.
- 90d or 180d worst drawdown remains materially beyond the -$600 budget.
- Stop-hit rate is materially worse than combo or top2.
- +300/+400 target rates are diluted into too-slow behavior.
- Stress degradation is not acceptable.
- Product/wrapper concentration creates an interpretation problem.
- Combo-plus-commodity mostly duplicates GLD/top2/combo exposure.
- Exact fresh-window streams cannot be produced.
- Wrapper warnings are hidden or interpreted as direct futures strategy evidence.

Candidate_exhaustive is never run in this batch.

