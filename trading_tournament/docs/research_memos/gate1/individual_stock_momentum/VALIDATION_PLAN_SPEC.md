# Validation Plan Spec

If Gate 2 is ever approved, the prototype must be validated with the same or stricter standards as ETF research.

## Required Tests

- Full-period test.
- In-sample / validation / out-of-sample periods.
- Rolling 30/60/90/180-day windows.
- Standard and stress slippage.
- Target-before-stop analysis.
- Benchmark-relative performance.
- Drawdown analysis.
- Time-to-target.
- Strategy contribution.
- Symbol concentration.
- Top-trade dependence.
- Regime performance.
- Sector concentration.
- Data quality report.
- Anti-overfitting log.

## Finality Rule

No sampled result should be called final. Serious claims require exhaustive finalist validation or a clearly documented final audit mode.

## Failure Criteria

Gate 2 should fail if the strategy depends on a few winners, underperforms ETF alternatives after stress costs, hits the -20% stop too frequently, cannot beat unbiased stock benchmarks, or relies on biased data.

