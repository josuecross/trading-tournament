# Minimum Data Contract Spec

Future serious stock momentum implementation requires a dataset with:

- symbol,
- permanent_id if available,
- date,
- open/high/low/close/volume,
- adjusted close or adjustment factors,
- splits/dividends,
- delisting date,
- delisting return or delisting price treatment,
- exchange,
- security type,
- active/inactive status,
- corporate action metadata,
- universe membership or all-listed universe,
- liquidity fields,
- provider metadata,
- acquisition timestamp,
- cache version,
- data quality flags.

## Required Filters

- common stocks only, if possible,
- minimum price,
- minimum dollar volume,
- exclude OTC/pink sheets unless explicitly reviewed,
- no leverage,
- no margin,
- no shorting,
- maximum position count,
- concentration cap suitable for a $3,000 account.

## Future Evidence

Future acquisition evidence must include provider metadata, symbol coverage, delisted-name coverage, adjustment checks, missingness checks, cache hash, and confirmation that raw OHLCV is excluded from advisor packets.

