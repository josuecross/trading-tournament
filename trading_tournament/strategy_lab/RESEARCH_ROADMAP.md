# Research Roadmap

Planning/governance artifact only. This roadmap does not implement a strategy, run a backtest, run candidate validation, download data, activate paper-forward, or add any broker/live-order/real-money path.

Current next action: `create_managed_futures_etf_wrapper_fast_exploration_review_prompt`

## Priority Backlog

1. `managed_futures_etf_wrapper`
   - Status: `next_family_to_review`
   - Next action: `create_managed_futures_etf_wrapper_fast_exploration_review_prompt`
   - Reason: Highest next priority because the project needs a family that is more additive than SPY/QQQ/sector/growth behavior. Trend-following / managed-futures-style ETF wrappers may provide a different return stream. This must be ETF/fund-wrapper only, not direct futures trading.
2. `dual_momentum_paa_etf_wrapper`
   - Status: `future_family_review`
   - Next action: `create_dual_momentum_paa_etf_wrapper_fast_exploration_review_prompt`
   - Reason: Clean relative momentum plus absolute momentum / protective allocation style. Plausible, but must be checked carefully for duplication with GROR, SPY_200d, and active combo.
3. `gtaa_faber_style_benchmark_lane`
   - Status: `future_benchmark_family`
   - Next action: `create_gtaa_faber_style_benchmark_lane_review_prompt`
   - Reason: Simple global tactical allocation / moving-average benchmark family. Useful as a benchmark and sanity check, but likely overlaps with SPY_200d, GROR, and active combo.
4. `dsr_sector_top2_momentum_200d_bil_v1`
   - Status: `future_review_candidate`
   - Next action: `create_promotion_review_for_dsr_sector_top2_momentum_200d_bil_v1`
   - Reason: Promising DSR same-family row. Exact metrics are missing/unavailable after recovery, and active DSR equal-weight is already frozen, so this is lower priority than new family discovery.
5. `dsr_sector_top3_momentum_defensive_cash_v1`
   - Status: `deferred_candidate_queue`
   - Next action: `create_candidate_exhaustive_prompt_for_dsr_sector_top3_momentum_defensive_cash_v1`
   - Reason: Promotion review already passed and candidate validation was recommended before being deferred. Same-family as active DSR equal-weight, so it remains deferred until new family discovery advances.
6. `static_all_weather_or_permanent_portfolio_benchmark`
   - Status: `future_benchmark_or_control`
   - Next action: `create_static_all_weather_benchmark_lane_review_prompt`
   - Reason: Potentially useful benchmark/control family. Likely too defensive/slow for the profit-first objective unless it provides strong drawdown diversification.
7. `quality_momentum_etf_proxy`
   - Status: `watchlist_no_more_rescue_now`
   - Next action: `keep_quality_momentum_on_watchlist`
   - Reason: Already investigated. It had profit power but failed risk/duplicate gates, including one bounded risk-control rescue batch. Do not rescue again unless new evidence appears.
8. `commodity_wrapper`
   - Status: `deferred`
   - Next action: `defer_commodity_wrapper_until_after_managed_futures_review`
   - Reason: Deferred. Commodity-only wrapper approaches may be too volatile unless expressed through a trend-following or managed-futures-style wrapper.
9. `crypto_spot`
   - Status: `deferred`
   - Next action: `defer_crypto_spot`
   - Reason: Deferred due risk/evidence concerns. Not aligned with current ETF-wrapper recovery direction.
10. `individual_stock_momentum`
   - Status: `blocked_or_deferred`
   - Next action: `keep_individual_stock_momentum_blocked`
   - Reason: Blocked/deferred because of survivorship, provider, package, and terms issues. Not appropriate for the current minimal ETF-wrapper direction.

## Boundaries

- No direct futures trading; managed futures is ETF/fund-wrapper only.
- No real-money recommendation.
- No broker integration, live orders, or order placement.
- No paper-forward activation or checkpoint.
- No backtest, research_sample, candidate_exhaustive, Profit Exploration, data download, or provider API call.
- Do not return to GROR or quality/momentum rescue unless new evidence appears.
