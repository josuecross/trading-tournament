# Dual Momentum PAA ETF Wrapper Data Policy

Allowed default symbols:

- `SPY`
- `QQQ`
- `EFA`
- `EEM`
- `IWM`
- `GLD`
- `IEF`
- `BIL`

Conditional benchmark-only:

- `TLT`
- `AGG`

Optional only if already approved elsewhere:

- `DBC` or broad commodity ETF wrapper, benchmark-only unless explicitly approved later.

Do not use individual stocks, leveraged ETFs, inverse ETFs, direct futures, options, forex, crypto, intraday data, sector ETFs as core symbols, or managed-futures wrappers as core symbols in this lane.

This review does not download data. A future research_sample may use yfinance-compatible adjusted daily ETF/fund-wrapper data only if explicitly prompted and clearly labeled as exploratory/non-institutional.
