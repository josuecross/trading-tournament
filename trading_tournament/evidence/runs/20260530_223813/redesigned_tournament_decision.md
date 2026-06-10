# Redesigned Tournament Decision

This is research-only paper/demo evidence. It is not a real-money trading recommendation.

## Blunt Answers
1. Did any evidence-backed strategy beat current_no_cash_proxy_alpha_AB? No.
2. Did any strategy materially improve 90-day +$300 before stop rate? No material improvement over current_no_cash_proxy_alpha_AB.
3. Did any strategy materially improve 90-day +$400 before stop rate? Review the table; +$400 remains low probability unless the rate is consistently above 5% under stress.
4. Did any strategy improve stress-slippage robustness? Best stress-stability variant: ``.
5. Did any strategy reduce drawdown while preserving target probability? Lowest drawdown-risk variant: `evidence_dual_momentum_taa`; target preservation must be judged against the rolling target columns.
6. Should current A/B remain the best candidate? Yes, current_no_cash_proxy_alpha_AB remains the main comparator.
7. Should any new strategy become the leading candidate? No new strategy displaces the current comparator.
8. Should C/D/E remain rejected/shadow-only? Yes.
9. Is the +$300 target still modest probability? Yes; even useful rates are not high enough to call reliable.
10. Is the +$400 target still low probability? Yes unless the final evidence table shows stress 90-day +$400 before-stop rates above 5%.
11. Is the redesigned tournament better than the current tournament? Not demonstrated by this run.
12. Single best next paper-forward candidate: `current_no_cash_proxy_alpha_AB`.

## Strategy Family Comparison
                  variant_name  evidence_family recommended_status  final_equity  stress_final_equity  stress_final_equity_delta  max_drawdown_dollars  target_300_before_any_stop  target_400_before_any_stop  rolling90_pct_windows_target_300_before_stop_standard  rolling90_pct_windows_target_400_before_stop_standard  rolling90_pct_windows_any_stop_hit_standard                                                                                              forward_test_decision_reason
current_no_cash_proxy_alpha_AB       current_ab          watchlist   3392.201266                  NaN                        NaN           -609.810639                        True                        True                                               0.166667                                                  0.125                                          0.0                                          not validated until independent rolling windows show stronger target reliability
    evidence_dual_momentum_taa     evidence_taa          watchlist   3087.135220                  NaN                        NaN           -638.969664                        True                        True                                               0.000000                                                  0.000                                          0.0                         90-day +300 before stop rate is 0.00%, below 10%; 90-day +400 before stop rate is 0.00%, below 5%
      original_full_tournament legacy_reference        shadow_only   3508.173545                  NaN                        NaN           -600.723143                        True                        True                                                    NaN                                                    NaN                                          NaN original full tournament is retained as reference only; variant includes C/D/E and at least one was killed by loss budget

No variant is marked validated.
