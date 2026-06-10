# Paper-Forward Observation Summary

## 1. Research-Only Statement

This is paper/demo observation only. It does not recommend real-money trading, does not connect to a broker, and does not place orders.

## 2. Run Identity

- run_id: 20260531_234928
- output: `evidence/paper_forward_runs/runs/20260531_234928/`
- compact file count: 10

## 3. Observation Period

- start: 2026-05-01
- end: 2026-05-29

## 4. Strategies Observed

SPY_200d_trend_model, current_no_cash_proxy_alpha_AB, SPY_buy_hold, and BIL_cash_proxy. Each row has its own independent $3,000 simulated paper account.

## 5. Current Status Table

| strategy | role | current_equity | current_return | status | signal_state | current_position_symbols |
| --- | --- | --- | --- | --- | --- | --- |
| SPY_200d_trend_model | primary_watchlist_candidate | 3147.5822 | 0.0492 | active_observation | risk_on | SPY |
| SPY_buy_hold | aggressive_benchmark | 3147.5822 | 0.0492 | active_observation | hold_spy | SPY |
| BIL_cash_proxy | defensive_benchmark | 3007.0297 | 0.0023 | active_observation | hold_bil | BIL |
| current_no_cash_proxy_alpha_AB | strategy_control | 2908.0136 | -0.0307 | active_observation | engine_replayed_signal_snapshot_unavailable | XLK |

## 6. Current Signals

| strategy | symbol | signal | target_weight | reason | data_quality_flag |
| --- | --- | --- | --- | --- | --- |
| SPY_200d_trend_model | SPY | risk_on | 1.0000 | SPY close > 200-day SMA | ok |
| SPY_200d_trend_model | BIL | not_selected | 0.0000 | BIL receives weight when SPY is below/at SMA200 or SPY SMA is unavailable. | ok |
| SPY_buy_hold | SPY | hold_spy | 1.0000 | Fixed benchmark holding. | ok |
| BIL_cash_proxy | BIL | hold_bil | 1.0000 | Fixed benchmark holding. | ok |
| current_no_cash_proxy_alpha_AB |  | unavailable | nan | Existing A/B engine was replayed for equity, but it does not expose a compact latest-signal API here; no signal invented. | signal_snapshot_unavailable |

## 7. Distance To +300/+400 Targets

| strategy | risk_status | current_equity | target_300_distance | distance_to_trailing_stop | max_drawdown_dollars |
| --- | --- | --- | --- | --- | --- |
| SPY_200d_trend_model | normal | 3147.5822 | 152.4178 | 600.0000 | -60.0824 |
| SPY_buy_hold | normal | 3147.5822 | 152.4178 | 600.0000 | -60.0824 |
| BIL_cash_proxy | normal | 3007.0297 | 292.9703 | 600.0000 | -0.3281 |
| current_no_cash_proxy_alpha_AB | normal | 2908.0136 | 391.9864 | 360.8866 | -261.4057 |

## 8. Distance To Stops

See `risk_status.csv`; stop mode is both absolute floor $2,400 and high-water mark minus $600.

## 9. Historical 90-Day Context

| strategy | current_vs_historical_status | historical_90d_pct_target_300_before_stop | historical_90d_pct_any_stop_hit |
| --- | --- | --- | --- |
| SPY_200d_trend_model | too_early_to_compare_to_90d_distribution | 0.2513 | 0.0048 |
| SPY_buy_hold | too_early_to_compare_to_90d_distribution | 0.3288 | 0.0678 |
| BIL_cash_proxy | too_early_to_compare_to_90d_distribution | 0.0000 | 0.0000 |
| current_no_cash_proxy_alpha_AB | too_early_to_compare_to_90d_distribution | 0.1262 | 0.0000 |

## 10. Risk Framework Status

| strategy | risk_framework_status | risk_band | risk_budget_used_pct | target_300_progress_pct | target_400_progress_pct |
| --- | --- | --- | --- | --- | --- |
| SPY_200d_trend_model | active_normal | normal | 0.1001 | 0.4919 | 0.3690 |
| SPY_buy_hold | active_normal | normal | 0.1001 | 0.4919 | 0.3690 |
| BIL_cash_proxy | active_normal | normal | 0.0005 | 0.0234 | 0.0176 |
| current_no_cash_proxy_alpha_AB | active_normal | normal | 0.4357 | 0.0000 | 0.0000 |

SPY_200d_trend_model remains governed by `balanced_speculative_research_v1`. The observation should continue only while fixed rules remain unchanged and the row stays inside the project stop framework.

## 11. Rule Or Data Issues

current_no_cash_proxy_alpha_AB equity was replayed with existing fixed rules, but compact latest-signal extraction is marked unavailable rather than invented.

## 12. Observation Active?

True

## 13. Success Criteria

Success is reaching +$300 or +$400 before either project stop, while fixed rules remain unchanged.

## 14. Failure Criteria

Failure is hitting the absolute or trailing project stop, or discovering data/signal extraction problems that make the observation unauditable.

## 15. Final Current Conclusion

SPY_200d_trend_model is active_observation with equity $3,147.58. It is $152.42 from +$300 and $600.00 above the trailing stop. No real-money action is implied.

Closest to +$300: SPY_200d_trend_model. Largest drawdown so far: current_no_cash_proxy_alpha_AB. This remains research-only paper observation.
