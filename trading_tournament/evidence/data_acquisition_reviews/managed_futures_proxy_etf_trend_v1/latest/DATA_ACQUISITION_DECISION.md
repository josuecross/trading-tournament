# Data Acquisition Decision

Decision: `acquisition_review_passed_create_provider_terms_review`

This decision permits a future provider terms/security review prompt. It does not approve an actual data download.

Provider terms/security review update: completed on 2026-06-05 with decision `approve_future_yfinance_download_prompt_dbmf_kmlm_only`. This later review approves a future controlled yfinance-compatible download prompt for `DBMF` and `KMLM` only. It does not download data, call an API, implement a strategy, run a backtest, add futures contract logic, or change paper-forward rules.

Controlled acquisition update: run `20260605_162923` downloaded and cached `DBMF` and `KMLM` only. Both symbols passed data-quality checks. `CTA`, `FMF`, and `WTMF` were not downloaded. `SPY` and `BIL` were not refreshed. Issuer/fund methodology review remains required before any strategy implementation prompt.

## Rationale

The candidate is data-gated because `DBMF`, `KMLM`, `CTA`, `FMF`, and `WTMF` are missing from local cache. Missing local cache should not be treated as permanent `data_unavailable`; it means provider lookup, terms/security review, and data-quality planning are required.

Managed-futures proxy funds may add a return driver that is less equity-beta-like than recent QQQ, value/momentum, and sector candidates. However, no proxy history, common overlap, or methodology evidence can be evaluated until provider coverage and data quality are reviewed.

## Next Allowed Action

Create a provider terms/security review. That future review should decide whether a controlled acquisition prompt may use the yfinance-compatible path or whether a keyed provider or deferral is required.

## Explicit Non-Actions

- No data download.
- No API call.
- No API key or secret.
- No strategy implementation.
- No backtest.
- No Profit Exploration run.
- No futures contract logic.
- No broker integration or live orders.
- No paper-forward rule change.
- No real-money recommendation.
