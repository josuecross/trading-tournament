# Future Data Download Plan

No download is performed by this packet.

## Possible Future Acquisition Symbols

Priority candidates:

- `DBMF`
- `KMLM`
- `CTA`

Optional/lower-priority review candidates:

- `FMF`
- `WTMF`

`CTA` must pass ticker-identity review before any download prompt. `FMF` and `WTMF` should be included only if provider coverage, fund status, inception history, and methodology review justify them.

## Provider Priority Order

1. existing local cache
2. yfinance-compatible path, if approved by a later provider terms/security review
3. Tiingo or Alpha Vantage if an API key is available and terms are acceptable
4. Nasdaq Data Link / Sharadar if access is acceptable
5. Polygon/Massive if coverage, cost, and terms are acceptable
6. reject or defer if none pass

## Future Task Boundaries

A future controlled acquisition prompt must:

- not implement a strategy
- not trigger a backtest
- no backtest may run
- not run Profit Exploration
- capture provider metadata
- produce coverage summaries
- produce data-quality summaries
- exclude raw OHLCV from compact/advisor evidence
- keep secrets out of the repo
- use no broker APIs
- use no live orders
- add no futures contract logic
