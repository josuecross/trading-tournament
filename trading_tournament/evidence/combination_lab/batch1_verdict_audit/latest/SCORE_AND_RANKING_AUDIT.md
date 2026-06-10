# Score And Ranking Audit

Audit decision: `ranking_valid_verdict_mapping_too_coarse`

The stop-aware ranking correctly identified `combo_plus_managed_futures_80_20_v1` as the best Batch 1 row by practical score, but the final verdict mapping compressed materially different outcomes into the same `too_slow` label.

## Available scoring fields

| combination | stop-aware practical rank | profit-seeking rank | drawdown-control rank | stop-aware score | profit score | drawdown-control score | prior verdict |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `combo_plus_managed_futures_80_20_v1` | 1 | 2 | 2 | 218.54 | 246.80 | 273.85 | `too_slow` |
| `top2_plus_managed_futures_80_20_v1` | 2 | 4 | 3 | 203.70 | 229.59 | 271.05 | `too_slow` |
| `combo_plus_top2_50_50_v1` | 3 | 6 | 5 | 100.47 | 166.02 | 224.98 | `too_slow` |

## Stop-aware score

The stop-aware practical score ranked the managed-futures blend first because it combined 0.0% 90d/180d stop-hit rates with materially lower drawdowns than the leaders. That part is logically consistent.

## Profit-seeking score

The profit-seeking score did not make the managed-futures blend the top overall row, but it did not support a blanket rejection either. The 180d +300/+400/+600 profile is meaningful enough for watchlist status.

## Drawdown-control score

The drawdown-control score supports the managed-futures blends. They used less of the -$600 risk budget than the combo/top2 blend and had lower worst drawdowns.

## Verdict mapping issue

The audit finds the verdict mapping under-expressed horizon-specific behavior:

- 30/60-day target rates were appropriately penalized.
- 180-day target rates and drawdown control were not reflected in the label.
- managed-futures short-history risk was present, but the label should preserve watchlist value rather than imply the result is simply too slow.
- stress degradation was higher for `combo_plus_managed_futures_80_20_v1` than for `combo_plus_top2_50_50_v1`, so immediate candidate_exhaustive is not justified.

Corrected labels:

- `combo_plus_top2_50_50_v1`: `duplicate_or_near_duplicate`
- `combo_plus_managed_futures_80_20_v1`: `short_history_watchlist`
- `top2_plus_managed_futures_80_20_v1`: `short_history_watchlist`

