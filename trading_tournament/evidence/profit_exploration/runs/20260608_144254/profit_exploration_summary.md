# Profit Exploration Summary

## Research Boundary

This is research-only paper/demo evidence. It does not recommend real-money trading, does not connect to brokers or exchanges, and does not place orders.

## Run Identity

- run_id: 20260608_144254
- mode: profit exploration
- account: independent $3,000 simulated account per experiment
- +$300/+400: minimum and strong success hurdles, not the final objective
- objective: highest stop-aware profit potential beyond +$400 while respecting the -$600 stop boundary

## Run Validation Scope

- run_validation_scope: all_horizons
- reduced_validation: false
- reduced_validation_reason: none
- selected_horizons: 30,60,90,180
- omitted_horizons: none
- selected_horizons_completed: false
- full_horizon_validation_completed: false
- candidate_exhaustive_completed: false
- final_validation_completed: false
- sampled_results_are_final: false

## Experiments

Completed experiments: GLD_buy_hold, asset_class_tsmom_top2_v1, SPY_200d_trend_model, BIL_cash_proxy, combo_SPY200d_GLD_50_50_v1, global_multi_asset_tsmom_top2_v1, combo_plus_global_multi_asset_80_20_v1, global_multi_asset_tsmom_top2_defensive_50_v1.

Blocked experiments: none.

Incomplete experiments: none.

Duplicate-skipped experiments: none.

Duplicate handling: canonical rule hashes are computed from strategy family, universe, rebalance frequency, lookback, trend filter, cash fallback, selected asset count, weighting rule, execution timing, max gross exposure, and leverage setting. Later duplicate rows are retained for audit visibility but are not counted as independent evidence.

## Target Ladder

- Highest exact +$300 probability: global_multi_asset_tsmom_top2_v1 (64.1%)
- Highest exact +$400 probability: GLD_buy_hold (43.6%)
- Highest +$600 probability: global_multi_asset_tsmom_top2_v1 (23.1%)
- Highest +$900 probability: GLD_buy_hold (17.9%)
- Highest +$1200 probability: GLD_buy_hold (0.0%)

## Profit And Risk

- Highest median stop-enforced equity: global_multi_asset_tsmom_top2_v1 ($3,208.81)
- Highest upside tail: GLD_buy_hold ($3,833.09)
- Best risk control: BIL_cash_proxy
- Best overall profit/risk tradeoff: GLD_buy_hold
- Exact best +$300 family/experiment: GLD_buy_hold
- Exact best +$400 family/experiment: GLD_buy_hold

## Combination Review

Combinations improving the diagnostic score versus SPY_200d: none.

High-upside but too-risky rows: GLD_buy_hold.




## Profit Score Audit

The original final_score ranked asset_class_tsmom_top2_v1 above combo_SPY200d_GLD_50_50_v1 because top2 had slightly higher 90-day +300/+400 target rates and lower stress degradation. The combo had better median equity, p95 equity, expected profit, stop behavior, and worst drawdown, but the original drawdown penalty only applies after the -$600 budget is breached. Original final_score: top2 77.7910; combo -60.5426.

Alternative diagnostic score leaders:

- profit_seeking_score leader: GLD_buy_hold (383.77)
- balanced_score leader: asset_class_tsmom_top2_v1 (192.52)
- drawdown_control_score leader: BIL_cash_proxy (353.17)

Score-audit verdict: the original score is usable as a target-ladder diagnostic, but it under-credits drawdown control inside the -$600 risk budget. The balanced and drawdown-control views should be reviewed before treating a narrow final_score edge as decision-dominant.



## Drawdown-Aware Score v2

Score v2 was added because the original final_score only penalized worst drawdown after the -$600 risk budget was breached. V2 penalizes risk-budget usage before the hard stop, so a row using roughly 95% of the drawdown budget is not treated the same as a row using roughly 75%.

V2 differs from the original final_score by combining 90-day and 180-day target/equity rewards with explicit stop, stress, evidence-quality, and drawdown-budget penalties. The drawdown penalty has no penalty up to 50% risk-budget use, moderate penalty from 50-75%, large penalty from 75-100%, and severe penalty above 100%.

