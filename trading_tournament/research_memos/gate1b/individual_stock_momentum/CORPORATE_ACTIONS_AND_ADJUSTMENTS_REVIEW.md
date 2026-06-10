# Corporate Actions And Adjustments Review

Individual stock momentum requires reliable adjusted prices and event handling.

## Requirements

- adjusted close suitable for total-return-style momentum,
- split handling,
- dividend handling,
- symbol-change handling,
- merger/acquisition treatment,
- delisting event handling,
- spinoff handling if available,
- stale or anomalous adjustment detection.

Bad adjustment data can fake momentum by creating artificial jumps, suppressing losses, or splitting one security history into multiple broken tickers.

## Required Data-Quality Checks

- duplicate dates,
- missing adjusted close,
- split jump sanity checks,
- abnormal return outliers around corporate actions,
- symbol continuity checks,
- delisting event coverage,
- volume/price missingness,
- provider revision metadata.

Conclusion: corporate-action integrity must be reviewed before any stock momentum implementation prompt.

