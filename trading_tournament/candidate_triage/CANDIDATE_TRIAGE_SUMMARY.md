# Candidate Triage Summary

## Boundary

This packet is research-only paper/demo governance. It does not implement strategy logic, run a backtest, run Profit Exploration, run candidate_exhaustive, download data, change paper-forward rules, or make a real-money recommendation.

## Summary Decision

The recent one-off ETF candidate expansion did not produce a new candidate_exhaustive row.

- QQQ dual momentum produced high target rates but used too much stop/drawdown budget.
- Value/momentum factor ETF rotation was mostly an equity-beta duplicate.
- Sector top2 remains watchlist only, with sector dispersion interest but equity-beta duplicate risk.
- Managed-futures proxy reduced drawdown but was too slow and has short-history fund-wrapper limitations.

The practical path remains combo/SPY200d/GLD review rather than adding more one-off ETF variants. `combo_SPY200d_GLD_50_50_v1` remains the practical leader and promotion-review path. `asset_class_tsmom_top2_v1` remains a serious challenger. `SPY_200d_trend_model` remains the frozen paper-forward candidate.

## Current Candidate Exhaustive Decision

No recent research_sample candidate should be added to candidate_exhaustive now. QQQ, value/momentum, sector top2, and managed-futures proxy all remain below the evidence threshold for candidate_exhaustive.

## Single Best Next Action

Pause one-off ETF candidate expansion and move the combo paper-forward observation-plan review forward, while keeping managed-futures proxy as a diversification watchlist item only.

