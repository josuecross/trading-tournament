# Challenge Summary

## 1. Research-Only Statement

This compact challenge audit is paper/demo research only. It does not recommend real-money trading, does not connect to a broker or exchange, and does not place orders.

## 2. Run Identity

- run_id: 20260601_040922
- output: `evidence/challenge_runs/runs/20260601_040922/`
- compact file count: 10
- validation_mode: candidate_exhaustive
- sampled_results_are_final: False
- final_validation_completed: False

## 3. What Was Tested

focused exact ETF finalist, ETF benchmarks, fixed diversified portfolio challenge diagnostics.

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

ETF benchmark rolling rows are present for SPY_buy_hold, SPY_200d_trend_model, and BIL_cash_proxy at 30/60/90/180 days for standard and stress labels; quality labels: exact.

## current_no_cash_proxy_alpha_AB Benchmark Comparison

- current_no_cash_proxy_alpha_AB: +300 18.6%, +400 4.8%, stop 0.0%, median stop equity 3044.69, worst drawdown -341.37.
- SPY_buy_hold: +300 31.5%, +400 15.0%, stop 6.4%, median stop equity 3152.55, worst drawdown -1329.58. Focus beats +300=False, +400=False, stop-rate=True, median-stop-equity=False, worst-drawdown=True.
- SPY_200d_trend_model: +300 23.8%, +400 9.9%, stop 0.5%, median stop equity 3095.59, worst drawdown -661.49. Focus beats +300=False, +400=False, stop-rate=True, median-stop-equity=False, worst-drawdown=True.
- BIL_cash_proxy: +300 0.0%, +400 0.0%, stop 0.0%, median stop equity 3000.46, worst drawdown -24.67. Focus beats +300=True, +400=True, stop-rate=True, median-stop-equity=True, worst-drawdown=False.

## Exact 90-Day Focus Table

Standard:

| Strategy | +300 before stop | +400 before stop | Any stop hit | Median stop-enforced equity | Worst drawdown | Final? |
|---|---:|---:|---:|---:|---:|---|
| current_no_cash_proxy_alpha_AB | 18.6% | 4.8% | 0.0% | $3,044.69 | $-341.37 | False |
| SPY_buy_hold | 31.5% | 15.0% | 6.4% | $3,152.55 | $-1,329.58 | True |
| SPY_200d_trend_model | 23.8% | 9.9% | 0.5% | $3,095.59 | $-661.49 | True |
| BIL_cash_proxy | 0.0% | 0.0% | 0.0% | $3,000.46 | $-24.67 | True |

Stress:

| Strategy | +300 before stop | +400 before stop | Any stop hit | Median stop-enforced equity | Worst drawdown | Final? |
|---|---:|---:|---:|---:|---:|---|
| current_no_cash_proxy_alpha_AB | 15.6% | 5.2% | 0.0% | $3,025.21 | $-340.73 | False |
| SPY_buy_hold | 31.3% | 14.7% | 6.4% | $3,150.97 | $-1,328.93 | True |
| SPY_200d_trend_model | 23.6% | 9.6% | 1.1% | $3,090.96 | $-687.75 | True |
| BIL_cash_proxy | 0.0% | 0.0% | 0.0% | $2,998.97 | $-26.17 | True |

## Practical Decision

- current_no_cash_proxy_alpha_AB vs SPY_200d_trend_model comparison is non-final.
- SPY_buy_hold +300 rate is 31.5% versus 18.6% for current_no_cash_proxy_alpha_AB, with stop-hit 6.4% versus 0.0%. It should be penalized if its stop risk or worst drawdown is materially worse.
- validation incomplete
- +$300/+400 remain unresolved until exact finalist rows complete.

## Finalist Validation Status

Finalist validation is incomplete/non-final. Focused candidate_exhaustive is incomplete because selected ETF finalist all_possible rolling is unavailable from compact evidence or runtime budget was exceeded.

current_no_cash_proxy_alpha_AB may be considered only as a research watchlist/finalist candidate until exact finalist validation is complete.

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

ETF volatility-control diagnostics were not enabled in this run.

No volatility-control diagnostic decision was made in this run.

## Diversified Portfolio Challenge

