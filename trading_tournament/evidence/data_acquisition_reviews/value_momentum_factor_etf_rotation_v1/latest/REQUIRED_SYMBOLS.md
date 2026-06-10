# Required Symbols

Scope: `value_momentum_factor_etf_rotation_v1`

| symbol | currently_cached | required_or_optional | role | acceptable_substitute | cache_status | acquisition_status |
|---|---|---|---|---|---|---|
| MTUM | false | required_preferred | momentum proxy | none selected yet | missing_from_local_cache | data_acquisition_required |
| VLUE | false | preferred | value proxy | VTV | missing_from_local_cache | data_acquisition_required |
| VTV | false | acceptable_substitute | broad value substitute | VLUE | missing_from_local_cache | data_acquisition_required |
| QUAL | false | preferred | quality proxy | omit only if future rule is explicitly simplified | missing_from_local_cache | provider_review_required |
| USMV | false | preferred | low-vol proxy | SPLV | missing_from_local_cache | data_acquisition_required |
| SPLV | false | acceptable_substitute | low-vol substitute | USMV | missing_from_local_cache | provider_review_required |
| SPY | true | required_benchmark | market benchmark | none | available_in_local_cache | available_in_local_cache |
| BIL | true | required_cash_proxy | cash proxy | none | available_in_local_cache | available_in_local_cache |

Status interpretation:

- `missing_from_local_cache` means the local project cache does not currently contain the symbol.
- It does not mean the symbol is unavailable from public or keyed data providers.
- Missing factor proxies require provider review and an approved acquisition prompt before any download.
