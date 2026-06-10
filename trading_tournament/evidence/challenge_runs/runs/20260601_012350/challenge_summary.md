# Challenge Summary

## 1. Research-Only Statement

This compact challenge audit is paper/demo research only. It does not recommend real-money trading, does not connect to a broker or exchange, and does not place orders.

## 2. Run Identity

- run_id: 20260601_012350
- output: `evidence/challenge_runs/runs/20260601_012350/`
- compact file count: 10
- validation_mode: candidate_exhaustive
- sampled_results_are_final: True
- final_validation_completed: True

## 3. What Was Tested

focused exact ETF finalist, ETF benchmarks, Tier 1 SPY_200d volatility-control diagnostics.

## 4. What Was Not Tested

Individual stocks, options, futures, forex, crypto perpetuals/futures, volatility products, intraday strategies, event/news strategies, live trading, broker integration, exchange execution, margin, shorting, and real order placement.

## 5. Account Assumptions

Each row is an independent $3,000 simulated challenge account. Targets are $3,300 and $3,400. Stops are $2,400 absolute floor and high-water mark minus $600, with mode `both`.

## 6. Best Result By +300 Before Stop

etf_benchmark / SPY_buy_hold (1.0x): +300 90d 32.9%, +400 90d 15.8%, stop 90d 6.8%.

## 7. Best Result By +400 Before Stop

etf_benchmark / SPY_buy_hold (1.0x): +300 90d 32.9%, +400 90d 15.8%, stop 90d 6.8%.

## 8. Best Risk-Controlled Result

etf_volatility_control_diagnostic / SPY_200d_vol_target_12_cap_1_10_v1 (1.0x): +300 90d 16.7%, +400 90d 4.7%, stop 90d 0.0%.

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

Simulated leverage rows were not included in this focused run. When included, they are approximate scenarios only and are not a real margin/liquidation model.

## Simulated ETF Leverage Diagnostic

Simulated ETF leverage diagnostics were not enabled in this run.

No ETF leverage diagnostic decision was made in this run.

## ETF Exposure Frontier Diagnostic

ETF exposure frontier diagnostics were not enabled in this run.

No exposure frontier decision was made in this run.

## ETF Volatility-Control Diagnostic

| Strategy | +300 before stop | +400 before stop | Any stop hit | Worst drawdown | Average exposure | Verdict ceiling |
|---|---:|---:|---:|---:|---:|---|
| SPY_200d_trend_model | 25.1% | 10.4% | 0.5% | $-661.49 | nan | baseline |
| SPY_200d_vol_target_12_cap_1_00_v1 | 14.9% | 3.5% | 0.0% | $-498.70 | 0.68 | too_slow |
| SPY_200d_vol_target_12_cap_1_10_v1 | 16.7% | 4.7% | 0.0% | $-516.86 | 0.71 | exploratory_only |

Cap 1.00 changed +300 by -10.2%, +400 by -6.9%, stop-hit by -0.5%, and worst drawdown by $162.79. Cap 1.10 changed +300 by -8.4%, +400 by -5.7%, stop-hit by -0.5%, and worst drawdown by $144.63. Best volatility-control diagnostic tradeoff: SPY_200d_vol_target_12_cap_1_00_v1 (too_slow). No volatility-control row deserves Tier 2 review from this packet because the target-probability loss is too large or the row remains merely exploratory. No volatility-control row is paper-forward ready.

## 12. Stop-Enforced Vs Unconditional Warning

Full-period final equity can be misleading. `stop_enforced_final_equity` is the relevant challenge metric when a project stop occurs before the final data date.

## 13. Full-Period Rows That Hit +300 Before Stop

etf_validated_lane/current_no_cash_proxy_alpha_AB/1.0x, etf_benchmark/SPY_200d_trend_model/1.0x, etf_volatility_control_diagnostic/SPY_200d_vol_target_12_cap_1_00_v1/1.0x, etf_volatility_control_diagnostic/SPY_200d_vol_target_12_cap_1_10_v1/1.0x, etf_benchmark/BIL_cash_proxy/1.0x

## 14. Full-Period Rows That Hit +400 Before Stop

etf_validated_lane/current_no_cash_proxy_alpha_AB/1.0x, etf_benchmark/SPY_200d_trend_model/1.0x, etf_volatility_control_diagnostic/SPY_200d_vol_target_12_cap_1_00_v1/1.0x, etf_volatility_control_diagnostic/SPY_200d_vol_target_12_cap_1_10_v1/1.0x, etf_benchmark/BIL_cash_proxy/1.0x

## 15. Strategies That Hit Project Stop

etf_validated_lane/current_no_cash_proxy_alpha_AB/1.0x, etf_benchmark/SPY_buy_hold/1.0x, etf_benchmark/SPY_200d_trend_model/1.0x, etf_volatility_control_diagnostic/SPY_200d_vol_target_12_cap_1_00_v1/1.0x, etf_volatility_control_diagnostic/SPY_200d_vol_target_12_cap_1_10_v1/1.0x

## 16. Too Risky

Rows with high 90-day stop-hit rates, large drawdowns, or large stop-enforced penalties should be treated as too risky or exploratory only even when final-date equity is high.

## 17. Too Slow

Cash and low-volatility defensive rows are too slow for the +$300/+400 challenge unless used only as benchmarks.

## 18. Deserve Further Research

Rows with non-trivial +300-before-stop rates and manageable stop rates deserve further research, not validation claims.

## 19. Rejected Or Deferred

Unimplemented instruments remain deferred or rejected for now. Crypto leverage scenarios are not approved for live or paper-forward use.

## 20. Risk Framework v1 Decision

Framework: balanced_speculative_research_v1. Paper-forward allowed by framework in this packet: SPY_200d_trend_model/standard, current_no_cash_proxy_alpha_AB/standard, BIL_cash_proxy/standard. Diagnostic-only or too-risky rows: SPY_200d_vol_target_12_cap_1_00_v1, SPY_200d_vol_target_12_cap_1_10_v1. Blocked/incomplete rows: none. Hard-stop band rows: SPY_200d_trend_model, SPY_buy_hold. +$300 remains the primary challenge target; +$400 remains aggressive. Exposure scaling above 1.00x remains diagnostic only. Unlevered SPY_200d remains the leading practical candidate when it has exact evidence; no row is a real-money recommendation.

## 21. Final Conclusion

SPY_200d_trend_model becomes the leading practical ETF watchlist candidate in this focused run. +$300 appears plausible under the exact focused 90-day ETF rows. +$400 remains low for current_no_cash_proxy_alpha_AB (3.4%) and modest for SPY_200d_trend_model (10.4%); it is not validated as reliable. current_no_cash_proxy_alpha_AB beats SPY_200d on +300=False, +400=False, stop-rate=True, median-stop-equity=False, worst-drawdown=True. SPY_buy_hold +300 rate is 32.9% versus 12.6% for current_no_cash_proxy_alpha_AB, with stop-hit 6.8% versus 0.0%. It should be penalized if its stop risk or worst drawdown is materially worse. Cap 1.00 changed +300 by -10.2%, +400 by -6.9%, stop-hit by -0.5%, and worst drawdown by $162.79. Cap 1.10 changed +300 by -8.4%, +400 by -5.7%, stop-hit by -0.5%, and worst drawdown by $144.63. Best volatility-control diagnostic tradeoff: SPY_200d_vol_target_12_cap_1_00_v1 (too_slow). No volatility-control row deserves Tier 2 review from this packet because the target-probability loss is too large or the row remains merely exploratory. No volatility-control row is paper-forward ready. This is still paper/demo research only, not a real-money recommendation.
