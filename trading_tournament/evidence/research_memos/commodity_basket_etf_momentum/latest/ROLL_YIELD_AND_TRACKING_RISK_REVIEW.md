# Roll Yield And Tracking Risk Review

Commodity basket products may hold futures or futures-linked indexes internally. The wrapper price can embed futures roll yield, collateral return, fees, transaction costs, and methodology choices.

## Key Risks

- Futures roll yield can dominate returns.
- Contango and backwardation can materially affect performance.
- Wrapper adjusted-price series are not direct commodity futures strategy evidence.
- Results may be product-specific and may not generalize across DBC, PDBC, COMT, GSG, or USCI.
- Product methodology changes can alter historical behavior.
- Energy-heavy baskets can create hidden concentration risk.
- Collateral/T-bill treatment can influence returns and should be understood before comparison with BIL or cash sleeves.

## Modeling Boundary

The project may later model exchange-traded wrapper adjusted prices if a data/product gate approves them. It must not add futures contracts, futures roll logic, margin, leverage, or shorting.

## Required Label

Any future research_sample must label results as `commodity_wrapper_evidence_research_sample_only`.
