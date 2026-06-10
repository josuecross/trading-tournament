# Cost, Tax, And Product Risk Review

## Cost And Liquidity

Expense ratios were not verified from official current documents in this task. A future product/data review must record expense ratio, average volume, bid/ask spread proxy, and trading cost assumptions before implementation.

Wrapper prices already include internal fund expenses, futures roll effects, collateral mechanics, and product-level costs to the extent reflected in adjusted prices. Project-level trading costs and slippage still apply to entry/rebalance trades.

## Tax And Wrapper Complexity

DBC and USCI likely carry K-1 or commodity-pool tax complexity. GSG may carry trust/product-specific tax complexity. PDBC is commonly identified as a no-K-1 wrapper, but official confirmation is required. COMT requires official confirmation of structure and tax treatment.

Tax complexity is not modeled as strategy performance in this research project, but it can make interpretation and practical suitability weaker. No real-money recommendation is made.

## Product Risks

- ETN issuer credit risk must be reviewed if any future commodity symbol is an ETN.
- Fund closure or product methodology changes can impair historical interpretation.
- Commodity drawdowns can be severe and may consume the -$600 risk budget quickly.
- Small $3,000 simulated accounts must avoid unrealistic concentration, turnover, or high-spread products.
- Liquidity and spread assumptions must be explicit before any research_sample.

## Cost Conclusion

Embedded wrapper costs are not enough by themselves. Future tests must still apply project-level trading cost/slippage assumptions and must disclose product expense/spread limitations.
