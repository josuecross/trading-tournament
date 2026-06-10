# Earnings And Event Handling Spec

Earnings and corporate events can dominate individual stock returns and gap risk.

## Handling Options

1. Avoid entries within N trading days before earnings.
2. Exit before earnings.
3. Allow earnings but model gap risk explicitly.
4. Use only strategies that do not require earnings timestamps.

## Preferred First Prototype Policy

The preferred first prototype policy is to avoid new entries near earnings until event data quality is known. A preliminary rule could block new entries from 5 trading days before scheduled earnings through 1 trading day after the announcement, but the exact window must be finalized before testing.

If reliable point-in-time earnings dates are unavailable, the project should either use a no-earnings-data strategy with explicit gap-risk acceptance or defer implementation.

## Non-Negotiable Rule

No earnings rule may use future announcement dates unavailable at signal time.

