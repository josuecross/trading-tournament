# Tiny Sample Acquisition Plan

This is a future plan only. No acquisition was performed.

## Scope

- maximum symbols: 5 to 20
- include one active liquid common stock if available
- include one delisted/inactive symbol if legally and technically available
- include one symbol with split/dividend history if available
- include one symbol with symbol-change or corporate-action history if available
- date range: small bounded range, preferably 2 to 5 years or event-specific window
- no full-market universe
- no strategy calculation
- no stock backtest
- no Profit Exploration
- no candidate_exhaustive

## Required Future Outputs

- coverage summary,
- field mapping sample,
- delisted/inactive sample check,
- adjustment field check,
- corporate-action sample check,
- security-type/exchange filter check,
- liquidity field check,
- cache manifest,
- raw data exclusion confirmation,
- quality summary,
- metadata summary,
- provider terms/security confirmation,
- no broker/live/order/real-money flags.

## Guardrails

The first future prompt should prefer metadata-only or path/export validation before any row-level data acquisition. Full-universe download remains forbidden until tiny-sample quality and field mapping pass.

