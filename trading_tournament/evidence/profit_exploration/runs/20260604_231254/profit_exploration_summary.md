# Profit Exploration Summary

## Research Boundary

This is research-only paper/demo evidence. It does not recommend real-money trading, does not connect to brokers or exchanges, and does not place orders.

## Run Identity

- run_id: 20260604_231254
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

Completed experiments: combo_SPY200d_GLD_50_50_v1, qqq_spy_gld_ief_dual_momentum_v1, asset_class_tsmom_top2_v1, value_momentum_factor_etf_rotation_v1, asset_class_tsmom_equal_weight_v1, IEF_buy_hold, SPY_200d_trend_model, GLD_buy_hold, asset_class_tsmom_top1_v1, SPY_GLD_IEF_dual_momentum_v1, GLD_SPY_rotation_v1, combo_SPY200d_GLD_BIL_60_30_10_v1, multi_asset_top2_momentum_v1, BIL_cash_proxy, SPY_GLD_dual_momentum_v1, IEF_200d_trend_model_v1, GLD_200d_trend_model_v1, SPY_buy_hold.

Blocked experiments: individual_stock_momentum, options_directional, options_premium, futures_trend_following, forex_momentum_carry, intraday_orb, volatility_products, event_news_momentum.

Incomplete experiments: A_ETF_sector_momentum, current_no_cash_proxy_alpha_AB.

Duplicate-skipped experiments: dual_momentum_SPY_GLD_IEF_v1.

Duplicate handling: canonical rule hashes are computed from strategy family, universe, rebalance frequency, lookback, trend filter, cash fallback, selected asset count, weighting rule, execution timing, max gross exposure, and leverage setting. Later duplicate rows are retained for audit visibility but are not counted as independent evidence.

## Target Ladder

- Highest exact +$300 probability: GLD_SPY_rotation_v1 (50.0%)
- Highest exact +$400 probability: qqq_spy_gld_ief_dual_momentum_v1 (42.5%)
- Highest +$600 probability: GLD_buy_hold (15.0%)
- Highest +$900 probability: GLD_buy_hold (15.0%)
- Highest +$1200 probability: combo_SPY200d_GLD_50_50_v1 (0.0%)

## Profit And Risk

- Highest median stop-enforced equity: SPY_buy_hold ($3,133.00)
- Highest upside tail: GLD_buy_hold ($3,716.46)
- Best risk control: IEF_buy_hold
- Best overall profit/risk tradeoff: combo_SPY200d_GLD_50_50_v1
- Exact best +$300 family/experiment: GLD_SPY_rotation_v1
- Exact best +$400 family/experiment: qqq_spy_gld_ief_dual_momentum_v1

## Combination Review

Combinations improving the diagnostic score versus SPY_200d: combo_SPY200d_GLD_50_50_v1.

High-upside but too-risky rows: qqq_spy_gld_ief_dual_momentum_v1, GLD_buy_hold, asset_class_tsmom_top1_v1, SPY_GLD_IEF_dual_momentum_v1, GLD_SPY_rotation_v1, SPY_GLD_dual_momentum_v1, GLD_200d_trend_model_v1, SPY_buy_hold.




## Profit Score Audit

The original final_score ranked asset_class_tsmom_top2_v1 above combo_SPY200d_GLD_50_50_v1 because top2 had slightly higher 90-day +300/+400 target rates and lower stress degradation. The combo had better median equity, p95 equity, expected profit, stop behavior, and worst drawdown, but the original drawdown penalty only applies after the -$600 budget is breached. Original final_score: top2 62.5715; combo 72.5801.

Alternative diagnostic score leaders:

- profit_seeking_score leader: GLD_buy_hold (307.77)
- balanced_score leader: combo_SPY200d_GLD_50_50_v1 (218.41)
- drawdown_control_score leader: BIL_cash_proxy (351.93)

Score-audit verdict: the original score is usable as a target-ladder diagnostic, but it under-credits drawdown control inside the -$600 risk budget. The balanced and drawdown-control views should be reviewed before treating a narrow final_score edge as decision-dominant.



## Drawdown-Aware Score v2

Score v2 was added because the original final_score only penalized worst drawdown after the -$600 risk budget was breached. V2 penalizes risk-budget usage before the hard stop, so a row using roughly 95% of the drawdown budget is not treated the same as a row using roughly 75%.

