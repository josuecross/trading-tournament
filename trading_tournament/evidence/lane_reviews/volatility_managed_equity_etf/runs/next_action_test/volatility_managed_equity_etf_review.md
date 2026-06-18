# Volatility-Managed Equity ETF Lane Review

Decision context: the latest promotion gap review recommended `volatility_managed_equity_etf` because current research rows are dominated by missing diagnostics, drawdown-budget failures, duplicate blends, and blocked provider/instrument lanes.

This is a review/design gate only. It does not implement a strategy, run a backtest, run Profit Exploration, download data, call provider APIs, run candidate_exhaustive, activate paper-forward, mutate active observations, replace frozen controls, add broker integration, place orders, or make a real-money recommendation.

## Strategy Idea

Use ETF/fund wrappers to test whether volatility-managed equity exposure can improve the current project gap: high-upside rows often breach the -$600 drawdown budget, while defensive rows become too slow or duplicate existing leaders.

The lane remains:

- ETF/fund wrapper only
- daily adjusted data only
- research_sample only
- exploratory and non-final
- no leverage
- no margin
- no shorting
- no options
- no futures
- no forex
- no intraday
- no broker integration
- no paper-forward activation

## Why This Lane May Help

- It directly targets drawdown-budget failures.
- It may preserve equity target potential better than pure cash dilution.
- It may produce a non-duplicate challenger if exposure changes are driven by volatility regimes rather than simply adding GLD or BIL.
- It stays compatible with fast ETF/fund exploratory data policy.

## Why This Lane May Fail

- It may reduce exposure too much and become too slow.
- It may duplicate `SPY_200d_trend_model`.
- It may reduce drawdown but also reduce +$300/+400 target probability.
- It may overfit volatility thresholds if future implementation tunes parameters.
- It may react after drawdowns instead of before them.
- It may look useful only because of a specific historical regime.

## Current Promotion Gap Inputs

- watchlist_missing_diagnostics: 24 rows
- blocked_survivorship_or_point_in_time_data: 19 rows
- too_risky_drawdown_budget: 17 rows
- duplicate_existing_leader: 10 rows
- protected_frozen_control: 8 rows
- too_slow_target_dilution: 7 rows
- rejected_low_value: 4 rows
- watchlist_short_history: 4 rows
- protected_active_observation: 2 rows
- protected_historical_leader: 1 rows

## Input Files Read

- strategy_lab\PROMOTION_POLICY.md
- strategy_lab\policies\EVIDENCE_TIER_POLICY.md
- strategy_lab\policies\EXPERIMENT_LANE_POLICY.md
- strategy_lab\policies\PAPER_FORWARD_FREEZE_POLICY.md
- strategy_lab\promotion_thresholds.yaml
- strategy_lab\strategy_registry.yaml
- evidence\promotion_gap\latest\promotion_gap_summary.md
- evidence\promotion_gap\latest\next_research_lane_recommendation.md
- evidence\promotion_gap\latest\next_allowed_action.md
- evidence\promotion_gap\latest\failure_mode_summary.csv
- evidence\promotion_gap\latest\closest_to_promotion.csv
- evidence\promotion_gap\latest\research_lane_ranking.csv
- evidence\promotion_review\latest\promotion_decisions.csv
- evidence\strategy_lab\latest\warnings_and_limitations.md

## Missing Input Files

- evidence\strategy_lab\latest\current_state_summary.md
- evidence\strategy_lab\latest\candidate_status_matrix.csv
- evidence\strategy_lab\latest\historical_leaders.csv
- evidence\strategy_lab\latest\active_observations.csv
