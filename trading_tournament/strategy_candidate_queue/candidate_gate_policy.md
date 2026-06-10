# Candidate Gate Policy

This policy controls when a queued idea can become an implementation task. Passing a gate does not validate a strategy or promote it to paper-forward. No real-money recommendation is made by passing any gate. Coding is allowed only after all required gates for the candidate pass.

## 1. Evidence Gate

- Pass criteria: The candidate has a clear research prior, a fixed rule concept, and a reason it may improve stop-aware profit potential or diversification.
- Fail criteria: The idea is only exciting, anecdotal, curve-fit, or selected because another strategy disappointed.
- Required evidence: Source prior, expected return driver, expected benchmark, failure mode, and anti-overfitting risk.
- Coding allowed after passing: No, this gate only permits data and feasibility review.

## 2. Data Gate

- Pass criteria: Required symbols or datasets are available, auditable, adjusted consistently, and have sufficient history for rolling windows.
- Fail criteria: Missing symbols, short history, survivorship bias, unverified vendor data, current-ticker-only stock evidence, or raw data that cannot be included in compact evidence.
- Required evidence: Data source, coverage window, survivorship/delisting policy where relevant, and no-network cache status.
- Coding allowed after passing: Only if other required gates also pass.

## 3. Execution Realism Gate

- Pass criteria: The existing daily ETF-style engine can model timing, costs, and fills plausibly for the candidate.
- Fail criteria: The candidate requires options chains, futures rolls, forex financing, intraday fills, order book modeling, margin, assignment, liquidation, or broker-specific execution.
- Required evidence: Execution timing assumptions, cost model, tradability notes, and explicit no-broker boundary.
- Coding allowed after passing: Only for simple daily ETF/fund candidates and only after other gates pass.

## 4. Risk-Model Gate

- Pass criteria: The candidate can be evaluated under the $3,000 account, +$300/+400/+600/+900/+1200 ladder, -$600 stop budget, drawdown-budget usage, and stress-cost framework.
- Fail criteria: Risk cannot be bounded, stop behavior cannot be modeled, leverage/margin is required, or high volatility overwhelms the current risk framework.
- Required evidence: Expected stop risk, target potential, stress scenario, and failure mode.
- Coding allowed after passing: Only if data and execution gates also pass.

## 5. Benchmark Gate

- Pass criteria: The candidate has a clear primary benchmark and comparison set.
- Fail criteria: No relevant benchmark, benchmark chosen after results, or comparison would be apples-to-oranges.
- Required evidence: Primary benchmark, secondary benchmarks, and expected correlation with current finalists.
- Coding allowed after passing: No, but implementation design may proceed if other gates are passed.

## 6. Diversification Gate

- Pass criteria: The candidate plausibly adds a return driver or risk profile not already covered by SPY_200d, combo_SPY200d_GLD_50_50, top2 asset-class momentum, GLD, SPY buy-hold, or BIL.
- Fail criteria: The candidate is a near-duplicate without a clear reason to improve stop-aware profit/risk.
- Required evidence: Expected correlation, diversification value, and duplicate/near-duplicate assessment.
- Coding allowed after passing: Only if it also passes the data, execution, risk, benchmark, complexity, target, and anti-overfitting gates.

## 7. Complexity Gate

- Pass criteria: The strategy is minimalist, fixed-rule, explainable, and can be tested without parameter grids.
- Fail criteria: Many variants, hidden optimization, complex instruments, unbounded implementation scope, or required infrastructure outside the project gates.
- Required evidence: Canonical rule sketch, fixed universe, fixed timing, fixed benchmarks, and no tuning plan.
- Coding allowed after passing: Only for queue items that pass all other gates.

## 8. Target-Potential Gate

- Pass criteria: The candidate has a plausible route to improving stop-aware profit potential, not merely lowering volatility.
- Fail criteria: The candidate is likely too slow for +$300/+400 or has upside that comes only from unacceptable stop/drawdown risk.
- Required evidence: Expected target potential, stop risk, and why it might beat current finalists.
- Coding allowed after passing: Only if the risk model gate also passes.

## 9. Anti-Overfitting Gate

- Pass criteria: The candidate is predeclared, limited in variants, and can be evaluated without parameter optimization or result-driven redesign.
- Fail criteria: Parameter grids, multiple lookback variants, tuning after seeing results, or deleting weak candidates.
- Required evidence: Versioned candidate id, fixed fields, and promotion requirements.
- Coding allowed after passing: Only after all gates pass and only as a separate implementation task.
