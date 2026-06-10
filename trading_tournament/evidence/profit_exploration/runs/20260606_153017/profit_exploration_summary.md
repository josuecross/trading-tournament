# Profit Exploration Summary

## Research Boundary

This is research-only paper/demo evidence. It does not recommend real-money trading, does not connect to brokers or exchanges, and does not place orders.

## Run Identity

- run_id: 20260606_153017
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

Completed experiments: qqq_spy_gld_ief_dual_momentum_v1, combo_plus_managed_futures_80_20_v1, asset_class_tsmom_top2_v1, value_momentum_factor_etf_rotation_v1, asset_class_tsmom_equal_weight_v1, top2_plus_managed_futures_80_20_v1, combo_plus_top2_50_50_v1, SPY_200d_trend_model, managed_futures_proxy_etf_trend_v1, GLD_buy_hold, sector_top2_momentum_simple_v1, BIL_cash_proxy, combo_SPY200d_GLD_50_50_v1, SPY_buy_hold.

Blocked experiments: none.

Incomplete experiments: none.

Duplicate-skipped experiments: none.

Duplicate handling: canonical rule hashes are computed from strategy family, universe, rebalance frequency, lookback, trend filter, cash fallback, selected asset count, weighting rule, execution timing, max gross exposure, and leverage setting. Later duplicate rows are retained for audit visibility but are not counted as independent evidence.

## Target Ladder

- Highest exact +$300 probability: qqq_spy_gld_ief_dual_momentum_v1 (47.5%)
- Highest exact +$400 probability: qqq_spy_gld_ief_dual_momentum_v1 (42.5%)
- Highest +$600 probability: GLD_buy_hold (15.0%)
- Highest +$900 probability: GLD_buy_hold (15.0%)
- Highest +$1200 probability: qqq_spy_gld_ief_dual_momentum_v1 (0.0%)

## Profit And Risk

- Highest median stop-enforced equity: combo_plus_managed_futures_80_20_v1 ($3,155.59)
- Highest upside tail: GLD_buy_hold ($3,716.46)
- Best risk control: BIL_cash_proxy
- Best overall profit/risk tradeoff: qqq_spy_gld_ief_dual_momentum_v1
- Exact best +$300 family/experiment: qqq_spy_gld_ief_dual_momentum_v1
- Exact best +$400 family/experiment: qqq_spy_gld_ief_dual_momentum_v1

## Combination Review

Combinations improving the diagnostic score versus SPY_200d: combo_plus_managed_futures_80_20_v1, combo_plus_top2_50_50_v1.

High-upside but too-risky rows: qqq_spy_gld_ief_dual_momentum_v1, GLD_buy_hold, SPY_buy_hold.




## Profit Score Audit

The original final_score ranked asset_class_tsmom_top2_v1 above combo_SPY200d_GLD_50_50_v1 because top2 had slightly higher 90-day +300/+400 target rates and lower stress degradation. The combo had better median equity, p95 equity, expected profit, stop behavior, and worst drawdown, but the original drawdown penalty only applies after the -$600 budget is breached. Original final_score: top2 62.5787; combo -73.5256.

Alternative diagnostic score leaders:

- profit_seeking_score leader: GLD_buy_hold (307.77)
- balanced_score leader: combo_plus_managed_futures_80_20_v1 (266.23)
- drawdown_control_score leader: BIL_cash_proxy (352.42)

Score-audit verdict: the original score is usable as a target-ladder diagnostic, but it under-credits drawdown control inside the -$600 risk budget. The balanced and drawdown-control views should be reviewed before treating a narrow final_score edge as decision-dominant.



## Drawdown-Aware Score v2

Score v2 was added because the original final_score only penalized worst drawdown after the -$600 risk budget was breached. V2 penalizes risk-budget usage before the hard stop, so a row using roughly 95% of the drawdown budget is not treated the same as a row using roughly 75%.

V2 differs from the original final_score by combining 90-day and 180-day target/equity rewards with explicit stop, stress, evidence-quality, and drawdown-budget penalties. The drawdown penalty has no penalty up to 50% risk-budget use, moderate penalty from 50-75%, large penalty from 75-100%, and severe penalty above 100%.

- Original final_score leader: qqq_spy_gld_ief_dual_momentum_v1 (65.27).
- Drawdown-aware v2 leader: combo_plus_managed_futures_80_20_v1 (218.54).
- Practical leader after v2: asset_class_tsmom_top2_v1.
- Combo/top2 comparison: combo v2 score -132.92 versus top2 54.37; combo risk budget used 90d/180d 0.70/0.81 versus top2 0.90/0.99.
- combo_SPY200d_GLD_50_50_v1 verdict: watchlist; v2 confirms it as the robust practical challenger in this reduced packet.
- asset_class_tsmom_top2_v1 verdict: practical_leader; it remains a serious challenger/watchlist row, but its target-rate edge does not fully compensate for drawdown-budget usage.
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
  - QQQ beat top2 on original final_score: yes (qqq_spy_gld_ief_dual_momentum_v1 65.2672 vs asset_class_tsmom_top2_v1 62.5787).
  - QQQ beat top2 on drawdown-aware v2 score: no (qqq_spy_gld_ief_dual_momentum_v1 $-80.32 vs asset_class_tsmom_top2_v1 $54.37).
  - QQQ beat top2 on 90d +300: yes (qqq_spy_gld_ief_dual_momentum_v1 47.5% vs asset_class_tsmom_top2_v1 20.0%).
  - QQQ beat top2 on 90d +400: yes (qqq_spy_gld_ief_dual_momentum_v1 42.5% vs asset_class_tsmom_top2_v1 12.5%).
  - QQQ beat top2 on 90d worst drawdown: no (qqq_spy_gld_ief_dual_momentum_v1 $-678.34 vs asset_class_tsmom_top2_v1 $-539.08).
