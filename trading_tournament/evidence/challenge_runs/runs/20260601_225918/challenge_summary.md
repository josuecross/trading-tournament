# Challenge Summary

## 1. Research-Only Statement

This compact challenge audit is paper/demo research only. It does not recommend real-money trading, does not connect to a broker or exchange, and does not place orders.

## 2. Run Identity

- run_id: 20260601_225918
- output: `evidence/challenge_runs/runs/20260601_225918/`
- compact file count: 10
- validation_mode: candidate_exhaustive
- sampled_results_are_final: False
- final_validation_completed: False

## 3. What Was Tested

focused exact ETF finalist, ETF benchmarks, independent family challenge rows with separate $3,000 accounts.

## 4. What Was Not Tested

Individual stocks, options, futures, forex, crypto perpetuals/futures, volatility products, intraday strategies, event/news strategies, live trading, broker integration, exchange execution, margin, shorting, and real order placement.

## 5. Account Assumptions

Each row is an independent $3,000 simulated challenge account. Targets are $3,300 and $3,400. Stops are $2,400 absolute floor and high-water mark minus $600, with mode `both`.

## 6. Best Result By +300 Before Stop

independent_family_challenge / GLD_buy_hold (1.0x): +300 90d 41.9%, +400 90d 27.9%, stop 90d 5.2%.

## 7. Best Result By +400 Before Stop

independent_family_challenge / GLD_buy_hold (1.0x): +300 90d 41.9%, +400 90d 27.9%, stop 90d 5.2%.

## 8. Best Risk-Controlled Result

independent_family_challenge / IEF_buy_hold (1.0x): +300 90d 4.4%, +400 90d 0.6%, stop 90d 0.0%.

## ETF Benchmark Rolling Rows

ETF benchmark rolling rows are unavailable.

## current_no_cash_proxy_alpha_AB Benchmark Comparison

- current_no_cash_proxy_alpha_AB: 90-day rolling comparison unavailable or not all-possible in this compact run.

## Exact 90-Day Focus Table

Standard:

| Strategy | +300 before stop | +400 before stop | Any stop hit | Median stop-enforced equity | Worst drawdown | Final? |
|---|---:|---:|---:|---:|---:|---|
| current_no_cash_proxy_alpha_AB | unavailable | unavailable | unavailable | unavailable | unavailable | no |
| SPY_buy_hold | 31.5% | 15.0% | 6.4% | $3,152.55 | $-1,329.58 | True |
| SPY_200d_trend_model | 23.8% | 9.9% | 0.5% | $3,095.59 | $-661.49 | True |
| BIL_cash_proxy | 0.0% | 0.0% | 0.0% | $3,000.46 | $-24.67 | True |

Stress:

| Strategy | +300 before stop | +400 before stop | Any stop hit | Median stop-enforced equity | Worst drawdown | Final? |
|---|---:|---:|---:|---:|---:|---|
| current_no_cash_proxy_alpha_AB | unavailable | unavailable | unavailable | unavailable | unavailable | no |
| SPY_buy_hold | 31.3% | 14.7% | 6.4% | $3,150.97 | $-1,328.93 | True |
| SPY_200d_trend_model | 23.6% | 9.6% | 1.1% | $3,090.96 | $-687.75 | True |
| BIL_cash_proxy | 0.0% | 0.0% | 0.0% | $2,998.97 | $-26.17 | True |

## Practical Decision

- current_no_cash_proxy_alpha_AB vs SPY_200d_trend_model comparison is non-final.
- SPY_buy_hold row unavailable.
- validation incomplete
- +$300/+400 remain unresolved until exact finalist rows complete.

## Finalist Validation Status

Finalist validation is incomplete/non-final. Independent family challenge is incomplete for unavailable exact-stream or blocked family rows; runnable ETF-like family rows may still have exact all_possible windows.

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

Diversified portfolio challenge diagnostics were not enabled in this run.

No diversified portfolio challenge decision was made in this run.

## Independent Family Challenge

| Family | Group | +300 before stop | +400 before stop | Any stop hit | Median stop equity | Worst drawdown | Verdict |
|---|---|---:|---:|---:|---:|---:|---|
| family_bond_treasury_ief_v1 | bond_treasury_etf | 4.4% | 0.6% | 0.0% | $3,036.79 | $-398.53 | too_slow |
| family_broad_etf_spy_buy_hold_v1 | broad_etf_buy_hold | 31.5% | 15.0% | 6.4% | $3,152.55 | $-1,329.58 | benchmark_candidate |
| family_broad_etf_spy200d_v1 | broad_etf_trend | 23.8% | 9.9% | 0.5% | $3,095.59 | $-661.49 | benchmark_candidate |
| family_cash_treasury_bil_v1 | cash_treasury_proxy | 0.0% | 0.0% | 0.0% | $3,000.46 | $-24.67 | benchmark_only |
| family_gold_gld_v1 | gold_commodity_etf | 41.9% | 27.9% | 5.2% | $3,108.13 | $-878.65 | watchlist |

