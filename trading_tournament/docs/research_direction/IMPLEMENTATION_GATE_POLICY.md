# Implementation Gate Policy

This policy prevents random expansion. No new instrument or strategy family should be implemented until it passes the relevant gate.

## Gate 0 - Research Memo Only

- No code.
- Describe the instrument or strategy.
- Identify data needs.
- Identify execution risks.
- Identify modeling risks.
- Explain why it might or might not fit the +$300/+400 goal.

Gate 0 is the default for options, futures, forex, crypto, volatility products, intraday trading, event/news strategies, and AI trade gating.

## Gate 1 - Feasibility Review

Required before prototype permission:

- Data source identified.
- Execution model identified.
- Slippage/spread assumptions identified.
- Risk model identified.
- Benchmarks identified.
- Failure criteria defined.

If these are missing, implementation is blocked.

## Gate 2 - Prototype Permission

Only if Gate 1 passes:

- Prototype must live in an isolated module.
- Prototype must not affect existing ETF Phase 1 results.
- Prototype must produce an evidence packet.
- Prototype must be labeled experimental.
- Prototype must not be used to select real trades.

## Gate 3 - Candidate Validation

Required for candidate status:

- Standard and stress assumptions.
- Rolling-window testing.
- Target-before-stop analysis.
- Benchmark comparison.
- Drawdown analysis.
- No parameter tuning.
- Weak results retained.

## Gate 4 - Paper-Forward Watchlist

Only after candidate validation:

- Fixed rules only.
- No mid-test changes.
- No real-money trading.
- No live execution.
- No broker integration.

## Instruments Currently Failing The Gate

### Options

Fail because option-chain data, bid/ask, IV, Greeks, assignment, exercise, and spread fill models are not implemented.

### Futures

Fail because continuous contracts, roll logic, margin, leverage, and gap risk are not modeled.

### Forex

Fail because financing, rates, broker spreads, and leverage assumptions are not modeled.

### Crypto Leverage

Fail because liquidation, funding, exchange-specific fees, and 24/7 risk are not modeled.

### Volatility Products

Fail because product mechanics, decay, roll yield, path dependency, and event risk are not modeled.

### Intraday Trading

Fail because current daily bars cannot model intraday fills, spread, queue, or stop behavior.

### Event / News Strategies

Fail because point-in-time event data and timestamp integrity are not available.

Conclusion: these areas may receive research memos, but not trading code, until their gates are passed.