V2 differs from the original final_score by combining 90-day and 180-day target/equity rewards with explicit stop, stress, evidence-quality, and drawdown-budget penalties. The drawdown penalty has no penalty up to 50% risk-budget use, moderate penalty from 50-75%, large penalty from 75-100%, and severe penalty above 100%.

- Original final_score leader: combo_SPY200d_GLD_50_50_v1 (72.58).
- Drawdown-aware v2 leader: combo_SPY200d_GLD_50_50_v1 (141.13).
- Practical leader after v2: combo_SPY200d_GLD_50_50_v1.
- Combo/top2 comparison: combo v2 score 141.13 versus top2 54.36; combo risk budget used 90d/180d 0.70/0.81 versus top2 0.90/0.99.
- combo_SPY200d_GLD_50_50_v1 verdict: practical_leader; v2 confirms it as the robust practical challenger in this reduced packet.
- asset_class_tsmom_top2_v1 verdict: promotion_review_candidate; it remains a serious challenger/watchlist row, but its target-rate edge does not fully compensate for drawdown-budget usage.
- GLD_buy_hold verdict: high_upside_high_risk; GLD remains high-upside/high-risk.
- SPY_buy_hold verdict: too_risky; SPY buy-hold remains too risky.
- BIL_cash_proxy verdict: benchmark_only; BIL remains defensive benchmark only and too slow for the target ladder.
- SPY_200d_trend_model remains the frozen paper-forward candidate.
- Full 30/60/90/180 candidate_exhaustive is still needed before any promotion or paper-forward decision.
- No real-money recommendation is made.



## QQQ Dual Momentum Research Sample

This row is research_sample only. It is not candidate-exhaustive, not validated, not paper-forward active, and not a real-money recommendation.

1. QQQ data available from cache: true.
2. Data downloaded: false. The run used existing local cache only.
3. Rule: monthly rebalance; rank QQQ, SPY, GLD, and IEF by 126-trading-day return; hold the top 1 asset only if return is positive and close is above its 200-day SMA; otherwise hold BIL. Weights become effective on the next trading day after the signal.
4. QQQ selected: 45.9%.
5. SPY selected: 10.7%.
6. GLD/IEF/BIL selected: GLD 29.3%; IEF 6.8%; BIL 7.3%.
7. QQQ +300/+400 target rates: see target ladder below; compare against top2/combo/SPY_200d in the direct comparisons.
8. QQQ +600/+900/+1200 upside: see target ladder below.
9. QQQ drawdown/stop risk: see stop/worst-drawdown rows below; concentration_warning=false.
10. Equity beta interpretation: QQQ did not trip the equity-beta duplicate warning in this research_sample packet. Equity allocation share=56.6%; defensive allocation share=43.4%.
11. QQQ versus asset_class_tsmom_top2_v1:
  - QQQ beat top2 on original final_score: yes (qqq_spy_gld_ief_dual_momentum_v1 65.2665 vs asset_class_tsmom_top2_v1 62.5715).
  - QQQ beat top2 on drawdown-aware v2 score: no (qqq_spy_gld_ief_dual_momentum_v1 $-80.32 vs asset_class_tsmom_top2_v1 $54.36).
  - QQQ beat top2 on 90d +300: yes (qqq_spy_gld_ief_dual_momentum_v1 47.5% vs asset_class_tsmom_top2_v1 20.0%).
  - QQQ beat top2 on 90d +400: yes (qqq_spy_gld_ief_dual_momentum_v1 42.5% vs asset_class_tsmom_top2_v1 12.5%).
  - QQQ beat top2 on 90d worst drawdown: no (qqq_spy_gld_ief_dual_momentum_v1 $-678.34 vs asset_class_tsmom_top2_v1 $-539.08).
