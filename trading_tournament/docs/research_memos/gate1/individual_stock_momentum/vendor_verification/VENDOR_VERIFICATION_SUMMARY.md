# Vendor Verification Summary

## Research-Only Statement

This packet is a research-only feasibility review. It does not approve stock momentum implementation, does not validate any strategy, does not connect to a broker, does not place orders, and does not recommend real-money trading.

## What Was Verified

Official or primary pages were manually reviewed for CRSP, Norgate Data, Nasdaq Data Link / Sharadar, Polygon, Tiingo, EODHD, Interactive Brokers, Alpaca, and yfinance. The review focused on whether each source appears capable of supporting credible individual-stock momentum research.

Verified high-level findings:

- CRSP publicly describes US stock databases with active and inactive company coverage, corporate actions, and delisting information/returns. It appears to be the strongest serious-research data candidate if access, cost, license, and export workflow are acceptable.
- Norgate Data publicly describes survivorship-bias-free US equities, active and delisted securities, historical index constituents, adjusted histories, and APIs. It appears to be the strongest practical follow-up candidate for a solo local project if license, cost, and delisting-return treatment are acceptable.
- yfinance is a Yahoo Finance download wrapper intended for personal/educational/research use and does not solve survivorship-free universe or delisting-return requirements. It remains toy-only for individual-stock momentum.
- Interactive Brokers and Alpaca provide broker/API and market-data references, but no official evidence was verified here that they solve survivorship-free universe construction, delisted stock history, and delisting returns for serious historical stock research.

## What Could Not Be Verified

The review did not verify vendor contracts, exact prices, trial terms, raw data schemas, local caching rights, redistribution limits, complete delisting-return fields, point-in-time universe construction details, earnings timestamp quality, or storage/runtime burden from a real export.

Sharadar/Nasdaq Data Link, Polygon, Tiingo, and EODHD remain unresolved for serious research until their delisted coverage, universe construction, corporate action treatment, and license/cost details are confirmed directly from official documentation or vendor support.

## Most Credible Serious Research Sources

1. CRSP: strongest academic/institutional candidate, but likely high access and licensing burden.
2. Norgate Data: strongest practical follow-up candidate based on public survivorship-bias-free and delisted-security descriptions, but delisting-return treatment and license/caching terms still need verification.
3. Nasdaq Data Link / Sharadar: possible candidate needing documentation and subscription verification.

## Toy/Demo-Only Sources

yfinance/current-ticker data is toy-only for stock momentum. It may be useful for learning mechanics only if explicitly isolated and labeled non-evidence, but it cannot support serious claims because it does not provide a survivorship-free historical universe with delisting treatment.

## Unsuitable Or Reference-Only Sources

Interactive Brokers and Alpaca are reference/execution-oriented sources for this research question unless they can separately provide survivorship-free, active-and-delisted historical equity universes with corporate action and delisting treatment. That was not verified.

## Gate 2 Status

Serious Gate 2 isolated prototype is not approved. Toy demo is not approved in this Gate 1A packet.

The current decision is `continue_defer`.

## Remaining Unresolved Items

- Confirm CRSP access, pricing, export terms, local caching rights, and project practicality.
- Confirm Norgate license/cost, delisting-return or terminal-price treatment, corporate-action fields, Python workflow, and local caching rights.
- Confirm whether Sharadar/Nasdaq Data Link includes active and delisted coverage, delisting returns or terminal treatment, point-in-time universe construction, and acceptable license/cost.
- Verify earnings date data source if stock strategies need earnings avoidance.
- Estimate storage/runtime from actual vendor sample exports before any prototype decision.
