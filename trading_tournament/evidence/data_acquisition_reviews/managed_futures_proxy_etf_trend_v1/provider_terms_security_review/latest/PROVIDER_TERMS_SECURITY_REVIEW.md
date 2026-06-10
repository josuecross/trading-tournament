# Provider Terms Security Review

Subject: `managed_futures_proxy_etf_trend_v1`

Decision: `approve_future_yfinance_download_prompt_dbmf_kmlm_only`

## Symbols Considered

High priority:

- `DBMF`
- `KMLM`

Conditional:

- `CTA`, only after ticker identity is verified.

Optional/lower priority:

- `FMF`
- `WTMF`

## Preferred Provider Path

The yfinance-compatible path is operationally simplest because the project already uses yfinance-compatible conventions for ETF/fund-style daily price series. A future task can reuse that convention while capturing provider metadata, request settings, timestamps, config hashes, coverage summaries, and quality summaries.

## yfinance/Yahoo Risks

Yahoo/yfinance data may have licensing or personal-use limitations, revisions, missing observations, ticker mapping problems, corporate-action adjustment differences, and occasional provider behavior changes. A future controlled acquisition must be explicit and must not silently refresh unrelated symbols.

## Remaining Terms Questions

Before any download prompt, the future task must confirm that the yfinance-compatible path is acceptable for personal research cache use, that raw OHLCV stays out of advisor packets, and that provider metadata is recorded. If terms are unacceptable, use keyed provider review or defer.

## Keyed Provider Fallback

Tiingo, Alpha Vantage, Nasdaq Data Link / Sharadar, and Polygon/Massive should be considered only if the yfinance-compatible path is rejected, missing required coverage, or fails data quality. Keyed providers require secret handling and terms review before use.

## Required Future Download Records

A future controlled acquisition must record provider id, timestamp, Python/package versions, request settings, symbol list, cache paths, row counts, first/last dates, duplicate dates, missing values, adjustment fields, data-quality verdicts, and a manifest confirming no strategy or backtest was run.

Raw OHLCV must not enter advisor packets. No real-money recommendation is made.

