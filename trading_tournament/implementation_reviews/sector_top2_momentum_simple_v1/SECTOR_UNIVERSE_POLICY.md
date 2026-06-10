# Sector Universe Policy

Review subject: `sector_top2_momentum_simple_v1`

This is a universe policy/gate decision only. No strategy is implemented, no runnable experiment is added, no backtest is run, no data is downloaded, no `A_ETF_sector_momentum` rule is modified, no paper-forward rule is changed, and no real-money recommendation is made.

## Policy Options Reviewed

### Option A: Core-Nine Fixed Universe

Universe:

- XLB
- XLE
- XLF
- XLI
- XLK
- XLP
- XLU
- XLV
- XLY

Pros:

- Longest common overlap: `2007-01-03 to 2026-05-29`.
- Avoids XLC late inception.
- Avoids XLRE missing data.
- No network needed.
- Simplest first implementation.

Cons:

- Omits communication services and real estate.
- Not the modern sector universe.

### Option B: Include XLC Availability-Aware

Universe: core nine plus XLC from `2018-06-19` onward.

Pros:

- Uses cached XLC.
- Closer to modern sector set.

Cons:

- Shorter common window or changing universe.
- Inception bias risk.
- More complicated implementation and evidence interpretation.

### Option C: Acquire XLRE And Use Modern Sectors

Pros:

- Closer modern sector coverage.

Cons:

- Requires new data acquisition.
- Still faces inception and overlap issues.
- Unnecessary before the first clean test.

## Chosen Policy

Decision: `core_nine_fixed_universe`

The first future research_sample implementation prompt may use only the core-nine fixed universe. `XLC` and `XLRE` are excluded from the first rule. XLC/XLRE can be revisited only through a new review.

## Fixed Future Rule Spec

Allowed future rule id: `sector_top2_momentum_simple_v1`

Universe:

- XLB
- XLE
- XLF
- XLI
- XLK
- XLP
- XLU
- XLV
- XLY
- BIL fallback

Rebalance:

- Monthly.

Ranking:

- Rank sector ETFs by 126-trading-day return.

Absolute filter:

- Each selected sector must have 126-day return greater than 0.
- Each selected sector must close above its 200-day SMA.

Selection:

- Hold top 2 qualifying sectors equally.
- Unused weight goes to BIL.
- If no sector qualifies, allocate 100% to BIL.

Constraints:

- No leverage.
- No shorting.
- No margin.
- No variants.
- No XLC.
- No XLRE.
- Do not modify `A_ETF_sector_momentum`.

## Implementation Approval Boundary

The implementation decision is updated to `approve_research_sample_implementation_core_nine`. This means a future research_sample implementation prompt may be created. It does not implement the strategy now, run a backtest now, run candidate_exhaustive now, activate paper-forward observation, change paper-forward rules, or make a real-money recommendation.

