# Implementation Review

Subject: `value_momentum_factor_etf_rotation_v1`

Review date: 2026-06-04

Boundary: research-only paper/demo review. No strategy was implemented, no backtest was run, no data was downloaded in this review update, no paper-forward row was changed, and no real-money recommendation is made.

## Candidate Concept

`value_momentum_factor_etf_rotation_v1` is a proposed ETF factor-rotation candidate. The intended family is `factor_rotation`, and the intended return driver is value plus momentum factor premia, with quality and low-volatility defensive context.

Reviewed proxies:

- Momentum: MTUM
- Value: VLUE and VTV
- Quality: QUAL
- Low-volatility / defensive equity: USMV and SPLV
- Broad market benchmark/risk-on baseline: SPY
- Cash / Treasury fallback: BIL

## Post-Acquisition Gate Result

The controlled yfinance-compatible acquisition run `20260604_213319` acquired MTUM, VLUE, VTV, QUAL, USMV, and SPLV. All six symbols passed the metadata and data-quality checks. SPY and BIL were already cached and were not refreshed.

Common overlap across MTUM, VLUE, VTV, QUAL, USMV, SPLV, SPY, and BIL is `2013-07-18 to 2026-05-29`. This is long enough to permit a future research_sample implementation, but it is not long enough to support strong final claims without further validation.

## Review Answers

1. What is the candidate? A future fixed-rule ETF factor-rotation strategy using momentum, value, quality, low-volatility, broad market, and cash/Treasury proxies.
2. Why consider it? It has a plausible factor-prior and tests whether factor ETF rotation improves stop-aware profit/risk versus the current drawdown-aware finalists.
3. What return driver does it add? U.S. equity factor rotation, especially momentum, value, quality, and low-volatility tilts.
4. Does it have enough local proxy support? Yes for research_sample implementation review. MTUM, VLUE, VTV, QUAL, USMV, SPLV, SPY, and BIL are now cached.
5. Can the current engine test it without downloads? A future implementation prompt can be written for the existing daily ETF framework using cached data only.
6. What benchmark should it beat? Primary benchmarks: combo_SPY200d_GLD_50_50_v1 and asset_class_tsmom_top2_v1.
7. What causes immediate failure later? Failure to beat combo/top2 on stop-aware profit/risk, worse drawdown-budget use, high stress degradation, high stop-hit rate, equity-beta duplication, or one ETF dominating allocations.
8. Should it be implemented now? No. This review allows a future implementation prompt only. It does not create strategy code.

## Recommended Future Fixed Rule

Recommended rule: Option A.

- Universe: MTUM, VTV, QUAL, USMV, SPY, BIL.
- Rebalance: monthly.
- Ranking assets: MTUM, VTV, QUAL, USMV, SPY.
- Ranking metric: 126-trading-day return.
- Absolute trend filter: selected assets must have 126-day return > 0 and price > 200-day SMA.
- Selection: hold the top 2 qualifying assets equal-weight.
- Fallback: unused weight goes to BIL.
- Constraints: no leverage, no shorting, no margin.

Why Option A: VTV is preferred over VLUE for the first implementation because it has a longer local history and reduces inception-date sensitivity. USMV is preferred as the primary low-volatility proxy because it is a broad minimum-volatility ETF with sufficient local history; SPLV remains a useful substitute or future diagnostic but is not needed in the first fixed rule. QUAL is included despite the shorter history because quality is central to the candidate thesis and already defines the common overlap window.

This recommended rule is fixed before any project performance result. It is not a parameter search and does not permit variants in the implementation prompt.

No real-money recommendation is made.
