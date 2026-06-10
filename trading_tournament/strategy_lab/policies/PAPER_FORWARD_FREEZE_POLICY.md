# Paper-Forward Freeze Policy

Active paper-forward strategies are frozen.

Rules:

- No mid-test rule changes.
- No parameter changes.
- No adding or removing strategies from the same observation without restarting a new observation.
- No broker integration, live orders, or order placement.
- Improvements require a new strategy id and version.
- Paper-forward results cannot be merged with exploratory results.
- A stopped observation is evidence, not permission to tune rules.

Current frozen rows are exported in `active_paper_forward_freeze.csv`.
