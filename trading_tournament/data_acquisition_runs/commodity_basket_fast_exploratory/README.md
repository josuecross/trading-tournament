# Commodity Basket Fast Exploratory Acquisition

This lane performs a controlled yfinance-compatible daily adjusted price acquisition for the approved commodity wrapper symbols only: DBC, PDBC, COMT, GSG, and USCI.

It is an exploratory data acquisition lane. It does not implement commodity momentum, run a backtest, run Profit Exploration, run candidate_exhaustive, use futures contracts directly, add broker integration, place orders, or make a real-money recommendation.

Raw OHLCV is written only to the local cache. Compact evidence and advisor packets contain metadata and quality summaries only.
