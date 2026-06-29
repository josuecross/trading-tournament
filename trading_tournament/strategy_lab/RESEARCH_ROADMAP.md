# Research Roadmap

## Compact Current State

- Updated UTC: `2026-06-29T01:22:56.014181+00:00`
- Current research mode: `next_family_discovery_after_indicator_validation_completed`
- Official current next action: `pause_expansion_and_wait_for_manual_direction`
- Post-discovery state-sync evidence: `C:\Users\te3442\Documents\GitHub\trading-tournament\trading_tournament\evidence\tournament_checkpoints\post_next_family_discovery_state_sync\latest`
- Next-family discovery evidence: `C:\Users\te3442\Documents\GitHub\trading-tournament\trading_tournament\evidence\parallel_research_discovery\next_family_after_indicator_validation\latest`
- Selected family: `managed_futures_etf_wrapper`
- Candidate evaluated: `mfv_equal_weight_trend_filter_v1`
- Candidate outcome: `discovery_reject`
- Promotion candidates count: `0`
- Limited-history label: `limited_history_common_window_short`
- Decision label: `weaker_than_active_references`
- Active VM and active DSR preserved.
- `static_all_weather_benchmark_v1` remains benchmark/control only.
- Exact rejected variants remain closed; old managed-futures top1/top2 rows remain historical context only.
- Intraday remains paused: `true`
- This sync did not run discovery, backtests, new metrics, provider download, intraday data, candidate_exhaustive, paper-forward action, broker/live path, or real-money recommendation.

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

## Pre-registered Active Sleeve Ensemble Lane

- Lane id: `active_sleeve_ensemble_lane`
- Purpose: test fixed combinations of existing active VM and active DSR sleeves, plus optional BIL, against active combo and market benchmarks.
- Future rows: `ase_vm_dsr_equal_weight_v1, ase_dsr_tilt_60_40_v1, ase_vm_tilt_60_40_v1, ase_risk_budget_static_45_45_10_bil_v1, ase_spy200d_canary_vm_dsr_v1, ase_drawdown_guard_reference_v1`
- Status: pre-registered, not yet run.
- No candidate_exhaustive, promotion, paper-forward, broker, live-order, provider-download, or real-money permission.
- Next action after pre-registration: `run_active_sleeve_ensemble_discovery_batch`.

## Roadmap Next Action Consistency

- Checked at UTC: `2026-06-22T04:35:21.793628+00:00`
- Top-level current next action: `run_active_sleeve_ensemble_discovery_batch`
- Historical backlog entries are deferred/context only and were not otherwise rewritten.

## Final ETF Track Stop/Go Decision

- Active-sleeve ensemble produced no promotion candidates.
- Active combo is benchmark/watchlist only.
- Current candidate pipeline remains empty.
- Final decision: `pre_register_one_final_breadth_state_regime_lane_then_stop_if_no_candidate`
- Next action: `pre_register_breadth_state_regime_lane`
- Stop condition: if the breadth-state regime lane produces no promotion-review candidate, run `archive_current_etf_wrapper_track_summary` and stop new ETF discovery.
- No candidate_exhaustive, paper-forward action, provider download, broker/live-order path, or real-money recommendation is authorized by this section.

## Pre-registered Breadth-State Regime Lane

- Lane id: `breadth_state_regime_lane`
- Purpose: test whether a predefined market-breadth/state machine adds value beyond simple top-N momentum, DSR, VM, QVM/LVQ, regional expansion, and active-sleeve ensembles.
- Fixed state definitions: `risk_on` when breadth count >= 8, `neutral` when 5-7, `risk_off` when <= 4, with SPY+QQQ below 200d forcing `risk_off`.
- Future rows: `bsr_breadth_state_top_assets_v1, bsr_breadth_state_defensive_shift_v1, bsr_breadth_state_lowvol_overlay_v1, bsr_breadth_state_active_combo_overlay_v1`
- Status: pre-registered, not yet run.
- No candidate_exhaustive, promotion, paper-forward, broker, live-order, provider-download, or real-money permission.
- Stop condition: if the future breadth-state discovery batch produces no promotion-review candidate, run `archive_current_etf_wrapper_track_summary` and stop new ETF-wrapper discovery.
- Next action after pre-registration: `run_breadth_state_regime_discovery_batch`.

