# Target-Window Co-Movement Completion

diagnostics_status: `available`

source_detail: `evidence/commodity_lab/risk_control_batch1_diagnostics_completion/latest/commodity_risk_control_diagnostics_detail.csv`

The diagnostics-only export produced 471 sampled fresh-window rows across the three Commodity Risk-Control Batch 1 candidates and 30/60/90/180 day horizons.

## Candidate Target And Increment Counts

Counts are sampled research_sample windows. Incremental means the candidate hit the target and the named benchmark did not hit that same target in the same window.

### commodity_basket_tsmom_top2_200d_filter_v1

| horizon | n | +300 | +400 | +600 | inc +300 vs base | inc +400 vs base | inc +300 vs combo | inc +400 vs combo | inc +300 vs top2 | inc +400 vs top2 | inc +300 vs SPY_200d | inc +400 vs SPY_200d | inc +300 vs GLD | inc +400 vs GLD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 30 | 40 | 9 | 2 | 1 | 0 | 0 | 9 | 2 | 9 | 2 | 8 | 2 | 7 | 2 |
| 60 | 39 | 11 | 8 | 5 | 1 | 0 | 11 | 8 | 11 | 8 | 11 | 8 | 9 | 7 |
| 90 | 39 | 17 | 10 | 8 | 1 | 0 | 15 | 10 | 14 | 10 | 9 | 9 | 7 | 4 |
| 180 | 39 | 22 | 21 | 12 | 0 | 0 | 7 | 11 | 9 | 11 | 4 | 15 | 7 | 8 |

Interpretation: the 200d filter did not create meaningful incremental target windows versus the base commodity rule. Its zero 180d increment versus base and unchanged drawdown breach support the prior filter-review label.

### commodity_basket_tsmom_top2_half_bil_v1

| horizon | n | +300 | +400 | +600 | inc +300 vs base | inc +400 vs base | inc +300 vs combo | inc +400 vs combo | inc +300 vs top2 | inc +400 vs top2 | inc +300 vs SPY_200d | inc +400 vs SPY_200d | inc +300 vs GLD | inc +400 vs GLD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 30 | 40 | 1 | 1 | 0 | 0 | 0 | 1 | 1 | 1 | 1 | 1 | 1 | 0 | 1 |
| 60 | 39 | 6 | 0 | 0 | 0 | 0 | 6 | 0 | 6 | 0 | 6 | 0 | 5 | 0 |
| 90 | 39 | 9 | 7 | 0 | 0 | 0 | 9 | 7 | 7 | 7 | 8 | 7 | 1 | 2 |
| 180 | 39 | 13 | 10 | 8 | 0 | 0 | 3 | 4 | 4 | 2 | 3 | 9 | 2 | 1 |

Interpretation: half-BIL reduces risk but does not add target windows versus the base commodity rule. It is a defensive row, not an additive candidate.

### combo_plus_commodity_basket_80_20_v1

| horizon | n | +300 | +400 | +600 | inc +300 vs base | inc +400 vs base | inc +300 vs combo | inc +400 vs combo | inc +300 vs top2 | inc +400 vs top2 | inc +300 vs SPY_200d | inc +400 vs SPY_200d | inc +300 vs GLD | inc +400 vs GLD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 30 | 40 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 60 | 39 | 3 | 0 | 0 | 3 | 0 | 0 | 0 | 1 | 0 | 2 | 0 | 0 | 0 |
| 90 | 39 | 12 | 2 | 0 | 9 | 2 | 2 | 0 | 4 | 0 | 7 | 2 | 3 | 0 |
| 180 | 39 | 25 | 18 | 8 | 7 | 6 | 3 | 3 | 5 | 4 | 10 | 12 | 3 | 2 |

For combo_plus_commodity_basket_80_20_v1:

- It created a small number of new target windows versus combo: 2 new 90d +300 windows, 0 new 90d +400 windows, 3 new 180d +300 windows, and 3 new 180d +400 windows.
- It created some windows versus top2: 4 new 90d +300, 0 new 90d +400, 5 new 180d +300, and 4 new 180d +400.
- It created limited windows versus GLD: 3 new 90d +300, 0 new 90d +400, 3 new 180d +300, and 2 new 180d +400.
- Most target hits still occur in windows where at least one existing leader also hits, especially at 90d +400.

Conclusion: target-window co-movement is now available. It supports `possible_incremental_target_value`, not a strong independent target-window claim.

