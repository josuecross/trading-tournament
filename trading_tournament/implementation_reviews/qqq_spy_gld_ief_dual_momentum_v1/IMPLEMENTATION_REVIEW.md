# Implementation Review: qqq_spy_gld_ief_dual_momentum_v1

## Research Boundary

This is a queue/gate review only. No strategy is implemented here. No real-money recommendation is made.

## What It Is

`qqq_spy_gld_ief_dual_momentum_v1` is a queued ETF dual-momentum idea:

- universe: QQQ, SPY, GLD, IEF, BIL
- expected driver: relative momentum plus absolute trend
- intended use: future research_sample only
- no leverage, no shorting, no margin

## Why It Is Being Considered

The current practical challenger is a SPY trend / GLD fixed combo. QQQ may add growth/equity momentum exposure while retaining GLD/IEF/BIL defensive sleeves.

## Return Driver Added

QQQ adds large-cap growth and technology-heavy equity beta. The return driver may be useful if growth momentum improves upside without unacceptable stop or drawdown behavior.

## Material Difference From Top2

The candidate is not identical to `asset_class_tsmom_top2_v1` because QQQ is not in the current top2 universe. However, it may be a near-duplicate in behavior if QQQ simply replaces SPY as a higher-beta equity sleeve.

## Data And Engine Fit

QQQ is present in the local ETF cache. The current engine could likely test it without network if a later implementation prompt extends the existing asset-class momentum logic to include QQQ. This review does not do that implementation.

## Benchmark To Beat

Primary benchmark: `asset_class_tsmom_top2_v1`.

Secondary benchmarks: `combo_SPY200d_GLD_50_50_v1`, `SPY_200d_trend_model`, `SPY_buy_hold`, `GLD_buy_hold`, and `BIL_cash_proxy`.

## Immediate Rejection Conditions

Reject or defer if:

- QQQ data becomes unavailable under no-network mode
- QQQ history overlap is insufficient
- QQQ mostly creates a higher-beta duplicate of SPY/top2
- target-rate improvement comes with materially worse stop or drawdown behavior
- stress degradation is worse than top2/combo
- QQQ dominates allocations and violates diversification intent

## Decision

Implementation review decision: `approve_research_sample_implementation`.

This means a future prompt may implement the candidate as a research_sample experiment only. No implementation is created in this task.