12. QQQ versus combo_SPY200d_GLD_50_50_v1:
  - QQQ beat combo on original final_score: yes (qqq_spy_gld_ief_dual_momentum_v1 65.2672 vs combo_SPY200d_GLD_50_50_v1 -73.5256).
  - QQQ beat combo on drawdown-aware v2 score: yes (qqq_spy_gld_ief_dual_momentum_v1 $-80.32 vs combo_SPY200d_GLD_50_50_v1 $-132.92).
  - QQQ beat combo on 90d +300: yes (qqq_spy_gld_ief_dual_momentum_v1 47.5% vs combo_SPY200d_GLD_50_50_v1 22.5%).
  - QQQ beat combo on 90d +400: yes (qqq_spy_gld_ief_dual_momentum_v1 42.5% vs combo_SPY200d_GLD_50_50_v1 15.0%).
  - QQQ beat combo on 90d worst drawdown: no (qqq_spy_gld_ief_dual_momentum_v1 $-678.34 vs combo_SPY200d_GLD_50_50_v1 $-418.84).
13. QQQ versus SPY_200d_trend_model:
  - QQQ beat SPY_200d on original final_score: yes (qqq_spy_gld_ief_dual_momentum_v1 65.2672 vs SPY_200d_trend_model 48.8964).
  - QQQ beat SPY_200d on drawdown-aware v2 score: no (qqq_spy_gld_ief_dual_momentum_v1 $-80.32 vs SPY_200d_trend_model $-69.66).
  - QQQ beat SPY_200d on 90d +300: yes (qqq_spy_gld_ief_dual_momentum_v1 47.5% vs SPY_200d_trend_model 20.0%).
  - QQQ beat SPY_200d on 90d +400: yes (qqq_spy_gld_ief_dual_momentum_v1 42.5% vs SPY_200d_trend_model 5.0%).
  - QQQ beat SPY_200d on 90d worst drawdown: no (qqq_spy_gld_ief_dual_momentum_v1 $-678.34 vs SPY_200d_trend_model $-590.69).
14. Future candidate_exhaustive deserved: false. Current verdict: too_risky.
15. No real-money recommendation is made.

QQQ target/risk ladder:

- 30d: +300 10.0%; +400 0.0%; +600 0.0%; +900 0.0%; +1200 0.0%; stop 0.0%; median $3,033.66; p95 $3,325.96; worst drawdown $-584.49
- 60d: +300 25.0%; +400 15.0%; +600 0.0%; +900 0.0%; +1200 0.0%; stop 2.5%; median $3,029.08; p95 $3,323.72; worst drawdown $-612.15
- 90d: +300 47.5%; +400 42.5%; +600 2.5%; +900 0.0%; +1200 0.0%; stop 17.5%; median $3,118.19; p95 $3,366.22; worst drawdown $-678.34
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
  - Value/momentum beat combo on drawdown-aware v2 score: yes (value_momentum_factor_etf_rotation_v1 $24.59 vs combo_SPY200d_GLD_50_50_v1 $-132.92).
  - Value/momentum beat combo on original final_score: yes (value_momentum_factor_etf_rotation_v1 59.2206 vs combo_SPY200d_GLD_50_50_v1 -73.5256).
  - Value/momentum beat combo on 90d +300: no (value_momentum_factor_etf_rotation_v1 17.5% vs combo_SPY200d_GLD_50_50_v1 22.5%).
  - Value/momentum beat combo on 90d +400: no (value_momentum_factor_etf_rotation_v1 12.5% vs combo_SPY200d_GLD_50_50_v1 15.0%).
  - Value/momentum beat combo on 90d stop-hit rate: no (value_momentum_factor_etf_rotation_v1 0.0% vs combo_SPY200d_GLD_50_50_v1 0.0%).
  - Value/momentum beat combo on 90d worst drawdown: yes (value_momentum_factor_etf_rotation_v1 $-407.75 vs combo_SPY200d_GLD_50_50_v1 $-418.84).
10. Value/momentum versus asset_class_tsmom_top2_v1:
  - Value/momentum beat top2 on drawdown-aware v2 score: no (value_momentum_factor_etf_rotation_v1 $24.59 vs asset_class_tsmom_top2_v1 $54.37).
  - Value/momentum beat top2 on original final_score: no (value_momentum_factor_etf_rotation_v1 59.2206 vs asset_class_tsmom_top2_v1 62.5787).
  - Value/momentum beat top2 on 90d +300: no (value_momentum_factor_etf_rotation_v1 17.5% vs asset_class_tsmom_top2_v1 20.0%).
  - Value/momentum beat top2 on 90d +400: no (value_momentum_factor_etf_rotation_v1 12.5% vs asset_class_tsmom_top2_v1 12.5%).
  - Value/momentum beat top2 on 90d stop-hit rate: no (value_momentum_factor_etf_rotation_v1 0.0% vs asset_class_tsmom_top2_v1 0.0%).
  - Value/momentum beat top2 on 90d worst drawdown: yes (value_momentum_factor_etf_rotation_v1 $-407.75 vs asset_class_tsmom_top2_v1 $-539.08).