## Breadth-State Regime Discovery Result

- Lane id: `breadth_state_regime_lane`
- Rows evaluated: `bsr_breadth_state_top_assets_v1, bsr_breadth_state_defensive_shift_v1, bsr_breadth_state_lowvol_overlay_v1, bsr_breadth_state_active_combo_overlay_v1`
- Promotion-review candidates: `0`
- Discovery outcomes: `{"bsr_breadth_state_active_combo_overlay_v1": "discovery_reject", "bsr_breadth_state_defensive_shift_v1": "discovery_reject", "bsr_breadth_state_lowvol_overlay_v1": "discovery_reject", "bsr_breadth_state_top_assets_v1": "discovery_reject"}`
- ETF-wrapper stop status: `no_candidate_archive_lane`
- Next action: `archive_stop_etf_wrapper_track`
- No candidate_exhaustive, paper-forward action, provider download, broker/live-order path, or real-money recommendation is authorized.

## Tournament Lane Gate Framework

- Created UTC: `2026-06-28T03:21:02.646468+00:00`
- Evidence path: `C:\Users\te3442\Documents\GitHub\trading-tournament\trading_tournament\evidence\tournament_lane_gate_framework\latest`
- Lanes: `conservative_etf_allocation_lane, moderate_tactical_etf_lane, macro_gld_duration_risk_off_lane, diversifier_contribution_lane, intraday_research_only_lane`
- Status: `created_governance_only`
- Next action: `pre_register_second_expansion_discovery_batch_with_lane_framework`
- No backtest, discovery, performance metric, candidate_exhaustive, paper-forward action, provider download, broker/live-order path, strategy result change, accepted/rejected state change, GLD/GROR state resumption, or real-money recommendation is authorized by this framework update.

## Second Expansion With Lane Framework Pre-Registration

- Created UTC: `2026-06-28T03:37:16.392141+00:00`
- Evidence path: `C:\Users\te3442\Documents\GitHub\trading-tournament\trading_tournament\evidence\pre_registered_lanes\second_expansion_with_lane_framework\latest`
- Candidate count: `5`
- Lanes used: `macro_gld_duration_risk_off_lane, moderate_tactical_etf_lane, diversifier_contribution_lane`
- Data availability status: `sufficient_for_second_expansion_discovery`
- Next action: `run_second_expansion_discovery_batch_with_lane_framework`
- No backtest, discovery, performance metric, candidate_exhaustive, paper-forward action, provider download, broker/live-order path, accepted/rejected strategy state change, old GLD/GROR state resumption, sector RS discovery, intraday/event candidate, or real-money recommendation is authorized by this pre-registration.

## Second Expansion With Lane Framework Discovery Result

- Created UTC: `2026-06-28T04:13:45.007156+00:00`
- Evidence path: `C:\Users\te3442\Documents\GitHub\trading-tournament\trading_tournament\evidence\parallel_research_discovery\second_expansion_with_lane_framework\latest`
- Candidates evaluated: `managed_futures_etf_trend_wrapper_v1, gld_gror_balanced_momentum_clean_v1, donchian_atr_breakout_etf_v1, turn_of_month_spy_qqq_v1, cash_pause_overlay_meta_v1`
- Promotion candidates: `0`
- Limited-history macro/watchlist candidates: `none`
- Rejected candidates: `managed_futures_etf_trend_wrapper_v1, gld_gror_balanced_momentum_clean_v1, donchian_atr_breakout_etf_v1, turn_of_month_spy_qqq_v1, cash_pause_overlay_meta_v1`
- Next action: `run_sector_rs_limited_history_discovery_batch`
- No candidate_exhaustive, paper-forward activation, provider download, broker/live-order path, sector RS discovery, old GLD/GROR state resumption, or real-money recommendation is authorized by this result.

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

## Turn-of-Month Zero-Trade Audit

