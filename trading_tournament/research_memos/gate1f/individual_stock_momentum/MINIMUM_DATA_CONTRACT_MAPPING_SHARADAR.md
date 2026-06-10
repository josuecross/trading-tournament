# Minimum Data Contract Mapping For Sharadar

Mapping statuses:

- `mapped_from_reviewed_docs`
- `likely_but_needs_sample`
- `unknown`
- `not_available`
- `package_dependent`

No API sample was acquired.

| Required field | candidate_sharadar_source | mapping_status | required_for_tiny_sample | blocker_if_missing |
|---|---|---|---:|---|
| symbol | Equity Prices / metadata | likely_but_needs_sample | true | Cannot identify securities. |
| permanent_id if available | TICKERS/metadata or related identifiers | unknown | false | Symbol-change handling weaker. |
| date | Equity Prices date field | likely_but_needs_sample | true | Cannot align bars/events. |
| open/high/low/close/volume | SEP / Equity Prices | likely_but_needs_sample | true | Cannot validate price momentum. |
| adjusted close or adjustment factors | SEP / Equity Prices adjustment fields | likely_but_needs_sample | true | Returns may be distorted. |
| splits/dividends | ACTIONS/corporate actions | package_dependent | true | Adjustment audit incomplete. |
| delisting date | metadata/status/delisted fields | package_dependent | true | Survivorship check incomplete. |
| delisting return or delisting price treatment | unknown delisting treatment fields or local final-price rule | unknown | true | Delisting impact may be understated. |
| exchange | TICKERS/metadata | likely_but_needs_sample | true | Exchange filter unavailable. |
| security type | TICKERS/metadata | package_dependent | true | Common-stock filter unavailable. |
| active/inactive status | TICKERS/metadata or delisted coverage | likely_but_needs_sample | true | Survivorship status unavailable. |
| corporate action metadata | ACTIONS/corporate actions | package_dependent | true | Corporate-action handling cannot be audited. |
| universe membership or all-listed universe | active/delisted metadata plus security filters | package_dependent | true | PIT/all-listed universe claim blocked. |
| liquidity fields | volume plus local dollar-volume calculation | likely_but_needs_sample | true | Liquidity filter cannot be tested. |
| provider metadata | Nasdaq Data Link table/package metadata | likely_but_needs_sample | true | Reproducibility weak. |
| acquisition timestamp | project acquisition metadata | likely_but_needs_sample | true | Cache governance incomplete. |
| cache version | project cache manifest plus provider table/version metadata | package_dependent | true | Refresh audit weak. |
| data quality flags | project-generated checks | likely_but_needs_sample | true | Quality gate cannot pass. |

## Mapping Conclusion

Sharadar may map enough fields for a serious tiny-sample review, but the mapping cannot be accepted until package selection and an approved metadata/tiny sample confirm table fields and terms.

