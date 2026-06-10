# Global Multi-Asset Fast Exploratory Acquisition

This lane performs a controlled cache-first, yfinance-compatible daily adjusted price acquisition for approved ETF/fund wrapper symbols only.

Approved symbols are SPY, QQQ, GLD, IEF, BIL, DBC, PDBC, COMT, GSG, USCI, IWM, EFA, EEM, and TLT. Existing local cache is used first; the yfinance-compatible path is used only for missing approved symbols.

This lane does not implement a strategy, run a backtest, run Profit Exploration, run candidate_exhaustive, activate paper-forward, add leverage, margin, shorting, futures contracts, options, forex, intraday logic, broker integration, live orders, order placement, or make a real-money recommendation.

Raw OHLCV is written only to the local cache when needed. Compact evidence and advisor packets contain metadata and quality summaries only.
