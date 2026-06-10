# Keyed Provider Review

No provider was called in this task. Keyed providers are fallback only unless yfinance-compatible acquisition is rejected or fails data quality.

| provider | requires_api_key | likely_supports_etf_or_fund_daily_history | adjustment_support_unknown | cost_or_rate_limit_risk | terms_review_required | secret_handling_required | when_to_use |
|---|---|---|---:|---|---:|---:|---|
| Tiingo | yes | likely | false_or_unknown | key and rate-limit risk | true | true | Use if yfinance-compatible coverage fails and Tiingo terms/fields are acceptable. |
| Alpha Vantage | yes_or_unknown | likely_or_unknown | true | key and rate-limit risk | true | true | Use only after coverage and adjustment behavior are reviewed. |
| Nasdaq Data Link / Sharadar | yes | likely_if_access_available | false_or_unknown | paid/access risk | true | true | Use if serious keyed data access is available and licensing permits research cache use. |
| Polygon/Massive | yes | likely | true | paid/rate-limit risk | true | true | Use if coverage, cost, and adjusted-field behavior are acceptable. |

Keyed providers are not approved for immediate use.

