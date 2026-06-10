# Implementation Decision

Decision: `approve_research_sample_implementation`

## Rationale

The controlled data acquisition run acquired MTUM, VLUE, VTV, QUAL, USMV, and SPLV, and all six symbols passed quality checks. SPY and BIL were already cached and were not refreshed. The common overlap across acquired factor proxies plus SPY/BIL is `2013-07-18 to 2026-05-29`.

The candidate now has enough local data coverage to allow a future research_sample implementation prompt. The approval is limited because proxy and inception risks remain material: the common overlap starts in 2013, the factor ETFs may mostly express U.S. equity beta, and no project performance evidence exists for this candidate.

## Approved Future Rule

The future prompt may implement one fixed rule only:

- Universe: MTUM, VTV, QUAL, USMV, SPY, BIL.
- Monthly rebalance.
- Rank MTUM, VTV, QUAL, USMV, and SPY by 126-trading-day return.
- A selected asset must have 126-day return > 0 and close above its 200-day SMA.
- Hold the top 2 qualifying assets equal-weight.
- Unused weight goes to BIL.
- No leverage, no shorting, no margin.

VLUE and SPLV are not included in the first fixed rule. They remain reviewed substitutes or future diagnostics, not variants approved here.

## Future Research_Sample Implementation Approval

Future research_sample implementation is approved only through a separate implementation prompt. That prompt must:

- use cached data only,
- avoid data refreshes,
- avoid parameter grids and variants,
- report allocation concentration and equity-beta duplicate diagnostics,
- compare against combo_SPY200d_GLD_50_50_v1 and asset_class_tsmom_top2_v1 as primary benchmarks,
- preserve research-only language,
- keep paper_forward_active false,
- avoid broker integration, live orders, and real-money recommendation language.

This decision does not implement the strategy, run profit exploration, run candidate_exhaustive, or activate paper-forward observation. No real-money recommendation is made.
