# Data Availability Review

This review uses local cached-data metadata and the completed acquisition quality packet. No data was downloaded in this review update.

## Cached Symbols After Controlled Acquisition

- MTUM: cached, 3303 rows, 2013-04-18 to 2026-06-04, quality status pass.
- VLUE: cached, 3303 rows, 2013-04-18 to 2026-06-04, quality status pass.
- VTV: cached, 4886 rows, 2007-01-03 to 2026-06-04, quality status pass.
- QUAL: cached, 3240 rows, 2013-07-18 to 2026-06-04, quality status pass.
- USMV: cached, 3676 rows, 2011-10-20 to 2026-06-04, quality status pass.
- SPLV: cached, 3793 rows, 2011-05-05 to 2026-06-04, quality status pass.
- SPY: already cached, 4882 rows, 2007-01-03 to 2026-05-29; not refreshed.
- BIL: already cached, 4781 rows, 2007-05-30 to 2026-05-29; not refreshed.

## Quality Check Result

The acquisition packet reports all six acquired factor ETF symbols as `pass`:

- duplicate dates: 0 for every acquired symbol,
- missing adjusted close: 0,
- missing close: 0,
- missing volume: 0,
- adjusted close available: true,
- raw close available: true,
- dividends and splits fields available,
- enough rows for 200-day SMA, 126-day momentum, and 180-day rolling after warmup.

## Common Overlap

Common overlap across MTUM, VLUE, VTV, QUAL, USMV, SPLV, SPY, and BIL is:

`2013-07-18 to 2026-05-29`

The overlap is acceptable for a future research_sample implementation prompt. It remains a limitation because it is much shorter than SPY/BIL history and does not include the 2008 crisis.

## No Raw OHLCV In Evidence

Raw OHLCV stays in the local data cache. Compact evidence and advisor packets contain only metadata, coverage summaries, quality summaries, and manifests.

## Implementation Readiness

Data gate status: `pass`.

Future implementation can use these symbols only after the implementation decision allows a separate fixed-rule research_sample prompt. This review does not implement the strategy, run profit exploration, run a backtest, or approve paper-forward observation.