12. QQQ versus combo_SPY200d_GLD_50_50_v1:
  - QQQ beat combo on original final_score: no (qqq_spy_gld_ief_dual_momentum_v1 65.2665 vs combo_SPY200d_GLD_50_50_v1 72.5801).
  - QQQ beat combo on drawdown-aware v2 score: no (qqq_spy_gld_ief_dual_momentum_v1 $-80.32 vs combo_SPY200d_GLD_50_50_v1 $141.13).
  - QQQ beat combo on 90d +300: yes (qqq_spy_gld_ief_dual_momentum_v1 47.5% vs combo_SPY200d_GLD_50_50_v1 22.5%).
  - QQQ beat combo on 90d +400: yes (qqq_spy_gld_ief_dual_momentum_v1 42.5% vs combo_SPY200d_GLD_50_50_v1 15.0%).
  - QQQ beat combo on 90d worst drawdown: no (qqq_spy_gld_ief_dual_momentum_v1 $-678.34 vs combo_SPY200d_GLD_50_50_v1 $-419.15).
13. QQQ versus SPY_200d_trend_model:
  - QQQ beat SPY_200d on original final_score: yes (qqq_spy_gld_ief_dual_momentum_v1 65.2665 vs SPY_200d_trend_model 48.0222).
  - QQQ beat SPY_200d on drawdown-aware v2 score: no (qqq_spy_gld_ief_dual_momentum_v1 $-80.32 vs SPY_200d_trend_model $-52.16).
  - QQQ beat SPY_200d on 90d +300: yes (qqq_spy_gld_ief_dual_momentum_v1 47.5% vs SPY_200d_trend_model 20.0%).
  - QQQ beat SPY_200d on 90d +400: yes (qqq_spy_gld_ief_dual_momentum_v1 42.5% vs SPY_200d_trend_model 5.0%).
  - QQQ beat SPY_200d on 90d worst drawdown: no (qqq_spy_gld_ief_dual_momentum_v1 $-678.34 vs SPY_200d_trend_model $-567.45).
14. Future candidate_exhaustive deserved: false. Current verdict: too_risky.
15. No real-money recommendation is made.

QQQ target/risk ladder:

- 30d: +300 10.0%; +400 0.0%; +600 0.0%; +900 0.0%; +1200 0.0%; stop 0.0%; median $3,033.66; p95 $3,325.96; worst drawdown $-584.49
- 60d: +300 25.0%; +400 15.0%; +600 0.0%; +900 0.0%; +1200 0.0%; stop 2.5%; median $3,029.08; p95 $3,323.72; worst drawdown $-612.15
- 90d: +300 47.5%; +400 42.5%; +600 2.5%; +900 0.0%; +1200 0.0%; stop 17.5%; median $3,118.19; p95 $3,366.23; worst drawdown $-678.34
- 180d: +300 67.5%; +400 62.5%; +600 40.0%; +900 20.0%; +1200 2.5%; stop 30.0%; median $3,457.79; p95 $3,667.37; worst drawdown $-815.89



## Value/Momentum Factor ETF Rotation Research Sample

This row is research_sample only. It is not candidate-exhaustive, not validated, not paper-forward active, and not a real-money recommendation.

1. Data available from cache: true. Cached implementation universe: MTUM, VTV, QUAL, USMV, SPY, BIL.
2. Data downloaded: false. The run used existing local cache only.
3. Rule: monthly rebalance; rank MTUM, VTV, QUAL, USMV, and SPY by 126-trading-day return; assets qualify only when return is positive and close is above the 200-day SMA; hold up to the top 2 qualifying assets at 50% each; unused weight goes to BIL; weights become effective on the next trading day after the signal.
4. Selection/allocation frequencies: MTUM selected 30.8% / allocation 15.4%; VTV selected 35.9% / allocation 18.0%; QUAL selected 20.6% / allocation 10.3%; USMV selected 19.8% / allocation 9.9%; SPY selected 44.7% / allocation 22.3%; BIL fallback 27.1% / allocation 24.1%.
5. +300/+400 target-rate improvement: see target ladder and direct comparisons below.
6. +600/+900/+1200 upside: see target ladder below.
7. Drawdown/stop risk: see stop and worst-drawdown rows below; concentration_warning=false.
8. Equity-beta duplication: The row tripped the equity-beta duplicate warning because equity-factor ETF exposure dominated allocations. Equity-factor allocation share=75.9%; cash/Treasury allocation share=24.1%.
9. Value/momentum versus combo_SPY200d_GLD_50_50_v1:
  - Value/momentum beat combo on drawdown-aware v2 score: no (value_momentum_factor_etf_rotation_v1 $22.55 vs combo_SPY200d_GLD_50_50_v1 $141.13).
  - Value/momentum beat combo on original final_score: no (value_momentum_factor_etf_rotation_v1 59.1912 vs combo_SPY200d_GLD_50_50_v1 72.5801).
  - Value/momentum beat combo on 90d +300: no (value_momentum_factor_etf_rotation_v1 17.5% vs combo_SPY200d_GLD_50_50_v1 22.5%).
  - Value/momentum beat combo on 90d +400: no (value_momentum_factor_etf_rotation_v1 12.5% vs combo_SPY200d_GLD_50_50_v1 15.0%).
  - Value/momentum beat combo on 90d stop-hit rate: no (value_momentum_factor_etf_rotation_v1 0.0% vs combo_SPY200d_GLD_50_50_v1 0.0%).
  - Value/momentum beat combo on 90d worst drawdown: yes (value_momentum_factor_etf_rotation_v1 $-407.74 vs combo_SPY200d_GLD_50_50_v1 $-419.15).
