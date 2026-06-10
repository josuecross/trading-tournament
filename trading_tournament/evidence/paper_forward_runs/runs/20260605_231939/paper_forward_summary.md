# Paper-Forward Observation Summary

## 1. Research-Only Statement

This is paper/demo observation only. It does not recommend real-money trading, does not connect to a broker, and does not place orders.

## 2. Run Identity

- run_id: 20260605_231939
- output: `evidence/paper_forward_runs/runs/20260605_231939/`
- compact file count: 10

## 3. Observation Period

- start: 2026-06-05
- end: 2026-05-29

## 4. Strategies Observed

SPY_200d_trend_model, SPY_buy_hold, BIL_cash_proxy, current_no_cash_proxy_alpha_AB, combo_SPY200d_GLD_50_50_v1. Each row has its own independent $3,000 simulated paper account when active. Blocked rows are recorded as governance evidence only.

## 5. Current Status Table

| strategy | role | current_equity | current_return | status | signal_state | current_position_symbols |
| --- | --- | --- | --- | --- | --- | --- |
| SPY_200d_trend_model | primary_watchlist_candidate | 3000.0000 | 0.0000 | no_new_data |  |  |
| SPY_buy_hold | aggressive_benchmark | 3000.0000 | 0.0000 | no_new_data |  |  |
| BIL_cash_proxy | defensive_benchmark | 3000.0000 | 0.0000 | no_new_data |  |  |
| current_no_cash_proxy_alpha_AB | strategy_control | 3000.0000 | 0.0000 | insufficient_data | unavailable | unavailable |
| combo_SPY200d_GLD_50_50_v1 | parallel_observation_candidate_blocked | 3000.0000 | 0.0000 | active_waiting_for_next_cached_trading_day | activation_waiting_for_data | SPY,GLD,BIL |

## 6. Current Signals

| strategy | symbol | signal | target_weight | reason | data_quality_flag |
| --- | --- | --- | --- | --- | --- |
| current_no_cash_proxy_alpha_AB |  | unavailable | nan | A/B replay unavailable: No observation dates after start date for current_no_cash_proxy_alpha_AB. | insufficient_data |
| combo_SPY200d_GLD_50_50_v1 | SPY | activation_waiting_for_data | nan | Combo paper/demo observation is waiting for cached data after the requested activation date. No data was downloaded and no observation metrics were fabricated. | waiting_for_cached_data |
| combo_SPY200d_GLD_50_50_v1 | GLD | activation_waiting_for_data | nan | Combo paper/demo observation is waiting for cached data after the requested activation date. No data was downloaded and no observation metrics were fabricated. | waiting_for_cached_data |
| combo_SPY200d_GLD_50_50_v1 | BIL | activation_waiting_for_data | nan | Combo paper/demo observation is waiting for cached data after the requested activation date. No data was downloaded and no observation metrics were fabricated. | waiting_for_cached_data |

## 7. Distance To +300/+400 Targets

| strategy | risk_status | current_equity | target_300_distance | distance_to_trailing_stop | max_drawdown_dollars |
| --- | --- | --- | --- | --- | --- |
| SPY_200d_trend_model | normal | 3000.0000 | 300.0000 | 600.0000 | 0.0000 |
| SPY_buy_hold | normal | 3000.0000 | 300.0000 | 600.0000 | 0.0000 |
| BIL_cash_proxy | normal | 3000.0000 | 300.0000 | 600.0000 | 0.0000 |
| current_no_cash_proxy_alpha_AB | normal | 3000.0000 | 300.0000 | 600.0000 | 0.0000 |
| combo_SPY200d_GLD_50_50_v1 | activation_blocked | 3000.0000 | 300.0000 | 600.0000 | 0.0000 |

## 8. Distance To Stops

See `risk_status.csv`; stop mode is both absolute floor $2,400 and high-water mark minus $600.

## 9. Historical 90-Day Context

| strategy | current_vs_historical_status | historical_90d_pct_target_300_before_stop | historical_90d_pct_any_stop_hit |
| --- | --- | --- | --- |
| SPY_200d_trend_model | too_early_to_compare_to_90d_distribution | 0.2381 | 0.0046 |
| SPY_buy_hold | too_early_to_compare_to_90d_distribution | 0.3150 | 0.0643 |
| BIL_cash_proxy | too_early_to_compare_to_90d_distribution | 0.0000 | 0.0000 |
| current_no_cash_proxy_alpha_AB | too_early_to_compare_to_90d_distribution | 0.1260 | 0.0000 |
| combo_SPY200d_GLD_50_50_v1 | active_waiting_for_next_cached_trading_day | nan | nan |

## 10. Risk Framework Status

