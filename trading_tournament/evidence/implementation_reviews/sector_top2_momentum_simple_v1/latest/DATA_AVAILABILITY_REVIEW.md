# Data Availability Review

No network call or data download was performed. This review uses local cache metadata only.

## Cached Symbols

Cached core sector symbols: `XLB`, `XLE`, `XLF`, `XLI`, `XLK`, `XLP`, `XLU`, `XLV`, `XLY`.

Cached late-inception sector symbol: `XLC`.

Missing optional sector symbol: `XLRE`. XLRE is missing from local cache and is not downloaded in this review.

## Common Overlap Window

Core nine-sector overlap: `2007-01-03 to 2026-05-29`.

Configured sector universe including XLC overlap: `2018-06-19 to 2026-05-29`.

XLRE cannot be included from local cache because it is missing.

## Review Questions

1. Which sector ETFs are already cached?
   `XLB`, `XLE`, `XLF`, `XLI`, `XLK`, `XLP`, `XLU`, `XLV`, `XLY`, and `XLC`.

2. Which sector ETFs are missing?
   `XLRE` is missing from local cache.

3. What is the common overlap window?
   `2007-01-03 to 2026-05-29` for the core nine-sector set; `2018-06-19 to 2026-05-29` if XLC must be present from inception.

4. Are late-inception sectors such as XLRE or XLC available?
   XLC is cached but late-inception relative to the core nine. XLRE is not cached.

5. Should late-inception sectors be excluded or handled with availability-aware universe rules?
   A future implementation prompt must decide this explicitly. Excluding XLC/XLRE maximizes overlap and avoids inception bias. Including XLC requires an availability-aware policy that is fixed before results are seen.

6. Is a no-network implementation possible?
   Yes for a core-nine sector top-2 rule with BIL fallback, assuming BIL remains locally cached. A no-network implementation using XLC is also possible but would have a shorter common history or an availability-aware universe rule.

7. Does available data support 30/60/90/180 rolling windows?
   Yes for cached core sectors. The data has enough rows for 126-day momentum, 200-day trend warmup, and 30/60/90/180 rolling windows after warmup.

8. Does sector coverage create survivorship or ETF-inception bias?
   Yes, potentially. The core nine-sector set avoids the late-inception XLC/XLRE problem but omits newer sectors. Including late-inception sectors can bias early windows or shrink the study window.

## Data Gate Status

Data gate status: `conditional`.

Reason: enough cached sector ETF history exists for a clean core-nine implementation, but late-inception and missing-sector handling must be fixed before code.