- Created UTC: `2026-06-28T14:59:40.204220+00:00`
- Evidence path: `C:\Users\te3442\Documents\GitHub\trading-tournament\trading_tournament\evidence\diagnostics\turn_of_month_zero_trade_audit\latest`
- Candidate: `turn_of_month_spy_qqq_v1`
- Zero-trade result confirmed: `True`
- Implementation bug found: `True`
- Calendar windows constructed: `221`
- Entry signals before execution: `180`
- Entry signals after filters: `180`
- Next action: `fix_turn_of_month_implementation_bug_before_more_research`
- This was audit-only: no new discovery, backtest, candidate_exhaustive, paper-forward action, provider download, broker/live path, state change, or real-money recommendation was authorized.

## Turn-of-Month Zero-Trade Implementation Fix

- Created UTC: `2026-06-28T15:13:45.884706+00:00`
- Evidence path: `C:\Users\te3442\Documents\GitHub\trading-tournament\trading_tournament\evidence\diagnostics\turn_of_month_zero_trade_fix\latest`
- Candidate: `turn_of_month_spy_qqq_v1`
- Bug fixed: `True`
- Frozen rule changed: `False`
- First eligible day matches after fix: `221`
- Entry signal count after fix: `180`
- Trade count after fix: `362`
- Next action: `rerun_turn_of_month_frozen_candidate_discovery_after_bugfix`
- This was bug-fix-only and post-fix diagnostic validation only; no broad discovery, candidate_exhaustive, paper-forward action, provider download, broker/live path, candidate status change, or real-money recommendation is authorized by this result.

## Turn-of-Month Post-Bugfix Rerun

- Created UTC: `2026-06-28T15:35:18.910449+00:00`
- Evidence path: `C:\Users\te3442\Documents\GitHub\trading-tournament\trading_tournament\evidence\parallel_research_discovery\turn_of_month_post_bugfix_rerun\latest`
- Candidate: `turn_of_month_spy_qqq_v1`
- Discovery outcome: `discovery_reject`
- Signal/entry reconciliation: `reconciled_initial_in_window_accounting_difference`
- Trade count: `362`
- Promotion candidates: `0`
- Next action: `pre_register_third_expansion_discovery_batch_with_lane_framework`
- This was a one-candidate frozen rerun only. No candidate_exhaustive, paper-forward action, provider download, broker/live path, sector RS discovery, old GROR state resumption, or real-money recommendation is authorized.

## Third Expansion With Lane Framework Pre-Registration

- Created UTC: `2026-06-28T15:50:30.486790+00:00`
- Evidence path: `C:\Users\te3442\Documents\GitHub\trading-tournament\trading_tournament\evidence\pre_registered_lanes\third_expansion_with_lane_framework\latest`
- Candidate count: `4`
- Candidates: `dual_momentum_paa_clean_v1, gld_ief_spy_defensive_rotation_v1, static_all_weather_benchmark_v1, volatility_regime_spy_qqq_bil_v1`
- Data availability status: `sufficient_for_third_expansion_discovery`
- Next action: `run_third_expansion_discovery_batch_with_lane_framework`
- This was pre-registration and data-availability audit only. No backtest, discovery, performance metric, candidate_exhaustive, paper-forward action, provider download, broker/live-order path, accepted/rejected strategy state change, old GLD/GROR state resumption, intraday demo candidate, event-data candidate, or real-money recommendation is authorized.

## Third Expansion With Lane Framework Discovery Result

- Created UTC: `2026-06-28T16:32:01.528971+00:00`
- Evidence path: `C:\Users\te3442\Documents\GitHub\trading-tournament\trading_tournament\evidence\parallel_research_discovery\third_expansion_with_lane_framework\latest`
- Candidates evaluated: `dual_momentum_paa_clean_v1, gld_ief_spy_defensive_rotation_v1, static_all_weather_benchmark_v1, volatility_regime_spy_qqq_bil_v1`
- Promotion candidates: `0`
- Macro promotion candidates: `none`
- Benchmark/control accepted: `static_all_weather_benchmark_v1`
- Rejected candidates: `dual_momentum_paa_clean_v1, gld_ief_spy_defensive_rotation_v1, volatility_regime_spy_qqq_bil_v1`
- Next action: `register_static_all_weather_as_benchmark_control_only`
- No candidate_exhaustive, paper-forward activation, provider download, broker/live-order path, old GLD/GROR state resumption, intraday/event candidate, or real-money recommendation is authorized by this result.

