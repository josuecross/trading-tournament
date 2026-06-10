# Strategy Family Classification

This classification is a research triage document. It does not validate any strategy and does not recommend real-money trading.

## Plausible Core Candidates

### Broad ETF Investing

- Evidence quality: strong as benchmark exposure, moderate as active edge.
- Role: core / benchmark.
- Reason: liquid, transparent, easy to model with daily adjusted data.
- What would invalidate it: target-before-stop rates that are no better than simple benchmarks after stress costs.
- Evidence required before implementation changes: rolling 30/60/90/180-day target-before-stop, benchmark comparison, and stress slippage.

### Time-Series Momentum

- Evidence quality: strong to moderate.
- Role: core.
- Reason: historically studied trend family with objective signals.
- What would invalidate it: whipsaw, poor stress results, or target rates below challenge needs.
- Evidence required: all fixed-rule ETF tests, rolling windows, drawdown, and benchmark-relative behavior.

### Cross-Sectional Momentum

- Evidence quality: moderate.
- Role: core.
- Reason: can exploit dispersion among ETFs or sectors.
- What would invalidate it: returns explained by a few symbols, excessive slippage sensitivity, or weak stress rolling windows.
- Evidence required: contribution analysis, symbol concentration, rolling target-before-stop, and stress slippage.

### Dual Momentum

- Evidence quality: moderate to strong.
- Role: core.
- Reason: combines cross-sectional and absolute trend concepts.
- What would invalidate it: defensive whipsaw, slow recovery, or no improvement over SPY trend benchmark.
- Evidence required: benchmark comparison, target-before-stop, and regime analysis.

### Tactical Asset Allocation

- Evidence quality: moderate to strong.
- Role: core.
- Reason: can combine return seeking with defensive allocation.
- What would invalidate it: too slow to reach target or still hitting the trailing stop.
- Evidence required: independent rolling windows and stress-slippage survival.

## Plausible Satellites

### Sector Rotation

- Evidence quality: moderate.
- Role: satellite / core-adjacent.
- Reason: sector dispersion may help, but correlations can collapse diversification.
- What would invalidate it: concentration in a few sectors or no improvement over broad ETFs.
- Evidence required: contribution, regime, and stress-slippage analysis.

### Volatility Targeting

- Evidence quality: moderate.
- Role: risk overlay / satellite.
- Reason: may reduce drawdown and stop hits.
- What would invalidate it: lower target rates without meaningful drawdown improvement.
- Evidence required: paired comparison versus non-vol-scaled strategy.

### Mean Reversion

- Evidence quality: weak to moderate.
- Role: satellite / shadow-only.
- Reason: short-term oversold bounces can work in some regimes, but are fragile.
- What would invalidate it: repeated small losses, loss-budget kills, or high slippage sensitivity.
- Evidence required: separate fixed-rule validation, not tuning.

### Breakout Systems

- Evidence quality: moderate but fragile.
- Role: satellite / shadow-only.
- Reason: can catch trends but false breakouts are common.
- What would invalidate it: poor profit factor under stress, high turnover, or loss-budget kills.
- Evidence required: Donchian-style benchmark, stress slippage, and rolling windows.

## Defensive Benchmarks

### Buy-And-Hold

- Evidence quality: strong.
- Role: benchmark.
- Reason: sets beta baseline.
- What would invalidate it: not applicable as benchmark; it can be inadequate for challenge timing.
- Evidence required: same adjusted data and effective dates.

### Defensive Rotation

- Evidence quality: moderate.
- Role: benchmark / defensive component.
- Reason: helps assess whether complexity improves drawdown.
- What would invalidate it: higher drawdown or lower return than simple cash/Treasury proxies.
- Evidence required: benchmark and drawdown comparison.

### Risk Parity

- Evidence quality: moderate.
- Role: defensive benchmark.
- Reason: useful for drawdown comparison, likely too slow for +$300 in short windows.
- What would invalidate it: poor drawdown control or hidden concentration.
- Evidence required: contribution and rolling drawdown.

### Cash / Treasury Strategies

- Evidence quality: strong as benchmark.
- Role: benchmark / defensive.
- Reason: essential for cash drag and reserve comparison.
- What would invalidate it: not a target engine.
- Evidence required: yield/cash proxy assumptions.

## Research-Only Ideas

### Individual Stock Momentum

- Evidence quality: moderate in literature, unknown in this project.
- Role: research-only.
- Reason: higher volatility may reach target, but data and bias risk are high.
- What would invalidate it: no survivorship-free universe or delisting handling.
- Evidence required: data memo before code.

### Dividend / Yield Strategies

- Evidence quality: moderate.
- Role: research-only / portfolio context.
- Reason: likely too slow for the challenge metric.
- What would invalidate it: target rate too low.
- Evidence required: memo only unless project goal changes.

### Crypto Momentum

- Evidence quality: weak to moderate and exchange-specific.
- Role: research-only.
- Reason: high volatility could hit target, but risk and data issues are severe.
- What would invalidate it: no clean exchange-specific data and fee model.
- Evidence required: crypto data/execution memo.

### Forex Carry / Momentum

- Evidence quality: moderate in broader research, unknown here.
- Role: research-only.
- Reason: requires financing, spreads, leverage, and broker assumptions.
- What would invalidate it: no realistic execution model.
- Evidence required: feasibility memo.

## Too Complex For Now

### Options Directional Strategies

- Evidence quality: unknown in this project.
- Role: too complex for now.
- Reason: option-chain data, IV, spreads, and decay are required.
- What would invalidate it: absence of realistic option fills.
- Evidence required: options framework plan before prototype.

### Options Premium Strategies

- Evidence quality: suspicious without tail modeling.
- Role: too complex for now / reject for now.
- Reason: small gains can hide rare large losses.
- What would invalidate it: missing margin and assignment model.
- Evidence required: tail-risk simulation and margin model.

### Futures Trend Following

- Evidence quality: moderate in literature, unknown here.
- Role: too complex for now.
- Reason: leverage, margin, continuous contracts, and rolls.
- What would invalidate it: no roll-adjusted data or margin model.
- Evidence required: futures framework memo.

### Volatility Strategies

- Evidence quality: suspicious.
- Role: too complex for now.
- Reason: path dependency and product mechanics dominate naive backtests.
- What would invalidate it: no product-specific model.
- Evidence required: volatility-product framework.

## Rejected For Now

### Crypto Leverage / Perpetuals

- Evidence quality: unknown.
- Role: reject.
- Reason: liquidation, funding, exchange, and leverage risks are outside scope.
- Evidence required before reconsideration: dedicated derivatives framework.

### Intraday Trading

- Evidence quality: weak in current data context.
- Role: reject for now / defer.
- Reason: current daily data cannot model fills or spread.
- Evidence required: clean intraday bid/ask or high-quality bars.

### Event / News Momentum

- Evidence quality: unknown.
- Role: reject for now / defer.
- Reason: timestamp leakage risk is severe.
- Evidence required: point-in-time event data.

### AI Market-Condition Gating

- Evidence quality: unknown and risky.
- Role: reject as trade gate.
- Reason: narrative discretion can hide overfitting.
- Evidence required: none for trading use; later report-audit only.
