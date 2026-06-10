# Profit Exploration Summary

## Research Boundary

This is research-only paper/demo evidence. It does not recommend real-money trading, does not connect to brokers or exchanges, and does not place orders.

## Run Identity

- run_id: 20260608_053732
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

Completed experiments: GLD_buy_hold, SPY_200d_trend_model, asset_class_tsmom_top2_v1, BIL_cash_proxy, combo_SPY200d_GLD_50_50_v1, combo_plus_crypto_spot_tsmom_90_10_v1, crypto_spot_equal_weight_200d_filter_v1, crypto_spot_tsmom_top1_cash_filter_v1.

Blocked experiments: none.

Incomplete experiments: none.

Duplicate-skipped experiments: none.

Duplicate handling: canonical rule hashes are computed from strategy family, universe, rebalance frequency, lookback, trend filter, cash fallback, selected asset count, weighting rule, execution timing, max gross exposure, and leverage setting. Later duplicate rows are retained for audit visibility but are not counted as independent evidence.

## Target Ladder

- Highest exact +$300 probability: GLD_buy_hold (53.8%)
- Highest exact +$400 probability: GLD_buy_hold (43.6%)
- Highest +$600 probability: GLD_buy_hold (20.5%)
- Highest +$900 probability: GLD_buy_hold (15.4%)
- Highest +$1200 probability: crypto_spot_tsmom_top1_cash_filter_v1 (5.1%)

## Profit And Risk

- Highest median stop-enforced equity: combo_SPY200d_GLD_50_50_v1 ($3,149.59)
- Highest upside tail: GLD_buy_hold ($3,722.49)
- Best risk control: BIL_cash_proxy
- Best overall profit/risk tradeoff: GLD_buy_hold
- Exact best +$300 family/experiment: GLD_buy_hold
- Exact best +$400 family/experiment: GLD_buy_hold

## Combination Review

Combinations improving the diagnostic score versus SPY_200d: none.

High-upside but too-risky rows: GLD_buy_hold.




## Profit Score Audit

The original final_score ranked asset_class_tsmom_top2_v1 above combo_SPY200d_GLD_50_50_v1 because top2 had slightly higher 90-day +300/+400 target rates and lower stress degradation. The combo had better median equity, p95 equity, expected profit, stop behavior, and worst drawdown, but the original drawdown penalty only applies after the -$600 budget is breached. Original final_score: top2 73.6398; combo -56.5558.

Alternative diagnostic score leaders:

- profit_seeking_score leader: GLD_buy_hold (387.65)
- balanced_score leader: asset_class_tsmom_top2_v1 (198.24)
- drawdown_control_score leader: BIL_cash_proxy (353.20)

Score-audit verdict: the original score is usable as a target-ladder diagnostic, but it under-credits drawdown control inside the -$600 risk budget. The balanced and drawdown-control views should be reviewed before treating a narrow final_score edge as decision-dominant.



## Drawdown-Aware Score v2

Score v2 was added because the original final_score only penalized worst drawdown after the -$600 risk budget was breached. V2 penalizes risk-budget usage before the hard stop, so a row using roughly 95% of the drawdown budget is not treated the same as a row using roughly 75%.

V2 differs from the original final_score by combining 90-day and 180-day target/equity rewards with explicit stop, stress, evidence-quality, and drawdown-budget penalties. The drawdown penalty has no penalty up to 50% risk-budget use, moderate penalty from 50-75%, large penalty from 75-100%, and severe penalty above 100%.

- Original final_score leader: GLD_buy_hold (149.58).
- Drawdown-aware v2 leader: SPY_200d_trend_model (126.05).
- Practical leader after v2: SPY_200d_trend_model.
- Combo/top2 comparison: combo v2 score -107.99 versus top2 107.60; combo risk budget used 90d/180d 0.69/0.81 versus top2 0.76/0.99.
- combo_SPY200d_GLD_50_50_v1 verdict: watchlist; v2 confirms it as the robust practical challenger in this reduced packet.
- asset_class_tsmom_top2_v1 verdict: promotion_review_candidate; it remains a serious challenger/watchlist row, but its target-rate edge does not fully compensate for drawdown-budget usage.
- GLD_buy_hold verdict: high_upside_high_risk; GLD remains high-upside/high-risk.
- SPY_buy_hold verdict: unavailable; SPY buy-hold remains too risky.
- BIL_cash_proxy verdict: benchmark_only; BIL remains defensive benchmark only and too slow for the target ladder.
- SPY_200d_trend_model remains the frozen paper-forward candidate.
- Full 30/60/90/180 candidate_exhaustive is still needed before any promotion or paper-forward decision.
- No real-money recommendation is made.








	

	

	

	

	
## Crypto Spot Tier 2 Risk-Control Batch 1

