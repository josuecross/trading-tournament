# Provider Field Coverage Review

Labels used:

- `confirmed_from_official_docs`
- `likely_but_needs_verification`
- `unknown`
- `not_supported`
- `requires_paid_access`
- `requires_institutional_access`

No provider APIs were called. No stock data was downloaded.

## Norgate Data

| Field | Review label | Notes |
|---|---|---|
| survivorship-free equities | confirmed_from_official_docs | Public overview says Norgate specializes in survivorship-bias-free stock-market data. |
| delisted names | confirmed_from_official_docs | Data-content pages describe US Delisted availability at Platinum/Diamond levels. |
| delisting returns or treatment | likely_but_needs_verification | Delisted securities and last bar metadata are documented; exact delisting return treatment needs product review. |
| adjusted OHLCV | likely_but_needs_verification | Historical daily/end-of-day access appears available; adjusted-field mechanics need mapping. |
| splits/dividends | confirmed_from_official_docs | Data-content tables list dividend and capital-event related data. |
| corporate actions | confirmed_from_official_docs | Capital Event and security information fields are listed. |
| symbol changes | likely_but_needs_verification | FAQ discusses lifecycle name/symbol changes and delisted symbol suffixes. |
| permanent/security IDs | unknown | Must verify identifiers exposed through plugins/API. |
| point-in-time universe membership | confirmed_from_official_docs | Historical index constituent true/false access is documented for supported integrations/subscription levels. |
| all-listed common stock universe | likely_but_needs_verification | Broad listed/delisted market coverage appears plausible; common-stock filter must be mapped. |
| exchange/security-type filters | confirmed_from_official_docs | Data-content tables include security classification and major-exchange listing identification. |
| active/inactive status | likely_but_needs_verification | Listed vs delisted database structure supports this, but exact field mapping needs Gate 1E. |
| liquidity fields | likely_but_needs_verification | OHLCV implies volume; dollar-volume construction must be local. |
| local cache feasibility | confirmed_from_official_docs | Overview describes a local proprietary database on the user's Windows machine. |
| metadata/versioning feasibility | likely_but_needs_verification | Metadata exists; cache-version metadata must be designed locally. |
| API or bulk export | likely_but_needs_verification | Plugins/APIs and ASCII export are documented, but feature completeness varies. |
| required subscription/account | requires_paid_access | Subscription level matters. |

## Nasdaq Data Link / Sharadar

| Field | Review label | Notes |
|---|---|---|
| survivorship-free equities | likely_but_needs_verification | Sharadar pages describe active and delisted coverage nearly free from survivorship bias; package details must verify. |
| delisted names | confirmed_from_official_docs | Nasdaq help center says U.S. Sharadar Equity Prices cover delisted stocks. |
| delisting returns or treatment | unknown | Must verify whether returns, delisting prices, or enough fields exist for local treatment. |
| adjusted OHLCV | likely_but_needs_verification | Sharadar Equity Prices and daily stock price data suggest price coverage; exact adjusted/unadjusted fields need mapping. |
| splits/dividends | likely_but_needs_verification | Corporate/fundamental packages may include actions; package coverage must be checked. |
| corporate actions | likely_but_needs_verification | Must verify package and table fields. |
| symbol changes | unknown | Must verify ticker-history support. |
| permanent/security IDs | unknown | Must verify identifiers in tables. |
| point-in-time universe membership | unknown | Must verify PIT universe or all-listed construction feasibility. |
| all-listed common stock universe | likely_but_needs_verification | Active/delisted public-company coverage may support this after filtering. |
| exchange/security-type filters | likely_but_needs_verification | Must verify fields. |
| active/inactive status | likely_but_needs_verification | Active/delisted coverage suggests feasibility. |
| liquidity fields | likely_but_needs_verification | Daily price data likely includes volume; must verify. |
| local cache feasibility | likely_but_needs_verification | Nasdaq Data Link docs mention downloads and APIs; local rights depend on terms/order. |
| metadata/versioning feasibility | likely_but_needs_verification | API/download metadata can be recorded locally if terms permit. |
| API or bulk export | confirmed_from_official_docs | Nasdaq Data Link documents REST APIs, downloads, libraries, and premium datasets. |
| required subscription/account | requires_paid_access | Premium subscriptions and API access likely required. |

## CRSP

| Field | Review label | Notes |
|---|---|---|
| survivorship-free equities | confirmed_from_official_docs | CRSP stock databases are broad academic equity databases. |
| delisted names | confirmed_from_official_docs | CRSP pages list security delisting information. |
| delisting returns or treatment | confirmed_from_official_docs | CRSP documentation describes delisting-return calculation and missing codes. |
| adjusted OHLCV | confirmed_from_official_docs | Price, quote, return, distribution, and derived items are documented. |
| splits/dividends | confirmed_from_official_docs | Corporate actions and dividend data are documented. |
| corporate actions | confirmed_from_official_docs | Corporate actions are listed as key data items. |
| symbol changes | likely_but_needs_verification | Identifiers/descriptors exist; exact mapping requires access. |
| permanent/security IDs | likely_but_needs_verification | CRSP identifiers are expected but require access. |
| point-in-time universe membership | likely_but_needs_verification | CRSP security history can support PIT work; exact universe design needs review. |
| all-listed common stock universe | likely_but_needs_verification | Exchange coverage and security metadata can likely support this. |
| exchange/security-type filters | likely_but_needs_verification | Exchange and descriptors are documented. |
| active/inactive status | likely_but_needs_verification | Delisting/status information can support this. |
| liquidity fields | confirmed_from_official_docs | Volume and shares outstanding are documented. |
| local cache feasibility | unknown | Depends on institutional access method and license. |
| metadata/versioning feasibility | likely_but_needs_verification | Versioned database releases appear documented. |
| API or bulk export | requires_institutional_access | Access mechanism depends on CRSP/WRDS/institution. |
| required subscription/account | requires_institutional_access | Not assumed available. |

