# Challenge Summary

## 1. Research-Only Statement

This compact challenge audit is paper/demo research only. It does not recommend real-money trading, does not connect to a broker or exchange, and does not place orders.

## 2. Run Identity

- run_id: 20260601_234739
- output: `evidence/challenge_runs/runs/20260601_234739/`
- compact file count: 10
- validation_mode: research_sample
- sampled_results_are_final: False
- final_validation_completed: False

## 3. What Was Tested

ETF evidence summaries, ETF benchmarks, long-only crypto spot exploratory strategies, BTC/ETH buy-and-hold benchmarks, approximate simulated leverage scenarios, independent family challenge rows with separate $3,000 accounts.

## 4. What Was Not Tested

Individual stocks, options, futures, forex, crypto perpetuals/futures, volatility products, intraday strategies, event/news strategies, live trading, broker integration, exchange execution, margin, shorting, and real order placement.

## 5. Account Assumptions

Each row is an independent $3,000 simulated challenge account. Targets are $3,300 and $3,400. Stops are $2,400 absolute floor and high-water mark minus $600, with mode `both`.

## 6. Best Result By +300 Before Stop

independent_family_challenge / crypto_buy_hold_equal_weight (1.0x): +300 90d 68.0%, +400 90d 58.4%, stop 90d 70.0%.

## 7. Best Result By +400 Before Stop

independent_family_challenge / crypto_buy_hold_equal_weight (1.0x): +300 90d 68.0%, +400 90d 58.4%, stop 90d 70.0%.

## 8. Best Risk-Controlled Result

independent_family_challenge / IEF_buy_hold (1.0x): +300 90d 8.2%, +400 90d 3.0%, stop 90d 0.0%.

## ETF Benchmark Rolling Rows

ETF benchmark rolling rows are unavailable.

## current_no_cash_proxy_alpha_AB Benchmark Comparison

- current_no_cash_proxy_alpha_AB: +300 nan%, +400 nan%, stop nan%, median stop equity nan, worst drawdown nan.
- SPY_buy_hold: unavailable.
- SPY_200d_trend_model: unavailable.
- BIL_cash_proxy: unavailable.

## Exact 90-Day Focus Table

Standard:

| Strategy | +300 before stop | +400 before stop | Any stop hit | Median stop-enforced equity | Worst drawdown | Final? |
|---|---:|---:|---:|---:|---:|---|
| current_no_cash_proxy_alpha_AB | nan% | nan% | nan% | $nan | $nan | False |
| SPY_buy_hold | 33.8% | 18.6% | 15.6% | $3,124.37 | $-1,280.68 | False |
| SPY_200d_trend_model | 22.8% | 8.2% | 0.2% | $3,073.65 | $-603.31 | False |
| BIL_cash_proxy | 0.0% | 0.0% | 0.0% | $3,003.73 | $-23.45 | False |

Stress:

| Strategy | +300 before stop | +400 before stop | Any stop hit | Median stop-enforced equity | Worst drawdown | Final? |
|---|---:|---:|---:|---:|---:|---|
| current_no_cash_proxy_alpha_AB | nan% | nan% | nan% | $nan | $nan | False |
| SPY_buy_hold | 33.8% | 18.4% | 15.6% | $3,122.81 | $-1,280.04 | False |
| SPY_200d_trend_model | 22.8% | 7.6% | 0.6% | $3,070.32 | $-628.24 | False |
| BIL_cash_proxy | 0.0% | 0.0% | 0.0% | $3,002.23 | $-23.44 | False |

## Practical Decision

- current_no_cash_proxy_alpha_AB vs SPY_200d_trend_model comparison is non-final.
- SPY_buy_hold +300 rate is 33.8% versus nan% for current_no_cash_proxy_alpha_AB, with stop-hit 15.6% versus nan%. It should be penalized if its stop risk or worst drawdown is materially worse.
- validation incomplete
- +$300/+400 remain unresolved until exact finalist rows complete.

## Finalist Validation Status

Finalist validation is incomplete/non-final. The run remains research evidence, not final validation.

current_no_cash_proxy_alpha_AB may be considered only as a research watchlist/finalist candidate until exact finalist validation is complete.

## 9. Best ETF Result

