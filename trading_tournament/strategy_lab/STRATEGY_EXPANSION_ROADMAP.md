# Strategy Expansion Roadmap

Created UTC: `2026-06-27T21:05:16.117359+00:00`

This roadmap saves research candidates only. It does not approve, backtest, promote, activate paper-forward, or touch any broker/live-order path.

The ETF-wrapper and breadth-state regime track is treated as archived after no promotion candidates. The expansion pipeline now separates strategy family, rule variant, symbol universe, timeframe, and risk controls before any testing.

Current next action: `pre_register_first_expansion_discovery_batch`

## Priority Order

| Rank | Candidate | Family | Timeframe | Status | Demo eligibility |
|---:|---|---|---|---|---|
| 1 | `dmr_liquid_etf_oversold_rebound_v1` | daily_mean_reversion | daily | daily_research_candidate | daily_demo_review_possible_after_validation |
| 2 | `vm_spy_qqq_daily_vol_target_v1` | volatility_managed_equity | daily | daily_research_candidate | daily_demo_review_possible_after_validation |
| 3 | `sector_rs_weekly_cash_filter_v1` | sector_relative_strength_rotation | weekly | registered_not_tested | weekly_demo_review_possible_after_validation |
| 4 | `vol_compression_breakout_etf_v1` | volatility_compression_breakout | daily | daily_research_candidate | daily_demo_review_possible_after_validation |
| 5 | `rs_pair_rotation_spy_qqq_xlk_xlu_v1` | long_only_relative_strength_pair_rotation | weekly | registered_not_tested | weekly_demo_review_possible_after_validation |
| 6 | `donchian_atr_breakout_etf_v1` | daily_breakout | daily | daily_research_candidate | daily_demo_review_possible_after_validation |
| 7 | `turn_of_month_spy_qqq_v1` | calendar_anomaly | daily | daily_research_candidate | daily_demo_review_possible_after_validation |
| 8 | `cash_pause_overlay_meta_v1` | shared_risk_overlay | meta-overlay | shared_risk_overlay | not_alpha_overlay_only |
| 9 | `orb_spy_qqq_30m_research_v1` | opening_range_breakout | intraday | intraday_research_only | research_only_until_execution_ready |
| 10 | `gap_down_fade_spy_qqq_research_v1` | gap_fade | intraday | intraday_research_only | research_only_until_execution_ready |
| 11 | `vwap_deviation_reversion_research_v1` | vwap_intraday_reversion | intraday | intraday_research_only | research_only_until_execution_ready |
| 12 | `post_earnings_drift_large_cap_later_v1` | post_earnings_drift | daily | later_data_quality_required | later_only_data_quality_blocked |

## Research Lanes

- Priority 1 contains immediate daily or weekly candidates with explicit benchmark and duplication checks.
- Priority 2 contains higher-risk daily or meta-overlay candidates that need careful risk review before testing.
- Priority 3 contains intraday research-only ideas. These are not demo eligible until intraday data quality and execution assumptions are proven.
- Priority 4 is later-only because point-in-time data quality is not yet established.

## Stop Rules

- Saving a candidate does not approve it.
- A failed test rejects the exact variant, not an entire strategy family.
- Any future variant must be pre-registered and must change exactly one major dimension.
- Do not reopen archived ETF-wrapper ideas without a structurally different hypothesis.
- Do not run the first expansion discovery batch from this roadmap step.

## First Expansion Discovery Batch Pre-Registration

Created UTC: `2026-06-28T00:58:21.768188+00:00`

Included candidates:

- `dmr_liquid_etf_oversold_rebound_v1`
- `vm_spy_qqq_daily_vol_target_v1`
- `sector_rs_weekly_cash_filter_v1`
- `vol_compression_breakout_etf_v1`
- `rs_pair_rotation_spy_qqq_xlk_xlu_v1`

Explicitly excluded candidates:

