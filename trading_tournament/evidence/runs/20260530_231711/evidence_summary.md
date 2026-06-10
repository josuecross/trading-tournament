# Evidence Summary


> WARNING: These rolling results are deterministic research samples, not final exhaustive validation. Use them for screening only; finalist claims still require candidate_exhaustive mode.

## 1. Research-Only Statement
This is paper/demo research only. There is no broker integration, no live orders, no AI trading gate, and no real-money recommendation.

## 2. Run Identity And Config
- Run id: `20260530_231711`
- Project stop mode: `both`
- Selected main run: `original_full_tournament_standard`
- Validation mode: `smoke`
- Rolling method: `deterministic_stratified_sample`
- Final validation completed: False
- Sampled results are final: False

If `rolling_method` is not `all_possible`, these rolling results are deterministic research samples, not final exhaustive validation.

## 3. Headline Result
- Final equity: $3,508.17
- Total return: 16.94%
- CAGR: 2.00%
- Max drawdown: $-600.72 (-17.62%)
- Trades: 368
- Skipped signals: 7458

## 4. Stop Mode And Risk-Budget Result
- Absolute floor stop hit: False
- Trailing drawdown stop hit: True
- Any project stop hit: True
- First project stop: trailing_drawdown_stop_hit on 2015-12-03

## 5. Target Timing
- +$300 hit before any selected stop: True
- +$400 hit before any selected stop: True

## 6. Standard Vs Stress Slippage
- Standard final equity: $3,508.17
- Stress final equity: $nan
- Stress delta: $nan

## 7. Strategy Variant Comparison
                  variant_name                                                                                 enabled_strategies slippage_label  slippage_pct_per_side  final_equity  total_return     cagr  max_drawdown_dollars  max_drawdown_pct  number_of_trades  profit_factor  expectancy_per_trade_dollars  expectancy_per_trade_r  win_rate  target_300_hit  target_300_before_any_stop  target_400_hit  target_400_before_any_stop  absolute_floor_stop_hit  trailing_drawdown_stop_hit  any_project_stop_hit first_project_stop_date                                      strategies_killed  top_5_trade_pnl_contribution_pct  best_strategy_by_pnl  worst_strategy_by_pnl suitable_for_forward_paper_test                                                                                              forward_test_decision_reason  evidence_family                              evidence_strength                    primary_failure_mode recommended_status
current_no_cash_proxy_alpha_AB                                                        A_ETF_sector_momentum,B_ETF_trend_following       standard                 0.0005   3392.201266      0.130734 0.015472           -609.810639         -0.152376               190       1.137796                      2.064217                0.100022  0.421053            True                        True            True                        True                    False                        True                  True              2016-01-04                                  B_ETF_trend_following                          0.206400 A_ETF_sector_momentum  B_ETF_trend_following                       watchlist                                          not validated until independent rolling windows show stronger target reliability       current_ab                                      watchlist                                                  watchlist
    evidence_dual_momentum_taa                                                                               N1_dual_momentum_taa       standard                 0.0005   3087.135220      0.029045 0.001900           -638.969664         -0.171485               295       1.017119                      0.295374               -0.026002  0.406780            True                        True            True                        True                    False                        True                  True              2023-02-02                                                                                 0.137493  N1_dual_momentum_taa   N1_dual_momentum_taa                       watchlist                         90-day +300 before stop rate is 0.00%, below 10%; 90-day +400 before stop rate is 0.00%, below 5%     evidence_taa plausible_fixed_rules_needs_forward_paper_test              low_90_day_target_300_rate          watchlist
      original_full_tournament A_ETF_sector_momentum,B_ETF_trend_following,C_swing_trend_pullback,D_mean_reversion,E_breakout_vcb       standard                 0.0005   3508.173545      0.169391 0.019967           -600.723143         -0.176175               368       1.138063                      1.380906                0.028237  0.380435            True                        True            True                        True                    False                        True                  True              2015-12-03 C_swing_trend_pullback,D_mean_reversion,E_breakout_vcb                          0.178410 A_ETF_sector_momentum C_swing_trend_pullback                     shadow_only original full tournament is retained as reference only; variant includes C/D/E and at least one was killed by loss budget legacy_reference                            weak_or_shadow_only legacy_satellites_killed_by_loss_budget        shadow_only

New evidence-backed strategy family comparison is written to `evidence_strategy_family_comparison.csv`.
The redesigned tournament decision is written to `redesigned_tournament_decision.md`, and anti-overfitting notes are written to `anti_overfitting_log.md`.

