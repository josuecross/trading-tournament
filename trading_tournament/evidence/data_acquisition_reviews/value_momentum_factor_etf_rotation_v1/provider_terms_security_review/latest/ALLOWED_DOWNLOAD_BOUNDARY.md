# Allowed Download Boundary

This boundary is for a future task only. No download is performed here.

## Allowed Symbols

If a future yfinance-compatible download prompt is executed, it may acquire only:

- MTUM
- VLUE
- VTV
- QUAL
- USMV
- SPLV

## Existing Cached Symbols

SPY and BIL are already cached. Do not refresh or overwrite them by default. A refresh requires explicit future approval.

## Required Boundaries

Future download must:

- use no broker APIs,
- use no live orders,
- use no strategy logic,
- use no backtest trigger,
- produce provider metadata,
- produce coverage summaries,
- produce data-quality summaries,
- keep raw OHLCV out of advisor upload,
- avoid secrets in the repo,
- stop before strategy implementation.

The future output should be a data-quality packet, not a trading recommendation.
