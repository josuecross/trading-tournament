# Drawdown And Risk-Budget Audit

## Risk-Budget Result

| Row | 90d stop | 90d worst DD | 90d budget usage | 180d stop | 180d worst DD | 180d budget usage | Audit |
|---|---:|---:|---:|---:|---:|---:|---|
| `commodity_basket_tsmom_top2_200d_filter_v1` | 2.6% | -$680.67 | 113.4% | 7.7% | -$718.24 | 119.7% | Still over budget. |
| `commodity_basket_tsmom_top2_half_bil_v1` | 0.0% | -$307.74 | 51.3% | 0.0% | -$319.65 | 53.3% | Under budget, but target diluted. |
| `combo_plus_commodity_basket_80_20_v1` | 0.0% | -$275.02 | 45.8% | 0.0% | -$316.93 | 52.8% | Under budget, best compromise. |

## Answers

- Candidates over the -$600 budget: `commodity_basket_tsmom_top2_200d_filter_v1`.
- Candidates below 100% risk-budget usage: `commodity_basket_tsmom_top2_half_bil_v1`, `combo_plus_commodity_basket_80_20_v1`.
- Candidates below 60% risk-budget usage at 90d/180d: `commodity_basket_tsmom_top2_half_bil_v1`, `combo_plus_commodity_basket_80_20_v1`.
- Stop-hit rates versus combo/top2: half-BIL and combo+commodity are acceptable at 0.0% in 90d/180d windows; the 200d filter is not acceptable because it retains 2.6%/7.7% stops.
- Drawdown improvement is material for half-BIL and combo+commodity.
- Half-BIL's drawdown improvement came with substantial target dilution.
- Combo+commodity has the best target/drawdown balance among the three risk-control rows, but it does not beat top2, SPY_200d, or GLD on reported stop-aware score, and only barely improves versus combo.

Audit result: risk-budget evidence supports diagnostics review for combo+commodity, not immediate candidate_exhaustive review.
