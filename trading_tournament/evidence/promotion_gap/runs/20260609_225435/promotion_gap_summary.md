# Promotion Gap Summary

This is a promotion-gap analysis only. It reads existing evidence and does not run backtests, Profit Exploration, candidate_exhaustive, data downloads, provider APIs, or paper-forward activation.

- Rows reviewed: 96
- Candidate_exhaustive queue rows: 0
- Protected active/control/leader rows: 11
- Dominant failure modes: watchlist_missing_diagnostics=24, blocked_survivorship_or_point_in_time_data=19, too_risky_leverage_or_unapproved_mechanics=17, duplicate_existing_leader=10, protected_frozen_control=8
- Next recommended lane: `volatility_managed_equity_etf`
- Exact next allowed action: `create_volatility_managed_equity_etf_fast_exploration_review_prompt`

## Closest Rows
| strategy_id | promotion_decision | failure_mode | closest_to_promotion_score | readiness_label | recommended_next_action |
| --- | --- | --- | --- | --- | --- |
| commodity_basket_tsmom_top2_200d_filter_v1 | mark_too_risky | too_risky_leverage_or_unapproved_mechanics | 30 | low_watchlist | research_sample_review |
| commodity_basket_tsmom_top2_v1 | mark_too_risky | too_risky_leverage_or_unapproved_mechanics | 30 | low_watchlist | research_sample_review |
| crypto_spot_equal_weight_200d_filter_v1 | mark_too_risky | too_risky_leverage_or_unapproved_mechanics | 30 | low_watchlist | research_sample_review |
| crypto_spot_tsmom_top1_cash_filter_v1 | mark_too_risky | too_risky_leverage_or_unapproved_mechanics | 30 | low_watchlist | research_sample_review |
| commodity_basket_tsmom_top2_half_bil_v1 | mark_too_slow | too_slow_target_dilution | 25 | low_watchlist | research_sample_review |
| combo_plus_global_multi_asset_80_20_v1 | mark_duplicate_or_near_duplicate | duplicate_existing_leader | 10 | not_close | duplicate_risk_review |
| global_multi_asset_tsmom_top2_defensive_50_v1 | mark_duplicate_or_near_duplicate | duplicate_existing_leader | 10 | not_close | duplicate_risk_review |
| global_multi_asset_tsmom_top2_v1 | mark_duplicate_or_near_duplicate | duplicate_existing_leader | 10 | not_close | duplicate_risk_review |
| A_ETF_sector_momentum | keep_watchlist | watchlist_missing_diagnostics | 0 | not_close | research_sample_review |
| B_ETF_trend_following | mark_too_slow | too_slow_target_dilution | 0 | not_close | research_sample_review |

## Missing Input Files
- evidence/strategy_lab/latest/active_observations.csv
- evidence/strategy_lab/latest/candidate_status_matrix.csv
- evidence/strategy_lab/latest/historical_leaders.csv
- evidence/strategy_lab/latest/blocked_and_gated_items.csv
- evidence/strategy_lab/latest/next_allowed_actions.csv
- evidence/strategy_lab/latest/research_state_manifest.json

## Decision Counts
- keep_watchlist: 28
- blocked: 19
- mark_too_risky: 17
- mark_duplicate_or_near_duplicate: 10
- keep_frozen_control: 8
- mark_too_slow: 7
- reject: 4
- keep_active_observation: 2
- mark_historical_leader: 1
