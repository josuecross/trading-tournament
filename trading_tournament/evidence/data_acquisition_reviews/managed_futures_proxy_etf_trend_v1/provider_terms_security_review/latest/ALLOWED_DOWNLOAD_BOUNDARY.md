# Allowed Download Boundary

Boundary decision: Option A, allow only `DBMF` and `KMLM` for the first future controlled download prompt.

## Approved First-Prompt Symbols

- `DBMF`
- `KMLM`

## Conditional Or Excluded From First Prompt

- `CTA`: excluded until ticker identity is resolved by a separate review.
- `FMF`: optional/lower priority after methodology and fund status review.
- `WTMF`: optional/lower priority after methodology and fund status review.

CTA: excluded until ticker identity is resolved.
FMF: optional/lower priority after methodology and fund status review.
WTMF: optional/lower priority after methodology and fund status review.

## Future Download Must

- use no broker APIs
- use no live orders
- use no futures contract logic
- use no strategy logic
- use no backtest trigger
- produce provider metadata
- produce coverage summaries
- produce data-quality summaries
- produce proxy methodology review requirements
- keep raw OHLCV out of advisor upload
- avoid secrets in the repo
- stop before strategy implementation
