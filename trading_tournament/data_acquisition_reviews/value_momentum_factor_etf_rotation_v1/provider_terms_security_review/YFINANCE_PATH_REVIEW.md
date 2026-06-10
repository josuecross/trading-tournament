# Yfinance-Compatible Path Review

This review does not call yfinance and does not download data.

The project already uses a yfinance-compatible path for some ETF/market research data. Future downloads for `value_momentum_factor_etf_rotation_v1` must be explicit and must not occur as a side effect of strategy testing.

## Requirements For Future Use

- Future download prompt must name only MTUM, VLUE, VTV, QUAL, USMV, and SPLV.
- The project’s adjusted OHLC convention must be used consistently.
- Downloaded data must be cached with provider metadata, acquisition timestamp, symbol list, request settings, and config hash.
- Coverage summary must be produced.
- Quality summary must be produced before any strategy implementation.
- Raw OHLCV must not enter advisor packets or compact evidence.
- No backtest or strategy run may start automatically after data acquisition.

## Known Risks

Yahoo/yfinance data may have personal-use/licensing limitations, revisions, gaps, missing rows, and adjustment differences. If terms or data quality are unacceptable, the project must use another provider review or defer.

## Decision

Decision option chosen: `approve_future_download_prompt_with_metadata`.

This means a future task may draft and run a narrowly scoped yfinance-compatible download prompt for the six missing symbols only. It does not download data now, does not validate the strategy, and does not permit paper-forward promotion.
