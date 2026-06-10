# Benchmark And Failure Criteria

## Primary Benchmarks

- `combo_SPY200d_GLD_50_50_v1`
- `asset_class_tsmom_top2_v1`

## Secondary Benchmarks

- `SPY_200d_trend_model`
- `GLD_buy_hold`
- `BIL_cash_proxy`
- `SPY_buy_hold`
- `qqq_spy_gld_ief_dual_momentum_v1`
- `value_momentum_factor_etf_rotation_v1`
- `sector_top2_momentum_simple_v1`

## Failure Criteria

Reject, defer, or block any stronger gate if:

- methodology is too opaque,
- wrapper-level modeling is not acceptable,
- target rates are too low,
- drawdown/stop risk is worse than combo/top2,
- stress degradation is worse than combo/top2,
- inception window is too short for the claim being made,
- behavior does not diversify current finalists,
- results depend on one fund only,
- exact fresh-window streams cannot be produced,
- fund data fails later quality or identity checks,
- results are described as direct futures strategy evidence,
- paper-forward activation is implied without a separate promotion review.

## Success Criteria For Research Sample Only

A future research_sample prompt may proceed only if it uses a fixed simple rule, preserves exact fresh-window streams, applies standard/stress project costs, reports DBMF/KMLM/BIL allocation diagnostics, and labels the evidence as short-history fund-wrapper proxy evidence.
