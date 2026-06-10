# Factor ETF Data Acquisition

This directory contains the controlled data-only acquisition tool for `value_momentum_factor_etf_rotation_v1`.

The tool is limited to the six provider-review-approved factor ETF proxy symbols: MTUM, VLUE, VTV, QUAL, USMV, and SPLV. It does not refresh SPY or BIL by default, does not implement strategy logic, does not run a backtest, does not change paper-forward rules, and does not make a real-money recommendation.

Evidence output contains metadata, coverage, gap, adjustment, and cache-write summaries only. Raw OHLCV/cache files are excluded from compact evidence and advisor upload packets.