In focused `candidate_exhaustive`, current_no_cash_proxy_alpha_AB is computed or loaded only from exact all-possible Backtester evidence; benchmark rows are computed directly from cached adjusted benchmark prices on the same effective calendar. See `strategy_rankings.csv` for the compact ranking.

## 10. Best Crypto Exploratory Result

Crypto rows remain Tier 1 exploratory when included. Large final-date crypto equity is not enough because many rows also hit project stops.

## 11. Best Simulated Leverage Result

Simulated leverage is approximate only when included. It often increases target hit rates and stop risk at the same time, and is not a real margin/liquidation model.

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

Diversified portfolio challenge diagnostics were not enabled in this run.

No diversified portfolio challenge decision was made in this run.

## Independent Family Challenge Completion

| Family | Group | Tier | Final? | +300 before stop | +400 before stop | Any stop hit | Median stop equity | Worst drawdown | Verdict |
|---|---|---|---|---:|---:|---:|---:|---:|---|
| family_bond_treasury_ief_v1 | bond_treasury_etf | benchmark | False | 8.2% | 3.0% | 0.0% | $3,023.89 | $-398.53 | too_slow |
| family_broad_etf_spy_buy_hold_v1 | broad_etf_buy_hold | benchmark | False | 33.8% | 18.6% | 15.6% | $3,124.37 | $-1,280.68 | benchmark_candidate |
| family_broad_etf_spy200d_v1 | broad_etf_trend | tier3_candidate_validation | False | 22.8% | 8.2% | 0.2% | $3,073.65 | $-603.31 | benchmark_candidate |
| family_cash_treasury_bil_v1 | cash_treasury_proxy | benchmark | False | 0.0% | 0.0% | 0.0% | $3,003.73 | $-23.45 | benchmark_only |
| family_crypto_spot_buy_hold_equal_weight_v1 | crypto_spot_buy_hold | tier1_exploratory | False | 68.0% | 58.4% | 70.0% | $3,185.23 | $-3,003.42 | exploratory_only |
| family_crypto_spot_time_series_momentum_v1 | crypto_spot_momentum | tier1_exploratory | False | 48.0% | 44.0% | 33.2% | $3,000.00 | $-2,683.85 | exploratory_only |
| family_etf_ab_no_cash_v1 | etf_ab_strategy | tier3_candidate_validation | False | nan% | nan% | nan% | $nan | $nan | incomplete_evidence |
| family_etf_sector_momentum_A_v1 | etf_sector_momentum | tier2_credible_prototype | False | nan% | nan% | nan% | $nan | $nan | incomplete_evidence |
| family_gold_gld_v1 | gold_commodity_etf | benchmark | False | 51.4% | 42.4% | 8.2% | $3,179.01 | $-840.62 | watchlist |

Each family row received its own independent $3,000 paper/demo account; family rows are not portfolio mixes and do not share capital. Runnable families: family_broad_etf_spy200d_v1, family_broad_etf_spy_buy_hold_v1, family_cash_treasury_bil_v1, family_bond_treasury_ief_v1, family_gold_gld_v1, family_crypto_spot_time_series_momentum_v1, family_crypto_spot_buy_hold_equal_weight_v1. Exact/final all_possible families: none with completed all_possible finality. Blocked families reported, not run: family_individual_stock_momentum_v1: Gate 1A continue_defer; no survivorship-free data/delisting treatment.; family_options_directional_v1: No option-chain, bid/ask, IV, Greeks, assignment/exercise, margin, or spread-fill model.; family_options_premium_v1: No option-chain, margin, assignment, tail-risk, or realistic fill model.; family_futures_trend_following_v1: No continuous contract, roll, margin, leverage, or gap model.; family_forex_momentum_carry_v1: No spread, financing, leverage, or broker execution model.; family_intraday_orb_v1: Current daily bars cannot model intraday fills, spreads, queue, or stop behavior.; family_volatility_products_v1: No product mechanics, decay, roll-yield, path-dependency, or event-risk model.; family_event_news_momentum_v1: No point-in-time event timestamps or reliable historical event data.. Incomplete exact-stream/data families: family_etf_sector_momentum_A_v1: Exact challenge-comparable rolling stream for current_momentum_only_A is incomplete; family row is not approximated from summary metrics.; family_etf_ab_no_cash_v1: Exact challenge-comparable rolling stream for current_no_cash_proxy_alpha_AB is incomplete; family row is not approximated from summary metrics.. Best exact +300 family: unavailable. Best exact +400 family: unavailable. Best exact risk-control family: unavailable. Families improving +300/stop/drawdown versus SPY_200d: none. Best exact overall family tradeoff: unavailable. Best exploratory family by +300 potential: family_crypto_spot_buy_hold_equal_weight_v1 / crypto_buy_hold_equal_weight (+300=68.0%, +400=58.4%, stop=70.0%, worst_dd=$-3,003.42). Crypto family rows were included but remain Tier 1 exploratory/non-final. GLD remains target-rich but drawdown-heavy when present; SPY_200d remains the paper-forward candidate unless another exact family improves target probability without worse stop/drawdown behavior. Blocked families are blocked, not ignored. +$300 is plausible in some exact families; +$400 remains aggressive. No family row is automatically paper-forward ready.

