# README For Advisor

This is a compact Global Multi-Asset ETF Fast Exploration Batch 1 acquisition packet for `global_multi_asset_fast_exploratory`.

It used existing cache first and a yfinance-compatible public-data path only for missing approved ETF/fund wrapper symbols. No unapproved symbols, keyed API provider, API key, secret, broker integration, live order, or order placement is included.

Raw OHLCV is excluded from this compact evidence packet and from advisor upload packets. Raw cache files, if written, remain under `data/cache/`.

This acquisition does not implement a strategy, run a backtest, run Profit Exploration, run candidate_exhaustive, activate paper-forward, add leverage, margin, shorting, futures contracts, options, forex, intraday logic, or make a real-money recommendation.
