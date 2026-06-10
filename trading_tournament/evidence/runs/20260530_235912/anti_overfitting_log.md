# Anti-Overfitting Log

- No parameter optimization was run.
- No grid search was run.
- Validation mode used: smoke.
- Strategy parameters were pre-specified in `config_used.yaml`.
- Existing C/D/E strategies were not tuned to improve results.
- New strategy families N1-N4 were tested using fixed daily ETF rules.
- All weak results are retained in `strategy_variant_results.csv` and `independent_rolling_window_summary.csv`.
- All possible rolling windows used: False.
- Rolling window methods observed: ['deterministic_stratified_sample'].
- Rolling validation final: False.
- Rolling method used: deterministic_stratified_sample.
- Sampled results are final: False.
- Rolling results are deterministic research samples or partial results; they are non-final.

- If any sampled windows appear in a run, treat that run as non-final validation.
- No broker integration, no live orders, no AI trading gate, and no real-money recommendation.
