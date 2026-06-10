# Combination Design Gate

Historical combination testing is allowed only after a combination implementation review approves a fixed rule.

## Requirements

- Combination rule is fixed before running.
- Components are already tested candidates or benchmarks.
- Each combination has an independent `$3,000` simulated account.
- No live, broker, or order behavior.
- No parameter grid.
- No hindsight weight optimization.
- Maximum combinations per batch: `3`.
- Primary benchmarks: `combo_SPY200d_GLD_50_50_v1`, `asset_class_tsmom_top2_v1`, `SPY_200d_trend_model`, `BIL_cash_proxy`, `GLD_buy_hold`, `SPY_buy_hold`.
- Failure criteria are written before test.
- Each combination reports target ladder, stop rate, drawdown, median/p95 equity, stress degradation, and correlation/co-movement if available.

## Allowed Verdicts

- `candidate_exhaustive_queue`
- `research_sample_candidate`
- `watchlist`
- `too_slow`
- `too_risky`
- `duplicate_or_near_duplicate`
- `incomplete_evidence`
- `reject_for_now`

## Forbidden Behavior

- Do not use the first paper-forward combo result to alter historical combinations.
- Do not optimize weights after seeing results.
- Do not add a combination because a prior candidate disappointed.
- Do not combine weak candidates without a predeclared diversification hypothesis.
- Do not mutate active paper-forward rows.

