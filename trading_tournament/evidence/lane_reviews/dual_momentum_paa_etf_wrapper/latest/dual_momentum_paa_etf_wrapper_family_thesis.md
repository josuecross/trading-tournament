# Dual Momentum PAA ETF Wrapper Family Thesis

Family id: `dual_momentum_paa_etf_wrapper`

Thesis: use simple ETF-wrapper rules combining relative momentum and absolute momentum / protective allocation logic to test whether a tactical multi-asset family can improve the project's profit/risk frontier without becoming another SPY_200d, GROR, or active-combo duplicate.

Why this family may help:

- Relative momentum can select stronger assets.
- Absolute momentum / trend filters can reduce crash exposure.
- Protective allocation may avoid deep drawdowns.
- It can remain simple, fixed-rule, and ETF-wrapper only.
- It may be more adaptable than static GTAA and less equity-heavy than quality/momentum.
- It may provide a clean bridge between trend following and tactical allocation.

Why this family may fail:

- It may duplicate GROR, SPY_200d, or active combo.
- It may become too defensive and slow.
- It may overfit tactical allocation logic if too many filters are added.
- It may underperform SPY/QQQ in strong equity regimes.
- It may rely too much on BIL.
- It may look good only because of a specific crisis window.
- It may not add enough after VM quality and DSR equal-weight are already active.

This family should be minimal and fixed-rule. No parameter search. No many-variant tuning. No direct futures. No leverage.
