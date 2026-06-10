# Implementation Decision

Decision: `approve_research_sample_implementation_core_nine`

## Rationale

The local cache contains enough long-history sector ETF data for a clean research_sample implementation using the core nine sector ETFs: `XLB`, `XLE`, `XLF`, `XLI`, `XLK`, `XLP`, `XLU`, `XLV`, and `XLY`. This supports a no-network future implementation prompt.

The universe policy decision chooses `core_nine_fixed_universe`. `XLC` is excluded from the first rule because it starts only on `2018-06-19`. `XLRE` is excluded from the first rule because it is not cached and would require acquisition review.

## What This Allows

This decision allows a future research_sample implementation prompt for the fixed core-nine rule only.

The future prompt must:

- implement one clean minimal rule only,
- use only `XLB`, `XLE`, `XLF`, `XLI`, `XLK`, `XLP`, `XLU`, `XLV`, `XLY`, and BIL fallback,
- exclude XLC,
- exclude XLRE,
- avoid modifying `A_ETF_sector_momentum`,
- use cached data only,
- avoid data downloads,
- report sector concentration and equity-beta duplicate diagnostics,
- expose exact fresh-window streams,
- preserve research-only language,
- keep `paper_forward_active` false,
- avoid broker integration, live orders, and real-money recommendation language.

## What This Does Not Allow

This decision does not implement the strategy, run profit exploration, run candidate_exhaustive, run a backtest, activate paper-forward observation, change paper-forward rules, or make a real-money recommendation.
