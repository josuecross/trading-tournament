# Paper-Forward Observation Summary

## 1. Research-Only Statement

This is paper/demo observation only. It does not recommend real-money trading, does not connect to a broker, and does not place orders.

## 2. Run Identity

- run_id: 20260606_040641
- output: `evidence/paper_forward_runs/runs/20260606_040641/`
- compact file count: 10

## 3. Observation Period

- start: 2026-06-05
- end: 2026-06-05

## 4. Strategies Observed

SPY_200d_trend_model, SPY_buy_hold, BIL_cash_proxy, current_no_cash_proxy_alpha_AB, combo_SPY200d_GLD_50_50_v1. Each row has its own independent $3,000 simulated paper account when active. Blocked rows are recorded as governance evidence only.

## 5. Current Status Table

| strategy | role | current_equity | current_return | status | signal_state | current_position_symbols |
| --- | --- | --- | --- | --- | --- | --- |
| SPY_200d_trend_model | primary_watchlist_candidate | 2998.5000 | -0.0005 | active_observation | risk_on | SPY |
| SPY_buy_hold | aggressive_benchmark | 2998.5000 | -0.0005 | active_observation | hold_spy | SPY |
| BIL_cash_proxy | defensive_benchmark | 2998.5000 | -0.0005 | active_observation | hold_bil | BIL |
| current_no_cash_proxy_alpha_AB | strategy_control | 3000.0000 | 0.0000 | active_observation | engine_replayed_signal_snapshot_unavailable | none_or_unavailable |
| combo_SPY200d_GLD_50_50_v1 | parallel_observation_candidate | 2904.9679 | -0.0317 | active_paper_demo_observation | active_combo_observation | GLD,SPY |

## 6. Current Signals

| strategy | symbol | signal | target_weight | reason | data_quality_flag |
| --- | --- | --- | --- | --- | --- |
| SPY_200d_trend_model | SPY | risk_on | 1.0000 | SPY close > 200-day SMA | ok |
| SPY_200d_trend_model | BIL | not_selected | 0.0000 | BIL receives weight when SPY is below/at SMA200 or SPY SMA is unavailable. | ok |
| SPY_buy_hold | SPY | hold_spy | 1.0000 | Fixed benchmark holding. | ok |
| BIL_cash_proxy | BIL | hold_bil | 1.0000 | Fixed benchmark holding. | ok |
| current_no_cash_proxy_alpha_AB |  | unavailable | nan | Existing A/B engine was replayed for equity, but it does not expose a compact latest-signal API here; no signal invented. | signal_snapshot_unavailable |
| combo_SPY200d_GLD_50_50_v1 | SPY | spy_sleeve_risk_on | 0.5000 | SPY_200d sleeve: SPY close > 200-day SMA | ok |
| combo_SPY200d_GLD_50_50_v1 | GLD | gld_buy_hold_sleeve | 0.5000 | Combo target weight from fixed 50/50 SPY_200d and GLD sleeves. | ok |
| combo_SPY200d_GLD_50_50_v1 | BIL | not_selected | 0.0000 | Combo target weight from fixed 50/50 SPY_200d and GLD sleeves. | ok |

## 7. Distance To +300/+400 Targets

| strategy | risk_status | current_equity | target_300_distance | distance_to_trailing_stop | max_drawdown_dollars |
| --- | --- | --- | --- | --- | --- |
| SPY_200d_trend_model | normal | 2998.5000 | 301.5000 | 600.0000 | 0.0000 |
| SPY_buy_hold | normal | 2998.5000 | 301.5000 | 600.0000 | 0.0000 |
| BIL_cash_proxy | normal | 2998.5000 | 301.5000 | 600.0000 | 0.0000 |
| current_no_cash_proxy_alpha_AB | normal | 3000.0000 | 300.0000 | 600.0000 | 0.0000 |
| combo_SPY200d_GLD_50_50_v1 | normal | 2904.9679 | 395.0321 | 600.0000 | 0.0000 |

## 8. Distance To Stops

See `risk_status.csv`; stop mode is both absolute floor $2,400 and high-water mark minus $600.

## 9. Historical 90-Day Context

| strategy | current_vs_historical_status | historical_90d_pct_target_300_before_stop | historical_90d_pct_any_stop_hit |
| --- | --- | --- | --- |
| SPY_200d_trend_model | too_early_to_compare_to_90d_distribution | 0.2381 | 0.0046 |
| SPY_buy_hold | too_early_to_compare_to_90d_distribution | 0.3150 | 0.0643 |
| BIL_cash_proxy | too_early_to_compare_to_90d_distribution | 0.0000 | 0.0000 |
| current_no_cash_proxy_alpha_AB | too_early_to_compare_to_90d_distribution | 0.1260 | 0.0000 |
| combo_SPY200d_GLD_50_50_v1 | too_early_to_compare_to_90d_distribution | nan | nan |

## 10. Risk Framework Status

