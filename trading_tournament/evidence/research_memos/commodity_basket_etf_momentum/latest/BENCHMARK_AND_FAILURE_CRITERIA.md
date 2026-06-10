# Benchmark And Failure Criteria

## Primary Benchmarks

- combo_SPY200d_GLD_50_50_v1
- asset_class_tsmom_top2_v1

## Secondary Benchmarks

- SPY_200d_trend_model
- GLD_buy_hold
- BIL_cash_proxy
- managed_futures_proxy_etf_trend_v1
- commodity products buy-hold, if later implemented

## Failure Criteria

- product structure too risky or opaque,
- data history too short,
- common overlap too short,
- target rates too low,
- worse drawdown/stop behavior than combo/top2,
- returns mostly duplicate GLD/top2 commodity sleeve,
- roll decay dominates,
- liquidity/spread unrealistic,
- exact fresh-window streams cannot be produced,
- product/tax/ETN risks make interpretation too messy.

## Required Reporting If Future Research Is Approved

Future research_sample must report +300/+400/+600/+900/+1200 target rates, 30/60/90/180 horizons, stop-hit rates, worst drawdown, risk-budget usage, median and p95 stop-enforced equity, stress degradation, correlation/co-movement diagnostics, and duplicate/diversification warnings.

No candidate_exhaustive, paper-forward observation, or real-money recommendation is approved by this review.
