# Implementation Review

Review subject: `sector_top2_momentum_simple_v1`

Boundary: review/gate packet only. No strategy was implemented, no runnable experiment was added, no backtest was run, no data was downloaded, no A strategy was modified, no paper-forward rule changed, and no real-money recommendation is made.

## What It Is

`sector_top2_momentum_simple_v1` is a proposed simple ETF sector momentum candidate. The concept is to rank sector ETFs by fixed momentum, hold the top two qualifying sectors, and move unqualified/unused weight to cash proxy. It is meant to test whether sector dispersion can improve stop-aware profit potential beyond broad SPY trend and existing finalist/challenger rows.

## Why It Is Being Considered

The current practical challenger is `combo_SPY200d_GLD_50_50_v1`, and `asset_class_tsmom_top2_v1` remains a serious challenger. A sector top-2 rule may add more concentrated equity dispersion than broad ETF trend without adding leverage, shorting, margin, options, futures, forex, intraday logic, or individual stocks.

## Local Data And Universe Findings

The nine classic sector ETFs are cached with long overlap from `2007-01-03 to 2026-05-29`: `XLB`, `XLE`, `XLF`, `XLI`, `XLK`, `XLP`, `XLU`, `XLV`, and `XLY`.

`XLC` is cached from `2018-06-19 to 2026-05-29`, but including it shortens the common overlap or requires an availability-aware universe rule. `XLRE` is not cached.

## A Strategy Relationship

The existing `A_ETF_sector_momentum` strategy should not be modified and should not be approximated from summary metrics. If this candidate is later implemented, it should be a separate clean minimal research_sample rule with independent fresh-window streams and diagnostics.

## Sector Universe Policy Decision

The universe policy is now fixed for the first future research_sample implementation prompt.

Policy chosen: `core_nine_fixed_universe`.

Options reviewed:

- Option A, core-nine fixed universe: use `XLB`, `XLE`, `XLF`, `XLI`, `XLK`, `XLP`, `XLU`, `XLV`, and `XLY`. This maximizes the local common overlap, avoids XLC late inception, avoids XLRE missing data, uses no network, and is the simplest first implementation. It omits communication services and real estate.
- Option B, availability-aware with XLC: include cached `XLC` from `2018-06-19` onward. This is closer to the modern sector set, but creates shorter common history or a changing universe and raises inception-bias risk.
- Option C, acquire XLRE and use modern sectors: closer to modern sector coverage, but requires new data acquisition and still faces inception/overlap issues.

The first future rule must exclude `XLC` and `XLRE`. XLC or XLRE can be added only after a new review.

## Fixed Future Rule Spec

Allowed future rule id: `sector_top2_momentum_simple_v1`

Universe:

- `XLB`
- `XLE`
- `XLF`
- `XLI`
- `XLK`
- `XLP`
- `XLU`
- `XLV`
- `XLY`
- `BIL` fallback

Rebalance: monthly.

Ranking: rank sector ETFs by 126-trading-day return.

Absolute filter:

- each selected sector must have 126-day return greater than 0,
- each selected sector must close above its 200-day SMA.

Selection:

- hold top 2 qualifying sectors equally,
- unused weight goes to BIL,
- if no sector qualifies, allocate 100% to BIL.

Constraints:

- no leverage,
- no shorting,
- no margin,
- no variants,
- no XLC,
- no XLRE,
- do not modify `A_ETF_sector_momentum`.

## Review Answers

1. Enough sector ETFs are cached for a clean core-nine no-network research_sample prompt.
2. XLC and XLRE are excluded from the first implementation rule.
3. The candidate may be mostly equity beta, so duplicate/correlation diagnostics are required.
4. The candidate should not reuse summary metrics from `A_ETF_sector_momentum`.
5. The future implementation must expose exact fresh-window streams and accounting checks.
6. Benchmarks and failure criteria are defined.

## Review Conclusion

Decision: `approve_research_sample_implementation_core_nine`.

The candidate deserves a future research_sample implementation prompt using the fixed core-nine universe only. This is not an implementation, not a backtest, not candidate_exhaustive, and not paper-forward activation.
