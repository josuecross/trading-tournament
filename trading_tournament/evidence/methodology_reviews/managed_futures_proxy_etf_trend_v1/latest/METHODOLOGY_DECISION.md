# Methodology Decision

Decision: `conditional_approval_short_history_label_required`

## Meaning

This decision approves a future `research_sample` implementation prompt only. It does not implement the strategy, run Profit Exploration, run a backtest, permit candidate_exhaustive, permit paper-forward activation, add futures contract logic, add broker integration, add live orders, or make a real-money recommendation.

## Evidence Supporting Approval

- DBMF and KMLM identities are sufficiently confirmed for research_sample wrapper-proxy testing.
- DBMF and KMLM data quality passed in the prior controlled acquisition packet.
- Wrapper-level ETF/fund adjusted-price modeling can be used by the current project engine without futures roll/margin modeling.
- DBMF and KMLM give a different potential return driver from the recent equity-heavy queue candidates.
- Benchmark and failure criteria are defined.

## Evidence Against Stronger Approval

- The effective common overlap starts only on 2020-12-02.
- The evidence does not cover 2008.
- KMLM wrapper history misses the COVID crash period.
- DBMF is more proprietary/active and may be fund-specific.
- Both funds have internal futures, roll, collateral, expense, and possible leverage mechanics hidden behind wrapper prices.
- Research results could be too slow for +300/+400 or depend on one fund only.

## Required Label

Any future implementation prompt and output must label the candidate as:

`fund_wrapper_proxy_short_history_limited_inception_research_sample_only`

## Approved Future Prompt Boundary

Allowed future implementation prompt, if created separately:

- Use DBMF, KMLM, and BIL only unless another review expands the universe.
- Use wrapper-level adjusted daily price series only.
- Use a simple fixed rule.
- Do not add direct futures contract logic.
- Do not model futures rolls or margin.
- Do not use leverage, shorting, or margin at the project strategy level.
- Do not run candidate_exhaustive by default.
- Do not activate paper-forward.

## Final Decision

DBMF and KMLM are acceptable ETF/fund wrapper proxies for a future research_sample implementation prompt, conditional on explicit short-history and wrapper-proxy labeling. No stronger decision is approved here.