## 12. Stop-Enforced Vs Unconditional Warning

Full-period final equity can be misleading. `stop_enforced_final_equity` is the relevant challenge metric when a project stop occurs before the final data date.

## 13. Full-Period Rows That Hit +300 Before Stop

independent_family_challenge/SPY_200d_trend_model/1.0x, independent_family_challenge/SPY_buy_hold/1.0x, independent_family_challenge/BIL_cash_proxy/1.0x, independent_family_challenge/IEF_buy_hold/1.0x, independent_family_challenge/GLD_buy_hold/1.0x, independent_family_challenge/crypto_time_series_momentum/1.0x

## 14. Full-Period Rows That Hit +400 Before Stop

independent_family_challenge/SPY_200d_trend_model/1.0x, independent_family_challenge/BIL_cash_proxy/1.0x, independent_family_challenge/IEF_buy_hold/1.0x, independent_family_challenge/GLD_buy_hold/1.0x, independent_family_challenge/crypto_time_series_momentum/1.0x

## 15. Strategies That Hit Project Stop

independent_family_challenge/SPY_200d_trend_model/1.0x, independent_family_challenge/SPY_buy_hold/1.0x, independent_family_challenge/IEF_buy_hold/1.0x, independent_family_challenge/GLD_buy_hold/1.0x, independent_family_challenge/crypto_time_series_momentum/1.0x, independent_family_challenge/crypto_buy_hold_equal_weight/1.0x

## 16. Too Risky

Rows with high 90-day stop-hit rates, large drawdowns, or large stop-enforced penalties should be treated as too risky or exploratory only even when final-date equity is high.

## 17. Too Slow

Cash and low-volatility defensive rows are too slow for the +$300/+400 challenge unless used only as benchmarks.

## 18. Deserve Further Research

Rows with non-trivial +300-before-stop rates and manageable stop rates deserve further research, not validation claims.

## 19. Rejected Or Deferred

Unimplemented instruments remain deferred or rejected for now. Crypto leverage scenarios are not approved for live or paper-forward use.

## 20. Risk Framework v1 Decision

Framework: balanced_speculative_research_v1. Paper-forward allowed by framework in this packet: BIL_cash_proxy/standard. Diagnostic-only or too-risky rows: crypto_time_series_momentum, crypto_buy_hold_equal_weight. Blocked/incomplete rows: SPY_200d_trend_model, IEF_buy_hold, BIL_cash_proxy, GLD_buy_hold, SPY_buy_hold, A_ETF_sector_momentum, current_no_cash_proxy_alpha_AB, family_individual_stock_momentum_v1, family_options_directional_v1, family_options_premium_v1. Hard-stop band rows: SPY_200d_trend_model, GLD_buy_hold, SPY_buy_hold, crypto_time_series_momentum, crypto_buy_hold_equal_weight, A_ETF_sector_momentum, current_no_cash_proxy_alpha_AB. +$300 remains the primary challenge target; +$400 remains aggressive. Exposure scaling above 1.00x remains diagnostic only. Unlevered SPY_200d remains the leading practical candidate when it has exact evidence; no row is a real-money recommendation.

## 21. Final Conclusion

+$300 and +$400 are possible in these tests, especially in volatile crypto windows and some ETF evidence rows, but possible does not mean reliable. Crypto appears more likely to reach targets quickly, with much higher stop risk and lower credibility. ETF results are more credible but generally slower and less explosive. The next practical step is to compare stop-enforced rolling behavior, not chase high unconditional final equity.
