# Commodity Review Decision

Decision: `approve_data_acquisition_review`

## Rationale

The reviewed commodity basket products are plausible enough for a controlled data-acquisition review, but none of DBC, PDBC, COMT, GSG, or USCI is currently cached locally. Product structure, wrapper/tax treatment, official symbol identity, inception/common overlap, adjusted-price availability, and liquidity/spread assumptions still need confirmation.

## Approved Next Step

A future controlled commodity data-acquisition review may be created. That future review must approve symbols, provider path, terms/security, raw-data exclusion, quality checks, cache paths, and metadata outputs before any data download.

## Not Approved

- commodity momentum implementation,
- commodity data download,
- data loader creation,
- backtest,
- Profit Exploration,
- candidate_exhaustive,
- futures contracts or futures roll logic,
- paper-forward observation,
- broker integration,
- live orders,
- real-money recommendation.

## Implementation Boundary

Implementation is not approved because product structures are not fully verified and no candidate commodity basket symbols are cached. A future implementation prompt would require completed data acquisition/quality evidence, fixed rules, benchmark/failure criteria, and wrapper-risk labels.