Runnable families: family_broad_etf_spy200d_v1, family_broad_etf_spy_buy_hold_v1, family_cash_treasury_bil_v1, family_bond_treasury_ief_v1, family_gold_gld_v1. Blocked families reported, not run: family_individual_stock_momentum_v1: Gate 1A continue_defer; no survivorship-free data/delisting treatment.; family_options_directional_v1: No option-chain, bid/ask, IV, Greeks, assignment/exercise, margin, or spread-fill model.; family_options_premium_v1: No option-chain, margin, assignment, tail-risk, or realistic fill model.; family_futures_trend_following_v1: No continuous contract, roll, margin, leverage, or gap model.; family_forex_momentum_carry_v1: No spread, financing, leverage, or broker execution model.; family_intraday_orb_v1: Current daily bars cannot model intraday fills, spreads, queue, or stop behavior.; family_volatility_products_v1: No product mechanics, decay, roll-yield, path-dependency, or event-risk model.; family_event_news_momentum_v1: No point-in-time event timestamps or reliable historical event data.. Unavailable exact-stream/data families: family_etf_sector_momentum_A_v1: unavailable_exact_stream; family_etf_ab_no_cash_v1: unavailable_exact_stream. Families improving +300/stop/drawdown versus SPY_200d: none. Best independent-family tradeoff: family_gold_gld_v1 / GLD_buy_hold (watchlist), +300=41.9%, +400=27.9%, stop=5.2%, worst drawdown=$-878.65. Crypto family rows were not included in this ETF-only family run. These rows use separate $3,000 accounts and are not blended portfolios. No family row is automatically paper-forward ready.

## 12. Stop-Enforced Vs Unconditional Warning

Full-period final equity can be misleading. `stop_enforced_final_equity` is the relevant challenge metric when a project stop occurs before the final data date.

## 13. Full-Period Rows That Hit +300 Before Stop

independent_family_challenge/SPY_200d_trend_model/1.0x, independent_family_challenge/SPY_buy_hold/1.0x, independent_family_challenge/BIL_cash_proxy/1.0x, independent_family_challenge/IEF_buy_hold/1.0x, independent_family_challenge/GLD_buy_hold/1.0x

## 14. Full-Period Rows That Hit +400 Before Stop

independent_family_challenge/SPY_200d_trend_model/1.0x, independent_family_challenge/BIL_cash_proxy/1.0x, independent_family_challenge/IEF_buy_hold/1.0x, independent_family_challenge/GLD_buy_hold/1.0x

## 15. Strategies That Hit Project Stop

independent_family_challenge/SPY_200d_trend_model/1.0x, independent_family_challenge/SPY_buy_hold/1.0x, independent_family_challenge/IEF_buy_hold/1.0x, independent_family_challenge/GLD_buy_hold/1.0x

## 16. Too Risky

Rows with high 90-day stop-hit rates, large drawdowns, or large stop-enforced penalties should be treated as too risky or exploratory only even when final-date equity is high.

## 17. Too Slow

Cash and low-volatility defensive rows are too slow for the +$300/+400 challenge unless used only as benchmarks.

## 18. Deserve Further Research

Rows with non-trivial +300-before-stop rates and manageable stop rates deserve further research, not validation claims.

## 19. Rejected Or Deferred

Unimplemented instruments remain deferred or rejected for now. Crypto leverage scenarios are not approved for live or paper-forward use.

## 20. Risk Framework v1 Decision

Framework: balanced_speculative_research_v1. Paper-forward allowed by framework in this packet: SPY_200d_trend_model/standard, BIL_cash_proxy/standard. Diagnostic-only or too-risky rows: GLD_buy_hold. Blocked/incomplete rows: A_ETF_sector_momentum, current_no_cash_proxy_alpha_AB, family_individual_stock_momentum_v1, family_options_directional_v1, family_options_premium_v1, family_futures_trend_following_v1, family_forex_momentum_carry_v1, family_intraday_orb_v1, family_volatility_products_v1, family_event_news_momentum_v1. Hard-stop band rows: GLD_buy_hold, SPY_200d_trend_model, SPY_buy_hold. +$300 remains the primary challenge target; +$400 remains aggressive. Exposure scaling above 1.00x remains diagnostic only. Unlevered SPY_200d remains the leading practical candidate when it has exact evidence; no row is a real-money recommendation.

## 21. Final Conclusion

validation incomplete +$300/+400 remain unresolved until exact finalist rows complete. current_no_cash_proxy_alpha_AB vs SPY_200d_trend_model comparison is non-final. SPY_buy_hold row unavailable. This is still paper/demo research only, not a real-money recommendation.
