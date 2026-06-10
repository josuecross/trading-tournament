# Proxy And Inception Review

Local cache reviewed: `data/cache`.

No data was downloaded. No APIs were called. No futures contracts were used.

| symbol | proxy_role | expected_return_driver | cached_locally | first_cached_date | last_cached_date | row_count | enough_history_for_rolling_windows | inception_or_history_risk | proxy_quality | likely_duplicate_of_current_equity_strategies | notes |
|---|---|---|---:|---|---|---:|---:|---|---|---|---|
| DBMF | managed-futures ETF proxy | diversified managed-futures style trend exposure through an ETF wrapper | false | n/a | n/a | 0 | false | unknown | unknown | low_to_medium_unknown | Missing from local cache; requires provider and inception review before use. |
| KMLM | managed-futures ETF proxy | managed-futures style trend exposure through a fund wrapper | false | n/a | n/a | 0 | false | unknown | unknown | low_to_medium_unknown | Missing from local cache; history length and methodology must be checked. |
| CTA | managed-futures ETF proxy | CTA/managed-futures style trend exposure through a fund wrapper | false | n/a | n/a | 0 | false | unknown | unknown | low_to_medium_unknown | Missing from local cache; ticker ambiguity and provider coverage must be reviewed. |
| FMF | managed-futures ETF/fund proxy | managed-futures style exposure through a fund wrapper | false | n/a | n/a | 0 | false | unknown | unknown | low_to_medium_unknown | Missing from local cache; proxy quality and availability are unverified. |
| WTMF | managed-futures ETF/fund proxy | managed-futures style exposure through a fund wrapper | false | n/a | n/a | 0 | false | unknown | unknown | low_to_medium_unknown | Missing from local cache; proxy quality and availability are unverified. |

## Inception Risk

The candidate remains inception-risk gated because no reviewed proxy series is cached. A future data acquisition review must record first date, last date, row count, provider metadata, and overlap with current benchmark symbols before any research_sample implementation is considered.

## Proxy Quality Caveat

Managed-futures ETF/fund proxies are not equivalent to a direct futures trend-following system. Fund methodology, holdings, fees, turnover, roll handling, and internal derivatives exposure can make the proxy result fund-specific rather than strategy-family evidence.

