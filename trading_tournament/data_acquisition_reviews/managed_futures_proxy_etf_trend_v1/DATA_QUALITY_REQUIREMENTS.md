# Data Quality Requirements

Any future acquired proxy series must pass metadata and quality checks before implementation review can be updated.

## Required Fields And Metadata

- daily dates
- adjusted close
- raw close if available
- splits/dividends if available
- sorted dates
- provider metadata
- acquisition timestamp
- request/config hash
- cache write manifest
- no raw OHLCV in advisor packets

## Required Quality Checks

- row count
- first date
- last date
- common overlap with SPY, BIL, combo/top2 benchmark windows where feasible
- duplicate dates
- missing adjusted close
- missing close
- missing volume
- gap report
- adjustment field report
- enough rows for 200-day SMA
- enough rows for 126-day momentum
- enough rows for 30/60/90/180 rolling windows after warmup

If a proxy fails a core quality check, the strategy must remain unimplemented and no backtest should run.