## 8. Independent Rolling-Window Validation
Replay rolling diagnostics are not final validation. Independent rolling-window simulations are the primary validation.

Sampling note: independent rolling rows report `window_sampling_method=deterministic_stratified_sample`. Possible window counts by group range up to 4541. If the method is not `all_possible`, treat the rates as deterministic audit samples, not exhaustive rolling probabilities.


Decision snapshot from `exhaustive_rolling_decision.md`:
- Best robust 90-day +$300 before stop variant: `current_no_cash_proxy_alpha_AB` at 16.67%
- Best robust 90-day +$400 before stop variant: `current_no_cash_proxy_alpha_AB` at 12.50%
- Best candidate status: `current_no_cash_proxy_alpha_AB` / `leading_watchlist_candidate`
- Probability assessment: `watchlist_not_validated`

                  variant_name slippage_label  horizon_trading_days  number_of_windows  median_final_equity  mean_final_equity  pct_windows_positive_return  pct_windows_loss  pct_windows_target_300_hit  pct_windows_target_300_before_stop  pct_windows_target_400_hit  pct_windows_target_400_before_stop  pct_windows_absolute_stop_hit  pct_windows_trailing_stop_hit  pct_windows_any_stop_hit  median_max_drawdown  worst_max_drawdown  median_number_of_trades  pct_windows_above_3300  pct_windows_above_3400  pct_windows_below_2400  10th_percentile_final_equity  25th_percentile_final_equity  75th_percentile_final_equity  90th_percentile_final_equity  possible_window_count          window_sampling_method  percentile_10_final_equity  percentile_25_final_equity  percentile_75_final_equity  percentile_90_final_equity
current_no_cash_proxy_alpha_AB       standard                    90                 24          3023.485773        3044.037302                     0.625000          0.291667                    0.166667                            0.166667                       0.125                               0.125                            0.0                            0.0                       0.0          -135.862590         -277.367915                     16.0                0.041667                     0.0                     0.0                   2904.296753                   2962.968671                   3126.571923                   3182.625454                   4541 deterministic_stratified_sample                 2904.296753                 2962.968671                 3126.571923                 3182.625454
    evidence_dual_momentum_taa       standard                    90                 24          3015.827541        3028.834650                     0.583333          0.416667                    0.000000                            0.000000                       0.000                               0.000                            0.0                            0.0                       0.0          -113.753971         -201.958266                      6.5                0.000000                     0.0                     0.0                   2887.288475                   2986.482135                   3115.058088                   3132.599108                   4541 deterministic_stratified_sample                 2887.288475                 2986.482135                 3115.058088                 3132.599108

## 9. Replay Rolling Diagnostics
These are secondary diagnostics only and do not reset strategy state independently.

 horizon_trading_days  number_of_windows  median_final_equity  mean_final_equity  pct_windows_target_300_hit  pct_windows_target_300_before_stop  pct_windows_target_400_hit  pct_windows_target_400_before_stop  pct_windows_absolute_stop_hit  pct_windows_trailing_stop_hit  pct_windows_any_stop_hit  median_max_drawdown  worst_max_drawdown  median_number_of_trades  pct_windows_positive_return  pct_windows_loss  pct_windows_below_2400  pct_windows_above_3300  pct_windows_above_3400
                   30               1966          3000.000000        3009.018264                    0.003052                            0.003052                    0.000000                            0.000000                            0.0                            0.0                       0.0           -83.576989         -279.382793                      5.0                     0.472024          0.492370                     0.0                0.000000                0.000000
                   60               1936          3003.223905        3018.070623                    0.029442                            0.029442                    0.012913                            0.012913                            0.0                            0.0                       0.0          -116.317807         -291.041610                     11.0                     0.514979          0.483471                     0.0                0.019628                0.007231
                   90               1906          3023.531646        3028.683779                    0.080273                            0.080273                    0.022036                            0.022036                            0.0                            0.0                       0.0          -148.189743         -308.583587                     16.0                     0.561910          0.438090                     0.0                0.052991                0.014166
                  180               1816          3078.710686        3079.705456                    0.262665                            0.262665                    0.111784                            0.111784                            0.0                            0.0                       0.0          -205.343329         -414.640228                     32.0                     0.661344          0.338656                     0.0                0.156388                0.069934