11. Value/momentum versus SPY_200d_trend_model:
  - Value/momentum beat SPY_200d on drawdown-aware v2 score: yes (value_momentum_factor_etf_rotation_v1 $24.59 vs SPY_200d_trend_model $-69.66).
  - Value/momentum beat SPY_200d on original final_score: yes (value_momentum_factor_etf_rotation_v1 59.2206 vs SPY_200d_trend_model 48.8964).
  - Value/momentum beat SPY_200d on 90d +300: no (value_momentum_factor_etf_rotation_v1 17.5% vs SPY_200d_trend_model 20.0%).
  - Value/momentum beat SPY_200d on 90d +400: yes (value_momentum_factor_etf_rotation_v1 12.5% vs SPY_200d_trend_model 5.0%).
  - Value/momentum beat SPY_200d on 90d stop-hit rate: no (value_momentum_factor_etf_rotation_v1 0.0% vs SPY_200d_trend_model 0.0%).
  - Value/momentum beat SPY_200d on 90d worst drawdown: yes (value_momentum_factor_etf_rotation_v1 $-407.75 vs SPY_200d_trend_model $-590.69).
12. Value/momentum versus QQQ dual momentum on stop-aware risk:
  - Value/momentum beat QQQ dual momentum on drawdown-aware v2 score: yes (value_momentum_factor_etf_rotation_v1 $24.59 vs qqq_spy_gld_ief_dual_momentum_v1 $-80.32).
  - Value/momentum beat QQQ dual momentum on original final_score: no (value_momentum_factor_etf_rotation_v1 59.2206 vs qqq_spy_gld_ief_dual_momentum_v1 65.2672).
  - Value/momentum beat QQQ dual momentum on 90d +300: no (value_momentum_factor_etf_rotation_v1 17.5% vs qqq_spy_gld_ief_dual_momentum_v1 47.5%).
  - Value/momentum beat QQQ dual momentum on 90d +400: no (value_momentum_factor_etf_rotation_v1 12.5% vs qqq_spy_gld_ief_dual_momentum_v1 42.5%).
  - Value/momentum beat QQQ dual momentum on 90d stop-hit rate: yes (value_momentum_factor_etf_rotation_v1 0.0% vs qqq_spy_gld_ief_dual_momentum_v1 17.5%).
  - Value/momentum beat QQQ dual momentum on 90d worst drawdown: yes (value_momentum_factor_etf_rotation_v1 $-407.75 vs qqq_spy_gld_ief_dual_momentum_v1 $-678.34).
13. Future candidate_exhaustive deserved: false. Current verdict: too_risky.
14. No real-money recommendation is made.

Value/momentum target/risk ladder:

- 30d: +300 0.0%; +400 0.0%; +600 0.0%; +900 0.0%; +1200 0.0%; stop 0.0%; median $3,048.78; p95 $3,226.74; worst drawdown $-350.50
- 60d: +300 5.0%; +400 0.0%; +600 0.0%; +900 0.0%; +1200 0.0%; stop 0.0%; median $3,024.44; p95 $3,274.63; worst drawdown $-378.49
- 90d: +300 17.5%; +400 12.5%; +600 0.0%; +900 0.0%; +1200 0.0%; stop 0.0%; median $3,072.93; p95 $3,315.19; worst drawdown $-407.75
- 180d: +300 50.0%; +400 27.5%; +600 2.5%; +900 0.0%; +1200 0.0%; stop 5.0%; median $3,257.16; p95 $3,467.70; worst drawdown $-605.16



## Sector Top-2 Momentum Research Sample

This row is research_sample only. It is not candidate-exhaustive, not validated, not paper-forward active, and not a real-money recommendation.

