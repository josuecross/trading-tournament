# Next Gate 1E Requirements

If the user accepts Norgate as the first provider path, Gate 1E should create a controlled acquisition plan for a tiny sample dataset only, not a full-market download.

## Suggested Gate 1E Scope

- metadata-only dry run first, if provider supports it,
- small symbol set,
- small date range,
- include at least one active symbol and one delisted/inactive symbol if legally and technically available,
- no full universe download until quality and field mapping pass,
- no stock strategy and no backtest.

## Required Gate 1E Outputs

- provider metadata,
- field mapping to the minimum data contract,
- coverage summary,
- delisted/inactive sample check,
- adjustment field check,
- point-in-time/universe check,
- security-type and exchange-filter check,
- liquidity-field check,
- local cache manifest,
- cache hash/metadata if terms permit,
- evidence packet excluding raw data,
- explicit no broker/live/order/real-money flags.

## If No Provider Is Selected

Defer implementation. Do not substitute current-ticker-only yfinance, Stooq, broker data, or incomplete fallback APIs as serious evidence.

