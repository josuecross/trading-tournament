# Inception And Common Overlap Review

## Commodity Product Overlap

Common overlap among DBC, PDBC, COMT, GSG, and USCI is unavailable from local cache because none of the symbols is cached. No inception dates are invented in this review.

## Existing Benchmark Cache Context

Local benchmark cache dates available from `data/cache/`:

| benchmark | first_cached_date | last_cached_date | row_count |
|---|---|---|---:|
| SPY_200d_trend_model / SPY | 2007-01-03 | 2026-06-05 | 4887 |
| GLD_buy_hold / GLD | 2007-01-03 | 2026-06-05 | 4887 |
| BIL_cash_proxy / BIL | 2007-05-30 | 2026-06-05 | 4786 |
| managed_futures_proxy_etf_trend_v1 / DBMF | 2019-05-08 | 2026-06-05 | 1780 |
| managed_futures_proxy_etf_trend_v1 / KMLM | 2020-12-02 | 2026-06-05 | 1383 |

## Required Benchmark Comparison Set

Future commodity research must compare against:

- combo_SPY200d_GLD_50_50_v1,
- asset_class_tsmom_top2_v1,
- SPY_200d_trend_model,
- GLD_buy_hold,
- BIL_cash_proxy,
- managed_futures_proxy_etf_trend_v1 if relevant.

## Bias Risk

Late-inception commodity products can make comparisons look stronger or weaker than full-history benchmarks. Any future result must disclose the common start/end date, common overlap row count, warmup loss, and whether the sample is shorter than SPY/GLD/BIL history.

## Reduced Universe

If only a subset of commodity products has acceptable history and product structure, a reduced universe may be reviewed first. A reduced universe must be predeclared before research_sample, and missing products must remain visible rather than quietly dropped.

## Short-History Label

Short-history labels are required if the common overlap after warmup is materially shorter than the benchmark history or if the product was launched too late for robust 30/60/90/180-day windows.