10. Value/momentum versus asset_class_tsmom_top2_v1:
  - Value/momentum beat top2 on drawdown-aware v2 score: no (value_momentum_factor_etf_rotation_v1 $22.55 vs asset_class_tsmom_top2_v1 $54.36).
  - Value/momentum beat top2 on original final_score: no (value_momentum_factor_etf_rotation_v1 59.1912 vs asset_class_tsmom_top2_v1 62.5715).
  - Value/momentum beat top2 on 90d +300: no (value_momentum_factor_etf_rotation_v1 17.5% vs asset_class_tsmom_top2_v1 20.0%).
  - Value/momentum beat top2 on 90d +400: no (value_momentum_factor_etf_rotation_v1 12.5% vs asset_class_tsmom_top2_v1 12.5%).
  - Value/momentum beat top2 on 90d stop-hit rate: no (value_momentum_factor_etf_rotation_v1 0.0% vs asset_class_tsmom_top2_v1 0.0%).
  - Value/momentum beat top2 on 90d worst drawdown: yes (value_momentum_factor_etf_rotation_v1 $-407.74 vs asset_class_tsmom_top2_v1 $-539.08).
11. Value/momentum versus SPY_200d_trend_model:
  - Value/momentum beat SPY_200d on drawdown-aware v2 score: yes (value_momentum_factor_etf_rotation_v1 $22.55 vs SPY_200d_trend_model $-52.16).
  - Value/momentum beat SPY_200d on original final_score: yes (value_momentum_factor_etf_rotation_v1 59.1912 vs SPY_200d_trend_model 48.0222).
  - Value/momentum beat SPY_200d on 90d +300: no (value_momentum_factor_etf_rotation_v1 17.5% vs SPY_200d_trend_model 20.0%).
  - Value/momentum beat SPY_200d on 90d +400: yes (value_momentum_factor_etf_rotation_v1 12.5% vs SPY_200d_trend_model 5.0%).
  - Value/momentum beat SPY_200d on 90d stop-hit rate: no (value_momentum_factor_etf_rotation_v1 0.0% vs SPY_200d_trend_model 0.0%).
  - Value/momentum beat SPY_200d on 90d worst drawdown: yes (value_momentum_factor_etf_rotation_v1 $-407.74 vs SPY_200d_trend_model $-567.45).
12. Value/momentum versus QQQ dual momentum on stop-aware risk:
  - Value/momentum beat QQQ dual momentum on drawdown-aware v2 score: yes (value_momentum_factor_etf_rotation_v1 $22.55 vs qqq_spy_gld_ief_dual_momentum_v1 $-80.32).
  - Value/momentum beat QQQ dual momentum on original final_score: no (value_momentum_factor_etf_rotation_v1 59.1912 vs qqq_spy_gld_ief_dual_momentum_v1 65.2665).
  - Value/momentum beat QQQ dual momentum on 90d +300: no (value_momentum_factor_etf_rotation_v1 17.5% vs qqq_spy_gld_ief_dual_momentum_v1 47.5%).
  - Value/momentum beat QQQ dual momentum on 90d +400: no (value_momentum_factor_etf_rotation_v1 12.5% vs qqq_spy_gld_ief_dual_momentum_v1 42.5%).
  - Value/momentum beat QQQ dual momentum on 90d stop-hit rate: yes (value_momentum_factor_etf_rotation_v1 0.0% vs qqq_spy_gld_ief_dual_momentum_v1 17.5%).
  - Value/momentum beat QQQ dual momentum on 90d worst drawdown: yes (value_momentum_factor_etf_rotation_v1 $-407.74 vs qqq_spy_gld_ief_dual_momentum_v1 $-678.34).