## Polygon/Massive

| Field | Review label | Notes |
|---|---|---|
| survivorship-free equities | likely_but_needs_verification | Knowledge-base notes discuss avoiding survivorship bias via delisted tickers. |
| delisted names | confirmed_from_official_docs | Docs/knowledge base describe `active=false` / delisted ticker handling. |
| delisting returns or treatment | unknown | Delisting-return treatment is not established from public docs reviewed. |
| adjusted OHLCV | likely_but_needs_verification | Stock docs include aggregates and corporate actions; adjustment process must be verified. |
| splits/dividends | confirmed_from_official_docs | Corporate-action/splits/dividends endpoints are documented. |
| corporate actions | likely_but_needs_verification | Ticker events and corporate-action endpoints exist, but full event coverage needs verification. |
| symbol changes | confirmed_from_official_docs | Ticker Events are documented as tracking ticker history. |
| permanent/security IDs | likely_but_needs_verification | FIGI/CIK fields appear in docs; availability by endpoint/plan must be checked. |
| point-in-time universe membership | unknown | Not established. |
| all-listed common stock universe | likely_but_needs_verification | Ticker endpoints may support broad discovery; PIT construction remains uncertain. |
| exchange/security-type filters | likely_but_needs_verification | Ticker type/market fields are documented. |
| active/inactive status | confirmed_from_official_docs | Active status is documented. |
| liquidity fields | likely_but_needs_verification | OHLCV data likely includes volume. |
| local cache feasibility | unknown | Terms and plan rights must be reviewed. |
| metadata/versioning feasibility | likely_but_needs_verification | API metadata can be captured if terms permit. |
| API or bulk export | confirmed_from_official_docs | REST APIs and plans are public. |
| required subscription/account | requires_paid_access | Useful coverage likely paid. |

## Tiingo

| Field | Review label | Notes |
|---|---|---|
| survivorship-free equities | unknown | Public page snippets mention delisted tickers, but serious survivorship treatment is unverified. |
| delisted names | likely_but_needs_verification | Needs official package/API verification. |
| delisting returns or treatment | unknown | Not established. |
| adjusted OHLCV | likely_but_needs_verification | Public page references adjusted prices; exact fields require review. |
| splits/dividends | likely_but_needs_verification | Public page references splits/dividends. |
| corporate actions | unknown | Needs package review. |
| symbol changes | unknown | Needs verification. |
| permanent/security IDs | unknown | Needs verification. |
| point-in-time universe membership | unknown | Not established. |
| all-listed common stock universe | unknown | Not established. |
| exchange/security-type filters | unknown | Needs verification. |
| active/inactive status | unknown | Needs verification. |
| liquidity fields | likely_but_needs_verification | Price data likely includes volume. |
| local cache feasibility | unknown | Terms review required. |
| metadata/versioning feasibility | unknown | Needs verification. |
| API or bulk export | likely_but_needs_verification | API access appears available. |
| required subscription/account | requires_paid_access | Useful coverage likely paid. |

## EODHD

| Field | Review label | Notes |
|---|---|---|
| survivorship-free equities | unknown | Public docs reviewed do not establish survivorship-free U.S. equity research quality. |
| delisted names | unknown | Needs verification. |
| delisting returns or treatment | unknown | Not established. |
| adjusted OHLCV | confirmed_from_official_docs | Public pages describe historical EOD OHLCV adjusted for splits/dividends. |
| splits/dividends | confirmed_from_official_docs | Splits and dividends are listed as datasets. |
| corporate actions | likely_but_needs_verification | Some corporate action fields appear available; serious mapping needs review. |
| symbol changes | unknown | Needs verification. |
| permanent/security IDs | unknown | Needs verification. |
| point-in-time universe membership | unknown | Not established. |
| all-listed common stock universe | unknown | Needs verification. |
| exchange/security-type filters | likely_but_needs_verification | Broad exchange coverage appears likely; filters need verification. |
| active/inactive status | unknown | Needs verification. |
| liquidity fields | likely_but_needs_verification | OHLCV likely includes volume. |
| local cache feasibility | unknown | Terms review required. |
| metadata/versioning feasibility | likely_but_needs_verification | API metadata can be captured if terms permit. |
| API or bulk export | confirmed_from_official_docs | Public docs list API/SDK endpoints. |
| required subscription/account | requires_paid_access | Useful coverage likely paid. |

## Field-Coverage Conclusion

Norgate is the best practical first path for Gate 1E because it most directly addresses survivorship-free listed/delisted equity research for an individual research workflow. CRSP appears strongest academically but access is the blocker. Sharadar is the strongest API-style secondary candidate but must prove delisting treatment and PIT/all-listed universe support. Fallback APIs are not rejected, but they need much stronger field proof before serious stock momentum claims.