| strategy | risk_framework_status | risk_band | risk_budget_used_pct | target_300_progress_pct | target_400_progress_pct |
| --- | --- | --- | --- | --- | --- |
| SPY_200d_trend_model | active_normal | normal | 0.0000 | 0.0000 | 0.0000 |
| SPY_buy_hold | active_normal | normal | 0.0000 | 0.0000 | 0.0000 |
| BIL_cash_proxy | active_normal | normal | 0.0000 | 0.0000 | 0.0000 |
| current_no_cash_proxy_alpha_AB | active_normal | normal | 0.0000 | 0.0000 | 0.0000 |
| combo_SPY200d_GLD_50_50_v1 | active_normal | normal | 0.0000 | 0.0000 | 0.0000 |

SPY_200d_trend_model remains governed by `balanced_speculative_research_v1`. The observation should continue only while fixed rules remain unchanged and the row stays inside the project stop framework.

## 11. Monthly Decision Checkpoint

| checkpoint_month | latest_observation_end_date | primary_strategy | primary_current_equity | primary_target_300_distance | primary_target_400_distance | primary_distance_to_absolute_stop | primary_distance_to_trailing_stop | primary_risk_band | decision | decision_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2026-06 | 2026-06-05 | SPY_200d_trend_model | 2998.5000 | 301.5000 | 401.5000 | 598.5000 | 600.0000 | normal | inconclusive_too_early | Elapsed trading days are below 30, so the monthly checkpoint is too early for a decision. |
| 2026-06 | 2026-06-05 | combo_SPY200d_GLD_50_50_v1 | 2904.9679 | 395.0321 | 495.0321 | 504.9679 | 600.0000 | normal | inconclusive_too_early | Combo observation is included beside SPY_200d; no judgment is allowed before 30 trading days. |

The checkpoint is a decision aid only. It forbids rule changes, parameter tuning, real-money trading, broker integration, and adding diagnostic rows to the active paper-forward observation.

## 12. Historical Expectation Comparison

| strategy | historical_90d_pct_target_300_before_stop | historical_90d_pct_target_400_before_stop | historical_90d_pct_any_stop_hit | historical_90d_median_stop_enforced_equity | historical_90d_worst_drawdown | current_vs_historical_status |
| --- | --- | --- | --- | --- | --- | --- |
| SPY_200d_trend_model | 0.2381 | 0.0987 | 0.0046 | 3095.5867 | -661.4912 | too_early_to_compare_to_90d_distribution |
| SPY_buy_hold | 0.3150 | 0.1496 | 0.0643 | 3152.5499 | -1329.5805 | too_early_to_compare_to_90d_distribution |
| BIL_cash_proxy | 0.0000 | 0.0000 | 0.0000 | 3000.4624 | -24.6742 | too_early_to_compare_to_90d_distribution |
| current_no_cash_proxy_alpha_AB | 0.1260 | 0.0340 | 0.0000 | 3024.7900 | -406.0200 | too_early_to_compare_to_90d_distribution |
| combo_SPY200d_GLD_50_50_v1 | nan | nan | nan | 3000.0000 | nan | too_early_to_compare_to_90d_distribution |

The historical context comes from the exact compact challenge audit baseline. It is not a prediction and does not validate real-money use.

## 13. Combo Parallel Observation Status

- combo_strategy: combo_SPY200d_GLD_50_50_v1
- combo_status: active_paper_demo_observation
- combo_rule_hash_verified: True
- combo_canonical_rule_hash: 6695f0d3ec403e2f377d99f3f63d1fc57a66f45f2c27a9072ab8c0a60a19ee67
- combo_replaces_spy200d: false
- SPY_200d_frozen_control: true
- combo_current_equity_if_available: $2,904.97
- combo_distance_to_300_if_available: $395.03
- combo_distance_to_400_if_available: $495.03
- combo_distance_to_stop_if_available: $504.97
- combo_vs_spy200d_equity_difference: $-93.53
- activation_note: Combo is active as a separate simulated paper/demo observation because the canonical rule hash is verified and cached data supports the requested activation date.

The combo does not replace SPY_200d. SPY_200d remains the frozen paper-forward control until a separate governance decision says otherwise.

## 14. Rule Or Data Issues

current_no_cash_proxy_alpha_AB equity was replayed with existing fixed rules, but compact latest-signal extraction is marked unavailable rather than invented.

The combo row must not become active without a verified canonical rule hash and cached data through the observation start date. No data was downloaded in this run.

## 15. Observation Active?

True

## 16. Success Criteria

Success is reaching +$300 or +$400 before either project stop, while fixed rules remain unchanged.

## 17. Failure Criteria

Failure is hitting the absolute or trailing project stop, or discovering data/signal extraction problems that make the observation unauditable.

## 18. Final Current Conclusion

SPY_200d_trend_model is active_observation with equity $2,998.50. It is $301.50 from +$300 and $600.00 above the trailing stop. No real-money action is implied.

Closest to +$300: current_no_cash_proxy_alpha_AB. Largest drawdown so far: SPY_200d_trend_model. This remains research-only paper observation.
