# Rejection And Promotion Criteria

Reject or watchlist a future research_sample row if:

- +$300 target-before-stop rate is not meaningfully competitive.
- +$400 target-before-stop rate is negligible.
- Drawdown budget still breaches.
- Target potential is too diluted.
- It duplicates `SPY_200d_trend_model` or active combo behavior.
- It depends on tuned volatility thresholds.
- It needs leverage or shorting.
- Evidence is too short.
- Stress assumptions break the row.
- It is worse than `SPY_200d_trend_model`, active combo, SPY buy-hold, or BIL on relevant metrics.

A future row may request promotion_review only if:

- it improves drawdown without destroying target probability, or
- it improves +$300 target-before-stop versus current leaders without breaching risk budget, or
- it shows materially different target windows from existing leaders, and
- it has basic QA, target, drawdown, stop, benchmark, and duplication evidence.

A future row may request candidate_exhaustive queue only after promotion review confirms:

- meaningful target evidence
- acceptable drawdown evidence
- no obvious stress fragility
- no near-duplicate behavior
- no data or instrument blocker
- no mutation of active paper/demo rows
