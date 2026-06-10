# Provider Feasibility Notes

No provider was contacted. All notes require future verification.

## CRSP

CRSP could provide academic-grade survivorship-aware equity history, delisted names, delisting treatment, and point-in-time identifiers if accessible. It is the best serious academic-grade path but is likely institutional/paywalled and operationally heavy. Worth pursuing only if access already exists or cost is acceptable.

## Norgate Data

Norgate may be the most practical serious candidate if affordable and accessible. It likely supports survivorship-free workflows and local caching, but delisting coverage, adjustment fields, license terms, and cache rights require verification. Worth pursuing next if the user wants a practical serious path.

## Nasdaq Data Link / Sharadar

Sharadar may support a serious path depending on subscription package and availability of SEP/SF1/actions/delisted fields. It requires API-key, subscription, and terms/security review. Worth pursuing if package coverage can be confirmed without assuming delisting returns are present.

## Polygon/Massive

Polygon/Massive may provide useful EOD and corporate-action data, but survivorship-free universe, delisted-name coverage, and point-in-time construction are unclear. It may support Tier 1 or possibly Tier 2 only after careful coverage review.

## Tiingo

Tiingo may be useful for EOD API work, but serious stock momentum requires verification of delisted names, universe construction, corporate actions, and terms. It is not approved for serious evidence from this review.

## EODHD

EODHD may provide broad EOD data and corporate-action fields, but delisting treatment and point-in-time universe support are unclear. It could be reviewed for Tier 1/Tier 2 only if coverage is verified.

## Alpaca

Alpaca is useful for current market data or execution context, but likely not sufficient for serious historical survivorship-free research. It is not preferred for this historical lane.

## Interactive Brokers

Interactive Brokers may provide current or broker-adjacent data access, but it is likely unsuitable for serious historical survivorship-free validation. It also sits close to broker-integration boundaries, which remain forbidden.

## yfinance/current ticker lists

yfinance/current-ticker lists are toy-only. They may test code paths, but cannot support serious performance evidence.

## Stooq/public CSV

Stooq/public CSV sources may be useful for rough exploration, but terms, adjustments, survivorship, delisting treatment, and reproducibility are weak or unknown. Treat as toy or defer.

