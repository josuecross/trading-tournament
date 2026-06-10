# Observation Scope

- observation_id: `combo_SPY200d_GLD_50_50_v1_observation_plan_v1`
- strategy_id: `combo_SPY200d_GLD_50_50_v1`
- account_type: simulated paper/demo only
- starting_equity: 3000
- primary_target: +300
- aggressive_target: +400
- extended_target_ladder: +600, +900, +1200 for evidence only
- hard_risk_budget: -600 / -20%
- start_date: not activated here; a later activation prompt must choose the start date
- observation_mode: parallel observation candidate, not replacement

## Comparison Rows

- `SPY_200d_trend_model`
- `asset_class_tsmom_top2_v1`
- `BIL_cash_proxy`
- `GLD_buy_hold`
- `SPY_buy_hold`

## Boundaries

No broker integration, no live orders, no order placement, no real-money recommendation, no rule changes, and no paper-forward activation are allowed by this review.

