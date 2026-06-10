# Score And Ranking Audit

## Available Scores

| Row | Stop-aware rank | Profit-seeking rank | Drawdown-control rank | Balanced drawdown-aware score | Profit-seeking score | Drawdown-control score |
|---|---:|---:|---:|---:|---:|---:|
| `commodity_basket_tsmom_top2_200d_filter_v1` | 8 | 5 | 8 | -192.86 | 56.03 | -142.27 |
| `commodity_basket_tsmom_top2_half_bil_v1` | 7 | 9 | 7 | -149.87 | -134.98 | -20.23 |
| `combo_plus_commodity_basket_80_20_v1` | 5 | 8 | 6 | -103.01 | -93.55 | -2.62 |

## Score Deltas Versus Benchmarks

| Row | vs base commodity | vs combo | vs top2 | vs SPY_200d | vs GLD | vs BIL |
|---|---:|---:|---:|---:|---:|---:|
| `commodity_basket_tsmom_top2_200d_filter_v1` | +3.88 | -84.87 | -300.45 | -318.91 | -246.47 | -187.77 |
| `commodity_basket_tsmom_top2_half_bil_v1` | +46.87 | -41.89 | -257.47 | -275.92 | -203.48 | -144.79 |
| `combo_plus_commodity_basket_80_20_v1` | +93.73 | +4.98 | -210.61 | -229.06 | -156.62 | -97.92 |

## Audit

`combo_plus_commodity_basket_80_20_v1` is the best risk-control row by the reported stop-aware practical rank and improves meaningfully versus the base commodity row. The improvement versus the active historical combo is only +4.98, which is too small to treat as robust without target-window co-movement and component contribution diagnostics.

The score ranking does not conflict with the risk interpretation: the 200d filter remains high-upside/high-risk, half-BIL is defensive but diluted, and combo+commodity is the best compromise. The candidate_exhaustive decision is conservative but justified because the best row is highly correlated with combo and has no exported target-window independence evidence.

Current audit conclusion: score evidence supports `candidate_diagnostics_review_required` for `combo_plus_commodity_basket_80_20_v1`, not candidate_exhaustive.
