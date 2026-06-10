# False Confidence Risks

## Backtest Overfitting

- What it is: rules fit to history rather than durable behavior.
- How it could fool the project: a strategy looks strong only because it was redesigned around known failures.
- Mitigation: no parameter optimization, fixed rules, rolling validation, weak results retained.

## Repeated Redesign Until Something Works

- What it is: trying variants until one looks exciting.
- How it could fool the project: the "winner" is just the survivor of many undocumented attempts.
- Mitigation: anti-overfitting log and implementation gates.

## Treating Sampled Validation As Final

- What it is: using deterministic samples as if they were all possible windows.
- How it could fool the project: probability estimates look more certain than they are.
- Mitigation: label sampled runs non-final and reserve exhaustive mode for finalists.

## Treating Paper Fills As Realistic

- What it is: assuming backtest fills would be available live.
- How it could fool the project: results overstate achievable execution.
- Mitigation: stress slippage and explicit paper-fill limitations.

## Underestimating Slippage

- What it is: costs too low for turnover, spreads, or market conditions.
- How it could fool the project: a small edge disappears live.
- Mitigation: standard and stress slippage comparisons.

## Ignoring Fees, Taxes, And Cash Drag

- What it is: simplified accounting.
- How it could fool the project: net performance may be overstated.
- Mitigation: document omissions and avoid income claims.

## Ignoring Live Execution Problems

- What it is: failing to model orders, latency, gaps, and liquidity.
- How it could fool the project: a clean backtest hides operational risk.
- Mitigation: no live trading and no broker integration.

## Treating ETFs As The Whole Opportunity Set

- What it is: narrowing too early.
- How it could fool the project: the project answers only an ETF subquestion.
- Mitigation: opportunity map before further code.

## Adding Complex Instruments Without Modeling Execution

- What it is: coding options, futures, crypto, or intraday rules with naive assumptions.
- How it could fool the project: high-risk instruments look easier than they are.
- Mitigation: Gate 0 and Gate 1 required.

## Treating AI Explanations As Edge

- What it is: accepting persuasive narrative as market signal.
- How it could fool the project: discretionary AI decisions hide overfitting.
- Mitigation: AI report-audit only, no trade gating.

## Confusing Engineering Sophistication With Profitability

- What it is: assuming a larger framework means a better strategy.
- How it could fool the project: observability is mistaken for edge.
- Mitigation: evidence hierarchy and benchmark comparison.

## Mistaking Benchmark Beta For Strategy Edge

- What it is: making money because the market rose.
- How it could fool the project: strategy appears useful but does not beat simple exposure.
- Mitigation: SPY, basket, cash, and trend benchmarks.

## Survivorship And ETF Inception Bias

- What it is: missing failed or unavailable instruments.
- How it could fool the project: historical opportunity is overstated.
- Mitigation: data coverage and inception review.

## Static Universe Bias

- What it is: using a fixed current universe for old periods.
- How it could fool the project: selection benefits from hindsight.
- Mitigation: document limitation and avoid overclaiming.

## Evidence Packet Overconfidence

- What it is: believing many files imply strong evidence.
- How it could fool the project: process output replaces evidence quality.
- Mitigation: prioritize the evidence hierarchy.

## Runtime-Driven Shortcuts

- What it is: downsampling or skipping tests because they are expensive.
- How it could fool the project: non-final evidence is treated as final.
- Mitigation: label sampled results and require exhaustive validation for finalists.