| Portfolio | Role | +300 before stop | +400 before stop | Any stop hit | Median stop equity | Worst drawdown | Verdict |
|---|---|---:|---:|---:|---:|---:|---|
| portfolio_spy200d_100_v1 | baseline_candidate | 23.8% | 9.8% | 0.5% | $3,095.59 | $-661.49 | watchlist_diagnostic |
| portfolio_spy200d_60_ief_20_bil_20_v1 | bond_defensive_mix | 2.8% | 0.4% | 0.0% | $3,067.78 | $-354.83 | too_slow |
| portfolio_spy200d_60_ief_20_gld_10_bil_10_v1 | multi_asset_defensive_mix | 4.9% | 0.9% | 0.0% | $3,081.24 | $-365.07 | too_slow |
| portfolio_spy200d_70_ab_20_bil_10_v1 | strategy_diversification_mix | 6.5% | 1.3% | 0.0% | $3,070.21 | $-472.30 | incomplete_evidence |
| portfolio_spy200d_70_bil_30_v1 | defensive_mix | 6.5% | 1.3% | 0.0% | $3,070.21 | $-472.30 | too_slow |
| portfolio_spy200d_70_gld_15_bil_15_v1 | gold_defensive_mix | 11.0% | 2.3% | 0.0% | $3,084.44 | $-455.16 | too_slow |
| portfolio_spy200d_80_ab_20_v1 | strategy_diversification_mix | 12.4% | 2.4% | 0.0% | $3,078.96 | $-536.26 | incomplete_evidence |
| portfolio_spy200d_80_bil_20_v1 | defensive_mix | 12.4% | 2.4% | 0.0% | $3,078.96 | $-536.26 | too_slow |

Unavailable portfolios: portfolio_spy200d_70_ab_20_bil_10_v1, portfolio_spy200d_80_ab_20_v1. Portfolios improving +300/stop/drawdown versus SPY_200d: none. Defensive mixes that appear too slow: portfolio_spy200d_60_ief_20_bil_20_v1, portfolio_spy200d_60_ief_20_gld_10_bil_10_v1, portfolio_spy200d_70_ab_20_bil_10_v1, portfolio_spy200d_70_bil_30_v1, portfolio_spy200d_70_gld_15_bil_15_v1, portfolio_spy200d_80_ab_20_v1, portfolio_spy200d_80_bil_20_v1. Best diagnostic tradeoff: portfolio_spy200d_100_v1 (watchlist_diagnostic), +300=23.8%, stop=0.5%, worst drawdown=$-661.49. Crypto-containing portfolios were not included in this run. No diversified portfolio becomes paper-forward ready without a separate promotion decision.

## 12. Stop-Enforced Vs Unconditional Warning

Full-period final equity can be misleading. `stop_enforced_final_equity` is the relevant challenge metric when a project stop occurs before the final data date.

## 13. Full-Period Rows That Hit +300 Before Stop

etf_validated_lane/current_no_cash_proxy_alpha_AB/1.0x, etf_benchmark/SPY_buy_hold/1.0x, etf_benchmark/SPY_200d_trend_model/1.0x, etf_benchmark/BIL_cash_proxy/1.0x, diversified_portfolio_challenge/portfolio_spy200d_100_v1/1.0x, diversified_portfolio_challenge/portfolio_spy200d_80_bil_20_v1/1.0x, diversified_portfolio_challenge/portfolio_spy200d_70_bil_30_v1/1.0x, diversified_portfolio_challenge/portfolio_spy200d_60_ief_20_bil_20_v1/1.0x, diversified_portfolio_challenge/portfolio_spy200d_70_gld_15_bil_15_v1/1.0x, diversified_portfolio_challenge/portfolio_spy200d_60_ief_20_gld_10_bil_10_v1/1.0x, diversified_portfolio_challenge/portfolio_spy200d_80_ab_20_v1/1.0x, diversified_portfolio_challenge/portfolio_spy200d_70_ab_20_bil_10_v1/1.0x

## 14. Full-Period Rows That Hit +400 Before Stop

