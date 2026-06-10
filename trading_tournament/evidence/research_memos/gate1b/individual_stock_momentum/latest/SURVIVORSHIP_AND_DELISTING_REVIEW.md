# Survivorship And Delisting Review

Current-ticker-only stock backtests are biased because they exclude bankruptcies, mergers, acquisitions, exchange removals, ticker changes, and stocks that fell out of the tradable universe. Momentum strategies can look materially better when the historical universe only contains survivors.

Delisted stocks matter because losers and failed securities are part of the opportunity set a historical strategy would have faced. Delisting returns matter because the final loss or cash-out event can dominate tail outcomes.

## Minimum Policy

Minimum credible research requires a survivorship policy that either includes delisted names or explicitly labels the result as toy/current-ticker only. Serious validation requires delisting treatment and clear point-in-time universe construction.

## Exploratory Exceptions

Current-ticker-only testing may be allowed only as Tier 1 toy evidence to test code flow, runtime, turnover, and rough mechanics. It must not be used for performance claims.

## Data-State Classification

- `serious_survivorship_free`: survivorship-free universe, delisted names, delisting treatment, and point-in-time selection are available.
- `credible_with_delisted_names_but_limited_returns`: delisted names are available, but delisting returns or event treatment are limited; usable only with warnings.
- `exploratory_current_ticker_only`: current tickers only; toy behavior only.
- `toy_demo_only`: small static ticker list, no serious historical conclusion.
- `rejected`: no adjustment integrity, no universe policy, or misleading survivorship claims.

Rejected: any review that presents current-ticker-only evidence as serious validation.