- `donchian_atr_breakout_etf_v1`
- `turn_of_month_spy_qqq_v1`
- `cash_pause_overlay_meta_v1`
- `orb_spy_qqq_30m_research_v1`
- `gap_down_fade_spy_qqq_research_v1`
- `vwap_deviation_reversion_research_v1`
- `post_earnings_drift_large_cap_later_v1`

Rules are frozen for the future discovery step. This step ran only pre-registration and data-availability audit.

Data availability status: `unknown_requires_manual_review`

Next action: `authorize_data_availability_or_cache_refresh_for_first_expansion_batch`

## First Expansion Manual Data Period Review

Created UTC: `2026-06-28T01:11:49.490151+00:00`

Selected resolution: `run_first_expansion_discovery_batch_without_sector_rs`

Next action: `run_first_expansion_discovery_batch_without_sector_rs`

Deferred limited-history action: `pre_register_sector_rs_limited_history_batch`

Reason: `XLRE` is cache-present but starts in 2015, so `sector_rs_weekly_cash_filter_v1` should not be treated as 2007-style/15-year comparable inside the first expansion discovery batch.

## First Expansion Discovery Without Sector RS Result

Created UTC: `2026-06-28T01:58:30.083545+00:00`

Rows evaluated: `dmr_liquid_etf_oversold_rebound_v1, vm_spy_qqq_daily_vol_target_v1, vol_compression_breakout_etf_v1, rs_pair_rotation_spy_qqq_xlk_xlu_v1`

Rows deferred/excluded: `sector_rs_weekly_cash_filter_v1, donchian_atr_breakout_etf_v1, turn_of_month_spy_qqq_v1, cash_pause_overlay_meta_v1, orb_spy_qqq_30m_research_v1, gap_down_fade_spy_qqq_research_v1, vwap_deviation_reversion_research_v1, post_earnings_drift_large_cap_later_v1`

Promotion-review candidates: `0`

Discovery outcomes: `{"dmr_liquid_etf_oversold_rebound_v1": "discovery_reject", "rs_pair_rotation_spy_qqq_xlk_xlu_v1": "discovery_reject", "vm_spy_qqq_daily_vol_target_v1": "discovery_reject", "vol_compression_breakout_etf_v1": "discovery_reject"}`

Next action: `pre_register_sector_rs_limited_history_batch`

No candidate_exhaustive, paper-forward action, provider download, broker/live-order path, ETF-wrapper reopening, or real-money recommendation is authorized.

## Sector RS Limited-History Pre-Registration

Created UTC: `2026-06-28T02:30:32.427849+00:00`

Candidate: `sector_rs_weekly_cash_filter_v1`

Limited-history label: `limited_history_due_to_xlre_inception`

Methodology: `common_start_2016_after_xlre_sma_warmup`

Reason: `XLRE` starts in 2015, so this row must not be treated as 2007-style/full-history comparable.

Valid future outcomes: `discovery_reject, promotion_review_candidate_limited_history`

Next action: `run_sector_rs_limited_history_discovery_batch`

No backtest, discovery, performance metric, candidate_exhaustive, paper-forward action, provider download, broker/live-order path, ETF-wrapper reopening, or real-money recommendation is authorized by this pre-registration.

## Sector RS Limited-History Discovery Result

- Created UTC: `2026-06-28T14:29:34.226417+00:00`
- Evidence path: `C:\Users\te3442\Documents\GitHub\trading-tournament\trading_tournament\evidence\parallel_research_discovery\sector_rs_limited_history\latest`
- Candidate evaluated: `sector_rs_weekly_cash_filter_v1`
- Limited-history label: `limited_history_due_to_xlre_inception`
- Methodology: `common_start_2016_after_xlre_sma_warmup`
- Discovery outcome: `discovery_reject`
- Promotion candidates: `0`
- Rejected candidates: `sector_rs_weekly_cash_filter_v1`
- Next action: `audit_turn_of_month_zero_trade_result`
- This is not a 2007-style full-history test. Same-window benchmarks were recomputed. No candidate_exhaustive, paper-forward activation, provider download, broker/live path, ETF-wrapper reopening, second-expansion rejected-row reopening, or real-money recommendation is authorized by this result.
