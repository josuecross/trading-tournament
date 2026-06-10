# Managed-Futures Proxy Data Acquisition Run

This folder contains the controlled yfinance-compatible acquisition runner for `managed_futures_proxy_etf_trend_v1`.

The allowed first-prompt symbols are `DBMF` and `KMLM` only. `CTA`, `FMF`, `WTMF`, `SPY`, and `BIL` are excluded from this acquisition task.

This task downloads/cache data only and writes metadata/quality evidence. It does not implement a strategy, run a backtest, run Profit Exploration, add futures contract logic, change paper-forward rules, use keyed providers, use API keys, connect to brokers, place live orders, or make a real-money recommendation.

