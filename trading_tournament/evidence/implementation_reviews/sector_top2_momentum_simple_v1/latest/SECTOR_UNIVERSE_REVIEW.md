# Sector Universe Review

Source used: local project configuration and local cache metadata only. No data was downloaded.

Project config references the existing sector-style universe used around `A_ETF_sector_momentum`: `XLK`, `XLF`, `XLE`, `XLV`, `XLY`, `XLP`, `XLU`, `XLI`, `XLB`, and `XLC`. `XLRE` is a common sector ETF but is not present in the local cache and is not part of the currently observed config universe.

| symbol | cached_locally | first_cached_date | last_cached_date | row_count | enough_history_for_rolling_windows | notes |
|---|---:|---|---|---:|---:|---|
| XLB | true | 2007-01-03 | 2026-05-29 | 4882 | true | Core long-history sector ETF in local cache. |
| XLE | true | 2007-01-03 | 2026-05-29 | 4882 | true | Core long-history sector ETF in local cache. |
| XLF | true | 2007-01-03 | 2026-05-29 | 4882 | true | Core long-history sector ETF in local cache. |
| XLI | true | 2007-01-03 | 2026-05-29 | 4882 | true | Core long-history sector ETF in local cache. |
| XLK | true | 2007-01-03 | 2026-05-29 | 4882 | true | Core long-history sector ETF in local cache. |
| XLP | true | 2007-01-03 | 2026-05-29 | 4882 | true | Core long-history sector ETF in local cache. |
| XLU | true | 2007-01-03 | 2026-05-29 | 4882 | true | Core long-history sector ETF in local cache. |
| XLV | true | 2007-01-03 | 2026-05-29 | 4882 | true | Core long-history sector ETF in local cache. |
| XLY | true | 2007-01-03 | 2026-05-29 | 4882 | true | Core long-history sector ETF in local cache. |
| XLC | true | 2018-06-19 | 2026-05-29 | 1997 | true | Cached and configured, but late inception materially shortens common overlap if included from inception. |
| XLRE | false |  |  | 0 | false | Not cached. Do not download in this review. Would require separate data gate if included later. |

## Universe Finding

The nine classic sector ETFs (`XLB`, `XLE`, `XLF`, `XLI`, `XLK`, `XLP`, `XLU`, `XLV`, `XLY`) have a clean common local cache window from `2007-01-03` to `2026-05-29`. Including `XLC` reduces the common overlap to `2018-06-19` to `2026-05-29`. Including `XLRE` is not possible without a future acquisition review because it is not cached.

The future implementation prompt should choose a fixed universe policy before code is written. The lowest-bias first prompt is likely a core-nine sector universe plus BIL fallback, or an explicit availability-aware rule that handles XLC without changing the historical universe silently. That universe policy is the remaining blocker.

