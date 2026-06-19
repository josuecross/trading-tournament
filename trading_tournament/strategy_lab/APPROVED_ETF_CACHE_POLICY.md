# Approved ETF Cache Policy

This project is a research-only paper/demo strategy lab. It may use practical ETF/fund-wrapper adjusted daily data for approved symbols, but it does not claim institutional-grade data quality and it does not support real-money trading decisions.

## Cache-First Rule

- Existing local cache is preferred.
- If approved ETF/fund-wrapper adjusted daily data is missing, explicit bootstrap is allowed.
- Bootstrap must be requested by a runner flag or prompt; audit-only mode must not download.
- Only symbols listed in `strategy_lab/approved_etf_symbol_map.yaml` may be bootstrapped.
- No silent substitution is allowed. Missing symbols must remain missing until that exact symbol is cached.

## Allowed Data Scope

- Approved ETF/fund-wrapper daily adjusted data only.
- Raw OHLCV may remain in the local cache format, but raw OHLCV must not be included in compact/advisor evidence packets.
- Evidence must label this data as exploratory, non-institutional, and not real-money-ready.
- Provider/API use must be logged with symbol, timestamp, status, and QA result.

## Forbidden Scope

- No individual stocks.
- No direct futures.
- No options.
- No forex.
- No crypto.
- No intraday.
- No leveraged or inverse ETFs unless explicitly approved in a later policy update.
- No broker integration, live orders, order placement, or real-money recommendation.

## Basic Data QA

A cached or bootstrapped symbol must pass basic QA before a strategy run uses it:

- adjusted close exists,
- adjusted close is not fully empty,
- enough rows exist for required indicators,
- no duplicate dates,
- first date is recorded,
- last date is recorded,
- row count is recorded,
- warmup sufficiency is recorded.

If QA fails, the symbol is treated as missing for readiness purposes and any affected result should be marked incomplete or recommended for rerun after cache repair.
