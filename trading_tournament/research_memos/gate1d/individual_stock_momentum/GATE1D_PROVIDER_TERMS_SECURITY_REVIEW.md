# Gate 1D Provider Terms Security Review

This review uses Gate 1B/Gate 1C local evidence plus public provider documentation pages. No account was created, no provider API was called, no stock data was downloaded, no API key was created, and no credentials were stored.

## Purpose

Gate 1D decides which serious provider path should be pursued first for individual stock momentum research. It focuses on field coverage, cache rights, security boundaries, and feasibility before any controlled acquisition prompt.

## Gate 1C Carry-Forward

Gate 1C concluded that individual stock momentum cannot proceed on current-ticker-only data as serious evidence. Serious research requires survivorship-aware coverage, delisted names, delisting treatment, point-in-time or all-listed universe support, corporate actions, liquidity fields, cache metadata, and security controls.

## Public Documentation Reviewed

- Norgate Data overview, data-content tables, FAQ, and subscription notes.
- Nasdaq Data Link documentation, terms, help center, and Sharadar publisher/data pages.
- CRSP US Stock Databases and CRSP stock/index guide pages.
- Massive/Polygon stock docs and knowledge-base notes for delisted tickers/corporate actions.
- Tiingo and EODHD public product/docs pages for field availability clues.

## Review Result

Norgate Data is the preferred practical provider path for the next Gate 1E controlled acquisition review because public documentation indicates survivorship-bias-free market data, delisted securities at appropriate subscription levels, historical index constituent access through supported integrations, and local-machine database access. These claims still require user cost/access acceptance and terms/security confirmation.

Nasdaq Data Link / Sharadar is the secondary serious path. It may support active and delisted U.S. public-company coverage, but package-specific fields, terms, API-key handling, and delisting-treatment details must be verified before acquisition.

CRSP remains the academic reference path if access exists. It appears strongest for delisting-return treatment and academic-grade history, but likely requires institutional or restricted access.

Polygon/Massive, Tiingo, and EODHD remain fallback providers only. Public pages suggest useful price/corporate-action APIs, and Massive currently documents delisted ticker handling, but the project should not treat them as serious survivorship-aware evidence until delisting treatment, point-in-time universe construction, security identifiers, cache rights, and terms are verified.

## Decision Boundary

This review does not approve data acquisition, stock strategy implementation, stock data loaders, backtests, Profit Exploration, candidate_exhaustive, paper-forward observation, broker integration, live orders, or real-money recommendations.

