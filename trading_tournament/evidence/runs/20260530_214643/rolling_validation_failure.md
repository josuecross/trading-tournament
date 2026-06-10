# Rolling Validation Failure / Non-Final Notice

Independent all-possible rolling-window validation did not complete for this run.

The expanded candidate matrix was too expensive for the current pure-Python daily backtest engine during local execution. No sampled rolling-window result is being presented as final validation.

Configured rolling validation: `{'method': 'all_possible', 'max_windows_per_group': None, 'parallel_workers': 0, 'chunk_size': 250, 'max_total_windows_for_local_run': 250000}`

Implication: 30/60/90/180-day target-before-stop probabilities for the redesigned strategy families are unavailable in this evidence bundle. Treat all strategy-family conclusions as non-final watchlist research only until the rolling engine is optimized or an explicit long-running job completes.

No real-money recommendation.
