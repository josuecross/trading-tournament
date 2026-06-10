# Anti-Overfitting Log

- No parameter optimization was run.
- No grid search was run.
- Strategy parameters were pre-specified in `config_used.yaml`.
- Existing C/D/E strategies were not tuned to improve results.
- New strategy families N1-N4 were tested using fixed daily ETF rules.
- All weak results are retained in `strategy_variant_results.csv` and `independent_rolling_window_summary.csv`.
- All possible rolling windows used: False.
- Rolling window methods observed: [].
- Rolling validation final: False.
- Independent rolling validation did not complete; this run is non-final for rolling-window probability claims.
- If any sampled windows appear in a future run, treat that run as non-final validation.
- No broker integration, no live orders, no AI trading gate, and no real-money recommendation.
