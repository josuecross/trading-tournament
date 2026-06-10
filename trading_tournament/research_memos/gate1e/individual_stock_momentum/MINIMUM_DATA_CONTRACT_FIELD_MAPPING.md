# Minimum Data Contract Field Mapping

No Norgate sample was acquired, and no exact local Norgate field names were inspected. Mappings below use Gate 1D review findings and mark every unverified item conservatively.

| Required field | mapped_norgate_field_or_source | mapping_status | required_for_tiny_sample | blocker_if_missing |
|---|---|---|---|---|
| symbol | Norgate listed/delisted symbol or export symbol | likely_but_needs_sample | true | Cannot identify securities. |
| permanent_id if available | unknown local Norgate identifier | unknown | false | Symbol-change handling weaker; require alternate mapping. |
| date | daily bar date | likely_but_needs_sample | true | Cannot align returns or events. |
| open/high/low/close/volume | daily OHLCV export or plugin data | likely_but_needs_sample | true | Cannot validate price history. |
| adjusted close or adjustment factors | adjusted price/export convention or capital-event adjustment source | likely_but_needs_sample | true | Momentum and return calculations would be unreliable. |
| splits/dividends | dividend/capital-event data source | likely_but_needs_sample | true | Corporate-action adjustment cannot be audited. |
| delisting date | delisted symbol suffix/last trading date or delisted metadata | likely_but_needs_sample | true | Survivorship-aware sample cannot be validated. |
| delisting return or delisting price treatment | last bar/delisted metadata or local treatment rule | unknown | true | Delisting impact may be understated. |
| exchange | major-exchange listing identification or security metadata | likely_but_needs_sample | true | Universe/security filters cannot be enforced. |
| security type | security classification metadata | likely_but_needs_sample | true | Common-stock filter cannot be enforced. |
| active/inactive status | listed vs delisted database source | likely_but_needs_sample | true | Survivorship status cannot be checked. |
| corporate action metadata | capital-event/security information metadata | likely_but_needs_sample | true | Event handling cannot be audited. |
| universe membership or all-listed universe | historical constituent query or listed/delisted universe construction | likely_but_needs_sample | true | PIT/all-listed universe claims cannot be made. |
| liquidity fields | volume plus local close*volume dollar-volume calculation | likely_but_needs_sample | true | Liquidity filter cannot be tested. |
| provider metadata | Norgate package/version/subscription metadata if terms allow | unknown | true | Evidence reproducibility weak. |
| acquisition timestamp | project acquisition metadata | mapped | true | Required for cache governance. |
| cache version | local cache manifest version plus provider update date if available | unknown | true | Cache refresh audit weak. |
| data quality flags | project-generated quality checks | mapped | true | Quality gate cannot pass without local flags. |

## Mapping Summary

The field map is plausible enough to design a future tiny-sample review, but not sufficient to approve acquisition because local Norgate access, terms acceptance, and exact sample fields are missing.

