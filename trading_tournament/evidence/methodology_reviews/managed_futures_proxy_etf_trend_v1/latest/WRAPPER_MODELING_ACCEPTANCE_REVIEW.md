# Wrapper Modeling Acceptance Review

The project models daily adjusted ETF/fund price series. It does not model futures contracts, futures rolls, margin, collateral mechanics, liquidation risk, or internal leverage.

## Questions

1. Can the project model DBMF/KMLM as ETF/fund wrappers using adjusted daily prices?

Yes, for research_sample only. The model can treat DBMF and KMLM as traded fund-wrapper return streams using adjusted daily prices.

2. What does wrapper-level modeling capture?

It captures the realized net price behavior of the wrapper after fund-level implementation, expenses, internal execution, collateral handling, and distributions as reflected in the adjusted price series.

3. What does wrapper-level modeling miss?

It misses futures contract selection, roll timing, notional exposure, collateral yield mechanics, margin requirements, intraday futures risk, internal fund execution, and methodology drift.

4. Does wrapper modeling avoid futures roll/margin/liquidation modeling?

Yes for the project engine, because the tradable wrapper is the ETF/fund price series. That does not mean those internal risks disappear; they are embedded and opaque.

5. Does wrapper modeling hide internal leverage, fees, turnover, collateral, and roll effects?

Yes. The adjusted price series can show net outcomes, but it does not expose the causal mechanics.

6. Is wrapper modeling acceptable for research_sample only?

Yes, conditionally. It must be labeled as fund-wrapper proxy evidence and short-history evidence.

7. Is wrapper modeling acceptable for candidate_exhaustive later?

Only after research_sample evidence shows enough target/risk promise and after a separate candidate_exhaustive gate accepts short-history limitations. Candidate_exhaustive should be blocked or specially labeled if short inception makes claims misleading.

8. Is wrapper modeling acceptable for paper-forward?

No, not from this review. Paper-forward would require a separate promotion review, product-risk review, execution realism review, and explicit decision. This packet does not permit paper-forward activation.

9. What would invalidate wrapper-level modeling?

Wrapper modeling should be rejected if fund identity is uncertain, methodology is too opaque to classify, adjusted price quality fails, fund history is too short for the intended claim, liquidity/spread risk makes small-account execution unrealistic, or results are presented as direct futures strategy evidence.

## Acceptance Decision

Wrapper-level ETF/fund price modeling is acceptable only for a future research_sample implementation prompt. It is not acceptable as direct managed-futures strategy evidence and does not approve candidate_exhaustive, paper-forward, broker integration, live orders, or real-money recommendation.
