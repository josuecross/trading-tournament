# Fast Exploratory Data Policy

Early historical screening does not require perfect data. This project does not require perfect institutional-grade data before every early historical screen.

For exchange-traded ETF and fund wrappers, a yfinance-compatible adjusted daily price path is acceptable for fast exploratory screening when basic quality checks pass. Those results must be labeled exploratory, non-final, not paper-forward, and not real-money evidence.

Mandatory limits for this fast lane:

- Basic QA is required before using a symbol in a research_sample.
- Raw OHLCV stays in the approved local cache and is excluded from compact evidence and advisor packets.
- Strict data, product, legal, tax, K-1, roll-risk, issuer methodology, and wrapper review is deferred until a candidate shows promise.
- Fast exploratory screens may run research_sample only.
- Fast exploratory screens may not run candidate_exhaustive.
- Fast exploratory screens may not activate paper-forward.
- Fast exploratory screens may not recommend real-money trading.

Individual stocks remain stricter because survivorship bias, delistings, delisting returns, point-in-time universe membership, corporate actions, and ticker history can dominate historical results. Current-ticker-only stock evidence remains toy-only.

Options, futures, forex, intraday, and direct futures-roll modeling remain gated. They require separate data, execution, margin, risk, and terms reviews before implementation.

Paper-forward observation and candidate_exhaustive remain strict lanes. Exploratory ETF/fund data can identify whether a family is worth more work, but it cannot approve promotion, paper-forward observation, broker integration, live orders, or real-money recommendation.
