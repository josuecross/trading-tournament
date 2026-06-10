# Fee, Expense, And Product Risk Review

This review is product-risk context for research governance. It is not trading advice.

## DBMF

- Expense ratio: 0.85% based on public secondary identity metadata and iMGP/DBi material.
- Fund wrapper cost risk: fund expenses are embedded in NAV/price behavior, but small-account trading may still face bid/ask and slippage costs.
- Liquidity/spread risk: must be reviewed in any future implementation packet; this review does not certify execution quality.
- Active management/model risk: material. DBMF uses a proprietary/active replication approach, so returns may be manager/model specific.
- Internal turnover risk: material because futures positioning can change.
- Futures roll/collateral risk: embedded inside wrapper returns and not decomposed by the project.
- Tax/product-structure caveats: not modeled here.
- Provider adjustment risks: adjusted price data quality passed, but provider revisions and distribution adjustment behavior remain possible.
- Cost treatment: fund costs are embedded in wrapper price/NAV, but project slippage/cost assumptions should still apply to ETF trades.

## KMLM

- Expense ratio: 0.90% from the KraneShares fund page.
- Fund wrapper cost risk: embedded in wrapper performance; trading costs still apply at project level.
- Liquidity/spread risk: future implementation must report realism caveats.
- Active/index/model risk: rules-based index exposure reduces some manager-discretion risk, but index design and tracking risk remain material.
- Internal turnover risk: material because the index can rebalance and roll futures.
- Futures roll/collateral risk: issuer FAQ describes futures rolls and cash/collateral management; the project does not model these internally.
- Tax/product-structure caveats: not modeled here.
- Provider adjustment risks: adjusted price data quality passed, but provider revisions and distribution adjustments remain possible.
- Cost treatment: fund costs are embedded in wrapper price/NAV, but project ETF trading costs should still be applied.

## Product Risk Decision

DBMF and KMLM product risks are acceptable for research_sample wrapper-proxy testing only. They are not acceptable for direct futures claims or paper-forward activation without separate review.
