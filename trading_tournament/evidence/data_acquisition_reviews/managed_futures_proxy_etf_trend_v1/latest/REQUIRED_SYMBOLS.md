# Required Symbols

Missing from local cache means `data_acquisition_required` or `provider_review_required`. It does not mean the symbol is permanently unavailable.

| symbol | intended_proxy_role | currently_cached | required_or_optional | possible_substitute | cache_status | acquisition_status | ticker_ambiguity_risk | notes |
|---|---|---:|---|---|---|---|---|---|
| DBMF | managed-futures ETF proxy | false | high_priority | KMLM or CTA if coverage/methodology passes | missing_from_local_cache | data_acquisition_required | low_to_medium | High-priority managed-futures proxy candidate; provider coverage and inception date must be checked. |
| KMLM | managed-futures ETF proxy | false | high_priority | DBMF or CTA if coverage/methodology passes | missing_from_local_cache | data_acquisition_required | low_to_medium | High-priority managed-futures proxy candidate; provider coverage and methodology must be reviewed. |
| CTA | CTA/managed-futures ETF proxy | false | review_required | DBMF or KMLM if ticker identity is ambiguous | missing_from_local_cache | provider_review_required | high | Ticker ambiguity must be checked before any download prompt; provider lookup must confirm the intended fund. |
| FMF | managed-futures ETF/fund proxy | false | optional_review | DBMF, KMLM, or CTA if available | missing_from_local_cache | provider_review_required | medium | Optional/lower-priority proxy; inclusion depends on provider coverage, inception history, and methodology clarity. |
| WTMF | managed-futures ETF/fund proxy | false | optional_review | DBMF, KMLM, or CTA if available | missing_from_local_cache | provider_review_required | medium | Optional/lower-priority proxy; inclusion depends on provider coverage, fund status, and methodology clarity. |

No raw OHLCV is included in this review.