1. Data available from cache: true. Cached implementation universe: XLB, XLE, XLF, XLI, XLK, XLP, XLU, XLV, XLY, BIL.
2. Data downloaded: false. The run used existing local cache only.
3. Universe used: core_nine_fixed_universe = XLB, XLE, XLF, XLI, XLK, XLP, XLU, XLV, XLY, with BIL fallback.
4. XLC and XLRE excluded: true. XLC is excluded for late-inception risk; XLRE is excluded because it is not cached.
5. Rule: monthly rebalance; rank core-nine sector ETFs by 126-trading-day return; a sector qualifies only when 126-day return is positive and close is above the 200-day SMA; hold up to the top 2 qualifying sectors at 50% each; unused weight goes to BIL; if no sector qualifies, hold 100% BIL; weights become effective on the next trading day after the signal.
6. Sector selection/allocation frequencies: XLB selected 10.7% / allocation 5.3%; XLE selected 24.8% / allocation 12.4%; XLF selected 22.0% / allocation 11.0%; XLI selected 12.1% / allocation 6.1%; XLK selected 31.5% / allocation 15.8%; XLP selected 13.4% / allocation 6.7%; XLU selected 20.5% / allocation 10.3%; XLV selected 18.8% / allocation 9.4%; XLY selected 24.6% / allocation 12.3%.
7. BIL fallback/allocation frequency: BIL selected 12.1% / allocation 10.8%.
8. +300/+400 target-rate improvement: see target ladder and direct comparisons below.
9. +600/+900/+1200 upside: see target ladder below.
10. Drawdown/stop risk: see stop and worst-drawdown rows below; concentration_warning=false.
11. Equity-beta duplication: The row tripped the equity-beta duplicate warning because core sector exposure dominated allocations. Equity-sector allocation share=89.2%; cash/Treasury allocation share=10.8%.
12. Sector dominance: max_single_sector_allocation=15.8%; top_sector_dominance=15.8%; sector_turnover=3.5%.
13. Sector top2 versus combo_SPY200d_GLD_50_50_v1:
  - Sector top2 beat combo on drawdown-aware v2 score: yes (sector_top2_momentum_simple_v1 $-98.02 vs combo_SPY200d_GLD_50_50_v1 $-132.92).
  - Sector top2 beat combo on original final_score: yes (sector_top2_momentum_simple_v1 32.1197 vs combo_SPY200d_GLD_50_50_v1 -73.5256).
  - Sector top2 beat combo on 90d +300: no (sector_top2_momentum_simple_v1 12.5% vs combo_SPY200d_GLD_50_50_v1 22.5%).
  - Sector top2 beat combo on 90d +400: no (sector_top2_momentum_simple_v1 2.5% vs combo_SPY200d_GLD_50_50_v1 15.0%).
  - Sector top2 beat combo on 90d stop-hit rate: no (sector_top2_momentum_simple_v1 2.5% vs combo_SPY200d_GLD_50_50_v1 0.0%).
  - Sector top2 beat combo on 90d worst drawdown: no (sector_top2_momentum_simple_v1 $-604.74 vs combo_SPY200d_GLD_50_50_v1 $-418.84).
14. Sector top2 versus asset_class_tsmom_top2_v1:
  - Sector top2 beat top2 on drawdown-aware v2 score: no (sector_top2_momentum_simple_v1 $-98.02 vs asset_class_tsmom_top2_v1 $54.37).
  - Sector top2 beat top2 on original final_score: no (sector_top2_momentum_simple_v1 32.1197 vs asset_class_tsmom_top2_v1 62.5787).
  - Sector top2 beat top2 on 90d +300: no (sector_top2_momentum_simple_v1 12.5% vs asset_class_tsmom_top2_v1 20.0%).
  - Sector top2 beat top2 on 90d +400: no (sector_top2_momentum_simple_v1 2.5% vs asset_class_tsmom_top2_v1 12.5%).
  - Sector top2 beat top2 on 90d stop-hit rate: no (sector_top2_momentum_simple_v1 2.5% vs asset_class_tsmom_top2_v1 0.0%).
  - Sector top2 beat top2 on 90d worst drawdown: no (sector_top2_momentum_simple_v1 $-604.74 vs asset_class_tsmom_top2_v1 $-539.08).
15. Sector top2 versus SPY_200d_trend_model:
  - Sector top2 beat SPY_200d on drawdown-aware v2 score: no (sector_top2_momentum_simple_v1 $-98.02 vs SPY_200d_trend_model $-69.66).
  - Sector top2 beat SPY_200d on original final_score: no (sector_top2_momentum_simple_v1 32.1197 vs SPY_200d_trend_model 48.8964).
  - Sector top2 beat SPY_200d on 90d +300: no (sector_top2_momentum_simple_v1 12.5% vs SPY_200d_trend_model 20.0%).
  - Sector top2 beat SPY_200d on 90d +400: no (sector_top2_momentum_simple_v1 2.5% vs SPY_200d_trend_model 5.0%).
  - Sector top2 beat SPY_200d on 90d stop-hit rate: no (sector_top2_momentum_simple_v1 2.5% vs SPY_200d_trend_model 0.0%).
  - Sector top2 beat SPY_200d on 90d worst drawdown: no (sector_top2_momentum_simple_v1 $-604.74 vs SPY_200d_trend_model $-590.69).
16. Sector top2 versus QQQ dual momentum on stop-aware risk:
  - Sector top2 beat QQQ dual momentum on drawdown-aware v2 score: no (sector_top2_momentum_simple_v1 $-98.02 vs qqq_spy_gld_ief_dual_momentum_v1 $-80.32).
  - Sector top2 beat QQQ dual momentum on original final_score: no (sector_top2_momentum_simple_v1 32.1197 vs qqq_spy_gld_ief_dual_momentum_v1 65.2672).
  - Sector top2 beat QQQ dual momentum on 90d +300: no (sector_top2_momentum_simple_v1 12.5% vs qqq_spy_gld_ief_dual_momentum_v1 47.5%).
  - Sector top2 beat QQQ dual momentum on 90d +400: no (sector_top2_momentum_simple_v1 2.5% vs qqq_spy_gld_ief_dual_momentum_v1 42.5%).
  - Sector top2 beat QQQ dual momentum on 90d stop-hit rate: yes (sector_top2_momentum_simple_v1 2.5% vs qqq_spy_gld_ief_dual_momentum_v1 17.5%).
  - Sector top2 beat QQQ dual momentum on 90d worst drawdown: yes (sector_top2_momentum_simple_v1 $-604.74 vs qqq_spy_gld_ief_dual_momentum_v1 $-678.34).
