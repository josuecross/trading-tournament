# Diagnostics Completion Decision

Decision: `diagnostics_support_short_history_watchlist_only`

This task does not run candidate_exhaustive.

## Rationale

The missing diagnostics were completed enough to decide that Batch 1 managed-futures combinations should remain watchlist-only:

- Target-window co-movement is available.
- Component final-equity contribution is available.
- Common-history sensitivity is available.
- Drawdown overlap detail is available.
- Managed-futures rows remain short-history fund-wrapper proxy evidence.

The main finding is skeptical:

- `combo_plus_managed_futures_80_20_v1` had a strong 180-day aggregate profile, but its 180-day +300/+400 hits were not independent of combo/top2 target windows.
- `top2_plus_managed_futures_80_20_v1` had a strong 180-day aggregate profile, but its 180-day +300/+400 hits were not independent of combo/top2 target windows.
- Same-window combo/top2 benchmarks had higher 180-day +300/+400 rates in the managed-futures common-history sample.
- Managed-futures sleeves contributed modestly to profits and mostly improved drawdown magnitude.

## Candidate Exhaustive Review

No candidate_exhaustive review is recommended now.

Future review could be reopened only if a later prompt requests a specific short-history-labeled review and adds:

- target-window co-movement thresholds
- daily component contribution to drawdown/recovery
- worst-5 drawdown window overlap
- explicit short-history acceptance criteria
- exact future horizons and runtime scope

Required label remains:

`fund_wrapper_proxy_short_history_limited_inception_research_sample_only`

