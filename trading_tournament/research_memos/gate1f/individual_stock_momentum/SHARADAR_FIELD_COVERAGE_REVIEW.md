# Sharadar Field Coverage Review

Status labels:

- `confirmed_from_reviewed_docs`
- `likely_but_needs_api_sample`
- `unknown`
- `not_supported`
- `package_dependent`
- `subscription_required`

No API was called and no data was downloaded.

| Field | Status | Notes |
|---|---|---|
| active stocks | likely_but_needs_api_sample | Sharadar public-company data likely includes active coverage, but package/table confirmation is required. |
| delisted stocks | confirmed_from_reviewed_docs | Prior reviewed Nasdaq/Sharadar notes indicate U.S. Sharadar Equity Prices cover delisted stocks. |
| delisting prices or returns / local treatment | unknown | Coverage of delisted names is not the same as delisting-return treatment. Must verify fields. |
| adjusted OHLCV | likely_but_needs_api_sample | Equity Prices likely supports adjusted prices; exact columns require sample. |
| unadjusted OHLCV if needed | likely_but_needs_api_sample | Must verify table columns and adjustment conventions. |
| splits/dividends | package_dependent | Candidate ACTIONS/corporate-action tables may be required. |
| corporate actions | package_dependent | Must verify actions package/table availability and event types. |
| ticker changes | unknown | Needs metadata/ticker-history verification. |
| permanent identifiers | unknown | Must verify whether stable security/company identifiers exist and persist across ticker changes. |
| point-in-time public-company coverage | package_dependent | Sharadar may support public-company history, but PIT universe construction must be proven. |
| all-listed universe construction | package_dependent | Requires active/delisted metadata, security type, exchange fields, and date coverage. |
| security type filtering | likely_but_needs_api_sample | Candidate metadata/tickers fields may support this. |
| exchange filtering | likely_but_needs_api_sample | Candidate metadata/tickers fields may support this. |
| liquidity fields / volume | likely_but_needs_api_sample | Daily prices likely include volume; sample required. |
| provider metadata | likely_but_needs_api_sample | Nasdaq Data Link table/API metadata can likely be captured if terms allow. |
| API download metadata | likely_but_needs_api_sample | Need sample and local logging plan. |
| local cache feasibility | package_dependent | Terms/order must permit local research cache. |

## Field-Coverage Conclusion

Sharadar is credible enough for a package/terms follow-up, but not enough for acquisition. The major blockers are delisting treatment, ticker-history identifiers, PIT/all-listed universe support, and cache-rights verification.

