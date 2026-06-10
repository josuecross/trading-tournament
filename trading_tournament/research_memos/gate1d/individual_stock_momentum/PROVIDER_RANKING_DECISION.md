# Provider Ranking Decision

## 1. Preferred Provider For Next Terms Review

Preferred: `Norgate Data`

Reason: Norgate is the most practical first path for an individual research workflow because public documentation indicates survivorship-bias-free equity coverage, delisted securities at appropriate subscription levels, historical constituent access through supported integrations, and a local-machine data model. It still requires user cost/access acceptance, subscription-level confirmation, and EULA/cache-rights review.

## 2. Secondary Provider

Secondary: `Nasdaq Data Link / Sharadar`

Reason: Sharadar appears plausible for API-style active/delisted U.S. equity data and public-company history, but package-specific field coverage, delisting-treatment details, point-in-time universe support, API terms, and local cache rights must be verified.

## 3. Academic Reference Provider

Academic reference: `CRSP`

Reason: CRSP appears strongest for academic-grade stock history and delisting-return treatment. It should be used first only if the user already has legitimate access or can obtain it under acceptable terms.

## 4. Fallback Providers

Fallback providers: `Polygon/Massive`, `Tiingo`, `EODHD`

Reason: These may provide useful EOD/corporate-action API data, but the reviewed public information does not yet prove enough survivorship-free, delisting-return/treatment, and point-in-time universe support for serious stock-momentum evidence.

## 5. Toy Only Or Not Suitable

Toy/not serious for this historical lane: `yfinance/current ticker lists`, `Stooq/public CSV`, `Alpaca`, `Interactive Brokers`

Reason: Gate 1C already classified current-ticker/free or broker-adjacent sources as insufficient for serious survivorship-aware historical stock momentum.

## Ranking Decision

Pursue `Norgate Data` first for a future Gate 1E controlled acquisition review. This is not a data-download approval.

