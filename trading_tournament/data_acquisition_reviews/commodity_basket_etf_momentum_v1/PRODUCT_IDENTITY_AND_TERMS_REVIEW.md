# Product Identity And Terms Review

Before any acquisition, each reviewed symbol must have official product identity and terms confirmed.

## Required Product Identity Fields

For each of DBC, PDBC, COMT, GSG, and USCI, a future review must confirm:

- official product name,
- issuer,
- wrapper type,
- ETF / ETN / trust / commodity pool / fund classification,
- index or active strategy,
- inception date,
- expense ratio,
- tax/K-1 treatment if applicable,
- futures-linked exposure,
- collateral/cash/T-bill treatment,
- issuer/product closure risk,
- adjusted-price modeling acceptability,
- whether raw OHLCV can remain in local cache only,
- whether metadata summaries can be included in advisor packets.

## Terms And Security Requirements

- No raw data may be redistributed in advisor packets.
- No API keys may be written to the repo.
- No secrets may appear in evidence, logs, manifests, or zip packets.
- Provider terms must allow local research cache use before acquisition.
- Metadata summaries may be included only if terms permit.
- If terms are unclear, acquisition remains blocked.

## Current Status

Product identity and terms are not confirmed enough to approve a download prompt in this task. A future product identity/terms review is required before any yfinance-compatible or keyed-provider acquisition.
