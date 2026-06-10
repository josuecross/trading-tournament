# Component Contribution Audit

Audit status: `partially_available`

Available fields:

- component contribution to final equity by window
- component contribution in +300 windows
- component contribution in +400 windows
- whether one sleeve dominates gains
- whether managed-futures sleeve diluted short-horizon target rates

Unavailable fields:

- exact component contribution to worst drawdown path
- exact component contribution to recovery windows

Those unavailable fields require daily component contribution time-series exports, not only window-level contribution totals.

## 180-Day Average Contribution

| combination | primary component | secondary component | primary avg contribution | secondary avg contribution | interpretation |
| --- | --- | --- | ---: | ---: | --- |
| `combo_plus_top2_50_50_v1` | combo | top2 | $134.70 | $107.83 | balanced but duplicative |
| `combo_plus_managed_futures_80_20_v1` | combo | managed futures | $345.42 | $43.60 | combo sleeve dominates gains |
| `top2_plus_managed_futures_80_20_v1` | top2 | managed futures | $293.50 | $42.28 | top2 sleeve dominates gains |

## Contribution In Target Windows

`combo_plus_managed_futures_80_20_v1`:

- +300 windows: combo sleeve avg contribution $513.15; managed-futures sleeve avg contribution $52.34.
- +400 windows: combo sleeve avg contribution $548.56; managed-futures sleeve avg contribution $60.87.

`top2_plus_managed_futures_80_20_v1`:

- +300 windows: top2 sleeve avg contribution $430.60; managed-futures sleeve avg contribution $48.91.
- +400 windows: top2 sleeve avg contribution $454.05; managed-futures sleeve avg contribution $57.80.

## Interpretation

The managed-futures sleeve was not the dominant profit contributor. It appears to reduce drawdown magnitude and volatility exposure more than it creates independent target-hit contribution.

The results still depend mostly on the combo/top2 sleeve. This supports watchlist-only status, not candidate_exhaustive review.

