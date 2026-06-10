# Data Requirements

Current project ETF yfinance data is not enough for serious individual-stock momentum testing.

## Required Before Implementation

1. Point-in-time stock universe: the system must know which stocks were available at each historical date.
2. Survivorship-free historical universe: failed, merged, acquired, and delisted names must be represented.
3. Delisted stock returns: delisting returns or terminal values must be included where possible.
4. Corporate actions: splits, dividends, mergers, spin-offs, symbol changes, and distributions must be handled.
5. Split/dividend adjusted OHLCV: adjusted fields must be auditable, not opaque.
6. Earnings calendar and earnings date handling: event dates must be point-in-time and not leaked.
7. Liquidity filters: average dollar volume, share volume, and trading days active.
8. Minimum price filters: penny and very-low-price names should be excluded.
9. Average dollar volume filters: minimum liquidity must be explicit before testing.
10. IPO seasoning rule: new listings need a minimum history before ranking.
11. Sector/industry classification if used: sector controls must be point-in-time.
12. Benchmark universe: a broad stock universe benchmark must be defined.
13. Data vendor candidates: survivorship-free vendors should be identified before coding.
14. yfinance limitation: current ticker lists from yfinance are not survivorship-free and do not solve delisting bias.

## Strict Data Gate

No stock momentum implementation should begin until the universe construction and delisting treatment are documented. A current-ticker backtest may be useful only as a toy demo and must not be presented as serious evidence.