This section reports exactly three fixed predeclared BTC/ETH spot-only risk-control candidates. It is research_sample only, uses cached/public daily data only, does not run candidate_exhaustive, does not alter active paper-forward observations, and does not make a real-money recommendation.

### crypto_spot_tsmom_top1_cash_filter_v1

- rule summary: Monthly BTC/ETH top-1 TSMOM with 126-day positive return and close > 200-day SMA filters; 50% selected spot crypto and 50% BIL; 100% BIL if no crypto qualifies.
- data source/cache status: cached BTC-USD/ETH-USD spot series plus cached BIL; Profit Exploration used `--reuse-cache --no-network`
- symbols used: BTC-USD, ETH-USD, BIL
- target/risk ladder: 30d +300 2.5%, +400 2.5%, +600 2.5%, +900 2.5%, +1200 0.0%, stop 0.0%, median $3,002.98, p95 $3,024.58, worst drawdown $-338.18; 60d +300 5.1%, +400 5.1%, +600 5.1%, +900 5.1%, +1200 2.6%, stop 0.0%, median $3,009.56, p95 $3,282.87, worst drawdown $-511.40; 90d +300 10.3%, +400 7.7%, +600 5.1%, +900 5.1%, +1200 5.1%, stop 7.7%, median $3,013.82, p95 $3,283.38, worst drawdown $-1,265.15; 180d +300 15.4%, +400 12.8%, +600 7.7%, +900 7.7%, +1200 5.1%, stop 28.2%, median $3,006.15, p95 $3,789.42, worst drawdown $-3,302.38
- BIL/cash allocation share: 87.7%
- max crypto exposure: 12.3%; BTC allocation share 6.8%; ETH allocation share 5.5%
- BTC/ETH allocation frequencies: BTC 13.6%; ETH 11.0%
- comparison versus combo: crypto row beat combo: no (crypto_spot_tsmom_top1_cash_filter_v1 $-1,109.47 vs combo_SPY200d_GLD_50_50_v1 $-107.99).
- comparison versus top2: crypto row beat top2: no (crypto_spot_tsmom_top1_cash_filter_v1 $-1,109.47 vs asset_class_tsmom_top2_v1 $107.60).
- comparison versus SPY_200d: crypto row beat SPY_200d: no (crypto_spot_tsmom_top1_cash_filter_v1 $-1,109.47 vs SPY_200d_trend_model $126.05).
- comparison versus GLD: crypto row beat GLD: no (crypto_spot_tsmom_top1_cash_filter_v1 $-1,109.47 vs GLD_buy_hold $53.61).
- verdict: high_upside_high_risk_watchlist
- candidate_exhaustive recommendation: false
- no leverage, margin, shorting, futures, perpetuals, options, broker integration, exchange execution, live orders, or real-money recommendation

### crypto_spot_equal_weight_200d_filter_v1

- rule summary: Monthly BTC/ETH equal-weight eligibility screen; each qualifying asset receives 25%, unused weight goes to BIL, and max crypto exposure is 50%.
- data source/cache status: cached BTC-USD/ETH-USD spot series plus cached BIL; Profit Exploration used `--reuse-cache --no-network`
- symbols used: BTC-USD, ETH-USD, BIL
- target/risk ladder: 30d +300 2.5%, +400 2.5%, +600 2.5%, +900 0.0%, +1200 0.0%, stop 0.0%, median $3,002.98, p95 $3,024.47, worst drawdown $-382.19; 60d +300 7.7%, +400 5.1%, +600 5.1%, +900 2.6%, +1200 0.0%, stop 2.6%, median $3,008.83, p95 $3,208.08, worst drawdown $-663.99; 90d +300 10.3%, +400 10.3%, +600 7.7%, +900 2.6%, +1200 2.6%, stop 5.1%, median $3,013.82, p95 $3,378.01, worst drawdown $-1,041.19; 180d +300 15.4%, +400 12.8%, +600 10.3%, +900 7.7%, +1200 5.1%, stop 28.2%, median $3,007.52, p95 $3,716.46, worst drawdown $-2,444.58
- BIL/cash allocation share: 89.5%
- max crypto exposure: 10.5%; BTC allocation share 5.5%; ETH allocation share 4.9%
- BTC/ETH allocation frequencies: BTC 22.2%; ETH 19.7%
- comparison versus combo: crypto row beat combo: no (crypto_spot_equal_weight_200d_filter_v1 $-891.87 vs combo_SPY200d_GLD_50_50_v1 $-107.99).
- comparison versus top2: crypto row beat top2: no (crypto_spot_equal_weight_200d_filter_v1 $-891.87 vs asset_class_tsmom_top2_v1 $107.60).
- comparison versus SPY_200d: crypto row beat SPY_200d: no (crypto_spot_equal_weight_200d_filter_v1 $-891.87 vs SPY_200d_trend_model $126.05).
- comparison versus GLD: crypto row beat GLD: no (crypto_spot_equal_weight_200d_filter_v1 $-891.87 vs GLD_buy_hold $53.61).
- verdict: high_upside_high_risk_watchlist
- candidate_exhaustive recommendation: false
- no leverage, margin, shorting, futures, perpetuals, options, broker integration, exchange execution, live orders, or real-money recommendation

