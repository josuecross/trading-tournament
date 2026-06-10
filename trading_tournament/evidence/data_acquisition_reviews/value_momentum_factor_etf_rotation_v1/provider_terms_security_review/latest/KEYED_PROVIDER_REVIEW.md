# Keyed Provider Review

This review does not call providers and does not create API keys.

| provider | requires_api_key | likely_supports_etf_daily_history | adjustment_support_unknown | cost_or_rate_limit_risk | terms_review_required | secret_handling_required | when_to_use |
|---|---|---|---|---|---|---|---|
| Alpha Vantage | yes_or_unknown | likely | true | rate_limit_and_plan_limits | true | true | Use only if yfinance-compatible path fails or terms/quality are unacceptable and an external key is available. |
| Tiingo | yes | likely | false_or_requires_review | plan_limits_possible | true | true | Use if yfinance-compatible data fails quality/terms and Tiingo terms allow local research cache. |
| Nasdaq Data Link / Sharadar | yes | likely | false_or_requires_review | paid_or_access_limited | true | true | Use for higher-governance equity/ETF data if paid/keyed access and licensing are acceptable. |
| Polygon/Massive | yes | likely | true | pricing_and_rate_limits | true | true | Use only after coverage, adjustment, cost, and terms review. |

Keyed providers are not approved for immediate use by this packet. They remain fallback review paths if the yfinance-compatible path is rejected or fails quality checks.
