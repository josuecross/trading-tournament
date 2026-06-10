# Sharadar Package And Table Review

This table lists candidate packages/tables that may be needed. Names are conservative and must be verified against the selected Nasdaq Data Link / Sharadar subscription before any API call.

| table_or_package | purpose | required_for_momentum | supports_minimum_data_contract_fields | package_dependency | unknowns | blocker_if_missing |
|---|---|---:|---|---|---|---|
| SEP / Equity Prices | Daily stock price history for active/delisted equities | true | symbol, date, OHLCV, adjusted/unadjusted price fields, volume if available | subscription_required | exact adjusted/unadjusted columns, delisted treatment | Cannot test price momentum. |
| TICKERS / metadata table | Security/company metadata and active/delisted flags | true | symbol, name, exchange, active/inactive, security type if present | package_dependent | stable IDs, type filters, date availability | Cannot build survivorship-aware universe filters. |
| ACTIONS / corporate actions | Splits, dividends, ticker/action events | true | splits/dividends, corporate actions, adjustment audit | package_dependent | event types, ticker-change coverage | Cannot audit adjustment integrity. |
| delisted/inactive coverage table or field | Delisted stock inclusion and status | true | delisting date/status, active/inactive status | package_dependent | delisting prices/returns, final treatment | Survivorship control incomplete. |
| ticker history / related tickers field | Symbol change tracking | true | permanent/ticker mapping support | package_dependent | exact relationship fields and dates | Symbol-change bias remains unresolved. |
| exchange/security-type metadata fields | Filter common stocks and exclude unsuitable instruments | true | exchange, security type, active/inactive status | package_dependent | common-stock classification availability | Universe may contain non-target instruments. |
| SF1 fundamentals | Fundamentals for future non-price research | false | not required for price momentum | subscription_required | not needed for Gate 1F | Not a blocker for price momentum. |

## Package Review Conclusion

The minimum serious path likely needs at least Equity Prices plus metadata/tickers plus actions/corporate-action support. If delisted/inactive coverage and security-type metadata are unavailable in the selected package, serious stock momentum remains blocked.

