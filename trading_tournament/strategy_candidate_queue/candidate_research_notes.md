# Candidate Research Notes

The current practical baseline is `SPY_200d_trend_model`. The strongest drawdown-aware Profit Exploration challenger is `combo_SPY200d_GLD_50_50_v1`, while `asset_class_tsmom_top2_v1` remains a serious but more drawdown-budget-intensive challenger. New ideas should be judged against those rows, not against weak or cherry-picked benchmarks.

## Queue Design Principles

- Prefer simple ETF/fund candidates that can be tested with existing daily adjusted-price conventions.
- Prefer candidates with a literature prior or a clear project-derived reason to test.
- Require a clear failure mode before implementation.
- Require candidate-specific benchmarks.
- Treat +$300/+400 as hurdles, not proof.
- Penalize drawdown-budget usage before a hard stop breach.
- Do not add variants to rescue a weak result.
- Do not use exploratory crypto, stock, or high-complexity instrument evidence as candidate-grade evidence.

## Candidate Notes

`qqq_spy_gld_ief_dual_momentum_v1` is the cleanest ETF-extension idea because it adds QQQ growth momentum without introducing leverage, shorts, margin, or new instrument classes. The risk is that it simply increases equity beta and duplicates current momentum finalists.

`value_momentum_factor_etf_rotation_v1` has a stronger academic prior, but ETF proxies may be young and fund-construction-specific. It should not be coded until proxy history and benchmark relevance are reviewed.

`low_vol_quality_defensive_rotation_v1` may reduce drawdown, but the project has repeatedly found defensive rows can become too slow. It needs a target-potential review before implementation.

`sector_top2_momentum_simple_v1` may improve target probability through sector dispersion, but it is tightly linked to the unresolved A-sector stream issue. No summary-metric approximation should be used.

`managed_futures_proxy_etf_trend_v1` is attractive for diversification if data is usable, but many managed-futures ETFs have short histories and may not represent the long-term literature.

`treasury_duration_trend_rotation_v1` is most useful as a drawdown-control candidate, but it is likely too slow unless paired with a higher-return sleeve in a later separately approved combination.

`commodity_basket_etf_momentum_v1` may diversify inflation regimes, but commodity ETF roll yield and product structure can distort evidence.

`crypto_spot_tsmom_tier2_review_v1` has target potential but remains blocked from candidate-grade treatment until exchange-specific data, fees, spreads, and 24/7 execution assumptions are documented.

`individual_stock_momentum_gate1b_v1` has a meaningful return prior, but the project must not implement it without survivorship-free data and delisting treatment.

`options_futures_forex_intraday_blocked_reference_v1` is included so high-complexity families are recorded as blocked, not ignored.

No real-money recommendation is made.
