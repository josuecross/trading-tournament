# Combo Versus SPY_200d Observation Design

The combo must be evaluated beside the existing frozen `SPY_200d_trend_model` paper/demo observation. It must not replace it.

## Monthly Comparison Fields

Each future checkpoint should compare:

- current equity
- distance to +300
- distance to +400
- distance to -600 stop
- max drawdown since observation start
- trailing drawdown
- target hit flags
- stop hit flags
- signal state
- equity difference versus SPY_200d
- drawdown difference versus SPY_200d
- whether combo is improving risk-adjusted observation evidence

## Governance Boundary

SPY_200d remains frozen until a separate governance decision says otherwise. Combo observation evidence may support later review, but cannot replace SPY_200d or activate real-money behavior.

