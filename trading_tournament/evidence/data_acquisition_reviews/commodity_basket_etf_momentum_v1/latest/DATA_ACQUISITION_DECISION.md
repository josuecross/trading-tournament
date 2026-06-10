# Data Acquisition Decision

Decision: `conditional_pending_product_identity_terms_review`

## Rationale

The commodity product/data review approved a data-acquisition review, but this gate still finds product identity, terms/cache rights, and wrapper/tax treatment unresolved. DBC, PDBC, COMT, GSG, and USCI are not locally cached, and no provider path is approved for immediate download.

## Future Download Symbols Approved

None in this task.

## Deferred Symbols

- PDBC and COMT: preferred for a future first-stage prompt after official product identity and terms review.
- DBC, GSG, and USCI: deferred until higher wrapper/tax/commodity-pool risks are confirmed and accepted.

## Required Product-Risk Labels

Future outputs must include `commodity_wrapper_evidence_research_sample_only` and any applicable short-history, K-1/tax, commodity-pool, roll-yield, methodology, liquidity/spread, and duplicate-exposure warnings.

## Raw Data Boundary

Raw OHLCV must remain in approved local cache only and must not be included in compact evidence or advisor packets.

## Implementation Boundary

Implementation remains blocked. This review does not approve commodity strategy code, data loaders, backtests, Profit Exploration, candidate_exhaustive, futures contracts, paper-forward observation, broker integration, live orders, or real-money recommendation.
