# Promotion Review: combo_SPY200d_GLD_50_50_v1

## Research Boundary

This is research-only paper/demo evidence. No real-money recommendation is made. No broker integration, live orders, or order placement are added.

## What It Is

`combo_SPY200d_GLD_50_50_v1` is a fixed, predeclared, independent $3,000 Profit Exploration experiment. It combines:

- 50% `SPY_200d_trend_model`
- 50% `GLD_buy_hold`
- monthly rebalance
- no leverage, no margin, no shorting

It is not allocation advice and is not paper-forward active.

## Evidence Supporting Promotion Review

- Full 30/60/90/180 `candidate_exhaustive` validation completed with `all_possible` windows.
- Accounting integrity passed: every rolling window starts at $3,000 with reset high-water mark, target state, and stop state.
- The combo is the `balanced_drawdown_aware_score_v2` leader and practical drawdown-aware challenger.
- It had 0.0% standard stop-hit rate at 30/60/90/180 horizons.
- It had better 90-day and 180-day worst drawdown than both `SPY_200d_trend_model` and `asset_class_tsmom_top2_v1`.
- It had higher 90-day median stop-enforced equity than `SPY_200d_trend_model`.
- It had lower stress degradation than `SPY_200d_trend_model`.

## Evidence Against Promotion

- It did not beat `SPY_200d_trend_model` on raw +300 or +400 rates at the main 90-day horizon.
- It did not beat `SPY_200d_trend_model` on 180-day +300 or +400 rates.
- It is a fixed combination and could dilute target-rate speed.
- It introduces GLD exposure, so the promotion review must ensure the benefit is risk-control diversification rather than hidden commodity concentration.
- It should not replace the existing frozen `SPY_200d_trend_model` observation without a separate explicit decision.

## Direct Answers

1. Evidence supports promotion review because full candidate-exhaustive research validation is complete and drawdown-aware v2 ranks the combo as the practical leader.
2. Evidence argues against immediate activation because raw +300/+400 target rates are weaker than `SPY_200d_trend_model` at 90 and 180 days.
3. The combo did not beat SPY_200d on raw +300/+400 target rates overall.
4. The combo did beat SPY_200d on drawdown and stop risk.
5. The combo beat `asset_class_tsmom_top2_v1` under drawdown-aware v2, but not under original final_score.
6. The combo survived stress costs better than SPY_200d, with stress degradation 22.03 versus 63.18.
7. The combo improved 90-day median stop-enforced equity versus SPY_200d: $3,107.86 versus $3,097.12.
8. The combo did not clearly improve 90-day p95 equity versus SPY_200d: $3,414.35 versus $3,418.41, but did improve 180-day p95: $3,722.65 versus $3,720.94.
9. The combo stayed inside the -$600 risk budget better than SPY_200d: 90-day risk-budget use 0.75 versus 1.10, and 180-day 0.86 versus 1.24.
10. Strongest argument for promotion review: it is the practical drawdown-aware leader after full all-horizon validation.
11. Strongest argument against promotion review: it sacrifices raw target-hit rate relative to SPY_200d.
12. The combo should be promoted to paper-forward review, not paper-forward activation.
13. The combo should run alongside SPY_200d in any future observation plan rather than replace SPY_200d automatically.
14. Evidence that would reject it from paper-forward review: loss of drawdown advantage, higher stop-hit rate, hidden rule drift, or failure to preserve fixed 50/50 rules.

## Decision

Promotion review decision: `promote_to_paper_forward_review`.

This means the next allowed action is to create a new isolated paper-forward observation plan. It does not activate paper-forward observation.

