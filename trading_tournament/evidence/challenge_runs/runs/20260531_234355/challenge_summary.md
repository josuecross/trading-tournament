# Challenge Summary

## 1. Research-Only Statement

This compact challenge audit is paper/demo research only. It does not recommend real-money trading, does not connect to a broker or exchange, and does not place orders.

## 2. Run Identity

- run_id: 20260531_234355
- output: `evidence/challenge_runs/runs/20260531_234355/`
- compact file count: 10
- validation_mode: candidate_exhaustive
- sampled_results_are_final: True
- final_validation_completed: True

## 3. What Was Tested

focused exact ETF finalist, ETF benchmarks, Tier 1 SPY_200d exposure frontier diagnostics.

## 4. What Was Not Tested

Individual stocks, options, futures, forex, crypto perpetuals/futures, volatility products, intraday strategies, event/news strategies, live trading, broker integration, exchange execution, margin, shorting, and real order placement.

## 5. Account Assumptions

Each row is an independent $3,000 simulated challenge account. Targets are $3,300 and $3,400. Stops are $2,400 absolute floor and high-water mark minus $600, with mode `both`.

## 6. Best Result By +300 Before Stop

simulated_etf_exposure_frontier / SPY_200d_exposure_frontier_1_25x (1.25x): +300 90d 33.8%, +400 90d 19.6%, stop 90d 3.5%.

## 7. Best Result By +400 Before Stop

simulated_etf_exposure_frontier / SPY_200d_exposure_frontier_1_25x (1.25x): +300 90d 33.8%, +400 90d 19.6%, stop 90d 3.5%.

## 8. Best Risk-Controlled Result

etf_validated_lane / current_no_cash_proxy_alpha_AB (1.0x): +300 90d 12.6%, +400 90d 3.4%, stop 90d 0.0%.

## ETF Benchmark Rolling Rows

ETF benchmark rolling rows are present for SPY_buy_hold, SPY_200d_trend_model, and BIL_cash_proxy at 30/60/90/180 days for standard and stress labels; quality labels: exact.

## current_no_cash_proxy_alpha_AB Benchmark Comparison

- current_no_cash_proxy_alpha_AB: +300 12.6%, +400 3.4%, stop 0.0%, median stop equity 3024.79, worst drawdown -406.02.
- SPY_buy_hold: +300 32.9%, +400 15.8%, stop 6.8%, median stop equity 3162.17, worst drawdown -1329.58. Focus beats +300=False, +400=False, stop-rate=True, median-stop-equity=False, worst-drawdown=True.
- SPY_200d_trend_model: +300 25.1%, +400 10.4%, stop 0.5%, median stop equity 3114.12, worst drawdown -661.49. Focus beats +300=False, +400=False, stop-rate=True, median-stop-equity=False, worst-drawdown=True.
- BIL_cash_proxy: +300 0.0%, +400 0.0%, stop 0.0%, median stop equity 2999.81, worst drawdown -24.67. Focus beats +300=True, +400=True, stop-rate=True, median-stop-equity=True, worst-drawdown=False.

## Exact 90-Day Focus Table

Standard:

| Strategy | +300 before stop | +400 before stop | Any stop hit | Median stop-enforced equity | Worst drawdown | Final? |
|---|---:|---:|---:|---:|---:|---|
| current_no_cash_proxy_alpha_AB | 12.6% | 3.4% | 0.0% | $3,024.79 | $-406.02 | True |
| SPY_buy_hold | 32.9% | 15.8% | 6.8% | $3,162.17 | $-1,329.58 | True |
| SPY_200d_trend_model | 25.1% | 10.4% | 0.5% | $3,114.12 | $-661.49 | True |
| BIL_cash_proxy | 0.0% | 0.0% | 0.0% | $2,999.81 | $-24.67 | True |

Stress:

| Strategy | +300 before stop | +400 before stop | Any stop hit | Median stop-enforced equity | Worst drawdown | Final? |
|---|---:|---:|---:|---:|---:|---|
| current_no_cash_proxy_alpha_AB | 11.1% | 3.5% | 0.0% | $3,007.78 | $-421.32 | True |
| SPY_buy_hold | 32.7% | 15.5% | 6.8% | $3,160.60 | $-1,328.93 | True |
| SPY_200d_trend_model | 25.0% | 10.1% | 1.2% | $3,109.14 | $-687.75 | True |
| BIL_cash_proxy | 0.0% | 0.0% | 0.0% | $2,998.31 | $-26.17 | True |

## Practical Decision

