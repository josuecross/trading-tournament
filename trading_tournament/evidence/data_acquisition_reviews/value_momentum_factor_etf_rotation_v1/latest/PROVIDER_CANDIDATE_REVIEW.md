# Provider Candidate Review

This review does not call APIs and does not download data. Provider availability is stated conservatively as likely, unknown, or needs provider lookup.

| symbol | role | cached_locally | candidate_providers | likely_available_from_provider | api_key_required | paid_or_free_unknown | adjustment_support_unknown | terms_review_required | proposed_next_action |
|---|---|---|---|---|---|---|---|---|---|
| MTUM | momentum proxy | false | yfinance; tiingo; alpha_vantage; nasdaq_data_link_sharadar; polygon_or_massive; stooq_or_other_public_csv | likely_but_requires_lookup | depends_on_provider | true | true | true | provider coverage and terms review before download prompt |
| VLUE | value proxy | false | yfinance; tiingo; alpha_vantage; nasdaq_data_link_sharadar; polygon_or_massive; stooq_or_other_public_csv | likely_but_requires_lookup | depends_on_provider | true | true | true | provider coverage and terms review before download prompt |
| VTV | broad value substitute | false | yfinance; tiingo; alpha_vantage; nasdaq_data_link_sharadar; polygon_or_massive; stooq_or_other_public_csv | likely_but_requires_lookup | depends_on_provider | true | true | true | provider coverage and terms review before download prompt |
| QUAL | quality proxy | false | yfinance; tiingo; alpha_vantage; nasdaq_data_link_sharadar; polygon_or_massive; stooq_or_other_public_csv | likely_but_requires_lookup | depends_on_provider | true | true | true | provider coverage and terms review before download prompt |
| USMV | low-vol proxy | false | yfinance; tiingo; alpha_vantage; nasdaq_data_link_sharadar; polygon_or_massive; stooq_or_other_public_csv | likely_but_requires_lookup | depends_on_provider | true | true | true | provider coverage and terms review before download prompt |
| SPLV | low-vol substitute | false | yfinance; tiingo; alpha_vantage; nasdaq_data_link_sharadar; polygon_or_massive; stooq_or_other_public_csv | likely_but_requires_lookup | depends_on_provider | true | true | true | provider coverage and terms review before download prompt |
| SPY | market benchmark | true | existing_local_cache | yes_cached | no | false | false_for_current_cache | false | use existing cache metadata only |
| BIL | cash proxy | true | existing_local_cache | yes_cached | no | false | false_for_current_cache | false | use existing cache metadata only |

Provider candidates reviewed:

1. `existing_local_cache`
2. `yfinance`
3. `alpha_vantage`
4. `tiingo`
5. `nasdaq_data_link_sharadar`
6. `polygon_or_massive`
7. `stooq_or_other_public_csv`

No provider is automatically approved for new downloads by this packet. Any future acquisition must explicitly pass terms, security, reproducibility, adjustment, and quality gates.
