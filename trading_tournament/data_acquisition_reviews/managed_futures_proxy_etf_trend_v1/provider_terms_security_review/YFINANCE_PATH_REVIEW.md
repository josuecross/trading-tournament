# Yfinance-Compatible Path Review

Decision: `approve_future_download_prompt_with_metadata`

The yfinance-compatible path is already used by the project for ETF/fund-style price series. It may be used later for a controlled, metadata-capturing acquisition of `DBMF` and `KMLM` only.

## Required Conditions

- Future downloads must be explicit, not accidental.
- Future download must be limited to approved symbols.
- Downloaded data must use the project's adjusted OHLC convention.
- Data must be cached with provider metadata, timestamp, symbol list, request settings, and config hash.
- Coverage summary must be produced.
- Quality summary must be produced before implementation review is updated.
- Raw OHLCV must not enter advisor packets.
- No backtest or strategy run may start automatically after data acquisition.
- Yahoo/yfinance data limitations must be acknowledged: licensing/personal-use limits, revisions, gaps, ticker mapping issues, and adjustment differences.
- If terms are unacceptable, use another provider review or defer.

## Decision Options

- `approve_future_download_prompt_with_metadata`: selected for DBMF/KMLM only.
- `conditional_terms_review_required`: not selected because this review permits a future prompt within a narrow boundary.
- `reject_yfinance_for_this_candidate`: not selected; yfinance-compatible path remains acceptable as the first controlled path.

