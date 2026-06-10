# Delisting And Corporate Actions Spec

Stock momentum cannot be credible unless delistings and corporate actions are treated explicitly.

## Required Treatment

- Delistings: include delisted names through their final tradable date.
- Bankruptcies: include terminal losses or conservative terminal values.
- Acquisitions: handle final cash/stock consideration when available or use conservative final price treatment.
- Mergers: preserve continuity only when the data vendor provides a valid mapping.
- Symbol changes: map historical identifiers without losing return history.
- Splits: adjusted OHLC must correctly handle split ratios.
- Dividends: dividend adjustments must be documented and auditable.
- Spin-offs: treatment must be specified by the data source or conservatively excluded/flagged.
- Missing terminal prices: use a conservative fallback and flag the event.
- Data revisions: cache source files and record vendor/version dates where possible.

## Conservative Fallback

If delisting returns are unavailable, do not approve Gate 2 except for toy-demo mode. A toy demo must be clearly labeled non-evidence and must not appear in strategy validation tables as a serious result.

