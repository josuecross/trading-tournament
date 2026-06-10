# Future Data Download Plan

This is a future-task outline only. No download is performed by this packet.

## Symbols To Acquire

- MTUM
- VLUE
- VTV
- QUAL
- USMV
- SPLV

Existing local cache already contains:

- SPY
- BIL

## Provider Priority Order

1. Existing local cache.
2. Current project yfinance-compatible path, if explicitly approved.
3. Tiingo or Alpha Vantage if an API key is available outside the repo and terms are acceptable.
4. Nasdaq Data Link / Sharadar if paid/keyed access is acceptable.
5. Polygon/Massive if coverage, cost, terms, and adjustment handling are acceptable.
6. Reject or defer if none pass.

## Secret Handling

No secrets in the repo. API keys must be supplied through environment variables or a local secret mechanism and must not be written to evidence.

## Cache And Normalization Requirements

- Store acquired data in an approved research cache path only.
- Capture provider id, acquisition timestamp, symbol list, and request/config hash.
- Normalize adjusted OHLC convention before research use.
- Keep raw provider data out of advisor packets.

## Coverage Summary Output

Any future acquisition task must produce metadata-only coverage summaries with symbol, row count, first date, last date, missing-day count, duplicate-date count, adjustment availability, and quality verdict.

## Tests To Add Later

- Provider metadata exists.
- No duplicate dates.
- Dates sorted.
- Required adjusted-close field exists.
- Common overlap with SPY/BIL is sufficient.
- No raw OHLCV appears in compact/advisor packets.

## Rollback Plan

If provider data fails quality checks, mark the affected symbols `data_rejected` or `provider_review_required`, remove them from research use, and keep the strategy unimplemented.