## Static All-Weather Benchmark Control Registration

- Created UTC: `2026-06-28T17:59:39.271971+00:00`
- Evidence path: `C:\Users\te3442\Documents\GitHub\trading-tournament\trading_tournament\evidence\benchmark_controls\static_all_weather_benchmark_v1\latest`
- Benchmark/control ID: `static_all_weather_benchmark_v1`
- Status: `benchmark_control_accepted`
- Universe: `SPY, IEF, GLD, BIL`
- Frozen allocation: `30% SPY, 40% IEF, 20% GLD, 10% BIL`
- Usage: same-window benchmark/control only for macro, diversifier, conservative allocation, and portfolio-contribution reviews.
- Next action: `audit_third_expansion_failures_before_more_expansion`
- No backtest, discovery, new performance metric, candidate_exhaustive, paper-forward action, provider download, broker/live path, third-expansion rejected-row reopening, or real-money recommendation is authorized by this registration.

## Third Expansion Failure Audit

- Created UTC: `2026-06-28T18:44:32.861538+00:00`
- Evidence path: `C:\Users\te3442\Documents\GitHub\trading-tournament\trading_tournament\evidence\tournament_failure_synthesis\third_expansion_failure_audit\latest`
- Audit-only governance step: `true`
- Recent expansion failures are mostly clean strategy failures, with limited lane-framing mismatch for macro/diversifier rows.
- No candidate deserves promotion review.
- Exact rejected variants remain closed.
- `static_all_weather_benchmark_v1` remains benchmark/control only.
- Daily/weekly expansion should pause before more discovery.
- Final next action: `pre_register_intraday_research_readiness_audit`
- No backtest, discovery, new performance metric, candidate_exhaustive, paper-forward action, provider download, broker/live path, rejected-row reopening, strategy-rule change, or real-money recommendation is authorized by this audit.

## Intraday Research Readiness Audit

- Created UTC: `2026-06-28T19:09:16.167748+00:00`
- Evidence path: `C:\Users\te3442\Documents\GitHub\trading-tournament\trading_tournament\evidence\intraday_readiness\intraday_research_readiness_audit\latest`
- Readiness verdict: `intraday_research_not_ready`
- Critical blockers: approved intraday data/cache, session calendar QA, signal/entry/exit bar contract, fill/slippage/no-fill model, intraday risk engine, and intraday kill-switch tests.
- Candidate suitability: ORB, gap-down fade, and VWAP deviation remain research-only concepts and are not authorized for discovery.
- Final next action: `fix_intraday_readiness_blockers`
- No intraday backtest, strategy discovery, new performance metric, provider download, candidate_exhaustive, paper-forward action, broker order, live order, strategy-rule change, strategy-state change, or real-money recommendation is authorized by this audit.

## Intraday Readiness Blocker Fix

- Created UTC: `2026-06-28T19:23:56.754166+00:00`
- Evidence path: `C:\Users\te3442\Documents\GitHub\trading-tournament\trading_tournament\evidence\intraday_readiness\fix_intraday_readiness_blockers\latest`
- Blocker-fix-only mode: `true`
- Contracts added: intraday data schema, cache, session timing, fill model, risk engine, kill switch, event logging, and candidate readiness gates.
- Blockers fixed: `6`
- Blockers partially fixed: `2`
- Critical blockers remaining: `2`
- Intraday cache contract created: `True`
- Intraday data present: `False`
- Intraday data source approved: `False`
- Readiness verdict after fix: `manual_intraday_data_source_review_required`
- Next action: `manual_intraday_data_source_review_required`
- No intraday backtest, discovery, performance metric, provider download, candidate_exhaustive, paper-forward action, broker order, live order, strategy-rule change, strategy-state change, demo eligibility, or real-money recommendation is authorized.

## Manual Intraday Data-Source Review

