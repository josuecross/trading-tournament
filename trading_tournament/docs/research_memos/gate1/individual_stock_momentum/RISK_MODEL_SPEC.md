# Risk Model Spec

The stock momentum risk model must be at least as strict as the ETF project model.

## Core Risk Rules

- Starting equity: $3,000.
- Project target: +$300 to +$400.
- Project stop: -$600 / -20%.
- Max single position exposure: preliminary 20% to 25% of equity.
- Max strategy exposure: no margin and no leverage.
- Max sector exposure: preliminary 30% if sector data is available.
- Max open risk: must fit within the project-level risk cap.
- Stop-loss handling: gap-through-stop fills at open; same-bar stop/target assumes stop first.
- Earnings gap handling: block entries near earnings or explicitly model gap risk.
- Daily/weekly loss blocks: use existing project discipline if applicable.
- Strategy kill criteria: predefine max strategy loss and disable condition.
- No martingale.
- No unplanned averaging down.
- No shorting initially.

## Gate 2 Requirement

All thresholds must be finalized before the first prototype run. No threshold may be tuned to improve historical results.

