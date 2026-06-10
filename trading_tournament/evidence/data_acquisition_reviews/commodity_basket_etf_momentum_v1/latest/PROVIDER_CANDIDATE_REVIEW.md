# Provider Candidate Review

No provider API was called. No data was downloaded. Labels are conservative and must be verified before any future acquisition prompt.

| provider_id | likely_supports_etf_or_fund_daily_history | likely_supports_adjusted_close | likely_supports_dividends_splits | likely_supports_actions_or_distributions | requires_api_key | terms_review_required | cost_or_rate_limit_risk | secret_handling_required | provider_status | notes |
|---|---|---|---|---|---|---|---|---|---|---|
| existing_local_cache | no_for_symbols_reviewed | not_applicable | not_applicable | not_applicable | no | no | none | no | insufficient | DBC, PDBC, COMT, GSG, and USCI are not cached locally. |
| yfinance_compatible_path | likely | likely | likely | unknown | no_key_typically | terms review required | rate_limit_and_revision_risk | no_api_secret_expected | not approved yet | Candidate future path for ETF/fund wrapper price data after product identity review. |
| Tiingo | likely | likely | likely | unknown | yes | terms review required | cost_or_rate_limit_risk | yes | not approved yet | Keyed provider; requires secret handling and terms review. |
| Alpha Vantage | likely | unknown | unknown | unknown | yes | terms review required | rate_limit_risk | yes | not approved yet | Keyed provider; adjusted fields and commodity wrapper coverage require verification. |
| Nasdaq Data Link | likely | unknown | unknown | unknown | yes | terms review required | package_cost_or_rate_limit_risk | yes | not approved yet | Package/table coverage for ETF wrappers requires verification. |
| Polygon/Massive | likely | likely | unknown | unknown | yes | terms review required | cost_or_rate_limit_risk | yes | not approved yet | Keyed provider; ETF adjusted data and actions coverage require verification. |
| issuer_fund_pages_metadata_only | not_price_history_path | not_applicable | not_applicable | likely_metadata_only | no_or_account_unknown | terms review required | low | no_secret_expected | metadata only | Useful for product identity, issuer, wrapper, fees, tax docs, methodology, inception. |
| public_csv_sources | unknown | unknown | unknown | unknown | no_or_unknown | terms review required | reproducibility_risk | no_or_unknown | not approved yet | Only acceptable if terms, reproducibility, adjusted fields, and metadata are adequate. |

## Provider Review Conclusion

The likely future provider path is a yfinance-compatible acquisition review after product identity and terms are confirmed. Keyed providers remain fallback paths only. Issuer/fund pages are useful for metadata, not raw market data.
