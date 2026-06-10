# Target-Window Comovement Audit

Audit status: `available`

Source detail:

`evidence/combination_lab/batch1_diagnostics_completion/latest/combination_diagnostics_detail.csv`

The diagnostics-only export produced 478 same-calendar window rows across the three Batch 1 combinations and 30/60/90/180-day horizons.

## 180-Day Target-Window Summary

| combination | windows | +300 hits | +400 hits | +600 hits | combo +300 also hit in target windows | top2 +300 also hit in target windows | incremental +300 vs combo | incremental +300 vs top2 | incremental +400 vs combo | incremental +400 vs top2 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `combo_plus_top2_50_50_v1` | 40 | 20 | 13 | 9 | 19 | 20 | 1 | 0 | 0 | 1 |
| `combo_plus_managed_futures_80_20_v1` | 39 | 25 | 21 | 16 | 25 | 25 | 0 | 0 | 0 | 0 |
| `top2_plus_managed_futures_80_20_v1` | 39 | 27 | 22 | 13 | 27 | 27 | 0 | 0 | 0 | 0 |

## Primary Finding

The managed-futures combinations did not create independent 180-day +300/+400 target windows versus combo or top2. Their 180-day target hits occurred in windows where the primary benchmarks also hit.

For `combo_plus_managed_futures_80_20_v1`:

- target_300_window_count: 25
- target_400_window_count: 21
- target_600_window_count: 16
- incremental +300 windows versus combo: 0
- incremental +300 windows versus top2: 0
- incremental +400 windows versus combo: 0
- incremental +400 windows versus top2: 0
- independent +300 percentage versus combo/top2: 0.0% / 0.0%
- independent +400 percentage versus combo/top2: 0.0% / 0.0%

For `top2_plus_managed_futures_80_20_v1`:

- target_300_window_count: 27
- target_400_window_count: 22
- target_600_window_count: 13
- incremental +300 windows versus combo: 0
- incremental +300 windows versus top2: 0
- incremental +400 windows versus combo: 0
- incremental +400 windows versus top2: 0
- independent +300 percentage versus combo/top2: 0.0% / 0.0%
- independent +400 percentage versus combo/top2: 0.0% / 0.0%

## Interpretation

The prior 180-day target profile looked strong in aggregate, but target-window co-movement shows that the managed-futures blends did not add independent target-hit windows over the current primary benchmarks.

This supports `short_history_watchlist` rather than candidate_exhaustive review.

