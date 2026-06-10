# Vendor Shortlist

## Serious Research Candidates

### CRSP

Reason shortlisted:

- Strongest apparent survivorship-free and delisting-aware institutional data candidate.
- Public documentation describes inactive companies, corporate actions, and delisting information/returns.

Remaining blockers:

- Access, cost, export workflow, license, local caching, and project practicality.

Next verification step:

- Verify whether this project can access CRSP and whether the license allows local cached research outputs.

Can support serious Gate 2?

- Possible only if access and license are resolved.

Can support toy demo?

- Not needed; if CRSP is available, use only serious research controls.

### Norgate Data

Reason shortlisted:

- Publicly describes survivorship-bias-free US equities, active and delisted securities, historical index constituents, adjusted price histories, and Python access.
- Appears more practical for a solo local project than CRSP.

Remaining blockers:

- Delisting-return or terminal treatment, cost, license, cache rights, and external evidence-sharing rules.

Next verification step:

- Confirm package contents, trial/sample data, delisting treatment, and license terms.

Can support serious Gate 2?

- Possible if unresolved blockers are cleared.

Can support toy demo?

- Toy demo is not approved by this packet.

## Possible Candidates Needing Follow-Up

### Nasdaq Data Link / Sharadar

Reason shortlisted:

- Plausible commercial source category for equity data and fundamentals.

Remaining blockers:

- Serious survivorship-free coverage, delisting treatment, point-in-time universe construction, package availability, cost, and license were not verified.

Next verification step:

- Review current official dataset documentation and contact vendor if needed.

Can support serious Gate 2?

- Unknown.

## Toy-Only Sources

### yfinance / Current Tickers

Reason listed:

- Easy local mechanics and already used for ETF data, but current-ticker stock universes are not serious evidence.

Remaining blockers:

- No survivorship-free universe, delisting returns, or point-in-time membership.

Can support serious Gate 2?

- No.

Can support toy demo?

- Only if separately approved as isolated non-evidence. This packet does not approve that.

## Unsuitable Or Reference-Only Sources

### Interactive Brokers

Use:

- Execution/reference source only.

Blocker:

- Does not solve survivorship-free historical universe and delisting needs.

### Alpaca

Use:

- Execution/reference or recent market-data source only.

Blocker:

- Does not solve survivorship-free historical universe and delisting needs.

### Polygon, Tiingo, EODHD

Use:

- Possible market-data follow-ups only.

Blocker:

- Serious survivorship-free and delisting treatment were not verified in this packet.
