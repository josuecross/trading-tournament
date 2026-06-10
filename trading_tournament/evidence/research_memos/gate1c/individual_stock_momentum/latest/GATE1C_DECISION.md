# Gate 1C Decision

Decision: `conditional_choose_provider_before_data_acquisition`

## Meaning

Individual stock momentum should not proceed to implementation, backtest, Profit Exploration, data acquisition, candidate_exhaustive, or paper-forward observation.

The next allowed action is to choose a serious provider for provider terms/security review. CRSP, Norgate Data, and Nasdaq Data Link / Sharadar are the most plausible serious paths, subject to cost/access/field verification.

## Serious Provider Review

Serious provider review is approved as the next governance step. It is not a data download approval.

## Toy Implementation

Toy/current-ticker implementation is not approved as the next step. If proposed later, it must be labeled `current_ticker_toy_only`, not preferred for the main objective, and unable to support serious claims.

## Forbidden

Do not implement stock momentum, add stock data loaders, download stock data, call provider APIs, run backtests, run Profit Exploration, approve paper-forward, add broker integration, place orders, or make a real-money recommendation.