## 10. Strategy Health: A/B/C/D/E
              strategy  enabled   final_pnl  final_unrealized_pnl  total_trades  winning_trades  losing_trades  win_rate  profit_factor  expectancy_dollars  expectancy_r  max_drawdown  max_consecutive_losses  killed_by_loss_budget  kill_date  kill_equity  kill_strategy_pnl first_trade_date last_trade_date  target_contribution_dollars  top_trade_contribution_pct  stress_result_available  standard_vs_stress_delta
 A_ETF_sector_momentum     True  428.535289                   0.0           149              58             91  0.389262       1.259990            2.876076      0.085834   -402.072043                      16                  False                     NaN                NaN       2008-05-19      2015-12-03                   428.535289                    0.307491                    False                       NaN
 B_ETF_trend_following     True  406.687044                   0.0           148              60             88  0.405405       1.298551            2.747885      0.069655   -283.231944                      11                  False                     NaN                NaN       2008-05-07      2015-12-03                   406.687044                    0.329658                    False                       NaN
C_swing_trend_pullback     True -152.420318                   0.0            23               5             18  0.217391       0.544979           -6.626970     -0.225168   -283.772848                       7                   True 2008-12-31  2701.142839        -151.341855       2008-01-22      2008-12-31                  -152.420318                    1.000000                    False                       NaN
      D_mean_reversion     True  -77.141231                   0.0            23               9             14  0.391304       0.525501           -3.353967     -0.277045   -108.438337                       7                   True 2008-05-01  2971.318384         -76.748981       2008-01-04      2008-05-01                   -77.141231                    0.867333                    False                       NaN
        E_breakout_vcb     True  -97.487240                   0.0            25               8             17  0.320000       0.435578           -3.899490     -0.046247   -117.661441                       6                   True 2009-10-02  2612.567542         -96.706516       2008-02-28      2009-10-02                   -97.487240                    0.991095                    False                       NaN

## 11. R-Multiple Quality Warning
R-multiple quality is not automatically trusted. Review tiny actual-risk and BIL/SHY rows in `r_multiple_diagnostics.csv`.

 total_trades  avg_intended_risk  median_intended_risk  avg_actual_risk  median_actual_risk  avg_risk_utilization_pct  median_risk_utilization_pct  pct_trades_risk_utilization_lt_25  pct_trades_risk_utilization_lt_50  pct_trades_stop_distance_lt_0_25pct  pct_trades_stop_distance_lt_0_50pct  max_r_multiple  min_r_multiple  mean_r_multiple  median_r_multiple               top_10_r_multiple_symbols  bil_trade_count  shy_trade_count    bil_pnl   shy_pnl  bil_avg_r_multiple  shy_avg_r_multiple  would_exclude_min_stop_distance_pct_count  would_exclude_min_stop_distance_pct_pnl  would_exclude_min_actual_risk_utilization_count  would_exclude_min_actual_risk_utilization_pnl
          368          43.043478                  45.0        22.292488           25.290211                  0.518755                      0.57311                           0.233696                           0.445652                             0.108696                              0.13587        7.110647       -2.084173         0.028237           -0.41403 XLV,IEF,XLU,XLY,BIL,GLD,XLI,GLD,GLD,XLY               20               32 -16.855039 -30.28477           -0.292663           -0.388371                                         40                               -20.169135                                               86                                      -4.657224

## 12. Symbol Concentration
Review `symbol_contribution.csv`, especially BIL and SHY flags.

## 13. Skipped Signals
Review `skipped_signal_summary.csv` and `skipped_signal_sample.csv`; only rejected generated signals are included.

## 14. Risk Events
Review `risk_events.csv` for stops, loss blocks, risk-cap blocks, gap-through stops, and final marks.

## 15. Data Quality
Review `data_quality_summary.csv` and `data_quality_summary.md` for coverage, late inception, and exclusions.

## 16. Consistency Check Result
- Passed: True
- Errors: []
- Warnings: []

## 17. What Would Invalidate This Strategy
- Low independent 90-day +$300/+400 target-before-stop rates.
- Trailing drawdown stop invalidates most target-reaching windows.
- Stress slippage materially damages results.
- A-only or A/B does not survive risk-adjusted review.
- Results depend on BIL/SHY or tiny-risk R-multiple artifacts.
- C/D/E continue hitting loss budgets.
- Top trades explain most profit.

## 18. Best Current Candidate For Paper Forward Test
- Candidate: current_no_cash_proxy_alpha_AB
- Status: leading_watchlist_candidate
- C/D/E status: shadow-only or rejected for now because C/D/E were killed by loss budgets in the main tournament.

## 19. Recommended Next Actions
- Upload the recommended evidence files in `README_FOR_AUDITOR.md`.
- Audit independent rolling windows before any forward paper test.
- Do not tune parameters based on this packet.
- Treat all candidates as watchlist until independent evidence improves.

## 20. No Real-Money Recommendation
This packet does not recommend real-money trading.