17. Sector top2 versus value/momentum factor rotation:
  - Sector top2 beat value/momentum factor rotation on drawdown-aware v2 score: no (sector_top2_momentum_simple_v1 $-98.02 vs value_momentum_factor_etf_rotation_v1 $24.59).
  - Sector top2 beat value/momentum factor rotation on original final_score: no (sector_top2_momentum_simple_v1 32.1197 vs value_momentum_factor_etf_rotation_v1 59.2206).
  - Sector top2 beat value/momentum factor rotation on 90d +300: no (sector_top2_momentum_simple_v1 12.5% vs value_momentum_factor_etf_rotation_v1 17.5%).
  - Sector top2 beat value/momentum factor rotation on 90d +400: no (sector_top2_momentum_simple_v1 2.5% vs value_momentum_factor_etf_rotation_v1 12.5%).
  - Sector top2 beat value/momentum factor rotation on 90d stop-hit rate: no (sector_top2_momentum_simple_v1 2.5% vs value_momentum_factor_etf_rotation_v1 0.0%).
  - Sector top2 beat value/momentum factor rotation on 90d worst drawdown: no (sector_top2_momentum_simple_v1 $-604.74 vs value_momentum_factor_etf_rotation_v1 $-407.75).
18. Future candidate_exhaustive deserved: false. Current verdict: too_risky.
19. No real-money recommendation is made.

Sector top2 target/risk ladder:

- 30d: +300 0.0%; +400 0.0%; +600 0.0%; +900 0.0%; +1200 0.0%; stop 0.0%; median $3,006.25; p95 $3,178.72; worst drawdown $-548.52
- 60d: +300 5.0%; +400 2.5%; +600 0.0%; +900 0.0%; +1200 0.0%; stop 0.0%; median $3,012.28; p95 $3,198.22; worst drawdown $-550.07
- 90d: +300 12.5%; +400 2.5%; +600 2.5%; +900 0.0%; +1200 0.0%; stop 2.5%; median $3,093.90; p95 $3,289.84; worst drawdown $-604.74
- 180d: +300 45.0%; +400 35.0%; +600 10.0%; +900 0.0%; +1200 0.0%; stop 2.5%; median $3,149.53; p95 $3,491.43; worst drawdown $-878.34


	
## Managed-Futures Proxy Research Sample

This row is research_sample only. It is not candidate-exhaustive, not validated, not paper-forward active, not a direct futures strategy test, and not a real-money recommendation.

1. Data available from cache: true. Cached implementation universe: DBMF, KMLM, BIL.
2. Data downloaded: false. The run used existing local cache only and did not refresh DBMF, KMLM, SPY, or BIL.
3. Universe used: DBMF and KMLM wrapper proxies, with BIL fallback.
4. CTA, FMF, and WTMF excluded: true. Those symbols remain outside this first fixed rule.
5. Rule: monthly rebalance; rank DBMF and KMLM by 126-trading-day return; a proxy qualifies only when 126-day return is positive and close is above the 200-day SMA; hold both qualifying proxies at 50% each, one qualifying proxy at 50% with unused 50% in BIL, or 100% BIL if neither qualifies; weights become effective on the next trading day after the signal.
6. DBMF/KMLM selected or allocated: DBMF selected 17.1% / allocation 8.6%; KMLM selected 8.5% / allocation 4.3%.
7. BIL fallback/allocation frequency: BIL selected 92.3% / allocation 87.1%.
8. +300/+400 target-rate improvement: see target ladder and direct comparisons below.
9. +600/+900/+1200 upside: see target ladder below.
10. Drawdown/stop risk: see stop and worst-drawdown rows below; proxy_concentration_warning=false; max_single_proxy_allocation=8.6%.
11. Diversifier or too slow: too_slow_warning=true. Diversification cannot be accepted without enough target potential.
12. Dependence on one fund: proxy_concentration_warning=false; max_single_proxy_allocation=8.6%.
13. Managed-futures proxy versus combo_SPY200d_GLD_50_50_v1:
  - Managed-futures proxy beat combo on drawdown-aware v2 score: yes (managed_futures_proxy_etf_trend_v1 $62.66 vs combo_SPY200d_GLD_50_50_v1 $-132.92).
  - Managed-futures proxy beat combo on original final_score: yes (managed_futures_proxy_etf_trend_v1 42.1653 vs combo_SPY200d_GLD_50_50_v1 -73.5256).
  - Managed-futures proxy beat combo on 90d +300: no (managed_futures_proxy_etf_trend_v1 17.5% vs combo_SPY200d_GLD_50_50_v1 22.5%).
  - Managed-futures proxy beat combo on 90d +400: no (managed_futures_proxy_etf_trend_v1 2.5% vs combo_SPY200d_GLD_50_50_v1 15.0%).
  - Managed-futures proxy beat combo on 90d stop-hit rate: no (managed_futures_proxy_etf_trend_v1 0.0% vs combo_SPY200d_GLD_50_50_v1 0.0%).
  - Managed-futures proxy beat combo on 90d worst drawdown: yes (managed_futures_proxy_etf_trend_v1 $-353.86 vs combo_SPY200d_GLD_50_50_v1 $-418.84).
