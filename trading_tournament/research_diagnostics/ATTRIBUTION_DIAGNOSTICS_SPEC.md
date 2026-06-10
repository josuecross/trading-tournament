# Attribution Diagnostics Spec

This is diagnostics infrastructure only. It does not implement strategies, run candidate_exhaustive, download data, change paper-forward rules, connect to brokers, place orders, or recommend real-money trading.

## Purpose

The attribution diagnostics layer helps future historical research explain:

- which components contributed to target hits,
- which components contributed to drawdowns,
- whether target windows are incremental versus combo/top2 benchmarks,
- whether drawdown improvement is independent or only lower exposure,
- whether a candidate is duplicate, diversifying, too slow, or genuinely additive.

## Inputs

Functions accept pandas Series or DataFrames supplied by caller code:

- daily equity curves,
- daily component return streams,
- component weights,
- window-level target flags,
- benchmark window flags,
- benchmark equity curves.

The module does not read raw cache files and does not call data providers.

## Core Outputs

The schema in `attribution_schema.yaml` defines:

- `target_window_attribution`,
- `component_contribution`,
- `drawdown_attribution`,
- `recovery_attribution`,
- `worst_n_drawdown_windows`.

Missing optional inputs should return explicit unavailable status fields rather than silently inventing diagnostics.

## Governance

Attribution diagnostics can support future research_sample and candidate_exhaustive review prompts, but they do not approve paper-forward activation or real-money use.

Active paper/demo observations remain separated from historical diagnostics. The active combo paper/demo observation is not changed by this infrastructure.

