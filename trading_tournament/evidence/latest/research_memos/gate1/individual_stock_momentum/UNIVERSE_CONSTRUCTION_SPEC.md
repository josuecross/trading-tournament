# Universe Construction Spec

This is a proposed initial universe for Gate 2 if approval is later granted. These rules must be finalized before testing and must not be tuned based on results.

## Proposed Conservative Universe

- Long-only.
- U.S. common stocks only.
- Exclude ETFs, funds, preferreds, warrants, units, rights, ADRs, and OTC names unless explicitly allowed in a later memo.
- Minimum adjusted price: preliminary $5 at signal date.
- Minimum average dollar volume: preliminary $10 million 20-day average dollar volume.
- Minimum trading history / IPO seasoning: preliminary 252 trading days before eligibility.
- No low-float, penny-stock, or microcap focus.
- Rebalance frequency: preliminary monthly or weekly, fixed before testing.
- Universe membership: determined point-in-time only.
- Sector cap: preliminary 30% if point-in-time sector data is available.
- Max number of positions: preliminary 5 to 10 for small-account testing.
- Position concentration cap: preliminary 20% to 25% of equity per name.

## Rules Not Approved Yet

Momentum lookback, trend filters, earnings handling, and exact ranking logic are not approved here. This document only defines feasibility constraints.

## Gate 2 Finalization Requirement

Exact thresholds must be finalized in a Gate 2 spec before any test is run. They must not be selected after reviewing performance.

