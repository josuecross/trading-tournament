# Implementation Review

Subject: `managed_futures_proxy_etf_trend_v1`

Review date: 2026-06-04

Decision: `data_acquisition_required`

This review considers whether managed-futures or CTA ETF/fund proxies could add a return driver different from the recent U.S.-equity-heavy candidates. The review uses local cache metadata only. It does not implement a strategy, run Profit Exploration, run a backtest, download data, use futures contracts, or change paper-forward rules.

## Candidate Concept

The candidate would eventually test a simple ETF/fund-proxy trend idea using daily fund prices, if suitable proxy data exists. It would not implement futures contracts, futures rolls, margin, leverage, or broker execution. A future rule would need to be fixed before implementation and would have to produce exact fresh-window rolling streams for Profit Exploration accounting checks.

## Why Review It Now

Recent candidates such as QQQ dual momentum, value/momentum factor rotation, and sector top2 momentum were materially exposed to U.S. equity beta or duplicate-risk concerns. Managed-futures proxy funds may provide a different crisis-diversifying return driver, but the available ETF/fund wrappers can have short histories and fund-specific methodology risk.

## Local Cache Finding

Reviewed proxy symbols: `DBMF`, `KMLM`, `CTA`, `FMF`, `WTMF`.

Cached locally: none of the reviewed managed-futures proxy symbols were found in `data/cache`.

Because no reviewed proxy is cached, no common overlap window can be calculated, no no-network research_sample implementation is possible now, and the correct next gate is data acquisition review rather than strategy implementation.

## Recommendation

Do not approve research_sample implementation yet. Create a future data acquisition review for the reviewed proxy symbols, including provider terms, inception coverage, adjustment fields, row counts, and metadata-only compact evidence. If enough proxy data later passes quality checks, update this review before any implementation prompt.

No real-money recommendation is made.