- Created UTC: `2026-06-28T19:55:37.440780+00:00`
- Evidence path: `C:\Users\te3442\Documents\GitHub\trading-tournament\trading_tournament\evidence\intraday_readiness\manual_intraday_data_source_review\latest`
- Decision: `manual_intraday_data_source_review_required`
- Approved intraday data source found: `False`
- Manual terms review required: `True`
- Local intraday data present: `False`
- Candidate source count: `3`
- Recommended data-source path: `manual_terms_review_then_select_yfinance_intraday_alpaca_data_or_manual_csv_source`
- Next action: `manual_intraday_data_source_review_required`
- No intraday backtest, discovery, performance metric, provider download, provider API call, cache bootstrap, candidate_exhaustive, paper-forward action, broker order, live order, strategy-state change, demo eligibility, or real-money recommendation is authorized.

## Intraday Data Constraints Pause

- Created UTC: `2026-06-28T20:18:43.192687+00:00`
- Evidence path: `C:\Users\te3442\Documents\GitHub\trading-tournament\trading_tournament\evidence\intraday_readiness\intraday_data_constraints_pause\latest`
- Governance checkpoint only: `true`
- Intraday research paused: `true`
- Approved intraday data source found: `false`
- Local intraday data present: `false`
- Manual terms review required: `true`
- Preserved infrastructure: intraday data schema, cache contract, session timing, fill/slippage/no-fill, risk engine, kill switch, event logging, and candidate readiness gates.
- Recommended non-intraday pivot: `pre_register_risk_controlled_high_return_family_review`
- No backtest, discovery, new performance metric, provider download, provider API call, cache bootstrap, candidate_exhaustive, paper-forward action, broker order, live order, strategy-state change, rejected-row reopening, or real-money recommendation is authorized.

## Risk-Controlled High-Return Family Review

- Created UTC: `2026-06-28T20:30:09.591887+00:00`
- Evidence path: `C:\Users\te3442\Documents\GitHub\trading-tournament\trading_tournament\evidence\pre_registered_lanes\risk_controlled_high_return_family_review\latest`
- Pre-registration only: `true`
- Candidate count: `2`
- Candidate IDs: `rc_dual_momentum_paa_vol_scaled_v1, rc_donchian_breakout_risk_budget_v1`
- Families reviewed: `dual_momentum_paa_clean_v1, donchian_atr_breakout_etf_v1, quality_momentum_etf_proxy_watchlist_only`
- Exact rejected parents remain closed: `dual_momentum_paa_clean_v1, donchian_atr_breakout_etf_v1`
- Data availability status: `sufficient_for_preregistered_discovery`
- Intraday research remains paused: `true`
- Next action: `run_risk_controlled_high_return_discovery_batch`
- No backtest, discovery, new performance metric, provider download, intraday data, candidate_exhaustive, paper-forward action, broker/live path, strategy-state change, rejected-row reopening, or real-money recommendation is authorized.

## Risk-Controlled High-Return Rule-Freeze Patch

- Created UTC: `2026-06-28T20:49:38.215198+00:00`
- Evidence path: `C:\Users\te3442\Documents\GitHub\trading-tournament\trading_tournament\evidence\pre_registered_lanes\risk_controlled_high_return_rule_freeze_patch\latest`
- Rule-freeze patch only: `true`
- Candidate membership changed: `false`
- Candidate count: `2`
- Parent rule mismatch found: `True`
- All formulas frozen: `True`
- Intraday research remains paused: `true`
- Next action: `manual_review_required_for_risk_controlled_high_return_batch`
- No backtest, discovery, new performance metric, provider download, intraday data, candidate_exhaustive, paper-forward action, broker/live path, strategy-state change, rejected-row reopening, or real-money recommendation is authorized.

## Risk-Controlled High-Return Manual Review

- Created UTC: `2026-06-28T21:04:46.006937+00:00`
- Evidence path: `C:\Users\te3442\Documents\GitHub\trading-tournament\trading_tournament\evidence\pre_registered_lanes\risk_controlled_high_return_manual_review\latest`
- Manual review only: `true`
- Decision: `approve_risk_controlled_high_return_discovery_batch_after_manual_review`
- Next action: `run_risk_controlled_high_return_discovery_batch`
- Dual momentum accepted: `True`
- Donchian parent mismatch found: `True`
- Prior 55-day language invalidated: `True`
- Official Donchian rule uses 20-day breakout: `True`
- Donchian accepted for future discovery: `True`
- Candidate count for future discovery: `2`
- No backtest, discovery, new metric, provider download, intraday data, candidate_exhaustive, paper-forward action, broker/live path, strategy-state change, rejected-row reopening, or real-money recommendation is authorized.

