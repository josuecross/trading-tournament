# Data Source Notes

Primary source used: `yfinance`.

- yfinance crypto data is Tier 1 exploratory only.
- Exchange-specific crypto prices may differ.
- Crypto trades 24/7 and daily bar timestamps can differ by source.
- No bid/ask spread, order book depth, exchange outage, delisting, custody, or stablecoin risk is modeled.

For crypto, `adj_close` is set equal to `close` when adjusted close is unavailable. This is documented as a Tier 1 exploratory convention, not a final data model.
