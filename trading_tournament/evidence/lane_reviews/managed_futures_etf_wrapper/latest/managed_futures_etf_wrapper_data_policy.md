# Managed Futures ETF Wrapper Data Policy

Allowed default wrapper symbols, only if cache/data is available or later explicitly bootstrapped:

- `DBMF`
- `KMLM`
- `CTA`
- `FMF`
- `WTMF`

Baseline/control symbols:

- `SPY`
- `QQQ`
- `BIL`
- `GLD`
- `IEF`

Conditional benchmark-only:

- `TLT`
- `AGG`

Do not use direct futures contracts, commodity futures contracts, forex contracts, crypto, options, leveraged ETFs, inverse ETFs, individual stocks, or intraday data.

This review does not download data. A future research_sample may use yfinance-compatible adjusted daily ETF/fund-wrapper data only if explicitly prompted and clearly labeled as exploratory/non-institutional. If wrapper histories are short, the future research_sample must label history limitations clearly.