- Original final_score leader: GLD_buy_hold (151.08).
- Drawdown-aware v2 leader: SPY_200d_trend_model (112.21).
- Practical leader after v2: SPY_200d_trend_model.
- Combo/top2 comparison: combo v2 score -117.28 versus top2 102.17; combo risk budget used 90d/180d 0.69/0.81 versus top2 0.76/0.99.
- combo_SPY200d_GLD_50_50_v1 verdict: watchlist; v2 confirms it as the robust practical challenger in this reduced packet.
- asset_class_tsmom_top2_v1 verdict: promotion_review_candidate; it remains a serious challenger/watchlist row, but its target-rate edge does not fully compensate for drawdown-budget usage.
- GLD_buy_hold verdict: high_upside_high_risk; GLD remains high-upside/high-risk.
- SPY_buy_hold verdict: unavailable; SPY buy-hold remains too risky.
- BIL_cash_proxy verdict: benchmark_only; BIL remains defensive benchmark only and too slow for the target ladder.
- SPY_200d_trend_model remains the frozen paper-forward candidate.
- Full 30/60/90/180 candidate_exhaustive is still needed before any promotion or paper-forward decision.
- No real-money recommendation is made.








	

	

	

	

	

	
## Global Multi-Asset ETF Fast Exploration Batch 1

This section reports exactly three fixed predeclared global multi-asset ETF/fund-wrapper candidates. It is research_sample only, uses cache-only Profit Exploration after controlled acquisition/cache QA, does not run candidate_exhaustive, does not alter active paper-forward observations, and does not make a real-money recommendation.

### global_multi_asset_tsmom_top2_v1

- rule summary: Monthly top-2 global ETF/fund wrapper TSMOM across SPY, QQQ, IWM, EFA, EEM, IEF, TLT, GLD, PDBC, and COMT; 126-day positive return filter; unused weight to BIL.
- data source/cache status: local cache only during Profit Exploration; approved symbols were populated or confirmed by the controlled global multi-asset fast acquisition lane
- symbols used: SPY, QQQ, IWM, EFA, EEM, IEF, TLT, GLD, PDBC, COMT, BIL
- target/risk ladder: 30d +300 32.5%, +400 20.0%, +600 2.5%, +900 2.5%, +1200 0.0%, stop 0.0%, median $3,075.53, p95 $3,507.85, worst drawdown $-345.05; 60d +300 25.6%, +400 25.6%, +600 23.1%, +900 0.0%, +1200 0.0%, stop 0.0%, median $3,168.56, p95 $3,434.50, worst drawdown $-472.23; 90d +300 64.1%, +400 30.8%, +600 23.1%, +900 0.0%, +1200 0.0%, stop 0.0%, median $3,208.81, p95 $3,462.39, worst drawdown $-574.12; 180d +300 76.9%, +400 64.1%, +600 53.8%, +900 15.4%, +1200 0.0%, stop 5.1%, median $3,558.26, p95 $3,850.00, worst drawdown $-602.54
- BIL/cash allocation share: 5.7%
- max asset/sleeve concentration: max asset 20.6%; combo sleeve 0.0%
- asset allocation shares: equity 57.1%; international 18.0%; duration 15.5%; real asset 21.7%
- comparison versus combo: multi-asset row beat combo: yes (global_multi_asset_tsmom_top2_v1 $-61.50 vs combo_SPY200d_GLD_50_50_v1 $-117.28).
- comparison versus top2: multi-asset row beat top2: no (global_multi_asset_tsmom_top2_v1 $-61.50 vs asset_class_tsmom_top2_v1 $102.17).
- comparison versus SPY_200d: multi-asset row beat SPY_200d: no (global_multi_asset_tsmom_top2_v1 $-61.50 vs SPY_200d_trend_model $112.21).
- comparison versus GLD: multi-asset row beat GLD: no (global_multi_asset_tsmom_top2_v1 $-61.50 vs GLD_buy_hold $53.62).
- comparison versus commodity base if available: multi-asset row beat commodity base: unavailable.
- comparison versus commodity 80/20 if available: multi-asset row beat commodity 80/20: unavailable.
- comparison versus crypto 90/10 if available: multi-asset row beat crypto 90/10: unavailable.
- verdict: research_sample_candidate_risk_budget_breach
- candidate_exhaustive recommendation: false
- no real-money recommendation

