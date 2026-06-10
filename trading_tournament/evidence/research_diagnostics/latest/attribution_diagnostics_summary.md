# Attribution Diagnostics Summary

Purpose: add reusable attribution diagnostics so future historical research can explain component target contribution, drawdown contribution, recovery contribution, target-window incrementality, and duplicate/diversification posture.

## Infrastructure Status

- target-window attribution support: available
- component final-equity contribution support: available
- component drawdown attribution support: available when component return streams or daily contribution streams are supplied
- recovery attribution support: available when component return streams or daily contribution streams are supplied
- worst-N drawdown extraction support: available
- drawdown co-incidence detail support: available
- duplicate/diversification diagnostic summary support: available

## Batch 1 Export Status

The optional diagnostics-only export produced `batch1_attribution_detail.csv` from existing Batch 1 diagnostics inputs.

- target-window attribution: available
- component final-equity contribution: available
- component drawdown contribution: unavailable in Batch 1 detail without daily component contribution streams
- component recovery contribution: unavailable in Batch 1 detail without daily component contribution streams
- worst-N drawdown windows: available
- candidate_exhaustive run: false
- data downloaded: false

## Interpretation

This infrastructure improves evidence quality for future reviews, but it does not change current Batch 1 decisions. `combo_plus_managed_futures_80_20_v1` and `top2_plus_managed_futures_80_20_v1` remain short-history watchlist rows, and `combo_plus_top2_50_50_v1` remains duplicate_or_near_duplicate.

No real-money recommendation is made.

