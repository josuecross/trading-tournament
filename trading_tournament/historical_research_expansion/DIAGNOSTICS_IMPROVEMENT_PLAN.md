# Diagnostics Improvement Plan

This is a plan only. It does not run new calculations, change scoring code, implement a strategy, run backtests, run Profit Exploration, or download data.

## 1. Correlation Diagnostics

- daily return correlation versus combo, top2, SPY_200d, GLD, BIL, and SPY buy-hold
- rolling 60/90-day correlation
- stress-period correlation
- target-window co-movement

## 2. Drawdown Co-Incidence

Report whether candidates draw down at the same time as combo, top2, or SPY_200d. A strategy that falls at the same time as the leader is less useful even if its standalone target rate looks acceptable.

## 3. Strategy Contribution

- allocation share
- sleeve contribution
- target-hit contribution
- downside contribution
- concentration by asset, sleeve, proxy fund, or regime

## 4. Regime Tagging

- bull equity
- bear equity
- inflation/rates stress
- gold-favorable
- cash-favorable
- high-volatility windows

## 5. Fresh-Window Exactness Audit

- all rolling windows rebased to `$3,000`
- high-water reset
- stop reset
- target state reset
- no inherited equity slicing

## 6. Dashboard Integration

- current state
- active paper-forward rows
- historical leaders
- watchlist
- blocked/gated
- next allowed actions

## Implementation Boundary

These diagnostics should be added before or alongside the next historical strategy tests. Reporting-only metadata extraction from existing evidence is acceptable; return recomputation, scoring rewrites, or strategy changes require separate scoped tasks.

