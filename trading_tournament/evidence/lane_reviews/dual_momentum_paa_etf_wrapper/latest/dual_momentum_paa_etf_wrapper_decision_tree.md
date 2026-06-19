# Dual Momentum PAA ETF Wrapper Decision Tree

1. If fixed ETF-wrapper symbols are unavailable, defer or perform an explicitly prompted data/symbol check.
2. If data is available, run only a future explicitly prompted exploratory research_sample.
3. If rows are too slow, watchlist or reject.
4. If rows breach risk budget, mark too_risky.
5. If rows duplicate GROR/SPY_200d/active combo, mark duplicate_or_near_duplicate.
6. If a fixed row is profitable, risk-acceptable, and additive, allow promotion_review_candidate.
7. If all rows fail, move to GTAA Faber-style benchmark lane.
