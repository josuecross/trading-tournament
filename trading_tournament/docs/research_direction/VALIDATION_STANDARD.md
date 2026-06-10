# Validation Standard

Future strategies must be tested against the same research discipline. No sampled result should be called validated.

## Required For ETF-Like Strategies

- Full-period backtest.
- Standard slippage.
- Stress slippage.
- Benchmark comparison.
- Rolling 30/60/90/180-day windows.
- Target-before-stop analysis.
- Max drawdown.
- Time-to-target.
- Strategy contribution.
- Symbol contribution.
- Data quality review.
- Anti-overfitting log.

ETF-like strategies may use the existing daily adjusted OHLC framework if their fills, risk, and universe assumptions are compatible.

## Required Before Non-ETF Implementation

- Data availability.
- Execution model.
- Spread/slippage model.
- Margin/leverage model if applicable.
- Event timestamp quality if applicable.
- Benchmark.
- Safety constraints.
- Reason to believe the daily ETF framework is insufficient.

Non-ETF strategies must not be coded simply because they appear more exciting or volatile.

## Validation Modes

### smoke

Fast code correctness check. It is not research evidence.

### research_sample

Preliminary research screen. Useful for iteration, but non-final.

### candidate_exhaustive

All-possible rolling validation for finalists only. This is the minimum mode for serious candidate claims.

### final_audit

Slow archival audit for final research review. It should include complete evidence, final assumptions, and no parameter changes.

## Sampling And Finality

Sampled validation is useful for development and screening. It is not final validation. Exhaustive validation is reserved for finalists because it is expensive and should not be run casually across every idea.

Final claims require `candidate_exhaustive` or `final_audit`. Any document using sampled rolling windows must clearly state that the results are non-final.
