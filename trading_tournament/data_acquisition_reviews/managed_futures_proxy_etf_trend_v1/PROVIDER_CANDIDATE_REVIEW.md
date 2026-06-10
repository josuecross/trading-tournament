# Provider Candidate Review

This review does not call APIs and does not download data. Provider coverage statements are conservative and must be verified by a future provider terms/security review.

| provider_id | likely_supports_etf_or_fund_daily_history | likely_supports_adjusted_close | likely_supports_dividends_splits | requires_api_key | terms_review_required | cost_or_rate_limit_risk | secret_handling_required | provider_status | notes |
|---|---|---|---|---|---|---|---|---|---|
| existing_local_cache | yes_if_cached | yes_if_cached | yes_if_cached | no | no | none | no | checked_missing | No reviewed managed-futures proxy symbol is currently in `data/cache`. |
| yfinance | likely | likely | likely_actions_available | no_key_for_library_path | yes | rate_limit_and_terms_risk | no_key_expected | provider_terms_review_required | Existing project has yfinance-compatible conventions, but future download must be explicit and metadata-captured. Coverage for each ticker requires lookup. |
| tiingo | likely | likely | likely | yes | yes | key_and_rate_limit_risk | yes | provider_terms_review_required | Possible fallback if terms, API key handling, and adjusted fields are acceptable. |
| alpha_vantage | likely_or_unknown | likely_or_unknown | unknown | yes_or_unknown | yes | key_and_rate_limit_risk | yes | provider_terms_review_required | Possible fallback; coverage, adjustment behavior, and rate limits require lookup. |
| nasdaq_data_link_sharadar | likely_for_funds_if_subscription | likely | likely | yes | yes | paid_or_access_risk | yes | provider_terms_review_required | Better-governed keyed path if access and licensing are acceptable. |
| polygon_or_massive | likely | likely | unknown | yes | yes | paid_or_rate_limit_risk | yes | provider_terms_review_required | Possible fallback; cost, ETF coverage, and adjustment fields require review. |
| issuer_fund_pages_metadata | metadata_only | no | no | no | yes | manual_reproducibility_risk | no | methodology_reference_only | Useful for inception, methodology, expense ratio, and holdings/risk-target notes, not as price data. |
| public_csv_sources | unknown | unknown | unknown | no_or_unknown | yes | reproducibility_and_terms_risk | no_or_unknown | review_required | Use only if terms, adjustments, and reproducibility are acceptable. |

No provider is approved for immediate download by this packet.

