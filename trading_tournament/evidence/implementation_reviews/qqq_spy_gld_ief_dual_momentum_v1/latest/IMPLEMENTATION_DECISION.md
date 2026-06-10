# Implementation Decision

Decision: `approve_research_sample_implementation`

## Meaning

This approves a future implementation prompt for `qqq_spy_gld_ief_dual_momentum_v1` as a research_sample Profit Exploration candidate only.

It does not implement the strategy in this task.

It does not approve:

- backtesting before implementation prompt
- candidate_exhaustive
- paper-forward observation
- broker integration
- live orders
- real-money use
- parameter tuning

## Required Conditions For The Future Prompt

The future implementation prompt must:

- use cache only / no network
- use fixed predeclared rules
- avoid parameter grids
- include duplicate canonical rule hashing
- report QQQ allocation concentration
- compare against top2, combo, SPY_200d, SPY buy-hold, GLD buy-hold, and BIL
- mark results as research_sample / non-final

No real-money recommendation is made.