13. Future candidate_exhaustive deserved: true. Current verdict: too_risky.
14. No real-money recommendation is made.

Value/momentum target/risk ladder:

- 30d: +300 0.0%; +400 0.0%; +600 0.0%; +900 0.0%; +1200 0.0%; stop 0.0%; median $3,048.78; p95 $3,221.96; worst drawdown $-350.50
- 60d: +300 5.0%; +400 0.0%; +600 0.0%; +900 0.0%; +1200 0.0%; stop 0.0%; median $3,018.19; p95 $3,274.63; worst drawdown $-378.49
- 90d: +300 17.5%; +400 12.5%; +600 0.0%; +900 0.0%; +1200 0.0%; stop 0.0%; median $3,072.93; p95 $3,315.19; worst drawdown $-407.74
- 180d: +300 47.5%; +400 27.5%; +600 2.5%; +900 0.0%; +1200 0.0%; stop 5.0%; median $3,249.98; p95 $3,467.96; worst drawdown $-605.16


## Candidate Exhaustive Queue

Candidate-exhaustive was not run for this task. The queue below is for later overnight validation only and does not promote any row.

- combo_SPY200d_GLD_50_50_v1: reason_for_queue=research_sample accounting-valid row improves diagnostic score versus SPY_200d; evidence_tier=tier2_credible_prototype; research_sample_result_summary=+300 22.5%, +400 15.0%, stop 0.0%, median $3,077.57; main_risk=combination may dilute upside or inherit GLD drawdown; comparison_target=SPY_200d_trend_model and combo_SPY200d_GLD_50_50_v1; recommended_finalist_set=combo_SPY200d_GLD_50_50_v1, SPY_200d_trend_model, combo_SPY200d_GLD_50_50_v1, GLD_buy_hold, BIL_cash_proxy
- asset_class_tsmom_top2_v1: reason_for_queue=research_sample accounting-valid row improves diagnostic score versus SPY_200d; evidence_tier=tier2_credible_prototype; research_sample_result_summary=+300 20.0%, +400 12.5%, stop 0.0%, median $3,097.46; main_risk=whipsaw, concentration, and possible defensive drag; comparison_target=SPY_200d_trend_model and combo_SPY200d_GLD_50_50_v1; recommended_finalist_set=asset_class_tsmom_top2_v1, SPY_200d_trend_model, combo_SPY200d_GLD_50_50_v1, GLD_buy_hold, BIL_cash_proxy
- value_momentum_factor_etf_rotation_v1: reason_for_queue=research_sample accounting-valid row improves diagnostic score versus SPY_200d; evidence_tier=tier2_credible_prototype; research_sample_result_summary=+300 17.5%, +400 12.5%, stop 0.0%, median $3,072.93; main_risk=U.S. equity beta duplication, factor proxy mismatch, one-ETF concentration, and 2013-onward inception/history limits; comparison_target=SPY_200d_trend_model and combo_SPY200d_GLD_50_50_v1; recommended_finalist_set=value_momentum_factor_etf_rotation_v1, SPY_200d_trend_model, combo_SPY200d_GLD_50_50_v1, GLD_buy_hold, BIL_cash_proxy
- asset_class_tsmom_equal_weight_v1: reason_for_queue=research_sample accounting-valid row improves diagnostic score versus SPY_200d; evidence_tier=tier2_credible_prototype; research_sample_result_summary=+300 17.5%, +400 12.5%, stop 0.0%, median $3,089.11; main_risk=diluted upside, regime whipsaw, and defensive drag; comparison_target=SPY_200d_trend_model and combo_SPY200d_GLD_50_50_v1; recommended_finalist_set=asset_class_tsmom_equal_weight_v1, SPY_200d_trend_model, combo_SPY200d_GLD_50_50_v1, GLD_buy_hold, BIL_cash_proxy

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
