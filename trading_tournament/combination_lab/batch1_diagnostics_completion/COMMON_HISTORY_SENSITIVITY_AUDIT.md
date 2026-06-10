# Common-History Sensitivity Audit

Audit status: `available`

Managed-futures common-history window in diagnostics detail:

- common_history_start: 2020-12-02
- common_history_end: 2026-05-29

The diagnostics compare managed-futures blends against combo/top2 over the same sampled 180-day windows.

## Full-History Aggregate Reference

From existing Batch 1 evidence:

- Full-history combo 180d +300/+400: 50.0% / 42.5%.
- Full-history top2 180d +300/+400: 55.0% / 42.5%.
- `combo_plus_managed_futures_80_20_v1` 180d +300/+400: 64.1% / 53.8%.
- `top2_plus_managed_futures_80_20_v1` 180d +300/+400: 69.2% / 56.4%.

## Same-Window Restricted Comparison

Over the same 2020+ managed-futures diagnostic windows:

| row | 180d +300 | 180d +400 | 180d worst drawdown |
| --- | ---: | ---: | ---: |
| same-window combo benchmark in `combo_plus_managed_futures_80_20_v1` rows | 76.9% | 64.1% | -$487.25 |
| same-window top2 benchmark in `combo_plus_managed_futures_80_20_v1` rows | 79.5% | 71.8% | -$586.67 |
| `combo_plus_managed_futures_80_20_v1` | 64.1% | 53.8% | -$372.25 |
| `top2_plus_managed_futures_80_20_v1` | 69.2% | 56.4% | -$402.75 |

## Bias Finding

The 2020+ common-history sample was favorable for combo/top2 target hits. The managed-futures blends did not beat same-window combo/top2 target rates; they mainly reduced drawdown magnitude.

Question: Are managed-futures blends strong because of the 80/20 structure, or because the available 2020+ sample was favorable?

Answer: the target profile appears materially influenced by favorable common-history sampling. The drawdown improvement may be real in this short window, but target-rate strength should not be extrapolated.

short_history_bias_warning: `true`

