# Current Research State

current_phase: `historical_research_expansion_parallel_to_paper_demo_observation`

## Paper/Demo Observation

- combo active as paper/demo observation: `active_paper_demo_observation`
- combo paper_forward_active: `true`
- combo current equity: `$2,998.50`
- combo checkpoint_status: `inconclusive_too_early`
- SPY_200d frozen control: `true`
- SPY_200d status: `active_observation`
- SPY_200d replaced: `false`

Forward checkpoint is not ready for judgment. No conclusion is allowed from first-day forward observation evidence.

## Historical Research Continues

The 30-trading-day paper-forward checkpoint rule does not block historical research. Historical research, data reviews, implementation reviews, diagnostics design, and predeclared combination-design preparation may continue in parallel under evidence gates.

## Active Combo Benchmark Reference

- active-combo benchmark id: `active_combo_vm_dsr_equal_weight_v1`
- active-combo reference available: `true`
- active-combo role: `benchmark_reference_only`
- active-combo next action: `pre_register_active_sleeve_ensemble_lane`
- active-combo paper_forward_active: `false`

## Candidate Triage

- no recent research_sample candidate deserves candidate_exhaustive now: `true`
- QQQ/value candidates: archived references
- sector top2 and managed-futures proxy: watchlist
- combo remains practical historical leader
- asset_class_tsmom_top2_v1 remains serious challenger

	## Next Allowed Action

	Latest historical combination batch status: `completed_no_candidate_exhaustive_queue`. Batch row statuses: combo_plus_top2_50_50_v1:too_slow, combo_plus_managed_futures_80_20_v1:too_slow, top2_plus_managed_futures_80_20_v1:too_slow.

	Latest combination verdict audit: `verdict_labels_corrected_with_no_candidate_exhaustive_run`. Audited verdicts: combo_plus_managed_futures_80_20_v1:short_history_watchlist, combo_plus_top2_50_50_v1:duplicate_or_near_duplicate, top2_plus_managed_futures_80_20_v1:short_history_watchlist. Candidate_exhaustive review decision: `more_diagnostics_required_before_candidate_exhaustive_decision`.

	Latest combination diagnostics completion: `diagnostics_support_short_history_watchlist_only`. Diagnostics status: target-window co-movement=available; component contribution=partially_available; drawdown coincidence=available_window_level_overlap. Candidate_exhaustive run: `false`.

	Attribution diagnostics available: `true`. Target-window attribution: `true`. Component drawdown attribution: `true`. Recovery attribution: `true`. Worst-N drawdown export: `true`.

	Individual stock momentum Gate 1B historical decision: `conditional_pending_provider_cost_review`.
	Individual stock momentum Gate 1C historical decision: `conditional_choose_provider_before_data_acquisition`.
	Individual stock momentum Gate 1D historical decision: `choose_norgate_for_gate1e_acquisition_review`.
	Individual stock momentum Gate 1E Norgate blocker: `blocked_no_local_norgate_access`. Local access: `not_found`. Terms: `not_confirmed`.
	Individual stock momentum Gate 1F status: `conditional_pending_package_and_terms_selection`. Decision: `conditional_pending_package_and_terms_selection`. Provider focus: `Nasdaq Data Link / Sharadar`. Package selected: `false`. Implementation: `not_implemented`; data downloaded: `false`; provider API called: `false`; next action: `user_select_sharadar_package`.

	Historical research queue reprioritization: `choose_commodity_basket_etf_momentum_review`. Stock momentum remains provider-blocked/conditional, with Norgate blocked and Sharadar pending package/terms selection. Next family: `commodity_basket_etf_momentum_v1`. Next action: `create_commodity_basket_etf_momentum_review`.

	Commodity basket ETF product/data review: `approve_data_acquisition_review`. Products reviewed: `DBC, PDBC, COMT, GSG, USCI`. Data acquisition review approved: `true`. Implementation approved: `false`. Commodity data downloaded: `false`. Next action: `commodity_data_acquisition_review`.

	Commodity basket ETF data acquisition review: `conditional_pending_product_identity_terms_review`. Future download symbols approved under the old strict lane: ``. Data downloaded in that review: `false`. Provider API called in that review: `false`.

	Fast exploratory ETF/fund data policy available: `true`. Commodity fast exploratory acquisition downloaded symbols: `DBC, PDBC, COMT, GSG, USCI`. Failed symbols: ``. Raw OHLCV in compact evidence: `false`.

	Commodity exploratory screen status: `research_sample_candidate_risk_budget_breach`. Verdict: `research_sample_candidate_risk_budget_breach`. Candidate_exhaustive run: `false`. Paper-forward active: `false`. Real-money recommendation: `false`.

	Commodity Risk-Control Batch 1 status: completed. Base commodity verdict correction: `research_sample_candidate_risk_budget_breach`. Best risk-control candidate: `combo_plus_commodity_basket_80_20_v1`. Candidate_exhaustive recommended: `false`. Candidate_exhaustive run: `false`. Best row registry status: `watchlist`.

	Commodity Risk-Control Batch 1 verdict audit: `commodity_risk_control_verdicts_audited_more_diagnostics_required`. Candidate_exhaustive decision: `more_diagnostics_required_before_candidate_exhaustive_decision`. Target-window co-movement: `unavailable_missing_window_ids`. Component contribution: `partial_unavailable_exact_path_contribution`. Candidate_exhaustive run: `false`.

	Commodity Risk-Control Batch 1 diagnostics completion: `diagnostics_support_watchlist_only_for_combo_plus_commodity_80_20`. Target-window co-movement: `available`. Component contribution: `partial_available_final_equity_window_contribution`. Drawdown overlap: `available`. Candidate_exhaustive recommended: `false`. Candidate_exhaustive run: `false`.

	Crypto spot fast exploratory policy available: `true`. BTC/ETH cache confirmed: `BTC-USD, ETH-USD`. Downloaded symbols: ``. Failed symbols: ``. Raw OHLCV in compact evidence: `false`.

		Crypto Spot Tier 2 Risk-Control Batch 1 status: `true`. Best risk-control candidate: `combo_plus_crypto_spot_tsmom_90_10_v1`. Candidate_exhaustive recommended: `false`. Candidate_exhaustive run: `false`. Data downloaded in Profit Exploration: `false`. Best row registry status: `research_sample_candidate`. Paper-forward active: `false`. Real-money recommendation: `false`.

		Global multi-asset fast acquisition downloaded symbols: `EFA, EEM`. Cache-confirmed symbols: `SPY, QQQ, GLD, IEF, BIL, DBC, PDBC, COMT, GSG, USCI, IWM, TLT`. Failed symbols: ``. Raw OHLCV in compact evidence: `false`.

		Global Multi-Asset ETF Fast Exploration Batch 1 status: `true`. Best multi-asset candidate: `global_multi_asset_tsmom_top2_v1`. Candidate_exhaustive recommended: `false`. Candidate_exhaustive run: `false`. Data downloaded in Profit Exploration: `false`. Best row registry status: `research_sample_candidate_risk_budget_breach`. Paper-forward active: `false`. Real-money recommendation: `false`.

		Preferred next action: review Global Multi-Asset ETF Fast Exploration Batch 1 as research_sample evidence only; no candidate_exhaustive is currently recommended. keep combo_plus_commodity_basket_80_20_v1 on watchlist only unless new evidence justifies reopening; product identity and wrapper/tax/roll-risk review remains required if reopened; use attribution diagnostics before any future combination candidate_exhaustive review. Do not tune the active combo, replace SPY_200d, or add random one-off ETF momentum variants.

## Research-Only Boundary

No paper-forward strategy was implemented, no backtest was run, no candidate_exhaustive was run, no broker integration or live orders were added, and no real-money recommendation is made. Controlled fast exploratory ETF/fund wrapper data acquisitions may be recorded separately when approved by prompt.