### combo_plus_crypto_spot_tsmom_90_10_v1

- rule summary: 90% historical combo_SPY200d_GLD_50_50_v1 component and 10% crypto_spot_tsmom_top1_cash_filter_v1, fixed monthly rebalance.
- data source/cache status: cached BTC-USD/ETH-USD spot series plus cached BIL; Profit Exploration used `--reuse-cache --no-network`
- symbols used: BTC-USD, ETH-USD, BIL
- target/risk ladder: 30d +300 0.0%, +400 0.0%, +600 0.0%, +900 0.0%, +1200 0.0%, stop 0.0%, median $3,036.34, p95 $3,220.31, worst drawdown $-234.89; 60d +300 12.8%, +400 2.6%, +600 0.0%, +900 0.0%, +1200 0.0%, stop 0.0%, median $3,122.79, p95 $3,306.28, worst drawdown $-326.16; 90d +300 30.8%, +400 17.9%, +600 0.0%, +900 0.0%, +1200 0.0%, stop 0.0%, median $3,136.87, p95 $3,366.52, worst drawdown $-368.68; 180d +300 61.5%, +400 48.7%, +600 28.2%, +900 0.0%, +1200 0.0%, stop 0.0%, median $3,305.56, p95 $3,764.95, worst drawdown $-419.71
- BIL/cash allocation share: 18.7%
- max crypto exposure: 1.2%; BTC allocation share 0.7%; ETH allocation share 0.6%
- BTC/ETH allocation frequencies: BTC unavailable; ETH unavailable
- comparison versus combo: crypto row beat combo: yes (combo_plus_crypto_spot_tsmom_90_10_v1 $-105.59 vs combo_SPY200d_GLD_50_50_v1 $-107.99).
- comparison versus top2: crypto row beat top2: no (combo_plus_crypto_spot_tsmom_90_10_v1 $-105.59 vs asset_class_tsmom_top2_v1 $107.60).
- comparison versus SPY_200d: crypto row beat SPY_200d: no (combo_plus_crypto_spot_tsmom_90_10_v1 $-105.59 vs SPY_200d_trend_model $126.05).
- comparison versus GLD: crypto row beat GLD: no (combo_plus_crypto_spot_tsmom_90_10_v1 $-105.59 vs GLD_buy_hold $53.61).
- verdict: research_sample_candidate
- candidate_exhaustive recommendation: false
- no leverage, margin, shorting, futures, perpetuals, options, broker integration, exchange execution, live orders, or real-money recommendation



	## Candidate Exhaustive Queue

Candidate-exhaustive was not run for this task. The queue below is for later overnight validation only and does not promote any row.

- SPY_200d_trend_model: reason_for_queue=research_sample accounting-valid row improves diagnostic score versus combo_SPY200d_GLD_50_50; evidence_tier=tier3_candidate_validation; research_sample_result_summary=+300 25.6%, +400 12.8%, stop 0.0%, median $3,107.69; main_risk=equity drawdown and whipsaw; comparison_target=SPY_200d_trend_model and combo_SPY200d_GLD_50_50_v1; recommended_finalist_set=SPY_200d_trend_model, SPY_200d_trend_model, combo_SPY200d_GLD_50_50_v1, GLD_buy_hold, BIL_cash_proxy
- asset_class_tsmom_top2_v1: reason_for_queue=research_sample accounting-valid row improves diagnostic score versus combo_SPY200d_GLD_50_50; evidence_tier=tier2_credible_prototype; research_sample_result_summary=+300 25.6%, +400 12.8%, stop 0.0%, median $3,120.71; main_risk=whipsaw, concentration, and possible defensive drag; comparison_target=SPY_200d_trend_model and combo_SPY200d_GLD_50_50_v1; recommended_finalist_set=asset_class_tsmom_top2_v1, SPY_200d_trend_model, combo_SPY200d_GLD_50_50_v1, GLD_buy_hold, BIL_cash_proxy

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
