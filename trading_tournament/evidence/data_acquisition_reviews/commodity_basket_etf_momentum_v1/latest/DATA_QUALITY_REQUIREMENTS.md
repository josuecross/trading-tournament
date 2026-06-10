# Data Quality Requirements

Any future acquired commodity wrapper series must pass daily-price quality checks before research_sample implementation can be considered.

## Required Fields And Checks

- daily dates,
- adjusted close,
- raw close if available,
- open/high/low/close/volume,
- splits/dividends/distributions if available,
- sorted dates,
- no duplicate dates,
- missing-value report,
- enough rows for 126-day momentum,
- enough rows for 200-day SMA if later used,
- enough rows for 30/60/90/180 rolling windows after warmup,
- first/last date,
- common overlap among commodity products,
- common overlap with SPY, GLD, BIL, combo/top2 if feasible,
- provider metadata,
- acquisition timestamp,
- request/config hash,
- no raw OHLCV in advisor packets.

## Quality Statuses

- pass: field coverage, continuity, adjusted prices, overlap, and metadata are sufficient.
- warning: usable only with explicit limitations, such as shorter history or missing action fields.
- fail: missing adjusted close, duplicate dates unresolved, insufficient rows, identity mismatch, or terms/security blocker.

## Evidence Boundary

Compact evidence may include metadata, coverage summaries, data-quality summaries, and cache manifests. Raw OHLCV must stay out of advisor packets.
