# Data Availability Review

This review used local cache metadata only. No data was downloaded and no network/API provider was called.

## Cached Symbols

No reviewed managed-futures proxy symbols are currently cached.

## Missing Symbols

- `DBMF`
- `KMLM`
- `CTA`
- `FMF`
- `WTMF`

## Common Overlap

Common overlap window: not calculable because none of the reviewed proxy symbols are cached locally.

## History And No-Network Feasibility

A no-network research_sample implementation is not possible now. The candidate remains data-gated because the project cannot evaluate proxy history, warmup coverage, 30/60/90/180 rolling windows, or stress behavior without a cached and quality-reviewed proxy series.

Short ETF/fund inception history could create misleading results even if data is acquired later. The review should not assume that a short post-inception sample captures enough crisis regimes to represent managed futures as a research family.

## Next Gate

Create a future data acquisition review. That review should decide provider path, terms/security handling, allowed symbols, cache metadata, adjustment availability, and quality requirements. It should still not implement a strategy or run a backtest.