- current_no_cash_proxy_alpha_AB beats SPY_200d on +300=False, +400=False, stop-rate=True, median-stop-equity=False, worst-drawdown=True.
- SPY_buy_hold +300 rate is 32.9% versus 12.6% for current_no_cash_proxy_alpha_AB, with stop-hit 6.8% versus 0.0%. It should be penalized if its stop risk or worst drawdown is materially worse.
- SPY_200d_trend_model becomes the leading practical ETF watchlist candidate in this focused run.
- +$300 appears plausible under the exact focused 90-day ETF rows. +$400 remains low for current_no_cash_proxy_alpha_AB (3.4%) and modest for SPY_200d_trend_model (10.4%); it is not validated as reliable.

## Finalist Validation Status

Finalist validation completed with all_possible windows.

current_no_cash_proxy_alpha_AB has completed the focused candidate_exhaustive path, but remains research-only and not a real-money recommendation.

## 9. Best ETF Result

In focused `candidate_exhaustive`, current_no_cash_proxy_alpha_AB is computed or loaded only from exact all-possible Backtester evidence; benchmark rows are computed directly from cached adjusted benchmark prices on the same effective calendar. See `strategy_rankings.csv` for the compact ranking.

## 10. Best Crypto Exploratory Result

Crypto rows were not included in this focused run. Prior crypto exploratory rows remain Tier 1 only and are not comparable to ETF evidence as validated candidates.

## 11. Best Simulated Leverage Result

Simulated leverage is approximate only when included. It often increases target hit rates and stop risk at the same time, and is not a real margin/liquidation model.

## Simulated ETF Leverage Diagnostic

Simulated ETF leverage diagnostics were not enabled in this run.

No ETF leverage diagnostic decision was made in this run.

## ETF Exposure Frontier Diagnostic

| Exposure | +300 before stop | +400 before stop | Any stop hit | Worst drawdown | Stop overshoot >$50 | Stop overshoot >$100 | Verdict ceiling |
|---:|---:|---:|---:|---:|---:|---:|---|
| 1.00x | 25.1% | 10.4% | 0.5% | $-661.49 | 0.1% | 0.0% | watchlist_diagnostic |
| 1.05x | 27.3% | 12.2% | 1.8% | $-693.58 | 0.0% | 0.0% | too_risky |
| 1.10x | 29.5% | 13.9% | 3.0% | $-726.10 | 0.1% | 0.0% | too_risky |
| 1.15x | 31.1% | 16.2% | 3.4% | $-759.02 | 0.8% | 0.0% | too_risky |
| 1.20x | 32.4% | 18.0% | 3.5% | $-792.32 | 1.5% | 0.3% | too_risky |
| 1.25x | 33.8% | 19.6% | 3.5% | $-825.96 | 1.4% | 0.2% | too_risky |

1.05x changed +300 by +2.2% and +400 by +1.7% versus 1.00x. 1.10x changed +300 by +4.4% and +400 by +3.5%. 1.15x changed +300 by +5.9% and +400 by +5.8%. Stop-hit rate becomes meaningfully worse at 1.10x; worst drawdown clearly exceeds -$600 at 1.00x. Best diagnostic tradeoff: SPY_200d_exposure_frontier_1_00x (1.00x), verdict=watchlist_diagnostic, diagnostic_score=-0.11. No exposure row is paper-forward ready.

## 12. Stop-Enforced Vs Unconditional Warning

Full-period final equity can be misleading. `stop_enforced_final_equity` is the relevant challenge metric when a project stop occurs before the final data date.

## 13. Full-Period Rows That Hit +300 Before Stop

etf_validated_lane/current_no_cash_proxy_alpha_AB/1.0x, etf_benchmark/SPY_200d_trend_model/1.0x, simulated_etf_exposure_frontier/SPY_200d_exposure_frontier_1_00x/1.0x, simulated_etf_exposure_frontier/SPY_200d_exposure_frontier_1_05x/1.05x, simulated_etf_exposure_frontier/SPY_200d_exposure_frontier_1_10x/1.1x, simulated_etf_exposure_frontier/SPY_200d_exposure_frontier_1_15x/1.15x, simulated_etf_exposure_frontier/SPY_200d_exposure_frontier_1_20x/1.2x, simulated_etf_exposure_frontier/SPY_200d_exposure_frontier_1_25x/1.25x, etf_benchmark/BIL_cash_proxy/1.0x

## 14. Full-Period Rows That Hit +400 Before Stop