## Risk-Controlled High-Return Discovery

- Created UTC: `2026-06-28T21:20:52.719075+00:00`
- Evidence path: `C:\Users\te3442\Documents\GitHub\trading-tournament\trading_tournament\evidence\parallel_research_discovery\risk_controlled_high_return_discovery\latest`
- Candidates evaluated: `rc_dual_momentum_paa_vol_scaled_v1, rc_donchian_breakout_risk_budget_v1`
- Promotion candidates: `0`
- Promotion candidate IDs: `none`
- Rejected candidate IDs: `rc_dual_momentum_paa_vol_scaled_v1, rc_donchian_breakout_risk_budget_v1`
- Invalidated 55-day Donchian rule used: `false`
- Intraday research remains paused: `true`
- Next action: `audit_risk_controlled_high_return_discovery_failures`
- No provider download, intraday data, candidate_exhaustive, paper-forward action, broker/live path, or real-money recommendation is authorized.

## Research Operating System Refactor

- Created UTC: `2026-06-28T21:55:45.685467+00:00`
- Evidence path: `C:\Users\te3442\Documents\GitHub\trading-tournament\trading_tournament\evidence\governance\research_operating_system_refactor\latest`
- Structure path: `C:\Users\te3442\Documents\GitHub\trading-tournament\trading_tournament\strategy_lab\research_os`
- Refactor status: `created_manual_review_required`
- Current model: family-first research, lane-specific gates, separate research value / promotion / paper-demo eligibility, mandatory parent-child lineage, mandatory signal funnel, controlled indicator governance, and data-source gates before testing.
- Preserved states: active VM and active DSR remain protected active/frozen observations; static all-weather remains benchmark/control only; intraday remains paused/data-source-blocked; exact rejected variants remain closed.
- No strategy backtest, discovery, new performance metric, provider download, intraday data use, candidate_exhaustive, paper-forward review/activation, broker/live path, order action, strategy promotion, or real-money recommendation is authorized by this refactor.
- Next action: `manual_review_refactored_research_os`

## Manual Review After Repository Refactor

- Created UTC: `2026-06-28T22:31:00.959614+00:00`
- Evidence path: `C:\Users\te3442\Documents\GitHub\trading-tournament\trading_tournament\evidence\repository_refactor\manual_review_after_family_lane_os_refactor\latest`
- Refactor accepted: `true`
- Canonical current-state file: `C:\Users\te3442\Documents\GitHub\trading-tournament\trading_tournament\reports\compact_state\current_tournament_state.md`
- Roadmap next action reconciled: `true`
- Official current next action: `audit_risk_controlled_high_return_discovery_failures`
- Generated/bulky tracked artifacts classified: `true`
- Files untracked from Git in this review: `0`
- Bulk generated-artifact untracking is safely deferred until a human confirms historical lineage coverage.
- Prior `manual_review_required_after_repository_refactor` and `manual_review_refactored_research_os` labels are now completed historical review labels.
- No strategy discovery, backtest, new metric, provider download, intraday data, candidate_exhaustive, paper-forward action, broker/live path, order action, rejected-row reopening, active-state mutation, or real-money recommendation is authorized by this review.

## Post Git Untrack Validation

- Created UTC: `2026-06-28T22:46:23.504180+00:00`
- Evidence path: `C:\Users\te3442\Documents\GitHub\trading-tournament\trading_tournament\evidence\repository_refactor\post_git_untrack_validation\latest`
- Validation status: `passed`
- Canonical files present: `true`
- Generated artifacts untracked or ignored: `true`
- Official current next action: `audit_risk_controlled_high_return_discovery_failures`
- No strategy discovery, backtest, new metric, provider download, intraday data, candidate_exhaustive, paper-forward action, broker/live path, order action, rejected-row reopening, active-state mutation, or real-money recommendation is authorized by this validation.

