# Data Policy

Allowed data for future research_sample:

- ETF/fund wrapper adjusted daily data.
- Existing cache preferred.
- yfinance-compatible data is acceptable for fast exploratory screening if basic QA passes.
- Raw OHLCV must stay out of compact advisor packets.
- Fast exploratory data alone cannot approve candidate_exhaustive.
- Fast exploratory data cannot activate paper-forward.

Future allowed symbols, only if data is available and QA passes:

- SPY
- QQQ
- IWM
- sector ETFs already used in the project
- BIL
- SHY
- IEF
- TLT
- GLD
- SPLV
- USMV
- QUAL

This review does not download data.

Basic QA requirements:

- sufficient history
- no missing adjusted close for the required period
- no impossible OHLC values
- no duplicate dates
- enough warmup data for indicators
- no raw vendor data in compact evidence
- symbol availability documented
