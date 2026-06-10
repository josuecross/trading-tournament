# Commodity Risk-Control Batch 1 Verdict Audit

This is a verdict/diagnostics audit only.

It reads existing Commodity Risk-Control Batch 1 and Profit Exploration evidence. It does not implement strategies, add commodity variants, run candidate_exhaustive, change the active combo paper-forward observation, replace SPY_200d, download data, use futures contracts directly, or make a real-money recommendation.

The audit focuses on whether any risk-control row, especially `combo_plus_commodity_basket_80_20_v1`, deserves a future candidate_exhaustive review prompt.

Research boundary:

- Active combo paper/demo observation remains unchanged.
- SPY_200d remains the frozen control.
- Commodity wrapper evidence remains exploratory, non-final, not paper-forward, and not real-money evidence.
- No futures contract, leverage, margin, shorting, broker, live-order, or order-placement behavior is added.
