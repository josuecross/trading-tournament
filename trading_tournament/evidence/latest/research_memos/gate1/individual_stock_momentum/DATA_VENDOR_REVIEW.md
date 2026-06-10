# Data Vendor Review

No web browsing was performed for this memo. Vendor items below are templates and prior-known categories that require external verification before any implementation.

| Source Category | Survivorship-Free Universe Available? | Delisted Stocks Included? | Delisting Returns Available? | Corporate Actions Included? | Point-In-Time Membership Available? | Earnings Data Available? | Cost / Access Burden | API / Export Availability | License Concerns | Suitability | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|
| CRSP or academic-grade survivorship-free data | likely yes, verify | likely yes, verify | likely yes, verify | likely yes, verify | likely yes, verify | separate source likely needed | high | institutional/export, verify | high; academic/commercial terms | best serious research candidate if accessible | possible |
| Norgate Data | likely yes for equities, verify | likely included, verify | verify | likely included, verify | index membership may be available, verify | likely separate source needed | moderate | export/API options need verification | commercial license | plausible retail-accessible candidate | possible |
| Polygon | unknown | unknown | unknown | likely corporate actions, verify | unknown | possible earnings fields, verify | moderate/high | API likely | commercial terms | possible only if survivorship/delisting solved | unknown |
| Nasdaq Data Link / Sharadar-type datasets | possible, verify | possible, verify | verify | likely included, verify | possible, verify | possible fundamentals/events, verify | moderate/high | API/export likely | commercial terms | plausible if dataset includes delisted tickers | possible |
| Tiingo | unknown | unknown | unknown | likely adjusted prices, verify | unknown | unknown | moderate | API likely | commercial terms | insufficient unless survivorship-free universe exists | unknown |
| EODHD | unknown | unknown | unknown | likely corporate actions, verify | unknown | possible calendar data, verify | low/moderate | API likely | commercial terms | not serious unless delisted/universe features verified | unknown |
| Interactive Brokers historical data | no serious research universe by itself | no | no | partial/varies | no | no | account/platform dependent | API/platform | broker data terms | execution reference, not research database | unsuitable |
| Alpaca historical data | no serious research universe by itself | no/unknown | no/unknown | partial/varies | no | no | low/moderate | API | broker/vendor terms | possible recent toy data only | unsuitable |
| yfinance/current ticker data | no | no | no | partial and revised | no | no reliable point-in-time event support | low | Python download | personal-use/data quality issues | toy demo only, not serious evidence | toy-only |

Strict conclusion: yfinance current tickers should be labeled toy-only, not serious research evidence. Serious Gate 2 approval requires verified survivorship-free coverage and delisting treatment.

## Gate 1A Vendor Verification

A focused Gate 1A vendor verification packet now exists at `vendor_verification/`.

Decision: `continue_defer`.

Summary: CRSP and Norgate Data appear to be the most credible serious-research candidates from official pages, with Sharadar/Nasdaq Data Link requiring follow-up. yfinance/current-ticker data remains toy-only. Gate 2 remains blocked until access, cost, license, local caching, delisting-return/terminal treatment, point-in-time universe construction, and runtime/storage burden are verified.
