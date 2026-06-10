# Duplicate And Correlation Risk Review

Managed-futures proxy exposure could add a different return driver from the current equity-heavy research candidates, but this remains unverified until data exists.

## Comparators

- `combo_SPY200d_GLD_50_50_v1`
- `asset_class_tsmom_top2_v1`
- `SPY_200d_trend_model`
- `GLD_buy_hold`
- `BIL_cash_proxy`
- `qqq_spy_gld_ief_dual_momentum_v1`
- `value_momentum_factor_etf_rotation_v1`
- `sector_top2_momentum_simple_v1`

## Review Answers

1. Different return driver: potentially yes, because managed-futures proxy funds may follow cross-asset trends rather than U.S. equity factor/sector leadership. This is not established without proxy data.
2. Drawdown reduction: possible if the proxy has crisis-diversifying behavior, but fund-specific losses and short history could undermine that.
3. Too slow for +300/+400: possible. Managed-futures proxy funds may diversify drawdown but fail the project's target ladder if returns are too modest.
4. Hidden product risk: material. Internal futures, leverage targets, collateral, fees, and roll behavior can affect results even if the project only sees ETF/fund prices.
5. Future correlation metrics: rolling correlation versus combo, top2, SPY_200d, GLD, BIL, QQQ dual momentum, value/momentum factor rotation, and sector top2; stress-period correlation; target-window co-movement; drawdown co-incidence.
6. Expected failure behavior: too-short history, too-low target rates, weak stress survival, or behavior that fails to diversify the current finalists.

Future implementation must report whether the proxy is genuinely diversifying or merely slow, fund-specific, or another risk-on exposure.