## Risk-Controlled High-Return Failure Audit

- Created UTC: `2026-06-28T22:51:54.236506+00:00`
- Evidence path: `C:\Users\te3442\Documents\GitHub\trading-tournament\trading_tournament\evidence\tournament_failure_synthesis\risk_controlled_high_return_failure_audit\latest`
- Audit-only governance step: `true`
- Candidates audited: `rc_dual_momentum_paa_vol_scaled_v1`, `rc_donchian_breakout_risk_budget_v1`
- Promotion-review candidates: `0`
- Clean rejects: `2`
- Dual momentum conclusion: volatility scaling preserved some target-hit evidence but failed small-account drawdown/risk-buffer, stress, and benchmark gates.
- Donchian conclusion: risk-budget sizing reduced drawdown but destroyed target-hit evidence and left skip/block logic plus defensive allocation dominating the result.
- Invalidated 55-day Donchian rule used: `false`
- Exact variants remain closed: `true`
- Immediate risk-control rescue allowed: `false`
- Intraday remains paused: `true`
- Official current next action: `pause_expansion_and_summarize_tournament_state`
- No backtest, discovery, new metric, provider download, intraday data, candidate_exhaustive, paper-forward action, broker/live path, order action, rejected-row reopening, risk-control tuning, gate relaxation, or real-money recommendation is authorized by this audit.

## Pause Expansion Summary

- Created UTC: `2026-06-28T23:00:16.496120+00:00`
- Evidence path: `C:\Users\te3442\Documents\GitHub\trading-tournament\trading_tournament\evidence\tournament_checkpoints\pause_expansion_summary\latest`
- Expansion paused: `true`
- Promotion candidates current count: `0`
- Active/frozen observations: `2`
- Benchmark/control references: `7`
- Closed exact-variant groups: `7`
- Families open only with future new hypothesis: `5`
- Intraday remains paused: `true`
- Official current next action: `pre_register_indicator_library_integration_audit`
- This checkpoint does not authorize discovery, backtests, new metrics, provider download, intraday data, candidate_exhaustive, paper-forward action, broker/live order paths, exact rejected variant reopening, gate relaxation, post-result tuning, or real-money recommendation.

## Indicator Library Integration Audit

- Created UTC: `2026-06-28T23:09:58.909235+00:00`
- Evidence path: `C:\Users\te3442\Documents\GitHub\trading-tournament\trading_tournament\evidence\governance\indicator_library_integration_audit\latest`
- Governance-only audit: `true`
- Dependency decision: `no_dependency_added_policy_only`
- Selected library: `current_custom_indicators_only`
- Library dependency added: `false`
- Allowed indicator entries: `17`
- Forbidden indicator rules: `11`
- Expansion remains paused: `true`
- Intraday remains paused: `true`
- Official current next action: `pre_register_indicator_validation_harness`
- This audit does not authorize discovery, backtests, new metrics, provider download, intraday data, candidate_exhaustive, paper-forward action, broker/live order paths, exact rejected variant reopening, indicator mining, parameter grids, gate weakening, or real-money recommendation.

## Indicator Validation Harness Preregistration

- Created UTC: `2026-06-28T23:20:59.220756+00:00`
- Evidence path: `C:\Users\te3442\Documents\GitHub\trading-tournament\trading_tournament\evidence\governance\indicator_validation_harness_preregistration\latest`
- Preregistration-only: `true`
- Indicator library dependency added: `false`
- Fixture types defined: `7`
- Indicator categories covered: `5`
- Lookahead checks defined: `6`
- Parity-test policy defined: `true`
- Expansion remains paused: `true`
- Intraday remains paused: `true`
- Official current next action: `implement_indicator_validation_harness`
- This preregistration does not authorize discovery, backtests, new metrics, provider download, intraday data, candidate_exhaustive, paper-forward action, broker/live order paths, indicator-library installation, strategy rule creation, or real-money recommendation.

## Indicator Validation Harness Implementation

