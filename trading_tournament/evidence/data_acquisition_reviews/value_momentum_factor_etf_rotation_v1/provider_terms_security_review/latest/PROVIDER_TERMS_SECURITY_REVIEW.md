# Provider Terms Security Review

This review does not call APIs and does not download data.

## Symbols Considered

Future acquisition may consider only:

- MTUM
- VLUE
- VTV
- QUAL
- USMV
- SPLV

SPY and BIL are already cached locally and should not be refreshed unless a future task explicitly asks for a refresh.

## Preferred Provider Path

The preferred first path is the project’s existing yfinance-compatible data path because the project already has conventions around adjusted ETF data and local cache use. This is the simplest path operationally because it avoids API-key storage and can be constrained to the six missing ETF proxies.

## yfinance / Yahoo Risks

Risks remain:

- personal-use and licensing limitations may apply,
- historical data can be revised,
- adjusted-price fields can differ by provider convention,
- gaps or missing rows can occur,
- dividends/splits treatment must be quality checked,
- reproducibility requires provider metadata and timestamped cache records.

## Terms And Licensing Questions

The future prompt must document that the data is used for personal research-only paper/demo analysis, not redistributed raw, and not included in advisor packets. If terms are unacceptable, the project must use a keyed provider review or defer acquisition.

## When To Consider Keyed Providers

Use Tiingo, Alpha Vantage, Nasdaq Data Link / Sharadar, or Polygon/Massive only if:

- the yfinance-compatible path fails terms or quality review,
- a provider key is available outside the repo,
- terms allow local research cache use,
- adjusted-price semantics and coverage are acceptable,
- the future task explicitly approves keyed provider use.

## Before Any Download Prompt

The future prompt must specify symbols, provider, no secrets in repo, cache location, metadata fields, adjustment convention, coverage summary, quality checks, and evidence exclusion rules.

## During Future Download

Record provider id, acquisition timestamp, symbol list, request settings, config hash, first/last dates, row counts, missing dates, duplicate dates, and quality verdicts. Raw OHLCV must not be copied into advisor packets.

No real-money recommendation is made.
