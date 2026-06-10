# Benchmark And Failure Criteria

## Primary Benchmarks

- `combo_SPY200d_GLD_50_50_v1`
- `asset_class_tsmom_top2_v1`

## Secondary Benchmarks

- `SPY_200d_trend_model`
- `GLD_buy_hold`
- `BIL_cash_proxy`
- `qqq_spy_gld_ief_dual_momentum_v1`
- `value_momentum_factor_etf_rotation_v1`
- `sector_top2_momentum_simple_v1`

## Failure Criteria

Reject or defer future implementation if any of these remain true:

- insufficient proxy history
- no cached data and no approved acquisition path
- proxy does not behave differently from current finalists
- target rates are too low for +300/+400
- drawdown or stop risk is worse than combo/top2
- stress degradation is worse than combo/top2
- fund methodology is too opaque
- hidden leverage or derivatives exposure cannot be interpreted at wrapper level
- exact fresh-window rolling streams cannot be produced
- result depends on a single fund, single regime, or short-history artifact

No paper-forward activation or real-money recommendation is allowed from this review.

