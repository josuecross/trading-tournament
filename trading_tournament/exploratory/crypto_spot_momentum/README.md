# Crypto Spot Momentum Exploratory Lane

This lane tests simple long-only crypto spot momentum as a Tier 1 exploratory screen.

It is separate from the ETF validated lane. It does not modify ETF strategy results, does not integrate crypto results into ETF candidate validation, and does not approve paper-forward trading.

Scope:

- Daily OHLCV only.
- BTC and ETH spot proxies by default.
- Long-only.
- No leverage.
- No margin.
- No shorting.
- No perpetuals.
- No futures.
- No options.
- No intraday trading.
- No broker or exchange trading functionality.

Default data source is `yfinance` using `BTC-USD` and `ETH-USD`. Optional CCXT support is intentionally non-default and only used if the package is already installed and the user explicitly selects it.

Evidence is labeled:

- `credibility_tier: Tier 1 exploratory screen`
- `final_validation: false`
- `candidate_validation: false`
- `paper_forward_ready: false`
- `real_money_recommendation: false`

Allowed conclusions are limited to exploratory language such as `interesting exploratory hypothesis`, `not worth further research`, `needs better data`, or `requires Tier 2 credible prototype`.

Forbidden conclusions include `validated`, `profitable`, `reliable`, `paper-forward ready`, `real-money suitable`, and `proven`.