etf_validated_lane/current_no_cash_proxy_alpha_AB/1.0x, etf_benchmark/SPY_200d_trend_model/1.0x, etf_benchmark/BIL_cash_proxy/1.0x, diversified_portfolio_challenge/portfolio_spy200d_100_v1/1.0x, diversified_portfolio_challenge/portfolio_spy200d_80_bil_20_v1/1.0x, diversified_portfolio_challenge/portfolio_spy200d_70_bil_30_v1/1.0x, diversified_portfolio_challenge/portfolio_spy200d_60_ief_20_bil_20_v1/1.0x, diversified_portfolio_challenge/portfolio_spy200d_70_gld_15_bil_15_v1/1.0x, diversified_portfolio_challenge/portfolio_spy200d_60_ief_20_gld_10_bil_10_v1/1.0x, diversified_portfolio_challenge/portfolio_spy200d_80_ab_20_v1/1.0x, diversified_portfolio_challenge/portfolio_spy200d_70_ab_20_bil_10_v1/1.0x

## 15. Strategies That Hit Project Stop

etf_validated_lane/current_no_cash_proxy_alpha_AB/1.0x, etf_benchmark/SPY_buy_hold/1.0x, etf_benchmark/SPY_200d_trend_model/1.0x, diversified_portfolio_challenge/portfolio_spy200d_100_v1/1.0x, diversified_portfolio_challenge/portfolio_spy200d_80_bil_20_v1/1.0x, diversified_portfolio_challenge/portfolio_spy200d_70_bil_30_v1/1.0x, diversified_portfolio_challenge/portfolio_spy200d_60_ief_20_bil_20_v1/1.0x, diversified_portfolio_challenge/portfolio_spy200d_70_gld_15_bil_15_v1/1.0x, diversified_portfolio_challenge/portfolio_spy200d_60_ief_20_gld_10_bil_10_v1/1.0x, diversified_portfolio_challenge/portfolio_spy200d_80_ab_20_v1/1.0x, diversified_portfolio_challenge/portfolio_spy200d_70_ab_20_bil_10_v1/1.0x

## 16. Too Risky

Rows with high 90-day stop-hit rates, large drawdowns, or large stop-enforced penalties should be treated as too risky or exploratory only even when final-date equity is high.

## 17. Too Slow

Cash and low-volatility defensive rows are too slow for the +$300/+400 challenge unless used only as benchmarks.

## 18. Deserve Further Research

Rows with non-trivial +300-before-stop rates and manageable stop rates deserve further research, not validation claims.

## 19. Rejected Or Deferred

Unimplemented instruments remain deferred or rejected for now. Crypto leverage scenarios are not approved for live or paper-forward use.

## 20. Risk Framework v1 Decision

Framework: balanced_speculative_research_v1. Paper-forward allowed by framework in this packet: SPY_200d_trend_model/standard, BIL_cash_proxy/standard. Diagnostic-only or too-risky rows: portfolio_spy200d_100_v1, portfolio_spy200d_70_gld_15_bil_15_v1, portfolio_spy200d_80_bil_20_v1, portfolio_spy200d_70_bil_30_v1, portfolio_spy200d_60_ief_20_gld_10_bil_10_v1, portfolio_spy200d_60_ief_20_bil_20_v1, portfolio_spy200d_80_ab_20_v1, portfolio_spy200d_70_ab_20_bil_10_v1. Blocked/incomplete rows: current_no_cash_proxy_alpha_AB. Hard-stop band rows: SPY_200d_trend_model, portfolio_spy200d_100_v1, SPY_buy_hold. +$300 remains the primary challenge target; +$400 remains aggressive. Exposure scaling above 1.00x remains diagnostic only. Unlevered SPY_200d remains the leading practical candidate when it has exact evidence; no row is a real-money recommendation.

## 21. Final Conclusion

validation incomplete +$300/+400 remain unresolved until exact finalist rows complete. current_no_cash_proxy_alpha_AB vs SPY_200d_trend_model comparison is non-final. SPY_buy_hold +300 rate is 31.5% versus 18.6% for current_no_cash_proxy_alpha_AB, with stop-hit 6.4% versus 0.0%. It should be penalized if its stop risk or worst drawdown is materially worse. This is still paper/demo research only, not a real-money recommendation.