### global_multi_asset_tsmom_top2_defensive_50_v1

- rule summary: 50% global_multi_asset_tsmom_top2_v1 sleeve and 50% BIL, fixed monthly rebalance.
- data source/cache status: local cache only during Profit Exploration; approved symbols were populated or confirmed by the controlled global multi-asset fast acquisition lane
- symbols used: SPY, QQQ, IWM, EFA, EEM, IEF, TLT, GLD, PDBC, COMT, BIL
- target/risk ladder: 30d +300 2.5%, +400 2.5%, +600 0.0%, +900 0.0%, +1200 0.0%, stop 0.0%, median $3,045.24, p95 $3,247.45, worst drawdown $-170.97; 60d +300 17.9%, +400 0.0%, +600 0.0%, +900 0.0%, +1200 0.0%, stop 0.0%, median $3,086.51, p95 $3,218.08, worst drawdown $-216.04; 90d +300 20.5%, +400 2.6%, +600 0.0%, +900 0.0%, +1200 0.0%, stop 0.0%, median $3,110.44, p95 $3,251.81, worst drawdown $-263.29; 180d +300 56.4%, +400 30.8%, +600 0.0%, +900 0.0%, +1200 0.0%, stop 0.0%, median $3,289.56, p95 $3,446.02, worst drawdown $-305.65
- BIL/cash allocation share: 49.4%
- max asset/sleeve concentration: max asset 10.3%; combo sleeve 0.0%
- asset allocation shares: equity 28.6%; international 9.0%; duration 7.7%; real asset 10.8%
- comparison versus combo: multi-asset row beat combo: no (global_multi_asset_tsmom_top2_defensive_50_v1 $-198.76 vs combo_SPY200d_GLD_50_50_v1 $-117.28).
- comparison versus top2: multi-asset row beat top2: no (global_multi_asset_tsmom_top2_defensive_50_v1 $-198.76 vs asset_class_tsmom_top2_v1 $102.17).
- comparison versus SPY_200d: multi-asset row beat SPY_200d: no (global_multi_asset_tsmom_top2_defensive_50_v1 $-198.76 vs SPY_200d_trend_model $112.21).
- comparison versus GLD: multi-asset row beat GLD: no (global_multi_asset_tsmom_top2_defensive_50_v1 $-198.76 vs GLD_buy_hold $53.62).
- comparison versus commodity base if available: multi-asset row beat commodity base: unavailable.
- comparison versus commodity 80/20 if available: multi-asset row beat commodity 80/20: unavailable.
- comparison versus crypto 90/10 if available: multi-asset row beat crypto 90/10: unavailable.
- verdict: watchlist
- candidate_exhaustive recommendation: false
- no real-money recommendation

### combo_plus_global_multi_asset_80_20_v1

