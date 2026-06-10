# Challenge Summary

## 1. Research-Only Statement

This compact challenge audit is paper/demo research only. It does not recommend real-money trading, does not connect to a broker or exchange, and does not place orders.

## 2. Run Identity

- run_id: 20260531_150829
- output: `evidence/challenge_runs/20260531_150829/`
- compact file count: 10
- validation_mode: candidate_exhaustive
- sampled_results_are_final: False
- final_validation_completed: False

## 3. What Was Tested

Implemented daily ETF evidence summaries, implemented long-only crypto spot exploratory strategies, BTC/ETH buy-and-hold benchmarks, and approximate simulated leverage scenarios.

## 4. What Was Not Tested

Individual stocks, options, futures, forex, crypto perpetuals/futures, volatility products, intraday strategies, event/news strategies, live trading, broker integration, exchange execution, margin, shorting, and real order placement.

## 5. Account Assumptions

Each row is an independent $3,000 simulated challenge account. Targets are $3,300 and $3,400. Stops are $2,400 absolute floor and high-water mark minus $600, with mode `both`.

## 6. Best Result By +300 Before Stop

etf_benchmark / SPY_buy_hold (1.0x): +300 90d 31.5%, +400 90d 15.0%, stop 90d 6.4%.

## 7. Best Result By +400 Before Stop

etf_benchmark / SPY_buy_hold (1.0x): +300 90d 31.5%, +400 90d 15.0%, stop 90d 6.4%.

## 8. Best Risk-Controlled Result

etf_validated_lane / current_no_cash_proxy_alpha_AB (1.0x): +300 90d 18.6%, +400 90d 4.8%, stop 90d 0.0%.

## ETF Benchmark Rolling Rows

ETF benchmark rolling rows are present for 90-day standard comparisons; quality labels: exact.

## current_no_cash_proxy_alpha_AB Benchmark Comparison

- current_no_cash_proxy_alpha_AB: +300 18.6%, +400 4.8%, stop 0.0%, median stop equity 3044.69, worst drawdown -341.37.
- SPY_buy_hold: +300 31.5%, +400 15.0%, stop 6.4%, median stop equity 3152.55, worst drawdown -1329.58. Focus beats +300=False, +400=False, stop-rate=True.
- SPY_200d_trend_model: +300 23.8%, +400 9.9%, stop 0.5%, median stop equity 3095.59, worst drawdown -661.49. Focus beats +300=False, +400=False, stop-rate=True.
- BIL_cash_proxy: +300 0.0%, +400 0.0%, stop 0.0%, median stop equity 3000.46, worst drawdown -24.67. Focus beats +300=True, +400=True, stop-rate=True.

## 9. Best ETF Result

ETF strategy rows are loaded from existing evidence summaries. See `strategy_rankings.csv`; ETF results have higher credibility than crypto Tier 1 rows, but compact ETF strategy stop-enforced values are marked approximate unless computed from an equity curve. ETF benchmark rows are computed directly from cached adjusted benchmark prices.

## 10. Best Crypto Exploratory Result

Crypto rows remain Tier 1 exploratory. Large final-date crypto equity is not enough because many rows also hit project stops.

## 11. Best Simulated Leverage Result

Simulated leverage is approximate only. It often increases target hit rates and stop risk at the same time, and is not a real margin/liquidation model.

## 12. Stop-Enforced Vs Unconditional Warning

Full-period final equity can be misleading. `stop_enforced_final_equity` is the relevant challenge metric when a project stop occurs before the final data date.

## 13. Strategies That Hit +300 Before Stop

etf_validated_lane/current_no_cash_proxy_alpha_AB/1.0x, etf_benchmark/SPY_buy_hold/1.0x, etf_benchmark/SPY_200d_trend_model/1.0x, etf_benchmark/BIL_cash_proxy/1.0x

## 14. Strategies That Hit +400 Before Stop

etf_validated_lane/current_no_cash_proxy_alpha_AB/1.0x, etf_benchmark/SPY_200d_trend_model/1.0x, etf_benchmark/BIL_cash_proxy/1.0x

## 15. Strategies That Hit Project Stop

etf_validated_lane/current_no_cash_proxy_alpha_AB/1.0x, etf_benchmark/SPY_buy_hold/1.0x, etf_benchmark/SPY_200d_trend_model/1.0x

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
