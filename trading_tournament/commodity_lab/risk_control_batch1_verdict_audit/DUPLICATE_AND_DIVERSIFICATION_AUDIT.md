# Duplicate And Diversification Audit

## Correlation Diagnostics

Correlation diagnostics are available from full-period standard equity-curve daily returns. Target-window co-movement is not available.

| Row | Corr vs base commodity | Corr vs combo | Corr vs top2 | Corr vs SPY_200d | Corr vs GLD | Corr vs BIL |
|---|---:|---:|---:|---:|---:|---:|
| `commodity_basket_tsmom_top2_200d_filter_v1` | 0.969 | 0.299 | 0.285 | 0.190 | 0.245 | 0.095 |
| `commodity_basket_tsmom_top2_half_bil_v1` | 0.986 | 0.307 | 0.280 | 0.211 | 0.240 | 0.250 |
| `combo_plus_commodity_basket_80_20_v1` | 0.559 | 0.962 | 0.709 | 0.566 | 0.816 | 0.050 |

## Audit

- Does commodity exposure add new target windows? `unavailable_missing_window_ids`.
- Does it mostly duplicate GLD/top2/commodity exposure? The 200d filter and half-BIL are highly correlated to the base commodity row. Combo+commodity is highly correlated to combo and GLD, and moderately/highly correlated to top2.
- Does combo+commodity mostly behave like combo? Yes, current evidence supports `mostly_combo_with_small_commodity_tilt`.
- Is product/sleeve concentration too high? Combo+commodity has 80% combo sleeve concentration, so any improvement may be mostly inherited combo behavior.
- Are drawdown co-incidence diagnostics available? Only equity-return correlation proxy is available; detailed drawdown overlap windows are not exported.
- Is diversification proven? No. Label: `diversification_not_proven`.

Best cautious labels:

- `commodity_basket_tsmom_top2_200d_filter_v1`: `duplicate_or_near_duplicate` to base behavior plus `filter_ineffective_or_bug_review`.
- `commodity_basket_tsmom_top2_half_bil_v1`: `risk_reducer_not_target_additive`.
- `combo_plus_commodity_basket_80_20_v1`: `mostly_combo_with_small_commodity_tilt` and `possible_incremental_target_value`.
