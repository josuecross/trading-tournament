# Gate 1 Feasibility Review: Individual Stock Momentum

Feasibility question: can individual stock momentum be credibly implemented in this project without unacceptable data bias, execution fantasy, or scope creep?

## 1. Research-Only Statement

This review is research-only. It does not implement stock momentum, approve live trading, connect to a broker, place orders, or recommend real-money trading.

## 2. Gate 0 Summary

Gate 0 concluded that individual stock momentum is plausible enough for feasibility review because stock dispersion may improve the probability of reaching +$300 to +$400 from a $3,000 simulated account. Gate 0 also concluded that implementation is blocked until survivorship-free data, delisting treatment, corporate action handling, liquidity rules, earnings treatment, benchmarks, execution assumptions, risk model, and validation plan are resolved.

## 3. Feasibility Question

The question is not whether stock momentum is interesting. It is whether this project can test it honestly. A current-ticker backtest would be inadequate for serious evidence.

## 4. Data Feasibility

Data feasibility is unresolved. Serious testing requires survivorship-free historical stock data, delisted names, corporate actions, point-in-time universe membership, and auditable adjusted OHLCV. Current yfinance ticker data is toy-only for this purpose.

## 5. Universe Feasibility

A conservative long-only U.S. common-stock universe is feasible in concept, but it requires point-in-time membership and pre-specified eligibility rules. Without that, the prototype would risk index membership lookahead and survivorship bias.

## 6. Delisting Feasibility

Delisting feasibility is the largest blocker. If delisted stocks and delisting returns are unavailable, Gate 2 should not be approved except for a clearly labeled toy demo.

## 7. Corporate Actions Feasibility

Corporate action handling is feasible only if the chosen data source provides reliable split, dividend, merger, symbol-change, and adjustment information. The current ETF adjusted-OHLC approach is not enough by itself for stock universes.

## 8. Earnings / Event Feasibility

Earnings dates are a major risk. The first prototype should avoid new entries near earnings unless point-in-time earnings dates are available. Any earnings rule must be fixed before testing.

## 9. Execution / Slippage Feasibility

Long-only liquid large-cap stocks may be feasible later. Low-float, penny, illiquid, short, or margin-based variants are not feasible in this framework. Spread and slippage assumptions must be conservative and fixed before testing.

## 10. Benchmark Feasibility

Benchmark feasibility is acceptable. SPY, cash/BIL, 60/40, ETF momentum, broad stock equal-weight, and stock momentum benchmarks can be specified. The broad stock benchmarks depend on the same data source and universe quality.

## 11. Risk Model Feasibility

The ETF project risk model can provide the starting shell: $3,000 starting equity, +$300/+400 target, -$600 stop, no martingale, no averaging down, no shorting, no margin, exposure caps, and strategy kill criteria. Stock-specific sector and single-name caps are required.

## 12. Runtime / Storage Feasibility

Runtime and storage are uncertain. A survivorship-free stock universe could be much larger than the ETF universe, so Gate 2 needs estimated symbol count, date range, file size, cache design, and rolling validation cost.

## 13. Cost / Access Feasibility

Cost and licensing are unresolved. Academic-grade or commercial survivorship-free datasets may be expensive or restricted. If credible data is not affordable or accessible, the project should defer serious implementation.

## 14. Main Blockers

- No selected survivorship-free data source.
- No delisting-return treatment.
- No point-in-time universe membership source.
- No earnings-date data quality decision.
- No stock-specific spread/slippage model.
- No runtime/storage estimate.
- No licensing review.

## 15. What Would Be Required For Gate 2

Gate 2 requires a credible data source, delisting treatment, corporate action plan, universe specification, earnings policy, liquidity filter, execution model, benchmarks, risk model, validation plan, cost/runtime estimate, and isolated implementation plan.

## 16. Preliminary Gate 1 Decision

Decision: `defer`.

The idea remains worth researching, but serious Gate 2 prototype permission is not approved because the critical data and delisting requirements are not resolved. A toy-demo-only prototype may be considered later only if it is explicitly labeled non-evidence and cannot be confused with serious validation.

