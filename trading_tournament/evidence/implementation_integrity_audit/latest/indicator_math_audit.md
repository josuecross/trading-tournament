# Indicator Math Audit

- 200-day SMA: implemented as rolling 200 trading-day mean of adjusted close.
- Trend eligibility: close > 200-day SMA.
- 126-day return: adjusted close / adjusted close shifted 126 trading days - 1.
- 63-day return: available in diagnostic core; not central to the audited current wrappers.
- 60-day realized volatility: rolling standard deviation of daily adjusted-close returns; non-annualized is acceptable for within-family ranking.
- Risk-adjusted rank: 126-day return / 60-day volatility with zero volatility treated as ineligible/very low rank.
- Positive 126-day return gate: used in dual momentum/PAA variants where documented; GTAA uses trend-filter eligibility without a separate positive-return gate.
- Monthly rebalance: first trading day of a new month uses prior trading day's signal, avoiding same-day lookahead under the project convention.
- Warmup: 200-day/126-day/60-day requirements are implicitly unavailable until enough history exists; sampled starts begin after warmup.

Finding: no high-severity indicator math bug found. The main caveat is that some families intentionally differ on whether positive 126-day return is required in addition to the 200-day trend gate.
