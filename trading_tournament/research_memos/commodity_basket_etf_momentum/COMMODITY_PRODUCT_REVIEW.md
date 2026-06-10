# Commodity Product Review

This review uses local cache inspection only for cache status. No price data was downloaded and no provider API was called. Product names and issuers below are common product identifiers that must be rechecked against official product documentation before any acquisition or implementation.

| symbol | product_name_if_known | issuer_if_known | ETF_or_ETN_or_fund_structure | exchange_traded_wrapper | commodity_exposure_type | broad_commodity_or_sector_specific | futures_based_exposure_likely | collateral_or_t_bill_component_likely | active_or_index_based | current_local_cache_status | first_cached_date_if_available | last_cached_date_if_available | row_count_if_available | product_risk_level | review_status | notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---:|---|---|---|
| DBC | Invesco DB Commodity Index Tracking Fund | Invesco | commodity pool/fund wrapper, needs official confirmation | true | futures-linked broad commodity index exposure | broad commodity basket | true | likely | index_based_likely | missing | unavailable | unavailable | 0 | high | acceptable_for_data_review | Product/tax/wrapper review is required before use; likely K-1/partnership-style complexity. |
| PDBC | Invesco Optimum Yield Diversified Commodity Strategy No K-1 ETF | Invesco | ETF, needs official confirmation | true | futures-linked broad commodity strategy exposure | broad commodity basket | true | likely | active_or_rules_based_likely | missing | unavailable | unavailable | 0 | medium | acceptable_for_data_review | May be easier operationally than K-1 products, but wrapper methodology and collateral treatment still need review. |
| COMT | iShares GSCI Commodity Dynamic Roll Strategy ETF | iShares / BlackRock | ETF, needs official confirmation | true | futures-linked dynamic-roll commodity strategy | broad commodity basket | true | likely | index_or_rules_based_likely | missing | unavailable | unavailable | 0 | medium | acceptable_for_data_review | Dynamic roll methodology can make results product-specific. |
| GSG | iShares S&P GSCI Commodity-Indexed Trust | iShares / BlackRock | commodity trust/fund wrapper, needs official confirmation | true | futures-linked S&P GSCI commodity exposure | broad commodity basket | true | likely | index_based_likely | missing | unavailable | unavailable | 0 | high | acceptable_for_data_review | Product/tax/wrapper risk must be reviewed; broad commodity exposure may be energy-heavy depending methodology. |
| USCI | United States Commodity Index Fund | USCF | commodity pool/fund wrapper, needs official confirmation | true | futures-linked commodity index exposure | broad commodity basket | true | likely | index_or_rules_based_likely | missing | unavailable | unavailable | 0 | high | acceptable_for_data_review | Product/tax/wrapper review is required before use; likely K-1/partnership-style complexity. |

## Local Cache Finding

None of DBC, PDBC, COMT, GSG, or USCI exists in `data/cache/` at the time of this review.

## Product Review Conclusion

All five symbols can proceed only to a controlled data-acquisition review, not implementation. The future review must verify official product structure, issuer, methodology, tax/wrapper treatment, inception, adjusted-price availability, liquidity, and terms before any data download.
