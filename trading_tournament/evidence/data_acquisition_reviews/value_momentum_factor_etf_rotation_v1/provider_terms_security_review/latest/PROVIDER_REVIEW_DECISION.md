# Provider Review Decision

Decision: `approve_future_yfinance_download_prompt`

## Rationale

The project already uses a yfinance-compatible path for ETF research data, and the missing value/momentum factor proxy symbols are ordinary ETF tickers. A future download prompt may use that existing path because it avoids API-key handling and can be tightly limited to the six missing symbols.

This approval is conditional on strict execution boundaries: explicit user approval in a future task, metadata capture, coverage and quality summaries, no strategy implementation, no backtest, and no raw OHLCV in advisor packets.

## Keyed Provider Decision

Keyed providers are not approved for immediate use. Tiingo, Alpha Vantage, Nasdaq Data Link / Sharadar, and Polygon/Massive remain fallback review options only if the yfinance-compatible path is unacceptable or fails quality checks.

## This Decision Does Not Do

- It does not download data.
- It does not call an API.
- It does not create or store an API key.
- It does not implement `value_momentum_factor_etf_rotation_v1`.
- It does not run a backtest.
- It does not change paper-forward rules.
- It does not make a real-money recommendation.
