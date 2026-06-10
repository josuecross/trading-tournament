# Rejected Or Deferred Candidates

This file records candidates that are not being implemented. They are blocked, deferred, or rejected for now because required gates have not passed.

- Options premium: reject for now. The project lacks option-chain data, realistic spreads/fills, margin, assignment, tail-risk, and exercise modeling.
- Options directional: defer. Directional options require option-chain history, Greeks, IV, bid/ask, assignment/exercise, and realistic fill modeling.
- Futures trend following: defer until a futures framework exists. The project lacks continuous contracts, roll rules, margin, leverage, gap, and contract-specific risk handling.
- Forex carry/momentum: defer. The project lacks spread, financing, rollover, leverage, and broker execution modeling.
- Intraday/day trading: reject for now. Current daily bars cannot model intraday fills, queue position, spreads, stops, or opening range behavior.
- Volatility products: reject for now. Product decay, roll yield, path dependency, event risk, and product mechanics are not modeled.
- Crypto leverage/perps: reject. Leverage, perpetual swaps, funding, liquidation, exchange outage/custody risk, and 24/7 execution are outside current gates.
- Individual stock momentum implementation: defer until Gate 1B/Gate 2 requirements pass. Serious evidence requires survivorship-free data, delisting returns, point-in-time universe, corporate actions, and an execution/cost model.
- AI trading gate: reject as a trade gate. The project must not use AI to approve trades or bypass fixed rules and evidence gates.

These items may be revisited only through explicit gate memos. No code is approved here.
