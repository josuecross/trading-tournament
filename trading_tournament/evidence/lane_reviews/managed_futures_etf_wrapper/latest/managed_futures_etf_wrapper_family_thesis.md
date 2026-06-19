# Managed Futures ETF Wrapper Family Thesis

Family id: `managed_futures_etf_wrapper`

Thesis: use ETF/fund wrappers that provide managed-futures-style or broad trend-following exposure to test whether the project can find a more additive return stream than equity/growth/sector-heavy families.

Why this family may help:

- It may be less correlated with SPY/QQQ/sector behavior.
- It may help during equity drawdowns.
- It may add crisis-alpha-like behavior through ETF wrappers.
- It may complement VM quality and DSR equal-weight without modifying them.
- It may improve the portfolio-level profit/risk frontier.

Why this family may fail:

- ETF wrapper histories may be short.
- Managed-futures ETFs can have high fees and tracking differences.
- Some wrappers may be too slow or low-return.
- Some wrappers may underperform in equity bull markets.
- Some wrappers may be internally futures-based, but the project only trades ETF shares.
- Performance may depend heavily on start date.
- A wrapper may look good only because of one recent regime.

This lane must not directly trade futures contracts. It must only use ETF/fund wrappers.
