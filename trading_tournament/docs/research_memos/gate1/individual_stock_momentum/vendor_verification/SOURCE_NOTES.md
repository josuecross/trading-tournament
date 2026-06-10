# Source Notes

Access date for this verification: 2026-05-31 UTC.

This review used manual inspection of official or primary pages where available. It did not use vendor APIs, did not scrape websites, did not download historical market data, and did not verify contract terms.

## CRSP

Official page reviewed:

- https://www.crsp.org/research/crsp-us-stock-databases/

Facts verified:

- CRSP publicly describes US stock databases covering common stocks on major US exchanges.
- CRSP describes price, return, shares outstanding, volume, and corporate-action-related data.
- CRSP publicly refers to historical descriptive information, inactive companies, delisting information, and delisting returns.

Facts not verified:

- Current subscription cost.
- Whether this project can access CRSP.
- Export format available to this local project.
- License rights for local caching and evidence-packet summaries.
- Whether earnings data is included or requires a separate source.

Interpretation:

CRSP is the strongest serious-research candidate if access, cost, license, and export workflow are acceptable. It is not automatically practical for this solo local project.

## Norgate Data

Official pages reviewed:

- https://norgatedata.com/
- https://norgatedata.com/data-content-tables.php

Facts verified:

- Norgate publicly describes survivorship-bias-free US equities data.
- Norgate publicly lists active and delisted US securities.
- Norgate publicly lists historical index constituents for major US indices.
- Norgate describes APIs including Python and adjusted price histories.

Facts not verified:

- Whether a delisting-return field or equivalent terminal treatment is available.
- Exact license terms for local caching.
- Exact cost for the needed package.
- Whether evidence-packet summaries can be shared externally.
- Earnings date availability.

Interpretation:

Norgate appears to be the strongest practical follow-up candidate, but serious Gate 2 remains blocked until cost, license, delisting treatment, and local workflow are verified.

## Nasdaq Data Link / Sharadar

Official pages reviewed:

- https://data.nasdaq.com/publishers/SHARADAR
- https://data.nasdaq.com/databases/SEP
- https://www.sharadar.com/data

Facts verified:

- Nasdaq Data Link / Sharadar is a plausible commercial dataset category for equity prices and fundamentals.

Facts not verified:

- Active and delisted stock coverage.
- Delisting returns or conservative terminal treatment.
- Point-in-time universe construction.
- Exact package availability, current documentation, cost, and license.

Interpretation:

Sharadar remains a possible candidate needing direct dataset and license verification.

## Polygon

Official pages reviewed:

- https://polygon.io/
- https://polygon.io/docs/stocks/getting-started

Facts verified:

- Polygon provides stock market data APIs and documentation.

Facts not verified:

- Survivorship-free historical universe.
- Active and delisted coverage sufficient for stock momentum.
- Delisting returns.
- Point-in-time universe membership.
- License terms for local research caching and evidence sharing.

Interpretation:

Polygon may be useful for price/reference data, but it is not verified as a serious stock-momentum research database.

## Tiingo

Official pages reviewed:

- https://www.tiingo.com/
- https://www.tiingo.com/documentation/general/overview

Facts verified:

- Tiingo provides market-data API access.

Facts not verified:

- Survivorship-free universe.
- Delisted stock coverage.
- Delisting returns.
- Point-in-time membership.
- License terms for this use case.

Interpretation:

Tiingo remains unknown for serious stock momentum until survivorship and delisting treatment are verified.

## EODHD

Official pages reviewed:

- https://eodhd.com/
- https://eodhd.com/financial-apis/

Facts verified:

- EODHD provides financial APIs and market-data style products.

Facts not verified:

- Survivorship-free universe.
- Delisted stock coverage and terminal treatment.
- Point-in-time membership.
- License and caching terms.

Interpretation:

EODHD remains an unknown or possible follow-up source, not a Gate 2-ready source.

## Interactive Brokers

Official pages reviewed:

- https://interactivebrokers.github.io/
- https://www.interactivebrokers.com/campus/ibkr-api-page/

Facts verified:

- Interactive Brokers provides API documentation and broker/platform access.

Facts not verified:

- Research-grade survivorship-free stock universe.
- Delisted stock history and delisting returns.
- Point-in-time historical membership.

Interpretation:

Interactive Brokers can be an execution/reference source, not the primary historical research database for this memo.

## Alpaca

Official pages reviewed:

- https://alpaca.markets/
- https://docs.alpaca.markets/

Facts verified:

- Alpaca provides broker/API and market-data documentation.

Facts not verified:

- Research-grade survivorship-free universe.
- Delisted stock history and delisting returns.
- Point-in-time historical membership.

Interpretation:

Alpaca is not verified as a serious historical stock-momentum research database. It is execution/reference oriented for this project.

## yfinance / Current Tickers

Official pages reviewed:

- https://pypi.org/project/yfinance/
- https://github.com/ranaroussi/yfinance

Facts verified:

- yfinance is a wrapper around Yahoo Finance downloads.
- The project describes itself for personal, educational, and research use and is not affiliated with Yahoo.

Facts not verified:

- A survivorship-free universe.
- Delisted stock coverage.
- Delisting returns.
- Point-in-time membership.

Interpretation:

yfinance/current-ticker data is toy-only for stock momentum. It cannot support serious validation.