14. Managed-futures proxy versus asset_class_tsmom_top2_v1:
  - Managed-futures proxy beat top2 on drawdown-aware v2 score: yes (managed_futures_proxy_etf_trend_v1 $62.66 vs asset_class_tsmom_top2_v1 $54.37).
  - Managed-futures proxy beat top2 on original final_score: no (managed_futures_proxy_etf_trend_v1 42.1653 vs asset_class_tsmom_top2_v1 62.5787).
  - Managed-futures proxy beat top2 on 90d +300: no (managed_futures_proxy_etf_trend_v1 17.5% vs asset_class_tsmom_top2_v1 20.0%).
  - Managed-futures proxy beat top2 on 90d +400: no (managed_futures_proxy_etf_trend_v1 2.5% vs asset_class_tsmom_top2_v1 12.5%).
  - Managed-futures proxy beat top2 on 90d stop-hit rate: no (managed_futures_proxy_etf_trend_v1 0.0% vs asset_class_tsmom_top2_v1 0.0%).
  - Managed-futures proxy beat top2 on 90d worst drawdown: yes (managed_futures_proxy_etf_trend_v1 $-353.86 vs asset_class_tsmom_top2_v1 $-539.08).
15. Managed-futures proxy versus SPY_200d_trend_model:
  - Managed-futures proxy beat SPY_200d on drawdown-aware v2 score: yes (managed_futures_proxy_etf_trend_v1 $62.66 vs SPY_200d_trend_model $-69.66).
  - Managed-futures proxy beat SPY_200d on original final_score: no (managed_futures_proxy_etf_trend_v1 42.1653 vs SPY_200d_trend_model 48.8964).
  - Managed-futures proxy beat SPY_200d on 90d +300: no (managed_futures_proxy_etf_trend_v1 17.5% vs SPY_200d_trend_model 20.0%).
  - Managed-futures proxy beat SPY_200d on 90d +400: no (managed_futures_proxy_etf_trend_v1 2.5% vs SPY_200d_trend_model 5.0%).
  - Managed-futures proxy beat SPY_200d on 90d stop-hit rate: no (managed_futures_proxy_etf_trend_v1 0.0% vs SPY_200d_trend_model 0.0%).
  - Managed-futures proxy beat SPY_200d on 90d worst drawdown: yes (managed_futures_proxy_etf_trend_v1 $-353.86 vs SPY_200d_trend_model $-590.69).
16. Managed-futures proxy versus GLD_buy_hold on risk-adjusted terms:
  - Managed-futures proxy beat GLD_buy_hold on drawdown-aware v2 score: yes (managed_futures_proxy_etf_trend_v1 $62.66 vs GLD_buy_hold $-66.51).
  - Managed-futures proxy beat GLD_buy_hold on original final_score: yes (managed_futures_proxy_etf_trend_v1 42.1653 vs GLD_buy_hold 35.4907).
  - Managed-futures proxy beat GLD_buy_hold on 90d +300: no (managed_futures_proxy_etf_trend_v1 17.5% vs GLD_buy_hold 47.5%).
  - Managed-futures proxy beat GLD_buy_hold on 90d +400: no (managed_futures_proxy_etf_trend_v1 2.5% vs GLD_buy_hold 32.5%).
  - Managed-futures proxy beat GLD_buy_hold on 90d stop-hit rate: yes (managed_futures_proxy_etf_trend_v1 0.0% vs GLD_buy_hold 20.0%).
  - Managed-futures proxy beat GLD_buy_hold on 90d worst drawdown: yes (managed_futures_proxy_etf_trend_v1 $-353.86 vs GLD_buy_hold $-842.61).
17. Managed-futures proxy versus BIL on target potential:
  - Managed-futures proxy beat BIL on drawdown-aware v2 score: yes (managed_futures_proxy_etf_trend_v1 $62.66 vs BIL_cash_proxy $-5.06).
  - Managed-futures proxy beat BIL on original final_score: yes (managed_futures_proxy_etf_trend_v1 42.1653 vs BIL_cash_proxy 2.9213).
  - Managed-futures proxy beat BIL on 90d +300: yes (managed_futures_proxy_etf_trend_v1 17.5% vs BIL_cash_proxy 0.0%).
  - Managed-futures proxy beat BIL on 90d +400: yes (managed_futures_proxy_etf_trend_v1 2.5% vs BIL_cash_proxy 0.0%).
  - Managed-futures proxy beat BIL on 90d stop-hit rate: no (managed_futures_proxy_etf_trend_v1 0.0% vs BIL_cash_proxy 0.0%).
  - Managed-futures proxy beat BIL on 90d worst drawdown: no (managed_futures_proxy_etf_trend_v1 $-353.86 vs BIL_cash_proxy $-21.48).
18. Future candidate_exhaustive deserved: false. Current verdict: too_slow.
19. Required short-history / fund-wrapper proxy warning: fund_wrapper_proxy_short_history_limited_inception_research_sample_only; wrapper_proxy_warning=true; short_history_warning=true; direct_futures_claim_disallowed=true.
20. No real-money recommendation is made.

Managed-futures proxy target/risk ladder:

	- 30d: +300 0.0%; +400 0.0%; +600 0.0%; +900 0.0%; +1200 0.0%; stop 0.0%; median $3,003.54; p95 $3,081.27; worst drawdown $-211.77
