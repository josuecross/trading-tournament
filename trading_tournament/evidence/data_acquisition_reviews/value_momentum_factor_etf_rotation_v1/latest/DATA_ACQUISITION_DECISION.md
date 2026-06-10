# Data Acquisition Decision

Decision: `conditional_pending_terms_or_api_key`

Provider terms/security addendum: `approve_future_yfinance_download_prompt`

## Rationale

MTUM, VLUE, VTV, QUAL, USMV, and SPLV are missing from local cache, but that should not be interpreted as permanent data unavailability. They are now classified as `data_acquisition_required` or `provider_review_required`.

The project has plausible provider candidates, including the existing yfinance-compatible path and keyed public/paid APIs. However, no provider terms, coverage, adjustment behavior, API-key handling, or quality workflow has been approved in this task.

Follow-up provider terms/security review approved a future yfinance-compatible download prompt for MTUM, VLUE, VTV, QUAL, USMV, and SPLV only. That future prompt must be explicit and must produce provider metadata, coverage summaries, and data-quality summaries before any strategy implementation or backtest.

## What This Decision Allows

- A future data-download prompt may be drafted after provider terms/security review.
- Future work may check provider coverage and acceptable adjusted-price semantics.
- Future evidence may contain metadata and coverage summaries.

## What This Decision Does Not Allow

- No data download now.
- No API call now.
- No API key or secret in the repo.
- No strategy implementation.
- No backtest.
- No paper-forward activation.
- No real-money recommendation.
