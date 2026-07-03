# Research Roadmap

## Compact Current State

- Updated UTC: `2026-06-30T18:08:59.178098+00:00`
- Current research mode: `operations_observation_checkpoint_completed`
- Official current next action: `manual_review_required_for_observation_logs`
- Observation-only checkpoint evidence: `C:\Users\te3442\Documents\GitHub\trading-tournament\trading_tournament\evidence\operations_observation\continue_paper_forward_observation_only\latest`
- Observation logs status: `observation_logs_missing_or_not_available`
- Current active observation count: `2`
- Active observations: `paper_forward_vm_quality_lowvol_proxy_v1, paper_forward_dsr_sector_equal_weight_defensive_filter_v1`
- Active VM and active DSR remain protected active/frozen observations.
- `static_all_weather_benchmark_v1` remains benchmark/control only.
- Research expansion remains paused.
- GLD/macro recovery remains queued but not run.
- Historical roadmap sections below this compact state are non-authoritative archive records unless cited by current-state files.
- This checkpoint did not run a sandbox batch, strategy discovery, new backtest, candidate_exhaustive, paper-forward activation, provider download, intraday test, broker/live action, strategy promotion, rejected variant reopening, GLD/macro recovery, or real-money recommendation.

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

## Current Research Checkpoint

- ETF-wrapper discovery is paused.
- Current best supported pair is active VM + active DSR.
- Candidate pipeline has no surviving candidate_exhaustive row.
- Next engineering action is `repair_active_combo_benchmark_and_reporting`.
- DSR caveat is accepted but recorded.
- No more immediate similar ETF-wrapper batch discovery.
