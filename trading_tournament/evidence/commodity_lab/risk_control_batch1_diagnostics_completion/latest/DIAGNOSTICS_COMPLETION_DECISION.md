# Diagnostics Completion Decision

Decision: `diagnostics_support_watchlist_only_for_combo_plus_commodity_80_20`

candidate_exhaustive_review_recommended: `false`

candidate_exhaustive_run: `false`

## Rationale

The diagnostics completion improved the evidence from correlation-only review to window-level target co-movement plus fixed-sleeve final-equity contribution.

combo_plus_commodity_basket_80_20_v1 has a strong risk profile and some incremental target windows, but it does not yet justify candidate_exhaustive review:

- 90d +400 incremental windows versus combo/top2/GLD were zero.
- 180d incremental windows versus combo were small: 3 new +300 windows and 3 new +400 windows.
- Score delta versus combo was only `+4.98`.
- The candidate lagged top2, SPY_200d, and GLD on reported score.
- Correlation to combo remained high at `0.962`.
- Component contribution shows the combo sleeve dominates 90d target-hit windows and remains the larger contributor at 180d.
- Drawdown magnitude improved, but worst 180d drawdown windows overlapped combo and GLD in the inspected worst samples.

## Status Effects

- `combo_plus_commodity_basket_80_20_v1`: watchlist only after diagnostics completion.
- `commodity_basket_tsmom_top2_200d_filter_v1`: keep `filter_ineffective_or_bug_review`.
- `commodity_basket_tsmom_top2_half_bil_v1`: keep `too_slow_defensive_watchlist`.
- `commodity_basket_tsmom_top2_v1`: keep `research_sample_candidate_risk_budget_breach`.

## Future Checks If Reopened

Any future candidate_exhaustive prompt would need:

- product identity and wrapper/tax/roll-risk review,
- exact daily component contribution streams,
- stronger incremental target-window evidence versus combo/top2/GLD,
- maintained 90d/180d drawdown inside or near the -$600 budget,
- no paper-forward promotion without a separate promotion review.

This task does not run candidate_exhaustive and does not change the active combo paper/demo observation.