- 60d: +300 2.5%; +400 2.5%; +600 0.0%; +900 0.0%; +1200 0.0%; stop 0.0%; median $3,008.87; p95 $3,122.61; worst drawdown $-271.01
- 90d: +300 17.5%; +400 2.5%; +600 2.5%; +900 0.0%; +1200 0.0%; stop 0.0%; median $3,012.86; p95 $3,265.84; worst drawdown $-353.86
- 180d: +300 25.0%; +400 17.5%; +600 12.5%; +900 0.0%; +1200 0.0%; stop 0.0%; median $3,023.24; p95 $3,564.46; worst drawdown $-464.92
	

	
## Historical Combination Batch 1

This section reports exactly three predeclared fixed historical combination rows. It is research_sample only, uses existing local cache only, does not alter active paper-forward observations, and does not make a real-money recommendation.

### combo_plus_top2_50_50_v1

- components: combo_SPY200d_GLD_50_50_v1, asset_class_tsmom_top2_v1
- fixed weights: {'combo_SPY200d_GLD_50_50_v1': 0.5, 'asset_class_tsmom_top2_v1': 0.5}
- data available from cache: true
- data downloaded: false
- exact fresh-window accounting used: true
- hypothesis: Blend drawdown-aware combo with stronger asset-class momentum target potential.
- main risk: Duplicate SPY/GLD/trend exposure; may not improve stop-aware profit/risk.
- target/risk ladder: 30d +300 2.5%, +400 0.0%, +600 0.0%, +900 0.0%, +1200 0.0%, stop 0.0%, median $3,029.06, p95 $3,268.19, worst drawdown $-403.42; 60d +300 17.5%, +400 0.0%, +600 0.0%, +900 0.0%, +1200 0.0%, stop 0.0%, median $3,031.72, p95 $3,328.42, worst drawdown $-418.03; 90d +300 20.0%, +400 5.0%, +600 0.0%, +900 0.0%, +1200 0.0%, stop 0.0%, median $3,100.37, p95 $3,354.98, worst drawdown $-450.67; 180d +300 50.0%, +400 32.5%, +600 22.5%, +900 0.0%, +1200 0.0%, stop 0.0%, median $3,192.44, p95 $3,570.34, worst drawdown $-491.30
- beat combo on stop-aware score: combination beat combo: yes (combo_plus_top2_50_50_v1 $100.47 vs combo_SPY200d_GLD_50_50_v1 $-132.92).
- beat top2 on stop-aware score: combination beat top2: yes (combo_plus_top2_50_50_v1 $100.47 vs asset_class_tsmom_top2_v1 $54.37).
- improve +300/+400 target rates: +300 versus combo: no (combo_plus_top2_50_50_v1 20.0% vs combo_SPY200d_GLD_50_50_v1 22.5%). +400 versus combo: no (combo_plus_top2_50_50_v1 5.0% vs combo_SPY200d_GLD_50_50_v1 15.0%).
- reduce stop-hit rate: stop-hit versus combo: no (combo_plus_top2_50_50_v1 0.0% vs combo_SPY200d_GLD_50_50_v1 0.0%).
- reduce worst drawdown: worst drawdown versus combo: no (combo_plus_top2_50_50_v1 $-450.67 vs combo_SPY200d_GLD_50_50_v1 $-418.84).
- short-history label: not_applicable
- verdict: too_slow
- deserves candidate_exhaustive: false

### combo_plus_managed_futures_80_20_v1

- components: combo_SPY200d_GLD_50_50_v1, managed_futures_proxy_etf_trend_v1
- fixed weights: {'combo_SPY200d_GLD_50_50_v1': 0.8, 'managed_futures_proxy_etf_trend_v1': 0.2}
- data available from cache: true
- data downloaded: false
- exact fresh-window accounting used: true
- hypothesis: Add a different fund-wrapper proxy return driver to reduce drawdown or improve stress behavior.
- main risk: Managed-futures proxy was too slow as standalone and has short-history fund-wrapper limitations.
- target/risk ladder: 30d +300 0.0%, +400 0.0%, +600 0.0%, +900 0.0%, +1200 0.0%, stop 0.0%, median $3,040.47, p95 $3,118.82, worst drawdown $-178.97; 60d +300 0.0%, +400 0.0%, +600 0.0%, +900 0.0%, +1200 0.0%, stop 0.0%, median $3,082.95, p95 $3,202.21, worst drawdown $-300.03; 90d +300 17.5%, +400 10.0%, +600 0.0%, +900 0.0%, +1200 0.0%, stop 0.0%, median $3,155.59, p95 $3,464.19, worst drawdown $-321.11; 180d +300 64.1%, +400 53.8%, +600 41.0%, +900 2.6%, +1200 0.0%, stop 0.0%, median $3,384.62, p95 $3,775.31, worst drawdown $-372.25
- beat combo on stop-aware score: combination beat combo: yes (combo_plus_managed_futures_80_20_v1 $218.54 vs combo_SPY200d_GLD_50_50_v1 $-132.92).
- beat top2 on stop-aware score: combination beat top2: yes (combo_plus_managed_futures_80_20_v1 $218.54 vs asset_class_tsmom_top2_v1 $54.37).
- improve +300/+400 target rates: +300 versus combo: no (combo_plus_managed_futures_80_20_v1 17.5% vs combo_SPY200d_GLD_50_50_v1 22.5%). +400 versus combo: no (combo_plus_managed_futures_80_20_v1 10.0% vs combo_SPY200d_GLD_50_50_v1 15.0%).
- reduce stop-hit rate: stop-hit versus combo: no (combo_plus_managed_futures_80_20_v1 0.0% vs combo_SPY200d_GLD_50_50_v1 0.0%).
- reduce worst drawdown: worst drawdown versus combo: yes (combo_plus_managed_futures_80_20_v1 $-321.11 vs combo_SPY200d_GLD_50_50_v1 $-418.84).
- short-history label: fund_wrapper_proxy_short_history_limited_inception_research_sample_only
- verdict: too_slow
- deserves candidate_exhaustive: false

