# Fixed Rules And Future Variants

Future variants must be fixed before testing. Do not optimize thresholds, lookbacks, weights, or symbol lists during implementation.

Approved future research_sample variants:

1. `vm_spy_realized_vol_target_v1`
   - Universe: SPY, BIL.
   - Use 20-day or 60-day realized volatility.
   - Normal volatility: 100% SPY.
   - High volatility: 50% SPY / 50% BIL.
   - If SPY is below 200-day SMA: use BIL or the existing trend-rule convention.
   - No leverage.

2. `vm_spy_drawdown_vol_filter_v1`
   - Universe: SPY, BIL.
   - Hold SPY only when SPY is above 200-day SMA and volatility is below a fixed threshold.
   - Otherwise hold BIL.
   - No leverage.

3. `vm_quality_lowvol_proxy_v1`
   - Universe: SPLV, USMV, QUAL, SPY, BIL if available and QA passes.
   - Monthly rebalance.
   - Simple trend or volatility filter.
   - No leverage.

4. `vm_sector_vol_scaled_top2_v1`
   - Universe: sector ETFs already supported by the project plus BIL.
   - Choose top 2 sectors by momentum and reduce exposure in fixed high-volatility regimes.
   - Compare against existing sector momentum behavior.
   - No leverage.

5. `vm_combo_overlay_v1`
   - Universe: current active combo components plus BIL.
   - Apply volatility exposure reducer to a copy of an existing combo with a new strategy id.
   - Must not mutate active combo observation.
   - Research_sample only.

All five variants are approved only for a future implementation prompt. This review does not implement them.