etf_validated_lane/current_no_cash_proxy_alpha_AB/1.0x, etf_benchmark/SPY_200d_trend_model/1.0x, simulated_etf_exposure_frontier/SPY_200d_exposure_frontier_1_00x/1.0x, simulated_etf_exposure_frontier/SPY_200d_exposure_frontier_1_05x/1.05x, simulated_etf_exposure_frontier/SPY_200d_exposure_frontier_1_10x/1.1x, simulated_etf_exposure_frontier/SPY_200d_exposure_frontier_1_15x/1.15x, simulated_etf_exposure_frontier/SPY_200d_exposure_frontier_1_20x/1.2x, simulated_etf_exposure_frontier/SPY_200d_exposure_frontier_1_25x/1.25x, etf_benchmark/BIL_cash_proxy/1.0x

## 15. Strategies That Hit Project Stop

etf_validated_lane/current_no_cash_proxy_alpha_AB/1.0x, etf_benchmark/SPY_buy_hold/1.0x, etf_benchmark/SPY_200d_trend_model/1.0x, simulated_etf_exposure_frontier/SPY_200d_exposure_frontier_1_00x/1.0x, simulated_etf_exposure_frontier/SPY_200d_exposure_frontier_1_05x/1.05x, simulated_etf_exposure_frontier/SPY_200d_exposure_frontier_1_10x/1.1x, simulated_etf_exposure_frontier/SPY_200d_exposure_frontier_1_15x/1.15x, simulated_etf_exposure_frontier/SPY_200d_exposure_frontier_1_20x/1.2x, simulated_etf_exposure_frontier/SPY_200d_exposure_frontier_1_25x/1.25x

## 16. Too Risky

Rows with high 90-day stop-hit rates, large drawdowns, or large stop-enforced penalties should be treated as too risky or exploratory only even when final-date equity is high.

## 17. Too Slow

Cash and low-volatility defensive rows are too slow for the +$300/+400 challenge unless used only as benchmarks.

## 18. Deserve Further Research

Rows with non-trivial +300-before-stop rates and manageable stop rates deserve further research, not validation claims.

## 19. Rejected Or Deferred

Unimplemented instruments remain deferred or rejected for now. Crypto leverage scenarios are not approved for live or paper-forward use.

## 20. Risk Framework v1 Decision

Framework: balanced_speculative_research_v1. Paper-forward allowed by framework in this packet: current_no_cash_proxy_alpha_AB/standard, BIL_cash_proxy/standard. Diagnostic-only or too-risky rows: SPY_200d_exposure_frontier_1_00x, SPY_200d_exposure_frontier_1_25x, SPY_200d_exposure_frontier_1_20x, SPY_200d_exposure_frontier_1_15x, SPY_200d_exposure_frontier_1_10x, SPY_200d_exposure_frontier_1_05x. Blocked/incomplete rows: none. Hard-stop band rows: SPY_200d_trend_model, SPY_200d_exposure_frontier_1_00x, SPY_buy_hold, SPY_200d_exposure_frontier_1_25x, SPY_200d_exposure_frontier_1_20x, SPY_200d_exposure_frontier_1_15x, SPY_200d_exposure_frontier_1_10x, SPY_200d_exposure_frontier_1_05x. +$300 remains the primary challenge target; +$400 remains aggressive. Exposure scaling above 1.00x remains diagnostic only. Unlevered SPY_200d remains the leading practical candidate when it has exact evidence; no row is a real-money recommendation.

## 21. Final Conclusion

SPY_200d_trend_model becomes the leading practical ETF watchlist candidate in this focused run. +$300 appears plausible under the exact focused 90-day ETF rows. +$400 remains low for current_no_cash_proxy_alpha_AB (3.4%) and modest for SPY_200d_trend_model (10.4%); it is not validated as reliable. current_no_cash_proxy_alpha_AB beats SPY_200d on +300=False, +400=False, stop-rate=True, median-stop-equity=False, worst-drawdown=True. SPY_buy_hold +300 rate is 32.9% versus 12.6% for current_no_cash_proxy_alpha_AB, with stop-hit 6.8% versus 0.0%. It should be penalized if its stop risk or worst drawdown is materially worse. 1.05x changed +300 by +2.2% and +400 by +1.7% versus 1.00x. 1.10x changed +300 by +4.4% and +400 by +3.5%. 1.15x changed +300 by +5.9% and +400 by +5.8%. Stop-hit rate becomes meaningfully worse at 1.10x; worst drawdown clearly exceeds -$600 at 1.00x. Best diagnostic tradeoff: SPY_200d_exposure_frontier_1_00x (1.00x), verdict=watchlist_diagnostic, diagnostic_score=-0.11. No exposure row is paper-forward ready. This is still paper/demo research only, not a real-money recommendation.
