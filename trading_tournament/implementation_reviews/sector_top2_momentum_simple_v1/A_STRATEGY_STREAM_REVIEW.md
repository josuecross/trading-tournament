# A Strategy Stream Review

The project already has `A_ETF_sector_momentum`. It is not modified by this review and must not be modified by a future sector top2 prompt.

The unresolved issue is evidence-stream exposure: A-family exact fresh-window streams are not compactly exposed for family/profit comparison. A new candidate must not approximate `A_ETF_sector_momentum` from summary metrics and must not corrupt or retrofit the existing A strategy.

## Review Questions

1. Can existing A strategy streams be reused exactly?
   Not from the compact evidence currently used by the project. Existing `A_ETF_sector_momentum` paths exist, but the accepted compact family/profit packets do not expose a fresh-window exact rolling stream suitable for this review.

2. If not, should `sector_top2_momentum_simple_v1` be a clean new minimal implementation rather than modifying A?
   Yes, if future implementation is approved. The clean version should be a separate research_sample candidate with its own rule hash, allocation diagnostics, and rolling-window stream.

3. What would make it different from A?
   The future candidate would be a deliberately simpler fixed rule: monthly rebalance, fixed momentum lookback, top-2 equal weight, explicit absolute trend/cash fallback, no ATR/trailing/rank-drop exits unless separately approved. The existing A strategy uses richer tactical behavior and should remain unchanged.

4. How can it avoid corrupting the existing A strategy?
   Do not edit `A_ETF_sector_momentum`. Do not alias its summary outputs. Do not share mutable state. Add a separate strategy id only after a future prompt, with separate diagnostics and a canonical rule hash.

5. What exact stream requirements must a future implementation satisfy?
   Every rolling window must rebuild from local window returns, start at $3,000, reset high-water/target/stop state, avoid inherited equity slicing, and expose daily or window-local equity sufficient for all Profit Exploration accounting checks.

## Stream Review Result

Result: `clean_minimal_candidate_preferred`.

The implementation review can continue only if the future prompt implements a separate minimal stream and does not modify or approximate `A_ETF_sector_momentum`.