- Created UTC: `2026-06-28T23:54:27.767971+00:00`
- Evidence path: `C:\Users\te3442\Documents\GitHub\trading-tournament\trading_tournament\evidence\governance\indicator_validation_harness_implementation\latest`
- Implementation-only: `true`
- Indicator library dependency added: `false`
- Fixture types implemented: `7`
- Indicator tests added: `19`
- Lookahead tests added: `6`
- Indicator bugs found: `0`
- Indicator bugs fixed: `0`
- Material past-strategy-result risk flagged: `false`
- Expansion remains paused: `true`
- Intraday remains paused: `true`
- Official current next action: `pre_register_indicator_library_dependency_review`
- This implementation does not authorize discovery, trading backtests, new strategy metrics, provider download, intraday data, candidate_exhaustive, paper-forward action, broker/live order paths, indicator-library installation, strategy rule creation, or real-money recommendation.

## Indicator Library Dependency Review

- Created UTC: `2026-06-29T00:14:06.525177+00:00`
- Evidence path: `C:\Users\te3442\Documents\GitHub\trading-tournament\trading_tournament\evidence\governance\indicator_library_dependency_review\latest`
- Dependency-review-only: `true`
- Dependency installed: `false`
- Dependency files changed: `false`
- Dependency decision: `stay_custom_indicators_only`
- Selected dependency candidate: `current_custom_indicators_only`
- Proposed dependency patch created: `false`
- Expansion remains paused: `true`
- Intraday remains paused: `true`
- Official current next action: `pre_register_next_family_after_indicator_validation`
- This review does not authorize dependency installation, strategy discovery, trading backtests, new strategy metrics, provider download, intraday data, candidate_exhaustive, paper-forward action, broker/live order paths, indicator strategy creation, grid search, or real-money recommendation.

## Next Family After Indicator Validation Preregistration

- Created UTC: `2026-06-29T00:46:51.160137+00:00`
- Evidence path: `C:\Users\te3442\Documents\GitHub\trading-tournament\trading_tournament\evidence\pre_registered_lanes\next_family_after_indicator_validation\latest`
- Family-preregistration-only: `true`
- Selected family: `managed_futures_etf_wrapper`
- Candidate count: `1`
- Candidate IDs: `mfv_equal_weight_trend_filter_v1`
- Data availability status: `sufficient_for_preregistered_discovery`
- Indicator library dependency added: `false`
- Expansion remains paused until discovery is separately authorized: `true`
- Intraday remains paused: `true`
- Official current next action: `run_next_family_discovery_after_indicator_validation`
- This preregistration does not authorize discovery, backtests, new strategy metrics, provider download, intraday data, candidate_exhaustive, paper-forward action, broker/live order paths, exact rejected variant reopening, or real-money recommendation.

## Next Family Discovery After Indicator Validation

- Created UTC: `2026-06-29T01:12:49.817446+00:00`
- Evidence path: `C:\Users\te3442\Documents\GitHub\trading-tournament\trading_tournament\evidence\parallel_research_discovery\next_family_after_indicator_validation\latest`
- Discovery scope: `mfv_equal_weight_trend_filter_v1` only
- Selected family: `managed_futures_etf_wrapper`
- Candidate outcome: `discovery_reject`
- Decision label: `weaker_than_active_references`
- Promotion candidates count: `0`
- Limited-history label: `limited_history_common_window_short`
- Next action: `pause_expansion_and_wait_for_manual_direction`
- Forbidden paths remained closed: candidate_exhaustive, paper-forward, provider download, intraday, broker/live order, and real-money recommendation.

## Post Next-Family Discovery State Sync

- Created UTC: `2026-06-29T01:22:56.014181+00:00`
- Evidence path: `C:\Users\te3442\Documents\GitHub\trading-tournament\trading_tournament\evidence\tournament_checkpoints\post_next_family_discovery_state_sync\latest`
- State-sync-only: `true`
- Candidate: `mfv_equal_weight_trend_filter_v1`
- Candidate outcome: `discovery_reject`
- Promotion candidates count: `0`
- Limited-history label: `limited_history_common_window_short`
- Next action: `pause_expansion_and_wait_for_manual_direction`
- No strategy discovery, backtest, new metric, provider download, intraday data, indicator dependency install, candidate_exhaustive, paper-forward, broker/live, or real-money action occurred in this sync.
