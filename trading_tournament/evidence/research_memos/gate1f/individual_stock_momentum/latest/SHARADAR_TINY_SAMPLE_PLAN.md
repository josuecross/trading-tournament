# Sharadar Tiny Sample Plan

This is a future-only controlled sample plan. No API call or data download was performed.

## Scope

- no full market download,
- no stock strategy,
- no backtest,
- no Profit Exploration,
- no candidate_exhaustive,
- metadata-first if possible,
- maximum symbols: 5 to 20,
- include active and delisted/inactive examples if fields allow,
- bounded date range,
- validate adjusted and unadjusted price fields,
- validate ticker metadata,
- validate corporate action sample,
- validate delisting/inactive sample,
- validate local cache metadata,
- exclude raw data from advisor packets.

## Required Future Outputs

- package/table selection record,
- terms/cache-rights confirmation,
- API-key handling plan using environment variables or ignored local secrets,
- coverage summary,
- metadata summary,
- field mapping sample,
- delisted/inactive sample check,
- adjustment/corporate-action sample check,
- security-type/exchange filter check,
- local cache manifest,
- quality summary,
- raw data exclusion confirmation.

## Not Approved

This plan does not approve API calls, stock data downloads, data loaders, strategy implementation, backtests, candidate_exhaustive, paper-forward observation, broker integration, or real-money recommendation.

