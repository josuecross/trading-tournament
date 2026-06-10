# Provider Review Decision

Decision: `approve_future_yfinance_download_prompt_dbmf_kmlm_only`

This decision does not download data.

## Rationale

`DBMF` and `KMLM` are the highest-priority managed-futures proxy candidates and are suitable for a tightly bounded future yfinance-compatible acquisition prompt with metadata and quality checks. `CTA` has unresolved ticker identity risk and should not be included unless a separate review resolves identity. `FMF` and `WTMF` remain optional/lower-priority until methodology and fund-status review justify inclusion.

## What Is Approved

A future controlled data acquisition prompt may request `DBMF` and `KMLM` only, using the project yfinance-compatible path, with provider metadata, coverage summaries, quality summaries, and raw-OHLCV exclusion from advisor packets.

## What Is Not Approved

- No data download in this task.
- No API call in this task.
- No keyed provider use.
- No strategy implementation.
- No backtest or Profit Exploration run.
- No futures contract logic.
- No paper-forward activation.
- No broker integration or live orders.
- No real-money recommendation.

