# Risk Policy

Future research_sample must evaluate:

- +$300 target-before-stop
- +$400 target-before-stop
- absolute -$600 budget
- trailing drawdown behavior
- max drawdown
- target dilution
- stress/slippage if applicable
- benchmark-relative drawdown
- correlation/overlap with existing leaders
- whether volatility management adds value or simply duplicates `SPY_200d_trend_model`

Risk rules:

- No leverage
- No margin
- No shorting
- No options
- No futures
- No forex
- No intraday
- No broker integration
- No live orders
- No real-money recommendation
- No active observation mutation

If a variant reduces drawdown but destroys target probability, mark `too_slow`.

If a variant keeps target probability but breaches the drawdown budget, mark `too_risky`.

If a variant mostly reproduces `SPY_200d_trend_model` or the active combo historical row, mark `duplicate_or_near_duplicate`.
