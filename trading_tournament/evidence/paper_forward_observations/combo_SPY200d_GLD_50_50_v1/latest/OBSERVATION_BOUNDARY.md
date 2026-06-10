# Observation Boundary

This packet prepares only a separate simulated paper/demo observation track for `combo_SPY200d_GLD_50_50_v1`.

## Allowed

- Record a blocked/prepared combo observation row.
- Keep `SPY_200d_trend_model` as the frozen control.
- Compare combo status beside SPY_200d when the paper-forward observation runner is called with `--include-combo-observation`.
- Preserve the approved checkpoint policy: first checkpoint after 30 trading days, then monthly.

## Not Allowed

- Do not replace SPY_200d.
- Do not change combo rules.
- Do not change SPY_200d rules.
- Do not change targets, stops, slippage, costs, or risk framework.
- Do not download data.
- Do not run backtests or Profit Exploration.
- Do not connect to brokers or place orders.
- Do not add a real-money recommendation.

## Failure/Exit References

Activation remains blocked if the rule hash is missing, cached data is unavailable, rule drift appears, evidence is inconsistent, or any broker/live/order behavior appears.
