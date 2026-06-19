# Fix Recommendations

1. Add exploratory labels such as `diversifier_watchlist_candidate`, `short_history_watchlist`, and `benchmark_watchlist` without weakening promotion or paper-forward gates.
2. Export combined benchmark-delta rows from parallel discovery so later audits do not need to infer from per-family or score-only outputs.
3. Keep managed-futures wrapper results marked short-history/watchlist unless future cached data length improves.
4. Do not rerun candidate validation or paper-forward from this audit; no high-severity implementation bug was found that would justify immediate reruns.
