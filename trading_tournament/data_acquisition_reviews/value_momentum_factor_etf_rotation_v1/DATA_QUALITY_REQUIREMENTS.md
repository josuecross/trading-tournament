# Data Quality Requirements

These requirements apply to any future acquired ETF series for `value_momentum_factor_etf_rotation_v1`.

## Required Fields And Structure

- Daily dates.
- Adjusted close.
- Raw close if available.
- Splits/dividends if available.
- Sorted dates.
- No duplicate dates.
- Enough rows for 200-day SMA and 126-day momentum warmups.
- Enough rows for 30/60/90/180 rolling windows after warmup.
- Enough common overlap with SPY and BIL.
- Provider metadata.
- Acquisition timestamp.
- Request/config hash or equivalent reproducibility marker.
- Coverage report.

## Acceptance Checks

- Row count by symbol.
- First and last date by symbol.
- Common overlap window.
- Missing-day and gap summary.
- Duplicate-date scan.
- Basic adjusted-price sanity checks.
- Comparison against already cached benchmark symbols when possible.

## Evidence Rule

Raw OHLCV must not be included in advisor packets or compact evidence. Only metadata, coverage summaries, gap reports, and quality flags are allowed in compact evidence.
