# Managed Futures ETF Wrapper Decision Tree

1. If wrapper symbols/history are unavailable, use symbol discovery or defer.
2. If ETF/fund-wrapper adjusted daily data is available, run only a future explicitly prompted research_sample.
3. If variants are too slow, watchlist or reject.
4. If variants breach risk budget, mark too_risky.
5. If variants duplicate GLD/bonds/BIL/equity beta, mark duplicate_or_near_duplicate.
6. If a fixed row is profitable, risk-acceptable, and additive, allow promotion_review_candidate.
