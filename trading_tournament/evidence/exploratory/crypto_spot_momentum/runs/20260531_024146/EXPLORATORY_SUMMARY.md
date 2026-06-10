# Crypto Spot Momentum Exploratory Summary

## Research-Only Statement

This is a paper/demo research artifact. It does not recommend real-money trading, does not connect to an exchange, does not place orders, and does not validate a strategy.

## Tier Label

- credibility_tier: Tier 1 exploratory screen
- final_validation: false
- candidate_validation: false
- paper_forward_ready: false
- real_money_recommendation: false

## Run Identity

- run_id: 20260531_024146
- validation_mode: smoke
- data_source: yfinance
- network_download_occurred: False

## Strategy Rules

The lane tests long-only daily BTC/ETH spot proxies using fixed rules: equal-weight buy and hold, BTC buy and hold, ETH buy and hold, weekly time-series momentum, weekly cross-sectional momentum, and weekly dual momentum with a cash filter. Cash earns zero.

## Cost Assumptions

Standard cost uses 0.10% per side. Stress cost uses 0.30% per side when included by the selected validation mode. These are Tier 1 exploratory assumptions, not final execution evidence.

## Standard Vs Stress Results

Best standard-cost result by final equity: crypto_dual_momentum_cash_filter.

Stress results were not part of this mode.

## Target-Before-Stop Results

Target-before-stop is reported in `strategy_results.csv`, `benchmark_results.csv`, `target_timing.csv`, and `rolling_window_summary.csv`. A target hit is not validation; it is only a challenge metric.

## Rolling-Window Summary

Best sampled 90-row +300-before-stop rate: BTC_buy_hold (standard) at 83.33%.

These rolling results are deterministic exploratory samples unless `candidate_exhaustive` is explicitly selected. They are not final validation.

## Benchmark Comparison

Benchmark rows include `crypto_buy_hold_equal_weight`, `BTC_buy_hold`, `ETH_buy_hold`, and `cash_flat` where available. Crypto benchmarks are highly volatile and do not imply investability.

## Main Reasons Not To Trust Results As Final

- yfinance crypto data is Tier 1 exploratory only.
- Exchange-specific crypto prices may differ.
- Crypto trades 24/7 and daily bar timestamps can differ by source.
- No bid/ask spread, order book depth, exchange outage, delisting, custody, or stablecoin risk is modeled.

## Tier 2 Review

Promotion decision: `continue_tier1`.

Tier 2 review, if allowed, would still be research-only and would require better data, explicit exchange/source assumptions, more complete cost modeling, and stronger validation.

## No Real-Money Recommendation

No result in this packet is a real-money recommendation.