### top2_plus_managed_futures_80_20_v1

- components: asset_class_tsmom_top2_v1, managed_futures_proxy_etf_trend_v1
- fixed weights: {'asset_class_tsmom_top2_v1': 0.8, 'managed_futures_proxy_etf_trend_v1': 0.2}
- data available from cache: true
- data downloaded: false
- exact fresh-window accounting used: true
- hypothesis: Reduce top2 drawdown-budget usage while retaining target potential.
- main risk: Target dilution; short-history managed-futures proxy evidence.
- target/risk ladder: 30d +300 0.0%, +400 0.0%, +600 0.0%, +900 0.0%, +1200 0.0%, stop 0.0%, median $3,005.70, p95 $3,114.80, worst drawdown $-192.12; 60d +300 0.0%, +400 0.0%, +600 0.0%, +900 0.0%, +1200 0.0%, stop 0.0%, median $2,996.74, p95 $3,202.21, worst drawdown $-305.22; 90d +300 15.0%, +400 10.0%, +600 0.0%, +900 0.0%, +1200 0.0%, stop 0.0%, median $3,092.70, p95 $3,464.19, worst drawdown $-326.63; 180d +300 69.2%, +400 56.4%, +600 33.3%, +900 0.0%, +1200 0.0%, stop 0.0%, median $3,373.93, p95 $3,666.39, worst drawdown $-402.75
- beat combo on stop-aware score: combination beat combo: yes (top2_plus_managed_futures_80_20_v1 $203.70 vs combo_SPY200d_GLD_50_50_v1 $-132.92).
- beat top2 on stop-aware score: combination beat top2: yes (top2_plus_managed_futures_80_20_v1 $203.70 vs asset_class_tsmom_top2_v1 $54.37).
- improve +300/+400 target rates: +300 versus combo: no (top2_plus_managed_futures_80_20_v1 15.0% vs combo_SPY200d_GLD_50_50_v1 22.5%). +400 versus combo: no (top2_plus_managed_futures_80_20_v1 10.0% vs combo_SPY200d_GLD_50_50_v1 15.0%).
- reduce stop-hit rate: stop-hit versus combo: no (top2_plus_managed_futures_80_20_v1 0.0% vs combo_SPY200d_GLD_50_50_v1 0.0%).
- reduce worst drawdown: worst drawdown versus combo: yes (top2_plus_managed_futures_80_20_v1 $-326.63 vs combo_SPY200d_GLD_50_50_v1 $-418.84).
- short-history label: fund_wrapper_proxy_short_history_limited_inception_research_sample_only
- verdict: too_slow
- deserves candidate_exhaustive: false



	## Candidate Exhaustive Queue

Candidate-exhaustive was not run for this task. The queue below is for later overnight validation only and does not promote any row.

- asset_class_tsmom_top2_v1: reason_for_queue=research_sample accounting-valid row improves diagnostic score versus SPY_200d/combo_SPY200d_GLD_50_50; evidence_tier=tier2_credible_prototype; research_sample_result_summary=+300 20.0%, +400 12.5%, stop 0.0%, median $3,097.46; main_risk=whipsaw, concentration, and possible defensive drag; comparison_target=SPY_200d_trend_model and combo_SPY200d_GLD_50_50_v1; recommended_finalist_set=asset_class_tsmom_top2_v1, SPY_200d_trend_model, combo_SPY200d_GLD_50_50_v1, GLD_buy_hold, BIL_cash_proxy
- asset_class_tsmom_equal_weight_v1: reason_for_queue=research_sample accounting-valid row improves diagnostic score versus SPY_200d/combo_SPY200d_GLD_50_50; evidence_tier=tier2_credible_prototype; research_sample_result_summary=+300 17.5%, +400 12.5%, stop 0.0%, median $3,089.11; main_risk=diluted upside, regime whipsaw, and defensive drag; comparison_target=SPY_200d_trend_model and combo_SPY200d_GLD_50_50_v1; recommended_finalist_set=asset_class_tsmom_equal_weight_v1, SPY_200d_trend_model, combo_SPY200d_GLD_50_50_v1, GLD_buy_hold, BIL_cash_proxy
- SPY_200d_trend_model: reason_for_queue=research_sample accounting-valid row improves diagnostic score versus combo_SPY200d_GLD_50_50; evidence_tier=tier3_candidate_validation; research_sample_result_summary=+300 20.0%, +400 5.0%, stop 0.0%, median $3,081.03; main_risk=equity drawdown and whipsaw; comparison_target=SPY_200d_trend_model and combo_SPY200d_GLD_50_50_v1; recommended_finalist_set=SPY_200d_trend_model, SPY_200d_trend_model, combo_SPY200d_GLD_50_50_v1, GLD_buy_hold, BIL_cash_proxy

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
