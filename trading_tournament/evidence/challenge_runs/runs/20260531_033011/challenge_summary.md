# Challenge Summary

## 1. Research-Only Statement

This compact challenge audit is paper/demo research only. It does not recommend real-money trading, does not connect to a broker or exchange, and does not place orders.

## 2. Run Identity

- run_id: 20260531_033011
- output: `evidence/challenge_runs/20260531_033011/`
- compact file count: 10

## 3. What Was Tested

Implemented daily ETF evidence summaries, implemented long-only crypto spot exploratory strategies, BTC/ETH buy-and-hold benchmarks, and approximate simulated leverage scenarios.

## 4. What Was Not Tested

Individual stocks, options, futures, forex, crypto perpetuals/futures, volatility products, intraday strategies, event/news strategies, live trading, broker integration, exchange execution, margin, shorting, and real order placement.

## 5. Account Assumptions

Each row is an independent $3,000 simulated challenge account. Targets are $3,300 and $3,400. Stops are $2,400 absolute floor and high-water mark minus $600, with mode `both`.

## 6. Best Result By +300 Before Stop

simulated_leverage_scenario / crypto_buy_hold_equal_weight (2.0x): +300 90d 71.6%, +400 90d 64.8%, stop 90d 94.4%.

## 7. Best Result By +400 Before Stop

simulated_leverage_scenario / crypto_buy_hold_equal_weight (2.0x): +300 90d 71.6%, +400 90d 64.8%, stop 90d 94.4%.

## 8. Best Risk-Controlled Result

etf_validated_lane / current_no_cash_proxy_alpha_AB (1.0x): +300 90d 18.6%, +400 90d 4.8%, stop 90d 0.0%.

## 9. Best ETF Result

ETF rows are loaded from existing evidence summaries. See `strategy_rankings.csv`; ETF results have higher credibility than crypto Tier 1 rows but some compact stop-enforced values are approximated from summary drawdowns.

## 10. Best Crypto Exploratory Result

Crypto rows remain Tier 1 exploratory. Large final-date crypto equity is not enough because many rows also hit project stops.

## 11. Best Simulated Leverage Result

Simulated leverage is approximate only. It often increases target hit rates and stop risk at the same time, and is not a real margin/liquidation model.

## 12. Stop-Enforced Vs Unconditional Warning

Full-period final equity can be misleading. `stop_enforced_final_equity` is the relevant challenge metric when a project stop occurs before the final data date.

## 13. Strategies That Hit +300 Before Stop

etf_validated_lane/current_no_cash_proxy_alpha_AB/1.0x, etf_validated_lane/current_core_only_AB/1.0x, etf_validated_lane/current_momentum_only_A/1.0x, etf_benchmark/SPY_200d_trend_model/1.0x, crypto_spot_momentum/BTC_buy_hold/1.0x, simulated_leverage_scenario/BTC_buy_hold/1.5x, simulated_leverage_scenario/BTC_buy_hold/2.0x, crypto_spot_momentum/ETH_buy_hold/1.0x, simulated_leverage_scenario/ETH_buy_hold/1.5x, simulated_leverage_scenario/ETH_buy_hold/2.0x, crypto_spot_momentum/crypto_time_series_momentum/1.0x, simulated_leverage_scenario/crypto_time_series_momentum/1.5x, simulated_leverage_scenario/crypto_time_series_momentum/2.0x, crypto_spot_momentum/crypto_dual_momentum_cash_filter/1.0x, simulated_leverage_scenario/crypto_dual_momentum_cash_filter/1.5x, simulated_leverage_scenario/crypto_dual_momentum_cash_filter/2.0x

## 14. Strategies That Hit +400 Before Stop

etf_validated_lane/current_no_cash_proxy_alpha_AB/1.0x, etf_validated_lane/current_core_only_AB/1.0x, etf_validated_lane/current_momentum_only_A/1.0x, etf_benchmark/SPY_200d_trend_model/1.0x, crypto_spot_momentum/BTC_buy_hold/1.0x, simulated_leverage_scenario/BTC_buy_hold/1.5x, simulated_leverage_scenario/BTC_buy_hold/2.0x, crypto_spot_momentum/ETH_buy_hold/1.0x, simulated_leverage_scenario/ETH_buy_hold/1.5x, simulated_leverage_scenario/ETH_buy_hold/2.0x, crypto_spot_momentum/crypto_time_series_momentum/1.0x, simulated_leverage_scenario/crypto_time_series_momentum/1.5x, simulated_leverage_scenario/crypto_time_series_momentum/2.0x, crypto_spot_momentum/crypto_dual_momentum_cash_filter/1.0x, simulated_leverage_scenario/crypto_dual_momentum_cash_filter/1.5x, simulated_leverage_scenario/crypto_dual_momentum_cash_filter/2.0x

## 15. Strategies That Hit Project Stop

etf_validated_lane/current_no_cash_proxy_alpha_AB/1.0x, etf_validated_lane/current_core_only_AB/1.0x, etf_validated_lane/current_momentum_only_A/1.0x, etf_benchmark/SPY_buy_hold/1.0x, etf_benchmark/SPY_200d_trend_model/1.0x, crypto_spot_momentum/BTC_buy_hold/1.0x, simulated_leverage_scenario/BTC_buy_hold/1.5x, simulated_leverage_scenario/BTC_buy_hold/2.0x, crypto_spot_momentum/ETH_buy_hold/1.0x, simulated_leverage_scenario/ETH_buy_hold/1.5x, simulated_leverage_scenario/ETH_buy_hold/2.0x, crypto_spot_momentum/crypto_buy_hold_equal_weight/1.0x, simulated_leverage_scenario/crypto_buy_hold_equal_weight/1.5x, simulated_leverage_scenario/crypto_buy_hold_equal_weight/2.0x, crypto_spot_momentum/crypto_time_series_momentum/1.0x, simulated_leverage_scenario/crypto_time_series_momentum/1.5x, simulated_leverage_scenario/crypto_time_series_momentum/2.0x, crypto_spot_momentum/crypto_cross_sectional_momentum/1.0x, simulated_leverage_scenario/crypto_cross_sectional_momentum/1.5x, simulated_leverage_scenario/crypto_cross_sectional_momentum/2.0x, crypto_spot_momentum/crypto_dual_momentum_cash_filter/1.0x, simulated_leverage_scenario/crypto_dual_momentum_cash_filter/1.5x, simulated_leverage_scenario/crypto_dual_momentum_cash_filter/2.0x

## 16. Too Risky

Rows with high 90-day stop-hit rates, large drawdowns, or large stop-enforced penalties should be treated as too risky or exploratory only even when final-date equity is high.

## 17. Too Slow

Cash and low-volatility defensive rows are too slow for the +$300/+400 challenge unless used only as benchmarks.

## 18. Deserve Further Research

Rows with non-trivial +300-before-stop rates and manageable stop rates deserve further research, not validation claims.

## 19. Rejected Or Deferred

Unimplemented instruments remain deferred or rejected for now. Crypto leverage scenarios are not approved for live or paper-forward use.

## 20. Final Conclusion

+$300 and +$400 are possible in these tests, especially in volatile crypto windows and some ETF evidence rows, but possible does not mean reliable. Crypto appears more likely to reach targets quickly, with much higher stop risk and lower credibility. ETF results are more credible but generally slower and less explosive. The next practical step is to compare stop-enforced rolling behavior, not chase high unconditional final equity.
