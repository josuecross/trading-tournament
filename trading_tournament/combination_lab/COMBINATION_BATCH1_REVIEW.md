# Historical Combination Batch 1 Review

This review authorizes one research_sample batch only. It does not authorize candidate_exhaustive, paper-forward observation, live trading, broker integration, order placement, or a real-money recommendation.

The batch tests exactly three fixed combinations:

- `combo_plus_top2_50_50_v1`: 50% `combo_SPY200d_GLD_50_50_v1` plus 50% `asset_class_tsmom_top2_v1`.
- `combo_plus_managed_futures_80_20_v1`: 80% `combo_SPY200d_GLD_50_50_v1` plus 20% `managed_futures_proxy_etf_trend_v1`.
- `top2_plus_managed_futures_80_20_v1`: 80% `asset_class_tsmom_top2_v1` plus 20% `managed_futures_proxy_etf_trend_v1`.

The active combo paper/demo observation remains separate. The active combo rules are not changed, and SPY_200d remains the frozen control.

Batch implementation requirements:

- Use exact component daily return streams, not summary statistics.
- Rebuild every rolling window from local returns with a fresh $3,000 starting equity.
- Reset high-water mark, target state, and stop state for every window.
- Use fixed weights only.
- Use no optimization and no optimized weights.
- Use standard/stress cost assumptions already used by Profit Exploration.
- Use no leverage, margin, shorting, futures contract logic, broker integration, or order placement.
- Keep managed-futures combinations short-history and fund-wrapper-proxy labeled.
