# Promotion Decision

Decision: `promote_to_paper_forward_review`

## Meaning

This decision means `combo_SPY200d_GLD_50_50_v1` deserves a separate paper-forward observation plan review.

It does not mean:

- paper-forward activation
- replacement of `SPY_200d_trend_model`
- real-money suitability
- broker integration
- live orders
- strategy-rule changes

## Rationale

The combo completed full 30/60/90/180 candidate-exhaustive research validation and passed accounting integrity. It did not beat SPY_200d on raw +300/+400 target rates, but it materially improved stop behavior, worst drawdown, drawdown-budget usage, and drawdown-aware score v2.

## Recommended Next Action

Create a new isolated paper-forward observation plan proposal. The plan should run alongside the existing frozen `SPY_200d_trend_model` observation rather than replace it.

## Rejection Conditions

Reject from paper-forward review if any future plan would:

- tune weights after seeing results
- change the SPY_200d rule
- change GLD sleeve behavior
- hide GLD concentration risk
- replace SPY_200d without explicit decision
- create broker/live/real-money features

No real-money recommendation is made.

