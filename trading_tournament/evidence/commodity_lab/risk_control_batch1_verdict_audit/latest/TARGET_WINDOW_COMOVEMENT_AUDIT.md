# Target-Window Co-Movement Audit

## Status

target_window_co_movement_status: `unavailable_missing_window_ids`

Aggregate target-hit counts are available from the rolling summary. Exact overlapping window IDs and benchmark target flags are not exported for Commodity Risk-Control Batch 1. Therefore the audit cannot calculate windows where base commodity, combo, top2, SPY_200d, or GLD also hit +300/+400, nor can it calculate independent target percentages versus combo/top2.

Do not infer target-window independence from labels, correlations, or aggregate target rates.

## Aggregate Target Counts

Counts below are derived from `number_of_windows` times reported target rates in the standard rolling summary.

| Row | Horizon | Windows | +300 count | +400 count | +600 count |
|---|---:|---:|---:|---:|---:|
| `commodity_basket_tsmom_top2_200d_filter_v1` | 30 | 40 | 9 | 2 | 1 |
| `commodity_basket_tsmom_top2_200d_filter_v1` | 60 | 39 | 11 | 8 | 5 |
| `commodity_basket_tsmom_top2_200d_filter_v1` | 90 | 39 | 17 | 10 | 8 |
| `commodity_basket_tsmom_top2_200d_filter_v1` | 180 | 39 | 22 | 21 | 12 |
| `commodity_basket_tsmom_top2_half_bil_v1` | 30 | 40 | 1 | 1 | 0 |
| `commodity_basket_tsmom_top2_half_bil_v1` | 60 | 39 | 6 | 0 | 0 |
| `commodity_basket_tsmom_top2_half_bil_v1` | 90 | 39 | 9 | 7 | 0 |
| `commodity_basket_tsmom_top2_half_bil_v1` | 180 | 39 | 13 | 10 | 8 |
| `combo_plus_commodity_basket_80_20_v1` | 30 | 40 | 0 | 0 | 0 |
| `combo_plus_commodity_basket_80_20_v1` | 60 | 39 | 3 | 0 | 0 |
| `combo_plus_commodity_basket_80_20_v1` | 90 | 39 | 12 | 2 | 0 |
| `combo_plus_commodity_basket_80_20_v1` | 180 | 39 | 25 | 18 | 8 |

## Required Future Fields

Future diagnostics must export:

- `experiment_id`
- `horizon`
- `window_start`
- `window_end`
- `target_300_hit`
- `target_400_hit`
- `target_600_hit`
- base commodity benchmark +300/+400 flags
- combo benchmark +300/+400 flags
- top2 benchmark +300/+400 flags
- SPY_200d benchmark +300/+400 flags
- GLD benchmark +300/+400 flags

Without those fields, candidate_exhaustive review should not be justified by claims of incremental target windows.
