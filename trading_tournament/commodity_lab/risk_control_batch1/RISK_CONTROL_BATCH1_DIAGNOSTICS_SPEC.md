# Risk-Control Batch 1 Diagnostics Spec

Each candidate must report:

- +300/+400 rates for 30/60/90/180 windows.
- +600/+900/+1200 rates.
- Stop-hit rates.
- Worst drawdown.
- Risk-budget usage.
- Median and p95 stop-enforced equity.
- Stress degradation.
- BIL/cash allocation or fallback share.
- Product or sleeve concentration.
- Comparison versus base commodity, combo, top2, SPY_200d, GLD, and BIL.
- Correlation diagnostics if standard equity curves are available.
- Candidate_exhaustive recommendation as review-only, never run-now.

If target-window co-movement or drawdown co-incidence is unavailable, the output must say unavailable rather than infer independence from labels.