| strategy | risk_framework_status | risk_band | risk_budget_used_pct | target_300_progress_pct | target_400_progress_pct |
| --- | --- | --- | --- | --- | --- |
| SPY_200d_trend_model | active_normal | normal | 0.0000 | 0.0000 | 0.0000 |
| SPY_buy_hold | active_normal | normal | 0.0000 | 0.0000 | 0.0000 |
| BIL_cash_proxy | active_normal | normal | 0.0000 | 0.0000 | 0.0000 |
| current_no_cash_proxy_alpha_AB | active_normal | normal | 0.0000 | 0.0000 | 0.0000 |
| combo_SPY200d_GLD_50_50_v1 | activation_blocked | normal | 0.0000 | 0.0000 | 0.0000 |

SPY_200d_trend_model remains governed by `balanced_speculative_research_v1`. The observation should continue only while fixed rules remain unchanged and the row stays inside the project stop framework.

## 11. Monthly Decision Checkpoint

| checkpoint_month | latest_observation_end_date | primary_strategy | primary_current_equity | primary_target_300_distance | primary_target_400_distance | primary_distance_to_absolute_stop | primary_distance_to_trailing_stop | primary_risk_band | decision | decision_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2026-05 | 2026-05-29 | SPY_200d_trend_model | 3000.0000 | 300.0000 | 400.0000 | 600.0000 | 600.0000 | normal | data_issue | Required paper-forward data or replay output is unavailable. |
| 2026-05 | 2026-05-29 | combo_SPY200d_GLD_50_50_v1 | 3000.0000 | 300.0000 | 400.0000 | 600.0000 | 600.0000 | normal | active_waiting_for_next_cached_trading_day | Combo activation is waiting for cached data after the requested activation date; no data download was performed. |

The checkpoint is a decision aid only. It forbids rule changes, parameter tuning, real-money trading, broker integration, and adding diagnostic rows to the active paper-forward observation.

## 12. Historical Expectation Comparison

| strategy | historical_90d_pct_target_300_before_stop | historical_90d_pct_target_400_before_stop | historical_90d_pct_any_stop_hit | historical_90d_median_stop_enforced_equity | historical_90d_worst_drawdown | current_vs_historical_status |
| --- | --- | --- | --- | --- | --- | --- |
| SPY_200d_trend_model | 0.2381 | 0.0987 | 0.0046 | 3095.5867 | -661.4912 | too_early_to_compare_to_90d_distribution |
| SPY_buy_hold | 0.3150 | 0.1496 | 0.0643 | 3152.5499 | -1329.5805 | too_early_to_compare_to_90d_distribution |
| BIL_cash_proxy | 0.0000 | 0.0000 | 0.0000 | 3000.4624 | -24.6742 | too_early_to_compare_to_90d_distribution |
| current_no_cash_proxy_alpha_AB | 0.1260 | 0.0340 | 0.0000 | 3024.7900 | -406.0200 | too_early_to_compare_to_90d_distribution |
| combo_SPY200d_GLD_50_50_v1 | nan | nan | nan | 3000.0000 | nan | active_waiting_for_next_cached_trading_day |

The historical context comes from the exact compact challenge audit baseline. It is not a prediction and does not validate real-money use.

## 13. Combo Parallel Observation Status

- combo_strategy: combo_SPY200d_GLD_50_50_v1
- combo_status: active_waiting_for_next_cached_trading_day
- combo_rule_hash_verified: True
- combo_canonical_rule_hash: 6695f0d3ec403e2f377d99f3f63d1fc57a66f45f2c27a9072ab8c0a60a19ee67
- combo_replaces_spy200d: false
- SPY_200d_frozen_control: true
- combo_current_equity_if_available: $3,000.00
- combo_distance_to_300_if_available: $300.00
- combo_distance_to_400_if_available: $400.00
- combo_distance_to_stop_if_available: $600.00
- combo_vs_spy200d_equity_difference: $0.00
- activation_note: Full active combo observation is not active unless the canonical rule hash is verified and cached data supports the requested activation date.

The combo does not replace SPY_200d. SPY_200d remains the frozen paper-forward control until a separate governance decision says otherwise.

## 14. Rule Or Data Issues

current_no_cash_proxy_alpha_AB equity was replayed with existing fixed rules, but compact latest-signal extraction is marked unavailable rather than invented.

The combo row must not become active without a verified canonical rule hash and cached data through the observation start date. No data was downloaded in this run.

## 15. Observation Active?

False

## 16. Success Criteria

Success is reaching +$300 or +$400 before either project stop, while fixed rules remain unchanged.

## 17. Failure Criteria

Failure is hitting the absolute or trailing project stop, or discovering data/signal extraction problems that make the observation unauditable.

## 18. Final Current Conclusion

SPY_200d_trend_model is no_new_data with equity $3,000.00. It is $300.00 from +$300 and $600.00 above the trailing stop. No real-money action is implied.

Closest to +$300: SPY_200d_trend_model. Largest drawdown so far: SPY_200d_trend_model. This remains research-only paper observation.