- rule summary: 80% historical combo_SPY200d_GLD_50_50_v1 component and 20% global_multi_asset_tsmom_top2_v1 sleeve, fixed monthly rebalance.
- data source/cache status: local cache only during Profit Exploration; approved symbols were populated or confirmed by the controlled global multi-asset fast acquisition lane
- symbols used: SPY, QQQ, IWM, EFA, EEM, IEF, TLT, GLD, PDBC, COMT, BIL
- target/risk ladder: 30d +300 2.5%, +400 0.0%, +600 0.0%, +900 0.0%, +1200 0.0%, stop 0.0%, median $3,040.91, p95 $3,296.82, worst drawdown $-184.63; 60d +300 17.9%, +400 2.6%, +600 0.0%, +900 0.0%, +1200 0.0%, stop 0.0%, median $3,132.24, p95 $3,355.15, worst drawdown $-373.80; 90d +300 30.8%, +400 20.5%, +600 0.0%, +900 0.0%, +1200 0.0%, stop 0.0%, median $3,156.17, p95 $3,406.18, worst drawdown $-420.76; 180d +300 61.5%, +400 51.3%, +600 25.6%, +900 2.6%, +1200 0.0%, stop 0.0%, median $3,360.07, p95 $3,663.20, worst drawdown $-496.60
- BIL/cash allocation share: 10.0%
- max asset/sleeve concentration: max asset 40.6%; combo sleeve 80.0%
- asset allocation shares: equity 39.9%; international 3.6%; duration 3.1%; real asset 42.4%
- comparison versus combo: multi-asset row beat combo: no (combo_plus_global_multi_asset_80_20_v1 $-119.04 vs combo_SPY200d_GLD_50_50_v1 $-117.28).
- comparison versus top2: multi-asset row beat top2: no (combo_plus_global_multi_asset_80_20_v1 $-119.04 vs asset_class_tsmom_top2_v1 $102.17).
- comparison versus SPY_200d: multi-asset row beat SPY_200d: no (combo_plus_global_multi_asset_80_20_v1 $-119.04 vs SPY_200d_trend_model $112.21).
- comparison versus GLD: multi-asset row beat GLD: no (combo_plus_global_multi_asset_80_20_v1 $-119.04 vs GLD_buy_hold $53.62).
- comparison versus commodity base if available: multi-asset row beat commodity base: unavailable.
- comparison versus commodity 80/20 if available: multi-asset row beat commodity 80/20: unavailable.
- comparison versus crypto 90/10 if available: multi-asset row beat crypto 90/10: unavailable.
- verdict: watchlist
- candidate_exhaustive recommendation: false
- no real-money recommendation



	## Candidate Exhaustive Queue

Candidate-exhaustive was not run for this task. The queue below is for later overnight validation only and does not promote any row.

- asset_class_tsmom_top2_v1: reason_for_queue=research_sample accounting-valid row improves diagnostic score versus SPY_200d/combo_SPY200d_GLD_50_50; evidence_tier=tier2_credible_prototype; research_sample_result_summary=+300 25.6%, +400 15.4%, stop 0.0%, median $3,128.73; main_risk=whipsaw, concentration, and possible defensive drag; comparison_target=SPY_200d_trend_model and combo_SPY200d_GLD_50_50_v1; recommended_finalist_set=asset_class_tsmom_top2_v1, SPY_200d_trend_model, combo_SPY200d_GLD_50_50_v1, GLD_buy_hold, BIL_cash_proxy
- SPY_200d_trend_model: reason_for_queue=research_sample accounting-valid row improves diagnostic score versus combo_SPY200d_GLD_50_50; evidence_tier=tier3_candidate_validation; research_sample_result_summary=+300 23.1%, +400 10.3%, stop 0.0%, median $3,098.53; main_risk=equity drawdown and whipsaw; comparison_target=SPY_200d_trend_model and combo_SPY200d_GLD_50_50_v1; recommended_finalist_set=SPY_200d_trend_model, SPY_200d_trend_model, combo_SPY200d_GLD_50_50_v1, GLD_buy_hold, BIL_cash_proxy

## Accounting Integrity Audit

- accounting_integrity_status: passed
- rolling_windows_rebased_to_3000: true
- buy_hold_reference_checks_passed: true
- combination_return_checks_passed: true
- failed_experiments: none
- invalidated_rankings: none
- profit_rankings_decision_usable: true

The previous pre-integrity profit league rankings are treated as invalidated because rolling windows had not yet proven fresh $3,000 rebasing. The current packet rebuilds every rolling window from window-local returns and blocks rankings if accounting integrity fails.

## Current Research Conclusion

SPY_200d_trend_model remains the frozen paper-forward candidate. Profit exploration is a parallel research league only. Any new leading profit candidate requires separate candidate-exhaustive/Tier 2 review before it can affect future research status.

## Next Work

Continue comparing independent experiments by stop-aware profit, not target hits alone. A/B and A-sector rows remain incomplete until exact fresh-window streams are exposed. Blocked instruments remain blocked until gates pass.

No real-money recommendation is made.
