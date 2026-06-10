# Gate 1 Decision

## Decision

`defer`

## Rationale

Individual stock momentum remains a plausible research family, but a serious isolated prototype is not approved. The project has not identified a verified survivorship-free data source, delisted stock coverage, delisting returns, point-in-time universe membership, acceptable cost/access terms, or runtime/storage impact.

Current yfinance/current-ticker data is toy-only for this purpose. It cannot support serious claims about stock momentum.

## What Is Allowed Next

- Continue Gate 1 vendor and feasibility research.
- Verify survivorship-free data candidates.
- Compare cost/access and licensing.
- Define final universe and execution assumptions before any code.
- Optionally consider a toy-demo-only plan later, clearly labeled as non-evidence.

## What Is Blocked

- Serious Gate 2 isolated prototype.
- Stock momentum strategy implementation.
- Stock data loader implementation.
- Backtests.
- Data downloads.
- Parameter tuning.
- Broker integration.
- AI trading gates.
- Real-money recommendations.

## Evidence Required To Change Decision

- Survivorship-free data source identified and accessible.
- Delisted stocks included.
- Delisting returns or conservative terminal treatment available.
- Corporate action handling feasible.
- Point-in-time universe construction feasible.
- Execution model defined.
- Benchmarks defined.
- Costs and runtime acceptable.

## Toy Demo Status

Toy demo is not approved in this memo. It may be reconsidered only if clearly labeled non-evidence and isolated from validation outputs.

## No Real-Money Statement

This decision does not recommend real-money trading and does not approve implementation.

## Gate 1A Update

Gate 1A vendor verification has been created at `vendor_verification/`.

Gate 1A decision: `continue_defer`.

The original Gate 1 decision remains `defer`. Serious Gate 2 implementation and toy-demo implementation remain blocked. The most credible follow-up candidates are CRSP and Norgate Data, but access, cost, license, local caching, delisting-return/terminal treatment, and point-in-time universe feasibility are not yet resolved.
